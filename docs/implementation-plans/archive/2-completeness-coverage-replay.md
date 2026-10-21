---
title: Withdrawn completeness coverage replay
intent: 'Withdrawn 2026-08-20 (user-confirmed). This preserved plan records why a
  bounded replay measurement is not justified: proving the model-visible input
  boundary requires a hermetic capture runner. Do not execute or resume it; keep
  BACKLOG #173 deferred unless measured operational audit cost warrants a new,
  bounded decision.'
status: planning
priority: medium
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: plan-seeds/archive/completeness-coverage-replay.replaced.md
steps:
- id: 1
  title: Build a versioned replay corpus from existing audit snapshots and predeclare
    schedules
  intent: Makes cases admissible only when a clean disposable worktree captures every
    model-visible input, the whole fresh-audit observation, fresh labels, and the
    evidence threshold.
  files:
  - plan_tool/review.py
  - plan_tool/review_persistence.py
  - plan_tool/fingerprint.py
  - plan_tool/shell.py
  - plan_tool/backend.py
  - tests/test_shell.py
  - tests/test_backend.py
  creates:
  - COMPLETENESS_COVERAGE_REPLAY_FORMAT.md
  - benchmarks/corpus/completeness-coverage/manifest.json
  - plan_tool/completeness_coverage_corpus.py
  - tests/test_completeness_coverage_corpus.py
  allowed_mentions:
  - benchmarks/corpus/completeness-coverage/cases.json
  - benchmarks/corpus/completeness-coverage/fixtures.bundle
  - plan_tool/completeness_coverage_replay.py
  - tests/test_completeness_coverage_replay.py
  complexity: high
  change_type: feature
  detail: docs/implementation-plans/archive/plan-details/completeness-coverage-replay/01-build-versioned-replay-corpus-existing.md
  status: pending
  scope: wont_do
  status_note: 'Withdrawn 2026-08-20 (user-confirmed): do not execute this approach;
    a future measurement requires a new, bounded design after measured audit cost.'
- id: 2
  title: Replay schedules read-only and report every exclusion and missed label
  intent: Applies one explicit fresh-versus-reuse observation relation and a fail-closed
    result table to select at most one pre-ranked cadence.
  files:
  - TESTING.md
  - docs/ARCHITECTURE.md
  creates:
  - plan_tool/completeness_coverage_replay.py
  - tests/test_completeness_coverage_replay.py
  - tests/fixtures/completeness_coverage_replay/labelled-cases.json
  allowed_mentions:
  - plan_tool/completeness_coverage_corpus.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: Supplies validated cases, explicit finding labels, and the predeclared control
      and candidate schedules.
  detail: docs/implementation-plans/archive/plan-details/completeness-coverage-replay/02-replay-schedules-read-only-report-every.md
  scope: wont_do
  status_note: 'Withdrawn 2026-08-20 (user-confirmed): do not execute this approach;
    a future measurement requires a new, bounded design after measured audit cost.'
- id: 3
  title: Capture and label fresh cases in disposable worktrees, preserve source histories,
    and leave no scratch reports
  intent: Produces required evidence for every reuse, full-discovery, and terminal
    confirmation branch without treating incomplete legacy sidecars as labels.
  creates:
  - benchmarks/corpus/completeness-coverage/cases.json
  - benchmarks/corpus/completeness-coverage/fixtures.bundle
  allowed_mentions:
  - benchmarks/corpus/completeness-coverage/manifest.json
  complexity: high
  change_type: non-code
  depends_on:
  - 1
  depends_on_notes:
    1: Supplies the capture, identity, eligibility, and serialization contract used
      for every case.
  detail: docs/implementation-plans/archive/plan-details/completeness-coverage-replay/03-capture-label-fresh-cases-disposable.md
  scope: wont_do
  status_note: 'Withdrawn 2026-08-20 (user-confirmed): do not execute this approach;
    a future measurement requires a new, bounded design after measured audit cost.'
