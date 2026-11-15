# Step 6 — Rewrite the `--commit` docs and the backlog entry to match footprint staging

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step edits three files: `docs/how-to/pipeline/detail.md`, `docs/how-to/pipeline/run.md` and `BUG_BACKLOG.md`. It makes them say what steps 2–5 shipped: each `--commit` surface stages and commits only its verb's footprint, then checks that the footprint is clean. In `detail.md` it deletes the "per-step `git add -A` is only safe while no prior step left the tree dirty" invariant. In `run.md` it rewrites the two flow-diagram lines, the archive note and the `.gitignore` note. In `BUG_BACKLOG.md` it shrinks the originating entry to the residual gap. That gap is that `run --commit` can still commit a concurrent write made during the backend call, because the backend's writes are recorded only as a path-name git delta. The step also records any other surface steps 2–5 could not convert, with the reason. If nothing is deferred, the entry is removed. On green, `rg 'git add -A' docs/how-to plan_tool/cli` returns no claim that `--commit` stages everything.

## Table of Contents

- [Why](#why) — which statements are false after steps 2–5
- [Input](#input) — what steps 2–5 must have landed and the sites to rewrite
- [Files (creates vs edits)](#files-creates-vs-edits) — the three edited files
- [Implementation](#implementation) — the edits per file and the constraints
- [Tests](#tests) — verification for this non-code step
- [Acceptance criteria](#acceptance-criteria) — observable checks
- [References](#references) — docs and symbols to read
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — work this step leaves out

## Why

After steps 2–5, `commit_all` and `_commit_green_step` stage `git add -A -- <paths>`. The how-to docs still say `--commit` stages everything and that per-step staging is safe only while the tree is clean. Those claims are now false, and the "safety invariant" argues for a constraint that no longer exists. The BUG_BACKLOG entry still describes the whole-tree defect as open. Operators and audits read these files as current behavior, so the stale text must go in the same change that makes it stale.

## Input

- **Steps 2–5 must be landed.** The footprint rules, help text and landed behavior live in their code; read `plan_tool/cli/authoring.py`, `plan_tool/cli/completeness_cmd.py`, `plan_tool/cli/manifest.py` and `plan_tool/cli/run_cmd.py:_commit_green_step` and let them win over this description and over sibling detail files.
- **`docs/how-to/pipeline/detail.md`, "Committing the result (`--commit`)":** the clean-tree-gate bullet mentions `git add -A`, and the "Safety invariant" bullet describes the skip-after-failure rule and the concurrent/split routing to the end-of-run commit. The "Residual sweep" and "Hook-aware" bullets stay.
- **`docs/how-to/pipeline/run.md` sites at HEAD (found with `rg -n 'git add -A'`):**
  - Two flow-diagram lines that read `git add -A + one commit per green step` (single-step path and `--all` sweep path).
  - The "`--archive` before `--commit`" note that says the green commit's `git add -A` captures the archive move.
  - The streams note that says the directory's own `.gitignore` stops `run --commit`'s `git add -A` from staging it.
- **Not a rewrite target:** `docs/cli/*.md` is generated and covered by the step 2–5 help-text edits; this step only checks it with `tests/cli/test_cli_reference.py`.
- **`BUG_BACKLOG.md` entry:** "`--commit` stages the whole working tree with `git add -A`, so a file another process changes during the run lands in the verb's commit". It has the usual scope-contract fields (Files, Symptom, Fix, Approach, Verification, Route).
- **Unverified, confirm first:** whether steps 2–5 each converted their surface in full. Read each landed commit and the step's own Deferred bullets. Anything they left unconverted becomes a named residual in the backlog entry.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `docs/how-to/pipeline/detail.md`: drop the "Safety invariant" bullet and the `git add -A` wording in the clean-tree bullet; describe footprint staging for the per-step, batch and residual commits.
  - `docs/how-to/pipeline/run.md`: rewrite the two flow-diagram lines, the "`--archive` before `--commit`" note and the streams `.gitignore` note.
  - `BUG_BACKLOG.md`: rewrite the originating entry as the deferred residual (or remove it).

## Implementation

**`detail.md`.**
- State what each commit stages: the plan file, the plan's `plan-details/<slug>/` directory and the project lessons directory. Check this against the footprint helper step 2 landed.
- Replace the clean-tree bullet's rationale with the true one: the precondition stays, and the commit no longer depends on it to avoid sweeping in unrelated files.
- Delete the safety-invariant bullet and the orphan-debris reasoning. Keep one sentence only if the landed code still skips later per-step commits after a failure; verify against `plan_tool/cli/authoring.py` and say exactly what the code does. The same check covers the concurrent (`--jobs>1`) and split paths: say they commit at end-of-run only if that is still true.
- Add one short bullet on the post-commit clean check: a footprint path still dirty after the commit makes the command exit non-zero and names the path. Keep the "Hook-aware" bullet.

**`run.md`.**
- Diagram lines: replace `git add -A + one commit per green step` with a footprint form, for example `commit the step's footprint (plan, plan-details, archive outputs, changed paths) + clean check`. Keep the surrounding SKIP and failure annotations true. If a line mentions the archive move being captured, keep that, since the archive outputs are in the footprint.
- "`--archive` before `--commit`": reword so the footprint, not a whole-tree add, captures the plan move and manifest edit. Keep the ordering point and the follow-up-run point, which still hold.
- Streams note: reword to say the directory is gitignored and `commit_all` skips gitignored entries with a warning, so the file is never staged. Keep "unredacted", "no size cap" and the `runs clear` text unchanged.
- Check the other `run.md` statements about the `--commit` precondition and "left dirty" recovery against step 5's landed fail-closed behavior, and edit only those that are now wrong.

**`BUG_BACKLOG.md`.**
- Retitle the entry for the residual, for example "`run --commit` can still commit a file another process writes during the backend call". Before renaming, grep for inbound links to the old heading's anchor (`rg -n 'stages-the-whole-working-tree' .`) and fix any hit.
- Keep Symptom, Files, Approach, Verification and Route in the entry's existing field layout. Rewrite Symptom to the residual only: the backend's writes are recorded only as a git delta of path names, so a concurrent write during the call to a path the backend did not write is committed only when that path is also in the delta, and a path already dirty before the call cannot be told apart from a backend edit. Take the exact boundary from step 5's landed behavior and its Deferred bullets; do not restate more than they establish.
- Drop the 2026-07-31 near-miss narrative unless it still illustrates the residual. If kept, date it and write it as past.
- Add one bullet per other surface steps 2–5 could not convert, each with its reason (for example, "needs new footprint bookkeeping"). If every surface converted, say none remain.
- Fix: say what would close the residual (a record of the paths the backend itself wrote). Do not specify it, and keep the plan's fence on new tracking subsystems.
- Remove the entry outright only if steps 2–5 left nothing deferred, including the `run` residual. The `run` residual exists by the plan's own fence, so expect the entry to stay.

**Constraints.**
- Write in the present tense; mark any kept history as dated and past.
- Do not edit code, help text or `docs/cli/*.md` here.
- Sweep vocabulary, not only the identifier `git add -A`: also search for "stages everything", "whole tree", "whole working tree" and "sweep that debris" in `docs/how-to` and `BUG_BACKLOG.md`.
- The `rg` over `plan_tool/cli` is an inventory check. A remaining code comment that describes the *old* whole-tree behavior is a stale claim to report to the owning step, not to fix here (the files are outside this step's list).

## Tests

### Verification (non-code step)

- **Residual grep:** `rg 'git add -A' docs/how-to plan_tool/cli` returns no statement that `--commit` stages everything. Any remaining hit is an accurate reference (for example, `commit_all`'s own footprint-scoped `git add -A -- <paths>`).
- **Vocabulary grep:** `rg -n -i 'stages (all|everything)|whole (working )?tree|per-step .git add' docs/how-to BUG_BACKLOG.md` returns nothing that describes `--commit` as whole-tree.
- **Claims match code:** read the landed footprint helper in each of steps 2–5 and confirm every footprint statement in `detail.md` and `run.md` names only paths the code stages.
- **Failure behavior:** confirm the post-commit clean check and its non-zero result in the landed `commit_all` before documenting it.
- **Anchors:** `rg` for inbound links to any renamed heading anchor in `BUG_BACKLOG.md`, `docs/` and `CLAUDE.md`; none dangle.
- **Generated docs:** `uv run pytest tests/cli/test_cli_reference.py` is clean.
- **Backlog entry:** the residual names `run --commit`, the git-delta cause, and every unconverted surface with its reason; or the entry is gone and no reference to it remains.
- **Clean tree:** `git status` shows only the three declared files changed.

## Acceptance criteria

- `docs/how-to/pipeline/detail.md` contains no "safety invariant" bullet and no claim that per-step commits stage the whole tree.
- `docs/how-to/pipeline/run.md` has no flow-diagram line saying `git add -A + one commit per green step`; the archive and `.gitignore` notes describe footprint staging.
- `docs/how-to/pipeline/detail.md` and `docs/how-to/pipeline/run.md` each state that a footprint path still dirty after the commit gives a non-zero exit.
- `BUG_BACKLOG.md` holds either the residual entry (the `run --commit` concurrent-write gap plus every unconverted surface with its reason) or no entry for this topic.
- `rg 'git add -A' docs/how-to plan_tool/cli` returns no claim that `--commit` stages everything.
- `uv run pytest tests/cli/test_cli_reference.py` passes.
- No file outside the three declared files changes.

## References

- BUG_BACKLOG.md, "`--commit` stages the whole working tree with `git add -A`…" — the entry this step reduces.
- `plan_tool/cli/gitcommit.py` (`commit_all`) — the landed staging and clean-check behavior to document.
- `plan_tool/cli/authoring.py` (`_commit_if_dirty`), `plan_tool/cli/completeness_cmd.py`, `plan_tool/cli/manifest.py`, `plan_tool/cli/run_cmd.py` (`_commit_green_step`) — the footprint rules from steps 2–5.
- `docs/TRACKING.md` § "Scope contract and anti-creep" — the entry fields and the rule for filing unconverted work.
- `docs/reference/documentation-style.md` — style for live developer docs.

## Applicable guardrails

- **The plan's "## Scope guardrails" (stage and commit only):** this step edits docs and the backlog only. It must not change code, the clean-tree precondition, commit subjects, which verbs accept `--commit`, commit granularity or the `launcher.py` test-authoring gate, and the docs must keep describing those as unchanged.
- **The plan's "## Scope guardrails" (do not widen):** the backlog residual must not propose a footprint-tracking subsystem, a hook or `--no-verify`; a verb that needs new bookkeeping is filed as a residual, not converted.
- **The plan's "## Out of scope" and "## Audit guardrails":** the concurrent-process-edits-a-written-file case and widening `--commit` to more verbs (BACKLOG #89) are not documented as fixed; the residual says what `run` still cannot see and leaves #89 alone.
- **The plan's "## Out of scope" (no new checks):** the docs describe only the one check the plan allows, that a written path is clean after the commit; they add no quality or agreement checks.

## Deferred

- Closing the `run --commit` concurrent-write gap — the plan's fence forbids new footprint tracking; it stays as the residual in `BUG_BACKLOG.md`.
- Widening `--commit` to other verbs — BACKLOG #89, which lands after this plan.
- Stale code comments or help-text wording found by the `plan_tool/cli` grep — owned by steps 2–5; report to the owning step rather than editing here.
- Hand edits to `docs/cli/*.md` — generated by `python -m plan_tool.cli_reference --write`, covered by the step 2–5 help-text changes.
