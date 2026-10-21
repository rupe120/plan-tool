> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Direct Pipeline Repo Root Resolution
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Fix create's manifest path to use the repo root it already resolved
  files:
  - plan_tool/create.py
  - tests/test_create.py
  complexity: low
  change_type: feature
  detail: docs/implementation-plans/plan-details/direct-pipeline-repo-root-resolution/01-fix-create-manifest-path-use-repo-root.md
  status: done
- id: 2
  title: Pass the repo root create actually used into every later pipeline stage
  files:
  - plan_tool/cli/direct_cmd.py
  - tests/cli/test_direct_cmd.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/direct-pipeline-repo-root-resolution/02-pass-repo-root-create-actually-used.md
  status: done
- id: 3
  title: Add a safety check that stops the chain if the relocated repo has unrelated
    uncommitted changes
  files:
  - plan_tool/cli/gitcommit.py
  - plan_tool/cli/direct_cmd.py
  - tests/cli/test_gitcommit.py
  - tests/cli/test_direct_cmd.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  detail: docs/implementation-plans/plan-details/direct-pipeline-repo-root-resolution/03-safety-check-that-stops-chain-relocated.md
  status: done
- id: 4
  title: Add end-to-end tests for direct-jira and direct-run when create relocates
    the repo root
  files:
  - tests/cli/test_direct_cmd.py
  complexity: high
  change_type: feature
  depends_on:
  - 3
  detail: docs/implementation-plans/plan-details/direct-pipeline-repo-root-resolution/04-end-end-tests-direct-jira-direct-run.md
  status: done
- id: 5
  title: Remove the resolved repo-root bug from the bug backlog
  files:
  - BUG_BACKLOG.md
  complexity: low
  change_type: non-code
  depends_on:
  - 4
  detail: docs/implementation-plans/plan-details/direct-pipeline-repo-root-resolution/05-remove-resolved-repo-root-bug-bug.md
  status: done
- id: 6
  title: Fix the same stale-manifest-path bug in register, deregister, sweep, and
    list
  files:
  - plan_tool/cli/manifest.py
  - plan_tool/cli/inspect.py
  - tests/cli/test_manifest_cmds.py
  - tests/cli/test_inspect_cmds.py
  complexity: low
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/direct-pipeline-repo-root-resolution/06-fix-same-stale-manifest-path-bug.md
  status: done
---
# Direct Pipeline Repo Root Resolution

## Overview

Fixes `plan-tool create`'s repo-root relocation handling (the seed-derived override `find_umbrella_root` computes in `plan_tool/cli/authoring.py` around line 507-541) so it propagates fully instead of leaving stale roots behind downstream. Two sites are fixed together: `create_plan` itself, where the manifest write can diverge from the plan write under a relocated root, and the `direct-jira`/`direct-run` chains in `plan_tool/cli/direct_cmd.py`, which resolve `repo_root` once before `create` runs and never learn about a later relocation. The fix threads the resolved root through `create_plan`'s manifest-path default and through every downstream stage namespace via the existing `args.repo_root`/`repo_root_override` plumbing, and adds a cleanliness guard on the relocated root before the first post-create commit. Standalone (non-direct-*) `detail`/`run` invocations are unaffected, since they resolve their own root fresh from cwd/`--repo-root` each time with no stale in-process hand-off to go bad. **Scope boundary:** this plan handles the case where the relocated root is *disjoint* from the cwd root (a true **sibling** project — `find_umbrella_root` case 1, one other `.git`) plus the fully-internal `create_plan` manifest divergence (step 1, which always applies). The case where the relocated root is *nested inside* the cwd root or is a strict *ancestor* of it — including `find_umbrella_root`'s case-2 "umbrella" (a common ancestor of sibling repos, which is an ancestor by construction) — is deliberately **refused with a clear error** rather than handled, because git's embedded-repository semantics make `git add -A` stage a gitlink and the step-0 precondition misread a nested `.git` as dirt; the full-support follow-up is tracked as BACKLOG #146 (see `## Out of scope`). `create_plan`'s manifest-path fix (decision 1) turns out to be one instance of a broader pattern — `plan_tool/cli/manifest.py`'s `register`/`deregister`/`sweep` and `plan_tool/cli/inspect.py`'s `list` share the same `default_manifest_path()`-with-no-`repo_root` call shape, each already having its own resolved `ctx.repo_root` sitting unused nearby; step 6 applies the identical fix to those **five** call sites (`register`, `deregister`, `sweep`, and `list`'s *two* sites — across four commands), riding along with decision 1 rather than opening a separate plan for the same root cause.