- id: 4
  title: 'Publish the replay result and update #299 and #173 without changing audit
    behavior'
  intent: 'Turns the captured evidence into the explicit decision gate that either
    permits #173 to be scoped or keeps it deferred.'
  files:
  - BACKLOG.md
  creates:
  - docs/COMPLETENESS_COVERAGE_REPLAY_RESULT.json
  - docs/COMPLETENESS_COVERAGE_REPLAY_REPORT.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 2
  - 3
  depends_on_notes:
    2: Supplies the deterministic evaluator and report renderer.
    3: Supplies the eligible and excluded real cases evaluated by every predeclared
      schedule.
  detail: docs/implementation-plans/archive/plan-details/completeness-coverage-replay/04-publish-replay-result-update-299-173.md
  scope: wont_do
  status_note: 'Withdrawn 2026-08-20 (user-confirmed): do not execute this approach;
    a future measurement requires a new, bounded design after measured audit cost.'
---
# Withdrawn Completeness Coverage Replay

> **Withdrawn 2026-08-20 (user-confirmed).** This bundle remains as provenance,
> not as an implementation instruction. The detail-grounded audit established
> that the capture needs a hermetic model-visible input boundary, rather than a
> bounded replay corpus. Its proof cost exceeds the current need. Do not execute
> or resume this plan; keep #173 deferred and use fresh completeness audits.
> Reconsider only after measured operational audit cost supports a new, bounded
> decision. This is a proof-burden inversion: the proof system would cost more
> than the decision it supports.

## Overview

BACKLOG #173 defers a fingerprint-gated audit cache and re-check lane until
evidence selects their full-discovery cadence. Existing report history is not
automatically admissible: a saved review may omit the plan/detail/code identity
needed to tell whether a reuse candidate observed the same inputs. This effort
creates the measurement rather than treating incomplete history as proof.

## Problem statement

A reuse schedule can reduce model calls only if it never hides a finding a
fresh full-discovery audit would surface. The binary observable is whether each
eligible captured case in the complete corpus has its labelled fresh finding
set represented by the simulated schedule. Missing or ambiguous identity is
not absence of a finding; it makes the case ineligible.

## Architecture

The corpus admits a case only from a clean, disposable worktree whose complete
model-visible repository state is committed and pinned by commit and tree
identity. It records an ordered fresh-audit attempt series: each attempt's
rendered-prompt digest, carried-finding digest, retry suffix state, outcome,
and audit configuration, as well as the plan, selected detail, source seed,
project context, stage/grade, and repository tree shared by the series. No
untracked repository file is allowed. A scoped code fingerprint is supporting
provenance, not a substitute for the complete worktree identity.

The observation unit is one complete fresh audit run over the whole prompt,
not a plan step. Its pre-run reuse key contains every model-visible initial
prompt input, complete repository state, and audit configuration known before
discovery begins. The ordered attempt trace records the later carried-finding
and retry inputs that arise during discovery; those outputs cannot become a
separate scan or a pre-run cache key. A step tag is finding attribution only
and cannot independently make a slot reusable. A future step-scoped cache
needs separately captured independent scan evidence. A fresh label set is
authoritative only when every attempted prompt is recorded, every attempt
conforms, the series has no failed, malformed, or skipped attempt, and its
coverage records `confirmed-dry` or `confirmed-low-yield` rather than merely
being not budget-limited. All other captures remain explicit exclusions or
unresolved comparisons, never empty authoritative label sets.

Each corpus trajectory is ordered. At each snapshot, a schedule observes the
current fresh labels when it chooses full discovery and otherwise carries the
entire most recently observed label set from an unchanged, reuse-eligible whole
fresh-audit observation with an eligible predecessor. Its observed union is compared
with that snapshot's authoritative fresh label set: an absent fresh label is a
discovery loss. A label without a declared observation unit or a reuse attempt
without an eligible predecessor is unresolved, never a carried label or a miss
by inference. The required terminal confirmation is always full discovery.

