> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Extract one reusable full-roadmap gate evaluator without changing current snapshot or structural-revision results

## Summary

Extract the ordered full-roadmap gate walk in `plan_tool/roadmap_impact_snapshot.py` so current callers share one evaluator. Keep `check_full_roadmap_gates()` as the compatible snapshot-facing entry point, with its current validation, candidate substitution, and result shape unchanged. Update `tests/test_roadmap_impact_snapshot.py` to lock down the shared walk’s ordering, envelopes, validation, and immutability. On green, snapshot capture and structural-revision proof receive the same gate outcomes they receive now.

## Table of Contents

- [Summary](#summary) — The refactor outcome and compatibility promise.
- [Table of Contents](#table-of-contents) — Links to every detail section.
- [Why](#why) — Why the gate walk needs one reusable owner before new candidate inputs exist.
- [Input](#input) — The snapshot, stage, substitution, and outcome contracts this refactor preserves.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two scoped files and their changes.
- [Implementation](#implementation) — The shared evaluator and invariants that must remain unchanged.
- [Tests](#tests) — Focused regression coverage for the extracted walk.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that keep this a refactor.
- [Handoff](#handoff) — The later direct complete-bundle feature.

## Why

`plan_tool/roadmap_impact_snapshot.py:check_full_roadmap_gates()` currently combines snapshot-specific checks with the ordered `ArtifactEnvelope` walk that both snapshot capture and `plan_tool/roadmap_structural_revision_proof.py:prove_structural_revision_candidate()` rely on. A later candidate route needs that ordered walk without fabricating a snapshot, but adding that route before separating the behavior would mix a compatibility refactor with a new API. Isolate the existing evaluator now so future code can reuse the proven gate behavior without changing either current result.

## Input

- **Snapshot contract:** `plan_tool/roadmap_impact_snapshot.py:RoadmapImpactSnapshot` supplies the captured `artifact_keys` and parsed `artifacts` that `check_full_roadmap_gates()` currently validates against the supplied stage table.

- **Stage contract:** `plan_tool/roadmap.py:RoadmapStage` supplies the ordered `artifact_key` and `gates` callable. The evaluator must continue to support injected stage tables used by `tests/test_roadmap_impact_snapshot.py:_stages()` rather than assuming `STAGES`.

- **Candidate contract:** `plan_tool/roadmap_impact_snapshot.py:CandidateSubstitution` supplies one selected stage index and replacement artifact. Its existing non-`None` artifact requirement remains in force.

- **Outcome contract:** `plan_tool/roadmap_impact_snapshot.py:RoadmapGateOutcome` binds each supplied `RoadmapStage` object to that stage’s violations. `plan_tool/roadmap_revision_publish.py:_require_successful_structural_proof()` depends on the returned stage objects retaining their supplied identity.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_impact_snapshot.py` — Extract the ordered full-roadmap evaluator from `check_full_roadmap_gates()` while preserving the public snapshot route and current callers.
  - `tests/test_roadmap_impact_snapshot.py` — Strengthen characterization coverage for evaluator ordering, candidate context, validation-before-gates, and unchanged snapshot behavior.

## Implementation

- **Foundational logic: the stage-ordered full-roadmap gate walk.** Put the loop that accumulates parsed artifacts, creates `plan_tool/roadmap_gates.py:ArtifactEnvelope` values, invokes each `RoadmapStage.gates` callable, and returns `RoadmapGateOutcome` values behind one reusable evaluator in `plan_tool/roadmap_impact_snapshot.py`.

- **Keep the public snapshot API stable.** `plan_tool/roadmap_impact_snapshot.py:check_full_roadmap_gates()` must retain its signature and remain responsible for its current snapshot length, artifact-key, and candidate-index validation before delegating to the extracted evaluator.

- **Preserve exact walk order.** The evaluator must process every supplied stage from first to last, return one outcome per stage in that order, and retain the exact supplied `RoadmapStage` object in each outcome. It must not skip earlier stages when a candidate starts later.

- **Preserve the current envelope rule.** Build each gate input from all artifacts accumulated through that stage and keep `ArtifactEnvelope.predecessor` set to `None`. A candidate replaces only the selected artifact, but that replacement must remain visible in the selected stage’s envelope and every later envelope.

- **Do not mutate captured evidence.** The extracted path must not alter `RoadmapImpactSnapshot.artifacts`, reread roadmap files, acquire a writer guard, or write evidence. Snapshot capture continues through `_require_current_gates()`, and structural proof continues through `plan_tool/roadmap_structural_revision_proof.py:prove_structural_revision_candidate()` without caller changes.

- **Keep this internal to the refactor.** Step 1 does not add a complete-bundle input type, a direct candidate-checking API, immutable-version fields, or new publication behavior. It prepares step 6 by giving the extracted evaluator explicit stage and parsed-artifact inputs while leaving snapshot adaptation in the existing public wrapper.

## Tests

### Tests for this step

In `tests/test_roadmap_impact_snapshot.py`:

- `test_capture_uses_each_stage_current_gate_tuple_with_predecessor_none` — Capture still runs the full ordered walk with `predecessor=None` and the same stage-by-stage accumulated context.

- `test_full_roadmap_gate_check_substitutes_candidate_from_its_stage_onward` — A candidate appears at its selected stage and in later envelopes while captured snapshot artifacts remain unchanged.

- `test_full_roadmap_gate_check_runs_every_affected_stage_gate_once` — The evaluator calls every supplied gate exactly once, returns outcomes in supplied order, and retains the supplied stage objects.

- `test_full_roadmap_gate_check_rejects_an_out_of_range_candidate_stage` — An invalid candidate index raises before any gate runs.

- `test_full_roadmap_gate_check_rejects_stage_table_mismatch_before_gate_execution` — A mismatched snapshot and stage table preserves the current refusal instead of producing partial outcomes.

- `test_capture_reports_shared_gate_violation_with_stage_context` — Snapshot capture still turns a shared evaluator violation into the same stage-context `RoadmapImpactSnapshotError`.

Every listed test must be green before this step is complete.

## Acceptance criteria

- `plan_tool/roadmap_impact_snapshot.py:check_full_roadmap_gates()` keeps its current public signature and returns an ordered tuple of `RoadmapGateOutcome` values for snapshot callers.

- One evaluator owns the ordered `ArtifactEnvelope(predecessor=None, ...)` gate walk in `plan_tool/roadmap_impact_snapshot.py`.

- A candidate substitution affects the selected artifact and every later gate context without mutating `RoadmapImpactSnapshot.artifacts`.

- Snapshot capture continues to reject a gate violation with the current stage-context error behavior.

- `plan_tool/roadmap_structural_revision_proof.py:prove_structural_revision_candidate()` continues to receive complete, stage-identity-preserving outcomes through the unchanged public gate-checking route.

- Step 1 leaves the direct complete-bundle gate input to step 6 and introduces no candidate lifecycle API.

- `tests/test_roadmap_impact_snapshot.py` passes.

## Applicable guardrails

- **The plan’s “## Scope guardrails”, binary observables:** Preserve gate results and their stage bindings as observable compatibility facts; this refactor must not change them.

- **The plan’s “## Scope guardrails”, allowed behavior changes:** Keep this work limited to preparatory reorganization. It must not expose an immutable-candidate lifecycle action.

- **The plan’s “## Scope guardrails”, allowed reorganization:** Limit restructuring to the shared evaluator in `plan_tool/roadmap_impact_snapshot.py`; do not reorganize unrelated roadmap pipeline or artifact-model code.

- **The plan’s “## Out of scope”:** Do not add candidate storage, publication, promotion, or writer behavior while extracting the evaluator.

## Handoff

- Direct complete-bundle gate evidence — Step 6 owns the new candidate input and its first caller; it remains outside this refactor.
