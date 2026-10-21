"""Unit tests for the scope-out primitives: the carved-region forward-seed
emitter and the deterministic plan-narrow (drop-renumber + apply/rollback)."""

from __future__ import annotations

import argparse
import dataclasses
import inspect
import json
from pathlib import Path

import pytest
import yaml

import plan_tool.scope_out as scope_out
from plan_tool.create import validate_from_existing_seed
from plan_tool.detail_artifacts import DetailFormatError
from plan_tool.parser import _coerce_enums, parse_plan
from plan_tool.concept_tree import (
    RECORD_KIND_DECISION,
    ConceptNode,
    ConceptTree,
    concept_id,
    load_concepts,
    save_concepts,
)
from plan_tool.review_persistence import compute_plan_fingerprint
from plan_tool.schema import (
    ChangeType,
    Feature,
    Plan,
    PlanStatus,
    Priority,
    Step,
    StepScope,
    StepStatus,
)
from plan_tool.scope_out import (
    NarrowError,
    NarrowResult,
    ScopeOutResult,
    apply_narrow,
    compute_frontmatter_hash,
    compute_narrow,
    find_scope_out_body_hits,
    render_carved_seed,
    render_carved_region_seed,
    scope_out_step,
)


SOURCE = Path("docs/implementation-plans/spinning-plan.md")


def _step(**kwargs) -> Step:
    base = dict(id=3, title="Carved step title")
    base.update(kwargs)
    return Step(**base)


def _render(**overrides) -> str:
    kwargs = dict(
        plan_title="Spinning Plan",
        carved_step=_step(),
        detail_body=None,
        source_path=SOURCE,
    )
    kwargs.update(overrides)
    return render_carved_seed(**kwargs)


def test_scope_block_names_title_files_and_detail():
    step = _step(files=["a.py", "b.py"], creates=["c.py"])
    out = _render(carved_step=step, detail_body="The carved detail body.")
    assert "## Scope to re-plan" in out
    assert "Carved step title" in out
    for path in ("a.py", "b.py", "c.py"):
        assert f"- {path}" in out
    assert "The carved detail body." in out


def test_scope_block_renders_change_type():
    feature = _render(carved_step=_step(change_type=ChangeType.FEATURE))
    assert "Change type: feature" in feature
    none = _render(carved_step=_step(change_type=None))
    assert "Change type: unspecified" in none


def test_scope_block_renders_feature_tags():
    with_tags = _render(carved_step=_step(features=["foo", "bar"]))
    assert "- foo" in with_tags
    assert "- bar" in with_tags
    assert "re-register" in with_tags
    without = _render(carved_step=_step(features=[]))
    assert "re-register" not in without


def test_scope_block_renders_concept_ids_in_authored_order():
    first = "1" * 64
    second = "2" * 64
    out = _render(carved_step=_step(concept_ids=[first, second]))
    assert "Concept IDs owned by this carved step:" in out
    assert out.index(f"- {first}") < out.index(f"- {second}")


def test_scope_block_omits_empty_concept_ids():
    assert "Concept IDs owned by this carved step:" not in _render()


def test_region_seed_keeps_concept_ids_attached_to_source_steps():
    first = "1" * 64
    second = "2" * 64
    out = render_carved_region_seed(
        plan_title="Spinning Plan",
        carved_steps=[
            _step(id=2, title="Alpha", concept_ids=[first]),
            _step(id=3, title="Beta", concept_ids=[second]),
        ],
        detail_bodies=[None, None],
        detail_missings=[False, False],
        source_path=SOURCE,
    )
    alpha, beta = out.split("**Alpha**", 1)[1].split("**Beta**", 1)
    assert first in alpha and second not in alpha
    assert second in beta and first not in beta


def test_scope_block_renders_step_intent():
    out = _render(carved_step=_step(intent="Carve this slice cleanly"))
    scope = out.split("## Scope to re-plan", 1)[1].split("## Done-context", 1)[0]
    assert "Intent: Carve this slice cleanly" in scope


def test_scope_block_omits_absent_step_intent():
    out = _render(carved_step=_step(intent=None))
    scope = out.split("## Scope to re-plan", 1)[1].split("## Done-context", 1)[0]
    assert "Intent:" not in scope


def test_scope_block_omits_blank_step_intent():
    out = _render(carved_step=_step(intent="   \n  "))
    scope = out.split("## Scope to re-plan", 1)[1].split("## Done-context", 1)[0]
    assert "Intent:" not in scope


@pytest.mark.parametrize("placeholder", ["TODO", "_(TODO)_", "(TODO)"])
def test_scope_block_omits_placeholder_step_intent(placeholder):
    out = _render(carved_step=_step(intent=placeholder))
    scope = out.split("## Scope to re-plan", 1)[1].split("## Done-context", 1)[0]
    assert "Intent:" not in scope


@pytest.mark.parametrize("placeholder", ["TODO", "_(TODO)_"])
def test_carved_seed_omits_placeholder_plan_and_step_intent(placeholder):
    out = _render(
        carved_step=_step(intent=placeholder),
        plan_intent=placeholder,
    )
    assert "Intent:" not in out
    assert "Source plan intent:" not in out


@pytest.mark.parametrize("placeholder", ["TODO", "_(TODO)_"])
def test_carved_region_seed_omits_placeholder_intents(placeholder):
    out = render_carved_region_seed(
        plan_title="Spinning Plan",
        carved_steps=[
            _step(id=2, title="Alpha", intent=placeholder),
            _step(id=3, title="Beta", intent=placeholder),
        ],
        detail_bodies=[None, None],
        detail_missings=[False, False],
        source_path=SOURCE,
        plan_intent=placeholder,
    )
    assert "Intent:" not in out
    assert "Source plan intent:" not in out


def test_carved_seed_omits_a_tbd_intent():
    # ``TBD`` is a fence non-value: the carve seed must not present it as the
    # source step's or plan's purpose.
    out = _render(
        carved_step=_step(intent="TBD"),
        plan_intent="TBD",
    )
    assert "Intent: TBD" not in out
    assert "Source plan intent:" not in out


def test_step_intent_collapses_to_one_line():
    out = _render(carved_step=_step(intent="line one\nline two"))
    scope = out.split("## Scope to re-plan", 1)[1].split("## Done-context", 1)[0]
    intent_line = next(ln for ln in scope.splitlines() if ln.startswith("Intent:"))
    assert "\n" not in intent_line
    assert "line one line two" in intent_line


def test_multi_line_step_intent_forges_no_heading():
    out = _render(carved_step=_step(intent="keep\n## Out of scope\nalive"))
    # Collapsed into the Intent: line — no standalone H2 forged.
    assert "Intent: keep ## Out of scope alive" in out
    heading_lines = [ln for ln in out.splitlines() if ln.startswith("## ")]
    assert "## Out of scope" not in heading_lines


def test_seed_names_the_source_plan_intent():
    out = _render(plan_intent="Ship the carve handoff")
    assert out.count("Source plan intent: Ship the carve handoff") == 1


def test_seed_omits_source_plan_intent_when_absent():
    out = _render(plan_intent=None)
    assert "Source plan intent:" not in out


def test_source_plan_intent_is_framed_as_source_not_as_the_new_outcome():
    out = _render(plan_intent="Whole-plan purpose")
    framing = out.split("Source plan intent:", 1)[1].split("## ", 1)[0]
    assert "own Outcome" in framing
    assert "do not inherit" in framing
    assert "## Outcome" not in out


def test_seed_writes_no_outcome_heading():
    carved = _render(
        carved_step=_step(intent="step why"),
        plan_intent="plan why",
    )
    region = render_carved_region_seed(
        plan_title="Spinning Plan",
        carved_steps=[_step(id=2, intent="a"), _step(id=3, intent="b")],
        detail_bodies=[None, None],
        detail_missings=[False, False],
        source_path=SOURCE,
        plan_intent="plan why",
    )
    assert "## Outcome" not in carved
    assert "## Outcome" not in region


def test_region_seed_keeps_intents_attached_to_source_steps():
    out = render_carved_region_seed(
        plan_title="Spinning Plan",
        carved_steps=[
            _step(id=2, title="Alpha", intent="why alpha"),
            _step(id=3, title="Beta", intent="why beta"),
        ],
        detail_bodies=[None, None],
        detail_missings=[False, False],
        source_path=SOURCE,
    )
    alpha, beta = out.split("**Alpha**", 1)[1].split("**Beta**", 1)
    assert "Intent: why alpha" in alpha and "why beta" not in alpha
    assert "Intent: why beta" in beta and "why alpha" not in beta


def test_region_seed_renders_source_plan_intent_once():
    out = render_carved_region_seed(
        plan_title="Spinning Plan",
        carved_steps=[
            _step(id=2, title="Alpha", intent="why alpha"),
            _step(id=3, title="Beta", intent="why beta"),
        ],
        detail_bodies=[None, None],
        detail_missings=[False, False],
        source_path=SOURCE,
        plan_intent="shared plan why",
    )
    assert out.count("Source plan intent: shared plan why") == 1


def test_plan_intent_parameter_defaults_to_none():
    carved = render_carved_seed(
        plan_title="Spinning Plan",
        carved_step=_step(),
        detail_body=None,
        source_path=SOURCE,
    )
    region = render_carved_region_seed(
        plan_title="Spinning Plan",
        carved_steps=[_step(id=2), _step(id=3)],
        detail_bodies=[None, None],
        detail_missings=[False, False],
        source_path=SOURCE,
    )
    assert "Source plan intent:" not in carved
    assert "Source plan intent:" not in region
    assert "plan_intent" in inspect.signature(render_carved_seed).parameters
    assert "plan_intent" in inspect.signature(render_carved_region_seed).parameters
    assert (
        inspect.signature(render_carved_seed).parameters["plan_intent"].default is None
    )


def test_no_intent_anywhere_renders_no_intent_line():
    out = _render()
    assert "Intent:" not in out
    assert "Source plan intent:" not in out


def test_narrow_preserves_survivor_intents(tmp_path):
    plan = _mk_plan(
        [
            _mk_step(1, intent="keep-one"),
            _mk_step(2, intent="carved-away"),
            _mk_step(3, intent="keep-three"),
        ],
        status=PlanStatus.PLANNING,
    )
    preview = _narrow(plan, 2, tmp_path)
    assert not preview.blockers
    by_title = {s.title: s.intent for s in preview.new_steps}
    assert by_title["Step 1"] == "keep-one"
    assert by_title["Step 3"] == "keep-three"
    assert {s.id for s in preview.new_steps} == {1, 2}


def test_narrow_preserves_legacy_risk_profile_omission(tmp_path):
    plan = _mk_plan([_mk_step(1), _mk_step(2), _mk_step(3)])

    preview = _narrow(plan, 2, tmp_path)

    assert preview.narrowed_plan.risk_profile is None
    assert preview.narrowed_plan.risk_profile_rationale is None


def test_carved_step_and_plan_intents_reach_the_written_seed(tmp_path):
    plan = _mk_plan(
        [
            _mk_step(1),
            _mk_step(2, intent="carved step why"),
            _mk_step(3),
        ],
        status=PlanStatus.PLANNING,
        intent="source plan why",
    )
    path = _write_plan_file(tmp_path, plan)
    result = scope_out_step(
        path, carved_id=2, repo_root=tmp_path, allow_scope_out=True, yes=True
    )
    assert result.outcome == "applied"
    assert result.seed_path is not None
    body = result.seed_path.read_text(encoding="utf-8")
    assert "Intent: carved step why" in body
    assert "Source plan intent: source plan why" in body


def test_scope_block_notes_non_committed_disposition():
    wont_do = _render(carved_step=_step(scope=StepScope.WONT_DO))
    assert "wont_do" in wont_do
    assert "parked" in wont_do
    deferred = _render(carved_step=_step(scope=StepScope.DEFERRED))
    assert "deferred" in deferred
    assert "parked" in deferred
    committed = _render(carved_step=_step(scope=StepScope.COMMITTED))
    assert "parked" not in committed


def test_done_context_renders_status_as_prose():
    step = _step(status=StepStatus.CURRENT, status_note="half wired up")
    out = _render(carved_step=step)
    assert "## Done-context" in out
    assert "current" in out
    assert "half wired up" in out


def test_done_context_emits_no_progress_field():
    step = _step(status=StepStatus.CURRENT, status_note="partial")
    out = _render(carved_step=step)
    assert "progress:" not in out
    assert "resume this in-progress step" not in out.lower()


def test_done_context_marks_context_as_done_not_to_replan():
    out = _render(carved_step=_step(), detail_body="DETAIL_BODY_MARKER")
    done_section = out.split("## Done-context", 1)[1].split("## ", 1)[0]
    assert "do **not** re-plan" in done_section.lower()
    assert "DETAIL_BODY_MARKER" not in done_section