The manifest defines the observation policy once. Snapshot zero is always full
discovery. At each later snapshot, terminal confirmation wins; otherwise a
changed pre-run reuse key forces full discovery, then the candidate's positive
interval forces full discovery when the number of snapshots since its most
recent full discovery reaches the interval, and only the remaining unchanged
snapshots reuse. Captures record only the candidate-independent facts needed to
derive that decision — ordered position, terminal flag, and pre-run reuse key
— never one stored policy outcome. The replay derives a result separately for
every candidate. A missing required fresh observation, ineligible predecessor,
missing candidate decision, or contradictory source fact is unresolved and
produces `insufficient-evidence`, not an alternate cadence interpretation.

The manifest also owns a versioned label registry before capture. A recorded
label is valid only when its registry id is paired with the exact fresh audit
output that supports it: attempt index, raw response bytes and digest, and the
parsed recommendation reference in that response. A reviewed explicit mapping
to the same declared label id is the only cross-snapshot identity; the replay
never matches recommendation ids, anchors, or prose. An unmapped or ambiguous
fresh finding remains unresolved and is published as such.

The capture hook exposes the audit only to a sealed source-root inventory that
matches the committed tree. A capture-only runner calls the same
`audit_plan_until_stable` discovery engine without the completeness CLI
wrapper, so it does not save reports or emit audit-coverage telemetry. It uses
a proven read-only backend profile rooted at that inventory, suppresses both
review and shell prompt-budget telemetry, and puts its own runtime state
outside the read surface. It checks the sealed inventory before and after every
backend attempt; a mutation, an audit-runtime writer, a fence failure, or an
ignored or untracked model-readable path makes the case ineligible. Git
administration and temporary tool paths must sit outside that surface. For every
eligible snapshot, the collector records its commit and tree in
`fixtures.bundle`, and the verifier must resolve both objects from that
committed bundle after the disposable worktree is removed.

The attempt trace starts at `claude_invoke`'s recovery boundary, not only at
the review wrapper. It records every backend call, retry, raw response, and
outcome, and associates those backend attempts with the rendered review prompt
attempt that initiated them. A series with an unrecorded backend retry is
excluded; normal audits keep their existing recovery and telemetry behavior.

Candidates are declared before capture. Each selectable candidate has a
full-discovery interval of at least two, its mandatory final full-discovery
confirmation, and a unique priority rank; the always-fresh control is never
selected. The manifest requires at least three independent trajectories
(distinct committed fixture histories, not copied reports) and resolved
exercise of reuse, changed-input, full-discovery, and final-confirmation
branches as a corpus diversity floor. That floor never creates a selection
subset: every candidate is evaluated against every eligible ordered case in the
complete corpus. The manifest also requires a witness for each candidate’s own
interval: an unchanged non-terminal reuse snapshot and a later unchanged
non-terminal snapshot at which that exact interval makes periodic full discovery
due. A shared trajectory is a witness only when it actually reaches that
candidate’s interval. A candidate is selectable only when its own witness and
all corpus comparisons resolve with no discovery loss. An eligible case missing
from a candidate's evaluation, or any unresolved eligible comparison, returns
`insufficient-evidence`; `no-safe-cadence` is possible only when every candidate
was evaluated over the complete eligible corpus and each loses a label. The
replay is deterministic and makes no model call.

`plan_tool.review_persistence:SavedReview` can persist plan/detail/code
fingerprints for current captures, while
`plan_tool.review_persistence:AuditInputSnapshot` captures the plan/detail
inputs and `plan_tool.fingerprint:compute_code_fingerprint` captures the
watched code map. Legacy reports that lack any required identity remain
ineligible; the corpus must not reconstruct them from filenames or prose.

## References