## Problem statement

`cmd_create` can relocate a plan's working repo root away from the cwd-derived default when a `--from-existing` seed's body references files under a different `.git` ancestor (narrower — a nested repo under the cwd root — or broader — a sibling/umbrella root); once confirmed (auto-confirmed under `--yes`), `cmd_create` writes the plan, its detail bundle, and the manifest entry under that relocated root instead of the cwd-derived one. Two downstream call sites don't know about this relocation, and both need fixing together:

1. **`create_plan` itself** (`plan_tool/create.py` line ~5669): `mf = manifest_path or default_manifest_path()` calls `default_manifest_path()` with no `repo_root` argument when `--manifest` isn't passed explicitly, so per `plan_tool/locator.py:54`'s docstring it re-walks from the current working directory and lands on the original, pre-override root — not the `repo_root` `create_plan` was actually called with. Meanwhile `resolve_output_dir(repo_root, ...)` a few lines above does use the overridden `repo_root`. So a single `create_plan` call can write the plan file under the umbrella root's `docs/implementation-plans/` while registering it in the cwd root's `.plan-tool/plans.json` manifest — a divergence entirely internal to `create`. Re-deriving 'the root create used' from `CreateResult.manifest_path` (the naive fix) would read back the wrong root here, because the manifest itself was written to the wrong place.

2. **`direct_cmd.py`**: `cmd_direct_jira` and `cmd_direct_run` both call `repo_root = _resolve_cmd_repo_root(args)` once, at the top, before `create` runs, and every stage after that reuses this stale value — the `working_tree_dirty(repo_root)` / `commit_all(repo_root, ...)` calls after `detail` (step 4) and after `completeness-apply` (step 5) commit against the wrong tree, and downstream stage handlers (`cmd_detail`, `cmd_completeness_apply`, `cmd_jira`, `cmd_run`, `cmd_reconcile_code`) each build context via `_load_context(args)` → `build_plan_tool_context(..., repo_root_override=args.repo_root)`, but `_stage_namespace` never sets `.repo_root`, so it stays `None` and each stage falls back to its own cwd-walk. Concretely, `cmd_detail` can't find `plan_name` in the cwd manifest (it was registered in the umbrella manifest), and the chain aborts 'plan not found' even though `create` succeeded and the plan exists on disk.

