> **Auto-archived**: this plan was swept on 2026-07-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Document the `worktree` command group across the six operator docs

## Summary

Document the worktree workspace feature (shipped by steps 1–4) across the six operator-facing docs in this step's `files:` list — `README.md`, `RUNBOOK.md`, `CLAUDE.md`, `BACKLOG.md`, and both `integrations/claude/SKILL.md` / `integrations/codex/SKILL.md`. None of these files mention worktrees today, so every edit is additive: a new operator workflow/section in `README.md` and `RUNBOOK.md`, a new `## Architecture` paragraph in `CLAUDE.md`, two new catalog rows in the SKILL "Subcommands at a glance" tables, and one forward-looking `BACKLOG.md` entry for the deferred `--worktree` convenience. The most important decision is **which caveats land on which surface**: the four sharp-edge caveats from the plan (`worktree_base`-change orphaning, clone manual-cleanup, per-branch manifest visibility / concurrent-`gc` / dirty-remove, and orphan-branch-on-remove) belong in `README.md` + `RUNBOOK.md` in full, are summarized in `CLAUDE.md`, and are pointer-only in the SKILL routers. On green, every doc describes the four verbs, the docs cross-link correctly, and no doc claims the feature is unbuilt or future.

## Table of Contents

- [Why](#why) — what's undocumented today and why operators need it now
- [Files (creates vs edits)](#files-creates-vs-edits) — the six docs and the per-file edits
- [Implementation](#implementation) — surface-by-surface: what to add and where to anchor it
- [Tests](#tests) — none (non-code); verification list instead
- [Verification (non-code step)](#verification-non-code-step) — link/accuracy checks
- [Acceptance criteria](#acceptance-criteria) — observable doc facts a reviewer can check
- [References](#references) — git docs backing the documented behavior
- [Deferred](#deferred) — the `--worktree` convenience and docs left to siblings

## Why

Steps 1–4 land a complete `worktree add` / `list` / `remove` / `prune` command group, a `worktree_base` config key, and a `--clone` opt-in — but no operator-facing doc mentions any of it. A grep for `worktree`/`workspace`/`clone-the-plan` across `README.md`, `RUNBOOK.md`, `CLAUDE.md`, `BACKLOG.md`, and the two SKILL files returns nothing relevant, so an operator who runs `plan-tool --help` and sees the new `worktree` group has no walkthrough, no config reference, and no statement of the safety gates and orphan caveats. The feature's sharp edges (`worktree_base` re-derivation orphaning existing workspaces, clones being manual-cleanup — never auto-deleted by `remove`/`prune` — and removal never deleting the branch) are silent foot-guns until documented. This step closes that gap and follows the project's rule that a docs step which lands a capability must describe it as **shipped**, not proposed.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `README.md` — add a third bullet to the "Two verbs sit off the main spine" list in `## Core subcommand workflow`; add a new H2 `## Worktrees (parallel plans)` section; add the matching line to `## Table of contents` in document order.
  - `RUNBOOK.md` — add a new H2 `## Workflow: run plans in parallel (worktrees)` placed immediately after `## Workflow: run a plan on its own branch (branch-awareness)`; add a `**Workspaces**` table block to `## Quick reference`; add the workflow's slug to `## Table of contents` in document order.
  - `CLAUDE.md` — add one `## Architecture` paragraph titled **Parallel plan worktrees** immediately after the **Branch-awareness (opt-in; OFF by default).** paragraph and before `## Tests`.
  - `BACKLOG.md` — add one forward-looking entry under `### A. New capability, well-scoped` for the deferred `--worktree` convenience on `run`/`detail`.
  - `integrations/claude/SKILL.md` — add a `**Workspaces**` row to the `## Subcommands at a glance` table; add a row to the `## Decision tree for common user asks` table.
  - `integrations/codex/SKILL.md` — the same two edits as the claude SKILL (these files are near-identical; keep them in lockstep).

## Implementation

The four caveats from the plan's `## Architecture` / `## Risks` are the content backbone. Carry the right subset onto each surface:

- **C1 — `worktree_base` orphaning.** Changing `worktree_base` after workspaces exist re-derives a *different* per-slug path, so `list`/`remove`/`prune` can no longer find the already-provisioned ones (worktrees survive via git's own registry; clones do not). Rule to document: **don't change `worktree_base` while workspaces exist; re-provision after a change.**
- **C2 — clones are manual-cleanup; plan-tool never auto-deletes a clone.** `remove` deletes *worktrees* (via `git worktree remove`); on a **clone** it surfaces a manual-cleanup message and deletes nothing. `prune` sweeps dead *worktrees only* (via git's worktree registry scoped to `worktree_base`) and ignores clones entirely. Reasons: a clone is an independent repo whose commits live only in its own `.git` (possible committed-but-unmerged work the uncommitted-only dirty gate can't see), and it carries no plan-tool provenance marker (so no scan can safely tell a dead plan-tool clone from an operator's unrelated repo). Rule to document: delete a clone yourself — `rm -rf <path>` after confirming no unmerged commits; `list` keeps clones visible.
- **C3 — per-branch manifest / shared-`gc` / dirty-remove.** A plan resolves inside a worktree only if its `.md` and `plans.json` entry are committed on the worktree's base branch (else "plan not found"); worktrees share `.git/objects`, so don't run an aggressive `gc` across parallel runs; `remove`/`prune` refuse a dirty *worktree* without `--force`, and `prune` surfaces (never silently deletes) a dead-but-dirty one even under `-y`.
- **C4 — orphan branch on remove.** `remove`/`prune` delete the *worktree* (the dir) but **not** the branch born inside the add; branch cleanup (`git branch -d`) stays the normal git flow. (Clones aren't deleted at all — see C2.)

### `README.md`

- **Off-spine verb bullet.** In `## Core subcommand workflow`, the list that begins "Two verbs sit off the main spine:" currently has **annotate** and **Branch-awareness** bullets. Add a third: **Worktrees** — provision an isolated working copy per plan so several plans' long `create`/`detail`/`run` processes run in parallel without sharing one index/branch/checkout; link to the new section. Reword the lead-in "Two verbs" to "A few verbs" (or drop the count) so the count stays honest.
- **New section.** Add an H2 `## Worktrees (parallel plans)`. Recommended placement: immediately before `## Modes` (among the operational sections). Cover, in this order:
  - the four verbs with one-line each: `worktree add <plan> [--branch B] [--clone]`, `worktree list`, `worktree remove <plan> [--force]`, `worktree prune`;
  - the default base path `<repo-parent>/<repo-name>.worktrees/<slug>` and the `worktree_base` config key (project `.plan-tool/config.json` → user `~/.plan-tool/config.json`), never inside the repo;
  - the branch rule: the branch is born inside the add on the plan's slug-derived name (branch-awareness OFF, the default) or `derive_branch` (ON), off the resolved start-point;
  - the `--clone` tradeoff (full object-store/remote/config duplication; opt-in; default and recommended path is a worktree);
  - all four caveats **C1–C4** in full.
- **TOC.** Add `- [Worktrees (parallel plans)](#worktrees-parallel-plans)` to `## Table of contents` at the position matching where the section lands in document order.

### `RUNBOOK.md`

- **New workflow section.** Add an H2 `## Workflow: run plans in parallel (worktrees)` directly after `## Workflow: run a plan on its own branch (branch-awareness)` — the worktree workflow is the natural neighbor of branch-awareness (a worktree is the home for a plan's branch). Cover:
  - provisioning: `plan-tool worktree add <plan>` (bare command works on a local-only repo with no remote), the printed `cd` hint, idempotent reuse of a healthy existing workspace, and the up-front warning when the plan `.md` / manifest entry isn't committed on the base branch (**C3** first clause);
  - running concurrently: `cd` into the worktree and run `plan-tool <cmd> <plan>` — per-cwd discovery (`locator.py`) resolves that worktree's manifest, and each worktree has its own untracked `.plan-tool/` caches;
  - inspecting: `worktree list` reports kind / branch / path / dirty for every plan's workspace;
  - teardown: `worktree remove <plan> [--force]` and `worktree prune`, with the dirty-gate behavior and the prune-surfaces-not-deletes rule (**C3**);
  - the `--clone` opt-in and its tradeoff;
  - all four caveats **C1–C4**, with **C4** (orphan branch) and **C2** (clone manual-cleanup) called out explicitly since an operator pruning dead/deregistered plans will hit both.
- **Quick reference.** In `## Quick reference`, add a `**Workspaces**` table block (mirroring the existing `**Discovery & inspection**` / `**Authoring**` blocks) with one row per verb.
- **TOC.** Add `- [Workflow: run plans in parallel (worktrees)](#workflow-run-plans-in-parallel-worktrees)` to `## Table of contents`, positioned right after the branch-awareness workflow line to mirror document order.

### `CLAUDE.md`

- **New Architecture paragraph.** Add one paragraph to `## Architecture` titled **Parallel plan worktrees** placed immediately after the **Branch-awareness (opt-in; OFF by default).** paragraph and before `## Tests`. Describe the three-layer structure landed by steps 1–4, citing the real symbols:
  - the git primitives in `plan_tool/cli/gitcommit.py` (`worktree_add`, `worktree_list`, `worktree_remove`, `worktree_prune`, `clone_repo`) — policy-free, `(rc, tail)` style, never raise;
  - the pure path/config leaf `plan_tool/worktree.py` (`worktree_base`, `derive_worktree_path`, `classify_target`), reusing `project_config.py`'s tolerant layered reader, default base a sibling of the repo;
  - the command group `plan_tool/cli/worktree_cmd.py` (`cmd_worktree` dispatching `add`/`list`/`remove`/`prune`), which owns branch + start-point resolution, reuse-vs-fail, kind dispatch, and the clean-tree gate;
  - the key rules in one clause each: branch born inside the add (never a main-tree `switch -c`), `--clone` as the full-isolation opt-in, the dirty gate protecting *worktree* deletion (clones are never auto-deleted — manual cleanup), and the no-branch-deletion / no-extra-state tenets.
- **Do not touch `## What this is`** — the pipeline one-liner stays unchanged; worktrees are an off-spine provisioning verb, not a pipeline stage.

### `BACKLOG.md`

- **Forward-looking entry.** Add one entry under `### A. New capability, well-scoped` for the **`--worktree` convenience on `run`/`detail`** — provision the plan's worktree and execute the command inside it in one call, kept separable from the `worktree add` primitive (the plan's `## Deferred`). Follow the full section-A entry shape — model the formatting on `#66` (the current max-numbered entry, used here only as a shape exemplar, *not* the number to reuse): open with a `**#67 — Title**` numbered header (the next free number after `#66`), then `**What:**` / `**Why:**` bullets, then the standard metadata bullets (Effort / Risks / Dependencies / Approach / Iterate) per the file's own "Which file does my entry go in?" rule — this is net-new capability, so `BACKLOG.md`, not `BUG_BACKLOG.md`.
- **No entry to trim.** A grep for `worktree`/`workspace`/`parallel plan`/`isolat` across `BACKLOG.md` finds no existing entry proposing this feature, so there is nothing to remove or reframe to past tense — this is a pure addition.

### `integrations/claude/SKILL.md` and `integrations/codex/SKILL.md`

- **Treat both files as one edit, applied twice.** They are near-identical (the only substantive difference is `claude` vs `codex exec` backend prose). Make the same two additions to each.
- **Subcommands at a glance.** Add a `**Workspaces**` group row to the `## Subcommands at a glance` table: subcommands `worktree add <plan> [--clone]`, `worktree list`, `worktree remove <plan> [--force]`, `worktree prune`; **Calls claude?** = No. Keep the row short — the SKILL is a router, so point at README/RUNBOOK for the caveats rather than restating C1–C4.
- **Decision tree.** Add one row to `## Decision tree for common user asks`, e.g. *"run two plans at once / work on plan B without disturbing plan A"* → `plan-tool worktree add <plan>` then `cd` into it.
- **Disambiguation — do not edit the "Not yet implemented" line.** The `## Not yet implemented / out of scope` section says "parallel **step** execution … permanently out of scope — the subprocess-per-step model is sequential by design." That is about parallel steps *within one plan*, which this feature does **not** change; the worktree feature is parallel *plan* execution. Leave that sentence unchanged; do not let the new Workspaces row imply per-step parallelism.

## Tests

No unit tests — this is a `non-code` step that changes only Markdown docs. See [Verification (non-code step)](#verification-non-code-step).

### Verification (non-code step)

- **Anchor accuracy.** Every new TOC entry's anchor matches the GitHub slug of the new heading it points to (`## Worktrees (parallel plans)` → `#worktrees-parallel-plans`; `## Workflow: run plans in parallel (worktrees)` → `#workflow-run-plans-in-parallel-worktrees`).
- **Cross-link validity.** The README off-spine bullet links to the new README section; the SKILL Workspaces row / decision-tree row point at README + RUNBOOK (no broken relative paths from `integrations/<backend>/SKILL.md` — they use `../../README.md` style like the existing `../../README.md#…` references in `## Invocation`/Backends).
- **Verb/flag fidelity.** The verb names and flags documented (`worktree add/list/remove/prune`, `--branch`, `--clone`, `--force`, `-y`) match the parser landed in `plan_tool/cli/worktree_cmd.py` and the generated `docs/cli/worktree.md` — spot-check against `plan-tool worktree --help` and each verb's `--help`.
- **No "future/proposed" framing.** No doc describes the worktree feature as planned, future, or unbuilt; all prose is present-tense "shipped".
- **SKILL parity.** The claude and codex SKILL files received identical Workspaces / decision-tree additions (diff the two new blocks — they should match byte-for-byte except surrounding backend prose).
- **Caveat coverage.** C1–C4 each appear in `README.md` and `RUNBOOK.md`; C4 (orphan branch) and C2 (clone manual-cleanup) are explicit in the RUNBOOK teardown prose.
- **Generated docs untouched.** This step edits no file under `docs/cli/` — `docs/cli/worktree.md` and `docs/cli/README.md` are owned by steps 3/4 and their drift guard (`tests/cli/test_cli_reference.py`) is not this step's concern.

## Acceptance criteria

- `README.md` has a `## Worktrees (parallel plans)` H2, a matching `## Table of contents` line at the correct document-order position, and a third off-spine bullet in `## Core subcommand workflow`.
- `RUNBOOK.md` has a `## Workflow: run plans in parallel (worktrees)` H2 immediately after the branch-awareness workflow, a `**Workspaces**` block in `## Quick reference`, and a matching TOC line.
- `CLAUDE.md` `## Architecture` has a **Parallel plan worktrees** paragraph after **Branch-awareness** and before `## Tests`, naming `gitcommit.py`, `plan_tool/worktree.py`, and `plan_tool/cli/worktree_cmd.py`.
- `BACKLOG.md` `### A. New capability, well-scoped` has a `--worktree` convenience entry following the full section-A shape — a `**#NN — Title**` numbered header (next free number), What/Why bullets, and the standard Effort/Risks/Dependencies/Approach/Iterate fields.
- Both SKILL files have a `**Workspaces**` row in `## Subcommands at a glance` and a worktree row in `## Decision tree for common user asks`, and neither edits the existing parallel-step-execution out-of-scope sentence.
- Caveats C1 (`worktree_base` orphaning), C2 (clone manual-cleanup), C3 (per-branch manifest / shared-`gc` / dirty-remove), and C4 (orphan branch on remove) are documented in `README.md` and `RUNBOOK.md`.
- No new TOC anchor 404s; no doc frames the feature as future/proposed.

## References

- [git-worktree Documentation](https://git-scm.com/docs/git-worktree) — Backs the `add`/`list`/`remove`/`prune` verb descriptions, the `--porcelain` list parsing, and git's same-branch-checkout refusal that the docs cite as the structural one-worktree-per-branch guarantee.
- [git-clone Documentation](https://git-scm.com/docs/git-clone) — Source for the `--clone` tradeoff prose (object-store/remote/config duplication vs. a worktree's shared store).
- [git-config Documentation](https://git-scm.com/docs/git-config) — Defines the `--local` config surface shared across a repo's worktrees, relevant to the `worktree_base` config and the branch-binding interaction noted in the docs.

## Deferred

- **`--worktree` convenience on `run`/`detail`** — provision-and-execute in one command; this step only *files the BACKLOG entry* for it, it does not document a shipped flag (the flag doesn't exist). Tracked as the new `BACKLOG.md` `### A` entry above.
- **`docs/cli/worktree.md` and `docs/cli/README.md`** — the generated per-subcommand reference and index row are produced and drift-guarded by steps 3/4 (`python -m plan_tool.cli_reference --write`), not hand-edited here.
- **`TESTING.md` / `PLAN_FORMAT.md` / other docs** — outside this step's `files:` list; the worktree primitives are real-git integration-tested (no invoker seam), so `TESTING.md`'s neutralization table needs no worktree row. If a future reviewer wants a worktree mention in `TESTING.md`, route it through a separate docs change.
