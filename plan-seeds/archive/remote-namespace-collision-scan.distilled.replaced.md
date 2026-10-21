> **Replaced**: this file has been superseded by `docs/implementation-plans/2-remote-namespace-collision-warning.md`.
> Preserved here for history; do not edit.

## Overview

Wire the existing git-shell helper `plan_tool/cli/gitcommit.py:list_branches` (lists local + remote-tracking short refs, no network) into the two collision surfaces that today detect collisions only against local `refs/heads` via `branch_exists`. With this, a `create`/`attach-branch` whose derived branch already exists *only* as a remote-tracking ref (e.g. `origin/plan/<slug>`) emits an advisory Tier-3 warning and proceeds unchanged. The change is purely additive, gated by the same `branch_awareness.enabled` flag (default OFF), so every existing repo is a byte-for-byte no-op. Either this lands or `list_branches` is dead code that should be deleted — this is the "land it" path.

## Problem statement

The branch-awareness feature (plan `attach-branch-to-plan`) shipped `list_branches`, which lists local **and** remote-tracking short refs (`git for-each-ref` over `refs/heads` + `refs/remotes`, no network) — but **nothing consumes it**. The create-time and attach-time collision surfaces both detect collisions with `branch_exists`, scoped to local `refs/heads` only. So `list_branches` is built-ahead dead code, and the namespace-collision warnings the Architecture describes as "remote-aware" are in fact local-only. The plan prose has since been reconciled to say so, and step 7's Deferred section names this remote scan as the explicit follow-up. The user-visible gap: a derived branch that already exists as someone else's pushed `origin/plan/<slug>` collides silently today.

## Architecture

Two collision surfaces gain a remote dimension; the run guard does not.

- **`create`** (the create-time collision gate, `plan_tool/cli/authoring.py:_create_branch_collision_gate`). Today: if the derived branch exists *locally* with no local owner, strong-warn and disambiguate from default. New: when the derived branch does **not** exist locally but a **remote-tracking** ref normalizes to it, emit an advisory warning ("`origin/plan/<slug>` already exists — likely someone else's plan or an unpulled branch, as of your last fetch") and **proceed unchanged** — no disambiguation, no branch mutation, no bind. The local namespace is free, so the warning is the entire behavior. Insert the remote check as a new branch *after* the local `branch_exists`/owner checks, before the local disambiguation.
- **`attach-branch`** (`plan_tool/cli/manifest.py`, ~the `branch_owner` + `branch_exists` re-home logic). Parity: when the target/re-home name collides only with a remote-tracking ref (no local branch, no local owner), warn in the same advisory voice and proceed; do not block the bind.

**Local always takes precedence.** A local `plan/<slug>` collision still disambiguates-from-default-and-binds exactly as today; if the branch exists locally, the existing local path runs and the remote check is not consulted.

**The normalization rule (load-bearing).** `list_branches` returns short names in a different namespace than the predicate compares against: local `plan/<slug>` vs. remote `origin/plan/<slug>`, `upstream/plan/<slug>`. There is no existing normalization helper — only `default_branch` hard-codes an `origin/` strip. Add a **pure** helper (unit-testable, no I/O) that decides "does any remote ref collide with this derived name?":
- A remote-tracking short ref has the form `<remote>/<branch-with-slashes>`. Strip the **first** path segment (split once on `/`) to recover the bare branch name, and compare to the derived name.
- Filter `<remote>/HEAD` symbolic entries — not real branches, would false-positive.
- Handle **multiple remotes** (the same `plan/<slug>` under `origin` and a fork is one collision, reported once).
- Keep the helper pure: the single git read (`list_branches`) happens once at the call site; the helper takes the ref list + derived name + prefixes as parameters, mirroring the pure-classifier discipline in `branch_ownership.py`.

**Guiding posture: Tier-3 advisory — surface, don't enforce.** A remote-only collision is the loosest ownership signal, so the response is warn-then-proceed — never a block, never an automatic branch mutation.