Source: `BUG_BACKLOG.md` RISK entry '`direct-jira` / `direct-run` resolve repo_root from cwd, not the repo `create` actually wrote to' (filed 2026-07-17, #118 direct-pipeline post-run `/code-review`, CONFIRMED).

## Architecture

1. **Fix `create_plan`'s manifest-path default first.** Change `mf = manifest_path or default_manifest_path()` to `mf = manifest_path or default_manifest_path(repo_root)`, making `create_plan` internally consistent (plan file and manifest entry always land under the same root) regardless of caller — a prerequisite for any downstream fix to have a correct root to read back. Explicit `--manifest` callers are unaffected since their path already wins via short-circuiting.

2. **Derive the actual working root from `CreateResult`, not a pre-create snapshot.** Once (1) lands, `CreateResult.manifest_path.parent.parent` (or equivalently deriving from `CreateResult.plan_path`'s owning `.git`/`.plan-tool` ancestor via `find_repo_root_from_cwd(start=...)`, which already accepts a `start` override per `plan_tool/locator.py:135`) reliably reflects the root `create` actually used. Prefer deriving from `plan_path`'s owning root if the two derivations can diverge under an explicit `--manifest` override, since that's the tree every downstream git operation (commit, dirty-check) actually needs.

3. **Thread the resolved root into every downstream stage namespace — but commit the original root's own known side effect first.** In both `cmd_direct_jira` and `cmd_direct_run`, after `result: CreateResult = sink[-1]` is read and validated (after the split-proposal / iteration-failure / size-gate guards), resolve the actual root per decision 2. Before repointing every subsequent git operation at it, check whether the *original* pre-create `repo_root` is now dirty: `cmd_create`'s `--from-existing` path archives the consumed seed file via `archive_existing_source(source_path, result.plan_path, repo_root=repo_root)` (`plan_tool/cli/authoring.py`), and that function resolves its archive directory from `source.parent` — the seed's own location — not from its `repo_root` argument (which it uses only for a cosmetic display string). The seed typically lives in the *original* root (the operator's own project), not the relocated one, so this archival write lands in the original root regardless of where `create` relocated to. If every post-create git operation moves to the resolved root wholesale (as this decision originally described), nothing ever commits that archival — it stays dirty in the original root, silently, and a later invocation from that root trips the unchanged step-0 `working_tree_dirty(repo_root)` precondition and aborts "requires a clean working tree." So, in this order (the ordering is load-bearing — see below): **(a)** run decision 7's disjointness refuse-guard; **(b)** if the resolved root differs from `repo_root` and `working_tree_dirty(repo_root)` (the original), commit it there first (a small, clearly-named commit covering only that known side effect); **(c)** *then* set the resolved root as `repo_root` on every subsequent `_stage_namespace(...)` call (detail, completeness-apply, jira/run, reconcile-code) and replace every post-create use of the original top-of-function `repo_root` local (the `working_tree_dirty`/`commit_all` calls in steps 4 onward of both verbs) with this resolved value; **(d)** step 4/onward then reaches decision 4's relocated-root cleanliness guard. The original-root commit (b) **must precede** decision 4's guard (d): if the guard aborts first, the original root's archival dirt would never be committed, silently reintroducing the exact regression this decision exists to prevent. This commit is a no-op when `--from` (no seed file) was used or the original root has nothing dirty — `working_tree_dirty` gates it. The step-0 precondition check (`working_tree_dirty` before `create` runs) correctly keeps using the original cwd-derived root — there is no other root to check yet at that point. Because decision 7 has already refused any non-disjoint relocation before (b) runs, `repo_root` and the resolved root are guaranteed *disjoint trees* here, so this commit's `git add -A` cannot stage the resolved root as an embedded gitlink — the embedding hazard exists only when one root is nested inside the other, which decision 7 rules out.

4. **Re-verify cleanliness of the relocated root before folding it into an auto-generated commit.** When the resolved root differs from the original cwd-derived root, add a cleanliness check on the resolved root immediately after relocation is detected, before `detail` runs — if unexpectedly dirty from something other than this run's own writes, abort with a clear message (mirroring the step-0 precondition's existing error shape) rather than commingling unrelated changes. This is a new guard, not a relaxation of an existing one.

5. **Scope boundary: standalone (non-direct-*) invocations are out of scope.** `plan-tool detail <name>` / `plan-tool run <name>` invoked directly already resolve their own root from cwd/`--repo-root` independently each time — there is no stale pre-create snapshot problem for them.

6. **Apply decision 1's fix pattern to the other bare `default_manifest_path()` call sites.** `register`/`deregister`/`sweep` (`plan_tool/cli/manifest.py`) and `list` (`plan_tool/cli/inspect.py`, two call sites) each already resolve a `ctx.repo_root` via `_load_context(args)` before computing their own manifest path as `args.manifest or default_manifest_path()` — the same no-`repo_root`-argument shape decision 1 fixes in `create_plan`, just with an already-resolved root sitting unused nearby instead of one that needs deriving. Thread `ctx.repo_root` into each of those `default_manifest_path(...)` calls the same way decision 1 threads `create_plan`'s `repo_root` parameter through. This is a distinct set of commands from the direct-* chain (decisions 2-4) — it shares only the root-cause pattern with decision 1, not any of the direct-* threading machinery.

