---
format_version: 1
title: Roadmap Stack Aware Approval
intent: Structural roadmap content reaches the accepted head, or changes enrolled
  seed state, only through a confirmed structural approval of the whole unpromoted
  stack that carries it, whether that content is the top candidate or an ancestor
  of it. Every surface that asks for or confirms an approval presents that whole stack.
status: completed
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: plan-seeds/roadmap-stack-aware-approval.md
steps:
- id: 1
  title: Add one stack-route derivation beside source_ancestry_to_root that reads
    each hop's stored operation_classification above the candidate's recorded root
    up to the candidate, contributes nothing for a hop with no stored route, and reports
    an unreadable hop as underivable
  intent: Gives every guard and the recovery predicate a single shared answer to whether
    a candidate's unpromoted stack is structural, so the writer and recovery cannot
    disagree.
  files:
  - plan_tool/roadmap_candidate_run.py
  - tests/test_roadmap_candidate_run.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/roadmap-stack-aware-approval/01-one-stack-route-derivation-beside.md
  status: done
- id: 2
  title: 'Make the review-side guards stack-aware: the answered route refuses a structural
    stack, decision eligibility and the CLI precheck accept a presentation-only top
    of a structural stack, and the edit replacement check tests the stack (edit sourcing
    and the reject/discard pointer release stay as they are; the shared _require_structural_candidate
    and _require_active_structural_candidate guards, which the promotion loader also
    calls, change here)'
  intent: Stops a structural ancestor from reaching review through the answered route,
    and makes the structural decision reachable for the stack that carries it.
  files:
  - plan_tool/roadmap_candidate_review.py
  - plan_tool/cli/roadmap_cmd.py
  - tests/test_roadmap_candidate_review.py
  - tests/cli/test_roadmap_cmd.py
  - plan_tool/roadmap_version_promotion.py
  - tests/test_roadmap_version_promotion.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: the shared stack-route derivation each guard consults, including for an edit's
      not-yet-stored replacement
  detail: docs/implementation-plans/plan-details/roadmap-stack-aware-approval/02-make-review-side-guards-stack-aware.md
  status: done
- id: 3
  title: 'Make the promotion boundary and the recovery predicate stack-aware: a structural
    stack promotes only under a structural-approval seal on its top candidate and
    journals the enrolled seed-state member, and recovery reads the same derivation
    (the head write, the journal, and the recovery machinery are unchanged)'
  intent: Ensures structural content reaches the head, and changes enrolled seed state,
    only through a structural approval, including when an interrupted promotion is
    recovered.
  files:
  - plan_tool/roadmap_version_promotion.py
  - plan_tool/roadmap_revision_publish.py
  - tests/test_roadmap_version_promotion.py
  - tests/test_roadmap_revision_publish.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 2
  depends_on_notes:
    1: the shared stack-route derivation, used by both the writer and recovery
    2: the shared structural-candidate guard that its directly-approved loader calls
  detail: docs/implementation-plans/plan-details/roadmap-stack-aware-approval/03-make-promotion-boundary-recovery.md
  status: done
- id: 4
  title: 'Build the whole-stack view, its digest, and its one shared printout: the
    ordered hops above the candidate''s recorded root (id, stored route, selected
    feedback, own diff), the cumulative root-to-candidate diff from build_roadmap_diff,
    the promotion effects, a deterministic digest of the view''s content that never
    depends on the printout, and the one printout that steps 5 and 6 render'
  intent: Gives every structural approval surface one shared, render-independent description
    of the stack and one shared printout of it, plus a digest the confirm step can
    bind to, so no surface carries its own copy.
  files:
  - plan_tool/roadmap_candidate_review.py
  - plan_tool/cli/roadmap_cmd.py
  - tests/test_roadmap_candidate_review.py
  - tests/cli/test_roadmap_cmd.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: the stack route, and the hop ordering above the candidate's recorded root
  detail: docs/implementation-plans/plan-details/roadmap-stack-aware-approval/04-build-whole-stack-view-its-digest-its.md
  status: done
