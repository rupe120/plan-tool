> **Replaced**: this file has been superseded by `docs/implementation-plans/2-precise-directive-staleness.md`.
> Preserved here for history; do not edit.

## Overview

Builds BACKLOG **#93**. This plan replaces the coarse whole-plan fingerprint guard in the structural-remedy walk (`_saved_directive_is_stale` in `plan_tool/cli/review_actions.py`) with a **precise per-directive target-set signature** that trips only when *this directive's own target steps* moved, not when the plan changed anywhere. It adds a new `Recommendation` field `target_signature: Optional[str] = None`, stamps it on directive-carrying recs in a single post-audit pass via a shared helper `compute_target_signature(plan, target_ids) -> str`, rewrites the guard to a per-directive check with the coarse whole-plan comparison preserved as the legacy fallback (`target_signature=None`), and extends the precise check to the third consumer — the `granularity-split` escalation dispatch. Legacy sidecars, non-directive recs, and call sites passing no `saved_plan_fingerprint` keep their current behavior.

## Problem statement

Today the structural-remedy walk guards against applying a **stale saved directive** — a re-ground / merge finding whose target step ids may now name *different* steps after a plan edit/renumber — with a **coarse whole-plan fingerprint** comparison (`_saved_directive_is_stale`). It **over-fires**: in a mixed-finding walk, applying any earlier finding rewrites the plan file, so a later re-ground/merge directive is downgraded to recommend-only **even though its own target ids are still valid** — making `--apply-structural` effectively a no-op for those remedies in any mixed walk. Two 2026-07-08 shipments raised the leverage: the dispatcher consolidation (#70) made `_saved_directive_is_stale` the **single guard for both re-ground and merge**, and the completeness-apply split bridge (#70) deliberately declined a coarse guard on its `granularity-split` dispatch (it would break the common walk), deferring the "renumbered to a *different valid* step" case here. The directive's authoritative target is `parse_merge_action(rec).step_ids` (re-ground/merge) or `rec.step_id` (split escalation) — **specific ids**, not the whole plan; the guard should ask only whether those ids still name the same steps they named when the finding was computed.

## Architecture

**The signature.** Signature content is the ordered `(target_id → step title)` identity, hashed. A renumber (an earlier split/merge shifted ids) makes a target id name a *different* step → its title changes → signature mismatch → **stale** (correct). An unrelated edit elsewhere, or a body/detail edit to a non-title part of a target step, leaves every target id→title pair unchanged → signature matches → **not stale** (the over-fire removed). It is deliberately **NOT a content hash** — hashing bodies/detail would over-fire on any body edit, reintroducing the coarse guard's problem at step granularity. Title is the stable human identity of a step (there is no per-step uuid; ids are positional — the only granular hashes today are per-detail-file and per-code-file, none over a single step's plan-content). A deliberate title *rename* of a target step (rare) over-fires to recommend-only — **safe** (never a wrong mutation) and vastly narrower than "any edit anywhere."

**Persistence.** Persist the signature as a new `Recommendation` field `target_signature: Optional[str] = None`. It auto-round-trips through `asdict` / `Recommendation(**r)` (`review.py:309-374`, `review_persistence.save_review`/`load_review`). `None` = "unknown" (legacy sidecars, non-directive recs) → the guard falls back to the current coarse whole-plan check so nothing regresses. Do **not** add a parallel `SavedReview`-level map — the per-rec field is simpler and needs no `update_annotation` map-plumbing, but it **must** still be added to the `update_annotation` re-serialization payload (`review_persistence.py:445-484`) or it is dropped on the first annotation write.

**Capture in one stamp pass.** After the audit computes recs and before `save_review`, walk the recs and stamp `target_signature` on each that carries a target set — the re-ground finding (`review.py:_reground_already_built_recommendation`), the pairwise merge finding (`granularity._merge_rec`), and the `granularity-split` MIXED-STEP finding (`granularity.parse_mixed_step_findings`, single `step_id`). The shared helper `compute_target_signature(plan, target_ids) -> str` resolves each id → current title and hashes the ordered pairs, reusing `drift_detection.compute_content_hash`'s SHA-256 primitive (`drift_detection.py:66-90`) — do not invent serialization. The stamp pass has the `Plan` in hand, so the re-ground producer (which today only receives ids via `HeuristicHit.step_id`) needs no new plumbing — this is why a post-audit stamp beats threading `Plan` into every producer.

**The rewritten guard.** Rewrite `_saved_directive_is_stale` (≈146-162) as a per-directive check with the coarse fallback preserved: if `rec.target_signature` is set, recompute `compute_target_signature(current_plan, target_ids)` and return `!=`; if it is `None`, keep the existing `saved_plan_fingerprint != compute_plan_fingerprint` behavior (coarse fallback `compute_plan_fingerprint`, `review_persistence.py:58-87`). Both `_dispatch_reground_remedy` (`review_actions.py:982-991`) and `_dispatch_merge_remedy` (`:1120-1129`) call the same rewritten closure — the consolidation already single-sourced it, so one edit fixes both. It keeps firing **after** each dispatcher's session short-circuit (`applied_structural_finding_ids`) and **before** the bridge, exactly as today.

