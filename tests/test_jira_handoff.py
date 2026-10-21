"""Unit tests for ``plan_tool.jira_handoff`` — the deterministic developer
handoff renderer and shared companion provenance contract."""

from __future__ import annotations

import ast
import json
from dataclasses import replace
from pathlib import Path

import pytest

import plan_tool.jira_handoff as jira_handoff
from plan_tool.jira_handoff import (
    CompanionRenderSettings,
    DETAIL_STATE_MISSING,
    DETAIL_STATE_PRESENT,
    CarriedStoryRecordRenderInput,
    CommittedStepRenderInput,
    DetailRenderInput,
    FileExcerptRenderInput,
    FILE_EXCERPT_STATE_EXCERPT,
    GeneratedSourcePairIdentity,
    HandoffRenderError,
    HandoffRenderInput,
    ParkedStepRenderInput,
    PROVENANCE_FORMAT_REVISION,
    build_companion_provenance,
    compute_input_fingerprint,
    read_json_provenance,
    read_markdown_provenance,
    read_markdown_story_provenance,
    render_handoff,
    render_handoff_body,
    strip_markdown_provenance,
    write_json_provenance,
    write_markdown_provenance,
)
from plan_tool.schema import Plan, Step


def _plan(*steps: Step, title: str = "Demo Plan") -> Plan:
    return Plan(title=title, status="planning", priority="medium", steps=list(steps))


def _pair_identity(**overrides) -> GeneratedSourcePairIdentity:
    defaults = dict(
        story_path="plan-details/demo/jira-stories.md",
        handoff_path="plan-details/demo/jira-handoff.md",
        format="markdown",
    )
    defaults.update(overrides)
    return GeneratedSourcePairIdentity(**defaults)


def _present_detail(path: str = "plan-details/demo/1.md", text: str = "## Intent\n\nDo it.\n") -> DetailRenderInput:
    return DetailRenderInput(state=DETAIL_STATE_PRESENT, path=path, text=text)


def _missing_detail() -> DetailRenderInput:
    return DetailRenderInput(state=DETAIL_STATE_MISSING)


def _companion_settings(**overrides: object) -> CompanionRenderSettings:
    defaults = dict(
        epic_key="DEMO",
        epic_name="Demo epic",
        epic_jira_id="DEMO-1",
        epic_description="Demo description",
        plan_tag="demo",
        max_hours=8,
        start_number=1,
        story_prompt_contract_revision=1,
        handoff_format_contract_revision=1,
    )
    defaults.update(overrides)
    return CompanionRenderSettings(**defaults)


def _render_input(
    *,
    plan: Plan,
    committed_steps: tuple[CommittedStepRenderInput, ...],
    parked_step_history: tuple[ParkedStepRenderInput, ...] = (),
    body_text: str = "",
    grade: str = "run",
    source_plan_path: str = "plans/1-demo.md",
    pair_identity: GeneratedSourcePairIdentity | None = None,
    companion_settings: CompanionRenderSettings | None = None,
) -> HandoffRenderInput:
    return HandoffRenderInput(
        plan=plan,
        body_text=body_text,
        grade=grade,
        source_plan_path=source_plan_path,
        committed_steps=committed_steps,
        parked_step_history=parked_step_history,
        pair_identity=pair_identity or _pair_identity(),
        companion_settings=companion_settings or _companion_settings(),
    )


def _step(id: int, title: str, intent: str = "Do the thing.", **kwargs) -> Step:
    return Step(id=id, title=title, intent=intent, **kwargs)


# --- ordering ----------------------------------------------------------------


def test_handoff_renders_every_committed_step_in_stable_dependency_order() -> None:
    # plan.steps lists step 3 (a dependent) before its prerequisite (step 2),
    # and independent step 1 before both.
    plan = _plan(
        _step(3, "Third", depends_on=[2]),
        _step(1, "First"),
        _step(2, "Second"),
    )
    committed = tuple(
        CommittedStepRenderInput(id=i, detail=_missing_detail())
        for i in (3, 1, 2)
    )
    render_input = _render_input(plan=plan, committed_steps=committed)

    body = render_handoff_body(render_input)

    idx1 = body.index("### Step 1 — First")
    idx2 = body.index("### Step 2 — Second")
    idx3 = body.index("### Step 3 — Third")
    assert idx1 < idx2 < idx3
    assert body.count("### Step ") == 3


