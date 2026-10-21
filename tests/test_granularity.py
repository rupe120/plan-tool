"""Unit tests for ``plan_tool.granularity`` — the deterministic split/merge
granularity advisor leaf."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from plan_tool import review
from plan_tool.granularity import (
    DETERMINISTIC_SPLIT_PREDICATE_KEYS,
    GRANULARITY_MERGE_SOURCE,
    GRANULARITY_SPLIT_SOURCE,
    GranularityEvidence,
    SPLIT_PREDICATE_CONJOINED_CLAUSES,
    SPLIT_PREDICATE_KEYS,
    SPLIT_PREDICATE_MIXED_STEP,
    SPLIT_PREDICATE_MIXED_VERBS,
    SPLIT_PREDICATE_UNRELATED_AREAS,
    assess_granularity,
    parse_mixed_step_findings,
    split_predicate_key,
)
from plan_tool.schema import ChangeType, Plan, Step


def _plan(*steps: Step) -> Plan:
    return Plan(title="Demo", status="planning", priority="medium", steps=list(steps))


def _evidence() -> GranularityEvidence:
    return GranularityEvidence()


def _split_recs(recs: list[review.Recommendation]) -> list[review.Recommendation]:
    return [r for r in recs if r.source == GRANULARITY_SPLIT_SOURCE]


def _merge_recs(recs: list[review.Recommendation]) -> list[review.Recommendation]:
    return [r for r in recs if r.source == GRANULARITY_MERGE_SOURCE]


def _single_split_rec(step: Step) -> review.Recommendation:
    recs = _split_recs(assess_granularity(_plan(step), stage="create",
                                          evidence=_evidence()))
    assert len(recs) == 1
    return recs[0]


# --- contract guards -------------------------------------------------------


@pytest.mark.parametrize("stage", ["create", "detail", "completeness"])
def test_returns_recommendations_for_each_stage(stage: str) -> None:
    plan = _plan(Step(id=1, title="Add login", files=["plan_tool/auth.py"]))
    recs = assess_granularity(plan, stage=stage, evidence=_evidence())
    assert isinstance(recs, list)
    assert all(isinstance(r, review.Recommendation) for r in recs)


def test_invalid_stage_raises() -> None:
    plan = _plan(Step(id=1, title="Add login", files=["plan_tool/auth.py"]))
    with pytest.raises(ValueError):
        assess_granularity(plan, stage="bogus", evidence=_evidence())


# --- split detectors -------------------------------------------------------


def test_mixed_refactor_feature_title_yields_split() -> None:
    plan = _plan(
        Step(id=1, title="Refactor parser to add validation", files=["plan_tool/parser.py"])
    )
    recs = _split_recs(assess_granularity(plan, stage="create", evidence=_evidence()))
    assert len(recs) == 1
    assert "mixes refactor and feature" in recs[0].title


def test_title_conjunction_yields_split() -> None:
    # Two feature verbs, so mixed-verbs does not trip — isolates the conjunction.
    plan = _plan(
        Step(id=1, title="Add login and wire the handler", files=["plan_tool/auth.py"])
    )
    recs = _split_recs(assess_granularity(plan, stage="create", evidence=_evidence()))
    assert len(recs) == 1
    assert "conjoins multiple action clauses" in recs[0].title


def test_comma_separated_action_clauses_yield_split() -> None:
    # Comma is a clause separator too: three verb-led clauses → over-packed.
    plan = _plan(
        Step(id=1, title="Add the parser, build the renderer, wire the loop",
             files=["plan_tool/x.py"])
    )
    recs = _split_recs(assess_granularity(plan, stage="create", evidence=_evidence()))
    assert len(recs) == 1
    assert "conjoins multiple action clauses" in recs[0].title
    assert "3 verb-led clauses" in recs[0].body


def test_comma_noun_enumeration_does_not_trip() -> None:
    # A verb followed by a comma-led NOUN list is one concern, not many — the
    # verb-led guard keeps the comma separator precise.
    plan = _plan(
        Step(id=1, title="Add the parser, the extractor, and the enumerator",
             files=["plan_tool/x.py"])
    )
    recs = _split_recs(assess_granularity(plan, stage="create", evidence=_evidence()))
    assert recs == []


def test_parenthetical_flag_list_does_not_trip() -> None:
    # Commas inside a parenthetical flag list are not clause boundaries (the
    # fragments aren't verb-led).
    plan = _plan(
        Step(id=1, title="Add subcommand (--target plan|code, --reconcile, --step)",
             files=["plan_tool/x.py"])
    )
    recs = _split_recs(assess_granularity(plan, stage="create", evidence=_evidence()))
    assert recs == []


def test_unrelated_file_span_yields_split() -> None:
    # Two genuinely-unrelated top-level CODE areas trip the split.
    plan = _plan(
        Step(
            id=1,
            title="Wire the thing",
            files=["plan_tool/auth.py", "amplify/handler.py"],
        )
    )
    recs = _split_recs(assess_granularity(plan, stage="create", evidence=_evidence()))
    assert len(recs) == 1
    assert "spans unrelated areas" in recs[0].title


def test_logic_plus_cli_slice_does_not_trip_area_split() -> None:
    # A package and its sub-package (logic + its CLI) are ONE vertical slice,
    # not two unrelated areas — must not false-positive (top-1 segment).
    plan = _plan(
        Step(
            id=1,
            title="Add the feature and its CLI flag",
            files=["plan_tool/jira.py", "plan_tool/cli/jira_cmd.py"],
        )
    )
    recs = _split_recs(assess_granularity(plan, stage="create", evidence=_evidence()))
    assert not any("spans unrelated areas" in r.title for r in recs)


def test_code_step_with_companion_doc_does_not_trip_area_split() -> None:
    # A `.md` doc rider alongside a code change is not a distinct area.
    plan = _plan(
        Step(
            id=1,
            title="Wire the thing",
            files=["plan_tool/auth.py"],
            creates=["docs/AUTH.md"],
        )
    )
    recs = _split_recs(assess_granularity(plan, stage="create", evidence=_evidence()))
    assert not any("spans unrelated areas" in r.title for r in recs)


def test_non_code_doc_step_across_many_surfaces_does_not_trip_area_split() -> None:
    # A non-code step that documents across many surfaces is not over-packed.
    plan = _plan(
        Step(
            id=1,
            title="Document across the operator surfaces",
            files=["README.md", "RUNBOOK.md", "CLAUDE.md", "docs/cli/x.md"],
            change_type=ChangeType.NON_CODE,
        )
    )
    recs = _split_recs(assess_granularity(plan, stage="create", evidence=_evidence()))
    assert not any("spans unrelated areas" in r.title for r in recs)


def test_step1_self_title_does_not_trip_split() -> None:
    plan = _plan(
        Step(
            id=1,
            title=(
                "Add cycle-free granularity leaf: assess_granularity contract, "
                "GranularityEvidence, and deterministic split/merge signals"
            ),
            files=["plan_tool/granularity.py"],
            creates=["tests/test_granularity.py"],
        )
    )
    assert _split_recs(assess_granularity(plan, stage="create", evidence=_evidence())) == []


def test_single_concern_step_yields_no_split() -> None:
    plan = _plan(
        Step(
            id=1,
            title="Add the granularity leaf",
            files=["plan_tool/granularity.py"],
            creates=["tests/test_granularity.py"],
        )
    )
    assert _split_recs(assess_granularity(plan, stage="create", evidence=_evidence())) == []


# --- merge detectors -------------------------------------------------------


def test_identical_file_sets_adjacent_yields_merge() -> None:
    plan = _plan(
        Step(id=1, title="Add part one", files=["plan_tool/auth.py"]),
        Step(id=2, title="Add part two", files=["plan_tool/auth.py"], depends_on=[1]),
    )
    recs = _merge_recs(assess_granularity(plan, stage="create", evidence=_evidence()))
    assert len(recs) == 1
    assert recs[0].step_id == 1


def test_trivial_refactor_feeding_one_feature_yields_merge() -> None:
    plan = _plan(
        Step(
            id=1,
            title="Extract helper",
            files=["plan_tool/helper.py"],
            change_type=ChangeType.REFACTOR,
        ),
        Step(
            id=2,
            title="Add feature on top",
            files=["plan_tool/feature.py"],
            change_type=ChangeType.FEATURE,
            depends_on=[1],
        ),
    )
    recs = _merge_recs(assess_granularity(plan, stage="create", evidence=_evidence()))
    assert len(recs) == 1
    assert recs[0].step_id == 1


def test_non_adjacent_or_distinct_files_no_merge() -> None:
    plan = _plan(
        Step(id=1, title="Add alpha", files=["plan_tool/alpha.py"]),
        Step(id=2, title="Add beta", files=["plan_tool/beta.py"]),
    )
    assert _merge_recs(assess_granularity(plan, stage="create", evidence=_evidence())) == []


def test_merge_rec_carries_merge_directive() -> None:
    plan = _plan(
        Step(id=1, title="Add part one", files=["plan_tool/auth.py"]),
        Step(id=2, title="Add part two", files=["plan_tool/auth.py"], depends_on=[1]),
    )
    rec = _merge_recs(assess_granularity(plan, stage="create", evidence=_evidence()))[0]
    assert "→ merge steps: 1, 2" in rec.suggested_action
    action = review.parse_merge_action(rec)
    assert action == review.MergeAction(kind=review.MERGE_ACTION_MERGE, step_ids=(1, 2))


def test_gapped_merge_pair_is_recommend_only_no_directive() -> None:
    # A dependency-adjacent but id-NON-contiguous pair (step 3 depends_on step 1,
    # identical files, step 2 unrelated in between) can never be folded by
    # merge_steps (it needs a contiguous run). The finding is still surfaced but
    # WITHOUT the dispatchable marker, so it routes through neutral triage
    # instead of dispatching to merge_bridge and failing with a confusing
    # "invalid" — gapped pairs need manual operator judgment.
    plan = _plan(
        Step(id=1, title="Add part one", files=["plan_tool/auth.py"]),
        Step(id=2, title="Unrelated", files=["plan_tool/other.py"]),
        Step(id=3, title="Add part two", files=["plan_tool/auth.py"], depends_on=[1]),
    )
    recs = _merge_recs(assess_granularity(plan, stage="create", evidence=_evidence()))
    assert len(recs) == 1
    rec = recs[0]
    # Finding still surfaced (prose names both steps) …
    assert "1 and 3" in rec.suggested_action
    # … but carries NO dispatchable directive, so it can't reach merge_bridge.
    assert "→ merge steps" not in rec.suggested_action
    assert review.parse_merge_action(rec) is None


def test_merge_directive_does_not_change_rec_id() -> None:
    plan = _plan(
        Step(id=1, title="Add part one", files=["plan_tool/auth.py"]),
        Step(id=2, title="Add part two", files=["plan_tool/auth.py"], depends_on=[1]),
    )
    rec = _merge_recs(assess_granularity(plan, stage="create", evidence=_evidence()))[0]
    expected = review._make_rec_id(
        1, GRANULARITY_MERGE_SOURCE, "merge:identical-files:1+2"
    )
    assert rec.id == expected


# --- guarantees ------------------------------------------------------------


def test_deterministic_path_never_calls_invoker() -> None:
    def _exploding_invoker(prompt: str) -> tuple[int, str]:
        raise AssertionError("invoker must not be called on the deterministic path")

    plan = _plan(
        Step(id=1, title="Refactor parser to add validation", files=["plan_tool/parser.py"])
    )
    recs = assess_granularity(
        plan, stage="detail", evidence=_evidence(), invoker=_exploding_invoker
    )
    assert _split_recs(recs)  # findings still returned


def test_rec_shape_and_sources() -> None:
    plan = _plan(
        Step(id=1, title="Refactor parser to add validation", files=["plan_tool/parser.py"]),
        Step(id=2, title="Add part", files=["plan_tool/parser.py"], depends_on=[1]),
    )
    recs = assess_granularity(plan, stage="create", evidence=_evidence())
    assert recs
    for rec in recs:
        assert rec.source in (GRANULARITY_SPLIT_SOURCE, GRANULARITY_MERGE_SOURCE)
        assert rec.severity == "info"
        # ids are minted via _make_rec_id → "step{N}-{source}-{hash}".
        assert rec.id.startswith(f"step{rec.step_id}-{rec.source}-")
        assert rec.confidence == "limited"
        assert review.is_apply_eligible(rec) is False
        # Both sources route to a non-apply triage message. The split source
        # gets the specific plan-tool split remedy (escalate plan step 2);
        # merge gets the producer-neutral merge/re-ground advisory shared with
        # reconcile's code-grounded re-ground finding.
        reason = review.triage_reason(rec)
        if rec.source == GRANULARITY_SPLIT_SOURCE:
            assert "plan-tool split" in reason
        else:
            assert "merge/re-ground advisory" in reason


def test_split_predicate_constants_pin_existing_values() -> None:
    assert SPLIT_PREDICATE_MIXED_VERBS == "mixed-verbs"
    assert SPLIT_PREDICATE_CONJOINED_CLAUSES == "two-clauses"
    assert SPLIT_PREDICATE_UNRELATED_AREAS == "multi-area"
    assert SPLIT_PREDICATE_MIXED_STEP == "mixed-step"
    assert DETERMINISTIC_SPLIT_PREDICATE_KEYS == {
        "mixed-verbs",
        "two-clauses",
        "multi-area",
    }
    assert SPLIT_PREDICATE_KEYS == {
        "mixed-verbs",
        "two-clauses",
        "multi-area",
        "mixed-step",
    }


def test_split_predicate_key_recovers_mixed_verbs() -> None:
    rec = _single_split_rec(
        Step(id=1, title="Refactor parser to add validation",
             files=["plan_tool/parser.py"])
    )
    assert split_predicate_key(rec) == SPLIT_PREDICATE_MIXED_VERBS


def test_split_predicate_key_recovers_conjoined_clauses() -> None:
    rec = _single_split_rec(
        Step(id=1, title="Add login and wire handler", files=["plan_tool/auth.py"])
    )
    assert split_predicate_key(rec) == SPLIT_PREDICATE_CONJOINED_CLAUSES


def test_split_predicate_key_recovers_unrelated_areas() -> None:
    rec = _single_split_rec(
        Step(id=1, title="Wire feature",
             files=["plan_tool/auth.py", "amplify/handler.py"])
    )
    assert split_predicate_key(rec) == SPLIT_PREDICATE_UNRELATED_AREAS


def test_split_predicate_key_maps_prose_mixed_step() -> None:
    rec = parse_mixed_step_findings(
        _STRUCTURAL_BLOCK_MIXED, _refactor_step(), "orch"
    )[0]
    assert split_predicate_key(rec) == SPLIT_PREDICATE_MIXED_STEP


def test_split_predicate_key_returns_none_for_non_split() -> None:
    rec = _merge_recs(
        assess_granularity(
            _plan(
                Step(id=1, title="Add part one", files=["plan_tool/auth.py"]),
                Step(id=2, title="Add part two", files=["plan_tool/auth.py"],
                     depends_on=[1]),
            ),
            stage="create",
            evidence=_evidence(),
        )
    )[0]
    assert split_predicate_key(rec) is None


def test_ids_are_stable() -> None:
    step = Step(id=1, title="Refactor parser to add validation", files=["plan_tool/parser.py"])
    plan = _plan(step)
    first = assess_granularity(plan, stage="create", evidence=_evidence())
    second = assess_granularity(plan, stage="create", evidence=_evidence())
    assert [r.id for r in first] == [r.id for r in second]


# --- prose MIXED-STEP kernel (granularity-split) ---------------------------


_STRUCTURAL_BLOCK_MIXED = (
    "Review of the detail body.\n\n"
    "## Findings\n\n"
    "_(none)_\n\n"
    "## Structural findings\n\n"
    "- MIXED-STEP: the `Promise.all` parallelization preserves behavior "
    "but the auth removal changes the failure mode from throw to "
    "fail-soft; these must be two steps\n"
)


def _refactor_step() -> Step:
    return Step(
        id=1,
        title="Wire up renderer",
        files=["plan_tool/renderer.py"],
        change_type=ChangeType.REFACTOR,
    )


def test_mixed_block_yields_split_finding() -> None:
    recs = parse_mixed_step_findings(_STRUCTURAL_BLOCK_MIXED, _refactor_step(), "orch")
    assert len(recs) == 1
    rec = recs[0]
    assert rec.source == "granularity-split"
    assert rec.severity == "medium"
    assert rec.confidence == "limited"
    assert rec.step_id == 1
    assert "fail-soft" in rec.body


def test_split_finding_is_not_apply_eligible() -> None:
    rec = parse_mixed_step_findings(_STRUCTURAL_BLOCK_MIXED, _refactor_step(), "orch")[0]
    assert review.is_apply_eligible(rec) is False
    reason = review.triage_reason(rec).lower()
    # granularity-split routes to the specific split remedy (escalate plan
    # step 2 replaced the generic "structural diagnostic / not auto-fixable" text).
    assert "plan-tool split" in reason
    assert "not an apply edit" in reason


def test_no_structural_block_returns_empty() -> None:
    raw = "## Findings\n\n- MEDIUM: omits citations\n"
    assert parse_mixed_step_findings(raw, _refactor_step(), "orch") == []


def test_non_code_step_drops_bullet() -> None:
    step = Step(
        id=1,
        title="Write docs",
        files=["docs/x.md"],
        change_type=ChangeType.NON_CODE,
    )
    assert parse_mixed_step_findings(_STRUCTURAL_BLOCK_MIXED, step, "orch") == []


def test_empty_bullet_skipped() -> None:
    raw = "## Structural findings\n\n- MIXED-STEP:   \n"
    assert parse_mixed_step_findings(raw, _refactor_step(), "orch") == []


def test_bold_token_and_heading_casing_tolerated() -> None:
    raw = (
        "## Structural Findings\n\n"
        "- **MIXED-STEP**: refactor extract bundled with a new flag\n"
    )
    recs = parse_mixed_step_findings(raw, _refactor_step(), "orch")
    assert len(recs) == 1
    assert recs[0].source == "granularity-split"


def test_detail_stage_delegates_to_kernel() -> None:
    # Single REFACTOR step, single area, no conjunction title: no deterministic
    # split/merge predicate trips, so every returned rec is the kernel's.
    plan = _plan(_refactor_step())
    recs = assess_granularity(
        plan,
        stage="detail",
        evidence=GranularityEvidence(detail_bodies={1: _STRUCTURAL_BLOCK_MIXED}),
    )
    kernel = [r for r in recs if r.severity == "medium"]
    assert len(kernel) == 1
    assert kernel[0].source == "granularity-split"
    assert "fail-soft" in kernel[0].body  # falsifiable against a no-op delegation


def test_detail_stage_never_calls_invoker() -> None:
    def _exploding_invoker(prompt: str) -> tuple[int, str]:
        raise AssertionError("invoker must not be called on the detail stage")

    plan = _plan(_refactor_step())
    recs = assess_granularity(
        plan,
        stage="detail",
        evidence=GranularityEvidence(detail_bodies={1: _STRUCTURAL_BLOCK_MIXED}),
        invoker=_exploding_invoker,
    )
    assert any(r.source == "granularity-split" and r.severity == "medium" for r in recs)


def test_import_purity() -> None:
    src = Path("plan_tool/granularity.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    allowed = {"plan_tool.schema", "plan_tool.review"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("plan_tool"):
            assert node.module in allowed, f"disallowed plan_tool import: {node.module}"
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("plan_tool"), (
                    f"disallowed plan_tool import: {alias.name}"
                )
