> **Auto-archived**: this plan was swept on 2026-07-08 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Precise Directive Staleness
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Add the target_signature field and a compute_target_signature helper
  files:
  - plan_tool/review.py
  - plan_tool/review_walk.py
  - DATA_CONTRACT.md
  - tests/test_review_walk.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/precise-directive-staleness/01-target-signature-field-compute-target.md
  status: done
- id: 2
  title: Stamp target_signature onto directive findings before they are saved
  files:
  - plan_tool/review_walk.py
  - plan_tool/cli/reconcile.py
  - plan_tool/completeness_report.py
  - plan_tool/cli/review_cmd.py
  - plan_tool/auto_reconcile.py
  - tests/test_review_walk.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/precise-directive-staleness/02-stamp-target-signature-directive.md
  status: done
- id: 3
  title: Rewrite the stale-directive guard to check each directive's own targets
  files:
  - plan_tool/cli/review_actions.py
  - tests/cli/test_review_actions.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/precise-directive-staleness/03-rewrite-stale-directive-guard-check.md
  status: done
- id: 4
  title: Guard the granularity-split escalation with the same precise check
  files:
  - plan_tool/cli/review_actions.py
  - tests/cli/test_review_actions.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  - 3
  detail: docs/implementation-plans/plan-details/precise-directive-staleness/04-guard-granularity-split-escalation-same.md
  status: done
- id: 5
  title: 'Reconcile BACKLOG #93 to shipped'
  files:
  - BACKLOG.md
  complexity: low
  change_type: non-code
  depends_on:
  - 2
  - 3
  - 4
  detail: docs/implementation-plans/plan-details/precise-directive-staleness/05-reconcile-backlog-93-shipped.md
  status: done
---
# Precise Directive Staleness

## Overview

Builds BACKLOG **#93**. This plan replaces the coarse whole-plan fingerprint guard in the structural-remedy walk (`_saved_directive_is_stale` in `plan_tool/cli/review_actions.py`) with a **precise per-directive target-set signature** that trips only when *this directive's own target steps* moved, not when the plan changed anywhere. It adds a new `Recommendation` field `target_signature: Optional[str] = None`, stamps it on directive-carrying recs in a single post-audit pass via a shared helper `compute_target_signature(plan, target_ids) -> str`, rewrites the guard to a per-directive check with the coarse whole-plan comparison preserved as the legacy fallback (`target_signature=None`), and extends the precise check to the third consumer — the `granularity-split` escalation dispatch. Legacy sidecars, non-directive recs, and call sites passing no `saved_plan_fingerprint` keep their current behavior.

## Problem statement

