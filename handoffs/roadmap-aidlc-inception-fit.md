# Handoff: fitting roadmap to the AI-DLC workflow framework

## Status

**Exploratory design. The points under § "Settled decisions" are decided,
and one of them is also applied to `BACKLOG.md`. The generic stage-run
source-admission boundary — the strict half of change 1 — ships and its
independent review converges on 2026-09-14; it neither selects multi-source
intake nor authorizes the remaining changes here. § "Open design choices"
lists what is still undecided.** This is the approach-level design for how `roadmap` should evolve so it
behaves as a well-fitting Inception implementation inside the AI-DLC workflow
framework. It answers the earlier question of how a brief should reach
`roadmap`; that intake-ideas handoff was retired 2026-09-29, and its § "How
this re-ranks the earlier intake ideas" records what became of each idea.

The evidence base has two parts, kept separate on purpose:

- **What `roadmap` does today** comes from the six existing Integration lineages.
  Every one of them was seeded by a hand-written concept brief. None had a
  structured upstream.
- **What will cross the seam** comes from the framework's own stage
  definitions and protocols, read at commit `6849b31d` of a fork of
  `awslabs/aidlc-workflows`, and from the first real corpus the AI-DLC runtime produced for
  Integration intent `260909-integration-mvp`. Verification Gate 1 is complete and the
  runtime is parked at the first Inception boundary without producing an
  Inception artifact. Integration commit `0527be7` corrects four prose sites after
  the recorded approval, so a fresh Gate receipt must bind that commit's
  exact bytes before the corpus becomes the experiment's frozen source.

## The boundary this design keeps

Integration works under the AI-DLC workflow **framework**. It is tied to neither the
AI-DLC **runtime** nor `plan-tool`. Three layers follow from that, and each
change below states which layer it touches.

| Layer | What it is | Who owns the mapping |
| --- | --- | --- |
| Framework contract | Artifact kinds, epistemic conventions, question and review shapes, phase-boundary checks | Read by Integration's workflow profile |
| Runtime layout | Record paths under `aidlc/spaces/<space>/intents/<dir>/`, hooks, audit shards | Integration's AI-DLC connector only |
| Engine contract | What `roadmap` accepts, produces, and gates | `plan-tool` |

`roadmap` learns **generic concepts** that the framework happens to need:
typed input roles, inherited versus derived decisions, open questions,
obligations, coverage output, and a shared frame for the model requests
that can change what the artifacts mean. It never learns AI-DLC artifact kind names,
stage slugs, or record paths. Integration's connector maps framework artifact kinds
onto `roadmap`'s roles as declarative data. That matches the Integration disposition,
which assigns connectors the job of declaring "the inputs it accepts and
artifacts it produces," and it keeps the intake review's fence: no
`plan-tool` intake feature depends on AI-DLC paths or stage names.

## What the framework says crosses into Inception

These are read directly from the framework, not inferred.

**Inception's declared Ideation inputs are narrow.** Across all 33 stage
definitions, the consumers of each Ideation artifact are:

| Ideation artifact | Consumed by an Inception stage | Consumed elsewhere |
| --- | --- | --- |
| `intent-statement` | requirements-analysis, optional | several Ideation stages |
| `scope-document` | requirements-analysis, optional | several Ideation stages |
| `wireframes` | refined-mockups, required | Ideation only otherwise |
| `user-flow` | refined-mockups, required | none |
| `feasibility-assessment` | none | Ideation only |
| `constraint-register` | none | Ideation only |
| `stakeholder-map` | none | approval-handoff only |
| `intent-backlog` | none | Ideation only |
| `raid-log` | none | none |
| `initiative-brief` | none | none |
| `decision-log` | none | none |

The consequence is direct: **the framework's own Inception never reads the
initiative brief.** The brief is the Gate 1 approval artifact, compiled for a
go/no-go decision. The current `--from-existing initiative-brief.md` plan
routes `roadmap` through a document the framework itself treats as approval
evidence, not Inception input.

**Feasibility still matters to Inception, through traceability rather than
consumption.** Integration's space loads an Inception phase rule: "Every requirement
must trace back to an ideation artifact (intent, feasibility, or scope)" and
"Do not introduce new requirements in inception without documenting their
origin." So the framework expects Inception output to cite feasibility even
though no stage declares it as a consume.

**Claims carry provenance, and the framework governs how it is consumed.**
Ideation artifacts tag every claim block with its source: `[Q<n>]` for a
confirmed answer, `[desc]` for the initial description, `[scope]` for the
workflow-selected scope, `[memory:M<n>]` for a loaded rule, and
`[assumption]` for unconfirmed content. The protocol's "Consuming grounded
artifacts" rule binds every downstream stage:

- A source tag records provenance; it does not permit strengthening or
  broadening the claim.
- An `[assumption]` stays an assumption downstream until a person confirms it
  in that downstream stage's questions file.
- An assumption, open question, **unselected option**, or workflow metadata is
  never silently promoted into a requirement, scope boundary, metric, or
  constraint.
- When downstream work needs an unresolved item, the stage asks a follow-up and
  records the answer in its own questions file.

**Decisions arrive as confirmed answers, not as argued trade-offs.** Each
questions file carries options `A`–`E` plus `X. Other`, an `[Answer]:` tag,
and a `Consolidated Summary Confirmation` that a person answers
`Looks correct`. The framework records *which* option a person chose. It does
not record *why* the others lost.

**Review findings cross the seam as accepted risks with a named follow-up.**
Ideation reviews are `advisory`: one pass, findings quoted at the human gate.
Approving a gate maps every open finding to `Accepted risk` on the audit
trail's `GATE_APPROVED` row. In this corpus that happened three times, and
each finding names later work:

| Finding | Required action, as recorded |
| --- | --- |
| Intent statement R-01 | Define the measured user population, observation period, and completion target. It was directed at Scope Definition, which did not address it. |
| Wireframes R-01 | Define visible acknowledgement and processing states for chat submissions during execution, in later interaction design. |
| Wireframes R-02 | Include repository-tree loading, empty, unavailable, and stale-reference states in the refined interaction design. |

