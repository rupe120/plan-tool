> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Make the review-side guards ask about the whole unpromoted stack

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step changes the review module's route guards from "is this candidate's own route structural?" to "does this candidate's unpromoted stack carry a structural route?". It edits `plan_tool/roadmap_candidate_review.py` and the CLI precheck in `plan_tool/cli/roadmap_cmd.py`. The guards it changes are the answered-route entry guard, the shared `_require_structural_candidate` and `_require_active_structural_candidate` guards, and the edit replacement check. All of them ask step 1's derivation through one helper that turns an underivable stack into a refusal, so no guard can read "cannot tell" as "not structural". When the step is done, the answered route refuses a structural stack and the structural decision accepts a presentation-only top of one. An edit is judged by its replacement's stack. Edit sourcing, reject/discard release, and all promotion behavior stay as they are.

## Table of Contents

- [Summary](#summary) — what the step changes and the key decision
- [Table of Contents](#table-of-contents) — this list
- [Why](#why) — the review-side half of the reported defect
- [Input](#input) — the derivation and stored facts the guards rely on, and what the tests here cannot show
- [Files (creates vs edits)](#files-creates-vs-edits) — the declared files, two of them mechanical additions
- [Implementation](#implementation) — behavior, approach, constraints, and the sweep of own-route sites
- [Tests](#tests) — test roster, stack builders, and mutation checks
- [Acceptance criteria](#acceptance-criteria) — observable checks
- [References](#references) — the plan, the ledger, and the modules involved
- [Applicable guardrails](#applicable-guardrails) — the plan fences that bind this step
- [Deferred](#deferred) — work other steps own

## Why

Every guard that gates the answered route or the structural decision reads only the candidate's own stored route. A presentation-only C2 stacked on a structural C1 therefore passes `_require_answered_review_route`, and `--decide-candidate C2` is refused by `_require_structural_candidate`. This step closes the review-side half: the answered route refuses the stack, and the decision surface accepts it. The promotion boundary and recovery are step 3's. The interim batch block in `_run_batch_candidate_proposal` stays until step 7, so between this step and step 7 the newly accepted stack shape is reachable only through a test helper. No stack-route symbol exists in the review module or the CLI at HEAD, so nothing here is already done.

## Input

- **Step 1's derivation.** Step 1 adds one read-only function beside `source_ancestry_to_root` in `plan_tool/roadmap_candidate_run.py`.
  - **Names.** Step 1 recommends `candidate_stack_route` returning a frozen `CandidateStackRoute` with `hops` and `is_structural`. Read the landed names off that module. The landed names win over any name in this file.
  - **Contract used here.** The function takes a tip id and a root id, both as keywords. It returns an empty stack when the tip equals the root or the root is `None`. It raises `CandidateProposalError` when any hop is unreadable. It never returns a value for an underivable stack.
- **Stored evidence facts.**
  - **Batch evidence always records a root.** `CandidateProposalEvidence` validates `root_version_id` against the batch receipt's root.
  - **Route is present or absent as a pair.** `normalized_operations` and `operation_classification` are both present or both absent. Legacy batch evidence and answered replacements carry neither.
  - **Selector-era evidence records no root.** Passing its `root_version_id` straight to the derivation yields an empty stack, so no guard needs a batch-versus-selector branch.
- **How a tip load and the derivation differ.** `load_stored_candidate_proposal` runs `_validate_candidate_evidence`, which walks the tip's ancestry at record level through `source_ancestry_to_root`. A deleted lower hop therefore fails the tip's own load before any guard runs. A lower hop whose stored route no longer matches its stored operations loads fine as part of a chain walk and fails only when the derivation loads that hop with full validation. Tests for the guard's underivable channel must use the second kind (see Tests).
- **Two error classes.** `CandidateProposalError` and `CandidateReviewError` are both `ValueError` subclasses but neither derives from the other.
  - **Entries that catch only `CandidateReviewError`.** The answered-route entries (`generate_candidate_question`, `record_reviewer_answer`, `request_replacement`, `seal_review`) and the decision branches map a caught `CandidateReviewError` to a `refused` result. They do not catch `CandidateProposalError`.
  - **Entries that catch both.** `_edit_structural_candidate` and `_release_active_candidate` already catch both.
- **Limit of this step's tests.** They show guard behavior over real stored stacks built with a helper. They cannot show that promotion or recovery handles the accepted shape, because neither consumes the derivation until step 3.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/roadmap_candidate_review.py`:
    - add one private helper that asks the derivation and translates its error;
    - make `_require_answered_review_route`, `_require_structural_candidate`, and `_require_active_structural_candidate` stack-aware;
    - update every call site of the first two;
    - change the edit replacement check in `_edit_structural_candidate`.
  - `plan_tool/cli/roadmap_cmd.py`: replace the own-route clause of the precheck in `_cmd_roadmap_structural_candidate_decision` with the stack answer, and import the derivation by name beside `load_stored_candidate_proposal`.
  - `tests/test_roadmap_candidate_review.py`: guard, decision, and edit tests over real stacks.
  - `tests/cli/test_roadmap_cmd.py`: precheck tests, updated setups for the existing precheck tests, and one real-orchestrator test.
- **Two mechanical files, both required.** Changing the two guard signatures breaks their other consumers, so the suite cannot be green without these edits.
  - `plan_tool/roadmap_version_promotion.py`: `_load_complete_directly_approved_candidate` passes `plans_dir` and `slug` to `_require_structural_candidate`. That one call is the only edit. Step 3 owns everything else in this module.
  - `tests/test_roadmap_version_promotion.py`: `test_answered_seal_cannot_promote_a_structural_initial_candidate` replaces `_require_answered_review_route` with `lambda _candidate: None`. Widen that stub to accept the new keywords. Nothing else in the file changes.

## Implementation

**Behavior to deliver.** The property is that a structural ancestor cannot reach review through the answered route, and that the structural decision can be made on the stack that carries it.

- **Answered-route entry.** It refuses when the candidate's stack is structural, at any hop. The refusal keeps the existing `--decide-candidate` pointer text. It refuses an underivable stack with a message that does not point at `--decide-candidate`, because a decision cannot succeed on an underivable stack either.
- **Decision eligibility.** `_require_structural_candidate` accepts a batch candidate that has stored operations when its stack is structural, even if its own route is presentation-only. The stored-operations shape check stays first and unchanged, so a route-less tip is refused without touching the derivation. `_require_active_structural_candidate` inherits the change through its call to the former, which covers the approve and edit publication rechecks.
- **CLI precheck.** It accepts the same candidates as the library guard and refuses the same ones. A refusal returns status 2, before any disclosure and before any decision call.
- **Edit replacement check.** The replacement is accepted when its own computed route is STRUCTURAL, or when the stack of its source is structural. The replacement is not stored when the check runs, which is why the check combines the two facts.

**Approach.** One way to do it:

- **One helper.** Add a private helper in the review module that takes `plans_dir`, `slug`, a tip id, and a root id. It calls step 1's derivation, returns `is_structural`, and re-raises `CandidateProposalError` as `CandidateReviewError` with a message that names the stack as underivable. Route all four uses through it:
  - the answered-route guard passes the candidate's own id and recorded root;
  - `_require_structural_candidate` passes the candidate's own id and recorded root;
  - the edit check passes `evidence.source_version_id` and the recorded root;
  - no guard calls the derivation directly.
- **Own route first in the edit check.** Test the replacement's own route before deriving the source's stack. The common structural-edit path then adds no derivation.
- **Keyword-only guard signatures.** Change `_require_answered_review_route(candidate, *, plans_dir, slug)` and `_require_structural_candidate(candidate, *, plans_dir, slug)`. Make the new parameters required, with no defaults. A default would let a caller silently get own-route behavior, which is the failure this step closes. Call sites to update:
  - `_require_answered_review_route`: `generate_candidate_question`, and `_load_admitted_initial_candidate_from_admission`, which serves `record_reviewer_answer`, `request_replacement`, and `seal_review`.
  - `_require_structural_candidate`: the reject and approve branches of `decide_structural_candidate`, `_edit_structural_candidate`, `_require_active_structural_candidate`, and the promotion loader named under Files.
- **CLI precheck shape.** Keep the stored-operations shape check and the admission-match check and their order. Replace only the own-classification clause with the stack answer, asking the derivation on the candidate's own id and its recorded root. Import the derivation by name into `plan_tool/cli/roadmap_cmd.py` so tests can stub it there, as they do for `load_stored_candidate_proposal`. Map an underivable stack to the same `error(...)` plus status 2 exit as the other precheck refusals.

**Rejected alternatives.**
- **Each guard translates the error itself.** That gives four copies of the translation, and one of them will drift.
- **Let `CandidateProposalError` propagate.** The answered-route entries do not catch it, so the failure would escape the library as an exception instead of a `refused` result.
- **Read an underivable stack as "not structural".** That fails open on the answered route, which is the misreading the plan fences.
- **Short-circuit the precheck on an own-route STRUCTURAL candidate.** It would leave the four fake-candidate CLI tests untouched. It also keeps a second copy of the predicate in the CLI and lets an underivable stack reach the disclosure.
- **Keep `_require_structural_candidate` as an own-route check and add a new stack guard for the decision.** The promotion loader would then stay own-route, which contradicts the plan's statement that this step changes the shared guards.

**Constraints (not free to vary).**
- **Message text stays.** Keep `candidate is not a stored structural proposal`, `structural candidate requires --decide-candidate`, and `structural edit replacement is not structural` unchanged. Only the new underivable message is new. The two copies of the first message (library and CLI) must stay identical.
- **Guard order.** The stored-operations shape check runs before any stack derivation in `_require_structural_candidate`.
- **Fail closed on the answered route.** No path may treat an underivable stack as admissible there.
- **No new state.** Nothing is cached, stored, or added to a result type. Repeat derivations under publication rechecks are acceptable.
- **Reject keeps its unguarded eligibility check.** The reject branch of `decide_structural_candidate` checks eligibility before `_release_active_candidate` takes the writer guard. Do not move it.

**Foundational logic and the sites left alone.** The foundational logic is "does a candidate's unpromoted stack carry a STRUCTURAL stored route". A sweep of `operation_classification` by identifier, and of route, structural, and own-source by vocabulary, gives these sites in the two edited modules.
- **Changed here:**
  - `_require_answered_review_route`;
  - `_require_structural_candidate`;
  - `_require_active_structural_candidate` (inherits);
  - the edit replacement check in `_edit_structural_candidate`;
  - the CLI precheck.
- **Stays own-route, deliberately:**
  - the answered-replacement refusal in `request_replacement` ("structural replacement cannot use the answered review route"). The entry guard already refuses a structural stack, so only the replacement's own hop is left to classify;
  - `_store_active_structural_replacement`, which records the replacement's own computed route;
  - `_release_active_candidate` and `_require_active_candidate_unchanged`, which carry no route logic;
  - `_new_structural_approval_seal` and `_validate_initial_candidate`.
- **Owned by other steps:**
  - `_render_candidate_proposal_result` and the disclosure's stored-route line (steps 4 to 6);
  - the promotion module's `_load_complete_sealed_candidate` and `_structural_promotion_seed_member`, and `_selected_promotion_is_structural` in `plan_tool/roadmap_revision_publish.py` (step 3).

**Interim reachability.** The decision surface now accepts a presentation-only top of a structural stack, and the CLI approve still seals and promotes in one invocation. Promotion does not yet add the seed-state effect for that shape, since step 3 owns it. That state cannot arise in production before step 7, because the interim batch block still refuses to stack under a structural candidate. Tests here must not promote such a stack.

## Tests

Tests live in `tests/test_roadmap_candidate_review.py` and `tests/cli/test_roadmap_cmd.py`.

**Stack builders (library tests).**
- **C1 structural, C2 presentation-only.** The interim block refuses this through `_run_batch` alone. Reuse the masking helper step 1 adds to `tests/test_roadmap_candidate_run.py`. Read its landed name and import it the way this module already imports `_run_batch` and `_seed_batch_ledger`. Importing does not put that file in this step's footprint. `_SECOND_BATCH_DELTA` has no operations, so a second hop built from it is presentation-only.
- **C1 presentation-only, C2 structural.** Needs no masking, because the block fires only under a structural active candidate. It needs a second open ledger item, because `_FIRST_BATCH_DELTA` answers `batch-one`. `_batch_item` in `tests/test_roadmap_candidate_run.py` builds one.
- **Forged lower hop.** Use `_edit_stored_evidence` from `tests/test_roadmap_candidate_run.py` to make a lower hop's stored route disagree with its stored operations. The tip still loads, so the guard, not the loader, is what refuses.
- **The replacement's route is classified against C1.** Choose each edit reply by the route it must produce, and assert the stored route instead of assuming it. `_batch_replacement_response()` is the presentation-only reply over the root.

**Library tests (`tests/test_roadmap_candidate_review.py`).**
- `test_answered_review_route_refuses_a_structural_candidate` (extended) — gains a stack-shape parameter: an own-structural top, and a presentation-only top over a structural lower hop. Each of the five routes refuses, names `--decide-candidate`, calls no backend, and leaves the tree unchanged. The route set stays in one place, so a new answered-route entry fails for both shapes.
- `test_answered_review_route_refuses_an_underivable_stack_instead_of_admitting_it` — over a forged lower hop, the question entry and the answer entry each return `refused`, never call the backend, write nothing, and do not name `--decide-candidate`. The two entries are the two distinct guard paths: a direct call, and the shared admission loader.
- `test_answered_review_route_still_admits_a_stack_with_no_structural_hop` — carve-out. A two-hop all-presentation stack still reaches the backend and stores its question inventory. It fails a guard that refuses any multi-hop stack.
- `test_structural_approval_of_a_presentation_only_top_seals_that_top_and_promotes_nothing` — the seal has decision `structural-approval` and binds the top candidate's id, and the accepted head is unchanged.
- `test_structural_rejection_of_a_presentation_only_top_releases_the_pointer_and_keeps_every_hop_stored` — the pointer releases, a terminal resolution exists for the top, and the lower hop stays stored as history.
- `test_structural_decision_refuses_a_stack_with_no_structural_hop_for_every_decision` — approve, edit, and reject, over a single presentation-only hop and a two-hop all-presentation stack. Each returns `refused`, calls no backend, and leaves the tree unchanged.
- `test_structural_decision_refuses_an_underivable_stack_with_no_write` — approve, edit, and reject over a forged lower hop return `refused` instead of raising `CandidateProposalError`, and leave the tree unchanged. This pins the error translation.
- `test_structural_edit_over_a_structural_lower_hop_accepts_a_presentation_only_replacement` — the replacement is stored and becomes the active candidate. It is sourced from C1, meaning its predecessor is C1. Its own stored route is presentation-only, and step 1's derivation reports its stack as structural. This pins that the edit check tests the stack, and that edit sourcing is unchanged.
- `test_structural_edit_over_a_presentation_only_lower_hop_still_refuses_a_replacement_with_no_structural_route` — a structural top over a presentation-only lower hop, with a presentation-only replacement, returns `response-rejected`, writes nothing, and leaves the top approvable. A lower hop that is not structural must not exempt the replacement.
- **Existing tests that must stay green and unedited.**
  - `test_structural_edit_that_cannot_yield_a_structural_replacement_stores_nothing_and_stays_approvable` covers the root-source refusal.
  - `test_batch_evidence_without_route_remains_readable_but_cannot_enter_any_structural_decision` covers the route-less carve-out.
  - The selector-era answered-route tests are the assertion for the `root_version_id is None` carve-out.

**CLI tests (`tests/cli/test_roadmap_cmd.py`).**
- **Setup change for existing precheck tests.** Each existing test that reaches the precheck through `_stored_structural_cli_candidate` (the four that call `_admit_candidate`) needs the derivation stubbed in `roadmap_cmd`. Add one helper for that and call it explicitly. A red test here is expected and is not a reason to narrow the change. Read each one: the own-structural happy paths keep their meaning under a structural stub.
- `test_structural_decision_accepts_a_presentation_only_top_when_its_stack_is_structural` — approve, edit, and reject with a presentation-only own route and a structural stub reach the decision call and print the disclosure.
- `test_structural_decision_refuses_an_ineligible_candidate_before_any_disclosure_or_decision` (extended) — the `presentation-only` case now means a non-structural stack answer. A new `underivable-stack` case, where the stub raises `CandidateProposalError`, gives status 2, no disclosure, and no decision call. The refusal reason reaches stderr.
- `test_structural_precheck_derives_the_stack_from_the_candidate_and_its_recorded_root` — the stub records its keywords. They carry the candidate's own id as tip, its `evidence.root_version_id` as root, and the command's `plans_dir` and slug. This rules out using the current head or the admission's root.
- `test_decide_candidate_reaches_a_presentation_only_top_of_a_real_structural_stack` — one real-orchestrator test, with no stubbed derivation and no stubbed library. `cmd_roadmap` with `--candidate-decision reject` over a real C1-structural / C2-presentation stack returns 0 and releases the pointer. It is the only check that the precheck and the library guard agree, so the command reaches the stack.
  - **Fixture.** The library helpers hard-wire the `storefront` slug and `tmp_path / "plans"`. Pass that slug and plans dir to `_ns`.
  - **Docstring.** Add this test to the module docstring's list of deliberate real-orchestrator exceptions in the same edit, so the docstring stays true.

**Verify by mutation.** Before calling the tests done, break the code each of these ways and confirm each turns a test red:
- revert `_require_answered_review_route` to an own-route check;
- treat `CandidateProposalError` as "not structural" in the helper;
- revert `_require_structural_candidate` to an own-route check;
- revert only the call inside `_require_active_structural_candidate`, which turns the approval test red at the publication recheck;
- in the edit check, accept any replacement when the source is not the root, and separately ignore the replacement's own route;
- make the answered guard refuse when `root_version_id is None`, which turns the selector-era tests red;
- revert the CLI precheck to an own-route check.

### Tests for this step

- **Tests added or changed.**
  - Library: two new answered-route tests, one extended answered-route test, and six new decision and edit tests, all in `tests/test_roadmap_candidate_review.py`.
  - CLI: three new tests, one extended, and four setup updates, all in `tests/cli/test_roadmap_cmd.py`.
  - Promotion: one stub signature in `tests/test_roadmap_version_promotion.py`.
- **What they cover.** The stack-aware answered route and decision, the underivable channel, the carve-outs, the edit check both ways, and the CLI precheck's call shape and reachability.
- **Green gate.** Every test above and the rest of the suite must be green before the step is done. The step's `test_command` is `uv run pytest tests/ -q -n auto`. The added tests also satisfy the plan's test-authoring gate.

## Acceptance criteria

- The answered-route entries return `refused`, naming `--decide-candidate`, when the candidate's stack is structural at any hop. That includes a presentation-only top over a structural lower hop. They call no backend and write nothing.
- The same entries return `refused` for an underivable stack without naming `--decide-candidate`, and never call the backend.
- Answered-route behavior is unchanged for all-presentation stacks, legacy route-less evidence, and selector-era candidates.
- `decide_structural_candidate` accepts approve, edit, and reject for a batch candidate with stored operations when its stack is structural. It returns `refused` with no write when the stack has no structural hop, when the stack is underivable, or when the candidate has no stored operations.
- Approving a presentation-only top of a structural stack stores a `structural-approval` seal that binds the top candidate, and promotes nothing.
- An edit replacement is accepted when its own route is STRUCTURAL or its source's stack is structural. Otherwise it returns `response-rejected` with no write. The replacement is still sourced from the top candidate's own source.
- `_require_answered_review_route` and `_require_structural_candidate` take required keyword `plans_dir` and `slug`, and every call in `plan_tool/` and `tests/` passes them.
- The CLI precheck asks the derivation for the candidate's own id and recorded root. It refuses with status 2, before any disclosure or decision call, for a non-structural or underivable stack.
- The answered-replacement refusal, `_release_active_candidate`, `_new_structural_approval_seal`, `_validate_initial_candidate`, `_render_candidate_proposal_result`, and the argparse surface are unchanged. `docs/cli/roadmap.md` needs no regeneration.
- `git diff --name-only` lists only the six declared files. The diffs in `plan_tool/roadmap_version_promotion.py` and `tests/test_roadmap_version_promotion.py` are limited to the argument pass and the widened stub.
- The full suite passes with `uv run pytest tests/ -q -n auto`.

## References

- [docs/implementation-plans/2-roadmap-stack-aware-approval.md](../../2-roadmap-stack-aware-approval.md) — § "Design decisions" (Stack route, Guards, Edit and reject keep their contracts) and the "Guard sites" table define what this step changes and keeps.
- [docs/implementation-plans/plan-details/roadmap-stack-aware-approval/01-one-stack-route-derivation-beside.md](01-one-stack-route-derivation-beside.md) — step 1's derivation, its error channel, and the stack-building test helper this step reuses.
- [handoffs/2026-09-23-roadmap-structural-feedback-approval-code-review.md](../../../../handoffs/2026-09-23-roadmap-structural-feedback-approval-code-review.md) — the P2.1 defect and the owner decisions.
- [plan_tool/roadmap_candidate_review.py](../../../../plan_tool/roadmap_candidate_review.py) — `decide_structural_candidate`, `_require_structural_candidate`, `_require_answered_review_route`, `_edit_structural_candidate`.
- [plan_tool/cli/roadmap_cmd.py](../../../../plan_tool/cli/roadmap_cmd.py) — `_cmd_roadmap_structural_candidate_decision`.
- [plan_tool/roadmap_version_promotion.py](../../../../plan_tool/roadmap_version_promotion.py) — `_load_complete_directly_approved_candidate`, the one other caller of the shared guard.

## Applicable guardrails

- **The plan's "Scope guardrails", "Not allowed": no second structural gate or per-hop approval.** The decision surface stays one approval of the top candidate. This step makes it reachable for a stack and adds no gate.
- **The plan's "Scope guardrails", "Not allowed": no cumulative classifier and no new persisted stack or binding field.** The guards read step 1's derivation over stored routes and store nothing. The edit check combines two stored or just-computed routes and does not classify the stack's content.
- **The plan's "Scope guardrails", "Not allowed": no change to the promotion writer, the journal, or the version and candidate stores.** The only promotion-module edit is passing two arguments to a shared guard. Promotion and recovery behavior is step 3's.
- **The plan's "Scope guardrails", "Not allowed": no stack output on `--reject-candidate`, `--discard-candidate`, or the answered route, and no confirm step for edit or reject.** This step adds no printout. Its only new text is the underivable refusal message.
- **The plan's "Scope guardrails", "Not allowed": no behavior change for legacy candidates that have no route.** A route-less tip is refused by the unchanged shape check, and a selector-era candidate yields an empty stack.
- **The plan's "Scope guardrails", ordering fence.** The batch block stays until step 7. This step lands the guards that the block's removal depends on.
- **The plan's "Out of scope": edit sourcing, reject/discard pointer release, and `_classify_validated_operations`.** All three stay unchanged.

## Deferred

- The promotion boundary, the answered-seal guard, the seed-state member, the recovery predicate, and the loader's seal requirement for a structural stack — step 3 owns them. This step passes two arguments through the loader and nothing more.
- The stack view, its digest, and its shared printout — step 4 owns them. The disclosure keeps showing the top hop's own stored route until steps 4 to 6.
- The two-invocation approve and the confirm flag — step 5 owns them. The CLI approve still seals and promotes in one invocation here.
- The proposal output's own-route check in `_render_candidate_proposal_result` — step 6 owns it.
- Retiring the batch block, and end-to-end tests of the stack across the direct, answered, edited, and recovered routes — step 7 owns them. This step asserts the guards only.
- The tip's own load raising `CandidateProposalError` ahead of any guard, for example a deleted lower hop — the current propagation at the library entries is unchanged. The class is not specific to stacks. If a library `refused` result is wanted there, file it in `BUG_BACKLOG.md`.
- Renaming `_store_active_structural_replacement`, which can now store a replacement whose own route is presentation-only over a structural lower hop — not built. Renaming is outside this step's outcome.