Today the structural-remedy walk guards against applying a **stale saved directive** — a re-ground / merge finding whose target step ids may now name *different* steps after a plan edit/renumber — with a **coarse whole-plan fingerprint** comparison (`_saved_directive_is_stale`). It **over-fires**: in a mixed-finding walk, applying any earlier finding rewrites the plan file, so a later re-ground/merge directive is downgraded to recommend-only **even though its own target ids are still valid** — making `--apply-structural` effectively a no-op for those remedies in any mixed walk. Two 2026-07-08 shipments raised the leverage: the dispatcher consolidation (#70) made `_saved_directive_is_stale` the **single guard for both re-ground and merge**, and the completeness-apply split bridge (#70) deliberately declined a coarse guard on its `granularity-split` dispatch (it would break the common walk), deferring the "renumbered to a *different valid* step" case here. The directive's authoritative target is `parse_merge_action(rec).step_ids` (re-ground/merge) or `rec.step_id` (split escalation) — **specific ids**, not the whole plan; the guard should ask only whether those ids still name the same steps they named when the finding was computed.

## Architecture

**The signature.** Signature content is the ordered `(target_id → title + change_type)` identity, hashed. A renumber (an earlier split/merge shifted ids) makes a target id name a *different* step → its title/change_type changes → signature mismatch → **stale** (correct). An unrelated edit elsewhere, or a body/detail edit to a non-title part of a target step, leaves every target pair unchanged → signature matches → **not stale** (the over-fire removed). It is deliberately **NOT a content hash** — hashing bodies/detail would over-fire on any body edit, reintroducing the coarse guard's problem at step granularity. There is no per-step uuid (ids are positional; the only granular hashes today are per-detail-file and per-code-file), so `title + change_type` is the strongest stable identity available at plan-content granularity.

**Two failure directions — the signature is a *precision* optimization, not the sole safety guarantee.** (1) *Over-fire:* a deliberate title/change_type *rename* of a target step downgrades that directive to recommend-only — safe, rare, and vastly narrower than "any edit anywhere." (2) *Under-fire (the one to be honest about):* `schema.py` uniques step **ids**, not titles, so a renumber that aligns a **same-title + same-change_type** step onto a target id produces a matching signature → the guard reports **fresh**. This does **not** mean a wrong mutation lands: the guard is precision (fewer spurious recommend-only downgrades), and **safety rests on the bridge's own target re-validation** — `reground_bridge` marks done only steps it confirms already-built, `merge_bridge` folds only steps it confirms mergeable/pending, and `escalate_to_split`/`split_is_safe` re-parse and re-check the target. So a signature collision at worst lets a still-wrong directive *reach* the bridge, which then refuses on its own checks — never a silent wrong flip. The plan must state this both-directions framing; do not claim the signature is "unconditionally safe."

**Persistence.** Persist the signature as a new `Recommendation` field `target_signature: Optional[str] = None`. It auto-round-trips through `asdict` / `Recommendation(**r)` everywhere recs are (re)serialized — `save_review`/`load_review` **and** `update_annotation`, which re-serializes recs with `[asdict(r) for r in saved.recommendations]` (`review_persistence.py:479`). So **`review_persistence.py` needs no edit** for the field to survive an annotation write — there is no hand-built per-rec payload to update (the hand-built payload covers only top-level `SavedReview` keys). `None` = "unknown" (legacy sidecars, non-directive recs) → the guard falls back to the current coarse whole-plan check so nothing regresses. Do **not** add a parallel `SavedReview`-level map — the per-rec field is simpler. (The data-contract work is real, though: document `target_signature` in `DATA_CONTRACT.md`'s `Recommendation` section, since the field is auto-discovered by the drift-guard registry.)

**Capture in one stamp pass.** After the audit computes recs and before `save_review`, walk the recs and stamp `target_signature` on each that carries a target set — the re-ground finding (`review.py:_reground_already_built_recommendation`), the pairwise merge finding (`granularity._merge_rec`), and the `granularity-split` MIXED-STEP finding (`granularity.parse_mixed_step_findings`, single `step_id`). The shared helper `compute_target_signature(plan, target_ids) -> str` resolves each id → current title and hashes the ordered pairs, reusing `drift_detection.compute_content_hash`'s SHA-256 primitive (`drift_detection.py:66-90`) — do not invent serialization. The stamp pass has the `Plan` in hand, so the re-ground producer (which today only receives ids via `HeuristicHit.step_id`) needs no new plumbing — this is why a post-audit stamp beats threading `Plan` into every producer.

**The rewritten guard.** Rewrite `_saved_directive_is_stale` (≈146-162) as a per-directive check with the coarse fallback preserved: if `rec.target_signature` is set, recompute `compute_target_signature(current_plan, target_ids)` and return `!=`; if it is `None`, keep the existing `saved_plan_fingerprint != compute_plan_fingerprint` behavior (coarse fallback `compute_plan_fingerprint`, `review_persistence.py:58-87`). Both `_dispatch_reground_remedy` (`review_actions.py:982-991`) and `_dispatch_merge_remedy` (`:1120-1129`) call the same rewritten closure — the consolidation already single-sourced it, so one edit fixes both. It keeps firing **after** each dispatcher's session short-circuit (`applied_structural_finding_ids`) and **before** the bridge, exactly as today.

**Third consumer — the split escalation.** The `granularity-split` dispatch (`_dispatch_structural_escalation` via the `action` router) currently has **no** staleness guard — it relies on `escalate_to_split` re-parsing the plan, which catches a *deleted* id but not a *renumbered-to-a-different-valid* id. Add a pre-dispatch precise check on `rec.target_signature` (single-id target set) that downgrades to recommend-only on mismatch, closing the case the split bridge deferred here. Same field, same helper — the natural completion, not scope creep; `escalate_to_split`'s re-parse stays as the deleted-id backstop.

**Directive recovery.** The directive `review.MergeAction` (`review.py:3655-3662`, `kind` + `step_ids`) is **never serialized** — it is recovered by `parse_merge_action` (≈3674-3694) from the `→ kind steps: ids` marker in `suggested_action`.

## References

- [dataclasses — Data Classes (Python Standard Library)](https://docs.python.org/3/library/dataclasses.html) — Official reference for adding a field with a default (target_signature: Optional[str] = None) and for asdict()/Recommendation(**r) round-tripping, which the plan relies on for persistence.
- [hashlib — Secure hashes and message digests (Python Standard Library)](https://docs.python.org/3/library/hashlib.html) — Reference for the SHA-256 primitive reused by compute_content_hash to hash the ordered (target_id → title) pairs into the target signature.
- [typing — Support for type hints: Optional](https://docs.python.org/3/library/typing.html#typing.Optional) — Defines the Optional[str] annotation used for the new target_signature field and its None (legacy/unknown) sentinel semantics.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- **`convergence_cmd.py`'s scope-out/split staleness (`classify_report_staleness`)** — a *separate, parallel* guard keyed on convergence-history `plan_fingerprint`, single-step `rec.step_focus` target, with its own `STALENESS_*` vocabulary; not the shared review-sidecar contract #93 names. Leave it; note it as a possible future generalization.
- **Call sites that pass no `saved_plan_fingerprint`** — reconcile-lane builders, the detail-reconcile sub-builder, and `completeness_cmd` keep their current "no signal → never gate" behavior; they gain the precise check only once they thread a saved signal.

## Risks

- **Signature over-fire (rename)** — a deliberate title/change_type rename of a target step downgrades that directive to recommend-only. Severity low; accepted as safe and rare.
- **Signature under-fire (same-title collision)** — `schema.py` uniques step ids, not titles, so a renumber aligning a same-title+change_type step onto a target id yields a matching signature (guard reports fresh). This is **not** a silent wrong mutation: the bridges re-validate their own targets (`reground_bridge` already-built, `merge_bridge` mergeable/pending, `escalate_to_split`/`split_is_safe` re-parse) and refuse a wrong target — the signature is precision, the bridge is safety. Severity low; accepted rather than inventing a per-step uuid that does not exist. A test should assert the collision case reaches the bridge (not a wrong flip).
- **Data-contract drift** — the new `Recommendation.target_signature` field is auto-discovered by the drift-guard registry, so `tests/test_data_contract.py` fails until it is documented in `DATA_CONTRACT.md`'s `Recommendation` section. (It round-trips through `save_review`/`load_review`/`update_annotation` automatically — no `review_persistence.py` payload edit needed.) Mitigation: document the field in the same step.
- **Data-contract drift** — adding a `Recommendation` field trips `tests/test_data_contract.py` (`test_contract_registry_discovers_dataclass_fields`, `test_every_persisted_field_is_documented_in_own_section`). Mitigation: document `target_signature` in `DATA_CONTRACT.md`'s `Recommendation` section (≈86-105) in the same plan.

## Testing

Follow the project's unit-first convention. Seam discipline: stub `reground_bridge` / `merge_bridge` / `escalate_to_split` so the conftest autouse gate never sees a real backend spawn.

- `tests/cli/test_review_actions.py` — `TestRegroundRemedyDispatch` (stale/empty/coincidental-done tests ≈1168-1234), `TestMergeRemedyDispatch` (≈1519-1727), and the split-escalation class. Update the coarse-guard assertions and **add**: the still-valid-survives-unrelated-edit test (both re-ground and merge), a precise renumber-downgrades test, a split-path renumber test, and a **same-title-collision test asserting the directive reaches the (stubbed) bridge** (precision under-fire → bridge is the safety, not a wrong flip).
- `tests/test_granularity.py` / `tests/test_review_walk.py` — unit coverage for the `compute_target_signature` helper (id→title+change_type hashing, missing-id, reorder) and a **round-trip test that `Recommendation.target_signature` survives `save_review`→`load_review`→`update_annotation`** (this is the field's actual persistence coverage — `test_update_annotation_preserves_saved_review_contract_keys` checks only top-level `SavedReview` keys, not per-rec fields).
- `tests/test_data_contract.py` — stays green with the new field documented (`test_contract_registry_discovers_dataclass_fields` and `test_every_persisted_field_is_documented_in_own_section` are the two that gate a new `Recommendation` field).

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — unit tests added with the implementation; green before completion.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (feature) — unit tests added with the implementation; green before completion.
- step 5 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- **The over-fire is gone:** a re-ground / merge / split directive with a valid `target_signature`, walked in a mixed-finding walk where an **unrelated** step was edited earlier, does **NOT** downgrade — the bridge is reached (given the opt-in). A test proves a still-valid directive survives an unrelated edit.
- **Genuine renumber still downgrades:** an earlier apply that renumbered the directive's target ids → signature mismatch → recommend-only, bridge not called.
- **Legacy preserved:** a rec with `target_signature=None` (old sidecar) falls back to the coarse whole-plan check — no regression; the empty-fingerprint "unknown → not stale" case still holds.
- **Split path closed:** a `granularity-split` dispatch whose single target id was renumbered to a different valid step downgrades to recommend-only; a deleted id still surfaces via `escalate_to_split`'s `step-missing`.
- **Data contract green:** `target_signature` is documented in `DATA_CONTRACT.md`'s `Recommendation` section and `tests/test_data_contract.py` passes (the field round-trips automatically through `save_review`/`load_review`/`update_annotation` — no `review_persistence.py` payload edit).
- **One shared guard:** re-ground and merge gate through the same rewritten `_saved_directive_is_stale`; no divergence reintroduced.
- **`BACKLOG.md` #93 reconciled:** marked shipped / removed, with #93's cross-references in #70's remaining-arms note and the Quality/accuracy roll-up (`audit-coverage` facet) updated.

## Deferred

- **`convergence_cmd.py`'s `classify_report_staleness`** single-carve/single-split guard — a separate contract; generalizing the precise idea there is a follow-up.
- **Title-rename over-fire** — a deliberate rename of a target step downgrades to recommend-only; accepted (safe, rare) rather than pursuing a stable per-step identity that does not exist today.
- **Call sites that pass no `saved_plan_fingerprint`** (reconcile-lane builders, detail-reconcile sub-builder, `completeness_cmd`) keep their current "no signal → never gate" behavior; they gain the precise check only once they thread a saved signal.
