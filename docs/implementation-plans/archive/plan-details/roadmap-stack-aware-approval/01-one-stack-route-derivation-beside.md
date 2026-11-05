> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Derive a candidate's unpromoted stack route beside `source_ancestry_to_root`

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step adds one read-only derivation to `plan_tool/roadmap_candidate_run.py`, placed next to `source_ancestry_to_root`. It takes a candidate (the tip) and its recorded root, and returns the ordered unpromoted hops above that root, up to and including the tip. Its answer, `is_structural`, is true when any hop has a stored `operation_classification` of STRUCTURAL. The main design decision is that an unreadable hop raises `CandidateProposalError` and is never a return value, so no caller can read "cannot tell" as "not structural". When the step is done, one function answers "is this stack structural?" for the guards, the promotion boundary, recovery, and the stack view, and tests in `tests/test_roadmap_candidate_run.py` pin that answer. No existing behavior changes.

## Table of Contents

- [Summary](#summary) — what the step adds and the key decision
- [Table of Contents](#table-of-contents) — this list
- [Why](#why) — the gap the derivation closes
- [Input](#input) — the stored evidence the derivation reads, and what the tests here cannot show
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files this step touches
- [Implementation](#implementation) — approach, design decisions, constraints, and sites left alone
- [Tests](#tests) — test cases, the test-setup constraint, and the green gate
- [Acceptance criteria](#acceptance-criteria) — observable checks
- [References](#references) — the plan, the ledger, and the consumer modules
- [Applicable guardrails](#applicable-guardrails) — the plan fences that bind this step
- [Deferred](#deferred) — work other steps own

## Why

Every guard that decides whether a candidate needs a structural decision reads only that candidate's own stored route. `source_ancestry_to_root` already walks a candidate's chain, but it returns ids only, so no code answers "does any unpromoted hop under this candidate carry a structural route?". Left as is, steps 2, 3, and 4 would each walk the chain themselves. The promotion writer and the recovery predicate could then disagree on whether a promotion needs its seed-state effect. This step supplies the single shared answer so they cannot. No stack-route symbol exists in `plan_tool/` or `tests/` at HEAD. The already-implemented signal fires only because the step title names `source_ancestry_to_root`.

## Input

- **Stored route evidence.** `CandidateProposalEvidence` in `plan_tool/roadmap_candidate_run.py` carries `operation_classification`, `normalized_operations`, `root_version_id`, `source_version_id`, and `batch_receipt`.
  - **"No stored route" is one shape.** `operation_classification is None`. The model validator `_requires_exact_bindings` forces `normalized_operations` and `operation_classification` to be both present or both absent on batch evidence, and forbids route facts on selector-era evidence.
  - **Three kinds of candidate carry no route.** Legacy batch evidence, an answered replacement (`plan_tool/roadmap_candidate_review.py:_store_batch_replacement` stores a `CandidateProposalEvidence` with both fields absent), and selector-era evidence.
- **Trust in a stored route.** `load_stored_candidate_proposal` runs `_validate_candidate_evidence`, which for batch evidence calls `_require_reproducible_batch_operations`. That function replays the stored operations and refuses a route that does not match them. A stored route is therefore only as trustworthy as the loader that read it.
- **Chain shape.** `source_ancestry_to_root` returns the predecessor ids from the source's immediate predecessor through the root, inclusive, and `()` when the source is the root. It refuses a missing, non-candidate, cyclic, or root-missing chain with `CandidateProposalError`.
- **Recovery's error handling.** `plan_tool/roadmap_revision_publish.py:_selected_promotion_is_structural` catches `(OSError, ValueError)` and returns `None` (unknown). `CandidateProposalError` is a `ValueError`, so an underivable stack already lands in that "unknown" branch when step 3 wires the derivation in.
- **Limit of this step's tests.** They show the derivation's answer over real stored chains. They cannot show that the writer and recovery agree, because neither consumes the derivation until steps 2 and 3.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/roadmap_candidate_run.py`: add a small frozen result type and the derivation function directly after `source_ancestry_to_root`. No new imports are needed (`roadmap_candidate`, `StoredCandidateProposal`, `load_stored_candidate_proposal`, and `CandidateProposalError` are already in the module).
  - `tests/test_roadmap_candidate_run.py`: add the derivation tests and one small fixture helper for building a stack the interim batch block would otherwise refuse (see Tests).

## Implementation

**Behavior to deliver.** Given a tip version id and a recorded root id, return the unpromoted stack: the tip plus every stored candidate between the tip and the root, with the root excluded. The result reports whether any hop is structural. Recommended names: `candidate_stack_route(*, plans_dir, slug, tip_version_id, root_version_id)` returning a frozen `CandidateStackRoute` with `hops` and an `is_structural` property. Names are the implementer's call. The behaviors below are not.

- **Hop set and order.**
  - The hops are the tip and the candidates below it, down to but not including the root. In `source_ancestry_to_root(source_version_id=tip, ...)` terms, that is the tip followed by the returned ids minus the final one, which is the root.
  - `hops` is ordered oldest first, with the tip last. Step 4's view reads this order, so it is fixed here.
- **Nothing to derive.**
  - When `tip_version_id == root_version_id`, return an empty stack and read nothing. The root is never loaded as a hop, and its stored route, or lack of one, is never read. The root can be an enrolled root, a previously promoted structural candidate, or a settlement-published head.
  - When `root_version_id is None` (selector-era evidence records no root), also return an empty stack. The `None` case lives inside the function so five or more call sites do not each repeat the carve-out.
- **Loading each hop.**
  - Load each hop with `load_stored_candidate_proposal`. Do not read `candidate_evidence_path` directly, because that skips the route replay that makes a stored route trustworthy.
  - Keep each hop as the loaded `StoredCandidateProposal` in `hops`. Step 4 reads the id, route, and diff off it without a second validated load. Adding a separate hop record type is the rejected alternative, since it would have no reader beyond what the candidate already carries.
- **The answer.** `is_structural` is true when any hop's `evidence.operation_classification` is STRUCTURAL. A hop whose route is `None` contributes nothing. It is not presentation-only, and it is not unknown. It still appears in `hops`.
- **Underivable stacks.** Any failure from the chain walk or from a hop load propagates as `CandidateProposalError`.
  - **What "unreadable" covers.** A missing hop, a hop that is not a stored candidate, a hop that fails validation (including a forged route), a chain that does not reach the declared root, and an unknown tip.
  - **No swallowing.** The function must not catch these and fall back to "not structural". That is the failure the plan's Risks section names: a promotion finishing without its seed effect.
  - **No new wrapper.** Do not wrap the loader's errors in a new type unless a test shows a case escaping as something other than `CandidateProposalError`. The channel matches `source_ancestry_to_root` and `load_stored_candidate_proposal`, which every existing caller already handles.

**Approach.** One way to do it:
- Call `source_ancestry_to_root` for the chain, so cycle, kind, and root-reachability checks stay in one place.
- Load hops oldest first.
- Build the frozen result.

**Rejected alternatives.**
- Returning `bool | None`, or a tri-state enum for underivable. Both are coercible with `if not result`, which is the silent misreading the plan fences.
- Returning only a bool. Step 4 would then walk the chain again, giving two walks that can disagree.
- A candidate-based signature. The edit check needs the stack of its source, which can be the root itself, before the replacement is stored. An id-based signature serves that call with no branch.

**Constraints (not free to vary).**
- **Route source.** Read routes only from stored evidence. Do not call `_classify_validated_operations` (`plan_tool/roadmap_candidate.py`) here. A recomputed or cumulative classifier is fenced by the plan.
- **No head or pointer reads.** The function must not consult the accepted head or the candidate admission pointer. The answer must be identical before promotion, after promotion, and during recovery, and depends only on the two ids passed in.
- **No persisted state.** Nothing new is written and nothing is cached. Stored versions are immutable, so recomputing is always correct. Cost grows with stack height because each hop's validated load re-walks its own ancestry.
- **Import direction.** `plan_tool/roadmap_revision_publish.py` imports `plan_tool.roadmap_candidate_run` lazily inside functions, and `roadmap_candidate_run` imports the publisher at module level. Keep the new code in `roadmap_candidate_run.py` and add no import to the publisher in this step.
- **Comments.** Keep the docstring to a line or two and point at `docs/implementation-plans/2-roadmap-stack-aware-approval.md` (§ "Design decisions", Stack route) for the rest.

**Foundational logic and the sites left alone.** The foundational logic is "does a candidate's unpromoted stack carry a STRUCTURAL stored route". Sweeping `operation_classification` by identifier, and route / structural / own-source by vocabulary, gives these sites. This step edits none of them.
- `plan_tool/roadmap_candidate_review.py`: `_require_answered_review_route`, `_require_structural_candidate`, `_require_active_structural_candidate`, and the edit path's "structural edit replacement is not structural" refusal. Step 2 makes them stack-aware.
- `plan_tool/cli/roadmap_cmd.py`: the CLI precheck in `_cmd_roadmap_structural_candidate_decision` is step 2's. The own-route check in `_render_candidate_proposal_result` is step 6's.
- `plan_tool/roadmap_version_promotion.py`: `_load_complete_sealed_candidate` and `_structural_promotion_seed_member`. Step 3 changes them.
- `plan_tool/roadmap_revision_publish.py`: `_selected_promotion_is_structural`. Step 3 changes it.
- The answered-replacement refusal in `plan_tool/roadmap_candidate_review.py` stays own-route, as the plan's Guard sites table says.
- `_run_batch_candidate_proposal`'s structural block stays exactly as is. Step 7 retires it. It is not converted to a stack check.
- `_require_reproducible_batch_operations` is the trust basis for stored routes and stays unchanged.

**For the edit check.** Step 2 tests a not-yet-stored replacement by calling this derivation on the top candidate's source (`evidence.source_version_id`) with its recorded root, then combining the result with the replacement's own computed route. The derivation therefore must accept a source that is the root itself, returning an empty stack.

## Tests

All tests go in `tests/test_roadmap_candidate_run.py`, built on the existing helpers: `_store_first_batch_candidate`, `_store_two_hop_chain`, `_run_batch`, `_edit_stored_evidence`, `_snapshot`, and the `_FIRST_BATCH_DELTA` / `_SECOND_BATCH_DELTA` / `_STRUCTURAL_FIRST_BATCH_DELTA` fixtures. An empty-operations batch classifies as presentation-only.

**Test-setup constraint.** Until step 7 retires the block, the real runner refuses a second batch under a structural active candidate. A stack with a structural hop below its top therefore cannot be built through `_run_batch` alone.
- Add one small, clearly named fixture helper that stores the second hop while the block sees a non-structural active candidate.
- One way: wrap `roadmap_candidate_run.load_stored_candidate_proposal` in `monkeypatch.context()` around only that one `_run_batch` call, returning the real candidate with its route masked. The mask must not be active while the derivation runs, or the derivation sees masked routes.
- Another way: replicate the runner's source → `materialize_candidate` → `_store_batch_candidate` sequence.
- Step 7 removes the need for this helper.
- A second structural delta likely needs its own open ledger item, because the first delta answers `batch-one`. `_batch_item` builds one.

Test cases:

- `test_stack_route_of_the_root_itself_is_empty_and_reads_nothing` — a tip equal to the root, using an id that names no stored candidate, returns no hops and `is_structural` false without raising.
- `test_stack_route_with_no_recorded_root_is_empty_not_underivable` — a selector-era candidate (`root_version_id is None`) returns an empty, non-structural stack. This pins the no-recorded-root carve-out as distinct from the underivable cases below.
- `test_hops_are_ordered_oldest_first_end_at_the_tip_and_exclude_the_root` — over `_store_two_hop_chain`, the hop ids equal `(first, second)` and the root id is absent. This pins the ordering step 4 depends on.
- `test_a_structural_hop_below_a_presentation_only_tip_makes_the_stack_structural` — the C1-structural / C2-presentation stack is structural while the tip's own route is PRESENTATION_ONLY. This is the reported defect's shape.
- `test_any_hop_position_counts_and_an_all_presentation_stack_is_not_structural` — one parametrized case: a structural hop at the bottom, the middle, and the top of a stack makes it structural, and an all-presentation stack is not. It fails an implementation that checks only the tip or only the first hop.
- `test_a_hop_with_no_stored_route_contributes_nothing_in_either_direction` — a route-less hop, made by the evidence rewrite `test_a_second_batch_still_stacks_on_an_active_candidate_that_is_not_structural` already uses, is present in `hops` but changes neither answer. It matches the both-absent shape an answered replacement stores.
- `test_the_root_hops_own_structural_route_is_never_counted` — deriving with a structural candidate as the declared root leaves the stack non-structural, while the same tip over the enrolled root is structural. This stands in for a stack rooted at a previously promoted structural candidate.
- `test_stack_route_never_reads_the_current_head_or_the_active_pointer` — with `load_accepted_version` and `load_candidate_admission` replaced by failing stubs, the derivation still returns. This pins that the answer depends only on the two ids passed in.
- `test_an_unreadable_hop_makes_the_stack_underivable_and_is_never_read_as_not_structural` — one parametrized case where each variant raises `CandidateProposalError` and never returns a route:
  - a deleted lower hop (`shutil.rmtree(version_directory_path(...))`), matching "unreadable";
  - a lower hop with forged evidence (`_edit_stored_evidence` setting `operation_classification="structural"`), matching "route does not match its stored operations". The tip loads cleanly, so this proves each hop is loaded and validated rather than only the tip;
  - a wrong declared root, matching "trace to its declared root";
  - an unknown tip id, matching "unreadable".

**Verify by mutation.** Before calling the tests done, break the derivation four ways and confirm each turns a test red:
- treat a failed hop load as skipped;
- count the root's route;
- check only the tip;
- read the root from the admission pointer.

### Tests for this step

- **Tests added.** The nine cases above, in `tests/test_roadmap_candidate_run.py`. They cover the hop set and order, the structural answer at each position, the route-less and no-recorded-root carve-outs, the root-route and head/pointer invariants, and the underivable failure channel.
- **Existing tests.** The interim-block refusal tests and the stacking carve-out tests (`test_a_second_batch_is_refused_before_any_model_call_while_a_structural_candidate_is_active`, `test_a_second_batch_still_stacks_on_an_active_candidate_that_is_not_structural`) must stay green and unedited, because this step does not touch the block.
- **Green gate.** Every test above must be green before the step is done. The step's `test_command` is `uv run pytest tests/ -q -n auto`. The added tests also satisfy the plan's test-authoring gate.

## Acceptance criteria

- `plan_tool/roadmap_candidate_run.py` exposes one keyword-only derivation next to `source_ancestry_to_root`. It returns a frozen result with ordered `hops` and an `is_structural` answer.
- A tip equal to the root, or a root of `None`, returns an empty, non-structural stack and reads no stored version.
- `hops` is oldest first, ends at the tip, and never contains the root id.
- `is_structural` is true exactly when some hop's stored route is STRUCTURAL, including when only a lower hop is and the tip's own route is presentation-only.
- A hop with no stored route appears in `hops` and changes neither the true nor the false answer.
- A missing hop, a hop that fails validation, a chain that does not reach the declared root, and an unknown tip each raise `CandidateProposalError`. No code path returns a stack for them.
- The derivation makes no call to `load_accepted_version` or `load_candidate_admission`, and calls neither `_classify_validated_operations` nor any write.
- `git diff --name-only` for this step lists only `plan_tool/roadmap_candidate_run.py` and `tests/test_roadmap_candidate_run.py`. The batch block in `_run_batch_candidate_proposal` is unchanged.
- The full suite passes with `uv run pytest tests/ -q -n auto`.

## References

- [docs/implementation-plans/2-roadmap-stack-aware-approval.md](../../2-roadmap-stack-aware-approval.md) — § "Design decisions" (Stack route), "Guard sites", and Risks define what this derivation must and must not do.
- [handoffs/2026-09-23-roadmap-structural-feedback-approval-code-review.md](../../../../../handoffs/2026-09-23-roadmap-structural-feedback-approval-code-review.md) — the P2.1 defect and the owner decisions this step serves.
- [plan_tool/roadmap_candidate_run.py](../../../../../plan_tool/roadmap_candidate_run.py) — `source_ancestry_to_root`, `load_stored_candidate_proposal`, `CandidateProposalEvidence`, and the batch runner.
- [plan_tool/roadmap_revision_publish.py](../../../../../plan_tool/roadmap_revision_publish.py) — `_selected_promotion_is_structural`, the recovery predicate that consumes this derivation in step 3.
- [ROADMAP_FEEDBACK_FORMAT.md](../../../../../ROADMAP_FEEDBACK_FORMAT.md) — the feedback lifecycle and the batch stacking rule.

## Applicable guardrails

- **The plan's "Scope guardrails", "Not allowed": no new persisted stack or binding field.** The derivation is computed at use from stored records, and this step writes nothing.
- **The plan's "Scope guardrails", "Not allowed": no cumulative classifier derived from content, and no quality or semantic judgment of stack content.** This step reads only stored routes. It must not recompute or infer a route, and it must not read meaning into an absent one.
- **The plan's "Scope guardrails", "Not allowed": no change to the promotion writer, the publication journal, the recovery machinery, or the version and candidate stores.** This step adds a read-only function and touches none of them. Recovery's predicate is step 3's.
- **The plan's "Scope guardrails", "Not allowed": no behavior change for legacy candidates that have no route.** A route-less hop contributes nothing, and a selector-era candidate yields an empty stack.
- **The plan's "Scope guardrails", ordering fence.** The interim batch block stays in place. This step does not touch it, and no guard changes behavior until steps 2 and 3 consume the derivation.
- **The plan's "Out of scope": `_classify_validated_operations`, edit sourcing, and reject/discard pointer release stay unchanged.**

## Deferred

- Stack-aware guards at answered-route entry, decision eligibility, the CLI precheck, and the edit check — step 2 owns them.
- The promotion boundary, the seed-state member, and the recovery predicate reading this derivation — step 3 owns them.
- The stack view, its digest, and its printout, which read `hops` — step 4 owns them.
- Retiring the batch block and its refusal tests, and the end-to-end carve-out assertions across the direct, answered, edited, and recovered routes — step 7 owns them. This step asserts the root carve-outs only at the derivation.
- Caching or memoizing the derivation — not built. Stored versions are immutable, so recomputing is correct, and a cache would be shared state the plan does not want.
