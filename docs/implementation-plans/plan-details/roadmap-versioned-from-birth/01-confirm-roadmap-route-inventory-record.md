# Step 1 — Confirm the roadmap route inventory and record it on BACKLOG #441

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This non-code step runs one caller trace over the roadmap modules. It confirms or corrects the plan's converted, removed, and unchanged route lists, the `source.json` reader list, and the module-deletion dispositions. It also checks whether any roadmap is in the `migration-pending` ledger state. The only file edited is `BACKLOG.md`: the result goes on the #441 entry, and #441 is marked plan-authored. No production code changes. On green, #441 carries a checked inventory that steps 2–10 can rely on, and any surviving `source.json` reader has either been ruled out or raised under the plan's stop rule.

## Table of Contents

- [Why](#why) — why the trace comes before any deletion
- [Input](#input) — what the trace reads and what it cannot prove
- [Files (creates vs edits)](#files-creates-vs-edits) — the one file edited
- [Implementation](#implementation) — trace procedure, findings so far, what to record on #441
- [Verification (non-code step)](#verification-non-code-step) — how to check the recorded result
- [Acceptance criteria](#acceptance-criteria) — observable end state
- [References](#references) — docs and symbols to read
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — work this step leaves to later steps

## Why

- The plan deletes a large amount of legacy roadmap code (the stage baselines, the revision checkpoint, the legacy publishers, `source.json`, the escalation and impact-analysis chain). Its route lists come from one code reading.
- A wrong disposition (a route marked removed that still has a live reader, or a `source.json` reader nobody listed) is cheap to fix now and expensive once steps 3–10 have built on it.
- `BACKLOG.md` #441 is the durable record of the scope contract. It must say what the plan will do and that the plan exists, so the entry is not picked up as unstarted work.

## Input

- **Plan body:** the "Route disposition" bullets (converted, removed, unchanged) and the "Inventory first" bullet in the plan's `## Architecture`. These are the claims under test.
- **Source entry:** `BACKLOG.md` #441, including its six-route list under "Why" and its "In scope" list.
- **Code at HEAD:** `plan_tool/roadmap*.py`, `plan_tool/create.py`, `plan_tool/cli/roadmap_cmd.py`, `plan_tool/cli/authoring.py`, `plan_tool/run_log.py`.
- **Limit — static trace only:** a grep shows where code reads a path, not whether a given roadmap on disk is in a given state. The `migration-pending` check below can only inspect code and tracked files. It cannot inspect Integration or any other consuming repo's roadmap folders.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `BACKLOG.md` — on the #441 entry, add the recorded inventory (confirmed or corrected lists, `source.json` reader list, ledger-state finding) and mark the entry plan-authored with the plan's path, `docs/implementation-plans/2-roadmap-versioned-from-birth.md`.

## Implementation

**Procedure.** Make one pass over the code, write down the result per item, then edit #441. Do not delete or change any code.

- **Trace by identifier and by vocabulary.** Search the symbol names and also the concept's words: "top-level artifact", "stage baseline", "enroll", "unenrolled", "recorded brief".
- **Route list.** For every CLI flag and view the plan names as converted, removed, or unchanged, find its handler in `plan_tool/cli/roadmap_cmd.py` and the orchestrator it calls. Confirm each lands in the list the plan puts it in. Any flag the parser registers that appears in none of the three lists must be classified and added.
- **Top-level artifact reads.** `RoadmapStage.artifact_path` and the `domain_path` / `constraints_path` / `components_path` / `plans_path` helpers in `plan_tool/roadmap_artifacts.py` are the top-level readers. The #441 verification requires none left in production code, so list every call site and say which step removes or converts it.

**Findings from the trace at HEAD** (the implementer re-runs the greps; HEAD wins on disagreement):

- **`stage.artifact_path(...)` call sites** are in these modules: `plan_tool/roadmap.py` (the stage loop and enrollment helpers), `plan_tool/roadmap_revision_publish.py`, `plan_tool/roadmap_revision_run.py`, `plan_tool/roadmap_escalation_run.py`, `plan_tool/roadmap_impact_run.py`, `plan_tool/roadmap_impact_snapshot.py`, `plan_tool/roadmap_structural_revision.py`, `plan_tool/roadmap_feedback_reopen.py`, `plan_tool/roadmap_decision_settlement.py`, `plan_tool/roadmap_decision_settlement_receipt.py`, `plan_tool/roadmap_decision_settlement_run.py`.
- **The settlement and reopen sites need a per-site call.** In `plan_tool/roadmap_decision_settlement.py`, the top-level read is the `else` branch of the accepted-version check, which is the unenrolled branch the plan removes. Check each of the other settlement and reopen sites the same way: confirm it is either an unenrolled-only branch or a live read that a step must convert. Record each site with its answer.
- **Direct readers of the other `path` helpers:** `plan_tool/roadmap.py` (the `--apply` and seed code that calls `load_plans_artifact(plans_path(...))`), `plan_tool/cli/authoring.py` (`_confirm_invalidated_roadmap_seed`), `plan_tool/create.py` (`_load_roadmap_research_targets`, reading `02` and `03`), `plan_tool/cli/roadmap_cmd.py`, `plan_tool/roadmap_feedback_ledger_run.py`, `plan_tool/roadmap_revision_checkpoint.py`. `plan_tool/roadmap_view.py:load_roadmap` already reads the accepted version first. Confirm which of its `*_path` references remain on a non-enrolled branch.
- **`source.json` readers.** The path comes from `plan_tool/roadmap_artifacts.py:brief_source_path` (`BRIEF_SOURCE_FILENAME`). Production references at HEAD:
  - `plan_tool/roadmap.py` — brief resolution and rebind (`_resolve_brief_path`), the writer `_write_brief_source`, and the first-write run-log call.
  - `plan_tool/roadmap_source.py:read_recorded_brief_source`.
  - `plan_tool/roadmap_impact_snapshot.py` (through `read_recorded_brief_source`).
  - `plan_tool/roadmap_revision_checkpoint.py` (through `brief_source_path`).
  - `plan_tool/run_log.py` (`RoadmapSourceRecorded` and its emitter).
- **One correction to check against the plan.** The plan lists "the uncalled revision run" as a `source.json` reader. At HEAD `plan_tool/roadmap_revision_run.py` has no `brief_source_path` or `read_recorded_brief_source` reference, and no production module imports it (only `tests/test_roadmap_revision_run.py`, `tests/test_roadmap_source_identity.py`, and `tests/test_roadmap_revision_checkpoint.py` do). Confirm both facts. If they hold, the plan's reader list drops it, and the module goes on the module-deletion list as uncalled rather than as a reader.
- **Stop rule.** If the trace finds a `source.json` reader that no plan step removes or replaces (for example a candidate, ledger, or seed route), record it on #441 and stop. Surface it to the plan owner instead of continuing; the plan's "Inventory first" bullet makes this the trigger.

**`migration-pending` check.**

- **Code facts to record:** the state is produced only by `plan_tool/roadmap.py:_ledger_state_for_enrollment` (when a captured snapshot carries feedback or removals) and consumed in `plan_tool/roadmap_feedback_ledger.py:check_ledger_processing_ready`, which returns `migration-required`. A comment in `plan_tool/roadmap_decision_settlement.py` also refers to it. List any other consumer the grep finds.
- **Roadmaps on disk:** no tracked file in this repository holds a roadmap ledger (`git ls-files` shows none). Say so explicitly on #441. For Integration, record the answer only if the operator has checked its ledger by hand; otherwise write "not checked from this repo; Integration is converted by hand after this ships" rather than leaving the question unstated.

**Module-deletion dispositions.** For each module the plan deletes (the stage-baseline and revision-checkpoint code, `plan_tool/roadmap_revision_publish.py` legacy publishers, `plan_tool/roadmap_revision_rollback.py`, the impact and escalation chain, the structural-revision modules), confirm the plan step that deletes it and that no step still calls code after its deleting step. This is the plan's "Retirement split" rule applied to the actual import graph.

**Recording on #441.**

- Add the confirmed lists (or the corrected ones) as a short sub-list under the entry, naming each flag or view once. Keep it the one place the list lives; later steps cite it.
- Mark the entry as plan-authored. Copy the wording and placement of an existing plan-authored backlog entry. Search `BACKLOG.md` for "plan-authored" and follow the nearest one.
- Roadmap items are owner-tracked and not promoted to Jira, so add no ticket key. State "no ticket key (roadmap items are owner-tracked)" rather than leaving the field absent.
- Use present and future tense. Do not leave historical narration about the trace.
- Leave the "Decision (2026-10-06, owner)" block and the scope contract fields unchanged.

## Verification (non-code step)

This is a non-code step; no unit tests apply. The test-authoring gate keys on `change_type`, which is `non-code` here. Verify the artifact instead:

1. Every flag and view in the plan's converted, removed, and unchanged lists appears once on #441, and every flag registered in `plan_tool/cli/roadmap_cmd.py` that touches roadmap content appears in exactly one list.
2. Re-run `grep -rn "artifact_path(" plan_tool` and confirm every hit is named on #441 with the step that removes or converts it.
3. Re-run `grep -rn "brief_source_path\|read_recorded_brief_source\|source\.json" plan_tool` and confirm the reader list on #441 matches the hits, including the revision-run correction.
4. Confirm #441 states the `migration-pending` finding in explicit words, including "no tracked roadmap ledger in this repo".
5. Confirm #441 is marked plan-authored and cites the plan path, and that its scope-contract fields are untouched (`git diff BACKLOG.md` shows additions only inside the #441 entry).
6. Confirm `git status` shows no file changed other than `BACKLOG.md`.

## Acceptance criteria

- `BACKLOG.md` #441 lists every roadmap route as converted, removed, or unchanged, with no flag in two lists and none unlisted.
- The `source.json` reader list on #441 matches `grep -rn "brief_source_path\|read_recorded_brief_source" plan_tool` at HEAD, and says whether the revision run is a reader.
- Every production `stage.artifact_path` call site is named on #441 with the step that handles it.
- #441 states whether any roadmap is in the `migration-pending` state and how that was established, or states that it was not checked and why.
- #441 is marked plan-authored with the plan's path.
- `git diff --stat` shows only `BACKLOG.md` changed.
- If a surviving `source.json` reader was found, #441 records it and the step stops there (stop rule); otherwise #441 says none was found.

## References

- `BACKLOG.md` #441 — source entry, decision, and scope contract.
- `ROADMAP_FORMAT.md` § "Immutable candidate-version authority" — accepted head and direct-reader boundary.
- `ROADMAP_FEEDBACK_FORMAT.md` — ledger states, including `migration-pending`.
- `plan_tool/roadmap_artifacts.py` — `brief_source_path`, `BRIEF_SOURCE_FILENAME`, the `*_path` helpers.
- `plan_tool/roadmap_versions.py` — `load_accepted_version`, `version_directory_path`.
- `plan_tool/roadmap_feedback_ledger.py` — `check_ledger_processing_ready`.

## Applicable guardrails

- **The plan's "## Out of scope" list** applies in full. This step changes no candidate, promotion, review-seal, ledger-format, or version-record contract, and adds no migration or mirror; it records an inventory only.
- **The plan's intent** (one stored copy, every command reads the accepted version) is the test for any disposition this step corrects. A correction must move a route toward that intent, not away from it.
- **The step's own intent** limits the edit to confirming lists and dispositions and marking #441. Do not rewrite the #441 scope contract or the owner decision.
- **The Stop rule in the plan's "Inventory first" bullet** applies to any `source.json` reader that no step replaces.

## Deferred

- Deleting any code, flag, or test — steps 3–10 own the removals; this step touches no code.
- A tool-driven migration of existing roadmaps — the plan's "## Out of scope" list excludes it; Integration is converted by hand after this ships.
- Checking Integration's ledger state beyond what the operator reports — the repo cannot see it.
- Consolidating the duplicated `artifact_path` readers — this is a deletion plan, not a consolidation; any new duplication finding goes to `BACKLOG.md` with machine-verified evidence.

## Tests

_(stub: model omitted this section — fill in manually)_

