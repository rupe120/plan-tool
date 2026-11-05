> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 9 — Promote only the exact active candidate for the current root

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Update `plan_tool/roadmap_version_promotion.py` so `promote_review_seal` promotes only the active candidate named by an exact sealed review and bound to the current accepted root. Update `tests/test_roadmap_version_promotion.py` for root-and-active-candidate review bindings, stale-pointer refusal, and ledger isolation. The key decision is that promotion validates immutable candidate, active-pointer, and review evidence, then atomically advances `AcceptedRoadmapHead` and clears the promoted candidate's active-candidate pointer (without recording it as terminal-resolved history); it does not rediscover or mutate mutable reviewer feedback. On green, a seal cannot promote a replaced, stale, or differently rooted candidate, later ledger edits cannot affect promotion, and an ordinary batch can create a new candidate for the promoted root immediately afterward.

## Table of Contents

- [Summary](#summary) — Reviewer view of the completed promotion boundary.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why selector-only promotion needs active-candidate and root binding.
- [Input](#input) — Upstream active-candidate and review evidence contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — Production and test changes in scope.
- [Implementation](#implementation) — Exact binding checks, selector publication, and ledger isolation.
- [Tests](#tests) — Focused promotion and preservation coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Durable publication and digest references.
- [Applicable guardrails](#applicable-guardrails) — Boundaries on authority and mutable feedback.
- [Deferred](#deferred) — Work outside this focused promotion change.

## Why

`plan_tool/roadmap_version_promotion.py:promote_review_seal` currently follows the fixed initial-candidate lineage and treats the candidate predecessor as the accepted head. Steps 5 and 8 introduce a root-bound active candidate and review activity that can replace that candidate, so promotion must prove the seal still names the exact active successor for the unchanged accepted root. Without that check, an older seal or candidate can move the canonical selector after its active pointer has changed, and any promotion path that rereads the live ledger would incorrectly let later reviewer edits influence an already sealed review.

## Input

- **No independent migration check.** Same invariant as step 8: promotion only ever names an existing active candidate, which step 5 (via step 3) could not have admitted for a `migration-pending` roadmap. This step does not call `check_ledger_processing_ready`.

- **Step 5 active-candidate state:** Read the landed root-and-active-candidate pointer and immutable stored-candidate evidence from `plan_tool/roadmap_candidate_run.py`, and reuse its pointer-release helper to clear the pointer on promotion. The landed record names and fields win over the current `CandidateProposalAdmission` shape. Promotion's release is a plain pointer clear, not a `CandidateTerminalResolution` — that record is reserved for rejection, discard, and settlement (step 5's shared shape, consumed by steps 7 and 8).
- **Step 8 review state:** Read the landed active-candidate review seal, question, answer, replacement, rejection, and discard contracts from `plan_tool/roadmap_candidate_review.py`, and the supersession record (`roadmap_candidate_run.load_candidate_supersession`) that the seal’s publication writes for the reviewed candidate. Promotion consumes immutable evidence only; it does not recreate review work.
- **Accepted-head contract:** Keep `plan_tool/roadmap_versions.py:AcceptedRoadmapHead`, `load_accepted_head`, `load_accepted_version`, `accepted_head_path`, and `render_accepted_head` as the canonical selector contract.
- **Publication boundary:** Keep `plan_tool/roadmap_revision_publish.py:require_roadmap_writer_token` and `publish_roadmap_generation` as the only write path. The final recheck remains inside the publication window.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_version_promotion.py` — Replace fixed initial-candidate assumptions with exact current-root, active-candidate, direct-source, batch, and seal validation while preserving selector-only publication.
  - `tests/test_roadmap_version_promotion.py` — Replace fixed-lineage fixtures and add active-pointer, root-binding, stale-state, and ledger-isolation coverage.

## Implementation

- **Use the active candidate as promotion authority.** Evolve `promote_review_seal` and `_load_complete_sealed_candidate` to load the accepted root, the current root-bound active candidate, and the requested seal before choosing a candidate to promote. The seal must name the same active candidate rather than merely a readable immutable candidate or an earlier review replacement. For a ledger-batch seal (one carrying a root/source/batch triple) the active candidate is the sealed replacement itself: the pointer names the replacement, the reviewed candidate is loaded as history, and the reviewed candidate’s supersession record must name that replacement and the same root. A selector-era seal keeps its fixed-lineage rules; they remain live for roadmaps that have no ledger, and a seal whose batch binding disagrees with its reviewed candidate’s lineage refuses.

- **Bind promotion to the complete processing pair.** Verify that the candidate, its stored evidence, the active-pointer state, and the review seal agree on the accepted root, direct source, candidate identity, and immutable batch facts supplied by steps 5 and 8. A candidate may be rooted in the current accepted root even when its direct source is a later active candidate; do not retain the older rule that requires the candidate’s direct predecessor to be the accepted head. A batch replacement’s direct predecessor is the reviewed candidate’s source, and the seal’s root/source/batch triple must equal the replacement evidence’s.

- **Reject stale state before publication and at replacement time.** Retain `StaleRoadmapVersionPromotionError` as the distinct failure for a changed accepted root, changed active pointer, or changed exact candidate binding. Extend the `publish_roadmap_generation` `before_replace` recheck so the state observed before validation still names the same current root and active candidate immediately before the selector changes.

- **Recheck stored candidate content from immutable bytes.** Keep `_recheck_stored_candidate`, `_parse_stored_artifacts`, `STAGES`, and `check_complete_roadmap_gates` as the deterministic proof that the sealed candidate’s stored brief, artifacts, content identity, predecessor diff, and gate evidence remain valid. Recompute only from immutable candidate and source material; do not regenerate a candidate, call a model, or infer a new batch. For a batch replacement the identity recompute passes the reviewed candidate’s batch receipt, the replacement’s persisted response patch and derived feedback, and no selected feedback, because the batch identity binds them; a tampered persisted patch therefore fails the identity recheck.

- **Publish the accepted-head selector and clear the active pointer together.** Build the `PendingGeneration` assembled by `promote_review_seal` from two members: the selector returned by `accepted_head_path`, and a release of the root's active-candidate pointer using the same pointer-clearing helper step 8 uses for rejection and discard (from `plan_tool/roadmap_candidate_run.py`, per step 5). Promotion is not a stale-resolution outcome — the promoted candidate becomes the new root rather than terminal history — so this release must not write step 5's `CandidateTerminalResolution` record; it only clears the pointer. Promotion must retain immutable version records, review records, and reviewer-ledger bytes unchanged. Clearing the pointer here — rather than leaving it bound to the now-promoted candidate — is what lets an ordinary batch create a new candidate immediately after promotion; the plan's "no second concurrent candidate" rule would otherwise block every candidate forever after the first promotion. The released pointer keeps the root it was released under, so the batch runner judges only a pointer that names an active candidate against the current root; a pointer with no active candidate never blocks a batch.

- **Keep the live ledger outside promotion.** Do not import or call the ledger runtime, loader, eligibility predicate, or mutation path from `plan_tool/roadmap_version_promotion.py`. The sealed candidate’s recorded batch evidence is sufficient for promotion; a later unrelated ledger edit must neither block nor alter a valid promotion.

- **Retain the existing writer-guard boundary.** `require_roadmap_writer_token` must run before reads that could lead to publication, and all selector writes must remain behind `publish_roadmap_generation`. Do not add a second accepted-head writer or transaction path.

## Tests

- `test_promotion_promotes_a_sealed_batch_replacement_and_moves_only_the_selector_and_the_pointer` — asserts promotion moves `AcceptedRoadmapHead` to the sealed replacement, releases the pointer while keeping its root, changes no other file under the roadmap (stored versions, records, ledger), and writes no `CandidateTerminalResolution` (distinguishing promotion from rejection, discard, and settlement).
- `test_promotion_publishes_the_selector_and_the_pointer_release_in_one_generation` — asserts the selector and the pointer release are the only members of one guarded generation.
- `test_promotion_refuses_a_sealed_replacement_that_a_later_batch_has_superseded` — asserts an earlier seal cannot promote a replacement after the pointer names its successor.
- `test_promotion_of_a_batch_replacement_requires_the_current_head_to_be_the_declared_root` and `test_promotion_requires_the_current_head_to_match_the_sealed_candidate_predecessor` — assert a candidate rooted in a former accepted root cannot become canonical (batch and selector-era lineage).
- `test_promotion_of_a_batch_replacement_rechecks_the_active_pointer_inside_the_journal_window` and `test_promotion_rechecks_head_predecessor_inside_the_journal_window` — assert the final publication recheck prevents a time-of-check/time-of-use promotion.
- `test_promotion_diffs_a_multi_hop_replacement_against_its_source_not_the_accepted_root` — asserts the direct source need not be the accepted root when the complete root-and-active processing pair is valid.
- `test_promotion_refuses_a_seal_whose_batch_binding_disagrees_with_the_replacement_evidence`, `test_promotion_refuses_a_seal_without_a_batch_binding_over_a_ledger_batch_candidate`, and `test_promotion_requires_the_supersession_record_of_the_reviewed_candidate_to_name_the_replacement` — assert substituted seal, batch, or supersession evidence cannot inherit a valid seal.
- `test_promotion_refuses_a_batch_replacement_whose_persisted_responses_no_longer_reproduce_its_identity` and `test_promotion_rechecks_complete_stored_candidate_bytes_raw_brief_and_gates` — assert unreproducible identity evidence, malformed stored bytes, or gate failures leave the accepted head unchanged.
- `test_a_batch_candidate_can_be_created_for_the_promoted_root_immediately_after_promotion` — asserts an ordinary batch can create a new active candidate for the newly promoted root right after promotion, proving the active-candidate slot was actually freed.
- `test_promotion_ignores_a_later_reviewer_edit_to_the_live_ledger_of_a_batch_replacement` and `test_promotion_does_not_read_or_rewrite_the_live_feedback_ledger` — assert a valid promotion succeeds after a later reviewer edit and leaves the ledger bytes unchanged.
- `test_promotion_has_no_model_or_candidate_regeneration_path` — asserts promotion remains an immutable-evidence validation path.

### Tests for this step

Every listed test in `tests/test_roadmap_version_promotion.py` must be green before this step is complete.

## Acceptance criteria

- `promote_review_seal` promotes only a sealed candidate that is the current active candidate for the current accepted root.
- A seal for a superseded, rejected, discarded, differently rooted, or otherwise non-active candidate raises a promotion error and leaves `AcceptedRoadmapHead` unchanged.
- A changed accepted root or active-candidate binding detected before or during guarded publication prevents promotion.
- Promotion accepts a valid root-bound candidate whose direct source is the active chain source recorded in immutable evidence.
- Promotion validates the selected candidate from stored immutable bytes and complete stage-ordered gate evidence.
- Promotion publishes the `AcceptedRoadmapHead` selector and clears the promoted candidate's active-candidate pointer in the same `publish_roadmap_generation` call, without writing step 5's `CandidateTerminalResolution` record.
- An ordinary batch can create a new active candidate for the newly promoted root immediately after promotion, because promotion leaves no candidate bound to the active pointer.
- Promotion neither reads nor rewrites the live feedback ledger, and unrelated later ledger edits do not affect a sealed promotion.
- `tests/test_roadmap_version_promotion.py` passes.

## References

- [hashlib — Secure Hashes and Message Digests](https://docs.python.org/3.13/library/hashlib.html) — Use SHA-256 over stored bytes when reproducing immutable evidence.
- [os.replace — Miscellaneous Operating System Interfaces](https://docs.python.org/3.13/library/os.html#os.replace) — Read for the atomic replacement behavior behind durable selector publication.
- [fcntl — The fcntl and ioctl System Calls](https://docs.python.org/3.13/library/fcntl.html) — Read for advisory locking used by the existing roadmap writer guard.

## Applicable guardrails

- **The plan’s “## Plan intent”, immutable artifacts and reviewer ledger:** This step may change only the canonical selector and must not turn mutable feedback into promotion input or artifact content.
- **The plan’s “## Step intent”, exact root, source, and snapshot:** This step must validate the reviewed active successor against its recorded processing pair rather than substitute a newer candidate or current reviewer state.
- **The plan’s “## Scope guardrails”, accepted-head authority:** This step must keep `AcceptedRoadmapHead` as the sole canonical-artifact selector and reuse the existing guarded publication path.
- **The plan’s “## Scope guardrails”, immutable batch evidence:** This step must use recorded candidate and review evidence, not rediscover eligible ledger items, responses, fingerprints, or derived context.
- **The plan’s “## Out of scope”, candidate lifecycle extensions:** This step must not add review protocols, candidate branches, stage-operation changes, or new feedback families.

## Deferred

- CLI surface changes — `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_promote_review_seal` remains outside this step because the existing command delegates to `promote_review_seal` and this step changes the promotion contract beneath that stable entry point.
