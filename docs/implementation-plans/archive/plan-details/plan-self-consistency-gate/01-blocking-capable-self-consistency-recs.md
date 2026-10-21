> **Auto-archived**: this plan was swept on 2026-07-09 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Add a blocking-capable `self_consistency_recs` bucket to the deterministic report

## Summary

Add one new field, `self_consistency_recs`, to the frozen `_DeterministicReport` dataclass in `plan_tool/cli/completeness_phases.py`, and thread it end to end: into the blocking gate `_completeness_has_blocking_findings` (in `plan_tool/cli/completeness_cmd.py`) so a `medium`+ finding there flips `has_blocking_findings`, and into both renderers (`_render_grouped_report` and `_render_completeness_json`) so the findings show up in the markdown report and the `--json` payload. This step is **scaffolding only** — it builds and wires the bucket but adds **no producer**, so on every real audit the bucket is empty and behavior is unchanged. The producers (the elevated `suppression-shape` and the new `orphaned-deliverable` detector) land in steps 2 and 3, which only need to append to a bucket that already gates and renders. The key design decision: this is a **second gate-read bucket** distinct from `smell_recs` (which the gate never reads), so a self-consistency finding can block while advisory smells stay non-blocking.

## Table of Contents

- [Why](#why) — the gap this step opens the door to close
- [Files (creates vs edits)](#files-creates-vs-edits) — the three files touched
- [Implementation](#implementation) — the field, the gate branch, and both render surfaces
- [Tests](#tests) — new gate, render, and field-shape cases
- [Acceptance criteria](#acceptance-criteria) — observable checks
- [References](#references) — the stdlib/contract docs that matter here
- [Deferred](#deferred) — producers and consolidations left for later steps

## Why

`smell_recs` is the advisory bucket the blocking gate `_completeness_has_blocking_findings` never reads — its keyword params list every deterministic issue bucket **except** `smell_recs`, so a finding routed there can never block no matter its severity. Steps 2 and 3 need somewhere to put findings that *should* be able to block (`orphaned-deliverable`, elevated `suppression-shape`). Rather than teach the gate to read `smell_recs` (which would break the "smells never gate" contract two integration tests pin), this step adds a **new** bucket that the gate, the grouped report, and the JSON payload all read — the same shape `data_contract_recs` and `audit_recs` already have. Landing the empty, wired bucket first keeps the producer steps small and lets each ship independently.

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**

- `plan_tool/cli/completeness_phases.py`
  - Add `self_consistency_recs: list = field(default_factory=list)` to `_DeterministicReport`, alongside the other defaulted buckets (`smell_recs`, `data_contract_recs`).
  - Update the `_DeterministicReport` docstring so it names the new blocking-capable bucket and no longer implies `smell_recs` is the only advisory bucket.
  - In `_run_deterministic_checks`, build an empty `self_consistency_recs` local and pass it into the `_DeterministicReport(...)` constructor (the insertion point steps 2/3 append to).
  - In `_render_completeness_json`, add a new `checks["self_consistency"]` group, keyed on `source`/`severity` like the existing `smells` group.
  - In `_render_grouped_report`, render a new `### Self-consistency` section from `det.self_consistency_recs` and include it in the `has_any` "no issues detected" check.
- `plan_tool/cli/completeness_cmd.py`
  - Add a `self_consistency_recs=()` keyword param to `_completeness_has_blocking_findings` and a `medium`+ blocking branch.
  - Pass `self_consistency_recs=det.self_consistency_recs` at both gate call sites in `cmd_completeness` (the `--json` `has_blocking` computation and the `--fail-on-findings` gate).
- `tests/cli/test_completeness_cmd.py`
  - Add gate, render, and field-shape cases; extend the existing baselines/field-list assertions.

## Implementation

**Foundational logic:** a second gate-read bucket on `_DeterministicReport` whose findings block at `medium`+, mirroring `data_contract_recs`/`audit_recs`. The one behavior that changes is the gate predicate; everything else is threading.

- **Add the field to `_DeterministicReport`** (`plan_tool/cli/completeness_phases.py`). Declare `self_consistency_recs: list = field(default_factory=list)` among the defaulted fields, after the seven required issue lists. Keeping it defaulted is required — the test helpers `_empty_det()` and `_det_with_smells()` and any positional/partial constructor must stay valid, exactly the reason `smell_recs` was placed after the required buckets. Update the class docstring: it currently frames `smell_recs` as "the one bucket the blocking-gate check never reads"; add that `self_consistency_recs` is a bucket the gate *does* read at `medium`+. Also bump the docstring's "single-sourcing the **eight** issue lists" count to **nine** — adding `self_consistency_recs` makes nine, and the stale count must move with the field.

- **Build the empty local in `_run_deterministic_checks`.** Add `self_consistency_recs: list = []` near where `smell_recs` is assembled, and pass `self_consistency_recs=self_consistency_recs` into the `_DeterministicReport(...)` return. No detector runs in this step — steps 2 and 3 append their recs to this local. Leave a one-line comment marking it as the producers' insertion point so a later reader doesn't delete it as dead. Do **not** touch the `_det_total` deterministic-count tail: like smells, self-consistency findings must not inflate the well-formedness count (the count is an operator-facing number for the no-claude battery).

- **Add the gate branch** in `_completeness_has_blocking_findings` (`plan_tool/cli/completeness_cmd.py`). Add `self_consistency_recs=()` as a keyword-only param (the function is already `*`-only), and add a branch that returns `True` when any rec is `medium`+. Reuse `convergence.is_blocking` (already imported in this module) rather than re-inlining the `("medium", "high", "critical")` tuple the two sibling branches use — the plan calls for mirroring `is_blocking` / `BLOCKING_SEVERITIES`. Match the existing case-insensitive behavior (`is_blocking` already lowercases). Update the docstring to name the new bucket alongside data-contract drift. **Ordering doesn't matter** for correctness (the gate is a short-circuit OR), but keep the new branch beside the other severity-gated buckets for readability.

- **Wire both call sites** in `cmd_completeness`. Pass `self_consistency_recs=det.self_consistency_recs` in the `--json` `has_blocking = _completeness_has_blocking_findings(...)` call and in the `--fail-on-findings` `_completeness_has_blocking_findings(...)` guard. Both are the load-bearing wiring — the new param defaults to `()`, so forgetting a site silently makes the bucket never gate at that path.

- **JSON renderer** (`_render_completeness_json`). Add a `"self_consistency"` group to the `checks` dict, mirroring the `smells` group: one object per rec with `severity`, `source`, `id`, `title`, `body`. `_render_completeness_json` already takes `det`, so read `det.self_consistency_recs` directly — no new param. `has_blocking` is passed in precomputed by the orchestrator, so this renderer needs no gate logic; it just surfaces the findings.

- **Grouped markdown renderer** (`_render_grouped_report`). Add a `### Self-consistency` section, rendered only when `det.self_consistency_recs` is non-empty, using the same `- {severity.upper()}{tag}: {body}` line shape as the `### Data contract` and `### Smells (advisory)` sections (`tag` = `` `[{rec.anchor}]` `` when present). Add `det.self_consistency_recs` to the `has_any` expression so the "no completeness issues detected" line stays honest. Give the section a one-line blurb that says these are blocking-capable plan-internal consistency findings, to distinguish them from the advisory smells section directly above.

- **Next-steps guidance — keep minimal.** The `_structural` next-step pointer routes findings toward `reconcile-plan-walk` / `completeness-audit --iterate`, which auto-apply. Self-consistency findings are **not** auto-applied by the iterate loop (like smells, they never enter it), so do **not** fold `det.self_consistency_recs` into the `_structural` trigger in this step — that would point the operator at a fruitless auto-apply. Leave the next-steps block as is; a human-review note is enough. (This is latitude: if you add a bespoke "review the self-consistency finding(s) by eye" line, keep it out of the `_structural`/`--iterate` path.)

**Duplication note:** the `medium`+ predicate is inlined as a raw tuple in the existing `data_contract_recs` and `audit_recs` branches of `_completeness_has_blocking_findings`, while `convergence.is_blocking` / `BLOCKING_SEVERITIES` (`plan_tool/convergence.py`) is the single source. Use `is_blocking` for the new branch. Consolidating the two existing inlined tuples onto `is_blocking` is a behavior-preserving cleanup outside this step's job — see Deferred.

## Tests

All tests are pure — no invoker, no backend spawn. Add to `tests/cli/test_completeness_cmd.py`. Every new test must be green before this step is done.

In `TestCompletenessHasBlockingFindings` (add `self_consistency_recs=()` to the `_clear()` baseline first):

- `test_self_consistency_recs_block_at_medium_and_above` — a rec at `medium`/`high`/`critical` in `self_consistency_recs` makes the gate return `True`.
- `test_self_consistency_recs_below_medium_do_not_block` — `info`/`nit` recs in `self_consistency_recs` return `False`.
- `test_self_consistency_rec_severity_match_is_case_insensitive` — a `"MEDIUM"` rec blocks.
- `test_all_clear_stays_not_blocking_with_empty_self_consistency` — the all-clear baseline (now carrying `self_consistency_recs=()`) is still `False`.

In `TestRunDeterministicChecks`:

- Extend `test_returns_deterministic_report_type`'s field-list assertion to include `"self_consistency_recs"`.
- `test_run_deterministic_checks_yields_empty_self_consistency_bucket` — a clean plan's report has `self_consistency_recs == []` (no producer yet).

For the renderers (near the existing JSON/grouped-report tests):

- `test_render_json_includes_self_consistency_group` — a hand-built `det` carrying a `medium` self-consistency rec surfaces it under `checks["self_consistency"]` keyed on `severity`/`source`/`id`/`title`/`body`, and that rec does **not** appear under `checks["smells"]`.
- `test_render_json_self_consistency_empty_group_when_none` — an all-clear `det` renders an empty `checks["self_consistency"]` list.
- `test_grouped_report_renders_self_consistency_section` — a `det` with a self-consistency rec renders a `### Self-consistency` section containing the rec body; an all-clear `det` renders neither the section nor a false "no issues detected" mismatch.

Regression (must stay green, no edits needed): `test_smells_do_not_affect_has_blocking` and the `TestGranularitySmellNeverGates` integration case — `smell_recs` stays structurally non-blocking.

Optional helper: a `_det_with_self_consistency(recs)` factory mirroring `_det_with_smells` keeps the render tests terse; add it if it reads cleaner.

### Test-creation order (feature step)

This is a **feature** step. Add every test above **with** the implementation. Green-before-done gate: all new tests pass and the two named regression tests stay green before the step is considered finished.

## Acceptance criteria

- `_DeterministicReport` has a `self_consistency_recs` field that defaults to an empty list; `_empty_det()` and `_det_with_smells()` still construct without it.
- `_completeness_has_blocking_findings(**all_clear, self_consistency_recs=[medium_rec])` returns `True`; with an `info`/`nit` rec it returns `False`.
- Both `_completeness_has_blocking_findings` call sites in `cmd_completeness` pass `self_consistency_recs=det.self_consistency_recs`.
- `_render_completeness_json` output contains a `checks["self_consistency"]` group; a `medium` self-consistency rec appears there and not under `checks["smells"]`.
- `_render_grouped_report` emits a `### Self-consistency` section when `det.self_consistency_recs` is non-empty, and the "no completeness issues detected" line no longer prints when only a self-consistency rec is present.
- `_run_deterministic_checks` on a clean plan returns `self_consistency_recs == []` (empty until steps 2/3 add producers).
- `smell_recs` remains absent from `_completeness_has_blocking_findings`'s params; the "smells never gate" tests stay green.
- A completed audit still exits 0 absent `--fail-on-findings`; no Claude call is added.

## References

- `plan_tool/cli/completeness_phases.py` — the in-file `smell_recs`/`data_contract_recs` fields and the `_DeterministicReport` docstring convention, the exact sibling pattern (defaulted `field(default_factory=list)` after the required buckets) the new `self_consistency_recs` field mirrors.
- `plan_tool/convergence.py` — `BLOCKING_SEVERITIES` / `is_blocking`, the single-source `medium`+ predicate to reuse for the new gate branch (already imported in `completeness_cmd.py`).
- `DATA_CONTRACT.md` — the `Recommendation` shape (`source`/`severity`/`id`/`title`/`body`/`anchor`) that the JSON and grouped-report render code reads per rec.

## Deferred

- **The `orphaned-deliverable` and elevated `suppression-shape` producers** — steps 3 and 2 respectively append to `self_consistency_recs`; this step ships the empty, wired bucket only.
- **The advisory `claim-vs-delivery` detector** — step 4, and it rides `smell_recs`, not this bucket.
- **Consolidating the two inlined `("medium","high","critical")` tuples** in `_completeness_has_blocking_findings`'s `data_contract_recs`/`audit_recs` branches onto `is_blocking` — a behavior-preserving cleanup; leave the siblings as they are and use `is_blocking` only for the new branch.
- **Routing self-consistency findings into the `_structural` next-steps / auto-apply path** — these findings are report-and-gate only; no apply path exists, so no next-step wiring beyond a human-review note.
