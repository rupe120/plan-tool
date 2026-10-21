# Step 6 — Document roadmap failure receipts and record the shipped backlog slice

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Document the completed roadmap rejected-response evidence flow in `README.md`, `docs/OPERATIONS.md`, and `docs/ARCHITECTURE.md`. Update the run-log guidance to describe the shared redacted receipt, its optional sidecar pointer, and the roadmap producer paths covered by steps 3–5. Keep `BUG_BACKLOG.md` as the owner of later producer migrations while updating it to show that the selected roadmap slice is complete; keep `BACKLOG.md` #217 as consolidated provenance rather than an independent work item. On green, an operator can find the durable receipt and any available raw sidecar without mistaking it for accepted-response storage or a new retry policy.

## Table of Contents

- [Summary](#summary) — Gives the completed documentation and backlog outcome.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Explains the remaining operator and tracking gap after producer wiring.
- [Input](#input) — Names the shared receipt and roadmap producer contracts this step documents.
- [Files (creates vs edits)](#files-creates-vs-edits) — Lists the documentation and backlog updates.
- [Implementation](#implementation) — Defines the documentation ownership and backlog-recording approach.
- [Tests](#tests) — Lists non-code verification for the documented contract.
- [Acceptance criteria](#acceptance-criteria) — States reviewer-checkable completion conditions.
- [References](#references) — Points to the receipt source entry and run-log contract.
- [Applicable guardrails](#applicable-guardrails) — Applies the plan’s evidence and scope boundaries.
- [Deferred](#deferred) — Records later migrations and unrelated receipt work.

## Why

Steps 3–5 make rejected roadmap replies observable, but the existing run-log documentation only describes `attempt_failed`, `gate_violations`, and detail’s parse-failure sidecar. Without a clear operator path and an updated source BUG record, users cannot tell which receipt identifies a rejected reply, whether a sidecar exists, or that the roadmap producer class is complete while other model-backed commands still need migration.

## Input

- **Step 1 sidecar outcome:** Step 1 supplies the shared best-effort sidecar result. Document only its safe disposition and optional path as exposed by the landed receipt contract; do not restate its persistence mechanics.
- **Step 2 receipt contract:** Step 2 supplies the shared redacted run-log event and `RunLogWriter` helper. Read the landed event name and field names from `plan_tool/run_log.py` and `DATA_CONTRACT.md`; the code wins over this plan if names differ.
- **Steps 3–5 producer coverage:** `plan_tool/roadmap.py:_run_stage`, `plan_tool/roadmap.py:_run_bounded_stage_feedback`, and `plan_tool/roadmap_revision_run.py:_run_accepted_revision` define the completed roadmap routes. Describe their coverage without implying that gate-rejection or accepted-response retention changed.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `README.md` — Update the `## Run logs` event list with the landed shared failure receipt and a concise roadmap operator path.
  - `docs/OPERATIONS.md` — Update `## Run logs` with the receipt’s safe fields, how to use its optional sidecar pointer, and the covered roadmap routes.
  - `docs/ARCHITECTURE.md` — Update the `## Roadmap` architecture description to place shared receipt emission with the stage and local-revision producers without changing ownership boundaries.
  - `BUG_BACKLOG.md` — Update `### Model-backed commands do not share one complete terminal failure receipt` to mark the roadmap slice shipped and retain the remaining producer migrations as the live work.
  - `BACKLOG.md` — Update `#217 — Roadmap rejected-response evidence (consolidated)` so its status and links match the shipped roadmap slice and its provenance-only role.

## Implementation

- **Document the receipt as the rejected-reply record.** In `README.md:## Run logs` and `docs/OPERATIONS.md:## Run logs`, add the landed event from `plan_tool/run_log.py:Event` alongside `AttemptFailed`, `GateViolations`, and `ParseFailure`. Explain that it records the producer-owned phase and attempt, failure reason, response byte identity, and sidecar disposition without placing raw response content in JSONL.

- **Give operators one safe lookup path.** Recommend that operators inspect the roadmap run’s JSONL through the existing `plan-tool runs` surface, identify the failure receipt for the relevant phase and attempt, and use its sidecar path only when the receipt reports one. State that a missing, unavailable, or failed sidecar capture remains a valid receipt outcome rather than a command failure.

- **Keep evidence classes separate.** Preserve `RunLogWriter.attempt_failed` as the retry-spending classification and `RunLogWriter.gate_violations` as the structured diagnosis for fresh and bounded stage gate failures. Document a redacted `not-retained` receipt alongside those gate events, correlated by phase and attempt, without implying raw sidecar retention or copied gate messages; the receipt does not replace either existing event.

- **Describe the completed roadmap scope accurately.** In `docs/ARCHITECTURE.md:## Roadmap`, extend the `plan_tool/roadmap.py` and `plan_tool/roadmap_revision_run.py` ownership description to name receipt emission for rejected replies in fresh stage authoring, bounded feedback, and local feedback revision. Keep publication, checkpoint, retry, and result ownership where the existing architecture section assigns it.

- **Record completion without closing the source BUG too broadly.** In `BUG_BACKLOG.md:### Model-backed commands do not share one complete terminal failure receipt`, replace the roadmap slice’s forward-looking implementation wording with a clearly dated shipped-slice record. Retain later producer migrations as the active scope and preserve the existing links to the related backlog items.

- **Keep #217 as provenance only.** In `BACKLOG.md:#217 — Roadmap rejected-response evidence (consolidated)`, align the entry with the source BUG’s shipped roadmap slice. Do not recreate a separate roadmap implementation route, retention policy, reader command, or cross-command completion claim.

## Tests

### Verification (non-code step)

1. **`test_readme_run_log_receipt_matches_data_contract` — Verify the receipt event name and documented safe fields in `README.md:## Run logs` match the landed contract in `DATA_CONTRACT.md` and `plan_tool/run_log.py:Event`.
2. **`test_operations_receipt_lookup_preserves_redaction_boundary` — Verify `docs/OPERATIONS.md:## Run logs` directs operators to an optional receipt-reported sidecar without describing raw response, prompt, validation, transcript, or tool-input content as JSONL fields.
3. **`test_roadmap_producer_coverage_matches_landed_callsites` — Verify the producer routes named in `docs/ARCHITECTURE.md:## Roadmap` match the landed receipt-emission paths in `plan_tool/roadmap.py:_run_stage`, `plan_tool/roadmap.py:_run_bounded_stage_feedback`, and `plan_tool/roadmap_revision_run.py:_run_accepted_revision`.
4. **`test_backlog_slice_status_has_one_live_owner` — Verify `BUG_BACKLOG.md:### Model-backed commands do not share one complete terminal failure receipt` retains later migrations, while `BACKLOG.md:#217 — Roadmap rejected-response evidence (consolidated)` remains provenance and does not offer a duplicate implementation route.
5. **`test_documentation_links_and_headings_resolve` — Check Markdown links and changed heading anchors in `README.md`, `docs/OPERATIONS.md`, `docs/ARCHITECTURE.md`, `BUG_BACKLOG.md`, and `BACKLOG.md`.

## Acceptance criteria

- `README.md:## Run logs` and `docs/OPERATIONS.md:## Run logs` identify the landed shared failure-receipt event and distinguish it from `attempt_failed` and `gate_violations`.
- The operator guidance names phase and attempt as the lookup keys and treats the receipt’s sidecar path as optional diagnostic evidence.
- No updated documentation describes raw response text, prompts, validation prose, provider transcripts, or tool-input summaries as stored in JSONL.
- `docs/ARCHITECTURE.md:## Roadmap` names the three completed roadmap producer routes without assigning retry, publication, checkpoint, or lifecycle ownership to the receipt layer.
- `BUG_BACKLOG.md:### Model-backed commands do not share one complete terminal failure receipt` records the roadmap slice as shipped while retaining later producer migrations.
- `BACKLOG.md:#217 — Roadmap rejected-response evidence (consolidated)` remains a consolidated provenance entry with no independent implementation route.
- Markdown links and changed section anchors resolve, and the documented event names match `plan_tool/run_log.py:Event` at the committed implementation.

## References

- [BUG_BACKLOG.md — “Model-backed commands do not share one complete terminal failure receipt”](BUG_BACKLOG.md) — Read for the shared receipt boundary, completed roadmap slice, and later migrations.
- [BACKLOG.md — #217 “Roadmap rejected-response evidence (consolidated)”](BACKLOG.md) — Read for the retired standalone scope and provenance-only status.
- [DATA_CONTRACT.md — Run log events](DATA_CONTRACT.md#run-log-events-repo-rootplan-toolrunsslugrun_idjsonl) — Read for the landed event schema and redaction boundary.
- [docs/OPERATIONS.md — Run logs](docs/OPERATIONS.md#run-logs) — Update the operator-facing run-log workflow.
- [docs/ARCHITECTURE.md — Roadmap](docs/ARCHITECTURE.md#roadmap) — Update module ownership without changing architectural boundaries.

## Applicable guardrails

- **The plan’s “## Scope guardrails”, redacted terminal receipt** — Keep the documentation focused on safe receipt metadata and optional sidecar availability; do not add any documented raw-JSONL or duplicated gate-diagnostic behavior.
- **The plan’s “## Out of scope”, response retention and retry behavior** — Do not describe this step as adding successful-response persistence, fresh or bounded gate-rejection persistence, retry changes, cleanup, or a diagnostic viewer.
- **The plan’s “## Out of scope”, lifecycle and publication work** — Do not revise documentation to assign roadmap publication, checkpoint, journal, or recovery behavior to the receipt contract.
- **The plan’s “## Scope guardrails”, later producer migrations** — Record only the completed roadmap producer class and retain the remaining migrations under the existing source BUG entry.

## Deferred

- Later model-backed producer migrations — `BUG_BACKLOG.md:### Model-backed commands do not share one complete terminal failure receipt` remains the tracking owner after the roadmap slice ships.
- Retention, cleanup, and a sidecar inspection command — Remain outside this plan’s diagnostic-evidence scope.
- Exception classification, return-code, terminal-status, template-read, and interrupt-lifecycle changes — Remain with the backlog work named by the plan’s scope fence.
