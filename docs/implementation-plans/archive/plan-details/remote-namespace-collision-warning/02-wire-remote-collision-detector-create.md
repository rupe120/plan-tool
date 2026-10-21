> **Auto-archived**: this plan was swept on 2026-06-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Wire the remote-collision advisory into the create-time gate

## Summary

Extend `plan_tool/cli/authoring.py:_create_branch_collision_gate` so that when the new plan's derived `plan/<slug>` branch does **not** exist locally, the gate reads the offline branch list once and, if a pushed remote ref already matches the name, emits a warn-and-proceed advisory (names the colliding remote ref + an "as of your last fetch — no network performed" caveat) before returning `None`. This is a pure advisory tier: **no disambiguation, no ad-hoc bind, no checkout** — the create still proceeds on the invocation branch. The load-bearing decision is **where** the remote read sits: it replaces the unconditional `return None` in the no-local-branch path, so the existing local-unowned **disambiguation** and local-owned **defer** paths never read `list_branches` and never double-warn. On green, a `create` whose convention name is already claimed only as someone else's `origin/plan/<slug>` surfaces the collision instead of silently reserving a remotely-taken name. Builds directly on step 1, which adds the pure `remote_collisions` helper and gives the offline `list_branches` enumerator its first consumer.

## Table of Contents

