> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Put full-roadmap gate checks behind one complete-bundle boundary without changing current results

## Summary

Add a direct complete-bundle gate input to `plan_tool/roadmap_impact_snapshot.py` while keeping the snapshot and single-substitution APIs compatible. Route both paths through one ordered full-roadmap gate walk, with complete evidence validated before any gate runs. Update `tests/test_roadmap_impact_snapshot.py` to characterize bundle completion, direct candidate checking, rejection ordering, and unchanged snapshot behavior. On green, a complete inert candidate can receive all roadmap gate results without a live snapshot, while current capture and structural-revision results stay the same.

## Table of Contents

- [Summary](#summary) — The step outcome and scoped files.
- [Table of Contents](#table-of-contents) — Links to each detail section.
- [Why](#why) — Why complete candidates need the existing gate behavior without live capture.
- [Input](#input) — The snapshot, stage, envelope, and substitution contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two existing files this step changes.
- [Implementation](#implementation) — The complete-bundle boundary and compatibility rules.
- [Tests](#tests) — Focused regression and direct-input coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Digest guidance for complete-bundle evidence.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that limit this step.
- [Deferred](#deferred) — Related gate routes and version work left outside this step.

## Why

`plan_tool/roadmap_impact_snapshot.py:check_full_roadmap_gates()` already provides the snapshot-based full-roadmap gate walk, and `CandidateSubstitution` already proves one selected artifact against its later-stage context. The missing behavior is a direct way to prove a complete candidate assembled from fixed artifact evidence without fabricating a live `RoadmapImpactSnapshot`. This step adds that public feature and treats every existing snapshot result as a compatibility constraint, not as a separately delivered refactor.

## Input

- **Captured snapshot:** `plan_tool/roadmap_impact_snapshot.py:RoadmapImpactSnapshot` carries stage-ordered artifact keys, texts, parsed artifacts, and digests alongside snapshot-specific brief and source identity evidence. The compatibility route must keep consuming this value unchanged.

- **Stage table:** `plan_tool/roadmap.py:RoadmapStage` supplies the ordered `artifact_key`, parser, and gate callable. Supplied stages must continue to match the evidence being checked.

- **Gate envelope:** `plan_tool/roadmap_gates.py:ArtifactEnvelope` requires the artifact under check and its earlier-stage context. Each gate call must retain `predecessor=None` in this full-roadmap path.

- **Single-artifact compatibility input:** `plan_tool/roadmap_impact_snapshot.py:CandidateSubstitution` identifies one stage index and parsed replacement artifact. It remains the input used by `plan_tool/roadmap_structural_revision_proof.py:prove_structural_revision_candidate()`.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_impact_snapshot.py` — Add the complete-bundle gate input and direct entry point, then make both public routes use one ordered gate walk without changing snapshot behavior.
  - `tests/test_roadmap_impact_snapshot.py` — Add direct complete-bundle, validation-order, and compatibility characterization tests using the existing `_stages()` and `_Artifact` helpers.

## Implementation

- **Add one complete candidate evidence value.** Introduce a frozen input such as `CompleteRoadmapGateInput` in `plan_tool/roadmap_impact_snapshot.py`. It must contain only the stage-ordered artifact keys, exact UTF-8 texts, parsed artifacts, and SHA-256 digests needed to prove a complete candidate. It must not carry source paths, recorded-brief state, canonical identities, version ids, reviewer state, or publication authority.

- **Expose a direct complete-bundle checker.** Add `check_complete_roadmap_gates()` for the new input and an optional supplied stage table. It must return the existing ordered `RoadmapGateOutcome` tuple and must not capture live files, admit baselines, acquire a writer guard, or write evidence.

- **Validate all evidence before gates.** The direct route must reject a wrong member count or key order, a digest that does not match `text.encode("utf-8")`, or a parsed artifact that differs from the matching `RoadmapStage.parse()` result. It must reject before calling the first stage gate and must not fill missing members from a snapshot or predecessor.

- **Use the existing gate behavior once.** Adapt each public input to one complete ordered artifact sequence before invoking one private gate evaluator. That evaluator must construct `ArtifactEnvelope` values in stage-table order, run every stage gate once, and retain the existing outcome order. The private extraction is an inseparable implementation detail of the new direct checker: no consumer depends on it, and it is not a second independently delivered change.

- **Keep substitution semantics exact.** `check_full_roadmap_gates()` must retain its current `CandidateSubstitution` validation. The selected artifact replaces only its selected slot; the selected artifact then remains visible in each later envelope. Earlier envelopes, the captured snapshot, and the result type must remain unchanged.

- **Keep snapshot capture as a complete-read boundary.** `capture_roadmap_impact_snapshot()` must finish each artifact read and parse before `_require_current_gates()` evaluates any stage gate. `_require_current_gates()` must keep converting non-empty outcomes into the existing `RoadmapImpactSnapshotError` form, including stage context and violation messages.

- **Keep recheck and structural proof compatible.** `recheck_roadmap_impact_snapshot()` must continue to obtain its second complete read through `capture_roadmap_impact_snapshot()`. `plan_tool/roadmap_structural_revision_proof.py:prove_structural_revision_candidate()` must remain on `check_full_roadmap_gates()` with `CandidateSubstitution`; this step does not convert that caller to the new direct route.

## Tests

### Tests for this step

- `test_capture_completes_all_artifacts_before_running_any_stage_gate` — Asserts every stage parser runs before the first gate spy observes an envelope.

- `test_complete_roadmap_gate_check_uses_every_candidate_member_without_a_snapshot` — Asserts the direct route accepts one complete input, runs all stages in order, and gives each envelope only the corresponding complete candidate context.

- `test_complete_roadmap_gate_check_rejects_invalid_evidence_before_gate_calls` — Asserts missing or reordered members, bad digests, and text/artifact mismatches fail before any gate executes.

- `test_complete_roadmap_gate_check_is_read_only` — Asserts direct complete-bundle checking neither captures roadmap inputs nor mutates its supplied evidence.

- `test_full_roadmap_gate_check_substitutes_candidate_from_its_stage_onward` — Retains the selected-slot and later-envelope behavior while proving the captured snapshot remains unchanged.

- `test_full_roadmap_gate_check_rejects_mismatched_stage_table_before_gate_calls` — Asserts snapshot key or count mismatches fail before a partial gate result exists.

- `test_full_roadmap_gate_check_rejects_an_out_of_range_candidate_stage` — Retains refusal of an invalid substitution index before any stage gate runs.

- `test_capture_reports_shared_gate_violation_with_stage_context` — Retains the snapshot capture error form for a current gate violation.

Every named test must be green before this step is complete.

The direct-checker tests and snapshot-compatibility tests must invoke their
respective public routes independently; a direct-route assertion cannot stand
in for characterization of `check_full_roadmap_gates()`.

## Acceptance criteria

- `check_complete_roadmap_gates()` accepts one complete ordered artifact bundle and returns one `RoadmapGateOutcome` per supplied stage in stage-table order.

- The direct complete-bundle route validates keys, texts, digests, and parsed artifacts before any stage gate runs.

- The direct route never reads live roadmap paths, creates a snapshot, writes evidence, or substitutes a missing candidate member from another input.

- `check_full_roadmap_gates()` retains its existing snapshot and `CandidateSubstitution` behavior, including selected-stage validation, later-envelope context, outcome order, and unchanged snapshot contents.

- Existing-route compatibility is asserted directly through `check_full_roadmap_gates()` independently of the new complete-bundle tests.

- `capture_roadmap_impact_snapshot()` still completes all artifact reads and parsing before its full-roadmap gate evaluation.

- `recheck_roadmap_impact_snapshot()` and `plan_tool/roadmap_structural_revision_proof.py:prove_structural_revision_candidate()` continue to use the snapshot compatibility route without source changes.

- `uv run pytest tests/test_roadmap_impact_snapshot.py -q` passes.

## References

- [hashlib — Secure hashes and message digests](https://docs.python.org/3.13/library/hashlib.html) — Use SHA-256 to bind each direct-input text value to its supplied digest.

## Applicable guardrails

- **The plan’s “## Plan intent” and step intent** — Limit this work to deterministic full-bundle gate admission for inert candidate inputs.

- **The plan’s “## Scope guardrails”, allowed behavior changes** — Preserve existing unversioned snapshot and structural-revision results while adding only the direct complete-candidate gate route.

- **The plan’s “## Scope guardrails”, model and promotion authority** — Keep this boundary read-only; it may validate supplied artifacts but must not create, approve, publish, or select a version.

- **The plan’s “## Scope guardrails”, validation boundary** — Reuse deterministic structural gates only; do not add prose-quality judgments, scoring, new gates, or exit behavior.

- **The plan’s “## Out of scope”** — Do not add version storage, accepted-head handling, durable publication, or legacy-writer changes.

## Deferred

- Consolidating `plan_tool/roadmap.py:_run_stage()`, `plan_tool/roadmap.py:_load_and_regate_below()`, and `plan_tool/roadmap_revision_publish.py:publish_revision_candidate()` with this full-bundle boundary — These routes gate incomplete generation or local publication contexts, so any shared refactor needs separate reconciliation.

- Immutable version records and raw recorded-brief bindings — Step 3 owns the stored-version contract that supplies later direct complete-bundle callers.