7. **Refuse a non-disjoint (nested or ancestor) relocation with a clear error — the scope boundary that keeps decisions 3-4 sound.** After `created_repo_root` is derived (decision 2) and before decision 3's original-root commit, check whether `created_repo_root` and the original `repo_root` are *disjoint trees*. When they are **not** — one is nested inside the other (`created_repo_root.resolve().is_relative_to(repo_root.resolve())` or the reverse) — `direct-jira`/`direct-run` **refuse** with a clear error (e.g. "`{verb}`: create relocated the plan to a repo nested within (or containing) the current one; nested-repo relocation is unsupported — run `plan-tool create`/`detail`/`run` from the target repo directly") and return non-zero, before any commit or stage threading. This is the deliberate scope boundary: git's embedded-repository semantics make the non-disjoint case genuinely hazardous — a nested `.git` reads as opaque `?? nested/` dirt to the step-0 precondition (so it rejects the chain before relocation logic runs), and a `git add -A` on the outer root stages the inner root as an embedded gitlink (`mode 160000`). Rather than partially mis-handle those, refuse cleanly; full nested/ancestor support is deferred to **BACKLOG #146**. Because this guard runs first, decisions 3 and 4 are guaranteed to operate on disjoint roots, where their `git add -A` commits and `git status` reads are well-behaved. **What "disjoint" means precisely:** the supported case is a true *sibling* — `find_umbrella_root`'s **case 1** (the seed's file references all resolve under a *single other* `.git` repo that is neither nested in nor an ancestor of cwd). `find_umbrella_root`'s **case 2** — a genuinely `.git`-less "umbrella" computed as the *deepest common ancestor* of several sibling repos — is by construction an **ancestor** of cwd, so it is caught by decision 7's `repo_root.is_relative_to(created_repo_root)` arm and **refused**, not supported. So the word "umbrella" denotes a *refused* (ancestor) shape, not a supported one; the supported disjoint case is a sibling only. The disjoint (sibling) relocation and the fully-internal `create_plan` manifest divergence (decision 1) — the plan's core value — are unaffected.

**Confirmed compatible fix surface:** every downstream stage handler already honors `args.repo_root` as an override (`build_plan_tool_context(..., repo_root_override=args.repo_root)`, `plan_tool/locator.py` around line 528-533) — the existing `--repo-root` flag's plumbing. The fix does not need a new 'handler context-resolution seam' abstraction; it needs the create-resolved root threaded into that existing override field on every downstream stage namespace `_stage_namespace` builds.

## Input

This plan's fix reads and extends the existing `--repo-root` override plumbing rather than introducing a new context-resolution seam:

- Every downstream stage handler (`cmd_detail`, `cmd_completeness_apply`, `cmd_jira`, `cmd_run`, `cmd_reconcile_code`) already honors `args.repo_root` as an override via `build_plan_tool_context(..., repo_root_override=args.repo_root)` (`plan_tool/locator.py` around line 528-533).
- Today `_stage_namespace` (in `plan_tool/cli/direct_cmd.py`) never sets `.repo_root`, so it stays `None` and each stage falls back to its own cwd-walk — this is the gap the fix closes by setting `repo_root` on every `_stage_namespace(...)` call built after `create` returns.
- Verifying this contract is limited to reading `plan_tool/locator.py`'s `default_manifest_path`/`find_repo_root_from_cwd` signatures and `plan_tool/cli/direct_cmd.py`'s `_stage_namespace`/`_load_context` call sites; there is no persisted schema or versioned API to check beyond the current source.

## References