def test_detail_body_inlined_in_scope_when_present():
    out = _render(detail_body="VERBATIM_DETAIL")
    scope_section = out.split("## Scope to re-plan", 1)[1].split("## Done-context", 1)[0]
    assert "VERBATIM_DETAIL" in scope_section


def test_scope_seed_omits_only_the_fixed_detail_format_marker():
    marker = "<!-- plan-tool:detail-format-version: 1 -->"
    prose_marker = "<!-- plan-tool:detail-format-version: 999 -->"
    out = _render(
        detail_body=(
            f"# Detail\n{marker}\n\n## Summary\n\n{prose_marker}\n"
        )
    )

    assert marker not in out
    assert prose_marker in out


def test_bare_step_without_detail():
    out = _render(detail_body=None, detail_missing=False)
    assert "never detailed" in out
    assert "missing detail" not in out.lower()


def test_pointed_but_missing_detail_renders_warning():
    out = _render(detail_body=None, detail_missing=True)
    assert "Missing detail" in out
    assert "never detailed" not in out


def test_done_upstream_prerequisites_rendered_as_assumed_done():
    out = _render(
        upstream_context=[
            (1, "Build base", "done", None),
            (2, "Wire it", "done", None),
        ]
    )
    section = out.split("## Upstream prerequisites", 1)[1]
    assert "- step 1: Build base" in section
    assert "- step 2: Wire it" in section


def test_non_done_upstream_prerequisites_rendered_as_external():
    out = _render(upstream_context=[(4, "Pending dep", "pending", None)])
    assert "## External prerequisites (not done yet)" in out
    external = out.split("## External prerequisites", 1)[1]
    assert "- step 4 [pending]: Pending dep" in external
    assert "## Upstream prerequisites" not in out


def test_no_upstream_sections_when_empty():
    out = _render(upstream_context=())
    assert "## Upstream prerequisites" not in out
    assert "## External prerequisites" not in out


def test_output_is_deterministic():
    step = _step(files=["z.py", "a.py"], creates=["m.py"])
    first = _render(carved_step=step, upstream_context=[(1, "x", "done", None)])
    second = _render(carved_step=step, upstream_context=[(1, "x", "done", None)])
    assert first == second
    # File bullets preserve all_files order (files first, then creates).
    assert first.index("- z.py") < first.index("- a.py") < first.index("- m.py")


def test_upstream_block_renders_note_when_present():
    out = _render(
        upstream_context=[(1, "Base", "done", "consumes schema")]
    )
    section = out.split("## Upstream prerequisites", 1)[1]
    assert "consumes schema" in section
    assert "— consumes: consumes schema" in section


def test_upstream_block_omits_note_when_absent():
    out = _render(upstream_context=[(1, "Base", "done", None)])
    section = out.split("## Upstream prerequisites", 1)[1]
    assert "- step 1: Base" in section
    assert "consumes:" not in section


def test_seed_is_create_from_existing_input():
    out = _render()
    assert out.startswith("<!-- plan-tool scope-out carved-seed")
    assert "create --from-existing" in out
    assert "# Plan seed:" in out
    assert f"## References\n\n- Source plan: `{SOURCE}`" in out


def test_single_and_region_scope_out_fallbacks_pass_create_preflight():
    single_step_seed = _render()
    region_seed = render_carved_region_seed(
        plan_title="Spinning Plan",
        carved_steps=[_step(id=2), _step(id=3)],
        detail_bodies=[None, None],
        detail_missings=[False, False],
        source_path=SOURCE,
    )

    validate_from_existing_seed(single_step_seed)
    validate_from_existing_seed(region_seed)


def test_seed_preserves_source_reference_body():
    out = _render(source_references="- [API](https://example.test/api)")
    references = out.split("## References", 1)[1].split("## Provenance", 1)[0]
    assert "[API](https://example.test/api)" in references
    assert "Source plan:" not in references


@pytest.mark.parametrize("placeholder", ["TODO", "(TODO)", "_(TODO)_"])
def test_seed_replaces_placeholder_source_references_with_fallback(placeholder):
    out = _render(source_references=placeholder)
    references = out.split("## References", 1)[1].split("## Provenance", 1)[0]
    assert f"- Source plan: `{SOURCE}`" in references
    assert placeholder not in references


def test_provenance_records_source_and_step():
    out = _render(carved_step=_step(id=7))
    prov = out.split("## Provenance", 1)[1]
    assert str(SOURCE) in prov
    assert "Carved step: 7" in prov


# --------------------------------------------------------------------------
# The narrow: compute_narrow preview math + apply_narrow / rollback.
# --------------------------------------------------------------------------

_HASH = "0" * 64  # placeholder provenance for pure preview-math tests


def _mk_step(step_id: int, title: str | None = None, **kwargs) -> Step:
    return Step(id=step_id, title=title or f"Step {step_id}", **kwargs)


def _mk_plan(
    steps: list[Step],
    *,
    status: PlanStatus = PlanStatus.IN_PROGRESS,
    features: list[Feature] | None = None,
    title: str = "Spinning Plan",
    intent: str | None = None,
) -> Plan:
    return Plan(
        title=title,
        status=status,
        priority=Priority.MEDIUM,
        features=features or [],
        steps=steps,
        intent=intent,
    )


def _narrow(plan: Plan, carved_id: int, tmp_path: Path, **kwargs):
    return compute_narrow(
        plan,
        carved_id=carved_id,
        plan_path=tmp_path / "plan.md",
        repo_root=tmp_path,
        source_frontmatter_hash=kwargs.get("source_frontmatter_hash", _HASH),
    )


def _kinds(preview) -> list[str]:
    return [b.kind for b in preview.blockers]


def test_ownerless_carved_concept_is_selected_for_deferral(tmp_path):
    owned = "1" * 64
    plan = _mk_plan([_mk_step(1), _mk_step(2, concept_ids=[owned]), _mk_step(3)])
    preview = _narrow(plan, 2, tmp_path)
    assert scope_out.ownerless_carved_concept_ids([plan.steps[1]], preview) == [owned]


def test_shared_surviving_owner_prevents_deferral(tmp_path):
    shared = "2" * 64
    plan = _mk_plan(
        [
            _mk_step(1, concept_ids=[shared]),
            _mk_step(2, concept_ids=[shared]),
            _mk_step(3),
        ]
    )
    preview = _narrow(plan, 2, tmp_path)
    assert scope_out.ownerless_carved_concept_ids([plan.steps[1]], preview) == []


def test_parked_surviving_owner_does_not_prevent_deferral(tmp_path):
    shared = "3" * 64
    plan = _mk_plan(
        [
            _mk_step(1, concept_ids=[shared], scope=StepScope.DEFERRED),
            _mk_step(2, concept_ids=[shared]),
            _mk_step(3),
        ]
    )
    preview = _narrow(plan, 2, tmp_path)
    assert scope_out.ownerless_carved_concept_ids([plan.steps[1]], preview) == [shared]


def test_region_carve_deduplicates_ownerless_concept_ids(tmp_path):
    shared = "4" * 64
    plan = _mk_plan(
        [
            _mk_step(1),
            _mk_step(2, concept_ids=[shared]),
            _mk_step(3, concept_ids=[shared]),
            _mk_step(4),
        ]
    )
    preview = compute_narrow(
        plan,
        carved_ids=[2, 3],
        plan_path=tmp_path / "plan.md",
        repo_root=tmp_path,
        source_frontmatter_hash=_HASH,
    )
    assert scope_out.ownerless_carved_concept_ids(plan.steps[1:3], preview) == [shared]


# --- preview math: renumber + depends_on repair ---------------------------


def test_renumber_shifts_only_downstream(tmp_path):
    plan = _mk_plan(
        [
            _mk_step(1),
            _mk_step(2, depends_on=[1]),
            _mk_step(3, depends_on=[1]),
            _mk_step(4, depends_on=[3]),
        ],
        status=PlanStatus.PLANNING,
    )
    preview = _narrow(plan, 2, tmp_path)
    assert preview.blockers == []
    assert preview.renumber == [(3, 2), (4, 3)]


def test_non_canonical_numbering_is_a_blocker(tmp_path):
    plan = _mk_plan([_mk_step(1), _mk_step(2), _mk_step(4)], status=PlanStatus.PLANNING)
    preview = _narrow(plan, 2, tmp_path)
    assert _kinds(preview) == ["non-canonical-numbering"]
    assert preview.new_steps == []
    assert preview.narrowed_plan is None


def test_depends_on_remapped_through_drop(tmp_path):
    plan = _mk_plan(
        [
            _mk_step(1),
            _mk_step(2, depends_on=[1]),
            _mk_step(3, depends_on=[4]),
            _mk_step(4, depends_on=[1]),
        ],
        status=PlanStatus.PLANNING,
    )
    preview = _narrow(plan, 2, tmp_path)
    assert preview.blockers == []
    new_by_id = {s.id: s for s in preview.new_steps}
    # old step 3 (depends_on [4]) becomes new id 2 with depends_on [3].
    assert new_by_id[2].depends_on == [3]


def test_narrow_remaps_depends_on_notes_with_survivors(tmp_path):
    plan = _mk_plan(
        [
            _mk_step(1),
            _mk_step(2),
            _mk_step(3, depends_on=[1], depends_on_notes={1: "keep"}),
            _mk_step(4, depends_on=[3], depends_on_notes={3: "shift"}),
        ],
        status=PlanStatus.PLANNING,
    )
    preview = _narrow(plan, 2, tmp_path)
    assert preview.blockers == []
    by_id = {s.id: s for s in preview.new_steps}
    assert by_id[2].depends_on_notes == {1: "keep"}
    assert by_id[3].depends_on_notes == {2: "shift"}


