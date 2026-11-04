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
| A draft (yours or an AI's) you want **pinned to reality** before trusting it. | Work that needs no durable plan or handoff. |

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
Commit a clean checkpoint before each long-running command; commit judged
corrections before re-auditing. Supporting command blocks show the route, not
permission to skip the review boundaries above.
See [monitoring and recovery](../../integrations/shared/DIRECTIVES.md#monitor-command-liveness-and-recover-safely).

### 1. Turn a rough idea into a buildable plan

> Inspect this repository and draft a grounded seed for [feature] with a scope fence and references; link it for review before creating the plan.

You have a feature in your head or a sentence in a ticket, and you want an
ordered plan a developer can build from.

```bash
plan-tool create my-feature --from-existing docs/implementation-plans/plan-seeds/my-feature.md --iterate
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
faith. Reconciliation does not replace either audit gate: follow
[the reviewed authoring sequence](#7-drive-a-plan-to-actually-correct-not-just-generated),
audit the bare plan before details, then audit the complete bundle before
separately requested execution or export. See [README → Decision flow](../../README.md#decision-flow).

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
plan-tool verify-all --rollup --fail-on-findings my-feature
```

`jira` exports the steps as stories; as they merge, you flip each step's
`status:` to `done`, and `verify-all` in CI catches drift between the plan and
the merged code (`--fail-on-findings` makes blocking findings fail CI;
without it, a completed verification exits 0 even with findings). You get a clean handoff plus
a CI gate. See [README → jira](../reference/commands.md#cli-usage) and
[verify-all](common-workflows.md#5-verify-all--ci-gate-after-the-jira-branch-conditional).

### 5. Keep a long-lived plan honest as the code moves

> Inspect this unexecuted plan and current code, then refresh its grounding and show proposed changes for review; do not implement it.

A plan you wrote weeks ago is still open, but the codebase has changed under it.
Use this route before execution. For work already produced by `run` or Jira
stories, preserve plan authority and use code reconciliation or
[annotate for the next iteration](#6-start-the-next-iteration-from-whats-already-built).

```bash
plan-tool reconcile-plan my-feature --refresh   # cheap: skips Claude on no drift
plan-tool reconcile-plan my-feature             # full plan-vs-code pass
```

`--refresh` compares a tracked fingerprint of the code against now and only
spends a Claude call when something actually drifted. You get a plan that
re-fits the repo instead of one that quietly went stale. Commit and review
plan changes, then repeat the applicable bare-plan or detail-grounded audit
before continuing; reconciliation does not certify either gate. See
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

### 9. Prepare a small change for execution or local export

> Use the plan-tool skill to prepare a grounded seed for this small change.
> Link the seed, plan and bare audit, then details and grounded audit for review
> at each boundary. After I approve the bundle, ask whether to execute it or
> export local stories and their paired developer handoff. Monitor commands to
> completion and report the actual results; do not publish tracker issues.

Use the same [reviewed authoring route](#7-drive-a-plan-to-actually-correct-not-just-generated)
as a larger feature, then choose [execution](#3-execute-a-plan-locally-one-step-at-a-time)
or [local Jira export](#4-hand-the-work-off-as-jira-stories). A small scope can
have fewer steps without removing either audit gate or the user's review points.
For a single obvious edit, use a direct change with
[its review loop](../../integrations/shared/DIRECTIVES.md#direct-changes-get-the-same-loop)
instead of creating a plan.

**Legacy compatibility only:** `direct-jira` and `direct-run` remain available
but are deprecated and scheduled for removal with `completeness-apply`
(BACKLOG #376). They chain gap-by-gap automatic application and are not the
route for new assistant-driven workflows. See the
[command reference](../reference/commands.md#cli-usage) for existing invocations.

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

Review the accepted roadmap's four artifacts before selecting plans:

| Artifact | What to review |
| --- | --- |
| `01-domain.md` | Entities, business rules and workflows |
| `02-constraints.md` | Quality-attribute priorities and the constraints that serve them |
| `03-components.md` | Component responsibilities and domain/constraint coverage |
| `04-roadmap.md` | Plan boundaries, ordering and dependencies |

The initial run checkpoints passed stages for recovery and publishes an
immutable version and accepted head only after all four pass. An existing
accepted head changes through reviewer ledger feedback and candidate review;
repeating the stage command does not regenerate it. A successful exit does
not mean pending decisions are settled.

Stage 4 supplies the plan mapping. Materialize selected draft seeds with
`roadmap my-project --materialize PLAN_ID`, then review their scope and
references before `create`. Materialization does not approve a seed. New seed
promotion with `roadmap my-project --apply` defaults to
`docs/implementation-plans/plan-seeds/`; existing recorded legacy destinations
stay in place. Promotion is optional: `create --from-existing` can consume a
reviewed draft at its reported path. Continue through the ordinary bare-plan
and detail-grounded audit gates for each selected plan.

Use the [TTRPG runbook](../demos/roadmap-demo.md) for assistant requests, and the
[roadmap walkthrough](roadmap.md) for commands, retained real-run observations
and these procedures:

- [Recover an interrupted initial run](roadmap.md#3-recover-from-a-stage-run-that-didnt-finish).
- [Inspect accepted artifacts and review views](roadmap.md#4-inspect-the-roadmap-without-calling-the-backend).
- [Settle a pending decision with evidence](roadmap.md#5-settle-a-pending-decision).
- [Submit feedback and review a candidate](roadmap.md#6-turn-reviewer-ledger-feedback-into-a-candidate).
- [Materialize, review and optionally promote seeds](roadmap.md#7-promote-accepted-draft-seeds-or-create-directly-from-them).

The [roadmap format](../../ROADMAP_FORMAT.md) owns immutable artifacts; the
[feedback format](../../ROADMAP_FEEDBACK_FORMAT.md) owns mutable reviewer input.
The [generated command reference](../cli/roadmap.md) lists flags and refusals.

## When *not* to use it

- **A trivial change.** A one-liner or a single obvious edit costs more to plan
  than to make. Just make it.
- **No repo to ground against.** The whole value is checking the plan against
  live code. Pure research or greenfield-with-no-code gets little benefit.
- **An already audited plan bundle.** Resume at execution when both audit
  gates cover the current committed bundle and the user authorizes execution.
  Informal manual verification does not replace those gates.
- **You want the model to write code freely.** This tool deliberately scopes and
  gates generation; if you want unconstrained output, you don't want this.
- **Throwaway work.** Spikes and experiments you'll delete don't need a durable,
  re-grounded plan.

## Pick your entry point

| You're starting from… | Start with |
| --- | --- |
| A single obvious edit | Skip plan-tool: edit directly, test and [review to convergence](../../integrations/shared/DIRECTIVES.md#direct-changes-get-the-same-loop). |
| A project-sized concept, before you have a seed | Ask for brief and roadmap review; `roadmap <slug> --from-existing <concept.md>`, then review the mapping, materialize selected seeds and review them before `create`; see [seed preparation](roadmap.md#7-promote-accepted-draft-seeds-or-create-directly-from-them) |
| A rough idea (1–2 sentences) | Ask for a grounded seed and review it, then `create <slug> --from-existing <seed>` |
| Nothing — author interactively | Ask for framing and seed review, or use the operator wizard: `create <slug>` |
| A rich draft (yours or an AI's) | Ask for grounding and input review, then `create <slug> --from-existing <path>` |
| A draft already in `## Steps` layout | `create <slug> --from-existing <path>` (skips the step-decomposition call) |
| An old plan + current code | Ask for carryover assessment and seed review; `annotate <old-plan>` → `create … --from-existing <seed>` |
| A plan file another tool wrote | Ask for grounding and review; `register <path>`, then both audit gates before separately requested execution |
| A small change you want straight to Jira stories | Use the reviewed authoring route, then request local stories and their developer handoff (§ 9 → § 4) |
| A small change that needs a durable plan and implementation checks | Use the reviewed authoring route, then request execution and post-run reconciliation/review (§ 9 → § 3) |

For the full flag-level reference, see [`../reference/commands.md`](../reference/commands.md) and the
generated per-command pages under [`docs/cli/`](../cli/README.md).