def test_handoff_renders_committed_dependency_edges_or_none() -> None:
    plan = _plan(_step(1, "First"), _step(2, "Second", depends_on=[1]))
    committed = (
        CommittedStepRenderInput(id=1, detail=_missing_detail()),
        CommittedStepRenderInput(id=2, detail=_missing_detail()),
    )
    render_input = _render_input(plan=plan, committed_steps=committed)

    body = render_handoff_body(render_input)

    assert "- Depends on: none" in body
    assert "- Depends on: 1 — First" in body


# --- plan path vs. suggested route --------------------------------------------


def test_handoff_keeps_committed_plan_outcome_and_intent_binding_separate_from_route() -> None:
    plan = _plan(_step(1, "Ship the widget", intent="Let users ship widgets."))
    committed = (
        CommittedStepRenderInput(
            id=1, detail=_present_detail(text="## Intent\n\nWidget mechanics.\n")
        ),
    )
    render_input = _render_input(plan=plan, committed_steps=committed)

    body = render_handoff_body(render_input)

    idx_plan_path = body.index("**Plan path**")
    idx_outcome = body.index("- Outcome: Ship the widget")
    idx_intent = body.index("- Intent: Let users ship widgets.")
    idx_route = body.index("**Suggested implementation route**")
    idx_alt = body.index(
        "A developer may choose a different compliant mechanism that still "
        "fulfills the plan path above."
    )
    idx_detail_text = body.index("Widget mechanics.")

    assert idx_plan_path < idx_outcome < idx_route
    assert idx_plan_path < idx_intent < idx_route
    assert idx_route < idx_alt < idx_detail_text


def test_handoff_uses_captured_detail_and_excerpt_values_without_reading_live_paths(
    tmp_path: Path,
) -> None:
    live_path = tmp_path / "plan_tool" / "widget.py"
    live_path.parent.mkdir(parents=True)
    live_path.write_text("live content on disk\n", encoding="utf-8")

    plan = _plan(_step(1, "Ship the widget"))
    committed = (
        CommittedStepRenderInput(
            id=1,
            detail=_present_detail(text="captured snapshot detail body"),
            file_excerpts=(
                FileExcerptRenderInput(
                    path="plan_tool/widget.py",
                    state=FILE_EXCERPT_STATE_EXCERPT,
                    excerpt_text="captured snapshot excerpt body",
                ),
            ),
        ),
    )
    render_input = _render_input(plan=plan, committed_steps=committed)

    body = render_handoff_body(render_input)

    assert "captured snapshot detail body" in body
    assert "captured snapshot excerpt body" in body
    assert "live content on disk" not in body

    # Changing the on-disk file after capture must not change the render.
    live_path.write_text("edited after capture\n", encoding="utf-8")
    body_again = render_handoff_body(render_input)
    assert body_again == body


# --- plan-body context ---------------------------------------------------------


def test_handoff_renders_selected_plan_context_and_excludes_audit_guardrails() -> None:
    body_text = (
        "## Overview\n\nOVERVIEW_MARKER\n\n"
        "## Problem statement\n\nPROBLEM_MARKER\n\n"
        "## Architecture\n\nARCHITECTURE_MARKER\n\n"
        "## Out of scope\n\nOUT_OF_SCOPE_MARKER\n\n"
        "## Risks\n\nRISKS_MARKER\n\n"
        "## Acceptance criteria\n\nACCEPTANCE_MARKER\n\n"
        "## Scope guardrails\n\nSCOPE_GUARDRAILS_MARKER\n\n"
        "## Expected placement\n\nEXPECTED_PLACEMENT_MARKER\n\n"
        "## Audit guardrails\n\nAUDIT_MARKER\n\n"
    )
    plan = _plan(_step(1, "Ship the widget"))
    committed = (CommittedStepRenderInput(id=1, detail=_present_detail()),)
    render_input = _render_input(
        plan=plan, committed_steps=committed, body_text=body_text
    )

    body = render_handoff_body(render_input)

    for marker in (
        "OVERVIEW_MARKER",
        "PROBLEM_MARKER",
        "ARCHITECTURE_MARKER",
        "OUT_OF_SCOPE_MARKER",
        "RISKS_MARKER",
        "ACCEPTANCE_MARKER",
        "SCOPE_GUARDRAILS_MARKER",
        "EXPECTED_PLACEMENT_MARKER",
    ):
        assert marker in body
    assert "AUDIT_MARKER" not in body
    assert "Audit guardrails" not in body