**Rules travel with the workspace, not with any artifact.** Every stage loads
`org`, `team`, `project`, and phase rule layers from the space's memory. Integration's
`project.md` now carries three corrections learned at Rough Mockups on
2026-09-11: model Integration as a dynamic workflow surface where runtime selection
belongs to each step; limit engine input to chat through the model worker with
a read-only, referenceable repository tree; and treat the streamed response
as the visible acknowledgement. These are the product's most important
Ideation insights, and they live in a rule file no Inception stage consumes
as an artifact.

**The Inception → Construction boundary checks coverage by stable ID.** The
framework checks that all requirements trace to designs, that stories trace to
requirements, that architecture covers stories, that units are defined, and
that the delivery plan is approved. It reads `traceability.json` files keyed by
stable IDs, with statuses `OK`, `GAP`, `ORPHAN`, `Deferred`, and `N/A`.

**Input change after approval is a declared policy.** The `feature` scope sets
`change_control: relaxed`: an input that changes after approval is recorded
and announced in one line, and the run continues.

## What `roadmap` does today, measured on hand-written briefs

Counting decisions across every artifact in the six Integration lineages shows three
behaviors. All three came from hand-written briefs, so they describe
`roadmap`, not the AI-DLC corpus.

- **One open question is re-decided at every stage.** In the frozen `integration`
  lineage, the ECS-versus-AgentCore choice is `pending` in all four
  artifacts. In `project-workspace-mvp`, the nine pending domain decisions
  come back as the same nine pending constraint decisions. Each stage
  guesses again and builds on its own guess.
- **A fact the brief omits gets guessed differently across runs.** Neither
  revision of the shared workspace brief states the hosting model. One
  lineage chose `silo` and marked it `pending`; the next chose `pool`.
- **One brief path held two different briefs.** Three lineages are bound to
  one path. The brief was edited between two runs on the same morning, and
  `source.json` records only the path.

The counter-evidence matters as much: the accepted membership-proof lineage
has no pending decisions in domain or constraints. **What the input settles,
`roadmap` carries.** Every failure sits in what the input left open.

## The seam as the box

Settled 2026-09-11. The seam artifacts form the explicit boundary within
which `roadmap` creates everything. They serve three purposes at once:

- **The box.** They state what may be built and what may not.
- **Translated concepts.** Their content becomes `roadmap`'s own rows, so the
  box lives inside the artifacts, where gates and reviewers can see it, not
  only in prompt text.
- **A shared frame.** The same grounding reaches every model request that can
  change what the artifacts mean, so that work stays inside the same box.

Not all seam material is box. The box is what bounds the work: the central
outcome, the scope fence, settled decisions, constraints and operating
limits, workflow rules, obligations, open questions, and assumptions. Content
is what describes the work: the intent narrative and the experience sketches.
Content reaches only the requests that need it, because some of it is
enumerable, and enumerations in `roadmap` input become row counts. Judgment
material and approval evidence stay outside both.

The box can be wrong. Inception learns things Ideation did not know, and a
request may find a box item that contradicts another, or one the work cannot
satisfy. A request that finds this raises an open question under change 4,
citing the box item. It never silently obeys a box item it believes is
wrong, and never silently works outside one. The framework works the same
way: a downstream stage asks a follow-up rather than overriding an upstream
answer. Without this, the box would turn Inception into transcription.

Today the box frames only first-run authoring. Only some model requests see
the source material at all:

| Model request | Sees the brief | Sees the smallest-proof boundary |
| --- | --- | --- |
| The four authoring stages | yes, whole | yes |
| Candidate revision | yes, inside its context bundle | no |
| Stage feedback revision | no | no |
| Local feedback revision | no | no |
| Structural revision | no; only the brief's hash, as evidence, plus the target plan's own intent and non-goals | no |
| Candidate review questions | no | no |
| Seed drafting | no; the four artifacts only | its own inline wording |

Once a baseline exists, every later change goes through the revision routes
and seed drafting, most of which never see the source. The box stops framing
the work after the first write, and the gates that remain check shape and
relations, not fit to the box. Change 8 closes that gap.

## The design

Eight changes, each tied to a framework convention and expressed in
`roadmap`'s own vocabulary. They are ordered by dependency, not by size.

### 1. A frozen source set with a declared change-control policy

- **Framework convention:** approvals bind artifact fingerprints; `feature`
  declares `change_control: relaxed`.
- **Today:** one recorded path, no digest comparison, and a measured case of
  one path serving two briefs.
- **Change:** the source record holds a set of sources, each with a role and
  a content digest, plus a root digest over the set. It binds at the first
  artifact write, reusing `roadmap_source_identity.py` rather than a second
  digest scheme. On drift, behavior follows a declared policy: `strict`
  refuses and names the two supported routes, feedback rows or a successor
  lineage; `relaxed` records the change, announces it in one line, and
  continues. The filed `BUG_BACKLOG.md` brief-drift entry becomes the
  `strict` half of this. Integration's connector also passes the upstream approval
  receipt as provenance, so the set is provably the approved snapshot.
  § "Citation snapshots" adds finer, item-level detection on top of this
  file-level identity.
- **Layer:** engine contract, plus connector-supplied provenance.

### 2. Typed source roles replace the approval memo as input

- **Framework convention:** Inception consumes artifacts by kind; the
  initiative brief is not an Inception input.
