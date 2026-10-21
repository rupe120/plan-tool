# Step 4 — Materialize a new deferral at detail's concept-persistence tail

## Summary

`plan_tool/detail.py` gains the ability to turn a concept the model proposes deferring into a **new, unconfirmed deferral** on the concept record — today it can only track step links on a concept an operator already signed off as `decision="defer"`. Two changes in `generate_detail`: (1) `parse_structured_detail_response` stops requiring the deferred concept to be an approved `defer` node, so a plain bootstrap/undecided node can be proposed; (2) the tail that persists deferrals applies the `defer` decision through `plan_tool/concept_review.py:review_concept_scope` with `sign_off=False` (so the node lands `review_state="unreviewed"`) and publishes through `plan_tool/concept_sync.py:synchronize_concepts` instead of the direct `save_concepts` write. The key decision: **materialize unconfirmed, never sign off** — detail runs non-interactively, and auto-signing its own suggestion is the founding incident (BACKLOG #121). On green: a detail step that defers a bootstrap concept leaves a `decision="defer"`, `review_state="unreviewed"` node in `concepts.json` plus the existing `detail_deferral_step_ids` step link, and the plan's `## Deferred` section stays untouched until an operator confirms via `scope-review`.

## Table of Contents

- [Why](#why) — what detail can't do today and why the defer point needs it
- [Input](#input) — the concept record, step-2 output, and the two helpers this reads
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files and their edits
- [Implementation](#implementation) — relax the precondition, materialize the decision, route the write
- [Tests](#tests) — the coupled tests to flip and the new materialization tests
- [Acceptance criteria](#acceptance-criteria) — checkable observable behaviors
- [References](#references) — the docs relevant to this step
- [Deferred](#deferred) — what this step leaves for later work and the backlog

## Why

`create` no longer signs off deferrals for every plan (steps 1–2), so the eager, pre-approved `decision="defer"` node that `plan_tool/detail.py` relies on today usually isn't there. But detail is a real defer point: its `parse_structured_detail_response` accepts a structured deferral envelope from the model, and the tail of `generate_detail` persists it. Right now that path is boxed in — `parse_structured_detail_response` rejects any deferral whose node isn't already `review_state="approved"` and `decision="defer"`, so detail can only *re-track* a concept an operator deferred earlier; it cannot **propose a new one**. This step opens that box: when the model proposes deferring a concept, detail records the proposal on the record as unconfirmed and lets an operator confirm it later, matching the lazy stance the rest of the plan sets.

## Input

- **Step 2's output** — step 2 reshaped `create` so a proposed `defer`/`wont_do` under `-y` is recorded `review_state="unreviewed"` (decision intact), never signed off, and a record is written only when it carries such a node. This step applies the same "record unconfirmed under automation" rule at detail's defer point.
- **The concept record** — `plan-details/<slug>/concepts.json` (`ConceptTree`/`ConceptNode` in `plan_tool/concept_tree.py`). `generate_detail` loads it near the top via `load_concepts(plan_path, compute_plan_fingerprint(plan_path))`, which returns `None` when the record is absent (the common lazy case). The whole concept tail is guarded by `concept_tree is not None`, so a plan with no record is untouched by this step.
- **`review_concept_scope`** (`plan_tool/concept_review.py`) — pure transform returning a deep copy. It checks `expected_source_state == tree.plan_fingerprint`, requires the scope to be non-empty known ids with one decision each, and on a decision change sets `node.decision`, resets `review_state="unreviewed"`, and clears the sign-off metadata. With `sign_off=False` the node stays unreviewed — exactly the unconfirmed state this step wants. It cannot invent a node: every scoped id must already exist in the tree.
- **`synchronize_concepts`** (`plan_tool/concept_sync.py`) — the guarded single publish. It compare-and-swaps the current sidecar against `original_tree`, compare-and-swaps the plan's owned sections/frontmatter against `source_plan_text` (defaulting to current on-disk when `None`), recomputes the plan fingerprint itself, rewrites `## Deferred`/`## Out of scope` from the **approved** nodes only (`render_scope_decisions`), and returns a frozen `ConceptSyncResult` whose `status` is one of `SUCCESS` / `SOURCE_DIVERGENCE` / `MAPPING_CONFLICT` / `INVALID_STATE` / `PUBLICATION_FAILURE`. An unreviewed `defer` node publishes into the sidecar but renders nothing into the plan prose and maps to no step scope — the right shape for an unconfirmed proposal.

Verification limit: `review_concept_scope` and `synchronize_concepts` are pure/guarded helpers already covered by `tests/test_concept_review.py` and `tests/test_concept_sync.py`; this step consumes them and does not re-verify their internals.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/detail.py` —
    - In `parse_structured_detail_response`, relax the per-deferral semantic check so a not-yet-approved concept node can be proposed for deferral. Drop the hard `node.review_state != "approved"` and `node.decision != "defer"` rejections; keep the node-exists, `step_id == step.id`, owner, and `## Deferred`-mentions-the-id checks.
    - In the concept tail of `generate_detail` (the block that today builds `replacements`, calls `_replace_detail_deferrals`, sets `plan_fingerprint`, and calls `save_concepts`): materialize the `defer` decision through `review_concept_scope(sign_off=False)` for the deferred concepts, then publish through `synchronize_concepts` on a fresh re-parse of the plan; map a non-`SUCCESS` result to the existing "persistence failed, prior links retained for recovery" outcome.
    - Import `synchronize_concepts` (and its result types) and `review_concept_scope` at module top; drop the now-unused `save_concepts` import.
  - `tests/test_detail.py` — flip the coupled tests in `TestStructuredDetailDeferrals` / `TestParseStructuredDetailResponse` and add the new materialization tests below.

## Implementation

**Relax the precondition so a new deferral is proposable.**
- `parse_structured_detail_response` today rejects a deferral unless its node is already `review_state == "approved"` and `decision == "defer"`. That pins detail to re-tracking, not proposing. Remove those two rejections.
- Keep the rest of the semantic gate: `deferral.step_id == step.id`, the node exists, the `## Deferred` body mentions exactly the deferred 64-hex ids, and the owner check (`concept_owners and step.id not in concept_owners` — an empty owner set still passes, which is correct for an unowned bootstrap node).
- **Guard against silently overriding an operator decision.** One way: still reject a node that is `review_state == "approved"` with a decision **other than** `defer` — so a detail step can't quietly un-commit a concept an operator already signed off as `include`/`wont_do`. Re-affirming an already-approved `defer` stays fine (no decision change). State this predicate as the recommended shape; the implementer owns the exact boolean.

**Materialize the decision as unconfirmed, then publish once.** Replace the tail's `_replace_detail_deferrals` → `save_concepts` write with:
- Build the deferral replacements exactly as today: `(result.step_id, result.deferrals)` for every `result.written`. `_replace_detail_deferrals` stays the owner of the `detail_deferral_step_ids` step-link bookkeeping — keep calling it.
- Collect the distinct concept ids being deferred across all written results. If any, apply them in one `review_concept_scope(tree, deferred_ids, {id: "defer" for id in deferred_ids}, expected_source_state=concept_tree.plan_fingerprint, sign_off=False)` call. `expected_source_state` is the top-of-run tree's own fingerprint, so the guard passes trivially. `sign_off=False` is the whole point — the node lands `decision="defer"`, `review_state="unreviewed"`.
- Order the two pure transforms so both land on one candidate tree (either compose their copies, or apply the decision first and hand that tree to `_replace_detail_deferrals`). The published tree must carry both the `defer` decision **and** the step link.
- Publish with `synchronize_concepts(plan_path, fresh_plan, original_tree=concept_tree, reviewed_tree=candidate, source_plan_text=None)`:
  - **`fresh_plan` must be a re-parse of the plan from disk at the tail**, not the plan parsed at the top of `generate_detail`. Every written step already round-tripped the plan through `update_step_detail_field`, so the top-of-run parse is stale and would drop the new `detail:` pointers on republish. The structural-split arm's own `final_plan = parse_plan(plan_path)` is the in-file precedent.
  - **`original_tree` is the unmutated tree from `load_concepts` at the top.** `generate_detail` never mutates it in place (both transforms deep-copy), so it is the correct compare-and-swap baseline for the sidecar. Do not hand it either candidate tree.
  - **`source_plan_text=None`** (default: current on-disk plan). Detail legitimately rewrote the plan since the top parse, so a stale top-of-run text would fail the owned-section compare-and-swap on every run. The sidecar compare-and-swap (`original_tree`) is the real integrity guard at this call site.
  - **Drop the manual `updated_concepts.plan_fingerprint = compute_plan_fingerprint(plan_path)`** — `synchronize_concepts` computes and stores the fingerprint itself. The candidate tree must still carry its existing non-empty `concept_fingerprint` (from `load_concepts`) so `_validate_tree` inside the sync passes; only the `plan_fingerprint` computation moves into the sync.
- **Run the tail whenever any step was written, even with no new deferrals.** Detail's writes changed the plan fingerprint, so the sidecar fingerprint must be refreshed; skipping the sync on an unchanged deferral set would leave the next run's `load_concepts` staleness check reading an out-of-date fingerprint. When there are no deferred ids at all, skip only the `review_concept_scope` call (its scope can't be empty) — still run `_replace_detail_deferrals` (to strip stale links) and `synchronize_concepts` (to refresh).

**Map a failed publish to the existing recovery signal.** Today a `save_concepts` exception flips every written result to `written=False` with a "concept deferral persistence failed … prior deferral links retained for recovery" reason. `synchronize_concepts` reports failure by **returning a non-`SUCCESS` `ConceptSyncResult`, not by raising** — so convert a non-`SUCCESS` status into that same result-flip. Keep the wording aligned with the current message so the recovery contract and any run-log expectations stay stable.

**Constraints that are not free to vary:**
- **Materialize unconfirmed, never sign off.** The rejected arm — `sign_off=True` so the deferral renders straight into `## Deferred` — silently accepts the tool's own suggestion under `-y`, which is BACKLOG #121, the incident this whole plan exists to fix. Detail is non-interactive automation; step 3 already built the surface that shows an operator the unconfirmed deferral, and `scope-review` is the only thing that signs it off.
- **`_replace_detail_deferrals` and the `detail_deferral_step_ids` key stay.** They are separate from the decision: the key is bookkeeping consumed by `_included_deferral_step_ids` (include-transition regeneration) and `_format_concept_scope_block` (prompt rendering). This step adds the decision on top; it does not replace the link.
- **`synchronize_concepts` is imported at `plan_tool/detail.py` module top**, alongside the existing patchable `apply_finding` import, so tests can monkeypatch `plan_tool.detail.synchronize_concepts`. The `detail → concept_sync` edge is cycle-safe (`concept_sync` imports only `concept_tree`, `parser`, `schema`). Do not make it a function-local import — detail is an orchestrator, not an import-clean leaf.

**Shared logic — the `detail_deferral_step_ids` reader in review.py.** `plan_tool/review.py:_structured_concept_deferral_is_valid` parses the same `detail_deferral_step_ids` key independently. This step does **not** touch it — it stays a separate reader on the raw key, and consolidating it onto a shared reader is a reconcile-owned follow-up, not this step's footprint (see Deferred). This step changes only how the key and the `defer` decision are **written**, not how review.py reads them.

## Tests

All in `tests/test_detail.py`. New tests land with the implementation; every one must be green before the step is done.

**Flip / retarget existing coupled tests:**
- `TestParseStructuredDetailResponse` semantic cases — retarget any case that fed an approved-`defer` node so an undecided/unreviewed bootstrap node is now accepted. Add `test_proposes_deferral_on_unreviewed_bootstrap_node` — a deferral naming an `decision=""`, `review_state="unreviewed"` node parses successfully.
- `test_concurrent_deferrals_save_once_in_step_order` — the spy target moves from `plan_tool.detail.save_concepts` to `plan_tool.detail.synchronize_concepts`. Land a seam-neutral sibling first (final sidecar carries both steps' links in step order) so the observable is pinned before the spy retarget, then retarget the spy to assert publish-exactly-once.

**New materialization tests:**
- `test_deferral_materializes_unreviewed_decision` — after `generate_detail`, the deferred node has `decision == "defer"` and `review_state == "unreviewed"`, plus its `detail_deferral_step_ids` link.
- `test_deferral_does_not_sign_off` — the materialized node is **not** `approved`; the plan's `## Deferred` section is unchanged (an unreviewed node renders nothing).
- `test_operator_approved_include_cannot_be_deferred` — a deferral naming an `approved`/`include` node is rejected (not written, file absent), matching the override guard.
- `test_publish_routes_through_synchronize_concepts` — patch `plan_tool.detail.synchronize_concepts` to return `SUCCESS` and assert it is called once with `original_tree` = the top-of-run tree and a `reviewed_tree` carrying the `defer` decision.
- `test_sync_source_divergence_retains_links_for_recovery` — patch the sync to return `SOURCE_DIVERGENCE`; the written results flip to `written=False` with the "prior deferral links retained for recovery" reason and the detail file stays on disk.
- `test_sidecar_fingerprint_fresh_after_persistence` — after a written run (even with unchanged deferral links), a fresh `load_concepts(plan_path, compute_plan_fingerprint(plan_path))` succeeds, proving the sync refreshed the fingerprint.
- `test_tail_reparses_plan_before_publish` — a two-step run whose earlier step wrote a `detail:` pointer still has that pointer after the concept publish (the stale top-of-run parse is not used).

## Acceptance criteria

- `parse_structured_detail_response` returns a `ParsedDetailResponse` for a deferral naming an `decision=""`, `review_state="unreviewed"` node, and returns `None` for a deferral naming an `approved`/`include` node.
- After a `generate_detail` run that defers a bootstrap concept, `concepts.json` holds that node with `decision == "defer"`, `review_state == "unreviewed"`, and `detail_deferral_step_ids` naming the deferring step.
- The plan's `## Deferred` section is byte-unchanged by an unconfirmed materialization (nothing renders for an unreviewed node).
- `generate_detail`'s concept tail calls `plan_tool.concept_sync.synchronize_concepts` (patchable) exactly once per run when a record exists and any step was written; it no longer calls `save_concepts`, and `grep -n "save_concepts" plan_tool/detail.py` returns nothing.
- A non-`SUCCESS` `ConceptSyncResult` flips the written results to `written=False` with the recovery-signal reason; the detail file remains on disk.
- A fresh `load_concepts` after a written run succeeds against the recomputed fingerprint (no `StaleConceptTreeError`).
- All new `TestStructuredDetailDeferrals` / `TestParseStructuredDetailResponse` tests pass, and `uv run pytest tests/test_detail.py -q` is green.

## References

- [dataclasses — Data Classes (Python 3.13)](https://docs.python.org/3/library/dataclasses.html) — `ConceptSyncResult`/`DetailDeferral` are frozen dataclasses; read for how the immutable result objects this tail consumes behave.
- [json — JSON encoder and decoder (Python 3.13)](https://docs.python.org/3/library/json.html) — the `detail_deferral_step_ids` value and the sidecar are `json.dumps`/`load` round-trips; read for the exact serialization the compare-and-swap keys on.
- [How to use temporary directories and files in tests (pytest)](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — the `tmp_path` fixture the new `generate_detail` tests use to stage a plan + `concepts.json` and re-read them after the run.

## Deferred

- Materializing a deferral when **no** concept record exists — deriving a bootstrap tree at detail time the way `plan_tool/cli/scope_review_cmd.py` does — is out of scope. The concept tail is guarded by `concept_tree is not None`, so a plan with no `concepts.json` still can't gain its first deferral here; route the derive-from-absent case to `BACKLOG.md` if wanted.
- Consolidating `plan_tool/review.py:_structured_concept_deferral_is_valid` onto a shared `detail_deferral_step_ids` reader — this step keeps review.py's independent parse; the consolidation is reconcile-owned, not a plan step.
- Enforcing a single-writer boundary that forbids `save_concepts` outside `plan_tool/concept_sync.py` (removing the calls in `plan_tool/create.py` and `plan_tool/scope_out.py`, adding a token-scan guard test) — the plan's "Out of scope" lists the concept-write-integrity hardening as superseded; this step only stops detail's own direct write.
- Operator confirmation of the materialized deferral — happens later through `scope-review` (already lazy) and is surfaced by step 3's status/completeness lines; this step does not add a confirm gate.

<!-- plan-tool-detail-deferrals
{"deferrals":[]}
-->
