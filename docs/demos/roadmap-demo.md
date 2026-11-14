# TTRPG World Builder — demo orchestration runbook

Ask a coding assistant to use the plan-tool skill to turn the
[TTRPG world-builder brief](../concepts/ttrpg-world-builder.md) into a reviewed
roadmap, selected seeds and one plan with details. The scenario retains markdown
notes, visibility rules, a link graph, marginalia, maps, calendars, timelines
and two far-future AI features.

This runbook describes preparation requests, not a completed demonstration.
Retained measurements do not establish a fresh
model run, qualified audit convergence or publication approval. Use the sibling
[planning demo](planning-demo.md) for the smaller request → artifact → decision
pattern.

## 1. Demo setup and outputs

Work in an isolated consuming repository. Keep its roadmap, manifest, seeds and
plans outside the plan-tool installation checkout. Prepare transcripts, a
narrative walkthrough, a deck and an unpublished Artifact draft only when actual
run evidence supports them (§ 8). Publication requires separate authorization.

Each request below asks the assistant to link its outputs, summarize changes
and return a decision. Review selected seeds before `create`, the bare plan and
audit before `detail`, and the detail bundle and grounded audit before any next
consuming stage. Wait for a user response unless explicit prior delegation covers
that transition. Silence and elapsed time grant no approval. These are demo
review points, not new tool-enforced gates.

The [roadmap guide](../how-to/roadmap.md) owns procedure; the
[shared directives](../../integrations/shared/DIRECTIVES.md) own assistant-driven
checkpointing, audits and monitoring. Follow those owners rather than treating
this walkthrough as another procedural policy.

## 2. Why the demo repo carries a scaffold

Roadmap generation grounds in the brief; `create` and `detail` also need live
code and documentation. A thin scaffold gives them real component seams and a
green test command. Scaffold what the accepted roadmap decides; leave behavior
design to the plans. Modules represent components and frozen dataclasses carry
entity `id` fields only. Do not invent function signatures or implementation
fields in advance.

Python and pytest provide a small local scaffold without a Node dependency
install. This is a scaffold choice, not a logical roadmap decision. Preserve any
accepted stack commitments when choosing the scaffold. Actual component and
entity IDs come from accepted artifacts, never guessed names.

## 3. Phase 0 — scratch repo setup

> Prepare a disposable Git repository for the TTRPG demo, separate from the
> plan-tool source checkout. Copy the existing concept brief to
> `docs/concepts/ttrpg-world-builder.md`; ignore `.tmp/`, Python bytecode and
> pytest caches before committing. Let the tool create its own manifest.
> Link the copied brief and repository README, report the repository path and
> clean checkpoint, and ask me to correct the setup or continue to roadmap
> generation. Do not create remote refs or publish anything.

The nearest Git root scopes discovery; no registration or manually created
`.plan-tool/` directory is needed. Use specifically named local logs such as
`.tmp/ttrpg-demo.roadmap-stage-run.log`.

### Phase 0b — the scaffold, authored after accepted roadmap publication

Run this after Phase 1 exposes the accepted component artifact, never before.
The first run publishes an accepted head only after all four stages pass.

> Read the accepted `03-components` artifact through its accepted-head version.
> Propose a thin module map using its actual component and entity IDs, then bring
> the map back for review before authoring it. Keep behavior with the plans.
> After authorization, create one module per component with `COMPONENT_ID`,
> `ENTITY_IDS` and frozen entity dataclasses carrying only `id`. Use safe Python
> names, such as `chronology.py` rather than the stdlib name `time.py`.
> Link the README's module-to-component table and traceability test. Make the
> test resolve the accepted component artifact and compare the complete component
> set and every module's entity set. Mutation-check it by perturbing one module's
> `ENTITY_IDS` and separately dropping a component from the map: each must fail
> for the expected reason and pass after restoration. Report actual results and
> ask me to review the scaffold before plan authoring.