- **Today:** one prose brief for every stage.
- **Change:** `roadmap` declares input roles, and each role declares which
  requests it reaches and what epistemic class it carries. Box roles reach
  model requests through change 8's frame; content roles reach only the
  stages named:

  | Role | Carries | Reaches | Class |
  | --- | --- | --- | --- |
  | `intent` | problem, users, success signal | stages 1–4, as content | grounding |
  | `scope` | central outcome and fence | in the frame, per change 8 | grounding |
  | `constraints` | hosting facets, quality dispositions, operating limits | in the frame, per change 8 | grounding |
  | `experience` | user flows and screen sketches | stage 1 only, as content | grounding |
  | `decisions` | confirmed answers and recorded settled decisions | in the frame, per change 8 | inherited |
  | `open-questions` | unresolved upstream items | in the frame, per change 8 | open |
  | `obligations` | accepted-risk findings with a required action | in the frame, per change 8 | obligation |
  | `rules` | selected workflow rule sections | in the frame, per change 8 | grounding |
  | `approval-evidence` | the approval memo, decision log, phase check | none | provenance only |
  | `judgment` | proto-decomposition such as a prioritized backlog, and the stakeholder map | none | review-time only |

  `experience` stops at stage 1 because a screen list handed to the plans
  stage is the same enumeration hazard as a backlog: four sketched screens
  can come back as four plan rows. `judgment` and `approval-evidence` are
  never rendered into any stage prompt; the prompt boundary enforces that,
  not documentation. For the AI-DLC corpus, Integration's connector maps
  `intent-statement` to `intent`, `scope-document` to `scope`, the
  feasibility and constraint artifacts to `constraints`, `wireframes` and
  `user-flow` to `experience`, the question files and the rule layers'
  `Decided` entries to `decisions`, each artifact's open entries to
  `open-questions`, the audit's accepted-risk findings to `obligations`, the
  rule sections selected by change 6 to `rules`, the approval-handoff
  outputs to `approval-evidence`, and the intent backlog and stakeholder map
  to `judgment`. The stakeholder map is review-time only because the intent
  statement already names the users; the map's remaining row is a
  decision-maker, not a domain actor.
- **Layer:** roles are engine contract; the mapping is connector data.

### 3. Epistemic classes carried end to end

- **Framework convention:** "Consuming grounded artifacts"; the Inception
  traceability rule.
- **Today:** a decision is `settled` or `pending` with no origin; design rows
  carry no source; every decision must name a rejected alternative with a
  reason.
- **Change:**
  - Decision rows gain an origin: **inherited**, with a citation to the
    source item that settled it, or **derived**, meaning `roadmap` made it.
  - An inherited decision is `settled` by construction. A stage may anchor to
    it but may not re-decide it. Changing it is an upstream change handled by
    change 1's policy.
  - The rejected-alternative gate applies to derived decisions only. Its
    purpose is steering: it exposes the paths `roadmap` weighed while
    generating an artifact, so a reviewer can redirect the generation. An
    inherited decision was not weighed by `roadmap`, so its authority is the
    person's confirmation, cited by source. The other options in an upstream
    question are the menu the question offered, not paths anyone considered
    and rejected, and they are never recorded as rejected alternatives. An
    inherited decision carries a rejected alternative only when the upstream
    record itself states a path that was considered and why it lost, and
    then verbatim.
  - Design rows that assert a fact cite a source item or a derived decision,
    and a gate checks the citation resolves. This is `roadmap`'s form of the
    framework's traceability rule and its upstream-coverage sensor.
  - An `assumption` class carries upstream assumptions, including RAID-log
    assumptions. A row that depends on one says so, and no stage may promote
    it.
  - Workflow metadata never grounds scope. A scope, fence, or boundary row
    may cite only a confirmed answer. A workflow setting, such as the scope a
    workflow was started under, proves only that setting. Integration's corpus shows
    why the line matters: the workflow runs at `feature` scope, which marks
    every lifecycle stage for execution, while the boundary a person
    confirmed is an MVP-sized product increment. A stage that read the
    workflow scope as the product boundary would widen the product to the
    workflow's full lifecycle.
- **Layer:** engine contract.

### 4. Each open question is raised once, in the framework's question shape

- **Framework convention:** unresolved items become follow-up questions in the
  current stage's questions file; answers are confirmed, then consumed.
- **Today:** a stage guesses, marks the guess `pending`, and every later stage
  guesses again.
- **Change:** when a stage reaches a load-bearing point the source set does
  not settle, it records one open question with a stable id, options, a
  recommendation, and a blank answer. Later stages cite that id instead of
  re-deciding. A declared mode chooses what happens next:
  - `stop` ends the run cleanly after the stage that raised the question.
    Nothing hangs; the next run reads the answer, and the answer becomes an
    inherited decision citing the question id.
  - `provisional` continues on the recommendation, marks every dependent row
    as provisional on that question id, and invalidates exactly those rows
    when the answer differs.

  Upstream open questions enter the same list before stage 1 runs. Every
  entry under an upstream artifact's `Assumptions & Open Questions` heading
  other than the framework's `None.` sentinel is imported as an open
  question, unless it carries the `[assumption]` tag, in which case it joins
  change 3's assumption class. Open question is the default because an
  assumption can be silently built on, while an open question must be
  settled. The default matters in practice: the one open entry in Integration's
  corpus, in the user flow, carries no tag. It says each workflow step needs
  a well-known complete state before the next step can be offered. The
  connector finds these entries by heading: the heading must start its own
  line, and a match inside a fenced block does not count.

  Source changes raise questions through the same list. § "Citation
  snapshots" raises one for each changed cited item and each broken anchor.

  This keeps `roadmap` non-interactive in the sense that matters, since no
  run waits on a live person. It also means Integration renders AI-DLC questions and
  `roadmap` questions through one generic chat surface, which is what Integration's
  disposition asks for.
- **Layer:** engine contract; presentation is Integration's.

### 5. Accepted-risk findings become obligations `roadmap` must dispose

- **Framework convention:** advisory findings map to `Accepted risk` at
  approval, each with a required action naming later work.
