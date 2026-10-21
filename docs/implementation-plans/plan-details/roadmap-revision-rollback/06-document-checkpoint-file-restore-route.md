# Step 6 — Document the revision checkpoint and restore route for operators, and close BACKLOG #394

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step is a documentation-only sweep across six files: it adds an operator-facing description of the roadmap revision checkpoint and its restore route to `ROADMAP_FORMAT.md`, `docs/how-to/roadmap.md`, `RUNBOOK.md`, `CAPABILITIES.md`, and `docs/ARCHITECTURE.md`, then removes the `#394` entry from `BACKLOG.md` once the shipped code and its tests confirm the route is real. Every one of the five doc edits carries the same explicit sentence the plan's Architecture section states: this checkpoint (`plan_tool/roadmap_revision_checkpoint.py`) and its restore runner (`plan_tool/roadmap_revision_rollback.py`) are unrelated to `plan-tool checkpoint list`/`clear`'s create/detail authoring cache (`plan_tool/checkpoint.py`, `plan_tool/cli/checkpoints.py`) — the two share a name and nothing else. No production code changes; the step's only write targets are the six files already declared. On green, an operator who hits a stopped roadmap run can find the restore command from the CLI hint (step 5), from the how-to guide, from the command reference table, and from the schema doc, and the backlog no longer lists this as open work.

## Table of Contents