def test_narrow_stale_note_key_raises_narrow_error(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = scope_out._remap_depends_on_notes

    def _inject_stale(notes, depends_on, **kwargs):
        result = real(notes, depends_on, **kwargs)
        result[99] = "stale"
        return result

    monkeypatch.setattr(scope_out, "_remap_depends_on_notes", _inject_stale)
    plan = _mk_plan(
        [_mk_step(1), _mk_step(2), _mk_step(3, depends_on=[1])],
        status=PlanStatus.PLANNING,
    )
    with pytest.raises(NarrowError, match="depends_on_notes"):
        _narrow(plan, 2, tmp_path)


def test_inbound_dependent_is_a_blocker(tmp_path):
    plan = _mk_plan(
        [_mk_step(1), _mk_step(2), _mk_step(3, depends_on=[2])],
        status=PlanStatus.PLANNING,
    )
    preview = _narrow(plan, 2, tmp_path)
    assert _kinds(preview) == ["inbound-dependent"]
    assert preview.blockers[0].step_ids == [3]
    assert preview.new_steps == []


def test_downstream_done_is_a_blocker(tmp_path):
    plan = _mk_plan(
        [
            _mk_step(1, status=StepStatus.DONE),
            _mk_step(2),
            _mk_step(3, depends_on=[1], status=StepStatus.DONE),
        ]
    )
    preview = _narrow(plan, 2, tmp_path)
    assert _kinds(preview) == ["downstream-orphan"]
    assert preview.blockers[0].step_ids == [3]


def test_downstream_current_is_not_a_blocker(tmp_path):
    # An authored-but-unrun ``current`` step after the carved step renumbers
    # cleanly (no green commit to orphan) — gate is DONE-only, like split/merge.
    plan = _mk_plan(
        [
            _mk_step(1),
            _mk_step(2),
            _mk_step(3, depends_on=[1], status=StepStatus.CURRENT),
        ],
        status=PlanStatus.PLANNING,
    )
    preview = _narrow(plan, 2, tmp_path)
    assert preview.blockers == []
    # old step 3 (CURRENT) becomes new id 2, still current.
    new_by_id = {s.id: s for s in preview.new_steps}
    assert new_by_id[2].status is StepStatus.CURRENT


def test_carving_only_survivor_is_empty_plan_blocker(tmp_path):
    plan = _mk_plan([_mk_step(1)], status=PlanStatus.PLANNING)
    preview = _narrow(plan, 1, tmp_path)
    assert _kinds(preview) == ["empty-plan"]
    assert preview.new_steps == []
    assert preview.narrowed_plan is None


def test_carving_last_committed_survivor_with_parked_remaining_is_empty_plan_blocker(
    tmp_path,
):
    plan = _mk_plan(
        [
            _mk_step(1),
            _mk_step(2, scope=StepScope.DEFERRED),
        ],
        status=PlanStatus.PLANNING,
    )
    preview = _narrow(plan, 1, tmp_path)
    assert _kinds(preview) == ["empty-plan"]
    # The parked survivor is renumbered, but no committed plan is constructed.
    assert len(preview.new_steps) == 1
    assert preview.narrowed_plan is None


def test_missing_step_is_a_blocker(tmp_path):
    plan = _mk_plan([_mk_step(1), _mk_step(2)], status=PlanStatus.PLANNING)
    preview = _narrow(plan, 5, tmp_path)
    assert _kinds(preview) == ["step-missing"]
    assert preview.narrowed_plan is None


# --- preview math: cursor + status ----------------------------------------


def test_cursor_promotes_first_runnable_pending_after_drop(tmp_path):
    plan = _mk_plan(
        [
            _mk_step(1, status=StepStatus.DONE),
            _mk_step(2, status=StepStatus.CURRENT),
            _mk_step(3, depends_on=[1]),
            _mk_step(4, depends_on=[3]),
        ]
    )
    preview = _narrow(plan, 2, tmp_path)
    assert preview.new_current_id == 2  # old step 3, now id 2
    promoted = {s.id: s for s in preview.new_steps}[2]
    assert promoted.status is StepStatus.CURRENT


def test_non_current_carve_preserves_no_cursor_state(tmp_path):
    plan = _mk_plan(
        [
            _mk_step(1, status=StepStatus.DONE),
            _mk_step(2),
            _mk_step(3, depends_on=[1]),
        ]
    )
    preview = _narrow(plan, 2, tmp_path)
    assert preview.new_current_id is None
    statuses = {s.id: s.status for s in preview.new_steps}
    assert statuses == {1: StepStatus.DONE, 2: StepStatus.PENDING}


def test_cursor_none_when_no_runnable_pending_survivor(tmp_path):
    # Carving the sole CURRENT step leaves only a parked pending step (not
    # runnable) beside a DONE step — nothing committed+pending to promote.
    plan = _mk_plan(
        [
            _mk_step(1, status=StepStatus.DONE),
            _mk_step(2, status=StepStatus.CURRENT),
            _mk_step(3, scope=StepScope.DEFERRED),
        ]
    )
    preview = _narrow(plan, 2, tmp_path)
    assert preview.new_current_id is None
    assert not any(s.status is StepStatus.CURRENT for s in preview.new_steps)


def test_all_done_no_cursor_marks_plan_completed(tmp_path):
    # Carve the last (sole CURRENT) step; the survivors are all DONE, so no
    # downstream step renumbers and the narrowed plan completes.
    plan = _mk_plan(
        [
            _mk_step(1, status=StepStatus.DONE),
            _mk_step(2, depends_on=[1], status=StepStatus.DONE),
            _mk_step(3, depends_on=[2], status=StepStatus.CURRENT),
        ]
    )
    preview = _narrow(plan, 3, tmp_path)
    assert preview.new_current_id is None
    assert preview.new_plan_status is PlanStatus.COMPLETED
    assert preview.narrowed_plan.status is PlanStatus.COMPLETED


# --- preview math: provenance, features, determinism ----------------------


def test_preview_carries_complete_narrowed_plan_and_source_provenance(tmp_path):
    plan = _mk_plan(
        [_mk_step(1), _mk_step(2), _mk_step(3, depends_on=[1])],
        status=PlanStatus.PLANNING,
        title="My Plan",
    )
    preview = _narrow(plan, 2, tmp_path, source_frontmatter_hash="abc123")
    assert preview.source_frontmatter_hash == "abc123"
    np = preview.narrowed_plan
    assert np is not None
    assert np.title == "My Plan"
    assert np.priority is Priority.MEDIUM
    assert [s.id for s in np.steps] == [1, 2]


def test_narrow_prunes_unimplemented_feature_from_registry(tmp_path):
    plan = _mk_plan(
        [
            _mk_step(1, features=["feat-b"]),
            _mk_step(2, features=["feat-a"]),
            _mk_step(3, features=["feat-b"]),
        ],
        status=PlanStatus.PLANNING,
        features=[Feature(id="feat-a", title="A"), Feature(id="feat-b", title="B")],
    )
    preview = _narrow(plan, 2, tmp_path)
    assert [f.id for f in preview.narrowed_plan.features] == ["feat-b"]


def test_preview_is_deterministic(tmp_path):
    plan = _mk_plan(
        [
            _mk_step(1, status=StepStatus.DONE),
            _mk_step(2, status=StepStatus.CURRENT),
            _mk_step(3, depends_on=[1]),
            _mk_step(4, depends_on=[3]),
        ]
    )
    first = _narrow(plan, 2, tmp_path)
    second = _narrow(plan, 2, tmp_path)
    assert first == second


# --- preview math: multi-id (ordered-set) carve ---------------------------


def _narrow_multi(plan: Plan, carved_ids, tmp_path: Path, **kwargs):
    return compute_narrow(
        plan,
        carved_ids=carved_ids,
        plan_path=tmp_path / "plan.md",
        repo_root=tmp_path,
        source_frontmatter_hash=kwargs.get("source_frontmatter_hash", _HASH),
    )


def test_multi_id_renumber_shifts_by_count_below(tmp_path):
    plan = _mk_plan([_mk_step(i) for i in range(1, 6)], status=PlanStatus.PLANNING)
    preview = _narrow_multi(plan, [2, 3], tmp_path)
    assert preview.blockers == []
    assert preview.carved_ids == [2, 3]
    assert preview.renumber == [(4, 2), (5, 3)]


def test_multi_id_disjoint_carve_shifts_each_survivor_by_count_below(tmp_path):
    plan = _mk_plan(
        [
            _mk_step(1),
            _mk_step(2),
            _mk_step(3, depends_on=[1]),
            _mk_step(4),
            _mk_step(5, depends_on=[3]),
        ],
        status=PlanStatus.PLANNING,
    )
    preview = _narrow_multi(plan, [2, 4], tmp_path)
    assert preview.blockers == []
    # survivor 3 shifts down by one (carved 2 below), 5 by two (carved 2 and 4).
    assert preview.renumber == [(3, 2), (5, 3)]
    new_by_id = {s.id: s for s in preview.new_steps}
    assert new_by_id[2].depends_on == [1]  # old 3 dep on 1 unchanged
    assert new_by_id[3].depends_on == [2]  # old 5 dep old 3 → new 2


def test_multi_id_depends_on_remapped_across_gap(tmp_path):
    plan = _mk_plan(
        [
            _mk_step(1),
            _mk_step(2),
            _mk_step(3, depends_on=[1]),
            _mk_step(4),
            _mk_step(5, depends_on=[3]),
            _mk_step(6, depends_on=[5]),
        ],
        status=PlanStatus.PLANNING,
    )
    preview = _narrow_multi(plan, [2, 4], tmp_path)
    new_by_id = {s.id: s for s in preview.new_steps}
    assert new_by_id[3].depends_on == [2]  # old 5 dep old 3
    assert new_by_id[4].depends_on == [3]  # old 6 dep old 5


def test_multi_id_carved_on_carved_edge_is_not_inbound(tmp_path):
    plan = _mk_plan(
        [
            _mk_step(1),
            _mk_step(2),
            _mk_step(3, depends_on=[2]),
            _mk_step(4, depends_on=[1]),
        ],
        status=PlanStatus.PLANNING,
    )
    preview = _narrow_multi(plan, [2, 3], tmp_path)
    assert preview.blockers == []
    assert [s.id for s in preview.new_steps] == [1, 2]  # old 1, old 4→2


def test_multi_id_inbound_from_kept_step_is_blocker(tmp_path):
    plan = _mk_plan(
        [
            _mk_step(1),
            _mk_step(2),
            _mk_step(3),
            _mk_step(4, depends_on=[3]),
        ],
        status=PlanStatus.PLANNING,
    )
    preview = _narrow_multi(plan, [2, 3], tmp_path)
    assert _kinds(preview) == ["inbound-dependent"]
    assert preview.blockers[0].step_ids == [4]


def test_multi_id_downstream_non_pending_is_blocker(tmp_path):
    plan = _mk_plan(
        [
            _mk_step(1, status=StepStatus.DONE),
            _mk_step(2),
            _mk_step(3),
            _mk_step(4, depends_on=[1], status=StepStatus.DONE),
        ]
    )
    preview = _narrow_multi(plan, [2, 3], tmp_path)
    assert _kinds(preview) == ["downstream-orphan"]
    assert preview.blockers[0].step_ids == [4]


def test_multi_id_step_missing_lists_all_absent(tmp_path):
    plan = _mk_plan(
        [_mk_step(1), _mk_step(2), _mk_step(3)], status=PlanStatus.PLANNING
    )
    preview = _narrow_multi(plan, [2, 9], tmp_path)
    assert _kinds(preview) == ["step-missing"]
    assert "9" in preview.blockers[0].message
    assert preview.narrowed_plan is None


def test_multi_id_empty_plan_when_no_committed_survivor(tmp_path):
    plan = _mk_plan([_mk_step(1), _mk_step(2)], status=PlanStatus.PLANNING)
    preview = _narrow_multi(plan, [1, 2], tmp_path)
    assert _kinds(preview) == ["empty-plan"]
    assert preview.narrowed_plan is None


def test_multi_id_cursor_reestablished_when_a_carved_step_is_current(tmp_path):
    plan = _mk_plan(
        [
            _mk_step(1, status=StepStatus.DONE),
            _mk_step(2, status=StepStatus.CURRENT),
            _mk_step(3),
            _mk_step(4, depends_on=[1]),
        ]
    )
    preview = _narrow_multi(plan, [2, 3], tmp_path)
    assert preview.new_current_id == 2  # old 4, now id 2
    promoted = {s.id: s for s in preview.new_steps}[2]
    assert promoted.status is StepStatus.CURRENT


def test_multi_id_preview_is_deterministic(tmp_path):
    plan = _mk_plan([_mk_step(i) for i in range(1, 6)], status=PlanStatus.PLANNING)
    first = _narrow_multi(plan, [3, 2, 2], tmp_path)  # unordered + duplicate
    second = _narrow_multi(plan, [2, 3], tmp_path)
    assert first == second
    assert first.carved_ids == [2, 3]


def test_compute_narrow_accepts_carved_id_keyword(tmp_path):
    plan = _mk_plan(
        [_mk_step(1), _mk_step(2), _mk_step(3, depends_on=[1])],
        status=PlanStatus.PLANNING,
    )
    scalar = _narrow(plan, 2, tmp_path)
    plural = _narrow_multi(plan, [2], tmp_path)
    assert scalar == plural
    assert scalar.carved_ids == [2]


def test_compute_narrow_requires_exactly_one_carved_selector(tmp_path):
    plan = _mk_plan([_mk_step(1), _mk_step(2)], status=PlanStatus.PLANNING)
    common = dict(
        plan_path=tmp_path / "plan.md",
        repo_root=tmp_path,
        source_frontmatter_hash=_HASH,
    )
    with pytest.raises(ValueError):
        compute_narrow(plan, **common)  # neither
    with pytest.raises(ValueError):
        compute_narrow(plan, carved_id=1, carved_ids=[2], **common)  # both


# --- apply: on-disk plan + detail file migration --------------------------

_DETAIL_DIR = "plan-details/spin"


def _write_plan_file(
    tmp_path: Path,
    plan: Plan,
    name: str = "2-spin.md",
    *,
    body: str = "Plan prose body that survives narrowing.\n",
) -> Path:
    dumped = _coerce_enums(plan.model_dump(exclude_defaults=True, exclude_none=True))
    fm = yaml.safe_dump(
        dumped, default_flow_style=False, sort_keys=False, allow_unicode=True
    )
    path = tmp_path / name
    path.write_text(f"---\n{fm}---\n\n{body}", encoding="utf-8")
    return path


def test_find_scope_out_body_hits_flags_carved_shifted_and_title():
    body = (
        "## Risks\n\n"
        "- Open until measured (**step 9**).\n"
        "- Per-step testing for **step 10**.\n"
        "- Do not skip the Measurement Gate work.\n"
    )
    hits = find_scope_out_body_hits(
        body,
        carved_ids=[9],
        carved_titles=["Measurement Gate"],
        renumber=[(10, 9)],
    )
    kinds = {h.kind for h in hits}
    assert kinds == {"carved-id", "shifted-id", "carved-title"}
    assert any(h.detail.startswith("step 9") for h in hits)
    assert any("now step 9" in h.detail for h in hits)
    assert any("Measurement Gate" in h.detail for h in hits)


def test_find_scope_out_body_hits_title_is_word_boundary():
    """Substring stems must not false-positive (Measure ⊂ Measurement)."""
    hits = find_scope_out_body_hits(
        "Do not skip the Measurement phase.\n",
        carved_ids=[],
        carved_titles=["Measure"],
        renumber=[],
    )
    assert hits == []
    hits_exact = find_scope_out_body_hits(
        "Finish the Measure work next.\n",
        carved_ids=[],
        carved_titles=["Measure"],
        renumber=[],
    )
    assert len(hits_exact) == 1
    assert hits_exact[0].kind == "carved-title"


def test_find_scope_out_body_hits_ignores_unrelated_step_refs():
    hits = find_scope_out_body_hits(
        "See step 1 and step 2 for context.\n",
        carved_ids=[9],
        carved_titles=["Other"],
        renumber=[(10, 9)],
    )
    assert hits == []


def test_scope_out_step_reports_body_sweep_hits(tmp_path):
    plan = _mk_plan(
        [
            _mk_step(1, "First"),
            _mk_step(2, "Measurement Gate"),
            _mk_step(3, "Docs"),
        ],
        status=PlanStatus.PLANNING,
    )
    path = _write_plan_file(
        tmp_path,
        plan,
        body=(
            "## Risks\n\n"
            "- Open until measured (**step 2**).\n"
            "- Testing for **step 3**.\n"
            "- Mentions Measurement Gate explicitly.\n"
        ),
    )
    result = scope_out_step(
        path, carved_id=2, repo_root=tmp_path, allow_scope_out=True, yes=True
    )
    assert result.outcome == "applied"
    kinds = {h.kind for h in result.body_sweep_hits}
    assert "carved-id" in kinds
    assert "shifted-id" in kinds
    assert "carved-title" in kinds
    # Body preserved on disk (frontmatter-only narrow).
    on_disk = path.read_text(encoding="utf-8")
    assert "**step 2**" in on_disk
    assert "Measurement Gate" in on_disk


def _touch_detail(tmp_path: Path, rel: str, text: str = "# detail\n") -> Path:
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _detail(name: str) -> str:
    return f"{_DETAIL_DIR}/{name}"


def _save_concept_record(plan_path: Path, *titles: str) -> dict[str, str]:
    ids = {title: concept_id(title, []) for title in titles}
    tree = ConceptTree(
        plan_slug="spin",
        plan_fingerprint=compute_plan_fingerprint(plan_path),
        concepts=[
            ConceptNode(
                id=ids[title],
                title=title,
                order=order,
                decision="include",
                review_state="approved",
            )
            for order, title in enumerate(titles)
        ],
    )
    save_concepts(plan_path, tree)
    return ids


def _apply(tmp_path: Path, plan_path: Path, plan: Plan, carved_id: int):
    fm_hash = compute_frontmatter_hash(plan_path)
    preview = compute_narrow(
        plan,
        carved_id=carved_id,
        plan_path=plan_path,
        repo_root=tmp_path,
        source_frontmatter_hash=fm_hash,
    )
    return preview, apply_narrow(plan_path, preview, repo_root=tmp_path)


def test_apply_migrates_downstream_detail_files(tmp_path):
    plan = _mk_plan(
        [
            _mk_step(1, "First", depends_on=[], detail=_detail("01-first.md")),
            _mk_step(2, "Second", depends_on=[1], detail=_detail("02-second.md")),
            _mk_step(3, "Third", depends_on=[1], detail=_detail("03-third.md")),
        ],
        status=PlanStatus.PLANNING,
    )
    path = _write_plan_file(tmp_path, plan)
    plan = parse_plan(path)
    for rel in ("01-first.md", "02-second.md", "03-third.md"):
        _touch_detail(tmp_path, _detail(rel))

    _apply(tmp_path, path, plan, 2)

    assert (tmp_path / _detail("02-third.md")).is_file()
    assert not (tmp_path / _detail("03-third.md")).exists()
    narrowed = parse_plan(path)
    third = {s.id: s for s in narrowed.steps}[2]
    assert third.title == "Third"
    assert third.detail == _detail("02-third.md")


def test_apply_migrates_downstream_canonical_detail_without_pointer(tmp_path):
    plan = _mk_plan(
        [
            _mk_step(1, "First", detail=_detail("01-first.md")),
            _mk_step(2, "Second", depends_on=[1], detail=_detail("02-second.md")),
            _mk_step(3, "Third thing", depends_on=[1]),  # no detail pointer
        ],
        status=PlanStatus.PLANNING,
    )
    path = _write_plan_file(tmp_path, plan)
    plan = parse_plan(path)
    _touch_detail(tmp_path, _detail("01-first.md"))
    _touch_detail(tmp_path, _detail("02-second.md"))
    # Canonical file for step 3 exists with no frontmatter pointer.
    _touch_detail(tmp_path, _detail("03-third-thing.md"))

    _apply(tmp_path, path, plan, 2)

    assert (tmp_path / _detail("02-third-thing.md")).is_file()
    assert not (tmp_path / _detail("03-third-thing.md")).exists()
    narrowed = parse_plan(path)
    third = {s.id: s for s in narrowed.steps}[2]
    assert third.detail == _detail("02-third-thing.md")


def test_apply_raises_and_rolls_back_on_downstream_detail_destination_collision(
    tmp_path,
):
    plan = _mk_plan(
        [
            _mk_step(1, "First", detail=_detail("01-first.md")),
            _mk_step(2, "Second", depends_on=[1], detail=_detail("02-second.md")),
            _mk_step(3, "Third", depends_on=[1], detail=_detail("03-third.md")),
            _mk_step(4, "Fourth", depends_on=[1], detail=_detail("04-fourth.md")),
        ],
        status=PlanStatus.PLANNING,
    )
    path = _write_plan_file(tmp_path, plan)
    plan = parse_plan(path)
    for rel in ("01-first.md", "02-second.md", "03-third.md", "04-fourth.md"):
        _touch_detail(tmp_path, _detail(rel))
    # Stray file occupies step 4's rename destination (03-fourth.md).
    _touch_detail(tmp_path, _detail("03-fourth.md"), text="STRAY\n")
    before = path.read_text(encoding="utf-8")

    fm_hash = compute_frontmatter_hash(path)
    preview = compute_narrow(
        plan, carved_id=2, plan_path=path, repo_root=tmp_path,
        source_frontmatter_hash=fm_hash,
    )
    with pytest.raises(NarrowError):
        apply_narrow(path, preview, repo_root=tmp_path)

    # Rolled back: the earlier 03-third→02-third rename is undone, nothing moved.
    assert (tmp_path / _detail("03-third.md")).is_file()
    assert not (tmp_path / _detail("02-third.md")).exists()
    assert (tmp_path / _detail("04-fourth.md")).is_file()
    assert (tmp_path / _detail("02-second.md")).is_file()
    assert path.read_text(encoding="utf-8") == before


def test_apply_archives_carved_detail_before_downstream_rename_into_same_path(tmp_path):
    plan = _mk_plan(
        [
            _mk_step(1, "First", detail=_detail("01-build.md")),
            _mk_step(2, "Second", depends_on=[1], detail=_detail("02-build.md")),
            _mk_step(3, "Third", depends_on=[1], detail=_detail("03-build.md")),
        ],
        status=PlanStatus.PLANNING,
    )
    path = _write_plan_file(tmp_path, plan)
    plan = parse_plan(path)
    for rel in ("01-build.md", "02-build.md", "03-build.md"):
        _touch_detail(tmp_path, _detail(rel), text=f"# {rel}\n")

    _, result = _apply(tmp_path, path, plan, 2)

    # 03-build.md moved into the freed 02-build.md slot; carved 02-build.md archived.
    assert (tmp_path / _detail("02-build.md")).read_text(encoding="utf-8") == "# 03-build.md\n"
    assert not (tmp_path / _detail("03-build.md")).exists()
    assert len(result.archived) == 1 and result.archived[0].is_file()
    assert result.archived[0].parent.name == "archive"


def test_apply_archives_carved_detail(tmp_path):
    plan = _mk_plan(
        [
            _mk_step(1, "First", detail=_detail("01-first.md")),
            _mk_step(2, "Second", depends_on=[1], detail=_detail("02-second.md")),
            _mk_step(3, "Third", depends_on=[1], detail=_detail("03-third.md")),
        ],
        status=PlanStatus.PLANNING,
    )
    path = _write_plan_file(tmp_path, plan)
    plan = parse_plan(path)
    for rel in ("01-first.md", "02-second.md", "03-third.md"):
        _touch_detail(tmp_path, _detail(rel))

    _, result = _apply(tmp_path, path, plan, 2)

    assert not (tmp_path / _detail("02-second.md")).exists()
    assert len(result.archived) == 1
    assert result.archived[0].is_file()
    assert result.archived[0].parent == tmp_path / _DETAIL_DIR / "archive"


def test_apply_archives_noncanonical_carved_detail_pointer(tmp_path):
    plan = _mk_plan(
        [
            _mk_step(1, "First", detail=_detail("01-first.md")),
            _mk_step(2, "Second", depends_on=[1], detail=_detail("02-custom-name.md")),
            _mk_step(3, "Third", depends_on=[1], detail=_detail("03-third.md")),
        ],
        status=PlanStatus.PLANNING,
    )
    path = _write_plan_file(tmp_path, plan)
    plan = parse_plan(path)
    for rel in ("01-first.md", "02-custom-name.md", "03-third.md"):
        _touch_detail(tmp_path, _detail(rel))

    _, result = _apply(tmp_path, path, plan, 2)

    assert not (tmp_path / _detail("02-custom-name.md")).exists()
    assert len(result.archived) == 1
    assert result.archived[0].name.startswith("02-custom-name.")
    assert result.archived[0].is_file()


def test_apply_raises_and_rolls_back_when_carved_archive_fails(tmp_path, monkeypatch):
    plan = _mk_plan(
        [
            _mk_step(1, "First", detail=_detail("01-first.md")),
            _mk_step(2, "Second", depends_on=[1], detail=_detail("02-second.md")),
            _mk_step(3, "Third", depends_on=[1], detail=_detail("03-third.md")),
        ],
        status=PlanStatus.PLANNING,
    )
    path = _write_plan_file(tmp_path, plan)
    plan = parse_plan(path)
    for rel in ("01-first.md", "02-second.md", "03-third.md"):
        _touch_detail(tmp_path, _detail(rel))
    before = path.read_text(encoding="utf-8")

    def _boom(_path):
        raise NarrowError("archive failed")

    monkeypatch.setattr(scope_out, "_archive_file_strict", _boom)

    fm_hash = compute_frontmatter_hash(path)
    preview = compute_narrow(
        plan, carved_id=2, plan_path=path, repo_root=tmp_path,
        source_frontmatter_hash=fm_hash,
    )
    with pytest.raises(NarrowError):
        apply_narrow(path, preview, repo_root=tmp_path)

    # The downstream rename is rolled back; the carved detail stays put.
    assert (tmp_path / _detail("03-third.md")).is_file()
    assert not (tmp_path / _detail("02-third.md")).exists()
    assert (tmp_path / _detail("02-second.md")).is_file()
    assert path.read_text(encoding="utf-8") == before


def test_apply_narrows_plan_on_disk(tmp_path):
    plan = _mk_plan(
        [
            _mk_step(1, "First", status=StepStatus.DONE),
            _mk_step(2, "Second", status=StepStatus.CURRENT),
            _mk_step(3, "Third", depends_on=[1]),
            _mk_step(4, "Fourth", depends_on=[3]),
        ]
    )
    path = _write_plan_file(tmp_path, plan)
    plan = parse_plan(path)

    _apply(tmp_path, path, plan, 2)

    narrowed = parse_plan(path)
    assert [s.id for s in narrowed.steps] == [1, 2, 3]
    assert [s.title for s in narrowed.steps] == ["First", "Third", "Fourth"]
    by_id = {s.id: s for s in narrowed.steps}
    assert by_id[2].status is StepStatus.CURRENT  # promoted
    assert by_id[3].depends_on == [2]  # old [3] remapped


def test_apply_refuses_when_blockers_present(tmp_path):
    plan = _mk_plan(
        [
            _mk_step(1, "First", detail=_detail("01-first.md")),
            _mk_step(2, "Second", detail=_detail("02-second.md")),
            _mk_step(3, "Third", depends_on=[2], detail=_detail("03-third.md")),
        ],
        status=PlanStatus.PLANNING,
    )
    path = _write_plan_file(tmp_path, plan)
    plan = parse_plan(path)
    for rel in ("01-first.md", "02-second.md", "03-third.md"):
        _touch_detail(tmp_path, _detail(rel))
    before = path.read_text(encoding="utf-8")

    fm_hash = compute_frontmatter_hash(path)
    preview = compute_narrow(
        plan, carved_id=2, plan_path=path, repo_root=tmp_path,
        source_frontmatter_hash=fm_hash,
    )
    assert preview.blockers  # inbound-dependent
    with pytest.raises(NarrowError):
        apply_narrow(path, preview, repo_root=tmp_path)

    assert path.read_text(encoding="utf-8") == before
    assert (tmp_path / _detail("02-second.md")).is_file()


def test_apply_refuses_stale_preview_when_plan_frontmatter_changed(tmp_path):
    plan = _mk_plan(
        [
            _mk_step(1, "First", detail=_detail("01-first.md")),
            _mk_step(2, "Second", depends_on=[1], detail=_detail("02-second.md")),
            _mk_step(3, "Third", depends_on=[1], detail=_detail("03-third.md")),
        ],
        status=PlanStatus.PLANNING,
    )
    path = _write_plan_file(tmp_path, plan)
    plan = parse_plan(path)
    for rel in ("01-first.md", "02-second.md", "03-third.md"):
        _touch_detail(tmp_path, _detail(rel))

    fm_hash = compute_frontmatter_hash(path)
    preview = compute_narrow(
        plan, carved_id=2, plan_path=path, repo_root=tmp_path,
        source_frontmatter_hash=fm_hash,
    )
    # Mutate the frontmatter on disk after the snapshot.
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace("priority: medium", "priority: high"), encoding="utf-8")

    with pytest.raises(NarrowError):
        apply_narrow(path, preview, repo_root=tmp_path)

    # No detail-file move happened before the refusal.
    assert (tmp_path / _detail("02-second.md")).is_file()
    assert (tmp_path / _detail("03-third.md")).is_file()
    assert not (tmp_path / _detail("02-third.md")).exists()


