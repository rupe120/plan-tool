> **Replaced**: this file has been superseded by `docs/implementation-plans/2-structural-dispatcher-consolidation.md`.
> Preserved here for history; do not edit.

## Overview

Consolidate the several near-identical structural apply-or-recommend dispatchers in `plan_tool/cli/review_actions.py` (`_dispatch_structural_escalation`, `_dispatch_reground_remedy`/`_dispatch_merge_remedy`, and `_dispatch_file_check_create`) into one shared shape. This is a **behavior-preserving refactor**, not a feature: it extracts the two truly-common, bug-prone pieces — a shared outcome-application kernel that owns the `WalkState` side-effect tail and a shared gate helper for the three bridge dispatchers — while leaving each dispatcher's genuinely-different glue in place. No user-facing behavior, message text, or exit code changes. Builds the dispatcher-consolidation follow-up of BACKLOG #70.

## Problem statement

Each structural dispatcher hand-rolls the same error-prone outcome→`WalkState` side-effect tail (set `state.apply_skip=True` on every non-applied outcome, leave it `False` on an applied/mutated one), and they have already diverged. The shipped fix `5d4fe1b` corrected exactly this: the `granularity-split` router branch reached `_dispatch_structural_escalation` without the `apply_skip` handling its sibling reground/merge dispatchers have, so an un-split finding was recorded as annotation status `applied` and silently pre-skipped on the next `completeness-apply` run — the required split lost. That was a one-off patch; the divergence surface still exists, so the next remedy can forget the same tail. This plan removes the surface so the bug class becomes unreachable by construction.

## Architecture

