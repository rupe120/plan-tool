> **Replaced**: this file has been superseded by `docs/implementation-plans/2-structural-dispatcher-consolidation.md`.
> Preserved here for history; do not edit.

# Plan seed: consolidate the structural-remedy apply-or-recommend dispatchers into one shape

Builds the **dispatcher-consolidation follow-up** of BACKLOG **#70**
("Structural-remedy vocabulary: remaining convenience arms" → Auto-bridges →
"consolidating the three apply-or-recommend dispatchers
(`_dispatch_structural_escalation`, `_dispatch_file_check_create`,
`_dispatch_reground_remedy`/`_dispatch_merge_remedy`) into one shape").

This is a **behavior-preserving refactor**, not a feature. Its whole purpose is to
kill a *class of bug*: the several near-identical structural dispatchers in
`plan_tool/cli/review_actions.py` each hand-roll the same error-prone
outcome→`WalkState` side-effect tail (set `state.apply_skip=True` on every
non-applied outcome, leave it `False` on an applied/mutated one), and they have
already diverged. The shipped fix `5d4fe1b` corrected exactly this: the
`granularity-split` router branch reached `_dispatch_structural_escalation`
without the `apply_skip` handling its sibling reground/merge dispatchers have, so
an un-split finding was recorded as annotation status `applied` and silently
pre-skipped on the next `completeness-apply` run — the required split lost. That
was a one-off patch; this plan removes the divergence surface so the next remedy
*cannot* forget.

> **Backlog reconciliation (carry forward — required).** Derived from BACKLOG
> **#70**. The final docs/status step **must** update `BACKLOG.md`: strike
> "consolidating the three apply-or-recommend dispatchers … into one shape" from
> #70's *Auto-bridges → Remaining follow-ups* list and note the ship date. The
> other #70 follow-ups (per-remedy `--merge`/`--reground` walk flags, re-ground's
> `create --from-existing` re-baseline arm, multi-step carve, code-reveals-a-split)
> stay open.

## The design thesis (do NOT write one mega-dispatcher)

