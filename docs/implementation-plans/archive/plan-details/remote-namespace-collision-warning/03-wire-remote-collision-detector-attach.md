> **Auto-archived**: this plan was swept on 2026-06-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Wire the remote-collision advisory into the attach-branch parity path

## Summary

Extend `plan_tool/cli/manifest.py:cmd_attach_branch` so the plain-bind path (the `if owner is None or owner.slug == slug:` block) reads the offline branch list once and, when the target override name collides only with a remote-tracking ref — no local branch, no local owner — emits a warn-and-proceed advisory (names the colliding remote ref + an "as of your last fetch — no network performed" caveat) before still calling `set_binding`. This is the attach-branch parity of step 2's create-time advisory: a pure advisory tier with **no block and no re-home** — the bind proceeds exactly as before plus a warning. The load-bearing decision is **placement**: the remote read sits inside the plain-bind block gated on `owner is None`, so the AD_HOC hard-refuse path, the CONVENTION re-home path, and the self-owned re-attach (`owner.slug == slug`) never read `list_branches` and never warn. Builds on step 1 (`remote_collisions` + the already-landed offline `list_branches`). On green, binding plan P to a name claimed only as someone else's `origin/<name>` surfaces the collision instead of silently reserving a remotely-taken name.

## Table of Contents

