> **Replaced**: this file has been superseded by `docs/implementation-plans/2-direct-pipeline-repo-root-resolution.md`.
> Preserved here for history; do not edit.

# Plan seed: fix `create`'s repo-root relocation not propagating to downstream context (direct-* chain + `create_plan` itself)

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing plan-seeds/direct-pipeline-repo-root-resolution.md --iterate
```

It is **not** itself a plan — `plan-tool create` consumes the prose below and
proposes a step decomposition; the author then runs `plan-tool detail` per step.

> **Source:** `BUG_BACKLOG.md` RISK entry "`direct-jira` / `direct-run` resolve
> repo_root from cwd, not the repo `create` actually wrote to" (filed
> 2026-07-17, #118 direct-pipeline post-run `/code-review`, CONFIRMED). This
> seed's final step must remove that entry from `BUG_BACKLOG.md` when the fix
> ships (per `BACKLOG.md`'s "which file does my entry go in?" bookkeeping
> rule) — do not leave it dangling as stale.

## Problem statement

`cmd_create` can **relocate** the plan's working repo root away from the
cwd-derived default: when a `--from-existing` seed's body references files
that live under a different `.git` ancestor (narrower — a nested repo under
the cwd root — or broader — a sibling/umbrella root), `cmd_create` computes a
seed-derived override (`find_umbrella_root` in
`plan_tool/cli/authoring.py` around line 507-541) and, once confirmed
(auto-confirmed under `--yes`), writes the plan, its detail bundle, and the
manifest entry under that **relocated** root instead of the cwd-derived one.

Two call sites downstream of that relocation don't know about it, and both
need fixing together — fixing only one leaves the chain broken:

### 1. `create_plan` itself: the manifest write can diverge from the plan write

`plan_tool/create.py` line ~5669:

```python
mf = manifest_path or default_manifest_path()
```

`manifest_path` here is `args.manifest`, which is `None` unless the operator
passes `--manifest` explicitly (the common case). When it's `None`,
`default_manifest_path()` is called **with no `repo_root` argument** — see
`plan_tool/locator.py:54`, whose docstring says exactly this: "When
`repo_root` is omitted it is resolved by walking up from the **current
working directory**." That re-walk lands back on the *original*,
pre-override root (cwd hasn't changed mid-process) — **not** the
`repo_root` parameter `create_plan` was actually called with, which may
already be the seed-derived override.

Meanwhile `output_dir` (a few lines above, `resolve_output_dir(repo_root,
...)`) **does** use the overridden `repo_root`. So in exactly the scenario
this bug is about, a single `create_plan` call can write the plan file under
the umbrella root's `docs/implementation-plans/` while registering it in the
**cwd root's** `.plan-tool/plans.json` manifest — a divergence entirely
internal to `create`, independent of the direct-* chain below. Any fix that
re-derives "the root `create` used" from `CreateResult.manifest_path` (the
naive reading of the original bug's "Fix" suggestion) would read back the
**wrong** root here, because the manifest itself was written to the wrong
place.

### 2. `direct_cmd.py`: downstream stages resolve context from a stale, pre-create root

`plan_tool/cli/direct_cmd.py` — both `cmd_direct_jira` and `cmd_direct_run`
call `repo_root = _resolve_cmd_repo_root(args)` **once, at the top**, before
`create` has run. Every stage after that reuses this same stale value:

- The `working_tree_dirty(repo_root)` / `commit_all(repo_root, ...)` calls
  after `detail` (step 4 in both verbs) and after `completeness-apply` (step
  5) commit against the wrong tree when create relocated.
- Downstream stage handlers (`cmd_detail`, `cmd_completeness_apply`,
  `cmd_jira`, `cmd_run`, `cmd_reconcile_code`) each build their own context
  via `_load_context(args)` →
  `build_plan_tool_context(args.plans_dir, manifest_path=args.manifest,
  repo_root_override=args.repo_root)`. `_stage_namespace` (the
  copy-and-override helper both verbs use to build each stage's namespace)
  never sets `.repo_root`, so it stays whatever the top-level CLI invocation
  left it as (`None` in the common no-`--repo-root`-flag case) — the
  downstream stages fall back to their own cwd-walk and never learn about
  create's relocation. Concretely: `cmd_detail` can't find `plan_name` in the
  cwd manifest (it was registered in the umbrella manifest), and the chain
  aborts "plan not found" even though `create` succeeded and the plan exists
  on disk.

**Confirmed compatible fix surface:** every downstream stage handler already
honors `args.repo_root` as an override
(`build_plan_tool_context(..., repo_root_override=args.repo_root)`, see
`plan_tool/locator.py` around line 528-533) — this is the existing
`--repo-root` flag's plumbing. So the fix does **not** need a new
"handler context-resolution seam" abstraction (an alternative the original
bug's "Fix" text floated as a heavier structural option) — it needs the
create-resolved root threaded into that *existing* override field on every
downstream stage namespace `_stage_namespace` builds.

## Resolved design decisions

1. **Fix `create_plan`'s manifest-path default first.** Change
   `mf = manifest_path or default_manifest_path()` to pass the resolved
   `repo_root` through: `mf = manifest_path or default_manifest_path(repo_root)`.
   This makes `create_plan` internally consistent (plan file and manifest
   entry always land under the same root) regardless of caller — a
   prerequisite for any downstream fix to have a correct root to read back.
   Explicit `--manifest` callers are unaffected (their path already wins via
   `manifest_path or ...` short-circuiting).

2. **Derive the actual working root from `CreateResult`, not from a
   pre-create snapshot.** Once (1) lands, `CreateResult.manifest_path.parent.parent`
   (or equivalently `CreateResult.plan_path`'s owning `.git`/`.plan-tool`
   ancestor via `find_repo_root_from_cwd(start=...)`, which already accepts a
   `start` override per `plan_tool/locator.py`) reliably reflects the root
   `create` actually used. Pick whichever derivation is more robust against
   an explicit `--manifest` override pointing somewhere unconventional (the
   two should agree on the ordinary path; if they can diverge under an
   explicit `--manifest`, prefer deriving from `plan_path`'s owning root,
   since that's the tree every downstream git operation — commit, dirty-check
   — actually needs).

3. **Thread that resolved root into every downstream stage namespace.** In
   both `cmd_direct_jira` and `cmd_direct_run`, after `result: CreateResult =
   sink[-1]` is read and validated (after the split-proposal /
   iteration-failure / size-gate guards — no point threading a root for a
   chain that's about to stop anyway), resolve the actual root per decision 2
   and set it as `repo_root` on every subsequent `_stage_namespace(...)` call
   (detail, completeness-apply, jira/run, reconcile-code) so
   `args.repo_root` overrides each stage's own cwd-walk. Also replace every
   post-create use of the original top-of-function `repo_root` local
   (the `working_tree_dirty(repo_root)` / `commit_all(repo_root, ...)` calls
   in steps 4 onward of both verbs) with this resolved value. The **step-0
   precondition check** (`working_tree_dirty` before `create` even runs)
   correctly keeps using the original cwd-derived root — there is no other
   root to check yet at that point.

4. **Re-verify cleanliness of the relocated root before folding it into an
   auto-generated commit.** When the resolved root (decision 2) differs from
   the original cwd-derived root, the relocated repo is a *different* git
   tree whose pre-existing dirty state was never checked by step 0's
   precondition (which only ever looked at the cwd repo). Without a check,
   the first post-create `commit_all` in the relocated repo would silently
   fold any pre-existing unrelated uncommitted changes there into the
   auto-generated "author plan and detail" commit message. Add a cleanliness
   check on the resolved root immediately after relocation is detected,
   *before* `detail` runs — if the relocated root is unexpectedly dirty from
   something other than this run's own writes, abort with a clear message
   (mirroring the step-0 precondition's existing error shape) rather than
   commingling unrelated changes.
   - This is a **new** guard, not a relaxation of an existing one: today
     nothing checks the relocated root's cleanliness at all pre-relocation,
     so this closes a real gap the fix would otherwise introduce (the current
     code accidentally "works" here only because it never notices the
     relocation in the first place).

5. **Scope boundary: standalone (non-direct-*) invocations are out of
   scope.** `plan-tool detail <name>` / `plan-tool run <name>` invoked
   directly by an operator (outside `direct-jira`/`direct-run`) already
   resolve their own root from cwd/`--repo-root` independently each time —
   there is no "stale pre-create snapshot" problem for them, because there's
   no in-process hand-off to go stale. This seed's fix is scoped to the
   in-process chain in `plan_tool/cli/direct_cmd.py` (plus the `create_plan`
   manifest-path prerequisite in decision 1, which is a correctness fix on
   its own regardless of caller). Do not redesign `_load_context` /
   `resolve_plan_for_context`'s general per-invocation resolution model.

## Seams to reuse (verified at HEAD)

- `plan_tool/create.py` line ~5669 (`mf = manifest_path or
  default_manifest_path()`) — decision 1's fix site.
- `plan_tool/locator.py:54` `default_manifest_path(repo_root: Optional[Path]
  = None)` — already accepts `repo_root`; decision 1 just needs to pass it.
- `plan_tool/locator.py:135` `find_repo_root_from_cwd(start: Optional[Path]
  = None)` — already accepts a `start` override, usable for decision 2's
  root re-derivation without touching cwd.
- `plan_tool/cli/direct_cmd.py` — `cmd_direct_jira` / `cmd_direct_run` (both
  need decision 3's threading + decision 4's guard), `_stage_namespace`
  (the copy-and-override helper every stage namespace goes through).
- `plan_tool/cli/context.py:_resolve_cmd_repo_root` — the step-0
  precondition's existing resolution call; leave as-is per decision 3.
- `plan_tool/locator.py` `build_plan_tool_context(...,
  repo_root_override=...)` around line 523-533 — confirms every downstream
  stage handler already honors an `args.repo_root` override; no new plumbing
  needed there.
- `plan_tool/cli/gitcommit.py` `working_tree_dirty` / `commit_all` — reused
  as-is, just called with the corrected root.

## Scope of work (indicative — let create decompose)

1. Fix `create_plan`'s manifest-path default to respect the resolved
   `repo_root` (decision 1).
2. Resolve-and-thread the actual working root through
   `cmd_direct_jira`/`cmd_direct_run`'s downstream stage namespaces and
   post-create git operations (decisions 2, 3).
3. Add the relocated-root cleanliness guard before the first post-create
   commit (decision 4).
4. Tests: a seed whose file references resolve to a **broader** (sibling
   umbrella) root and one that resolves to a **narrower** (nested) root, each
   driven through `direct-jira` and `direct-run` end-to-end (fake/stub
   invokers per `tests/conftest.py`'s autouse real-backend gate) confirming:
   the plan is found by `detail`/`completeness-apply`/`jira`/`run`, commits
   land in the relocated repo (not the original cwd repo), and a
   pre-existing dirty relocated repo aborts cleanly instead of commingling.
5. Docs/status step: remove the fixed RISK entry from `BUG_BACKLOG.md` (the
   source entry named above) per `BACKLOG.md`'s bookkeeping rule.

## Non-goals / out of scope

- Redesigning `_load_context` / `resolve_plan_for_context`'s general
  per-invocation root-resolution model (decision 5) — every non-direct-*
  command keeps resolving from cwd/`--repo-root` exactly as today.
- A new "handler context-resolution seam" abstraction — the existing
  `--repo-root`/`repo_root_override` plumbing already covers this; adding a
  new seam would be unjustified scope growth for what's actually a threading
  fix (see "Confirmed compatible fix surface" above).
- Branch-awareness / worktree provisioning interactions — out of scope;
  this seed is about repo-root *resolution*, not branch or worktree
  selection.
- The `emit_concept_tree` dormant-twin bug (a separate, already-filed
  BUG_BACKLOG RISK entry, unrelated code path, zero production callers) —
  not touched here.

## Acceptance criteria (plan-level)

- A `direct-jira` or `direct-run` invocation whose `--from-existing` seed
  references files under a different `.git` ancestor than cwd (broader or
  narrower) completes the full chain (`create → detail → completeness-apply
  → jira` / `→ run --all --commit → reconcile-code`) without a spurious
  "plan not found" abort.
- `create_plan` never writes the plan file and its manifest entry under two
  different roots in the same call, regardless of caller (direct-* chain or
  a standalone `plan-tool create`).
- Every post-create git operation in the direct-* chain (`working_tree_dirty`
  / `commit_all` calls in steps 4+ of both verbs) targets the root `create`
  actually used, not the pre-create cwd snapshot.
- When create relocates to a different root than the one checked at step 0,
  and that relocated root is unexpectedly dirty from unrelated
  pre-existing changes, the chain aborts with a clear message instead of
  folding those changes into an auto-generated commit.
- The no-relocation (common) case is behaviorally unchanged — same commits,
  same root, no new prompts or checks fire when `create` doesn't relocate.
- `BUG_BACKLOG.md`'s "`direct-jira` / `direct-run` resolve repo_root from
  cwd…" entry is removed once the fix ships.
