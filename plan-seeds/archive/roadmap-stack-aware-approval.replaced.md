> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-stack-aware-approval.md`.
> Preserved here for history; do not edit.

## Outcome

Structural roadmap content reaches the accepted head, or changes enrolled seed state, only through a confirmed structural approval of the whole unpromoted stack that carries it, whether that content is the top candidate or an ancestor of it. Every surface that asks for or confirms an approval presents that whole stack.

## Overview

Make structural approval stack-aware and retire the interim batch block. Batches keep sourcing from the active candidate; approving the top candidate covers every unpromoted hop beneath it. Source entry: `BACKLOG.md` #431, whose scope contract this seed carries; the review ledger `handoffs/2026-09-23-roadmap-structural-feedback-approval-code-review.md` (P2.1) records the defect and the owner's decisions.

## Problem statement

The revision chain stacks on purpose. `plan_tool/roadmap_candidate_run.py:_run_batch_candidate_proposal` sources a new batch from the active candidate, and `source_ancestry_to_root` walks back to the accepted root. The route is classified against each candidate's direct source (`plan_tool/roadmap_candidate.py:_classify_validated_operations`, called from `materialize_candidate`). A structural C1 can therefore sit under a wording-only C2 that classifies as presentation-only. C2 can then be promoted through the answered route (`--review-candidate` / `--answer-question` / `--promote-review-seal`) with no structural decision and no seed invalidation, carrying C1's structural change into the head (its replacement is sourced from C1).

Every guard that should stop this checks the candidate's own route: `_require_answered_review_route` and `_require_structural_candidate` (`plan_tool/roadmap_candidate_review.py`), the answered-seal guard in `plan_tool/roadmap_version_promotion.py:_load_complete_sealed_candidate`, `_load_complete_directly_approved_candidate`, `_structural_promotion_seed_member`, `plan_tool/roadmap_revision_publish.py:_selected_promotion_is_structural`, the CLI precheck in `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_structural_candidate_decision`, and the edit path's "replacement is not structural" refusal. Because of these guards, `--decide-candidate C2 --candidate-decision approve` is refused today. Every review surface shows only the top hop: the disclosure (`_render_structural_candidate_disclosure`) prints the candidate's own `predecessor_diff` plus the source and root ids, and `--promote-review-seal` prints only the promoted version id.

Until this effort ships, the interim backstop is a refusal in `_run_batch_candidate_proposal` (commit `ae3fb0bc`). While the active candidate's stored route is STRUCTURAL, `--propose-candidate` is refused before any backend call.

## Architecture

Owner decisions, 2026-09-24 (settled; do not re-open):

1. **Approval carries the stack.** A structural approval covers everything built on the approved candidate. The block is removed in this effort, after every guard that replaces it.
2. **The whole stack is presented** on every surface that asks for or confirms an approval: the structural decision, the answered route's review, answer, and promote surfaces, and the proposal output. Presenting only the top hop is the defect.
3. **Approval has a separate confirm step.** `--decide-candidate ID --candidate-decision approve` without a confirm flag presents the stack and a digest, and writes nothing. This is also how a pending candidate is viewed. The same command with a confirm flag carrying that digest is the only invocation that seals and promotes. It refuses when the stack has changed since the digest was issued. No terminal prompt. It follows the repository's existing explicit-confirmation patterns (`--confirm-restore-revision`, `--confirm-feedback-reopen`, and decision settlement's `confirmation-required` result in `plan_tool/roadmap_decision_settlement_enrolled.py`). `create` derives the flag's name and the per-value contract for each outcome and exit status: producer, precedence, consumers, and exit path.

Design decisions:

- **Stack route.** A stack is structural if and only if any hop from the accepted root to the candidate has a stored `CandidateProposalEvidence.operation_classification` of STRUCTURAL. The route is derived at use from the ancestry. One derivation beside `source_ancestry_to_root` serves every guard and the recovery predicate, so writer and recovery cannot disagree. The derivation reads the stored value and never reads meaning into an absent one. Answered replacements and legacy evidence that has no route keep their current behavior. Stored routes are trustworthy: `_require_reproducible_batch_operations` replays them from their bytes on load.
- **Guards.** Each own-route guard listed in the Problem statement becomes stack-aware. The decision surface accepts a candidate whose own route is presentation-only when its stack is structural. The answered route refuses a structural stack. A structural stack can be promoted only with a `structural-approval` seal on its top candidate, and that promotion journals the enrolled seed-state member in the same publication.
- **No new binding.** A version id is the sha256 of a payload that includes `predecessor_version_id` (`plan_tool/roadmap_versions.py:_create_stored_version`). A seal that binds the top candidate's id therefore already binds every ancestor.
- **Stack view.** The view lists the hops in order from the accepted root, each with its id, stored route, selected feedback, and own diff. It adds the cumulative diff from root to candidate, computed deterministically from stored bytes (`plan_tool/roadmap_diff.py:build_roadmap_diff`) with no backend call, and states the promotion effects over the whole stack. On surfaces that can end the stack, it also states that reject drops every unpromoted hop.
- **Digest.** The digest is a deterministic function of the stack view's content, not of how the terminal renders it. It is recomputed from stored records under the writer guard that the approval seal is published under.
- **Sign-off.** The owner confirmed on 2026-09-24 (settled; do not re-open): the stack route is derived from stored routes at use, with no new persisted field; the confirm digest is stateless, so no confirmation receipt is persisted between the two runs; and the edit path's replacement check becomes stack-aware.
- **Edit and reject keep their contracts.** An edit's replacement is still sourced from the top candidate's own source. Reject and discard still release the whole active pointer, and the abandoned hops remain as immutable history. Only what these decisions present changes.

## In scope

- One stack-route derivation, and stack-aware guards at answered-route entry, decision eligibility, edit acceptance, the promotion boundary, and the seed and recovery predicates.
- The whole-stack view on the proposal output, the structural decision, and the answered route's review, answer, and promote surfaces.
- The two-invocation approve with a digest-bound confirm.
- Removing the batch block and its refusal tests, updating the tests and docstrings that assume it (`tests/test_roadmap_candidate_run.py`, and the decision-eligibility matrix in `tests/test_roadmap_candidate_review.py`, whose later-batch cell becomes reachable again), and replacing them with tests of the new property. The stacking carve-out tests stay: they remain true.
- Documentation: `docs/how-to/roadmap.md`, `ROADMAP_FEEDBACK_FORMAT.md`, and `docs/ARCHITECTURE.md` no longer state the block; the review ledger's settled-decision bullet records the replacement; the generated CLI reference follows the parser.
- Backlog reconciliation. The plan's final docs and status step removes `BACKLOG.md` #431 after full shipment, marks it plan-authored while execution is pending, and leaves any deferred follow-up filed.

## Scope guardrails

Binary observable: every promotion whose ancestry from the accepted root contains a hop with a stored STRUCTURAL route is sealed as `structural-approval` on its top candidate after a matching confirm digest, and it journals the enrolled seed-state member. No other promotion carries a STRUCTURAL hop.

Mechanism: the shared stack-route derivation is consumed by the stack-aware guards at answered-route entry, decision eligibility, the promotion boundary, and the seed and recovery predicates. The owning destination is the promotion boundary in `plan_tool/roadmap_version_promotion.py`, which remains the sole writer of `AcceptedRoadmapHead`. Ordering fence: the batch block's removal lands after every guard, the stack view, and the confirm step have landed. No intermediate state stacks under a structural candidate without stack-aware guards.

Not allowed:

- Any quality or semantic judgment of stack content.
- A cumulative classifier derived from content.
- A second structural gate, or a separate approval for each hop.
- A new persisted stack or binding field, unless the property breaks without it for a named consumer.
- Auto-approval.
- A terminal prompt.
- Any change to the promotion writer's sole-writer authority, the publication journal, the recovery machinery (only the structural predicate it consults becomes stack-aware), or the version and candidate stores.
- A separate read-only show command.
- A confirm step for edit or reject. Their outputs present the whole stack, but only approve gets a confirm step.
- Wider run-log coverage for the decision commands.
- The ledger's current/stale label (BACKLOG #428).
- Any behavior change for legacy candidates that have no route.

## Out of scope

- Run-log lifecycles for the decision commands (the owner's separate aim, tracked in the review ledger), BACKLOG #428, and the unreachable selected-local runner (BACKLOG #429).
- Changing edit sourcing, reject/discard pointer release, `_classify_validated_operations`, or operation authority.
- Feedback-state effects of promotion beyond what promotion already does.

## Allowed behavior changes

`--propose-candidate` stacks under a structural candidate; `--decide-candidate` accepts a presentation-only top of a structural stack; an unconfirmed approve writes nothing and prints stack and digest; the answered route refuses a structural stack; structural-stack promotions journal seed invalidation; review, proposal, and promotion output presents the whole stack. Nothing else changes.

## Allowed reorganization

None beyond one shared stack-route derivation in the candidate storage layer, which every guard and the recovery predicate consume. This is necessary because the writer and recovery must return one answer.

## Risks

- A guard missed during the sweep reopens the defect; enumerate by identifier (`operation_classification`) and by vocabulary (route, structural, own source) first.
- Recovery that computes the route differently from the writer can finish a promotion without its seed effect.
- A digest that includes rendering can refuse a valid confirm. A digest that leaves out a hop can confirm a stack the operator never saw.

## Testing

Stage-separated replay. **Property and routes:** a structural hop under a presentation-only top is refused on the answered route, is presented on the decision surface, and reaches the head only through a confirmed structural approval that journals the seed effect. This holds for direct, answered, edited, and recovered promotions. A stale digest refuses with no write. **Bare stage:** keep the property, the ordering fence, the single-derivation decision, and the owner decisions. Defer the flag name, the outcome vocabulary, and the view layout to `create` and `detail`. **Detail-grounded stage:** may require the reproduced C1-structural/C2-presentation stack end to end; the confirm/refuse matrix (no flag, matching digest, stale digest after a new batch, and after an edit or reject); recovery after an interrupted structural-stack promotion; the carve-outs for legacy candidates without a route and for all-presentation stacks; and replacement of the block's refusal tests.

## Acceptance criteria

- The binary observable in Scope guardrails holds on the direct, answered, edited, and recovered routes.
- A presentation-only candidate stacked on a structural one cannot be promoted through the answered route. It can be approved through `--decide-candidate`, and its promotion journals the enrolled seed-state member.
- An approve without the confirm flag writes nothing. An approve with the confirm flag seals and promotes only when the digest matches the current stack.
- Every approve/confirm surface, and the proposal output, presents every unpromoted hop from the accepted root to the candidate, together with the cumulative diff.
- The batch block and its refusal tests are gone, replaced by tests of the new property; the stacking carve-out tests still pass; the docs and ledger no longer state the block.
- Legacy candidates without a route, and all-presentation stacks, keep their current routes.
- `BACKLOG.md` #431 is reconciled as described in In scope.

## Deferred

- A confirm step for rejecting a multi-hop stack.
- A read-only show command, if ever needed.

## Stop / defer

File in `BACKLOG.md` / `BUG_BACKLOG.md` any discovery needing a new persisted binding, a change to the publication journal or recovery machinery, a change to edit sourcing, or wider run-log coverage. Stop and surface the problem if the stack route cannot be derived from stored evidence without a new persisted field.

## References

- [`handoffs/2026-09-23-roadmap-structural-feedback-approval-code-review.md`](../handoffs/2026-09-23-roadmap-structural-feedback-approval-code-review.md): P2.1 defect, the interim block, and the owner decisions.
- [`docs/implementation-plans/2-roadmap-structural-feedback-approval.md`](../docs/implementation-plans/2-roadmap-structural-feedback-approval.md): the structural approval lifecycle this effort extends.
- [`ROADMAP_FEEDBACK_FORMAT.md`](../ROADMAP_FEEDBACK_FORMAT.md): the feedback lifecycle and the batch stacking rule.
- [`docs/how-to/roadmap.md`](../docs/how-to/roadmap.md): operator workflow.
- [`plan_tool/roadmap_candidate_run.py`](../plan_tool/roadmap_candidate_run.py): batch sourcing, ancestry walk, and stored route evidence.
- [`plan_tool/roadmap_candidate_review.py`](../plan_tool/roadmap_candidate_review.py): structural decision, route guards, and seals.
- [`plan_tool/roadmap_version_promotion.py`](../plan_tool/roadmap_version_promotion.py): the sole accepted-head writer and the seed-state member.
- [`plan_tool/roadmap_revision_publish.py`](../plan_tool/roadmap_revision_publish.py): the recovery predicate for structural promotions.
