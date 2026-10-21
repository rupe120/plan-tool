> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Define strict receipt selection, canonicality, and reason capture

## Summary

Define the receipt-only selection contract in `plan_tool/roadmap_escalation_selection.py` using the shared selector and lookup facts from step 1. Extend `plan_tool/roadmap_feedback.py` with the narrow receipt-safe identifier check without changing the existing selector grammar. The main decision is that receipt selection returns one ordered verdict from the selected artifact only; it does not reuse local revision eligibility or inspect other artifacts. When green, callers can obtain one raw-byte, render-canonical snapshot plus a selected safe target and closed reason, or a precise rejection reason.

## Table of Contents

- [Summary](#summary) — Reviewer-level outcome and affected modules.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why receipt selection needs its own contract.
- [Input](#input) — Contracts received from step 1 and existing roadmap types.
- [Files (creates vs edits)](#files-creates-vs-edits) — New and modified files.
- [Implementation](#implementation) — Selection order, canonicality, and identifier rules.
- [Tests](#tests) — Focused contract coverage for every outcome.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Digest API reference.
- [Applicable guardrails](#applicable-guardrails) — Boundaries this step must preserve.
- [Deferred](#deferred) — Related work deliberately left outside this step.

## Why

`plan_tool/roadmap_revision.py:preflight_feedback_revision` combines selection with the bounded local writer’s row-only target and text-field rules. A structural receipt needs the same selector facts but must accept artifact targets, preserve evidence from locally ineligible requests, and never decide impact beyond the selected artifact. Defining that contract before receipt persistence gives later steps one safe, deterministic source for selection, reason, and source-freshness facts.

## Input

- **Step 1 shared boundary:** `plan_tool/roadmap_feedback.py:FeedbackSelector`, its selector parser, and its artifact-local matching-row lookup provide syntax and candidate facts only. Step 2 adds receipt policy above that boundary without changing those facts.
- **Configured stage contract:** `plan_tool/roadmap.py:RoadmapStage` and `plan_tool/roadmap.py:STAGES` provide the selected stage’s artifact key, parser, and renderer. Keep stage configuration injected by the caller; the new selection module must not own or modify the stage table.
- **Parsed artifact contract:** `plan_tool/roadmap_artifacts.py:FeedbackRow`, `plan_tool/roadmap_artifacts.py:FeedbackTargetKind`, and `plan_tool/roadmap_artifacts.py:design_row_collections` define feedback state, target shape, and live design rows in one artifact.
- **Source limit:** Work from one supplied raw selected-artifact byte snapshot. Reading the selected path and mapping later command outcomes remain outside this step.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_escalation_selection.py` — Pure receipt snapshot, reason, identifier, and selected-artifact selection contract.
  - `tests/test_roadmap_escalation_selection.py` — Direct tests for snapshot and receipt-selection outcomes.

- **Existing files (edits only):**
  - `plan_tool/roadmap_feedback.py` — Add the receipt-safe identifier predicate while leaving shared selector parsing and candidate lookup unchanged.
  - `tests/test_roadmap_feedback.py` — Test the new identifier grammar and prove it does not narrow the existing selector grammar.

## Implementation

- **Foundational logic:** Admit one receipt-safe selector before any source work, then select exactly one receipt-eligible feedback row and target from one render-canonical artifact snapshot in a fixed rejection order.

- **Keep selector facts separate from receipt admission.** Build on step 1’s `plan_tool/roadmap_feedback.py:FeedbackSelector` and fixed-stage recognition. Preserve the existing selector grammar, including its original feedback-id text, then expose a separate pure receipt-admission check. Do not make the shared parser reject a locally valid but receipt-unsafe identifier.

- **Define one receipt-safe identifier rule and its order.** Add a pure predicate in `plan_tool/roadmap_feedback.py` for ASCII identifiers matching `[A-Za-z0-9][A-Za-z0-9._-]{0,127}`. After closed selector syntax and fixed-stage recognition, apply it to the selector artifact key and feedback id before reason validation, supplied-source access, feedback lookup, cardinality, or row-state checks; an unsafe selector is the outer `identifier-rejected` preflight with no resolved fields. Apply the same predicate to a selected row target only inside the later selected-artifact predicate, before that target becomes a receipt-facing fact. Do not change the broader roadmap row-id grammar or the local revision contract.

- **Make the new module a pure receipt contract.** `plan_tool/roadmap_escalation_selection.py` should consume supplied bytes, parser and renderer callables, a receipt-safe parsed selector, and a closed reason. Its caller performs the outer selector admission before it supplies either reason or bytes. The module must not read paths, write files, invoke a backend, emit telemetry, import `plan_tool/roadmap_revision.py`, or import `plan_tool/roadmap.py`.

- **Bind canonicality to one raw snapshot.** Strictly decode the supplied bytes as UTF-8, parse that exact text with the selected stage parser, render the parsed artifact, encode the rendered text as UTF-8, and compare those bytes with the original snapshot. Do not normalize line endings, Unicode, whitespace, or frontmatter. Compute the SHA-256 digest from the original bytes only after successful UTF-8 decoding; retain that digest for parse and canonicality rejections, but not for undecodable input.

- **Keep snapshot evidence distinct from receipt data.** The snapshot may retain the parsed artifact internally so selection can inspect it, but receipt-facing selection facts must contain only safe selector and target identifiers, lifecycle state, reason, and source digest. Do not return or copy `FeedbackRow.request`, target prose, relation data, or artifact body into the selection result.

- **Use one total selected-artifact-only predicate for a safe selector.** Use the shared lookup to preserve zero, one, or many candidates, then return the first applicable receipt verdict in this order: `missing-feedback`, `duplicate-feedback`, `not-open`, `already-responded`, `identifier-rejected` for an unsafe parsed row target, `missing-or-ambiguous-target`, `target-not-live-in-selected-artifact`, or acceptance. Check lifecycle state before response presence. Do not use this predicate to reclassify an unsafe selector.

- **Treat parsed target shape as a snapshot failure.** `plan_tool/roadmap_artifacts.py:_parse_feedback_target` already rejects a missing or malformed target. Do not add a receipt-selection fallback that invents a target verdict for malformed artifact data; parsing must fail before the predicate runs.

- **Handle both valid target kinds.** For `FeedbackTargetKind.ARTIFACT`, select the selector artifact key as the target identifier. For `FeedbackTargetKind.ROW`, require a receipt-safe row id, then inspect every collection from `plan_tool/roadmap_artifacts.py:design_row_collections` in the selected artifact only. Zero live matches, including a target named only by a removal record, is `target-not-live-in-selected-artifact`; more than one live match is `missing-or-ambiguous-target`.

- **Do not inherit local revision policy.** `plan_tool/roadmap_revision.py:preflight_feedback_revision` remains row-only and checks `TEXT_FIELDS_BY_ROW_TYPE`; receipt selection must neither call it nor copy its allowlist. An artifact-targeted open row can be receipt-eligible even though local revision rejects it.

- **Close the reason vocabulary.** Accept only `prose`, `row-structure`, `collection-structure`, `relationship-semantics`, `decision-semantics`, and `cross-artifact-impact`. Preserve the chosen value exactly in the selection facts. Reject any other value rather than deriving a reason from reviewer text or choosing an impact route.

## Tests

### Tests for this step

- `tests/test_roadmap_feedback.py::test_receipt_safe_id_accepts_the_closed_ascii_grammar` — Accepts valid one-to-128-character ASCII routing identifiers.
- `tests/test_roadmap_feedback.py::test_receipt_safe_id_rejects_empty_non_ascii_bad_prefix_invalid_character_and_overlong_values` — Rejects every identifier shape outside the receipt boundary.
- `tests/test_roadmap_feedback.py::test_selector_parser_preserves_its_broader_existing_grammar` — Proves a selector can remain syntactically valid while receipt admission later rejects its unsafe identifier.
- `tests/test_roadmap_escalation_selection.py::test_canonical_snapshot_binds_parsed_artifact_and_digest_to_the_original_raw_bytes` — Proves parsing, rendering, and SHA-256 use one supplied UTF-8 byte snapshot.
- `tests/test_roadmap_escalation_selection.py::test_canonical_snapshot_rejects_non_utf8_before_exposing_a_digest` — Proves undecodable source has no digest or parsed artifact.
- `tests/test_roadmap_escalation_selection.py::test_canonical_snapshot_retains_raw_digest_for_parse_and_render_canonicality_rejections` — Proves readable malformed and noncanonical source retains the raw-byte digest for later preflight reporting.
- `tests/test_roadmap_escalation_selection.py::test_canonical_snapshot_rejects_crlf_without_normalizing_source_bytes` — Proves renderer-byte comparison rejects CRLF or other raw-byte changes.
- `tests/test_roadmap_escalation_selection.py::test_reason_accepts_each_closed_receipt_reason_without_reclassification` — Accepts every listed reason and preserves its selected value.
- `tests/test_roadmap_escalation_selection.py::test_reason_rejects_values_outside_the_closed_vocabulary` — Rejects blank, altered, and unknown reason values.
- `tests/test_roadmap_escalation_selection.py::test_selection_reports_missing_and_duplicate_feedback_before_lifecycle_checks` — Preserves zero and many matching candidates as distinct first verdicts.
- `tests/test_roadmap_escalation_selection.py::test_selection_checks_non_open_state_before_existing_response` — Proves an overlapping non-open and answered row returns `not-open`.
- `tests/test_roadmap_escalation_selection.py::test_selection_rejects_an_open_row_with_a_proposed_response` — Returns `already-responded` only after the row is open.
- `tests/test_roadmap_escalation_selection.py::test_selection_accepts_an_artifact_target_without_local_revision_allowlist_checks` — Produces an artifact target whose id is the selector artifact key.
- `tests/test_roadmap_escalation_selection.py::test_receipt_safe_selector_rejects_before_reason_source_or_feedback_lookup` — Proves a syntactically valid unsafe selector reaches the outer `identifier-rejected` result before reason validation, source access, cardinality, or row-state checks.
- `tests/test_roadmap_escalation_selection.py::test_selection_rejects_unsafe_row_target_before_recording_target_facts` — Applies receipt-safe target admission before target liveness and exposes no unsafe target id.
- `tests/test_roadmap_escalation_selection.py::test_selection_reports_ambiguous_and_missing_live_row_targets_in_selected_artifact` — Distinguishes duplicate live rows from absent rows, including an id retained only in removals.
- `tests/test_roadmap_escalation_selection.py::test_selection_never_uses_another_artifact_to_make_a_row_target_live` — Rejects a target absent from the selected artifact even when another artifact could contain the same id.

Every listed test must be green before this step is complete.

## Acceptance criteria

- `plan_tool/roadmap_feedback.py` exposes a pure receipt-safe identifier check with the closed ASCII grammar while its selector parser keeps the existing local-revision grammar.
- `plan_tool/roadmap_escalation_selection.py` accepts one raw byte snapshot and proves UTF-8 decode, parse, render, byte-level canonicality, and digest binding without reading or writing a path.
- A non-UTF-8 snapshot exposes no digest; a readable source that fails parsing or render-byte canonicality retains the digest of its original raw bytes.
- After closed selector syntax and fixed-stage recognition, receipt admission rejects an unsafe selector before reason or source work; for a receipt-safe selector, selection returns exactly one ordered selected-artifact verdict and never silently picks a duplicate feedback row or target.
- An artifact target is receipt-eligible with the selector artifact key as its target id; a row target is eligible only when it is receipt-safe and appears exactly once in the selected artifact.
- Receipt selection never reads another artifact, consults local revision field policy, infers impact, or carries reviewer prose in its receipt-facing result.
- Only the six closed reason values are accepted, and the selected value is retained unchanged.
- `tests/test_roadmap_feedback.py` and `tests/test_roadmap_escalation_selection.py` pass.

## References

- [hashlib — Secure hashes and message digests](https://docs.python.org/3.13/library/hashlib.html) — Use for the SHA-256 digest bound to the raw selected-artifact bytes.

## Applicable guardrails

- **The plan’s “## Step intent”, receipt-only selection:** Keep selection limited to the chosen artifact, receipt-safe identifiers, canonical source evidence, and one closed reason.
- **The plan’s “## Plan intent”, no-write boundary:** Keep this module pure; it must not publish a receipt, change a roadmap artifact, invoke a backend, or start broader work.
- **The plan’s “## Out of scope”, local revision compatibility:** Do not change `plan_tool/roadmap_revision.py:preflight_feedback_revision`, its allowlist, or its failure and recovery behavior.
- **The plan’s “## Out of scope”, impact analysis:** Do not inspect other artifacts, calculate relation closure, or turn a reason into a route recommendation.
- **The plan’s “## Out of scope”, identifier grammar:** Narrow only the receipt-facing identifiers; do not alter artifact parsing or roadmap-wide row identifiers.
- **The plan’s “## Out of scope”, immutable evidence storage:** Define selection facts only. Receipt schema, persistence, final-name binding, and storage lifecycle remain with later steps.

## Deferred

- `plan_tool/roadmap_revision.py:preflight_feedback_revision` and `plan_tool/roadmap_revision.py:TEXT_FIELDS_BY_ROW_TYPE` — Keep bounded local-revision eligibility unchanged; it serves a different write contract.
- `plan_tool/roadmap.py:_check_predecessor_review_rows` and `plan_tool/roadmap_gates.py:check_feedback_integrity` — Keep roadmap-run feedback validation separate because it has predecessor and removal-record rules that receipt selection must not adopt.
- `plan_tool/roadmap_revision_run.py:_selected_target_id` and `plan_tool/roadmap_revision_patch.py:_selected_feedback` — Leave local logging recovery and merge-time snapshot checks unchanged; consolidating their distinct failure contracts needs a separately scoped refactor.
- `roadmap-escalation-impact-routing` — Owns relation closure, cross-artifact impact analysis, and route selection after a receipt is available.
- Receipt schema belongs to step 3, lifecycle mapping to step 4, parser preparation to step 5, and receipt CLI wiring to step 6 after this step supplies selection facts.
