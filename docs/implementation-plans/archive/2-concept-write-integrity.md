---
title: Concept Write Integrity
status: planning
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Teach synchronize_concepts to handle unsigned scope state without erasing
    scope prose
  files:
  - plan_tool/concept_sync.py
  - tests/test_concept_sync.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/concept-write-integrity/01-teach-synchronize-concepts-handle.md
  status: current
- id: 2
  title: Restore the archived colliding plan when a create fails after archiving it
  files:
  - plan_tool/create.py
  - tests/test_create.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/concept-write-integrity/02-restore-archived-colliding-plan-when.md
- id: 3
  title: Route create's unsigned save_concepts fallbacks through synchronize_concepts
  files:
  - plan_tool/create.py
  - tests/test_create.py
  complexity: medium
  change_type: refactor
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/concept-write-integrity/03-route-create-unsigned-save-concepts.md
- id: 4
  title: Route detail's deferral persistence through synchronize_concepts
  files:
  - plan_tool/detail.py
  - plan_tool/concept_sync.py
  - tests/test_detail.py
  - tests/test_concept_sync.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/concept-write-integrity/04-route-detail-deferral-persistence.md
- id: 5
  title: Route scope-out's carved sidecar save through synchronize_concepts and add
    the no-writer-outside-concept_sync guard test
  files:
  - plan_tool/scope_out.py
  - tests/test_scope_out.py
  - tests/test_concept_sync.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 3
  - 4
  detail: docs/implementation-plans/plan-details/concept-write-integrity/05-route-scope-out-carved-sidecar-save.md
- id: 6
  title: Validate the replacement detail body before archiving the old file and restore
    it when the write fails
  files:
  - plan_tool/detail.py
  - tests/test_detail.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/concept-write-integrity/06-validate-replacement-detail-body-before.md
- id: 7
  title: 'Harden _parse_emitted_concepts: provenance-check cited evidence and keep
    unpaired-surrogate and malformed output inside the fail-soft boundary'
  files:
  - plan_tool/concept_tree.py
  - tests/test_concept_tree.py
  - tests/test_concept_emit.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/concept-write-integrity/07-harden-parse-emitted-concepts.md
- id: 8
  title: 'Document the single-writer invariant in DATA_CONTRACT.md and reconcile BACKLOG
    #121/#126-#128 and RUNBOOK.md'
  files:
  - DATA_CONTRACT.md
  - BACKLOG.md
  - RUNBOOK.md
  complexity: low
  change_type: non-code
  depends_on:
  - 2
  - 3
  - 4
  - 5
  - 6
  - 7
  detail: docs/implementation-plans/plan-details/concept-write-integrity/08-document-single-writer-invariant-data.md
---
# Concept Write Integrity

> **Superseded — parked 2026-07-15.** This plan hardens the *eager* concept-decomposition
> machinery. It is superseded by `plan-seeds/lazy-deferral-confirmation.md`, which makes concept
> materialization lazy and removes most of the write-integrity surface this plan addresses. The
> completeness audit converged **11 → 1 finding**; the lone remaining medium (`step4-mixed-refactor-feature`)
> asks to split step 4, which would push the plan past its own declared ~6–8 step ceiling — the
> seed's own "defer rather than grow" trigger. Its concrete bug fixes remain captured in BACKLOG
> #126–#128. Kept in `archive/` as the ready-to-run fallback if the lazy approach is rejected.

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

## References

