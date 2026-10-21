> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Put full-roadmap gate checks behind one complete-bundle boundary without changing current results

## Summary

Keep full-roadmap gate evaluation in `plan_tool/roadmap_impact_snapshot.py`. Limit changes to that module and `tests/test_roadmap_impact_snapshot.py`, preserving the current gate outcomes and error form. On green, the current snapshot and one-artifact compatibility routes remain intact, while one direct evidenced complete-candidate route reaches the same private ordered gate walk without constructing or capturing a `RoadmapImpactSnapshot`.

## Table of Contents

- [Summary](#summary) — The step’s outcome and narrow footprint.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why candidate checking needs a complete captured bundle.
- [Input](#input) — The snapshot, stage, and candidate contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two scoped files and their roles.
- [Implementation](#implementation) — The shared full-roadmap gate boundary and its invariants.
- [Tests](#tests) — Characterization coverage for ordering, substitution, and errors.
- [Acceptance criteria](#acceptance-criteria) — Observable conditions for completion.
- [References](#references) — Digest guidance relevant to captured snapshot identity.
- [Applicable guardrails](#applicable-guardrails) — Plan fences that limit this work.
- [Deferred](#deferred) — Nearby gate paths that stay outside this step.

## Why

Candidate acceptance needs every gate to see artifacts from one captured roadmap state, not a mix of old and newly read inputs. `capture_roadmap_impact_snapshot()` already builds a `RoadmapImpactSnapshot` before `_require_current_gates()` evaluates it, and `check_full_roadmap_gates()` provides the reusable full-bundle walk. Preserve that seam and pin its ordering so later candidate-version work can reuse the same acceptance boundary without changing the results for current roadmaps.

## Input

- **Captured snapshot:** `plan_tool/roadmap_impact_snapshot.py:RoadmapImpactSnapshot` supplies ordered `artifact_keys`, parsed `artifacts`, retained source text, digests, and canonical source identities. Gate evaluation must use this captured object rather than re-reading individual artifacts.

- **Stage table:** `plan_tool/roadmap.py:RoadmapStage` supplies each `artifact_key` and `gates` callable. The supplied stage sequence must match the snapshot’s ordered keys.

- **Current one-artifact input:** `plan_tool/roadmap_impact_snapshot.py:CandidateSubstitution` identifies one zero-based stage index and parsed candidate artifact. It remains the compatibility input for the shipped structural-revision caller and does not carry version, reviewer, or promotion state.

- **Complete candidate input:** Add one frozen `CompleteRoadmapGateInput` carrying the stage-ordered artifact keys, exact UTF-8 artifact texts, parsed artifacts, and raw text digests for every stage. Callers derive it from their already-validated stored or materialized candidate evidence. It carries gate evidence only—no source paths, source identities, version, reviewer, or promotion state.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_impact_snapshot.py` — Retain the complete-read-then-gate boundary across `capture_roadmap_impact_snapshot()`, `check_full_roadmap_gates()`, and `_require_current_gates()`.
  - `tests/test_roadmap_impact_snapshot.py` — Add or strengthen direct characterization tests for complete capture before gating, candidate context, stage-table validation, and unchanged error behavior.

## Implementation

- **Complete the bundle before gates run.** Keep `capture_roadmap_impact_snapshot()` responsible for reading and parsing every selected `RoadmapStage`, admitting each canonical source identity, and constructing one frozen `RoadmapImpactSnapshot` before it calls `_require_current_gates()`. Do not run a stage gate from `_capture_artifact()` or another per-artifact read path.

- **Use one private full-roadmap gate walk.** Keep `check_full_roadmap_gates()` compatible with its captured snapshot, ordered stage table, and optional current `CandidateSubstitution`. Add one direct `check_complete_roadmap_gates()` entry point for `CompleteRoadmapGateInput`. Both validate and normalize their evidence to one complete ordered artifact tuple, then call the same private envelope-and-gate walk. `_require_current_gates()` must only convert non-empty outcomes into the existing `RoadmapImpactSnapshotError` form.

- **Preserve envelope order and contents.** Build each `plan_tool/roadmap_gates.py:ArtifactEnvelope` in stage-table order with `predecessor=None`. A `CandidateSubstitution` replaces only the captured artifact at its selected index and remains upstream context for later envelopes. The direct complete-candidate route supplies every envelope slot from its input, so no changed stage is checked beside predecessor content and no live snapshot is needed as a carrier.

- **Validate complete candidate evidence before gates.** Require the complete input's count and keys to match the stage table, each digest to match its exact UTF-8 text, and each parsed artifact to equal the result of its matching stage parser on that text. Reject any mismatch before the first gate; do not silently fill a missing candidate member from the predecessor snapshot.

- **Keep input evidence immutable.** Neither public route may mutate `RoadmapImpactSnapshot`, `CompleteRoadmapGateInput`, or the supplied stage table. Candidate inputs are validation values, not writes or replacements of captured evidence.

- **Reject mismatched inputs before calling gates.** Keep the count and `artifact_key` checks between the snapshot and supplied stages, reject a substitution index outside that stage sequence, and reject incomplete or mismatched complete-candidate evidence. These failures must not produce partial gate outcomes.

- **Preserve the current recheck path.** `recheck_roadmap_impact_snapshot()` must continue to call `capture_roadmap_impact_snapshot()`, so an unchanged binding is also re-evaluated through the same complete-bundle gate boundary.

- **Keep the public seam compatible.** `plan_tool/roadmap_structural_revision_proof.py:prove_structural_revision_candidate` already consumes `check_full_roadmap_gates()` with `CandidateSubstitution`; retain that call and its result shape and ordering. `check_complete_roadmap_gates()` is one thin evidence-specific entry to the same private walk, not a replacement for the structural route or a second gate implementation.

## Tests

Use the controlled `_stages()` and `_Artifact` helpers in `tests/test_roadmap_impact_snapshot.py` so the tests observe envelope construction and gate calls without changing real roadmap artifacts.

### Tests for this step

- `test_capture_completes_all_artifacts_before_running_any_stage_gate` — Asserts every artifact parse completes before the first gate spy runs.
- `test_capture_uses_each_stage_current_gate_tuple_with_predecessor_none` — Asserts capture invokes every stage’s existing gate with the accumulated captured context and no predecessor.
- `test_full_roadmap_gate_check_substitutes_candidate_from_its_stage_onward` — Asserts the selected slot and all later envelopes see the candidate while the snapshot remains unchanged.
- `test_complete_roadmap_gate_check_uses_every_candidate_artifact_without_a_snapshot` — Asserts a candidate changing multiple stages supplies every envelope slot from one complete input without a predecessor fallback, live source read, or fabricated snapshot.
- `test_complete_roadmap_gate_check_rejects_mismatched_candidate_evidence` — Asserts missing/reordered keys, wrong text digests, or parsed artifacts that do not match their text reject before any gate call.
- `test_full_roadmap_gate_check_runs_every_affected_stage_gate_once` — Asserts outcomes and gate calls follow the stage table exactly once each.
- `test_full_roadmap_gate_check_rejects_mismatched_stage_table_before_gate_calls` — Asserts mismatched snapshot keys or length raise before any gate runs.
- `test_full_roadmap_gate_check_rejects_an_out_of_range_candidate_stage` — Asserts an invalid candidate index cannot produce a partial full-roadmap check.
- `test_capture_reports_shared_gate_violation_with_stage_context` — Asserts a gate failure keeps its stage number, stage name, and violation message in the existing error form.
- `test_snapshot_capture_never_acquires_writer_guard_or_writes_evidence` — Asserts the shared acceptance boundary remains read-only.

Every named test must be green before this step is complete.

## Acceptance criteria

- `capture_roadmap_impact_snapshot()` completes all selected artifact reads and parsing before it evaluates any stage gate.
- `check_full_roadmap_gates()` returns one `RoadmapGateOutcome` for every supplied stage in stage-table order.
- The compatibility `CandidateSubstitution` changes only its selected envelope slot and the upstream context supplied to later stages; the captured snapshot remains unchanged.
- A complete candidate supplies matched text, parsed artifact, and digest evidence for every stage and is gated directly as one ordered bundle without a snapshot or predecessor fallback.
- A snapshot/stage-table mismatch or invalid candidate index raises before any stage gate runs.
- A current gate violation still raises `RoadmapImpactSnapshotError` with the same stage context and violation text.
- `tests/test_roadmap_impact_snapshot.py` passes with the complete-bundle ordering and no-write behavior covered.

## References

- [hashlib — Secure hashes and message digests](https://docs.python.org/3.13/library/hashlib.html) — Use this for the SHA-256 evidence binding that gate evaluation must preserve rather than recompute from mixed reads.

## Applicable guardrails

- **The plan’s “## Plan intent” and step intent** — Keep this step limited to the shared acceptance boundary for complete candidate artifacts; do not implement candidate storage, review, or promotion here.

- **The plan’s “## Scope guardrails”, allowed behavior changes** — Preserve current behavior for an unversioned roadmap and avoid changing unrelated roadmap execution paths.

- **The plan’s “## Scope guardrails”, model and promotion authority** — Keep this module deterministic and read-only; it may evaluate an inert candidate but must not create, approve, or publish one.

- **The plan’s “## Scope guardrails”, validation boundary** — Reuse existing deterministic stage gates and their results without adding prose-quality judgments, scoring, or new exit behavior.

- **The plan’s “## Out of scope”, version management and writer integration** — Do not add version history, accepted-head reads, durable promotion, or broad legacy-writer migration.

## Deferred

- Consolidating direct per-stage gate calls in `plan_tool/roadmap.py:_run_stage`, `plan_tool/roadmap.py:_load_and_regate_below`, and `plan_tool/roadmap_revision_publish.py:publish_revision_candidate` — Those paths own generation or local publication behavior, so merging them into this read-only full-bundle boundary exceeds this step’s footprint.
