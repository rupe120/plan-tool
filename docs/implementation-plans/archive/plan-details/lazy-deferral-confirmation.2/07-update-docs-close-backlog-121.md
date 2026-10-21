> **Auto-archived**: this plan was swept on 2026-07-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 7 — Update BACKLOG.md, CLAUDE.md, and DATA_CONTRACT.md to close #121 and reconcile the lazy-deferral disposition

## Summary

Close out the plan's docs and bookkeeping once steps 1–6 ship the flat decision-record lazy model. `BACKLOG.md`'s `#121` disposition is flipped from "lazy is the forward direction / parked" to **shipped** (naming `docs/implementation-plans/2-lazy-deferral-confirmation.md`), the deferred-residue entries (`#126–#128` moot-for-lazy, `#130` sub-concept drill, `#131` legacy migration, `#132` dismiss verb, `#129` monitoring) are confirmed to still stand, `CLAUDE.md`'s "Concept sign-off and ownership" paragraph is rewritten to describe lazy materialization (a `concepts.json` record only when a plan defers something; un-deferred plans get none; a deferral is a flat decision record that is **not** fingerprint-validated; validity is bucket-existence; surfaced non-blocking), and `DATA_CONTRACT.md` documents the flat decision-record shape beside the legacy full-tree record. The key rule: verify each claim against the shipped code + tests at HEAD before writing it — `depends_on` says steps 1–6 ran, not that their guarantees hold — and route any gap back to the owning step rather than describing unshipped behavior as shipped.

## Table of Contents