Do **not** write one mega-dispatcher: a single parameterized dispatcher would be worse than the status quo because the genuine per-lane differences resist it, and `_dispatch_file_check_create` inverts the `yes_to_all` rule (it **auto-applies** create under `-y`, opposite of the three bridge dispatchers' force-recommend-only), which forcing them together would bury.

Instead extract the two pieces that are truly common and bug-prone:

1. **A shared outcome-application kernel** (the load-bearing piece) — a small pure descriptor plus one function that owns the `WalkState` side-effect tail: given an outcome and its classification, set/leave `apply_skip`, record the halt flags, add to `applied_structural_finding_ids`, and (only when asked) refresh the drift baseline. Each dispatcher maps its bridge's outcome enum to this classification and calls the kernel, so "set `apply_skip=True` on every non-applied outcome" is written once by construction. Keep it a **cycle-free leaf**: it reads/writes `WalkState` and takes a plain descriptor, must not import orchestrators, and can live as a module-level helper (or a helper on `WalkState`) so it is unit-testable in isolation.

2. **A shared gate helper** for the three bridge dispatchers: `allow = <token> and not state.yes_to_all` with `yes=False` / `prompt_fn=None` (the bridge owns the TTY confirm). `_dispatch_file_check_create` is **excluded** from this helper — it has no bridge and inverts `yes_to_all`.

The kernel keys on a per-outcome descriptor with four dimensions, verified against the current behavior map (do not invent new behavior):
- **terminal-applied?** — applied/mutated → leave `apply_skip=False` (walk records `applied`); every other outcome → `apply_skip=True` (walk records `skip`). The genuine-noop "resolved" paths count as terminal-applied (leave False): reground `noop` (plan already fully done) and file-check "already declared"/"moved".
- **halts on applied?** — merge: always; escalation: only when `halt_on_applied` (the completeness-apply lane); reground: never. When set, the kernel sets `state.halt_requested = True` **and** `state.halt_apply_landed = True`.
- **records finding id as applied?** — reground + merge add `rec.id` to `state.applied_structural_finding_ids` (feeds their session short-circuit); escalation + file-check do not.
- **refreshes drift baseline?** — escalation only, and only in the reconcile lane (guarded by `reconcile_scope_guard.iter_lock`); the kernel takes the guard and no-ops when absent. Do not generalize to merge/reground.

Keep per-dispatcher (the kernel must NOT flatten these, per the map): the bridge call itself (`escalate_to_split` / `reground_bridge` / `merge_bridge` / inline `parse_plan`/`write_plan`); the opt-in token (`allow_split` vs `allow_structural_remedy` — deliberately separate, see `review_actions.py:90-96`); the confirm seam (`prompt_fn=None` / `yes=False` / `builtins.input`); the target-id source (`rec.step_id` vs `directive.step_ids`, plus path for file-check); the directive/kind guard (`rec.step_id is None`, `kind==REGROUND`, `kind==MERGE`, `path is None`); the staleness guard (`_saved_directive_is_stale`, reground+merge only, running **after** the session short-circuit and **before** the bridge); and the session short-circuit (reground+merge only). `_dispatch_file_check_create` routes its outcomes through the shared kernel but keeps its own interactive `input` flow and inverted `yes_to_all` auto-apply — if even the kernel doesn't fit it cleanly, leave it out with a one-line rationale rather than contorting the kernel.

## Out of scope

- Per-remedy `--merge`/`--reground` walk flags — a separate #70 follow-up.
- Re-ground's human-authored `create --from-existing` re-baseline arm — a separate #70 follow-up.
- The multi-step/region carve and the code-reveals-a-split reconcile producer — separate #70 follow-ups.
- Precise per-step-id staleness — this refactor preserves the current coarse whole-plan `_saved_directive_is_stale()` guard as-is; replacing it is BACKLOG #93.
- Any behavior change, new capability, or user-facing/exit-code change — if the refactor tempts a behavior change ("this outcome should really set halt"), that is a separate backlog finding, not part of the consolidation.

## Risks

- **Behavior drift during extraction** — behavior-preserving means byte-identical outcomes, not "close enough." Mitigated by authoring the characterization-test matrix FIRST and requiring it to pass unchanged through the extraction (green→refactor→green).
- **Over-consolidation into one mega-dispatcher** would be worse than the status quo, burying `_dispatch_file_check_create`'s inverted `yes_to_all` auto-apply asymmetry. Mitigated by extracting only the two common pieces and keeping per-dispatcher glue in place.
- **Kernel doesn't fit file-check cleanly** — file-check has no bridge and inverts `yes_to_all`. Mitigated by excluding it from the gate helper and, if even the kernel doesn't fit, leaving it out with a one-line rationale rather than contorting the kernel.
- **Losing a genuine per-lane difference** the kernel flattens (halt-on-applied timing, drift refresh scope, session short-circuit, distinct opt-in tokens) — mitigated by grounding the kernel on the verified per-outcome map and preserving the must-preserve list exactly.

## Testing

Characterization-first, per the project's behavior-preserving-refactor discipline: pin the *current* observable behavior of each dispatcher across **every** outcome before touching production code — the returned status string (or a stable substring) and the exact post-call `WalkState` (`apply_skip`, `halt_requested`, `halt_apply_landed`, `applied_structural_finding_ids`), plus the drift `refresh_snapshot` call for escalation-applied-in-reconcile-lane. Only once that matrix is green does the extraction begin, and the same tests must stay green unchanged through it.

- `tests/cli/test_review_actions.py` — extend the existing dispatch classes `TestStructuralEscalation`, `TestRegroundRemedyDispatch`, `TestMergeRemedyDispatch`, `TestSplitEscalationDispatch`, and the file-check tests to assert post-call `WalkState` (not just the return string), filling gaps (e.g. escalation had no `apply_skip` assertions until `23e1685`). Add a direct unit test of the extracted kernel asserting it sets `apply_skip=True` for a non-terminal outcome and leaves it `False` for a terminal-applied one.
- Seam discipline: stub the bridges (`escalate_to_split`, `reground_bridge`, `merge_bridge`) and `builtins.input`; the conftest autouse gate must not see a real backend spawn.
- The full suite must stay green.

## Acceptance criteria

- The `apply_skip`/halt/`applied_structural_finding_ids`/drift-refresh side-effect tail is written **once** in a shared outcome kernel; the three bridge dispatchers (and, if clean, file-check) route their outcomes through it, and no dispatcher hand-rolls `state.apply_skip = True` per-outcome anymore.
- A shared gate helper single-sources `allow = <token> and not state.yes_to_all` for the three bridge dispatchers; `_dispatch_file_check_create` is deliberately excluded.
- A characterization-test matrix over all outcomes of all dispatchers (status string + post-call `WalkState` + escalation's reconcile-lane drift refresh) is authored **before** the extraction and passes **unchanged** after it; the full suite stays green.
- The consolidation makes the `5d4fe1b` bug class unreachable by construction: an outcome is classified as applied/non-applied in one place, so a new remedy reusing the kernel cannot record a non-applied outcome as `applied`. A test asserts the kernel sets `apply_skip=True` for a non-terminal outcome and leaves it `False` for a terminal-applied one.
- No user-facing behavior, message text (beyond incidental wording the tests pin), or exit code changes; the two opt-in tokens (`allow_split` ≠ `allow_structural_remedy`) stay distinct; the BLOCKED-STRUCTURAL reconcile path (`_dispatch_apply_finding` → escalation with `halt_on_applied=False`, and its `applied` drift refresh) and per-lane halt/refresh semantics are byte-identical.
- `BACKLOG.md` #70 is reconciled: strike "consolidating the three apply-or-recommend dispatchers … into one shape" from #70's *Auto-bridges → Remaining follow-ups* list and note the ship date; the other #70 follow-ups stay open. If the shared kernel is worth citing, add a one-line pointer in the CLAUDE.md "Escalate-to-split bridge" / structural-remedy paragraph.

## Deferred

- The other #70 follow-ups (per-remedy `--merge`/`--reground` walk flags, re-ground's human-authored `create --from-existing` re-baseline arm, the multi-step/region carve, and the code-reveals-a-split reconcile producer) — file to BACKLOG #70 as they surface.
- Precise per-step-id staleness (#93) — this refactor preserves the current coarse whole-plan `_saved_directive_is_stale()` guard as-is; replacing it is #93.
- Any behavior change surfaced while refactoring (a dispatcher that "should" halt/refresh/short-circuit but doesn't) → a backlog finding, not this plan.
