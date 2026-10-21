> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Share the full-roadmap gate check with candidate proofs

## Summary

Extract the full-roadmap gate traversal from `plan_tool/roadmap_impact_snapshot.py:_require_current_gates` so snapshot capture and later candidate proof use one rule. Update `tests/test_roadmap_impact_snapshot.py` to cover both the unchanged current-state path and a supplied in-memory candidate. Keep `capture_roadmap_impact_snapshot` and `recheck_roadmap_impact_snapshot` responsible for snapshot binding and errors. On green, every relevant stage gate sees the same ordered envelope whether it evaluates captured artifacts or a candidate replacement.

## Table of Contents

- [Summary](#summary) — Reviewer-level outcome and affected surfaces.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Why one traversal must serve snapshots and proofs.
- [Input](#input) — Existing stage, snapshot, and gate contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — Exact file footprint.
- [Implementation](#implementation) — Shared traversal rules and boundaries.
- [Tests](#tests) — Focused coverage for current and candidate contexts.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this refactor.
- [Deferred](#deferred) — Related work deliberately left outside this step.

## Why

`plan_tool/roadmap_impact_snapshot.py:_require_current_gates` currently owns the stage-ordered current-state gate walk. Step 5 needs that same walk with one candidate substituted, and a second loop could drift on stage order, envelope contents, or the required `predecessor=None` rule. Share the traversal now so a proof checks the complete captured roadmap through the same gate contexts that make a snapshot valid.

## Input

- **Captured stage data:** `plan_tool/roadmap_impact_snapshot.py:RoadmapImpactSnapshot` retains parsed artifacts in the order and keys captured from `plan_tool/roadmap.py:RoadmapStage`.
- **Stage contract:** `plan_tool/roadmap.py:RoadmapStage` supplies each stage's `artifact_key` field for the `plan_tool/roadmap_gates.py:ArtifactEnvelope`, and its `gates` field evaluates that stage’s context.
- **Gate contract:** `plan_tool/roadmap_gates.py:ArtifactEnvelope` determines the artifact under check from the last populated stage field. Every shared traversal context must keep `predecessor=None`.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_impact_snapshot.py` — Extract the reusable full-roadmap gate traversal from `_require_current_gates` while preserving snapshot capture and stale-snapshot behavior.
  - `tests/test_roadmap_impact_snapshot.py` — Extend current gate-context coverage and add candidate-substitution coverage for the shared traversal.

## Implementation

- **Foundational logic:** Define one stage-ordered full-roadmap gate traversal that can evaluate captured artifacts or replace one captured artifact with an in-memory candidate.

- **Keep `capture_roadmap_impact_snapshot` as the current-state owner.** It must still capture every supplied `RoadmapStage`, enforce render-canonical text through `_capture_artifact`, and reject a failed current gate through `RoadmapImpactSnapshotError`.

- **Build contexts from stage data, not stage-name branches.** For each stage in supplied order, populate `ArtifactEnvelope` with artifacts from the first stage through the stage being checked, using `RoadmapStage.artifact_key`. Run that stage’s `RoadmapStage.gates` exactly once.

- **Make candidate substitution positional and bounded.** A candidate for one captured stage replaces that artifact in the selected stage’s context and every later stage’s context. Earlier stage contexts must continue to use their captured artifacts. The traversal must not modify the captured `RoadmapImpactSnapshot` or reread artifacts from disk.

- **Keep revision gates inactive.** Every context created by this shared rule must set `ArtifactEnvelope.predecessor` to `None`; candidate proof will separately own predecessor-versus-candidate structural checks in step 5.

- **Separate traversal from caller-specific failure handling.** Preserve the snapshot-facing stage identity and violation-message behavior in `_require_current_gates` or its equivalent wrapper. Expose enough stage-attributed gate outcome for step 5 to reject a candidate without reimplementing the traversal.

- **Do not widen the gate surface.** Leave `plan_tool/roadmap.py:RoadmapStage`, `plan_tool/roadmap_gates.py:ArtifactEnvelope`, the stage gate sets, snapshot binding, and artifact schemas unchanged.

## Tests

### Tests for this step

- `test_capture_uses_each_stage_current_gate_tuple_with_predecessor_none` — Assert that capture evaluates every stage in order, each envelope contains the current prefix through its stage, and every envelope has `predecessor is None`.
- `test_full_roadmap_gate_check_substitutes_candidate_from_its_stage_onward` — Assert that a candidate replaces only its selected stage in that stage’s and later gate contexts, while earlier contexts retain captured artifacts.
- `test_full_roadmap_gate_check_runs_every_affected_stage_gate_once` — Assert that candidate evaluation reaches the selected stage and every later stage exactly once instead of checking only the candidate’s own gate.
- `test_capture_reports_shared_gate_violation_with_stage_context` — Assert that a violation from the shared traversal still prevents snapshot capture and identifies the failing stage through `RoadmapImpactSnapshotError`.
- `test_recheck_reruns_current_gates_even_when_captured_bytes_match` — Keep the existing recheck coverage so unchanged bytes do not bypass a changed gate result.

Green-before-done gate: `uv run pytest tests/test_roadmap_impact_snapshot.py -q` passes.

## Acceptance criteria

- `capture_roadmap_impact_snapshot` evaluates every captured stage gate in supplied stage order using the current artifact prefix and `predecessor=None`.
- The shared traversal can evaluate one in-memory candidate without changing the captured snapshot or reading replacement data from disk.
- A candidate appears in its own and all later stage gate contexts, while earlier contexts retain their captured artifact values.
- A current gate violation continues to reject snapshot capture with stage-specific `RoadmapImpactSnapshotError` output.
- `tests/test_roadmap_impact_snapshot.py` passes with coverage for current-state and candidate-substitution traversal.

## Applicable guardrails

- **The plan’s `## Architecture`, candidate-proof boundary:** Limit this step to declared gate invariants over the captured roadmap context; do not turn gate traversal into semantic impact assessment.
- **The plan’s `## Out of scope`, mutation boundary:** Do not change artifact schemas, stage generation, revision modes, or canonical artifact writes while extracting this read-only rule.
- **The plan’s intent, one-artifact publication boundary:** Keep this helper limited to validating in-memory gate inputs; it must not publish, lock, or otherwise widen a candidate’s write set.

## Deferred

- **Candidate structural comparison and proof result ownership** — Step 5 owns predecessor comparisons and publication-facing proof decisions; this step only supplies the shared gate traversal.
- **Broader envelope-builder consolidation** — `plan_tool/roadmap.py:_build_envelope` and `plan_tool/roadmap_revision_publish.py:publish_revision_candidate` remain unchanged because they serve normal stage runs and local publication; route any wider consolidation through reconcile work.
- **Candidate-aware semantic impact classification** — Remains tracked by BACKLOG #289; this traversal proves only declared gate invariants.
