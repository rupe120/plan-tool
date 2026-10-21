> **Replaced**: this file has been superseded by `docs/implementation-plans/2-direct-pipeline-repo-root-resolution.md`.
> Preserved here for history; do not edit.

## Overview

Fixes `plan-tool create`'s repo-root relocation (the seed-derived override `find_umbrella_root` computes in `plan_tool/cli/authoring.py` around line 507-541) so it propagates fully instead of leaving stale roots behind downstream. Two sites are fixed together: `create_plan` itself, where the manifest write can diverge from the plan write under a relocated root, and the `direct-jira`/`direct-run` chains in `plan_tool/cli/direct_cmd.py`, which resolve `repo_root` once before `create` runs and never learn about a later relocation. The fix threads the resolved root through `create_plan`'s manifest-path default and through every downstream stage namespace via the existing `args.repo_root`/`repo_root_override` plumbing, and adds a cleanliness guard on the relocated root before the first post-create commit. Standalone (non-direct-*) `detail`/`run` invocations are unaffected, since they resolve their own root fresh from cwd/`--repo-root` each time with no stale in-process hand-off to go bad.

## Problem statement

`cmd_create` can relocate a plan's working repo root away from the cwd-derived default when a `--from-existing` seed's body references files under a different `.git` ancestor (narrower — a nested repo under the cwd root — or broader — a sibling/umbrella root); once confirmed (auto-confirmed under `--yes`), `cmd_create` writes the plan, its detail bundle, and the manifest entry under that relocated root instead of the cwd-derived one. Two downstream call sites don't know about this relocation, and both need fixing together:

1. **`create_plan` itself** (`plan_tool/create.py` line ~5669): `mf = manifest_path or default_manifest_path()` calls `default_manifest_path()` with no `repo_root` argument when `--manifest` isn't passed explicitly, so per `plan_tool/locator.py:54`'s docstring it re-walks from the current working directory and lands on the original, pre-override root — not the `repo_root` `create_plan` was actually called with. Meanwhile `resolve_output_dir(repo_root, ...)` a few lines above does use the overridden `repo_root`. So a single `create_plan` call can write the plan file under the umbrella root's `docs/implementation-plans/` while registering it in the cwd root's `.plan-tool/plans.json` manifest — a divergence entirely internal to `create`. Re-deriving 'the root create used' from `CreateResult.manifest_path` (the naive fix) would read back the wrong root here, because the manifest itself was written to the wrong place.

2. **`direct_cmd.py`**: `cmd_direct_jira` and `cmd_direct_run` both call `repo_root = _resolve_cmd_repo_root(args)` once, at the top, before `create` runs, and every stage after that reuses this stale value — the `working_tree_dirty(repo_root)` / `commit_all(repo_root, ...)` calls after `detail` (step 4) and after `completeness-apply` (step 5) commit against the wrong tree, and downstream stage handlers (`cmd_detail`, `cmd_completeness_apply`, `cmd_jira`, `cmd_run`, `cmd_reconcile_code`) each build context via `_load_context(args)` → `build_plan_tool_context(..., repo_root_override=args.repo_root)`, but `_stage_namespace` never sets `.repo_root`, so it stays `None` and each stage falls back to its own cwd-walk. Concretely, `cmd_detail` can't find `plan_name` in the cwd manifest (it was registered in the umbrella manifest), and the chain aborts 'plan not found' even though `create` succeeded and the plan exists on disk.

