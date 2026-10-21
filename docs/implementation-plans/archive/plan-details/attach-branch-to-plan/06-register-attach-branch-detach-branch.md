> **Auto-archived**: this plan was swept on 2026-06-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Register `attach-branch` / `detach-branch` verbs on `manifest.py`

## Summary

Adds two manifest-group verbs to `plan_tool/cli/manifest.py` — `attach-branch <plan> <branch>` (set the ad-hoc override) and `detach-branch <plan>` (clear it) — wired through the four-site verb-registration footprint (`register()` parser+dispatch+handlers, `app.py` re-import, `parser.py:CANONICAL_COMMAND_ORDER`, `__init__.py` catalog/`__all__`). Both **refuse non-zero when branch awareness is off** (flag-check first, before any branch read). `attach-branch` records the override via step 3's `branch_binding.set_binding`; when the requested branch is **another registered plan's convention name** it strong-warns and, on consent, **re-homes** — branches the plan's own `derive_branch` name *from the existing branch* (carrying the work over) on a clean tree, then binds to it. `detach-branch` clears via `clear_binding` (quiet no-op when nothing was bound). On green: `attach-branch --help` / `detach-branch --help` exit 0 (the step's `gate`), the two verbs dispatch end-to-end, and `tests/cli/package_surface_help.golden.txt` is regenerated to carry them.

## Table of Contents

