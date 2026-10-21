> **Auto-archived**: this plan was swept on 2026-07-09 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Elevate `suppression-shape` to `medium` and route it onto the blocking-capable bucket

## Summary

Bump `detect_suppression_shape`'s severity from `info` to `medium` in `plan_tool/review.py`, and in `plan_tool/cli/completeness_phases.py`'s `_run_deterministic_checks` split its findings out of the advisory `smell_recs` bucket into the new gate-read `self_consistency_recs` bucket (the field step 1 added and wired). The one design decision: the elevation is inert on its own — a `medium` finding that still rides `smell_recs` can never block because the gate never reads that bucket, so the **move** is what makes it blocking-capable. On green, a plan whose step suppresses an existing audit gate produces a `medium` `suppression-shape` finding that renders under `### Self-consistency` and flips the exit code under `--fail-on-findings`, while `smell_recs` stays structurally non-blocking. No gate, renderer, or JSON-shape edits are needed here — step 1 already made `self_consistency_recs` gate and render.

## Table of Contents

- [Why](#why) — why the elevation is inert without the move
- [Input](#input) — the step-1 bucket this step feeds
- [Files (creates vs edits)](#files-creates-vs-edits) — the three source files and two test files
- [Implementation](#implementation) — the severity bump, the partition, and the stale-framing fixes
- [Tests](#tests) — detector severity, routing, and blocking-gate cases
- [Acceptance criteria](#acceptance-criteria) — observable checks
- [References](#references) — the internal machinery this step reuses
- [Deferred](#deferred) — the orphaned-deliverable producer and other steps' work

## Why

`detect_suppression_shape` (`plan_tool/review.py`) already fires exactly when a step's own deliverable suppresses, downgrades, or bypasses an existing audit gate — the brittle shape that let the #95 `prompt-budget-advisory` plan ship a silenced double-warn. But it emits at `severity="info"` and routes through `collect_smell_findings` onto `_DeterministicReport.smell_recs`, the one bucket `_completeness_has_blocking_findings` never reads. So the finding surfaces but can never block, no matter its severity. Step 1 added the `self_consistency_recs` bucket that the gate and both renderers read at `medium`+. This step makes `suppression-shape` the bucket's first producer: bumping severity alone does nothing while the rec still rides `smell_recs`, so the elevation and the move must land together.

## Input

- **`_DeterministicReport.self_consistency_recs`** — produced by step 1 (`plan_tool/cli/completeness_phases.py`). Step 1 declares the field, threads it into `_completeness_has_blocking_findings` (gate) with a `medium`+ blocking branch, renders it in `_render_grouped_report` (a `### Self-consistency` section) and `_render_completeness_json` (a `checks["self_consistency"]` group), and includes it in the grouped report's `has_any` all-clear check. This step only **populates** that field; it does not re-wire the gate or the renderers. Reference step 1's outcome, not its mechanism — if the field or gate branch changed name at implementation time, use whatever step 1 actually landed.

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**

- `plan_tool/review.py`
  - In `detect_suppression_shape`, change the emitted `severity="info"` to `severity="medium"`.
  - Update `detect_suppression_shape`'s docstring line that states `severity="info"` to say `medium`.
  - Reword the `--- Advisory smell layer …` module comment (the block above `_FEATURE_ID_RE` that claims "Every detector here returns `info`") so it no longer implies `suppression-shape` is `info`/advisory-only. Keep the true parts: `suppression-shape` stays out of `APPLY_ELIGIBLE_SOURCES` and is still **not** wired into `collect_deterministic_findings`.
  - Optional: add a module constant `SUPPRESSION_SHAPE_SOURCE = "suppression-shape"` so the detector and the completeness-side partition key on one symbol instead of a bare string in two files.
- `plan_tool/cli/completeness_phases.py`
  - In `_run_deterministic_checks`, after `smell_recs` is fully assembled (`collect_smell_findings` + `granularity_recs` + the optional `_collect_purity_split_findings`), partition `suppression-shape` recs out of `smell_recs` into a `self_consistency_recs` local, and pass `self_consistency_recs=…` into the `_DeterministicReport(...)` return.
  - Fix the stale framing that named `suppression-shape` as a smell: the `### Smells (advisory)` block's descriptive line in `_render_grouped_report` ("brittle feature refs, suppression-shaped or self-referential steps, …") and the `"smells"` group comment in `_render_completeness_json` ("`feature-ref` / `suppression-shape` / `self-referential`"). Drop the `suppression-shape` mention from both since it no longer rides `smell_recs`.
- `plan_tool/cli/inspect.py`
  - In `cmd_validate`, correct the inline comment (~`inspect.py:462`) that calls the smell findings "info-severity and dismissible": `suppression-shape` now emits `medium`, so drop the false severity claim while keeping the true one — `validate` has no gate, so these findings still never touch the exit code (the only rc flip is the `INVALID:` arm). Comment-only edit; no behavior change.
- `tests/test_review.py`
  - Update `TestSuppressionShape`'s severity assertions to `medium`; add a routing/severity case as needed.
- `tests/cli/test_completeness_cmd.py`
  - Add a routing test (suppression lands in `self_consistency_recs`, not `smell_recs`) and a blocking-gate case; keep the "smells never gate" tests green.

## Implementation

**Foundational logic:** one detector's finding moves from a non-blocking advisory bucket to a blocking-capable bucket at `medium`. The behavior that changes is *which bucket* the finding lands in and *at what severity*; nothing about *when it trips* changes.

- **Bump severity in the detector, not at the call site.** In `plan_tool/review.py`'s `detect_suppression_shape`, set `severity="medium"` on the emitted `Recommendation`. This single-sources the severity for every caller (the completeness battery and `plan_tool/cli/inspect.py`'s `cmd_validate` — the `plan-tool validate` command — which surfaces the same detector via `collect_smell_findings`). `validate` is a display surface with no gate, so showing the finding as `medium` there is correct and needs no behavior change — but its inline comment claiming the smell findings are "info-severity" goes stale under the bump and must be corrected (comment-only; see the Files list). The alternative — bumping severity only inside `_run_deterministic_checks` — was rejected: it would split the detector's contract across two files and leave `validate` showing a stale `info`.

- **Partition in the completeness battery, don't remove the detector from `collect_smell_findings`.** In `_run_deterministic_checks` (`plan_tool/cli/completeness_phases.py`), after the `smell_recs` local is fully built (including the `granularity_recs` fold and the optional `run_purity` `_collect_purity_split_findings` fold), split it:
  - one way: `self_consistency_recs = [r for r in smell_recs if r.source == "suppression-shape"]` and rebind `smell_recs = [r for r in smell_recs if r.source != "suppression-shape"]` (use the `SUPPRESSION_SHAPE_SOURCE` constant if you add it).
  - Then pass `self_consistency_recs=self_consistency_recs` into the `_DeterministicReport(...)` return alongside `smell_recs=smell_recs`.
  - **Why partition instead of pulling `detect_suppression_shape` out of `collect_smell_findings`:** `collect_smell_findings` is also called by `plan_tool/cli/inspect.py:cmd_validate` (the `plan-tool validate` command). Removing the detector there would silently drop `suppression-shape` from the `validate` surface. Partitioning at the completeness battery keeps `validate`'s behavior unchanged — its only edit here is the comment-only correction — and confines the *routing* change to `review.py` + `completeness_phases.py`.

- **Source alone is a safe key here — no severity filter needed.** `suppression-shape` has exactly one producer (`detect_suppression_shape`), unlike `granularity-split`, which two producers emit at different severities into `smell_recs` (the info deterministic detector and the medium Claude purity pass) and therefore needs a `source AND severity` filter. Don't copy that two-key filter here; keying on `source == "suppression-shape"` is correct and complete.

- **Do not touch the gate or the renderers.** `_completeness_has_blocking_findings` lives in `plan_tool/cli/completeness_cmd.py` (step 1's file, out of this step's `files:` list) and already reads `self_consistency_recs` at `medium`+ via `convergence.is_blocking`. Because the elevated finding is `medium`, it blocks through that existing branch with no edit here. The renderers already read the bucket generically and include it in `has_any` (step 1). This step's only render-side work is deleting the two stale text mentions of `suppression-shape` from the `smell_recs` descriptions.

- **Keep `suppression-shape` out of the auto-apply path.** The finding routes to a gate/report bucket, never to `apply_finding`. Leave `suppression-shape` absent from `APPLY_ELIGIBLE_SOURCES` and out of `collect_deterministic_findings` (the `--iterate` broadcast fan-out) and out of the `_structural` next-steps router — a suppression finding has no auto-fix; the correct remedy is human review of whether the gate is wrong. This matches step 1's rule that `self_consistency_recs` stays out of the `_structural` router.

- **Ordering gotcha:** the partition must run *after* the `run_purity` fold, or a purity `granularity-split` rec could be swept incorrectly — but since the key is `source == "suppression-shape"`, purity recs (`granularity-split`) are untouched regardless. Placing the partition right before the `_DeterministicReport(...)` return keeps it unambiguous.

## Tests

### Test-creation order (feature step)

This is a **feature** step. Add the tests below **with** the implementation; every new test must be green before the step is done.

`tests/test_review.py` (next to `TestSuppressionShape`):

- `test_title_states_suppression_trips` (existing) — update its `severity == "info"` assertion to `medium`.
- `test_suppression_severity_is_medium` — a tripping plan yields a rec with `severity == "medium"` and `source == "suppression-shape"`.
- Confirm the non-trip cases stay green unchanged: `test_self_describing_detector_does_not_trip`, `test_class_of_units_reasoning_does_not_trip`, `test_real_detail_bundle_self_flags_nothing` (the meta-case — the detector's own describing prose still does not trip).

`tests/cli/test_completeness_cmd.py` (extend `TestRunDeterministicChecks`, `TestCompletenessHasBlockingFindings`, and the render/JSON groups):

- `test_suppression_routes_to_self_consistency_not_smells` — driving `_run_deterministic_checks` (or `main(["completeness-audit", …])`) on a suppression-shaped plan, the `suppression-shape` rec appears in `det.self_consistency_recs` and is **absent** from `det.smell_recs`.
- `test_self_consistency_suppression_blocks` — a `_DeterministicReport` with a `medium` `suppression-shape` rec in `self_consistency_recs` makes `_completeness_has_blocking_findings` (step 1's gate) return True, and `--fail-on-findings` yields rc 1.
- `test_smell_only_plan_not_reported_as_no_issues` (existing, ~`_det_with_smells([_rec("info", source="suppression-shape")])`) — update the fixture source to a still-advisory smell (e.g. `self-referential`) so it no longer implies `suppression-shape` rides `smell_recs`; keep the "smells section shows / all-clear hidden" assertion.
- Keep green: `test_smells_do_not_affect_has_blocking` (source `self-referential`) and the other "smells never gate" cases — `smell_recs` stays structurally non-blocking.

## Acceptance criteria

- `detect_suppression_shape` in `plan_tool/review.py` emits `severity="medium"` (was `info`); `source` stays `"suppression-shape"`.
- Running the deterministic battery on a suppression-shaped plan places the finding in `_DeterministicReport.self_consistency_recs` and **not** in `smell_recs`.
- A `medium` `suppression-shape` finding in `self_consistency_recs` makes `_completeness_has_blocking_findings` return True and flips the process rc to 1 under `--fail-on-findings`; without the flag the audit still exits 0.
- The `### Self-consistency` report section and `checks["self_consistency"]` JSON group show the elevated finding (both wired by step 1); the `### Smells (advisory)` description and the `"smells"` JSON-group comment no longer mention `suppression-shape`.
- `cmd_validate`'s inline comment in `plan_tool/cli/inspect.py` no longer calls the smell findings "info-severity"; it still states `validate` never touches the exit code. `validate`'s behavior is unchanged.
- The meta-case (the detector's own describing prose) still does not trip, and a plan that legitimately reasons over / excuses a suppression still passes.
- The "smells never gate" tests (`tests/cli/test_completeness_cmd.py`, e.g. `test_smells_do_not_affect_has_blocking`) stay green.
- `suppression-shape` remains absent from `APPLY_ELIGIBLE_SOURCES` and is not added to `collect_deterministic_findings` or the `_structural` next-steps router.

## References

- Step 1's detail (`docs/implementation-plans/plan-details/plan-self-consistency-gate/01-blocking-capable-self-consistency-recs.md`) — the `self_consistency_recs` contract this step feeds: the field, its `medium`+ gate branch in `_completeness_has_blocking_findings`, and the `### Self-consistency` / `checks["self_consistency"]` renderers. Reference its landed outcome, not its mechanism.
- `detect_suppression_shape` and `collect_smell_findings` (`plan_tool/review.py`) — the single detector whose `severity` this step bumps and the smell-collector it rides; also the seam that keeps `plan-tool validate` showing the finding after the completeness-side partition.
- The completeness report render/persist path (`_run_deterministic_checks`, `_render_grouped_report`, `_render_completeness_json` in `plan_tool/cli/completeness_phases.py`) — where the partition splits `suppression-shape` off `smell_recs` and where the two stale smell-description mentions live.

## Deferred

- **The `orphaned-deliverable` detector** — step 3 adds the second producer for `self_consistency_recs` (a step declaring a `creates:`/detail-introduced symbol no in-scope step consumes). Out of scope here; this step only seeds the bucket with `suppression-shape`.
- **The `claim-vs-delivery` advisory detector** — step 4 adds it on `smell_recs` (stays advisory), out of scope here.
- **The `self_consistency_recs` field, gate branch, and renderers** — owned by step 1; this step depends on them and only populates the field.
- **Changing `plan_tool/cli/inspect.py` behavior** — `cmd_validate` (the `plan-tool validate` command) keeps surfacing `suppression-shape` via `collect_smell_findings` (now at `medium`) and still never gates; the only in-scope inspect.py edit is the comment-only correction of its stale "info-severity" line (see Files). No `validate` behavior changes.
- **A first-party-gate vocabulary for `suppression-shape`** — not needed now; add only if a false-positive rate later demands it (per the plan's Deferred).