- [Summary](#summary) — what the step does and its one hard rule
- [Why](#why) — why the docs go stale the moment steps 1–6 land
- [Input](#input) — the shipped outcomes and drift-guard contract this step consumes
- [Files (creates vs edits)](#files-creates-vs-edits) — the three docs touched
- [Implementation](#implementation) — the backlog tense flip, the CLAUDE.md rewrite, the DATA_CONTRACT addition
- [Tests](#tests) — verification appropriate to a docs step
- [Acceptance criteria](#acceptance-criteria) — checkable observable state
- [Deferred](#deferred) — doc surfaces left to other owners

## Why

This is the seed's mandated closure ("its final docs/status step must update `BACKLOG.md`"). Steps 1–6 change how concept deferrals are recorded, validated, surfaced, and confirmed, but the project docs still describe the eager, fingerprint-validated tree. `CLAUDE.md`'s concept paragraph says create "records operator-approved owners" and treats the whole hierarchical machinery as current — both now wrong on the lazy path. `BACKLOG.md`'s `#121` frames lazy-deferral as the forward direction to build and points at seeds `create` has since archived — a stale tense and a dead reference. `DATA_CONTRACT.md` documents only the legacy record shape, so a future author has no description of the flat decision record. Left unreconciled, the docs read as if the eager machinery is still the design.

## Input

- **Steps 1–6 outcomes** (verify at HEAD, do not assume): step 1 — a flat decision-record kind loads without the `plan_fingerprint` guard; step 2 — `create -y` records only pending deferrals and writes no record for an un-deferred plan; step 3 — `check_concept_coverage` is total and surfaces a missing-bucket record; step 4 — `scope-review` confirms a flat record after unrelated edits and can resolve a missing-bucket record; step 5 — the three non-blocking surfaces name the bare `node.id`; step 6 — detail records a flat pending decision on a record-absent plan.
- **Drift-guard contract** (`tests/test_data_contract.py`): section-scoped tests assert documented fields match the runtime dataclasses. Add the flat-record fields as prose or a table consistent with the existing Concept-sidecar section; run the suite after editing.
- **BACKLOG entry state at HEAD**: `#121`'s disposition bullets (the "Altitude reframe (2026-07-15)" / "parked" language), and the residue entries `#126`–`#132` — the regions carrying "forward direction" / "parked" / "deferred" language for lazy-deferral.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `BACKLOG.md` — flip `#121` to shipped (name the plan file); confirm `#126`–`#128` stay moot-for-lazy, and `#129`/`#130`/`#131`/`#132` stay open with their deferred residue intact; sweep for any other stale `lazy-deferral` future-tense reference.
  - `CLAUDE.md` — rewrite the "Concept sign-off and ownership" paragraph to describe lazy materialization (flat decision record, not fingerprint-validated, bucket-existence validity, surfaced non-blocking, un-deferred plans record-absent). State the forward invariant, no "previously eager…" narration.
  - `DATA_CONTRACT.md` — document the flat decision record `{bucket, title, rationale, decision (defer|wont_do), review_state}` beside the legacy full-tree record, noting it skips the `plan_fingerprint` guard.

## Implementation

- **Verify before writing (the one hard ordering).** Before editing any doc, confirm each claim at HEAD: the flat record loads without a staleness raise, `scope-review` resolves a missing-bucket record, the surfaces name the bare id, an un-deferred `create -y` writes no record. If any check fails, the gap belongs to the owning step — stop and route it there rather than describing unshipped behavior as shipped.
- **BACKLOG.md — the tense flip.** `#121`: state the lazy-deferral MVP shipped via `docs/implementation-plans/2-concept-write-integrity.md`… (name `2-lazy-deferral-confirmation.md`); keep the supersession-of-eager-hardening note. Confirm `#126`–`#128` remain moot-for-lazy (not retired), and `#129`/`#130`/`#131`/`#132` remain open. Do not retire any residue entry — this step reconciles language, it retires nothing but `#121`.
- **CLAUDE.md — the paragraph rewrite.** Replace the eager description with the lazy invariant, in prose: a `concepts.json` record exists only when a plan defers something; a deferral is a flat decision record that is not validated against plan text (so it survives unrelated edits); its only validity check is whether its `bucket` still exists; pending deferrals are surfaced non-blocking in `status` / the completeness report / a `create` run-summary and confirmed via `scope-review`. Keep the shipped hierarchical machinery described as dormant, not removed.
- **DATA_CONTRACT.md — the record shape.** Document the flat decision record and the record-kind branch that keeps the legacy full-tree record loadable, matching the existing section's voice; prefer prose over new field-tables if that keeps the drift guard green, and run `tests/test_data_contract.py` either way.
- **Parts that must not vary:** docs state the forward invariant, not history (git owns "previously eager"); `#126`–`#132` stay open; every symbol/path cited is copied from HEAD, not from this plan.

## Tests

### Verification (non-code step)

- `uv run pytest tests/test_data_contract.py -q` — green after the DATA_CONTRACT edit.
- `grep -n "lazy-deferral" BACKLOG.md` — every hit reads as shipped / open-deferred; no "forward direction" / "parked" future tense remains on `#121`.
- `grep -rn "emit_concept_tree" plan_tool/create.py` — returns nothing on the create path (confirms the lazy claim before documenting it).
- Path check — every file path cited in the new prose exists at HEAD.

## Acceptance criteria

- `BACKLOG.md` `#121` reads as shipped and names `docs/implementation-plans/2-lazy-deferral-confirmation.md`; `#126`–`#132` remain open with their deferred residue intact.
- `CLAUDE.md`'s concept paragraph describes the flat, not-fingerprint-validated decision record, bucket-existence validity, and the non-blocking surfaces — with no eager-machinery language presented as current.
- `DATA_CONTRACT.md` documents the flat decision-record shape beside the legacy record; `uv run pytest tests/test_data_contract.py -q` passes.
- No claim in the docs describes behavior steps 1–6 did not actually ship (verified by the greps above).

## Deferred

- Retiring `#126`–`#132` — their residue is untouched by this plan; this step only reconciles language.
- CAPABILITIES.md / RUNBOOK.md touch-ups — outside this step's declared file list; the plan ships no new command or schema surface requiring a catalog entry.
- Documenting the sub-concept drill / migration / dismiss designs — owned by `#130`/`#131`/`#132`.
