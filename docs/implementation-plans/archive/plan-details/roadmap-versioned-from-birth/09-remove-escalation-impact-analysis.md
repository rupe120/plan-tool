> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 9 — Remove the escalation, impact-analysis, and --rewrite-structural routes and the modules they alone use

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step removes three CLI routes from `plan_tool/cli/roadmap_cmd.py`: `--escalate-feedback` / `--escalation-reason`, `--analyze-escalation`, and `--rewrite-structural` / `--rewrite-analysis`. It also removes the `--view escalations` and `--view impact-analyses` views. The modules that only those routes use are deleted along with their tests. The key decision is that **deletion follows a caller trace, not the file list**. Three modules the step lists (`plan_tool/roadmap_impact_snapshot.py`, `plan_tool/roadmap_impact_relations.py`, `plan_tool/roadmap_escalation_selection.py`) still have importers in code that survives. Each is deleted only if it is orphaned after the routes go. Otherwise it is trimmed to what the survivors use. On green, no production code can write an escalation receipt or an impact analysis, or run a structural rewrite. Stored receipt and analysis records are left on disk and nothing reads them.

## Table of Contents

- [Why](#why) — what these routes still do and why they cannot coexist with the version store
- [Input](#input) — step 1 and step 8 outputs and the caller trace this step depends on
- [Files (creates vs edits)](#files-creates-vs-edits) — deletions, edits, and the two declared additions
- [Implementation](#implementation) — route removal, module disposition, constraints
- [Tests](#tests) — what is deleted, what is added, and the mutation checks
- [Acceptance criteria](#acceptance-criteria) — observable end state
- [References](#references) — docs and symbols to read
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — work this step leaves to others

## Why

- The three routes admit work through stage baselines and select feedback rows embedded in the top-level artifacts. A stored version carries neither. After steps 3–8, no roadmap has top-level artifacts, so these routes have nothing valid to read.
- Left in place, they keep the legacy readers alive. They also keep a writer in `plan_tool/roadmap_revision_publish.py` (`publish_structural_revision_proof`) that targets the unversioned layout.
- The plan's intent is one stored copy that every command reads. A structural rewrite or an impact analysis against top-level files breaks that.
- The plan's "Out of scope" list names no replacement for structural rewrites, so removal leaves no replacement route.

## Input

- **Step 1 output:** the `BACKLOG.md` #441 inventory lists these routes as removed. Take the removal list from that record. If it disagrees with the caller trace below, the record is wrong. Correct it and raise the disagreement under the plan's stop rule.
- **Step 8 output:** `plan_tool/cli/roadmap_cmd.py` has already lost the working-tree compare path. This step edits the same file after it, so read the landed file.
- **Caller trace (run this first, at HEAD).** The following importers exist outside the step's file list. They set what can be deleted.
  - `plan_tool/roadmap_impact_snapshot.py` is imported by `plan_tool/roadmap_candidate.py`, `plan_tool/roadmap_version_promotion.py`, `plan_tool/roadmap_decision_settlement_enrolled.py`, and `plan_tool/roadmap.py` (a function-local import using `capture_roadmap_impact_snapshot` and `recheck_roadmap_impact_snapshot`). It also supplies the `_binding` / `snapshot_artifacts_match_captured_text` helpers.
  - `plan_tool/roadmap_impact_relations.py` is imported by `plan_tool/roadmap_candidate_context.py` (`resolve_impact_closure`, `ImpactTarget`).
  - `plan_tool/roadmap_escalation_selection.py` is imported by `plan_tool/roadmap_feedback_reopen.py` and `plan_tool/roadmap_decision_settlement.py`.
  - `plan_tool/roadmap_evidence_store.py` is imported by `plan_tool/roadmap_decision_settlement_receipt.py` and `plan_tool/roadmap_decision_settlement_enrolled.py`. It is not in this step's list and must stay.
  - `plan_tool/roadmap_structural_revision.py`, `plan_tool/roadmap_structural_revision_proof.py`, `plan_tool/roadmap_structural_revision_patch.py`, and `plan_tool/roadmap_structural_operations.py` are not in the list. The first one imports `plan_tool/roadmap_escalation.py`, `plan_tool/roadmap_impact_analysis.py`, and the impact snapshot/relations modules, so it cannot survive their deletion.
- **Limit:** a static trace and the test suite show that imports resolve. They do not show that Integration's stored records stay harmless on disk. That is the post-ship hand run.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/roadmap_cmd.py` — remove the three route handlers and the escalation and impact-analysis view handlers, along with their conflict predicates, renderers, parser arguments, and help text. See Implementation.
  - `docs/cli/roadmap.md` — regenerate with `python -m plan_tool.cli_reference --write` after the parser drops the escalation, impact-analysis, and `--rewrite-structural` flags; the full-suite gate runs the drift test in `tests/cli/test_cli_reference.py` at this step.
  - `plan_tool/roadmap_view.py` — remove any escalation or impact reference the trace finds. A grep at HEAD finds none, so this may be a zero-diff file. Say so in the commit if it is.
  - `plan_tool/roadmap_revision_publish.py` — remove `publish_structural_revision_proof`, its helpers (`_require_successful_structural_proof`, `_require_current_proof_binding`, `_structural_stage_table`), and `StructuralRevisionPublicationError` / `StaleStructuralRevisionPublicationError`. Nothing else uses them. Leave every other writer and the guard (`roadmap_writer_guard`, `recover_roadmap_publication`) alone.
  - `CAPABILITIES.md` — remove the three routes and the two views from the `roadmap` capability prose. Remove the deleted modules from its `surfaces:` list. `check_capabilities` fires `absent-surface` on a cited path that is not on disk.
  - `TESTING.md` — remove the structural-revision invoker row and the "Roadmap escalation receipt tests" paragraph.
  - `tests/cli/test_roadmap_cmd.py` — delete the cases for the removed routes and views. Update the module docstring and imports (it imports `plan_tool.roadmap_impact_snapshot` and `plan_tool.roadmap_escalation_run`).
  - `tests/test_roadmap_view.py` — edit only if the trace finds a reference.
  - `tests/test_roadmap_revision_publish.py` — delete the cases for `publish_structural_revision_proof`. This file is **not in the declared list**. It is required because the function it tests is removed.
- **Files deleted outright (route-only):**
  - `plan_tool/roadmap_escalation.py`, `plan_tool/roadmap_escalation_run.py`
  - `plan_tool/roadmap_impact_run.py`, `plan_tool/roadmap_impact_analysis.py`
  - `plan_tool/roadmap_structural_revision_run.py`
  - Tests: `tests/test_roadmap_escalation.py`, `tests/test_roadmap_escalation_run.py`, `tests/test_roadmap_impact_run.py`, `tests/test_roadmap_impact_analysis.py`, `tests/test_roadmap_structural_revision_run.py`
- **Files deleted only if the trace leaves them orphaned (default: trim, do not delete):**
  - `plan_tool/roadmap_impact_snapshot.py` and `tests/test_roadmap_impact_snapshot.py`
  - `plan_tool/roadmap_impact_relations.py` and `tests/test_roadmap_impact_relations.py`
  - `plan_tool/roadmap_escalation_selection.py` and `tests/test_roadmap_escalation_selection.py`
- **Declared additions (outside the step's list, required by the deletions):** `plan_tool/roadmap_structural_revision.py`, `plan_tool/roadmap_structural_revision_proof.py`, `plan_tool/roadmap_structural_revision_patch.py`, and `plan_tool/roadmap_structural_operations.py`, with their tests (`tests/test_roadmap_structural_revision.py`, `tests/test_roadmap_structural_revision_patch.py`, `tests/test_roadmap_structural_revision_proof.py`, `tests/test_roadmap_structural_operations.py`, and the publisher cases in `tests/test_roadmap_revision_publish.py`). Delete them when the trace shows `plan_tool/roadmap_structural_revision_run.py` was their only consumer. If any of them has a surviving importer, keep that module and report it.

## Implementation

**Behavior that must hold when the step is done:**

- **Routes gone.** Passing any of the three removed flags, or either removed `--view` value, is an argparse error. No handler, no conflict predicate, and no renderer for them remains in `plan_tool/cli/roadmap_cmd.py`.
- **No writer remains.** Nothing in `plan_tool/` writes a receipt, an impact analysis, or a structural-revision proof.
- **Stored records left alone.** Existing files under `.plan-tool/evidence/escalations/` and the impact-analysis evidence namespace are not read, validated, migrated, or deleted. The step adds no code that touches them.
- **Everything imports.** `python -c "import plan_tool.cli"` and the full suite succeed with no dangling import.

**Recommended order of work:**

- **1. Run the caller trace and write the result down.** Run a grep by module name and by the symbols each survivor imports. Record per module: delete, trim, or keep. Do this before any deletion, because a green suite after a partial deletion proves only the sites you changed.
- **2. Remove the CLI surface.** In `plan_tool/cli/roadmap_cmd.py`:
  - Remove the `_has_escalation_view` / `_has_impact_analysis_creation` / `_has_impact_analysis_view` predicates, the `*_has_conflict` predicates, `_cmd_roadmap_escalation_receipt`, `_cmd_roadmap_impact_analysis`, `_cmd_roadmap_escalations_view`, `_cmd_roadmap_impact_analyses_view`, and every `_render_*escalation*` / `_render_*impact*` helper.
  - Remove the two `--view` choices, and the pre-dispatch branches in `cmd_roadmap` that call these handlers or reject their companion options.
  - Remove the `--rewrite-structural` handler path and its `--rewrite-analysis` partner.
  - Update the module docstring paragraphs that describe the three routes.
  - Re-check the argparse mutual-exclusion and "meaningful only alongside `--view`" checks. They still have to reject invalid combinations after two choices disappear.
- **3. Delete route-only modules and their tests.** Delete the modules listed above. Then delete `plan_tool/roadmap_revision_publish.py`'s structural-proof writer.
- **4. Dispose of the three shared modules, one at a time.**
  - Trace each survivor import. A survivor that needs only part of a module keeps that part.
  - Prefer trimming in place over moving code. Do not create a new module to host the survivors' symbols, because a move changes shared ownership and belongs to separate work.
  - If trimming would make a survivor import from a module whose name no longer fits, leave the name and file a `BACKLOG.md` entry. Do not rename here.
  - Remove only symbols with no remaining caller, including the evidence-version and receipt symbols that exist only for the deleted routes.
  - Keep each trimmed module's own tests for the symbols that stay. Delete the cases for removed symbols.
- **5. Sweep the vocabulary.** Search for `escalat`, `impact analysis`, `impact-analys`, `receipt`, `rewrite-structural`, and `structural revision` in `CAPABILITIES.md`, `TESTING.md`, `docs/how-to/roadmap.md`, and the module docstrings of survivors. Edit prose that still describes the removed routes. The `docs/how-to/roadmap.md` rewrite belongs to a later step; only report what remains there.
- **6. Run the repo guards.** `plan-tool validate` runs the capability check. `tests/test_duplication.py` fails if a deletion removes one of the deliberately duplicated helpers it pins. A failure from either is a signal to re-read the trace, not to edit the guard.

**Constraints and gotchas:**

- **Do not delete by name.** `roadmap_impact_snapshot.py` sounds route-only and is not: candidate storage, promotion, and enrolled decision settlement import it.
- **`roadmap_evidence_store.py` stays.** Decision settlement imports it. It is outside this step's list on purpose.
- **Do not touch `plan_tool/run_log.py` events.** The `roadmap_impact_*` run-log event classes and the hand-copied reason list that cites `roadmap_escalation_selection.ReceiptReason` belong to the run-log contract. Changing them is a separate decision.
- **`plan_tool/jira.py` mentions `roadmap_impact_snapshot.py` in a comment only.** Leave the comment unless the file is deleted. If it is, make the comment true.
- **No new route.** Do not add a replacement for structural rewrite or revision restore (the plan's "Out of scope" list).
- **Smallest change.** Delete code. Do not add a compatibility shim or a "this route was removed" message beyond argparse's own unknown-argument error.

## Tests

### Tests for this step

All of these must be green before the step is finished. Run `uv run pytest tests/ -q -n auto`, then the `-m "not integration"` loop.

- `tests/cli/test_roadmap_cmd.py::test_removed_roadmap_flags_are_rejected_by_the_parser` — each of `--escalate-feedback`, `--analyze-escalation`, and `--rewrite-structural` exits with an argparse error and invokes no orchestrator.
- `tests/cli/test_roadmap_cmd.py::test_removed_views_are_not_accepted_view_choices` — `--view escalations` and `--view impact-analyses` are rejected, and the remaining `--view` choices still parse.
- `tests/cli/test_roadmap_cmd.py::test_view_companion_option_rejection_is_unchanged_for_remaining_views` — the "`--id` only with `--view index`" style combination checks still reject invalid input after the view list shrank.
- `tests/test_roadmap_revision_publish.py` — the cases for `publish_structural_revision_proof` are deleted. A new case, `test_structural_proof_publisher_is_gone_and_other_publishers_remain`, asserts the removed names are absent from the module and the surviving publishers are still importable.
- `tests/test_roadmap_view.py` — runs unchanged. It is the check that the view loader still works for an enrolled roadmap.
- **Survivor-seam tests (existing, must still pass unchanged):** the suites for `plan_tool/roadmap_candidate.py`, `plan_tool/roadmap_version_promotion.py`, `plan_tool/roadmap_feedback_reopen.py`, and `plan_tool/roadmap_decision_settlement*.py`. They are the only evidence that trimming the shared modules did not break a survivor.
- `tests/test_capability_catalog.py` (or the `plan-tool validate` capability check) — no `absent-surface` finding for a deleted path.
- **Mutation check:** restore one deleted import in a survivor and confirm the suite goes red. Then restore one removed argparse flag and confirm `test_removed_roadmap_flags_are_rejected_by_the_parser` goes red.

## Acceptance criteria

- `plan-tool roadmap <slug> --escalate-feedback x:y --escalation-reason prose` exits non-zero with an argparse error. The same holds for `--analyze-escalation` and `--rewrite-structural`.
- `plan-tool roadmap <slug> --view escalations` and `--view impact-analyses` are rejected.
- `rg -n "escalat|impact_analys|rewrite.structural" plan_tool/cli/roadmap_cmd.py` returns nothing.
- `plan_tool/roadmap_escalation.py`, `plan_tool/roadmap_escalation_run.py`, `plan_tool/roadmap_impact_run.py`, `plan_tool/roadmap_impact_analysis.py`, and `plan_tool/roadmap_structural_revision_run.py` do not exist.
- `rg -n "publish_structural_revision_proof" plan_tool tests` returns nothing.
- For each of the three shared modules, the commit message states whether it was deleted, trimmed, or kept, and names the surviving importers that decided it.
- No file under `.plan-tool/evidence/` is read or written by any removed or retained code path in this step. `rg -n "evidence/escalations" plan_tool` returns nothing.
- `CAPABILITIES.md` cites no path that is not on disk. `plan-tool validate` reports no capability finding.
- `python -c "import plan_tool.cli"` succeeds. The full suite is green, with no test deleted that pinned a surviving behavior.
- `uv run pytest tests/cli/test_cli_reference.py -q` passes with `docs/cli/roadmap.md` regenerated.

## References

- `BACKLOG.md` #441 — source entry, the step 1 inventory, and the scope contract.
- `ROADMAP_FORMAT.md` § "Immutable candidate-version authority" — accepted head and the direct-reader boundary.
- `ROADMAP_FEEDBACK_FORMAT.md` — ledger states, to confirm no ledger behavior changes here.
- `plan_tool/roadmap_versions.py` — `load_accepted_version`, the one read path that remains.
- `plan_tool/roadmap_revision_publish.py` — the guard and surviving publishers.
- `docs/how-to/roadmap.md` — the operator procedure that a later step rewrites.
- `TESTING.md` — the seam-by-seam table, to keep current.

## Applicable guardrails

- **The plan's "Out of scope", candidate/review-seal/promotion/version-record contracts.** Trimming the shared modules must not change what `plan_tool/roadmap_candidate.py`, `plan_tool/roadmap_version_promotion.py`, or the survivors' tests assert. The survivor-seam tests are the check.
- **The plan's "Out of scope", ledger format.** `plan_tool/roadmap_feedback_reopen.py` and decision settlement read feedback state. This step may only fix their imports, not their behavior.
- **The plan's "Out of scope", version-store route for structural rewrites.** No replacement route may be added here. A recurring need becomes a new backlog entry.
- **The plan's "Out of scope", tool-driven migration.** The step does not read, convert, or delete stored receipts or analyses.
- **The plan's intent, one stored copy read by every command.** The step removes the readers that bind to stage baselines and embedded feedback, and adds none.

## Deferred

- Rewrite of `docs/how-to/roadmap.md` and the other operator docs that describe the removed routes — owned by the plan's documentation step, which this step does not replace.
- Removal of the `roadmap_impact_*` run-log event classes and the hand-copied reason list in `plan_tool/run_log.py` — a run-log contract change; file a `BACKLOG.md` entry if the trace shows they are now dead.
- Renaming any shared module the trace trims (for example, a module that kept only snapshot helpers) — shared ownership change, separate work.
- Deleting or migrating stored receipt and analysis records in existing roadmaps — out of scope; Integration is converted by hand after this ships.
