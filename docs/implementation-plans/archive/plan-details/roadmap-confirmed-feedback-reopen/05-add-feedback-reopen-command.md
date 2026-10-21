> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Add the confirmed feedback reopen command

## Summary

Expose the step-4 confirmed reopen operation through one explicit `roadmap` command pair. Update `plan_tool/cli/roadmap_cmd.py` to track both flags, reject incomplete or companion modes, and dispatch only to the landed feedback reopen operation. Update the generated CLI reference, top-level help catalog, feedback summary, and named operator guides so they describe the narrow exception without weakening ordinary reviewer ownership. On green, a confirmed command reopens one safe selected row through the existing operation, and its next escalation receipt has a new identity. The confirmation is the operator's authority for unavailable evidence; the command does not classify it.

## Table of Contents

- [Summary](#summary) — The completed command surface and observable result.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — The missing operator path and stale guidance this step fixes.
- [Input](#input) — Upstream reopen and receipt contracts this CLI consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — The files changed, including one required scope addition.
- [Implementation](#implementation) — Exclusive parsing, dispatch, output, and documentation rules.
- [Tests](#tests) — CLI, generated-reference, and end-to-end coverage.
- [Acceptance criteria](#acceptance-criteria) — Checkable completion conditions.
- [References](#references) — Primary parsing and test-fixture guidance.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this command.
- [Deferred](#deferred) — Work that remains outside this operator surface.

## Why

`plan_tool/cli/roadmap_cmd.py:cmd_roadmap` already gives receipt creation, impact analysis, structural rewrite, and local revision their own exclusive preflight paths, but it has no route to the confirmed reopen operation from step 4. Meanwhile `RUNBOOK.md:### Redirecting a proposal with feedback` and the named guides describe every reopen as a raw reviewer edit. Without this step, the bounded recovery and step 3’s fresh-receipt proof remain unreachable, and operators receive instructions that are too broad for the one permitted exception.

## Input

- **Step 3 receipt contract:** Step 3 makes `plan_tool/roadmap_escalation_run.py:run_roadmap_escalation_receipt` build and recheck nonce-aware receipts. This step must prove the first receipt after a successful reopen differs from the older receipt without recreating identity logic in the CLI.

- **Step 4 reopen contract:** Step 4 lands the confirmed, redacted operation in `plan_tool/roadmap_feedback_reopen.py`. Read its landed public entry point and terminal result shape before wiring it; that code owns selector validation, safety checks, source admission, mutation, and refusal details.

- **Existing exclusive-mode pattern:** `plan_tool/cli/roadmap_cmd.py:_TrackExclusiveOption`, `_option_occurrences`, and the existing `*_has_conflict` predicates retain repeated options for runner-owned preflight. Reuse that pattern so the CLI can distinguish an omitted companion from a repeated one.

- **Generated reference and package help:** `plan_tool.cli_reference:render_reference` generates `docs/cli/roadmap.md`, while `plan_tool/cli/__init__.py` supplies the Roadmap catalog text checked against `tests/cli/package_surface_help.golden.txt`.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/cli/roadmap_cmd.py` — Register and dispatch the exclusive reopen pair; extend conflict checks and redacted result rendering.
  - `plan_tool/cli/__init__.py` — Required scope addition: add the compact reopen invocation to the top-level Roadmap help catalog that produces the golden snapshot.
  - `docs/cli/roadmap.md` — Regenerate from the updated parser; do not hand-edit it.
  - `README.md` — Update the `### 0. roadmap` review-channel guidance with the one confirmed exception.
  - `RUNBOOK.md` — Update `### Redirecting a proposal with feedback` so ordinary reviewer reopening remains the rule and the confirmed command is the sole exception.
  - `CAPABILITIES.md` — Update `## Architecture roadmap` to describe the bounded operator action without describing a general recovery capability.
  - `docs/how-to/roadmap.md` — Add the command to `## Command sequence at a glance` and correct `## 5. Ask for a revision with feedback`.
  - `docs/how-to/roadmap-demo.md` — Correct the `### feedback rows — say what is wrong and let the model answer` lifecycle guidance without turning the demo loop into a general recovery procedure.
  - `tests/cli/test_roadmap_cmd.py` — Cover parsing, exclusivity, dispatch, redaction, and the fresh-receipt path.
  - `tests/cli/package_surface_help.golden.txt` — Rebaseline the top-level `--help` snapshot after its catalog source changes.

## Implementation

- **Foundational logic: exclusive confirmed reopen dispatch.** Add one `roadmap` action that accepts exactly one `--reopen-feedback SELECTOR` and exactly one `--confirm-feedback-reopen`, then delegates to step 4’s operation or refuses without another roadmap action running.

- **Track every occurrence.** Use `plan_tool/cli/roadmap_cmd.py:_TrackExclusiveOption` for both flags, including the confirmation flag. Give the confirmation flag an unset default so `_option_occurrences` can distinguish absent, single, and repeated appearances; a plain `store_true` default would lose that fact.

- **Keep the pair outside broad-mode tracking.** Do not make the reopen action a `_TrackRoadmapMode` option. It is an exclusive action like `--analyze-escalation` and `--rewrite-structural`, not a stage, seed, view, or re-entry mode.

- **Make the reopen route own parsed conflicts.** Add a presence helper and a narrow conflict predicate beside `_has_structural_rewrite` and `_structural_rewrite_has_conflict`. Require one selector and one confirmation occurrence, and reject every broad mode, view, evidence action, local revision, and baseline-enrollment action beside the pair. `-y` remains only the seed-promotion acknowledgement and must never count as reopen confirmation.

- **Sweep every sibling predicate.** Update `_escalation_creation_has_conflict`, `_escalation_view_has_conflict`, `_impact_analysis_creation_has_conflict`, `_impact_analysis_view_has_conflict`, `_structural_rewrite_has_conflict`, `_revise_feedback_has_conflict`, and the enrollment conflict path so a future dispatch reorder cannot let the new action bypass another exclusive route.

- **Dispatch before any competing roadmap action.** In `plan_tool/cli/roadmap_cmd.py:cmd_roadmap`, route any occurrence of either reopen flag to its dedicated branch before ordinary mode dispatch. A malformed parser value remains argparse’s responsibility; a missing, repeated, or conflicting pair reaches the reopen operation as a rejected mode and must not start a stage run, local revision, evidence action, seed action, or view.

- **Keep the CLI thin.** Forward the selected value, confirmation fact, resolved repository root, and plans directory using the landed step-4 signature. Do not duplicate selector parsing, existing-record checks, source reads, safety checks, nonce creation, writer locking, or artifact mutation in `plan_tool/cli/roadmap_cmd.py`.

- **Render only redacted terminal facts.** Add a small renderer and exit-status mapping based on the step-4 result contract. Do not echo the selector, prior response, reopen nonce, or record contents; return the runner’s terminal status rather than inferring success from display text.

- **Correct lifecycle guidance in the command itself.** Update `_feedback_summary_lines` to replace its absolute “no command … reopen” claim with the precise rule: ordinary close, defer, and reopen remain reviewer edits, and `--reopen-feedback` is the one explicitly confirmed exception. Do not say that the command detects invalid evidence.

- **Generate the parser reference.** Treat `plan_tool/cli/roadmap_cmd.py:register` as the source for `docs/cli/roadmap.md`. Regenerate the file through `plan_tool.cli_reference:render_reference` after help text settles, and preserve the reference generator’s normal table and usage formatting.

- **Update operator guidance narrowly.** In the named guides, show the exact two-flag command as the only tool-driven reopen exception. Keep close, defer, and ordinary reopening as reviewer edits, and state that `--revise-feedback` does not gain reopen authority. Do not add evidence inputs, a generic retry recipe, or a second lifecycle-edit command.

- **Update top-level help at its source.** Add one concise Roadmap catalog line in `plan_tool/cli/__init__.py`, then rebaseline `tests/cli/package_surface_help.golden.txt`. Updating only the golden file would leave `plan-tool --help` and its checked-in source inconsistent.

## Tests

### Tests for this step

- `tests/cli/test_roadmap_cmd.py:test_feedback_reopen_options_preserve_absent_single_and_repeated_occurrences` — The parser retains absent, one, and repeated selector and confirmation occurrences without treating an absent confirmation as present.

- `tests/cli/test_roadmap_cmd.py:test_feedback_reopen_help_documents_the_exact_confirmed_pair` — Help includes both flags and makes explicit that confirmation is required.

- `tests/cli/test_roadmap_cmd.py:test_feedback_reopen_dispatches_only_the_confirmed_operation` — A valid pair forwards the selected value and true confirmation once, without reaching the broad roadmap runner.

- `tests/cli/test_roadmap_cmd.py:test_feedback_reopen_incomplete_or_repeated_pair_reaches_only_reopen_preflight` — Missing or repeated selector or confirmation values produce the reopen preflight refusal and do not fall through to another action.

- `tests/cli/test_roadmap_cmd.py:test_feedback_reopen_rejects_every_companion_mode_without_other_dispatch` — Stage, seed, view, receipt, analysis, rewrite, local-revision, enrollment, `-y`, `--mode`, and `--id` companions are rejected before their own dispatch paths run.

- `tests/cli/test_roadmap_cmd.py:test_existing_exclusive_mode_predicates_reject_the_feedback_reopen_pair` — Every existing exclusive-mode predicate treats the new pair as incompatible.

- `tests/cli/test_roadmap_cmd.py:test_feedback_reopen_does_not_treat_yes_as_confirmation` — `-y` alone, or beside the selector, cannot authorize the reopen.

- `tests/cli/test_roadmap_cmd.py:test_feedback_reopen_renders_only_redacted_terminal_facts` — CLI output omits the selector, prior response, and reopen nonce while preserving the operation’s exit status.

- `tests/cli/test_roadmap_cmd.py:test_feedback_reopen_existing_record_is_refused_without_artifact_change` — The real CLI path refuses an intact reopen record and leaves the selected artifact unchanged.

- `tests/cli/test_roadmap_cmd.py:test_feedback_reopen_first_escalation_receipt_differs_from_the_prior_receipt` — A real confirmed reopen followed by `run_roadmap_escalation_receipt` creates a new receipt identity while retaining the earlier immutable receipt.

- `tests/cli/test_roadmap_cmd.py:test_feedback_summary_names_the_confirmed_reopen_exception` — Normal roadmap output preserves reviewer ownership for ordinary lifecycle moves and identifies the exact confirmed exception without claiming evidence classification.

- `tests/cli/test_cli_reference.py:TestCliReferenceDrift.test_every_generated_file_matches_disk` — The regenerated `docs/cli/roadmap.md` matches the parser output.

- `tests/cli/test_package_surface.py:TestHelpGoldenSnapshot.test_help_matches_golden` — The updated package help source matches `tests/cli/package_surface_help.golden.txt`.

Green-before-done gate: every listed test and `uv run pytest tests/ -q -n auto` must pass.

## Acceptance criteria

- `plan-tool roadmap <slug> --reopen-feedback <selector> --confirm-feedback-reopen` invokes only the landed step-4 operation.

- A missing or repeated selector or confirmation, `-y` without the dedicated confirmation flag, or any companion roadmap action returns a refusal status without dispatching another action.

- Existing exclusive commands reject the reopen pair through their own conflict predicates.

- The CLI performs no backend call, stage run, seed action, evidence action, view, or local revision for a reopen request.

- An intact reopen record is refused through the real command path without changing artifact bytes.

- CLI output exposes only redacted terminal facts and never includes the selector, prior response, or reopen nonce.

- The first escalation receipt after a successful reopen has a different identity from the earlier receipt for that row.

- `docs/cli/roadmap.md` is generated from the parser, `tests/cli/package_surface_help.golden.txt` matches top-level help, `_feedback_summary_lines`, and every named operator guide identifies the action as the sole confirmed exception to ordinary reviewer reopening without claiming it classifies unavailable evidence.

## References

- [argparse — Parser for command-line options and argumentshttps: — Use this for custom action, default, and exclusive-option behavior.

- [pytest fixtures: explicit, modular, scalablehttps: — Use isolated on-disk fixtures for the real command and receipt-identity regression.

## Applicable guardrails

- **The plan’s “## Plan intent”, bounded recovery proof:** Expose only the named confirmed reopen and preserve its fresh-receipt proof.

- **The plan’s “## Step intent”, exclusive operator action:** Keep all safety and mutation decisions in step 4; the CLI only admits the exact flag pair and routes it.

- **The plan’s “## Out of scope”, evidence and provenance limits:** Do not add evidence paths, history reads, response classification, or operator-attestation inputs.

- **The plan’s “## Out of scope”, lifecycle limits:** Preserve reviewer ownership for ordinary close, defer, and reopening, and do not expand `--revise-feedback`.

- **The plan’s “## Out of scope”, command and publication limits:** Do not add another command, view, writer, journal, recovery flow, or transaction surface.

## Deferred

- General evidence recovery and response provenance — Require a separately scoped plan rather than expanding this confirmed exception.

- Raw reopen-record alteration detection and external-writer serialization — Remain outside this command’s bounded proof and publication contract.