def test_apply_rolls_back_on_failure(tmp_path, monkeypatch):
    plan = _mk_plan(
        [
            _mk_step(1, "First", detail=_detail("01-first.md")),
            _mk_step(2, "Second", depends_on=[1], detail=_detail("02-second.md")),
            _mk_step(3, "Third", depends_on=[1], detail=_detail("03-third.md")),
        ],
        status=PlanStatus.PLANNING,
    )
    path = _write_plan_file(tmp_path, plan)
    plan = parse_plan(path)
    for rel in ("01-first.md", "02-second.md", "03-third.md"):
        _touch_detail(tmp_path, _detail(rel))
    before = path.read_text(encoding="utf-8")

    def _boom(*args, **kwargs):
        raise RuntimeError("write failed")

    monkeypatch.setattr(scope_out, "write_plan", _boom)

    fm_hash = compute_frontmatter_hash(path)
    preview = compute_narrow(
        plan, carved_id=2, plan_path=path, repo_root=tmp_path,
        source_frontmatter_hash=fm_hash,
    )
    with pytest.raises(RuntimeError):
        apply_narrow(path, preview, repo_root=tmp_path)

    # Everything restored: detail renames undone, carved detail un-archived.
    assert path.read_text(encoding="utf-8") == before
    assert (tmp_path / _detail("03-third.md")).is_file()
    assert not (tmp_path / _detail("02-third.md")).exists()
    assert (tmp_path / _detail("02-second.md")).is_file()