- [Why](#why) — the silent-remote-collision gap this advisory closes
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files touched
- [Implementation](#implementation) — the advisory branch, its placement, and imports
- [Tests](#tests) — the three pinned behaviors plus the no-collision silent case
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors
- [References](#references) — the git docs grounding the offline read + staleness caveat
- [Deferred](#deferred) — what stays out of this step's footprint

## Why

- The create-time gate today only sees **local** refs. `_create_branch_collision_gate` calls `branch_exists(repo_root, derived)` (which scopes to `refs/heads/<name>` per `plan_tool/cli/gitcommit.py:branch_exists`) and returns `None` the moment no local branch matches. A derived name that already exists solely as a pushed `origin/plan/<slug>` is reserved silently — the developer authors a plan whose convention branch name is already taken on the remote, and nothing says so.
- Step 1 closes the detection half: it adds `plan_tool/cli/gitcommit.py:remote_collisions` (pure, ref-list in / colliding full short refs out) and makes the offline `list_branches` enumerator its first consumer. This step closes the wiring half — read `list_branches` once at the no-local-branch decision point and warn when a remote ref collides.
- This is **advisory only** (warn-and-proceed). A remote-tracking ref is just "what the remote looked like at last fetch"; the developer may legitimately want the name anyway, and the gate performs no network. Per the accumulated advisory-gate rule, a gate whose purpose is to *inform* degrades to proceed — it never refuses or mutates on this path.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/authoring.py` — extend the existing `from plan_tool.cli.gitcommit import (...)` block (currently `branch_exists`, `checkout_existing_branch`, `create_and_checkout_branch`, `current_branch`, `default_branch`) to also import `list_branches` and `remote_collisions`; add the remote-advisory branch inside `_create_branch_collision_gate`'s no-local-branch path.
  - `tests/cli/test_authoring_cmds.py` — add a `TestCreateBranchRemoteCollisionGate` class (helper-level, mirroring `TestCreateBranchCollisionGate`) covering the remote-only warn-and-proceed, the local-collision-does-not-read-remote case, the flag-off no-read case, and the remote-no-collision silent case.

## Implementation

### `plan_tool/cli/authoring.py` — `_create_branch_collision_gate`

- **Anchor the change on the no-local-branch early return.** The gate's current order is: `branch_awareness_enabled` check → `current_branch` (`None` ⇒ return) → `prefixes = branch_prefixes(...)` / `derived = derive_branch(slug, prefixes)` → **`if not branch_exists(repo_root, derived): return None`** → `branch_owner(...) is not None` defer → `warn(...)` + disambiguation. The remote advisory replaces the bare `return None` in the `not branch_exists(...)` block.

- **New advisory branch (inside `if not branch_exists(repo_root, derived):`):**
  - Read the offline enumerator once: `collisions = remote_collisions(list_branches(repo_root), derived, prefixes)`. Reuse the already-computed `derived` and `prefixes` — do **not** re-read config or re-derive.
  - When `collisions` is non-empty, `warn(...)` naming the colliding remote ref(s) (`", ".join(collisions)` — `remote_collisions` already returns the sorted full short refs, e.g. `origin/plan/<slug>`), with the **"as of your last fetch — no network performed"** caveat and a note that the create proceeds on the invocation branch (suggest `git fetch` to refresh / a distinct slug if the remote work is unrelated).
  - `return None` regardless of whether `collisions` is empty — this path always proceeds.

- **Why this placement, not "after both local checks":** the advisory must fire **only** when there is no local branch to act on.
  - **Local-unowned collision** (`branch_exists` true, unowned): control never enters the `not branch_exists` block, so `list_branches` is never read and the disambiguation path emits no remote warning — exactly the "local collision still disambiguates without also warning" requirement.
  - **Local-owned** (`branch_owner(...)` not `None`): same — never reaches the remote read; a registered plan already owns the name.
  - **Flag off / non-git / detached HEAD:** the gate returns at `branch_awareness_enabled` or `current_branch is None` **before** `prefixes`/`derived`/`list_branches`, so no branch enumeration happens at all.

- **No mutation on this path.** Unlike the local-unowned branch, the advisory performs no `default_branch` resolution, no first-free `plan/<slug>-N` probe, no `checkout_existing_branch` / `create_and_checkout_branch`, no `set_binding`, and sets no `args._branch_collision_rollback`. The advisory tier is observably a single `warn` + `return None`.

- **Foundational logic + duplication scan.** The core rule added is *"a no-local-branch create whose derived name collides with a remote-tracking ref warns but proceeds."* The detection primitive (`remote_collisions`) and the offline enumerator (`list_branches`) are single-sourced in `plan_tool/cli/gitcommit.py` (step 1). The only other create-time branch preflight is this same gate's local-collision tier and `plan_tool/cli/run_cmd.py:_preflight_branch_guard` (current-vs-bound at run time) — neither performs a remote-namespace check, so there is no parallel remote-collision block to keep in sync. `plan_tool/cli/manifest.py:cmd_attach_branch` is the other prospective `remote_collisions` consumer (a sibling wiring step), out of this step's two-file footprint — see Deferred.

## Tests

All cases are **helper-level**, driving `_create_branch_collision_gate(...)` directly on a `tmp_path` git repo with branch awareness enabled (reuse the module's `_branch_aware_repo`, `_make_branch`, `_args`, `_gate` helpers). No claude is invoked — the gate is pure of orchestrator calls. The remote ref is **simulated by stubbing** `authoring.list_branches` so the test asserts the gate's remote read goes through the offline, network-free seam (never a real remote).

New class `TestCreateBranchRemoteCollisionGate` in `tests/cli/test_authoring_cmds.py`:

- `test_remote_only_collision_warns_and_proceeds` — branch-aware repo, **no** local `plan/demo`; `monkeypatch.setattr(authoring, "list_branches", lambda _r: ["origin/plan/demo", "main"])`; gate returns `None`; stderr names `origin/plan/demo` and contains the "no network performed" caveat.
- `test_remote_no_collision_is_silent` — no local `plan/demo`; stub `list_branches` → `["main", "origin/main"]` (nothing normalizes to `plan/demo`); gate returns `None`; stderr carries no remote-collision warning.
- `test_local_collision_does_not_read_remote` — local unowned `plan/demo` exists (`_make_branch`), `PLAN_TOOL_DEFAULT_BRANCH` set, `--yes`; stub `authoring.list_branches` to raise `AssertionError` (must not be called); gate disambiguates (returns `None`, `branch_exists("plan/demo-2")` true) and emits no remote warning — proves the disambiguation path never reads the remote enumerator.
- `test_flag_off_reads_no_branches` — no branch-awareness config; stub `authoring.list_branches` to raise `AssertionError`; gate returns `None` (short-circuits before any enumeration).
- `test_owned_local_branch_skips_remote_read` — local `plan/demo` exists and `demo` is registered (`registered_slugs={"demo"}`); stub `authoring.list_branches` to raise; gate returns `None` via the owned-defer path without reading remote refs.

### Test-creation order (feature step)

This is a **feature** step. Author the five unit cases **alongside** the `_create_branch_collision_gate` edit:

- `test_remote_only_collision_warns_and_proceeds` / `test_remote_no_collision_is_silent` cover the new advisory branch (warn vs silent).
- `test_local_collision_does_not_read_remote` / `test_owned_local_branch_skips_remote_read` / `test_flag_off_reads_no_branches` pin the negative guarantee: the remote enumerator is read on *no other path*.

Green-before-done gate: every new test must pass (`uv run pytest tests/cli/test_authoring_cmds.py -q`) and the existing `TestCreateBranchCollisionGate` cases must stay green unmodified before the step is finished.

## Acceptance criteria

- `_create_branch_collision_gate` returns `None` (proceeds) on a no-local-branch remote collision and emits a stderr warning naming the colliding `origin/plan/<slug>` ref plus the "no network performed" caveat.
- The gate reads `list_branches` **only** in the no-local-branch path: it is not called when branch awareness is off, when `current_branch` is `None`, when the local derived branch exists (owned or unowned), and disambiguation still produces `plan/<slug>-2` with no remote warning.
- The advisory path performs no checkout, no `set_binding`, and sets no `args._branch_collision_rollback`.
- `authoring.py` imports `list_branches` and `remote_collisions` from `plan_tool.cli.gitcommit`.
- All five new `TestCreateBranchRemoteCollisionGate` cases pass; the existing local-collision suite passes unchanged.

## References

- [Git - Remote Branches (Pro Git)](https://git-scm.com/book/en/v2/Git-Branching-Remote-Branches) — Remote-tracking refs like `origin/plan/<slug>` update only on fetch; grounds the "as of your last fetch — no network performed" wording the advisory must carry.
- [Git - git-for-each-ref Documentation](https://git-scm.com/docs/git-for-each-ref) — The command behind `list_branches`; confirms the enumeration reads local ref storage (incl. `refs/remotes`) with no network call.
- [git-remote(1) Documentation](https://git-scm.com/docs/git-remote) — Multiple-remote configuration and the `<remote>/HEAD` symbolic ref that `remote_collisions` filters, clarifying why a collision message may name more than one remote ref.

## Deferred

- **Wiring `remote_collisions` into `plan_tool/cli/manifest.py:cmd_attach_branch`** — the other create/attach surface that should warn on a remote collision is a sibling step (step 3 of this plan), out of this step's two-file footprint.
- **Consolidating the three branch preflights** (this gate's local + remote tiers and `run_cmd.py:_preflight_branch_guard`) into one shared seam — a cross-command refactor `detail` cannot mint; route to `reconcile-plan` if an audit flags the divergence.
- **Any real-network freshness check** (e.g. `git ls-remote`) — explicitly out of scope; the advisory is offline-only by design and states its staleness in the caveat.
