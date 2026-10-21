> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 9 — Wire an explicit exact-pair structural rewrite command with no local or broad fallback

## Summary

Add the sole structural-rewrite command form to `plan_tool/cli/roadmap_cmd.py`: `--rewrite-structural RECEIPT_FINAL --rewrite-analysis ANALYSIS_FINAL`. Extend parser occurrence tracking, exclusive dispatch, safe terminal rendering, command help, the package help snapshot, and `docs/cli/roadmap.md`. The key decision is that the CLI forwards only the two explicitly supplied evidence finals to step 8’s runner; it never substitutes a selector, scans for a current record, invokes local revision, or starts broad stage work. On green, a valid pair reaches the structural runner once, while every missing, repeated, or companion-mode form is rejected through its redacted preflight path.

## Table of Contents

- [Summary](#summary) — Reviewer-level outcome and affected surfaces.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Why the structural runner needs its own CLI boundary.
- [Input](#input) — Existing command routing and step 8 contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Exact file footprint.
- [Implementation](#implementation) — Parser, dispatch, rendering, and exclusivity rules.
- [Tests](#tests) — Focused CLI and help-snapshot coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this command.
- [Deferred](#deferred) — Work owned by other steps or later scope.

## Why

`plan_tool/cli/roadmap_cmd.py:cmd_roadmap` currently offers a selector-based local revision through `run_local_feedback_revision` and evidence creation through `run_roadmap_impact_analysis`, but neither command carries one immutable receipt-analysis pair into the bounded structural runner from step 8. Without a separate exclusive surface, an operator can only infer evidence from a selector or fall into an existing roadmap mode, which weakens the one-artifact write boundary before preflight can record a safe refusal.

## Input

- **Step 8 runner:** Use the public structural runner and redacted result contract that step 8 lands in `plan_tool/roadmap_structural_revision_run.py`. Read its landed argument and exit-code contract rather than recreating preflight, backend, or lifecycle behavior in the CLI.

- **Existing exclusive routes:** `plan_tool/cli/roadmap_cmd.py:cmd_roadmap`, `_revise_feedback_has_conflict`, `_impact_analysis_creation_has_conflict`, and `_escalation_creation_has_conflict` establish that one route owns parseable conflicts and passes `mode_rejected` to its typed runner.

- **Occurrence tracking:** `plan_tool/cli/roadmap_cmd.py:_TrackEscalationOption`, `_receipt_option_occurrences`, and `_impact_analysis_occurrences` preserve repeated option facts while keeping direct `argparse.Namespace` callers compatible.

- **Invoker seam:** `plan_tool/cli/roadmap_cmd.py:cmd_roadmap` accepts `plan_tool/roadmap.py:StageInvoker` for tests. Step 8’s injected invoker is the only structural backend seam this command forwards.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/cli/roadmap_cmd.py` — Register the exact-pair flags, route them to step 8’s runner, enforce exclusive-mode ownership, map its redacted result to the command exit, and describe the command in the module overview.
  - `plan_tool/cli/__init__.py` — Add the structural-rewrite command form to the roadmap section of the top-level help description.
  - `tests/cli/test_roadmap_cmd.py` — Cover parsing, occurrence preservation, direct dispatch, conflict ownership, interruption, safe output, and no-fallback behavior.
  - `tests/cli/package_surface_help.golden.txt` — Refresh the intentional top-level help snapshot.
  - `docs/cli/roadmap.md` — Document the exact command form and its exclusive CLI behavior in `## Usage` and `## Options`.

## Implementation

- **Foundational logic:** Route exactly one explicit receipt-analysis pair to the structural runner, with no evidence inference or alternate command path.

- **Add two companion options, not a broad-mode option.** In `plan_tool/cli/roadmap_cmd.py:register`, add `--rewrite-structural RECEIPT_FINAL` and `--rewrite-analysis ANALYSIS_FINAL`. Reuse the occurrence-preserving action pattern near `_TrackEscalationOption` so each final remains visible when an option is absent, repeated, or supplied through a direct namespace. Do not add either flag to `_TrackRoadmapMode`: the two flags must coexist, while broad modes remain incompatible.

- **Make cardinality part of the structural preflight.** A structural request is valid at the CLI boundary only when each option occurred exactly once and no companion roadmap mode appeared. Preserve the raw final strings only long enough to pass the final supplied values plus `mode_rejected` to step 8’s runner. The runner validates their 64-hex shape before any evidence load and records malformed values only as a fact-free `mode-rejected` event; the CLI must not normalize names, compare evidence, select a replacement value, or render the raw values.

- **Give structural rewrite dispatch priority.** In `plan_tool/cli/roadmap_cmd.py:cmd_roadmap`, detect either structural option before the impact-analysis, escalation, local-revision, view, and broad-mode branches. Resolve only the normal repository and plans paths needed to call the runner, then delegate once. This keeps missing, repeated, malformed, and mixed forms on the structural runner’s redacted preflight path instead of letting another command interpret part of the request.

- **Sweep every exclusive predicate.** Add structural-option presence to `_revise_feedback_has_conflict`, receipt creation and inspection conflict checks, and impact-analysis creation and inspection conflict checks. Add one structural conflict predicate that rejects all existing exclusive routes and `_broad_mode_companions_present` facts. Keep the predicate-level protections even though structural dispatch runs first, so a future reorder cannot make another mode accept the pair.

- **Keep the runner as the only executor.** Add a small structural dispatch helper beside `_cmd_roadmap_revise_feedback` and `_cmd_roadmap_impact_analysis`. Forward the injected `invoker` only when `cmd_roadmap` received one, leaving the step 8 production invoker intact otherwise. Do not call `run_local_feedback_revision`, `run_roadmap`, a view helper, a seed helper, or an evidence scan as a substitute path.

- **Render only runner-approved facts.** Return the structural runner’s landed exit mapping directly and print a terse terminal summary from fields its result explicitly marks safe. Never echo either supplied final, reviewer content, prompt text, reply text, artifact content, or error detail. Keep the outer `KeyboardInterrupt` handling consistent with the local-revision branch: return `130` and do not continue into another roadmap mode.

- **Update the public command description narrowly.** In `plan_tool/cli/__init__.py` and `docs/cli/roadmap.md`, show the complete two-option form and state that both finals are explicit, required once, and exclusive. Keep broader workflow-selection guidance out of this step; step 10 owns that documentation.

- **Refresh generated help deliberately.** Update `tests/cli/package_surface_help.golden.txt` from the parser’s actual output after the public text settles. Preserve the existing `tests/cli/test_package_surface.py:test_help_matches_golden` normalization contract rather than hand-editing only the roadmap excerpt.

## Tests

### Tests for this step

- `tests/cli/test_roadmap_cmd.py:test_structural_rewrite_options_preserve_absent_single_and_repeated_occurrences` — asserts both flags retain every occurrence and direct namespaces keep compatible defaults.

- `tests/cli/test_roadmap_cmd.py:test_structural_rewrite_pair_is_not_a_broad_mode` — asserts the two required flags parse together without entering `_roadmap_mode_occurrences`.

- `tests/cli/test_roadmap_cmd.py:test_structural_rewrite_dispatches_only_the_explicit_pair_to_the_structural_runner` — asserts the runner receives the slug, both supplied finals, resolved paths, and no inferred selector or evidence record.

- `tests/cli/test_roadmap_cmd.py:test_structural_rewrite_forwards_the_injected_invoker_only_when_supplied` — asserts tests can inject the runner seam while ordinary dispatch keeps the runner’s production invoker.

- `tests/cli/test_roadmap_cmd.py:test_structural_rewrite_invalid_pair_cardinality_reaches_only_structural_preflight` — covers a missing member and repeated member, asserting `mode_rejected` is true and no local, view, or broad handler runs.

- `tests/cli/test_roadmap_cmd.py:test_structural_rewrite_malformed_final_identity_reaches_redacted_mode_rejection` — forwards an invalid final only to the runner, which returns the fact-free rejection without evidence inspection or raw-value output.

- `tests/cli/test_roadmap_cmd.py:test_structural_rewrite_forwards_every_companion_mode_to_structural_preflight` — covers local revision, receipt creation, impact analysis, inspection, confirmation, brief, and broad-mode companions without evidence selection or fallback.

- `tests/cli/test_roadmap_cmd.py:test_existing_exclusive_mode_predicates_reject_the_structural_pair` — keeps receipt, impact, inspection, and local predicates safe against a future dispatch-order change.

- `tests/cli/test_roadmap_cmd.py:test_structural_rewrite_renders_only_redacted_runner_fields_and_returns_its_status` — asserts safe terminal facts render, the runner’s exit code is returned, and unsafe supplied values never reach output.

- `tests/cli/test_roadmap_cmd.py:test_structural_rewrite_interrupt_returns_130_without_broad_fallback` — asserts an interruption cannot continue into any other roadmap action.

- `tests/cli/test_roadmap_cmd.py:test_help_documents_the_exact_structural_rewrite_pair` — asserts both option names and their required-pair relationship appear in roadmap help.

- `tests/cli/test_package_surface.py:test_help_matches_golden` — verifies `tests/cli/package_surface_help.golden.txt` matches the complete top-level parser output.

Every test above must be green before this step is considered finished:

`uv run pytest tests/cli/test_roadmap_cmd.py tests/cli/test_package_surface.py -q`

## Acceptance criteria

- `plan-tool roadmap <slug> --rewrite-structural RECEIPT_FINAL --rewrite-analysis ANALYSIS_FINAL` parses as one dedicated structural-rewrite request.

- The CLI forwards only the two explicit final values, resolved paths, and the optional injected invoker to step 8’s runner; it does not derive a selector, current evidence final, route, or write target.

- Missing or repeated pair members and every companion roadmap action reach structural preflight as a rejected mode and do not call local revision, broad stage execution, seed work, views, or evidence inspection.

- Existing local revision, receipt, impact-analysis, and inspection conflict predicates reject the structural pair if dispatch order changes later.

- Structural terminal output contains only runner-approved facts, returns the runner’s exit code, and never echoes supplied finals or content-bearing diagnostic data.

- `plan_tool/cli/__init__.py`, `docs/cli/roadmap.md`, and `tests/cli/package_surface_help.golden.txt` show the same exact-pair syntax and exclusivity rule.

- `uv run pytest tests/cli/test_roadmap_cmd.py tests/cli/test_package_surface.py -q` passes.

## Applicable guardrails

- **The plan’s “Plan intent,” one-artifact rewrite boundary:** Keep the CLI as a thin command boundary. It may invoke the selected runner but must not add selection, proof, or write behavior.

- **The plan’s “Step intent,” explicit-evidence boundary:** Require both immutable finals from the operator and preserve them as the sole evidence inputs.

- **The plan’s “## Architecture,” route and final-identity boundary:** Do not treat an impact route, evidence directory, selector, timestamp, or current record as permission to choose a pair or widen the write set.

- **The plan’s “## Out of scope,” local and broad fallback boundary:** Do not alter the local-revision route, start stage re-entry, or add a generic structural editor while wiring this command.

## Deferred

- **Structural runner implementation and lifecycle outcomes** — Step 8 owns the backend, preflight, proof, publication, and redacted result contract; this step only exposes its landed interface.

- **Broader workflow-selection documentation** — Step 10 owns the format, capability, walkthrough, and operator guidance outside this command’s reference page.

- **Generic, cross-artifact, or broad structural work** (`74b73f49705a852b50f557668e68847846dfbb86c7128a8a3a3e8a8c026fd252`) — The plan’s `## Out of scope` routes this beyond the exact-pair command.