- id: 5
  title: 'Split structural approve into two invocations: without the confirm flag
    it prints step 4''s shared stack printout and the digest and writes nothing; with
    a matching digest it prints the same printout, seals and promotes, and it refuses
    with no write on a differing digest; regenerate the CLI reference'
  intent: Makes sure an operator approves the exact stack they saw, and that an approval
    whose digest differs from the one recomputed at confirm time seals nothing. The
    step's detail file owns the flag name, the result and exit status of each outcome,
    and whether an unconfirmed approve exits 0.
  files:
  - plan_tool/roadmap_candidate_review.py
  - plan_tool/cli/roadmap_cmd.py
  - docs/cli/roadmap.md
  - tests/test_roadmap_candidate_review.py
  - tests/cli/test_roadmap_cmd.py
  - tests/test_roadmap_candidate_run.py
  - tests/test_roadmap_version_promotion.py
  complexity: high
  change_type: feature
  depends_on:
  - 2
  - 3
  - 4
  depends_on_notes:
    2: decision eligibility for a presentation-only top of a structural stack
    3: a promotion boundary that accepts the structural-approval seal on the stack's
      top candidate
    4: the stack view and its shared printout, and the digest recomputed under the
      seal's writer guard
  detail: docs/implementation-plans/plan-details/roadmap-stack-aware-approval/05-split-structural-approve-two.md
  status: done
- id: 6
  title: Render step 4's shared stack printout on the structural decision's edit and
    reject outcomes (with a note that reject drops every unpromoted hop) and on the
    proposal output when its stack carries a structural hop; step 5 owns both approve
    invocations
  intent: Ends the top-hop-only presentation defect, so every surface that asks for
    or confirms a structural approval shows what the approval covers.
  files:
  - plan_tool/cli/roadmap_cmd.py
  - tests/cli/test_roadmap_cmd.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  - 4
  - 5
  depends_on_notes:
    2: the precheck and the derivation-stub test helper that the edit and reject arms
      build on
    4: the shared stack view and printout each surface renders
    5: the approve and non-approve split of the handler, and the build-and-print helper
  detail: docs/implementation-plans/plan-details/roadmap-stack-aware-approval/06-render-step-shared-stack-printout-on.md
  status: done
- id: 7
  title: Retire the interim structural batch block in _run_batch_candidate_proposal
    and its refusal tests, reopen the later-batch cell of the decision-eligibility
    matrix, and add end-to-end tests for the C1-structural/C2-presentation stack on
    the direct, answered, edited, and recovered routes (the stacking carve-out tests
    stay)
  intent: Lets the revision chain stack as designed once every guard under Guard sites,
    the stack view, and the confirm step are in place, and proves the property end
    to end.
  files:
  - plan_tool/roadmap_candidate_run.py
  - tests/test_roadmap_candidate_run.py
  - tests/test_roadmap_candidate_review.py
  - tests/test_roadmap_version_promotion.py
  - tests/cli/test_roadmap_cmd.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  - 3
  - 5
  - 6
  depends_on_notes:
    2: the answered route refuses a structural stack, and decision eligibility accepts
      its top
    3: promotion and recovery of a structural stack require structural approval and
      journal the seed effect
    5: approval is confirmed against the stack digest
    6: the structural decision and a structural-stack proposal present the whole stack
  detail: docs/implementation-plans/plan-details/roadmap-stack-aware-approval/07-retire-interim-structural-batch-block.md
  status: done
- id: 8
  title: 'Update the roadmap docs, the persisted-contract doc, and the review ledger
    so they describe stack-aware approval (two-invocation approve, whole-stack scope,
    no batch block), delete the shipped BACKLOG #431 entry, and reword every other
    backlog entry that names the block'
  intent: Keeps the operator docs, architecture notes, ledger, and backlog in line
    with shipped behavior, removes the shipped source backlog entry, and rewords the
    other entries that name the block (the adjacency note and the Out of scope line
    in entry 430). Nothing is deferred, so no follow-up entry is filed.
  files:
  - docs/how-to/roadmap.md
  - ROADMAP_FEEDBACK_FORMAT.md
  - docs/ARCHITECTURE.md
  - README.md
  - CAPABILITIES.md
  - ROADMAP_FORMAT.md
  - DATA_CONTRACT.md
  - handoffs/2026-09-23-roadmap-structural-feedback-approval-code-review.md
  - handoffs/2026-09-22-roadmap-feedback-revision-approval.md
  - BACKLOG.md
  - tests/test_roadmap_feedback_format.py
  - changelog.d/roadmap-stack-aware-approval.md
  complexity: low
  change_type: non-code
  depends_on:
  - 7
  depends_on_notes:
    7: the block is retired and the stack-aware property is verified
  detail: docs/implementation-plans/plan-details/roadmap-stack-aware-approval/08-update-roadmap-docs-persisted-contract.md
  status: done