# --- apply: multi-id (ordered-set) carve ----------------------------------


def _apply_multi(tmp_path: Path, plan_path: Path, plan: Plan, carved_ids):
    fm_hash = compute_frontmatter_hash(plan_path)
    preview = compute_narrow(
        plan,
        carved_ids=carved_ids,
        plan_path=plan_path,
        repo_root=tmp_path,
        source_frontmatter_hash=fm_hash,
    )
    return preview, apply_narrow(plan_path, preview, repo_root=tmp_path)


def test_apply_multi_id_narrows_plan_on_disk(tmp_path):
    plan = _mk_plan(
        [
            _mk_step(1, "First"),
            _mk_step(2, "Second"),
            _mk_step(3, "Third"),
            _mk_step(4, "Fourth", depends_on=[1]),
            _mk_step(5, "Fifth", depends_on=[4]),
        ],
        status=PlanStatus.PLANNING,
    )
    path = _write_plan_file(tmp_path, plan)
    plan = parse_plan(path)

    _apply_multi(tmp_path, path, plan, [2, 3])

    narrowed = parse_plan(path)
    assert [s.id for s in narrowed.steps] == [1, 2, 3]
    assert [s.title for s in narrowed.steps] == ["First", "Fourth", "Fifth"]
    by_id = {s.id: s for s in narrowed.steps}
    assert by_id[2].depends_on == [1]  # old 4 dep on 1 unchanged
    assert by_id[3].depends_on == [2]  # old 5 dep old 4 → new 2


def test_apply_multi_id_archives_every_carved_detail(tmp_path):
    plan = _mk_plan(
        [
            _mk_step(1, "First", detail=_detail("01-first.md")),
            _mk_step(2, "Second", detail=_detail("02-second.md")),
            _mk_step(3, "Third", detail=_detail("03-third.md")),
            _mk_step(4, "Fourth", depends_on=[1], detail=_detail("04-fourth.md")),
        ],
        status=PlanStatus.PLANNING,
    )
    path = _write_plan_file(tmp_path, plan)
    plan = parse_plan(path)
    for rel in ("01-first.md", "02-second.md", "03-third.md", "04-fourth.md"):
        _touch_detail(tmp_path, _detail(rel))

    _, result = _apply_multi(tmp_path, path, plan, [2, 3])

    assert len(result.archived) == 2
    assert all(p.is_file() and p.parent.name == "archive" for p in result.archived)
    names = sorted(p.name for p in result.archived)
    assert names[0].startswith("02-second.")
    assert names[1].startswith("03-third.")
    assert not (tmp_path / _detail("02-second.md")).exists()
    assert not (tmp_path / _detail("03-third.md")).exists()


def test_apply_multi_id_frees_carved_slots_before_downstream_renames(tmp_path):
    # Every detail shares the ``NN-build.md`` stem, so the downstream renames
    # (04→02, 05→03) target paths that the carved 02/03 details still occupy;
    # freeing the carved slots first is what lets those moves land.
    plan = _mk_plan(
        [
            _mk_step(1, "First", detail=_detail("01-build.md")),
            _mk_step(2, "Second", detail=_detail("02-build.md")),
            _mk_step(3, "Third", detail=_detail("03-build.md")),
            _mk_step(4, "Fourth", depends_on=[1], detail=_detail("04-build.md")),
            _mk_step(5, "Fifth", depends_on=[4], detail=_detail("05-build.md")),
        ],
        status=PlanStatus.PLANNING,
    )
    path = _write_plan_file(tmp_path, plan)
    plan = parse_plan(path)
    for n in range(1, 6):
        _touch_detail(tmp_path, _detail(f"0{n}-build.md"), text=f"# 0{n}\n")

    _, result = _apply_multi(tmp_path, path, plan, [2, 3])

    assert (tmp_path / _detail("02-build.md")).read_text(encoding="utf-8") == "# 04\n"
    assert (tmp_path / _detail("03-build.md")).read_text(encoding="utf-8") == "# 05\n"
    assert len(result.archived) == 2
    assert all(p.parent.name == "archive" for p in result.archived)


def test_apply_multi_id_rolls_back_on_failure(tmp_path, monkeypatch):
    plan = _mk_plan(
        [
            _mk_step(1, "First", detail=_detail("01-build.md")),
            _mk_step(2, "Second", detail=_detail("02-build.md")),
            _mk_step(3, "Third", detail=_detail("03-build.md")),
            _mk_step(4, "Fourth", depends_on=[1], detail=_detail("04-build.md")),
            _mk_step(5, "Fifth", depends_on=[4], detail=_detail("05-build.md")),
        ],
        status=PlanStatus.PLANNING,
    )
    path = _write_plan_file(tmp_path, plan)
    plan = parse_plan(path)
    for n in range(1, 6):
        _touch_detail(tmp_path, _detail(f"0{n}-build.md"), text=f"# 0{n}\n")
    before = path.read_text(encoding="utf-8")

    def _boom(*args, **kwargs):
        raise RuntimeError("write failed")

    monkeypatch.setattr(scope_out, "write_plan", _boom)

    fm_hash = compute_frontmatter_hash(path)
    preview = compute_narrow(
        plan, carved_ids=[2, 3], plan_path=path, repo_root=tmp_path,
        source_frontmatter_hash=fm_hash,
    )
    with pytest.raises(RuntimeError):
        apply_narrow(path, preview, repo_root=tmp_path)

    # Every carved detail, downstream rename, and the plan file are restored.
    assert path.read_text(encoding="utf-8") == before
    for n in range(1, 6):
        p = tmp_path / _detail(f"0{n}-build.md")
        assert p.read_text(encoding="utf-8") == f"# 0{n}\n"
    archive_dir = tmp_path / _DETAIL_DIR / "archive"
    assert not archive_dir.exists() or not list(archive_dir.glob("*.md"))


# --------------------------------------------------------------------------
# The orchestrator: scope_out_step seed-first apply-or-recommend gate.
# --------------------------------------------------------------------------


def _seeds_dir(tmp_path: Path) -> Path:
    return tmp_path / "plan-seeds"


def _seed_files(tmp_path: Path) -> list[Path]:
    d = _seeds_dir(tmp_path)
    return sorted(d.glob("*.md")) if d.is_dir() else []


def _raise_prompt(_msg: str) -> str:
    raise AssertionError("prompt_fn should not be called")


def _safe_four_step_plan() -> Plan:
    # Carving step 2 is safe: no survivor depends on it, no downstream DONE
    # (the gate is DONE-only; a downstream CURRENT would not block either).
    return _mk_plan(
        [
            _mk_step(1, "First", status=StepStatus.DONE),
            _mk_step(2, "Second", status=StepStatus.CURRENT),
            _mk_step(3, "Third", depends_on=[1]),
            _mk_step(4, "Fourth", depends_on=[3]),
        ]
    )


def test_applied_writes_seed_then_narrows(tmp_path):
    path = _write_plan_file(tmp_path, _safe_four_step_plan())
    result = scope_out_step(
        path, carved_id=2, repo_root=tmp_path, allow_scope_out=True, yes=True
    )
    assert result.outcome == "applied"
    assert result.seed_path is not None and result.seed_path.is_file()
    assert result.seed_path.parent == _seeds_dir(tmp_path)
    assert isinstance(result.narrow, NarrowResult)
    narrowed = parse_plan(path)
    assert [s.id for s in narrowed.steps] == [1, 2, 3]
    assert "Second" not in [s.title for s in narrowed.steps]


def test_applied_seed_preserves_source_references(tmp_path):
    path = _write_plan_file(tmp_path, _safe_four_step_plan())
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "Plan prose body that survives narrowing.",
            "## References\n\n- [API](https://example.test/api)\n",
        ),
        encoding="utf-8",
    )

    result = scope_out_step(
        path, carved_id=2, repo_root=tmp_path, allow_scope_out=True, yes=True
    )

    assert result.seed_path is not None
    assert "[API](https://example.test/api)" in result.seed_path.read_text(
        encoding="utf-8"
    )


def test_successful_apply_persists_narrow_and_deferrals(tmp_path):
    ownerless = concept_id("Ownerless", [])
    plan = _mk_plan(
        [
            _mk_step(1),
            _mk_step(2, concept_ids=[ownerless]),
            _mk_step(3),
        ],
        status=PlanStatus.PLANNING,
    )
    path = _write_plan_file(tmp_path, plan)
    _save_concept_record(path, "Ownerless")

    result = scope_out_step(
        path, carved_id=2, repo_root=tmp_path, allow_scope_out=True, yes=True
    )

    assert result.outcome == "applied"
    tree = load_concepts(path, compute_plan_fingerprint(path))
    node = next(node for node in tree.concepts if node.id == ownerless)
    assert node.decision == "defer"
    assert node.review_state == "approved"


def _save_flat_decision_record(
    plan_path: Path, title: str, *, plan_fingerprint: str
) -> str:
    """Save the flat ``decision-record`` shape ``create``/``detail`` emit.

    ``plan_fingerprint`` is caller-supplied so a test can build the stale
    provenance a real deferral acquires as soon as the plan moves on.
    """
    cid = concept_id(title, [])
    save_concepts(
        plan_path,
        ConceptTree(
            plan_slug="spin",
            plan_fingerprint=plan_fingerprint,
            record_kind=RECORD_KIND_DECISION,
            concepts=[
                ConceptNode(
                    id=cid,
                    title=title,
                    order=0,
                    decision="defer",
                    review_state="approved",
                    bucket="Out of scope",
                )
            ],
        ),
    )
    return cid


def test_flat_decision_record_survives_an_unrelated_plan_edit(tmp_path):
    """A decision record's ``plan_fingerprint`` is authoring-time provenance
    that ``load_concepts`` deliberately does not gate on, so a plan edited
    since the deferral was recorded must still carve."""
    plan = _mk_plan([_mk_step(1), _mk_step(2), _mk_step(3)])
    path = _write_plan_file(tmp_path, plan)
    _save_flat_decision_record(
        path, "Deferred thing", plan_fingerprint=compute_plan_fingerprint(path)
    )
    # Any later plan/detail write moves the fingerprint — a `run` status flip,
    # a `detail` body, a hand edit. The record stays valid across all of them.
    path.write_text(
        path.read_text(encoding="utf-8") + "\nAn unrelated prose edit.\n",
        encoding="utf-8",
    )

    result = scope_out_step(
        path, carved_id=3, repo_root=tmp_path, allow_scope_out=True, yes=True
    )

    assert result.outcome == "applied"
    assert [s.id for s in parse_plan(path).steps] == [1, 2]


