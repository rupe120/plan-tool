> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Wire exclusive escalation creation and log-free receipt views

## Summary

Add the receipt command surface to `plan_tool/cli/roadmap_cmd.py`: one paired creation form, `--escalate-feedback SELECTOR` with `--escalation-reason REASON`, and one read-only form, `--view escalations`. Route creation through step 4’s typed receipt runner and add a separate receipt-view path that enumerates evidence without creating telemetry. The key decision is that receipt-entry precedence is decided before local revision, broad roadmap dispatch, or existing view rendering, while non-receipt commands retain step 5’s compatible behavior. When green, creation produces only a redacted lifecycle result and receipt views show validated evidence freshness without writing anything.

## Table of Contents

- [Summary](#summary) — Reviewer-level outcome and command boundary.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why the roadmap command needs a distinct receipt entry path.
- [Input](#input) — Contracts from the earlier receipt and parser steps.
- [Files (creates vs edits)](#files-creates-vs-edits) — CLI, help, catalog, and regression-test work.
- [Implementation](#implementation) — Creation precedence, runner dispatch, and receipt-view behavior.
- [Tests](#tests) — Focused command-surface and no-write regression coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Parser and test-fixture references.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that limit this step.
- [Deferred](#deferred) — Work intentionally left outside CLI wiring.

## Why

`plan_tool/cli/roadmap_cmd.py:register` and `plan_tool/cli/roadmap_cmd.py:cmd_roadmap` currently route broad roadmap actions, bounded local revision, and five read-only roadmap views, but none can create or validate immutable receipt evidence. A structural request must not be silently treated as local revision or broad execution, and a receipt view must not inherit creation telemetry or generic roadmap-view loading. This step makes the new route explicit at the command boundary while retaining the established command behavior that step 5 protects.

## Input

- **Step 4 receipt runner:** Consume the public typed runner and result contract in `plan_tool/roadmap_escalation_run.py`. Let it own typed malformed-syntax versus unknown-stage selector routing, receipt-safe selector admission before reason or source work, selected-artifact receipt selection, redacted lifecycle events, storage-result mapping, creation process status, and cached view freshness classification including distinct `source-unavailable`.

- **Steps 2 and 3 receipt contracts:** Use the landed selection and receipt-validation boundaries in `plan_tool/roadmap_escalation_selection.py` and `plan_tool/roadmap_escalation.py`. The CLI must not duplicate selection order, receipt parsing, semantic-id validation, or redaction rules.

- **Step 5 parser state:** Build on the occurrence-preserving state added around `plan_tool/cli/roadmap_cmd.py:register` and `plan_tool/cli/roadmap_cmd.py:_TrackFromStage`. It must distinguish absent, single, and repeated receipt options and view occurrences, including whether any view occurrence is `escalations`, before dispatch.

- **Configured roadmap facts:** Use `plan_tool/roadmap_artifacts.py:roadmap_dir` for receipt-entry root validation and `plan_tool/roadmap.py:STAGES` only to identify the configured source artifact during receipt-view freshness checks.

- **Immutable evidence boundary:** Use the prerequisite’s `plan_tool/roadmap_evidence_store.py:scan_evidence` only for receipt inspection. It returns opaque evidence; the CLI validates those bytes through the receipt contract before displaying any receipt-derived field.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/cli/roadmap_cmd.py` — Register receipt flags and view choice, classify receipt-entry precedence, dispatch creation through the typed runner, render safe results, and add a separate log-free escalation-view path.
  - `plan_tool/cli/__init__.py` — Update the Roadmap command catalog with the creation and inspection forms.
  - `tests/cli/test_roadmap_cmd.py` — Add parser, dispatch, precedence, redaction, status, and no-side-effect coverage.
  - `tests/cli/package_surface_help.golden.txt` — Rebaseline top-level help for the expanded Roadmap catalog.
  - `docs/cli/roadmap.md` — Document the exact receipt command forms, exclusive inputs, and log-free inspection behavior.
  - `CAPABILITIES.md` — Extend `architecture-roadmap` with the implemented receipt creation and inspection surface.

## Implementation

- **Foundational logic:** Classify every receipt-entry invocation before broad roadmap dispatch, then either run one redacted receipt lifecycle or render one log-free evidence view.

- **Add one exclusive creation pair.** Extend `plan_tool/cli/roadmap_cmd.py:register` with `--escalate-feedback SELECTOR` and `--escalation-reason REASON`. Preserve every occurrence of both flags so the command can reject missing or repeated members instead of accepting a final value silently.

- **Add `escalations` as a receipt-only view choice.** Keep the existing `summary`, `walk`, `ledger`, `index`, and `seeds` behavior under `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_view`. Route `--view escalations` to a separate handler or clearly isolated branch, because it has a different input contract and must not call `plan_tool/roadmap_view.py:load_roadmap`.

- **Keep repeated-view ownership precise.** Without a creation flag, preserve the current final-value behavior for repeated view occurrences that contain no `escalations`. Any repeated view occurrence set that includes `escalations` is a standard log-free usage error before storage, so receipt inspection remains exactly one `--view escalations`. With a creation flag, any well-formed view occurrence remains the row-1 `mode-rejected` conflict owned by receipt preflight.

- **Validate a receipt root before any receipt work.** When either creation flag appears or the requested view is `escalations`, call `plan_tool/roadmap_artifacts.py:roadmap_dir` after resolving `plans_dir` but before opening a run log, reading source bytes, or scanning evidence. An invalid slug remains a log-free usage error with status `2`, even when the creation pair is otherwise malformed.

- **Give creation precedence over every other roadmap mode.** For a root-valid invocation containing either creation flag, classify the pair before `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_revise_feedback`, the existing broad handlers, or any view handler. Missing or repeated creation flags, and any well-formed companion mode or modifier, must reach the step 4 runner as a redacted `mode-rejected` preflight rather than being ignored or handled by another command path.

- **Delegate selector ordering to the runner.** Pass the syntactically collected creation values to step 4 without loading a source or looking up feedback in the CLI. The runner consumes the shared typed malformed-syntax/unknown-stage distinction, then applies receipt-safe selector admission before reason validation or selected-artifact selection, so rows 2, 2b, and 3 cannot become source or row verdicts through error-text parsing.

- **Retain parser-owned failures.** Keep `argparse` validation for invalid `--view`, `--mode`, and `--from-stage` values. Those malformed inputs must remain ordinary log-free parser usage errors, even beside receipt flags; only well-formed combinations reach receipt precedence.

- **Keep non-receipt compatibility intact.** If neither creation flag nor `--view escalations` appears, use step 5’s compatibility boundary before the existing dispatch order in `plan_tool/cli/roadmap_cmd.py:cmd_roadmap`. Existing broad-mode conflicts must retain their established status and output before path resolution, disk reads, backend work, or lifecycle logging.

- **Delegate creation rather than rebuilding it.** Pass the parsed creation facts and parser-derived conflict state to the step 4 runner. Render only its typed outcome, process status, receipt identity, and `requires-scope-review` handoff when those fields are available. Never print raw selector or reason input, feedback request text, receipt bytes, source text, or exception prose.

- **Keep receipt inspection read-only and log-free.** Reject every modifier or action beside a pure `--view escalations` request before evidence access. Do not open `RunLogWriter`, call the creation runner, invoke a backend, acquire a roadmap writer, or dispatch a broad roadmap action.

- **Validate evidence before displaying it.** For each opaque record returned by `scan_evidence`, use the step 3 contract to reject duplicate-member, unsupported, unsafe-identifier, path-substituted, or semantic-id-mismatched receipts. Delegate configured-path/source freshness to step 4, then use the step 2 total selection predicate only after freshness succeeds. A stale, unavailable, noncanonical, ineligible, or target-mismatched receipt has no handoff; `source-unavailable` remains visibly distinct from readable resolved evidence.

- **Keep invalid output safe.** A valid current receipt may show its redacted receipt facts and handoff. Invalid evidence may show only its status and escaped relative storage location. A failed enumeration must render `storage-unavailable` as a completed, log-free view rather than as an empty result.

- **Update operator-facing surfaces together.** Keep `plan_tool/cli/__init__.py`, `docs/cli/roadmap.md`, `tests/cli/package_surface_help.golden.txt`, and `CAPABILITIES.md:## Architecture roadmap` aligned with the actual parser forms. Leave receipt schema and workflow explanation to step 7.

## Tests

### Tests for this step

- `tests/cli/test_roadmap_cmd.py::TestArgparseWiring::test_escalation_flags_preserve_absent_single_and_repeated_occurrences` — Proves both creation flags and repeated `--view` values retain enough parser state for exclusive command classification.

- `tests/cli/test_roadmap_cmd.py::TestArgparseWiring::test_escalation_view_is_a_supported_view_choice` — Confirms `--view escalations` parses while existing view choices remain available.

- `tests/cli/test_roadmap_cmd.py::test_invalid_receipt_slug_is_log_free_before_runner_source_or_storage_access` — Proves receipt root validation returns status `2` before any receipt lifecycle or evidence action.

- `tests/cli/test_roadmap_cmd.py::test_creation_pair_requires_exactly_one_selector_and_reason` — Rejects partial and repeated creation pairs through one redacted `mode-rejected` lifecycle.

- `tests/cli/test_roadmap_cmd.py::test_unsafe_selector_delegates_to_row_2b_before_source_or_broad_dispatch` — Proves a syntactically valid unsafe creation selector reaches the runner’s redacted `identifier-rejected` preflight and no source, view, local-revision, or broad handler.

- `tests/cli/test_roadmap_cmd.py::test_malformed_and_unknown_creation_selectors_delegate_to_distinct_runner_preflights` — Proves malformed selector syntax and an unknown configured stage reach their distinct redacted runner preflights and no source, view, local-revision, or broad handler.

- `tests/cli/test_roadmap_cmd.py::test_creation_conflicts_precede_local_revision_broad_dispatch_and_every_view` — Proves either creation flag beside each well-formed companion reaches receipt preflight and reaches no competing handler.

- `tests/cli/test_roadmap_cmd.py::test_malformed_existing_option_stays_argparse_log_free_beside_creation` — Preserves standard parser failure for invalid view, mode, and stage values before receipt work.

- `tests/cli/test_roadmap_cmd.py::test_valid_creation_delegates_once_to_receipt_runner_and_renders_only_safe_fields` — Verifies CLI-to-runner wiring, status mapping, safe handoff output, and absence of raw input or reviewer content.

- `tests/cli/test_roadmap_cmd.py::test_receipt_creation_never_invokes_backend_or_roadmap_writer` — Proves normal and rejected creation paths bypass `run_roadmap`, local revision, and canonical mutation helpers.

- `tests/cli/test_roadmap_cmd.py::test_escalation_view_rejects_every_modifier_and_action_before_storage` — Covers prohibited companions with status `2`, no scan, and no run log.

- `tests/cli/test_roadmap_cmd.py::test_repeated_ordinary_view_keeps_current_final_value` — Proves repeated non-`escalations` views keep their current final-value behavior and do not become receipt validation.

- `tests/cli/test_roadmap_cmd.py::test_repeated_view_containing_escalations_is_standard_log_free_usage_error` — Proves any repeated `--view` set containing `escalations` cannot collapse to a receipt or ordinary view.

- `tests/cli/test_roadmap_cmd.py::test_escalation_view_is_log_free_and_missing_namespace_is_empty` — Confirms the pure view creates neither telemetry nor evidence storage.

- `tests/cli/test_roadmap_cmd.py::test_escalation_view_revalidates_receipt_source_selection_and_target_before_handoff` — Covers fresh, stale, unavailable, noncanonical, ineligible, and target-mismatched evidence without granting an invalid handoff.

- `tests/cli/test_roadmap_cmd.py::test_invalid_escalation_evidence_discloses_only_safe_status_and_relative_location` — Rejects malformed or substituted records without rendering receipt fields or source content.

- `tests/cli/test_roadmap_cmd.py::test_existing_nonreceipt_views_and_broad_mode_conflicts_keep_current_contracts` — Keeps step 5’s compatibility result and existing `--mode` and `--id` behavior intact.

- `tests/cli/test_package_surface.py::TestHelpGoldenSnapshot::test_help_matches_golden` — Confirms the edited top-level command catalog matches `tests/cli/package_surface_help.golden.txt`.

Every listed test must be green before this step is complete.

## Acceptance criteria

- `plan-tool roadmap <slug> --escalate-feedback SELECTOR --escalation-reason REASON` reaches the receipt runner exactly once and reports only the runner’s safe typed result.

- A root-valid creation invocation with an incomplete, repeated, or well-formed conflicting companion records one redacted `mode-rejected` preflight/result lifecycle and reaches no local revision, broad roadmap action, receipt view, or backend.

- A syntactically valid unsafe creation selector reaches the runner’s row-2b `identifier-rejected` preflight before reason validation, source access, feedback lookup, local revision, broad dispatch, or receipt viewing.

- A malformed creation selector and a syntactically valid unknown configured stage reach the runner’s distinct `malformed-selector` and `unknown-artifact` preflights without CLI error-text parsing, source access, feedback lookup, local revision, broad dispatch, or receipt viewing.

- Invalid receipt slugs and parser-invalid companion values exit with status `2` without a run log, source read, storage access, or evidence publication.

- Without a creation flag, repeated views that contain no `escalations` retain their current final-value behavior; any repeated view containing `escalations` exits with a log-free usage error before storage. With a creation flag, every well-formed view occurrence remains the redacted row-1 `mode-rejected` lifecycle.

- `plan-tool roadmap <slug> --view escalations` accepts no modifier or action option, creates no telemetry, and treats an absent evidence namespace as an empty completed view.

- Receipt views validate opaque records, recompute source binding, and rerun selection before displaying a handoff; invalid or stale records have no handoff and disclose no reviewer or artifact content.

- Existing non-receipt modes, local revision, and the five existing roadmap views retain their current dispatch behavior and usage results.

- `plan_tool/cli/__init__.py`, `docs/cli/roadmap.md`, `CAPABILITIES.md`, and `tests/cli/package_surface_help.golden.txt` describe the same implemented command surface.

- No creation or view path rewrites canonical roadmap artifacts, feedback state, seeds, drafts, or Git state, and no path invokes a backend.

## References

- [argparse — Parser for command-line options and arguments](https://docs.python.org/3.13/library/argparse.html) — Use for custom actions, repeated option tracking, and parser-owned validation.

- [pytest monkeypatch](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Use to prove rejected commands do not reach runners, storage, or backend paths.

- [pytest temporary directories](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — Use isolated roadmap and evidence fixtures for receipt-view tests.

## Applicable guardrails

- **The plan’s “## Plan intent”, receipt-only record** — Limit this command surface to immutable receipt evidence and its handoff; do not make scope or route decisions.

- **The plan’s “## Step intent”, exclusive precedence** — Reject partial, repeated, and well-formed conflicting receipt invocations before broad dispatch or receipt viewing, then recheck selection before any view handoff.

- **The plan’s “## Out of scope”, local revision compatibility** — Leave `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_revise_feedback` and its bounded writer contract unchanged.

- **The plan’s “## Out of scope”, stage and seed behavior** — Do not change stage execution, seed handling, or existing broad-mode behavior beyond the receipt-entry classifier.

- **The plan’s “## Out of scope”, immutable-evidence storage** — Consume the prerequisite’s publication and enumeration API without adding filesystem protocol or storage recovery logic here.

- **The plan’s “## Out of scope”, identifier grammar** — Apply receipt-safe validation only through the landed receipt contracts; do not alter roadmap-wide identifiers or local revision parsing.

## Deferred

- Broader receipt-schema and workflow documentation — Step 7 owns the full operator explanation and format-reference updates.

- Relation closure, impact analysis, and route selection — The receipt handoff records evidence only and does not choose later work.

- Structural artifact patches and multi-artifact publication — This command remains noncanonical and leaves roadmap-owned state unchanged.

- Shared command-mode infrastructure outside `plan_tool/cli/roadmap_cmd.py` — Other command modules have separate compatibility contracts.