---
# Roadmap Stack Aware Approval

## Overview

Make structural approval stack-aware and retire the interim batch block. Batches keep sourcing from the active candidate; approving the top candidate covers every unpromoted hop beneath it. Source entry: `BACKLOG.md` #431 (Jira `IPPT-9`), whose scope contract this plan carries; the review ledger `handoffs/2026-09-23-roadmap-structural-feedback-approval-code-review.md` (P2.1) records the defect and the owner's decisions.

## Problem statement

The revision chain stacks on purpose. `plan_tool/roadmap_candidate_run.py:_run_batch_candidate_proposal` sources a new batch from the active candidate, and `source_ancestry_to_root` walks back to the accepted root. The route is classified against each candidate's direct source (`plan_tool/roadmap_candidate.py:_classify_validated_operations`, called from `materialize_candidate`). A structural C1 can therefore sit under a wording-only C2 that classifies as presentation-only. C2 can then be promoted through the answered route (`--review-candidate` / `--answer-question` / `--promote-review-seal`) with no structural decision and no seed invalidation, carrying C1's structural change into the head (its replacement is sourced from C1).

Every guard that should stop this checks the candidate's own route: `_require_answered_review_route`, `_require_structural_candidate`, and `_require_active_structural_candidate` (`plan_tool/roadmap_candidate_review.py`), the answered-replacement refusal in the same module, the answered-seal guard in `plan_tool/roadmap_version_promotion.py:_load_complete_sealed_candidate`, `_load_complete_directly_approved_candidate`, `_structural_promotion_seed_member`, `plan_tool/roadmap_revision_publish.py:_selected_promotion_is_structural`, the CLI precheck in `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_structural_candidate_decision`, the proposal output's own-route check in `_render_candidate_proposal_result` (same module), and the edit path's "replacement is not structural" refusal. Because of these guards, `--decide-candidate C2 --candidate-decision approve` is refused today. The structural approval surface shows only the top hop: the disclosure (`_render_structural_candidate_disclosure`) prints the candidate's own `predecessor_diff` plus the source and root ids.

Until this effort ships, the interim backstop is a refusal in `_run_batch_candidate_proposal` (commit `ae3fb0bc`). While the active candidate's stored route is STRUCTURAL, `--propose-candidate` is refused before any backend call.

## Architecture

Owner decisions, 2026-09-24 (settled; do not re-open):

1. **Approval carries the stack.** A structural approval covers everything built on the approved candidate. The block is removed in this effort, after every guard that replaces it.
2. **The whole stack is presented** on every surface that asks for or confirms a structural approval: the structural decision, and the proposal output of a stack that carries a structural hop. Presenting only the top hop is the defect. Amended by the owner, 2026-09-24, after a necessity review (settled; do not re-open): the answered route's review, answer, and promote-review-seal output is not such a surface: an answered seal over a structural stack is refused, and a structural-approval seal it can promote was minted by a confirmed approve that presented the stack, so it keeps its current output. Presentation-only hops lower in a stack stay unshown there, as today.
3. **Approval has a separate confirm step.** `--decide-candidate ID --candidate-decision approve` without a confirm flag presents the stack and a digest, and writes nothing. This is also how a pending candidate is viewed. The same command with a confirm flag carrying that digest is the only invocation that seals and promotes. It refuses when the stack has changed since the digest was issued. No terminal prompt. It follows the repository's existing explicit-confirmation patterns (`--confirm-restore-revision`, `--confirm-feedback-reopen`, and decision settlement's `confirmation-required` result in `plan_tool/roadmap_decision_settlement_enrolled.py`). Step 5's detail file owns the flag's name and the per-value contract for each outcome and exit status: producer, precedence, consumers, and exit path. It states whether an unconfirmed approve exits 0, since automation can read exit 0 as approval.

Design decisions:

- **Stack route.** A stack is structural if and only if any hop above the candidate's recorded root, up to and including the candidate, has a stored `CandidateProposalEvidence.operation_classification` of STRUCTURAL. The route is derived at use from the ancestry above the candidate's recorded root (`root_version_id` in its stored evidence), never the current head, so the answer is the same on both sides of promotion and during recovery. The hops are the unpromoted candidates strictly above that root: the root's own stored route, or lack of one, is never read, because the root can be an enrolled root, a previously promoted structural candidate, or a head published by decision settlement. One derivation beside `source_ancestry_to_root` serves every guard and the recovery predicate, so writer and recovery cannot disagree. A hop with a stored route contributes it. A hop with no stored route (legacy evidence, or an answered replacement, which persists none) contributes nothing, and the derivation never reads meaning into an absent one. A hop that is missing, is not a stored candidate, or fails validation is a different case: it makes the whole stack underivable, every guard and the recovery predicate refuse it, and none reads it as "no structural hop". A candidate whose evidence records no root (selector-era evidence) has no unpromoted stack to derive: it yields no structural hop, which is distinct from underivable, so the answered-route entry, the answered-seal loader, and the recovery predicate keep their current behavior for it, as they do for an answered replacement and for legacy evidence that has no route. Stored routes are trustworthy: `_require_reproducible_batch_operations` replays them from their bytes on load.
- **Guards.** Each own-route guard listed in the Problem statement becomes stack-aware. The decision surface accepts a candidate whose own route is presentation-only when its stack is structural. The edit check tests the replacement's stack, its source's stack plus its own computed route, because the replacement is not stored when the check runs. The answered route refuses a structural stack. Every own-route site and its owner is listed under Guard sites. A structural stack can be promoted only with a `structural-approval` seal on its top candidate, and that promotion journals the enrolled seed-state member in the same publication.
- **No new binding.** A version id is the sha256 of a payload that includes `predecessor_version_id` (`plan_tool/roadmap_versions.py:_create_stored_version`). A seal that binds the top candidate's id therefore already binds every ancestor.
- **Stack view.** The view lists the hops in order above the candidate's recorded root, each with its id, stored route, selected feedback, and own diff. It adds the cumulative diff from root to candidate, computed deterministically from stored bytes (`plan_tool/roadmap_diff.py:build_roadmap_diff`) with no backend call, and states the promotion effects over the whole stack. The structural decision keeps everything its disclosure prints today, so the view extends that disclosure and never replaces it; step 4's detail file owns any per-hop field beyond the list above. On the structural decision it also states that reject drops every unpromoted hop. One printout of the view, owned by step 4, is what the structural decision and the proposal output of a stack that carries a structural hop render: step 5 wires it on both approve invocations (unconfirmed and confirm), and step 6 on edit, reject, and the proposal output. Nothing else renders it: `--reject-candidate`, `--discard-candidate`, the answered route's review, answer, and promote-review-seal output, and any stack with no structural hop keep their current output.
- **Digest.** The digest is a deterministic function of the stack view's content, not of how the terminal renders it. It is recomputed from stored records under the writer guard that the approval seal is published under, and a supplied digest other than the recomputed one refuses with no write. A candidate that is no longer active is already refused before any digest could be compared.
- **Sign-off.** The owner confirmed on 2026-09-24 (settled; do not re-open): the stack route is derived from stored routes at use, with no new persisted field; the confirm digest is stateless, so no confirmation receipt is persisted between the two runs; and the edit path's replacement check becomes stack-aware.
- **Edit and reject keep their contracts.** An edit's replacement is still sourced from the top candidate's own source. Reject and discard still release the whole active pointer, and the abandoned hops remain as immutable history. Only what these decisions present changes.

**Guard sites.** Every own-route site the sweep changes or keeps, with its owner:

| Site | Owner |
| --- | --- |
| `_require_answered_review_route` (answered-route entry) | step 2 |
| `_require_structural_candidate` and `_require_active_structural_candidate` (the decision, edit, and approve rechecks, and the promotion loader `_load_complete_directly_approved_candidate`, which calls the former) | step 2 changes the shared guards, so step 3 depends on step 2 |
| the CLI precheck in `_cmd_roadmap_structural_candidate_decision`; the edit path's "structural edit replacement is not structural" refusal | step 2 |
| the proposal output's own-route check in `_render_candidate_proposal_result` (whether the structural disclosure prints) | step 6 |
| the answered-seal guard `_load_complete_sealed_candidate`; `_structural_promotion_seed_member`; `_selected_promotion_is_structural` (recovery) | step 3 |
| the answered-replacement refusal ("structural replacement cannot use the answered review route") | stays own-route: the entry guard already refuses a structural stack, so only the replacement's own hop is left to classify |