- [json — JSON encoder and decoder (Python 3 standard library)](https://docs.python.org/3/library/json.html) — Documents json.load/json.dumps, JSONDecodeError, and the module's explicit acceptance of unpaired UTF-16 surrogates — the exact behavior the fail-soft _parse_emitted_concepts() boundary must guard against.
- [codecs — Codec registry, error handlers (Python 3 standard library)](https://docs.python.org/3/library/codecs.html) — Documents the surrogatepass/surrogateescape error handlers and why UTF-8 encoding of lone surrogates raises — needed to keep an unpaired surrogate from crashing concept ID derivation outside the fail-soft boundary.
- [os — Files and directories: os.replace (Python 3 standard library)](https://docs.python.org/3/library/os.html#os.replace) — Defines the atomic same-filesystem rename primitive used for write-then-replace so concepts.json and detail files are never left half-written.
- [pathlib — Path.replace, Path.rename, Path.write_text (Python 3 standard library)](https://docs.python.org/3/library/pathlib.html) — Covers the pathlib rename/replace/write semantics (overwrite behavior, platform differences) relevant to archiving a colliding plan and restoring a prior detail body on failure.
- [shutil — High-level file operations: shutil.move (Python 3 standard library)](https://docs.python.org/3/library/shutil.html) — Specifies shutil.move's os.rename-first/copy-fallback and overwrite semantics, which govern the archive-move and restore-on-failure ordering in the create-collision and detail-replacement fixes.
- [tempfile — mkstemp and NamedTemporaryFile (Python 3 standard library)](https://docs.python.org/3/library/tempfile.html) — Documents race-free temporary file creation for the validate-then-swap pattern: write the replacement body to a temp file, validate it, then atomically replace the active file.

## Steps

See the `steps:` block in the frontmatter.

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

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — unit tests added with the implementation; green before completion.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (refactor) — characterization tests pinned before the change; pass unchanged after.
- step 4 (feature) — a routing step that fuses a behavior-preserving helper move with a new signed-tree re-render: pin the preserved-behavior characterization tests (unsigned persistence, publish-once ordering) before the change so they pass unchanged after, **and** add the new-behavior tests (signed-tree owned-section re-render, owner step_id remap after an auto-split, concurrent-rewrite refusal) with the implementation.
- step 5 (feature) — same shape as step 4: pin the preserved-behavior characterization battery before the change, and add the new-behavior tests (signed carved-deferral rendering, surviving/carved step_id remap, sync-refusal rollback, the single-writer guard) with the implementation.
- step 6 (feature) — unit tests added with the implementation; green before completion.
- step 7 (feature) — unit tests added with the implementation; green before completion.
- step 8 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- A create whose concept publication fails restores the archived colliding plan: the archive move happens only after publication succeeds, or the original is restored on failure (`plan_tool/create.py` collision-replacement path).
- No production code path outside `concept_sync` writes `concepts.json`: the direct `save_concepts` writers at `plan_tool/create.py:6276`/`:7021`, `plan_tool/detail.py:4234`, and `plan_tool/scope_out.py:896-901` are routed through `synchronize_concepts()`, and a guard test asserts no production `save_concepts` caller outside `concept_sync.py`.
- Plan prose and the concept record agree after each mutating flow (the behavioral point of routing through the single writer, not just the mechanical writer count): after a signed-tree detail or scope-out run, the plan's owned `## Deferred` / `## Out of scope` sections match the record's rendering, and the concept owner step_ids the signed sync consumes are remapped across any step renumber (detail auto-split, scope-out narrow) so the record never points at a wrong or removed step.
- An interrupted or rejected detail regeneration never leaves a step with no detail: the replacement is validated by the existing seven-section gate before `_archive_existing_detail()` moves the active file, and the prior body is restored when the write fails.
- Invalid or mismatched emitted concept output (provenance mismatch, unpaired surrogate, malformed JSON) leaves `concepts.json` byte-for-byte unchanged on disk and reports the rejection; malformed text never escapes as an exception mid-mutation (`_parse_emitted_concepts()`, `plan_tool/concept_tree.py:281`).
- No fix adds a Claude call, and no new modules, commands, or schemas are introduced.
- The final docs/status step updates `BACKLOG.md`: #121's follow-up disposition notes the write-integrity fixes shipped, #126/#127/#128 are adjusted if any residue was absorbed here, and the single-writer invariant is documented in `DATA_CONTRACT.md`'s concepts section (with `RUNBOOK.md` updated as applicable).

## Deferred

- Publication-transaction authority, typed intents, rollback journal, recovery CLI, resumable create review — BACKLOG **#126** / archived remediation-1.
- Detail-envelope tightening, legacy-Markdown fallback removal, include-regeneration bounding — BACKLOG **#127** / archived remediation-2 steps 3, 4, 6.
- Non-delivery ledger, lifecycle candidate-generation prep, seed accounting envelope and create-side restoration — BACKLOG **#128** / archived remediation-3a/3b/3c.
