> **Auto-archived**: this plan was swept on 2026-07-08 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Persist the medium mixed-step split finding to the completeness sidecar

## Summary

The completeness audit already renders the `medium` mixed-step `granularity-split` finding (step 1 folds it into the advisory `smell_recs` bucket), but that bucket only reaches the report markdown — it never lands in the saved sidecar's `recommendations` list. This step edits `plan_tool/cli/completeness_phases.py:_persist_and_present_report` to subset the incoming `smell_recs` down to just the `medium` `granularity-split` recs (the prose MIXED-STEP judgment) and add them to `sidecar_recs`, so `save_review` persists them alongside correctness/completeness/data-contract findings. It documents the new persisted producer in `DATA_CONTRACT.md`'s saved-review-sidecar section and guards that prose with a drift test. On green, a completeness audit of a plan with a mixed refactor+feature step writes a sidecar whose `recommendations` include the `medium` `granularity-split` rec (with `step_id` set), which steps 3–4 replay through the split bridge.

## Table of Contents

- [Why](#why) — the persistence gap this closes and why steps 3–4 need it
- [Input](#input) — the finding contract and the persistence tail this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — what this step touches
- [Implementation](#implementation) — how the medium split rec reaches `sidecar_recs`
- [Tests](#tests) — unit cases added with the implementation
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — the docs worth reading for this step
- [Deferred](#deferred) — what this step deliberately leaves out

## Why

Step 1 makes the completeness audit *produce* the `medium` mixed-step `granularity-split` finding, but it can only route it through `det.smell_recs` — the advisory bucket that `plan_tool/cli/completeness_cmd.py:cmd_completeness` passes verbatim as `smell_recs=det.smell_recs`. In `plan_tool/cli/completeness_phases.py:_persist_and_present_report`, `smell_recs` feeds only the report markdown (`smells=list(smell_recs)` into `build_report_md`); the persisted `sidecar_recs` is built from `correctness_recs + conceptual_recs + data_contract_recs` and never includes any smell. So today the finding shows in the on-screen "Smells (advisory)" section but is dropped from the saved `<ts>-completeness.json`. Steps 3–4 dispatch the finding to the shipped `escalate_to_split` bridge from the `completeness-apply` walk, and that walk replays the saved sidecar — it cannot act on a finding the sidecar never stored. This step makes the sidecar carry it, without touching `cmd_completeness` (out of scope): the subset happens at the one point where `sidecar_recs` is assembled.

## Input

- **Consumes step 1's finding on the `smell_recs` bucket.** Step 1 folds the `medium` `granularity-split` rec into `_DeterministicReport.smell_recs` (the same bucket the `info` deterministic granularity recs join). This step reads that bucket as it arrives on the `smell_recs=` parameter of `_persist_and_present_report`.
- **Keys on `source` + `severity` to isolate the mixed-step rec.** The prose MIXED-STEP producer (`plan_tool/granularity.py:parse_mixed_step_findings`) returns `source="granularity-split"` (the `GRANULARITY_SPLIT_SOURCE` constant), `severity="medium"`, and `step_id=step.id`. The deterministic detectors (`plan_tool/granularity.py:_split_rec`, `_merge_findings`) return `severity="info"` (the `_GRANULARITY_SEV` constant). Filtering on `source == GRANULARITY_SPLIT_SOURCE and severity == "medium"` selects exactly the mixed-step recs and leaves the `info` split recs, the `granularity-merge` recs, and the repo-structural smells advisory-only.
- **Feeds the existing persistence tail unchanged.** The saved sidecar's `recommendations` field is the persisted `Recommendation` list written by `plan_tool/review_persistence.py:save_review` (via `write_completeness_report`) and read back by `load_review`. This step adds entries to that list; it changes no field on `Recommendation` or `SavedReview` (see `DATA_CONTRACT.md`).

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/completeness_phases.py` — in `_persist_and_present_report`, subset `smell_recs` to the `medium` `granularity-split` recs and add them to `sidecar_recs` at the single point where that list is built.
  - `DATA_CONTRACT.md` — extend the "Saved review sidecar" section to note that completeness audits also persist the `medium` mixed-step `granularity-split` finding (with `step_id` set) for the split bridge.
  - `tests/cli/test_completeness_cmd.py` — add cases proving the `medium` split rec reaches the persisted `recommendations` while `info`/merge smells do not.
  - `tests/test_data_contract.py` — add a drift-guard case asserting the new sidecar prose exists.

## Implementation

- **Build a `medium`-split subset from `smell_recs`, add it to `sidecar_recs`.** In `plan_tool/cli/completeness_phases.py:_persist_and_present_report`, the `sidecar_recs` list is assembled once inside the `if not skip_sidecar_write:` branch as `list(correctness_recs) + list(conceptual_recs) + list(data_contract_recs)`. Compute a subset — one clear way: `[r for r in smell_recs if r.source == GRANULARITY_SPLIT_SOURCE and r.severity == "medium"]` — and append it so the full set is `correctness + conceptual + data_contract + mixed_split`. Appending at the end is the least disruptive slot: the persisted order does not drive the apply walk (that re-ranks via `_CONCEPTUAL_APPLY_SOURCE_RANK` in step 3), and appending keeps the existing correctness-first, data-contract-last order intact.
- **Do the subset at the single `sidecar_recs` assembly point, not before.** `sidecar_recs` is both persisted (`recommendations=sidecar_recs` in the `write_completeness_report` call) and handed to `_completeness_convergence_diagnosis(..., current_recs=sidecar_recs)`. Adding the mixed-split subset to the one `sidecar_recs` local keeps persistence and the convergence diagnosis reading one consistent finding set — the mixed-step recs will now count toward the current run's recurrence signal, which is correct since they are real persisted findings.
- **Import `GRANULARITY_SPLIT_SOURCE` body-locally.** Match the module's existing pattern: `_run_deterministic_checks` already imports `GRANULARITY_SPLIT_SOURCE` from `plan_tool.granularity` inside its body. `_persist_and_present_report` is a separate function, so add its own body-local import (or a module-level constant reference) rather than assuming the name is in scope. Do not hard-code the `"granularity-split"` string literal — use the constant so a rename can't silently break the filter.
- **Preserve the "never flips the exit code" invariant.** `granularity-split` must stay out of the blocking gate. This step edits only the persistence tail, so `_completeness_has_blocking_findings` (which reads the deterministic issue lists + `data_contract_recs` + `audit_recs`, never `smell_recs` and never the persisted `recommendations`) is untouched — the `medium` split rec persists but still cannot flip `--fail-on-findings`. Keep it that way; do not route the subset into the blocking gate.
- **Leave rendering and the `smell_recs` bucket alone.** The report markdown still renders every smell via `smells=list(smell_recs)` into `build_report_md`, so the mixed-step finding continues to show in the "Smells (advisory)" section (step 1's surface). This step only adds a persistence path; it must not remove the rec from `smell_recs` or the rendered report.
- **Rejected alternative — a new `_DeterministicReport` bucket.** One could add a dedicated `mixed_split_recs` bucket to `_DeterministicReport` in `_run_deterministic_checks` and thread it through `cmd_completeness`. That would touch `plan_tool/cli/completeness_cmd.py`, which is out of this step's file scope, for no gain: subsetting `smell_recs` inside `_persist_and_present_report` reaches the same result with fewer files touched. Prefer the subset.

## Tests

Add unit cases to `tests/cli/test_completeness_cmd.py` alongside the existing `_persist_and_present_report` cases (`test_persist_passes_union_and_fingerprints`, `test_persist_passes_data_contract_recommendations`), reusing the `write_completeness_report` spy pattern that captures `kwargs["recommendations"]`. Construct the mixed-step rec with `source="granularity-split"`, `severity="medium"`, `step_id=2` (the `_rec` helper takes no `step_id`, so build a `Recommendation` directly or extend `_rec` with an optional `step_id`).

- `test_persist_folds_medium_granularity_split_into_sidecar` — a `medium` `granularity-split` rec passed on `smell_recs` appears in `captured["recommendations"]`, after the correctness/conceptual/data-contract recs.
- `test_persist_drops_info_granularity_split_from_sidecar` — an `info` `granularity-split` rec on `smell_recs` is not in `captured["recommendations"]` (stays advisory-only).
- `test_persist_drops_granularity_merge_from_sidecar` — a `medium`/`info` `granularity-merge` rec on `smell_recs` is not persisted (only `granularity-split` is the split-bridge family).
- `test_persist_drops_repo_structural_smell_from_sidecar` — a non-granularity smell rec on `smell_recs` is not persisted.
- `test_persist_preserves_existing_union_when_no_medium_split` — with no `medium` split in `smell_recs`, `captured["recommendations"]` is unchanged (`correctness + conceptual + data_contract`), pinning that the existing order/behavior is untouched.

Add to `tests/test_data_contract.py` (mirroring `test_data_contract_apply_workflow_documented`):

- `test_completeness_persists_mixed_step_split_documented` — the "Saved review sidecar" section prose names the `granularity-split` mixed-step finding as a persisted completeness producer (assert on `_section(_doc_text(), "Saved review sidecar")` containing `granularity-split` and a "mixed" / "split bridge" phrasing).

### Test-creation order (feature step)

This is a **feature** step — new persistence behavior. Add the `completeness_phases` filter cases first (they pin the subset predicate), then the `DATA_CONTRACT.md` drift case (it pins the doc obligation). Every new test must be green before the step is done; run `uv run pytest tests/cli/test_completeness_cmd.py tests/test_data_contract.py -q`.

## Acceptance criteria

- `_persist_and_present_report`, given a `medium` `source="granularity-split"` rec on `smell_recs`, passes it inside `recommendations=` to `write_completeness_report`.
- The same call, given an `info` `granularity-split` rec or any `granularity-merge` / repo-structural smell rec, does **not** include it in `recommendations=`.
- With no `medium` split in `smell_recs`, `recommendations=` equals the prior `correctness + conceptual + data_contract` union (existing `test_persist_passes_*` cases still green).
- An end-to-end `completeness-audit` of a plan with a mixed refactor+feature step writes a sidecar whose `recommendations` list contains the `medium` `granularity-split` rec with `step_id` set to the mixed step.
- `--fail-on-findings` still exits 0 when the only finding is the mixed-step split (the `TestGranularitySmellNeverGates` invariant holds).
- `DATA_CONTRACT.md`'s saved-review-sidecar section documents the persisted mixed-step `granularity-split` finding, and `test_completeness_persists_mixed_step_split_documented` passes.

## References

- [DATA_CONTRACT.md](../../../../DATA_CONTRACT.md) — the saved-review-sidecar / `Recommendation` schema this step documents against; the code-owned registry (`plan_tool/data_contract.py`) stays authoritative and this step adds no field.

## Deferred

- **Dispatching the persisted finding to the split bridge** — steps 3–4 filter the saved `granularity-split` recs and route them through `escalate_to_split` in the `completeness-apply` walk. This step only persists.
- **Making `granularity-split` apply-eligible in generic walks** — the source stays out of `APPLY_ELIGIBLE_SOURCES` / `_APPLY_AS_FINDING_SOURCES`; the split bridge, not `apply_finding`, is the remedy (steps 3–4).
- **Persisting `granularity-merge` findings** — merge stays advisory (smell-only); its actuation is the separate merge/re-ground bridge, not this plan.
- **Producing the finding** — step 1 owns the Claude-judged producer and the `smell_recs` fold; this step assumes that bucket already carries the `medium` rec.
