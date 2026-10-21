> **Auto-archived**: this plan was swept on 2026-06-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 7 — Add a create-time namespace-collision warning to `cmd_create` that disambiguates an unowned derived branch

## Summary

Adds a branch-awareness preflight to `plan_tool/cli/authoring.py:cmd_create` — a new module-private helper `_create_branch_collision_gate` plus one guarded call site after the repo root is finalized. When branch-awareness is **enabled** and the new plan's derived branch (`plan/<slug>`) **already exists with no local owner** (no registered plan claims it via convention, no ad-hoc binding points at it), the gate strong-warns and, on continue, creates the **first-free disambiguated branch** (`plan/<slug>-2`, then `-3`, …) **FROM the default branch** and **ad-hoc-binds the new plan to it** so the new plan's work lands on a clean, non-colliding branch the run guard recognizes as owned. The load-bearing decision is **flag-check-first inertness**: with branch-awareness off (every repo today) the gate is a byte-for-byte no-op, and on a non-git / detached-HEAD tree it short-circuits explicitly when `current_branch` returns `None` (mirroring step 5's guard) so the restore-on-failure path always has a real invocation branch to return to. It composes step 1's `branch_awareness_enabled` / `branch_prefixes` / `derive_branch`, step 2's `branch_exists` / `default_branch` / `checkout_existing_branch` / `create_and_checkout_branch`, step 3's `set_binding`, and step 4's `branch_owner` over a registered-slug set the caller reads once. On green, an off-config create is unchanged, a collision with `-y` auto-creates `plan/<slug>-2` from default and binds the plan to it, and a declined collision returns rc 2 without touching the tree or invoking claude. If a downstream `create_plan`/`append_to_manifest` failure follows a disambiguating switch, `cmd_create` best-effort clears the binding and restores the invocation branch so no orphan binding or stranded checkout survives an aborted author.

## Table of Contents

- [Why](#why) — what the collision protects against and why it lives in `cmd_create`
- [Files (creates vs edits)](#files-creates-vs-edits) — the two edited files
- [Implementation](#implementation) — the gate helper, its seam, the collision predicate, the disambiguation, and the create-from-default composition
- [Tests](#tests) — per-behavior unit/component cases and the green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — observable behaviors a reviewer can check
- [References](#references) — git docs underpinning the branch reads/creation
- [Deferred](#deferred) — remote scan and cross-command consolidation left out

## Why

`plan-tool create` derives a plan's branch name from its slug (`plan/<slug>`), but nothing checks whether that name is already taken by *unrelated* work before the new plan adopts it. If a developer (or a stale local checkout) already has a `plan/<slug>` branch that **no registered plan owns**, the new plan silently shares a namespace name with foreign work — and the step-5 run guard would later treat that branch's contents as ambiguous. This step closes that gap at authoring time: it detects the orphan-branch collision, makes the developer acknowledge it, and on consent moves the new plan onto a fresh disambiguated branch cut from the default branch, leaving the foreign `plan/<slug>` untouched. Keeping the check in `cmd_create` (not in `create_plan` or a shared resolver) scopes it to exactly the one command that mints a new slug, and placing it before `RunLogWriter.start` means a declined collision opens no run log and writes no plan.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/authoring.py`
    - Add `_create_branch_collision_gate(args, *, repo_root, slug, registered_slugs, input_fn=input) -> Optional[int]` — the preflight helper.
    - Add four module-top imports: step 1's `branch_awareness_enabled` / `branch_prefixes` / `derive_branch` from `plan_tool.project_config`; step 2's `branch_exists` / `default_branch` / `current_branch` / `checkout_existing_branch` / `create_and_checkout_branch` from `plan_tool.cli.gitcommit` (alongside the two existing aliased single-line imports at `authoring.py:135–136` — `commit_all as _commit_all` and `working_tree_dirty as _working_tree_dirty`); step 3's `set_binding` / `clear_binding` from `plan_tool.branch_binding`; step 4's `branch_owner` from `plan_tool.branch_ownership`. Add `from plan_tool.locator import load_manifest_plan_paths, slug_from_filename` (extend the existing `from plan_tool.locator import …` block).
    - Add one guarded call site inside `cmd_create`, immediately after `repo_root = chosen` and **before** `RunLogWriter.start`.
  - `tests/cli/test_authoring_cmds.py`
    - Add a `TestCreateBranchCollisionGate` class (helper-level unit cases against a `tmp_path` git repo) and one component case driving `main(["create", …])` for the off-config no-op and the declined-collision early return.

## Implementation

All code lands in `plan_tool/cli/authoring.py`. The gate is a **flag-check-first preflight** that performs an irreversible git mutation only on the collision-and-consent path; every refusal-capable check runs before that mutation so a rejected request leaves no orphan branch.

### The call site in `cmd_create`

- **Place the call after `repo_root = chosen` and before `RunLogWriter.start`.** This is the same seam the run-root umbrella/confirm logic finalizes (`repo_root = chosen` in the `if not explicit_root:` block) and is reached only after the two early branches that must skip branch logic. **The call must sit at function-body indentation — dedented out of the `if not explicit_root:` block (which ends at `authoring.py:323–331`), not nested inside it.** `repo_root = chosen` lives *inside* that block, so an implementer following "immediately after `repo_root = chosen`" literally would indent the gate into the block and silently skip it for the explicit-root path (`--repo-root` / `PLAN_TOOL_REPO_ROOT`), which never enters the block; the "before `RunLogWriter.start`" pin is the disambiguator. The early branches the gate runs after:
  - `--reprocess` early-returns via `_cmd_create_reprocess` at the top of `cmd_create` — never reaches the gate.
  - `resolve_create_slug` has already set `args.slug` to a concrete slug (it invokes claude only when the slug is omitted; a caller passing an explicit slug reaches the gate with no backend call).
- **Build the registered-slug set once and pass it down** (read-once-pass-down): `registered = {s for p in load_manifest_plan_paths(repo_root, manifest_path=args.manifest) if (s := slug_from_filename(p)) }`. The gate stays pure of manifest I/O and is unit-testable with a literal set.
- **Short-circuit on a non-None return:** `gate_rc = _create_branch_collision_gate(args, repo_root=repo_root, slug=args.slug, registered_slugs=registered)`; `if gate_rc is not None: return gate_rc`. A `None` return means "proceed with create" (possibly after a branch switch the gate already performed); an `int` means "abort now with this rc" — so no `RunLogWriter.start`, no `create_plan`, no `append_to_manifest` runs on the abort path. When the gate proceeded *after* switching+binding, it records the rollback context on `args` (see "Downstream-authoring rollback" below) so `cmd_create` can undo the binding and restore the invocation branch if the downstream author fails.

### `_create_branch_collision_gate` — control flow

Order every refusal-capable check before the irreversible checkout/create (atomic-from-the-user's-side):

1. **Flag check (inert no-op when off).** `if not branch_awareness_enabled(repo_root): return None`. With no config — every repo today — the gate does zero git I/O and `cmd_create` is byte-for-byte unchanged.
2. **Read the current branch once; no-op when undeterminable.** `invocation = current_branch(repo_root)` (step 2). `if invocation is None: return None` — non-git or detached HEAD (folded into one sentinel by step 2's `git symbolic-ref`) short-circuits before any collision/ownership work, exactly as step 5's guard does. This is load-bearing: the restore-on-failure path below (`checkout_existing_branch(repo_root, invocation)`) needs a real branch to return to, so the gate must never proceed past here with `invocation is None`.
3. **Derive the canonical branch.** `prefixes = branch_prefixes(repo_root)`; `derived = derive_branch(slug, prefixes)` (step 1's producer uses the **primary** prefix → one canonical name).
4. **Collision predicate.** `if not branch_exists(repo_root, derived): return None`. `branch_exists` scopes to local `refs/heads`, so a name-free repo proceeds untouched.
5. **Ownership check.** `if branch_owner(repo_root, derived, registered_slugs, prefixes) is not None: return None`. A branch a registered plan already owns (convention-registered or ad-hoc-bound) is **not** a foreign collision — leave it to the slug-uniqueness path / run guard. Only an **unowned** existing branch (orphan) is the namespace collision this step warns on.
6. **Strong-warn + consent.** `warn(...)` naming `derived` and stating it exists but is owned by no registered plan. Then mirror `_confirm_repo_root`'s posture: `proceed = getattr(args, "yes", False) or not sys.stdin.isatty()` else prompt `input_fn("branch <derived> already exists and is unowned; [c]reate a disambiguated branch from the default branch, or [a]bort? [c/A] ")` and accept `{"c","create","y","yes"}`. **Decline → `return 2`** (collision rc, matching `cmd_create`'s other usage/collision returns) with nothing mutated.
7. **Resolve the anchor (graceful degradation).** `base = default_branch(repo_root)` (step 2: `PLAN_TOOL_DEFAULT_BRANCH` env → `origin/HEAD` → `None`). **Verify the resolved default actually resolves before using it:** `default_branch` returns a `PLAN_TOOL_DEFAULT_BRANCH` value verbatim (non-`None`) even when that branch does not exist, so treat the anchor as undeterminable when `base is None` **or** `not branch_exists(repo_root, base)` (an env-named default that does not resolve counts as undeterminable exactly like the `None` case, and must not reach the `checkout_existing_branch(repo_root, base)` compose step and hard-abort with a non-zero rc). On either undeterminable case: `warn(...)` — a **strong warning, never a quiet `info` note** — that the default branch is undeterminable so disambiguation is skipped, protection was skipped, and the foreign `<derived>` is now left silently convention-owned (Tier-2) by the new plan, re-exposing the run-on-foreign-work hazard the gate exists to prevent; then **`return None`** (proceed with a plain create on the current branch, no ad-hoc binding) — blocking create entirely would be unhelpful where no anchor exists, and a misconfigured env var must fail safe rather than abort.
8. **Clean-tree refusal (before any switch).** `if _working_tree_dirty(repo_root): error(...); return 2`. Switching branches needs a clean tree; reuse the module's existing `_working_tree_dirty` (the `gitcommit.working_tree_dirty` re-export) so this gate agrees with the rest of `authoring.py` on "dirty". This check sits with the other refusals, before the mutation.
9. **First-free disambiguation.** Iterate `n` from 2 upward, `candidate = f"{derived}-{n}"`, and pick the **first** for which `branch_exists(repo_root, candidate)` is `False`. Cap the scan (e.g. `n <= 100`) and `error` + `return 1` if exhausted (pathological).
10. **Create FROM the default branch (composed, no create-from-start primitive).** `gitcommit` exposes only switch + create-from-HEAD, so compose, using the `invocation` branch captured at step 2 so a mid-composition failure can restore it:
   - `invocation` is the branch the developer ran `create` on (read once at step 2, guaranteed non-`None` here), recorded before any switch.
   - `rc, tail = checkout_existing_branch(repo_root, base)`; `if rc != 0: error(tail); return 1`. (This first switch has not yet left `invocation`, so there is nothing to restore on its failure.)
   - Gated on that `rc == 0`: `rc2, tail2 = create_and_checkout_branch(repo_root, candidate)` (`git switch -c` from the just-switched default HEAD). **On failure the composition has already switched away from `invocation` onto `base`, so best-effort-restore the invocation branch before returning** — a failed create must never strand the developer on the default branch with no plan: `if rc2 != 0:` `if invocation: checkout_existing_branch(repo_root, invocation)` (best-effort, ignore its rc), then `error(f"{tail2}; restored branch {invocation}")` and `return 1`. The report names both the create failure and the branch it was restored to.
   - **Bind the new plan to its disambiguated branch.** `set_binding(repo_root, slug, candidate)` (step 3) records the ad-hoc override so step 4's `expected_branch(slug)` resolves to `candidate` — not the foreign derived `plan/<slug>` — and the step-5 run guard recognizes `candidate` as Tier-1 owned when the developer later runs the plan from it. Without this the disambiguation would undo itself: the guard would Tier-4-nudge from `candidate` back onto the foreign `plan/<slug>` the disambiguation existed to avoid.
   - **Record the rollback context** for the downstream author: `args._branch_collision_rollback = (invocation, slug, candidate)`. This is the only path that sets the attribute; every refusal/no-op return above leaves it unset.
   - `success(f"created disambiguated branch {candidate} from {base} and bound {slug} to it")`; `return None` so `cmd_create` proceeds to write the plan on `candidate`.

### Downstream-authoring rollback (the `create_plan`-fails case)

The gate's switch+create+bind at step 9 is an **irreversible mutation that completes before `cmd_create` authors the plan** — `create_plan` (a claude invocation) and `append_to_manifest` both run *after* the gate returns `None`, and either can fail or raise. Without recovery a failed author would strand the developer on `candidate` with an ad-hoc binding to `candidate` but no plan file ever written — an orphan binding the step-5 run guard would later treat as Tier-1 ownership of an empty branch. Sequence the mutation against that downstream failure so a failed author leaves no orphan binding and no stranded checkout:

- **`cmd_create` wraps the downstream author.** Guard the `create_plan` → `append_to_manifest` span so that on a raised exception **or** a non-success result, when `args._branch_collision_rollback` is set (only the disambiguation path sets it), `cmd_create` best-effort recovers *before* re-surfacing the original failure: `clear_binding(repo_root, slug)` (step 3 — removes the orphan binding so `expected_branch(slug)` falls back to the derived name and the run guard no longer sees `candidate` as Tier-1 owned) and `checkout_existing_branch(repo_root, invocation)` (step 2, best-effort, ignore its rc — un-strands the developer). Re-raise / return the original authoring rc unchanged; the rollback never masks the underlying failure.
- **Report, don't silently orphan, the residual branch.** The tool never deletes branches (plan "Out of scope → No branch deletion"; step 2 ships no delete primitive), so the now-unbound `candidate` ref — an empty branch at `base`'s HEAD — is left in place but **named in the failure report** ("authoring failed; cleared binding `<slug>` and restored branch `<invocation>`; left empty branch `<candidate>` — remove it manually if unwanted") rather than left hidden. A later create takes the next first-free suffix.
- **Mirror the gate's own partial-failure posture.** This extends the same best-effort-restore pattern step 9 already applies to its internal `create_and_checkout_branch` failure outward to the create-then-author span, so both the gate-internal and the downstream failure leave the developer on `invocation` with no dangling binding.

### Non-obvious decisions

- **Verify cross-step signatures at HEAD before wiring them.** The names and arities above (`project_config.branch_awareness_enabled` / `branch_prefixes(repo_root)` / `derive_branch(slug, prefixes)`, `gitcommit.branch_exists` / `default_branch` / `checkout_existing_branch` / `create_and_checkout_branch`, `branch_binding.set_binding(repo_root, slug, branch)`, `branch_ownership.branch_owner(repo_root, derived, registered_slugs, prefixes)`) describe steps 1/2/3/4 as designed, not as shipped. Before importing them, grep the landed modules and pass only what the exported signatures actually accept — reconcile the call sites here if a name or arity differs.
- **Non-git / detached HEAD short-circuits via the `current_branch is None` check (step 2), not via `branch_exists`.** `branch_exists` (`git show-ref --verify refs/heads/<name>`) returns `True` for an existing local branch regardless of HEAD state, so it does **not** fold detached HEAD to `False`; the explicit `invocation is None` no-op is what keeps the gate inert on a detached HEAD that happens to have an existing `plan/<slug>`, and guarantees the restore path has a branch to return to.
- **Disambiguate off `derived`, not off `slug`** — the suffix lands on the *branch* name (`plan/<slug>-2`), preserving the configured prefix; do not re-derive from `f"{slug}-2"` (that would re-apply prefix logic and is harder to read).
- **No new flags.** The step's footprint is the warning + disambiguation behind the existing `-y` / TTY posture; it adds no `create` subparser argument. (The `--force` / `--allow-non-default-branch` flags named in older accumulated lessons belong to a **superseded** create-gate design — confirmed absent from `cmd_create`'s subparser — and are not added here.)

## Tests

All cases land in `tests/cli/test_authoring_cmds.py`, following its split-proof conventions (import from `plan_tool.cli`, drive helpers directly or `main(argv)` on a temp repo; script TTY via `sys.stdin` / `input_fn`). The branch side-effects are asserted at the **helper** level against a real `tmp_path` git repo (so `create_plan`/claude is never reached); the off-config and declined paths also get a `main([...])` component case. Each test is written with the implementation; **all must be green before the step is done.**

`TestCreateBranchCollisionGate` (helper unit, `tmp_path` git repo with `.plan-tool/config.json` enabling branch-awareness unless noted):

- `test_off_config_is_noop` — branch-awareness absent → returns `None`, no git reads, derived branch never inspected.
- `test_non_git_or_detached_is_noop` — `current_branch` → `None` (non-git `tmp_path` without `.git`, or detached HEAD) → returns `None` at the step-2 short-circuit even when `branch_exists(derived)` is `True`, never reaching the ownership/disambiguation work.
- `test_no_existing_branch_proceeds` — derived branch absent → returns `None`, no warning.
- `test_existing_owned_branch_proceeds` — `plan/<slug>` exists and `<slug>` is in `registered_slugs` (convention owner) → returns `None` (not a foreign collision).
- `test_unowned_collision_declined_returns_2` — `plan/<slug>` exists, unowned, `input_fn` returns `"a"` → returns `2`, no branch created, tree untouched.
- `test_unowned_collision_continue_creates_first_free` — collision + consent → creates `plan/<slug>-2` from the default branch, leaves `plan/<slug>` intact, current branch is `plan/<slug>-2`, returns `None`.
- `test_disambiguated_branch_is_bound` — collision + consent → `set_binding` records `<slug> → plan/<slug>-2`, so `expected_branch(repo_root, slug)` resolves to the disambiguated branch, not the foreign derived `plan/<slug>`.
- `test_disambiguation_skips_taken_suffixes` — `plan/<slug>` and `plan/<slug>-2` already exist → creates `plan/<slug>-3`.
- `test_yes_auto_continues` — `args.yes=True`, non-interactive → no prompt, disambiguated branch created, returns `None`.
- `test_dirty_tree_refuses` — collision + consent but uncommitted change → returns `2`, no checkout/create performed.
- `test_no_default_branch_skips_disambiguation` — `default_branch` is `None` (no `origin/HEAD`, env unset) → emits a strong warning (asserted on `warn`, not `info`) that protection was skipped and the foreign `<derived>` is now silently convention-owned, returns `None`, no branch created, no ad-hoc binding.
- `test_creates_from_default_not_current_head` — invoked while checked out on an unrelated branch with a distinct HEAD → the disambiguated branch's base commit equals the default branch's HEAD, not the invocation branch's.

Component (`main(["create", …])`, no claude):

- `test_main_create_off_config_unchanged` — without branch-awareness, an existing `plan/<slug>` branch does not alter create's behavior.
- `test_main_create_declined_collision_returns_2_no_plan` — branch-awareness on, collision, scripted decline → exit 2, no plan file written, no manifest entry, no claude invoked (halts before `create_plan`).
- `test_main_create_authoring_failure_rolls_back_binding` — branch-awareness on, unowned collision, consent so the gate switches to `candidate` and binds `<slug>`; `create_plan` stubbed to fail → the `<slug>` binding is cleared (`all_bindings` / `reverse_binding` no longer return `candidate`), the current branch is restored to the invocation branch, the leftover `candidate` branch still exists, and the original authoring rc is surfaced.

## Acceptance criteria

- `branch_awareness_enabled(repo_root)` `False` → `_create_branch_collision_gate` returns `None` having performed no git I/O; existing `create` tests pass unedited.
- Non-git / detached HEAD (`current_branch` → `None`) → gate returns `None` at the step-2 short-circuit, even when an existing local `plan/<slug>` would make `branch_exists` `True`; never raises.
- `branch_exists(repo_root, derive_branch(slug, prefixes))` `False` → gate returns `None`.
- Existing `plan/<slug>` owned by a registered plan → gate returns `None`.
- Existing **unowned** `plan/<slug>` + decline → gate returns `2`, no branch created, working tree unchanged.
- Existing unowned `plan/<slug>` + consent on a clean tree with a resolvable default branch → `plan/<slug>-N` (first free, N≥2) is created from the default branch's HEAD and checked out, the plan is ad-hoc-bound to it (`expected_branch(slug) == plan/<slug>-N`); gate returns `None`.
- Consent on a dirty tree → gate returns `2`, no checkout/create.
- Mid-composition failure (`checkout_existing_branch(default)` succeeds, then `create_and_checkout_branch(candidate)` fails) → gate best-effort-restores the invocation branch before returning `1`, and the error names both the create failure and the restored branch (the developer is never stranded on the default branch with no plan).
- Downstream-author failure after a disambiguating switch (`create_plan`/`append_to_manifest` raises or returns non-success) → `cmd_create` best-effort clears the `<slug>` binding and restores the invocation branch, names the leftover `candidate` branch in the failure report, and surfaces the original authoring rc unchanged (no orphan binding, developer not stranded).
- `main(["create", <slug>, "--from", <brief>])` with branch-awareness off and an existing `plan/<slug>` branch behaves identically to today.
- All `TestCreateBranchCollisionGate` and the two component cases pass under `uv run pytest tests/cli/test_authoring_cmds.py -q`.

## References

- [Git - git-switch Documentation](https://git-scm.com/docs/git-switch) — semantics of `git switch -c` / `git switch` underpinning `create_and_checkout_branch` and `checkout_existing_branch`.
- [Git - git-symbolic-ref Documentation](https://git-scm.com/docs/git-symbolic-ref) — how `default_branch` resolves `refs/remotes/origin/HEAD`, the anchor the disambiguated branch is cut from.
- [Git - git-check-ref-format Documentation](https://git-scm.com/docs/git-check-ref-format) — ref-name rules that `derive_branch` (step 1) already enforces for `plan/<slug>` and the `-N` suffix.
- [subprocess — Subprocess management (Python docs)](https://docs.python.org/3/library/subprocess.html) — return-code handling for the `(rc, tail)` git mutators this gate composes.

## Deferred

- **Remote-tracking namespace scan** — `branch_exists` checks local `refs/heads` only; detecting a collision against `origin/plan/<slug>` via step 2's `list_branches` is a possible enhancement, deferred.
- **Consolidating the three branch preflights** — this create-time collision gate, step 5's `_preflight_branch_guard` (current-vs-bound), and step 6's attach-branch collision handling share a flag-check-first skeleton but compare different branch pairs; unifying them is a cross-command refactor `detail` cannot mint → reconcile.
