> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-versioned-feedback-revision-chain.md`.
> Preserved here for history; do not edit.

## Overview

Route ordinary roadmap feedback through the existing immutable candidate-version lifecycle after explicit enrollment. `--revise-feedback` refuses on an unenrolled roadmap with the existing `--enroll-version` next step; on an enrolled roadmap, it proposes an inert successor from `AcceptedRoadmapHead` through the existing candidate workflow. Only `--promote-review-seal` advances the accepted head, and later revisions build from that promoted successor without rewriting live top-level roadmap artifacts.

## Problem statement

The repository already supports an immutable version chain through `--enroll-version`, `--propose-candidate`, candidate review, exact review seals, and `--promote-review-seal`. The separate `--revise-feedback` route still requires an unenrolled roadmap and writes live artifacts through the legacy bounded writer, so ordinary feedback becomes unavailable after structural approval enrolls a roadmap. The route must be retired or narrowed while preserving an actionable transition for unenrolled users.

## Architecture

Keep `plan_tool/roadmap_version_enrollment.py` and `--enroll-version` as the only explicit root-enrollment path. An unenrolled `--revise-feedback` invocation inspects only enough state to return the enrollment requirement without invoking a backend or writing roadmap state; no command silently enrolls a roadmap.

For an enrolled roadmap, route the feedback selector to `plan_tool/roadmap_candidate_run.py:run_initial_candidate_proposal()`, which continues to own fixed feedback admission, accepted-predecessor selection, candidate materialization, full-roadmap gates, and inert candidate storage. Return the stored candidate identity and established next review command without copying candidate logic, adapting the unenrolled writer to mutate enrolled state, selecting a candidate, or making the accepted head follow live top-level files.

Keep `plan_tool/roadmap_candidate_review.py` responsible for the question, answer-bound replacement, and exact review seal. Keep `plan_tool/roadmap_version_promotion.py:promote_review_seal()` as the only feedback-candidate writer that advances `AcceptedRoadmapHead`, and retain `plan_tool/roadmap_revision_publish.py` as the shared publication journal and recovery boundary used by version-owned writers. The dedicated enrollment, candidate, review, answer, and promotion commands retain their existing contracts.

## Out of scope

New immutable-version schemas; a second candidate store; a second accepted-head
writer; a new review or approval protocol; structural-operation classification;
pending structural-proposal storage; multi-artifact structural publication;
automatic feedback grouping; and a general workflow or transaction framework.
Those structural concerns remain in the paused structural-approval plan.

## Risks

A convenience route can accidentally duplicate candidate admission or make a
stored candidate look accepted. Routing only the structural path would still
leave later bounded feedback rejected after enrollment. Reading live artifacts
instead of the accepted version would fork the version chain. Retiring the
legacy route without an actionable enrollment refusal would strand current
unenrolled users.

## Testing

Prove an unenrolled `--revise-feedback` invocation makes no backend call or
write and names `--enroll-version`; explicit root enrollment remains unchanged;
an enrolled ordinary-feedback invocation reuses the candidate proposal owner
and stores an inert successor from the accepted head; candidate storage does
not move the head or rewrite live artifacts; the existing review and
review-seal promotion path advances the head; stale-predecessor, feedback-drift,
gate, review, promotion, and recovery failures preserve the prior accepted
head; and a second ordinary-feedback proposal uses the first promoted successor
as its predecessor.

## Acceptance criteria

- No new version, candidate, review, promotion, or recovery subsystem is
  introduced.
- Unenrolled ordinary feedback receives an explicit, non-writing enrollment
  requirement; enrollment remains a separate operator action.
- Enrolled ordinary feedback delegates to the existing inert candidate
  proposal lifecycle with the exact selected feedback and accepted predecessor.
- Only existing review-seal promotion advances the accepted head, and it never
  rewrites live top-level roadmap artifacts.
- A second ordinary-feedback proposal derives from the newly promoted accepted
  version.
- The paused structural-approval plan can reuse this route without owning
  enrollment, candidate storage, review, promotion, or version recovery.

## Input

The repository already has the version chain needed by structural feedback:
`--enroll-version` creates the accepted root, `--propose-candidate` stores an
inert predecessor-bound candidate, candidate review creates an exact review
seal, and `--promote-review-seal` atomically advances the accepted head. The

## Scope guardrails

`AcceptedRoadmapHead` remains the sole canonical selector for an enrolled
roadmap. Candidate storage, a model reply, a review question, or a review seal
does not advance it. Promotion changes only the accepted head after exact
review-seal and current-predecessor verification; it does not rewrite live
top-level artifact paths. Every successor has one explicit accepted
predecessor, and no command silently enrolls a roadmap.

The feedback lifecycle stays unchanged: candidate construction carries the
selected request, and the proposed response remains reviewer-owned until the
existing review and promotion path makes its version canonical. This plan does
not introduce a second meaning of approval or bypass the candidate review
requirement.
