> **Replaced**: this file has been superseded by `docs/implementation-plans/2-research-chosen-technology.md`.
> Preserved here for history; do not edit.

# Research the technology a plan actually chose, and refuse to guess

Seed for BACKLOG **#244**. Depends on the shipped `roadmap-hosting-and-stores`
schema, which records the technology choices this reads; author against its
archived detail bundle. The resulting plan updates `BACKLOG.md` (#244) in its final
docs step, and closes it only on full shipment.

## Outcome

`create`'s web research is grounded in the technologies the plan actually
uses, and `create` refuses to proceed when it cannot ground one and no
operator description exists.

## Overview

Three changes to `create`'s existing research phase:

- **Feed it the real inputs.** `_build_research_context` also reads the
  technology strings recorded on the roadmap's `hosting:` and `stores:` rows,
  not just the plan title and step titles.
- **Notice when research finds nothing** for a named technology, per
  technology rather than for the batch.
- **Refuse, naming what failed** — the technology and the field that named
  it — unless that row carries an operator `description`. This seed's plan
owns that `description` field; the shipped hosting/store schema deliberately does not.

## Problem statement

`_build_research_context` (`plan_tool/create.py:2434`) builds the research
description from the plan **title plus step titles**, and `create.py:6690`
uses it whenever there is no `--from` text. No technology choice reaches it.

**Measured, 2026-08-07.** `world-foundation`'s `References` cited `sqlite3`
and PEP 249 as "useful when defining the single world-scoped
repository/session boundary that mediates all reads and writes" — while all
six of its code steps keep every store an in-process stand-in and none
imports `sqlite3`. The research phase had nothing to ground on, so it
produced plausible documentation for a persistence layer the plan does not
build. The detail-grounded audit caught it as `persistence-references`
(MEDIUM); a reader would not have, because `References` is trusted precisely
*because* it looks researched.

**The contrast is the same machinery with better inputs, one run apart.** The
`roadmap-hosting-and-stores` seed named AWS explicitly, and that run's
research returned the Lambda execution-environment lifecycle (which became
the factual basis for a gate rather than an assertion), the AWS
Well-Architected SaaS Lens tenancy models, a multi-tenant storage-partitioning
whitepaper, Azure's independent tenancy taxonomy as a neutrality check, and
12-Factor's stateless-process statement. Nothing about the phase changed —
only what it was told to research.

**Why vendor services are the worst case.** They are fast-moving, frequently
renamed, and full of near-homonyms — Aurora Serverless v1 versus v2, DSQL,
Lambda SnapStart — where a model's confident wrong answer is indistinguishable
from a right one, and where the wrongness surfaces at implementation time
rather than review time.

## Architecture

**The refusal is the feature; the research quality is not checkable and is
not checked.** The gate keys on one binary fact per named technology: the
research step returned at least one source, or a non-empty operator
`description` is present. Nothing asserts the sources are good, current,
relevant, or actually about the technology named. That boundary is the whole
reason this can ship as a gate at all — see CLAUDE.md § "Validating a semantic
property you cannot observe", whose rule is to assert a binary fact about
state, deliver the rest, and enumerate what may not be checked.

**A hard stop, decided 2026-08-07 — do not soften to a warning.** Research
returning nothing usable blocks, names the technology and the field that named
it, and tells the operator what to add. Warn-and-continue was weighed and
rejected: it re-opens the exact silent-invention path this closes, and an
advisory on a channel operators already skim is not a fence. The refusal must
behave identically on non-interactive stdin — a Claude session auto-driving
gets the same error, never a prompt it cannot answer.

**A technology with no public documentation is the case the description
exists for, not an edge case to engineer around.** Something brand-new,
internal, or proprietary legitimately has none; that is precisely when writing
down what it is and how to use it properly is worth the operator's time. The
plan's job is to make supplying it cheap and to not discard work already done
in the same run — not to widen the gate.

**Scope of the read.** Only technologies named in a **recorded field** are
researched and gated. A technology mentioned only in prose is out — prose
mining is unbounded and would turn every incidental noun into a blocking
question.

## Scope of work

- `_build_research_context` and its call sites in `plan_tool/create.py`.
- Per-technology empty-result detection in the research phase, and the
  refusal path plus its message and non-interactive behavior.
- The `description` field on the existing `hosting:` and store rows —
  `plan_tool/roadmap_artifacts.py`, and `ROADMAP_FORMAT.md`'s schemas.
- `tests/test_create.py`, plus the roadmap artifact and format tests the new
  field touches.

## The binary observable

For each technology named in a recorded field, either the research step
returned at least one source, or a non-empty operator `description` is present
on that row. Presence, per named technology — nothing else.

## Not allowed — enumerated, not implied

No gate, finding, or prompt directive in this effort may assert any of these.
A proposal for one is invalid, not deferrable:

- whether a `description` is **accurate, sufficient, current, or
  well-written**, and any length, shape, or format cap on it;
- whether the fetched documentation **is actually about** the technology
  named, or matches its version;
- any **scoring, ranking, freshness, or authority judgment** on sources, and
  any minimum source count above one;
- any quality judgment on the resulting `References` entries;
- any gate on technologies **not** named in a recorded field, including ones
  appearing only in prose, a step title, or a detail file;
- **re-researching on every run** — the existing checkpoint/resume path stands;
- a pinned doc-URL registry, a vendor catalogue, or offline doc bundling;
- extending any of this to `detail`, `run`, `jira`, or `reconcile-*`;
- changing what `References` renders as, or its position in the body;
- any new exit-code convention beyond the one refusal, which is a
  failure-to-complete and exits non-zero like every other.

## Out of scope

- The existing hosting/store blocks, vocabularies, and gates — this consumes
  them and must not redesign them. A defect found in them is filed as new work,
  not fixed here.
- Threading research into `detail`, `run`, or `jira`.
- Researching entity fields, patterns, or constraints — technology only.
- Any `--framework` lens work (#208 position 05). A lens supplies vocabulary;
  this supplies documentation, and the two must not be merged.
- Offline or air-gapped operation.

## Allowed behavior changes

`create` gains one refusal path and reads the existing hosting/store rows when present. A plan
naming no technology in a recorded field behaves exactly as it does today,
byte for byte.

## Allowed reorganization

None.

## Risks

- **A new way for `create` to fail, late in a long run.** The refusal lands
  after step proposal, so it must not discard that work — an operator who adds
  a description should not pay for a full re-proposal. If the plan cannot make
  that cheap, say so rather than shipping a re-run loop.
- **Ceremony, and the tell to watch for.** If operators routinely paste a
  one-line description to clear the gate without reading anything, the gate is
  theatre. Measure that before tuning it.
- **Detection quality is the likeliest defect.** A search that misses docs
  which exist produces a refusal the operator cannot honestly satisfy. See
  Stop/defer.

## Testing

Hermetic, with a stubbed research invoker — never the real network. What
would prove the Outcome: a named technology whose research returns sources
proceeds; the same one returning nothing and carrying no description refuses,
naming both the technology and its field; the same one with a description
present proceeds; a plan naming no recorded technology is unchanged from
today; and the refusal fires identically on non-interactive stdin.

Assert by mutation (CLAUDE.md § Tests). Assert the carve-out explicitly: a
description whose content is obviously useless still passes, because quality
is deliberately not checked — that test is what stops a later reader from
"improving" the gate into a judgment.

## Acceptance criteria

- Research context includes every technology string recorded on the roadmap's
  `hosting:` and store rows, demonstrated by a test reading the rendered
  prompt.
- An empty research result for a named technology, with no `description`,
  refuses; the message names the technology, the field that named it, and what
  to add.
- The same case with a non-empty `description` proceeds.
- The refusal is identical on non-interactive stdin — no prompt, no skip.
- A plan with no recorded technologies produces byte-identical output to
  today.
- A useless-but-present `description` passes, asserted directly.
- `ROADMAP_FORMAT.md` documents the `description` field on both row kinds.
- `BACKLOG.md` #244 is updated when the work ships.

## Deferred

- Research for `detail`, `run`, and `jira`.
- Any re-research or staleness policy for a cached result.
- Researching non-technology rows.
