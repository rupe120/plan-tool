> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Make root enrollment store feedback-free versions while blocking legacy feedback processing until explicit ledger migration

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Update `plan_tool/roadmap.py` so `enroll_roadmap_root` stores feedback-free artifact content in a newly enrolled immutable root and records the ledger state that later feedback routes need. Use step 1’s landed ledger contract to distinguish a clean ledger-native enrollment from an enrollment that contains embedded legacy feedback. Preserve the existing working artifacts exactly as they are; enrollment changes immutable storage and managed ledger state, not the legacy files a reviewer edited. On green, a root selected through `AcceptedRoadmapHead` contains no embedded feedback, while legacy embedded-feedback processing remains unavailable until step 6 records an explicit migration.

## Table of Contents

- [Summary](#summary) — Reviewer view of the completed enrollment boundary.
- [Table of Contents](#table-of-contents) — Links to the sections in this detail.
- [Why](#why) — Why immutable root storage must separate from legacy reviewer input.
- [Input](#input) — Existing enrollment, version, artifact, and step 1 ledger contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — Production and test changes in this step.
- [Implementation](#implementation) — Feedback-free enrollment and migration-pending classification.
- [Tests](#tests) — Focused enrollment and legacy-boundary coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable conditions for completion.
- [References](#references) — Primary references for stable hashing and atomic publication.
- [Applicable guardrails](#applicable-guardrails) — Scope limits for immutable and mutable authority.
- [Deferred](#deferred) — Later owners of migration and ledger processing.

## Why

`plan_tool/roadmap.py:enroll_roadmap_root` currently prepares immutable root members from the captured live artifact texts, even though `plan_tool/roadmap_artifacts.py:REVIEW_ROW_KEYS` identifies embedded review data as a separate channel. That can freeze reviewer-controlled feedback inside accepted version content. Step 1 supplies the separate ledger contract and feedback-removing projection; this step establishes the safe enrollment boundary without silently importing, deleting, or continuing to process the old embedded rows.

## Input

- **Step 1 ledger contract:** Use the landed `plan_tool/roadmap_feedback_ledger.py` projection and ledger-state contract. Step 1 owns the exact persisted names and canonical bytes; the landed module wins over this detail if its identifiers differ.
- **Root enrollment path:** `plan_tool/roadmap.py:enroll_roadmap_root` captures the live snapshot, calls `prepare_root_version_from_snapshot`, builds a generation through `build_root_enrollment_generation`, and publishes it under `_roadmap_writer_owner`.
- **Immutable-version authority:** `plan_tool/roadmap_versions.py:prepare_root_version_from_snapshot`, `build_root_enrollment_generation`, and `AcceptedRoadmapHead` remain the only root-content and selector path.
- **Legacy feedback route:** `plan_tool/roadmap.py:run_roadmap`, `_has_open_feedback`, and `_run_bounded_stage_feedback` still consume `FeedbackRow` values from working artifacts. Treat that route as legacy-only after enrollment; do not adapt it to read the ledger in this step.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/roadmap.py` — Project root-enrollment artifacts through step 1’s feedback-free contract, create the appropriate ledger state under the existing writer guard, and refuse legacy embedded-feedback processing after enrollment until migration is recorded.
  - `tests/test_roadmap.py` — Extend root-enrollment fixtures and direct-API coverage for clean, legacy, and refusal paths.

## Implementation

- **Store projected artifacts, not live review collections.** In `plan_tool/roadmap.py:enroll_roadmap_root`, retain `capture_roadmap_impact_snapshot` as the source-admission and final-recheck authority, but give `prepare_root_version_from_snapshot` a step-1-derived feedback-free version of the captured artifact content. The stored texts, digests, and resulting root version id must describe the projected content, not the original embedded feedback bytes.

- **Keep the root publication atomic.** Build the feedback-free root members, accepted-head selector, and initial ledger-state member into the same guarded enrollment publication performed through `build_root_enrollment_generation` and `publish_roadmap_generation`. A root must not become selectable before its ledger classification is durable, and a failed final recheck must leave neither a selected head nor partial managed state.

- **Classify enrollment from the captured source.** When the captured working artifacts contain no embedded feedback channel, create the step-1 ledger-native initial state. When they contain embedded feedback, create the distinct migration-pending state instead. The classification must inspect the original captured artifacts before projection so stripping content cannot turn a legacy roadmap into a clean enrollment.

- **Do not silently migrate legacy rows.** Preserve every embedded `FeedbackRow`, its state, request, and response in the legacy working artifacts. Do not synthesize ledger items, retarget rows, clear responses, or write a second version to represent an import. Step 6 owns the explicit idempotent import and its completion record.

- **Block every old write route after legacy enrollment, not only feedback.** Ensure the legacy path rooted in `run_roadmap` cannot enter `_run_bounded_stage_feedback`, and cannot regenerate or otherwise rewrite any stage artifact, for an enrolled migration-pending roadmap. Migration (step 6) reads embedded feedback directly from these legacy working artifacts, so they must stay byte-for-value frozen for the entire migration-pending window, not just protected from the feedback sub-flow — a stage regeneration that touches an artifact containing embedded feedback would silently destroy migration's only source. Return the established migration-required refusal shape once the step-1 state contract provides it; the refusal must occur before an invoker call, artifact write, accepted-head change, or ledger mutation. Keep unenrolled roadmap behavior unchanged, including the existing embedded-feedback flow.

- **Do not widen immutable authority.** Reuse `_roadmap_writer_owner`, `roadmap_writer_guard`, `publish_roadmap_generation`, and the accepted-head writer already used by root enrollment. Do not add an alternate version namespace, selector, journal, or direct artifact rewrite route.

- **Keep legacy source admission intact.** `plan_tool/roadmap_source_identity.py:canonical_projection` and the baseline checks continue to support legacy working artifacts during the compatibility period. This step changes what new immutable root storage contains, not the meaning of an unenrolled artifact or the parser and renderer contracts in `plan_tool/roadmap_artifacts.py`.

## Tests

### Tests for this step

- `test_root_enrollment_stores_feedback_free_artifact_versions` — Enroll captured artifacts containing embedded feedback and assert the accepted version loads with no embedded feedback channel while its design content remains intact.
- `test_root_enrollment_preserves_legacy_working_artifact_bytes` — Assert enrollment does not rewrite the source artifact that contains legacy feedback or remove its request, lifecycle state, or proposed response.
- `test_feedback_free_root_enrollment_creates_ledger_native_state` — Enroll a clean artifact set and assert the managed ledger state is immediately ledger-native.
- `test_embedded_feedback_root_enrollment_creates_migration_pending_state` — Enroll artifacts with embedded feedback and assert the managed ledger state requires explicit migration rather than silently importing items.
- `test_legacy_pending_enrollment_blocks_embedded_feedback_processing_before_invoker` — Assert an enrolled migration-pending roadmap cannot reach `_run_bounded_stage_feedback`, call the model invoker, publish artifacts, or alter the accepted head.
- `test_legacy_pending_enrollment_blocks_stage_regeneration_writes` — Assert an enrolled migration-pending roadmap cannot regenerate or rewrite any stage artifact through `run_roadmap`, so the legacy working artifacts step 6 later reads stay byte-for-value unchanged for the whole migration-pending window.
- `test_root_enrollment_final_recheck_refusal_leaves_no_head_or_ledger_state` — Force the existing final source recheck to refuse and assert root members, selector, and initial ledger state are absent.
- `test_unenrolled_legacy_feedback_route_remains_available` — Assert the existing embedded-feedback route retains its current behavior before root enrollment.

Green-before-done gate: every test above and `uv run pytest tests/ -q -n auto` must pass.

## Acceptance criteria

- Root versions created by `enroll_roadmap_root` contain artifact content with no embedded feedback channel.
- Enrollment preserves the original legacy working artifacts without rewriting their embedded feedback.
- A feedback-free enrollment records ledger-native state in the same guarded publication as its immutable root and accepted head.
- An enrollment with embedded feedback records migration-pending state and does not create ledger items from that feedback.
- Legacy embedded-feedback processing on a migration-pending enrolled roadmap refuses before any model invocation or durable mutation.
- Stage regeneration through `run_roadmap` on a migration-pending enrolled roadmap also refuses before any model invocation or durable mutation, so the legacy working artifacts stay byte-for-value frozen until migration completes.
- Existing unenrolled legacy roadmap behavior remains unchanged.
- `tests/test_roadmap.py` and the full required test command pass.

## References

- [json — JSON Encoder and Decoder](https://docs.python.org/3.13/library/json.html) — Review stable serialization rules used by immutable version and ledger evidence.
- [hashlib — Secure Hashes and Message Digests](https://docs.python.org/3.13/library/hashlib.html) — Review SHA-256 inputs when projected artifact content changes version identity.
- [os — Miscellaneous Operating System Interfaces](https://docs.python.org/3.13/library/os.html#os.replace) — Review atomic replacement expectations behind durable guarded publication.

## Applicable guardrails

- **The plan’s “## Scope guardrails”, ledger ownership:** This step must keep reviewer input outside canonical artifact content and must not make ledger writes another accepted-head authority.
- **The plan’s “## Scope guardrails”, existing publication authority:** This step must use the existing guarded publication and accepted-head path rather than create a parallel version chain or transaction path.
- **The plan’s “## Scope guardrails”, exact batch evidence:** This step may establish enrollment state only; it must not invent candidate, response, or later ledger-snapshot behavior.
- **The plan’s “## Out of scope”, automatic retargeting:** This step must preserve embedded items as legacy input and must not infer ledger targets during enrollment.
- **The plan’s “## Out of scope”, user interface:** Keep this work in root enrollment and direct API behavior; command wiring and reviewer-edit actions remain with later steps.

## Deferred

- Explicit idempotent import of embedded feedback and migration completion recording — Step 6 owns the ledger mutation and reviewer-facing migration route.
- Root-and-active candidate batch construction and ledger eligibility processing — Step 3 owns the processing-source and immutable batch boundary.
- Feedback-free successor generation and candidate storage — Steps 4 and 5 own proposal responses, derived context, and active-candidate state.
- Retirement of the unenrolled embedded-feedback compatibility path — Step 10 owns command routing and the final legacy-writer boundary.