- [Summary](#summary) — what this step delivers and where the line is drawn
- [Why](#why) — the gap this step closes
- [Input](#input) — the contracts steps 2–5 hand this step
- [Files (creates vs edits)](#files-creates-vs-edits) — what changes, file by file
- [Implementation](#implementation) — the edit to make in each of the six files
- [Tests](#tests) — non-code verification
- [Acceptance criteria](#acceptance-criteria)
- [References](#references)
- [Applicable guardrails](#applicable-guardrails)
- [Deferred](#deferred)

## Why

Steps 1–5 give an operator a real way back from a roadmap stage run that stopped partway: a checkpoint records the pre-run state, a restore runner turns it into a write, an explicit confirmed CLI pair invokes it, and the CLI itself names the restore command at every non-completion exit. None of that is written down anywhere an operator would read before hitting the failure — `ROADMAP_FORMAT.md` has no section for it, `docs/how-to/roadmap.md`'s numbered walkthrough has no step for it, `RUNBOOK.md`'s roadmap command table and workflow section don't mention it, `CAPABILITIES.md`'s `architecture-roadmap` entry doesn't cite the two new modules, and `docs/ARCHITECTURE.md`'s Roadmap section doesn't describe the checkpoint lifecycle. The plan's own title for this step also names a real risk worth heading off in writing: `plan-tool checkpoint list`/`clear` is an existing, differently-scoped subcommand family that happens to share the word "checkpoint," and an operator (or a future contributor extending either one) who conflates the two could reach for the wrong command or the wrong mental model. `BACKLOG.md` #394 is the tracked record of this whole plan; per `docs/TRACKING.md`'s rule that a plan-sourced entry is removed once its work ships, closing it is this step's job now that steps 2–5 (which it depends on) have landed and passed their tests.

## Input

- **Step 2's discard-on-completion invariant** (`plan_tool/roadmap.py:_run_roadmap`) — a checkpoint exists on disk exactly when a run has not completed (`OUTCOME_COMPLETED` / `OUTCOME_COMPLETED_NO_CHANGE` discard it; every other outcome, and any escaping exception, leaves it). This is the fact every doc edit in this step describes as "when a checkpoint exists," not a restated mechanism.
- **Step 3's closed restore contract** (`plan_tool/roadmap_revision_rollback.py:restore_roadmap_revision`) — the five-row matrix (no checkpoint / enrolled / matches last-tracked → restored / matches pre-run → already-restored / anything else → refused, changed since the failed run), the recovery-first ordering under the writer lock, and republishing through the unmodified `publish_roadmap_generation`. This step's docs describe the outcome of each row in plain language; they do not re-derive the sequencing rules step 3's own Implementation section already settled.
- **Step 4's CLI contract** (`plan_tool/cli/roadmap_cmd.py`) — the exact flag spelling `--restore-revision`/`--confirm-restore-revision`, that `-y` is not confirmation, that the pair is exclusive with every other roadmap option, and the exit-code mapping (`0` for `"restored"`/`"already-restored"`, `2` for any `"refused"` reason). `docs/cli/roadmap.md` is step 4's own regenerated output and is not touched here.
- **Step 5's discoverability hint** (step 5's outcome, added to `plan_tool/cli/roadmap_cmd.py`; not yet a resolvable HEAD symbol when this step's own detail is written — confirm its landed name per the note below) — the fact that all four non-completion paths of an ordinary stage run already print the restore command when a checkpoint exists, so the docs this step writes are a second, deliberate discovery surface (read before the failure, or read instead of trusting memory of the printed hint), not the operator's only way to find the command.
- **Landed names win over names this plan suggested.** Steps 1–5's own detail files repeatedly mark specific names (the checkpoint filename, the flag spelling, function names) as recommendations rather than requirements. Before writing any of the six edits below, read the actual landed modules and `cli/roadmap_cmd.py --help` output — grep for `RESTORE_OUTCOME_`, `restore_roadmap_revision`, `--restore-revision`, and the checkpoint's tracked-file constant — and use whatever the code actually calls them. Do not transcribe a name from this detail file or from steps 1–5's detail files without confirming it against HEAD.

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**

- `ROADMAP_FORMAT.md` — extend the source-of-truth banner to name the two new modules; add one new section documenting the checkpoint's tracked inventory and the restore route's five-row matrix.
- `docs/how-to/roadmap.md` — add one new numbered section walking an operator from a stopped run to a completed restore.
- `RUNBOOK.md` — add one row to the roadmap command quick-reference table; add one new subsection to the roadmap workflow walkthrough.
- `CAPABILITIES.md` — add the two new module paths to `architecture-roadmap`'s `surfaces:`, add `survive-interruption` to its `principles:`, add one new prose bullet describing the restore action.
- `docs/ARCHITECTURE.md` — add one new paragraph under the existing "## Roadmap" section describing the checkpoint and restore modules.
- `BACKLOG.md` — delete the `#394` entry.

## Implementation

**`ROADMAP_FORMAT.md`.** The doc's opening blockquote already splits the enforced contract by channel and names the module that owns each one (shape in `roadmap_artifacts.py`, relations in `roadmap_gates.py`, local feedback revision in `roadmap_revision.py`, and so on). Extend that same sentence with a clause naming the checkpoint and restore channel and its two modules, `plan_tool/roadmap_revision_checkpoint.py` and `plan_tool/roadmap_revision_rollback.py`, matching the banner's existing "if this doc and the code disagree, the code wins" framing — this new section inherits that same disclaimer, so it must describe outcomes and shapes, not claim to be the enforcement itself.

Add one new `##` section documenting, in this doc's usual register (a short lead paragraph, then the closed vocabulary or table the schema actually has):

- What creates the checkpoint (any stage run, before its first tracked write) and what discards it (a completed run, or a successful restore) — one checkpoint per roadmap, spanning consecutive runs that did not complete, per step 2's invariant above.
- The tracked inventory: the four stage artifacts, their four baselines, `seed-state.json`, and the recorded brief source — ten files, each carrying a pre-run byte-or-absent value and a last-written byte-or-absent value.
- The restore invocation (`plan-tool roadmap <slug> --restore-revision --confirm-restore-revision`) and its five-row matrix, presented as a table mirroring the plan's own Architecture section (no checkpoint / enrolled / matches last-tracked → restored / matches pre-run → already-restored / anything else → refused).
- One explicit sentence: this checkpoint and restore route are unrelated to `plan-tool checkpoint list`/`clear`'s create/detail authoring cache under `.plan-tool/checkpoints/<plan-slug>/` (`plan_tool/checkpoint.py`, `plan_tool/cli/checkpoints.py`) — the two share the word "checkpoint" and nothing else: not a subcommand family, a storage location, or a lifecycle.

Where to put it is a judgment call, not a fixed slot: the doc's other post-creation operator-action sections — "Local feedback revision contract," "Structural escalation receipts," "Impact-routing analyses" — are the closest topical siblings, and placing the new section near them (before or after any one of the three) keeps every "what can an operator do to an existing roadmap" section together. Add the section's own row to the doc's existing "## See also" list only if it needs a forward pointer other sections don't already give it; that list currently points at sibling FORMAT docs and view modules, not every internal module, so an addition there is optional.

**`docs/how-to/roadmap.md`.** Add one new numbered section to the existing `## 1.` through `## 7.` sequence. The natural slot is right after `## 2. Generate the roadmap` and before `## 3. Inspect the roadmap without calling the backend` — a stopped stage run is the direct continuation of section 2's subject, and renumbering sections 3–7 to 4–8 is a small, mechanical edit — but treat the exact position as a recommendation the implementer can adjust if a different ordering reads better once the section is drafted.

Cover, in the doc's plain-prose-plus-fenced-example style:

- When a checkpoint exists: any way a stage run can stop without completing (an invalid stage, an exhausted attempt budget, an operator interrupt, a crash).
- That the operator does not need to remember this section to find the command: per step 5, `plan-tool roadmap` already prints the exact restore command at the point a run stops, naming the slug and both flags.
- The command itself, in a fenced example matching the doc's existing style:

  ```bash
  plan-tool roadmap my-project --restore-revision --confirm-restore-revision
  ```

- The refusal cases in plain language: no checkpoint to restore, the roadmap is enrolled, or the roadmap changed since the failed run (a later hand edit, another writer's change) — each one changes nothing.
- That a completed run, including one that changed nothing, is never rolled back — matching the plan's own top-level rule, already stated in this file's frontmatter `intent`.
- The same disambiguation sentence as `ROADMAP_FORMAT.md`'s, cross-referencing `RUNBOOK.md`'s "Workflow: recover from an interrupted create/detail run" section by name for anyone who actually wants the `plan-tool checkpoint list`/`clear` authoring cache instead.

**`RUNBOOK.md`.** Two edits:

1. Add one row to the roadmap command quick-reference table (the `| plan-tool roadmap <slug> --enroll-version | ... |`-style table inside "## Command sequence at a glance" or its equivalent), matching the table's existing one-sentence-per-command style: `--restore-revision --confirm-restore-revision`, a short description covering the five-row outcome and that `-y` is not a substitute for the confirm flag.
2. Add one new `###` subsection inside "## Workflow: turn a concept brief into architecture artifacts (`roadmap`)". The existing subsections under that heading walk an operator through reviewing a proposal, redirecting it with feedback, recording structural feedback, and enrolling a root; a subsection on recovering from a run that didn't finish belongs among them. The natural slot is after "### Redirecting a proposal with feedback" and its `####` children and before "### Record structural feedback without revising the roadmap," since both neighbors are about acting on an existing, not-yet-final roadmap — again, a recommendation rather than a fixed requirement. Follow this section's established pattern: a short prose lead, a fenced command example, and a cross-reference to `ROADMAP_FORMAT.md`'s new section by anchor. Include the same disambiguation sentence, and consider adding one forward-pointing sentence inside the existing "## Workflow: recover from an interrupted create/detail run" section too, so an operator who searches for "checkpoint" and lands there first is pointed at the roadmap restore route as well — this closes the disambiguation from both directions, though it is not required if the new subsection alone makes the distinction discoverable.

**`CAPABILITIES.md`.** Three edits to the existing `## Architecture roadmap` entry:

1. Add `plan_tool/roadmap_revision_checkpoint.py` and `plan_tool/roadmap_revision_rollback.py` to the `surfaces:` list, alongside the existing `roadmap_revision_*` siblings already there (`roadmap_revision.py`, `roadmap_revision_patch.py`, `roadmap_revision_publish.py`, `roadmap_revision_run.py`).
2. Add `survive-interruption` to the `principles:` list (currently `converge-on-correct-plan`, `deterministic-non-determinism`). `MISSION.md`'s fourth principle — "state is checkpointed and every stage resumable" — is exactly what this checkpoint/restore route delivers for the roadmap verb, and no capability currently cites it.
3. Add one new prose bullet in the same style as the existing `--escalate-feedback`/`--analyze-escalation`/`--revise-feedback` bullets: the explicit, confirmed pair, the fact it refuses without changing anything when the roadmap is enrolled or has changed since the failed run, and that it restores the ten tracked files to their pre-run bytes on the remaining row.

No new capability entry and no `plan-tool validate` orphan-subcommand risk: `--restore-revision`/`--confirm-restore-revision` are flags on the existing `roadmap` subcommand, not a new subcommand, so the co-location rule that binds a *new subcommand* to a same-step `CAPABILITIES.md` entry does not apply here — only the surfaces list needs the two new module paths so `check_capabilities`'s absent-surface check has something to validate against.

**`docs/ARCHITECTURE.md`.** Add one new bold-lead paragraph under the existing "## Roadmap" section, matching that section's established convention: every capability there is a `**Title (`module.py`, ...).**` paragraph, not a further nested heading — "### Immutable roadmap evidence" is the section's only actual `###`, and everything else (structural escalation receipts, impact-routing analyses, exact-pair structural rewrite, immutable root enrollment, brief-source persistence, stage selection and publication, direct stage-run status, "a stage is a row of data") is a same-level bold paragraph underneath it. Add the new paragraph near the stage-run-lifecycle paragraphs — "Stage selection and publication," "Direct stage-run status," and "A stage is a row of data" are the closest topical fit, since the checkpoint and restore route extends exactly that lifecycle.

Cover: `plan_tool/roadmap_revision_checkpoint.py`'s ten-file inventory and its two byte-or-absent fields per entry, and that it never parses tracked file content; `plan_tool/roadmap_revision_rollback.py:restore_roadmap_revision`'s writer-lock-held, recovery-first sequencing and its five-row matrix; and the CLI surface (`--restore-revision`/`--confirm-restore-revision` in `cli/roadmap_cmd.py`, step 5's non-completion-path hint). Close with a pointer to `ROADMAP_FORMAT.md` for the schema and matrix contract, matching this doc's own convention of ending each capability paragraph that way. Include the disambiguation from `plan-tool checkpoint list`/`clear` here too — this document in particular is read by future contributors deciding where new checkpoint-shaped code belongs, so stating plainly that the two are unrelated is what keeps a future addition from being wired into the wrong one.

**`BACKLOG.md`.** Delete the entire `#394` entry — from its `**#394 — Roll back a roadmap revision that fails or is cut short**` heading line through its own closing `- **Status:** seeded 2026-09-18 (`plan-seeds/roadmap-revision-rollback.md`)` line. It is the last entry in `### A. New capability, well-scoped`, immediately before `### B. Significant UX changes` begins. Per `docs/TRACKING.md`'s rule ("the backlog entry stays in this file until the plan's work ships, then both get removed together"), delete it outright — do not move it to `docs/history/backlog-decisions.md`, which this same plan's own Architecture section cites only for a *withdrawn* decision (the un-enrollment feature), not a shipped one. Do this only after confirming steps 2–5's code and tests actually shipped (see Tests below); the step's own acceptance criterion is "once the route ships and its tests pass," which this step does not itself cause — it only records that it happened.

## Tests

This is a **non-code** step — it changes no production code, adds no test file, and edits no `files:` entry that `enforce_step_tests` would gate a test-authoring requirement against.

### Verification (non-code step)

- Confirm steps 2–5 actually shipped before touching `BACKLOG.md`: `rg -n "restore_roadmap_revision|RevisionRestoreResult|RESTORE_OUTCOME_" plan_tool/` and `rg -n "restore-revision" plan_tool/cli/roadmap_cmd.py` both return real hits, and `plan-tool roadmap --help` (or `docs/cli/roadmap.md`, step 4's regenerated output) lists `--restore-revision`/`--confirm-restore-revision`.
- Every symbol, flag, and filename cited in the five doc edits (`plan_tool/roadmap_revision_checkpoint.py`, `plan_tool/roadmap_revision_rollback.py`, `restore_roadmap_revision`, `--restore-revision`, `--confirm-restore-revision`, the checkpoint's tracked-file constant, the exit-code mapping) matches the landed code at HEAD, not a provisional name from steps 1–5's detail files or from this one.
- `rg -n "#394" BACKLOG.md` returns nothing after the edit, and the file still parses as valid markdown around the deletion boundary (no orphaned list item or dangling section header left behind).
- Every markdown heading added by this step resolves from any cross-reference this step itself writes (`ROADMAP_FORMAT.md#<new-anchor>`, the `RUNBOOK.md` cross-reference to "Workflow: recover from an interrupted create/detail run"): render or hand-derive the GitHub-style anchor and grep the target file for the corresponding `## `/`### ` heading text.
- `plan-tool validate` passes — the capability-catalog check (`plan_tool/capability_catalog.py`) confirms the two newly cited surface paths exist on disk and that `architecture-roadmap`'s `principles:` entries are all valid `MISSION.md` ids.
- `git status` is clean at the end: only the six declared files changed, no stray scratch file left under the repo root.
- Full suite: `uv run pytest tests/ -q -n auto`.

## Acceptance criteria

- `ROADMAP_FORMAT.md`'s source-of-truth banner names `plan_tool/roadmap_revision_checkpoint.py` and `plan_tool/roadmap_revision_rollback.py`, and a new section documents the ten-file tracked inventory, the restore invocation, and its five-row outcome matrix.
- `docs/how-to/roadmap.md` has a new numbered section walking an operator from a stopped run to a completed restore, including the refusal cases and the rule that a completed run is never rolled back.
- `RUNBOOK.md`'s roadmap command quick-reference table has a row for `--restore-revision --confirm-restore-revision`, and its roadmap workflow section has a subsection covering the same restore procedure.
- `CAPABILITIES.md`'s `architecture-roadmap` capability lists both new module paths in `surfaces:`, lists `survive-interruption` in `principles:`, and has a new bullet describing the restore action.
- `docs/ARCHITECTURE.md`'s Roadmap section has a new paragraph describing the checkpoint and restore modules, closing with a pointer to `ROADMAP_FORMAT.md`.
- Every one of the five doc edits states plainly that this checkpoint is unrelated to `plan-tool checkpoint list`/`clear`'s create/detail authoring cache.
- `BACKLOG.md` no longer contains the `#394` entry.
- `plan-tool validate` and `uv run pytest tests/ -q -n auto` both pass after the edit.

## References

- `BACKLOG.md` #394 — the entry this step removes, and its full scope contract (the source this plan was seeded from).
- `docs/TRACKING.md` — the rule that a plan-sourced backlog entry is deleted, not archived, once its work ships.
- `docs/history/backlog-decisions.md` — where a *withdrawn* decision goes; cited here only to show why `#394`, a shipped decision, does not belong there.
- `RUNBOOK.md`'s existing command-families table and "Workflow: recover from an interrupted create/detail run" section, and `plan_tool/cli/checkpoints.py` / `plan_tool/checkpoint.py` — the unrelated `plan-tool checkpoint list`/`clear` family every doc edit in this step must distinguish itself from.
- `docs/implementation-plans/plan-details/roadmap-revision-rollback/01-roadmap-revision-checkpoint-file-that.md` through `05-name-restore-command-when-checkpoint.md` — the landed shape of the checkpoint, restore runner, CLI flags, and discovery hint this step documents; read the actual code over these detail files wherever they differ.

## Applicable guardrails

The plan's `## Scope guardrails` bind this step on several points:

- "No automatic restore, and no restore offered on anything but an explicit command" — every doc edit must describe restore as requiring the explicit, confirmed `--restore-revision --confirm-restore-revision` pair; none may imply an automatic or `-y`-triggered recovery path.
- "No new persisted state except the checkpoint" — the new `ROADMAP_FORMAT.md` section documents exactly one new artifact, the checkpoint file; it must not describe a receipt, an evidence-store record, or any other new sidecar.
- "No change to enrollment, candidates, review seals, promotion, or the `.roadmap-versions/` namespace" — every description of the restore matrix's "enrolled" row must state that restore refuses on an enrolled roadmap, never that it touches enrollment.
- "Eligibility never reads run logs" — no doc edit may describe restore's eligibility as depending on `.plan-tool/runs/` or any run-log content; it is decided entirely from the checkpoint and on-disk file bytes.

The plan's top-level `## Out of scope` also binds the prose: none of the six edits may describe rolling back a completed run, un-enrolling a valid root, or automatic retry/resume after a restore as supported.

## Deferred

- Regenerating `docs/cli/roadmap.md` — step 4's own closing action; this step reads that file as ground truth for the flag names but does not regenerate or hand-edit it.
- Any change to the checkpoint module, the restore runner, the CLI flags, or the discovery hint themselves — steps 1–5; this step documents what they shipped.
- Splitting the restore matrix's three refusal reasons into separate exit codes or separate documented commands — step 4 deliberately maps all three `"refused"` reasons to one exit code, and this step's docs present that as one row, not three.
- Authoring a new `MISSION.md` principle — `survive-interruption` already exists; this step only cites it on `architecture-roadmap`.
- Moving or editing `docs/history/backlog-decisions.md` — that file records withdrawn or reversed decisions; `#394` is a shipped decision and is deleted from `BACKLOG.md` outright, never moved there.