## Scope guardrails

Binary observable: every candidate-lineage promotion whose hops above its recorded root include one with a stored STRUCTURAL route carries a `structural-approval` seal on its top candidate and journals the enrolled seed-state member. That seal has one construction site, the approve invocation that carries the confirm; the digest match is checked at confirm time and is not stored. No other promotion carries a STRUCTURAL hop.

Mechanism: the shared stack-route derivation is consumed by the stack-aware guards at answered-route entry, decision eligibility, the promotion boundary, and the seed and recovery predicates. The owning destination is the promotion boundary in `plan_tool/roadmap_version_promotion.py`, which remains the sole writer of candidate-lineage promotions to `AcceptedRoadmapHead`. Decision settlement (`plan_tool/roadmap_decision_settlement_enrolled.py`) and root enrollment (`plan_tool/roadmap_versions.py`) publish their own heads through routes this plan leaves unchanged. Ordering fence: the batch block's removal lands after every guard, the stack view, and the confirm step have landed. No intermediate state stacks under a structural candidate without stack-aware guards.

Not allowed:

- Any quality or semantic judgment of stack content.
- A cumulative classifier derived from content.
- A second structural gate, or a separate approval for each hop.
- A new persisted stack or binding field, unless the property breaks without it for a named consumer.
- Auto-approval.
- A terminal prompt.
- Any change to the promotion writer's authority over candidate-lineage promotions, the publication journal, the recovery machinery (only the structural predicate it consults becomes stack-aware), or the version and candidate stores.
- A separate read-only show command. Deliberately not built: an unconfirmed approve is how a pending candidate is viewed (owner decision, 2026-09-24). No `BACKLOG.md` entry is filed for it.
- A confirm step for edit or reject, including rejecting a multi-hop stack. Their outputs present the whole stack, but only approve gets a confirm step. No `BACKLOG.md` entry is filed for it.
- Stack output on `--reject-candidate`, `--discard-candidate`, or the answered route's review, answer, and promote-review-seal output. None asks for or confirms a structural approval, and each keeps its contract; only the structural decision's reject carries the note. Showing presentation-only hops lower in a stack there is deliberately not built, and no `BACKLOG.md` entry is filed for it.
- Wider run-log coverage for the decision commands.
- The ledger's current/stale label (BACKLOG #428).
- Any behavior change for legacy candidates that have no route.

## References

