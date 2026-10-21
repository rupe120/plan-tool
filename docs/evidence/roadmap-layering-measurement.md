# Does the roadmap layering produce better-grounded plans? — the 2026-08-01 measurement

BACKLOG **#208** claims that plans derived through `roadmap`'s domain →
constraints chain are better grounded than plans written straight from a concept
brief. Arc position 01 shipped the chain's first two artifacts and nothing that
consumed them, so the claim had never been tested. This is the one test that has
been run, recorded here because it is cited in decisions and its raw artifacts
live in gitignored scratch.

**Result: all three plans reached the same architecture.** What the layering
produced instead was a **decision record** — rejected alternatives, provenance,
and a don't-re-open fence that the brief-only plans had none of.

**Read § "How to read this result" before citing it.** This measurement asked a
*replacement* question, and #208's Outcome has since been settled as
*collaborative*, which makes that the wrong test. The null was once read as the
premise failing and acted on; the reversal is settled and must not be re-opened
on these grounds.

---

## Design

Three `create` runs, same slice (blind-review integrity for `cfp-review`), same
empty git repo, so neither arm had code to ground in and the **seed was the only
variable**. `--iterate` at its default (ON), held constant. Criteria fixed in
writing before any run.

| Arm | Seed | |
|---|---|---|
| **Roadmap** | Derived through `01-domain.md` / `02-constraints.md` — settled decisions, rejected alternatives, quality-attribute dispositions, traceability ids | what arc position 03 would emit |
| **Control** | The concept brief only | states the same *requirements*; resolves no architecture |
| **Control, decontaminated** | Same, minus one leaked sentence | see Weaknesses |

The prediction, written before the runs: *if both plans land the same
architecture, the layering is not buying what #208 claims and positions 02–03
need re-justifying.*

## What came back

The result splits cleanly: **the architecture criteria tied, and every
record-keeping criterion went to the roadmap arm.**

| # | Pre-registered criterion | Roadmap | Controls |
|---|---|---|---|
| 1 | **Settled-decision transfer** — blindness by projection; conflict checked at assignment *and* at write; declared beats inferred | ✅ all four | ✅ all four |
| 2 | **Rejected alternatives survive** | ✅ | ❌ none |
| 3 | **Fence quality from dispositions** | ✅ cites `qa-performance` `not-load-bearing`, `qa-scalability` `traded-away`, and forbids optimizing the cost away | ❌ no disposition-grounded fence |
| 4 | **Criteria tied to checkable constraints** | ✅ | ❌ generic intent |
| 5 | **Provenance** | ✅ 19 named constraint/rule citations | ❌ 0 |
| 6 | **Decomposition sanity** (steps) | 11 | 12 / 11 |

Criterion 1 is the headline: a plan written from the brief alone reached **every
architecture decision** the roadmap seed spelled out, including the non-obvious
ones. The decontaminated control also *organized* the work slightly better — it
unified both blindness directions into one module where the roadmap arm split
them across two steps.

Criteria 2–5 are what the layering actually bought, and criterion 6 confirms it
did not buy them by merely producing a bigger plan.

### What the layering did buy

The roadmap arm records decisions as **settled**, each with its rejected
alternatives, a citable id, and a don't-re-open fence:

> **`decision-blind-by-projection`** … Rejected: field- or row-level access
> control on a shared model — every new query, export and report would then have
> to be checked against the policy … Also rejected: stripping identifying text
> from the proposal body — a guess about prose that fails silently.

> These decisions are settled in the `cfp-review` roadmap artifacts … and **must
> not be re-opened by this plan**; the ids above are the traceability chain back
> to them.

Both controls left the central decision formally **open in prose while their
steps silently committed to one answer** — control-clean states "the plan must
decide and record where the blindness guarantee lives" and then builds the
projection anyway. That is a plan contradicting itself, which an audit flags.

### What the layering cost

One result ran **against** the roadmap arm. Its rejected-alternative rationale is
**weaker** than what the control derived live.

The roadmap arm rejects access control in one frozen sentence — "every new query,
export and report would then have to be checked against the policy." The control
fetched the PostgreSQL reference docs and found **three documented RLS bypasses**
the guarantee must account for: superusers and `BYPASSRLS` roles; the table owner
unless `ALTER TABLE … FORCE ROW LEVEL SECURITY` is set; and referential-integrity
checks, which always bypass row security — the documented covert channel. It also
caught that a table-level grant is unaffected by a later column-level revoke.

**The roadmap's reasons were frozen at constraints-authoring time; `create`
grounds against live docs.** A settled decision is only as good as the reasoning
sealed into it.

## Weaknesses, stated before the runs

- **n=1 slice, n=1 project, one judge.** No error bar.
- **Control contamination.** The control was written after reading the artifacts.
  The likeliest direction of that bias is a control that is *better* than a real
  from-scratch seed — which makes a positive result for the roadmap arm more
  credible and **a null result less so**. The decontaminated arm removed one
  leaked sentence of rationale; it changed nothing.
- **Empty repo.** Neither arm got code grounding, suppressing a real strength of
  `create`. This isolates the seed but does not reproduce normal conditions.
- **Self-judged.** Fixing criteria in advance limits post-hoc rationalization; it
  does not eliminate it.

## How to read this result

**This is not evidence against the arc, and it must not be cited as such.**

The measurement asked a **replacement** question — does the arc beat an ad-hoc
brief? On 2026-08-02 the operator settled #208's Outcome as **collaborative**: the
verb proposes, a human reviews and gives feedback, it re-proposes. Under that
Outcome a proposal landing where a competent human's first draft lands is a
**good** proposal, so the replacement benchmark is the wrong test. The question
was **retired rather than answered**.

**The mid-session error worth not repeating.** The null was first read as the
premise failing and acted on: #208's Outcome was narrowed to "provenance and
finality" and the components artifact and framework lenses were cut. The operator
corrected the framing and **the cuts were reverted the same day**. Both artifacts
are restored; their value is as *review surfaces*, which a one-shot-quality test
cannot see.

The generalizable lesson: **check what a benchmark assumes about how the thing is
used before acting on its result.**

## What would actually test the arc

A collaborative measurement, not a one-shot quality comparison — whether feedback
on a proposal survives into the next proposal, and whether a reviewer reaches a
good artifact in fewer rounds. Arc position 02 built that channel and produced
the first end-to-end evidence: on the real exercise, id continuity held 12/12
entities, 13/13 rules and 12/12 decisions against an 85/30/25 regeneration
baseline, and a human reviewer accepted both responses.

That measurement ran on 2026-08-05 across two briefs. Three of the
decision-record rule's four branches are confirmed, revisions were shown not to
invent design rows nobody asked for, entity field-name sets held 11–12 of 12
under revision against 0 of 11 under regeneration, and the constraints stage's
retry budget was decided calibrated. Records in `docs/history/backlog-decisions.md`
(#215, #232) and BACKLOG **#208**. One branch remains open — whether a removal
that opens a question may mint a decision answering it — and it is a wording
question, not a measurement.

## Artifacts

All under `.tmp/` — **gitignored and transient**, which is why this document
exists.

| Path | |
|---|---|
| `roadmap-validation.criteria.md` | the six pre-registered criteria and weaknesses |
| `roadmap-validation.create-{roadmap,control,control-clean}.log` | the three runs |
| `roadmap-validation-repo/` | the empty repo: three plans, six seeds |

Durable record: BACKLOG **#208**'s Framing bullet. Cite that and this file, not
the transient handoff.
