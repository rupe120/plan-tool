# Premise ledger: make "this plan does not know enough yet" expressible, and let it hold `detail` back

## Outcome

A plan carries a `premises:` collection of factual claims its design rests on;
`create` and `detail` may mint an `open` row for a claim they cannot establish;
an `open` row naming steps in `blocks` raises one `medium` self-consistency
finding and makes `detail` skip exactly those steps until a reviewer answers or
accepts the risk.

## Overview

Today a plan whose premises are unknown at authoring time is authored anyway.
The unknown becomes conditional prose — two mechanisms specified, one to be
deleted later — and the audit loop then converges the branch structure instead
of questioning it. Nothing in the tool can say *I do not know this yet*, so the
only available move is to guess in both directions and write both down.

This seed adds the missing channel and one consumer for it. The channel is a
reflection of the roadmap verb's review collections (`ROADMAP_FORMAT.md` § The
review collections): a row that lives *in* the artifact so it diffs and travels,
one side owning each state move, and a row's presence changing what the *next*
run may do. The reflection is the point — roadmap's channel runs reviewer →
model and `roadmap.py:_invented_review_rows` rejects a row the predecessor did
not carry, because there the reviewer owns the channel. Here the model's one
move **is** minting, because a premise nobody knew to question is exactly the
one no reviewer opened a row for.

The tool never judges a premise. It asserts one binary fact — a row is `open` and
names steps — and puts the claim in front of a human. See § In scope for the
enumerated list of what may not be checked; the enumeration, not this paragraph,
is what holds the line.

## Problem statement

Measured 2026-08-05 in `example-app-amplify` (`assessment-service-dynamic-people-types`).
The effort: source an assessment wizard's option list from a third-party API
instead of a hardcoded array.

- **Step 1**, non-code: probe the vendor for a catalog endpoint whose existence
  was *inferred from the naming pattern* of two sibling endpoints.
- **Steps 2–6**: the implementation consuming whatever step 1 found — every one
  `depends_on` step 1, and every one authored **before** step 1 ran.

