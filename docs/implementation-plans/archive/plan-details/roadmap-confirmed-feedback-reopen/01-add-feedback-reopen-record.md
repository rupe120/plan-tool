> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Add a redacted feedback reopen record and fresh nonce field

## Summary

Extend the roadmap feedback artifact contract with an optional, redacted feedback reopen record. Update `plan_tool/roadmap_artifacts.py` parsing, rendering, and reviewer comments; update `plan_tool/roadmap.py` and `ROADMAP_FORMAT.md` so the lifecycle rule names the one operator-confirmed exception. Preserve ordinary reviewer reopening and every existing feedback artifact unchanged when no record is present. On green, a feedback row can round-trip a complete redacted record whose nonce is available to later receipt work.

## Table of Contents

- [Summary](#summary) — The completed step at a glance.
- [Table of Contents](#table-of-contents) — Links to each major section.
- [Why](#why) — The missing artifact contract and lifecycle wording.
- [Input](#input) — Existing feedback shape and lifecycle rules this step extends.
- [Files (creates vs edits)](#files-creates-vs-edits) — The exact files changed in this step.
- [Implementation](#implementation) — The record contract, redaction boundary, and lifecycle guidance.
- [Tests](#tests) — Focused parser, renderer, and documentation checks.
- [Acceptance criteria](#acceptance-criteria) — Observable conditions for completion.
- [References](#references) — Primary references for nonce handling and tests.
- [Applicable guardrails](#applicable-guardrails) — Scope limits that bind this work.
- [Deferred](#deferred) — Follow-up work owned by later steps.

## Why

`plan_tool/roadmap_artifacts.py:FeedbackRow` currently records the reviewer request, lifecycle state, and optional model response, while `ROADMAP_FORMAT.md:### The feedback lifecycle` says all moves out of `awaiting-review` are reviewer edits. The confirmed reopen needs one redacted current-artifact fact on the selected row so later receipt readers can distinguish the next receipt without retaining the response or legacy evidence that cannot be verified.

## Input

- **Existing feedback contract:** `plan_tool/roadmap_artifacts.py:FeedbackRow`, `_parse_feedback_rows`, and `_feedback_mapping` define the shared shape used by all four roadmap artifact parsers and renderers.
- **Ordinary reopen behavior:** `plan_tool/roadmap_artifacts.py:_parse_proposed_response` deliberately allows an `open` row to retain an earlier response. Keep that behavior; the feedback reopen record must not make a normal reviewer reopen invalid.
- **Model lifecycle boundary:** `plan_tool/roadmap_gates.py:check_feedback_integrity` permits only the model transition from `open` to `awaiting-review`; this step must not widen that model-owned transition.
- **Later consumers:** steps 2 and 3 consume the landed record shape and nonce. This step defines the serialized contract only.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_artifacts.py` — Add the typed optional record, its parse and render support, and reviewer-facing rendered guidance.
  - `plan_tool/roadmap.py` — Correct the module lifecycle contract to preserve reviewer ownership while naming the dedicated confirmed exception.
  - `ROADMAP_FORMAT.md` — Document the feedback-row field, redaction boundary, and the narrow lifecycle exception.
  - `tests/test_roadmap_artifacts.py` — Cover parsing, rendering, compatibility, redaction, and rendered guidance.
  - `tests/test_roadmap_format.py` — Guard the public format and lifecycle documentation against drift.

## Implementation

- **Foundational logic:** add typed parsing and rendering for one optional feedback reopen record attached to a feedback row. Keep it nested under the feedback row rather than creating a new top-level review collection, so `REVIEW_ROW_KEYS` remains the existing `feedback` and `removals` contract.

- **Use a narrow record type:** add a frozen `FeedbackReopenRecord` and an optional `feedback_reopen` field on `plan_tool/roadmap_artifacts.py:FeedbackRow`. Keep the new optional field after `proposed_response` so existing positional `FeedbackRow` construction remains valid.

- **Make the wire shape complete and closed:** require exactly `selector`, `reason`, `nonce`, and `recorded_at`. `selector` is exactly the two-string `ReceiptSafeSelector` mapping, `{"artifact_key": "...", "feedback_id": "..."}`; `reason` is exactly `operator-confirmed-evidence-unavailable`; `nonce` is exactly the 43-character URL-safe token produced by `secrets.token_urlsafe(32)`; and `recorded_at` is a UTC RFC 3339 timestamp with six fractional-second digits and trailing `Z`. Reject missing, blank, wrongly typed, malformed, or extra record fields. This exception to the artifact’s normally open top-level schema prevents a record from becoming a place for response text, digests, evidence data, paths, or operator statements.

- **Preserve redaction in both directions:** extend `_parse_feedback_rows` and `_feedback_mapping` so a valid record round-trips by value. When `feedback_reopen` is absent, render no key and preserve the current output for ordinary feedback rows. Do not derive, copy, hash, or otherwise retain `proposed_response` inside the record.

- **Keep record creation out of this step:** this step defines the nonce field and validates its presence when a record exists; it does not generate a nonce, select a row, clear a response, or write an artifact. Step 4 owns the confirmed atomic transition that creates the record, and step 3 owns receipt identity and currentness.

- **Keep model revision unable to author the record:** do not add `feedback_reopen` to model prompts or revision-operation inputs. The normal stage routes in `plan_tool/roadmap.py:_run_stage` and `_run_bounded_stage_feedback` must clear an existing current record as they create a fresh response; the later dedicated writer is the only code path allowed to set the record.

- **Update reviewer guidance without rewriting legacy bytes:** preserve `_FEEDBACK_KEY_COMMENT` and `_NO_FEEDBACK_KEY_COMMENT` byte-for-byte for artifacts without a record. Add a record-present feedback comment that names the explicitly confirmed `--reopen-feedback` action as the sole tool exception; update the lifecycle statement in `plan_tool/roadmap.py` and `ROADMAP_FORMAT.md` directly. This keeps baseline enrollment canonical while ensuring a reopened artifact does not carry false guidance.

- **Update the format contract consistently:** revise `ROADMAP_FORMAT.md:The review collections`, `### The feedback lifecycle`, the `FeedbackState` description, and the shape table so they agree on the optional record, its redaction boundary, and the ordinary reviewer workflow. Keep the existing `--revise-feedback` no-reopen contract intact.

## Tests

### Tests for this step

- `test_feedback_reopen_record_parses_and_round_trips` — A feedback row with all required record fields parses into `FeedbackReopenRecord` and renders back to an equal artifact.
- `test_feedback_reopen_record_copies_its_selector_and_remains_hashable` — A direct record construction copies its selector, remains immutable, and has stable value hashing.
- `test_feedback_reopen_record_requires_complete_redacted_shape` — Missing, blank, or wrongly typed selector, reason, nonce, or timestamp values raise `RoadmapArtifactError` naming the feedback row and field.
- `test_feedback_reopen_record_rejects_response_evidence_and_freeform_fields` — Unsupported nested keys, including response, digest, evidence, path, and free-form attestation data, fail parsing rather than becoming retained metadata.
- `test_feedback_without_feedback_reopen_remains_legacy_compatible` — Existing feedback fixtures parse and render without a new key or changed value.
- `test_feedback_reopen_record_is_omitted_when_absent` — A row without the optional record renders no `feedback_reopen` key.
- `test_rendered_feedback_guidance_names_only_the_confirmed_reopen_exception` — A record-bearing artifact names the confirmed exception and never presents a model-authored reopen route.
- `test_legacy_feedback_guidance_retains_its_exact_bytes` — Both legacy reviewer-guidance comment forms retain their exact rendered bytes.
- `test_feedback_lifecycle_documents_the_redacted_feedback_reopen_record` — `ROADMAP_FORMAT.md` names the record fields and its redaction boundary.
- `test_feedback_lifecycle_keeps_reviewer_reopen_and_revise_feedback_boundaries` — The format guide keeps ordinary reopening with the reviewer and preserves `--revise-feedback` as unable to reopen feedback.

Every listed test must be green before this step is complete.

## Acceptance criteria

- A feedback row can carry one optional `feedback_reopen` record with the exact selector object, fixed reason, 43-character nonce, and UTC timestamp form.
- Parsing rejects a malformed record and any extra nested field that could retain response, evidence, path, digest, or free-form operator content.
- Parsing and rendering an artifact with no reopen record produces the same feedback contract as before, including omission of the optional key.
- `REVIEW_ROW_KEYS` and the top-level feedback/removals ordering remain unchanged.
- Legacy rendered reviewer comments remain byte-identical; a record-bearing artifact, `plan_tool/roadmap.py`, and `ROADMAP_FORMAT.md` describe `--reopen-feedback` as an operator-confirmed exception while preserving the model’s normal `open` to `awaiting-review` transition only.
- `uv run pytest tests/test_roadmap_artifacts.py tests/test_roadmap_format.py -q` passes.

## References

- [secrets — Generate secure random numbers for managing secretshttps: — Use this when step 4 generates the nonce whose field this step defines.
- [pytest fixtures: explicit, modular, scalablehttps: — Use focused fixtures to isolate record parsing, rendering, and documentation checks.

## Applicable guardrails

- **The plan’s “## Plan intent”, bounded recovery proof:** Keep the record as a narrow fact about the confirmed reopen, not a general evidence or response history surface.
- **The plan’s “## Step intent”, operator-confirmed exception:** Document the one exception without making it available to model-authored revision or ordinary lifecycle editing.
- **The plan’s “## Out of scope”, evidence and provenance limits:** Reject record content outside the fixed redacted shape; do not add evidence handling, attestations, archives, or response provenance.
- **The plan’s “## Out of scope”, command and publication limits:** Do not add a CLI action, writer, lock behavior, journal, or recovery flow in this step.

## Deferred

- `plan_tool/roadmap_gates.py:check_feedback_integrity` and `plan_tool/roadmap_revision_patch.py:merge_stage_feedback_revision` — Keep the existing model-only lifecycle behavior; steps 2 and 4 own the separate guarded exception.
- Safety checks, confirmation handling, nonce generation, and atomic publication — Steps 2 and 4 own the no-mutation refusal rules and writer path.
- Receipt and impact-analysis identity changes — Step 3 owns nonce-aware currentness.
- CLI wiring and broader operator-guide updates — Step 5 owns the command surface and its end-to-end proof.
- General evidence recovery or response provenance — Requires a new seed under the plan’s stated scope fence.
