> **Withdrawn 2026-09-22** — Superseded 2026-09-22: roadmap-lifetime selector admission cannot support successive ordinary feedback revisions; the replacement plan derives accepted-head-scoped feedback batches.
> Preserved here for history; do not edit.

---
format_version: 1
title: Roadmap Versioned Feedback Revision Chain
intent: Ordinary roadmap feedback uses the existing immutable candidate-version lifecycle
  after explicit enrollment. A revision proposes an inert successor from the accepted
  head; only the existing review-seal promotion advances the accepted head, and a
  later revision builds from that promoted successor.
status: planning
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: plan-seeds/roadmap-versioned-feedback-revision-chain.md
steps:
- id: 1
  title: Route --revise-feedback to inert candidates, preserve candidate storage,
    and retire legacy artifact, baseline, and seed-state replacements
  intent: Ordinary feedback remains available after enrollment while unenrolled roadmaps
    receive a non-writing --enroll-version handoff.
  files:
  - plan_tool/cli/roadmap_cmd.py
  - tests/cli/test_roadmap_cmd.py
  complexity: medium
  change_type: feature
  status: current
- id: 2
  title: Document --revise-feedback as an immutable candidate shortcut and remove
    legacy local-writer guidance
  intent: Readers and future plans see one consistent enrollment, candidate review,
    promotion, and failure-preservation workflow.
  files:
  - ROADMAP_FORMAT.md
  - README.md
  - CAPABILITIES.md
  - DATA_CONTRACT.md
  - RUNBOOK.md
  - BACKLOG.md
  - BUG_BACKLOG.md
  - CLAUDE.md
  - TESTING.md
  - docs/ARCHITECTURE.md
  - docs/cli/roadmap.md
  - docs/how-to/common-workflows.md
  - docs/how-to/roadmap.md
  - docs/reference/commands.md
  - tests/test_roadmap_format.py
  complexity: high
  change_type: non-code
  depends_on:
  - 1
  depends_on_notes:
    1: Provides the landed command behavior and output that the documentation and
      contract checks must describe.
---
# Roadmap Versioned Feedback Revision Chain

## Overview

Route ordinary roadmap feedback through the existing immutable candidate-version lifecycle after explicit enrollment. `--revise-feedback` refuses on an unenrolled roadmap with the existing `--enroll-version` next step; on an enrolled roadmap, it proposes an inert successor from `AcceptedRoadmapHead` through the existing candidate workflow. Only `--promote-review-seal` advances the accepted head, and later revisions build from that promoted successor without rewriting live top-level roadmap artifacts.

## Problem statement

The repository already supports an immutable version chain through `--enroll-version`, `--propose-candidate`, candidate review, exact review seals, and `--promote-review-seal`. The separate `--revise-feedback` route still requires an unenrolled roadmap and writes live artifacts through the legacy bounded writer, so ordinary feedback becomes unavailable after structural approval enrolls a roadmap. The route must be retired or narrowed while preserving an actionable transition for unenrolled users.

## Architecture

Keep `plan_tool/roadmap_version_enrollment.py` and `--enroll-version` as the only explicit root-enrollment path. An unenrolled `--revise-feedback` invocation inspects only enough state to return the enrollment requirement without invoking a backend or writing roadmap state; no command silently enrolls a roadmap.

For an enrolled roadmap, route the feedback selector to `plan_tool/roadmap_candidate_run.py:run_initial_candidate_proposal()`, which continues to own fixed feedback admission, accepted-predecessor selection, candidate materialization, full-roadmap gates, and inert candidate storage. Return the stored candidate identity and established next review command without copying candidate logic, adapting the unenrolled writer to mutate enrolled state, selecting a candidate, or making the accepted head follow live top-level files.

Keep `plan_tool/roadmap_candidate_review.py` responsible for the question, answer-bound replacement, and exact review seal. Keep `plan_tool/roadmap_version_promotion.py:promote_review_seal()` as the only feedback-candidate writer that advances `AcceptedRoadmapHead`, and retain `plan_tool/roadmap_revision_publish.py` as the shared publication journal and recovery boundary used by version-owned writers. The dedicated enrollment, candidate, review, answer, and promotion commands retain their existing contracts.

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

## References

- [argparse — Parser for command-line options, arguments and subcommands](https://docs.python.org/3.13/library/argparse.html) — Covers option actions, validation, and mutually exclusive CLI modes needed to route the revision commands.
- [Configuration | Pydantic Docs](https://docs.pydantic.dev/latest/api/config/) — Documents strict, frozen, and extra-forbidden model configuration used by immutable version records.
- [Validators | Pydantic Docs](https://docs.pydantic.dev/latest/concepts/validators/) — Explains field and model validators used to enforce predecessor, identity, and accepted-head invariants.
- [hashlib — Secure hashes and message digests](https://docs.python.org/3.13/library/hashlib.html) — Documents SHA-256 hashing used for content identities, version IDs, and exact review bindings.
- [os — Miscellaneous operating system interfaces](https://docs.python.org/3.13/library/os.html) — Covers replace, link, fsync, and directory operations underlying atomic durable publication and recovery.
- [fcntl — The fcntl and ioctl system calls](https://docs.python.org/3.13/library/fcntl.html) — Documents POSIX advisory file locking used to serialize accepted-head writers and readers.
- [How to monkeypatch/mock modules and environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Covers isolated substitution of backend and write boundaries for proving refusal and failure-path side effects.

## Steps

See the `steps:` block in the frontmatter.

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

## Deferred

- Structural-feedback integration remains deferred to the paused
  structural-approval plan because it requires separate classification,
  proposal-storage, and multi-artifact publication contracts.
