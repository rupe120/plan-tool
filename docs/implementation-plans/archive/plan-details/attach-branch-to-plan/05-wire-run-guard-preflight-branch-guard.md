> **Auto-archived**: this plan was swept on 2026-06-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Wire the run guard: `_preflight_branch_guard` + `--switch-branch` on `run`

## Summary

Adds a branch-awareness preflight to `plan_tool/cli/run_cmd.py`: a new `_preflight_branch_guard` helper plus a `--switch-branch` flag on the `run` subparser. The guard fires only on a mutating `run` (`--mode run`, not `--dry-run`) — covering single-step, `--all` sweep, and `--reconcile` — and is gated first on `plan_tool/project_config.py:branch_awareness_enabled`, so an off-config (every repo today) is a byte-for-byte no-op. It composes step 4's `plan_tool/branch_ownership.py` lookups (`branch_owner` → `classify_branch`) over the current branch read once via step 2's `plan_tool/cli/gitcommit.py:current_branch`, then maps the tier to UX: **Tier 1–2 block unless the branch is this plan's** (non-zero rc), **Tier 3 warn + proceed**, **Tier 4 nudge** toward `expected_branch` (or, with `--switch-branch` on a clean tree, create-if-missing + switch). Non-git / detached HEAD (`current_branch` → `None`) prints a one-line note and proceeds. On green, every existing `run` test passes unchanged (guard is inert with the flag off), `run --help` advertises `--switch-branch` (the step's `gate`), and the new tests in `tests/cli/test_run_cmd.py` pin each tier's mapping.

## Table of Contents

