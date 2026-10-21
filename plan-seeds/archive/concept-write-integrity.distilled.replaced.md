> **Replaced**: this file has been superseded by `docs/implementation-plans/2-concept-write-integrity.md`.
> Preserved here for history; do not edit.

## Overview

Fix the four concrete write-integrity gaps in the shipped concept sign-off machinery (the `concepts.json` record, three-state sign-off, `scope-review`, `Step.concept_ids` ownership, and `concept-coverage` enforcement), plus the docs/backlog reconciliation that closes them out. The machinery is functionally complete, but its write paths can lose data or let the plan prose and the concept record diverge. All fixes are deterministic write-path changes inside existing modules — no new modules, commands, schemas, or Claude calls — and the expected decomposition is ~6–8 steps. This plan is the deliberate distillation of the six archived concept-remediation plans (2026-07-13), cut from a ~46-step hardening program to the handful of findings whose failure modes are real today (source: reconcile audit `0129c29` on the shipped BACKLOG #121 integrations, distilled from archived plans `2-concept-remediation-1-publication-transactions.md` findings 1–2 and `2-concept-remediation-2-authoring-boundary-hardening.md` findings 3–4).

## Problem statement

The shipped concept machinery's write paths have four integrity gaps:

1. **Create collision-archive ordering.** `create_plan()` archives a colliding plan (collision replacement, `plan_tool/create.py:5393` `_decide_replace_collisions` and the archival path near `create.py:4498`/`:5369`) *before* concept synchronization succeeds, and a later failure deletes the new plan without restoring the archived original — a failed create can strand an archived collision plan.

2. **Three writers bypass the canonical synchronizer.** `concept_sync.synchronize_concepts()` is the designed single writer keeping plan prose, rendered scope, and the concept record aligned, but three production call sites write the concept sidecar directly, letting plan prose and the concept record diverge: unsigned create falls back to a direct `save_concepts` (`plan_tool/create.py:6276`, `:7021`) because the synchronizer erases unsigned scope prose; `detail` persists deferral updates directly (`plan_tool/detail.py:4234`); and `apply_narrow` saves its carved sidecar directly (`plan_tool/scope_out.py:896-901`).

3. **Detail replacement safety.** `_archive_existing_detail()` (`plan_tool/detail.py:5335`, called at `:4402`/`:4745`/`:5047` and `:2156`) moves the active detail file away before the replacement body is known-good, so an interrupted or rejected regeneration can leave a step with no detail.

4. **Fail-soft concept parse.** `_parse_emitted_concepts()` (`plan_tool/concept_tree.py:281`) accepts a concept whose `evidence_rationale` merely contains a literal excerpt without provenance-checking the cited evidence, and an unpaired surrogate in emitted output can crash ID derivation outside the fail-soft boundary — invalid model-emitted concept output can mutate the tree instead of failing soft.

A fifth work item follows from these: update the concept-workflow docs the fixes touch (`RUNBOOK.md` / `DATA_CONTRACT.md` as applicable — the single-writer invariant belongs in `DATA_CONTRACT.md`'s concepts section) and perform the `BACKLOG.md` bookkeeping: note under #121's follow-up disposition that the write-integrity fixes shipped, and adjust #126/#127/#128 if any of their residue was absorbed here.

## Architecture

No new components are introduced; every fix lands inside the existing `concept_sync.py` / `concept_tree.py` / `create.py` / `detail.py` / `scope_out.py` surfaces — if a fix appears to need new machinery, that is the signal it belongs to BACKLOG #126/#127/#128 instead.

- **Ordering over journaling for create collisions:** the archive move of a colliding plan happens only after publication succeeds — or the archived original is restored on failure. The recovery model stays git + fingerprint: a stale `plan_fingerprint` reads as "re-derive"; no journals or locks are added.
- **Single-writer consolidation:** extend `synchronize_concepts()` to handle unsigned scope state (the reason the unsigned-create path currently bypasses it), then route all three direct writers (`create.py`'s unsigned fallback, `detail`'s deferral persistence, `apply_narrow`'s carved sidecar) through it, so no production code path outside `concept_sync` writes `concepts.json`. The invariant is guarded by a test asserting no production `save_concepts` caller outside `concept_sync.py`.
- **Validate-before-replace for detail files:** validate the replacement body first (the existing seven-section gate) and restore the prior body when the write fails, so `_archive_existing_detail()` never destroys the active detail before the replacement is known-good.
- **Fail-soft parse boundary:** invalid or mismatched emitted concept output (provenance mismatch, unpaired surrogate, malformed text) leaves the input tree byte-for-byte unchanged and reports the rejection; malformed text never escapes as an exception mid-mutation.
- **Invoker seam discipline:** none of these fixes adds a Claude call; all are deterministic write-path changes.

The plan consumes the shipped BACKLOG #121 contracts as-is: the validated `concepts.json` sidecar record and its `save_concepts` persistence, `synchronize_concepts()` as the designed single writer, the existing seven-section detail gate, the `_parse_emitted_concepts()` fail-soft boundary (including `evidence_rationale`), and the git + `plan_fingerprint` recovery model. The cited line anchors date from reconcile audit `0129c29` and should be re-verified against current code during detailing.

## Out of scope

- Publication-transaction authority, rollback journal, recovery command, repo lock, non-delivery ledger, and seed accounting envelope — those designs are preserved under `docs/implementation-plans/archive/` and tracked as BACKLOG **#126**, **#127**, and **#128**; this seed fixes the concrete data-loss and divergence bugs in the shipped concept sign-off machinery, nothing more.
- New modules, commands, or schemas — every fix lands inside the existing `concept_sync.py` / `concept_tree.py` / `create.py` / `detail.py` / `scope_out.py` surfaces; a fix that appears to need new machinery belongs to #126/#127/#128 instead.
- Journals or locks — the recovery model stays git + fingerprint.

## Risks

- Convergence pressure could grow the plan past its intended ~6–8 steps; the seed's mitigation is to defer to the backlog entries (BACKLOG #126/#127/#128) rather than growing this plan.

## Testing

Per TESTING.md, tests must not spawn a real backend (see the invoker neutralization table); all fixes are deterministic write-path changes, so unit-level tests with seams stubbed are the default tier.

- Restore-on-failure tests: create collision archival (plan restored when publication fails) and detail replacement (prior body restored when the new envelope is rejected or the write fails).
- Single-writer test: no production `save_concepts` call outside `concept_sync.py` (source scan or import-hook style, mirroring existing architectural guards).
- Byte-identical-tree tests: rejected emitted-concept output (provenance mismatch, unpaired surrogate, malformed JSON) leaves `concepts.json` unchanged on disk.
- Divergence regression: after routing detail/scope-out through the synchronizer, plan scope prose and the concept record agree after each mutating flow (unit-level, seams stubbed).

## Acceptance criteria

- A create whose concept publication fails restores the archived colliding plan: the archive move happens only after publication succeeds, or the original is restored on failure (`plan_tool/create.py` collision-replacement path).
- No production code path outside `concept_sync` writes `concepts.json`: the direct `save_concepts` writers at `plan_tool/create.py:6276`/`:7021`, `plan_tool/detail.py:4234`, and `plan_tool/scope_out.py:896-901` are routed through `synchronize_concepts()`, and a guard test asserts no production `save_concepts` caller outside `concept_sync.py`.
- An interrupted or rejected detail regeneration never leaves a step with no detail: the replacement is validated by the existing seven-section gate before `_archive_existing_detail()` moves the active file, and the prior body is restored when the write fails.
- Invalid or mismatched emitted concept output (provenance mismatch, unpaired surrogate, malformed JSON) leaves `concepts.json` byte-for-byte unchanged on disk and reports the rejection; malformed text never escapes as an exception mid-mutation (`_parse_emitted_concepts()`, `plan_tool/concept_tree.py:281`).
- No fix adds a Claude call, and no new modules, commands, or schemas are introduced.
- The final docs/status step updates `BACKLOG.md`: #121's follow-up disposition notes the write-integrity fixes shipped, #126/#127/#128 are adjusted if any residue was absorbed here, and the single-writer invariant is documented in `DATA_CONTRACT.md`'s concepts section (with `RUNBOOK.md` updated as applicable).

## Deferred

- Publication-transaction authority, typed intents, rollback journal, recovery CLI, resumable create review — BACKLOG **#126** / archived remediation-1.
- Detail-envelope tightening, legacy-Markdown fallback removal, include-regeneration bounding — BACKLOG **#127** / archived remediation-2 steps 3, 4, 6.
- Non-delivery ledger, lifecycle candidate-generation prep, seed accounting envelope and create-side restoration — BACKLOG **#128** / archived remediation-3a/3b/3c.
