> **Auto-archived**: this plan was swept on 2026-06-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Remote Namespace Collision Warning
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: 'Add pure remote-collision detector to gitcommit.py: normalize remote-tracking
    short refs (split-once on ''/'' to strip the <remote>/ segment, filter <remote>/HEAD,
    collapse multi-remote) and return remote refs colliding with a derived branch
    name — unit tests in test_gitcommit.py alongside list_branches coverage'
  files:
  - plan_tool/cli/gitcommit.py
  - tests/cli/test_gitcommit.py
  complexity: low
  change_type: feature
  detail: docs/implementation-plans/plan-details/remote-namespace-collision-warning/01-pure-remote-collision-detector.md
  status: done
- id: 2
  title: Wire the remote-collision detector into the create-time gate (_create_branch_collision_gate
    in authoring.py) as a flag-gated advisory Tier-3 branch inserted after the local
    branch_exists/branch_owner checks and before local disambiguation — warn-and-proceed
    (name the remote ref + 'as of last fetch, no network performed' caveat), no disambiguation/bind/checkout;
    component tests in test_authoring_cmds.py (remote-only warns and proceeds, local
    collision still disambiguates without also warning, flag-off reads nothing) with
    list_branches stubbed to assert no network
  files:
  - plan_tool/cli/authoring.py
  - tests/cli/test_authoring_cmds.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/remote-namespace-collision-warning/02-wire-remote-collision-detector-create.md
  status: done
- id: 3
  title: Wire the remote-collision detector into the attach-branch parity path (cmd_attach_branch
    in manifest.py) — flag-gated advisory warning (same voice + staleness caveat)
    when the target/re-home name collides only with a remote-tracking ref (no local
    branch, no local owner), still bind with no block or re-home; component tests
    in test_manifest_cmds.py (remote-only collision warns and still binds, flag-off
    reads nothing) with list_branches stubbed to assert no network
  files:
  - plan_tool/cli/manifest.py
  - tests/cli/test_manifest_cmds.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/remote-namespace-collision-warning/03-wire-remote-collision-detector-attach.md
  status: done
---
# Remote Namespace Collision Warning

## Overview

Wire the existing git-shell helper `plan_tool/cli/gitcommit.py:list_branches` (lists local + remote-tracking short refs, no network) into the two collision surfaces that today detect collisions only against local `refs/heads` via `branch_exists`. With this, a `create`/`attach-branch` whose derived branch already exists *only* as a remote-tracking ref (e.g. `origin/plan/<slug>`) emits an advisory Tier-3 warning and proceeds unchanged. The change is purely additive, gated by the same `branch_awareness.enabled` flag (default OFF), so every existing repo is a byte-for-byte no-op. Either this lands or `list_branches` is dead code that should be deleted — this is the "land it" path.

## Problem statement

The branch-awareness feature (plan `attach-branch-to-plan`) shipped `list_branches`, which lists local **and** remote-tracking short refs (`git for-each-ref` over `refs/heads` + `refs/remotes`, no network) — but **nothing consumes it**. The create-time and attach-time collision surfaces both detect collisions with `branch_exists`, scoped to local `refs/heads` only. So `list_branches` is built-ahead dead code, and the namespace-collision warnings the Architecture describes as "remote-aware" are in fact local-only. The plan prose has since been reconciled to say so, and step 7's Deferred section names this remote scan as the explicit follow-up. The user-visible gap: a derived branch that already exists as someone else's pushed `origin/plan/<slug>` collides silently today.

## Architecture

Two collision surfaces gain a remote dimension; the run guard does not.

