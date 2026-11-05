# Roadmap feedback revision and approval handoff

## Purpose

Record the completed roadmap feedback revision and structural-approval work. This
handoff preserves the implementation boundary and any separate follow-up; it
does not assign a new plan.

## Settled direction

Roadmap feedback revisions use a commit-like immutable history. Each feedback update proposes a successor from the accepted head, review binds exact candidate bytes, promotion advances only the accepted-head selector, and the next update starts from the promoted successor. Live top-level roadmap files are not a mutable working tree for pending feedback.

The structural approval gate now uses that history. Users submit one ordinary
feedback type. Valid typed operations determine whether the bounded or
structural candidate path applies; users never pre-classify feedback as
structural. Approval binds one reviewed top candidate and covers every
unpromoted candidate beneath it, edit creates a replacement for a fresh
decision, rejection releases only the active candidate, and promotion alone
advances the accepted head.

## Completion record

The revision-history plan and the Roadmap Structural Feedback Approval plan are
complete. The latter documents and implements one ordinary feedback intake,
validated operation routing, exact structural approval, promotion-only
publication, failure preservation, enrolled seed-state effects, and
accepted-version predecessors for later feedback revisions. Its documentation
and focused contract tests close BACKLOG #423.

The detail-grounded audit is clean at 7/7 detail coverage
(`20260923-220408-completeness.md`). Three complete post-run
`reconcile-code --all` sweeps cover all six code steps; step 7 is non-code.
Four independent post-run `/code-review` passes (`high`, headless) found three
routes by which structural content could reach the accepted head without a
structural decision, plus test and documentation gaps; each is fixed and pinned.
The answered route refuses a structural initial candidate and a structural
replacement, and promotion refuses an answered seal whose initial candidate is
structural. The full suite is green (13,730 passed, 190 skipped). The
loop closed on 2026-09-24 by owner decision on executed evidence — a randomized
state-machine search of 51,000 transitions with a route-independent oracle found
no violation — short of the two-consecutive-clean-pass rule. The findings,
dispositions, and convergence status are in the review record below.

The property those guards protect — structural content reaches the accepted
head, or changes enrolled seed state, only through a structural approval — holds
for stacked candidates too. The `roadmap-stack-aware-approval` plan (2026-09-24)
carries it: a new `--propose-candidate` batch stacks under a structural
candidate, and an approval covers the whole unpromoted stack in two invocations,
the second bound to a digest of the stack the first printed.

The plans remained sequential: approval consumes the immutable candidate,
review-seal, promotion, publication-journal, and accepted-head contracts from
revision history. Separate selector-shaped escalation, settlement, analysis,
and exact-pair rewrite routes remain outside ordinary proposal approval.

## Current artifacts

- Revision-history plan: `docs/implementation-plans/archive/2-roadmap-versioned-feedback-revision-chain.md` (`completed`). Its seed was consumed by `create`; the final generation is archived at `plan-seeds/archive/roadmap-versioned-feedback-revision-chain.replaced.2.md`.
- Revision-history review record: `handoffs/2026-09-23-roadmap-versioned-feedback-revision-chain-code-review.md`.
- Revision-history pull request: `https://github.com/rupe120/plan-tool/pull/18`, squash-merged 2026-09-23.
- Structural-approval plan: `docs/implementation-plans/archive/2-roadmap-structural-feedback-approval.md`.
- Structural-approval review record: `handoffs/2026-09-23-roadmap-structural-feedback-approval-code-review.md`.
- Stack-aware approval plan: `docs/implementation-plans/archive/2-roadmap-stack-aware-approval.md`. It extends the structural-approval lifecycle to the whole unpromoted stack.
- Reconstruction evidence: `<integration-consumer-root>/.tmp/plan-tool-423-structural-roadmap-feedback-revision-reconstruction.md`.

The structural-approval plan completes the approval work; do not treat its seed
or this handoff as an active pickup instruction.

## Reuse boundary

The completed approval plan reuses the immutable candidate store,
`AcceptedRoadmapHead`, candidate review bindings, exact review seal, promotion
writer, publication journal, checkpoint/recovery behavior, feedback-state
handling, and seed invalidation. It introduces no second version chain,
candidate store, accepted-head writer, or transaction system.

## Remaining boundary

The lifecycle does not add workflow authoring, automatic approval, feedback
grouping, multi-user approval, or a general transaction system. Any work on
those capabilities requires a separate decision and plan.
