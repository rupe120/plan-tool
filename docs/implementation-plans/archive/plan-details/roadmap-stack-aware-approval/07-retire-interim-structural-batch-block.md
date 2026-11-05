> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 7 — Retire the interim structural batch block, reopen the later-batch matrix cell, and prove the stack end to end

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step deletes the one branch in `_run_batch_candidate_proposal` (`plan_tool/roadmap_candidate_run.py`) that refuses a new batch while the active candidate's stored route is STRUCTURAL, so a batch stacks on a structural candidate as the plan designs. The stack-aware guards from steps 2, 3, 5, and 6 replace the branch, and nothing new is added in its place. In the four declared test files, the block's refusal tests give way to stacking tests, the `superseded-by-later-batch` cell of the decision-eligibility matrix returns, and the fixture helper that steps 1 to 6 use to build a stack the block would refuse is retired. The key decision is to delete the branch outright, never convert it into a stack check, and let end-to-end tests hold the property: a C1-structural / C2-presentation-only stack built only by the shipped runner is driven through the direct, answered, edited, and recovered routes. On green, two `--propose-candidate` runs store that stack, the answered route refuses it, and it reaches the accepted head only through a confirmed structural approval of its top that journals the seed-state effect.

## Table of Contents

- [Summary](#summary) — what the step deletes, adds, and proves
- [Table of Contents](#table-of-contents) — this list
- [Why](#why) — what the block does today and why it must go now
- [Input](#input) — what steps 1–6 hand this step, what the runner stores for a stack, and what the tests cannot show
- [Files (creates vs edits)](#files-creates-vs-edits) — the five declared files and the edits in each
- [Implementation](#implementation) — the removal, the pre-removal sweep, the test changes, and the four routes
- [Tests](#tests) — deleted, changed, and new cases, mutation checks, and the green gate
- [Acceptance criteria](#acceptance-criteria) — observable checks
- [References](#references) — the plan, the ledger, and the sibling details
- [Applicable guardrails](#applicable-guardrails) — the plan fences that bind this step
- [Deferred](#deferred) — work other steps own and what is deliberately not built

## Why

The block is the only thing that keeps a stacked structural candidate out of production. While the active candidate's stored route is STRUCTURAL, `--propose-candidate` refuses before any model call. That freezes new reviewer batches until the operator decides the pending candidate. It also contradicts the plan's design: batches keep sourcing from the active candidate, and one approval covers every unpromoted hop beneath its top. With steps 2, 3, 5, and 6 in place, every route from a structural hop to the head asks the whole stack, so the block protects nothing and hides the guards from real use. Its three-cell refusal test pins the old behavior, and the matrix cell it removed stays missing. The fixture helper that steps 1 to 6 use exists only to get around it. At HEAD the block, its refusal test, and the missing matrix cell are all present, so none of this work is done.

## Input

- **Outputs of steps 1 to 6.**
  - **Names.** None of these symbols exist at HEAD when this file is written. Read every landed name off the modules. The landed names win over any name in this file.
  - **Step 1.** A stack-route derivation beside `source_ancestry_to_root`, recommended as `candidate_stack_route`. It also adds one fixture helper to `tests/test_roadmap_candidate_run.py` that stores a second hop while the block sees a non-structural active candidate. Step 1 states that step 7 removes the need for it.
  - **Step 2.** Stack-aware `_require_answered_review_route` and `_require_structural_candidate`, the edit replacement check in `_edit_structural_candidate`, and the CLI precheck in `_cmd_roadmap_structural_candidate_decision`.
  - **Step 3.** The stack-aware promotion boundary, `_structural_promotion_seed_member`, and `_selected_promotion_is_structural`. It also adds a stack builder to `tests/test_roadmap_version_promotion.py` that approves C2 and returns `(root, C2, seal)`.
  - **Step 5.** `decide_structural_candidate(..., confirm_digest=...)`, the `--confirm-stack-digest` flag, and an approve helper beside `_run_batch` (recommended as `_approve_structural_candidate`). Real-orchestrator CLI tests over a real stack.
  - **Step 6.** The whole-stack printout on the structural decision's edit and reject outcomes and on the proposal output of a structural stack.
- **What steps 1 to 6 already pin.** Their tests own the per-layer cases: each guard, the digest matrix, the printout, and the predicate. They build the stack with step 1's helper. This step must not restate those matrices.
- **What the runner stores for a stacked batch.** `_store_batch_candidate` publishes one generation holding the new candidate's bytes and evidence, a supersession record for the former active candidate, the active-pointer swap, and the ledger patch.
  - The new candidate's `source_version_id` is the active candidate's version id, and its `root_version_id` is the accepted root.
  - Its route is classified against that source through `materialize_candidate(predecessor=source)`. A wording-only C2 over a structural C1 therefore stores PRESENTATION_ONLY.
- **Edit and answered replacements keep their sourcing.** `_edit_structural_candidate` sources the replacement from the edited candidate's own `source_version_id`. An edit of C2 yields E2 with C1 as its predecessor, so E2's hops are C1 and E2 and C2 is not among them.
- **Recovery on an enrolled roadmap.** `recover_roadmap_publication` accepts only a completed journal, where every member is at its new bytes, and refuses anything incomplete. The recovered route is therefore "a complete journal is dropped, an incomplete one is refused". It is not a roll forward.
- **A second batch needs eligible work.** Without derived context left by the first hop, a second batch refuses with `no eligible work` before any guard runs. `_STRUCTURAL_FIRST_BATCH_DELTA` carries `derived-one` for this reason. `_SECOND_BATCH_DELTA` has no operations, so it classifies presentation-only.
- **Limit of this step's tests.** They run canned replies with green gates stubbed, as the sibling suites do. They show that the guards, the confirm step, promotion, and recovery agree on a stack the shipped runner built. They cannot show how a real model classifies its second batch, or that an operator reads the printout.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only), all declared for this step:**
  - `plan_tool/roadmap_candidate_run.py`:
    - Delete the structural branch and its refusal message in `_run_batch_candidate_proposal`. Nothing else changes.
    - The same-receipt re-entry return above it, the selector-era `unpromoted-candidate-lineage` refusal, and `_store_batch_candidate` stay as they are.
    - Expect no import change.
  - `tests/test_roadmap_candidate_run.py`:
    - Delete `test_a_second_batch_is_refused_before_any_model_call_while_a_structural_candidate_is_active`.
    - Add the stacking test that replaces it.
    - Reword the docstring of `test_a_second_batch_still_stacks_on_an_active_candidate_that_is_not_structural`.
    - Delete step 1's masking helper and convert its callers to `_run_batch`.
  - `tests/test_roadmap_candidate_review.py`:
    - Restore the `superseded-by-later-batch` situation in `test_structural_decision_refuses_a_candidate_that_is_no_longer_the_admitted_one_without_writes`.
    - Convert the masking-helper callers.
  - `tests/test_roadmap_version_promotion.py`:
    - Add the route tests and the stale-seal test.
    - Convert step 3's stack builder to build with `_run_batch` alone.
  - `tests/cli/test_roadmap_cmd.py`:
    - Add one operator-walk test through the real orchestrator.
    - Convert the masking-helper callers.
    - Extend the module docstring's list of deliberate real-orchestrator exceptions in the same edit.
- **Check for a caller outside these five files.** Run `rg '<masking helper name>' tests/`. Step 3's predicate tests in `tests/test_roadmap_revision_publish.py` use stubs and are expected to have none. If a caller exists elsewhere, add that file to the footprint and say so in the handoff.

## Implementation

**Behavior to deliver.**
- After this step, `--propose-candidate` stacks on the active candidate whatever its stored route is: STRUCTURAL, presentation-only, or absent. No refusal replaces the deleted branch.
- The order in `_run_batch_candidate_proposal` after removal is:
  1. ledger readiness;
  2. admission and root load;
  3. the selector-era lineage refusal;
  4. the pair check, active candidate load, and source ancestry;
  5. context build, with its no-work and refusal returns;
  6. the same-receipt re-entry return;
  7. the model call.
- The deleted branch sat between steps 6 and 7.

**Pre-removal sweep (the plan's ordering fence).** Do this before deleting anything. With the block gone, a guard that still reads only its own route is reachable in production.
- **Confirm steps 2, 3, 5, and 6 landed.** Their tests must be green over the masked-stack shape.
- **Sweep by identifier and by vocabulary.** Run `rg 'operation_classification' plan_tool/` and search `plan_tool/` for structural, own route, own source, and active structural.
- **Every remaining own-route read must be a deliberate keep** from the plan's "Guard sites" table:
  - the answered-replacement refusal in `request_replacement`;
  - `_store_active_structural_replacement`, which records the replacement's own computed route;
  - the route replay in `_require_reproducible_batch_operations`, which is the trust basis for stored routes;
  - the disclosure's `stored route:` line, which prints and decides nothing.
- **Every other reader must be stack-aware.** At HEAD those are `_require_answered_review_route`, `_require_structural_candidate`, the edit replacement check, `_load_complete_sealed_candidate`, `_structural_promotion_seed_member`, `_selected_promotion_is_structural`, the CLI precheck, and `_render_candidate_proposal_result`.
- **On any other own-route eligibility read, stop.** It is a missed site. Fix it at its owner step's site, or surface it. Do not delete the block over a known-open guard.

**Delete, never convert.**
- Rejected: replace the branch with "refuse while the stack is structural". That still forbids the stacking the plan designs, and step 1's detail already rules it out.
- Rejected: keep the branch behind a flag. Two behaviors would need tests for good, and the plan retires the block.

**Test changes, in order.**
- **Replace the refusal test with a stacking test.**
  - Keep the three active states: initial, approved-not-promoted, edit-produced. Each old cell gets a replacement asserting the new outcome.
  - Assert the batch is stored after exactly one model call. The new candidate's source is the active candidate, its root is the accepted root, and its own route is PRESENTATION_ONLY.
  - Assert step 1's derivation reports its stack as structural. This guards against a fixture that silently built the wrong shape.
  - Assert the pointer names the new candidate and a supersession record names the former one. The former candidate's stored bytes and evidence are unchanged.
  - Build the approved-not-promoted state with step 5's approve helper.
- **Reopen the matrix cell.**
  - Add `superseded-by-later-batch` back to the situations of `test_structural_decision_refuses_a_candidate_that_is_no_longer_the_admitted_one_without_writes`. That restores three cells, one per decision.
  - Give that test's first hop derived context. Copy `_structural_batch_delta()` and set `derived_feedback` locally. The shared helper serves many other tests and stays as it is.
  - Store the second hop with `_run_batch(tmp_path, _SECOND_BATCH_DELTA)`.
  - Delete the docstring sentence that says a later batch cannot supersede a structural candidate. The sentence is false after this step.
  - Pass the approve cell the digest that step 5's stack view yields for the stored superseded candidate. Otherwise the cell refuses for a missing or wrong digest and stays green for the wrong reason.
  - Assert the refusal is the admitted-candidate refusal, not one of step 5's digest refusals.
  - Rejected: an extra `approved-then-superseded-by-later-batch` cell. It exercises the same admitted-candidate loader that `approved-then-superseded-by-edit` already pins. The stale-seal test below pins its consequence at promotion.
- **Retire the masking helper.**
  - Delete the helper step 1 adds. Convert each caller to a plain `_run_batch` for the second hop.
  - Keep any wrapper that also asserts the built shape (C2 presentation-only, stack structural), and have it call `_run_batch` directly.
  - Callers span steps 1, 2, 3, 5, and 6 in the four test files.
  - Reword prose that describes the block or the helper, and delete it where it explains nothing else. Two known spots: the carve-out test's docstring, which explains a refusal that no longer exists, and step 1's Test-setup note. Change the carve-out test's docstring only, never its assertions.
- **Add the route tests.** See the table below. Build every stack with `_run_batch` and nothing else.

**The four routes.** All start from a runner-built stack: C1 structural, then C2 presentation-only through `_run_batch`. One shared oracle checks the plan's binary observable after each route.

| Route | What the test drives | End state asserted |
| --- | --- | --- |
| Direct | Approve C2 with its own digest through step 5's helper, then promote the returned seal. | Head is C2 and carries C1's structural change. The seal is `structural-approval` on C2. The journal holds the selector, the pointer release, and the seed member. Tracked seeds end `invalidated`. Decisions on C1 refuse with no write because C1 is superseded. |
| Answered | The question entry on C2, then a seal minted under the "seal issued before the entry guard" stub (widened by step 2), then promote it. | The entry refuses, names `--decide-candidate`, calls no backend, and leaves the tree unchanged. The stubbed-guard seal is refused at the promotion boundary with `RoadmapVersionPromotionError`. Head, pointer, seed state, and journal are unchanged. |
| Edited | Approve C2, then edit C2 with a presentation-only reply, then promote C2's old seal, then approve E2 and promote. | E2 is stored, unsealed, sourced from C1, with a PRESENTATION_ONLY own route and a structural stack. C2's seal no longer promotes. E2 promotes only under its own confirmed approval, with the seed member journaled. |
| Recovered | Capture the promotion journal with a spy on `publish_roadmap_generation`, reinstate it, and run `recover_roadmap_publication` under the writer guard. | The complete journal is dropped and the tree is unchanged. The variant without the seed member raises `RoadmapPublicationRecoveryError` and leaves the journal in place. |

- **The oracle.**
  - If the head moved, the top's seal is `structural-approval`, the captured generation includes the seed member, and tracked seeds are `invalidated`.
  - If a route refused, head, pointer, seed state, and journal are unchanged.
  - It reads seal decisions, journal members, and known fixture bytes. It must not classify content.
- **Edit reply for the edited route.** Choose a reply that differs from C2's stored delta, such as a different derived-feedback line. An identical delta likely reproduces C2's version identity, and the store refuses that collision.
- **Recovered route on the edited top.** Run it over E2's promotion as well as the direct top. Its hops are C1 and E2, which is a different chain shape from step 3's direct case.
- **Stale approval.** One extra test covers the state the block used to prevent.
  - Approve C1, then stack C2 with the runner so the pointer moves.
  - Promoting C1's seal must raise `RoadmapVersionPromotionError` and change nothing.
  - Approving C2 needs its own digest, and promoting it then succeeds.
  - This pins that an approval never carries forward to a hop stacked after it.
- **Latitude.** One parametrized test or several small ones may hold the routes, and a small shared helper may hold the seed-state setup. Copy the setup lines of the existing direct-promotion test in the promotion suite rather than inventing a new fixture.

**Operator walk (`tests/cli/test_roadmap_cmd.py`).** One real-orchestrator test.
- Run `--propose-candidate` twice through `cmd_roadmap`, the first with a structural reply carrying derived feedback and the second with a presentation-only reply.
- Both runs exit 0, and the second run's output presents both hops (step 6).
- `--review-candidate` on C2 exits 2 and names `--decide-candidate`.
- An unconfirmed approve of C2 exits 2, prints a `stack digest:` line, and leaves the plans tree unchanged.
- An approve carrying that printed digest exits 0 and prints `promoted version:`. The head is C2.
- The first `--propose-candidate` needs a structural reply for the CLI fixture's item and entity. Extend `_enrolled_roadmap_with_a_proposed_candidate` with a keyword-only reply argument whose default is today's reply, so its existing callers are unchanged.
- Assert the first hop's stored route is STRUCTURAL before continuing, so a wrong fixture cannot pass.
- Do not restate step 5's flag matrix or step 6's printout cases.

**Constraints (not free to vary).**
- **This step is the last behavior change.** It must not edit a guard. A red route test means a missed guard: fix it at the owner step's site or surface it. Do not patch it here.
- **Runner-built stacks only.** The stack-building path must not monkeypatch `load_stored_candidate_proposal`, the derivation, a `_require_*` guard, or the runner. Allowed patches are the gate stubs and the invoker seams. The one exception is the answered route's pre-guard seal, which stubs only `_require_answered_review_route`, and only to mint the seal.
- **Assert the shape.** Every builder asserts that C2's own route is PRESENTATION_ONLY and that its stack is structural.
- **Refusals change nothing.** Compare `_tree` or `_snapshot` before and after.
- **The carve-outs stay.** Route-less and all-presentation stacks keep their tests, and their assertions stay unedited. That set includes `test_a_second_batch_still_stacks_on_an_active_candidate_that_is_not_structural`, `_sealed_two_hop_replacement`, and the route-less answered-route tests.
- **Leave the re-entry return alone.** The same-receipt return above the deleted branch is BACKLOG #430's. This step neither tests nor changes it.

**Foundational logic and the sites.** The logic is "which candidate a new batch may source from". A sweep by identifier (`_run_batch_candidate_proposal`, `source_ancestry_to_root`, `_load_resolved_version`, `build_supersession_member`) and by vocabulary (block, blocks, awaits a decision, cannot supersede, a blocked batch) gives these sites.
- **Changed here:** the branch itself, its refusal test, the matrix docstring's sentence, and the carve-out test's docstring.
- **Left alone, deliberately:**
  - `_store_batch_candidate` and `build_candidate_context`, which already handle stacking;
  - `_store_batch_replacement` and `_store_active_structural_replacement`, which source from the initial's own source and never inherit an active candidate's content;
  - the selector-era `unpromoted-candidate-lineage` refusal.
- **Owned by step 8:** `docs/how-to/roadmap.md`, `ROADMAP_FEEDBACK_FORMAT.md`, `docs/ARCHITECTURE.md`, `DATA_CONTRACT.md`, the review ledger, the 2026-09-22 handoff, and the backlog entries that name the block.

## Tests

Cases live in the four declared test files. Steps 2, 3, 5, and 6 own the per-layer cases, so this step adds only cases that need the shipped runner or a whole route.

**`tests/test_roadmap_candidate_run.py`**
- `test_a_second_batch_is_refused_before_any_model_call_while_a_structural_candidate_is_active` — deleted with the block. Its `pytest.fail("a blocked batch invoked the backend")` guard goes with it.
- `test_a_batch_stacks_on_an_active_structural_candidate_in_every_active_state` — parametrized over initial, approved-not-promoted, and edit-produced. Asserts stored, one model call, source is the former active candidate, own route PRESENTATION_ONLY, stack structural, pointer and supersession updated, and the former candidate's bytes unchanged. The name states the invariant: structural approval, not proposal, is where structural content is decided.
- `test_a_second_batch_still_stacks_on_an_active_candidate_that_is_not_structural` — stays. Assertions unedited, docstring reworded. It would still turn red if someone reintroduced a block keyed on absence.

**`tests/test_roadmap_candidate_review.py`**
- `test_structural_decision_refuses_a_candidate_that_is_no_longer_the_admitted_one_without_writes` — three restored `superseded-by-later-batch` cells. Each of approve, edit, and reject returns `refused`, no seal, and an unchanged tree, and never reaches the backend. The approve cell carries a valid digest so the eligibility refusal is what fires.

**`tests/test_roadmap_version_promotion.py`**
- `test_direct_route_promotes_a_runner_built_structural_stack_only_under_a_confirmed_approval_of_its_top` — the direct row of the table.
- `test_answered_route_cannot_carry_a_runner_built_structural_hop_into_the_head` — the answered row. It repeats step 3's boundary case on purpose, now as one walk over a runner-built stack. It is not a new matrix.
- `test_edited_route_promotes_a_structural_stack_only_under_the_replacements_own_confirmed_approval` — the edited row.
- `test_recovery_of_a_completed_structural_stack_promotion_requires_the_seed_member` — the recovered row, over the direct top and the edited top.
- `test_an_approval_of_a_lower_hop_cannot_promote_after_a_later_batch_stacks_on_it` — the stale-approval case.

**`tests/cli/test_roadmap_cmd.py`**
- `test_operator_walk_stacks_a_batch_under_a_structural_candidate_and_reaches_the_head_only_by_confirmed_approval` — the operator walk. Add it to the module docstring's list of deliberate real-orchestrator exceptions, with the reason: the seam between the proposal output, the refusal, and the two approve invocations is visible only over the real orchestrator.

**Helper retirement.** The callers of step 1's masking helper in all four files now build with `_run_batch`. No test monkeypatches `load_stored_candidate_proposal` to hide a route from the runner.

**Verify by mutation.** With the block gone, these route tests are the only backstop for each guard. Break the code each of these ways and confirm each turns a test red, then restore it:
- reintroduce the block: the stacking test turns red, and the carve-out tests stay green;
- reintroduce the block keyed on absence: the carve-out tests turn red;
- revert `_require_answered_review_route` to an own-route check: the answered route test turns red;
- revert `_require_structural_candidate` to an own-route check: the direct route test turns red;
- revert `_structural_promotion_seed_member` to an own-route check: the direct and edited route tests turn red;
- revert `_selected_promotion_is_structural` to an own-route check: the recovered route test turns red;
- make the edit replacement check test only the replacement's own route: the edited route test turns red;
- delete the boundary seal check from step 3: the answered route test turns red.

### Tests for this step

- **Deleted:** one parametrized test (three cells).
- **Changed:** one parametrized matrix test gains three cells. Two docstrings are reworded. Every caller of the masking helper, about a dozen across the four files, is converted.
- **Added:** one parametrized stacking test (three cells), five promotion tests, and one CLI walk. That is about seven new functions.
- **Green gate:** every case above and the rest of the suite must be green before the step is done. The step's `test_command` is `uv run pytest tests/ -q -n auto`. The added tests also satisfy the plan's test-authoring gate.

## Acceptance criteria

- `_run_batch_candidate_proposal` has no branch that reads the active candidate's stored route. The text `an active structural candidate awaits a decision` appears nowhere in `plan_tool/` or `tests/`.
- A batch stored under an active structural candidate in the initial, approved-not-promoted, and edit-produced states returns `stored` after one model call, with the active candidate as its source.
- The same-receipt re-entry return and the selector-era `unpromoted-candidate-lineage` refusal are unchanged.
- Approve, edit, and reject of a structural candidate that a later batch superseded each return `refused` with no write. The three `superseded-by-later-batch` cells are in the matrix.
- **Direct route:** a runner-built C1-structural / C2-presentation-only stack reaches the head only through a `structural-approval` seal on C2, with the journal holding the selector, release, and seed members and tracked seeds `invalidated`.
- **Answered route:** the entry refuses the stack, and a seal minted past the entry guard is refused at the promotion boundary. Head, pointer, seed state, and journal are unchanged.
- **Edited route:** E2 needs its own confirmed approval and promotes with the seed member. C2's earlier seal does not promote.
- **Recovered route:** the complete journal recovers, and the journal without the seed member is refused and left in place.
- A seal for a lower hop does not promote after a later batch stacks on it.
- The CLI walk exits 0 and 0 for the two proposals and 2 for the answered-route review. The unconfirmed approve exits 2 and leaves the tree unchanged. The confirmed approve exits 0 and moves the head to C2.
- Every carve-out test still passes with its assertions unedited: route-less candidates, all-presentation stacks, and selector-era candidates.
- `rg '<masking helper name>' tests/` returns nothing, and no stack-building path patches the runner, the derivation, or a guard.
- `git diff --name-only` lists only the five declared files.
- Each mutation check above turns a test red before the step is closed.
- The full suite passes with `uv run pytest tests/ -q -n auto`.

## References

- [docs/implementation-plans/2-roadmap-stack-aware-approval.md](../../2-roadmap-stack-aware-approval.md) — § "Architecture" owner decision 1, "Guard sites", "Scope guardrails" (ordering fence), and "Testing" define what this step retires and proves.
- [handoffs/2026-09-23-roadmap-structural-feedback-approval-code-review.md](../../../../../handoffs/2026-09-23-roadmap-structural-feedback-approval-code-review.md) — P2.1 records the defect, the reproduction, and the block; P4.1 records why the three active states are pinned.
- [plan_tool/roadmap_candidate_run.py](../../../../../plan_tool/roadmap_candidate_run.py) — `_run_batch_candidate_proposal`, `_store_batch_candidate`, and `source_ancestry_to_root`.
- [plan_tool/roadmap_version_promotion.py](../../../../../plan_tool/roadmap_version_promotion.py) — the promotion boundary the route tests drive.
- [plan_tool/roadmap_revision_publish.py](../../../../../plan_tool/roadmap_revision_publish.py) — `recover_roadmap_publication` and its completed-journal rule.
- [docs/implementation-plans/plan-details/roadmap-stack-aware-approval/01-one-stack-route-derivation-beside.md](01-one-stack-route-derivation-beside.md) — the masking helper this step retires.
- [docs/implementation-plans/plan-details/roadmap-stack-aware-approval/03-make-promotion-boundary-recovery.md](03-make-promotion-boundary-recovery.md) — the stack builder and the per-layer promotion and recovery cases.
- [docs/implementation-plans/plan-details/roadmap-stack-aware-approval/05-split-structural-approve-two.md](05-split-structural-approve-two.md) — the approve helper, the digest contract, and the real-orchestrator cases.
- [ROADMAP_FEEDBACK_FORMAT.md](../../../../../ROADMAP_FEEDBACK_FORMAT.md) — the batch stacking rule. Step 8 rewords its block sentence.

## Applicable guardrails

- **The plan's "Scope guardrails", ordering fence.** This step is the block's removal, so it runs last. The pre-removal sweep is how it proves every guard, the stack view, and the confirm step are in place first.
- **The plan's "Scope guardrails", binary observable.** The four route tests and the oracle assert it directly on each route. The seal has one construction site, the confirmed approve, and these tests never build a seal any other way.
- **The plan's "Scope guardrails", "Not allowed": no change to the promotion writer, the publication journal, the recovery machinery, or the stores.** This step edits none of them. The recovered route only exercises recovery.
- **The plan's "Scope guardrails", "Not allowed": no persisted stack or binding field, no cumulative classifier, no quality judgment of content.** The oracle reads stored seal decisions, journal members, and known fixture bytes. No new stored field appears.
- **The plan's "Scope guardrails", "Not allowed": no auto-approval and no terminal prompt.** Every approve in the route tests and the CLI walk passes its digest explicitly.
- **The plan's "Scope guardrails", "Not allowed": no confirm step for edit or reject, and no stack output on other surfaces.** The answered route's output stays a plain refusal. The walk adds no assertion that widens any output.
- **The plan's "Scope guardrails", "Not allowed": no behavior change for legacy candidates that have no route.** The carve-out tests stay and stay unedited.
- **The plan's "Out of scope": edit sourcing, reject and discard pointer release, `_classify_validated_operations`, and operation authority.** The edited route relies on edit sourcing exactly as it is.
- **The plan's "Out of scope": earlier single-command seals, BACKLOG #428, and the unreachable selected-local runner (BACKLOG #429).** None is touched.

## Deferred

- Rewording the docs, the review ledger, the 2026-09-22 handoff, the backlog entries that name the block (including #430's adjacency note and Out of scope line), the pin in `tests/test_roadmap_feedback_format.py`, and the changelog — step 8 owns them. Until it lands, the docs still state the block as current behavior.
- The same-receipt re-entry return in `_run_batch_candidate_proposal` — BACKLOG #430 investigates it. This step neither tests nor changes it.
- A guard fix that a route test exposes — belongs to the owner step of that guard, not to this one. Surface it before closing this step.
- An extra `approved-then-superseded-by-later-batch` matrix cell — not added. The admitted-candidate loader is already pinned by the edit variant, and the stale-approval test pins its consequence at promotion.
- A randomized state-machine harness over the route space — not built. The four route tests and the mutation checks are the proportionate backstop.
- A cap or refusal for deep stacks — not built. The plan sets no limit, and derivation cost grows with stack height by design.
- Measuring how a real model classifies its second batch — needs a real backend and real briefs, which the hermetic suite cannot supply.
