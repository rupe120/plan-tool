> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Define the qualified audit-result contract

## Summary

Define one internal result decision that classifies every completed completeness audit from explicit facts rather than report wording. Update the completeness finalization and persistence helpers so they preserve the audited plan revision, grade-selected detail revision, and audit stage through pre-apply checkpoints, finalization, reuse checks, and replay checks. The LLM continues to use live project code, history, prompts, lessons, and configuration as context for explaining why an issue matters; this step does not claim that context was frozen or reproducible. On green, every finalization path has one deterministic headline decision without changing the settled stage bars, finding eligibility, or exit-code policy.

## Table of Contents

- [Summary](#summary) — Reviewer-level outcome and the main design choice.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — The gap in today’s separately derived finalization state.
- [Input](#input) — Existing audit, finding, coverage, and persistence inputs.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed by this step.
- [Implementation](#implementation) — Contract, revision capture, and propagation rules.
- [Tests](#tests) — Coverage for the new decision and immutable revision behavior.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Standard-library and test-contract references.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this work.
- [Deferred](#deferred) — Follow-on presentation and authoring work.

## Why

`finalize_completeness_run()` currently combines coverage, blocking findings, and iterate stops in several paths, while `_render_completeness_json()`, report writing, reuse, and replay each receive only part of that state. Fingerprints are also computed when a report is saved, which can describe plan or detail bytes changed by an iterate loop rather than the revision the audit assessed. This step establishes one source for the final result decision and preserves the audited plan/detail revision so later reporting can explain an audit truthfully. The project stays available as live context: the purpose is to explain plan issues in the project, not to pretend every contextual input was captured.

## Input

- **Finalization facts:** Read `_DeterministicReport`, `_IterateOutcome`, `compute_conceptual_bar_blocking_ids()`, `_conceptual_bar_from_audit_recs()`, and `_completeness_finalize_is_clean()` in `plan_tool/cli/completeness_cmd.py` and `plan_tool/cli/completeness_phases.py`.
- **Project context:** Keep the final `_run_deterministic_checks()` battery, optional `_collect_purity_split_findings()` model call, project code, prompts, lessons, configuration, and saved-history inputs available as their existing live context. They explain findings but do not expand the revision that decides whether a saved plan result is current.
- **Finding disposition:** Use `Recommendation`, `is_apply_eligible()`, `partition_findings_for_triage()`, and `triage_reason()` in `plan_tool/review.py` to classify whether deferred work is advisory or still needs a human. Do not change those policies.
- **Coverage evidence:** Read `normalize_audit_coverage()`, `audit_coverage_qualifies_sample()`, and `project_audit_coverage()` in `plan_tool/review_persistence.py`; malformed or legacy-missing evidence must remain distinct from observed incomplete coverage.
- **Revision inputs:** Extend `plan_tool/review_persistence.py:AuditInputSnapshot` into the one grade-aware capture for run and Jira audit plan/detail input. It must retain the captured plan text and every grade-selected detail’s resolution, path, present/missing/unreadable state, and bytes where present. Derive the public plan digest and detail-bundle revision from that capture rather than calling `compute_detail_bundle_fingerprint()` or rereading the selected files later. Keep `compute_plan_fingerprint()` and existing code fingerprints for compatible legacy/report metadata; they do not decide whether a saved plan result is current.
- **Audit-time stage:** Read `derive_audit_stage()` and its pre-loop capture in `plan_tool/cli/completeness_cmd.py`; distinguish it from the post-loop bundle stage recomputed for existing top-level reporting.
- **Saved-audit role:** Treat `plan_tool/review_persistence.py:SavedReview`'s `is_pre_apply_checkpoint` field and `is_reusable_audit_sidecar()` in `plan_tool/completeness_report.py` as the current final-versus-recovery distinction.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/cli/completeness_cmd.py` — Build the final result from explicit facts, capture the audit stage with the sampled plan/detail revision, and reject non-final or stale saved evidence before reuse or replay.
  - `plan_tool/cli/completeness_phases.py` — Extend `_IterateOutcome`, `_sample_conceptual_audit()`, `write_pre_apply_audit_checkpoint()`, and `_persist_and_present_report()` to retain the audit-time plan/detail revision through finalization.
  - `plan_tool/completeness_report.py` — Make `ReusableAudit` and `resolve_reusable_audit()` evaluate audited plan and selected-detail freshness together.
  - `plan_tool/fingerprint.py` — Provide capture-derived plan/detail revision serialization while retaining legacy fingerprint helpers for their existing callers.
  - `plan_tool/review.py` — Accept the grade-aware plan/detail capture in `audit_plan_until_stable()` and use it for every prompt instead of recapturing run grade or live-reading Jira details.
  - `plan_tool/review_persistence.py` — Keep the immutable sampled revision and legacy/final-role state readable without treating absent evidence as current.
  - `tests/cli/test_completeness_cmd.py` — Cover result precedence, iterate-state mapping, replay rejection, and finalization preservation.
  - `tests/test_completeness_report.py` — Cover plan/detail reuse freshness and sampled revision retention at report-write boundaries.
  - `tests/test_review.py` — Cover shared run/Jira capture use in conceptual audit prompts.
  - `tests/test_review_persistence.py` — Cover revision persistence, legacy unknown evidence, and checkpoint role handling.

## Implementation

- **Define one ordered result decision.** Add a small immutable result model and a pure classifier close to `finalize_completeness_run()` in `plan_tool/cli/completeness_cmd.py`. Feed it named facts, not rendered text or missing fields inferred by a reporter.

  - `no-qualified-current-evidence` wins whenever the audit was absent, skipped, failed, audited-revision capture failed, coverage is unconfirmed or legacy-unknown, or the sampled plan/detail revision no longer matches the current selected artifacts. When no audited-revision capture completed, publish `stage`, `coverage`, and `revision_status` as `not-sampled` with `audit_revision: null`; when a fresh capture completed but passes fail or coverage exhausts, retain its captured bare/detail stage and use `unconfirmed` coverage.
  - `awaiting-human-action` follows only for qualified evidence that has a blocking/manual requirement, an early or halted loop exit, `terminal_hand_apply`, `manual_fix_blocking_findings`, or deferred work that is not wholly advisory.
  - `advisory-only` follows when qualified evidence has result-bearing findings but none require action. This includes a bare medium completeness finding left after `converged` or `no_blocking_findings`.
  - `clean` is allowed only when `_completeness_finalize_is_clean()` permits it and no result-bearing finding remains.

- **Treat `all_auto_apply_findings_deferred` as an input, not a result.** Use the deferred finding classes produced by `partition_findings_for_triage()` and the existing structural/apply eligibility facts in `plan_tool/review.py`. It maps to advisory-only only when every remaining finding is explicitly advisory; structural, manually fixable, or material triage deferrals remain awaiting-human-action.

- **Define one result-bearing membership rule.** Centralize the check over the current issue buckets in `_DeterministicReport`, conceptual `Recommendation` values, `path_style_hint`, and dependency issues. Deterministic findings, conceptual findings, and smells that are currently surfaced count toward advisory-only versus clean; audit-shape advice, plan-mass data, coverage metadata, and report notes do not. Use the existing live project context for the final deterministic battery and optional purity model call; do not make access to that context a new qualification gate. Keep `_completeness_has_blocking_findings()` as the existing stage-bar decision rather than widening its threshold.

- **Capture the audited plan/detail revision and stage before result-bearing evaluation starts.** Extend `AuditInputSnapshot.capture()` with a grade argument and make it the only plan/detail capture for a fresh audit. It parses the captured plan text, resolves every selected detail for that grade, and records each selected path, resolution, present/missing/unreadable state, and bytes where present. Derive the persisted plan digest and ordered detail-bundle revision—including absent or unreadable entries—from that object; do not call a separate fingerprint helper or reread disk later. Complete this capture before the conceptual audit begins. A missing selected detail is a captured bare-plan state; if capture never completes, do not infer bare/detail from later disk and return the explicit `not-sampled` qualifiers with null audit revision. Keep the later post-loop bundle stage as a separate top-level view rather than relabeling `qualified_result.stage`.

- **Share the capture with the model’s plan/detail input.** Change `plan_tool/review.py:audit_plan_until_stable()` to accept the grade-aware capture from the completeness command and use its captured plan and selected details for every `render_plan_audit_prompt()` call. It must not construct a second run-grade snapshot or live-read Jira details. The saved audit revision and the prompt’s plan/detail payload therefore have one identity across fresh, reused, iterate, and Jira-grade paths. This does not create a project workspace or constrain code, prompts, lessons, configuration, or history: those remain live explanation context.

- **Keep project context live.** `plan_tool/review.py:audit_plan_until_stable()`, the final `_run_deterministic_checks()` battery, and the optional `--purity` call continue to read the normal project context. That context is how the audit explains the plan’s impact; it is not part of the plan/detail freshness comparison and need not be materialized, sandboxed, or persisted as a reproducible input set.

- **Keep the sampled plan/detail revision immutable through iteration.** Thread the capture through `_sample_conceptual_audit()`, `_IterateOutcome`, `write_pre_apply_audit_checkpoint()`, `finalize_completeness_run()`, `_persist_and_present_report()`, and `write_completeness_report()` in `plan_tool/cli/completeness_phases.py` and `plan_tool/completeness_report.py`. The pre-apply checkpoint and final sidecar must use the same audit-time plan/detail values; do not replace them with values recomputed after `apply_finding()` changes the plan or selected details.

- **Use plan/detail freshness for later qualification.** Extend `ReusableAudit` / `resolve_reusable_audit()` in `plan_tool/completeness_report.py` to require matching plan and grade-selected detail revisions before a saved audit is current or reusable. Make `_resolve_audit_reuse()` and `cmd_completeness_apply()` in `plan_tool/cli/completeness_cmd.py` fail closed for a checkpoint, unknown role, missing revision capture, or changed plan/detail revision and direct the operator to a fresh audit. The same check is the prerequisite for final presentation, replay, authoring handoff, and Step 2’s saved-sidecar consumers.

- **Preserve compatibility and boundaries.** Keep `SavedReview` loading legacy payloads in `plan_tool/review_persistence.py`; their missing coverage or revision evidence is unknown, never clean. Do not add user-facing report prose, the public `qualified_result` JSON object, or a new exit-code rule here—step 2 renders and documents the already-computed contract.

## Tests

### Tests for this step

- `tests/cli/test_completeness_cmd.py:test_qualified_result_no_evidence_overrides_every_stop` — absent, skipped, and pre-capture failures publish `not-sampled` stage/coverage/revision with a null audit revision; completed-but-unconfirmed, legacy-unknown, and stale evidence always select no-qualified-current-evidence with their distinct qualifiers.
- `tests/cli/test_completeness_cmd.py:test_qualified_result_audit_only_mapping` — qualified blocking, advisory-only, and empty audit-only finding sets map to awaiting-human-action, advisory-only, and clean.
- `tests/cli/test_completeness_cmd.py:test_qualified_result_iterate_stop_matrix` — every existing iterate stop, including halted exits, has one mapping without changing its existing return behavior.
- `tests/cli/test_completeness_cmd.py:test_all_auto_apply_deferred_requires_advisory_only_remainder` — structural and material triage deferrals require human action; advisory-only deferrals do not.
- `tests/cli/test_completeness_cmd.py:test_converged_bare_medium_completeness_finding_is_advisory` — a non-blocking result-bearing finding prevents a clean result.
- `tests/cli/test_completeness_cmd.py:test_finalization_persists_the_sampled_revision_after_iteration` — final persistence receives the original audit-time revision rather than post-apply fingerprints.
- `tests/cli/test_completeness_cmd.py:test_final_result_preserves_plan_detail_revision_while_context_stays_live` — final deterministic checks and the optional purity model call retain normal project context while the result preserves the captured plan/detail revision.
- `tests/test_review.py:test_audit_plan_uses_the_supplied_grade_aware_capture` — run and Jira passes render their plan/detail prompt from one caller-supplied capture; a later disk edit cannot change either the prompt payload or persisted revision identity.
- `tests/test_review_persistence.py:test_grade_aware_audit_capture_records_missing_and_unreadable_selected_details` — both grades preserve selected path, resolution, and state in the captured detail revision; missing or unreadable entries cannot disappear from identity.
- `tests/cli/test_completeness_cmd.py:test_qualified_result_stage_is_captured_before_iteration` — a bare sample that gains detail preserves its audit-time stage while existing top-level reporting shows the post-loop stage.
- `tests/cli/test_completeness_cmd.py:test_completeness_apply_rejects_checkpoint_or_stale_sample` — default and explicit saved-audit selection cannot replay non-final or changed evidence.
- `tests/test_completeness_report.py:test_reusable_audit_requires_matching_plan_and_selected_detail` — selected-detail or plan drift makes a saved audit non-current, while a change only to live project context does not rewrite the saved revision.
- `tests/test_completeness_report.py:test_report_writer_keeps_audit_time_fingerprints` — report persistence does not replace sampled fingerprints during finalization.
- `tests/test_review_persistence.py:test_saved_review_preserves_audit_revision_and_legacy_unknown_state` — persisted sampled inputs round-trip while legacy payloads remain readable and unknown.
- `tests/test_review_persistence.py:test_checkpoint_role_is_never_a_final_result` — a confirmed or malformed checkpoint role cannot supply final audit evidence.
- **Green gate:** Every test above and the existing affected test suites must pass before this step is complete.

## Acceptance criteria

- A pure classifier returns exactly one of the four ordered headlines from explicit audit facts, with no-qualified-current-evidence taking precedence over every stop and halt.
- An absent, skipped, or pre-capture failed audit publishes `not-sampled` stage, coverage, and revision qualification with `audit_revision: null`; `unconfirmed` remains the state of a completed fresh sample whose coverage cannot qualify.
- `converged` and `no_blocking_findings` produce clean only when no result-bearing finding remains.
- `all_auto_apply_findings_deferred` produces advisory-only only when every deferred finding is advisory; other deferred classes produce awaiting-human-action.
- Existing stage-bar thresholds, automatic-apply eligibility, and `--fail-on-findings` exit behavior remain unchanged for the same underlying findings.
- A fresh conceptual audit creates one grade-aware capture of its plan and selected-detail revision plus audit stage before result-bearing evaluation starts; that capture supplies both every conceptual prompt’s plan/detail payload and the persisted revision, while project code and other context remain live for the audit’s explanation.
- The pre-apply checkpoint and final report sidecar retain the same sampled plan/detail revision even when iteration changes those artifacts afterward.
- Reuse and completeness replay reject checkpoints, unknown legacy revision evidence, missing revision data, and plan/detail drift with a fresh-audit route.
- Legacy sidecars remain loadable but cannot be treated as qualified current evidence solely because fields are absent.

## References

- [sys — System-specific parameters and functions](https://docs.python.org/3.13/library/sys.html) — Preserve stderr and final process-result behavior while threading the new decision.
- [argparse — Parser for command-line options, arguments and subcommands](https://docs.python.org/3.13/library/argparse.html) — Keep the existing `--fail-on-findings` argument contract intact.
- [json — JSON encoder and decoder](https://docs.python.org/3.13/library/json.html) — Preserve readable, stable persistence behavior for legacy and new audit state.
- [hashlib — Secure hashes and message digests](https://docs.python.org/3.13/library/hashlib.html) — Use the existing SHA-256 identity approach for sampled revisions.
- [How to capture stdout/stderr output](https://docs.pytest.org/en/stable/how-to/capture-stdout-stderr.html) — Pin finalization and backend-output behavior at CLI boundaries.
- [RFC 8259: The JavaScript Object Notation (JSON) Data Interchange Format](https://datatracker.ietf.org/doc/html/rfc8259) — Keep persisted audit values interoperable and explicit about null versus absent state.

## Applicable guardrails

- **The plan’s “## Plan intent”** — derive the result only from deterministic audit facts and keep coverage and revision qualification separate from the headline.
- **The plan’s “## Step intent”** — establish the ordered model, complete finalization mapping, and immutable capture before later steps add presentation language.
- **The plan’s “## Out of scope”** — do not change stage bars, severity policy, pass policy, automatic application, scoring, broad layout, or user disposition decisions.

## Deferred

- **Public report and JSON presentation** — Step 2 renders and documents the shared result model, including the additive machine-readable result object.
- **Data-contract apply integration** — Step 2 updates `plan_tool/cli/data_contract_cmd.py` to consume the final-sidecar rule at its command-specific selection boundary.
- **Create and detail follow-up wording** — Step 3 consumes the qualified final result for authoring handoffs.
