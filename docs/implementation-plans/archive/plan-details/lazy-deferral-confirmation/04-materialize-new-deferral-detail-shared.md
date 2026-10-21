# Step 4 — Materialize a new deferral at detail's shared-find routing (pending, not signed)

## Summary

`plan_tool/detail.py` gains the ability to turn a concept the detail model proposes deferring — its shared-find routing to `## Deferred` — into a **pending** `defer` decision on the concept record. Today the deferral envelope can only track a step link on a concept an operator already signed off; `parse_structured_detail_response` rejects any deferral whose node is not already an approved `defer` node. Two changes: (1) surface not-yet-decided concepts to the model in `_format_concept_scope_block` and relax that parse gate so a deferral may target one of them; (2) change `generate_detail`'s concept-persistence tail to apply `defer` through `plan_tool/concept_review.py:review_concept_scope` **without `sign_off`** (leaving `review_state="unreviewed"`) and persist the sidecar directly, deriving a bootstrap tree on the fly when the plan has no record yet. The key decision, per this plan's change C/D: **do not sign the materialized deferral off** — detail runs under `-y`, so an auto-signed deferral would be the silent-acceptance failure the plan exists to fix. A pending deferral is **not** rendered into `## Deferred` (that path renders only `approved` nodes); it is surfaced by step 3's `concept-unsigned-deferral` finding with its concept id, and the operator's later `scope-review` confirmation is what signs it off and renders it. On green: a detail step that defers a concept leaves an **unreviewed** `decision="defer"` node in `concepts.json`, keeps its `detail_deferral_step_ids` link, and renders nothing into `## Deferred` until confirmed.

## Table of Contents

