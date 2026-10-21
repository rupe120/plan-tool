# Step 5 — Add exclusive retirement import, reopen, and recovery modes with a safe review view

## Summary

Add the four bounded roadmap CLI workflows in `plan_tool/cli/roadmap_cmd.py`: fixed-root retirement-record creation, documented-version-1 archive import, controlled reopen, and attempt recovery. Route each action to the landed step 2 or step 4 service rather than recreating validation, publication, or recovery logic in the CLI. Extend the existing `--view ledger --mode review` path in `plan_tool/roadmap_view.py` to show persisted safe reopen metadata while omitting prior response text. On green, operators must supply the dedicated confirmation for each trust boundary, and every command and view output remains backend-free and redacted.

## Table of Contents

- [Summary](#summary) — The completed CLI and review behavior.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — The missing safe operator workflow.
- [Input](#input) — Upstream runner, classifier, CLI, and view contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — Scoped code, docs, and tests.
- [Implementation](#implementation) — Exclusive dispatch, confirmation, rendering, and view rules.
- [Tests](#tests) — Focused command and renderer coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — CLI parsing reference.
- [Applicable guardrails](#applicable-guardrails) — Boundaries on this recovery surface.
- [Deferred](#deferred) — Work intentionally left outside this step.

## Why

`plan_tool/cli/roadmap_cmd.py:cmd_roadmap()` already separates broad roadmap modes from exclusive receipt, analysis, and structural routes, but it has no public path to record retirement, reopen an admitted response, or recover a published attempt. `plan_tool/roadmap_view.py:_render_pending_feedback()` currently renders ordinary review context only, so it cannot safely show the identity and reason behind a completed reopen. Operators need one explicit, inspectable workflow that uses the landed gates without exposing the prior response.

## Input

- **Step 2 retirement contract:** Consume the landed publisher and closed invalidation result from `plan_tool/roadmap_evidence_retirement.py`. Its input names, allowed evidence location, and result fields are code-owned; do not recreate the classifier in the CLI.

- **Step 4 reopen runner:** Consume the landed backend-free runner in `plan_tool/roadmap_feedback_reopen_run.py`. Use its closed terminal result and recovery outcome rather than opening a writer guard, reading logs, or mutating roadmap artifacts in `plan_tool/cli/roadmap_cmd.py`.

- **Exclusive CLI pattern:** Follow `plan_tool/cli/roadmap_cmd.py:_TrackEscalationOption`, `_option_occurrences()`, `_has_receipt_creation()`, and the existing `*_has_conflict()` predicates. Direct `cmd_roadmap()` callers construct namespaces by hand, so parser-only validation is insufficient.

- **Review-mode boundary:** Preserve `plan_tool/roadmap_view.py:LoadedRoadmap`, `MODE_CURRENT`, `MODE_REVIEW`, `load_roadmap()`, and `render_decision_ledger()`. Current mode hides feedback by design; review mode may read only parsed roadmap state and must not inspect evidence storage or run logs.

- **Package help contract:** `plan_tool/cli/app.py:build_parser()` builds root help from `plan_tool/cli/__init__.py`’s package docstring. Updating the catalog requires rebaselining the existing golden help snapshot.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/cli/roadmap_cmd.py` — Add parser inputs, exclusive-mode detection, thin dispatch helpers, and redacted result rendering for retirement, documented archive import, reopen, and recovery.
  - `plan_tool/cli/__init__.py` — Add the four operator-facing roadmap forms to the command catalog.
  - `plan_tool/roadmap_view.py` — Extend the existing review ledger with safe reopen-history metadata and preserve current-mode hiding.
  - `CAPABILITIES.md` — Update the `architecture-roadmap` capability with the bounded recovery workflow and review boundary.
  - `TESTING.md` — Add focused guidance for the backend-free reopen CLI and safe review tests.
  - `docs/cli/roadmap.md` — Document syntax, exclusivity, required confirmations, safe outcomes, and the review command.
  - `tests/cli/test_roadmap_cmd.py` — Cover parser shape, conflict handling, runner dispatch, exit mapping, and redaction.
  - `tests/test_roadmap_view.py` — Cover safe review rendering and current-mode hiding.
  - `tests/cli/package_surface_help.golden.txt` — **Scope addition required:** rebaseline the root help snapshot after the `plan_tool/cli/__init__.py` catalog changes.

## Implementation

- **Keep four actions exclusive.** Add one fixed-root retirement-record action using `--record-retired-evidence FINAL`, `--retained-evidence PATH`, and `--confirm-retirement`; one documented archive import using `--import-retired-evidence FINAL`, `--legacy-evidence PATH`, and `--confirm-retirement`; one reopen action with one receipt-safe feedback selector, the landed exact-evidence inputs, one classifier-matching reason, and `--confirm-response-evidence`; and recovery with that selector plus `--recover-reopen ATTEMPT_ID`. The import runner itself, not the CLI, limits `--legacy-evidence` to the named version-1 archive root.

- **Use feedback-shaped naming for reopen selection.** One reasonable public form is `--reopen-feedback SELECTOR`, matching `--revise-feedback` and `--escalate-feedback`. Settle the exact evidence-option spellings from the landed step 2 interface, then use those same names consistently in parser help and `docs/cli/roadmap.md`.

- **Treat confirmation as a separate trust input.** `--confirm-retirement` and `--confirm-response-evidence` must be explicit flags. `-y` must never satisfy either confirmation, and no TTY prompt or implicit acknowledgement may replace them.

- **Preserve every occurrence needed for rejection.** Extend the occurrence-preserving approach around `_TrackEscalationOption` so repeated selectors, finals, reasons, or incompatible action forms reach the owning runner as a mode rejection rather than letting the last value silently win. The fixed-root retirement action, archive import, reopen action, and recovery action must each reject the other three.

- **Reject companions before stateful work.** Each new action must reject every broad mode tracked by `_TrackRoadmapMode`, `--revise-feedback`, escalation creation and inspection, impact analysis creation and inspection, structural rewrite, `--mode`, `--id`, explicit `--from-stage`, and `--yes`. Preserve the existing no-path-resolution/no-dispatch behavior for malformed mode combinations.

- **Keep command handlers thin.** Resolve `repo_root` and `plans_dir` as `cmd_roadmap()` already does, validate the slug before the selected runner can touch storage, pass the runner one conflict verdict, and map its returned status. Do not call `run_roadmap()`, seed actions, an invoker, or direct artifact/evidence writers from any new branch.

- **Render an allowlist of safe terminal facts.** Follow `_render_escalation_receipt_result()` and `_render_impact_analysis_result()` rather than printing arbitrary result data or exceptions. Show only closed outcomes and safe identifiers such as selector, retirement-record identity, original provenance class, separate admission route, invalidation reason, safe attestation identity, and reissue-attempt identity. Never print `FeedbackRow.proposed_response`, response-ledger text, retained evidence bytes, attestation prose, or an arbitrary runner detail string.

- **Use the existing review ledger.** Extend `plan_tool/roadmap_view.py:_render_pending_feedback()` and `render_decision_ledger()` under `MODE_REVIEW` with a compact reopen-history projection. It must identify the feedback row and, when the landed history carries them, display original provenance class, separate admission route, invalidation reason, safe attestation identity when attested, retirement-record or evidence identity, and reissue-attempt identity.

- **Keep the view a leaf and read-only.** `load_roadmap()` remains the only roadmap disk loader. Do not add imports from the reopen runner, retirement service, evidence store, or run log to `plan_tool/roadmap_view.py`; use the parsed `FeedbackRow` fields supplied by earlier steps. Preserve the source-order behavior of `feedback_index` and the existing `MODE_CURRENT` empty-feedback contract.

- **State missing history plainly.** A legacy or ordinary feedback row with no reopen history must render an explicit unavailable or absent marker, not an inferred provenance class, reason, or attempt identity.

- **Keep documentation aligned.** Update `docs/cli/roadmap.md`, `plan_tool/cli/__init__.py`, and `CAPABILITIES.md` together. Describe that retirement records do not change a feedback row, reopen and recovery remain backend-free, recovery does not republish artifacts, and the review ledger excludes prior response text.

- **Refresh the root-help fixture.** Rebaseline `tests/cli/package_surface_help.golden.txt` through the documented package-surface workflow after the package catalog changes. Do not edit `tests/cli/test_package_surface.py` merely to accommodate the new wording.

## Tests

### Tests for this step

- `tests/cli/test_roadmap_cmd.py::test_retirement_record_mode_requires_one_final_retained_path_and_confirmation` — Retirement dispatch accepts one complete explicit request and rejects missing or repeated required inputs.

- `tests/cli/test_roadmap_cmd.py::test_documented_v1_archive_import_requires_one_final_source_and_confirmation` — Import dispatch accepts only its explicit form and forwards source validation to the Step 2 service.

- `tests/cli/test_roadmap_cmd.py::test_reopen_mode_requires_one_selector_evidence_inputs_reason_and_confirmation` — Reopen accepts only one complete selector-and-evidence request with the landed closed reason.

- `tests/cli/test_roadmap_cmd.py::test_recovery_mode_requires_only_matching_selector_and_attempt` — Recovery accepts one selector plus one attempt and rejects evidence, reason, and confirmation inputs.

- `tests/cli/test_roadmap_cmd.py::test_yes_never_satisfies_retirement_or_response_evidence_confirmation` — `-y` cannot authorize either trust boundary.

- `tests/cli/test_roadmap_cmd.py::test_reopen_actions_reject_every_broad_and_exclusive_companion_before_io` — All four new modes reject existing and sibling actions before path resolution, runner invocation, artifact access, or backend work.

- `tests/cli/test_roadmap_cmd.py::test_reopen_action_occurrences_reach_the_runner_as_mode_rejection` — Repeated or conflicting exclusive inputs are not silently reduced to a final value.

- `tests/cli/test_roadmap_cmd.py::test_retirement_import_reopen_and_recovery_dispatch_only_to_their_landed_runners` — Each branch forwards only the required safe inputs and never falls back to stage, seed, or revision dispatch.

- `tests/cli/test_roadmap_cmd.py::test_reopen_terminal_output_contains_only_safe_identifiers_and_closed_outcomes` — Success, refusal, `committed-log-pending`, and recovered output omit prior response text and other untrusted detail.

- `tests/test_roadmap_view.py::test_review_ledger_renders_safe_reopen_history_without_response_text` — Review mode shows only safe original provenance, admission route, reason, evidence, and attempt metadata for a reopened row.

- `tests/test_roadmap_view.py::test_review_ledger_marks_missing_reopen_history_without_inference` — Legacy or ordinary rows do not acquire invented provenance or invalidation metadata.

- `tests/test_roadmap_view.py::test_current_mode_hides_reopen_history_with_all_feedback_rows` — `MODE_CURRENT` exposes neither feedback nor reopen metadata.

- `tests/test_roadmap_view.py::test_review_reopen_history_keeps_stage_then_source_order` — Safe reopen rows retain the established review ordering.

Every listed test, followed by `uv run pytest tests/ -q -n auto`, must be green before this step is complete.

## Acceptance criteria

- The CLI exposes separate fixed-root retirement-record, documented-version-1 archive import, reopen, and `--recover-reopen ATTEMPT_ID` action shapes.

- Retirement and archive import require `--confirm-retirement`; reopen requires `--confirm-response-evidence`; `-y` satisfies neither.

- Recovery accepts only its matching selector and attempt identity, and it cannot create an attestation, republish a roadmap artifact, or select replacement evidence.

- Each new action rejects repeated required values and every incompatible existing or sibling roadmap option before performing I/O or dispatch.

- Each action delegates only to its landed step 2 or step 4 service and never invokes a backend or broad roadmap workflow.

- Terminal command output contains only closed outcomes and safe identifiers; it contains no prior response text, ledger text, evidence bytes, or attestation prose.

- `plan-tool roadmap <slug> --view ledger --mode review` shows safe original provenance and distinct admission-route metadata in stable feedback order, while current mode continues to hide all feedback metadata.

- `docs/cli/roadmap.md`, `plan_tool/cli/__init__.py`, `CAPABILITIES.md`, `TESTING.md`, and the package-help golden snapshot describe the same command contract.

- All listed focused tests and `uv run pytest tests/ -q -n auto` pass.

## References

- [argparse — Parser for command-line options, arguments and subcommands](https://docs.python.org/3.13/library/argparse.html) — Use for parser actions, repeated-option handling, and exclusive action validation.

## Applicable guardrails

- **Explicit trust boundaries** — The plan’s “## Step intent” requires dedicated confirmation at each trust boundary. Keep confirmation separate from existing convenience flags and result rendering.

- **Preserve ordinary protections** — The plan’s “## Plan intent” requires this CLI to route only the admitted recovery case. Do not add an already-responded bypass to general roadmap actions.

- **No general editor** — The plan’s “## Out of scope” limits this command surface to bounded recovery operations. Do not expose arbitrary feedback mutation.

- **No ordinary re-escalation** — The plan’s “## Out of scope” keeps normal evidence issuance out of these new modes.

## Deferred

- General roadmap revision retention #242 — Keep the broader retention redesign separate from this bounded operator workflow.

- Raw evidence, response-text, or run-log browsing commands — Keep privileged inspection outside the safe review view.