- **`create`** (the create-time collision gate, `plan_tool/cli/authoring.py:_create_branch_collision_gate`). Today: if the derived branch exists *locally* with no local owner, strong-warn and disambiguate from default. New: when the derived branch does **not** exist locally but a **remote-tracking** ref normalizes to it, emit an advisory warning ("`origin/plan/<slug>` already exists — likely someone else's plan or an unpulled branch, as of your last fetch") and **proceed unchanged** — no disambiguation, no branch mutation, no bind. The local namespace is free, so the warning is the entire behavior. Place the remote check inside the no-local-branch path — replace the early `return None` in the `if not branch_exists(...)` block, so it runs only when the derived branch does not exist locally and never reaches the local owner check or disambiguation.
- **`attach-branch`** (`plan_tool/cli/manifest.py`, ~the `branch_owner` + `branch_exists` re-home logic). Near-parity: when the target/re-home name has no local owner (`branch_owner` returns `None`) and a remote-tracking ref normalizes to it, warn in the same advisory voice and proceed; do not block the bind. The gate keys on `owner is None`, not on no-local-branch, so an unowned local orphan branch that also exists remotely still warns (it diverges from `create`, which checks `branch_exists` first — see step 3 Deferred).

**Local always takes precedence.** A local `plan/<slug>` collision still disambiguates-from-default-and-binds exactly as today; if the branch exists locally, the existing local path runs and the remote check is not consulted.

**The normalization rule (load-bearing).** `list_branches` returns short names in a different namespace than the predicate compares against: local `plan/<slug>` vs. remote `origin/plan/<slug>`, `upstream/plan/<slug>`. There is no existing normalization helper — only `default_branch` hard-codes an `origin/` strip. Add a **pure** helper (unit-testable, no I/O) that decides "does any remote ref collide with this derived name?":
- A remote-tracking short ref has the form `<remote>/<branch-with-slashes>`. Strip the **first** path segment (split once on `/`) to recover the bare branch name, and compare to the derived name.
- Filter `<remote>/HEAD` symbolic entries — not real branches, would false-positive.
- Handle **multiple remotes** (the same `plan/<slug>` under `origin` and a fork is one collision, surfaced as a single advisory that names every colliding remote ref — one warning, not one ref).
- Keep the helper pure: the single git read (`list_branches`) happens once at the call site; the helper takes the ref list + derived name + prefixes as parameters, mirroring the pure-classifier discipline in `branch_ownership.py`.
- Scope: remote collision detection tests only the **primary** derived name (the one `derive_branch` produces from the primary prefix), mirroring the local create path's primary-only `branch_exists` check. A remote convention name under a configured *secondary* prefix (e.g. `origin/feature/<slug>` when prefixes are `["plan/", "feature/"]`) is **out of scope by design** — it never warns, keeping the remote path byte-for-byte consistent with local detection.

**Guiding posture: Tier-3 advisory — surface, don't enforce.** A remote-only collision is the loosest ownership signal, so the response is warn-then-proceed — never a block, never an automatic branch mutation.