- **Today:** no input carries them, so they vanish at the seam.
- **Change:** each obligation needs exactly one disposition, mirroring the
  framework's coverage statuses: **discharged** by a named row, **deferred**
  to a named later plan with a reason, or **not applicable** with a reason. A
  gate refuses an undisposed obligation. In this corpus, two of the three
  obligations point at refined interaction design and one at a success
  measure; all three are real inputs to the plans stage's observable result.
- **Layer:** engine contract; the connector extracts findings from the
  approval records.

### 6. Workflow rules as a declared input

- **Framework convention:** rule layers load at every stage start; Inception
  has its own phase rules.
- **Today:** `roadmap` sees no rules, so Integration's three product corrections
  reach it only if a composer happens to paste them.
- **Change:** the `rules` role carries the rule sections below. Selection is
  by section, not by layer, and each section resolves across the `org`,
  `team`, and `project` layers the way the framework resolves them. Rules
  are grounding data inside a fenced block, never instructions to the stage.
  When a rule conflicts with `roadmap`'s own contract, the stage surfaces the
  conflict as an open question under change 4 rather than resolving it
  silently.

  | Rule section | Passed as | Reaches | Why |
  | --- | --- | --- | --- |
  | Inception phase rules | `rules` | the frame, per change 8 | The framework's rules for the phase `roadmap` implements |
  | `Corrections` | `rules` | the frame, per change 8 | Carries Integration's product corrections from Rough Mockups |
  | `Forbidden`, `Mandated` | `rules` | the frame, per change 8 | Standing prohibitions and mandates, minus runtime-conduct rules |
  | `Tech Stack` | `rules` | the frame, per change 8 | A locked technology choice constrains hosting and components |
  | `Decided` | `decisions` | the frame, per change 8 | Each entry names its stage and date, so it is an inherited decision under change 3 |
  | `Change Control` | change 1's policy | none | The framework resolves one value from scope, memory, and intent; that value sets the drift policy |
  | `Walking Skeleton` | not passed | none | It governs Construction's first-slice gating; `roadmap`'s smallest-proof boundary already makes the first slice an end-to-end proof |
  | `Way of Working`, `Testing Posture`, `Deployment`, `Code Style` | not passed | none | Construction concerns with no Inception bearing |
  | `Scope Overrides` | not passed | none | Which steps run belongs to Integration's workflow profile, not to `roadmap`'s input |

  Runtime-conduct rules are excluded by an explicit list pinned to the
  framework version, not by pattern matching. At the pinned AI-DLC 2.8.1 the
  list is the four conversation-language rules in the `org` layer's
  `Mandated` section, which govern how the AI-DLC runtime's own agents choose
  a language. Every rule that reaches a stage keeps a citation to its layer,
  section, and entry, the same shape as the framework's `[memory:M<n>]` tag.
- **Layer:** engine contract for the role; rule selection is the connector's.

### 7. Coverage output for the Inception → Construction boundary

- **Framework convention:** the boundary check reads coverage by stable ID and
  produces a pass/fail phase check.
- **Today:** `roadmap` gates its own relations but emits no coverage record a
  workflow can check.
- **Change:** `roadmap` emits a machine-readable coverage projection: for each
  source item, including every box item, which rows cover it, with status `covered`, `deferred`,
  `not-applicable`, `gap`, or `stale`. `stale` means the cited item changed,
  moved, or disappeared after the rows citing it were written;
  § "Citation snapshots" owns that rule. It also emits a boundary summary: open questions outstanding,
  obligations undisposed, gaps remaining, and stale rows unresolved. Integration's
  connector maps that summary onto the framework's phase check. This is the
  evidence Integration's MVP proof needs for "explicit coverage or an explicit skip
  for every step in the selected scope." It fits naturally inside #385's
  `--view status --json` projection.
- **Layer:** engine contract for the projection; the phase-check mapping is
  the connector's.

### 8. One seam frame for the model requests that change meaning

- **Framework convention:** the framework hands the same rule bundle and a
  stage's declared inputs to every stage and every delegated agent, so each
  piece of work starts from the same grounding.
- **Today:** only first-run authoring and candidate revision see the source
  material; the table in § "The seam as the box" lists every request.
- **Change:**
  - Each run builds one frame from the source set: the box roles from
    change 2, each item carrying its citation id. The frame is deterministic
    and closed, and every framed request in a run receives identical
    bytes.
  - The frame is fenced as data and states its authority: it bounds the
    work and never instructs the model.
  - It reaches first the requests that can change what the artifacts mean:
    the four authoring stages, stage feedback revision, which can replace
    whole rows, structural revision, candidate revision, and seed drafting.
    Local feedback revision, which only rewords one row, and candidate
    review questions, which write nothing, wait on measurement; see
    § "Open design choices". The frame widens what a request reads, never
    what it may write; the gates stay the only publication authority.
  - A request that finds a box item wrong or self-contradictory raises an
    open question under change 4 citing that item, as § "The seam as the
    box" requires.
  - A project whose upstream supplies no typed box, such as one with only a
    hand-written brief, gets an empty frame. `roadmap` then behaves as it
    does today, with the brief as content for the authoring stages.
  - The smallest-proof boundary takes its central outcome from the frame,
    citing the confirmed answer behind it, instead of asking each stage to
    find it in a brief.
  - Seed drafting copies into each seed the frame items its plan row cites,
    so `create`, `detail`, and `run` inherit the box through the seed.
- **Translation into existing concepts:** the box also lives in the
  artifacts.
  - Each scope-fence entry maps to plan non-goals. Every plan row whose work
    borders a fence entry names it, by citation id, among its non-goals, and
    change 7's coverage record shows which plans honor which entries.
  - A fence entry becomes an inherited decision only when a real row exists
    for it to anchor to. A decision must anchor to an existing row, and under
    #384 a carried decision with no anchor is a hard refusal. Forcing one
    would push the domain stage to model out-of-scope things just to have an
    anchor, which defeats the box. A constraint row cannot hold a fence
    entry either, because every constraint must name a quality attribute.
  - A product correction in the workflow rules becomes an inherited decision
    anchored to the domain rows it governs, such as Integration's correction that
    runtime selection belongs to each workflow step. Where no such row
    exists, it stays in the frame as a rule.
  - An operating limit becomes a constraint row when it bounds a ranked
    attribute, and an assumption otherwise. A constraint cannot name an
    attribute disposed as not load-bearing, so Integration's roughly 100
    human-paced users, which bear on scalability, stay an assumption.
  - Change 7's coverage record lists every box item, so each must be
    covered, deferred, or not applicable. That makes the box checkable.