- [pathlib — Object-oriented filesystem paths](https://docs.python.org/3/library/pathlib.html) — Covers Path.resolve(), .parent/.parents ancestor traversal, and path equality needed to implement repo-root walking and comparing a relocated root against the cwd-derived one.
- [git-rev-parse Documentation — --show-toplevel](https://git-scm.com/docs/git-rev-parse) — Canonical reference for resolving a working tree's top-level (.git ancestor) directory, the underlying operation `find_repo_root_from_cwd`/`find_umbrella_root` must replicate for narrower/broader root detection.
- [git-status Documentation — porcelain format](https://git-scm.com/docs/git-status) — Defines the stable, script-parseable porcelain output used to implement a reliable working_tree_dirty()/cleanliness check on the relocated root before folding it into an auto-generated commit.
- [argparse — Parser for command-line options, arguments and sub-commands](https://docs.python.org/3/library/argparse.html) — Documents the Namespace object and attribute-assignment semantics relevant to threading a resolved repo_root through args/_stage_namespace across the direct-jira/direct-run stage handlers.
- [git-worktree Documentation](https://git-scm.com/docs/git-worktree) — Reference for git's own notion of per-worktree root and administrative files, useful context when reasoning about repo-root ambiguity across nested/sibling .git ancestors and commit targeting.
- [os.path — Common pathname manipulations](https://docs.python.org/3/library/os.path.html) — Standard-library reference for ancestor/relative path operations (commonpath, relpath) that can validate whether a resolved root is narrower or broader than another candidate root.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Redesigning `_load_context` / `resolve_plan_for_context`'s general per-invocation root-resolution model — every non-direct-* command keeps resolving from cwd/`--repo-root` exactly as today.
- A new 'handler context-resolution seam' abstraction — the existing `--repo-root`/`repo_root_override` plumbing already covers this; adding a new seam would be unjustified scope growth for what's actually a threading fix.
- Branch-awareness / worktree provisioning interactions — this seed is about repo-root resolution, not branch or worktree selection.
- The `emit_concept_tree` dormant-twin bug — a separate, already-filed BUG_BACKLOG RISK entry, unrelated code path, zero production callers; not touched here.
- **Nested / ancestor-repo relocation** — when `create` relocates to a root nested inside the cwd root, or to a strict ancestor of it (the non-disjoint cases), the direct-* verbs **refuse** with a clear error (decision 7) rather than handle it. Full support — detecting the embedded-repo boundary, scoping commits to explicit pathspecs so `git add -A` never stages a gitlink, teaching the step-0 precondition to ignore an embedded `.git`, fixing `find_umbrella_root`'s ancestor-vs-sibling relation classification, **and cleaning up `create`'s already-written footprint on the ancestor refuse path** (the seed archive left uncommitted when the refuse returns before the original-root commit — see Risks) — is deferred to **BACKLOG #146**. The narrower correctness gap where a *disjoint* relocation that also **replaces** a colliding same-slug plan writes extra files (`replaced_archives` / manifest removal / `plan_details_renamed_to`) IS handled here (step 3's expected-dirt set accounts for them); only the non-disjoint nesting is deferred.

## Risks

- Without the decision-4 cleanliness guard, when create relocates to a root different from the cwd-derived one, that relocated repo's pre-existing dirty state (never checked by step 0's precondition, which only inspects the cwd repo) could get silently folded into the first post-create `commit_all`'s auto-generated commit message, commingling unrelated changes. This is a real gap the fix would otherwise introduce (today's code only 'works' because it never notices the relocation at all). Mitigation: add a cleanliness check on the resolved root immediately after relocation is detected, before `detail` runs, aborting with a clear error (mirroring step 0's existing precondition shape) if the relocated root is unexpectedly dirty.
- Without decision 3's original-root commit, repointing every post-create git operation at the resolved root would silently orphan the *original* root's own known side effect: `cmd_create`'s `--from-existing` path archives the consumed seed at `source.parent/archive/` (`archive_existing_source`, `plan_tool/cli/authoring.py`) — the seed's own location, which is typically the original root, not the relocated one. Left uncommitted, that residual dirt would trip the unchanged step-0 `working_tree_dirty(repo_root)` precondition on the *next* invocation from the original root, causing a spurious "requires a clean working tree" abort on a completely unrelated future run — a regression this plan's own fix would introduce in exactly the `--from-existing` + relocation scenario it exists to support. Mitigation: commit the original root's own dirt (if any) immediately after relocation is detected and before repointing subsequent stages, per decision 3.
- The original-root commit and the relocated-root cleanliness guard would be a hazard **if** the two roots could be nested: `git add -A` on the outer root would stage the inner root as an embedded gitlink (`mode 160000`), and a nested `.git` under the original root would read as opaque dirt to the step-0 precondition, rejecting the chain before relocation logic runs. Decision 7's up-front refuse-guard removes the **embedding/corruption** hazard for both non-disjoint sub-cases (nested and ancestor): any non-disjoint relocation is refused before either the original-root commit or the relocated-root guard runs, so those never do a `git add -A` across a repo boundary. For the **nested** sub-case the refusal is fully clean — the embedded `.git` reads as dirt and trips the step-0 precondition *before* `create` even runs, so nothing is written to clean up. **The ancestor sub-case has one residual, benign consequence, not corruption:** there is no embedded-`.git` tripwire, so step 0 passes, `create` runs and archives the consumed `--from-existing` seed in the original root, and decision 7 then refuses and returns *before* decision 3's original-root commit — leaving that archival dirt uncommitted. On the next invocation from that root it trips the step-0 precondition (a spurious "requires a clean working tree" the operator clears by committing/removing the archive). This is a **known limitation of the refused (unsupported) ancestor path**, not the supported disjoint path — cleaning up `create`'s already-written footprint on a refused relocation is part of **BACKLOG #146**'s full-support scope (the refuse deliberately does *not* try to commit or roll back a half-run of an unsupported case). The ordering — refuse-guard → original-root commit → thread → relocated-root guard — is specified in decision 3 and both steps' detail files so on the *supported* (disjoint) path an aborted relocated-root guard never orphans the original-root commit.

## Testing

Drive a seed whose file references resolve to a broader (true **sibling**, disjoint — `find_umbrella_root` case 1, one other `.git`) root through both `direct-jira` and `direct-run` end-to-end (fake/stub invokers per `tests/conftest.py`'s autouse real-backend gate), confirming: the plan is found by `detail`/`completeness-apply`/`jira`/`run`; commits land in the relocated repo (not the original cwd repo); and a pre-existing dirty relocated repo aborts cleanly instead of commingling changes. Separately, drive a seed that resolves to a **nested** (or ancestor) root and confirm both verbs **refuse** with a clear error (decision 7) rather than proceed — the nested/embedded-repo case is scoped out (BACKLOG #146), so its acceptance is a clean refusal, not a completed chain.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — unit tests added with the implementation; green before completion.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (feature) — unit tests added with the implementation; green before completion.
- step 5 (non-code) — verification appropriate to the artifacts; no test-ordering directive.
- step 6 (feature) — unit tests added with the implementation; green before completion.

## Acceptance criteria

- A `direct-jira` or `direct-run` invocation whose `--from-existing` seed relocates `create` to a **disjoint sibling** root (`find_umbrella_root` case 1 — one other `.git`, neither nested nor ancestor) completes the full chain (`create → detail → completeness-apply → jira` / `→ run --all --commit → reconcile-code`) without a spurious 'plan not found' abort. (An ancestor "umbrella" — case 2 — is refused, not completed, per decision 7.)
- When `create` relocates to a **non-disjoint** root (nested inside cwd, or a strict ancestor of it), the direct-* verb **refuses** with a clear, actionable error naming the situation and returns non-zero, before any post-create commit or stage runs — it does not attempt (and does not corrupt state trying) to handle the embedded-repo case (deferred to #146).
- A disjoint relocation that also **replaces** a colliding same-slug plan (`should_replace` branch) — writing `replaced_archives`, removing a manifest entry, and possibly a `plan_details_renamed_to` rename under the relocated root — is **not** misclassified as unrelated dirt by step 3's guard: those `create`-authored writes are in the expected set and the chain proceeds.
- `create_plan` never writes the plan file and its manifest entry under two different roots in the same call, regardless of caller (direct-* chain or a standalone `plan-tool create`).
- Every post-create git operation in the direct-* chain (`working_tree_dirty` / `commit_all` calls in steps 4+ of both verbs) targets the root `create` actually used, not the pre-create cwd snapshot.
- When create relocates via `--from-existing` and archives the consumed seed (`archive_existing_source`) in the original, pre-relocation root, that root's resulting dirt is committed there before subsequent stages repoint at the relocated root — a later invocation from the original root never trips the step-0 clean-tree precondition because of this run's own residual archival dirt.
- When create relocates to a different root than the one checked at step 0, and that relocated root is unexpectedly dirty from unrelated pre-existing changes, the chain aborts with a clear message instead of folding those changes into an auto-generated commit.
- The no-relocation (common) case is behaviorally unchanged — same commits, same root, no new prompts or checks fire when `create` doesn't relocate.
- Running `register`, `deregister`, `sweep`, or `list` with `--repo-root` pointed away from cwd reads and writes the manifest under `--repo-root`, never under a stale cwd-derived path (step 6).
- `BUG_BACKLOG.md`'s '`direct-jira` / `direct-run` resolve repo_root from cwd…' entry is removed once the fix ships.

## Deferred

- None yet — nothing has been dropped or postponed during implementation; permanent exclusions live in `## Out of scope`. Populate as items surface.