**Staleness UX (re-introduced on purpose).** Because the scan reads remote-*tracking* refs (no network), it is only ever "as of your last fetch." The warning **must say so** and must not promise freshness — e.g. "…as of your last `git fetch`; run `git fetch` to refresh. No network was performed." (This caveat was removed from the parent plan's Risks when the remote scan was descoped; wiring the feature re-introduces it.)

**Off-state gating.** Callers check `branch_awareness_enabled` first, before any `list_branches` read; with the flag off every repo behaves byte-for-byte as before. Non-git trees and repos with no remotes yield an empty list and fall straight through.

## References

- [Git - git-for-each-ref Documentation](https://git-scm.com/docs/git-for-each-ref) — Official reference for the command underlying `list_branches`, including the `%(refname:short)` format that strips `refs/remotes/` and the field modifiers an implementer needs to enumerate local and remote-tracking refs without a network call.
- [Git - git-refs Documentation](https://git-scm.com/docs/git-refs) — Defines the ref hierarchy (`refs/heads` vs `refs/remotes`) that distinguishes a local branch from a remote-tracking ref, which is the exact distinction the new collision check is built on.
- [Git - Remote Branches (Pro Git)](https://git-scm.com/book/en/v2/Git-Branching-Remote-Branches) — Authoritative explanation of how remote-tracking branches like `origin/plan/<slug>` are stored and only updated on fetch, grounding the plan's 'as of your last fetch' staleness caveat and no-network guarantee.
- [Git - git-check-ref-format Documentation](https://git-scm.com/docs/git-check-ref-format) — Specifies the legal characters and slash-segment rules for branch names, needed to correctly split `<remote>/<branch-with-slashes>` on the first `/` and handle slash-bearing branch names in the normalization helper.
- [git-remote(1) Documentation](https://git-scm.com/docs/git-remote) — Documents multiple-remote configuration and the `<remote>/HEAD` symbolic ref, clarifying why the helper must handle several remotes and filter out `HEAD` entries to avoid false-positive collisions.

## Steps

See the `steps:` block in the frontmatter.

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

For the two wired surfaces, add cases driving the gates with a stubbed/mocked `list_branches` (asserting no network is performed): `tests/cli/test_authoring_cmds.py` for the `create` create-time gate (`_create_branch_collision_gate`) — enabled remote-only collision warns and proceeds unchanged; local collision still disambiguates and the remote warning does not also fire; flag-off reads nothing; a **two-remote collision** (`list_branches` returns both `origin/plan/<slug>` and `fork/plan/<slug>`) emits **exactly one** warning naming both refs (the gate collapses the helper's two-ref result into a single advisory — pin the "reported once" claim at the wiring level, not just the helper's de-dup). `tests/cli/test_manifest_cmds.py` for the `attach-branch` parity warning — remote-only collision warns advisorily and still binds. Assert the no-network guarantee via a stubbed/mocked `list_branches` and/or a local-only `tmp_path` repo. All existing suites in these three files must still pass; per the invoker seam, override or stub Claude-invoking backends so no real subprocess is spawned.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — unit tests added with the implementation; green before completion.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.

## Acceptance criteria

- **Off-state is a byte-for-byte no-op:** with `branch_awareness.enabled` off (or absent), neither `create` nor `attach-branch` reads `list_branches`; every existing test passes.
- **Remote-only collision on `create`:** enabled, the derived branch exists only as `origin/plan/<slug>` (no local branch) → an advisory warning that names the remote ref and the "as of last fetch" caveat is emitted, and `create` proceeds unchanged (no disambiguated branch, no bind, no checkout, exit as if no collision).
- **Local beats remote:** when `plan/<slug>` exists *locally*, the existing local disambiguation path runs and the remote-only warning does **not** also fire.
- **Normalization:** `origin/plan/<slug>` and `fork/plan/<slug>` both normalize to `plan/<slug>` and collide; `<remote>/HEAD` entries are filtered and never collide; a remote ref under a non-configured prefix does not collide.
- **Multi-remote:** the same name under two remotes warns once, not twice.
- **No-network guarantee:** the scan issues no network call (assert via a stubbed/mocked `list_branches` and/or a local-only `tmp_path` repo).
- **`attach-branch` advisory:** binding/re-homing onto a name with no local owner that also collides with a remote ref warns advisorily and still binds (no block); the gate keys on `owner is None`, so an unowned local orphan that also exists remotely warns too (per step 3 Deferred, not full parity with `create`).
- **Non-git / no-remotes:** `list_branches` returns `[]` → no warning, no crash.

## Deferred

- **Opt-in network refresh before the scan** (e.g. a `--fetch` flag that runs `git fetch` first) — kept out of this iteration to preserve the strict no-network guarantee; the "as of last fetch" staleness gap motivates revisiting it so a never-fetched dev isn't blind to a remote collision.
- **Per-remote spread summary beyond the ref list** — the single advisory already names every colliding remote ref; a richer summary (e.g. grouping refs by remote, counts, or fetch-recency per remote) is postponed as a UX refinement, not a correctness need.