- **Layer:** engine contract.

### The Inception-step coverage decision

Separate from the eight changes, fitting the framework requires an explicit
answer for every Inception step. Integration's intent runs at `feature` scope, which
marks all 33 stages EXECUTE; reverse engineering skips only because the
project is greenfield.

| Inception step | `roadmap` today | Standing |
| --- | --- | --- |
| practices-discovery | nothing | uncovered |
| requirements-analysis | domain entities, rules, workflows; quality dispositions | partial: no testable requirement IDs |
| user-stories | nothing | uncovered |
| refined-mockups | nothing | uncovered; two obligations point here |
| domain-design | components and their decisions | covered |
| units-generation | plan rows | covered |
| contract-design | nothing | uncovered; likely applies, since plans must integrate across the web and worker units |
| delivery-planning | plan ordering and assumptions | covered |

Integration's disposition already requires each uncovered step to be closed by a
`roadmap` change or removed explicitly from the configured scope. Each row
above is that decision. It is part `plan-tool`'s, since `roadmap` could grow
the capability, and part Integration's, since the workflow profile could skip the
step. One vocabulary alignment is worth noting: `roadmap`'s smallest-proof
boundary is the framework's walking skeleton, and Integration's scope document
already answered delivery planning's first strategic question with a
risk-first order confirmed at its questions Q3 and Q4. That answer is an
inherited decision under change 3, not something the plans stage should
re-derive.

## How this re-ranks the earlier intake ideas

- **Per-stage role routing, backlog #383, becomes the primary design.** The
  framework consumes artifacts by kind, so typed roles with prompt-boundary
  enforcement fit it directly. Change 2 is #383 with role semantics taken
  from the framework's epistemic classes.
- **Typed frontmatter on one brief file becomes one possible carrier** for the
  `decisions` role, not the design itself.
- **The Integration-owned source manifest becomes the connector mapping** from
  framework artifact kinds to `roadmap` roles.
- **The brief-drift fix becomes the `strict` half** of change 1's policy.
- **Steering Ideation to record rejection reasons is withdrawn.** An
  inherited decision needs a citation, not reasons, so no Ideation rule is
  needed. Asking Ideation for reasons would manufacture rejections of options
  nobody weighed.
- **Review-time aids stay as recorded.** The dry-run view of each stage's
  rendered input becomes more valuable once inputs are role-routed.
- **Upstream-revision impact routing stays speculative,** though per-stage
  role visibility makes it concrete: a changed role maps to exactly the
  stages that can see it.

## Settled decisions

Settled 2026-09-11. Each is applied in the change named, and none is
reopened without new evidence.

- **The seam artifacts form the box.** Applied in § "The seam as the box"
  and change 8. They bound what `roadmap` creates, translate into its own
  rows where a row can hold them, and frame the model requests that can
  change what the artifacts mean. A request that finds the box wrong raises
  an open question instead of obeying or breaking it.
- **The stakeholder map is review-time only.** Applied in change 2. The
  intent statement already names the users, and the map's remaining row is a
  decision-maker, not a domain actor.
- **The decision log is approval evidence only.** Applied in change 2. The
  completed log repeats the confirmed answers in the question files, so
  rendering both would duplicate inherited decisions. Question files carry
  the `decisions` role; the decision log remains provenance for Gate 1.
- **Workflow metadata never grounds scope.** Applied in change 3. Only a
  confirmed answer can ground a scope, fence, or boundary row.
- **Upstream open questions seed the question list.** Applied in change 4.
  Untagged open entries import as open questions, not assumptions.
- **Rules are selected by section, with runtime conduct excluded.** Applied
  in change 6, including the explicit exclusion list and the routing of
  `Decided` entries to inherited decisions.
- **Cited items are snapshotted and compared on every run.** Applied in
  § "Citation snapshots". Snapshots are item-level, committed, and never
  authoritative over the upstream artifact.
- **A changed cited item uses all three mechanisms.** Applied in
  § "Citation snapshots". Its rows are marked stale, a person answers one
  question per changed item, and a revise or drop answer becomes a feedback
  row. A stale plan row blocks seed materialization.
- **A broken anchor marks its rows stale and raises a question.** Applied in
  § "Citation snapshots". A person confirms a likely move or chooses how to
  handle a lost item, and a feedback row follows only when the answer changes
  a row. Like any stale plan row, one with a broken anchor blocks seed
  materialization until resolved.
- **Uncommitted sources block the run.** Applied in § "Citation snapshots".
  A run does not start until every source in the source set is committed.
- **Whitespace-only edits count as changes, for now.** Applied in
  § "Citation snapshots". A cited item whose bytes differ only in
  whitespace is treated like any other edit. `roadmap`'s presentation-only
  tolerance for its own baselines is deliberately not reused yet; revisit it
  if upstream reformatting produces noise.
- **Inherited decisions cite their source instead of carrying rejected
  alternatives.** Applied in change 3 and in `BACKLOG.md` #384; the next
  section records why.

## Resolved: the rejected-alternatives rule in #384

Settled 2026-09-11; do not reopen without new evidence. `BACKLOG.md` #384
previously held that a carried decision's `rejected_alternatives` and
`rationale` requirements "must not be relaxed for carried rows." The
requirement exists to steer generation: a derived decision's rejected
alternatives show a reviewer which paths `roadmap` weighed while writing an
artifact, so feedback can redirect it. That purpose does not apply to a
decision a person already made upstream. The other options an Ideation
question offered are the menu the question imagined, not paths anyone weighed
and rejected, so listing them as rejected alternatives would misstate the
record.

