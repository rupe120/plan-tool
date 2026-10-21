> **Replaced**: this file has been superseded by
> `docs/implementation-plans/archive/2-completeness-coverage-replay.md`.
> Preserved here for history; do not edit.

# completeness-coverage-replay: measure a safe completeness-audit refresh cadence

## Outcome

A small, versioned corpus of fully captured completeness-audit cases and a
deterministic replay produce one evidence-bound result: a full-discovery
cadence that retains every labelled fresh finding, `no-safe-cadence`, or
`insufficient-evidence`. The result changes no audit behavior; it only decides
whether BACKLOG #173 can be scoped.

## Overview

BACKLOG #173 defers a fingerprint-gated audit cache and re-check lane until
evidence selects their full-discovery cadence. Existing report history is not
automatically admissible: a saved review may omit the plan/detail/code identity
needed to tell whether a reuse candidate observed the same inputs. This effort
creates the measurement rather than treating incomplete history as proof.

## Problem statement

A reuse schedule can reduce model calls only if it never hides a finding a
fresh full-discovery audit would surface. The binary observable is whether each
eligible captured case's labelled fresh finding set remains represented by the
simulated schedule. Missing or ambiguous identity is not absence of a finding;
it makes the case ineligible.

## Architecture

The corpus stores each case's captured plan, selected detail, code,
stage/grade, and audit configuration identity beside an authoritative fresh
full-discovery label. Candidate schedules are declared before replay and retain
an always-fresh control; only a reuse schedule with no labelled discovery loss
can be reported as selectable. The replay is deterministic and reads the
corpus without invoking a model. Its report names every excluded case and every
missed label, so it cannot turn uncertainty into a safe result.

`plan_tool.review_persistence:SavedReview` can persist plan/detail/code
fingerprints for current captures, while
`plan_tool.review_persistence:AuditInputSnapshot` captures the plan/detail
inputs and `plan_tool.fingerprint:compute_code_fingerprint` captures the
watched code map. Legacy reports that lack any required identity remain
ineligible; the corpus must not reconstruct them from filenames or prose.

## Out of scope

- Implementing #173's cache, re-check lane, or a new audit CLI surface.
- Changing completeness prompts, pass budgets, gate behavior, exit codes, or
  existing saved-report semantics.
- Content-based finding matching, inferred labels, or an automatic cadence
  decision.
- Expanding the corpus to unrelated authoring or roadmap benchmarks.

## Risks

The corpus may contain too few eligible cases, or every reuse schedule may
miss a labelled finding. Either result leaves #173 deferred. Model-generated
finding identifiers may not establish identity across independent runs, so the
corpus must use explicit fresh labels and report unresolved comparisons rather
than matching by prose.

## Testing

The replay proves that a candidate schedule missing a labelled fresh finding is
rejected, a case without complete input identity is excluded rather than counted
as covered, and rerunning from the same corpus yields the same report without a
model call. The bare-plan audit preserves the evidence boundary; the
detail-grounded audit may require the corpus, labels, and report to cover every
declared candidate schedule before implementation starts.

## Acceptance criteria

- A committed corpus identifies every eligible case's complete input identity
  and fresh full-discovery label.
- The deterministic replay reports all candidate schedules, exclusions, and
  discovery losses, and never calls a model.
- The measurement records one result: a selected safe cadence, `no-safe-cadence`,
  or `insufficient-evidence`; only the first permits #173 to be authored.
- BACKLOG #299 and #173 state the measured result and the resulting #173 status.

## Deferred

BACKLOG #173 owns any cache or re-check implementation after this measurement
selects a safe cadence. A finding about a different audit surface or benchmark
is filed in BACKLOG.md rather than absorbed here.
