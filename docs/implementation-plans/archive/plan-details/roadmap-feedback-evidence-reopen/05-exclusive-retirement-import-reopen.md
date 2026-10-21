# Step 5 — Add exclusive retirement import, reopen, and recovery CLI modes with a safe review view

## Summary

Add four exclusive `roadmap` actions in `plan_tool/cli/roadmap_cmd.py`: retirement-record creation, documented archive import, controlled feedback reopen, and reopen-attempt recovery. Route each action to the services delivered by steps 2 and 4, leaving evidence validation, artifact publication, and log recovery outside the CLI. Extend `plan_tool/roadmap_view.py:render_decision_ledger()` so review mode shows redacted reopen history while current mode continues to hide feedback. On green, every trust boundary requires its dedicated flag, output contains only safe facts, and the CLI catalog, documentation, capability entry, and help snapshot agree.

## Table of Contents

- [Summary](#summary) — The completed CLI and review behavior.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — The missing operator workflow.
- [Input](#input) — Upstream contracts and current CLI boundaries.
- [Files (creates vs edits)](#files-creates-vs-edits) — Scoped code, documentation, and tests.
- [Implementation](#implementation) — Exclusive dispatch, safe rendering, and review rules.
- [Tests](#tests) — Focused CLI and view coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Parser reference for the command surface.
- [Applicable guardrails](#applicable-guardrails) — Boundaries that constrain this step.
- [Deferred](#deferred) — Work outside the bounded recovery surface.

## Why

`plan_tool/cli/roadmap_cmd.py:cmd_roadmap()` has exclusive paths for receipts, impact analyses, structural rewrites, and local revisions, but operators cannot create the retirement record, reopen an admitted response, or recover its terminal event without bypassing those boundaries. `plan_tool/roadmap_view.py:_render_pending_feedback()` shows normal review context only, so a completed reopen has no safe operator-facing explanation. This step makes the landed recovery path usable and auditable without exposing prior response text or widening ordinary feedback actions.

## Input

- **Step 2 retirement contract:** Use the landed `plan_tool/roadmap_evidence_retirement.py` public services for retirement-record creation, documented archive import, and closed invalidation results. A reopen uses `--retirement-record FINAL` only for `retired`, or `--receipt-final FINAL` only for unreadable or invalid active evidence; its landed argument and result names win over this detail. The CLI must not reproduce root checks or classification rules.

- **Step 4 reopen contract:** Use the landed `plan_tool/roadmap_feedback_reopen_run.py` service for controlled reopen and attempt recovery. It owns publication, final rechecks, terminal-log recovery, and closed outcomes.

- **Existing exclusive-mode boundary:** Build on `plan_tool/cli/roadmap_cmd.py:cmd_roadmap()`, `_TrackEscalationOption`, `_option_occurrences()`, `_broad_mode_companions_present()`, and the existing `*_has_conflict()` predicates. Direct callers use hand-built namespaces through the `_ns()` test helper, so parser-only checks are insufficient.

- **Review data boundary:** Step 4 persists the redacted reopen history on `plan_tool/roadmap_artifacts.py:FeedbackRow`. Keep `plan_tool/roadmap_view.py:load_roadmap()` as the loader and use only the parsed row state it returns.

- **Package-help contract:** `plan_tool/cli/app.py:build_parser()` uses the package docstring in `plan_tool/cli/__init__.py`, and `tests/cli/test_package_surface.py:TestHelpGoldenSnapshot.test_help_matches_golden` checks its rendered output.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/cli/roadmap_cmd.py` — Add the new option forms, occurrence-aware exclusivity checks, thin service dispatch, and redacted terminal rendering.
  - `plan_tool/cli/__init__.py` — Add the four operator-facing roadmap forms to the command catalog.
  - `plan_tool/roadmap_view.py` — Extend `render_decision_ledger()`’s review-mode feedback entries with safe reopen-history facts.
  - `CAPABILITIES.md` — Extend `## Architecture roadmap` with the bounded recovery workflow and its implementing modules.
  - `TESTING.md` — Extend `### The tests/cli/ characterization-test convention` or the roadmap testing guidance with the backend-free recovery test boundary.
  - `docs/cli/roadmap.md` — Update `## Usage` and `## Options` with syntax, exclusivity, confirmations, safe outcomes, and the review view.
  - `tests/cli/test_roadmap_cmd.py` — Cover parser shape, hand-built namespaces, conflict rejection, service dispatch, exit handling, and redaction.
  - `tests/test_roadmap_view.py` — Cover safe reopen-history rendering, missing-history handling, ordering, and current-mode hiding.
  - `tests/cli/package_surface_help.golden.txt` — Scope addition required: rebaseline the root help snapshot after changing `plan_tool/cli/__init__.py`.

## Implementation

- **Make exclusive recovery selection the foundational logic.** Extend the mode-selection pattern in `plan_tool/cli/roadmap_cmd.py:cmd_roadmap()` so exactly one retirement, import, reopen, or recovery action owns a request. Keep the existing dispatcher as the sole CLI owner; `plan_tool/cli/app.py:COMMAND_MODULES` already registers `roadmap_cmd.register()`.

- **Expose the four bounded forms.** Add `--record-retired-evidence FINAL --retained-evidence PATH --confirm-retirement` and `--import-retired-evidence FINAL --legacy-evidence PATH --confirm-retirement`. Use `--reopen-feedback SELECTOR --retirement-record FINAL` only with `retired`, or `--reopen-feedback SELECTOR --receipt-final FINAL` only with `receipt-unreadable` or `receipt-invalid`, alongside the landed invalidation reason and `--confirm-response-evidence`. Reopen accepts neither both locator flags nor a path. Keep recovery as that selector plus `--recover-reopen ATTEMPT_ID`.

- **Use the landed service vocabulary.** Reuse step 2’s reason-specific final and locator names in parser help and `docs/cli/roadmap.md`; do not create aliases, accept an arbitrary reopen path, or reimplement fixed-root checks. Reuse step 4’s terminal categories and status mapping rather than inferring success from artifact state.

- **Keep each confirmation separate.** `--confirm-retirement` authorizes only retirement record creation or archive import. `--confirm-response-evidence` authorizes only a reopen request. `-y` remains an apply-seed convenience flag and must not satisfy either confirmation or cause a prompt.

- **Preserve repeated inputs for preflight.** Use the occurrence-tracking approach around `_TrackEscalationOption` and `_option_occurrences()` for each single-value recovery input. Repeated selectors, finals, locators, reasons, or attempt IDs must reach the selected service as a rejected mode rather than silently using the last value.

- **Reject every companion before work starts.** Each new action must reject the other recovery actions, broad modes tracked by `_TrackRoadmapMode`, `--revise-feedback`, receipt creation and inspection, impact-analysis creation and inspection, structural rewrite, `--mode`, `--id`, explicit `--from-stage`, and `--yes`. Preserve the existing pre-dispatch behavior: an invalid combination performs no path resolution, evidence access, service call, stage run, or backend invocation.

- **Keep handlers thin.** Resolve `repo_root` and `plans_dir` with the existing `cmd_roadmap()` path, validate the slug through `plan_tool/roadmap_artifacts.py:roadmap_dir()`, pass one mode-rejection verdict to the selected service, and render its result. Do not open `plan_tool/roadmap_revision_publish.py:roadmap_writer_guard()`, read `plan_tool/run_log.py:run_log_path()`, or call `plan_tool/roadmap.py:run_roadmap()` from these CLI branches.

- **Allowlist command output.** Follow `_render_escalation_receipt_result()` and `_render_impact_analysis_result()`: print only closed outcomes and safe identifiers supplied by the landed result, such as the selector, locator kind and final, original provenance class, admission route, invalidation reason, attestation identity, and reissue-attempt identity. Never print `FeedbackRow.proposed_response`, response-ledger text, evidence bytes, attestation prose, or arbitrary service detail.

- **Keep recovery narrow.** A recovery command may append only the exact terminal event bound by step 4. It must not publish an artifact again, create another attestation, choose replacement evidence, or invoke a backend.

- **Extend the ledger, not a second view.** Update `plan_tool/roadmap_view.py:_render_pending_feedback()` and `render_decision_ledger()` to append a compact reopen-history projection under `MODE_REVIEW`. Show the original provenance class, separate admission route, invalidation reason, locator kind and final, safe attestation identity when present, and reissue-attempt identity.

- **Keep the review view read-only and private.** `load_roadmap()` remains the only roadmap disk read. Do not import the retirement service, reopen runner, evidence store, or run log into `plan_tool/roadmap_view.py`; the renderer must use parsed `FeedbackRow` data only. Preserve `LoadedRoadmap.feedback_index`’s stage-then-source order and its empty-current-mode contract.

- **Do not infer missing history.** A row with no persisted reopen history must render an explicit absent marker, not a guessed provenance, reason, or attempt. Current mode must continue to omit both normal feedback and reopen metadata.

- **Keep public surfaces aligned.** Update the `architecture-roadmap` entry in `CAPABILITIES.md` to list the step-2 and step-4 recovery modules after they land. Update `docs/cli/roadmap.md`, the roadmap catalog in `plan_tool/cli/__init__.py`, `TESTING.md`, and `tests/cli/package_surface_help.golden.txt` in the same change.

## Tests

### Tests for this step

- `tests/cli/test_roadmap_cmd.py::test_retirement_record_requires_final_retained_path_and_confirmation` — The retirement-record action accepts one complete request and refuses missing or repeated single-value inputs.

- `tests/cli/test_roadmap_cmd.py::test_archive_import_requires_final_legacy_path_and_confirmation` — The import action forwards one explicit request to the step-2 service without validating the archive root in the CLI.

- `tests/cli/test_roadmap_cmd.py::test_reopen_requires_one_selector_reason_specific_locator_and_confirmation` — The reopen action accepts only its complete request: a retirement-record final for `retired`, or an active receipt final for unreadable or invalid evidence.

- `tests/cli/test_roadmap_cmd.py::test_recovery_requires_only_matching_selector_and_attempt` — Recovery rejects evidence, reason, and confirmation inputs and forwards only the selector and attempt identity.

- `tests/cli/test_roadmap_cmd.py::test_yes_never_satisfies_recovery_trust_confirmations` — `-y` does not authorize retirement, import, or reopen.

- `tests/cli/test_roadmap_cmd.py::test_recovery_modes_reject_every_existing_and_sibling_companion_before_io` — Invalid combinations do not resolve paths, call a service, inspect evidence, or start backend work.

- `tests/cli/test_roadmap_cmd.py::test_direct_namespace_recovery_conflicts_do_not_silently_use_last_value` — Hand-built `cmd_roadmap()` namespaces preserve repeated values, both locator forms, and paths for the selected service’s rejection.

- `tests/cli/test_roadmap_cmd.py::test_recovery_modes_dispatch_only_to_their_landed_services` — Each action calls only its selected step-2 or step-4 service and never falls back to a stage, seed, local revision, or structural route.

- `tests/cli/test_roadmap_cmd.py::test_recovery_output_allowlists_safe_terminal_facts` — Success, refusal, pending-log, and recovered output omit response text, evidence bytes, and attestation prose.

- `tests/test_roadmap_view.py::test_review_ledger_renders_redacted_reopen_history_without_response_text` — Review mode displays only the safe persisted reopen facts.

- `tests/test_roadmap_view.py::test_review_ledger_marks_absent_reopen_history_without_inference` — A row without reopen history does not gain invented metadata.

- `tests/test_roadmap_view.py::test_current_ledger_hides_reopen_history_with_feedback` — `MODE_CURRENT` exposes neither feedback nor reopen-history metadata.

- `tests/test_roadmap_view.py::test_review_ledger_reopen_history_keeps_stage_then_source_order` — Reopen metadata retains the established feedback ordering.

- `tests/cli/test_package_surface.py::TestHelpGoldenSnapshot.test_help_matches_golden` — The package catalog and rebaselined golden help remain synchronized.

Every listed test, then `uv run pytest tests/ -q -n auto`, must be green before this step is complete.

## Acceptance criteria

- The CLI exposes separate retirement-record, documented archive-import, controlled reopen, and `--recover-reopen ATTEMPT_ID` action forms; reopen accepts only a reason-matching final locator and no arbitrary path.

- Retirement and import require `--confirm-retirement`; reopen requires `--confirm-response-evidence`; `-y` satisfies neither.

- Each new action rejects repeated single-value inputs and every incompatible roadmap option before I/O or dispatch.

- Every new branch delegates only to its landed step-2 or step-4 service and never invokes a backend or broad roadmap workflow.

- Recovery can restore only its bound terminal event and cannot republish an artifact, create an attestation, or select evidence.

- Terminal output contains only closed outcomes and safe identifiers. It contains no prior response text, response-ledger text, evidence bytes, or attestation prose.

- `plan-tool roadmap <slug> --view ledger --mode review` renders safe reopen history in feedback order, while current mode continues to hide all feedback metadata.

- `docs/cli/roadmap.md`, `plan_tool/cli/__init__.py`, `CAPABILITIES.md`, `TESTING.md`, and `tests/cli/package_surface_help.golden.txt` describe the same command contract.

- All listed focused tests and `uv run pytest tests/ -q -n auto` pass.

## References

- [argparse — Parser for command-line options, arguments and subcommands](https://docs.python.org/3.13/library/argparse.html) — Use for parser actions, repeated-option handling, and exclusivity checks.

## Applicable guardrails

- **Explicit trust boundaries** — The plan’s “## Step intent” requires separate operator confirmation for each recovery trust boundary; keep them independent from existing convenience flags.

- **Preserve ordinary protections** — The plan’s “## Plan intent” limits this CLI to the admitted recovery route; do not add an already-responded bypass to ordinary roadmap actions.

- **No general editor** — The plan’s “## Out of scope” limits these modes to bounded recovery behavior; do not expose arbitrary feedback mutation.

- **No ordinary re-escalation** — The plan’s “## Out of scope” keeps ordinary evidence issuance out of the new modes.

## Deferred

- General roadmap revision retention #242 — Keep the broader redesign separate from this bounded recovery workflow.

- Raw evidence, response-text, and run-log browsing commands — Keep privileged inspection outside the safe review view.