- [Why](#why) — the silent-remote-collision gap on the attach path
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files touched
- [Implementation](#implementation) — the advisory branch, its placement, and imports
- [Tests](#tests) — the required pinned behaviors plus the silent/no-read cases
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors
- [References](#references) — the git docs grounding the offline read + staleness caveat
- [Deferred](#deferred) — the re-home-name remote check and other out-of-footprint items

## Why

- `cmd_attach_branch`'s plain-bind path sees only **local** ownership. It computes `owner = branch_owner(ctx.repo_root, branch, registered, prefixes)` and, when `owner is None`, binds the override verbatim via `set_binding`. A target override that already exists solely as a pushed `origin/<name>` is reserved silently — the operator attaches a plan to a name already taken on the remote and nothing says so.
- Step 1 closes the detection half (`plan_tool/cli/gitcommit.py:remote_collisions`, pure: ref-list in / colliding full short refs out) and gives the offline `list_branches` enumerator a consumer. Step 2 wires it into the create gate. This step closes the same gap on the **attach-branch** parity surface — read `list_branches` once at the no-local-owner bind point and warn when a remote ref collides.
- This is **advisory only** (warn-and-proceed). A remote-tracking ref is just "what the remote looked like at last fetch"; the operator may legitimately want the name, and the command performs no network. Per the accumulated advisory-gate rule, a gate whose purpose is to *inform* degrades to proceed — it never refuses or mutates on this path.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/manifest.py` — extend the existing `from plan_tool.cli.gitcommit import (...)` block to also import `list_branches` and `remote_collisions`; add the remote-advisory read inside `cmd_attach_branch`'s plain-bind block, gated on `owner is None`.
  - `tests/cli/test_manifest_cmds.py` — add cases to the existing `TestAttachBranch` class covering the remote-only warn-and-proceed, the flag-off no-read, the remote-no-collision silent case, the self-owned no-read case, and the local-owner paths not reading remote.

## Implementation

### `plan_tool/cli/manifest.py` — imports

- **Extend the `from plan_tool.cli.gitcommit import (...)` block** (currently `branch_exists`, `checkout_existing_branch`, `commit_all`, `create_and_checkout_branch`, `current_branch`, `working_tree_dirty`) to also import `list_branches` and `remote_collisions`. Both must be module-level names so the component tests can patch `manifest_mod.list_branches` / `manifest_mod.remote_collisions` (the suite patches every git seam as a `manifest_mod` attribute — see `test_attach_rehome_creates_from_existing` patching `manifest_mod.checkout_existing_branch`).
- `remote_collisions` is **step 1's deliverable** (not yet on disk); `list_branches` already exists in `plan_tool/cli/gitcommit.py` (its `git for-each-ref refs/heads refs/remotes`, offline). depends_on: 1.

### `plan_tool/cli/manifest.py` — `cmd_attach_branch` plain-bind block

- **Anchor the change on the existing plain-bind block** — the `if owner is None or owner.slug == slug:` branch that today does `set_binding(ctx.repo_root, slug, branch)` then `success(...)`. `prefixes = branch_prefixes(ctx.repo_root)` is already computed just above (reuse it — no re-read, no re-derive).
- **Gate the remote read on `owner is None`** (the genuinely-foreign-name case = "no local owner"). Inside that block, before `set_binding`:
  - `collisions = remote_collisions(list_branches(ctx.repo_root), branch, prefixes)` — one offline read, the override `branch` is the name tested (not a derived name; attach binds the user's literal override).
  - If `collisions` is non-empty, `warn(...)` naming the colliding remote ref(s) (`", ".join(collisions)`) plus the staleness caveat and the same `git fetch` remediation hint step 2's create advisory carries, e.g. `"{branch} already exists as remote ref(s) {refs} (as of your last fetch — no network performed); run git fetch to refresh; binding anyway."`. Same voice as step 2's create advisory.
  - Then fall through to the existing `set_binding` + `success` — **no block, no re-home, no checkout**. The bind result (rc 0) is unchanged.
- **`owner.slug == slug` (self-owned re-attach) skips the remote read** — placing the read under `if owner is None:` (not the whole `or` block) means re-attaching a plan to its own already-owned name reads nothing and warns nothing. A remote collision on a name you already own is noise.
- **The local-owner paths never reach the read** — the AD_HOC hard-refuse (`owner.kind == OWNER_AD_HOC`) and the CONVENTION re-home path are reached only when `owner is not None` and `owner.slug != slug`, so control never enters the plain-bind block; they neither read `list_branches` nor warn.
- **Foundational logic** — "warn-and-proceed on a remote-only namespace collision, reusing the pure `remote_collisions` normalizer." The parallel call site is `plan_tool/cli/authoring.py:_create_branch_collision_gate` (step 2), which performs the identical read-once + `remote_collisions` + warn-and-proceed in the create gate's no-local-branch path. The two are intentionally separate call sites of the same shared helper (different commands, different name source — derived in create, user-override here); consolidating the two advisory call sites into one helper is a cross-command refactor → Deferred.

## Tests

All in `tests/cli/test_manifest_cmds.py`, added to the existing `TestAttachBranch` class (mirroring its `_args` / `_Recorder` / `_enable_branch_awareness` scaffolding; `list_branches` is stubbed in every case so no test touches the network).

- `test_attach_remote_only_collision_warns_and_binds` — branch awareness on, `branch_owner` stubbed → `None`, `list_branches` stubbed → `["origin/feat/x"]`, `remote_collisions` stubbed (or real) so it returns `["origin/feat/x"]` for target `"feat/x"`; asserts rc 0, `set_binding` still called with `(root, "demo", "feat/x")`, and the captured stderr names `origin/feat/x` and contains the "no network" caveat.
- `test_attach_flag_off_reads_no_branches` — branch awareness off; `list_branches` stubbed to **raise** `AssertionError`; asserts rc 2 (the flag-off refuse) and no raise — proving the early flag-check returns before any branch read.
- `test_attach_local_orphan_plus_remote_warns_and_binds` — `branch_owner` → `None` (unowned local orphan), target `"feat/x"`, `list_branches` stubbed → `["feat/x", "origin/feat/x"]` so the ref list holds both the local orphan and the colliding remote ref; asserts rc 0, `set_binding` still called with `(root, "demo", "feat/x")`, and the advisory fires naming `origin/feat/x` — pinning the stated divergence from `create` (the gate keys on `owner is None`, not no-local-branch, so an unowned local orphan that also exists remotely still warns).
- `test_attach_remote_no_collision_silent` — `branch_owner` → `None`, `list_branches` → `[]` (or refs that don't normalize to the target); asserts rc 0, `set_binding` called, and no warning text in stderr — the advisory is conditional on a non-empty collision.
- `test_attach_self_owned_skips_remote_read` — `branch_owner` → `BranchOwner(slug="demo", kind=OWNER_CONVENTION)`, target `"plan/demo"`; `list_branches` stubbed to **raise**; asserts rc 0 and `set_binding` called — proving the self-owned (`owner.slug == slug`) re-attach never reads remote.
- `test_attach_adhoc_refuse_does_not_read_remote` — `branch_owner` → `BranchOwner(slug="other", kind=OWNER_AD_HOC)`; `list_branches` stubbed to **raise**; asserts rc 2 and the existing "already attached" refuse text — proving the hard-refuse path never reads remote.
- `test_attach_rehome_does_not_read_remote` — `branch_owner` → `BranchOwner(slug="other", kind=OWNER_CONVENTION)`, `-y`, clean tree, mutators stubbed `(0, "")`; `list_branches` stubbed to **raise**; asserts rc 0 (re-home succeeds) — proving the re-home path never reads remote (the advisory is plain-bind-only).

A raising `list_branches` stub on every should-not-read path converts an accidental hoist of the read into a hard failure (the captured "stub-to-raise pins the negative" rule).

### Test-creation order (feature step)

This is a **feature** step. Author the six tests above alongside the `cmd_attach_branch` edit. Green-before-done gate: every new test must pass (and the pre-existing `TestAttachBranch` cases must stay green unmodified) before the step is considered finished. Run `uv run pytest tests/cli/test_manifest_cmds.py -q`.

## Acceptance criteria

- `cmd_attach_branch`, with branch awareness on and `owner is None`, calls `remote_collisions(list_branches(repo_root), branch, prefixes)` exactly once before `set_binding`.
- A non-empty collision emits one `warn` naming the colliding remote ref(s) and the "no network performed" caveat, then still binds (rc 0, `set_binding` called).
- An empty collision binds silently (rc 0, no warning).
- The flag-off, AD_HOC-refuse, CONVENTION-re-home, and self-owned (`owner.slug == slug`) paths never call `list_branches` (proven by a raising stub).
- `manifest.py` imports `list_branches` and `remote_collisions` from `plan_tool.cli.gitcommit`.
- `uv run pytest tests/cli/test_manifest_cmds.py -q` passes.

## References

- [Git - git-for-each-ref Documentation](https://git-scm.com/docs/git-for-each-ref) — the `%(refname:short)` format and `refs/heads refs/remotes` enumeration behind the offline `list_branches` this step consumes.
- [Git - Remote Branches (Pro Git)](https://git-scm.com/book/en/v2/Git-Branching-Remote-Branches) — how remote-tracking refs like `origin/<name>` are stored and only updated on fetch, grounding the "as of your last fetch" caveat and the no-network guarantee.
- [Git - git-check-ref-format Documentation](https://git-scm.com/docs/git-check-ref-format) — legal slash-segment rules for branch names, the basis for `remote_collisions`'s split-once `<remote>/` strip that the attach override (which may itself contain `/`) must respect.

## Deferred

- **Remote collision on the re-home name** — the CONVENTION re-home path mints `rehome = derive_branch(slug, prefixes)` and binds to it; that derived name could also collide with a remote ref. Out of footprint: this step's advisory is the plain-bind parity only ("no block or re-home" per the step title). A re-home-name remote check is a follow-up for reconcile.
- **Consolidating the two advisory call sites** — `cmd_attach_branch`'s plain-bind advisory and `authoring.py:_create_branch_collision_gate`'s create-time advisory perform the same read-once + `remote_collisions` + warn-and-proceed against different name sources. Unifying them into one shared helper is a cross-command refactor `detail` cannot mint → reconcile.
- **Local-orphan-branch collision** — a target that exists as an unowned local branch (orphan, `owner is None`) will trigger the remote advisory only if a remote ref also collides; warning on a purely-local orphan name is a separate ownership concern handled by the tier classifier, not this advisory.