**Third consumer — the split escalation.** The `granularity-split` dispatch (`_dispatch_structural_escalation` via the `action` router) currently has **no** staleness guard — it relies on `escalate_to_split` re-parsing the plan, which catches a *deleted* id but not a *renumbered-to-a-different-valid* id. Add a pre-dispatch precise check on `rec.target_signature` (single-id target set) that downgrades to recommend-only on mismatch, closing the case the split bridge deferred here. Same field, same helper — the natural completion, not scope creep; `escalate_to_split`'s re-parse stays as the deleted-id backstop.

**Directive recovery.** The directive `review.MergeAction` (`review.py:3655-3662`, `kind` + `step_ids`) is **never serialized** — it is recovered by `parse_merge_action` (≈3674-3694) from the `→ kind steps: ids` marker in `suggested_action`.

## Out of scope

- **`convergence_cmd.py`'s scope-out/split staleness (`classify_report_staleness`)** — a *separate, parallel* guard keyed on convergence-history `plan_fingerprint`, single-step `rec.step_focus` target, with its own `STALENESS_*` vocabulary; not the shared review-sidecar contract #93 names. Leave it; note it as a possible future generalization.
- **Call sites that pass no `saved_plan_fingerprint`** — reconcile-lane builders, the detail-reconcile sub-builder, and `completeness_cmd` keep their current "no signal → never gate" behavior; they gain the precise check only once they thread a saved signal.

## Risks

- **Title-rename over-fire** — a deliberate rename of a target step downgrades that directive to recommend-only. Severity low; accepted as safe (never a wrong mutation) and rare, rather than pursuing a stable per-step identity that does not exist today.
- **Dropped-on-write field** — if `target_signature` is not added to `update_annotation`'s re-serialization payload (`review_persistence.py:445-484`), it is silently dropped on the first annotation write and the guard falls back to coarse. Mitigation: include it in the payload and cover it with `tests/test_data_contract.py`'s `test_update_annotation_preserves_saved_review_contract_keys`.
- **Data-contract drift** — adding a `Recommendation` field trips `tests/test_data_contract.py` (`test_contract_registry_discovers_dataclass_fields`, `test_every_persisted_field_is_documented_in_own_section`). Mitigation: document `target_signature` in `DATA_CONTRACT.md`'s `Recommendation` section (≈86-105) in the same plan.

## Testing

Follow the project's unit-first convention. Seam discipline: stub `reground_bridge` / `merge_bridge` / `escalate_to_split` so the conftest autouse gate never sees a real backend spawn.

- `tests/cli/test_review_actions.py` — `TestRegroundRemedyDispatch` (stale/empty/coincidental-done tests ≈1168-1234), `TestMergeRemedyDispatch` (≈1519-1727), and the split-escalation class. Update the coarse-guard assertions and **add**: the still-valid-survives-unrelated-edit test (both re-ground and merge), a precise renumber-downgrades test, and a split-path renumber test.
- `tests/test_granularity.py` / `tests/test_review_walk.py` — unit coverage for the `compute_target_signature` helper (id→title hashing, missing-id, reorder) and the marker round-trip unchanged.
- `tests/test_data_contract.py` — stays green with the new field documented (`test_contract_registry_discovers_dataclass_fields`, `test_every_persisted_field_is_documented_in_own_section`, `test_update_annotation_preserves_saved_review_contract_keys`).

## Acceptance criteria

- **The over-fire is gone:** a re-ground / merge / split directive with a valid `target_signature`, walked in a mixed-finding walk where an **unrelated** step was edited earlier, does **NOT** downgrade — the bridge is reached (given the opt-in). A test proves a still-valid directive survives an unrelated edit.
- **Genuine renumber still downgrades:** an earlier apply that renumbered the directive's target ids → signature mismatch → recommend-only, bridge not called.
- **Legacy preserved:** a rec with `target_signature=None` (old sidecar) falls back to the coarse whole-plan check — no regression; the empty-fingerprint "unknown → not stale" case still holds.
- **Split path closed:** a `granularity-split` dispatch whose single target id was renumbered to a different valid step downgrades to recommend-only; a deleted id still surfaces via `escalate_to_split`'s `step-missing`.
- **Data contract green:** `target_signature` is documented in `DATA_CONTRACT.md`, added to `update_annotation`'s payload, and `tests/test_data_contract.py` passes.
- **One shared guard:** re-ground and merge gate through the same rewritten `_saved_directive_is_stale`; no divergence reintroduced.
- **`BACKLOG.md` #93 reconciled:** marked shipped / removed, with #93's cross-references in #70's remaining-arms note and the Quality/accuracy roll-up (`audit-coverage` facet) updated.

## Deferred

- **`convergence_cmd.py`'s `classify_report_staleness`** single-carve/single-split guard — a separate contract; generalizing the precise idea there is a follow-up.
- **Title-rename over-fire** — a deliberate rename of a target step downgrades to recommend-only; accepted (safe, rare) rather than pursuing a stable per-step identity that does not exist today.
- **Call sites that pass no `saved_plan_fingerprint`** (reconcile-lane builders, detail-reconcile sub-builder, `completeness_cmd`) keep their current "no signal → never gate" behavior; they gain the precise check only once they thread a saved signal.