- [`handoffs/2026-09-23-roadmap-structural-feedback-approval-code-review.md`](../handoffs/2026-09-23-roadmap-structural-feedback-approval-code-review.md): P2.1 defect, the interim block, and the owner decisions.
- [`docs/implementation-plans/2-roadmap-structural-feedback-approval.md`](../docs/implementation-plans/2-roadmap-structural-feedback-approval.md): the structural approval lifecycle this effort extends.
- [`ROADMAP_FEEDBACK_FORMAT.md`](../ROADMAP_FEEDBACK_FORMAT.md): the feedback lifecycle and the batch stacking rule.
- [`docs/how-to/roadmap.md`](../docs/how-to/roadmap.md): operator workflow.
- [`plan_tool/roadmap_candidate_run.py`](../plan_tool/roadmap_candidate_run.py): batch sourcing, ancestry walk, and stored route evidence.
- [`plan_tool/roadmap_candidate_review.py`](../plan_tool/roadmap_candidate_review.py): structural decision, route guards, and seals.
- [`plan_tool/roadmap_version_promotion.py`](../plan_tool/roadmap_version_promotion.py): the candidate-lineage promotion writer and the seed-state member.
- [`plan_tool/roadmap_revision_publish.py`](../plan_tool/roadmap_revision_publish.py): the recovery predicate for structural promotions.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Run-log lifecycles for the decision commands (the owner's separate aim, tracked in the review ledger), BACKLOG #428, and the unreachable selected-local runner (BACKLOG #429).
- Changing edit sourcing, reject/discard pointer release, `_classify_validated_operations`, or operation authority.
- Feedback-state effects of promotion beyond what promotion already does.
- Seals minted by the earlier single-command approve are not migrated: that command sealed and promoted in one invocation, so an unpromoted seal can exist only after an interruption, and it stays promotable while its candidate is still the active one; a later stacked batch makes it stale.

## Risks

- A guard missed during the sweep reopens the defect; enumerate by identifier (`operation_classification`) and by vocabulary (route, structural, own source) first.
- Recovery that computes the route differently from the writer can finish a promotion without its seed effect.
- A derivation shared by the writer and recovery that reads an unreadable hop as "no structural hop" lets a promotion finish without its seed effect. Recovery refuses an unreadable candidate today (its predicate returns unknown, and the legacy check declines when the evidence file exists), and the new derivation must keep that.
- A digest that includes rendering can refuse a valid confirm. A digest that leaves out a hop can confirm a stack the operator never saw.

## Testing

Stage-separated replay. **Property and routes:** a structural hop under a presentation-only top is refused on the answered route, is presented on the decision surface, and reaches the head only through a confirmed structural approval that journals the seed effect. This holds for direct, answered, edited, and recovered promotions. A supplied digest that differs from the recomputed one refuses with no write. **Bare stage:** keep the property, the ordering fence, the single-derivation decision, and the owner decisions. Defer the flag name, the outcome vocabulary, the exit status of each outcome, and the view layout to the detail files: step 5's owns the first three, step 4's the layout. **Detail-grounded stage:** may require the reproduced C1-structural/C2-presentation stack end to end; the confirm/refuse matrix (no flag, matching digest, differing digest, and a candidate that is no longer active), each pinning its outcome and exit status; a digest that changes when any hop's stored content or the hop set changes and stays fixed when only the printout's wording changes; edit and reject running with no confirm flag; an edit accepted when its replacement's stack carries a structural hop, including one over a structural lower hop, and refused when it does not; recovery after an interrupted structural-stack promotion; an unreadable hop refused at the promotion boundary and at recovery; the carve-outs for legacy candidates without a route or without a recorded root, for all-presentation stacks, and for a stack rooted at an enrolled root or at a previously promoted structural candidate (a settlement-published head shares their property, because the walk ends at the root by id and never loads it), each asserted as a carve-out, including that the answered route's output, standalone `--reject-candidate` and `--discard-candidate` output, and a stack with no structural hop keep their current output; and replacement of the block's refusal tests.

## Acceptance criteria

- The binary observable in Scope guardrails holds on the direct, answered, edited, and recovered routes. An edit is accepted when its replacement's stack carries a structural hop and refused when it does not.
- A presentation-only candidate stacked on a structural one cannot be promoted through the answered route. It can be approved through `--decide-candidate`, and its promotion journals the enrolled seed-state member.
- An approve without the confirm flag writes nothing. An approve with the confirm flag seals and promotes only when the supplied digest equals the digest recomputed for the candidate; a differing digest refuses with no write. The digest changes when a hop's stored content or the hop set changes, and does not change when only the printout's wording or layout changes.
- The structural decision, and the proposal output of a stack that carries a structural hop, present every hop above the candidate's recorded root, with the cumulative diff. The answered route's output, `--reject-candidate` and `--discard-candidate` output, and the output of a stack with no structural hop are unchanged. The structural decision's reject output states that reject drops every unpromoted hop.
- The batch block and its refusal tests are gone, replaced by tests of the new property; the stacking carve-out tests still pass; the docs, the ledger, and the 2026-09-22 handoff no longer state the block as current behavior and describe the two-invocation approve and the whole-stack scope of a structural approval, and the existing pin in `tests/test_roadmap_feedback_format.py` matches the reworded approval sentence.
- Legacy candidates without a route or without a recorded root, all-presentation stacks, and stacks rooted at an enrolled root or a previously promoted structural candidate keep their current routes.
- An unreadable hop makes the stack underivable: every guard and the recovery predicate refuse it, and no promotion or recovery completes without its seed effect.
- `BACKLOG.md` #431 is deleted when step 8 ships. No follow-up entry is filed, because nothing is deferred. Every other entry that names the block is reworded, found by grepping the backlog for the block's wording (entry 430 has two such references).
- `changelog.d/roadmap-stack-aware-approval.md` states the two user-visible changes: the two-invocation approve and stacking under a structural candidate.

## Deferred

None. The confirm step for rejecting a multi-hop stack and the read-only show command are refused, not deferred; see Scope guardrails, Not allowed. No `BACKLOG.md` entry is filed for either.
