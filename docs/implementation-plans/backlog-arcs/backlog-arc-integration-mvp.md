# Integration MVP backlog arc

## Current goal (2026-10-13)

Use Integration as the first serious real-project exercise of `plan-tool roadmap`.
Integration's product definition is owned by Integration's repository, per its
`handoffs/README.md` split (Integration records product decisions; this repository
records engine behavior). That README now carries an **order of operations**
naming which of its handoffs governs which step; read it first, then
`docs/concepts/integration-mvp-domain-disposition.md` (the product-intent authority).
This arc does not restate the product definition; it records the tool-exercise
route and the findings ledger.

**Integration's product shape moved on 2026-09-09 and this arc's exercise did not.**
Integration is now a multi-engine control plane: AI-DLC is the engine for phases 0–2
and `plan-tool` for Construction, with the seam at AI-DLC's Verification Gate
2. That is Integration's product. What this arc exercises is unchanged — building
Integration still runs `plan-tool roadmap` for Inception — and the two assignments
are deliberately different instances of one per-phase model. Do not read the
product's engine assignment as a change to the route below.

The successor roadmap `integration-aidlc-mvp` is accepted and this arc is at M4:
plans run one at a time in the roadmap's order. Six of the nine plans have run
to convergence (`connector-registry-seed`, `workflow-catalog-core`,
`step-completion-and-handoff`, `isolated-engine-worker`,
`chat-output-streaming`, `repository-browse-and-reference`). The remaining
three (`cdk-infrastructure-and-environments`, `bitbucket-deployment-pipelines`,
`static-spa-delivery`) carry the first real deployment, into a dedicated AWS
test account. Integration's per-plan convergence records and its
`docs/experiments/integration-cli-simulation/` observations are the evidence base;
the ledger below points at the plan-tool entries they produced.

For an enrolled roadmap, feedback enters the immutable candidate route. Do not
use the unversioned `--revise-feedback`, `--escalate-feedback`,
`--analyze-escalation`, or `--rewrite-structural` routes for this exercise.

## Which document is canonical (settled 2026-09-09)

**Integration's `handoffs/README.md` § "Order of operations" owns the sequence.** It
says what happens next, in what order, and what authorizes each step. **This
file owns the operating detail for driving `plan-tool` through that sequence**
— the exact invocations and their flags, the recovery recipes, the clone
topology and its delivery gate, and the findings ledger. It carries no
competing route.

The split is the one both repositories already state — Integration records product
decisions, source artifacts, execution gates, and authorized next actions;
this repository records engine behavior — applied to the routing question the
rule had not yet been applied to. Before this was settled, both files carried
an ordered sequence over the same work, and they diverged the first time the
brief's production changed: Integration's authoring route moved to an AI-DLC Ideation
run and M2 here stayed stale until it was amended. One sequence, in one file,
is what stops that recurring.

**So: drive from Integration.** Read its README's order of operations, and come here
for the commands and the operating knowledge each of its steps needs. The
milestones below keep their M-numbers because the ledger, the handoffs, and
this repository's own history cite them; each now names the Integration step it
serves rather than sequencing that step itself.

## File intent

This file is the operating guide for using Integration as the real project that
exercises `plan-tool roadmap`. It records how to run each `plan-tool`
operation Integration's route calls for, and the standing judgement of what those
artifacts prove about the roadmap verb.

## Details

It records the repositories and clones in play and the canonical-delivery gate
between them, what the tool will and will not do against Integration's existing
lineages, the `integration-aidlc-mvp` successor target, the roadmap operations and
their evidence, and the ledger of `plan-tool` findings Integration surfaces and where
each one is tracked.

Integration's first-pass product completion remains this arc's later outcome. Its
current phase tests the roadmap verb against the real product's artifacts. The
current phase ends when the roadmap-function questions are answered or routed
to the `plan-tool` subsystem that owns them; then the accepted roadmap output
can resume the delivery route.

Four dated grounding notes are tracked beside this file under `analysis/`;
see § "Reading map" below for what each one is and which parts are retired.

## Choose this arc when

The next session is going to run a `plan-tool` command against Integration, or is
going to judge whether the `roadmap` verb is fit for a real project. **Read
Integration's `handoffs/README.md` order of operations first for what step the
session is on; read this file for how to run it.** Do not materialize seeds or
create, detail, run, or implement a Integration plan until this
roadmap-function phase is complete and the user resumes delivery. Do not choose
it to fix `plan-tool` itself: a tool defect found here is filed where its subsystem lives
(`backlog-arc-roadmap.md`, `BUG_BACKLOG.md`, `BACKLOG.md`) and fixed in the
active development clone, never in this arc. A finding whose subsystem is
`archive/backlog-arc-structural-rewrite-safety.md`'s completed scope is a
fresh `BACKLOG.md`/`BUG_BACKLOG.md` item, never a reopening — that arc is
archived and takes no new work.

## Delivery cadence

Commit the Integration repository before every writing `roadmap` invocation and commit
each reviewed feedback, evidence, or artifact update as its own bounded commit
so a later session can see exactly what changed and why. Every `roadmap` call
is long-running: launch it in the background, tee it to a specifically named
`.tmp/integration-aidlc-mvp.roadmap.log`, prefix pipes with `set -o pipefail &&`, and never
kill a quiet process without the user's permission. Do not push automatically;
push only when the user explicitly requests it.

## Relationship to the roadmap arc

`backlog-arc-roadmap.md` § "Real-world evidence source" names Integration as the one
real consumer of the `roadmap` verb and rules that continuous real usage is
not tracked as its own arc, because it has no terminal exit. This arc begins
Integration MVP delivery with a bounded artifact exercise: it tests the roadmap verb's
artifact, feedback, evidence, and revision behavior before starting the
downstream plan pipeline.
The routing rule stands unchanged — a `plan-tool` defect found while driving
this arc goes to the file that owns the subsystem, and this arc only records
that it was found and where it went (§ "Plan-tool findings ledger").

## Working set — repositories and clones