That is not one effort. It is a research task and an unwritten plan, stapled
together and audited as if it were a single design. What the ambiguity produced,
verbatim from the bundle: an identifier branch with three arms; `subtext` sourced
two different ways with both mechanisms specified; risks written per-arm ("on the
other arm this risk does not exist"); acceptance criteria split into
positive-finding and negative-finding columns because even *which file the step
writes* depended on the outcome. And a full last-known-good persistence layer —
its own store, IAM, and tests — designed to defend a failure mode that one HTTP
call later disproved. It was authored, audited, approved, and then removed.

Four `completeness-audit` rounds went **17 → 16 → 25 → 30** findings, correct
every round and unable to converge, because a contradiction between two
hypothetical arms is unfalsifiable: satisfying the finding means elaborating an
arm, and elaborating an arm adds surface for the next round. Round 1's HIGH
suggested widening the gate's stop condition — good advice *about* the
conditional, and it entrenched the conditional. No finding said the plan should
not have been written yet, because no lens asks that.

Measuring cost one throwaway script, three runs, **~10 minutes**. It deleted a
mapping table, a local copy table, a cache-key branch, the persistence layer, and
roughly half the conditional prose in the bundle.

**The plan volunteered the confession and nothing was listening.** Its body said
the endpoint's existence "is inference from the `/fields` + `/my/fieldMenu`
naming pattern, not a verified capability." A prose sweep for that sentence is
the wrong remedy — a healthy go/no-go gate and a design-determining one use
identical words. The remedy is to make it a **field** the author fills in while
the fix still costs ten minutes.

**Why a convention cannot substitute for a persisted collection**, measured on
`remove-vendor-scraper-poc` and recorded in `risk-profile-1-detection.md`: a
directive present only in the seed is dropped by `create` and invisible to
`detail`; and retro-fitting it into the plan body afterwards moved that audit
18 → 17 findings while pushing HIGH **up** 3 → 5, because the new findings were
contradictions against ceremony already written into the bundle. Premises must be
on the artifact and present **before `detail` runs**.

## Architecture

### The row

A `premises:` collection in plan frontmatter, shaped on roadmap's `FeedbackRow`:

```yaml
premises:
  - id: string        # required, non-empty. Its own namespace: nothing else resolves against it.
    claim: string     # required key. The factual claim the design rests on. Blank parses.
    blocks: [int]     # required key. Step ids unauthorable until this is settled.
                      # Present-and-empty parses — a plan-wide premise blocks nothing.
    state: open | answered | accepted-risk   # required. Closed vocabulary.
    evidence: string  # how the claim was established. Required and non-blank on
                      # `answered`; optional on the other two.
```

`evidence`-on-`answered` is the deliberate exception to blank-parses, exactly as
`proposed_response`-on-`awaiting-review` is in `ROADMAP_FORMAT.md`: `answered` is
*defined* by carrying the evidence. Absent or null collection parses as empty, and
the key is omitted when empty, so every existing plan round-trips unchanged.

### Who may move a row — the reflected rule

**The model mints, and makes no state move.** `create` and `detail` may add a row
in `state: open`. On a row the predecessor already carried, `id`, `claim`,
`blocks`, and `state` are immutable to the model. Every state move is the
reviewer's, made in their editor before the next run: `open → answered` with
evidence, or `open → accepted-risk`. Closing is deleting the row — there is no
`closed` member, because a closed premise is not state the artifact carries.

This is one rule with one owner per move, which is what makes roadmap's channel
hold. It also means a model can never unblock itself.

### Seed → plan mapping

A `## Premises` H2 in the seed maps to the frontmatter collection
deterministically, with no Claude call — the `## Outcome` → `intent` precedent at
`create.py:_intent_from_seed_outcome`. It carries that function's constraint:
read the **raw** seed, because `## Premises` is not a canonical body section and
the distill first-pass drops it.

This is not a second why-section (SEED_FORMAT.md, decided 2026-08-02, not
reopened). `## Outcome` says what the effort achieves; a premise says what must
be true for the effort to be authorable, and carries its own evidence field.
They cannot disagree, because they are not the same altitude or the same claim.

### The check

`check_premise_openness`, mirroring `check_intent_presence`
(`review.py:2473-2500`) in every respect: one single-sourced
`PREMISE_OPENNESS_SOURCE` token shared by the detector and its consumers,
registered beside `INTENT_PRESENCE_SOURCE` at `review.py:3620`, emitting
`medium`, and blocking completeness convergence through the existing
self-consistency path in `cli/completeness_phases.py`. It fires on exactly one
condition: `state == "open"` and `blocks` is non-empty. Exit codes are untouched
— a completed audit still exits 0.

### The one consumer

`detail` **skips** a step whose id appears in an open premise's `blocks`, printing
the premise id and claim and the remedy (answer the row, or set
`accepted-risk`). Skip, not fail; the rest of the bundle authors normally.

This consumer is what stops the ledger from being a comment field. A channel
whose rows change nothing is `check-saturation` — every part correct, no producer
delivering the value. One consumer is also the whole of it: see § Deferred.

### Relationship to the registered audit shape

`premise-conditioned-design` ships in `AUDIT_SHAPES` as `judgment_only` (landed
2026-08-05, ahead of this seed). It stays judgment-only. This seed adds no
detector for it, changes no classification, and touches
`is_advisory_emitter_eligible` not at all — the shape is how a *session* is told
to stop and re-ask; the ledger is how an *author* records what they do not know.

## In scope

`plan_tool/schema.py` and `plan_tool/parser.py` (the collection and its
validation), `plan_tool/review.py` (the detector and its source token),
`plan_tool/cli/completeness_phases.py` (convergence blocking, beside the existing
intent path), `plan_tool/create.py` (the seed map and minting), `plan_tool/detail.py`
(minting and the skip), `PLAN_FORMAT.md`, `SEED_FORMAT.md`, `DATA_CONTRACT.md`,
`tests/`.

### Scope contract

- **Binary observable, in one sentence:** a premise row whose `state` is `open`
  names at least one step id in `blocks`. Membership in a closed vocabulary and
  non-emptiness of a list; nothing else.
- **Allowed behavior changes:** the new frontmatter collection; one new `medium`
  finding source; `detail` skipping blocked steps; the seed `## Premises` map.
  Nothing else user-visible.
- **Allowed reorganization:** none.
- **Verification:** § Testing. Every assertion is over parsed structure or a
  finding's source token — none over prose content.
- **Stop / defer:** § Deferred, and anything the iteration loop surfaces outside
  this fence goes to `BACKLOG.md` / `BUG_BACKLOG.md`, never applied as plan
  expansion.

### Not allowed — enumerated, because stating the principle does not hold it

Per CLAUDE.md § "Validating a semantic property you cannot observe". Each of
these is a finding that is **invalid, not deferrable**:

- judging whether a `claim` is true, well-founded, material, or worth measuring;
- judging whether `evidence` supports its `claim`, or comparing `evidence`,
  `claim`, or a premise to any other prose in the plan, the detail bundle, or the
  code — an agreement check between two prose artifacts;
- detecting design branches, arms, conditional constructions, or per-arm risks
  and criteria anywhere in the plan or detail files. This is the withdrawn
  `collect_change_type_test_order_findings` shape: a matcher over prose that
  measures vocabulary at an ~85% false-positive base rate;
- inferring `blocks` from `depends_on`, the step graph, `change_type`, or step
  text. `blocks` is authored, never derived;
- any shape, length, count, or ratio cap on `claim`, `evidence`, or the
  collection;
- any exit-code flip, any refusal to advance a `run`, any `create` abort, any
  gate on `jira`;
- an `audit_shapes` detector, advisory emitter, or `checked` classification for
  `premise-conditioned-design`;
- the model closing a row, answering one, moving its state, or editing a carried
  row's `id`, `claim`, or `blocks`.

## Out of scope

- Every consumer but `detail`'s skip — `run`, `jira`, `reconcile-code`,
  `verify`, and `annotate` read the collection not at all. Adding a consumer is
  its own decision with its own evidence; "consumer X cannot see it" is out of
  scope by default.
- The stale-arm sweep after a premise is answered. The existing rule already
  covers it — CLAUDE.md § "Documentation is forward-looking" mandates the
  identifiers-plus-vocabulary sweep after any structural change. What is missing
  is a trigger, not a checker, and that one-line addition is § Deferred.
- The `convergence` trajectory signal. Filed in `BUG_BACKLOG.md` as a defect in
  the verdict, independent of whether this ships.
- Auto-proposing premises by classifying the seed, and any calibration corpus.
- Migrating existing plans.

## Risks

- **Ledger theater** — rows minted for everything until operators skim the
  channel, which is the failure mode the 2026-08-02 intent reversal named. Three
  mitigations, all structural: the check keys on `blocks`, so a premise blocking
  nothing never fires; the severity is `medium`; and the remedy is runnable in
  one edit, which is the condition CLAUDE.md's carve requires before a presence
  finding may block convergence at all.
- **Minting as a refusal channel** — a model minting rows rather than reading the
  code, when the unknown is only unread. Mitigations: minting never blocks the
  run that mints, so there is no local incentive; and `detail` already grounds
  against HEAD, so an unread-code premise is answerable in the same pass. Watch
  for this in the characterization corpus.
- **Blocking on an irreducible unknown** — a premise awaiting a third party or
  observable only in production has no ten-minute answer. `accepted-risk` is the
  designed exit, and it is a better artifact than conditional prose because it
  names the exposure. Surfacing a genuinely blocked plan is the goal state, not
  a failure of the check.
- **`blocks` drifting under a renumber** — step ids move under split, merge, and
  scope-out. Treat a `blocks` id that names no declared step as a validation
  error with the premise id in the message, and sweep `blocks` wherever the
  existing renumber paths already rewrite `depends_on`.
- **Order of landing** — premises are worthless after `detail` has written a
  conditional bundle (measured above, 18 → 17 findings with HIGH rising 3 → 5).
  The skip consumer must land with the field, not after it.

## Testing

- **Schema:** collection round-trips; absent and null parse as empty; the key is
  omitted when empty so existing plans are byte-identical; unknown `state`
  rejected naming the row id and the known members; `answered` with blank or
  absent `evidence` rejected; `blocks` naming an undeclared step rejected.
- **Detector, by mutation of each condition:** `open` + non-empty `blocks` → one
  `medium` on `PREMISE_OPENNESS_SOURCE`; `open` + empty `blocks` → none;
  `answered` → none; `accepted-risk` → none; empty collection → none. Assert the
  **source token and severity**, never rendered words.
- **Convergence:** an open blocking premise holds completeness convergence open
  and the exit code stays 0; answering it converges. Mirrors the intent-presence
  coverage.
- **Seed map:** `## Premises` in a raw seed lands in frontmatter; absent → empty;
  a fixture large enough to distill still maps, proving the raw-seed read.
- **Immutability:** a model-authored revision altering a carried row's `id`,
  `claim`, `blocks`, or `state` is rejected naming the field that changed; adding
  a new `open` row is accepted.
- **`detail` skip:** a step in an open premise's `blocks` is skipped with the
  premise id printed and the rest of the bundle authored; the same step authors
  once the row is `answered`; `accepted-risk` also authors.
- **Characterization:** the `assessment-service-dynamic-people-types` premise — *a
  catalog endpoint exists at the path inferred from `/fields` and
  `/my/fieldMenu`* — blocking steps 2–6 skips exactly those five and authors
  step 1.

## Acceptance criteria

- A plan carrying an `open` premise with a non-empty `blocks` raises exactly one
  `medium` finding and holds completeness convergence open, with the exit code
  unchanged.
- `detail` on that plan authors every unblocked step and skips every blocked one,
  printing the premise id, the claim, and both remedies.
- Answering the row unblocks those steps with no other change to the plan.
- A seed's `## Premises` reaches the generated plan's frontmatter without a
  Claude call, above and below the distill size gate.
- A plan with no premises is byte-identical through every read/write path, and
  raises no new finding.
- The `blocks` of every premise resolve to declared steps after a split, merge,
  or scope-out.
- `AUDIT_SHAPES` is unchanged by this work and `premise-conditioned-design`
  remains `judgment_only`.

## Deferred

- Consumers beyond `detail`'s skip, each on its own evidence.
- Adding "a premise moving to `answered`" to the list of structural changes that
  trigger the identifiers-plus-vocabulary sweep in CLAUDE.md — a documentation
  edit, not a checker.
- The `convergence` churn-without-recurrence signal (`BUG_BACKLOG.md`).
- Proposing premises automatically from seed classification.
- A `scope-out --at-premise` carve, once there is evidence that carving at an
  unanswered premise is common enough to need its own entry point; an ordinary
  `scope-out` already does it.

## References

- `ROADMAP_FORMAT.md` — reviewer-owned feedback-row lifecycle that informs the
  premise-row ownership rule.
- `plan_tool/review.py` — `check_intent_presence` and finding-source precedent
  mirrored by the premise-openness check.
- `DATA_CONTRACT.md` — persisted plan-frontmatter contract documentation this
  collection extends.