def test_handoff_scope_and_expected_placement_override_suggested_route() -> None:
    plan = _plan(_step(1, "Ship the widget"))
    committed = (CommittedStepRenderInput(id=1, detail=_present_detail()),)

    with_scope = _render_input(
        plan=plan,
        committed_steps=committed,
        body_text="## Scope guardrails\n\nMust stay inside the fence.\n",
    )
    body_with_scope = render_handoff_body(with_scope)
    assert (
        "Scope guardrails and Expected placement in this plan's captured "
        "context win over this suggested route" in body_with_scope
    )
    # No conflict classifier or refusal — the route still renders.
    assert "**Suggested implementation route**" in body_with_scope

    without_scope = _render_input(plan=plan, committed_steps=committed, body_text="")
    body_without_scope = render_handoff_body(without_scope)
    assert (
        "Scope guardrails and Expected placement in this plan's captured "
        "context win over this suggested route" not in body_without_scope
    )


# --- binding-input errors -------------------------------------------------------


def test_handoff_rejects_non_done_step_without_title_or_meaningful_intent() -> None:
    committed = (CommittedStepRenderInput(id=1, detail=_missing_detail()),)

    blank_title_plan = _plan(_step(1, "   ", intent="Do the thing."))
    with pytest.raises(HandoffRenderError):
        render_handoff_body(
            _render_input(plan=blank_title_plan, committed_steps=committed)
        )

    no_intent_plan = _plan(_step(1, "Ship it", intent=None))
    with pytest.raises(HandoffRenderError):
        render_handoff_body(
            _render_input(plan=no_intent_plan, committed_steps=committed)
        )

    placeholder_intent_plan = _plan(_step(1, "Ship it", intent="TBD"))
    with pytest.raises(HandoffRenderError):
        render_handoff_body(
            _render_input(plan=placeholder_intent_plan, committed_steps=committed)
        )


# --- done-step / parked-step history --------------------------------------------


def test_handoff_renders_done_step_status_and_missing_sources_as_visible_history() -> None:
    plan = _plan(_step(1, "Ship the widget", intent=None, status="done"))
    committed = (CommittedStepRenderInput(id=1, detail=_missing_detail()),)
    render_input = _render_input(plan=plan, committed_steps=committed)

    body = render_handoff_body(render_input)

    assert "- Status: done — historical; no implementation action" in body
    assert "- Intent: _(no meaningful intent recorded)_" in body
    assert "_(no selected detail captured for this historical step)_" in body
    assert "**Suggested implementation route**" not in body


def test_handoff_renders_done_step_excerpts_only_as_historical_context() -> None:
    plan = _plan(_step(1, "Ship the widget", status="done"))
    committed = (
        CommittedStepRenderInput(
            id=1,
            detail=_present_detail(text="completed implementation detail"),
            file_excerpts=(
                FileExcerptRenderInput(
                    path="plan_tool/widget.py",
                    state=FILE_EXCERPT_STATE_EXCERPT,
                    excerpt_text="completed implementation excerpt",
                ),
            ),
        ),
    )

    body = render_handoff_body(_render_input(plan=plan, committed_steps=committed))

    assert "**Historical declared files**" in body
    assert "completed implementation excerpt" in body
    assert "**Suggested implementation route**" not in body


def test_handoff_renders_blank_done_title_as_not_recorded() -> None:
    plan = _plan(_step(1, "", intent=None, status="done"))
    committed = (CommittedStepRenderInput(id=1, detail=_missing_detail()),)
    render_input = _render_input(plan=plan, committed_steps=committed)

    body = render_handoff_body(render_input)

    assert "### Step 1 — _(title not recorded)_" in body
    assert "- Outcome: _(title not recorded)_" in body


def test_handoff_lists_parked_steps_as_non_actionable_history_only() -> None:
    plan = _plan(_step(1, "Ship the widget"))
    committed = (CommittedStepRenderInput(id=1, detail=_missing_detail()),)
    parked = (
        ParkedStepRenderInput(
            id=9, title="Gated feature", scope="deferred", status_note="waiting on X"
        ),
        ParkedStepRenderInput(id=10, title="Abandoned idea", scope="wont_do"),
    )
    render_input = _render_input(
        plan=plan, committed_steps=committed, parked_step_history=parked
    )

    body = render_handoff_body(render_input)

    parked_section = body[body.index("## Parked plan history") :]
    assert "- Step 9 — Gated feature (scope: deferred) — waiting on X" in parked_section
    assert (
        "- Step 10 — Abandoned idea (scope: wont_do) — "
        "_(no status note recorded)_" in parked_section
    )
    assert "Depends on" not in parked_section
    assert "Outcome:" not in parked_section
    assert "Suggested implementation route" not in parked_section


