> **Auto-archived**: this plan was swept on 2026-07-08 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Reconcile BACKLOG #93 to shipped

## Summary

Removes BACKLOG **#93** — the `[Investigation]` entry that asked for the precise per-step-id staleness check — now that steps 2–4 built it. The only file touched is `BACKLOG.md`. Three edits: delete the `#93 — [Investigation] Precise per-step-id re-ground staleness check …` entry, drop its `#93` clause from the Quality/accuracy lens `audit-coverage` roll-up, and confirm the `#70` Auto-bridges note's "stale-saved-directive guard" wording still reads true (it does — the guard is now precise, not coarse). Because this is a docs-only reconcile that depends on the code from steps 2–4, the implementer first verifies the shipped symbols exist at HEAD; if they don't, stop and route back to the owning step rather than editing code here. On green, `grep -n "#93" BACKLOG.md` returns nothing and the roll-up + `#70` note carry no stale framing of the guard as over-firing.

## Table of Contents

- [Why](#why) — why #93 is resolved and must leave the active backlog
- [Input](#input) — the shipped code from steps 2–4 and the BACKLOG.md structure this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — the one file and its three edits
- [Implementation](#implementation) — what to remove, what to check, and what to leave alone
- [Tests](#tests) — verification for a non-code step
- [Acceptance criteria](#acceptance-criteria) — observable results on green
- [Deferred](#deferred) — the convergence generalization and everything this step does not do

## Why

`BACKLOG.md`'s own rule is **"Remove a feature's entry when it ships"** — the file is forward-looking work only, and shipped items move to git history, the plan file, and `LESSONS_LEARNED.md`. #93 asked for a precise per-directive staleness check to replace the coarse whole-plan fingerprint guard; steps 1–4 of this plan built exactly that (the `target_signature` field, the stamp pass, the rewritten `_saved_directive_is_stale`, and the split-escalation guard). With the work shipped there is no residual forward-looking task in #93's core, so the entry now misleads anyone triaging the backlog into thinking the guard is still coarse. This step retires it and sweeps the one roll-up cross-reference so the backlog stays honest.

## Input

- **Steps 2–4 produce the shipped behavior this step attests to.** Step 2 stamps `target_signature` before every `save_review` (`plan_tool/review_walk.py:stamp_target_signatures`), step 3 rewrites `_saved_directive_is_stale(rec)` (`plan_tool/cli/review_actions.py`) to a per-directive check, and step 4 guards the `granularity-split` escalation with the same check. This step **reads** that those landed; it changes no code.
- **The `BACKLOG.md` entry contract.** The `#93 — [Investigation] …` entry is a single block from its bold heading through its `- **Origin:**` line. Removing it means deleting the whole block plus the blank line separating it from the next entry (`#87`), leaving `#87` and `#71` intact.
- **The Quality/accuracy lens roll-up.** The `audit-coverage:` facet bullet lists three members — `#66`, `#100`, and `#93` — with `#93` as the trailing clause ending `… staleness check).`. Dropping `#93` means the bullet ends on the `#100` clause (`… complement to #66).`), with comma/period punctuation repaired.
- **The `#70` Auto-bridges note.** The `#70 — Structural-remedy vocabulary: remaining convenience arms` entry's Auto-bridges bullet mentions "a stale-saved-directive guard so a renumbered plan can't fold the wrong steps." This is the guard #93 made precise; the sentence stays true and needs no #93 back-reference (it never carried one).

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `BACKLOG.md` — three edits:
    1. **Delete** the `#93 — [Investigation] Precise per-step-id re-ground staleness check (replace the coarse whole-plan fingerprint guard)` entry in full (heading through its `- **Origin:**` line, plus the trailing blank line before `#87`).
    2. **Drop** the `#93` clause from the `audit-coverage:` facet bullet in the Quality/accuracy lens roll-up (`**Current quality/accuracy-impacting items** …`), repairing the punctuation so the bullet ends cleanly on the `#100` clause.
    3. **Confirm** the `#70` Auto-bridges note's "stale-saved-directive guard" wording is not stale; edit only if it still frames the guard as coarse or over-firing (it does not today, so this is expected to be a no-op verification).

## Implementation

- **This is a non-code, docs-only reconcile — change no production code.** If verifying the shipped symbols surfaces a gap (a symbol missing, the guard still coarse), **stop and route it back to the owning step (2, 3, or 4)** — do not patch code here. A docs step's job is to make already-shipped behavior legible, not to finish it.

- **Verify the dependency first, then remove.** Before deleting #93, confirm the precise guard actually shipped at HEAD:
  - `Recommendation.target_signature` exists on the frozen dataclass in `plan_tool/review.py`.
  - `compute_target_signature` and `stamp_target_signatures` exist in `plan_tool/review_walk.py`.
  - `_saved_directive_is_stale` in `plan_tool/cli/review_actions.py` takes a `rec` and compares a per-directive signature (no longer a no-argument whole-plan-fingerprint closure).
  - One way: `grep -n "target_signature" plan_tool/review.py plan_tool/review_walk.py` and read the `_saved_directive_is_stale` signature. If all three hold, the entry is safe to retire.

- **Remove the whole #93 entry — don't mark it shipped in place.** `BACKLOG.md` retires shipped items by deletion (its "Remove a feature's entry when it ships" rule), unlike the `#70` entry which keeps `SHIPPED` notes because it still has live arms. #93's core has no residual live arm (the convergence generalization is a separate contract — see Deferred), so the entry leaves the backlog entirely.

- **Sweep the one live cross-reference.** After deleting the entry, `grep -n "#93" BACKLOG.md` must return nothing. The only external live reference is the `audit-coverage:` roll-up clause — drop it and fix the surrounding comma/period so the facet still lists `#66` and `#100` correctly. Leave `#66` and `#100` untouched.

- **Do not over-sweep #70 or adjacent facets.** The `#70` entry is multi-arm; touch only the guard-framing check described above and change nothing else in it. In the roll-up, the `#93` clause is the only member to remove from `audit-coverage` — the `grounding`, `convergence`, `gate-signal`, and `heuristic-tuning` facets and their members are out of scope.

- **Ignore archived copies.** `#93` also appears under `plan-seeds/archive/` and `docs/implementation-plans/archive/` (e.g. `docs/implementation-plans/archive/2-completeness-apply-split-bridge.md`, `docs/implementation-plans/archive/2-structural-dispatcher-consolidation.md`). Those are historical artifacts, are not in this step's `files:` list, and must not be edited — the deferral-to-#93 language they carry was true when written.

- **Foundational logic and where it recurs.** The core action is "retire a shipped BACKLOG entry and repair its live cross-references." The same pattern was exercised by the two prior `#70`-arm reconcile steps (`docs/implementation-plans/archive/plan-details/structural-dispatcher-consolidation/04-reconcile-backlog-70-claude-md-pointer.md` and the earlier completeness-apply-split-bridge reconcile). Those retired a single *arm* of #70 with a `SHIPPED` note because #70 stays live; this step differs by removing an entire entry, matching the backlog's remove-on-ship rule for a fully-resolved investigation. No consolidation is needed — the reconcile lives in one file.

## Tests

### Verification (non-code step)

This step changes no production code. Verify the reconcile against the file itself, not with unit tests:

- **#93 entry gone** — `grep -n "#93" BACKLOG.md` returns no matches.
- **Roll-up repaired** — the `audit-coverage:` facet bullet lists `#66` and `#100` only, with valid comma/period punctuation and no dangling clause.
- **#70 note intact** — the `#70 — Structural-remedy vocabulary: remaining convenience arms` entry still has all its arms; the "stale-saved-directive guard" sentence reads true (guard is precise) and carries no stale over-fire framing.
- **Neighbors intact** — `#87` and `#71` entries are unchanged and correctly separated after the deletion.
- **Shipped symbols present** — the step 2–4 symbols listed in Implementation exist at HEAD (spot-checked before removal), so the removal is justified.
- **Full suite still green** — `uv run pytest tests/ -q` passes (no doc-content assertions should reference #93; confirm none break).

## Acceptance criteria

- `grep -n "#93" BACKLOG.md` returns nothing.
- The `#93 — [Investigation] Precise per-step-id re-ground staleness check …` entry no longer appears above `#87` in the backlog.
- The Quality/accuracy lens `audit-coverage:` facet bullet lists exactly `#66` and `#100`, punctuation clean.
- The `#70` entry retains its arms and its Auto-bridges "stale-saved-directive guard" wording; no #93 back-reference is left dangling.
- `#87` and `#71` entries are byte-for-byte what they were except for the blank-line boundary left by the deletion.
- No production `plan_tool/` file is modified by this step.

## Deferred

- **The convergence-path generalization** (`plan_tool/cli/convergence_cmd.py:classify_report_staleness`) — a separate staleness contract keyed on convergence-history `plan_fingerprint` and a single `rec.step_focus` target, not the shared review-sidecar guard #93 named. The plan's Out-of-scope/Deferred already records it as a possible future generalization; this step files no new backlog entry for it, matching the plan's decision to leave it noted rather than tracked.
- **Any code change to the guard, stamp pass, or field** — owned by steps 1–4; if verification finds a gap, route it back there, don't fix it here.
- **Archived `#93` mentions** under `plan-seeds/archive/` and `docs/implementation-plans/archive/` — historical, out of this step's file scope, left untouched.