- [Why](#why) — what the verbs unblock and why they join the manifest group
- [Files (creates vs edits)](#files-creates-vs-edits) — the four code edits + two test edits
- [Implementation](#implementation) — handlers, the disabled-refusal, the collision/re-home path, and the four wiring sites
- [Tests](#tests) — per-behavior cases in `test_manifest_cmds.py` + the golden regen
- [Acceptance criteria](#acceptance-criteria) — observable behaviors a reviewer can check
- [References](#references) — git docs underpinning the override store + branch creation
- [Deferred](#deferred) — out-of-footprint items routed elsewhere

## Why

Steps 1–4 built the cycle-free machinery to store an ad-hoc plan→branch override (`plan_tool/branch_binding.py`) and to answer "who owns branch B?" (`plan_tool/branch_ownership.py`), and step 5 wired the run guard to *consume* an override. Nothing yet lets a developer *set* one. This step adds the user-facing verbs: `attach-branch` records the override that overrides `expected_branch`'s derivation, `detach-branch` clears it back to the derived default. They live in the `manifest.py` command group (joining `register`/`deregister`/`sweep`) because they are slug-keyed, registered-plan-scoped manifest-mode commands — the same group, resolver helpers (`_resolve_register_target` / `_resolve_deregister_target`), and directory-mode refusal apply. The protected behavior is the **convention-namespace warning**: binding plan P to a branch that is plan R's reserved `<prefix><slug>` name would let two plans claim one branch, so `attach-branch` re-homes P's work onto P's own name instead.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/manifest.py` — add `cmd_attach_branch` / `cmd_detach_branch`; add four imports (`project_config` branch helpers, `branch_binding` store, `branch_ownership` lookup, two `gitcommit` branch mutators); extend the existing `from plan_tool.cli.gitcommit import ...` line; add both verbs' subparsers + dispatch entries in `register()`.
  - `plan_tool/cli/app.py` — extend the `from plan_tool.cli.manifest import (...)` block with `cmd_attach_branch`, `cmd_detach_branch` so the `plan_tool.cli` package mirror exposes `plan_tool.cli.cmd_attach_branch` / `…cmd_detach_branch`.
  - `plan_tool/cli/parser.py` — append `"attach-branch"`, `"detach-branch"` to the tail of `CANONICAL_COMMAND_ORDER` (renders them right after `annotate`, before the non-canonical aliases).
  - `plan_tool/cli/__init__.py` — add two catalog docstring lines under the **State management** group (beside `register`/`deregister`/`sweep`) and two `__all__` entries (`"cmd_attach_branch"`, `"cmd_detach_branch"`).
  - `tests/cli/test_manifest_cmds.py` — add `TestAttachBranch` / `TestDetachBranch` classes plus a parser-surface assertion.
  - `tests/cli/package_surface_help.golden.txt` — regenerate (`UPDATE_CLI_GOLDEN=1`): the metavar brace list gains `attach-branch,detach-branch` after `annotate`, and the description block gains the two new catalog lines.
- **No `COMMAND_MODULES` edit:** `manifest.py` (`_manifest_commands`) is already in the `app.py:COMMAND_MODULES` tuple — adding verbs to an already-registered module needs no registry entry.

## Implementation

### `plan_tool/cli/manifest.py` — imports

- **Extend the existing gitcommit import** from `from plan_tool.cli.gitcommit import commit_all, working_tree_dirty` to also pull `branch_exists, current_branch, checkout_existing_branch, create_and_checkout_branch` (step 2 mutators/readers).
- **Add three domain-leaf imports** (all acyclic — none import `plan_tool.cli`):
  - `from plan_tool.project_config import branch_awareness_enabled, branch_prefixes, derive_branch` (step 1).
  - `from plan_tool.branch_binding import BranchBindingError, clear_binding, set_binding` (step 3).
  - `from plan_tool.branch_ownership import OWNER_AD_HOC, OWNER_CONVENTION, branch_owner` (step 4).
- **`slug_from_filename`** is already imported from `plan_tool.locator`; reuse it for slug derivation. No new manifest read — the override lives in git config, not `structured_plans.json`, so these verbs never call `append_to_manifest` / `default_manifest_path`.

### `cmd_attach_branch(args) -> int`

Front-load **every refusal-capable check before any git mutation** (gate → resolve → uniqueness/collision → consent → clean-tree → mutate → persist), so a rejected request leaves no orphan branch or binding:

1. **Context + manifest-mode guard.** `ctx = _load_context(args)`; if `ctx.plans_dir is not None`, `error("attach-branch is a manifest-mode command; drop --plans-dir / PLAN_TOOL_PLANS_DIR to use it.")` and `return 2` (the verbatim shape `cmd_register` uses).
2. **Disabled-refusal (flag-check first).** `if not branch_awareness_enabled(ctx.repo_root):` → `error("branch awareness is disabled; enable it in .plan-tool/config.json (or set PLAN_TOOL_BRANCH_AWARENESS=1).")` → `return 2`. This precedes every branch read/derive — the off-by-default leakage guard (plan "Risks → Flag-check leakage").
3. **Resolve the plan.** `target = _resolve_register_target(ctx, args.plan)` — the **file-must-exist** resolver (attach acts on a live plan, per the register/attach contract). On `None` → `error(f"no plan file matching {args.plan!r}. …")` → `return 2`. `slug = slug_from_filename(target)`.
4. **Empty-branch guard.** `branch = args.branch.strip()`; if falsy → `error("branch name is required.")` → `return 2`. (Front-loads what `set_binding` would otherwise raise.)
   - **Do not run `project_config._is_valid_ref` on the override branch.** `_is_valid_ref` mandates a `/` (it guards *derived* `<prefix><slug>` names); an arbitrary override like `JIRA-1` is legal and must not be rejected. The override is stored verbatim; git enforces ref validity at checkout time.
5. **Compute classification inputs once** (read-once-pass-down): `prefixes = branch_prefixes(ctx.repo_root)`; `registered = {e.slug for e in ctx.entries}` (the already-loaded `PlanToolContext.entries`, each `plan_tool/locator.py:PlanEntry.slug`).
6. **Ownership / collision lookup.** `owner = branch_owner(ctx.repo_root, branch, registered, prefixes)` — the single git-config-reading lookup (consults `reverse_binding` then `convention_owner`). Branch on the verdict:
   - **No collision** — `owner is None` or `owner.slug == slug`: bind directly. Wrap loud: `try: set_binding(ctx.repo_root, slug, branch) except BranchBindingError as exc: error(str(exc)); return 1`. On success `success(f"bound {slug} → {branch}")`; `return 0`. (`set_binding` writes `git config --local`, not the working tree, so the plain bind needs no clean-tree gate.)
   - **Ad-hoc collision (hard refuse)** — `owner.kind == OWNER_AD_HOC and owner.slug != slug`: another plan holds an *explicit* binding to this branch (a one-branch-per-plan desync the user must resolve, not auto-rewrite). `error(f"{branch} is already attached to plan {owner.slug!r}; run 'detach-branch {owner.slug}' first or choose another branch.")` → `return 2`. No re-home (re-home is reserved for structural convention collisions).
   - **Convention-name collision (warn + re-home)** — `owner.kind == OWNER_CONVENTION and owner.slug != slug`: proceed to the re-home path below.

#### Re-home path (convention collision)

- **Strong-warn.** `warn(f"{branch} is the convention branch of registered plan {owner.slug!r}; attaching {slug} there would let two plans claim it.")`.
- **Consent gate** (mirror `_prompt_remove_missing`'s `-y` / TTY / non-TTY contract; re-home is a branch *mutation*, so it never proceeds unattended without `-y`):
  - `args.yes` true → proceed.
  - Non-interactive (`not sys.stdin.isatty()`) without `-y` → print a hint to stderr (`"re-run with -y to re-home {slug} onto its own branch from {branch}"`) and `return 2` (the requested attach did not complete).
  - Interactive TTY → `import builtins` body-local; prompt `f"Re-home {slug} onto its own branch from {branch}? [y/N]: "`; on anything but `y`/`yes` (or `EOFError`/`KeyboardInterrupt`) → `"left unchanged."` to stderr and `return 2`.
- **Clean-tree gate** (only on this mutating path — never unconditional): `if working_tree_dirty(ctx.repo_root): error("re-home needs a clean working tree (commit or stash first)."); return 2`. Reuse the module's already-imported `working_tree_dirty` (the same reader `cmd_sweep --commit` gates on).
- **Compute the re-home target.** `rehome = derive_branch(slug, prefixes)` — the plan's own primary-prefix convention name (`plan/<slug>`).
- **Capture the invocation branch first** (before any switch): `invocation = current_branch(ctx.repo_root)` (step 2) — the branch `attach-branch` was run on, so a mid-composition failure can restore it.
- **Create-from-existing, reuse-if-exists** (gate → mutate). There is no `git switch -c <new> <start>` primitive, so branch *from* the colliding branch via a two-step switch-then-create, all through the step-2 `(rc, tail)` never-raise mutators:
  - `if branch_exists(ctx.repo_root, rehome):` the plan's branch already exists → `rc, tail = checkout_existing_branch(ctx.repo_root, rehome)` (switch to it; nothing to carry).
  - `elif branch_exists(ctx.repo_root, branch):` switch to the colliding branch first, then create the re-home branch from its HEAD (carries the work): `rc, tail = checkout_existing_branch(ctx.repo_root, branch)`; on `rc == 0`, `rc, tail = create_and_checkout_branch(ctx.repo_root, rehome)`.
  - `else:` the colliding name is a registered plan's convention name but not a *local* branch — nothing to carry; create `rehome` from current HEAD: `rc, tail = create_and_checkout_branch(ctx.repo_root, rehome)` and note "no local {branch} to carry from".
  - On any `rc != 0` → **best-effort-restore the invocation branch before returning** (the `elif`'s `create_and_checkout_branch` can fail *after* its `checkout_existing_branch(branch)` already switched away from `invocation`, stranding the developer on the colliding branch): `if invocation and invocation != current_branch(ctx.repo_root): checkout_existing_branch(ctx.repo_root, invocation)` (best-effort, ignore its rc), then `error(f"{tail}; restored branch {invocation}")` → `return 2` (no binding persisted — the irreversible step failed before persist). The report names both the failure and the branch it was restored to.
- **Persist last.** `try: set_binding(ctx.repo_root, slug, rehome) except BranchBindingError as exc: error(str(exc)); return 1`. `success(f"re-homed {slug} → {rehome} (from {branch})")`; `return 0`.
  - **Binding `slug → derive_branch(slug)` is deliberate, not redundant:** it records that the attach happened and pins the explicit intent even though `expected_branch` would derive the same name; harmless if later read as override == derived.

### `cmd_detach_branch(args) -> int`

1. **Context + manifest-mode guard** — identical shape to `cmd_attach_branch` (`return 2` in directory mode).
2. **Disabled-refusal** — identical (`return 2`).
3. **Resolve the plan via `_resolve_deregister_target(ctx, args.plan)`** — the **need-not-exist-on-disk** resolver (detach acts on an existing/known entry whose file may have moved, matching `cmd_deregister`). On `None` → `error(f"no registered plan matching {args.plan!r}. …")` → `return 2`. `slug = slug_from_filename(target)`.
4. **Clear, quiet.** `if clear_binding(ctx.repo_root, slug):` → `success(f"cleared branch override for {slug} (the branch on disk was left in place)")`; else → `info(f"no branch override to clear for {slug}")`. `return 0` either way. `clear_binding` never raises and treats an absent binding as a satisfied no-op — an idempotent `detach-branch` retry is always `0`. **Never deletes the branch** (plan "Out of scope → No branch deletion").

### `register()` additions

- **Reuse the local `yes_parent`** already built in `register()`. Add `attach-branch` with `parents=[yes_parent]` (needs `-y` for the re-home consent); `detach-branch` needs no `-y` (quiet, no prompt).
- `attach-branch`: positional `plan` (help: "path or slug of a registered plan") and positional `branch` (help: "branch to attach (arbitrary; stored as an untracked local-git-config override)"); help string naming the disabled-refusal and convention-collision re-home.
- `detach-branch`: positional `plan`; help string noting it clears the override and leaves the branch in place.
- **Extend the returned dispatch dict** with `"attach-branch": cmd_attach_branch, "detach-branch": cmd_detach_branch`.

### The other three wiring sites

- **`plan_tool/cli/app.py`** — add `cmd_attach_branch`, `cmd_detach_branch` to the existing `from plan_tool.cli.manifest import (...)` tuple so `__init__.py`'s `dir(app)` mirror loop re-exports `plan_tool.cli.cmd_attach_branch` / `…cmd_detach_branch` (the surface `test_package_surface.py` and the `__all__` entries assert).
- **`plan_tool/cli/parser.py`** — append `"attach-branch"`, `"detach-branch"` to the end of `CANONICAL_COMMAND_ORDER`. `_reorder_subcommands` sorts by `_canonical_index`, so they render immediately after `annotate` and before the non-canonical aliases (`root`, `split`, …) that sort to the tail.
- **`plan_tool/cli/__init__.py`** — add two lines to the **State management** catalog group (after the `sweep` line), e.g. `plan-tool attach-branch <plan> <branch>  Attach a plan to an ad-hoc branch (untracked local git config; off unless branch awareness is enabled).` and the `detach-branch` counterpart; add `"cmd_attach_branch"`, `"cmd_detach_branch"` to `__all__`.

### Foundational logic and shared locations

- **Foundational logic:** "two registered-plan, slug-keyed verbs that set/clear the git-config override, refusing when branch awareness is off and re-homing on a convention-name collision."
- **The disabled-refusal flag-check** (`branch_awareness_enabled` first) is the same pattern as the step-5 run guard (`plan_tool/cli/run_cmd.py:_preflight_branch_guard`) and the step-7 create gate (`plan_tool/cli/authoring.py`) — three different commands, one rule; not consolidatable (different commands, different surrounding flow).
- **Ownership/collision logic is not duplicated here** — it lives once in `plan_tool/branch_ownership.py:branch_owner` / `convention_owner` (step 4); this handler consumes the verdict and maps it to UX.
- **Branch creation/switch primitives** live once in `plan_tool/cli/gitcommit.py` (step 2); the re-home reuses `create_and_checkout_branch` / `checkout_existing_branch` under its own clean-tree gate (the primitives stay policy-free).
- **The `subprocess.run([...], cwd=…, stdin=DEVNULL, capture_output=True, text=True)` git-shell shape** duplicated across `gitcommit.py`, `run_cmd.py`, `branch_binding.py`, and `bench.py` is a known cross-module consolidation `detail` cannot mint → see [Deferred](#deferred).

## Tests

All cases land in `tests/cli/test_manifest_cmds.py` (extends the existing characterization file). Build the namespace through the real parser — `args = build_parser().parse_args(repo.argv("attach-branch", "demo", "feat/x"))` — then call `cmd_attach_branch(args)` directly, monkeypatching the branch symbols **imported into `plan_tool.cli.manifest`** (`branch_awareness_enabled`, `branch_owner`, `set_binding`, `clear_binding`, `working_tree_dirty`, `branch_exists`, `checkout_existing_branch`, `create_and_checkout_branch`, `derive_branch`) to inject each scenario without a real git-config store (the `registered_plan`/`tmp_repo` fixtures create only a stub `.git` dir). Build a `BranchOwner` by hand (`from plan_tool.branch_ownership import BranchOwner, OWNER_AD_HOC, OWNER_CONVENTION`) to feed `branch_owner`'s return. Drive the TTY/`-y` decision by patching `sys.stdin` (a `_FakeStdin`) / `builtins.input`, as the existing sweep-prompt tests do. Enumerate the tests **with** the implementation; the green-before-done gate: every case below passes before this step is complete.

### Disabled-refusal (the distinctive behavior)
- `test_attach_refuses_when_disabled` — no config (default off): `cmd_attach_branch` returns `2`, names "disabled", and `set_binding` is never called.
- `test_detach_refuses_when_disabled` — same for `cmd_detach_branch`; `clear_binding` never called.

### Mode / resolution refusals
- `test_attach_refuses_directory_mode` — `--plans-dir` set → returns `2` with the manifest-mode message.
- `test_attach_unresolvable_plan_returns_2` — enabled, unknown plan slug → `2`.
- `test_attach_empty_branch_returns_2` — enabled, blank branch positional → `2`, no `set_binding`.

### Plain attach (no collision)
- `test_attach_binds_when_no_owner` — enabled, `branch_owner` → `None`: calls `set_binding(repo_root, "demo", "feat/x")`, returns `0`, no clean-tree gate consulted.
- `test_attach_binds_when_self_owned` — `branch_owner` → owner whose slug == this plan: binds, returns `0`.
- `test_attach_surfaces_set_binding_error` — `set_binding` raises `BranchBindingError`: returns `1`, message surfaced.
- `test_attach_does_not_validate_override_ref` — branch `"JIRA-1"` (no `/`): binds successfully (no `_is_valid_ref` rejection).

### Ad-hoc collision (hard refuse)
- `test_attach_refuses_adhoc_bound_elsewhere` — `branch_owner` → `BranchOwner("other", OWNER_AD_HOC)`: returns `2`, message names `other` and `detach-branch`; no mutator called.

### Convention collision (warn + re-home)
- `test_attach_rehome_requires_consent_noninteractive` — `OWNER_CONVENTION` owner ≠ plan, non-TTY, no `-y`: returns `2`, no branch mutator called.
- `test_attach_rehome_refuses_dirty_tree` — consent via `-y`, `working_tree_dirty` → `True`: returns `2`, no mutator called.
- `test_attach_rehome_creates_from_existing` — `-y`, clean tree, `branch_exists(rehome)` → `False`, `branch_exists(colliding)` → `True`: calls `checkout_existing_branch(colliding)` then `create_and_checkout_branch(rehome)`, then `set_binding(slug, rehome)`, returns `0`.
- `test_attach_rehome_reuses_existing_rehome_branch` — `branch_exists(rehome)` → `True`: calls `checkout_existing_branch(rehome)` only (no create), binds, returns `0`.
- `test_attach_rehome_mutator_failure_no_bind` — a mutator returns `(rc!=0, tail)`: returns `2`, `set_binding` never called (no orphan binding).

### Detach
- `test_detach_clears_existing` — enabled, `clear_binding` → `True`: returns `0`, success message.
- `test_detach_quiet_when_absent` — `clear_binding` → `False`: returns `0`, info message, never raises.
- `test_detach_unresolvable_plan_returns_2` — unknown slug → `2`.

### Parser surface (the step's `gate`)
- `test_attach_detach_registered` — `build_parser()` dispatch (via `assemble`) maps `attach-branch` / `detach-branch` to the two handlers, and each subparser's `format_help()` is non-empty (mirrors `gate: attach-branch --help … && detach-branch --help …`).
- `tests/cli/test_package_surface.py` stays green after regenerating `package_surface_help.golden.txt` (`UPDATE_CLI_GOLDEN=1`); `test_help_lists_every_subcommand` and `test_register_returns_dispatch_for_every_subcommand` pick up the two verbs automatically — no edit to that file.

### Test-creation order (feature step)
- **This is a feature step — new behavior.** Write each case above alongside the handler/wiring it covers.
- **Green-before-done gate:** every new test passes (`uv run pytest tests/cli/test_manifest_cmds.py tests/cli/test_package_surface.py -q`) **and** the full non-integration suite stays green (`uv run pytest -m "not integration" tests/ -q`) — the disabled-by-default state means no existing test regresses.

## Acceptance criteria

- `attach-branch` / `detach-branch` parse, dispatch, and `--help` exit 0 (the frontmatter `gate`).
- With branch awareness off (every repo today), both verbs return non-zero (`2`) with a "disabled — enable in `.plan-tool/config.json`" message and touch no git config.
- Enabled, no collision: `attach-branch P <branch>` calls `set_binding(repo_root, slug(P), <branch>)` and returns `0`; an arbitrary `<branch>` with no `/` (e.g. `JIRA-1`) is accepted.
- Enabled, `<branch>` already ad-hoc-bound to another plan Q: returns non-zero naming Q, binds nothing.
- Enabled, `<branch>` is registered plan R's convention name: strong-warns; without consent (`-y`/TTY-yes) binds nothing and returns non-zero; with consent on a clean tree it creates `derive_branch(slug(P))` from `<branch>` (reusing it if already present), binds P to that re-home name, and returns `0`; refuses non-zero on a dirty tree.
- Re-home mid-composition failure (`checkout_existing_branch(<branch>)` succeeds, then `create_and_checkout_branch(rehome)` fails) → best-effort-restores the invocation branch before returning `2`, persists no binding, and the error names both the failure and the restored branch (the developer is never stranded on the colliding branch).
- `detach-branch P` returns `0`, clearing the override when present and a quiet no-op (still `0`) when absent; never deletes a branch.
- `plan-tool --help` lists `attach-branch` and `detach-branch` (after `annotate`); `tests/cli/test_package_surface.py` passes against the regenerated golden.
- Every test in `tests/cli/test_manifest_cmds.py` passes; the full non-integration suite stays green.

## References

- [Git - git-config Documentation](https://git-scm.com/docs/git-config) — `--local` semantics behind the `set_binding` / `clear_binding` store these verbs drive (step 3); confirms the override is untracked and branch-independent.
- [Git - git-branch Documentation](https://git-scm.com/docs/git-branch) — `git switch` / `git switch -c` semantics behind the clean-tree-gated, reuse-if-exists re-home creation (via step 2's `checkout_existing_branch` / `create_and_checkout_branch`).
- [Git - git-check-ref-format Documentation](https://git-scm.com/docs/git-check-ref-format) — why the *override* branch is stored verbatim (not run through `_is_valid_ref`, which mandates a `/` for derived `<prefix><slug>` names).

## Deferred

- **SKILL.md / RUNBOOK / README catalog rows for the two verbs** — step 8 (`Document branch-awareness across the six operator surfaces`, `depends_on: 5,6,7`) owns the docs surfaces; this step edits only the `__init__.py` in-code catalog that feeds `--help`.
- **Switching the developer onto an arbitrary override branch on a plain (non-collision) `attach-branch`** — attach records the binding only; landing on the branch is the run guard's `--switch-branch` (step 5) or a manual checkout. Auto-switching every plain attach is an additive enhancement, not in this footprint.
- **Re-homing on an *ad-hoc* collision** — only convention-name collisions re-home (the structural-ownership case the plan specifies); an explicit binding to another plan is a hard refuse, leaving conflict resolution to the operator.
- **Consolidating the duplicated `subprocess.run` git-shell shape** across `plan_tool/cli/gitcommit.py`, `plan_tool/cli/run_cmd.py`, `plan_tool/branch_binding.py`, and `plan_tool/bench.py` — a cross-module refactor `detail` cannot mint; route to reconcile.
- **Sourcing `registered_slugs` other than from `ctx.entries`** — the collision check reads the already-loaded `PlanToolContext.entries`; no fresh manifest read is added.
