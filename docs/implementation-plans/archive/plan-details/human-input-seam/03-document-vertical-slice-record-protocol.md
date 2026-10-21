> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Document the vertical-slice record protocol and retain the wider migration as a deferred backlog item

## Summary

Create `HUMAN_IO_FORMAT.md` as the operator reference for the filesystem request and resolution records delivered by steps 1 and 2. Update `BACKLOG.md` to retire the completed vertical-slice entry and retain the wider human-input migration as deferred work. Make the landed code the source of truth for field names and behavior rather than copying proposals from earlier plan text. On green, an operator can configure and answer the one supported review-walk interaction, while the backlog makes no repository-wide coverage claim.

## Table of Contents

- [Summary](#summary) — The completed documentation and backlog outcome.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Why the proven record exchange needs an operator contract.
- [Input](#input) — The step-1 protocol and step-2 consumer this documentation describes.
- [Files (creates vs edits)](#files-creates-vs-edits) — The new reference and backlog update.
- [Implementation](#implementation) — Required protocol content and backlog disposition.
- [Tests](#tests) — Existing focused tests and non-code verification.
- [Acceptance criteria](#acceptance-criteria) — Checkable documentation and backlog outcomes.
- [References](#references) — Primary references for the documented filesystem and JSON behavior.
- [Applicable guardrails](#applicable-guardrails) — Boundaries that keep this a single-consumer proof.
- [Deferred](#deferred) — Work deliberately left with the future migration.

## Why

Steps 1 and 2 establish a filesystem exchange that an operator must perform correctly, but the existing `plan_tool/review_walk.py:walk_recommendations` surface does not explain its remote records. A small protocol reference makes the proof usable without treating its two reads in `plan_tool/review_walk.py:_prompt_for_annotation` as evidence that every interactive route has migrated.

## Input

- **Step 1 record contract:** Read the landed `plan_tool/human_io.py:HumanInputRequest`, `plan_tool/human_io.py:HumanInputResolution`, and `plan_tool/human_io.py:make_human_input_provider` interfaces. Their implemented field names, mode handling, file names, and failure behavior control `HUMAN_IO_FORMAT.md`.
- **Step 2 consumer scope:** Read the landed `plan_tool/review_walk.py:walk_recommendations` and `_prompt_for_annotation` changes. The document must identify only `review-walk.annotation` and `review-walk.feedback` as supported prompt purposes.
- **Backlog handoff:** Read `BACKLOG.md` **#322** before editing. The completed proof leaves one deferred migration entry, not a copied route inventory.

## Files (creates vs edits)

- **New files:**
  - `HUMAN_IO_FORMAT.md` — Define the operator-facing configuration, request-record, resolution-record, lifecycle, error, and scope contract for the vertical slice.

- **Existing files (edits only):**
  - `BACKLOG.md` — Retire the completed vertical-slice entry and retain **#322** as the deferred, freshly-inventoried follow-up without references to the retired entry.

## Implementation

- **Foundational logic:** Describe one safe filesystem request-and-resolution exchange for the single review-walk proof.

- **Make code authoritative.** Start `HUMAN_IO_FORMAT.md` with a concise source-of-truth notice naming `plan_tool/human_io.py:make_human_input_provider` and the relevant request and resolution types. The document must state that the landed code wins if it disagrees with the reference.

- **Document configuration and mode selection.** Explain that an unset `PLAN_TOOL_HUMAN_IO` preserves terminal callback behavior, while `PLAN_TOOL_HUMAN_IO=remote` requires a valid existing `PLAN_TOOL_HUMAN_IO_DIR`. State that unsupported explicit modes and invalid directories fail instead of silently selecting terminal input.

- **Document the record pair from the landed schema.** Show valid JSON examples using the field names that `plan_tool/human_io.py` actually writes and reads. Explain the `<request_id>.request.json` and `<request_id>.resolution.json` names, that a request carries its generated identity, stable prompt purpose, and displayed prompt text, and that a resolution supplies the same request identity plus text.

- **Document the operator lifecycle.** Explain that the provider first publishes a complete request, the operator reads that final record, writes the matching resolution to a sibling temporary path, and publishes the complete resolution to its final path without replacing an existing file. The provider remains waiting while only an in-progress temporary resolution exists and reads only the final path. Make clear that each actual read has a fresh request identity; operators must answer the emitted request rather than choosing an identifier themselves.

- **Preserve the record-safety rules.** State that both final paths use complete-before-visible, no-clobber publication. A malformed JSON final record, missing required value, mismatched request identity, or either existing final path produces an error without overwriting either file. State that remote mode has no default answer or terminal fallback.

- **Keep the proof boundary visible.** Name `review-walk.annotation` and `review-walk.feedback` as the only documented prompt purposes. State that the protocol does not make caller-side walk-start checks headless and does not define behavior for other direct-input or human-availability routes.

- **Reconcile the backlog direction.** Retire the vertical-slice entry once the proof is complete. Keep **#322** as the sole broader migration handoff, update it to point to the landed protocol and focused proof instead of the retired entry, and retain its fresh-inventory requirement. Do not add a route inventory, select shared remote policy, or author a follow-up plan in this step.

## Tests

This non-code step adds no test file. The plan’s `change_type: non-code` exempts it from the test-authoring gate; use the checks below to verify the reference against the landed proof.

### Verification (non-code step)

1. `tests/test_human_io.py:test_remote_request_record_preserves_request_identity_and_prompt` — Passes and matches every request field and file-name rule shown in `HUMAN_IO_FORMAT.md`.
2. `tests/test_human_io.py:test_remote_waits_for_matching_text_resolution` — Passes and proves the documented wait-for-a-matching-resolution rule.
3. `tests/test_human_io.py:test_remote_ignores_in_progress_resolution_until_complete_publication` — Passes and proves that a temporary resolution is not read as an answer before final publication.
4. `tests/test_human_io.py:test_existing_request_record_is_never_overwritten` and `tests/test_human_io.py:test_existing_resolution_record_is_never_overwritten` — Pass and prove the documented no-clobber rule.
5. `tests/test_human_io.py:test_remote_rejects_malformed_resolution` and `tests/test_human_io.py:test_remote_rejects_mismatched_resolution_request_id` — Pass and prove that rejected final records do not become answers.
6. `tests/test_review_walk.py:test_remote_annotation_command_request_uses_annotation_prompt_id` and `tests/test_review_walk.py:test_remote_feedback_request_uses_feedback_prompt_id_and_distinct_request_ids` — Pass and match the two prompt purposes and fresh-identity rule in the document.
7. Parse every JSON example in `HUMAN_IO_FORMAT.md` and compare its keys and value types with the landed request and resolution code.
8. Confirm `BACKLOG.md` has no separate vertical-slice entry, retains **#322** as deferred work, and contains no reference to the retired entry.

## Acceptance criteria

- `HUMAN_IO_FORMAT.md` names the landed human-input symbols as its source of truth and states that code wins on disagreement.
- `HUMAN_IO_FORMAT.md` documents the actual remote configuration, request and resolution paths, complete-before-visible publication rule, JSON fields, matching rule, wait behavior, and no-clobber failures.
- Every JSON example in `HUMAN_IO_FORMAT.md` parses and matches the landed record contract.
- `HUMAN_IO_FORMAT.md` names only `review-walk.annotation` and `review-walk.feedback` as supported prompt purposes and makes no repository-wide headless-input claim.
- The focused cases in `tests/test_human_io.py` and `tests/test_review_walk.py` pass.
- `BACKLOG.md` retires the vertical-slice entry and retains **#322** as deferred follow-up work without a stale reference to that entry.

## References

- [Built-in Functions — input()https: — Read this for the terminal-input behavior that remote mode does not replace by default.
- [pathlib — Object-oriented filesystem pathshttps: — Read this for the configured-directory and exclusive-record behavior.
- [json — JSON encoder and decoderhttps: — Read this for the request and resolution examples.

## Applicable guardrails

- **The plan’s “## Plan intent”, single-consumer proof:** Document only the proven review-walk exchange; do not present the protocol as a tool-wide migration.
- **The plan’s “## Step intent”, operable proof:** Give an operator enough information to use and diagnose the record exchange without adding new behavior.
- **The plan’s “## Out of scope”, caller-start behavior:** Do not document a changed TTY or walk-start policy because this step does not change one.
- **The plan’s “## Out of scope”, remote-answer policy:** Do not add defaults, advisory delivery, alternate transports, timeouts, authorization, or conflict rules to the protocol.
- **The plan’s declared risk profile:** Keep the documented filesystem effects limited to the explicitly configured request and resolution directory.

## Deferred

- Remaining direct-input and human-availability routes — **#322** owns a fresh post-proof inventory and any justified migration groups.
- Caller-side review-walk start checks — The plan’s `## Out of scope` keeps these decisions outside the vertical proof.
- Shared remote-answer policy or another transport — Defer until a named future route establishes a concrete need.
