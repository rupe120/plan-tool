# Step 1 — Add `review.is_structural(rec)` classification predicate seeded with `detail-purity`

## Summary

- **Adds one predicate** to `plan_tool/review.py`: `is_structural(rec)` returns `True` when a finding's only correct fix is a structural plan edit (split a step), `False` otherwise. It is seeded with a single source, `detail-purity`, via a new `STRUCTURAL_SOURCES` frozenset.
- **Mirrors the existing `is_apply_eligible` / `APPLY_ELIGIBLE_SOURCES` shape** and sits directly beside it, so the two membership predicates read as a pair.
- **Single-sources the structural test** by rewriting `triage_reason`'s lone `rec.source == "detail-purity"` guard to call `is_structural(rec)` — behavior-preserving, since `STRUCTURAL_SOURCES` has exactly one member today.
- **Forward contract only:** no caller routes structural findings to escalation yet. `triage_reason` is the predicate's only consumer in this step; steps 3–5 (`launcher.escalate_to_split`, the create/detail convergence loops, `cli/review_actions.py`) read `is_structural` to drive the new behavior.
- **Renders the create path's split recommendation** by adding a `structural-split` branch to `triage_reason` (pointing at `plan-tool split`) and surfacing the rec's `body`/`suggested_action` in `emit_triage_summary`, so step 5's `open_deferred`-appended recommendation carries real split content instead of misdirecting to `plan-tool detail`.
- **On green:** `is_structural` is importable from `plan_tool.review`, classifies `detail-purity` as structural and everything else as not, and `detail-purity` stays out of `APPLY_ELIGIBLE_SOURCES`.

## Table of Contents