- [Why](#why) — what the guard protects and why it lives in `run_cmd.py`
- [Files (creates vs edits)](#files-creates-vs-edits) — the three edited files
- [Implementation](#implementation) — the guard helper, its placement, the flag, the tier→UX map
- [Tests](#tests) — per-tier guard mapping, off-state/non-git no-ops, the `--help` gate
- [Acceptance criteria](#acceptance-criteria) — observable behaviors a reviewer can check
- [References](#references) — git docs underpinning the branch reads/switch
- [Deferred](#deferred) — commands and UX deliberately left out

## Why

`plan-tool run` executes wherever the developer happens to be checked out — there is no check that plan P's steps land on P's branch rather than another plan's branch or some unrelated one (plan "Problem statement"). Steps 1–4 built the cycle-free machinery to answer "who owns this branch?" (`plan_tool/branch_ownership.py:branch_owner` → `classify_branch`) and "where should P run?" (`expected_branch`), but nothing calls them. This step wires that classification into the one mutating entry point — `plan_tool/cli/run_cmd.py:cmd_run` — as a preflight that is **strict only where a local signal makes ownership unambiguous (Tier 1–2)** and stays out of the way otherwise (Tier 3–4), honoring the plan's "strict by signal, not by setting" principle. Keeping the guard a `run_cmd.py` preflight (not in `locator.py:resolve_plan_for_context`) is load-bearing: it must not block read-only/authoring commands that also resolve plans (plan "Risks → Guard placement too broad").

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/run_cmd.py` — add the `_preflight_branch_guard` helper; add three module imports (`project_config`, `branch_ownership`, `gitcommit` branch symbols); add one guarded call site in `cmd_run` after `run_slug` is computed and before the `--all` dispatch / either `_save_run_prefs` write; add the `--switch-branch` argument to the `run` subparser in `register`.
  - `tests/cli/test_run_cmd.py` — add the guard's unit/component tests (off-state no-op, non-git no-op, each tier's block/warn/nudge/switch mapping, the dirty-tree switch refusal) and a `run --help` surface assertion for the `--switch-branch` gate; extend `_sweep_args` (or add a dedicated namespace builder) with `switch_branch=False`.
  - `tests/cli/package_surface_help.golden.txt` — verify-no-drift: `--switch-branch` is a `run`-subparser flag, surfaced only by `run --help`, so the top-level `plan-tool --help` catalog this golden snapshots is **unchanged**; the step keeps `tests/cli/test_package_surface.py` green with this file byte-identical (re-baseline via `UPDATE_CLI_GOLDEN=1` only if a deliberate catalog edit is made — none is here).

## Implementation

All code lands in `plan_tool/cli/run_cmd.py`.

### Imports to add

- **`from plan_tool.project_config import branch_awareness_enabled, branch_prefixes`** (step 1 leaf).
- **`from plan_tool.branch_ownership import Tier, branch_owner, classify_branch, convention_owner, expected_branch`** (step 4 layer). `convention_owner` is used to surface the shadowed-convention conflict in the Tier-1 block message.
- **`from plan_tool.cli.gitcommit import branch_exists, checkout_existing_branch, create_and_checkout_branch, current_branch`** (step 2 helpers).
- **Import direction is acyclic.** `plan_tool/cli/gitcommit.py` imports nothing from `plan_tool.cli`; `plan_tool/branch_ownership.py` imports only the two leaves `plan_tool/project_config.py` + `plan_tool/branch_binding.py`; `plan_tool/project_config.py` is stdlib-only. So `run_cmd` → {`project_config`, `branch_ownership`, `gitcommit`} adds no edge to `app` and no cycle (matches the module docstring's one-directional import rule).
- **The step-1 import is deliberately not a direct `depends_on` edge.** This step imports `branch_awareness_enabled`/`branch_prefixes` from step 1's `plan_tool/project_config.py`, yet the frontmatter `depends_on` is `[2, 4]` with no `1`. That ordering is safe because step 4 (`depends_on: [1, 3]`) already requires step 1, so step 1 is transitively satisfied before this step runs; the direct edge is omitted on purpose to keep `depends_on` to the nearest predecessors rather than restating the transitive closure.

### `_preflight_branch_guard(args, *, ctx, plan_slug) -> Optional[int]`

Add the helper near the other `cmd_run` preflights (alongside `_confirm_missing_step_details` / the prefs helpers). **Return contract: `None` → proceed; an `int` → `cmd_run` returns it immediately.** Use a non-zero rc for a block/refusal (`2`, consistent with this file's other preflight rejections — the `--reconcile`/`--all` mutex gates). Steps:

1. **Flag-check first.** `if not branch_awareness_enabled(ctx.repo_root): return None`. This is the off-by-default short-circuit — no branch is read before it (plan "Risks → Flag-check leakage"; mirrors every other branch path).
2. **Read the current branch once.** `current = current_branch(ctx.repo_root)`. If `current is None` (detached HEAD / non-git, folded into one sentinel by step 2's `git symbolic-ref`), emit a one-line stderr note (e.g. via `warn(...)`: "branch awareness on but current branch is undeterminable (detached HEAD or non-git) — proceeding") and `return None`. This is the load-bearing "unknown branch → proceed with a note" path (plan "Risks → Non-git / detached HEAD").
3. **Compute inputs once** (keeps `classify_branch` pure, per step 4): `prefixes = branch_prefixes(ctx.repo_root)`; `registered = {e.slug for e in ctx.entries}` — the registered-slug set the Tier-2 condition needs, sourced from the already-loaded `PlanToolContext.entries` (each `plan_tool/locator.py:PlanEntry.slug`), not a fresh manifest read.
4. **Classify.** `owner = branch_owner(ctx.repo_root, current, registered, prefixes)` (the only I/O — reads the git-config override via step 3's `reverse_binding`); `cls = classify_branch(current, plan_slug, owner, prefixes)`.
5. **Map tier → UX:**
   - **Tier 1–2 (`cls.tier <= Tier.CONVENTION_OWNED`):**
     - `if cls.is_owned_by_plan: return None` — this is P's own branch; proceed silently.
     - Else **block**: `error(...)` naming the owning slug (`cls.owner`), the tier kind (ad-hoc binding vs convention name), and the remedy (`attach-branch`/`detach-branch` (step 6 verbs) or switch to P's expected branch); `return 2`. The integer-ordered `Tier(IntEnum)` makes the `<= Tier.CONVENTION_OWNED` predicate read naturally (step 4 chose `IntEnum` for exactly this).
     - **Surface the shadowed-convention conflict (Tier 1 only):** when `cls.tier == Tier.AD_HOC_OWNED`, also call `co = convention_owner(current, registered, prefixes)`; if `co is not None and co != cls.owner`, append a line noting the convention claim by `co` is shadowed by the ad-hoc binding (plan acceptance: "the conflict is surfaced"). The classifier never breaks this tie — ad-hoc already won in `branch_owner` — so surfacing it is purely the guard's message concern.
   - **Tier 3 (`Tier.ORPHAN_PATTERN`):** advisory only — `warn(...)` that the branch matches the convention pattern but no locally-registered plan owns it (likely someone else's / unpulled), then `return None`. Never blocks, interactive or not.
   - **Tier 4 (`Tier.UNOWNED`):**
     - `expected = expected_branch(ctx.repo_root, plan_slug, prefixes)`.
     - `if current == expected: return None` — already on the right branch (or no separate expected name applies); no nudge.
     - Else, branch on `getattr(args, "switch_branch", False)`:
       - **`--switch-branch` set:** the clean-tree-gated switch. `if _working_tree_dirty(ctx.repo_root):` refuse — `error("--switch-branch needs a clean working tree (commit or stash first)")`; `return 2`. Check the precondition **only on this switch path**, never unconditionally (a no-op-path clean-tree check would be a false refusal). On a clean tree: `if branch_exists(ctx.repo_root, expected): rc, tail = checkout_existing_branch(...)` else `rc, tail = create_and_checkout_branch(...)`. On `rc == 0` print what happened (switched / created+switched) and `return None`; on non-zero `error(tail)` and `return 2`.
       - **`--switch-branch` not set:** `warn(...)` nudging that P's expected branch is `expected` and `--switch-branch` will move there on a clean tree; `return None` (proceed). Non-interactive runs proceed identically — never wedge automation (plan: "Tier 3–4 warn-and-proceed").

- **`branch_exists` gates create-vs-switch (no try/switch fallback).** Step 2's `branch_exists` scopes to local `refs/heads`, so a `True` means a branch `checkout_existing_branch` (`git switch <name>`) can land on; a `False` routes to `create_and_checkout_branch` (`git switch -c <name>`). Conflating them is wrong — `git switch -c` errors when the branch already exists, and plain `git switch` errors when it doesn't.
- **Clean-tree reader choice.** Reuse this module's existing `plan_tool/cli/run_cmd.py:_working_tree_dirty` (the same reader the `--commit` sweep gate uses) so the guard and the sweep agree on "dirty". It duplicates `plan_tool/cli/gitcommit.py:working_tree_dirty`; consolidating that pair is a known cross-module refactor left for reconcile (see Deferred), not in this footprint.

### Call site in `cmd_run`

- **Placement:** immediately after `run_slug = slug_from_filename(path)` and **before** the `if getattr(args, "all", False):` sweep-dispatch block — i.e., before *both* `_save_run_prefs` writes (the post-sweep one and the single-step one) and before the `--reconcile` mutex branch and `RunLogWriter.start`.
- **Why before the prefs writes:** `_save_run_prefs` writes `.plan-tool/run-prefs.json`, which dirties the working tree; placing the guard after it would let the command's own bookkeeping trip `--switch-branch`'s clean-tree gate. The guard must measure the *user's* tree state, not the tool's (plan "Risks → Branch creation is a mutation").
- **Why before the run log / mutex:** a blocked or short-circuited preflight must leave no ghost run dir and must precede any work; a wrong-branch run is refused before validation noise.
- **Mutating gate (call-site predicate, single shared entry):**
  ```
  if args.mode == "run" and not args.dry_run:
      guard_rc = _preflight_branch_guard(args, ctx=ctx, plan_slug=run_slug)
      if guard_rc is not None:
          return guard_rc
  ```
  `cmd_run` is the single funnel all mutating `run` variants pass through: single-step run, `run --all` (which dispatches into `_cmd_run_sweep` → `run_step` *after* this call site), and `run --reconcile` (which requires `mode == "run"`). Because the guard sits before the `if getattr(args, "all", False):` dispatch, it runs exactly once for the sweep too — `_cmd_run_sweep` calls `run_step` directly (never re-entering `cmd_run`), so placing the guard inside it would be the only way to double-guard. One predicate-gated call here covers all three variants; review modes (`mode != "run"`) and `--dry-run` skip it. Do **not** add a second call into `_cmd_run_sweep`.

### `--switch-branch` flag in `register`

- Add to the `run` subparser (`p_run`), not to `reconcile-code`:
  ```
  p_run.add_argument(
      "--switch-branch",
      action="store_true",
      dest="switch_branch",
      help=(
          "for branch-aware repos: on an unowned branch whose plan expects a "
          "different branch, switch to (creating if missing) the plan's "
          "expected branch on a clean tree before running; refuses on a dirty "
          "tree. No effect when branch awareness is off."
      ),
  )
  ```
- **Read it with `getattr(args, "switch_branch", False)` in the guard** so hand-built test namespaces (and any caller that pre-dates the attribute) stay safe; the flag ships on `p_run` so real `run` invocations always carry it.

### Foundational logic and shared locations

- **Foundational logic:** "on a mutating run, classify the current branch against the plan and block / warn / nudge / switch accordingly." Grepping `plan_tool/` and `tests/` for `_preflight_branch_guard` / `switch_branch` / `--switch-branch` returns nothing — no existing guard to fold in.
- **The classification rule itself is not duplicated here** — it lives once in `plan_tool/branch_ownership.py` (step 4); this step only maps its verdict to UX.
- **Git clean-tree read is duplicated** across `plan_tool/cli/run_cmd.py:_working_tree_dirty` and `plan_tool/cli/gitcommit.py:working_tree_dirty`; the guard reuses the former. Unifying the two is a cross-module consolidation `detail` cannot mint → **Deferred** (reconcile).

## Tests

All cases land in `tests/cli/test_run_cmd.py` (extends the existing characterization file). Drive `_preflight_branch_guard` directly with a hand-built `PlanToolContext` (via the file's `_ctx`) + an `argparse.Namespace`, monkeypatching the branch symbols imported into `plan_tool.cli.run_cmd` (`branch_awareness_enabled`, `current_branch`, `branch_owner`, `classify_branch`, `convention_owner`, `expected_branch`, `branch_exists`, the two mutators, `_working_tree_dirty`) to inject each scenario without standing up real git/config state — the pure tier logic is already pinned in `tests/test_branch_ownership.py` (step 4). Add `switch_branch=False` to the namespace builder used to drive the guard. Real `git` is allowed by `tests/conftest.py` (only `claude`/`codex` are gated), so the one end-to-end switch case may use a `tmp_path` repo via `_init_git_repo`.

### Off-state / non-git no-ops
- `test_guard_noop_when_disabled` — `branch_awareness_enabled` → `False`: returns `None`, and `current_branch` is never called (no branch read before the flag check).
- `test_guard_noop_non_git_or_detached` — enabled, `current_branch` → `None`: returns `None` and prints a note to stderr; never classifies.

### Tier 1–2 (block-unless-mine)
- `test_guard_tier1_blocks_other_plan` — ad-hoc owner `Q` ≠ `plan_slug`: returns non-zero, message names `Q`.
- `test_guard_tier1_proceeds_own_plan` — ad-hoc owner == `plan_slug` (`is_owned_by_plan` True): returns `None`.
- `test_guard_tier1_surfaces_shadowed_convention` — ad-hoc `Q` while `convention_owner` returns a different `R`: block message names both `Q` and the shadowed `R`.
- `test_guard_tier2_blocks_other_plan` — convention owner `R` ≠ `plan_slug`: returns non-zero.
- `test_guard_tier2_proceeds_own_plan` — convention owner == `plan_slug`: returns `None`.

### Tier 3 (warn + proceed)
- `test_guard_tier3_warns_and_proceeds` — `Tier.ORPHAN_PATTERN`: returns `None`, emits a warning; no block.

### Tier 4 (nudge / switch)
- `test_guard_tier4_no_action_when_on_expected` — unowned and `current == expected_branch`: returns `None`, no nudge.
- `test_guard_tier4_nudges_when_elsewhere` — unowned, `expected` ≠ `current`, no `--switch-branch`: returns `None`, emits the expected-branch nudge.
- `test_guard_tier4_switch_creates_missing` — `switch_branch=True`, clean tree, `branch_exists` → `False`: calls `create_and_checkout_branch(expected)`, returns `None`.
- `test_guard_tier4_switch_uses_existing` — `switch_branch=True`, clean tree, `branch_exists` → `True`: calls `checkout_existing_branch(expected)` (not the create mutator), returns `None`.
- `test_guard_tier4_switch_refuses_dirty` — `switch_branch=True`, `_working_tree_dirty` → `True`: returns non-zero, neither mutator called.
- `test_guard_tier4_switch_mutator_failure` — mutator returns `(rc!=0, tail)`: returns non-zero, surfaces `tail`.

### Call-site gating (component, via `cmd_run` or the predicate)
- `test_run_review_mode_skips_guard` — `--mode check` (mode ≠ "run"): guard not invoked. **Monkeypatch `run_cmd.run_step` (or spy `run_cmd._preflight_branch_guard`)** so the post-guard path doesn't reach the real `claude` backend and trip `tests/conftest.py`'s autouse real-backend gate — the `--dry-run` sibling needs no such stub since dry-run never calls claude.
- `test_run_dry_run_skips_guard` — `--dry-run`: guard not invoked.

### Flag surface (the step's `gate`)
- `test_run_help_advertises_switch_branch` — `build_parser()`'s `run` subparser `format_help()` contains `--switch-branch` (mirrors the frontmatter `gate: uv run plan-tool run --help | grep -q -- --switch-branch`).
- `tests/cli/test_package_surface.py` stays green with `package_surface_help.golden.txt` byte-unchanged (flag is subparser-local).

### Test-creation order (feature step)
- **This is a feature step — new behavior.** Write each test above alongside the guard/flag implementation.
- **Green-before-done gate:** every new test passes (`uv run pytest tests/cli/test_run_cmd.py -q`) **and** the full non-integration suite stays green unchanged (`uv run pytest -m "not integration" tests/ -q`) — the off-state guarantee means no existing `run` test may regress.

## Acceptance criteria

- With branch awareness off (no config), `_preflight_branch_guard` returns `None` having read no branch; all pre-existing `run` tests pass unchanged.
- Outside a git repo / on detached HEAD, the guard returns `None` and prints a note — never raises, never blocks.
- On a Tier 1 (ad-hoc-bound) or Tier 2 (locally-registered convention) branch owned by another plan, `run <other>` returns non-zero naming the owner; `run <owner>` proceeds.
- A Tier 1 branch that also matches a different plan's convention name surfaces the shadowed-convention conflict in the block message.
- On a Tier 3 orphan-pattern branch, `run` warns and proceeds (rc unaffected).
- On a Tier 4 unowned branch whose `expected_branch` differs, `run` nudges and proceeds; `run --switch-branch` on a clean tree creates-if-missing and switches (`checkout_existing_branch` when the branch exists, `create_and_checkout_branch` otherwise), and refuses non-zero on a dirty tree.
- The guard call site sits before both `_save_run_prefs` writes and the run-log open; review modes and `--dry-run` skip it.
- `plan-tool run --help` lists `--switch-branch`; `tests/cli/test_package_surface.py` passes with the golden unchanged.

## References

- [Git - git-symbolic-ref Documentation](https://git-scm.com/docs/git-symbolic-ref) — the non-zero exit on detached HEAD / non-repo behind `current_branch` returning `None` (the guard's no-op path).
- [Git - git-branch Documentation](https://git-scm.com/docs/git-branch) — `git switch` / `git switch -c` semantics behind the create-if-missing, clean-tree-gated, never-clobber `--switch-branch` path.
- [Git - git-config Documentation](https://git-scm.com/docs/git-config) — `--local` storage of the ad-hoc override that `branch_owner`/`expected_branch` read, driving Tier 1.

## Deferred

- **Guarding the standalone `reconcile-code` verb and other commands** — the guard covers `run` (single / `--all` / `--reconcile`) only, matching the plan's "run, and reconcile under `run`" scope; `cmd_reconcile_code` and the read-only/authoring verbs are not wired in. The plan keeps the guard helper reusable for a later opt-in (plan "Deferred").
- **Interactive y/n switch offer on a TTY** — the deterministic surface is the explicit `--switch-branch` flag plus the advisory nudge; an interactive prompt that maps to the same clean-tree-gated switch is an additive enhancement.
- **Consolidating `_working_tree_dirty` (run_cmd) with `gitcommit.working_tree_dirty`** — a cross-module refactor `detail` cannot mint; routed to reconcile.
- **Disambiguated branch creation (`plan/<slug>-2` from default)** — step 7's `cmd_create` collision warning, not the run guard.
