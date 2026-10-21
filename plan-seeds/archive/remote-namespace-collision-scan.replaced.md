> **Replaced**: this file has been superseded by `docs/implementation-plans/2-remote-namespace-collision-warning.md`.
> Preserved here for history; do not edit.

# Plan seed: remote-aware namespace-collision scan (wire `list_branches`)

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing plan-seeds/remote-namespace-collision-scan.md --iterate
```

It is **not** itself a plan — `plan-tool create` consumes the prose below
and proposes a step decomposition; the author then runs `plan-tool detail`
per step.

---

## Context — what exists and what this finishes

The branch-awareness feature (plan `attach-branch-to-plan`) shipped a
git-shell helper `plan_tool/cli/gitcommit.py:list_branches` that lists
local **and** remote-tracking short refs (`git for-each-ref` over
`refs/heads` + `refs/remotes`, no network) — but **nothing consumes it**.
The create-time and attach-time collision surfaces both detect collisions
with `branch_exists`, which is scoped to local `refs/heads` only. So
`list_branches` is built-ahead, dead code, and the namespace-collision
warnings the Architecture describes as "remote-aware" are in fact
local-only (the plan prose has since been reconciled to say so, and step
7's Deferred section names this remote scan as the explicit follow-up).

This plan **wires `list_branches` into the collision surfaces** so a
`create`/`attach-branch` whose derived branch already exists *only as a
remote-tracking ref* (e.g. `origin/plan/<slug>`) surfaces an advisory
warning. Either this lands, or `list_branches` should be deleted as
unused — this plan is the "land it" path.

## Guiding principle

**Advisory, Tier-3 posture: surface, don't enforce.** A remote-only
collision means someone (or a past you) pushed a branch under the same
convention name — *likely someone else's work or an unpulled branch*. It
is the loosest ownership signal, so the response is a **warning, then
proceed** — never a block, never an automatic branch mutation. The change
is purely **additive**: a new warning for a case that is silent today.

> **Gated by the same `branch_awareness.enabled` flag (default OFF).** With
> the flag off — every existing repo — this is a byte-for-byte no-op: the
> flag is checked first, before any `list_branches` read. Non-git trees and
> repos with no remotes yield an empty list and fall straight through.

## What changes

Two collision surfaces gain a remote dimension; the run guard does not.

- **`create` (the create-time collision gate,
  `plan_tool/cli/authoring.py:_create_branch_collision_gate`).** Today: if
  the derived branch exists *locally* with no local owner, strong-warn and
  disambiguate from default. New: additionally, when the derived branch
  does **not** exist locally but a **remote-tracking** ref normalizes to it,
  emit an advisory warning ("`origin/plan/<slug>` already exists — likely
  someone else's plan or an unpulled branch, as of your last fetch") and
  **proceed unchanged** — *no disambiguation, no branch mutation, no bind*.
  The local namespace is free, so there is nothing to disambiguate; the
  warning is the entire behavior.
- **`attach-branch` (`plan_tool/cli/manifest.py`).** Parity: when the
  target/re-home name collides only with a remote-tracking ref (no local
  branch, no local owner), warn in the same advisory voice and proceed; do
  not block the bind.

**The local collision behavior is unchanged.** A local `plan/<slug>`
collision still disambiguates-from-default-and-binds exactly as it does
today. Local always takes precedence: if the branch exists locally, the
existing local path runs and the remote check is not consulted.

## The normalization rule (the load-bearing detail)

`list_branches` returns short names in a different namespace than the
predicate compares against: local `plan/<slug>` vs. remote
`origin/plan/<slug>`, `upstream/plan/<slug>`. There is **no existing
normalization helper** — only `default_branch` hard-codes an `origin/`
strip. Add a **pure** helper (unit-testable, no I/O) that decides "does any
remote ref collide with this derived name?":

- A remote-tracking short ref has the form `<remote>/<branch-with-slashes>`.
  Strip the **first** path segment (split once on `/`) to recover the bare
  branch name, and compare that to the derived name.
- **Filter the `<remote>/HEAD` symbolic entries** — they are not real
  branches and would false-positive.
- Handle **multiple remotes** (the same `plan/<slug>` under `origin` and a
  fork is one collision, reported once).
- Keep the helper pure: the single git read (`list_branches`) happens once
  at the call site; the helper takes the ref list + derived name + prefixes
  as parameters (mirroring the pure-classifier discipline in
  `branch_ownership.py`).

## Staleness UX (re-introduced on purpose)

Because the scan reads remote-*tracking* refs (no network), it is only ever
"as of your last fetch." The warning **must say so** and must not promise
freshness — e.g. "…as of your last `git fetch`; run `git fetch` to refresh.
No network was performed." (This staleness caveat was removed from the
parent plan's Risks when the remote scan was descoped; wiring the feature
re-introduces it.)

## Out of scope / non-goals

- **No network.** Never run `git fetch`/`git ls-remote`; read local
  ref storage only. A stale view is acceptable and labeled as such.
- **No blocking, no mutation on the remote-only path.** Tier-3 advisory
  only — warn and proceed. No disambiguation, no branch creation, no
  binding for a remote-only collision.
- **No run-guard change.** The run guard grades the *current* branch; you
  cannot be checked out on a remote-tracking ref, so its tier
  classification (`branch_owner`/`classify_branch`) is unaffected and
  untouched.
- **No change to the local collision path.** Local detection, disambiguation
  from default, and binding stay exactly as shipped.
- **No remote/upstream binding, no PR linkage, no worktree awareness.**
  Remote refs are read solely to *warn* about collisions.
- **No multi-remote autodetection beyond the scan** (no "pick the right
  remote" logic) — every remote-tracking ref that normalizes to the derived
  name counts.

## Acceptance criteria (plan-level)

- **Off-state is a byte-for-byte no-op:** with `branch_awareness.enabled`
  off (or absent), neither `create` nor `attach-branch` reads
  `list_branches`; every existing test passes.
- **Remote-only collision on `create`:** enabled, the derived branch exists
  only as `origin/plan/<slug>` (no local branch) → an advisory warning that
  names the remote ref and the "as of last fetch" caveat is emitted, and
  `create` **proceeds unchanged** (no disambiguated branch, no bind, no
  checkout, exit as if no collision).
- **Local beats remote:** when `plan/<slug>` exists *locally*, the existing
  local disambiguation path runs and the remote-only warning does **not**
  also fire.
- **Normalization:** `origin/plan/<slug>` and `fork/plan/<slug>` both
  normalize to `plan/<slug>` and collide; `<remote>/HEAD` entries are
  filtered and never collide; a remote ref under a non-configured prefix
  does not collide.
- **Multi-remote:** the same name under two remotes warns once, not twice.
- **No-network guarantee:** the scan issues no network call (assert via a
  stubbed/mocked `list_branches` and/or a local-only `tmp_path` repo).
- **`attach-branch` parity:** binding/re-homing onto a name that collides
  only remotely warns advisorily and still binds (no block).
- **Non-git / no-remotes:** `list_branches` returns `[]` → no warning, no
  crash.

## Risks

- **Flag-check leakage.** Check `branch_awareness_enabled` first on every
  new path, before any `list_branches` read; off-is-a-no-op is an explicit
  test per surface.
- **Remote-name stripping ambiguity.** Splitting `<remote>/<branch>` on the
  first `/` assumes the first segment is the remote name (true for
  `for-each-ref refs/remotes` short output). Filter `HEAD` entries; test a
  branch whose own name contains slashes (`origin/plan/<slug>` →
  `plan/<slug>`, not `plan`).
- **False sense of safety.** The warning is "as of last fetch" — a dev who
  never fetched sees nothing. Say so in the message; do not let the wording
  imply a guarantee.
- **Surface drift.** Keep the remote check additive and behind the same
  flag-check-first skeleton the two existing collision gates already use, so
  the local path and the new remote path can't disagree on "what is a
  collision."
- **Double-warn.** Ensure local and remote-only paths are mutually exclusive
  (local existence short-circuits the remote check) so a name that exists
  both locally and remotely doesn't emit two warnings.

## Seams to verify before extending

- `plan_tool/cli/gitcommit.py:list_branches` (the producer to consume) and
  `branch_exists` / `default_branch` (the latter's `origin/` strip is the
  only existing remote-name handling — generalize, don't copy).
- `plan_tool/cli/authoring.py:_create_branch_collision_gate` (create
  surface; insert the remote check as the new branch *after* the local
  `branch_exists`/owner checks, before the local disambiguation).
- `plan_tool/cli/manifest.py` attach-branch handler (~the `branch_owner` +
  `branch_exists` re-home logic) for the parity warning.
- `plan_tool/branch_ownership.py` for the pure-helper / parameter-not-I/O
  discipline the normalization helper should follow.
- `tests/cli/test_authoring_cmds.py`, `tests/cli/test_manifest_cmds.py`,
  `tests/cli/test_gitcommit.py` for where the new cases land.

## References

- [Git - git-for-each-ref Documentation](https://git-scm.com/docs/git-for-each-ref)
  — no-network listing of `refs/heads` + `refs/remotes`, the basis for
  `list_branches` and its `%(refname:short)` output this plan parses.
- [Git - git-check-ref-format Documentation](https://git-scm.com/docs/git-check-ref-format)
  — ref-name rules the derived name already satisfies; relevant when
  reasoning about the slash structure of remote short names.