#384 is amended to match. A carried decision cites the confirmed answer that
settled it, and the rejected-alternative requirement stays on derived
decisions. A carried decision is kept from becoming an unsupported assertion
by its citation, which must resolve to a confirmed answer inside the frozen
source set from change 1.

## Citation snapshots

Settled 2026-09-11. When a stage cites a source item, `roadmap` copies that
item's exact bytes into a snapshot it owns and references the snapshot, so a
later change to the source can be detected and shown.

### Fit with the framework

Change detection is what the framework expects. Its Change Control guide says
the setting "only decides the consequence of an input change, not whether the
framework notices it." The framework always notices. `strict` stops the run
with a sentence naming what changed and asks for approval again. `relaxed`
records the change once as a `CHANGE_ACCEPTED` audit row, announces it in one
line, and continues, leaving the approval and its evidence exactly as they
were. A consuming engine that notices upstream changes applies the same
principle one step downstream.

The framework also fingerprints at item level where it matters. A gate
approval records a separate fingerprint for each review finding it accepts as
a risk, not one digest for the whole artifact. That is precedent for
item-level snapshots.

### What a copy adds over a digest

Detection alone needs only a digest. A copy earns its place three ways:

- **It shows what changed.** A digest says only that something changed. The
  snapshot lets `roadmap` show the cited text before and after, which both
  Change Control outcomes need: `strict` has to name the change, and
  `relaxed` has to announce it.
- **It limits impact to the rows that cite the changed item.** A whole-file
  digest flags every row that cites anything in the file. An item-level
  snapshot flags only rows whose cited item changed, so an edit to one
  question does not disturb rows grounded in another.
- **It makes a stage reproducible.** Review and revision can re-read exactly
  what a stage saw, even after the source moves on.

### Where it could conflict, and how to avoid that

- **Authority.** The upstream artifact stays the source of truth. A snapshot
  records what `roadmap` consumed; no stage treats it as current once the
  source has changed. This also keeps Integration's rule that engine artifacts are
  not copied into a second store: the snapshot is the consuming engine's
  provenance, scoped to cited items, not a copy of the artifact.
- **Granularity.** Only citable items are snapshotted: a question with its
  confirmed answer, a numbered row such as a constraint or RAID entry, a
  review finding, or a rule entry. Whole files and prose paragraphs are not.
  Prose carries no stable anchor, and whole-file snapshots bring back the
  false alarms item-level detection exists to avoid.
- **Durability.** Snapshots must survive a fresh checkout, because Integration's
  managed worker runs in scoped checkouts. A local-only store would lose them,
  and detection would break without anyone noticing.

### Shape

- **Identity.** A citation names the upstream artifact kind, the stage that
  produced it, the item's anchor, and the source commit. The stage belongs in
  the identity because each stage numbers its questions from 1, so a bare
  question tag is ambiguous. A design row cites a citation id, and the index
  in the source record maps that id to its anchor and snapshot. Keeping a
  citation after a change, or re-pointing it after a move, therefore updates
  only the index; anything that changes a row goes through a feedback row.
- **Storage.** Snapshot bytes go into `plan-tool`'s existing immutable,
  content-addressed evidence store as a new namespace, committed with the
  project the way escalation receipts already are. The store already
  publishes exact bytes atomically under their SHA-256, so no second snapshot
  mechanism is needed. The lineage's source record from change 1 keeps the
  index from each citation to its snapshot digest.
- **Committed sources only.** A run does not start while any source in the
  source set has uncommitted changes. It names the uncommitted files and
  proceeds once they are committed. The check covers every source, not only
  cited items, because stages read whole role content.
- **Detection.** Each run compares every cited item's current bytes with its
  snapshot. Any byte difference counts, whitespace included. A difference
  follows change 1's policy at item level. Under `strict` the run stops and
  names the changed items. Under `relaxed` it records the change, announces
  it, and continues under the rules below. Neither policy silently re-grounds
  a row.
- **Framework linkage.** Integration's connector sets the policy from the
  framework's resolved Change Control value, so `roadmap` reacts to an
  upstream change the way the upstream workflow would.

### A changed cited item

All three mechanisms apply together, each doing a different job:

- **The coverage record marks the rows `stale`.** Change 7's record shows
  every row that cites the changed item, so nothing drifts unseen. Marking a
  row stale runs no model and rewrites nothing.
- **A person answers one question per changed item.** The question, raised
  through change 4's list, shows the old text, the new text, and the rows
  that cite it. The answer is keep, revise, or drop.
- **A revise or drop answer becomes a feedback row.** The tool writes an
  open feedback row on each affected artifact, citing the answer, and the
  existing revision route makes and seals the change. A drop removes the row
  through the artifact's `removals` record like any other removal.

A keep answer re-binds the citation to the new text in the index and clears
the stale mark; no artifact changes. Writing feedback only after a person
answers settles two concerns: the feedback row names the answer that asked
for it, and a trivial upstream edit costs one keep answer, not a model
revision. Until the question is answered and any resulting feedback is
resolved, a stale plan row blocks seed materialization, because
materializing first invalidates every draft.

### A broken anchor

A citation points at an anchor such as a question number or a constraint ID.
An upstream revision can break it in three ways:

- **Reused.** The anchor still exists but holds different content. The
  snapshot comparison catches this, and the changed-item rule above applies.
- **Moved.** The same content now sits under a different anchor, for example
  when an inserted row renumbers the rows below it. The tool finds the exact
  snapshot bytes elsewhere in the artifact and raises a question proposing
  the new anchor. A person confirms the move or treats the item as gone.
  Confirmation re-points the citation in the index and clears the stale
  mark. It never happens automatically, because identical text can appear in
  more than one place.