These checks are requirements for a future preparation run, not results of this
documentation conversion. Commit the reviewed scaffold before `create`.

## 4. Phase 1 — the four roadmap stages

> Use the plan-tool skill to generate the TTRPG roadmap from the copied brief.
> Monitor to confirmed completion and retain the command output and run records.
> If it stops, report its actual state without claiming a completed roadmap.
> Link the accepted version and its four artifacts when published, summarize
> decisions and unresolved questions, and ask me to review before proposing
> changes or building the scaffold.

Supporting command, from the consuming repository:

```bash
set -o pipefail && plan-tool roadmap ttrpg-world-builder \
  --from-existing docs/concepts/ttrpg-world-builder.md \
  2>&1 | tee .tmp/ttrpg-demo.roadmap-stage-run.log
```

The first stage run holds passed stages in a resume directory and publishes the
immutable version and accepted head only when all four pass. Once a head exists,
stage runs refuse; use feedback routes for changes. Roadmap artifacts are not
plans and do not enter the plan manifest.

### What to read for, per stage

> Inspect the accepted roadmap read-only first. Show its accepted version ID,
> artifact links, decision ledger, plan mapping and seed states. Distinguish
> canonical accepted content from mutable reviewer-ledger items and any inert
> active candidate. Summarize the seams below and ask which, if any, I want to
> challenge; do not submit feedback or accept a candidate from this inspection.

| Artifact | Inspect | Reader decision |
| --- | --- | --- |
| `01-domain` | Secret entity versus note field; marginalia ownership and anchors | Are the domain boundaries faithful to the brief? |
| `02-constraints` | Security priority and explicit tradeoffs for a small-group app | Do priorities reflect what the project will spend? |
| `03-components` | Visibility ownership across notes, graph and marginalia | Are seams and rejected alternatives explained? |
| `04-roadmap` | Plan IDs, cohesive outcomes, scope fences, producer/consumer ownership, dependencies and explicit AI deferrals | Does each plan have a necessary bounded outcome and an owned path to acceptance? |