A single parameterized dispatcher would be *worse* than the status quo: the
genuine per-lane differences (below) resist it, and `_dispatch_file_check_create`
inverts the `yes_to_all` rule (it **auto-applies** create under `-y`, opposite of
the three bridge dispatchers' force-recommend-only). Forcing them together buries
that asymmetry. Instead extract the **two pieces that are truly common and
bug-prone**, and leave each dispatcher's genuinely-different glue in place:

1. **A shared outcome-application kernel** — the load-bearing piece. A small pure
   descriptor plus one function that owns the `WalkState` side-effect tail:
   given an outcome and its classification, set/leave `apply_skip`, record the
   halt flags, add to `applied_structural_finding_ids`, and (only when asked)
   refresh the drift baseline. Each dispatcher maps its bridge's outcome enum to
   this classification and calls the kernel — so "set `apply_skip=True` on every
   non-applied outcome" is written **once**, by construction. This is the whole
   point; everything else is secondary.

2. **A shared gate helper** for the three bridge dispatchers: `allow = <token>
   and not state.yes_to_all` with `yes=False` / `prompt_fn=None` (the bridge owns
   the TTY confirm). `_dispatch_file_check_create` is **excluded** from this
   helper (it has no bridge and inverts `yes_to_all`).

Keep per-dispatcher: the bridge call itself, the opt-in token (`allow_split` vs
`allow_structural_remedy` — deliberately separate, see `review_actions.py:90-96`),
the target-id source (`rec.step_id` vs `directive.step_ids`), the directive/kind
guard, the staleness guard, and the session short-circuit.

## The outcome classification (ground the kernel on this)

The kernel keys on a per-outcome descriptor with these dimensions (every current
behavior is one combination — verify against the map, do not invent new
behavior):

- **terminal-applied?** — did the bridge mutate the plan? Applied/mutated →
  leave `apply_skip=False` (walk records `applied`). Every other outcome →
  `apply_skip=True` (walk records `skip`). **The genuine-noop "resolved" paths
  count as terminal-applied for `apply_skip` purposes** (leave it False): reground
  `noop` (plan already fully done) and file-check "already declared"/"moved".
- **halts on applied?** — merge: always; escalation: only when `halt_on_applied`
  (the completeness-apply lane); reground: never. When set, the kernel sets
  `state.halt_requested = True` **and** `state.halt_apply_landed = True`.
- **records the finding id as applied?** — reground + merge add `rec.id` to
  `state.applied_structural_finding_ids` (feeds their session short-circuit);
  escalation + file-check do not.
- **refreshes drift baseline?** — escalation only, and only in the reconcile lane
  (guarded by `reconcile_scope_guard.iter_lock`); the kernel must take the guard
  and no-op when absent. Do **not** generalize to merge/reground.

## Genuine per-dispatcher differences the kernel must NOT flatten (from the map)

| Aspect | escalation | reground | merge | file-check |
|---|---|---|---|---|
| Bridge | `escalate_to_split` | `reground_bridge` | `merge_bridge` | inline `parse_plan`/`write_plan` |
| Opt-in token | `allow_split` | `allow_structural_remedy` | `allow_structural_remedy` | none (interactive c/f) |
| Confirm seam | `prompt_fn=None` | `yes=False` | `yes=False` | `builtins.input` |
| Target ids | `rec.step_id` | `directive.step_ids` | `directive.step_ids` | `rec.step_id` + path |
| Pre-gate guard | `rec.step_id is None` | kind==REGROUND | kind==MERGE | `path is None` |
| Staleness guard | NO | YES (`_saved_directive_is_stale`) | YES | NO |
| Session short-circuit | NO | YES | YES | NO |
| `applied_structural_finding_ids.add` | NO | YES | YES | NO |
| Halt on applied | only `halt_on_applied` | NO | ALWAYS | NO |
| Drift `refresh_snapshot` | YES (reconcile only) | NO | NO | NO |
| `yes_to_all` | force recommend-only | force recommend-only | force recommend-only | **force auto-apply (create)** |

## Resolved design decisions

1. **Characterization tests FIRST — this is the non-negotiable spine of a
   behavior-preserving refactor.** Before touching production code, pin the
   *current* observable behavior of each dispatcher across **every** outcome:
   the returned status string (or a stable substring), and the exact post-call
   `WalkState` (`apply_skip`, `halt_requested`, `halt_apply_landed`,
   `applied_structural_finding_ids`), plus the drift `refresh_snapshot` call for
   escalation-applied-in-reconcile-lane. The existing suites
   (`tests/cli/test_review_actions.py` classes `TestStructuralEscalation`,
   `TestRegroundRemedyDispatch`, `TestMergeRemedyDispatch`,
   `TestSplitEscalationDispatch`, and the file-check tests) are the base; fill any
   gaps (e.g. escalation had **no** `apply_skip` assertions until `23e1685`). Only
   once the matrix is green does the extraction begin; the same tests must stay
   green **unchanged** through it (green→refactor→green).

2. **Scope: the three bridge dispatchers are the core; file-check joins only the
   kernel, not the gate.** `_dispatch_file_check_create` routes its outcomes
   through the **shared outcome kernel** (it benefits from the single-sourced
   `apply_skip` tail) but keeps its own interactive `input` flow and its inverted
   `yes_to_all` auto-apply — it does **not** use the shared bridge gate helper. If
   even the kernel doesn't fit file-check cleanly, leave it out with a one-line
   rationale rather than contorting the kernel; the three bridge dispatchers are
   where the divergence bug lives.

3. **Behavior-preserving means byte-identical outcomes, not "close enough."**
   Preserve exactly (the map's must-preserve list): the BLOCKED-STRUCTURAL
   reconcile-lane path (`_dispatch_apply_finding` → escalation with
   `halt_on_applied=False`, and its `applied` drift refresh must still fire); the
   escalation-only, reconcile-only drift refresh; merge-always / reground-never /
   escalation-conditional halt; the staleness guard running **after** the session
   short-circuit and **before** the bridge; the `rec.step_id is None` plan-level
   branch; file-check's `yes_to_all`-auto-applies; and the two separate opt-in
   tokens (`allow_split` ≠ `allow_structural_remedy`).

4. **No new capability, no scope creep.** This plan does not add per-remedy
   `--merge`/`--reground` flags, does not touch the coarse-fingerprint staleness
   design (that's BACKLOG #93), does not add the reground re-baseline arm, and
   does not change any user-facing behavior or exit code. If the refactor tempts a
   behavior change ("this outcome should really set halt"), that is a **separate**
   finding for the backlog, not part of the consolidation.

5. **Keep the kernel a cycle-free leaf.** It reads/writes `WalkState` and takes a
   plain descriptor; it must not import orchestrators. It can live as a small
   module-level helper (or a helper on `WalkState`) that the nested dispatchers
   call, so it is unit-testable in isolation without building the whole action fn.

## Deferred (out of scope — file to BACKLOG #70 as they surface)

- **The other #70 follow-ups** — per-remedy `--merge`/`--reground` walk flags,
  re-ground's human-authored `create --from-existing` re-baseline arm, the
  multi-step/region carve, and the code-reveals-a-split reconcile producer.
- **Precise per-step-id staleness (#93)** — this refactor preserves the current
  coarse whole-plan `_saved_directive_is_stale()` guard as-is; replacing it is #93.
- **Any behavior change** surfaced while refactoring (a dispatcher that "should"
  halt/refresh/short-circuit but doesn't) → a backlog finding, not this plan.

## Acceptance criteria (plan-level)

- The `apply_skip`/halt/`applied_structural_finding_ids`/drift-refresh side-effect
  tail is written **once** in a shared outcome kernel; the three bridge
  dispatchers (and, if clean, file-check) route their outcomes through it, and no
  dispatcher hand-rolls `state.apply_skip = True` per-outcome anymore.
- A shared gate helper single-sources `allow = <token> and not state.yes_to_all`
  for the three bridge dispatchers; file-check is deliberately excluded.
- **Every** current behavior is preserved: a characterization-test matrix over all
  outcomes of all dispatchers (status string + post-call `WalkState` + escalation's
  reconcile-lane drift refresh) is authored **before** the extraction and passes
  **unchanged** after it. The full suite stays green.
- The consolidation makes the `5d4fe1b` bug class unreachable by construction: an
  outcome is classified as applied/non-applied in one place, so a new remedy that
  reuses the kernel cannot record a non-applied outcome as `applied`. Add a test
  asserting the kernel sets `apply_skip=True` for a non-terminal outcome and
  leaves it `False` for a terminal-applied one.
- No user-facing behavior, message text (beyond incidental wording the tests
  pin), or exit code changes; the two opt-in tokens stay distinct; the
  BLOCKED-STRUCTURAL reconcile path and per-lane halt/refresh semantics are
  byte-identical.
- `BACKLOG.md` #70 reconciled (strike the dispatcher-consolidation follow-up, note
  the ship date); if the shared kernel is worth citing, add a one-line pointer in
  the CLAUDE.md "Escalate-to-split bridge" / structural-remedy paragraph.

## Tests (where coverage lands)

- `tests/cli/test_review_actions.py` — the characterization matrix (extend the
  existing dispatch classes; assert post-call `WalkState`, not just the return
  string) and a direct unit test of the extracted kernel.
- Seam discipline: stub the bridges (`escalate_to_split`, `reground_bridge`,
  `merge_bridge`) and `builtins.input`; the conftest autouse gate must not see a
  real backend spawn.