- **Gone.** The content appears nowhere, so the rows citing it have lost
  their grounding, which is stronger than a change. The tool raises a
  question, and a person chooses a new basis, revise, or drop. A new basis is
  another citation or a derived decision with its own rationale. Each of
  those answers changes a row, so each becomes a feedback row, and the stale
  mark clears when that feedback is resolved.

A moved or gone citation marks its rows `stale`, exactly as a changed item
does. The coverage record shows them, and a stale plan row blocks seed
materialization until the question is answered and any resulting feedback is
resolved.

Question numbers are the safest anchors; the framework's intent-capture rules
continue the numbering for follow-ups so source IDs stay stable. Register rows
such as constraint and RAID entries carry no such rule, so moves most likely
come from them.

### An uncommitted source

A run blocks until every source is committed, as § "Shape" states. A
citation records the source commit, and detection assumes that commit holds
the bytes the stage read. An uncommitted edit breaks that assumption, and the
stage might consume a draft nobody approved. Blocking also matches the intake
review's rule that the corpus is committed before `roadmap` runs. Integration's
corpus showed the gap on 2026-09-11, when its approved Rough Mockups
artifacts sat uncommitted for a time.

Two alternatives were considered and rejected:

- **Reading from the recorded commit instead of the working tree.** It
  closes the gap by construction, but it silently ignores recent edits, which
  surprises the person who made them.
- **Allowing the run and labeling the citation uncommitted.** It relies on
  the snapshot alone and weakens the record of where each citation came
  from.

## Open design choices

Recorded 2026-09-11. Each entry states what is undecided, the options, and
what it depends on. An entry marked blocked waits on the named event; the
others can be decided now.

### How RAID risks, issues, and dependencies map

**Unblocked.** RAID assumptions are settled: they join change 3's assumption
class. Risks, issues, and dependencies have no destination yet. Two options:

- **Sort them into existing concepts.** Issues become open questions under
  change 4. Risks and dependencies become obligations under change 5, each
  needing a disposition. Integration's corpus fits this: its one issue, that no
  cloud account or service is selected, is an unanswered question, and each
  risk and the one dependency names a response later work must honor.
- **Add a risk row type to `roadmap`'s artifacts.** Risks stay visible as
  risks, but this costs a schema change, new gates, and prompt changes
  across stages.

Sorting into existing concepts is the lean, since RAID IDs are citable under
§ "Citation snapshots". One piece of evidence bears on any reader of RAID
entries: the RAID log in Integration's corpus is malformed Markdown. Its header row
has six cells and its separator row has five, so a standard Markdown parser
does not recognize it as a table. Whatever reads RAID entries must tolerate
or refuse that; it cannot assume a valid table.

### How hosting and quality facts reach stage 2

**Unblocked, though one option needs an upstream revision.** No
machine-readable form of these facts exists upstream today. The hosting
facets sit in a table in the feasibility assessment, in `plan-tool`'s closed
values. The quality dispositions sit in that artifact's prose. The confirmed
answers behind both, feasibility questions Q7 and Q8, are prose too. Three
options:

- **The tool writes the rows from a fenced, machine-readable upstream
  block.** This needs an Ideation rule change. Integration's feasibility stage is
  already approved, so this corpus would need a revision under Change Control
  first.
- **The connector parses the prose table and the tool writes the rows.**
  This works on today's corpus, but it is position-based parsing of
  free-form output, which this project's conventions warn against. The
  malformed RAID table above shows the risk is real.
- **The model writes the rows, and each hosting and disposition row must
  cite its confirmed answer.** A person confirms the values at review. This
  works today with no parsing, but nothing checks the values automatically.

Whichever is chosen, the hosting and disposition rows cite feasibility Q7 and
Q8 under § "Citation snapshots".

### The question-mode default

**Unblocked.** Change 4 defines two modes for an open question a stage
raises, `stop` and `provisional`, but no default. `stop` is safer, since
nothing builds on a guess, but it ends a run at every open question.
`provisional` keeps runs moving, but a different answer invalidates the rows
built on the recommendation. Questions raised by source changes under
§ "Citation snapshots" already behave provisionally under `relaxed` Change
Control: the run continues, and stale marks contain the effect. The default
here governs the questions a stage raises about its own open points.

### How the source set reaches `roadmap`

**Decided for now (2026-09-16).** The comparison shipped #384 on the single
brief and held #383, so no carrier change is selected. It reopens only if a
per-stage grounding gap is proven. The options below stay recorded for that
case. **Was: unblocked.** The design names roles, a source record, and a citation
index, but not the input format. Three options:

- **Extend the recorded source with role-tagged sources,** the shape backlog
  item #383 already proposes.
- **A separate manifest file** named on the command line.
- **Typed frontmatter on a single composed brief,** the ideas document's
  first idea.

The format must let change 1's identity cover every source, and it must
hold the citation index from § "Citation snapshots". Extending the recorded
source is the lean, because change 1's identity and the citation index
already live there.

### What Integration's first roadmap run needs

**Blocked on the experiment in § "What stays unproven".** This choice
separates the changes that must exist before Integration's own first roadmap run
from the ones that can follow. It also covers the bootstrap. Integration's
connector does not exist yet, so something else must map the corpus for the
first run: a hand-written manifest, a script in Integration's repository, or
`roadmap` reading a generic manifest. The experiment's script-built arm is a
working prototype of that mapping.

### Framework requirement IDs

**Blocked on the Inception-step coverage decision's requirements-analysis
row.** If `roadmap` takes on requirements analysis, it needs testable
requirement IDs, because the Inception phase rules require every requirement
to have a clear pass or fail criterion. If it does not, coverage keys on
upstream source items and `roadmap` keeps its own IDs.

### How the in-scope list appears in the frame

**Unblocked.** Integration's scope document lists five in-scope items. A list in
`roadmap` input tends to come back as one row per item, as the frozen `integration`
lineage measured. Three options:

