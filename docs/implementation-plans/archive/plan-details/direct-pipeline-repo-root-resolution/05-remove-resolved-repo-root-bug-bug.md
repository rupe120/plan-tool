> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Remove the resolved repo-root bug from the bug backlog

## Summary

Once steps 1–4 land and verify the repo-root relocation fix (`create_plan`'s manifest-path default, the `created_repo_root` threading through `direct-jira`/`direct-run`, the relocated-root dirty guard, and the real end-to-end relocation tests), this step removes the RISK entry in `BUG_BACKLOG.md` titled "`direct-jira` / `direct-run` resolve repo_root from cwd, not the repo `create` actually wrote to" — the entry the plan's Problem statement cites as its `Source`. The only file touched is `BUG_BACKLOG.md`; the edit deletes exactly that entry's header and its five bullets (Files/Symptom/Fix/Approach/Origin) and nothing else in the file. The key design point is ordering: this step must confirm the fix is actually present at HEAD (not just that steps 1–4 are marked `done` in the plan) before deleting the entry, since `BUG_BACKLOG.md`'s own convention ("When an item is fixed, remove it") ties removal to the code being fixed, not to plan bookkeeping. On green, `BUG_BACKLOG.md` no longer names this bug, every other entry in the file is byte-identical to before, and the plan's own final acceptance-criteria bullet ("`BUG_BACKLOG.md`'s '`direct-jira` / `direct-run` resolve repo_root from cwd…' entry is removed once the fix ships") is satisfied.

## Table of Contents

- [Why](#why) — why this entry can only be removed now, after steps 1–4
- [Input](#input) — what this step reads from steps 1–4 and from `BUG_BACKLOG.md`'s own entry-shape convention
- [Files (creates vs edits)](#files-creates-vs-edits) — the one in-scope file and the exact lines removed
- [Implementation](#implementation) — the verify-then-remove approach and what must stay untouched
- [Tests](#tests) — non-code verification in place of unit tests
- [Acceptance criteria](#acceptance-criteria) — observable state of `BUG_BACKLOG.md` on green
- [Deferred](#deferred) — the other backlog entries and files this step deliberately leaves alone

## Why

`BUG_BACKLOG.md`'s own usage rules say "When an item is fixed, remove it. Git history is the record; this file should reflect the *current* outstanding-bug state, not the cumulative history." The entry this step removes is the plan's own origin: its Problem statement explicitly names it as `Source: BUG_BACKLOG.md RISK entry '\`direct-jira\` / \`direct-run\` resolve repo_root from cwd, not the repo \`create\` actually wrote to' (filed 2026-07-17, #118 direct-pipeline post-run /code-review, CONFIRMED)`, and the plan's Acceptance criteria section lists its removal as the final bullet. Leaving it in place after steps 1–4 land would misrepresent the current outstanding-bug state — exactly the staleness the file's own maintenance rule warns against — and CLAUDE.md's "Backlog-derived seeds must carry backlog reconciliation forward" directive is why this plan carries its own removal step instead of leaving it to an operator's memory.

## Input

This step depends on step 4 (`depends_on: 4`) and, transitively, steps 1–3, but should verify their landed outcome directly rather than trust the plan's step-status field:

- **The fix itself** (steps 1–3): `create_plan`'s manifest-path default reading the resolved `repo_root` (step 1), `created_repo_root` threaded into every `_stage_namespace(...)` call and every post-create `working_tree_dirty`/`commit_all` call in `plan_tool/cli/direct_cmd.py` (step 2), and the relocated-root dirty guard added to `plan_tool/cli/gitcommit.py`/`plan_tool/cli/direct_cmd.py` (step 3). Verify these landed by reading the current code at the anchors named in each step's own detail file — don't re-derive their mechanisms here.
- **The end-to-end proof** (step 4): real, unstubbed relocation tests in `tests/cli/test_direct_cmd.py` covering both `direct-jira` and `direct-run`, both relocation directions, and the dirty-abort case. Their existence and green status is this step's precondition — check `uv run pytest tests/cli/test_direct_cmd.py -q` passes before editing the backlog.
- **`BUG_BACKLOG.md`'s own entry-shape and section conventions** (top of the file, `### Entry shape` and the `## Severity legend`/`## RISK` structure): the edit must remove one complete entry cleanly and leave the surrounding `## RISK` section's spacing and remaining three entries intact.

Verifying this step is limited to reading the current source at HEAD and running the existing test suite — there's no persisted schema or saved audit for `BUG_BACKLOG.md` itself; no test or `plan_tool/` module parses the file programmatically (confirmed by grep — it exists purely for human triage per its own "How to use it" section).

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `BUG_BACKLOG.md` — delete the entry currently reading `### \`direct-jira\` / \`direct-run\` resolve repo_root from cwd, not the repo \`create\` actually wrote to` under the `## RISK` heading, together with its five bullets (`**Files:**`, `**Symptom:**`, `**Fix:**`, `**Approach:**`, `**Origin:**`) and the entry's trailing blank line, so the section reads directly from `## RISK` into the next entry (`### \`convergence\` diagnostic recommends "spinning → re-decompose"...`).

## Implementation

**Verify before removing — don't treat this as a rubber-stamp doc edit.** `BUG_BACKLOG.md`'s "How to use it" rule ties removal to the item actually being fixed, and this plan's own Acceptance criteria bullet says the entry is removed "once the fix ships," not once step 4 is checked off. Confirm at HEAD:
- `plan_tool/create.py`'s manifest-path assignment reads the resolved `repo_root` (step 1's fix).
- `plan_tool/cli/direct_cmd.py`'s `_stage_namespace(...)` calls and post-create `working_tree_dirty`/`commit_all` calls use the create-derived root, not the pre-create one (step 2's fix).
- The relocated-root dirty guard from step 3 exists and runs before `detail` in both `cmd_direct_jira`/`cmd_direct_run`.
- `tests/cli/test_direct_cmd.py`'s step-4 end-to-end relocation scenarios exist and pass (`uv run pytest tests/cli/test_direct_cmd.py -q`).

**The removal itself is a single, bounded deletion.** Take out only the named entry's header and its five bullets, plus the blank line that separates it from the next entry, so the file's existing "one blank line between entries" convention (visible between every other pair of entries in `## RISK` and `## MINOR`) is preserved across the seam. Nothing else in the file changes — not wording, not spacing, not heading levels — in any entry above or below it.

**What must not move.** The plan's `## Out of scope` section explicitly calls out one entry in the same `## RISK` section — the dormant `emit_concept_tree` bug (`plan_tool/concept_tree.py:emit_concept_tree`) — as "a separate, already-filed BUG_BACKLOG RISK entry, unrelated code path, zero production callers; not touched here." The other two `## RISK` entries (the `convergence` diagnostic "spinning" bug and the `completeness-audit --reuse-audit` coverage bug) and every `## MINOR` entry are equally out of scope for this step — they're unrelated bugs that happen to share the file. `## BUG` (currently `_(none outstanding)_`) is untouched too. Don't touch `BACKLOG.md` or `LESSONS_LEARNED.md`: this plan's `Source` names one `BUG_BACKLOG.md` entry, and there is no corresponding forward-looking `BACKLOG.md` item to reconcile for this particular bug.

## Tests

This step changes no production code, so there is nothing to unit test.

### Verification (non-code step)

- Confirm the fix landed before editing: check `plan_tool/create.py` for the corrected manifest-path resolution (step 1), check `plan_tool/cli/direct_cmd.py` for the create-derived root threaded through `_stage_namespace(...)` and the post-create git calls (step 2) and for the dirty guard (step 3), and run `uv run pytest tests/cli/test_direct_cmd.py -q` to confirm step 4's real relocation tests pass.
- Diff `BUG_BACKLOG.md` before and after the edit: the only change is the removal of the one named entry (its header, five bullets, and one blank line); every other line is byte-identical.
- Read the edited `## RISK` section top to bottom: `## RISK` is followed by a blank line and then `### \`convergence\` diagnostic recommends "spinning → re-decompose"...` directly, with the file's normal entry spacing intact, and the remaining three `## RISK` entries plus `## BUG`/`## MINOR` unchanged.
- Run `grep -rn "resolve repo_root from cwd" --include="*.md"` across the repo and confirm the only remaining hits are in the plan's own docs (`docs/implementation-plans/2-direct-pipeline-repo-root-resolution.md` and the archived seed under `plan-seeds/archive/`) — expected, and out of this step's scope to edit.

## Acceptance criteria

- `BUG_BACKLOG.md` no longer contains the entry titled "`direct-jira` / `direct-run` resolve repo_root from cwd, not the repo `create` actually wrote to," including its `**Files:**`/`**Symptom:**`/`**Fix:**`/`**Approach:**`/`**Origin:**` bullets.
- `BUG_BACKLOG.md`'s `## BUG` section, the remaining three `## RISK` entries (`convergence` diagnostic spinning bug, `completeness-audit --reuse-audit` coverage bug, dormant `emit_concept_tree` bug), and every `## MINOR` entry are present and unmodified.
- `BUG_BACKLOG.md` stays well-formed Markdown: `## RISK` is followed by a blank line and then the next entry's `###` header, matching the file's existing entry-spacing convention.
- The removal is made only after confirming steps 1–4's fix and end-to-end tests are present and passing at HEAD.

## Deferred

- The `emit_concept_tree` dormant-twin RISK entry (`plan_tool/concept_tree.py:emit_concept_tree`) — a separate, already-filed bug on an unrelated code path with zero production callers; the plan's `## Out of scope` names it explicitly as untouched by this plan.
- The `convergence` diagnostic "spinning → re-decompose" RISK entry and the `completeness-audit --reuse-audit` coverage RISK entry — unrelated bugs sharing the same `## RISK` section, left as-is.
- Any `BACKLOG.md` or `LESSONS_LEARNED.md` bookkeeping — this plan's `Source` is a single `BUG_BACKLOG.md` entry; there is no corresponding `BACKLOG.md` item to reconcile.
- Fixing the same stale-manifest-path pattern in `plan_tool/cli/manifest.py`/`plan_tool/cli/inspect.py` — step 6's job, unrelated files and call sites.