def test_handoff_never_renders_dropped_story_history_as_a_committed_plan_path_step() -> None:
    plan = _plan(_step(1, "Ship the widget"))
    committed = (CommittedStepRenderInput(id=1, detail=_present_detail()),)
    render_input = _render_input(plan=plan, committed_steps=committed)

    body = render_handoff_body(render_input)
    assert "999" not in body
    assert "DROP-1" not in body
    assert "dropped ticket" not in body

    dropped_record = CarriedStoryRecordRenderInput(
        id="DROP-1",
        steps=(999,),
        export_state="dropped",
        jira_issue_key="PROJ-999",
        rendered_content="dropped ticket content mentioning step 999",
    )
    provenance_without = build_companion_provenance(
        render_input,
    )
    provenance_with = build_companion_provenance(
        render_input,
        existing_story_records=(dropped_record,),
    )
    assert provenance_without.fingerprint != provenance_with.fingerprint

    text_without = render_handoff(render_input, provenance_without)
    text_with = render_handoff(render_input, provenance_with)
    assert "999" not in text_without.split("-->", 1)[1]
    assert "999" not in text_with.split("-->", 1)[1]
    assert render_handoff_body(render_input) == body


# --- companion provenance --------------------------------------------------------


def test_companion_provenance_records_complete_pair_identity_for_both_output_formats() -> None:
    plan = _plan(_step(1, "Ship the widget"))
    committed = (
        CommittedStepRenderInput(
            id=1, detail=_present_detail(path="plan-details/demo/1.md")
        ),
    )
    pair_identity = _pair_identity(
        story_path="plan-details/demo/jira-stories.json",
        handoff_path="plan-details/demo/jira-handoff.md",
        format="json",
    )
    render_input = _render_input(
        plan=plan,
        committed_steps=committed,
        pair_identity=pair_identity,
        companion_settings=_companion_settings(
            story_prompt_contract_revision=3,
            handoff_format_contract_revision=5,
        ),
    )

    provenance = build_companion_provenance(render_input)

    assert provenance.pair_identity == pair_identity
    assert provenance.selected_detail_source_paths == ((1, "plan-details/demo/1.md"),)

    md_block = write_markdown_provenance(provenance)
    assert read_markdown_provenance(md_block) == provenance

    full_handoff = render_handoff(render_input, provenance)
    assert read_markdown_provenance(full_handoff) == provenance

    json_block = write_json_provenance(provenance)
    assert read_json_provenance(json_block) == provenance

    story_payload = {"plan_title": "Demo Plan", **json_block, "stories": []}
    assert read_json_provenance(json.dumps(story_payload)) == provenance


def test_markdown_provenance_preserves_detail_paths_with_delimiters() -> None:
    plan = _plan(_step(1, "Ship the widget"))
    render_input = _render_input(
        plan=plan,
        committed_steps=(
            CommittedStepRenderInput(
                id=1,
                detail=_present_detail(path="plan-details/a|b=widget.md"),
            ),
        ),
    )

    provenance = build_companion_provenance(render_input)

    assert read_markdown_provenance(write_markdown_provenance(provenance)) == provenance


def test_json_provenance_preserves_detail_path_order_like_markdown_does() -> None:
    # A dependent step can be captured ahead of its (lower-numbered)
    # prerequisite -- _stable_committed_order is topological, not strictly
    # ascending. Both provenance formats must round-trip that exact order,
    # not silently reorder it, since compute_input_fingerprint is
    # order-sensitive.
    plan = _plan(_step(2, "Ship the widget"), _step(1, "Prep the widget"))
    render_input = _render_input(
        plan=plan,
        committed_steps=(
            CommittedStepRenderInput(
                id=2, detail=_present_detail(path="plan-details/demo/2.md")
            ),
            CommittedStepRenderInput(
                id=1, detail=_present_detail(path="plan-details/demo/1.md")
            ),
        ),
    )

    provenance = build_companion_provenance(render_input)
    assert provenance.selected_detail_source_paths == (
        (2, "plan-details/demo/2.md"),
        (1, "plan-details/demo/1.md"),
    )

    assert read_markdown_provenance(write_markdown_provenance(provenance)) == provenance
    assert read_json_provenance(write_json_provenance(provenance)) == provenance


