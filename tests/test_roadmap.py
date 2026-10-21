"""Tests for the roadmap orchestrator.

Most cases drive :func:`plan_tool.roadmap.run_roadmap` with an injected
three-stage table, the real step-1 parsers and renderers, canned gate sets, and a
fake invoker; their stage templates are written to a tmp directory and
``prompts_dir`` is patched at the module (fixture ``env``). The cases that
exercise the **shipped** table and its prompt files instead run against the real
``plan_tool/prompts/`` directory (fixture ``shipped_env``). The classes that
drive the real gate sets end to end are marked ``integration``.
"""

from __future__ import annotations

import ast
import contextlib
import functools
import hashlib
import inspect
import json
import os
import re
from dataclasses import dataclass, fields, replace
from pathlib import Path
from string import Template
from types import SimpleNamespace
from typing import Any, Optional, Sequence

import pytest

from plan_tool import backend_runner, claude_errors, roadmap, roadmap_gates, shell
from plan_tool import model_response_sidecar
from plan_tool.scope_fence import extract_h2_sections, h2_section_spans
from plan_tool import roadmap_impact_snapshot
from plan_tool.create import validate_from_existing_seed
from plan_tool.renderer import prompts_dir
from roadmap_accepted_fixtures import advance_accepted_head, publish_accepted_root
from subprocess_doubles import _FakeProc
from plan_tool.roadmap import (
    ACCEPT_OUTCOME_ACCEPTED,
    ACCEPT_OUTCOME_REFUSED,
    APPLY_OUTCOME_APPLIED,
    APPLY_OUTCOME_RECOMMENDED,
    APPLY_OUTCOME_REFUSED,
    FAILURE_AUTHORED_REVIEW_ROWS,
    FAILURE_GATES,
    FAILURE_INVOKE,
    FAILURE_PARSE,
    OUTCOME_COMPLETED,
    OUTCOME_COMPLETED_NO_CHANGE,
    OUTCOME_STAGE_EXHAUSTED,
    OUTCOME_STAGE_INVALID,
    RoadmapError,
    RoadmapHeadExistsError,
    RoadmapPreHeadStateError,
    RoadmapResult,
    RoadmapSeedRefreshFailure,
    SEED_REFRESH_OUTCOME_APPLIED,
    SEED_REFRESH_OUTCOME_EXHAUSTED,
    SEED_REFRESH_OUTCOME_PARTIAL,
    RoadmapStage,
    accept_roadmap_seed,
    apply_roadmap_seeds,
    refresh_roadmap_seeds,
)
from plan_tool.roadmap_seed_state import (
    digest_text,
    empty_seed_state,
    load_seed_state,
    seed_refresh_report_path,
    seed_state_path,
    write_seed_state,
)
from plan_tool.roadmap_source import (
    CarriedDecision,
    CarriedDecisions,
    digest_decoded_text,
    read_brief_text,
)
from plan_tool.roadmap_stage_resume import (
    RESUME_DIRNAME,
    resume_dir_path,
    write_brief_digest,
    write_stage,
)
from plan_tool.roadmap_seed_manifest import (
    NoPublishedRoadmapVersionError,
    no_published_version_message,
)
from plan_tool.roadmap_seed_manifest import (
    DRAFT_SEED_STATE_CURRENT,
    DRAFT_SEED_STATE_DIGEST_MISMATCHED,
    DRAFT_SEED_STATE_DUPLICATE,
    DRAFT_SEED_STATE_MALFORMED,
    DRAFT_SEED_STATE_MISSING,
    DRAFT_SEED_STATE_PATH_ESCAPING,
    DRAFT_SEED_STATE_STALE,
    DraftSeedClassification,
)
from plan_tool.roadmap_artifacts import (
    AttributeDispositionRow,
    BusinessRuleRow,
    COMPONENTS_FILENAME,
    COMPONENTS_ROW_KEYS,
    ComponentRow,
    ComponentsArtifact,
    CONSTRAINTS_FILENAME,
    CONSTRAINTS_ROW_KEYS,
    ConstraintDisposition,
    ConstraintRow,
    ConstraintsArtifact,
    DOMAIN_FILENAME,
    DOMAIN_ROW_KEYS,
    DecisionRow,
    DecisionStatus,
    DomainArtifact,
    EntityRow,
    FeedbackRow,
    FeedbackState,
    FeedbackTarget,
    FeedbackTargetKind,
    FieldRow,
    FieldType,
    HOSTING_FACETS,
    HostingRow,
    STACK_CONCERNS,
    StackRow,
    PatternRow,
    PLANS_FILENAME,
    PLANS_ROW_KEYS,
    DRAFT_SEED_CROSS_CUTTING_KEY,
    DRAFT_SEED_ROADMAP_COMPONENTS_KEY,
    PlanDisposition,
    PlanRow,
    PlansArtifact,
    AssumptionRow,
    OrderingEntry,
    QUALITY_ATTRIBUTES,
    REVIEW_ROW_KEYS,
    RejectedAlternative,
    RemovalRecord,
    RoadmapArtifactError,
    StoreRow,
    WorkflowRow,
    components_path,
    constraints_path,
    domain_path,
    draft_seeds_dir,
    load_components_artifact,
    load_constraints_artifact,
    load_domain_artifact,
    load_plans_artifact,
    parse_components_artifact,
    parse_constraints_artifact,
    parse_domain_artifact,
    parse_plans_artifact,
    parse_draft_seed_provenance,
    plans_path,
    render_components_artifact,
    render_constraints_artifact,
    render_domain_artifact,
    render_plans_artifact,
    resolve_draft_seed_path,
    roadmap_dir,
)
from plan_tool.roadmap_versions import (
    ACCEPTED_HEAD_FILENAME,
    accepted_head_path,
    is_roadmap_enrolled,
    load_accepted_version,
    version_namespace_path,
)
from plan_tool.roadmap_feedback_ledger import (
    LedgerState,
    load_ledger,
    roadmap_feedback_ledger_path,
)
from plan_tool.roadmap_source_identity import (
    GenerationMember,
    PendingGeneration,
    pending_generation_path,
    render_pending_generation,
)
from plan_tool.roadmap_gates import (
    COMPONENTS_GATES,
    CONSTRAINTS_GATES,
    DOMAIN_GATES,
    HOSTING_FACET_VALUES,
    PLANS_GATES,
    VIOLATION_ALTERED_SETTLED_DECISION,
    VIOLATION_DROPPED_DESIGN_ROW,
    VIOLATION_DROPPED_FEEDBACK,
    VIOLATION_UNDEFINED_ENTITY_REFERENCE,
    VIOLATION_UNDEFINED_PATTERN_REFERENCE,
    VIOLATION_UNDISPOSED_ATTRIBUTE,
    VIOLATION_UNRESOLVED_CONSTRAINT_ANCHOR,
    VIOLATION_UNCOVERED_ENTITY,
    ArtifactEnvelope,
    Violation,
    run_components_gates,
    run_constraints_gates,
    run_domain_gates,
    run_plans_gates,
)
from plan_tool.run_log import RunLogLineTooLarge, RunLogWriter, read_run_events


SLUG = "storefront"
BRIEF = "A storefront that takes orders.\n"


def _source_json_path(plans_dir: Path) -> Path:
    """The recorded-brief file the stage run no longer writes; tests pin its absence."""
    return roadmap_dir(plans_dir, SLUG) / "source.json"


# --------------------------------------------------------------------------
# Artifact builders — every one clears the real gate sets
# --------------------------------------------------------------------------


def _decision(
    prefix: str, index: int, *, anchor: str, status: DecisionStatus
) -> DecisionRow:
    return DecisionRow(
        id=f"dec-{prefix}-{index}",
        chosen_option="one aggregate",
        rejected_alternatives=(
            RejectedAlternative(option="two aggregates", reason="splits the invariant"),
        ),
        rationale="keeps the invariant local to one write path",
        anchor=anchor,
        status=status,
    )


def _body(*row_ids: str) -> str:
    """A prose body naming every inventoried row, which the prose gate wants."""
    named = " ".join(f"`{row_id}`" for row_id in row_ids)
    return f"\n## Notes\n\nThis artifact describes {named}.\n"


def _domain(
    *,
    entity_ids: Sequence[str] = ("order",),
    statuses: Sequence[DecisionStatus] = (DecisionStatus.SETTLED,),
) -> DomainArtifact:
    entities = tuple(
        EntityRow(
            id=entity_id,
            name=entity_id.title(),
            fields=(FieldRow(name="id", type=FieldType.TEXT),),
        )
        for entity_id in entity_ids
    )
    anchor = entity_ids[0]
    decisions = tuple(
        _decision("domain", index, anchor=anchor, status=status)
        for index, status in enumerate(statuses, start=1)
    )
    rules = (
        BusinessRuleRow(
            id="rule-1",
            statement="an order is paid before it ships",
            entity_ids=(anchor,),
        ),
    )
    workflows = (WorkflowRow(id="flow-1", name="Checkout", entity_ids=(anchor,)),)
    return DomainArtifact(
        entities=entities,
        business_rules=rules,
        workflows=workflows,
        decisions=decisions,
        body=_body(
            *entity_ids,
            "rule-1",
            "flow-1",
            *(row.id for row in decisions),
        ),
    )


def _domain_text(**kwargs: Any) -> str:
    return render_domain_artifact(_domain(**kwargs))


def _carried_domain_brief(*, source_id: str = "answer-domain") -> str:
    decision = _domain().decisions[0]
    block = {
        "confirmed_answers": [
            {"id": source_id, "answer": decision.chosen_option, "status": "confirmed"}
        ],
        "decisions": [
            {
                "id": decision.id,
                "owner": "domain",
                "anchor": decision.anchor,
                "chosen_option": decision.chosen_option,
                "source": source_id,
                "rationale": decision.rationale,
                "rejected_alternatives": [
                    {"option": item.option, "reason": item.reason}
                    for item in decision.rejected_alternatives
                ],
            }
        ],
    }
    return "# Concept\n\n## Carried decisions\n\n```json\n" + json.dumps(block) + "\n```\n"


def _constraints(
    *,
    anchor: str = "order",
    statuses: Sequence[DecisionStatus] = (DecisionStatus.SETTLED,),
) -> ConstraintsArtifact:
    dispositions = tuple(
        AttributeDispositionRow(
            id=f"disp-{attribute}",
            attribute=attribute,
            disposition=(
                ConstraintDisposition.PRIORITIZED
                if attribute == "performance"
                else ConstraintDisposition.NOT_LOAD_BEARING
            ),
        )
        for attribute in QUALITY_ATTRIBUTES
    )
    constraints = (
        ConstraintRow(
            id="con-1",
            statement="checkout answers under 200ms at p95",
            attribute="performance",
            anchor_ids=(anchor,),
        ),
    )
    decisions = tuple(
        _decision("constraints", index, anchor="con-1", status=status)
        for index, status in enumerate(statuses, start=1)
    )
    hosting = (
        HostingRow(id="hosting-compute", facet="compute", value="per-request"),
        HostingRow(id="hosting-model", facet="model", value="pool"),
        HostingRow(id="hosting-topology", facet="topology", value="single-unit"),
    )
    return ConstraintsArtifact(
        dispositions=dispositions,
        constraints=constraints,
        decisions=decisions,
        body=_body(
            *(row.id for row in dispositions),
            "con-1",
            *(row.id for row in decisions),
        ),
        hosting=hosting,
    )


def _constraints_text(**kwargs: Any) -> str:
    return render_constraints_artifact(_constraints(**kwargs))


def _components(
    *,
    statuses: Sequence[DecisionStatus] = (DecisionStatus.SETTLED,),
) -> ComponentsArtifact:
    system_patterns = (
        PatternRow(
            id="pattern-audit-before-response",
            name="Audit before response",
            statement="check before answering",
        ),
    )
    component_patterns = (
        PatternRow(
            id="pattern-checkout",
            name="Checkout boundary",
            statement="one consistency boundary per checkout path",
        ),
    )
    components = (
        ComponentRow(
            id="component-checkout",
            name="Checkout",
            entity_ids=("order",),
            pattern_ids=("pattern-audit-before-response", "pattern-checkout"),
            constraint_ids=("con-1",),
            store_ids=("store-checkout",),
        ),
    )
    stores = (
        StoreRow(
            id="store-checkout",
            category="relational",
            sharing="pool",
        ),
    )
    decisions = tuple(
        _decision("components", index, anchor="con-1", status=status)
        for index, status in enumerate(statuses, start=1)
    )
    return ComponentsArtifact(
        system_patterns=system_patterns,
        component_patterns=component_patterns,
        components=components,
        decisions=decisions,
        body=_body(
            "pattern-audit-before-response",
            "pattern-checkout",
            "component-checkout",
            *(row.id for row in decisions),
        ),
        stores=stores,
    )


def _components_text(**kwargs: Any) -> str:
    return render_components_artifact(_components(**kwargs))


# --------------------------------------------------------------------------
# Stage tables, invokers, gate recorders
# --------------------------------------------------------------------------


def _clean_gates(envelope: ArtifactEnvelope) -> list[Violation]:
    return []


def _violation(message: str, row_id: str = "order") -> Violation:
    return Violation(
        kind="test-violation",
        artifact=DOMAIN_FILENAME,
        row_id=row_id,
        message=message,
    )


class _GateRecorder:
    """Canned violation rounds, recording every envelope it judged."""

    def __init__(self, *rounds: Sequence[Violation]) -> None:
        self._rounds: list[Sequence[Violation]] = list(rounds) or [()]
        self.envelopes: list[ArtifactEnvelope] = []

    def __call__(self, envelope: ArtifactEnvelope) -> list[Violation]:
        self.envelopes.append(envelope)
        index = min(len(self.envelopes) - 1, len(self._rounds) - 1)
        return list(self._rounds[index])


class _StubInvoker:
    """Canned ``(rc, stdout)`` replies in call order, recording every prompt.

    A reply may be a bare string (rc 0) or an ``(rc, stdout)`` pair. The last
    reply repeats once the list runs out, so an always-failing stage needs one
    entry rather than one per attempt.
    """

    def __init__(self, *replies: Any) -> None:
        self._replies = [
            reply if isinstance(reply, tuple) else (0, reply) for reply in replies
        ]
        self.prompts: list[str] = []

    def __call__(self, prompt: str) -> tuple[int, str]:
        self.prompts.append(prompt)
        index = min(len(self.prompts) - 1, len(self._replies) - 1)
        return self._replies[index]

    @property
    def calls(self) -> int:
        return len(self.prompts)


def _three_stage_invoker(**kwargs: Any) -> _StubInvoker:
    """Canned conforming replies for stages 1–3."""
    return _StubInvoker(_domain_text(), _constraints_text(), _components_text(**kwargs))


def _four_stage_invoker(**kwargs: Any) -> _StubInvoker:
    """Canned conforming replies for every shipped stage."""
    return _StubInvoker(
        _domain_text(),
        _constraints_text(),
        _components_text(**kwargs),
        _plans_text(**kwargs),
    )


def _never_called(prompt: str) -> tuple[int, str]:
    raise AssertionError("the invoker must not be called")


def _claude_stream_result(text: str) -> str:
    """A minimal claude ``stream-json`` stdout: one terminal ``result`` line
    carrying ``text`` — what the real ``shell_roadmap_invoker`` →
    ``shell.claude_invoke`` path collapses back to ``text`` alone (via
    ``claude_invoke``'s collapse rule)."""
    return json.dumps({"type": "result", "result": text, "usage": {}}) + "\n"


def _fake_popen_factory(responses: Sequence[Any]):
    """A Popen double yielding canned ``SimpleNamespace(stdout=..., stderr=...,
    returncode=...)`` results in order — the real-invoker tests' analog of
    ``_StubInvoker``, driving ``shell.claude_invoke`` (and so
    ``roadmap.shell_roadmap_invoker``) instead of bypassing it. No git
    delegation needed: ``roadmap.py`` never scopes ``spawn_cwd``, so
    ``claude_invoke``'s partial-mutation retry guard is always ``None`` here
    and never shells out to git."""
    it = iter(responses)

    def fake_popen(argv, **kwargs):
        resp = next(it)
        return _FakeProc(
            resp.stdout.splitlines(keepends=True),
            resp.stderr.splitlines(keepends=True),
            resp.returncode,
        )

    return fake_popen


def _stages(
    *,
    domain_gates: Any = _clean_gates,
    constraints_gates: Any = _clean_gates,
    domain_render: Any = render_domain_artifact,
    prompt_names: tuple[str, str] = ("stage-1.md", "stage-2.md"),
    numbers: tuple[int, int] = (1, 2),
) -> tuple[RoadmapStage, ...]:
    return (
        RoadmapStage(
            number=numbers[0],
            name="domain",
            prompt_filename=prompt_names[0],
            artifact_key="domain",
            parse=parse_domain_artifact,
            render=domain_render,
            gates=domain_gates,
        ),
        RoadmapStage(
            number=numbers[1],
            name="constraints",
            prompt_filename=prompt_names[1],
            artifact_key="constraints",
            parse=parse_constraints_artifact,
            render=render_constraints_artifact,
            gates=constraints_gates,
        ),
    )


def test_load_accepted_roadmap_artifacts_wraps_non_utf8_stored_bytes(
    env: _Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A stored member that is not UTF-8 surfaces as the artifact error, not a bare decode error."""
    env.publish_accepted()
    real = roadmap.load_accepted_version(plans_dir=env.plans_dir, slug=SLUG)
    assert real is not None
    corrupt = SimpleNamespace(
        record=real.record, artifact_bytes=(b"\xff", *real.artifact_bytes[1:])
    )
    monkeypatch.setattr(roadmap, "load_accepted_version", lambda **_: corrupt)

    with pytest.raises(RoadmapArtifactError) as excinfo:
        roadmap.load_accepted_roadmap_artifacts(plans_dir=env.plans_dir, slug=SLUG)

    assert isinstance(excinfo.value.__cause__, UnicodeDecodeError)
    assert "--from-stage" not in str(excinfo.value)


@dataclass
class _Env:
    repo_root: Path
    plans_dir: Path
    brief_path: Path
    prompts: Path
    last_run_log: Path | None = None
    expects_exact_run_log: bool = False

    def run(self, **kwargs: Any) -> roadmap.RoadmapResult:
        kwargs.setdefault("invoker", _never_called)
        brief_path = kwargs.pop("brief_path", self.brief_path)
        logs_dir = self.repo_root / ".plan-tool" / "runs" / SLUG
        before = set(logs_dir.glob("*.jsonl"))
        self.last_run_log = None
        self.expects_exact_run_log = True
        try:
            return roadmap.run_roadmap(
                SLUG,
                repo_root=self.repo_root,
                plans_dir=self.plans_dir,
                brief_path=brief_path,
                **kwargs,
            )
        finally:
            created = set(logs_dir.glob("*.jsonl")) - before
            if len(created) == 1:
                self.last_run_log = created.pop()

    @property
    def domain_file(self) -> Path:
        return domain_path(self.plans_dir, SLUG)

    @property
    def constraints_file(self) -> Path:
        return constraints_path(self.plans_dir, SLUG)

    @property
    def components_file(self) -> Path:
        return components_path(self.plans_dir, SLUG)

    @property
    def plans_file(self) -> Path:
        return plans_path(self.plans_dir, SLUG)

    def held_stage_file(self, stage_number: int) -> Path:
        """Where a run keeps a passed stage until the root version publishes."""
        return resume_dir_path(self.repo_root, SLUG) / f"stage-{stage_number}.md"

    def write_domain(self, text: Optional[str] = None) -> Path:
        path = self.domain_file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text if text is not None else _domain_text(), encoding="utf-8")
        return path

    def write_constraints(self, text: Optional[str] = None) -> Path:
        path = self.constraints_file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            text if text is not None else _constraints_text(), encoding="utf-8"
        )
        return path

    def write_components(self, text: Optional[str] = None) -> Path:
        path = self.components_file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            text if text is not None else _components_text(), encoding="utf-8"
        )
        return path

    def write_plans(self, text: Optional[str] = None) -> Path:
        path = self.plans_file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            text if text is not None else _plans_artifact_text(), encoding="utf-8"
        )
        return path

    def publish_accepted(
        self,
        *,
        domain: Optional[str] = None,
        constraints: Optional[str] = None,
        components: Optional[str] = None,
        plans: Optional[str] = None,
    ) -> None:
        """Publish the four artifacts as the accepted root; seed routes read only this."""
        publish_accepted_root(
            self.plans_dir,
            SLUG,
            (
                domain if domain is not None else _domain_text(),
                constraints if constraints is not None else _constraints_text(),
                components if components is not None else _components_text(),
                plans if plans is not None else _plans_artifact_text(),
            ),
        )

    def run_log_events(self) -> list[dict]:
        if self.expects_exact_run_log:
            assert self.last_run_log is not None, "expected exactly one run log from the last run"
            return read_run_events(self.last_run_log)
        logs = list((self.repo_root / ".plan-tool" / "runs" / SLUG).glob("*.jsonl"))
        assert logs, "no run log was written"
        return read_run_events(max(logs, key=lambda path: path.stat().st_mtime_ns))


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _Env:
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "stage-1.md").write_text(
        "Stage 1 for ${slug}\n\nBRIEF:\n${brief}\n", encoding="utf-8"
    )
    (prompts / "stage-2.md").write_text(
        "Stage 2 for ${slug}\n\nBRIEF:\n${brief}\n\nDOMAIN:\n${domain_artifact}\n",
        encoding="utf-8",
    )
    # A stage handed a predecessor reads the shared revision template, so the
    # injected-stage cases need one here too (TESTING.md's roadmap row).
    (prompts / roadmap.REVISION_PROMPT_FILENAME).write_text(
        "REVISION\n\nPRIOR:\n${predecessor_artifact}\n\n"
        "FEEDBACK:\n${active_feedback}\n\nAUTHORING:\n${authoring_prompt}\n",
        encoding="utf-8",
    )
    (prompts / roadmap.STAGE_FEEDBACK_REVISION_PROMPT_FILENAME).write_text(
        "CONTEXT=${context_json}\nSCHEMA=${operation_schema}\n"
        "LIMITS=${max_active_feedback_items}/${max_response_bytes}/"
        "${max_prose_amendment_bytes}/${max_material_operations_per_feedback}\n",
        encoding="utf-8",
    )
    # Every stage prompt is rendered with these two available, whether or not
    # the synthetic template above references them (mirrors REVISION_PROMPT_FILENAME).
    (prompts / roadmap.SMALLEST_PROOF_BOUNDARY_HEADER_FILENAME).write_text(
        "HEADER", encoding="utf-8"
    )
    (prompts / roadmap.SMALLEST_PROOF_BOUNDARY_FOOTER_FILENAME).write_text(
        "FOOTER", encoding="utf-8"
    )
    (prompts / roadmap.WRITING_STYLE_PROMPT_FILENAME).write_text(
        "STYLE", encoding="utf-8"
    )
    monkeypatch.setattr(roadmap, "prompts_dir", lambda: prompts)
    brief_path = tmp_path / "concept.md"
    brief_path.write_text(BRIEF, encoding="utf-8")
    plans_dir = tmp_path / "docs" / "implementation-plans"
    plans_dir.mkdir(parents=True)
    return _Env(
        repo_root=tmp_path,
        plans_dir=plans_dir,
        brief_path=brief_path,
        prompts=prompts,
    )


def test_invalid_carried_decisions_refuse_before_stage_or_source_write(env: _Env) -> None:
    env.brief_path.write_text(
        "## Carried decisions\n\n```json\n{\"confirmed_answers\": [], \"decisions\": [], \"extra\": true}\n```\n",
        encoding="utf-8",
    )
    invoker = _StubInvoker(_domain_text())

    with pytest.raises(roadmap.RoadmapError, match="carried decisions"):
        env.run(stages=_stages()[:1], invoker=invoker)

    assert invoker.prompts == []
    assert not _source_json_path(env.plans_dir).exists()
    assert not env.domain_file.exists()


def test_initial_brief_block_reaches_stage_and_is_held_without_a_source_record(env: _Env) -> None:
    brief = _carried_domain_brief()
    env.brief_path.write_text(brief, encoding="utf-8")
    domain = _domain()
    inherited = replace(
        domain,
        decisions=(replace(domain.decisions[0], source="answer-domain"),),
    )

    result = env.run(
        stages=_stages(domain_gates=run_domain_gates)[:1],
        invoker=_StubInvoker(render_domain_artifact(inherited)),
    )

    assert result.outcome == OUTCOME_COMPLETED
    assert not _source_json_path(env.plans_dir).exists()
    held =(resume_dir_path(env.repo_root, SLUG) / "stage-1.md").read_text()
    assert parse_domain_artifact(held).decisions[0].source == "answer-domain"


def test_changed_brief_refuses_before_carried_block_parse_and_keeps_the_held_stage(
    env: _Env,
) -> None:
    """The changed-brief remedy outranks a carried-block parse error in the new brief."""
    stage = _stages()[:1]
    assert env.run(stages=stage, invoker=_StubInvoker(_domain_text())).outcome == OUTCOME_COMPLETED
    held_file = resume_dir_path(env.repo_root, SLUG) / "stage-1.md"
    held_before = held_file.read_bytes()
    env.brief_path.write_text("## Carried decisions\n\n```json\n{bad}\n```\n", encoding="utf-8")

    with pytest.raises(RoadmapError, match="brief changed"):
        env.run(stages=stage)

    assert held_file.read_bytes() == held_before


@pytest.fixture
def shipped_env(tmp_path: Path) -> _Env:
    """The same environment against the **shipped** prompt templates.

    ``prompts_dir`` is deliberately left unpatched, so every case using this
    fixture renders the real ``plan_tool/prompts/roadmap-domain.md``.
    """
    brief_path = tmp_path / "concept.md"
    brief_path.write_text(BRIEF, encoding="utf-8")
    plans_dir = tmp_path / "docs" / "implementation-plans"
    plans_dir.mkdir(parents=True)
    return _Env(
        repo_root=tmp_path,
        plans_dir=plans_dir,
        brief_path=brief_path,
        prompts=prompts_dir(),
    )


# --------------------------------------------------------------------------
# The shipped stages: their prompt files and the names those restate
# --------------------------------------------------------------------------


def _domain_stage() -> RoadmapStage:
    return roadmap.STAGES[0]


def _constraints_stage() -> RoadmapStage:
    return roadmap.STAGES[1]


def _components_stage() -> RoadmapStage:
    return roadmap.STAGES[2]


def _plans_stage(*, gates: Any = _clean_gates) -> RoadmapStage:
    stage = roadmap.STAGES[3]
    if gates is _clean_gates:
        return stage
    return replace(stage, gates=gates)


def _prompt_text(stage: RoadmapStage) -> str:
    return (prompts_dir() / stage.prompt_filename).read_text(encoding="utf-8")


def _domain_prompt_text() -> str:
    return _prompt_text(_domain_stage())


def _constraints_prompt_text() -> str:
    return _prompt_text(_constraints_stage())


def _components_prompt_text() -> str:
    return _prompt_text(_components_stage())


def _plans_prompt_text() -> str:
    return _prompt_text(_plans_stage())


def _allowed_variables(stage: RoadmapStage) -> set[str]:
    """The variable names ``_render_stage_prompt`` supplies to ``stage``."""
    return {
        "slug",
        "brief",
        "smallest_proof_boundary_header",
        "smallest_proof_boundary_footer",
        "writing_style",
        "inherited_decisions",
    } | {
        f"{below.artifact_key}_artifact"
        for below in roadmap.STAGES
        if below.number < stage.number
    }


def _placeholders(text: str) -> set[str]:
    """Every ``$name`` / ``${name}`` a ``Template`` would try to substitute."""
    return {
        match.group("named") or match.group("braced")
        for match in Template.pattern.finditer(text)
        if match.group("named") or match.group("braced")
    }


@pytest.mark.parametrize("stage", roadmap.STAGES, ids=lambda s: s.name)
def test_every_authoring_stage_includes_the_shared_writing_style(
    stage: RoadmapStage,
) -> None:
    """All four stages read one writing-style fragment, so a reviewer gets the
    same plain-words rules at every stage; the fragment is not copied per stage."""
    assert "${writing_style}" in _prompt_text(stage)
    fragment = (prompts_dir() / roadmap.WRITING_STYLE_PROMPT_FILENAME).read_text(
        encoding="utf-8"
    )
    assert fragment.strip()


def test_rendered_stage_prompt_carries_the_shared_writing_style(
    shipped_env: _Env,
) -> None:
    invoker = _StubInvoker(_domain_text())

    shipped_env.run(stages=roadmap.STAGES[:1], invoker=invoker)

    assert "${writing_style}" not in invoker.prompts[0]
    fragment = (prompts_dir() / roadmap.WRITING_STYLE_PROMPT_FILENAME).read_text(
        encoding="utf-8"
    )
    assert fragment.strip() in invoker.prompts[0]


def test_carried_decision_prompt_context_is_scoped_to_its_owning_artifact() -> None:
    carried = CarriedDecisions(
        decisions=tuple(
            CarriedDecision(
                id=f"inherited-{stage.artifact_key}",
                owner=stage.artifact_key,
                anchor="anchor-1",
                chosen_option=f"option-{stage.artifact_key}",
                source="answer-1",
            )
            for stage in roadmap.STAGES
        )
    )
    brief = "Brief text\n\n## Carried decisions\n\n```json\nsecret-source-block\n```\n"

    for stage in roadmap.STAGES:
        prompt = roadmap._render_stage_prompt(
            stage,
            slug=SLUG,
            brief=brief,
            upstream=(),
            carried_decisions=carried,
        )
        assert f"inherited-{stage.artifact_key}" in prompt
        assert "secret-source-block" not in prompt
        for other in roadmap.STAGES:
            if other != stage:
                assert f"inherited-{other.artifact_key}" not in prompt


@pytest.mark.parametrize("stage", roadmap.STAGES, ids=lambda s: s.name)
def test_every_stage_prompt_renders_the_style_fragment_with_no_placeholder_left(
    stage: RoadmapStage,
) -> None:
    """Dropping ``writing_style`` from the variable map would leave a literal
    ``${writing_style}`` in the model's prompt (``safe_substitute`` ignores it)."""
    prompt = roadmap._render_stage_prompt(
        stage, slug=SLUG, brief="Brief\n", upstream=(), carried_decisions=None
    )
    fragment = (prompts_dir() / roadmap.WRITING_STYLE_PROMPT_FILENAME).read_text(
        encoding="utf-8"
    )
    assert "${writing_style}" not in prompt
    assert fragment.strip() in prompt


def test_missing_style_fragment_fails_the_stage_before_any_model_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A stage that cannot load its shared style block must not run unstyled."""
    shipped = prompts_dir()
    broken = tmp_path / "prompts"
    broken.mkdir()
    for source in shipped.iterdir():
        if source.name != roadmap.WRITING_STYLE_PROMPT_FILENAME:
            (broken / source.name).write_text(
                source.read_text(encoding="utf-8"), encoding="utf-8"
            )
    monkeypatch.setattr(roadmap, "prompts_dir", lambda: broken)

    with pytest.raises(roadmap.RoadmapError, match="writing-style"):
        roadmap._render_stage_prompt(
            roadmap.STAGES[0], slug=SLUG, brief="Brief\n", upstream=(), carried_decisions=None
        )


def _flattened(text: str) -> str:
    """``text`` lowercased with its line wrapping collapsed to single spaces.

    Every phrase pinned below is prose in a hard-wrapped template, so a rewrap
    that changes no words must not redden a check.
    """
    return " ".join(text.lower().split())


_FENCED_BLOCK = re.compile(r"^```[^\n]*\n(.*?)^```", re.DOTALL | re.MULTILINE)


def _prompt_example(prompt_text: str) -> str:
    """The skeleton artifact embedded in a stage prompt.

    Identified by content — the one fenced block opening on a frontmatter
    fence — so the blocks holding the brief and the upstream artifact never
    match.
    """
    blocks = [
        block
        for block in _FENCED_BLOCK.findall(prompt_text)
        if block.startswith("---\n")
    ]
    assert len(blocks) == 1, f"expected one example artifact, found {len(blocks)}"
    return blocks[0]


def _revision_prompt_text() -> str:
    return (prompts_dir() / roadmap.REVISION_PROMPT_FILENAME).read_text(
        encoding="utf-8"
    )


def _revision_example(prompt_text: Optional[str] = None) -> str:
    """The review-collections fragment embedded in the revision prompt.

    Identified by content — the one fenced block opening on the ``feedback:``
    key. ``_prompt_example`` cannot serve: the fragment is not a whole artifact
    and so does not open on a frontmatter fence.
    """
    text = _revision_prompt_text() if prompt_text is None else prompt_text
    blocks = [
        block
        for block in _FENCED_BLOCK.findall(text)
        if block.startswith("feedback:\n")
    ]
    assert len(blocks) == 1, f"expected one review-row example, found {len(blocks)}"
    return blocks[0]


def _row_key_names(row_keys: Sequence[str], row_types: Sequence[type]) -> list[str]:
    """Every frontmatter name one artifact's contract declares."""
    names = set(row_keys)
    for row_type in row_types:
        names.update(field.name for field in fields(row_type))
    return sorted(names)


_INVENTORY_HEADING = "## The frontmatter inventory"


def _inventory_section(text: str) -> str:
    """The prompt's frontmatter-inventory section, heading to next H2.

    Scoped rather than whole-file, and matched as a whole token rather than a
    substring, because the loose form was a test that could not fail: the
    embedded YAML skeleton restates every key, and `name`, `id`, `option` and
    `anchor` all occur in ordinary prose — so 10 of 15 keys stayed green with
    this whole section deleted, and a rename to `anchor_id` passed because
    `anchor` is its prefix.
    """
    start = text.index(_INVENTORY_HEADING) + len(_INVENTORY_HEADING)
    rest = text[start:]
    end = rest.find("\n## ")
    return rest if end == -1 else rest[:end]


def _names_key(section: str, key: str) -> bool:
    """Whether ``section`` names ``key`` bounded on both sides."""
    return (
        re.search(rf"(?<![0-9A-Za-z_]){re.escape(key)}(?![0-9A-Za-z_])", section)
        is not None
    )


def _required_domain_row_keys() -> list[str]:
    return _row_key_names(
        DOMAIN_ROW_KEYS,
        (EntityRow, BusinessRuleRow, WorkflowRow, DecisionRow, RejectedAlternative),
    )


def _required_constraints_row_keys() -> list[str]:
    return _row_key_names(
        CONSTRAINTS_ROW_KEYS,
        (
            HostingRow,
            StackRow,
            AttributeDispositionRow,
            ConstraintRow,
            DecisionRow,
            RejectedAlternative,
        ),
    )


def _required_components_row_keys() -> list[str]:
    return _row_key_names(
        COMPONENTS_ROW_KEYS,
        (PatternRow, StoreRow, ComponentRow, DecisionRow, RejectedAlternative),
    )


def _required_plans_row_keys() -> list[str]:
    return _row_key_names(
        PLANS_ROW_KEYS,
        (PlanRow, OrderingEntry, AssumptionRow, DecisionRow, RejectedAlternative),
    )


# The phrase(s) each gate's rule is stated under in its stage's prompt. Keyed by
# gate rather than listed flat: a gate joining a shipped gate set with no entry
# here reddens the parametrized case below instead of costing retry budget at
# run time. Two gates appear in both sets and are stated per stage, so the map
# is per stage too.
_GATE_PROMPT_SUBJECTS: dict[str, tuple[str, ...]] = {
    "check_artifact_non_empty": ("at least one entity and at least one workflow",),
    "check_duplicate_row_ids": ("unique across all four collections",),
    "check_entity_references": (
        "every workflow and every business rule",
        "entity_ids",
    ),
    "check_entity_fields": (
        "every entity lists at least one field",
        "unique within an entity",
        "exactly the `reference` fields",
    ),
    "check_decision_records": (
        "rejected alternative",
        "rationale",
        "anchor",
    ),
    "check_inherited_decisions": ("reproduce every supplied row exactly", "do not invent deliberation"),
    "check_inventory_has_prose": ("appears in the prose body",),
}

_CONSTRAINTS_GATE_PROMPT_SUBJECTS: dict[str, tuple[str, ...]] = {
    "check_artifact_non_empty": (
        "at least one constraint row",
        "dispositions alone are not a constraints artifact",
    ),
    "check_duplicate_row_ids": ("unique across all five collections",),
    "check_stack_totality": (
        "exactly one stack row",
        "never as an invented choice",
    ),
    "check_hosting_totality": (
        "exactly one hosting row",
        "fixed facet",
    ),
    "check_hosting_value_membership": ("concrete values for its facet",),
    "check_hosting_topology_coherence": (
        "`compute: mixed` and `model: bridge`",
        "topology: multi-unit",
    ),
    "check_attribute_totality": (
        "exactly one disposition",
        "not-load-bearing",
    ),
    "check_constraint_anchors": ("anchors to at least one id",),
    "check_decision_records": (
        "rejected alternative",
        "rationale",
        "anchor",
    ),
    "check_inherited_decisions": ("reproduce every supplied row exactly", "do not invent deliberation"),
    "check_inventory_has_prose": ("appears in the prose body",),
}

_COMPONENTS_GATE_PROMPT_SUBJECTS: dict[str, tuple[str, ...]] = {
    "check_artifact_non_empty": (
        "declare at least one component row",
        "pattern ids it applies",
    ),
    "check_duplicate_row_ids": (
        "unique across every artifact in the envelope",
        "`02-constraints.md`, and this file",
    ),
    "check_component_entity_references": (
        "every component names at least one entity id",
        "from `01-domain.md`",
    ),
    "check_entity_component_coverage": (
        "every domain entity is owned by at least one component",
        "appears on no component",
    ),
    "check_component_pattern_references": (
        "both pattern collections are non-empty",
        "every component names at least one pattern id",
    ),
    "check_component_constraint_references": (
        "constraint_ids` entry names a constraint row",
        "`02-constraints.md` defines",
    ),
    "check_prioritized_constraint_discharge": (
        "prioritized attribute is cited",
        "traded-away",
        "component's `constraint_ids`",
    ),
    "check_store_definitions": (
        "every component names at least one defined store",
        "in-process",
    ),
    "check_store_coverage": ("each store definition is used",),
    "check_store_value_membership": (
        "every store uses a concrete category and sharing model",
        "key-value",
        "there is no undecided value",
    ),
    "check_decision_records": (
        "rejected alternative",
        "rationale",
        "anchor",
    ),
    "check_inherited_decisions": ("reproduce every supplied row exactly", "do not invent deliberation"),
    "check_inventory_has_prose": ("appears in the prose body",),
}

_PLANS_GATE_PROMPT_SUBJECTS: dict[str, tuple[str, ...]] = {
    "check_artifact_non_empty": (
        "name at least one plan",
        "draft seed path destination it declares",
    ),
    "check_duplicate_row_ids": ("unique across every artifact in the envelope",),
    "check_plan_review_context": ("non-blank `intent`", "`non_goals` entry"),
    "check_plan_component_references": (
        "cross-cutting",
        "03-components.md",
        "component ids it covers",
    ),
    "check_component_plan_coverage": (
        "every component id in `03-components.md`",
        "appears on at least one plan",
    ),
    "check_draft_seed_bundle_alignment": (
        "draft_seed_path",
        "unique basename",
    ),
    "check_plan_ordering_totality": (
        "create-compatible slug",
        "ordering",
        "depends_on",
    ),
    "check_assumption_plan_references": ("consuming_plan_ids",),
    "check_decision_records": (
        "rejected alternative",
        "rationale",
        "anchor",
    ),
    "check_inherited_decisions": ("reproduce every supplied row exactly", "do not invent deliberation"),
    "check_inventory_has_prose": ("appears in the prose body",),
}


def _gate_rule_source(
    gate_name: str,
    *,
    authoring_subjects: dict[str, tuple[str, ...]],
    authoring_text: str,
) -> tuple[tuple[str, ...], str]:
    """The first-run prompt phrases for one first-run gate, if it has any."""
    subjects = authoring_subjects.get(gate_name)
    return (() if subjects is None else subjects), authoring_text


class TestShippedStageTable:
    def test_stage_table_ships_four_stages(self) -> None:
        assert len(roadmap.STAGES) == 4
        assert [stage.number for stage in roadmap.STAGES] == [1, 2, 3, 4]
        assert [stage.name for stage in roadmap.STAGES] == [
            "domain",
            "constraints",
            "components",
            "plans",
        ]
        assert [stage.artifact_key for stage in roadmap.STAGES] == [
            "domain",
            "constraints",
            "components",
            "plans",
        ]

    def test_shipped_table_run_publishes_all_four_artifacts_into_the_version_store(
        self, shipped_env: _Env
    ) -> None:
        result = shipped_env.run(
            stages=roadmap.STAGES,
            invoker=_four_stage_invoker(),
        )

        accepted = load_accepted_version(plans_dir=shipped_env.plans_dir, slug=SLUG)
        assert accepted is not None
        assert result.outcome == OUTCOME_COMPLETED
        assert result.stages_run == (1, 2, 3, 4)
        assert result.written_stages == (1, 2, 3, 4)
        assert [path.name for path in result.artifacts] == [
            DOMAIN_FILENAME,
            CONSTRAINTS_FILENAME,
            COMPONENTS_FILENAME,
            PLANS_FILENAME,
        ]
        assert all(
            path.parent.name == accepted.record.version_id and path.is_file()
            for path in result.artifacts
        )
        assert not draft_seeds_dir(shipped_env.plans_dir, SLUG).exists()

    def test_plans_stage_row_reuses_landed_path_parser_renderer_and_gates(
        self,
    ) -> None:
        stage = _plans_stage()

        assert stage.parse is parse_plans_artifact
        assert stage.render is render_plans_artifact
        assert stage.gates is run_plans_gates

    def test_partial_stage_table_completes_holding_its_stages_and_publishes_no_version(
        self, shipped_env: _Env
    ) -> None:
        """Deliberate: only the full version inventory forms a root version; an
        injected partial table is a programmatic seam, never the CLI."""
        result = shipped_env.run(
            stages=roadmap.STAGES[:1], invoker=_StubInvoker(_domain_text())
        )

        assert result.outcome == OUTCOME_COMPLETED
        assert result.artifacts == ()
        assert not shipped_env.domain_file.exists()
        assert not accepted_head_path(shipped_env.plans_dir, SLUG).exists()
        assert (resume_dir_path(shipped_env.repo_root, SLUG) / "stage-1.md").is_file()

    def test_domain_stage_row_reuses_step_ones_path_helper_and_parser(self) -> None:
        stage = _domain_stage()

        assert stage.parse is parse_domain_artifact
        assert stage.render is render_domain_artifact

    def test_domain_stage_row_carries_the_landed_domain_gate_set(self) -> None:
        assert _domain_stage().gates is run_domain_gates

    def test_constraints_stage_row_reuses_step_ones_path_helper_and_parser(
        self,
    ) -> None:
        stage = _constraints_stage()

        assert stage.parse is parse_constraints_artifact
        assert stage.render is render_constraints_artifact

    def test_constraints_stage_row_carries_the_landed_constraints_gate_set(
        self,
    ) -> None:
        assert _constraints_stage().gates is run_constraints_gates

    def test_components_stage_row_reuses_step_ones_path_helper_and_parser(
        self,
    ) -> None:
        stage = _components_stage()

        assert stage.parse is parse_components_artifact
        assert stage.render is render_components_artifact

    def test_components_stage_row_carries_the_landed_components_gate_set(
        self,
    ) -> None:
        assert _components_stage().gates is run_components_gates


class TestDomainPromptTemplate:
    def test_domain_prompt_template_ships_under_prompts_dir(self) -> None:
        assert (prompts_dir() / _domain_stage().prompt_filename).is_file()

    def test_domain_prompt_placeholders_are_a_subset_of_the_variable_map(
        self,
    ) -> None:
        stage = _domain_stage()

        assert _placeholders(_domain_prompt_text()) <= _allowed_variables(stage)

    def test_domain_prompt_renders_with_no_unresolved_placeholder(
        self, shipped_env: _Env
    ) -> None:
        invoker = _StubInvoker(_domain_text())

        shipped_env.run(stages=roadmap.STAGES[:1], invoker=invoker)

        assert "${" not in invoker.prompts[0]
        assert _placeholders(invoker.prompts[0]) == set()

    def test_brief_text_reaches_the_domain_prompt(self, shipped_env: _Env) -> None:
        shipped_env.brief_path.write_text("MARKER-7Q the concept\n", encoding="utf-8")
        invoker = _StubInvoker(_domain_text())

        shipped_env.run(stages=roadmap.STAGES[:1], invoker=invoker)

        assert "MARKER-7Q" in invoker.prompts[0]

    @pytest.mark.parametrize("key", _required_domain_row_keys())
    def test_domain_prompt_names_every_required_row_key(self, key: str) -> None:
        section = _inventory_section(_domain_prompt_text())

        assert _names_key(section, key), (
            f"roadmap-domain.md's {_INVENTORY_HEADING} never names '{key}' as a "
            f"whole token — a stage told the wrong key spends every attempt "
            f"failing to parse"
        )

    def test_domain_prompt_names_both_decision_status_values(self) -> None:
        text = _domain_prompt_text()

        assert all(member.value in text for member in DecisionStatus)

    @pytest.mark.parametrize("gate", DOMAIN_GATES, ids=lambda gate: gate.__name__)
    def test_domain_prompt_states_every_domain_gate_rule(self, gate: Any) -> None:
        subjects, source = _gate_rule_source(
            gate.__name__,
            authoring_subjects=_GATE_PROMPT_SUBJECTS,
            authoring_text=_domain_prompt_text(),
        )
        if not subjects:
            return

        text = _flattened(source)
        for subject in subjects:
            assert subject in text


class TestDomainPromptExample:
    def test_prompt_example_parses_through_the_domain_parser(self) -> None:
        artifact = parse_domain_artifact(_prompt_example(_domain_prompt_text()))

        assert artifact.entities
        assert artifact.workflows
        assert artifact.decisions

    def test_prompt_example_clears_the_domain_gate_set(self) -> None:
        artifact = parse_domain_artifact(_prompt_example(_domain_prompt_text()))

        assert run_domain_gates(ArtifactEnvelope(domain=artifact)) == []


# --------------------------------------------------------------------------
# The shipped constraints stage: its prompt file and its embedded example
# --------------------------------------------------------------------------


class TestConstraintsPromptTemplate:
    def test_constraints_prompt_template_ships_under_prompts_dir(self) -> None:
        assert (prompts_dir() / _constraints_stage().prompt_filename).is_file()

    def test_constraints_prompt_placeholders_are_a_subset_of_the_variable_map(
        self,
    ) -> None:
        stage = _constraints_stage()

        assert _placeholders(_constraints_prompt_text()) <= _allowed_variables(stage)

    def test_constraints_prompt_renders_with_no_unresolved_placeholder(
        self, shipped_env: _Env
    ) -> None:
        invoker = _StubInvoker(_domain_text(), _constraints_text(), _components_text())

        shipped_env.run(stages=roadmap.STAGES[:3], invoker=invoker)

        assert "${" not in invoker.prompts[1]
        assert _placeholders(invoker.prompts[1]) == set()

    @pytest.mark.parametrize("attribute", QUALITY_ATTRIBUTES)
    def test_constraints_prompt_names_every_quality_attribute(
        self, attribute: str
    ) -> None:
        assert attribute in _constraints_prompt_text()

    def test_constraints_prompt_names_every_disposition_value(self) -> None:
        text = _constraints_prompt_text()

        assert all(member.value in text for member in ConstraintDisposition)

    def test_constraints_prompt_names_every_hosting_facet_and_value(self) -> None:
        text = _constraints_prompt_text()

        assert all(facet in text for facet in HOSTING_FACETS)
        assert all(
            value in text
            for values in HOSTING_FACET_VALUES.values()
            for value in values
        )

    @pytest.mark.parametrize("key", _required_constraints_row_keys())
    def test_constraints_prompt_names_every_required_row_key(self, key: str) -> None:
        section = _inventory_section(_constraints_prompt_text())

        assert _names_key(section, key), (
            f"roadmap-constraints.md's {_INVENTORY_HEADING} never names '{key}' "
            f"as a whole token — a stage told the wrong key spends every attempt "
            f"failing to parse"
        )

    def test_constraints_prompt_names_both_decision_status_values(self) -> None:
        text = _constraints_prompt_text()

        assert all(member.value in text for member in DecisionStatus)

    @pytest.mark.parametrize("gate", CONSTRAINTS_GATES, ids=lambda gate: gate.__name__)
    def test_constraints_prompt_states_every_constraints_gate_rule(
        self, gate: Any
    ) -> None:
        subjects, source = _gate_rule_source(
            gate.__name__,
            authoring_subjects=_CONSTRAINTS_GATE_PROMPT_SUBJECTS,
            authoring_text=_constraints_prompt_text(),
        )
        if not subjects:
            return

        text = _flattened(source)
        for subject in subjects:
            assert subject in text

    def test_constraints_prompt_forbids_constraining_a_not_load_bearing_attribute(
        self,
    ) -> None:
        text = _flattened(_constraints_prompt_text())

        assert "never be one this artifact disposes `not-load-bearing`" in text

    @pytest.mark.parametrize("concern", STACK_CONCERNS)
    def test_constraints_prompt_names_every_stack_concern(self, concern: str) -> None:
        assert _names_key(_stack_section(_constraints_prompt_text()), concern)

    def test_constraints_prompt_tells_the_model_to_record_open_when_the_brief_is_undecided(
        self,
    ) -> None:
        text = _flattened(_stack_section(_constraints_prompt_text()))

        assert "`open`" in text
        assert "when the brief leaves that concern undecided" in text
        assert "never invent a vendor, product, or version the brief does not name" in text

    def test_constraints_prompt_still_forbids_inventing_a_hosting_vendor(self) -> None:
        """Deliberate carve-out: stack rows may be `open`, hosting rows may not.
        Widening the `open` allowance into the hosting block must go red here."""
        text = _flattened(_constraints_prompt_text())

        assert (
            "do not invent a vendor, product detail, a deployment unit, or a "
            "pending decision to fill this block" in text
        )
        assert "there is no undecided value" in text

    def test_constraints_prompt_no_longer_counts_four_collections(self) -> None:
        text = _flattened(_constraints_prompt_text())

        assert "four collections" not in text
        assert "all four collections" not in text
        assert "five collections" in text


def _stack_section(text: str) -> str:
    """The prompt's `## Stack` section, heading to the next H2."""
    start = text.index("\n## Stack\n") + len("\n## Stack\n")
    rest = text[start:]
    end = rest.find("\n## ")
    return rest if end == -1 else rest[:end]


def _example_domain() -> DomainArtifact:
    """A domain holding exactly the ids the constraints example anchors to.

    Built here rather than embedded in the prompt: the prompt describes one
    artifact, and the anchor gate still needs an upstream to resolve against.
    """
    return DomainArtifact(
        entities=(
            EntityRow(
                id="entity-1",
                name="Entity",
                fields=(FieldRow(name="id", type=FieldType.TEXT),),
            ),
        ),
        business_rules=(
            BusinessRuleRow(
                id="rule-1", statement="the rule", entity_ids=("entity-1",)
            ),
        ),
        workflows=(WorkflowRow(id="flow-1", name="Flow", entity_ids=("entity-1",)),),
        decisions=(),
        body=_body("entity-1", "rule-1", "flow-1"),
    )


class TestConstraintsPromptExample:
    def test_prompt_example_parses_through_the_constraints_parser(self) -> None:
        artifact = parse_constraints_artifact(
            _prompt_example(_constraints_prompt_text())
        )

        assert artifact.dispositions
        assert artifact.constraints
        assert artifact.decisions

    def test_prompt_example_disposes_every_attribute_exactly_once(self) -> None:
        artifact = parse_constraints_artifact(
            _prompt_example(_constraints_prompt_text())
        )

        disposed = [row.attribute for row in artifact.dispositions]
        assert sorted(disposed) == sorted(QUALITY_ATTRIBUTES)

    def test_prompt_example_clears_the_constraints_gate_set(self) -> None:
        artifact = parse_constraints_artifact(
            _prompt_example(_constraints_prompt_text())
        )

        envelope = ArtifactEnvelope(domain=_example_domain(), constraints=artifact)
        assert run_constraints_gates(envelope) == []

    def test_prompt_example_carries_a_total_stack_with_one_open_row(self) -> None:
        artifact = parse_constraints_artifact(
            _prompt_example(_constraints_prompt_text())
        )

        assert artifact.stack is not None
        assert sorted(row.concern for row in artifact.stack) == sorted(STACK_CONCERNS)
        assert any(row.open for row in artifact.stack)
        assert any(row.choice is not None for row in artifact.stack)

    def test_prompt_example_stack_names_no_vendor(self) -> None:
        """The example teaches by copy, so its stack rows hold only `open` and a
        placeholder: no product-shaped text a model could carry into its answer."""
        artifact = parse_constraints_artifact(
            _prompt_example(_constraints_prompt_text())
        )

        assert artifact.stack is not None
        for row in artifact.stack:
            assert row.open or (
                row.choice is not None
                and row.choice.startswith("<")
                and row.choice.endswith(">")
            )


_INTEGRATION_BRIEF = (
    "A world-builder for tabletop games. No cloud account or specific service "
    "is fixed yet. Data lives in a relational store.\n"
)


def _integration_constraints_text(*, platform_choice: str | None = None) -> str:
    """Canned constraints reply: platform `open` (or a vendor choice), the store
    engine as the brief's generic category, language/runtime `open`."""
    platform = (
        StackRow(id="stack-platform", concern="platform", open=True)
        if platform_choice is None
        else StackRow(id="stack-platform", concern="platform", choice=platform_choice)
    )
    return render_constraints_artifact(
        replace(
            _constraints(),
            stack=(
                platform,
                StackRow(
                    id="stack-store-engine",
                    concern="store-engine",
                    choice="relational store",
                ),
                StackRow(
                    id="stack-language-runtime", concern="language-runtime", open=True
                ),
            ),
        )
    )


class TestIntegrationBriefReplayUnderTheInvokerSeam:
    """Canned replies through the real parser and gates. These show the contract
    is satisfiable and the prompt carries the instruction; they do not measure
    what a real model does with the brief."""

    def test_integration_brief_replay_open_deployment_platform_clears_gates_and_renders(
        self, shipped_env: _Env
    ) -> None:
        shipped_env.brief_path.write_text(_INTEGRATION_BRIEF, encoding="utf-8")
        invoker = _StubInvoker(_domain_text(), _integration_constraints_text())

        result = shipped_env.run(stages=roadmap.STAGES[:2], invoker=invoker)

        assert result.outcome == OUTCOME_COMPLETED
        assert result.violations == ()
        written = load_constraints_artifact(shipped_env.held_stage_file(2))
        assert written.stack is not None
        by_concern = {row.concern: row for row in written.stack}
        assert by_concern["platform"].open is True
        assert by_concern["platform"].choice is None
        assert by_concern["store-engine"].choice == "relational store"

    def test_integration_brief_replay_prompt_reaches_the_model_with_the_open_instruction(
        self, shipped_env: _Env
    ) -> None:
        shipped_env.brief_path.write_text(_INTEGRATION_BRIEF, encoding="utf-8")
        invoker = _StubInvoker(_domain_text(), _integration_constraints_text())

        shipped_env.run(stages=roadmap.STAGES[:2], invoker=invoker)

        prompt = _flattened(invoker.prompts[1])
        assert "no cloud account or specific service is fixed yet" in prompt
        assert "when the brief leaves that concern undecided" in prompt
        assert "never invent a vendor, product, or version the brief does not name" in prompt

    def test_integration_brief_replay_invented_vendor_is_not_a_gate_failure(
        self, shipped_env: _Env
    ) -> None:
        """Deliberate: the invented-vendor ban is an instruction to the model,
        not a check. No gate judges a stack choice's quality, so a vendor choice
        clears. Do not add a vendor gate."""
        shipped_env.brief_path.write_text(_INTEGRATION_BRIEF, encoding="utf-8")
        invoker = _StubInvoker(
            _domain_text(), _integration_constraints_text(platform_choice="SomeVendor Cloud")
        )

        result = shipped_env.run(stages=roadmap.STAGES[:2], invoker=invoker)

        assert result.outcome == OUTCOME_COMPLETED
        assert result.violations == ()


# --------------------------------------------------------------------------
# The shipped components stage: its prompt file and its embedded example
# --------------------------------------------------------------------------


class TestComponentsPromptTemplate:
    def test_components_prompt_template_ships_under_prompts_dir(self) -> None:
        assert (prompts_dir() / _components_stage().prompt_filename).is_file()

    def test_components_prompt_placeholders_are_a_subset_of_the_variable_map(
        self,
    ) -> None:
        stage = _components_stage()

        assert _placeholders(_components_prompt_text()) <= _allowed_variables(stage)

    def test_components_prompt_renders_with_no_unresolved_placeholder(
        self, shipped_env: _Env
    ) -> None:
        invoker = _three_stage_invoker()

        shipped_env.run(stages=roadmap.STAGES[:3], invoker=invoker)

        assert "${" not in invoker.prompts[2]
        assert _placeholders(invoker.prompts[2]) == set()

    def test_brief_and_upstream_artifacts_reach_the_components_prompt(
        self, shipped_env: _Env
    ) -> None:
        shipped_env.brief_path.write_text(
            "MARKER-BRIEF the concept\n", encoding="utf-8"
        )
        invoker = _StubInvoker(
            _domain_text(entity_ids=("marker-entity",)),
            _constraints_text(anchor="marker-entity"),
            _components_text(),
        )

        shipped_env.run(stages=roadmap.STAGES[:3], invoker=invoker)

        prompt = invoker.prompts[2]
        assert "MARKER-BRIEF" in prompt
        assert "marker-entity" in prompt
        assert "con-1" in prompt

    @pytest.mark.parametrize("key", _required_components_row_keys())
    def test_components_prompt_names_every_required_row_key(self, key: str) -> None:
        section = _inventory_section(_components_prompt_text())

        assert _names_key(section, key), (
            f"roadmap-components.md's {_INVENTORY_HEADING} never names '{key}' "
            f"as a whole token — a stage told the wrong key spends every attempt "
            f"failing to parse"
        )

    def test_components_prompt_names_both_decision_status_values(self) -> None:
        text = _components_prompt_text()

        assert all(member.value in text for member in DecisionStatus)

    @pytest.mark.parametrize("gate", COMPONENTS_GATES, ids=lambda gate: gate.__name__)
    def test_components_prompt_states_every_components_gate_rule(
        self, gate: Any
    ) -> None:
        subjects, source = _gate_rule_source(
            gate.__name__,
            authoring_subjects=_COMPONENTS_GATE_PROMPT_SUBJECTS,
            authoring_text=_components_prompt_text(),
        )
        if not subjects:
            return

        text = _flattened(source)
        for subject in subjects:
            assert subject in text

    def test_components_prompt_cites_no_repo_document(self) -> None:
        text = _components_prompt_text()

        assert "FORMAT.md" not in text
        assert "ROADMAP_FORMAT.md" not in text

    def test_components_prompt_matches_coverage_and_discharge_contracts(self) -> None:
        """Overview and rule 1 must restate the gates, not invent exclusivity
        or claim patterns discharge constraints."""
        text = _components_prompt_text()

        assert "belongs to at least one component" in text
        assert "each entity belongs to exactly one component" not in text
        assert "pattern ids it applies" in text
        assert "pattern ids that discharge" not in text

    def test_components_prompt_claims_no_exclusive_partition(self) -> None:
        """No gate checks that two components own disjoint entity ids, so the
        prompt may not call the artifact a partition — see
        ``test_two_components_may_own_the_same_entity_id``."""
        text = _components_prompt_text()

        assert "entity partition" not in text.lower()

    def test_components_prompt_sources_entity_ids_from_entities_only(self) -> None:
        """`entity_ids` resolves against ``domain.entities`` alone, so the
        prompt has to say which collection to draw from — naming the rule and
        workflow collections beside it is what buys a rejected attempt."""
        text = _flattened(_components_prompt_text())

        assert "`entity_ids` holds **entity ids only**" in text
        assert "never a business rule id, a workflow id, or a field name" in text


class TestComponentsPromptExample:
    def test_prompt_example_parses_through_the_components_parser(self) -> None:
        artifact = parse_components_artifact(_prompt_example(_components_prompt_text()))

        assert artifact.system_patterns
        assert artifact.component_patterns
        assert artifact.components
        assert artifact.decisions

    def test_prompt_example_clears_the_components_gate_set(self) -> None:
        artifact = parse_components_artifact(_prompt_example(_components_prompt_text()))

        envelope = ArtifactEnvelope(
            domain=_domain(),
            constraints=_constraints(),
            components=artifact,
        )
        assert run_components_gates(envelope) == []


# --------------------------------------------------------------------------
# The shipped plans stage: its prompt file and its embedded example
# --------------------------------------------------------------------------


class TestPlansPromptTemplate:
    def test_plans_prompt_template_ships_under_prompts_dir(self) -> None:
        assert (prompts_dir() / _plans_stage().prompt_filename).is_file()

    def test_plans_prompt_placeholders_are_a_subset_of_the_variable_map(
        self,
    ) -> None:
        stage = _plans_stage()

        assert _placeholders(_plans_prompt_text()) <= _allowed_variables(stage)

    def test_plans_prompt_renders_with_no_unresolved_placeholder(
        self, shipped_env: _Env
    ) -> None:
        invoker = _four_stage_invoker()

        shipped_env.run(stages=roadmap.STAGES, invoker=invoker)

        guidance = _plans_prompt_text().split(
            "## Map complete implementation responsibilities", 1
        )[1].split("## The frontmatter inventory", 1)[0]
        assert guidance in invoker.prompts[3]
        assert "${" not in invoker.prompts[3]
        assert _placeholders(invoker.prompts[3]) == set()

    def test_plans_prompt_assigns_shared_producers_and_consumer_integration(self) -> None:
        text = _flattened(_plans_prompt_text())

        assert "which plan produces each shared capability or contract" in text
        assert "which plans consume it" in text
        assert "which plan connects each consumer to the producer" in text
        assert "existing row descriptions and narrative linked by plan id" in text

    def test_plans_prompt_assigns_business_input_operations_without_inventing_support(self) -> None:
        text = _flattened(_plans_prompt_text())

        assert "an existing producer does not imply it already supports that operation" in text
        assert "keep distinct source identities distinct" in text
        assert "state unresolved source support as an assumption" in text
        assert "rather than inventing a capability or an internal mechanism" in text

    def test_plans_prompt_traces_every_hop_of_a_transition_inside_the_production_bullet(self) -> None:
        text = _flattened(_plans_prompt_text())
        bullet = text.split("**assign shared production and integration.**", 1)[1].split(
            "**order required handoffs.**", 1
        )[0]

        assert "business transition of evidence, content, or an identity" in bullet
        assert "from where it originates to where it is consumed" in bullet
        assert "the operation that produces or corrects it (not only the check that reads it)" in bullet
        assert "what makes the actual output available to its consumer" in bullet
        assert "the integration that receives it" in bullet
        # Ownership is named even when support is unresolved; the bullet's one assumption
        # sentence carries the unresolved part, so a hop is never unowned and never invented.
        assert "name a plan that owns each hop, even when the source leaves its support unresolved" in bullet
        assert "state unresolved source support as an assumption" in bullet

    def test_plans_prompt_sizes_rows_by_responsibility_without_fixed_count(self) -> None:
        text = _flattened(_plans_prompt_text())

        assert "cohesive implementation outcome" in text
        assert "explicit scope boundary, identifiable prerequisites" in text
        assert "verifiable completion result" in text
        assert "split overly broad scopes into bounded plan rows" in text
        assert "splitting steps inside one broad plan is insufficient" in text
        guidance = text.split("## map complete implementation responsibilities", 1)[1].split(
            "## the frontmatter inventory", 1
        )[0]
        for disposition in ("keep", "merge", "split", "cross-cutting"):
            assert f"`{disposition}`" in guidance
        assert "several plans per component are expected where needed" in text
        assert "do not impose a target plan count or directory-based boundaries" in text
        assert "or create a separate plan for every shared concern" in text

    def test_plans_prompt_orders_required_handoffs_and_keeps_unknowns_explicit(self) -> None:
        text = _flattened(_plans_prompt_text())

        assert "use `ordering.depends_on` for prerequisite plans" in text
        assert "what each consumer needs delivered by those plans" in text
        assert "`assumption_targets` as plan references for ordering-level assumptions" in text
        assert "inter-plan unknowns in `assumptions` with their consuming plans" in text
        assert "unknown prerequisite remains explicit; do not invent a settled result" in text

    def test_plans_prompt_preserves_eventual_observed_acceptance_within_source_scope(self) -> None:
        text = _flattened(_plans_prompt_text())

        assert "plan-id-linked narrative" in text
        assert "which plan proves each bounded route works, including consumer integration" in text
        assert "observed runtime or deployment evidence when the source outcome requires it" in text
        assert "drafting-only or benchmark execution restriction does not replace eventual completion evidence with document review" in text
        assert "stay within the smallest proof boundary above" in text
        assert "do not add proof for capabilities outside the requested outcome" in text

    @pytest.mark.parametrize("key", PLANS_ROW_KEYS)
    def test_plans_prompt_names_every_plans_row_key(self, key: str) -> None:
        section = _inventory_section(_plans_prompt_text())

        assert _names_key(section, key), (
            f"roadmap-plans.md's {_INVENTORY_HEADING} never names '{key}' as a "
            f"whole token — a stage told the wrong key spends every attempt "
            f"failing to parse"
        )

    def test_plans_prompt_names_every_plan_disposition_value(self) -> None:
        text = _plans_prompt_text()

        assert all(member.value in text for member in PlanDisposition)

    @pytest.mark.parametrize("gate", PLANS_GATES, ids=lambda gate: gate.__name__)
    def test_plans_prompt_states_every_plans_gate_rule(self, gate: Any) -> None:
        subjects, source = _gate_rule_source(
            gate.__name__,
            authoring_subjects=_PLANS_GATE_PROMPT_SUBJECTS,
            authoring_text=_plans_prompt_text(),
        )
        if not subjects:
            return

        text = _flattened(source)
        for subject in subjects:
            assert subject in text

    def test_plans_prompt_cites_no_repo_document(self) -> None:
        text = _plans_prompt_text()

        assert "FORMAT.md" not in text
        assert "SEED_FORMAT.md" not in text
        assert "ROADMAP_FORMAT.md" not in text

    def test_plans_prompt_forbids_component_ids_as_plan_slugs(self) -> None:
        text = _plans_prompt_text()

        assert "Do not reuse component ids as plan ids" in text

    def test_authoring_prompts_hold_the_proof_and_altitude_boundaries(self) -> None:
        """Every stage embeds the shared proof-boundary section rather than restating it."""
        prompt_texts = (
            _domain_prompt_text(),
            _constraints_prompt_text(),
            _components_prompt_text(),
            _plans_prompt_text(),
        )

        for text in prompt_texts:
            assert "${smallest_proof_boundary_header}" in text
            assert "${smallest_proof_boundary_footer}" in text

        header = (prompts_dir() / roadmap.SMALLEST_PROOF_BOUNDARY_HEADER_FILENAME).read_text(
            encoding="utf-8"
        )
        footer = (prompts_dir() / roadmap.SMALLEST_PROOF_BOUNDARY_FOOTER_FILENAME).read_text(
            encoding="utf-8"
        )
        assert "smallest end-to-end proof" in header
        assert "eventual product capability" in header
        assert "Stay at the roadmap altitude" in footer
        assert "`create` and `detail`" in footer


class TestPlansPromptExample:
    def test_prompt_example_parses_through_the_plans_parser(self) -> None:
        artifact = parse_plans_artifact(_prompt_example(_plans_prompt_text()))

        assert artifact.plans
        assert artifact.ordering
        assert artifact.assumptions

    def test_prompt_example_clears_run_plans_gates(self) -> None:
        artifact = parse_plans_artifact(_prompt_example(_plans_prompt_text()))

        envelope = ArtifactEnvelope(
            domain=_domain(),
            constraints=_constraints(),
            components=_components(),
            plans=artifact,
        )
        assert run_plans_gates(envelope) == []


# --------------------------------------------------------------------------
# The shared revision prompt: wrapping a stage's authoring prompt
# --------------------------------------------------------------------------

_REVISION_RULES_HEADING = "## The revision rules"
_REVISION_ARTIFACT_HEADING = "## The artifact you are revising"
_REVIEW_COLLECTIONS_HEADING = "### The two review collections"


def _rendered_prompt(
    stage: RoadmapStage,
    *,
    predecessor: Any = None,
    brief: str = BRIEF,
    upstream: Sequence[Any] = (),
) -> str:
    """``_render_stage_prompt`` for ``stage``, in whichever mode is selected."""
    return roadmap._render_stage_prompt(
        stage, slug=SLUG, brief=brief, upstream=upstream, predecessor=predecessor
    )


def _predecessor(artifact: Any = None, *, text: Optional[str] = None) -> Any:
    """One artifact as it sits on disk, for the ``predecessor`` argument.

    The stage is derived from the artifact's type, so the one helper serves
    every shipped stage — which is what the shared-template cases need.
    """
    artifact = _domain() if artifact is None else artifact
    if isinstance(artifact, ComponentsArtifact):
        stage = _components_stage()
    elif isinstance(artifact, ConstraintsArtifact):
        stage = _constraints_stage()
    elif isinstance(artifact, PlansArtifact):
        stage = _plans_stage()
    else:
        stage = _domain_stage()
    return roadmap._LoadedArtifact(
        stage=stage,
        path=Path("plans") / SLUG / f"{stage.artifact_key}.md",
        text=stage.render(artifact) if text is None else text,
        artifact=artifact,
    )


def _feedback(
    row_id: str,
    *,
    state: FeedbackState = FeedbackState.OPEN,
    request: str = "say what happens when an order is cancelled",
    target_row_id: Optional[str] = None,
    response: Optional[str] = None,
) -> FeedbackRow:
    target = (
        FeedbackTarget(kind=FeedbackTargetKind.ARTIFACT)
        if target_row_id is None
        else FeedbackTarget(kind=FeedbackTargetKind.ROW, row_id=target_row_id)
    )
    return FeedbackRow(
        id=row_id,
        target=target,
        request=request,
        state=state,
        proposed_response=response,
    )


def _with_feedback(*rows: FeedbackRow) -> DomainArtifact:
    return replace(_domain(), feedback=rows)


def _review_schema_section(text: str) -> str:
    """The revision prompt's review-row schema, heading to the next H3.

    Scoped rather than whole-file for the reason ``_inventory_section`` is: the
    embedded example restates every key, so a whole-file check would stay green
    with the schema prose deleted.
    """
    start = text.index(_REVIEW_COLLECTIONS_HEADING) + len(_REVIEW_COLLECTIONS_HEADING)
    rest = text[start:]
    end = rest.find("\n### ")
    return rest if end == -1 else rest[:end]


def _required_review_row_keys() -> list[str]:
    return _row_key_names(REVIEW_ROW_KEYS, (FeedbackRow, FeedbackTarget, RemovalRecord))


class TestRenderStagePromptReadErrors:
    """An unreadable prompt input surfaces as ``RoadmapEnvironmentalError``,
    not a bare OSError — and specifically that subtype, not the base
    ``RoadmapError`` a genuinely missing template raises, because
    ``cmd_roadmap`` maps the two to different exit codes (1 vs. 2)."""

    @pytest.mark.parametrize("failure", (OSError("permission denied"), UnicodeDecodeError("utf-8", b"\\xff", 0, 1, "invalid start byte")))
    def test_render_stage_prompt_wraps_an_unreadable_template(
        self, monkeypatch: pytest.MonkeyPatch, failure: OSError | UnicodeDecodeError
    ) -> None:
        stage = _domain_stage()
        template_path = prompts_dir() / stage.prompt_filename
        original_read_text = Path.read_text

        def broken_read_text(self: Path, *args: Any, **kwargs: Any) -> str:
            if self == template_path:
                raise failure
            return original_read_text(self, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", broken_read_text)

        with pytest.raises(roadmap.RoadmapEnvironmentalError, match="not readable") as excinfo:
            roadmap._render_stage_prompt(stage, slug=SLUG, brief=BRIEF, upstream=())

        assert isinstance(excinfo.value.__cause__, type(failure))

    @pytest.mark.parametrize("failure", (OSError("permission denied"), UnicodeDecodeError("utf-8", b"\\xff", 0, 1, "invalid start byte")))
    def test_render_stage_feedback_prompt_wraps_an_unreadable_template(
        self, monkeypatch: pytest.MonkeyPatch, failure: OSError | UnicodeDecodeError
    ) -> None:
        template_path = prompts_dir() / roadmap.STAGE_FEEDBACK_REVISION_PROMPT_FILENAME
        original_read_text = Path.read_text

        def broken_read_text(self: Path, *args: Any, **kwargs: Any) -> str:
            if self == template_path:
                raise failure
            return original_read_text(self, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", broken_read_text)
        context = roadmap.build_stage_revision_context(_domain(), artifact_key="domain")

        with pytest.raises(roadmap.RoadmapEnvironmentalError, match="not readable") as excinfo:
            roadmap._render_stage_feedback_prompt(context)

        assert isinstance(excinfo.value.__cause__, type(failure))

    def test_render_stage_prompt_missing_template_stays_base_roadmap_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A missing (not merely unreadable) template is still the base
        ``RoadmapError`` — ``cmd_roadmap`` must keep mapping it to rc=2, the
        pre-flight/bad-argument code, not the environmental subtype's 1."""
        stage = _domain_stage()
        monkeypatch.setattr(Path, "is_file", lambda self: False)

        with pytest.raises(roadmap.RoadmapError) as excinfo:
            roadmap._render_stage_prompt(stage, slug=SLUG, brief=BRIEF, upstream=())

        assert not isinstance(excinfo.value, roadmap.RoadmapEnvironmentalError)

    def test_render_stage_prompt_missing_template_marks_stage_not_started(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A missing template fails before any invoker attempt, so it must
        carry ``roadmap_stage_started = False`` for ``_stage_run_guard`` to
        preserve — otherwise ``cmd_roadmap`` reads a genuinely-missing
        template (rc=2) as a mid-run failure (rc=1)."""
        stage = _domain_stage()
        monkeypatch.setattr(Path, "is_file", lambda self: False)

        with pytest.raises(roadmap.RoadmapError) as excinfo:
            roadmap._render_stage_prompt(stage, slug=SLUG, brief=BRIEF, upstream=())

        assert excinfo.value.roadmap_stage_started is False

    def test_render_stage_feedback_prompt_missing_template_marks_stage_not_started(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Same preflight fact as the authoring prompt's missing-template
        case, for the bounded-feedback prompt's own template checks."""
        monkeypatch.setattr(Path, "is_file", lambda self: False)
        context = roadmap.build_stage_revision_context(_domain(), artifact_key="domain")

        with pytest.raises(roadmap.RoadmapError) as excinfo:
            roadmap._render_stage_feedback_prompt(context)

        assert excinfo.value.roadmap_stage_started is False


class TestRevisionModeSelection:
    """Predecessor presence, and nothing else, selects the revision wrapper."""

    def test_revision_template_ships_under_prompts_dir(self) -> None:
        assert (prompts_dir() / roadmap.REVISION_PROMPT_FILENAME).is_file()

    def test_shared_revision_prompt_keeps_updates_proportional_and_at_altitude(self) -> None:
        text = _revision_prompt_text()

        assert "smallest truthful response" in text
        assert "proportional to the selected reviewer request" in text
        assert "target's recorded role" in text
        assert "declared plan intent" in text
        assert "eventual capability" in text
        assert "selected artifact at its own altitude" in text

    def test_shipped_stage_feedback_prompt_inherits_the_update_judgment(self) -> None:
        artifact = replace(
            _domain(),
            feedback=(
                FeedbackRow(
                    "feedback-order",
                    FeedbackTarget(FeedbackTargetKind.ROW, "order"),
                    "Rename the entity.",
                    FeedbackState.OPEN,
                ),
            ),
        )

        prompt = roadmap._render_stage_feedback_prompt(
            roadmap.build_stage_revision_context(artifact, artifact_key="domain")
        )

        assert "smallest truthful response" in prompt
        assert "target's recorded role" in prompt
        assert "selected artifact at its own altitude" in prompt

    def test_no_predecessor_renders_the_authoring_prompt_unchanged(self) -> None:
        expected = Template(_domain_prompt_text()).safe_substitute(
            slug=SLUG, brief=BRIEF
        )

        assert _rendered_prompt(_domain_stage()) == expected

    def test_first_run_prompt_shows_no_revision_framing(
        self, shipped_env: _Env
    ) -> None:
        invoker = _StubInvoker(_domain_text(), _constraints_text(), _components_text())

        shipped_env.run(stages=roadmap.STAGES[:3], invoker=invoker)

        for prompt in invoker.prompts:
            assert _REVISION_RULES_HEADING not in prompt
            assert _REVISION_ARTIFACT_HEADING not in prompt

    def test_a_predecessor_wraps_the_authoring_prompt_whole(self) -> None:
        authoring = _rendered_prompt(_domain_stage())

        rendered = _rendered_prompt(_domain_stage(), predecessor=_predecessor())

        assert authoring in rendered
        assert _REVISION_RULES_HEADING in rendered

    def test_revision_prompt_carries_the_predecessor_text_verbatim(self) -> None:
        # A hand edit the renderer would drop, so this cannot pass on a
        # re-render of the parsed artifact.
        artifact = _domain()
        on_disk = f"{render_domain_artifact(artifact)}\n<!-- a hand edit -->\n"

        rendered = _rendered_prompt(
            _domain_stage(), predecessor=_predecessor(artifact, text=on_disk)
        )

        assert on_disk in rendered

    def test_revision_rules_follow_the_wrapped_authoring_prompt(self) -> None:
        # The authoring prompt ends with its own skeleton and its own
        # "re-author from scratch" line, so rules placed before it lose to text
        # the model reads later.
        authoring = _rendered_prompt(_domain_stage())

        rendered = _rendered_prompt(_domain_stage(), predecessor=_predecessor())

        wrapped_end = rendered.index(authoring) + len(authoring)
        assert rendered.index(_REVISION_RULES_HEADING) > wrapped_end

    def test_missing_revision_template_raises_naming_the_expected_path(
        self, env: _Env
    ) -> None:
        (env.prompts / roadmap.REVISION_PROMPT_FILENAME).unlink()
        invoker = _StubInvoker(_domain_text())

        with pytest.raises(RoadmapError) as excinfo:
            roadmap._run_stage(
                _stages()[0],
                slug=SLUG,
                brief=BRIEF,
                upstream=(),
                invoker=invoker,
                max_attempts=3,
                run_logger=None,
                phase="stage-1-domain",
                predecessor=_predecessor(),
            )

        assert str(env.prompts / roadmap.REVISION_PROMPT_FILENAME) in str(excinfo.value)
        assert invoker.calls == 0

    def test_both_stages_use_the_one_shared_revision_template(self) -> None:
        shipped = sorted(path.name for path in prompts_dir().glob("roadmap-*.md"))
        assert shipped == [
            "roadmap-components.md",
            "roadmap-constraints.md",
            "roadmap-domain.md",
            "roadmap-feedback-revision.md",
            "roadmap-plans.md",
            roadmap.REVISION_PROMPT_FILENAME,
            "roadmap-seed.md",
            "roadmap-structural-feedback-revision.md",
        ]
        assert not any("revision" in field.name for field in fields(RoadmapStage))

        domain = _rendered_prompt(_domain_stage(), predecessor=_predecessor())
        constraints = _rendered_prompt(
            _constraints_stage(),
            predecessor=_predecessor(_constraints()),
            upstream=(_predecessor(),),
        )

        for rendered in (domain, constraints):
            assert _REVISION_RULES_HEADING in rendered
            assert _REVIEW_COLLECTIONS_HEADING in rendered


class TestActiveFeedbackBlock:
    """Only ``open`` rows travel as active guidance, and they travel whole."""

    def test_only_open_feedback_is_sent_as_active_guidance(self) -> None:
        artifact = _with_feedback(
            _feedback("fb-open"),
            _feedback(
                "fb-answered",
                state=FeedbackState.AWAITING_REVIEW,
                response="split the entity",
            ),
            _feedback("fb-parked", state=FeedbackState.DEFERRED),
        )

        block = roadmap._active_feedback_block(artifact)

        assert "fb-open" in block
        assert "fb-answered" not in block
        assert "fb-parked" not in block

    def test_every_open_feedback_id_appears_in_the_active_block(self) -> None:
        artifact = _with_feedback(
            _feedback("fb-1"), _feedback("fb-2"), _feedback("fb-3")
        )

        rendered = _rendered_prompt(_domain_stage(), predecessor=_predecessor(artifact))

        block = roadmap._active_feedback_block(artifact)
        assert block in rendered
        for row in artifact.feedback:
            assert f"'{row.id}'" in block

    def test_active_block_preserves_artifact_order(self) -> None:
        artifact = _with_feedback(
            _feedback("fb-c"), _feedback("fb-a"), _feedback("fb-b")
        )

        block = roadmap._active_feedback_block(artifact)

        assert block.index("fb-c") < block.index("fb-a") < block.index("fb-b")

    def test_a_request_is_quoted_verbatim(self) -> None:
        request = "Split `order` into Order and OrderLine — WHY is it one row?"

        block = roadmap._active_feedback_block(
            _with_feedback(_feedback("fb-1", request=request))
        )

        assert request in block

    def test_a_multi_line_request_keeps_its_lines(self) -> None:
        request = (
            "Two problems here.\n\n- the entity is too coarse\n- the flow skips payment"
        )

        block = roadmap._active_feedback_block(
            _with_feedback(_feedback("fb-1", request=request))
        )

        assert request in block

    def test_a_long_request_is_never_truncated(self) -> None:
        # The plan's fence: no cap or rejection keyed on a request's length.
        request = " ".join(f"paragraph-{index} of the review." for index in range(500))

        block = roadmap._active_feedback_block(
            _with_feedback(_feedback("fb-1", request=request))
        )

        assert request in block

    def test_a_row_target_names_its_row_id(self) -> None:
        block = roadmap._active_feedback_block(
            _with_feedback(_feedback("fb-1", target_row_id="rule-1"))
        )

        assert "rule-1" in block

    def test_an_artifact_target_is_labelled_with_no_row_id(self) -> None:
        block = roadmap._active_feedback_block(_with_feedback(_feedback("fb-1")))

        assert "the artifact as a whole" in block
        assert "row '" not in block

    def test_no_open_feedback_renders_the_explicit_no_active_feedback_line(
        self,
    ) -> None:
        # Neither state is active guidance, so an artifact carrying only these
        # renders the line rather than a dangling empty heading.
        parked = _with_feedback(
            _feedback("fb-parked", state=FeedbackState.DEFERRED),
            _feedback(
                "fb-answered",
                state=FeedbackState.AWAITING_REVIEW,
                response="split the entity",
            ),
        )

        for artifact in (_domain(), parked):
            assert (
                roadmap._active_feedback_block(artifact) == roadmap._NO_ACTIVE_FEEDBACK
            )
        for row in parked.feedback:
            assert row.id not in roadmap._active_feedback_block(parked)

        rendered = _rendered_prompt(_domain_stage(), predecessor=_predecessor(parked))
        assert roadmap._NO_ACTIVE_FEEDBACK in rendered
        assert "no active feedback" in roadmap._NO_ACTIVE_FEEDBACK.lower()

    def test_deferred_rows_reach_the_model_only_through_the_predecessor_text(
        self,
    ) -> None:
        request = "MARKER-PARKED revisit the refund path next quarter"
        artifact = _with_feedback(
            _feedback("fb-1", state=FeedbackState.DEFERRED, request=request)
        )

        rendered = _rendered_prompt(_domain_stage(), predecessor=_predecessor(artifact))

        assert request in rendered
        assert request not in roadmap._active_feedback_block(artifact)

    def test_a_synthetic_stage_artifact_without_feedback_renders_the_block(
        self,
    ) -> None:
        # The ``getattr`` default: a stage carrying some other artifact type
        # still renders rather than raising.
        assert roadmap._active_feedback_block(object()) == roadmap._NO_ACTIVE_FEEDBACK


class TestRevisionReflectionContract:
    """What the shipped template tells the model to do with the feedback."""

    def test_revision_prompt_requires_a_response_for_every_open_feedback_id(
        self,
    ) -> None:
        text = _flattened(_revision_prompt_text())

        assert "write that row's `proposed_response`" in text
        assert (
            "a row you leave `open` is a request the revision still owes an answer to"
            in text
        )

    def test_all_three_authoring_prompts_carry_the_say_it_aloud_test(self) -> None:
        # "Plain, everyday words" was already in both and did not take; the
        # standard is a test the model can apply, not an adjective.
        for text in (
            _domain_prompt_text(),
            _constraints_prompt_text(),
            _components_prompt_text(),
        ):
            flat = _flattened(text)
            assert "would a person say this to another person" in flat
            assert "if it is not something a person would say, rewrite it" in flat
            # The scope is every line of prose, decisions included.
            assert (
                "rule statements, workflow names, and the `chosen_option` and "
                "`rationale` of every decision" in flat
            )
            # The guard against hearing "be casual" and dropping conditions.
            assert "plain is not vague" in flat
            assert "every condition has to survive the rewrite" in flat
            # Two carves, both added after a live run overreached: the first
            # rewrote every id into a sentence (and cost a gates retry on
            # dangling anchors), the second split rules to shorten them.
            assert "this governs prose, not ids" in flat
            assert "an `id` is an identifier, not a sentence" in flat
            assert "split a sentence, never a rule" in flat
            assert "how many rules there are follows the domain, not the prose" in flat

    def test_the_plain_english_block_does_not_drift_across_authoring_prompts(
        self,
    ) -> None:
        # The block is duplicated by necessity — standalone prompt files
        # with no include — so pin them equal rather than trusting a sweep.
        marker = "**The test: would a person say this"

        def block(text: str, which: str) -> str:
            assert marker in text, f"{which} prompt carries no plain-English block"
            start = text.index(marker)
            return text[start : text.index("## Shape", start)].strip()

        canonical = block(_domain_prompt_text(), "domain")
        assert block(_constraints_prompt_text(), "constraints") == canonical
        assert block(_components_prompt_text(), "components") == canonical

    def test_revision_prompt_glosses_concepts_once_per_row_not_once_per_file(
        self,
    ) -> None:
        # A reviewer reads one row's response on its own, so the gloss resets
        # per row. Nothing pinned this contract before; it shipped from the
        # step-9 readability review untested.
        text = _flattened(_revision_prompt_text())

        assert "say what a thing is the first time you name it" in text
        assert "counted per feedback row, not per file" in text
        assert "each response introduces every concept it names" in text
        assert "even when a sibling response already introduced the same one" in text

    def test_revision_prompt_reserves_settled_for_what_the_reviewer_decided(
        self,
    ) -> None:
        # A settled decision is immutable to a revision, so a model settling
        # its own unprompted choice walls off the reviewer's next correction
        # of it — measured on toollib, where it cost a round trip.
        text = _flattened(_revision_prompt_text())

        assert (
            "settle what the reviewer settled; leave `pending` what you chose" in text
        )
        assert "that call is yours and not yet theirs, so mark it `pending`" in text
        assert "walls off their next correction of it" in text

    def test_revision_prompt_states_carve_b_narrow_on_removals(self) -> None:
        # Settled 2026-08-05: Carve B is narrow — no decision about the
        # removed row itself; a surviving-row gap decision is the positive
        # branch. Broad ("no decision beside a removal") was rejected.
        text = _flattened(_revision_prompt_text())

        assert (
            "do **not** also mint a decision whose subject is that removed id" in text
        )
        assert (
            "decision anchored to a **surviving** row about a gap the removal "
            "opened is the ordinary positive branch" in text
        )

    def test_revision_prompt_bans_words_the_artifact_does_not_define(self) -> None:
        text = _flattened(_revision_prompt_text())

        assert "use no word the artifact does not define" in text

    def test_revision_prompt_forbids_deleting_closing_or_deferring_feedback(
        self,
    ) -> None:
        text = _flattened(_revision_prompt_text())

        assert "never delete, close, or defer a feedback row" in text

    def test_revision_prompt_forbids_altering_an_id_target_or_request(self) -> None:
        text = _flattened(_revision_prompt_text())

        assert (
            "never change a feedback row's `id`, its `target`, or its `request`" in text
        )

    def test_revision_prompt_states_the_one_allowed_state_transition(self) -> None:
        text = _flattened(_revision_prompt_text())

        assert (
            f"the only state move you may make is `{FeedbackState.OPEN.value}` to "
            f"`{FeedbackState.AWAITING_REVIEW.value}`" in text
        )

    def test_revision_prompt_forbids_inventing_a_feedback_row(self) -> None:
        text = _flattened(_revision_prompt_text())

        assert "never invent a feedback row" in text
        assert (
            "never write a `removals` record that no `open` feedback asked for" in text
        )
        assert (
            "never delete or prune a `removals` record the artifact above carries"
            in text
        )

    def test_revision_prompt_requires_a_cited_rationale_bearing_removal(self) -> None:
        text = _flattened(_revision_prompt_text())

        assert (
            "add a `removals` record naming it in `removed_id`, with a non-blank "
            "`rationale` and at least one `open` feedback id in `feedback_ids`" in text
        )
        assert "only an `open` feedback row authorizes a removal" in text

    def test_revision_prompt_pins_a_settled_decision_and_names_the_un_settle_action(
        self,
    ) -> None:
        text = _flattened(_revision_prompt_text())

        assert (
            f"a `decisions` row the artifact above marks "
            f"`{DecisionStatus.SETTLED.value}` keeps its `id`, its `status`, its "
            f"`chosen_option`, and its `anchor`" in text
        )
        # The transitive block, and the one move the model has instead.
        assert (
            f"a design row that a `{DecisionStatus.SETTLED.value}` decision "
            f"anchors to may not be removed either" in text
        )
        assert (
            f"set that decision's `status` to `{DecisionStatus.PENDING.value}` first"
            in text
        )

    def test_revision_prompt_overrides_the_authoring_re_author_instruction(
        self,
    ) -> None:
        re_author = "you re-author the whole artifact from scratch"
        # The sentence is in both authoring prompts, so the override is real.
        assert re_author in _flattened(_domain_prompt_text())
        assert re_author in _flattened(_constraints_prompt_text())

        text = _flattened(_revision_prompt_text())

        assert re_author in text
        assert "you are not authoring from scratch" in text
        assert "your starting point is the artifact above" in text

    def test_revision_prompt_tells_the_model_to_carry_non_active_feedback_unchanged(
        self,
    ) -> None:
        text = _flattened(_revision_prompt_text())

        assert "through unchanged, `proposed_response` included" in text

    def test_revision_prompt_overrides_the_authoring_collection_inventory(
        self,
    ) -> None:
        # Relative to the wrapped inventory, never a number: one template wraps
        # two prompts whose collection counts differ.
        text = _flattened(_revision_prompt_text())

        assert "count from the contract above and add these two" in text
        assert "four collections" not in text
        assert "three collections" not in text

    def test_revision_prompt_overrides_the_authoring_no_questions_rule(self) -> None:
        text = _flattened(_revision_prompt_text())

        assert "the reviewer reads your `proposed_response`" in text
        assert "ask one focused question there" in text
        # The permission covers scope, not only ambiguity about what to change
        # — widened 2026-08-04 after a real run asked a scope question about an
        # otherwise unambiguous request. The cap is what stops it inflating
        # into a question on every request.
        assert "or when it implies a scope you cannot infer" in text
        assert "one question, not a checklist" in text

    def test_revision_prompt_overrides_the_authoring_check_count_and_skeleton(
        self,
    ) -> None:
        text = _flattened(_revision_prompt_text())

        assert "three more run beside them" in text
        assert "the skeleton shows the authoring shape only" in text
        assert "meet all six" not in text

    @pytest.mark.parametrize("key", _required_review_row_keys())
    def test_revision_prompt_names_every_review_row_key(self, key: str) -> None:
        section = _review_schema_section(_revision_prompt_text())

        assert _names_key(section, key), (
            f"roadmap-revision.md's {_REVIEW_COLLECTIONS_HEADING} never names "
            f"'{key}' as a whole token — no repo doc reaches the model, so the "
            f"schema is stated here or nowhere"
        )

    @pytest.mark.parametrize("state", FeedbackState, ids=lambda member: member.value)
    def test_revision_prompt_names_every_feedback_state_value(
        self, state: FeedbackState
    ) -> None:
        assert f"`{state.value}`" in _review_schema_section(_revision_prompt_text())

    @pytest.mark.parametrize(
        "kind", FeedbackTargetKind, ids=lambda member: member.value
    )
    def test_revision_prompt_names_both_feedback_target_kinds(
        self, kind: FeedbackTargetKind
    ) -> None:
        assert f"`{kind.value}`" in _review_schema_section(_revision_prompt_text())

    def test_revision_prompt_cites_no_repo_document(self) -> None:
        # The verb runs inside whatever repo the operator is in, and that repo
        # has no copy of this project's docs.
        for filename in (
            roadmap.REVISION_PROMPT_FILENAME,
            _domain_stage().prompt_filename,
            _constraints_stage().prompt_filename,
            _components_stage().prompt_filename,
        ):
            text = (prompts_dir() / filename).read_text(encoding="utf-8")
            assert "FORMAT.md" not in text
            if filename == roadmap.REVISION_PROMPT_FILENAME:
                assert re.search(r"[0-9A-Za-z_-]+\.md", text) is None


class TestRevisionTemplateMechanics:
    def test_revision_prompt_placeholders_are_a_subset_of_the_revision_variable_map(
        self,
    ) -> None:
        # Equality, not containment: the template names exactly the three
        # values the renderer supplies, and every one of them is used.
        assert _placeholders(_revision_prompt_text()) == set(
            roadmap.REVISION_PROMPT_VARIABLES
        )
        assert len(roadmap.REVISION_PROMPT_VARIABLES) == 3

    def test_revision_prompt_renders_with_no_unresolved_placeholder(self) -> None:
        rendered = _rendered_prompt(_domain_stage(), predecessor=_predecessor())

        assert "${" not in rendered
        assert _placeholders(rendered) == set()

    def test_a_dollar_placeholder_in_the_brief_survives_into_the_revision_prompt(
        self,
    ) -> None:
        # One substitution pass per template, and a substituted value is never
        # rescanned — which is why the authoring prompt is a value, not text
        # concatenated ahead of a second pass.
        rendered = _rendered_prompt(
            _domain_stage(),
            predecessor=_predecessor(),
            brief="Call the roadmap ${slug} in the prose.\n",
        )

        assert "${slug}" in rendered

    def test_revision_template_holds_no_bare_dollar(self) -> None:
        # ``safe_substitute`` leaves an unknown placeholder in place rather than
        # raising, so a typo would ship to the model with nothing red firing.
        assert re.search(r"\$(?!\{)", _revision_prompt_text()) is None


# The domain rows the revision template's example names, so the example can be
# spliced into a real artifact and judged by the real gates.
def _example_base(*, with_removed_row: bool) -> DomainArtifact:
    entities = [
        EntityRow(
            id="row-1",
            name="Row One",
            fields=(FieldRow(name="id", type=FieldType.TEXT),),
        )
    ]
    if with_removed_row:
        entities.append(
            EntityRow(
                id="row-2",
                name="Row Two",
                fields=(FieldRow(name="id", type=FieldType.TEXT),),
            )
        )
    return DomainArtifact(
        entities=tuple(entities),
        business_rules=(),
        workflows=(WorkflowRow(id="row-flow", name="Flow", entity_ids=("row-1",)),),
        decisions=(),
        body=_body(*(row.id for row in entities), "row-flow"),
    )


def _splice_review_rows(artifact_text: str, fragment: str) -> str:
    """Put ``fragment`` into ``artifact_text``'s frontmatter, above its close."""
    lines = artifact_text.splitlines(keepends=True)
    close = next(
        index for index in range(1, len(lines)) if lines[index].rstrip("\n") == "---"
    )
    return "".join(lines[:close]) + fragment + "".join(lines[close:])


def _spliced_revision_example() -> str:
    return _splice_review_rows(
        render_domain_artifact(_example_base(with_removed_row=False)),
        _revision_example(),
    )


def _example_predecessor() -> DomainArtifact:
    """The prior version the example's review rows answer.

    Its feedback is the example's own rows read back: the ``open`` request the
    revision answers, and the ``deferred`` one it carries through untouched.
    """
    answered, carried = parse_domain_artifact(_spliced_revision_example()).feedback
    return replace(
        _example_base(with_removed_row=True),
        feedback=(
            replace(answered, state=FeedbackState.OPEN, proposed_response=None),
            carried,
        ),
    )


class TestRevisionPromptExample:
    def test_revision_example_parses_when_spliced_into_an_artifact(self) -> None:
        artifact = parse_domain_artifact(_spliced_revision_example())

        assert len(artifact.feedback) == 2
        assert len(artifact.removals) == 1

    def test_revision_example_clears_the_gate_set_against_a_matching_predecessor(
        self,
    ) -> None:
        revision = parse_domain_artifact(_spliced_revision_example())

        envelope = ArtifactEnvelope(domain=revision, predecessor=_example_predecessor())
        assert run_domain_gates(envelope) == []

    def test_revision_example_uses_placeholder_ids(self) -> None:
        artifact = parse_domain_artifact(_spliced_revision_example())

        assert [row.id for row in artifact.feedback] == ["fb-1", "fb-2"]
        assert [record.removed_id for record in artifact.removals] == ["row-2"]
        for row in artifact.feedback:
            assert row.request.startswith("<") and row.request.endswith(">")


class TestAFirstRunRejectsModelAuthoredReviewRows:
    """A first run has no reviewer, so any review row in a reply is the model's."""

    def test_a_predecessor_free_stage_rejects_any_model_authored_feedback_row(
        self, env: _Env
    ) -> None:
        # No gate can see this case: every feedback rule is predecessor-derived,
        # so a fresh authoring pass could otherwise mint a row the next run
        # cannot tell from the reviewer's own.
        invoker = _StubInvoker(
            render_domain_artifact(_with_feedback(_feedback("fb-1")))
        )

        result = env.run(stages=_stages()[:1], invoker=invoker, max_stage_attempts=1)

        assert result.failure_kind == FAILURE_AUTHORED_REVIEW_ROWS
        assert not env.domain_file.exists()

    def test_the_retry_correction_names_the_dropped_entries_in_first_run_terms(
        self, env: _Env
    ) -> None:
        """A first run has no revision and no reviewer row; the correction must not invoke either."""
        invoker = _StubInvoker(
            render_domain_artifact(_with_feedback(_feedback("fb-1"))), _domain_text()
        )

        env.run(stages=_stages()[:1], invoker=invoker, max_stage_attempts=2)

        retry_prompt = invoker.prompts[1]
        assert "feedback row 'fb-1'" in retry_prompt
        assert "drop the 'feedback' and 'removals' entries" in retry_prompt
        assert "a first run has no feedback or removals" in retry_prompt
        assert "revision" not in retry_prompt.split("authored review rows", 1)[1]
        assert "proposed_response" not in retry_prompt.split("authored review rows", 1)[1]

    def test_a_predecessor_free_stage_rejects_a_model_authored_removal_record(
        self, env: _Env
    ) -> None:
        # The removal half. A fabricated record that reached disk would become
        # carried history no later revision re-judges, and would permanently
        # block re-declaring the row it names.
        invoker = _StubInvoker(
            render_domain_artifact(
                replace(
                    _domain(),
                    removals=(
                        RemovalRecord(
                            removed_id="legacy-report",
                            rationale="the reviewer asked for it",
                            feedback_ids=("fb-1",),
                        ),
                    ),
                )
            )
        )

        result = env.run(stages=_stages()[:1], invoker=invoker, max_stage_attempts=1)

        assert result.failure_kind == FAILURE_AUTHORED_REVIEW_ROWS
        assert not env.domain_file.exists()

    def test_the_first_run_reports_no_feedback_awaiting_review_and_no_newly_settled_decisions(
        self, env: _Env
    ) -> None:
        # A first run has no reviewer, so neither advisory can carry a value
        # even when the model settles every decision it authors.
        result = env.run(
            stages=_stages()[:1],
            invoker=_StubInvoker(
                _domain_text(statuses=(DecisionStatus.SETTLED, DecisionStatus.SETTLED))
            ),
        )

        assert result.feedback_awaiting_review == 0
        assert result.newly_settled_decisions == ()


# Whole-artifact re-entry was replaced by the bounded-operation route. The
# prompt-level tests below document that retired wrapper and remain out of
# collection while the focused bounded-route coverage owns its replacement.
for _retired_whole_artifact_case in (
    TestRevisionModeSelection,
    TestActiveFeedbackBlock,
    TestRevisionReflectionContract,
    TestRevisionTemplateMechanics,
    TestRevisionPromptExample,
):
    _retired_whole_artifact_case = pytest.mark.skip(
        reason="the bounded feedback route replaces whole-artifact re-entry"
    )(_retired_whole_artifact_case)


# --------------------------------------------------------------------------
# The shipped domain stage, end to end against the real gates
# --------------------------------------------------------------------------


def _undefined_entity_domain() -> DomainArtifact:
    """A domain whose only workflow names an entity nothing defines."""
    return replace(
        _domain(),
        workflows=(WorkflowRow(id="flow-1", name="Checkout", entity_ids=("cart",)),),
    )


@pytest.mark.integration
class TestDomainStageAgainstTheRealGates:
    """The shipped domain row alone, with its real prompt, parser, and gates."""

    def test_conforming_response_clears_the_real_domain_gates_and_writes(
        self, shipped_env: _Env
    ) -> None:
        invoker = _StubInvoker(_domain_text())

        result = shipped_env.run(stages=roadmap.STAGES[:1], invoker=invoker)

        assert invoker.calls == 1
        assert result.outcome == OUTCOME_COMPLETED
        assert shipped_env.held_stage_file(1).read_text(encoding="utf-8") == _domain_text()
        assert result.violations == ()

    def test_first_authoring_attempt_reuses_its_pre_prompt_source_recheck(self) -> None:
        rechecks: list[None] = []

        outcome = roadmap._run_stage(
            roadmap.STAGES[0],
            slug=SLUG,
            brief=BRIEF,
            upstream=(),
            invoker=_StubInvoker(_domain_text()),
            max_attempts=1,
            run_logger=None,
            phase="stage-1-domain",
            source_recheck=lambda: rechecks.append(None),
        )

        assert outcome.artifact is not None
        # Before prompt rendering and before gates remain; attempt one does
        # not repeat the first check before any source read can intervene.
        assert rechecks == [None, None]

    def test_held_domain_artifact_reparses_through_the_loader(
        self, shipped_env: _Env
    ) -> None:
        shipped_env.run(stages=roadmap.STAGES[:1], invoker=_StubInvoker(_domain_text()))

        assert load_domain_artifact(shipped_env.held_stage_file(1)) == _domain()

    def test_undefined_entity_reference_is_retried_with_the_gate_message(
        self, shipped_env: _Env
    ) -> None:
        broken = _undefined_entity_domain()
        expected = run_domain_gates(ArtifactEnvelope(domain=broken))
        assert [v.kind for v in expected] == [VIOLATION_UNDEFINED_ENTITY_REFERENCE]
        invoker = _StubInvoker(render_domain_artifact(broken), _domain_text())

        result = shipped_env.run(stages=roadmap.STAGES[:1], invoker=invoker)

        assert invoker.calls == 2
        assert f"- {expected[0].message}\n" in invoker.prompts[1]
        assert result.outcome == OUTCOME_COMPLETED

    def test_always_violating_domain_response_exhausts_and_writes_nothing(
        self, shipped_env: _Env
    ) -> None:
        invoker = _StubInvoker(render_domain_artifact(_undefined_entity_domain()))

        result = shipped_env.run(
            stages=roadmap.STAGES, invoker=invoker, max_stage_attempts=2
        )

        assert invoker.calls == 2
        assert result.outcome == OUTCOME_STAGE_EXHAUSTED
        assert result.failed_stage == 1
        assert result.failure_kind == FAILURE_GATES
        assert result.artifacts == ()
        assert not shipped_env.domain_file.exists()

    def test_pending_decision_does_not_fail_the_domain_stage(
        self, shipped_env: _Env
    ) -> None:
        result = shipped_env.run(
            stages=roadmap.STAGES[:1],
            invoker=_StubInvoker(_domain_text(statuses=(DecisionStatus.PENDING,))),
        )

        assert result.outcome == OUTCOME_COMPLETED
        assert result.pending_decisions == 1
        assert shipped_env.held_stage_file(1).is_file()


# --------------------------------------------------------------------------
# The upstream artifact reaching stage 2, and both shipped stages end to end
# --------------------------------------------------------------------------


def _missing_attribute_constraints() -> ConstraintsArtifact:
    """A constraints artifact leaving the last quality attribute undisposed."""
    full = _constraints()
    return replace(full, dispositions=full.dispositions[:-1])


def _multi_anchor_constraints() -> ConstraintsArtifact:
    """One constraint anchored to a rule id and a workflow id, not an entity."""
    full = _constraints()
    return replace(
        full,
        constraints=(
            ConstraintRow(
                id="con-1",
                statement="checkout answers under 200ms at p95",
                attribute="performance",
                anchor_ids=("rule-1", "flow-1"),
            ),
        ),
    )


class TestUpstreamArtifactReachesTheConstraintsStage:
    def test_domain_artifact_text_reaches_the_constraints_prompt(
        self, shipped_env: _Env
    ) -> None:
        invoker = _StubInvoker(
            _domain_text(entity_ids=("marker-entity",)),
            _constraints_text(anchor="marker-entity"),
        )

        shipped_env.run(stages=roadmap.STAGES[:3], invoker=invoker)

        assert "marker-entity" in invoker.prompts[1]

    def test_stage_one_prompt_carries_no_upstream_artifact(
        self, shipped_env: _Env
    ) -> None:
        # The map is filled for every stage, so stage 1's upstream is empty.
        # Pinned here so making the upstream variable required cannot break the
        # first stage silently.
        assert _allowed_variables(_domain_stage()) == {
            "slug",
            "brief",
            "inherited_decisions",
            "smallest_proof_boundary_header",
            "smallest_proof_boundary_footer",
            "writing_style",
        }
        assert not any(
            name.endswith("_artifact") for name in _placeholders(_domain_prompt_text())
        )
        invoker = _StubInvoker(_domain_text(), _constraints_text(), _components_text())

        shipped_env.run(stages=roadmap.STAGES[:3], invoker=invoker)

        assert _placeholders(invoker.prompts[0]) == set()

    def test_constraints_gate_envelope_carries_the_domain_artifact(
        self, shipped_env: _Env
    ) -> None:
        recorder = _GateRecorder()
        stages = (roadmap.STAGES[0], replace(roadmap.STAGES[1], gates=recorder))

        shipped_env.run(
            stages=stages,
            invoker=_StubInvoker(
                _domain_text(), _constraints_text(), _components_text()
            ),
        )

        envelope = recorder.envelopes[0]
        assert envelope.domain == _domain()
        assert envelope.constraints == _constraints()


@pytest.mark.integration
class TestBothShippedStagesAgainstTheRealGates:
    """The first two shipped rows end to end: real prompts, parsers, gates, writes."""

    def test_two_stage_run_writes_both_artifacts_and_completes(
        self, shipped_env: _Env
    ) -> None:
        invoker = _StubInvoker(_domain_text(), _constraints_text())

        result = shipped_env.run(stages=roadmap.STAGES[:2], invoker=invoker)

        assert invoker.calls == 2
        assert result.outcome == OUTCOME_COMPLETED
        assert result.violations == ()
        assert shipped_env.held_stage_file(1).is_file()
        assert shipped_env.held_stage_file(2).is_file()

    def test_held_constraints_artifact_reparses_through_the_loader(
        self, shipped_env: _Env
    ) -> None:
        shipped_env.run(
            stages=roadmap.STAGES[:2],
            invoker=_StubInvoker(_domain_text(), _constraints_text()),
        )

        assert load_constraints_artifact(shipped_env.held_stage_file(2)) == _constraints()

    def test_missing_attribute_is_retried_with_the_totality_gate_message(
        self, shipped_env: _Env
    ) -> None:
        broken = _missing_attribute_constraints()
        expected = run_constraints_gates(
            ArtifactEnvelope(domain=_domain(), constraints=broken)
        )
        assert [v.kind for v in expected] == [VIOLATION_UNDISPOSED_ATTRIBUTE]
        invoker = _StubInvoker(
            _domain_text(),
            render_constraints_artifact(broken),
            _constraints_text(),
        )

        result = shipped_env.run(stages=roadmap.STAGES[:2], invoker=invoker)

        assert invoker.calls == 3
        assert f"- {expected[0].message}\n" in invoker.prompts[2]
        assert result.outcome == OUTCOME_COMPLETED

    def test_unresolvable_anchor_is_retried_with_the_anchor_gate_message(
        self, shipped_env: _Env
    ) -> None:
        broken = _constraints(anchor="no-such-row")
        expected = run_constraints_gates(
            ArtifactEnvelope(domain=_domain(), constraints=broken)
        )
        assert [v.kind for v in expected] == [VIOLATION_UNRESOLVED_CONSTRAINT_ANCHOR]
        invoker = _StubInvoker(
            _domain_text(),
            render_constraints_artifact(broken),
            _constraints_text(),
        )

        result = shipped_env.run(stages=roadmap.STAGES[:2], invoker=invoker)

        assert invoker.calls == 3
        assert f"- {expected[0].message}\n" in invoker.prompts[2]
        assert result.outcome == OUTCOME_COMPLETED

    def test_anchor_gate_resolves_against_stage_ones_held_artifact(
        self, shipped_env: _Env
    ) -> None:
        anchored = _multi_anchor_constraints()
        invoker = _StubInvoker(_domain_text(), render_constraints_artifact(anchored))

        result = shipped_env.run(stages=roadmap.STAGES[:2], invoker=invoker)

        assert invoker.calls == 2
        assert result.outcome == OUTCOME_COMPLETED
        assert load_constraints_artifact(shipped_env.held_stage_file(2)) == anchored

    def test_always_violating_constraints_response_exhausts_and_leaves_domain_intact(
        self, shipped_env: _Env
    ) -> None:
        invoker = _StubInvoker(_domain_text(), _constraints_text(anchor="no-such-row"))

        result = shipped_env.run(
            stages=roadmap.STAGES[:2], invoker=invoker, max_stage_attempts=2
        )

        assert invoker.calls == 3
        assert result.outcome == OUTCOME_STAGE_EXHAUSTED
        assert result.failed_stage == 2
        assert result.failure_kind == FAILURE_GATES
        assert result.artifacts == ()
        assert not shipped_env.held_stage_file(2).exists()
        assert shipped_env.held_stage_file(1).read_text(encoding="utf-8") == _domain_text()

    def test_pending_constraints_decision_does_not_fail_the_run(
        self, shipped_env: _Env
    ) -> None:
        result = shipped_env.run(
            stages=roadmap.STAGES[:2],
            invoker=_StubInvoker(
                _domain_text(),
                _constraints_text(statuses=(DecisionStatus.PENDING,)),
            ),
        )

        assert result.outcome == OUTCOME_COMPLETED
        assert result.pending_decisions == 1
        assert shipped_env.held_stage_file(2).is_file()


def _undefined_pattern_components() -> ComponentsArtifact:
    """A components artifact whose only component cites an undefined pattern."""
    return replace(
        _components(),
        components=(
            ComponentRow(
                id="component-checkout",
                name="Checkout",
                entity_ids=("order",),
                pattern_ids=("missing-pattern",),
                constraint_ids=("con-1",),
                store_ids=("store-checkout",),
            ),
        ),
    )


@pytest.mark.integration
class TestComponentsStageAgainstTheRealGates:
    """The shipped components row with its real prompt, parser, and gates."""

    def test_conforming_components_response_clears_the_real_gates_and_is_held(
        self, shipped_env: _Env
    ) -> None:
        invoker = _three_stage_invoker()

        result = shipped_env.run(stages=roadmap.STAGES[:3], invoker=invoker)

        assert invoker.calls == 3
        assert result.outcome == OUTCOME_COMPLETED
        assert result.violations == ()
        assert load_components_artifact(shipped_env.held_stage_file(3)) == _components()

    def test_gate_violation_is_retried_with_the_message_verbatim(
        self, shipped_env: _Env
    ) -> None:
        broken = _undefined_pattern_components()
        expected = run_components_gates(
            ArtifactEnvelope(
                domain=_domain(), constraints=_constraints(), components=broken
            )
        )
        assert [v.kind for v in expected] == [VIOLATION_UNDEFINED_PATTERN_REFERENCE]
        invoker = _StubInvoker(
            _domain_text(),
            _constraints_text(),
            render_components_artifact(broken),
            _components_text(),
        )

        result = shipped_env.run(stages=roadmap.STAGES[:3], invoker=invoker)

        assert invoker.calls == 4
        assert f"- {expected[0].message}\n" in invoker.prompts[3]
        assert result.outcome == OUTCOME_COMPLETED

    def test_always_violating_components_response_exhausts_and_keeps_upstream_held(
        self, shipped_env: _Env
    ) -> None:
        invoker = _StubInvoker(
            _domain_text(),
            _constraints_text(),
            render_components_artifact(_undefined_pattern_components()),
        )

        result = shipped_env.run(
            stages=roadmap.STAGES[:3], invoker=invoker, max_stage_attempts=2
        )

        assert invoker.calls == 4
        assert result.outcome == OUTCOME_STAGE_EXHAUSTED
        assert result.failed_stage == 3
        assert result.failure_kind == FAILURE_GATES
        assert result.artifacts == ()
        assert shipped_env.held_stage_file(1).is_file()
        assert shipped_env.held_stage_file(2).is_file()
        assert not shipped_env.held_stage_file(3).exists()

    def test_pending_components_decision_does_not_fail_the_run(
        self, shipped_env: _Env
    ) -> None:
        result = shipped_env.run(
            stages=roadmap.STAGES[:3],
            invoker=_three_stage_invoker(statuses=(DecisionStatus.PENDING,)),
        )

        assert result.outcome == OUTCOME_COMPLETED
        assert result.pending_decisions == 1
        assert shipped_env.held_stage_file(3).is_file()


@pytest.mark.integration
class TestFourStageArcAgainstTheRealGates:
    """All four shipped rows end to end."""

    def test_four_stage_run_publishes_the_version_and_completes(
        self, shipped_env: _Env
    ) -> None:
        invoker = _four_stage_invoker()

        result = shipped_env.run(stages=roadmap.STAGES, invoker=invoker)

        assert invoker.calls == 4
        assert result.outcome == OUTCOME_COMPLETED
        assert result.violations == ()
        assert accepted_head_path(shipped_env.plans_dir, SLUG).is_file()
        assert len(result.artifacts) == 4
        assert all(path.is_file() for path in result.artifacts)

    def test_four_stage_run_does_not_write_plan_seeds_dir(
        self, shipped_env: _Env, tmp_path: Path
    ) -> None:
        repo_seeds = tmp_path / "plan-seeds"
        repo_seeds.mkdir()
        marker = repo_seeds / "marker.md"
        marker.write_text("untouched\n", encoding="utf-8")

        shipped_env.run(stages=roadmap.STAGES, invoker=_four_stage_invoker())

        assert marker.read_text(encoding="utf-8") == "untouched\n"

    def test_published_plans_artifact_reparses_from_the_version_store(
        self, shipped_env: _Env
    ) -> None:
        result = shipped_env.run(stages=roadmap.STAGES, invoker=_four_stage_invoker())

        loaded = load_plans_artifact(result.artifacts[3])
        assert result.artifacts[3].name == PLANS_FILENAME
        assert loaded.plans
        assert loaded.ordering

    def test_plans_stage_writes_no_draft_seeds(self, shipped_env: _Env) -> None:
        shipped_env.run(
            stages=roadmap.STAGES,
            invoker=_StubInvoker(
                _domain_text(),
                _constraints_text(),
                _components_text(),
                _plans_artifact_text(),
            ),
        )

        assert not draft_seeds_dir(shipped_env.plans_dir, SLUG).exists()

    def test_exhausted_plans_stage_publishes_nothing_and_keeps_stages_one_to_three_held(
        self, shipped_env: _Env
    ) -> None:
        broken = _plans_artifact_text(plans=(_PLAN_ORDER,))
        result = shipped_env.run(
            stages=roadmap.STAGES,
            invoker=_StubInvoker(
                _domain_text(), _constraints_text(), _components_text(), broken
            ),
            max_stage_attempts=1,
        )

        assert result.outcome == OUTCOME_STAGE_EXHAUSTED
        assert result.failed_stage == 4
        assert not accepted_head_path(shipped_env.plans_dir, SLUG).exists()
        assert not draft_seeds_dir(shipped_env.plans_dir, SLUG).exists()
        assert [shipped_env.held_stage_file(n).is_file() for n in (1, 2, 3, 4)] == [
            True,
            True,
            True,
            False,
        ]

    def test_invalid_carried_decision_gate_refusal_publishes_no_version_seed_state_or_seeds(
        self, shipped_env: _Env
    ) -> None:
        decision = replace(_PLANS_DECISION, status=DecisionStatus.SETTLED, source="answer-old")
        brief_block = {
            "confirmed_answers": [
                {"id": "answer-new", "answer": decision.chosen_option, "status": "confirmed"}
            ],
            "decisions": [
                {
                    "id": decision.id,
                    "owner": "plans",
                    "anchor": decision.anchor,
                    "chosen_option": decision.chosen_option,
                    "source": "answer-new",
                    "rationale": decision.rationale,
                    "rejected_alternatives": [
                        {"option": item.option, "reason": item.reason}
                        for item in decision.rejected_alternatives
                    ],
                }
            ],
        }
        shipped_env.brief_path.write_text(
            "# Concept\n\n## Carried decisions\n\n```json\n"
            + json.dumps(brief_block)
            + "\n```\n",
            encoding="utf-8",
        )

        result = shipped_env.run(
            stages=roadmap.STAGES,
            invoker=_StubInvoker(
                _domain_text(),
                _constraints_text(),
                _components_text(),
                _plans_text(decisions=(decision,)),
            ),
            max_stage_attempts=1,
        )

        assert result.outcome == OUTCOME_STAGE_EXHAUSTED
        assert any(
            violation.kind == "inherited-decision-unknown-source"
            for violation in result.violations
        )
        assert not accepted_head_path(shipped_env.plans_dir, SLUG).exists()
        assert not seed_state_path(roadmap_dir(shipped_env.plans_dir, SLUG)).exists()
        assert not draft_seeds_dir(shipped_env.plans_dir, SLUG).exists()

    def test_gate_violation_on_plans_stage_is_retried_with_messages(
        self, shipped_env: _Env
    ) -> None:
        reply = _plans_text()
        invoker = _StubInvoker(
            _domain_text(), _constraints_text(), _components_text(), reply, reply
        )
        stages = (
            *roadmap.STAGES[:3],
            replace(
                roadmap.STAGES[3],
                gates=_GateRecorder(
                    (_violation("plans gate says fix this"),),
                    (),
                ),
            ),
        )

        result = shipped_env.run(stages=stages, invoker=invoker, max_stage_attempts=2)

        assert result.outcome == OUTCOME_COMPLETED
        assert invoker.calls == 5
        assert "plans gate says fix this" in invoker.prompts[4]


@pytest.mark.integration
class TestThreeStageArcAgainstTheRealGates:
    """All three shipped rows end to end."""

    def test_three_stage_run_writes_all_artifacts_and_completes(
        self, shipped_env: _Env
    ) -> None:
        invoker = _three_stage_invoker()

        result = shipped_env.run(stages=roadmap.STAGES[:3], invoker=invoker)

        assert invoker.calls == 3
        assert result.outcome == OUTCOME_COMPLETED
        assert result.violations == ()
        assert [shipped_env.held_stage_file(n).is_file() for n in (1, 2, 3)] == [True] * 3

    def test_stage_two_exhaustion_never_invokes_stage_three(
        self, shipped_env: _Env
    ) -> None:
        invoker = _StubInvoker(_domain_text(), _constraints_text(anchor="no-such-row"))

        result = shipped_env.run(
            stages=roadmap.STAGES, invoker=invoker, max_stage_attempts=2
        )

        assert invoker.calls == 3
        assert result.outcome == OUTCOME_STAGE_EXHAUSTED
        assert result.failed_stage == 2
        assert len(invoker.prompts) == 3

    def test_components_gate_envelope_carries_domain_and_constraints_from_memory(
        self, shipped_env: _Env
    ) -> None:
        recorder = _GateRecorder()
        stages = (
            roadmap.STAGES[0],
            roadmap.STAGES[1],
            replace(roadmap.STAGES[2], gates=recorder),
        )

        shipped_env.run(stages=stages, invoker=_three_stage_invoker())

        envelope = recorder.envelopes[0]
        assert envelope.domain == _domain()
        assert envelope.constraints == _constraints()


# --------------------------------------------------------------------------
# A stage is data, not a code path
# --------------------------------------------------------------------------


class _RecordingParser:
    """A stage's own parser, wrapped so the loop's use of it is observable."""

    def __init__(self, parse: Any) -> None:
        self._parse = parse
        self.calls = 0

    def __call__(self, text: str) -> Any:
        self.calls += 1
        return self._parse(text)


class TestSyntheticThirdStage:
    """A third stage arrives as a table entry, never as a branch in the loop."""

    @staticmethod
    def _table(env: _Env, *, gates: Any, parse: Any = None) -> tuple[RoadmapStage, ...]:
        for stage in roadmap.STAGES:
            (env.prompts / stage.prompt_filename).write_text(
                f"Stage {stage.number} for ${{slug}}\n\nBRIEF:\n${{brief}}\n",
                encoding="utf-8",
            )
        (env.prompts / "stage-4.md").write_text(
            "Stage 4 for ${slug}\n\nDOMAIN:\n${domain_artifact}\n\n"
            "CONSTRAINTS:\n${constraints_artifact}\n\n"
            "COMPONENTS:\n${components_artifact}\n\n"
            "PLANS:\n${plans_artifact}\n",
            encoding="utf-8",
        )
        (env.prompts / "stage-5.md").write_text(
            "Stage 5 for ${slug}\n\nDOMAIN:\n${domain_artifact}\n\n"
            "CONSTRAINTS:\n${constraints_artifact}\n\n"
            "COMPONENTS:\n${components_artifact}\n\n"
            "PLANS:\n${plans_artifact}\n",
            encoding="utf-8",
        )
        synthetic = RoadmapStage(
            number=5,
            name="synthetic",
            prompt_filename="stage-5.md",
            artifact_key="components",
            parse=parse if parse is not None else parse_components_artifact,
            render=render_components_artifact,
            gates=gates,
        )
        # A copy — the shipped tuple is never appended to.
        return (*roadmap.STAGES, synthetic)

    def test_a_synthetic_third_stage_drives_through_the_loop_unchanged(
        self, env: _Env
    ) -> None:
        parser = _RecordingParser(parse_components_artifact)
        gates = _GateRecorder()
        invoker = _StubInvoker(
            _domain_text(),
            _constraints_text(),
            _components_text(),
            _plans_text(),
            _components_text(),
        )

        result = env.run(
            stages=self._table(env, gates=gates, parse=parser), invoker=invoker
        )

        assert invoker.calls == 5
        assert result.outcome == OUTCOME_COMPLETED
        assert result.stages_run == (1, 2, 3, 4, 5)
        # A five-row table is not the version inventory, so nothing publishes.
        assert result.artifacts == ()
        assert [env.held_stage_file(n).is_file() for n in range(1, 6)] == [True] * 5
        # Stage 5's own parser and gate set are the ones the loop used for it.
        assert parser.calls >= 1
        assert len(gates.envelopes) == 1

        source = Path(roadmap.__file__).read_text(encoding="utf-8")
        assert not re.search(r"stage\.(name|number)\s*==", source)

    def test_the_synthetic_stage_receives_all_shipped_artifacts_below_it(
        self, env: _Env
    ) -> None:
        marker_components = render_components_artifact(
            replace(
                _components(),
                components=(
                    replace(
                        _components().components[0],
                        entity_ids=("marker-entity",),
                    ),
                ),
            )
        )
        gates = _GateRecorder()
        invoker = _StubInvoker(
            _domain_text(entity_ids=("marker-entity",)),
            _constraints_text(anchor="marker-entity"),
            marker_components,
            _plans_text(),
            marker_components,
        )

        env.run(stages=self._table(env, gates=gates), invoker=invoker)

        # Every artifact below stage 5 reaches it, each under its own variable.
        assert "marker-entity" in invoker.prompts[4]
        assert "con-1" in invoker.prompts[4]
        assert "component-checkout" in invoker.prompts[4]
        assert "plan-order-core" in invoker.prompts[4]
        assert gates.envelopes[0].domain == _domain(entity_ids=("marker-entity",))

    def test_the_shipped_table_is_unchanged_by_the_synthetic_stage_case(
        self, env: _Env
    ) -> None:
        env.run(
            stages=self._table(env, gates=_GateRecorder()),
            invoker=_StubInvoker(
                _domain_text(),
                _constraints_text(),
                _components_text(),
                _plans_text(),
                _components_text(),
            ),
        )

        assert len(roadmap.STAGES) == 4
        assert [stage.number for stage in roadmap.STAGES] == [1, 2, 3, 4]


# --------------------------------------------------------------------------
# Stage table and dispatch
# --------------------------------------------------------------------------


class TestStageTableAndDispatch:
    def test_stages_run_in_table_order(self, env: _Env) -> None:
        invoker = _StubInvoker(_domain_text(), _constraints_text(), _components_text())

        # Handed to the loop highest-number-first; it still runs 1 then 2.
        env.run(stages=tuple(reversed(_stages())), invoker=invoker)

        assert [prompt.splitlines()[0] for prompt in invoker.prompts] == [
            f"Stage 1 for {SLUG}",
            f"Stage 2 for {SLUG}",
        ]

    def test_gate_envelope_carries_every_artifact_below_the_stage(
        self, env: _Env
    ) -> None:
        fresh_gate = _GateRecorder()
        env.run(
            stages=_stages(constraints_gates=fresh_gate),
            invoker=_StubInvoker(
                _domain_text(), _constraints_text(), _components_text()
            ),
        )
        fresh = fresh_gate.envelopes[0]
        assert [row.id for row in fresh.domain.entities] == ["order"]
        assert fresh.constraints is not None

    def test_upstream_is_the_rendered_then_reparsed_text_not_the_replys_parse(
        self, env: _Env
    ) -> None:
        def render_with_ghost(artifact: DomainArtifact) -> str:
            return render_domain_artifact(
                replace(
                    artifact,
                    entities=artifact.entities
                    + (
                        EntityRow(
                            id="ghost",
                            name="Ghost",
                            fields=(FieldRow(name="id", type=FieldType.TEXT),),
                        ),
                    ),
                )
            )

        gate = _GateRecorder()
        reply = _domain_text()
        assert "ghost" not in reply

        env.run(
            stages=_stages(domain_render=render_with_ghost, constraints_gates=gate),
            invoker=_StubInvoker(reply, _constraints_text()),
        )

        # Stage 2 sees what a resumed run would read back from the held text,
        # not the reply's parse, so a renderer defect fails on the next stage.
        assert "ghost" in {row.id for row in gate.envelopes[0].domain.entities}


# --------------------------------------------------------------------------
# The clean path
# --------------------------------------------------------------------------


class TestCleanPath:
    def test_clean_run_holds_one_artifact_per_stage_and_writes_no_top_level_file(
        self, env: _Env
    ) -> None:
        env.run(
            stages=_stages(),
            invoker=_StubInvoker(
                _domain_text(), _constraints_text(), _components_text()
            ),
        )

        assert env.held_stage_file(1).is_file()
        assert env.held_stage_file(2).is_file()
        assert not env.domain_file.exists()
        assert not env.constraints_file.exists()

    def test_held_artifact_reparses_through_the_loader(self, env: _Env) -> None:
        env.run(
            stages=_stages(),
            invoker=_StubInvoker(
                _domain_text(), _constraints_text(), _components_text()
            ),
        )

        assert load_domain_artifact(env.held_stage_file(1)) == _domain()

    def test_held_bytes_come_from_the_renderer_not_the_raw_response(
        self, env: _Env
    ) -> None:
        reply = f"Sure, here it is:\n\n```markdown\n{_domain_text()}```\n"

        env.run(stages=_stages()[:1], invoker=_StubInvoker(reply))

        on_disk = env.held_stage_file(1).read_text(encoding="utf-8")
        assert on_disk == _domain_text()
        assert "Sure, here it is" not in on_disk
        assert "```" not in on_disk

    def test_ambiguous_preamble_fences_retry_instead_of_corrupting(
        self, env: _Env
    ) -> None:
        opener_first = f"```text\nnot an outer wrapper\n{_domain_text()}```\n"
        commentary_on_both_sides = (
            f"Sure, here it is:\n\n```markdown\nHere is the domain artifact:\n"
            f"{_domain_text()}```\n"
        )
        invoker = _StubInvoker(opener_first, commentary_on_both_sides, _domain_text())

        env.run(stages=_stages()[:1], invoker=invoker, max_stage_attempts=3)

        on_disk = env.held_stage_file(1).read_text(encoding="utf-8")
        assert on_disk == _domain_text()
        assert invoker.calls == 3
        assert "not an outer wrapper" not in on_disk

    def test_four_backtick_outer_reply_fence_is_stripped(self, env: _Env) -> None:
        reply = f"````markdown\n{_domain_text()}````\n"

        env.run(stages=_stages()[:1], invoker=_StubInvoker(reply))

        assert env.held_stage_file(1).read_text(encoding="utf-8") == _domain_text()

    def test_run_state_stays_under_the_run_directory_and_never_under_the_roadmap_folder(
        self, env: _Env
    ) -> None:
        env.run(
            stages=_stages(),
            invoker=_StubInvoker(
                _domain_text(), _constraints_text(), _components_text()
            ),
        )

        state_dir = env.repo_root / ".plan-tool"
        written = [path for path in state_dir.rglob("*") if path.is_file()]
        assert written
        runs_dir = state_dir / "runs" / SLUG
        assert all(
            path.parent in (runs_dir, runs_dir / RESUME_DIRNAME) for path in written
        )
        assert not any(
            path.name in (DOMAIN_FILENAME, CONSTRAINTS_FILENAME) for path in written
        )
        assert not env.domain_file.exists()

    def test_clean_run_returns_the_completed_outcome(self, env: _Env) -> None:
        result = env.run(
            stages=_stages(),
            invoker=_StubInvoker(
                _domain_text(), _constraints_text(), _components_text()
            ),
        )

        assert result.outcome == OUTCOME_COMPLETED
        assert result.artifacts == ()
        assert result.stages_run == (1, 2)
        assert result.failed_stage is None
        assert result.violations == ()


# --------------------------------------------------------------------------
# Stage status
# --------------------------------------------------------------------------


class TestStageRunGuard:
    """Direct coverage for the shared stage-loop exception guard."""

    def test_emits_stopped_and_reraises_on_exception(self) -> None:
        statuses: list[str] = []
        stage = _stages()[0]

        with pytest.raises(ValueError), roadmap._stage_run_guard(
            statuses.append, slug="storefront", stage=stage
        ):
            raise ValueError("boom")

        assert statuses == ["roadmap storefront: stage 1 (domain) stopped"]

    def test_does_not_emit_on_a_normal_exit(self) -> None:
        statuses: list[str] = []
        stage = _stages()[0]

        with roadmap._stage_run_guard(statuses.append, slug="storefront", stage=stage):
            pass

        assert statuses == []

    def test_does_not_emit_on_break_or_continue(self) -> None:
        """A ``break``/``continue`` inside the guarded block is not an
        exception, so it must resolve without firing "stopped" — the exact
        property that keeps every already-terminal branch in the stage loop
        (a successful write, a re-gate) from double-reporting."""
        statuses: list[str] = []
        stage = _stages()[0]

        for _ in (1,):
            with roadmap._stage_run_guard(statuses.append, slug="storefront", stage=stage):
                continue

        assert statuses == []

    def test_does_not_double_emit_when_the_body_already_reported_stopped(self) -> None:
        """A branch that reports "stopped" itself via the yielded reporter,
        then raises while doing its own follow-up bookkeeping, must not make
        the guard's ``except`` report a second "stopped" for the same
        attempt."""
        statuses: list[str] = []
        stage = _stages()[0]

        with pytest.raises(ValueError), roadmap._stage_run_guard(
            statuses.append, slug="storefront", stage=stage
        ) as reporter:
            reporter.emit()
            raise ValueError("boom in post-stopped bookkeeping")

        assert statuses == ["roadmap storefront: stage 1 (domain) stopped"]

    def test_sets_stage_started_when_absent(self) -> None:
        """A ``RoadmapError`` with no prior opinion is presumed to have come
        from an in-progress attempt (the ordinary case), so the guard fills
        in ``True``."""
        stage = _stages()[0]

        with pytest.raises(roadmap.RoadmapError) as excinfo, roadmap._stage_run_guard(
            None, slug="storefront", stage=stage
        ):
            raise roadmap.RoadmapError("boom mid-attempt")

        assert excinfo.value.roadmap_stage_started is True

    def test_preserves_a_preflight_failure_marked_not_started(self) -> None:
        """A failure that already knows it happened before any stage
        attempt (e.g. ``_preflight_prompt_error``'s ``False``) must survive
        the guard unchanged — the guard only fills in a missing fact, it
        never overrides one already recorded at the origin."""
        stage = _stages()[0]

        def raise_preflight_failure() -> None:
            raise roadmap._preflight_prompt_error("no prompt template")

        with pytest.raises(roadmap.RoadmapError) as excinfo, roadmap._stage_run_guard(
            None, slug="storefront", stage=stage
        ):
            raise_preflight_failure()

        assert excinfo.value.roadmap_stage_started is False


class TestRoadmapStageStatus:
    def test_run_roadmap_is_silent_without_a_status_callback(
        self, env: _Env, capsys: pytest.CaptureFixture[str]
    ) -> None:
        result = env.run(stages=_stages()[:1], invoker=_StubInvoker(_domain_text()))

        captured = capsys.readouterr()

        assert result.outcome == OUTCOME_COMPLETED
        assert env.held_stage_file(1).is_file()
        assert captured.out == ""
        assert captured.err == ""

    def test_accepted_range_precedes_first_stage_start_and_retries_are_reported(
        self, env: _Env
    ) -> None:
        statuses: list[str] = []
        gate = _GateRecorder((_violation("retry once"),), ())

        result = env.run(
            stages=_stages(domain_gates=gate)[:1],
            invoker=_StubInvoker(_domain_text()),
            status_callback=statuses.append,
        )

        assert result.outcome == OUTCOME_COMPLETED
        assert statuses == [
            "roadmap storefront: accepted 1 stage(s) [1]",
            "roadmap storefront: stage 1 (domain) started",
            "roadmap storefront: stage 1 (domain) retrying (attempt 2) after gates",
            "roadmap storefront: stage 1 (domain) wrote",
        ]

    def test_exhausted_retry_budget_emits_stopped_not_a_false_retry(
        self, env: _Env
    ) -> None:
        statuses: list[str] = []
        gate = _GateRecorder((_violation("never passes"),))

        result = env.run(
            stages=_stages(domain_gates=gate)[:1],
            invoker=_StubInvoker(_domain_text()),
            max_stage_attempts=2,
            status_callback=statuses.append,
        )

        assert result.outcome == OUTCOME_STAGE_EXHAUSTED
        assert statuses == [
            "roadmap storefront: accepted 1 stage(s) [1]",
            "roadmap storefront: stage 1 (domain) started",
            "roadmap storefront: stage 1 (domain) retrying (attempt 2) after gates",
            "roadmap storefront: stage 1 (domain) stopped after gates",
        ]

    def test_phase_end_failure_after_an_explicit_stopped_does_not_double_report(
        self, env: _Env, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A ``phase_end`` failure that lands *after* a branch already
        reported "stopped" itself (exhaustion here) must not make the guard
        report a second, bare "stopped" for the same attempt."""
        statuses: list[str] = []
        gate = _GateRecorder((_violation("never passes"),))

        def broken_phase_end(
            self: Any, phase: str, duration_ms: int, outcome: str, **extra: Any
        ) -> None:
            if outcome == "exhausted":
                raise RunLogLineTooLarge("phase-end payload too large")

        monkeypatch.setattr(roadmap.RunLogWriter, "phase_end", broken_phase_end)

        with pytest.raises(RunLogLineTooLarge):
            env.run(
                stages=_stages(domain_gates=gate)[:1],
                invoker=_StubInvoker(_domain_text()),
                max_stage_attempts=2,
                status_callback=statuses.append,
            )

        assert statuses == [
            "roadmap storefront: accepted 1 stage(s) [1]",
            "roadmap storefront: stage 1 (domain) started",
            "roadmap storefront: stage 1 (domain) retrying (attempt 2) after gates",
            "roadmap storefront: stage 1 (domain) stopped after gates",
        ]

    def test_escaping_roadmap_error_after_stage_start_stops_and_reraises(
        self, env: _Env
    ) -> None:
        statuses: list[str] = []
        stage = replace(_stages()[0], prompt_filename="missing-template.md")

        with pytest.raises(RoadmapError):
            env.run(stages=(stage,), invoker=_never_called, status_callback=statuses.append)

        assert statuses == [
            "roadmap storefront: accepted 1 stage(s) [1]",
            "roadmap storefront: stage 1 (domain) started",
            "roadmap storefront: stage 1 (domain) stopped",
        ]

    def test_status_lines_are_single_line_ascii_capped_and_distinguishable(self) -> None:
        first: list[str] = []
        second: list[str] = []
        stage = replace(_stages()[0], number="7\n" * 100, name="name\x00é" * 100)

        roadmap._emit_roadmap_status(
            first.append,
            slug="same-prefix-" + "x" * 100 + "first\n",
            stage=stage,
            fact="started",
        )
        roadmap._emit_roadmap_status(
            second.append,
            slug="same-prefix-" + "x" * 100 + "second\n",
            stage=stage,
            fact="started",
        )

        assert len(first) == len(second) == 1
        assert first[0] != second[0]
        for status in (*first, *second):
            assert len(status) <= 250
            assert status.isascii()
            assert all(" " <= char <= "~" for char in status)
            assert "...#" in status

    @pytest.mark.parametrize("limit", [0, 1, 5, 13, 14, 15, 80])
    def test_bounded_status_text_never_exceeds_its_own_limit(self, limit: int) -> None:
        result = roadmap._bounded_status_text("x" * 200, limit=limit)

        assert len(result) <= limit

    def test_bounded_status_text_clips_non_ascii_escaped_text_without_raising(self) -> None:
        """The digest hashes the clipped text as utf-8, not ascii: an
        ``escaped=True`` caller's text is not guaranteed ascii-only, and a
        non-ascii value over the limit must still clip, not raise."""
        result = roadmap._bounded_status_text("é" * 100, limit=80, escaped=True)

        assert len(result) <= 80
        assert "...#" in result

    def test_accepted_range_uses_actual_sparse_stage_numbers(self, env: _Env) -> None:
        statuses: list[str] = []
        sparse_stage = replace(_stages()[0], number=7)

        result = env.run(
            stages=(sparse_stage,),
            invoker=_StubInvoker(_domain_text()),
            status_callback=statuses.append,
        )

        assert result.outcome == OUTCOME_COMPLETED
        assert statuses[0] == "roadmap storefront: accepted 1 stage(s) [7]"
        assert "[1" not in statuses[0]

        large: list[str] = []
        huge_stage = replace(sparse_stage, number=10**100)
        roadmap._emit_accepted_stage_selection(
            large.append,
            slug="storefront",
            stages=(huge_stage,),
        )

        assert len(large) == 1
        assert len(large[0]) <= 250
        assert large[0].isascii()
        assert "...#" in large[0]

    def test_empty_stage_table_reports_zero_selected_stages_then_completed(
        self, env: _Env
    ) -> None:
        statuses: list[str] = []

        result = env.run(stages=(), invoker=_never_called, status_callback=statuses.append)
        roadmap.emit_roadmap_terminal_status(statuses.append, slug=SLUG, result=result)

        assert result.outcome == OUTCOME_COMPLETED
        assert statuses == [
            "roadmap storefront: accepted 0 stage(s) []",
            "roadmap storefront: completed",
        ]

    def test_terminal_status_reuses_the_safe_slug_formatter(self) -> None:
        statuses: list[str] = []
        result = RoadmapResult(
            outcome=OUTCOME_COMPLETED,
            artifacts=(),
            stages_run=(),
            pending_decisions=0,
        )

        roadmap.emit_roadmap_terminal_status(
            statuses.append,
            slug="storefront\nunsafe",
            result=result,
        )

        assert statuses == ["roadmap storefront\\nunsafe: completed"]

    def test_terminal_status_sink_exception_is_fail_open(self, env: _Env) -> None:
        result = env.run(stages=_stages()[:1], invoker=_StubInvoker(_domain_text()))

        roadmap.emit_roadmap_terminal_status(
            lambda _status: (_ for _ in ()).throw(RuntimeError("closed sink")),
            slug=SLUG,
            result=result,
        )

        assert result.outcome == OUTCOME_COMPLETED
        assert env.held_stage_file(1).is_file()

    def test_terminal_status_never_raises_on_an_unregistered_outcome(self) -> None:
        """An unregistered ``outcome`` stays fail-open (no emit, no raise) —
        the run has already completed by the time this runs."""
        statuses: list[str] = []
        result = RoadmapResult(
            outcome="not-a-registered-outcome",
            artifacts=(),
            stages_run=(),
            pending_decisions=0,
        )

        roadmap.emit_roadmap_terminal_status(statuses.append, slug=SLUG, result=result)

        assert statuses == []

    def test_status_callback_exception_is_fail_open(self, env: _Env) -> None:
        def broken_callback(_status: str) -> None:
            raise RuntimeError("closed sink")

        result = env.run(
            stages=_stages()[:1],
            invoker=_StubInvoker(_domain_text()),
            status_callback=broken_callback,
        )

        assert result.outcome == OUTCOME_COMPLETED
        assert env.held_stage_file(1).is_file()

    def test_status_callback_keyboard_interrupt_propagates(self, env: _Env) -> None:
        with pytest.raises(KeyboardInterrupt):
            env.run(
                stages=_stages()[:1],
                invoker=_never_called,
                status_callback=lambda _status: (_ for _ in ()).throw(KeyboardInterrupt()),
            )

    def test_status_callback_preserves_existing_run_log_events(self, env: _Env) -> None:
        statuses: list[str] = []

        result = env.run(
            stages=_stages()[:1],
            invoker=_StubInvoker(_domain_text()),
            status_callback=statuses.append,
        )

        assert result.outcome == OUTCOME_COMPLETED
        assert statuses == [
            "roadmap storefront: accepted 1 stage(s) [1]",
            "roadmap storefront: stage 1 (domain) started",
            "roadmap storefront: stage 1 (domain) wrote",
        ]
        assert [event["event"] for event in env.run_log_events()] == [
            "run_start",
            "phase_start",
            "claude_call_start",
            "roadmap_stage_written",
            "phase_end",
            "run_end",
        ]

    @pytest.mark.parametrize("log_count", (0, 2))
    def test_run_log_events_rejects_non_unique_wrapped_run_logs(
        self, env: _Env, monkeypatch: pytest.MonkeyPatch, log_count: int
    ) -> None:
        def run_with_wrong_log_count(*_args: Any, **_kwargs: Any) -> RoadmapResult:
            logs_dir = env.repo_root / ".plan-tool" / "runs" / SLUG
            logs_dir.mkdir(parents=True, exist_ok=True)
            for index in range(log_count):
                (logs_dir / f"probe-{index}.jsonl").write_text("{}\n", encoding="utf-8")
            return RoadmapResult(
                outcome=OUTCOME_COMPLETED,
                artifacts=(),
                stages_run=(),
                pending_decisions=0,
            )

        monkeypatch.setattr(roadmap, "run_roadmap", run_with_wrong_log_count)

        env.run()

        with pytest.raises(AssertionError, match="expected exactly one run log"):
            env.run_log_events()

    def test_mid_run_writer_guard_failure_preserves_after_start_origin(
        self, shipped_env: _Env, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Publication guard failures retain their started-run classification."""

        def broken_publish(*_args: Any, **_kwargs: Any) -> None:
            raise roadmap.RoadmapWriterGuardError("stale writer token")

        monkeypatch.setattr(roadmap, "publish_roadmap_generation", broken_publish)

        with pytest.raises(roadmap.RoadmapRunStartedWriterGuardError):
            shipped_env.run(stages=roadmap.STAGES, invoker=_four_stage_invoker())

        events = shipped_env.run_log_events()
        assert [event for event in events if event["event"] == "phase_start"]
        run_ends = [event for event in events if event["event"] == "run_end"]
        assert len(run_ends) == 1
        assert run_ends[0]["outcome"] == "error"
        assert run_ends[0]["rc"] == 1

    def test_phase_start_log_failure_emits_stopped(
        self, env: _Env, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``run_logger.phase_start`` runs after ``started`` is emitted,
        inside the dispatch try/except, so a failure there still emits
        ``stopped`` instead of leaving the stream on the prior stage."""
        statuses: list[str] = []

        def broken_phase_start(*_args: Any, **_kwargs: Any) -> None:
            raise RunLogLineTooLarge("phase-start payload too large")

        monkeypatch.setattr(roadmap.RunLogWriter, "phase_start", broken_phase_start)

        with pytest.raises(RunLogLineTooLarge):
            env.run(
                stages=_stages()[:1],
                invoker=_StubInvoker(_domain_text()),
                status_callback=statuses.append,
            )

        assert statuses == [
            "roadmap storefront: accepted 1 stage(s) [1]",
            "roadmap storefront: stage 1 (domain) started",
            "roadmap storefront: stage 1 (domain) stopped",
        ]

    def test_gate_violations_log_failure_emits_stopped(
        self, env: _Env, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A non-roadmap ``ValueError`` from ``gate_violations``, uncaught by
        ``_run_stage`` itself, still reaches the dispatch-level catch-all."""
        statuses: list[str] = []
        gate = _GateRecorder((_violation("never passes"),))

        def broken_gate_violations(*_args: Any, **_kwargs: Any) -> None:
            raise RunLogLineTooLarge("violation payload too large")

        monkeypatch.setattr(roadmap.RunLogWriter, "gate_violations", broken_gate_violations)

        with pytest.raises(RunLogLineTooLarge):
            env.run(
                stages=_stages(domain_gates=gate)[:1],
                invoker=_StubInvoker(_domain_text()),
                status_callback=statuses.append,
            )

        assert statuses == [
            "roadmap storefront: accepted 1 stage(s) [1]",
            "roadmap storefront: stage 1 (domain) started",
            "roadmap storefront: stage 1 (domain) stopped",
        ]

    def test_post_write_bookkeeping_failure_emits_stopped_after_wrote(
        self, env: _Env, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failure after ``wrote`` is emitted must still emit ``stopped``
        — see the comment beside this except block for why they don't
        contradict."""
        statuses: list[str] = []

        def broken_roadmap_stage_written(*_args: Any, **_kwargs: Any) -> None:
            raise RunLogLineTooLarge("artifact digest payload too large")

        monkeypatch.setattr(
            roadmap.RunLogWriter, "roadmap_stage_written", broken_roadmap_stage_written
        )

        with pytest.raises(RunLogLineTooLarge):
            env.run(
                stages=_stages()[:1],
                invoker=_StubInvoker(_domain_text()),
                status_callback=statuses.append,
            )

        assert statuses == [
            "roadmap storefront: accepted 1 stage(s) [1]",
            "roadmap storefront: stage 1 (domain) started",
            "roadmap storefront: stage 1 (domain) wrote",
            "roadmap storefront: stage 1 (domain) stopped",
        ]

    def test_status_facts_omit_prompt_reply_exception_and_transport_content(
        self, env: _Env, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        statuses: list[str] = []
        reply_marker = "reply-secret-DO-NOT-EMIT"
        transport_marker = "transport-secret-DO-NOT-EMIT"
        prompt_marker = "prompt-secret-DO-NOT-EMIT"
        exception_marker = "exception-secret-DO-NOT-EMIT"

        result = env.run(
            stages=_stages()[:1],
            invoker=_StubInvoker((7, f"{reply_marker} {transport_marker}")),
            max_stage_attempts=1,
            status_callback=statuses.append,
        )

        assert result.outcome == OUTCOME_STAGE_EXHAUSTED
        assert reply_marker not in "\n".join(statuses)
        assert transport_marker not in "\n".join(statuses)
        assert statuses[-1] == "roadmap storefront: stage 1 (domain) stopped after invoke"

        prompt_statuses: list[str] = []
        prompt_stage = replace(_stages()[0], prompt_filename=f"{prompt_marker}.md")
        with pytest.raises(RoadmapError):
            env.run(
                stages=(prompt_stage,),
                invoker=_never_called,
                status_callback=prompt_statuses.append,
            )
        assert prompt_marker not in "\n".join(prompt_statuses)

        def raise_prompt_error(*_args: Any, **_kwargs: Any) -> str:
            raise RoadmapError(exception_marker)

        exception_statuses: list[str] = []
        monkeypatch.setattr(roadmap, "_render_stage_prompt", raise_prompt_error)
        with pytest.raises(RoadmapError, match=exception_marker):
            env.run(
                stages=_stages()[:1],
                invoker=_never_called,
                status_callback=exception_statuses.append,
            )
        assert exception_marker not in "\n".join(exception_statuses)


# --------------------------------------------------------------------------
# The retry loop
# --------------------------------------------------------------------------


class TestRetryLoop:
    def test_violations_are_appended_to_the_retried_prompt(self, env: _Env) -> None:
        gate = _GateRecorder((_violation("name the entity ids"),), ())
        invoker = _StubInvoker(_domain_text())

        env.run(stages=_stages(domain_gates=gate)[:1], invoker=invoker)

        assert "name the entity ids" not in invoker.prompts[0]
        assert "The previous response was rejected" in invoker.prompts[1]
        assert "- name the entity ids" in invoker.prompts[1]

    def test_retry_prompt_carries_every_violation_message_verbatim(
        self, env: _Env
    ) -> None:
        messages = [
            "workflow 'flow-1' in 01-domain.md references entity id 'cart', "
            "which no entity row defines",
            "decision 'dec-domain-1' in 01-domain.md has a blank rationale",
        ]
        gate = _GateRecorder(tuple(_violation(message) for message in messages), ())
        invoker = _StubInvoker(_domain_text())

        env.run(stages=_stages(domain_gates=gate)[:1], invoker=invoker)

        for message in messages:
            assert f"- {message}\n" in invoker.prompts[1]

    def test_corrections_replace_rather_than_accumulate(self, env: _Env) -> None:
        gate = _GateRecorder(
            (_violation("violation A"),), (_violation("violation B"),), ()
        )
        invoker = _StubInvoker(_domain_text())

        env.run(stages=_stages(domain_gates=gate)[:1], invoker=invoker)

        assert "- violation B" in invoker.prompts[2]
        assert "violation A" not in invoker.prompts[2]

    def test_second_attempt_passing_gates_writes_the_artifact(self, env: _Env) -> None:
        gate = _GateRecorder((_violation("fix it"),), ())
        invoker = _StubInvoker(_domain_text())

        result = env.run(stages=_stages(domain_gates=gate)[:1], invoker=invoker)

        assert invoker.calls == 2
        assert result.outcome == OUTCOME_COMPLETED
        assert env.held_stage_file(1).is_file()

    def test_unparseable_response_is_retried_like_a_violation(self, env: _Env) -> None:
        invoker = _StubInvoker("I could not produce that.", _domain_text())

        result = env.run(stages=_stages()[:1], invoker=invoker)

        assert invoker.calls == 2
        assert result.outcome == OUTCOME_COMPLETED

    def test_failed_invoke_consumes_an_attempt(self, env: _Env) -> None:
        invoker = _StubInvoker((7, "backend refused"), _domain_text())

        result = env.run(stages=_stages()[:1], invoker=invoker)

        assert invoker.calls == 2
        assert result.outcome == OUTCOME_COMPLETED

    def test_empty_response_consumes_an_attempt(self, env: _Env) -> None:
        invoker = _StubInvoker((0, "   "), _domain_text())

        result = env.run(stages=_stages()[:1], invoker=invoker)

        assert invoker.calls == 2
        assert result.outcome == OUTCOME_COMPLETED

    def test_attempt_count_is_bounded_by_the_budget(self, env: _Env) -> None:
        gate = _GateRecorder((_violation("never satisfied"),))
        invoker = _StubInvoker(_domain_text())

        env.run(stages=_stages(domain_gates=gate)[:1], invoker=invoker)

        assert invoker.calls == roadmap.MAX_STAGE_ATTEMPTS


# --------------------------------------------------------------------------
# Halting
# --------------------------------------------------------------------------


class TestHalting:
    def test_exhausted_budget_halts_before_the_next_stage(self, env: _Env) -> None:
        gate = _GateRecorder((_violation("never satisfied"),))
        invoker = _StubInvoker(_domain_text())

        env.run(
            stages=_stages(domain_gates=gate),
            invoker=invoker,
            max_stage_attempts=2,
        )

        assert invoker.calls == 2
        assert all(prompt.startswith("Stage 1") for prompt in invoker.prompts)

    def test_exhausted_budget_writes_no_artifact_for_the_failed_stage(
        self, env: _Env
    ) -> None:
        gate = _GateRecorder((_violation("never satisfied"),))

        env.run(
            stages=_stages(domain_gates=gate)[:1],
            invoker=_StubInvoker(_domain_text()),
            max_stage_attempts=2,
        )

        assert not env.held_stage_file(1).exists()

    def test_exhausted_budget_leaves_earlier_held_stages_intact(self, env: _Env) -> None:
        gate = _GateRecorder((_violation("never satisfied"),))

        env.run(
            stages=_stages(constraints_gates=gate),
            invoker=_StubInvoker(
                _domain_text(), _constraints_text(), _components_text()
            ),
            max_stage_attempts=2,
        )

        assert env.held_stage_file(1).read_text(encoding="utf-8") == _domain_text()
        assert not env.held_stage_file(2).exists()

    def test_exhausted_budget_returns_the_stage_exhausted_outcome(
        self, env: _Env
    ) -> None:
        violation = _violation("never satisfied")
        gate = _GateRecorder((violation,))

        result = env.run(
            stages=_stages(constraints_gates=gate),
            invoker=_StubInvoker(
                _domain_text(), _constraints_text(), _components_text()
            ),
            max_stage_attempts=2,
        )

        assert result.outcome == OUTCOME_STAGE_EXHAUSTED
        assert result.failed_stage == 2
        assert result.violations == (violation,)
        assert result.artifacts == ()


# --------------------------------------------------------------------------
# The exit-code convention
# --------------------------------------------------------------------------


class TestExitCodeConvention:
    def test_pending_decisions_do_not_change_the_outcome(self, env: _Env) -> None:
        result = env.run(
            stages=_stages(),
            invoker=_StubInvoker(
                _domain_text(statuses=(DecisionStatus.PENDING,)),
                _constraints_text(statuses=(DecisionStatus.PENDING,)),
            ),
        )

        assert result.outcome == OUTCOME_COMPLETED

    def test_pending_decision_count_is_reported_on_the_result(self, env: _Env) -> None:
        result = env.run(
            stages=_stages(),
            invoker=_StubInvoker(
                _domain_text(
                    statuses=(
                        DecisionStatus.PENDING,
                        DecisionStatus.PENDING,
                        DecisionStatus.SETTLED,
                    )
                ),
                _constraints_text(statuses=(DecisionStatus.PENDING,)),
            ),
        )

        assert result.pending_decisions == 3

    def test_outcome_vocabulary_is_closed(self, env: _Env) -> None:
        assert roadmap.OUTCOMES == (
            OUTCOME_COMPLETED,
            OUTCOME_COMPLETED_NO_CHANGE,
            OUTCOME_STAGE_EXHAUSTED,
            OUTCOME_STAGE_INVALID,
        )

        completed = env.run(
            stages=_stages(),
            invoker=_StubInvoker(
                _domain_text(), _constraints_text(), _components_text()
            ),
        )
        exhausted = env.run(
            stages=_stages(domain_gates=_GateRecorder((_violation("no"),)))[:1],
            invoker=_StubInvoker(_domain_text()),
            max_stage_attempts=1,
        )

        assert {completed.outcome, exhausted.outcome} <= set(roadmap.OUTCOMES)
        assert roadmap.is_successful_roadmap_outcome(OUTCOME_COMPLETED)
        assert roadmap.is_successful_roadmap_outcome(OUTCOME_COMPLETED_NO_CHANGE)
        assert not roadmap.is_successful_roadmap_outcome(OUTCOME_STAGE_EXHAUSTED)
        assert not roadmap.is_successful_roadmap_outcome(OUTCOME_STAGE_INVALID)


class TestBoundedStageFeedbackPrimitives:
    """Function-level pins for the bounded stage-feedback route; the stage run no
    longer reaches it (feedback re-enters through the review routes)."""

    def test_feedback_free_route_is_a_named_nonpublishing_operation(self, env: _Env) -> None:
        env.publish_accepted()
        stage = _stages()[0]
        predecessor = roadmap.load_accepted_roadmap_artifacts(
            plans_dir=env.plans_dir, slug=SLUG
        )[0]

        outcome = roadmap._run_feedback_free_stage(
            stage,
            predecessor=predecessor,
            upstream=(),
            feedback_snapshot_before=roadmap.feedback_snapshot(predecessor.artifact),
        )

        assert outcome.artifact == predecessor.artifact
        assert outcome.violations == ()
        assert outcome.reused_predecessor is True

    def test_stage_feedback_prompt_renders_typed_schema_and_limits_without_body(
        self, env: _Env
    ) -> None:
        artifact = replace(
            _domain(),
            body=(
                "\n## Target\n\n`order` is selected.\n"
                "\n## Unrelated\n\nhidden-body-secret stays hidden.\n"
            ),
            feedback=(
                FeedbackRow(
                    "feedback-order",
                    FeedbackTarget(FeedbackTargetKind.ROW, "order"),
                    "Rename the entity.",
                    FeedbackState.OPEN,
                ),
            ),
        )
        context = roadmap.build_stage_revision_context(artifact, artifact_key="domain")

        prompt = roadmap._render_stage_feedback_prompt(context)

        assert '"operations"' in prompt
        assert str(context.limits.max_response_bytes) in prompt
        assert "hidden-body-secret" not in prompt
        assert "${" not in prompt

    def test_stage_feedback_prompt_serializes_set_context_in_stable_order(self) -> None:
        assert roadmap._prompt_json_value(frozenset({"relation-z", "relation-a"})) == [
            "relation-a",
            "relation-z",
        ]

    def test_stage_feedback_prompt_serializes_str_enums_by_wire_value(self) -> None:
        assert roadmap._prompt_json_value(FeedbackState.AWAITING_REVIEW) == "awaiting-review"

    def test_stage_feedback_retry_keeps_the_closed_json_response_contract(self) -> None:
        retry = roadmap._stage_feedback_corrections_block(("response was invalid",))

        assert "one unfenced JSON object" in retry
        assert "closed response schema" in retry
        assert "whole artifact" not in retry


# --------------------------------------------------------------------------
# The run log
# --------------------------------------------------------------------------


class TestRunLog:
    def test_run_log_lands_under_the_runs_directory(self, env: _Env) -> None:
        env.run(
            stages=_stages(),
            invoker=_StubInvoker(
                _domain_text(), _constraints_text(), _components_text()
            ),
        )

        logs = list((env.repo_root / ".plan-tool" / "runs" / SLUG).glob("*.jsonl"))
        assert len(logs) == 1

    def test_stage_run_does_not_opt_into_context(self, env: _Env) -> None:
        result = env.run(
            stages=_stages()[:1],
            invoker=_StubInvoker(_domain_text()),
        )

        events = env.run_log_events()
        assert events[0]["command"] == "roadmap"
        assert events[0]["argv"] == []
        # A first run has no flags, and the logger omits an empty set.
        assert "flags" not in events[0]
        assert [event["event"] for event in events] == [
            "run_start",
            "phase_start",
            "claude_call_start",
            "roadmap_stage_written",
            "phase_end",
            "run_end",
        ]
        assert result.outcome == OUTCOME_COMPLETED
        assert events[-1]["outcome"] == OUTCOME_COMPLETED
        assert events[-1]["rc"] == 0
        assert all(
            context_key not in event
            for event in events
            for context_key in (
                "roadmap_action",
                "roadmap_slug",
                "requested_plan_id",
                "active_plan_id",
                "seed_attempt",
                "backend_attempt",
            )
        )
        assert not (
            env.repo_root / ".plan-tool" / "runs" / SLUG / "in-flight.json"
        ).exists()

    def test_each_stage_emits_a_phase_pair(self, env: _Env) -> None:
        env.run(
            stages=_stages(),
            invoker=_StubInvoker(
                _domain_text(), _constraints_text(), _components_text()
            ),
        )

        events = env.run_log_events()
        starts = [e["phase"] for e in events if e["event"] == "phase_start"]
        ends = [e["phase"] for e in events if e["event"] == "phase_end"]
        assert starts == ["stage-1-domain", "stage-2-constraints"]
        assert ends == starts

    def test_run_records_each_held_stage_and_no_source_events(self, env: _Env) -> None:
        env.run(
            stages=_stages(),
            invoker=_StubInvoker(_domain_text(), _constraints_text()),
        )

        events = env.run_log_events()
        assert not [e for e in events if e["event"].startswith("roadmap_source_")]
        assert BRIEF not in json.dumps(events)

        written = [e for e in events if e["event"] == "roadmap_stage_written"]
        assert [e["stage"] for e in written] == [1, 2]
        assert [e["replaced"] for e in written] == [False, False]
        assert all(len(e["artifact_digest"]) == 64 for e in written)
        assert [e["draft_seed_count"] for e in written] == [0, 0]

    def test_completed_four_stage_run_logs_zero_draft_seed_count_for_every_stage(
        self, shipped_env: _Env
    ) -> None:
        shipped_env.run(stages=roadmap.STAGES, invoker=_four_stage_invoker())

        written = [
            event
            for event in shipped_env.run_log_events()
            if event["event"] == "roadmap_stage_written"
        ]
        assert [event["stage"] for event in written] == [1, 2, 3, 4]
        assert [event["draft_seed_count"] for event in written] == [0, 0, 0, 0]

    def test_stage_run_preflight_error_ends_the_owned_writer_as_refused(
        self, env: _Env
    ) -> None:
        with pytest.raises(RoadmapError, match="no concept brief was given"):
            roadmap.run_roadmap(
                SLUG,
                repo_root=env.repo_root,
                plans_dir=env.plans_dir,
                brief_path=None,
                stages=_stages()[:1],
            )

        events = env.run_log_events()
        failed = [e for e in events if e["event"] == "roadmap_preflight_failed"]
        assert [e["check"] for e in failed] == ["brief_source"]
        run_ends = [event for event in events if event["event"] == "run_end"]
        assert len(run_ends) == 1
        assert run_ends[0]["outcome"] == "preflight-refused"
        assert run_ends[0]["rc"] == 2
        assert not (
            env.repo_root / ".plan-tool" / "runs" / SLUG / "in-flight.json"
        ).exists()

    def test_stage_run_keyboard_interrupt_is_reraised_after_owned_writer_cleanup(
        self, env: _Env
    ) -> None:
        def interrupted_invoker(_prompt: str) -> tuple[int, str]:
            raise KeyboardInterrupt

        with pytest.raises(KeyboardInterrupt):
            env.run(stages=_stages()[:1], invoker=interrupted_invoker)

        events = env.run_log_events()
        run_ends = [event for event in events if event["event"] == "run_end"]
        assert len(run_ends) == 1
        assert run_ends[0]["outcome"] == "error"
        assert run_ends[0]["rc"] == 130
        assert run_ends[0]["error"] == "interrupted"
        assert not (
            env.repo_root / ".plan-tool" / "runs" / SLUG / "in-flight.json"
        ).exists()

    def test_caller_supplied_roadmap_logger_is_not_ended_by_the_command(
        self, env: _Env
    ) -> None:
        writer = RunLogWriter.start(
            repo_root=env.repo_root,
            slug=SLUG,
            command="roadmap",
            argv=[],
            flags={"injected": True},
        )
        try:
            result = env.run(
                stages=_stages()[:1],
                invoker=_StubInvoker(_domain_text()),
                run_logger=writer,
            )

            events = read_run_events(writer.log_path)
            assert result.outcome == OUTCOME_COMPLETED
            assert not [event for event in events if event["event"] == "run_end"]
            assert writer.in_flight_path.exists()
        finally:
            writer.run_end(outcome="test-complete", rc=0)

    def test_each_attempt_emits_a_claude_call_start(self, env: _Env) -> None:
        gate = _GateRecorder((_violation("never satisfied"),))

        env.run(
            stages=_stages(domain_gates=gate)[:1],
            invoker=_StubInvoker(_domain_text()),
            max_stage_attempts=3,
        )

        events = env.run_log_events()
        attempts = [e["attempt"] for e in events if e["event"] == "claude_call_start"]
        assert attempts == [1, 2, 3]

    def test_a_failed_attempt_records_the_violations_that_consumed_it(
        self, env: _Env
    ) -> None:
        gate = _GateRecorder((_violation("order must be an integer"),), ())

        env.run(
            stages=_stages(domain_gates=gate)[:1],
            invoker=_StubInvoker(_domain_text()),
            max_stage_attempts=3,
        )

        events = [e for e in env.run_log_events() if e["event"] == "gate_violations"]
        assert len(events) == 1
        assert events[0]["attempt"] == 1
        assert events[0]["phase"] == "stage-1-domain"
        assert events[0]["stage"] == 1
        assert events[0]["violations"] == ["order must be an integer"]
        assert events[0]["violation_count"] == 1
        assert events[0]["violations_omitted"] == 0

    def test_a_clean_first_attempt_records_no_violations(self, env: _Env) -> None:
        # The point of the event: a stage that passed on its last attempt
        # must not read like this one.
        env.run(
            stages=_stages(),
            invoker=_StubInvoker(
                _domain_text(), _constraints_text(), _components_text()
            ),
        )

        events = env.run_log_events()
        assert [e for e in events if e["event"] == "gate_violations"] == []

    def test_every_attempt_of_an_exhausted_stage_records_its_violations(
        self, env: _Env
    ) -> None:
        gate = _GateRecorder((_violation("never satisfied"),))

        env.run(
            stages=_stages(domain_gates=gate)[:1],
            invoker=_StubInvoker(_domain_text()),
            max_stage_attempts=3,
        )

        events = [e for e in env.run_log_events() if e["event"] == "gate_violations"]
        assert [e["attempt"] for e in events] == [1, 2, 3]
        assert all(e["violations"] == ["never satisfied"] for e in events)

    def test_a_non_gate_failure_records_no_violations(self, env: _Env) -> None:
        # The reply never became an artifact, so no gate had anything to say;
        # that failure kind's evidence is the reply itself (BACKLOG #217).
        env.run(
            stages=_stages()[:1],
            invoker=_StubInvoker((7, "backend refused")),
            max_stage_attempts=2,
        )

        events = env.run_log_events()
        assert [e for e in events if e["event"] == "gate_violations"] == []

    def test_run_end_is_emitted_on_the_failure_path(self, env: _Env) -> None:
        gate = _GateRecorder((_violation("never satisfied"),))

        env.run(
            stages=_stages(domain_gates=gate)[:1],
            invoker=_StubInvoker(_domain_text()),
            max_stage_attempts=1,
        )

        events = env.run_log_events()
        run_ends = [e for e in events if e["event"] == "run_end"]
        assert len(run_ends) == 1
        assert run_ends[0]["outcome"] == OUTCOME_STAGE_EXHAUSTED
        assert run_ends[0]["rc"] == 1
        assert not (
            env.repo_root / ".plan-tool" / "runs" / SLUG / "in-flight.json"
        ).exists()


class TestRealInvoker:
    """Drives ``run_roadmap`` through the real ``shell_roadmap_invoker`` →
    ``shell.claude_invoke`` path (a mocked ``backend_runner.subprocess.Popen``)
    rather than the ``_StubInvoker`` every other case in this file injects —
    pinning what the production call path actually writes to the run log.
    ``claude_invoke`` now builds a full observer from whatever writer
    ``_run_stage``'s ``bind_shell_sink`` bound and passes it to the shared
    runner (batch-authoring-observability plan, step 7), so a heartbeat or
    stall marker *can* land here too — ``test_records_call_start_and_end_only``
    sees neither only because its single-line canned response completes
    before the (real, unshortened) 20s/300s thresholds ever fire, not
    because no writer reaches the runner."""

    def test_records_call_start_and_end_only(
        self, env: _Env, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
        monkeypatch.setattr(
            backend_runner.subprocess,
            "Popen",
            _fake_popen_factory(
                [
                    SimpleNamespace(
                        stdout=_claude_stream_result(_domain_text()),
                        stderr="",
                        returncode=0,
                    ),
                ]
            ),
        )

        result = env.run(stages=_stages()[:1], invoker=roadmap.shell_roadmap_invoker)

        assert result.outcome == OUTCOME_COMPLETED
        events = env.run_log_events()
        kinds = [e["event"] for e in events]
        assert kinds.count("claude_call_start") == 1
        assert kinds.count("claude_call_end") == 1
        assert kinds.index("claude_call_start") < kinds.index("claude_call_end")
        assert "claude_call_progress" not in kinds
        assert "claude_call_stall_suspected" not in kinds

    def test_internal_rate_limit_retry_yields_two_call_end_events_under_one_start(
        self, env: _Env, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # No real wait: ``wait_until_epoch`` is looked up on the
        # ``claude_errors`` module at call time (a free-variable reference
        # inside ``make_wait_seam``'s closure, not a frozen default), so
        # patching it here — rather than the ``_sleep``/``_clock`` kwargs
        # ``shell_roadmap_invoker`` never threads through — short-circuits
        # the real ~3600s fallback wait without touching the retry path.
        monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
        monkeypatch.setattr(
            claude_errors,
            "wait_until_epoch",
            lambda *a, **k: claude_errors.WaitUntilResult(
                action=claude_errors.WaitUntilAction.RETRY
            ),
        )
        monkeypatch.setattr(
            backend_runner.subprocess,
            "Popen",
            _fake_popen_factory(
                [
                    SimpleNamespace(
                        stdout="You've hit your limit. resets 3am",
                        stderr="",
                        returncode=1,
                    ),
                    SimpleNamespace(
                        stdout=_claude_stream_result(_domain_text()),
                        stderr="",
                        returncode=0,
                    ),
                ]
            ),
        )

        result = env.run(stages=_stages()[:1], invoker=roadmap.shell_roadmap_invoker)

        assert result.outcome == OUTCOME_COMPLETED
        events = env.run_log_events()
        starts = [e for e in events if e["event"] == "claude_call_start"]
        ends = [e for e in events if e["event"] == "claude_call_end"]
        assert len(starts) == 1
        assert starts[0]["attempt"] == 1
        assert len(ends) == 2
        assert [e["rc"] for e in ends] == [1, 0]
        # Both of claude_invoke's internal attempts land under the single
        # roadmap-level attempt that spawned them — bind_shell_sink overrides
        # every forwarded event's ``attempt`` to the bind-time value, so an
        # internal retry is invisible at the roadmap level (see
        # ``run_log.RunLogWriter.bind_shell_sink``).
        assert [e["attempt"] for e in ends] == [1, 1]

    def test_configured_timeout_is_recorded_as_invoke_failure(
        self, env: _Env, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A configured-timeout kill (the shared runner's monitor thread,
        driven by ``scoped_claude_timeout``) surfaces as an ordinary
        ``FAILURE_INVOKE`` with no same-budget retry — the direct
        replacement for the pre-runner-swap ``subprocess.TimeoutExpired``
        test."""
        from test_backend_runner import _NeverSilentProc

        monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
        proc = _NeverSilentProc()
        monkeypatch.setattr(backend_runner.subprocess, "Popen", lambda *a, **kw: proc)
        monkeypatch.setattr(backend_runner, "_PROGRESS_INTERVAL_S", 0.02)
        monkeypatch.setattr(backend_runner, "_KILL_AFTER_SILENCE_S", 10.0)
        monkeypatch.setattr(backend_runner, "_KILL_GRACE_S", 0.02)

        with shell.scoped_claude_timeout(0.06):
            result = env.run(
                stages=_stages()[:1],
                invoker=roadmap.shell_roadmap_invoker,
                max_stage_attempts=1,
            )

        assert result.outcome == OUTCOME_STAGE_EXHAUSTED
        assert result.failure_kind == FAILURE_INVOKE
        assert proc.terminate_called  # no same-budget retry inside claude_invoke

    def test_stage_call_emits_the_full_event_set_via_the_shared_writer(
        self, env: _Env, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Batch-authoring-observability plan step 7: a roadmap stage call
        now produces ``claude_stream_event``/``backend_spawn``/
        ``backend_termination`` rows through its existing, unedited call
        path — ``_run_stage``'s ``bind_shell_sink`` already bound the real
        writer; what changed is that ``claude_invoke`` now actually builds
        an observer from it. No change to ``plan_tool/roadmap.py`` itself."""
        from plan_tool.run_log import RunLogWriter

        monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
        monkeypatch.setattr(
            backend_runner.subprocess,
            "Popen",
            _fake_popen_factory(
                [
                    SimpleNamespace(
                        stdout=_claude_stream_result(_domain_text()),
                        stderr="",
                        returncode=0,
                    ),
                ]
            ),
        )
        writer = RunLogWriter.start(
            repo_root=env.repo_root,
            slug=SLUG,
            command="roadmap",
            argv=[],
        )

        result = env.run(
            stages=_stages()[:1],
            invoker=roadmap.shell_roadmap_invoker,
            run_logger=writer,
        )

        assert result.outcome == OUTCOME_COMPLETED
        kinds = {e["event"] for e in read_run_events(writer.log_path)}
        assert "claude_stream_event" in kinds
        assert "backend_spawn" in kinds
        assert "backend_termination" in kinds


class TestAttemptFailedEvent:
    """Every spent attempt names its failure kind — BACKLOG #217.

    ``gate_violations`` speaks for one kind of four, and ``failure_kind``
    reaches ``RoadmapResult`` only when the stage exhausts. So the case these
    pin is the *recovered* attempt, which is the common one.
    """

    @staticmethod
    def _kinds(env: _Env) -> list[str]:
        return [
            e["failure_kind"]
            for e in env.run_log_events()
            if e["event"] == "attempt_failed"
        ]

    def test_an_attempt_that_fails_and_then_recovers_still_names_its_kind(
        self, env: _Env
    ) -> None:
        # The whole point: the stage succeeds, so the result carries only the
        # good run and nothing else would record that an attempt was spent.
        invoker = _StubInvoker("no artifact in this reply", _domain_text())

        result = env.run(stages=_stages()[:1], invoker=invoker, max_stage_attempts=3)

        assert result.outcome == OUTCOME_COMPLETED
        assert result.failure_kind is None
        assert invoker.calls == 2
        assert self._kinds(env) == [FAILURE_PARSE]

    def test_a_reply_that_lifts_but_fails_the_parser_names_the_parse_kind(
        self, env: _Env
    ) -> None:
        # The *second* of two sites that both report ``parse``: this reply
        # clears ``_lift_artifact_text`` and dies in ``stage.parse``. Covered
        # separately because suppressing this site alone leaves the sibling
        # site's test green — verified by mutation.
        off_contract = "---\nentities: not-a-list\n---\n\n## Body\n\ntext\n"

        env.run(
            stages=_stages()[:1],
            invoker=_StubInvoker(off_contract),
            max_stage_attempts=2,
        )

        assert self._kinds(env) == [FAILURE_PARSE, FAILURE_PARSE]

    def test_a_clean_first_attempt_names_no_failure(self, env: _Env) -> None:
        env.run(
            stages=_stages(),
            invoker=_StubInvoker(
                _domain_text(), _constraints_text(), _components_text()
            ),
        )

        assert self._kinds(env) == []

    def test_an_unusable_reply_is_recorded_as_the_invoke_kind(self, env: _Env) -> None:
        env.run(
            stages=_stages()[:1],
            invoker=_StubInvoker((7, "backend refused")),
            max_stage_attempts=2,
        )

        assert self._kinds(env) == [FAILURE_INVOKE, FAILURE_INVOKE]

    def test_an_invented_feedback_row_is_recorded_as_its_own_kind(
        self, env: _Env
    ) -> None:
        # A first run has no reviewer, so any feedback row in a reply is invented.
        invented = _with_feedback(
            _feedback("fb-invented", request="the model made this up"),
        )

        env.run(
            stages=_stages()[:1],
            invoker=_StubInvoker(render_domain_artifact(invented)),
            max_stage_attempts=2,
        )

        assert self._kinds(env) == [
            FAILURE_AUTHORED_REVIEW_ROWS,
            FAILURE_AUTHORED_REVIEW_ROWS,
        ]

    def test_the_gates_kind_emits_this_event_as_well_as_its_violations(
        self, env: _Env
    ) -> None:
        # Deliberate redundancy: counting spent attempts by kind reads one
        # event type rather than unioning two.
        gate = _GateRecorder((_violation("never satisfied"),))

        env.run(
            stages=_stages(domain_gates=gate)[:1],
            invoker=_StubInvoker(_domain_text()),
            max_stage_attempts=2,
        )

        events = env.run_log_events()
        failed = [e for e in events if e["event"] == "attempt_failed"]
        gated = [e for e in events if e["event"] == "gate_violations"]
        assert [e["attempt"] for e in failed] == [1, 2]
        assert [e["attempt"] for e in gated] == [1, 2]
        assert {e["failure_kind"] for e in failed} == {FAILURE_GATES}

    def test_the_event_carries_the_phase_and_stage_of_its_attempt(
        self, env: _Env
    ) -> None:
        env.run(
            stages=_stages()[:1],
            invoker=_StubInvoker((7, "backend refused")),
            max_stage_attempts=1,
        )

        events = [e for e in env.run_log_events() if e["event"] == "attempt_failed"]
        assert len(events) == 1
        assert events[0]["phase"] == "stage-1-domain"
        assert events[0]["stage"] == 1
        assert events[0]["attempt"] == 1


class TestFreshStageModelFailureReceipts:
    """Rejected fresh replies remain diagnosable after a later accepted write."""

    @staticmethod
    def _receipts(env: _Env) -> list[dict[str, Any]]:
        return [
            event
            for event in env.run_log_events()
            if event["event"] == "model_failure_receipt"
        ]

    def test_recovered_fresh_invoke_failure_emits_a_redacted_receipt_before_the_successful_write(
        self, env: _Env
    ) -> None:
        rejected = "backend supplied a rejected reply"

        result = env.run(
            stages=_stages()[:1],
            invoker=_StubInvoker((7, rejected), _domain_text()),
            max_stage_attempts=2,
        )

        receipts = self._receipts(env)
        assert result.outcome == OUTCOME_COMPLETED
        assert env.held_stage_file(1).is_file()
        assert [(item["reason"], item["attempt"]) for item in receipts] == [
            (FAILURE_INVOKE, 1)
        ]
        assert receipts[0]["sidecar_disposition"] == "written"
        assert receipts[0]["response_bytes"] == len(rejected.encode("utf-8"))
        assert receipts[0]["response_sha256"] == hashlib.sha256(
            rejected.encode("utf-8")
        ).hexdigest()
        assert rejected not in json.dumps(receipts[0])
        assert rejected not in json.dumps(env.run_log_events())

    def test_recovered_fresh_empty_invoke_failure_records_no_response_without_raw_content(
        self, env: _Env
    ) -> None:
        result = env.run(
            stages=_stages()[:1], invoker=_StubInvoker("", _domain_text()), max_stage_attempts=2
        )

        receipts = self._receipts(env)
        assert result.outcome == OUTCOME_COMPLETED
        assert len(receipts) == 1
        assert receipts[0]["sidecar_disposition"] == "no-response"
        assert receipts[0]["response_bytes"] is None
        assert receipts[0]["response_sha256"] is None

    def test_recovered_fresh_whitespace_invoke_failure_retains_byte_identity(
        self, env: _Env
    ) -> None:
        rejected = " \n\t "
        env.run(
            stages=_stages()[:1], invoker=_StubInvoker(rejected, _domain_text()), max_stage_attempts=2
        )

        receipt = self._receipts(env)[0]
        assert receipt["sidecar_disposition"] == "written"
        assert receipt["response_bytes"] == len(rejected.encode("utf-8"))
        assert receipt["response_sha256"] == hashlib.sha256(rejected.encode("utf-8")).hexdigest()

    @pytest.mark.parametrize(
        "rejected",
        [
            "no artifact in this reply",
            "---\nentities: not-a-list\n---\n\n## Body\n\ntext\n",
        ],
        ids=["unliftable", "parser-rejected"],
    )
    def test_recovered_fresh_parse_failures_emit_receipts_before_the_successful_write(
        self, env: _Env, rejected: str
    ) -> None:
        result = env.run(
            stages=_stages()[:1], invoker=_StubInvoker(rejected, _domain_text()), max_stage_attempts=2
        )

        assert result.outcome == OUTCOME_COMPLETED
        assert [item["reason"] for item in self._receipts(env)] == [FAILURE_PARSE]

    def test_authored_review_rows_on_a_fresh_stage_emit_a_receipt_before_retry(
        self, env: _Env
    ) -> None:
        rejected = render_domain_artifact(_with_feedback(_feedback("fb-invented")))
        result = env.run(
            stages=_stages()[:1], invoker=_StubInvoker(rejected, _domain_text()), max_stage_attempts=2
        )

        assert result.outcome == OUTCOME_COMPLETED
        assert [item["reason"] for item in self._receipts(env)] == [
            FAILURE_AUTHORED_REVIEW_ROWS
        ]

    def test_fresh_gate_rejection_emits_not_retained_receipt(self, env: _Env) -> None:
        rejected = _domain_text()
        env.run(
            stages=_stages(domain_gates=_GateRecorder((_violation("do not copy this"),), ()))[:1],
            invoker=_StubInvoker(rejected, _domain_text()),
            max_stage_attempts=2,
        )

        receipts = self._receipts(env)
        assert [(item["reason"], item["sidecar_disposition"]) for item in receipts] == [
            (FAILURE_GATES, "not-retained")
        ]
        assert "sidecar_path" not in receipts[0]
        assert not list((env.repo_root / ".plan-tool" / "parse-failures").rglob("*.txt"))

    def test_fresh_sidecar_write_failure_does_not_block_a_recovered_retry(
        self, env: _Env, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fail_write(path: object, data: bytes) -> None:
            raise OSError("disk unavailable")

        monkeypatch.setattr(model_response_sidecar, "atomic_write_bytes", fail_write)

        result = env.run(
            stages=_stages()[:1], invoker=_StubInvoker("not an artifact", _domain_text()), max_stage_attempts=2
        )

        assert result.outcome == OUTCOME_COMPLETED
        assert self._receipts(env)[0]["sidecar_disposition"] == "write-failed"

    def test_clean_fresh_stage_emits_no_model_failure_receipt(self, env: _Env) -> None:
        env.run(stages=_stages()[:1], invoker=_StubInvoker(_domain_text()))

        assert self._receipts(env) == []


# --------------------------------------------------------------------------
# Inputs and seams
# --------------------------------------------------------------------------


def _refusing_writer_guard(error: Exception):
    """A ``roadmap_writer_guard`` stand-in whose acquisition raises ``error``."""

    @contextlib.contextmanager
    def guard(*_args: object, **_kwargs: object):
        raise error
        yield  # pragma: no cover

    return guard


class TestInputsAndSeams:
    def test_writer_guard_preflight_raises_roadmap_error(
        self, env: _Env, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The direct API normalizes every writer preflight failure to its
        documented exception family."""
        monkeypatch.setattr(
            roadmap,
            "roadmap_writer_guard",
            _refusing_writer_guard(roadmap.RoadmapWriterGuardError("stale writer token")),
        )

        with pytest.raises(roadmap.RoadmapError, match="stale writer token") as excinfo:
            env.run()

        assert isinstance(excinfo.value.__cause__, roadmap.RoadmapWriterGuardError)

    def test_preflight_writer_guard_refusal_has_one_owned_terminal_record(
        self, env: _Env, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Writer preflight refusal ends once without inventing a stage fact."""
        monkeypatch.setattr(
            roadmap,
            "roadmap_writer_guard",
            _refusing_writer_guard(roadmap.RoadmapWriterGuardError("stale writer token")),
        )

        with pytest.raises(roadmap.RoadmapError, match="stale writer token"):
            env.run()

        events = env.run_log_events()
        run_ends = [event for event in events if event["event"] == "run_end"]
        assert len(run_ends) == 1
        assert run_ends[0]["outcome"] == "preflight-refused"
        assert run_ends[0]["rc"] == 2
        assert not [event for event in events if event["event"] == "phase_start"]
        assert not (env.repo_root / ".plan-tool" / "runs" / SLUG / "in-flight.json").exists()

    def test_preflight_writer_validation_refusal_has_one_owned_terminal_record(
        self, env: _Env, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            roadmap,
            "roadmap_writer_guard",
            _refusing_writer_guard(
                roadmap.RoadmapRevisionPublishError("accepted head is corrupt")
            ),
        )

        with pytest.raises(roadmap.RoadmapError, match="accepted head is corrupt"):
            env.run()

        run_ends = [event for event in env.run_log_events() if event["event"] == "run_end"]
        assert len(run_ends) == 1
        assert run_ends[0]["outcome"] == "preflight-refused"
        assert run_ends[0]["rc"] == 2

    def test_caller_supplied_logger_is_not_ended_for_writer_guard_origin_paths(
        self, env: _Env, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Writer-origin classification never ends a caller-owned logger."""
        writer = RunLogWriter.start(
            repo_root=env.repo_root, slug=SLUG, command="roadmap", argv=[], flags={}
        )
        original_guard = roadmap.roadmap_writer_guard
        monkeypatch.setattr(
            roadmap,
            "roadmap_writer_guard",
            _refusing_writer_guard(roadmap.RoadmapWriterGuardError("stale writer token")),
        )
        try:
            with pytest.raises(roadmap.RoadmapError):
                env.run(run_logger=writer)
            monkeypatch.setattr(roadmap, "roadmap_writer_guard", original_guard)

            def stale_head_read(**_kwargs: Any) -> None:
                raise roadmap.RoadmapWriterGuardError("stale writer token")

            monkeypatch.setattr(roadmap, "load_accepted_head", stale_head_read)
            with pytest.raises(roadmap.RoadmapRunStartedWriterGuardError):
                env.run(
                    run_logger=writer,
                    stages=_stages()[:1],
                    invoker=_StubInvoker(_domain_text()),
                )
            assert not [
                event for event in read_run_events(writer.log_path) if event["event"] == "run_end"
            ]
        finally:
            writer.run_end(outcome="test-complete", rc=0)

    @pytest.mark.parametrize(
        "call",
        [
            pytest.param(
                lambda env: roadmap.accept_roadmap_seed(
                    SLUG,
                    "plan-x",
                    repo_root=env.repo_root,
                    plans_dir=env.plans_dir,
                ),
                id="accept_roadmap_seed",
            ),
            pytest.param(
                lambda env: roadmap.apply_roadmap_seeds(
                    SLUG,
                    repo_root=env.repo_root,
                    plans_dir=env.plans_dir,
                    allow_apply=True,
                ),
                id="apply_roadmap_seeds",
            ),
            pytest.param(
                lambda env: roadmap.materialize_plan_seed(
                    SLUG,
                    "plan-x",
                    repo_root=env.repo_root,
                    plans_dir=env.plans_dir,
                ),
                id="materialize_plan_seed",
            ),
            pytest.param(
                lambda env: roadmap.materialize_and_diff_one_plan(
                    SLUG,
                    _PLAN_ORDER,
                    repo_root=env.repo_root,
                    plans_dir=env.plans_dir,
                ),
                id="materialize_and_diff_one_plan",
            ),
            pytest.param(
                lambda env: roadmap.refresh_roadmap_seeds(
                    SLUG, repo_root=env.repo_root, plans_dir=env.plans_dir
                ),
                id="refresh_roadmap_seeds",
            ),
        ],
    )
    def test_every_direct_api_writer_guard_preflight_normalizes_the_same_way(
        self, env: _Env, monkeypatch: pytest.MonkeyPatch, call
    ) -> None:
        """Every direct-API entry point that calls
        writer-token check before doing its own work must
        normalize a stale/contended token to ``RoadmapError`` the same way,
        not leak the raw ``RoadmapWriterGuardError``."""

        def stale_writer_token(*_args: object, **_kwargs: object) -> None:
            raise roadmap.RoadmapWriterGuardError("stale writer token")

        monkeypatch.setattr(roadmap, "require_roadmap_writer_token", stale_writer_token)
        # apply_roadmap_seeds's fence-validity preflight
        # (_reject_unmatched_operator_draft_fences) reads the accepted plans
        # artifact before the writer-guard check runs, so it needs a published
        # head to reach that check at all — the other entries have no such precondition.
        env.publish_accepted()

        with pytest.raises(
            roadmap.RoadmapError, match="stale writer token"
        ) as excinfo:
            call(env)

        assert isinstance(excinfo.value.__cause__, roadmap.RoadmapWriterGuardError)

    def test_apply_roadmap_seeds_inner_token_reuse_guard_also_normalizes(
        self, env: _Env
    ) -> None:
        """``_apply_roadmap_seeds`` re-validates its caller's writer token
        with a second, independent guard call (``require_roadmap_writer_token``)
        after the outer ``apply_roadmap_seeds`` preflight already passed --
        catching a token that went stale between the two checks. That inner
        call must normalize to ``RoadmapError`` too, not just the outer one.
        No monkeypatch is needed: an inactive token (its owning ``with``
        block already exited) makes the real guard raise on its own."""
        with roadmap._roadmap_writer_owner(env.plans_dir, SLUG) as writer_token:
            pass  # deactivate the token by leaving its owning scope

        with pytest.raises(
            roadmap.RoadmapError, match="writer token"
        ) as excinfo:
            roadmap._apply_roadmap_seeds(
                SLUG,
                repo_root=env.repo_root,
                plans_dir=env.plans_dir,
                allow_apply=True,
                yes=False,
                prompt_fn=None,
                writer_token=writer_token,
            )

        assert isinstance(
            excinfo.value.__cause__, roadmap.RoadmapWriterGuardError
        )

    def test_a_first_run_needs_a_brief_path(self, env: _Env) -> None:
        invoker = _StubInvoker(_domain_text())

        with pytest.raises(RoadmapError, match="no concept brief was given"):
            roadmap.run_roadmap(
                SLUG,
                repo_root=env.repo_root,
                plans_dir=env.plans_dir,
                brief_path=None,
                stages=_stages()[:1],
                invoker=invoker,
            )

        assert invoker.calls == 0

    def test_exhausted_first_stage_leaves_no_brief_record_and_no_top_level_file(
        self, env: _Env
    ) -> None:
        env.run(
            stages=_stages()[:1],
            invoker=_StubInvoker("not an artifact"),
            max_stage_attempts=1,
        )

        assert not _source_json_path(env.plans_dir).exists()
        assert not env.domain_file.exists()

    def test_missing_brief_raises_naming_the_path(self, env: _Env) -> None:
        missing = env.repo_root / "no-such-brief.md"
        invoker = _StubInvoker(_domain_text())

        with pytest.raises(RoadmapError) as excinfo:
            roadmap.run_roadmap(
                SLUG,
                repo_root=env.repo_root,
                plans_dir=env.plans_dir,
                brief_path=missing,
                stages=_stages(),
                invoker=invoker,
            )

        assert str(missing) in str(excinfo.value)
        assert invoker.calls == 0

    def test_non_utf8_brief_is_a_brief_read_preflight_failure(self, env: _Env) -> None:
        env.brief_path.write_bytes(b"\xff")
        invoker = _StubInvoker(_domain_text())
        runs_dir = env.repo_root / ".plan-tool" / "runs" / SLUG
        before = set(runs_dir.glob("*.jsonl")) if runs_dir.exists() else set()

        with pytest.raises(RoadmapError, match="brief is not readable"):
            roadmap.run_roadmap(
                SLUG,
                repo_root=env.repo_root,
                plans_dir=env.plans_dir,
                brief_path=env.brief_path,
                stages=_stages()[:1],
                invoker=invoker,
            )

        assert invoker.calls == 0
        written_logs = set(runs_dir.glob("*.jsonl")) - before
        assert len(written_logs) == 1
        assert [
            event["check"]
            for event in read_run_events(written_logs.pop())
            if event["event"] == "roadmap_preflight_failed"
        ] == ["brief_read"]

    def test_brief_text_reaches_the_stage_prompt(self, env: _Env) -> None:
        env.brief_path.write_text("MARKER-7Q the concept\n", encoding="utf-8")
        invoker = _StubInvoker(_domain_text())

        env.run(stages=_stages()[:1], invoker=invoker)

        assert "MARKER-7Q" in invoker.prompts[0]

    def test_missing_prompt_template_raises_naming_the_expected_path(
        self, env: _Env
    ) -> None:
        stages = _stages(prompt_names=("nope.md", "stage-2.md"))

        with pytest.raises(RoadmapError) as excinfo:
            env.run(stages=stages, invoker=_never_called)

        assert str(env.prompts / "nope.md") in str(excinfo.value)

    def test_default_invoker_is_the_shell_seam(self) -> None:
        default = inspect.signature(roadmap.run_roadmap).parameters["invoker"].default

        assert default is roadmap.shell_roadmap_invoker

    def test_run_is_non_interactive(self) -> None:
        for function in (roadmap._run_stage, roadmap._run_roadmap):
            source = inspect.getsource(function)

            assert "input(" not in source
            assert "isatty" not in source


# --------------------------------------------------------------------------
# Failure-kind reporting
# --------------------------------------------------------------------------


class TestFailureKindRecording:
    def test_exhaustion_by_gates_carries_the_gates_failure_kind(
        self, env: _Env
    ) -> None:
        gate = _GateRecorder((_violation("never satisfied"),))

        result = env.run(
            stages=_stages(domain_gates=gate)[:1],
            invoker=_StubInvoker(_domain_text()),
            max_stage_attempts=1,
        )

        assert result.failure_kind == FAILURE_GATES
        assert [v.message for v in result.violations] == ["never satisfied"]

    def test_exhaustion_by_invoke_carries_the_invoke_kind_and_diagnostic(
        self, env: _Env
    ) -> None:
        result = env.run(
            stages=_stages()[:1],
            invoker=_StubInvoker((7, "backend refused: quota exhausted")),
            max_stage_attempts=2,
        )

        assert result.failure_kind == FAILURE_INVOKE
        assert result.failure_rc == 7
        assert "backend refused" in (result.failure_detail or "")
        assert result.violations == ()

    def test_exhaustion_by_parse_carries_the_parse_kind_and_reply_head(
        self, env: _Env
    ) -> None:
        result = env.run(
            stages=_stages()[:1],
            invoker=_StubInvoker("I cannot produce that artifact."),
            max_stage_attempts=2,
        )

        assert result.failure_kind == FAILURE_PARSE
        assert "I cannot produce that artifact." in (result.failure_detail or "")
        assert result.failure_rc is None

    def test_gate_exhaustion_has_no_invoke_diagnostic(self, env: _Env) -> None:
        gate = _GateRecorder((_violation("never satisfied"),))

        result = env.run(
            stages=_stages(domain_gates=gate)[:1],
            invoker=_StubInvoker(_domain_text()),
            max_stage_attempts=1,
        )

        assert result.failure_rc is None
        assert result.failure_detail is None

    def test_the_orchestrator_renders_no_operator_advice(
        self, env: _Env, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``run_roadmap`` reports facts as data and prints nothing.

        Rendering belongs to ``cli.roadmap_cmd``; a second copy here is what
        made one run tell an operator the same thing twice, on two streams.
        """
        env.run(
            stages=_stages(),
            invoker=_StubInvoker(
                _domain_text(), _constraints_text(), _components_text()
            ),
        )

        captured = capsys.readouterr()
        assert captured.err == ""
        assert captured.out == ""


# --------------------------------------------------------------------------
# Plans fixtures and side-output stages
# --------------------------------------------------------------------------


_PLANS_DECISION = DecisionRow(
    id="decision-4",
    chosen_option="Ship auth as a cross-cutting plan.",
    rejected_alternatives=(
        RejectedAlternative(
            option="Fold auth into every slice.",
            reason="Duplicates the same plumbing five times.",
        ),
    ),
    rationale="One auth plan keeps the hand-off readable.",
    anchor="plan-auth",
    status=DecisionStatus.PENDING,
)

_PLAN_ORDER = PlanRow(
    id="plan-order-core",
    title="Order core",
    disposition=PlanDisposition.KEEP,
    component_ids=("component-checkout",),
    draft_seed_path="plan-seed-drafts/order-core.md",
    sizing_rationale="One component, one plan.",
    intent="Let checkout create an order before authentication is required.",
    non_goals=("Shared authentication plumbing for all delivery slices.",),
)

_PLAN_AUTH = PlanRow(
    id="plan-auth",
    title="Auth plumbing",
    disposition=PlanDisposition.CROSS_CUTTING,
    component_ids=(),
    draft_seed_path="plan-seed-drafts/auth.md",
    sizing_rationale="Shared across slices.",
    intent="Provide authentication boundaries shared by every delivery slice.",
    non_goals=("Checkout-specific order creation behavior.",),
)

_PLANS_ASSUMPTION = AssumptionRow(
    id="assumption-1",
    statement="Checkout stays in plan-order-core until auth lands.",
    consuming_plan_ids=("plan-order-core",),
)

_PLANS_ORDERING = (
    OrderingEntry(plan_id="plan-auth"),
    OrderingEntry(
        plan_id="plan-order-core",
        depends_on=("plan-auth",),
    ),
)


def _plans(
    *,
    plans: tuple[PlanRow, ...] = (_PLAN_ORDER, _PLAN_AUTH),
    ordering=_PLANS_ORDERING,
    assumptions=(_PLANS_ASSUMPTION,),
    decisions=(_PLANS_DECISION,),
    body: Optional[str] = None,
    feedback: tuple[FeedbackRow, ...] = (),
) -> PlansArtifact:
    design_rows = (*plans, *assumptions, *decisions)
    if body is None:
        body = "\n".join(
            (
                "# Plans",
                "",
                " ".join(f"`{row.id}`" for row in design_rows),
                "",
            )
        )
    return PlansArtifact(
        plans=plans,
        ordering=ordering,
        assumptions=assumptions,
        decisions=decisions,
        body=body,
        feedback=feedback,
    )


def _plans_artifact_text(**kwargs: Any) -> str:
    return render_plans_artifact(_plans(**kwargs))


def _seed_text(
    *,
    components: tuple[str, ...] = ("component-checkout",),
    cross_cutting: bool = False,
    marker: str = "",
) -> str:
    lines = ["---"]
    if components:
        lines.append("roadmap_components:")
        lines.extend(f"  - {component_id}" for component_id in components)
    else:
        lines.append("roadmap_components: []")
    if cross_cutting:
        lines.append("cross_cutting: true")
    lines.extend(["---", "", "# Seed body", ""])
    if marker:
        lines.append(marker)
        lines.append("")
    lines.extend(
        [
            "## Risks",
            "",
            "- A risk the accepted roadmap already states.",
            "",
            "## References",
            "",
            f"- `{DOMAIN_FILENAME}`",
            f"- `{CONSTRAINTS_FILENAME}`",
            f"- `{COMPONENTS_FILENAME}`",
            f"- `{PLANS_FILENAME}`",
            "",
        ]
    )
    return "\n".join(lines)


def _plans_text(**kwargs: Any) -> str:
    return render_plans_artifact(_plans(**kwargs))


def _loaded_artifact(stage: RoadmapStage, artifact: Any) -> roadmap._LoadedArtifact:
    text = stage.render(artifact)
    return roadmap._LoadedArtifact(
        stage=stage, path=Path(), text=text, artifact=artifact
    )


def _plans_upstream_loaded() -> tuple[roadmap._LoadedArtifact, ...]:
    return (
        _loaded_artifact(_domain_stage(), _domain()),
        _loaded_artifact(_constraints_stage(), _constraints()),
        _loaded_artifact(_components_stage(), _components()),
    )


def _plans_run_table(*, plans_gates: Any = _clean_gates) -> tuple[RoadmapStage, ...]:
    if plans_gates is _clean_gates:
        return roadmap.STAGES
    return (*roadmap.STAGES[:3], replace(roadmap.STAGES[3], gates=plans_gates))


def _ensure_plans_prompt(env: _Env) -> None:
    path = env.prompts / "roadmap-plans.md"
    if not path.is_file():
        path.write_text(
            "Plans for ${slug}\n\nBRIEF:\n${brief}\n\n"
            "DOMAIN:\n${domain_artifact}\n\n"
            "CONSTRAINTS:\n${constraints_artifact}\n\n"
            "COMPONENTS:\n${components_artifact}\n",
            encoding="utf-8",
        )


def _seed_plans_upstream(env: _Env) -> None:
    env.write_domain()
    env.write_constraints()
    env.write_components()
    _ensure_plans_prompt(env)


def _record_order_seed_published(env: "_Env") -> None:
    """Record the order seed as published, the only proof the tool wrote its copy."""
    state_path = seed_state_path(roadmap_dir(env.plans_dir, SLUG))
    write_seed_state(
        state_path,
        {
            "version": 1,
            "seeds": {
                _PLAN_ORDER.id: {
                    "draft_seed_path": _PLAN_ORDER.draft_seed_path,
                    "status": "current",
                    "digest": "old-digest",
                    "published": True,
                }
            },
        },
    )


def _prepare_seed_materialization(env: _Env, *, plans: Optional[str] = None) -> None:
    _ensure_plans_prompt(env)
    env.publish_accepted(plans=plans)
    (env.prompts / "roadmap-seed.md").write_text(
        "Seed ${slug} / ${plan_id}\n${domain_artifact}\n"
        "${constraints_artifact}\n${components_artifact}\n${plans_artifact}\n",
        encoding="utf-8",
    )


def _stacked(
    env: _Env,
    text: str,
    *,
    plan: PlanRow = _PLAN_ORDER,
    constraints: Optional[ConstraintsArtifact] = None,
    components: Optional[ComponentsArtifact] = None,
) -> str:
    """``text`` as materialization writes it: the tool's ``## Stack`` section applied."""
    constraints = constraints or _constraints()
    components = components or _components()
    version = load_accepted_version(plans_dir=env.plans_dir, slug=SLUG)
    assert version is not None
    section = roadmap._render_stack_section(
        version_id=version.record.version_id,
        hosting=constraints.hosting,
        stores=components.stores,
        components=components.components,
        stack=constraints.stack,
        plan=plan,
    )
    return roadmap._replace_stack_section(text, section)


def _written_draft(env: _Env, plan: PlanRow = _PLAN_ORDER) -> str:
    return resolve_draft_seed_path(env.plans_dir, SLUG, plan.draft_seed_path).read_text(
        encoding="utf-8"
    )


def _stack_h2_count(text: str) -> int:
    return len(re.findall(r"^## Stack[ \t]*$", text, flags=re.MULTILINE))


def _materialize(env: _Env, invoker: _StubInvoker, **kwargs: Any):
    return roadmap.materialize_plan_seed(
        SLUG,
        _PLAN_ORDER.id,
        repo_root=env.repo_root,
        plans_dir=env.plans_dir,
        invoker=invoker,
        **kwargs,
    )


def _materialization_observer(
    env: _Env, *, plan_id: str = _PLAN_ORDER.id
) -> tuple[RunLogWriter, Any]:
    writer = RunLogWriter.start(
        repo_root=env.repo_root,
        slug=SLUG,
        command="roadmap",
        argv=[],
        context={
            "roadmap_action": "materialize",
            "roadmap_slug": SLUG,
            "requested_plan_id": plan_id,
            "active_plan_id": plan_id,
            "seed_attempt": None,
            "backend_attempt": None,
            "backend_child_started": False,
        },
    )
    return writer, roadmap._MaterializationObserver(
        writer,
        plan_id=plan_id,
        phase=f"seed-materialize:{plan_id}",
    )


def _seed_prompt_text() -> str:
    return (prompts_dir() / "roadmap-seed.md").read_text(encoding="utf-8")


_STORE_OTHER = StoreRow(id="store-other", category="object", sharing="silo")
_COMPONENT_OTHER = ComponentRow(
    id="component-other",
    name="Other",
    entity_ids=("order",),
    pattern_ids=("pattern-checkout",),
    store_ids=("store-other", "store-checkout"),
)


class TestMaterializedStackSection:
    def test_materialized_seed_has_stack_section_naming_the_accepted_version_id(
        self, env: _Env
    ) -> None:
        _prepare_seed_materialization(env)

        _materialize(env, _StubInvoker(_seed_text()))

        version = load_accepted_version(plans_dir=env.plans_dir, slug=SLUG)
        assert version is not None
        draft = _written_draft(env)
        assert _stack_h2_count(draft) == 1
        assert version.record.version_id in draft

    def test_stack_lists_every_hosting_row_with_id_facet_value_product(
        self, env: _Env
    ) -> None:
        hosting = (
            HostingRow(id="hosting-compute", facet="compute", value="per-request", product="lambda"),
            HostingRow(id="hosting-model", facet="model", value="pool"),
            HostingRow(id="hosting-topology", facet="topology", value="single-unit"),
        )
        _prepare_seed_materialization(env)
        env.publish_accepted(
            constraints=render_constraints_artifact(replace(_constraints(), hosting=hosting))
        )

        _materialize(env, _StubInvoker(_seed_text()))

        draft = _written_draft(env)
        for row in hosting:
            assert f"`{row.id}`" in draft
            assert f"facet: {row.facet}" in draft
            assert f"value: {row.value}" in draft
        # `product` is legal on a compute row only; the others render no product of their own.
        assert "product: lambda" in draft

    def test_stack_lists_only_stores_named_by_the_plans_components(self, env: _Env) -> None:
        components = replace(
            _components(),
            components=(*_components().components, _COMPONENT_OTHER),
            stores=(*_components().stores, _STORE_OTHER),
        )
        _prepare_seed_materialization(env)
        env.publish_accepted(components=render_components_artifact(components))
        owning_checkout_only = _stacked(env, _seed_text(), components=components)

        _materialize(env, _StubInvoker(_seed_text()))

        draft = _written_draft(env)
        # `store-other` is reachable only through a component the plan row does not own.
        assert "`store-other`" not in draft
        assert draft.count("`store-checkout`") == 1
        assert draft == owning_checkout_only

    def test_row_without_product_states_the_product_is_left_open(self, env: _Env) -> None:
        _prepare_seed_materialization(env)

        _materialize(env, _StubInvoker(_seed_text()))

        draft = _written_draft(env)
        stack = draft[draft.index("## Stack") : draft.index("## References")]
        assert roadmap._OPEN_PRODUCT_TEXT in stack
        assert "None" not in stack
        assert "product: \n" not in stack and "product: ;" not in stack
        # Three default hosting rows and one default store row, none with a product.
        assert stack.count(roadmap._OPEN_PRODUCT_TEXT) == 4

    def test_changed_accepted_row_changes_the_rendered_stack_on_rematerialization(
        self, env: _Env
    ) -> None:
        _prepare_seed_materialization(env)
        _materialize(env, _StubInvoker(_seed_text()))
        first = _written_draft(env)

        _materialize(env, _StubInvoker(_seed_text()))
        assert _written_draft(env) == first, "an unchanged roadmap rematerializes identically"

        changed = replace(
            _constraints(),
            hosting=(HostingRow(id="hosting-compute", facet="compute", value="always-on"),),
        )
        advance_accepted_head(
            env.plans_dir,
            SLUG,
            (
                _domain_text(),
                render_constraints_artifact(changed),
                _components_text(),
                _plans_artifact_text(),
            ),
        )
        _materialize(env, _StubInvoker(_seed_text()))

        second = _written_draft(env)
        assert second != first
        assert "value: always-on" in second
        assert "value: per-request" not in second
        state = load_seed_state(seed_state_path(roadmap_dir(env.plans_dir, SLUG)))
        assert state["seeds"][_PLAN_ORDER.id]["digest"] == digest_text(second)

    def test_cross_cutting_plan_stack_includes_its_listed_components_stores(
        self, env: _Env
    ) -> None:
        _prepare_seed_materialization(env)
        env.publish_accepted()
        version = load_accepted_version(plans_dir=env.plans_dir, slug=SLUG)
        assert version is not None
        cross_cutting = replace(_PLAN_AUTH, component_ids=("component-checkout",))

        section = roadmap._render_stack_section(
            version_id=version.record.version_id,
            hosting=_constraints().hosting,
            stores=_components().stores,
            components=_components().components,
            stack=_constraints().stack,
            plan=cross_cutting,
        )

        assert "`store-checkout`" in section

    def test_plan_with_no_components_renders_hosting_rows_alone(self, env: _Env) -> None:
        _prepare_seed_materialization(env)

        result = roadmap.materialize_plan_seed(
            SLUG,
            _PLAN_AUTH.id,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            invoker=_StubInvoker(_seed_text(components=(), cross_cutting=True)),
        )

        assert result.outcome == roadmap.SEED_MATERIALIZE_OUTCOME_APPLIED
        draft = _written_draft(env, _PLAN_AUTH)
        assert "`hosting-compute`" in draft
        assert "`store-checkout`" not in draft

    def test_roadmap_with_no_hosting_or_stores_still_emits_an_explicit_stack_section(
        self, env: _Env
    ) -> None:
        _prepare_seed_materialization(env)
        env.publish_accepted(
            constraints=render_constraints_artifact(replace(_constraints(), hosting=())),
            components=render_components_artifact(replace(_components(), stores=())),
        )

        _materialize(env, _StubInvoker(_seed_text()))

        draft = _written_draft(env)
        assert _stack_h2_count(draft) == 1
        assert "lists no hosting rows" in draft
        assert "name no store" in draft

    def test_model_authored_stack_section_is_replaced_not_kept(self, env: _Env) -> None:
        _prepare_seed_materialization(env)
        authored = _seed_text().replace(
            "## References",
            "## Stack\n\nWRONG-ONE: use mainframes\n\n## Stack\n\nWRONG-TWO\n\n## References",
        )

        _materialize(env, _StubInvoker(authored))

        draft = _written_draft(env)
        assert "WRONG-ONE" not in draft and "WRONG-TWO" not in draft
        assert _stack_h2_count(draft) == 1
        assert draft == _stacked(env, _seed_text())

    def test_lookalike_stack_headings_and_fenced_stack_text_are_not_replaced(
        self, env: _Env
    ) -> None:
        _prepare_seed_materialization(env)
        lookalikes = (
            "## Stacked\n\nKEEP-STACKED\n\n"
            "### Stack\n\nKEEP-H3\n\n"
            "```\n## Stack\nKEEP-BACKTICK-FENCE\n```\n\n"
            "~~~\n## Stack\nKEEP-TILDE-FENCE\n~~~\n\n"
        )
        authored = _seed_text().replace(
            "## References", lookalikes + "## Stack\n\nREPLACED\n\n## References"
        )

        _materialize(env, _StubInvoker(authored))

        draft = _written_draft(env)
        for kept in ("## Stacked", "### Stack\n", "KEEP-BACKTICK-FENCE", "KEEP-TILDE-FENCE"):
            assert kept in draft
        assert "REPLACED" not in draft
        # Only the tool's own heading counts outside a fence.
        assert len(h2_section_spans(draft, "stack")) == 1

    @pytest.mark.parametrize(
        "heading",
        ["## stack", "## STACK", "##  Stack", "##\tStack", "## Stack ##", "## Stack   "],
        ids=["lowercase", "uppercase", "extra-space", "tab", "closing-hashes", "trailing-space"],
    )
    def test_model_authored_stack_heading_variants_are_replaced_so_create_reads_the_tools(
        self, env: _Env, heading: str
    ) -> None:
        # The replacer and `create` must recognize a heading by one rule: a variant
        # `create` would read as the plan's `## Stack` must not survive the replacement.
        _prepare_seed_materialization(env)
        authored = _seed_text().replace(
            "## References", f"{heading}\n\nMODEL-INVENTED-STACK\n\n## References"
        )

        _materialize(env, _StubInvoker(authored))

        draft = _written_draft(env)
        assert "MODEL-INVENTED-STACK" not in draft
        assert len(h2_section_spans(draft, "stack")) == 1
        assert "MODEL-INVENTED-STACK" not in extract_h2_sections(draft, ignore_fenced_code=True)["stack"]

    def test_replaced_model_stack_section_ends_at_the_next_h1_like_the_readers_do(
        self, env: _Env
    ) -> None:
        _prepare_seed_materialization(env)
        authored = _seed_text().replace(
            "## References",
            "## Stack\n\nMODEL-STACK\n\n# Notes\n\nKEEP-NOTES-BODY\n\n## References",
        )

        _materialize(env, _StubInvoker(authored))

        draft = _written_draft(env)
        assert "MODEL-STACK" not in draft
        assert "KEEP-NOTES-BODY" in draft

    def test_four_space_indented_fence_does_not_hide_a_model_stack_heading(
        self, env: _Env
    ) -> None:
        # An indented fence-looking line is not a fence under the reader's rules, so the
        # model's real `## Stack` after it must still be replaced.
        _prepare_seed_materialization(env)
        authored = _seed_text().replace(
            "## References",
            "    ```\n\n## Stack\n\nMODEL-AFTER-INDENTED-FENCE\n\n## References",
        )

        _materialize(env, _StubInvoker(authored))

        draft = _written_draft(env)
        assert "MODEL-AFTER-INDENTED-FENCE" not in draft
        assert len(h2_section_spans(draft, "stack")) == 1

    def test_a_stack_comment_in_the_frontmatter_leaves_the_frontmatter_untouched(self) -> None:
        # A column-0 `##` YAML comment is legal in frontmatter and is not a section; the
        # replacer must neither remove it nor let it swallow the closing fence.
        frontmatter = "---\nroadmap_components:\n  - c1\n## Stack\n---\n"
        draft = (
            frontmatter + "\n# Seed\n\n## Outcome\n\nx\n\n## Stack\n\nMODEL\n\n## References\n\n- a\n"
        )

        out = roadmap._replace_stack_section(draft, "## Stack\n\nTOOL\n")

        assert out.startswith(frontmatter)
        assert "MODEL" not in out
        assert len(h2_section_spans(roadmap._strip_frontmatter(out), "stack")) == 1

    def test_a_fence_run_in_the_frontmatter_does_not_hide_the_bodys_stack_section(self) -> None:
        frontmatter = "---\nnote: |\n  text\n```\n---\n"
        draft = frontmatter + "\n## Outcome\n\nx\n\n## Stack\n\nMODEL\n\n## References\n\n- a\n"

        out = roadmap._replace_stack_section(draft, "## Stack\n\nTOOL\n")

        assert out.startswith(frontmatter)
        assert "MODEL" not in out
        assert out.index("TOOL") < out.index("## References")

    def test_product_text_renders_on_one_line_and_blank_product_reads_as_open(self) -> None:
        stores = (
            SimpleNamespace(id="store-a", category="relational", sharing="pool",
                            product="Postgres\n## Notes\n  16"),
            SimpleNamespace(id="store-b", category="document", sharing="silo", product="   "),
        )
        component = SimpleNamespace(id="c", store_ids=("store-a", "store-b"))
        plan = SimpleNamespace(component_ids=("c",))

        section = roadmap._render_stack_section(
            version_id="v1",
            hosting=(),
            stores=stores,
            components=(component,),
            stack=(),
            plan=plan,
        )

        assert "product: Postgres ## Notes 16" in section
        assert "\n## Notes" not in section
        assert "`store-b` — category: document; sharing: silo; product: product left open" in section

    def test_promoted_seed_rewritten_after_materialization_carries_the_stack(
        self, env: _Env
    ) -> None:
        _prepare_seed_materialization(env)
        _record_order_seed_published(env)
        promoted = roadmap.resolve_plan_seed_dest(env.repo_root / "plan-seeds", _PLAN_ORDER.id)
        promoted.parent.mkdir(parents=True, exist_ok=True)
        promoted.write_text("old promoted seed\n", encoding="utf-8")

        _materialize(env, _StubInvoker(_seed_text()))

        body = promoted.read_text(encoding="utf-8")
        assert _stack_h2_count(body) == 1
        assert "`hosting-compute`" in body
        # Both overwrite paths write the text that carries the technology-stack part.
        assert "### Technology stack" in body
        assert "### Technology stack" in _written_draft(env)

    def test_rendered_stack_passes_draft_seed_content_validation(self, env: _Env) -> None:
        _prepare_seed_materialization(env)

        _materialize(env, _StubInvoker(_seed_text()))

        assert roadmap_gates.validate_draft_seed_content(
            _written_draft(env), plan=_PLAN_ORDER
        ) == []


def _render_stack_only(stack: Any) -> str:
    return roadmap._render_stack_section(
        version_id="v1", hosting=(), stores=(), components=(), stack=stack, plan=_PLAN_ORDER
    )


class TestSeedTechnologyStackLines:
    def test_seed_stack_section_renders_chosen_stack_rows_verbatim(self) -> None:
        section = _render_stack_only(
            (StackRow(id="stack-store-engine", concern="store-engine", choice="Postgres 16"),)
        )

        assert "- `stack-store-engine` — concern: store-engine; choice: Postgres 16" in section

    def test_seed_stack_section_renders_open_concern_as_open_not_a_vendor(self) -> None:
        section = _render_stack_only(
            (StackRow(id="stack-platform", concern="platform", open=True),)
        )

        assert (
            f"- `stack-platform` — concern: platform; {roadmap._STACK_OPEN_TEXT}" in section
        )
        assert "choice:" not in section

    def test_seed_stack_section_says_stack_not_recorded_when_collection_absent(self) -> None:
        section = _render_stack_only(None)

        assert roadmap._STACK_NOT_RECORDED_TEXT in section
        assert "choice:" not in section

    def test_seed_stack_section_distinguishes_present_empty_from_not_recorded(self) -> None:
        empty = _render_stack_only(())
        absent = _render_stack_only(None)

        assert empty != absent
        assert roadmap._STACK_EMPTY_TEXT in empty
        assert roadmap._STACK_NOT_RECORDED_TEXT not in empty

    def test_seed_stack_section_keeps_source_order_and_is_deterministic(self) -> None:
        rows = (
            StackRow(id="stack-z", concern="platform", open=True),
            StackRow(id="stack-a", concern="language-runtime", choice="Python 3.13"),
        )

        first = _render_stack_only(rows)

        assert first == _render_stack_only(rows)
        assert first.index("`stack-z`") < first.index("`stack-a`")

    def test_seed_stack_lines_sit_inside_the_single_stack_heading(self) -> None:
        section = _render_stack_only((StackRow(id="stack-p", concern="platform", open=True),))

        assert _stack_h2_count(section) == 1
        assert section.index("### Hosting") < section.index("### Stores")
        assert section.index("### Stores") < section.index("### Technology stack")
        assert section.index("### Technology stack") < section.index("`stack-p`")

    def test_draft_seed_materialization_writes_the_open_stack_concern_as_open(
        self, env: _Env
    ) -> None:
        _prepare_seed_materialization(env)
        env.publish_accepted(constraints=_integration_constraints_text())

        _materialize(env, _StubInvoker(_seed_text()))

        draft = _written_draft(env)
        assert _stack_h2_count(draft) == 1
        assert f"concern: platform; {roadmap._STACK_OPEN_TEXT}" in draft
        assert f"concern: language-runtime; {roadmap._STACK_OPEN_TEXT}" in draft
        assert "concern: store-engine; choice: relational store" in draft


class TestSeedPromptTemplate:
    def test_seed_prompt_preserves_selected_row_responsibilities_and_source_references(self) -> None:
        text = _flattened(_seed_prompt_text())
        for instruction in (
            "shared production", "consumer integration", "required handoffs",
            "contribution to eventual acceptance", "source ids and artifact references",
            "accepted narrative alongside the structured rows",
            "rather than collapsing distinct routes into a generic component brief",
            "do not invent missing assignments",
        ):
            assert instruction in text

    def test_seed_prompt_keeps_sibling_prerequisites_outside_selected_row_scope(self) -> None:
        text = _flattened(_seed_prompt_text())
        assert "`ordering.depends_on` and relevant inter-plan assumptions" in text
        assert "distinguish what this row delivers from what another row supplies" in text
        assert "do not repartition accepted rows or implement a sibling prerequisite" in text

    def test_seed_prompt_preserves_business_delivery_when_prerequisites_are_missing(self) -> None:
        text = _flattened(_seed_prompt_text())

        assert "preserve the named producer and consumer operations" in text
        assert "do not turn a required production or update operation into only a check" in text
        assert "carry that uncertainty explicitly without assigning new scope" in text
        assert "missing prerequisite implementation blocks eventual execution or acceptance" in text
        assert "does not replace this row's implementation outcome" in text
        assert "prerequisite-verification-only outcome" in text

    def test_seed_prompt_requests_testing_and_acceptance_criteria_as_output_sections(self) -> None:
        sections = re.findall(r"^- `([^`]+)`$", _seed_prompt_text(), re.MULTILINE)
        assert "Testing" in sections
        assert "Acceptance criteria" in sections
        assert "Verification" not in sections

    def test_seed_prompt_preserves_required_observed_proof_without_authorizing_execution(self) -> None:
        text = _flattened(_seed_prompt_text())
        assert "observed end-to-end behavior or an operational result" in text
        assert "preserve that eventual proof requirement" in text
        assert "do not execute application work or live provider calls" in text
        assert "must not weaken eventual proof into document inspection or a simulated result" in text

    def test_seed_prompt_says_stack_section_is_tool_owned_and_open_stays_open(self) -> None:
        text = _flattened(_seed_prompt_text())

        assert "do not rewrite it" in text
        assert "a stack concern marked open stays open" in text
        assert "do not choose a vendor, runtime, or engine" in text

    def test_seed_prompt_tells_the_model_not_to_author_a_stack_section(self) -> None:
        text = _flattened(_seed_prompt_text())

        assert "the tool inserts the `## stack` section" in text
        assert "do not write a `## stack` section" in text

    def test_seed_prompt_template_ships_under_prompts_dir(self) -> None:
        assert (prompts_dir() / "roadmap-seed.md").is_file()

    def test_seed_prompt_placeholders_are_a_subset_of_the_variable_map(self) -> None:
        assert _placeholders(_seed_prompt_text()) <= {
            "slug",
            "plan_id",
            "domain_artifact",
            "constraints_artifact",
            "components_artifact",
            "plans_artifact",
        }

    def test_seed_prompt_names_draft_seed_provenance_keys(self) -> None:
        text = _seed_prompt_text()

        assert DRAFT_SEED_ROADMAP_COMPONENTS_KEY in text
        assert DRAFT_SEED_CROSS_CUTTING_KEY in text

    def test_seed_prompt_requires_references_to_all_accepted_artifacts(self) -> None:
        text = _seed_prompt_text()

        assert "References" in text
        for filename in (
            DOMAIN_FILENAME,
            CONSTRAINTS_FILENAME,
            COMPONENTS_FILENAME,
            PLANS_FILENAME,
        ):
            assert filename in text

    def test_seed_prompt_states_component_resolution_and_cross_cutting_rules(
        self,
    ) -> None:
        text = _flattened(_seed_prompt_text())

        assert "must resolve against this plan row's `component_ids`" in text
        assert "`cross_cutting: true`" in text

    def test_seed_prompt_warns_against_copying_rejected_alternative_rationale(
        self,
    ) -> None:
        text = _flattened(_seed_prompt_text())

        assert "without pasting long rejected-alternative rationale prose" in text
        assert "`create` re-grounds reasons against live docs" in text

    def test_seed_prompt_states_the_plan_review_contract(self) -> None:
        text = _flattened(_seed_prompt_text())

        assert "preserve the owning plan row's `intent` in `outcome`" in text
        assert (
            "the authoritative review statement; do not make a reviewer infer "
            "it from this derived seed" in text
        )

    def test_seed_prompt_keeps_the_proof_and_roadmap_altitude(self) -> None:
        text = _flattened(_seed_prompt_text())

        assert "smallest end-to-end proof" in text
        assert "eventual capability" in text
        assert "stay at the roadmap altitude" in text
        assert "for `create` and `detail` to ground later" in text

    def test_seed_prompt_invites_repository_inspection(self) -> None:
        text = _seed_prompt_text()

        assert "inspect the **current repository**" in text
        assert "Do not read the repository" not in text

    def test_seed_prompt_cites_no_repo_document(self) -> None:
        assert "FORMAT.md" not in _seed_prompt_text()

    @pytest.mark.parametrize(
        "section",
        (
            "Outcome",
            "In scope",
            "Out of scope / Non-goals",
            "Allowed behavior changes",
            "Allowed reorganization",
            "Testing",
            "Acceptance criteria",
            "Stop / defer",
        ),
    )
    def test_seed_prompt_names_every_scope_contract_section(self, section: str) -> None:
        assert section in _seed_prompt_text()

    def test_seed_prompt_requires_risks_drawn_only_from_accepted_artifacts(self) -> None:
        # `create` refuses an evidence-only section with no source text, and
        # Risks is the one a scope-contract seed otherwise never states.
        text = _seed_prompt_text()

        assert "- `Risks`" in text
        assert "invent none" in text

    def test_seed_prompt_renders_with_no_unresolved_placeholder(
        self, shipped_env: _Env
    ) -> None:
        shipped_env.publish_accepted()
        invoker = _StubInvoker(_seed_text())

        _materialize(shipped_env, invoker)

        assert "${" not in invoker.prompts[0]
        assert _placeholders(invoker.prompts[0]) == set()


class TestMaterializePlanSeed:
    def test_materialization_delivers_obligation_guidance_with_accepted_sibling_context(
        self, shipped_env: _Env
    ) -> None:
        shipped_env.publish_accepted(plans=_plans_artifact_text())
        invoker = _StubInvoker(_seed_text())

        _materialize(shipped_env, invoker)

        prompt = invoker.prompts[0]
        assert _PLAN_ORDER.id in prompt
        assert _plans_artifact_text() in prompt
        assert _PLANS_ASSUMPTION.statement in prompt
        assert "depends_on:" in prompt and _PLAN_AUTH.id in prompt
        for instruction in (
            "shared production", "consumer integration", "required handoffs",
            "source ids and artifact references", "Do not repartition accepted rows",
            "- `Testing`", "- `Acceptance criteria`", "eventual proof requirement",
        ):
            assert instruction in prompt
        for filename in (DOMAIN_FILENAME, CONSTRAINTS_FILENAME, COMPONENTS_FILENAME, PLANS_FILENAME):
            assert filename in prompt
        assert "${" not in prompt

    def test_materialization_preserves_supplied_testing_and_acceptance_sections(
        self, shipped_env: _Env
    ) -> None:
        shipped_env.publish_accepted(plans=_plans_artifact_text())
        proof = (
            "## Testing\n\nObserve an order through checkout after the plan-auth handoff.\n\n"
            "## Acceptance criteria\n\n"
            "- Order creation succeeds end to end using sibling-owned authentication.\n\n"
        )
        candidate = _seed_text().replace("## Risks", proof + "## Risks")

        result = _materialize(shipped_env, _StubInvoker(candidate))

        assert result.outcome == roadmap.SEED_MATERIALIZE_OUTCOME_APPLIED
        draft = _written_draft(shipped_env)
        assert proof in draft
        validate_from_existing_seed(draft)
        assert draft == _stacked(shipped_env, candidate)
        assert _stack_h2_count(draft) == 1

    def test_seed_materialize_prompt_wraps_an_unreadable_template(
        self, env: _Env, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _prepare_seed_materialization(env)
        template_path = env.prompts / "roadmap-seed.md"
        original_read_text = Path.read_text

        def broken_read_text(self: Path, *args: Any, **kwargs: Any) -> str:
            if self == template_path:
                raise UnicodeDecodeError("utf-8", b"\\xff", 0, 1, "invalid start byte")
            return original_read_text(self, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", broken_read_text)

        with pytest.raises(roadmap.RoadmapEnvironmentalError, match="not readable") as excinfo:
            _materialize(env, _StubInvoker(_seed_text()))

        assert isinstance(excinfo.value.__cause__, UnicodeDecodeError)

    def test_seed_materialization_template_failure_writes_no_seed_or_state(
        self, env: _Env, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _prepare_seed_materialization(env)
        template_path = env.prompts / "roadmap-seed.md"
        original_read_text = Path.read_text

        def broken_read_text(self: Path, *args: Any, **kwargs: Any) -> str:
            if self == template_path:
                raise OSError("template unavailable")
            return original_read_text(self, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", broken_read_text)
        invoker = _StubInvoker(_seed_text())
        target = resolve_draft_seed_path(
            env.plans_dir, SLUG, _PLAN_ORDER.draft_seed_path
        )

        with pytest.raises(roadmap.RoadmapEnvironmentalError, match="not readable"):
            _materialize(env, invoker)

        assert invoker.calls == 0
        assert not target.exists()
        assert not seed_state_path(roadmap_dir(env.plans_dir, SLUG)).exists()

    def test_materialize_writes_draft_and_sidecar_entry_together_on_success(
        self, env: _Env
    ) -> None:
        _prepare_seed_materialization(env)
        candidate = _seed_text(marker="MATERIALIZED")

        result = _materialize(env, _StubInvoker(candidate))

        target = resolve_draft_seed_path(
            env.plans_dir, SLUG, _PLAN_ORDER.draft_seed_path
        )
        state = load_seed_state(seed_state_path(roadmap_dir(env.plans_dir, SLUG)))
        assert result.outcome == roadmap.SEED_MATERIALIZE_OUTCOME_APPLIED
        assert result.draft_seed_path == target
        assert target.read_text(encoding="utf-8") == _stacked(env, candidate)
        assert state["seeds"][_PLAN_ORDER.id] == {
            "draft_seed_path": _PLAN_ORDER.draft_seed_path,
            "status": "current",
            "digest": digest_text(_stacked(env, candidate)),
            "published": False,
        }

    def test_materialize_accepts_a_bare_outer_reply_fence(self, env: _Env) -> None:
        _prepare_seed_materialization(env)
        candidate = _seed_text(marker="WRAPPED")

        result = _materialize(env, _StubInvoker(f"```markdown\n{candidate}```\n"))

        target = resolve_draft_seed_path(
            env.plans_dir, SLUG, _PLAN_ORDER.draft_seed_path
        )
        assert result.outcome == roadmap.SEED_MATERIALIZE_OUTCOME_APPLIED
        assert target.read_text(encoding="utf-8") == _stacked(env, candidate)

    def test_materialize_accepts_a_preamble_outer_reply_fence(self, env: _Env) -> None:
        _prepare_seed_materialization(env)
        candidate = _seed_text(marker="WRAPPED")

        result = _materialize(
            env, _StubInvoker(f"Sure, here it is:\n\n```markdown\n{candidate}```\n")
        )

        target = resolve_draft_seed_path(
            env.plans_dir, SLUG, _PLAN_ORDER.draft_seed_path
        )
        assert result.outcome == roadmap.SEED_MATERIALIZE_OUTCOME_APPLIED
        assert target.read_text(encoding="utf-8") == _stacked(env, candidate)

    def test_materialize_ambiguous_preamble_fence_retries(self, env: _Env) -> None:
        _prepare_seed_materialization(env)
        candidate = _seed_text(marker="RETRIED")
        ambiguous = f"```text\nnot an outer wrapper\n{candidate}```\n"
        invoker = _StubInvoker(ambiguous, candidate)

        result = _materialize(env, invoker)

        target = resolve_draft_seed_path(
            env.plans_dir, SLUG, _PLAN_ORDER.draft_seed_path
        )
        assert result.outcome == roadmap.SEED_MATERIALIZE_OUTCOME_APPLIED
        assert invoker.calls == 2
        assert target.read_text(encoding="utf-8") == _stacked(env, candidate)

    def test_materialize_rewrites_a_stale_sidecar_draft_seed_path(
        self, env: _Env
    ) -> None:
        _prepare_seed_materialization(env)
        state_path = seed_state_path(roadmap_dir(env.plans_dir, SLUG))
        write_seed_state(
            state_path,
            {
                "version": 1,
                "seeds": {
                    _PLAN_ORDER.id: {
                        "draft_seed_path": "plan-seed-drafts/old-name.md",
                        "status": "current",
                        "digest": "old-digest",
                        "published": False,
                    }
                },
            },
        )

        _materialize(env, _StubInvoker(_seed_text()))

        entry = load_seed_state(state_path)["seeds"][_PLAN_ORDER.id]
        assert entry["draft_seed_path"] == _PLAN_ORDER.draft_seed_path

    def test_materialize_leaves_other_sidecar_entries_unchanged(
        self, env: _Env
    ) -> None:
        _prepare_seed_materialization(env)
        state_path = seed_state_path(roadmap_dir(env.plans_dir, SLUG))
        other_entry = {
            "draft_seed_path": _PLAN_AUTH.draft_seed_path,
            "status": "invalidated",
            "digest": "auth-digest",
            "published": False,
        }
        write_seed_state(
            state_path, {"version": 1, "seeds": {_PLAN_AUTH.id: other_entry}}
        )

        _materialize(env, _StubInvoker(_seed_text()))

        assert load_seed_state(state_path)["seeds"][_PLAN_AUTH.id] == other_entry

    def test_materialize_invoke_failure_retries_with_correction(
        self, env: _Env
    ) -> None:
        _prepare_seed_materialization(env)
        invoker = _StubInvoker((7, "backend refused"), _seed_text())

        result = _materialize(env, invoker)

        assert result.outcome == roadmap.SEED_MATERIALIZE_OUTCOME_APPLIED
        assert invoker.calls == 2
        assert "previous attempt produced no usable draft seed" in invoker.prompts[1]

    def test_materialize_unliftable_reply_retries_with_correction(
        self, env: _Env
    ) -> None:
        _prepare_seed_materialization(env)
        invoker = _StubInvoker("I cannot write it.", _seed_text())

        _materialize(env, invoker)

        assert invoker.calls == 2
        assert "previous response carried no draft seed" in invoker.prompts[1]

    def test_materialize_gate_violation_retries_with_its_message(
        self, env: _Env
    ) -> None:
        _prepare_seed_materialization(env)
        invalid = _seed_text(components=("component-missing",))
        message = roadmap_gates.validate_draft_seed_content(invalid, plan=_PLAN_ORDER)[
            0
        ].message
        invoker = _StubInvoker(invalid, _seed_text())

        _materialize(env, invoker)

        assert message in invoker.prompts[1]

    def test_materialize_missing_accepted_artifact_reference_retries_without_writing(
        self, env: _Env
    ) -> None:
        _prepare_seed_materialization(env)
        invalid = _seed_text().replace(f"- `{DOMAIN_FILENAME}`\n", "")
        message = roadmap_gates.validate_draft_seed_content(invalid, plan=_PLAN_ORDER)[0].message
        target = resolve_draft_seed_path(
            env.plans_dir, SLUG, _PLAN_ORDER.draft_seed_path
        )
        exhausted = _materialize(env, _StubInvoker(invalid), max_attempts=1)

        assert exhausted.outcome == roadmap.SEED_MATERIALIZE_OUTCOME_EXHAUSTED
        assert exhausted.failure_kind == FAILURE_GATES
        assert exhausted.violations[0].message == message
        assert not target.exists()
        assert not seed_state_path(roadmap_dir(env.plans_dir, SLUG)).exists()

        invoker = _StubInvoker(invalid, _seed_text())
        result = _materialize(env, invoker)

        assert result.outcome == roadmap.SEED_MATERIALIZE_OUTCOME_APPLIED
        assert message in invoker.prompts[1]
        assert target.read_text(encoding="utf-8") == _stacked(env, _seed_text())

    def test_materialize_exhausted_writes_nothing_on_a_first_time_attempt(
        self, env: _Env
    ) -> None:
        _prepare_seed_materialization(env)

        result = _materialize(env, _StubInvoker("not a seed"), max_attempts=1)

        target = resolve_draft_seed_path(
            env.plans_dir, SLUG, _PLAN_ORDER.draft_seed_path
        )
        assert result.outcome == roadmap.SEED_MATERIALIZE_OUTCOME_EXHAUSTED
        assert result.failure_kind == FAILURE_PARSE
        assert not target.exists()
        assert not seed_state_path(roadmap_dir(env.plans_dir, SLUG)).exists()

    def test_materialize_exhausted_leaves_a_prior_draft_and_entry_untouched(
        self, env: _Env
    ) -> None:
        _prepare_seed_materialization(env)
        target = resolve_draft_seed_path(
            env.plans_dir, SLUG, _PLAN_ORDER.draft_seed_path
        )
        previous = _seed_text(marker="PRIOR")
        target.parent.mkdir(parents=True)
        target.write_text(previous, encoding="utf-8")
        state_path = seed_state_path(roadmap_dir(env.plans_dir, SLUG))
        original_entry = {
            "draft_seed_path": _PLAN_ORDER.draft_seed_path,
            "status": "invalidated",
            "digest": digest_text(previous),
            "published": False,
        }
        write_seed_state(
            state_path, {"version": 1, "seeds": {_PLAN_ORDER.id: original_entry}}
        )

        _materialize(env, _StubInvoker((9, "no")), max_attempts=1)

        assert target.read_text(encoding="utf-8") == previous
        assert load_seed_state(state_path)["seeds"][_PLAN_ORDER.id] == original_entry

    def test_materialize_unknown_plan_id_raises_without_calling_invoker(
        self, env: _Env
    ) -> None:
        _prepare_seed_materialization(env)
        invoker = _StubInvoker(_seed_text())

        with pytest.raises(RoadmapError, match=f"{SLUG}.*plan-absent"):
            roadmap.materialize_plan_seed(
                SLUG,
                "plan-absent",
                repo_root=env.repo_root,
                plans_dir=env.plans_dir,
                invoker=invoker,
            )

        assert invoker.calls == 0

    @pytest.mark.integration
    def test_both_seed_handoffs_deliver_obligations_without_changing_accepted_authority(
        self, env: _Env, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool import create as create_module
        from plan_tool.schema import Step
        from tests.test_create import _direct_ready_file_source, _patch_direct_route_metadata

        _prepare_seed_materialization(env)
        accepted = load_accepted_version(plans_dir=env.plans_dir, slug=SLUG)
        head_bytes = accepted_head_path(env.plans_dir, SLUG).read_bytes()
        obligations = (
            "CHECKOUT-17 delivers consumer integration.",
            "AUTH-23 is a sibling prerequisite; do not implement auth here.",
            "PROOF-31 requires an observed checkout result.",
        )
        candidate = _seed_text(marker="MATERIALIZED") + _direct_ready_file_source().replace(
            "## References\n\n- [API](https://example.test/api)\n", ""
        )
        candidate = candidate.replace("Overview body.", obligations[0]).replace(
            "Architecture body.", obligations[1]
        ).replace("Testing body.", obligations[2])
        # The seed fixture already owns Risks and References.
        candidate = candidate.replace("## Risks\n\nRisks body.\n", "")
        candidate = candidate.replace(
            f"- `{DOMAIN_FILENAME}`",
            f"- `src/checkout.py#proof` — CHECKOUT-CONTRACT\n- `{DOMAIN_FILENAME}`",
        )
        _materialize(env, _StubInvoker(candidate))
        roadmap.materialize_plan_seed(
            SLUG,
            _PLAN_AUTH.id,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            invoker=_StubInvoker(
                _seed_text(components=(), cross_cutting=True, marker="AUTH")
            ),
        )
        materialized = resolve_draft_seed_path(
            env.plans_dir, SLUG, _PLAN_ORDER.draft_seed_path
        )

        result = apply_roadmap_seeds(
            SLUG,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            allow_apply=True,
            yes=True,
        )

        assert result.outcome == APPLY_OUTCOME_APPLIED
        materialized.write_text(
            materialized.read_text(encoding="utf-8") + "\nReviewer clarification.\n",
            encoding="utf-8",
        )
        accepted_seed = accept_roadmap_seed(
            SLUG, _PLAN_ORDER.id, repo_root=env.repo_root, plans_dir=env.plans_dir
        )
        assert accepted_seed.outcome == ACCEPT_OUTCOME_ACCEPTED
        _patch_direct_route_metadata(monkeypatch)
        monkeypatch.setattr(
            create_module, "assess_direct_source_split_from_claude",
            lambda *_args, **_kwargs: create_module.DirectSplitAssessment(),
        )
        authoring_sources = []

        def propose_steps(source, *_args, **_kwargs):
            authoring_sources.append(source)
            return [Step(id=1, title="Deliver checkout integration")]

        monkeypatch.setattr(create_module, "propose_steps_from_claude", propose_steps)
        for route, source in (
            ("draft", materialized),
            ("promoted", env.repo_root / "plan-seeds" / f"{_PLAN_ORDER.id}.md"),
        ):
            seed = source.read_text(encoding="utf-8")
            validate_from_existing_seed(seed)
            created = create_module.create_plan(
                f"checkout-{route}", repo_root=env.repo_root,
                output_dir_override=env.plans_dir,
                manifest_path=env.repo_root / "manifest.json",
                from_description=seed, from_existing_path=source,
                yes=True, resume=False, offer_intents=False,
                claude_invoker=lambda _prompt: pytest.fail("unexpected backend call"),
            )
            assert created.plan_path is not None
            published = created.plan_path.read_text(encoding="utf-8")
            for supplied in (
                *obligations, "src/checkout.py#proof", "CHECKOUT-CONTRACT",
                DOMAIN_FILENAME, PLANS_FILENAME,
            ):
                assert supplied in authoring_sources[-1]
                assert supplied in published
        assert len(authoring_sources) == 2
        assert accepted_head_path(env.plans_dir, SLUG).read_bytes() == head_bytes
        current = load_accepted_version(plans_dir=env.plans_dir, slug=SLUG)
        assert current == accepted

    def test_materialize_default_invoker_is_shell_roadmap_invoker(self) -> None:
        assert (
            inspect.signature(roadmap.materialize_plan_seed)
            .parameters["invoker"]
            .default
            is roadmap.shell_roadmap_invoker
        )

    def test_materialization_observer_records_safe_candidate_attempt_fields(
        self, env: _Env
    ) -> None:
        _prepare_seed_materialization(env)
        writer, observer = _materialization_observer(env)
        seed = _seed_text(marker="SEED-CONTENT-MUST-NOT-LOG")

        changes, failure = roadmap.materialize_and_diff_one_plan(
            SLUG,
            _PLAN_ORDER,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            invoker=_StubInvoker(seed),
            materialization_observer=observer,
        )

        assert changes and failure is None
        events = read_run_events(writer.log_path)
        start = next(event for event in events if event["event"] == "claude_call_start")
        assert start["active_plan_id"] == _PLAN_ORDER.id
        assert start["seed_attempt"] == start["attempt"] == 1
        assert start["backend_attempt"] is None
        assert start["backend_child_started"] is False
        log_text = writer.log_path.read_text(encoding="utf-8")
        assert "SEED-CONTENT-MUST-NOT-LOG" not in log_text
        assert "prompt" not in start

    def test_materialization_failure_uses_the_final_observed_backend_attempt(
        self, env: _Env
    ) -> None:
        _prepare_seed_materialization(env)
        writer, observer = _materialization_observer(env)

        def two_children_then_bad_seed(_prompt: str) -> tuple[int, str]:
            observer.backend_spawn(backend="claude")
            observer.backend_termination(
                backend="claude", reason="backend_nonzero", duration_ms=3
            )
            observer.backend_spawn(backend="claude")
            observer.backend_termination(
                backend="claude", reason="completed", duration_ms=4
            )
            return 0, "REPLY-DERIVED-TEXT-MUST-NOT-LOG"

        result = _materialize(
            env,
            two_children_then_bad_seed,
            max_attempts=1,
            materialization_observer=observer,
        )

        assert result.outcome == roadmap.SEED_MATERIALIZE_OUTCOME_EXHAUSTED
        failure = next(
            event
            for event in read_run_events(writer.log_path)
            if event["event"] == "attempt_failed"
        )
        assert failure["failure_kind"] == FAILURE_PARSE
        assert failure["seed_attempt"] == failure["attempt"] == 1
        assert failure["backend_attempt"] == 2
        assert failure["backend_child_started"] is True
        assert "REPLY-DERIVED-TEXT-MUST-NOT-LOG" not in writer.log_path.read_text(
            encoding="utf-8"
        )

    def test_materialization_observer_does_not_change_result_or_retry_behavior(
        self, env: _Env
    ) -> None:
        _prepare_seed_materialization(env)
        writer, observer = _materialization_observer(env)
        invoker = _StubInvoker("not a seed", _seed_text(marker="RECOVERED"))

        result = _materialize(env, invoker, materialization_observer=observer)

        assert result.outcome == roadmap.SEED_MATERIALIZE_OUTCOME_APPLIED
        assert invoker.calls == 2
        assert "previous response carried no draft seed" in invoker.prompts[1]
        starts = [
            event
            for event in read_run_events(writer.log_path)
            if event["event"] == "claude_call_start"
        ]
        assert [event["seed_attempt"] for event in starts] == [1, 2]
        failures = [
            event
            for event in read_run_events(writer.log_path)
            if event["event"] == "attempt_failed"
        ]
        assert [event["failure_kind"] for event in failures] == [FAILURE_PARSE]

    def test_materialize_resyncs_an_already_published_copy(self, env: _Env) -> None:
        _prepare_seed_materialization(env)
        state_path = seed_state_path(roadmap_dir(env.plans_dir, SLUG))
        write_seed_state(
            state_path,
            {
                "version": 1,
                "seeds": {
                    _PLAN_ORDER.id: {
                        "draft_seed_path": _PLAN_ORDER.draft_seed_path,
                        "status": "current",
                        "digest": "old-digest",
                        "published": True,
                    }
                },
            },
        )
        candidate = _seed_text(marker="RESYNCED")

        _materialize(env, _StubInvoker(candidate))

        promoted = env.repo_root / "plan-seeds" / f"{_PLAN_ORDER.id}.md"
        body = promoted.read_text(encoding="utf-8")
        assert "RESYNCED" in body
        assert "plan-tool-roadmap-seed-state" in body
        assert load_seed_state(state_path)["seeds"][_PLAN_ORDER.id]["published"] is True

    def test_materialize_resyncs_an_existing_promoted_copy(self, env: _Env) -> None:
        _prepare_seed_materialization(env)
        _record_order_seed_published(env)
        promoted = env.repo_root / "plan-seeds" / f"{_PLAN_ORDER.id}.md"
        promoted.parent.mkdir()
        promoted.write_text("old promoted seed\n", encoding="utf-8")

        _materialize(env, _StubInvoker(_seed_text(marker="RESYNCED-FILE")))

        assert "RESYNCED-FILE" in promoted.read_text(encoding="utf-8")
        state = load_seed_state(seed_state_path(roadmap_dir(env.plans_dir, SLUG)))
        assert state["seeds"][_PLAN_ORDER.id]["published"] is True

    def test_materialize_resyncs_an_archived_promoted_copy(self, env: _Env) -> None:
        _prepare_seed_materialization(env)
        _record_order_seed_published(env)
        promoted = env.repo_root / "plan-seeds" / f"{_PLAN_ORDER.id}.md"
        archive = promoted.parent / "archive" / f"{_PLAN_ORDER.id}.replaced.md"
        archive.parent.mkdir(parents=True)
        archive.write_text("archived promoted seed\n", encoding="utf-8")

        _materialize(env, _StubInvoker(_seed_text(marker="RESYNCED-ARCHIVE")))

        assert "RESYNCED-ARCHIVE" in promoted.read_text(encoding="utf-8")

    def test_materialize_never_writes_an_unpromoted_copy(self, env: _Env) -> None:
        _prepare_seed_materialization(env)

        _materialize(env, _StubInvoker(_seed_text()))

        assert not (env.repo_root / "plan-seeds" / f"{_PLAN_ORDER.id}.md").exists()

    def test_materialize_never_overwrites_an_unpublished_seeds_existing_file(
        self, env: _Env
    ) -> None:
        # An existing plan-seeds/ file is not proof the tool wrote it: it may be
        # hand-written or another roadmap's. Only the recorded flag is.
        _prepare_seed_materialization(env)
        promoted = env.repo_root / "plan-seeds" / f"{_PLAN_ORDER.id}.md"
        promoted.parent.mkdir()
        promoted.write_text("hand-written seed\n", encoding="utf-8")

        _materialize(env, _StubInvoker(_seed_text(marker="MUST-NOT-LAND")))

        assert promoted.read_text(encoding="utf-8") == "hand-written seed\n"
        state = load_seed_state(seed_state_path(roadmap_dir(env.plans_dir, SLUG)))
        assert state["seeds"][_PLAN_ORDER.id]["published"] is False

    def test_materialize_does_not_promote_from_a_same_named_archive_alone(
        self, env: _Env
    ) -> None:
        # A same-named archive can belong to another roadmap's seed.
        _prepare_seed_materialization(env)
        promoted = env.repo_root / "plan-seeds" / f"{_PLAN_ORDER.id}.md"
        archive = promoted.parent / "archive" / f"{_PLAN_ORDER.id}.replaced.md"
        archive.parent.mkdir(parents=True)
        archive.write_text("another roadmap's archived seed\n", encoding="utf-8")

        _materialize(env, _StubInvoker(_seed_text()))

        assert not promoted.exists()

    def test_materialize_writes_promoted_copy_before_sidecar(
        self, env: _Env, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _prepare_seed_materialization(env)
        _record_order_seed_published(env)
        promoted = env.repo_root / "plan-seeds" / f"{_PLAN_ORDER.id}.md"
        promoted.parent.mkdir()
        promoted.write_text("old promoted seed\n", encoding="utf-8")
        events: list[str] = []
        original_atomic_write = roadmap.atomic_write_text
        original_write_state = roadmap._write_roadmap_seed_state

        def record_atomic(path: Path, text: str, **kwargs: Any) -> None:
            if path == promoted:
                events.append("promoted")
            original_atomic_write(path, text, **kwargs)

        def record_state(*args: Any, **kwargs: Any) -> None:
            events.append("state")
            original_write_state(*args, **kwargs)

        monkeypatch.setattr(roadmap, "atomic_write_text", record_atomic)
        monkeypatch.setattr(roadmap, "_write_roadmap_seed_state", record_state)

        _materialize(env, _StubInvoker(_seed_text()))

        assert events.index("promoted") < events.index("state")

    def test_materialize_sidecar_failure_leaves_the_prior_digest_visible(
        self, env: _Env, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _prepare_seed_materialization(env)
        state_path = seed_state_path(roadmap_dir(env.plans_dir, SLUG))
        old_entry = {
            "draft_seed_path": _PLAN_ORDER.draft_seed_path,
            "status": "current",
            "digest": "old-digest",
            "published": True,
        }
        write_seed_state(
            state_path, {"version": 1, "seeds": {_PLAN_ORDER.id: old_entry}}
        )

        def fail_state_write(*_args: Any, **_kwargs: Any) -> None:
            raise OSError("state write interrupted")

        monkeypatch.setattr(roadmap, "_write_roadmap_seed_state", fail_state_write)
        with pytest.raises(OSError, match="state write interrupted"):
            _materialize(env, _StubInvoker(_seed_text(marker="NEW-DRAFT")))

        assert load_seed_state(state_path)["seeds"][_PLAN_ORDER.id] == old_entry

    def test_fresh_stage4_publish_does_not_create_seed_state(
        self, shipped_env: _Env
    ) -> None:
        result = shipped_env.run(stages=roadmap.STAGES, invoker=_four_stage_invoker())

        assert result.invalidated_seed_count == 0
        assert not seed_state_path(roadmap_dir(shipped_env.plans_dir, SLUG)).exists()


class TestMaterializationRealInvoker:
    def test_materialization_observer_distinguishes_candidate_retry_from_backend_recovery(
        self, env: _Env, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _prepare_seed_materialization(env)
        writer, observer = _materialization_observer(env)
        monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
        monkeypatch.setattr(
            claude_errors,
            "wait_until_epoch",
            lambda *args, **kwargs: claude_errors.WaitUntilResult(
                action=claude_errors.WaitUntilAction.RETRY
            ),
        )
        monkeypatch.setattr(
            backend_runner.subprocess,
            "Popen",
            _fake_popen_factory(
                [
                    SimpleNamespace(
                        stdout="You've hit your limit. resets 3am",
                        stderr="",
                        returncode=1,
                    ),
                    SimpleNamespace(
                        stdout=_claude_stream_result("not a seed"),
                        stderr="",
                        returncode=0,
                    ),
                    SimpleNamespace(
                        stdout=_claude_stream_result(_seed_text()),
                        stderr="",
                        returncode=0,
                    ),
                ]
            ),
        )

        result = roadmap.materialize_plan_seed(
            SLUG,
            _PLAN_ORDER.id,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            invoker=roadmap.shell_roadmap_invoker,
            materialization_observer=observer,
        )

        assert result.outcome == roadmap.SEED_MATERIALIZE_OUTCOME_APPLIED
        events = read_run_events(writer.log_path)
        starts = [event for event in events if event["event"] == "claude_call_start"]
        assert [event["attempt"] for event in starts] == [1, 2]
        assert [event["backend_attempt"] for event in starts] == [None, None]
        spawns = [event for event in events if event["event"] == "backend_spawn"]
        assert [event["attempt"] for event in spawns] == [1, 2, 1]
        assert [event["seed_attempt"] for event in spawns] == [1, 1, 2]
        ends = [event for event in events if event["event"] == "claude_call_end"]
        assert [event["attempt"] for event in ends] == [1, 2, 1]
        wait = next(
            event for event in events if event["event"] == "backend_recovery_wait"
        )
        assert wait["seed_attempt"] == wait["backend_attempt"] == wait["attempt"] == 1
        assert wait["next_attempt"] == 2
        from plan_tool.run_log import read_in_flight

        snapshot = read_in_flight(writer.in_flight_path)
        assert snapshot is not None
        assert snapshot["seed_attempt"] == 2
        assert snapshot["backend_attempt"] == 1
        assert snapshot["backend_child_started"] is True

    def test_materialization_no_child_failure_uses_null_backend_attempt(
        self, env: _Env, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _prepare_seed_materialization(env)
        writer, observer = _materialization_observer(env)
        monkeypatch.setattr(shell.shutil, "which", lambda _name: None)

        result = roadmap.materialize_plan_seed(
            SLUG,
            _PLAN_ORDER.id,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            invoker=roadmap.shell_roadmap_invoker,
            max_attempts=1,
            materialization_observer=observer,
        )

        assert result.outcome == roadmap.SEED_MATERIALIZE_OUTCOME_EXHAUSTED
        failure = next(
            event
            for event in read_run_events(writer.log_path)
            if event["event"] == "attempt_failed"
        )
        assert failure["failure_kind"] == FAILURE_INVOKE
        assert failure["failure_rc"] == 127
        assert failure["backend_attempt"] is None
        assert failure["backend_child_started"] is False

    def test_materialization_observer_records_no_child_termination(
        self, env: _Env
    ) -> None:
        """A runner spawn failure still leaves a safe lifecycle marker."""
        writer, observer = _materialization_observer(env)
        observer.begin_seed_attempt(
            seed_attempt=1, prompt_bytes=0, prompt_sha256="0" * 64
        )
        observer.backend_termination(
            backend="claude", reason="spawn_failure", duration_ms=0
        )

        termination = next(
            event
            for event in read_run_events(writer.log_path)
            if event["event"] == "backend_termination"
        )
        assert termination["attempt"] == termination["seed_attempt"] == 1
        assert termination["backend_attempt"] is None
        assert termination["backend_child_started"] is False

    def test_materialization_observer_omits_tool_and_reply_derived_text(
        self, env: _Env, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _prepare_seed_materialization(env)
        writer, observer = _materialization_observer(env)
        monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
        tool_line = (
            '{"type":"assistant","message":{"content":[{"type":"tool_use",'
            '"name":"Bash","input":{"command":"TOOL-INPUT-MUST-NOT-LOG"}}]}}\n'
        )
        invalid_seed = _seed_text(components=("component-validation-leak",))
        monkeypatch.setattr(
            backend_runner.subprocess,
            "Popen",
            _fake_popen_factory(
                [
                    SimpleNamespace(
                        stdout=tool_line + _claude_stream_result(invalid_seed),
                        stderr="",
                        returncode=0,
                    )
                ]
            ),
        )

        result = roadmap.materialize_plan_seed(
            SLUG,
            _PLAN_ORDER.id,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            invoker=roadmap.shell_roadmap_invoker,
            max_attempts=1,
            materialization_observer=observer,
        )

        assert result.outcome == roadmap.SEED_MATERIALIZE_OUTCOME_EXHAUSTED
        events = read_run_events(writer.log_path)
        stream = next(
            event for event in events if event["event"] == "claude_stream_event"
        )
        assert stream["kind"] == "tool_use"
        assert stream["tool_name"] == "Bash"
        assert "tool_input_summary" not in stream
        from plan_tool.run_log import read_in_flight

        snapshot = read_in_flight(writer.in_flight_path)
        assert snapshot is not None
        durable_text = writer.log_path.read_text(encoding="utf-8") + json.dumps(
            snapshot
        )
        for unsafe_value in (
            "TOOL-INPUT-MUST-NOT-LOG",
            "component-validation-leak",
            "roadmap components are not declared by this plan row",
        ):
            assert unsafe_value not in durable_text

    def test_materialization_observer_restores_shell_binding_after_each_call(
        self, env: _Env, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _prepare_seed_materialization(env)
        writer, observer = _materialization_observer(env)
        monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
        monkeypatch.setattr(
            backend_runner.subprocess,
            "Popen",
            _fake_popen_factory(
                [
                    SimpleNamespace(
                        stdout=_claude_stream_result(_seed_text()),
                        stderr="",
                        returncode=0,
                    )
                ]
            ),
        )
        outer_events: list[Any] = []
        outer_sink = outer_events.append
        outer_writer = object()
        shell.set_active_sink(outer_sink)
        shell.set_active_run_logger(outer_writer)
        try:
            result = roadmap.materialize_plan_seed(
                SLUG,
                _PLAN_ORDER.id,
                repo_root=env.repo_root,
                plans_dir=env.plans_dir,
                invoker=roadmap.shell_roadmap_invoker,
                materialization_observer=observer,
            )
            assert result.outcome == roadmap.SEED_MATERIALIZE_OUTCOME_APPLIED
            assert shell.get_active_sink() is outer_sink
            assert shell.get_active_run_logger() is outer_writer

            with pytest.raises(KeyboardInterrupt):
                roadmap.materialize_plan_seed(
                    SLUG,
                    _PLAN_ORDER.id,
                    repo_root=env.repo_root,
                    plans_dir=env.plans_dir,
                    invoker=lambda _prompt: (_ for _ in ()).throw(KeyboardInterrupt()),
                    materialization_observer=observer,
                )
            assert shell.get_active_sink() is outer_sink
            assert shell.get_active_run_logger() is outer_writer
        finally:
            shell.set_active_sink(None)
            shell.set_active_run_logger(None)


class TestRefreshRoadmapSeeds:
    def _lifecycle_events(self, env: _Env) -> list[dict]:
        return env.run_log_events()

    def _assert_snapshot_removed(self, env: _Env) -> None:
        assert not (
            env.repo_root / ".plan-tool" / "runs" / SLUG / "in-flight.json"
        ).exists()

    def test_refresh_emits_source_ordered_row_phases_and_clears_context(
        self, env: _Env, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _prepare_seed_materialization(env)
        env.publish_accepted(plans=
            _plans_artifact_text(
                ordering=(
                    OrderingEntry(plan_id=_PLAN_AUTH.id),
                    OrderingEntry(plan_id=_PLAN_ORDER.id),
                )
            )
        )
        calls: list[str] = []
        inactive_snapshots: list[dict] = []
        original_update_context = roadmap.RunLogWriter.update_context

        def capture_inactive_context(writer, *args, **kwargs):
            result = original_update_context(writer, *args, **kwargs)
            if kwargs.get("active_plan_id", object()) is None:
                inactive_snapshots.append(
                    json.loads(writer.in_flight_path.read_text(encoding="utf-8"))
                )
            return result

        def materialize(_slug, row, **kwargs):
            calls.append(row.id)
            kwargs["materialization_observer"].begin_seed_attempt(
                seed_attempt=1, prompt_bytes=42, prompt_sha256="0" * 64
            )
            return (
                roadmap.RoadmapSeedRefreshChange(
                    plan_id=row.id,
                    target=env.repo_root / f"{row.id}.md",
                    previous=None,
                    action="created",
                    diff="",
                ),
            ), None

        monkeypatch.setattr(
            roadmap.RunLogWriter, "update_context", capture_inactive_context
        )
        monkeypatch.setattr(roadmap, "materialize_and_diff_one_plan", materialize)

        result = refresh_roadmap_seeds(
            SLUG, repo_root=env.repo_root, plans_dir=env.plans_dir
        )

        assert result.outcome == SEED_REFRESH_OUTCOME_APPLIED
        assert calls == [_PLAN_ORDER.id, _PLAN_AUTH.id]
        events = self._lifecycle_events(env)
        assert events[0]["roadmap_action"] == "refresh-seeds"
        assert events[0]["roadmap_slug"] == SLUG
        assert events[0]["requested_plan_id"] is None
        assert events[0]["active_plan_id"] is None
        assert [
            event["phase"] for event in events if event["event"] == "phase_start"
        ] == [
            f"seed-materialize:{_PLAN_ORDER.id}",
            f"seed-materialize:{_PLAN_AUTH.id}",
        ]
        phase_ends = [event for event in events if event["event"] == "phase_end"]
        assert [event["active_plan_id"] for event in phase_ends] == calls
        assert all(event["seed_attempt"] is None for event in phase_ends)
        assert all(event["backend_attempt"] is None for event in phase_ends)
        assert len(inactive_snapshots) == 2
        assert all(
            snapshot["active_plan_id"] is None for snapshot in inactive_snapshots
        )
        assert all(snapshot["seed_attempt"] is None for snapshot in inactive_snapshots)
        assert all(
            snapshot["backend_attempt"] is None for snapshot in inactive_snapshots
        )
        assert events[-1]["outcome"] == "completed"
        assert events[-1]["active_plan_id"] is None
        self._assert_snapshot_removed(env)

    def test_refresh_passes_the_active_phase_observer_without_replacing_the_invoker_default(
        self, env: _Env, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _prepare_seed_materialization(env)
        calls: list[dict] = []

        def materialize(_slug, row, **kwargs):
            calls.append(kwargs)
            return (), None

        monkeypatch.setattr(roadmap, "materialize_and_diff_one_plan", materialize)

        refresh_roadmap_seeds(SLUG, repo_root=env.repo_root, plans_dir=env.plans_dir)
        assert all("invoker" not in kwargs for kwargs in calls)
        assert all("writer_token" in kwargs for kwargs in calls)
        assert all(
            isinstance(
                kwargs["materialization_observer"], roadmap._MaterializationObserver
            )
            for kwargs in calls
        )

        calls.clear()
        supplied_invoker = lambda _prompt: (0, "")
        refresh_roadmap_seeds(
            SLUG,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            invoker=supplied_invoker,
        )
        assert all(kwargs["invoker"] is supplied_invoker for kwargs in calls)
        assert all("writer_token" in kwargs for kwargs in calls)
        assert all(
            isinstance(
                kwargs["materialization_observer"], roadmap._MaterializationObserver
            )
            for kwargs in calls
        )

    def test_empty_refresh_records_completed_with_zero_row_phases(
        self, env: _Env
    ) -> None:
        _prepare_seed_materialization(env)
        env.publish_accepted(plans=
            _plans_artifact_text(plans=(), ordering=(), assumptions=(), decisions=())
        )

        result = refresh_roadmap_seeds(
            SLUG, repo_root=env.repo_root, plans_dir=env.plans_dir
        )

        assert result.outcome == SEED_REFRESH_OUTCOME_APPLIED
        assert result.changes == ()
        assert result.failures == ()
        assert result.report_path is None
        events = self._lifecycle_events(env)
        assert [event["event"] for event in events] == ["run_start", "run_end"]
        assert events[-1]["outcome"] == "completed"
        assert events[-1]["rc"] == 0
        self._assert_snapshot_removed(env)

    def test_refresh_row_setup_refusal_closes_the_active_phase_and_halts(
        self, env: _Env, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _prepare_seed_materialization(env)
        monkeypatch.setattr(
            roadmap,
            "materialize_and_diff_one_plan",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                RoadmapError("row preparation refused")
            ),
        )

        with pytest.raises(RoadmapError, match="row preparation refused"):
            refresh_roadmap_seeds(
                SLUG, repo_root=env.repo_root, plans_dir=env.plans_dir
            )

        events = self._lifecycle_events(env)
        phase_end = next(event for event in events if event["event"] == "phase_end")
        assert phase_end["outcome"] == "preflight-refused"
        assert phase_end["active_plan_id"] == _PLAN_ORDER.id
        assert phase_end["seed_attempt"] is None
        assert phase_end["backend_attempt"] is None
        assert events[-1]["outcome"] == "preflight-refused"
        assert events[-1]["rc"] == 2
        assert events[-1]["active_plan_id"] is None
        self._assert_snapshot_removed(env)

    def test_refresh_later_row_refusal_keeps_and_reports_earlier_successes(
        self, env: _Env, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A row that raises after an earlier row already succeeded must not
        discard that row's already-written change, and must not be labeled
        "preflight-refused" — nothing about this run was refused before it
        started; it failed partway through."""
        _prepare_seed_materialization(env)

        def materialize(_slug, row, **_kwargs):
            if row.id == _PLAN_AUTH.id:
                raise RoadmapError("row preparation refused")
            return (
                roadmap.RoadmapSeedRefreshChange(
                    plan_id=row.id,
                    target=env.repo_root / f"{row.id}.md",
                    previous=None,
                    action="created",
                    diff="",
                ),
            ), None

        monkeypatch.setattr(roadmap, "materialize_and_diff_one_plan", materialize)
        reports: list[tuple[tuple, tuple]] = []
        monkeypatch.setattr(
            roadmap,
            "write_seed_refresh_report",
            lambda _slug, changes, failures, **_kwargs: (
                reports.append((tuple(changes), tuple(failures)))
                or env.plans_dir / "seed-refresh-report.md"
            ),
        )

        with pytest.raises(RoadmapError, match="row preparation refused"):
            refresh_roadmap_seeds(
                SLUG, repo_root=env.repo_root, plans_dir=env.plans_dir
            )

        assert len(reports) == 1
        changes, failures = reports[0]
        assert [change.plan_id for change in changes] == [_PLAN_ORDER.id]
        assert failures == ()

        events = self._lifecycle_events(env)
        phase_ends = [event for event in events if event["event"] == "phase_end"]
        assert [event["phase"] for event in phase_ends] == [
            f"seed-materialize:{_PLAN_ORDER.id}",
            f"seed-materialize:{_PLAN_AUTH.id}",
        ]
        assert phase_ends[0]["outcome"] == "ok"
        assert phase_ends[1]["outcome"] == "row-refused"
        assert events[-1]["outcome"] == "error"
        assert events[-1]["rc"] == 1
        self._assert_snapshot_removed(env)

    def test_refresh_row_write_error_preserves_prior_recovery_state_and_records_safe_error(
        self, env: _Env, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _prepare_seed_materialization(env)
        auth_path = resolve_draft_seed_path(
            env.plans_dir, SLUG, _PLAN_AUTH.draft_seed_path
        )
        auth_path.parent.mkdir(parents=True)
        prior_auth = _seed_text(components=(), cross_cutting=True, marker="PRIOR-AUTH")
        auth_path.write_text(prior_auth, encoding="utf-8")
        state_path = seed_state_path(roadmap_dir(env.plans_dir, SLUG))
        prior_auth_entry = {
            "draft_seed_path": _PLAN_AUTH.draft_seed_path,
            "status": "invalidated",
            "digest": digest_text(prior_auth),
            "published": False,
        }
        write_seed_state(
            state_path, {"version": 1, "seeds": {_PLAN_AUTH.id: prior_auth_entry}}
        )
        original_atomic_write = roadmap.atomic_write_text

        def fail_auth_draft(path: Path, text: str) -> None:
            if path == auth_path:
                raise RuntimeError("SEED-CONTENT-MUST-NOT-LOG")
            original_atomic_write(path, text)

        monkeypatch.setattr(roadmap, "atomic_write_text", fail_auth_draft)

        with pytest.raises(RuntimeError, match="SEED-CONTENT-MUST-NOT-LOG"):
            refresh_roadmap_seeds(
                SLUG,
                repo_root=env.repo_root,
                plans_dir=env.plans_dir,
                invoker=_StubInvoker(
                    _seed_text(marker="ORDER-LANDED"),
                    _seed_text(components=(), cross_cutting=True, marker="AUTH-FAILED"),
                ),
            )

        order_path = resolve_draft_seed_path(
            env.plans_dir, SLUG, _PLAN_ORDER.draft_seed_path
        )
        assert "ORDER-LANDED" in order_path.read_text(encoding="utf-8")
        assert auth_path.read_text(encoding="utf-8") == prior_auth
        assert load_seed_state(state_path)["seeds"][_PLAN_AUTH.id] == prior_auth_entry
        events = self._lifecycle_events(env)
        failure = next(event for event in events if event["event"] == "attempt_failed")
        assert failure["failure_kind"] == "materialize-error"
        assert failure["active_plan_id"] == _PLAN_AUTH.id
        assert events[-1]["outcome"] == "error"
        assert events[-1]["active_plan_id"] is None
        assert "SEED-CONTENT-MUST-NOT-LOG" not in json.dumps(events)
        self._assert_snapshot_removed(env)

    def test_refresh_report_publication_error_is_command_scoped(
        self, env: _Env, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _prepare_seed_materialization(env)
        report_path = seed_refresh_report_path(roadmap_dir(env.plans_dir, SLUG))
        original_atomic_write = roadmap.atomic_write_text

        def fail_report(path: Path, text: str) -> None:
            if path == report_path:
                raise RuntimeError("REPORT-CONTENT-MUST-NOT-LOG")
            original_atomic_write(path, text)

        monkeypatch.setattr(roadmap, "atomic_write_text", fail_report)

        with pytest.raises(RuntimeError, match="REPORT-CONTENT-MUST-NOT-LOG"):
            refresh_roadmap_seeds(
                SLUG,
                repo_root=env.repo_root,
                plans_dir=env.plans_dir,
                invoker=_StubInvoker(
                    _seed_text(marker="ORDER-LANDED"),
                    _seed_text(components=(), cross_cutting=True, marker="AUTH-LANDED"),
                ),
            )

        events = self._lifecycle_events(env)
        assert [event["event"] for event in events].count("phase_start") == 2
        assert [event["event"] for event in events].count("phase_end") == 2
        assert not any(event["event"] == "attempt_failed" for event in events)
        assert events[-1]["outcome"] == "error"
        assert events[-1]["active_plan_id"] is None
        assert "REPORT-CONTENT-MUST-NOT-LOG" not in json.dumps(events)
        self._assert_snapshot_removed(env)

    def test_refresh_calls_materialize_plan_seed_once_per_plan_on_a_clean_run(
        self, env: _Env
    ) -> None:
        _prepare_seed_materialization(env)
        invoker = _StubInvoker(
            _seed_text(marker="REFRESHED-ORDER"),
            _seed_text(components=(), cross_cutting=True, marker="REFRESHED-AUTH"),
        )

        result = refresh_roadmap_seeds(
            SLUG,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            invoker=invoker,
        )

        assert invoker.calls == 2
        assert result.outcome == SEED_REFRESH_OUTCOME_APPLIED
        assert [change.target for change in result.changes] == [
            resolve_draft_seed_path(env.plans_dir, SLUG, _PLAN_ORDER.draft_seed_path),
            resolve_draft_seed_path(env.plans_dir, SLUG, _PLAN_AUTH.draft_seed_path),
        ]

    def test_refresh_recreates_an_archived_seed_and_writes_its_diff_report(
        self, env: _Env
    ) -> None:
        _prepare_seed_materialization(env)
        refresh_roadmap_seeds(
            SLUG,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            invoker=_StubInvoker(
                _seed_text(marker="ORIGINAL-ORDER"),
                _seed_text(components=(), cross_cutting=True, marker="ORIGINAL-AUTH"),
            ),
        )
        order_path = resolve_draft_seed_path(
            env.plans_dir, SLUG, _PLAN_ORDER.draft_seed_path
        )
        before = order_path.read_text(encoding="utf-8")
        archive = order_path.parent / "archive" / "order-core.replaced.md"
        archive.parent.mkdir()
        archive.write_text(before, encoding="utf-8")
        order_path.unlink()
        state_path = seed_state_path(env.plans_file.parent)
        state = load_seed_state(state_path)
        for entry in state["seeds"].values():
            entry["status"] = "invalidated"
        roadmap.write_seed_state(state_path, state)
        refreshed_order = _seed_text(marker="REFRESHED-FROM-CODE")

        result = refresh_roadmap_seeds(
            SLUG,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            invoker=_StubInvoker(
                refreshed_order,
                _seed_text(components=(), cross_cutting=True, marker="REFRESHED-AUTH"),
            ),
        )

        assert result.outcome == SEED_REFRESH_OUTCOME_APPLIED
        assert order_path.read_text(encoding="utf-8") == _stacked(env, refreshed_order)
        recreated = next(
            change
            for change in result.changes
            if change.plan_id == _PLAN_ORDER.id and change.target == order_path
        )
        assert recreated.action == "recreated"
        assert "REFRESHED-FROM-CODE" in recreated.diff
        assert result.report_path is not None
        assert "REFRESHED-FROM-CODE" in result.report_path.read_text(encoding="utf-8")
        assert all(
            entry["status"] == "current"
            for entry in load_seed_state(state_path)["seeds"].values()
        )

    def test_refresh_isolates_one_failing_plan_and_returns_partial(
        self, env: _Env
    ) -> None:
        _prepare_seed_materialization(env)
        invalid_auth = _seed_text(components=("component-missing",))

        result = refresh_roadmap_seeds(
            SLUG,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            invoker=_StubInvoker(_seed_text(marker="LANDED"), invalid_auth),
            max_stage_attempts=1,
        )

        auth_path = resolve_draft_seed_path(
            env.plans_dir, SLUG, _PLAN_AUTH.draft_seed_path
        )
        assert result.outcome == SEED_REFRESH_OUTCOME_PARTIAL
        assert {change.plan_id for change in result.changes} == {_PLAN_ORDER.id}
        assert result.failures == (
            RoadmapSeedRefreshFailure(
                plan_id=_PLAN_AUTH.id,
                failure_kind=FAILURE_GATES,
                violations=result.failures[0].violations,
            ),
        )
        assert not auth_path.exists()

    def test_refresh_failure_leaves_a_prior_draft_untouched(self, env: _Env) -> None:
        _prepare_seed_materialization(env)
        auth_path = resolve_draft_seed_path(
            env.plans_dir, SLUG, _PLAN_AUTH.draft_seed_path
        )
        prior = _seed_text(components=(), cross_cutting=True, marker="PRIOR-AUTH")
        auth_path.parent.mkdir(parents=True)
        auth_path.write_text(prior, encoding="utf-8")

        result = refresh_roadmap_seeds(
            SLUG,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            invoker=_StubInvoker(
                _seed_text(marker="LANDED"),
                _seed_text(components=("component-missing",)),
            ),
            max_stage_attempts=1,
        )

        assert result.outcome == SEED_REFRESH_OUTCOME_PARTIAL
        assert auth_path.read_text(encoding="utf-8") == prior

    def test_refresh_returns_exhausted_and_writes_a_failure_report_when_every_plan_fails(
        self, env: _Env
    ) -> None:
        _prepare_seed_materialization(env)
        invalid = _seed_text(components=("component-missing",))

        result = refresh_roadmap_seeds(
            SLUG,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            invoker=_StubInvoker(invalid),
            max_stage_attempts=1,
        )

        assert result.outcome == SEED_REFRESH_OUTCOME_EXHAUSTED
        assert result.changes == ()
        assert len(result.failures) == 2
        assert result.report_path is not None
        report = result.report_path.read_text(encoding="utf-8")
        for failure in result.failures:
            assert failure.plan_id in report
            assert failure.failure_kind in report

    def test_refresh_retries_a_failing_plan_up_to_max_stage_attempts(
        self, env: _Env
    ) -> None:
        _prepare_seed_materialization(env)
        env.publish_accepted(plans=
            _plans_artifact_text(
                plans=(_PLAN_ORDER,),
                ordering=(OrderingEntry(plan_id=_PLAN_ORDER.id),),
                assumptions=(),
                decisions=(),
            )
        )
        invoker = _StubInvoker(_seed_text(components=("component-missing",)))

        result = refresh_roadmap_seeds(
            SLUG,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            invoker=invoker,
            max_stage_attempts=2,
        )

        assert result.outcome == SEED_REFRESH_OUTCOME_EXHAUSTED
        assert invoker.calls == 2

    def test_refresh_report_names_the_failed_plan_in_a_mixed_batch(
        self, env: _Env
    ) -> None:
        _prepare_seed_materialization(env)

        result = refresh_roadmap_seeds(
            SLUG,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            invoker=_StubInvoker(
                _seed_text(marker="LANDED"),
                _seed_text(components=("component-missing",)),
            ),
            max_stage_attempts=1,
        )

        assert result.report_path is not None
        report = result.report_path.read_text(encoding="utf-8")
        assert _PLAN_AUTH.id in report
        assert FAILURE_GATES in report

    @pytest.mark.integration
    def test_refresh_regenerates_two_plans_through_the_real_materialize_call_and_prompt(
        self, shipped_env: _Env
    ) -> None:
        _ensure_plans_prompt(shipped_env)
        shipped_env.publish_accepted()
        order_path = resolve_draft_seed_path(
            shipped_env.plans_dir, SLUG, _PLAN_ORDER.draft_seed_path
        )
        auth_path = resolve_draft_seed_path(
            shipped_env.plans_dir, SLUG, _PLAN_AUTH.draft_seed_path
        )

        result = refresh_roadmap_seeds(
            SLUG,
            repo_root=shipped_env.repo_root,
            plans_dir=shipped_env.plans_dir,
            invoker=_StubInvoker(
                _seed_text(marker="SHIPPED-ORDER"),
                _seed_text(components=(), cross_cutting=True, marker="SHIPPED-AUTH"),
            ),
        )

        assert result.outcome == SEED_REFRESH_OUTCOME_APPLIED
        assert order_path.is_file()
        assert auth_path.is_file()
        assert result.report_path is not None
        assert result.report_path.is_file()


class TestMaterializeAndDiffOnePlan:
    def test_unmatched_generated_draft_is_not_materialized(self, env: _Env) -> None:
        _prepare_seed_materialization(env)
        target = resolve_draft_seed_path(
            env.plans_dir, SLUG, _PLAN_ORDER.draft_seed_path
        )

        changes, failure = roadmap.materialize_and_diff_one_plan(
            SLUG,
            _PLAN_ORDER,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            invoker=_StubInvoker(_seed_text(marker="unsafe") + "\n```\n"),
            max_attempts=1,
        )

        assert changes == ()
        assert failure is not None
        assert failure.failure_kind == FAILURE_GATES
        assert not target.exists()

    def test_unmatched_operator_draft_rejects_before_seed_promotion(
        self, env: _Env
    ) -> None:
        _prepare_seed_materialization(env)
        target = resolve_draft_seed_path(
            env.plans_dir, SLUG, _PLAN_ORDER.draft_seed_path
        )
        original = _seed_text(marker="operator") + "\n```\n"
        target.parent.mkdir(parents=True)
        target.write_text(original, encoding="utf-8")

        with pytest.raises(RoadmapError, match="unmatched opening code fence"):
            roadmap.apply_roadmap_seeds(
                SLUG,
                repo_root=env.repo_root,
                plans_dir=env.plans_dir,
                allow_apply=True,
                yes=True,
            )

        assert target.read_text(encoding="utf-8") == original
        assert not (env.repo_root / "plan-seeds").exists()

    def test_reports_created_for_a_first_time_draft(self, env: _Env) -> None:
        _prepare_seed_materialization(env)

        changes, failure = roadmap.materialize_and_diff_one_plan(
            SLUG,
            _PLAN_ORDER,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            invoker=_StubInvoker(_seed_text(marker="FIRST-DRAFT")),
        )

        assert failure is None
        assert len(changes) == 1
        assert changes[0].action == "created"

    def test_reports_updated_and_unchanged_existing_drafts(self, env: _Env) -> None:
        _prepare_seed_materialization(env)
        target = resolve_draft_seed_path(
            env.plans_dir, SLUG, _PLAN_ORDER.draft_seed_path
        )
        target.parent.mkdir(parents=True)
        target.write_text(_seed_text(marker="OLD"), encoding="utf-8")
        refreshed = _seed_text(marker="REFRESHED")

        updated, failure = roadmap.materialize_and_diff_one_plan(
            SLUG,
            _PLAN_ORDER,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            invoker=_StubInvoker(refreshed),
        )
        unchanged, failure = roadmap.materialize_and_diff_one_plan(
            SLUG,
            _PLAN_ORDER,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            invoker=_StubInvoker(refreshed),
        )

        assert failure is None
        assert updated[0].action == "updated"
        assert unchanged[0].action == "unchanged"

    def test_reports_recreated_from_an_archived_draft(self, env: _Env) -> None:
        _prepare_seed_materialization(env)
        target = resolve_draft_seed_path(
            env.plans_dir, SLUG, _PLAN_ORDER.draft_seed_path
        )
        archive = target.parent / "archive" / "order-core.replaced.md"
        archive.parent.mkdir(parents=True)
        archive.write_text(_seed_text(marker="ARCHIVED"), encoding="utf-8")

        changes, failure = roadmap.materialize_and_diff_one_plan(
            SLUG,
            _PLAN_ORDER,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            invoker=_StubInvoker(_seed_text(marker="RESTORED")),
        )

        assert failure is None
        assert changes[0].action == "recreated"
        assert changes[0].previous == archive

    def test_diffs_the_promoted_copy_when_the_row_is_published(self, env: _Env) -> None:
        _prepare_seed_materialization(env)
        state_path = seed_state_path(roadmap_dir(env.plans_dir, SLUG))
        write_seed_state(
            state_path,
            {
                "version": 1,
                "seeds": {
                    _PLAN_ORDER.id: {
                        "draft_seed_path": _PLAN_ORDER.draft_seed_path,
                        "status": "current",
                        "digest": "old-digest",
                        "published": True,
                    }
                },
            },
        )

        changes, failure = roadmap.materialize_and_diff_one_plan(
            SLUG,
            _PLAN_ORDER,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            invoker=_StubInvoker(_seed_text(marker="PUBLISHED")),
        )

        assert failure is None
        assert {change.target for change in changes} == {
            resolve_draft_seed_path(env.plans_dir, SLUG, _PLAN_ORDER.draft_seed_path),
            env.repo_root / "plan-seeds" / f"{_PLAN_ORDER.id}.md",
        }

    def test_an_unpublished_seeds_plan_seeds_file_is_neither_read_nor_reported(
        self, env: _Env
    ) -> None:
        # A hand-written or other-roadmap file (here not even UTF-8) is not the
        # tool's to diff: refresh neither reads it nor lists it as unchanged.
        _prepare_seed_materialization(env)
        foreign = env.repo_root / "plan-seeds" / f"{_PLAN_ORDER.id}.md"
        foreign.parent.mkdir()
        foreign.write_bytes(b"\xff\xfe not utf-8\n")
        archive = foreign.parent / "archive" / f"{_PLAN_ORDER.id}.replaced.md"
        archive.parent.mkdir()
        archive.write_bytes(b"\xff\xfe archived\n")

        changes, failure = roadmap.materialize_and_diff_one_plan(
            SLUG,
            _PLAN_ORDER,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            invoker=_StubInvoker(_seed_text(marker="UNPUBLISHED")),
        )

        assert failure is None
        assert {change.target for change in changes} == {
            resolve_draft_seed_path(env.plans_dir, SLUG, _PLAN_ORDER.draft_seed_path)
        }
        assert foreign.read_bytes() == b"\xff\xfe not utf-8\n"

    def test_returns_failure_without_changing_a_prior_draft(self, env: _Env) -> None:
        _prepare_seed_materialization(env)
        target = resolve_draft_seed_path(
            env.plans_dir, SLUG, _PLAN_ORDER.draft_seed_path
        )
        target.parent.mkdir(parents=True)
        prior = _seed_text(marker="PRIOR")
        target.write_text(prior, encoding="utf-8")

        changes, failure = roadmap.materialize_and_diff_one_plan(
            SLUG,
            _PLAN_ORDER,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            invoker=_StubInvoker("not a seed"),
            max_attempts=1,
        )

        assert changes == ()
        assert failure is not None
        assert failure.failure_kind == FAILURE_PARSE
        assert target.read_text(encoding="utf-8") == prior

    def test_default_invoker_is_shell_roadmap_invoker(self) -> None:
        assert (
            inspect.signature(roadmap.materialize_and_diff_one_plan)
            .parameters["invoker"]
            .default
            is roadmap.shell_roadmap_invoker
        )


class TestWriteSeedRefreshReport:
    def test_writes_changes_and_failures_to_the_shared_report_path(
        self, env: _Env
    ) -> None:
        _prepare_seed_materialization(env)
        target = resolve_draft_seed_path(
            env.plans_dir, SLUG, _PLAN_ORDER.draft_seed_path
        )
        report_path = roadmap.write_seed_refresh_report(
            SLUG,
            (
                roadmap.RoadmapSeedRefreshChange(
                    plan_id=_PLAN_ORDER.id,
                    target=target,
                    previous=None,
                    action="created",
                    diff="",
                ),
            ),
            (
                RoadmapSeedRefreshFailure(
                    plan_id=_PLAN_AUTH.id, failure_kind=FAILURE_GATES
                ),
            ),
            plans_dir=env.plans_dir,
        )

        assert report_path == seed_refresh_report_path(roadmap_dir(env.plans_dir, SLUG))
        report = report_path.read_text(encoding="utf-8")
        assert _PLAN_ORDER.id in report
        assert _PLAN_AUTH.id in report

    def test_skips_the_report_when_no_plan_produced_a_result(self, env: _Env) -> None:
        _prepare_seed_materialization(env)

        report_path = roadmap.write_seed_refresh_report(
            SLUG, (), plans_dir=env.plans_dir
        )

        assert report_path is None
        assert not seed_refresh_report_path(roadmap_dir(env.plans_dir, SLUG)).exists()


def test_loop_never_branches_on_stage_identity() -> None:
    source = Path(inspect.getfile(roadmap)).read_text(encoding="utf-8")
    assert not re.search(r"stage\.(number|name)\s*==", source)


# --------------------------------------------------------------------------
# Apply-only seed promotion
# --------------------------------------------------------------------------


@dataclass
class _ApplyEnv:
    repo_root: Path
    plans_dir: Path
    slug: str = "my-roadmap"
    writer_token: Any = None

    def capture_writer_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Record the writer token a seed route takes, for republishing under its own guard."""
        original = roadmap._roadmap_writer_owner

        @contextlib.contextmanager
        def capturing(plans_dir: Path, slug: str):
            with original(plans_dir, slug) as token:
                self.writer_token = token
                yield token

        monkeypatch.setattr(roadmap, "_roadmap_writer_owner", capturing)

    @property
    def roadmap_root(self) -> Path:
        return self.plans_dir / "roadmaps" / self.slug

    @property
    def seeds_dir(self) -> Path:
        return self.roadmap_root / "plan-seed-drafts"

    @property
    def plan_seeds_dir(self) -> Path:
        return self.repo_root / "plan-seeds"

    def write_plans(self, artifact: PlansArtifact) -> None:
        """Publish ``artifact`` as the accepted head's plans member."""
        publish_accepted_root(
            self.plans_dir,
            self.slug,
            (
                _domain_text(),
                _constraints_text(),
                _components_text(),
                render_plans_artifact(artifact),
            ),
            writer_token=self.writer_token,
        )

    def write_draft(
        self,
        rel_path: str,
        text: str,
        *,
        plan_id: str | None = None,
        status: str = "current",
        recorded_path: str | None = None,
    ) -> Path:
        path = resolve_draft_seed_path(self.plans_dir, self.slug, rel_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        if plan_id is not None:
            state_path = seed_state_path(self.roadmap_root)
            state = load_seed_state(state_path)
            state["seeds"][plan_id] = {
                "draft_seed_path": recorded_path or rel_path,
                "status": status,
                "digest": digest_text(text),
                "published": False,
            }
            write_seed_state(state_path, state)
        return path


def _apply_env(tmp_path: Path) -> _ApplyEnv:
    plans_dir = tmp_path / "docs" / "implementation-plans"
    return _ApplyEnv(repo_root=tmp_path, plans_dir=plans_dir)


def _standard_apply_setup(env: _ApplyEnv) -> None:
    env.write_plans(_plans())
    env.write_draft(
        "plan-seed-drafts/auth.md",
        _seed_text(components=(), cross_cutting=True),
        plan_id="plan-auth",
    )
    env.write_draft(
        "plan-seed-drafts/order-core.md",
        _seed_text(components=("component-checkout",), marker="BODY-MARKER"),
        plan_id="plan-order-core",
    )


class TestAcceptRoadmapSeed:
    @staticmethod
    def _hand_edit_auth_draft(env: _ApplyEnv) -> tuple[Path, str]:
        source = resolve_draft_seed_path(
            env.plans_dir, env.slug, _PLAN_AUTH.draft_seed_path
        )
        text = _seed_text(components=(), cross_cutting=True, marker="HAND-EDITED-AUTH")
        source.write_text(text, encoding="utf-8")
        return source, text

    def test_accept_records_live_digest_as_current_and_preserves_draft(
        self, tmp_path: Path
    ) -> None:
        env = _apply_env(tmp_path)
        _standard_apply_setup(env)
        source, edited = self._hand_edit_auth_draft(env)

        result = accept_roadmap_seed(
            env.slug,
            _PLAN_AUTH.id,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
        )

        entry = load_seed_state(seed_state_path(env.roadmap_root))["seeds"][
            _PLAN_AUTH.id
        ]
        assert result.outcome == ACCEPT_OUTCOME_ACCEPTED
        assert result.target == source
        assert entry["status"] == "current"
        assert entry["digest"] == digest_text(edited)
        assert source.read_text(encoding="utf-8") == edited

    def test_accept_wraps_a_toctou_read_failure_as_a_roadmap_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        env = _apply_env(tmp_path)
        _standard_apply_setup(env)
        source, _edited = self._hand_edit_auth_draft(env)
        # Simulate the draft vanishing after classification reported it
        # digest-mismatched but before the subsequent independent read.
        source.unlink()
        monkeypatch.setattr(
            roadmap,
            "classify_draft_seeds",
            lambda *_args, **_kwargs: {
                _PLAN_AUTH.id: DraftSeedClassification(
                    plan_id=_PLAN_AUTH.id,
                    state=DRAFT_SEED_STATE_DIGEST_MISMATCHED,
                )
            },
        )

        with pytest.raises(RoadmapError):
            accept_roadmap_seed(
                env.slug,
                _PLAN_AUTH.id,
                repo_root=env.repo_root,
                plans_dir=env.plans_dir,
            )

    def test_accept_resyncs_an_already_promoted_copy(self, tmp_path: Path) -> None:
        env = _apply_env(tmp_path)
        _standard_apply_setup(env)
        _source, edited = self._hand_edit_auth_draft(env)
        state_path = seed_state_path(env.roadmap_root)
        state = load_seed_state(state_path)
        state["seeds"][_PLAN_AUTH.id]["published"] = True
        write_seed_state(state_path, state)
        promoted = env.plan_seeds_dir / f"{_PLAN_AUTH.id}.md"
        promoted.parent.mkdir()
        promoted.write_text("old promoted seed\n", encoding="utf-8")

        result = accept_roadmap_seed(
            env.slug,
            _PLAN_AUTH.id,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
        )

        marker = roadmap.render_seed_state_marker(
            state_path=state_path,
            repo_root=env.repo_root,
            roadmap_slug=env.slug,
            plan_id=_PLAN_AUTH.id,
        )
        assert result.promoted_target == promoted
        assert promoted.read_text(encoding="utf-8") == roadmap._promoted_seed_body(
            edited, marker=marker
        )

    def test_accept_failed_copy_write_leaves_the_draft_re_acceptable(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Copy before sidecar: if the copy write fails the sidecar still says
        # digest-mismatched, so the same accept can be re-run. Sidecar-first
        # recorded the draft current and made the retry a refusal.
        env = _apply_env(tmp_path)
        _standard_apply_setup(env)
        _source, edited = self._hand_edit_auth_draft(env)
        _set_seed_state_value(env, _PLAN_AUTH.id, "published", True)
        promoted = env.plan_seeds_dir / f"{_PLAN_AUTH.id}.md"
        promoted.parent.mkdir()
        promoted.write_text("old promoted seed\n", encoding="utf-8")
        original = roadmap.atomic_write_text

        def failing(path: Path, text: str, **kwargs: Any) -> None:
            if path == promoted:
                raise OSError("disk full")
            original(path, text, **kwargs)

        sidecar = seed_state_path(env.roadmap_root)
        before = sidecar.read_bytes()

        monkeypatch.setattr(roadmap, "atomic_write_text", failing)
        with pytest.raises(RoadmapError, match="re-run --accept-seed"):
            accept_roadmap_seed(
                env.slug, _PLAN_AUTH.id, repo_root=env.repo_root, plans_dir=env.plans_dir
            )
        monkeypatch.setattr(roadmap, "atomic_write_text", original)
        assert sidecar.read_bytes() == before

        retry = accept_roadmap_seed(
            env.slug, _PLAN_AUTH.id, repo_root=env.repo_root, plans_dir=env.plans_dir
        )

        assert retry.outcome == ACCEPT_OUTCOME_ACCEPTED
        assert "HAND-EDITED-AUTH" in promoted.read_text(encoding="utf-8")
        assert (
            load_seed_state(seed_state_path(env.roadmap_root))["seeds"][_PLAN_AUTH.id][
                "digest"
            ]
            == digest_text(edited)
        )

    def test_accept_failed_sidecar_write_after_the_copy_is_re_acceptable(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The mirror failure: the copy landed, the sidecar did not. The draft
        # still classifies digest-mismatched, so the retry converges.
        env = _apply_env(tmp_path)
        _standard_apply_setup(env)
        _source, edited = self._hand_edit_auth_draft(env)
        _set_seed_state_value(env, _PLAN_AUTH.id, "published", True)
        promoted = env.plan_seeds_dir / f"{_PLAN_AUTH.id}.md"
        promoted.parent.mkdir()
        promoted.write_text("old promoted seed\n", encoding="utf-8")
        original = roadmap._write_roadmap_seed_state

        def failing(*args: Any, **kwargs: Any) -> None:
            raise RoadmapError("sidecar write failed")

        monkeypatch.setattr(roadmap, "_write_roadmap_seed_state", failing)
        with pytest.raises(RoadmapError, match="sidecar write failed"):
            accept_roadmap_seed(
                env.slug, _PLAN_AUTH.id, repo_root=env.repo_root, plans_dir=env.plans_dir
            )
        monkeypatch.setattr(roadmap, "_write_roadmap_seed_state", original)
        assert "HAND-EDITED-AUTH" in promoted.read_text(encoding="utf-8")

        retry = accept_roadmap_seed(
            env.slug, _PLAN_AUTH.id, repo_root=env.repo_root, plans_dir=env.plans_dir
        )

        assert retry.outcome == ACCEPT_OUTCOME_ACCEPTED
        assert (
            load_seed_state(seed_state_path(env.roadmap_root))["seeds"][_PLAN_AUTH.id][
                "digest"
            ]
            == digest_text(edited)
        )

    def test_accept_does_not_promote_a_first_copy(self, tmp_path: Path) -> None:
        env = _apply_env(tmp_path)
        _standard_apply_setup(env)
        self._hand_edit_auth_draft(env)
        promoted = env.plan_seeds_dir / f"{_PLAN_AUTH.id}.md"

        result = accept_roadmap_seed(
            env.slug,
            _PLAN_AUTH.id,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
        )

        assert result.outcome == ACCEPT_OUTCOME_ACCEPTED
        assert result.promoted_target is None
        assert not promoted.exists()

    def test_accept_never_overwrites_an_unpublished_seeds_existing_file(
        self, tmp_path: Path
    ) -> None:
        # An existing file is not proof the tool wrote it; only the recorded
        # published flag is, so a hand-written or other-roadmap copy survives.
        env = _apply_env(tmp_path)
        _standard_apply_setup(env)
        self._hand_edit_auth_draft(env)
        promoted = env.plan_seeds_dir / f"{_PLAN_AUTH.id}.md"
        promoted.parent.mkdir()
        promoted.write_text("hand-written seed\n", encoding="utf-8")

        result = accept_roadmap_seed(
            env.slug,
            _PLAN_AUTH.id,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
        )

        assert result.outcome == ACCEPT_OUTCOME_ACCEPTED
        assert result.promoted_target is None
        assert promoted.read_text(encoding="utf-8") == "hand-written seed\n"
        assert (
            load_seed_state(seed_state_path(env.roadmap_root))["seeds"][_PLAN_AUTH.id][
                "published"
            ]
            is False
        )

    def test_accept_resyncs_a_published_seeds_archive_without_a_live_copy(
        self, tmp_path: Path
    ) -> None:
        env = _apply_env(tmp_path)
        _standard_apply_setup(env)
        self._hand_edit_auth_draft(env)
        _set_seed_state_value(env, _PLAN_AUTH.id, "published", True)
        promoted = env.plan_seeds_dir / f"{_PLAN_AUTH.id}.md"
        archive = promoted.parent / "archive" / f"{_PLAN_AUTH.id}.replaced.md"
        archive.parent.mkdir(parents=True)
        archive.write_text("old archived seed\n", encoding="utf-8")

        result = accept_roadmap_seed(
            env.slug,
            _PLAN_AUTH.id,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
        )

        assert result.promoted_target == promoted
        assert "HAND-EDITED-AUTH" in promoted.read_text(encoding="utf-8")

    @pytest.mark.parametrize(
        ("state", "configure"),
        (
            (
                DRAFT_SEED_STATE_CURRENT,
                lambda env: None,
            ),
            (
                DRAFT_SEED_STATE_MISSING,
                lambda env: resolve_draft_seed_path(
                    env.plans_dir, env.slug, _PLAN_AUTH.draft_seed_path
                ).unlink(),
            ),
            (
                DRAFT_SEED_STATE_STALE,
                lambda env: _set_seed_state_value(
                    env, _PLAN_AUTH.id, "status", "invalidated"
                ),
            ),
            (
                DRAFT_SEED_STATE_MALFORMED,
                lambda env: _write_current_invalid_auth_draft(env),
            ),
            (
                DRAFT_SEED_STATE_PATH_ESCAPING,
                lambda env: _set_seed_state_value(
                    env, _PLAN_AUTH.id, "draft_seed_path", "../escape.md"
                ),
            ),
            (
                DRAFT_SEED_STATE_DUPLICATE,
                lambda env: env.write_plans(
                    _plans(
                        plans=(
                            replace(
                                _PLAN_ORDER,
                                draft_seed_path=_PLAN_AUTH.draft_seed_path,
                            ),
                            _PLAN_AUTH,
                        )
                    )
                ),
            ),
        ),
    )
    def test_accept_refuses_each_non_digest_mismatched_classification(
        self, state: str, configure, tmp_path: Path
    ) -> None:
        env = _apply_env(tmp_path)
        _standard_apply_setup(env)
        configure(env)
        sidecar = seed_state_path(env.roadmap_root)
        before = sidecar.read_bytes()
        promoted = env.plan_seeds_dir / f"{_PLAN_AUTH.id}.md"

        result = accept_roadmap_seed(
            env.slug,
            _PLAN_AUTH.id,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
        )

        assert result.outcome == ACCEPT_OUTCOME_REFUSED
        assert result.state == state
        assert result.violations == ()
        assert sidecar.read_bytes() == before
        assert not promoted.exists()

    def test_accept_refuses_a_hand_edit_that_fails_validation(
        self, tmp_path: Path
    ) -> None:
        env = _apply_env(tmp_path)
        _standard_apply_setup(env)
        source = resolve_draft_seed_path(
            env.plans_dir, env.slug, _PLAN_AUTH.draft_seed_path
        )
        invalid = _seed_text(components=("component-missing",))
        source.write_text(invalid, encoding="utf-8")
        sidecar = seed_state_path(env.roadmap_root)
        before = sidecar.read_bytes()

        result = accept_roadmap_seed(
            env.slug,
            _PLAN_AUTH.id,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
        )

        assert result.outcome == ACCEPT_OUTCOME_REFUSED
        assert result.state is None
        assert result.violations
        assert sidecar.read_bytes() == before
        assert source.read_text(encoding="utf-8") == invalid
        assert not (env.plan_seeds_dir / f"{_PLAN_AUTH.id}.md").exists()

    def test_accept_refuses_hand_edit_missing_accepted_artifact_reference(
        self, tmp_path: Path
    ) -> None:
        env = _apply_env(tmp_path)
        _standard_apply_setup(env)
        source = resolve_draft_seed_path(
            env.plans_dir, env.slug, _PLAN_AUTH.draft_seed_path
        )
        invalid = _seed_text(components=(), cross_cutting=True).replace(
            f"- `{PLANS_FILENAME}`\n", ""
        )
        source.write_text(invalid, encoding="utf-8")
        sidecar = seed_state_path(env.roadmap_root)
        before = sidecar.read_bytes()

        result = accept_roadmap_seed(
            env.slug,
            _PLAN_AUTH.id,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
        )

        assert result.outcome == ACCEPT_OUTCOME_REFUSED
        assert PLANS_FILENAME in result.violations[0].message
        assert sidecar.read_bytes() == before
        assert not (env.plan_seeds_dir / f"{_PLAN_AUTH.id}.md").exists()

    def test_accept_refuses_an_unknown_plan_id(self, tmp_path: Path) -> None:
        env = _apply_env(tmp_path)
        _standard_apply_setup(env)
        sidecar = seed_state_path(env.roadmap_root)
        before = sidecar.read_bytes()

        result = accept_roadmap_seed(
            env.slug,
            "plan-absent",
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
        )

        assert result.outcome == ACCEPT_OUTCOME_REFUSED
        assert result.state is None
        assert result.violations == ()
        assert sidecar.read_bytes() == before

    def test_accept_wraps_an_invalid_slug_as_roadmap_error(
        self, tmp_path: Path
    ) -> None:
        env = _apply_env(tmp_path)

        with pytest.raises(RoadmapError):
            accept_roadmap_seed(
                "../escape",
                _PLAN_AUTH.id,
                repo_root=env.repo_root,
                plans_dir=env.plans_dir,
            )

    def test_accept_propagates_a_malformed_roadmap_artifact(
        self, tmp_path: Path
    ) -> None:
        env = _apply_env(tmp_path)
        env.roadmap_root.mkdir(parents=True)
        (env.roadmap_root / PLANS_FILENAME).write_text("{", encoding="utf-8")

        with pytest.raises(RoadmapArtifactError):
            accept_roadmap_seed(
                env.slug,
                _PLAN_AUTH.id,
                repo_root=env.repo_root,
                plans_dir=env.plans_dir,
            )

    def test_accept_wraps_a_corrupt_sidecar_as_roadmap_error(
        self, tmp_path: Path
    ) -> None:
        env = _apply_env(tmp_path)
        _standard_apply_setup(env)
        seed_state_path(env.roadmap_root).write_text("{", encoding="utf-8")

        with pytest.raises(RoadmapError):
            accept_roadmap_seed(
                env.slug,
                _PLAN_AUTH.id,
                repo_root=env.repo_root,
                plans_dir=env.plans_dir,
            )


def _set_seed_state_value(
    env: _ApplyEnv, plan_id: str, key: str, value: object
) -> None:
    path = seed_state_path(env.roadmap_root)
    state = load_seed_state(path)
    state["seeds"][plan_id][key] = value
    write_seed_state(path, state)


def _write_current_invalid_auth_draft(env: _ApplyEnv) -> None:
    source = resolve_draft_seed_path(
        env.plans_dir, env.slug, _PLAN_AUTH.draft_seed_path
    )
    text = _seed_text(components=("component-missing",))
    source.write_text(text, encoding="utf-8")
    _set_seed_state_value(env, _PLAN_AUTH.id, "digest", digest_text(text))


class TestApplyRoadmapSeeds:
    def test_apply_recommended_when_allow_apply_false(self, tmp_path: Path) -> None:
        env = _apply_env(tmp_path)
        _standard_apply_setup(env)

        result = apply_roadmap_seeds(
            env.slug,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            allow_apply=False,
        )

        assert result.outcome == APPLY_OUTCOME_RECOMMENDED
        assert len(result.targets) == 2
        assert result.promotions == ()
        assert not env.plan_seeds_dir.exists()

    def test_apply_does_not_opt_into_context(self, tmp_path: Path) -> None:
        env = _apply_env(tmp_path)
        _standard_apply_setup(env)

        result = apply_roadmap_seeds(
            env.slug,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            allow_apply=True,
            yes=True,
        )

        logs = list((env.repo_root / ".plan-tool" / "runs" / env.slug).glob("*.jsonl"))
        assert len(logs) == 1
        events = read_run_events(logs[0])
        assert events[0]["event"] == "run_start"
        assert events[0]["command"] == "roadmap"
        assert events[0]["argv"] == []
        assert events[0]["flags"] == {
            "mode": "apply",
            "yes": True,
            "allow_apply": True,
        }
        applied = next(e for e in events if e["event"] == "roadmap_seed_apply_result")
        assert applied["outcome"] == result.outcome == APPLY_OUTCOME_APPLIED
        assert applied["target_count"] == 2
        assert applied["promotion_count"] == 2
        assert applied["collision_count"] == 0
        assert applied["missing_draft_count"] == 0
        assert applied["malformed_draft_count"] == 0
        assert applied["stale_draft_count"] == 0
        assert applied["path_escaping_draft_count"] == 0
        assert applied["duplicate_draft_count"] == 0
        assert applied["digest_mismatched_draft_count"] == 0
        assert events[-1]["event"] == "run_end"
        assert events[-1]["outcome"] == APPLY_OUTCOME_APPLIED
        assert events[-1]["rc"] == 0
        assert all(
            context_key not in event
            for event in events
            for context_key in (
                "roadmap_action",
                "roadmap_slug",
                "requested_plan_id",
                "active_plan_id",
                "seed_attempt",
                "backend_attempt",
            )
        )
        assert not (
            env.repo_root / ".plan-tool" / "runs" / env.slug / "in-flight.json"
        ).exists()

    def test_apply_refused_when_destination_exists(self, tmp_path: Path) -> None:
        env = _apply_env(tmp_path)
        _standard_apply_setup(env)
        env.plan_seeds_dir.mkdir(parents=True)
        existing = env.plan_seeds_dir / "plan-auth.md"
        existing.write_text("blocked\n", encoding="utf-8")
        auth_draft = env.write_draft(
            "plan-seed-drafts/auth.md",
            _seed_text(components=(), cross_cutting=True),
            plan_id="plan-auth",
        )

        result = apply_roadmap_seeds(
            env.slug,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            allow_apply=True,
            yes=True,
        )

        assert result.outcome == APPLY_OUTCOME_REFUSED
        assert existing.read_text(encoding="utf-8") == "blocked\n"
        assert auth_draft.read_text(encoding="utf-8").startswith("---")
        logs = list((env.repo_root / ".plan-tool" / "runs" / env.slug).glob("*.jsonl"))
        events = read_run_events(logs[0])
        assert events[-1]["event"] == "run_end"
        assert events[-1]["outcome"] == APPLY_OUTCOME_REFUSED
        assert events[-1]["rc"] == 2
        assert not (
            env.repo_root / ".plan-tool" / "runs" / env.slug / "in-flight.json"
        ).exists()

    @staticmethod
    def _mark_published(env: _ApplyEnv, plan_id: str) -> None:
        from plan_tool import roadmap as roadmap_module

        state = roadmap_module._load_roadmap_seed_state(
            plans_dir=env.plans_dir, slug=env.slug
        )
        state["seeds"].setdefault(plan_id, {})["published"] = True
        roadmap_module._write_roadmap_seed_state(
            state, plans_dir=env.plans_dir, slug=env.slug
        )

    def test_apply_skips_a_published_seed_and_promotes_the_unpublished_rest(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Integration, 2026-10-09: published seeds blocked every new one as collisions.
        env = _apply_env(tmp_path)
        _standard_apply_setup(env)
        env.plan_seeds_dir.mkdir(parents=True)
        published = env.plan_seeds_dir / "plan-order-core.md"
        published.write_text("operator-edited published seed\n", encoding="utf-8")
        self._mark_published(env, "plan-order-core")

        result = apply_roadmap_seeds(
            env.slug,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            allow_apply=True,
            yes=True,
        )

        assert result.outcome == APPLY_OUTCOME_APPLIED
        assert [plan_id for plan_id, _s, _d in result.promotions] == ["plan-auth"]
        assert [plan_id for plan_id, _d in result.skipped] == ["plan-order-core"]
        assert published.read_text(encoding="utf-8") == "operator-edited published seed\n"
        assert (env.plan_seeds_dir / "plan-auth.md").is_file()

    def test_apply_does_not_recopy_a_published_seed_create_already_consumed(
        self, tmp_path: Path
    ) -> None:
        env = _apply_env(tmp_path)
        _standard_apply_setup(env)
        self._mark_published(env, "plan-auth")
        self._mark_published(env, "plan-order-core")

        result = apply_roadmap_seeds(
            env.slug,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            allow_apply=True,
            yes=True,
        )

        assert result.outcome == APPLY_OUTCOME_RECOMMENDED
        assert result.targets == ()
        assert {plan_id for plan_id, _d in result.skipped} == {"plan-auth", "plan-order-core"}
        assert not env.plan_seeds_dir.exists()

    def test_apply_still_refuses_a_collision_beside_a_skipped_published_seed(
        self, tmp_path: Path
    ) -> None:
        env = _apply_env(tmp_path)
        _standard_apply_setup(env)
        env.plan_seeds_dir.mkdir(parents=True)
        blocker = env.plan_seeds_dir / "plan-auth.md"
        blocker.write_text("hand-written\n", encoding="utf-8")
        self._mark_published(env, "plan-order-core")

        result = apply_roadmap_seeds(
            env.slug,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            allow_apply=True,
            yes=True,
        )

        assert result.outcome == APPLY_OUTCOME_REFUSED
        assert result.collisions == (blocker,)
        assert [plan_id for plan_id, _d in result.skipped] == ["plan-order-core"]
        assert blocker.read_text(encoding="utf-8") == "hand-written\n"

    def test_apply_warns_on_a_stale_published_seed_but_still_promotes_the_rest(
        self, tmp_path: Path
    ) -> None:
        # Skipping must not hide an out-of-date published copy, and refusing
        # over it would re-block every new seed after a roadmap revision.
        from plan_tool import roadmap as roadmap_module

        env = _apply_env(tmp_path)
        _standard_apply_setup(env)
        self._mark_published(env, "plan-order-core")
        state = roadmap_module._load_roadmap_seed_state(
            plans_dir=env.plans_dir, slug=env.slug
        )
        state["seeds"]["plan-order-core"]["status"] = "invalidated"
        roadmap_module._write_roadmap_seed_state(
            state, plans_dir=env.plans_dir, slug=env.slug
        )

        result = apply_roadmap_seeds(
            env.slug,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            allow_apply=True,
            yes=True,
        )

        assert result.outcome == APPLY_OUTCOME_APPLIED
        assert result.refused_drafts == ()
        assert [(c.plan_id, c.state) for c in result.stale_published] == [
            ("plan-order-core", DRAFT_SEED_STATE_STALE)
        ]
        assert [plan_id for plan_id, _s, _d in result.promotions] == ["plan-auth"]

    def test_apply_promotes_an_unpublished_seed_despite_a_same_named_archive(
        self, tmp_path: Path
    ) -> None:
        # Deliberately not an archive-filename check: the archive may belong to
        # another roadmap or a hand-written seed of the same name.
        env = _apply_env(tmp_path)
        _standard_apply_setup(env)
        archive = env.plan_seeds_dir / "archive"
        archive.mkdir(parents=True)
        (archive / "plan-auth.replaced.md").write_text("other roadmap\n", encoding="utf-8")

        result = apply_roadmap_seeds(
            env.slug,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            allow_apply=True,
            yes=True,
        )

        assert result.outcome == APPLY_OUTCOME_APPLIED
        assert result.skipped == ()
        assert (env.plan_seeds_dir / "plan-auth.md").is_file()

    def test_apply_refused_when_draft_missing(self, tmp_path: Path) -> None:
        env = _apply_env(tmp_path)
        env.write_plans(_plans())
        env.write_draft(
            "plan-seed-drafts/order-core.md",
            _seed_text(components=("component-checkout",)),
            plan_id="plan-order-core",
        )

        result = apply_roadmap_seeds(
            env.slug,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            allow_apply=True,
            yes=True,
        )

        assert result.outcome == APPLY_OUTCOME_REFUSED
        assert result.refused_drafts[0].state == DRAFT_SEED_STATE_MISSING
        assert not env.plan_seeds_dir.exists()

    def test_apply_refused_is_all_or_nothing(self, tmp_path: Path) -> None:
        env = _apply_env(tmp_path)
        _standard_apply_setup(env)
        env.plan_seeds_dir.mkdir(parents=True)
        (env.plan_seeds_dir / "plan-order-core.md").write_text(
            "blocked\n", encoding="utf-8"
        )

        result = apply_roadmap_seeds(
            env.slug,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            allow_apply=True,
            yes=True,
        )

        assert result.outcome == APPLY_OUTCOME_REFUSED
        assert not (env.plan_seeds_dir / "plan-auth.md").exists()

    def test_apply_error_ends_the_owned_writer_once(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        env = _apply_env(tmp_path)
        _standard_apply_setup(env)
        real_link = os.link
        calls = {"n": 0}

        def flaky_link(src, dst, *args, **kwargs):
            calls["n"] += 1
            if calls["n"] >= 2:
                raise OSError("simulated apply link failure")
            return real_link(src, dst, *args, **kwargs)

        monkeypatch.setattr(roadmap.os, "link", flaky_link)

        with pytest.raises(OSError, match="simulated apply link failure"):
            apply_roadmap_seeds(
                env.slug,
                repo_root=env.repo_root,
                plans_dir=env.plans_dir,
                allow_apply=True,
                yes=True,
            )

        assert not (env.plan_seeds_dir / "plan-auth.md").exists()
        assert not (env.plan_seeds_dir / "plan-order-core.md").exists()
        logs = list((env.repo_root / ".plan-tool" / "runs" / env.slug).glob("*.jsonl"))
        events = read_run_events(logs[0])
        run_ends = [event for event in events if event["event"] == "run_end"]
        assert len(run_ends) == 1
        assert run_ends[0]["outcome"] == "error"
        assert run_ends[0]["rc"] == 1
        assert run_ends[0]["error"] == "simulated apply link failure"
        assert not (
            env.repo_root / ".plan-tool" / "runs" / env.slug / "in-flight.json"
        ).exists()

    def test_apply_refuses_a_destination_created_after_preflight(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The confirm holds preflight's check-to-use window open, so the
        commit must refuse a late destination rather than clobber it."""
        env = _apply_env(tmp_path)
        _standard_apply_setup(env)
        late = env.plan_seeds_dir / "plan-order-core.md"

        def confirm_then_collide(*_args: Any, **_kwargs: Any) -> bool:
            late.parent.mkdir(parents=True, exist_ok=True)
            late.write_text("hand-authored\n", encoding="utf-8")
            return True

        monkeypatch.setattr(roadmap, "_confirm_apply_seeds", confirm_then_collide)

        result = apply_roadmap_seeds(
            env.slug,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            allow_apply=True,
        )

        assert result.outcome == APPLY_OUTCOME_REFUSED
        assert result.collisions == (late,)
        # The pre-existing file survives untouched, and the seed that landed
        # before the collision is rolled back.
        assert late.read_text(encoding="utf-8") == "hand-authored\n"
        assert not (env.plan_seeds_dir / "plan-auth.md").exists()

    def test_apply_yes_copies_in_ordering_sequence(self, tmp_path: Path) -> None:
        env = _apply_env(tmp_path)
        _standard_apply_setup(env)

        result = apply_roadmap_seeds(
            env.slug,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            allow_apply=True,
            yes=True,
        )

        assert result.outcome == APPLY_OUTCOME_APPLIED
        assert [plan_id for plan_id, _s, _d in result.promotions] == [
            "plan-auth",
            "plan-order-core",
        ]

    def test_apply_leaves_slug_drafts_on_disk(self, tmp_path: Path) -> None:
        env = _apply_env(tmp_path)
        _standard_apply_setup(env)
        order_draft = resolve_draft_seed_path(
            env.plans_dir, env.slug, "plan-seed-drafts/order-core.md"
        )
        before = order_draft.read_bytes()

        apply_roadmap_seeds(
            env.slug,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            allow_apply=True,
            yes=True,
        )

        assert order_draft.read_bytes() == before

    def test_apply_strips_provenance_frontmatter(self, tmp_path: Path) -> None:
        env = _apply_env(tmp_path)
        _standard_apply_setup(env)

        apply_roadmap_seeds(
            env.slug,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            allow_apply=True,
            yes=True,
        )

        promoted = (env.plan_seeds_dir / "plan-order-core.md").read_text(
            encoding="utf-8"
        )
        assert DRAFT_SEED_ROADMAP_COMPONENTS_KEY not in promoted
        assert "BODY-MARKER" in promoted
        assert "# Seed body" in promoted

    def test_apply_refuses_malformed_draft(self, tmp_path: Path) -> None:
        env = _apply_env(tmp_path)
        env.write_plans(_plans())
        env.write_draft(
            "plan-seed-drafts/auth.md",
            _seed_text(components=(), cross_cutting=True),
            plan_id="plan-auth",
        )
        env.write_draft(
            "plan-seed-drafts/order-core.md",
            "---\nroadmap_components: not-a-list\n---\n\n# bad\n",
            plan_id="plan-order-core",
        )

        result = apply_roadmap_seeds(
            env.slug,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            allow_apply=True,
            yes=True,
        )

        assert result.outcome == APPLY_OUTCOME_REFUSED
        assert result.refused_drafts[0].state == DRAFT_SEED_STATE_MALFORMED
        assert not env.plan_seeds_dir.exists()

    def test_apply_refuses_a_current_digest_draft_with_no_risks(
        self, tmp_path: Path
    ) -> None:
        env = _apply_env(tmp_path)
        _standard_apply_setup(env)
        source = resolve_draft_seed_path(
            env.plans_dir, env.slug, _PLAN_AUTH.draft_seed_path
        )
        text = source.read_text(encoding="utf-8").replace(
            "## Risks\n\n- A risk the accepted roadmap already states.\n\n", ""
        )
        assert "## Risks" not in text
        source.write_text(text, encoding="utf-8")
        _set_seed_state_value(env, _PLAN_AUTH.id, "digest", digest_text(text))

        result = apply_roadmap_seeds(
            env.slug,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            allow_apply=True,
            yes=True,
        )

        assert result.outcome == APPLY_OUTCOME_REFUSED
        assert result.refused_drafts[0].state == DRAFT_SEED_STATE_MALFORMED
        assert not env.plan_seeds_dir.exists()

    def test_apply_refuses_stale_draft(self, tmp_path: Path) -> None:
        env = _apply_env(tmp_path)
        _standard_apply_setup(env)
        state_path = seed_state_path(env.roadmap_root)
        state = load_seed_state(state_path)
        state["seeds"]["plan-auth"]["status"] = "invalidated"
        write_seed_state(state_path, state)

        result = apply_roadmap_seeds(
            env.slug,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            allow_apply=True,
            yes=True,
        )

        assert result.outcome == APPLY_OUTCOME_REFUSED
        assert result.refused_drafts[0].state == DRAFT_SEED_STATE_STALE
        assert not env.plan_seeds_dir.exists()

    def test_apply_refuses_digest_mismatched_draft(self, tmp_path: Path) -> None:
        env = _apply_env(tmp_path)
        _standard_apply_setup(env)
        draft = resolve_draft_seed_path(
            env.plans_dir, env.slug, "plan-seed-drafts/auth.md"
        )
        draft.write_text(
            _seed_text(components=(), cross_cutting=True, marker="hand edit"),
            encoding="utf-8",
        )

        result = apply_roadmap_seeds(
            env.slug,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            allow_apply=True,
            yes=True,
        )

        assert result.outcome == APPLY_OUTCOME_REFUSED
        assert result.refused_drafts[0].state == DRAFT_SEED_STATE_DIGEST_MISMATCHED
        assert not env.plan_seeds_dir.exists()

    def test_apply_refuses_draft_with_no_sidecar_entry(self, tmp_path: Path) -> None:
        env = _apply_env(tmp_path)
        _standard_apply_setup(env)
        state_path = seed_state_path(env.roadmap_root)
        state = load_seed_state(state_path)
        del state["seeds"]["plan-auth"]
        write_seed_state(state_path, state)

        result = apply_roadmap_seeds(
            env.slug,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            allow_apply=True,
            yes=True,
        )

        assert result.outcome == APPLY_OUTCOME_REFUSED
        assert result.refused_drafts[0].state == DRAFT_SEED_STATE_DIGEST_MISMATCHED
        assert not env.plan_seeds_dir.exists()

    def test_apply_refuses_path_escaping_sidecar_entry(self, tmp_path: Path) -> None:
        env = _apply_env(tmp_path)
        _standard_apply_setup(env)
        state_path = seed_state_path(env.roadmap_root)
        state = load_seed_state(state_path)
        state["seeds"]["plan-auth"]["draft_seed_path"] = "../escape.md"
        write_seed_state(state_path, state)

        result = apply_roadmap_seeds(
            env.slug,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            allow_apply=True,
            yes=True,
        )

        assert result.outcome == APPLY_OUTCOME_REFUSED
        assert result.refused_drafts[0].state == DRAFT_SEED_STATE_PATH_ESCAPING
        assert result.refused_drafts[0].detail
        assert not env.plan_seeds_dir.exists()

    def test_apply_refuses_duplicate_draft_basenames(self, tmp_path: Path) -> None:
        env = _apply_env(tmp_path)
        _standard_apply_setup(env)
        duplicate_order = replace(
            _PLAN_ORDER, draft_seed_path="plan-seed-drafts/auth.md"
        )
        env.write_plans(_plans(plans=(duplicate_order, _PLAN_AUTH)))

        result = apply_roadmap_seeds(
            env.slug,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            allow_apply=True,
            yes=True,
        )

        assert result.outcome == APPLY_OUTCOME_REFUSED
        assert [draft.state for draft in result.refused_drafts] == [
            DRAFT_SEED_STATE_DUPLICATE,
            DRAFT_SEED_STATE_DUPLICATE,
        ]
        assert all(draft.detail for draft in result.refused_drafts)
        assert not env.plan_seeds_dir.exists()

    def test_apply_refusal_carries_detail_and_ordering_sequence(
        self, tmp_path: Path
    ) -> None:
        env = _apply_env(tmp_path)
        _standard_apply_setup(env)
        state_path = seed_state_path(env.roadmap_root)
        state = load_seed_state(state_path)
        state["seeds"]["plan-auth"]["draft_seed_path"] = "../escape.md"
        state["seeds"]["plan-order-core"]["status"] = "invalidated"
        write_seed_state(state_path, state)

        result = apply_roadmap_seeds(
            env.slug,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            allow_apply=True,
            yes=True,
        )

        assert [(draft.plan_id, draft.state) for draft in result.refused_drafts] == [
            ("plan-auth", DRAFT_SEED_STATE_PATH_ESCAPING),
            ("plan-order-core", DRAFT_SEED_STATE_STALE),
        ]
        assert result.refused_drafts[0].detail

    def test_apply_reclassifies_after_confirm_before_commit(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        env = _apply_env(tmp_path)
        _standard_apply_setup(env)
        monkeypatch.setattr(roadmap.sys.stdin, "isatty", lambda: True)
        draft = resolve_draft_seed_path(
            env.plans_dir, env.slug, "plan-seed-drafts/auth.md"
        )

        def edit_then_confirm(_prompt: str) -> str:
            draft.write_text(
                _seed_text(components=(), cross_cutting=True, marker="hand edit"),
                encoding="utf-8",
            )
            return "y"

        result = apply_roadmap_seeds(
            env.slug,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            allow_apply=True,
            prompt_fn=edit_then_confirm,
        )

        assert result.outcome == APPLY_OUTCOME_REFUSED
        assert result.refused_drafts[0].state == DRAFT_SEED_STATE_DIGEST_MISMATCHED
        assert not env.plan_seeds_dir.exists()
        assert not list(env.repo_root.rglob(".*.tmp"))

    def test_apply_refuses_a_post_classification_reference_regression(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        env = _apply_env(tmp_path)
        _standard_apply_setup(env)
        draft = resolve_draft_seed_path(
            env.plans_dir, env.slug, _PLAN_AUTH.draft_seed_path
        )
        invalid = _seed_text(components=(), cross_cutting=True).replace(
            f"- `{DOMAIN_FILENAME}`\n", ""
        )
        original_classify = roadmap.classify_draft_seeds
        classify_calls = 0

        def classify_then_regress(*args: Any, **kwargs: Any):
            nonlocal classify_calls
            classifications = original_classify(*args, **kwargs)
            classify_calls += 1
            if classify_calls == 2:
                draft.write_text(invalid, encoding="utf-8")
            return classifications

        monkeypatch.setattr(roadmap, "classify_draft_seeds", classify_then_regress)

        result = apply_roadmap_seeds(
            env.slug,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            allow_apply=True,
            yes=True,
        )

        assert result.outcome == APPLY_OUTCOME_REFUSED
        assert result.refused_drafts[0].state == DRAFT_SEED_STATE_MALFORMED
        assert DOMAIN_FILENAME in result.refused_drafts[0].detail
        assert not env.plan_seeds_dir.exists()

    def test_apply_commits_fresh_source_when_draft_path_changes_during_confirm(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        env = _apply_env(tmp_path)
        _standard_apply_setup(env)
        env.capture_writer_token(monkeypatch)
        monkeypatch.setattr(roadmap.sys.stdin, "isatty", lambda: True)

        def revise_then_confirm(_prompt: str) -> str:
            env.write_draft(
                "plan-seed-drafts/auth-v2.md",
                _seed_text(
                    components=(),
                    cross_cutting=True,
                    marker="REVALIDATED-NEW-CONTENT",
                ),
                plan_id="plan-auth",
            )
            env.write_plans(
                _plans(
                    plans=(
                        _PLAN_ORDER,
                        replace(
                            _PLAN_AUTH,
                            draft_seed_path="plan-seed-drafts/auth-v2.md",
                        ),
                    )
                )
            )
            return "y"

        result = apply_roadmap_seeds(
            env.slug,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            allow_apply=True,
            prompt_fn=revise_then_confirm,
        )

        assert result.outcome == APPLY_OUTCOME_APPLIED
        promoted = env.plan_seeds_dir / "plan-auth.md"
        assert "REVALIDATED-NEW-CONTENT" in promoted.read_text(encoding="utf-8")

    def test_apply_recheck_refuses_revision_with_changed_component_ids(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        env = _apply_env(tmp_path)
        _standard_apply_setup(env)
        env.capture_writer_token(monkeypatch)
        monkeypatch.setattr(roadmap.sys.stdin, "isatty", lambda: True)

        def revise_then_confirm(_prompt: str) -> str:
            env.write_plans(
                _plans(plans=(replace(_PLAN_ORDER, component_ids=()), _PLAN_AUTH))
            )
            return "y"

        result = apply_roadmap_seeds(
            env.slug,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            allow_apply=True,
            prompt_fn=revise_then_confirm,
        )

        assert result.outcome == APPLY_OUTCOME_REFUSED
        assert result.refused_drafts[0].plan_id == "plan-order-core"
        assert result.refused_drafts[0].state == DRAFT_SEED_STATE_MALFORMED
        assert not env.plan_seeds_dir.exists()

    def test_apply_recheck_refuses_target_dropped_during_confirm(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        env = _apply_env(tmp_path)
        _standard_apply_setup(env)
        env.capture_writer_token(monkeypatch)
        monkeypatch.setattr(roadmap.sys.stdin, "isatty", lambda: True)

        def drop_then_confirm(_prompt: str) -> str:
            env.write_plans(
                _plans(
                    plans=(_PLAN_ORDER,),
                    ordering=(OrderingEntry(plan_id="plan-order-core"),),
                    assumptions=(),
                    decisions=(),
                )
            )
            return "y"

        result = apply_roadmap_seeds(
            env.slug,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            allow_apply=True,
            prompt_fn=drop_then_confirm,
        )

        assert result.outcome == APPLY_OUTCOME_REFUSED
        assert [target[0] for target in result.targets] == [
            "plan-auth",
            "plan-order-core",
        ]
        assert result.refused_drafts[0].plan_id == "plan-auth"
        assert result.refused_drafts[0].state == DRAFT_SEED_STATE_MISSING
        assert "no longer present" in result.refused_drafts[0].detail
        assert not env.plan_seeds_dir.exists()

    def test_register_seed_promotions_skips_a_plan_row_added_after_source_texts_were_computed(
        self, tmp_path: Path
    ) -> None:
        """A plan row added to the roadmap during the apply confirm wait has
        no promoted snapshot in ``source_text_by_plan_id`` and must not be
        recorded. Regression: iterating ``artifact.plans`` (which now
        includes the added row) instead of the plans actually promoted
        raised ``KeyError`` looking up that row's digest."""
        env = _apply_env(tmp_path)
        _standard_apply_setup(env)
        applied = apply_roadmap_seeds(
            env.slug,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            allow_apply=True,
            yes=True,
        )
        assert applied.outcome == APPLY_OUTCOME_APPLIED

        added_plan = replace(
            _PLAN_ORDER, id="plan-extra", draft_seed_path="plan-seed-drafts/extra.md"
        )
        fresh_artifact = _plans(plans=(_PLAN_ORDER, _PLAN_AUTH, added_plan))

        roadmap._register_roadmap_seed_promotions(
            fresh_artifact,
            plans_dir=env.plans_dir,
            slug=env.slug,
            source_text_by_plan_id={
                "plan-order-core": "order text",
                "plan-auth": "auth text",
            },
        )

        entries = load_seed_state(seed_state_path(env.roadmap_root))["seeds"]
        assert set(entries) == {"plan-order-core", "plan-auth"}

    def test_apply_corrupt_sidecar_raises_roadmap_error(self, tmp_path: Path) -> None:
        env = _apply_env(tmp_path)
        _standard_apply_setup(env)
        seed_state_path(env.roadmap_root).write_text("not json\n", encoding="utf-8")

        with pytest.raises(RoadmapError, match="cannot read roadmap seed state"):
            apply_roadmap_seeds(
                env.slug,
                repo_root=env.repo_root,
                plans_dir=env.plans_dir,
                allow_apply=True,
                yes=True,
            )

    def test_apply_run_log_counts_each_refused_draft_state(
        self, tmp_path: Path
    ) -> None:
        env = _apply_env(tmp_path)
        _standard_apply_setup(env)
        resolve_draft_seed_path(
            env.plans_dir, env.slug, "plan-seed-drafts/auth.md"
        ).unlink()
        state_path = seed_state_path(env.roadmap_root)
        state = load_seed_state(state_path)
        state["seeds"]["plan-order-core"]["status"] = "invalidated"
        write_seed_state(state_path, state)

        result = apply_roadmap_seeds(
            env.slug,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            allow_apply=True,
            yes=True,
        )

        logs = list((env.repo_root / ".plan-tool" / "runs" / env.slug).glob("*.jsonl"))
        event = next(
            event
            for event in read_run_events(logs[0])
            if event["event"] == "roadmap_seed_apply_result"
        )
        assert result.outcome == APPLY_OUTCOME_REFUSED
        assert event["missing_draft_count"] == 1
        assert event["stale_draft_count"] == 1
        assert event["malformed_draft_count"] == 0
        assert event["path_escaping_draft_count"] == 0
        assert event["duplicate_draft_count"] == 0
        assert event["digest_mismatched_draft_count"] == 0

    def test_apply_refused_when_ordering_plan_missing(self, tmp_path: Path) -> None:
        env = _apply_env(tmp_path)
        env.write_plans(
            _plans(
                ordering=(
                    OrderingEntry(plan_id="plan-auth"),
                    OrderingEntry(plan_id="plan-missing"),
                )
            )
        )
        env.write_draft(
            "plan-seed-drafts/auth.md", _seed_text(components=(), cross_cutting=True)
        )

        result = apply_roadmap_seeds(
            env.slug,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            allow_apply=True,
            yes=True,
        )

        assert result.outcome == APPLY_OUTCOME_REFUSED
        assert result.bijection_error is not None
        assert "ordering" in result.bijection_error

    def test_apply_refused_when_plan_absent_from_ordering(self, tmp_path: Path) -> None:
        env = _apply_env(tmp_path)
        env.write_plans(_plans(ordering=(OrderingEntry(plan_id="plan-order-core"),)))
        env.write_draft(
            "plan-seed-drafts/order-core.md",
            _seed_text(components=("component-checkout",)),
        )

        result = apply_roadmap_seeds(
            env.slug,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            allow_apply=True,
            yes=True,
        )

        assert result.outcome == APPLY_OUTCOME_REFUSED
        assert result.bijection_error is not None
        assert "plan-auth" in result.bijection_error

    def test_apply_creates_plan_seeds_dir(self, tmp_path: Path) -> None:
        env = _apply_env(tmp_path)
        _standard_apply_setup(env)
        assert not env.plan_seeds_dir.exists()

        apply_roadmap_seeds(
            env.slug,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            allow_apply=True,
            yes=True,
        )

        assert env.plan_seeds_dir.is_dir()
        assert (env.plan_seeds_dir / "plan-auth.md").is_file()

    def test_apply_confirm_declined_returns_recommended(self, tmp_path: Path) -> None:
        env = _apply_env(tmp_path)
        _standard_apply_setup(env)

        result = apply_roadmap_seeds(
            env.slug,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            allow_apply=True,
            prompt_fn=lambda _prompt: "n",
        )

        assert result.outcome == APPLY_OUTCOME_RECOMMENDED
        assert not env.plan_seeds_dir.exists()

    def test_apply_non_tty_without_yes_returns_recommended(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        env = _apply_env(tmp_path)
        _standard_apply_setup(env)
        monkeypatch.setattr(roadmap.sys.stdin, "isatty", lambda: False)

        result = apply_roadmap_seeds(
            env.slug,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            allow_apply=True,
        )

        assert result.outcome == APPLY_OUTCOME_RECOMMENDED
        assert not env.plan_seeds_dir.exists()

    def test_apply_never_invokes_roadmap_backend(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        env = _apply_env(tmp_path)
        _standard_apply_setup(env)

        def boom(_prompt: str) -> tuple[int, str]:
            raise AssertionError("shell_roadmap_invoker must not run on --apply")

        monkeypatch.setattr(roadmap, "shell_roadmap_invoker", boom)

        result = apply_roadmap_seeds(
            env.slug,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            allow_apply=True,
            yes=True,
        )

        assert result.outcome == APPLY_OUTCOME_APPLIED
        assert (env.plan_seeds_dir / "plan-auth.md").is_file()


# --------------------------------------------------------------------------
# The first stage run holds results, then publishes the root version
# --------------------------------------------------------------------------


def _spy_on_published_generation(
    monkeypatch: pytest.MonkeyPatch,
) -> list[PendingGeneration]:
    """Record every generation the stage run publishes, and still publish it."""
    captured: list[PendingGeneration] = []
    original = roadmap.publish_roadmap_generation

    def spy(generation: PendingGeneration, **kwargs: Any) -> None:
        captured.append(generation)
        original(generation, **kwargs)

    monkeypatch.setattr(roadmap, "publish_roadmap_generation", spy)
    return captured


def _fail_stage_four(env: _Env) -> RoadmapResult:
    """A run whose stage 4 exhausts, leaving stages 1-3 held for a resume."""
    broken_plans = _plans_artifact_text(plans=(_PLAN_ORDER,))
    return env.run(
        stages=roadmap.STAGES,
        invoker=_StubInvoker(
            _domain_text(), _constraints_text(), _components_text(), broken_plans
        ),
        max_stage_attempts=1,
    )


def _tree_snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _make_pre_head_state(env: _Env, kind: str) -> Path:
    """Create one kind of pre-head roadmap state; return the path the refusal names."""
    root = roadmap_dir(env.plans_dir, SLUG)
    root.mkdir(parents=True, exist_ok=True)
    if kind == "stage-file":
        path = root / DOMAIN_FILENAME
        path.write_text(_domain_text(), encoding="utf-8")
        return path
    if kind == "ledger":
        path = roadmap_feedback_ledger_path(env.plans_dir, SLUG)
        path.write_text("not: a real ledger\n", encoding="utf-8")
        return path
    if kind == "seed-state":
        path = seed_state_path(root)
        path.write_text('{"version": 1, "seeds": {}}\n', encoding="utf-8")
        return path
    if kind == "version-store":
        stored = version_namespace_path(env.plans_dir, SLUG) / ("a" * 64) / "version.json"
        stored.parent.mkdir(parents=True)
        stored.write_text("{}\n", encoding="utf-8")
        return version_namespace_path(env.plans_dir, SLUG)
    assert kind == "draft-seed"
    draft = draft_seeds_dir(env.plans_dir, SLUG) / "plan-a.md"
    draft.parent.mkdir(parents=True)
    draft.write_text("# a draft\n", encoding="utf-8")
    return draft_seeds_dir(env.plans_dir, SLUG)


class TestFirstRunPublishesTheRootVersion:
    def test_first_run_publishes_one_root_version_and_head_after_stage_four(
        self, shipped_env: _Env
    ) -> None:
        result = shipped_env.run(stages=roadmap.STAGES, invoker=_four_stage_invoker())

        accepted = load_accepted_version(plans_dir=shipped_env.plans_dir, slug=SLUG)
        assert accepted is not None
        stored = sorted(
            entry.name
            for entry in version_namespace_path(shipped_env.plans_dir, SLUG).iterdir()
            if entry.is_dir()
        )
        assert result.outcome == OUTCOME_COMPLETED
        assert stored == [accepted.record.version_id]
        assert accepted.brief_bytes == BRIEF.encode("utf-8")
        assert accepted_head_path(shipped_env.plans_dir, SLUG).is_file()

    def test_a_failing_resume_cleanup_after_the_head_commit_warns_and_still_completes(
        self,
        shipped_env: _Env,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """The head is committed, so a cleanup OSError must not report the run as failed."""

        def _boom(repo_root: Path, slug: str) -> None:
            raise OSError("resume dir busy")

        monkeypatch.setattr(roadmap, "delete_resume", _boom)

        result = shipped_env.run(stages=roadmap.STAGES, invoker=_four_stage_invoker())

        assert result.outcome == OUTCOME_COMPLETED
        assert accepted_head_path(shipped_env.plans_dir, SLUG).is_file()
        assert load_accepted_version(plans_dir=shipped_env.plans_dir, slug=SLUG) is not None
        assert "resume dir busy" in capsys.readouterr().err

    def test_published_artifacts_are_the_canonical_held_stage_texts(
        self, shipped_env: _Env
    ) -> None:
        shipped_env.run(stages=roadmap.STAGES, invoker=_four_stage_invoker())

        accepted = load_accepted_version(plans_dir=shipped_env.plans_dir, slug=SLUG)
        assert accepted is not None
        assert [member.decode("utf-8") for member in accepted.artifact_bytes] == [
            _domain_text(),
            _constraints_text(),
            _components_text(),
            _plans_text(),
        ]

    def test_first_run_writes_no_top_level_stage_files(self, shipped_env: _Env) -> None:
        shipped_env.run(stages=roadmap.STAGES, invoker=_four_stage_invoker())

        assert not list(roadmap_dir(shipped_env.plans_dir, SLUG).glob("[0-9][0-9]-*.md"))

    @pytest.mark.parametrize("stage_four_fails", (False, True), ids=("success", "failed-run"))
    def test_first_run_writes_no_baseline_checkpoint_or_source_json(
        self, shipped_env: _Env, stage_four_fails: bool
    ) -> None:
        if stage_four_fails:
            _fail_stage_four(shipped_env)
        else:
            shipped_env.run(stages=roadmap.STAGES, invoker=_four_stage_invoker())

        root = roadmap_dir(shipped_env.plans_dir, SLUG)
        assert not _source_json_path(shipped_env.plans_dir).exists()
        assert not (root / ".roadmap-revision-checkpoint.json").exists()
        assert not (root / ".roadmap-baselines").exists()

    def test_head_is_written_last_in_the_published_generation(
        self, shipped_env: _Env, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured = _spy_on_published_generation(monkeypatch)

        shipped_env.run(stages=roadmap.STAGES, invoker=_four_stage_invoker())

        (generation,) = captured
        paths = [member.relative_path for member in generation.members]
        ledger = roadmap_feedback_ledger_path(shipped_env.plans_dir, SLUG)
        root = roadmap_dir(shipped_env.plans_dir, SLUG)
        assert generation.kind == "root-enrollment"
        assert paths[-1].endswith(ACCEPTED_HEAD_FILENAME)
        assert not any(path.endswith(ACCEPTED_HEAD_FILENAME) for path in paths[:-1])
        assert ledger.relative_to(root).as_posix() in paths[:-1]

    def test_later_stage_gates_see_earlier_results_from_memory(
        self, shipped_env: _Env
    ) -> None:
        recorder = _GateRecorder()
        stages = (
            roadmap.STAGES[0],
            replace(roadmap.STAGES[1], gates=recorder),
            *roadmap.STAGES[2:],
        )

        class TamperingInvoker(_StubInvoker):
            def __call__(self, prompt: str) -> tuple[int, str]:
                if self.calls == 1:
                    # About to author stage 2: damage stage 1's held copy.
                    shipped_env.held_stage_file(1).write_text("garbage", encoding="utf-8")
                return super().__call__(prompt)

        invoker = TamperingInvoker(
            _domain_text(), _constraints_text(), _components_text(), _plans_text()
        )

        result = shipped_env.run(stages=stages, invoker=invoker)

        assert result.outcome == OUTCOME_COMPLETED
        assert recorder.envelopes[0].domain == _domain()
        assert _domain_text() in invoker.prompts[1]
        accepted = load_accepted_version(plans_dir=shipped_env.plans_dir, slug=SLUG)
        assert accepted is not None
        assert accepted.artifact_bytes[0].decode("utf-8") == _domain_text()

    def test_failed_stage_four_leaves_only_the_resume_directory_holding_stages_one_to_three(
        self, shipped_env: _Env
    ) -> None:
        result = _fail_stage_four(shipped_env)

        resume = resume_dir_path(shipped_env.repo_root, SLUG)
        assert result.outcome == OUTCOME_STAGE_EXHAUSTED
        assert result.failed_stage == 4
        assert sorted(entry.name for entry in resume.iterdir()) == [
            "brief.digest",
            "stage-1.md",
            "stage-2.md",
            "stage-3.md",
        ]
        assert not roadmap_dir(shipped_env.plans_dir, SLUG).exists()

    def test_rerun_after_stage_four_failure_does_not_call_the_invoker_for_stages_one_to_three(
        self, shipped_env: _Env
    ) -> None:
        _fail_stage_four(shipped_env)
        statuses: list[str] = []
        invoker = _StubInvoker(_plans_text())

        result = shipped_env.run(
            stages=roadmap.STAGES, invoker=invoker, status_callback=statuses.append
        )

        assert result.outcome == OUTCOME_COMPLETED
        assert invoker.calls == 1
        assert result.stages_run == (4,)
        assert [status for status in statuses if status.endswith("re-gated without write")] == [
            "roadmap storefront: stage 1 (domain) re-gated without write",
            "roadmap storefront: stage 2 (constraints) re-gated without write",
            "roadmap storefront: stage 3 (components) re-gated without write",
        ]
        assert accepted_head_path(shipped_env.plans_dir, SLUG).is_file()

    def test_exhausted_stage_halts_the_arc_and_never_calls_the_next_invoker(
        self, shipped_env: _Env
    ) -> None:
        failing_constraints = replace(
            roadmap.STAGES[1], gates=_GateRecorder((_violation("never satisfied"),))
        )
        stages = (roadmap.STAGES[0], failing_constraints, *roadmap.STAGES[2:])
        invoker = _StubInvoker(_domain_text(), _constraints_text(), _components_text())

        result = shipped_env.run(stages=stages, invoker=invoker, max_stage_attempts=2)

        assert result.outcome == OUTCOME_STAGE_EXHAUSTED
        assert result.failed_stage == 2
        assert result.stages_run == (1, 2)
        assert invoker.calls == 3
        assert not shipped_env.held_stage_file(3).exists()

    def test_resume_directory_survives_until_the_head_commits(
        self, shipped_env: _Env, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def failing_publish(*_args: Any, **_kwargs: Any) -> None:
            raise roadmap.RoadmapRevisionPublishError("injected publish failure")

        monkeypatch.setattr(roadmap, "publish_roadmap_generation", failing_publish)

        with pytest.raises(RoadmapError, match="injected publish failure"):
            shipped_env.run(stages=roadmap.STAGES, invoker=_four_stage_invoker())

        assert [shipped_env.held_stage_file(n).is_file() for n in (1, 2, 3, 4)] == [True] * 4
        assert not accepted_head_path(shipped_env.plans_dir, SLUG).exists()

    def test_resume_directory_is_deleted_only_after_head_commits(
        self, shipped_env: _Env, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        resume = resume_dir_path(shipped_env.repo_root, SLUG)
        observed: list[tuple[str, bool, bool]] = []
        original = roadmap.publish_roadmap_generation

        def observing_publish(generation: PendingGeneration, **kwargs: Any) -> None:
            head = accepted_head_path(shipped_env.plans_dir, SLUG)
            observed.append(("before", resume.is_dir(), head.exists()))
            original(generation, **kwargs)
            observed.append(("after", resume.is_dir(), head.exists()))

        monkeypatch.setattr(roadmap, "publish_roadmap_generation", observing_publish)

        shipped_env.run(stages=roadmap.STAGES, invoker=_four_stage_invoker())

        assert observed == [("before", True, False), ("after", True, True)]
        assert not resume.exists()
        assert accepted_head_path(shipped_env.plans_dir, SLUG).is_file()

    def test_run_refuses_when_an_accepted_head_exists_without_reading_the_brief(
        self, shipped_env: _Env
    ) -> None:
        shipped_env.run(stages=roadmap.STAGES, invoker=_four_stage_invoker())
        accepted = load_accepted_version(plans_dir=shipped_env.plans_dir, slug=SLUG)
        assert accepted is not None
        missing_brief = shipped_env.repo_root / "no-such-brief.md"

        with pytest.raises(RoadmapHeadExistsError) as excinfo:
            shipped_env.run(
                stages=roadmap.STAGES, invoker=_never_called, brief_path=missing_brief
            )

        message = str(excinfo.value)
        assert accepted.record.version_id in message
        assert "feedback and review, not through a stage run" in message
        assert "not readable" not in message

    def test_post_head_stage_refusal_refreshes_the_index(self, shipped_env: _Env) -> None:
        """The refusal still raises, and also rewrites INDEX.md so a crash after the head commit heals."""
        from plan_tool.roadmap_index import INDEX_FILENAME

        shipped_env.run(stages=roadmap.STAGES, invoker=_four_stage_invoker())
        index = roadmap_dir(shipped_env.plans_dir, SLUG) / INDEX_FILENAME
        index.write_text("stale\n", encoding="utf-8")

        with pytest.raises(RoadmapHeadExistsError):
            shipped_env.run(stages=roadmap.STAGES, invoker=_never_called)

        assert index.read_text(encoding="utf-8") != "stale\n"
        assert "stale" not in index.read_text(encoding="utf-8")

    def test_resume_directory_beside_an_accepted_head_is_deleted_on_refusal(
        self, shipped_env: _Env
    ) -> None:
        shipped_env.run(stages=roadmap.STAGES, invoker=_four_stage_invoker())
        write_brief_digest(shipped_env.repo_root, SLUG, "0" * 64)
        write_stage(shipped_env.repo_root, SLUG, 1, _domain_text())
        resume = resume_dir_path(shipped_env.repo_root, SLUG)
        assert resume.is_dir()

        with pytest.raises(RoadmapHeadExistsError):
            shipped_env.run(stages=roadmap.STAGES, invoker=_never_called)

        assert not resume.exists()

    def test_a_failing_resume_cleanup_beside_an_accepted_head_still_refuses_and_refreshes_the_index(
        self,
        shipped_env: _Env,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """The head refusal and index repair are independent of the cleanup outcome."""
        shipped_env.run(stages=roadmap.STAGES, invoker=_four_stage_invoker())
        index = roadmap_dir(shipped_env.plans_dir, SLUG) / "INDEX.md"
        index.write_text("stale\n", encoding="utf-8")

        def _boom(repo_root: Path, slug: str) -> None:
            raise OSError("resume dir busy")

        monkeypatch.setattr(roadmap, "delete_resume", _boom)

        with pytest.raises(RoadmapHeadExistsError):
            shipped_env.run(stages=roadmap.STAGES, invoker=_never_called)

        assert "resume dir busy" in capsys.readouterr().err
        assert "stale" not in index.read_text(encoding="utf-8")

    def test_stages_after_a_damaged_stage_are_discarded_so_a_later_run_cannot_regate_them(
        self, shipped_env: _Env
    ) -> None:
        """Stale stage 3 must not survive a run that regenerates stage 2 then exhausts at 3."""
        _fail_stage_four(shipped_env)
        shipped_env.held_stage_file(2).write_bytes(b"\xff\xfe\xfd")
        failing_components = replace(
            roadmap.STAGES[2], gates=_GateRecorder((_violation("never satisfied"),))
        )
        stages = (*roadmap.STAGES[:2], failing_components, roadmap.STAGES[3])

        result = shipped_env.run(
            stages=stages,
            invoker=_StubInvoker(_constraints_text(), _components_text()),
            max_stage_attempts=1,
        )

        assert result.outcome == OUTCOME_STAGE_EXHAUSTED
        assert result.failed_stage == 3
        assert shipped_env.held_stage_file(2).exists()
        assert not shipped_env.held_stage_file(3).exists()

    def test_a_held_stage_that_is_unreadable_is_regenerated_with_a_warning(
        self, shipped_env: _Env
    ) -> None:
        _fail_stage_four(shipped_env)
        shipped_env.held_stage_file(2).write_bytes(b"\xff\xfe\xfd")
        statuses: list[str] = []
        invoker = _StubInvoker(_constraints_text(), _components_text(), _plans_text())

        result = shipped_env.run(
            stages=roadmap.STAGES, invoker=invoker, status_callback=statuses.append
        )

        assert result.outcome == OUTCOME_COMPLETED
        assert invoker.calls == 3
        assert result.stages_run == (2, 3, 4)
        assert any("stage-2.md" in status and "warning" in status for status in statuses)
        assert "roadmap storefront: stage 1 (domain) re-gated without write" in statuses

    def test_a_held_stage_that_fails_its_regate_is_regenerated_with_the_stages_after_it(
        self, shipped_env: _Env
    ) -> None:
        _fail_stage_four(shipped_env)
        shipped_env.held_stage_file(2).write_text(
            _constraints_text(anchor="no-such-row"), encoding="utf-8"
        )
        statuses: list[str] = []
        files_at_first_call: list[list[bool]] = []

        class Invoker(_StubInvoker):
            def __call__(self, prompt: str) -> tuple[int, str]:
                if not self.calls:
                    files_at_first_call.append(
                        [shipped_env.held_stage_file(n).exists() for n in (1, 2, 3)]
                    )
                return super().__call__(prompt)

        invoker = Invoker(_constraints_text(), _components_text(), _plans_text())

        result = shipped_env.run(
            stages=roadmap.STAGES, invoker=invoker, status_callback=statuses.append
        )

        assert result.outcome == OUTCOME_COMPLETED
        assert result.stages_run == (2, 3, 4)
        assert invoker.calls == 3
        # Before stage 2 regenerates, the failing file and the stale stage 3 are gone.
        assert files_at_first_call == [[True, False, False]]
        assert any("stage-2.md" in status and "warning" in status for status in statuses)

    def test_an_unverifiable_brief_digest_regenerates_every_held_stage_with_a_warning(
        self, shipped_env: _Env
    ) -> None:
        """Deliberately not a refusal: only a *differing* digest refuses."""
        _fail_stage_four(shipped_env)
        (resume_dir_path(shipped_env.repo_root, SLUG) / "brief.digest").write_text(
            "not-a-digest\n", encoding="utf-8"
        )
        statuses: list[str] = []
        invoker = _four_stage_invoker()

        result = shipped_env.run(
            stages=roadmap.STAGES, invoker=invoker, status_callback=statuses.append
        )

        assert result.outcome == OUTCOME_COMPLETED
        assert invoker.calls == 4
        assert any("brief.digest" in status and "warning" in status for status in statuses)

    @pytest.mark.parametrize(
        "kinds",
        (
            ("stage-file",),
            ("ledger",),
            ("seed-state",),
            ("version-store",),
            ("draft-seed",),
            ("stage-file", "ledger"),
        ),
        ids=lambda kinds: "+".join(kinds),
    )
    def test_folder_with_pre_head_state_refuses_naming_every_path_found(
        self, shipped_env: _Env, kinds: tuple[str, ...]
    ) -> None:
        expected = [_make_pre_head_state(shipped_env, kind) for kind in kinds]
        root = roadmap_dir(shipped_env.plans_dir, SLUG)
        before = _tree_snapshot(root)

        with pytest.raises(RoadmapPreHeadStateError) as excinfo:
            shipped_env.run(stages=roadmap.STAGES, invoker=_never_called)

        message = str(excinfo.value)
        assert all(str(path) in message for path in expected)
        assert "by hand" in message
        assert "successor slug" in message
        assert "migrat" not in message.lower()
        assert _tree_snapshot(root) == before

    def test_stray_durable_write_temp_files_are_not_pre_head_state(
        self, shipped_env: _Env
    ) -> None:
        """A SIGKILL mid-write leaves `.<name>.<random>.tmp`; it is never stored state."""
        namespace = version_namespace_path(shipped_env.plans_dir, SLUG)
        version_dir = namespace / ("a" * 64)
        version_dir.mkdir(parents=True)
        (version_dir / ".version.json.k3j2h1.tmp").write_bytes(b"partial")
        (namespace / f".{accepted_head_path(shipped_env.plans_dir, SLUG).name}.x9y8.tmp").write_bytes(
            b"partial"
        )

        result = shipped_env.run(stages=roadmap.STAGES, invoker=_four_stage_invoker())

        assert result.outcome == OUTCOME_COMPLETED

    @pytest.mark.parametrize("name", ("version.json", "notes.tmp", ".hidden", "x.tmp"))
    def test_a_real_stored_file_still_refuses_even_when_it_resembles_a_temp_name(
        self, shipped_env: _Env, name: str
    ) -> None:
        """Only the exact `.<name>.<random>.tmp` shape is exempt; every other file is state."""
        version_dir = version_namespace_path(shipped_env.plans_dir, SLUG) / ("a" * 64)
        version_dir.mkdir(parents=True)
        (version_dir / name).write_bytes(b"{}")

        with pytest.raises(RoadmapPreHeadStateError):
            shipped_env.run(stages=roadmap.STAGES, invoker=_never_called)

    def test_pending_root_journal_is_recovered_before_the_resume_directory_is_read(
        self, shipped_env: _Env, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured = _spy_on_published_generation(monkeypatch)
        shipped_env.run(stages=roadmap.STAGES, invoker=_four_stage_invoker())
        root = roadmap_dir(shipped_env.plans_dir, SLUG)
        journal = pending_generation_path(root)
        journal.write_bytes(render_pending_generation(captured[0]))
        write_brief_digest(shipped_env.repo_root, SLUG, "0" * 64)
        write_stage(shipped_env.repo_root, SLUG, 1, _domain_text())
        shipped_env.brief_path.write_text("A changed brief.\n", encoding="utf-8")

        with pytest.raises(RoadmapHeadExistsError):
            shipped_env.run(stages=roadmap.STAGES, invoker=_never_called)

        assert not journal.exists()

    def test_crash_before_the_head_commit_recovers_then_republishes_instead_of_refusing(
        self, shipped_env: _Env, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured = _spy_on_published_generation(monkeypatch)
        shipped_env.run(stages=roadmap.STAGES, invoker=_four_stage_invoker())
        root = roadmap_dir(shipped_env.plans_dir, SLUG)
        accepted = load_accepted_version(plans_dir=shipped_env.plans_dir, slug=SLUG)
        assert accepted is not None
        # The crash window: members and ledger landed, the head did not.
        accepted_head_path(shipped_env.plans_dir, SLUG).unlink()
        pending_generation_path(root).write_bytes(render_pending_generation(captured[0]))
        write_brief_digest(shipped_env.repo_root, SLUG, digest_decoded_text(BRIEF))
        for number, artifact_bytes in enumerate(accepted.artifact_bytes, start=1):
            write_stage(shipped_env.repo_root, SLUG, number, artifact_bytes.decode("utf-8"))

        result = shipped_env.run(stages=roadmap.STAGES, invoker=_never_called)

        republished = load_accepted_version(plans_dir=shipped_env.plans_dir, slug=SLUG)
        assert result.outcome == OUTCOME_COMPLETED
        assert result.stages_run == ()
        assert republished is not None
        assert republished.record.version_id == accepted.record.version_id
        assert roadmap_feedback_ledger_path(shipped_env.plans_dir, SLUG).is_file()
        assert not pending_generation_path(root).exists()
        assert not resume_dir_path(shipped_env.repo_root, SLUG).exists()

    def test_changed_brief_refuses_with_the_remedy_and_deletes_nothing(
        self, shipped_env: _Env
    ) -> None:
        _fail_stage_four(shipped_env)
        resume = resume_dir_path(shipped_env.repo_root, SLUG)
        before = _tree_snapshot(resume)
        shipped_env.brief_path.write_text("A different concept.\n", encoding="utf-8")

        with pytest.raises(RoadmapError) as excinfo:
            shipped_env.run(stages=roadmap.STAGES, invoker=_never_called)

        message = str(excinfo.value)
        assert "Restore the original brief" in message
        assert "delete" in message and str(resume) in message
        assert "successor slug" in message
        assert _tree_snapshot(resume) == before

    @pytest.mark.parametrize("keyword", ("from_stage", "confirm_brief_rebind"))
    def test_run_roadmap_rejects_the_removed_keywords(
        self, shipped_env: _Env, keyword: str
    ) -> None:
        with pytest.raises(TypeError, match=keyword):
            roadmap.run_roadmap(
                SLUG,
                repo_root=shipped_env.repo_root,
                plans_dir=shipped_env.plans_dir,
                brief_path=shipped_env.brief_path,
                **{keyword: 1 if keyword == "from_stage" else True},
            )

    def test_initial_ledger_is_feedback_free_and_ledger_native(
        self, shipped_env: _Env
    ) -> None:
        shipped_env.run(stages=roadmap.STAGES, invoker=_four_stage_invoker())

        ledger = load_ledger(roadmap_feedback_ledger_path(shipped_env.plans_dir, SLUG))
        assert ledger.ledger_state is LedgerState.LEDGER_NATIVE
        assert ledger.reviewer_feedback_groups == ()


# --------------------------------------------------------------------------
# Seed routes read the accepted version
# --------------------------------------------------------------------------


def _artifact_texts(*, plans: str, domain: Optional[str] = None) -> tuple[str, str, str, str]:
    return (
        domain if domain is not None else _domain_text(),
        _constraints_text(),
        _components_text(),
        plans,
    )


_HEAD_ORDERING = (OrderingEntry(plan_id=_PLAN_ORDER.id), OrderingEntry(plan_id=_PLAN_AUTH.id))


class TestAcceptedVersionSeedRoutes:
    def test_load_accepted_roadmap_artifacts_parses_the_stored_members_in_stage_order(
        self, env: _Env
    ) -> None:
        env.publish_accepted()
        stored = load_accepted_version(plans_dir=env.plans_dir, slug=SLUG)
        assert stored is not None

        loaded = roadmap.load_accepted_roadmap_artifacts(plans_dir=env.plans_dir, slug=SLUG)

        assert [item.stage.number for item in loaded] == [stage.number for stage in roadmap.STAGES]
        assert [item.text.encode("utf-8") for item in loaded] == list(stored.artifact_bytes)
        assert isinstance(loaded[-1].artifact, PlansArtifact)

    def test_loader_raises_no_published_version_error_when_no_accepted_head(
        self, env: _Env
    ) -> None:
        with pytest.raises(NoPublishedRoadmapVersionError, match="no published version"):
            roadmap.load_accepted_roadmap_artifacts(plans_dir=env.plans_dir, slug=SLUG)
        with pytest.raises(NoPublishedRoadmapVersionError):
            roadmap.load_accepted_plans_artifact(plans_dir=env.plans_dir, slug=SLUG)

    def test_no_published_version_message_points_at_hand_conversion_only_when_top_level_files_exist(
        self, env: _Env
    ) -> None:
        bare = no_published_version_message(env.plans_dir, SLUG)
        assert "no published version" in bare
        assert "convert by hand" not in bare

        env.write_domain()

        with_leftover = no_published_version_message(env.plans_dir, SLUG)
        assert "convert by hand" in with_leftover
        assert "docs/how-to/roadmap.md" in with_leftover
        with pytest.raises(NoPublishedRoadmapVersionError, match="convert by hand"):
            roadmap.load_accepted_roadmap_artifacts(plans_dir=env.plans_dir, slug=SLUG)

    def test_loader_never_falls_back_to_top_level_files_beside_an_accepted_head(
        self, env: _Env
    ) -> None:
        """Inert top-level leftovers never shadow the stored version (deliberate carve-out)."""
        env.publish_accepted()
        env.write_plans(_plans_artifact_text(plans=(_PLAN_ORDER,), ordering=_HEAD_ORDERING[:1]))
        env.write_domain(_domain_text() + "\nTOP-LEVEL-LEFTOVER\n")

        loaded = roadmap.load_accepted_roadmap_artifacts(plans_dir=env.plans_dir, slug=SLUG)

        assert [row.id for row in loaded[-1].artifact.plans] == [_PLAN_ORDER.id, _PLAN_AUTH.id]
        assert "TOP-LEVEL-LEFTOVER" not in loaded[0].text
        assert env.plans_file not in {item.path for item in loaded}

    def test_refresh_seeds_runs_on_an_accepted_head_that_advanced_past_its_root(
        self, env: _Env
    ) -> None:
        _prepare_seed_materialization(env)
        advance_accepted_head(
            env.plans_dir,
            SLUG,
            _artifact_texts(
                plans=_plans_artifact_text(
                    plans=(_PLAN_ORDER,), ordering=_HEAD_ORDERING[:1], assumptions=(), decisions=()
                )
            ),
        )

        result = refresh_roadmap_seeds(
            SLUG,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            invoker=_StubInvoker(_seed_text(marker="HEAD-ROW")),
        )

        assert result.outcome == SEED_REFRESH_OUTCOME_APPLIED
        assert [change.plan_id for change in result.changes] == [_PLAN_ORDER.id]
        assert resolve_draft_seed_path(
            env.plans_dir, SLUG, _PLAN_ORDER.draft_seed_path
        ).is_file()
        assert not resolve_draft_seed_path(
            env.plans_dir, SLUG, _PLAN_AUTH.draft_seed_path
        ).exists()
        entries = load_seed_state(seed_state_path(roadmap_dir(env.plans_dir, SLUG)))["seeds"]
        assert set(entries) == {_PLAN_ORDER.id}

    def test_materialize_prompt_embeds_the_accepted_versions_artifact_text(
        self, env: _Env
    ) -> None:
        env.write_domain(_domain_text() + "\nTOP-LEVEL-ONLY-DOMAIN\n")
        _prepare_seed_materialization(env)
        head_domain = _domain_text() + "\nHEAD-ONLY-DOMAIN\n"
        advance_accepted_head(
            env.plans_dir, SLUG, _artifact_texts(plans=_plans_artifact_text(), domain=head_domain)
        )
        invoker = _StubInvoker(_seed_text())
        accepted = load_accepted_version(plans_dir=env.plans_dir, slug=SLUG)
        head_bytes = accepted_head_path(env.plans_dir, SLUG).read_bytes()

        _materialize(env, invoker)

        assert head_domain in invoker.prompts[0]
        assert "TOP-LEVEL-ONLY-DOMAIN" not in invoker.prompts[0]
        assert accepted_head_path(env.plans_dir, SLUG).read_bytes() == head_bytes
        assert load_accepted_version(plans_dir=env.plans_dir, slug=SLUG) == accepted

    def test_accept_seed_records_digest_and_keeps_published_flag_on_an_advanced_head(
        self, tmp_path: Path
    ) -> None:
        env = _apply_env(tmp_path)
        _standard_apply_setup(env)
        moved = replace(_PLAN_AUTH, draft_seed_path="plan-seed-drafts/auth-v2.md")
        advance_accepted_head(
            env.plans_dir,
            env.slug,
            _artifact_texts(plans=render_plans_artifact(_plans(plans=(_PLAN_ORDER, moved)))),
        )
        edited = _seed_text(components=(), cross_cutting=True, marker="HEAD-EDITED-AUTH")
        source = env.write_draft("plan-seed-drafts/auth-v2.md", edited)
        state_path = seed_state_path(env.roadmap_root)
        state = load_seed_state(state_path)
        state["seeds"][_PLAN_AUTH.id]["published"] = True
        write_seed_state(state_path, state)
        promoted = env.plan_seeds_dir / f"{_PLAN_AUTH.id}.md"
        promoted.parent.mkdir()
        promoted.write_text("old promoted seed\n", encoding="utf-8")

        result = accept_roadmap_seed(
            env.slug, _PLAN_AUTH.id, repo_root=env.repo_root, plans_dir=env.plans_dir
        )

        entry = load_seed_state(state_path)["seeds"][_PLAN_AUTH.id]
        assert result.outcome == ACCEPT_OUTCOME_ACCEPTED
        assert result.target == source
        assert entry["digest"] == digest_text(edited)
        assert entry["draft_seed_path"] == "plan-seed-drafts/auth-v2.md"
        assert entry["published"] is True
        assert "HEAD-EDITED-AUTH" in promoted.read_text(encoding="utf-8")

    def test_apply_seeds_promotes_ordered_targets_from_the_accepted_plans_artifact(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        env = _apply_env(tmp_path)
        _standard_apply_setup(env)
        env.capture_writer_token(monkeypatch)
        monkeypatch.setattr(roadmap.sys.stdin, "isatty", lambda: True)
        advance_accepted_head(
            env.plans_dir,
            env.slug,
            _artifact_texts(plans=_plans_artifact_text(ordering=_HEAD_ORDERING)),
        )
        moved = replace(_PLAN_AUTH, draft_seed_path="plan-seed-drafts/auth-v2.md")
        moved_head = _artifact_texts(
            plans=render_plans_artifact(
                _plans(plans=(_PLAN_ORDER, moved), ordering=_HEAD_ORDERING)
            )
        )

        def move_draft_then_confirm(_prompt: str) -> str:
            env.write_draft(
                "plan-seed-drafts/auth-v2.md",
                _seed_text(components=(), cross_cutting=True, marker="MOVED-ON-HEAD"),
                plan_id=_PLAN_AUTH.id,
            )
            advance_accepted_head(env.plans_dir, env.slug, moved_head)
            return "y"

        recommended = apply_roadmap_seeds(
            env.slug, repo_root=env.repo_root, plans_dir=env.plans_dir, allow_apply=False
        )
        applied = apply_roadmap_seeds(
            env.slug,
            repo_root=env.repo_root,
            plans_dir=env.plans_dir,
            allow_apply=True,
            prompt_fn=move_draft_then_confirm,
        )

        ordered = [_PLAN_ORDER.id, _PLAN_AUTH.id]
        assert [plan_id for plan_id, _s, _d in recommended.targets] == ordered
        assert applied.outcome == APPLY_OUTCOME_APPLIED
        assert [plan_id for plan_id, _s, _d in applied.promotions] == ordered
        # The post-confirm freshness re-check reloads the head, so its moved draft is promoted.
        assert "MOVED-ON-HEAD" in (env.plan_seeds_dir / f"{_PLAN_AUTH.id}.md").read_text(
            encoding="utf-8"
        )

    def test_apply_refuses_with_no_published_version_and_writes_nothing(
        self, tmp_path: Path
    ) -> None:
        env = _apply_env(tmp_path)
        env.write_draft("plan-seed-drafts/auth.md", _seed_text(), plan_id=_PLAN_AUTH.id)
        env.roadmap_root.joinpath(PLANS_FILENAME).write_text(
            _plans_artifact_text(), encoding="utf-8"
        )
        state_path = seed_state_path(env.roadmap_root)
        state_before = state_path.read_bytes()

        with pytest.raises(NoPublishedRoadmapVersionError):
            apply_roadmap_seeds(
                env.slug,
                repo_root=env.repo_root,
                plans_dir=env.plans_dir,
                allow_apply=True,
                yes=True,
            )

        assert not env.plan_seeds_dir.exists()
        assert state_path.read_bytes() == state_before

    @pytest.mark.parametrize(
        "call",
        [
            pytest.param(
                lambda env: roadmap.refresh_roadmap_seeds(
                    SLUG,
                    repo_root=env.repo_root,
                    plans_dir=env.plans_dir,
                    invoker=_StubInvoker(_seed_text(), _seed_text(components=(), cross_cutting=True)),
                ),
                id="refresh_roadmap_seeds",
            ),
            pytest.param(
                lambda env: roadmap.materialize_plan_seed(
                    SLUG,
                    _PLAN_ORDER.id,
                    repo_root=env.repo_root,
                    plans_dir=env.plans_dir,
                    invoker=_StubInvoker(_seed_text()),
                ),
                id="materialize_plan_seed",
            ),
            pytest.param(
                lambda env: roadmap.materialize_and_diff_one_plan(
                    SLUG,
                    _PLAN_ORDER,
                    repo_root=env.repo_root,
                    plans_dir=env.plans_dir,
                    invoker=_StubInvoker(_seed_text()),
                ),
                id="materialize_and_diff_one_plan",
            ),
            pytest.param(
                lambda env: roadmap.accept_roadmap_seed(
                    SLUG, _PLAN_ORDER.id, repo_root=env.repo_root, plans_dir=env.plans_dir
                ),
                id="accept_roadmap_seed",
            ),
            pytest.param(
                lambda env: roadmap.apply_roadmap_seeds(
                    SLUG, repo_root=env.repo_root, plans_dir=env.plans_dir, allow_apply=False
                ),
                id="apply_roadmap_seeds",
            ),
        ],
    )
    def test_seed_routes_no_longer_refuse_an_enrolled_roadmap(self, env: _Env, call) -> None:
        """A roadmap with an accepted head is the only kind; no seed route refuses it as enrolled."""
        _prepare_seed_materialization(env)
        assert is_roadmap_enrolled(plans_dir=env.plans_dir, slug=SLUG)

        try:
            call(env)
        except roadmap.RoadmapError as exc:  # pragma: no cover - the regression
            assert "enrolled" not in str(exc), f"seed route refused an enrolled roadmap: {exc}"

    def test_seed_route_writes_stay_under_the_writer_guard(self, env: _Env) -> None:
        _prepare_seed_materialization(env)
        with roadmap._roadmap_writer_owner(env.plans_dir, SLUG) as stale_token:
            pass  # leaving the owning scope deactivates the token
        invoker = _StubInvoker(_seed_text())

        with pytest.raises(RoadmapError, match="writer token"):
            roadmap.materialize_plan_seed(
                SLUG,
                _PLAN_ORDER.id,
                repo_root=env.repo_root,
                plans_dir=env.plans_dir,
                invoker=invoker,
                writer_token=stale_token,
            )

        assert invoker.calls == 0
        assert not resolve_draft_seed_path(
            env.plans_dir, SLUG, _PLAN_ORDER.draft_seed_path
        ).exists()


# --------------------------------------------------------------------------
# One reader path: the version store is the only place roadmap content resolves
# --------------------------------------------------------------------------
#
# Each scanner asserts a binary fact about code (a name or file is referenced or
# not), never a judgment about meaning. Each takes ``(source, relative_path)`` and
# returns the violations it finds, so ``test_guard_flags_a_planted_violation`` can
# run it over a synthetic source and prove it can go red.

_PLAN_TOOL_DIR = Path(__file__).resolve().parents[1] / "plan_tool"
_TOP_LEVEL_PATH_HELPERS = frozenset(
    {"domain_path", "constraints_path", "components_path", "plans_path"}
)
# Only these modules may name the resume directory: its owner and the stage run.
_RESUME_DIR_ALLOWED = frozenset(
    {"plan_tool/roadmap_stage_resume.py", "plan_tool/roadmap.py"}
)
_RESUME_DIR_NAMES = frozenset({"resume_dir_path", "RESUME_DIRNAME"})
_RESUME_MODULE = "plan_tool.roadmap_stage_resume"
_INDEX_MODULE = "plan_tool.roadmap_index"
_INDEX_WRITER_FUNCTION = "write_roadmap_index"
# Allowlist, each entry with its reason. The match is an exact path plus a
# substring of one string constant, never a whole module.
_INDEX_MD_LITERAL_ALLOWLIST = (
    (
        "plan_tool/roadmap.py",
        "could not refresh INDEX.md",
        "the operator warning names the file it failed to write; it opens nothing",
    ),
)


def _production_files() -> list[tuple[str, Path]]:
    return sorted(
        (path.relative_to(_PLAN_TOOL_DIR.parent).as_posix(), path)
        for path in _PLAN_TOOL_DIR.rglob("*.py")
    )


@functools.cache
def _parse_source(source: str) -> ast.AST:
    return ast.parse(source)


def _docstring_nodes(tree: ast.AST) -> set[int]:
    """Ids of the string-constant nodes that are module, class, or function docstrings."""
    found: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                found.add(id(body[0].value))
    return found


def _scan_top_level_artifact_reads(source: str, relative_path: str) -> list[str]:
    """Flag ``<x>.artifact_path`` attribute reads and any use of the top-level path helpers.

    Only ``plan_tool/roadmap_artifacts.py`` may define or name the helpers. A keyword
    argument spelled ``artifact_path=`` (a run-log field) is not an attribute read.
    """
    violations: list[str] = []
    for node in ast.walk(_parse_source(source)):
        if isinstance(node, ast.Attribute) and node.attr == "artifact_path":
            violations.append(f"{relative_path}:{node.lineno}: reads .artifact_path")
        if relative_path == "plan_tool/roadmap_artifacts.py":
            continue
        name = (
            node.id
            if isinstance(node, ast.Name)
            else node.attr
            if isinstance(node, ast.Attribute)
            else node.name
            if isinstance(node, ast.alias)
            else None
        )
        if name in _TOP_LEVEL_PATH_HELPERS:
            violations.append(f"{relative_path}:{getattr(node, 'lineno', 0)}: uses {name}")
    return violations


def _scan_resume_directory_references(source: str, relative_path: str) -> list[str]:
    """Flag any module outside the owner and the stage run that names the resume directory."""
    if relative_path in _RESUME_DIR_ALLOWED:
        return []
    violations: list[str] = []
    for node in ast.walk(_parse_source(source)):
        if isinstance(node, ast.ImportFrom) and node.module == _RESUME_MODULE:
            violations.append(f"{relative_path}:{node.lineno}: imports {_RESUME_MODULE}")
        elif isinstance(node, ast.Import) and any(a.name == _RESUME_MODULE for a in node.names):
            violations.append(f"{relative_path}:{node.lineno}: imports {_RESUME_MODULE}")
        elif isinstance(node, ast.alias) and node.name in _RESUME_DIR_NAMES:
            violations.append(f"{relative_path}:{getattr(node, 'lineno', 0)}: imports {node.name}")
        elif isinstance(node, ast.Name) and node.id in _RESUME_DIR_NAMES:
            violations.append(f"{relative_path}:{node.lineno}: names {node.id}")
        elif isinstance(node, ast.Attribute) and node.attr in _RESUME_DIR_NAMES:
            violations.append(f"{relative_path}:{node.lineno}: names {node.attr}")
    return violations


def _scan_index_md_references(source: str, relative_path: str) -> list[str]:
    """Flag every way a module other than the index writer can touch ``INDEX.md``.

    The literal appears only in ``plan_tool/roadmap_index.py``; only ``plan_tool/roadmap.py``
    imports that module; and inside it ``INDEX_FILENAME`` is used only by the one function
    that writes the file, so nothing reads it back.
    """
    tree = _parse_source(source)
    violations: list[str] = []
    docstrings = _docstring_nodes(tree)
    in_index_module = relative_path == "plan_tool/roadmap_index.py"

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and "INDEX.md" in node.value
            and id(node) not in docstrings
            and not in_index_module
            and not any(
                relative_path == path and fragment in node.value
                for path, fragment, _reason in _INDEX_MD_LITERAL_ALLOWLIST
            )
        ):
            violations.append(f"{relative_path}:{node.lineno}: INDEX.md literal")
        if relative_path != "plan_tool/roadmap.py" and not in_index_module:
            if isinstance(node, ast.ImportFrom) and node.module == _INDEX_MODULE:
                violations.append(f"{relative_path}:{node.lineno}: imports {_INDEX_MODULE}")
            elif isinstance(node, ast.Import) and any(a.name == _INDEX_MODULE for a in node.names):
                violations.append(f"{relative_path}:{node.lineno}: imports {_INDEX_MODULE}")
        if not in_index_module and isinstance(node, (ast.Name, ast.alias)):
            name = node.id if isinstance(node, ast.Name) else node.name
            if name == "INDEX_FILENAME":
                violations.append(f"{relative_path}:{getattr(node, 'lineno', 0)}: names INDEX_FILENAME")

    if in_index_module:
        for function in ast.walk(tree):
            if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if function.name == _INDEX_WRITER_FUNCTION:
                continue
            for node in ast.walk(function):
                if isinstance(node, ast.Name) and node.id == "INDEX_FILENAME":
                    violations.append(
                        f"{relative_path}:{node.lineno}: {function.name} uses INDEX_FILENAME"
                    )
    return violations


def _scan_source_json_mentions(source: str, relative_path: str) -> list[str]:
    """Flag ``source.json`` anywhere in the text, comments and docstrings included."""
    return [
        f"{relative_path}:{number}: mentions source.json"
        for number, line in enumerate(source.splitlines(), start=1)
        if "source.json" in line
    ]


def _scan_production(scanner) -> list[str]:
    violations: list[str] = []
    for relative_path, path in _production_files():
        violations.extend(scanner(path.read_text(encoding="utf-8"), relative_path))
    return violations


class TestVersionStoreIsTheOnlyReaderPath:
    def test_no_production_module_reads_stage_artifact_path_or_top_level_path_helpers(
        self,
    ) -> None:
        assert "artifact_path" not in {field.name for field in fields(RoadmapStage)}
        assert _scan_production(_scan_top_level_artifact_reads) == []

    def test_resume_directory_is_referenced_only_by_the_stage_run_and_its_owner(self) -> None:
        assert _scan_production(_scan_resume_directory_references) == []

    def test_index_md_is_written_only_by_the_index_module_and_never_read(self) -> None:
        assert _scan_production(_scan_index_md_references) == []
        assert all(reason for _path, _fragment, reason in _INDEX_MD_LITERAL_ALLOWLIST)

    def test_source_json_appears_in_no_production_module(self) -> None:
        assert _scan_production(_scan_source_json_mentions) == []

    def test_guard_flags_a_planted_violation(self) -> None:
        """Each scanner goes red on the read it guards, and stays green on the sanctioned form."""
        cases = (
            (_scan_top_level_artifact_reads, "plan_tool/x.py", "p = stage.artifact_path(d, s)\n"),
            (
                _scan_top_level_artifact_reads,
                "plan_tool/x.py",
                "from plan_tool.roadmap_artifacts import domain_path\n",
            ),
            (_scan_top_level_artifact_reads, "plan_tool/x.py", "p = plans_path(d, s)\n"),
            (
                _scan_resume_directory_references,
                "plan_tool/x.py",
                "from plan_tool.roadmap_stage_resume import read_held_stages\n",
            ),
            (
                _scan_resume_directory_references,
                "plan_tool/x.py",
                "p = resume_dir_path(root, slug)\n",
            ),
            (_scan_index_md_references, "plan_tool/x.py", "p = d / 'INDEX.md'\n"),
            (
                _scan_index_md_references,
                "plan_tool/x.py",
                "from plan_tool.roadmap_index import write_roadmap_index\n",
            ),
            (
                _scan_index_md_references,
                "plan_tool/roadmap_index.py",
                "def read_back(d):\n    return (d / INDEX_FILENAME).read_text()\n",
            ),
            (_scan_source_json_mentions, "plan_tool/x.py", "# reads source.json\n"),
            (_scan_source_json_mentions, "plan_tool/x.py", "p = d / 'source.json'\n"),
        )
        for scanner, relative_path, planted in cases:
            assert scanner(planted, relative_path), (scanner.__name__, planted)

        sanctioned = (
            (_scan_top_level_artifact_reads, "plan_tool/roadmap_artifacts.py", "def domain_path(p, s): ...\n"),
            (_scan_top_level_artifact_reads, "plan_tool/x.py", "log(artifact_path='x')\n"),
            (_scan_resume_directory_references, "plan_tool/roadmap.py", "p = resume_dir_path(r, s)\n"),
            (
                _scan_resume_directory_references,
                "plan_tool/roadmap_stage_resume.py",
                "p = resume_dir_path(r, s)\n",
            ),
            (_scan_index_md_references, "plan_tool/x.py", '"""Mentions INDEX.md in a docstring."""\n'),
            (
                _scan_index_md_references,
                "plan_tool/roadmap.py",
                "from plan_tool.roadmap_index import write_roadmap_index\n",
            ),
            (
                _scan_index_md_references,
                "plan_tool/roadmap_index.py",
                "def write_roadmap_index(d):\n    return d / INDEX_FILENAME\n",
            ),
        )
        for scanner, relative_path, source in sanctioned:
            assert scanner(source, relative_path) == [], (scanner.__name__, relative_path, source)


@pytest.mark.integration
def test_materialized_seed_context_reaches_create_and_the_published_plan(
    env: _Env, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from plan_tool import create
    from plan_tool.schema import RiskProfile, Step

    _prepare_seed_materialization(env)
    obligations = {
        name: f"{name}: preserve accepted responsibility and proof."
        for name in create._evidence_only_body_section_keys()
    }
    seed = _seed_text() + "\n" + "\n\n".join(
        f"## {name}\n\n{body}" for name, body in obligations.items()
        if name != "Risks"
    )
    _materialize(env, _StubInvoker(seed))
    source = resolve_draft_seed_path(env.plans_dir, SLUG, _PLAN_ORDER.draft_seed_path)
    source_text = source.read_text(encoding="utf-8")
    sections = create.extract_h2_sections(source_text, ignore_fenced_code=True)
    lines = source_text.splitlines()
    evidence = {name: sections[name.lower()] for name in obligations}
    normalized = create.DistillOutcome.normalized(
        {"Overview": "Accepted route", "Problem statement": "Retain context",
         "Architecture": "Existing handoff", **evidence},
        {name: ((lines.index(body) + 1, lines.index(body) + 1),)
         for name, body in evidence.items()},
    )
    monkeypatch.setattr(create, "propose_distilled_seed_from_claude", lambda *a, **k: normalized)
    monkeypatch.setattr(create, "_propose_risk_profile_from_seed", lambda *a, **k:
        create._RiskProfileProposal(profile=RiskProfile.STANDARD, rationale="fixture",
                                    minimum_profile=RiskProfile.STANDARD))
    monkeypatch.setattr(create, "_resolve_risk_declaration", lambda proposal, **k:
        create._RiskDeclaration(profile=proposal.profile, rationale="fixture", mode="fixture"))

    def propose_steps(text, *args, **kwargs):
        for body in evidence.values():
            assert body in text
        assert sections["references"] in text
        return [Step(id=1, title="Implement accepted responsibility")]

    monkeypatch.setattr(create, "propose_steps_from_claude", propose_steps)
    monkeypatch.setattr(create, "propose_references_from_claude", lambda *a, **k:
        create.ReferenceResearchResult.from_references([]))
    monkeypatch.setattr(create, "_review_step_change_types", lambda steps, **k: steps)
    monkeypatch.setattr(create, "_review_create_concepts", lambda tree, steps, **k: (tree, steps))
    result = create.create_plan(
        "materialized-context", repo_root=env.repo_root,
        output_dir_override=env.repo_root / "implementation-plans",
        from_description=source_text, from_existing_path=source,
        yes=True, resume=False, offer_intents=False,
        claude_invoker=lambda prompt: pytest.fail("unexpected backend call"),
    )
    assert result.plan_path is not None
    published = result.plan_path.read_text(encoding="utf-8")
    assert sections["references"] in published
    for body in evidence.values():
        assert body in published
