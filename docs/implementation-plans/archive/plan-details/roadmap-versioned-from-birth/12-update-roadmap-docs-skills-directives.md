> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 12 — Update the roadmap docs, skills, directives, and generated CLI reference for the version-only store, and remove BACKLOG #441

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step sweeps every live developer doc, skill, and directive so none names a removed roadmap route, and so each describes the version-only store that steps 3–11 ship. It rewrites `docs/how-to/roadmap.md` as the operator procedure. That page must cover the resume directory and the remedy for a brief-digest refusal, the post-head stage refusal, the no-published-version refusal with its hand-conversion procedure, the `--compare` default, `INDEX.md`, and `--reopen-ledger-feedback`. It regenerates `docs/cli/roadmap.md` from the parser and extends `tests/test_roadmap_format.py` so the removed-route vocabulary cannot return. The last edit removes the #441 entry from `BACKLOG.md`. On green, a grep for the removed flags over the live docs finds only dated history that has earned its place, and the doc guards pass.

## Table of Contents

- [Why](#why) — what the docs still say after the code changes
- [Input](#input) — what the landed steps supply and what this step cannot check
- [Files (creates vs edits)](#files-creates-vs-edits) — no new files; edits per file
- [Implementation](#implementation) — sweep method, per-topic content, BACKLOG removal
- [Tests](#tests) — guard changes and verification checks
- [Acceptance criteria](#acceptance-criteria) — observable end state
- [References](#references) — docs and symbols to read
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — work this step leaves out

## Why

- Steps 3 and 6–11 remove `--from-stage`, `--confirm-brief-rebind`, `--enroll-version`, `--enroll-baselines`, `--migrate-feedback-ledger`, `--restore-revision` (with `--confirm-restore-revision`), `--reopen-feedback`, the escalation and impact-analysis routes, `--rewrite-structural`/`--rewrite-analysis`, and the `escalations`/`impact-analyses` views. The docs still describe all of them, including the command list at the top of `docs/how-to/roadmap.md` and the usage line in `docs/cli/roadmap.md`.
- Every doc also states the old model: top-level `0N-*.md` files, `source.json`, stage baselines, the `migration-pending` ledger state, and a working-tree `--compare` target. A reader following them reaches a refusal the docs never explain.
- `integrations/claude/SKILL.md`, `integrations/codex/SKILL.md`, and `integrations/cursor/SKILL.md` carry the roadmap route content. `CLAUDE.md` is injected into every session, so a stale roadmap paragraph misleads each run.
- `BACKLOG.md` #441 must be removed when the work ships. Step 1 marked it plan-authored; this step is the final docs and status step the entry's reconciliation requirement names.

## Input

- **Landed code wins.** Read flag names, error class names, file names, and refusal wording from the code as steps 2–11 landed it: `plan_tool/roadmap_stage_resume.py` (resume directory name constant), `plan_tool/roadmap_index.py` (`INDEX.md` content and status vocabulary), `NoPublishedRoadmapVersionError` (created by step 6 in `plan_tool/roadmap_seed_manifest.py`; it does not exist at HEAD), `plan_tool/roadmap_compare_run.py`, and `plan_tool/cli/roadmap_cmd.py`. Where this detail or an earlier detail names something differently, the landed name wins.
- **Step 1 record:** the #441 inventory (converted, removed, unchanged routes; the `migration-pending` finding). Use it as the removal checklist, and verify each item against the parser.
- **Step 3 refusals:** the stage run refuses once an accepted head exists, refuses a folder with no head that holds any pre-head state (top-level `0N-*.md` files, a ledger, `seed-state.json`, a populated `.roadmap-versions/`, draft seeds), and refuses a changed brief with the operator's remedy (a held stage that is unreadable or fails its re-gate is regenerated with a warning, not refused). Quote the landed wording.
- **Step 6 refusal:** `NoPublishedRoadmapVersionError` covers a folder with no accepted head and points at hand conversion when top-level files exist. The doc must also cover an enrolled folder that still has leftover top-level files, `source.json`, `.roadmap-baselines/`, and `.roadmap-rollbacks/`; take that behavior from the landed code, not from the plan text.
- **Generated reference:** `docs/cli/roadmap.md` comes from the argparse parser through `python -m plan_tool.cli_reference --write`. It is drift-guarded by `tests/cli/test_cli_reference.py`, so edit the parser never and the file never by hand.
- **Limit:** the guards check vocabulary, examples, and symbols. They cannot show the hand-conversion procedure works on a real folder such as Integration's. A reviewer must follow it once on a throwaway copy.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `docs/how-to/roadmap.md` — rewrite the command list and the operator procedure; add the sections listed under Implementation.
  - `docs/cli/roadmap.md` — regenerate only; no hand edits.
  - `ROADMAP_FORMAT.md` — drop the removed-route modules from the source-of-truth banner and the "What writes them" prose; delete § "Revision checkpoint and restore" and § "Stage re-entry selection and bounded feedback" and the escalation and impact-analysis route material. State the gate-function count from `plan_tool/roadmap_gates.py` as landed.
  - `ROADMAP_FEEDBACK_FORMAT.md` — delete the `migration-pending` lifecycle text and the "Legacy migration" section; state that every ledger is ledger-native; keep `--reopen-ledger-feedback` among the reviewer actions.
  - `docs/how-to/roadmap-demo.md` — update the stage-run section (no top-level artifacts; the version store and `INDEX.md` are what the run leaves) and any re-entry or `--enroll-version` step.
  - `docs/ARCHITECTURE.md` — update the Roadmap section: the comparison route's target resolution, the removed escalation, impact, and structural-rewrite leaves, and the new `roadmap_stage_resume.py` and `roadmap_index.py` leaves. Keep the BACKLOG #406 import-graph note only if still true.
  - `integrations/shared/DIRECTIVES.md` — rewrite the `# Roadmap` section and delete `## Roadmap non-stage routes` and `## Roadmap rewrite`.
  - `integrations/claude/SKILL.md`, `integrations/codex/SKILL.md`, `integrations/cursor/SKILL.md` — same roadmap route content, same edit in all three.
  - `README.md` — trim the roadmap command block to the surviving routes.
  - `RUNBOOK.md` — rewrite the roadmap workflow and recovery recipes.
  - `DATA_CONTRACT.md` — remove removed-route run-log events and `source.json` schema text; keep the seed-action lifecycle section.
  - `CLAUDE.md` — rewrite the leading roadmap paragraphs and the "What this is" roadmap paragraph for the version-only store; fix the `ROADMAP_FORMAT.md` and `docs/how-to/roadmap.md` reference bullets. This file's rule changes need `architect`-tier review through the pull-request flow, which the plan's PR must request.
  - `tests/test_roadmap_format.py` — delete or rewrite guards that pin removed routes; add the guards under Tests.
  - `BACKLOG.md` — delete the #441 entry; reconcile the cross-references listed under Implementation.

## Implementation

**Method.** Enumerate before editing, and write the list down.

- **Class:** a live doc names a removed route, a removed file model, or a removed ledger state.
- **By identifier:** search the live docs for each removed flag, view name, module name, `source.json`, `migration-pending`, `0N-*.md`, `RoadmapStage.artifact_path`, `stage baseline`, and `--from-stage`.
- **By vocabulary:** also search for the concept's words in other phrasings: "re-enter at", "re-gate", "enrolled", "unenrolled", "legacy roadmap", "working tree" (for `--compare`), "baseline", "rebind", "checkpoint", "restore".
- **Decide per hit:** delete it, or keep it as dated, past-framed history. Keep history only for a don't-reopen decision, a don't-repeat failure, or a live legacy contract. Mark any kept history with its date.
- **Scope of the sweep:** limit it to this step's file list. A hit in a file outside the list is not edited here; record it under Deferred.

**Content that must exist when done** (one home per fact; link rather than restate):

- **Resume directory:** `docs/how-to/roadmap.md` states that a failed first run leaves only the resume directory under `.plan-tool/runs/<slug>/`, that a later run resumes from the first stage that is missing or fails its re-gate, and that a changed brief refuses with a remedy: restore the brief, delete the named `roadmap-stage-resume/` directory by hand (never the run-log directory that also holds the run logs), or start a successor slug. The directory name and behavior are owned by `plan_tool/roadmap_stage_resume.py`. Do not document it as a user-editable input.
- **Post-head stage refusal:** state that the stage run refuses once an accepted head exists, and what to use instead (candidate and feedback routes).
- **No-published-version refusal and hand conversion:** state the refusal and its causes. Give the hand-conversion procedure for both folder cases. For a folder with no accepted head, it is moving or deleting the files the refusal lists (top-level `0N-*.md` files, `feedback-ledger.yaml` (deleting it discards its feedback rows), `seed-state.json`, a populated `.roadmap-versions/`, draft seeds), or starting a successor slug. For an enrolled folder with leftovers, it is deleting the top-level `0N-*.md` files, `source.json`, `.roadmap-baselines/`, and `.roadmap-rollbacks/`. Take the steps from the landed refusal text and step 3's pre-head-state refusal. State that no tool-driven migration exists. Also state the closed list of roadmap-folder files: the feedback ledger, `seed-state.json`, `INDEX.md`, the draft-seed directory, and `.plan-tool/evidence/` (inside the roadmap folder, not the repository's run-log `.plan-tool/`).
- **`--compare` default:** an omitted `--comparison-target` means the active candidate; with none active, the command refuses and asks for `--comparison-target`. An omitted `--comparison-base` still means the accepted head.
- **`INDEX.md`:** generated, human-facing, rewritten after every version-store change, read by no command. Document the version statuses as `plan_tool/roadmap_index.py` defines them.
- **`--reopen-ledger-feedback`:** documented as the replacement for the removed `--reopen-feedback`, in `docs/how-to/roadmap.md` and `ROADMAP_FEEDBACK_FORMAT.md`.

**Constraints that must hold:**

- **Source-of-truth banners:** keep `ROADMAP_FORMAT.md`'s banner shape and only drop the modules that no longer exist. Name no symbol that is not at HEAD.
- **Anchor safety:** before renaming or deleting a heading, search the corpus for inbound links to its anchor (for example `docs/how-to/roadmap.md` § 5 is cited from `integrations/shared/DIRECTIVES.md`). Fix every inbound link in this step's files.
- **Skill triplet:** the three `SKILL.md` roadmap edits stay textually parallel. Only the backend-specific words differ.
- **Reference-doc bullets in `CLAUDE.md`:** change clauses tersely; depth stays in the pointed-at doc.
- **Forward-looking voice:** write present and future tense. Do not narrate what was removed except as a dated, past-framed note a reader needs.
- **Documentation style:** follow `docs/reference/documentation-style.md` for any rewritten live developer doc.

**Regenerating the CLI reference.** Land the parser changes first (steps 3 and 8–11), then run `python -m plan_tool.cli_reference --write` and commit the result. Do not hand-edit `docs/cli/roadmap.md`.

**BACKLOG #441 removal.**

- Delete the #441 entry only after the docs sweep passes, because its verification clause lists the end state.
- Sweep both halves for the removed entry: its identifier (`#441`) and its vocabulary ("version store only", "no command reads stale top-level artifacts"). `BACKLOG.md` cross-references #441 from other entries (for example one noting a docs table is "#441's docs sweep"); update or remove each one with the reason, and fix any arc or router listing in `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md` that names #441. If the arc file is outside this step's list, record it under Deferred instead of editing it.
- A promoted ticket stub, if one exists, goes with the entry per `docs/TRACKING.md` § "Promotion stubs".
- Keep any deferred follow-up (structural rewrite or revision-restore routes if they recur) as new, separate entries; the plan's "Out of scope" names no replacement.

## Tests

Tests: `tests/test_roadmap_format.py` (approx. 6 deleted or rewritten, approx. 4 added), `tests/cli/test_cli_reference.py` (unchanged; runs as the drift guard).

- **Deleted or rewritten:** the guards that pin removed-route guidance (the baseline-enrollment, source-admission, brief-drift, and structural-guidance tests, such as `test_baseline_enrollment_prefix_recovery_guidance_matches_the_landed_contract` and `test_non_stage_brief_drift_guidance_*`) and any that read a removed `ROADMAP_FORMAT.md` section. Read each before deleting: keep a test whose subject still ships, and rewrite one whose subject changed.
- `test_live_roadmap_docs_name_no_removed_route` — parametrized over this step's doc files; asserts none contains a removed flag token outside a dated, past-framed history line, the `--reopen-ledger-feedback` replacement note, or the hand-conversion procedure. Assert keys (the exact flag tokens), not words.
- `test_removed_route_guard_covers_every_flag_the_parser_dropped` — asserts the removed-token list contains no flag still registered in the roadmap parser, and each listed flag is absent from it; this stops the guard flagging a live flag or going stale.
- `test_how_to_documents_the_version_only_refusals_and_defaults` — asserts `docs/how-to/roadmap.md` mentions `INDEX.md`, `--reopen-ledger-feedback`, `--comparison-target`, and the landed `NoPublishedRoadmapVersionError` wording's anchor phrase.
- `test_skill_roadmap_route_content_is_identical_across_backends` — asserts the roadmap section of the three `SKILL.md` files matches after backend-specific words are normalized; pins the skill triplet rule.
- `test_removed_backlog_441_entry_is_absent_and_not_cross_referenced_as_open` — asserts `BACKLOG.md` has no `**#441 —` heading and no other entry calls #441 pending.
- **Mutation check:** reintroduce `--from-stage` into one doc and confirm `test_live_roadmap_docs_name_no_removed_route` goes red; restore the entry heading for #441 and confirm the BACKLOG test goes red.

### Verification (non-code step)

The only code-adjacent edit is the guard file; the rest is docs. The test-authoring gate does not apply to the doc edits, so these checks substitute:

1. `uv run pytest tests/test_roadmap_format.py tests/cli/test_cli_reference.py tests/test_data_contract.py -q` passes.
2. `python -m plan_tool.cli_reference --write` produces no further diff in `docs/cli/roadmap.md`.
3. `rg -n -e '--from-stage|--enroll-version|--enroll-baselines|--migrate-feedback-ledger|--restore-revision|--reopen-feedback |--escalate-feedback|--analyze-escalation|--rewrite-structural|--confirm-brief-rebind|source\.json|migration-pending'` over this step's doc files returns only dated, past-framed lines, the replacement note, and the hand-conversion procedure, each reviewed.
4. `rg -n 'uv run plan-tool roadmap|plan-tool roadmap' docs/how-to/roadmap.md` lists only flags present in `docs/cli/roadmap.md`.
5. Every symbol cited in the edited docs exists at HEAD (`rg` each); no raw line numbers are cited.
6. Every relative link and heading anchor touched or inbound to a changed heading resolves.
7. A reviewer follows the hand-conversion procedure once on a throwaway copy of a legacy folder and confirms the refusal text and the steps agree.
8. `git status` shows only this step's files.

## Acceptance criteria

- No live doc in this step's file list names a removed roadmap flag, view, or module outside dated, past-framed history, the replacement note for `--reopen-feedback`, and the hand-conversion procedure.
- `docs/how-to/roadmap.md` documents: the resume directory and the brief-digest remedy, the post-head stage refusal, the no-published-version refusal and the hand-conversion procedure for both folder cases, the `--compare` default and its no-active-candidate refusal, `INDEX.md`, and `--reopen-ledger-feedback`.
- `ROADMAP_FEEDBACK_FORMAT.md` has no `migration-pending` state and no legacy-migration section.
- `docs/cli/roadmap.md` matches the parser: `uv run pytest tests/cli/test_cli_reference.py -q` passes.
- The roadmap section of the three `SKILL.md` files is textually parallel and names no removed route.
- `CLAUDE.md`'s roadmap paragraphs and reference bullets describe the version-only store and name no removed route.
- `BACKLOG.md` has no #441 entry, and no other entry or arc router in this step's files refers to it as open.
- `uv run pytest tests/ -q -n auto` passes.

## References

- `BACKLOG.md` #441 — source entry, decision, and scope contract (removed by this step).
- `ROADMAP_FORMAT.md` § "Immutable candidate-version authority" — accepted head and direct-reader boundary; the sections on revision checkpoint and stage re-entry are the removed text.
- `ROADMAP_FEEDBACK_FORMAT.md` — ledger states and reviewer actions.
- `docs/reference/documentation-style.md` — structure and review checklist for live developer docs.
- `docs/TRACKING.md` § "Promotion stubs" — how a promoted entry's stub is removed.
- `plan_tool/roadmap_versions.py` (`load_accepted_version`), `plan_tool/roadmap_stage_resume.py`, `plan_tool/roadmap_index.py`, `NoPublishedRoadmapVersionError` (created by step 6 in `plan_tool/roadmap_seed_manifest.py`; it does not exist at HEAD), `plan_tool/roadmap_compare_run.py`, `plan_tool/cli/roadmap_cmd.py` — landed names and wording to document.
- `plan_tool/cli_reference.py` — generator for `docs/cli/roadmap.md`.

## Applicable guardrails

- **The plan's "## Out of scope", tool-driven migration:** document hand conversion only. Do not describe or imply a migrate command.
- **The plan's "## Out of scope", read-only top-level mirror:** do not document `INDEX.md` or any other file as a mirror of the accepted version, or as something a command reads.
- **The plan's "## Out of scope", dates or timestamps in `INDEX.md`:** the `INDEX.md` description must not mention dates or timestamps in index or version records.
- **The plan's "## Out of scope", structural rewrite and revision restore:** state no replacement route. Mention the removals as removals; any recurring need becomes a new backlog entry, not doc text.
- **The plan's "## Out of scope", candidate/promotion/version-record and ledger-format contracts:** edit prose only; change no contract. Ledger edits are limited to deleting legacy migration text.
- **The plan intent (one stored copy, every command reads the accepted version):** every rewritten passage must be consistent with it; no passage may suggest a second readable copy.

## Deferred

- Hits for removed-route vocabulary in docs outside this step's file list (for example `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md`, other `docs/` pages, `CONTRIBUTING.md`) — not edited here; file a backlog entry if the sweep finds any.
- A tool-driven migration for existing roadmaps — the plan's "Out of scope" leaves Integration to hand conversion after this ships.
- Moving this file's dated measurements into `docs/evidence/` — separate scoped work noted in `CLAUDE.md`'s header.