def test_markdown_provenance_ignores_a_look_alike_block_in_story_body_prose() -> None:
    # A story documenting or quoting this feature can legitimately contain
    # the literal provenance marker text as an example. Only the real,
    # writer-placed trailing block may be recognized or stripped -- a
    # look-alike earlier in the body must survive untouched.
    plan = _plan(_step(1, "Ship the widget"))
    render_input = _render_input(
        plan=plan,
        committed_steps=(
            CommittedStepRenderInput(id=1, detail=_present_detail()),
        ),
    )
    provenance = build_companion_provenance(render_input)

    fake_block = (
        "<!-- plan-tool-companion-provenance\n"
        "this is an example of the provenance format\n"
        "-->"
    )
    story_with_fake = (
        "# Story\n\nSee the format below:\n\n"
        + fake_block
        + "\n\nRest of the story body.\n"
    )
    real_block = write_markdown_provenance(provenance)
    text = story_with_fake.rstrip("\n") + "\n\n" + real_block + "\n"

    # The real trailing block still parses correctly...
    assert read_markdown_provenance(text) == provenance
    # ...and stripping it must not delete the fake block or the story
    # content that follows it.
    stripped = strip_markdown_provenance(text)
    assert fake_block in stripped
    assert "Rest of the story body." in stripped
    assert "plan-tool-companion-provenance" not in stripped.rsplit(fake_block, 1)[1]


def test_story_ownership_requires_the_generated_story_provenance_position() -> None:
    plan = _plan(_step(1, "Ship the widget"))
    render_input = _render_input(
        plan=plan,
        committed_steps=(CommittedStepRenderInput(id=1, detail=_present_detail()),),
    )
    provenance = build_companion_provenance(render_input)
    text = "parked status note\n\n" + write_markdown_provenance(provenance)

    assert read_markdown_provenance(text) == provenance
    assert read_markdown_story_provenance(text) is None


def test_story_provenance_round_trips_for_a_plan_with_an_empty_title() -> None:
    # Plan.title carries no non-empty validator (schema.py), so an empty
    # title is legal. The story header then renders as
    # "# JIRA stories — " with nothing after the trailing space, which
    # must still round-trip the same way a non-empty title does -- the
    # sibling handoff title regex already allows zero trailing characters.
    plan = _plan(_step(1, "Ship the widget"))
    render_input = _render_input(
        plan=plan,
        committed_steps=(CommittedStepRenderInput(id=1, detail=_present_detail()),),
    )
    provenance = build_companion_provenance(render_input)
    text = (
        "# JIRA stories — \n\nStory body.\n\n" + write_markdown_provenance(provenance)
    )

    assert read_markdown_story_provenance(text) == provenance


def test_handoff_fingerprint_changes_for_carried_story_records_but_excludes_predecessor_ownership_evidence() -> None:
    plan = _plan(_step(1, "Ship the widget"), _step(2, "Verify the widget"))
    committed = (
        CommittedStepRenderInput(id=1, detail=_present_detail()),
        CommittedStepRenderInput(id=2, detail=_present_detail()),
    )
    render_input = _render_input(plan=plan, committed_steps=committed)

    base_record = CarriedStoryRecordRenderInput(
        id="AUTH-S1",
        steps=(2, 1),
        export_state="created",
        jira_issue_key="PROJ-1",
        rendered_content="content v1",
        raw_target_proof="sha-aaa",
        predecessor_provenance_fingerprint="fp-aaa",
    )
    baseline = compute_input_fingerprint(render_input, (base_record,))

    only_evidence_changed = replace(
        base_record,
        raw_target_proof="sha-completely-different",
        predecessor_provenance_fingerprint="fp-completely-different",
    )
    assert compute_input_fingerprint(render_input, (only_evidence_changed,)) == baseline

    reordered_steps = replace(base_record, steps=(1, 2))
    assert compute_input_fingerprint(render_input, (reordered_steps,)) == baseline

    content_changed = replace(base_record, rendered_content="content v2")
    assert compute_input_fingerprint(render_input, (content_changed,)) != baseline

    state_changed = replace(base_record, export_state="dropped")
    assert compute_input_fingerprint(render_input, (state_changed,)) != baseline

    key_changed = replace(base_record, jira_issue_key="PROJ-2")
    assert compute_input_fingerprint(render_input, (key_changed,)) != baseline


