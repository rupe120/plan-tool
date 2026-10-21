> **Replaced**: this file has been superseded by `docs/implementation-plans/2-precise-directive-staleness.md`.
> Preserved here for history; do not edit.

# Plan seed: precise per-directive target-set staleness check (replace the coarse whole-plan fingerprint guard)

Builds BACKLOG **#93**. Today the structural-remedy walk guards against applying a
**stale saved directive** (a re-ground / merge finding whose target step ids may
now name *different* steps after a plan edit/renumber) with a **coarse whole-plan
fingerprint** comparison (`_saved_directive_is_stale` in
`plan_tool/cli/review_actions.py`). It **over-fires**: in a mixed-finding walk,
applying any earlier finding rewrites the plan file, so a later re-ground/merge
directive is downgraded to recommend-only **even though its own target ids are
still valid** — making `--apply-structural` effectively a no-op for those remedies
in any mixed walk. Replace the coarse guard with a **precise per-directive
target-set signature** that trips only when *this directive's own target steps*
moved, not when the plan changed anywhere.

> **Increased leverage (why now).** Two 2026-07-08 shipments made this the shared
> answer for **three** consumers, not one: the dispatcher consolidation (#70) made
> `_saved_directive_is_stale` the **single guard for both re-ground and merge**,
> and the completeness-apply split bridge (#70) deliberately declined a coarse
> guard on its `granularity-split` dispatch (it would break the common walk),
> deferring the "renumbered to a *different valid* step" case **here**.

> **Backlog reconciliation (carry forward — required).** Derived from BACKLOG
> **#93** (an `[Investigation]` entry — this plan resolves the design and ships it).
> The final docs/status step **must** update `BACKLOG.md`: mark #93 shipped /
> remove it, and update #93's cross-references in #70's remaining-arms note and the
> Quality/accuracy roll-up (`audit-coverage` facet) accordingly.

## The precise check (design thesis)

The directive's authoritative target is `parse_merge_action(rec).step_ids` (for
re-ground/merge) or `rec.step_id` (for the split escalation) — **specific ids**,
not the whole plan. The guard should ask: *do those ids still name the same steps
they named when the finding was computed?* Capture a **target-set signature** at
finding-computation time and re-validate only it.

- **Signature content = ordered `(target_id → step title)` identity, hashed.** A
  renumber (an earlier split/merge shifted ids) makes a target id name a
  *different* step → its title changes → signature mismatch → **stale** (correct).
  An unrelated edit elsewhere, or a body/detail edit to a non-title part of a
  target step, leaves every target id→title pair unchanged → signature matches →
  **not stale** (the over-fire this plan removes).
- **NOT a content hash.** Hashing the target steps' bodies/detail would over-fire
  on any body edit — reintroducing the coarse guard's problem at step granularity.
  Title is the stable human identity of a step (there is no per-step uuid; ids are
  positional — confirmed: the only granular hashes today are per-detail-file and
  per-code-file, none over a single step's plan-content). A deliberate title
  *rename* of a target step (rare) will over-fire to recommend-only — **safe**
  (never a wrong mutation) and vastly narrower than "any edit anywhere."

## Resolved design decisions (ground the build on these)

1. **Persist the signature as a new `Recommendation` field:
   `target_signature: Optional[str] = None`.** It auto-round-trips through
   `asdict` / `Recommendation(**r)` (`review.py:309-374`,
   `review_persistence.save_review`/`load_review`). `None` = "unknown" (legacy
   sidecars, non-directive recs) → the guard **falls back to the current coarse
   whole-plan check** so nothing regresses. Do **not** add a parallel
   `SavedReview`-level map — the per-rec field is simpler and needs no
   `update_annotation` map-plumbing (but it still must be added to the
   `update_annotation` re-serialization payload — `review_persistence.py:445-484`
   — or it's dropped on the first annotation write).

2. **Data-contract change — handle it in the same plan.** Adding a
   `Recommendation` field trips `tests/test_data_contract.py`
   (`test_contract_registry_discovers_dataclass_fields`,
   `test_every_persisted_field_is_documented_in_own_section`,
   `test_update_annotation_preserves_saved_review_contract_keys`). Document
   `target_signature` in `DATA_CONTRACT.md`'s `Recommendation` section (≈86-105)
   and keep the guard green.

3. **Capture in one "stamp" pass over the recs, not scattered in producers.**
   After the audit computes recs and before `save_review`, walk the recs and stamp
   `target_signature` on each that carries a target set — the re-ground finding
   (`review.py:_reground_already_built_recommendation`), the pairwise merge finding
   (`granularity._merge_rec`), and the `granularity-split` MIXED-STEP finding.
   A shared helper `compute_target_signature(plan, target_ids) -> str` resolves
   each id → current title and hashes the ordered pairs (reuse
   `drift_detection.compute_content_hash`'s SHA-256 primitive; do not invent
   serialization). The stamp pass has the `Plan` in hand, so the re-ground
   producer (which today only receives ids) needs no new plumbing — this is why a
   post-audit stamp beats threading `Plan` into every producer. (For the split
   finding the target set is the single `rec.step_id`.)

4. **Rewrite `_saved_directive_is_stale` as a per-directive check, coarse fallback
   preserved.** New shape: if `rec.target_signature` is set, recompute
   `compute_target_signature(current_plan, target_ids)` and return `!=`; if it is
   `None`, keep the existing `saved_plan_fingerprint != compute_plan_fingerprint`
   behavior. Both `_dispatch_reground_remedy` (`review_actions.py:982-991`) and
   `_dispatch_merge_remedy` (`:1120-1129`) call the same rewritten closure — the
   consolidation already single-sourced it, so one edit fixes both. Keep it firing
   **after** each dispatcher's session short-circuit (`applied_structural_finding_ids`)
   and **before** the bridge, exactly as today.

5. **Extend the precise guard to the split-escalation dispatch (the third
   consumer).** The `granularity-split` dispatch (`_dispatch_structural_escalation`
   via the `action` router) currently has **no** staleness guard — it relies on
   `escalate_to_split` re-parsing the plan (which catches a *deleted* id but not a
   *renumbered-to-a-different-valid* id). Add a pre-dispatch precise check on
   `rec.target_signature` (single-id target set) that downgrades to recommend-only
   on mismatch, closing the case the split bridge deferred here. Same field, same
   helper — this is the natural completion, not scope creep. (`escalate_to_split`'s
   re-parse stays as the deleted-id backstop.)

6. **`convergence_cmd.py`'s scope-out/split staleness is OUT of scope.** It is a
   *separate, parallel* guard (`classify_report_staleness`, keyed on
   convergence-history `plan_fingerprint`, single-step `rec.step_focus` target,
   its own `STALENESS_*` vocabulary) — not the shared review-sidecar contract #93
   names. Leave it; note it as a possible future generalization.

## The seams (grounded — cite these)

- Guard: `review_actions.py:_saved_directive_is_stale` (≈146-162), passed
  `saved_plan_fingerprint` (kwarg on `_build_review_action_fn`, ≈59; wired from the
  sidecar in `review_cmd.py:407/492/578`). Call sites: `_dispatch_reground_remedy`
  (≈982), `_dispatch_merge_remedy` (≈1120).
- Directive: `review.MergeAction` (`review.py:3655-3662`, `kind` + `step_ids`,
  **never serialized** — recovered by `parse_merge_action`, ≈3674-3694, from the
  `→ kind steps: ids` marker in `suggested_action`).
- Producers / stamp targets: `_reground_already_built_recommendation`
  (`review.py:3301-3351`, has ids via `HeuristicHit.step_id`), `_merge_rec`
  (`granularity.py:380-413`, has `Step` objects → titles), and the MIXED-STEP
  `granularity-split` producer (`granularity.parse_mixed_step_findings`, single
  `step_id`).
- Persistence: `Recommendation` (`review.py:309-374`), `save_review`/`load_review`
  (`review_persistence.py:285-415`), `update_annotation` (≈445-484). Contract:
  `DATA_CONTRACT.md` Recommendation section + `plan_tool/data_contract.py` registry
  + `tests/test_data_contract.py`.
- Hash primitive to reuse: `drift_detection.compute_content_hash`
  (`drift_detection.py:66-90`). Coarse fallback: `compute_plan_fingerprint`
  (`review_persistence.py:58-87`).

## Deferred (out of scope)

- **`convergence_cmd.py`'s `classify_report_staleness`** single-carve/single-split
  guard — separate contract; generalizing the precise idea there is a follow-up.
- **Title-rename over-fire** — a deliberate rename of a target step downgrades to
  recommend-only; accepted (safe, rare) rather than pursuing a stable per-step
  identity that doesn't exist today.
- **Call sites that pass no `saved_plan_fingerprint`** (reconcile-lane builders,
  detail-reconcile sub-builder, `completeness_cmd`) keep their current
  "no signal → never gate" behavior — they gain the precise check only once they
  thread a saved signal, out of scope here.

## Acceptance criteria (plan-level)

- **The over-fire is gone:** a re-ground / merge / split directive with a valid
  `target_signature` is walked in a mixed-finding walk where an **unrelated** step
  was edited earlier → the guard does **NOT** downgrade; the bridge is reached
  (given the opt-in). A test proves a still-valid directive survives an unrelated
  edit — the behavior change this plan exists for.
- **Genuine renumber still downgrades:** an earlier apply that renumbered the
  directive's target ids → signature mismatch → recommend-only, bridge not called
  (the existing safety preserved).
- **Legacy preserved:** a rec with `target_signature=None` (old sidecar) falls back
  to the coarse whole-plan check — no regression; the empty-fingerprint "unknown →
  not stale" case still holds.
- **Split path closed:** a `granularity-split` dispatch whose single target id was
  renumbered to a different valid step downgrades to recommend-only (previously it
  would have split the wrong step); a deleted id still surfaces via
  `escalate_to_split`'s `step-missing`.
- **Data contract green:** `target_signature` documented in `DATA_CONTRACT.md`,
  added to `update_annotation`'s payload, and `tests/test_data_contract.py` passes.
- **One shared guard:** re-ground and merge gate through the same rewritten
  `_saved_directive_is_stale`; no divergence reintroduced.
- `BACKLOG.md` #93 reconciled (marked shipped / removed; roll-up + #70 note updated).

## Tests (where coverage lands)

- `tests/cli/test_review_actions.py` — `TestRegroundRemedyDispatch` (stale/empty/
  coincidental-done tests ≈1168-1234), `TestMergeRemedyDispatch` (≈1519-1727),
  and the split-escalation class. Update the coarse-guard assertions and **add**
  the still-valid-survives-unrelated-edit test (both reground and merge) plus a
  precise renumber-downgrades test and a split-path renumber test.
- `tests/test_data_contract.py` — stays green with the new field documented.
- `tests/test_granularity.py` / `tests/test_review_walk.py` — the
  `compute_target_signature` helper's unit coverage (id→title hashing, missing-id,
  reorder) and the marker round-trip unchanged.
- Seam discipline: stub `reground_bridge` / `merge_bridge` / `escalate_to_split`;
  the conftest autouse gate must not see a real backend spawn.
