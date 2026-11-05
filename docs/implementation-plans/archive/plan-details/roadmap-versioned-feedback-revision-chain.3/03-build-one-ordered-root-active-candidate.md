> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Build one ordered root-and-active-candidate batch from eligible reviewer feedback and current roadmap-derived context

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Update `plan_tool/roadmap_candidate_context.py` to build one immutable batch from the current accepted root, optional active candidate source, eligible reviewer-ledger items, and current derived feedback. Update `tests/test_roadmap_candidate_context.py` to cover batch selection, ordering, identity, and refusal behavior. The key decision is that the batch records exact snapshots from one processing pair rather than selecting one embedded `FeedbackRow` from an artifact. On green, later candidate work receives a deterministic, byte-bounded payload and receipt that cannot be changed by later ledger edits.

## Table of Contents

- [Summary](#summary) — Reviewer view of the completed batch builder.
- [Table of Contents](#table-of-contents) — Links to every section in this file.
- [Why](#why) — Why one selector-bound embedded-feedback context is insufficient.
- [Input](#input) — Upstream ledger and enrollment contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Production and test changes in scope.
- [Implementation](#implementation) — Batch identity, source selection, ordering, and bounded rendering.
- [Tests](#tests) — Focused contract coverage for the batch builder.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Serialization, hashing, and immutable-record references.
- [Applicable guardrails](#applicable-guardrails) — Boundaries on authority and batch behavior.
- [Deferred](#deferred) — Nearby lifecycle work owned by later steps.

## Why

`plan_tool/roadmap_candidate_context.py:build_candidate_context` currently builds context around one selector and one embedded `FeedbackRow`, while the revision-chain design needs one ordinary run to bind every eligible reviewer request and the current source’s derived context. Without a batch-level snapshot and stable order, candidate storage cannot prove which mutable requests and source facts the proposal used after a reviewer edits the ledger or an active candidate changes.

## Input

- **Step 1 ledger contract:** Consume step 1’s canonical ledger digest, immutable reviewer-item snapshot shape, target fingerprint, eligibility predicate, derived-feedback representation, and `check_ledger_processing_ready` refusal helper. The landed step 1 contract wins over names suggested by this detail.
- **Step 2 enrollment boundary:** Consume step 2’s feedback-free accepted-root content and its migration boundary. This builder must not fall back to embedded artifact feedback.
- **Immutable source content:** Retain `plan_tool/roadmap_versions.py:ResolvedRoadmapVersion`, `StoredRoadmapVersion`, and `AcceptedRoadmapHead` as the source-content and accepted-root contracts. Continue validating stored bytes before reading them.
- **Existing context projection:** Reuse the relevant projection rules in `plan_tool/roadmap_candidate_context.py:_verify_predecessor`, `_resolve_closure`, `_project_members`, `_render_payload`, and `_canonical_json_bytes` where they still fit a batch. Replace selector-specific assumptions rather than keeping a parallel context format.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_candidate_context.py` — Replace single-feedback context compilation with immutable root/source batch construction, canonical payload rendering, receipts, and fail-closed validation.
  - `tests/test_roadmap_candidate_context.py` — Replace selector-focused fixtures and assertions with root/source, ledger, derived-context, ordering, identity, and refusal coverage.

## Implementation

- **Build one batch from one processing pair.** Make the public batch-building entry point accept the accepted root, the direct source selected from that root and any active candidate, and the canonical ledger snapshot. The result must bind both root and source revision identities; the direct source is the accepted root when no active candidate exists and the active candidate when one exists.

- **Refuse before any batch work when migration is pending.** Call step 1's `check_ledger_processing_ready` first. A `migration-required` result must return immediately with no eligibility filtering, no derived-context read, no capsule, and no backend call — this is the one place every ordinary-feedback and candidate-creation path funnels through, so it is where the plan's migration fence is actually enforced for steps 4 and 5.

- **Replace single-item selection with eligibility filtering.** Retire the `build_candidate_context` assumption that `plan_tool/roadmap_feedback.py:parse_feedback_selector` and `_select_feedback` choose exactly one open embedded row. Use step 1’s eligibility contract to include only eligible reviewer-created open items, preserving ineligible items as ledger state rather than treating them as failures or retargeting them. The selector form of `build_candidate_context` (root plus one feedback selector, no ledger) stays as an explicit legacy boundary: roadmaps that have no ledger, and their stored selector-era candidates, are read through it, and it is called only when no ledger is supplied. Every ledger-bearing caller uses the batch form; a selector-form call that is given a ledger is a batch call.

- **Include current derived context separately.** Read derived feedback only from the direct source’s revision-bound set. Preserve nondeleted derived entries in the batch even when there are no eligible reviewer-created items; do not carry derived entries forward from another source or infer them from older candidate history.

- **Make ordering explicit and stable.** Order reviewer snapshots and derived context by the canonical ordering supplied by their owning contracts, then use that order consistently in the payload, receipt, identity input, and tests. Do not depend on mapping iteration, filesystem order, or the order in which closures happen to resolve.

- **Keep exact immutable evidence.** Extend the capsule and receipt records near `CandidateContextCapsule` and `CandidateContextReceipt` so they expose the root id, source id, whole-ledger digest, ordered reviewer snapshots, and ordered derived context. Preserve strict frozen records and canonical JSON through `_canonical_json_bytes`; the batch digest must change when any bound input changes.

- **Preserve byte and source validation.** Keep `_verify_predecessor` as the gate for source bytes, digests, UTF-8, parsed artifacts, and artifact ordering. Apply the existing `CANDIDATE_CONTEXT_MAX_BYTES` rule to the complete batch payload. An over-budget outcome must expose safe membership evidence without returning partial model-facing content.

- **Return deterministic no-work only for an empty complete batch.** When there are zero eligible reviewer-created open items and zero nondeleted derived entries, return a distinct non-writing no-work result. It must not create a capsule, call a backend, mutate the ledger, change a candidate pointer, or advance the accepted head. A batch containing either input family is not no-work.

- **Fail closed on inconsistent inputs.** Refuse a root/source pair that does not match the declared ancestry, malformed or inconsistent ledger data, changed target fingerprints, invalid source content, or a payload that exceeds the fixed ceiling. Do not substitute live artifacts, later ledger bytes, or a different active candidate to recover.

- **Keep projection behavior narrow.** Continue using the established impact-closure and member-projection rules only to provide roadmap context for the selected direct source. Do not add candidate storage, active-pointer writes, review behavior, ledger mutation, or a second version-chain mechanism in this module.

## Tests

- `test_batch_refuses_migration_pending_roadmap_before_any_eligibility_or_derived_context_work` — asserts a `migration-pending` ledger state returns the deterministic `migration-required` result before eligibility filtering, derived-context reads, or a capsule.
- `test_batch_uses_accepted_root_when_no_active_candidate_exists` — asserts the root is both root and direct source when no active candidate is supplied.
- `test_batch_uses_active_candidate_as_direct_source_and_retains_root_identity` — asserts an active candidate changes only the direct source while preserving the accepted-root binding.
- `test_batch_snapshots_every_eligible_reviewer_item_in_canonical_order` — asserts all and only eligible open reviewer items appear in stable order.
- `test_batch_excludes_ineligible_reviewer_item_without_mutating_ledger_state` — asserts stale, deferred, closed, or fingerprint-mismatched items are absent without being changed.
- `test_batch_includes_nondeleted_current_derived_context_without_reusing_prior_source_context` — asserts derived entries come only from the direct source and honor deletion state.
- `test_batch_no_work_requires_zero_eligible_items_and_zero_nondeleted_derived_entries` — asserts each nonempty input family prevents no-work, while an entirely empty batch returns the deterministic non-writing result.
- `test_batch_payload_and_receipt_bind_root_source_ledger_and_ordered_inputs` — asserts changing any bound identity, ledger digest, reviewer snapshot, or derived entry changes the immutable batch evidence.
- `test_batch_order_is_repeatable_across_equivalent_inputs` — asserts equivalent inputs produce identical payload bytes, receipt, and batch identity.
- `test_batch_refuses_mismatched_processing_pair_without_partial_payload` — asserts an inconsistent root/source relationship returns a refusal with no capsule.
- `test_over_budget_batch_reports_safe_membership_without_model_content` — asserts the ceiling refusal retains inspectable membership facts but no partial payload.
- `test_candidate_context_batch_contract` — runs every changed case in `tests/test_roadmap_candidate_context.py` green before this step is complete.

## Acceptance criteria

- A `migration-pending` roadmap refuses with the deterministic `migration-required` result before any eligibility, derived-context, or capsule work — the one gate every ordinary-feedback and candidate-creation path funnels through.
- A context result binds one accepted-root revision, one direct-source revision, one canonical ledger digest, ordered eligible reviewer snapshots, and ordered current derived context.
- The direct source is the accepted root without an active candidate and the active candidate when one is present.
- Eligible reviewer items and nondeleted derived entries use stable canonical order in both payload and receipt.
- Later edits to the ledger, target fingerprints, derived context, root, or active source cannot alter an already-issued batch.
- A batch returns deterministic no-work only when both its eligible reviewer-item set and its nondeleted derived-context set are empty.
- No-work creates no capsule and performs no backend call, candidate write, ledger mutation, pointer change, or accepted-head change.
- Invalid source bytes, invalid processing pairs, inconsistent snapshots, and over-budget payloads return fail-closed outcomes without a partial model-facing payload.
- `tests/test_roadmap_candidate_context.py` passes.

## References

- [Models — Pydantic Documentation](https://docs.pydantic.dev/latest/concepts/models/) — Read strict, frozen model configuration for immutable batch and receipt records.
- [json — JSON Encoder and Decoder](https://docs.python.org/3.13/library/json.html) — Read stable JSON serialization options for exact payload bytes.
- [RFC 8785: JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785.html) — Use as the reproducibility reference for canonical batch identity inputs.
- [hashlib — Secure Hashes and Message Digests](https://docs.python.org/3.13/library/hashlib.html) — Read SHA-256 byte-digest behavior for batch evidence.

## Applicable guardrails

- **The plan’s “## Scope guardrails”, accepted-head authority:** This step must treat `AcceptedRoadmapHead` as the canonical-artifact selector and must not create a competing selector or version chain.
- **The plan’s “## Scope guardrails”, exact candidate evidence:** This step must bind one root, one direct source, and one immutable ledger snapshot without substituting later reviewer or derived-context data.
- **The plan’s “## Scope guardrails”, unrelated ledger edits:** This step must record the whole-ledger digest as evidence only; it must not make unrelated later edits a batch-construction or future-storage refusal condition.
- **The plan’s “## Out of scope”, candidate lifecycle scope:** This step must not add structural classification, automatic retargeting, concurrent branches, stage-operation changes, or general review protocol behavior.

## Deferred

- Candidate storage, active-pointer publication, and admitted-item response transitions — step 5 owns the guarded persistence operation.
- Successor artifact construction and response-patch validation — step 4 owns proposal materialization from this batch.
- Reviewer ledger editing and legacy migration — step 6 owns mutable ledger operations and compatibility handling.
- Candidate questions, rejection, and discard resolution — step 8 owns the focused review lifecycle.
