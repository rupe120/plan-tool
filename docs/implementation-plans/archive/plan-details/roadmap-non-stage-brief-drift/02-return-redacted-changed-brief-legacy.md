> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Return redacted changed-brief and legacy-brief impact refusals before evidence publication, preserving guarded recovery and run-log cleanup

## Summary

Make impact-analysis creation return distinct `changed-brief` and `legacy-brief` refusals when step 1’s snapshot baseline check fails. Update `plan_tool/roadmap_impact_run.py`, `plan_tool/run_log.py`, and the exclusive CLI path so both outcomes remain redacted, exit with status `1`, and publish no immutable analysis. Keep guarded recovery, final snapshot recheck, lifecycle ordering, and in-flight run-log cleanup intact. On green, matching briefs keep the current publication path while changed and legacy briefs stop before evidence publication.

## Table of Contents

- [Summary](#summary) — States the completed impact-analysis behavior.
- [Table of Contents](#table-of-contents) — Links to the detail sections.
- [Why](#why) — Explains why impact evidence needs its own brief-drift refusal.
- [Input](#input) — Defines the step 1 snapshot classification and current lifecycle contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — Lists every scoped file and its role.
- [Implementation](#implementation) — Describes the refusal, telemetry, recovery, and CLI boundaries.
- [Tests](#tests) — Names focused coverage for the new outcomes and preserved behavior.
- [Acceptance criteria](#acceptance-criteria) — Lists observable completion checks.
- [References](#references) — Points to the governing route and data contracts.
- [Applicable guardrails](#applicable-guardrails) — Applies the plan’s authority and disclosure limits.
- [Deferred](#deferred) — Records later route and inspection work.

## Why

`plan_tool/roadmap_impact_run.py:_resolve_preflight` currently treats every snapshot failure as a generic `snapshot-rejected` result, even though step 1 makes a changed accepted brief and a legacy unknown baseline distinct states. Impact analysis persists immutable route evidence that includes current brief facts, so it must refuse each state before route resolution or evidence publication without borrowing stage-run admission or baseline-rebind authority.

## Input

- **Step 1 classification:** Use the caller-visible changed-versus-legacy snapshot result from `plan_tool/roadmap_impact_snapshot.py:capture_roadmap_impact_snapshot` and `plan_tool/roadmap_impact_snapshot.py:recheck_roadmap_impact_snapshot`. Step 1 owns the digest comparison and preserves the distinction through recheck.

- **Impact preflight contract:** Preserve `plan_tool/roadmap_impact_run.py:_resolve_preflight`’s receipt-first ordering and `plan_tool/roadmap_impact_run.py:_ImpactPreflight`’s redacted facts.

- **Lifecycle contract:** Keep `plan_tool/run_log.py:RoadmapImpactPreflight`, `plan_tool/run_log.py:RoadmapImpactResult`, and the existing terminal `run_end` call as the only impact lifecycle records.

- **Digest meaning:** Treat `brief_digest` as the decoded-text digest described by `ROADMAP_FORMAT.md:Concept-brief source admission and lifecycle`, `DATA_CONTRACT.md:RoadmapSourceResolved`, and `plan_tool/run_log.py:RoadmapSourceResolved`; do not compare or report it as raw `source.json` or stored-brief bytes.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `plan_tool/roadmap_impact_run.py` — map step 1’s changed and legacy classifications during capture and final recheck to closed impact-analysis refusals, and persist the supported creation command in run-log argv.
  - `plan_tool/run_log.py` — extend the closed impact preflight and terminal vocabularies without adding event fields, and define `RoadmapSourceResolved.brief_digest` as the decoded-text digest.
  - `plan_tool/cli/roadmap_cmd.py` — keep `--analyze-escalation` output limited to the redacted terminal result and its status.
  - `tests/test_roadmap_impact_run.py` — cover initial-capture and final-recheck refusals, recovery ordering, no publication, and cleanup.
  - `tests/test_run_log.py` — cover the new preflight/result vocabulary, fact-prefix rules, and terminal cleanup behavior.
  - `tests/cli/test_roadmap_cmd.py` — cover redacted changed and legacy CLI output and status mapping.
  - `DATA_CONTRACT.md` — document the added closed preflight and terminal values plus their allowed facts, and define `RoadmapSourceResolved.brief_digest` as the decoded-text digest.
  - `ROADMAP_FORMAT.md` — document impact-analysis creation precedence, refusal status, and non-publication boundary.
  - `docs/cli/roadmap.md` — document changed and legacy refusal behavior for `--analyze-escalation`.
  - `tests/test_data_contract.py` — keep the persisted lifecycle documentation aligned with the dataclasses.
  - `tests/test_roadmap_format.py` — keep the impact-analysis reference vocabulary aligned with the landed types and CLI contract.
  - `tests/cli/test_cli_reference.py` — retain the generated CLI-reference drift guard after parser-help and reference regeneration.

## Implementation

- **Foundational logic:** Route step 1’s changed-versus-legacy snapshot classification into impact-analysis-specific `changed-brief` and `legacy-brief` terminal outcomes. These are valid requests that cannot proceed, so they must return status `1`; retain status `2` for `mode-rejected` and `final-rejected` usage failures.

- **Record the supported creation command.** Have `run_roadmap_impact_analysis` persist `--analyze-escalation`, never `--impact-analysis`, in its run-log `argv`. Keep its existing impact-analysis flag metadata, and assert the durable argv uses the command the CLI accepts.

- **Refuse after receipt admission but before route construction.** In `plan_tool/roadmap_impact_run.py:_resolve_preflight`, preserve the named-receipt checks in `_load_requested_receipt`. Once the receipt is admitted, map a changed or legacy snapshot capture to its matching refusal rather than the generic `snapshot-rejected` path. Do not resolve a closure, build an `ImpactAnalysis`, or call `publish_evidence` for either refusal.

- **Preserve the final writer-window check.** In `plan_tool/roadmap_impact_run.py:_run_while_guarded`, recognize the same two classifications when `recheck_roadmap_impact_snapshot` detects a change after an initially matching capture. Return the matching refusal before publication. Other recheck failures must remain the existing generic `invalid` outcome.

- **Do not rewrite durable preflight facts.** A matching capture can already have emitted an `accepted` preflight before the final recheck sees new brief drift. Keep that append as historical lifecycle evidence, then emit the distinct terminal refusal; do not append a compensating preflight event.

- **Keep recovery and guard ownership unchanged.** `run_roadmap_impact_analysis` must still enter `roadmap_writer_guard`, run `recover_roadmap_publication`, and hold the guard across capture, recheck, and any possible publication. A drift refusal must not skip recovery or widen the writer’s authority.

- **Extend closed types, not event shape.** Add `changed-brief` and `legacy-brief` consistently to `ImpactRunLifecycleOutcome`, `ImpactRunCommandOutcome`, `ImpactPreflightVerdict`, `RoadmapImpactPreflight.verdict`, `RoadmapImpactResult.outcome`, and the two `RunLogWriter` validation methods. Keep the existing event field sets unchanged.

- **Keep preflight facts prefix-safe.** The new preflight verdicts occur after a validated receipt but before a captured snapshot. `RoadmapImpactPreflight` may therefore contain the safe receipt group, but must leave snapshot and closure facts null. It must not carry brief text, paths, raw command input, receipt bodies, or new diagnostic fields.

- **Keep refusal result facts empty.** `RoadmapImpactResult` for either refusal must leave `analysis_id`, `route_class`, `publication_outcome`, and `next_workflow` null. The CLI must therefore print only the terminal outcome and status, never an analysis identity, route, publication result, workflow, or requested receipt final.

- **Use the normal terminal path after successful preflight logging.** Route normal changed and legacy refusals through `_persist_terminal` so `RoadmapImpactResult` precedes `RunLogWriter.run_end` and the writer removes only its own in-flight record. Retain `_finish_failed_append` for failed lifecycle appends and keep its no-compensating-event behavior.

- **Keep telemetry failure behavior unchanged.** A failed startup, preflight append, or terminal-result append must not claim a durable impact result. A `run_end` failure after a durable terminal event must return the already durable changed or legacy result, matching the existing cleanup rule.

- **Keep CLI ownership narrow.** `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_impact_analysis` and `_render_impact_analysis_result` must remain thin dispatch and redacted rendering. Do not add a CLI-local baseline check, a rebind path, a source-admission event, or a follow-on command.

- **Document creation only.** Update the impact-analysis creation text in `ROADMAP_FORMAT.md:Impact-routing analyses`, `DATA_CONTRACT.md:RoadmapImpactPreflight`, `DATA_CONTRACT.md:RoadmapImpactResult`, and the `--analyze-escalation` parser help in `plan_tool/cli/roadmap_cmd.py:register`; regenerate `docs/cli/roadmap.md` from that help. Leave log-free inspection status rendering to step 3.

- **Define the source digest once.** Update `DATA_CONTRACT.md:RoadmapSourceResolved` and `RoadmapSourceResolved`’s run-log docstring to state that `brief_digest` is the SHA-256 digest of decoded UTF-8 text. Keep the raw `source.json` and immutable stored-brief digests distinct, and extend their documentation drift tests.

## Tests

- `test_brief_refusal_recovers_under_guard_before_capture_and_never_publishes` — parameterizes changed and legacy refusals, asserting guarded recovery and no analysis record.

- `test_brief_refusal_during_final_recheck_stops_before_evidence_publication` — parameterizes changed and legacy writer-window refusals and leaves no immutable analysis.

- `test_non_brief_snapshot_failure_remains_invalid` — asserts unrelated capture and recheck failures keep the existing `invalid` result.

- `test_brief_refusals_emit_redacted_terminal_lifecycle_and_clean_in_flight` — asserts each refusal writes one allowed preflight/result sequence, emits `run_end`, and removes only its own in-flight snapshot.

- `test_impact_preflight_brief_refusals_stop_after_safe_receipt_facts` — asserts `RoadmapImpactPreflight` accepts both new verdicts only with the receipt prefix and no snapshot or closure facts.

- `test_impact_result_brief_refusals_expose_no_analysis_facts` — asserts both new terminal outcomes reject analysis, route, publication, and workflow values.

- `test_impact_brief_refusal_vocabulary_rejects_unknown_values` — asserts the run-log writers remain closed to unknown preflight and result values.

- `test_analyze_escalation_brief_refusals_render_only_outcome_and_status` — asserts the CLI returns `1`, prints no unsafe requested final, and omits optional analysis fields.

- `test_impact_run_log_records_supported_analyze_escalation_argv` — asserts the persisted impact run argv uses `--analyze-escalation` and never the unsupported spelling.

- `test_impact_analysis_accepts_crlf_brief_digest_written_by_stage_admission` — asserts a matching CRLF baseline emitted by stage admission keeps ordinary impact capture and publication available.

- `test_data_contract_documents_impact_brief_refusal_vocabulary` — asserts the persisted event documentation names both outcomes and their redaction rule.

- `test_source_resolved_digest_contract_uses_decoded_text` — asserts `RoadmapSourceResolved` documentation and its run-log docstring use the one decoded-text meaning.

- `test_impact_analysis_reference_documents_changed_and_legacy_creation_refusals` — asserts `ROADMAP_FORMAT.md` contains every landed impact outcome and the correct status boundary.

- `TestCliReferenceDrift.test_every_generated_file_matches_disk` — asserts the regenerated Roadmap CLI reference matches the landed parser help.

### Tests for this step

Every test above must be green before this step is complete. Run the focused impact-run, run-log, CLI, data-contract, and roadmap-format suites, then run the plan’s full `uv run pytest tests/ -q -n auto` command.

## Acceptance criteria

- A matching accepted brief keeps the existing impact-analysis capture, recheck, and immutable publication behavior.

- A changed recorded brief returns `changed-brief` with status `1` before closure resolution at preflight, or after closure resolution but before evidence publication at final recheck.

- A legacy recorded source returns `legacy-brief` with status `1` before closure resolution at preflight, or after closure resolution but before evidence publication at final recheck.

- A changed or legacy state found only during final recheck returns the same distinct refusal and writes no immutable analysis.

- Both refusal lifecycle records contain only the allowed redacted receipt facts and no analysis, route, publication, workflow, brief-content, or path facts.

- A normal refusal uses the terminal lifecycle path and cleans its own in-flight run-log record without removing a newer run’s snapshot.

- Invalid request syntax remains `preflight-rejected` with status `2`, and unrelated snapshot failures remain `invalid`.

- No impact-analysis refusal emits stage-run source-admission telemetry, changes `source.json`, rebinds a baseline, writes roadmap artifacts, or invokes a backend.

- Impact run provenance records `--analyze-escalation`, and source-resolution documentation defines `brief_digest` only as the decoded-text digest.

- `tests/test_roadmap_impact_run.py`, `tests/test_run_log.py`, `tests/cli/test_roadmap_cmd.py`, `tests/test_data_contract.py`, and `tests/test_roadmap_format.py` pass with the updated contracts.

## References

- [BACKLOG.md closed route-local brief-drift record](../../../../../BACKLOG.md) — Read the route-specific brief-drift authority decision.

- [Roadmap AI-DLC integration delivery handoff](../../../../../handoffs/2026-09-14-roadmap-aidlc-integration-delivery.md) — Read the non-stage writer boundary and delivery order.

- [plan_tool/roadmap_impact_snapshot.py](../../../../../plan_tool/roadmap_impact_snapshot.py) — Read the step 1 capture and recheck classification seam.

- `plan_tool/roadmap_impact_run.py` (source at the plan’s revision) — Read the guarded impact-analysis lifecycle and publication path.

- [DATA_CONTRACT.md](../../../../../DATA_CONTRACT.md) — Read the redacted impact preflight and terminal event contracts.

- [ROADMAP_FORMAT.md](../../../../../ROADMAP_FORMAT.md) — Read impact-analysis evidence, status, and noncanonical-write rules.

## Applicable guardrails

- **The plan’s “## Step intent”:** Limit this work to preventing impact-analysis evidence publication from unaccepted brief text. Do not change another route’s policy.

- **The plan’s “## Out of scope”:** Do not add shared source-admission infrastructure, a non-stage rebind path, stage lifecycle behavior, prompts, stages, or broader rewrite authority.

- **The plan’s “### Contracts and constraints,” digest meaning:** Use the decoded-text baseline comparison from step 1 and keep it separate from raw source-record and immutable stored-brief evidence.

- **The plan’s “### Contracts and constraints,” writer-window rule:** Preserve capture and final recheck under the existing writer guard before the route makes its persisted claim.

- **The plan’s “### Contracts and constraints,” disclosure rule:** Keep results and lifecycle events inside the existing redacted contract; do not add prose, paths, or source content as diagnostics.

## Deferred

- `plan_tool/roadmap_impact_run.py:current_impact_analysis` and `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_impact_analyses_view` — step 3 owns changed and legacy status for the log-free inspection path.

- `plan_tool/roadmap_structural_revision.py` and `plan_tool/roadmap_structural_revision_run.py` — step 4 owns structural-rewrite drift refusals and its separate lifecycle contract.

- `plan_tool/roadmap.py:enroll_roadmap_root` — step 5 owns root-enrollment drift refusals and accepted-head write behavior.

- A generic non-stage source-admission or baseline-rebind mechanism — excluded by the plan’s scope fence because each writer retains its own authority and result contract.
