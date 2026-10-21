> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Wire exclusive escalation creation and log-free receipt views

## Summary

Add the `--escalate-feedback` and `--escalation-reason` creation path plus the `--view escalations` inspection path to `plan_tool/cli/roadmap_cmd.py`. Keep receipt creation exclusive and delegate its typed lifecycle work to step 4’s runner; keep receipt inspection read-only and log-free. Update the roadmap command’s parser help, top-level help catalog, CLI reference, capability description, and golden snapshot together. When green, operators can create a receipt or inspect receipt status without triggering a broad roadmap action, a backend call, or an unintended write.

## Table of Contents

- [Summary](#summary) — Reviewer-level outcome and affected command surfaces.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why the CLI must make receipt actions unambiguous.
- [Input](#input) — Contracts supplied by the earlier receipt steps and current CLI.
- [Files (creates vs edits)](#files-creates-vs-edits) — Existing command, test, and documentation files to update.
- [Implementation](#implementation) — Dispatch order, exclusivity, rendering, and no-write rules.
- [Tests](#tests) — CLI cases that prove creation and inspection boundaries.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary CLI and pytest references.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this wiring.
- [Deferred](#deferred) — Work intentionally left to later steps or prerequisites.

## Why

`plan_tool/cli/roadmap_cmd.py:cmd_roadmap` currently routes stage runs, seed actions, local feedback revision, and five canonical-artifact views, but it has no way to preserve repeated receipt options or to keep a receipt request from being mistaken for a broad roadmap action. Receipt creation needs the runner from step 4 to record one redacted lifecycle, while receipt inspection must remain a pure read even when evidence is missing or invalid. The command layer must therefore decide the mode before existing broad dispatch can read, write, invoke a backend, or render an unrelated view.

## Input

- **Step 2 selection outcome:** Use step 2’s total selected-artifact receipt-selection boundary for creation and for the live re-check before any inspection handoff. Do not recreate its ordered eligibility rules in the CLI.

- **Step 3 receipt contract:** Use step 3’s strict receipt parser and identity/path validation when inspecting opaque evidence. Stored receipt content must never choose the source artifact path to read.

- **Step 4 runner outcome:** Delegate creation to step 4’s typed receipt runner and use its typed lifecycle outcome and process status. The runner owns creation telemetry and its redaction rules.

- **Current command surface:** Preserve existing stage and seed behavior in `plan_tool/cli/roadmap_cmd.py:cmd_roadmap`, local revision behavior in `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_revise_feedback`, and ordinary-view behavior in `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_view`. Use `plan_tool/roadmap_artifacts.py:roadmap_dir` as the pure validation boundary for a receipt-entry slug before dispatch can open a log, read a source, publish, or scan evidence.

- **Evidence listing:** Use `plan_tool/roadmap_evidence_store.py:scan_evidence` with `EvidenceNamespace.ESCALATIONS` for inspection. Its empty result is a read-only empty namespace, and its failure result is distinct from an empty list.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/cli/roadmap_cmd.py` — Register receipt flags and view choice, preserve option occurrences, dispatch creation before broad modes, render typed creation results, and render log-free evidence status.
  - `plan_tool/cli/__init__.py` — Update the top-level roadmap command catalog with receipt creation and inspection forms.
  - `tests/cli/test_roadmap_cmd.py` — Add parser, dispatch, redaction, exit-status, and pure-view regression coverage.
  - `tests/cli/package_surface_help.golden.txt` — Rebaseline the intentional top-level help change.
  - `docs/cli/roadmap.md` — Document receipt creation, receipt inspection, exclusivity, and their no-backend/no-write behavior.
  - `CAPABILITIES.md` — Extend the `architecture-roadmap` capability with the landed receipt surfaces and their creation-versus-inspection boundary.

## Implementation

- **Foundational logic:** Classify receipt creation and receipt inspection before ordinary roadmap dispatch, preserving repeated-option evidence so no invocation is silently reinterpreted.

- **Add one paired creation surface.** `plan_tool/cli/roadmap_cmd.py:register` must accept `--escalate-feedback ARTIFACT:FEEDBACK_ID` and `--escalation-reason REASON`. Creation is valid only when each appears exactly once.

- **Preserve option counts through dispatch.** Do not rely on argparse’s final stored value for either receipt flag or `--view`. One approach is a tracking action shaped like `plan_tool/cli/roadmap_cmd.py:_TrackFromStage`; any approach is acceptable if `cmd_roadmap` can distinguish absent, single, and repeated occurrences.

- **Collect broad modes before enforcing their ordinary exclusivity.** Keep receipt flags outside the broad run-mode group and remove parser-level mutual exclusion for `--apply`, `--refresh-seeds`, `--accept-seed`, `--materialize`, `--from-stage`, and `--view`. The parser must retain enough state to classify a receipt command containing any combination of those options instead of aborting before step 4 can record the required redacted rejection. When no receipt-creation flag is present, dispatch restores the same broad-mode mutual-exclusion usage error before any ordinary action, view, source access, storage access, or log.

- **Validate the receipt root before a receipt side effect.** Before routing either receipt creation or `--view escalations`, call `plan_tool/roadmap_artifacts.py:roadmap_dir(plans_dir, slug)`. A separator or parent-component slug exits through standard usage status `2` and reaches neither the runner, `RunLogWriter`, source read, publication, nor `scan_evidence`. This pure CLI check makes the command's usage result deterministic; step 4 repeats it as the direct-caller boundary.

- **Give creation precedence over every conflicting mode.** After root validation, route any invocation containing either receipt-creation flag before the existing `--revise-feedback`, stage, seed, and view branches. An incomplete pair, repeated pair member, one or more broad-mode companions, or any other prohibited companion must reach the receipt runner as the documented `mode-rejected` rejection; it must not load evidence, render a view, call `run_roadmap`, or call `run_local_feedback_revision`. This includes combinations such as `--apply --refresh-seeds` that are ordinary usage errors only when no receipt-creation flag is present.

- **Keep local revision unchanged when receipt creation is absent.** Preserve `plan_tool/cli/roadmap_cmd.py:_revise_feedback_has_conflict` and the current `--revise-feedback` dispatch contract for ordinary local-revision calls. Do not widen its writer, backend, or recovery behavior.

- **Delegate creation once.** Pass the selector, reason, resolved repository paths, configured stages, and typed mode state to step 4’s runner. Do not open a second `RunLogWriter`, repeat selection in the CLI, publish evidence directly, or pass the command’s stage `invoker` into the receipt path.

- **Render only typed, safe creation facts.** Map the runner’s process status directly: durable created or reused receipts exit `0`; preflight rejection exits `2`; storage rejection, collision, invalid existing evidence, and write failure exit `1`; interruption exits `130`. Print the `requires-scope-review` handoff only for durable created or reused outcomes, and never echo raw selector or reason input, exception text, feedback prose, target prose, or receipt bytes.

- **Add `escalations` as a view choice.** Keep `summary`, `walk`, `ledger`, `index`, and `seeds` on `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_view` and its current `--mode`/`--id` rules. Handle `--view escalations` through a separate receipt-inspection branch so it never calls `plan_tool/roadmap_view.py:load_roadmap` as a substitute for evidence validation.

- **Make receipt inspection exclusive and log-free.** After root validation, reject every receipt-view modifier or action option before `scan_evidence` runs. Repeated `--view` is a standard usage error with exit `2`, no receipt lifecycle event, and no run log. A creation flag beside any view remains a creation preflight, so it wins over receipt-view validation and does not render a view.

- **Validate evidence before displaying trusted facts.** Enumerate only through `plan_tool/roadmap_evidence_store.py:scan_evidence`, validate each record through step 3’s contract, recompute its selector-derived stage path from `plan_tool/roadmap.py:STAGES` and `plan_tool/roadmap_artifacts.py:roadmap_dir`, then re-run step 2’s total selection predicate against the current selected artifact before showing a handoff.

- **Keep status distinct from trust.** Show `storage-unavailable` for a scan failure and exit `0`. Keep invalid, stale, noncanonical, source-unavailable, selection-ineligible, and target-mismatched evidence visible without a handoff. Invalid evidence may expose only its status and escaped relative storage location, never stored receipt fields.

- **Protect the no-write boundary.** Neither receipt creation nor receipt inspection may invoke a backend, rewrite a canonical roadmap artifact, change feedback or seed state, or modify Git state. Inspection must not create a missing evidence namespace or telemetry.

- **Update public descriptions together.** Keep `plan_tool/cli/__init__.py`, `docs/cli/roadmap.md`, `CAPABILITIES.md`’s `## Architecture roadmap` section, and `tests/cli/package_surface_help.golden.txt` aligned with `register`. State that creation writes immutable evidence plus its redacted lifecycle, while `--view escalations` remains log-free and read-only.

## Tests

### Tests for this step

- `tests/cli/test_roadmap_cmd.py::test_escalation_creation_requires_exactly_one_selector_and_reason` — Accepts one paired creation request and identifies every partial pair as a receipt preflight rejection.

- `tests/cli/test_roadmap_cmd.py::test_repeated_escalation_options_are_not_collapsed` — Preserves repeated selector and reason occurrences and sends each case to the runner as `mode-rejected`.

- `tests/cli/test_roadmap_cmd.py::test_escalation_creation_conflict_precedence_skips_broad_dispatch_and_views` — Proves receipt creation wins over every conflicting roadmap action, local revision, and view without calling their handlers.

- `tests/cli/test_roadmap_cmd.py::test_escalation_creation_precedence_survives_multiple_broad_modes` — Gives creation every pair and a representative higher-cardinality combination of `--apply`, `--refresh-seeds`, `--accept-seed`, `--materialize`, `--from-stage`, and `--view`, proving each reaches one `mode-rejected` runner lifecycle rather than argparse.

- `tests/cli/test_roadmap_cmd.py::test_nonreceipt_broad_mode_conflicts_keep_usage_contract` — Covers the same broad-mode combinations without a creation flag and proves the current usage rejection remains log-free and reaches no ordinary handler.

- `tests/cli/test_roadmap_cmd.py::test_escalation_creation_delegates_once_without_a_backend_invoker` — Sends one typed request to the receipt runner and reaches no stage or local-revision backend seam.

- `tests/cli/test_roadmap_cmd.py::test_escalation_creation_uses_runner_process_statuses` — Maps each typed lifecycle outcome to `0`, `1`, `2`, or `130` without a second CLI policy map.

- `tests/cli/test_roadmap_cmd.py::test_escalation_creation_output_never_echoes_raw_input_or_reviewer_content` — Uses sentinel raw values to prove CLI output retains only safe typed facts.

- `tests/cli/test_roadmap_cmd.py::test_view_escalations_is_log_free_and_missing_namespace_stays_absent` — Scans an empty namespace, exits `0`, creates no evidence directory, and opens no run log.

- `tests/cli/test_roadmap_cmd.py::test_repeated_view_escalations_is_usage_error_before_scan` — Rejects repeated `--view` before evidence access and without telemetry.

- `tests/cli/test_roadmap_cmd.py::test_invalid_receipt_slug_is_usage_before_runner_or_scan` — Uses separator and parent-component slugs for creation and `--view escalations`, proving status `2` with no runner, logger, source, publication, or evidence scan.

- `tests/cli/test_roadmap_cmd.py::test_view_escalations_rejects_every_modifier_before_scan` — Covers receipt-view modifiers and action options, asserting each rejected form reaches neither storage nor a logger.

- `tests/cli/test_roadmap_cmd.py::test_existing_views_keep_their_mode_and_id_contracts` — Proves the five existing view values retain their current `--mode` and `--id` behavior.

- `tests/cli/test_roadmap_cmd.py::test_escalation_view_validates_receipt_and_reruns_selection_before_handoff` — Shows a handoff only when stored evidence, current source, and re-derived selected target all agree.

- `tests/cli/test_roadmap_cmd.py::test_escalation_view_untrusted_evidence_has_no_handoff_or_receipt_fields` — Covers invalid, stale, noncanonical, unavailable, and selection-ineligible evidence without exposing stored receipt content.

- `tests/cli/test_roadmap_cmd.py::test_escalation_view_storage_failure_is_visible_and_exits_zero` — Renders `storage-unavailable` as a completed, log-free inspection result.

- `tests/cli/test_roadmap_cmd.py::test_roadmap_help_documents_escalation_creation_and_view` — Pins the parser help text for both new command forms and their exclusive behavior.

- `tests/cli/test_package_surface.py::TestCliHelpGolden.test_help_matches_golden` — Runs unchanged against the updated `tests/cli/package_surface_help.golden.txt` snapshot.

Every listed test must be green before this step is complete.

## Acceptance criteria

- `plan-tool roadmap <slug> --escalate-feedback <artifact>:<feedback-id> --escalation-reason <reason>` delegates exactly one creation request to the step 4 runner and never invokes a backend.

- Incomplete, repeated, or conflicting receipt creation reaches one redacted receipt preflight/result lifecycle with exit `2`, without broad dispatch or receipt inspection. Receipt-aware parsing keeps every broad-mode combination available for this decision; the same combinations without a creation flag retain their existing log-free usage rejection.

- `plan-tool roadmap <slug> --view escalations` reads evidence through `scan_evidence`, never opens a run log, and returns `0` for empty, unavailable, stale, invalid, or ineligible evidence.

- A receipt-entry slug is validated through `roadmap_dir(plans_dir, slug)` before the runner or `scan_evidence`; an invalid slug returns log-free usage status `2` and reaches no logger, source, publication, or evidence scan. A receipt-view modifier, action option, or repeated `--view` returns `2` before any evidence scan; existing non-receipt views retain their current modifiers.

- Only a validated receipt whose current selected artifact passes the total receipt-selection predicate and has a matching target receives a `requires-scope-review` handoff.

- CLI output and receipt views omit raw selector and reason input, reviewer prose, artifact content, receipt bytes, and exception-derived text.

- `plan_tool/cli/__init__.py`, `docs/cli/roadmap.md`, `CAPABILITIES.md`, parser help, and `tests/cli/package_surface_help.golden.txt` describe the same receipt commands and read/write boundary.

## References

- [argparse — Parser for command-line options and arguments](https://docs.python.org/3.13/library/argparse.html) — Use for paired options, custom actions, and command-mode parsing.

- [pytest monkeypatch](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Use to prove forbidden dispatch, storage, logger, and backend seams remain untouched.

- [pytest temporary directories](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — Use isolated roadmap and evidence fixtures for no-write inspection checks.

## Applicable guardrails

- **The plan’s “## Step intent”, exclusive receipt modes:** Make creation and inspection unambiguous before existing roadmap dispatch or receipt inspection begins.

- **The plan’s “## Plan intent”, receipt-only record:** Limit this step to creation wiring, inspection, and scope-review handoff. Do not turn a receipt into impact analysis or a broad revision decision.

- **The plan’s “## Out of scope”, local revision compatibility:** Preserve `--revise-feedback` behavior and do not alter its writer, allowlist, backend, or recovery path.

- **The plan’s “## Out of scope”, immutable-evidence storage:** Consume the prerequisite’s publish and scan APIs without changing storage internals or reproducing their filesystem behavior.

- **The plan’s “## Out of scope”, roadmap and reviewer-owned state:** Do not add a canonical artifact writer, feedback-state change, seed action, Git action, or backend invocation.

- **The plan’s “## Out of scope”, identifier grammar:** Apply receipt-safe admission only through the earlier receipt contracts; do not narrow existing roadmap or local-revision identifiers.

## Deferred

- Receipt schema reference and walkthrough documentation — Step 6 owns the durable format and operator documentation beyond the command reference updated here.

- Broader impact analysis and structural changes — The plan’s out-of-scope boundary keeps route selection, relation analysis, and artifact mutation outside this receipt command.

- Immutable-evidence storage behavior — The prerequisite remains responsible for durable publication, enumeration mechanics, and filesystem failure handling.
