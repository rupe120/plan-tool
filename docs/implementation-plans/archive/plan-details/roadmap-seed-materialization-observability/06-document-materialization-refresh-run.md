> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Document materialization and refresh run phases, outcomes, redaction, and backend-free command boundaries

## Summary

Document the materialization and refresh liveness contract in `README.md`, `DATA_CONTRACT.md`, `TESTING.md`, and `CAPABILITIES.md`. Make the key distinction clear: `--materialize` and `--refresh-seeds` own backend-backed, redacted roadmap runs, while `--apply`, `--accept-seed`, and `--view` retain their separate backend and logging boundaries. Describe source-ordered row phases, plan attribution, terminal outcomes, inactive snapshot state, and the safe test seams without adding a second event schema. On green, operators can interpret seed-action JSONL and `in-flight.json`, and contributors can test these paths without a live backend.

## Table of Contents

- [Summary](#summary) — The documentation outcome and its observable result.
- [Table of Contents](#table-of-contents) — Links to every section in this detail.
- [Why](#why) — The current documentation gap and why it matters.
- [Input](#input) — Contracts supplied by steps 2–5 and the current command boundaries.
- [Files (creates vs edits)](#files-creates-vs-edits) — The four documentation files this step edits.
- [Implementation](#implementation) — The materialization, refresh, redaction, and test guidance to document.
- [Tests](#tests) — Non-code verification using existing contract and roadmap coverage.
- [Acceptance criteria](#acceptance-criteria) — Reviewable documentation completion checks.
- [References](#references) — Primary references for durable records, interrupts, and redaction.
- [Applicable guardrails](#applicable-guardrails) — Scope limits that bind these documentation changes.
- [Deferred](#deferred) — Documentation and observability work left outside this step.

## Why

`CAPABILITIES.md`’s `## Architecture roadmap` says backend work happens only in roadmap stages, but `plan_tool/roadmap.py:materialize_plan_seed()` defaults to `shell_roadmap_invoker` and `refresh_roadmap_seeds()` drives that materializer for each row. `README.md` and `DATA_CONTRACT.md` document stage and apply records but do not explain seed-action phases, attribution, outcomes, or redaction. The existing `CAPABILITIES.md` `## Run state & resumption` section is generic and does not cover this command contract, so operators and test authors lack one accurate description of what these modes do.

## Input

- **Step 2 writer context:** Use the field names and propagation behavior that land in `plan_tool/run_log.py:RunLogWriter`. The landed code is the source of truth if an earlier detail proposed a different name.

- **Step 3 materializer observer:** Document only the safe lifecycle, retry, and failure facts the roadmap-local observer records around `plan_tool/roadmap.py:materialize_plan_seed()`. Keep its content redaction rules separate from the human-facing `RoadmapSeedMaterializeResult.failure_detail`.

- **Step 4 materialize lifecycle:** Document the lifecycle owned by `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_materialize()`, including selected and all-eligible work, no-op handling, source-row phases, and cleanup.

- **Step 5 refresh lifecycle:** Document the lifecycle owned by `plan_tool/roadmap.py:refresh_roadmap_seeds()`, including source-order row processing, independent exhausted-row handling, report grouping, and cleanup.

- **Existing result boundary:** `plan_tool/roadmap.py:RoadmapSeedRefreshResult` and the `SEED_REFRESH_OUTCOME_*` constants remain command-result values. Do not describe those values as the new terminal run-log outcomes.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `README.md` — Add `--materialize` to the roadmap command overview and document the seed-action run-log, snapshot, outcome, and backend-free mode boundaries in `### 0. roadmap` and `## Run logs`.
  - `DATA_CONTRACT.md` — Extend `## Run log events` with the materialization and refresh context, row-phase, retry-counter, outcome, and redaction contract.
  - `TESTING.md` — Extend `## Backend fallback seams` and related guardrails with the fake-invoker recipe and command-boundary guidance for roadmap seed actions.
  - `CAPABILITIES.md` — Correct `## Architecture roadmap` so it distinguishes stage, materialize, refresh, apply, accept, and view behavior without creating a second capability.

## Implementation

- **Make one operator contract the foundational logic.** Document that `plan-tool roadmap <slug> --materialize [PLAN_ID]` and `--refresh-seeds` each create one command-level JSONL record and an active `in-flight.json` snapshot. Point readers to `plan_tool/run_log.py:RunLogWriter.start()`, `RunLogWriter.phase_start()`, `RunLogWriter.phase_end()`, and `RunLogWriter.run_end()` as the contract anchors.

- **Keep materialize and refresh distinct from backend-free modes.** In `README.md` and `CAPABILITIES.md`, state that materialize and refresh call the standalone seed materializer; `--apply` remains backend-free but keeps its existing apply-specific record; `--accept-seed` and `--view` remain backend-free and log-free. Do not imply that every roadmap read creates a run record.

- **Document one source-ordered row phase shape.** Explain that each attempted seed row uses `seed-materialize:<plan-id>` and that both commands follow the `plans` field of `plan_tool/roadmap_artifacts.py:PlansArtifact`, not `PlansArtifact.ordering`. A selected materialization has one requested row; refresh attempts every source-order row.

- **Document attribution as context, not a new event type.** In `DATA_CONTRACT.md`, describe immutable `command: "roadmap"` plus `roadmap_action`, `roadmap_slug`, `requested_plan_id`, and `active_plan_id` as top-level writer context carried by every run record and snapshot. Keep command identity distinct from `roadmap_action`.

- **Define active and inactive plan state precisely.** State that `requested_plan_id` identifies an explicit materialize request, while `active_plan_id` identifies only the row currently being prepared or materialized. A row’s phase end retains its active ID; the immediately following inter-phase snapshot and all terminal records use literal null for inactive row context.

- **Explain the two retry counters without exposing implementation prose.** Define `seed_attempt` as the candidate-seed correction attempt and `backend_attempt` as the child-process attempt within it. State that this pair is authoritative; legacy `attempt` remains the candidate ordinal on materializer events and the child ordinal on child lifecycle events, while recovery `next_attempt` names the next child ordinal. Document literal-null inactive values, the no-child marker, and the rule that a recovery wait stays tied to the child that just failed. Keep the wording tied to step 3’s landed observer rather than prescribing its internal implementation.

- **Publish the closed terminal-outcome table.** Document `completed`, `no-op`, `partial`, `exhausted`, `preflight-refused`, `interrupted`, and `error`; distinguish command preflight/refusal from exhausted backend work and unexpected post-start errors. Preserve the existing user-visible result and exit-code meanings implemented by `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_materialize()` and `_cmd_roadmap_refresh_seeds()`.

- **Make redaction a documented contract.** State that materialization and refresh records may retain lifecycle timing, retry counts, safe failure kind, numeric return code, and aggregate counts. They must not retain prompts, seed bodies, replies, reply heads, validation prose, `failure_detail`, provider transcripts, or tool-input summaries. Keep `_render_seed_refresh_report()` outside that log contract because it remains the human-facing report.

- **Use the existing test seams.** Update `TESTING.md` to direct unit tests to pass `invoker=` to `plan_tool/roadmap.py:materialize_plan_seed()` or `plan_tool/roadmap.py:refresh_roadmap_seeds()`, and CLI tests to pass the injected invoker through `plan_tool/cli/roadmap_cmd.py:cmd_roadmap()`. Require canned, valid seed text and temporary repository roots; do not use a live backend to prove log, phase, outcome, or cleanup behavior.

- **Avoid duplicate schemas.** Keep `DATA_CONTRACT.md`’s `Event`-union rule intact: this documentation describes context and extra fields attached through the writer, not a new event discriminator, run-log schema version, or persisted seed-state schema.

## Tests

This is a non-code step. The test-authoring gate does not apply because the plan marks it `change_type: non-code`; verify the documentation against the already-landed test coverage instead.

### Verification (non-code step)

1. `tests/test_data_contract.py::test_every_persisted_field_is_documented_in_own_section` — Confirms registered run-log event fields remain documented in their `DATA_CONTRACT.md` sections.

2. `tests/test_data_contract.py::test_documented_fields_are_registered_or_aliases` — Confirms the updated event documentation does not name stale registered fields.

3. `tests/test_capability_catalog.py::test_repo_capabilities_doc_is_self_consistent` — Confirms the edited `CAPABILITIES.md` entry remains parseable and valid.

4. `tests/test_roadmap.py` and `tests/cli/test_roadmap_cmd.py` — Run the materialize and refresh lifecycle coverage with fake invokers, confirming the documented command, outcome, ordering, and cleanup rules match behavior without a live backend.

5. Documentation review — Check that `README.md`, `DATA_CONTRACT.md`, and `CAPABILITIES.md` agree that materialize and refresh use backend-backed runs, while apply, accept, and view retain their documented boundaries.

## Acceptance criteria

- `README.md` documents `--materialize [PLAN_ID]` beside `--refresh-seeds` and explains that both produce the roadmap seed-action liveness record.

- `README.md` distinguishes backend-backed materialize and refresh from backend-free apply, accept, and view behavior without claiming that every backend-free mode is log-free.

- `DATA_CONTRACT.md` documents the materialize and refresh context fields, source-ordered `seed-materialize:<plan-id>` phases, inactive null state, retry counters, terminal outcomes, and redaction boundary.

- `DATA_CONTRACT.md` does not describe the materialization context as a new `Event` discriminator or a new `seed-state.json` schema.

- `CAPABILITIES.md` no longer states that backend work occurs only in roadmap stages and accurately describes the materialize and refresh lifecycle boundary.

- `TESTING.md` names an explicit fake-invoker path for direct and CLI-level materialization and refresh tests, and tells contributors not to use a live backend.

- `uv run pytest tests/test_data_contract.py tests/test_capability_catalog.py tests/test_roadmap.py tests/cli/test_roadmap_cmd.py -q` passes.

## References

- [JSON Lines Format](https://jsonlines.org/) — Use for the durable, independently readable JSONL record contract.

- [Python signal — Asynchronous Event Handlers](https://docs.python.org/3.13/library/signal.html#general-rules) — Use for the documented Ctrl-C and `KeyboardInterrupt` boundary.

- [OWASP Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html) — Use for the redaction and sensitive-data exclusion rules.

## Applicable guardrails

- **The plan’s “## Plan intent”, durable liveness contract:** Document only the roadmap materialize and refresh record, snapshot, attribution, and cleanup behavior supplied by the earlier steps.

- **The plan’s “## Step intent”, operator and contributor alignment:** Keep this step documentary; do not change command behavior, event production, or test fixtures.

- **The plan’s “## Out of scope”, seed behavior and reports:** Do not present documentation as changing prompt content, validation, retries, seed state, paths, promotion, or refresh-report behavior.

- **The plan’s “## Out of scope”, limited observability rollout:** Keep the described lifecycle limited to roadmap materialization and refresh rather than presenting it as a generic backend policy.

- **The plan’s “## Out of scope”, durable data:** State the redaction boundary clearly and do not normalize content-bearing values as acceptable diagnostic fields.

## Deferred

- Detailed lifecycle prose in `docs/cli/roadmap.md` — That option reference is outside this step’s declared file set; keep the full run-log contract in `README.md` and `DATA_CONTRACT.md` unless a later plan changes the reference’s role.

- Provider transcripts, monitoring commands, and broader backend-observability documentation — The plan’s scope fence reserves those surfaces for separate work.
