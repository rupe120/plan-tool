# Step 4 — Replace create's whole-tree confirm walk with a deferral-only gate that records proposed defer/wont_do as pending guide posts, safe under `-y`

## Summary

Replace `plan_tool/create.py`'s whole-tree concept walk (`_review_create_concepts`) with a **deferral-only gate**: it keeps only concepts proposed `defer`/`wont_do`, records each as a **pending guide post** (`review_state="unreviewed"`, never signed), drops owner assignment entirely, and produces a `record_kind="guide-post"` record (step 2's shape) with each node carrying a `bucket` + `bucket_anchor` (step 1's `compute_bucket_anchor`). Under `-y` every proposed deferral is kept pending; interactively the operator keeps or declines each, and a declined proposal is dropped (no guide post). The other change is a **non-empty guard** on both concept-persistence sites in `create_plan` so an un-deferred plan writes no `concepts.json` at all. On green, `create -y` proposing a deferral leaves a pending guide-post `concepts.json` that is never auto-signed, a plain create writes no concept record, and the sign-off/surfacing of that pending guide post is left to `scope-review` (step 5) and the status/report surfaces (step 7).

## Table of Contents

- [Why](#why) — what the whole-tree walk breaks and what the deferral-only gate fixes
- [Input](#input) — the guide-post shape, the anchor primitive, and the review contract this consumes
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files this step edits
- [Implementation](#implementation) — the gate rewrite, the bucket anchoring, and the persistence guard
- [Tests](#tests) — unit + integration cases added and reconciled with the code
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — hashlib, dataclasses, pytest
- [Deferred](#deferred) — what later steps wire in

## Why

Today `plan_tool/create.py:_review_create_concepts` walks **every** concept node — asking `include`/`defer`/`wont_do` and an owning step for each — and is skipped whole under `-y` (`interactive = sys.stdin.isatty() and not yes`), which silently accepts the tool's own suggestions. That silent-accept-under-automation is the founding incident (BACKLOG #121). It also over-produces: on a normal create the tree is written in full even though nobody signs off on it, and it is fingerprinted against the whole plan+detail bundle so a pending deferral goes stale by confirm time. This plan's design point **D** replaces the walk with a gate that records **only** proposed deferrals, as lightweight pending guide posts, and never signs under `-y`. Steps 1 and 2 already built the pieces this step wires into a live producer: step 1 added `plan_tool/review_persistence.py:compute_bucket_anchor`, and step 2 added the guide-post record shape (`ConceptNode.bucket`/`bucket_anchor`, `ConceptTree.record_kind`) plus the loader branch that skips the bundle-fingerprint staleness check for `record_kind == "guide-post"`. This step is the first place a guide-post record is actually written.

## Input

This step consumes three upstream contracts; its correctness rests on each staying shaped as expected:

- **Step 1's `plan_tool/review_persistence.py:compute_bucket_anchor(bucket, bucket_source_text) -> str`** — the deterministic 64-char digest each surviving guide post stores in `bucket_anchor`. The `bucket` label and `bucket_source_text` this step feeds it must match what the read/confirm callers re-extract later (steps 5 and 6), or the round-trip anchor comparison never matches.
- **Step 2's guide-post record shape and loader** (`plan_tool/concept_tree.py`): `ConceptNode.bucket`/`bucket_anchor`, `ConceptTree.record_kind`, and `save_concepts`'s `_validate_tree`. After step 2, a guide-post record's validation requires every node be `defer`/`wont_do` with a non-empty `bucket` and `bucket_anchor` (adjust to the exact per-kind strictness step 2 landed) — so this gate must set both before persistence or `save_concepts` rejects the record. `concept_id` identity still excludes the new fields, so the bare `node.id` a guide post exposes stays stable (this is the token `scope-review --concept` consumes in step 5).
- **`plan_tool/concept_review.py:review_concept_scope(tree, ids, decisions, expected_source_state, *, sign_off=False)`** — the existing scoped review primitive. Called with `sign_off=False` it sets `review_state="unreviewed"` on a decision change; with `sign_off=True` it sets `"approved"`. This step must never sign at create, so `sign_off` is always `False` here (or the gate builds the pending record directly without this call — see Implementation).
- **The bootstrap tree from `plan_tool/concept_bootstrap.py:bootstrap_concepts`** — each node is one body section: `title = section.name`, `source = section.body`, `decision = ""` (no proposed deferral by default). After step 3 removed enrichment, a plain create's tree is flat section nodes with no deferrals, so the common create path produces an empty guide-post record (no `concepts.json`). Proposed deferrals come from a node already carrying `decision` in `{defer, wont_do}` (a resumed/`--from-existing`-seeded tree, or an interactive choice).

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/create.py` — rewrite `_review_create_concepts` into the deferral-only gate (rename recommended, e.g. `_collect_deferral_guide_posts`); update its single call site in `create_plan` (the `concept_tree, reviewed_steps = _review_create_concepts(...)` line and the `plan = plan.model_copy(update={"steps": reviewed_steps})` that follows); add the non-empty guard to both unsigned concept-persistence arms (the post-write `else` arm that calls `save_concepts`, and the iterate-tail `elif budget.enabled` arm that calls `save_concepts`); import `compute_bucket_anchor` from `plan_tool.review_persistence` alongside the existing `compute_plan_fingerprint` function-local imports.
  - `tests/test_create.py` — rework the `_review_create_concepts` unit tests (owner-assignment tests become obsolete; the unattended-unsigned test becomes the pending-guide-post test), add the new deferral-only / bucket-anchor cases, retarget the `signed_review` monkeypatch, and reconcile the integration tests that asserted a signed/owned concept record or a bootstrap-record file at create.

## Implementation

**Foundational logic of this step:** *the create-time concept gate's decision rule — record only proposed `defer`/`wont_do` concepts, as pending guide posts, never signed under `-y`, and write nothing when there are none.* The parallel sites that exercise the same "is this record signed?" idea are the `signed_concept_scope` / `signed_concept_review` predicates (`any(node.review_state == "approved" …)`) and the two concept-persistence arms in `create_plan`; this step touches the persistence arms (the non-empty guard) but does not need to change the signed-predicate logic — the new gate simply never produces an approved node, so those predicates evaluate `False` for create-produced records.

- **Rewrite the gate to be deferral-only.** The new gate walks the input tree and keeps a node **only** when its `decision` is `defer` or `wont_do`. An `include` or empty-decision node produces nothing (a committed step is its own proof — no owner is recorded). This drops all of the old owner-collection machinery (the "Owning step id(s)" prompt, `accepted_owner_ids`, `owners`, the uncommitted-owner rejection) — `Step.concept_ids` is left dormant plan-wide, so the gate no longer touches steps.
- **Never sign at create; record pending.** Each surviving deferral keeps its `decision` and gets `review_state="unreviewed"`. This is the `-y` safety fix: automation records a *pending* proposal the operator can later confirm, never a silently-signed decision. Sign-off moves entirely to `scope-review` (step 5) — create does not call `review_concept_scope(sign_off=True)`. One clean way: build the pending guide-post nodes directly (filter + set fields), skipping `review_concept_scope` entirely since no sign-off happens; another is to call it with `sign_off=False`. Either is fine as long as no node comes out `"approved"`.
- **Interactive keep/decline; `-y` keeps all pending.** When interactive, surface each proposed deferral and let the operator keep it (record the guide post) or decline it (drop it — no guide post). When non-interactive (`-y`), keep every proposed deferral pending. Reuse the existing `interactive` parameter and the caller's interactivity predicate (`sys.stdin.isatty() and not yes and (input_fn is input or concept_invoker is not shell_concept_invoker)`) unchanged — do **not** remove the `concept_invoker` parameter, which step 3 kept solely for that heuristic.
- **Set `bucket` and `bucket_anchor` on each surviving node.** For a flat bootstrap node the bucket is its own section: use the section name as `bucket` (the node's `title`) and the section body as the source text (the node's `source`), then `bucket_anchor = compute_bucket_anchor(bucket, node.source)`. The label + source text pair must match what steps 5/6 re-derive when they re-extract "the section named `bucket`" and hash its body — that consistency is what lets the anchor round-trip and detect a real bucket-level change without a bundle-wide false positive. For a node that carries a `parent_path` (a legacy/deep record reached via resume), use its top-level bucket; the common post-step-3 create path only has flat nodes.
- **Return a guide-post `ConceptTree` (possibly empty), not the old `(tree, steps)` pair.** Recommended: the gate returns a `ConceptTree` with `record_kind="guide-post"` containing only the surviving pending nodes (empty list when there are no deferrals). Keep `plan_slug` and let `plan_fingerprint` carry the bootstrap value — the persistence arm overwrites it with `compute_plan_fingerprint(plan_path)` as provenance, exactly as the current unsigned arm does. Drop the `reviewed_steps` return and the `plan.model_copy(update={"steps": reviewed_steps})` line at the call site (owners are dormant). *Alternative, rejected:* return `Optional[ConceptTree]` (`None` when empty). It reads cleanly but forces `None`-guards at the mid-flow `render_scope_decisions(concept_tree)` and `signed_concept_review` uses; an empty `ConceptTree` flows through both harmlessly (empty render, `False` predicate) so only the two save sites need a guard. You have latitude on the name and the empty-vs-`None` choice; if you keep `None`, guard every `concept_tree.` use between the gate and persistence.
- **Guard both persistence sites on a non-empty record.** In `create_plan`, the post-write unsigned arm (the `else` below `signed_concept_scope`, which sets `concept_tree.plan_fingerprint = compute_plan_fingerprint(plan_path)` then `save_concepts`) and the iterate-tail unsigned arm (the `elif budget.enabled` that does the same) must **skip the save when the record has no concepts**. An un-deferred plan then gets no `concepts.json` at all — record-absence is the load-bearing "no staleness to invalidate" signal (design points A and D). Leave the signed arms (`synchronize_concepts`) intact; the new gate never produces an approved node, so they simply are not reached for create-produced records — don't delete machinery the plan keeps dormant.
- **Constraints that must hold:**
  - `record_kind` must be `"guide-post"` on the written record, or step 2's loader applies the wrong (bundle-fingerprint) staleness rule and re-breaks the confirm loop.
  - Every surviving node must be `defer`/`wont_do` with non-empty `bucket` and `bucket_anchor` before `save_concepts`, or `_validate_tree` rejects the guide-post record.
  - `node.id` must stay `concept_id(title, parent_path)` — setting `bucket`/`bucket_anchor` must not perturb identity; the bare id is the scope-review token.
  - `plan_fingerprint` stays non-empty (provenance) so `_validate_tree` passes; the loader just stops gating staleness on it for guide posts.
  - create never signs — no `review_state == "approved"` node comes out of this gate.

## Tests

New and reconciled cases in `tests/test_create.py`. This is a **feature** step (`enforce_step_tests: true`): author every case with the implementation; all must be green before the step is done.

Unit cases for the gate:

- `test_deferral_gate_unattended_records_pending_guide_post` — rework of `test_review_create_concepts_unattended_keeps_proposals_unsigned`: under `-y`, a tree with one `defer` node returns a `record_kind="guide-post"` tree whose single node has `decision="defer"`, `review_state="unreviewed"`, and non-empty `bucket`/`bucket_anchor`; nothing is signed.
- `test_deferral_gate_drops_included_concepts` — an `include`/empty-decision node produces no guide post (empty record; no owner recorded).
- `test_deferral_gate_interactive_decline_drops_proposal` — interactively declining a proposed deferral leaves no guide post; keeping it records a pending (unreviewed) one.
- `test_deferral_gate_never_signs_under_y` — no node in the returned record has `review_state == "approved"`.
- `test_deferral_gate_bucket_anchor_matches_primitive` — the written `bucket_anchor` equals `compute_bucket_anchor(bucket, node.source)` for the node's section (round-trip check against step 1's primitive).
- Delete the now-obsolete owner tests (`test_review_create_concepts_assigns_explicit_owner_interactively`, `_allows_shared_explicit_ownership`, `_rejects_uncommitted_owner`, `_does_not_infer_owner_from_title`) — owner assignment no longer exists at create; note the removal so a reviewer sees it is deliberate, not lost coverage.

Integration cases (`create_plan` end-to-end):

- `test_undeferred_create_writes_no_concept_record` — a plain create (no deferrals) writes **no** `concepts.json` (reconciles step 3's `test_retains_deterministic_concepts_and_uses_independent_invoker`, whose `concepts_path(...).is_file()` assertion must flip to "does not exist" now that a bootstrap-only record is no longer written — cross-step: step 3 kept the file, step 4 removes it for un-deferred plans).
- `test_create_defer_writes_pending_guide_post` — a create that defers a concept (via a seed/resume tree carrying `defer`) writes a `record_kind="guide-post"` record with the node `review_state="unreviewed"`; `load_concepts` returns it without raising after an unrelated later edit (the staleness fix from step 2). Surfacing the bare id in status/report/run-summary is **step 7**, not asserted here.
- Retarget/rework `test_assigns_signed_concept_id_to_written_committed_step` — create no longer signs or assigns owners; rewrite it to assert a **pending** record (or remove it, since signed-at-create is gone) rather than `review_state == "approved"` + `concept_ids`.
- Retarget the `signed_review` monkeypatch and the synchronize-failure-cleanup test to the new gate signature (it still asserts the post-write cleanup unlinks the plan and sidecar and leaves the manifest untouched); update the stub to return the new gate's shape.

### Test-creation order (feature step)

Author the unit cases alongside the gate rewrite and the integration cases alongside the persistence guard. The existing non-concept create suites (priority-bucket, collision/replace, references) must stay green unchanged. Green before the step is finished.

## Acceptance criteria

- `create -y` proposing a `defer`/`wont_do` concept writes a `record_kind="guide-post"` `concepts.json` whose node has `review_state="unreviewed"` and non-empty `bucket`/`bucket_anchor`, and no node is `"approved"`.
- A plain create with no proposed deferrals writes **no** `concepts.json`.
- Interactively declining a proposed deferral writes no guide post for it.
- Each written guide post's `bucket_anchor` equals `compute_bucket_anchor(bucket, node.source)` for its section.
- The gate assigns no owners: `Step.concept_ids` is unchanged by create.
- `node.id` for a written guide post equals `concept_id(node.title, node.parent_path)` (identity unaffected by `bucket`/`bucket_anchor`).
- `create_plan` never signs a concept at create (no `review_concept_scope(sign_off=True)` on the create path).
- `grep -n "_review_create_concepts" plan_tool/create.py` shows the renamed gate (or the old name reused) called exactly once; no owner-prompt code remains in it.
- `uv run pytest tests/test_create.py -q` passes, including the new and reconciled cases.

## References

- [hashlib — Secure hashes and message digests (Python docs)](https://docs.python.org/3/library/hashlib.html) — background for the `bucket_anchor` value produced by step 1's `compute_bucket_anchor`.
- [dataclasses — Data Classes (Python docs)](https://docs.python.org/3/library/dataclasses.html) — how `ConceptNode`/`ConceptTree` fields (`bucket`, `bucket_anchor`, `record_kind`) construct and serialize for the guide-post record.
- [pytest — How to use temporary directories and files in tests](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — the `tmp_path` fixture used for the hermetic create/persistence tests.

## Deferred

- Confirming (signing off) a pending guide post and rendering it into `## Deferred` — `scope-review` owns this (step 5) via `render_scope_decisions`; create only records the pending proposal.
- Surfacing pending guide posts (bucket + title + bare id) in `status`, the completeness report, and a `create` run-summary line — step 7 (depends on this step).
- Re-validating a guide post against the **current** bucket source text on read (recompute the anchor and treat a mismatch as "re-derive") — the read/confirm callers own it: `check_concept_coverage` and its `collect_*` callers (step 6) and `scope-review` (step 5).
- Detail's shared-find routing recording a pending guide post on a narrowed or absent record — step 8.
- Lazy drill of sub-concepts under a bucket — not needed at create; the flat bucket derivation (section name + section body) is cheap and needs no drilling.
- Migrating legacy full-tree `concepts.json` records to the guide-post shape — out of scope plan-wide; legacy records stay loadable as-is (step 2).