Resolve the root roles using
[portable checkout paths](../../../CONTRIBUTING.md#portable-checkout-paths).
`<development-root>` and `<documentation-root>` are locally selected working
clones; verify each with `git -C <checkout> rev-parse --show-toplevel`. Neither
role implies the source used by the installed CLI.

| Path | Role | Rule |
| --- | --- | --- |
| `<integration-consumer-root>` | The Integration repository: product handoffs and disposition, concept briefs, roadmap lineages under `docs/implementation-plans/roadmaps/`, stale promoted `plan-seeds/`, run logs, evidence store. | Every `plan-tool` command in this arc runs from this root (or with `--repo-root` pointing at it). Nothing here is a `plan-tool` source tree. |
| `<integration-infra-root>` | Separate infrastructure repository the frozen `integration` roadmap's `platform-baseline` row consumes (self-mutating CDK pipeline, prerequisite contract). | Not touched by this arc until a milestone names it. |
| `<installed-plan-tool-root>` | The **canonical** `plan-tool` repository. The installed `plan-tool` binary is an editable install of this directory (`~/.local/share/uv/tools/plan-tool/…/_editable_impl_plan_tool.pth` → this path), so whatever is checked out here is what runs against Integration. | The only checkout allowed to run a writing command against Integration (§ "Canonical Plan-tool delivery gate" in `backlog-arc-roadmap.md`). |
| `<development-root>` | A `plan-tool` development clone. M0 discovers its current selection only when a Integration session needs a named fix. | Fix the tool here. Do not run it against Integration's real files. |
| `<documentation-root>` | This clone maintains this arc document and may carry unrelated tool work. | Do not run it against Integration's real files. |

**Current delivery rule.** Clone roles, commit counts, and branch tips are
not durable evidence. M0 identifies the installed and canonical commits and
checks a named dependency against them. A clone-local change is never eligible
to run a Integration write; it must be committed, verified, pushed to `origin`, and
pulled into the canonical checkout first.

Verify which code is about to run, every time, before a writing command:

```bash
cat "$(uv tool dir)"/plan-tool/lib/python*/site-packages/_editable_impl_plan_tool.pth
git -C "<installed-plan-tool-root>" log -1 --format='%h %ad %s' --date=short
git -C "<installed-plan-tool-root>" status --short
plan-tool roadmap --help | head -5
```

The reported commit must contain the fix the session depends on, the tree must
be clean, and the help text must list every flag the milestone's commands use.
`plan-tool --version` prints the release version but not the commit, so the `.pth` line plus the commit are still the check.

## Reading map — the interplay across repos

Three repos, and only one entry point named "arc" that is about Integration
specifically: **this file.** Read it end to end first; it is designed to need
nothing else for the milestone route. Everything below is what it draws from
and hands off to, by repo, so a reader can find any of it without re-deriving
which of the three checkouts holds it.

**This repo (`plan-tool-1` or `plan-tool-2`) — the plan of attack, not the product**

- `docs/implementation-plans/backlog-arcs/backlog-arc-integration-mvp.md` — this file.
- `docs/implementation-plans/backlog-arcs/analysis/integration-mvp-*.md` — four
  grounding notes dated 2026-08-28. Each carries a status line saying which
  parts are retired; none defines Integration's product:
  - `integration-mvp-aidlc-grounding.md` — what AI-DLC's five phases and its `mob`
    stage mode actually define at v2.5.62. Its "how Integration maps onto it" and
    vocabulary-map halves describe the retired 2026-08-28 definition.
  - `integration-mvp-sample-ux-grounding.md` — the AWS sample's mechanics and the
    defects to refuse (regex-sniffed approvals, in-band UI tags, unversioned
    transcripts, socket-as-record). The refusals remain useful evidence; its
    "copy the UX concept" recommendation is not a Integration decision.
  - `integration-mvp-orchestration-facts.md` — measured `plan-tool` behavior
    (verified against copies of Integration's real tree): no git repo required,
    self-baselining stage writes, the revision-vs-forward-path split, the
    JSONL run-log status feed. Still valid, except that `--revise-feedback` is
    a retired route for enrolled roadmaps.
  - `integration-mvp-domain-gap.md` — what the frozen `integration` domain models and what
    the two earlier feedback rows on its `01-domain.md` asked for. Its
    conversation/mob entity gap analysis describes the retired definition.
- `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md` — the sibling
  arc for the `roadmap` verb's own capability work (not Integration-specific);
  cross-linked in both directions with this file (§ "Relationship to the
  roadmap arc" above, and its own "Real-world evidence source" section).
- `handoffs/2026-08-28-integration-web-and-cli-question.md` — dated history. Its
  decisions (web-first, no Integration CLI, `plan-tool` at the technical boundary,
  Jira as a run-grade implementation-detail export with concise stories and a
  paired developer handoff) stand; its consulting-engagement domain does not — Integration's
  `docs/concepts/integration-mvp-domain-disposition.md` records what superseded it.

**The `integration` repository — the product this arc is delivering**

- `handoffs/README.md` — read this first. Its **order of operations** names
  which handoff governs which step of the route, in working order rather than
  the newest-first order the list shows.
- `handoffs/2026-09-08-roadmap-exercise-reframe.md` — the objective split, the
  AI-DLC `mvp`-scope stage table, lineage standings, and the decisions made.
  Still binding; its brief-authoring line is amended by the route below.
- `handoffs/2026-09-08-aidlc-authoring-route.md` — how the brief is produced:
  AI-DLC Ideation at `feature` scope to Gate 1, the composition rule, and the
  six preconditions. This is M2's governing document as of 2026-09-09.
- `handoffs/2026-09-09-roadmap-from-ideation.md` — what `roadmap` expects of
  its one brief against what Ideation hands over: the artifact-to-stage
  mapping, and the two defects behind this arc's 2026-09-09 ledger rows.
- `handoffs/2026-09-09-control-plane-mvp-shape.md` — the product's engine
  model and the evidence for it. Read when a decision needs its citation; it
  routes nothing in this arc.
- `docs/concepts/integration-mvp-domain-disposition.md` — the single product-intent
  authority: product intent, phase ownership, vocabulary, the successor
  route, lineage dispositions, and the dated decisions that still bind.
- `integration-roadmap-concept.md` — the original brief. Its architecture and
  topology decisions (S3/CloudFront, ECS Fargate, plan-tool as engine of
  record) are retained by citation; its initiative/roadmap domain is
  superseded by the four-phase definition in Integration's disposition.
- `docs/implementation-plans/roadmaps/integration/{01-domain,02-constraints,
  03-components,04-roadmap}.md` — the frozen roadmap generated from that
  brief. Retained as evidence; never hand-edited, and not re-entered without
  a newly authorized route.
- `plan-seeds/*.md` — the nine seeds promoted from that roadmap, stale, to be
  archived before a new roadmap's `--apply` (M4). One of them is
  `pilot-rollout.md`; "operations" is reserved vocabulary for the concept doc
  below and is not reused for pilot work.
- `docs/concepts/operations-phase.md` — a speculative, not-yet-authorized
  future Operations-phase outline. The AI-DLC `mvp` scope excludes Operation
  and Integration's disposition lists it out of the MVP.

**Development clones — where tool changes originate**

No Integration-specific document lives in a development clone. A session inspects a
clone only when it needs a named tool fix, then M0 verifies that the completed
fix has reached canonical before any writing command runs against Integration.

## What the tool will and will not do against Integration's existing lineages

Product standing for each lineage lives in Integration's
`docs/concepts/integration-mvp-domain-disposition.md`. What this arc needs is the
mechanical state, verified against copies of Integration's real tree.

- **No `integration` stage can be revised.** Its `constraints` and `components`
  baselines refuse admission after a hand repair, and `--enroll-baselines`
  bootstraps only a wholly unenrolled prefix, so it will not replace them. A
  revision attempt fails closed before any backend call, costing time and no
  tokens. A reusable recovery route is deferred
  (`roadmap-source-baseline-recovery`, user-confirmed 2026-08-27) and M1
  rejects the one-time remedy.
- **Baseline drift never blocked the forward path.** `--materialize`,
  `--apply`, and `create` do not admit a stage against its baseline. An
  earlier draft of this arc claimed the opposite, which is the don't-repeat
  behind M1's rule: price a route by running it against a copy of the real
  tree, not by reading the document that describes it.
- **Nine promoted seed destinations are occupied.** `plan-seeds/` holds the
  2026-08-11 promotion and `--apply` refuses by default on an existing
  destination, on any roadmap that reuses one of those plan ids. M4 archives
  them in their own commit first.

M5 replaces this section with the successor's state once M3 has run.

## The product under test — recorded in Integration, not here

Integration's product definition lives in Integration's repository, per its
`handoffs/README.md` split: Integration records product decisions; this repository
records engine behavior. Read that README's order of operations and
`docs/concepts/integration-mvp-domain-disposition.md` there before running any
milestone below.

The summary this route depends on, current at 2026-09-09: Integration is an MVP for
the AI-DLC Initialization, Ideation, Inception, and Construction phases,
delivered as a **multi-engine control plane**. Engines supply every stage and
Integration authors no agent workflows of its own; in the product, AI-DLC is the
engine for phases 0–2 and `plan-tool` for Construction, with the seam at
AI-DLC's Verification Gate 2 and the AI-DLC workflow parked there. A chat
agent interface manages artifact feedback and routes it to the owning engine's
own revision path. The AI-DLC `mvp` scope (23 of 33 stages, no Operation) is
the completeness target for *building* Integration, not a limit on what the product
renders — the product models the engine's full stage vocabulary and treats
scope as a runtime selection.

**What that does and does not change for this arc.** Building Integration uses a
different assignment of the same per-phase model — AI-DLC for phases 0–1,
`plan-tool roadmap` for Inception, `plan-tool` for Construction — and that is
the assignment every milestone below runs. Both are instances of one model and
neither supersedes the other. Integration's pre-roadmap concept, questions,
refinement, and affirmation step is Ideation; earlier documents that call it
"Inception" use retired vocabulary.

**Superseded 2026-09-08/09, kept because a reader will meet it in older
prose.** The definition in which "Integration runs Initialization and Ideation with
generic agent workflows" is retired: engines supply those stages now. The
sentence survives in documents dated before 2026-09-09; the disposition doc is
what is current.

**Retired 2026-09-08.** This section formerly held a 2026-08-28 definition of
Integration as two phases (Inception and Construction) built around a
mob-contribution loop with a three-pane UI copied from the AWS sample. That
definition is not Integration's product and is not to be reintroduced from the dated
grounding notes under `analysis/`; those notes remain evidence of what AI-DLC
and the sample define, not of what Integration builds.

**Fence this route enforces at roadmap review.** A row that delivers any of
the following is refused, not deferred: the Operation phase; AI-DLC rule-file
import, runtime embedding, or a compatibility layer; Jira API writes (the
`jira` export is the only Jira surface); a Integration CLI or a `PLAN_TOOL_HUMAN_IO`
browser transport; the `plan-tool` #322 headless arc; AgentCore Runtime
adoption ahead of an ECS-only baseline; a multi-environment pipeline (the MVP
deploys one environment). Integration's disposition carries the full out-of-MVP list.

## Operating guide, by Integration step

**The sequence is Integration's**, in its `handoffs/README.md` § "Order of
operations". This section supplies the `plan-tool` operating detail each of
its steps needs. Each milestone states its entry condition, the commands, and
the exit evidence; what it no longer states is what comes next, because that
is Integration's to say.

| Integration step | Milestone here | What this file supplies |
| --- | --- | --- |
| Any writing command, before it runs | **M0** | The tool-identity check. Integration's step 5 and its reframe handoff both require it and neither defines it; this is where it lives. |
| Settled before step 1 | **M1** | The successor-lineage decision and its rejected alternatives, as `plan-tool` mechanics. Integration's disposition carries it as product intent. |
| Steps 2–4 (Ideation, compose, review the brief) | **M2** | What the brief has to contain for `roadmap`'s stages to work, and the enumeration caution. Integration's authoring route governs how it is produced. |
| Steps 5–6 (generate, review the roadmap) | **M3** | The generation invocation, the review views, and the candidate-lifecycle commands for feedback. |
| Step 7 (seeds, plans, execution) | **M4** | Seed promotion, `create`, the audit gates, `detail`, `run`, `reconcile-code`. |
| After steps 6 and 7 | **M5** | What to write down while the evidence is fresh, and where. |

Findings against the tool go to the ledger and the owning backlog file at the
moment they are observed, not at a milestone boundary.

### M0 — Identify the tool before trusting it

*Serves: any Integration step that runs a writing command — its step 5 requires this
check by name.*

**Entry:** any session that will run a writing `plan-tool` command against
Integration.

1. Re-run the verification block in § "Working set". The `.pth` target, the
   canonical commit, a clean tree, and the flag list must all check out.
2. Decide whether a pull is actually needed, rather than pulling by reflex.
   Identify the named fix the session needs, verify whether the canonical
   checkout contains it, and compare the relevant code rather than a
   historical commit count. The canonical delivery gate in
   `backlog-arc-roadmap.md` forbids testing a clone-local change against Integration;
   a change that has not been pushed to `origin` and pulled into canonical has
   no Integration authority, however complete it is in its own clone.
3. In Integration: confirm `git status --short` shows only the known stray writer
   lock, decide its disposition (§ ledger), and commit the reviewed state.
4. Read-only baseline check, run from `plan-tool-1` or canonical (it imports
   `plan_tool` and writes nothing):

   ```bash
   uv run python - <<'EOF'
   from pathlib import Path
   from plan_tool.roadmap import STAGES
   from plan_tool.roadmap_source_identity import admit_baseline_backed_source, RoadmapSourceIdentityError
   plans_dir = Path("<integration-consumer-root>/docs/implementation-plans")
   root = plans_dir / "roadmaps" / "integration"
   for stage in STAGES:
       art = stage.parse(stage.artifact_path(plans_dir, "integration").read_text())
       try:
           admit_baseline_backed_source(art, roadmap_root=root, roadmap_slug="integration", stage_key=stage.artifact_key)
           print(stage.artifact_key, "ADMITTED")
       except RoadmapSourceIdentityError as e:
           print(stage.artifact_key, "REFUSED:", e)
   EOF
   ```

**Exit:** the installed tool is identified by commit and contains whatever the
next milestone names; the Integration tree is committed; and the baseline check
result is recorded in Integration's current `handoffs/` record. Expect
`domain`/`plans` admitted and `constraints`/`components` refused on the frozen
`integration` lineage; that is its settled state, not a repair signal.

### M1 — Roadmap disposition (decided 2026-09-08)

*Serves: settled before Integration's step 1. Integration's disposition doc carries this as
product intent; what follows is the `plan-tool` mechanics behind it.*

**Decision:** a successor roadmap, `integration-aidlc-mvp`, grounded in a fresh
`integration-aidlc-mvp-concept.md` (hand-authored as decided; composed from an AI-DLC
Ideation run as amended 2026-09-09, see M2). Every earlier lineage stays as
readable evidence; none is repaired, re-entered, or promoted.

Why a successor and not a revision: the accepted
`project-workspace-membership-proof` lineage's recorded brief defines a
one-journey vertical proof, and the product outcome is now the four-phase MVP.
`plan-tool`'s lineage rule (`docs/how-to/roadmap.md` § "Reuse the slug, or start a successor")
reserves an outcome change for a successor named `<product>-<concept-boundary>`
and paired with `<slug>-concept.md`. `integration-aidlc-mvp` names the product and
the boundary (the AI-DLC `mvp` scope). The boundary word is a session choice;
rename it before the first `roadmap` write if a different word is wanted,
because the slug is fixed by that write.

Rejected 2026-09-08, each with its reason: extending the membership proof by
feedback rows (changes the lineage's outcome and exercises only the feedback
lifecycle); driving `integration` forward from its frozen seeds (builds the retired
initiative pilot); the one-time 2:3 baseline remedy on `integration` (an unsupported
hand mutation of writer-owned trust state, with nothing to gain now that
`integration` is evidence); overwriting `integration` in place (refused by the tool:
`already grounded in integration-roadmap-concept.md`).

Verified 2026-08-28 on a copy of Integration's real tree, and still the mechanics
this route relies on: a new slug in the same repo reaches the backend with no
baseline prerequisite, and `publish_stage_artifact` writes each stage's
artifact and baseline together, so every route on the successor is open from
the first write. `--apply` refuses on an existing `plan-seeds/<plan-id>.md`,
so the nine 2026-08-11 promoted seeds are archived before the successor's
first promotion (M4).

**Exit:** recorded here and in Integration's current handoff and disposition.

### M2 — Author the MVP concept brief

*Serves: Integration's steps 2–4. Integration's authoring route governs how the brief is
produced and reviewed; this milestone says what it must contain for
`roadmap`'s stages to work, and what it must not contain.*

**Entry:** M1 decided. The brief is the intent the roadmap generates from, at
roadmap altitude, per `docs/how-to/roadmap.md` § 1 (scale and load shape,
what must not go wrong, the calls still open). Path:
`<integration-consumer-root>/integration-aidlc-mvp-concept.md`.

**Amended 2026-09-09 — how the brief is produced.** It is no longer written
from a blank file. Integration runs AI-DLC Initialization and Ideation at `feature`
scope, stops at Verification Gate 1, and composes the brief from that output;
`handoffs/2026-09-08-aidlc-authoring-route.md` in Integration governs it and is the
document to follow, not this milestone's prose. What that route settles, and
why it matters to this arc:

- **`feature`, not `mvp`, for the Ideation run.** `feature` includes stage 1.7
  Approval & Handoff, which compiles the initiative brief and runs the
  Ideation → Inception verification check; `mvp` skips it and produces no
  brief artifact at all. The AI-DLC `mvp` scope remains Integration's *product*
  completeness target and the thing the generated roadmap is judged against —
  it was never the scope the brief is authored under.
- **The composition rule.** Initiative brief, plus the hosting facets and
  quality-attribute dispositions from feasibility, plus the settled answers
  from every stage's questions file, plus the fence. `intent-backlog.md` is
  excluded: it is prioritized proto-Units, which is exactly the enumeration
  this milestone's own caution is about.
- **An upstream rule closes the stage-2 gap before it opens.** A
  `memory/phases/ideation.md` rule, written before the run, makes feasibility
  record the three hosting facets in this tool's closed values and dispose the
  seven quality attributes — the same facts the 2026-08-24 `stage-exhausted`
  recovery row below had to be hand-repaired for.

Everything else in this milestone stands unchanged, and the caution below is
the reason the composition rule excludes what it excludes.

The brief states, in this order:

1. **Product intent** — the four-phase outcome in substance from Integration's
   disposition: Integration is an MVP for AI-DLC Initialization, Ideation,
   Inception, and Construction; Integration runs Initialization and Ideation with
   generic agent workflows; `plan-tool roadmap` is Inception; implementation
   plans are Construction; the chat agent interface manages artifact feedback
   and coordinates rebuilds; project creation is a direct operation that uses
   AI-DLC-style workflow agents for the initial artifacts.
2. **Authority and topology carried forward**, cited by decision id from the
   frozen `integration` roadmap and by date from Integration's disposition: plan-tool as
   engine of record; web control plane plus managed ECS worker; server-side
   credentials; durable jobs and reconnectable status; immutable versioned
   artifacts with lineage; explicit human approval at material gates; the
   many-people, many-projects membership model.
3. **Completeness target** — one sentence naming the AI-DLC `mvp` scope and
   pointing at Integration's handoff for the stage table. Not the table itself; see
   the caution below.
4. **Fence** — the out-of-MVP list from Integration's disposition, stated as
   non-goals the stage-4 rows must respect.
5. **Decisions the roadmap must resolve** — each phrased as a question with
   the evidence that would settle it. Front-load only go/no-go gates; a step
   whose *design* depends on an investigation the same roadmap contains is
   the `premise-conditioned-design` shape and belongs in a throwaway probe
   before the brief, not in a row.
6. **Scale** — roughly 100 internal employees, many projects, one lifecycle
   run per roadmap lineage; not multi-tenant.

**Write it at product altitude, not at stage altitude.** `roadmap` spends four
backend calls establishing a domain vocabulary and a citable decision record;
a brief that only lists phases and stages gives stage 1 nothing to model and
produces a thin domain that `create` would have covered for one call. The
brief must describe the world the product operates in — project, membership,
repository, source document, concept brief, roadmap lineage, feedback, plan,
worker job; who produces and approves each; what must not go wrong when
feedback is lost, contradicted, or never returned — and then name the four
phases as what the product delivers inside it. If the brief cannot be written
that way, that is the signal to skip `roadmap` and write a `create` seed
instead.

Sweep the draft for vocabulary before running it: Integration's pre-roadmap step is
Ideation, not Inception; `mob`, `contribution`, `engagement`, `SOW`, and
`initiative` do not appear; every `roadmap`/`seed`/`plan`/`detail` term that
survives is there because the MVP genuinely reuses that plan-tool concept,
not because it was copied from an old brief.

**Do not write a "should separately stage" list, and cap the deployment
posture explicitly.** This is the measured lesson from the existing roadmap,
and it is the single highest-leverage line in this milestone.
`integration-roadmap-concept.md` § "Scope for the first roadmap" asks for "the
smallest coherent product slice… **It should also establish the platform
foundations required to expand safely to approximately 100 users**", then
enumerates a nine-bullet "should separately stage" list. The roadmap returned
**exactly nine plan rows** covering those nine bullets — including a
`cross-cutting`, first-in-order `platform-baseline` committing to four
environments, two application pipelines, a separate self-mutating infra repo,
a versioned prerequisite contract with digest validation, concurrent-promotion
ancestry checks, and release plus hotfix scripts. Roughly 11,300 words of
roadmap and 3,300 words of seeds came out of that one enumeration.

The tool did its job faithfully; the brief asked for a platform and got one.
So: state the four phases and the fence, state that the MVP deploys **one**
environment and that deployment posture is deliberately not staged as a
foundation, and let stage 4 decide how many rows the work needs. An
enumeration in the brief becomes a row count in the roadmap.

**Exit:** the brief is committed in Integration; it names the four phases, the fence,
and the pending decisions; a read-through confirms it does not pre-select
mechanisms the roadmap should choose, and that it contains no enumeration the
roadmap will return one row per (the caution above).

### M3 — Generate and review the MVP roadmap

*Serves: Integration's steps 5–6.*

**Entry:** the brief is committed in Integration and has passed its step-4 review;
M0 verification re-run in the same session.

Generation (conceptual work → Codex Sol, per `CLAUDE.md` § "Model
selection"):

```bash
cd <integration-consumer-root> && git status --short   # must be clean
set -o pipefail && plan-tool --backend codex \
  roadmap integration-aidlc-mvp --from-existing integration-aidlc-mvp-concept.md \
  2>&1 | tee .tmp/integration-aidlc-mvp.roadmap.log
```

Background it, announce the task id and log path, and treat it as complete
only when all four artifacts exist, no `plan-tool roadmap` process remains,
and `--view summary` renders. Then review without the backend:

```bash
plan-tool roadmap integration-aidlc-mvp --view summary --mode review
plan-tool roadmap integration-aidlc-mvp --view walk --mode review
plan-tool roadmap integration-aidlc-mvp --view ledger --mode review
plan-tool roadmap integration-aidlc-mvp --view index --id <row-id>
plan-tool roadmap integration-aidlc-mvp --view seeds
```

Read each stage the way the walkthrough prescribes — seams in `01-domain.md`,
a ranking (not an all-`prioritized` table) in `02-constraints.md`, ownership
and discharge in `03-components.md`, intent / delivery shape / non-goals per
row in `04-roadmap.md` — and judge the roadmap against Integration's fence and the
23-stage `mvp`-scope target in Integration's handoff: a row that delivers a fenced
capability is a review finding, and a phase the target includes with no row
and no named later slice is a gap.

Feedback, one reviewer-approved row at a time, through the immutable candidate
route (never `--from-stage` merely to close a row, never a hand edit to a
canonical artifact after its baseline exists — that is exactly how `integration`
closed its own routes):

```bash
# Add one `feedback:` row (block scalar `>-` for the request text) to the
# artifact and commit it. Run this once only when no accepted root exists.
plan-tool roadmap integration-aidlc-mvp --enroll-version
# Propose one inert, complete roadmap candidate from the selected feedback.
set -o pipefail && plan-tool --backend codex \
  roadmap integration-aidlc-mvp --propose-candidate domain:<feedback-id> 2>&1 | tee .tmp/integration-aidlc-mvp.candidate-<feedback-id>.log
# Review the initial candidate, answer its stored question, then promote only
# the exact sealed replacement.
plan-tool roadmap integration-aidlc-mvp --review-candidate <INITIAL_CANDIDATE_VERSION_ID>
plan-tool roadmap integration-aidlc-mvp --answer-question <QUESTION_ID> --answer '<ANSWER>'
plan-tool roadmap integration-aidlc-mvp --promote-review-seal <REVIEW_SEAL_ID>
```

Commit each candidate, review record, seal, and accepted-head update as its
own bounded checkpoint.

**Current candidate-policy boundary.**
`plan_tool/roadmap_candidate.py:materialize_candidate()` now returns a hard
refusal, a review-required candidate, or a gate-clean candidate. An otherwise
valid selected-feedback candidate with an exact, capsule-authorized,
mechanically derived policy impact reaches this same review path as an inert
review-required candidate; all other relation failures remain refusals and
publish no candidate. Every review-required-lineage replacement, including a
gate-clean result, recomputes impact facts and requires
multiplicity-preserving containment by the initial disclosure while reusing the
initial admitted capsule. Record delivery evidence in this arc, but do not
narrow the feedback request, hand-edit canonical artifacts, add a second
relation-confirmation workflow, or direct a mutation to Integration's accepted
roadmap. `ROADMAP_FORMAT.md` owns the complete lifecycle contract.

**Exit:** four gate-valid artifacts under `roadmaps/integration-aidlc-mvp/`; every
feedback row is promoted through a sealed candidate or explicitly deferred;
pending decisions triaged into "settles before seeds" and "settles inside a
plan"; the review recorded in the session handoff with the stage counts. Do
not materialize seeds while a row that changes a plan row is still open —
any artifact change invalidates all draft seeds.

### M4 — Seeds, first plan, gates, execution

*Serves: Integration's step 7.*

**Entry:** M3 exit evidence exists and is committed.

First clear the promotion destinations: `--apply` is refuse-by-default on an
existing `plan-seeds/<plan-id>.md`, and Integration already holds nine from the
2026-08-11 promotion. Archive or delete the ones the new roadmap will reuse
before promoting, in their own commit.

```bash
plan-tool roadmap integration-aidlc-mvp --materialize                  # or --materialize <plan-id> for one row
plan-tool roadmap integration-aidlc-mvp --view seeds                    # every needed draft classifies `current`
plan-tool roadmap integration-aidlc-mvp --accept-seed <plan-id>         # only for a reviewed hand-edited draft
plan-tool roadmap integration-aidlc-mvp --apply -y                      # promotes drafts into plan-seeds/
```

Review each promoted seed against `SEED_FORMAT.md` and the MVP fence at seed
altitude (correctness fully; completeness only for HIGH/CRITICAL omissions).
Then the ordinary pipeline for the first row — one plan at a time, in the
roadmap's ordering:

```bash
git status --short                                         # clean before every call
set -o pipefail && plan-tool --backend codex \
  create <plan-id> --from-existing plan-seeds/<plan-id>.md 2>&1 | tee .tmp/integration-aidlc-mvp.create-<plan-id>.log
set -o pipefail && plan-tool --backend codex \
  completeness-audit <plan-id> --iterate --commit 2>&1 | tee .tmp/integration-aidlc-mvp.audit-bare-<plan-id>.log
#   → hand-apply plan-correctness findings; re-audit until one of the three exits fires
set -o pipefail && plan-tool --backend codex \
  detail <plan-id> --commit 2>&1 | tee .tmp/integration-aidlc-mvp.detail-<plan-id>.log
set -o pipefail && plan-tool --backend codex \
  completeness-audit <plan-id> --iterate --commit 2>&1 | tee .tmp/integration-aidlc-mvp.audit-detail-<plan-id>.log
set -o pipefail && plan-tool --backend codex \
  run <plan-id> --all --commit -y < /dev/null 2>&1 | tee .tmp/integration-aidlc-mvp.run-<plan-id>.log
set -o pipefail && plan-tool --backend codex \
  reconcile-code <plan-id> --all 2>&1 | tee .tmp/integration-aidlc-mvp.reconcile-<plan-id>.log
```

The model is pinned in Integration's `.plan-tool/backends.json` (`gpt-6.1-sol` for
every codex call, set 2026-10-12), so these commands name no `--model`.

followed by a `/code-review` loop to convergence. The audit gates, exits,
`--commit` rules, and reconcile directionality are the ones in
`integrations/shared/DIRECTIVES.md`; this arc adds only the Integration-specific
check that each plan's steps map to a phase the completeness target includes
or to a prerequisite the brief named, and nothing else.

**Exit per plan:** all steps green and committed; three clean
`reconcile-code` sweeps or an explicit deferral; the plan's contribution to
the MVP slice demonstrable. **Exit for the milestone:** the four MVP
phases are exercisable end to end on one project.

### M5 — Judgement checkpoint

*Serves: after Integration's steps 6 and 7.*

**Entry:** after M3, and again after each M4 plan. This is where the
"first real project" evidence is written down while it is fresh.

Record, in the session handoff and in the ledger below: what the roadmap
verb produced that a hand-written seed would not have (seams, trade-offs,
decision records); where it cost more than it returned (retries, gate
churn, re-review after invalidation); which feedback rows entered candidate
review and what their proposed diffs and review questions established; and
every tool defect, with the backlog file it went to. Then rewrite § "What the
tool will and will not do against Integration's existing lineages" so it describes
`integration-aidlc-mvp`, deleting the predecessor state it replaces rather than
keeping both.

**Exit:** that section describes the successor; the ledger has no undated
entry and every entry says whether it is a tool defect or a seed-shape
finding.

## Recovery recipes observed on Integration

These are the failures the `integration` run logs actually recorded and the response
each one earned. They are here so the next session does not rediscover them.

| Observed | What it was | Response |
| --- | --- | --- |
| Stage 4 `attempt_failed` → `gate_violations` → retry, sometimes `stage-exhausted` (2026-08-11/12, five runs). | Gate retries on the plans stage; a completed run may still hold `pending` decisions. | Retries are normal; `stage-exhausted` means re-enter with `--from-stage 4` after reading the gate lines in the log. Pending is a review queue, not a failure. |
| Runs ending `outcome: error` inside a stage-1 `claude_call_start` (2026-08-12, three runs); "three failed revision attempts on a 35 KB artifact" (2026-08-19 analysis). | Whole-artifact regeneration of a 783-line YAML file: a dead call, an unparseable reply, and one silent rewrite the gate caught after a 15-minute round trip. **This is the timeout that stopped Integration work and forced the roadmap re-architecture.** | The bounded stage-feedback route fixed the former unversioned case. The current route uses immutable candidates; never expect a whole-stage rerun to recover feedback. |
| `roadmap_preflight_failed … invalid YAML in 01-domain.md` (2026-08-12) and again for `02-constraints.md` (2026-08-24). | A hand-typed feedback `request` in a quoted scalar containing an apostrophe. | Write requests as block scalars (`>-`). `ea6b41fe` makes the reviewer stub use that shape and returns the repair snippet on malformed feedback frontmatter. |
| Stage 2 `stage-exhausted` after three attempts (2026-08-24): replies omitted schema-required hosting facets; downstream `stage-invalid` on missing store bindings. | Schema fields (`hosting` compute/model/topology, `stores`/`store_ids`) added to the artifact schema after Integration's first run; broad regeneration does not reliably produce them. | Those are material deployment choices — a person decides them. On `integration` they were hand-repaired under authorization, which then closed the baseline routes. On `integration-aidlc-mvp` the brief states them up front so stage 2 has the facts. |
| Stale `.plan-tool/mutation.lock` / `roadmap-integration.writer.lock.stale-20260826` after a terminated run. | A killed run leaves its lock. | Verify the recorded PID is dead before removing a lock; never remove one merely because it exists. |

## Plan-tool findings ledger from Integration

What real use has surfaced, in the order found, and where each is owned. An
entry here is a pointer; the owning file carries the design.

Two kinds of entry live here and both are wanted. A **tool defect** is owned by
the backlog file for its subsystem. A **seed-shape finding** records what a
source brief's shape does to the artifacts it produces; those are owned here,
because learning what shape a seed needs is a stated purpose of driving
`roadmap` against a real project, not a by-product of it. Mark which kind an
entry is rather than leaving a reader to infer it.

| Found | Finding | Owner / state |
| --- | --- | --- |
| 2026-08-12 | Hand-typed feedback in a raw YAML scalar corrupts the canonical artifact. | **Bounded recovery 2026-08-28** in `ea6b41fe`: generated guidance uses `request: >-`, and malformed feedback frontmatter names that repair. The canonical renderer preserves supported scalar styles. |
| 2026-08-19 | Whole-artifact regeneration fails on real (35 KB) artifacts; the codebase already had the bounded pattern in two other places. | `backlog-arcs/analysis/roadmap-feedback-revision-architecture.md`; **shipped 2026-08-20** as the bounded stage-feedback route (`backlog-arc-roadmap.md` step 0). |
| 2026-08-23 | Schema fields added after first generation (`hosting`, `stores`) block v2 evidence until a human supplies the facts; enrollment requires exact-canonical files (a parse→render rewrite was needed first). | Recorded in Integration `.tmp/roadmap-v2-evidence-onboarding.md`; no tool change filed — the facts were genuinely missing. |
| 2026-08-24 | v1-schema receipts appeared through the CLI after the v2 lock. | **Closed 2026-08-28** as an archive-safe Integration-local won't-do; `BACKLOG.md` #313 remains conditional, with the unverified mechanism retained only as provenance. |
| 2026-08-26 | Escalation receipts were never committed, so each defeated its own accountability purpose; the interim `.gitignore` stopgap was the wrong direction. | **Completed 2026-09-03** in `plan-tool-1` by `2-escalation-receipt-persistence.md` (4/4 steps). It becomes available to Integration only when M0 verifies it committed, pushed to `origin`, and pulled into the canonical checkout. |
| 2026-08-26 | A hand edit to a baseline-enrolled artifact permanently closes every mutation route for that stage; `--enroll-baselines` cannot re-enroll; no recovery route exists. | `roadmap-source-baseline-recovery` — **deferred 2026-08-27 (user-confirmed)**; `backlog-arc-roadmap.md` step 3 in `plan-tool-1`. This arc's M1 routes around it. |
| 2026-08-26 | Reopening an `awaiting-review` row needed a tool-driven exception. | `2-roadmap-confirmed-feedback-reopen.md` — **shipped 2026-08-27** (#315). |
| 2026-08-28 | Any artifact change invalidates all nine draft seeds at once; on a nine-row roadmap every feedback round re-queues every seed for re-review. Measured consequence: `--apply` on `integration` returns `refused` with 9 collisions and 9 `stale` drafts. | Unfiled, and the collision half is correct refuse-by-default behavior, not a defect. File the invalidation breadth in `BACKLOG.md` only if M3 on `integration-aidlc-mvp` shows it dominates review time; per-row invalidation is a design decision, not a bug. |
| 2026-08-28 | An empty `docs/implementation-plans/.roadmap-integration.writer.lock` sits untracked beside the artifacts. Verified in `roadmap_revision_publish.py`: `roadmap_writer_guard` creates it (`O_CREAT`) and never unlinks it, and `roadmap_reader_guard` *requires* it to exist ("roadmap reader requires an existing usable writer lock") — so it is the persistent advisory lock, not a leak. Integration's `.gitignore` does not name it, so every session sees a dirty tree. | Not a tool bug. Integration-side disposition at M0 step 3: add `docs/implementation-plans/.roadmap-*.writer.lock` to Integration's `.gitignore`, then confirm that a fresh clone with no lock file can still run a reader (`--view`) before relying on the ignore — if it cannot, that is a `BUG_BACKLOG.md` entry (reader guard fails closed on a clean checkout). |
| 2026-08-28 | **Brief shape determines roadmap shape, measured.** The `integration` brief's nine-bullet "should separately stage" list produced exactly nine plan rows, and its "should **also** establish the platform foundations" sentence produced a four-environment, dual-pipeline `platform-baseline` as the first, blocking row. | Not a tool defect — the roadmap faithfully executed its brief. This is a **seed-shape finding**, which is what the multi-lineage exercise is for, and it is the don't-repeat behind M2's "do not write a 'should separately stage' list": **an enumeration in the brief becomes a row count in the roadmap.** |
| 2026-08-28 | The first draft of this arc asserted that the baseline drift blocked the whole pipeline and that the one-time remedy needed an authored plan. Both were wrong: `--materialize`/`--apply`/`create` never required baseline admission, and delete-all-four + `--enroll-baselines` re-admits every stage in minutes. The error came from reading `backlog-arc-roadmap.md`'s prose instead of the code. | Not a tool finding — an arc-authoring correction, kept as a don't-repeat: **price a route by running it against a copy of the real tree, not by reading the arc that describes it.** |
| 2026-08-28 | `plan-tool` has no `--version`; the only way to know what runs against Integration is the `.pth` target plus a `git log -1` in that directory. Three checkouts diverged for a day without anyone able to tell from the CLI. | Unfiled; small `BACKLOG.md` candidate (print the source commit in `--help` or a `--version`). Decide at M0. |
| 2026-09-04 | The `project-workspace-membership-proof` feedback removes persisted project selection and updates its membership scope. Its normalized diagnostic delta reaches `relation-authority` because existing-row replacements change declared relations. | The delivered [candidate-policy review plan routes an otherwise valid, exact policy impact into the existing single-review lifecycle as an inert review-required candidate. Its replacements reuse the initial capsule and require multiplicity-preserving containment by the initial disclosure; hard refusals publish no candidate. The accepted Integration roadmap remains unchanged unless the existing exact review-seal promotion completes. This observation records provenance and does not authorize a Integration mutation. |
| 2026-09-04 | A normalized-artifact destination can reappear after bounded recovery because another process or a person writes it; a lock cannot fully prevent that human coordination problem, and a headless worker cannot ask what to preserve. | `BACKLOG.md` #353 owns a durable plan-tool contention record, pending generated payload, explicit human choice, and idempotent resume. It is parked until the narrow collision correction converges. Integration is an intended consumer; this arc does not absorb the plan-tool fix or add Integration transport/UI scope. |
| 2026-09-14 | **Closed source-admission boundary.** A recorded brief now binds its decoded text as well as its path. Changed or legacy content refuses before roadmap work; an operator may deliberately accept current text only at the same recorded path, replacing the source baseline without regenerating artifacts or altering feedback or seed state. | Semantic changes remain reviewer feedback on the owning artifact or a successor roadmap lineage. The lifecycle records redacted selection, admission, and persistence facts; it never logs brief text. Its independent review converges in `handoffs/2026-09-12-roadmap-brief-source-drift-code-review.md`. |
| 2026-09-09 | **Tool finding (capability).** Stage 2 requires one hosting row per facet and one disposition per quality attribute, and guesses when the brief is silent — the exact failure the 2026-08-24 `stage-exhausted` row records. With a structured upstream producer those facts exist in a `constraint-register.md` that has no route to the stage except being pasted into the brief. Likewise, questions the upstream engine already asked and a human already answered are re-derived here and land as `pending`. | `BACKLOG.md` #383 (per-stage supplements with declared `grounding`/`judgment` roles) and #384 (settled decisions carried in as gated `settled` rows); `backlog-arc-roadmap.md` route position 9, narrow before general. Integration's interim answer needs no tool change: an upstream `memory/phases/ideation.md` rule makes feasibility record the facts (M2). |
| 2026-09-09 | **Tool finding (consumer-driven).** No roadmap `--view` emits JSON, so a caller wanting a roadmap's *state* between runs — stage artifacts, baseline enrollment, feedback states, draft-seed classification, last outcome — must parse human output or re-implement the classifiers. Surfaced by Integration's control-plane work, where the other engine offers both an event log and a JSON status projection and `plan-tool` offers only the former. | `BACKLOG.md` #385; `backlog-arc-roadmap.md` route position 10, independent and evidence-gated — it waits on Integration actually having a connector to consume it. |
| 2026-09-09 | **Seed-shape finding.** The enumeration hazard has a new door. When the brief is composed from an upstream engine's output rather than typed, the tempting inputs are precisely the enumerated ones — a prioritized backlog of proto-Units, a stakeholder list — and pasting either reproduces the measured nine-row outcome without anyone writing a "should separately stage" list. | Owned here. The composition rule in Integration's authoring route excludes `intent-backlog.md` and the stakeholder-map body for this reason, and #383's `judgment` role is the tool-side form of the same fence: material the roadmap is measured against afterward is never rendered into a stage prompt. |
| 2026-10-13 | **Tool defect.** A `run` step whose executor stopped deliberately, changing no declared file, is reported as a test-authoring gate failure, and its stated reason is readable only with `--debug`. Seen 22 times across four Integration plans; each was a real upstream gap the executor correctly refused to paper over. | Shipped 2026-10-13: `run` reports "no edits applied" and keeps the final reply in a failure receipt (`RUNBOOK.md` § "`run` fails with \"no edits applied\""). Integration `BACKLOG.md` #5 can read the receipt's `reason` and sidecar. Routing the reason to roadmap feedback: #488. |
| 2026-10-13 | **Tool defect.** A declined feature step is reported as "marked done" before the gate refuses it, and a plan's status can flip to `completed` with steps still unrun, so each decline needs a hand reset of the plan file. | Related to `BUG_BACKLOG.md` "A `non-code` step can be marked done by `run` without editing any of its declared files" (IPPT-16), which covered non-code steps only. Superseded 2026-10-13: `run` now blocks any step whose declared files all stayed unchanged as "no edits applied", for every step type; the IPPT-16 seed and stub are retired. |
| 2026-10-13 | **Tool defect.** The test-authoring gate passes when the step's new tests could not run (the executor's sandbox had no browser), so a step reports green while its own report says 16 tests did not execute. | **Unfiled.** |
| 2026-10-13 | **Tool defect (UX).** `--debug` is a global flag and is rejected after the subcommand (`run <plan> --debug` → unrecognized arguments). | **Unfiled.** |
| 2026-10-19 | **Tool findings (capability).** Integration's Construction batch driver design infers state `plan-tool` does not record: a new plan's path (by diffing `plans.json`), a refused `create` (no run log), a gate's verdict (sidecar fields combined by assumption), each finding's triage label, and per-run usage. A sibling-plan-created path also recurs as a false audit finding in multi-plan batches. | `backlog-arc-driver-contract.md` owns `BACKLOG.md` #499, #502, #506 (#500, #501, and #505 shipped 2026-10-19); #504 (plan dependencies) is routed by `backlog-arc-roadmap.md`; the sibling-path false positive is a `BUG_BACKLOG.md` entry. |

## Decision gates

- A roadmap row that delivers a fenced capability is refused at review, not
  deferred into a later plan.
- The `integration` roadmap is not edited by hand, re-entered, or recovered without
  a fresh, user-authorized route; it is cited, not mutated.
- No writing `plan-tool` command runs against Integration from a clone; the
  canonical delivery gate applies to every session.
- A canonical `integration-aidlc-mvp` artifact is never hand-edited once its baseline
  exists; every change goes through a feedback row.
- Seeds are materialized only after the feedback rows that touch plan rows
  are closed; `--apply` only after every draft the first plan needs classifies
  `current`.
- A tool defect found here is filed where its subsystem lives before the
  session continues; this arc records only the pointer.

## Exit and handoff

The arc ends when one project has been carried through the four MVP phases in
the browser — the project created and its source retained; Ideation's concept
brief refined through chat and affirmed at a hard-stop gate; a roadmap
generated from that brief and reviewed through the candidate lifecycle with
chat-managed feedback; one plan created and audited; and one Construction exit
taken (a `jira` export of concise stories plus its paired developer handoff,
or one bounded `run` step executed by the worker returning status, revision,
and evidence) — and the lineage-state section and the findings ledger describe
that state. The next route is then Integration's own product arc, which can be
written only once this proof settles the architecture and workflow it tests.

## Out of scope

This arc does not build Integration's application code except through the plans M4
produces; does not repair or recover the `integration` roadmap; does not decide the
Jira-API, AI-DLC-compatibility-layer, AgentCore, or Integration-CLI questions the
fence defers; does not widen `HUMAN_IO_FORMAT.md` into a Integration transport; and
does not fix `plan-tool` — it points at the file that does.