- [Why](#why) — why detail can't introduce a new deferral today, and why it must be pending
- [Input](#input) — the record shape, step-2 output, and helper contracts this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files and their edits
- [Implementation](#implementation) — surface proposable nodes, relax the gate, record pending, derive-on-absent
- [Tests](#tests) — the new tests and the ones to retarget
- [Acceptance criteria](#acceptance-criteria) — checkable observable behaviors
- [References](#references) — the docs relevant to this step
- [Deferred](#deferred) — the confirmation-render path and the writer consolidation left out

## Why

Detail's shared-find directive (`plan_tool/detail.py:_DETAIL_FOUNDATIONAL_COMBINED_DIRECTIVE` / `_DETAIL_FOUNDATIONAL_SPLIT_DIRECTIVE`) already tells the model to name a step's shared logic and route a find that needs its own consolidation step to `## Deferred`. But that routing is a dead end for the concept record: `parse_structured_detail_response` only accepts a deferral whose node is already `review_state="approved"` and `decision="defer"` (the check in its `all(supplied)` block), so detail can track a step link on a deferral an operator already made — it cannot **introduce** one. This step lets detail materialize the deferral its own shared-find routing proposes. Crucially it records the proposal **pending** (`review_state="unreviewed"`), not signed off: detail runs under `-y`, and per change C a `-y` deferral must never be silently accepted. A pending deferral surfaces through step 3's finding (with its id) and is confirmed — and only then rendered — by the operator's `scope-review defer`/`wont_do`. A mis-proposed pending deferral (e.g. one a committed step actually implements) is harmless because it is **inert until confirmed** — it never renders and never counts, so the operator simply doesn't confirm it; actively dismissing a wrong pending deferral is deferred (see Deferred).

## Input

- **Step 2's output** — step 2 reshapes `create`'s concept gate so a normal un-deferred plan gets **no `concepts.json`**, and a confirm-gate deferral is written to the record as pending. This step reads whatever record step 2 left: **either absent** (the common case — this step derives a bootstrap tree on the fly, see Implementation) **or** a `ConceptTree` with section nodes it can defer.
- **The concept record shape** — `plan-details/<slug>/concepts.json` (`ConceptTree` / `ConceptNode` in `plan_tool/concept_tree.py`), whose `decision` ∈ `{"", "include", "defer", "wont_do"}` and `review_state` ∈ `{"unreviewed", "approved"}`. A bootstrap section node carries `decision=""`, `review_state="unreviewed"` — the state this step's materialization starts from, and (minus the decision) the state it leaves the deferred node in.
- **`bootstrap_concepts`** (`plan_tool/concept_bootstrap.py:bootstrap_concepts`) — derives a thin section-node tree from the plan body, exactly as `scope_review_cmd.py:57-64` calls it when `original_tree is None`. This step reuses it to materialize a target node when the plan is record-absent.
- **`review_concept_scope`** (`plan_tool/concept_review.py:review_concept_scope`) — applies a decision to exactly the given ids against an `expected_source_state` (compared to `tree.plan_fingerprint`); called here **without `sign_off`** so the node becomes `decision="defer"` while `review_state` stays `"unreviewed"` (the pending state).
- **The record writer** — `plan_tool/concept_tree.py:save_concepts` persists the sidecar. This step keeps the direct sidecar write (it does **not** route through `synchronize_concepts`): the plan puts the `concept_sync` unsigned-safe arm out of scope, and `synchronize_concepts` on an unsigned tree would re-render — and blank — the plan's `## Deferred`/`## Out of scope` prose. A pending deferral must live in the sidecar only, invisible in prose until confirmed.
- **The loaded tree in `generate_detail`** — `generate_detail` loads the tree once near the top via `load_concepts(plan_path, compute_plan_fingerprint(plan_path))` and never mutates it (`_replace_detail_deferrals` deep-copies).

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/detail.py` —
    - `_format_concept_scope_block`: also list defer-proposable not-yet-approved nodes (today it skips every node whose `review_state != "approved"`), so the model can name a concept to defer by its id.
    - `parse_structured_detail_response`: in the `all(supplied)` validation block, drop the `node.review_state != "approved"` and `node.decision != "defer"` rejections; keep the `step_id == step.id`, node-exists, owner (unowned or owned-by-this-step), and `## Deferred`-mentions-the-id checks.
    - `generate_detail`'s concept-persistence tail: derive a bootstrap tree when the record is absent, apply `defer` **without `sign_off`** via `review_concept_scope` for the newly-proposed ids, keep the step-link replacement, refresh the fingerprint, and `save_concepts`.
  - `tests/test_detail.py` — new materialization tests plus retargeting the tests coupled to the old approval gate (see Tests).

## Implementation

- **Let the model name a concept to defer.** `_format_concept_scope_block` today shows only `approved` nodes. The model can't reference a node it can't see, so extend the block to also list defer-proposable nodes (`decision` in `{"", "include"}`, not yet `approved`), clearly marked as proposable. Keep the approved lines unchanged so `test_dry_run_reports_include_regeneration_without_writes` (asserts `decision=include` in the prompt) stays green.
- **Relax the parse gate, keep the real guards.** In `parse_structured_detail_response`'s `all(supplied)` block, drop only the two rejections that require pre-approval (`node.review_state != "approved"`, `node.decision != "defer"`). Keep every other check: `deferral.step_id == step.id`, the node exists in the tree, the owner check (`concept_owners and step.id not in concept_owners`), and the rule that the `## Deferred` body must mention exactly the deferred ids. A deferral may now target a not-yet-decided node this step owns or that no step owns.
- **Derive a target when the plan is record-absent.** The common plan carries no `concepts.json` (step 2). When `concept_tree is None` and the response proposes a deferral, derive a bootstrap tree from the plan body (`bootstrap_concepts`, as `scope_review_cmd.py` does), and materialize the proposed decision on the matching section node. When a record already exists, defer the node already present. Either way the target node exists before the decision is applied.
- **Record the deferral PENDING — do not sign off, do not render.** Apply `defer` to the newly-proposed ids through `review_concept_scope(tree, ids, {id: "defer"}, expected_source_state=tree.plan_fingerprint)` **without `sign_off=True`**, so each node becomes `decision="defer"`, `review_state="unreviewed"`. Keep the existing step-link replacement (`_replace_detail_deferrals`) so `detail_deferral_step_ids` still tracks which step deferred the concept, in deterministic step order. Refresh `plan_fingerprint = compute_plan_fingerprint(plan_path)` and persist with `save_concepts`. **Do not route through `synchronize_concepts`**: on an unsigned tree it would blank the plan's owned sections (the plan forbids adding the unsigned-safe arm). The pending node stays in the sidecar, surfaced by step 3's `concept-unsigned-deferral` finding, until `scope-review` signs it off and renders it. **Record shape:** the persisted tree is the **thin section bootstrap** (one `defer` node among the `decision=""` section nodes), not decision-only — consistent with the plan's change E (which reuses `scope-review`'s derive-the-section-tree behavior); a decision-only record on this path is a deferred nicety, not this step's job.
- **Why pending, not signed — and say why in a comment.** Signing off (`sign_off=True`) under `-y` would make a model-proposed deferral a decision the operator never saw — the founding incident (BACKLOG #121) this plan closes. The rejected alternative (sign off so it renders immediately) reintroduces exactly that silent acceptance; do not take it. The operator's `scope-review defer`/`wont_do` confirmation is what both signs off and renders; a pending deferral that is never confirmed stays inert (never rendered, never counted), which is the harmless resting state for a mis-proposed one.
- **Constraints that must hold (do not vary):**
  - **`review_concept_scope` runs against the tree's own fingerprint.** Pass `expected_source_state=tree.plan_fingerprint` (the loaded or freshly-bootstrapped tree), so the decision application's compare-and-swap matches the record it is mutating.
  - **Refresh the fingerprint before saving.** Detail rewrote the plan/detail bundle this run, so set `plan_fingerprint = compute_plan_fingerprint(plan_path)` before `save_concepts`, or the next `load_concepts` raises `StaleConceptTreeError` (the exact hazard seen twice while authoring the parked plan).
  - **Best-effort, non-fatal.** A failed pending write marks the affected results `written=False` with a persistence-failed `skipped_reason` (naming the written detail path and that prior links are retained), mirroring the current tail's `except` outcome — it must not abort the detail run.
- **Foundational logic and its other sites.** Consolidating detail's, create's, and `scope_out.py`'s sidecar writes onto one writer is the parked concept-write-integrity single-writer goal — out of scope here (this step keeps the direct `save_concepts` write, now writing a pending node).

## Tests

New tests in `tests/test_detail.py` (class `TestStructuredDetailDeferrals` and a sibling for the prompt block):

- `test_parse_accepts_deferral_of_not_yet_approved_node` — `parse_structured_detail_response` returns the deferral when the node exists, is unowned or owned by this step, is mentioned in `## Deferred`, and `step_id == step.id`, even with `review_state="unreviewed"` / `decision=""`.
- `test_parse_rejects_deferral_for_other_step` — a deferral whose `step_id != step.id` still returns `None`.
- `test_parse_rejects_deferral_owned_by_other_step` — a deferral targeting a node in another step's `concept_ids` still returns `None`.
- `test_parse_rejects_when_deferred_body_omits_id` — the `## Deferred`-mentions-the-id check still fires.
- `test_scope_block_lists_proposable_nodes` — `_format_concept_scope_block` lists a not-yet-approved node so the model can name it.
- `test_detail_materializes_new_deferral_pending` — after `generate_detail`, the deferred node is `decision="defer"`, **`review_state="unreviewed"`**, and `detail_deferral_step_ids` carries this step.
- `test_detail_pending_deferral_not_rendered` — the plan's `## Deferred` section does **not** contain the deferred concept after the run (pending stays out of prose); the sidecar fingerprint is fresh (`load_concepts` succeeds).
- `test_detail_materializes_on_absent_record` — a plan with no `concepts.json` gets a bootstrap-derived pending deferral node written; no error on the absent-record path.
- `test_detail_deferral_write_failure_is_non_fatal` — a `save_concepts` failure leaves the detail file on disk and marks the step `written=False` with a persistence-failed reason.

Retargeted existing tests:

- `test_concurrent_deferrals_save_once_in_step_order` — keep the `plan_tool.detail.save_concepts` spy (this step keeps that seam); assert both steps' links land in deterministic order.
- `test_valid_deferral_persists_after_detail_write` — a pre-existing `defer` node's step link still persists; now an unreviewed proposed node can also be deferred.
- `test_yes_does_not_sign_off_unreviewed_concept` — stays green and is now **load-bearing**: even when detail materializes a deferral, no node is flipped to `approved` under `-y`.

### Test-creation order (feature step)

This is a **feature** step. Add each test above alongside the code that makes it pass. Green-before-done gate: every new test, and the retargeted tests, must be green before this step is considered finished.

## Acceptance criteria

- `parse_structured_detail_response` returns a `ParsedDetailResponse` for a deferral targeting a `review_state="unreviewed"` node this step owns (or that no step owns) when the `## Deferred` body names its id and `step_id == step.id`.
- `parse_structured_detail_response` returns `None` for a deferral whose `step_id != step.id`, or whose node is owned by a different step, or whose id is absent from `## Deferred`.
- After `generate_detail` defers a concept, `load_concepts` shows that node with `decision="defer"`, **`review_state="unreviewed"`**, and `detail_deferral_step_ids` including this step.
- The plan's `## Deferred` section does **not** contain the pending concept after the run — it is rendered only after `scope-review` signs it off.
- A plan with no prior `concepts.json` still materializes the pending deferral (bootstrap-derived); no `StaleConceptTreeError` on the next load (fingerprint refreshed).
- A sidecar write failure leaves the written detail file on disk and marks the step `written=False`; the detail run does not abort.
- `uv run pytest tests/test_detail.py -q` passes.

## References

- [dataclasses — Data Classes (Python 3.13)](https://docs.python.org/3/library/dataclasses.html) — `DetailDeferral` and `ConceptNode`/`ConceptTree` are frozen/plain dataclasses; needed to reason about the immutable deferral records and the deep-copied candidate tree.
- [json — JSON encoder and decoder (Python 3.13)](https://docs.python.org/3/library/json.html) — `detail_deferral_step_ids` is a compact JSON list and the sidecar is `json.dumps(asdict(tree), ...)`; needed for the step-link and fingerprint byte framing.
- [How to use temporary directories and files in tests (pytest)](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — the `tmp_path` fixture the new `generate_detail` materialization tests build on.

## Deferred

- Rendering a materialized deferral into `## Deferred` at detail time — deliberately **not** done: rendering requires sign-off, and sign-off under `-y` is the founding incident. Rendering happens on the operator's `scope-review` confirmation (already lazy), which owns the signed path.
- Consolidating `plan_tool/detail.py`'s, `plan_tool/create.py`'s, and `plan_tool/scope_out.py:apply_narrow`'s sidecar writes onto one writer (the parked concept-write-integrity single-writer goal) — out of scope; this step keeps the direct `save_concepts` write.
- Tight ownership-bounding of a detail pending deferral to concepts genuinely lacking a committed owner — under lazy there is no `Step.concept_ids` to check, so `scope-review` confirmation is the interim guard (a plan-level Deferred item).
- `plan_tool/review.py`'s independent parse of `detail_deferral_step_ids` (`_structured_concept_deferral_is_valid`) consolidating onto a shared reader — reconcile-owned, not any plan step.