Source: `BUG_BACKLOG.md` RISK entry '`direct-jira` / `direct-run` resolve repo_root from cwd, not the repo `create` actually wrote to' (filed 2026-07-17, #118 direct-pipeline post-run `/code-review`, CONFIRMED).

## Architecture

1. **Fix `create_plan`'s manifest-path default first.** Change `mf = manifest_path or default_manifest_path()` to `mf = manifest_path or default_manifest_path(repo_root)`, making `create_plan` internally consistent (plan file and manifest entry always land under the same root) regardless of caller — a prerequisite for any downstream fix to have a correct root to read back. Explicit `--manifest` callers are unaffected since their path already wins via short-circuiting.

2. **Derive the actual working root from `CreateResult`, not a pre-create snapshot.** Once (1) lands, `CreateResult.manifest_path.parent.parent` (or equivalently deriving from `CreateResult.plan_path`'s owning `.git`/`.plan-tool` ancestor via `find_repo_root_from_cwd(start=...)`, which already accepts a `start` override per `plan_tool/locator.py:135`) reliably reflects the root `create` actually used. Prefer deriving from `plan_path`'s owning root if the two derivations can diverge under an explicit `--manifest` override, since that's the tree every downstream git operation (commit, dirty-check) actually needs.

3. **Thread the resolved root into every downstream stage namespace.** In both `cmd_direct_jira` and `cmd_direct_run`, after `result: CreateResult = sink[-1]` is read and validated (after the split-proposal / iteration-failure / size-gate guards), resolve the actual root per decision 2 and set it as `repo_root` on every subsequent `_stage_namespace(...)` call (detail, completeness-apply, jira/run, reconcile-code), and replace every post-create use of the original top-of-function `repo_root` local (the `working_tree_dirty`/`commit_all` calls in steps 4 onward of both verbs) with this resolved value. The step-0 precondition check (`working_tree_dirty` before `create` runs) correctly keeps using the original cwd-derived root — there is no other root to check yet at that point.

4. **Re-verify cleanliness of the relocated root before folding it into an auto-generated commit.** When the resolved root differs from the original cwd-derived root, add a cleanliness check on the resolved root immediately after relocation is detected, before `detail` runs — if unexpectedly dirty from something other than this run's own writes, abort with a clear message (mirroring the step-0 precondition's existing error shape) rather than commingling unrelated changes. This is a new guard, not a relaxation of an existing one.

5. **Scope boundary: standalone (non-direct-*) invocations are out of scope.** `plan-tool detail <name>` / `plan-tool run <name>` invoked directly already resolve their own root from cwd/`--repo-root` independently each time — there is no stale pre-create snapshot problem for them.

**Confirmed compatible fix surface:** every downstream stage handler already honors `args.repo_root` as an override (`build_plan_tool_context(..., repo_root_override=args.repo_root)`, `plan_tool/locator.py` around line 528-533) — the existing `--repo-root` flag's plumbing. The fix does not need a new 'handler context-resolution seam' abstraction; it needs the create-resolved root threaded into that existing override field on every downstream stage namespace `_stage_namespace` builds.

## Out of scope

- Redesigning `_load_context` / `resolve_plan_for_context`'s general per-invocation root-resolution model — every non-direct-* command keeps resolving from cwd/`--repo-root` exactly as today.
- A new 'handler context-resolution seam' abstraction — the existing `--repo-root`/`repo_root_override` plumbing already covers this; adding a new seam would be unjustified scope growth for what's actually a threading fix.
- Branch-awareness / worktree provisioning interactions — this seed is about repo-root resolution, not branch or worktree selection.
- The `emit_concept_tree` dormant-twin bug — a separate, already-filed BUG_BACKLOG RISK entry, unrelated code path, zero production callers; not touched here.

## Risks

- Without the decision-4 cleanliness guard, when create relocates to a root different from the cwd-derived one, that relocated repo's pre-existing dirty state (never checked by step 0's precondition, which only inspects the cwd repo) could get silently folded into the first post-create `commit_all`'s auto-generated commit message, commingling unrelated changes. This is a real gap the fix would otherwise introduce (today's code only 'works' because it never notices the relocation at all). Mitigation: add a cleanliness check on the resolved root immediately after relocation is detected, before `detail` runs, aborting with a clear error (mirroring step 0's existing precondition shape) if the relocated root is unexpectedly dirty.

## Testing

Drive a seed whose file references resolve to a broader (sibling umbrella) root and one that resolves to a narrower (nested) root, each through both `direct-jira` and `direct-run` end-to-end (fake/stub invokers per `tests/conftest.py`'s autouse real-backend gate), confirming: the plan is found by `detail`/`completeness-apply`/`jira`/`run`; commits land in the relocated repo (not the original cwd repo); and a pre-existing dirty relocated repo aborts cleanly instead of commingling changes.

## Acceptance criteria

- A `direct-jira` or `direct-run` invocation whose `--from-existing` seed references files under a different `.git` ancestor than cwd (broader or narrower) completes the full chain (`create → detail → completeness-apply → jira` / `→ run --all --commit → reconcile-code`) without a spurious 'plan not found' abort.
- `create_plan` never writes the plan file and its manifest entry under two different roots in the same call, regardless of caller (direct-* chain or a standalone `plan-tool create`).
- Every post-create git operation in the direct-* chain (`working_tree_dirty` / `commit_all` calls in steps 4+ of both verbs) targets the root `create` actually used, not the pre-create cwd snapshot.
- When create relocates to a different root than the one checked at step 0, and that relocated root is unexpectedly dirty from unrelated pre-existing changes, the chain aborts with a clear message instead of folding those changes into an auto-generated commit.
- The no-relocation (common) case is behaviorally unchanged — same commits, same root, no new prompts or checks fire when `create` doesn't relocate.
- `BUG_BACKLOG.md`'s '`direct-jira` / `direct-run` resolve repo_root from cwd…' entry is removed once the fix ships.
