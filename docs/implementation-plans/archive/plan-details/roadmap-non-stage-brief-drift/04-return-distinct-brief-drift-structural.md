> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Return distinct brief-drift structural refusals after evaluator admission and guarded recovery

## Summary

Make structural rewrite return `changed-brief` and `legacy-brief` when step 1 rejects the snapshot baseline. Update `plan_tool/roadmap_structural_revision.py`, `plan_tool/roadmap_structural_revision_run.py`, `plan_tool/run_log.py`, and the structural CLI result mapping without adding a new writer path. Preserve evaluator-first admission, guarded recovery, final publication recheck, and journal cleanup. On green, matching briefs retain the existing rewrite path while changed and legacy briefs return redacted status `1` results with no artifact, baseline, or seed update.

## Table of Contents

- [Summary](#summary) — States the completed structural-rewrite behavior.
- [Table of Contents](#table-of-contents) — Lists the detail sections in reading order.
- [Why](#why) — Explains why structural publication needs its own drift refusal.
- [Input](#input) — Defines the step 1 snapshot classification and writer-window inputs.
- [Files (creates vs edits)](#files-creates-vs-edits) — Lists every scoped edit.
- [Implementation](#implementation) — Describes refusal routing, lifecycle facts, and recovery boundaries.
- [Tests](#tests) — Names focused behavior and regression coverage.
- [Acceptance criteria](#acceptance-criteria) — Lists observable completion conditions.
- [References](#references) — Links to the route and contract sources.
- [Applicable guardrails](#applicable-guardrails) — Applies the plan’s authority, digest, and disclosure limits.
- [Deferred](#deferred) — Records adjacent work outside this step.

## Why

`plan_tool/roadmap_structural_revision.py:load_structural_revision_preflight` currently flattens every snapshot failure into generic non-current evidence, so structural rewrite cannot tell an unaccepted changed brief from an unknown legacy baseline. This route can atomically replace a selected artifact, its baseline sidecar, and seed state, so it must stop on either state before it can publish a proof-backed claim.

## Input

- **Step 1 classification:** Consume step 1’s caller-visible changed and legacy failures from `plan_tool/roadmap_impact_snapshot.py:capture_roadmap_impact_snapshot` and `plan_tool/roadmap_impact_snapshot.py:recheck_roadmap_impact_snapshot`.

- **Structural preflight:** Preserve `plan_tool/roadmap_structural_revision.py:load_structural_revision_preflight` as the exact-pair, snapshot, and selected-feedback binding owner.

- **Guarded publication:** Preserve `plan_tool/roadmap_structural_revision_run.py:run_structural_revision` ordering and `plan_tool/roadmap_revision_publish.py:publish_structural_revision_proof`’s final call back into structural preflight.

- **Digest meaning:** Treat `brief_digest` only as step 1’s decoded UTF-8 text baseline. Do not report or compare raw `source.json` bytes or stored-brief bytes as the accepted baseline.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `plan_tool/roadmap_structural_revision.py` — preserve step 1’s changed and legacy classifications through initial capture and recheck instead of collapsing them into generic evidence failure.
  - `plan_tool/roadmap_structural_revision_run.py` — map the distinct preflight and final-recheck failures to closed structural outcomes and status behavior, and persist the supported structural-rewrite command in run-log argv.
  - `plan_tool/run_log.py` — add the closed preflight verdicts and final-attempt outcomes without adding event fields.
  - `plan_tool/cli/roadmap_cmd.py` — keep structural result rendering redacted, map valid brief refusals to status `1`, and update the parser help that generates the CLI reference.
  - `tests/test_roadmap_structural_revision.py` — cover initial capture and recheck classification at the structural preflight boundary.
  - `tests/test_roadmap_structural_revision_run.py` — cover evaluator and recovery ordering, no backend work, final-recheck outcomes, publication preservation, and run-log cleanup.
  - `tests/test_run_log.py` — cover the expanded closed vocabulary, fact matrix, phase matrix, and no-newer-snapshot cleanup rule.
  - `tests/cli/test_roadmap_cmd.py` — cover redacted output and exit-status mapping for both refusals.
  - `DATA_CONTRACT.md` — document the added structural preflight and attempt values with their allowed facts.
  - `ROADMAP_FORMAT.md` — document changed and legacy structural refusal precedence and the closed vocabularies.
  - `docs/cli/roadmap.md` — regenerate the structural-rewrite option reference from the updated parser help.
  - `tests/test_data_contract.py` — keep persisted structural lifecycle documentation aligned with the dataclasses.
  - `tests/test_roadmap_format.py` — keep the exact-pair reference markers and redaction contract aligned with landed values.
  - `tests/cli/test_cli_reference.py` — verify generated CLI text includes the distinct brief-drift behavior.

## Implementation

- **Foundational logic:** Route step 1’s changed-versus-legacy snapshot classification into structural-rewrite-specific `changed-brief` and `legacy-brief` refusals.

- **Record the supported structural command.** Have `run_structural_revision` persist `--rewrite-structural`, never `--structural-revision`, in its durable run-log `argv`, and assert that provenance uses the command the CLI accepts.

- **Preserve the existing admission order.** `plan_tool/roadmap_structural_revision_run.py:run_structural_revision` must reject malformed mode input before evaluator work, reject an unavailable evaluator without reading evidence, then run `recover_roadmap_publication` under `roadmap_writer_guard` before structural preflight can return either brief refusal.

- **Keep changed and legacy distinct at structural preflight.** `plan_tool/roadmap_structural_revision.py:load_structural_revision_preflight` must catch step 1’s two dedicated snapshot failures before its broad `RoadmapImpactSnapshotError` handling. It must expose stable structural-preflight failures that preserve the category without carrying source text, paths, or evidence bodies.

- **Do not broaden the snapshot contract.** `load_structural_revision_preflight` must retain generic evidence rejection for malformed sources, unrelated snapshot failures, stale identities, invalid evidence pairs, and `requires-scope-review`. Only a valid-but-different decoded brief and a valid legacy record receive the new outcomes.

- **Keep initial refusal facts minimal.** A changed or legacy failure occurs after the requested receipt and analysis finals are known but before snapshot selection and canonical binding. `RoadmapStructuralRevisionPreflight` must retain only the safe final pair, with selection, target, binding, and canonicality facts null. It must not emit `RoadmapStructuralRevisionAttempt`.

- **Keep command validity separate from refusal status.** `plan_tool/roadmap_structural_revision_run.py:structural_revision_result_return_code` must return status `1` for `changed-brief` and `legacy-brief`, because both name valid requests that cannot proceed. Invalid pair cardinality and incompatible modes must retain status `2`; successful publication remains `0`, and interruption remains `130`.

- **Preserve final-recheck distinction.** `plan_tool/roadmap_revision_publish.py:publish_structural_revision_proof` already re-enters `load_structural_revision_preflight` before replacement and wraps failures as `StaleStructuralRevisionPublicationError`. Reuse that contract unchanged. In `plan_tool/roadmap_structural_revision_run.py:_run_accepted_structural_revision`, recognize a controlled changed or legacy cause from that final-recheck path and return the matching terminal outcome instead of flattening it to `final-snapshot-stale`.

- **Keep failed-recheck cleanup intact.** The final recheck must still run after `publish_roadmap_generation` records its pending generation and before it replaces members. A changed or legacy final recheck must leave the artifact, baseline sidecar, seed-state file, and pending-generation journal unchanged or removed according to the existing failed-recheck cleanup rule.

- **Extend values, not event shape.** Add both terms to `RoadmapStructuralRevisionPreflight.verdict`, `RoadmapStructuralRevisionAttempt.outcome`, `RunLogWriter.roadmap_structural_revision_preflight`, `RunLogWriter.roadmap_structural_revision_attempt`, and their validation helpers. Do not add fields, disclose diagnostics, or change `RUN_LOG_SCHEMA_VERSION`.

- **Keep final attempt phases truthful.** A changed or legacy result found after accepted preflight must record the existing accepted operation, merge, and proof prefix; record final snapshot as stale and publication as not reached. It must retain a null invalidated-seed count.

- **Use the existing terminal cleanup path.** `run_structural_revision` must always call `RunLogWriter.run_end` through its existing `finally` block. A brief refusal must remove only its own in-flight snapshot and must not remove a newer same-slug run’s snapshot.

- **Keep CLI rendering thin.** `plan_tool/cli/roadmap_cmd.py:_render_structural_rewrite_result` must print only `structural rewrite: changed-brief` or `structural rewrite: legacy-brief`. It must not print finals, artifact paths, seed counts, brief text, source paths, or a recovery command.

- **Update the local contract docs together.** Update `ROADMAP_FORMAT.md:Exact-pair structural rewrite`, `DATA_CONTRACT.md:RoadmapStructuralRevisionPreflight`, `DATA_CONTRACT.md:RoadmapStructuralRevisionAttempt`, and the `--rewrite-analysis` help in `plan_tool/cli/roadmap_cmd.py:register`. Regenerate `docs/cli/roadmap.md`; do not update broader operator guides in this step.

## Tests

- `test_structural_preflight_preserves_brief_refusal_before_selected_slice` — parameterizes changed and legacy decoded-text baseline refusals before selected-feedback resolution and without input mutation.

- `test_structural_preflight_preserves_brief_refusal_from_final_recheck` — parameterizes final-recheck changed and legacy refusals after selected-feedback resolution but before publication.

- `test_structural_runner_recovers_before_brief_refusal_without_backend_work` — parameterizes both baseline refusals after evaluator admission and guarded recovery while backend invocation and publication remain unreachable.

- `test_structural_final_changed_brief_recheck_returns_distinct_outcome_and_cleans_journal` — asserts late changed drift returns `changed-brief`, preserves artifact, baseline, and seed bytes, and removes the failed-recheck journal.

- `test_structural_final_legacy_brief_recheck_returns_distinct_outcome_and_cleans_journal` — asserts the same writer-window preservation for a newly legacy record.

- `test_structural_non_brief_snapshot_failure_remains_evidence_or_stale_rejection` — asserts unrelated snapshot failures retain their existing generic route result.

- `test_structural_brief_refusals_emit_only_allowed_events_and_clean_own_in_flight_snapshot` — asserts initial refusals emit one redacted preflight plus `run_end`, no attempt, and preserve a newer run’s snapshot.

- `test_structural_preflight_brief_refusals_require_only_safe_final_pair` — asserts both new preflight values reject selection, target, binding, canonicality, and diagnostic facts.

- `test_structural_attempt_brief_refusals_require_final_stale_phase_prefix` — asserts both late outcomes accept only the completed pre-publication phase tuple and null seed count.

- `test_structural_run_log_rejects_unknown_brief_refusal_values_and_content` — asserts the lifecycle writer remains closed to unlisted values and extra sensitive fields.

- `test_structural_rewrite_brief_refusals_render_redacted_output_with_status_one` — asserts each CLI result returns `1` and omits requested finals and optional publication fields.

- `test_structural_run_log_records_supported_rewrite_structural_argv` — asserts durable structural-rewrite provenance uses `--rewrite-structural`, never the unsupported spelling.

- `test_structural_rewrite_accepts_crlf_brief_digest_written_by_stage_admission` — asserts a matching CRLF baseline emitted by stage admission remains eligible for ordinary structural preflight.

- `test_data_contract_documents_structural_brief_refusal_vocabulary` — asserts both persisted sections document the added values and their fact rules.

- `test_structural_rewrite_reference_documents_changed_and_legacy_refusals` — asserts the `ROADMAP_FORMAT.md` markers cover every landed preflight and attempt value.

- `test_roadmap_reference_documents_structural_brief_refusals` — asserts generated `docs/cli/roadmap.md` retains the evaluator boundary and describes both distinct refusals.

### Tests for this step

Every listed test must be green before this step is complete. Run `uv run pytest tests/test_roadmap_structural_revision.py tests/test_roadmap_structural_revision_run.py tests/test_run_log.py tests/cli/test_roadmap_cmd.py tests/test_data_contract.py tests/test_roadmap_format.py tests/cli/test_cli_reference.py -q`, then run `uv run pytest tests/ -q -n auto`.

## Acceptance criteria

- A matching accepted brief retains the current structural preflight, evaluator, proof, publication, and seed-invalidation behavior.

- A changed recorded brief returns `changed-brief` with status `1` after evaluator admission and guarded recovery, before backend work or publication.

- A legacy recorded source returns `legacy-brief` with status `1` under the same ordering and write boundary.

- A changed or legacy state first found during final guarded recheck returns the same distinct terminal outcome with stale final-snapshot facts and no seed count.

- Initial brief refusals retain only the allowed final-pair facts, emit no structural attempt, and disclose no brief text, path, receipt body, analysis body, prompt, reply, or exception text.

- Final brief refusals leave artifact, baseline, and seed-state bytes unchanged and preserve failed-recheck pending-generation cleanup.

- Malformed command forms remain status `2`; evaluator rejection remains fact-free; unrelated snapshot failures retain their existing generic behavior.

- No brief refusal updates `source.json`, rebinds a baseline, emits stage-run source-admission telemetry, widens rewrite authority, or invokes a backend.

- Structural-rewrite run-log provenance records `--rewrite-structural`, and a matching CRLF stage-admission digest remains eligible for its ordinary path.

- `tests/test_roadmap_structural_revision.py`, `tests/test_roadmap_structural_revision_run.py`, `tests/test_run_log.py`, `tests/cli/test_roadmap_cmd.py`, `tests/test_data_contract.py`, `tests/test_roadmap_format.py`, and `tests/cli/test_cli_reference.py` pass.

## References

- [BACKLOG.md closed route-local brief-drift record](../../../../../BACKLOG.md) — Defines the route-specific non-stage brief-drift scope.

- [Roadmap AI-DLC integration delivery handoff](../../../../../handoffs/2026-09-14-roadmap-aidlc-integration-delivery.md) — Defines the non-stage writer and Integration scope fence.

- [plan_tool/roadmap_impact_snapshot.py](../../../../../plan_tool/roadmap_impact_snapshot.py) — Provides the step 1 capture and recheck seam.

- `plan_tool/roadmap_structural_revision.py` (source at the plan’s revision) — Owns exact-pair structural preflight.

- `plan_tool/roadmap_structural_revision_run.py` (source at the plan’s revision) — Owns evaluator ordering, terminal results, and run-log completion.

- [DATA_CONTRACT.md](../../../../../DATA_CONTRACT.md) — Defines the persisted redacted structural lifecycle.

- [ROADMAP_FORMAT.md](../../../../../ROADMAP_FORMAT.md) — Defines exact-pair rewrite authority and operator-facing route rules.

## Applicable guardrails

- **The plan’s “## Step intent”:** Limit changes to structural rewrite’s changed and legacy brief policy; do not change another route’s policy.

- **The plan’s “## Out of scope”:** Do not add source-admission infrastructure, a non-stage rebind, prompts, stages, semantic re-grounding, or broader rewrite authority.

- **The plan’s “### Contracts and constraints,” digest meaning:** Use only step 1’s decoded-text comparison and keep raw source and stored-brief evidence separate.

- **The plan’s “### Contracts and constraints,” writer-window rule:** Preserve capture and final recheck under the existing writer guard before any persisted structural claim.

- **The plan’s “### Contracts and constraints,” disclosure rule:** Keep results, lifecycle records, and CLI output within the current redacted structural contract.

## Deferred

- `plan_tool/roadmap_impact_run.py` — steps 2 and 3 own impact-analysis creation and inspection outcomes.

- `plan_tool/roadmap.py:enroll_roadmap_root` — step 5 owns root-enrollment brief refusals and accepted-head write behavior.

- `plan_tool/roadmap_revision_publish.py:publish_structural_revision_proof` and `plan_tool/roadmap_revision_publish.py:publish_roadmap_generation` — reuse the existing final-recheck wrapper and journal cleanup without changing publication protocol.

- Broad operator-guide updates and BACKLOG.md closure — step 6 owns the public documentation sweep after all three route policies land.

- A generic non-stage admission or rebind mechanism — excluded by the plan’s scope fence because structural rewrite retains its own authority and result contract.