def test_handoff_fingerprint_changes_for_every_companion_render_setting() -> None:
    plan = _plan(_step(1, "Ship the widget"))
    committed = (CommittedStepRenderInput(id=1, detail=_present_detail()),)
    render_input = _render_input(plan=plan, committed_steps=committed)
    baseline = compute_input_fingerprint(render_input)

    for changed_settings in (
        _companion_settings(epic_key="OTHER"),
        _companion_settings(epic_name="Other epic"),
        _companion_settings(epic_jira_id="OTHER-1"),
        _companion_settings(epic_description="Other description"),
        _companion_settings(plan_tag="other"),
        _companion_settings(max_hours=13),
        _companion_settings(start_number=3),
        _companion_settings(story_prompt_contract_revision=2),
        _companion_settings(handoff_format_contract_revision=2),
    ):
        changed_input = replace(render_input, companion_settings=changed_settings)
        assert compute_input_fingerprint(changed_input) != baseline


def test_handoff_fingerprint_changes_for_a_file_excerpt_fallback_reason() -> None:
    # compute_input_fingerprint's docstring promises a deterministic hash
    # "over every captured value that can change either generated source";
    # _render_file_excerpts renders fallback_reason as its own line, so two
    # renders differing only in it produce different handoff bodies and
    # must not collide on the same fingerprint.
    plan = _plan(_step(1, "Ship the widget"))

    def render_input_with_reason(reason: str) -> object:
        committed = (
            CommittedStepRenderInput(
                id=1,
                detail=_present_detail(),
                file_excerpts=(
                    FileExcerptRenderInput(
                        path="plan_tool/widget.py",
                        state=FILE_EXCERPT_STATE_EXCERPT,
                        excerpt_text="fallback preview: same text either way",
                        fallback_reason=reason,
                    ),
                ),
            ),
        )
        return _render_input(plan=plan, committed_steps=committed)

    baseline = compute_input_fingerprint(
        render_input_with_reason("no-symbol-match")
    )
    changed = compute_input_fingerprint(
        render_input_with_reason("unsupported-file-type")
    )
    assert baseline != changed


def test_companion_provenance_readers_reject_missing_or_malformed_generated_metadata() -> None:
    plan = _plan(_step(1, "Ship the widget"))
    committed = (CommittedStepRenderInput(id=1, detail=_present_detail()),)
    render_input = _render_input(plan=plan, committed_steps=committed)
    provenance = build_companion_provenance(render_input)

    assert read_markdown_provenance("no marker here at all") is None

    md_block = write_markdown_provenance(provenance)
    missing_field = md_block.replace("fingerprint: " + provenance.fingerprint, "")
    assert read_markdown_provenance(missing_field) is None

    bad_revision = md_block.replace(
        "provenance_format_revision: 1",
        f"provenance_format_revision: {PROVENANCE_FORMAT_REVISION + 1}",
    )
    assert read_markdown_provenance(bad_revision) is None

    non_numeric_revision = md_block.replace(
        "provenance_format_revision: 1", "provenance_format_revision: not-a-number"
    )
    assert read_markdown_provenance(non_numeric_revision) is None

    assert read_json_provenance("not valid json") is None
    assert read_json_provenance("{}") is None
    assert read_json_provenance(json.dumps({"plan_title": "x"})) is None

    json_block = write_json_provenance(provenance)
    key = "plan_tool_companion_provenance"
    incomplete = dict(json_block[key])
    del incomplete["fingerprint"]
    assert read_json_provenance({key: incomplete}) is None

    wrong_shape = dict(json_block[key])
    wrong_shape["pair_identity"] = "not-a-dict"
    assert read_json_provenance({key: wrong_shape}) is None

    # bool is an int subclass -- int(True) == 1 must not be silently
    # accepted as a valid revision for any of the three revision fields.
    for revision_key in (
        "provenance_format_revision",
        "story_prompt_contract_revision",
        "handoff_format_contract_revision",
    ):
        boolean_revision = dict(json_block[key])
        boolean_revision[revision_key] = True
        assert read_json_provenance({key: boolean_revision}) is None

    # int(1.9) == 1 in Python -- a JSON float revision must not be
    # silently truncated into a valid-looking int the way int(<text>) on
    # a Markdown fractional value naturally rejects instead (below).
    for revision_key in (
        "provenance_format_revision",
        "story_prompt_contract_revision",
        "handoff_format_contract_revision",
    ):
        fractional_revision = dict(json_block[key])
        fractional_revision[revision_key] = float(fractional_revision[revision_key]) + 0.9
        assert read_json_provenance({key: fractional_revision}) is None

    fractional_md_revision = md_block.replace(
        "provenance_format_revision: 1", "provenance_format_revision: 1.9"
    )
    assert read_markdown_provenance(fractional_md_revision) is None