- [Why](#why) — what's missing today and why the predicate comes first
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files this step touches
- [Implementation](#implementation) — the constant, the predicate, and the one consumer rewrite
- [Tests](#tests) — the cases added to `TestApplyTriage`
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — pytest docs for the new unit tests
- [Deferred](#deferred) — what later steps own (escalation, rename, new verdict)

## Why

A finding whose only correct fix is "split this step into two" is recognized but dead-ended. The purity self-check tags such a step `detail-purity` (`plan_tool/detail.py: _parse_purity_findings`), the source is deliberately absent from `APPLY_ELIGIBLE_SOURCES`, and the convergence loop skips it. The escalation bridge in steps 3–5 needs a **single, named way to ask "is this finding structural?"** so it can route the same finding to the split engine instead of skipping. Today that test exists only as a bare string compare buried in `triage_reason`. This step lifts it into a reusable predicate so every later caller asks one question, in one place, against one source set — without yet changing any routing behavior.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/review.py` — add the `STRUCTURAL_SOURCES` frozenset and the `is_structural(rec)` predicate beside `APPLY_ELIGIBLE_SOURCES` / `is_apply_eligible`; rewrite the `rec.source == "detail-purity"` guard in `triage_reason` to call `is_structural(rec)`; add a `structural-split` branch to `triage_reason` and render the rec's `body`/`suggested_action` in `emit_triage_summary`.
  - `tests/test_review.py` — add unit cases to the existing `TestApplyTriage` class.

## Implementation

### `plan_tool/review.py`

**Add the source set + predicate immediately after `is_apply_eligible`** (after the `APPLY_ELIGIBLE_SOURCES` frozenset and its `is_apply_eligible` function), before the `AUDIT_FIX_SOURCES` block. Mirror the existing pattern exactly — a module-level frozenset plus a one-line membership predicate:

- `STRUCTURAL_SOURCES: frozenset[str] = frozenset({"detail-purity"})` — the finding sources whose only correct remedy is a structural plan edit (split a step into a refactor-then-feature pair), not a prose edit `apply_finding` can make. Seeded with the one source that exists today.
- `def is_structural(rec: Recommendation) -> bool:` — returns `rec.source in STRUCTURAL_SOURCES`.

Docstring (keep it terse per the project's concise-docs rule): one line stating it's `True` for findings whose fix is a structural split, and a note that the set is currently just `detail-purity` and that membership in `STRUCTURAL_SOURCES` is, by invariant, **disjoint from** `APPLY_ELIGIBLE_SOURCES` (a finding is either prose-fixable or structural, never both).

**Design decision — separate set, not a subset relationship.** `STRUCTURAL_SOURCES` is its own frozenset, not derived from `APPLY_ELIGIBLE_SOURCES`. Structural sources are a *named subset of the apply-ineligible sources* — every structural source is also not apply-eligible, but not every apply-ineligible source is structural (e.g. `file-check`, `deps`, `path-style`, `test-strategy` are diagnostics with no split remedy). Keeping the two sets independent makes "structural" mean specifically "split-able," which is exactly what the escalation bridge keys on. A test pins the disjointness invariant so a future edit can't accidentally list a source in both.

**Rewrite the one consumer in `triage_reason`.** The function currently opens with:

- `if rec.source == "detail-purity":` → returns the split-recommend message.

Change that guard to `if is_structural(rec):`. This is **behavior-preserving** — `is_structural(rec)` is exactly `rec.source == "detail-purity"` while `STRUCTURAL_SOURCES` has one member — and it single-sources the literal so review.py no longer compares against the bare `"detail-purity"` string in two places. Keep the returned message text unchanged (it accurately describes the only current member; later steps revisit the wording if/when more sources join). Do **not** remove the dedicated branch — it must still fire before the generic `not is_apply_eligible(rec)` fallback so a `detail-purity` finding keeps its specific "split it into type-pure steps" reason rather than the generic "structural diagnostic" text.

**Add a `structural-split` branch to `triage_reason` and render it in `emit_triage_summary`.** Step 5's create wiring appends the bridge's `structural-split` `Recommendation` (source `"structural-split"`, carrying the proposed refactor/feature titles + rationale in `rec.body` and the `plan-tool split --into …` command in `rec.suggested_action`, both authored in step 3 — step 3 recovers titles and rationale from a single proposal, either by running the proposal itself and parsing the raw response via `_parse_steps_json(..., rationales_out=...)` rather than calling `_propose_step_split`, or by extending `_propose_step_split` to surface its `rationales_out`/raw, never via a second divergent Claude call) to the `open_deferred` list that `emit_triage_summary` consumes. Two review.py edits make that recommendation legible instead of misdirecting:

- **`triage_reason`:** add a dedicated `elif rec.source == "structural-split":` branch (after the `is_structural` branch, before the generic `not is_apply_eligible(rec)` fallback) returning a message that points the operator at `plan-tool split` (e.g. "the more-correct plan splits this step; run `plan-tool split` to apply"). Without this branch a `structural-split` rec falls through to the generic "structural diagnostic — … run `plan-tool detail`" text, misdirecting the operator to the wrong command.
- **`emit_triage_summary`:** for a `structural-split` rec, render `rec.body` (proposed titles + rationale) and `rec.suggested_action` (the `plan-tool split --into …` command) beneath the existing `  - {rec.id}: {rec.title} [{triage_reason(rec)}]` line, so the surfaced recommendation actually carries the split content the create acceptance criterion promises. Non-`structural-split` recs keep the existing one-line rendering.

This rendering lands in review.py here because step 5's create path cannot edit review.py (outside its declared `files:`) and both `triage_reason` and `emit_triage_summary` live in review.py; it is forward-safe-but-inert until step 3 first emits a `structural-split` rec. Note `structural-split` is a *recommendation output* source, distinct from the `detail-purity` *finding input* source — it is **not** added to `STRUCTURAL_SOURCES`/`is_structural`.

**Foundational logic and its other call sites.** The core rule this step adds is the classification "this finding's fix is a split." Grep confirms the only place that rule is currently encoded is `triage_reason`'s `detail-purity` literal (`plan_tool/review.py`) and the emitter `_parse_purity_findings` (`plan_tool/detail.py`, out of scope — it produces the source string). After this step, the *classification* lives only in `STRUCTURAL_SOURCES` / `is_structural`. The future consumers that will read the predicate — `plan_tool/launcher.py: escalate_to_split`, the create/detail convergence loops, and `plan_tool/cli/review_actions.py` — are added in steps 3–5 and are **out of scope here**; this step ships the predicate with no escalation wiring (see Deferred).

**Do not** touch `APPLY_ELIGIBLE_SOURCES`, `is_apply_eligible`, the emitter in `plan_tool/detail.py`, or `plan_tool/__init__.py`. `is_apply_eligible` is imported in tests via `from plan_tool.review import ...`, never from the package surface, so no re-export is needed; follow the same convention for `is_structural`.

## Tests

All cases go in the existing `TestApplyTriage` class in `tests/test_review.py`, reusing its `_rec_src(*, rec_id, source, severity="high")` helper. The class already imports `is_apply_eligible` / `triage_reason` body-locally per its convention.

- `test_is_structural_by_source` — `is_structural` returns `True` for a `detail-purity` rec; returns `False` for a sample across the other source families (`claude`, `body-completeness`, `file-check`, `deps`, `heuristic`, `test-strategy`).
- `test_detail_purity_stays_apply_ineligible` — for a `detail-purity` rec, `is_apply_eligible(rec) is False` **and** `"detail-purity" not in APPLY_ELIGIBLE_SOURCES`. Pins the plan invariant that the source remains skip-not-apply.
- `test_structural_sources_disjoint_from_apply_eligible` — `STRUCTURAL_SOURCES & APPLY_ELIGIBLE_SOURCES == frozenset()`. Guards the "a finding is never both structural and prose-fixable" invariant.
- `test_triage_reason_uses_is_structural` — `triage_reason` for a `detail-purity` rec still contains `"split"` (the dedicated message), proving the predicate-driven guard preserves the prior behavior and the branch still fires before the generic fallback.
- `test_triage_reason_structural_split_points_to_split` — `triage_reason` for a `structural-split` rec names `plan-tool split` and does **not** misdirect to `plan-tool detail`.
- `test_emit_triage_summary_renders_structural_split_content` — `emit_triage_summary` output for a `structural-split` rec includes its `body` (proposed titles + rationale) and `suggested_action` (`plan-tool split --into …`), not just its title line.

### Test-creation order (feature step)

This is a **feature** step. Write the four unit tests above alongside the `review.py` edit. Green-before-done gate: all four must pass (`uv run pytest tests/test_review.py::TestApplyTriage -q`) and the full `tests/test_review.py` suite plus `tests/test_detail.py` (which already asserts `detail-purity` recs are apply-ineligible and that `triage_reason` mentions "split") must stay green before this step is considered finished.

## Acceptance criteria

- `from plan_tool.review import is_structural` imports successfully.
- `is_structural(rec)` returns `True` when `rec.source == "detail-purity"` and `False` for every other source.
- `STRUCTURAL_SOURCES == frozenset({"detail-purity"})`.
- `"detail-purity" not in APPLY_ELIGIBLE_SOURCES` (unchanged) and `is_apply_eligible` returns `False` for a `detail-purity` rec.
- `STRUCTURAL_SOURCES` and `APPLY_ELIGIBLE_SOURCES` share no members.
- `triage_reason` for a `detail-purity` rec still returns a message containing `"split"` (behavior preserved through the rewritten guard).
- `triage_reason` for a `structural-split` rec returns a message naming `plan-tool split` (not `plan-tool detail`).
- `emit_triage_summary` renders a `structural-split` rec's `body` and `suggested_action`, not just its `{rec.id}: {rec.title}` line.
- `tests/test_review.py` and `tests/test_detail.py` pass.

## References

- [How to mark test functions with attributes — pytest](https://docs.pytest.org/en/stable/how-to/mark.html) — `@pytest.mark` usage and selecting marked tests, for adding the new unit cases without disturbing the existing markers.
- [How to use fixtures — pytest](https://docs.pytest.org/en/stable/how-to/fixtures.html) — `tmp_path` and helper-method patterns; here the cases reuse `TestApplyTriage._rec_src` rather than a fixture, but this documents the conventions the file follows.

## Deferred

- **`escalate_to_split` and any escalation routing** — steps 3–4. This step adds the predicate only; no caller turns a structural finding into a split here.
- **`BLOCKED-STRUCTURAL` verdict bucket** (`parse_apply_verdict` / `ApplyFindingResult`, the `apply-finding` prompt) — step 2. The other half of the escalation set lives in `launcher.py`, not in `is_structural`.
- **Convergence-loop and `cli/review_actions.py` consumption** of `is_structural` — steps 4 and 5.
- **Renaming `detail-purity` → `granularity-split`** across emitter and classifier — explicitly postponed by the plan's Deferred section to avoid churning the classification surface mid-bridge; `STRUCTURAL_SOURCES` holds the current literal and is the single place a later rename edits.
