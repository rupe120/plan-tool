> **Auto-archived**: this plan was swept on 2026-07-08 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Reconcile BACKLOG #70's dispatcher-consolidation follow-up and point CLAUDE.md at the shared outcome kernel

## Summary

This is a **non-code, docs-only** step. It closes the loop on the consolidation the plan ships: strike the "consolidate the apply-or-recommend dispatchers into one shape" follow-up from BACKLOG #70 (with a 2026-07-08 ship note), and add a one-line pointer in `CLAUDE.md` so the escalate-to-split bridge paragraph names the shared kernel (`apply_structural_outcome` / `StructuralOutcomeEffects`) and gate helper (`structural_apply_allowed`) that steps 2 and 3 land in `plan_tool/review_walk.py`. The key call: touch only the one #70 follow-up clause and the one CLAUDE.md paragraph — leave the sibling #70 arms and the "Structural remedy vocabulary" bullets alone. On green, `#70` no longer lists dispatcher consolidation as pending work, and a reader of CLAUDE.md's bridge paragraph learns the four dispatchers now single-source their `WalkState` tail.

## Table of Contents

- [Why](#why) — why the backlog and doc must catch up now
- [Input](#input) — the step-2/3 symbols this pointer names
- [Files (creates vs edits)](#files-creates-vs-edits) — the two docs this step edits
- [Implementation](#implementation) — the exact clause to strike and the pointer to add
- [Verification (non-code step)](#verification-non-code-step) — how to confirm the edits are correct and grounded
- [Acceptance criteria](#acceptance-criteria) — observable checks a reviewer can run
- [References](#references) — the backlog reconciliation discipline
- [Deferred](#deferred) — the #70 arms this step leaves open

## Why

The plan's real work (steps 2–3) removes the divergence surface that fix `5d4fe1b` patched. Once that ships, two docs are stale: BACKLOG #70's *Remaining follow-ups* still lists "consolidating the … dispatchers … into one shape" as open convenience work, and CLAUDE.md's escalate-to-split bridge paragraph still describes each dispatcher hand-rolling its own `WalkState` tail with no mention of the shared kernel. Leaving the backlog stale re-surfaces already-shipped work in the next planning sweep; leaving CLAUDE.md silent hides the single reviewable place the tail now lives, so a future editor could reintroduce an inline hand-set line. This step makes both docs match the shipped code.

## Input

This step's CLAUDE.md pointer names symbols that **steps 2 and 3 own** — cite them, do not restate how they work:

- **Step 2 produces** the shared outcome kernel `apply_structural_outcome` + the frozen descriptor `StructuralOutcomeEffects` in `plan_tool/review_walk.py`, routing all four structural dispatchers' `WalkState` side-effect tail (`apply_skip`, `halt_requested`, `halt_apply_landed`, `applied_structural_finding_ids`) through it. Escalation's drift `refresh_snapshot` stays inline in `_dispatch_structural_escalation`.
- **Step 3 produces** the shared gate helper `structural_apply_allowed` in `plan_tool/review_walk.py`, single-sourcing `allow = <opt-in token> and not state.yes_to_all` for the three bridge dispatchers; `_dispatch_file_check_create` is deliberately excluded (it inverts the rule).

If either symbol name changes during step 2/3 implementation, use the name that actually lands — the pointer's job is to name the real single-source location, not a guessed identifier.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `BACKLOG.md` — under **#70 → Auto-bridges → Remaining follow-ups (convenience)**, remove the "consolidating the … apply-or-recommend dispatchers … into one shape" clause and add a short 2026-07-08 ship note. Leave every sibling arm and the #70 Effort/Approach/Origin lines intact.
  - `CLAUDE.md` — add a one-line pointer in the **"Escalate-to-split bridge (`launcher.py:escalate_to_split`)"** paragraph naming the shared kernel and gate helper in `plan_tool/review_walk.py`.

## Implementation

**Foundational change:** make two human-facing docs describe the post-consolidation forward state. No production code, schema, or CLI surface changes.

### BACKLOG.md — strike one follow-up clause, add a ship note

- **Target the exact clause, not the entry.** In `BACKLOG.md`, the `#70 — Structural-remedy vocabulary: remaining convenience arms` entry has an **Auto-bridges** bullet whose `**Remaining follow-ups (convenience):**` line enumerates three arms: per-remedy `--merge`/`--reground` walk flags; consolidating the apply-or-recommend dispatchers (naming `_dispatch_structural_escalation`, `_dispatch_file_check_create`, `_dispatch_reground_remedy`/`_dispatch_merge_remedy`) into one shape; and re-ground's `create --from-existing` re-baseline arm. **Remove only the dispatcher-consolidation clause** (including its parenthetical list of the four dispatcher names) and keep the other two arms exactly as they read.
- **Add a ship note in the adjacent style.** Match the existing `**SHIPPED (scope-out + re-ground + merge)**` / `**SHIPPED (2026-07-08)**` shape already used inside this same entry (the Auto-bridges "SHIPPED" note and the Completeness-apply split bridge note). One line naming what shipped and the date (2026-07-08) — e.g. that the four structural dispatchers' shared `WalkState` side-effect tail and the three bridges' apply-or-recommend gate are now single-sourced in `plan_tool/review_walk.py`. Do not convert the whole #70 entry to shipped; only this arm closed.
- **Sweep before editing.** Grep `#70`, the four dispatcher symbol names, and the phrase "into one shape" / "consolidat" across `BACKLOG.md` (and `BUG_BACKLOG.md`) so no sibling reference still frames dispatcher consolidation as pending. The `#70` id itself stays live because the other arms remain open — do **not** delete the entry or its Origin/Effort/Approach lines.

### CLAUDE.md — add the shared-kernel pointer

- **Home the pointer in the bridge paragraph.** Add the pointer to the `**Escalate-to-split bridge (`launcher.py:escalate_to_split`)**` paragraph, which already names `_dispatch_structural_escalation` and enumerates the callers. One sentence: the four structural dispatchers built by `plan_tool/cli/review_actions.py`'s `_build_review_action_fn` now single-source their `WalkState` side-effect tail through step 2's `apply_structural_outcome` / `StructuralOutcomeEffects` in `plan_tool/review_walk.py`, and the three bridge dispatchers share step 3's `structural_apply_allowed` gate there (file-check stays out of the gate, since it inverts the `yes_to_all` rule; escalation's drift `refresh_snapshot` stays inline).
- **Do not touch the "Structural remedy vocabulary" re-split bullet.** That bullet names `granularity-split → escalate_to_split` at the vocabulary altitude and is deliberately caller-agnostic. Adding a kernel-location note there would drift the two altitudes apart. Update the bridge paragraph only.
- **Keep the existing caller count honest.** The bridge paragraph currently reads "Three callers wire it" — this step adds no caller, so **do not** change that count. The pointer is about where the shared tail/gate live, not a new caller.
- **Terse, one line.** Per CLAUDE.md's own "Code comments" rule and the file's density, the pointer is a single clause pointing at the single-source location, not a paragraph restating the kernel's four-dimension map (that lives in the plan and the step-2 detail).

**Constraint that must hold:** the CLAUDE.md pointer must name the symbols that steps 2 and 3 actually create. Because this step `depends_on: 2, 3`, confirm the symbol names in `plan_tool/review_walk.py` at implementation time before writing the sentence — a pointer to a non-existent symbol reads as drift on the next reconcile.

## Verification (non-code step)

This step changes no production code — verify the artifacts, not unit tests.

- **BACKLOG grep:** after the edit, `grep -n "into one shape\|consolidat" BACKLOG.md` returns no line framing dispatcher consolidation as a pending #70 follow-up; the two sibling arms (`--merge`/`--reground` walk flags, re-ground re-baseline) still appear.
- **#70 integrity:** `grep -n "#70" BACKLOG.md` still shows the entry heading, Origin, Effort, and Approach lines — the entry was not deleted, only one arm closed.
- **CLAUDE.md symbol accuracy:** the symbol names in the new pointer (`apply_structural_outcome`, `StructuralOutcomeEffects`, `structural_apply_allowed`) exist in `plan_tool/review_walk.py` at HEAD after steps 2–3 land — `grep -n` each in that file returns a definition.
- **CLAUDE.md caller count unchanged:** the bridge paragraph still reads "Three callers wire it" (this step adds no caller).
- **No sibling drift:** the "Structural remedy vocabulary" re-split bullet is untouched.

## Acceptance criteria

- `BACKLOG.md` #70's *Remaining follow-ups (convenience)* line no longer lists dispatcher consolidation, and carries a 2026-07-08 ship note in the entry's existing SHIPPED style.
- The other two #70 Auto-bridges follow-ups (per-remedy `--merge`/`--reground` walk flags; re-ground `create --from-existing` re-baseline arm) and the #70 Origin/Effort/Approach lines are unchanged.
- `CLAUDE.md`'s escalate-to-split bridge paragraph contains a one-line pointer naming `apply_structural_outcome`/`StructuralOutcomeEffects` and `structural_apply_allowed` in `plan_tool/review_walk.py` as the single source for the four dispatchers' tail and the three bridges' gate.
- The named symbols exist in `plan_tool/review_walk.py` at HEAD.
- The CLAUDE.md caller count and the "Structural remedy vocabulary" re-split bullet are unchanged.
- No production code, test, or schema file changes in this step.

## References

- `docs/implementation-plans/plan-details/structural-dispatcher-consolidation/02-extract-shared-outcome-application.md` — step 2's detail; source of the `apply_structural_outcome`/`StructuralOutcomeEffects` names this step's CLAUDE.md pointer cites.
- `docs/implementation-plans/plan-details/structural-dispatcher-consolidation/03-shared-gate-helper-three-bridge.md` — step 3's detail; source of the `structural_apply_allowed` gate name this step's pointer cites.
- `plan_tool/review_walk.py` — the single-source location for the shared kernel and gate helper the pointer names; confirm the symbol names here at HEAD before writing the sentence.

## Deferred

- **The other #70 Auto-bridges follow-ups** — per-remedy `--merge`/`--reground` walk flags and re-ground's human-authored `create --from-existing` re-baseline arm stay open in #70; this step only closes the dispatcher-consolidation arm.
- **The remaining #70 arms** — multi-step/multi-region carve and the code-reveals-a-split reconcile producer stay open in #70.
- **Precise per-step-id staleness (#93)** — untouched; this plan preserved the coarse whole-plan `_saved_directive_is_stale()` guard.
- **The kernel and gate helper themselves** — authored by steps 2 and 3; this step only points at them.

## Tests

No unit tests apply — this is a docs-only, non-code step touching only `BACKLOG.md` and `CLAUDE.md`, with no production code, schema, or CLI surface to exercise. Confirm the edits via the doc-checks in [## Verification (non-code step)](#verification-non-code-step): the BACKLOG grep, #70 integrity check, CLAUDE.md symbol-accuracy grep against `plan_tool/review_walk.py`, the unchanged "Three callers wire it" count, and the untouched "Structural remedy vocabulary" re-split bullet. The full suite must still pass unchanged, since this step edits no code.

