"""Tests for plan_tool.create — the interactive plan authoring wizard.

Never spawns a real claude subprocess or blocks on stdin. `input_fn` and
`claude_invoker` are injected as fakes.
"""

from __future__ import annotations

import argparse
import copy
import inspect
from io import StringIO
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable, Optional

import pytest

from pydantic import ValidationError as PydanticValidationError

from plan_tool import create as create_module
from plan_tool.create import (
    CreateError,
    CreateResult,
    DirectSplitAssessment,
    FileBackedSourceRoute,
    Misspelling,
    ReferenceResearchResult,
    _ask,
    _ask_choice,
    _ask_int_list,
    _ask_yn,
    _dump_failed_response,
    _intent_from_seed_outcome,
    _load_speller,
    _looks_like_code,
    _parse_slug_response,
    _preserve_on_disk_step_fields,
    _reproposal_is_skippable,
    _ROADMAP_NO_SOURCE_REFERENCES_BODY,
    _STEP_PROPOSAL_RESPONSE_CONTRACT,
    _parse_steps_json,
    _review_create_concepts,
    _steps_missing_intent,
    _summarize_step_graph_error,
    append_to_manifest,
    archive_existing_source,
    check_collision,
    classify_file_backed_source,
    create_plan,
    extract_h2_sections,
    find_misspellings,
    propose_distilled_seed_from_claude,
    propose_steps_from_claude,
    read_existing_description,
    resolve_create_slug,
    resolve_output_dir,
    slugify,
    suggest_slug,
    validate_output_dir_in_repo,
    validate_slug,
    write_new_plan,
)
from plan_tool.parser import parse_plan
from plan_tool.concept_tree import (
    ConceptNode,
    ConceptTree,
    concept_id,
    concepts_path,
    load_concepts,
    save_concepts,
)


_PREPARATION_SECTION_KEYS = (
    "Overview",
    "Problem statement",
    "Architecture",
    "Out of scope",
    "Risks",
    "Testing",
    "Acceptance criteria",
    "Deferred",
)
_PREPARATION_EVIDENCE_KEYS = tuple(
    key
    for key in _PREPARATION_SECTION_KEYS
    if key not in {"Overview", "Problem statement", "Architecture"}
)


def _valid_preparation_response(prompt: str) -> str:
    """Return a source-citing normalized response for a routed test invoker."""
    numbered_lines = [
        (int(number), line)
        for number, line in re.findall(r"(?m)^(\d+)\t(.*)$", prompt)
    ]
    evidence_line = next(
        (
            number
            for number, line in numbered_lines
            if line.strip() and not re.match(r"^ {0,3}#{1,6}(?:[ \t]|$)", line)
        ),
        1,
    )
    spans = {}
    for key in _PREPARATION_EVIDENCE_KEYS:
        selected = evidence_line
        for index, (number, line) in enumerate(numbered_lines):
            if line.strip().lower() != f"## {key}".lower():
                continue
            for candidate_number, candidate_line in numbered_lines[index + 1 :]:
                if re.match(r"^ {0,3}#{1,6}(?:[ \t]|$)", candidate_line):
                    break
                if candidate_line.strip():
                    selected = candidate_number
                    break
            break
        spans[key] = [{"start_line": selected, "end_line": selected}]
    return json.dumps(
        {
            "outcome": "single",
            "sections": {
                key: f"{key} prepared body."
                for key in _PREPARATION_SECTION_KEYS
            },
            "evidence_spans": spans,
        }
    )


def _normalized_outcome_for_test(
    sections: Optional[dict[str, Optional[str]]] = None,
    *,
    markdown: Optional[str] = None,
) -> create_module.DistillOutcome:
    """Build a normalized result for routing tests that stub the parser seam."""
    resolved = {
        key: f"{key} prepared body."
        for key in _PREPARATION_SECTION_KEYS
    }
    if sections is not None:
        resolved.update(sections)
    if markdown is not None:
        extracted = extract_h2_sections(markdown)
        for key in (*_PREPARATION_SECTION_KEYS, *create_module._OPTIONAL_PLAN_BODY_SECTIONS):
            if (body := extracted.get(key.lower())) is not None:
                resolved[key] = body
    return create_module.DistillOutcome.normalized(
        resolved,
        {key: ((1, 1),) for key in _PREPARATION_EVIDENCE_KEYS},
    )
from plan_tool.progress import (
    NullReporter,
    ProgressReporter,
    StderrReporter,
    StepHandle,
)
from plan_tool.schema import (
    ChangeType,
    Complexity,
    Plan,
    PlanStatus,
    Priority,
    RiskProfile,
    Step,
    StepScope,
    StepStatus,
)


_REAL_PROPOSE_RISK_PROFILE_FROM_SEED = create_module._propose_risk_profile_from_seed
_REAL_RESOLVE_RISK_DECLARATION = create_module._resolve_risk_declaration


def test_create_plan_signature_is_exact() -> None:
    """Keep create_plan's callable boundary stable for direct callers."""
    from plan_tool import create as create_module

    signature = inspect.signature(create_plan)
    parameter_records = [
        (parameter.name, parameter.kind, parameter.default, parameter.annotation)
        for parameter in signature.parameters.values()
    ]

    assert parameter_records == [
        ("slug", inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.empty, "str"),
        ("repo_root", inspect.Parameter.KEYWORD_ONLY, inspect.Parameter.empty, "Path"),
        ("output_dir_override", inspect.Parameter.KEYWORD_ONLY, None, "Optional[Path]"),
        ("manifest_path", inspect.Parameter.KEYWORD_ONLY, None, "Optional[Path]"),
        ("from_description", inspect.Parameter.KEYWORD_ONLY, None, "Optional[str]"),
        ("from_existing_path", inspect.Parameter.KEYWORD_ONLY, None, "Optional[Path]"),
        (
            "tracked_seed_location",
            inspect.Parameter.KEYWORD_ONLY,
            None,
            "Optional[TrackedSeedLocation]",
        ),
        ("seed_body", inspect.Parameter.KEYWORD_ONLY, None, "Optional[str]"),
        ("input_fn", inspect.Parameter.KEYWORD_ONLY, input, "InputFn"),
        (
            "claude_invoker",
            inspect.Parameter.KEYWORD_ONLY,
            create_module.shell_claude_invoker,
            "ClaudeInvoker",
        ),
        (
            "concept_invoker",
            inspect.Parameter.KEYWORD_ONLY,
            create_module.shell_concept_invoker,
            "ClaudeInvoker",
        ),
        (
            "foundational_invoker",
            inspect.Parameter.KEYWORD_ONLY,
            None,
            "Optional[ClaudeInvoker]",
        ),
        ("capture_scenarios", inspect.Parameter.KEYWORD_ONLY, False, "bool"),
        ("arm", inspect.Parameter.KEYWORD_ONLY, None, "Optional[str]"),
        ("replace_on_collision", inspect.Parameter.KEYWORD_ONLY, None, "Optional[bool]"),
        ("yes", inspect.Parameter.KEYWORD_ONLY, False, "bool"),
        ("resume", inspect.Parameter.KEYWORD_ONLY, True, "bool"),
        (
            "budget",
            inspect.Parameter.KEYWORD_ONLY,
            create_module.IterativeBudget(enabled=False),
            "IterativeBudget",
        ),
        ("allow_drift", inspect.Parameter.KEYWORD_ONLY, False, "bool"),
        ("auto_reconcile_on_drift", inspect.Parameter.KEYWORD_ONLY, True, "bool"),
        ("collision_sidecar", inspect.Parameter.KEYWORD_ONLY, True, "bool"),
        ("triage", inspect.Parameter.KEYWORD_ONLY, True, "bool"),
        ("include_info", inspect.Parameter.KEYWORD_ONLY, False, "bool"),
        ("synthesize_body", inspect.Parameter.KEYWORD_ONLY, True, "bool"),
        ("offer_intents", inspect.Parameter.KEYWORD_ONLY, True, "bool"),
        ("allow_placeholder_body", inspect.Parameter.KEYWORD_ONLY, False, "bool"),
        ("fetch_docs", inspect.Parameter.KEYWORD_ONLY, True, "bool"),
        ("distill", inspect.Parameter.KEYWORD_ONLY, False, "bool"),
        ("skip_prose_reproposal", inspect.Parameter.KEYWORD_ONLY, True, "bool"),
        ("run_logger", inspect.Parameter.KEYWORD_ONLY, None, "Optional[RunLoggerLike]"),
    ]
    assert signature.return_annotation == "CreateResult"


def test_review_create_concepts_unattended_keeps_proposals_unsigned() -> None:
    """Under -y a proposed deferral lands pending in a decision record."""
    node = ConceptNode(
        id=concept_id("Candidate", []),
        title="Candidate",
        decision="defer",
    )
    tree = ConceptTree(
        plan_slug="demo",
        plan_fingerprint="source",
        concepts=[node],
    )
    steps = [Step(id=1, title="Ship", scope=StepScope.COMMITTED)]

    record, returned_steps = _review_create_concepts(
        tree,
        steps,
        input_fn=lambda prompt: (_ for _ in ()).throw(AssertionError(prompt)),
        yes=True,
        interactive=False,
    )

    assert record.record_kind == "decision-record"
    assert record.concepts[0].decision == "defer"
    assert record.concepts[0].review_state == "unreviewed"
    assert record.concepts[0].bucket == "Candidate"
    assert returned_steps[0].concept_ids == []


def test_review_create_concepts_records_only_deferrals() -> None:
    """Only defer/wont_do nodes are recorded; include nodes are dropped."""
    included = ConceptNode(
        id=concept_id("Kept", []), title="Kept", decision="include"
    )
    deferred = ConceptNode(
        id=concept_id("Later", []), title="Later", decision="defer"
    )
    tree = ConceptTree("demo", "source", [included, deferred])

    record, _ = _review_create_concepts(
        tree,
        [Step(id=1, title="Ship", scope=StepScope.COMMITTED)],
        input_fn=lambda prompt: (_ for _ in ()).throw(AssertionError(prompt)),
        yes=True,
        interactive=False,
    )

    assert record.record_kind == "decision-record"
    assert [node.title for node in record.concepts] == ["Later"]
    assert record.concepts[0].bucket == "Later"


def test_review_create_concepts_interactive_defer_signs_off() -> None:
    """An interactively confirmed deferral is signed off."""
    node = ConceptNode(
        id=concept_id("Candidate", []), title="Candidate", decision="include"
    )
    tree = ConceptTree("demo", "source", [node])

    record, _ = _review_create_concepts(
        tree,
        [Step(id=1, title="Ship", scope=StepScope.COMMITTED)],
        input_fn=_queue_input(["defer"]),
        yes=False,
        interactive=True,
    )

    assert record.concepts[0].decision == "defer"
    assert record.concepts[0].review_state == "approved"
    assert record.concepts[0].bucket == "Candidate"


def test_review_create_concepts_interactive_decline_drops() -> None:
    """Answering include for a proposed deferral produces no node."""
    node = ConceptNode(
        id=concept_id("Candidate", []), title="Candidate", decision="defer"
    )
    tree = ConceptTree("demo", "source", [node])

    record, _ = _review_create_concepts(
        tree,
        [Step(id=1, title="Ship", scope=StepScope.COMMITTED)],
        input_fn=_queue_input(["include"]),
        yes=False,
        interactive=True,
    )

    assert record.concepts == []


def test_review_create_concepts_all_include_returns_empty_record() -> None:
    """An all-include bootstrap tree yields a zero-concept decision record."""
    tree = ConceptTree(
        "demo",
        "source",
        [
            ConceptNode(id=concept_id("One", []), title="One"),
            ConceptNode(id=concept_id("Two", []), title="Two"),
        ],
    )

    record, returned_steps = _review_create_concepts(
        tree,
        [Step(id=1, title="Ship", scope=StepScope.COMMITTED)],
        input_fn=lambda prompt: (_ for _ in ()).throw(AssertionError(prompt)),
        yes=True,
        interactive=False,
    )

    assert record.record_kind == "decision-record"
    assert record.concepts == []
    assert returned_steps[0].concept_ids == []


def _queue_input(
    answers: list[str], *, test_command: Optional[str] = ""
) -> Callable[[str], str]:
    """Build a fake input() that pops answers in order. Extras raise.

    Existing interactive-create tests predate the optional test-command prompt,
    so they omit it by default without shifting their scripted choices. Pass
    ``test_command=None`` when a test must consume its next queued answer.
    """
    it = iter(answers)

    def fake(prompt: str) -> str:
        if (
            prompt == "Test command (optional, blank to omit): "
            and test_command is not None
        ):
            return test_command
        try:
            return next(it)
        except StopIteration as exc:
            raise AssertionError(
                f"input_fn ran out of answers at prompt: {prompt!r}"
            ) from exc

    return fake


def _basic_metadata_answers(
    *, title: str = "Demo Plan", priority: str = "medium"
) -> list[str]:
    """Answers covering the metadata phase (lessons=no)."""
    return [title, priority, "n"]


@pytest.fixture(autouse=True)
def _disable_step3_todo_check():
    """Disable step 3's fail-loud ``_(TODO)_`` body check for legacy
    test classes that pre-date it.

    The check refuses to ship a plan whose rendered body would contain
    ``_(TODO)_`` placeholders in any required H2 section. Most legacy
    tests in this module drive ``create_plan`` with synthetic inputs
    (stubbed references, no seed_body, claude-only step proposals) and
    write plans that trip the check incidentally — those tests verify
    surfaces orthogonal to body completeness (resume, run-log, priority
    bucketing, references rendering, …) so neutralizing the check for
    them keeps the assertions focused.

    Uses a private :class:`pytest.MonkeyPatch` instance (rather than
    consuming the test's ``monkeypatch`` fixture) so that a test which
    calls ``monkeypatch.undo()`` mid-body — see
    ``test_create_plan_keeps_checkpoints_when_write_fails`` — does NOT
    clear the patch out from under itself.

    Tests that exercise the check itself live in
    :class:`TestCreatePlanRejectsTodoBody`, which overrides this
    fixture with a no-op so the production check stays live for that
    class only.
    """
    from plan_tool import create as create_module

    mp = pytest.MonkeyPatch()
    mp.setattr(
        create_module,
        "_find_placeholder_body_sections",
        lambda _body: [],
    )
    try:
        yield
    finally:
        mp.undo()


@pytest.fixture(autouse=True)
def _stub_risk_profile_classifier():
    """Keep legacy create-flow tests focused on their existing call seams."""
    from plan_tool import create as create_module

    mp = pytest.MonkeyPatch()
    mp.setattr(
        create_module,
        "_propose_risk_profile_from_seed",
        lambda *_args, **_kwargs: create_module._standard_risk_profile_proposal(
            "Risk classification defaults to standard in this isolated test."
        ),
    )
    try:
        yield
    finally:
        mp.undo()


@pytest.fixture(autouse=True)
def _stub_risk_declaration_for_existing_create_tests():
    """Keep pre-declaration fixtures focused on the prompt they characterize."""
    from plan_tool import create as create_module

    mp = pytest.MonkeyPatch()
    mp.setattr(
        create_module,
        "_resolve_risk_declaration",
        lambda *_args, **_kwargs: create_module._RiskDeclaration(
            RiskProfile.STANDARD,
            "Risk declaration uses standard in this isolated test.",
            "silent_standard",
        ),
    )
    try:
        yield
    finally:
        mp.undo()


def _single_step_answers(
    *, title: str = "First step", complexity: str = "low"
) -> list[str]:
    """Answers for one step + 'no' to 'add another?'."""
    return [title, complexity, "", "", "n"]


def _proposed_step(title: str, **overrides) -> dict:
    """One step object in the step-proposal JSON contract.

    Carries an ``intent`` by default: a proposed step without one is a soft
    rejection that spends ``propose_steps_from_claude``'s single repair retry,
    so an intent-less canned body silently adds a second invoker call to every
    call-count assertion in this module.
    """
    return {
        "title": title,
        "intent": f"prove {title} lands",
        "complexity": "low",
        "files": [],
        "depends_on": [],
        **overrides,
    }


# The recurring one-step canned proposal.
_ONE_STEP_JSON = json.dumps([_proposed_step("one")])


def _low_risk_classifier_response(source_text: str) -> str:
    """Return the closed low-risk response backed by the deletion fixture."""
    lines = source_text.splitlines()
    return json.dumps(
        {
            "tier": "low",
            "rationale": (
                "The seed removes the proof of concept, names no consumers, "
                "and adds no external, schema, API, contract, or runtime surface."
            ),
            "evidence": {
                "deletion_dominance": lines[2],
                "no_consumer": lines[3],
                "no_new_surface": lines[4],
            },
        }
    )


class TestRiskProfileClassification:
    _FIXTURE = (
        Path(__file__).parent
        / "fixtures"
        / "create"
        / "remove-vendor-scraper-poc-seed.md"
    )

    def _fixture_text(self) -> str:
        return self._FIXTURE.read_text(encoding="utf-8")

    def _prepare_seed(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        *,
        source: Optional[str],
        seed_body: Optional[str] = None,
        from_existing_path: Optional[Path] = None,
        distill: bool = False,
        replace_on_collision: Optional[bool] = None,
        claude_invoker: Optional[Callable[[str], str]] = None,
    ) -> Any:
        (tmp_path / ".git").mkdir(parents=True, exist_ok=True)
        output_dir = tmp_path / "plans"
        output_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(
            create_module,
            "propose_steps_from_claude",
            lambda *_args, **_kwargs: [Step(id=1, title="Classify seed")],
        )
        monkeypatch.setattr(
            create_module,
            "propose_references_from_claude",
            lambda *_args, **_kwargs: ReferenceResearchResult.from_references([]),
        )
        monkeypatch.setattr(
            create_module,
            "_review_step_change_types",
            lambda steps, **_kwargs: steps,
        )
        monkeypatch.setattr(
            create_module,
            "_review_create_concepts",
            lambda tree, steps, **_kwargs: (tree, steps),
        )
        answers = _basic_metadata_answers()
        if source is None:
            answers += _single_step_answers()
        return create_module._prepare_create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=output_dir,
            manifest_path=tmp_path / "plans.json",
            from_description=source,
            from_existing_path=from_existing_path,
            tracked_seed_location=None,
            seed_body=seed_body,
            input_fn=_queue_input(answers),
            claude_invoker=claude_invoker
            or (
                lambda prompt: (
                    _valid_preparation_response(prompt)
                    if "Distill a free-form seed" in prompt
                    else _ONE_STEP_JSON
                )
            ),
            concept_invoker=lambda _prompt: "",
            foundational_invoker=None,
            capture_scenarios=False,
            arm=None,
            replace_on_collision=replace_on_collision,
            yes=False,
            resume=True,
            budget=create_module.IterativeBudget(enabled=False),
            synthesize_body=False,
            offer_intents=False,
            allow_placeholder_body=True,
            fetch_docs=False,
            distill=distill,
            run_logger=None,
        )

    def test_risk_profile_prompt_requires_seed_only_closed_json(self) -> None:
        prompt = (create_module.prompts_dir() / "classify-risk-profile.md").read_text(
            encoding="utf-8"
        )

        assert "Use only the supplied seed text" in prompt
        assert "Do not inspect the repository" in prompt
        assert "only `low` or `standard`" in prompt
        assert "Respond with ONLY this JSON object shape" in prompt
        assert "deletion_dominance" in prompt
        assert "no_consumer" in prompt
        assert "no_new_surface" in prompt

    def test_parse_risk_profile_low_requires_seed_grounded_admission_evidence(
        self,
    ) -> None:
        source = self._fixture_text()
        proposal = create_module._parse_risk_profile_json(
            _low_risk_classifier_response(source), source
        )

        assert proposal.profile is RiskProfile.LOW
        assert proposal.minimum_profile is RiskProfile.LOW
        assert proposal.rationale.count("\n") == 0

        response = json.loads(_low_risk_classifier_response(source))
        response["evidence"]["no_consumer"] = "invented support"
        unsupported = create_module._parse_risk_profile_json(
            json.dumps(response), source
        )

        assert unsupported.profile is RiskProfile.STANDARD

    def test_parse_risk_profile_negated_deletion_evidence_defaults_to_standard(
        self,
    ) -> None:
        source = (
            self._fixture_text()
            + "\nThis change does not remove the proof of concept.\n"
        )
        response = json.loads(_low_risk_classifier_response(source))
        response["evidence"]["deletion_dominance"] = source.splitlines()[-1]

        negated_evidence = create_module._parse_risk_profile_json(
            json.dumps(response), source
        )

        assert negated_evidence.profile is RiskProfile.STANDARD

        rationale_response = json.loads(
            _low_risk_classifier_response(self._fixture_text())
        )
        rationale_response["rationale"] = (
            "This change does not remove the proof of concept, has no named consumer, "
            "and adds no new API."
        )
        negated_rationale = create_module._parse_risk_profile_json(
            json.dumps(rationale_response), self._fixture_text()
        )

        assert negated_rationale.profile is RiskProfile.STANDARD

    @pytest.mark.parametrize(
        "response",
        (
            lambda source: _low_risk_classifier_response(source).replace(
                '"tier": "low"', '"tier": "standard", "tier": "low"', 1
            ),
            lambda source: _low_risk_classifier_response(source).replace(
                '"no_consumer": ', '"no_consumer": "ignored", "no_consumer": ', 1
            ),
        ),
    )
    def test_parse_risk_profile_duplicate_json_key_defaults_to_standard(
        self, response: Callable[[str], str]
    ) -> None:
        source = self._fixture_text()

        proposal = create_module._parse_risk_profile_json(response(source), source)

        assert proposal.profile is RiskProfile.STANDARD
        assert proposal.minimum_profile is RiskProfile.STANDARD

    @pytest.mark.parametrize(
        "counter_signal",
        (
            "The named report-worker consumer still reads this output.",
            "The public contract changes.",
            "A data migration is required.",
            "Authorization rules change for this removal.",
            "Add a new external integration.",
            "Add a new schema.",
            "Add a new API.",
            "Add a new runtime surface.",
        ),
    )
    def test_parse_risk_profile_source_counter_signal_sets_standard_floor(
        self, counter_signal: str
    ) -> None:
        source = self._fixture_text() + f"\n{counter_signal}\n"
        proposal = create_module._parse_risk_profile_json(
            _low_risk_classifier_response(source), source
        )

        assert proposal.profile is RiskProfile.STANDARD
        assert proposal.minimum_profile is RiskProfile.STANDARD
        assert proposal.rationale.count("\n") == 0

    @pytest.mark.parametrize(
        ("counter_signal", "expected_signal"),
        (
            (
                "No consumers remain and the report-worker consumer still reads it.",
                "named consumer",
            ),
            (
                "No new contract is created and the existing contract changes.",
                "contract",
            ),
            (
                "No migration is required and a database migration is required.",
                "migration",
            ),
            (
                "No authorization change is required and authorization rules change.",
                "authentication or authorization",
            ),
            ("The API endpoint will be added.", "api surface"),
            *(
                (
                    f"No new {surface} is added and the update exposes a new {surface}.",
                    "contract" if surface == "contract" else f"{surface} surface",
                )
                for surface in ("external", "schema", "api", "contract", "runtime")
            ),
            *(
                (
                    f"No {surface} surface is new and the {surface} surface is new.",
                    "contract" if surface == "contract" else f"{surface} surface",
                )
                for surface in ("external", "schema", "api", "contract", "runtime")
            ),
        ),
    )
    def test_parse_risk_profile_mixed_negative_and_positive_signals_set_standard(
        self, counter_signal: str, expected_signal: str
    ) -> None:
        source = self._fixture_text() + f"\n{counter_signal}\n"

        assert expected_signal in create_module._risk_profile_source_counter_signals(source)

        proposal = create_module._parse_risk_profile_json(
            _low_risk_classifier_response(source), source
        )

        assert proposal.profile is RiskProfile.STANDARD
        assert proposal.minimum_profile is RiskProfile.STANDARD

    @pytest.mark.parametrize(
        ("rationale", "expected_signal"),
        (
            (
                "The deletion retains a named consumer and adds no new API.",
                "named consumer",
            ),
            (
                "The deletion has no named consumer, adds no new API, and changes the contract.",
                "contract",
            ),
            (
                "The deletion has no named consumer, adds no new API, and needs a migration.",
                "migration",
            ),
            (
                "The deletion has no named consumer, adds no new API, and changes authorization.",
                "authentication or authorization",
            ),
            *(
                (
                    f"The deletion has no named consumer and adds a new {surface}.",
                    "contract" if surface == "contract" else f"{surface} surface",
                )
                for surface in ("external", "schema", "api", "contract", "runtime")
            ),
        ),
    )
    def test_parse_risk_profile_counter_signal_in_rationale_defaults_to_standard(
        self, rationale: str, expected_signal: str
    ) -> None:
        source = self._fixture_text()
        response = json.loads(_low_risk_classifier_response(source))
        response["rationale"] = rationale

        assert expected_signal in create_module._risk_profile_source_counter_signals(rationale)

        proposal = create_module._parse_risk_profile_json(json.dumps(response), source)

        assert proposal.profile is RiskProfile.STANDARD
        assert proposal.minimum_profile is RiskProfile.STANDARD

    def test_parse_risk_profile_negative_evidence_does_not_count_as_counter_signal(
        self,
    ) -> None:
        source = self._fixture_text()

        assert create_module._risk_profile_source_counter_signals(source) == []

    def test_parse_risk_profile_explicit_negative_surface_is_not_counter_signal(
        self,
    ) -> None:
        source = self._fixture_text().replace(
            "This deletion adds no new external, schema, API, contract, or runtime surface.",
            "This deletion does not add a new external, schema, API, contract, or runtime surface.",
        )

        assert create_module._risk_profile_source_counter_signals(source) == []

    def test_parse_risk_profile_positive_surface_after_negative_clause_is_counter_signal(
        self,
    ) -> None:
        source = self._fixture_text().replace(
            "This deletion adds no new external, schema, API, contract, or runtime surface.",
            "This deletion adds no new external, schema, API, contract, or runtime "
            "surface and the update exposes a new API.",
        )

        assert create_module._risk_profile_source_counter_signals(source) == [
            "api surface"
        ]
        proposal = create_module._parse_risk_profile_json(
            _low_risk_classifier_response(source), source
        )

        assert proposal.profile is RiskProfile.STANDARD

    def test_parse_risk_profile_contradictory_source_defaults_to_standard(self) -> None:
        source = self._fixture_text() + (
            "\nNo consumers remain, but the report-worker consumer still reads it.\n"
        )

        proposal = create_module._parse_risk_profile_json(
            _low_risk_classifier_response(source), source
        )

        assert proposal.profile is RiskProfile.STANDARD

    @pytest.mark.parametrize(
        "response",
        (
            "not JSON",
            None,
            json.dumps({"tier": "high", "rationale": "No automatic high.", "evidence": {}}),
            json.dumps(
                {
                    "tier": "standard",
                    "rationale": "Use the standard tier.",
                    "evidence": {
                        "deletion_dominance": None,
                        "no_consumer": None,
                        "no_new_surface": None,
                    },
                    "unexpected": True,
                }
            ),
            json.dumps(
                {
                    "tier": "low",
                    "rationale": "delete consumer surface",
                    "evidence": {"deletion_dominance": "x"},
                }
            ),
            json.dumps(
                {
                    "tier": "low",
                    "rationale": "",
                    "evidence": {
                        "deletion_dominance": "x",
                        "no_consumer": "x",
                        "no_new_surface": "x",
                    },
                }
            ),
            json.dumps(
                {
                    "tier": "low",
                    "rationale": "delete consumer surface\nsecond line",
                    "evidence": {
                        "deletion_dominance": "x",
                        "no_consumer": "x",
                        "no_new_surface": "x",
                    },
                }
            ),
            json.dumps(
                {
                    "tier": "low",
                    "rationale": "delete consumer surface",
                    "evidence": {
                        "deletion_dominance": "invented",
                        "no_consumer": "invented",
                        "no_new_surface": "invented",
                    },
                }
            ),
        ),
    )
    def test_parse_risk_profile_unsupported_or_ambiguous_response_defaults_to_standard(
        self, response: object
    ) -> None:
        proposal = create_module._parse_risk_profile_json(
            response, self._fixture_text()
        )

        assert proposal.profile is RiskProfile.STANDARD
        assert proposal.minimum_profile is RiskProfile.STANDARD
        assert proposal.rationale.strip()
        assert "\n" not in proposal.rationale

    def test_risk_classifier_invocation_failure_defaults_to_standard(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            create_module,
            "_propose_risk_profile_from_seed",
            _REAL_PROPOSE_RISK_PROFILE_FROM_SEED,
        )
        prepared = self._prepare_seed(
            tmp_path,
            monkeypatch,
            source=self._fixture_text(),
            claude_invoker=lambda _prompt: (_ for _ in ()).throw(
                RuntimeError("offline")
            ),
        )

        assert prepared.risk_profile_proposal.profile is RiskProfile.STANDARD
        assert "unavailable" in prepared.risk_profile_proposal.rationale

    def test_risk_classifier_invocation_failure_logs_the_real_exception(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A genuine bug in invoker wiring must stay distinguishable from a
        real outage: the fallback rationale says "unavailable" either way, but
        the actual exception type/message must reach the console so an
        operator (or a future debugging session) is not stuck guessing which
        one actually happened."""
        monkeypatch.setattr(
            create_module,
            "_propose_risk_profile_from_seed",
            _REAL_PROPOSE_RISK_PROFILE_FROM_SEED,
        )
        self._prepare_seed(
            tmp_path,
            monkeypatch,
            source=self._fixture_text(),
            claude_invoker=lambda _prompt: (_ for _ in ()).throw(
                TypeError("invoker() missing 1 required positional argument")
            ),
        )

        err = capsys.readouterr().err
        assert "TypeError" in err
        assert "missing 1 required positional argument" in err

    def test_remove_vendor_scraper_fixture_proposes_low(self, tmp_path: Path) -> None:
        source = self._fixture_text()
        proposal = _REAL_PROPOSE_RISK_PROFILE_FROM_SEED(
            source,
            lambda _prompt: _low_risk_classifier_response(source),
            slug="demo",
            predicted_plan_path=tmp_path / "plans" / "2-demo.md",
            repo_root=tmp_path,
            resume=True,
            allow_resume=True,
        )

        assert proposal.profile is RiskProfile.LOW

    def test_seed_body_precedence_controls_risk_classification_input(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen: list[str] = []
        monkeypatch.setattr(
            create_module,
            "_propose_risk_profile_from_seed",
            lambda source, *_args, **_kwargs: (
                seen.append(source)
                or create_module._standard_risk_profile_proposal(
                    "Risk classification defaults to standard for seed precedence."
                )
            ),
        )

        prepared = self._prepare_seed(
            tmp_path,
            monkeypatch,
            source="Canonical description must not win.",
            seed_body="Provenance seed controls classification.",
        )

        assert prepared.risk_profile_proposal.profile is RiskProfile.STANDARD
        assert seen == ["Provenance seed controls classification."]

    def test_seed_fed_single_plan_routes_share_risk_classification_policy(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen: list[str] = []
        monkeypatch.setattr(
            create_module,
            "_propose_risk_profile_from_seed",
            lambda source, *_args, **_kwargs: (
                seen.append(source)
                or create_module._standard_risk_profile_proposal(
                    "Risk classification defaults to standard for route coverage."
                )
            ),
        )
        canonical = "\n\n".join(
            f"## {section}\n\nCanonical {section}."
            for section in create_module._canonical_body_section_keys()
        )
        direct_file = tmp_path / "seed.md"
        direct_file.write_text(
            "Direct file seed.\n\n## References\n\n"
            "- [API](https://example.test/api)\n",
            encoding="utf-8",
        )

        self._prepare_seed(tmp_path / "inline", monkeypatch, source="Inline seed.")
        self._prepare_seed(
            tmp_path / "file",
            monkeypatch,
            source=direct_file.read_text(encoding="utf-8"),
            from_existing_path=direct_file,
        )
        self._prepare_seed(
            tmp_path / "canonical",
            monkeypatch,
            source=canonical,
            distill=True,
        )
        monkeypatch.setattr(
            create_module,
            "propose_distilled_seed_from_claude",
            lambda *_args, **_kwargs: _normalized_outcome_for_test(),
        )
        self._prepare_seed(
            tmp_path / "distilled",
            monkeypatch,
            source="Original distilled seed.",
            distill=True,
        )
        monkeypatch.setattr(
            create_module,
            "propose_distilled_seed_from_claude",
            lambda *_args, **_kwargs: create_module.DistillOutcome.refused(
                "test refusal"
            ),
        )
        self._prepare_seed(
            tmp_path / "passthrough",
            monkeypatch,
            source="Passthrough seed.",
            distill=True,
        )
        self._prepare_seed(
            tmp_path / "no-distill",
            monkeypatch,
            source="No-distill seed.",
            distill=False,
        )

        assert seen == [
            "Inline seed.",
            "Direct file seed.\n\n## References\n\n- [API](https://example.test/api)\n",
            canonical,
            "Original distilled seed.",
            "Passthrough seed.",
            "No-distill seed.",
        ]

    def test_split_proposal_skips_risk_classification_and_publication(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            create_module,
            "propose_distilled_seed_from_claude",
            lambda *_args, **_kwargs: create_module.DistillOutcome.split_proposal(
                [
                    create_module.SplitProposalEntry("One", "one", "First."),
                    create_module.SplitProposalEntry("Two", "two", "Second."),
                ]
            ),
        )
        monkeypatch.setattr(
            create_module,
            "_propose_risk_profile_from_seed",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("split proposals must not classify")
            ),
        )

        result = self._prepare_seed(
            tmp_path, monkeypatch, source="Split this seed.", distill=True
        )

        assert isinstance(result, CreateResult)
        assert result.plan_path is None
        assert result.split_proposal is not None

    def test_no_source_create_uses_standard_without_classifier_call(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[str] = []
        monkeypatch.setattr(
            create_module,
            "_propose_risk_profile_from_seed",
            _REAL_PROPOSE_RISK_PROFILE_FROM_SEED,
        )
        prepared = self._prepare_seed(
            tmp_path,
            monkeypatch,
            source=None,
            claude_invoker=lambda prompt: calls.append(prompt) or _ONE_STEP_JSON,
        )

        assert calls == []
        assert prepared.risk_profile_proposal.profile is RiskProfile.STANDARD
        assert prepared.risk_profile_proposal.rationale.strip()

    def test_risk_classification_checkpoint_reuses_matching_source_target_and_revision(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        source = self._fixture_text()
        target = tmp_path / "plans" / "2-demo.md"
        calls: list[str] = []

        def invoker(_prompt: str) -> str:
            calls.append("invoke")
            return _low_risk_classifier_response(source)

        first = _REAL_PROPOSE_RISK_PROFILE_FROM_SEED(
            source, invoker, slug="demo", predicted_plan_path=target,
            repo_root=tmp_path, resume=True, allow_resume=True,
        )
        resumed = _REAL_PROPOSE_RISK_PROFILE_FROM_SEED(
            source,
            lambda _prompt: (_ for _ in ()).throw(AssertionError("cache miss")),
            slug="demo",
            predicted_plan_path=target,
            repo_root=tmp_path,
            resume=True,
            allow_resume=True,
        )
        _REAL_PROPOSE_RISK_PROFILE_FROM_SEED(
            source + "\nChanged.", invoker, slug="demo", predicted_plan_path=target,
            repo_root=tmp_path, resume=True, allow_resume=True,
        )
        _REAL_PROPOSE_RISK_PROFILE_FROM_SEED(
            source, invoker, slug="demo", predicted_plan_path=tmp_path / "elsewhere" / "2-demo.md",
            repo_root=tmp_path, resume=True, allow_resume=True,
        )
        monkeypatch.setattr(create_module, "_RISK_PROFILE_CLASSIFIER_POLICY_REVISION", "test-revision")
        _REAL_PROPOSE_RISK_PROFILE_FROM_SEED(
            source, invoker, slug="demo", predicted_plan_path=target,
            repo_root=tmp_path, resume=True, allow_resume=True,
        )

        assert first.profile is RiskProfile.LOW
        assert resumed.profile is RiskProfile.LOW
        assert calls == ["invoke", "invoke", "invoke", "invoke"]

    def test_replacement_create_does_not_reuse_risk_classification_checkpoint(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        output_dir = tmp_path / "plans"
        output_dir.mkdir()
        (output_dir / "2-demo.md").write_text("# Existing\n", encoding="utf-8")
        (tmp_path / "plans.json").write_text(
            json.dumps({"plans": ["plans/2-demo.md"]}), encoding="utf-8"
        )
        resume_values: list[bool] = []
        monkeypatch.setattr(
            create_module,
            "_propose_risk_profile_from_seed",
            lambda _source, *_args, **kwargs: (
                resume_values.append(kwargs["allow_resume"])
                or create_module._standard_risk_profile_proposal(
                    "Risk classification defaults to standard for replacement."
                )
            ),
        )

        self._prepare_seed(
            tmp_path,
            monkeypatch,
            source="Replacement seed.",
            replace_on_collision=True,
        )

        assert resume_values == [False]

    def test_registered_collision_refuses_before_risk_checkpoint_read(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        output_dir = tmp_path / "plans"
        output_dir.mkdir()
        (output_dir / "2-demo.md").write_text("# Existing\n", encoding="utf-8")
        (tmp_path / "plans.json").write_text(
            json.dumps({"plans": ["plans/2-demo.md"]}), encoding="utf-8"
        )
        monkeypatch.setattr(
            create_module,
            "_propose_risk_profile_from_seed",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("collision refusal must happen before classification")
            ),
        )

        with pytest.raises(FileExistsError, match="already exists"):
            self._prepare_seed(
                tmp_path,
                monkeypatch,
                source="Colliding seed.",
                replace_on_collision=False,
            )

    def test_no_resume_risk_classification_invokes_fresh(self, tmp_path: Path) -> None:
        source = self._fixture_text()
        target = tmp_path / "plans" / "2-demo.md"
        calls: list[str] = []

        def invoker(_prompt: str) -> str:
            calls.append("invoke")
            return _low_risk_classifier_response(source)

        _REAL_PROPOSE_RISK_PROFILE_FROM_SEED(
            source, invoker, slug="demo", predicted_plan_path=target,
            repo_root=tmp_path, resume=True, allow_resume=True,
        )
        _REAL_PROPOSE_RISK_PROFILE_FROM_SEED(
            source, invoker, slug="demo", predicted_plan_path=target,
            repo_root=tmp_path, resume=False, allow_resume=True,
        )

        assert calls == ["invoke", "invoke"]


class TestRiskDeclarationResolution:
    """The classifier advises; this gate creates the persisted declaration."""

    @staticmethod
    def _admitted_low() -> Any:
        return create_module._RiskProfileProposal(
            profile=RiskProfile.LOW,
            rationale="The source removes the unused component without a new surface.",
            minimum_profile=RiskProfile.LOW,
            low_admitted=True,
            source_counter_signals=(),
        )

    def _resolve(
        self,
        tmp_path: Path,
        proposal: Any,
        *,
        answers: list[str],
        monkeypatch: pytest.MonkeyPatch,
        yes: bool = False,
        resume: bool = True,
        source_text: str = "Remove the unused component.",
    ) -> Any:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        return _REAL_RESOLVE_RISK_DECLARATION(
            proposal,
            source_text=source_text,
            slug="demo",
            predicted_plan_path=tmp_path / "plans" / "2-demo.md",
            repo_root=tmp_path,
            input_fn=_queue_input(answers),
            yes=yes,
            resume=resume,
            allow_resume=True,
            run_logger=None,
        )

    def test_interactive_risk_declaration_accepts_admitted_proposal(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        declaration = self._resolve(
            tmp_path, self._admitted_low(), answers=[""], monkeypatch=monkeypatch
        )
        assert declaration == create_module._RiskDeclaration(
            RiskProfile.LOW,
            "The source removes the unused component without a new surface.",
            "accepted",
        )

    def test_interactive_risk_declaration_accepts_admitted_proposal_before_initial_write(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            create_module, "_resolve_risk_declaration", _REAL_RESOLVE_RISK_DECLARATION
        )
        monkeypatch.setattr(
            create_module,
            "_propose_risk_profile_from_seed",
            lambda *_args, **_kwargs: self._admitted_low(),
        )
        monkeypatch.setattr(
            create_module,
            "propose_steps_from_claude",
            lambda *_args, **_kwargs: [Step(id=1, title="Remove")],
        )
        monkeypatch.setattr(
            create_module,
            "propose_references_from_claude",
            lambda *_args, **_kwargs: ReferenceResearchResult.from_references([]),
        )
        monkeypatch.setattr(
            create_module, "_review_step_change_types", lambda steps, **_kwargs: steps
        )
        monkeypatch.setattr(
            create_module, "_review_create_concepts", lambda tree, steps, **_kwargs: (tree, steps)
        )
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        written: list[Plan] = []
        original_write = create_module.write_plan

        def spy(path: Path, plan: Plan, **kwargs: Any) -> None:
            written.append(plan)
            original_write(path, plan, **kwargs)

        monkeypatch.setattr(create_module, "write_plan", spy)
        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=tmp_path / "plans",
            manifest_path=tmp_path / "plans.json",
            from_description="Remove the unused component.",
            input_fn=_queue_input(_basic_metadata_answers() + [""]),
            yes=False,
            offer_intents=False,
            synthesize_body=False,
            allow_placeholder_body=True,
        )
        assert len(written) == 1
        assert written[0].risk_profile is RiskProfile.LOW
        assert (
            parse_plan(result.plan_path).risk_profile_rationale == written[0].risk_profile_rationale
        )

    def test_interactive_risk_declaration_override_requires_final_rationale_and_respects_floor(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        declaration = self._resolve(
            tmp_path,
            create_module._standard_risk_profile_proposal("The source needs standard review."),
            answers=["o", "low", "standard", "", "Final standard rationale."],
            monkeypatch=monkeypatch,
        )
        assert declaration.profile is RiskProfile.STANDARD
        assert declaration.rationale == "Final standard rationale."
        assert declaration.mode == "override"

    def test_interactive_risk_declaration_decline_records_standard_final_rationale(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        declaration = self._resolve(
            tmp_path, self._admitted_low(), answers=["d"], monkeypatch=monkeypatch
        )
        assert declaration.profile is RiskProfile.STANDARD
        assert "declined" in declaration.rationale
        assert declaration.mode == "declined"

    def test_silent_risk_declaration_uses_standard_without_accepting_model_proposal(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)
        declaration = _REAL_RESOLVE_RISK_DECLARATION(
            self._admitted_low(),
            source_text="Remove the unused component.",
            slug="demo",
            predicted_plan_path=tmp_path / "plans" / "2-demo.md",
            repo_root=tmp_path,
            input_fn=lambda _prompt: (_ for _ in ()).throw(AssertionError("prompted")),
            yes=False,
            resume=True,
            allow_resume=True,
            run_logger=None,
        )
        assert declaration.profile is RiskProfile.STANDARD
        assert declaration.mode == "silent_standard"

        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        for source_text, yes in ((None, False), ("Remove the unused component.", True)):
            declaration = _REAL_RESOLVE_RISK_DECLARATION(
                self._admitted_low(),
                source_text=source_text,
                slug="silent",
                predicted_plan_path=tmp_path / "plans" / "2-silent.md",
                repo_root=tmp_path,
                input_fn=lambda _prompt: (_ for _ in ()).throw(AssertionError("prompted")),
                yes=yes,
                resume=True,
                allow_resume=True,
                run_logger=None,
            )
            assert declaration.profile is RiskProfile.STANDARD
            assert declaration.mode == "silent_standard"

    def test_interactive_risk_declaration_checkpoint_replays_exact_matching_decision(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        first = self._resolve(
            tmp_path,
            self._admitted_low(),
            answers=["o", "high", "Escalate review."],
            monkeypatch=monkeypatch,
        )
        assert first.profile is RiskProfile.HIGH
        replayed = _REAL_RESOLVE_RISK_DECLARATION(
            self._admitted_low(),
            source_text="Remove the unused component.",
            slug="demo",
            predicted_plan_path=tmp_path / "plans" / "2-demo.md",
            repo_root=tmp_path,
            input_fn=lambda _prompt: (_ for _ in ()).throw(AssertionError("re-prompted")),
            yes=False,
            resume=True,
            allow_resume=True,
            run_logger=None,
        )
        assert replayed == first

    def test_tty_eof_resume_never_replays_interactive_risk_decision(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Also pins the checkpoint-resume EOF path's operator-visible warning —
        the sibling of the fresh-declaration EOF path, easy to miss because it
        is a second, separate ``except EOFError`` in the same function."""
        first = self._resolve(
            tmp_path,
            self._admitted_low(),
            answers=["o", "high", "Escalate review."],
            monkeypatch=monkeypatch,
        )
        assert first.profile is RiskProfile.HIGH

        monkeypatch.setattr(create_module, "_stdin_has_pending_input", lambda: True)
        silent = _REAL_RESOLVE_RISK_DECLARATION(
            self._admitted_low(),
            source_text="Remove the unused component.",
            slug="demo",
            predicted_plan_path=tmp_path / "plans" / "2-demo.md",
            repo_root=tmp_path,
            input_fn=lambda _prompt: (_ for _ in ()).throw(EOFError()),
            yes=False,
            resume=True,
            allow_resume=True,
            run_logger=None,
        )

        assert silent.profile is RiskProfile.STANDARD
        assert silent.mode == "silent_standard"
        assert "non-interactive stdin" in capsys.readouterr().err

    def test_fresh_interactive_risk_declaration_eof_warns_before_silent_standard(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """EOF on a fresh (uncached) risk-declaration prompt must warn, matching
        every other ``_ask*`` helper's ``_eof_default`` convention — a silent
        default here is the one checkpoint most tied to a safety-relevant
        declaration, so the operator must see that nothing was chosen for
        them."""
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        declaration = _REAL_RESOLVE_RISK_DECLARATION(
            self._admitted_low(),
            source_text="Remove the unused component.",
            slug="demo",
            predicted_plan_path=tmp_path / "plans" / "2-demo.md",
            repo_root=tmp_path,
            input_fn=lambda _prompt: (_ for _ in ()).throw(EOFError()),
            yes=False,
            resume=True,
            allow_resume=True,
            run_logger=None,
        )
        assert declaration.mode == "silent_standard"
        assert "non-interactive stdin" in capsys.readouterr().err

    def test_silent_resume_never_replays_interactive_risk_decision(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        first = self._resolve(
            tmp_path,
            self._admitted_low(),
            answers=["o", "high", "Escalate review."],
            monkeypatch=monkeypatch,
        )
        assert first.profile is RiskProfile.HIGH

        monkeypatch.setattr("sys.stdin.isatty", lambda: False)
        silent = _REAL_RESOLVE_RISK_DECLARATION(
            self._admitted_low(),
            source_text="Remove the unused component.",
            slug="demo",
            predicted_plan_path=tmp_path / "plans" / "2-demo.md",
            repo_root=tmp_path,
            input_fn=lambda _prompt: (_ for _ in ()).throw(AssertionError("prompted")),
            yes=False,
            resume=True,
            allow_resume=True,
            run_logger=None,
        )
        assert silent.mode == "silent_standard"

        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        changed_target = _REAL_RESOLVE_RISK_DECLARATION(
            self._admitted_low(),
            source_text="Remove the unused component.",
            slug="demo",
            predicted_plan_path=tmp_path / "plans" / "2-other.md",
            repo_root=tmp_path,
            input_fn=_queue_input(["d"]),
            yes=False,
            resume=True,
            allow_resume=True,
            run_logger=None,
        )
        assert changed_target.mode == "declined"

        fresh = _REAL_RESOLVE_RISK_DECLARATION(
            self._admitted_low(),
            source_text="Remove the unused component.",
            slug="demo",
            predicted_plan_path=tmp_path / "plans" / "2-demo.md",
            repo_root=tmp_path,
            input_fn=_queue_input(["d"]),
            yes=False,
            resume=False,
            allow_resume=False,
            run_logger=None,
        )
        assert fresh.mode == "declined"

    def test_risk_declaration_never_persists_low_without_step_two_admission(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        with pytest.raises(CreateError, match="required admission"):
            self._resolve(
                tmp_path,
                create_module._RiskProfileProposal(
                    RiskProfile.LOW,
                    "The source removes the unused component without a new surface.",
                    RiskProfile.LOW,
                ),
                answers=[""],
                monkeypatch=monkeypatch,
            )

        with pytest.raises(CreateError, match="required admission"):
            self._resolve(
                tmp_path,
                create_module._RiskProfileProposal(
                    RiskProfile.LOW,
                    "The source removes the unused component without a new surface.",
                    RiskProfile.LOW,
                    low_admitted=True,
                    source_counter_signals=("API",),
                ),
                answers=[""],
                monkeypatch=monkeypatch,
            )

    @pytest.mark.parametrize(
        "proposal",
        (
            create_module._RiskProfileProposal(
                RiskProfile.HIGH, "", RiskProfile.HIGH
            ),
            create_module._RiskProfileProposal("standard", "", RiskProfile.STANDARD),
        ),
    )
    def test_risk_declaration_rejects_out_of_contract_proposal_before_rationale_fallback(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, proposal: Any
    ) -> None:
        with pytest.raises(CreateError, match="outside its closed contract"):
            self._resolve(
                tmp_path,
                proposal,
                answers=[""],
                monkeypatch=monkeypatch,
            )

    @pytest.mark.parametrize("rationale", ("", "First line.\nSecond line."))
    def test_malformed_classifier_rationale_falls_back_after_contract_validation(
        self, rationale: str
    ) -> None:
        proposal = create_module._RiskProfileProposal(
            RiskProfile.LOW,
            rationale,
            RiskProfile.LOW,
            low_admitted=True,
        )

        assert create_module._normalize_risk_profile_proposal(proposal) == (
            create_module._standard_risk_profile_proposal(
                create_module._RISK_PROFILE_FALLBACK_RATIONALE
            )
        )

    def test_risk_declaration_rescreens_source_before_accepting_low(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        with pytest.raises(
            CreateError, match="source counter-signals: api surface"
        ):
            self._resolve(
                tmp_path,
                self._admitted_low(),
                answers=[""],
                monkeypatch=monkeypatch,
                source_text="The removal exposes a new API.",
            )

    @pytest.mark.parametrize(
        "payload",
        (
            {"profile": "low", "rationale": "Forged rationale.", "mode": "accepted"},
            {"profile": "standard", "rationale": "Forged decline.", "mode": "declined"},
        ),
    )
    def test_risk_declaration_rejects_forged_proposal_derived_checkpoint(
        self, payload: dict[str, str]
    ) -> None:
        assert (
            create_module._deserialize_risk_declaration(
                json.dumps(payload), self._admitted_low()
            )
            is None
        )

    def test_risk_declaration_replays_exact_proposal_derived_checkpoint(self) -> None:
        proposal = self._admitted_low()
        declarations = (
            create_module._RiskDeclaration(
                proposal.profile, proposal.rationale, "accepted"
            ),
            create_module._declined_risk_declaration(proposal),
        )

        for declaration in declarations:
            assert (
                create_module._deserialize_risk_declaration(
                    create_module._serialize_risk_declaration(declaration), proposal
                )
                == declaration
            )

    def test_risk_declaration_checkpoint_save_failure_blocks_publication(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        monkeypatch.setattr(
            create_module,
            "save_checkpoint",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("disk full")),
        )
        with pytest.raises(CreateError, match="publication did not begin"):
            _REAL_RESOLVE_RISK_DECLARATION(
                self._admitted_low(),
                source_text="Remove the unused component.",
                slug="demo",
                predicted_plan_path=tmp_path / "plans" / "2-demo.md",
                repo_root=tmp_path,
                input_fn=_queue_input([""]),
                yes=False,
                resume=True,
                allow_resume=True,
                run_logger=None,
            )

    def test_risk_decision_run_log_records_proposal_final_declaration_and_mode(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        events: list[tuple[str, dict[str, Any]]] = []

        class Logger:
            def phase_start(self, phase: str, **extra: Any) -> None:
                events.append((f"start:{phase}", extra))

            def phase_end(self, phase: str, _duration: int, _outcome: str, **extra: Any) -> None:
                events.append((f"end:{phase}", extra))

            def checkpoint_save(self, *_args: Any) -> None:
                pass

        declaration = self._resolve(
            tmp_path,
            self._admitted_low(),
            answers=["d"],
            monkeypatch=monkeypatch,
        )
        _REAL_RESOLVE_RISK_DECLARATION(
            self._admitted_low(),
            source_text="Remove the unused component.",
            slug="run-log",
            predicted_plan_path=tmp_path / "plans" / "2-run-log.md",
            repo_root=tmp_path,
            input_fn=_queue_input(["d"]),
            yes=False,
            resume=False,
            allow_resume=True,
            run_logger=Logger(),
        )
        assert declaration.mode == "declined"
        assert events[0][1]["proposal"]["profile"] == "low"
        assert events[-1][1]["decision_mode"] == "declined"
        assert events[-1][1]["final_declaration"]["profile"] == "standard"


class TestValidateSlug:
    @pytest.mark.parametrize(
        "slug", ["ab", "foo", "foo-bar", "foo1-bar2", "1-2-3", "x1"]
    )
    def test_valid_slugs(self, slug: str) -> None:
        validate_slug(slug)  # should not raise

    @pytest.mark.parametrize(
        "slug",
        ["", "a", "-foo", "foo-", "Foo", "foo_bar", "foo bar", "foo--bar-"],
    )
    def test_invalid_slugs(self, slug: str) -> None:
        with pytest.raises(CreateError):
            validate_slug(slug)


class TestSlugify:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("Add User Auth", "add-user-auth"),
            ("  Refactor the CLI parser  ", "refactor-the-cli-parser"),
            ("Foo: bar / baz!!", "foo-bar-baz"),
            ("already-a-slug", "already-a-slug"),
            ("MixedCASE123", "mixedcase123"),
        ],
    )
    def test_basic_slugification(self, text: str, expected: str) -> None:
        assert slugify(text) == expected

    def test_truncates_to_max_words(self) -> None:
        assert slugify("one two three four five six seven") == (
            "one-two-three-four-five-six"
        )
        assert slugify("a b c", max_words=2) == "a-b"

    @pytest.mark.parametrize("text", ["", "   ", "!!!", "x", "_"])
    def test_returns_empty_when_nothing_slug_worthy(self, text: str) -> None:
        # Single-char / empty results can't satisfy SLUG_RE (>=2 chars).
        assert slugify(text) == ""

    def test_result_always_validates_when_nonempty(self) -> None:
        out = slugify("Some Plan Title")
        assert out
        validate_slug(out)  # should not raise


class TestParseSlugResponse:
    def test_takes_first_nonblank_line(self) -> None:
        assert _parse_slug_response("\n\nadd-user-auth\nextra\n") == (
            "add-user-auth"
        )

    def test_strips_backticks_and_normalizes(self) -> None:
        assert _parse_slug_response("`Add User Auth`") == "add-user-auth"

    @pytest.mark.parametrize("raw", ["", "   ", "\n\n", "`` "])
    def test_returns_none_when_nothing_usable(self, raw: str) -> None:
        assert _parse_slug_response(raw) is None


class TestSuggestSlug:
    def test_uses_claude_response(self) -> None:
        slug = suggest_slug(
            "We want to add user authentication",
            lambda _prompt: "add-user-auth",
            reporter=NullReporter(),
        )
        assert slug == "add-user-auth"

    def test_falls_back_to_first_line_when_claude_empty(self) -> None:
        slug = suggest_slug(
            "# Refactor the CLI parser\n\nmore prose",
            lambda _prompt: "",
            reporter=NullReporter(),
        )
        assert slug == "refactor-the-cli-parser"

    def test_falls_back_when_claude_unparseable(self) -> None:
        slug = suggest_slug(
            "Add caching layer",
            lambda _prompt: "```",
            reporter=NullReporter(),
        )
        assert slug == "add-caching-layer"

    def test_returns_none_when_no_source_and_dead_invoker(self) -> None:
        assert (
            suggest_slug("", lambda _prompt: "", reporter=NullReporter())
            is None
        )


class TestResolveCreateSlug:
    def _invoker(self, value: str) -> Callable[[str], str]:
        return lambda _prompt: value

    def test_provided_slug_validated_and_returned(self) -> None:
        out = resolve_create_slug(
            "my-slug", None, self._invoker("ignored"),
        )
        assert out == "my-slug"

    def test_provided_invalid_slug_raises(self) -> None:
        with pytest.raises(CreateError):
            resolve_create_slug("Bad Slug", None, self._invoker("x"))

    def test_suggests_and_accepts_default_on_blank_input(self) -> None:
        out = resolve_create_slug(
            None,
            "Add user auth",
            self._invoker("add-user-auth"),
            input_fn=_queue_input([""]),
            reporter=NullReporter(),
        )
        assert out == "add-user-auth"

    def test_user_overrides_suggestion(self) -> None:
        out = resolve_create_slug(
            None,
            "Add user auth",
            self._invoker("add-user-auth"),
            input_fn=_queue_input(["different-slug"]),
            reporter=NullReporter(),
        )
        assert out == "different-slug"

    def test_reprompts_until_valid(self) -> None:
        out = resolve_create_slug(
            None,
            "Add user auth",
            self._invoker("add-user-auth"),
            input_fn=_queue_input(["Bad Slug", "good-slug"]),
            reporter=NullReporter(),
        )
        assert out == "good-slug"

    def test_yes_takes_suggestion_without_prompting(self) -> None:
        out = resolve_create_slug(
            None,
            "Add user auth",
            self._invoker("add-user-auth"),
            input_fn=_queue_input([]),  # must not be consulted
            yes=True,
            reporter=NullReporter(),
        )
        assert out == "add-user-auth"

    def test_raises_when_no_slug_and_no_description(self) -> None:
        with pytest.raises(CreateError, match="pass a slug explicitly"):
            resolve_create_slug(None, None, self._invoker("x"))

    def test_raises_when_no_slug_and_blank_description(self) -> None:
        with pytest.raises(CreateError, match="pass a slug explicitly"):
            resolve_create_slug(None, "   ", self._invoker("x"))


class TestResolveOutputDir:
    def test_default_under_repo_root(self, tmp_path: Path) -> None:
        out = resolve_output_dir(tmp_path)
        assert out == (tmp_path / "docs" / "implementation-plans").resolve()

    def test_relative_override_resolved_against_repo(self, tmp_path: Path) -> None:
        out = resolve_output_dir(tmp_path, Path("docs/ip"))
        assert out == (tmp_path / "docs" / "ip").resolve()

    def test_absolute_override_kept(self, tmp_path: Path) -> None:
        abs_dir = tmp_path / "elsewhere"
        out = resolve_output_dir(tmp_path, abs_dir)
        assert out == abs_dir.resolve()


class TestCheckCollision:
    def test_no_collision_when_dir_missing(self, tmp_path: Path) -> None:
        check_collision(tmp_path / "nope", "foo")  # must not raise

    def test_detects_priority_prefixed_match(self, tmp_path: Path) -> None:
        (tmp_path / "2-foo.md").write_text("x", encoding="utf-8")
        with pytest.raises(FileExistsError, match="foo"):
            check_collision(tmp_path, "foo")

    def test_detects_unprefixed_match(self, tmp_path: Path) -> None:
        (tmp_path / "foo.md").write_text("x", encoding="utf-8")
        with pytest.raises(FileExistsError, match="foo"):
            check_collision(tmp_path, "foo")

    def test_allows_distinct_slug(self, tmp_path: Path) -> None:
        (tmp_path / "1-other.md").write_text("x", encoding="utf-8")
        check_collision(tmp_path, "foo")  # must not raise

    def test_does_not_false_match_on_suffix(self, tmp_path: Path) -> None:
        """Regression: creating slug `bar` must not collide with `1-foo-bar.md`.

        The glob was originally `*-{slug}.md`, which matches any filename ending
        in `-{slug}`. Narrowing to `[123]-{slug}.md` fixes the false positive.
        """
        (tmp_path / "1-foo-bar.md").write_text("x", encoding="utf-8")
        check_collision(tmp_path, "bar")  # must not raise


class TestValidateOutputDirInRepo:
    def test_accepts_dir_inside_repo(self, tmp_path: Path) -> None:
        inner = tmp_path / "sub"
        inner.mkdir()
        validate_output_dir_in_repo(inner, tmp_path)

    def test_rejects_dir_outside_repo(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        outside = tmp_path / "outside"
        repo.mkdir()
        outside.mkdir()
        with pytest.raises(CreateError, match="not inside"):
            validate_output_dir_in_repo(outside, repo)


class TestPromptsOnNonInteractiveStdin:
    """EOF on a closed stdin resolves each prompt to its documented default
    instead of raising an unhandled EOFError. See BUG_BACKLOG."""

    @staticmethod
    def _eof(_prompt: str) -> str:
        raise EOFError("EOF when reading a line")

    def test_ask_takes_default(self) -> None:
        assert _ask(self._eof, "Output directory: ", default="docs/x") == "docs/x"

    def test_ask_optional_returns_empty(self) -> None:
        assert _ask(self._eof, "Optional: ") == ""

    def test_ask_required_without_default_fails_clean(self) -> None:
        # No default to take, and re-prompting would spin against closed
        # stdin — a clean CreateError, not an EOFError and not a hang.
        with pytest.raises(CreateError, match="non-interactive stdin"):
            _ask(self._eof, "Title: ", required=True)

    def test_ask_choice_takes_default(self) -> None:
        got = _ask_choice(
            self._eof, "Change type", choices=("code", "non-code"), default="code"
        )
        assert got == "code"

    def test_ask_yn_takes_default_both_ways(self) -> None:
        assert _ask_yn(self._eof, "Replace?", default=False) is False
        assert _ask_yn(self._eof, "Proceed?", default=True) is True

    def test_ask_int_list_returns_empty(self) -> None:
        got = _ask_int_list(self._eof, "deps: ", valid_ids={1, 2}, self_id=3)
        assert got == []

    def test_default_is_announced_on_stderr(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _ask(self._eof, "Output directory: ", default="docs/x")
        assert "non-interactive stdin" in capsys.readouterr().err


class TestAskIntList:
    def test_blank_returns_empty(self) -> None:
        got = _ask_int_list(
            _queue_input([""]), "x: ", valid_ids={1, 2}, self_id=3
        )
        assert got == []

    def test_valid_ids_returned(self) -> None:
        got = _ask_int_list(
            _queue_input(["1, 2"]), "x: ", valid_ids={1, 2}, self_id=3
        )
        assert got == [1, 2]

    @pytest.mark.parametrize(
        "bad_input, expected_error",
        [
            ("oops", "comma-separated integers"),  # non-int
            ("99", "unknown step id"),  # id not in valid_ids
            ("2", "cannot depend on itself"),  # self_id == 2 rejection
        ],
        ids=["non_int", "unknown_id", "self_dep"],
    )
    def test_reprompts_on_invalid_input(
        self,
        capsys: pytest.CaptureFixture[str],
        bad_input: str,
        expected_error: str,
    ) -> None:
        """Each invalid input shape triggers the matching reprompt
        message; subsequent valid input is accepted. Consolidated from
        three near-identical tests."""
        got = _ask_int_list(
            _queue_input([bad_input, "1"]),
            "x: ",
            valid_ids={1},
            self_id=2,
        )
        assert got == [1]
        assert expected_error in capsys.readouterr().out


class TestWriteNewPlan:
    def test_file_has_priority_prefix(self, tmp_path: Path) -> None:
        plan = Plan(
            title="T",
            status=PlanStatus.PLANNING,
            priority=Priority.HIGH,
            steps=[Step(id=1, title="s")],
        )
        path = write_new_plan(tmp_path, "foo", plan)
        assert path.name == "1-foo.md"

    def test_medium_gets_prefix_two(self, tmp_path: Path) -> None:
        plan = Plan(
            title="T",
            status=PlanStatus.PLANNING,
            priority=Priority.MEDIUM,
            steps=[Step(id=1, title="s")],
        )
        assert write_new_plan(tmp_path, "foo", plan).name == "2-foo.md"

    def test_low_gets_prefix_three(self, tmp_path: Path) -> None:
        plan = Plan(
            title="T",
            status=PlanStatus.PLANNING,
            priority=Priority.LOW,
            steps=[Step(id=1, title="s")],
        )
        assert write_new_plan(tmp_path, "foo", plan).name == "3-foo.md"

    def test_output_parses_round_trip(self, tmp_path: Path) -> None:
        plan = Plan(
            title="Demo",
            status=PlanStatus.PLANNING,
            priority=Priority.MEDIUM,
            steps=[Step(id=1, title="first", complexity=Complexity.LOW)],
        )
        path = write_new_plan(tmp_path, "demo", plan)
        reloaded = parse_plan(path)
        assert reloaded.title == "Demo"
        assert reloaded.priority == Priority.MEDIUM
        assert reloaded.steps[0].title == "first"
        assert "# Demo" in path.read_text(encoding="utf-8")


    def test_interrupted_initial_write_leaves_an_invalid_stub(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan = Plan(
            title="Demo",
            status=PlanStatus.PLANNING,
            priority=Priority.MEDIUM,
            steps=[Step(id=1, title="first")],
        )
        monkeypatch.setattr(
            create_module,
            "write_plan",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("write stopped")),
        )
        with pytest.raises(OSError, match="write stopped"):
            write_new_plan(tmp_path, "demo", plan)
        from plan_tool.parser import ValidationError as PlanValidationError

        with pytest.raises(PlanValidationError):
            parse_plan(tmp_path / "2-demo.md")

class TestAppendToManifest:
    def test_creates_manifest_when_missing(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        plan = tmp_path / "plans" / "1-foo.md"
        plan.parent.mkdir()
        plan.write_text("x", encoding="utf-8")
        mf = tmp_path / "m.json"
        updated = append_to_manifest(mf, tmp_path, plan)
        assert updated is True
        data = json.loads(mf.read_text(encoding="utf-8"))
        assert data == {"plans": ["plans/1-foo.md"]}

    def test_appends_to_existing_manifest(self, tmp_path: Path) -> None:
        plan = tmp_path / "plans" / "1-foo.md"
        plan.parent.mkdir()
        plan.write_text("x", encoding="utf-8")
        mf = tmp_path / "m.json"
        mf.write_text(json.dumps({"plans": ["other.md"]}), encoding="utf-8")
        append_to_manifest(mf, tmp_path, plan)
        data = json.loads(mf.read_text(encoding="utf-8"))
        assert data["plans"] == ["other.md", "plans/1-foo.md"]

    def test_noop_when_already_listed(self, tmp_path: Path) -> None:
        plan = tmp_path / "1-foo.md"
        plan.write_text("x", encoding="utf-8")
        mf = tmp_path / "m.json"
        mf.write_text(json.dumps({"plans": ["1-foo.md"]}), encoding="utf-8")
        updated = append_to_manifest(mf, tmp_path, plan)
        assert updated is False
        data = json.loads(mf.read_text(encoding="utf-8"))
        assert data["plans"] == ["1-foo.md"]  # not duplicated

    def test_rejects_plan_outside_repo_root(self, tmp_path: Path) -> None:
        outside = tmp_path / "outside"
        outside.mkdir()
        plan = outside / "1-foo.md"
        plan.write_text("x", encoding="utf-8")
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        mf = repo_root / "m.json"
        with pytest.raises(CreateError, match="not inside"):
            append_to_manifest(mf, repo_root, plan)

    def test_rejects_malformed_existing_manifest(self, tmp_path: Path) -> None:
        plan = tmp_path / "1-foo.md"
        plan.write_text("x", encoding="utf-8")
        mf = tmp_path / "m.json"
        mf.write_text("{ not valid", encoding="utf-8")
        with pytest.raises(CreateError, match="invalid JSON"):
            append_to_manifest(mf, tmp_path, plan)


@pytest.mark.integration
class TestCreatePlanBlankSkeleton:
    @pytest.fixture(autouse=True)
    def _stub_propose_references(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Stub the references-proposal claude call site. These tests
        don't pass ``from_description=`` (so ``propose_steps_from_claude``
        is skipped) and don't assert anything about references — they
        exercise the interactive-wizard path. Without this, the
        production default would shell out to real claude for the
        "Researching developer docs" step."""
        from plan_tool import create as create_module
        monkeypatch.setattr(
            create_module, "propose_references_from_claude",
            lambda *a, **kw: ReferenceResearchResult.from_references([]),
        )

    def test_happy_path(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"
        answers = _basic_metadata_answers() + _single_step_answers()

        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            input_fn=_queue_input(answers),
        )

        assert result.plan_path == (out_dir / "2-demo.md")
        assert result.manifest_updated is True

        plan = parse_plan(result.plan_path)
        assert plan.title == "Demo Plan"
        assert plan.priority == Priority.MEDIUM
        assert plan.lessons is None
        assert [s.title for s in plan.steps] == ["First step"]
        assert plan.steps[0].complexity == Complexity.LOW

        data = json.loads(manifest.read_text(encoding="utf-8"))
        assert data["plans"] == ["plans/2-demo.md"]
        assert data["plans"].count("plans/2-demo.md") == 1  # exactly once

    def test_manifest_lands_under_repo_root_not_cwd(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Two independent project roots, each with its own .git marker.
        cwd_root = tmp_path / "cwd-repo"
        repo_root = tmp_path / "other-repo"
        for root in (cwd_root, repo_root):
            root.mkdir()
            (root / ".git").mkdir()
        out_dir = repo_root / "plans"
        out_dir.mkdir()
        monkeypatch.chdir(cwd_root)

        answers = _basic_metadata_answers() + _single_step_answers()
        result = create_plan(
            "demo",
            repo_root=repo_root,
            output_dir_override=out_dir,
            manifest_path=None,
            input_fn=_queue_input(answers),
        )

        expected_manifest = repo_root / ".plan-tool" / "plans.json"
        assert result.manifest_path == expected_manifest
        assert expected_manifest.exists()
        # The manifest must not land under the cwd-derived root.
        assert not (cwd_root / ".plan-tool" / "plans.json").exists()
        # Plan file and manifest entry agree on repo_root, not cwd.
        assert result.plan_path is not None
        assert repo_root in result.plan_path.parents

    def test_slug_collision_aborts(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        (out_dir / "1-demo.md").write_text("x", encoding="utf-8")
        manifest = tmp_path / "m.json"

        with pytest.raises(FileExistsError, match="demo"):
            create_plan(
                "demo",
                repo_root=tmp_path,
                output_dir_override=out_dir,
                manifest_path=manifest,
                input_fn=_queue_input([]),  # never consumed
                replace_on_collision=False,
            )

    def test_invalid_slug_rejected_before_prompts(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        with pytest.raises(CreateError, match="invalid slug"):
            create_plan(
                "Bad Slug",
                repo_root=tmp_path,
                input_fn=_queue_input([]),
            )

    def test_lessons_path_default_is_repo_relative(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "docs" / "ip"
        out_dir.mkdir(parents=True)
        manifest = tmp_path / "m.json"
        # enable lessons (answer 'y'), accept default path (answer '')
        answers = (
            ["My Plan", "low", "y", ""]
            + _single_step_answers()
        )

        create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            input_fn=_queue_input(answers),
        )

        plan = parse_plan(out_dir / "3-demo.md")
        assert plan.lessons == "docs/ip/plan-details/demo/lessons.md"

    def test_new_plans_enable_test_enforcement(self, tmp_path: Path) -> None:
        """New plans opt into test enforcement by default (backward-compat
        legacy plans, which lack the key, stay off)."""
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "docs" / "ip"
        out_dir.mkdir(parents=True)
        manifest = tmp_path / "m.json"
        answers = ["My Plan", "low", "n"] + _single_step_answers()

        create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            input_fn=_queue_input(answers),
        )

        plan = parse_plan(out_dir / "3-demo.md")
        assert plan.enforce_step_tests is True

    def test_enforce_step_tests_survives_rewrite(self, tmp_path: Path) -> None:
        """The switch round-trips through a parse → mutate → write_plan cycle
        (run's status write-back, reconcile, etc. must not drop it)."""
        from plan_tool.parser import write_plan
        from plan_tool.schema import StepStatus

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "docs" / "ip"
        out_dir.mkdir(parents=True)
        manifest = tmp_path / "m.json"
        answers = ["My Plan", "low", "n"] + _single_step_answers()

        create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            input_fn=_queue_input(answers),
        )

        path = out_dir / "3-demo.md"
        plan = parse_plan(path)
        assert plan.enforce_step_tests is True
        # Mutate a step's status (as run's write-back would) and rewrite.
        plan.steps[0].status = StepStatus.DONE
        write_plan(path, plan, expect_unchanged=False)

        assert parse_plan(path).enforce_step_tests is True

    def test_output_dir_outside_repo_rejected_before_write(
        self, tmp_path: Path
    ) -> None:
        """Orphan-file regression: containment must be checked upfront.

        Previously, ``write_new_plan`` ran first and left the .md on disk while
        ``append_to_manifest`` rejected the path for being outside the repo.
        """
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".git").mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        manifest = repo / "m.json"

        with pytest.raises(CreateError, match="not inside"):
            create_plan(
                "demo",
                repo_root=repo,
                output_dir_override=outside,
                manifest_path=manifest,
                input_fn=_queue_input([]),  # never consumed
            )
        # No plan file created.
        assert list(outside.iterdir()) == []
        assert not manifest.exists()

    def test_prompts_for_output_dir_when_not_provided(self, tmp_path: Path) -> None:
        """With no --output-dir flag, the wizard prompts for it (default wins on blank)."""
        (tmp_path / ".git").mkdir()
        manifest = tmp_path / "m.json"
        # First answer is blank → accept default `docs/implementation-plans/`.
        answers = [""] + _basic_metadata_answers() + _single_step_answers()

        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=None,
            manifest_path=manifest,
            input_fn=_queue_input(answers),
        )

        expected = tmp_path / "docs" / "implementation-plans" / "2-demo.md"
        assert result.plan_path == expected.resolve()
        assert result.plan_path.is_file()

    def test_noop_manifest_when_already_present(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"
        manifest.write_text(
            json.dumps({"plans": ["plans/2-demo.md"]}), encoding="utf-8"
        )
        answers = _basic_metadata_answers() + _single_step_answers()

        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            input_fn=_queue_input(answers),
        )

        assert result.manifest_updated is False
        data = json.loads(manifest.read_text(encoding="utf-8"))
        assert data["plans"] == ["plans/2-demo.md"]  # still exactly one


class TestCreatePlanTestCommandResolution:
    """New-plan test commands come only from qualification or this invocation."""

    _SEED = "## Outcome\n\nCreate the plan fixture.\n"

    def _create(
        self,
        root: Path,
        slug: str,
        *,
        input_fn: Callable[[str], str],
        yes: bool = False,
    ) -> CreateResult:
        (root / ".git").mkdir(exist_ok=True)
        output_dir = root / "plans"
        output_dir.mkdir(exist_ok=True)
        return create_plan(
            slug,
            repo_root=root,
            output_dir_override=output_dir,
            manifest_path=root / "plans.json",
            from_description=self._SEED,
            input_fn=input_fn,
            claude_invoker=lambda _prompt: _ONE_STEP_JSON,
            yes=yes,
        )

    def test_create_plan_uses_preflight_qualified_test_command(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool import create as create_module
        from plan_tool.runner_detect import UV_PYTEST_COMMAND

        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        qualified_roots: list[Path] = []

        def qualify(repo_root: Path) -> str:
            qualified_roots.append(repo_root)
            return UV_PYTEST_COMMAND

        monkeypatch.setattr(
            create_module,
            "qualify_uv_pytest_command",
            qualify,
        )
        prompts: list[str] = []
        answers = iter(_basic_metadata_answers() + [""])

        def input_fn(prompt: str) -> str:
            prompts.append(prompt)
            assert "Test command" not in prompt
            return next(answers)

        result = self._create(tmp_path, "demo", input_fn=input_fn)

        assert parse_plan(result.plan_path).test_command == UV_PYTEST_COMMAND
        assert f"test_command: {UV_PYTEST_COMMAND}\n" in result.plan_path.read_text(
            encoding="utf-8"
        )
        assert qualified_roots == [tmp_path.resolve()]
        assert not any("Test command" in prompt for prompt in prompts)

    def test_create_plan_prompts_once_for_unknown_test_command(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool import create as create_module

        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        monkeypatch.setattr(
            create_module, "qualify_uv_pytest_command", lambda repo_root: None
        )
        prompts: list[str] = []
        answers = iter(_basic_metadata_answers() + ["", "make test"])

        def input_fn(prompt: str) -> str:
            prompts.append(prompt)
            return next(answers)

        result = self._create(tmp_path, "demo", input_fn=input_fn)

        assert parse_plan(result.plan_path).test_command == "make test"
        assert [p for p in prompts if "Test command" in p] == [
            "Test command (optional, blank to omit): "
        ]

    def test_create_plan_trims_operator_test_command_without_rewriting_it(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool import create as create_module

        command = "  uv run pytest tests/ -q && echo 'TODO TBD'  "
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        monkeypatch.setattr(
            create_module, "qualify_uv_pytest_command", lambda repo_root: None
        )

        result = self._create(
            tmp_path,
            "demo",
            input_fn=_queue_input(
                _basic_metadata_answers() + ["", command], test_command=None
            ),
        )

        assert parse_plan(result.plan_path).test_command == command.strip()

    @pytest.mark.parametrize(
        "operator_command",
        ["", "   ", "TODO", "(TODO)", "_(TODO)_", "TBD", "(TBD)", "_(TBD)_"],
    )
    def test_create_plan_omits_blank_or_placeholder_test_command(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        operator_command: str,
    ) -> None:
        from plan_tool import create as create_module

        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        monkeypatch.setattr(
            create_module, "qualify_uv_pytest_command", lambda repo_root: None
        )

        result = self._create(
            tmp_path,
            "demo",
            input_fn=_queue_input(
                _basic_metadata_answers() + ["", operator_command],
                test_command=None,
            ),
        )

        assert parse_plan(result.plan_path).test_command is None
        assert "test_command:" not in result.plan_path.read_text(encoding="utf-8")

    @pytest.mark.parametrize(
        "operator_command",
        ["echo TODO", "uv run pytest --tb=short # TBD"],
    )
    def test_create_plan_keeps_command_containing_placeholder_text(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        operator_command: str,
    ) -> None:
        from plan_tool import create as create_module

        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        monkeypatch.setattr(
            create_module, "qualify_uv_pytest_command", lambda repo_root: None
        )

        result = self._create(
            tmp_path,
            "demo",
            input_fn=_queue_input(
                _basic_metadata_answers() + ["", operator_command],
                test_command=None,
            ),
        )

        assert parse_plan(result.plan_path).test_command == operator_command

    def test_create_plan_unknown_test_command_omits_without_prompt_under_yes(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool import create as create_module

        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        monkeypatch.setattr(
            create_module, "qualify_uv_pytest_command", lambda repo_root: None
        )
        prompts: list[str] = []

        def input_fn(prompt: str) -> str:
            prompts.append(prompt)
            assert "Test command" not in prompt
            return ""

        result = self._create(tmp_path, "demo", input_fn=input_fn, yes=True)

        assert parse_plan(result.plan_path).test_command is None
        assert "test_command:" not in result.plan_path.read_text(encoding="utf-8")
        stderr_lines = capsys.readouterr().err.splitlines()
        assert sum("test command omitted:" in line for line in stderr_lines) == 1
        assert not any("Test command" in prompt for prompt in prompts)

    def test_create_plan_unknown_test_command_omits_without_prompt_on_non_tty(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool import create as create_module

        monkeypatch.setattr("sys.stdin.isatty", lambda: False)
        monkeypatch.setattr(
            create_module, "qualify_uv_pytest_command", lambda repo_root: None
        )
        prompts: list[str] = []

        def input_fn(prompt: str) -> str:
            prompts.append(prompt)
            assert "Test command" not in prompt
            return ""

        result = self._create(tmp_path, "demo", input_fn=input_fn)

        assert parse_plan(result.plan_path).test_command is None
        assert "test_command:" not in result.plan_path.read_text(encoding="utf-8")
        stderr_lines = capsys.readouterr().err.splitlines()
        assert sum("test command omitted:" in line for line in stderr_lines) == 1
        assert not any("Test command" in prompt for prompt in prompts)

    def test_create_plan_does_not_reuse_operator_test_command_across_invocations(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool import create as create_module

        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        monkeypatch.setattr(
            create_module, "qualify_uv_pytest_command", lambda repo_root: None
        )

        first = self._create(
            tmp_path,
            "first",
            input_fn=_queue_input(
                _basic_metadata_answers() + ["", "make first-test"],
                test_command=None,
            ),
        )
        second = self._create(
            tmp_path,
            "second",
            input_fn=_queue_input(
                _basic_metadata_answers() + ["", ""], test_command=None
            ),
        )

        assert parse_plan(first.plan_path).test_command == "make first-test"
        assert parse_plan(second.plan_path).test_command is None


@pytest.mark.integration
class TestCreatePlanFromDescription:
    def test_happy_path_uses_claude_steps(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        canned = json.dumps(
            [
                _proposed_step("one"),
                _proposed_step(
                    "two", complexity=None, files=["x.py"], depends_on=[1]
                ),
            ]
        )
        # No step prompts needed — claude steps are accepted.
        answers = _basic_metadata_answers()

        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="Build a thing",
            input_fn=_queue_input(answers),
            claude_invoker=lambda prompt: (
                _valid_preparation_response(prompt)
                if "Distill a free-form seed" in prompt
                else canned
            ),
        )

        plan = parse_plan(result.plan_path)
        assert [s.title for s in plan.steps] == ["one", "two"]
        assert plan.steps[0].complexity == Complexity.LOW
        assert plan.steps[1].files == ["x.py"]
        assert plan.steps[1].depends_on == [1]

    def test_proposed_intents_reach_the_written_frontmatter(
        self, tmp_path: Path
    ) -> None:
        """End-to-end: a proposal's intents survive the merge paths that
        rebuild steps by ``model_copy`` and round-trip through ``parse_plan``.
        Those merges carry unlisted fields forward — this pins that, rather
        than any code asserting it."""
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()

        canned = json.dumps(
            [
                _proposed_step("one", intent="ground the parser"),
                _proposed_step("two", intent="wire the CLI", depends_on=[1]),
            ]
        )
        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=tmp_path / "m.json",
            from_description="Build a thing",
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=lambda prompt: canned,
        )

        assert "\n  intent: ground the parser\n" in result.plan_path.read_text(
            encoding="utf-8"
        )
        plan = parse_plan(result.plan_path)
        assert [s.intent for s in plan.steps] == [
            "ground the parser",
            "wire the CLI",
        ]
        # ``_seed_initial_step_status`` promotes step 1 to ``current`` via
        # ``model_copy`` — the intent rides through untouched.
        assert plan.steps[0].status == StepStatus.CURRENT

    def test_claude_steps_carry_creates_field(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        canned = json.dumps(
            [
                {
                    "title": "scaffold",
                    "complexity": "medium",
                    "files": ["existing.py"],
                    "creates": ["pkg/new_module.py"],
                    "depends_on": [],
                },
            ]
        )
        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="Build a thing",
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=lambda prompt: canned,
        )

        plan = parse_plan(result.plan_path)
        assert plan.steps[0].files == ["existing.py"]
        assert plan.steps[0].creates == ["pkg/new_module.py"]
        # creates round-trips through the on-disk frontmatter.
        assert "creates:" in result.plan_path.read_text(encoding="utf-8")

    def test_bad_json_falls_back_to_interactive(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        # Metadata + one interactive step since fallback kicks in.
        answers = _basic_metadata_answers() + _single_step_answers()

        def invoker(prompt: str) -> str:
            if "Distill a free-form seed" in prompt:
                return _valid_preparation_response(prompt)
            if "developer and API reference documentation" in prompt:
                return "[]"
            return "sorry I can't do that"

        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="Build a thing",
            input_fn=_queue_input(answers),
            claude_invoker=invoker,
        )

        plan = parse_plan(result.plan_path)
        assert [s.title for s in plan.steps] == ["First step"]
        out = capsys.readouterr().out
        assert "parseable" in out  # fallback notice surfaced

    def test_invalid_graph_from_claude_falls_back(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Claude-proposed steps with an unknown depends_on fall back to interactive,
        rather than raising pydantic.ValidationError at final Plan construction.
        """
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"
        bad_graph = json.dumps(
            [
                {"title": "only", "complexity": None, "files": [],
                 "depends_on": [99]},  # references nonexistent step
            ]
        )
        answers = _basic_metadata_answers() + _single_step_answers()

        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="Build a thing",
            input_fn=_queue_input(answers),
            claude_invoker=lambda prompt: bad_graph,
        )

        plan = parse_plan(result.plan_path)
        assert [s.title for s in plan.steps] == ["First step"]  # interactive wins
        assert "parseable" in capsys.readouterr().out

    def test_claude_extra_text_around_json_still_parses(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        chatter = (
            "Sure, here's my proposal:\n"
            '[{"title": "only", "complexity": null, "files": [], "depends_on": []}]\n'
            "Let me know if you'd like changes."
        )
        answers = _basic_metadata_answers()

        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="Build a thing",
            input_fn=_queue_input(answers),
            claude_invoker=lambda prompt: chatter,
        )

        plan = parse_plan(result.plan_path)
        assert [s.title for s in plan.steps] == ["only"]


class TestSeedOutcomeBecomesPlanIntent:
    """The seed's ``## Outcome`` maps to the new plan's ``intent``.

    Presence only — nothing here judges an Outcome's quality, and a seed that
    states none leaves ``intent`` unset for the intent proposer.
    """

    _STEPS_JSON = _ONE_STEP_JSON

    def _create(self, root: Path, seed: str, **kwargs) -> CreateResult:
        (root / ".git").mkdir(parents=True)
        out_dir = root / "plans"
        out_dir.mkdir()
        kwargs.setdefault("claude_invoker", lambda _prompt: self._STEPS_JSON)
        return create_plan(
            "demo",
            repo_root=root,
            output_dir_override=out_dir,
            manifest_path=root / "m.json",
            from_description=seed,
            input_fn=_queue_input(_basic_metadata_answers()),
            **kwargs,
        )

    def _intent(self, root: Path, seed: str, **kwargs) -> Optional[str]:
        return parse_plan(self._create(root, seed, **kwargs).plan_path).intent

    def test_outcome_section_becomes_plan_intent(self, tmp_path: Path) -> None:
        seed = "## Outcome\n\nShip the thing\n\n## Why\n\nBecause.\n"
        assert self._intent(tmp_path, seed) == "Ship the thing"

    def test_outcome_is_read_before_distillation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Distillation drops ``## Outcome``; the map runs on the raw seed."""
        from plan_tool import create as create_module
        from plan_tool.create import DistillOutcome

        distilled = (
            "## Overview\n\nDistilled overview.\n\n"
            "## Problem statement\n\nDistilled problem.\n"
        )
        distill_calls: list[str] = []

        def fake_distill(source_text: str, *_args, **_kwargs) -> DistillOutcome:
            distill_calls.append(source_text)
            return _normalized_outcome_for_test(
                {"Overview": "Distilled overview.", "Problem statement": "Distilled problem."}
            )

        monkeypatch.setattr(
            create_module, "propose_distilled_seed_from_claude", fake_distill
        )

        seed = "## Outcome\n\nShip the thing\n\n## Why\n\nBecause.\n"
        intent = self._intent(tmp_path, seed, distill=True)

        # Pin that distillation actually ran and dropped the heading — a
        # skipped pass would leave this asserting nothing about read order.
        assert distill_calls == [seed]
        assert "## Outcome" not in distilled
        assert intent == "Ship the thing"

    def test_wrapped_outcome_collapses_to_one_line(self, tmp_path: Path) -> None:
        seed = (
            "## Outcome\n\n"
            "Ship the thing so a stated why\ntravels with the work\n"
            "instead of being re-inferred.\n"
        )
        assert self._intent(tmp_path, seed) == (
            "Ship the thing so a stated why travels with the work instead of "
            "being re-inferred."
        )

    def test_first_outcome_paragraph_becomes_plan_intent(
        self, tmp_path: Path
    ) -> None:
        seed = (
            "## Outcome\n\n"
            "Make the stated result the plan intent.\n\n"
            "Product shape and scope fence prose stay in the seed body.\n"
            "---\n"
        )
        assert self._intent(tmp_path, seed) == (
            "Make the stated result the plan intent."
        )

    @pytest.mark.parametrize("thematic_break", ("---", "***", "___"))
    def test_thematic_break_is_not_part_of_outcome_intent(
        self, thematic_break: str
    ) -> None:
        seed = f"## Outcome\n\nShip the result.\n{thematic_break}\n"
        assert _intent_from_seed_outcome(seed) == "Ship the result."

    @pytest.mark.parametrize("thematic_break", ("---", "***", "___"))
    def test_thematic_break_preserves_outcome_paragraph_boundary(
        self, thematic_break: str
    ) -> None:
        seed = (
            f"## Outcome\n\nResult sentence.\n{thematic_break}\n"
            "Product fence paragraph two.\n"
        )
        assert _intent_from_seed_outcome(seed) == "Result sentence."

    def test_placeholder_outcome_leaves_intent_unset(
        self, tmp_path: Path
    ) -> None:
        result = self._create(tmp_path, "## Outcome\n\n_(TODO)_\n")
        assert parse_plan(result.plan_path).intent is None
        # Plan-level only: the proposal's step intents render indented under
        # ``steps:``, so anchor on the column-0 frontmatter key.
        assert "\nintent:" not in result.plan_path.read_text(encoding="utf-8")

    def test_seed_without_outcome_leaves_intent_unset(
        self, tmp_path: Path
    ) -> None:
        """No substitute: not the title, not the seed's first line."""
        seed = "## Why\n\nBecause the thing is broken.\n"
        assert self._intent(tmp_path, seed) is None

    def test_outcome_heading_matches_case_insensitively(
        self, tmp_path: Path
    ) -> None:
        assert self._intent(tmp_path, "## outcome\n\nShip the thing\n") == (
            "Ship the thing"
        )

    def test_first_outcome_wins_on_duplicate_heading(self) -> None:
        """Matches ``extract_h2_sections``, which keeps the first occurrence.

        Driven at the helper: ``create_plan`` rejects *any* seed with a
        repeated H2 title before the map is reached, because the concept
        bootstrap mints one id per section and two same-named sections
        collide. That failure is independent of ``## Outcome``.
        """
        seed = "## Outcome\n\nFirst outcome\n\n## Outcome\n\nSecond outcome\n"
        assert _intent_from_seed_outcome(seed) == "First outcome"

    def test_intent_round_trips_through_the_written_plan(
        self, tmp_path: Path
    ) -> None:
        result = self._create(tmp_path, "## Outcome\n\nShip the thing\n")
        text = result.plan_path.read_text(encoding="utf-8")
        assert "intent: Ship the thing" in text
        assert parse_plan(result.plan_path).intent == "Ship the thing"

    def test_frontmatter_comment_does_not_shadow_the_real_outcome(self) -> None:
        """A ``##``-prefixed YAML comment is legal at column 0 in frontmatter.

        Without the leading-block strip the comment parses as the first
        ``outcome`` section and its body is the rest of the frontmatter.
        Driven at the helper for the duplicate-heading reason above.
        """
        seed = (
            "---\n"
            "## Outcome\n"
            "status: planning\n"
            "---\n\n"
            "## Outcome\n\nShip the thing\n"
        )
        assert _intent_from_seed_outcome(seed) == "Ship the thing"

    def test_mapping_adds_no_claude_call(self, tmp_path: Path) -> None:
        with_outcome = "## Why\n\nBecause.\n\n## Outcome\n\nShip the thing\n"
        without_outcome = "## Why\n\nBecause.\n"

        counts: list[int] = []
        for name, seed in (
            ("with", with_outcome),
            ("without", without_outcome),
        ):
            calls = 0

            def invoker(_prompt: str) -> str:
                nonlocal calls
                calls += 1
                return self._STEPS_JSON

            self._create(tmp_path / name, seed, claude_invoker=invoker)
            counts.append(calls)

        assert counts[0] == counts[1]

    def test_plan_intent_never_reaches_step_intents(self, tmp_path: Path) -> None:
        """Step-level intent comes from the proposal; this map is plan-only."""
        plan = parse_plan(
            self._create(tmp_path, "## Outcome\n\nShip the thing\n").plan_path
        )
        assert plan.intent == "Ship the thing"
        assert [s.intent for s in plan.steps] == ["prove one lands"]


_INTENT_PROMPT_MARKER = "Draft a one-line `intent` for each target"
_SPLIT_PROMPT_MARKER = "You are decomposing ONE implementation step"
_INTENT_WALK_MARKER = "(a)ccept / (e)dit / (d)ecline"


def _is_intent_prompt(prompt: str) -> bool:
    return _INTENT_PROMPT_MARKER in prompt


def _intent_json(*drafts: tuple[object, str]) -> str:
    """Canned intent-proposal body from ``(target, intent)`` pairs."""
    return json.dumps([{"target": t, "intent": i} for t, i in drafts])


class _CreateInvokerFake:
    """Recording ``claude_invoker`` that answers the intent (and split) prompt
    apart from every other create round-trip."""

    def __init__(
        self,
        *,
        steps_json: str = _ONE_STEP_JSON,
        intent_json: str = "[]",
        split_json: Optional[str] = None,
    ) -> None:
        self.steps_json = steps_json
        self.intent_json = intent_json
        self.split_json = split_json
        self.prompts: list[str] = []

    @property
    def intent_prompts(self) -> list[str]:
        return [p for p in self.prompts if _is_intent_prompt(p)]

    def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if _is_intent_prompt(prompt):
            return self.intent_json
        if self.split_json is not None and _SPLIT_PROMPT_MARKER in prompt:
            return self.split_json
        if "developer and API reference documentation" in prompt:
            return "[]"
        return self.steps_json


def _recording_input(record: list[str], answers: list[str]) -> Callable[[str], str]:
    """``_queue_input`` that also records every prompt it was shown."""
    queued = _queue_input(answers)

    def fake(prompt: str) -> str:
        record.append(prompt)
        return queued(prompt)

    return fake


class TestCreateOffersMissingIntents:
    """``create``'s last authoring gate: offer a drafted ``intent`` wherever
    the seed's ``## Outcome``, the step proposal, a wizard split, the canonical
    reader, or the interactive loop left one missing.

    Presence is the only test any value gets — nothing here judges a draft.
    """

    def _create(
        self,
        root: Path,
        *,
        invoker: Callable[[str], str],
        input_fn: Callable[[str], str],
        seed: Optional[str] = "Build a thing",
        **kwargs,
    ) -> CreateResult:
        (root / ".git").mkdir(parents=True)
        out_dir = root / "plans"
        out_dir.mkdir()
        return create_plan(
            "demo",
            repo_root=root,
            output_dir_override=out_dir,
            manifest_path=root / "m.json",
            from_description=seed,
            input_fn=input_fn,
            claude_invoker=invoker,
            **kwargs,
        )

    # ---- which targets are missing --------------------------------------

    def test_no_call_when_plan_and_every_step_have_intents(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        fake = _CreateInvokerFake()
        result = self._create(
            tmp_path,
            invoker=fake,
            input_fn=_queue_input(_basic_metadata_answers() + [""]),
            seed="## Outcome\n\nShip the thing\n",
        )
        assert fake.intent_prompts == []
        plan = parse_plan(result.plan_path)
        assert plan.intent == "Ship the thing"
        assert plan.steps[0].intent == "prove one lands"

    def test_seed_outcome_leaves_only_the_step_gaps(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        fake = _CreateInvokerFake(steps_json=_no_intent_json())
        self._create(
            tmp_path,
            invoker=fake,
            input_fn=_queue_input(_basic_metadata_answers() + ["", "d"]),
            seed="## Outcome\n\nShip the thing\n",
        )
        prompt = fake.intent_prompts[0]
        assert '"plan" — the plan itself' not in prompt
        assert "- 1 — one" in prompt

    def test_step_with_a_usable_intent_is_never_a_target(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        steps_json = json.dumps(
            [
                _proposed_step("one", intent="keep me untouched"),
                _proposed_step("two", intent=None, depends_on=[1]),
            ]
        )
        fake = _CreateInvokerFake(steps_json=steps_json)
        result = self._create(
            tmp_path,
            invoker=fake,
            input_fn=_queue_input(_basic_metadata_answers() + ["", "", "d", "d"]),
            seed="Build a thing",
        )
        prompt = fake.intent_prompts[0]
        assert "- 2 — two" in prompt
        assert "- 1 — one" not in prompt
        # The renderer echoes no stored value, so a non-target's intent can
        # neither be shown back nor overwritten.
        assert "keep me untouched" not in prompt
        assert parse_plan(result.plan_path).steps[0].intent == "keep me untouched"

    # ---- mode ladder -----------------------------------------------------

    def test_non_interactive_without_yes_skips_the_proposal(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)
        fake = _CreateInvokerFake(steps_json=_no_intent_json())
        result = self._create(
            tmp_path,
            invoker=fake,
            input_fn=_queue_input(_basic_metadata_answers()),
        )
        assert fake.intent_prompts == []
        plan = parse_plan(result.plan_path)
        assert plan.intent is None
        assert plan.steps[0].intent is None

    def test_yes_accepts_every_draft_without_prompting(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)
        fake = _CreateInvokerFake(
            steps_json=_no_intent_json(),
            intent_json=_intent_json(
                ("plan", "carry the why forward"), (1, "ground the parser")
            ),
        )
        shown: list[str] = []
        result = self._create(
            tmp_path,
            invoker=fake,
            input_fn=_recording_input(shown, [""] * 8),
            yes=True,
        )
        plan = parse_plan(result.plan_path)
        assert plan.intent == "carry the why forward"
        assert plan.steps[0].intent == "ground the parser"
        # The accept/edit/decline walk never ran.
        assert not any(_INTENT_WALK_MARKER in p for p in shown)

    def test_yes_notes_accepted_targets_on_stderr(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)
        fake = _CreateInvokerFake(
            steps_json=_no_intent_json(),
            intent_json=_intent_json(("plan", "carry the why"), (1, "ground it")),
        )
        self._create(
            tmp_path, invoker=fake, input_fn=_silent_input_fn, yes=True
        )
        err = capsys.readouterr().err
        assert "accepted the proposed intent for the plan, step 1" in err

    def test_interactive_accept_keeps_the_drafted_text(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        fake = _CreateInvokerFake(
            intent_json=_intent_json(("plan", "carry the why forward"))
        )
        result = self._create(
            tmp_path,
            invoker=fake,
            input_fn=_queue_input(_basic_metadata_answers() + ["", ""]),
        )
        assert parse_plan(result.plan_path).intent == "carry the why forward"

    def test_interactive_edit_writes_the_replacement(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        fake = _CreateInvokerFake(intent_json=_intent_json(("plan", "the draft")))
        result = self._create(
            tmp_path,
            invoker=fake,
            input_fn=_queue_input(
                _basic_metadata_answers() + ["", "e", "what I actually meant"]
            ),
        )
        assert parse_plan(result.plan_path).intent == "what I actually meant"

    def test_declining_every_draft_leaves_intents_unset(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        fake = _CreateInvokerFake(intent_json=_intent_json(("plan", "the draft")))
        result = self._create(
            tmp_path,
            invoker=fake,
            input_fn=_queue_input(_basic_metadata_answers() + ["", "d"]),
        )
        assert parse_plan(result.plan_path).intent is None
        # Plan-level only: step intents render indented under ``steps:``.
        assert "\nintent:" not in result.plan_path.read_text(encoding="utf-8")

    def test_unusable_response_does_not_fail_the_create(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        fake = _CreateInvokerFake(intent_json="sorry, I can't do that")
        result = self._create(
            tmp_path,
            invoker=fake,
            input_fn=_queue_input(_basic_metadata_answers() + [""]),
        )
        assert result.plan_path.exists()
        assert parse_plan(result.plan_path).intent is None

    # ---- placement and ordering -----------------------------------------

    def test_intents_ride_the_single_initial_plan_write(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Accepted values are folded in *before* the write (``write_new_plan``
        routes through ``write_plan``), so the create path never
        writes-then-rewrites the plan file."""
        from plan_tool import create as create_module

        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        written: list[Optional[str]] = []
        real_write_plan = create_module.write_plan

        def spy(path: Path, plan: Plan, **kwargs):
            written.append(plan.intent)
            return real_write_plan(path, plan, **kwargs)

        monkeypatch.setattr(create_module, "write_plan", spy)
        fake = _CreateInvokerFake(
            intent_json=_intent_json(("plan", "carry the why forward"))
        )
        result = self._create(
            tmp_path,
            invoker=fake,
            input_fn=_queue_input(_basic_metadata_answers() + ["", ""]),
        )
        # Exactly one write, and it already carried the accepted value.
        assert written == ["carry the why forward"]
        assert parse_plan(result.plan_path).intent == "carry the why forward"

    def test_drafts_target_post_split_step_ids(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        steps_json = json.dumps(
            [
                _proposed_step("mixed", intent=None),
                _proposed_step("after", intent="wire it up", depends_on=[1]),
            ]
        )
        fake = _CreateInvokerFake(
            steps_json=steps_json, split_json=_SPLIT_PAIR_JSON
        )
        # "s" splits step 1; the two halves + the downstream step accept.
        self._create(
            tmp_path,
            invoker=fake,
            input_fn=_queue_input(
                _basic_metadata_answers() + ["s", "", "", "", "d", "d", "d"]
            ),
        )
        prompt = fake.intent_prompts[0]
        # The downstream step renumbered 2 → 3 and kept its intent, so the
        # two split halves are the only step targets.
        assert "- 1 — characterize" in prompt
        assert "- 2 — add behavior" in prompt
        assert "- 3 — after" not in prompt

    def test_split_replacement_is_offered_an_intent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``_propose_step_split``'s prompt never asks for ``intent``; running
        after the change-type review is what covers the replacement steps."""
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        fake = _CreateInvokerFake(
            steps_json=json.dumps([_proposed_step("mixed", intent=None)]),
            split_json=_SPLIT_PAIR_JSON,
            intent_json=_intent_json((2, "make the easy change")),
        )
        result = self._create(
            tmp_path,
            invoker=fake,
            input_fn=_queue_input(_basic_metadata_answers() + ["s", "", "", ""]),
        )
        plan = parse_plan(result.plan_path)
        assert plan.steps[1].title == "add behavior"
        assert plan.steps[1].intent == "make the easy change"

    def test_interactive_fallback_steps_are_offered_intents(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        fake = _CreateInvokerFake(
            steps_json="sorry I can't do that",
            intent_json=_intent_json((1, "prove the fallback lands")),
        )
        result = self._create(
            tmp_path,
            invoker=fake,
            input_fn=_queue_input(
                _basic_metadata_answers() + _single_step_answers() + ["", ""]
            ),
        )
        plan = parse_plan(result.plan_path)
        assert plan.steps[0].title == "First step"
        assert plan.steps[0].intent == "prove the fallback lands"

    def test_canonical_extracted_steps_are_offered_intents(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``extract_steps_from_canonical`` copies title / files / edges and no
        intent, so both extracted steps reach the offer."""
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        fake = _CreateInvokerFake(
            intent_json=_intent_json((1, "ground the reader"), (2, "wire it up"))
        )
        result = self._create(
            tmp_path,
            invoker=fake,
            input_fn=_queue_input(_basic_metadata_answers() + ["", "", "", ""]),
            seed=_CANONICAL_BODY,
        )
        assert [s.intent for s in parse_plan(result.plan_path).steps] == [
            "ground the reader",
            "wire it up",
        ]

    # ---- wiring to the proposal module ----------------------------------

    def test_create_passes_its_claude_invoker_through(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No second seam and no real-backend default — the injected fake is
        what drafts. ``tests/conftest.py``'s gate would raise otherwise."""
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        fake = _CreateInvokerFake(intent_json=_intent_json(("plan", "a why")))
        self._create(
            tmp_path,
            invoker=fake,
            input_fn=_queue_input(_basic_metadata_answers() + ["", ""]),
        )
        assert len(fake.intent_prompts) == 1

    def test_seed_text_is_the_prompt_grounding(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        fake = _CreateInvokerFake()
        self._create(
            tmp_path,
            invoker=fake,
            input_fn=_queue_input(_basic_metadata_answers() + ["", "d"]),
            seed="Rebuild the widget indexer so lookups stop scanning.",
        )
        prompt = fake.intent_prompts[0]
        assert "Source material this plan was written from:" in prompt
        assert "Rebuild the widget indexer so lookups stop scanning." in prompt

    def test_interactive_path_passes_empty_grounding(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No seed and no ``--from`` text: the prompt is built from the plan
        alone rather than from a second source ladder."""
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        fake = _CreateInvokerFake(intent_json=_intent_json(("plan", "a why")))
        self._create(
            tmp_path,
            invoker=fake,
            input_fn=_queue_input(
                _basic_metadata_answers() + _single_step_answers() + ["", "", "d"]
            ),
            seed=None,
        )
        prompt = fake.intent_prompts[0]
        assert "Source material this plan was written from:" not in prompt
        assert "Plan: Demo Plan" in prompt

    def test_declining_every_draft_still_checkpoints_the_decision(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A full decline persists, so a resume does not re-ask.

        The offer used to return at its ``if not kept:`` guard *before* the
        checkpoint save, so declining everything wrote nothing: a later
        failure (the fail-loud ``_(TODO)_`` body gate) preserved checkpoints
        for the re-run, and the resumed run re-spent the proposal round-trip
        and re-asked every question already answered.
        """
        from plan_tool.create import (
            _INTENT_REVIEW_CHECKPOINT_NAME,
            _offer_missing_intents,
        )

        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        plan = Plan(
            title="Demo Plan",
            status="planning",
            priority="medium",
            steps=[Step(id=1, title="Do the thing")],
        )
        calls: list[str] = []

        def invoker(prompt: str) -> str:
            calls.append(prompt)
            return _intent_json(("plan", "a drafted why"), (1, "a step why"))

        returned = _offer_missing_intents(
            plan,
            input_fn=_queue_input(["d", "d"]),
            invoker=invoker,
            repo_root=tmp_path,
            slug="demo",
            output_dir=out_dir,
        )

        assert len(calls) == 1
        assert returned.intent is None
        assert returned.step_by_id(1).intent is None
        ckpt = checkpoint_path(tmp_path, "demo", _INTENT_REVIEW_CHECKPOINT_NAME)
        assert ckpt.exists(), "a declined offer must still checkpoint"

        # The decision replays: a resume neither re-proposes nor re-asks.
        again = _offer_missing_intents(
            plan,
            input_fn=_queue_input([]),
            invoker=invoker,
            repo_root=tmp_path,
            slug="demo",
            output_dir=out_dir,
        )
        assert len(calls) == 1, "resume must not re-spend the round-trip"
        assert again.intent is None

    def test_empty_draft_list_is_not_checkpointed_as_a_decline(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The model producing nothing is not an operator decision.

        Checkpointing it froze the plan intent-less forever: the input hash
        does not move, so every later `--resume` short-circuited before the
        backend call and the operator was never asked.
        """
        from plan_tool.create import (
            _INTENT_REVIEW_CHECKPOINT_NAME,
            _offer_missing_intents,
        )

        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        plan = Plan(
            title="Demo Plan",
            status="planning",
            priority="medium",
            steps=[Step(id=1, title="Do the thing")],
        )
        _offer_missing_intents(
            plan,
            input_fn=_queue_input([]),
            invoker=lambda _p: "[]",
            repo_root=tmp_path,
            slug="demo",
            output_dir=out_dir,
        )
        ckpt = checkpoint_path(tmp_path, "demo", _INTENT_REVIEW_CHECKPOINT_NAME)
        assert not ckpt.exists(), "nothing was decided, so nothing to freeze"

    # ---- observability ---------------------------------------------------

    @pytest.mark.parametrize(
        "tty,seed,intent_json,extra_answers,expected_reason",
        [
            (
                True,
                "## Outcome\n\nShip the thing\n",
                "[]",
                [""],
                "nothing_missing",
            ),
            (False, "Build a thing", "[]", [], "non_interactive"),
            (True, "Build a thing", "not json at all", [""], "unusable_response"),
            (
                True,
                "Build a thing",
                json.dumps([{"target": "plan", "intent": "a why"}]),
                ["", "d"],
                "all_declined",
            ),
        ],
    )
    def test_run_log_names_the_skip_reason(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        tty: bool,
        seed: str,
        intent_json: str,
        extra_answers: list[str],
        expected_reason: str,
    ) -> None:
        from plan_tool.run_log import RunLogWriter

        monkeypatch.setattr("sys.stdin.isatty", lambda: tty)
        run_logger = RunLogWriter.start(
            repo_root=tmp_path,
            slug="demo",
            command="create",
            argv=["plan-tool", "create", "demo"],
        )
        self._create(
            tmp_path,
            invoker=_CreateInvokerFake(intent_json=intent_json),
            input_fn=_queue_input(_basic_metadata_answers() + extra_answers),
            seed=seed,
            run_logger=run_logger,
        )
        ends = [
            e
            for e in _read_run_log(tmp_path, "demo")
            if e["event"] == "phase_end" and e["phase"] == "propose_intents"
        ]
        assert len(ends) == 1
        assert ends[0]["outcome"] == "skipped"
        assert ends[0]["skip_reason"] == expected_reason

    def test_run_log_omits_skip_reason_on_the_applied_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.run_log import RunLogWriter

        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        run_logger = RunLogWriter.start(
            repo_root=tmp_path,
            slug="demo",
            command="create",
            argv=["plan-tool", "create", "demo"],
        )
        self._create(
            tmp_path,
            invoker=_CreateInvokerFake(
                intent_json=_intent_json(("plan", "carry the why"))
            ),
            input_fn=_queue_input(_basic_metadata_answers() + ["", ""]),
            run_logger=run_logger,
        )
        end = next(
            e
            for e in _read_run_log(tmp_path, "demo")
            if e["event"] == "phase_end" and e["phase"] == "propose_intents"
        )
        assert end["outcome"] == "ok"
        assert "skip_reason" not in end

    def test_resume_restores_the_reviewed_intents(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The reviewed values are checkpointed, so a re-run after a later
        failure re-spends neither the round-trip nor the operator's answers."""
        from plan_tool.create import _offer_missing_intents

        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        repo, out_dir, _ = _seed_review_repo(tmp_path)
        plan = Plan(
            title="Demo",
            status=PlanStatus.PLANNING,
            priority=Priority.MEDIUM,
            steps=[Step(id=1, title="one")],
        )
        reviewed = _offer_missing_intents(
            plan,
            input_fn=_queue_input(["", ""]),
            invoker=lambda _p: _intent_json(("plan", "a why"), (1, "a step why")),
            repo_root=repo,
            slug="demo",
            output_dir=out_dir,
        )
        assert reviewed.intent == "a why"

        def explode(_prompt: str) -> str:
            raise AssertionError("resume must not re-propose")

        restored = _offer_missing_intents(
            plan,
            input_fn=_queue_input([]),  # raises if the walk re-prompts
            invoker=explode,
            repo_root=repo,
            slug="demo",
            output_dir=out_dir,
        )
        assert restored.intent == "a why"
        assert restored.steps[0].intent == "a step why"

    # ---- the boundary this step closes -----------------------------------

    def test_created_plan_emits_no_intent_presence_finding(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.review import check_intent_presence

        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        fake = _CreateInvokerFake(
            steps_json=_no_intent_json(),
            intent_json=_intent_json(("plan", "carry the why"), (1, "ground it")),
        )
        result = self._create(
            tmp_path,
            invoker=fake,
            input_fn=_queue_input(_basic_metadata_answers() + ["", "", ""]),
        )
        assert check_intent_presence(parse_plan(result.plan_path)) == []


class TestReproposalPreservesAcceptedIntent:
    """The post-write ``--iterate`` re-proposal is a step producer like any
    other, and is not authoritative over an intent the operator accepted."""

    def test_missing_reproposed_intent_keeps_the_prior_value(self) -> None:
        prior = Step(id=1, title="one", intent="the accepted why")
        merged = _preserve_on_disk_step_fields(Step(id=1, title="one"), prior)
        assert merged.intent == "the accepted why"

    def test_placeholder_reproposed_intent_keeps_the_prior_value(self) -> None:
        prior = Step(id=1, title="one", intent="the accepted why")
        merged = _preserve_on_disk_step_fields(
            Step(id=1, title="one", intent="TBD"), prior
        )
        assert merged.intent == "the accepted why"

    def test_reviewed_intent_survives_a_reproposal_that_carries_one(
        self,
    ) -> None:
        """The operator's reviewed value wins over a later automated pass.

        Was the reverse until the xhigh review: step 5's own acceptance
        criterion is that an accepted intent survives the post-write
        re-proposal, and letting the model overwrite it silently discarded
        prose a human had edited and confirmed.
        """
        prior = Step(id=1, title="one", intent="the accepted why")
        merged = _preserve_on_disk_step_fields(
            Step(id=1, title="one", intent="a model rewrite"), prior
        )
        assert merged.intent == "the accepted why"

    def test_intent_does_not_travel_to_a_different_step_at_the_same_id(
        self,
    ) -> None:
        """Ids are positional, so a re-proposal that reorders puts a different
        step under the same id — carrying the intent across would make a false
        statement about it, which the fence then threads into that step's
        detail and run prompts."""
        prior = Step(id=3, title="Add the --no-backfill flag", intent="opt out")
        merged = _preserve_on_disk_step_fields(
            Step(id=3, title="Write the parser round-trip tests"), prior
        )
        assert merged.intent is None

    def test_new_step_keeps_its_own_intent_and_starts_pending(self) -> None:
        merged = _preserve_on_disk_step_fields(
            Step(id=2, title="new", intent="fresh why", status=StepStatus.DONE),
            None,
        )
        assert merged.intent == "fresh why"
        assert merged.status == StepStatus.PENDING

    def test_prior_status_still_outlives_the_reproposal(self) -> None:
        prior = Step(id=1, title="one", status=StepStatus.DONE)
        merged = _preserve_on_disk_step_fields(
            Step(id=1, title="one", status=StepStatus.PENDING), prior
        )
        assert merged.status == StepStatus.DONE

    @pytest.mark.integration
    def test_accepted_intent_survives_a_full_iterate_run(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """End to end: the operator accepts a draft pre-write, the post-write
        loop re-proposes the same step carrying no intent, and the accepted
        text is still on the step when the run finishes."""
        from plan_tool import create as create_module

        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        collect_calls = {"n": 0}

        def fake_collect(*_args, **_kwargs):
            collect_calls["n"] += 1
            return [_rec("A")] if collect_calls["n"] == 1 else []

        monkeypatch.setattr(
            create_module, "collect_deterministic_findings", fake_collect
        )
        monkeypatch.setattr(
            create_module, "apply_finding", lambda *a, **kw: _stub_apply_result()
        )

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=tmp_path / "m.json",
            from_description="build a thing",
            input_fn=_queue_input(_basic_metadata_answers() + ["", ""]),
            # Every step round-trip answers with an intent-less proposal, so
            # the re-proposal is exactly the "returns intent: None" case.
            claude_invoker=_CreateInvokerFake(
                steps_json=_no_intent_json(),
                intent_json=_intent_json((1, "the accepted why")),
            ),
            budget=_IterativeBudget(enabled=True, max_iterations=3),
        )
        assert parse_plan(result.plan_path).steps[0].intent == "the accepted why"


# ---------- shell integration (regression) ----------


@pytest.mark.integration
class TestShellClaudeInvokerRegression:
    """Pin the ``(rc, stdout)`` contract of ``create.shell_claude_invoker``.

    Step 2 of the "Run Log Structured Events" plan adds a sink-emit
    side-channel to ``plan_tool.shell.claude_invoke``. These tests
    guarantee that the production invoker used by ``create_plan`` still
    surfaces a plain ``str`` to its callers (i.e. discards ``rc``) and
    that flipping the sink on does not perturb ``create_plan``'s
    inputs or outputs.
    """

    @pytest.fixture(autouse=True)
    def _stub_propose_references(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Stub the references-proposal claude call site for tests in
        this class that drive ``create_plan`` without an explicit
        ``claude_invoker=`` (e.g. ``test_create_plan_clears_sink_on_exit``).
        Tests that directly exercise ``shell_claude_invoker`` install
        their own ``subprocess.run`` mock which is unaffected by this."""
        from plan_tool import create as create_module
        monkeypatch.setattr(
            create_module, "propose_references_from_claude",
            lambda *a, **kw: ReferenceResearchResult.from_references([]),
        )

    def test_shell_claude_invoker_still_returns_str_only(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool import backend_runner, shell
        from plan_tool.create import shell_claude_invoker
        from plan_tool.run_log import ClaudeCallEnd
        from subprocess_doubles import _FakeProc

        monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
        monkeypatch.setattr(
            backend_runner.subprocess,
            "Popen",
            lambda argv, **kwargs: _FakeProc(["some text"], [], 0),
        )

        recorded: list[ClaudeCallEnd] = []
        shell.set_active_sink(recorded.append)
        try:
            out = shell_claude_invoker("hello")
        finally:
            shell.set_active_sink(None)

        assert isinstance(out, str)
        assert out == "some text"
        # Sink fired exactly once even though the wrapper discards rc.
        assert len(recorded) == 1
        assert recorded[0].rc == 0

    def test_create_plan_unaffected_by_sink_being_installed(
        self, tmp_path: Path
    ) -> None:
        """A fake ``claude_invoker`` injected by tests bypasses
        ``shell.claude_invoke`` entirely, so the sink must not see
        any events even when installed."""
        from plan_tool import shell
        from plan_tool.run_log import ClaudeCallEnd

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        canned = json.dumps(
            [
                {
                    "title": "only",
                    "complexity": "low",
                    "files": [],
                    "depends_on": [],
                }
            ]
        )
        answers = _basic_metadata_answers()

        recorded: list[ClaudeCallEnd] = []
        shell.set_active_sink(recorded.append)
        try:
            result = create_plan(
                "demo",
                repo_root=tmp_path,
                output_dir_override=out_dir,
                manifest_path=manifest,
                from_description="Build a thing",
                input_fn=_queue_input(answers),
                claude_invoker=lambda prompt: canned,
            )
        finally:
            shell.set_active_sink(None)

        plan = parse_plan(result.plan_path)
        assert [s.title for s in plan.steps] == ["only"]
        # Injected fake invoker does not route through shell.claude_invoke
        # → no event should reach the sink.
        assert recorded == []

    def test_create_plan_clears_sink_on_exit(self, tmp_path: Path) -> None:
        """Defensive regression: step 3's wrapper must clear the sink in
        a ``finally:`` block so test runs don't leak state. We simulate
        that contract here by wrapping ``create_plan`` ourselves and
        asserting the sink is ``None`` after the call returns."""
        from plan_tool import shell
        from plan_tool.run_log import ClaudeCallEnd

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"
        answers = _basic_metadata_answers() + _single_step_answers()

        recorded: list[ClaudeCallEnd] = []
        shell.set_active_sink(recorded.append)
        try:
            create_plan(
                "demo",
                repo_root=tmp_path,
                output_dir_override=out_dir,
                manifest_path=manifest,
                input_fn=_queue_input(answers),
            )
        finally:
            shell.set_active_sink(None)

        assert shell.get_active_sink() is None


class TestReadExistingDescription:
    def test_reads_file_contents(self, tmp_path: Path) -> None:
        path = tmp_path / "notes.md"
        path.write_text("# Plan\n\nDo a thing.\n", encoding="utf-8")
        body = read_existing_description(path)
        assert body == "# Plan\n\nDo a thing.\n"

    def test_no_size_cap(self, tmp_path: Path) -> None:
        # The old _MAX_EXISTING_BYTES hard cap is gone — read_existing_description
        # just reads the file, no matter how large. Oversize handling moved to
        # the distill first-pass (single-plan reorganize or multi-plan split).
        path = tmp_path / "big.md"
        path.write_text("x" * 200_000, encoding="utf-8")
        assert read_existing_description(path) == "x" * 200_000

    def test_missing_path_raises(self, tmp_path: Path) -> None:
        with pytest.raises(CreateError, match="not a file"):
            read_existing_description(tmp_path / "nope.md")

    def test_directory_raises(self, tmp_path: Path) -> None:
        (tmp_path / "adir").mkdir()
        with pytest.raises(CreateError, match="not a file"):
            read_existing_description(tmp_path / "adir")


@pytest.mark.integration
class TestCreatePlanFromExistingViaCli:
    """End-to-end: `--from-existing <path>` reads the file and feeds it as the
    description to claude, which proposes steps the wizard accepts.
    """

    def _setup_repo(
        self, tmp_path: Path
    ) -> tuple[Path, Path, Path, Path]:
        repo = tmp_path
        (repo / ".git").mkdir()
        out_dir = repo / "plans"
        out_dir.mkdir()
        manifest = repo / "m.json"
        source = repo / "notes.md"
        source.write_text(
            "# Old Plan\n\nWe should refactor the auth module.\n\n"
            "## References\n\n"
            "- [Auth API](https://example.test/auth)\n",
            encoding="utf-8",
        )
        return repo, out_dir, manifest, source

    def test_happy_path_via_main(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool.cli import context as cli_context
        from plan_tool import create as create_module
        from plan_tool.launcher import ApplyFindingResult

        repo, out_dir, manifest, source = self._setup_repo(tmp_path)

        # Capture the description claude saw so we can assert it includes the
        # source file's contents.
        captured: dict[str, str] = {}

        def fake_invoker(prompt: str) -> str:
            captured["prompt"] = prompt
            if "Distill a free-form seed" in prompt:
                return _valid_preparation_response(prompt)
            return json.dumps(
                [{"title": "refactor auth", "complexity": "medium",
                  "files": [], "depends_on": []}]
            )

        # Patch the create wizard's claude invoker default + input_fn
        # at the call site by replacing create_plan with a thin wrapper.
        original_create_plan = cli_module.create_plan
        answers = _basic_metadata_answers()

        def patched_create_plan(*args, **kwargs):
            kwargs.setdefault("input_fn", _queue_input(answers))
            kwargs["claude_invoker"] = fake_invoker
            return original_create_plan(*args, **kwargs)

        monkeypatch.setattr("plan_tool.cli.authoring.create_plan", patched_create_plan)
        # Stub apply_finding so the post-write convergence loop doesn't
        # shell out to real claude (apply_finding defaults to shell_invoker).
        monkeypatch.setattr(
            create_module,
            "apply_finding",
            lambda *a, **kw: ApplyFindingResult(
                step_id=None, exit_code=0, verdict="APPLIED",
                summary="", diff_text="", pre_snapshot={}, stdout="",
            ),
        )
        monkeypatch.chdir(repo)

        rc = cli_module.main(
            [
                "--manifest",
                str(manifest),
                "create",
                "demo",
                "--from-existing",
                str(source),
                "--output-dir",
                str(out_dir),
            ]
        )
        assert rc == 0

        # Source moved to archive with notice prepended; original gone.
        assert not source.exists()
        archived = repo / "archive" / "notes.replaced.md"
        assert archived.is_file()
        archived_text = archived.read_text(encoding="utf-8")
        assert "Replaced" in archived_text
        assert "# Old Plan" in archived_text  # original content preserved

        # New plan exists, was registered.
        new_plan_path = out_dir / "2-demo.md"
        assert new_plan_path.is_file()
        plan = parse_plan(new_plan_path)
        assert [s.title for s in plan.steps] == ["refactor auth"]
        assert plan.steps[0].complexity == Complexity.MEDIUM

        # Manifest gained exactly one entry.
        data = json.loads(manifest.read_text(encoding="utf-8"))
        assert data["plans"] == ["plans/2-demo.md"]

        # Source contents were forwarded to claude as the description.
        assert "auth module" in captured["prompt"]

    def test_missing_path_returns_nonzero(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool.cli import context as cli_context

        (tmp_path / ".git").mkdir()
        manifest = tmp_path / "m.json"
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(
            [
                "--manifest",
                str(manifest),
                "create",
                "demo",
                "--from-existing",
                str(tmp_path / "missing.md"),
            ]
        )
        assert rc == 2
        # No plan, no manifest.
        assert not manifest.exists()

    def test_missing_references_rejects_before_slug_inference(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool.cli import authoring as authoring_module

        (tmp_path / ".git").mkdir()
        source = tmp_path / "notes.md"
        source.write_text("# Draft\n\nNo references yet.\n", encoding="utf-8")
        invoked = False

        def unexpected_slug_call(*_args, **_kwargs):
            nonlocal invoked
            invoked = True
            raise AssertionError("seed preflight must run before slug inference")

        monkeypatch.setattr(authoring_module, "resolve_create_slug", unexpected_slug_call)
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(
            ["create", "--from-existing", str(source), "--output-dir", "plans"]
        )

        assert rc == 2
        assert not invoked
        assert not (tmp_path / "plans").exists()

    def test_from_and_from_existing_are_mutually_exclusive(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool.cli import context as cli_context

        (tmp_path / ".git").mkdir()
        source = tmp_path / "notes.md"
        source.write_text("x", encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        with pytest.raises(SystemExit):
            cli_module.main(
                [
                    "create",
                    "demo",
                    "--from",
                    "an inline description",
                    "--from-existing",
                    str(source),
                ]
            )


class TestArchiveExistingSource:
    def test_moves_source_with_notice_prepended(self, tmp_path: Path) -> None:
        plans_dir = tmp_path / "docs" / "implementation-plans"
        plans_dir.mkdir(parents=True)
        source = plans_dir / "1-foo.md"
        source.write_text("# Foo\n\nOriginal body.\n", encoding="utf-8")
        new_plan = tmp_path / ".agents" / "implementation-plans" / "2-foo.md"

        result = archive_existing_source(source, new_plan, repo_root=tmp_path)

        archived = plans_dir / "archive" / "1-foo.replaced.md"
        assert archived.is_file()
        text = archived.read_text(encoding="utf-8")
        assert "Replaced" in text
        # Notice references the new plan's repo-relative path.
        assert ".agents/implementation-plans/2-foo.md" in text
        assert "Original body." in text  # body preserved verbatim
        assert not source.exists()
        assert (source, archived) in result.archived
        assert result.skipped == []

    def test_archives_plan_details_when_present(self, tmp_path: Path) -> None:
        plans_dir = tmp_path / "docs" / "implementation-plans"
        plans_dir.mkdir(parents=True)
        source = plans_dir / "1-foo.md"
        source.write_text("# Foo\n", encoding="utf-8")
        details = plans_dir / "plan-details" / "foo"
        details.mkdir(parents=True)
        (details / "01-step.md").write_text(
            "# Step 1 detail\n\nDo a thing.\n", encoding="utf-8"
        )
        (details / "02-step.md").write_text(
            "# Step 2 detail\n", encoding="utf-8"
        )
        # Non-md sibling should be moved verbatim (no notice).
        (details / "diagram.txt").write_text("ascii art", encoding="utf-8")
        new_plan = tmp_path / "new.md"

        result = archive_existing_source(source, new_plan, repo_root=tmp_path)

        archived_details = plans_dir / "archive" / "plan-details" / "foo"
        assert archived_details.is_dir()
        archived_step = archived_details / "01-step.md"
        assert archived_step.is_file()
        assert "Replaced" in archived_step.read_text(encoding="utf-8")
        assert "Do a thing." in archived_step.read_text(encoding="utf-8")
        assert (archived_details / "02-step.md").is_file()
        # Non-md file copied without notice.
        assert (
            archived_details / "diagram.txt"
        ).read_text(encoding="utf-8") == "ascii art"
        # Originals removed.
        assert not details.exists()
        assert result.skipped == []

    def test_archived_detail_snapshot_has_no_run_grade_carrier(
        self, tmp_path: Path
    ) -> None:
        """The replacement breadcrumb prepended ahead of the H1 puts the
        archived snapshot outside the live run-grade format-version
        carrier — a deliberate exemption, not a change to
        ``_copy_details_bundle_for_archive`` itself."""
        from plan_tool.detail_artifacts import locate_detail_format_carrier

        plans_dir = tmp_path / "docs" / "implementation-plans"
        plans_dir.mkdir(parents=True)
        source = plans_dir / "1-foo.md"
        source.write_text("# Foo\n", encoding="utf-8")
        details = plans_dir / "plan-details" / "foo"
        details.mkdir(parents=True)
        run_grade_body = (
            "# Step 1 — Detail\n\n"
            "<!-- plan-tool:detail-format-version: 1 -->\n\n"
            "## Summary\n\nDo a thing.\n"
        )
        (details / "01-step.md").write_text(run_grade_body, encoding="utf-8")
        assert locate_detail_format_carrier(run_grade_body) is not None
        new_plan = tmp_path / "new.md"

        archive_existing_source(source, new_plan, repo_root=tmp_path)

        archived_text = (
            plans_dir / "archive" / "plan-details" / "foo" / "01-step.md"
        ).read_text(encoding="utf-8")
        assert locate_detail_format_carrier(archived_text) is None

    def test_no_plan_details_when_filename_lacks_priority_prefix(
        self, tmp_path: Path
    ) -> None:
        source = tmp_path / "notes.md"
        source.write_text("body", encoding="utf-8")
        # A plan-details/foo dir exists but the filename has no `<n>-<slug>` pattern,
        # so the function won't try to find a slug — and the directory stays put.
        details = tmp_path / "plan-details" / "foo"
        details.mkdir(parents=True)
        (details / "01.md").write_text("x", encoding="utf-8")
        new_plan = tmp_path / "new.md"

        archive_existing_source(source, new_plan, repo_root=tmp_path)

        # Source archived, details untouched (no slug to match).
        assert (tmp_path / "archive" / "notes.replaced.md").is_file()
        assert details.is_dir()
        assert (details / "01.md").is_file()

    def test_collision_in_archive_uses_numbered_replacement(
        self, tmp_path: Path
    ) -> None:
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        source = plans_dir / "1-foo.md"
        source.write_text("body", encoding="utf-8")
        # Pre-existing collision in archive dir.
        archive_dir = plans_dir / "archive"
        archive_dir.mkdir()
        collided = archive_dir / "1-foo.replaced.md"
        collided.write_text("preexisting", encoding="utf-8")

        new_plan = tmp_path / "new.md"
        result = archive_existing_source(source, new_plan, repo_root=tmp_path)

        archived = archive_dir / "1-foo.replaced.1.md"
        assert not source.exists()
        assert collided.read_text(encoding="utf-8") == "preexisting"
        assert archived.is_file()
        assert "body" in archived.read_text(encoding="utf-8")
        assert result.skipped == []
        assert (source, archived) in result.archived

    def test_plan_details_collision_uses_matching_numbered_bundle(
        self, tmp_path: Path
    ) -> None:
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        source = plans_dir / "1-foo.md"
        source.write_text("# Foo\n", encoding="utf-8")
        details = plans_dir / "plan-details" / "foo"
        details.mkdir(parents=True)
        (details / "01-step.md").write_text("# Detail\n", encoding="utf-8")
        archive_details = plans_dir / "archive" / "plan-details" / "foo"
        archive_details.mkdir(parents=True)
        (archive_details / "old.md").write_text("old", encoding="utf-8")

        new_plan = tmp_path / "new.md"
        result = archive_existing_source(source, new_plan, repo_root=tmp_path)

        archived_source = plans_dir / "archive" / "1-foo.replaced.1.md"
        archived_details = (
            plans_dir / "archive" / "plan-details" / "foo.replaced.1"
        )
        assert archived_source.is_file()
        assert archived_details.is_dir()
        assert (archived_details / "01-step.md").is_file()
        assert (archive_details / "old.md").is_file()
        assert not source.exists()
        assert not details.exists()
        assert result.skipped == []

    def test_plan_details_stage_failure_leaves_source_and_details_in_place(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import plan_tool.create as create_module

        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        source = plans_dir / "1-foo.md"
        source.write_text("# Foo\n", encoding="utf-8")
        details = plans_dir / "plan-details" / "foo"
        details.mkdir(parents=True)
        (details / "01-step.md").write_text("# Detail\n", encoding="utf-8")

        def fail_copy(*args, **kwargs):
            raise OSError("disk full")

        monkeypatch.setattr(
            create_module, "_copy_details_bundle_for_archive", fail_copy
        )

        result = archive_existing_source(
            source, tmp_path / "new.md", repo_root=tmp_path
        )

        assert any("could not archive plan-details" in s for s in result.skipped)
        assert result.archived == []
        assert source.is_file()
        assert details.is_dir()
        assert not (plans_dir / "archive" / "1-foo.replaced.md").exists()
        assert not (plans_dir / "archive" / "plan-details" / "foo").exists()

    def test_missing_source_reports_skip(self, tmp_path: Path) -> None:
        new_plan = tmp_path / "new.md"
        result = archive_existing_source(
            tmp_path / "missing.md", new_plan, repo_root=tmp_path
        )
        assert any("no longer exists" in s for s in result.skipped)
        assert result.archived == []

    def test_display_path_falls_back_to_absolute_when_outside_repo(
        self, tmp_path: Path
    ) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        source = repo / "1-foo.md"
        source.write_text("body", encoding="utf-8")
        # New plan is somehow outside the repo — display falls back to absolute.
        new_plan = outside / "x.md"
        new_plan.write_text("y", encoding="utf-8")

        archive_existing_source(source, new_plan, repo_root=repo)

        archived = repo / "archive" / "1-foo.replaced.md"
        assert str(new_plan) in archived.read_text(encoding="utf-8")


# --- progress reporting ----------------------------------------------------


class _RecordingHandle(StepHandle):
    def __init__(self) -> None:
        self.completed: tuple[float, int] | None = None
        self.failed: tuple[float, str] | None = None
        self.notices: list[tuple[str, str]] = []

    def complete(self, elapsed_s: float, response_bytes: int) -> None:
        self.completed = (elapsed_s, response_bytes)

    def fail(self, elapsed_s: float, reason: str) -> None:
        self.failed = (elapsed_s, reason)

    def notice(self, message: str, *, kind: str = "retry") -> None:
        self.notices.append((message, kind))


class _RecordingReporter(ProgressReporter):
    def __init__(self) -> None:
        self.starts: list[tuple[int, int, str]] = []
        self.handles: list[_RecordingHandle] = []
        # Step 3 added optional ``phase`` / ``attempt`` / ``prompt_bytes``
        # kwargs to ``start_step``; record them separately so historical
        # ``self.starts`` assertions stay untouched while new tests can
        # introspect them.
        self.start_kwargs: list[dict] = []

    def start_step(
        self,
        idx: int,
        total: int,
        label: str,
        *,
        phase: object = None,
        attempt: int = 1,
        prompt_bytes: int = 0,
        prompt_sha256: object = None,
    ) -> StepHandle:
        self.starts.append((idx, total, label))
        self.start_kwargs.append(
            {"phase": phase, "attempt": attempt, "prompt_bytes": prompt_bytes}
        )
        h = _RecordingHandle()
        self.handles.append(h)
        return h


class TestProposalBusinessDelivery:
    def test_missing_prerequisites_do_not_erase_assigned_implementation(self) -> None:
        prompts: list[str] = []
        steps = propose_steps_from_claude(
            "Implement readiness using the pending evidence producer; do not build that producer.",
            lambda prompt: prompts.append(prompt) or _ONE_STEP_JSON,
        )
        assert steps is not None
        prompt = prompts[0]
        assert "Preserve assigned production, update, and consumer-integration work" in prompt
        assert "checking supplied data does not implement the operation that supplies it" in prompt
        assert "retain this plan's implementation steps conditional on that prerequisite" in prompt
        assert "Do not replace an implementation outcome with only prerequisite verification" in prompt
        assert "invent the missing prerequisite's interface, or implement its scope here" in prompt


class TestProposeStepsFromClaudeProgress:
    def test_complete_on_success(self) -> None:
        reporter = _RecordingReporter()
        canned = _ONE_STEP_JSON
        steps = propose_steps_from_claude(
            "build a thing",
            lambda prompt: canned,
            reporter=reporter,
        )
        assert steps is not None
        assert reporter.starts == [(1, 1, "Proposing initial steps")]
        h = reporter.handles[0]
        assert h.completed is not None
        assert h.failed is None

    def test_fail_on_unparseable(self) -> None:
        reporter = _RecordingReporter()
        steps = propose_steps_from_claude(
            "build a thing",
            lambda prompt: "sorry",
            reporter=reporter,
        )
        assert steps is None
        h = reporter.handles[0]
        assert h.completed is None
        assert h.failed is not None
        _, reason = h.failed
        assert "unparseable" in reason

    def test_fail_on_invalid_graph(self) -> None:
        reporter = _RecordingReporter()
        bad = json.dumps(
            [{"title": "only", "complexity": None, "files": [], "depends_on": [99]}]
        )
        steps = propose_steps_from_claude(
            "build a thing",
            lambda prompt: bad,
            reporter=reporter,
        )
        assert steps is None
        h = reporter.handles[0]
        assert h.completed is None
        assert h.failed is not None
        _, reason = h.failed
        assert "invalid graph" in reason

    def test_invalid_graph_recovers_on_repair_retry(self) -> None:
        """A bad graph on the first attempt + a valid graph on the repair
        retry yields a successful proposal (no failure)."""
        bad = json.dumps(
            [{"title": "only", "complexity": None, "files": [], "depends_on": [99]}]
        )
        good = json.dumps(
            [{"title": "first", "complexity": "low", "files": [], "depends_on": []}]
        )
        prompts: list[str] = []

        def invoker(prompt: str) -> str:
            prompts.append(prompt)
            # First call (the rejected one) must be told it failed in the
            # repair prompt; the retry returns a valid graph.
            return bad if len(prompts) == 1 else good

        reporter = _RecordingReporter()
        steps = propose_steps_from_claude(
            "build a thing", invoker, reporter=reporter,
        )
        assert len(prompts) == 2  # original + one repair retry
        assert "quoted numerals are tolerated" in prompts[1]
        assert steps is not None
        assert [s.title for s in steps] == ["first"]
        assert reporter.handles[0].failed is None

    def test_invalid_graph_fails_after_retry_also_bad(self) -> None:
        """Both attempts bad → still a failure (None), invoker called twice."""
        bad = json.dumps(
            [{"title": "only", "complexity": None, "files": [], "depends_on": [99]}]
        )
        calls = {"n": 0}

        def invoker(prompt: str) -> str:
            calls["n"] += 1
            return bad

        reporter = _RecordingReporter()
        steps = propose_steps_from_claude(
            "build a thing", invoker, reporter=reporter,
        )
        assert calls["n"] == 2
        assert steps is None
        assert reporter.handles[0].failed is not None

    def test_invalid_graph_reason_carries_schema_detail(self) -> None:
        """The generic 'invalid graph' line now names the actual cause so a
        future debugging pass doesn't have to guess which step/dep broke.
        """
        reporter = _RecordingReporter()
        bad = json.dumps(
            [{"title": "only", "complexity": None, "files": [], "depends_on": [99]}]
        )
        propose_steps_from_claude(
            "build a thing", lambda prompt: bad, reporter=reporter
        )
        _, reason = reporter.handles[0].failed
        # schema message: "step 1 depends_on references unknown id(s): [99]"
        assert "unknown id(s): [99]" in reason

    def test_foundational_sweep_merges_consolidation_step(
        self, tmp_path: Path
    ) -> None:
        """When a ``foundational_invoker`` is supplied, the sweep runs after the
        proposal parses and merges a consolidation step into the result."""
        (tmp_path / ".git").mkdir()
        proposal = _ONE_STEP_JSON
        sweep = json.dumps(
            {
                "logic": "root walk",
                "shared_locations": [],
                "consolidation": {
                    "title": "Consolidate root walk",
                    "files": [],
                    "creates": [],
                    "after_step_id": 1,
                    "rationale": "dedup the two root-walk implementations",
                },
            }
        )
        steps = propose_steps_from_claude(
            "build a thing",
            lambda _p: proposal,
            reporter=_RecordingReporter(),
            repo_root=tmp_path,
            foundational_invoker=lambda _p: sweep,
        )
        assert steps is not None
        assert [s.title for s in steps] == ["one", "Consolidate root walk"]
        assert steps[1].depends_on == [1]
        # Best-effort toward item 7's per-step intent, not a guarantee: when
        # the sweep supplies a rationale (as here), the auto-generated
        # consolidation step reuses it rather than shipping with none — but
        # a rationale-less response still yields intent=None (see
        # TestDependsOnNotesNegativeSpace.
        # test_merge_sweep_into_steps_produces_no_depends_on_notes).
        assert steps[1].intent == "dedup the two root-walk implementations"

    def test_foundational_sweep_warns_when_consolidation_intent_unusable(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """When neither field clears is_usable_intent, the consolidation
        step ships with intent=None on only the TTY-gated
        _offer_missing_intents backstop — surface it via tool() rather than
        let a non-interactive/no-``--yes`` run ship it silently."""
        (tmp_path / ".git").mkdir()
        proposal = _ONE_STEP_JSON
        sweep = json.dumps(
            {
                "logic": "root walk",
                "shared_locations": [],
                "consolidation": {
                    "title": "Consolidate root walk",
                    "files": [],
                    "creates": [],
                    "after_step_id": 1,
                    "rationale": "TODO",
                    "intent": "TBD",
                },
            }
        )
        steps = propose_steps_from_claude(
            "build a thing",
            lambda _p: proposal,
            reporter=_RecordingReporter(),
            repo_root=tmp_path,
            foundational_invoker=lambda _p: sweep,
        )
        assert steps is not None
        assert steps[1].intent is None
        assert "no usable intent" in capsys.readouterr().err

    def test_foundational_sweep_does_not_warn_for_suppressed_consolidation(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        (tmp_path / ".git").mkdir()
        sweep = json.dumps(
            {
                "logic": "root walk",
                "shared_locations": [
                    {
                        "path": "plan_tool/root.py",
                        "recommendation": "defer",
                        "step_id": 1,
                    }
                ],
                "consolidation": {
                    "title": "Consolidate root walk",
                    "files": ["plan_tool/root.py"],
                    "creates": [],
                    "after_step_id": 1,
                    "rationale": "TODO",
                    "intent": "TBD",
                },
            }
        )

        steps = propose_steps_from_claude(
            "build a thing",
            lambda _p: _ONE_STEP_JSON,
            reporter=_RecordingReporter(),
            repo_root=tmp_path,
            foundational_invoker=lambda _p: sweep,
        )

        assert steps is not None
        assert [step.title for step in steps] == ["one"]
        assert "consolidation step" not in capsys.readouterr().err

    def test_foundational_sweep_skipped_without_invoker(
        self, tmp_path: Path
    ) -> None:
        """Omitting ``foundational_invoker`` keeps the single-call behavior —
        the proposal is returned unchanged with no sweep."""
        (tmp_path / ".git").mkdir()
        proposal = _ONE_STEP_JSON
        steps = propose_steps_from_claude(
            "build a thing",
            lambda _p: proposal,
            reporter=_RecordingReporter(),
            repo_root=tmp_path,
        )
        assert steps is not None
        assert [s.title for s in steps] == ["one"]

    def test_invalid_graph_dumps_raw_response(self, tmp_path: Path) -> None:
        """With slug + repo_root, the rejected response is persisted under
        .plan-tool/parse-failures/<slug>/ so it can be inspected later."""
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        reporter = _RecordingReporter()
        bad = json.dumps(
            [{"title": "only", "complexity": None, "files": [], "depends_on": [99]}]
        )
        propose_steps_from_claude(
            "build a thing",
            lambda prompt: bad,
            reporter=reporter,
            repo_root=tmp_path,
            slug="demo",
            output_dir=out_dir,
        )
        dumps = list(
            (tmp_path / ".plan-tool" / "parse-failures" / "demo").glob(
                "propose-steps-invalid-graph-*.txt"
            )
        )
        assert len(dumps) == 1
        assert dumps[0].read_text() == bad
        # The failure line points the user at the dump.
        _, reason = reporter.handles[0].failed
        assert "parse-failures" in reason

    def test_unparseable_dumps_raw_response(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        reporter = _RecordingReporter()
        propose_steps_from_claude(
            "build a thing",
            lambda prompt: "no json here",
            reporter=reporter,
            repo_root=tmp_path,
            slug="demo",
            output_dir=out_dir,
        )
        dumps = list(
            (tmp_path / ".plan-tool" / "parse-failures" / "demo").glob(
                "propose-steps-unparseable-*.txt"
            )
        )
        assert len(dumps) == 1
        assert dumps[0].read_text() == "no json here"

    def test_no_dump_without_slug_context(self, tmp_path: Path) -> None:
        """Test-only callers that omit slug/repo_root keep the historical
        no-side-effect behavior (no parse-failures dir created)."""
        reporter = _RecordingReporter()
        propose_steps_from_claude(
            "build a thing", lambda prompt: "nope", reporter=reporter
        )
        assert not (tmp_path / ".plan-tool").exists()


def _no_intent_json(*titles: str) -> str:
    """A valid step graph whose steps carry no ``intent`` — the soft rejection."""
    return json.dumps(
        [_proposed_step(t, intent=None) for t in (titles or ("one",))]
    )


class TestProposeStepsIntentRetry:
    """A proposed step with no usable ``intent`` is a SOFT rejection: it spends
    the function's existing single repair attempt (never a third call) and the
    valid steps are kept either way — the ``intent-presence`` finding and the
    intent proposer are the standing remedy for a still-missing one."""

    def test_no_retry_when_every_step_has_an_intent(self) -> None:
        calls = {"n": 0}

        def invoker(prompt: str) -> str:
            calls["n"] += 1
            return _ONE_STEP_JSON

        steps = propose_steps_from_claude(
            "build a thing", invoker, reporter=_RecordingReporter()
        )
        assert calls["n"] == 1
        assert steps is not None and steps[0].intent == "prove one lands"

    def test_missing_intent_triggers_one_retry(self) -> None:
        calls = {"n": 0}

        def invoker(prompt: str) -> str:
            calls["n"] += 1
            return _no_intent_json() if calls["n"] == 1 else _ONE_STEP_JSON

        reporter = _RecordingReporter()
        steps = propose_steps_from_claude(
            "build a thing", invoker, reporter=reporter
        )
        assert calls["n"] == 2  # original + the ONE repair retry, never three
        assert steps is not None
        assert [s.intent for s in steps] == ["prove one lands"]
        assert reporter.handles[0].completed is not None
        assert reporter.handles[0].failed is None

    def test_retry_prompt_names_the_steps_missing_intent(self) -> None:
        prompts: list[str] = []

        def invoker(prompt: str) -> str:
            prompts.append(prompt)
            return (
                _no_intent_json("alpha", "beta")
                if len(prompts) == 1
                else _ONE_STEP_JSON
            )

        propose_steps_from_claude(
            "build a thing", invoker, reporter=_RecordingReporter()
        )
        repair = prompts[1]
        # By array position + title: the model never emitted ids ("Ids are
        # assigned by the caller"), so an id would point at nothing it can see.
        assert "#1 (alpha)" in repair and "#2 (beta)" in repair
        # The correction stands alone — it restates the requirement, it does
        # not only name the offenders.
        assert "every object needs a non-empty `intent`" in repair
        assert "`TODO`, `TBD`" in repair

    def test_placeholder_intent_triggers_the_retry(self) -> None:
        calls = {"n": 0}

        def invoker(prompt: str) -> str:
            calls["n"] += 1
            if calls["n"] == 1:
                return json.dumps([_proposed_step("one", intent="TBD")])
            return _ONE_STEP_JSON

        steps = propose_steps_from_claude(
            "build a thing", invoker, reporter=_RecordingReporter()
        )
        # ``is_usable_intent`` is the judge — a placeholder counts as missing.
        assert calls["n"] == 2
        assert steps is not None and steps[0].intent == "prove one lands"

    def test_missing_intent_after_retry_keeps_the_proposal(self) -> None:
        calls = {"n": 0}

        def invoker(prompt: str) -> str:
            calls["n"] += 1
            return _no_intent_json()

        reporter = _RecordingReporter()
        steps = propose_steps_from_claude(
            "build a thing", invoker, reporter=reporter
        )
        assert calls["n"] == 2
        # Soft: a valid step graph is never discarded over a missing one-liner.
        assert steps is not None
        assert [s.title for s in steps] == ["one"]
        assert steps[0].intent is None
        assert reporter.handles[0].completed is not None
        assert reporter.handles[0].failed is None

    def test_intent_shortfall_writes_no_parse_failure(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.run_log import RunLogWriter

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        run_logger = RunLogWriter.start(
            repo_root=tmp_path,
            slug="demo",
            command="create",
            argv=["plan-tool", "create", "demo"],
        )

        steps = propose_steps_from_claude(
            "build a thing",
            lambda prompt: _no_intent_json(),
            reporter=_RecordingReporter(),
            repo_root=tmp_path,
            slug="demo",
            output_dir=out_dir,
            run_logger=run_logger,
        )
        assert steps is not None
        # An intent-only shortfall is not a parse error — filing it as one
        # would misreport a valid proposal as a broken response.
        assert not (tmp_path / ".plan-tool" / "parse-failures").exists()
        events = _read_run_log(tmp_path, "demo")
        assert [e for e in events if e["event"] == "parse_failure"] == []

    def test_intent_retry_shares_the_single_repair_budget(self) -> None:
        """An unparseable first response repaired into an intent-less second
        gives exactly two calls — the two rejection kinds share one budget."""
        calls = {"n": 0}

        def invoker(prompt: str) -> str:
            calls["n"] += 1
            return "sorry, no json" if calls["n"] == 1 else _no_intent_json()

        steps = propose_steps_from_claude(
            "build a thing", invoker, reporter=_RecordingReporter()
        )
        assert calls["n"] == 2
        assert steps is not None and steps[0].intent is None

    def test_soft_retry_keeps_first_proposal_when_retry_is_unparseable(
        self,
    ) -> None:
        calls = {"n": 0}
        rationales: dict[int, str] = {}

        def invoker(prompt: str) -> str:
            calls["n"] += 1
            if calls["n"] == 1:
                return json.dumps(
                    [_proposed_step("keeper", intent=None, rationale="pure")]
                )
            return "garbage, not json"

        reporter = _RecordingReporter()
        steps = propose_steps_from_claude(
            "build a thing",
            invoker,
            reporter=reporter,
            rationales_out=rationales,
        )
        assert calls["n"] == 2
        # The good first graph survives a worse retry — the naive
        # single-``raw`` implementation drops it.
        assert steps is not None
        assert [s.title for s in steps] == ["keeper"]
        assert rationales == {1: "pure"}
        assert reporter.handles[0].failed is None

    def test_soft_retry_restores_depends_on_notes_key_present(
        self,
    ) -> None:
        """Re-decompose fallback must restore omit-vs-``{}`` flags with steps.

        Attempt 2 clears ``depends_on_notes_key_present_out`` before re-parse;
        without a keep_on_failure snapshot, a restored first proposal would
        leave empty/stale flags for ``_preserve_on_disk_step_fields``.
        """
        calls = {"n": 0}
        notes_key_present: dict[int, bool] = {}

        def invoker(prompt: str) -> str:
            calls["n"] += 1
            if calls["n"] == 1:
                # Omit depends_on_notes (False) on step 1; explicit {} (True)
                # on step 2 — both missing usable intent to force soft repair.
                return json.dumps(
                    [
                        _proposed_step(
                            "alpha",
                            intent=None,
                            depends_on=[],
                        ),
                        _proposed_step(
                            "beta",
                            intent=None,
                            depends_on=[1],
                            depends_on_notes={},
                        ),
                    ]
                )
            # Same count, different titles → re-decompose → keep attempt 1.
            return json.dumps(
                [
                    _proposed_step("other-a", intent="x"),
                    _proposed_step(
                        "other-b",
                        intent="y",
                        depends_on=[1],
                        depends_on_notes={1: "repair note"},
                    ),
                ]
            )

        steps = propose_steps_from_claude(
            "build a thing",
            invoker,
            reporter=_RecordingReporter(),
            depends_on_notes_key_present_out=notes_key_present,
        )
        assert calls["n"] == 2
        assert steps is not None
        assert [s.title for s in steps] == ["alpha", "beta"]
        assert notes_key_present == {1: False, 2: True}

    def test_soft_retry_preserves_notes_when_repair_omits_key(self) -> None:
        """Same-decomposition intent repair must not silently clear notes."""
        calls = {"n": 0}

        def invoker(prompt: str) -> str:
            calls["n"] += 1
            if calls["n"] == 1:
                return json.dumps(
                    [
                        _proposed_step("alpha", intent=None),
                        _proposed_step(
                            "beta",
                            intent=None,
                            depends_on=[1],
                            depends_on_notes={1: "consumes alpha API"},
                        ),
                    ]
                )
            # Same titles + intents; omit depends_on_notes entirely.
            return json.dumps(
                [
                    _proposed_step("alpha", intent="land alpha"),
                    _proposed_step(
                        "beta",
                        intent="land beta",
                        depends_on=[1],
                    ),
                ]
            )

        steps = propose_steps_from_claude(
            "build a thing", invoker, reporter=_RecordingReporter()
        )
        assert calls["n"] == 2
        assert steps is not None
        assert steps[1].depends_on_notes == {1: "consumes alpha API"}

    def test_soft_retry_explicit_empty_notes_clears(self) -> None:
        calls = {"n": 0}

        def invoker(prompt: str) -> str:
            calls["n"] += 1
            if calls["n"] == 1:
                return json.dumps(
                    [
                        _proposed_step("alpha", intent=None),
                        _proposed_step(
                            "beta",
                            intent=None,
                            depends_on=[1],
                            depends_on_notes={1: "consumes alpha API"},
                        ),
                    ]
                )
            return json.dumps(
                [
                    _proposed_step("alpha", intent="land alpha"),
                    _proposed_step(
                        "beta",
                        intent="land beta",
                        depends_on=[1],
                        depends_on_notes={},
                    ),
                ]
            )

        steps = propose_steps_from_claude(
            "build a thing", invoker, reporter=_RecordingReporter()
        )
        assert calls["n"] == 2
        assert steps is not None
        assert steps[1].depends_on_notes == {}

    def test_checkpoint_saves_the_accepted_response_body(
        self, tmp_path: Path
    ) -> None:
        """``raw`` and the returned steps stay in sync: a ``--resume`` must not
        replay a body the previous run never used."""
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        first = _no_intent_json("keeper")
        calls = {"n": 0}

        def invoker(prompt: str) -> str:
            calls["n"] += 1
            return first if calls["n"] == 1 else "garbage, not json"

        steps = propose_steps_from_claude(
            "build a thing",
            invoker,
            reporter=_RecordingReporter(),
            repo_root=tmp_path,
            slug="demo",
            output_dir=out_dir,
        )
        assert steps is not None and [s.title for s in steps] == ["keeper"]
        ckpt = checkpoint_path(tmp_path, "demo", _INITIAL_STEPS_CHECKPOINT_NAME)
        saved = json.loads(ckpt.read_text(encoding="utf-8"))
        assert saved["payload"] == first

    def test_retry_notice_names_the_intent_reason(self) -> None:
        calls = {"n": 0}

        def invoker(prompt: str) -> str:
            calls["n"] += 1
            return _no_intent_json() if calls["n"] == 1 else _ONE_STEP_JSON

        reporter = _RecordingReporter()
        propose_steps_from_claude("build a thing", invoker, reporter=reporter)
        notices = reporter.handles[0].notices
        assert len(notices) == 1
        message, kind = notices[0]
        assert kind == "retry"
        assert "intent" in message

    def test_cached_body_without_intent_spends_no_call(
        self, tmp_path: Path
    ) -> None:
        """A checkpoint predating the ``intent`` prompt key resumes as-is.

        ``_initial_steps_input_hash`` deliberately does not key on the prompt
        text, and the save block is gated on a cache MISS — so retrying a
        resume would spend a call whose better body is never written back, and
        every later resume of the slug would spend it again.
        """
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        legacy = _no_intent_json("legacy")
        save_checkpoint(
            checkpoint_path(tmp_path, "demo", _INITIAL_STEPS_CHECKPOINT_NAME),
            Checkpoint(
                input_hash=_initial_steps_input_hash(
                    "demo", "build a thing", out_dir, tmp_path
                ),
                payload=legacy,
                created_at=_now_iso(),
            ),
        )

        def explode(prompt: str) -> str:
            raise AssertionError("a cached hit must not spend a call")

        steps = propose_steps_from_claude(
            "build a thing",
            explode,
            reporter=_RecordingReporter(),
            repo_root=tmp_path,
            slug="demo",
            output_dir=out_dir,
        )
        assert steps is not None
        assert [s.title for s in steps] == ["legacy"]
        assert steps[0].intent is None  # left to the intent-presence finding


    def test_retry_clears_stale_rationales_from_the_first_attempt(self) -> None:
        """`_parse_steps_json` only ever adds, so attempt 1's rationales would
        otherwise survive under attempt 2's ids — handing the change-type
        wizard a defense written about a superseded step."""
        first = json.dumps(
            [
                {"title": "A", "rationale": "A-why", "files": [], "depends_on": []},
                {"title": "B", "rationale": "B-why", "files": [], "depends_on": []},
            ]
        )
        repair = json.dumps(
            [
                {
                    "title": "A",
                    "intent": "why A",
                    "rationale": "A2-why",
                    "files": [],
                    "depends_on": [],
                },
                {
                    "title": "B",
                    "intent": "why B",
                    "files": [],
                    "depends_on": [],
                },
            ]
        )
        responses = iter([first, repair])
        rationales: dict[int, str] = {}
        steps = propose_steps_from_claude(
            "build a thing",
            lambda _p: next(responses),
            rationales_out=rationales,
        )
        assert steps is not None
        assert rationales == {1: "A2-why"}

    def test_repair_that_redecomposes_is_discarded(self) -> None:
        """A soft rejection means the graph was already good, so the repair is
        licensed only to ADD intents. A repair that re-decomposes silently
        replaced a graph the operator never saw."""
        first = json.dumps(
            [
                {"title": t, "files": [], "depends_on": []}
                for t in ("A", "B", "C")
            ]
        )
        repair = json.dumps(
            [{"title": "One big step", "intent": "w", "files": [], "depends_on": []}]
        )
        responses = iter([first, repair])
        steps = propose_steps_from_claude(
            "build a thing", lambda _p: next(responses)
        )
        assert steps is not None
        assert [s.title for s in steps] == ["A", "B", "C"]

    def test_repair_that_only_adds_intents_is_taken(self) -> None:
        first = json.dumps(
            [{"title": t, "files": [], "depends_on": []} for t in ("A", "B")]
        )
        repair = json.dumps(
            [
                {"title": "A", "intent": "why A", "files": [], "depends_on": []},
                {"title": "B", "intent": "why B", "files": [], "depends_on": []},
            ]
        )
        responses = iter([first, repair])
        steps = propose_steps_from_claude(
            "build a thing", lambda _p: next(responses)
        )
        assert steps is not None
        assert [s.intent for s in steps] == ["why A", "why B"]

class TestStepsMissingIntent:
    def test_reports_positions_of_unusable_intents(self) -> None:
        steps = [
            Step(id=1, title="a", intent="real why"),
            Step(id=2, title="b"),
            Step(id=3, title="c", intent="   "),
            Step(id=4, title="d", intent="TODO"),
        ]
        assert _steps_missing_intent(steps) == [2, 3, 4]

    def test_empty_when_every_step_has_one(self) -> None:
        steps = [Step(id=1, title="a", intent="why a")]
        assert _steps_missing_intent(steps) == []


class TestSummarizeStepGraphError:
    def _err(self, steps: list[dict]):
        with pytest.raises(PydanticValidationError) as ei:
            Plan(
                title="t",
                status=PlanStatus.PLANNING,
                priority=Priority.LOW,
                steps=[Step(**s) for s in steps],
            )
        return ei.value

    def test_unknown_dependency(self) -> None:
        exc = self._err([{"id": 1, "title": "a", "depends_on": [99]}])
        assert _summarize_step_graph_error(exc) == (
            "step 1 depends_on references unknown id(s): [99]"
        )

    def test_self_dependency(self) -> None:
        exc = self._err([{"id": 1, "title": "a", "depends_on": [1]}])
        assert "cannot depend on itself" in _summarize_step_graph_error(exc)

    def test_strips_value_error_prefix(self) -> None:
        exc = self._err([{"id": 1, "title": "a", "depends_on": [99]}])
        assert not _summarize_step_graph_error(exc).startswith("Value error")


class TestDumpFailedResponse:
    def test_returns_none_without_slug(self, tmp_path: Path) -> None:
        assert (
            _dump_failed_response(
                repo_root=tmp_path,
                slug=None,
                phase="x",
                iteration=0,
                raw="data",
            )
            is None
        )

    def test_writes_under_parse_failures(self, tmp_path: Path) -> None:
        path = _dump_failed_response(
            repo_root=tmp_path,
            slug="demo",
            phase="propose-steps-invalid-graph",
            iteration=2,
            raw="raw body",
        )
        assert path is not None
        assert path.read_text() == "raw body"
        assert path.parent == tmp_path / ".plan-tool" / "parse-failures" / "demo"
        assert "iter2" in path.name


class _FakeSpeller:
    """Deterministic Speller for spell-check tests — no pyspellchecker dep.

    ``vocab`` is the set of known words (lowercased); anything else is
    "misspelled". ``fixes`` maps a misspelled word to its suggestion.
    """

    def __init__(self, vocab: set[str], fixes: dict[str, str] | None = None) -> None:
        self._vocab = {w.lower() for w in vocab}
        self._fixes = fixes or {}

    def is_misspelled(self, word: str) -> bool:
        return word.lower() not in self._vocab

    def correction(self, word: str) -> Optional[str]:
        return self._fixes.get(word.lower())


class TestLooksLikeCode:
    @pytest.mark.parametrize(
        "token",
        ["bedrock.ts", "create-ssm.sh", "instanceName", "SSM", "v2", "api_key", "a/b"],
    )
    def test_code_shaped_tokens(self, token: str) -> None:
        assert _looks_like_code(token) is True

    @pytest.mark.parametrize("token", ["Standardize", "parameters", "app", "Plan"])
    def test_plain_words_are_not_code(self, token: str) -> None:
        assert _looks_like_code(token) is False


class TestFindMisspellings:
    def test_flags_slug_typo_with_suggestion(self) -> None:
        speller = _FakeSpeller(
            {"standardize", "app", "parameters"}, {"paramerters": "parameters"}
        )
        out = find_misspellings(
            {"slug": "standardize-app-paramerters"}, speller=speller
        )
        assert out == [
            Misspelling(word="paramerters", field="slug", suggestion="parameters")
        ]

    def test_dedupes_across_slug_and_title(self) -> None:
        speller = _FakeSpeller({"standardize", "app"}, {"paramerters": "parameters"})
        out = find_misspellings(
            {
                "slug": "standardize-app-paramerters",
                "title": "Standardize App Paramerters",
            },
            speller=speller,
        )
        assert [m.word for m in out] == ["paramerters"]
        assert out[0].field == "slug"  # first field wins

    def test_skips_code_and_short_tokens(self) -> None:
        # ``instanceName`` (camelCase), ``bedrock.ts`` / ``create-ssm.sh``
        # tails (dotted), ``v2`` (digit), and ``app`` / ``ssm`` (<4 chars)
        # are all skipped. Only the plain word ``create`` survives the
        # filters (the dash split exposes it), so knowing it => no findings.
        speller = _FakeSpeller({"create"})
        out = find_misspellings(
            {"title": "Use instanceName in bedrock.ts and create-ssm.sh v2; app ssm"},
            speller=speller,
        )
        assert out == []

    def test_clean_fields_no_findings(self) -> None:
        speller = _FakeSpeller({"standardize", "app", "parameters"})
        assert find_misspellings({"slug": "standardize-app-parameters"}, speller=speller) == []

    def test_domain_vocabulary_is_allowlisted(self) -> None:
        # A dictionary flags these and suggests nonsense ('jira' -> 'lira'),
        # firing on every touch of the plan. See BUG_BACKLOG.
        speller = _FakeSpeller({"export"}, {"jira": "lira", "backlog": "backlog"})
        out = find_misspellings(
            {"slug": "jira-export-backlog", "title": "Jira Export Backlog"},
            speller=speller,
        )
        assert out == []

    def test_allowlist_does_not_mute_real_typos(self) -> None:
        speller = _FakeSpeller({"export"}, {"jira": "lira", "paramerters": "parameters"})
        out = find_misspellings({"slug": "jira-export-paramerters"}, speller=speller)
        assert [m.word for m in out] == ["paramerters"]

    def test_noop_when_speller_unavailable(self, monkeypatch) -> None:
        # Default path with the optional dep absent => silent no-op.
        monkeypatch.setattr("plan_tool.create._load_speller", lambda: None)
        assert find_misspellings({"slug": "definitelynotaword-xyzzyq"}) == []

    def test_empty_fields_ignored(self) -> None:
        speller = _FakeSpeller(set())
        assert find_misspellings({"slug": "", "title": ""}, speller=speller) == []


class TestCreatePlanSpellCheck:
    def test_warns_and_records_slug_typo(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool import create as create_module

        monkeypatch.setattr(
            create_module,
            "_load_speller",
            lambda: _FakeSpeller(
                {"standardize", "demo", "plan"}, {"paramerters": "parameters"}
            ),
        )
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        canned = _ONE_STEP_JSON
        result = create_plan(
            "standardize-app-paramerters",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=tmp_path / "m.json",
            from_description="Build a thing",
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=lambda prompt: canned,
        )
        assert result.plan_path is not None and result.plan_path.is_file()
        assert [m.word for m in result.misspellings] == ["paramerters"]
        err = capsys.readouterr().err
        assert "possible misspelling" in err
        assert "paramerters" in err and "parameters" in err

    def test_clean_slug_no_warning(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool import create as create_module

        monkeypatch.setattr(
            create_module,
            "_load_speller",
            lambda: _FakeSpeller({"standardize", "demo", "plan"}),
        )
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        canned = _ONE_STEP_JSON
        result = create_plan(
            "standardize",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=tmp_path / "m.json",
            from_description="Build a thing",
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=lambda prompt: canned,
        )
        assert result.misspellings == []
        assert "possible misspelling" not in capsys.readouterr().err


@pytest.mark.integration
class TestCmdCreateFromEndToEndStderr:
    """End-to-end ``plan-tool create --from`` flow: ``StderrReporter`` (the
    production default) emits a start + completion line on stderr.
    """

    def test_emits_progress_on_stderr(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool.cli import context as cli_context
        from plan_tool import create as create_module
        from plan_tool.launcher import ApplyFindingResult

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        canned = json.dumps(
            [{"title": "first", "complexity": "low", "files": [], "depends_on": []}]
        )

        original_create_plan = cli_module.create_plan
        answers = _basic_metadata_answers()

        def patched_create_plan(*args, **kwargs):
            kwargs.setdefault("input_fn", _queue_input(answers))
            kwargs["claude_invoker"] = lambda prompt: canned
            return original_create_plan(*args, **kwargs)

        monkeypatch.setattr("plan_tool.cli.authoring.create_plan", patched_create_plan)
        # Stub apply_finding so the post-write convergence loop doesn't
        # shell out to real claude (apply_finding defaults to shell_invoker).
        monkeypatch.setattr(
            create_module,
            "apply_finding",
            lambda *a, **kw: ApplyFindingResult(
                step_id=None, exit_code=0, verdict="APPLIED",
                summary="", diff_text="", pre_snapshot={}, stdout="",
            ),
        )
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(
            [
                "--manifest",
                str(manifest),
                "create",
                "demo",
                "--from",
                "build a thing",
                "--output-dir",
                str(out_dir),
            ]
        )
        assert rc == 0
        err = capsys.readouterr().err
        # Singleton call (n=1) → the ``[1/1]`` counter is suppressed.
        assert "Proposing initial steps" in err
        assert "[1/1]" not in err
        assert "done in" in err


# --- Step 6: create hardening ---------------------------------------------


from plan_tool.create import validate_lessons_in_repo


class TestValidateLessonsInRepo:
    def test_accepts_relative_path_inside_repo(self, tmp_path: Path) -> None:
        validate_lessons_in_repo("plan-details/foo/lessons.md", tmp_path)

    def test_accepts_absolute_path_inside_repo(self, tmp_path: Path) -> None:
        validate_lessons_in_repo(
            str(tmp_path / "plan-details" / "foo" / "lessons.md"),
            tmp_path,
        )

    def test_rejects_path_outside_repo(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        with pytest.raises(CreateError, match="not inside"):
            validate_lessons_in_repo(str(outside / "lessons.md"), repo)


class TestCreatePlanPublication:
    @pytest.mark.parametrize("newline", ["\n", "\r\n", "\r"])
    def test_publish_create_plan_preserves_collision_to_manifest_order(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, newline: str
    ) -> None:
        """Publish replacement state in the order later phases rely on."""
        from plan_tool import create as create_module
        from plan_tool.canonical import CanonicalProvenance
        from plan_tool.concept_sync import ConceptSyncResult, SyncStatus

        repo_root = tmp_path
        output_dir = repo_root / "plans"
        output_dir.mkdir()
        manifest_path = repo_root / "manifest.json"
        collision_path = output_dir / "4-old.md"
        plan_path = output_dir / "2-demo.md"
        existing_details = output_dir / "plan-details" / "old"
        renamed_details = output_dir / "plan-details" / "demo"
        plan = Plan(
            title="Demo",
            status=PlanStatus.PLANNING,
            priority=Priority.MEDIUM,
            steps=[Step(id=1, title="Publish")],
        )
        concept_tree = ConceptTree(
            "demo",
            "",
            [
                ConceptNode(
                    id=concept_id("Publication", []),
                    title="Publication",
                    review_state="approved",
                )
            ],
        )
        prepared = create_module.PreparedCreatePlan(
            plan=plan,
            output_dir=output_dir,
            predicted_plan_path=plan_path,
            manifest_path=manifest_path,
            collisions=[create_module.Collision(collision_path, registered=True)],
            should_replace=True,
            provenance=CanonicalProvenance("4-old.md", "plan-details/old"),
            from_existing_path=collision_path,
            concept_tree=concept_tree,
            saved_concepts=None,
            references=[],
            seed_sections={},
            synthesized_sections=None,
            supplied_guardrails={},
            risk_profile_proposal=create_module._standard_risk_profile_proposal(
                "Risk classification defaults to standard for publication setup."
            ),
            continuation=create_module._CreatePlanContinuation(
                from_description=None,
                input_fn=input,
                distilled_seed=None,
                dropped_references=[],
                misspellings=[],
            ),
        )
        events: list[str] = []

        def archive(source: Path, target: Path, **kwargs: Any):
            assert source == collision_path
            assert target == plan_path
            events.append("archive")
            return create_module.ArchiveResult(
                archived=[(collision_path, output_dir / "archive" / "4-old.md")]
            )

        def remove(manifest: Path, root: Path, source: Path) -> bool:
            assert (manifest, root, source) == (
                manifest_path, repo_root, collision_path,
            )
            events.append("remove")
            return True

        def write(*args: Any, **kwargs: Any) -> Path:
            assert args[:3] == (output_dir, "demo", plan)
            events.append("write")
            plan_path.write_bytes(("published" + newline).encode())
            return plan_path

        def parse(path: Path) -> Plan:
            assert path == plan_path
            events.append("parse")
            return plan

        def resolve(source: Path, provenance: CanonicalProvenance) -> Path:
            assert (source, provenance) == (
                collision_path, prepared.provenance,
            )
            events.append("resolve-details")
            return existing_details

        def rename(source: Path, target_dir: Path, slug: str):
            assert (source, target_dir, slug) == (
                existing_details, output_dir, "demo",
            )
            events.append("rename")
            return renamed_details, None

        def fingerprint(path: Path) -> str:
            assert path == plan_path
            events.append("fingerprint")
            return "initial-fingerprint"

        def sync(*args: Any, **kwargs: Any) -> ConceptSyncResult:
            assert args[:4] == (plan_path, plan, None, concept_tree)
            assert args[3] is not concept_tree
            assert kwargs["source_plan_text"] == "published" + newline
            events.append("sync")
            return ConceptSyncResult(SyncStatus.SUCCESS, plan_fingerprint="synced")

        def append(manifest: Path, root: Path, path: Path) -> bool:
            assert (manifest, root, path) == (manifest_path, repo_root, plan_path)
            events.append("append")
            return True

        monkeypatch.setattr(create_module, "archive_existing_source", archive)
        monkeypatch.setattr(create_module, "remove_from_manifest", remove)
        monkeypatch.setattr(create_module, "write_new_plan", write)
        monkeypatch.setattr(create_module, "parse_plan", parse)
        monkeypatch.setattr(create_module, "resolve_existing_plan_details", resolve)
        monkeypatch.setattr(create_module, "rename_plan_details_to_slug", rename)
        monkeypatch.setattr(
            "plan_tool.review_persistence.compute_plan_fingerprint", fingerprint
        )
        monkeypatch.setattr(create_module, "synchronize_concepts", sync)
        monkeypatch.setattr(create_module, "append_to_manifest", append)

        published = create_module._publish_create_plan(
            "demo", prepared=prepared, repo_root=repo_root
        )

        assert events == [
            "archive",
            "remove",
            "write",
            "parse",
            "resolve-details",
            "rename",
            "fingerprint",
            "sync",
            "parse",
            "append",
        ]
        assert published.plan_path == plan_path
        assert published.concept_tree.plan_fingerprint == "synced"
        assert published.manifest_updated is True
        assert published.plan_details_renamed_to == renamed_details
        assert published.replaced_manifest_entries == ["plans/4-old.md"]


class TestCreatePlanFinalization:
    def _handoffs(
        self,
        tmp_path: Path,
        *,
        plan: Optional[Plan] = None,
        concept_tree: Optional[ConceptTree] = None,
        signed_concept_scope: bool = False,
    ) -> tuple[Any, Any]:
        from plan_tool import create as create_module

        output_dir = tmp_path / "plans"
        output_dir.mkdir(exist_ok=True)
        plan_path = output_dir / "2-demo.md"
        plan_path.write_text("published plan\n", encoding="utf-8")
        plan = plan or Plan(
            title="Original proposal",
            status=PlanStatus.PLANNING,
            priority=Priority.MEDIUM,
            steps=[Step(id=1, title="Prepare")],
        )
        concept_tree = concept_tree or ConceptTree("demo", "initial", [])
        prepared = create_module.PreparedCreatePlan(
            plan=plan,
            output_dir=output_dir,
            predicted_plan_path=plan_path,
            manifest_path=tmp_path / "manifest.json",
            collisions=[],
            should_replace=False,
            provenance=None,
            from_existing_path=None,
            concept_tree=concept_tree,
            saved_concepts=None,
            references=[],
            seed_sections={},
            synthesized_sections=None,
            supplied_guardrails={},
            risk_profile_proposal=create_module._standard_risk_profile_proposal(
                "Risk classification defaults to standard for finalization setup."
            ),
            continuation=create_module._CreatePlanContinuation(
                from_description="Build a thing",
                input_fn=input,
                distilled_seed=None,
                dropped_references=[],
                misspellings=[],
            ),
        )
        published = create_module._PublishedCreatePlan(
            plan_path=plan_path,
            concept_tree=concept_tree,
            plan_fingerprint="published-fingerprint",
            signed_concept_scope=signed_concept_scope,
            manifest_updated=True,
            plan_details_renamed_to=None,
            plan_details_skip_reason=None,
            replaced_archives=[],
            replaced_skipped=[],
            replaced_manifest_entries=[],
        )
        return prepared, published

    def test_create_plan_runs_prepare_publish_converge_finalize_in_order(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool import create as create_module

        prepared, published = self._handoffs(tmp_path)
        terminal_outcome = "iteration-stage failure"
        expected = CreateResult(
            plan_path=published.plan_path,
            manifest_path=prepared.manifest_path,
            manifest_updated=True,
            iteration_stage_failure=terminal_outcome,
        )
        calls: list[str] = []

        def prepare(slug: str, **kwargs: Any):
            assert slug == "demo"
            calls.append("prepare")
            return prepared

        def publish(slug: str, **kwargs: Any):
            assert slug == "demo"
            assert kwargs["prepared"] is prepared
            calls.append("publish")
            return published

        def converge(request: Any):
            assert request.plan_path == published.plan_path
            assert request.plan_fingerprint == "published-fingerprint"
            assert request.output_dir == prepared.output_dir
            assert request.from_description == prepared.continuation.from_description
            calls.append("converge")
            return terminal_outcome

        def finalize(slug: str, **kwargs: Any):
            assert slug == "demo"
            assert kwargs["prepared"] is prepared
            assert kwargs["published"] is published
            assert kwargs["iteration_stage_failure"] == terminal_outcome
            calls.append("finalize")
            return expected

        monkeypatch.setattr(create_module, "_prepare_create_plan", prepare)
        monkeypatch.setattr(create_module, "_publish_create_plan", publish)
        monkeypatch.setattr(create_module, "_converge_create_plan", converge)
        monkeypatch.setattr(create_module, "_finalize_create_plan", finalize)

        assert create_plan("demo", repo_root=tmp_path) is expected
        assert calls == ["prepare", "publish", "converge", "finalize"]

    def test_create_plan_reraises_detail_format_error_from_convergence(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool import create as create_module
        from plan_tool.detail_artifacts import DetailFormatError

        prepared, published = self._handoffs(tmp_path)
        monkeypatch.setattr(
            create_module, "_prepare_create_plan", lambda *_args, **_kwargs: prepared,
        )
        monkeypatch.setattr(
            create_module, "_publish_create_plan", lambda *_args, **_kwargs: published,
        )
        monkeypatch.setattr(
            create_module,
            "_converge_create_plan",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                DetailFormatError("detail declares an unsupported version")
            ),
        )
        monkeypatch.setattr(
            create_module,
            "_restore_materialized_evidence_and_sync_concepts",
            lambda *_args, **_kwargs: None,
        )

        with pytest.raises(DetailFormatError):
            create_plan("demo", repo_root=tmp_path)

    def test_create_phase_definitions_follow_orchestration_order(self) -> None:
        """Keep the phase handoffs readable in the order create invokes them."""
        from plan_tool import create as create_module

        source = inspect.getsource(create_module)
        phase_definitions = (
            "def _prepare_create_plan(",
            "def _publish_create_plan(",
            "def _converge_create_plan(",
            "def _finalize_create_plan(",
        )
        assert [source.index(phase) for phase in phase_definitions] == sorted(
            source.index(phase) for phase in phase_definitions
        )

    def test_create_plan_split_proposal_bypasses_later_phases(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool import create as create_module

        split_result = CreateResult(
            plan_path=None,
            manifest_path=tmp_path / "manifest.json",
            manifest_updated=False,
            split_proposal=create_module.SplitProposal(entries=[]),
        )
        monkeypatch.setattr(
            create_module, "_prepare_create_plan", lambda *args, **kwargs: split_result
        )

        def unexpected_phase(*args: Any, **kwargs: Any):
            raise AssertionError("split proposals must bypass later phases")

        monkeypatch.setattr(create_module, "_publish_create_plan", unexpected_phase)
        monkeypatch.setattr(create_module, "_converge_create_plan", unexpected_phase)
        monkeypatch.setattr(create_module, "_finalize_create_plan", unexpected_phase)

        assert create_plan("demo", repo_root=tmp_path) is split_result

    def test_finalize_create_plan_discards_checkpoints_for_normal_terminal_outcome(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool import create as create_module
        from plan_tool.checkpoint import checkpoint_dir

        prepared, published = self._handoffs(tmp_path)
        checkpoint_root = checkpoint_dir(tmp_path, "demo")
        checkpoint_root.mkdir(parents=True)
        checkpoint_names = (
            create_module._INITIAL_STEPS_CHECKPOINT_NAME,
            create_module._REFERENCES_CHECKPOINT_NAME,
            create_module._BODY_SECTIONS_CHECKPOINT_NAME,
            create_module._DISTILL_SEED_CHECKPOINT_NAME,
            create_module._RISK_PROFILE_CHECKPOINT_NAME,
            create_module._RISK_DECLARATION_CHECKPOINT_NAME,
            create_module._REFERENCE_DOCS_CHECKPOINT_NAME,
            create_module._STEP_REVIEW_CHECKPOINT_NAME,
            create_module._INTENT_REVIEW_CHECKPOINT_NAME,
        )
        for name in checkpoint_names:
            (checkpoint_root / f"{name}.json").write_text("{}", encoding="utf-8")

        discarded: list[tuple[str, str]] = []

        class RunLogger:
            def checkpoint_discard(self, name: str, reason: str) -> None:
                discarded.append((name, reason))

        monkeypatch.setattr(create_module, "parse_plan", lambda path: prepared.plan)
        monkeypatch.setattr(create_module, "advise_path_issues", lambda *args: None)

        result = create_module._finalize_create_plan(
            "demo",
            prepared=prepared,
            published=published,
            iteration_stage_failure=None,
            repo_root=tmp_path,
            budget=create_module.IterativeBudget(enabled=False),
            run_logger=RunLogger(),
        )

        assert result.iteration_stage_failure is None
        assert not list(checkpoint_root.glob("create-*.json"))
        assert discarded == [(name, "success") for name in checkpoint_names]

    def test_finalize_create_plan_retains_checkpoints_after_iteration_stage_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool import create as create_module
        from plan_tool.checkpoint import checkpoint_dir

        prepared, published = self._handoffs(tmp_path)
        checkpoint_root = checkpoint_dir(tmp_path, "demo")
        checkpoint_root.mkdir(parents=True)
        checkpoint = checkpoint_root / "create-initial-steps.json"
        checkpoint.write_text("{}", encoding="utf-8")
        monkeypatch.setattr(create_module, "parse_plan", lambda path: prepared.plan)
        monkeypatch.setattr(create_module, "advise_path_issues", lambda *args: None)

        result = create_module._finalize_create_plan(
            "demo",
            prepared=prepared,
            published=published,
            iteration_stage_failure="iteration 1 step proposal failed",
            repo_root=tmp_path,
            budget=create_module.IterativeBudget(enabled=False),
            run_logger=None,
        )

        assert result.iteration_stage_failure == "iteration 1 step proposal failed"
        assert checkpoint.exists()

    @pytest.mark.parametrize("newline", ["\n", "\r\n", "\r"])
    def test_finalize_create_plan_uses_original_plan_for_advice_and_disk_plan_for_concepts(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, newline: str
    ) -> None:
        from plan_tool import create as create_module
        from plan_tool.concept_sync import ConceptSyncResult, SyncStatus

        original_plan = Plan(
            title="Original proposal",
            status=PlanStatus.PLANNING,
            priority=Priority.MEDIUM,
            steps=[Step(id=1, title="Original step")],
        )
        disk_plan = Plan(
            title="Converged plan",
            status=PlanStatus.PLANNING,
            priority=Priority.MEDIUM,
            steps=[Step(id=1, title="Converged step")],
        )
        concept_tree = ConceptTree(
            "demo",
            "initial",
            [
                ConceptNode(
                    id=concept_id("Converged concept", []),
                    title="Converged concept",
                    review_state="approved",
                )
            ],
        )
        prepared, published = self._handoffs(
            tmp_path,
            plan=original_plan,
            concept_tree=concept_tree,
            signed_concept_scope=True,
        )
        published.plan_path.write_bytes(("published plan" + newline).encode())
        advice_plans: list[Plan] = []
        coverage_plans: list[Plan] = []

        monkeypatch.setattr(create_module, "parse_plan", lambda path: disk_plan)
        monkeypatch.setattr(
            create_module,
            "advise_path_issues",
            lambda plan, repo_root: advice_plans.append(plan),
        )

        def sync(plan_path: Path, plan: Plan, *args: Any, **kwargs: Any):
            assert plan_path == published.plan_path
            assert plan is disk_plan
            assert kwargs["source_plan_text"] == "published plan" + newline
            return ConceptSyncResult(SyncStatus.SUCCESS, plan_fingerprint="synced")

        def coverage(plan: Plan, *args: Any, **kwargs: Any):
            coverage_plans.append(plan)
            return []

        monkeypatch.setattr(create_module, "synchronize_concepts", sync)
        monkeypatch.setattr("plan_tool.review.check_concept_coverage", coverage)

        create_module._finalize_create_plan(
            "demo",
            prepared=prepared,
            published=published,
            iteration_stage_failure=None,
            repo_root=tmp_path,
            budget=create_module.IterativeBudget(enabled=True),
            run_logger=None,
        )

        assert advice_plans == [original_plan]
        assert coverage_plans == [disk_plan]

    def test_finalize_create_plan_reparses_after_unsigned_concept_persistence(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool import create as create_module

        prepared, published = self._handoffs(tmp_path)
        persisted_plan = Plan(
            title="Persisted plan",
            status=PlanStatus.PLANNING,
            priority=Priority.MEDIUM,
            steps=[Step(id=1, title="After persistence")],
        )
        events: list[str] = []

        monkeypatch.setattr(
            create_module, "advise_path_issues", lambda *args: None
        )

        def persist(*args: Any, **kwargs: Any) -> None:
            events.append("persist")

        def parse(path: Path) -> Plan:
            assert path == published.plan_path
            assert events == ["persist"]
            events.append("parse")
            return persisted_plan

        def coverage(plan: Plan, *args: Any, **kwargs: Any):
            assert plan is persisted_plan
            events.append("coverage")
            return []

        monkeypatch.setattr(create_module, "_persist_or_clear_concepts", persist)
        monkeypatch.setattr(create_module, "parse_plan", parse)
        monkeypatch.setattr(
            "plan_tool.review.check_concept_coverage", coverage
        )

        create_module._finalize_create_plan(
            "demo",
            prepared=prepared,
            published=published,
            iteration_stage_failure=None,
            repo_root=tmp_path,
            budget=create_module.IterativeBudget(enabled=True),
            run_logger=None,
        )

        assert events == ["persist", "parse", "coverage"]


@pytest.mark.integration
class TestCreatePlanPostWriteReparse:
    @pytest.fixture(autouse=True)
    def _stub_propose_references(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Stub the references claude call site so these tests don't
        shell out for the "Researching developer docs" step. They only
        assert behavior around the post-write reparse, not references."""
        from plan_tool import create as create_module
        monkeypatch.setattr(
            create_module, "propose_references_from_claude",
            lambda *a, **kw: ReferenceResearchResult.from_references([]),
        )

    def test_post_write_reparse_succeeds_for_valid_plan(
        self, tmp_path: Path
    ) -> None:
        """Happy path — the reparse silently passes for a normal create."""
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"
        answers = _basic_metadata_answers() + _single_step_answers()

        # Should not raise — reparse passes.
        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            input_fn=_queue_input(answers),
        )
        assert result.plan_path.is_file()

    def test_post_write_reparse_failure_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If parse_plan raises after the write, surface as CreateError."""
        from plan_tool import create as create_module

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"
        answers = _basic_metadata_answers() + _single_step_answers()

        from plan_tool.parser import ParseError

        def fake_parse(path):
            raise ParseError("simulated parse failure")

        monkeypatch.setattr(create_module, "parse_plan", fake_parse)

        with pytest.raises(CreateError, match="post-write reparse") as exc_info:
            create_plan(
                "demo",
                repo_root=tmp_path,
                output_dir_override=out_dir,
                manifest_path=manifest,
                input_fn=_queue_input(answers),
            )
        retained = out_dir / "2-demo.md"
        assert retained.is_file()
        assert exc_info.value.artifact == create_module._CreatedArtifact(
            retained, registered=False, parse_valid=False
        )
        assert not manifest.exists()


    def test_manifest_failure_retains_parse_valid_unregistered_artifact(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"
        monkeypatch.setattr(
            create_module,
            "append_to_manifest",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("manifest write stopped")),
        )
        with pytest.raises(CreateError, match="parse-valid but unregistered") as exc_info:
            create_plan(
                "demo",
                repo_root=tmp_path,
                output_dir_override=out_dir,
                manifest_path=manifest,
                input_fn=_queue_input(_basic_metadata_answers() + _single_step_answers()),
            )
        assert exc_info.value.artifact is not None
        assert exc_info.value.artifact.parse_valid is True
        assert exc_info.value.artifact.registered is False
        assert (out_dir / "2-demo.md").exists()


    def test_post_manifest_finalization_error_retains_registered_incomplete_plan(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"
        monkeypatch.setattr(create_module, "_converge_create_plan", lambda *_args: None)
        monkeypatch.setattr(
            create_module,
            "_finalize_create_plan",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("tail stopped")),
        )
        with pytest.raises(
            CreateError, match="registered but finalization is incomplete"
        ) as exc_info:
            create_plan(
                "demo",
                repo_root=tmp_path,
                output_dir_override=out_dir,
                manifest_path=manifest,
                input_fn=_queue_input(_basic_metadata_answers() + _single_step_answers()),
            )
        assert exc_info.value.artifact is not None
        assert exc_info.value.artifact.registered is True
        assert exc_info.value.artifact.parse_valid is True
        assert "plans/2-demo.md" in json.loads(manifest.read_text(encoding="utf-8"))["plans"]


@pytest.mark.integration
class TestCreatePlanRecoveryBoundaries:
    @pytest.fixture(autouse=True)
    def _stub_propose_references(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Keep recovery tests focused on their post-research failure seam."""
        monkeypatch.setattr(
            create_module,
            "propose_references_from_claude",
            lambda *_args, **_kwargs: ReferenceResearchResult.from_references([]),
        )

    def test_decision_gate_failure_has_no_replacement_side_effects(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Keep an unstarted publish from changing a replacement or its source."""
        output_dir = tmp_path / "plans"
        output_dir.mkdir()
        existing = output_dir / "2-demo.md"
        existing.write_text("retained collision\n", encoding="utf-8")
        source = tmp_path / "seed.md"
        source.write_text(
            "source that remains available\n\n## References\n\n"
            "- [API](https://example.test/api)\n",
            encoding="utf-8",
        )
        manifest = tmp_path / "m.json"
        manifest.write_text(
            json.dumps({"plans": ["plans/2-demo.md"]}), encoding="utf-8"
        )

        def fail_decision_checkpoint(*_args: Any, **_kwargs: Any) -> Any:
            raise CreateError("risk decision checkpoint failed; publication did not begin")

        monkeypatch.setattr(
            create_module, "_resolve_risk_declaration", fail_decision_checkpoint
        )

        with pytest.raises(CreateError, match="publication did not begin"):
            create_plan(
                "demo",
                repo_root=tmp_path,
                output_dir_override=output_dir,
                manifest_path=manifest,
                from_description=source.read_text(encoding="utf-8"),
                from_existing_path=source,
                input_fn=_queue_input(_basic_metadata_answers() + _single_step_answers()),
                replace_on_collision=True,
                claude_invoker=lambda prompt: (
                    _valid_preparation_response(prompt)
                    if "Distill a free-form seed" in prompt
                    else _ONE_STEP_JSON
                ),
            )

        assert existing.read_text(encoding="utf-8") == "retained collision\n"
        assert source.read_text(encoding="utf-8") == (
            "source that remains available\n\n## References\n\n"
            "- [API](https://example.test/api)\n"
        )
        assert json.loads(manifest.read_text(encoding="utf-8")) == {
            "plans": ["plans/2-demo.md"]
        }
        assert not (output_dir / "archive").exists()

    def test_write_new_plan_partial_is_retained_unregistered_and_retry_refuses_overwrite(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Keep a stub on disk for deliberate repair instead of retry cleanup."""
        output_dir = tmp_path / "plans"
        output_dir.mkdir()
        manifest = tmp_path / "m.json"

        def fail_final_plan_write(*_args: Any, **_kwargs: Any) -> None:
            raise OSError("final plan serialization stopped")

        monkeypatch.setattr(create_module, "write_plan", fail_final_plan_write)

        with pytest.raises(CreateError, match="invalid and unregistered") as exc_info:
            create_plan(
                "demo",
                repo_root=tmp_path,
                output_dir_override=output_dir,
                manifest_path=manifest,
                input_fn=_queue_input(_basic_metadata_answers() + _single_step_answers()),
                from_description="Build a thing",
                claude_invoker=lambda _prompt: json.dumps([{"description": "Build it", "intent": "Deliver behavior"}]),
                yes=True,
            )

        retained = output_dir / "2-demo.md"
        assert exc_info.value.artifact == create_module._CreatedArtifact(
            retained, registered=False, parse_valid=False
        )
        retained_bytes = retained.read_bytes()
        assert b"create_in_progress: true" in retained_bytes
        assert not manifest.exists()

        with pytest.raises(FileExistsError, match="not registered"):
            create_plan(
                "demo",
                repo_root=tmp_path,
                output_dir_override=output_dir,
                manifest_path=manifest,
                input_fn=lambda _prompt: (_ for _ in ()).throw(
                    AssertionError("a collision retry must stop before prompting")
                ),
                replace_on_collision=False,
            )

        assert retained.read_bytes() == retained_bytes
        assert not (output_dir / "archive").exists()

    def test_corrupt_postwrite_target_is_retained_as_invalid_recovery_artifact(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Fail closed when retained bytes cannot be decoded as a plan."""
        output_dir = tmp_path / "plans"
        output_dir.mkdir()
        manifest = tmp_path / "m.json"

        def corrupt_final_plan_write(path: Path, *_args: Any, **_kwargs: Any) -> None:
            path.write_bytes(b"\xff")
            raise OSError("final plan serialization stopped")

        monkeypatch.setattr(create_module, "write_plan", corrupt_final_plan_write)

        with pytest.raises(CreateError, match="invalid and unregistered") as exc_info:
            create_plan(
                "demo",
                repo_root=tmp_path,
                output_dir_override=output_dir,
                manifest_path=manifest,
                input_fn=_queue_input(_basic_metadata_answers() + _single_step_answers()),
            )

        retained = output_dir / "2-demo.md"
        assert retained.read_bytes() == b"\xff"
        assert exc_info.value.artifact == create_module._CreatedArtifact(
            retained, registered=False, parse_valid=False
        )
        assert not manifest.exists()

    def test_valid_postwrite_partial_retains_its_saved_risk_declaration(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Preserve the operator declaration when manifest publication stops."""
        output_dir = tmp_path / "plans"
        output_dir.mkdir()
        manifest = tmp_path / "m.json"
        declaration = create_module._RiskDeclaration(
            RiskProfile.HIGH,
            "Operator selected high review for the retained artifact.",
            "override",
        )
        monkeypatch.setattr(
            create_module,
            "_resolve_risk_declaration",
            lambda *_args, **_kwargs: declaration,
        )
        monkeypatch.setattr(
            create_module,
            "append_to_manifest",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                OSError("manifest write stopped")
            ),
        )

        with pytest.raises(CreateError, match="parse-valid but unregistered") as exc_info:
            create_plan(
                "demo",
                repo_root=tmp_path,
                output_dir_override=output_dir,
                manifest_path=manifest,
                input_fn=_queue_input(_basic_metadata_answers() + _single_step_answers()),
            )

        retained = output_dir / "2-demo.md"
        saved = parse_plan(retained)
        assert saved.risk_profile is RiskProfile.HIGH
        assert saved.risk_profile_rationale == declaration.rationale
        assert exc_info.value.artifact == create_module._CreatedArtifact(
            retained, registered=False, parse_valid=True
        )
        assert not manifest.exists()

    def test_postwrite_interrupt_retains_stub_as_invalid_recovery_artifact(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Carry the created stub through Ctrl-C instead of removing it."""
        output_dir = tmp_path / "plans"
        output_dir.mkdir()
        manifest = tmp_path / "m.json"
        monkeypatch.setattr(
            create_module,
            "write_plan",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(KeyboardInterrupt()),
        )

        with pytest.raises(create_module._CreateInterrupted) as exc_info:
            create_plan(
                "demo",
                repo_root=tmp_path,
                output_dir_override=output_dir,
                manifest_path=manifest,
                input_fn=_queue_input(_basic_metadata_answers() + _single_step_answers()),
            )

        retained = output_dir / "2-demo.md"
        assert exc_info.value.artifact == create_module._CreatedArtifact(
            retained, registered=False, parse_valid=False
        )
        assert retained.is_file()
        assert not manifest.exists()

    def test_from_existing_retained_plan_is_an_explicit_conversion_not_a_retry(
        self, tmp_path: Path
    ) -> None:
        """Archive a retained target only when the operator names it as the source."""
        output_dir = tmp_path / "plans"
        output_dir.mkdir()
        manifest = tmp_path / "m.json"
        retained = write_new_plan(
            output_dir,
            "demo",
            Plan(
                title="Retained demo",
                status=PlanStatus.PLANNING,
                priority=Priority.MEDIUM,
                steps=[Step(id=1, title="Repair retained plan")],
            ),
        )
        retained.write_text(
            retained.read_text(encoding="utf-8").replace(
                "## References\n\n_(TODO)_",
                "## References\n\n- [API](https://example.test/api)",
            ),
            encoding="utf-8",
        )
        retained_bytes = retained.read_bytes()

        def invoker(prompt: str) -> str:
            if "Distill a free-form seed" in prompt:
                return _valid_preparation_response(prompt)
            if "developer and API reference documentation" in prompt:
                return _REF_JSON
            if "Synthesize plan body sections" in prompt:
                return _SYNTHESIS_NULL_JSON
            return ""

        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=output_dir,
            manifest_path=manifest,
            from_description=retained.read_text(encoding="utf-8"),
            from_existing_path=retained,
            input_fn=_queue_input(_basic_metadata_answers() + _single_step_answers()),
            claude_invoker=invoker,
        )

        archived = output_dir / "archive" / "2-demo.replaced.md"
        assert result.plan_path == output_dir / "2-demo.md"
        assert archived.read_bytes().endswith(retained_bytes)
        assert result.plan_path.is_file()
        assert "plans/2-demo.md" in json.loads(manifest.read_text(encoding="utf-8"))["plans"]

@pytest.mark.integration
class TestCreatePlanLessonsValidation:
    def test_lessons_outside_repo_rejected(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".git").mkdir()
        out_dir = repo / "plans"
        out_dir.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        manifest = repo / "m.json"

        # Enable lessons (y), then provide an outside-repo path.
        outside_lessons = str(outside / "lessons.md")
        answers = (
            ["My Plan", "low", "y", outside_lessons]
            + _single_step_answers()
        )

        with pytest.raises(CreateError, match="not inside"):
            create_plan(
                "demo",
                repo_root=repo,
                output_dir_override=out_dir,
                manifest_path=manifest,
                input_fn=_queue_input(answers),
            )


# --- Step 1: priority-bucket prefix ---------------------------------------


class TestWriteNewPlanPriorityPrefix:
    def test_high_priority_gets_prefix_one(self, tmp_path: Path) -> None:
        plan = Plan(
            title="T", status=PlanStatus.PLANNING, priority=Priority.HIGH,
            steps=[Step(id=1, title="s")],
        )
        assert write_new_plan(tmp_path, "new", plan).name == "1-new.md"

    def test_medium_priority_gets_prefix_two(self, tmp_path: Path) -> None:
        plan = Plan(
            title="T", status=PlanStatus.PLANNING, priority=Priority.MEDIUM,
            steps=[Step(id=1, title="s")],
        )
        assert write_new_plan(tmp_path, "new", plan).name == "2-new.md"

    def test_low_priority_gets_prefix_three(self, tmp_path: Path) -> None:
        plan = Plan(
            title="T", status=PlanStatus.PLANNING, priority=Priority.LOW,
            steps=[Step(id=1, title="s")],
        )
        assert write_new_plan(tmp_path, "new", plan).name == "3-new.md"

    def test_prefix_ignores_existing_files(self, tmp_path: Path) -> None:
        """The priority bucket is fixed; pre-existing prefixed files in the
        output dir do not shift the new plan to a different number."""
        (tmp_path / "5-existing.md").write_text("x", encoding="utf-8")
        plan = Plan(
            title="T", status=PlanStatus.PLANNING, priority=Priority.MEDIUM,
            steps=[Step(id=1, title="s")],
        )
        assert write_new_plan(tmp_path, "new", plan).name == "2-new.md"


@pytest.mark.integration
class TestCreatePlanPriorityPrefix:
    @pytest.fixture(autouse=True)
    def _stub_propose_references(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Stub the references claude call site — these tests assert
        on filename prefixing logic, not references."""
        from plan_tool import create as create_module
        monkeypatch.setattr(
            create_module, "propose_references_from_claude",
            lambda *a, **kw: ReferenceResearchResult.from_references([]),
        )

    def test_create_uses_priority_bucket(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        (out_dir / "5-existing.md").write_text("x", encoding="utf-8")
        manifest = tmp_path / "m.json"
        answers = _basic_metadata_answers() + _single_step_answers()
        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            input_fn=_queue_input(answers),
        )
        # Medium priority (from _basic_metadata_answers) → bucket 2.
        assert result.plan_path.name == "2-demo.md"

    def test_create_high_priority(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"
        answers = (
            _basic_metadata_answers(priority="high")
            + _single_step_answers()
        )
        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            input_fn=_queue_input(answers),
        )
        assert result.plan_path.name == "1-demo.md"

    def test_create_low_priority(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"
        answers = (
            _basic_metadata_answers(priority="low")
            + _single_step_answers()
        )
        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            input_fn=_queue_input(answers),
        )
        assert result.plan_path.name == "3-demo.md"


# --- Step 2: structured body template -------------------------------------


from plan_tool.create import PLAN_BODY_SECTIONS, _render_plan_body


class TestRenderPlanBody:
    def test_starts_with_h1_title(self) -> None:
        out = _render_plan_body("My Plan")
        assert out.startswith("# My Plan\n")

    def test_contains_every_section(self) -> None:
        out = _render_plan_body("X")
        for section in PLAN_BODY_SECTIONS:
            assert f"## {section}" in out

    def test_steps_section_points_at_frontmatter(self) -> None:
        out = _render_plan_body("X")
        assert "See the `steps:` block" in out

    def test_explicit_references_body_overrides_seed_and_link_rows(self) -> None:
        from plan_tool.create import Reference

        out = _render_plan_body(
            "X",
            references=[Reference("Vendor docs", "https://example.com/docs", None)],
            references_body=_ROADMAP_NO_SOURCE_REFERENCES_BODY,
            seed_sections={"references": "seed references"},
        )

        references = out.split("## References\n\n", 1)[1].split("## Steps", 1)[0]
        assert references.strip() == _ROADMAP_NO_SOURCE_REFERENCES_BODY

    def test_other_sections_get_todo_placeholder(self) -> None:
        out = _render_plan_body("X")
        # Overview, Problem statement, Architecture, etc. all get _(TODO)_.
        # There are 8 such sections (PLAN_BODY_SECTIONS minus "Steps").
        assert out.count("_(TODO)_") == len(PLAN_BODY_SECTIONS) - 1

    def test_unrelated_plan_omits_input_section(self) -> None:
        out = _render_plan_body("X")
        assert "## Input" not in out

    def test_contract_consuming_plan_renders_input_section(self) -> None:
        out = _render_plan_body(
            "X",
            synthesized_sections={
                "Input": (
                    "Reads `audit.json` and depends on the `status` field."
                )
            },
        )
        assert out.count("## Input") == 1
        assert "Reads `audit.json`" in out
        assert out.index("## Architecture") < out.index("## Input")
        assert out.index("## Input") < out.index("## References")

        from_seed = _render_plan_body(
            "X",
            seed_sections={"input": "Reads the persisted schema sidecar."},
        )
        assert from_seed.count("## Input") == 1
        assert "persisted schema sidecar" in from_seed

    def test_render_plan_body_keeps_supplied_guardrails_separate(self) -> None:
        guardrails = {
            "Scope guardrails": "SCOPE_SEED_BODY",
            "Audit guardrails": "AUDIT_SEED_BODY",
            "Expected placement": "PLACEMENT_SEED_BODY",
            "Stack": "STACK_SEED_BODY",
        }
        out = _render_plan_body(
            "X",
            supplied_guardrails=guardrails,
            synthesized_sections={
                "Scope guardrails": "MODEL_SCOPE_BODY",
                "Audit guardrails": "MODEL_AUDIT_BODY",
                "Expected placement": "MODEL_PLACEMENT_BODY",
                "Stack": "MODEL_STACK_BODY",
            },
        )
        for heading, supplied_body in guardrails.items():
            assert out.count(f"## {heading}") == 1
            assert supplied_body in out
            assert f"MODEL_{heading.split()[0].upper()}_BODY" not in out
        assert out.index("## Architecture") < out.index("## Scope guardrails")
        assert out.index("## Stack") < out.index("## References")

    def test_stack_body_is_preserved_verbatim_through_create(self) -> None:
        # The seed's ``## Stack`` replaces whatever the model wrote for it.
        seed = "## Stack\n\n| Layer | Choice |\n| --- | --- |\n| Store | PostgreSQL |\n"
        from plan_tool.create import _extract_supplied_guardrails

        supplied = _extract_supplied_guardrails(seed)
        out = _render_plan_body(
            "X",
            supplied_guardrails=supplied,
            synthesized_sections={"Stack": "SQLite on a laptop."},
        )

        assert supplied == {"Stack": "| Layer | Choice |\n| --- | --- |\n| Store | PostgreSQL |"}
        assert out.count("## Stack") == 1
        assert supplied["Stack"] in out
        assert "SQLite" not in out

    def test_seed_without_stack_produces_no_stack_section_in_the_plan(
        self,
    ) -> None:
        # Absent section: no heading and no ``_(TODO)_`` stub is written.
        from plan_tool.create import _extract_supplied_guardrails

        seed = "## Scope guardrails\n\nKeep the CLI stable.\n"
        out = _render_plan_body(
            "X",
            supplied_guardrails=_extract_supplied_guardrails(seed),
            synthesized_sections={"Stack": "MODEL_STACK_BODY"},
        )

        assert "## Stack" not in out
        assert "MODEL_STACK_BODY" not in out

    def test_stack_is_captured_before_distillation_and_not_invented_by_it(
        self,
    ) -> None:
        from plan_tool.create import (
            _extract_supplied_guardrails,
            _find_dropped_guardrail_headings,
            _find_uncarried_guardrail_headings,
        )

        with_stack = _extract_supplied_guardrails("## Stack\n\nPostgreSQL.\n")
        without_stack = _extract_supplied_guardrails("## Scope guardrails\n\nX.\n")

        # A stage output that drops a seed ``Stack`` is reported as dropped.
        assert _find_dropped_guardrail_headings(with_stack, set()) == ["Stack"]
        # A stage output that invents a ``Stack`` the seed lacks is uncarried.
        assert _find_uncarried_guardrail_headings(
            without_stack, {"Stack": "SQLite."}
        ) == ["Stack"]

    def test_seed_without_guardrails_does_not_render_guardrail_headings(self) -> None:
        out = _render_plan_body("X")
        for heading in (
            "Scope guardrails", "Audit guardrails", "Expected placement", "Stack"
        ):
            assert f"## {heading}" not in out

    def test_guardrail_atx_closing_sequence_is_preserved(self) -> None:
        from plan_tool.create import _extract_supplied_guardrails

        supplied = _extract_supplied_guardrails(
            "## Audit guardrails ##\n\nKeep audit output stable.\n"
        )
        out = _render_plan_body("X", supplied_guardrails=supplied)

        assert supplied == {"Audit guardrails": "Keep audit output stable."}
        assert out.count("## Audit guardrails") == 1
        assert "Keep audit output stable." in out

    def test_ends_with_trailing_newline(self) -> None:
        out = _render_plan_body("X")
        assert out.endswith("\n")
        assert not out.endswith("\n\n")  # exactly one trailing newline


from plan_tool.create import (  # noqa: E402
    _find_placeholder_body_sections,
    _render_section_shapes_block,
    _render_testing_strategy,
)


def _testing_section_body(rendered: str) -> str:
    """Lift the prose under ``## Testing`` from a rendered plan body."""
    from plan_tool.create import extract_h2_sections

    return extract_h2_sections(rendered)["testing"]


class TestTestingStrategyEnumeration:
    """The per-step test-strategy block appended to ``## Testing`` and its
    interaction with the synthesized ≻ seed ≻ ``_(TODO)_`` ladder."""

    def test_render_testing_strategy_none_when_no_classified(self) -> None:
        assert _render_testing_strategy([Step(id=1, title="s")]) is None

    def test_render_testing_strategy_enumerates_each_type(self) -> None:
        block = _render_testing_strategy(
            [
                Step(id=1, title="r", change_type=ChangeType.REFACTOR),
                Step(id=2, title="f", change_type=ChangeType.FEATURE),
                Step(id=3, title="n", change_type=ChangeType.NON_CODE),
            ]
        )
        assert block is not None
        bullets = [ln for ln in block.splitlines() if ln.startswith("- ")]
        # One bullet per change_type keeps every id paired with its own type.
        assert len(bullets) == 3
        assert "step 1 (refactor)" in block
        assert "step 2 (feature)" in block
        assert "step 3 (non-code)" in block
        assert "verification appropriate" in block
        # Both code types carry the same strategy — the per-type ordering
        # contract was withdrawn (BACKLOG #204).
        assert block.count("tests covering the behavior a step changes") == 2
        assert "characterization" not in block

    def test_render_testing_strategy_groups_steps_sharing_a_strategy_without_dropping_any(
        self,
    ) -> None:
        """Steps of one change_type collapse into one bullet for readability;
        every step id must still appear, and an unclassified step is never
        merged into a classified group (it carries no directive)."""
        block = _render_testing_strategy(
            [
                Step(id=1, title="a", change_type=ChangeType.FEATURE),
                Step(id=2, title="b", change_type=ChangeType.FEATURE),
                Step(id=3, title="c"),
                Step(id=4, title="d", change_type=ChangeType.FEATURE),
            ]
        )
        assert block is not None
        bullets = [ln for ln in block.splitlines() if ln.startswith("- ")]
        assert bullets[0].startswith("- steps 1, 2, 4 (feature) — ")
        assert bullets[1] == "- step 3 — unclassified; no per-step test directive."
        assert len(bullets) == 2

    def test_render_testing_strategy_orders_bullets_by_first_step_id(self) -> None:
        """A reader scanning for a step id finds its bullet in plan order, not
        grouped-by-type order with unclassified steps always last."""
        block = _render_testing_strategy(
            [
                Step(id=1, title="a", change_type=ChangeType.NON_CODE),
                Step(id=2, title="b", change_type=ChangeType.FEATURE),
                Step(id=3, title="c"),
                Step(id=4, title="d", change_type=ChangeType.NON_CODE),
            ]
        )
        assert block is not None
        bullets = [ln for ln in block.splitlines() if ln.startswith("- ")]
        assert [b.split(" — ")[0] for b in bullets] == [
            "- steps 1, 4 (non-code)",
            "- step 2 (feature)",
            "- step 3",
        ]

    def test_render_testing_strategy_partial_lists_unclassified(self) -> None:
        block = _render_testing_strategy(
            [
                Step(id=1, title="f", change_type=ChangeType.FEATURE),
                Step(id=2, title="u"),
            ]
        )
        assert block is not None
        assert "step 1 (feature)" in block
        assert "step 2 — unclassified" in block

    def test_render_plan_body_unclassified_steps_unchanged(self) -> None:
        # The no-arg call is the real default; comparing against it pins
        # the byte-identical invariant without re-encoding the expected body.
        assert _render_plan_body(
            "X", steps=[Step(id=1, title="s")]
        ) == _render_plan_body("X")

    def test_render_plan_body_appends_enumeration_below_synthesized_testing(
        self,
    ) -> None:
        prose = "SYNTH_TESTING_PROSE"
        out = _render_plan_body(
            "X",
            synthesized_sections={"Testing": prose},
            steps=[Step(id=1, title="s", change_type=ChangeType.REFACTOR)],
        )
        body = _testing_section_body(out)
        assert prose in body
        assert "Per-step test strategy" in body
        assert body.index(prose) < body.index("Per-step test strategy")

    def test_render_plan_body_appends_enumeration_below_seed_testing(
        self,
    ) -> None:
        prose = "SEED_TESTING_PROSE"
        out = _render_plan_body(
            "X",
            seed_sections={"testing": prose},
            steps=[Step(id=1, title="s", change_type=ChangeType.FEATURE)],
        )
        body = _testing_section_body(out)
        assert prose in body
        assert "Per-step test strategy" in body
        assert body.index(prose) < body.index("Per-step test strategy")

    def test_render_plan_body_enumeration_replaces_placeholder_when_no_prose(
        self,
    ) -> None:
        out = _render_plan_body(
            "X",
            steps=[Step(id=1, title="s", change_type=ChangeType.REFACTOR)],
        )
        body = _testing_section_body(out)
        assert "Per-step test strategy" in body
        assert "_(TODO)_" not in body
        # A sibling section with no prose still renders the placeholder.
        from plan_tool.create import extract_h2_sections

        assert extract_h2_sections(out)["overview"].strip() == "_(TODO)_"

    def test_render_plan_body_testing_placeholder_when_no_classified(
        self,
    ) -> None:
        out = _render_plan_body("X", steps=[Step(id=1, title="s")])
        assert _testing_section_body(out).strip() == "_(TODO)_"

    def test_section_shapes_block_documents_per_step_enumeration(self) -> None:
        block = _render_section_shapes_block()
        testing_bullet = next(
            ln for ln in block.splitlines() if ln.startswith("- **Testing**")
        )
        assert "change_type" in testing_bullet
        assert "per-step" in testing_bullet

    def test_section_shapes_block_documents_conditional_input(self) -> None:
        block = _render_section_shapes_block()
        input_bullet = next(
            ln for ln in block.splitlines() if ln.startswith("- **Input**")
        )
        assert "_[conditional]_" in input_bullet
        assert "existing contract" in input_bullet
        assert "Omit this section" in input_bullet

    def test_section_shapes_block_tags_each_bullet_with_policy(self) -> None:
        """Every catalog bullet carries its derive/evidence policy tag, keyed
        off ``_DERIVE_FROM_INTENT_SECTIONS`` — the one source both the distill
        and synthesis prompts steer by."""
        from plan_tool.create import _DERIVE_FROM_INTENT_SECTIONS

        block = _render_section_shapes_block()
        bullets = {
            ln.split("**")[1]: ln
            for ln in block.splitlines()
            if ln.startswith("- **")
        }
        assert bullets, "shapes block produced no bullets"
        for section, bullet in bullets.items():
            if section in {
                "Input", "Scope guardrails", "Audit guardrails",
                "Expected placement", "Stack",
            }:
                continue
            expected = (
                "_[derive from intent]_"
                if section in _DERIVE_FROM_INTENT_SECTIONS
                else "_[evidence-only]_"
            )
            assert expected in bullet, f"{section} missing {expected}"
        # The narrative-from-goal sections are the derive set; a fabrication-
        # prone section (Risks) stays evidence-only.
        assert "_[derive from intent]_" in bullets["Overview"]
        assert "_[evidence-only]_" in bullets["Risks"]


class TestWriteNewPlanBody:
    def test_written_plan_has_section_skeleton(self, tmp_path: Path) -> None:
        plan = Plan(
            title="My Plan",
            status=PlanStatus.PLANNING,
            priority=Priority.MEDIUM,
            steps=[Step(id=1, title="s")],
        )
        path = write_new_plan(tmp_path, "demo", plan)
        body = path.read_text(encoding="utf-8")
        for section in PLAN_BODY_SECTIONS:
            assert f"## {section}" in body

    def test_written_plan_is_round_trippable(self, tmp_path: Path) -> None:
        """Skeleton body must survive parse_plan + write_plan."""
        plan = Plan(
            title="My Plan",
            status=PlanStatus.PLANNING,
            priority=Priority.MEDIUM,
            steps=[Step(id=1, title="s")],
        )
        path = write_new_plan(tmp_path, "demo", plan)
        # Should not raise.
        reloaded = parse_plan(path)
        assert reloaded.title == "My Plan"

    def test_write_new_plan_threads_steps_into_testing(
        self, tmp_path: Path
    ) -> None:
        """A classified-step plan's written Testing section carries the
        per-step enumeration."""
        plan = Plan(
            title="My Plan",
            status=PlanStatus.PLANNING,
            priority=Priority.MEDIUM,
            steps=[
                Step(id=1, title="r", change_type=ChangeType.REFACTOR),
                Step(id=2, title="f", change_type=ChangeType.FEATURE),
            ],
        )
        path = write_new_plan(tmp_path, "demo", plan)
        body = path.read_text(encoding="utf-8")
        assert "Per-step test strategy" in body
        assert "step 1 (refactor)" in body
        assert "step 2 (feature)" in body

    def test_write_new_plan_preserves_normalized_testing_on_initial_write(
        self, tmp_path: Path
    ) -> None:
        """Normalized source evidence must not gain generated Testing prose."""
        plan = Plan(
            title="My Plan",
            status=PlanStatus.PLANNING,
            priority=Priority.MEDIUM,
            steps=[Step(id=1, title="f", change_type=ChangeType.FEATURE)],
        )
        path = write_new_plan(
            tmp_path,
            "normalized",
            plan,
            synthesized_sections={"Testing": "SOURCE_TESTING_EVIDENCE"},
            normalized_preparation_sections={"Testing": "SOURCE_TESTING_EVIDENCE"},
        )

        body = _testing_section_body(path.read_text(encoding="utf-8"))
        assert body.strip() == "SOURCE_TESTING_EVIDENCE"
        assert "Per-step test strategy" not in body


# --- Code-review fixes ----------------------------------------------------


@pytest.mark.integration
class TestCheckCollisionLegacyPrefixes:
    """Collision detection must also catch legacy multi-digit prefixes left
    on disk from earlier numbering schemes (4, 5, 6, …, 12, …) so we don't
    silently overwrite a slug that already occupies a non-priority slot.
    """

    def test_detects_collision_at_legacy_prefix(self, tmp_path: Path) -> None:
        (tmp_path / "5-foo.md").write_text("x", encoding="utf-8")
        with pytest.raises(FileExistsError, match="foo"):
            check_collision(tmp_path, "foo")

    def test_detects_collision_at_double_digit_prefix(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "12-foo.md").write_text("x", encoding="utf-8")
        with pytest.raises(FileExistsError, match="foo"):
            check_collision(tmp_path, "foo")

    def test_no_false_match_on_suffix_at_legacy_prefix(
        self, tmp_path: Path
    ) -> None:
        """`5-foo-bar.md` must not collide with slug `bar` (regression of
        the original glob fix, now under the regex-based check)."""
        (tmp_path / "5-foo-bar.md").write_text("x", encoding="utf-8")
        check_collision(tmp_path, "bar")  # must not raise

    def test_create_plan_refuses_duplicate_at_legacy_prefix(
        self, tmp_path: Path
    ) -> None:
        """End-to-end: the wizard refuses when a slug already lives at a
        legacy prefix outside the priority-bucket range."""
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        (out_dir / "5-existing.md").write_text("x", encoding="utf-8")
        manifest = tmp_path / "m.json"

        with pytest.raises(FileExistsError, match="existing"):
            create_plan(
                "existing",
                repo_root=tmp_path,
                output_dir_override=out_dir,
                manifest_path=manifest,
                input_fn=_queue_input([]),  # never consumed
                replace_on_collision=False,
            )


# --- Step 4: canonical-layout extraction ----------------------------------


from plan_tool.create import extract_steps_from_canonical


_CANONICAL_BODY = (
    "# Sample Plan\n"
    "\n"
    "## Overview\n"
    "\n"
    "Some prose.\n"
    "\n"
    "## Steps\n"
    "\n"
    "### 1. First step\n"
    "\n"
    "Files:\n"
    "- `apps/web/foo.ts`\n"
    "- `apps/web/bar.ts`\n"
    "\n"
    "### 2. Second step\n"
    "\n"
    "Files:\n"
    "- `apps/web/baz.ts`\n"
    "\n"
    "Depends on: 1\n"
    "\n"
    "## Acceptance criteria\n"
    "\n"
    "- All tests pass.\n"
    "\n"
    "## References\n"
    "\n"
    "- [Canonical API](https://example.test/canonical)\n"
)


class TestParseStepsJsonChangeType:
    """``_parse_steps_json`` parses ``change_type`` leniently — unknown or
    missing values coerce to ``None`` and never reject the proposal, the
    deliberate opposite of the sibling ``complexity`` field."""

    def test_refactor_feature_non_code_parse(self) -> None:
        raw = json.dumps(
            [
                {"title": "Restructure", "change_type": "refactor"},
                {"title": "Add behavior", "change_type": "feature"},
                {"title": "Wire CI", "change_type": "non-code"},
            ]
        )
        steps = _parse_steps_json(raw)
        assert steps is not None
        assert [s.change_type for s in steps] == [
            ChangeType.REFACTOR,
            ChangeType.FEATURE,
            ChangeType.NON_CODE,
        ]

    def test_missing_change_type_is_none(self) -> None:
        steps = _parse_steps_json(json.dumps([{"title": "No type key"}]))
        assert steps is not None
        assert steps[0].change_type is None

    def test_null_change_type_is_none(self) -> None:
        raw = json.dumps([{"title": "Null type", "change_type": None}])
        steps = _parse_steps_json(raw)
        assert steps is not None
        assert steps[0].change_type is None

    def test_non_string_change_type_is_none(self) -> None:
        raw = json.dumps(
            [
                {"title": "Numeric", "change_type": 3},
                {"title": "List", "change_type": ["refactor"]},
            ]
        )
        steps = _parse_steps_json(raw)
        assert steps is not None
        assert [s.change_type for s in steps] == [None, None]

    def test_unknown_change_type_coerces_to_none(self) -> None:
        """An unrecognized ``change_type`` string yields ``None`` and the
        loop continues — whereas an invalid ``complexity`` rejects the
        entire proposal. The asymmetry is the point."""
        unknown_ct = _parse_steps_json(
            json.dumps([{"title": "Chore step", "change_type": "chore"}])
        )
        assert unknown_ct is not None
        assert unknown_ct[0].change_type is None

        invalid_cx = _parse_steps_json(
            json.dumps([{"title": "Bad complexity", "complexity": "epic"}])
        )
        assert invalid_cx is None

    def test_rationale_key_ignored(self) -> None:
        raw = json.dumps(
            [
                {
                    "title": "Defended step",
                    "change_type": "feature",
                    "rationale": "purely new behavior; no restructuring",
                }
            ]
        )
        steps = _parse_steps_json(raw)
        assert steps is not None
        assert steps[0].change_type is ChangeType.FEATURE
        assert not hasattr(steps[0], "rationale")


class TestExtractStepsFromCanonical:
    def test_happy_path_returns_steps(self) -> None:
        steps = extract_steps_from_canonical(_CANONICAL_BODY)
        assert steps is not None
        assert [s.id for s in steps] == [1, 2]
        assert [s.title for s in steps] == ["First step", "Second step"]
        assert steps[0].files == ["apps/web/foo.ts", "apps/web/bar.ts"]
        assert steps[0].depends_on == []
        assert steps[1].files == ["apps/web/baz.ts"]
        assert steps[1].depends_on == [1]

    def test_steps_validate_as_plan(self) -> None:
        """Extracted steps must satisfy Plan's schema (sequential ids,
        well-formed depends_on graph), or they're useless to create_plan."""
        steps = extract_steps_from_canonical(_CANONICAL_BODY)
        assert steps is not None
        Plan(
            title="x",
            status=PlanStatus.PLANNING,
            priority=Priority.LOW,
            steps=steps,
        )

    def test_no_steps_h2_returns_none(self) -> None:
        text = (
            "# Free-form Notes\n\n"
            "Some narrative without a Steps section.\n"
        )
        assert extract_steps_from_canonical(text) is None

    def test_drift_extra_blank_line_returns_none(self) -> None:
        """An extra blank line between the H2 and the first step breaks
        the strict round-trip; fall back rather than half-guess."""
        drifted = _CANONICAL_BODY.replace(
            "## Steps\n\n### 1.", "## Steps\n\n\n### 1."
        )
        assert extract_steps_from_canonical(drifted) is None

    def test_drift_non_canonical_heading_returns_none(self) -> None:
        """The Phase-style heading form is recognized by ``parse_source``
        but NOT by the strict reader; falls back to Claude."""
        text = (
            "## Steps\n\n"
            "### Phase 1 — First step\n\n"
            "Files:\n- `a.ts`\n"
        )
        assert extract_steps_from_canonical(text) is None

    def test_drift_prose_between_files_and_next_step(self) -> None:
        """Mid-section prose isn't canonical; round-trip check rejects."""
        text = (
            "## Steps\n\n"
            "### 1. First\n\n"
            "Files:\n- `a.ts`\n\n"
            "Some explanatory prose.\n\n"
            "### 2. Second\n"
        )
        assert extract_steps_from_canonical(text) is None

    def test_strips_frontmatter_before_extracting(self) -> None:
        text = (
            "---\n"
            "title: stub\n"
            "---\n"
            + _CANONICAL_BODY
        )
        steps = extract_steps_from_canonical(text)
        assert steps is not None
        assert [s.title for s in steps] == ["First step", "Second step"]

    def test_steps_only_doc(self) -> None:
        """No title, no overview, no acceptance — just ``## Steps``."""
        text = (
            "## Steps\n\n"
            "### 1. Only step\n"
        )
        steps = extract_steps_from_canonical(text)
        assert steps is not None
        assert [s.title for s in steps] == ["Only step"]
        assert steps[0].files == []
        assert steps[0].creates == []
        assert steps[0].depends_on == []

    def test_creates_block_after_files(self) -> None:
        """A ``Creates:`` block (new files) parses alongside ``Files:``,
        in the canonical Files → Creates → Depends on order."""
        text = (
            "## Steps\n\n"
            "### 1. Modify and add\n\n"
            "Files:\n- `existing.py`\n\n"
            "Creates:\n- `pkg/new_a.py`\n- `pkg/new_b.py`\n\n"
            "Depends on: \n"
        ).replace("\n\nDepends on: \n", "\n")  # drop empty depends line
        steps = extract_steps_from_canonical(text)
        assert steps is not None
        assert steps[0].files == ["existing.py"]
        assert steps[0].creates == ["pkg/new_a.py", "pkg/new_b.py"]
        # Merged footprint exposes both, files first.
        assert steps[0].all_files == ["existing.py", "pkg/new_a.py", "pkg/new_b.py"]

    def test_creates_only_step(self) -> None:
        """A step with only a ``Creates:`` block (no ``Files:``) round-trips."""
        text = (
            "## Steps\n\n"
            "### 1. Brand new module\n\n"
            "Creates:\n- `pkg/brand_new.py`\n"
        )
        steps = extract_steps_from_canonical(text)
        assert steps is not None
        assert steps[0].files == []
        assert steps[0].creates == ["pkg/brand_new.py"]

    def test_drift_creates_before_files_returns_none(self) -> None:
        """Canonical order is Files → Creates; reversing them fails the
        byte-exact round-trip and falls back to the Claude path."""
        text = (
            "## Steps\n\n"
            "### 1. Wrong order\n\n"
            "Creates:\n- `pkg/new.py`\n\n"
            "Files:\n- `existing.py`\n"
        )
        assert extract_steps_from_canonical(text) is None

    def test_change_type_copied_from_canonical(self) -> None:
        """A canonical ``Type: refactor`` line lands as the matching
        ``ChangeType`` enum on the extracted step."""
        text = (
            "## Steps\n\n"
            "### 1. Restructure\n\n"
            "Type: refactor\n\n"
            "Files:\n- `pkg/mod.py`\n"
        )
        steps = extract_steps_from_canonical(text)
        assert steps is not None
        assert steps[0].change_type == ChangeType.REFACTOR

    def test_change_type_none_when_type_line_absent(self) -> None:
        """The ``Type:``-less ``_CANONICAL_BODY`` yields ``None`` for every
        step's ``change_type``."""
        steps = extract_steps_from_canonical(_CANONICAL_BODY)
        assert steps is not None
        assert all(s.change_type is None for s in steps)


from plan_tool.canonical import extract_canonical_steps


class TestCanonicalChangeType:
    """Direct ``extract_canonical_steps`` coverage for the optional
    ``Type:`` line that lands in ``CanonicalStep.change_type``."""

    def test_type_line_parsed_into_change_type(self) -> None:
        text = (
            "## Steps\n\n"
            "### 1. First step\n\n"
            "Type: refactor\n\n"
            "Files:\n- `a.py`\n"
        )
        steps = extract_canonical_steps(text)
        assert steps is not None
        assert steps[0].change_type == "refactor"

    def test_all_three_type_values_extracted(self) -> None:
        text = (
            "## Steps\n\n"
            "### 1. Refactor step\n\n"
            "Type: refactor\n\n"
            "### 2. Feature step\n\n"
            "Type: feature\n\n"
            "### 3. Docs step\n\n"
            "Type: non-code\n"
        )
        steps = extract_canonical_steps(text)
        assert steps is not None
        assert [s.change_type for s in steps] == ["refactor", "feature", "non-code"]

    def test_no_type_line_leaves_change_type_none(self) -> None:
        steps = extract_canonical_steps(_CANONICAL_BODY)
        assert steps is not None
        assert all(s.change_type is None for s in steps)

    def test_type_line_round_trips(self) -> None:
        text = (
            "## Steps\n\n"
            "### 1. First step\n\n"
            "Type: feature\n\n"
            "Files:\n- `a.py`\n"
        )
        steps = extract_canonical_steps(text)
        assert steps is not None
        assert steps[0].change_type == "feature"

    def test_invalid_type_value_falls_back_to_none(self) -> None:
        text = (
            "## Steps\n\n"
            "### 1. First step\n\n"
            "Type: chore\n\n"
            "Files:\n- `a.py`\n"
        )
        assert extract_canonical_steps(text) is None

    def test_type_line_wrong_position_falls_back(self) -> None:
        # ``Type:`` after ``Files:`` (not first-under-heading) fails the
        # byte-exact round-trip — the renderer emits it first.
        text = (
            "## Steps\n\n"
            "### 1. First step\n\n"
            "Files:\n- `a.py`\n\n"
            "Type: refactor\n"
        )
        assert extract_canonical_steps(text) is None


@pytest.mark.integration
class TestCreatePlanFromCanonicalSource:
    """Integration: when ``from_description`` carries a canonical body, the
    Claude step-proposal path is skipped and the extracted steps land
    directly in the new plan. Claude is still invoked once for
    References research (always-on); the test verifies it was NOT asked
    to propose steps.
    """

    def test_canonical_source_skips_claude_step_proposal(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        prompts_seen: list[str] = []

        def recording_invoker(prompt: str) -> str:
            prompts_seen.append(prompt)
            if "Distill a free-form seed" in prompt:
                return _valid_preparation_response(prompt)
            if "Synthesize plan body sections" in prompt:
                return _SYNTHESIS_NULL_JSON
            return "[]"  # no references; canonical extraction supplies steps

        answers = _basic_metadata_answers()
        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description=_CANONICAL_BODY,
            input_fn=_queue_input(answers),
            claude_invoker=recording_invoker,
        )

        plan = parse_plan(result.plan_path)
        assert [s.title for s in plan.steps] == ["First step", "Second step"]
        assert plan.steps[0].files == ["apps/web/foo.ts", "apps/web/bar.ts"]
        assert plan.steps[1].depends_on == [1]
        # Two claude calls — references + body-sections synthesis —
        # but never the step-proposal call (canonical extraction supplies
        # steps deterministically). The synthesis call fires because
        # ``_CANONICAL_BODY`` has only a subset of the canonical body
        # H2s, so the canonical-skip optimization does not engage.
        assert len(prompts_seen) == 2
        for prompt in prompts_seen:
            assert "Propose an initial plan step-list" not in prompt
        refs_prompts = [
            p for p in prompts_seen
            if "developer and API reference documentation" in p
        ]
        synth_prompts = [
            p for p in prompts_seen
            if "Synthesize plan body sections" in p
        ]
        assert len(refs_prompts) == 1
        assert len(synth_prompts) == 1

    def test_no_steps_h2_falls_back_silently(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A source with no ``## Steps`` was never canonical — silent fallback
        to the existing Claude path, no warning printed."""
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        canned = json.dumps(
            [{"title": "from claude", "complexity": None, "files": [],
              "depends_on": []}]
        )
        answers = _basic_metadata_answers()

        create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="Just some free-form notes, no Steps section.\n",
            input_fn=_queue_input(answers),
            claude_invoker=lambda prompt: (
                _valid_preparation_response(prompt)
                if "Distill a free-form seed" in prompt
                else canned
            ),
        )

        captured = capsys.readouterr()
        # No '## Steps' marker on this source → silent fall-through to
        # Claude (the wizard only narrates the canonical-shape miss when
        # the source obviously tried to be canonical).
        assert "doesn't match the canonical shape" not in captured.err
        assert "doesn't match the canonical shape" not in captured.out

    def test_drifted_canonical_warns_then_falls_back(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A source that obviously *tried* to be canonical (has ``## Steps``)
        but failed strict extraction must emit a non-silent notice naming
        the source path before falling back to Claude. The notice is
        informational — `create` is itself the canonical-conversion
        flow, so it must NOT recommend any extra user command."""
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"
        source_path = tmp_path / "drifted.md"
        # Extra blank line between H2 and first step → fails strict.
        drifted = _CANONICAL_BODY.replace(
            "## Steps\n\n### 1.", "## Steps\n\n\n### 1."
        )
        source_path.write_text(drifted, encoding="utf-8")

        canned = json.dumps(
            [{"title": "from claude", "complexity": None, "files": [],
              "depends_on": []}]
        )
        answers = _basic_metadata_answers()

        create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description=drifted,
            from_existing_path=source_path,
            input_fn=_queue_input(answers),
            claude_invoker=lambda prompt: (
                _valid_preparation_response(prompt)
                if "Distill a free-form seed" in prompt
                else canned
            ),
        )

        err = capsys.readouterr().err
        assert "Distilling seed" in err
        # `create` is itself the canonical-conversion flow — the notice
        # describes what the wizard is doing, it does not ask the user
        # to run another command. Guarding against regressing back to
        # the old "Run 'plan-tool reformat' first" recommendation.
        assert "plan-tool reformat" not in err

    def test_canonical_via_cli_end_to_end(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """End-to-end through ``cli.main``: a canonical source on disk feeds
        into ``create --from-existing``. Claude is invoked once (for
        References research) but never for step proposal. Exercises the
        CLI's ``from_existing_path`` plumbing."""
        from plan_tool.cli import app as cli_module
        from plan_tool.cli import context as cli_context

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"
        source = tmp_path / "canonical.md"
        source.write_text(_CANONICAL_BODY, encoding="utf-8")

        prompts_seen: list[str] = []

        def recording_invoker(prompt: str) -> str:
            prompts_seen.append(prompt)
            if "Distill a free-form seed" in prompt:
                return _valid_preparation_response(prompt)
            if "Synthesize plan body sections" in prompt:
                return _SYNTHESIS_NULL_JSON
            if "Propose an initial plan step-list" in prompt:
                return json.dumps(
                    [
                        {"title": "First step", "files": [], "depends_on": []},
                        {"title": "Second step", "files": [], "depends_on": [1]},
                    ]
                )
            return "[]"

        original_create_plan = cli_module.create_plan
        answers = _basic_metadata_answers()

        def patched(*args, **kwargs):
            kwargs.setdefault("input_fn", _queue_input(answers))
            kwargs["claude_invoker"] = recording_invoker
            return original_create_plan(*args, **kwargs)

        monkeypatch.setattr("plan_tool.cli.authoring.create_plan", patched)
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "create", "demo",
                "--from-existing", str(source),
                "--output-dir", str(out_dir),
                "--no-distill",
                "--no-iterate",
            ]
        )
        assert rc == 0
        plan = parse_plan(out_dir / "2-demo.md")
        assert [s.title for s in plan.steps] == ["First step", "Second step"]
        assert plan.steps[1].depends_on == [1]
        assert any("Distill a free-form seed" in prompt for prompt in prompts_seen)
        assert any("Propose an initial plan step-list" in prompt for prompt in prompts_seen)


class TestSourceSeedProvenance:
    """``Plan.source_seed`` (BACKLOG #162) — written only by ``create
    --from-existing`` when the input path resolves to a readable file
    inside the repo; unset otherwise. Feeds the audit's scope-contract
    block (see ``TestFormatScopeContractBlock`` in ``tests/test_review.py``).
    """

    def _create(
        self,
        tmp_path: Path,
        *,
        from_existing_path: Path | None,
        from_description: str | None = None,
    ):
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"
        answers = _basic_metadata_answers()
        canned = json.dumps(
            [{"title": "a step", "complexity": None, "files": [],
              "depends_on": []}]
        )
        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description=from_description,
            from_existing_path=from_existing_path,
            input_fn=_queue_input(answers),
            claude_invoker=lambda prompt: (
                _valid_preparation_response(prompt)
                if "Distill a free-form seed" in prompt
                else canned
            ),
        )
        return parse_plan(result.plan_path)

    def test_source_seed_set_to_repo_relative_path(self, tmp_path: Path) -> None:
        source = tmp_path / "notes.md"
        source.write_text(
            "# Notes\n\nRefactor the auth module.\n\n"
            "## References\n\n- [API](https://example.test/api)\n",
            encoding="utf-8",
        )

        plan = self._create(
            tmp_path,
            from_existing_path=source,
            from_description=source.read_text(encoding="utf-8"),
        )

        assert plan.source_seed == "notes.md"

    def test_source_seed_set_to_repo_relative_path_in_subdir(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "plan-seeds").mkdir()
        source = tmp_path / "plan-seeds" / "notes.md"
        source.write_text(
            "# Notes\n\nRefactor the auth module.\n\n"
            "## References\n\n- [API](https://example.test/api)\n",
            encoding="utf-8",
        )

        plan = self._create(
            tmp_path,
            from_existing_path=source,
            from_description=source.read_text(encoding="utf-8"),
        )

        assert plan.source_seed == "plan-seeds/notes.md"

    def test_source_seed_unset_for_blank_skeleton(self, tmp_path: Path) -> None:
        plan = self._create(
            tmp_path,
            from_existing_path=None,
            from_description="A plan with no originating seed file.",
        )

        assert plan.source_seed is None

    def test_source_seed_unset_when_path_outside_repo(
        self, tmp_path: Path, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        outside = tmp_path_factory.mktemp("outside-repo")
        source = outside / "notes.md"
        source.write_text(
            "# Notes\n\nRefactor the auth module.\n\n"
            "## References\n\n- [API](https://example.test/api)\n",
            encoding="utf-8",
        )

        plan = self._create(
            tmp_path,
            from_existing_path=source,
            from_description=source.read_text(encoding="utf-8"),
        )

        assert plan.source_seed is None

    def test_source_seed_survives_the_cli_archiving_its_own_seed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The CLI (``cli/authoring.py``, not ``create_plan`` itself)
        unconditionally archives a ``--from-existing`` seed right after
        publishing the new plan — the common case, not an edge case. This
        pins the full real chain end to end: ``plan.source_seed`` still
        names the pre-archival path, the seed is genuinely gone from there,
        and ``_format_scope_contract_block`` still resolves real content
        through :func:`plan_tool.pathutil.latest_seed_archive`'s fallback."""
        from plan_tool.cli import app as cli_module
        from plan_tool.review import _format_scope_contract_block

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"
        source = tmp_path / "notes.md"
        source.write_text(
            "# Plan seed: demo\n\n"
            "## Outcome\n\nShip the demo feature end to end.\n\n"
            "## References\n\n- [API](https://example.test/api)\n",
            encoding="utf-8",
        )

        def fake_invoker(prompt: str) -> str:
            if "Distill a free-form seed" in prompt:
                return _valid_preparation_response(prompt)
            return json.dumps(
                [{"title": "a step", "complexity": None, "files": [],
                  "depends_on": []}]
            )

        original_create_plan = cli_module.create_plan
        answers = _basic_metadata_answers()

        def patched(*args, **kwargs):
            kwargs.setdefault("input_fn", _queue_input(answers))
            kwargs["claude_invoker"] = fake_invoker
            return original_create_plan(*args, **kwargs)

        monkeypatch.setattr("plan_tool.cli.authoring.create_plan", patched)
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "create", "demo",
                "--from-existing", str(source),
                "--output-dir", str(out_dir),
                "--no-distill",
                "--no-iterate",
            ]
        )
        assert rc == 0
        assert not source.exists()

        plan = parse_plan(out_dir / "2-demo.md")
        assert plan.source_seed == "notes.md"

        block = _format_scope_contract_block(plan, tmp_path)
        assert "Ship the demo feature end to end." in block


# --- Provenance plumbing: plan-details rename + original-seed archival ----


from plan_tool.create import (
    rename_plan_details_to_slug,
    resolve_existing_plan_details,
)
from plan_tool.canonical import CanonicalProvenance


def _canonical_with_provenance(
    *, source_name: str, plan_details: str | None
) -> str:
    """Build canonical markdown with a provenance frontmatter block.

    Hand-built (previously used `render_canonical` from the removed
    `reformat` module; see BACKLOG #40). The body matches the strict
    canonical shape so :func:`extract_canonical_steps` lifts a single
    step out of it.
    """
    frontmatter_lines = [f"source: {source_name}"]
    if plan_details is not None:
        frontmatter_lines.append(f"plan_details: {plan_details}")
    frontmatter = "\n".join(frontmatter_lines)
    return (
        f"---\n{frontmatter}\n---\n"
        "# From Existing\n\n"
        "## Overview\n\n"
        "seed overview\n\n"
        "## Steps\n\n"
        "### 1. Step one\n\n"
        "Files:\n"
        "- `x.ts`\n"
        "\n"
        "## References\n\n"
        "- [Canonical API](https://example.test/canonical)\n"
    )


class TestResolveExistingPlanDetails:
    def test_returns_path_when_dir_exists(self, tmp_path: Path) -> None:
        canonical = tmp_path / "2-foo-canonical.md"
        canonical.write_text("x", encoding="utf-8")
        (tmp_path / "plan-details" / "foo").mkdir(parents=True)
        provenance = CanonicalProvenance(
            source="2-foo.md", plan_details="plan-details/foo"
        )
        got = resolve_existing_plan_details(canonical, provenance)
        assert got == (tmp_path / "plan-details" / "foo").resolve()

    def test_returns_none_when_provenance_missing_plan_details(
        self, tmp_path: Path
    ) -> None:
        canonical = tmp_path / "2-foo-canonical.md"
        canonical.write_text("x", encoding="utf-8")
        provenance = CanonicalProvenance(source="2-foo.md", plan_details=None)
        assert resolve_existing_plan_details(canonical, provenance) is None

    def test_returns_none_when_dir_gone(self, tmp_path: Path) -> None:
        canonical = tmp_path / "2-foo-canonical.md"
        canonical.write_text("x", encoding="utf-8")
        provenance = CanonicalProvenance(
            source="2-foo.md", plan_details="plan-details/foo"
        )
        # Directory never created.
        assert resolve_existing_plan_details(canonical, provenance) is None


class TestRenamePlanDetailsToSlug:
    def test_moves_dir_and_preserves_contents(self, tmp_path: Path) -> None:
        source_dir = tmp_path / "plans" / "plan-details" / "old-slug"
        source_dir.mkdir(parents=True)
        (source_dir / "01-step.md").write_text(
            "# detail\n", encoding="utf-8"
        )
        output_dir = tmp_path / "plans"

        target, reason = rename_plan_details_to_slug(
            existing_details=source_dir,
            output_dir=output_dir,
            new_slug="new-slug",
        )

        assert reason is None
        assert target is not None
        assert target == (output_dir / "plan-details" / "new-slug").resolve()
        assert (target / "01-step.md").read_text(encoding="utf-8") == "# detail\n"
        # Source location no longer exists after the rename.
        assert not source_dir.exists()

    def test_skips_when_target_already_exists(self, tmp_path: Path) -> None:
        source_dir = tmp_path / "plans" / "plan-details" / "old-slug"
        source_dir.mkdir(parents=True)
        target = tmp_path / "plans" / "plan-details" / "new-slug"
        target.mkdir(parents=True)
        (target / "existing.md").write_text("x", encoding="utf-8")

        result_target, reason = rename_plan_details_to_slug(
            existing_details=source_dir,
            output_dir=tmp_path / "plans",
            new_slug="new-slug",
        )

        assert result_target is None
        assert reason is not None
        assert "already exists" in reason
        # Source stays put; the conflicting target is untouched.
        assert source_dir.is_dir()
        assert (target / "existing.md").read_text(encoding="utf-8") == "x"

    def test_noop_when_target_equals_source(self, tmp_path: Path) -> None:
        """Slug unchanged → no rename, no error, no warning."""
        details = tmp_path / "plans" / "plan-details" / "slug"
        details.mkdir(parents=True)

        target, reason = rename_plan_details_to_slug(
            existing_details=details.resolve(),
            output_dir=tmp_path / "plans",
            new_slug="slug",
        )

        assert target is None
        assert reason is None
        assert details.is_dir()


@pytest.mark.integration
class TestCreatePlanReusesPlanDetails:
    """End-to-end: ``create --from-existing`` on a canonical with provenance
    renames plan-details to the new slug and surfaces the provenance back
    in :class:`CreateResult`.
    """

    def test_plan_details_renamed_to_new_slug(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        # Seed (referenced by provenance, but not actually parsed here).
        (out_dir / "2-old.md").write_text("seed prose", encoding="utf-8")
        # Existing plan-details for the seed.
        old_details = out_dir / "plan-details" / "old"
        old_details.mkdir(parents=True)
        (old_details / "01-step.md").write_text("# detail\n", encoding="utf-8")
        # Canonical pointing at both.
        canonical = out_dir / "2-old-canonical.md"
        canonical.write_text(
            _canonical_with_provenance(
                source_name="2-old.md", plan_details="plan-details/old"
            ),
            encoding="utf-8",
        )
        manifest = tmp_path / "m.json"
        answers = _basic_metadata_answers(title="New Plan")

        result = create_plan(
            "new",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description=canonical.read_text(encoding="utf-8"),
            from_existing_path=canonical,
            input_fn=_queue_input(answers),
            # Canonical extraction supplies steps; the one claude call
            # still happens for References research. Return "[]" so the
            # References section renders as ``_(TODO)_``.
            claude_invoker=lambda prompt: (
                _valid_preparation_response(prompt)
                if "Distill a free-form seed" in prompt
                else _ONE_STEP_JSON
                if "Propose an initial plan step-list" in prompt
                else "[]"
            ),
        )

        # New plan exists with the new slug; old plan-details has moved.
        assert result.plan_details_renamed_to is not None
        assert (
            result.plan_details_renamed_to
            == (out_dir / "plan-details" / "new").resolve()
        )
        assert not old_details.exists()
        new_details = out_dir / "plan-details" / "new"
        assert (new_details / "01-step.md").read_text(
            encoding="utf-8"
        ) == "# detail\n"
        # Provenance is round-tripped on the result.
        assert result.provenance is not None
        assert result.provenance.source == "2-old.md"

    def test_plan_details_skip_surfaces_reason(self, tmp_path: Path) -> None:
        """Collision with an existing target leaves the source dir in place
        and reports a skip reason; the new plan is still written."""
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        (out_dir / "2-old.md").write_text("seed", encoding="utf-8")
        old_details = out_dir / "plan-details" / "old"
        old_details.mkdir(parents=True)
        # Pre-existing collision at the new slug location.
        collide = out_dir / "plan-details" / "new"
        collide.mkdir(parents=True)
        (collide / "already.md").write_text("untouched", encoding="utf-8")

        canonical = out_dir / "2-old-canonical.md"
        canonical.write_text(
            _canonical_with_provenance(
                source_name="2-old.md", plan_details="plan-details/old"
            ),
            encoding="utf-8",
        )
        manifest = tmp_path / "m.json"

        result = create_plan(
            "new",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description=canonical.read_text(encoding="utf-8"),
            from_existing_path=canonical,
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=lambda prompt: (
                _valid_preparation_response(prompt)
                if "Distill a free-form seed" in prompt
                else _ONE_STEP_JSON
                if "Propose an initial plan step-list" in prompt
                else "[]"
            ),
        )

        assert result.plan_details_renamed_to is None
        assert result.plan_details_skip_reason is not None
        assert "already exists" in result.plan_details_skip_reason
        # Source dir and conflicting target both untouched.
        assert old_details.is_dir()
        assert (collide / "already.md").read_text(encoding="utf-8") == "untouched"
        # Plan still written normally.
        assert result.plan_path.is_file()

    def test_no_provenance_no_rename(self, tmp_path: Path) -> None:
        """Canonical without a frontmatter block has no provenance; the
        rename codepath is a no-op and existing tests stay green."""
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        canonical = out_dir / "canonical.md"
        # Hand-built canonical body WITHOUT provenance (no frontmatter).
        # Format mirrors what the deleted ``render_canonical`` produced;
        # see ``PLAN_FORMAT.md`` → Canonical step layout.
        body = (
            "# X\n\n## Overview\n\no\n\n## Steps\n\n### 1. s\n\n"
            "## References\n\n- [API](https://example.test/api)\n"
        )
        canonical.write_text(body, encoding="utf-8")
        manifest = tmp_path / "m.json"

        def invoker(prompt: str) -> str:
            if "Distill a free-form seed" in prompt:
                return _valid_preparation_response(prompt)
            if "developer and API reference documentation" in prompt:
                return _REF_JSON
            if "Synthesize plan body sections" in prompt:
                return _SYNTHESIS_NULL_JSON
            return _STEP_JSON

        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description=body,
            from_existing_path=canonical,
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=invoker,
        )

        assert result.provenance is None
        assert result.plan_details_renamed_to is None
        assert result.plan_details_skip_reason is None


@pytest.mark.integration
class TestCliArchivesOriginalSeed:
    """``cmd_create`` archives BOTH the canonical and the original seed
    when provenance points back to the seed file. This is the fix for
    the orphaned-seed case the user originally hit.
    """

    def test_seed_is_archived_alongside_canonical(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool.cli import context as cli_context

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"
        # Original seed (the file reformat ran on).
        seed = out_dir / "2-old.md"
        seed.write_text(
            "# Old Plan\n\nSeed body.\n\n"
            "## References\n\n- [API](https://example.test/api)\n",
            encoding="utf-8",
        )
        # Canonical with provenance pointing at the seed.
        canonical = out_dir / "2-old-canonical.md"
        canonical.write_text(
            _canonical_with_provenance(source_name="2-old.md", plan_details=None),
            encoding="utf-8",
        )

        original_create_plan = cli_module.create_plan
        answers = _basic_metadata_answers()

        def patched(*args, **kwargs):
            kwargs.setdefault("input_fn", _queue_input(answers))
            kwargs["claude_invoker"] = lambda prompt: (
                _valid_preparation_response(prompt)
                if "Distill a free-form seed" in prompt
                else _ONE_STEP_JSON
                if "Propose an initial plan step-list" in prompt
                else "[]"
            )
            return original_create_plan(*args, **kwargs)

        monkeypatch.setattr("plan_tool.cli.authoring.create_plan", patched)
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "create", "new",
                "--from-existing", str(canonical),
                "--output-dir", str(out_dir),
                "--no-distill",
                "--no-iterate",
            ]
        )
        assert rc == 0

        # Both files moved into the archive with a replacement notice.
        archive_dir = out_dir / "archive"
        canonical_archived = archive_dir / "2-old-canonical.replaced.md"
        seed_archived = archive_dir / "2-old.replaced.md"
        assert canonical_archived.is_file()
        assert seed_archived.is_file()
        assert "Replaced" in seed_archived.read_text(encoding="utf-8")
        assert "Seed body." in seed_archived.read_text(encoding="utf-8")
        # Originals removed.
        assert not canonical.exists()
        assert not seed.exists()

    def test_missing_seed_does_not_break_create(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Provenance points at a file that no longer exists (user deleted
        it manually). Create should still succeed; the seed-archive step is
        a no-op for that branch."""
        from plan_tool.cli import app as cli_module
        from plan_tool.cli import context as cli_context

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"
        canonical = out_dir / "2-old-canonical.md"
        canonical.write_text(
            _canonical_with_provenance(
                source_name="2-old.md", plan_details=None
            ),
            encoding="utf-8",
        )
        # ``2-old.md`` deliberately absent.

        original_create_plan = cli_module.create_plan
        answers = _basic_metadata_answers()

        def patched(*args, **kwargs):
            kwargs.setdefault("input_fn", _queue_input(answers))
            kwargs["claude_invoker"] = lambda prompt: (
                _valid_preparation_response(prompt)
                if "Distill a free-form seed" in prompt
                else _ONE_STEP_JSON
                if "Propose an initial plan step-list" in prompt
                else "[]"
            )
            return original_create_plan(*args, **kwargs)

        monkeypatch.setattr("plan_tool.cli.authoring.create_plan", patched)
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "create", "new",
                "--from-existing", str(canonical),
                "--output-dir", str(out_dir),
                "--no-distill",
                "--no-iterate",
            ]
        )
        assert rc == 0
        # Canonical still archived; missing seed simply has no archive entry.
        archived = out_dir / "archive" / "2-old-canonical.replaced.md"
        assert archived.is_file()
        assert not (out_dir / "archive" / "2-old.replaced.md").exists()


# --- Collision replacement: prompt → archive existing → write new plan ----


from plan_tool.create import (
    find_collisions,
    predict_plan_path,
    remove_from_manifest,
)


class TestFindCollisions:
    def test_returns_empty_when_dir_missing(self, tmp_path: Path) -> None:
        assert find_collisions(tmp_path / "nope", "foo") == []

    def test_finds_prefixed_match(self, tmp_path: Path) -> None:
        (tmp_path / "4-foo.md").write_text("x", encoding="utf-8")
        hits = find_collisions(tmp_path, "foo")
        assert [c.path.name for c in hits] == ["4-foo.md"]

    def test_finds_unprefixed_match(self, tmp_path: Path) -> None:
        (tmp_path / "foo.md").write_text("x", encoding="utf-8")
        hits = find_collisions(tmp_path, "foo")
        assert [c.path.name for c in hits] == ["foo.md"]

    def test_no_match_returns_empty(self, tmp_path: Path) -> None:
        (tmp_path / "1-other.md").write_text("x", encoding="utf-8")
        assert find_collisions(tmp_path, "foo") == []

    def test_no_false_match_on_suffix(self, tmp_path: Path) -> None:
        (tmp_path / "4-foo-bar.md").write_text("x", encoding="utf-8")
        assert find_collisions(tmp_path, "bar") == []

    def test_legacy_callers_get_registered_true(self, tmp_path: Path) -> None:
        """Without manifest context, every hit is reported as registered=True
        so legacy callers (e.g. `check_collision`) keep fail-fast semantics."""
        (tmp_path / "2-foo.md").write_text("x", encoding="utf-8")
        hits = find_collisions(tmp_path, "foo")
        assert len(hits) == 1
        assert hits[0].registered is True

    def test_manifest_context_marks_unlisted_as_orphan(
        self, tmp_path: Path
    ) -> None:
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        (out_dir / "2-foo.md").write_text("x", encoding="utf-8")
        manifest = tmp_path / "m.json"
        manifest.write_text(
            json.dumps({"plans": []}), encoding="utf-8"
        )
        hits = find_collisions(
            out_dir, "foo", manifest_path=manifest, repo_root=tmp_path
        )
        assert len(hits) == 1
        assert hits[0].registered is False

    def test_manifest_context_marks_listed_as_registered(
        self, tmp_path: Path
    ) -> None:
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        (out_dir / "2-foo.md").write_text("x", encoding="utf-8")
        manifest = tmp_path / "m.json"
        manifest.write_text(
            json.dumps({"plans": ["plans/2-foo.md"]}), encoding="utf-8"
        )
        hits = find_collisions(
            out_dir, "foo", manifest_path=manifest, repo_root=tmp_path
        )
        assert len(hits) == 1
        assert hits[0].registered is True


class TestRemoveFromManifest:
    def test_removes_existing_entry(self, tmp_path: Path) -> None:
        mf = tmp_path / "m.json"
        mf.write_text(
            json.dumps({"plans": ["plans/4-foo.md", "plans/2-bar.md"]}),
            encoding="utf-8",
        )
        plan = tmp_path / "plans" / "4-foo.md"
        plan.parent.mkdir()
        plan.write_text("x", encoding="utf-8")
        removed = remove_from_manifest(mf, tmp_path, plan)
        assert removed is True
        data = json.loads(mf.read_text(encoding="utf-8"))
        assert data["plans"] == ["plans/2-bar.md"]

    def test_noop_when_entry_missing(self, tmp_path: Path) -> None:
        mf = tmp_path / "m.json"
        mf.write_text(
            json.dumps({"plans": ["plans/2-bar.md"]}), encoding="utf-8"
        )
        plan = tmp_path / "plans" / "4-foo.md"
        plan.parent.mkdir()
        plan.write_text("x", encoding="utf-8")
        removed = remove_from_manifest(mf, tmp_path, plan)
        assert removed is False
        data = json.loads(mf.read_text(encoding="utf-8"))
        assert data["plans"] == ["plans/2-bar.md"]

    def test_noop_when_manifest_missing(self, tmp_path: Path) -> None:
        plan = tmp_path / "plans" / "4-foo.md"
        plan.parent.mkdir()
        plan.write_text("x", encoding="utf-8")
        assert remove_from_manifest(tmp_path / "nope.json", tmp_path, plan) is False


class TestPredictPlanPath:
    """Predicted path is the priority bucket regardless of what's on disk."""

    def test_predict_uses_priority_bucket(self, tmp_path: Path) -> None:
        # Pre-existing files don't influence the predicted slot.
        for prefix, name in [(1, "a"), (2, "b"), (3, "c"), (4, "foo")]:
            (tmp_path / f"{prefix}-{name}.md").write_text("x", encoding="utf-8")
        predicted = predict_plan_path(tmp_path, "foo", Priority.MEDIUM)
        # Medium priority → bucket 2 regardless of the collision at 4-foo.md.
        assert predicted.name == "2-foo.md"


@pytest.mark.integration
class TestCreatePlanReplaceOnCollision:
    @pytest.fixture(autouse=True)
    def _stub_propose_references(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Stub the references claude call site — these tests assert
        on collision-and-replace behavior, not references."""
        from plan_tool import create as create_module
        monkeypatch.setattr(
            create_module, "propose_references_from_claude",
            lambda *a, **kw: ReferenceResearchResult.from_references([]),
        )

    @pytest.mark.parametrize("text_key", ["description", "title"])
    def test_replace_via_kwarg_archives_existing(self, tmp_path: Path, text_key: str) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        # Existing plan lives at a legacy prefix; replacement should
        # land the new plan at its priority bucket regardless.
        existing = out_dir / "4-foo.md"
        existing.write_text("# Old\n\nOriginal content.\n", encoding="utf-8")
        # Manifest entry the new flow should clean up.
        manifest = tmp_path / "m.json"
        manifest.write_text(
            json.dumps({"plans": ["plans/4-foo.md"]}), encoding="utf-8"
        )
        # Plan-details that belong to the existing plan.
        old_details = out_dir / "plan-details" / "foo"
        old_details.mkdir(parents=True)
        (old_details / "01-step.md").write_text("# detail\n", encoding="utf-8")

        answers = _basic_metadata_answers() + _single_step_answers()
        result = create_plan(
            "foo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            input_fn=_queue_input(answers),
            replace_on_collision=True,
            from_description="Build a replacement",
            claude_invoker=lambda _prompt: json.dumps([{text_key: "Replacement step", "intent": "Supply replacement behavior"}]),
            yes=True,
        )

        assert parse_plan(result.plan_path).steps[0].title == "Replacement step"
        assert "  description: Replacement step" in result.plan_path.read_text()
        assert not existing.exists()
        assert not old_details.exists()
        # New plan lands at the medium-priority bucket.
        assert result.plan_path.name == "2-foo.md"
        # Existing plan moved into archive with replacement notice.
        archived = out_dir / "archive" / "4-foo.replaced.md"
        assert archived.is_file()
        text = archived.read_text(encoding="utf-8")
        assert "Replaced" in text
        assert "Original content." in text
        # Plan-details archived alongside.
        archived_details = out_dir / "archive" / "plan-details" / "foo"
        assert archived_details.is_dir()
        assert (archived_details / "01-step.md").is_file()
        # Manifest: stale entry removed, new entry added.
        data = json.loads(manifest.read_text(encoding="utf-8"))
        assert data["plans"] == ["plans/2-foo.md"]
        # Stale entry reported on the result.
        assert result.replaced_manifest_entries == ["plans/4-foo.md"]
        # Archive pairs surfaced.
        assert any(
            target.name == "4-foo.replaced.md"
            for _, target in result.replaced_archives
        )

    def test_replace_via_prompt_yes(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        (out_dir / "4-foo.md").write_text("# Old\n", encoding="utf-8")
        # Pre-populate the manifest so the existing file is recognized as
        # a registered plan (not an orphan) — the interactive prompt path
        # only fires for registered collisions.
        manifest = tmp_path / "m.json"
        manifest.write_text(
            json.dumps({"plans": ["plans/4-foo.md"]}), encoding="utf-8"
        )

        # First answer 'y' to the new replace prompt, then the usual metadata.
        answers = (
            ["y"] + _basic_metadata_answers() + _single_step_answers()
        )
        result = create_plan(
            "foo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            input_fn=_queue_input(answers),
        )
        # Medium priority → bucket 2.
        assert result.plan_path.name == "2-foo.md"
        assert (out_dir / "archive" / "4-foo.replaced.md").is_file()

    def test_decline_prompt_raises_file_exists(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        (out_dir / "4-foo.md").write_text("# Old\n", encoding="utf-8")
        # Registered file → prompt fires. Declining preserves the
        # historical abort message.
        manifest = tmp_path / "m.json"
        manifest.write_text(
            json.dumps({"plans": ["plans/4-foo.md"]}), encoding="utf-8"
        )

        # Answer 'n' to the replace prompt → preserves historical abort.
        with pytest.raises(FileExistsError, match="foo"):
            create_plan(
                "foo",
                repo_root=tmp_path,
                output_dir_override=out_dir,
                manifest_path=manifest,
                input_fn=_queue_input(["n"]),
            )
        # New plan never created; existing still on disk.
        assert (out_dir / "4-foo.md").read_text(encoding="utf-8") == "# Old\n"

    def test_no_prompt_when_replace_kwarg_set(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Explicit ``replace_on_collision=True`` skips the prompt entirely
        (no input_fn consumption for the replace question).

        Also covers the "I know what I'm doing" escape hatch: explicit
        replace takes precedence over the orphan-refusal check, so an
        unregistered file on disk is still clobbered when the caller
        asks for it.
        """
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        (out_dir / "4-foo.md").write_text("# Old\n", encoding="utf-8")
        manifest = tmp_path / "m.json"

        # No 'y' at the front — metadata only. If the wizard prompted,
        # ``_queue_input`` would raise.
        answers = _basic_metadata_answers() + _single_step_answers()
        create_plan(
            "foo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            input_fn=_queue_input(answers),
            replace_on_collision=True,
        )


class TestDecideReplaceFromExistingSeed:
    """The ``--from-existing <orphan>`` workflow is the canonical way to
    convert an unstructured draft into a managed plan: the source file
    is consumed (archived) as part of the create. So when the seed file
    IS one of the collisions, ``_decide_replace_collisions`` must
    auto-approve replacement — no orphan refusal, no interactive prompt
    — for that file. Other collisions still go through the normal
    flow.
    """

    @pytest.fixture(autouse=True)
    def _stub_claude_proposals(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The end-to-end test in this class drives ``create_plan``
        with ``from_description=`` set, which would fire both
        ``propose_steps_from_claude`` and ``propose_references_from_claude``.
        Stub both to keep the test hermetic. ``propose_steps_from_claude``
        returning ``None`` triggers the interactive-wizard fallback,
        which is what the test exercises. Harmless for the
        ``_decide_replace_collisions`` direct-call tests that don't go
        through ``create_plan``."""
        from plan_tool import create as create_module
        monkeypatch.setattr(
            create_module, "propose_steps_from_claude",
            lambda *a, **kw: None,
        )
        monkeypatch.setattr(
            create_module, "propose_references_from_claude",
            lambda *a, **kw: ReferenceResearchResult.from_references([]),
        )

    def _no_input(self, _prompt: str) -> str:
        raise AssertionError("must not prompt when seed exempts the collision")

    def test_seed_only_collision_returns_true_silently(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.create import Collision, _decide_replace_collisions

        seed = tmp_path / "foo.md"
        seed.write_text("draft", encoding="utf-8")
        collisions = [Collision(path=seed, registered=False)]
        assert _decide_replace_collisions(
            collisions,
            "foo",
            self._no_input,
            None,
            from_existing_path=seed,
        ) is True

    def test_seed_plus_other_orphan_still_refuses(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.create import Collision, _decide_replace_collisions

        seed = tmp_path / "foo.md"
        other = tmp_path / "2-foo.md"
        seed.write_text("draft", encoding="utf-8")
        other.write_text("# Other", encoding="utf-8")
        collisions = [
            Collision(path=seed, registered=False),
            Collision(path=other, registered=False),
        ]
        with pytest.raises(FileExistsError, match="not registered"):
            _decide_replace_collisions(
                collisions,
                "foo",
                self._no_input,
                None,
                from_existing_path=seed,
            )

    def test_seed_plus_registered_prompts_only_for_registered(
        self, tmp_path: Path
    ) -> None:
        """When the seed is exempted and a separate REGISTERED collision
        remains, the prompt fires for the registered file only — listing
        that path (not the seed path) and respecting decline."""
        from plan_tool.create import Collision, _decide_replace_collisions

        seed = tmp_path / "foo.md"
        registered = tmp_path / "2-foo.md"
        prompts: list[str] = []

        def fake_input(prompt: str) -> str:
            prompts.append(prompt)
            return "n"

        with pytest.raises(FileExistsError):
            _decide_replace_collisions(
                [
                    Collision(path=seed, registered=False),
                    Collision(path=registered, registered=True),
                ],
                "foo",
                fake_input,
                None,
                from_existing_path=seed,
            )
        assert any(str(registered) in p for p in prompts) or any(
            "Replace it" in p for p in prompts
        )

    def test_create_plan_from_existing_orphan_archives_seed(
        self, tmp_path: Path
    ) -> None:
        """End-to-end: ``create --from-existing <orphan>`` with an
        unstructured draft at the slug's path archives the draft and
        writes a new structured plan in its place, without prompting
        for replacement."""
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        seed = out_dir / "foo.md"
        seed.write_text(
            "# Foo Draft\n\nUnstructured prose seed.\n\n"
            "## References\n\n- [API](https://example.test/api)\n",
            encoding="utf-8",
        )
        manifest = tmp_path / "m.json"

        answers = _basic_metadata_answers() + _single_step_answers()

        def invoker(prompt: str) -> str:
            if "Distill a free-form seed" in prompt:
                return _valid_preparation_response(prompt)
            if "developer and API reference documentation" in prompt:
                return _REF_JSON
            if "Synthesize plan body sections" in prompt:
                return _SYNTHESIS_NULL_JSON
            # Return malformed JSON for the steps round-trip so create
            # falls back to the interactive step builder (which the
            # ``_single_step_answers()`` input_fn satisfies).
            return ""

        result = create_plan(
            "foo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description=seed.read_text(encoding="utf-8"),
            from_existing_path=seed,
            input_fn=_queue_input(answers),
            claude_invoker=invoker,
        )
        # New plan lands at the priority-prefixed name (medium → 2-).
        assert result.plan_path.name == "2-foo.md"
        # Seed archived alongside.
        assert (out_dir / "archive" / "foo.replaced.md").is_file()


# --- References web-research ----------------------------------------------


from plan_tool.create import (  # noqa: E402
    Reference,
    _build_research_context,
    _parse_references_json,
    propose_references_from_claude,
    validate_from_existing_seed,
)


class TestParseReferencesJson:
    def test_happy_path(self) -> None:
        raw = json.dumps(
            [
                {
                    "title": "AWS Amplify Gen 2",
                    "url": "https://docs.amplify.aws/gen2/",
                    "description": "Backend definition reference.",
                },
                {
                    "title": "Bedrock AgentCore",
                    "url": "https://docs.aws.amazon.com/bedrock/agentcore/",
                    "description": "InvokeAgentRuntime API.",
                },
            ]
        )
        result = _parse_references_json(raw)
        assert result.outcome == "populated"
        assert [r.title for r in result.references] == [
            "AWS Amplify Gen 2",
            "Bedrock AgentCore",
        ]
        assert result.references[0].url == "https://docs.amplify.aws/gen2/"
        assert result.references[1].description == "InvokeAgentRuntime API."

    def test_tolerates_chatter_around_array(self) -> None:
        raw = (
            "Here you go:\n"
            '[{"title": "Docs", "url": "https://example.com", "description": ""}]\n'
            "Hope that helps."
        )
        result = _parse_references_json(raw)
        assert result.outcome == "populated"
        assert len(result.references) == 1
        assert result.references[0].url == "https://example.com"

    def test_empty_array_returns_empty_result(self) -> None:
        result = _parse_references_json("[]")
        assert result.outcome == "empty"
        assert result.references == ()

    def test_no_json_returns_unparseable_result(self) -> None:
        result = _parse_references_json("sorry I cannot help")
        assert result.outcome == "unparseable"
        assert result.references == ()

    def test_top_level_not_array_returns_unparseable_result(self) -> None:
        result = _parse_references_json('{"title": "x"}')
        assert result.outcome == "unparseable"

    def test_drops_entries_with_non_http_url(self) -> None:
        raw = json.dumps(
            [
                {"title": "ok", "url": "https://a.com", "description": ""},
                {"title": "bad", "url": "ftp://b.com", "description": ""},
                {"title": "also bad", "url": "", "description": ""},
            ]
        )
        result = _parse_references_json(raw)
        assert result.outcome == "populated"
        assert [r.url for r in result.references] == ["https://a.com"]

    def test_drops_entries_missing_title(self) -> None:
        raw = json.dumps(
            [
                {"title": "", "url": "https://a.com", "description": ""},
                {"url": "https://b.com", "description": ""},  # no title key
                {"title": "keep", "url": "https://c.com"},  # no description
            ]
        )
        result = _parse_references_json(raw)
        assert result.outcome == "populated"
        assert [r.title for r in result.references] == ["keep"]
        assert result.references[0].description == ""


class _AttemptFailedRunLogger:
    """Minimal ``RunLoggerLike`` fake recording ``attempt_failed`` calls;
    every other method is a no-op. Shared by tests asserting which
    ``failure_kind`` a reference-research attempt records."""

    def __init__(self) -> None:
        self.failures: list[dict[str, object]] = []

    def attempt_failed(self, **kwargs: object) -> None:
        self.failures.append(kwargs)

    def claude_call_start(self, **_kwargs: object) -> None:
        return None

    def install_call_end_sink(self, **_kwargs: object) -> None:
        return None

    def uninstall_call_end_sink(self) -> None:
        return None


class TestProposeReferencesFromClaude:
    def test_complete_on_success(self) -> None:
        reporter = _RecordingReporter()
        canned = json.dumps(
            [{"title": "Docs", "url": "https://example.com", "description": "x"}]
        )
        result = propose_references_from_claude(
            "My Plan",
            "build a thing",
            lambda prompt: canned,
            reporter=reporter,
        )
        assert result.outcome == "populated"
        assert len(result.references) == 1
        assert reporter.starts == [(1, 1, "Researching developer docs")]
        assert reporter.handles[0].completed is not None

    def test_unparseable_first_response_retries_once(self) -> None:
        reporter = _RecordingReporter()
        calls: list[str] = []
        run_logger = _AttemptFailedRunLogger()

        def invoker(prompt: str) -> str:
            calls.append(prompt)
            return (
                "no idea sorry"
                if len(calls) == 1
                else json.dumps([
                    {
                        "title": "Recovered docs",
                        "url": "https://example.com/recovered",
                        "description": "A repaired response.",
                    }
                ])
            )

        result = propose_references_from_claude(
            "My Plan",
            "build a thing",
            invoker,
            reporter=reporter,
            run_logger=run_logger,
        )
        assert result.outcome == "populated"
        assert [reference.title for reference in result.references] == [
            "Recovered docs"
        ]
        assert len(calls) == 2
        assert reporter.handles[0].completed is not None
        assert reporter.handles[0].failed is None
        assert reporter.handles[0].notices == [
            (
                "developer-doc research: first response was unparseable; retrying once",
                "retry",
            )
        ]
        assert run_logger.failures == [
            {
                "phase": "propose_references",
                "attempt": 1,
                "failure_kind": "parse",
            }
        ]

    @pytest.mark.parametrize("raising_attempt", [1, 2])
    def test_invoker_exception_fails_the_progress_handle(
        self, raising_attempt: int
    ) -> None:
        """Either reference-research invocation closes its progress handle
        before a backend exception escapes."""
        reporter = _RecordingReporter()
        calls = 0

        def invoker(_prompt: str) -> str:
            nonlocal calls
            calls += 1
            if calls == raising_attempt:
                raise RuntimeError("backend unavailable")
            return "not JSON"

        with pytest.raises(RuntimeError, match="backend unavailable"):
            propose_references_from_claude(
                "My Plan", "build a thing", invoker, reporter=reporter
            )

        assert calls == raising_attempt
        assert reporter.handles[0].completed is None
        assert reporter.handles[0].failed is not None
        assert "backend unavailable" in reporter.handles[0].failed[1]

    @pytest.mark.parametrize("raising_attempt", [1, 2])
    def test_invoker_exception_records_a_transport_attempt_failure(
        self, raising_attempt: int
    ) -> None:
        """A raised invoker exception is a distinct failure kind from a
        parseable-but-rejected response -- ``"transport"`` matches this
        codebase's existing failure-kind vocabulary for a raised backend
        call (see ``roadmap_candidate_run.py``/``roadmap_candidate_review.py``),
        so the run log can tell the two apart the same way ``"parse"``
        already does for an unparseable response."""
        reporter = _RecordingReporter()
        run_logger = _AttemptFailedRunLogger()
        calls = 0

        def invoker(_prompt: str) -> str:
            nonlocal calls
            calls += 1
            if calls == raising_attempt:
                raise RuntimeError("backend unavailable")
            return "not JSON"

        with pytest.raises(RuntimeError, match="backend unavailable"):
            propose_references_from_claude(
                "My Plan",
                "build a thing",
                invoker,
                reporter=reporter,
                run_logger=run_logger,
            )

        # When attempt 2 is the one that raises, attempt 1's return value
        # ("not JSON", matching the sibling handle-failure test above) is
        # itself an unparseable response, so it records its own "parse"
        # attempt-failure before the retry's "transport" one.
        expected = (
            [{"phase": "propose_references", "attempt": 1, "failure_kind": "parse"}]
            if raising_attempt == 2
            else []
        ) + [
            {
                "phase": "propose_references",
                "attempt": raising_attempt,
                "failure_kind": "transport",
            }
        ]
        assert run_logger.failures == expected

    def test_repair_prompt_includes_rejected_reply_and_json_array_contract(
        self,
    ) -> None:
        rejected_response = "formatting-slip-marker"
        prompts: list[str] = []

        def invoker(prompt: str) -> str:
            prompts.append(prompt)
            return rejected_response if len(prompts) == 1 else "[]"

        result = propose_references_from_claude(
            "My Plan",
            "build a thing",
            invoker,
            reporter=_RecordingReporter(),
        )

        assert result.outcome == "empty"
        assert rejected_response in prompts[1]
        assert "Respond with only one JSON array" in prompts[1]
        assert "replacement response" in prompts[1]

    def test_parseable_empty_response_does_not_retry(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        calls = 0

        def invoker(_prompt: str) -> str:
            nonlocal calls
            calls += 1
            return "[]"

        result = propose_references_from_claude(
            "My Plan",
            "build a thing",
            invoker,
            reporter=_RecordingReporter(),
            slug="demo",
            output_dir=out_dir,
            repo_root=tmp_path,
        )

        assert result.outcome == "empty"
        assert calls == 1
        checkpoint = checkpoint_path(tmp_path, "demo", _REFERENCES_CHECKPOINT_NAME)
        assert checkpoint.exists()
        assert json.loads(checkpoint.read_text(encoding="utf-8"))["payload"] == "[]"

    def test_repair_records_propose_references_attempts_one_and_two(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.run_log import RunLogWriter

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        run_logger = RunLogWriter.start(
            repo_root=tmp_path,
            slug="demo",
            command="create",
            argv=["plan-tool", "create", "demo"],
        )
        responses = iter(["not JSON", "[]"])

        result = propose_references_from_claude(
            "My Plan",
            "build a thing",
            lambda _prompt: next(responses),
            reporter=StderrReporter(stream=StringIO(), run_log=run_logger),
            slug="demo",
            output_dir=out_dir,
            repo_root=tmp_path,
            run_logger=run_logger,
        )

        assert result.outcome == "empty"
        events = _read_run_log(tmp_path, "demo")
        calls = [
            event
            for event in events
            if event["event"] == "claude_call_start"
            and event["phase"] == "propose_references"
        ]
        assert [event["attempt"] for event in calls] == [1, 2]
        failures = [event for event in events if event["event"] == "attempt_failed"]
        assert [(event["attempt"], event["failure_kind"]) for event in failures] == [
            (1, "parse")
        ]

    def test_parseable_repair_replaces_references_checkpoint_payload(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        initial_response = json.dumps([
            {
                "title": "Initial docs",
                "url": "https://example.com/initial",
                "description": "The original checkpoint payload.",
            }
        ])
        repaired_response = json.dumps([
            {
                "title": "Repaired docs",
                "url": "https://example.com/repaired",
                "description": "The accepted replacement payload.",
            }
        ])
        propose_references_from_claude(
            "My Plan",
            "build a thing",
            lambda _prompt: initial_response,
            reporter=_RecordingReporter(),
            slug="demo",
            output_dir=out_dir,
            repo_root=tmp_path,
        )

        responses = iter(["not JSON", repaired_response])
        result = propose_references_from_claude(
            "My Plan",
            "build a thing",
            lambda _prompt: next(responses),
            reporter=_RecordingReporter(),
            slug="demo",
            output_dir=out_dir,
            repo_root=tmp_path,
            resume=False,
        )

        assert result.outcome == "populated"
        checkpoint = checkpoint_path(tmp_path, "demo", _REFERENCES_CHECKPOINT_NAME)
        assert (
            json.loads(checkpoint.read_text(encoding="utf-8"))["payload"]
            == repaired_response
        )

    def test_twice_unparseable_dumps_attempt_two_and_skips_references_checkpoint(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.run_log import RunLogWriter

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        run_logger = RunLogWriter.start(
            repo_root=tmp_path,
            slug="demo",
            command="create",
            argv=["plan-tool", "create", "demo"],
        )
        stream = StringIO()
        reporter = StderrReporter(stream=stream, run_log=run_logger)
        responses = iter(["first malformed", "second malformed"])

        result = propose_references_from_claude(
            "My Plan",
            "build a thing",
            lambda _prompt: next(responses),
            reporter=reporter,
            slug="demo",
            output_dir=out_dir,
            repo_root=tmp_path,
            run_logger=run_logger,
        )

        assert result.outcome == "unparseable"
        assert not checkpoint_path(
            tmp_path, "demo", _REFERENCES_CHECKPOINT_NAME
        ).exists()
        events = _read_run_log(tmp_path, "demo")
        failures = [event for event in events if event["event"] == "attempt_failed"]
        assert [(event["attempt"], event["failure_kind"]) for event in failures] == [
            (1, "parse"),
            (2, "parse"),
        ]
        diagnostics = [event for event in events if event["event"] == "parse_failure"]
        assert len(diagnostics) == 1
        assert diagnostics[0]["phase"] == "propose_references"
        assert diagnostics[0]["attempt"] == 2
        dump = tmp_path / diagnostics[0]["failure_path"]
        assert dump.read_text(encoding="utf-8") == "second malformed"
        assert "raw response saved to" in stream.getvalue()

    def test_prompt_carries_title_and_description(self) -> None:
        seen: dict[str, str] = {}

        def invoker(prompt: str) -> str:
            seen["prompt"] = prompt
            return "[]"

        propose_references_from_claude(
            "Cache Layer Migration",
            "Move ElastiCache cluster from Redis to Valkey.",
            invoker,
            reporter=_RecordingReporter(),
        )
        assert "Cache Layer Migration" in seen["prompt"]
        assert "ElastiCache" in seen["prompt"]
        assert "developer and API reference documentation" in seen["prompt"]


@pytest.mark.parametrize(
    ("phase", "invoke"),
    [
        pytest.param(
            "propose_steps",
            lambda invoker, reporter, run_logger: propose_steps_from_claude(
                "build a thing",
                invoker,
                reporter=reporter,
                run_logger=run_logger,
            ),
            id="steps",
        ),
        pytest.param(
            "propose_body_sections",
            lambda invoker, reporter, run_logger: propose_body_sections(
                "seed prose",
                invoker,
                reporter=reporter,
                run_logger=run_logger,
            ),
            id="body-sections",
        ),
        pytest.param(
            "propose_distilled_seed",
            lambda invoker, reporter, run_logger: propose_distilled_seed_from_claude(
                "seed prose",
                invoker,
                reporter=reporter,
                run_logger=run_logger,
            ),
            id="distill",
        ),
    ],
)
@pytest.mark.parametrize("raising_attempt", [1, 2])
def test_create_phase_invoker_exception_closes_and_records_transport_failure(
    phase: str,
    invoke: Callable[..., object],
    raising_attempt: int,
) -> None:
    """Every create phase closes the shared handle on a transport failure."""
    reporter = _RecordingReporter()
    run_logger = _AttemptFailedRunLogger()
    calls = 0

    def invoker(_prompt: str) -> str:
        nonlocal calls
        calls += 1
        if calls == raising_attempt:
            raise RuntimeError("backend unavailable")
        return "not JSON"

    with pytest.raises(RuntimeError, match="backend unavailable"):
        invoke(invoker, reporter, run_logger)

    assert calls == raising_attempt
    assert reporter.handles[0].completed is None
    assert reporter.handles[0].failed is not None
    assert "backend unavailable" in reporter.handles[0].failed[1]
    assert run_logger.failures == [
        {
            "phase": phase,
            "attempt": raising_attempt,
            "failure_kind": "transport",
        }
    ]


class TestInitialReferenceResearchFailure:
    """Initial generic research must settle before create can publish."""

    def _prepare_create(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        reference_result: ReferenceResearchResult,
    ) -> tuple[Path, Path]:
        (tmp_path / ".git").mkdir()
        output_dir = tmp_path / "plans"
        output_dir.mkdir()
        manifest_path = tmp_path / "manifest.json"
        monkeypatch.setattr(
            create_module,
            "propose_steps_from_claude",
            lambda *_args, **_kwargs: [Step(id=1, title="Build the feature")],
        )
        monkeypatch.setattr(
            create_module,
            "propose_references_from_claude",
            lambda *_args, **_kwargs: reference_result,
        )
        return output_dir, manifest_path

    def _create(
        self,
        tmp_path: Path,
        output_dir: Path,
        manifest_path: Path,
        **kwargs: Any,
    ) -> CreateResult:
        return create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=output_dir,
            manifest_path=manifest_path,
            from_description="Implement the developer-facing feature.",
            input_fn=_queue_input(_basic_metadata_answers()),
            **kwargs,
        )

    def test_initial_terminal_unparseable_research_aborts_create_before_plan_write(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        output_dir, manifest_path = self._prepare_create(
            tmp_path, monkeypatch, ReferenceResearchResult.unparseable()
        )

        with pytest.raises(CreateError, match="terminal developer-document"):
            self._create(tmp_path, output_dir, manifest_path)

        assert not (output_dir / "2-demo.md").exists()
        assert not manifest_path.exists()

    def test_initial_terminal_unparseable_research_preserves_collision_and_manifest(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        output_dir, manifest_path = self._prepare_create(
            tmp_path, monkeypatch, ReferenceResearchResult.unparseable()
        )
        collision = output_dir / "2-demo.md"
        original_plan = "# Existing plan\n"
        collision.write_text(original_plan, encoding="utf-8")
        original_manifest = {"plans": ["plans/2-demo.md"]}
        manifest_path.write_text(json.dumps(original_manifest), encoding="utf-8")

        with pytest.raises(CreateError, match="terminal developer-document"):
            self._create(
                tmp_path,
                output_dir,
                manifest_path,
                replace_on_collision=True,
            )

        assert collision.read_text(encoding="utf-8") == original_plan
        assert json.loads(manifest_path.read_text(encoding="utf-8")) == original_manifest
        assert not (output_dir / "archive" / "2-demo.replaced.md").exists()

    def test_initial_terminal_unparseable_research_stops_fetch_and_synthesis(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        output_dir, manifest_path = self._prepare_create(
            tmp_path, monkeypatch, ReferenceResearchResult.unparseable()
        )

        def fail_if_called(*_args: object, **_kwargs: object) -> None:
            raise AssertionError("initial malformed research must stop publication work")

        monkeypatch.setattr(create_module, "_fetch_reference_docs_block", fail_if_called)
        monkeypatch.setattr(create_module, "propose_body_sections", fail_if_called)

        with pytest.raises(CreateError, match="terminal developer-document"):
            self._create(tmp_path, output_dir, manifest_path)

    def test_initial_terminal_unparseable_research_records_error_phase(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.run_log import RunLogWriter

        output_dir, manifest_path = self._prepare_create(
            tmp_path, monkeypatch, ReferenceResearchResult.unparseable()
        )
        run_logger = RunLogWriter.start(
            repo_root=tmp_path,
            slug="demo",
            command="create",
            argv=["plan-tool", "create", "demo"],
        )

        with pytest.raises(CreateError, match="terminal developer-document"):
            self._create(
                tmp_path,
                output_dir,
                manifest_path,
                run_logger=run_logger,
            )

        phase_ends = [
            event
            for event in _read_run_log(tmp_path, "demo")
            if event["event"] == "phase_end"
            and event["phase"] == "propose_references"
        ]
        assert [event["outcome"] for event in phase_ends] == ["error"]

    def test_initial_terminal_unparseable_research_has_retry_diagnostic(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        output_dir, manifest_path = self._prepare_create(
            tmp_path, monkeypatch, ReferenceResearchResult.unparseable()
        )

        with pytest.raises(CreateError) as error:
            self._create(tmp_path, output_dir, manifest_path)

        assert "terminal developer-document reference research" in str(error.value)
        assert "retry the original `plan-tool create …` command" in str(error.value)

    def test_initial_valid_empty_research_continues_to_publish(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.run_log import RunLogWriter

        output_dir, manifest_path = self._prepare_create(
            tmp_path,
            monkeypatch,
            ReferenceResearchResult.from_references([]),
        )
        run_logger = RunLogWriter.start(
            repo_root=tmp_path,
            slug="demo",
            command="create",
            argv=["plan-tool", "create", "demo"],
        )
        monkeypatch.setattr(
            create_module,
            "propose_body_sections",
            lambda *_args, **_kwargs: {
                key: f"synthesized {key} body"
                for key in create_module._BODY_SECTIONS_CANONICAL_KEYS
            },
        )

        result = self._create(
            tmp_path,
            output_dir,
            manifest_path,
            run_logger=run_logger,
        )

        assert result.plan_path == output_dir / "2-demo.md"
        assert result.plan_path.exists()
        assert "## References\n\n_(TODO)_" in result.plan_path.read_text(
            encoding="utf-8"
        )
        assert json.loads(manifest_path.read_text(encoding="utf-8")) == {
            "plans": ["plans/2-demo.md"]
        }
        phase_ends = [
            event
            for event in _read_run_log(tmp_path, "demo")
            if event["event"] == "phase_end"
            and event["phase"] == "propose_references"
        ]
        assert [event["outcome"] for event in phase_ends] == ["skipped"]


class TestFromExistingSeedValidation:
    def test_rejects_missing_references(self) -> None:
        with pytest.raises(CreateError, match=r"## References"):
            validate_from_existing_seed("# Draft\n\n## Overview\n\nBody.\n")

    @pytest.mark.parametrize("placeholder", ["TODO", "(TODO)", "_(TODO)_"])
    def test_rejects_placeholder_references(self, placeholder: str) -> None:
        with pytest.raises(CreateError, match=r"non-placeholder"):
            validate_from_existing_seed(
                f"# Draft\n\n## References\n\n{placeholder}\n"
            )

    def test_accepts_nonempty_references(self) -> None:
        validate_from_existing_seed(
            "# Draft\n\n## References\n\n- [API](https://example.test/api)\n"
        )

    @pytest.mark.parametrize("heading", ("references", "References ##"))
    def test_accepts_normalized_references_heading(self, heading: str) -> None:
        validate_from_existing_seed(
            f"# Draft\n\n## {heading}\n\n- [API](https://example.test/api)\n"
        )

    def test_rejects_frontmatter_only_references(self) -> None:
        with pytest.raises(CreateError, match=r"## References"):
            validate_from_existing_seed(
                "---\n## References\n---\n# Draft\n\n## Overview\n\nBody.\n"
            )

    def test_rejects_fenced_only_references(self) -> None:
        with pytest.raises(CreateError, match=r"## References"):
            validate_from_existing_seed(
                "```markdown\n## References\n- https://example.test/api\n```\n"
            )

    def test_accepts_body_references_after_frontmatter(self) -> None:
        validate_from_existing_seed(
            "---\n## References\n---\n# Draft\n\n## References\n\n"
            "- `plan_tool/create.py`\n"
        )

    def test_accepts_reference_content_that_mentions_todo(self) -> None:
        validate_from_existing_seed(
            "# Draft\n\n## References\n\n- TODO: verify API version\n"
        )

    def test_direct_create_rejects_before_every_invoker(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        source = tmp_path / "seed.md"
        source.write_text("# Draft\n\n## Overview\n\nBody.\n", encoding="utf-8")
        calls = 0

        def invoker(_prompt: str) -> str:
            nonlocal calls
            calls += 1
            return "[]"

        with pytest.raises(CreateError, match=r"## References"):
            create_plan(
                "demo",
                repo_root=tmp_path,
                output_dir_override=tmp_path / "plans",
                manifest_path=tmp_path / "manifest.json",
                from_description=source.read_text(encoding="utf-8"),
                from_existing_path=source,
                claude_invoker=invoker,
                concept_invoker=invoker,
                foundational_invoker=invoker,
            )

        assert calls == 0
        assert not (tmp_path / "plans").exists()
        assert not (tmp_path / "manifest.json").exists()

    def test_direct_create_frontmatter_only_references_refuses_before_invokers_and_writes(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / ".git").mkdir()
        source = tmp_path / "seed.md"
        source.write_text(
            "---\n## References\n---\n# Draft\n\n## Overview\n\nBody.\n",
            encoding="utf-8",
        )
        calls = 0

        def invoker(_prompt: str) -> str:
            nonlocal calls
            calls += 1
            return "[]"

        with pytest.raises(CreateError, match=r"## References"):
            create_plan(
                "demo",
                repo_root=tmp_path,
                output_dir_override=tmp_path / "plans",
                manifest_path=tmp_path / "manifest.json",
                from_description=source.read_text(encoding="utf-8"),
                from_existing_path=source,
                claude_invoker=invoker,
                concept_invoker=invoker,
                foundational_invoker=invoker,
            )

        assert calls == 0
        assert not (tmp_path / "plans").exists()
        assert not (tmp_path / "manifest.json").exists()
        assert not (tmp_path / ".plan-tool").exists()
        assert not (tmp_path / "archive").exists()

    def test_live_plan_seeds_pass_references_preflight(self) -> None:
        seed_dir = Path(__file__).resolve().parents[1] / "plan-seeds"
        seed_paths = sorted(path for path in seed_dir.glob("*.md") if path.name != "README.md")
        assert seed_paths
        for seed_path in seed_paths:
            validate_from_existing_seed(seed_path.read_text(encoding="utf-8"))


def _direct_ready_file_source(*, steps: str = "") -> str:
    sections = [
        "## References\n\n- [API](https://example.test/api)\n",
    ]
    for heading in create_module._BODY_SECTIONS_CANONICAL_KEYS:
        sections.append(f"## {heading}\n\n{heading} body.\n")
    if steps:
        sections.append(steps)
    return "\n".join(sections)


def _patch_direct_route_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep direct-route tests focused on routing rather than risk prompts."""
    monkeypatch.setattr(
        create_module,
        "_propose_risk_profile_from_seed",
        lambda *_args, **_kwargs: create_module._RiskProfileProposal(
            profile=RiskProfile.STANDARD,
            rationale="direct test",
            minimum_profile=RiskProfile.STANDARD,
        ),
    )
    monkeypatch.setattr(
        create_module,
        "_resolve_risk_declaration",
        lambda proposal, **_kwargs: create_module._RiskDeclaration(
            profile=proposal.profile,
            rationale=proposal.rationale,
            mode="direct-test",
        ),
    )


class TestFileBackedSourceIntake:
    def test_file_backed_route_vocabulary_is_closed(self) -> None:
        assert {route.value for route in FileBackedSourceRoute} == {
            "direct",
            "normalized",
            "split",
            "refused",
        }

    @pytest.mark.parametrize(
        "source",
        [
            "# Draft\n",
            "## References\n\n",
            "## References\n\n_(TODO)_\n",
            (
                "## References\n\n- [One](https://example.test/one)\n\n"
                "## References\n\n- [Two](https://example.test/two)\n"
            ),
        ],
    )
    def test_classify_file_backed_source_requires_one_non_placeholder_references_heading(
        self, source: str
    ) -> None:
        with pytest.raises(CreateError, match=r"non-placeholder `## References`"):
            classify_file_backed_source(source)

    def test_classify_file_backed_source_ignores_frontmatter_and_fenced_reference_examples(
        self,
    ) -> None:
        with pytest.raises(CreateError, match=r"## References"):
            classify_file_backed_source(
                "---\n## References\n---\n\n```markdown\n"
                "## References\n\n- [Example](https://example.test/example)\n```\n"
            )

        intake = classify_file_backed_source(
            "---\n## References\n---\n\n```markdown\n"
            "## References\n\n- [Example](https://example.test/example)\n```\n\n"
            "## References\n\n- [Real](https://example.test/real)\n"
        )

        assert intake.references_ready is True

    def test_file_backed_unmatched_fence_is_a_no_route_preflight_refusal(
        self, tmp_path: Path
    ) -> None:
        source = tmp_path / "source.md"
        source_text = "## References\n\n- [API](https://example.test/api)\n\n```\n"

        with pytest.raises(CreateError, match="unmatched opening code fence"):
            create_plan(
                "unmatched-fence",
                repo_root=tmp_path,
                output_dir_override=tmp_path / "plans",
                manifest_path=tmp_path / "manifest.json",
                from_description=source_text,
                from_existing_path=source,
                claude_invoker=lambda _prompt: pytest.fail("model must not run"),
            )

        assert not (tmp_path / "plans").exists()
        assert not (tmp_path / ".plan-tool").exists()

    def test_preparation_route_does_not_parse_strict_steps(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            create_module,
            "extract_steps_from_canonical",
            lambda *_args, **_kwargs: pytest.fail(
                "preparation routes do not use strict source steps"
            ),
        )

        intake = classify_file_backed_source(
            "## References\n\n- [API](https://example.test/api)\n"
        )

        assert intake.needs_preparation is True
        assert intake.strict_steps is None

    def test_classify_file_backed_source_requires_each_normalized_direct_ready_body_heading_once(
        self,
    ) -> None:
        for heading in create_module._BODY_SECTIONS_CANONICAL_KEYS:
            complete = _direct_ready_file_source() + "\n"
            missing = complete.replace(
                f"## {heading}\n\n{heading} body.\n\n", ""
            )
            empty = complete.replace(
                f"## {heading}\n\n{heading} body.", f"## {heading}"
            )
            placeholder = complete.replace(
                f"{heading} body.", "_(TODO)_", 1
            )
            duplicate = complete + (
                f"\n## {heading}\n\nSecond {heading} body.\n"
            )

            assert classify_file_backed_source(missing).needs_preparation
            assert classify_file_backed_source(empty).needs_preparation
            assert classify_file_backed_source(placeholder).needs_preparation
            assert classify_file_backed_source(duplicate).needs_preparation

    @pytest.mark.parametrize("lookalike", ["Summary"])
    def test_classify_file_backed_source_rejects_heading_lookalikes_for_direct_readiness(
        self, lookalike: str
    ) -> None:
        source = _direct_ready_file_source().replace(
            "## Overview", f"## {lookalike}"
        )

        intake = classify_file_backed_source(source)

        assert intake.references_ready is True
        assert intake.direct_ready is False
        assert intake.needs_preparation is True

    @pytest.mark.parametrize("heading", ["overview", "Overview ##"])
    def test_classify_file_backed_source_normalizes_canonical_headings(
        self, heading: str
    ) -> None:
        source = _direct_ready_file_source().replace("## Overview", f"## {heading}")

        assert classify_file_backed_source(source).direct_ready is True

    def test_classify_file_backed_source_does_not_use_source_size_as_a_property(
        self,
    ) -> None:
        small = _direct_ready_file_source()
        large = small.replace("Overview body.", "Overview body. " + "x" * 20_000)

        assert classify_file_backed_source(small).direct_ready is True
        assert classify_file_backed_source(large).direct_ready is True

    def test_classify_file_backed_source_lifts_strict_steps_when_available(self) -> None:
        intake = classify_file_backed_source(
            _direct_ready_file_source(
                steps="## Steps\n\n### 1. Classify the source\n"
            )
        )

        assert intake.direct_ready is True
        assert intake.strict_steps is not None
        assert [step.title for step in intake.strict_steps] == ["Classify the source"]

    def test_classify_file_backed_source_keeps_direct_readiness_when_steps_are_not_strict(
        self,
    ) -> None:
        no_steps = classify_file_backed_source(_direct_ready_file_source())
        malformed_steps = classify_file_backed_source(
            _direct_ready_file_source(steps="## Steps\n\n### Phase one\n")
        )

        assert no_steps.direct_ready is True
        assert no_steps.strict_steps is None
        assert malformed_steps.direct_ready is True
        assert malformed_steps.strict_steps is None

    def test_create_plan_rejects_duplicate_references_before_every_invoker_or_write(
        self, tmp_path: Path
    ) -> None:
        source = tmp_path / "source.md"
        source.write_text(
            "## References\n\n- [One](https://example.test/one)\n\n"
            "## References\n\n- [Two](https://example.test/two)\n",
            encoding="utf-8",
        )

        with pytest.raises(CreateError, match=r"exactly one non-placeholder"):
            create_plan(
                "duplicate-references",
                repo_root=tmp_path,
                output_dir_override=tmp_path / "plans",
                manifest_path=tmp_path / "manifest.json",
                from_description=source.read_text(encoding="utf-8"),
                from_existing_path=source,
                claude_invoker=lambda _prompt: pytest.fail("model must not run"),
            )

        assert not (tmp_path / "plans").exists()
        assert not (tmp_path / "manifest.json").exists()
        assert not (tmp_path / ".plan-tool").exists()
        assert not (tmp_path / "archive").exists()

    def test_create_plan_file_backed_route_uses_empty_selected_provenance_source(
        self, tmp_path: Path
    ) -> None:
        source = tmp_path / "source.md"
        description = "## References\n\n- [Real](https://example.test/real)\n"

        with pytest.raises(CreateError, match=r"## References"):
            create_plan(
                "empty-provenance",
                repo_root=tmp_path,
                output_dir_override=tmp_path / "plans",
                manifest_path=tmp_path / "manifest.json",
                from_description=description,
                from_existing_path=source,
                seed_body="",
                claude_invoker=lambda _prompt: pytest.fail("model must not run"),
            )

        assert not (tmp_path / "plans").exists()
        assert not (tmp_path / "manifest.json").exists()

    def test_file_backed_preparation_refusal_stops_before_authoring_or_writes(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        source = tmp_path / "source.md"
        source.write_text(
            "Build the file-backed routing contract.\n\n"
            "## References\n\n"
            "- [Contract](https://example.test/contract)\n",
            encoding="utf-8",
        )
        preparation_calls: list[str] = []

        def invalid_preparation(prompt: str) -> str:
            preparation_calls.append(prompt)
            return "not preparation JSON"

        monkeypatch.setattr(
            create_module,
            "_propose_risk_profile_from_seed",
            lambda *_args, **_kwargs: pytest.fail(
                "refused preparation must stop before risk classification"
            ),
        )
        monkeypatch.setattr(
            create_module,
            "propose_steps_from_claude",
            lambda *_args, **_kwargs: pytest.fail(
                "refused preparation must stop before step proposal"
            ),
        )

        result = create_plan(
            "refused-preparation",
            repo_root=tmp_path,
            output_dir_override=tmp_path / "plans",
            manifest_path=tmp_path / "manifest.json",
            from_description=source.read_text(encoding="utf-8"),
            from_existing_path=source,
            yes=True,
            resume=False,
            distill=False,
            claude_invoker=invalid_preparation,
        )

        assert len(preparation_calls) == 2
        assert result.plan_path is None
        assert result.file_backed_route is FileBackedSourceRoute.REFUSED
        assert result.refusal_reason is not None
        assert "seed preparation remained invalid" in result.refusal_reason
        assert not (tmp_path / "plans").exists()
        assert not (tmp_path / "manifest.json").exists()

    @pytest.mark.parametrize("section_name", _PREPARATION_EVIDENCE_KEYS)
    @pytest.mark.parametrize(
        "unsupported_support",
        ("missing_text", "missing_spans", "invalid_spans"),
    )
    def test_normalized_evidence_gate_requires_each_evidence_only_section(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        section_name: str,
        unsupported_support: str,
    ) -> None:
        source = tmp_path / "source.md"
        source.write_text(
            "Build the file-backed routing contract.\n\n"
            "## References\n\n"
            "- [Contract](https://example.test/contract)\n",
            encoding="utf-8",
        )
        normalized = _normalized_outcome_for_test()
        assert normalized.sections is not None
        assert normalized.evidence_spans is not None
        if unsupported_support == "missing_text":
            normalized.sections[section_name] = None
        elif unsupported_support == "missing_spans":
            normalized.evidence_spans.pop(section_name)
        else:
            normalized.evidence_spans[section_name] = ((0, 0),)

        monkeypatch.setattr(
            create_module,
            "propose_distilled_seed_from_claude",
            lambda *_args, **_kwargs: normalized,
        )
        for authoring_call in (
            "_propose_risk_profile_from_seed",
            "propose_steps_from_claude",
            "propose_references_from_claude",
            "propose_body_sections",
            "_publish_create_plan",
            "_converge_create_plan",
        ):
            monkeypatch.setattr(
                create_module,
                authoring_call,
                lambda *_args, **_kwargs: pytest.fail(
                    "unsupported normalized evidence must stop before authoring"
                ),
            )

        result = create_plan(
            "unsupported-normalized-evidence",
            repo_root=tmp_path,
            output_dir_override=tmp_path / "plans",
            manifest_path=tmp_path / "manifest.json",
            from_description=source.read_text(encoding="utf-8"),
            from_existing_path=source,
            yes=True,
            resume=False,
            distill=False,
            claude_invoker=lambda _prompt: pytest.fail(
                "the normalized preparation result is already supplied"
            ),
        )

        assert result.plan_path is None
        assert result.file_backed_route is FileBackedSourceRoute.REFUSED
        assert result.refusal_reason is not None
        assert section_name in result.refusal_reason
        assert not (tmp_path / "plans").exists()
        assert not (tmp_path / "manifest.json").exists()

    def test_non_null_model_evidence_without_spans_is_refused(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        source = tmp_path / "source.md"
        source.write_text(
            "Build the file-backed routing contract.\n\n"
            "## References\n\n"
            "- [Contract](https://example.test/contract)\n",
            encoding="utf-8",
        )
        normalized = _normalized_outcome_for_test()
        assert normalized.sections is not None
        assert normalized.evidence_spans is not None
        normalized.sections["Risks"] = "Invented model evidence."
        normalized.evidence_spans["Risks"] = None
        monkeypatch.setattr(
            create_module,
            "propose_distilled_seed_from_claude",
            lambda *_args, **_kwargs: normalized,
        )
        monkeypatch.setattr(
            create_module,
            "_propose_risk_profile_from_seed",
            lambda *_args, **_kwargs: pytest.fail(
                "model text without spans must not reach risk classification"
            ),
        )

        result = create_plan(
            "model-evidence-without-spans",
            repo_root=tmp_path,
            output_dir_override=tmp_path / "plans",
            manifest_path=tmp_path / "manifest.json",
            from_description=source.read_text(encoding="utf-8"),
            from_existing_path=source,
            yes=True,
            resume=False,
            claude_invoker=lambda _prompt: pytest.fail(
                "the normalized preparation result is already supplied"
            ),
        )

        assert result.plan_path is None
        assert result.file_backed_route is FileBackedSourceRoute.REFUSED
        assert result.refusal_reason is not None
        assert "Risks" in result.refusal_reason
        assert not (tmp_path / "plans").exists()
        assert not (tmp_path / "manifest.json").exists()

    @pytest.mark.parametrize("iterate", (False, True))
    def test_unsupported_normalized_evidence_refuses_before_publication_in_both_modes(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        iterate: bool,
    ) -> None:
        source = tmp_path / "source.md"
        source.write_text(
            "Build the file-backed routing contract.\n\n"
            "## References\n\n"
            "- [Contract](https://example.test/contract)\n",
            encoding="utf-8",
        )
        normalized = _normalized_outcome_for_test()
        assert normalized.sections is not None
        assert normalized.evidence_spans is not None
        normalized.sections["Deferred"] = "An ungrounded deferred claim."
        normalized.evidence_spans.pop("Deferred", None)
        monkeypatch.setattr(
            create_module,
            "propose_distilled_seed_from_claude",
            lambda *_args, **_kwargs: normalized,
        )
        monkeypatch.setattr(
            create_module,
            "_converge_create_plan",
            lambda *_args, **_kwargs: pytest.fail(
                "unsupported normalized evidence must not enter convergence"
            ),
        )
        monkeypatch.setattr(
            create_module,
            "_publish_create_plan",
            lambda *_args, **_kwargs: pytest.fail(
                "unsupported normalized evidence must not publish"
            ),
        )
        result = create_plan(
            "unsupported-normalized-budget",
            repo_root=tmp_path,
            output_dir_override=tmp_path / "plans",
            manifest_path=tmp_path / "manifest.json",
            from_description=source.read_text(encoding="utf-8"),
            from_existing_path=source,
            yes=True,
            resume=False,
            budget=create_module.IterativeBudget(enabled=iterate),
            claude_invoker=lambda _prompt: pytest.fail(
                "the normalized preparation result is already supplied"
            ),
        )

        assert result.plan_path is None
        assert result.file_backed_route is FileBackedSourceRoute.REFUSED
        assert result.refusal_reason is not None
        assert "Deferred" in result.refusal_reason
        assert create_module._unsupported_evidence_refusal("Deferred") in result.refusal_reason
        assert not (tmp_path / "plans").exists()
        assert not (tmp_path / "manifest.json").exists()

    @pytest.mark.parametrize(
        "section", create_module._evidence_only_body_section_keys()
    )
    def test_unsupported_evidence_refusal_names_both_the_seed_edit_and_an_unchanged_rerun(
        self, section: str
    ) -> None:
        # The gate fires when preparation cites no source text, whether or not the
        # seed has the section, and a re-run prepares afresh; so both remedies hold.
        reason = create_module._unsupported_evidence_refusal(section)

        assert f"add a '## {section}' section" in reason
        assert "re-run unchanged" in reason

    @pytest.mark.parametrize("deferred", (None, "", "   "))
    def test_normalized_evidence_gate_allows_empty_optional_deferred(
        self,
        deferred: Optional[str],
    ) -> None:
        normalized = _normalized_outcome_for_test()
        assert normalized.sections is not None
        assert normalized.evidence_spans is not None
        normalized.sections["Deferred"] = deferred
        normalized.evidence_spans.pop("Deferred", None)

        assert (
            create_module._unsupported_normalized_evidence_section(
                normalized.sections,
                normalized.evidence_spans,
            )
            is None
        )

    @pytest.mark.parametrize("resume", [False, True])
    @pytest.mark.parametrize("separate_seed", [False, True])
    @pytest.mark.integration
    def test_ordinary_file_backed_seed_retains_obligations_without_roadmap_metadata(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        resume: bool,
        separate_seed: bool,
    ) -> None:
        source = tmp_path / "source.md"
        evidence_bodies = {
            section_name: f"{section_name} source evidence."
            for section_name in _PREPARATION_EVIDENCE_KEYS
        }
        evidence_bodies["Testing"] = "PROOF-31 requires an observed checkout result."
        evidence_bodies["Scope guardrails"] = (
            "AUTH-23 supplies the sibling prerequisite; do not implement auth here."
        )
        source_text = "Build the file-backed routing contract.\n\n" + "\n\n".join(
            f"## {section_name}\n\n{body}"
            for section_name, body in evidence_bodies.items()
        ) + "\n\n## References\n\n- `src/contract.py#anchor` — SOURCE-17 keeps the proof\n"
        source.write_text(
            source_text,
            encoding="utf-8",
        )
        source_lines = source_text.splitlines()
        normalized = create_module.DistillOutcome.normalized(
            {
                "Overview": "Derived overview.",
                "Problem statement": "Derived problem statement.",
                "Architecture": "Derived architecture.",
                **evidence_bodies,
            },
            {
                section_name: (
                    (source_lines.index(body) + 1, source_lines.index(body) + 1),
                )
                for section_name, body in evidence_bodies.items()
            },
        )
        monkeypatch.setattr(
            create_module,
            "propose_distilled_seed_from_claude",
            lambda *_args, **_kwargs: normalized,
        )
        monkeypatch.setattr(
            create_module,
            "_propose_risk_profile_from_seed",
            lambda *_args, **_kwargs: create_module._RiskProfileProposal(
                profile=RiskProfile.STANDARD,
                rationale="source-supported test",
                minimum_profile=RiskProfile.STANDARD,
            ),
        )
        monkeypatch.setattr(
            create_module,
            "_resolve_risk_declaration",
            lambda proposal, **_kwargs: create_module._RiskDeclaration(
                profile=proposal.profile,
                rationale=proposal.rationale,
                mode="source-supported-test",
            ),
        )
        def propose_steps(source_text, *_args, **_kwargs):
            for evidence_body in evidence_bodies.values():
                assert evidence_body in source_text
            assert "src/contract.py#anchor" in source_text
            assert "SOURCE-17 keeps the proof" in source_text
            assert "UNSELECTED" not in source_text
            return [Step(id=1, title="Keep source evidence")]

        monkeypatch.setattr(create_module, "propose_steps_from_claude", propose_steps)
        monkeypatch.setattr(
            create_module,
            "propose_references_from_claude",
            lambda *_args, **_kwargs: ReferenceResearchResult.from_references([
                Reference(title="Docs", url="https://example.test/generated")
            ]),
        )
        monkeypatch.setattr(
            create_module,
            "propose_body_sections",
            lambda *_args, **_kwargs: pytest.fail(
                "complete normalized evidence must skip body synthesis"
            ),
        )
        monkeypatch.setattr(
            create_module,
            "_review_step_change_types",
            lambda steps, **_kwargs: steps,
        )

        def review_concepts(tree, steps, **_kwargs):
            sources = {concept.title: concept.source for concept in tree.concepts}
            assert sources["overview"] == "Derived overview."
            assert sources["architecture"] == "Derived architecture."
            return tree, steps

        monkeypatch.setattr(
            create_module,
            "_review_create_concepts",
            review_concepts,
        )

        result = create_plan(
            "source-supported-normalized-evidence",
            repo_root=tmp_path,
            output_dir_override=tmp_path / "plans",
            manifest_path=tmp_path / "manifest.json",
            from_description=("UNSELECTED\n\n## References\n\nwrong.py"
                              if separate_seed else source_text),
            seed_body=source_text if separate_seed else None,
            from_existing_path=source,
            yes=True,
            resume=resume,
            offer_intents=False,
            claude_invoker=lambda _prompt: pytest.fail(
                "the normalized preparation result is already supplied"
            ),
        )

        assert result.plan_path is not None
        body = result.plan_path.read_text(encoding="utf-8")
        assert "https://example.test/generated" in body
        assert "src/contract.py#anchor" in body
        assert "SOURCE-17 keeps the proof" in body
        assert "UNSELECTED" not in body
        assert "Derived overview." in body
        assert "Derived architecture." in body
        for evidence_body in evidence_bodies.values():
            assert evidence_body in body

    def test_inline_distill_keeps_iteration_edits_outside_preparation_protection(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        normalized = _normalized_outcome_for_test()
        monkeypatch.setattr(
            create_module,
            "propose_distilled_seed_from_claude",
            lambda *_args, **_kwargs: normalized,
        )
        monkeypatch.setattr(
            create_module,
            "_propose_risk_profile_from_seed",
            lambda *_args, **_kwargs: create_module._RiskProfileProposal(
                profile=RiskProfile.STANDARD,
                rationale="inline test",
                minimum_profile=RiskProfile.STANDARD,
            ),
        )
        monkeypatch.setattr(
            create_module,
            "_resolve_risk_declaration",
            lambda proposal, **_kwargs: create_module._RiskDeclaration(
                profile=proposal.profile,
                rationale=proposal.rationale,
                mode="inline-test",
            ),
        )
        monkeypatch.setattr(
            create_module,
            "propose_steps_from_claude",
            lambda *_args, **_kwargs: [Step(id=1, title="Keep iteration edit")],
        )
        monkeypatch.setattr(
            create_module,
            "propose_references_from_claude",
            lambda *_args, **_kwargs: ReferenceResearchResult.from_references([]),
        )
        monkeypatch.setattr(
            create_module,
            "_review_step_change_types",
            lambda steps, **_kwargs: steps,
        )
        monkeypatch.setattr(
            create_module,
            "_review_create_concepts",
            lambda tree, steps, **_kwargs: (tree, steps),
        )
        collect_calls = {"count": 0}

        def collect(*_args, **_kwargs):
            collect_calls["count"] += 1
            return [_rec("inline-edit")] if collect_calls["count"] == 1 else []

        monkeypatch.setattr(create_module, "collect_deterministic_findings", collect)

        def apply(plan_path: Path, **_kwargs) -> _ApplyFindingResult:
            assert create_module._patch_plan_body_section(
                plan_path, "Risks", "iteration-owned edit"
            )
            return _stub_apply_result()

        monkeypatch.setattr(create_module, "apply_finding", apply)

        result = create_plan(
            "inline-distill-edits",
            repo_root=tmp_path,
            output_dir_override=tmp_path / "plans",
            manifest_path=tmp_path / "manifest.json",
            from_description="inline source that needs distillation",
            yes=True,
            resume=False,
            offer_intents=False,
            distill=True,
            budget=_IterativeBudget(enabled=True, max_iterations=2),
            claude_invoker=lambda _prompt: pytest.fail("distill result is stubbed"),
        )

        assert result.file_backed_route is None
        assert result.plan_path is not None
        assert "iteration-owned edit" in result.plan_path.read_text(encoding="utf-8")

    @pytest.mark.parametrize(
        ("remove_risks_heading", "expected_risks"),
        [
            (False, "Risks prepared body."),
            (True, None),
        ],
        ids=("rewritten", "removed"),
    )
    def test_interrupted_normalized_iteration_restores_protected_evidence(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        remove_risks_heading: bool,
        expected_risks: Optional[str],
    ) -> None:
        source = tmp_path / "source.md"
        source.write_text(
            "## References\n\n- [API](https://example.test/api)\n",
            encoding="utf-8",
        )
        normalized = _normalized_outcome_for_test()
        monkeypatch.setattr(
            create_module,
            "propose_distilled_seed_from_claude",
            lambda *_args, **_kwargs: normalized,
        )
        monkeypatch.setattr(
            create_module,
            "_propose_risk_profile_from_seed",
            lambda *_args, **_kwargs: create_module._RiskProfileProposal(
                profile=RiskProfile.STANDARD,
                rationale="normalized test",
                minimum_profile=RiskProfile.STANDARD,
            ),
        )
        monkeypatch.setattr(
            create_module,
            "_resolve_risk_declaration",
            lambda proposal, **_kwargs: create_module._RiskDeclaration(
                profile=proposal.profile,
                rationale=proposal.rationale,
                mode="normalized-test",
            ),
        )
        monkeypatch.setattr(
            create_module,
            "propose_steps_from_claude",
            lambda *_args, **_kwargs: [Step(id=1, title="Protect evidence")],
        )
        monkeypatch.setattr(
            create_module,
            "propose_references_from_claude",
            lambda *_args, **_kwargs: ReferenceResearchResult.from_references([]),
        )
        monkeypatch.setattr(
            create_module,
            "_review_step_change_types",
            lambda steps, **_kwargs: steps,
        )
        monkeypatch.setattr(
            create_module,
            "_review_create_concepts",
            lambda tree, steps, **_kwargs: (tree, steps),
        )
        monkeypatch.setattr(
            create_module,
            "collect_deterministic_findings",
            lambda *_args, **_kwargs: [_rec("restore-on-failure")],
        )

        def rewrite_then_fail(plan_path: Path, **_kwargs) -> _ApplyFindingResult:
            if remove_risks_heading:
                text = plan_path.read_text(encoding="utf-8")
                risks_start = text.index("## Risks\n")
                testing_start = text.index("## Testing\n", risks_start)
                plan_path.write_text(
                    text[:risks_start] + text[testing_start:], encoding="utf-8"
                )
            else:
                assert create_module._patch_plan_body_section(
                    plan_path, "Risks", "model-rewritten evidence"
                )
            assert create_module._patch_plan_body_section(
                plan_path, "References", "- Generated research"
            )
            raise RuntimeError("apply interrupted")

        monkeypatch.setattr(create_module, "apply_finding", rewrite_then_fail)

        with pytest.raises(
            CreateError, match="registered but finalization is incomplete"
        ) as error_info:
            create_plan(
                "restore-normalized-evidence",
                repo_root=tmp_path,
                output_dir_override=tmp_path / "plans",
                manifest_path=tmp_path / "manifest.json",
                from_description=source.read_text(encoding="utf-8"),
                from_existing_path=source,
                yes=True,
                resume=False,
                offer_intents=False,
                budget=_IterativeBudget(enabled=True, max_iterations=2),
                claude_invoker=lambda _prompt: pytest.fail(
                    "distill result is stubbed"
                ),
            )

        assert "apply interrupted" in str(error_info.value)
        assert (
            "validated evidence section 'Risks' disappeared"
            not in str(error_info.value)
        )
        plan_path = next((tmp_path / "plans").glob("*.md"))
        body = plan_path.read_text(encoding="utf-8")
        assert "https://example.test/api" in body
        assert "Generated research" in body
        if expected_risks is None:
            assert "## Risks" not in body
        else:
            assert expected_risks in body
            assert "model-rewritten evidence" not in body

    def test_cmd_create_preflight_uses_empty_selected_provenance_source(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli import app as cli_module

        (tmp_path / ".git").mkdir()
        source = tmp_path / "source.md"
        source.write_text(
            "## References\n\n- [Real](https://example.test/real)\n",
            encoding="utf-8",
        )
        monkeypatch.setattr("plan_tool.cli.authoring._read_seed_body", lambda *_: "")
        monkeypatch.setattr(
            "plan_tool.cli.authoring.resolve_create_slug",
            lambda *_args, **_kwargs: pytest.fail("slug resolution must not run"),
        )
        monkeypatch.setattr(
            "plan_tool.cli.authoring.create_plan",
            lambda *_args, **_kwargs: pytest.fail("create must not run"),
        )
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(
            ["create", "empty-provenance", "--from-existing", str(source)]
        )

        assert rc == 2
        assert not (tmp_path / ".plan-tool").exists()

    def test_create_plan_without_from_existing_path_keeps_inline_input_outside_file_backed_preflight(
        self, tmp_path: Path
    ) -> None:
        with pytest.raises(CreateError, match="invalid slug"):
            create_plan(
                "not a slug",
                repo_root=tmp_path,
                from_description="Inline prose without a References heading.",
                claude_invoker=lambda _prompt: pytest.fail("model must not run"),
            )

    @pytest.mark.parametrize("distill", [False, True])
    def test_direct_single_assesses_selected_raw_source_once(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, distill: bool
    ) -> None:
        _patch_direct_route_metadata(monkeypatch)
        raw_source = _direct_ready_file_source(
            steps="## Steps\n\n### 1. Preserve source authority\n"
        )
        assessed: list[str] = []
        monkeypatch.setattr(
            create_module,
            "assess_direct_source_split_from_claude",
            lambda source, *_args, **_kwargs: (
                assessed.append(source) or DirectSplitAssessment()
            ),
        )
        monkeypatch.setattr(
            create_module,
            "propose_distilled_seed_from_claude",
            lambda *_args, **_kwargs: pytest.fail("direct input must not distill"),
        )

        result = create_plan(
            "direct-raw",
            repo_root=tmp_path,
            output_dir_override=tmp_path / "plans",
            manifest_path=tmp_path / "manifest.json",
            from_description="unselected provenance prose",
            from_existing_path=tmp_path / "source.md",
            seed_body=raw_source,
            yes=True,
            resume=False,
            distill=distill,
            offer_intents=False,
            claude_invoker=lambda _prompt: pytest.fail("unexpected model call"),
        )

        assert assessed == [raw_source]
        assert result.plan_path is not None
        assert result.file_backed_route is FileBackedSourceRoute.DIRECT

    def test_direct_single_preserves_source_references_without_generic_authoring(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_direct_route_metadata(monkeypatch)
        raw_source = _direct_ready_file_source(
            steps="## Steps\n\n### 1. Preserve source authority\n"
        ).replace("Overview body.", "AUTHORITATIVE OVERVIEW.")
        monkeypatch.setattr(
            create_module,
            "assess_direct_source_split_from_claude",
            lambda *_args, **_kwargs: DirectSplitAssessment(),
        )
        monkeypatch.setattr(
            create_module,
            "propose_references_from_claude",
            lambda *_args, **_kwargs: pytest.fail("direct input must not research references"),
        )
        monkeypatch.setattr(
            create_module,
            "propose_body_sections",
            lambda *_args, **_kwargs: pytest.fail("direct input must not synthesize body"),
        )

        result = create_plan(
            "direct-authority",
            repo_root=tmp_path,
            output_dir_override=tmp_path / "plans",
            manifest_path=tmp_path / "manifest.json",
            from_description=raw_source,
            from_existing_path=tmp_path / "source.md",
            yes=True,
            resume=False,
            offer_intents=False,
            claude_invoker=lambda _prompt: pytest.fail("unexpected model call"),
        )

        assert result.plan_path is not None
        body = result.plan_path.read_text(encoding="utf-8")
        assert "AUTHORITATIVE OVERVIEW." in body
        assert "## References\n\n- [API](https://example.test/api)" in body

    def test_direct_single_uses_lifted_strict_steps_without_step_proposal(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_direct_route_metadata(monkeypatch)
        raw_source = _direct_ready_file_source(
            steps="## Steps\n\n### 1. Keep lifted steps\n"
        )
        monkeypatch.setattr(
            create_module,
            "assess_direct_source_split_from_claude",
            lambda *_args, **_kwargs: DirectSplitAssessment(),
        )
        monkeypatch.setattr(
            create_module,
            "propose_steps_from_claude",
            lambda *_args, **_kwargs: pytest.fail("lifted steps must bypass proposal"),
        )

        result = create_plan(
            "direct-lifted",
            repo_root=tmp_path,
            output_dir_override=tmp_path / "plans",
            manifest_path=tmp_path / "manifest.json",
            from_description=raw_source,
            from_existing_path=tmp_path / "source.md",
            yes=True,
            resume=False,
            offer_intents=False,
            claude_invoker=lambda _prompt: pytest.fail("unexpected model call"),
        )

        assert result.plan_path is not None
        assert parse_plan(result.plan_path).steps[0].title == "Keep lifted steps"

    def test_direct_single_proposes_steps_only_when_lifted_steps_are_absent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_direct_route_metadata(monkeypatch)
        raw_source = _direct_ready_file_source()
        proposed_from: list[str] = []
        monkeypatch.setattr(
            create_module,
            "assess_direct_source_split_from_claude",
            lambda *_args, **_kwargs: DirectSplitAssessment(),
        )
        monkeypatch.setattr(
            create_module,
            "propose_steps_from_claude",
            lambda source, *_args, **_kwargs: (
                proposed_from.append(source)
                or [Step(id=1, title="Proposed direct step")]
            ),
        )

        result = create_plan(
            "direct-proposed-step",
            repo_root=tmp_path,
            output_dir_override=tmp_path / "plans",
            manifest_path=tmp_path / "manifest.json",
            from_description=raw_source,
            from_existing_path=tmp_path / "source.md",
            yes=True,
            resume=False,
            offer_intents=False,
            claude_invoker=lambda _prompt: pytest.fail("unexpected model call"),
        )

        assert result.plan_path is not None
        assert proposed_from == [raw_source]

    def test_direct_split_returns_shared_proposal_without_publication(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        raw_source = _direct_ready_file_source()
        monkeypatch.setattr(
            create_module,
            "assess_direct_source_split_from_claude",
            lambda *_args, **_kwargs: DirectSplitAssessment(
                split=[
                    create_module.SplitProposalEntry("One", "one", "first"),
                    create_module.SplitProposalEntry("Two", "two", "second"),
                ]
            ),
        )
        monkeypatch.setattr(
            create_module,
            "_propose_risk_profile_from_seed",
            lambda *_args, **_kwargs: pytest.fail("split must not continue create"),
        )

        result = create_plan(
            "direct-split",
            repo_root=tmp_path,
            output_dir_override=tmp_path / "plans",
            manifest_path=tmp_path / "manifest.json",
            from_description=raw_source,
            from_existing_path=tmp_path / "source.md",
            yes=True,
            resume=False,
            claude_invoker=lambda _prompt: pytest.fail("assessment was patched"),
        )

        assert result.plan_path is None
        assert result.split_proposal is not None
        assert result.file_backed_route is FileBackedSourceRoute.SPLIT
        assert not (tmp_path / "plans").exists()
        assert not (tmp_path / "manifest.json").exists()

    def test_direct_invalid_assessment_fails_closed_after_one_call(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        raw_source = _direct_ready_file_source()
        calls: list[str] = []

        def invalid_assessment(prompt: str) -> str:
            calls.append(prompt)
            return '{"outcome":"single","sections":{"Overview":"replacement"}}'

        result = create_plan(
            "direct-invalid",
            repo_root=tmp_path,
            output_dir_override=tmp_path / "plans",
            manifest_path=tmp_path / "manifest.json",
            from_description=raw_source,
            from_existing_path=tmp_path / "source.md",
            yes=True,
            resume=False,
            claude_invoker=invalid_assessment,
        )

        assert len(calls) == 1
        assert result.plan_path is None
        assert result.file_backed_route is FileBackedSourceRoute.REFUSED
        assert result.refusal_reason is not None
        assert "assessment is invalid" in result.refusal_reason
        assert not (tmp_path / "plans").exists()
        assert not (tmp_path / "manifest.json").exists()

    def test_direct_single_bypasses_convergence_and_scope_body_writers(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_direct_route_metadata(monkeypatch)
        raw_source = _direct_ready_file_source(
            steps="## Steps\n\n### 1. Keep direct text\n"
        ).replace("Out of scope body.", "SOURCE SCOPE BOUNDARY.")
        monkeypatch.setattr(
            create_module,
            "assess_direct_source_split_from_claude",
            lambda *_args, **_kwargs: DirectSplitAssessment(),
        )
        monkeypatch.setattr(
            create_module,
            "_converge_create_plan",
            lambda *_args, **_kwargs: pytest.fail("direct route must bypass convergence"),
        )
        monkeypatch.setattr(
            create_module,
            "render_scope_decisions",
            lambda *_args, **_kwargs: pytest.fail("direct source must keep scope prose"),
        )
        monkeypatch.setattr(create_module, "_has_approved_concepts", lambda *_args: True)
        monkeypatch.setattr(
            create_module,
            "synchronize_concepts",
            lambda *_args, **_kwargs: pytest.fail("direct source must not synchronize body"),
        )

        result = create_plan(
            "direct-no-converge",
            repo_root=tmp_path,
            output_dir_override=tmp_path / "plans",
            manifest_path=tmp_path / "manifest.json",
            from_description=raw_source,
            from_existing_path=tmp_path / "source.md",
            yes=True,
            resume=False,
            budget=create_module.IterativeBudget(enabled=True),
            offer_intents=False,
            claude_invoker=lambda _prompt: pytest.fail("unexpected model call"),
        )

        assert result.plan_path is not None
        assert "SOURCE SCOPE BOUNDARY." in result.plan_path.read_text(encoding="utf-8")


class TestBuildResearchContext:
    def test_includes_title_and_step_titles(self) -> None:
        steps = [
            Step(id=1, title="Wire SQS consumer", files=["amplify/lambda/x.ts"]),
            Step(id=2, title="Add DynamoDB GSI", files=[]),
        ]
        ctx = _build_research_context("My Plan", steps)
        assert "My Plan" in ctx
        assert "Wire SQS consumer" in ctx
        assert "Add DynamoDB GSI" in ctx
        assert "amplify/lambda/x.ts" in ctx


def _write_roadmap_research_source(
    tmp_path: Path,
    *,
    hosting: tuple[object, ...] = (),
    stores: tuple[object, ...] = (),
    domain_text: str | None = None,
    constraints_text: str | None = None,
    publish: bool = True,
):
    """Publish the accepted root version a tracked source's research targets read."""
    from plan_tool.roadmap_artifacts import (
        ComponentsArtifact,
        ConstraintsArtifact,
        PlansArtifact,
        render_components_artifact,
        render_constraints_artifact,
        render_plans_artifact,
        roadmap_dir,
    )
    from plan_tool.roadmap_seed_state import TrackedSeedLocation, seed_state_path
    from tests.roadmap_accepted_fixtures import publish_accepted_root, with_minimal_upstream

    plans_dir = tmp_path / "plans"
    slug = "chosen"
    root = roadmap_dir(plans_dir, slug)
    root.mkdir(parents=True)
    if publish:
        constraints = constraints_text or render_constraints_artifact(
            ConstraintsArtifact(
                dispositions=(),
                constraints=(),
                decisions=(),
                body="# Constraints\n",
                hosting=hosting,
            )
        )
        components = render_components_artifact(
            ComponentsArtifact(
                system_patterns=(),
                component_patterns=(),
                components=(),
                decisions=(),
                body="# Components\n",
                stores=stores,
            )
        )
        plans = render_plans_artifact(
            PlansArtifact(
                plans=(), ordering=(), assumptions=(), decisions=(), body="# Roadmap\n"
            )
        )
        domain = domain_text if domain_text is not None else with_minimal_upstream("")[0]
        publish_accepted_root(plans_dir, slug, (domain, constraints, components, plans))
    return TrackedSeedLocation(
        plan_id="selected-plan",
        roadmap_slug=slug,
        state_path=seed_state_path(root),
        via_marker=False,
    )


class TestTrackedRoadmapReferences:
    def test_tracked_roadmap_source_selects_hosting_and_store_products_in_source_order(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.create import _load_roadmap_research_targets
        from plan_tool.roadmap_artifacts import HostingRow, StoreRow

        location = _write_roadmap_research_source(
            tmp_path,
            hosting=(
                HostingRow("host-a", "compute", "managed", "Platform A"),
                HostingRow("host-b", "compute", "managed", "Platform B"),
            ),
            stores=(
                StoreRow("store-a", "cache", "shared", "Store A"),
                StoreRow("store-b", "sql", "shared", "Store B"),
            ),
        )

        targets = _load_roadmap_research_targets(location)

        assert [(target.token, target.product) for target in targets] == [
            ("hosting-1", "Platform A"),
            ("hosting-2", "Platform B"),
            ("stores-1", "Store A"),
            ("stores-2", "Store B"),
        ]

    def test_research_targets_come_from_accepted_version_not_stale_top_level_files(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.create import _load_roadmap_research_targets
        from plan_tool.roadmap_artifacts import (
            ComponentsArtifact,
            ConstraintsArtifact,
            HostingRow,
            StoreRow,
            components_path,
            constraints_path,
            render_components_artifact,
            render_constraints_artifact,
        )

        location = _write_roadmap_research_source(
            tmp_path,
            hosting=(HostingRow("host-a", "compute", "managed", "Head Platform"),),
            stores=(StoreRow("store-a", "cache", "shared", "Head Store"),),
        )
        plans_dir = tmp_path / "plans"
        constraints_path(plans_dir, "chosen").write_text(
            render_constraints_artifact(
                ConstraintsArtifact(
                    dispositions=(),
                    constraints=(),
                    decisions=(),
                    body="# Stale\n",
                    hosting=(HostingRow("old", "compute", "managed", "Stale Platform"),),
                )
            ),
            encoding="utf-8",
        )
        components_path(plans_dir, "chosen").write_text(
            render_components_artifact(
                ComponentsArtifact(
                    system_patterns=(),
                    component_patterns=(),
                    components=(),
                    decisions=(),
                    body="# Stale\n",
                    stores=(StoreRow("old", "cache", "shared", "Stale Store"),),
                )
            ),
            encoding="utf-8",
        )

        targets = _load_roadmap_research_targets(location)

        assert [target.product for target in targets] == ["Head Platform", "Head Store"]

    def test_research_targets_follow_a_head_that_moved_past_the_root(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.create import _load_roadmap_research_targets
        from plan_tool.roadmap_artifacts import (
            ComponentsArtifact,
            ConstraintsArtifact,
            HostingRow,
            PlansArtifact,
            StoreRow,
            render_components_artifact,
            render_constraints_artifact,
            render_plans_artifact,
        )
        from tests.roadmap_accepted_fixtures import (
            advance_accepted_head,
            with_minimal_upstream,
        )

        location = _write_roadmap_research_source(
            tmp_path,
            hosting=(HostingRow("host-a", "compute", "managed", "Root Platform"),),
        )
        advance_accepted_head(
            tmp_path / "plans",
            "chosen",
            (
                with_minimal_upstream("")[0],
                render_constraints_artifact(
                    ConstraintsArtifact(
                        dispositions=(),
                        constraints=(),
                        decisions=(),
                        body="# Constraints\n",
                        hosting=(HostingRow("host-b", "compute", "managed", "Moved Platform"),),
                    )
                ),
                render_components_artifact(
                    ComponentsArtifact(
                        system_patterns=(),
                        component_patterns=(),
                        components=(),
                        decisions=(),
                        body="# Components\n",
                        stores=(StoreRow("store-b", "sql", "shared", "Moved Store"),),
                    )
                ),
                render_plans_artifact(
                    PlansArtifact(
                        plans=(), ordering=(), assumptions=(), decisions=(), body="# R\n"
                    )
                ),
            ),
        )

        targets = _load_roadmap_research_targets(location)

        assert [target.product for target in targets] == ["Moved Platform", "Moved Store"]

    def test_no_accepted_head_refuses_before_any_row_is_read(self, tmp_path: Path) -> None:
        from plan_tool.create import _load_roadmap_research_targets
        from plan_tool.roadmap_seed_manifest import NoPublishedRoadmapVersionError

        location = _write_roadmap_research_source(tmp_path, publish=False)

        with pytest.raises(NoPublishedRoadmapVersionError, match="no published version"):
            _load_roadmap_research_targets(location)

    def test_corrupt_accepted_head_is_a_create_error_not_a_traceback(self, tmp_path: Path) -> None:
        from plan_tool.create import CreateError, _load_roadmap_research_targets
        from plan_tool.roadmap_versions import accepted_head_path

        location = _write_roadmap_research_source(tmp_path)
        accepted_head_path(tmp_path / "plans", "chosen").write_text("{not json", encoding="utf-8")

        with pytest.raises(CreateError, match="accepted roadmap version for 'chosen'"):
            _load_roadmap_research_targets(location)

    def test_unparseable_constraints_member_is_a_create_error(self, tmp_path: Path) -> None:
        from plan_tool.create import CreateError, _load_roadmap_research_targets

        location = _write_roadmap_research_source(
            tmp_path, constraints_text="not a constraints artifact\n"
        )

        with pytest.raises(CreateError, match="'chosen'"):
            _load_roadmap_research_targets(location)

    def test_unparseable_domain_member_does_not_block_target_loading(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.create import _load_roadmap_research_targets
        from plan_tool.roadmap_artifacts import HostingRow

        location = _write_roadmap_research_source(
            tmp_path,
            hosting=(HostingRow("host-a", "compute", "managed", "Platform A"),),
            domain_text="not a domain artifact\n",
        )

        targets = _load_roadmap_research_targets(location)

        assert [target.product for target in targets] == ["Platform A"]

    def test_roadmap_research_target_trims_products_and_preserves_origin_description_and_disclosure(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.create import _load_roadmap_research_targets
        from plan_tool.roadmap_artifacts import (
            HostingRow,
            ResearchDisclosure,
            StoreRow,
        )

        location = _write_roadmap_research_source(
            tmp_path,
            hosting=(
                HostingRow("blank", "compute", "managed", "   "),
                HostingRow(
                    "keep",
                    "compute",
                    "managed",
                    "  Private platform  ",
                    "Runs the internal API.",
                    ResearchDisclosure.LOCAL,
                ),
            ),
            stores=(StoreRow("store", "sql", "shared", "  PostgreSQL  "),),
        )

        targets = _load_roadmap_research_targets(location)

        assert [(target.token, target.product) for target in targets] == [
            ("hosting-2", "Private platform"),
            ("stores-1", "PostgreSQL"),
        ]
        assert targets[0].origin == "02-constraints.md hosting row 2 (id 'keep')"
        assert targets[0].description == "Runs the internal API."
        assert targets[0].research_disclosure == ResearchDisclosure.LOCAL

    def test_roadmap_research_target_tokens_keep_duplicate_products_and_row_ids_distinct(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.create import _load_roadmap_research_targets
        from plan_tool.roadmap_artifacts import HostingRow, StoreRow

        location = _write_roadmap_research_source(
            tmp_path,
            hosting=(
                HostingRow("duplicate", "compute", "managed", "Shared product"),
                HostingRow("duplicate", "compute", "managed", "Shared product"),
            ),
            stores=(StoreRow("duplicate", "sql", "shared", "Shared product"),),
        )

        targets = _load_roadmap_research_targets(location)

        assert [target.token for target in targets] == [
            "hosting-1", "hosting-2", "stores-1"
        ]
        assert [target.product for target in targets] == ["Shared product"] * 3

    def test_tracked_roadmap_research_prompt_requests_only_external_targets(self) -> None:
        from plan_tool.create import (
            RoadmapResearchTarget,
            propose_roadmap_references_from_claude,
        )
        from plan_tool.roadmap_artifacts import ResearchDisclosure

        seen: list[str] = []
        targets = (
            RoadmapResearchTarget(
                "hosting-1", "Public product", "02-constraints.md hosting row 1",
                "private external description", ResearchDisclosure.EXTERNAL,
            ),
            RoadmapResearchTarget(
                "stores-1", "Private product", "private/path row 1",
                "private local description", ResearchDisclosure.LOCAL,
            ),
        )
        verdicts = propose_roadmap_references_from_claude(
            targets,
            lambda prompt: seen.append(prompt) or json.dumps([
                {"token": "hosting-1", "references": []},
            ]),
            reporter=_RecordingReporter(),
        )

        assert [verdict.target_token for verdict in verdicts] == [
            "hosting-1", "stores-1"
        ]
        prompt = seen[0]
        assert "hosting-1" in prompt and "Public product" in prompt
        for private_value in (
            "Private product", "private/path", "private external description",
            "private local description", "02-constraints.md",
        ):
            assert private_value not in prompt

    def test_local_or_unmarked_target_requires_description_without_invoking_research(
        self,
    ) -> None:
        from plan_tool.create import (
            CreateError,
            RoadmapResearchTarget,
            propose_roadmap_references_from_claude,
        )
        from plan_tool.roadmap_artifacts import ResearchDisclosure

        invocations = 0

        def invoker(_prompt: str) -> str:
            nonlocal invocations
            invocations += 1
            return "[]"

        with pytest.raises(CreateError, match="no description"):
            propose_roadmap_references_from_claude(
                (
                    RoadmapResearchTarget(
                        "hosting-1", "Undisclosed", "origin", None, None
                    ),
                    RoadmapResearchTarget(
                        "stores-1", "External", "origin", None,
                        ResearchDisclosure.EXTERNAL,
                    ),
                ),
                invoker,
            )
        assert invocations == 0

        verdicts = propose_roadmap_references_from_claude(
            (
                RoadmapResearchTarget(
                    "hosting-1", "Undisclosed", "origin", "Use the local service.",
                    None,
                ),
            ),
            invoker,
        )
        assert invocations == 0
        assert verdicts[0].is_local and verdicts[0].references == ()

    def test_all_local_targets_skip_research_without_generic_fallback(self) -> None:
        from plan_tool.create import (
            RoadmapResearchTarget,
            propose_roadmap_references_from_claude,
        )
        from plan_tool.roadmap_artifacts import ResearchDisclosure

        verdicts = propose_roadmap_references_from_claude(
            (
                RoadmapResearchTarget(
                    "hosting-1", "Internal host", "host origin", "Host description",
                    ResearchDisclosure.LOCAL,
                ),
                RoadmapResearchTarget(
                    "stores-1", "Internal store", "store origin", "Store description",
                    None,
                ),
            ),
            lambda _prompt: (_ for _ in ()).throw(
                AssertionError("local targets must not invoke research")
            ),
        )

        assert [verdict.is_local for verdict in verdicts] == [True, True]

    def test_all_local_snapshot_skips_generic_references_during_create(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool import create as create_module
        from plan_tool.roadmap_artifacts import HostingRow, ResearchDisclosure

        location = _write_roadmap_research_source(
            tmp_path,
            hosting=(HostingRow(
                "host", "compute", "managed", "Internal host", "Use the local host.",
                ResearchDisclosure.LOCAL,
            ),),
        )
        monkeypatch.setattr(
            create_module,
            "propose_references_from_claude",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("selected local rows must not use generic research")
            ),
        )

        result = create_plan(
            "selected-local",
            repo_root=tmp_path,
            output_dir_override=tmp_path / "output",
            from_description=_CANONICAL_BODY,
            tracked_seed_location=location,
            yes=True,
            offer_intents=False,
            synthesize_body=False,
            fetch_docs=False,
            allow_placeholder_body=True,
        )

        assert result.plan_path is not None
        body = result.plan_path.read_text(encoding="utf-8")
        assert _ROADMAP_NO_SOURCE_REFERENCES_BODY in body

    def test_roadmap_target_without_sources_or_description_refuses_before_publication(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.create import CreateError, create_plan
        from plan_tool.roadmap_artifacts import HostingRow, ResearchDisclosure

        location = _write_roadmap_research_source(
            tmp_path,
            hosting=(HostingRow(
                "host", "compute", "managed", "Ungrounded host", None,
                ResearchDisclosure.EXTERNAL,
            ),),
        )
        output_dir = tmp_path / "output"
        manifest = tmp_path / "manifest.json"
        output_dir.mkdir()
        collision = output_dir / "2-selected-refusal.md"
        collision.write_text("existing collision\n", encoding="utf-8")

        with pytest.raises(CreateError) as exc:
            create_plan(
                "selected-refusal",
                repo_root=tmp_path,
                output_dir_override=output_dir,
                manifest_path=manifest,
                from_description=_CANONICAL_BODY,
                tracked_seed_location=location,
                yes=True,
                replace_on_collision=True,
                offer_intents=False,
                synthesize_body=False,
                fetch_docs=False,
                allow_placeholder_body=True,
                claude_invoker=lambda _prompt: json.dumps([
                    {"token": "hosting-1", "references": []},
                ]),
            )

        message = str(exc.value)
        assert "Ungrounded host" in message
        assert "02-constraints.md hosting row 1" in message
        assert "add a description" in message
        assert "repair source evidence" in message
        assert collision.read_text(encoding="utf-8") == "existing collision\n"
        assert not (output_dir / "archive").exists()
        assert not manifest.exists()

    def test_roadmap_refusal_never_prompts_on_noninteractive_stdin(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import builtins

        from plan_tool import create as create_module
        from plan_tool.create import CreateError, create_plan
        from plan_tool.roadmap_artifacts import HostingRow, ResearchDisclosure

        location = _write_roadmap_research_source(
            tmp_path,
            hosting=(HostingRow(
                "host", "compute", "managed", "Ungrounded host", None,
                ResearchDisclosure.EXTERNAL,
            ),),
        )
        original_input = builtins.input
        monkeypatch.setattr(create_module, "input", original_input, raising=False)
        monkeypatch.setattr(
            builtins,
            "input",
            lambda _prompt: pytest.fail("roadmap refusal must not prompt"),
        )
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)

        with pytest.raises(CreateError, match="Ungrounded host"):
            create_plan(
                "selected-noninteractive-refusal",
                repo_root=tmp_path,
                output_dir_override=tmp_path / "output",
                from_description=_CANONICAL_BODY,
                tracked_seed_location=location,
                yes=True,
                offer_intents=False,
                synthesize_body=False,
                fetch_docs=False,
                allow_placeholder_body=True,
                claude_invoker=lambda _prompt: json.dumps([
                    {"token": "hosting-1", "references": []},
                ]),
            )

    def test_roadmap_target_description_allows_empty_verdict_without_quality_check(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.create import create_plan
        from plan_tool.roadmap_artifacts import HostingRow, ResearchDisclosure

        location = _write_roadmap_research_source(
            tmp_path,
            hosting=(HostingRow(
                "host", "compute", "managed", "Description-backed host", "x",
                ResearchDisclosure.EXTERNAL,
            ),),
        )
        complete_seed_without_references = _CANONICAL_FULL_SEED.replace(
            "## References\n\n- [Ref](https://example.com) — example reference.\n\n",
            "",
        )

        result = create_plan(
            "selected-description",
            repo_root=tmp_path,
            output_dir_override=tmp_path / "output",
            from_description=complete_seed_without_references,
            tracked_seed_location=location,
            yes=True,
            offer_intents=False,
            synthesize_body=False,
            fetch_docs=False,
            claude_invoker=lambda _prompt: json.dumps([
                {"token": "hosting-1", "references": []},
            ]),
        )

        assert result.plan_path is not None
        assert _ROADMAP_NO_SOURCE_REFERENCES_BODY in result.plan_path.read_text(
            encoding="utf-8"
        )

    def test_roadmap_refusal_keeps_checkpoints_and_description_retry_reuses_steps(
        self, tmp_path: Path
    ) -> None:
        from dataclasses import replace

        from plan_tool.create import (
            CreateError,
            _INITIAL_STEPS_CHECKPOINT_NAME,
            _REFERENCES_CHECKPOINT_NAME,
            checkpoint_path,
            create_plan,
        )
        from plan_tool.roadmap_artifacts import (
            HostingRow,
            ResearchDisclosure,
            parse_constraints_artifact,
            render_constraints_artifact,
        )
        from plan_tool.roadmap_versions import load_accepted_version
        from tests.roadmap_accepted_fixtures import publish_accepted_root

        location = _write_roadmap_research_source(
            tmp_path,
            hosting=(HostingRow(
                "host", "compute", "managed", "Retry host", None,
                ResearchDisclosure.EXTERNAL,
            ),),
        )
        calls = {"steps": 0, "references": 0}

        def invoker(prompt: str) -> str:
            if "Requested products:" in prompt:
                calls["references"] += 1
                return json.dumps([{"token": "hosting-1", "references": []}])
            calls["steps"] += 1
            return json.dumps([
                {
                    "title": "Propose a step",
                    "complexity": "low",
                    "files": [],
                    "intent": "Deliver the requested service.",
                },
            ])

        create_kwargs = {
            "repo_root": tmp_path,
            "output_dir_override": tmp_path / "output",
            "from_description": "Build the requested service.",
            "tracked_seed_location": location,
            "yes": True,
            "offer_intents": False,
            "synthesize_body": False,
            "fetch_docs": False,
            "allow_placeholder_body": True,
            "claude_invoker": invoker,
        }
        with pytest.raises(CreateError, match="Retry host"):
            create_plan("selected-retry", **create_kwargs)

        assert checkpoint_path(
            tmp_path, "selected-retry", _INITIAL_STEPS_CHECKPOINT_NAME
        ).is_file()
        assert checkpoint_path(
            tmp_path, "selected-retry", _REFERENCES_CHECKPOINT_NAME
        ).is_file()

        plans_dir = tmp_path / "plans"
        accepted = load_accepted_version(plans_dir=plans_dir, slug="chosen")
        assert accepted is not None
        texts = [member.decode("utf-8") for member in accepted.artifact_bytes]
        artifact = parse_constraints_artifact(texts[1])
        texts[1] = render_constraints_artifact(
            replace(
                artifact,
                hosting=(replace(artifact.hosting[0], description="Corrected."),),
            )
        )
        publish_accepted_root(plans_dir, "chosen", texts)

        result = create_plan("selected-retry", **create_kwargs)

        assert result.plan_path is not None
        assert calls == {"steps": 1, "references": 2}

    def test_roadmap_refusal_checks_each_target_independently(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.create import CreateError, create_plan
        from plan_tool.roadmap_artifacts import HostingRow, ResearchDisclosure, StoreRow

        location = _write_roadmap_research_source(
            tmp_path,
            hosting=(HostingRow(
                "host", "compute", "managed", "Grounded host", None,
                ResearchDisclosure.EXTERNAL,
            ),),
            stores=(StoreRow(
                "store", "sql", "shared", "Ungrounded store", None,
                ResearchDisclosure.EXTERNAL,
            ),),
        )

        with pytest.raises(CreateError, match="Ungrounded store"):
            create_plan(
                "selected-independent",
                repo_root=tmp_path,
                output_dir_override=tmp_path / "output",
                from_description=_CANONICAL_BODY,
                tracked_seed_location=location,
                yes=True,
                offer_intents=False,
                synthesize_body=False,
                fetch_docs=False,
                allow_placeholder_body=True,
                claude_invoker=lambda _prompt: json.dumps([
                    {
                        "token": "hosting-1",
                        "references": [{
                            "title": "Host docs",
                            "url": "https://example.com/host",
                        }],
                    },
                    {"token": "stores-1", "references": []},
                ]),
            )

    def test_mixed_selected_verdicts_render_decoded_references_and_description_disclosure(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.create import create_plan
        from plan_tool.roadmap_artifacts import HostingRow, ResearchDisclosure, StoreRow

        location = _write_roadmap_research_source(
            tmp_path,
            hosting=(HostingRow(
                "host", "compute", "managed", "Public host", None,
                ResearchDisclosure.EXTERNAL,
            ),),
            stores=(StoreRow(
                "store", "sql", "shared", "Private store", "No useful detail.",
                ResearchDisclosure.LOCAL,
            ),),
        )

        result = create_plan(
            "selected-mixed",
            repo_root=tmp_path,
            output_dir_override=tmp_path / "output",
            from_description=_CANONICAL_BODY,
            tracked_seed_location=location,
            yes=True,
            offer_intents=False,
            synthesize_body=False,
            fetch_docs=False,
            allow_placeholder_body=True,
            claude_invoker=lambda _prompt: json.dumps([
                {
                    "token": "hosting-1",
                    "references": [{
                        "title": "Host docs",
                        "url": "https://example.com/host",
                    }],
                },
            ]),
        )

        body = result.plan_path.read_text(encoding="utf-8")
        assert "- [Host docs](https://example.com/host)" in body
        assert _ROADMAP_NO_SOURCE_REFERENCES_BODY not in body
        # The disclosure names the description-backed product honestly; it
        # never dresses the recorded description up as a decoded source.
        assert "Private store" in body
        assert "recorded operator description" in body
        assert "No useful detail." not in body

    def test_description_backed_disclosure_dedupes_repeated_products(self) -> None:
        """Two distinct rows may legitimately share one recorded product
        string; the disclosure must name it once, not once per row."""
        from plan_tool.create import _description_backed_disclosure

        assert _description_backed_disclosure(["AWS", "AWS"]) == (
            "The following selected product publishes under a recorded "
            "operator description rather than a decoded source: AWS."
        )
        assert _description_backed_disclosure(["AWS", "GCP", "AWS"]) == (
            "The following selected products publish under a recorded "
            "operator description rather than a decoded source: AWS, GCP."
        )

    def test_tracked_roadmap_without_products_keeps_generic_references_research(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool import create as create_module

        location = _write_roadmap_research_source(tmp_path)
        calls: list[tuple[str, str]] = []

        def generic(title: str, description: str, *_args, **_kwargs):
            calls.append((title, description))
            return ReferenceResearchResult.from_references([])

        monkeypatch.setattr(create_module, "propose_references_from_claude", generic)
        result = create_plan(
            "selected-empty",
            repo_root=tmp_path,
            output_dir_override=tmp_path / "output",
            from_description=_CANONICAL_BODY,
            tracked_seed_location=location,
            yes=True,
            offer_intents=False,
            synthesize_body=False,
            fetch_docs=False,
            allow_placeholder_body=True,
        )

        assert result.plan_path is not None
        assert calls == [("Selected Empty", _CANONICAL_BODY)]

    @pytest.mark.parametrize(
        "records, message",
        [
            ([], "missing result"),
            (
                [
                    {"token": "hosting-1", "references": []},
                    {"token": "hosting-1", "references": []},
                ],
                "duplicate target",
            ),
            ([{"token": "unknown", "references": []}], "foreign target"),
        ],
    )
    def test_tracked_roadmap_research_rejects_missing_duplicate_and_foreign_target_records(
        self, records: list[dict[str, object]], message: str
    ) -> None:
        from plan_tool.create import (
            CreateError,
            RoadmapResearchTarget,
            propose_roadmap_references_from_claude,
        )
        from plan_tool.roadmap_artifacts import ResearchDisclosure

        target = RoadmapResearchTarget(
            "hosting-1", "Product", "origin", None, ResearchDisclosure.EXTERNAL
        )
        with pytest.raises(CreateError, match=message):
            propose_roadmap_references_from_claude(
                (target,), lambda _prompt: json.dumps(records), reporter=_RecordingReporter()
            )

    def test_tracked_roadmap_research_rejects_invalid_reference_members(self) -> None:
        from plan_tool.create import (
            CreateError,
            RoadmapResearchTarget,
            propose_roadmap_references_from_claude,
        )
        from plan_tool.roadmap_artifacts import ResearchDisclosure

        target = RoadmapResearchTarget(
            "hosting-1", "Product", "origin", None, ResearchDisclosure.EXTERNAL
        )
        with pytest.raises(CreateError, match="valid Reference"):
            propose_roadmap_references_from_claude(
                (target,),
                lambda _prompt: json.dumps([
                    {"token": "hosting-1", "references": [{"title": "Bad", "url": "ftp://bad"}]}
                ]),
                reporter=_RecordingReporter(),
            )

    def test_tracked_roadmap_research_accepts_explicit_empty_source_list(self) -> None:
        from plan_tool.create import (
            RoadmapResearchTarget,
            propose_roadmap_references_from_claude,
        )
        from plan_tool.roadmap_artifacts import ResearchDisclosure

        target = RoadmapResearchTarget(
            "hosting-1", "Product", "origin", None, ResearchDisclosure.EXTERNAL
        )
        verdicts = propose_roadmap_references_from_claude(
            (target,),
            lambda _prompt: '[{"token": "hosting-1", "references": []}]',
            reporter=_RecordingReporter(),
        )

        assert verdicts[0].source == "external"
        assert verdicts[0].references == ()

    def test_tracked_roadmap_artifact_failure_does_not_fall_back_to_generic_research(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.create import CreateError, create_plan

        location = _write_roadmap_research_source(
            tmp_path, constraints_text="not a constraints artifact\n"
        )
        invocations = 0

        def invoker(_prompt: str) -> str:
            nonlocal invocations
            invocations += 1
            return "[]"

        with pytest.raises(CreateError, match="could not load selected roadmap products"):
            create_plan(
                "selected",
                repo_root=tmp_path,
                output_dir_override=tmp_path / "plans",
                tracked_seed_location=location,
                yes=True,
                claude_invoker=invoker,
            )
        assert invocations == 0

    def test_references_checkpoint_hash_changes_with_roadmap_snapshot_but_not_legacy_input(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.create import RoadmapResearchTarget, _references_input_hash
        from plan_tool.roadmap_artifacts import ResearchDisclosure

        legacy = _references_input_hash("demo", "Plan", "seed", tmp_path, tmp_path)
        assert legacy == _references_input_hash("demo", "Plan", "seed", tmp_path, tmp_path)
        base_target = RoadmapResearchTarget(
            "hosting-1", "Product", "origin", "Description", ResearchDisclosure.LOCAL
        )
        changed_target = RoadmapResearchTarget(
            "hosting-1", "Product", "origin", "Changed description", ResearchDisclosure.LOCAL
        )
        changed_disclosure = RoadmapResearchTarget(
            "hosting-1", "Product", "origin", "Description", ResearchDisclosure.EXTERNAL
        )
        selected = _references_input_hash(
            "demo", "ignored", "ignored", tmp_path, tmp_path,
            roadmap_targets=(base_target,),
        )
        assert selected != _references_input_hash(
            "demo", "ignored", "ignored", tmp_path, tmp_path,
            roadmap_targets=(changed_target,),
        )
        assert selected != _references_input_hash(
            "demo", "ignored", "ignored", tmp_path, tmp_path,
            roadmap_targets=(changed_disclosure,),
        )


@pytest.mark.integration
class TestReferencesRenderedIntoBody:
    """End-to-end: claude returns references and they render as a bulleted
    list in the new plan's ``## References`` section."""

    def test_references_appear_in_written_plan(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        # Same invoker handles BOTH the step proposal call and the
        # references call. The step JSON parses cleanly; for refs the
        # entries with `url` win. Real claude separates the two via the
        # distinct prompts; this fake conflates them and lets the
        # parsers filter.
        step_json = json.dumps(
            [{"title": "step one", "complexity": "low", "files": [], "depends_on": []}]
        )
        ref_json = json.dumps(
            [
                {
                    "title": "Vendor Docs",
                    "url": "https://example.com/docs",
                    "description": "Primary API reference.",
                }
            ]
        )

        def invoker(prompt: str) -> str:
            if "developer and API reference documentation" in prompt:
                return ref_json
            return step_json

        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="Build a thing",
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=invoker,
        )

        body = result.plan_path.read_text(encoding="utf-8")
        assert "## References" in body
        assert "[Vendor Docs](https://example.com/docs)" in body
        assert "Primary API reference." in body
        # References section is not a TODO placeholder.
        assert "## References\n\n_(TODO)_" not in body

    def test_no_references_falls_back_to_todo(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        # Empty refs response → References section stays a TODO.
        def invoker(prompt: str) -> str:
            if "developer and API reference documentation" in prompt:
                return "[]"
            return json.dumps(
                [{"title": "s", "complexity": "low", "files": [], "depends_on": []}]
            )

        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="Build a thing",
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=invoker,
        )

        body = result.plan_path.read_text(encoding="utf-8")
        assert "## References\n\n_(TODO)_" in body

    def test_interactive_create_still_calls_references(
        self, tmp_path: Path
    ) -> None:
        """Even without --from, the wizard builds a research context from
        title + step titles and invokes claude for references."""
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        prompts_seen: list[str] = []

        def invoker(prompt: str) -> str:
            prompts_seen.append(prompt)
            return json.dumps(
                [
                    {
                        "title": "Guide",
                        "url": "https://guide.example.com",
                        "description": "How-to.",
                    }
                ]
            )

        answers = _basic_metadata_answers(title="Interactive Plan") + _single_step_answers(
            title="Wire it up"
        )

        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            input_fn=_queue_input(answers),
            claude_invoker=invoker,
        )

        # One claude call — for references. The research context carries
        # the title and interactive step titles.
        assert len(prompts_seen) == 1
        assert "Interactive Plan" in prompts_seen[0]
        assert "Wire it up" in prompts_seen[0]

        body = result.plan_path.read_text(encoding="utf-8")
        assert "[Guide](https://guide.example.com)" in body


# --- Seed-body enrichment: lift original prose into the new plan ----------


class TestRenderPlanBodyWithSeedSections:
    def test_substitutes_matching_sections(self) -> None:
        seed = {
            "overview": "Real overview content.",
            "architecture": "Real architecture content.",
            "risks": "- risk 1\n- risk 2",
        }
        out = _render_plan_body("Title", seed_sections=seed)
        assert "## Overview\n\nReal overview content.\n" in out
        assert "## Architecture\n\nReal architecture content.\n" in out
        assert "## Risks\n\n- risk 1\n- risk 2\n" in out

    def test_unmatched_sections_keep_todo(self) -> None:
        seed = {"overview": "filled"}
        out = _render_plan_body("X", seed_sections=seed)
        # 9 sections; Steps points at frontmatter, Overview is filled,
        # the remaining 7 fall back to _(TODO)_.
        assert out.count("_(TODO)_") == len(PLAN_BODY_SECTIONS) - 2
        assert "## Overview\n\nfilled" in out

    def test_steps_section_always_points_at_frontmatter(self) -> None:
        seed = {"steps": "should be ignored"}
        out = _render_plan_body("X", seed_sections=seed)
        assert "See the `steps:` block" in out
        assert "should be ignored" not in out

    def test_references_arg_wins_over_seed_section(self) -> None:

        seed = {"references": "- [SeedLink](https://seed.example.com)"}
        refs = [Reference(title="ClaudeLink", url="https://claude.example.com")]
        out = _render_plan_body("X", references=refs, seed_sections=seed)
        assert "ClaudeLink" in out
        assert "SeedLink" not in out

    def test_references_seed_used_when_no_references_arg(self) -> None:
        seed = {"references": "- [SeedLink](https://seed.example.com)"}
        out = _render_plan_body("X", seed_sections=seed)
        assert "SeedLink" in out
        # And the section's TODO placeholder is replaced.
        assert "## References\n\n- [SeedLink]" in out


@pytest.mark.integration
class TestCreatePlanWithSeedBody:
    """Integration: ``seed_body`` enriches the body and the references prompt."""

    def test_seed_body_populates_plan_body_sections(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        seed = (
            "# Old Plan\n\n"
            "## Overview\n\nDetailed overview from the seed.\n\n"
            "## Architecture\n\nDetailed architecture from the seed.\n\n"
            "## Risks\n\n- seed risk\n"
        )

        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description=_CANONICAL_BODY,
            seed_body=seed,
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=lambda prompt: (
                _valid_preparation_response(prompt)
                if "Distill a free-form seed" in prompt
                else _ONE_STEP_JSON
                if "Propose an initial plan step-list" in prompt
                else "[]"
            ),
        )

        body = result.plan_path.read_text(encoding="utf-8")
        assert "Detailed overview from the seed." in body
        assert "Detailed architecture from the seed." in body
        assert "- seed risk" in body
        # Sections with no seed match still get TODO.
        assert "## Out of scope\n\n_(TODO)_" in body

    def test_seed_body_used_as_references_research_context(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        seed = (
            "# Old Plan\n\n## Overview\n\nMarker-seed-prose-9f3a.\n"
        )
        prompts_seen: list[str] = []

        def invoker(prompt: str) -> str:
            prompts_seen.append(prompt)
            return "[]"

        create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description=_CANONICAL_BODY,
            seed_body=seed,
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=invoker,
        )

        # The references prompt and the body-sections synthesis prompt
        # both carry the seed body (not the canonical) as the source
        # they reason over. The synthesis call may retry once on its
        # all-empty-list response, so accept either 2 or 3 prompts.
        refs_prompts = [
            p for p in prompts_seen
            if "developer and API reference documentation" in p
        ]
        synth_prompts = [
            p for p in prompts_seen
            if "Synthesize plan body sections" in p
        ]
        assert len(refs_prompts) == 1
        assert len(synth_prompts) >= 1
        assert "Marker-seed-prose-9f3a" in refs_prompts[0]
        assert "Marker-seed-prose-9f3a" in synth_prompts[0]

    def test_no_seed_body_falls_back_to_from_description(
        self, tmp_path: Path
    ) -> None:
        """No separate ``seed_body`` → ``from_description`` is the body source.

        Only sections the source doesn't carry stay ``_(TODO)_``. Was:
        every section placeholdered, discarding the source's own prose.
        """
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description=_CANONICAL_BODY,
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=lambda prompt: "[]",
        )

        body = result.plan_path.read_text(encoding="utf-8")
        # ``_CANONICAL_BODY`` carries Overview, References, and Acceptance
        # criteria; all three land verbatim. The remaining six sections
        # stay placeholders when the model returns no usable synthesis.
        assert "## Overview\n\nSome prose." in body
        assert "## Acceptance criteria\n\n- All tests pass." in body
        assert body.count("_(TODO)_") == len(PLAN_BODY_SECTIONS) - 4


class TestCmdCreateSeedResolution:
    """End-to-end: ``cmd_create`` reads the seed via canonical provenance."""

    def test_seed_body_lifted_from_disk(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool.cli import context as cli_context

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        # Seed (the original) with rich H2 sections.
        seed = out_dir / "2-old.md"
        seed.write_text(
            "# Old Plan\n\n"
            "## Overview\n\nSeed overview marker-fa72.\n\n"
            "## Architecture\n\nSeed architecture marker-fa72.\n\n"
            "## References\n\n- [API](https://example.test/api)\n",
            encoding="utf-8",
        )
        # Canonical with provenance pointing at the seed.
        canonical = out_dir / "2-old-canonical.md"
        canonical.write_text(
            _canonical_with_provenance(
                source_name="2-old.md", plan_details=None
            ),
            encoding="utf-8",
        )

        original = cli_module.create_plan
        answers = _basic_metadata_answers()

        def patched(*args, **kwargs):
            kwargs.setdefault("input_fn", _queue_input(answers))
            kwargs["claude_invoker"] = lambda prompt: (
                _valid_preparation_response(prompt)
                if "Distill a free-form seed" in prompt
                else _ONE_STEP_JSON
                if "Propose an initial plan step-list" in prompt
                else "[]"
            )
            return original(*args, **kwargs)

        monkeypatch.setattr("plan_tool.cli.authoring.create_plan", patched)
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "create", "new",
                "--from-existing", str(canonical),
                "--output-dir", str(out_dir),
                "--no-distill",
                "--no-iterate",
            ]
        )
        assert rc == 0
        new_plan = next(p for p in out_dir.glob("*-new.md"))
        body = new_plan.read_text(encoding="utf-8")
        assert "Seed overview marker-fa72." in body
        assert "Architecture prepared body." in body

    def test_missing_seed_warns_and_falls_back_to_canonical_text(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A dangling provenance pointer warns but costs only the richer prose.

        The canonical's own H2s still populate the body — the warning
        marks what was lost (the seed's fuller text), not a body-wide
        degradation to ``_(TODO)_``.
        """
        from plan_tool.cli import app as cli_module
        from plan_tool.cli import context as cli_context

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        # Canonical points at a seed that doesn't exist on disk.
        canonical = out_dir / "2-old-canonical.md"
        canonical.write_text(
            _canonical_with_provenance(
                source_name="2-old.md", plan_details=None
            ),
            encoding="utf-8",
        )

        original = cli_module.create_plan
        answers = _basic_metadata_answers()

        def patched(*args, **kwargs):
            kwargs.setdefault("input_fn", _queue_input(answers))
            kwargs["claude_invoker"] = lambda prompt: (
                _valid_preparation_response(prompt)
                if "Distill a free-form seed" in prompt
                else _ONE_STEP_JSON
                if "Propose an initial plan step-list" in prompt
                else "[]"
            )
            return original(*args, **kwargs)

        monkeypatch.setattr("plan_tool.cli.authoring.create_plan", patched)
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "create", "new",
                "--from-existing", str(canonical),
                "--output-dir", str(out_dir),
                "--no-distill",
                "--no-iterate",
            ]
        )
        assert rc == 0
        err = capsys.readouterr().err
        assert "warning:" in err
        assert "2-old.md" in err
        # New plan is still written, and the canonical text it fell back to
        # supplies Overview. Only sections the canonical never carried
        # (Risks here) placeholder.
        new_plan = next(p for p in out_dir.glob("*-new.md"))
        body = new_plan.read_text(encoding="utf-8")
        assert "## Overview\n\nOverview prepared body." in body
        assert "## Risks" in body


# --- Resumable create-time checkpoints -------------------------------------


from datetime import datetime, timezone  # noqa: E402

from plan_tool.checkpoint import (  # noqa: E402
    Checkpoint,
    checkpoint_path,
    save_checkpoint,
)
from plan_tool.create import (  # noqa: E402
    _BODY_SECTIONS_CHECKPOINT_NAME,
    _INITIAL_STEPS_CHECKPOINT_NAME,
    _REFERENCE_DOCS_CHECKPOINT_NAME,
    _REFERENCES_CHECKPOINT_NAME,
    _body_sections_input_hash,
    _render_local_code_context,
    _render_local_code_grounding,
    _initial_steps_input_hash,
    _parse_body_sections_json,
    _references_input_hash,
    propose_body_sections,
)
from plan_tool.granularity import assess_granularity  # noqa: E402


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


_STEP_JSON = json.dumps([_proposed_step("first")])
_REF_JSON = json.dumps(
    [{"title": "Docs", "url": "https://example.com", "description": "x"}]
)
# A second, distinct references payload. Used by the iteration-loop tests
# to prove that a references round which lands DURING an iteration (vs.
# the round-0 refs baked in by ``write_new_plan``) was actually patched
# into the body — the URL only appears if the in-loop patch ran.
_REF_JSON_ITER = json.dumps(
    [{"title": "Updated", "url": "https://updated.example.com", "description": "y"}]
)
# An invalid step graph: ``depends_on`` references an id (99) no step
# declares. ``propose_steps_from_claude`` rejects this and returns None,
# the trigger for the iteration loop's fail-fast abort.
# An ``intent`` is present so the broken graph stays the only thing under test.
_INVALID_STEP_JSON = json.dumps([_proposed_step("only", depends_on=[99])])
# All-null synthesis response: the canonical-key set with every value
# ``None``. Validator-accepted shape that signals "no source-derivable
# content" — the renderer falls through to H2-extraction → ``_(TODO)_``
# for every body section. Suitable default for tests that don't care
# about synthesized body content.
_SYNTHESIS_NULL_JSON = json.dumps(
    {
        "Overview": None,
        "Problem statement": None,
        "Architecture": None,
        "Out of scope": None,
        "Risks": None,
        "Testing": None,
        "Acceptance criteria": None,
        "Deferred": None,
    }
)


@pytest.mark.integration
class TestCreatePlanResume:
    def test_propose_steps_writes_checkpoint_when_slug_and_output_dir_provided(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()

        steps = propose_steps_from_claude(
            "build a thing",
            lambda prompt: _STEP_JSON,
            reporter=_RecordingReporter(),
            repo_root=tmp_path,
            slug="demo",
            output_dir=out_dir,
        )
        assert steps is not None

        ckpt = checkpoint_path(tmp_path, "demo", _INITIAL_STEPS_CHECKPOINT_NAME)
        assert ckpt.exists()
        body = json.loads(ckpt.read_text(encoding="utf-8"))
        assert body["payload"] == _STEP_JSON
        assert body["input_hash"] == _initial_steps_input_hash(
            "demo", "build a thing", out_dir, tmp_path
        )

    def test_propose_steps_skips_invoker_on_cache_hit(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()

        ckpt = checkpoint_path(tmp_path, "demo", _INITIAL_STEPS_CHECKPOINT_NAME)
        save_checkpoint(
            ckpt,
            Checkpoint(
                input_hash=_initial_steps_input_hash(
                    "demo", "build a thing", out_dir, tmp_path
                ),
                payload=_STEP_JSON,
                created_at=_now_iso(),
            ),
        )

        def explode(prompt: str) -> str:
            raise AssertionError("invoker must not be called on cache hit")

        steps = propose_steps_from_claude(
            "build a thing",
            explode,
            reporter=_RecordingReporter(),
            repo_root=tmp_path,
            slug="demo",
            output_dir=out_dir,
        )
        assert steps is not None
        assert len(steps) == 1
        assert steps[0].title == "first"

    def test_checkpoint_resume_restores_change_type(self, tmp_path: Path) -> None:
        """``change_type`` rides the raw-JSON checkpoint payload: a resume
        re-parses it through the lenient parser and restores each step's
        classification with zero checkpoint-code change."""
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()

        classified = json.dumps(
            [
                {
                    "title": "Restructure",
                    "change_type": "refactor",
                    "files": [],
                    "depends_on": [],
                },
                {
                    "title": "Add behavior",
                    "change_type": "feature",
                    "files": [],
                    "depends_on": [1],
                },
            ]
        )
        ckpt = checkpoint_path(tmp_path, "demo", _INITIAL_STEPS_CHECKPOINT_NAME)
        save_checkpoint(
            ckpt,
            Checkpoint(
                input_hash=_initial_steps_input_hash(
                    "demo", "build a thing", out_dir, tmp_path
                ),
                payload=classified,
                created_at=_now_iso(),
            ),
        )

        def explode(prompt: str) -> str:
            raise AssertionError("invoker must not be called on cache hit")

        steps = propose_steps_from_claude(
            "build a thing",
            explode,
            reporter=_RecordingReporter(),
            repo_root=tmp_path,
            slug="demo",
            output_dir=out_dir,
        )
        assert steps is not None
        assert [s.change_type for s in steps] == [
            ChangeType.REFACTOR,
            ChangeType.FEATURE,
        ]

    def test_propose_steps_cache_miss_on_description_change_re_invokes(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()

        ckpt = checkpoint_path(tmp_path, "demo", _INITIAL_STEPS_CHECKPOINT_NAME)
        save_checkpoint(
            ckpt,
            Checkpoint(
                input_hash=_initial_steps_input_hash(
                    "demo", "foo", out_dir, tmp_path
                ),
                payload=_STEP_JSON,
                created_at=_now_iso(),
            ),
        )

        counter = {"n": 0}

        def invoker(prompt: str) -> str:
            counter["n"] += 1
            return _STEP_JSON

        steps = propose_steps_from_claude(
            "bar",
            invoker,
            reporter=_RecordingReporter(),
            repo_root=tmp_path,
            slug="demo",
            output_dir=out_dir,
        )
        assert steps is not None
        assert counter["n"] == 1
        body = json.loads(ckpt.read_text(encoding="utf-8"))
        assert body["input_hash"] == _initial_steps_input_hash(
            "demo", "bar", out_dir, tmp_path
        )

    def test_propose_steps_no_checkpoint_when_slug_or_output_dir_missing(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()

        steps = propose_steps_from_claude(
            "build a thing",
            lambda prompt: _STEP_JSON,
            reporter=_RecordingReporter(),
            repo_root=tmp_path,
        )
        assert steps is not None

        ckpt_root = tmp_path / ".plan-tool" / "checkpoints"
        assert not ckpt_root.exists() or not any(ckpt_root.rglob("*.json"))

    def test_propose_references_writes_and_loads_checkpoint(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()

        result = propose_references_from_claude(
            "My Plan",
            "build a thing",
            lambda prompt: _REF_JSON,
            reporter=_RecordingReporter(),
            slug="demo",
            output_dir=out_dir,
            repo_root=tmp_path,
        )
        assert result.outcome == "populated"
        assert len(result.references) == 1

        ckpt = checkpoint_path(tmp_path, "demo", _REFERENCES_CHECKPOINT_NAME)
        assert ckpt.exists()
        body = json.loads(ckpt.read_text(encoding="utf-8"))
        assert body["payload"] == _REF_JSON
        assert body["input_hash"] == _references_input_hash(
            "demo", "My Plan", "build a thing", out_dir, tmp_path
        )

        def explode(prompt: str) -> str:
            raise AssertionError("invoker must not be called on cache hit")

        resumed_result = propose_references_from_claude(
            "My Plan",
            "build a thing",
            explode,
            reporter=_RecordingReporter(),
            slug="demo",
            output_dir=out_dir,
            repo_root=tmp_path,
        )
        assert resumed_result.outcome == "populated"
        assert len(resumed_result.references) == 1

    def test_unparseable_references_checkpoint_skips_retry(
        self, tmp_path: Path
    ) -> None:
        """A replayed malformed response cannot gain information from a
        retry, so it returns without invoking the backend."""
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        checkpoint = checkpoint_path(
            tmp_path, "demo", _REFERENCES_CHECKPOINT_NAME
        )
        save_checkpoint(
            checkpoint,
            Checkpoint(
                input_hash=_references_input_hash(
                    "demo", "My Plan", "build a thing", out_dir, tmp_path
                ),
                payload="not JSON",
                created_at=_now_iso(),
            ),
        )

        def invoker(_prompt: str) -> str:
            raise AssertionError("cached research must not retry")

        result = propose_references_from_claude(
            "My Plan",
            "build a thing",
            invoker,
            reporter=_RecordingReporter(),
            slug="demo",
            output_dir=out_dir,
            repo_root=tmp_path,
        )

        assert result.outcome == "unparseable"

    def test_propose_references_cache_miss_on_title_change_re_invokes(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()

        ckpt = checkpoint_path(tmp_path, "demo", _REFERENCES_CHECKPOINT_NAME)
        save_checkpoint(
            ckpt,
            Checkpoint(
                input_hash=_references_input_hash(
                    "demo", "Foo", "build a thing", out_dir, tmp_path
                ),
                payload=_REF_JSON,
                created_at=_now_iso(),
            ),
        )

        counter = {"n": 0}

        def invoker(prompt: str) -> str:
            counter["n"] += 1
            return _REF_JSON

        result = propose_references_from_claude(
            "Bar",
            "build a thing",
            invoker,
            reporter=_RecordingReporter(),
            slug="demo",
            output_dir=out_dir,
            repo_root=tmp_path,
        )
        assert result.outcome == "populated"
        assert counter["n"] == 1

    def test_create_plan_discards_both_checkpoints_on_success(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        def invoker(prompt: str) -> str:
            if "developer and API reference documentation" in prompt:
                return _REF_JSON
            return _STEP_JSON

        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="build a thing",
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=invoker,
        )
        assert result.plan_path.exists()

        steps_ckpt = checkpoint_path(
            tmp_path, "demo", _INITIAL_STEPS_CHECKPOINT_NAME
        )
        refs_ckpt = checkpoint_path(
            tmp_path, "demo", _REFERENCES_CHECKPOINT_NAME
        )
        assert not steps_ckpt.exists()
        assert not refs_ckpt.exists()

    def test_create_plan_keeps_checkpoints_when_write_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool import create as create_module
        from plan_tool.parser import ParseError

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        def invoker(prompt: str) -> str:
            if "developer and API reference documentation" in prompt:
                return _REF_JSON
            if "Synthesize plan body sections" in prompt:
                return _SYNTHESIS_NULL_JSON
            return _STEP_JSON

        def fake_parse(path):
            raise ParseError("simulated parse failure")

        monkeypatch.setattr(create_module, "parse_plan", fake_parse)

        with pytest.raises(CreateError, match="post-write reparse"):
            create_plan(
                "demo",
                repo_root=tmp_path,
                output_dir_override=out_dir,
                manifest_path=manifest,
                from_description="build a thing",
                input_fn=_queue_input(_basic_metadata_answers()),
                claude_invoker=invoker,
            )

        steps_ckpt = checkpoint_path(
            tmp_path, "demo", _INITIAL_STEPS_CHECKPOINT_NAME
        )
        refs_ckpt = checkpoint_path(
            tmp_path, "demo", _REFERENCES_CHECKPOINT_NAME
        )
        body_ckpt = checkpoint_path(
            tmp_path, "demo", _BODY_SECTIONS_CHECKPOINT_NAME
        )
        assert steps_ckpt.exists()
        assert refs_ckpt.exists()
        assert body_ckpt.exists()
        steps_body = json.loads(steps_ckpt.read_text(encoding="utf-8"))
        refs_body = json.loads(refs_ckpt.read_text(encoding="utf-8"))
        body_body = json.loads(body_ckpt.read_text(encoding="utf-8"))
        assert steps_body["payload"] == _STEP_JSON
        assert refs_body["payload"] == _REF_JSON
        assert body_body["payload"] == _SYNTHESIS_NULL_JSON
        assert steps_body["input_hash"] == _initial_steps_input_hash(
            "demo", "build a thing", out_dir, tmp_path
        )
        assert refs_body["input_hash"] == _references_input_hash(
            "demo", "Demo Plan", "build a thing", out_dir, tmp_path
        )
        assert body_body["input_hash"] == _body_sections_input_hash(
            "demo", "build a thing", out_dir, tmp_path
        )

        # Restore parse_plan and re-run with exploding invokers — both
        # phases should hit the cache and complete without invoking.
        monkeypatch.undo()

        def explode(prompt: str) -> str:
            raise AssertionError("invoker must not be called on cache hit")

        # The first run wrote the plan file to disk, but the parse-plan
        # failure happened *after* write_new_plan. The collision branch
        # in create_plan would normally trigger; cleanly remove the
        # stale plan file so the resume run can re-write it.
        for stray in out_dir.glob("*-demo.md"):
            stray.unlink()

        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="build a thing",
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=explode,
        )
        assert result.plan_path.exists()

    def test_create_plan_resume_false_skips_load_but_still_saves_then_discards(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        # Pre-seed all three checkpoints with payloads that would cause
        # parse failures if used (so a load would manifest as a failure
        # mode — but resume=False means they're ignored).
        steps_ckpt = checkpoint_path(
            tmp_path, "demo", _INITIAL_STEPS_CHECKPOINT_NAME
        )
        refs_ckpt = checkpoint_path(
            tmp_path, "demo", _REFERENCES_CHECKPOINT_NAME
        )
        body_ckpt = checkpoint_path(
            tmp_path, "demo", _BODY_SECTIONS_CHECKPOINT_NAME
        )
        save_checkpoint(
            steps_ckpt,
            Checkpoint(
                input_hash=_initial_steps_input_hash(
                    "demo", "build a thing", out_dir, tmp_path
                ),
                payload=_STEP_JSON,
                created_at=_now_iso(),
            ),
        )
        save_checkpoint(
            refs_ckpt,
            Checkpoint(
                input_hash=_references_input_hash(
                    "demo", "Demo Plan", "build a thing", out_dir, tmp_path
                ),
                payload=_REF_JSON,
                created_at=_now_iso(),
            ),
        )
        save_checkpoint(
            body_ckpt,
            Checkpoint(
                input_hash=_body_sections_input_hash(
                    "demo", "build a thing", out_dir, tmp_path
                ),
                payload=_SYNTHESIS_NULL_JSON,
                created_at=_now_iso(),
            ),
        )

        counter = {"steps": 0, "refs": 0, "synth": 0}

        def invoker(prompt: str) -> str:
            if "developer and API reference documentation" in prompt:
                counter["refs"] += 1
                return _REF_JSON
            if "Synthesize plan body sections" in prompt:
                counter["synth"] += 1
                return _SYNTHESIS_NULL_JSON
            counter["steps"] += 1
            return _STEP_JSON

        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="build a thing",
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=invoker,
            resume=False,
        )
        assert result.plan_path.exists()
        assert counter["steps"] == 1
        assert counter["refs"] == 1
        assert counter["synth"] == 1
        assert not steps_ckpt.exists()
        assert not refs_ckpt.exists()
        assert not body_ckpt.exists()

    def test_create_plan_both_phases_cached_zero_total_invokes(
        self, tmp_path: Path
    ) -> None:
        """All three checkpoints pre-seeded → claude is never invoked."""
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        steps_ckpt = checkpoint_path(
            tmp_path, "demo", _INITIAL_STEPS_CHECKPOINT_NAME
        )
        refs_ckpt = checkpoint_path(
            tmp_path, "demo", _REFERENCES_CHECKPOINT_NAME
        )
        body_ckpt = checkpoint_path(
            tmp_path, "demo", _BODY_SECTIONS_CHECKPOINT_NAME
        )
        save_checkpoint(
            steps_ckpt,
            Checkpoint(
                input_hash=_initial_steps_input_hash(
                    "demo", "build a thing", out_dir, tmp_path
                ),
                payload=_STEP_JSON,
                created_at=_now_iso(),
            ),
        )
        save_checkpoint(
            refs_ckpt,
            Checkpoint(
                input_hash=_references_input_hash(
                    "demo", "Demo Plan", "build a thing", out_dir, tmp_path
                ),
                payload=_REF_JSON,
                created_at=_now_iso(),
            ),
        )
        save_checkpoint(
            body_ckpt,
            Checkpoint(
                input_hash=_body_sections_input_hash(
                    "demo", "build a thing", out_dir, tmp_path
                ),
                payload=_SYNTHESIS_NULL_JSON,
                created_at=_now_iso(),
            ),
        )

        def explode(prompt: str) -> str:
            raise AssertionError("invoker must not be called when all caches hit")

        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="build a thing",
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=explode,
        )
        assert result.plan_path.exists()

        # Cached payloads landed in the new plan.
        plan = parse_plan(result.plan_path)
        assert [s.title for s in plan.steps] == ["first"]
        body = result.plan_path.read_text(encoding="utf-8")
        assert "[Docs](https://example.com)" in body

        # All three checkpoints discarded after the successful create.
        assert not steps_ckpt.exists()
        assert not refs_ckpt.exists()
        assert not body_ckpt.exists()

    def test_create_plan_partial_cache_steps_cached_refs_fresh(
        self, tmp_path: Path
    ) -> None:
        """Initial-steps cache hit, references cache miss → one invocation for refs."""
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        steps_ckpt = checkpoint_path(
            tmp_path, "demo", _INITIAL_STEPS_CHECKPOINT_NAME
        )
        save_checkpoint(
            steps_ckpt,
            Checkpoint(
                input_hash=_initial_steps_input_hash(
                    "demo", "build a thing", out_dir, tmp_path
                ),
                payload=_STEP_JSON,
                created_at=_now_iso(),
            ),
        )

        counter = {"steps": 0, "refs": 0, "synth": 0}

        def invoker(prompt: str) -> str:
            if "developer and API reference documentation" in prompt:
                counter["refs"] += 1
                return _REF_JSON
            if "Synthesize plan body sections" in prompt:
                counter["synth"] += 1
                return _SYNTHESIS_NULL_JSON
            counter["steps"] += 1
            return _STEP_JSON

        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="build a thing",
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=invoker,
        )
        assert result.plan_path.exists()

        # Steps came from cache; references + body sections were fetched fresh.
        assert counter["steps"] == 0
        assert counter["refs"] == 1
        assert counter["synth"] == 1
        plan = parse_plan(result.plan_path)
        assert [s.title for s in plan.steps] == ["first"]
        body = result.plan_path.read_text(encoding="utf-8")
        assert "[Docs](https://example.com)" in body

    def test_propose_references_cache_miss_on_description_change_re_invokes(
        self, tmp_path: Path
    ) -> None:
        """Mutating the research description invalidates the refs cache."""
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()

        ckpt = checkpoint_path(tmp_path, "demo", _REFERENCES_CHECKPOINT_NAME)
        save_checkpoint(
            ckpt,
            Checkpoint(
                input_hash=_references_input_hash(
                    "demo", "My Plan", "old description", out_dir, tmp_path
                ),
                payload=_REF_JSON,
                created_at=_now_iso(),
            ),
        )

        counter = {"n": 0}

        def invoker(prompt: str) -> str:
            counter["n"] += 1
            return _REF_JSON

        result = propose_references_from_claude(
            "My Plan",
            "new description",
            invoker,
            reporter=_RecordingReporter(),
            slug="demo",
            output_dir=out_dir,
            repo_root=tmp_path,
        )
        assert result.outcome == "populated"
        # Description differs → cache misses → invoker fires once.
        assert counter["n"] == 1
        # The new hash overwrites the stale entry.
        body = json.loads(ckpt.read_text(encoding="utf-8"))
        assert body["input_hash"] == _references_input_hash(
            "demo", "My Plan", "new description", out_dir, tmp_path
        )

    def test_create_plan_replace_on_collision_with_valid_checkpoint_overwrites(
        self, tmp_path: Path
    ) -> None:
        """``replace_on_collision=True`` is orthogonal to ``resume=True``.

        Pre-existing plan is archived AND the cached steps body lands in
        the new plan — the two flags must compose cleanly.
        """
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        # Existing plan occupying the slug.
        existing = out_dir / "2-demo.md"
        existing.write_text(
            "---\n"
            "title: Old Plan\n"
            "status: planning\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: old step\n"
            "---\n\n# Old Plan\n",
            encoding="utf-8",
        )

        # Seed all three checkpoints for the new (about-to-be-created) plan.
        steps_ckpt = checkpoint_path(
            tmp_path, "demo", _INITIAL_STEPS_CHECKPOINT_NAME
        )
        refs_ckpt = checkpoint_path(
            tmp_path, "demo", _REFERENCES_CHECKPOINT_NAME
        )
        body_ckpt = checkpoint_path(
            tmp_path, "demo", _BODY_SECTIONS_CHECKPOINT_NAME
        )
        save_checkpoint(
            steps_ckpt,
            Checkpoint(
                input_hash=_initial_steps_input_hash(
                    "demo", "build a thing", out_dir, tmp_path
                ),
                payload=_STEP_JSON,
                created_at=_now_iso(),
            ),
        )
        save_checkpoint(
            refs_ckpt,
            Checkpoint(
                input_hash=_references_input_hash(
                    "demo", "Demo Plan", "build a thing", out_dir, tmp_path
                ),
                payload=_REF_JSON,
                created_at=_now_iso(),
            ),
        )
        save_checkpoint(
            body_ckpt,
            Checkpoint(
                input_hash=_body_sections_input_hash(
                    "demo", "build a thing", out_dir, tmp_path
                ),
                payload=_SYNTHESIS_NULL_JSON,
                created_at=_now_iso(),
            ),
        )

        def explode(prompt: str) -> str:
            raise AssertionError("invoker must not be called when all caches hit")

        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="build a thing",
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=explode,
            replace_on_collision=True,
        )

        # Old plan body archived under the priority-prefixed name; new
        # plan occupies the same path (medium priority → ``2-demo.md``).
        archived = out_dir / "archive" / "2-demo.replaced.md"
        assert archived.is_file()
        assert "Old Plan" in archived.read_text(encoding="utf-8")

        assert result.plan_path.is_file()
        assert result.plan_path == existing  # same slug + priority bucket
        plan = parse_plan(result.plan_path)
        # New plan was written: title is the metadata default ("Demo Plan"),
        # steps come from the cached payload.
        assert plan.title == "Demo Plan"
        assert [s.title for s in plan.steps] == ["first"]  # from cache
        body = result.plan_path.read_text(encoding="utf-8")
        assert "[Docs](https://example.com)" in body  # cached refs

        # All three checkpoints discarded post-commit.
        assert not steps_ckpt.exists()
        assert not refs_ckpt.exists()
        assert not body_ckpt.exists()


@pytest.mark.integration
class TestResumePromptAndFlag:
    """`--no-resume` CLI flag plus interactive resume prompt on TTY."""

    def test_no_resume_flag_passes_resume_false_to_create_plan(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool.cli import context as cli_context

        captured: dict[str, object] = {}

        class _FakeResult:
            plan_path = tmp_path / "1-demo.md"
            manifest_path = tmp_path / "m.json"
            manifest_updated = True
            provenance = None
            plan_details_renamed_to = None
            plan_details_skip_reason = None
            replaced_archives: list = []
            replaced_skipped: list = []
            replaced_manifest_entries: list = []
            split_proposal = None
            distilled_seed = None
            iteration_stage_failure = None
            file_backed_route = None
            refusal_reason = None

        def fake_create_plan(slug, **kwargs):
            captured.update(kwargs)
            captured["slug"] = slug
            return _FakeResult()

        monkeypatch.setattr("plan_tool.cli.authoring.create_plan", fake_create_plan)
        monkeypatch.setattr(
            cli_context, "find_repo_root_from_cwd", lambda: tmp_path
        )
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(["create", "demo", "--no-resume"])
        assert rc == 0
        assert captured.get("resume") is False

    def test_no_resume_flag_default_is_resume_true(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool.cli import context as cli_context

        captured: dict[str, object] = {}

        class _FakeResult:
            plan_path = tmp_path / "1-demo.md"
            manifest_path = tmp_path / "m.json"
            manifest_updated = True
            provenance = None
            plan_details_renamed_to = None
            plan_details_skip_reason = None
            replaced_archives: list = []
            replaced_skipped: list = []
            replaced_manifest_entries: list = []
            split_proposal = None
            distilled_seed = None
            iteration_stage_failure = None
            file_backed_route = None
            refusal_reason = None

        def fake_create_plan(slug, **kwargs):
            captured.update(kwargs)
            captured["slug"] = slug
            return _FakeResult()

        monkeypatch.setattr("plan_tool.cli.authoring.create_plan", fake_create_plan)
        monkeypatch.setattr(
            cli_context, "find_repo_root_from_cwd", lambda: tmp_path
        )
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(["create", "demo"])
        assert rc == 0
        assert captured.get("resume") is True

    def test_initial_steps_prompt_yes_reuses_cached_proposal(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()

        # Pre-seed the steps checkpoint.
        ckpt = checkpoint_path(
            tmp_path, "demo", _INITIAL_STEPS_CHECKPOINT_NAME
        )
        save_checkpoint(
            ckpt,
            Checkpoint(
                input_hash=_initial_steps_input_hash(
                    "demo", "build a thing", out_dir, tmp_path
                ),
                payload=_STEP_JSON,
                created_at=_now_iso(),
            ),
        )

        monkeypatch.setattr("sys.stdin.isatty", lambda: True)

        def explode(prompt: str) -> str:
            raise AssertionError("invoker must not be called on cache accept")

        steps = propose_steps_from_claude(
            "build a thing",
            explode,
            reporter=_RecordingReporter(),
            repo_root=tmp_path,
            slug="demo",
            output_dir=out_dir,
            input_fn=lambda _q: "",  # empty → default yes
        )
        assert steps is not None
        assert len(steps) == 1

    def test_initial_steps_prompt_no_discards_and_reinvokes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()

        ckpt = checkpoint_path(
            tmp_path, "demo", _INITIAL_STEPS_CHECKPOINT_NAME
        )
        save_checkpoint(
            ckpt,
            Checkpoint(
                input_hash=_initial_steps_input_hash(
                    "demo", "build a thing", out_dir, tmp_path
                ),
                payload='[{"title": "stale", "complexity": "low", "files": [], "depends_on": []}]',
                created_at=_now_iso(),
            ),
        )

        monkeypatch.setattr("sys.stdin.isatty", lambda: True)

        counter = {"n": 0}

        def invoker(prompt: str) -> str:
            counter["n"] += 1
            return _STEP_JSON

        steps = propose_steps_from_claude(
            "build a thing",
            invoker,
            reporter=_RecordingReporter(),
            repo_root=tmp_path,
            slug="demo",
            output_dir=out_dir,
            input_fn=lambda _q: "n",
        )
        assert steps is not None
        assert counter["n"] == 1
        assert steps[0].title == "first"  # from _STEP_JSON, not "stale"

    def test_references_prompt_independent_of_initial_steps_prompt(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """References checkpoint pre-seeded; initial-steps has no checkpoint.

        Initial-steps phase invokes claude (no cache). References phase
        finds its checkpoint, prompts (TTY), and reuses on default-yes.
        """
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()

        refs_ckpt = checkpoint_path(
            tmp_path, "demo", _REFERENCES_CHECKPOINT_NAME
        )
        save_checkpoint(
            refs_ckpt,
            Checkpoint(
                input_hash=_references_input_hash(
                    "demo", "Bar", "build a thing", out_dir, tmp_path
                ),
                payload=_REF_JSON,
                created_at=_now_iso(),
            ),
        )

        monkeypatch.setattr("sys.stdin.isatty", lambda: True)

        # Initial steps: no checkpoint, so the invoker runs.
        steps_counter = {"n": 0}

        def steps_invoker(prompt: str) -> str:
            steps_counter["n"] += 1
            return _STEP_JSON

        steps = propose_steps_from_claude(
            "build a thing",
            steps_invoker,
            reporter=_RecordingReporter(),
            repo_root=tmp_path,
            slug="demo",
            output_dir=out_dir,
            input_fn=lambda _q: "",
        )
        assert steps is not None
        assert steps_counter["n"] == 1

        # References: cache hit, prompt accepts → invoker not called.
        def refs_explode(prompt: str) -> str:
            raise AssertionError("refs invoker must not run on accept")

        result = propose_references_from_claude(
            "Bar",
            "build a thing",
            refs_explode,
            reporter=_RecordingReporter(),
            slug="demo",
            output_dir=out_dir,
            repo_root=tmp_path,
            input_fn=lambda _q: "",
        )
        assert result.outcome == "populated"
        assert len(result.references) == 1

    def test_yes_flag_with_existing_checkpoint_reuses_without_prompting(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Under ``--yes``, the silent input_fn returns '' → default-yes.

        Pre-seeded checkpoints are reused, so the invoker is spent on none of
        those three round-trips. The intent offer is the one uncheckpointed
        call ``--yes`` still makes (the seed states no ``## Outcome``); it
        drafts nothing here, so nothing is written. No prompt deadlock.
        """
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        # Pre-seed all three checkpoints.
        from plan_tool.create import _silent_input_fn

        steps_ckpt = checkpoint_path(
            tmp_path, "demo", _INITIAL_STEPS_CHECKPOINT_NAME
        )
        refs_ckpt = checkpoint_path(
            tmp_path, "demo", _REFERENCES_CHECKPOINT_NAME
        )
        body_ckpt = checkpoint_path(
            tmp_path, "demo", _BODY_SECTIONS_CHECKPOINT_NAME
        )
        save_checkpoint(
            steps_ckpt,
            Checkpoint(
                input_hash=_initial_steps_input_hash(
                    "demo", "build a thing", out_dir, tmp_path
                ),
                payload=_STEP_JSON,
                created_at=_now_iso(),
            ),
        )
        save_checkpoint(
            refs_ckpt,
            Checkpoint(
                input_hash=_references_input_hash(
                    "demo", "Demo", "build a thing", out_dir, tmp_path
                ),
                payload=_REF_JSON,
                created_at=_now_iso(),
            ),
        )
        save_checkpoint(
            body_ckpt,
            Checkpoint(
                input_hash=_body_sections_input_hash(
                    "demo", "build a thing", out_dir, tmp_path
                ),
                payload=_SYNTHESIS_NULL_JSON,
                created_at=_now_iso(),
            ),
        )

        monkeypatch.setattr("sys.stdin.isatty", lambda: True)

        cached_phase_calls: list[str] = []

        def explode(prompt: str) -> str:
            if _is_intent_prompt(prompt):
                return "[]"
            cached_phase_calls.append(prompt)
            raise AssertionError("invoker must not be called on cache accept")

        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="build a thing",
            input_fn=_silent_input_fn,
            claude_invoker=explode,
            yes=True,
        )
        assert result.plan_path.exists()
        assert cached_phase_calls == []
        # All three checkpoints discarded post-commit.
        assert not steps_ckpt.exists()
        assert not refs_ckpt.exists()
        assert not body_ckpt.exists()


# --- Run log wiring (step 3 of the Run Log Structured Events plan) ---------


import os as _os  # noqa: E402

from plan_tool.run_log import (  # noqa: E402
    RUN_LOG_SCHEMA_VERSION as _RUN_LOG_SCHEMA_VERSION,
    in_flight_path as _in_flight_path,
    run_dir as _run_dir,
)


def _read_run_log(repo_root: Path, slug: str) -> list[dict]:
    """Read the single JSONL run log under ``.plan-tool/runs/<slug>/``.

    Asserts exactly one ``.jsonl`` exists so callers can rely on the
    filename being uniquely the run id.
    """
    rd = _run_dir(repo_root, slug)
    files = sorted(rd.glob("*.jsonl"))
    assert len(files) == 1, f"expected exactly one run log under {rd}, found {files}"
    return [
        json.loads(line)
        for line in files[0].read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _events(log: list[dict]) -> list[str]:
    return [e["event"] for e in log]


def _seed_repo_for_cmd_create(tmp_path: Path) -> tuple[Path, Path, Path]:
    (tmp_path / ".git").mkdir()
    out_dir = tmp_path / "plans"
    out_dir.mkdir()
    manifest = tmp_path / "m.json"
    return tmp_path, out_dir, manifest


def _patch_shell_to_fake_claude(
    monkeypatch: pytest.MonkeyPatch, stdout_for_prompt: Callable[[str], str]
) -> None:
    """Make ``shell.claude_invoke`` route through the sink without spawning a process.

    Bypassing ``create_plan``'s injected ``claude_invoker`` and instead
    patching ``backend_runner.subprocess.Popen`` means the production
    ``shell_claude_invoker`` runs end-to-end, the sink installed by
    ``_RunLogger.install_call_end_sink`` fires for every call, and the
    ``ClaudeCallEnd`` event lands in the JSONL exactly as production
    would emit it.
    """
    from plan_tool import backend_runner
    from plan_tool import shell as shell_module
    from subprocess_doubles import _FakeProc, claude_result_ndjson

    monkeypatch.setattr(shell_module.shutil, "which", lambda _name: "/usr/bin/claude")

    real_popen = backend_runner.subprocess.Popen

    def fake_popen(argv, **kwargs):
        if argv and argv[0] == "git":
            return real_popen(argv, **kwargs)
        # argv is the stream-json batch form (BACKLOG #74); the prompt is last.
        # Wrap the response in a terminal `result` envelope the way real claude
        # does so claude_invoke's collapse rule unwraps it back to text + usage.
        prompt = argv[-1]
        envelope = claude_result_ndjson(
            stdout_for_prompt(prompt),
            usage={
                "input_tokens": 1,
                "output_tokens": 1,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
            },
        )
        return _FakeProc(envelope.splitlines(keepends=True), [], 0)

    monkeypatch.setattr(backend_runner.subprocess, "Popen", fake_popen)


def _stdout_for_prompt(prompt: str) -> str:
    if "Propose an initial plan step-list" in prompt:
        return _STEP_JSON
    if "developer and API reference documentation" in prompt:
        return _REF_JSON
    if "Synthesize plan body sections" in prompt:
        return _SYNTHESIS_NULL_JSON
    return _STEP_JSON


@pytest.mark.integration
class TestCmdCreateRunLog:
    """End-to-end run log wiring through ``cmd_create``.

    These tests drive ``cli.main`` with a patched
    ``backend_runner.subprocess.Popen`` rather than an injected
    ``claude_invoker`` so the
    ``shell.set_active_sink`` path (step 2) participates and the
    JSONL ends up with ``claude_call_end`` events, mirroring production.
    """

    def _invoke_main(
        self,
        monkeypatch: pytest.MonkeyPatch,
        repo_root: Path,
        out_dir: Path,
        manifest: Path,
        slug: str = "demo",
        from_description: str = "Build a thing",
        answers: Optional[list[str]] = None,
        extra_args: Optional[list[str]] = None,
    ) -> int:
        from plan_tool.cli import app as cli_module
        from plan_tool.cli import context as cli_context

        if answers is None:
            answers = _basic_metadata_answers()
        # This suite exercises the production Claude transport specifically;
        # do not let a developer's ambient backend selection change its wire
        # envelope.
        monkeypatch.delenv("PLAN_TOOL_BACKEND", raising=False)
        _patch_shell_to_fake_claude(monkeypatch, _stdout_for_prompt)

        original_create_plan = cli_module.create_plan

        def patched_create_plan(*args, **kwargs):
            kwargs.setdefault("input_fn", _queue_input(answers))
            return original_create_plan(*args, **kwargs)

        monkeypatch.setattr("plan_tool.cli.authoring.create_plan", patched_create_plan)
        monkeypatch.chdir(repo_root)
        # ``create`` now opts INTO the post-write convergence loop and the
        # distill first-pass by default. These run-log tests exercise the
        # non-iterating, non-distilling steps/references/body write path, so
        # opt out via ``--no-iterate`` and ``--no-distill`` to keep their
        # scope unchanged (distill has its own dedicated tests).
        monkeypatch.setattr(sys, "argv", [
            "plan-tool", "--backend", "claude",
            "--manifest", str(manifest), "create", slug,
            "--from", from_description, "--output-dir", str(out_dir),
            "--no-iterate", "--no-distill",
        ])

        return cli_module.main([
            "--backend", "claude", "--manifest", str(manifest), "create", slug,
            "--from", from_description, "--output-dir", str(out_dir),
            "--no-iterate", "--no-distill",
            *(extra_args or []),
        ])

    def test_happy_path_writes_run_start_and_run_end(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo, out_dir, manifest = _seed_repo_for_cmd_create(tmp_path)
        rc = self._invoke_main(monkeypatch, repo, out_dir, manifest)
        assert rc == 0

        log = _read_run_log(repo, "demo")
        assert log[0]["event"] == "run_start"
        assert log[-1]["event"] == "run_end"
        # All events share the run_id.
        run_id = log[0]["run_id"]
        assert all(e["run_id"] == run_id for e in log)
        assert log[-1]["outcome"] == "ok"
        assert log[-1]["rc"] == 0

    def test_run_start_records_command_slug_argv_pid_cwd(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo, out_dir, manifest = _seed_repo_for_cmd_create(tmp_path)
        rc = self._invoke_main(monkeypatch, repo, out_dir, manifest)
        assert rc == 0

        log = _read_run_log(repo, "demo")
        start = log[0]
        assert start["command"] == "create"
        assert start["plan_slug"] == "demo"
        assert start["schema_version"] == _RUN_LOG_SCHEMA_VERSION
        assert start["pid"] == _os.getpid()
        # cwd captured at run start.
        assert start["cwd"] == str(repo)
        # argv is the snapshot of sys.argv at start_run() time.
        assert isinstance(start["argv"], list)
        assert start["argv"][0] == "plan-tool"

    def test_phase_pairs_for_propose_steps_and_propose_references(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo, out_dir, manifest = _seed_repo_for_cmd_create(tmp_path)
        rc = self._invoke_main(monkeypatch, repo, out_dir, manifest)
        assert rc == 0

        log = _read_run_log(repo, "demo")
        phase_starts = [e for e in log if e["event"] == "phase_start"]
        phase_ends = [e for e in log if e["event"] == "phase_end"]
        assert [e["phase"] for e in phase_starts] == [
            "propose_steps", "propose_intents", "propose_references",
            "fetch_reference_docs", "propose_body_sections",
        ]
        assert [e["phase"] for e in phase_ends] == [
            "propose_steps", "propose_intents", "propose_references",
            "fetch_reference_docs", "propose_body_sections",
        ]
        # propose_intents ends "skipped" (``non_interactive``): stdin is not a
        # TTY here and ``--yes`` is off, so the offer never spends a call.
        # propose_steps / propose_references end with "ok"; the body
        # sections phase ends with "skipped" because the fake returns
        # the all-null synthesis JSON (see ``_SYNTHESIS_NULL_JSON``) —
        # all-null is the documented "no synthesized content" signal
        # and the wrapper buckets it as ``skipped`` so runs-diff can
        # spot quality regressions distinct from "ok with content."
        # fetch_reference_docs ends "skipped" too: the conftest network
        # gate routes the fetch into the error path, so no doc text is
        # extracted and the grounding block is empty.
        outcomes = {e["phase"]: e["outcome"] for e in phase_ends}
        assert outcomes["propose_steps"] == "ok"
        assert outcomes["propose_intents"] == "skipped"
        assert outcomes["propose_references"] == "ok"
        assert outcomes["fetch_reference_docs"] == "skipped"
        assert outcomes["propose_body_sections"] == "skipped"

    def test_checkpoint_save_emitted_after_successful_claude_call(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo, out_dir, manifest = _seed_repo_for_cmd_create(tmp_path)
        rc = self._invoke_main(monkeypatch, repo, out_dir, manifest)
        assert rc == 0

        log = _read_run_log(repo, "demo")
        saves = [e for e in log if e["event"] == "checkpoint_save"]
        names = {e["name"] for e in saves}
        assert names == {
            _INITIAL_STEPS_CHECKPOINT_NAME,
            _REFERENCES_CHECKPOINT_NAME,
            _REFERENCE_DOCS_CHECKPOINT_NAME,
            _BODY_SECTIONS_CHECKPOINT_NAME,
        }
        for s in saves:
            assert s["payload_bytes"] > 0
            assert s["input_hash"]

    def test_checkpoint_hit_emitted_on_resume(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo, out_dir, manifest = _seed_repo_for_cmd_create(tmp_path)

        # Pre-seed both checkpoints with input hashes matching this run.
        steps_ckpt = checkpoint_path(repo, "demo", _INITIAL_STEPS_CHECKPOINT_NAME)
        save_checkpoint(
            steps_ckpt,
            Checkpoint(
                input_hash=_initial_steps_input_hash(
                    "demo", "Build a thing", out_dir, repo
                ),
                payload=_STEP_JSON,
                created_at=_now_iso(),
            ),
        )
        refs_ckpt = checkpoint_path(repo, "demo", _REFERENCES_CHECKPOINT_NAME)
        save_checkpoint(
            refs_ckpt,
            Checkpoint(
                input_hash=_references_input_hash(
                    "demo", "Demo Plan", "Build a thing", out_dir, repo
                ),
                payload=_REF_JSON,
                created_at=_now_iso(),
            ),
        )
        body_ckpt = checkpoint_path(repo, "demo", _BODY_SECTIONS_CHECKPOINT_NAME)
        save_checkpoint(
            body_ckpt,
            Checkpoint(
                input_hash=_body_sections_input_hash(
                    "demo", "Build a thing", out_dir, repo
                ),
                payload=_SYNTHESIS_NULL_JSON,
                created_at=_now_iso(),
            ),
        )

        rc = self._invoke_main(monkeypatch, repo, out_dir, manifest)
        assert rc == 0

        log = _read_run_log(repo, "demo")
        hit_names = {e["name"] for e in log if e["event"] == "checkpoint_hit"}
        assert hit_names == {
            _INITIAL_STEPS_CHECKPOINT_NAME,
            _REFERENCES_CHECKPOINT_NAME,
            _BODY_SECTIONS_CHECKPOINT_NAME,
        }
        # No claude_call_* events when all phases come from cache.
        kinds = _events(log)
        assert "claude_call_start" not in kinds
        assert "claude_call_end" not in kinds

    def test_checkpoint_discard_success_after_post_write_reparse(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo, out_dir, manifest = _seed_repo_for_cmd_create(tmp_path)
        rc = self._invoke_main(monkeypatch, repo, out_dir, manifest)
        assert rc == 0

        log = _read_run_log(repo, "demo")
        discards = [
            e for e in log
            if e["event"] == "checkpoint_discard" and e["reason"] == "success"
        ]
        names = sorted(e["name"] for e in discards)
        assert names == sorted([
            _INITIAL_STEPS_CHECKPOINT_NAME,
            _REFERENCES_CHECKPOINT_NAME,
            _REFERENCE_DOCS_CHECKPOINT_NAME,
            _BODY_SECTIONS_CHECKPOINT_NAME,
        ])

    def test_checkpoint_discard_force_when_user_declines_resume(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo, out_dir, manifest = _seed_repo_for_cmd_create(tmp_path)

        steps_ckpt = checkpoint_path(repo, "demo", _INITIAL_STEPS_CHECKPOINT_NAME)
        save_checkpoint(
            steps_ckpt,
            Checkpoint(
                input_hash=_initial_steps_input_hash(
                    "demo", "Build a thing", out_dir, repo
                ),
                payload=_STEP_JSON,
                created_at=_now_iso(),
            ),
        )

        # Make sys.stdin look like a TTY so the resume prompt is asked.
        # ``prompt_metadata`` runs before ``propose_steps_from_claude``, so
        # the resume "n" comes after the metadata answers. The trailing ""
        # accepts the single re-proposed step at the change-type review gate
        # (TTY → interactive review), which runs once steps are finalized.
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        answers = _basic_metadata_answers() + ["n", ""]

        rc = self._invoke_main(
            monkeypatch, repo, out_dir, manifest, answers=answers
        )
        assert rc == 0

        log = _read_run_log(repo, "demo")
        force_discards = [
            e for e in log
            if e["event"] == "checkpoint_discard" and e["reason"] == "force"
        ]
        assert any(
            e["name"] == _INITIAL_STEPS_CHECKPOINT_NAME for e in force_discards
        )

    def test_run_end_outcome_error_when_create_plan_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool.cli import context as cli_context

        repo, out_dir, manifest = _seed_repo_for_cmd_create(tmp_path)
        # Pre-create a colliding plan so create_plan raises FileExistsError
        # (cmd_create catches it, returns rc=1; outcome stays "error").
        (out_dir / "2-demo.md").write_text("x", encoding="utf-8")

        original_create_plan = cli_module.create_plan

        def patched(*args, **kwargs):
            kwargs.setdefault("input_fn", _queue_input([]))
            kwargs["claude_invoker"] = lambda prompt: _STEP_JSON
            kwargs["replace_on_collision"] = False
            return original_create_plan(*args, **kwargs)

        monkeypatch.setattr("plan_tool.cli.authoring.create_plan", patched)
        monkeypatch.chdir(repo)

        rc = cli_module.main([
            "--manifest", str(manifest), "create", "demo",
            "--from", "build a thing", "--output-dir", str(out_dir),
            "--no-iterate",
        ])
        assert rc == 1

        log = _read_run_log(repo, "demo")
        assert log[0]["event"] == "run_start"
        assert log[-1]["event"] == "run_end"
        assert log[-1]["outcome"] == "error"
        assert log[-1]["rc"] == 1

    def test_run_end_outcome_interrupted_when_keyboard_interrupt(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool.cli import context as cli_context

        repo, out_dir, manifest = _seed_repo_for_cmd_create(tmp_path)

        def boom(*args, **kwargs):
            raise KeyboardInterrupt()

        monkeypatch.setattr("plan_tool.cli.authoring.create_plan", boom)
        monkeypatch.chdir(repo)

        with pytest.raises(SystemExit) as exc:
            cli_module.main([
                "--manifest", str(manifest), "create", "demo",
                "--from", "build a thing", "--output-dir", str(out_dir),
                "--no-iterate",
            ])
        assert exc.value.code == 130

        log = _read_run_log(repo, "demo")
        assert log[-1]["event"] == "run_end"
        assert log[-1]["outcome"] == "interrupted"
        assert log[-1]["rc"] == 130

    def test_in_flight_snapshot_written_at_start_and_removed_at_end(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool.cli import context as cli_context

        repo, out_dir, manifest = _seed_repo_for_cmd_create(tmp_path)
        snap_path = _in_flight_path(repo, "demo")

        snapshot_seen: dict[str, bool] = {"present": False}
        original_create_plan = cli_module.create_plan

        def patched_create_plan(*args, **kwargs):
            # Mid-run: the in-flight snapshot file should exist.
            snapshot_seen["present"] = snap_path.exists()
            kwargs.setdefault("input_fn", _queue_input(_basic_metadata_answers()))
            kwargs["claude_invoker"] = lambda prompt: _stdout_for_prompt(prompt)
            return original_create_plan(*args, **kwargs)

        monkeypatch.setattr("plan_tool.cli.authoring.create_plan", patched_create_plan)
        monkeypatch.chdir(repo)

        rc = cli_module.main([
            "--manifest", str(manifest), "create", "demo",
            "--from", "build a thing", "--output-dir", str(out_dir),
            "--no-iterate",
        ])
        assert rc == 0
        assert snapshot_seen["present"], "in-flight snapshot missing during run"
        assert not snap_path.exists(), "in-flight snapshot survived run end"

    def test_run_log_dir_uses_dot_plan_tool_runs_layout(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo, out_dir, manifest = _seed_repo_for_cmd_create(tmp_path)
        rc = self._invoke_main(monkeypatch, repo, out_dir, manifest)
        assert rc == 0

        runs_dir = repo / ".plan-tool" / "runs" / "demo"
        files = list(runs_dir.glob("*.jsonl"))
        assert len(files) == 1
        run_id = files[0].stem
        # ``new_run_id`` shape: timestamp-with-dashes + 6 hex chars.
        # We don't pin the timestamp, just the trailing "-<6 hex>" tail.
        assert len(run_id) >= 7
        assert run_id[-7] == "-"
        assert all(c in "0123456789abcdef" for c in run_id[-6:])


@pytest.mark.integration
class TestCmdCreateResultSink:
    """``cmd_create`` deposits its ``CreateResult`` into a caller-set sink.

    The direct-pipeline verbs set ``args._create_result_sink`` to a list to
    receive the in-memory result without re-reading the plan from disk. These
    tests stub the ``plan_tool.cli.authoring.create_plan`` module global (the
    sanctioned seam) and drive ``cmd_create`` with a real parser-built
    ``Namespace`` carrying the sink.
    """

    def _namespace(
        self, out_dir: Path, manifest: Path, slug: str = "demo"
    ) -> "argparse.Namespace":
        from plan_tool.cli.app import build_parser

        return build_parser().parse_args([
            "--manifest", str(manifest), "create", slug,
            "--from", "build a thing", "--output-dir", str(out_dir),
            "-y", "--no-iterate", "--no-distill",
        ])

    def test_create_result_sink_receives_result(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli.authoring import cmd_create

        repo, out_dir, manifest = _seed_repo_for_cmd_create(tmp_path)
        result = CreateResult(
            plan_path=out_dir / "demo.md",
            manifest_path=manifest,
            manifest_updated=True,
        )
        monkeypatch.setattr(
            "plan_tool.cli.authoring.create_plan", lambda *a, **k: result
        )
        monkeypatch.chdir(repo)

        args = self._namespace(out_dir, manifest)
        sink: list[CreateResult] = []
        args._create_result_sink = sink

        rc = cmd_create(args)
        assert rc == 0
        assert sink == [result]

    def test_create_result_sink_receives_inline_split_proposal(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli.authoring import cmd_create
        from plan_tool.create import SplitProposal

        repo, out_dir, manifest = _seed_repo_for_cmd_create(tmp_path)
        result = CreateResult(
            plan_path=None,
            manifest_path=manifest,
            manifest_updated=False,
            split_proposal=SplitProposal(entries=[]),
        )
        monkeypatch.setattr(
            "plan_tool.cli.authoring.create_plan", lambda *a, **k: result
        )
        emitted: list[SplitProposal] = []

        # The parser-built namespace uses inline ``--from``. Capture the
        # worksheet emission to prove the inline compatibility branch runs.
        monkeypatch.setattr(
            "plan_tool.cli.authoring._emit_split_proposal",
            lambda proposal, **_kwargs: emitted.append(proposal),
        )
        monkeypatch.chdir(repo)

        args = self._namespace(out_dir, manifest)
        sink: list[CreateResult] = []
        args._create_result_sink = sink

        rc = cmd_create(args)
        assert rc == 0
        assert sink == [result]
        assert sink[0].split_proposal is not None
        assert sink[0].file_backed_route is None
        assert sink[0].plan_path is None
        assert emitted == [result.split_proposal]

    def test_create_result_sink_empty_on_create_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli.authoring import cmd_create
        from plan_tool.create import CreateError

        repo, out_dir, manifest = _seed_repo_for_cmd_create(tmp_path)

        def boom(*a, **k):
            raise CreateError("nope")

        monkeypatch.setattr("plan_tool.cli.authoring.create_plan", boom)
        monkeypatch.chdir(repo)

        args = self._namespace(out_dir, manifest)
        sink: list[CreateResult] = []
        args._create_result_sink = sink

        rc = cmd_create(args)
        assert rc == 1
        assert sink == []

    def test_create_result_sink_deposits_once(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli.authoring import cmd_create

        repo, out_dir, manifest = _seed_repo_for_cmd_create(tmp_path)
        result = CreateResult(
            plan_path=out_dir / "demo.md",
            manifest_path=manifest,
            manifest_updated=True,
        )
        monkeypatch.setattr(
            "plan_tool.cli.authoring.create_plan", lambda *a, **k: result
        )
        monkeypatch.chdir(repo)

        args = self._namespace(out_dir, manifest)
        sink: list[CreateResult] = []
        args._create_result_sink = sink

        cmd_create(args)
        assert len(sink) == 1


# --- Post-write iteration loop (step 2 of the iterative-completeness plan) ---


from plan_tool.convergence import IterativeBudget as _IterativeBudget  # noqa: E402
from plan_tool.launcher import ApplyFindingResult as _ApplyFindingResult  # noqa: E402
from plan_tool.review import Recommendation as _Recommendation  # noqa: E402


def _rec(rec_id: str, *, anchor: Optional[str] = None) -> _Recommendation:
    """Build a minimal :class:`Recommendation` for iteration-loop tests.

    Uses an apply-eligible source (``body-completeness``) so the apply
    loop actually dispatches it -- these tests exercise loop mechanics
    (convergence, drift, checkpointing), not source-eligibility, which
    is covered directly in ``test_review.py``."""
    return _Recommendation(
        id=rec_id,
        source="body-completeness",
        severity="medium",
        step_id=None,
        title=f"finding {rec_id}",
        body=f"body for {rec_id}",
        anchor=anchor,
    )


def _stub_apply_result() -> _ApplyFindingResult:
    """A no-op :class:`ApplyFindingResult` for the fake apply_finding."""
    return _ApplyFindingResult(
        step_id=None,
        exit_code=0,
        verdict="APPLIED",
        summary="",
        diff_text="",
        pre_snapshot={},
        stdout="",
    )


def _iter_invoker(counter: dict) -> Callable[[str], str]:
    """Counted invoker that returns valid steps/refs/body-sections JSON."""

    def invoker(prompt: str) -> str:
        counter["n"] += 1
        if "developer and API reference documentation" in prompt:
            return _REF_JSON
        if "Synthesize plan body sections" in prompt:
            return _SYNTHESIS_NULL_JSON
        return _STEP_JSON

    return invoker


@pytest.mark.integration
class TestCreatePlanIterationLoop:
    """Post-write iteration loop in ``create_plan`` (step 2).

    Each test injects a fake ``claude_invoker`` plus monkey-patched
    ``apply_finding`` / ``collect_deterministic_findings`` at
    ``plan_tool.create.*`` scope so the loop runs deterministically
    without spawning subprocesses.
    """

    def test_create_plan_with_disabled_budget_is_no_op(
        self, tmp_path: Path
    ) -> None:
        """Default ``IterativeBudget(enabled=False)`` skips the loop.

        Invoker count stays at 2 (initial steps + references) — the
        pre-step-2 call count for ``create_plan``.
        """
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        counter = {"n": 0}
        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="build a thing",
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=_iter_invoker(counter),
        )
        assert result.plan_path.exists()
        assert counter["n"] == 3

    def test_create_plan_iterates_until_converged(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """One apply pass resolves all findings → loop exits ``converged``.

        The applied finding is apply-eligible (not deferred), so the
        post-apply short-circuit doesn't fire; the iteration re-proposes
        once, then the next ``should_continue`` converges (no findings).
        Invoker fires 5 times: round-0 steps+refs+body + round-1
        steps+refs re-author.
        """
        from plan_tool import create as create_module

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        collect_calls = {"n": 0}

        def fake_collect(*args, **kwargs):
            collect_calls["n"] += 1
            return [_rec("A")] if collect_calls["n"] == 1 else []

        monkeypatch.setattr(
            create_module, "collect_deterministic_findings", fake_collect
        )
        monkeypatch.setattr(
            create_module, "apply_finding", lambda *a, **kw: _stub_apply_result()
        )

        counter = {"n": 0}
        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="build a thing",
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=_iter_invoker(counter),
            budget=_IterativeBudget(enabled=True, max_iterations=3),
            skip_prose_reproposal=False,
        )
        assert result.plan_path.exists()
        assert result.iteration_stage_failure is None
        # Round-0 (3) + one round-1 re-author (steps+refs = 2) = 5.
        assert counter["n"] == 5
        # Two collect calls: pre-loop (round 0) + end-of-loop (post-iter).
        # No post-apply re-derive here -- nothing was deferred this round.
        assert collect_calls["n"] == 2

    def test_intent_survives_the_iteration_status_merge(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The loop rebuilds the re-proposal's steps with
        ``model_copy(update={"status": ...})``, which carries every unlisted
        field forward — a zero-diff site this pins rather than edits."""
        from plan_tool import create as create_module

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()

        collect_calls = {"n": 0}

        def fake_collect(*args, **kwargs):
            collect_calls["n"] += 1
            return [_rec("A")] if collect_calls["n"] == 1 else []

        monkeypatch.setattr(
            create_module, "collect_deterministic_findings", fake_collect
        )
        monkeypatch.setattr(
            create_module, "apply_finding", lambda *a, **kw: _stub_apply_result()
        )

        counter = {"n": 0}
        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=tmp_path / "m.json",
            from_description="build a thing",
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=_iter_invoker(counter),
            budget=_IterativeBudget(enabled=True, max_iterations=3),
            skip_prose_reproposal=False,
        )

        # The re-proposal ran (5 calls), so the merged steps came through the
        # status merge — and still carry ``_STEP_JSON``'s intent.
        assert counter["n"] == 5
        plan = parse_plan(result.plan_path)
        assert [s.intent for s in plan.steps] == ["prove first lands"]

    def test_create_apply_loop_hoists_and_forwards_telemetry_keys(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool import create as create_module
        import plan_tool.review_persistence as persistence

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"
        findings = [_rec("A", anchor="overview"), _rec("B")]
        monkeypatch.setattr(
            create_module,
            "collect_deterministic_findings",
            lambda *a, **kw: findings,
        )
        fingerprint_calls: list[Path] = []
        monkeypatch.setattr(
            persistence,
            "compute_plan_fingerprint",
            lambda path: fingerprint_calls.append(path) or "shared-plan-fp",
        )
        apply_calls: list[dict] = []

        def fake_apply(*args, **kwargs):
            apply_calls.append(kwargs)
            return _stub_apply_result()

        monkeypatch.setattr(create_module, "apply_finding", fake_apply)
        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="build a thing",
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=_iter_invoker({"n": 0}),
            budget=_IterativeBudget(enabled=True, max_iterations=1),
        )

        assert result.plan_path.exists()
        assert [call["anchor"] for call in apply_calls] == ["overview", ""]
        assert {call["plan_fingerprint"] for call in apply_calls} == {
            "shared-plan-fp"
        }
        assert all("record_verdict" not in call for call in apply_calls)
        assert fingerprint_calls == [result.plan_path]

    def test_create_apply_loop_fingerprint_failure_is_best_effort(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool import create as create_module
        import plan_tool.review_persistence as persistence

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"
        rec = _rec("A", anchor="overview")
        monkeypatch.setattr(
            create_module,
            "collect_deterministic_findings",
            lambda *a, **kw: [rec],
        )

        def fail_fingerprint(_path):
            raise OSError("fingerprint unavailable")

        monkeypatch.setattr(
            persistence, "compute_plan_fingerprint", fail_fingerprint
        )
        apply_calls: list[dict] = []
        monkeypatch.setattr(
            create_module,
            "apply_finding",
            lambda *a, **kw: apply_calls.append(kw) or _stub_apply_result(),
        )
        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="build a thing",
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=_iter_invoker({"n": 0}),
            budget=_IterativeBudget(enabled=True, max_iterations=1),
        )

        assert result.plan_path.exists()
        assert [(call["anchor"], call["plan_fingerprint"]) for call in apply_calls] == [
            ("overview", "")
        ]

    def test_iteration_dedups_apply_dispatch_and_keeps_finding_open(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A re-surfacing finding is dispatched once but still counts open."""
        from plan_tool import create as create_module

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        rounds = [
            [_rec("persistent-a")],
            [_rec("persistent-a"), _rec("r1-b"), _rec("r1-c"), _rec("r1-d")],
            [_rec("persistent-a"), _rec("r2-e"), _rec("r2-f"), _rec("r2-g")],
        ]
        scan_n = {"i": 0}

        def fake_collect(*a, **kw):  # noqa: ARG001
            i = min(scan_n["i"], len(rounds) - 1)
            scan_n["i"] += 1
            return rounds[i]

        monkeypatch.setattr(
            create_module, "collect_deterministic_findings", fake_collect
        )
        applied_bodies: list[str] = []

        def fake_apply_finding(plan_path, **kwargs):  # noqa: ARG001
            applied_bodies.append(kwargs.get("finding_body", ""))
            return _stub_apply_result()

        monkeypatch.setattr(create_module, "apply_finding", fake_apply_finding)

        from plan_tool.run_log import RunLogWriter

        run_logger = RunLogWriter.start(
            repo_root=tmp_path,
            slug="demo",
            command="create",
            argv=["plan-tool", "create", "demo", "--iterate"],
        )
        counter = {"n": 0}
        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="build a thing",
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=_iter_invoker(counter),
            budget=_IterativeBudget(enabled=True, max_iterations=2),
            skip_prose_reproposal=False,
            run_logger=run_logger,
        )

        assert result.plan_path.exists()
        assert sum(body.endswith("body for persistent-a") for body in applied_bodies) == 1
        assert any(body.endswith("body for r1-b") for body in applied_bodies)
        assert all("confidence: limited" in body for body in applied_bodies)
        log = _read_run_log(tmp_path, "demo")
        apply_starts = [
            e for e in log
            if e["event"] == "phase_start"
            and e["phase"] == "apply_finding_dispatch"
        ]
        assert [
            e["finding_label"] for e in apply_starts
        ].count("body for persistent-a") == 1

        err = capsys.readouterr().err
        assert "max_iterations" in err
        assert "open_findings=4" in err

    def test_iteration_post_apply_dedup_short_circuits_deferred_rederive(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Deferred re-derive treats already-dispatched eligible findings as open."""
        from plan_tool import create as create_module

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        deferred = _Recommendation(
            id="info-note",
            source="body-completeness",
            severity="info",
            step_id=None,
            title="advisory note",
            body="body for info-note",
        )
        scan_n = {"i": 0}

        def fake_collect(*a, **kw):  # noqa: ARG001
            scan_n["i"] += 1
            return [_rec("persistent-a"), deferred]

        monkeypatch.setattr(
            create_module, "collect_deterministic_findings", fake_collect
        )
        applied_bodies: list[str] = []

        def fake_apply_finding(plan_path, **kwargs):  # noqa: ARG001
            applied_bodies.append(kwargs.get("finding_body", ""))
            return _stub_apply_result()

        monkeypatch.setattr(create_module, "apply_finding", fake_apply_finding)

        counter = {"n": 0}
        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="build a thing",
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=_iter_invoker(counter),
            budget=_IterativeBudget(enabled=True, max_iterations=5),
            skip_prose_reproposal=False,
        )

        assert result.plan_path.exists()
        assert len(applied_bodies) == 1
        assert applied_bodies[0].endswith("body for persistent-a")
        assert "confidence: limited" in applied_bodies[0]
        # Initial steps + refs + body only: the post-apply dedup halt avoided
        # an iteration re-proposal even though skip_prose_reproposal=False.
        assert counter["n"] == 3
        # Initial scan plus the post-apply re-derive, then halt.
        assert scan_n["i"] == 2

    def test_create_plan_stops_on_marginal_overlap(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Findings unchanged across rounds → ``"marginal"`` halt."""
        from plan_tool import create as create_module

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        # Same finding set every collect call → 100% overlap → marginal.
        monkeypatch.setattr(
            create_module,
            "collect_deterministic_findings",
            lambda *a, **kw: [_rec("A"), _rec("B")],
        )
        monkeypatch.setattr(
            create_module, "apply_finding", lambda *a, **kw: _stub_apply_result()
        )

        counter = {"n": 0}
        create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="build a thing",
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=_iter_invoker(counter),
            budget=_IterativeBudget(enabled=True, max_iterations=5),
            skip_prose_reproposal=False,
        )
        # 2 initial + 2 round-1 re-author; loop exits with marginal on
        # the iteration-2 should_continue check, before iter-2 re-author.
        assert counter["n"] == 5
        err = capsys.readouterr().err
        assert "iteration loop stopped: marginal" in err

    def test_create_plan_stops_on_max_iterations(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """New finding ID each round → exits after exactly ``max_iterations``."""
        from plan_tool import create as create_module

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        # Stream a fresh, apply-eligible finding ID on EVERY collect call
        # (a counter, so it never exhausts regardless of how many times
        # the loop re-derives findings). Fresh ids each round keep the
        # marginal predicate False; always-apply-eligible keeps the
        # post-apply short-circuit from firing, so the loop runs until the
        # max_iterations cap.
        fresh = {"n": 0}

        def fake_collect(*args, **kwargs):
            fresh["n"] += 1
            return [_rec(f"A{fresh['n']}")]

        monkeypatch.setattr(
            create_module, "collect_deterministic_findings", fake_collect
        )
        monkeypatch.setattr(
            create_module, "apply_finding", lambda *a, **kw: _stub_apply_result()
        )

        counter = {"n": 0}
        create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="build a thing",
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=_iter_invoker(counter),
            budget=_IterativeBudget(enabled=True, max_iterations=2),
        )
        err = capsys.readouterr().err
        assert "iteration loop stopped: max_iterations" in err

    def test_create_plan_stops_on_deadline_exceeded(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """``budget_seconds=0`` exhausts the deadline before iter 1's apply.

        ``ConvergenceState.started_at`` captures ``time.monotonic()`` via a
        ``default_factory`` reference bound at class-definition time, so
        monkey-patching ``time.monotonic`` after the fact won't move the
        deadline. Using ``budget_seconds=0`` is the in-band trigger:
        ``should_continue`` evaluates ``now - started >= 0`` on the first
        check and stops with ``deadline_exceeded``.
        """
        from plan_tool import create as create_module

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        apply_calls = {"n": 0}

        def fake_apply(*a, **kw):
            apply_calls["n"] += 1
            return _stub_apply_result()

        monkeypatch.setattr(
            create_module,
            "collect_deterministic_findings",
            lambda *a, **kw: [_rec("A")],
        )
        monkeypatch.setattr(create_module, "apply_finding", fake_apply)

        counter = {"n": 0}
        create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="build a thing",
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=_iter_invoker(counter),
            budget=_IterativeBudget(
                enabled=True, max_iterations=3, budget_seconds=0
            ),
        )
        # 2 initial invocations, then loop exits before iter-1 apply runs.
        assert counter["n"] == 3
        assert apply_calls["n"] == 0
        err = capsys.readouterr().err
        assert "iteration loop stopped: deadline_exceeded" in err

    def test_create_plan_stops_on_time_budget_with_resume_hint(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """The cooperative wall-clock cap (#123) stops the loop cleanly at a
        round boundary and prints a resume hint.

        ``hard_budget_seconds`` is a strictly-positive elapsed cap, so unlike
        ``budget_seconds=0`` it can't trigger at elapsed≈0 on the first check;
        the loop also binds the real ``time.monotonic`` for ``started_at`` and
        ``should_continue``'s default clock. So we force the reason at the
        ``should_continue`` seam and assert the wiring: the time-budget banner +
        resume hint print, and the run completes cleanly (no raise / non-zero).
        The clock→reason half is covered by tests/test_convergence.py.
        """
        from plan_tool import create as create_module

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        monkeypatch.setattr(
            create_module,
            "collect_deterministic_findings",
            lambda *a, **kw: [_rec("A")],
        )
        monkeypatch.setattr(
            create_module,
            "should_continue",
            lambda *a, **kw: (False, "time_budget_exceeded"),
        )

        counter = {"n": 0}
        create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="build a thing",
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=_iter_invoker(counter),
            budget=_IterativeBudget(
                enabled=True, max_iterations=3, hard_budget_seconds=300
            ),
        )
        err = capsys.readouterr().err
        assert "iteration loop stopped: time_budget_exceeded" in err
        assert "--time-budget" in err

    def test_iteration_step_failure_aborts_with_failure_signal(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A failed step re-proposal mid-loop aborts with a FAILURE banner.

        Round 0's steps parse cleanly; iteration 1's re-proposal returns
        an invalid graph (``propose_steps_from_claude`` → None). The loop
        must NOT limp on to a ``marginal`` stop — it aborts, emits a
        distinct FAILURE banner, and carries the reason out via
        ``CreateResult.iteration_stage_failure`` (the CLI returns 0 for the
        resumable published plan). The round-0 plan is still on disk.
        """
        from plan_tool import create as create_module

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        # One apply-eligible finding every round so the loop reaches the
        # re-proposal rather than short-circuiting on an empty apply set.
        monkeypatch.setattr(
            create_module,
            "collect_deterministic_findings",
            lambda *a, **kw: [_rec("A")],
        )
        monkeypatch.setattr(
            create_module, "apply_finding", lambda *a, **kw: _stub_apply_result()
        )

        step_calls = {"n": 0}

        def invoker(prompt: str) -> str:
            if "developer and API reference documentation" in prompt:
                return _REF_JSON
            if "Synthesize plan body sections" in prompt:
                return _SYNTHESIS_NULL_JSON
            step_calls["n"] += 1
            # Round 0 parses; iteration 1's re-proposal is the invalid graph.
            return _STEP_JSON if step_calls["n"] == 1 else _INVALID_STEP_JSON

        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="build a thing",
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=invoker,
            budget=_IterativeBudget(enabled=True, max_iterations=5),
            skip_prose_reproposal=False,
        )

        assert result.plan_path.exists()
        assert result.iteration_stage_failure is not None
        assert "iteration 1" in result.iteration_stage_failure
        err = capsys.readouterr().err
        assert "iteration loop FAILED" in err
        # The abort must not masquerade as a clean convergence stop.
        assert "iteration loop stopped: marginal" not in err
        # Banner points at the actual resolution for the open findings.
        assert "plan-tool detail demo" in err
        assert "plan-tool reconcile-plan-walk demo" in err

    def test_iteration_terminal_unparseable_references_stops_before_step_reproposal(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Keep the post-apply plan unchanged when iteration research fails."""
        from plan_tool import create as create_module

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        monkeypatch.setattr(
            create_module,
            "collect_deterministic_findings",
            lambda *a, **kw: [_rec("A")],
        )
        post_apply_plan: dict[str, str] = {}

        def apply_and_snapshot(plan_path: Path, **_kwargs: object) -> _ApplyFindingResult:
            create_module._patch_plan_body_section(
                plan_path, "References", "post-apply reference"
            )
            post_apply_plan["text"] = plan_path.read_text(encoding="utf-8")
            return _stub_apply_result()

        monkeypatch.setattr(create_module, "apply_finding", apply_and_snapshot)

        step_iterations: list[int] = []

        def propose_steps(*_args: object, **kwargs: object) -> list[Step]:
            iteration = kwargs.get("iteration", 0)
            assert isinstance(iteration, int)
            step_iterations.append(iteration)
            if iteration:
                raise AssertionError("malformed research must stop step re-proposal")
            return [Step(id=1, title="Initial step")]

        def propose_references(*_args: object, **kwargs: object) -> ReferenceResearchResult:
            return (
                ReferenceResearchResult.unparseable()
                if kwargs.get("iteration") == 1
                else ReferenceResearchResult.from_references([])
            )

        monkeypatch.setattr(create_module, "propose_steps_from_claude", propose_steps)
        monkeypatch.setattr(
            create_module, "propose_references_from_claude", propose_references
        )

        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="build a thing",
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=_iter_invoker({"n": 0}),
            budget=_IterativeBudget(enabled=True, max_iterations=5),
            skip_prose_reproposal=False,
        )

        assert result.iteration_stage_failure is not None
        assert "reference research failed in iteration 1" in result.iteration_stage_failure
        assert step_iterations == [0]
        assert result.plan_path.read_text(encoding="utf-8") == post_apply_plan["text"]
        assert "post-apply reference" in post_apply_plan["text"]
        err = capsys.readouterr().err
        assert "reference research failed in iteration 1" in err
        assert "`create` exits 0" in err

    def test_iteration_terminal_unparseable_references_records_error_phase(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Record malformed iteration research as an error, not a skip."""
        from plan_tool import create as create_module
        from plan_tool.run_log import RunLogWriter

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"
        run_logger = RunLogWriter.start(
            repo_root=tmp_path,
            slug="demo",
            command="create",
            argv=["plan-tool", "create", "demo"],
        )

        monkeypatch.setattr(
            create_module,
            "collect_deterministic_findings",
            lambda *a, **kw: [_rec("A")],
        )
        monkeypatch.setattr(
            create_module, "apply_finding", lambda *a, **kw: _stub_apply_result()
        )
        monkeypatch.setattr(
            create_module,
            "propose_steps_from_claude",
            lambda *_args, **_kwargs: [Step(id=1, title="Initial step")],
        )
        monkeypatch.setattr(
            create_module,
            "propose_references_from_claude",
            lambda *_args, **kwargs: (
                ReferenceResearchResult.unparseable()
                if kwargs.get("iteration") == 1
                else ReferenceResearchResult.from_references([])
            ),
        )

        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="build a thing",
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=_iter_invoker({"n": 0}),
            budget=_IterativeBudget(enabled=True, max_iterations=5),
            skip_prose_reproposal=False,
            run_logger=run_logger,
        )

        assert result.iteration_stage_failure is not None
        iteration_events = [
            event
            for event in _read_run_log(tmp_path, "demo")
            if event.get("phase") == "propose_references"
            and event.get("iteration") == 1
        ]
        assert [event["event"] for event in iteration_events] == [
            "phase_start", "phase_end"
        ]
        assert iteration_events[-1]["outcome"] == "error"

    def test_iteration_stage_failure_preserves_checkpoints_for_resume(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A stage-failure abort KEEPS the round-0 checkpoints so a re-run
        resumes the expensive distill/steps/references/body stages from
        cache instead of re-spending the claude round-trips. (Contrast: a
        clean convergence discards them.)"""
        from plan_tool import create as create_module
        from plan_tool.checkpoint import checkpoint_dir

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        monkeypatch.setattr(
            create_module,
            "collect_deterministic_findings",
            lambda *a, **kw: [_rec("A")],
        )
        monkeypatch.setattr(
            create_module, "apply_finding", lambda *a, **kw: _stub_apply_result()
        )

        step_calls = {"n": 0}

        def invoker(prompt: str) -> str:
            if "developer and API reference documentation" in prompt:
                return _REF_JSON
            if "Synthesize plan body sections" in prompt:
                return _SYNTHESIS_NULL_JSON
            step_calls["n"] += 1
            return _STEP_JSON if step_calls["n"] == 1 else _INVALID_STEP_JSON

        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="build a thing",
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=invoker,
            budget=_IterativeBudget(enabled=True, max_iterations=5),
            skip_prose_reproposal=False,
        )

        assert result.iteration_stage_failure is not None
        # Round-0 checkpoints survive the abort (not discarded), so a
        # re-run can hash-match and resume them.
        ckpt_dir = checkpoint_dir(tmp_path, "demo")
        assert ckpt_dir.is_dir()
        assert list(ckpt_dir.glob("*.json"))

    def test_iteration_clean_converge_discards_checkpoints(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The complement: a clean (converged) finish still discards the
        checkpoints -- they served their purpose and shouldn't linger."""
        from plan_tool import create as create_module
        from plan_tool.checkpoint import checkpoint_dir

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        collect_calls = {"n": 0}

        def fake_collect(*a, **kw):
            collect_calls["n"] += 1
            return [_rec("A")] if collect_calls["n"] == 1 else []

        monkeypatch.setattr(
            create_module, "collect_deterministic_findings", fake_collect
        )
        monkeypatch.setattr(
            create_module, "apply_finding", lambda *a, **kw: _stub_apply_result()
        )

        counter = {"n": 0}
        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="build a thing",
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=_iter_invoker(counter),
            budget=_IterativeBudget(enabled=True, max_iterations=3),
        )

        assert result.iteration_stage_failure is None
        ckpt_dir = checkpoint_dir(tmp_path, "demo")
        # No create-* checkpoint shards linger after a clean finish.
        assert not list(ckpt_dir.glob("create-*.json"))

    @pytest.mark.parametrize(
        ("terminal_case", "expected_signal"),
        [
            ("converged", None),
            ("marginal", "iteration loop stopped: marginal"),
            ("budget", "iteration loop stopped: max_iterations"),
            ("drift", "drift detected"),
            ("parse_halt", "reverted apply-finding edits"),
            ("deferred_only", "are triaged-deferred"),
            ("retry_blocked", "already applied this run"),
        ],
    )
    def test_create_plan_normal_terminal_paths_discard_checkpoints(
        self,
        terminal_case: str,
        expected_signal: Optional[str],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Every normal stop reaches finalization and clears checkpoints."""
        from plan_tool import create as create_module
        from plan_tool.checkpoint import checkpoint_dir

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"
        eligible = _rec("eligible")
        deferred = _Recommendation(
            id="deferred-file-check",
            source="file-check",
            severity="medium",
            step_id=1,
            title="deferred file check",
            body="fix the declared path",
        )
        collect_calls = {"n": 0}

        def collect_terminal_findings(*args, **kwargs):
            collect_calls["n"] += 1
            if terminal_case == "converged":
                return []
            if terminal_case == "marginal":
                return [eligible]
            if terminal_case == "budget":
                return [_rec(f"budget-{collect_calls['n']}")]
            if terminal_case in {"drift", "parse_halt"}:
                return [eligible]
            if terminal_case == "deferred_only":
                return [deferred]
            assert terminal_case == "retry_blocked"
            return [eligible, deferred]

        monkeypatch.setattr(
            create_module,
            "collect_deterministic_findings",
            collect_terminal_findings,
        )
        monkeypatch.setattr(
            create_module,
            "apply_finding",
            lambda *args, **kwargs: _stub_apply_result(),
        )
        if terminal_case == "parse_halt":
            monkeypatch.setattr(
                create_module,
                "revert_apply_if_parse_broken",
                lambda _result: True,
            )
        if terminal_case == "drift":
            from plan_tool import drift_detection

            monkeypatch.setattr(
                drift_detection,
                "check_drift",
                lambda _lock: [tmp_path / "drifted.py"],
            )

        seen_terminal_outcomes: list[Optional[str]] = []
        original_finalize = create_module._finalize_create_plan

        def observe_finalization(*args, **kwargs):
            seen_terminal_outcomes.append(kwargs["iteration_stage_failure"])
            return original_finalize(*args, **kwargs)

        monkeypatch.setattr(
            create_module, "_finalize_create_plan", observe_finalization
        )

        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="build a thing",
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=_iter_invoker({"n": 0}),
            budget=_IterativeBudget(
                enabled=True,
                max_iterations=1 if terminal_case == "budget" else 3,
            ),
            auto_reconcile_on_drift=False,
            skip_prose_reproposal=False,
        )

        captured = capsys.readouterr()
        if expected_signal is not None:
            assert expected_signal in captured.out + captured.err
        assert result.iteration_stage_failure is None
        assert seen_terminal_outcomes == [None]
        assert not list(checkpoint_dir(tmp_path, "demo").glob("create-*.json"))

    def test_no_reproposal_when_only_deferred_findings_remain(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Regression for the original bug report. After the apply phase
        resolves the last apply-eligible finding, leaving only deferred
        (structural) findings, the loop must STOP without re-proposing the
        step graph -- the re-proposal is where the invalid-graph failure
        came from, and it can't fix structural findings anyway.

        Asserts the step-proposal invoker fires exactly once (round 0); a
        second call would mean the wasted re-proposal ran.
        """
        from plan_tool import create as create_module

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        # A deferred (structural) finding -- file-check is not in
        # APPLY_ELIGIBLE_SOURCES, so triage always defers it.
        deferred = _Recommendation(
            id="step1-file-check-x", source="file-check", severity="medium",
            step_id=1, title="path doesn't resolve", body="fix the path",
        )
        collect_calls = {"n": 0}

        def fake_collect(*a, **kw):
            collect_calls["n"] += 1
            # First (pre-loop) call: one apply-eligible + one deferred.
            # Second (post-apply) call: the eligible one is resolved, only
            # the deferred structural finding remains.
            if collect_calls["n"] == 1:
                return [_rec("A"), deferred]
            return [deferred]

        monkeypatch.setattr(
            create_module, "collect_deterministic_findings", fake_collect
        )
        monkeypatch.setattr(
            create_module, "apply_finding", lambda *a, **kw: _stub_apply_result()
        )

        step_calls = {"n": 0}

        def invoker(prompt: str) -> str:
            if "developer and API reference documentation" in prompt:
                return _REF_JSON
            if "Synthesize plan body sections" in prompt:
                return _SYNTHESIS_NULL_JSON
            step_calls["n"] += 1
            return _STEP_JSON

        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="build a thing",
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=invoker,
            budget=_IterativeBudget(enabled=True, max_iterations=5),
        )

        assert result.plan_path.exists()
        # Clean stop, NOT a stage failure: the fragile re-proposal was skipped.
        assert result.iteration_stage_failure is None
        # Step proposal ran only for round 0 -- no wasted iteration re-proposal.
        assert step_calls["n"] == 1

    def test_iteration_references_patched_despite_step_failure(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A successful refs round isn't discarded when steps fail (bug fix).

        The references patch now runs independently of the steps outcome.
        Iteration 1 returns fresh references AND a broken step graph; the
        fresh references' URL must still land in the plan body even though
        the loop aborts on the step failure.
        """
        from plan_tool import create as create_module

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        monkeypatch.setattr(
            create_module,
            "collect_deterministic_findings",
            lambda *a, **kw: [_rec("A")],
        )
        monkeypatch.setattr(
            create_module, "apply_finding", lambda *a, **kw: _stub_apply_result()
        )

        step_calls = {"n": 0}
        ref_calls = {"n": 0}

        def invoker(prompt: str) -> str:
            if "developer and API reference documentation" in prompt:
                ref_calls["n"] += 1
                # Round 0 baseline refs, then distinct iteration-1 refs.
                return _REF_JSON if ref_calls["n"] == 1 else _REF_JSON_ITER
            if "Synthesize plan body sections" in prompt:
                return _SYNTHESIS_NULL_JSON
            step_calls["n"] += 1
            return _STEP_JSON if step_calls["n"] == 1 else _INVALID_STEP_JSON

        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="build a thing",
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=invoker,
            budget=_IterativeBudget(enabled=True, max_iterations=5),
            skip_prose_reproposal=False,
        )

        # Steps failed in iteration 1 (loop aborted) ...
        assert result.iteration_stage_failure is not None
        assert ref_calls["n"] == 2
        # ... but the iteration's references were still patched in.
        body = result.plan_path.read_text(encoding="utf-8")
        assert "https://updated.example.com" in body
        assert "Any work completed before\n  the failed stage remains published" in (
            capsys.readouterr().err
        )

    def test_iteration_hash_differs_from_round_zero(
        self, tmp_path: Path
    ) -> None:
        """Iteration kwarg perturbs the steps hash; ``iteration=0`` is the legacy default.

        Same check on the references hash for parity.
        """
        out_dir = tmp_path / "plans"

        # iteration=0 explicit == iteration omitted (legacy 4-arg call).
        h0_legacy = _initial_steps_input_hash(
            "demo", "build a thing", out_dir, tmp_path
        )
        h0_explicit = _initial_steps_input_hash(
            "demo", "build a thing", out_dir, tmp_path, iteration=0
        )
        assert h0_legacy == h0_explicit

        h1 = _initial_steps_input_hash(
            "demo", "build a thing", out_dir, tmp_path, iteration=1
        )
        h2 = _initial_steps_input_hash(
            "demo", "build a thing", out_dir, tmp_path, iteration=2
        )
        assert h0_legacy != h1
        assert h1 != h2

        # References hash exhibits the same shape.
        r0_legacy = _references_input_hash(
            "demo", "Demo", "build a thing", out_dir, tmp_path
        )
        r0_explicit = _references_input_hash(
            "demo", "Demo", "build a thing", out_dir, tmp_path, iteration=0
        )
        r1 = _references_input_hash(
            "demo", "Demo", "build a thing", out_dir, tmp_path, iteration=1
        )
        assert r0_legacy == r0_explicit
        assert r0_legacy != r1

    def test_round_zero_hash_unchanged_from_pre_step_2(
        self, tmp_path: Path
    ) -> None:
        """Pinned SHA-256 hex regression-guards the conditional iteration key.

        If a future change adds ``"iteration"`` unconditionally to the
        payload (instead of only when ``> 0``), every pre-existing
        on-disk create checkpoint would invalidate. The literal below is
        what ``_initial_steps_input_hash("demo", "build a thing",
        repo_root/"plans", repo_root)`` returned before step 2 landed.
        """
        repo_root = tmp_path
        out_dir = repo_root / "plans"
        expected = (
            "d438aee95c053fcee665518ddc7cb728518ed2cccfe498cd64907ba719869dbc"
        )
        assert (
            _initial_steps_input_hash(
                "demo", "build a thing", out_dir, repo_root
            )
            == expected
        )
        assert (
            _initial_steps_input_hash(
                "demo", "build a thing", out_dir, repo_root, iteration=0
            )
            == expected
        )

    def test_iteration_checkpoint_files_are_discarded_on_success(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A successful iterated create leaves no per-iteration shards behind.

        Drives the loop for ``max_iterations=2`` (which writes
        ``-iter1`` and ``-iter2`` shards for both steps and references),
        then asserts the discard sweep cleared every
        ``create-initial-steps*.json`` / ``create-references*.json``.
        """
        from plan_tool import create as create_module

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        # Fresh apply-eligible finding every collect call so the loop runs
        # the full two iterations (writing -iter1 + -iter2 shards) before
        # the max_iterations cap stops it -- a finite list would be
        # exhausted by the per-iteration re-derive.
        fresh = {"n": 0}

        def fake_collect(*a, **kw):
            fresh["n"] += 1
            return [_rec(f"A{fresh['n']}")]

        monkeypatch.setattr(
            create_module, "collect_deterministic_findings", fake_collect
        )
        monkeypatch.setattr(
            create_module, "apply_finding", lambda *a, **kw: _stub_apply_result()
        )

        counter = {"n": 0}
        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="build a thing",
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=_iter_invoker(counter),
            budget=_IterativeBudget(enabled=True, max_iterations=2),
        )
        assert result.plan_path.exists()

        ckpt_dir = tmp_path / ".plan-tool" / "checkpoints" / "demo"
        if ckpt_dir.exists():
            assert list(ckpt_dir.glob("*.json")) == []

    def test_iteration_loop_preserves_body_fills_and_step_statuses(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The iteration loop must NOT clobber the prose body or
        downgrade step statuses on re-write.

        Regression for the bug where ``write_new_plan`` was called
        inside the loop and rebuilt the body from ``seed_sections``
        (the original ``_(TODO)_`` placeholders), discarding every
        section that ``apply_finding`` had filled in earlier iterations.
        Companion regression for the related symptom where
        ``propose_steps_from_claude`` returned ``status: done`` on
        every step and the loop accepted those statuses wholesale,
        marking the entire plan complete without any code being
        written.

        Pin: after the iteration loop, (a) ``## Overview`` is no
        longer ``_(TODO)_``, and (b) on-disk step statuses survive
        the iteration unchanged (the initial create seeds step 1 to
        ``current`` so review has a "next thing to do" anchor; the
        loop must not advance that to ``done`` based on a claude
        proposal).
        """
        from plan_tool import create as create_module

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        # Findings list a plan-level placeholder so apply_finding has
        # something legitimate to "fix" (the stub edits ## Overview).
        monkeypatch.setattr(
            create_module,
            "collect_deterministic_findings",
            lambda *a, **kw: [_rec("placeholder-overview")],
        )

        def fake_apply_finding(plan_path, **kwargs):
            # Simulate ``apply_finding`` filling in the ## Overview body.
            text = plan_path.read_text(encoding="utf-8")
            text = text.replace(
                "## Overview\n\n_(TODO)_",
                "## Overview\n\nReal content filled by apply_finding.",
                1,
            )
            plan_path.write_text(text, encoding="utf-8")
            return _stub_apply_result()

        monkeypatch.setattr(create_module, "apply_finding", fake_apply_finding)

        # Mock propose_steps_from_claude to:
        # - return PENDING statuses on the initial create call (so the
        #   on-disk plan starts in a known-pending state)
        # - return DONE statuses on every subsequent (iteration) call
        # The fix under test must preserve the on-disk pending statuses
        # despite the proposal claiming done.
        from plan_tool.schema import Step, StepStatus

        propose_calls = {"n": 0}

        def fake_propose_steps(*a, **kw):
            propose_calls["n"] += 1
            status = (
                StepStatus.PENDING if propose_calls["n"] == 1 else StepStatus.DONE
            )
            return [
                Step(id=1, title="Step one", status=status),
                Step(id=2, title="Step two", status=status),
            ]

        monkeypatch.setattr(
            create_module, "propose_steps_from_claude", fake_propose_steps
        )
        monkeypatch.setattr(
            create_module,
            "propose_references_from_claude",
            lambda *a, **kw: ReferenceResearchResult.from_references([]),
        )

        counter = {"n": 0}
        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="build a thing",
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=_iter_invoker(counter),
            budget=_IterativeBudget(enabled=True, max_iterations=2),
        )

        final_text = result.plan_path.read_text(encoding="utf-8")
        # Body fill survived: ## Overview is not back to _(TODO)_.
        assert "Real content filled by apply_finding." in final_text
        assert (
            "## Overview\n\n_(TODO)_" not in final_text
        ), "iteration loop clobbered apply_finding's body fill"

        # Step statuses were preserved despite claude proposing
        # them as done. The initial create seeds the first runnable
        # step to ``current``; the rest stay ``pending``. The
        # iteration loop must preserve both — advancing a step to
        # ``done`` is ``plan-tool run``'s job, not create's.
        final_plan = create_module.parse_plan(result.plan_path)
        statuses = {s.id: s.status for s in final_plan.steps}
        assert statuses[1] == StepStatus.CURRENT, (
            f"step 1 status was {statuses[1]}, expected current "
            "(initial create seeds the first runnable step to current; "
            "the iteration loop must preserve that)"
        )
        assert statuses[2] == StepStatus.PENDING, (
            f"step 2 status was {statuses[2]}, expected pending "
            "(create iteration loop must not advance status; "
            "that's plan-tool run's job)"
        )

    def test_iteration_preserves_in_flight_or_done_steps_dropped_from_proposal(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When the iteration's step proposal omits a step that's on disk
        with status ``current`` or ``done``, the merged plan KEEPS that
        step intact and logs a warning. Pending/blocked steps the
        proposal drops are allowed through.

        Protects against silent loss of ``plan-tool run`` execution work
        if the iteration loop happens to overlap with a run that just
        advanced a step.
        """
        from plan_tool import create as create_module
        from plan_tool.schema import Step, StepStatus

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        monkeypatch.setattr(
            create_module,
            "collect_deterministic_findings",
            lambda *a, **kw: [_rec("X")],
        )

        # apply_finding side-effect: after the initial create lands the
        # plan with two pending steps, sneak a status promotion onto
        # step 1 (simulates a concurrent ``plan-tool run`` advancing it
        # to ``done``). Uses parse_plan + write_plan so it's robust to
        # yaml indentation choices that text.replace would be fragile to.
        def fake_apply_finding(plan_path, **kwargs):
            plan = create_module.parse_plan(plan_path)
            updated_steps = [
                s.model_copy(update={"status": StepStatus.DONE})
                if s.id == 1
                else s
                for s in plan.steps
            ]
            plan = plan.model_copy(update={"steps": updated_steps})
            create_module.write_plan(plan_path, plan)
            return _stub_apply_result()

        monkeypatch.setattr(
            create_module, "apply_finding", fake_apply_finding
        )

        # propose_steps_from_claude: initial pass returns ids 1+2 pending;
        # iteration pass DROPS step 1 (which has since been bumped to done)
        # and proposes a new step 2 (replacing the pending one) -- the
        # guard should keep step 1.
        propose_calls = {"n": 0}

        def fake_propose_steps(*a, **kw):
            propose_calls["n"] += 1
            if propose_calls["n"] == 1:
                return [
                    Step(id=1, title="Step one", status=StepStatus.PENDING),
                    Step(id=2, title="Step two", status=StepStatus.PENDING),
                ]
            return [
                Step(id=2, title="Step two revised", status=StepStatus.DONE),
            ]

        monkeypatch.setattr(
            create_module, "propose_steps_from_claude", fake_propose_steps
        )
        monkeypatch.setattr(
            create_module, "propose_references_from_claude",
            lambda *a, **kw: ReferenceResearchResult.from_references([]),
        )

        counter = {"n": 0}
        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="build a thing",
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=_iter_invoker(counter),
            budget=_IterativeBudget(enabled=True, max_iterations=1),
            skip_prose_reproposal=False,
        )

        final_plan = create_module.parse_plan(result.plan_path)
        ids = sorted(s.id for s in final_plan.steps)
        statuses = {s.id: s.status for s in final_plan.steps}

        # Step 1 (status=done on disk) was DROPPED from the proposal
        # but the guard preserved it.
        assert 1 in ids, "guard must keep done step dropped from proposal"
        assert statuses[1] == StepStatus.DONE, (
            "preserved step keeps its on-disk status"
        )

        # Step 2 came through the proposal and its proposed status
        # (DONE) was overridden back to the on-disk status (PENDING).
        assert 2 in ids
        assert statuses[2] == StepStatus.PENDING, (
            "iteration loop never lets a proposal-supplied status "
            "advance a step past its on-disk state"
        )

        # Warning was emitted to stderr.
        captured = capsys.readouterr()
        assert "proposal dropped step 1" in captured.err, captured.err
        assert "execution work cannot be silently discarded" in captured.err

    def test_iteration_checkpoint_files_survive_failed_write(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Forcing ``write_plan`` to raise on the iter-1 re-write keeps both shards.

        Round-0 checkpoints (created during the initial proposal calls)
        and the iter-1 shards must both remain on disk: the discard
        sweep only runs on the success path, mirroring the existing
        resume contract for the non-iterating create.

        Note: the iteration loop body uses ``write_plan`` (NOT
        ``write_new_plan``) when re-writing the plan between rounds --
        ``write_plan`` preserves the body, while ``write_new_plan``
        would clobber ``apply_finding``'s body fills with the original
        seed_sections (see bug fix in create.py iteration-loop step).
        This test pins the post-fix call site.
        """
        from plan_tool import create as create_module

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        monkeypatch.setattr(
            create_module,
            "collect_deterministic_findings",
            lambda *a, **kw: [_rec("A")],
        )
        monkeypatch.setattr(
            create_module, "apply_finding", lambda *a, **kw: _stub_apply_result()
        )

        # ``write_plan`` is called once during the initial ``write_new_plan``
        # (from inside it) and again on every iteration-loop re-write.
        # Fail only on the iter-1 call so the initial plan lands and the
        # iter-1 checkpoint files have a chance to be written before the
        # failure.
        original_write_plan = create_module.write_plan
        write_calls = {"n": 0}

        def fake_write_plan(*args, **kwargs):
            write_calls["n"] += 1
            if write_calls["n"] >= 2:
                raise OSError("simulated write failure on iteration re-write")
            return original_write_plan(*args, **kwargs)

        monkeypatch.setattr(create_module, "write_plan", fake_write_plan)

        counter = {"n": 0}
        with pytest.raises(
            CreateError, match="registered but finalization is incomplete"
        ):
            create_plan(
                "demo",
                repo_root=tmp_path,
                output_dir_override=out_dir,
                manifest_path=manifest,
                from_description="build a thing",
                input_fn=_queue_input(_basic_metadata_answers()),
                claude_invoker=_iter_invoker(counter),
                budget=_IterativeBudget(enabled=True, max_iterations=3),
                skip_prose_reproposal=False,
            )

        ckpt_dir = tmp_path / ".plan-tool" / "checkpoints" / "demo"
        steps_round_0 = ckpt_dir / f"{_INITIAL_STEPS_CHECKPOINT_NAME}.json"
        refs_round_0 = ckpt_dir / f"{_REFERENCES_CHECKPOINT_NAME}.json"
        steps_iter_1 = ckpt_dir / f"{_INITIAL_STEPS_CHECKPOINT_NAME}-iter1.json"
        refs_iter_1 = ckpt_dir / f"{_REFERENCES_CHECKPOINT_NAME}-iter1.json"
        assert steps_round_0.exists()
        assert refs_round_0.exists()
        assert steps_iter_1.exists()
        assert refs_iter_1.exists()


# --- Step 6: cross-cutting iteration-surface invariants for cmd_create ----


@pytest.mark.integration
class TestCrossCuttingIterationCreate:
    """Cross-cutting invariants over the create iteration loop.

    The internals (loop body, marginal-stop predicate, budget) are
    covered by ``TestCreatePlanIterationLoop`` above (step 2). These
    tests pin the *contract* the user sees across subcommands: an
    interrupted iter-N preserves iter-0 checkpoints so the re-run
    cache-hits round 0 (saving the two pre-loop claude calls), the
    marginal-stop predicate halts cleanly before the next round
    fires, the iteration-keyed input hash genuinely partitions the
    cache so iter-1's payload can't be replayed as iter-0's, and
    budget exhaustion is a clean exit (current contract: discard
    checkpoints just like a converged run).
    """

    def test_iteration_n_checkpoint_resumed_after_interrupt(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An iter-1 crash mid-loop leaves iter-0 checkpoints intact;
        the re-run hits the iter-0 cache (zero pre-loop invocations).

        Cross-cutting bit: pins that even though the post-write loop
        constructs each iter-N propose call with ``resume=False``, the
        original top-of-``create_plan`` propose calls (which DO honour
        ``resume=True``) still find the round-0 checkpoints on disk.
        """
        from plan_tool import create as create_module

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        monkeypatch.setattr(
            create_module,
            "collect_deterministic_findings",
            lambda *a, **kw: [_rec("A")],
        )
        monkeypatch.setattr(
            create_module, "apply_finding", lambda *a, **kw: _stub_apply_result()
        )

        # Fail the iter-1 ``write_plan`` so the discard-on-success
        # sweep at the tail of ``create_plan`` never runs.
        # Note: the loop body uses ``write_plan`` (not ``write_new_plan``)
        # post-bug-fix. ``write_plan`` is also called once inside
        # ``write_new_plan`` during initial create -- fail only on call
        # >= 2 so the initial plan lands first.
        original_write = create_module.write_plan
        write_calls = {"n": 0}

        def fail_on_iter_write(*args, **kwargs):
            write_calls["n"] += 1
            if write_calls["n"] >= 2:
                raise OSError("interrupted mid-iter-1 write")
            return original_write(*args, **kwargs)

        monkeypatch.setattr(create_module, "write_plan", fail_on_iter_write)

        first_counter = {"n": 0}
        with pytest.raises(
            CreateError, match="registered but finalization is incomplete"
        ):
            create_plan(
                "demo",
                repo_root=tmp_path,
                output_dir_override=out_dir,
                manifest_path=manifest,
                from_description="build a thing",
                input_fn=_queue_input(_basic_metadata_answers()),
                claude_invoker=_iter_invoker(first_counter),
                budget=_IterativeBudget(enabled=True, max_iterations=3),
                skip_prose_reproposal=False,
            )

        # First run: 2 initial invocations + 2 iter-1 re-author invocations
        # before the simulated write failure.
        assert first_counter["n"] == 5

        ckpt_dir = tmp_path / ".plan-tool" / "checkpoints" / "demo"
        steps_round_0 = ckpt_dir / f"{_INITIAL_STEPS_CHECKPOINT_NAME}.json"
        refs_round_0 = ckpt_dir / f"{_REFERENCES_CHECKPOINT_NAME}.json"
        assert steps_round_0.exists()
        assert refs_round_0.exists()
        # Iter-0 checkpoints keyed on the iteration=0 (legacy) hash.
        steps_body = json.loads(steps_round_0.read_text(encoding="utf-8"))
        refs_body = json.loads(refs_round_0.read_text(encoding="utf-8"))
        assert steps_body["input_hash"] == _initial_steps_input_hash(
            "demo", "build a thing", out_dir, tmp_path, iteration=0
        )
        assert refs_body["input_hash"] == _references_input_hash(
            "demo", "Demo Plan", "build a thing", out_dir, tmp_path, iteration=0
        )

        # Re-run with the failure removed. The two pre-loop propose calls
        # honour resume=True and must cache-hit the iter-0 checkpoints
        # left by the interrupted run — so the only claude work in the
        # second run is the iter-1 loop body (which always uses
        # resume=False).
        monkeypatch.setattr(create_module, "write_plan", original_write)

        second_counter = {"n": 0}
        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="build a thing",
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=_iter_invoker(second_counter),
            budget=_IterativeBudget(enabled=True, max_iterations=1),
            skip_prose_reproposal=False,
            replace_on_collision=True,
        )
        assert result.plan_path.exists()
        # iter-0's two propose calls were served from cache. Only the
        # iter-1 loop's two re-author calls invoked claude.
        assert second_counter["n"] == 2

    def test_budget_exhaustion_completes_cleanly_with_max_iterations_reason(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Cap=1 with always-fresh findings exits ``max_iterations``.

        The cross-cutting claim: budget exhaustion is a *normal* exit —
        the discard sweep at the tail of ``create_plan`` still runs, so
        no stale checkpoint shards leak into the next run. (This is the
        current contract; step 6's plan description sketched a
        "checkpoints persist on exhaustion" variant which does not
        match the implementation's discard-on-every-exit semantics.)
        """
        from plan_tool import create as create_module

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        seq = iter([
            [_rec("A0")],
            [_rec("A1")],
            [_rec("A2")],
        ])

        def fake_collect(*args, **kwargs):
            return next(seq)

        monkeypatch.setattr(
            create_module, "collect_deterministic_findings", fake_collect
        )
        monkeypatch.setattr(
            create_module, "apply_finding", lambda *a, **kw: _stub_apply_result()
        )

        counter = {"n": 0}
        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="build a thing",
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=_iter_invoker(counter),
            budget=_IterativeBudget(enabled=True, max_iterations=1),
            skip_prose_reproposal=False,
        )
        assert result.plan_path.exists()
        # 2 initial + 2 iter-1 re-author = 4 total.
        assert counter["n"] == 5
        err = capsys.readouterr().err
        assert "iteration loop stopped: max_iterations" in err

        # Exhaustion is a clean exit: discard sweep runs.
        ckpt_dir = tmp_path / ".plan-tool" / "checkpoints" / "demo"
        if ckpt_dir.exists():
            assert list(ckpt_dir.glob("*.json")) == []

    def test_marginal_stop_when_iter_n_subset_of_iter_prior(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Same finding-set on iter-1 and iter-2 → marginal short-circuit.

        Cross-cutting bit: the *invocation count* is bounded by the
        marginal stop. With ``max_iterations=5`` the loop would happily
        run all five rounds, but the marginal predicate must halt after
        iter-1 — so the iter-2 re-author calls never fire.
        """
        from plan_tool import create as create_module

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        # Identical findings every collect → 100% overlap → marginal.
        monkeypatch.setattr(
            create_module,
            "collect_deterministic_findings",
            lambda *a, **kw: [_rec("A"), _rec("B")],
        )
        monkeypatch.setattr(
            create_module, "apply_finding", lambda *a, **kw: _stub_apply_result()
        )

        counter = {"n": 0}
        create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="build a thing",
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=_iter_invoker(counter),
            budget=_IterativeBudget(enabled=True, max_iterations=5),
            skip_prose_reproposal=False,
        )
        # 2 initial + 2 iter-1 re-author = 4. Iter-2 doesn't fire.
        assert counter["n"] == 5
        err = capsys.readouterr().err
        assert "iteration loop stopped: marginal" in err

    def test_iteration_index_invalidates_iter0_only_cache(
        self, tmp_path: Path
    ) -> None:
        """Iter-0 and iter-1 hashes partition the cache by round.

        Positive arm: seed iter-0 and iter-1 checkpoints under their
        respective shard filenames + hash keys, then call
        ``propose_steps_from_claude`` with ``iteration=0`` and
        ``iteration=1`` (both ``resume=True``) — both hit cache, no
        invocations. Negative arm: a hand-rolled iter-1 checkpoint
        seeded under the iter-0 hash key fails to load when
        ``iteration=1`` keying is supplied (the hash mismatch is the
        regression pin against a future refactor that drops the
        ``iteration`` kwarg from ``_initial_steps_input_hash``).
        """
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()

        iter0_hash = _initial_steps_input_hash(
            "demo", "build a thing", out_dir, tmp_path, iteration=0
        )
        iter1_hash = _initial_steps_input_hash(
            "demo", "build a thing", out_dir, tmp_path, iteration=1
        )
        assert iter0_hash != iter1_hash

        iter0_ckpt = checkpoint_path(
            tmp_path, "demo", _INITIAL_STEPS_CHECKPOINT_NAME
        )
        iter1_ckpt = checkpoint_path(
            tmp_path, "demo", f"{_INITIAL_STEPS_CHECKPOINT_NAME}-iter1"
        )
        save_checkpoint(
            iter0_ckpt,
            Checkpoint(
                input_hash=iter0_hash,
                payload=_STEP_JSON,
                created_at=_now_iso(),
            ),
        )
        save_checkpoint(
            iter1_ckpt,
            Checkpoint(
                input_hash=iter1_hash,
                payload=_STEP_JSON,
                created_at=_now_iso(),
            ),
        )

        def explode(prompt: str) -> str:
            raise AssertionError("invoker must not run on cache hit")

        steps_round_0 = propose_steps_from_claude(
            "build a thing",
            explode,
            reporter=_RecordingReporter(),
            repo_root=tmp_path,
            slug="demo",
            output_dir=out_dir,
            iteration=0,
        )
        steps_round_1 = propose_steps_from_claude(
            "build a thing",
            explode,
            reporter=_RecordingReporter(),
            repo_root=tmp_path,
            slug="demo",
            output_dir=out_dir,
            iteration=1,
        )
        assert steps_round_0 is not None
        assert steps_round_1 is not None

        # Negative arm: mis-key iter-1's checkpoint with iter-0's hash.
        # A correctly-keyed propose with ``iteration=1`` must reject the
        # cached body (hash mismatch) and invoke claude. If a future
        # refactor drops the ``iteration`` keyword from the hash, this
        # mis-keyed checkpoint would be served as a false cache hit and
        # the invoker call count would stay at 0.
        iter1_ckpt.unlink()
        save_checkpoint(
            iter1_ckpt,
            Checkpoint(
                input_hash=iter0_hash,  # deliberately wrong for iter=1
                payload=_STEP_JSON,
                created_at=_now_iso(),
            ),
        )
        miss_counter = {"n": 0}

        def counting_invoker(prompt: str) -> str:
            miss_counter["n"] += 1
            return _STEP_JSON

        propose_steps_from_claude(
            "build a thing",
            counting_invoker,
            reporter=_RecordingReporter(),
            repo_root=tmp_path,
            slug="demo",
            output_dir=out_dir,
            iteration=1,
        )
        assert miss_counter["n"] == 1


# --- Mid-iteration drift halt (task #33) ----------------------------------

@pytest.mark.integration
class TestCreatePlanDriftHalt:
    """Pre/post-apply drift check in ``create_plan``'s iteration loop.

    Mirrors the cmd_completeness pattern (task #30). When a watched
    (step.files) file's mtime advances during the iteration, the loop
    halts: before tokens are spent if drift fires pre-apply, or after
    the current apply's edits are kept if drift fires post-apply.
    ``allow_drift=True`` opts back into the legacy warn-but-proceed.
    """

    def test_iterate_loop_reverts_parse_broken_apply(self) -> None:
        """Call-site contract: parse-breaking apply edits are reverted.

        The helper itself is covered in launcher/completeness tests; this
        guards the create iterate loop against regressing back to leaving an
        unparseable plan on disk.
        """
        from plan_tool.create import _converge_create_plan

        src = inspect.getsource(_converge_create_plan)
        revert = "apply_reverted = revert_apply_if_parse_broken(apply_result)"
        assert revert in src
        assert src.index(revert) < src.index("run_logger.phase_end(", src.index(revert))
        assert '"reverted" if apply_reverted' in src
        assert "wedge the create" in src
        assert "parse_halted = True" in src

    def _setup(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Shared fixture: create a watched src/foo.py, stub propose
        to return a single step with step.files=[that file], stub
        references to empty, and return the watched path."""
        from plan_tool import create as create_module
        from plan_tool.schema import Step, StepStatus

        (tmp_path / ".git").mkdir()
        (tmp_path / "src").mkdir()
        watched = tmp_path / "src" / "foo.py"
        watched.write_text("original\n", encoding="utf-8")
        out_dir = tmp_path / "plans"
        out_dir.mkdir()

        monkeypatch.setattr(
            create_module,
            "propose_steps_from_claude",
            lambda *a, **kw: [
                Step(
                    id=1,
                    title="Step one",
                    files=["src/foo.py"],
                    status=StepStatus.PENDING,
                )
            ],
        )
        monkeypatch.setattr(
            create_module,
            "propose_references_from_claude",
            lambda *a, **kw: ReferenceResearchResult.from_references([]),
        )
        return create_module, watched, out_dir

    def test_post_apply_drift_halts_loop_and_keeps_edits(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """First apply advances the watched mtime; loop halts after
        the apply with ``DURING apply`` phase wording. The mock counts
        exactly one apply call -- the loop never reaches the second
        finding's apply."""
        import os

        create_module, watched, out_dir = self._setup(tmp_path, monkeypatch)

        apply_calls = {"n": 0}

        def fake_apply(*a, **kw):
            apply_calls["n"] += 1
            # Mutate watched-file CONTENT so check_drift fires
            # DURING (#31 uses content hashing -- mtime advance
            # alone no longer counts as drift).
            watched.write_bytes(
                watched.read_bytes() + b"_drift"
            )
            return _stub_apply_result()

        monkeypatch.setattr(create_module, "apply_finding", fake_apply)
        monkeypatch.setattr(
            create_module,
            "collect_deterministic_findings",
            lambda *a, **kw: [_rec("A"), _rec("B")],
        )

        counter = {"n": 0}
        create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=tmp_path / "m.json",
            from_description="build a thing",
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=_iter_invoker(counter),
            budget=_IterativeBudget(enabled=True, max_iterations=3),
            # Auto-reconcile would fire run_step → real claude shell-out
            # in tests that don't mock it. Opt out to keep this test
            # focused on the drift-halt path itself.
            auto_reconcile_on_drift=False,
        )

        assert apply_calls["n"] == 1
        err = capsys.readouterr().err
        assert "drift detected" in err
        assert "DURING apply" in err
        # the drifted file's owning step is named
        # inline. Proves create_plan's drift-halt call site passes
        # `file_to_step` through. Without the plumbing this would
        # render as a bare `- src/foo.py`.
        assert "(step 1: Step one)" in err

    def test_pre_apply_drift_halts_loop_before_tokens(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Drift introduced between iterations halts iter 2's pre-apply
        check with ``BEFORE applying`` wording. Iter 1's apply ran
        (no drift then); iter 2's apply did NOT run."""
        import os

        create_module, watched, out_dir = self._setup(tmp_path, monkeypatch)

        collect_calls = {"n": 0}

        def collect_seq(*a, **kw):
            collect_calls["n"] += 1
            # These findings are apply-eligible (not deferred), so the
            # post-apply short-circuit never fires -- the collect sequence
            # is just pre-loop + one end-of-loop re-derive per iteration.
            #   call 1 (pre-loop): one finding for iter 1.
            #   call 2 (end of iter 1): new finding for iter 2 + mutate
            #     watched-file content so iter 2's pre-apply check
            #     fires (#31: content hash, not mtime).
            if collect_calls["n"] == 1:
                return [_rec("A")]
            if collect_calls["n"] == 2:
                watched.write_bytes(
                    watched.read_bytes() + b"_drift"
                )
                return [_rec("B")]
            return []

        monkeypatch.setattr(
            create_module,
            "collect_deterministic_findings",
            collect_seq,
        )

        apply_calls = {"n": 0}

        def fake_apply(*a, **kw):
            apply_calls["n"] += 1
            return _stub_apply_result()

        monkeypatch.setattr(create_module, "apply_finding", fake_apply)

        counter = {"n": 0}
        create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=tmp_path / "m.json",
            from_description="build a thing",
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=_iter_invoker(counter),
            budget=_IterativeBudget(enabled=True, max_iterations=3),
            auto_reconcile_on_drift=False,
        )

        # Iter 1 ran 1 apply (no drift then); iter 2 halted before its apply.
        assert apply_calls["n"] == 1
        err = capsys.readouterr().err
        assert "drift detected" in err
        assert "BEFORE applying" in err

    def test_allow_drift_disables_halt(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """``allow_drift=True`` opts back into the legacy warn-but-proceed
        path: the apply still touches the watched mtime but the loop
        does NOT emit the halt warning and apply runs on both findings."""
        import os

        create_module, watched, out_dir = self._setup(tmp_path, monkeypatch)

        apply_calls = {"n": 0}

        def fake_apply(*a, **kw):
            apply_calls["n"] += 1
            # Mutate content -- legacy mtime-advance no longer
            # constitutes drift.
            watched.write_bytes(
                watched.read_bytes() + b"_drift"
            )
            return _stub_apply_result()

        monkeypatch.setattr(create_module, "apply_finding", fake_apply)
        # First collect returns 2 findings, subsequent returns 0 so
        # the loop converges quickly.
        collect_calls = {"n": 0}

        def collect_seq(*a, **kw):
            collect_calls["n"] += 1
            return [_rec("A"), _rec("B")] if collect_calls["n"] == 1 else []

        monkeypatch.setattr(
            create_module,
            "collect_deterministic_findings",
            collect_seq,
        )

        counter = {"n": 0}
        create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=tmp_path / "m.json",
            from_description="build a thing",
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=_iter_invoker(counter),
            budget=_IterativeBudget(enabled=True, max_iterations=3),
            allow_drift=True,
        )

        # Both findings' applies run -- no halt.
        assert apply_calls["n"] == 2
        err = capsys.readouterr().err
        assert "drift detected" not in err
        assert "DURING apply" not in err
        # The legacy lock-release drift warning still fires.
        assert "changed during" in err


# --- #26: Surgical body patch for iteration-loop References update ---


class TestReferencesBodyPatch:
    """Unit tests for the helpers backing the iteration-loop References patch.

    These cover the primitives in isolation; the full iteration-loop
    integration is exercised by ``TestCreatePlanReferencesIteration``
    below.
    """

    def test_render_references_body_formats_bullets(self) -> None:
        from plan_tool.create import _render_references_body

        out = _render_references_body([
            Reference(title="Anthropic API", url="https://x/a", description="docs"),
            Reference(title="Bare", url="https://x/b"),
        ])
        assert out == (
            "- [Anthropic API](https://x/a) — docs\n"
            "- [Bare](https://x/b)"
        )

    def test_render_references_body_empty_returns_empty(self) -> None:
        from plan_tool.create import _render_references_body

        assert _render_references_body([]) == ""

    def test_patch_plan_body_section_replaces_target_only(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.create import _patch_plan_body_section

        plan_path = tmp_path / "p.md"
        plan_path.write_text(
            "---\n"
            "title: Demo\n"
            "---\n"
            "# Demo\n"
            "\n"
            "## Overview\n"
            "\n"
            "overview body\n"
            "\n"
            "## References\n"
            "\n"
            "_(TODO)_\n"
            "\n"
            "## Steps\n"
            "\n"
            "See the `steps:` block in the frontmatter.\n",
            encoding="utf-8",
        )

        patched = _patch_plan_body_section(
            plan_path,
            "References",
            "- [Docs](https://x) — gloss",
        )
        assert patched is True

        text = plan_path.read_text(encoding="utf-8")
        # New references content landed under the heading
        assert "## References\n\n- [Docs](https://x) — gloss\n\n" in text
        # Neighboring sections untouched
        assert "## Overview\n\noverview body" in text
        assert "## Steps\n\nSee the `steps:` block" in text
        # Frontmatter byte-preserved
        assert text.startswith("---\ntitle: Demo\n---\n")

    def test_patch_plan_body_section_case_insensitive_match(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.create import _patch_plan_body_section

        plan_path = tmp_path / "p.md"
        plan_path.write_text(
            "---\nx: 1\n---\n## references\n\nold\n\n## Steps\n\ns\n",
            encoding="utf-8",
        )
        assert _patch_plan_body_section(plan_path, "References", "new") is True
        assert "## references\n\nnew\n\n## Steps" in plan_path.read_text(
            encoding="utf-8"
        )

    def test_patch_plan_body_section_ignores_closed_fenced_pseudo_heading(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.create import _patch_plan_body_section

        plan_path = tmp_path / "p.md"
        plan_path.write_text(
            "---\nx: 1\n---\n```markdown\n## References\n\nexample only\n```\n"
            "\n## References\n\nold\n\n## Steps\n\nbody\n",
            encoding="utf-8",
        )

        assert _patch_plan_body_section(plan_path, "References", "new") is True
        text = plan_path.read_text(encoding="utf-8")
        assert "```markdown\n## References\n\nexample only\n```" in text
        assert "## References\n\nnew\n\n## Steps" in text

    def test_patch_plan_body_section_missing_section_is_noop(
        self, tmp_path: Path
    ) -> None:
        """No matching H2 → returns ``False`` and file is unchanged."""
        from plan_tool.create import _patch_plan_body_section

        plan_path = tmp_path / "p.md"
        original = (
            "---\nx: 1\n---\n## Overview\n\nbody\n\n## Steps\n\ns\n"
        )
        plan_path.write_text(original, encoding="utf-8")
        assert _patch_plan_body_section(plan_path, "References", "new") is False
        assert plan_path.read_text(encoding="utf-8") == original

    def test_patch_plan_body_section_rejects_unmatched_fence_without_writing(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.create import CreateError, _patch_plan_body_section

        plan_path = tmp_path / "p.md"
        original = "---\nx: 1\n---\n## References\n\nold\n\n```\n"
        plan_path.write_text(original, encoding="utf-8")

        with pytest.raises(CreateError, match="unmatched opening code fence"):
            _patch_plan_body_section(plan_path, "References", "new")

        assert plan_path.read_text(encoding="utf-8") == original


@pytest.mark.integration
class TestCreatePlanReferencesIteration:
    """The iteration loop refreshes ``## References`` on each round.

    Regression for #26: the create-iterate loop swapped ``write_new_plan``
    for ``write_plan`` (#24) to stop clobbering body sections that
    ``apply_finding`` had filled in. That swap removed the only place
    where ``refs_proposal`` was rendered into the body. This test pins
    the surgical patch that restores it.
    """

    def test_iteration_loop_updates_references_section(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool import create as create_module

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        # Round 0 References research returns ROUND-0 URL; round 1 (the
        # iteration's re-author) returns ROUND-1 URL. After the loop,
        # the on-disk plan must show the round-1 URL.
        round0_ref = json.dumps([{
            "title": "Round0 Doc",
            "url": "https://example.com/round0",
            "description": "first",
        }])
        round1_ref = json.dumps([{
            "title": "Round1 Doc",
            "url": "https://example.com/round1",
            "description": "second",
        }])

        ref_calls = {"n": 0}

        def invoker(prompt: str) -> str:
            if "developer and API reference documentation" in prompt:
                ref_calls["n"] += 1
                return round0_ref if ref_calls["n"] == 1 else round1_ref
            return _STEP_JSON

        collect_calls = {"n": 0}

        def fake_collect(*args, **kwargs):
            collect_calls["n"] += 1
            # One apply-eligible (non-deferred) finding for round 1, then
            # converge: the iteration re-proposes once (refreshing
            # references), then the next should_continue converges.
            return [_rec("A")] if collect_calls["n"] == 1 else []

        monkeypatch.setattr(
            create_module, "collect_deterministic_findings", fake_collect
        )
        monkeypatch.setattr(
            create_module, "apply_finding", lambda *a, **kw: _stub_apply_result()
        )

        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="build a thing",
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=invoker,
            budget=_IterativeBudget(enabled=True, max_iterations=3),
            skip_prose_reproposal=False,
        )

        # Loop ran exactly one iteration: 2 references calls total
        # (round-0 initial + round-1 re-author).
        assert ref_calls["n"] == 2

        body = result.plan_path.read_text(encoding="utf-8")
        # Iteration-1 references landed
        assert "https://example.com/round1" in body
        assert "Round1 Doc" in body
        # Initial round-0 references were replaced (not left behind)
        assert "https://example.com/round0" not in body
        assert "Round0 Doc" not in body
        # Section header still present, single occurrence
        assert body.count("## References") == 1

    def test_iteration_rejects_unmatched_plan_after_apply_before_reproposal(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool import create as create_module

        (tmp_path / ".git").mkdir()
        counter = {"n": 0}
        monkeypatch.setattr(
            create_module,
            "collect_deterministic_findings",
            lambda *_a, **_k: [_rec("A")],
        )

        def write_unsafe_plan(plan_path: Path, *_a, **_k):
            plan_path.write_text(
                plan_path.read_text(encoding="utf-8") + "\n```\n",
                encoding="utf-8",
            )
            return _stub_apply_result()

        monkeypatch.setattr(create_module, "apply_finding", write_unsafe_plan)

        with pytest.raises(CreateError, match="unmatched opening code fence"):
            create_plan(
                "demo",
                repo_root=tmp_path,
                output_dir_override=tmp_path / "plans",
                manifest_path=tmp_path / "m.json",
                from_description="build a thing",
                input_fn=_queue_input(_basic_metadata_answers()),
                claude_invoker=_iter_invoker(counter),
                budget=_IterativeBudget(enabled=True, max_iterations=3),
                skip_prose_reproposal=False,
            )

        # Initial steps, references, and body synthesis run; the loop does not
        # invoke the next model stage or overwrite the unsafe body.
        assert counter["n"] == 3

    def test_iteration_loop_preserves_references_when_refs_empty(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Empty round-1 refs proposal must NOT clobber the existing body.

        Pins the populated-result guard at the patch call site: a valid-empty
        result means "no good references found," so the existing References
        block (which may have been hand-edited or filled by ``apply_finding``)
        must survive the iteration.
        """
        from plan_tool import create as create_module
        from plan_tool.run_log import RunLogWriter

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"
        run_logger = RunLogWriter.start(
            repo_root=tmp_path,
            slug="demo",
            command="create",
            argv=["plan-tool", "create", "demo"],
        )

        round0_ref = json.dumps([{
            "title": "Round0 Doc",
            "url": "https://example.com/round0",
            "description": "first",
        }])
        # Round 1: claude reports "no good references found."
        empty_ref = "[]"

        ref_calls = {"n": 0}
        step_calls = {"n": 0}

        def invoker(prompt: str) -> str:
            if "developer and API reference documentation" in prompt:
                ref_calls["n"] += 1
                return round0_ref if ref_calls["n"] == 1 else empty_ref
            if "Synthesize plan body sections" in prompt:
                return _SYNTHESIS_NULL_JSON
            step_calls["n"] += 1
            return _STEP_JSON

        collect_calls = {"n": 0}

        def fake_collect(*args, **kwargs):
            collect_calls["n"] += 1
            # One apply-eligible (non-deferred) finding for round 1, then
            # converge: the iteration re-proposes references once.
            return [_rec("A")] if collect_calls["n"] == 1 else []

        monkeypatch.setattr(
            create_module, "collect_deterministic_findings", fake_collect
        )
        monkeypatch.setattr(
            create_module, "apply_finding", lambda *a, **kw: _stub_apply_result()
        )

        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="build a thing",
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=invoker,
            budget=_IterativeBudget(enabled=True, max_iterations=3),
            skip_prose_reproposal=False,
            run_logger=run_logger,
        )

        assert ref_calls["n"] == 2
        assert step_calls["n"] == 2
        assert result.iteration_stage_failure is None
        body = result.plan_path.read_text(encoding="utf-8")
        # Round-0 references survive: empty round-1 proposal is treated
        # as "no opinion this round," not "clobber to _(TODO)_".
        assert "https://example.com/round0" in body
        assert "Round0 Doc" in body
        assert "_(TODO)_" not in body.split("## References", 1)[1].split(
            "## ", 1
        )[0]
        iteration_phase_ends = [
            event
            for event in _read_run_log(tmp_path, "demo")
            if event["event"] == "phase_end"
            and event.get("phase") == "propose_references"
            and event.get("iteration") == 1
        ]
        assert [event["outcome"] for event in iteration_phase_ends] == ["skipped"]

    def test_roadmap_iteration_preserves_accepted_references_without_reresearch(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool import create as create_module
        from plan_tool.roadmap_artifacts import HostingRow, ResearchDisclosure

        location = _write_roadmap_research_source(
            tmp_path,
            hosting=(HostingRow(
                "host", "compute", "managed", "Description-backed host", "x",
                ResearchDisclosure.EXTERNAL,
            ),),
        )
        reference_calls = 0

        def invoker(prompt: str) -> str:
            nonlocal reference_calls
            if "Requested products:" in prompt:
                reference_calls += 1
                return json.dumps([{"token": "hosting-1", "references": []}])
            return _STEP_JSON

        collect_calls = 0

        def fake_collect(*args, **kwargs):
            nonlocal collect_calls
            collect_calls += 1
            return [_rec("A")] if collect_calls == 1 else []

        monkeypatch.setattr(
            create_module, "collect_deterministic_findings", fake_collect
        )
        monkeypatch.setattr(
            create_module, "apply_finding", lambda *a, **kw: _stub_apply_result()
        )

        result = create_plan(
            "selected-iterate",
            repo_root=tmp_path,
            output_dir_override=tmp_path / "output",
            from_description=_CANONICAL_BODY,
            tracked_seed_location=location,
            yes=True,
            offer_intents=False,
            synthesize_body=False,
            fetch_docs=False,
            allow_placeholder_body=True,
            claude_invoker=invoker,
            budget=_IterativeBudget(enabled=True, max_iterations=3),
            skip_prose_reproposal=False,
        )

        assert reference_calls == 1
        body = result.plan_path.read_text(encoding="utf-8")
        assert _ROADMAP_NO_SOURCE_REFERENCES_BODY in body


# --- Step 3: fail-loud refusal of plans with `_(TODO)_` body sections ---


FIXTURES_CREATE = Path(__file__).parent / "fixtures" / "create"


@pytest.mark.integration
class TestCreatePlanRejectsTodoBody:
    """Pre-write fail-loud check refuses to ship a plan whose body would
    render as ``_(TODO)_`` in any required H2 section.

    Refs bug-backlog entry "``create`` ships plans with ``_(TODO)_``
    body sections silently." The check fires when ``budget.enabled`` is
    False (the default, non-``--iterate`` path); when iteration is
    enabled the convergence loop's ``apply_finding`` calls own the
    TODO-fill path and the check is bypassed.
    """

    @pytest.fixture(autouse=True)
    def _stub_propose_references(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Keep the references-research claude call off the wire on the
        non-iteration tests in this class. Mirrors the autouse fixture in
        ``TestCreatePlanBlankSkeleton``. Iteration-mode tests still inject
        their own ``claude_invoker``; this stub only neutralizes the
        production default."""
        from plan_tool import create as create_module
        monkeypatch.setattr(
            create_module, "propose_references_from_claude",
            lambda *a, **kw: ReferenceResearchResult.from_references([]),
        )

    @pytest.fixture(autouse=True)
    def _disable_step3_todo_check(self) -> None:
        """Override the module-level disable: keep the new check live
        for these tests, which are designed to exercise it end-to-end."""

    def test_blank_skeleton_create_rejects_todo_body(
        self, tmp_path: Path
    ) -> None:
        """No seed + no claude refs → every non-Steps section renders as
        ``_(TODO)_`` and the wizard refuses before writing."""
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"
        answers = _basic_metadata_answers() + _single_step_answers()

        with pytest.raises(
            CreateError, match=r"_\(TODO\)_ placeholders in:"
        ) as exc:
            create_plan(
                "demo",
                repo_root=tmp_path,
                output_dir_override=out_dir,
                manifest_path=manifest,
                input_fn=_queue_input(answers),
            )

        msg = str(exc.value)
        for section in ("Overview", "Problem statement", "Architecture"):
            assert section in msg, f"missing {section!r} in: {msg}"
        # ``--iterate`` hint is part of the contract so users have a
        # discoverable path forward.
        assert "--iterate" in msg
        assert list(out_dir.iterdir()) == []
        assert not manifest.exists()

    def test_partial_body_fixture_rejects_remaining_todos(
        self, tmp_path: Path
    ) -> None:
        """The partial-body fixture lands ``## Overview``, ``## Steps``,
        and ``## Acceptance criteria``; the wizard must refuse the
        seven remaining placeholders.

        Pins the bug's general shape -- a partially-populated source
        description that previously shipped silently with seven
        ``_(TODO)_`` sections. Fixture content is generic; the bug
        fires for any source description with this partial-body
        shape, not for a specific real-world source.
        """
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        seed = (FIXTURES_CREATE / "partial-body-source.md").read_text(
            encoding="utf-8"
        )
        # Fixture's ``## Steps`` section doesn't match the strict canonical
        # shape (no ``Files:`` blocks, no closing newline discipline), so
        # the wizard falls back to claude for step extraction. A canned
        # JSON response keeps the test hermetic.
        canned_steps = json.dumps(
            [
                {
                    "title": "first",
                    "complexity": "low",
                    "files": [],
                    "depends_on": [],
                }
            ]
        )
        answers = _basic_metadata_answers()

        with pytest.raises(
            CreateError, match=r"_\(TODO\)_ placeholders in:"
        ) as exc:
            create_plan(
                "demo",
                repo_root=tmp_path,
                output_dir_override=out_dir,
                manifest_path=manifest,
                from_description=seed,
                seed_body=seed,
                input_fn=_queue_input(answers),
                claude_invoker=lambda prompt: canned_steps,
            )

        msg = str(exc.value)
        expected_missing = (
            "Problem statement",
            "Architecture",
            "References",
            "Out of scope",
            "Risks",
            "Testing",
            "Deferred",
        )
        for section in expected_missing:
            assert section in msg, f"missing {section!r} in: {msg}"
        # Sections the seed populates must NOT appear in the error.
        for populated in ("Overview", "Acceptance criteria"):
            assert populated not in msg, (
                f"unexpected {populated!r} in message; seed populated it"
            )
        assert list(out_dir.iterdir()) == []
        assert not manifest.exists()

    def test_allow_placeholder_body_bypasses_gate(
        self, tmp_path: Path
    ) -> None:
        """``allow_placeholder_body=True`` writes the plan despite
        ``_(TODO)_`` sections.

        The opt-out exists for proposal-consuming callers — the bench
        harness scores steps/change_types/dependency shape and never
        reads body sections; without it every ``synthesize_body=False``
        one-shot trial dies at the gate regardless of backend quality
        (found live: the first real ``bench run`` recorded
        ``unknown_nonzero`` for all single-plan proposal cells).
        """
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"
        answers = _basic_metadata_answers() + _single_step_answers()

        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            input_fn=_queue_input(answers),
            allow_placeholder_body=True,
        )

        assert result.plan_path.exists()
        body = result.plan_path.read_text(encoding="utf-8")
        # The blank-skeleton placeholders ship by design under the opt-out.
        assert "_(TODO)_" in body
        assert manifest.exists()

    def test_fully_populated_seed_succeeds(self, tmp_path: Path) -> None:
        """A seed whose every section has non-TODO prose passes the gate."""
        from plan_tool.create import PLAN_BODY_SECTIONS

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        seed_lines: list[str] = ["# T", ""]
        for section in PLAN_BODY_SECTIONS:
            seed_lines.append(f"## {section}")
            seed_lines.append("")
            seed_lines.append(f"populated body for {section.lower()}.")
            seed_lines.append("")
        full_seed = "\n".join(seed_lines)

        answers = _basic_metadata_answers() + _single_step_answers()

        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            seed_body=full_seed,
            input_fn=_queue_input(answers),
        )

        assert result.plan_path.exists()
        plan = parse_plan(result.plan_path)
        assert plan.title == "Demo Plan"
        body = result.plan_path.read_text(encoding="utf-8")
        # No placeholders survived the seed substitution.
        assert "_(TODO)_" not in body

    def test_create_plan_classified_steps_pass_testing_gate(
        self, tmp_path: Path
    ) -> None:
        """Classified steps fill Testing's placeholder with the per-step
        enumeration, so the fail-loud gate passes for Testing.

        Classifying steps clears only Testing's placeholder; the gate still
        flags every other unseeded section, so the create must seed the
        eight non-Testing, non-Steps sections with non-placeholder prose.
        """
        from plan_tool.create import PLAN_BODY_SECTIONS

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        # Seed every section EXCEPT Testing (the enumeration fills it) and
        # Steps (the frontmatter pointer fills it).
        seed_lines: list[str] = ["# T", ""]
        for section in PLAN_BODY_SECTIONS:
            if section in ("Testing", "Steps"):
                continue
            seed_lines.append(f"## {section}")
            seed_lines.append("")
            seed_lines.append(f"populated body for {section.lower()}.")
            seed_lines.append("")
        full_seed = "\n".join(seed_lines)

        classified_steps = json.dumps(
            [
                {
                    "title": "restructure",
                    "complexity": "low",
                    "change_type": "refactor",
                    "rationale": "behavior-preserving",
                    "files": [],
                    "creates": [],
                    "depends_on": [],
                },
                {
                    "title": "add behavior",
                    "complexity": "low",
                    "change_type": "feature",
                    "rationale": "new behavior",
                    "files": [],
                    "creates": [],
                    "depends_on": [1],
                },
            ]
        )

        answers = _basic_metadata_answers()

        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            # ``from_description`` routes step decomposition through the
            # claude proposal path so ``claude_invoker`` supplies the
            # classified steps; ``seed_body`` alone would fall through to
            # interactive step entry and never consult the invoker.
            from_description="restructure then extend",
            seed_body=full_seed,
            input_fn=_queue_input(answers),
            claude_invoker=lambda prompt: classified_steps,
        )

        assert result.plan_path.exists()
        body = result.plan_path.read_text(encoding="utf-8")
        assert "_(TODO)_" not in body
        assert "Per-step test strategy" in body
        assert "step 1 (refactor)" in body
        assert "step 2 (feature)" in body

    def test_iteration_mode_bypasses_pre_write_check(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``budget.enabled=True`` skips the fail-loud gate so the
        convergence loop's ``apply_finding`` calls own the TODO-fill path.

        With a partially-populated seed the gate would otherwise refuse;
        flipping iteration on must let the plan land so the loop can run.
        The ``apply_finding`` stub here doesn't actually fill placeholders,
        which lets the assertion pin ``_(TODO)_`` in the on-disk body and
        prove the gate was bypassed (otherwise the file wouldn't exist).
        """
        from plan_tool import create as create_module

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"
        seed = (FIXTURES_CREATE / "partial-body-source.md").read_text(
            encoding="utf-8"
        )

        collect_calls = {"n": 0}

        def fake_collect(*args, **kwargs):
            collect_calls["n"] += 1
            return [_rec("A")] if collect_calls["n"] == 1 else []

        monkeypatch.setattr(
            create_module, "collect_deterministic_findings", fake_collect
        )
        monkeypatch.setattr(
            create_module,
            "apply_finding",
            lambda *a, **kw: _stub_apply_result(),
        )

        counter = {"n": 0}
        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description=seed,
            seed_body=seed,
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=_iter_invoker(counter),
            budget=_IterativeBudget(enabled=True, max_iterations=1),
        )

        assert result.plan_path.exists()
        # Loop ran exactly once: round 0 collect (initial) + round 1
        # collect (post-apply, returns [] → converged).
        assert collect_calls["n"] == 2
        body = result.plan_path.read_text(encoding="utf-8")
        assert "_(TODO)_" in body

    def test_todo_failure_does_not_archive_collision(
        self, tmp_path: Path
    ) -> None:
        """A pre-write TODO failure leaves a colliding existing plan
        byte-identical: the check runs BEFORE
        :func:`archive_existing_source`, so a rejected create cannot
        prepend a Replaced-by notice or move the file to ``archive/``."""
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        existing = out_dir / "2-demo.md"
        sentinel = "# sentinel content (must survive)\n"
        existing.write_text(sentinel, encoding="utf-8")

        answers = _basic_metadata_answers() + _single_step_answers()

        with pytest.raises(
            CreateError, match=r"_\(TODO\)_ placeholders in:"
        ):
            create_plan(
                "demo",
                repo_root=tmp_path,
                output_dir_override=out_dir,
                manifest_path=manifest,
                input_fn=_queue_input(answers),
                replace_on_collision=True,
            )

        assert existing.read_text(encoding="utf-8") == sentinel
        assert not (out_dir / "archive").exists()
        assert not manifest.exists()


# --- Body-sections synthesis ---------------------------------------------


_BODY_CANONICAL_KEYS: tuple[str, ...] = (
    "Overview",
    "Problem statement",
    "Architecture",
    "Out of scope",
    "Risks",
    "Testing",
    "Acceptance criteria",
    "Deferred",
)


def _full_body_payload() -> dict[str, str]:
    """Return a JSON-shaped dict with one unique non-empty string per canonical key."""
    return {key: f"body for {key}" for key in _BODY_CANONICAL_KEYS}


def _full_body_json() -> str:
    return json.dumps(_full_body_payload())


class TestParseBodySectionsJson:
    def test_happy_path_all_eight_keys_populated(self) -> None:
        raw = _full_body_json()
        result, error = _parse_body_sections_json(raw)
        assert error is None
        assert result is not None
        assert set(result.keys()) == set(_BODY_CANONICAL_KEYS)
        for key in _BODY_CANONICAL_KEYS:
            assert result[key] == f"body for {key}"

    def test_happy_path_required_canonical_keys_stay_stable(self) -> None:
        from plan_tool.create import _canonical_body_section_keys

        assert _canonical_body_section_keys() == _BODY_CANONICAL_KEYS
        assert "Input" not in _canonical_body_section_keys()

    def test_optional_input_section_can_be_preserved(self) -> None:
        payload = _full_body_payload()
        payload["Input"] = "Reads the saved drift audit JSON."
        result, error = _parse_body_sections_json(json.dumps(payload))
        assert error is None
        assert result is not None
        assert result["Input"] == "Reads the saved drift audit JSON."
        assert set(result) == set(_BODY_CANONICAL_KEYS) | {"Input"}

    def test_body_section_parser_accepts_recognized_guardrails(self) -> None:
        payload = _full_body_payload()
        supplied_guardrails = {
            "Scope guardrails": "Keep this change narrow.",
            "Audit guardrails": "Do not alter audit severity.",
            "Expected placement": "Keep this beside the parser.",
        }
        payload.update(supplied_guardrails)
        result, error = _parse_body_sections_json(json.dumps(payload))
        assert error is None
        assert result is not None
        for heading, body in supplied_guardrails.items():
            assert result[heading] == body

        payload["Unknown guardrail"] = "not allowed"
        result, error = _parse_body_sections_json(json.dumps(payload))
        assert result is None
        assert error is not None
        assert "Unknown guardrail" in error

    def test_null_values_preserved_as_python_none(self) -> None:
        payload: dict[str, Optional[str]] = {
            key: f"body for {key}" for key in _BODY_CANONICAL_KEYS
        }
        payload["Risks"] = None
        payload["Deferred"] = None
        result, error = _parse_body_sections_json(json.dumps(payload))
        assert error is None
        assert result is not None
        assert result["Risks"] is None
        assert result["Deferred"] is None
        assert result["Overview"] == "body for Overview"

    def test_tolerates_chatter_around_object(self) -> None:
        raw = f"Here you go:\n{_full_body_json()}\nHope that helps."
        result, error = _parse_body_sections_json(raw)
        assert error is None
        assert result is not None
        assert result["Overview"] == "body for Overview"

    def test_rejects_missing_canonical_key_returns_none(self) -> None:
        payload = _full_body_payload()
        del payload["Risks"]
        result, error = _parse_body_sections_json(json.dumps(payload))
        assert result is None
        assert error is not None
        assert "Risks" in error

    def test_rejects_unknown_key_returns_none(self) -> None:
        payload = _full_body_payload()
        payload["Cost analysis"] = "bogus"
        result, error = _parse_body_sections_json(json.dumps(payload))
        assert result is None
        assert error is not None
        assert "Cost analysis" in error

    @pytest.mark.parametrize("forbidden", ["Steps", "References"])
    def test_rejects_steps_or_references_keys(self, forbidden: str) -> None:
        payload = _full_body_payload()
        payload[forbidden] = "should not be here"
        result, error = _parse_body_sections_json(json.dumps(payload))
        assert result is None
        assert error is not None
        assert forbidden in error

    @pytest.mark.parametrize(
        "bad_value", [42, True, ["x"], {"nested": "value"}]
    )
    def test_rejects_non_string_non_null_value(self, bad_value: object) -> None:
        payload: dict[str, object] = dict(_full_body_payload())
        payload["Risks"] = bad_value
        result, error = _parse_body_sections_json(json.dumps(payload))
        assert result is None
        assert error is not None
        assert "Risks" in error

    def test_rejects_top_level_array_returns_none(self) -> None:
        result, error = _parse_body_sections_json('[{"Overview": "x"}]')
        assert result is None
        assert error is not None

    def test_rejects_unparseable_json_returns_none(self) -> None:
        result, error = _parse_body_sections_json("sorry I cannot help")
        assert result is None
        assert error is not None

    def test_empty_string_value_rejected(self) -> None:
        payload = _full_body_payload()
        payload["Overview"] = ""
        result, error = _parse_body_sections_json(json.dumps(payload))
        assert result is None
        assert error is not None
        assert "Overview" in error


class TestProposeBodySectionsFromClaude:
    def test_complete_on_success_returns_eight_key_dict(self) -> None:
        reporter = _RecordingReporter()
        result = propose_body_sections(
            "seed prose",
            lambda prompt: _full_body_json(),
            reporter=reporter,
        )
        assert set(result.keys()) == set(_BODY_CANONICAL_KEYS)
        for key in _BODY_CANONICAL_KEYS:
            assert result[key] == f"body for {key}"
        assert reporter.handles[0].completed is not None
        assert reporter.handles[0].failed is None
        idx, total, label = reporter.starts[0]
        assert (idx, total) == (1, 1)
        assert "body sections" in label.lower()

    def test_returns_all_null_dict_when_both_attempts_fail(self) -> None:
        reporter = _RecordingReporter()
        counter = {"n": 0}

        def invoker(prompt: str) -> str:
            counter["n"] += 1
            return "sorry I cannot help"

        result = propose_body_sections(
            "seed prose",
            invoker,
            reporter=reporter,
        )
        assert counter["n"] == 2
        assert result == {key: None for key in _BODY_CANONICAL_KEYS}
        assert reporter.handles[0].failed is not None
        _, reason = reporter.handles[0].failed
        assert "body-sections synthesis failed" in reason

    def test_retry_fires_on_first_parse_failure(self) -> None:
        counter = {"n": 0}
        captured_prompts: list[str] = []

        def invoker(prompt: str) -> str:
            captured_prompts.append(prompt)
            counter["n"] += 1
            if counter["n"] == 1:
                return "garbage with no json"
            return _full_body_json()

        reporter = _RecordingReporter()
        result = propose_body_sections(
            "seed prose",
            invoker,
            reporter=reporter,
        )
        assert counter["n"] == 2
        # Recovered to a fully-populated dict (not all-null).
        assert result["Overview"] == "body for Overview"
        # First prompt is the plain synthesis prompt; second carries the
        # repair block built by ``_render_synthesis_prompt(..., repair_error=...,
        # prior_response=...)``.
        assert "## Repair retry" not in captured_prompts[0]
        assert "## Repair retry" in captured_prompts[1]
        assert "Your prior response failed validation" in captured_prompts[1]
        # The reporter records a completion on the same handle (the
        # retry does not allocate a fresh step).
        assert reporter.handles[0].completed is not None

    def test_retry_failure_records_two_attempts(self) -> None:
        counter = {"n": 0}

        def invoker(prompt: str) -> str:
            counter["n"] += 1
            return "still no json"

        reporter = _RecordingReporter()
        result = propose_body_sections(
            "seed prose",
            invoker,
            reporter=reporter,
        )
        assert counter["n"] == 2
        assert result == {key: None for key in _BODY_CANONICAL_KEYS}

    def test_prompt_carries_source_text(self) -> None:
        seen: dict[str, str] = {}
        marker = "Marker-seed-7a91"

        def invoker(prompt: str) -> str:
            seen["prompt"] = prompt
            return _full_body_json()

        propose_body_sections(
            f"## Goal\n{marker}\n",
            invoker,
            reporter=_RecordingReporter(),
        )
        assert marker in seen["prompt"]

    def test_prompt_carries_local_code_context_and_conflict_rule(self) -> None:
        seen: dict[str, str] = {}
        body = _full_body_payload()
        body["Architecture"] = "Use `pkg/decision.py:resolve` for routing."

        def invoker(prompt: str) -> str:
            seen["prompt"] = prompt
            return json.dumps(body)

        propose_body_sections(
            "seed prose",
            invoker,
            local_code_context="local-code-marker-72bd",
            local_code_anchors=("pkg/decision.py:resolve",),
            reporter=_RecordingReporter(),
        )

        assert "## Local repository code" in seen["prompt"]
        assert "local-code-marker-72bd" in seen["prompt"]
        assert "## Required local code citations" in seen["prompt"]
        assert "- `pkg/decision.py:resolve`" in seen["prompt"]
        assert "Seed/code conflict" in seen["prompt"]
        assert "Architecture altitude" in seen["prompt"]
        assert "observable-contract" in seen["prompt"]
        assert "source- or local-code-supported" in seen["prompt"]
        assert "leave those inner mechanics to detail" in seen["prompt"]

    @pytest.mark.parametrize(
        "seed",
        [
            pytest.param(
                "## Goal\n\n"
                "Refactor dispatch while retaining outer-ordering-refactor.\n",
                id="refactor",
            ),
            pytest.param(
                "## Goal\n\n"
                "Deliver feature-outcome-feature for users.\n",
                id="feature",
            ),
            pytest.param(
                "## Goal\n\n"
                "Deliver feature-outcome-mixed while restructuring "
                "outer-ownership-mixed.\n",
                id="mixed",
            ),
        ],
    )
    def test_synthesis_prompt_keeps_architecture_at_contract_level(
        self, seed: str
    ) -> None:
        seen: dict[str, str] = {}

        def invoker(prompt: str) -> str:
            seen["prompt"] = prompt
            return _full_body_json()

        propose_body_sections(seed, invoker, reporter=_RecordingReporter())

        normalized_prompt = " ".join(seen["prompt"].split())
        assert seed in seen["prompt"]
        assert "outer ownership, ordering, bypass, terminal" in normalized_prompt
        assert "every seed-stated feature outcome" in normalized_prompt
        assert (
            "guard, predicate, accumulator, rebuild, callback, or fixture"
            in normalized_prompt
        )
        assert "leave those inner mechanics to detail" in normalized_prompt
        assert "keep the plan no broader than the seed's intended outcome" in normalized_prompt

    def test_synthesis_prompt_does_not_infer_a_refactor_map_from_grounding(
        self,
    ) -> None:
        seen: dict[str, str] = {}

        def invoker(prompt: str) -> str:
            seen["prompt"] = prompt
            return _full_body_json()

        propose_body_sections(
            "## Goal\n\nKeep independent-terminal-boundary visible.\n",
            invoker,
            local_code_context="guard-marker-43bc\nrebuild-marker-43bc",
            dependency_cohesion_block=(
                "- Step 2 depends on step 1 — cohesion-marker-43bc"
            ),
            reporter=_RecordingReporter(),
        )

        normalized_prompt = " ".join(seen["prompt"].split())
        assert "guard-marker-43bc" in seen["prompt"]
        assert "rebuild-marker-43bc" in seen["prompt"]
        assert "cohesion-marker-43bc" in seen["prompt"]
        assert "not proof of an ownership boundary" in normalized_prompt
        assert "not automatically independent" in normalized_prompt
        assert (
            "Do not manufacture a refactor phase map, dependency graph"
            in normalized_prompt
        )
        assert "Preserve a supported outer boundary even when it" in normalized_prompt

    def test_prompt_carries_dependency_cohesion_block(self) -> None:
        seen: dict[str, str] = {}

        def invoker(prompt: str) -> str:
            seen["prompt"] = prompt
            return _full_body_json()

        propose_body_sections(
            "seed prose",
            invoker,
            dependency_cohesion_block=(
                "- Step 4 depends on step 1 — cohesion-marker-91fc"
            ),
            reporter=_RecordingReporter(),
        )

        assert "## Dependency cohesion" in seen["prompt"]
        assert "cohesion-marker-91fc" in seen["prompt"]
        # Surfaced ahead of the Architecture-anchor evidence — BACKLOG #252's
        # "the grounding checks cohesion-bearing dependency claims first".
        assert seen["prompt"].index("cohesion-marker-91fc") < seen[
            "prompt"
        ].index("## Local repository code")

    def test_prompt_dependency_cohesion_block_empty_fallback(self) -> None:
        seen: dict[str, str] = {}

        def invoker(prompt: str) -> str:
            seen["prompt"] = prompt
            return _full_body_json()

        propose_body_sections(
            "seed prose",
            invoker,
            reporter=_RecordingReporter(),
        )

        assert (
            "No `depends_on` edge lacks a shared declared production file"
            in seen["prompt"]
        )

    def test_retries_when_architecture_omits_resolved_local_anchor(self) -> None:
        prompts: list[str] = []
        counter = {"n": 0}
        missing = _full_body_payload()
        retained = _full_body_payload()
        retained["Architecture"] = (
            "Route calibration through `pkg/decision.py:resolve`."
        )

        def invoker(prompt: str) -> str:
            prompts.append(prompt)
            counter["n"] += 1
            return json.dumps(missing if counter["n"] == 1 else retained)

        result = propose_body_sections(
            "seed prose",
            invoker,
            local_code_context="local-code-marker-72bd",
            local_code_anchors=("pkg/decision.py:resolve",),
            reporter=_RecordingReporter(),
        )

        assert counter["n"] == 2
        assert result["Architecture"] == retained["Architecture"]
        assert "Architecture must retain every resolved repository anchor" in prompts[1]

    def test_prompt_carries_section_shapes_block(self) -> None:
        seen: dict[str, str] = {}

        def invoker(prompt: str) -> str:
            seen["prompt"] = prompt
            return _full_body_json()

        propose_body_sections(
            "seed prose",
            invoker,
            reporter=_RecordingReporter(),
        )
        prompt = seen["prompt"]
        # Every canonical key surfaces in the rendered prompt.
        for key in _BODY_CANONICAL_KEYS:
            assert key in prompt, f"section name {key!r} missing from prompt"
        # The shape catalog's bulleted phrasing is embedded (proves
        # ``_render_section_shapes_block`` walked ``PLAN_BODY_SECTION_SHAPES``
        # rather than hardcoding a duplicate).
        assert "Bulleted exclusions" in prompt

    def test_prompt_documents_conditional_input_outside_required_json(self) -> None:
        seen: dict[str, str] = {}

        def invoker(prompt: str) -> str:
            seen["prompt"] = prompt
            return _full_body_json()

        propose_body_sections(
            "seed prose",
            invoker,
            reporter=_RecordingReporter(),
        )
        prompt = seen["prompt"]
        example = prompt.split("```json", 1)[1].split("```", 1)[0]
        assert '"Input"' not in example
        assert "are\nthe only recognized optional keys" in prompt
        assert "existing data structure" in prompt


class TestProposeBodySectionsCheckpoint:
    def test_writes_checkpoint_when_slug_and_output_dir_provided(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()

        raw = _full_body_json()
        result = propose_body_sections(
            "seed prose",
            lambda prompt: raw,
            reporter=_RecordingReporter(),
            slug="demo",
            output_dir=out_dir,
            repo_root=tmp_path,
        )
        assert set(result.keys()) == set(_BODY_CANONICAL_KEYS)

        ckpt = checkpoint_path(tmp_path, "demo", _BODY_SECTIONS_CHECKPOINT_NAME)
        assert ckpt.exists()
        body = json.loads(ckpt.read_text(encoding="utf-8"))
        assert body["payload"] == raw
        assert body["input_hash"] == _body_sections_input_hash(
            "demo", "seed prose", out_dir, tmp_path
        )

    def test_skips_invoker_on_cache_hit(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()

        ckpt = checkpoint_path(tmp_path, "demo", _BODY_SECTIONS_CHECKPOINT_NAME)
        save_checkpoint(
            ckpt,
            Checkpoint(
                input_hash=_body_sections_input_hash(
                    "demo", "seed prose", out_dir, tmp_path
                ),
                payload=_full_body_json(),
                created_at=_now_iso(),
            ),
        )

        def explode(prompt: str) -> str:
            raise AssertionError("invoker must not be called on cache hit")

        result = propose_body_sections(
            "seed prose",
            explode,
            reporter=_RecordingReporter(),
            slug="demo",
            output_dir=out_dir,
            repo_root=tmp_path,
        )
        assert result["Overview"] == "body for Overview"

    def test_cache_miss_on_source_text_change_re_invokes(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()

        ckpt = checkpoint_path(tmp_path, "demo", _BODY_SECTIONS_CHECKPOINT_NAME)
        save_checkpoint(
            ckpt,
            Checkpoint(
                input_hash=_body_sections_input_hash(
                    "demo", "old seed", out_dir, tmp_path
                ),
                payload=_full_body_json(),
                created_at=_now_iso(),
            ),
        )

        counter = {"n": 0}
        fresh_payload = json.dumps(
            {key: f"fresh {key}" for key in _BODY_CANONICAL_KEYS}
        )

        def invoker(prompt: str) -> str:
            counter["n"] += 1
            return fresh_payload

        result = propose_body_sections(
            "new seed",
            invoker,
            reporter=_RecordingReporter(),
            slug="demo",
            output_dir=out_dir,
            repo_root=tmp_path,
        )
        assert counter["n"] == 1
        assert result["Overview"] == "fresh Overview"
        body = json.loads(ckpt.read_text(encoding="utf-8"))
        assert body["payload"] == fresh_payload
        assert body["input_hash"] == _body_sections_input_hash(
            "demo", "new seed", out_dir, tmp_path
        )

    def test_no_checkpoint_when_slug_or_output_dir_missing(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()

        result = propose_body_sections(
            "seed prose",
            lambda prompt: _full_body_json(),
            reporter=_RecordingReporter(),
        )
        assert set(result.keys()) == set(_BODY_CANONICAL_KEYS)

        ckpt_root = tmp_path / ".plan-tool" / "checkpoints"
        assert not ckpt_root.exists() or not any(ckpt_root.rglob("*.json"))

    def test_iter1_shards_into_separate_filename(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()

        result = propose_body_sections(
            "seed prose",
            lambda prompt: _full_body_json(),
            reporter=_RecordingReporter(),
            slug="demo",
            output_dir=out_dir,
            repo_root=tmp_path,
            iteration=1,
        )
        assert set(result.keys()) == set(_BODY_CANONICAL_KEYS)

        iter_ckpt = checkpoint_path(
            tmp_path, "demo", f"{_BODY_SECTIONS_CHECKPOINT_NAME}-iter1"
        )
        assert iter_ckpt.exists()
        # The round-0 path is *not* used when iteration > 0.
        round0_ckpt = checkpoint_path(
            tmp_path, "demo", _BODY_SECTIONS_CHECKPOINT_NAME
        )
        assert not round0_ckpt.exists()

    def test_resume_false_skips_load_but_still_saves(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()

        ckpt = checkpoint_path(tmp_path, "demo", _BODY_SECTIONS_CHECKPOINT_NAME)
        save_checkpoint(
            ckpt,
            Checkpoint(
                input_hash=_body_sections_input_hash(
                    "demo", "seed prose", out_dir, tmp_path
                ),
                payload="corrupt — should be overwritten",
                created_at=_now_iso(),
            ),
        )

        counter = {"n": 0}
        fresh = _full_body_json()

        def invoker(prompt: str) -> str:
            counter["n"] += 1
            return fresh

        result = propose_body_sections(
            "seed prose",
            invoker,
            reporter=_RecordingReporter(),
            slug="demo",
            output_dir=out_dir,
            repo_root=tmp_path,
            resume=False,
        )
        assert counter["n"] == 1
        assert result["Overview"] == "body for Overview"
        body = json.loads(ckpt.read_text(encoding="utf-8"))
        assert body["payload"] == fresh

    def test_tty_prompt_yes_reuses_cached_proposal(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()

        ckpt = checkpoint_path(tmp_path, "demo", _BODY_SECTIONS_CHECKPOINT_NAME)
        save_checkpoint(
            ckpt,
            Checkpoint(
                input_hash=_body_sections_input_hash(
                    "demo", "seed prose", out_dir, tmp_path
                ),
                payload=_full_body_json(),
                created_at=_now_iso(),
            ),
        )

        monkeypatch.setattr("sys.stdin.isatty", lambda: True)

        def explode(prompt: str) -> str:
            raise AssertionError("invoker must not be called on cache accept")

        result = propose_body_sections(
            "seed prose",
            explode,
            reporter=_RecordingReporter(),
            slug="demo",
            output_dir=out_dir,
            repo_root=tmp_path,
            input_fn=lambda _q: "",  # empty → default yes
        )
        assert result["Overview"] == "body for Overview"


class TestBodySectionsInputHash:
    def test_iteration_zero_legacy_equivalence(self, tmp_path: Path) -> None:
        out_dir = tmp_path / "plans"
        bare = _body_sections_input_hash("demo", "x", out_dir, tmp_path)
        explicit = _body_sections_input_hash(
            "demo", "x", out_dir, tmp_path, iteration=0
        )
        assert bare == explicit

    def test_iteration_n_perturbs_hash(self, tmp_path: Path) -> None:
        out_dir = tmp_path / "plans"
        h0 = _body_sections_input_hash(
            "demo", "x", out_dir, tmp_path, iteration=0
        )
        h1 = _body_sections_input_hash(
            "demo", "x", out_dir, tmp_path, iteration=1
        )
        h2 = _body_sections_input_hash(
            "demo", "x", out_dir, tmp_path, iteration=2
        )
        assert len({h0, h1, h2}) == 3

    def test_source_text_change_invalidates(self, tmp_path: Path) -> None:
        out_dir = tmp_path / "plans"
        a = _body_sections_input_hash("demo", "old", out_dir, tmp_path)
        b = _body_sections_input_hash("demo", "new", out_dir, tmp_path)
        assert a != b

    def test_project_context_change_invalidates_create_hashes(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.create import _intent_review_input_hash

        out_dir = tmp_path / "plans"
        empty = _body_sections_input_hash("demo", "seed", out_dir, tmp_path)
        assert empty == _body_sections_input_hash(
            "demo", "seed", out_dir, tmp_path, project_context=""
        )
        old = _body_sections_input_hash(
            "demo", "seed", out_dir, tmp_path, project_context="intent: old"
        )
        new = _body_sections_input_hash(
            "demo", "seed", out_dir, tmp_path, project_context="intent: new"
        )
        assert len({empty, old, new}) == 3

        initial = _initial_steps_input_hash("demo", "seed", out_dir, tmp_path)
        assert initial == _initial_steps_input_hash(
            "demo", "seed", out_dir, tmp_path, project_context=""
        )
        assert initial != _initial_steps_input_hash(
            "demo", "seed", out_dir, tmp_path, project_context="intent: old"
        )

        plan = Plan(
            title="Demo",
            status=PlanStatus.PLANNING,
            priority=Priority.LOW,
            steps=[Step(id=1, title="Build it")],
        )
        intent_review = _intent_review_input_hash("demo", plan, out_dir, tmp_path)
        assert intent_review == _intent_review_input_hash(
            "demo", plan, out_dir, tmp_path, project_context=""
        )
        assert intent_review != _intent_review_input_hash(
            "demo", plan, out_dir, tmp_path, project_context="intent: old"
        )

    def test_local_code_context_change_invalidates(self, tmp_path: Path) -> None:
        out_dir = tmp_path / "plans"
        a = _body_sections_input_hash(
            "demo", "seed", out_dir, tmp_path, local_code_context="old code"
        )
        b = _body_sections_input_hash(
            "demo", "seed", out_dir, tmp_path, local_code_context="new code"
        )
        assert a != b

    def test_dependency_cohesion_block_change_invalidates(
        self, tmp_path: Path
    ) -> None:
        out_dir = tmp_path / "plans"
        bare = _body_sections_input_hash("demo", "seed", out_dir, tmp_path)
        empty = _body_sections_input_hash(
            "demo", "seed", out_dir, tmp_path, dependency_cohesion_block=""
        )
        assert bare == empty, "empty dependency_cohesion_block must not perturb the hash"
        a = _body_sections_input_hash(
            "demo",
            "seed",
            out_dir,
            tmp_path,
            dependency_cohesion_block="- Step 4 depends on step 1 — ...",
        )
        b = _body_sections_input_hash(
            "demo",
            "seed",
            out_dir,
            tmp_path,
            dependency_cohesion_block="- Step 5 depends on step 1 — ...",
        )
        assert a != b
        assert a != bare

    def test_slug_change_invalidates(self, tmp_path: Path) -> None:
        out_dir = tmp_path / "plans"
        a = _body_sections_input_hash("demo", "x", out_dir, tmp_path)
        b = _body_sections_input_hash("other", "x", out_dir, tmp_path)
        assert a != b

    def test_output_dir_relative_to_repo_root(self, tmp_path: Path) -> None:
        # Two distinct repo roots whose ``output_dir`` resolves to the
        # same repo-relative path (``plans``) produce the same hash —
        # the hash keys on ``_relative_output_dir(...)`` rather than the
        # absolute filesystem path.
        repo_a = tmp_path / "repo_a"
        repo_b = tmp_path / "repo_b"
        repo_a.mkdir()
        repo_b.mkdir()
        out_a = repo_a / "plans"
        out_b = repo_b / "plans"
        h_a = _body_sections_input_hash("demo", "x", out_a, repo_a)
        h_b = _body_sections_input_hash("demo", "x", out_b, repo_b)
        assert h_a == h_b


# --- From-existing body synthesis: free-form / canonical / opt-out ---------
#
# Integration tests for the third Claude round-trip wired by steps 3-5.
# Cover (a) free-form seeds with non-canonical H2 names being populated
# via synthesis, (b) canonical seeds short-circuiting the synthesis call,
# (c) the ``--no-synthesize-body`` CLI opt-out restoring pre-this-plan
# H2-extraction-only behavior, and (d) the ``create-body-sections``
# checkpoint write / hit / miss / discard semantics alongside the
# existing two checkpoints.


_FREE_FORM_SEED = (
    "# Free-form notes\n"
    "\n"
    "## Goal\n"
    "\n"
    "Replace the legacy poller with an event-driven webhook. "
    "marker-goal-a1b2.\n"
    "\n"
    "## Non-goals\n"
    "\n"
    "- Migrating the historical archive. marker-non-goals-c3d4.\n"
    "- Touching the retention policy.\n"
    "\n"
    "## Acceptance criteria (plan-level)\n"
    "\n"
    "- Webhook receives events with HMAC verification. "
    "marker-accept-e5f6.\n"
    "\n"
    "## Notes\n"
    "\n"
    "marker-notes-g7h8 — implementation details.\n"
    "\n"
    "## References\n"
    "\n"
    "- [Webhook API](https://example.test/webhook)\n"
)


_CANONICAL_FULL_SEED = (
    "# Full canonical seed\n"
    "\n"
    "## Overview\n"
    "\n"
    "Canonical overview body.\n"
    "\n"
    "## Problem statement\n"
    "\n"
    "Canonical problem body.\n"
    "\n"
    "## Architecture\n"
    "\n"
    "Canonical architecture body.\n"
    "\n"
    "## References\n"
    "\n"
    "- [Ref](https://example.com) — example reference.\n"
    "\n"
    "## Steps\n"
    "\n"
    "### 1. First step\n"
    "\n"
    "Files:\n"
    "- `apps/web/foo.ts`\n"
    "\n"
    "### 2. Second step\n"
    "\n"
    "Files:\n"
    "- `apps/web/bar.ts`\n"
    "\n"
    "Depends on: 1\n"
    "\n"
    "## Out of scope\n"
    "\n"
    "- Canonical out-of-scope bullet.\n"
    "\n"
    "## Risks\n"
    "\n"
    "- Canonical risk bullet.\n"
    "\n"
    "## Testing\n"
    "\n"
    "- Canonical testing bullet.\n"
    "\n"
    "## Acceptance criteria\n"
    "\n"
    "- Canonical acceptance bullet.\n"
    "\n"
    "## Deferred\n"
    "\n"
    "- Canonical deferred bullet.\n"
)


@pytest.mark.integration
class TestCreatePlanConceptIntegration:
    def test_core_sync_failure_retains_unregistered_parse_valid_artifact(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "manifest.json"
        from plan_tool.concept_review import review_concept_scope
        from plan_tool.concept_sync import ConceptSyncResult, SyncStatus

        def signed_review(tree, steps, **kwargs):
            reviewed = review_concept_scope(
                tree,
                [node.id for node in tree.concepts],
                {node.id: "include" for node in tree.concepts},
                tree.plan_fingerprint,
                sign_off=True,
            )
            owned = steps[0].model_copy(
                update={"concept_ids": [reviewed.concepts[0].id]}
            )
            return reviewed, [owned, *steps[1:]]

        monkeypatch.setattr("plan_tool.create._review_create_concepts", signed_review)
        monkeypatch.setattr(
            "plan_tool.create.synchronize_concepts",
            lambda *args, **kwargs: ConceptSyncResult(
                SyncStatus.INVALID_STATE, "invalid reviewed state"
            ),
        )

        with pytest.raises(
            CreateError, match="failed to synchronize concepts"
        ) as exc_info:
            create_plan(
                "demo",
                repo_root=tmp_path,
                output_dir_override=out_dir,
                manifest_path=manifest,
                from_description=_CANONICAL_FULL_SEED,
                seed_body=_CANONICAL_FULL_SEED,
                input_fn=_queue_input(_basic_metadata_answers()),
                claude_invoker=lambda prompt: _REF_JSON,
                concept_invoker=lambda prompt: "not-json",
            )

        # A synchronization failure after the target write leaves the
        # unregistered artifact available for explicit repair or conversion.
        assert (out_dir / "2-demo.md").exists()
        assert exc_info.value.artifact is not None
        assert exc_info.value.artifact.registered is False
        assert exc_info.value.artifact.parse_valid is True
        assert not concepts_path(out_dir / "2-demo.md").exists()
        assert not manifest.exists()


    def test_interactive_defer_signs_and_renders_deferred(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "manifest.json"
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        step_response = json.dumps([
            {
                "title": "Ship overview",
                "change_type": "refactor",
                "files": [],
                "depends_on": [],
            }
        ])

        def claude_invoker(prompt: str) -> str:
            if "Propose an initial plan step-list" in prompt:
                return step_response
            return "[]"

        # Accept the proposed change type, then defer every deterministic
        # concept. Extra "defer" answers are harmless — the gate consumes one
        # per section and leaves the rest unread.
        concept_answers = ["", *(["defer"] * 20)]
        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="Build a thing",
            input_fn=_queue_input(
                _basic_metadata_answers() + concept_answers
            ),
            claude_invoker=claude_invoker,
            concept_invoker=lambda prompt: "not-json",
            allow_placeholder_body=True,
        )

        from plan_tool.review_persistence import compute_plan_fingerprint

        tree = load_concepts(
            result.plan_path, compute_plan_fingerprint(result.plan_path)
        )
        assert tree is not None
        assert tree.record_kind == "decision-record"
        assert tree.concepts
        assert all(node.decision == "defer" for node in tree.concepts)
        assert all(node.review_state == "approved" for node in tree.concepts)
        assert all(node.bucket for node in tree.concepts)
        assert "## Deferred" in result.plan_path.read_text(encoding="utf-8")

    def test_no_enrichment_and_no_record_on_undeferred_plan(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "manifest.json"
        concept_prompts: list[str] = []
        claude_prompts: list[str] = []

        def claude_invoker(prompt: str) -> str:
            claude_prompts.append(prompt)
            return _REF_JSON

        def concept_invoker(prompt: str) -> str:
            concept_prompts.append(prompt)
            return "not-json"

        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description=_CANONICAL_FULL_SEED,
            seed_body=_CANONICAL_FULL_SEED,
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=claude_invoker,
            concept_invoker=concept_invoker,
        )

        # An un-deferred plan enriches nothing and persists no concept record.
        assert concept_prompts == []
        assert not any("deterministic concept record" in p for p in claude_prompts)
        assert not concepts_path(result.plan_path).exists()

    def test_resume_reuses_saved_concepts_without_enrichment(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "manifest.json"
        common = dict(
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description=_CANONICAL_FULL_SEED,
            seed_body=_CANONICAL_FULL_SEED,
            claude_invoker=lambda prompt: _REF_JSON,
        )
        create_plan(
            "demo",
            input_fn=_queue_input(_basic_metadata_answers()),
            concept_invoker=lambda prompt: "not-json",
            **common,
        )

        result = create_plan(
            "demo",
            input_fn=_queue_input(_basic_metadata_answers()),
            concept_invoker=lambda prompt: (_ for _ in ()).throw(
                AssertionError("valid resume must skip enrichment")
            ),
            replace_on_collision=True,
            **common,
        )

        assert result.plan_path.is_file()

    @pytest.mark.parametrize("iterate", [False, True])
    def test_undeferred_create_writes_no_concept_record(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, iterate: bool
    ) -> None:
        from plan_tool import create as create_module

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "manifest.json"
        # The --iterate path converges immediately with no findings, so both
        # the default and iterate-tail save arms are reached with an empty
        # (un-deferred) record.
        monkeypatch.setattr(
            create_module, "collect_deterministic_findings", lambda *a, **kw: []
        )
        budget = (
            _IterativeBudget(enabled=True, max_iterations=2)
            if iterate
            else _IterativeBudget(enabled=False)
        )
        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="build a thing",
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=_iter_invoker({"n": 0}),
            concept_invoker=lambda prompt: "not-json",
            budget=budget,
            allow_placeholder_body=True,
        )

        assert not concepts_path(result.plan_path).exists()

    def test_deferral_under_yes_persists_unreviewed_record(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool import create as create_module

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "manifest.json"

        def stub_gate(tree, steps, **kwargs):
            node = ConceptNode(
                id=concept_id("Deferred concept", []),
                title="Deferred concept",
                decision="defer",
                review_state="unreviewed",
                bucket="Deferred concept",
            )
            record = ConceptTree(
                tree.plan_slug,
                tree.plan_fingerprint,
                [node],
                record_kind="decision-record",
            )
            return record, steps

        monkeypatch.setattr(create_module, "_review_create_concepts", stub_gate)

        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="build a thing",
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=_iter_invoker({"n": 0}),
            concept_invoker=lambda prompt: "not-json",
            yes=True,
            allow_placeholder_body=True,
        )

        from plan_tool.review_persistence import compute_plan_fingerprint

        assert concepts_path(result.plan_path).exists()
        tree = load_concepts(
            result.plan_path, compute_plan_fingerprint(result.plan_path)
        )
        assert tree is not None
        assert tree.record_kind == "decision-record"
        assert [node.review_state for node in tree.concepts] == ["unreviewed"]

    @pytest.mark.parametrize("review_state", ["unreviewed", "approved"])
    def test_rerun_carries_forward_a_saved_flat_deferral(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, review_state: str,
    ) -> None:
        """BUG_BACKLOG regression: a `create` re-run used to feed the saved
        flat decision record into `rederive_concepts` (the full-tree three-way
        merge), whose `_source_key` matching never recognizes a flat node.
        An `unreviewed` deferral was silently dropped; an `approved` one
        unconditionally raised `CreateError` on every subsequent create over
        the same plan. Both must now survive a plain re-run untouched."""
        from plan_tool import create as create_module

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "manifest.json"

        def stub_gate(tree, steps, **kwargs):
            node = ConceptNode(
                id=concept_id("Deferred concept", []),
                title="Deferred concept",
                decision="defer",
                review_state=review_state,
                bucket="Deferred concept",
            )
            record = ConceptTree(
                tree.plan_slug, tree.plan_fingerprint, [node],
                record_kind="decision-record",
            )
            return record, steps

        monkeypatch.setattr(create_module, "_review_create_concepts", stub_gate)

        common = dict(
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="build a thing",
            claude_invoker=_iter_invoker({"n": 0}),
            concept_invoker=lambda prompt: "not-json",
            yes=True,
            allow_placeholder_body=True,
        )
        create_plan(
            "demo", input_fn=_queue_input(_basic_metadata_answers()), **common,
        )

        # Second create: undo the stub so the real (unstubbed) merge path
        # runs this time — this is what used to raise CreateError (approved)
        # or silently drop the record (unreviewed) instead of carrying it
        # forward.
        monkeypatch.undo()
        result = create_plan(
            "demo",
            input_fn=_queue_input(_basic_metadata_answers()),
            replace_on_collision=True,
            **common,
        )

        from plan_tool.review_persistence import compute_plan_fingerprint

        assert concepts_path(result.plan_path).exists()
        tree = load_concepts(
            result.plan_path, compute_plan_fingerprint(result.plan_path)
        )
        assert tree is not None
        assert [node.decision for node in tree.concepts] == ["defer"]
        assert [node.review_state for node in tree.concepts] == [review_state]

    def test_create_prints_pending_deferral_summary_line(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool import create as create_module

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "manifest.json"

        def stub_gate(tree, steps, **kwargs):
            node = ConceptNode(
                id=concept_id("Deferred concept", []),
                title="Deferred concept",
                decision="defer",
                review_state="unreviewed",
                bucket="Deferred concept",
            )
            record = ConceptTree(
                tree.plan_slug, tree.plan_fingerprint, [node],
                record_kind="decision-record",
            )
            return record, steps

        monkeypatch.setattr(create_module, "_review_create_concepts", stub_gate)

        create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="build a thing",
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=_iter_invoker({"n": 0}),
            concept_invoker=lambda prompt: "not-json",
            yes=True,
            allow_placeholder_body=True,
        )

        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert "pending concept decision(s) awaiting sign-off" in combined
        assert "plan-tool scope-review demo" in combined

    def test_create_no_deferral_prints_no_pending_line(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "manifest.json"

        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description=_CANONICAL_FULL_SEED,
            seed_body=_CANONICAL_FULL_SEED,
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=lambda prompt: _REF_JSON,
            concept_invoker=lambda prompt: "not-json",
        )

        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert "pending concept decision" not in combined
        assert result.plan_path.is_file()


class TestPersistOrClearConcepts:
    """Unit tests for the write-arms' shared save-or-clear helper (code
    review follow-up): clearing a pre-existing sidecar on an empty result
    is only safe when the merge that produced it is proven not to drop a
    real deferral — the (dormant) full-tree merge is not, so it must keep
    the conservative leave-untouched behavior."""

    def _plan_path(self, tmp_path: Path) -> Path:
        plan_path = tmp_path / "plans" / "2-demo.md"
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        return plan_path

    def _tree(self, *, concepts=()) -> ConceptTree:
        return ConceptTree(
            plan_slug="demo", plan_fingerprint="fp", concepts=list(concepts),
        )

    def test_non_empty_result_is_saved(self, tmp_path: Path) -> None:
        from plan_tool.create import _persist_or_clear_concepts

        plan_path = self._plan_path(tmp_path)
        node = ConceptNode(
            id=concept_id("risks", []), title="risks",
            decision="defer", bucket="risks",
        )
        _persist_or_clear_concepts(
            plan_path, self._tree(concepts=[node]), safe_to_clear=False,
        )
        assert concepts_path(plan_path).exists()

    def test_empty_result_clears_sidecar_when_safe(self, tmp_path: Path) -> None:
        from plan_tool.create import _persist_or_clear_concepts

        plan_path = self._plan_path(tmp_path)
        save_concepts(plan_path, self._tree(concepts=[
            ConceptNode(id=concept_id("risks", []), title="risks",
                        decision="defer", bucket="risks"),
        ]))
        assert concepts_path(plan_path).exists()

        _persist_or_clear_concepts(
            plan_path, self._tree(concepts=[]), safe_to_clear=True,
        )
        assert not concepts_path(plan_path).exists()

    def test_empty_result_leaves_sidecar_when_not_safe(self, tmp_path: Path) -> None:
        from plan_tool.create import _persist_or_clear_concepts

        plan_path = self._plan_path(tmp_path)
        save_concepts(plan_path, self._tree(concepts=[
            ConceptNode(id=concept_id("risks", []), title="risks",
                        decision="defer", bucket="risks"),
        ]))

        _persist_or_clear_concepts(
            plan_path, self._tree(concepts=[]), safe_to_clear=False,
        )
        assert concepts_path(plan_path).exists()

    def test_empty_result_no_pre_existing_sidecar_is_a_no_op(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.create import _persist_or_clear_concepts

        plan_path = self._plan_path(tmp_path)
        _persist_or_clear_concepts(
            plan_path, self._tree(concepts=[]), safe_to_clear=True,
        )
        assert not concepts_path(plan_path).exists()

    def test_unlink_oserror_is_caught_and_warned_not_raised(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from plan_tool import create as create_module
        from plan_tool.create import _persist_or_clear_concepts

        plan_path = self._plan_path(tmp_path)
        save_concepts(plan_path, self._tree(concepts=[
            ConceptNode(id=concept_id("risks", []), title="risks",
                        decision="defer", bucket="risks"),
        ]))

        class _BoomPath:
            def unlink(self):
                raise PermissionError("locked")

        monkeypatch.setattr(
            create_module, "concepts_path", lambda _plan_path: _BoomPath()
        )
        warnings: list[str] = []
        monkeypatch.setattr(create_module, "tool", warnings.append)

        _persist_or_clear_concepts(
            plan_path, self._tree(concepts=[]), safe_to_clear=True,
        )
        assert len(warnings) == 1
        assert "locked" in warnings[0]


def test_distill_prompt_keeps_eight_keys_and_abstains_from_scope_decisions() -> None:
    prompt = (Path(__file__).parents[1] / "plan_tool/prompts/distill-seed.md").read_text(
        encoding="utf-8"
    )
    for key in (
        "Overview", "Problem statement", "Architecture", "Out of scope",
        "Risks", "Testing", "Acceptance criteria", "Deferred",
    ):
        assert f'"{key}"' in prompt
    assert "Concept-owned scope abstention" in prompt
    assert "Keep both keys in the eight-key" in prompt


def test_distill_prompt_preserves_seed_audit_altitude() -> None:
    """The create-side seed pass must not expand a seed into a finished plan."""
    prompt = (Path(__file__).parents[1] / "plan_tool/prompts/distill-seed.md").read_text(
        encoding="utf-8"
    )
    normalized = " ".join(prompt.split())
    assert "Seed-audit boundary" in prompt
    assert "material correctness issues should be resolved until they converge" in normalized
    assert "does **not** perform that review" in normalized
    assert "must not invent corrections" in normalized
    assert "Seed completeness is intentionally narrow" in prompt
    assert "**HIGH** or **CRITICAL**" in prompt
    assert "ordinary completeness" in normalized


def test_distill_prompt_preserves_stage_separated_replays() -> None:
    prompt = (Path(__file__).parents[1] / "plan_tool/prompts/distill-seed.md").read_text(
        encoding="utf-8"
    )
    normalized = " ".join(prompt.split())
    assert "Stage-separated replay preservation" in prompt
    assert "named property, the routes it covers, and both stage dispositions" in normalized
    assert "detail-owned mechanism into `Architecture`" in normalized


def test_stack_is_a_recognized_optional_key_in_both_prompts() -> None:
    # Asserted by key: the recognized-optional-keys sentence must list the
    # backticked ``Stack`` key, and the prompt must keep its existing rule
    # against inventing a guardrail.
    for name in ("synthesize-body.md", "distill-seed.md"):
        prompt = (Path(__file__).parents[1] / "plan_tool/prompts" / name).read_text(
            encoding="utf-8"
        )
        normalized = " ".join(prompt.split())
        sentence = normalized.split("are the only recognized optional keys")[0]
        assert "`Stack`" in sentence.rsplit(".", 1)[-1], name
        assert "never invent a guardrail" in normalized, name


def test_distill_parser_accepts_recognized_guardrails() -> None:
    from plan_tool.create import (
        _render_distilled_markdown,
        _validate_distilled_sections,
    )

    sections: dict[str, object] = _full_body_payload()
    sections.update(
        {
            "Scope guardrails": "DISTILL_SCOPE_BODY",
            "Audit guardrails": "DISTILL_AUDIT_BODY",
            "Expected placement": "DISTILL_PLACEMENT_BODY",
        }
    )
    parsed, error = _validate_distilled_sections(sections)
    assert error is None
    assert parsed is not None
    rendered = _render_distilled_markdown(parsed)
    for heading, body in (
        ("Scope guardrails", "DISTILL_SCOPE_BODY"),
        ("Audit guardrails", "DISTILL_AUDIT_BODY"),
        ("Expected placement", "DISTILL_PLACEMENT_BODY"),
    ):
        assert f"## {heading}" in rendered
        assert body in rendered

    sections["Unrecognized guardrail"] = "nope"
    parsed, error = _validate_distilled_sections(sections)
    assert parsed is None
    assert error is not None
    assert "Unrecognized guardrail" in error


def test_guardrail_prompt_contracts_allow_only_recognized_optional_keys() -> None:
    prompts_dir = Path(__file__).parents[1] / "plan_tool/prompts"
    distill_prompt = (prompts_dir / "distill-seed.md").read_text(encoding="utf-8")
    synthesis_prompt = (prompts_dir / "synthesize-body.md").read_text(
        encoding="utf-8"
    )
    for prompt in (distill_prompt, synthesis_prompt):
        for heading in (
            "Scope guardrails", "Audit guardrails", "Expected placement"
        ):
            assert heading in prompt
        assert "Preserve supplied guardrail text verbatim" in prompt or (
            "preserve that body as a separate section" in prompt
        )
        assert "only recognized optional keys" in prompt or "four recognized optional keys" in prompt


def test_distill_prompt_rejects_data_source_only_coupling_as_shared_implementation() -> None:
    prompt = (Path(__file__).parents[1] / "plan_tool/prompts/distill-seed.md").read_text(
        encoding="utf-8"
    )
    normalized = " ".join(prompt.split())
    assert "names the shared implementation concretely" in normalized
    assert "is not shared implementation" in normalized
    assert "unnamed or data-only coupling claim counts as no claim" in normalized

    # BACKLOG #249's fixture: the withdrawn audit-trajectory-instrumentation seed
    # asserted "two co-dependent gaps share one substrate: the sequence of saved
    # completeness sidecars" — a shared data source, not shared implementation —
    # and distill correctly answered `single` from it. The criterion above must
    # name exactly this shape (an example seed, "sidecar sequence" included) as
    # disqualifying, so this claim no longer counts as evidence for single.
    seed = " ".join((
        Path(__file__).parents[1]
        / "plan-seeds/archive/audit-trajectory-instrumentation.replaced.md"
    ).read_text(encoding="utf-8").split())
    assert "share one substrate: the sequence of saved completeness sidecars" in seed
    assert "sidecar sequence" in normalized


class TestBridgingDependencyEdges:
    """BACKLOG #252: order create's grounding by which depends_on edges

    connect steps sharing no declared production file — the claims most
    worth verifying, since nothing else in the plan's frontmatter backs
    them.
    """

    @staticmethod
    def _step(id_: int, *, files=(), creates=(), depends_on=()) -> Step:
        return Step(
            id=id_,
            title=f"step {id_}",
            files=list(files),
            creates=list(creates),
            depends_on=list(depends_on),
        )

    def test_no_shared_file_is_bridging(self) -> None:
        from plan_tool.create import _bridging_dependency_edges

        steps = [
            self._step(1, files=["plan_tool/a.py"]),
            self._step(2, files=["plan_tool/b.py"], depends_on=[1]),
        ]
        edges = _bridging_dependency_edges(steps)
        assert [(e.dependent_id, e.antecedent_id) for e in edges] == [(2, 1)]

    def test_shared_production_file_is_not_bridging(self) -> None:
        from plan_tool.create import _bridging_dependency_edges

        steps = [
            self._step(1, files=["plan_tool/a.py"]),
            self._step(
                2, files=["plan_tool/a.py", "plan_tool/b.py"], depends_on=[1]
            ),
        ]
        assert _bridging_dependency_edges(steps) == []

    def test_shared_created_file_counts_as_shared(self) -> None:
        from plan_tool.create import _bridging_dependency_edges

        steps = [
            self._step(1, creates=["plan_tool/new_mod.py"]),
            self._step(2, files=["plan_tool/new_mod.py"], depends_on=[1]),
        ]
        assert _bridging_dependency_edges(steps) == []

    def test_shared_test_only_file_is_still_bridging(self) -> None:
        # A shared test file is weak cohesion evidence — steps routinely
        # converge on the same test module without depending on each
        # other's code — so it must not suppress the bridging signal.
        from plan_tool.create import _bridging_dependency_edges

        steps = [
            self._step(1, files=["plan_tool/a.py", "tests/test_shared.py"]),
            self._step(
                2,
                files=["plan_tool/b.py", "tests/test_shared.py"],
                depends_on=[1],
            ),
        ]
        edges = _bridging_dependency_edges(steps)
        assert [(e.dependent_id, e.antecedent_id) for e in edges] == [(2, 1)]

    def test_step_with_no_production_file_purchases_no_edge(self) -> None:
        # A test-only or docs-only step is not "unjustified" — it simply
        # has no production footprint to compare, so its edges are
        # excluded rather than flagged.
        from plan_tool.create import _bridging_dependency_edges

        steps = [
            self._step(1, files=["tests/test_a.py"]),
            self._step(2, files=["DOCS.md"], depends_on=[1]),
        ]
        assert _bridging_dependency_edges(steps) == []

    def test_edges_sorted_by_dependent_then_antecedent(self) -> None:
        from plan_tool.create import _bridging_dependency_edges

        steps = [
            self._step(1, files=["plan_tool/a.py"]),
            self._step(2, files=["plan_tool/b.py"]),
            self._step(3, files=["plan_tool/c.py"], depends_on=[2, 1]),
        ]
        edges = _bridging_dependency_edges(steps)
        assert [(e.dependent_id, e.antecedent_id) for e in edges] == [
            (3, 1),
            (3, 2),
        ]

    def test_render_empty_edges_is_empty_string(self) -> None:
        from plan_tool.create import _render_dependency_cohesion_block

        assert _render_dependency_cohesion_block([]) == ""

    def test_render_names_steps_and_files(self) -> None:
        from plan_tool.create import (
            _BridgingDependencyEdge,
            _render_dependency_cohesion_block,
        )

        edge = _BridgingDependencyEdge(
            dependent_id=4,
            antecedent_id=1,
            dependent_files=("plan_tool/cli/completeness_phases.py",),
            antecedent_files=("plan_tool/telemetry.py",),
        )
        rendered = _render_dependency_cohesion_block([edge])
        assert "Step 4 depends on step 1" in rendered
        assert "`plan_tool/cli/completeness_phases.py`" in rendered
        assert "`plan_tool/telemetry.py`" in rendered

    def test_withdrawn_172_plan_yields_its_measured_four_bridging_edges(
        self,
    ) -> None:
        """BACKLOG #252's named scope-contract fixture.

        The withdrawn `audit-trajectory-instrumentation` plan is the same
        fixture BACKLOG #251 measured by hand: 8 steps, 4 disjoint
        production modules, and exactly the edges 4→1, 4→2, 4→3, 5→1
        sharing no declared production file. Steps 7 (test/fixture-only)
        and 8 (docs-only) purchase no production footprint, so their edges
        (7→4, 7→6, 8→7) are excluded, not flagged — matching #251's own
        "4 disjoint modules" count, not a naive per-edge file diff (which
        would also flag 7→4 and 8→7).
        """
        from plan_tool.create import _bridging_dependency_edges
        from plan_tool.parser import parse_plan_text

        archived = (
            Path(__file__).parents[1]
            / "docs/implementation-plans/archive/2-audit-trajectory-instrumentation.withdrawn.md"
        )
        text = archived.read_text(encoding="utf-8")
        # Strip the leading withdrawal blockquote — parse_plan_text requires
        # the file to open directly on the frontmatter fence.
        text = text[text.index("---") :]
        plan = parse_plan_text(text)

        edges = _bridging_dependency_edges(plan.steps)

        assert [(e.dependent_id, e.antecedent_id) for e in edges] == [
            (4, 1),
            (4, 2),
            (4, 3),
            (5, 1),
        ]


WITHDRAWN_AUDIT_TRAJECTORY_NOTES_FIXTURE = (
    Path(__file__).parent / "fixtures" / "withdrawn_audit_trajectory_depends_on_notes.md"
)


def _bridging_edge_pairs(plan: Plan) -> list[tuple[int, int]]:
    from plan_tool.create import _bridging_dependency_edges

    return [
        (e.dependent_id, e.antecedent_id)
        for e in _bridging_dependency_edges(plan.steps)
    ]


class TestWithdrawnAuditTrajectoryDependsOnNotesFixture:
    """BACKLOG #253: the motivational graph with depends_on_notes on bridging edges."""

    def test_fixture_parses(self) -> None:
        plan = parse_plan(WITHDRAWN_AUDIT_TRAJECTORY_NOTES_FIXTURE)
        assert plan.title.startswith("Audit Trajectory Instrumentation")

    def test_fixture_yields_same_four_bridging_edges_as_archive(self) -> None:
        plan = parse_plan(WITHDRAWN_AUDIT_TRAJECTORY_NOTES_FIXTURE)
        assert _bridging_edge_pairs(plan) == [(4, 1), (4, 2), (4, 3), (5, 1)]

    def test_fixture_bridging_edges_each_have_note_or_visible_silence(
        self,
    ) -> None:
        plan = parse_plan(WITHDRAWN_AUDIT_TRAJECTORY_NOTES_FIXTURE)
        by_id = {s.id: s for s in plan.steps}
        for dependent_id, antecedent_id in _bridging_edge_pairs(plan):
            notes = by_id[dependent_id].depends_on_notes
            if antecedent_id in notes:
                assert notes[antecedent_id].strip()
            else:
                assert antecedent_id not in notes

    def test_fixture_annotates_three_bridging_edges_and_leaves_one_silent(
        self,
    ) -> None:
        plan = parse_plan(WITHDRAWN_AUDIT_TRAJECTORY_NOTES_FIXTURE)
        step4 = plan.step_by_id(4)
        step5 = plan.step_by_id(5)
        for antecedent_id in (1, 2, 3):
            assert step4.depends_on_notes[antecedent_id].strip()
        assert 1 not in step5.depends_on_notes

    def test_fixture_note_keys_are_subset_of_depends_on(self) -> None:
        plan = parse_plan(WITHDRAWN_AUDIT_TRAJECTORY_NOTES_FIXTURE)
        for step in plan.steps:
            assert set(step.depends_on_notes) <= set(step.depends_on)

    def test_fixture_is_not_the_archived_withdrawn_plan(self) -> None:
        text = WITHDRAWN_AUDIT_TRAJECTORY_NOTES_FIXTURE.read_text(encoding="utf-8")
        assert "tests/fixtures/" in str(WITHDRAWN_AUDIT_TRAJECTORY_NOTES_FIXTURE)
        assert not text.startswith("> **Withdrawn")
        assert text.startswith("---")


def test_create_plan_preserves_all_supplied_guardrails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from plan_tool import create as create_module
    from plan_tool.create import DistillOutcome

    (tmp_path / ".git").mkdir()
    output_dir = tmp_path / "plans"
    output_dir.mkdir()
    seed = """## Steps

### 1. Keep guardrails

Files: `plan_tool/create.py`

## Scope guardrails

ORIGINAL_SCOPE_GUARDRAIL

## Audit guardrails

ORIGINAL_AUDIT_GUARDRAIL

## Expected placement

ORIGINAL_EXPECTED_PLACEMENT
"""
    distilled_body = """## Overview

Distilled overview.

## Problem statement

Distilled problem.

## Architecture

Distilled architecture.
"""
    monkeypatch.setattr(
        create_module,
        "propose_distilled_seed_from_claude",
        lambda *_args, **_kwargs: _normalized_outcome_for_test(
            markdown=distilled_body
        ),
    )
    monkeypatch.setattr(
        create_module,
        "propose_references_from_claude",
        lambda *_args, **_kwargs: ReferenceResearchResult.from_references([]),
    )
    monkeypatch.setattr(
        create_module,
        "propose_steps_from_claude",
        lambda *_args, **_kwargs: [Step(id=1, title="Keep guardrails")],
    )
    monkeypatch.setattr(
        create_module,
        "propose_body_sections",
        lambda *_args, **_kwargs: {
            **{key: None for key in _BODY_CANONICAL_KEYS},
            "Scope guardrails": "REWRITTEN_SCOPE_GUARDRAIL",
            "Audit guardrails": "REWRITTEN_AUDIT_GUARDRAIL",
            "Expected placement": "REWRITTEN_EXPECTED_PLACEMENT",
        },
    )

    result = create_plan(
        "demo",
        repo_root=tmp_path,
        output_dir_override=output_dir,
        manifest_path=tmp_path / "plans.json",
        from_description=seed,
        seed_body=seed,
        input_fn=_queue_input(_basic_metadata_answers()),
        claude_invoker=lambda _prompt: "unused",
        distill=True,
        allow_placeholder_body=True,
    )

    body = result.plan_path.read_text(encoding="utf-8")
    assert (
        "## Scope guardrails (dropped during distillation)"
        in capsys.readouterr().err
    )
    for heading, supplied_body, rewritten_body in (
        ("Scope guardrails", "ORIGINAL_SCOPE_GUARDRAIL", "REWRITTEN_SCOPE_GUARDRAIL"),
        ("Audit guardrails", "ORIGINAL_AUDIT_GUARDRAIL", "REWRITTEN_AUDIT_GUARDRAIL"),
        ("Expected placement", "ORIGINAL_EXPECTED_PLACEMENT", "REWRITTEN_EXPECTED_PLACEMENT"),
    ):
        assert body.count(f"## {heading}") == 1
        assert supplied_body in body
        assert rewritten_body not in body


def _guardrail_seed(*headings: str) -> str:
    sections = "\n\n".join(
        f"## {heading}\n\nSUPPLIED_{heading.upper().replace(' ', '_')}"
        for heading in headings
    )
    return """## Steps

### 1. Keep guardrails

Files: `plan_tool/create.py`

""" + sections


def _configure_guardrail_create_stages(
    monkeypatch: pytest.MonkeyPatch,
    *,
    distilled: Optional[str] = None,
    synthesized: Optional[dict[str, Optional[str]]] = None,
) -> None:
    from plan_tool import create as create_module
    from plan_tool.create import DistillOutcome

    if distilled is not None:
        monkeypatch.setattr(
            create_module,
            "propose_distilled_seed_from_claude",
            lambda *_args, **_kwargs: _normalized_outcome_for_test(markdown=distilled),
        )
    monkeypatch.setattr(
        create_module,
        "propose_references_from_claude",
        lambda *_args, **_kwargs: ReferenceResearchResult.from_references([]),
    )
    monkeypatch.setattr(
        create_module,
        "propose_steps_from_claude",
        lambda *_args, **_kwargs: [Step(id=1, title="Keep guardrails")],
    )
    if synthesized is not None:
        monkeypatch.setattr(
            create_module,
            "propose_body_sections",
            lambda *_args, **_kwargs: synthesized,
        )


def _run_guardrail_create(
    tmp_path: Path, seed: str, *, distill: bool
) -> CreateResult:
    (tmp_path / ".git").mkdir()
    output_dir = tmp_path / "plans"
    output_dir.mkdir()
    return create_plan(
        "demo",
        repo_root=tmp_path,
        output_dir_override=output_dir,
        manifest_path=tmp_path / "plans.json",
        from_description=seed,
        seed_body=seed,
        input_fn=_queue_input(_basic_metadata_answers()),
        claude_invoker=lambda _prompt: "unused",
        distill=distill,
        allow_placeholder_body=True,
    )


def test_distill_guardrail_heading_drop_emits_deterministic_finding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    seed = _guardrail_seed(*("Scope guardrails", "Audit guardrails"))
    _configure_guardrail_create_stages(
        monkeypatch,
        distilled="## Scope guardrails\n\nRETAINED_SCOPE",
        synthesized={
            **{key: None for key in _BODY_CANONICAL_KEYS},
            "Scope guardrails": "RETAINED_SCOPE",
        },
    )

    _run_guardrail_create(tmp_path, seed, distill=True)

    stderr = capsys.readouterr().err
    assert "## Audit guardrails (dropped during distillation)" in stderr
    assert "## Scope guardrails (dropped during distillation)" not in stderr


def test_distill_only_guardrail_heading_warns_after_plan_is_written(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    seed = """## Steps

### 1. Keep guardrails

Files: `plan_tool/create.py`

### Scope contract

KEEP_THIS_NARROW
"""
    _configure_guardrail_create_stages(
        monkeypatch,
        distilled="## Scope guardrails\n\nDISTILLED_SCOPE_GUARDRAIL",
        synthesized={
            **{key: None for key in _BODY_CANONICAL_KEYS},
            "Scope guardrails": "DISTILLED_SCOPE_GUARDRAIL",
        },
    )

    result = _run_guardrail_create(tmp_path, seed, distill=True)

    body = result.plan_path.read_text(encoding="utf-8")
    stderr = capsys.readouterr().err
    assert "## Scope guardrails" not in body
    assert "absent from the original seed" in stderr
    assert "will not appear in the written plan" in stderr
    assert "  - ## Scope guardrails" in stderr


def test_distill_guardrail_headings_retained_emit_no_finding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    seed = _guardrail_seed(*("Scope guardrails", "Audit guardrails"))
    _configure_guardrail_create_stages(
        monkeypatch,
        distilled=(
            "## Scope guardrails\n\nRETAINED_SCOPE\n\n"
            "## Audit guardrails\n\nRETAINED_AUDIT"
        ),
        synthesized={
            **{key: None for key in _BODY_CANONICAL_KEYS},
            "Scope guardrails": "RETAINED_SCOPE",
            "Audit guardrails": "RETAINED_AUDIT",
        },
    )

    _run_guardrail_create(tmp_path, seed, distill=True)

    assert "dropped during distillation" not in capsys.readouterr().err


def test_synthesis_guardrail_heading_drop_emits_deterministic_finding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    seed = _guardrail_seed(*("Scope guardrails", "Audit guardrails"))
    _configure_guardrail_create_stages(
        monkeypatch,
        synthesized={
            **{key: None for key in _BODY_CANONICAL_KEYS},
            "Scope guardrails": "RETAINED_SCOPE",
            "Audit guardrails": None,
        },
    )

    _run_guardrail_create(tmp_path, seed, distill=False)

    stderr = capsys.readouterr().err
    assert "## Audit guardrails (dropped during body synthesis)" in stderr
    assert "## Scope guardrails (dropped during body synthesis)" not in stderr


def test_synthesis_retained_and_unsupplied_guardrails_emit_no_finding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    seed = _guardrail_seed("Scope guardrails")
    _configure_guardrail_create_stages(
        monkeypatch,
        synthesized={
            **{key: None for key in _BODY_CANONICAL_KEYS},
            "Scope guardrails": "RETAINED_SCOPE",
            "Audit guardrails": None,
        },
    )

    _run_guardrail_create(tmp_path, seed, distill=False)

    assert "dropped during body synthesis" not in capsys.readouterr().err


def test_synthesis_only_guardrail_heading_warns_after_plan_is_written(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A guardrail heading synthesis invents that the raw seed never
    supplied is not rendered (``_render_plan_body`` reads only
    ``supplied_guardrails``) -- this is the body-synthesis analog of
    ``test_distill_only_guardrail_heading_warns_after_plan_is_written``.
    """
    seed = """## Steps

### 1. Keep guardrails

Files: `plan_tool/create.py`

### Scope contract

KEEP_THIS_NARROW
"""
    _configure_guardrail_create_stages(
        monkeypatch,
        synthesized={
            **{key: None for key in _BODY_CANONICAL_KEYS},
            "Scope guardrails": "SYNTHESIZED_SCOPE_GUARDRAIL",
        },
    )

    result = _run_guardrail_create(tmp_path, seed, distill=False)

    body = result.plan_path.read_text(encoding="utf-8")
    stderr = capsys.readouterr().err
    assert "## Scope guardrails" not in body
    assert "body synthesis produced guardrail heading(s)" in stderr
    assert "absent from the original seed" in stderr
    assert "will not appear in the written plan" in stderr
    assert "  - ## Scope guardrails" in stderr


def test_synthesis_uncarried_and_distill_uncarried_guardrails_both_warn(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Distillation and body synthesis each invent a guardrail heading the
    raw seed never supplied; both stages' warnings fire independently.
    """
    seed = """## Steps

### 1. Keep guardrails

Files: `plan_tool/create.py`
"""
    _configure_guardrail_create_stages(
        monkeypatch,
        distilled="## Scope guardrails\n\nDISTILLED_SCOPE_GUARDRAIL",
        synthesized={
            **{key: None for key in _BODY_CANONICAL_KEYS},
            "Scope guardrails": "DISTILLED_SCOPE_GUARDRAIL",
            "Audit guardrails": "SYNTHESIZED_AUDIT_GUARDRAIL",
        },
    )

    _run_guardrail_create(tmp_path, seed, distill=True)

    stderr = capsys.readouterr().err
    assert "distillation produced guardrail heading(s)" in stderr
    assert "  - ## Scope guardrails" in stderr
    assert "body synthesis produced guardrail heading(s)" not in stderr


# Stable sub-string unique to ``prompts/synthesize-body.md`` (its H1).
# The references prompt uses ``"developer and API reference documentation"``
# and the step-proposal prompt has no synthesis-marker, so a recording
# invoker can route by prefix-matching on these two markers and treat
# everything else as the steps prompt.
_SYNTHESIS_PROMPT_MARKER = "Synthesize plan body sections"


def _synthesis_invoker(
    body_payload: object,
    *,
    prompts_seen: Optional[list[str]] = None,
    explode_on_synthesis: bool = False,
) -> Callable[[str], str]:
    """Build a recording invoker that routes by prompt content.

    Returns ``_STEP_JSON`` for the step-proposal prompt, ``_REF_JSON``
    for the references-research prompt, and ``body_payload`` (rendered to
    JSON when not already a string) for the synthesis prompt. Each call's
    prompt is appended to ``prompts_seen`` when provided so tests can pin
    "this prompt was seen / not seen." Set ``explode_on_synthesis=True``
    to assert synthesis must NOT fire (raises on the synthesis prompt).
    """
    if isinstance(body_payload, str):
        body_raw = body_payload
    else:
        body_raw = json.dumps(body_payload)

    def invoker(prompt: str) -> str:
        if prompts_seen is not None:
            prompts_seen.append(prompt)
        if "Assess whether this file-backed plan source" in prompt:
            return '{"outcome":"single"}'
        if "Distill a free-form seed" in prompt:
            return _valid_preparation_response(prompt)
        if _SYNTHESIS_PROMPT_MARKER in prompt:
            if explode_on_synthesis:
                raise AssertionError(
                    "synthesis prompt must not fire for this run"
                )
            return body_raw
        if "developer and API reference documentation" in prompt:
            return _REF_JSON
        return _STEP_JSON

    return invoker


def _default_body_payload() -> dict[str, str]:
    """Full eight-key synthesis payload, one unique string per key."""
    return {key: f"synthesized {key} body" for key in _BODY_CANONICAL_KEYS}


def _stub_fetch(monkeypatch: pytest.MonkeyPatch, html_by_url: dict[str, bytes]) -> None:
    """Patch ``plan_tool.fetch.urlopen`` to serve canned HTML per URL.

    Overrides the conftest network gate (last setattr wins). A URL absent
    from ``html_by_url`` raises ``URLError`` so the fetch lands in the
    error path, exercising the empty-grounding fallback.
    """
    import plan_tool.fetch as _fetch_mod
    from urllib.error import URLError

    class _Headers:
        def get_content_type(self) -> str:
            return "text/html"

        def get_content_charset(self) -> Optional[str]:
            return "utf-8"

    class _Resp:
        def __init__(self, body: bytes) -> None:
            self._body = body
            self.headers = _Headers()

        def read(self, n: int = -1) -> bytes:
            return self._body if n is None or n < 0 else self._body[:n]

        def __enter__(self) -> "_Resp":
            return self

        def __exit__(self, *exc: object) -> bool:
            return False

    def fake_urlopen(req: object, timeout: object = None) -> object:
        url = getattr(req, "full_url", req)
        if url not in html_by_url:
            raise URLError(f"no stub for {url}")
        return _Resp(html_by_url[url])

    monkeypatch.setattr(_fetch_mod, "urlopen", fake_urlopen)


class TestLocalCodeGrounding:
    def test_reads_only_architecture_inline_code_anchors(self, tmp_path: Path) -> None:
        source = (
            "## Overview\n\nMention `overview_only` without reading it.\n\n"
            "## Architecture\n\n"
            "Route calibration through `resolve_calibration` in "
            "`pkg/decision.py:resolve_calibration`.\n"
        )
        package = tmp_path / "pkg"
        package.mkdir()
        (package / "decision.py").write_text(
            "def resolve_calibration(value: int) -> int:\n"
            "    return value + 1\n",
            encoding="utf-8",
        )
        (package / "other.py").write_text(
            "def overview_only() -> None:\n    pass\n", encoding="utf-8"
        )

        context = _render_local_code_context(source, tmp_path)

        assert "resolve_calibration" in context
        assert "pkg/decision.py" in context
        assert "return value + 1" in context
        assert "overview_only" not in context

    def test_source_change_changes_grounding_context(self, tmp_path: Path) -> None:
        path = tmp_path / "decision.py"
        path.write_text(
            "def resolve_calibration(value: int) -> int:\n    return value + 1\n",
            encoding="utf-8",
        )
        source = "## Architecture\n\nCall `resolve_calibration`.\n"
        before = _render_local_code_context(source, tmp_path)
        path.write_text(
            "def resolve_calibration(value: int) -> int:\n    return value + 2\n",
            encoding="utf-8",
        )

        after = _render_local_code_context(source, tmp_path)

        assert before != after

    def test_missing_anchor_is_uncertainty_not_a_conflict(self, tmp_path: Path) -> None:
        context = _render_local_code_context(
            "## Architecture\n\nAdd `new_pipeline` after validation.\n", tmp_path
        )

        assert "new_pipeline" in context
        assert "absence alone is not a conflict" in context

    def test_missing_explicit_path_does_not_use_a_lookalike(self, tmp_path: Path) -> None:
        (tmp_path / "current.py").write_text(
            "def resolve_calibration() -> None:\n    pass\n", encoding="utf-8"
        )

        context = _render_local_code_context(
            "## Architecture\n\nUse `old.py:resolve_calibration`.\n", tmp_path
        )

        assert "no resolved repository declaration" in context
        assert "named repository path is not on disk" in context
        assert "current.py" not in context

    def test_explicit_path_disambiguates_a_matching_bare_anchor(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "chosen.py").write_text(
            "def resolve_calibration() -> None:\n    pass\n", encoding="utf-8"
        )
        (tmp_path / "lookalike.py").write_text(
            "def resolve_calibration() -> None:\n    pass\n", encoding="utf-8"
        )

        grounding = _render_local_code_grounding(
            "## Architecture\n\nUse `resolve_calibration` in "
            "`chosen.py:resolve_calibration`.\n",
            tmp_path,
        )

        assert grounding.resolved_anchors == ("chosen.py:resolve_calibration",)
        assert "ambiguous repository declaration" not in grounding.context
        assert "lookalike.py" not in grounding.context

    def test_bare_anchor_requires_one_declaration(self, tmp_path: Path) -> None:
        (tmp_path / "comment.py").write_text(
            "# resolve_calibration() is called by the legacy path.\n",
            encoding="utf-8",
        )
        (tmp_path / "decision.py").write_text(
            "def resolve_calibration(value: int) -> int:\n    return value + 1\n",
            encoding="utf-8",
        )

        grounding = _render_local_code_grounding(
            "## Architecture\n\nUse `resolve_calibration`.\n", tmp_path
        )

        assert grounding.resolved_anchors == ("decision.py:resolve_calibration",)
        assert "decision.py:resolve_calibration" in grounding.context
        assert "comment.py" not in grounding.context

    def test_ambiguous_bare_anchor_requires_explicit_path(self, tmp_path: Path) -> None:
        (tmp_path / "legacy.py").write_text(
            "def resolve_calibration() -> None:\n    pass\n", encoding="utf-8"
        )
        (tmp_path / "modern.py").write_text(
            "def resolve_calibration() -> None:\n    pass\n", encoding="utf-8"
        )

        grounding = _render_local_code_grounding(
            "## Architecture\n\nUse `resolve_calibration`.\n", tmp_path
        )

        assert grounding.resolved_anchors == ()
        assert "ambiguous repository declaration" in grounding.context
        assert "`legacy.py:resolve_calibration`" in grounding.context
        assert "`modern.py:resolve_calibration`" in grounding.context
        assert "Source fingerprint" not in grounding.context

    def test_bare_anchor_scan_reads_each_source_once(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "first.py").write_text(
            "def first_anchor() -> None:\n    pass\n", encoding="utf-8"
        )
        (tmp_path / "second.py").write_text(
            "def second_anchor() -> None:\n    pass\n", encoding="utf-8"
        )
        from plan_tool import create as create_module

        original_read = create_module._read_local_code_file
        reads: list[Path] = []

        def spy_read(path: Path) -> tuple[Optional[str], Optional[str]]:
            reads.append(path)
            return original_read(path)

        monkeypatch.setattr(create_module, "_read_local_code_file", spy_read)

        _render_local_code_grounding(
            "## Architecture\n\nUse `first_anchor` and `second_anchor`.\n",
            tmp_path,
        )

        assert {path.relative_to(tmp_path).as_posix() for path in reads} == {
            "first.py",
            "second.py",
        }
        assert len(reads) == len(set(reads))


@pytest.mark.integration
class TestCreatePlanGroundsSynthesisInLocalCode:
    def test_architecture_anchor_reaches_synthesis_prompt(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        (tmp_path / "decision.py").write_text(
            "def resolve_calibration(value: int) -> int:\n"
            "    return value + 1\n",
            encoding="utf-8",
        )
        seed = (
            "## Goal\n\nImprove calibration.\n\n"
            "## Architecture\n\n"
            "Wire the result through `resolve_calibration`.\n"
        )
        prompts_seen: list[str] = []
        body_payload = _default_body_payload()
        body_payload["Architecture"] = (
            "Wire the result through `decision.py:resolve_calibration`."
        )
        invoker = _synthesis_invoker(body_payload, prompts_seen=prompts_seen)

        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=tmp_path / "m.json",
            from_description=seed,
            seed_body=seed,
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=invoker,
            fetch_docs=False,
        )

        prompt = next(p for p in prompts_seen if _SYNTHESIS_PROMPT_MARKER in p)
        assert "## Local repository code" in prompt
        assert "resolve_calibration" in prompt
        assert "return value + 1" in prompt
        assert "- `decision.py:resolve_calibration`" in prompt
        assert "`decision.py:resolve_calibration`" in result.plan_path.read_text(
            encoding="utf-8"
        )


class TestCreatePlanGroundsSynthesisInDependencyCohesion:
    """BACKLOG #252, at the real ``create_plan()`` call site.

    ``propose_body_sections()``'s own unit tests (``test_prompt_carries_
    dependency_cohesion_block``) pass ``dependency_cohesion_block`` directly
    and cannot catch ``create_plan()`` itself failing to forward the value it
    computes — this is that regression test, driving the real orchestrator
    end to end.
    """

    def test_bridging_edge_reaches_synthesis_prompt(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        seed = "## Goal\n\nDo the thing.\n"

        steps_json = json.dumps(
            [
                _proposed_step("first", files=["plan_tool/a.py"]),
                _proposed_step(
                    "second", files=["plan_tool/b.py"], depends_on=[1]
                ),
            ]
        )
        prompts_seen: list[str] = []
        body_payload = _default_body_payload()

        def invoker(prompt: str) -> str:
            prompts_seen.append(prompt)
            if _SYNTHESIS_PROMPT_MARKER in prompt:
                return json.dumps(body_payload)
            if "developer and API reference documentation" in prompt:
                return _REF_JSON
            return steps_json

        create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=tmp_path / "m.json",
            from_description=seed,
            seed_body=seed,
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=invoker,
            fetch_docs=False,
        )

        prompt = next(p for p in prompts_seen if _SYNTHESIS_PROMPT_MARKER in p)
        assert "## Dependency cohesion" in prompt
        assert "Step 2 depends on step 1" in prompt
        assert "`plan_tool/a.py`" in prompt
        assert "`plan_tool/b.py`" in prompt

    def test_deferred_step_purchases_no_edge(self, tmp_path: Path) -> None:
        # A step the concept-review gate parks (scope != committed) is not
        # a live claim the plan is making — its depends_on edge must not
        # appear even when it shares no file with its antecedent.
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        seed = "## Goal\n\nDo the thing.\n"

        steps_json = json.dumps(
            [
                _proposed_step("first", files=["plan_tool/a.py"]),
                _proposed_step(
                    "second", files=["plan_tool/b.py"], depends_on=[1]
                ),
            ]
        )
        prompts_seen: list[str] = []
        body_payload = _default_body_payload()

        def invoker(prompt: str) -> str:
            prompts_seen.append(prompt)
            if _SYNTHESIS_PROMPT_MARKER in prompt:
                return json.dumps(body_payload)
            if "developer and API reference documentation" in prompt:
                return _REF_JSON
            return steps_json

        from plan_tool import create as create_module

        original_review = create_module._review_create_concepts

        def _park_step_two(concept_tree, steps, **kwargs):
            tree, reviewed = original_review(concept_tree, steps, **kwargs)
            reviewed = [
                s.model_copy(update={"scope": StepScope.WONT_DO})
                if s.id == 2
                else s
                for s in reviewed
            ]
            return tree, reviewed

        import pytest as _pytest

        mp = _pytest.MonkeyPatch()
        mp.setattr(
            create_module, "_review_create_concepts", _park_step_two
        )
        try:
            create_plan(
                "demo",
                repo_root=tmp_path,
                output_dir_override=out_dir,
                manifest_path=tmp_path / "m.json",
                from_description=seed,
                seed_body=seed,
                input_fn=_queue_input(_basic_metadata_answers()),
                claude_invoker=invoker,
                fetch_docs=False,
                allow_placeholder_body=True,
            )
        finally:
            mp.undo()

        prompt = next(p for p in prompts_seen if _SYNTHESIS_PROMPT_MARKER in p)
        assert "Step 2 depends on step 1" not in prompt
        assert (
            "No `depends_on` edge lacks a shared declared production file"
            in prompt
        )


@pytest.mark.integration
class TestCreatePlanGroundsSynthesisInFetchedDocs:
    """``fetch_docs`` folds reference-URL content into the synthesis prompt."""

    def test_fetched_doc_content_reaches_synthesis_prompt(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        # ``_REF_JSON`` points at https://example.com — serve it doc text
        # carrying a unique marker the synthesis prompt must echo.
        _stub_fetch(
            monkeypatch,
            {
                "https://example.com": (
                    b"<html><head><title>Webhook API</title></head><body>"
                    b"<p>marker-fetched-doc-z9y8 the HMAC header is X-Sig.</p>"
                    b"</body></html>"
                )
            },
        )
        prompts_seen: list[str] = []
        invoker = _synthesis_invoker(
            _default_body_payload(), prompts_seen=prompts_seen
        )

        create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description=_FREE_FORM_SEED,
            seed_body=_FREE_FORM_SEED,
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=invoker,
        )

        synthesis_prompts = [
            p for p in prompts_seen if _SYNTHESIS_PROMPT_MARKER in p
        ]
        assert synthesis_prompts, "synthesis prompt never fired"
        prompt = synthesis_prompts[0]
        # The extracted doc text + its title are present in the grounding
        # block, and the fenced "## Reference documentation" section exists.
        assert "## Reference documentation" in prompt
        assert "marker-fetched-doc-z9y8" in prompt
        assert "Webhook API" in prompt
        # The seed-only fallback note is NOT present when docs were fetched.
        assert "None fetched" not in prompt

    def test_no_fetch_docs_leaves_synthesis_seed_only(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        # If fetch_docs=False honored its contract, urlopen is never called;
        # raise if it is so a regression is caught loudly.
        def explode(req: object, timeout: object = None) -> object:
            raise AssertionError("fetch must not run under fetch_docs=False")

        import plan_tool.fetch as _fetch_mod

        monkeypatch.setattr(_fetch_mod, "urlopen", explode)
        prompts_seen: list[str] = []
        invoker = _synthesis_invoker(
            _default_body_payload(), prompts_seen=prompts_seen
        )

        create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description=_FREE_FORM_SEED,
            seed_body=_FREE_FORM_SEED,
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=invoker,
            fetch_docs=False,
        )

        prompt = next(
            p for p in prompts_seen if _SYNTHESIS_PROMPT_MARKER in p
        )
        # Grounding block renders the seed-only note; no reference-docs
        # checkpoint was written.
        assert "None fetched" in prompt
        assert not (
            checkpoint_path(tmp_path, "demo", _REFERENCE_DOCS_CHECKPOINT_NAME)
        ).exists()

    def test_dead_link_falls_back_to_seed_only(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        # No stub entry for example.com => URLError => error doc => empty
        # grounding block. The create must still succeed.
        _stub_fetch(monkeypatch, {})
        prompts_seen: list[str] = []
        invoker = _synthesis_invoker(
            _default_body_payload(), prompts_seen=prompts_seen
        )

        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description=_FREE_FORM_SEED,
            seed_body=_FREE_FORM_SEED,
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=invoker,
        )

        assert result.plan_path.is_file()
        prompt = next(
            p for p in prompts_seen if _SYNTHESIS_PROMPT_MARKER in p
        )
        assert "None fetched" in prompt


@pytest.mark.integration
class TestCreatePlanFromExistingFreeForm:
    """Synthesis populates canonical body sections from non-canonical H2 seeds."""

    def test_non_canonical_h2_names_populated_via_synthesis(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        body_payload = {
            "Overview": "Synthesized overview carrying marker-goal-a1b2.",
            "Problem statement": "Synthesized problem statement body.",
            "Architecture": "Synthesized architecture body.",
            "Out of scope": (
                "- Synthesized out-of-scope carrying marker-non-goals-c3d4."
            ),
            "Risks": "- Synthesized risk bullet.",
            "Testing": "- Synthesized testing bullet.",
            "Acceptance criteria": (
                "- Synthesized acceptance carrying marker-accept-e5f6."
            ),
            "Deferred": "- Synthesized deferred bullet.",
        }
        prompts_seen: list[str] = []
        invoker = _synthesis_invoker(body_payload, prompts_seen=prompts_seen)

        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description=_FREE_FORM_SEED,
            seed_body=_FREE_FORM_SEED,
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=invoker,
        )

        body = result.plan_path.read_text(encoding="utf-8")
        # Canonical H2 names land with synthesized prose under them.
        assert "## Overview\n\nSynthesized overview carrying marker-goal-a1b2." in body
        assert "## Out of scope\n\n- Synthesized out-of-scope carrying marker-non-goals-c3d4." in body
        assert "## Acceptance criteria\n\n- Synthesized acceptance carrying marker-accept-e5f6." in body
        # No TODO placeholders survive — synthesis filled every canonical
        # body section.
        assert "_(TODO)_" not in body
        # Synthesis prompt actually fired (not a "skipped" false positive).
        assert any(_SYNTHESIS_PROMPT_MARKER in p for p in prompts_seen)

    def test_synthesis_null_for_risks_renders_todo_not_invented(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        body_payload: dict[str, Optional[str]] = _default_body_payload()
        body_payload["Risks"] = None
        prompts_seen: list[str] = []
        invoker = _synthesis_invoker(body_payload, prompts_seen=prompts_seen)

        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description=_FREE_FORM_SEED,
            seed_body=_FREE_FORM_SEED,
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=invoker,
        )

        body = result.plan_path.read_text(encoding="utf-8")
        # Null synthesis for Risks (and no H2 match in the free-form seed)
        # renders as the literal TODO placeholder — Claude is not asked to
        # invent risks the seed never raised.
        assert "## Risks\n\n_(TODO)_" in body
        # Other canonical sections still populated by synthesis.
        assert "synthesized Overview body" in body
        # Synthesis was actually invoked — distinguishes the null path
        # from a "synthesis was skipped" false positive.
        assert any(_SYNTHESIS_PROMPT_MARKER in p for p in prompts_seen)

    def test_synthesized_wins_over_h2_extracted_when_both_present(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        # Mixed seed: one canonical H2 (Architecture) AND non-canonical
        # H2s so the canonical-skip optimization does NOT fire and
        # synthesis is invoked.
        mixed_seed = (
            "# Mixed seed\n"
            "\n"
            "## Goal\n"
            "\n"
            "Non-canonical Goal body.\n"
            "\n"
            "## Architecture\n"
            "\n"
            "seed-architecture-content marker-seed-arch.\n"
        )

        body_payload = _default_body_payload()
        body_payload["Architecture"] = (
            "synthesized-architecture-content marker-synth-arch"
        )

        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description=mixed_seed,
            seed_body=mixed_seed,
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=_synthesis_invoker(body_payload),
        )

        body = result.plan_path.read_text(encoding="utf-8")
        # Synthesized prose wins over the seed's H2-extracted body.
        assert "marker-synth-arch" in body
        assert "marker-seed-arch" not in body

    def test_null_synthesis_falls_through_to_h2_extracted(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        mixed_seed = (
            "# Mixed seed\n"
            "\n"
            "## Goal\n"
            "\n"
            "Non-canonical Goal body.\n"
            "\n"
            "## Architecture\n"
            "\n"
            "seed-architecture-content marker-seed-arch.\n"
        )

        body_payload: dict[str, Optional[str]] = _default_body_payload()
        body_payload["Architecture"] = None

        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description=mixed_seed,
            seed_body=mixed_seed,
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=_synthesis_invoker(body_payload),
        )

        body = result.plan_path.read_text(encoding="utf-8")
        # Null synthesis falls through to the seed's H2-extracted body.
        assert "marker-seed-arch" in body

    def test_double_repair_failure_writes_plan_with_todos_and_exits_zero(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        synth_attempts = {"n": 0}

        def invoker(prompt: str) -> str:
            if _SYNTHESIS_PROMPT_MARKER in prompt:
                synth_attempts["n"] += 1
                return "garbage with no json"
            if "developer and API reference documentation" in prompt:
                return _REF_JSON
            return _STEP_JSON

        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description=_FREE_FORM_SEED,
            seed_body=_FREE_FORM_SEED,
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=invoker,
        )

        # Initial + one repair retry; second failure falls back to all-null
        # without raising.
        assert synth_attempts["n"] == 2
        assert result.plan_path.exists()
        body = result.plan_path.read_text(encoding="utf-8")
        # All-null synthesis + no H2 match in the free-form seed means
        # every canonical section renders as the literal TODO placeholder.
        assert "## Risks\n\n_(TODO)_" in body
        assert "## Overview\n\n_(TODO)_" in body


@pytest.mark.integration
class TestCreatePlanFromExistingCanonicalSkipsSynthesis:
    """Canonical seeds short-circuit the synthesis round-trip."""

    def test_canonical_seed_skips_synthesis_call(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        prompts_seen: list[str] = []
        # Canonical seed extracts steps deterministically (no Claude call
        # for steps) and ``_canonical_seed_covers_all`` returns True so
        # synthesis is skipped. The only Claude call left is references.
        invoker = _synthesis_invoker(
            "{}",
            prompts_seen=prompts_seen,
            explode_on_synthesis=True,
        )

        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description=_CANONICAL_FULL_SEED,
            seed_body=_CANONICAL_FULL_SEED,
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=invoker,
        )

        # Synthesis prompt never seen by the invoker.
        assert not any(_SYNTHESIS_PROMPT_MARKER in p for p in prompts_seen)
        # Plan still wrote successfully (canonical seed populates body via
        # H2 extraction).
        body = result.plan_path.read_text(encoding="utf-8")
        assert "Canonical overview body." in body
        assert "Canonical risk bullet." in body

    def test_canonical_run_byte_identical_to_no_synthesize_body_run(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / ".git").mkdir()
        out_a = tmp_path / "plans_a"
        out_a.mkdir()
        out_b = tmp_path / "plans_b"
        out_b.mkdir()
        manifest_a = tmp_path / "m_a.json"
        manifest_b = tmp_path / "m_b.json"

        # Recording invoker explodes on synthesis so neither run can
        # depend on a synthesis call. Run A relies on canonical-skip;
        # run B relies on synthesize_body=False — both must produce the
        # same body bytes (the plan-level acceptance criterion).
        invoker = _synthesis_invoker(
            "{}", explode_on_synthesis=True
        )

        result_a = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_a,
            manifest_path=manifest_a,
            from_description=_CANONICAL_FULL_SEED,
            seed_body=_CANONICAL_FULL_SEED,
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=invoker,
        )
        result_b = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_b,
            manifest_path=manifest_b,
            from_description=_CANONICAL_FULL_SEED,
            seed_body=_CANONICAL_FULL_SEED,
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=invoker,
            synthesize_body=False,
        )

        assert result_a.plan_path.read_bytes() == result_b.plan_path.read_bytes()

    def test_canonical_h2_names_with_empty_bodies_still_triggers_synthesis(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        # Every canonical H2 name is present, but each section body is
        # whitespace-only. ``extract_h2_sections`` drops empty sections,
        # so ``_canonical_seed_covers_all`` returns False and synthesis
        # must still run. Includes a canonical Steps section so the
        # step-extraction round-trip skips Claude.
        empty_body_seed = (
            "# Empty canonical bodies\n"
            "\n"
            "## Overview\n"
            "\n"
            "## Problem statement\n"
            "\n"
            "## Architecture\n"
            "\n"
            "## References\n"
            "\n"
            "## Steps\n"
            "\n"
            "### 1. Only step\n"
            "\n"
            "Files:\n"
            "- `a.ts`\n"
            "\n"
            "## Out of scope\n"
            "\n"
            "## Risks\n"
            "\n"
            "## Testing\n"
            "\n"
            "## Acceptance criteria\n"
            "\n"
            "## Deferred\n"
        )

        prompts_seen: list[str] = []
        invoker = _synthesis_invoker(
            _default_body_payload(), prompts_seen=prompts_seen
        )

        create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description=empty_body_seed,
            seed_body=empty_body_seed,
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=invoker,
        )

        # Synthesis prompt fired exactly once — empty-body canonical names
        # do NOT trip the canonical-skip optimization.
        synth_prompts = [
            p for p in prompts_seen if _SYNTHESIS_PROMPT_MARKER in p
        ]
        assert len(synth_prompts) == 1


@pytest.mark.integration
class TestCanonicalSeedWithoutSeedBodyFillsBody:
    """A canonical seed with no ``seed_body`` still fills the plan body.

    ``seed_body`` is ``None`` for every seed authored today — its only
    producer was the removed ``reformat`` provenance frontmatter — so
    this, not the sibling class above, is the shape a real
    ``create --from-existing <canonical seed>`` takes. The regression:
    the synthesis gate re-extracted H2s from ``from_description`` and
    correctly skipped synthesis, while ``seed_sections`` stayed ``{}``
    because it only read ``seed_body``. Both halves now read one
    ``body_source``, so a skip is only taken on sections the renderer
    holds.
    """

    def test_canonical_seed_body_source_falls_back_to_from_description(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        prompts_seen: list[str] = []
        invoker = _synthesis_invoker(
            "{}",
            prompts_seen=prompts_seen,
            explode_on_synthesis=True,
        )

        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description=_CANONICAL_FULL_SEED,
            seed_body=None,  # the shape of every seed authored today
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=invoker,
        )

        # Synthesis is still skipped (the saved round-trip)...
        assert not any(_SYNTHESIS_PROMPT_MARKER in p for p in prompts_seen)
        # ...and the seed's own prose is what the skip bought us: every
        # canonical section carries seed content, none ships _(TODO)_.
        body = result.plan_path.read_text(encoding="utf-8")
        assert _find_placeholder_body_sections(body) == []
        assert "Canonical overview body." in body
        assert "Canonical problem body." in body
        assert "Canonical architecture body." in body
        assert "- Canonical out-of-scope bullet." in body
        assert "- Canonical risk bullet." in body
        assert "- Canonical testing bullet." in body
        assert "- Canonical acceptance bullet." in body
        assert "- Canonical deferred bullet." in body

    def test_seed_body_present_and_absent_render_the_same_body(
        self, tmp_path: Path
    ) -> None:
        """The fallback is a true equivalence, not a near-miss.

        A provenance-resolved ``seed_body`` and the same text arriving
        only as ``from_description`` must produce byte-identical plans.
        """
        (tmp_path / ".git").mkdir()
        out_a = tmp_path / "plans_a"
        out_a.mkdir()
        out_b = tmp_path / "plans_b"
        out_b.mkdir()

        invoker = _synthesis_invoker("{}", explode_on_synthesis=True)

        def _create(out_dir: Path, manifest: str, seed_body: Optional[str]):
            return create_plan(
                "demo",
                repo_root=tmp_path,
                output_dir_override=out_dir,
                manifest_path=tmp_path / manifest,
                from_description=_CANONICAL_FULL_SEED,
                seed_body=seed_body,
                input_fn=_queue_input(_basic_metadata_answers()),
                claude_invoker=invoker,
            )

        with_body = _create(out_a, "m_a.json", _CANONICAL_FULL_SEED)
        without_body = _create(out_b, "m_b.json", None)

        assert (
            with_body.plan_path.read_bytes()
            == without_body.plan_path.read_bytes()
        )

    def test_cli_canonical_seed_needs_no_apply_finding_to_fill_body(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The end-to-end repro: `--from-existing` on a plain seed file.

        Under ``--iterate`` the fail-loud ``_(TODO)_`` gate stands down
        and the convergence loop fills placeholders one
        ``apply_finding`` call per section — the pessimization the bug
        reported (one synthesis call saved, N spent, seed prose
        discarded). With the body filled from the seed there is nothing
        for the loop to fill, so ``apply_finding`` must never fire.
        """
        from plan_tool import create as create_module
        from plan_tool.cli import app as cli_module

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"
        # A plain seed file: no provenance frontmatter, so the CLI's
        # ``_read_seed_body`` returns ``None`` -- unpatched, on purpose.
        seed = tmp_path / "seed.md"
        seed.write_text(_CANONICAL_FULL_SEED, encoding="utf-8")

        invoker = _synthesis_invoker("{}", explode_on_synthesis=True)

        # Record rather than raise: a raise surfaces only as a generic
        # non-zero rc, while a recorded call names the regression outright
        # and lets the run finish so the body assertions below still run.
        apply_calls: list[str] = []

        def _record_apply(*_a, **kwargs):
            apply_calls.append(str(kwargs.get("finding_body", "")))
            return _stub_apply_result()

        monkeypatch.setattr(create_module, "apply_finding", _record_apply)

        original_create_plan = cli_module.create_plan
        answers = _basic_metadata_answers()

        def patched_create_plan(*args, **kwargs):
            kwargs.setdefault("input_fn", _queue_input(answers))
            kwargs["claude_invoker"] = invoker
            return original_create_plan(*args, **kwargs)

        monkeypatch.setattr(
            "plan_tool.cli.authoring.create_plan", patched_create_plan
        )
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "create", "demo",
                "--from-existing", str(seed),
                "--output-dir", str(out_dir),
                "--no-distill",
                "--iterate",
            ]
        )
        assert rc == 0
        assert apply_calls == [], (
            "apply_finding fired: a canonical seed's body should already be "
            "filled from its own H2 sections, leaving the loop nothing to fill"
        )

        written = list(out_dir.glob("*.md"))
        assert len(written) == 1
        body = written[0].read_text(encoding="utf-8")
        assert _find_placeholder_body_sections(body) == []
        assert "Canonical overview body." in body


@pytest.mark.integration
class TestBodySynthesisSkipReasons:
    """Every ``propose_body_sections`` skip names its cause in the run log.

    Four causes bucket to ``outcome="skipped"``, and only one of them
    (``all_null_response``) is a quality signal — the others are
    deliberate savings. Without ``skip_reason`` they are
    indistinguishable in ``runs show``, and a regression that silently
    stops synthesizing reads exactly like a healthy canonical-seed run.
    Three are pinned here; ``no_synthesize_body`` is pinned by
    ``TestCreatePlanNoSynthesizeBodyFlag`` beside its opt-out flag.
    """

    def _body_phase_end(self, repo_root: Path, slug: str) -> dict:
        ends = [
            e for e in _read_run_log(repo_root, slug)
            if e["event"] == "phase_end"
            and e["phase"] == "propose_body_sections"
        ]
        assert len(ends) == 1, f"expected one body phase_end, got {ends}"
        return ends[0]

    def _create(
        self,
        tmp_path: Path,
        *,
        from_description: Optional[str],
        invoker: Callable[[str], str],
        answers: Optional[list[str]] = None,
    ) -> None:
        from plan_tool.run_log import RunLogWriter

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        run_logger = RunLogWriter.start(
            repo_root=tmp_path,
            slug="demo",
            command="create",
            argv=["plan-tool", "create", "demo"],
        )
        create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=tmp_path / "m.json",
            from_description=from_description,
            input_fn=_queue_input(
                answers if answers is not None
                else _basic_metadata_answers()
            ),
            claude_invoker=invoker,
            run_logger=run_logger,
            allow_placeholder_body=True,
        )

    def test_interactive_path_skip_names_no_source(
        self, tmp_path: Path
    ) -> None:
        """No seed at all — there is nothing to synthesize *from*."""
        # Metadata, then one hand-entered step (title / complexity /
        # files / depends-on), then "add another?" -> no.
        answers = _basic_metadata_answers() + [
            "Only step", "", "", "", "n",
        ]
        self._create(
            tmp_path,
            from_description=None,
            invoker=_synthesis_invoker("{}", explode_on_synthesis=True),
            answers=answers,
        )
        end = self._body_phase_end(tmp_path, "demo")
        assert end["outcome"] == "skipped"
        assert end.get("skip_reason") == "no_source"

    def test_canonical_seed_skip_names_already_canonical(
        self, tmp_path: Path
    ) -> None:
        self._create(
            tmp_path,
            from_description=_CANONICAL_FULL_SEED,
            invoker=_synthesis_invoker("{}", explode_on_synthesis=True),
        )
        end = self._body_phase_end(tmp_path, "demo")
        assert end["outcome"] == "skipped"
        assert end.get("skip_reason") == "already_canonical"

    def test_all_null_synthesis_is_distinguishable_from_a_saved_call(
        self, tmp_path: Path
    ) -> None:
        """The one skip that means the call ran and produced nothing."""
        self._create(
            tmp_path,
            from_description=_FREE_FORM_SEED,
            invoker=_synthesis_invoker(
                {key: None for key in _BODY_CANONICAL_KEYS}
            ),
        )
        end = self._body_phase_end(tmp_path, "demo")
        assert end["outcome"] == "skipped"
        assert end.get("skip_reason") == "all_null_response"

    def test_successful_synthesis_carries_no_skip_reason(
        self, tmp_path: Path
    ) -> None:
        """A reason is emitted only on a skip — never as a null field."""
        self._create(
            tmp_path,
            from_description=_FREE_FORM_SEED,
            invoker=_synthesis_invoker(_default_body_payload()),
        )
        end = self._body_phase_end(tmp_path, "demo")
        assert end["outcome"] == "ok"
        assert "skip_reason" not in end


@pytest.mark.integration
class TestCreatePlanNoSynthesizeBodyFlag:
    """``--no-synthesize-body`` skips synthesis end-to-end via the CLI."""

    @pytest.fixture(autouse=True)
    def _disable_step3_todo_check(self) -> None:
        """Override the module-level disable: keep the fail-loud check
        live for the whole class so the free-form opt-out test exercises
        it. The canonical-seed tests in this class populate every body
        section via H2 extraction, so the gate has nothing to flag for
        them and they pass regardless.
        """

    def _run_via_cli(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        *,
        source_text: str,
        invoker: Callable[[str], str],
        extra_args: Optional[list[str]] = None,
        seed_body: Optional[str] = None,
    ) -> tuple[int, Path, Path, Path]:
        from plan_tool.cli import app as cli_module
        from plan_tool.cli import context as cli_context

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"
        source = tmp_path / "source.md"
        source.write_text(source_text, encoding="utf-8")

        original_create_plan = cli_module.create_plan
        answers = _basic_metadata_answers()

        def patched_create_plan(*args, **kwargs):
            kwargs.setdefault("input_fn", _queue_input(answers))
            kwargs["claude_invoker"] = invoker
            return original_create_plan(*args, **kwargs)

        monkeypatch.setattr("plan_tool.cli.authoring.create_plan", patched_create_plan)
        # ``_read_seed_body`` returns ``None`` for sources without
        # ``reformat`` provenance frontmatter. Tests that need a seed_body
        # injected (canonical-skip / H2-extraction assertions on the body)
        # patch it to return the controlled content directly — cleaner than
        # wiring up a canonical-with-provenance + sibling seed file.
        if seed_body is not None:
            monkeypatch.setattr(
                "plan_tool.cli.authoring._read_seed_body", lambda _p, _t: seed_body
            )
        monkeypatch.chdir(tmp_path)

        argv = [
            "--manifest", str(manifest),
            "create", "demo",
            "--from-existing", str(source),
            "--output-dir", str(out_dir),
            "--no-distill",
            "--no-iterate",
        ]
        if extra_args:
            argv.extend(extra_args)
        rc = cli_module.main(argv)
        return rc, tmp_path, out_dir, manifest

    def test_flag_skips_synthesis_round_trip_via_cli(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        prompts_seen: list[str] = []
        invoker = _synthesis_invoker(
            "{}",
            prompts_seen=prompts_seen,
            explode_on_synthesis=True,
        )

        rc, _, _, _ = self._run_via_cli(
            tmp_path,
            monkeypatch,
            source_text=_CANONICAL_FULL_SEED,
            invoker=invoker,
            extra_args=["--no-synthesize-body"],
            seed_body=_CANONICAL_FULL_SEED,
        )
        assert rc == 0
        # Synthesis prompt never seen.
        assert not any(_SYNTHESIS_PROMPT_MARKER in p for p in prompts_seen)

    def test_flag_emits_phase_skipped_with_skip_reason_annotation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        invoker = _synthesis_invoker(
            "{}", explode_on_synthesis=True
        )

        rc, repo, _, _ = self._run_via_cli(
            tmp_path,
            monkeypatch,
            source_text=_CANONICAL_FULL_SEED,
            invoker=invoker,
            extra_args=["--no-synthesize-body"],
            seed_body=_CANONICAL_FULL_SEED,
        )
        assert rc == 0

        log = _read_run_log(repo, "demo")
        body_phase_ends = [
            e for e in log
            if e["event"] == "phase_end"
            and e["phase"] == "propose_body_sections"
        ]
        assert len(body_phase_ends) == 1
        end_event = body_phase_ends[0]
        assert end_event["outcome"] == "skipped"
        # Direct file-backed sources skip body synthesis for source authority,
        # independently of the compatibility flag.
        assert end_event.get("skip_reason") == "source_authoritative"

    def test_flag_with_free_form_seed_trips_fail_loud_gate(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool.cli import context as cli_context

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"
        source = tmp_path / "source.md"
        source.write_text(_FREE_FORM_SEED, encoding="utf-8")

        invoker = _synthesis_invoker(
            "{}", explode_on_synthesis=True
        )

        original_create_plan = cli_module.create_plan

        def patched_create_plan(*args, **kwargs):
            kwargs.setdefault(
                "input_fn", _queue_input(_basic_metadata_answers())
            )
            kwargs["claude_invoker"] = invoker
            return original_create_plan(*args, **kwargs)

        monkeypatch.setattr("plan_tool.cli.authoring.create_plan", patched_create_plan)
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main([
            "--manifest", str(manifest),
            "create", "demo",
            "--from-existing", str(source),
            "--output-dir", str(out_dir),
            "--no-distill",
            "--no-iterate",
            "--no-synthesize-body",
        ])
        # File-backed preparation supplies the complete normalized body before
        # the opt-out can leave generic synthesis placeholders behind.
        assert rc == 0
        assert list(out_dir.glob("*-demo.md"))
        assert manifest.exists()

    def test_flag_with_canonical_seed_writes_plan_via_h2_extraction(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        invoker = _synthesis_invoker(
            "{}", explode_on_synthesis=True
        )

        rc, _, out_dir, _ = self._run_via_cli(
            tmp_path,
            monkeypatch,
            source_text=_CANONICAL_FULL_SEED,
            invoker=invoker,
            extra_args=["--no-synthesize-body"],
            seed_body=_CANONICAL_FULL_SEED,
        )
        assert rc == 0

        new_plan = next(p for p in out_dir.glob("*-demo.md"))
        body = new_plan.read_text(encoding="utf-8")
        # H2-extraction populated every canonical section.
        assert "Canonical overview body." in body
        assert "Canonical architecture body." in body
        assert "Canonical risk bullet." in body
        assert "Canonical deferred bullet." in body


@pytest.mark.integration
class TestCreatePlanBodySectionsCheckpointResume:
    """The ``create-body-sections`` checkpoint integrates with the
    existing two checkpoints in the create_plan write / hit / miss /
    discard cycle."""

    def test_propose_body_sections_writes_checkpoint_in_create_plan_run(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool import create as create_module

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        body_raw = json.dumps(_default_body_payload())
        invoker = _synthesis_invoker(body_raw)

        # Neutralize the success-tail checkpoint discard so the
        # body-sections file survives the run and the test can inspect
        # the on-disk payload. The discard semantics get their own
        # coverage in ``test_body_sections_checkpoint_discarded_on_success``.
        monkeypatch.setattr(
            create_module, "discard_checkpoint", lambda _p: False
        )

        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description=_FREE_FORM_SEED,
            seed_body=_FREE_FORM_SEED,
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=invoker,
        )

        assert result.plan_path.exists()
        ckpt_path_ = checkpoint_path(
            tmp_path, "demo", _BODY_SECTIONS_CHECKPOINT_NAME
        )
        assert ckpt_path_.exists()
        body = json.loads(ckpt_path_.read_text(encoding="utf-8"))
        assert body["payload"] == body_raw
        assert body["input_hash"] == _body_sections_input_hash(
            "demo", _FREE_FORM_SEED, out_dir, tmp_path
        )

    def test_body_sections_checkpoint_cache_hit_skips_invoker(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        # Pre-seed the body-sections checkpoint with a matching input hash
        # AND pre-seed the other two checkpoints so the invoker is never
        # called.
        cached_body = json.dumps(
            {**_default_body_payload(), "Overview": "cached-overview-marker"}
        )
        ckpt_body = checkpoint_path(
            tmp_path, "demo", _BODY_SECTIONS_CHECKPOINT_NAME
        )
        save_checkpoint(
            ckpt_body,
            Checkpoint(
                input_hash=_body_sections_input_hash(
                    "demo", _FREE_FORM_SEED, out_dir, tmp_path
                ),
                payload=cached_body,
                created_at=_now_iso(),
            ),
        )
        ckpt_steps = checkpoint_path(
            tmp_path, "demo", _INITIAL_STEPS_CHECKPOINT_NAME
        )
        save_checkpoint(
            ckpt_steps,
            Checkpoint(
                input_hash=_initial_steps_input_hash(
                    "demo", _FREE_FORM_SEED, out_dir, tmp_path
                ),
                payload=_STEP_JSON,
                created_at=_now_iso(),
            ),
        )
        ckpt_refs = checkpoint_path(
            tmp_path, "demo", _REFERENCES_CHECKPOINT_NAME
        )
        save_checkpoint(
            ckpt_refs,
            Checkpoint(
                input_hash=_references_input_hash(
                    "demo", "Demo Plan", _FREE_FORM_SEED, out_dir, tmp_path
                ),
                payload=_REF_JSON,
                created_at=_now_iso(),
            ),
        )

        def explode(prompt: str) -> str:
            raise AssertionError(
                "invoker must not be called when every checkpoint hits"
            )

        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description=_FREE_FORM_SEED,
            seed_body=_FREE_FORM_SEED,
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=explode,
        )

        body = result.plan_path.read_text(encoding="utf-8")
        assert "cached-overview-marker" in body

    def test_body_sections_checkpoint_miss_on_seed_change_re_invokes(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"

        # Pre-seed body-sections checkpoint with a STALE input hash (it
        # references a different seed text).
        ckpt_body = checkpoint_path(
            tmp_path, "demo", _BODY_SECTIONS_CHECKPOINT_NAME
        )
        stale_hash = _body_sections_input_hash(
            "demo", "old seed text", out_dir, tmp_path
        )
        save_checkpoint(
            ckpt_body,
            Checkpoint(
                input_hash=stale_hash,
                payload=json.dumps(_default_body_payload()),
                created_at=_now_iso(),
            ),
        )

        synth_attempts = {"n": 0}
        fresh_payload = {
            **_default_body_payload(),
            "Overview": "fresh-overview-marker",
        }
        fresh_raw = json.dumps(fresh_payload)

        def invoker(prompt: str) -> str:
            if _SYNTHESIS_PROMPT_MARKER in prompt:
                synth_attempts["n"] += 1
                return fresh_raw
            if "developer and API reference documentation" in prompt:
                return _REF_JSON
            return _STEP_JSON

        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description=_FREE_FORM_SEED,
            seed_body=_FREE_FORM_SEED,
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=invoker,
        )

        # Synthesis prompt fired exactly once — stale hash invalidated the
        # cached payload.
        assert synth_attempts["n"] == 1
        body = result.plan_path.read_text(encoding="utf-8")
        assert "fresh-overview-marker" in body

    def test_body_sections_checkpoint_discarded_on_success(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool.cli import context as cli_context

        repo, out_dir, manifest = _seed_repo_for_cmd_create(tmp_path)
        source = tmp_path / "source.md"
        source.write_text(_FREE_FORM_SEED, encoding="utf-8")

        body_raw = json.dumps(_default_body_payload())
        invoker = _synthesis_invoker(body_raw)

        original_create_plan = cli_module.create_plan

        def patched_create_plan(*args, **kwargs):
            kwargs.setdefault(
                "input_fn", _queue_input(_basic_metadata_answers())
            )
            kwargs["claude_invoker"] = invoker
            return original_create_plan(*args, **kwargs)

        monkeypatch.setattr("plan_tool.cli.authoring.create_plan", patched_create_plan)
        monkeypatch.chdir(repo)

        rc = cli_module.main([
            "--manifest", str(manifest),
            "create", "demo",
            "--from-existing", str(source),
            "--output-dir", str(out_dir),
            "--no-distill",
            "--no-iterate",
        ])
        assert rc == 0

        log = _read_run_log(repo, "demo")
        discards = [
            e for e in log
            if e["event"] == "checkpoint_discard" and e["reason"] == "success"
        ]
        names = {e["name"] for e in discards}
        # Normalized preparation bypasses body synthesis, so only the stages
        # that ran leave checkpoints to discard.
        assert _INITIAL_STEPS_CHECKPOINT_NAME in names
        assert _REFERENCES_CHECKPOINT_NAME in names
        assert _BODY_SECTIONS_CHECKPOINT_NAME not in names


# --- Step 3: per-step change-type review gate -----------------------------

from plan_tool.checkpoint import checkpoint_dir  # noqa: E402
from plan_tool.create import (  # noqa: E402
    _SPLIT,
    _STEP_REVIEW_CHECKPOINT_NAME,
    _apply_step_merge,
    _apply_step_split,
    _ask_change_type,
    _format_depends_on_review_lines,
    _granularity_split_hints,
    _propose_step_split,
    _review_step_change_types,
    _silent_input_fn,
    _step_review_input_hash,
)
from plan_tool.telemetry import code_fingerprint_digest, read_decisions  # noqa: E402


def _appending_invoker(payload: str) -> Callable[[str], str]:
    """Fake claude that records prompts and returns a fixed payload."""
    seen: list[str] = []

    def fake(prompt: str) -> str:
        seen.append(prompt)
        return payload

    fake.seen = seen  # type: ignore[attr-defined]
    return fake


_SPLIT_PAIR_JSON = json.dumps(
    [
        {"title": "characterize", "change_type": "refactor", "files": [], "creates": []},
        {"title": "add behavior", "change_type": "feature", "files": [], "creates": []},
    ]
)

_CONCEPT_A = "a" * 64
_CONCEPT_B = "b" * 64
_CONCEPT_C = "c" * 64


def test_parse_steps_json_preserves_concept_ids() -> None:
    steps = _parse_steps_json(
        json.dumps([{"title": "Owned", "concept_ids": [_CONCEPT_A]}])
    )
    assert steps is not None
    assert steps[0].concept_ids == [_CONCEPT_A]


@pytest.mark.parametrize(
    "concept_ids",
    ["not-a-list", [123], ["not-a-valid-id"], [_CONCEPT_A, _CONCEPT_A]],
)
def test_parse_steps_json_rejects_malformed_concept_ids(concept_ids) -> None:
    assert _parse_steps_json(
        json.dumps([{"title": "Owned", "concept_ids": concept_ids}])
    ) is None


class TestGranularitySplitHints:
    def test_split_hints_filters_to_split_source(self) -> None:
        # Step 1's title trips a split detector; steps 2 & 3 share an identical
        # non-empty file set (a merge smell). Only the split step is keyed.
        steps = [
            Step(id=1, title="Refactor parser and add validation"),
            Step(id=2, title="touch x", files=["x.py"]),
            Step(id=3, title="touch x again", files=["x.py"], depends_on=[2]),
        ]
        hints = _granularity_split_hints(steps)
        assert set(hints) == {1}
        assert hints[1] and all(isinstance(line, str) for line in hints[1])

    def test_split_hints_empty_on_unbuildable_graph(self) -> None:
        # depends_on points at an id that cannot resolve → Plan(...) rejects it,
        # and the best-effort guard yields {} rather than raising.
        steps = [Step(id=1, title="x", depends_on=[99])]
        assert _granularity_split_hints(steps) == {}

    def test_split_hints_passes_invoker_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, object] = {}

        def fake_assess(plan, **kwargs):
            captured.update(kwargs)
            return []

        monkeypatch.setattr("plan_tool.create.assess_granularity", fake_assess)
        _granularity_split_hints([Step(id=1, title="x")])
        assert captured["stage"] == "create"
        assert captured["invoker"] is None

    def test_split_hints_render_stored_confidence(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.review import Recommendation

        rec = Recommendation(
            id="split", source="granularity-split", severity="medium",
            step_id=1, title="Split the step", body="Separate concerns.",
            suggested_action="plan-tool split demo --step 1", confidence=None,
        )
        monkeypatch.setattr("plan_tool.create.assess_granularity", lambda *a, **k: [rec])

        assert _granularity_split_hints([Step(id=1, title="mixed")]) == {
            1: ["confidence: unknown — plan-tool split demo --step 1"]
        }


class TestFormatDependsOnReviewLines:
    def test_formatter_emits_nothing_when_depends_on_empty(self) -> None:
        step = Step(id=2, title="tail", depends_on=[])
        assert _format_depends_on_review_lines(step, {1: Step(id=1, title="head")}) == []

    def test_formatter_emits_id_without_note(self) -> None:
        steps_by_id = {1: Step(id=1, title="setup")}
        step = Step(id=2, title="tail", depends_on=[1])
        lines = _format_depends_on_review_lines(step, steps_by_id)
        assert lines == ["depends_on 1 (setup)"]

    def test_formatter_emits_id_with_note(self) -> None:
        steps_by_id = {1: Step(id=1, title="setup")}
        step = Step(
            id=2,
            title="tail",
            depends_on=[1],
            depends_on_notes={1: "consumes schema"},
        )
        lines = _format_depends_on_review_lines(step, steps_by_id)
        assert lines == ["depends_on 1 (setup): consumes schema"]

    def test_formatter_treats_empty_string_as_silent(self) -> None:
        steps_by_id = {1: Step(id=1, title="setup")}
        step = Step(
            id=2,
            title="tail",
            depends_on=[1],
            depends_on_notes={1: ""},
        )
        lines = _format_depends_on_review_lines(step, steps_by_id)
        assert lines == ["depends_on 1 (setup)"]

    def test_formatter_partial_coverage(self) -> None:
        steps_by_id = {
            1: Step(id=1, title="first"),
            2: Step(id=2, title="second"),
        }
        step = Step(
            id=3,
            title="tail",
            depends_on=[1, 2],
            depends_on_notes={1: "from first"},
        )
        lines = _format_depends_on_review_lines(step, steps_by_id)
        assert lines == [
            "depends_on 1 (first): from first",
            "depends_on 2 (second)",
        ]

    def test_formatter_preserves_depends_on_order(self) -> None:
        steps_by_id = {
            1: Step(id=1, title="first"),
            2: Step(id=2, title="second"),
        }
        step = Step(id=3, title="tail", depends_on=[2, 1])
        lines = _format_depends_on_review_lines(step, steps_by_id)
        assert lines == [
            "depends_on 2 (second)",
            "depends_on 1 (first)",
        ]

    def test_formatter_omits_title_when_antecedent_missing(self) -> None:
        step = Step(
            id=2,
            title="tail",
            depends_on=[99],
            depends_on_notes={99: "orphan note"},
        )
        lines = _format_depends_on_review_lines(step, {})
        assert lines == ["depends_on 99: orphan note"]


class TestAskChangeType:
    def test_enter_accepts_proposal(self) -> None:
        out = _ask_change_type(
            _queue_input([""]),
            step=Step(id=1, title="x"),
            proposed=ChangeType.REFACTOR,
            rationale=None,
            can_split=True,
        )
        assert out is ChangeType.REFACTOR

    def test_enter_leaves_none_when_unproposed(self) -> None:
        out = _ask_change_type(
            _queue_input([""]),
            step=Step(id=1, title="x"),
            proposed=None,
            rationale=None,
            can_split=True,
        )
        assert out is None

    def test_override_letters(self) -> None:
        step = Step(id=1, title="x")
        got = [
            _ask_change_type(
                _queue_input([letter]),
                step=step,
                proposed=ChangeType.NON_CODE,
                rationale=None,
                can_split=True,
            )
            for letter in ("r", "f", "n")
        ]
        assert got == [ChangeType.REFACTOR, ChangeType.FEATURE, ChangeType.NON_CODE]

    def test_split_sentinel_when_can_split(self) -> None:
        out = _ask_change_type(
            _queue_input(["s"]),
            step=Step(id=1, title="x"),
            proposed=None,
            rationale=None,
            can_split=True,
        )
        assert out is _SPLIT

    def test_split_rejected_when_cannot_split(self) -> None:
        # ``s`` is refused (no invoker), then ``r`` resolves the prompt.
        out = _ask_change_type(
            _queue_input(["s", "r"]),
            step=Step(id=1, title="x"),
            proposed=None,
            rationale=None,
            can_split=False,
        )
        assert out is ChangeType.REFACTOR

    def test_invalid_answer_reprompts(self) -> None:
        out = _ask_change_type(
            _queue_input(["zzz", "f"]),
            step=Step(id=1, title="x"),
            proposed=None,
            rationale=None,
            can_split=True,
        )
        assert out is ChangeType.FEATURE

    def test_granularity_hint_printed(self, capsys: pytest.CaptureFixture) -> None:
        _ask_change_type(
            _queue_input([""]),
            step=Step(id=1, title="x"),
            proposed=None,
            rationale=None,
            can_split=True,
            granularity_hint=["consider splitting step 1"],
        )
        assert "granularity: consider splitting step 1" in capsys.readouterr().out

    def test_no_granularity_hint_when_absent(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        _ask_change_type(
            _queue_input([""]),
            step=Step(id=1, title="x"),
            proposed=None,
            rationale=None,
            can_split=True,
        )
        assert "granularity:" not in capsys.readouterr().out

    def test_ask_change_type_prints_depends_on_and_note(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        all_steps = [
            Step(id=1, title="setup"),
            Step(
                id=2,
                title="tail",
                depends_on=[1],
                depends_on_notes={1: "consumes schema"},
            ),
        ]
        _ask_change_type(
            _queue_input([""]),
            step=all_steps[1],
            proposed=None,
            rationale=None,
            can_split=True,
            all_steps=all_steps,
        )
        out = capsys.readouterr().out
        assert "depends_on 1 (setup): consumes schema" in out

    def test_ask_change_type_prints_depends_on_without_note(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        all_steps = [
            Step(id=1, title="setup"),
            Step(id=2, title="tail", depends_on=[1]),
        ]
        _ask_change_type(
            _queue_input([""]),
            step=all_steps[1],
            proposed=None,
            rationale=None,
            can_split=True,
            all_steps=all_steps,
        )
        out = capsys.readouterr().out
        assert "depends_on 1 (setup)" in out
        assert ": " not in out.split("depends_on 1 (setup)")[1].split("\n")[0]

    def test_ask_change_type_omits_depends_on_when_empty(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        all_steps = [Step(id=1, title="solo")]
        _ask_change_type(
            _queue_input([""]),
            step=all_steps[0],
            proposed=None,
            rationale=None,
            can_split=True,
            all_steps=all_steps,
        )
        assert "depends_on" not in capsys.readouterr().out

    def test_ask_change_type_omits_depends_on_when_all_steps_not_passed(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        step = Step(
            id=2,
            title="tail",
            depends_on=[1],
            depends_on_notes={1: "hidden without lookup"},
        )
        _ask_change_type(
            _queue_input([""]),
            step=step,
            proposed=None,
            rationale=None,
            can_split=True,
        )
        assert "depends_on" not in capsys.readouterr().out


class TestApplyStepSplit:
    def _mixed_list(self) -> list[Step]:
        # step 2 is the split target; step 3 depends on it.
        return [
            Step(id=1, title="setup"),
            Step(id=2, title="mixed", depends_on=[1]),
            Step(id=3, title="after", depends_on=[2]),
        ]

    def _replacements(self) -> list[Step]:
        return [
            Step(id=1, title="refactor half", change_type=ChangeType.REFACTOR),
            Step(id=2, title="feature half", change_type=ChangeType.FEATURE),
        ]

    def test_first_replacement_inherits_depends_on(self) -> None:
        out = _apply_step_split(self._mixed_list(), 2, self._replacements())
        refactor = out[1]
        assert refactor.title == "refactor half"
        assert refactor.depends_on == [1]  # inherited from the target

    def test_feature_depends_on_refactor(self) -> None:
        out = _apply_step_split(self._mixed_list(), 2, self._replacements())
        feature = out[2]
        assert feature.title == "feature half"
        assert feature.depends_on == [out[1].id]

    def test_inbound_edges_redirect_to_terminal(self) -> None:
        out = _apply_step_split(self._mixed_list(), 2, self._replacements())
        after = next(s for s in out if s.title == "after")
        feature = next(s for s in out if s.title == "feature half")
        assert after.depends_on == [feature.id]  # repointed from the target

    def test_downstream_ids_shift_by_one(self) -> None:
        out = _apply_step_split(self._mixed_list(), 2, self._replacements())
        assert [s.id for s in out] == [1, 2, 3, 4]  # contiguous 1..N
        assert [s.title for s in out] == [
            "setup",
            "refactor half",
            "feature half",
            "after",
        ]

    def test_first_replacement_inherits_target_status(self) -> None:
        # Splitting the `current` step keeps exactly one current step: the
        # first half inherits the target's status, later halves are pending.
        steps = [
            Step(id=1, title="setup", status=StepStatus.DONE),
            Step(id=2, title="mixed", depends_on=[1], status=StepStatus.CURRENT),
            Step(id=3, title="after", depends_on=[2]),
        ]
        out = _apply_step_split(steps, 2, self._replacements())
        assert out[1].status == StepStatus.CURRENT  # first half
        assert out[2].status == StepStatus.PENDING  # second half
        assert [s.id for s in out if s.status == StepStatus.CURRENT] == [2]

    def test_pending_target_yields_all_pending_halves(self) -> None:
        out = _apply_step_split(self._mixed_list(), 2, self._replacements())
        assert out[1].status == StepStatus.PENDING
        assert out[2].status == StepStatus.PENDING

    def test_invalid_split_graph_raises_summary(self) -> None:
        # A sibling step references an unknown id; after the splice the
        # graph is still invalid, so ``Plan(...)`` rejects it.
        bad = [
            Step(id=1, title="mixed"),
            Step(id=2, title="dangling", depends_on=[99]),
        ]
        with pytest.raises(CreateError) as exc:
            _apply_step_split(bad, 1, self._replacements())
        assert "unknown id" in str(exc.value)
        # The input list is never mutated.
        assert bad[1].depends_on == [99]

    def test_redistributes_all_concept_ids(self) -> None:
        steps = self._mixed_list()
        steps[1] = steps[1].model_copy(
            update={"concept_ids": [_CONCEPT_A, _CONCEPT_B]}
        )
        replacements = self._replacements()
        replacements[0] = replacements[0].model_copy(
            update={"concept_ids": [_CONCEPT_A]}
        )
        replacements[1] = replacements[1].model_copy(
            update={"concept_ids": [_CONCEPT_B]}
        )
        out = _apply_step_split(steps, 2, replacements)
        assert [s.concept_ids for s in out[1:3]] == [[_CONCEPT_A], [_CONCEPT_B]]

    def test_allows_repeated_cross_half_ownership(self) -> None:
        steps = self._mixed_list()
        steps[1] = steps[1].model_copy(update={"concept_ids": [_CONCEPT_A]})
        replacements = [
            replacement.model_copy(update={"concept_ids": [_CONCEPT_A]})
            for replacement in self._replacements()
        ]
        out = _apply_step_split(steps, 2, replacements)
        assert [s.concept_ids for s in out[1:3]] == [[_CONCEPT_A], [_CONCEPT_A]]

    def test_rejects_dropped_concept_id_without_mutating_input(self) -> None:
        steps = self._mixed_list()
        steps[1] = steps[1].model_copy(
            update={"concept_ids": [_CONCEPT_A, _CONCEPT_B]}
        )
        before = copy.deepcopy(steps)
        replacements = self._replacements()
        replacements[0] = replacements[0].model_copy(
            update={"concept_ids": [_CONCEPT_A]}
        )
        with pytest.raises(CreateError, match="dropped concept_ids"):
            _apply_step_split(steps, 2, replacements)
        assert steps == before

    def test_rejects_invented_concept_id(self) -> None:
        steps = self._mixed_list()
        steps[1] = steps[1].model_copy(update={"concept_ids": [_CONCEPT_A]})
        replacements = self._replacements()
        replacements[0] = replacements[0].model_copy(
            update={"concept_ids": [_CONCEPT_A, _CONCEPT_C]}
        )
        with pytest.raises(CreateError, match="invented concept_ids"):
            _apply_step_split(steps, 2, replacements)

    def test_empty_ownership_requires_empty_replacements(self) -> None:
        replacements = self._replacements()
        replacements[0] = replacements[0].model_copy(
            update={"concept_ids": [_CONCEPT_A]}
        )
        with pytest.raises(CreateError, match="invented concept_ids"):
            _apply_step_split(self._mixed_list(), 2, replacements)

    def test_split_clears_note_on_repointed_inbound_edge(self) -> None:
        steps = [
            Step(id=1, title="setup"),
            Step(id=2, title="mixed", depends_on=[1]),
            Step(
                id=3,
                title="after",
                depends_on=[2],
                depends_on_notes={2: "consumes mixed"},
            ),
        ]
        out = _apply_step_split(steps, 2, self._replacements())
        after = next(s for s in out if s.title == "after")
        feature = next(s for s in out if s.title == "feature half")
        assert after.depends_on == [feature.id]
        assert after.depends_on_notes == {}

    def test_split_does_not_copy_target_notes_to_replacements(self) -> None:
        steps = self._mixed_list()
        steps[1] = steps[1].model_copy(
            update={"depends_on_notes": {1: "target outbound note"}}
        )
        out = _apply_step_split(steps, 2, self._replacements())
        for half in out[1:3]:
            assert half.depends_on_notes == {}

    def test_split_clears_notes_on_parsed_replacements(self) -> None:
        replacements = [
            r.model_copy(update={"depends_on_notes": {1: "proposer note"}})
            for r in self._replacements()
        ]
        out = _apply_step_split(self._mixed_list(), 2, replacements)
        assert out[1].depends_on_notes == {}
        assert out[2].depends_on_notes == {}

    def test_split_remaps_note_keys_for_untouched_downstream(self) -> None:
        steps = [
            Step(id=1, title="setup"),
            Step(id=2, title="mixed", depends_on=[1]),
            Step(id=3, title="mid", depends_on=[1], depends_on_notes={1: "keep"}),
            Step(id=4, title="tail", depends_on=[3], depends_on_notes={3: "shift"}),
        ]
        out = _apply_step_split(steps, 2, self._replacements())
        mid = next(s for s in out if s.title == "mid")
        tail = next(s for s in out if s.title == "tail")
        assert mid.depends_on_notes == {1: "keep"}
        assert tail.depends_on_notes == {mid.id: "shift"}

    def test_split_with_notes_produces_valid_graph(self) -> None:
        steps = [
            Step(id=1, title="setup"),
            Step(
                id=2,
                title="mixed",
                depends_on=[1],
                depends_on_notes={1: "outbound"},
            ),
            Step(
                id=3,
                title="after",
                depends_on=[2],
                depends_on_notes={2: "inbound"},
            ),
        ]
        out = _apply_step_split(steps, 2, self._replacements())
        for step in out:
            assert set(step.depends_on_notes) <= set(step.depends_on)


def test_propose_step_split_prompt_forbids_depends_on_notes() -> None:
    step = Step(id=1, title="Mixed", concept_ids=[_CONCEPT_A, _CONCEPT_B])
    invoker = _appending_invoker(_SPLIT_PAIR_JSON)
    _propose_step_split(step, invoker)
    assert invoker.seen  # type: ignore[attr-defined]
    assert "`depends_on_notes`" in invoker.seen[0]  # type: ignore[attr-defined]


def test_propose_step_split_rejects_nonconserving_distribution() -> None:
    step = Step(id=1, title="Mixed", concept_ids=[_CONCEPT_A, _CONCEPT_B])
    response = json.dumps(
        [
            {"title": "Refactor", "concept_ids": [_CONCEPT_A]},
            {"title": "Feature", "concept_ids": []},
        ]
    )
    assert _propose_step_split(step, lambda _prompt: response) is None


def test_propose_step_split_replacements_carry_no_intent() -> None:
    """Fixture omits ``intent``; halves default to None (never copy the target)."""
    step = Step(
        id=1,
        title="Mixed",
        intent="make the mixed step work",
        concept_ids=[_CONCEPT_A, _CONCEPT_B],
    )
    response = json.dumps(
        [
            {
                "title": "Refactor",
                "change_type": "refactor",
                "files": [],
                "creates": [],
                "concept_ids": [_CONCEPT_A],
            },
            {
                "title": "Feature",
                "change_type": "feature",
                "files": [],
                "creates": [],
                "concept_ids": [_CONCEPT_B],
            },
        ]
    )
    halves = _propose_step_split(step, lambda _prompt: response)
    assert halves is not None
    assert len(halves) == 2
    assert halves[0].intent is None
    assert halves[1].intent is None


def test_review_split_preserves_concept_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    response = json.dumps(
        [
            {
                "title": "Refactor",
                "change_type": "refactor",
                "concept_ids": [_CONCEPT_A],
            },
            {
                "title": "Feature",
                "change_type": "feature",
                "concept_ids": [_CONCEPT_B],
            },
        ]
    )
    reviewed = _review_step_change_types(
        [
            Step(
                id=1,
                title="Refactor parser and add validation",
                concept_ids=[_CONCEPT_A, _CONCEPT_B],
            )
        ],
        input_fn=_queue_input(["s", "", ""]),
        invoker=lambda _prompt: response,
        resume=False,
    )
    assert [step.concept_ids for step in reviewed] == [
        [_CONCEPT_A],
        [_CONCEPT_B],
    ]


class TestApplyStepMerge:
    def _chain(self, n: int) -> list[Step]:
        # A contiguous chain: step k depends on step k-1.
        return [
            Step(id=i, title=f"s{i}", depends_on=[i - 1] if i > 1 else [])
            for i in range(1, n + 1)
        ]

    def _merged(self, **kw) -> Step:
        # The caller-assembled combined step; id/depends_on are placeholders
        # the transform overwrites.
        defaults = dict(id=99, title="combined")
        defaults.update(kw)
        return Step(**defaults)

    def test_folds_contiguous_chain_to_one(self) -> None:
        out = _apply_step_merge(self._chain(4), [2, 3], self._merged())
        assert [s.id for s in out] == [1, 2, 3]
        assert out[1].title == "combined"  # merged step at survivor (id 2)

    def test_renumbers_downstream_ids_down_by_eliminated(self) -> None:
        out = _apply_step_merge(self._chain(4), [2, 3], self._merged())
        # Old step 4 (after a 2-id region) shifts down by len(set)-1 == 1.
        after = next(s for s in out if s.title == "s4")
        assert after.id == 3

    def test_merged_depends_on_is_external_union_internal_dropped(self) -> None:
        out = _apply_step_merge(self._chain(4), [2, 3], self._merged())
        merged = out[1]
        # Member 2's external dep is step 1; the 2->? internal edge (3 dep 2)
        # is dropped. So merged depends only on 1.
        assert merged.depends_on == [1]

    def test_dependent_repoints_to_merged_id(self) -> None:
        out = _apply_step_merge(self._chain(4), [2, 3], self._merged())
        # Old step 4 depended on member 3; now depends on the merged id (2).
        after = next(s for s in out if s.title == "s4")
        assert after.depends_on == [2]

    def test_collapsed_dependent_edges_deduped(self) -> None:
        steps = [
            Step(id=1, title="s1"),
            Step(id=2, title="s2", depends_on=[1]),
            Step(id=3, title="s3", depends_on=[2]),
            Step(id=4, title="s4", depends_on=[2, 3]),  # depends on BOTH members
        ]
        out = _apply_step_merge(steps, [2, 3], self._merged())
        after = next(s for s in out if s.title == "s4")
        assert after.depends_on == [2]  # both edges collapse to one, deduped

    def test_accepts_legal_reverse_intra_set_edge(self) -> None:
        # Lower-id member 2 depends on higher-id member 3 (reverse edge);
        # undirected-connected, so the set folds legally.
        steps = [
            Step(id=1, title="s1"),
            Step(id=2, title="s2", depends_on=[1, 3]),
            Step(id=3, title="s3"),
        ]
        out = _apply_step_merge(steps, [2, 3], self._merged())
        assert [s.id for s in out] == [1, 2]
        assert out[1].depends_on == [1]  # external dep kept, internal dropped

    def test_inherits_merged_step_content(self) -> None:
        merged = self._merged(
            title="big step",
            files=["a.py", "b.py"],
            creates=["c.py"],
            change_type=ChangeType.FEATURE,
        )
        out = _apply_step_merge(self._chain(4), [2, 3], merged)
        got = out[1]
        assert got.title == "big step"
        assert got.files == ["a.py", "b.py"]
        assert got.creates == ["c.py"]
        assert got.change_type is ChangeType.FEATURE

    def test_unions_member_concept_ids(self) -> None:
        steps = self._chain(4)
        steps[1] = steps[1].model_copy(update={"concept_ids": [_CONCEPT_A]})
        steps[2] = steps[2].model_copy(update={"concept_ids": [_CONCEPT_B]})

        out = _apply_step_merge(steps, [2, 3], self._merged())

        assert out[1].concept_ids == [_CONCEPT_A, _CONCEPT_B]

    def test_deduplicates_overlapping_concept_ids_in_first_seen_order(self) -> None:
        steps = self._chain(4)
        steps[1] = steps[1].model_copy(
            update={"concept_ids": [_CONCEPT_B, _CONCEPT_A]}
        )
        steps[2] = steps[2].model_copy(
            update={"concept_ids": [_CONCEPT_A, _CONCEPT_C]}
        )

        out = _apply_step_merge(steps, [2, 3], self._merged())

        assert out[1].concept_ids == [_CONCEPT_B, _CONCEPT_A, _CONCEPT_C]

    def test_empty_member_ownership_produces_empty_union(self) -> None:
        out = _apply_step_merge(self._chain(4), [2, 3], self._merged())

        assert out[1].concept_ids == []

    def test_ignores_concept_ids_supplied_only_by_merged_placeholder(self) -> None:
        out = _apply_step_merge(
            self._chain(4),
            [2, 3],
            self._merged(concept_ids=[_CONCEPT_C]),
        )

        assert out[1].concept_ids == []

    def test_concept_union_does_not_mutate_inputs(self) -> None:
        steps = self._chain(4)
        steps[1] = steps[1].model_copy(update={"concept_ids": [_CONCEPT_A]})
        steps[2] = steps[2].model_copy(
            update={"concept_ids": [_CONCEPT_A, _CONCEPT_B]}
        )
        merged = self._merged(concept_ids=[_CONCEPT_C])
        before_steps = copy.deepcopy(steps)
        before_merged = copy.deepcopy(merged)

        _apply_step_merge(steps, [2, 3], merged)

        assert steps == before_steps
        assert merged == before_merged

    def test_survivor_pending_when_no_member_current(self) -> None:
        # All-PENDING members → survivor PENDING (the transform owns status;
        # the caller-built ``merged`` status is ignored).
        merged = self._merged(status=StepStatus.CURRENT)
        out = _apply_step_merge(self._chain(4), [2, 3], merged)
        assert out[1].status is StepStatus.PENDING

    def test_survivor_inherits_current_from_member(self) -> None:
        # A current member → survivor current, keeping exactly one current step
        # so the merged plan stays runnable (the merge analog of split's
        # first-half status inheritance).
        steps = self._chain(4)
        steps[1] = steps[1].model_copy(update={"status": StepStatus.CURRENT})
        out = _apply_step_merge(steps, [2, 3], self._merged())
        assert out[1].status is StepStatus.CURRENT
        assert [s.status for s in out].count(StepStatus.CURRENT) == 1

    def test_rejects_fewer_than_two_ids(self) -> None:
        with pytest.raises(CreateError, match="at least two"):
            _apply_step_merge(self._chain(4), [2], self._merged())

    def test_rejects_unknown_id(self) -> None:
        with pytest.raises(CreateError, match="not found"):
            _apply_step_merge(self._chain(4), [2, 99], self._merged())

    def test_rejects_non_contiguous_set(self) -> None:
        steps = self._chain(4)
        with pytest.raises(CreateError, match="contiguous"):
            _apply_step_merge(steps, [2, 4], self._merged())
        # input untouched
        assert [s.id for s in steps] == [1, 2, 3, 4]

    def test_rejects_fork_join_disjoint_set(self) -> None:
        # Members 2 and 3 are contiguous but share no member-to-member edge
        # (both depend only on non-member 1) — disjoint.
        steps = [
            Step(id=1, title="s1"),
            Step(id=2, title="s2", depends_on=[1]),
            Step(id=3, title="s3", depends_on=[1]),
        ]
        with pytest.raises(CreateError, match="disjoint"):
            _apply_step_merge(steps, [2, 3], self._merged())

    def test_raises_on_cycle_via_dry_run(self) -> None:
        # External step 4 depends on member 2; member 3 depends on step 4.
        # Folding {2,3} makes merged->4 and 4->merged: a cycle.
        steps = [
            Step(id=1, title="s1"),
            Step(id=2, title="s2", depends_on=[1]),
            Step(id=3, title="s3", depends_on=[2, 4]),
            Step(id=4, title="s4", depends_on=[2]),
        ]
        with pytest.raises(CreateError, match="invalid step graph"):
            _apply_step_merge(steps, [2, 3], self._merged())

    def test_never_emits_self_loop(self) -> None:
        out = _apply_step_merge(self._chain(4), [2, 3], self._merged())
        merged = out[1]
        assert merged.id not in merged.depends_on

    def test_does_not_mutate_input_on_success(self) -> None:
        steps = self._chain(4)
        merged = self._merged(files=["x.py"])
        before_steps = copy.deepcopy(steps)
        before_merged = copy.deepcopy(merged)
        _apply_step_merge(steps, [2, 3], merged)
        assert steps == before_steps
        assert merged == before_merged

    def test_does_not_mutate_input_on_error(self) -> None:
        steps = self._chain(4)
        before = copy.deepcopy(steps)
        with pytest.raises(CreateError):
            _apply_step_merge(steps, [2, 4], self._merged())  # non-contiguous
        assert steps == before

    def test_merge_outbound_keeps_note_when_unanimous(self) -> None:
        steps = self._chain(4)
        steps[1] = steps[1].model_copy(
            update={"depends_on_notes": {1: "same"}}
        )
        steps[2] = steps[2].model_copy(
            update={"depends_on_notes": {1: "same"}}
        )
        out = _apply_step_merge(steps, [2, 3], self._merged())
        assert out[1].depends_on_notes == {1: "same"}

    def test_merge_outbound_keeps_note_when_only_one_member_has_edge(self) -> None:
        steps = self._chain(4)
        steps[1] = steps[1].model_copy(
            update={"depends_on_notes": {1: "only voter"}}
        )
        out = _apply_step_merge(steps, [2, 3], self._merged())
        assert out[1].depends_on_notes == {1: "only voter"}

    def test_merge_outbound_clears_note_when_text_differs(self) -> None:
        steps = self._chain(4)
        steps[1] = steps[1].model_copy(update={"depends_on_notes": {1: "a"}})
        steps[2] = steps[2].model_copy(
            update={"depends_on": [1, 2], "depends_on_notes": {1: "b"}}
        )
        out = _apply_step_merge(steps, [2, 3], self._merged())
        assert 1 not in out[1].depends_on_notes

    def test_merge_inbound_clears_note_when_collapsed_edges_disagree(self) -> None:
        steps = [
            Step(id=1, title="s1"),
            Step(id=2, title="s2", depends_on=[1]),
            Step(id=3, title="s3", depends_on=[2]),
            Step(
                id=4,
                title="s4",
                depends_on=[2, 3],
                depends_on_notes={2: "a", 3: "b"},
            ),
        ]
        out = _apply_step_merge(steps, [2, 3], self._merged())
        after = next(s for s in out if s.title == "s4")
        assert after.depends_on == [2]
        assert after.depends_on_notes == {}

    def test_merge_inbound_keeps_note_when_collapsed_edges_agree(self) -> None:
        steps = [
            Step(id=1, title="s1"),
            Step(id=2, title="s2", depends_on=[1]),
            Step(id=3, title="s3", depends_on=[2]),
            Step(
                id=4,
                title="s4",
                depends_on=[2, 3],
                depends_on_notes={2: "same", 3: "same"},
            ),
        ]
        out = _apply_step_merge(steps, [2, 3], self._merged())
        after = next(s for s in out if s.title == "s4")
        assert after.depends_on_notes == {2: "same"}

    def test_merge_with_notes_produces_valid_graph(self) -> None:
        steps = self._chain(4)
        steps[1] = steps[1].model_copy(
            update={"depends_on_notes": {1: "member note"}}
        )
        steps[3] = steps[3].model_copy(
            update={"depends_on_notes": {3: "downstream note"}}
        )
        out = _apply_step_merge(steps, [2, 3], self._merged())
        for step in out:
            assert set(step.depends_on_notes) <= set(step.depends_on)

    def test_merge_stale_note_key_raises_create_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool import create as create_mod

        real = create_mod._collapse_inbound_depends_on_notes

        def _inject_stale(step, renumber, new_depends_on):
            result = real(step, renumber, new_depends_on)
            result[99] = "stale"
            return result

        monkeypatch.setattr(
            create_mod, "_collapse_inbound_depends_on_notes", _inject_stale
        )
        with pytest.raises(CreateError) as exc:
            _apply_step_merge(self._chain(4), [2, 3], self._merged())
        assert "depends_on_notes" in str(exc.value)


class TestStepReviewLoop:
    def test_split_then_review_expands_list(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        steps = [
            Step(id=1, title="mixed"),
            Step(id=2, title="after", depends_on=[1]),
        ]
        invoker = _appending_invoker(_SPLIT_PAIR_JSON)
        # "s" splits step 1; the two halves + the downstream step are then
        # each accepted with Enter.
        reviewed = _review_step_change_types(
            steps,
            input_fn=_queue_input(["s", "", "", ""]),
            invoker=invoker,
            resume=False,
        )
        assert [s.title for s in reviewed] == [
            "characterize",
            "add behavior",
            "after",
        ]
        assert reviewed[0].change_type is ChangeType.REFACTOR
        assert reviewed[1].change_type is ChangeType.FEATURE
        assert reviewed[0].depends_on == []
        assert reviewed[1].depends_on == [1]
        assert reviewed[2].depends_on == [2]  # repointed to the feature half
        assert len(invoker.seen) == 1  # one decompose round-trip

    def test_manual_step_unclassified_then_reviewed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.create import _prompt_one_step

        # _prompt_one_step asks title / complexity / files / depends_on —
        # and NO change-type question. Exactly four answers; a fifth prompt
        # would exhaust the queue and raise.
        manual = _prompt_one_step(
            _queue_input(["Manual step", "", "", ""]), 1, set()
        )
        assert manual.change_type is None

        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        prompts: list[str] = []

        def record(prompt: str) -> str:
            prompts.append(prompt)
            return ""

        reviewed = _review_step_change_types(
            [manual], input_fn=record, invoker=None, resume=False
        )
        # Reviewed exactly once (single classification gate), still None.
        assert len(prompts) == 1
        assert reviewed[0].change_type is None

    def test_mixed_title_step_shows_hint(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        steps = [Step(id=1, title="Refactor parser and add validation")]
        _review_step_change_types(
            steps,
            input_fn=_queue_input([""]),
            invoker=_appending_invoker(_SPLIT_PAIR_JSON),
            resume=False,
        )
        assert "granularity:" in capsys.readouterr().out

    def test_review_prints_depends_on_notes_before_prompt(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        steps = [
            Step(id=1, title="setup"),
            Step(
                id=2,
                title="tail",
                depends_on=[1],
                depends_on_notes={1: "consumes the base module"},
            ),
        ]
        _review_step_change_types(
            steps,
            input_fn=_queue_input(["", ""]),
            invoker=_appending_invoker(_SPLIT_PAIR_JSON),
            resume=False,
        )
        out = capsys.readouterr().out
        before_prompt = out.split("(r)efactor")[0]
        assert "depends_on 1 (setup): consumes the base module" in before_prompt

    def test_clean_step_shows_no_hint(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        steps = [Step(id=1, title="Add validation helper")]
        _review_step_change_types(
            steps,
            input_fn=_queue_input([""]),
            invoker=_appending_invoker(_SPLIT_PAIR_JSON),
            resume=False,
        )
        assert "granularity:" not in capsys.readouterr().out

    def test_hint_suppressed_when_cannot_split(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)

        def boom(*a, **k):  # would-be advisor must not be consulted
            raise AssertionError("assess_granularity called with can_split False")

        monkeypatch.setattr("plan_tool.create.assess_granularity", boom)
        steps = [Step(id=1, title="Refactor parser and add validation")]
        _review_step_change_types(
            steps,
            input_fn=_queue_input([""]),
            invoker=None,  # can_split False
            resume=False,
        )
        assert "granularity:" not in capsys.readouterr().out

    def test_advisor_failure_does_not_break_review(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)

        def boom(*a, **k):
            raise RuntimeError("advisor blew up")

        monkeypatch.setattr("plan_tool.create.assess_granularity", boom)
        steps = [Step(id=1, title="Refactor parser and add validation")]
        reviewed = _review_step_change_types(
            steps,
            input_fn=_queue_input([""]),
            invoker=_appending_invoker(_SPLIT_PAIR_JSON),
            resume=False,
        )
        assert [s.title for s in reviewed] == ["Refactor parser and add validation"]

    def test_hint_recomputed_after_split(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        steps = [Step(id=1, title="Refactor parser and add validation")]
        # Split step 1; the two clean halves ("characterize" / "add behavior")
        # are then accepted with Enter.
        _review_step_change_types(
            steps,
            input_fn=_queue_input(["s", "", ""]),
            invoker=_appending_invoker(_SPLIT_PAIR_JSON),
            resume=False,
        )
        out = capsys.readouterr().out
        # No stale hint survives the renumber: the post-split halves are clean,
        # so nothing after the split banner re-prints a granularity line.
        _, _, after_split = out.partition("split step 1 into:")
        assert "granularity:" not in after_split

    def test_merge_smell_not_surfaced_in_loop(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        steps = [
            Step(id=1, title="touch x", files=["x.py"]),
            Step(id=2, title="touch x again", files=["x.py"], depends_on=[1]),
        ]
        _review_step_change_types(
            steps,
            input_fn=_queue_input(["", ""]),
            invoker=_appending_invoker(_SPLIT_PAIR_JSON),
            resume=False,
        )
        assert "granularity:" not in capsys.readouterr().out


class TestStepReviewAssessmentTelemetry:
    def test_interactive_pass_records_one_assessment(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        steps = [
            Step(id=1, title="Refactor parser and add validation",
                 files=["plan_tool/parser.py"], creates=["amplify/handler.py"])
        ]
        _review_step_change_types(
            steps,
            input_fn=_queue_input([""]),
            invoker=_appending_invoker(_SPLIT_PAIR_JSON),
            repo_root=tmp_path,
            slug="demo",
            resume=False,
        )
        events = [e for e in read_decisions(tmp_path) if e.decision == "create-review"]
        assert len(events) == 1
        event = events[0]
        assert event.plan_slug == "demo"
        assert event.context["stage"] == "create"
        assert event.context["mode"] == "interactive"
        assert event.context["steps"] == 1
        assert event.context["file_footprint"] == 2
        assert event.context["split"] >= 1
        assert event.context["split_steps"] == 1
        assert event.context["split_step_ids"] == ["1"]
        assert event.context["predicate_counts"] == {
            "mixed-verbs": 1,
            "multi-area": 1,
            "two-clauses": 1,
        }
        assert event.context["can_split"] is True
        assert isinstance(event.context["candidate_fingerprint"], str)
        assert event.context["assessment_id"]
        assert read_decisions(tmp_path)[0].decision == "create-review"

    def test_assessment_records_candidate_fingerprint(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        first = [Step(id=1, title="Add a", files=["a.py"])]
        second = [Step(id=1, title="Add b", files=["a.py"])]
        _review_step_change_types(
            first, input_fn=_queue_input([""]), invoker=None,
            repo_root=tmp_path, slug="demo", resume=False,
        )
        _review_step_change_types(
            first, input_fn=_queue_input([""]), invoker=None,
            repo_root=tmp_path, slug="demo", resume=False,
        )
        _review_step_change_types(
            second, input_fn=_queue_input([""]), invoker=None,
            repo_root=tmp_path, slug="demo", resume=False,
        )
        fps = [
            e.context["candidate_fingerprint"]
            for e in read_decisions(tmp_path)
            if e.decision == "create-review"
        ]
        assert fps[0] == fps[1]
        assert fps[0] != fps[2]
        assessment_ids = [
            e.context["assessment_id"]
            for e in read_decisions(tmp_path)
            if e.decision == "create-review"
        ]
        assert len(set(assessment_ids)) == 3

    def test_yes_non_tty_and_checkpoint_modes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        steps = [Step(id=1, title="one", change_type=ChangeType.FEATURE)]
        _review_step_change_types(
            steps, input_fn=_silent_input_fn, invoker=None,
            repo_root=tmp_path, slug="yes", resume=False, yes=True,
        )
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)
        _review_step_change_types(
            steps, input_fn=_silent_input_fn, invoker=None,
            repo_root=tmp_path, slug="tty", resume=False,
        )

        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        input_hash = _step_review_input_hash("ckpt", steps, out_dir, tmp_path)
        save_checkpoint(
            checkpoint_path(tmp_path, "ckpt", _STEP_REVIEW_CHECKPOINT_NAME),
            Checkpoint(
                input_hash=input_hash,
                payload=json.dumps(
                    [s.model_dump(mode="json", exclude_none=True) for s in steps]
                ),
                created_at=_now_iso(),
            ),
        )
        _review_step_change_types(
            steps, input_fn=_silent_input_fn, invoker=None,
            repo_root=tmp_path, slug="ckpt", output_dir=out_dir,
        )
        modes = [
            e.context["mode"]
            for e in read_decisions(tmp_path)
            if e.decision == "create-review"
        ]
        assert modes == ["yes", "non_tty", "checkpoint"]

    def test_advisor_failure_records_nothing_but_review_succeeds(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)

        def boom(*a, **k):
            raise RuntimeError("advisor blew up")

        monkeypatch.setattr("plan_tool.create.assess_granularity", boom)
        steps = [Step(id=1, title="Refactor parser and add validation")]
        reviewed = _review_step_change_types(
            steps, input_fn=_queue_input([""]), invoker=None,
            repo_root=tmp_path, slug="demo", resume=False,
        )
        assert reviewed == steps
        assert read_decisions(tmp_path) == []

    def test_advisor_runs_for_telemetry_when_cannot_split(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        calls = 0
        original = assess_granularity

        def wrapped(*a, **k):
            nonlocal calls
            calls += 1
            return original(*a, **k)

        monkeypatch.setattr("plan_tool.create.assess_granularity", wrapped)
        _review_step_change_types(
            [Step(id=1, title="Refactor parser and add validation")],
            input_fn=_queue_input([""]),
            invoker=None,
            repo_root=tmp_path,
            slug="demo",
            resume=False,
        )
        assert calls >= 1
        event = [e for e in read_decisions(tmp_path)
                 if e.decision == "create-review"][0]
        assert event.context["can_split"] is False

    def test_assessment_records_code_fingerprint(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        (tmp_path / "a.py").write_text("print('hi')\n")
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        _review_step_change_types(
            [Step(id=1, title="Add a", files=["a.py"])],
            input_fn=_queue_input([""]),
            invoker=None,
            repo_root=tmp_path,
            slug="demo",
            output_dir=out_dir,
            resume=False,
        )
        event = [e for e in read_decisions(tmp_path)
                 if e.decision == "create-review"][0]
        assert len(event.code_fingerprint) == 64
        assert event.code_fingerprint != code_fingerprint_digest({})

    def test_assessment_code_fingerprint_empty_without_output_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        (tmp_path / "a.py").write_text("print('hi')\n")
        _review_step_change_types(
            [Step(id=1, title="Add a", files=["a.py"])],
            input_fn=_queue_input([""]),
            invoker=None,
            repo_root=tmp_path,
            slug="demo",
            resume=False,
        )
        event = [e for e in read_decisions(tmp_path)
                 if e.decision == "create-review"][0]
        assert event.code_fingerprint == ""

    def test_assessment_code_fingerprint_omits_missing_files(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        _review_step_change_types(
            [Step(id=1, title="Add a", files=["nope.py"])],
            input_fn=_queue_input([""]),
            invoker=None,
            repo_root=tmp_path,
            slug="demo",
            output_dir=out_dir,
            resume=False,
        )
        event = [e for e in read_decisions(tmp_path)
                 if e.decision == "create-review"][0]
        assert event.code_fingerprint == code_fingerprint_digest({})


class TestStepReviewOutcomeTelemetry:
    def test_accept_override_and_unclassified_actions(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        steps = [
            Step(id=1, title="feature", change_type=ChangeType.FEATURE),
            Step(id=2, title="feature to refactor", change_type=ChangeType.FEATURE),
            Step(id=3, title="blank"),
            Step(id=4, title="classify"),
        ]
        _review_step_change_types(
            steps,
            input_fn=_queue_input(["", "r", "", "f"]),
            invoker=_appending_invoker(_SPLIT_PAIR_JSON),
            repo_root=tmp_path,
            slug="demo",
            resume=False,
        )
        outcomes = [e for e in read_decisions(tmp_path)
                    if e.decision == "create-step-outcome"]
        assert [e.context["action"] for e in outcomes] == [
            "accept",
            "override",
            "unclassified-accepted",
            "unclassified-classified",
        ]
        assert outcomes[0].plan_slug == "demo"
        assert outcomes[0].context["proposed_change_type"] == "feature"
        assert outcomes[0].context["resolved_change_type"] == "feature"
        assert outcomes[1].context["proposed_change_type"] == "feature"
        assert outcomes[1].context["resolved_change_type"] == "refactor"
        assert outcomes[2].context["proposed_change_type"] is None
        assert outcomes[2].context["resolved_change_type"] is None
        assert outcomes[3].context["proposed_change_type"] is None
        assert outcomes[3].context["resolved_change_type"] == "feature"
        review = [e for e in read_decisions(tmp_path)
                  if e.decision == "create-review"][0]
        assert {e.context["assessment_id"] for e in outcomes} == {
            review.context["assessment_id"]
        }

    def test_split_requested_then_applied_records_two_events(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        steps = [Step(id=1, title="Refactor parser and add validation")]
        _review_step_change_types(
            steps,
            input_fn=_queue_input(["s", "", ""]),
            invoker=_appending_invoker(_SPLIT_PAIR_JSON),
            repo_root=tmp_path,
            slug="demo",
            resume=False,
        )
        outcomes = [e for e in read_decisions(tmp_path)
                    if e.decision == "create-step-outcome"]
        assert [e.context["action"] for e in outcomes[:2]] == [
            "split-requested",
            "split-applied",
        ]
        assert outcomes[0].context["had_split_hint"] is True
        assert outcomes[1].context["before_steps"] == 1
        assert outcomes[1].context["after_steps"] == 2
        assert outcomes[0].context["step_id"] == "1"
        assert outcomes[1].context["step_id"] == "1"
        review = [e for e in read_decisions(tmp_path)
                  if e.decision == "create-review"][0]
        assert {e.context["assessment_id"] for e in outcomes} == {
            review.context["assessment_id"]
        }

    def test_split_unusable_records_terminal(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        _review_step_change_types(
            [Step(id=1, title="Refactor parser and add validation")],
            input_fn=_queue_input(["s", ""]),
            invoker=_appending_invoker("not json"),
            repo_root=tmp_path,
            slug="demo",
            resume=False,
        )
        actions = [e.context["action"] for e in read_decisions(tmp_path)
                   if e.decision == "create-step-outcome"]
        assert actions[:2] == ["split-requested", "split-unusable"]

    def test_split_invalid_records_error_class(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)

        def bad_apply(*a, **k):
            raise CreateError("bad graph")

        monkeypatch.setattr("plan_tool.create._apply_step_split", bad_apply)
        _review_step_change_types(
            [Step(id=1, title="Refactor parser and add validation")],
            input_fn=_queue_input(["s", ""]),
            invoker=_appending_invoker(_SPLIT_PAIR_JSON),
            repo_root=tmp_path,
            slug="demo",
            resume=False,
        )
        invalid = [
            e for e in read_decisions(tmp_path)
            if e.context.get("action") == "split-invalid"
        ][0]
        assert invalid.context["error_class"] == "CreateError"

    def test_split_proposer_exception_records_split_error_then_reraises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)

        def explode(prompt: str) -> str:
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            _review_step_change_types(
                [Step(id=1, title="Refactor parser and add validation")],
                input_fn=_queue_input(["s"]),
                invoker=explode,
                repo_root=tmp_path,
                slug="demo",
                resume=False,
            )
        actions = [e.context["action"] for e in read_decisions(tmp_path)
                   if e.decision == "create-step-outcome"]
        assert actions == ["split-requested", "split-error"]
        error = read_decisions(tmp_path)[-1]
        assert error.context["error_class"] == "RuntimeError"

    def test_no_repo_root_records_no_outcomes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        reviewed = _review_step_change_types(
            [Step(id=1, title="feature", change_type=ChangeType.FEATURE)],
            input_fn=_queue_input([""]),
            invoker=None,
            resume=False,
        )
        assert reviewed[0].change_type is ChangeType.FEATURE

    def test_create_assessment_alone_owns_code_fingerprint(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        (tmp_path / "a.py").write_text("print('hi')\n")
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        _review_step_change_types(
            [Step(id=1, title="Add a", files=["a.py"],
                  change_type=ChangeType.FEATURE)],
            input_fn=_queue_input([""]),
            invoker=None,
            repo_root=tmp_path,
            slug="demo",
            output_dir=out_dir,
            resume=False,
        )
        events = read_decisions(tmp_path)
        review = [e for e in events if e.decision == "create-review"][0]
        outcome = [e for e in events if e.decision == "create-step-outcome"][0]
        assert review.code_fingerprint
        assert outcome.code_fingerprint == ""
        assert outcome.context["assessment_id"] == review.context["assessment_id"]

    def test_step_outcomes_join_one_assessment(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        (tmp_path / "a.py").write_text("a\n")
        (tmp_path / "b.py").write_text("b\n")
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        _review_step_change_types(
            [
                Step(id=1, title="Add a", files=["a.py"],
                     change_type=ChangeType.FEATURE),
                Step(id=2, title="Add b", files=["b.py"],
                     change_type=ChangeType.FEATURE),
            ],
            input_fn=_queue_input(["", ""]),
            invoker=None,
            repo_root=tmp_path,
            slug="demo",
            output_dir=out_dir,
            resume=False,
        )
        outcomes = [e for e in read_decisions(tmp_path)
                    if e.decision == "create-step-outcome"]
        assert len(outcomes) == 2
        review = [e for e in read_decisions(tmp_path)
                  if e.decision == "create-review"][0]
        assert {e.context["assessment_id"] for e in outcomes} == {
            review.context["assessment_id"]
        }
        assert all(e.code_fingerprint == "" for e in outcomes)

    def test_fingerprint_failure_keeps_association_and_review_behavior(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        (tmp_path / "a.py").write_text("a\n")
        out_dir = tmp_path / "plans"
        out_dir.mkdir()

        def boom(*a, **k):
            raise RuntimeError("fingerprint blew up")

        monkeypatch.setattr(
            "plan_tool.fingerprint.compute_code_fingerprint", boom
        )
        reviewed = _review_step_change_types(
            [Step(id=1, title="Add a", files=["a.py"],
                  change_type=ChangeType.FEATURE)],
            input_fn=_queue_input([""]),
            invoker=None,
            repo_root=tmp_path,
            slug="demo",
            output_dir=out_dir,
            resume=False,
        )
        assert reviewed[0].change_type is ChangeType.FEATURE
        events = read_decisions(tmp_path)
        review = [e for e in events if e.decision == "create-review"][0]
        outcome = [e for e in events if e.decision == "create-step-outcome"][0]
        assert review.code_fingerprint == ""
        assert outcome.code_fingerprint == ""
        assert outcome.context["assessment_id"] == review.context["assessment_id"]

    def test_assessment_id_failure_skips_create_telemetry_without_breaking_review(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)

        def fail_uuid() -> None:
            raise RuntimeError("uuid unavailable")

        monkeypatch.setattr("plan_tool.create.uuid.uuid4", fail_uuid)
        reviewed = _review_step_change_types(
            [Step(id=1, title="Add a", change_type=ChangeType.FEATURE)],
            input_fn=_queue_input(["r"]),
            invoker=None,
            repo_root=tmp_path,
            slug="demo",
            resume=False,
        )
        assert reviewed[0].change_type is ChangeType.REFACTOR
        assert read_decisions(tmp_path) == []

    def test_failed_assessment_append_skips_associated_outcomes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        monkeypatch.setattr(
            "plan_tool.create.record_create_granularity_assessment",
            lambda *args, **kwargs: False,
        )
        reviewed = _review_step_change_types(
            [Step(id=1, title="Add a", change_type=ChangeType.FEATURE)],
            input_fn=_queue_input([""]),
            invoker=None,
            repo_root=tmp_path,
            slug="demo",
            resume=False,
        )
        assert reviewed[0].change_type is ChangeType.FEATURE
        assert read_decisions(tmp_path) == []

    def test_partial_assessment_append_failure_skips_associated_outcomes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import plan_tool.telemetry as telemetry

        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        real_write = telemetry.os.write
        writes = 0

        def short_then_stall(fd: int, data: bytes) -> int:
            nonlocal writes
            writes += 1
            if writes == 1:
                return real_write(fd, data[:5])
            return 0

        monkeypatch.setattr(telemetry.os, "write", short_then_stall)
        reviewed = _review_step_change_types(
            [Step(id=1, title="Add a", change_type=ChangeType.FEATURE)],
            input_fn=_queue_input([""]),
            invoker=None,
            repo_root=tmp_path,
            slug="demo",
            resume=False,
        )
        assert reviewed[0].change_type is ChangeType.FEATURE
        assert read_decisions(tmp_path) == []

    def test_create_event_plan_fingerprint_empty(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        (tmp_path / "a.py").write_text("a\n")
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        _review_step_change_types(
            [Step(id=1, title="Add a", files=["a.py"],
                  change_type=ChangeType.FEATURE)],
            input_fn=_queue_input([""]),
            invoker=None,
            repo_root=tmp_path,
            slug="demo",
            output_dir=out_dir,
            resume=False,
        )
        events = [e for e in read_decisions(tmp_path)
                  if e.decision in ("create-review", "create-step-outcome")]
        assert events
        # Create decisions are made pre-write, so no on-disk plan digest.
        assert all(e.plan_fingerprint == "" for e in events)


def _seed_review_repo(tmp_path: Path) -> tuple[Path, Path, Path]:
    (tmp_path / ".git").mkdir()
    out_dir = tmp_path / "plans"
    out_dir.mkdir()
    manifest = tmp_path / "m.json"
    return tmp_path, out_dir, manifest


class TestCreatePlanStepReviewYes:
    def test_yes_keeps_proposals_verbatim(self, tmp_path: Path) -> None:
        repo, out_dir, manifest = _seed_review_repo(tmp_path)
        canned = json.dumps(
            [
                {"title": "one", "change_type": "refactor", "files": [], "depends_on": []},
                {"title": "two", "change_type": "feature", "files": [], "depends_on": [1]},
            ]
        )

        def guard(prompt: str) -> str:
            assert "accept" not in prompt and "efactor" not in prompt, (
                f"review must not prompt under --yes: {prompt!r}"
            )
            return ""

        result = create_plan(
            "demo",
            repo_root=repo,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="Build a thing",
            input_fn=guard,
            claude_invoker=lambda prompt: canned,
            yes=True,
        )
        plan = parse_plan(result.plan_path)
        assert plan.steps[0].change_type is ChangeType.REFACTOR
        assert plan.steps[1].change_type is ChangeType.FEATURE

    def test_yes_lists_unproposed_on_stderr(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo, out_dir, manifest = _seed_review_repo(tmp_path)
        canned = json.dumps(
            [
                {"title": "one", "change_type": "refactor", "files": [], "depends_on": []},
                {"title": "two", "files": [], "depends_on": [1]},  # unproposed
            ]
        )
        create_plan(
            "demo",
            repo_root=repo,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="Build a thing",
            input_fn=_silent_input_fn,
            claude_invoker=lambda prompt: canned,
            yes=True,
        )
        err = capsys.readouterr().err
        assert "change_type=None" in err
        assert "2" in err  # the unproposed step id


class TestStepReviewCheckpoint:
    def test_resume_restores_reviewed_steps(self, tmp_path: Path) -> None:
        repo, out_dir, manifest = _seed_review_repo(tmp_path)
        canned = json.dumps(
            [{"title": "one", "change_type": "feature", "files": [], "depends_on": []}]
        )
        pre = _parse_steps_json(canned)
        assert pre is not None
        reviewed = [
            s.model_copy(update={"change_type": ChangeType.REFACTOR}) for s in pre
        ]
        save_checkpoint(
            checkpoint_path(repo, "demo", _STEP_REVIEW_CHECKPOINT_NAME),
            Checkpoint(
                input_hash=_step_review_input_hash("demo", pre, out_dir, repo),
                payload=json.dumps(
                    [s.model_dump(mode="json", exclude_none=True) for s in reviewed]
                ),
                created_at=_now_iso(),
            ),
        )

        # Metadata answers only — a review prompt would exhaust the queue.
        result = create_plan(
            "demo",
            repo_root=repo,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="Build a thing",
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=lambda prompt: canned,
        )
        plan = parse_plan(result.plan_path)
        # Restored REFACTOR (not the proposal's FEATURE).
        assert plan.steps[0].change_type is ChangeType.REFACTOR

    def test_changed_proposal_invalidates_checkpoint(self, tmp_path: Path) -> None:
        repo, out_dir, _ = _seed_review_repo(tmp_path)
        steps_a = [Step(id=1, title="alpha")]
        steps_b = [Step(id=1, title="beta")]
        h_a = _step_review_input_hash("demo", steps_a, out_dir, repo)
        h_b = _step_review_input_hash("demo", steps_b, out_dir, repo)
        assert h_a != h_b

    def test_clean_create_discards_step_review_checkpoint(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo, out_dir, manifest = _seed_review_repo(tmp_path)
        canned = json.dumps(
            [{"title": "one", "change_type": "refactor", "files": [], "depends_on": []}]
        )
        # TTY → the review runs and saves a create-step-review checkpoint;
        # the success path must then discard it.
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        create_plan(
            "demo",
            repo_root=repo,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="Build a thing",
            input_fn=_queue_input(_basic_metadata_answers() + [""]),
            claude_invoker=lambda prompt: canned,
        )
        leftover = list(
            checkpoint_dir(repo, "demo").glob(f"{_STEP_REVIEW_CHECKPOINT_NAME}*.json")
        )
        assert leftover == []


class TestRationalesOut:
    def test_parse_captures_rationale(self) -> None:
        raw = json.dumps(
            [
                {"title": "one", "change_type": "refactor", "rationale": "pure restructure"},
                {"title": "two", "change_type": "feature"},  # no rationale
            ]
        )
        out: dict[int, str] = {}
        steps = _parse_steps_json(raw, rationales_out=out)
        assert steps is not None
        assert out == {1: "pure restructure"}

    def test_prepare_call_owns_initial_rationales_out(self) -> None:
        import inspect

        from plan_tool.create import _converge_create_plan, _prepare_create_plan

        prepare_source = inspect.getsource(_prepare_create_plan)
        converge_source = inspect.getsource(_converge_create_plan)
        assert prepare_source.count("rationales_out=step_rationales") == 1
        assert "rationales_out=step_rationales" not in converge_source

    def test_initial_proposal_rationales_reach_step_review(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool import create as create_module

        repo, out_dir, manifest = _seed_review_repo(tmp_path)
        captured: dict[int, str] = {}

        def review_steps(steps: list[Step], **kwargs: Any) -> list[Step]:
            captured.update(kwargs["rationales"])
            return steps

        monkeypatch.setattr(
            create_module, "_review_step_change_types", review_steps
        )
        monkeypatch.setattr(
            create_module,
            "propose_references_from_claude",
            lambda *args, **kwargs: ReferenceResearchResult.from_references([]),
        )
        create_plan(
            "demo",
            repo_root=repo,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="Build a thing",
            claude_invoker=lambda prompt: json.dumps([
                {"title": "one", "rationale": "pure restructure"}
            ]),
            yes=True,
            synthesize_body=False,
            allow_placeholder_body=True,
        )
        assert captured == {1: "pure restructure"}


# --- Create-time step proposal: prompt A/B mode ----------------------------

from plan_tool.create import (  # noqa: E402
    _MECHANISM_REACH_RULE,
    _PROPOSAL_FOUNDATIONAL_ITEM,
    _render_from_prompt,
    _render_synthesis_prompt,
    _render_sweep_context,
)


class TestRenderFromPromptABMode:
    """The step-proposal prompt is the A/B control surface. COMBINED (default)
    inlines item 9 (foundational logic). SPLIT omits it
    (``omit_foundational_item=True``), since a separate call runs it. Items 7
    (intent) and 8 (destructive-op disposition) are fixed and ride both arms.
    ``create`` does not propose ``gate:`` commands in either arm — see
    ``suggest-gates`` for grounded, post-build gate suggestion instead."""

    def test_combined_default_inlines_foundational(self) -> None:
        prompt = _render_from_prompt("Build a thing")
        # Foundational is the last item (9) by default.
        assert "foundational logic" in prompt
        assert "other locations that share that logic" in prompt
        assert "9. **Identify" in prompt

    def test_split_omits_foundational(self) -> None:
        prompt = _render_from_prompt("Build a thing", omit_foundational_item=True)
        assert "foundational logic" not in prompt
        assert "9. **Identify" not in prompt
        # No invented JSON key leaks in either mode.
        assert "shared_locations" not in prompt
        # change_type (item 6) and intent (item 7) survive.
        assert '"change_type"' in prompt
        assert "7. Give every step a one-line `intent`" in prompt

    def test_smallest_proof_guidance_survives_both_arms(self) -> None:
        for arm in ({}, {"omit_foundational_item": True}):
            prompt = _render_from_prompt("Build a thing", **arm)
            assert "smallest end-to-end proof" in prompt
            assert "adjacent workflow, cleanup, generalization, or future" in prompt
            assert "Keep the step list at plan altitude" in prompt

    def test_create_prompt_states_all_three_mechanism_reach_routes(self) -> None:
        for arm in ({}, {"omit_foundational_item": True}):
            prompt = _render_from_prompt("Add the focused property", **arm)
            assert prompt.count(_MECHANISM_REACH_RULE) == 1
            assert "current common owner unchanged" in prompt
            assert "smallest local adapter or bounded additive extension" in prompt
            assert "required shared semantic change out of the focused plan" in prompt
            assert "none proves shared semantic reach" in prompt
            assert '"mechanism_reach"' not in prompt

    def test_synthesis_prompt_states_all_three_mechanism_reach_routes(self) -> None:
        prompt = _render_synthesis_prompt("Add the focused property")
        assert "current common owner unchanged" in prompt
        assert "smallest local adapter or bounded additive extension" in prompt
        assert "required shared semantic change out of the focused plan" in prompt
        assert "do not add a route field or a new body section" in prompt
        assert "## Mechanism reach" not in prompt
        assert '"route"' not in prompt

    def test_single_concern_stage3_present(self) -> None:
        # The proposal prompt enforces single-concern decomposition beyond
        # change_type purity (BACKLOG #58): Stage 3 plus the don't-over-
        # fragment counterweight, in both A/B arms.
        prompt = _render_from_prompt("Build a thing")
        assert "Stage 3 — one concern per step" in prompt
        assert "different control-flow shapes" in prompt
        assert "no namable live scenario is NOT a step" in prompt
        assert "do NOT over-fragment" in prompt
        # Survives the split arm too (it rides with item 6, not 7/8).
        split = _render_from_prompt("Build a thing", omit_foundational_item=True)
        assert "Stage 3 — one concern per step" in split


class TestRefactorBoundaryProposalGuidance:
    """Create proposal paths keep refactors at observable execution boundaries."""

    _BOUNDARY_RULE = "select a distinct observable execution boundary"
    _RULE_ONLY_DETAIL = "its observable owner's detail"
    _ARMS = [{}, {"omit_foundational_item": True}]

    def test_refactor_boundary_rule_survives_both_proposal_arms(self) -> None:
        for arm in self._ARMS:
            prompt = _render_from_prompt("Refactor the runner", **arm)
            assert prompt.index("Stage 2 — type-pure decomposition") < prompt.index(
                "Stage 3 — one concern per step"
            )
            assert prompt.index("For `feature` work") < prompt.index(
                self._BOUNDARY_RULE
            ) < prompt.index("For either code type")
            assert '"observable_boundary"' not in prompt

    def test_refactor_prompt_keeps_inner_mechanics_in_detail_without_observable_contract(
        self,
    ) -> None:
        prompt = _render_from_prompt("Refactor the runner")
        assert self._RULE_ONLY_DETAIL in prompt
        assert (
            "only when it independently owns an observable handoff, ordering, "
            "or bypass contract" in prompt
        )
        for mechanic in (
            "guard",
            "accumulator",
            "selector",
            "rebuild",
            "callback",
            "fixture",
        ):
            assert mechanic in prompt

    def test_refactor_prompt_uses_one_concern_fallback_when_no_outer_map_is_grounded(
        self,
    ) -> None:
        prompt = _render_from_prompt("Refactor the runner")
        assert "does not ground a public-entry-to-terminal path" in prompt
        assert "do not invent an outer boundary or phase count" in prompt
        assert "do not promote an inner mechanism merely because it repeats" in prompt

    def test_combined_foundational_item_requires_an_eligible_boundary(self) -> None:
        assert "apply Stage 3's boundary rule here" in _PROPOSAL_FOUNDATIONAL_ITEM
        assert (
            "otherwise leave it with its observable owner"
            in _PROPOSAL_FOUNDATIONAL_ITEM
        )
        assert self._BOUNDARY_RULE not in _PROPOSAL_FOUNDATIONAL_ITEM
        assert "Apply the mechanism-reach rule above" in _PROPOSAL_FOUNDATIONAL_ITEM
        assert "never add a new JSON key" in _PROPOSAL_FOUNDATIONAL_ITEM

    def test_combined_prompt_has_one_complete_refactor_rule(self) -> None:
        prompt = _render_from_prompt("Refactor the runner")
        assert prompt.count(self._BOUNDARY_RULE) == 1
        assert "apply Stage 3's boundary rule here" in prompt

    def test_split_sweep_context_includes_focused_description_and_step_boundary(
        self,
    ) -> None:
        context = _render_sweep_context(
            [
                Step(
                    id=1,
                    title="Refactor the runner",
                    files=["plan_tool/runner.py"],
                    creates=["tests/test_runner.py"],
                )
            ],
            "Preserve the focused property for one caller.",
        )
        assert self._BOUNDARY_RULE in context
        assert self._RULE_ONLY_DETAIL in context
        assert "Focused plan description:" in context
        assert "Preserve the focused property for one caller." in context
        assert "step 1: Refactor the runner" in context
        assert "declared boundary:" in context
        assert "files: plan_tool/runner.py" in context
        assert "creates: tests/test_runner.py" in context
        assert "checkpoint" not in context

    def test_split_sweep_context_keeps_the_steps_only_helper_call(self) -> None:
        context = _render_sweep_context([Step(id=1, title="Refactor the runner")])

        assert "Focused plan description:" in context
        assert "_not supplied_" in context
        assert "step 1: Refactor the runner" in context


class TestParseStepsJsonGate:
    """``create`` no longer asks the model for a ``gate:`` list, and there is
    no operator review left to vet one — so a stray ``gate`` key in the
    response must never reach ``Step.gate`` unreviewed. ``_parse_steps_json``
    ignores it outright."""

    def test_gate_key_is_ignored(self) -> None:
        raw = json.dumps(
            [{"title": "Rename", "gate": ["pytest tests/x.py -q", "grep -q foo ."]}]
        )
        steps = _parse_steps_json(raw)
        assert steps is not None
        assert steps[0].gate == []

    def test_missing_gate_key_is_also_empty(self) -> None:
        steps = _parse_steps_json(json.dumps([{"title": "No gate key"}]))
        assert steps is not None
        assert steps[0].gate == []

    def test_yes_writes_no_gate_to_plan(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo, out_dir, manifest = _seed_review_repo(tmp_path)
        canned = json.dumps(
            [
                {
                    "title": "rename",
                    "change_type": "refactor",
                    "files": [],
                    "depends_on": [],
                    "gate": ["pytest tests/x.py -q"],
                }
            ]
        )
        create_plan(
            "demo",
            repo_root=repo,
            output_dir_override=out_dir,
            manifest_path=manifest,
            from_description="Build a thing",
            input_fn=_silent_input_fn,
            claude_invoker=lambda prompt: canned,
            yes=True,
        )
        plan = parse_plan(next(p for p in out_dir.glob("*-demo.md")))
        assert plan.steps[0].gate == []


class TestProposalPromptAsksForIntent:
    """Item 7 + the ``intent`` JSON key ride the one proposal call ``create``
    already makes, in both A/B arms."""

    _ARMS = [
        {},
        {"omit_foundational_item": True},
    ]

    def test_proposal_prompt_asks_for_intent(self) -> None:
        prompt = _render_from_prompt("Build a thing")
        assert _STEP_PROPOSAL_RESPONSE_CONTRACT.render_prompt_block() in prompt
        assert "7. Give every step a one-line `intent`" in prompt
        # The line against ``rationale`` — the one a reader gets wrong.
        assert "Do not confuse it with `rationale`" in prompt

    def test_scope_prompts_accept_the_shared_project_context(self) -> None:
        from plan_tool.create import _render_synthesis_prompt

        context = (
            "## Confirmed project context\n\n"
            "This context guides scope and trade-offs.\n\n"
            "### Project intent\n\nKeep it small.\n\n"
            "### Non-goals\n\n- Do not add a service.\n\n"
            "### Settled decisions\n\n- Prefer reversible changes."
        )
        proposal = _render_from_prompt("Build a thing", project_context=context)
        synthesis = _render_synthesis_prompt(
            "Build a thing", project_context=context
        )

        for prompt in (proposal, synthesis):
            assert "Keep it small." in prompt
            assert "Do not add a service." in prompt
            assert "Prefer reversible changes." in prompt
            assert prompt.index("Confirmed project context") < prompt.index(
                "Build a thing"
            )

    def test_create_scope_prompts_load_the_confirmed_profile(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.create import propose_body_sections
        from plan_tool.project_profile import initialize_project_profile

        initialize_project_profile(
            tmp_path,
            intent="Keep it small.",
            non_goals=("Do not add a service.",),
            decisions=("Prefer reversible changes.",),
        )
        prompts: list[str] = []

        def steps_invoker(prompt: str) -> str:
            prompts.append(prompt)
            return _STEP_JSON

        def body_invoker(prompt: str) -> str:
            prompts.append(prompt)
            return _full_body_json()

        assert propose_steps_from_claude(
            "Build a thing", steps_invoker, repo_root=tmp_path
        )
        propose_body_sections(
            "Build a thing", body_invoker, repo_root=tmp_path
        )
        for prompt in prompts:
            assert "Keep it small." in prompt
            assert "Do not add a service." in prompt
            assert "Prefer reversible changes." in prompt

    def test_missing_intent_prompt_loads_the_confirmed_profile(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.create import _offer_missing_intents
        from plan_tool.project_profile import initialize_project_profile

        initialize_project_profile(tmp_path, intent="Keep it small.")
        seen: list[str] = []
        plan = Plan(
            title="Demo",
            status=PlanStatus.PLANNING,
            priority=Priority.LOW,
            steps=[Step(id=1, title="Build it")],
        )
        _offer_missing_intents(
            plan,
            input_fn=lambda _prompt: "",
            invoker=lambda prompt: seen.append(prompt) or json.dumps([]),
            repo_root=tmp_path,
            yes=True,
        )

        assert len(seen) == 1
        assert "Keep it small." in seen[0]

    def test_intent_item_survives_both_prompt_arms(self) -> None:
        for arm in self._ARMS:
            prompt = _render_from_prompt("Build a thing", **arm)
            assert _STEP_PROPOSAL_RESPONSE_CONTRACT.render_prompt_block() in prompt, arm
            assert "7. Give every step a one-line `intent`" in prompt, arm

    def test_prompt_item_numbering_has_no_gaps(self) -> None:
        for arm in self._ARMS:
            prompt = _render_from_prompt("Build a thing", **arm)
            nums = [
                int(m) for m in re.findall(r"^(\d+)\. ", prompt, re.MULTILINE)
            ]
            expected = 8 + (0 if arm.get("omit_foundational_item") else 1)
            assert nums == list(range(1, expected + 1)), arm
            assert '"observable_boundary"' not in prompt, arm


class TestProposalPromptDestructiveItem:
    """Item 8 (destructive-op disposition) is fixed and rides both A/B arms:
    a step that modifies or retires a write path must state each destructive
    operation's fate, folded into existing step shapes — no new JSON key."""

    _ARMS = TestProposalPromptAsksForIntent._ARMS

    def test_destructive_item_survives_both_prompt_arms(self) -> None:
        for arm in self._ARMS:
            prompt = _render_from_prompt("Build a thing", **arm)
            assert "8. **Enumerate destructive operations" in prompt, arm
            assert "preserved, narrowed, or retired" in prompt, arm
            # The retired-producer / live-consumer hazard is the measured
            # CRITICAL class the item exists to pre-empt.
            assert "possibly empty" in prompt, arm

    def test_destructive_item_adds_no_json_key(self) -> None:
        for arm in self._ARMS:
            prompt = _render_from_prompt("Build a thing", **arm)
            assert "destructive_ops" not in prompt, arm
            assert '"disposition"' not in prompt, arm

    def test_destructive_item_forbids_folding_into_intent(self) -> None:
        """Item 8 must not tell the model it may fold a disposition into
        `intent` — that field is item 7's alone, one line, why-this-step-
        exists only. Both the prohibition and the closing generalization
        must exclude `intent`, not just one of the two."""
        for arm in self._ARMS:
            prompt = _render_from_prompt("Build a thing", **arm)
            assert "Do not " in prompt and "fold it into `intent`" in prompt, arm
            assert "never `intent`" in prompt, arm


class TestParseStepsJsonIntent:
    """``_parse_steps_json`` reads ``intent`` leniently — like ``change_type``,
    a bad value coerces to ``None`` and never rejects the list. It
    makes no usability judgment: ``is_usable_intent`` is applied in exactly one
    place, ``propose_steps_from_claude``'s retry check."""

    def test_parse_steps_json_reads_intent(self) -> None:
        steps = _parse_steps_json(
            json.dumps([{"title": "t", "intent": "why this exists"}])
        )
        assert steps is not None
        assert steps[0].intent == "why this exists"

    def test_parse_steps_json_tolerates_missing_intent(self) -> None:
        steps = _parse_steps_json(json.dumps([{"title": "No intent key"}]))
        assert steps is not None and len(steps) == 1
        assert steps[0].intent is None

    @pytest.mark.parametrize("value", [3, None, ["a"], {"a": 1}, True])
    def test_parse_steps_json_tolerates_non_string_intent(self, value) -> None:
        steps = _parse_steps_json(json.dumps([{"title": "t", "intent": value}]))
        assert steps is not None and len(steps) == 1
        assert steps[0].intent is None

    def test_parse_steps_json_strips_intent_whitespace(self) -> None:
        steps = _parse_steps_json(
            json.dumps(
                [
                    {"title": "a", "intent": "  padded  "},
                    {"title": "b", "intent": "   "},
                ]
            )
        )
        assert steps is not None
        assert [s.intent for s in steps] == ["padded", None]

    def test_parse_steps_json_keeps_a_placeholder_intent_verbatim(self) -> None:
        steps = _parse_steps_json(json.dumps([{"title": "t", "intent": "TODO"}]))
        assert steps is not None
        assert steps[0].intent == "TODO"


class TestProposalPromptDependsOnNotes:
    """Optional ``depends_on_notes`` rides the JSON contract beside ``depends_on``."""

    _ARMS = TestProposalPromptAsksForIntent._ARMS

    def test_proposal_prompt_names_depends_on_notes_shape(self) -> None:
        prompt = _render_from_prompt("Build a thing")
        assert _STEP_PROPOSAL_RESPONSE_CONTRACT.render_prompt_block() in prompt
        assert "omit the key, or omit individual ids" in prompt

    def test_depends_on_notes_explainer_survives_both_prompt_arms(self) -> None:
        for arm in self._ARMS:
            prompt = _render_from_prompt("Build a thing", **arm)
            assert _STEP_PROPOSAL_RESPONSE_CONTRACT.render_prompt_block() in prompt, arm
            assert "never require a note" in prompt, arm


class TestParseStepsJsonDependsOn:
    def test_depends_on_coerces_quoted_numeral(self) -> None:
        steps = _parse_steps_json(
            json.dumps([{"title": "dependent", "depends_on": ["5"]}])
        )
        assert steps is not None
        assert steps[0].depends_on == [5]

    @pytest.mark.parametrize(
        "raw_id",
        [
            "--5",
            "²",
            "5.0",
            "2_0",
            "٢",
            "02",
            "0",
            pytest.param("1" + "0" * 4999, id="oversized"),
        ],
    )
    def test_depends_on_rejects_malformed_numeral_string_without_raising(
        self, raw_id: str
    ) -> None:
        assert _parse_steps_json(
            json.dumps([{"title": "dependent", "depends_on": [raw_id]}])
        ) is None

    def test_depends_on_deduplicates_mixed_numeral_forms(self) -> None:
        steps = _parse_steps_json(
            json.dumps([{"title": "dependent", "depends_on": [1, "1"]}])
        )
        assert steps is not None
        assert steps[0].depends_on == [1]


class TestParseStepsJsonDependsOnNotes:
    """``_parse_steps_json`` reads ``depends_on_notes`` leniently — orphan keys
    and empty strings are dropped; a bad top-level shape coerces to ``{}``."""

    def test_parse_steps_json_reads_depends_on_notes(self) -> None:
        raw = json.dumps(
            [
                {
                    "title": "second",
                    "depends_on": [1],
                    "depends_on_notes": {1: "consumes the schema"},
                }
            ]
        )
        steps = _parse_steps_json(raw)
        assert steps is not None
        assert steps[0].depends_on_notes == {1: "consumes the schema"}

    def test_parse_steps_json_tolerates_missing_depends_on_notes(self) -> None:
        steps = _parse_steps_json(json.dumps([{"title": "No notes key"}]))
        assert steps is not None
        assert steps[0].depends_on_notes == {}

    def test_parse_steps_json_tolerates_non_object_depends_on_notes(self) -> None:
        raw = json.dumps(
            [{"title": "Bad", "depends_on": [1], "depends_on_notes": "nope"}]
        )
        steps = _parse_steps_json(raw)
        assert steps is not None
        assert steps[0].depends_on_notes == {}

    def test_parse_steps_json_drops_orphan_note_keys(self) -> None:
        raw = json.dumps(
            [
                {
                    "title": "t",
                    "depends_on": [1],
                    "depends_on_notes": {2: "orphan"},
                }
            ]
        )
        steps = _parse_steps_json(raw)
        assert steps is not None
        assert steps[0].depends_on_notes == {}

    def test_parse_steps_json_drops_note_for_removed_depends_on_id(self) -> None:
        raw = json.dumps(
            [
                {
                    "title": "t",
                    "depends_on": [1],
                    "depends_on_notes": {1: "keep", 2: "drop"},
                }
            ]
        )
        steps = _parse_steps_json(raw)
        assert steps is not None
        assert steps[0].depends_on_notes == {1: "keep"}

    def test_parse_steps_json_coerces_stringified_int_keys(self) -> None:
        raw = json.dumps(
            [
                {
                    "title": "t",
                    "depends_on": [1],
                    "depends_on_notes": {"1": "from string key"},
                }
            ]
        )
        steps = _parse_steps_json(raw)
        assert steps is not None
        assert steps[0].depends_on_notes == {1: "from string key"}

    @pytest.mark.parametrize(
        "raw_id",
        [
            "01",
            "2_0",
            "٢",
            pytest.param("1" + "0" * 4999, id="oversized"),
        ],
    )
    def test_parse_steps_json_drops_malformed_note_key_without_raising(
        self, raw_id: str
    ) -> None:
        steps = _parse_steps_json(
            json.dumps(
                [{
                    "title": "t",
                    "depends_on": [1],
                    "depends_on_notes": {raw_id: "bad key"},
                }]
            )
        )
        assert steps is not None
        assert steps[0].depends_on_notes == {}

    def test_parse_steps_json_drops_ambiguous_normalized_note_keys(self) -> None:
        steps = _parse_steps_json(
            json.dumps(
                [{
                    "title": "t",
                    "depends_on": [1],
                    "depends_on_notes": {"1": "first", " 1": "second"},
                }]
            )
        )
        assert steps is not None
        assert steps[0].depends_on_notes == {}

    def test_parse_steps_json_accepts_partial_edge_coverage(self) -> None:
        raw = json.dumps(
            [
                {
                    "title": "t",
                    "depends_on": [1, 2],
                    "depends_on_notes": {1: "only first edge"},
                }
            ]
        )
        steps = _parse_steps_json(raw)
        assert steps is not None
        assert steps[0].depends_on_notes == {1: "only first edge"}

    def test_parse_steps_json_drops_empty_string_note_values(self) -> None:
        raw = json.dumps(
            [
                {
                    "title": "t",
                    "depends_on": [1],
                    "depends_on_notes": {1: ""},
                }
            ]
        )
        steps = _parse_steps_json(raw)
        assert steps is not None
        assert steps[0].depends_on_notes == {}

    def test_key_present_out_tracks_omit_vs_explicit_empty(self) -> None:
        present: dict[int, bool] = {}
        _parse_steps_json(
            json.dumps([{"title": "omit"}]),
            depends_on_notes_key_present_out=present,
        )
        assert present == {1: False}
        present.clear()
        _parse_steps_json(
            json.dumps([{"title": "explicit", "depends_on_notes": {}}]),
            depends_on_notes_key_present_out=present,
        )
        assert present == {1: True}


class TestManualDependsOnNotes:
    def test_prompt_one_step_collects_optional_notes(self) -> None:
        from plan_tool.create import _prompt_one_step

        prior = Step(id=1, title="base step")
        step = _prompt_one_step(
            _queue_input(
                ["Downstream", "", "", "1", "delivers the parser API"]
            ),
            2,
            {1},
            [prior],
        )
        assert step.depends_on_notes == {1: "delivers the parser API"}

        step_blanks = _prompt_one_step(
            _queue_input(["Other", "", "", "1, 2", "", ""]),
            2,
            {1},
            [prior],
        )
        assert step_blanks.depends_on_notes == {}

    def test_prompt_one_step_skips_note_prompts_when_no_depends_on(self) -> None:
        from plan_tool.create import _prompt_one_step

        # title / complexity / files / depends_on — four prompts only.
        step = _prompt_one_step(_queue_input(["Manual step", "", "", ""]), 1, set())
        assert step.depends_on_notes == {}


class TestProposedDependsOnNotesEndToEnd:
    def test_proposed_depends_on_notes_reach_written_frontmatter(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()

        canned = json.dumps(
            [
                _proposed_step("one"),
                _proposed_step(
                    "two",
                    depends_on=[1],
                    depends_on_notes={1: "consumes the base module"},
                ),
            ]
        )
        result = create_plan(
            "demo",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=tmp_path / "m.json",
            from_description="Build a thing",
            input_fn=_queue_input(_basic_metadata_answers()),
            claude_invoker=lambda prompt: canned,
        )

        text = result.plan_path.read_text(encoding="utf-8")
        assert "depends_on_notes:" in text
        assert "consumes the base module" in text
        plan = parse_plan(result.plan_path)
        assert plan.steps[1].depends_on_notes == {1: "consumes the base module"}

    def test_proposed_step_without_note_accepted_unchanged(self) -> None:
        calls: list[str] = []

        def invoker(prompt: str) -> str:
            calls.append(prompt)
            return json.dumps(
                [
                    _proposed_step("one"),
                    _proposed_step("two", depends_on=[1]),
                ]
            )

        steps = propose_steps_from_claude("Build a thing", invoker)
        assert steps is not None
        assert steps[1].depends_on_notes == {}
        assert len(calls) == 1


class TestReproposalPreservesDependsOnNotes:
    def test_preserve_on_disk_keeps_depends_on_notes_when_proposal_omits(
        self,
    ) -> None:
        prior = Step(
            id=2,
            title="two",
            depends_on=[1],
            depends_on_notes={1: "the accepted note"},
        )
        merged = _preserve_on_disk_step_fields(
            Step(id=2, title="two", depends_on=[1]),
            prior,
            proposal_included_depends_on_notes=False,
        )
        assert merged.depends_on_notes == {1: "the accepted note"}

        cleared = _preserve_on_disk_step_fields(
            Step(id=2, title="two", depends_on=[1], depends_on_notes={}),
            prior,
            proposal_included_depends_on_notes=True,
        )
        assert cleared.depends_on_notes == {}

    def test_preserve_on_disk_intersects_notes_with_proposal_depends_on(
        self,
    ) -> None:
        prior = Step(
            id=2,
            title="downstream",
            depends_on=[1, 2],
            depends_on_notes={1: "from one", 2: "from two"},
        )
        merged = _preserve_on_disk_step_fields(
            Step(id=2, title="downstream", depends_on=[1]),
            prior,
            proposal_included_depends_on_notes=False,
        )
        assert merged.depends_on_notes == {1: "from one"}


class TestReproposalPreservesGate:
    """``create`` never proposes ``gate:`` (see TestParseStepsJsonGate), so a
    title-matched step's on-disk gate commands — set by ``suggest-gates`` or
    by hand — must survive the ``--iterate`` loop's step re-proposal rather
    than being silently wiped by the always-empty reproposed value."""

    def test_preserve_on_disk_keeps_gate_when_title_matches(self) -> None:
        prior = Step(id=1, title="one", gate=["pytest tests/test_x.py -q"])
        merged = _preserve_on_disk_step_fields(Step(id=1, title="one"), prior)
        assert merged.gate == ["pytest tests/test_x.py -q"]

    def test_gate_does_not_travel_to_a_different_step_at_the_same_id(self) -> None:
        prior = Step(id=1, title="old title", gate=["pytest tests/test_x.py -q"])
        merged = _preserve_on_disk_step_fields(
            Step(id=1, title="different step"), prior
        )
        assert merged.gate == []

    def test_new_step_has_no_gate(self) -> None:
        merged = _preserve_on_disk_step_fields(Step(id=2, title="new"), None)
        assert merged.gate == []


class TestDependsOnNotesNegativeSpace:
    def test_canonical_extraction_produces_no_depends_on_notes(self) -> None:
        steps = extract_steps_from_canonical(_CANONICAL_BODY)
        assert steps is not None
        assert all(s.depends_on_notes == {} for s in steps)

    def test_merge_sweep_into_steps_produces_no_depends_on_notes(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.foundational_logic import (
            ConsolidationSuggestion,
            SweepResult,
            merge_sweep_into_steps,
        )

        steps = [
            Step(id=1, title="first", files=["a.py"]),
            Step(id=2, title="second", depends_on=[1]),
        ]
        result = SweepResult(
            logic="shared rule",
            consolidation=ConsolidationSuggestion(
                title="Consolidate shared rule",
                files=["a.py"],
                after_step_id=1,
            ),
        )
        merged = merge_sweep_into_steps(steps, result, repo_root=tmp_path)
        consolidation = merged[-1]
        assert consolidation.depends_on == [1]
        # A rationale-less suggestion falls back to None, not an empty
        # string, matching _parse_steps_json's own empty-to-None coercion
        # for intent elsewhere in create's step-building path.
        assert consolidation.intent is None
        assert consolidation.depends_on_notes == {}


class TestReproposalSkippable:
    """Opportunity 3 (minimize-claude): a round that applied only
    prose/body-section findings can skip the steps/references re-proposal."""

    def test_prose_only_sources_are_skippable(self) -> None:
        assert _reproposal_is_skippable({"body-completeness"})
        assert _reproposal_is_skippable({"detail-body"})
        assert _reproposal_is_skippable({"body-completeness", "detail-body"})

    def test_any_non_prose_source_blocks_skip(self) -> None:
        # A correctness / reconcile apply could warrant re-derivation.
        assert not _reproposal_is_skippable({"plan-correctness"})
        assert not _reproposal_is_skippable({"body-completeness", "plan-correctness"})
        assert not _reproposal_is_skippable({"reconcile"})

    def test_empty_is_not_skippable(self) -> None:
        # No applied findings -> no signal -> re-propose (conservative default).
        assert not _reproposal_is_skippable(set())


class TestSkipProseReproposalFlagWiring:
    """Opp 3 promotion: ``--no-skip-prose-reproposal`` toggles the
    ``create_plan(skip_prose_reproposal=...)`` kwarg; default is ON."""

    def _captured_kwarg(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        extra_args: list[str],
    ) -> object:
        from plan_tool.cli import app as cli_module

        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        manifest = tmp_path / "m.json"
        source = tmp_path / "canonical.md"
        source.write_text(_CANONICAL_BODY, encoding="utf-8")

        captured: dict = {}
        original_create_plan = cli_module.create_plan
        answers = _basic_metadata_answers()

        def recording_invoker(prompt: str) -> str:
            if "Distill a free-form seed" in prompt:
                return _valid_preparation_response(prompt)
            if "Synthesize plan body sections" in prompt:
                return _SYNTHESIS_NULL_JSON
            if "Propose an initial plan step-list" in prompt:
                return _ONE_STEP_JSON
            return "[]"

        def patched(*args, **kwargs):
            captured.update(kwargs)
            kwargs.setdefault("input_fn", _queue_input(answers))
            kwargs["claude_invoker"] = recording_invoker
            return original_create_plan(*args, **kwargs)

        monkeypatch.setattr("plan_tool.cli.authoring.create_plan", patched)
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "create", "demo",
                "--from-existing", str(source),
                "--output-dir", str(out_dir),
                "--no-distill", "--no-iterate",
                *extra_args,
            ]
        )
        assert rc == 0
        return captured["skip_prose_reproposal"]

    def test_default_is_skip_on(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert self._captured_kwarg(tmp_path, monkeypatch, []) is True

    def test_flag_disables_skip(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert (
            self._captured_kwarg(
                tmp_path, monkeypatch, ["--no-skip-prose-reproposal"]
            )
            is False
        )


# --- Prompt-budget advisory across the create wizard's prose-heavy phases ---
#
# Step 4 wires the step-1 prompt-budget leaf into ``propose_distilled_seed_from_claude``,
# ``propose_steps_from_claude``, and ``propose_body_sections`` — one shared helper
# (``_maybe_warn_create_budget``) fired once per invoked phase, before the send.
# These tests spy on the module-level ``maybe_warn_prompt_budget`` /
# ``record_prompt_budget`` names on ``plan_tool.create`` and drive each phase
# directly with a fake invoker + a ``NullReporter``.

import dataclasses  # noqa: E402

from plan_tool.create import (  # noqa: E402
    _DISTILL_SEED_CHECKPOINT_NAME,
    _distill_seed_input_hash,
)
from plan_tool.prompt_budget import estimate_prompt_budget  # noqa: E402

_DISTILL_SECTION_KEYS = [
    "Overview",
    "Problem statement",
    "Architecture",
    "Out of scope",
    "Risks",
    "Testing",
    "Acceptance criteria",
    "Deferred",
]


def _distill_single_json() -> str:
    """A valid single-outcome distill response (all sections filled)."""
    return json.dumps(
        {
            "outcome": "single",
            "sections": {
                k: f"{k} body — see `src/app.py`." for k in _DISTILL_SECTION_KEYS
            },
            "evidence_spans": {
                key: [{"start_line": 1, "end_line": 1}]
                for key in _DISTILL_SECTION_KEYS
                if key not in {"Overview", "Problem statement", "Architecture"}
            },
        }
    )


class _WarnSpy:
    """Records each advisory call and returns a budget at a forced level."""

    def __init__(self, level: str = "warn") -> None:
        self.level = level
        self.calls: list[dict] = []

    def __call__(
        self, total_bytes, *, context_window=None, blocks=None, surface=""
    ):
        self.calls.append(
            {
                "total_bytes": total_bytes,
                "context_window": context_window,
                "blocks": list(blocks) if blocks else [],
                "surface": surface,
            }
        )
        budget = estimate_prompt_budget(
            total_bytes, context_window=context_window, blocks=blocks
        )
        return dataclasses.replace(budget, level=self.level)


class _RecordSpy:
    def __init__(self, raises: bool = False) -> None:
        self.calls: list[dict] = []
        self._raises = raises

    def __call__(self, repo_root, **kwargs):
        self.calls.append({"repo_root": repo_root, **kwargs})
        if self._raises:
            raise RuntimeError("telemetry write failed")


def _install_budget_spies(
    monkeypatch: pytest.MonkeyPatch,
    *,
    level: str = "warn",
    record_raises: bool = False,
) -> tuple[_WarnSpy, _RecordSpy]:
    from plan_tool import create as create_module

    warn_spy = _WarnSpy(level=level)
    record_spy = _RecordSpy(raises=record_raises)
    monkeypatch.setattr(create_module, "maybe_warn_prompt_budget", warn_spy)
    monkeypatch.setattr(create_module, "record_prompt_budget", record_spy)
    return warn_spy, record_spy


class TestCreatePromptBudgetAdvisory:
    def _install_fake_shell(
        self,
        monkeypatch: pytest.MonkeyPatch,
        stdout: str,
        records: list[dict] | None = None,
    ) -> list[dict]:
        from types import SimpleNamespace

        from plan_tool import backend_runner, shell as shell_module
        from plan_tool.backend import PromptTransport
        from subprocess_doubles import _FakeProc

        shell_records = records if records is not None else []
        fake_backend = SimpleNamespace(
            name="claude",
            binary="claude",
            batch_transport=lambda p: PromptTransport(["claude", "-p", p]),
            batch_output="stdout",
            parse_stream_line=lambda line, *, bytes_in: None,
        )
        monkeypatch.setattr(
            shell_module, "get_active_backend", lambda: fake_backend
        )
        monkeypatch.setattr(
            backend_runner, "get_active_backend", lambda: fake_backend
        )
        monkeypatch.setattr(
            shell_module.shutil, "which", lambda _name: "/usr/bin/claude"
        )
        real_popen = backend_runner.subprocess.Popen

        def fake_popen(argv, **kwargs):
            if argv and argv[0] == "git":
                return real_popen(argv, **kwargs)
            return _FakeProc(stdout.splitlines(keepends=True), [], 0)

        monkeypatch.setattr(backend_runner.subprocess, "Popen", fake_popen)
        monkeypatch.setattr(
            shell_module,
            "record_prompt_budget",
            lambda *a, **k: shell_records.append({"source": "shell", **dict(k)}),
        )
        return shell_records

    # --- distill ---------------------------------------------------------
    def test_distill_warns_before_invoke(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        warn_spy, _ = _install_budget_spies(monkeypatch)
        seen: dict[str, str] = {}

        def invoker(prompt: str) -> str:
            seen["prompt"] = prompt
            return _distill_single_json()

        outcome = propose_distilled_seed_from_claude(
            "raw seed prose", invoker, reporter=NullReporter()
        )
        assert not outcome.is_split
        assert len(warn_spy.calls) == 1
        call = warn_spy.calls[0]
        assert call["total_bytes"] == len(seen["prompt"].encode("utf-8"))
        block_names = [name for name, _ in call["blocks"]]
        assert block_names == ["seed"]

    def test_distill_records_prompt_budget(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / ".git").mkdir()
        warn_spy, record_spy = _install_budget_spies(monkeypatch, level="high")
        propose_distilled_seed_from_claude(
            "raw seed prose",
            lambda prompt: _distill_single_json(),
            reporter=NullReporter(),
            repo_root=tmp_path,
        )
        assert len(record_spy.calls) == 1
        rec = record_spy.calls[0]
        assert rec["phase"] == "create-distill"
        assert rec["advisory"] == "high"

    def test_distill_shell_invoker_records_named_budget_only(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.backend import spawn_cwd
        from plan_tool import create as create_module
        from plan_tool.create import shell_claude_invoker

        (tmp_path / ".git").mkdir()
        _install_budget_spies(monkeypatch)
        records: list[dict] = []
        monkeypatch.setattr(
            create_module,
            "record_prompt_budget",
            lambda *a, **k: records.append({"source": "create", **dict(k)}),
        )
        self._install_fake_shell(monkeypatch, _distill_single_json(), records)

        with spawn_cwd(tmp_path):
            outcome = propose_distilled_seed_from_claude(
                "raw seed prose",
                shell_claude_invoker,
                reporter=NullReporter(),
                repo_root=tmp_path,
            )

        assert not outcome.is_split
        assert [rec["phase"] for rec in records] == ["create-distill"]
        assert [rec["source"] for rec in records] == ["create"]

    # --- steps -----------------------------------------------------------
    def test_steps_warns_before_invoke(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        warn_spy, _ = _install_budget_spies(monkeypatch)
        canned = _ONE_STEP_JSON
        steps = propose_steps_from_claude(
            "build a thing", lambda prompt: canned, reporter=NullReporter()
        )
        assert steps is not None
        assert len(warn_spy.calls) == 1
        block_names = [name for name, _ in warn_spy.calls[0]["blocks"]]
        assert "description" in block_names

    def test_steps_records_prompt_budget_phase(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / ".git").mkdir()
        _, record_spy = _install_budget_spies(monkeypatch)
        canned = _ONE_STEP_JSON
        propose_steps_from_claude(
            "build a thing",
            lambda prompt: canned,
            reporter=NullReporter(),
            repo_root=tmp_path,
        )
        assert len(record_spy.calls) == 1
        assert record_spy.calls[0]["phase"] == "create-steps"

    def test_steps_shell_invoker_records_named_budget_only(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.backend import spawn_cwd
        from plan_tool import create as create_module
        from plan_tool.create import shell_claude_invoker

        (tmp_path / ".git").mkdir()
        _install_budget_spies(monkeypatch)
        canned = _ONE_STEP_JSON
        records: list[dict] = []
        monkeypatch.setattr(
            create_module,
            "record_prompt_budget",
            lambda *a, **k: records.append({"source": "create", **dict(k)}),
        )
        self._install_fake_shell(monkeypatch, canned, records)

        with spawn_cwd(tmp_path):
            steps = propose_steps_from_claude(
                "build a thing",
                shell_claude_invoker,
                reporter=NullReporter(),
                repo_root=tmp_path,
            )

        assert steps is not None
        assert [rec["phase"] for rec in records] == ["create-steps"]
        assert [rec["source"] for rec in records] == ["create"]

    def test_steps_repair_send_measured_by_create_surface_not_backstop(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The parse-repair retry is measured by the named create surface
        against its OWN (larger) prompt and the generic shell backstop is
        suppressed — so both sends record under ``create-steps`` and neither
        leaks a mislabeled generic ``shell-backstop`` advisory."""
        from types import SimpleNamespace

        from plan_tool.backend import PromptTransport, spawn_cwd
        from plan_tool import backend_runner
        from plan_tool import shell as shell_module
        from plan_tool import create as create_module
        from plan_tool.create import shell_claude_invoker
        from subprocess_doubles import _FakeProc

        (tmp_path / ".git").mkdir()
        _install_budget_spies(monkeypatch)  # create record succeeds → covered
        records: list[dict] = []
        monkeypatch.setattr(
            create_module,
            "record_prompt_budget",
            lambda *a, **k: records.append({"source": "create", **dict(k)}),
        )
        # First send: an invalid graph → triggers the repair retry. Second
        # send (the repair): a valid graph.
        bad = json.dumps(
            [{"title": "only", "complexity": None, "files": [], "depends_on": [99]}]
        )
        good = json.dumps(
            [{"title": "first", "complexity": "low", "files": [], "depends_on": []}]
        )
        responses = [bad, good]
        fake_backend = SimpleNamespace(
            name="claude",
            binary="claude",
            batch_transport=lambda p: PromptTransport(["claude", "-p", p]),
            batch_output="stdout",
            parse_stream_line=lambda line, *, bytes_in: None,
        )
        monkeypatch.setattr(
            shell_module, "get_active_backend", lambda: fake_backend
        )
        monkeypatch.setattr(
            backend_runner, "get_active_backend", lambda: fake_backend
        )
        monkeypatch.setattr(
            shell_module.shutil, "which", lambda _name: "/usr/bin/claude"
        )
        real_popen = backend_runner.subprocess.Popen

        def fake_popen(argv, **kwargs):
            if argv and argv[0] == "git":
                return real_popen(argv, **kwargs)
            return _FakeProc(responses.pop(0).splitlines(keepends=True), [], 0)

        monkeypatch.setattr(backend_runner.subprocess, "Popen", fake_popen)
        monkeypatch.setattr(
            shell_module,
            "record_prompt_budget",
            lambda *a, **k: records.append({"source": "shell", **dict(k)}),
        )

        with spawn_cwd(tmp_path):
            steps = propose_steps_from_claude(
                "build a thing",
                shell_claude_invoker,
                reporter=NullReporter(),
                repo_root=tmp_path,
            )

        assert steps is not None  # recovered on the repair retry
        assert responses == []  # both the original AND the repair send fired
        # Both the primary AND the repair send are measured by the create
        # surface (the repair against its own larger prompt); neither leaked a
        # generic shell-backstop record.
        assert [rec["source"] for rec in records] == ["create", "create"]
        assert all(rec["phase"] == "create-steps" for rec in records)
        # The repair prompt is the larger of the two (it appends the rejected
        # response), so its recorded byte count exceeds the primary's.
        assert records[1]["total_bytes"] > records[0]["total_bytes"]

    def test_reference_repair_records_named_budget_and_suppresses_backstop(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The generic-reference repair measures its own larger prompt."""
        from contextlib import contextmanager

        from plan_tool import create as create_module

        (tmp_path / ".git").mkdir()
        warn_spy, record_spy = _install_budget_spies(monkeypatch)
        backstop_active: list[bool] = []

        @contextmanager
        def capture_backstop(*, active: bool):
            backstop_active.append(active)
            yield

        monkeypatch.setattr(
            create_module, "suppress_prompt_budget_backstop", capture_backstop
        )
        prompts: list[str] = []

        def invoker(prompt: str) -> str:
            prompts.append(prompt)
            return "not JSON" if len(prompts) == 1 else "[]"

        result = propose_references_from_claude(
            "My Plan",
            "build a thing",
            invoker,
            reporter=NullReporter(),
            slug="demo",
            output_dir=tmp_path,
            repo_root=tmp_path,
        )

        assert result.outcome == "empty"
        assert len(prompts) == 2
        assert len(warn_spy.calls) == 1
        assert warn_spy.calls[0]["total_bytes"] == len(prompts[1].encode("utf-8"))
        assert warn_spy.calls[0]["blocks"] == [
            ("rejected-response", len("not JSON".encode("utf-8")))
        ]
        assert [record["phase"] for record in record_spy.calls] == [
            "create-references"
        ]
        assert backstop_active == [True]

    def test_reference_repair_send_measured_by_create_surface_not_backstop(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Same claim as the spy-based test above, proven against the REAL
        ``suppress_prompt_budget_backstop`` context-var wiring (not a bare
        recorder standing in for it): the repair send suppresses the generic
        shell-sourced backstop record, while the (currently uncovered)
        primary send still falls back to it — so both sends land under a
        distinct, verifiable source rather than only proving the call shape."""
        from types import SimpleNamespace

        from plan_tool.backend import PromptTransport, spawn_cwd
        from plan_tool import backend_runner
        from plan_tool import shell as shell_module
        from plan_tool import create as create_module
        from plan_tool.create import shell_claude_invoker
        from subprocess_doubles import _FakeProc

        (tmp_path / ".git").mkdir()
        _install_budget_spies(monkeypatch)  # create record succeeds → covered
        records: list[dict] = []
        monkeypatch.setattr(
            create_module,
            "record_prompt_budget",
            lambda *a, **k: records.append({"source": "create", **dict(k)}),
        )
        monkeypatch.setattr(
            shell_module,
            "record_prompt_budget",
            lambda *a, **k: records.append({"source": "shell", **dict(k)}),
        )
        # First send: unparseable → triggers the repair retry. Second send
        # (the repair): a valid (empty) reference array.
        responses = ["not JSON", "[]"]
        fake_backend = SimpleNamespace(
            name="claude",
            binary="claude",
            batch_transport=lambda p: PromptTransport(["claude", "-p", p]),
            batch_output="stdout",
            parse_stream_line=lambda line, *, bytes_in: None,
        )
        monkeypatch.setattr(
            shell_module, "get_active_backend", lambda: fake_backend
        )
        monkeypatch.setattr(
            backend_runner, "get_active_backend", lambda: fake_backend
        )
        monkeypatch.setattr(
            shell_module.shutil, "which", lambda _name: "/usr/bin/claude"
        )
        real_popen = backend_runner.subprocess.Popen

        def fake_popen(argv, **kwargs):
            if argv and argv[0] == "git":
                return real_popen(argv, **kwargs)
            return _FakeProc(responses.pop(0).splitlines(keepends=True), [], 0)

        monkeypatch.setattr(backend_runner.subprocess, "Popen", fake_popen)

        with spawn_cwd(tmp_path):
            result = propose_references_from_claude(
                "My Plan",
                "build a thing",
                shell_claude_invoker,
                reporter=NullReporter(),
                slug="demo",
                output_dir=tmp_path,
                repo_root=tmp_path,
            )

        assert result.outcome == "empty"
        assert responses == []  # both the primary AND the repair send fired
        # The primary send has no scoped coverage today (see the header
        # comment on ``_maybe_warn_create_budget``), so it falls back to the
        # generic shell-backstop record; the repair send IS scoped-covered,
        # so it suppresses that backstop and records under the create
        # surface instead. A broken ``suppress_prompt_budget_backstop``
        # wiring would leak a second "shell" record here and fail this
        # assertion, which a bare recorder standing in for the context
        # manager cannot detect.
        assert [rec["source"] for rec in records] == ["shell", "create"]
        assert records[1]["phase"] == "create-references"

    def test_steps_backstop_is_fallback_when_advisory_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When the scoped create advisory raises (and is swallowed), the send
        is NOT suppressed, so the generic shell backstop stays a fallback net
        instead of leaving the prompt with zero budget coverage."""
        from plan_tool.backend import spawn_cwd
        from plan_tool import create as create_module
        from plan_tool.create import shell_claude_invoker

        (tmp_path / ".git").mkdir()
        # Warn succeeds (returns a budget) but the scoped record raises →
        # _maybe_warn_create_budget swallows it and returns False (not covered).
        _install_budget_spies(monkeypatch)
        records: list[dict] = []
        monkeypatch.setattr(
            create_module,
            "record_prompt_budget",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        canned = _ONE_STEP_JSON
        self._install_fake_shell(monkeypatch, canned, records)

        with spawn_cwd(tmp_path):
            steps = propose_steps_from_claude(
                "build a thing",
                shell_claude_invoker,
                reporter=NullReporter(),
                repo_root=tmp_path,
            )

        assert steps is not None
        # The scoped create record raised → the shell backstop fired instead.
        assert [rec["source"] for rec in records] == ["shell"]
        assert records[0]["phase"] == "shell-backstop"

    # --- synthesis -------------------------------------------------------
    def test_synthesis_warns_before_invoke(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        warn_spy, _ = _install_budget_spies(monkeypatch)
        result = propose_body_sections(
            "seed prose",
            lambda prompt: _full_body_json(),
            reporter=NullReporter(),
        )
        assert set(result.keys()) == set(_BODY_CANONICAL_KEYS)
        assert len(warn_spy.calls) == 1
        block_names = [name for name, _ in warn_spy.calls[0]["blocks"]]
        assert "seed" in block_names

    def test_synthesis_records_prompt_budget_phase(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / ".git").mkdir()
        _, record_spy = _install_budget_spies(monkeypatch)
        propose_body_sections(
            "seed prose",
            lambda prompt: _full_body_json(),
            reporter=NullReporter(),
            repo_root=tmp_path,
        )
        assert len(record_spy.calls) == 1
        assert record_spy.calls[0]["phase"] == "create-synthesis"

    def test_synthesis_shell_invoker_records_named_budget_only(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.backend import spawn_cwd
        from plan_tool import create as create_module
        from plan_tool.create import shell_claude_invoker

        (tmp_path / ".git").mkdir()
        _install_budget_spies(monkeypatch)
        records: list[dict] = []
        monkeypatch.setattr(
            create_module,
            "record_prompt_budget",
            lambda *a, **k: records.append({"source": "create", **dict(k)}),
        )
        self._install_fake_shell(monkeypatch, _full_body_json(), records)

        with spawn_cwd(tmp_path):
            result = propose_body_sections(
                "seed prose",
                shell_claude_invoker,
                reporter=NullReporter(),
                repo_root=tmp_path,
            )

        assert result["Overview"] == "body for Overview"
        assert [rec["phase"] for rec in records] == ["create-synthesis"]
        assert [rec["source"] for rec in records] == ["create"]

    # --- cross-cutting invariants ---------------------------------------
    def test_advisory_does_not_change_result(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With the level forced to ``high``, every phase still returns its
        normal result and still invokes."""
        _install_budget_spies(monkeypatch, level="high")

        distill_calls = {"n": 0}

        def distill_invoker(prompt: str) -> str:
            distill_calls["n"] += 1
            return _distill_single_json()

        outcome = propose_distilled_seed_from_claude(
            "raw seed", distill_invoker, reporter=NullReporter()
        )
        assert distill_calls["n"] == 1 and not outcome.is_split

        steps = propose_steps_from_claude(
            "build a thing",
            lambda p: _ONE_STEP_JSON,
            reporter=NullReporter(),
        )
        assert steps is not None and [s.title for s in steps] == ["one"]

        result = propose_body_sections(
            "seed prose", lambda p: _full_body_json(), reporter=NullReporter()
        )
        assert set(result.keys()) == set(_BODY_CANONICAL_KEYS)

    def test_resumed_phase_does_not_warn_or_record(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / ".git").mkdir()
        out_dir = tmp_path / "plans"
        out_dir.mkdir()
        warn_spy, record_spy = _install_budget_spies(monkeypatch)

        ckpt = checkpoint_path(tmp_path, "demo", _BODY_SECTIONS_CHECKPOINT_NAME)
        save_checkpoint(
            ckpt,
            Checkpoint(
                input_hash=_body_sections_input_hash(
                    "demo", "seed prose", out_dir, tmp_path
                ),
                payload=_full_body_json(),
                created_at=_now_iso(),
            ),
        )

        def explode(prompt: str) -> str:
            raise AssertionError("invoker must not fire on a cache hit")

        result = propose_body_sections(
            "seed prose",
            explode,
            reporter=NullReporter(),
            slug="demo",
            output_dir=out_dir,
            repo_root=tmp_path,
        )
        assert result["Overview"] == "body for Overview"
        assert warn_spy.calls == []
        assert record_spy.calls == []

    def test_repair_retry_measures_its_own_larger_prompt(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Each send is measured against ITS OWN prompt: the repair retry
        appends the full rejected response, so — unlike detail's tiny-suffix
        retry — it can be materially larger and gets its own scoped advisory
        (the stderr warn still only fires at warn/high, so a normal repair
        stays silent). Prevents a large repair from sending uncovered."""
        warn_spy, _ = _install_budget_spies(monkeypatch)
        counter = {"n": 0}

        def invoker(prompt: str) -> str:
            counter["n"] += 1
            # First attempt fails to parse; the repair retry succeeds.
            return "garbage" if counter["n"] == 1 else _full_body_json()

        result = propose_body_sections(
            "seed prose", invoker, reporter=NullReporter()
        )
        assert counter["n"] == 2  # initial + one repair retry
        assert result["Overview"] == "body for Overview"
        # Both sends measured; the repair prompt (embeds the rejected response)
        # is the larger of the two.
        assert len(warn_spy.calls) == 2
        assert warn_spy.calls[1]["total_bytes"] > warn_spy.calls[0]["total_bytes"]

    def test_advisory_never_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / ".git").mkdir()
        # The recorder raises; the shared helper must swallow it.
        _install_budget_spies(monkeypatch, record_raises=True)
        result = propose_body_sections(
            "seed prose",
            lambda p: _full_body_json(),
            reporter=NullReporter(),
            repo_root=tmp_path,
        )
        assert set(result.keys()) == set(_BODY_CANONICAL_KEYS)

    def test_no_record_when_repo_root_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        warn_spy, record_spy = _install_budget_spies(monkeypatch)
        propose_body_sections(
            "seed prose",
            lambda p: _full_body_json(),
            reporter=NullReporter(),
            repo_root=None,
        )
        assert len(warn_spy.calls) == 1  # warns
        assert record_spy.calls == []  # but records nothing without a root


def test_seed_section_transfer_uses_real_headings_and_preserves_fenced_examples() -> None:
    from plan_tool.create import _extract_supplied_guardrails, _render_plan_body

    seed = (
        "## Scope guardrails\n\n"
        "Keep the source example.\n\n```markdown\n"
        "## Expected placement\nExample-only placement.\n```\n\n"
        "## Expected placement\n\nUse the real module boundary.\n"
    )

    rendered = _render_plan_body(
        "Fence-safe transfer",
        supplied_guardrails=_extract_supplied_guardrails(seed),
    )

    assert "## Expected placement\nExample-only placement." in rendered
    assert "Use the real module boundary." in rendered


def test_architecture_code_anchors_ignore_fenced_inline_code() -> None:
    from plan_tool.create import _architecture_code_anchors

    anchors = _architecture_code_anchors(
        "## Architecture\n\n```markdown\n"
        "Call `example_only_anchor`.\n```\n\n"
        "Call `real_anchor`.\n"
    )

    assert [anchor.mention for anchor in anchors] == ["real_anchor"]


def test_dropped_reference_matching_ignores_fenced_artifact_examples() -> None:
    from plan_tool.create import find_dropped_references

    fenced_reference = (
        "## Risks\n\n```markdown\noperator cutover runbook\n```\n\n"
        "## Acceptance criteria\n\nNo artifact requirement.\n"
    )
    fenced_corroboration = (
        "## Risks\n\noperator cutover runbook\n\n"
        "## Acceptance criteria\n\n```markdown\nrunbook\n```\n"
    )

    assert find_dropped_references(fenced_reference) == []
    assert [reference.keyword for reference in find_dropped_references(fenced_corroboration)] == [
        "runbook"
    ]


def test_from_existing_reference_eligibility_ignores_fenced_example() -> None:
    with pytest.raises(CreateError, match=r"non-placeholder `## References`"):
        validate_from_existing_seed(
            "## References\n\n```markdown\n"
            "- [Example](https://example.test/reference)\n```\n"
        )

    validate_from_existing_seed(
        "## References\n\n"
        "- [Real](https://example.test/reference)\n"
    )


def test_create_rejects_unmatched_seed_before_authoring_work(tmp_path: Path) -> None:
    with pytest.raises(CreateError, match="unmatched opening code fence"):
        create_plan(
            "unsafe-seed",
            repo_root=tmp_path,
            from_description="## References\n\n```\n",
            claude_invoker=lambda _prompt: pytest.fail("model must not run"),
        )

    assert not (tmp_path / "docs" / "implementation-plans").exists()


@pytest.mark.parametrize(
    ("seed_body", "from_description"),
    [
        (
            "## References\n\n- [Real](https://example.test/reference)\n",
            "## Summary\n\n```\n",
        ),
        (
            "## References\n\n```\n",
            "## References\n\n- [Real](https://example.test/reference)\n",
        ),
    ],
)
def test_create_preflights_each_raw_source_before_model_or_write(
    tmp_path: Path, seed_body: str, from_description: str
) -> None:
    with pytest.raises(CreateError, match="unmatched opening code fence"):
        create_plan(
            "unsafe-source",
            repo_root=tmp_path,
            from_existing_path=tmp_path / "source.md",
            seed_body=seed_body,
            from_description=from_description,
            claude_invoker=lambda _prompt: pytest.fail("model must not run"),
        )

    assert not (tmp_path / "docs" / "implementation-plans").exists()


def test_synthesize_body_prompt_has_a_writing_style_section() -> None:
    """The plan body is what a reviewer reads, so synthesis carries a wording
    section. Its wording quality is judged by review; only the heading and the
    one carve-out sentence that limits rewording are pinned."""
    from plan_tool.renderer import prompts_dir

    text = (prompts_dir() / "synthesize-body.md").read_text(encoding="utf-8")
    assert "## Writing style" in text
    # The carve-out that keeps seed-supplied scope text from being paraphrased.
    assert "Reword only a `[derive from intent]` section that you author" in text


@pytest.mark.parametrize("explicit_body", [None, "- Product disclosure"])
@pytest.mark.parametrize("preserve_source", [False, True])
def test_local_references_accompany_research_only_for_protected_sources(
    explicit_body, preserve_source,
):
    local = "- `src/api.py#handler` — SOURCE-42 proof notes"
    body = create_module._render_plan_body(
        "References",
        references=[Reference(title="Docs", url="https://example.test/docs")],
        references_body=explicit_body,
        seed_sections={"references": local},
        preserve_source_sections=preserve_source,
    )
    assert (local in body) is preserve_source
    assert (explicit_body or "https://example.test/docs") in body


def test_normalized_local_references_restore_without_erasing_refreshed_research(tmp_path):
    path = tmp_path / "plan.md"
    local = "- `local.py#proof` — SOURCE-7 explanation"
    path.write_text("---\ntitle: Test\n---\n## References\n\n- Refreshed research\n", encoding="utf-8")
    sections = {"References": local}
    assert create_module._restore_materialized_evidence_sections(path, sections)
    assert local in path.read_text(encoding="utf-8")
    assert "Refreshed research" in path.read_text(encoding="utf-8")
    assert not create_module._restore_materialized_evidence_sections(path, sections)
    path.write_text("---\ntitle: Test\n---\n## Overview\n\nRetained plan\n", encoding="utf-8")
    assert create_module._restore_materialized_evidence_sections(path, sections)
    assert local in path.read_text(encoding="utf-8")


def test_local_reference_is_not_judged_present_because_it_is_a_substring_of_other_text(tmp_path):
    """Presence is whole-line equality: a fragment of unrelated prose must not drop protected References."""
    local = "- a.py"
    path = tmp_path / "plan.md"
    path.write_text("---\ntitle: Test\n---\n## References\n\n- a.py.bak is unrelated research\n", encoding="utf-8")
    assert create_module._restore_materialized_evidence_sections(path, {"References": local})
    assert path.read_text(encoding="utf-8").splitlines().count("- a.py") == 1
    body = create_module._render_plan_body(
        "References",
        references=[Reference(title="Docs", url="https://example.test/a.py.bak")],
        seed_sections={"references": local},
        preserve_source_sections=True,
    )
    assert body.splitlines().count("- a.py") == 1


def test_protected_references_are_restored_as_a_verbatim_block_exactly_once(tmp_path):
    """Indented lines and fenced blocks survive intact; a re-run changes nothing."""
    block = "- a.py\n  - nested note\n```\ncmd\n```"
    path = tmp_path / "plan.md"
    path.write_text(
        "---\ntitle: Test\n---\n## References\n\n- a.py\n```\nother\n```\n", encoding="utf-8"
    )
    sections = {"References": block}
    assert create_module._restore_materialized_evidence_sections(path, sections)
    text = path.read_text(encoding="utf-8")
    assert "\n" + block + "\n" in text
    assert not create_module._restore_materialized_evidence_sections(path, sections)
    assert path.read_text(encoding="utf-8") == text


def test_missing_references_section_is_restored_in_canonical_order(tmp_path):
    """A deleted References section returns before Steps, not after Deferred."""
    path = tmp_path / "plan.md"
    path.write_text(
        "---\ntitle: Test\n---\n## Overview\n\nO\n\n## Steps\n\nS\n\n## Deferred\n\nD\n",
        encoding="utf-8",
    )
    local = "- `local.py#proof` — SOURCE-9"
    assert create_module._restore_materialized_evidence_sections(path, {"References": local})
    text = path.read_text(encoding="utf-8")
    assert text.index("## Overview") < text.index("## References") < text.index("## Steps")
    assert text.index("## Steps") < text.index("## Deferred")


def test_empty_references_heading_is_filled_in_place_and_frontmatter_is_never_an_anchor(tmp_path):
    """No duplicate heading for an emptied section; a '## Steps' line in frontmatter is not an insertion point."""
    path = tmp_path / "plan.md"
    path.write_text(
        "---\ntitle: Test\nnote: |\n  x\n## Steps\n---\n## References\n\n## Steps\n\nS\n",
        encoding="utf-8",
    )
    assert create_module._restore_materialized_evidence_sections(path, {"References": "- r.py"})
    text = path.read_text(encoding="utf-8")
    assert text.count("## References") == 1 and "- r.py" in text
    path.write_text("---\ntitle: Test\nnote: |\n  x\n## Steps\n---\n## Overview\n\nO\n\n## Steps\n\nS\n", encoding="utf-8")
    assert create_module._restore_materialized_evidence_sections(path, {"References": "- r.py"})
    text = path.read_text(encoding="utf-8")
    front, body = text.split("\n---\n", 2)[0], text.split("\n---\n", 2)[1]
    assert "## References" not in front
    assert body.index("## Overview") < body.index("## References") < body.index("## Steps")


def test_restored_references_ignore_a_fenced_later_heading_and_fall_back_to_end_of_file(tmp_path):
    """A '## Steps' inside a code fence is not an anchor; with no later section the heading goes last."""
    path = tmp_path / "plan.md"
    path.write_text(
        "---\ntitle: Test\n---\n## Overview\n\n```\n## Steps\n```\n",
        encoding="utf-8",
    )
    assert create_module._restore_materialized_evidence_sections(path, {"References": "- r.py"})
    text = path.read_text(encoding="utf-8")
    assert text.index("```\n## Steps\n```") < text.index("## References")
    assert text.rstrip().endswith("- r.py")


@pytest.fixture
def normalized_reference_create(tmp_path, monkeypatch):
    """Exercise real preparation checkpoints with isolated authoring responses."""
    (tmp_path / ".git").mkdir()
    source = tmp_path / "source.md"
    source.write_text(
        "Build source context.\n\n"
        + "\n\n".join(
            f"## {key}\n\n{key} source proof."
            for key in _PREPARATION_EVIDENCE_KEYS
        )
        + "\n\n## References\n\n- `current.py#proof` — CURRENT-SOURCE\n",
        encoding="utf-8",
    )
    state = {"preparations": 0, "research": 0, "fail_steps": False}

    def invoker(prompt):
        if "Distill a free-form seed" in prompt:
            state["preparations"] += 1
            return _valid_preparation_response(prompt)
        if "developer and API reference documentation" in prompt:
            state["research"] += 1
            return _REF_JSON if state["research"] == 1 else _REF_JSON_ITER
        if state["fail_steps"]:
            raise CreateError("interrupted after preparation")
        return _STEP_JSON

    monkeypatch.setattr(
        create_module, "_propose_risk_profile_from_seed",
        lambda *_a, **_kw: create_module._RiskProfileProposal(
            profile=RiskProfile.STANDARD, rationale="test", minimum_profile=RiskProfile.STANDARD,
        ),
    )
    monkeypatch.setattr(
        create_module, "_resolve_risk_declaration",
        lambda proposal, **_kw: create_module._RiskDeclaration(
            profile=proposal.profile, rationale=proposal.rationale, mode="test",
        ),
    )
    monkeypatch.setattr(create_module, "_review_step_change_types", lambda steps, **_kw: steps)
    monkeypatch.setattr(create_module, "_review_create_concepts", lambda tree, steps, **_kw: (tree, steps))

    def create(**overrides):
        arguments = dict(
            repo_root=tmp_path, output_dir_override=tmp_path / "plans",
            manifest_path=tmp_path / "manifest.json", from_description=source.read_text(),
            from_existing_path=source, yes=True, resume=True, offer_intents=False,
            fetch_docs=False, claude_invoker=invoker,
        )
        arguments.update(overrides)
        return create_plan("reference-context", **arguments)

    return source, state, create


@pytest.mark.integration
def test_resume_reuses_preparation_but_invalidates_it_for_changed_selected_source(
    normalized_reference_create,
):
    source, state, create = normalized_reference_create
    state["fail_steps"] = True
    for _ in range(2):
        with pytest.raises(CreateError, match="interrupted after preparation"):
            create()
    assert state["preparations"] == 1  # The second call really loads the checkpoint.
    stale = source.read_text()
    selected = stale.replace("current.py#proof", "replacement.py#proof").replace(
        "CURRENT-SOURCE", "REPLACEMENT-SOURCE"
    )
    source.write_text(selected)
    state["fail_steps"] = False
    result = create(from_description=stale, seed_body=selected)
    assert state["preparations"] == 2
    body = result.plan_path.read_text()
    assert "replacement.py#proof" in body and "REPLACEMENT-SOURCE" in body
    assert "current.py#proof" not in body and "CURRENT-SOURCE" not in body
    assert "Testing source proof." in body


@pytest.mark.integration
def test_normalized_create_refreshes_research_and_finalizes_with_source_context(
    normalized_reference_create, monkeypatch,
):
    _source, state, create = normalized_reference_create
    checks = {"count": 0}

    def findings(*_a, **_kw):
        checks["count"] += 1
        return [_rec("refresh-references")] if checks["count"] == 1 else []

    monkeypatch.setattr(create_module, "collect_deterministic_findings", findings)
    monkeypatch.setattr(create_module, "apply_finding", lambda *_a, **_kw: _stub_apply_result())
    result = create(
        budget=create_module.IterativeBudget(enabled=True, max_iterations=3),
        skip_prose_reproposal=False,
    )
    assert result.iteration_stage_failure is None
    assert state["research"] == 2
    body = result.plan_path.read_text()
    assert "current.py#proof" in body and "CURRENT-SOURCE" in body
    assert "Testing source proof." in body
    assert "Acceptance criteria source proof." in body
    assert "https://updated.example.com" in body


class TestProposalDescriptionAlias:
    @pytest.mark.parametrize("omit_foundational_item", [False, True])
    def test_step_proposal_contract_requests_description_in_both_prompt_arms(
        self, omit_foundational_item: bool
    ) -> None:
        prompt = _render_from_prompt("Build it", omit_foundational_item=omit_foundational_item)
        assert '"description": "plain-language step description"' in prompt
        assert "Write every `description`" in prompt
        assert '"title"' not in prompt
        assert "`title`" not in prompt

    @pytest.mark.parametrize("keys", [
        {"description": "  Keep text exactly  "},
        {"title": "  Keep text exactly  "},
        {"description": "  Keep text exactly  ", "title": "  Keep text exactly  "},
    ])
    def test_proposal_accepts_either_step_text_spelling_without_changing_text(self, keys) -> None:
        steps = _parse_steps_json(json.dumps([keys]))
        assert steps is not None
        assert steps[0].title == "  Keep text exactly  "

    @pytest.mark.parametrize("keys", [
        {}, {"description": ""}, {"title": ""},
        {"description": " \n "}, {"title": " \n "},
        {"description": "one", "title": "two"},
        *[{key: value, other: "valid"}
          for key, other in [("description", "title"), ("title", "description")]
          for value in [None, 1, True, [], {}, "", "  "]],
    ])
    def test_proposal_rejects_missing_blank_conflicting_or_invalid_supplied_text(self, keys) -> None:
        assert _parse_steps_json(json.dumps([keys])) is None

    def test_description_proposal_preserves_other_step_fields(self) -> None:
        rationales = {}
        steps = _parse_steps_json(json.dumps([{
            "description": "Deliver it", "depends_on": ["2", 2],
            "depends_on_notes": {"2": "Use its output"}, "concept_ids": [_CONCEPT_A],
            "intent": "Deliver\nbehavior", "rationale": "  New behavior  ",
            "complexity": "low", "change_type": "unrecognized", "gate": ["untrusted"],
            "files": ["existing.py"], "creates": ["new.py"],
        }]), rationales_out=rationales)
        assert steps is not None
        step = steps[0]
        assert step.depends_on == [2]
        assert step.depends_on_notes == {2: "Use its output"}
        assert step.concept_ids == [_CONCEPT_A]
        assert step.intent == "Deliver behavior"
        assert rationales == {1: "New behavior"}
        assert step.complexity is Complexity.LOW
        assert step.change_type is None
        assert step.gate == []
        assert step.files == ["existing.py"] and step.creates == ["new.py"]
        assert _parse_steps_json('[{"description":"Valid", "complexity":"invalid"}]') is None

    @pytest.mark.parametrize("text_key", ["description", "title"])
    def test_split_proposal_requests_description_and_accepts_either_spelling(self, text_key) -> None:
        prompts = []
        def invoke(prompt):
            prompts.append(prompt)
            return json.dumps([{text_key: "Refactor", "change_type": "refactor"},
                               {text_key: "Feature", "change_type": "feature"}])
        original = Step(id=3, title="Mixed", depends_on=[1])
        pair = _propose_step_split(original, invoke)
        assert pair is not None
        assert '`description`, `change_type`' in prompts[0]
        assert '`title`' not in prompts[0]
        wired = _apply_step_split([Step(id=1, title="Before"), original], 3, pair)
        assert wired[1].title == "Refactor" and wired[1].depends_on == [1]
        assert wired[2].title == "Feature" and wired[2].depends_on == [wired[1].id]


def test_description_steps_preserve_archive_failure_restoration(tmp_path, monkeypatch) -> None:
    steps = _parse_steps_json('[{"description":"Keep this text"}]')
    assert steps is not None
    source = create_module.write_new_plan(
        tmp_path, "demo", Plan(title="Demo", status="planning", priority="medium", steps=steps)
    )
    original = source.read_bytes()
    details = tmp_path / "plan-details" / "demo"
    details.mkdir(parents=True)
    (details / "01-step.md").write_text("detail")

    def fail_publication(*_args):
        raise OSError("publication stopped")

    monkeypatch.setattr(create_module, "_publish_archive_dir", fail_publication)
    result = archive_existing_source(source, tmp_path / "replacement.md", repo_root=tmp_path)
    assert result.skipped and result.archived == []
    assert source.read_bytes() == original
    assert parse_plan(source).steps[0].title == "Keep this text"
    assert (details / "01-step.md").read_text() == "detail"
    assert not list((tmp_path / "archive").rglob("*.md"))
    assert not list((tmp_path / "archive").rglob("*.tmp"))