**Staleness UX (re-introduced on purpose).** Because the scan reads remote-*tracking* refs (no network), it is only ever "as of your last fetch." The warning **must say so** and must not promise freshness — e.g. "…as of your last `git fetch`; run `git fetch` to refresh. No network was performed." (This caveat was removed from the parent plan's Risks when the remote scan was descoped; wiring the feature re-introduces it.)

**Off-state gating.** Callers check `branch_awareness_enabled` first, before any `list_branches` read; with the flag off every repo behaves byte-for-byte as before. Non-git trees and repos with no remotes yield an empty list and fall straight through.

## Out of scope

- **No network.** Never run `git fetch`/`git ls-remote`; read local ref storage only. A stale view is acceptable and labeled as such.
- **No blocking, no mutation on the remote-only path.** Tier-3 advisory only — warn and proceed. No disambiguation, no branch creation, no binding for a remote-only collision.
- **No run-guard change.** The run guard grades the *current* branch; you cannot be checked out on a remote-tracking ref, so its tier classification (`branch_owner`/`classify_branch`) is unaffected and untouched.
- **No change to the local collision path.** Local detection, disambiguation from default, and binding stay exactly as shipped.
- **No remote/upstream binding, no PR linkage, no worktree awareness.** Remote refs are read solely to *warn* about collisions.
- **No multi-remote autodetection beyond the scan** (no "pick the right remote" logic) — every remote-tracking ref that normalizes to the derived name counts.

## Risks

- **Flag-check leakage.** Check `branch_awareness_enabled` first on every new path, before any `list_branches` read; off-is-a-no-op is an explicit test per surface.
- **Remote-name stripping ambiguity.** Splitting `<remote>/<branch>` on the first `/` assumes the first segment is the remote name (true for `for-each-ref refs/remotes` short output). Filter `HEAD` entries; test a branch whose own name contains slashes (`origin/plan/<slug>` → `plan/<slug>`, not `plan`).
- **False sense of safety.** The warning is "as of last fetch" — a dev who never fetched sees nothing. Say so in the message; do not let the wording imply a guarantee.
- **Surface drift.** Keep the remote check additive and behind the same flag-check-first skeleton the two existing collision gates already use, so the local path and the new remote path can't disagree on "what is a collision."
- **Double-warn.** Ensure local and remote-only paths are mutually exclusive (local existence short-circuits the remote check) so a name that exists both locally and remotely doesn't emit two warnings.

## Testing

Unit-first. The normalization helper is pure (ref list + derived name + prefixes in, collision decision out) and gets the bulk of coverage as isolated unit tests: `origin/plan/<slug>` and `fork/plan/<slug>` both normalize to `plan/<slug>` and collide; `<remote>/HEAD` entries are filtered and never collide; a remote ref under a non-configured prefix does not collide; the same name under two remotes counts once; a slash-bearing branch name (`origin/plan/<slug>` → `plan/<slug>`, not `plan`) normalizes correctly; an empty ref list yields no collision. Land these in `tests/cli/test_gitcommit.py` (helper) alongside `list_branches` coverage.

For the two wired surfaces, add cases driving the gates with a stubbed/mocked `list_branches` (asserting no network is performed): `tests/cli/test_authoring_cmds.py` for the `create` create-time gate (`_create_branch_collision_gate`) — enabled remote-only collision warns and proceeds unchanged; local collision still disambiguates and the remote warning does not also fire; flag-off reads nothing. `tests/cli/test_manifest_cmds.py` for the `attach-branch` parity warning — remote-only collision warns advisorily and still binds. Assert the no-network guarantee via a stubbed/mocked `list_branches` and/or a local-only `tmp_path` repo. All existing suites in these three files must still pass; per the invoker seam, override or stub Claude-invoking backends so no real subprocess is spawned.

## Acceptance criteria

- **Off-state is a byte-for-byte no-op:** with `branch_awareness.enabled` off (or absent), neither `create` nor `attach-branch` reads `list_branches`; every existing test passes.
- **Remote-only collision on `create`:** enabled, the derived branch exists only as `origin/plan/<slug>` (no local branch) → an advisory warning that names the remote ref and the "as of last fetch" caveat is emitted, and `create` proceeds unchanged (no disambiguated branch, no bind, no checkout, exit as if no collision).
- **Local beats remote:** when `plan/<slug>` exists *locally*, the existing local disambiguation path runs and the remote-only warning does **not** also fire.
- **Normalization:** `origin/plan/<slug>` and `fork/plan/<slug>` both normalize to `plan/<slug>` and collide; `<remote>/HEAD` entries are filtered and never collide; a remote ref under a non-configured prefix does not collide.
- **Multi-remote:** the same name under two remotes warns once, not twice.
- **No-network guarantee:** the scan issues no network call (assert via a stubbed/mocked `list_branches` and/or a local-only `tmp_path` repo).
- **`attach-branch` parity:** binding/re-homing onto a name that collides only remotely warns advisorily and still binds (no block).
- **Non-git / no-remotes:** `list_branches` returns `[]` → no warning, no crash.
