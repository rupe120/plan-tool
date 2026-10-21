> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Add the confirmed feedback reopen operation

## Summary

Extend `plan_tool/roadmap_feedback_reopen.py` with the confirmed, writer-checked reopen operation and add a narrow publication path in `plan_tool/roadmap_revision_publish.py`. The operation must recheck the selected artifact’s canonical bytes and baseline admission under the writer lock before replacing anything. On success, exactly one safe row becomes `open`, its response is omitted, and it carries one redacted step-1 record; all refusal paths leave disk unchanged.

## Table of Contents

- [Summary](#summary) — The completed behavior at a glance.
- [Table of Contents](#table-of-contents) — Links to each major section.
- [Why](#why) — The missing safe mutation boundary.
- [Input](#input) — Contracts supplied by earlier steps and existing publication code.
- [Files (creates vs edits)](#files-creates-vs-edits) — The files this step changes.
- [Implementation](#implementation) — The confirmed transition and atomic publication rules.
- [Tests](#tests) — Focused success, refusal, and publication tests.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Primary references for nonce and atomic-write behavior.
- [Applicable guardrails](#applicable-guardrails) — Scope limits that bind this writer.
- [Deferred](#deferred) — Work owned by other steps or a future seed.

## Why

`plan_tool/roadmap_escalation_selection.py:select_receipt_feedback` correctly leaves answered rows outside the ordinary receipt path, while `plan_tool/roadmap_revision_publish.py:publish_revision_candidate` is designed for broader local revisions that update baseline and seed-state members. The confirmed feedback reopen needs a separate, deterministic mutation boundary that changes only the selected feedback row after an in-lock currentness check. The confirmation, not the artifact, supplies the unavailable-evidence determination, so this operation must not grow a classifier or general feedback editor.

## Input

- **Step 1 record contract:** Step 1 establishes the optional `feedback_reopen` row field and `FeedbackReopenRecord` shape. Read the landed record fields and validation rules before implementing this step; its code wins over this detail if names differ.

- **Step 2 candidate contract:** Step 2 provides the pure safety, candidate construction, and candidate-currentness APIs in `plan_tool/roadmap_feedback_reopen.py`. This step consumes those results and must not duplicate their row-selection or source-binding rules.

- **Stage and source admission:** `plan_tool/roadmap.py:RoadmapStage` supplies the selected artifact’s path, parser, and renderer. `plan_tool/roadmap_escalation_selection.py:canonical_artifact_snapshot` and `admit_versioned_artifact_source` remain the source-admission path.

- **Publication boundary:** `plan_tool/roadmap_revision_publish.py:roadmap_writer_guard`, `require_roadmap_writer_token`, and `_publish_generation` provide the active writer lease and existing recoverable atomic replacement path.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_feedback_reopen.py` — Add the confirmed operation, writer-checked source reads, record creation, candidate transformation, and redacted result or refusal facts.
  - `plan_tool/roadmap_revision_publish.py` — Add the narrow feedback-reopen artifact-only publication helper that reuses the active writer token and existing generation writer.
  - `tests/test_roadmap_feedback_reopen.py` — Cover direct orchestration success and every refusal-without-mutation path.
  - `tests/test_roadmap_revision_publish.py` — Cover the new writer-token, final-boundary, and artifact-only publication behavior.

## Implementation

- **Foundational logic: confirmed feedback reopen transition.** Add one direct operation that accepts selector input plus explicit confirmation and mode-conflict facts, then either refuses without changing disk or atomically publishes one safe row’s reopen transition. The operation validates its selector into the receipt-safe form before source reads. The confirmation is the authority for the unavailable-evidence determination; this operation does not infer it.

- **Require confirmation before mutation.** A false or missing confirmation must return a closed refusal result and must not acquire a write path that can publish. Step 5 owns argument parsing, acknowledgement text, and occurrence-based mode-conflict detection; this module receives and enforces the resulting facts.

- **Hold the writer lock across observation and publication.** In `plan_tool/roadmap_feedback_reopen.py`, acquire `plan_tool/roadmap_revision_publish.py:roadmap_writer_guard` before reading the selected artifact. Reuse its `RoadmapWriterToken` for the eventual publisher instead of opening a nested guard.

- **Use the step-2 candidate twice.** Build the initial candidate from a canonical, baseline-admitted selected artifact under the lock. Immediately before replacement, read the full selected artifact again, repeat canonical snapshot and baseline admission, and require the step-2 currentness check to match the captured source digest, safe row, and receipt-resolvable target.

- **Treat all visible byte changes as stale.** The final check must refuse a changed selected row, another feedback row, a design row, prose body, or noncanonical presentation bytes. Do not merge the candidate with the new file contents, and make no guarantee about an external raw write after that final check.

- **Build one fixed redacted record.** Transform only the selected `FeedbackRow`: set `state` to `FeedbackState.OPEN`, set `proposed_response` to `None`, and attach one landed step-1 record with the exact selector mapping, fixed `operator-confirmed-evidence-unavailable` reason, fresh `secrets.token_urlsafe(32)` nonce, and canonical UTC timestamp. Do not accept any of those record facts from free-form caller input.

- **Preserve every unrelated value.** Keep feedback order, all unselected rows, design rows, artifact body, and the selected row’s request and target unchanged. The response must be absent from the rendered candidate and must not appear in the operation result, record, or publication error.

- **Publish only the selected artifact.** Add a narrowly named helper in `plan_tool/roadmap_revision_publish.py` rather than routing through `publish_revision_candidate`. It should require the active matching writer token, render and reparse the candidate, run the final callback at `_publish_generation`’s replacement boundary, and publish a generation containing only the selected artifact member.

- **Leave semantic sidecars alone.** The reopen changes feedback only, which `plan_tool/roadmap_source_identity.py:canonical_projection` excludes from baseline identity. Preserve the existing baseline and seed-state bytes; do not invalidate seeds or add a new journal or recovery surface.

- **Keep the operation direct and redacted.** Do not add a run log, argument-parser setup, model invocation, evidence read, history lookup, or another lifecycle-edit route. The caller needs only a redacted success or refusal outcome suitable for step 5 to render.

## Tests

### Tests for this step

- `tests/test_roadmap_feedback_reopen.py:test_feedback_reopen_reopens_exactly_one_safe_row_with_a_redacted_record` — A confirmed safe selection clears only that response, returns the row to `open`, and writes one valid record with the exact reason, nonce, and timestamp forms.

- `tests/test_roadmap_feedback_reopen.py:test_feedback_reopen_preserves_unselected_rows_and_artifact_content` — Feedback order, other feedback rows, design rows, prose, request, and target remain unchanged.

- `tests/test_roadmap_feedback_reopen.py:test_feedback_reopen_requires_confirmation_without_mutation` — A missing or false confirmation publishes nothing.

- `tests/test_roadmap_feedback_reopen.py:test_feedback_reopen_rejects_unsafe_selector_before_source_read` — Both raw and caller-constructed receipt-unsafe selectors refuse before the operation enters the writer or source-admission path.

- `tests/test_roadmap_feedback_reopen.py:test_feedback_reopen_refuses_an_unsafe_or_already_recorded_row_without_mutation` — Wrong state, blank response, duplicate or missing selection, and an intact record cannot reopen a row.

- `tests/test_roadmap_feedback_reopen.py:test_feedback_reopen_refuses_a_target_unavailable_to_ordinary_receipt_without_mutation` — A missing, malformed, absent, or ambiguous target cannot reopen and leaves the artifact unchanged.

- `tests/test_roadmap_feedback_reopen.py:test_feedback_reopen_refuses_noncanonical_or_baseline_changed_source_without_mutation` — Source admission failures never reach publication.

- `tests/test_roadmap_feedback_reopen.py:test_feedback_reopen_final_recheck_refuses_every_visible_source_change` — Selected-feedback, unselected-feedback, design-row, prose, and presentation-byte changes at the final check remain on disk and no candidate is merged.

- `tests/test_roadmap_feedback_reopen.py:test_feedback_reopen_does_not_return_or_record_the_prior_response` — The prior response is absent from the published artifact’s record and direct result facts.

- `tests/test_roadmap_revision_publish.py:test_feedback_reopen_publication_requires_the_active_matching_writer_token` — A missing, inactive, or foreign token cannot use the specialized writer.

- `tests/test_roadmap_revision_publish.py:test_feedback_reopen_publication_replaces_only_the_selected_artifact` — The artifact changes through the generation writer while its baseline and seed-state sidecars remain unchanged.

- `tests/test_roadmap_revision_publish.py:test_feedback_reopen_publication_runs_the_final_recheck_before_replacement` — A refusal at the replacement boundary leaves artifact bytes unchanged and clears the pending generation journal.

Green-before-done gate: every listed test and `uv run pytest tests/ -q -n auto` must pass.

## Acceptance criteria

- A confirmed receipt-safe selection reopens exactly one current, safe row whose target can issue an ordinary receipt, and atomically writes its redacted record with the exact reason, nonce, and timestamp forms.

- The selected row renders as `open` with no `proposed_response`; its request and target remain unchanged.

- Missing confirmation, an unsafe row or target, an existing record, failed source admission, or a visible final-check change refuses without mutation.

- The final check compares the full canonical source digest as well as current baseline admission and row safety.

- The specialized publication path requires the active matching writer token and changes only the selected artifact, not its baseline or seed-state sidecars.

- The action performs no merge, external-writer coordination, run logging, evidence inspection, history lookup, recovery command, or argument-parser setup.

- `tests/test_roadmap_feedback_reopen.py`, `tests/test_roadmap_revision_publish.py`, and the configured full test command pass.

## References

- [secrets — Generate secure random numbers for managing secretshttps: — Use this for the fresh opaque nonce recorded by the confirmed transition.

- [os — Miscellaneous operating system interfaces (os.replace)https: — Review the atomic replacement primitive used by the existing generation writer.

- [pytest fixtures: explicit, modular, scalablehttps: — Use isolated fixtures for baseline admission, final-check drift, and no-mutation assertions.

## Applicable guardrails

- **The plan’s “## Plan intent”, bounded recovery proof:** Limit this operation to one confirmed selected row and its redacted current-artifact record; confirmation is authority, not evidence classification.

- **The plan’s “## Step intent”, final in-lock recheck:** Refuse stale visible input rather than merging it, and do not claim safety for external writes after the final check.

- **The plan’s “## Out of scope”, evidence and provenance limits:** Do not read, classify, retain, or infer legacy evidence or response provenance.

- **The plan’s “## Out of scope”, lifecycle and command limits:** Keep ordinary lifecycle ownership unchanged and leave the exclusive CLI surface to step 5.

- **The plan’s “## Out of scope”, publication limits:** Reuse the existing atomic writer without adding a new recovery, journal, terminal-event, or broad operator-view contract.

## Deferred

- CLI parsing, exclusivity checks, help text, and end-to-end command coverage — Step 5 owns the operator surface.

- Receipt and impact-analysis nonce currentness — Step 3 owns the identity and reader updates.

- General evidence recovery, response provenance, raw-record integrity detection, and external-writer serialization — Require a new seed under the plan’s scope fence.
