> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Make the promotion boundary and the recovery predicate ask the whole stack

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step makes the promotion writer and the recovery predicate ask step 1's stack-route derivation instead of the promoted candidate's own stored route. It edits `plan_tool/roadmap_version_promotion.py` and `plan_tool/roadmap_revision_publish.py:_selected_promotion_is_structural`, plus their two test files. In the writer it changes three things: the answered-seal guard, the seed-state member, and one boundary check that requires a `structural-approval` seal for a structural stack. The main design decision is that writer and recovery ask with the same two inputs: the promoted candidate's own version id and its recorded root. That way they cannot disagree, and an underivable stack is a refusal on both sides, never "not structural". When the step is done, a presentation-only top over a structural hop promotes only under a `structural-approval` seal and journals the seed-state member. An answered seal over such a stack is refused with no write, and recovery of that journal demands the seed member. The head write, the journal, and the recovery machinery do not change.

## Table of Contents

- [Summary](#summary) — what the step changes and the key decision
- [Table of Contents](#table-of-contents) — this list
- [Why](#why) — the writer and recovery half of the reported defect
- [Input](#input) — the derivation, guards, and stored facts this step relies on, and what its tests cannot show
- [Files (creates vs edits)](#files-creates-vs-edits) — the four declared files
- [Implementation](#implementation) — behavior, approach, rejected alternatives, constraints, and the site sweep
- [Tests](#tests) — test roster, stack builder, mutation checks, and the green gate
- [Acceptance criteria](#acceptance-criteria) — observable checks
- [References](#references) — the plan and the modules involved
- [Applicable guardrails](#applicable-guardrails) — the plan fences that bind this step
- [Deferred](#deferred) — work other steps own, and what is deliberately not built

## Why

Three sites read only the promoted candidate's own stored route:
- the answered-seal guard in `_load_complete_sealed_candidate`;
- `_structural_promotion_seed_member` in `plan_tool/roadmap_version_promotion.py`;
- `_selected_promotion_is_structural` in `plan_tool/roadmap_revision_publish.py`.

Step 2 makes the decision surface accept a presentation-only top over a structural hop, so that top can now be sealed as `structural-approval`. Promoting that seal today moves the head to the top with no seed invalidation, because the top's own route is presentation-only. Recovery accepts a journal with no seed member for the same reason. This step closes both. Neither module consumes a stack-route symbol at HEAD, so none of this work is already done. The interim batch block stays until step 7, so until then the shape is reachable only through a test helper.

## Input

- **Step 1's derivation.** One read-only function beside `source_ancestry_to_root` in `plan_tool/roadmap_candidate_run.py`.
  - **Names.** Step 1 recommends `candidate_stack_route` returning a frozen `CandidateStackRoute` with `hops` and `is_structural`. Read the landed names off that module. The landed names win over any name in this file.
  - **Contract used here.** It takes a tip id and a root id as keywords. It returns an empty stack when the tip equals the root or the root is `None`. It raises `CandidateProposalError` for any unreadable hop, and it never reads the head or the admission pointer.
- **Step 2's shared guards.** `_require_structural_candidate` (which `_load_complete_directly_approved_candidate` already calls) and `_require_answered_review_route` in `plan_tool/roadmap_candidate_review.py`. After step 2 both are stack-aware, take required `plans_dir` and `slug`, and raise `CandidateReviewError`. Read the landed signatures.
- **Recorded root on both stored candidate types.** `StoredCandidateProposal.evidence` and `StoredCandidateReviewReplacement.evidence` each carry `root_version_id`. Selector-era evidence records none, so the derivation returns an empty stack.
- **Where an answered replacement sits in a chain.** `_store_batch_replacement` in `plan_tool/roadmap_candidate_review.py` sources the replacement from the reviewed candidate's own source. It also stores a route-less `CandidateProposalEvidence` at `candidate_evidence_path`.
  - `load_stored_candidate_proposal` therefore works on the head after an answered promotion, which is what recovery relies on.
  - The reviewed candidate is not in the replacement's chain. Its own hop is not part of the promoted stack.
- **Error classes.** `CandidateProposalError`, `CandidateReviewError`, and `RoadmapVersionPromotionError` are all `ValueError` subclasses. The `try` in `promote_review_seal` maps the first two to the third. `_structural_promotion_seed_member` sits outside that `try`.
- **Recovery's "unknown" channel.** `_selected_promotion_is_structural` returns `None` on `(OSError, ValueError)`.
  - `_is_completed_version_owned_generation` then accepts only the legacy selector-only case.
  - `_is_legacy_selector_only_promotion` declines whenever the candidate evidence file exists.
  - So `None` is a refusal for any head that has evidence, which is the fail-closed behavior this step keeps.
- **Pinned seam.** Existing tests in `tests/test_roadmap_revision_publish.py` patch `_selected_promotion_is_structural` by name with `lambda **_kwargs: True`. The name and keyword-only shape stay.
- **Limit of this step's tests.** They show writer and recovery behavior over real stored stacks built with a helper. They cannot show that a production command reaches the stack shape, because the batch block still refuses to build one. Step 7 owns that end to end. The own-hop refusal on the reviewed candidate rests on step 2's shared guard and is not exercised with that guard stubbed.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/roadmap_version_promotion.py`:
    - make the answered-seal guard in `_load_complete_sealed_candidate` stack-aware;
    - add one boundary check and one small helper that asks the derivation for the promoted candidate;
    - change `_structural_promotion_seed_member` to use that answer.
  - `plan_tool/roadmap_revision_publish.py`: make `_selected_promotion_is_structural` return the derivation's answer.
  - `tests/test_roadmap_version_promotion.py`: extend three existing tests over stack shape and add the writer and recovery cases below.
  - `tests/test_roadmap_revision_publish.py`: add predicate and recovery cases below.
- **Read only:** `plan_tool/roadmap_candidate_run.py` (step 1) and `plan_tool/roadmap_candidate_review.py` (step 2). This step edits neither. No file outside the declared list changes.

## Implementation

**Behavior to deliver.**
- **Seal requirement.**
  - `promote_review_seal` must refuse a promotion whose promoted candidate's stack is structural unless `seal.decision` is `structural-approval`.
  - The refusal is a `RoadmapVersionPromotionError` raised before the generation is built. Its text keeps `--decide-candidate`.
- **Seed member.** The seed-state member is journaled exactly when that stack is structural.
  - The answer comes from the derivation.
  - It must not come from the candidate's own route, and it must not come from the seal's `decision`.
- **Answered-seal guard.** `_load_complete_sealed_candidate` refuses an answered seal when the reviewed candidate's stack is structural at any hop, its own hop included.
- **Recovery predicate.** `_selected_promotion_is_structural` returns the derivation's answer for the head's version id and its recorded root, and `None` when it cannot tell.
- **Underivable stacks.** The writer raises `RoadmapVersionPromotionError`. The predicate returns `None`, which recovery already turns into a refusal. Neither reads it as "not structural".

**Approach.** One way to do it (the shape is the constraint, not the names):
- **Boundary check and seed member.**
  - Add one private helper in `plan_tool/roadmap_version_promotion.py`. It reads `candidate.evidence.root_version_id`, calls the derivation with the candidate's own `version_id`, and returns `is_structural`.
  - Call it inside the existing `try` in `promote_review_seal`, right after `_recheck_stored_candidate`.
  - Use the answer twice: refuse when it is true and `seal.decision != "structural-approval"`, then decide the seed member.
  - `_structural_promotion_seed_member` drops its `isinstance` and own-route test and takes the answer. The plans-artifact parse and the `build_enrolled_promotion_seed_state_member` call stay.
- **Answered-seal guard.**
  - Replace the inline own-route test on `initial` with a call to step 2's shared answered-route guard.
  - Keep the `is_batch` condition and the guard's position.
  - Its `CandidateReviewError` reaches the caller as a `RoadmapVersionPromotionError` with the same text.
  - The boundary then asks the same question, with the same inputs, as the answered-route entry.
- **Recovery.** Keep the load of the head's candidate, since it supplies the recorded root. Then call the derivation and return `is_structural`. Add the derivation to the existing in-function import and drop the `CandidateOperationClassification` import, which nothing else there uses.

**Why two derivations in the writer.**
- **On `initial`.** The answered guard derives on the reviewed candidate. That is the only check that sees an own-structural reviewed candidate, because the replacement's chain skips it.
- **On the promoted candidate.** The boundary check derives on the promoted candidate. That is the same question recovery can ask from the head alone.
- **Fixed by construction.** For a completed answered promotion both answers are "not structural", since the replacement's stack is a subset of the reviewed candidate's.

**Rejected alternatives.**
- **Key the seed member on `seal.decision`.** Recovery cannot see the seal, so the two predicates could then disagree.
- **Derive from `initial` at the writer and from the head at recovery.** The inputs differ for an answered promotion, which is the disagreement this step removes.
- **Read the root from the head or the admission pointer.** After promotion the head is the top and the pointer is released. Only the recorded root gives the same answer on both sides of promotion.
- **Merge the writer's and recovery's predicates into one function.**
  - The writer refuses with an error, and recovery reports "unknown". Those failure policies differ, so the two are look-alikes, not duplicates.
  - The one shared piece is the derivation.
- **Read a `None` or an error as "not structural" in recovery.** That finishes a promotion without its seed effect, which is the risk the plan names.

**Constraints (not free to vary).**
- **Same inputs.**
  - Tip is the promoted candidate's own version id. Root is its recorded `evidence.root_version_id`.
  - The head, the admission root, and the seal's root are not inputs.
- **Error placement.** The boundary derivation must run inside the `try` in `promote_review_seal`, before the `PendingGeneration` is built. A `CandidateProposalError` that escapes it is neither a `RoadmapVersionPromotionError` nor a refusal the CLI maps.
- **Recovery keeps its channel.** Keep `except (OSError, ValueError)` and the `None` result. Do not narrow the except and do not default to `False`.
- **Name and signature stay.** `_selected_promotion_is_structural(*, plans_dir, slug, version_id) -> bool | None`.
- **Import direction.** `plan_tool/roadmap_revision_publish.py` imports `plan_tool.roadmap_candidate_run` only inside functions, because `roadmap_candidate_run` imports the publisher at module level. Add no module-level import.
- **Nothing else moves.**
  - Journal member order stays selector, release, seed.
  - `_expected_completed_promotion_seed_member` is untouched.
  - `final_recheck` is untouched: stored versions are immutable, and its seal, head, and admission rechecks already bind the tip and the root.
- **No new state.** Nothing is persisted or cached.

**Foundational logic and the sites.** The logic is "does the promoted candidate's unpromoted stack carry a STRUCTURAL stored route, and so need a structural-approval seal and the seed effect". A sweep of `operation_classification` by identifier, and of route, structural, own source, and seed by vocabulary, gives these sites.
- **Changed here:**
  - the answered-seal guard in `_load_complete_sealed_candidate`;
  - `_structural_promotion_seed_member`;
  - `_selected_promotion_is_structural`.
- **Changed through step 2, no edit here:** `_load_complete_directly_approved_candidate` calls the shared `_require_structural_candidate`.
- **Stays as is, deliberately:**
  - The decision-settlement and root-enrollment branches of `_is_completed_version_owned_generation` publish their own heads through routes the plan leaves unchanged.
  - `_expected_completed_promotion_seed_member` and the `review-seal-promotion` member order carry no route logic.
  - The other seed-invalidation writers in `plan_tool/roadmap_revision_publish.py` serve unenrolled local revisions and never see a candidate-lineage promotion.
  - `_recheck_stored_candidate` replays only the promoted candidate's own operations.
- **Owned by other steps:**
  - The proposal output and CLI sites are steps 2 and 6.
  - The batch block in `_run_batch_candidate_proposal` is step 7.

**Interim reachability.** Production still seals and promotes in one invocation through the CLI approve, and the batch block still refuses to stack under a structural candidate. The stacked shape therefore reaches this code only through tests until step 7.

## Tests

Cases live in `tests/test_roadmap_version_promotion.py` (real stacks) and `tests/test_roadmap_revision_publish.py` (the predicate, with fakes).

**Stack builder (promotion tests).** Add one helper beside `_direct_structural_approval`. It builds C1 structural under a presentation-only C2, approves C2 with `decide_structural_candidate`, and returns `(root, C2, seal)`.
- **Masking helper.** The batch block refuses a second batch under a structural active candidate. Reuse the masking helper step 1 adds to `tests/test_roadmap_candidate_run.py`. Read its landed name and import it the way this module imports `_run_batch`.
- **Second hop.** `_SECOND_BATCH_DELTA` has no operations, so it classifies as presentation-only.
- **Fixture check.** The helper asserts its own shape: C2's stored route is presentation-only, and the derivation reports C2's stack as structural. A helper that silently built the wrong stack would otherwise let every case pass without testing anything.
- **Gates.** `check_complete_roadmap_gates` stays patched to `_green_gates` in this module.

**Promotion cases (`tests/test_roadmap_version_promotion.py`).** Extend the three existing tests in place with a stack-shape parameter, keeping the own-structural case first so its assertions do not change.
- `test_promotion_promotes_the_directly_approved_initial_structural_candidate_with_seed_invalidation` — over own-structural top and presentation-only top over a structural hop, the journal carries selector, release, and seed members, and tracked seeds end `invalidated`. Only the second shape fails today.
- `test_completed_direct_structural_promotion_recovery_requires_exact_three_members` — over the same two shapes, the complete journal recovers, and both incomplete variants, including the one without the seed member, refuse and leave the journal.
- `test_answered_seal_cannot_promote_a_structural_initial_candidate` — over own-structural initial and presentation-only initial over a structural hop, `RoadmapVersionPromotionError` naming `--decide-candidate` and an unchanged tree. Mint the second shape's seal under the same "seal issued before the entry guard" stub, widened by step 2.

New cases:
- `test_seal_requirement_holds_at_the_boundary_when_the_review_guards_are_bypassed` — with `_require_answered_review_route` and `_require_structural_candidate` stubbed to no-ops for the whole flow, an answered seal over the stacked shape is still refused. Choose the replacement reply so it classifies presentation-only over C1, or `request_replacement` refuses it first. This pins the boundary check independently of the loader guards.
- `test_promotion_refuses_an_underivable_stack_as_a_promotion_error_with_no_write` — parametrized over review guards live and bypassed. After C2's approval seal, forge C1's stored evidence with `_edit_stored_evidence` so its route disagrees with its stored operations.
  - `_promote` raises `RoadmapVersionPromotionError`, never a raw `CandidateProposalError` or `CandidateReviewError`.
  - The head, admission, seed state, and journal are unchanged.
  - The bypassed variant pins that the boundary derivation runs inside the `try`.
- `test_all_presentation_stack_promotion_journals_no_seed_member_and_recovers_with_two_members` — carve-out over the multi-hop builder `_sealed_two_hop_replacement`. Members are selector and release only, and the captured journal recovers as complete.
- `test_a_stack_rooted_at_a_promoted_structural_candidate_does_not_count_the_roots_route` — carve-out.
  - After a direct structural promotion the head is C1. A presentation-only batch over it goes through the answered route: compose the calls `_batch_review` and `_request_batch_replacement` make, then seal.
  - It promotes with no seed member, and its journal recovers with two members.
  - It fails an implementation that counts the root's route or walks past the recorded root.
- `test_writer_and_recovery_derive_from_the_same_tip_and_recorded_root` — spy on the derivation through the `roadmap_candidate_run` module attribute, calling through to the real function. Over the direct stacked shape, the writer's calls all use one `(tip, root)` pair. Recovery of the captured journal uses the same pair, and its root differs from the head at recovery time.

**Predicate cases (`tests/test_roadmap_revision_publish.py`).** Stub `load_stored_candidate_proposal` and the derivation on `plan_tool.roadmap_candidate_run`, which the predicate imports at call time. Give the head, the admission, and the stub's recorded root distinct ids.
- `test_promotion_structural_predicate_asks_for_the_promoted_id_and_its_recorded_root` — keywords are `plans_dir`, `slug`, the head's version id as tip, and the loaded evidence's `root_version_id` as root.
- `test_promotion_structural_predicate_returns_the_stack_answer_not_the_tops_own_route` — parametrized: a presentation-only top with a structural stack gives `True`, and a route-less top with a non-structural stack gives `False`.
- `test_promotion_structural_predicate_reports_an_underivable_stack_as_unknown_never_as_false` — a derivation raising `CandidateProposalError` gives `None`. A load raising `CandidateProposalError` or `OSError` also gives `None`, with the derivation never called.
- `test_structural_promotion_recovery_refuses_a_missing_seed_member_through_the_real_predicate` — a structural stack answer from the stubs and a selector-only journal: recovery refuses and leaves the journal. The existing test monkeypatches the predicate itself, so it does not cover this wiring.
- `test_recovery_refuses_an_underivable_stack_even_when_the_top_loads` — the top loads, the derivation raises, and an evidence file exists so the legacy check declines. Recovery raises `RoadmapPublicationRecoveryError` and the tree is unchanged.

**Existing tests that must stay green and unedited.**
- **Route-less and single-hop carve-outs (promotion):**
  - `test_route_less_batch_candidate_keeps_the_answered_route_through_promotion`
  - `test_promotion_promotes_a_sealed_batch_replacement_and_moves_only_the_selector_and_the_pointer`
  - `test_promotion_requires_an_active_matching_writer_token_and_writes_only_the_selector`
  - `test_edited_structural_candidate_needs_its_own_approval_before_promotion`
- **Selector-only recovery and predicate-patching (recovery):**
  - `test_completed_review_seal_promotion_journal_is_dropped_without_touching_members`
  - `test_completed_structural_promotion_seed_journal_is_dropped_without_touching_members`
  - `test_structural_promotion_recovery_refuses_missing_seed_invalidation`

**Verify by mutation.** Break the code each of these ways and confirm each turns a test red:
- revert `_selected_promotion_is_structural` to the own route;
- read an error as `False` in the predicate;
- revert the seed member to the own route;
- revert the answered guard to an own-route check;
- delete the boundary seal check;
- move the boundary derivation outside the `try`;
- derive recovery's root from the head or the admission pointer.

### Tests for this step

- **Tests added or changed.** Three extended in place and five new in `tests/test_roadmap_version_promotion.py`. Five new in `tests/test_roadmap_revision_publish.py`. That is about thirteen functions, plus one stack-builder helper.
- **What they cover.** Both writer routes over both stack shapes, the seal requirement at the boundary, the underivable channel, the carve-outs, writer and recovery agreement, and the predicate's failure mapping.
- **Green gate.** Every test above and the rest of the suite must be green before the step is done. The step's `test_command` is `uv run pytest tests/ -q -n auto`. The added tests also satisfy the plan's test-authoring gate.

## Acceptance criteria

- **Stacked direct approval.**
  - A `structural-approval` seal on a presentation-only top over a structural hop promotes.
  - The journal holds exactly the selector, release, and seed members, and the head is the top.
- **Answered seal refused.**
  - An answered seal whose reviewed candidate's stack is structural at any hop, its own included, raises `RoadmapVersionPromotionError` naming `--decide-candidate`.
  - The head, admission, seed state, and journal are unchanged.
- **Boundary stands alone for the promoted candidate's stack.** A structural lower hop is still refused with the review-side guards stubbed out. The own-hop refusal on the reviewed candidate depends on step 2's shared guard and is not covered when that guard is stubbed.
- **Underivable refused.**
  - An underivable stack raises `RoadmapVersionPromotionError`, never a raw `CandidateProposalError`, with no write.
  - This holds with the review-side guards live or stubbed out.
- **Recovery predicate.**
  - `_selected_promotion_is_structural` keeps its name and keyword-only signature.
  - It returns the derivation's answer, and `None` when it cannot tell.
  - It never returns `False` for an underivable stack.
- **Recovery journal.**
  - Recovery accepts the complete three-member journal for the stacked shape.
  - It refuses the same journal without the seed member and leaves it in place.
- **One question.** The writer and recovery ask the derivation with the same tip and recorded root, and never with the head.
- **Carve-outs.** All-presentation stacks, legacy route-less candidates, selector-era candidates, and a stack rooted at a previously promoted structural candidate keep journals with no seed member, and the writer refuses none of them.
- **Footprint.** `git diff --name-only` lists only the four declared files. `plan_tool/roadmap_revision_publish.py` gains no module-level import of `plan_tool.roadmap_candidate_run`.
- **Suite.** `uv run pytest tests/ -q -n auto` passes.

## References

- [docs/implementation-plans/2-roadmap-stack-aware-approval.md](../../2-roadmap-stack-aware-approval.md) — § "Design decisions" (Stack route, Guards), "Guard sites", and Risks define what the boundary and recovery must and must not do.
- [docs/implementation-plans/plan-details/roadmap-stack-aware-approval/01-one-stack-route-derivation-beside.md](01-one-stack-route-derivation-beside.md) — step 1's derivation contract and the masking helper this step's tests reuse.
- [docs/implementation-plans/plan-details/roadmap-stack-aware-approval/02-make-review-side-guards-stack-aware.md](02-make-review-side-guards-stack-aware.md) — step 2's shared guards, their signatures, and the deferral to this step.
- [handoffs/2026-09-23-roadmap-structural-feedback-approval-code-review.md](../../../../../handoffs/2026-09-23-roadmap-structural-feedback-approval-code-review.md) — the P2.1 defect and the owner decisions.
- [plan_tool/roadmap_version_promotion.py](../../../../../plan_tool/roadmap_version_promotion.py) — the candidate-lineage promotion writer and the seed-state member.
- [plan_tool/roadmap_revision_publish.py](../../../../../plan_tool/roadmap_revision_publish.py) — `_selected_promotion_is_structural` and `_is_completed_version_owned_generation`.
- [ROADMAP_FEEDBACK_FORMAT.md](../../../../../ROADMAP_FEEDBACK_FORMAT.md) — the feedback lifecycle and the batch stacking rule.

## Applicable guardrails

- **The plan's "Scope guardrails", binary observable and mechanism.** The promotion boundary in `plan_tool/roadmap_version_promotion.py` stays the sole writer of candidate-lineage promotions. This step adds the seal requirement and the seed effect to that writer, and the recovery predicate consumes the same derivation.
- **The plan's "Scope guardrails", "Not allowed": no change to the promotion writer's authority, the journal, or the recovery machinery beyond the structural predicate it consults.** Journal kind, member order, the head write, and `_expected_completed_promotion_seed_member` stay as they are. Only the structural predicate and the seed member's trigger change.
- **The plan's "Scope guardrails", "Not allowed": no second structural gate and no separate approval per hop.** The boundary check requires the one existing `structural-approval` seal on the top candidate.
- **The plan's "Scope guardrails", "Not allowed": no cumulative classifier and no new persisted stack or binding field.** Both consumers read stored routes through step 1's derivation and store nothing.
- **The plan's "Scope guardrails", "Not allowed": no behavior change for legacy candidates that have no route.** A route-less or selector-era candidate contributes nothing and yields the journals it yields today.
- **The plan's "Scope guardrails", ordering fence.** The batch block stays until step 7. This step lands the writer and recovery guards that its removal depends on.
- **The plan's "Out of scope", earlier single-command seals.** An unpromoted seal from the earlier approve stays promotable while its candidate is still the active one. This step adds no migration.

## Deferred

- The stack view, its digest, and its shared printout — step 4 owns them.
- The two-invocation approve and the confirm flag that mint the seal — step 5 owns them. This step consumes the seal as it exists.
- Stack output on the decision surfaces and the proposal output — step 6 owns it.
- Retiring the batch block, and end-to-end tests of the direct, answered, edited, and recovered routes — step 7 owns them. This step pins the writer and recovery layers only.
- Documentation of the two-invocation approve and the whole-stack scope — step 8 owns it.
- Folding the writer's and recovery's structural predicates into one function — not built. Their failure policies differ, and the derivation is the shared piece.
- Reducing the repeated loads of the head's candidate during recovery — not built. Recovery reads a journal only when one is pending, and stored versions are immutable, so recomputing is correct.