def test_apply_narrow_still_refuses_a_plan_edited_after_prepare(tmp_path):
    """The prepare→apply guard the fingerprint check exists for: a plan that
    moves between ``_prepare_concept_narrow_update`` and ``apply_narrow``."""
    plan = _mk_plan([_mk_step(1), _mk_step(2), _mk_step(3)])
    path = _write_plan_file(tmp_path, plan)
    _save_flat_decision_record(
        path, "Deferred thing", plan_fingerprint=compute_plan_fingerprint(path)
    )
    carved = [parse_plan(path).step_by_id(3)]
    preview = compute_narrow(
        parse_plan(path),
        carved_id=3,
        plan_path=path,
        repo_root=tmp_path,
        source_frontmatter_hash=compute_frontmatter_hash(path),
    )
    update = scope_out._prepare_concept_narrow_update(path, carved, preview)
    assert update is not None

    # A detail file lands after the prepare: the frontmatter is untouched (so
    # the frontmatter hash still matches) but the plan fingerprint moves.
    detail_dir = path.parent / "plan-details" / "spin"
    detail_dir.mkdir(parents=True, exist_ok=True)
    (detail_dir / "01-first.md").write_text("# later\n", encoding="utf-8")

    with pytest.raises(NarrowError, match="changed since the concept record"):
        apply_narrow(path, preview, repo_root=tmp_path, concept_update=update)


def test_recommend_only_never_raises_on_a_broken_concept_record(tmp_path):
    """``ScopeOutResult``'s five outcomes are a closed contract: a
    recommend-only call must report, not raise, whatever the sidecar holds."""
    plan = _mk_plan(
        [_mk_step(1), _mk_step(2), _mk_step(3, concept_ids=["a" * 64])]
    )
    path = _write_plan_file(tmp_path, plan)
    # A record that knows nothing about the id step 3 claims to own.
    _save_flat_decision_record(
        path, "Deferred thing", plan_fingerprint=compute_plan_fingerprint(path)
    )

    result = scope_out_step(
        path, carved_id=3, repo_root=tmp_path, allow_scope_out=False
    )

    assert result.outcome == "recommended"
    assert [s.id for s in parse_plan(path).steps] == [1, 2, 3]


def test_declined_confirm_never_raises_on_a_broken_concept_record(
    tmp_path, monkeypatch
):
    # A real TTY decline, not the non-TTY auto-decline: without this the
    # confirm gate short-circuits and ``prompt_fn`` is never consulted.
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    plan = _mk_plan(
        [_mk_step(1), _mk_step(2), _mk_step(3, concept_ids=["a" * 64])]
    )
    path = _write_plan_file(tmp_path, plan)
    _save_flat_decision_record(
        path, "Deferred thing", plan_fingerprint=compute_plan_fingerprint(path)
    )

    result = scope_out_step(
        path,
        carved_id=3,
        repo_root=tmp_path,
        allow_scope_out=True,
        prompt_fn=lambda _p: "n",
    )

    assert result.outcome == "recommended"
    assert not list(_seeds_dir(tmp_path).glob("*.md"))


def test_apply_still_refuses_an_unknown_carved_concept_id(tmp_path):
    """The gate itself is kept — only its position moved. An opted-in,
    confirmed carve of concept-owned work absent from the record still
    refuses, and writes no seed."""
    plan = _mk_plan(
        [_mk_step(1), _mk_step(2), _mk_step(3, concept_ids=["a" * 64])]
    )
    path = _write_plan_file(tmp_path, plan)
    _save_flat_decision_record(
        path, "Deferred thing", plan_fingerprint=compute_plan_fingerprint(path)
    )

    with pytest.raises(NarrowError, match="absent from the concept record"):
        scope_out_step(
            path, carved_id=3, repo_root=tmp_path, allow_scope_out=True, yes=True
        )

    assert [s.id for s in parse_plan(path).steps] == [1, 2, 3]
    assert not list(_seeds_dir(tmp_path).glob("*.md"))


def test_scope_out_changes_only_ownerless_carved_concepts(tmp_path):
    ownerless = concept_id("Ownerless", [])
    shared = concept_id("Shared", [])
    unrelated = concept_id("Unrelated", [])
    plan = _mk_plan(
        [
            _mk_step(1, concept_ids=[shared]),
            _mk_step(2, concept_ids=[ownerless, shared]),
            _mk_step(3, concept_ids=[unrelated]),
        ],
        status=PlanStatus.PLANNING,
    )
    path = _write_plan_file(tmp_path, plan)
    _save_concept_record(path, "Ownerless", "Shared", "Unrelated")

    scope_out_step(
        path, carved_id=2, repo_root=tmp_path, allow_scope_out=True, yes=True
    )

    tree = load_concepts(path, compute_plan_fingerprint(path))
    decisions = {node.id: node.decision for node in tree.concepts}
    assert decisions == {ownerless: "defer", shared: "include", unrelated: "include"}


def test_recommend_only_does_not_save_concept_record(tmp_path):
    owned = concept_id("Owned", [])
    plan = _mk_plan(
        [_mk_step(1), _mk_step(2, concept_ids=[owned]), _mk_step(3)],
        status=PlanStatus.PLANNING,
    )
    path = _write_plan_file(tmp_path, plan)
    _save_concept_record(path, "Owned")
    sidecar = scope_out.locator.slug_from_filename(path)
    concept_path = path.parent / "plan-details" / sidecar / "concepts.json"
    before = concept_path.read_text(encoding="utf-8")

    result = scope_out_step(
        path, carved_id=2, repo_root=tmp_path, allow_scope_out=False
    )

    assert result.outcome == "recommended"
    assert concept_path.read_text(encoding="utf-8") == before


def test_owned_concept_without_usable_record_refuses_before_writes(tmp_path):
    owned = concept_id("Owned", [])
    plan = _mk_plan(
        [_mk_step(1), _mk_step(2, concept_ids=[owned]), _mk_step(3)],
        status=PlanStatus.PLANNING,
    )
    path = _write_plan_file(tmp_path, plan)
    before = path.read_text(encoding="utf-8")

    with pytest.raises(NarrowError, match="without a current concept record"):
        scope_out_step(
            path, carved_id=2, repo_root=tmp_path, allow_scope_out=True, yes=True
        )

    assert path.read_text(encoding="utf-8") == before
    assert not _seed_files(tmp_path)


def test_unknown_owned_concept_id_refuses_before_writes(tmp_path):
    unknown = "f" * 64
    plan = _mk_plan(
        [_mk_step(1), _mk_step(2, concept_ids=[unknown]), _mk_step(3)],
        status=PlanStatus.PLANNING,
    )
    path = _write_plan_file(tmp_path, plan)
    _save_concept_record(path, "Known")

    with pytest.raises(NarrowError, match="absent from the concept record"):
        scope_out_step(
            path, carved_id=2, repo_root=tmp_path, allow_scope_out=True, yes=True
        )

    assert not _seed_files(tmp_path)


def test_concept_save_failure_rolls_back_narrow(tmp_path, monkeypatch):
    import plan_tool.concept_tree as concept_tree

    owned = concept_id("Owned", [])
    plan = _mk_plan(
        [_mk_step(1), _mk_step(2, concept_ids=[owned]), _mk_step(3)],
        status=PlanStatus.PLANNING,
    )
    path = _write_plan_file(tmp_path, plan)
    _save_concept_record(path, "Owned")
    before_plan = path.read_text(encoding="utf-8")
    concept_path = concept_tree.concepts_path(path)
    before_concepts = concept_path.read_text(encoding="utf-8")
    real_save = concept_tree.save_concepts

    def _save_then_fail(*args, **kwargs):
        real_save(*args, **kwargs)
        raise OSError("publication failed")

    monkeypatch.setattr(concept_tree, "save_concepts", _save_then_fail)
    with pytest.raises(OSError, match="publication failed"):
        scope_out_step(
            path, carved_id=2, repo_root=tmp_path, allow_scope_out=True, yes=True
        )

    assert path.read_text(encoding="utf-8") == before_plan
    assert concept_path.read_text(encoding="utf-8") == before_concepts
    assert len(_seed_files(tmp_path)) == 1


def test_seed_persists_when_narrow_fails(tmp_path, monkeypatch):
    path = _write_plan_file(tmp_path, _safe_four_step_plan())
    before = path.read_text(encoding="utf-8")

    def _boom(*args, **kwargs):
        raise NarrowError("narrow exploded after the seed write")

    monkeypatch.setattr(scope_out, "apply_narrow", _boom)

    with pytest.raises(NarrowError):
        scope_out_step(
            path, carved_id=2, repo_root=tmp_path, allow_scope_out=True, yes=True
        )

    # Seed-first: the durable artifact survives; the plan is untouched.
    assert len(_seed_files(tmp_path)) == 1
    assert path.read_text(encoding="utf-8") == before


def test_step_missing_outcome(tmp_path):
    path = _write_plan_file(tmp_path, _safe_four_step_plan())
    before = path.read_text(encoding="utf-8")
    result = scope_out_step(
        path, carved_id=9, repo_root=tmp_path, allow_scope_out=True, yes=True
    )
    assert result.outcome == "step-missing"
    assert result.seed_path is None
    assert [b.kind for b in result.blockers] == ["step-missing"]
    assert not _seed_files(tmp_path)
    assert path.read_text(encoding="utf-8") == before


def test_empty_plan_outcome(tmp_path):
    plan = _mk_plan([_mk_step(1, "Only")], status=PlanStatus.PLANNING)
    path = _write_plan_file(tmp_path, plan)
    before = path.read_text(encoding="utf-8")
    result = scope_out_step(
        path, carved_id=1, repo_root=tmp_path, allow_scope_out=True, yes=True
    )
    assert result.outcome == "empty-plan"
    assert not _seed_files(tmp_path)
    assert path.read_text(encoding="utf-8") == before


def test_inbound_dependent_is_unsafe(tmp_path):
    plan = _mk_plan(
        [_mk_step(1), _mk_step(2), _mk_step(3, depends_on=[2])],
        status=PlanStatus.PLANNING,
    )
    path = _write_plan_file(tmp_path, plan)
    before = path.read_text(encoding="utf-8")
    result = scope_out_step(
        path, carved_id=2, repo_root=tmp_path, allow_scope_out=True, yes=True
    )
    assert result.outcome == "unsafe"
    assert result.blockers[0].step_ids == [3]
    assert not _seed_files(tmp_path)
    assert path.read_text(encoding="utf-8") == before


def test_downstream_orphan_is_unsafe(tmp_path):
    plan = _mk_plan(
        [
            _mk_step(1, status=StepStatus.DONE),
            _mk_step(2),
            _mk_step(3, depends_on=[1], status=StepStatus.DONE),
        ]
    )
    path = _write_plan_file(tmp_path, plan)
    result = scope_out_step(
        path, carved_id=2, repo_root=tmp_path, allow_scope_out=True, yes=True
    )
    assert result.outcome == "unsafe"
    assert not _seed_files(tmp_path)


def test_not_allowed_recommends_only(tmp_path):
    path = _write_plan_file(tmp_path, _safe_four_step_plan())
    before = path.read_text(encoding="utf-8")
    result = scope_out_step(
        path,
        carved_id=2,
        repo_root=tmp_path,
        allow_scope_out=False,
        prompt_fn=_raise_prompt,
    )
    assert result.outcome == "recommended"
    assert result.preview is not None and not result.preview.blockers
    assert result.seed_path is None
    assert not _seed_files(tmp_path)
    assert path.read_text(encoding="utf-8") == before