Use summary, walk, ledger, index, seeds or HTML views as appropriate. The
[immutable authority contract](../../ROADMAP_FORMAT.md#immutable-candidate-version-authority)
owns selection: comparison and presentation do not accept a proposal. Prefer
actual entity IDs for downstream traceability; do not assume generated names
remain stable across independent runs.

## 5. Phase 2 — the review loop (the part worth demoing)

Keep reviewer input, candidate review and decision settlement separate. The
[ledger lifecycle](../../ROADMAP_FEEDBACK_FORMAT.md#lifecycle-and-ownership)
owns mutable input; immutable accepted artifacts are never hand-edited.

### Ledger feedback — say what is wrong and let the model propose

> Draft feedback against the accepted roadmap, using real artifact or row IDs.
> For example, investigate whether People/Place/Thing/Event make note types too
> heavy. Show me the proposed ledger target and request for correction or approval
> before submitting. After authorized submission, link the ledger item and report
> its state; ask whether to build an inert candidate from eligible feedback.

> Propose the candidate from the reviewed ledger input. Link its narrative
> evidence, stored route and selected feedback snapshot, and compare it read-only
> with the accepted head. Show the entire unpromoted stack if present. Summarize
> the changes and questions; return them for my review without accepting or
> promoting anything.

### Review the candidate by its stored route

> Follow the candidate's stored review requirement under the ledger-to-candidate
> procedure. For a nonstructural reviewed route, show the review questions and
> proposed answers before recording my responses, then return the answered seal
> for a separately authorized promotion. If any hop is structural, disclose every
> unpromoted hop and cumulative diff and ask for one approve/edit/reject decision
> on the top candidate covering the whole stack. For approval, show the first
> invocation's disclosure and exact stack digest before requesting authorization
> to confirm it. Explain that matching confirmation seals and publishes the top
> candidate. After any authorized action, link its evidence and re-read the
> accepted head so I can verify what changed.

Use [Ledger-to-candidate workflow](../../ROADMAP_FEEDBACK_FORMAT.md#ledger-to-candidate-workflow)
for bounded versus structural routes, whole-stack disclosure, digest confirmation
and recovery. A request to compare, propose or present grants no publication
authority. Editing a candidate requires fresh review; rejection advances no head.

### `pending` decisions — settle with the confirmed command

> Inspect pending decisions and identify one whose choice I can actually settle.
> Link its accepted artifact, alternatives, anchor and named live approving
> feedback evidence. Ask for my decision before running settlement; do not
> infer it from candidate review. If authorized, use the confirmed selector-based
> settlement route. If it would stale an active candidate, show the exact
> confirmation-evidence receipt and ask whether to proceed. Apply my yes/no
> response in a separate invocation bound to that receipt, then link the result
> and accepted head for review.

[Settle a pending decision](../how-to/roadmap.md#5-settle-a-pending-decision)
owns selectors and evidence; [Settlement confirmation](../../ROADMAP_FEEDBACK_FORMAT.md#settlement-confirmation)
owns receipt-bound responses. There is no prompt or `-y` substitute for that
response, and no direct edit of immutable decision status.

### Two feedback items to write, chosen to show both outcomes

Seek one accepted change and one request conflicting with a settled commitment.
Bring both back for review; neither model agreement nor refusal is guaranteed.
Capture the real exchange and candidate comparison, including a stopped or
unexpected outcome rather than inventing a successful demonstration.

## 5a. The refused feedback row — the highest-value thing to film

The useful frame is a prior commitment confronting a new request. Inspect the
predecessor before selecting the request:

> Find a real settled decision in the accepted predecessor, and link its ID,
> chosen option and anchor. If none exists, report that the demonstration lacks
> its precondition; ask whether I want to settle a genuinely pending decision
> through the separate route. Propose a feedback request that conflicts with the
> actual settled choice, such as reversing the secret entity decision or dropping
> its anchored row. Show the exact target and request for my review first.
> After authorization, submit it and propose an inert candidate. Capture the
> narrative evidence, comparison and any gate violations. Report whether the
> model preserves the commitment, a deterministic check rejects an attempted
> change, or the observed route exposes a limitation. Do not accept the candidate
> merely to complete the demonstration.

### Why the refusal is reliable, not hopeful

The deterministic property is conditional on a supplied predecessor.
[`check_settled_decisions`](../../plan_tool/roadmap_gates.py) compares settled
IDs, status, chosen option and anchor; dropping or altering them produces
`dropped-settled-decision` or `altered-settled-decision`.
`check_decision_records` requires resolvable anchors. Rationale and rejected
alternatives are deliberately outside the equality check.

A model leaving the commitment untouched is evidence of model compliance, not
an observed deterministic rejection. Record a gate rejection only if it occurs.
The [closed-vocabulary contract](../../ROADMAP_FORMAT.md#closed-vocabularies)
documents that candidate promotion supplies no predecessor to this check, making
it a no-op there. Do not claim an end-to-end promotion guarantee from these gates.

### The precondition that will bite

Without a predecessor there is no prior settled commitment to compare. Inspect
the real accepted decision and its lineage, not a guessed example ID. Pending
status alone cannot demonstrate the fence.

### The recipe

1. Review a real settled predecessor decision and its anchored design row.
2. Review and authorize the conflicting ledger request.
3. Propose and compare an inert candidate; retain actual narrative and gate evidence.
4. Present the observed outcome and enforcement limits for reader review.

There is no promised unlock or supported un-settle sequence in this demo. Do
not edit immutable artifacts or promise that repeating the request will succeed.

<a id="6-phase-3--promote-the-draft-seeds"></a>

## 6. Phase 3 — materialize and review seeds; optionally promote

> Inspect the accepted `04-roadmap` mapping and draft states, showing which
> version supplies them. Explain that a fresh roadmap has plan rows and declared
> paths but no seed files yet. Ask which rows I want materialized, then materialize
> only those eligible drafts. An active candidate must not silently supply their
> content. Link each selected seed, summarize scope, prerequisites, proof
> obligations, non-goals and Stack context, and ask for corrections or continuation.
> Wait for my review before `create`; materialization is not content approval.

> For reviewed current drafts, explain that promotion is optional and applies
> across the roadmap's promotion targets, not just the rows selected for this
> demo. Inspect the full target set and states before proposing a copy. If it
> includes unreviewed or missing drafts, report them and offer direct use of the
> selected current drafts; do not expand materialization or review without my
> authorization. Show the preview and reported destinations when promotion is
> appropriate, then ask whether to authorize the copy or use drafts directly.
> After an authorized copy, link the seeds and ordered create handoff.
> Promotion does not approve the seed content or accept a roadmap candidate.

[Promote accepted draft seeds, or create directly from them](../how-to/roadmap.md#7-promote-accepted-draft-seeds-or-create-directly-from-them)
owns materialization, reviewed digest acceptance and optional copying.
`--materialize <roadmap-plan-id>` selects an existing `plans[].id` from the
accepted `04-roadmap.md`, before its seed file necessarily exists. It does not
create an implementation plan or assign a new name. With no ID it processes
all recoverable drafts. Substitute the selected row's actual ID for the
placeholder. Later create handoffs reuse that row ID as the plan slug and use
its reviewed seed path. Take the repo-relative path from materialization or
promotion output; do not treat a slug-relative artifact path as repo-relative.
Supporting commands also include `--apply` for preview, and
`--apply -y` only for an authorized unattended copy. Choose one reviewed source
per plan: its current slug-relative draft or promoted copy. Do not hand-edit the
tool-written Stack section; change accepted commitments through feedback.

## 7. Phases 4–6 — one plan to full depth

### Choosing the plan

Prefer the notes + secrets visibility slice: it owns the brief's central fork
and supplies assumptions for graph, marginalia and timeline work. Use the actual
accepted plan ID. Ask the reader to confirm a coherent outcome and boundary
rather than forcing the illustrative name `ttrpg-note-visibility`.

### Phase 4 — `create`

> Use the plan-tool skill to create the selected plan from its reviewed seed.
> Preserve settled decisions and sibling scope fences while grounding reasons
> against live code and docs. Monitor to completion, link the bare plan and
> summarize steps, dependencies, acceptance criteria and changes from the seed.
> Run the bare audit next, then bring the plan and its audit back for review
> before authoring details.

Supporting command: `plan-tool create <roadmap-plan-id> --from-existing <reported-seed-path>`.
Substitute the selected existing roadmap row ID and its reviewed repo-relative
seed path; this command creates the implementation plan.
Create defaults to iteration; retain it.

### Phase 5 — audit the bare plan, before detail

> Run the bare-plan audit through the skill with iteration and checkpointing.
> Read the saved report and triage conceptual findings through session-directed
> judgment under the shared directives. Surface consequential scope or design decisions to me. Commit bounded
> corrections before re-auditing changed snapshots. Link the plan and reports,
> summarize changes, exact N of M detail coverage, qualification, convergence
> outcome and withheld axes. Ask for corrections or continuation and wait before
> detail authoring unless explicit prior delegation covers it.

Supporting command: `plan-tool completeness-audit <plan-id> --iterate --commit`.
Bare means at least one detail file is absent. Read findings by axis; withheld
completeness/detail apply actions do not defer material plan-body corrections.
The [audit procedure](../how-to/pipeline/audit.md) owns qualified-result
interpretation, freshness and convergence exits. Process success alone does not
certify a completed gate.

**Quota-stopped branch.** If `early_stop_reason="plan-quota"`, retain the report,
actual pass count and unconfirmed coverage. Do not apply/reuse its findings or
claim completion. Resolve the provider condition and start a fresh audit before
detail. Other unconfirmed or budget-limited results retain their reported limits.

### Phase 6 — `detail`

> After my bare-plan review, author run-grade details through the skill with
> per-step commits and default one-shot detail behavior. Run the detail-grounded
> iterative audit and judge corrections through the existing directives. Link
> the detail bundle and saved reports, summarize changes, verification guidance,
> unresolved decisions, coverage, qualification and convergence outcome. Ask for
> corrections or continuation and wait unless explicitly delegated. Stop at
> authoring; this demo does not authorize implementation or export.

Supporting commands: `plan-tool detail <plan-id> --commit`, then
`plan-tool completeness-audit <plan-id> --iterate --commit`. Do not opt detail
into iteration. A quota-stopped detail-grounded audit is also incomplete; resolve
it and rerun before describing the bundle as having passed both gates.

## 8. Phase 7 — build the four deliverables

> Once the reviewed authoring bundle has completed both audit gates, prepare the
> following local outputs from actual evidence. Link each draft, identify missing
> evidence and ask me to review before continuing. Do not invent counts, quotes
> or successful outcomes, and do not publish an Artifact or replace remote refs.

| Preparation output | Evidence to inspect | Reader decision |
| --- | --- | --- |
| Terminal transcripts | Named logs, reports, accepted IDs and actual comparisons | Is the capture complete and safe to share? |
| Narrative walkthrough | Real disposition table, feedback outcomes, plan and detail links | Does each claim match the retained run? |
| reveal.js deck | Brief → artifacts → tradeoffs → observed refusal → seeds → plan → detail | Does the presentation explain the review boundaries? |
| Unpublished Artifact draft | Reviewed narrative and stage/traceability diagrams | Correct the draft or separately authorize publication |

Prepare transcripts during the run; build the narrative, deck and Artifact draft
only after Phase 6 completes. Show the conflicting request beside the actual
unchanged commitment or rejection evidence, with its limits (§ 5a). A presentation
request does not authorize publication. Use the available Artifact authoring
procedure only when separately asked to produce that output; this conversion
creates no deliverables and publishes nothing.

## 9. Capture discipline

> Follow the shared directives for long-running commands. Report task and log
> paths, monitor to confirmed completion and share progress; do not stop a quiet
> process without my explicit permission. Keep specifically named logs and
> preserve stderr. Record actual completion and review decisions in the handoff.

For shell captures use `set -o pipefail` before `| tee` so failures remain visible.
Commit clean checkpoints before tool invocations and prefer supported `--commit`
flags as the directives specify. Retain comparisons and narrative evidence;
review logs for private material before preparing shareable outputs.

## 10. Cost, time, and what can go wrong

**Budget for:** four initial stage calls plus any retries, candidate proposals
and review edits, selected seed materialization, create iteration, both audit
gates and per-step detail authoring. Report actual usage from retained records;
do not promise fixed cost or duration. Read-only inspection and promotion copies
do not invoke a backend.

**Failure modes to expect and film rather than hide:**

| Symptom | Meaning | Move |
|---|---|---|
| `stage-exhausted` | one stage burned all 3 attempts | Each `retrying (attempt N) after <kind>` line and the final `stopped after <kind>` line already name every attempt's kind; inspect `.plan-tool/runs/<slug>/*.jsonl` for the specific violation or parse detail |
| Gate violations on retry | working as designed | This is the deterministic half of the design — worth showing, not editing out |
| All-`prioritized` stage 2 | priorities may lack meaningful tradeoffs | Review the brief; with an accepted head, use ledger feedback and candidate review rather than rerunning stages |
| Ordinary shared-budget rate limiting | short retry window | Inherited backoff handles it; do not add concurrency |
| Confirmed Cursor monthly plan quota | terminal provider condition | Return after the failed attempt; resolve the provider condition and start a fresh command, not a retry or fallback |

**Measured 2026-08-06: stage 1 exhausted on the first run and passed on the
second, and the numbers are worth knowing before you budget.** The failing run
cost ~7.5 minutes and ~$1.45 and wrote nothing. Its three attempts:

| Attempt | Kind | Cause |
|---|---|---|
| 1 | gates | `decision-secret-is-a-block` inventoried but not named in prose |
| 2 | gates | `rule-everything-stays-in-one-world` inventoried but not named in prose |
| 3 | parse | reply unparseable; only its 400-char head survives |

**Read that as a brief-size effect, not bad luck.** The successful run's
`01-domain.md` carries 23 entities, 18 business rules and 21 workflows — **62
inventoried rows**, every one of which `check_inventory_has_prose` requires be
named by id in the prose body. It is all-or-nothing across all 62, so a model at
~98% compliance still fails, and it failed on exactly one row twice. A brief
with ten feature areas should expect roughly even odds on stage 1 and budget a
retry. Trim the brief's scope if a run has to be reliable.

**Two diagnostic notes this run proved out:**

- **At the time of this run (2026-08-06), the terminal display was not the
  per-attempt record** — it could name only the final attempt's failure kind:
  this run read `(parse failure)` when two of three attempts were *gate*
  failures on an unrelated axis. The terminal now reports every attempt's
  kind via a `retrying (attempt N) after <kind>` line per retry and a final
  `stopped after <kind>` line; open `.plan-tool/runs/<slug>/*.jsonl` for the
  specific violation message or parse detail, not to learn which kind failed.
- **The unusable reply is not kept** (the open half of BACKLOG #217). Attempt
  3's parse failure is undiagnosable: 400 characters survive of a 31,858-byte
  reply. Do not plan on root-causing a parse exhaustion.

**If the review loop will not converge** — the same objection resurfacing across
re-entries, or a fix needing structural rework — stop looping and surface it
rather than iterating indefinitely. A demo that shows the honest stopping rule
is better than one that hides four silent retries.

---

## 11. What the demo deliberately does not show

- **Execution:** no `run`, `reconcile-code` or post-run code-review tail.
- **Framework lenses:** this walkthrough uses the existing four-stage route.
- **Scored decomposition quality:** gates check contracts; readers judge seams.
- **Proof of better designs:** read the [layering measurement's interpretation](../evidence/roadmap-layering-measurement.md#how-to-read-this-result)
  before citing it; it supports decision provenance rather than a design-quality claim.
- **Replacement of human authorship:** the assistant proposes, readers review,
  and the assistant returns consequential choices for decision.

## 12. Execution checklist

Preparation provenance: the retained 2026-08-06 run records these first three
items as complete (see § 10). They do not certify a fresh rehearsal; reverify
artifacts and results before presenting. The remaining entries request future
preparation, not completed work.

- [x] Phase 0 — scratch repo, brief copied and committed (retained preparation)
- [x] Phase 1 — four stages green, artifacts committed (retained second run)
- [x] Phase 0b — scaffold from stage 3, mutation-checked (retained preparation)
- [ ] Phase 1 — inspect current accepted head, artifacts and unresolved decisions with reader
- [ ] Phase 2 — review ledger request, candidate evidence and stored review route
- [ ] Phase 2 — authorize candidate decision/confirmation or seal promotion separately
- [ ] Phase 2 — inspect settled predecessor; capture actual conflicting-feedback outcome and limits (§ 5a)
- [ ] Phase 2 — if needed, authorize settlement separately, including receipt-bound response
- [ ] Phase 3 — materialize selected accepted seeds and obtain content review
- [ ] Phase 3 — review copy preview; obtain authorization for promotion or direct draft use
- [ ] Phase 4–5 — create, bare audit, then reader review of plan, reports and changes
- [ ] Phase 6 — detail, grounded audit, then reader review of bundle, reports and changes
- [ ] Phase 7 — prepare transcripts, narrative, deck and unpublished Artifact draft from real evidence
- [ ] Publication — obtain separate authorization before publishing any reviewed output
