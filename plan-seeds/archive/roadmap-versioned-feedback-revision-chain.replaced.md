> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-versioned-feedback-revision-chain.md`.
> Preserved here for history; do not edit.

# Route ordinary roadmap feedback through immutable candidate versions

## Outcome

Ordinary roadmap feedback uses the existing immutable candidate-version
lifecycle after explicit enrollment. A revision proposes an inert successor
from the accepted head; only the existing review-seal promotion advances the
accepted head, and a later revision builds from that promoted successor.

## Problem statement

The repository already has the version chain needed by structural feedback:
`--enroll-version` creates the accepted root, `--propose-candidate` stores an
inert predecessor-bound candidate, candidate review creates an exact review
seal, and `--promote-review-seal` atomically advances the accepted head. The
separate `--revise-feedback` route still requires an unenrolled roadmap and
writes live artifacts through the legacy bounded writer. If structural
approval enrolls a roadmap, that legacy route becomes unavailable for later
ordinary feedback.

## In scope

Route ordinary feedback onto the existing enrolled candidate lifecycle;
define the explicit unenrolled-to-enrolled operator transition; preserve the
selected-feedback and predecessor bindings through proposal, review, and
promotion; and retire or narrow the legacy mutable route so future feedback
does not become impossible after enrollment.

## Out of scope

New immutable-version schemas; a second candidate store; a second accepted-head
writer; a new review or approval protocol; structural-operation classification;
pending structural-proposal storage; multi-artifact structural publication;
automatic feedback grouping; and a general workflow or transaction framework.
Those structural concerns remain in the paused structural-approval plan.

## Allowed behavior changes

`--revise-feedback` on an unenrolled roadmap refuses with the exact existing
`--enroll-version` next step rather than silently enrolling or continuing the
legacy in-place mutation. On an enrolled roadmap, ordinary feedback enters the
same inert candidate workflow already exposed by `--propose-candidate`; it does
not write live top-level roadmap artifacts or select a candidate by itself.
The dedicated enrollment, candidate, review, answer, and promotion commands
retain their existing contracts.

## Architecture

Reuse these boundaries as-is:

1. `plan_tool/roadmap_version_enrollment.py` and `--enroll-version` remain the
   only explicit root-enrollment path.
2. `plan_tool/roadmap_candidate_run.py:run_initial_candidate_proposal()` remains
   the owner of fixed feedback admission, accepted-predecessor selection,
   candidate materialization, full-roadmap gates, and inert candidate storage.
3. `plan_tool/roadmap_candidate_review.py` remains the owner of the question,
   answer-bound replacement, and exact review seal.
4. `plan_tool/roadmap_version_promotion.py:promote_review_seal()` remains the
   only feedback-candidate writer that advances `AcceptedRoadmapHead`.
5. `plan_tool/roadmap_revision_publish.py` remains the shared publication
   journal and recovery boundary used by those version-owned writers.

Add only the routing seam needed for ordinary feedback to select those owners.
For an unenrolled roadmap, inspect enough state to return the explicit
enrollment requirement without invoking a backend or writing roadmap state.
For an enrolled roadmap, pass the feedback selector into the existing candidate
proposal owner and return its stored candidate identity and established next
review command. Do not adapt the unenrolled writer to mutate enrolled state,
copy candidate logic, or make the accepted head follow live top-level files.

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

## References

- [BACKLOG #423](../BACKLOG.md): paused downstream structural-approval scope.
- [Roadmap format](../ROADMAP_FORMAT.md): immutable candidate-version authority
  and feedback lifecycle.
- [Version enrollment](../plan_tool/roadmap_version_enrollment.py): explicit
  root enrollment.
- [Candidate runner](../plan_tool/roadmap_candidate_run.py): existing
  predecessor-bound candidate construction and storage.
- [Candidate review](../plan_tool/roadmap_candidate_review.py): existing
  question, answer, replacement, and review-seal lifecycle.
- [Version promotion](../plan_tool/roadmap_version_promotion.py): accepted-head
  advancement.
- [Legacy revision runner](../plan_tool/roadmap_revision_run.py): unenrolled
  bounded writer to retire or narrow.
- [Revision publication](../plan_tool/roadmap_revision_publish.py): writer,
  journal, and recovery contracts.
- [Seed format](../SEED_FORMAT.md): seed ingestion requirements.