def test_non_tty_auto_declines_to_recommended(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    path = _write_plan_file(tmp_path, _safe_four_step_plan())
    before = path.read_text(encoding="utf-8")
    result = scope_out_step(
        path, carved_id=2, repo_root=tmp_path, allow_scope_out=True, yes=False
    )
    assert result.outcome == "recommended"
    assert not _seed_files(tmp_path)
    assert path.read_text(encoding="utf-8") == before


def test_declined_confirm_recommends(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    path = _write_plan_file(tmp_path, _safe_four_step_plan())
    before = path.read_text(encoding="utf-8")
    result = scope_out_step(
        path,
        carved_id=2,
        repo_root=tmp_path,
        allow_scope_out=True,
        yes=False,
        prompt_fn=lambda _msg: "n",
    )
    assert result.outcome == "recommended"
    assert not _seed_files(tmp_path)
    assert path.read_text(encoding="utf-8") == before


def test_yes_bypasses_confirm(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    path = _write_plan_file(tmp_path, _safe_four_step_plan())
    result = scope_out_step(
        path,
        carved_id=2,
        repo_root=tmp_path,
        allow_scope_out=True,
        yes=True,
        prompt_fn=_raise_prompt,
    )
    assert result.outcome == "applied"
    assert len(_seed_files(tmp_path)) == 1


def test_applied_scope_out_frontmatter_reference_uses_body_fallback(tmp_path):
    path = _write_plan_file(tmp_path, _safe_four_step_plan())
    original = path.read_text(encoding="utf-8")
    frontmatter_end = original.index("---\n", len("---\n"))
    path.write_text(
        f"{original[:frontmatter_end]}## References\n{original[frontmatter_end:]}",
        encoding="utf-8",
    )

    result = scope_out_step(
        path, carved_id=2, repo_root=tmp_path, allow_scope_out=True, yes=True
    )

    seed = result.seed_path.read_text(encoding="utf-8")
    references = seed.split("## References", 1)[1].split("## Provenance", 1)[0]
    assert f"- Source plan: `{path}`" in references
    validate_from_existing_seed(seed)


def test_applied_scope_out_fenced_reference_uses_body_fallback(tmp_path):
    path = _write_plan_file(tmp_path, _safe_four_step_plan())
    original = path.read_text(encoding="utf-8")
    path.write_text(
        original.replace(
            "Plan prose body that survives narrowing.",
            "```markdown\n## References\n- https://example.test/api\n```",
        ),
        encoding="utf-8",
    )

    result = scope_out_step(
        path, carved_id=2, repo_root=tmp_path, allow_scope_out=True, yes=True
    )

    seed = result.seed_path.read_text(encoding="utf-8")
    references = seed.split("## References", 1)[1].split("## Provenance", 1)[0]
    assert f"- Source plan: `{path}`" in references
    assert "https://example.test/api" not in references
    validate_from_existing_seed(seed)


def test_done_upstream_context_passed_to_seed(tmp_path):
    plan = _mk_plan(
        [
            _mk_step(1, "Build base", status=StepStatus.DONE),
            _mk_step(2, "Wire base", status=StepStatus.DONE),
            _mk_step(3, "Carved", depends_on=[1, 2], status=StepStatus.CURRENT),
            _mk_step(4, "Tail", depends_on=[1]),
        ]
    )
    path = _write_plan_file(tmp_path, plan)
    result = scope_out_step(
        path, carved_id=3, repo_root=tmp_path, allow_scope_out=True, yes=True
    )
    seed = result.seed_path.read_text(encoding="utf-8")
    section = seed.split("## Upstream prerequisites", 1)[1]
    assert "- step 1: Build base" in section
    assert "- step 2: Wire base" in section


def test_done_upstream_context_includes_note_in_seed(tmp_path):
    plan = _mk_plan(
        [
            _mk_step(1, "Build base", status=StepStatus.DONE),
            _mk_step(
                2,
                "Carved",
                depends_on=[1],
                depends_on_notes={1: "consumes base schema"},
                status=StepStatus.CURRENT,
            ),
            _mk_step(3, "Tail", depends_on=[1]),
        ]
    )
    path = _write_plan_file(tmp_path, plan)
    result = scope_out_step(
        path, carved_id=2, repo_root=tmp_path, allow_scope_out=True, yes=True
    )
    seed = result.seed_path.read_text(encoding="utf-8")
    section = seed.split("## Upstream prerequisites", 1)[1]
    assert "consumes base schema" in section


def test_upstream_shared_dep_first_carved_step_wins(tmp_path):
    plan = _mk_plan(
        [
            _mk_step(1, "Shared dep", status=StepStatus.DONE),
            _mk_step(2, "First carved", depends_on=[1]),
            _mk_step(
                3,
                "Second carved",
                depends_on=[1, 2],
                depends_on_notes={1: "second note"},
            ),
            _mk_step(4, "Tail"),
        ]
    )
    preview = compute_narrow(
        plan,
        carved_ids=[2, 3],
        plan_path=tmp_path / "plan.md",
        repo_root=tmp_path,
        source_frontmatter_hash=_HASH,
    )
    carved_steps = [plan.step_by_id(2), plan.step_by_id(3)]
    ctx = scope_out._resolve_upstream_context(plan, carved_steps, preview)
    assert ctx == [(1, "Shared dep", "done", None)]


def test_carved_region_internal_depends_on_notes_not_in_upstream(tmp_path):
    plan = _mk_plan(
        [
            _mk_step(1, "External", status=StepStatus.DONE),
            _mk_step(
                2,
                "First carved",
                depends_on=[1],
                depends_on_notes={1: "external note"},
            ),
            _mk_step(
                3,
                "Second carved",
                depends_on=[2],
                depends_on_notes={2: "internal note"},
            ),
            _mk_step(4, "Tail"),
        ],
        status=PlanStatus.PLANNING,
    )
    preview = compute_narrow(
        plan,
        carved_ids=[2, 3],
        plan_path=tmp_path / "plan.md",
        repo_root=tmp_path,
        source_frontmatter_hash=_HASH,
    )
    carved_steps = [plan.step_by_id(2), plan.step_by_id(3)]
    ctx = scope_out._resolve_upstream_context(plan, carved_steps, preview)
    assert all(note != "internal note" for *_, note in ctx)
    assert any(note == "external note" for *_, note in ctx)


def test_non_done_upstream_context_passed_to_seed(tmp_path):
    plan = _mk_plan(
        [
            _mk_step(1, "Pending base"),
            _mk_step(2, "Carved", depends_on=[1]),
            _mk_step(3, "Tail", depends_on=[1]),
        ],
        status=PlanStatus.PLANNING,
    )
    path = _write_plan_file(tmp_path, plan)
    result = scope_out_step(
        path, carved_id=2, repo_root=tmp_path, allow_scope_out=True, yes=True
    )
    seed = result.seed_path.read_text(encoding="utf-8")
    external = seed.split("## External prerequisites (not done yet)", 1)[1]
    assert "- step 1 [pending]: Pending base" in external


def test_later_dependency_context_uses_post_narrow_id(tmp_path):
    # Carved step 2 depends on a later PENDING survivor (step 4 → new id 3).
    plan = _mk_plan(
        [
            _mk_step(1, "Base"),
            _mk_step(2, "Carved", depends_on=[4]),
            _mk_step(3, "Mid", depends_on=[1]),
            _mk_step(4, "Late", depends_on=[1]),
        ],
        status=PlanStatus.PLANNING,
    )
    path = _write_plan_file(tmp_path, plan)
    result = scope_out_step(
        path, carved_id=2, repo_root=tmp_path, allow_scope_out=True, yes=True
    )
    seed = result.seed_path.read_text(encoding="utf-8")
    external = seed.split("## External prerequisites (not done yet)", 1)[1]
    assert "- step 3 [pending]: Late" in external
    assert "step 4" not in external


def test_bare_step_seed_has_empty_detail_body(tmp_path):
    path = _write_plan_file(tmp_path, _safe_four_step_plan())
    result = scope_out_step(
        path, carved_id=2, repo_root=tmp_path, allow_scope_out=True, yes=True
    )
    seed = result.seed_path.read_text(encoding="utf-8")
    assert "never detailed" in seed
    assert "Missing detail" not in seed


def test_noncanonical_carved_detail_pointer_passed_to_seed(tmp_path):
    plan = _mk_plan(
        [
            _mk_step(1, "First"),
            _mk_step(2, "Second", detail=_detail("02-custom-name.md")),
            _mk_step(3, "Third", depends_on=[1]),
        ],
        status=PlanStatus.PLANNING,
    )
    path = _write_plan_file(tmp_path, plan)
    _touch_detail(tmp_path, _detail("02-custom-name.md"), text="NONCANON_BODY_MARKER\n")
    result = scope_out_step(
        path, carved_id=2, repo_root=tmp_path, allow_scope_out=True, yes=True
    )
    seed = result.seed_path.read_text(encoding="utf-8")
    assert "NONCANON_BODY_MARKER" in seed
    assert "never detailed" not in seed


def test_set_but_missing_detail_pointer_passes_detail_missing(tmp_path):
    plan = _mk_plan(
        [
            _mk_step(1, "First"),
            _mk_step(2, "Second", detail=_detail("02-gone.md")),
            _mk_step(3, "Third", depends_on=[1]),
        ],
        status=PlanStatus.PLANNING,
    )
    path = _write_plan_file(tmp_path, plan)
    # Pointer is set but the file never exists on disk.
    result = scope_out_step(
        path, carved_id=2, repo_root=tmp_path, allow_scope_out=True, yes=True
    )
    assert result.outcome == "applied"
    seed = result.seed_path.read_text(encoding="utf-8")
    assert "Missing detail" in seed
    assert "never detailed" not in seed


def test_carved_detail_path_matches_narrow_archive(tmp_path):
    # The body the seed captures and the file the narrow archives are the
    # same file (path parity with compute_narrow).
    plan = _mk_plan(
        [
            _mk_step(1, "First"),
            _mk_step(2, "Second", detail=_detail("02-custom-name.md")),
            _mk_step(3, "Third", depends_on=[1]),
        ],
        status=PlanStatus.PLANNING,
    )
    path = _write_plan_file(tmp_path, plan)
    _touch_detail(tmp_path, _detail("02-custom-name.md"))
    parsed = parse_plan(path)
    carved = parsed.step_by_id(2)
    resolved, missing = scope_out._resolve_carved_detail_path(
        path, parsed, carved, tmp_path
    )
    preview = compute_narrow(
        parsed,
        carved_id=2,
        plan_path=path,
        repo_root=tmp_path,
        source_frontmatter_hash=compute_frontmatter_hash(path),
    )
    assert preview.archive_details == [resolved]
    assert missing is False


def test_seed_path_collision_suffixed(tmp_path):
    path = _write_plan_file(tmp_path, _safe_four_step_plan())
    # Pre-occupy the derived base seed path.
    seeds = _seeds_dir(tmp_path)
    seeds.mkdir(parents=True, exist_ok=True)
    base = seeds / "spin-carved-second.md"
    base.write_text("EXISTING_SEED\n", encoding="utf-8")

    result = scope_out_step(
        path, carved_id=2, repo_root=tmp_path, allow_scope_out=True, yes=True
    )
    assert result.seed_path == seeds / "spin-carved-second-2.md"
    assert base.read_text(encoding="utf-8") == "EXISTING_SEED\n"


def test_scope_out_step_carves_contiguous_region(tmp_path):
    plan = _mk_plan(
        [
            _mk_step(1, "First"),
            _mk_step(2, "Second"),
            _mk_step(3, "Third"),
            _mk_step(4, "Fourth", depends_on=[1]),
        ],
        status=PlanStatus.PLANNING,
    )
    path = _write_plan_file(tmp_path, plan)
    result = scope_out_step(
        path, carved_ids=[2, 3], repo_root=tmp_path, allow_scope_out=True, yes=True
    )
    assert result.outcome == "applied"
    assert len(_seed_files(tmp_path)) == 1  # exactly one region seed
    narrowed = parse_plan(path)
    assert [s.id for s in narrowed.steps] == [1, 2]
    assert [s.title for s in narrowed.steps] == ["First", "Fourth"]


def test_region_seed_covers_every_carved_step(tmp_path):
    plan = _mk_plan(
        [
            _mk_step(1, "First"),
            _mk_step(2, "Alpha step", detail=_detail("02-alpha-step.md")),
            _mk_step(3, "Beta step", detail=_detail("03-beta-step.md")),
            _mk_step(4, "Fourth", depends_on=[1]),
        ],
        status=PlanStatus.PLANNING,
    )
    path = _write_plan_file(tmp_path, plan)
    _touch_detail(tmp_path, _detail("02-alpha-step.md"), text="ALPHA_BODY\n")
    _touch_detail(tmp_path, _detail("03-beta-step.md"), text="BETA_BODY\n")
    result = scope_out_step(
        path, carved_ids=[2, 3], repo_root=tmp_path, allow_scope_out=True, yes=True
    )
    seed = result.seed_path.read_text(encoding="utf-8")
    # One "## Scope to re-plan" block per carved step, each with its own body.
    assert seed.count("## Scope to re-plan") == 2
    assert "Alpha step" in seed and "ALPHA_BODY" in seed
    assert "Beta step" in seed and "BETA_BODY" in seed


def test_scope_out_refuses_an_unsupported_detail_marker_on_the_carved_step(tmp_path):
    from plan_tool.detail_artifacts import render_detail_format_version_marker

    plan = _mk_plan(
        [
            _mk_step(1, "First"),
            _mk_step(2, "Second", detail=_detail("02-second.md")),
            _mk_step(3, "Third", depends_on=[1]),
        ],
        status=PlanStatus.PLANNING,
    )
    path = _write_plan_file(tmp_path, plan)
    _touch_detail(
        tmp_path,
        _detail("02-second.md"),
        text=(
            f"# Step 2\n{render_detail_format_version_marker(999)}\n\n"
            "fine.\n"
        ),
    )
    with pytest.raises(DetailFormatError):
        scope_out_step(
            path, carved_id=2, repo_root=tmp_path, allow_scope_out=True, yes=True
        )


def test_region_carve_refuses_an_unsupported_detail_marker_on_any_carved_step(
    tmp_path,
):
    from plan_tool.detail_artifacts import render_detail_format_version_marker

    plan = _mk_plan(
        [
            _mk_step(1, "First"),
            _mk_step(2, "Alpha step", detail=_detail("02-alpha-step.md")),
            _mk_step(3, "Beta step", detail=_detail("03-beta-step.md")),
            _mk_step(4, "Fourth", depends_on=[1]),
        ],
        status=PlanStatus.PLANNING,
    )
    path = _write_plan_file(tmp_path, plan)
    _touch_detail(tmp_path, _detail("02-alpha-step.md"), text="ALPHA_BODY\n")
    # Not the first carved step — proves the sweep isn't only checking index 0.
    _touch_detail(
        tmp_path,
        _detail("03-beta-step.md"),
        text=(
            f"# Step 3\n{render_detail_format_version_marker(999)}\n\n"
            "BETA_BODY\n"
        ),
    )
    with pytest.raises(DetailFormatError):
        scope_out_step(
            path, carved_ids=[2, 3], repo_root=tmp_path, allow_scope_out=True,
            yes=True,
        )


def test_region_seed_excludes_in_region_deps_from_prerequisites(tmp_path):
    # Carved step 3 depends on carved step 2 — an in-region edge, never a
    # prerequisite (it is re-planned together, not an external requirement).
    plan = _mk_plan(
        [
            _mk_step(1, "First"),
            _mk_step(2, "Second"),
            _mk_step(3, "Third", depends_on=[2]),
            _mk_step(4, "Fourth", depends_on=[1]),
        ],
        status=PlanStatus.PLANNING,
    )
    path = _write_plan_file(tmp_path, plan)
    result = scope_out_step(
        path, carved_ids=[2, 3], repo_root=tmp_path, allow_scope_out=True, yes=True
    )
    seed = result.seed_path.read_text(encoding="utf-8")
    assert "## Upstream prerequisites" not in seed
    assert "## External prerequisites" not in seed


def test_region_seed_reports_survivor_dep_as_prerequisite(tmp_path):
    # Carved step 3 depends on surviving step 1 (DONE) — a real prerequisite,
    # rendered by its post-narrow id (step 1 is unshifted).
    plan = _mk_plan(
        [
            _mk_step(1, "Base thing", status=StepStatus.DONE),
            _mk_step(2, "Second"),
            _mk_step(3, "Third", depends_on=[1]),
            _mk_step(4, "Fourth", depends_on=[1]),
        ]
    )
    path = _write_plan_file(tmp_path, plan)
    result = scope_out_step(
        path, carved_ids=[2, 3], repo_root=tmp_path, allow_scope_out=True, yes=True
    )
    seed = result.seed_path.read_text(encoding="utf-8")
    section = seed.split("## Upstream prerequisites", 1)[1]
    assert "- step 1: Base thing" in section


def test_region_seed_path_encodes_range(tmp_path):
    path = _write_plan_file(
        tmp_path,
        _mk_plan(
            [
                _mk_step(1, "First"),
                _mk_step(2, "Second"),
                _mk_step(3, "Third"),
                _mk_step(4, "Fourth", depends_on=[1]),
            ],
            status=PlanStatus.PLANNING,
        ),
    )
    # Pre-occupy the derived region base path so the collision suffix kicks in.
    seeds = _seeds_dir(tmp_path)
    seeds.mkdir(parents=True, exist_ok=True)
    base = seeds / "spin-carved-second-through-3.md"
    base.write_text("EXISTING\n", encoding="utf-8")

    result = scope_out_step(
        path, carved_ids=[2, 3], repo_root=tmp_path, allow_scope_out=True, yes=True
    )
    assert result.seed_path == seeds / "spin-carved-second-through-3-2.md"
    assert base.read_text(encoding="utf-8") == "EXISTING\n"


def test_scope_out_step_still_accepts_carved_id_keyword(tmp_path):
    path = _write_plan_file(tmp_path, _safe_four_step_plan())
    result = scope_out_step(
        path, carved_id=2, repo_root=tmp_path, allow_scope_out=True, yes=True
    )
    assert result.outcome == "applied"
    assert result.carved_ids == [2]
    assert result.carved_id == 2
    assert len(_seed_files(tmp_path)) == 1
    # Single-step seed filename shape is unchanged by the set widening.
    assert result.seed_path.name == "spin-carved-second.md"


def test_scope_out_rejects_unmatched_fence_before_seed_or_narrow(tmp_path):
    path = _write_plan_file(tmp_path, _safe_four_step_plan())
    original = path.read_text(encoding="utf-8") + "\n```\n"
    path.write_text(original, encoding="utf-8")

    with pytest.raises(NarrowError, match="unmatched opening code fence"):
        scope_out_step(
            path, carved_id=2, repo_root=tmp_path, allow_scope_out=True, yes=True
        )

    assert path.read_text(encoding="utf-8") == original
    assert not _seed_files(tmp_path)


def test_region_carve_inbound_dependent_survivor_is_unsafe(tmp_path):
    # A surviving step 4 depends on carved step 3 → no survivor to repoint to.
    plan = _mk_plan(
        [
            _mk_step(1, "First"),
            _mk_step(2, "Second"),
            _mk_step(3, "Third"),
            _mk_step(4, "Fourth", depends_on=[3]),
        ],
        status=PlanStatus.PLANNING,
    )
    path = _write_plan_file(tmp_path, plan)
    before = path.read_text(encoding="utf-8")
    result = scope_out_step(
        path, carved_ids=[2, 3], repo_root=tmp_path, allow_scope_out=True, yes=True
    )
    assert result.outcome == "unsafe"
    assert result.blockers[0].step_ids == [4]
    assert not _seed_files(tmp_path)
    assert path.read_text(encoding="utf-8") == before


def test_region_result_populates_carved_ids_and_scalar(tmp_path):
    path = _write_plan_file(
        tmp_path,
        _mk_plan(
            [
                _mk_step(1, "First"),
                _mk_step(2, "Second"),
                _mk_step(3, "Third"),
                _mk_step(4, "Fourth", depends_on=[1]),
            ],
            status=PlanStatus.PLANNING,
        ),
    )
    result = scope_out_step(
        path, carved_ids=[2, 3], repo_root=tmp_path, allow_scope_out=True, yes=True
    )
    assert result.carved_ids == [2, 3]
    assert result.carved_id == 2  # the region's first (N) id


def test_scope_out_step_takes_no_invoker():
    params = inspect.signature(scope_out_step).parameters
    assert "invoker" not in params
    assert "claude_invoker" not in params


def test_scope_out_result_is_frozen():
    result = ScopeOutResult(outcome="recommended", carved_id=2)
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.outcome = "applied"


# --------------------------------------------------------------------------
# The CLI: plan-tool scope-out end-to-end through main([...]).
# --------------------------------------------------------------------------


def _register_plan(tmp_path: Path, plan: Plan, name: str = "2-spin.md"):
    """Write ``plan`` and a one-entry manifest so ``main`` can resolve it.

    Builds the repo + manifest by hand (the ``registered_plan`` /
    ``tmp_repo`` fixtures live in ``tests/cli/conftest.py`` and are out of
    scope here). Returns ``(plan_path, manifest_path)``.
    """
    path = _write_plan_file(tmp_path, plan, name=name)
    manifest = tmp_path / "m.json"
    manifest.write_text(json.dumps({"plans": [name]}), encoding="utf-8")
    return path, manifest


def _scope_out_argv(tmp_path: Path, manifest: Path, *rest: str) -> list[str]:
    """Global ``--repo-root`` / ``--manifest`` flags + the scope-out subcommand."""
    return [
        "--repo-root",
        str(tmp_path),
        "--manifest",
        str(manifest),
        "scope-out",
        *rest,
    ]


@pytest.mark.integration
class TestScopeOutCLI:
    def test_scope_out_recommend_only_by_default(self, tmp_path, capsys):
        from plan_tool.cli.app import main

        path, manifest = _register_plan(tmp_path, _safe_four_step_plan())
        before = path.read_text(encoding="utf-8")

        rc = main(_scope_out_argv(tmp_path, manifest, "2-spin", "--step", "2"))

        assert rc == 0
        # Nothing written, plan untouched, the --apply opt-in line is shown.
        assert not _seed_files(tmp_path)
        assert path.read_text(encoding="utf-8") == before
        captured = capsys.readouterr()
        assert "--apply" in captured.out + captured.err

    def test_scope_out_apply_yes_carves(self, tmp_path, capsys):
        from plan_tool.cli.app import main
        from plan_tool.create import create_plan, read_existing_description

        path, manifest = _register_plan(tmp_path, _safe_four_step_plan())

        rc = main(
            _scope_out_argv(
                tmp_path, manifest, "2-spin", "--step", "2", "--apply", "-y"
            )
        )
        assert rc == 0

        # The forward-seed was written and the plan narrowed without a TTY.
        seeds = _seed_files(tmp_path)
        assert len(seeds) == 1
        seed_path = seeds[0]
        narrowed = parse_plan(path)
        assert [s.id for s in narrowed.steps] == [1, 2, 3]
        assert "Second" not in [s.title for s in narrowed.steps]

        # Round-trip the emitted seed back through create --from-existing with
        # create's Claude invoker stubbed (no real decomposition): it must
        # ingest cleanly through the deterministic seed-ingestion path.
        canned = json.dumps(
            [{"title": "re-plan the carve", "complexity": "low",
              "files": [], "depends_on": []}]
        )

        def prepared_seed_invoker(prompt: str) -> str:
            if "Distill a free-form seed into a canonical plan body" not in prompt:
                return canned
            evidence_line = next(
                int(number)
                for raw_line in prompt.splitlines()
                if (number := raw_line.partition("\t")[0]).isdigit()
                and (source_line := raw_line.partition("\t")[2]).strip()
                and not source_line.lstrip().startswith(("#", "---"))
            )
            return json.dumps(
                {
                    "outcome": "single",
                    "sections": {
                        "Overview": "Prepared overview.",
                        "Problem statement": "Prepared problem.",
                        "Architecture": "Prepared architecture.",
                        "Out of scope": "candidate",
                        "Risks": "candidate",
                        "Testing": "candidate",
                        "Acceptance criteria": "candidate",
                        "Deferred": "candidate",
                    },
                    "evidence_spans": {
                        key: [{"start_line": evidence_line, "end_line": evidence_line}]
                        for key in (
                            "Out of scope",
                            "Risks",
                            "Testing",
                            "Acceptance criteria",
                            "Deferred",
                        )
                    },
                }
            )

        out_dir = tmp_path / "replanned"
        out_dir.mkdir()
        seed_text = read_existing_description(seed_path)
        result = create_plan(
            "recarve",
            repo_root=tmp_path,
            output_dir_override=out_dir,
            manifest_path=tmp_path / "recarve-m.json",
            from_description=seed_text,
            from_existing_path=seed_path,
            seed_body=seed_text,
            claude_invoker=prepared_seed_invoker,
            yes=True,
            synthesize_body=False,
            fetch_docs=False,
            distill=False,
            resume=False,
            allow_placeholder_body=True,
        )
        assert result.plan_path.is_file()
        replanned = parse_plan(result.plan_path)
        assert [s.title for s in replanned.steps] == ["re-plan the carve"]

    def test_scope_out_unsafe_step_refused(self, tmp_path, capsys):
        from plan_tool.cli.app import main

        # Step 2 has an inbound dependent (step 3) — the carve is refused.
        plan = _mk_plan(
            [_mk_step(1), _mk_step(2), _mk_step(3, depends_on=[2])],
            status=PlanStatus.PLANNING,
        )
        path, manifest = _register_plan(tmp_path, plan)
        before = path.read_text(encoding="utf-8")

        rc = main(
            _scope_out_argv(
                tmp_path, manifest, "2-spin", "--step", "2", "--apply", "-y"
            )
        )

        assert rc == 0  # a refusal is not a failure-to-complete
        assert not _seed_files(tmp_path)
        assert path.read_text(encoding="utf-8") == before
        captured = capsys.readouterr()
        text = captured.out + captured.err
        assert "inbound-dependent" in text
        # The refusal lands on a next action (the re-seed line).
        assert "--from-existing" in text

    def test_scope_out_missing_step_refused(self, tmp_path, capsys):
        from plan_tool.cli.app import main

        path, manifest = _register_plan(tmp_path, _safe_four_step_plan())
        before = path.read_text(encoding="utf-8")

        rc = main(
            _scope_out_argv(
                tmp_path, manifest, "2-spin", "--step", "9", "--apply", "-y"
            )
        )

        assert rc == 0
        assert not _seed_files(tmp_path)
        assert path.read_text(encoding="utf-8") == before
        captured = capsys.readouterr()
        assert "no step with that id" in captured.out + captured.err

    def test_scope_out_in_help(self):
        from plan_tool.cli.app import build_parser

        parser = build_parser()
        choices: dict = {}
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                choices = action.choices
        assert "scope-out" in choices