- [Python 3.13 json — JSON Encoder and Decoder](https://docs.python.org/3.13/library/json.html) — Documents deterministic JSON serialization options needed for stable corpus and replay reports.
- [Python 3.13 hashlib — Secure Hashes and Message Digests](https://docs.python.org/3.13/library/hashlib.html) — Defines SHA-256 hashing APIs for reproducible plan, detail, code, and configuration identities.
- [RFC 8785 — JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785.html) — Specifies invariant JSON encoding rules useful when replay inputs or results must hash identically.
- [JSON Schema Draft 2020-12 Validation](https://json-schema.org/draft/2020-12/json-schema-validation) — Defines structural validation keywords for enforcing versioned corpus fields and complete identity records.
- [pytest — Parametrizing Fixtures and Test Functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Shows how to exercise every captured case and candidate cadence through repeatable test matrices.
- [pytest — Monkeypatching Modules and Environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Explains dependency patching needed to prove deterministic replay never invokes a model backend.

## Steps

See the `steps:` block in the frontmatter.

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
rejected, a missing worktree/prompt/scan identity is excluded rather than
counted as covered, an unconfirmed fresh audit cannot label a case, and an
eligible case omitted from any candidate evaluation returns
`insufficient-evidence`. Fixtures exercise discovery, reuse, changed input,
each candidate’s interval-due periodic full discovery, and terminal
confirmation, and prove the predeclared rank selects exactly one loss-free
candidate over the complete eligible corpus. Rerunning the same corpus yields
the same report without a model call. The bare-plan audit preserves this
evidence boundary; the detail-grounded audit may require the corpus, labels,
and report to cover every declared candidate schedule before implementation
starts.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — tests covering the behavior this step changes; green before completion.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.
- step 3 (non-code) — verification appropriate to the artifacts rather than unit tests.
- step 4 (non-code) — verification appropriate to the artifacts rather than unit tests.

## Acceptance criteria

- A committed corpus identifies every eligible case's complete worktree,
  whole-observation-unit and ordered-attempt identities, authoritative fresh
  labels, candidate-independent policy facts, and complete evidence-universe
  membership; incomplete, failed, malformed,
  skipped, budget-limited, or unconfirmed series remain excluded or unresolved.
- The manifest fixes the initial, changed-input, periodic, and terminal
  observation policy; captures retain only candidate-independent policy facts
  and the replay derives one result per candidate.
- Every label has a predeclared registry id and retained raw fresh-output
  evidence; an unmapped or ambiguous finding is unresolved rather than matched
  by identifier, anchor, or prose.
- `fixtures.bundle` lets a future verifier resolve each eligible captured
  commit and tree after scratch worktrees are removed, and no ignored or
  untracked model-readable path enters an eligible capture.
- Capture mode calls the full discovery engine through a read-only backend
  profile, records every backend recovery attempt, and suppresses all audit
  runtime writers under the sealed source root; a mutation, unrecorded retry,
  or fence failure excludes the case without changing normal audit recovery or
  telemetry.
- Every selectable candidate declares a full-discovery interval of at least
  two, terminal confirmation, unique rank, and its own reuse plus non-terminal
  interval-due witness before capture; the always-fresh control is reported but
  never selected.
- The deterministic replay reports all candidate schedules, their derived
  policy decisions and interval witnesses, exclusions, unresolved comparisons,
  discovery losses, and never calls a model.
- The measurement returns `insufficient-evidence` unless every eligible case
  is evaluated and all its comparisons resolve for every candidate; otherwise
  it selects the first ranked loss-free candidate or returns
  `no-safe-cadence`. Only a selected result permits #173 to be authored.
- BACKLOG #299 and #173 state the measured result and the resulting #173 status.

## Deferred

BACKLOG #173 owns any cache or re-check implementation after this measurement
selects a safe cadence. A finding about a different audit surface or benchmark
is filed in BACKLOG.md rather than absorbed here.