- **Render the list in the frame, labeled as bounds rather than a plan
  list,** and rely on the prompts to honor the label.
- **Keep only the central outcome and the fence in the frame,** and check
  the in-scope items through change 7's coverage record instead.
- **Render the list for stages 1 through 3,** and withhold it from the plans
  stage and seed drafting.

### How fit to the box is checked

**Unblocked.** Deterministic gates can check that every box item is covered,
that citations resolve, and that inherited decisions are unchanged. They
cannot check whether a row's meaning contradicts a fence entry. That needs a
model-based review, for example a box-conformance question added to
candidate review.

### Whether the frame reaches wording-only and read-only requests

**Blocked on the experiment's revision pass.** Change 8 frames first the
requests that can change what the artifacts mean. Two request types wait:
local feedback revision, which rewords one row, and candidate review
questions, which write nothing. Rewording can still shift meaning, so the
case is weaker, not absent. Extend the frame to them if the revision pass in
§ "What stays unproven" shows drift outside the box; otherwise leave them as
they are.

### How far the frame reaches past `roadmap`

**Unblocked.** Change 8 carries the frame into seeds. Still open: whether
`create`, `detail`, and `run` also read the seam directly, or only through
their seed. Reading only through the seed keeps the translation in one place.
Reading directly guards against a seed that dropped something.

### Frame size against byte ceilings

**Unblocked.** Some revision routes have fixed ceilings: the bounded stage
route caps its reply, and the candidate bundle caps its own size. The frame
must be counted within those ceilings or carried beside them. Excluding
narrative content keeps it small, but its size is not yet measured on
Integration's corpus.

### The Inception-step coverage table

**Unblocked.** Recorded in § "The Inception-step coverage decision". Each
uncovered step needs a `roadmap` capability or an explicit skip in Integration's
workflow profile.

## Provisional sequencing

1. Change 1, frozen source set and change-control policy. It fixes a measured
   defect and every later change depends on a stable identity.
2. Change 3's inherited-versus-derived decisions, the narrow half, delivered
   as the amended #384, together with citation snapshots, which rest on the
   same citations.
3. Change 4, settle-once questions.
4. Change 2 with changes 5, 6, and 8: typed roles, the shared frame,
   per-stage visibility for content, obligations, and rules.
5. Change 7, the coverage projection, with #385.
6. The Inception-step coverage decision can be made at any point, but must be
   made before a Integration roadmap is accepted.

## What stays unproven

The three measured behaviors come from hand-written briefs. How much of them
an AI-DLC corpus removes without any tool change is not yet measured. The
framework-conformance arguments stand on their own, since they follow from the
framework's stated rules, but the size of the benefit does not.

The A/B experiment in the ideas document should change one arm, add four
measures, and add a revision pass:

- **Replace its composed-brief arm** with a deterministic, role-sectioned
  composition of the framework's own Inception inputs: intent statement, scope
  document, wireframes, user flow, feasibility and constraint artifacts, and
  confirmed answers, with the backlog and stakeholder body excluded. Keep the
  initiative brief as the other arm. That directly tests change 2's claim.
- **Add these measures:** pending rows per distinct open question; any output
  that contradicts a confirmed upstream answer; how many of the three
  accepted-risk obligations the output addresses; and whether the domain
  keeps workflow steps generic, with the engine as configuration, as Integration's
  project rules require.
- **Add a revision pass.** After each arm's first write, apply the same
  feedback through the revision routes that do not see the source today,
  and check whether any revision moves outside the box. That measures
  whether the frame must reach the wording-only and read-only requests.

## Considered and rejected

- **`roadmap` reading AI-DLC record paths directly.** Paths are runtime
  layout, engine-resolved and able to re-root. Coupling `plan-tool` to them
  breaks the framework-versus-runtime boundary.
- **`roadmap` learning AI-DLC artifact kind names natively.** Framework
  vocabulary belongs in Integration's connector as data, so `roadmap` stays usable
  by projects with no AI-DLC upstream.
- **Running AI-DLC Inception stages for the uncovered steps.** The MVP assigns
  one engine per step and excludes AI-DLC Inception.
- **Making `roadmap` interactive.** Change 4's question artifact gets the
  framework's behavior without a run that waits on a live person.
- **A model-summarized intake capsule.** Summarization is exactly the
  compression that loses the hosting table and the product corrections. Any
  composition must be deterministic.
- **Passing the whole Ideation directory.** Already fenced by the intake
  review; memory diaries, audit shards, and question options are not co-equal
  requirements.
- **Rendering the whole brief into every request.** It would carry narrative
  and enumerable content into the narrow revision routes. Change 8's frame
  carries only the box.

## Scope fence

- The settled decisions fix parts of the design; they select no change for
  implementation. Only the #384 amendment is filed, and it changes a backlog
  entry's wording, not shipped behavior.
- No roadmap run is authorized; the intake review's preconditions still
  govern.
- The connector mapping, rule selection, and question presentation are Integration
  application work and are recorded here only as the other half of each
  change.
- The Inception-step coverage decision is shared: `plan-tool` owns whether
  `roadmap` grows a capability, and Integration owns whether its workflow profile
  skips a step.
- Anything this discussion settles for `plan-tool` is drafted as a
  `BACKLOG.md` entry in this clone, pushed to `origin`, and pulled into the
  canonical checkout before implementation.

## Next

1. Keep refining this design; only the points under § "Settled decisions"
   are conclusions.
2. Decide the unblocked entries in § "Open design choices": the
   Inception-step coverage table, the RAID mapping, the hosting-facts
   approach, the question-mode default, the source-set format, how the
   in-scope list appears in the frame, how fit to the box is checked, and
   the frame's reach and size.
3. After Integration freezes its Ideation corpus, run the revised experiment in this
   clone, then decide what Integration's first roadmap run needs and whether the
   frame reaches the wording-only and read-only requests.
4. Settle framework requirement IDs after the coverage decision.
