> **Replaced**: this file has been superseded by `docs/implementation-plans/2-concept-write-integrity.md`.
> Preserved here for history; do not edit.

# Plan seed: concept write integrity — the distilled remediation fixes

This file is a `plan-tool create` input. Use it via:

    plan-tool create concept-write-integrity --from-existing plan-seeds/concept-write-integrity.md --iterate

> **Scope boundary — this seed fixes the concrete data-loss and divergence bugs in the
> shipped concept sign-off machinery, nothing more.** It is the deliberate distillation of
> the six archived concept-remediation plans (2026-07-13): the ~46-step hardening program
> was cut to the handful of findings whose failure modes are real today. It does **not**
> build a publication-transaction authority, rollback journal, recovery command, repo
> lock, non-delivery ledger, or seed accounting envelope — those designs are preserved
> under `docs/implementation-plans/archive/` and tracked as BACKLOG **#126**, **#127**,
> and **#128**. Expected decomposition: **~6–8 steps**; if convergence pressure pushes it
> past that, defer to the backlog entries rather than growing this plan.

Source: reconcile audit `0129c29` on the shipped BACKLOG #121 integrations, distilled from
the archived plans `2-concept-remediation-1-publication-transactions.md` (findings 1–2)
and `2-concept-remediation-2-authoring-boundary-hardening.md` (findings 3–4). When this
work ships, its final docs/status step must update `BACKLOG.md`: note under #121's
follow-up disposition that the write-integrity fixes shipped, and adjust #126/#127/#128
if any of their residue was absorbed here.

---

## Overview

The shipped concept machinery (`concepts.json` record, three-state sign-off,
`scope-review`, `Step.concept_ids` ownership, `concept-coverage` enforcement) is
functionally complete, but its **write paths** have four integrity gaps: a failed create
can strand an archived collision plan; three production call sites bypass the canonical
synchronizer and write the concept sidecar directly, letting plan prose and the concept
record diverge; detail replacement destroys the active detail body before the replacement
is validated; and invalid model-emitted concept output can mutate the tree instead of
failing soft. Fix exactly those four, plus the docs/backlog reconciliation.

## Problem statement — grounded

1. **Create collision-archive ordering.** `create_plan()` archives a colliding plan
   (collision replacement, `plan_tool/create.py:5393` `_decide_replace_collisions` and the
   archival path near `create.py:4498`/`:5369`) *before* concept synchronization succeeds,
   and a later failure deletes the new plan without restoring the archived original. The
   archive move must happen only after publication succeeds — or be restored on failure.

2. **Three writers bypass the canonical synchronizer.** `concept_sync.synchronize_concepts()`
   is the designed single writer keeping plan prose, rendered scope, and the concept
   record aligned, but:
   - unsigned create falls back to a direct `save_concepts` (`plan_tool/create.py:6276`,
     `:7021`) because the synchronizer erases unsigned scope prose;
   - `detail` persists deferral updates directly (`plan_tool/detail.py:4234`);
   - `apply_narrow` saves its carved sidecar directly (`plan_tool/scope_out.py:896-901`).

   Extend `synchronize_concepts()` to handle unsigned scope state, then route all of these
   through it so no production code path outside `concept_sync` writes `concepts.json`.
   Guard the invariant with a test asserting no production `save_concepts` caller outside
   `concept_sync.py`.

3. **Detail replacement safety.** `_archive_existing_detail()` (`plan_tool/detail.py:5335`,
   called at `:4402`/`:4745`/`:5047` and `:2156`) moves the active detail file away before
   the replacement body is known-good. Validate the replacement first (the existing
   seven-section gate) and restore the prior body when the write fails, so an interrupted
   or rejected regeneration never leaves a step with no detail.

4. **Fail-soft concept parse.** `_parse_emitted_concepts()` (`plan_tool/concept_tree.py:281`)
   accepts a concept whose `evidence_rationale` merely contains a literal excerpt without
   provenance-checking the cited evidence, and an unpaired surrogate in emitted output can
   crash ID derivation outside the fail-soft boundary. Invalid or mismatched emitted
   concept output must leave the input tree **byte-for-byte unchanged** and report the
   rejection; malformed text must never escape as an exception mid-mutation.

5. **Docs + backlog reconciliation.** Update the concept-workflow docs the fixes touch
   (`RUNBOOK.md` / `DATA_CONTRACT.md` as applicable — the single-writer invariant belongs
   in `DATA_CONTRACT.md`'s concepts section) and perform the `BACKLOG.md` bookkeeping
   named in the Source note above.

## Constraints

- **No new modules, commands, or schemas.** Every fix lands inside the existing
  `concept_sync.py` / `concept_tree.py` / `create.py` / `detail.py` / `scope_out.py`
  surfaces. If a fix appears to need new machinery, that is the signal it belongs to
  #126/#127/#128 instead.
- **Recovery model stays git + fingerprint.** A stale `plan_fingerprint` reads as
  "re-derive"; do not add journals or locks.
- **Invoker seam discipline.** None of these fixes should add a Claude call; all are
  deterministic write-path changes. Tests must not spawn a real backend
  (see TESTING.md's neutralization table).

## Testing

- Restore-on-failure tests: create collision archival (plan restored when publication
  fails) and detail replacement (prior body restored when the new envelope is rejected
  or the write fails).
- Single-writer test: no production `save_concepts` call outside `concept_sync.py`
  (source scan or import-hook style, mirroring existing architectural guards).
- Byte-identical-tree tests: rejected emitted-concept output (provenance mismatch,
  unpaired surrogate, malformed JSON) leaves `concepts.json` unchanged on disk.
- Divergence regression: after routing detail/scope-out through the synchronizer, plan
  scope prose and the concept record agree after each mutating flow
  (unit-level, seams stubbed).

## Deferred (tracked, not this plan)

- Publication-transaction authority, typed intents, rollback journal, recovery CLI,
  resumable create review — BACKLOG **#126** / archived remediation-1.
- Detail-envelope tightening, legacy-Markdown fallback removal, include-regeneration
  bounding — BACKLOG **#127** / archived remediation-2 steps 3, 4, 6.
- Non-delivery ledger, lifecycle candidate-generation prep, seed accounting envelope and
  create-side restoration — BACKLOG **#128** / archived remediation-3a/3b/3c.
