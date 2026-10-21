> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Require confirmation before replacing changed or legacy source.json

## Summary

Add a confirmation-aware `run_roadmap` admission boundary in `plan_tool/roadmap.py` and cover it in `tests/test_roadmap.py`. A changed or legacy baseline at the recorded path must remain refused unless the caller supplies the new boolean confirmation input. The input is a no-op for initial recording and matching-baseline runs, which retain their existing behavior and gain no rebind authority. On green, an unconfirmed refusal occurs before recovery, source replacement, artifact work, seed work, or backend invocation.

## Table of Contents

- [Summary](#summary) — The completed behavior at a glance.
- [Table of Contents](#table-of-contents) — Links to each major section.
- [Why](#why) — Why repeated source paths need separate consent.
- [Input](#input) — The source and lifecycle contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — The exact source and test files changed.
- [Implementation](#implementation) — The confirmation predicate, ordering, and preserved behavior.
- [Tests](#tests) — Focused admission and no-write coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Source-admission contracts and plan scope.
- [Applicable guardrails](#applicable-guardrails) — Boundaries that constrain this step.
- [Deferred](#deferred) — CLI and documentation work owned later.

## Why

`plan_tool/roadmap.py:_run_roadmap` currently promotes a same-path `refused-changed` or `refused-legacy` admission to `accepted-rebind` whenever `brief_path` is present. A repeated path identifies the source but does not prove consent to replace its recorded decoded-text baseline. This step makes consent an explicit input while retaining the existing narrow, baseline-only rebind route.

## Input

- **Recorded source identity:** `plan_tool/roadmap.py:_resolve_brief_path` and `plan_tool/roadmap_source.py:RecordedBriefSource` establish whether an explicit path is the recorded source and expose the accepted digest.

- **Admission lifecycle:** `plan_tool/roadmap.py:_run_roadmap` emits the existing `refused-changed`, `refused-legacy`, and `accepted-rebind` dispositions through `plan_tool/run_log.py:RoadmapSourceAdmissionDisposition`. Keep those values and their redaction boundary.

- **Initial recording:** `plan_tool/roadmap.py:_write_brief_source` remains tied to `record_brief_source` after the first successful `publish_stage_artifact` call. Confirmation must not create or move that first-recording path.

- **Existing rebind result:** `plan_tool/roadmap.py:RoadmapResult` already exposes `baseline_rebound` to separate a successful baseline replacement from ordinary stage effects. Retain that result contract.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/roadmap.py` — Add the confirmation-aware stage-run input, gate same-path changed and legacy rebinds on it, and ensure refusal happens before any mutable recovery or stage route.
  - `tests/test_roadmap.py` — Update positive rebind cases to supply confirmation and add refusal, ordering, and unchanged-route coverage.

## Implementation

- **Foundational logic:** add a confirmation-gated source-admission predicate. A changed or legacy baseline may reach `_write_brief_source` only when the caller supplied both the already-validated same recorded `brief_path` and explicit rebind confirmation.

- **Keep the public API additive:** add a keyword-only `confirm_brief_rebind: bool = False` input to `plan_tool/roadmap.py:run_roadmap` and pass it to `_run_roadmap`. The false default must preserve existing callers that do not have rebind authority.

- **Use the existing source facts:** keep `_resolve_brief_path` as the authority for same-path identity and keep the existing decoded-text digest comparison as the authority for `refused-changed` and `refused-legacy`. Do not add semantic comparison, brief-quality checks, or a second source parser.

- **Require both conditions for a rebind:** only turn a refusal into `accepted-rebind` when the baseline needs replacement, the supplied path is the recorded path, and `confirm_brief_rebind` is true. Do not infer confirmation from a repeated path.

- **Keep unconfirmed refusals fail-closed:** with a changed or legacy recorded baseline and no confirmation, retain the existing refusal disposition, `RoadmapPreflightFailed(check="brief_source")`, redacted error shape, and result-to-exit-code path. Do not update `source.json`, set `baseline_rebound`, or produce a replacement result.

- **Put admission before mutable recovery:** perform the source-admission decision before `plan_tool/roadmap_revision_publish.py:recover_roadmap_publication`, because recovery can change a recorded generation. The refusal path must also stay ahead of artifact loading, `publish_stage_artifact`, seed-state writes, draft or promoted seed work, and the stage invoker. Keep writer ownership and unenrolled-roadmap checks intact.

- **Preserve confirmed behavior exactly:** when confirmation is present, retain the existing `_write_brief_source` atomic replacement, `accepted-rebind` lifecycle event, and `baseline_rebound=True` result fact. The successful baseline write must remain separate from later ordinary feedback, stage, artifact, and seed behavior.

- **Keep unaffected admissions unchanged:** a matching recorded digest must continue through ordinary processing without rebinding even when confirmation is true. An initial source must still be recorded only after its first successful artifact publication when confirmation is true. A different explicit path must remain rejected by `_resolve_brief_path`, even when confirmation is true.

- **Keep this non-interactive:** this module accepts only the boolean input. Do not add a prompt, TTY check, generic confirmation helper, new lifecycle disposition, or changed exit-code convention.

## Tests

### Tests for this step

- `test_unconfirmed_same_path_changed_digest_refuses_before_recovery_or_writes` — An explicit recorded path with changed text and no confirmation keeps source, artifact, and seed bytes unchanged; reaches neither recovery nor the invoker; and emits a redacted `refused-changed` admission before the brief-source preflight failure.

- `test_unconfirmed_same_path_legacy_record_refuses_before_recovery_or_writes` — A path-only legacy record with an explicit same path and no confirmation preserves all durable state, skips recovery and backend work, and emits the redacted `refused-legacy` admission.

- `test_same_path_changed_digest_rebinds_before_feedback_free_reentry` — Update the existing positive changed-baseline case to pass `confirm_brief_rebind=True` and retain its source-only replacement and accepted-rebind assertions.

- `test_same_path_legacy_record_rebinds_before_artifact_admission` — Update the legacy positive case to pass confirmation and prove the digest is recorded before ordinary artifact admission.

- `test_same_path_rebind_continues_the_open_feedback_route` — Update the open-feedback positive case to pass confirmation and retain the ordinary feedback route after the baseline-only write.

- `test_rebind_replaces_only_source_before_ordinary_processing` — Update the source-isolation case to pass confirmation and retain its artifact and seed byte checks at the source-write boundary.

- `test_rebind_confirmation_keeps_different_path_refused` — A confirmation input cannot bypass `plan_tool/roadmap.py:_resolve_brief_path` for a different explicit brief path.

- `test_rebind_confirmation_is_noop_for_initial_recording` — A true confirmation input leaves initial recording tied to the first successful stage publication and does not become an early rebind write.

- `test_rebind_confirmation_is_noop_for_matching_baseline` — A true confirmation input leaves a matching baseline as a normal re-entry with `baseline_rebound=False`.

- `test_rebind_write_failure_is_a_source_preflight_error` — Update the write-failure case to pass confirmation and retain the existing no-admission-event failure behavior.

- `test_rebind_precedes_a_reported_upstream_preflight_failure` — Update the positive rebind ordering case to pass confirmation and retain source acceptance before later preflight reporting.

- `test_rebind_precedes_a_reported_stage_render_failure` — Update the stage-render failure case to pass confirmation and retain the accepted-baseline context on the later error.

Every listed test must be green before this step is complete.

## Acceptance criteria

- `plan_tool/roadmap.py:run_roadmap` accepts an explicit boolean confirmation input whose default is false.

- An explicit same path with a changed or legacy baseline and no confirmation raises the existing refusal before recovery, source replacement, artifact loading, seed work, or backend invocation.

- An unconfirmed refusal leaves `source.json`, roadmap artifacts, draft seeds, promoted seeds, and seed state unchanged.

- A confirmed same-path changed or legacy baseline retains the existing atomic source-only rebind, `accepted-rebind` lifecycle disposition, and `baseline_rebound=True` result fact.

- Matching and initial admissions retain their current behavior with either confirmation value and do not gain rebind authority; a different path remains refused even when confirmation is true.

- `uv run pytest tests/test_roadmap.py -q` passes.

## References

- [Roadmap Brief Rebind Confirmation plan](../../2-roadmap-brief-rebind-confirmation.md) — Read the step boundary and the confirmation authority matrix.

- [BACKLOG.md](../../../../BACKLOG.md) — Read #367’s confirmed consent decision and scope contract.

- [ROADMAP_FORMAT.md](../../../../ROADMAP_FORMAT.md#concept-brief-source-admission-and-lifecycle) — Read the source-admission ordering and baseline-only lifecycle rules.

- [DATA_CONTRACT.md](../../../../DATA_CONTRACT.md#roadmap-source-admission-lifecycle-event) — Read the redacted source-admission event contract.

## Applicable guardrails

- **The plan’s “## Scope guardrails”, admission condition:** Limit `plan_tool/roadmap.py` to the boolean confirmation and existing source path and digest facts.

- **The plan’s “## Scope guardrails”, non-interactive behavior:** Do not add an interactive or inferred-consent route in the stage runner.

- **The plan’s “## Scope guardrails”, narrow implementation:** Do not add shared confirmation infrastructure, a new source model, a stage, a Integration mutation, or an exit-code change.

- **The plan’s “## Out of scope”, roadmap meaning:** Do not re-ground, regenerate, reconcile, or semantically validate existing roadmap artifacts as part of a confirmed baseline replacement.

- **The plan’s “## Out of scope”, ordinary routes:** Keep matching-baseline stage runs and non-stage writer policy unchanged.

## Deferred

- `plan_tool/cli/roadmap_cmd.py:cmd_roadmap` and `plan_tool/cli/roadmap_cmd.py:register` — Step 2 owns parsing and forwarding `--confirm-brief-rebind`, plus rejection of non-stage uses.

- `ROADMAP_FORMAT.md`, `DATA_CONTRACT.md`, and operator guides — Step 3 owns documentation for the confirmed and unconfirmed lifecycle wording.

- Confirmation for any other roadmap authority — Keep it outside this focused source-admission change; record separate evidence-backed work if needed.
