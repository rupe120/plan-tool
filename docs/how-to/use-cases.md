# When to use plan-tool

This doc answers three questions: **is your work a good fit**, **which use case
are you in**, and **which commands to reach for**. It is situation-first — the
opposite end of the other docs:

- [`MISSION.md`](../../MISSION.md) — *why* the tool is built the way it is (principles).
- [`CAPABILITIES.md`](../../CAPABILITIES.md) — *what* surfaces exist and which principle each serves.
- [`../reference/commands.md`](../reference/commands.md) and [`common-workflows.md`](common-workflows.md) — *how* commands and flags work. The [`README.md`](../../README.md) is the front door that links them.
- This doc — *when* to use it and *which path* to take.

## What it's for, in one line

Use plan-tool when you have real engineering work that's big enough to need a
plan, and you want that plan to stay **honest about the code** instead of
drifting into a wish-list. It turns a rough idea into an ordered, scoped plan,
checks the plan against the repo as it is right now, and then either runs the
plan locally or hands it off as Jira stories.

The problem it solves is **trust**, not text. An LLM will happily write a
confident plan that cites files that don't exist and skips the hard step. This
tool wraps that generation in deterministic checks so the output is grounded,
scoped, and verifiable.

## Is your work a good fit?

| Good fit | Poor fit |
| --- | --- |
| A feature or change that spans **several files or steps** and benefits from being ordered. | A one-line fix or a single obvious edit — just make the change. |
| Work you want a **second engineer (or a future you) to pick up** from a written spec. | Throwaway scripts and spikes you'll delete tomorrow. |
| Work grounded in a **real repo** the tool can read and check against. | Pure research or design with no code to ground against (use a research tool). |
| A plan you'll **keep around** while the code moves underneath it. | A decision you'll act on once and never revisit. |
| Work you want to **hand off as Jira stories** with estimates and dependencies. | Ad-hoc tasks that don't need tracking. |
| A draft (yours or an AI's) you want **pinned to reality** before trusting it. | A plan you've already verified by hand and just want to execute. |

Rule of thumb: if the cost of a wrong or stale plan is real — wasted
implementation, a misled teammate, a missed edge case — the tool earns its
overhead. If the change is small enough to just do, do it.

## Use-case catalog

Each entry is a situation, the path to take, and what you get out of it. Spine
commands support the assistant requests below — see the linked guides for every flag.

Ask the assistant to prepare inputs; you do not need a prewritten seed. Follow
[the planning walkthrough](../demos/planning-demo.md): review the linked seed and
scope summary before plan creation, the plan and bare audit before details, and
the details and grounded audit before a separate execution or local-export request.
At each boundary the assistant summarizes changes, asks for corrections or
continuation and waits for your response unless explicit prior delegation covers
it. Status inspection alone authorizes no implementation. For resumption, inspect
the original invocation and reports first; choose the next incomplete stage within
the requested scope only after confirmed command exit, using its recorded outcome.
See [monitoring and recovery](../../integrations/shared/DIRECTIVES.md#monitor-command-liveness-and-recover-safely).

### 1. Turn a rough idea into a buildable plan

> Inspect this repository and draft a grounded seed for [feature] with a scope fence and references; link it for review before creating the plan.

You have a feature in your head or a sentence in a ticket, and you want an
ordered plan a developer can build from.

```bash
plan-tool create my-feature --from-existing plan-seeds/my-feature.md --iterate
plan-tool completeness-audit my-feature --iterate --commit  # bare audit, then review
plan-tool detail my-feature --commit                       # after plan review
plan-tool completeness-audit my-feature --iterate --commit  # grounded audit, then review
```

`create` proposes the steps (checked against files that actually exist),
`detail` writes per-step implementation notes, and the audit confirms the plan
covers its own concepts. You get a plan whose file paths and steps match the
repo, not the prose. See [README → create](common-workflows.md#1-create--author-a-new-plan).

If the idea turns out to be project-sized rather than one feature — you can't
say what the domain is or what it trades on, let alone what the steps are —
start at [11. Ground a project-sized concept before you write a seed](#11-ground-a-project-sized-concept-before-you-write-a-seed)
and come back here with a seed.

### 2. Bring an external or AI-written draft under control

> Assess this draft against current code and show the grounded input and changes for review before plan creation.

Someone (or some model) handed you a draft plan. It reads well, but you don't
trust that it fits the code.

```bash
plan-tool create my-feature --from-existing path/to/draft.md
plan-tool reconcile-plan my-feature     # pin every step to the current code
```

`create --from-existing` reorganizes the draft into the canonical shape (and
will tell you if it's really several plans in a trench coat), then
`reconcile-plan` checks each step against the live tree and edits the plan to
match. You get a draft that's been ground against reality instead of taken on
faith. See [README → Decision flow](../../README.md#decision-flow).

### 3. Execute a plan locally, one step at a time

> Execute this reviewed plan through the plan-tool skill, then reconcile code against the plan and review changes to convergence; report results and unresolved decisions.

You have a vetted plan and want to build it on your own machine without losing
the thread between steps.

```bash
plan-tool status my-feature        # what's the current step?
plan-tool run my-feature --commit       # build the current step
plan-tool run my-feature --all --commit # build every runnable step in order
```

Each step runs in a fresh Claude subprocess with gates around it; plan state
only advances on success, and an interrupted run resumes instead of restarting.
You get step-by-step execution that survives a crash or a Ctrl-C. See
[README → run](common-workflows.md#4-run--execute-the-plan) and
[Resuming after a failure](../OPERATIONS.md#resuming-after-a-failure).

**After the plan completes, reconcile code with the plan and review it.**

```bash
plan-tool reconcile-code my-feature --all  # complete sweep, including done code steps
```

Save every report and judge findings against code and tests. `--dry-run` renders
prompts only; it supplies no drift verdict. Follow the existing
[post-run reconciliation and code-review contract](../../integrations/shared/DIRECTIVES.md#after-run-finishes-a-plan)
for convergence and stopping. Code review belongs to the driving session;
post-run completeness auditing is outside this tail.

### 4. Hand the work off as Jira stories

> Export this reviewed bundle as local Jira stories and their paired developer handoff. Link both, summarize changes and validation, and leave tracker publication for a separate request.

Your team works in Jira, and you want the plan exported as right-sized stories
with estimates and dependencies.

```bash
plan-tool jira my-feature --max-hours 8
# in CI, after stories merge and steps are flipped to done:
plan-tool verify-all --rollup my-feature
```

`jira` exports the steps as stories; as they merge, you flip each step's
`status:` to `done`, and `verify-all` in CI catches drift between the plan and
the merged code (non-zero exit on a real mismatch). You get a clean handoff plus
a CI gate. See [README → jira](../reference/commands.md#cli-usage) and
[verify-all](common-workflows.md#5-verify-all--ci-gate-after-the-jira-branch-conditional).

### 5. Keep a long-lived plan honest as the code moves

> Inspect this unexecuted plan and current code, then refresh its grounding and show proposed changes for review; do not implement it.

A plan you wrote weeks ago is still open, but the codebase has changed under it.

```bash
plan-tool reconcile-plan my-feature --refresh   # cheap: skips Claude on no drift
plan-tool reconcile-plan my-feature             # full plan-vs-code pass
```

`--refresh` compares a tracked fingerprint of the code against now and only
spends a Claude call when something actually drifted. You get a plan that
re-fits the repo instead of one that quietly went stale. See
[README → Audit a plan's quality](common-workflows.md#3-audit-a-plans-quality).

### 6. Start the next iteration from what's already built

> Assess this old plan against current code and prepare a forward seed for review without changing the source or executing new work.

An old plan is partly built, and you want to start fresh from where the code
actually is — not re-run the stale plan.

```bash
plan-tool annotate path/to/old-plan.md          # judge it against current code
plan-tool create next-iteration --from-existing <stem>.seed.md
```

`annotate` reads the old plan, sees what's been built, and emits a seed for the
next `create` — without touching the original. You get a clean next iteration
grounded in the current state, not a patched-over old one. See
[README → annotate / Decision flow](../../README.md#decision-flow).

### 7. Drive a plan to "actually correct," not just "generated"

> Use the plan-tool skill to prepare this reviewed seed through both audit gates, bringing material scope and design decisions back to me; stop before execution or export.

You want the plan tightened until it stops surfacing problems, not just written
once.

```bash
plan-tool create my-feature --from-existing seed.md --iterate
plan-tool completeness-audit my-feature --iterate --commit  # bare gate
plan-tool detail my-feature --commit                       # after review
plan-tool completeness-audit my-feature --iterate --commit  # detail-grounded gate
```

Use judged corrections between audits and report coverage, qualification and
convergence under the [audit procedure](pipeline/audit.md). Detail authoring is
one-shot by default; do not routinely opt into `detail --iterate`. A recurring
finding calls for investigation of its provenance before structural changes.
Operator diagnostics remain available:

```bash
plan-tool convergence my-feature     # loop health and advisories
plan-tool split-criteria my-feature  # inspect the decomposition rationale
```

Use `scope-out` only after reviewing whether a separate plan is warranted.

See [README → Iterating to convergence](../ITERATION.md)
and the [Runbook](../../RUNBOOK.md).

### 8. Review whether telemetry signals need tuning

You want to see how heuristic decisions behave across plans and over time before
deciding whether a signal is over-sensitive, under-used, frequently reverted,
or poorly correlated with later outcomes.

```bash
plan-tool telemetry
plan-tool telemetry --json   # machine-readable output for scripts and CI
```

The report groups each signal by `(kind, decision)`, so unrelated decisions
within a family such as `granularity` remain separate. It counts the four
operator-facing outcomes—`acted-on`, `no-op`, `reverted`, and `still-open`—and
shows correlation coverage alongside advisory tuning suggestions. Legacy and
ownerless events still contribute to counts even when they lack the keys needed
to connect them to a later outcome; low coverage therefore does not by itself
mean a heuristic is poor.

This command is read-only: it never changes a threshold, plan, or configuration.
Use the default report for review and `--json` when another tool needs the same
analysis. See the generated [`telemetry` command reference](../cli/telemetry.md)
for the complete command contract and flags.

### 9. Run the whole pipeline in one command for a small change

**Deprecated, going away (BACKLOG #367).** `direct-jira` and `direct-run`
exist only to chain `completeness-apply`'s gap-by-gap apply, which is
retiring: reviewing the whole saved report at once beats walking it one
finding at a time, and the slow pace obscures whether the plan is actually
converging. String `create → detail → …` together by hand instead, hand-
applying `completeness-audit`'s conceptual findings between stages.

You have a small change — a handful of steps, one or two Jira stories — and
stringing `create → detail → … → jira`/`run` together by hand is more ceremony
than the work deserves.

```bash
plan-tool direct-jira my-small-change --from-existing seed.md   # → Jira-sized stories
plan-tool direct-run my-small-change --from-existing seed.md    # → committed + reconciled code
```

`direct-jira` chains `create → detail → completeness-apply → jira`; `direct-run`
chains `create → detail → completeness-apply → run --commit → reconcile-code`.
Same gated stages, one process. If `create` produces a plan too large (or a
multi-plan split), the verb stops and points you at the full step-by-step
pipeline instead of one-shotting an over-large concept. See
[README → Direct pipeline](../reference/commands.md#cli-usage).

### 10. Use an existing compact Jira-grade bundle

You want each step described as **what changes, why, and how you know it
worked** — a brief a ticket reader and an implementer can both act on — rather
than the run-grade file's call sites, exact edits, and test rosters.

```bash
plan-tool jira my-feature --grade jira              # stories grounded on it
plan-tool run my-feature --detail-grade jira        # execute from it
plan-tool completeness-audit my-feature --grade jira  # audit against its contract
```

New Jira-grade detail authoring is disabled: use `plan-tool detail my-feature`
for new run-grade detail. Existing compact bundles remain legacy inputs in
their own `jira/` subdirectory; the run-grade bundle and every `detail:`
pointer stay untouched. `plan-tool jira` produces stories and the generated
developer handoff, which is terminal output rather than a replacement for a
detail bundle.

Each consumer **fails loudly** rather than falling back: a step whose jira-grade
artifact is missing or off-contract stops the export or the run before any
backend call, so you never get output silently grounded on the other grade. The
section contract is in
[`../../DETAIL_FORMAT.md`](../../DETAIL_FORMAT.md#jira-grade--the-compact-contract).

Two limits worth knowing before you commit: the jira-grade audit is
**report-only** (no findings sidecar, so no `completeness-apply`, no
`--iterate`, no `convergence` history for that run — you read the report and fix
by hand), and `direct-jira` / `direct-run` have no grade selector yet.

### 11. Ground a project-sized concept before you write a seed

> Inspect the repository and help prepare a grounded concept brief for review.
> Use the plan-tool skill to prepare a roadmap, link its artifacts and summarize
> decisions for my review before deriving seeds or individual plans.

See the [TTRPG demo](../demos/roadmap-demo.md) for the larger-concept review route.

You have a concept brief for a whole project rather than one feature, and you
can't yet say what the domain is, which quality attributes it trades on, or how
many plans it should become. Writing a `create` seed straight from that brief
means inventing all of it in your head first.

```bash
plan-tool roadmap my-project --from-existing path/to/concept.md
```

The stage run is first-run only. It holds each gate-clean stage in a resume
directory, so a run that stops part-way resumes from the first missing or
failing stage when you repeat the command with the same brief; a changed brief
is refused with its remedy. Once all four stages pass, it publishes one
immutable version and the accepted head. A roadmap that already has an accepted
head refuses a stage run: route semantic changes through ledger feedback and
candidate review, or a successor roadmap lineage.

**Worked end to end on a real run**, including automated plan derivation and
the manual fallback from artifacts to seeds:
[`docs/how-to/roadmap.md`](roadmap.md).

`roadmap` sits one rung above `create`. It writes four gated artifacts plus
draft seeds into one immutable version under `docs/implementation-plans/roadmaps/<slug>/`: **`01-domain.md`** — entities,
business rules, and workflows, each workflow and rule naming the entity ids it
touches — **`02-constraints.md`**, where every quality attribute carries
exactly one disposition (`prioritized`, `traded-away`, or `not-load-bearing` —
a real answer, not an omission) plus the constraints that discharge them,
anchored to ids `01-domain.md` defines — **`03-components.md`**, which
divides the domain into logical components grounded in those entity ids,
applies patterns, and discharges prioritized constraints — and
**`04-roadmap.md`**, which maps components to an ordered plan list with draft
seeds at each row's `draft_seed_path`. Claude runs only
*inside* a stage; the checks between stages are deterministic, and a failing
gate retries that stage with the violations quoted back instead of letting bad
output reach the next one.

Applying a feedback row invalidates derived seeds without replacing their
current bytes. Run `plan-tool roadmap my-project --refresh-seeds` to regenerate
them against current code, restore any archived copy, and save the difference
report. Until then, `create --from-existing` requires a confirmation before it
continues with an invalidated seed.

The verb is **non-interactive** during stage runs — no confirm, no prompt, no
`-y` (except under `--apply`, where `-y` is the second opt-in for seed
promotion). Where a stage
must guess at a load-bearing tradeoff it records the guess as a decision row
marked `pending`, and that is the review channel: read the artifact and accept
or reject the guess (accepting a decision means settling it: `plan-tool
roadmap <slug> --settle-decision <artifact>:<decision-id> --settlement-evidence
<artifact>:<feedback-id> --confirm-decision-settlement`, citing a live
feedback row that approves it).

**To change a published roadmap, say what is wrong in your own words.** Submit
a ledger item naming a design row or the artifact as a whole, then propose a
candidate:

```bash
plan-tool roadmap my-project --submit-feedback fb-gift-cards-are-out-of-scope --feedback-target domain:row:gift-card --feedback-request 'Gift cards are a later product decision. Drop the entity.'
plan-tool roadmap my-project --propose-candidate
```

The model may propose a response but may not close, defer, or delete your
request; reviewers make those changes through `--close-feedback`,
`--defer-feedback`, and `--reopen-ledger-feedback`. A candidate changes nothing
until it is approved and promoted; see
[`docs/how-to/roadmap.md`](roadmap.md) § 6.

A completed run exits 0 even with `pending` decisions and feedback awaiting
review still on disk. There are two non-zero exits: **1** when a stage spends
its retry budget (backend failure, unparseable reply, or gate violations
alike), and **2** for a pre-flight failure before any stage runs — an
unreadable or changed brief, a roadmap that already has an accepted head, or a
folder holding pre-head state.

**Where the arc stops today.** Four stages ship: `01-domain.md`,
`02-constraints.md`, `03-components.md`, `04-roadmap.md`, and draft seeds under
the slug directory. Stage 4 writes the plan mapping, emits draft seeds, and
prints runnable `create --from-existing` lines. Optional `roadmap <slug> --apply`
promotes drafts into `plan-seeds/`; it is not required to run `create` against
slug-relative draft paths. Manual seed authoring remains a fallback — see
walkthrough § 5. Arc position **05** (framework lenses) remains unauthored
(BACKLOG #208). When `create --from-existing` returns a `SplitProposal` instead
of a plan, stdout recommends `roadmap` as the structured decomposition path
(recommend-only; no slug or brief operands). `roadmap <slug> --view summary`
is the compact review starting point once the artifacts are written; it names
attention items and their drill-down commands. `roadmap <slug> --view
{walk,ledger,index}` reads the full relationships back when needed, and
`roadmap <slug> --view html` writes one self-contained, print-formatted page
(to `<roadmap-dir>/review.html` by default, or `--output <path>`) carrying
every row of all four artifacts, each resolvable reference linking to the
row it names and each dangling or ambiguous one visibly marked, opening with
an ER-style diagram of the domain entities and their reference fields — the
form to reach for when the task is reading the design rather than auditing its
state. They are backend-free deterministic renderings: `html` writes its
derived page, while the other views write no output file. All remain distinct
from `--apply` (which mutates `plan-seeds/`) and from `create` (which consumes
a seed).

See [`ROADMAP_FORMAT.md`](../../ROADMAP_FORMAT.md) for the artifact schema — including
the feedback row's keys, its lifecycle states, and what each one means — the
generated [`roadmap` command reference](../cli/roadmap.md) for the full flag
list, and
[RUNBOOK → redirecting a proposal with feedback](../../RUNBOOK.md#redirecting-a-proposal-with-feedback)
for the end-to-end loop.

## When *not* to use it

- **A trivial change.** A one-liner or a single obvious edit costs more to plan
  than to make. Just make it.
- **No repo to ground against.** The whole value is checking the plan against
  live code. Pure research or greenfield-with-no-code gets little benefit.
- **A plan you've already verified by hand** and only want to run — skip the
  audits and go straight to `run`.
- **You want the model to write code freely.** This tool deliberately scopes and
  gates generation; if you want unconstrained output, you don't want this.
- **Throwaway work.** Spikes and experiments you'll delete don't need a durable,
  re-grounded plan.

## Pick your entry point

| You're starting from… | Start with |
| --- | --- |
| A project-sized concept, before you have a seed | Ask for brief and roadmap review; `roadmap <slug> --from-existing <concept.md>` (writes four artifacts and draft seeds; review mapping, then run the printed `create --from-existing` lines — optionally `roadmap --apply` to promote into `plan-seeds/`; see walkthrough § 5) |
| A rough idea (1–2 sentences) | Ask for a grounded seed and review it, then `create <slug> --from-existing <seed>` |
| Nothing — author interactively | Ask for framing and seed review, or use the operator wizard: `create <slug>` |
| A rich draft (yours or an AI's) | Ask for grounding and input review, then `create <slug> --from-existing <path>` |
| A draft already in `## Steps` layout | `create <slug> --from-existing <path>` (skips the step-decomposition call) |
| An old plan + current code | Ask for carryover assessment and seed review; `annotate <old-plan>` → `create … --from-existing <seed>` |
| A plan file another tool wrote | Ask for grounding and review; `register <path>`, then both audit gates before separately requested execution |
| A small change you want straight to Jira stories | `direct-jira <slug> --from-existing <path>` (deprecated, BACKLOG #367 — see § 9) |
| A small change you want built and reconciled | `direct-run <slug> --from-existing <path>` (deprecated, BACKLOG #367 — see § 9) |

For the full flag-level reference, see [`../reference/commands.md`](../reference/commands.md) and the
generated per-command pages under [`docs/cli/`](../cli/README.md).
