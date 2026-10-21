> **Auto-archived**: this plan was swept on 2026-06-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Pure remote-collision detector in `gitcommit.py`

## Summary

Add a pure, I/O-free helper `remote_collisions` to `plan_tool/cli/gitcommit.py` that takes the raw short-ref list from `list_branches`, a derived branch name, and the configured prefixes, and returns the remote-tracking short refs that normalize to the derived name. Normalization splits each short ref **once** on `/` to strip the leading `<remote>/` segment, filters `<remote>/HEAD` symbolic entries, and excludes entries that are themselves local convention branches. The load-bearing decision: the helper is pure (ref list in, colliding refs out) — the single `list_branches` git read stays at the call site (steps 2/3), keeping this function unit-testable with literal lists and the leaf stdlib-only. On green, `list_branches` finally has a consumer: a `create`/`attach-branch` gate can ask "does any remote ref collide with `plan/<slug>`?" without a network call.

## Table of Contents

- [Why](#why) — what gap this closes and why now
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files touched
- [Implementation](#implementation) — the `remote_collisions` helper, signature, and normalization rule
- [Tests](#tests) — unit cases added alongside `list_branches` coverage
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors
- [References](#references) — the git ref-format/for-each-ref docs that ground the split rule
- [Deferred](#deferred) — what steps 2/3 own and the residual heuristic limit

## Why

- `plan_tool/cli/gitcommit.py:list_branches` already lists local **and** remote-tracking short refs offline (`git for-each-ref refs/heads refs/remotes`), but **nothing consumes it** — it is build-ahead dead code.
- The two collision surfaces (`_create_branch_collision_gate` in `plan_tool/cli/authoring.py`, the re-home logic in `plan_tool/cli/manifest.py`) detect collisions only against local `refs/heads` via `branch_exists`. A derived branch that already exists solely as someone else's pushed `origin/plan/<slug>` collides silently today.
- The missing piece is a **pure normalization step**: `list_branches` returns names in a different namespace (`origin/plan/<slug>`) than the predicate compares against (`plan/<slug>`). There is no existing normalization helper — only `default_branch` hard-codes a one-off `origin/` strip. This step adds the reusable, testable primitive; steps 2 and 3 wire it into the two gates.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/gitcommit.py` — add the `remote_collisions` function; add `from collections.abc import Sequence` for the new type hints (the file currently imports only `os`, `subprocess`, `pathlib.Path`). No change to `list_branches` or any other symbol.
  - `tests/cli/test_gitcommit.py` — add a `TestRemoteCollisions` class; extend the top-level import from `plan_tool.cli.gitcommit` to include `remote_collisions`.

## Implementation

### `plan_tool/cli/gitcommit.py` — add `remote_collisions`

- **Signature:** `def remote_collisions(refs: Sequence[str], derived: str, prefixes: Sequence[str]) -> list[str]`.
  - `refs` — the raw output of `list_branches` (local + remote-tracking short refs, unsorted, unfiltered).
  - `derived` — the canonical branch name to test against (the caller computes it via `plan_tool.project_config.derive_branch(slug, prefixes)`, e.g. `plan/<slug>`).
  - `prefixes` — the configured branch prefixes (caller computes once via `plan_tool.project_config.branch_prefixes`); used only to exclude local convention branches (below).
- **Returns:** the sorted, de-duplicated list of the **colliding remote-tracking short refs** in full form, e.g. `["fork/plan/<slug>", "origin/plan/<slug>"]`; `[]` when nothing collides. Returning the full short refs (not just the stripped name) lets steps 2/3 name the offending ref in the advisory message; the caller collapses the list into a **single** warning ("collapse multi-remote / report once" is the gate's job, not this helper's — see Deferred).
- **Purity:** no `subprocess`, no `repo_root`, no git read. Mirrors the pure-classifier discipline in `plan_tool/branch_ownership.py` (`convention_owner`, `matches_convention_pattern`) — the lone git read (`list_branches`) happens once at the call site and the result is passed in.
- **Normalization rule (load-bearing), applied per entry in `refs`:**
  1. **Skip single-segment entries** — a ref with no `/` (e.g. `main`) cannot be a `<remote>/<branch>` tracking ref; skip it.
  2. **Skip local convention branches** — skip any entry that *itself* starts with a configured prefix with a non-empty tail (`any(entry.startswith(p) and len(entry) > len(p) for p in prefixes)`). An entry like `plan/<slug>` is a local convention branch, not a remote ref; its first segment is a prefix, not a remote name. This is the only use of `prefixes`. Implement the check **inline** (stdlib only) — do **not** import `plan_tool.branch_ownership.matches_convention_pattern`, which would invert the dependency direction and break `gitcommit.py`'s stdlib-only leaf contract (it imports nothing from `plan_tool.*`).
  3. **Split once on `/`** — `remote, _, tail = entry.partition("/")`. `tail` is the bare branch name with the `<remote>/` segment stripped. `partition` (split-once) preserves slash-bearing branch names: `origin/plan/my/slug` → `tail == "plan/my/slug"`, **not** `plan`.
  4. **Filter `<remote>/HEAD`** — skip when `tail == "HEAD"` (the symbolic `origin/HEAD` entry is not a real branch and must not false-positive) or when `tail` is empty.
  5. **Collision test** — when `tail == derived`, the entry collides; collect the **full** `entry` (e.g. `origin/plan/<slug>`).
- **De-dup + order:** return `sorted(set(collected))` so the result is deterministic and a name appearing once per remote yields one entry per remote (a duplicated raw entry collapses).
- **Call sites:** none in this step. `remote_collisions` is consumed by `_create_branch_collision_gate` (`plan_tool/cli/authoring.py`, step 2) and `cmd_attach_branch` (`plan_tool/cli/manifest.py`, step 3). Both gate on `branch_awareness_enabled` first and read `list_branches` once before calling this helper.

### Foundational logic / duplication scan

- **Core rule added:** "strip the `<remote>/` segment from a short ref and compare the remainder to a derived branch name." The only other `origin/`-stripping in the codebase is the hard-coded `_, _, branch = short.partition("/")` inside `plan_tool/cli/gitcommit.py:default_branch` — that one is scoped to the single `refs/remotes/origin/HEAD` symbolic ref and is not a general normalizer; leave it untouched (different input, different purpose).
- **Convention-pattern check duplicated:** step 2 (`prefixes` exclusion) replicates the semantics of `plan_tool/branch_ownership.py:matches_convention_pattern`. Consolidation into one source is impossible here — `gitcommit.py` is a stdlib leaf below `branch_ownership.py` and importing it would create a cycle. The inline duplicate (one boolean expression) is the correct trade; no consolidation step is minted.

## Tests

All cases land in `tests/cli/test_gitcommit.py` in a new `TestRemoteCollisions` class. The helper is pure, so every test passes literal lists — no `tmp_path` repo, no git. Place the class adjacent to `TestListBranches` (the producer whose output it normalizes).

- `test_single_remote_collides` — `["origin/plan/x"]`, derived `plan/x` → `["origin/plan/x"]`.
- `test_multi_remote_both_surfaced` — `["origin/plan/x", "fork/plan/x"]`, derived `plan/x` → `["fork/plan/x", "origin/plan/x"]` (both colliding remotes returned, sorted; the single-warning collapse is the gate's concern).
- `test_remote_head_is_filtered` — `["origin/HEAD"]`, derived `HEAD` → `[]` (symbolic `<remote>/HEAD` never collides).
- `test_non_matching_remote_no_collision` — `["origin/feature/y"]`, derived `plan/x` → `[]` (a remote ref under a non-derived name does not collide).
- `test_slash_bearing_branch_name_normalizes` — `["origin/plan/my/slug"]`, derived `plan/my/slug` → `["origin/plan/my/slug"]` (split-once keeps the slash-bearing tail; not stripped to `plan`).
- `test_local_convention_branch_not_remote_collision` — `["plan/x"]`, prefixes `["plan/"]`, derived `plan/x` → `[]` (a local convention branch is excluded, never treated as a remote ref).
- `test_single_segment_ref_ignored` — `["main"]`, derived `plan/x` → `[]` (no `/`, cannot be a tracking ref).
- `test_duplicate_raw_entries_deduped` — `["origin/plan/x", "origin/plan/x"]`, derived `plan/x` → `["origin/plan/x"]` (de-dup).
- `test_empty_ref_list_no_collision` — `[]`, derived `plan/x` → `[]`.

### Test-creation order (feature step)

- This is a **feature** step — new behavior with no prior test pinning it.
- Add the nine `TestRemoteCollisions` cases **with** the `remote_collisions` implementation in the same change.
- **Green-before-done gate:** every new case above must pass (`uv run pytest tests/cli/test_gitcommit.py -q`) before this step is considered finished; the existing `TestListBranches` and all other `test_gitcommit.py` classes must keep passing unmodified.

## Acceptance criteria

- `plan_tool.cli.gitcommit.remote_collisions(refs, derived, prefixes)` exists with that signature and returns `list[str]`.
- `remote_collisions(["origin/plan/x"], "plan/x", ["plan/"]) == ["origin/plan/x"]`.
- `remote_collisions(["origin/plan/x", "fork/plan/x"], "plan/x", ["plan/"]) == ["fork/plan/x", "origin/plan/x"]`.
- `remote_collisions(["origin/HEAD"], "HEAD", ["plan/"]) == []`.
- `remote_collisions(["plan/x"], "plan/x", ["plan/"]) == []` (local convention branch excluded).
- `remote_collisions(["origin/plan/my/slug"], "plan/my/slug", ["plan/"]) == ["origin/plan/my/slug"]` (slash-bearing tail preserved).
- `remote_collisions([], "plan/x", ["plan/"]) == []`.
- The function performs **no** `subprocess` / git call (verifiable by inspection; it takes no `repo_root`).
- `gitcommit.py` still imports nothing from `plan_tool.*` (stdlib-only leaf preserved).
- `uv run pytest tests/cli/test_gitcommit.py -q` is green.

## References

- [Git - git-for-each-ref Documentation](https://git-scm.com/docs/git-for-each-ref) — the `%(refname:short)` format that `list_branches` uses to print local and remote-tracking refs offline; defines the short-name shape this helper normalizes.
- [Git - git-check-ref-format Documentation](https://git-scm.com/docs/git-check-ref-format) — legal branch-name characters and slash-segment rules, justifying split-once (`partition`) over a greedy split so slash-bearing branch names survive normalization.
- [git-remote(1) Documentation](https://git-scm.com/docs/git-remote) — multiple-remote configuration and the `<remote>/HEAD` symbolic ref, grounding the multi-remote handling and the `HEAD` filter.

## Deferred

- **Wiring into the two gates** — steps 2 (`plan_tool/cli/authoring.py:_create_branch_collision_gate`) and 3 (`plan_tool/cli/manifest.py:cmd_attach_branch`) call `remote_collisions`, gate on `branch_awareness_enabled` first, read `list_branches` once, and emit the advisory "as of your last fetch / no network performed" warning. Out of scope here.
- **Collapse-to-one-warning ("reported once")** — this helper returns every colliding remote ref so the caller can name them; emitting a single advisory regardless of how many remotes match is the gate's responsibility (steps 2/3), not the helper's.
- **Residual heuristic limit** — a local branch literally named `<segment>/plan/<slug>` (a non-prefix leading segment) would normalize to `plan/<slug>` and false-positive, because local-vs-remote cannot be perfectly distinguished from short names alone. Accepted as a Tier-3 advisory risk (the feature only ever warns, never blocks or mutates); a precise fix would require `list_branches` to tag each ref local/remote — not in this plan's scope.
- **Consolidating the convention-pattern check** — the inline prefix exclusion duplicates `plan_tool/branch_ownership.py:matches_convention_pattern`; deduping is blocked by `gitcommit.py`'s stdlib-only leaf contract and is not minted as a refactor step.