def test_companion_provenance_readers_reject_unicode_digit_step_ids_without_raising() -> None:
    plan = _plan(_step(1, "Ship the widget"))
    render_input = _render_input(
        plan=plan,
        committed_steps=(CommittedStepRenderInput(id=1, detail=_present_detail()),),
    )
    provenance = build_companion_provenance(render_input)

    json_block = write_json_provenance(provenance)
    json_block["plan_tool_companion_provenance"]["selected_detail_source_paths"] = {
        "²": "plan-details/demo/1.md"
    }
    assert read_json_provenance(json_block) is None

    markdown_block = write_markdown_provenance(provenance).replace(
        'selected_detail_source_paths: [[1,"plan-details/demo/1.md"]]',
        "selected_detail_source_paths: ²=plan-details/demo/1.md",
    )
    assert read_markdown_provenance(markdown_block) is None


def test_handoff_discloses_excerpt_kind_and_truncation() -> None:
    plan = _plan(_step(1, "Ship the widget"))
    committed = (
        CommittedStepRenderInput(
            id=1,
            detail=_present_detail(),
            file_excerpts=(
                FileExcerptRenderInput(
                    path="plan_tool/widget.py",
                    state=FILE_EXCERPT_STATE_EXCERPT,
                    excerpt_text="partial body",
                    excerpt_kind="fallback",
                    fallback_reason="no-symbol-match",
                    truncated=True,
                ),
            ),
        ),
    )

    body = render_handoff_body(_render_input(plan=plan, committed_steps=committed))

    assert (
        "_excerpt_kind: fallback; fallback_reason: no-symbol-match; "
        "truncated: true_"
    ) in body


# --- import boundary --------------------------------------------------------------


def test_jira_handoff_does_not_import_plan_tool_jira_at_runtime() -> None:
    source = Path(jira_handoff.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name != "plan_tool.jira", (
                    "plan_tool/jira_handoff.py must not import plan_tool.jira"
                )
        elif isinstance(node, ast.ImportFrom):
            assert node.module != "plan_tool.jira", (
                "plan_tool/jira_handoff.py must not import from plan_tool.jira"
            )


def test_handoff_plan_context_ignores_fenced_pseudo_heading() -> None:
    plan = _plan(_step(1, "Ship the widget"))
    body = render_handoff_body(
        _render_input(
            plan=plan,
            committed_steps=(
                CommittedStepRenderInput(id=1, detail=_present_detail()),
            ),
            body_text=(
                "## Overview\n\nBefore the example.\n\n```markdown\n"
                "## Architecture\nExample-only architecture.\n```\n\n"
                "After the example.\n\n"
                "## Architecture\n\nReal architecture.\n"
            ),
        )
    )

    assert "Example-only architecture." in body
    assert "After the example." in body
    assert "Real architecture." in body


def test_handoff_preview_renders_unmatched_plan_body() -> None:
    plan = _plan(_step(1, "Ship the widget"))

    body = render_handoff_body(
        _render_input(
            plan=plan,
            committed_steps=(CommittedStepRenderInput(id=1, detail=_present_detail()),),
            body_text="## Overview\n\nPreview source remains visible.\n\n```\n",
        )
    )

    assert "Preview source remains visible." in body


def test_stack_and_audit_guardrails_are_deliberately_absent_from_the_handoff_whitelist() -> None:
    """The handoff section list is a whitelist; a later consolidation over
    ``GUARDRAIL_BODY_SECTIONS`` must not start carrying these two into a handoff."""
    names = jira_handoff._PLAN_CONTEXT_SECTION_NAMES

    assert "Stack" not in names
    assert "Audit guardrails" not in names
