# Documentation, demos and onboarding

Documentation accuracy, placement and readability, demos, onboarding and skill-router guidance. Each section below is one change or route in this workstream, ordered by the date it was opened; new work in the workstream appends a section here instead of creating a file (`README.md` § "Naming").

| Section | Opened |
| --- | --- |
| [developer docs and work tracking](#developer-docs-and-work-tracking) | 2026-09-14 |
| [documentation readability and onboarding](#documentation-readability-and-onboarding) | 2026-09-15 |
| [general documentation cleanup](#general-documentation-cleanup) | 2026-09-23 |
| [Demonstration refresh pickup](#demonstration-refresh-pickup) | 2026-10-21 |
| [Documentation placement review pickup](#documentation-placement-review-pickup) | 2026-10-21 |
| [Skill-led demo and example conversion review](#skill-led-demo-and-example-conversion-review) | 2026-10-21 |
| [Skill-router recipe repairs](#skill-router-recipe-repairs) | 2026-10-21 |
| [Iteration route documentation repair](#iteration-route-documentation-repair) | 2026-10-22 |
| [Run iteration guidance accuracy](#run-iteration-guidance-accuracy) | 2026-10-22 |
| [Demo workflow alignment](#demo-workflow-alignment) | 2026-10-23 |
| [Direct-edit onboarding clarity](#direct-edit-onboarding-clarity) | 2026-10-23 |
| [General onboarding documentation](#general-onboarding-documentation) | 2026-10-23 |
| [README roadmap seed handoff](#readme-roadmap-seed-handoff) | 2026-10-23 |
| [Use-case guidance correction](#use-case-guidance-correction) | 2026-10-23 |
| [Onboarding guidance entry removal: code review ledger](#onboarding-guidance-entry-removal-code-review-ledger) | 2026-11-13 |

## developer docs and work tracking

*Opened 2026-09-14.*

### Status

**Done and green; open for review as
[PR #13](https://github.com/rupe120/plan-tool/pull/13).** The work sits on
branch `docs/developer-front-door`, based on `origin/main` at `b1114783`.

The branch also carries the convergence-evaluation withdrawal described below.
The evaluator plan did not earn implementation; the convergence judgment stays
in the orchestrating session, and BACKLOG #367/#369 carry the resulting direct
authority-migration work instead.

The goal was to reshape the project docs for a team of developers who both
use `plan-tool` and use it to change `plan-tool`. The README is now a short
front door. The reference material lives in focused guides, and the backlog
rules have their own home. All of it is written in one voice (plain, to the
point, a little light-hearted, nothing lost), with the developer framed as
the guardian and mentor of the coding assistants.

### What landed

| Commit | What it does |
| --- | --- |
| `652c18e7` | Moves the README's reference sections verbatim into `docs/COMMANDS.md`, `WORKFLOWS.md`, `ITERATION.md`, `OPERATIONS.md`, `BACKENDS.md`, and `GATES.md`. Links from other docs follow; two doc-sweep tests re-point at the new files. |
| `755f6d73` | Fixes six links that were already broken in the docs the split touched. |
| `06d4cac0` | Rewrites [`README.md`](../README.md) as a developer front door. Adds [`CONTRIBUTING.md`](../CONTRIBUTING.md), [`docs/DEVELOPMENT_MODEL.md`](../docs/explanations/development-model.md), and a module map in [`docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md). |
| `9460a204` | A plain-English pass over the six reference guides. |
| `f4260749` | Retires the `completeness` command name (about 45 places) and corrects the `--iterate` defaults against the parser. Only `create` defaults on; `detail` and `completeness-audit` default off. |
| `0b9ab03a` | Files the `GateCleanCandidate` import-order test flake in [`BUG_BACKLOG.md`](../BUG_BACKLOG.md) (RISK). |
| `d222a338` | Moves about 600 lines of backlog rules into [`docs/TRACKING.md`](../docs/TRACKING.md). Adds the route, readiness, and tier labels and the tier checklist. |
| `1e6f2c79` | Replaces the never-shipped `.agents/plan-tool.sh` wrapper path with `plan-tool` (72 places). |

### How it was checked

- **Links:** a link checker covers relative paths and GitHub anchors. Every
  touched file ends with zero broken links.
- **Facts:** the voice pass was guarded by a script that compares old and new
  text. Every heading, inline code span, link target, and number had to
  survive. Test-pinned text stayed verbatim.
- **Meaning:** two independent reviews compared each rewrite with its
  original. They found five places where the meaning had drifted (for
  example, "is sound" softened to "a good sign"), and all five were reverted.
- **Stories:** the case studies in `docs/DEVELOPMENT_MODEL.md` were checked
  against their sources before being copied in. Two details were corrected
  that way, and one story was dropped because its record no longer exists.
- **Tests:** the full suite passed on every batch: 12,251 passed, 190
  skipped.

One run hit the known `GateCleanCandidate` flake. That module passes 18/18 on
its own and reads none of these docs, and the re-run passed.

### Settled in this work: don't reopen

- **AI attribution (owner, 2026-09-14).** The no-attribution rule covers
  client work only. This project is internal, so assistant commit trailers
  and provenance notes are welcome here, as `AI_SDLC_POLICY.md` describes.
  `CONTRIBUTING.md` § Commits states it.
- **Framing (owner, 2026-09-14).** The developer is the guardian and mentor
  of the coding assistants. Assistant behavior is described as plain fact
  to plan around, not as something to fight. Ordinary engineering hygiene,
  such as whole-class fixes, running tests, and small commits, isn't
  presented as new. It's written down often because assistants need the
  reminder.
- **Voice (owner, 2026-09-14).** Plain English, to the point, a little
  light-hearted, with no detail lost.
- **Self-contained docs (owner, 2026-09-14).** Anything that ships stays
  inside this repo. Examples from elsewhere get copied in with their facts;
  never link to another clone or a scratch folder.
- **Tier is a judgment, not a computation.** A keyword-based sizing of the
  backlog misjudged entries in both directions. For example, it let in #55,
  which runs into Lesson 15, and left out #266, which is a good starter item.
  Nothing derives, scores, or gates on a tier. `docs/TRACKING.md` records
  this.
- **Where test-pinned text lives now:**
  - The roadmap source-admission, structural-route, and stage-feedback
    guidance is in `docs/WORKFLOWS.md`.
  - The model-family tokens are in `docs/BACKENDS.md`.
  - The routing arcs, the Now board table, and the #328 record stay in
    `BACKLOG.md`.
  - Anyone moving that text updates the guide maps in
    `tests/test_roadmap_format.py` and `tests/test_model_specs.py`.
- **`completeness` mentions left on purpose:**
  - the persisted sidecar `kind` value;
  - ARCHITECTURE's list of the code that imports the granularity module;
  - RUNBOOK's "`completeness` primitive";
  - the dated lessons in `LESSONS_LEARNED.md`;
  - archived plans, seeds, and reports.
- **Convergence scope reset (2026-09-15, superseded by the withdrawal
  below).** This 2026-09-15 reset gated the 2026-09-14 proposal to retire
  `completeness-apply` and launch several evidence adapters together behind
  evaluator evidence (BACKLOG #367/#369). The withdrawal below returns to the
  2026-09-14 direct-retirement direction instead: `completeness-apply`,
  direct pipelines, and other application authorities are scoped for direct
  migration under #367/#369, not gated on an evaluator that did not ship.
- **Historical convergence stop (2026-09-15, superseded by the withdrawal
  below).** Three committed bare-plan audits did not converge: the
  material conceptual set moved from 6 findings
  ([16:15 report — retained historical summary](../docs/evidence/public-release-content-snapshot.md#applied-dispositions-and-retained-conclusions)),
  to 5 ([16:59 report — retained historical summary](../docs/evidence/public-release-content-snapshot.md#applied-dispositions-and-retained-conclusions)),
  then to 7 HIGH findings
  ([17:34 report — retained historical summary](../docs/evidence/public-release-content-snapshot.md#applied-dispositions-and-retained-conclusions)).
  At audit time the latest report was current but budget-limited and returned
  `no-qualified-current-evidence`. Its new requirements touch unique plan
  selection, grade-bound persistence, audit-produced direct evidence,
  protected code inputs, exclusive run-log events, and trajectory
  classification. Do not add detail files or implement the then-current plan by
  extending that list. The withdrawal below supersedes the required-decision
  state entirely. This history does not reopen or block BACKLOG #367 or #369;
  they remain separately selectable and unassigned.

- **Run-grade evaluator reset (2026-09-15, superseded by the withdrawal
  below).** V1 was narrowed to one explicit final run-grade plan-audit report
  for one uniquely resolved plan, validating only the report's canonical-plan
  and run-grade detail-bundle binding at envelope construction. This reset is
  kept as provenance for why the evaluator's judged surface had shrunk to
  almost nothing by the time it was withdrawn.

- **Second plan-audit evaluator convergence stop (2026-09-15, superseded by
  the withdrawal below).** The owner-confirmed narrow slice completed one
  structural repair round and then two manual conceptual snapshots: the
  [18:21 report — retained historical summary](../docs/evidence/public-release-content-snapshot.md#applied-dispositions-and-retained-conclusions)
  contained two HIGH gaps, while the budget-limited
  [18:42 report — retained historical summary](../docs/evidence/public-release-content-snapshot.md#applied-dispositions-and-retained-conclusions)
  contained four HIGH gaps and reported `no-qualified-current-evidence` with
  unconfirmed coverage — one interlocked fixed-judge contract (explanation
  authority, confirmed-low-yield evidence, command-bound generic
  backend/recovery policy, and exclusion of user configuration and rules).
  All four were checkable at HEAD as real code/plan defects, not model
  variance turned into prose; see the withdrawal record below for why the
  slice was withdrawn instead of fixed.

- **Convergence-evaluator withdrawal (owner-confirmed, 2026-09-15).** 25
  bare-plan audits across 2026-09-14/15 (28 plan commits, 95 findings) never
  converged: the scope moved under the audit four times — four evidence
  contexts collapsed to one, 13 steps to 8, persistent run logs to none — and
  each reshape brought new surface rather than the same gap recurring. Only
  16 of the 95 findings touched the judge seam at all (invocation profile,
  input isolation, outcome eligibility, output gate); none asked what the
  judge would conclude. The conceptual reason: after the v1 narrowing the
  eligibility gate leaves the model almost nothing to decide (at most
  `converged` vs `continue` on a qualified low-yield report with remaining
  material findings), and the orchestrating session driving `plan-tool`
  already makes that same choice with more evidence (history, live code, the
  source seed) than the evaluator's envelope permits, without stacking a
  second judge on top of the audit. This also matches BACKLOG #231's
  2026-08-19 retirement: keep the convergence pause in the driving workflow,
  do not recreate it as a persisted classifier or CLI route. The plan and its
  plan-details bundle moved to
  [`docs/implementation-plans/archive/2-orchestrator-owned-convergence-eval.md`](../docs/implementation-plans/archive/2-orchestrator-owned-convergence-eval.md)
  with a superseded banner; its seed moved to
  `plan-seeds/archive/convergence-eval-plan-audit-v1.replaced.md`. BACKLOG
  #368 and #370–#375 (evaluator adapters and governance) are retired as
  moot. BACKLOG #367 and #369 continue as the direct
  `completeness-apply`/`apply_finding` authority migration this decision also
  motivated, decoupled from the evaluator's evidence gate — see
  `docs/implementation-plans/backlog-arcs/backlog-arc-convergence-evidence.md`
  item 10 for the durable record.

### Follow-up added to the branch

- [`docs/GLOSSARY.md`](../docs/GLOSSARY.md) defines the recurring plan-tool
  vocabulary, including the difference between the convergence process, an
  automated stop, and the convergence diagnostic.
- [`CONTRIBUTING.md`](../CONTRIBUTING.md),
  [`docs/DEVELOPMENT_MODEL.md`](../docs/explanations/development-model.md), and
  [`handoffs/README.md`](README.md) make pull-request review the team checkpoint
  after local loops and give local/PR findings one durable ledger.
- [`docs/implementation-plans/archive/2-orchestrator-owned-convergence-eval.md`](../docs/implementation-plans/archive/2-orchestrator-owned-convergence-eval.md)
  and `plan-seeds/archive/convergence-eval-plan-audit-v1.replaced.md` record
  the withdrawn run-grade, explicit-report evaluator; see the withdrawal entry
  above and `backlog-arc-convergence-evidence.md` item 10. BACKLOG #367 and
  #369 retain the direct application-authority migration and inventory as
  separately selectable developer handoffs; #368 and #370–#375 are retired.
- The added internal links resolve. The fast suite passes: 11,432 passed, 158
  skipped.

### Open decisions for the owner

1. **Tracking model.** Options:
   - (A) one file per item, with a generated index;
   - (B) an external tracker only;
   - (C) a hybrid: the tracker holds status and assignment, the repo holds
     the scope contract;
   - (D) keep the single `BACKLOG.md`.

   The recommendation is A, or C if a tracker is already in daily use. D
   keeps a merge hotspot: about 14% of recent commits touch `BACKLOG.md`.
2. **Remote of record:** GitHub or Bitbucket. The PR, CI, and review
   tooling depend on the answer.
3. **Committed evidence.** Keep committing every saved report (4,334 files
   so far), or only the ones a PR or handoff cites.
4. **Code-review tail rules.** A round cap (three is suggested), reviewing
   only the new commits after round 1, and whether cleanup-only findings
   count toward convergence.
5. **Checker independence.** Whether the reviewer must be a different
   person, or can be a fresh session given only the review inputs.
6. **`CLAUDE.md` split.** Where the dated evidence moves, and who approves
   changes to the rules half.
7. **Persona tiers:**
   - tiers on work items only, or on people too (leaning items only, with
     explicit architect review on high-stakes surfaces);
   - whether to fold the readiness lens and bucket C into the readiness
     label, and whether to retire buckets A–E;
   - a minimum number of ready starter items (5 is suggested);
   - when a newcomer drives a guided plan;
   - who the first Architects are. Roughly 76 items look architect-tier by
     a rough keyword count, and today there is one Architect.
### Next actions

In rough order. Each is its own bounded piece of work.

1. **In the next clone, fetch `docs/developer-front-door` and read this
   handoff's convergence-evaluator withdrawal record. The evaluator plan is
   archived; do not revive it. BACKLOG #367 and #369 (the direct
   `completeness-apply`/`apply_finding` authority migration) remain
   unassigned until scoped. Review and merge
   [PR #13](https://github.com/rupe120/plan-tool/pull/13) when the documentation
   branch is ready** (owner).
2. **Resolve the backlog-id collision before other unpublished work lands.**
   A development clone holds unpublished entries numbered #365 and #366.
   `origin/main` already has different #365 and #366 entries. Before
   publishing that work, renumber its entries above the highest id on
   `origin/main`, and update every place that cites them, by number and by
   name. BACKLOG #233 (a duplicate-id check) would catch the next one; it's
   also a good starter item. (The check is `tests/test_backlog_ids.py`.)
3. **Tag the backlog.** Draft route, readiness, and tier labels for the 17
   bug entries (including the two filed in this work) and the 60 open direct
   entries, then have an Architect review them.
   Tidy the fields while you're there:
   - 40 entries have no `Approach:` tag, or a nonstandard one;
   - about 45 have no usable `Effort:`;
   - 11 are marked done but still listed: #181, #191, #217, #295, #305,
     #309, #331, #333, #334, #337, #351.
4. **Fix the two filed code bugs:**
   - `create` and `reprocess` still print the retired `plan-tool
     completeness` (direct);
   - the `GateCleanCandidate` flake needs its import order reproduced in a
     fresh interpreter first.
5. **Remaining documentation:**
   - **Review case studies:** tracked pages under `docs/review-case-studies/`,
     one per lesson. The sources are review ledgers kept outside this repo,
     so copy the facts in before those are cleaned up.
   - **`docs/TRACKING.md`:** its "Iterate convention" block repeats
     `DIRECTIVES.md` and has drifted. Replace it with a pointer.
   - **`DIRECTIVES.md`:** describe the code-review tail as a
     backend-neutral step with its own stop rule, once decision 4 lands.
   - **`CLAUDE.md`:** split rules from dated evidence, once decision 6
     lands.
6. **Tooling candidates.** File these as backlog entries; don't bundle
   them:
   - `--version`, or the source commit, in `--help`;
   - the tool build recorded in saved reports;
   - a CI workflow;
   - a PR template;
   - a changelog and release tags;
   - the code-review-loop skill tracked in the repo, with `install-skill`
     support.

### Things worth knowing

- **Which `plan-tool` runs.** The global command is an editable install of
  one clone, so it runs whatever that clone has checked out.
  `CONTRIBUTING.md` § "Which plan-tool is running?" shows the check. Do it
  before trusting a run that depends on a recent change.
- **A red full suite isn't automatically your change.** Read the error
  first. If it's `GateCleanCandidate` "not fully defined", it's the filed
  flake: run the module alone, then re-run the suite.
- **Doc sweeps: check the claim, not just the name.** Renaming
  `completeness` to `completeness-audit` at first kept a wrong default and
  made it look current. The parser, not the prose, settled it.

### Fence for the next session

- Don't mass-tag the backlog without Architect review.
- Don't rebase or renumber another clone's commits without the owner's
  go-ahead.
- Don't turn the tier into a computed or gating field.
- Code fixes for the two filed bugs go through their own backlog-entry
  route, not a docs change.

## documentation readability and onboarding

*Opened 2026-09-15.*

### Status

**Active follow-up to the developer-docs front door.** This handoff scopes a
systematic readability review of the project's live developer documentation.
The review will help a new contributor find the normal path, its exceptions,
and the next action without having to decode a dense prose block.

This handoff is the review record. It keeps the readability audit, fact fences,
and next actions with the change that they describe rather than adding a
standing reference document. The first batches establish the style guide,
directive, newcomer path, and task-first documentation layers. The next batch
reconciles live references to those layers on the current branch before deeper
readability review continues.

It does not reopen the documentation split recorded in
[§ "developer docs and work tracking"](docs-and-onboarding.md#developer-docs-and-work-tracking),
nor does it change product behavior. Its target is how the existing, verified
information is structured and explained.

The work is now integrated on `main`. Treat this handoff's older branch and
pre-relocation path references as history; the current documentation map owns
the live paths.

### Settled direction

- The developer documentation is an onboarding surface, not only a reference
  archive. A reader must be able to scan it before reading it deeply.
- Technical precision remains mandatory. Paths, symbols, commands, state
  conditions, ordering rules, compatibility constraints, and acceptance facts
  stay intact when prose is reshaped.
- Content will use the structure that expresses its meaning: mappings use
  tables, state-dependent behavior uses a matrix, ordered behavior uses a
  numbered flow, and exceptions follow the normal path.
- Sentence-level review will name the actor or subject of each claim and what a
  metric counts. The `docs/explanations/development-model.md` change from "per-pass counts"
  to "per-pass gap counts" is the first small example.
- **Session-directed edits (owner, 2026-09-15).** When the driving developer
  asks a coding assistant to make a judged, bounded change, call it a
  session-directed edit. The developer owns the decision; the assistant writes
  and verifies the edit. Reserve "direct edit" for the broader artifact change
  outside a `plan-tool` automatic-apply path and name genuinely human-only
  actions explicitly.
- The project directives will reinforce this quality bar, but will link to a
  focused documentation-style guide rather than becoming another long style
  manual.
- This work is distinct from BACKLOG #167. That item changes generated
  run-grade plan-detail output; this handoff covers human-authored developer
  documentation.

### Terminology sweep (cut 2026-09-15)

**Defect class:** active guidance that says an edit happens "by hand" or is
"hand-applied" hides whether the developer owns a judgment, a coding assistant
writes the change, or a human must operate an external system.

The identifier search covered `by hand`, `hand-edit`, `hand-apply`, and
`hand-run` across the live guides and driving directives. The vocabulary search
covered direct/manual/session wording at the same sites. The sweep replaces
session-driven conceptual corrections with **session-directed edit** and
generic artifact mutations with **direct edit**. It leaves literal warnings
about manually typing a Git range, and historical/archive records, unchanged.
The CLI reference and the benchmark recommendation were regenerated from their
sources. The recommendation now identifies its stored 2026-06-07 run as stale
because the current corpus changed; re-benchmark before relying on its values.

**Validation (2026-09-15):** `uv run pytest -n auto`
`tests/test_roadmap_format.py tests/test_model_specs.py`
`tests/test_completeness_report.py tests/test_convergence_diagnosis.py`
`tests/test_bench.py tests/cli/test_bench_cmd.py`
`tests/cli/test_cli_reference.py tests/cli/test_completeness_cmd.py`
`tests/cli/test_review_actions.py -q` — 1,135 passed.

### New-contributor path (cut 2026-09-15)

**Defect class:** the newcomer reading list exists, but a reader has to join
the README's contributor link with the later `CONTRIBUTING.md` role section to
recover the order and next action.

The path makes `CONTRIBUTING.md` the authority for five stages: orient, set
up and test, learn the core model, complete a starter change, and graduate to
plan-driven work. `README.md` links to that path. The existing “Getting
started” role subsection points back to it rather than duplicating its reading
list. Fact fences: each named document and anchor already exists; the direct
and plan routes retain their existing authorities.

**Validation (2026-09-15):** `uv run pytest -n auto`
`tests/test_roadmap_format.py tests/test_model_specs.py -q` — 87 passed.

### Task-first documentation layers (cut 2026-09-15; reviewed 2026-09-16)

**Defect class:** top-level pages mix a reader's next action with workflow
rationale and exhaustive contract detail, so a reader has to infer which
paragraph applies to their task.

The migration establishes `docs/how-to/` for task routes,
`docs/explanations/` for settled rationale, `docs/reference/` for exact
contracts, `docs/evidence/` for measurements, and `docs/history/` for
re-open-resistant records. [`docs/README.md`](../docs/README.md) is the map.
`README.md` starts with common tasks and links to the layers; its
assistant-role summary links to the explanation rather than carrying the full
discussion. Historical records keep their recorded paths as provenance.

**Path reconciliation (cut 2026-09-16):** the documentation map's root-level
shared operating references remain canonical. The README's twelve stale links to
relocated task, reference, contract, and evidence pages now resolve to their
current owners. The identifier search covered the former uppercase filenames;
the vocabulary search covered their reader-facing names. `CONTRIBUTING.md`,
`CLAUDE.md`, generated CLI docs, active plans, and active skills already use
the current paths or intentionally point at a root-level shared reference.
Saved reports, archived plans, benchmark fixtures, and historical handoffs
remain unchanged because their recorded paths are provenance.

**Fact fence:** each replacement targets an existing document in
`docs/how-to/`, `docs/reference/`, or `docs/evidence/`; the README keeps the
same command, lifecycle, and backend-contract claims. The roadmap-format
guard now follows the relocated Codex contract and roadmap walkthrough, and
its backlog assertions cover the current #365–#367 routing. `git diff --check`,
the stale-path search, and `uv run pytest tests/test_roadmap_format.py -q` are
clean for the active README surface.

**Front-door routing (cut 2026-09-16):** the README now begins with a task
table for installation, plan authoring, operation/recovery, exact references,
and contribution. Its new **Your first plan** route links the decision flow to
the normal workflow and the Runbook exception path. The illustrative source
tree now names the relocated pipeline guides, and the common-workflows guide
links back to that route. This cut preserves the complete workflow and contract
material below the entry route; it does not yet remove or reshape those deeper
sections.

**Command-guide routing (cut 2026-09-16):**
`docs/reference/commands.md` now routes readers from a task to its command
family and owning how-to guide before its exhaustive syntax block. The block,
flag notes, placeholder definitions, and mode contracts remain in place. The
cut also repairs the page's malformed README, CLI-reference, headless, and
plan-format links.

**Workflow-route cut (2026-09-16):** the README keeps its roadmap-specific
operator contract, then replaces the duplicated create-through-withdraw
walkthrough with a task table that points to the owning pipeline, audit, run,
gates, and command guides. The table makes the reconcile direction explicit:
pre-execution `reconcile-plan` edits the plan from code, while post-execution
`reconcile-code` edits code from the plan. The roadmap-format guard now ends
its README route section at the replacement's **Plan workflow** boundary.

**Entry-route wording (cut 2026-09-16):** nine live guides retain their useful
README or first-plan route but drop the redundant “Part of the plan-tool docs”
prefix. The development-model route now has a valid Markdown target. This is a
wording-only sweep; it changes no guide authority or task route.

**Documentation-only relocation (cut 2026-09-16):** the demo and use-case
guides now live in `docs/how-to/`; lessons learned lives in
`docs/explanations/`; and the human-input protocol lives in
`docs/reference/contracts/`. Live documentation, backlog, seed, and test
references now use the new paths. Historical handoffs and archived plans retain
their recorded root paths as provenance.

**Policy relocation (cut 2026-09-16):** the draft AI-assisted-development
policy now lives in `docs/reference/` and is indexed with the other exact
reference material. Its contributor and README links follow the new path.

**Starting-point recipes (cut 2026-09-16):** the README decision table now
links every starting point to a concrete command and short outcome in
`docs/how-to/choose-a-starting-point.md`. The how-to index routes authoring
readers there before the normal workflow. The README remains a chooser; the new
guide owns the copyable examples and route-specific next action.

**Chooser expansion (cut 2026-09-16):** Tracking, Gates, Operations, and
Iteration now begin with task-to-action tables. Each table links a reader to
the existing section that owns the detailed contract, rather than repeating
the route's exceptions or mechanics.

### Scope

Review the live developer-facing surface first:

- `README.md`, `CONTRIBUTING.md`, and `docs/explanations/development-model.md`;
- `docs/ARCHITECTURE.md`, `docs/reference/commands.md`,
  `docs/how-to/common-workflows.md`, `docs/ITERATION.md`, `docs/GATES.md`,
  and `docs/TRACKING.md`;
- the glossary and the developer-facing portions of `CLAUDE.md` that direct
  documentation work.

Do not bulk-rewrite archived plans, saved reports, historical handoffs, or
immutable evidence. Those remain readable where practical, but their
provenance and exact historical wording take priority. Do not alter generated
plan-detail prompts or quality checks under this handoff; route that work to
#167.

### Delivery sequence

#### 1. Establish the standard

Create a short `docs/reference/documentation-style.md` with examples of the preferred
shapes and a review checklist. Add a compact directive in `CLAUDE.md` that
requires the guide for developer-facing documentation changes. The directive
will say the rule; the guide will carry its examples and exceptions.

The standard will require each section to state its purpose or conclusion
before code anchors and implementation detail. It will require a writer to
separate the normal path from exceptions, use headings for independent
contracts, and choose tables or flows when the content is a mapping or
sequence. A long paragraph is a review signal, not a mechanically forbidden
form: a cohesive explanation may remain prose when a table or split would hide
its logic.

#### 2. Make an audit before rewriting

Record one row per reviewed section in this handoff, or in a successor review
ledger when a later batch needs its own record. Each row will name:

| Field | Record |
| --- | --- |
| Reader and task | Who reads it and what they need to accomplish. |
| Current role | Orientation, workflow, reference, policy, or historical evidence. |
| Finding | `keep`, `reshape`, `relocate`, or `clarify`, with the concrete obstacle. |
| Intended shape | Short overview, table, state matrix, numbered flow, example, or link out. |
| Fact fence | Commands, anchors, terms, and tests/document checks that preserve meaning. |
| Disposition | The planned batch or a reason the section remains unchanged. |

`keep` is a useful result. The audit does not create a duty to rewrite every
file or flatten every technical explanation.

#### Current audit ledger (2026-09-16)

This first ledger covers the high-traffic sections that route the four reader
journeys. It records the next bounded rewrite rather than treating the audit
as approval to reshape every section at once.

| Reader and task | Current role | Finding and intended shape | Fact fence | Disposition |
| --- | --- | --- | --- | --- |
| New contributor: choose a route and install | `README.md` front door, decision flow, install | `reshape`: a task-first table and short first-plan route now precede the complete workflow material. | Command names, decision-flow outcomes, install commands, format ownership, roadmap route. | Front-door routing cut 2026-09-16; deeper duplication remains a later batch. |
| Operator: run or recover a plan | `README.md` common workflows, headless, recovery, iteration, gates | `relocate` and `reshape`: the duplicated create-through-withdraw walkthrough is now a task map; focused guides own its operational depth. | Every command, flag, gate order, failure exit, recovery pointer, and reconcile direction. | Workflow-route cut 2026-09-16; headless, recovery, iteration, and gates remain separate future reviews. |
| Contributor: make a first change | `CONTRIBUTING.md` new-contributor path and develop/test | `keep`: the five-stage path already names the next action and owners. Review only links and terminology when its authorities move. | Five stages, test commands, work-selection and direct-versus-plan boundaries. | No prose change planned. |
| Contributor: drive or review a change | `CONTRIBUTING.md` direct/plan, completion, review, and docs sections | `reshape`: the normal change path is clear, but its review and role alternatives need a compact normal-path-to-exception bridge. | Audit gate, commit rhythm, reviewer roles, pull-request checks, documentation-style authority. | Contributor-workflow batch. |
| Contributor: understand why the workflow exists | `docs/explanations/development-model.md` | `keep`: the explanation uses a conclusion-first narrative and separates the roles, loops, evidence, and examples. | Guardian/mentor distinction, three roles, gap-count terminology, evidence claims. | No prose change planned. |
| Developer: find module ownership | `docs/ARCHITECTURE.md` module map and subsystem entries | `clarify`: retain the map and one-owner-per-section contract; split unusually dense subsystem paragraphs only when their independent rules cannot scan together. | Module names, import directions, public seams, command ownership, referenced contracts. | Subsystem-by-subsystem future batches. |
| Developer: understand audit ownership and coverage | `docs/ARCHITECTURE.md` Correctness gates | `reshape` complete: overview, ownership table, bundle-state matrix, audit/apply authority, parallel flow, and orchestration boundary now expose the normal route before exceptions. | Gate owners, bare-bundle withholding, conceptual-source authority, parallel replay order, CLI seam. | Pilot complete; revisit only for behavior changes. |
| Operator: find a command or exact option | `docs/reference/commands.md` | `reshape`: a compact task-to-command map now precedes the syntax and flag exceptions. | Generated CLI source, command spellings, deprecated-direct warning, placeholder rules. | Command-guide routing cut 2026-09-16; revise deeper flag notes only with their owning contracts. |
| Operator: select a pipeline stage | `docs/how-to/common-workflows.md` | `keep`: the numbered stage order and per-stage headings already match the task. Reduce duplicated overview only when the README route changes. | Stage order, commands, roadmap exception, audit and run gates. | No prose change planned. |
| Developer/operator: assess iteration and gates | `docs/ITERATION.md` and `docs/GATES.md` | `clarify`: both own state-dependent policy and need matrices for default/optional/exception behavior where prose currently mixes them. | `--iterate` defaults, termination and checkpoint rules; reconcile direction, gate ownership, completeness boundary. | Gates-and-iteration batch. |
| Contributor: create and maintain work records | `docs/TRACKING.md` | `reshape`: the lifecycle is a flow, but the direct-versus-plan boundary, scope contract, and authoring commands interrupt it. Put the normal lifecycle first and move detailed fences into linked subsections. | Entry labels, file-selection rule, scope contract, canonical-direction rule, command sequence. | Tracking batch. |

#### 3. Prioritize reader journeys

Order fixes by the newcomer tasks they unblock:

1. Find out what `plan-tool` is, how to install it, and where to begin.
2. Run or review a plan safely, including how gates and exceptions work.
3. Change `plan-tool` itself without confusing descriptive architecture with
   mandatory project rules.
4. Find ownership, tracking, and escalation routes.

Start with high-traffic dense sections. `docs/ARCHITECTURE.md`'s
**Correctness gates** section is the pilot: it currently combines gate scope,
module ownership, bare-plan state, audit/apply authority, and parallel replay
in one block. Reshape it into a concise overview, ownership table,
coverage-state matrix, and short subsections for audit authority and parallel
application. Use the result to calibrate the style guide before expanding the
same pattern elsewhere.

#### 4. Revise in bounded, fact-preserving batches

Use one reader journey or closely related document group per reviewable batch.
Before editing, enumerate every repeated rule by identifier and vocabulary;
update the class or record why a site differs. Preserve test-pinned wording or
update its owning test map deliberately. Keep the existing link checker and
factual-anchor checks in the validation set, and add focused checks only where
the new document structure creates a stable contract worth pinning.

Do not use a global word-count gate or a mechanical paraphrase pass. Automated
checks may report candidate paragraphs for review, but reviewer judgment will
decide whether density is necessary to state one cohesive contract.

#### 5. Validate as onboarding material

For each batch, ask a reviewer with fresh context to follow the intended
reader task using only the edited documents. Record where they cannot find the
normal path, an exception, ownership, or a next action. Resolve material
findings before calling the batch ready. The team's general decision about
reviewer independence remains open; fresh-context review is the minimum for
this work until that decision lands.

End with one cross-document walkthrough of all four reader journeys. Confirm
that document links, terminology, and authority boundaries agree across the
journey rather than only inside a single file.

#### 6. Make the standard durable

Add a documentation-readability item to the pull-request review checklist.
An advisory helper may flag unusually long prose blocks after a baseline
exists, but it must not reject precision-heavy reference material solely by
length. Revisit the audit on future major documentation changes and extend it
only to new live developer-facing material.

### Acceptance criteria

- The style guide and compact directive give contributors a concrete,
  non-mechanical standard for scan-first developer documentation.
- Every in-scope document section has an audit disposition, reader task, and
  fact fence.
- The pilot section demonstrates the standard without losing any current
  correctness-gate behavior or module ownership facts.
- Each changed batch preserves valid links and passes its applicable
  documentation and test checks.
- A fresh-context review can complete each named reader journey and identify
  normal paths, exceptions, and next actions from the documents alone.
- The pull-request checklist makes readability an ordinary review concern.

### Open decisions

1. Does the audit and pilot stay with the front-door pull request after review,
   or move to a follow-up branch before requesting review?
2. Does the team adopt the existing suggested three-round code-review-tail cap
   and reviewer-independence policy before this work starts, or use the
   fresh-context minimum stated above?

### Next action

1. Run a fresh-context walkthrough of the newcomer and operator routes using
   the README, `CONTRIBUTING.md`, and the task-first documentation map.
2. Review the remaining README headless, recovery, iteration, and gates sections
   as separate task routes; do not merge their exception contracts into the
   first-plan overview.
3. Add the readability item to the pull-request checklist after the walkthrough
   identifies the practical review prompt.

## general documentation cleanup

*Opened 2026-09-23.*

This tracks documentation hygiene that belongs to no feature: what is queued,
what is undecided, and what a future session must not "fix". Delete an item when
it closes. Work that has an owner and a fence lives in the backlog; this file
is the index that keeps the loose ends in one place.

### Queued

| Item | Where it is tracked | Next step |
| --- | --- | --- |
| Broken relative links in `RUNBOOK.md` and three dated handoffs | `BACKLOG.md` #426 | Repoint 13 links; decide two with no identified successor. |
| A link-check test | Not filed | Owner decides whether to file it as its own entry (see below). |
| Jira docs vs the real `IPPT` project | [`docs/how-to/jira-management.md`](../docs/how-to/jira-management.md) | Seed the first tickets. |
| `CLAUDE.md` evidence extraction | `tracking-and-jira.md` § "Team handoff: tracking-model decisions and remaining work" § 6 | Move the multi-paragraph measurements to `docs/evidence/`; keep the rule and a short verdict. Needs Architect review. |
| Bucket C to readiness, per entry | The same handoff, decision 7 | Check each entry the "Readiness lens" section once called bucket C against its actual readiness label. |
| Route, readiness, and tier labels | `docs/TRACKING.md` § "Labels every entry carries" | Count coverage with `grep -c '^- \*\*Route:\*\*' BACKLOG.md` (likewise `Readiness:` and `Tier:`) against `grep -c '^\*\*#[0-9]* — ' BACKLOG.md`. Tag an entry when someone next touches it. |
| One stale citation in a roadmap plan detail | The 09-17 handoff, "for the roadmap owner" | `docs/implementation-plans/archive/plan-details/roadmap-decision-settlement/07-document-settlement-route-retire-every.md` line 77 cites `BUG_BACKLOG.md:275`. Fix it at that plan's next re-audit: editing the detail makes its saved reports stale. |

### Broken relative links: the scan

The scan finds **142** broken relative links in tracked markdown. Only 13 are a
defect that is in scope to fix now.

| Count | Where | What it is | Action |
| --- | --- | --- | --- |
| 81 | 17 plan and plan-detail files under `docs/implementation-plans/` | Frozen once audited. Not classified further. | Leave. Editing one makes its saved audit reports stale. |
| 26 | `tests/fixtures/reformat/` (2 files) | Fictional links in test input. | Leave. |
| 12 | The four `SKILL.md` copies, all to `DIRECTIVES.md` | **Not broken.** `plan-tool install-skill` writes `SKILL.md` and `DIRECTIVES.md` into one directory, so they resolve once installed. | Leave. Repointing them would break them there. |
| 10 | `RUNBOOK.md` | Docs renamed or deleted by a docs restructure. Eight have a likely new home that exists; two have none identified. | `BACKLOG.md` #426. |
| 8 | Two archived design plans under `docs/design-plans/archive/` | Frozen. | Leave. |
| 3 | Two dated handoffs | Docs renamed to `docs/explanations/`. | `BACKLOG.md` #426. |
| 2 | `lessons/general.md` | Fictional examples (`app://nope`, `other.md#slug`), not links. | Leave. |

The scan reads every tracked `*.md` outside `docs/implementation-plans/archive/`,
`plan-seeds/archive/`, `.plan-tool/`, and saved `reports/`, drops fenced code
blocks, and resolves each markdown link target that is not `http`, `mailto`, or an
in-page anchor against the file's own directory:

```python
import os, re, subprocess
files = subprocess.run(["git", "ls-files", "*.md"], capture_output=True, text=True).stdout.split()
skip = ("docs/implementation-plans/archive/", "plan-seeds/archive/", ".plan-tool/")
fence = "`" * 3  # built, not written, so this block holds no fence characters
fenced = re.compile(re.escape(fence) + ".*?" + re.escape(fence), re.S)
broken = []
for f in files:
    if f.startswith(skip) or "/reports/" in f:
        continue
    text = fenced.sub("", open(f, encoding="utf-8", errors="replace").read())
    for m in re.finditer(r"\]\(([^)\s]+)\)", text):
        target = m.group(1)
        if target.startswith(("http", "mailto", "#", "<")):
            continue
        path = target.split("#")[0]
        if path and not os.path.exists(os.path.normpath(os.path.join(os.path.dirname(f), path))):
            broken.append((f, target))
print(len(broken), "broken relative links")
for f, target in broken:
    print(f"{f}: {target}")
```

### A link-check test: undecided

The same defect (docs moved or renamed, citers not swept) recurs: it has hit
`BACKLOG.md`'s links, the decisions log and two handoffs, and one live doc. A
test would catch the next one. A project rule says one
Outcome per entry, so it would be its own backlog entry, not part of #426. It
must treat three groups as exceptions, or it starts red at the baseline above:
the installed-layout links in the `SKILL.md` copies, the fixtures, and the frozen
plan and plan-detail files. Nothing is filed; the owner decides.

### Jira docs vs the real project

`docs/TRACKING.md` § "Jira board" describes the board, and
[`docs/how-to/jira-management.md`](../docs/how-to/jira-management.md) owns the
ticket seeding.

### Settled: do not reopen

- The `DIRECTIVES.md` links in the `SKILL.md` copies are correct as installed.
  A link scan flags them; they are not defects.
- Frozen plan and plan-detail files are not edited for link hygiene.
- A dated handoff may take a path-only repoint when the owner asks. Nine links in
  two handoffs have had one.
- `BACKLOG.md` #191 and #217 look stale but are not: each describes genuinely open
  remaining scope (half shipped, with a "what remains" section). Leave them.

## Demonstration refresh pickup

*Opened 2026-10-21.*

The assistant-led guides and authored reading samples cover the retained
dark-mode and TTRPG scenarios. All four plan steps pass their full test gates.
The bounded live dark-mode planning/local-export rehearsal completes with
confirmed, current advisory-only audit results and passing story lint. It does
not implement the feature or verify browser behavior. Remote checkpoint
publication remains pending and requires separate authorization through the
[release handoff](release.md#public-onboarding-and-release-pickup).

The [verification record](../docs/evidence/skill-led-demo-examples-verification.md)
owns snapshot identities, stage outcomes, the recovered child permission failure,
artifact hashes and remaining verification limits. Documentation readiness,
a bounded rehearsal and remote publication are separate results.

Keep `demo/1-seed`, `demo/2-plan`, `demo/3-detail` and `demo/4-jira` on both
Bitbucket and GitHub. The [sanitized publication record](release.md#sanitized-release-publication-pickup)
records their shared needs-updating notice. Private recovery bundles retain the
previous staged contents; local fixture tips below are not approved replacements.

### Current plan pickup: use the plan-tool skill

[Teach demos and examples through the plan-tool skill](../docs/implementation-plans/archive/2-skill-led-demo-examples.md)
provides the maintained walkthroughs and learning entry points. All four steps
are done. The launcher owns plan status and the post-flight checks. Do not
re-author the seed, restart the conversion or repeat the completed rehearsal
merely because the original nested step could not initialize Codex.

The [implementation review ledger](docs-and-onboarding.md#skill-led-demo-and-example-conversion-review)
records two independent clean documentation reviews and the final passing suite.

Next pickup: read the final reconciliation/review evidence and prepare a bounded
implementation pull request when authorized. The documentation plan's code
reconciliation sweep reports no eligible code steps because all four are
explicitly non-code; independent documentation review supplies the accuracy
check. Follow the [shared directives](../integrations/shared/DIRECTIVES.md).
Remote demo ref replacement remains a separate reviewed action.

#### Plan scope and user review

Dark mode remains the planning scenario; TTRPG remains the advanced roadmap
scenario. TTRPG receives contract review here, not full regeneration.
No CLI, skill, schema or monitoring changes belong to this effort.

The guides ask the assistant to link actual artifacts, summarize changes and
ask for corrections or continuation at seed, bare-plan/audit and detail/audit
boundaries. Wait for the user's response unless explicit prior delegation covers
the transition. Export requires its separate request after detail review.
The verification record distinguishes the narrative review checkpoints from
assistant-reviewed artifacts in the owner-authorized batch rehearsal. It does
not claim a person separately approved each generated rehearsal artifact.

#### Authoring evidence and audit trajectory

Dated plan-authoring provenance, 2026-10-21: the plan's bare and detailed audit
reports record the following snapshots. These audit this documentation plan,
not a consuming-repository dark-mode rehearsal.

| Snapshot | Coverage and retained conclusion | Report |
| --- | --- | --- |
| Bare | 0 of 4; clean, confirmed; detail/completeness apply withheld | [23:38 report](../docs/implementation-plans/archive/plan-details/skill-led-demo-examples/reports/20261021-233834-completeness.md) |
| Initial detailed | 4 of 4; clean, confirmed; superseded by user-review amendment | [23:44 report](../docs/implementation-plans/archive/plan-details/skill-led-demo-examples/reports/20261021-234419-completeness.md) |
| Amended detailed | 4 of 4; clean, confirmed; zero blocking/deferred findings | [23:47 report](../docs/implementation-plans/archive/plan-details/skill-led-demo-examples/reports/20261021-234705-completeness.md) |

The original authoring handoff records 14,698 passed and 66 skipped in 62.83s.
That dated result does not replace the launcher's current post-flight result or
verify the live demo. The [archived source brief](../plan-seeds/archive/skill-led-demo-examples.replaced.md)
and retained reports provide durable authoring provenance; transient logs are
not required to read the current guides.

### Local candidate

Dated preparation provenance, 2026-10-21: the following describes the original
local candidate snapshot. Its scratch repository and receipts are absent in
this clone; none of these checks is a fresh verification.

The local review repository is `.tmp/public-release-demo-refresh-v2`. Its bundle
is `.tmp/public-release-demo-refresh.bundle`, and its machine-readable ref and
verification receipts are `.tmp/public-release-demo-refresh.refs.json` and
`.tmp/public-release-demo-refresh.verification.json`. These files are local
preparation artifacts, not remote refs. Copy the private recovery bundle named
in the release handoff to durable private storage before replacing remote refs.

| Ref | Local target | What it presents |
| --- | --- | --- |
| sanitized root | `949e6dd5e8c093e7c073e004d468eb022a15484c` | 2,608 selected paths from source `256f466380dda423117273da0ed69735048474d3` |
| `main` | `d8aa550190c8a2cc3cf3d5284d385e30633b4231` | Release 0.2.0 metadata and collected changelog |
| `v0.2.0` | annotated tag object `4a534a841c7b3daaa0fe8e60ec4916da0c28c2f9` | Points to the local release commit |
| `demo/1-seed` | `9ff9e70e6f1ff15e66f56b9155e7f6fb751c7733` | Scope-fenced brief with the required References section |
| `demo/2-plan` | `6e22cdd88dbe1f7ad71e46ca8dba3264b98b9842` | Current-format plan with intent, three steps and test footprints |
| `demo/3-detail` | `d1bde66e824430b907d9fb7db7bd59b9facaf274` | Three run-grade detail files |
| `demo/4-jira` | `c563f3202885c54e3dee0e18faeb7872c4103870` | Local story export and paired developer handoff |

The demo commits form one direct chain above `main`. The repository has one
parentless root, no remotes or alternates, and no old source commits reachable
from its refs. The bundle verifies and `git fsck` passes. The old `v0.1.0` tag
is retained in private recovery material and remains unchanged on both hosts.
The 2,608-path base includes the primary documentation-folder
READMEs and the documentation placement handoff. Its path and content digests
are recorded in `.tmp/public-release-demo-base.verification.json`. The earlier
2,601-path [final-selection receipt](../docs/evidence/public-release-final-selection-verification-20261021.json)
continues to describe its own frozen candidate, not these later bytes.

### Verification and presentation boundary

Dated original-preparation provenance, 2026-10-21: the earlier fixture candidate
parsed and carried supported detail markers; its local story lint returned three
advisory size warnings (3h, 2h, 2h). The prepared cards labeled fixture input.
Its isolated full suite recorded 14,698 passed and 66 skipped in 58.00s. These
facts describe the local candidate table above, not the newly captured one-step
live rehearsal, and do not certify the current remote checkpoint contents.

### Remaining demo verification and publication

1. Review the current implementation changes and their completed-plan evidence.
   The child initialization restriction is resolved by parent-session access;
   planning, both audit stages, paired local export and lint have captured results.
2. If preparing a presentation, choose captured material deliberately. The
   bounded dependency-free rehearsal verifies the maintained workflow; it does
   not replace the private React fixture chain or refresh remote checkpoint tips.
3. Recheck local checkpoint refs, stage differences, private recovery bundles and
   old remote tips before proposing replacements. Preserve the four checkpoint
   names and distinguish captured output from authored reading samples.
4. Obtain separate review and authorization for remote demo ref updates, then
   read both hosts back. Main, tags, visibility and organization transfer remain
   with the release workflow. No fresh TTRPG run or browser interaction is claimed.

Use [the planning guide](../docs/demos/planning-demo.md) for the workflow and
[the documentation placement handoff](docs-and-onboarding.md#documentation-placement-review-pickup)
for the primary-folder review record. No remote publication is performed here.

## Documentation placement review pickup

*Opened 2026-10-21.*

Primary documentation folders have purpose READMEs; per-plan detail, report and
other artifact folders retain their existing format contracts. The documentation
map routes session progress to `handoffs/`, general task procedures to
`docs/how-to/`, and demo walkthroughs and presenter runbooks to `docs/demos/`.

### Review scope and result

All 18 how-to pages are screened by purpose, headings, introductions and searches
for session status, pending work and dated assumptions. This is a placement and
initial-workflow review, not a fresh audit of every CLI flag or source-map line.

- The demo update checklist lives in § "Demonstration refresh pickup", outside how-to.
- `docs/demos/README.md` is the demo entry point. The planning demo and roadmap
  demo runbook live beside it. The planning demo needs updating before its next
  presentation; its refresh remains deferred. The former roadmap-demo location
  is a routing page so retained plan and audit citations continue to resolve.
- Installation guidance handles credentials/source movement conditionally.
- Branch-awareness states the current opt-in behavior without a former-state comparison.
- Common workflows and the audit introduction name both audit gates. The common
  workflow no longer calls missing bare-plan details a design defect. The audit
  diagram distinguishes deterministic edits from conceptual session judgment.
- The roadmap demo keeps its repeatable setup/output contract; per-session owner
  narration is removed. Runtime `pending` states, recovery instructions and dated
  measurements remain where they explain correct operation.

### Verification and next action

All 12 primary `docs/` folders have a README; the new READMEs and updated
navigation resolve their relative file targets. No new README is added beneath
plan-details, reports, archives or individual evidence bundles. The generated CLI
index remains unchanged. Focused locator, generated CLI-reference and backlog-readability checks pass:
120 tests in 0.75 seconds. Reviewed how-to file targets resolve. Continue release
preparation independently of the deferred demo refresh. These selected-document
edits require a new candidate verification before publication; the earlier frozen
2,601-file root remains a measured checkpoint.

The demo relocation passes relative-link checks and all 53 roadmap-format
tests. The removed-route documentation guard follows the roadmap demo to its
new location. Root and documentation indexes expose the demo entry point.

## Skill-led demo and example conversion review

*Opened 2026-10-21.*

| Field | Record |
| --- | --- |
| Plan | [Teach demos and examples through the plan-tool skill](../docs/implementation-plans/archive/2-skill-led-demo-examples.md) |
| Base | `80dfaa78e8ff95d1528a581e4fb10fba6ecc0b27` |
| Reviewed implementation snapshot | `81a83f5bb0409e58150c703a0d6add8ef381d133` |
| Branch | `implement/skill-led-demo-examples` |
| Checks | Four full-suite step gates pass; final suite: 14,698 passed, 66 skipped in 71.48s; 290 local file targets and 201 fragment targets resolve; fixture parser/round-trip checks pass |
| Reviewers | Two independent Codex `gpt-6.1-sol` report-only sessions, read-only sandbox |
| Disposition | Documentation review converges: two consecutive independent passes report no material findings; implementation and bounded live rehearsal complete |

### Scope and settled boundaries

The change retains dark mode and TTRPG, keeps CLI procedures as supporting
references, and teaches assistant requests for grounded seeds, monitoring and
result review. Seeds, bare plans/audits and details/grounded audits receive
explicit user review before the next consuming stage unless explicit delegation
covers continuation. Silence is not approval. All four plan steps remain
non-code; tool, skill, schema and monitoring behavior do not change.

The live dark-mode rehearsal ends at local paired export. It does not implement
the feature, create remote issues, prove browser behavior, regenerate TTRPG or
replace remote presentation checkpoints. The
[verification record](../docs/evidence/skill-led-demo-examples-verification.md)
retains stage conclusions, qualification, artifact hashes and the distinction
between narrative user-review checkpoints and assistant-reviewed batch artifacts.

### Findings and dispositions

| Finding | Disposition and evidence |
| --- | --- |
| Seed excerpt uses `Verification` instead of the canonical `Testing` heading | **fixed `e9bf52e68`** — the excerpt now demonstrates the heading SEED_FORMAT.md requires for ingestion; identifier/vocabulary review finds no sibling seed instance in the changed guides. |
| Pre-existing RUNBOOK fragment does not resolve to the canonical step layout heading | **fixed `49311e1a1`** — the link now uses the actual heading slug. Final accuracy review checks the source heading and all 201 fragment targets; no workflow or logic changes. |
| Three quick-recipe contradictions repeat across all shipped skill routers | **fixed `31fdf2f22` in the [separate skill repair](docs-and-onboarding.md#skill-router-recipe-repairs)** — bare audit omitted, detail iteration default misstated, manual done-state recovery suggested. Shared directives and command help establish the correct behavior; installer coverage does not pin the wrong claims. No router fix belongs to this conversion. |
| Nested backend probe cannot initialize in the restricted step context | **fixed `81a83f5bb`** — parent-session access completes the real rehearsal and replaces the global blocker claim with context-specific failure/recovery provenance. This is an execution-context recovery, not a change to backend implementation. |
| Rehearsal granularity heuristic calls three files unrelated | **declined** — one small feature owns initialization, browser wiring and markup. The INFO/limited-confidence advisory remains visible; both audit reports retain `advisory-only`, confirmed/current, zero conceptual findings. No split or clean-audit claim is made. |

### Review passes

1. Report-only review of `80dfaa78e..2aab4c878`: no material correctness or
   completeness finding. Method: accepted plan/details, entire implementation
   diff, owning contracts, source and existing tests; fixture round-trip and
   whitespace checks. The live retry is pending at this snapshot, and no success
   is inferred. Artifact: `.tmp/skill-led-demo-examples.review-1.md`.
2. Independent report-only review of `80dfaa78e..81a83f5bb`: no material finding.
   Method: full diff plus actual rehearsal files, report qualification, all six
   artifact hashes, companion fingerprints, command lifecycle records and
   unchanged application/test files. Artifact:
   `.tmp/skill-led-demo-examples.review-2.md`.

The saved final responses identify their reviewed ranges and methods. Their
conclusions are retained here because `.tmp/` paths may disappear. The second
pass reviews the final evidence update independently; it does not assume the
first pass's conclusion. No production logic changes in this range. The later one-line navigation
correction (`49311e1a1`) is checked against the actual heading and the full
changed-document fragment set; final closure metadata adds no behavioral claim.

### Reconciliation and closure

`plan-tool --backend codex --model gpt-6.1-sol reconcile-code
skill-led-demo-examples --all -y` exits 0 and reports no code steps to reconcile.
All four steps are explicitly non-code; there is no eligible code sweep to
repeat. Log: `.tmp/skill-led-demo-examples.reconcile-sweep-1.log`.

The launcher completes and commits all four steps. The parent corrects the seed
excerpt, files the skill observation separately, completes the bounded rehearsal,
and synchronizes evidence/status. The final `uv run pytest tests/ -q -n auto`
passes with 14,698 passed and 66 skipped. Local story lint checks one actual
story without warnings, and the rehearsal's single baseline Node test passes.
Neither suite result is described as proof of an unimplemented feature.

The review loop closes as converged for the implemented documentation scope.
The skill-router correction has its own repair and review record; it is separate
from this demo implementation. Remote demo ref
replacement, release publication, browser testing and any fresh TTRPG run retain
their explicit boundaries; no merge or publication is performed by this review.

## Skill-router recipe repairs

*Opened 2026-10-21.*

| Field | Record |
| --- | --- |
| Base | `94e259687968ad18dfc965799a45df93218acd30` |
| Source-fix snapshot | `8fcf1b1f7` on `fix/skill-router-recipes` |
| Scope | Claude, Codex and Cursor routers; resolved backlog and evidence links |
| Runtime changes | None |
| Validation | Eight parent parser checks; 33 affected tests pass; full suite at `8fcf1b1f7`: 14,698 passed, 66 skipped in 61.41s |
| Review state | Actual Claude Code passes 2–3 find no router correctness defect; record cleanup verified, see closure |

### Property and sites

The routers must agree with existing command behavior and the canonical
[shared directives](../integrations/shared/DIRECTIVES.md) about authoring order,
iteration, recovery, verification authority and exit status. This repair changes
instructions; it adds no workflow gate and changes no CLI behavior.

The pre-edit identifier search covers `detail --reconcile`, `reconcile-plan`,
`[REDIRECT]`, `--iterate`, manual done-state editing and budget exhaustion.
The vocabulary search covers the authoring pipeline, implemented work,
headless examples, defaults, recovery, read-only checks and CI gates. Sites are
the headless block, decision tree, pipeline summary, reconcile catalog and
iteration summary in all three routers. A resolved-record sweep also finds
two demo records linking the removed backlog heading; those links move here.

### Findings and dispositions

| Finding | Disposition and evidence |
| --- | --- |
| Completeness recipe and pipeline omit the bare audit | **fixed `31fdf2f22`** — seed/create → bare audit → one-shot detail → grounded audit, with committed judged corrections and user review boundaries. |
| Detail default and compatible iteration flags are misstated | **fixed `31fdf2f22`** — detail defaults off; actual parser checks reject `detail --reconcile --iterate` and standalone reconcile iteration flags. The examples use only valid combinations. |
| Test-defect recovery suggests hand-editing done status | **fixed `31fdf2f22`** — commit the tested code/test correction without the plan, use `run --accept --commit` to run gates and advance, and retain the canonical unsuitable-implementation/no-gate escape routes. |
| Verification/redirect recipes send produced work to plan mutation | **fixed `31fdf2f22`** — request report-only inspection with `run --step N --mode check`; qualify all plan-side recipes as pre-execution and judge post-run redirects without an automatic code-canonical plan rewrite. |
| Summary promises budget exhaustion exits nonzero | **fixed `31fdf2f22`** — completed loops can exit zero; inspect saved outcome/qualification and use only supported CI flags. Existing exhaustion coverage explicitly asserts zero. |
| Independent headless examples still resemble an unaudited sequence | **fixed `4c5b20e62`** — all three blocks are explicitly syntax examples, with sequential authoring routed to the staged recipe and canonical gates. |

The original three-issue backlog record is fulfilled and removed. The two additional findings are the produced-work verification/redirect
authority error and the budget-exhaustion exit-status claim listed above.
They have provenance in local branch `docs/skill-router-follow-up-findings` at `c02aa3ff7`; that tracking
commit is not a remaining fix and should not be replayed as pending work after
this repair. The broader installed-skill portability and policy effort (#508)
remains separate. A nested sandbox initialization limitation observed during
the demo is resolved by parent access; it is not claimed as a skill runtime fix.

### Validation and reviews

- Real `build_parser().parse_args()` checks cover create, both audit gates,
  one-shot detail, report-only step inspection, both plan-side reconcile routes
  and gated acceptance without executing handlers.
- `uv run pytest tests/cli/test_skill_cmd.py
  tests/test_cli.py::TestCrossCuttingIterationCLI::test_budget_exhaustion_stderr_signal_create -q`:
  33 pass, including installer/copy behavior and the documented zero-exit case.
  After the headless correction the same affected set passes in 0.53s.
- Initial full-suite run before the Claude corrections: `uv run pytest tests/ -q -n auto`,
  14,698 pass and 66 skip in 63.02s. The later snapshot/result is in the header.
  No tests matching prose are added.
- Review 1, `94e259687..31fdf2f22`: no material finding; independently checks
  parser variants, owning contracts, source and relevant existing tests.
- Review 2, the same source snapshot: one P2 at the headless syntax block,
  corrected class-wide in `4c5b20e62`; no other material finding. It validates
  17 representative parser cases and the implemented authority boundaries.
- Review 3, `94e259687..4c5b20e62`: no material finding after the correction;
  independently checks the full identifier/vocabulary class, canonical rules,
  source and tests, with 12 parser-only probes. The remaining deeper iteration
  guide contradiction is tracked in BUG_BACKLOG.md rather than expanded into
  this router repair.
- Review 4, `94e259687..49f663dc4`, independently checks all eight changed
  files, 19 parser probes, handlers, source/tests, resolved links and the
  retained full-suite result; it reports no material findings. Saved artifacts
  use `.tmp/skill-router-recipes.review-N.md`; these verdicts retain the
  conclusions when scratch paths disappear.

No plan-tool execution plan or post-run code reconcile sweep is needed for this
direct documentation correction. The direct-change accuracy/completeness loop
applies; installation refresh and publication are recorded only when performed.

### Installation and closure

Before refresh, the installed Codex `SKILL.md` and `DIRECTIVES.md` copies match
the pre-fix source, so no custom content is overwritten. The global
`plan-tool install-skill --integration codex --user --force` reports “already
installed,” but a byte comparison still finds the old router. Its bundled-source
resolution does not select this checkout's changed router; this is not evidence
that `--force` is broken.

The explicit checkout invocation succeeds:

```bash
.venv/bin/python -c 'from plan_tool.cli.app import main; raise SystemExit(main(["install-skill", "--integration", "codex", "--user", "--force"]))'
```

Post-install byte checks confirm both installed files match the verified source.
Existing Claude/Cursor installation links are not retargeted. The branch push's
required full-suite hook also passes.

Two consecutive independent post-correction Codex reviews are clean. They do not
constitute the directed Claude Code `/code-review` route; that omission is
identified on 2026-10-21 and the actual Claude loop follows below. The deeper
iteration-guide mismatch remains separately tracked. No CLI behavior changes,
new gates, default-branch pushes or pull-request merge are part of this repair.


### Claude Code review pass 1 — 2026-10-21

Scope: `94e259687..ef924797e`. Claude Sonnet 5.5 invokes the actual built-in
`code-review` Skill with `high` effort in session
`1b67de09-bf16-47ed-b385-4dc20c19831d`. The original CLI exits zero and writes
`.tmp/skill-router-recipes.claude-review-1.md`; its stream records the Skill
invocation. Local diff review only; no publication or code edits.

| Finding | Disposition |
| --- | --- |
| F1 medium-low: check mode does not assess implementation | **refuted in part / clarified** — `prompts/check.md` explicitly requests mismatches between the step and code and forbids rewriting. A clean model report cannot prove delivery; the routers now state that limitation instead of promising read-only enforcement. Mutating `reconcile-code` is inappropriate for an inspection request. |
| F2 medium-low: detail example lacks clean-tree precondition | **fixed** — all three detail syntax lines state the precondition and plan commit. |
| F3 low: reconcile auto-apply warning loses “every” | **fixed** — all three lines state every recommendation is auto-applied without judgment. |
| F4 low: local provenance is unreachable on this branch | **clarified** — the local branch is named beside the commit. The finding descriptions and dispositions are retained here without depending on that branch merging. |
| F5 low: review 4 is embedded in review 3 | **fixed** — separate review bullet; remove incidental CLI narration. |
| F6 nit: extra backlog separator | **fixed** — normalize heading separators. |
| F7 nit: long completeness recipe duplicates directives | **declined** — the router must expose both audit gates, commits and user boundaries; its explicit clean-baseline instruction already covers the scenario. No additional workflow is introduced. |

Pass-1 outcome: convergence remained pending fresh Claude Code reviews after
these corrections.


### Claude Code review pass 2 — 2026-10-21

Scope: `94e259687..8fcf1b1f7`. Actual built-in `code-review` Skill at high effort,
Claude Sonnet 5.5, fresh session `43e9f02a-db4b-48aa-9bc2-79190646a2a7`;
CLI exits zero with `.tmp/skill-router-recipes.claude-review-2.md`.

| Finding | Disposition |
| --- | --- |
| 1 medium-low: evidence page describes repaired recipes as current | **fixed** — date the observation and frame the former recipes as past; retain it as demo provenance. |
| 2 low: header names an earlier source/test snapshot | **fixed** — name `8fcf1b1f7` and its fresh full-suite result (14,698 pass, 66 skip, 61.41s); affected set is 33 pass in 0.54s. |
| 3 low: local provenance does not name its two findings | **fixed** — identify both defects explicitly beside the branch reference; their descriptions/dispositions remain in the finding table. |
| 4 low: check mode is model-judged | **declined, residual limitation** — the existing caveat states that a clean report cannot prove delivery; no deterministic semantic guarantee is claimed. |
| 5 nit: completeness recipe duplicates directives and omits output override | **declined** — retain both gates in the router; the independent syntax example's optional output override does not constrain the default-location recipe. |
| 6 nit: backlog should include run reconciliation iteration | **refuted as proposed** — canonical directives explicitly describe `run --iterate` as reconcile-loop control; the unsupported detail combination is independently proven by the parser. Do not widen the backlog from an unverified claim that run ignores reconciliation iteration. |

The router instructions receive no further change in this pass. These record
corrections do not reset their review window. Pass 2 reports no router correctness
defect; another independent pass is required before Claude convergence is claimed.


### Claude Code review pass 3 — 2026-10-21

Scope: `94e259687..a575487d5`. Actual built-in `code-review` Skill at high effort,
Claude Sonnet 5.5, session `a467cb5b-edf1-413e-aad8-c80585d634b4`, original CLI
exit zero. Report: `.tmp/skill-router-recipes.claude-review-3.md`. Its summary
count has a typo the reviewer could not edit after writing; the individual
findings below govern (one low-medium, four low, one nit).

| Finding | Disposition |
| --- | --- |
| A1 low-medium: four live gates reference the removed bug entry | **fixed** — BACKLOG #510/#515 and the installed-skill/public-release arcs link this repair as satisfying recipe consistency. Their independent unfinished prerequisites stay. Identifier and vocabulary searches enumerate all four sites before editing. |
| A2 low: iteration follow-up omits README sibling | **fixed tracking** — add README.md to the existing guide-accuracy backlog entry; leave actual guide changes to that bounded work. |
| A3 low: repair table overstates check-mode enforcement | **fixed** — use “request report-only inspection”; the prompt directs no rewriting but does not enforce filesystem isolation. |
| A4 low: index count differs from table rows | **clarified** — remove the count from the index; the finding table retains individual fixes and provenance. |
| A5 low: two full-suite timings lack separate attribution | **clarified** — label the original run separately from the fresh `8fcf1b1f7` run. |
| A6 nit: per-pass pending line reads as current | **fixed** — explicitly label the pass-1 outcome. |

Router convergence: passes 2 and 3 independently report no router correctness
defect, with residual advisory limitations dispositioned. At the pass-3 snapshot, supporting-record
verification remained pending; closure below records the completed sweep. This
is not represented as a wholly clean branch review. The latest findings predominantly
concern the repair's own record edits. Finish this bounded application and
verify the named properties rather than repeatedly elaborating review prose.


### Claude review closure

The actual Claude Code route comprises three completed high-effort Skill
invocations, with separate sessions, exact ranges and saved findings above.
Passes 2 and 3 independently find no router correctness defect after the final
router change (`8fcf1b1f7`); remaining model-judgment limitations and optional
wording suggestions have explicit dispositions. This is router convergence,
not a claim that those reports contain zero findings across every record.

The final supporting-record correction is committed as `59796a8ad`. Verification
confirms all four live prerequisite replacements resolve to this ledger, the
removed-entry heading/vocabulary has no remaining live gate in BACKLOG,
BUG_BACKLOG or the backlog arcs, and all three routers carry the clean-tree,
every-recommendation and delivery-evidence clarifications. `git diff --check`
is clean. The installed Codex skill and directives byte-match current sources.
The final record-only sweep changes no router or runtime behavior, so the fresh
33-test and 14,698-test results above remain the behavioral evidence.

Stop under the direct-change self-seeded-edit exit: later findings predominantly
concern these repair records; complete their bounded application and verify the
properties instead of resampling unchanged routers. No further full review is
claimed after `59796a8ad`, and no fully clean whole-branch Claude verdict is
claimed. All reported findings have dispositions. The omission in the earlier
execution is corrected; the skill already contains the Claude review requirement.

### Follow-up correction — 2026-10-22

Pass-2 finding 6 above is incorrectly refuted: the canonical directive itself
contains a stale claim. `cmd_run` and its existing dispatch test explicitly
reject `run --reconcile --iterate` with exit 2. The
[iteration-route repair](docs-and-onboarding.md#iteration-route-documentation-repair)
corrects the user-facing guides and directives against source/test evidence;
protected CLAUDE.md policy and generated help remain separately tracked.
The earlier no-router-defect verdict does not establish run-side flag support.


### Iteration policy/help follow-up — 2026-10-22

The protected-policy and CLI help/warning deferral is implemented in the
[run iteration guidance repair](docs-and-onboarding.md#run-iteration-guidance-accuracy).
That record owns current validation and review status; deferrals above retain
the provenance of these earlier review snapshots, not a remaining open bug.

## Iteration route documentation repair

*Opened 2026-10-22.*

Base: `330441789` (merged PR #135). Scope: iteration examples/defaults and
reconciliation-loop claims in README, iteration/operations/common-workflow
guides, RUNBOOK, shared directives and the three skill routers. Runtime behavior
is unchanged. The fulfilled guide bug is removed; protected policy/generated
help mismatch remains in BUG_BACKLOG.md for architect-tier work.

### Property and sites

Only implemented loops are described as iterative. `create` defaults on;
`detail` and `completeness-audit` default off. Detail stays one-shot unless
explicitly requested. Detail reconciliation rejects either iteration flag;
legacy run reconciliation rejects `--iterate`; standalone reconcile verbs do
not accept it. Plan-side reconciliation remains pre-execution, with
plan-canonical code reconciliation after execution.

Identifier search covers both reconcile aliases and iteration flags; vocabulary
search covers defaults, headless examples, loop counts, per-invocation budgets
and checkpoint claims. Sites: README headless/defaults/table/use cases/budgets/
checkpoint/gate summaries/reconcile example; ITERATION equivalents; RUNBOOK
loop introduction/reconcile recipes; OPERATIONS headless examples;
common-workflows create/run examples; shared directive iteration paragraph and
all three routers. Protected policy and generated help are separately tracked.

### Validation

Existing tests: `TestIterateFlagsDetail`, `TestDetailReconcileDispatch`,
`TestRunReconcileDispatch` in tests/test_cli.py plus tests/cli/test_skill_cmd.py:
58 passed in 0.66s. These pin authoring defaults, both reconciliation rejections,
standalone dispatch and installation behavior without a live backend. No tests
that mirror prose are added. Full-suite and review results are recorded below.

### Review status

Four actual Claude Code Skill reviews are complete. Reviews 3 and 4 are
consecutive low-yield passes with no new medium-or-higher finding. Their
advisories are dispositioned below; closure is low-yield, not wholly clean.

### Claude review 1

Range `330441789..9816a9482`; actual built-in `code-review` Skill at high effort,
Sonnet 5.5, session `918ad21b-85d2-4e5f-905a-dccfd3471ef3`; CLI exits zero.
Saved report: `.tmp/iteration-guide-routes.review-1.md`.

| Finding | Disposition |
| --- | --- |
| 1 medium: GATES guide still advertises reconcile iteration | Fixed: gate lists and example use implemented authoring routes. |
| 2 medium: directives imply reconcile-run is the valid iterate route | Fixed: ordinary run is named as a no-op; reconcile rejection remains explicit. |
| 3 medium: TRACKING prescribes removed mode/iteration | Fixed: phase 3b and examples use post-execution `reconcile-code`, with judged separate invocations. |
| 4 low: headless explanations still reference obsolete loop | Fixed: explain deterministic authoring fixes, conceptual judgment, valid independent examples and actual completeness CI flag. |
| 5 low: architecture/recovery/pipeline siblings | Fixed: supported route lists and time-budget coverage; internal helper references explicitly distinguish implementation from CLI availability. |
| 6 low: runtime warning absent from follow-up | Filed in existing protected-policy/help bug; runtime behavior stays unchanged here. |
| 7 low: router argument hints include ineffective iteration flags | Fixed: remove run-iteration budget flags from all three hints; authoring loops remain documented in the body. |
| 8 low: voice and unnecessary churn | Fixed human-facing detail-request wording and headless paragraphs; retain equivalent README/guide facts while correcting stale route claims. No broad style rewrite. |
| 9 info: whitespace | Fixed extra separators at changed sites. |

Second sweep: identifier searches include `--mode reconcile`, `_iterate_reconcile_loop`,
both aliases and iteration flags. Vocabulary includes gate surface lists,
re-audit, per-step/per-run budgets, headless apply and time-budget coverage.
Additional sites are GATES, TRACKING, ARCHITECTURE, recovery index/audit and
pipeline audit; all receive route corrections or explicit internal-only labels.

Full suite at `9816a9482`: 14,698 passed, 66 skipped in 54.73s. Parser-only probes
confirm three defaults, four valid forms and four unsupported combinations;
run-side rejection is pinned by its existing handler test. Review is not yet
converged; the next pass reviews the corrected committed snapshot.


### Claude review 2

Range `330441789..99ffa33e6`; actual built-in `code-review` Skill at high effort,
Sonnet 5.5, session `7cf66b91-f7dc-4e1e-af4c-66950cd54049`; CLI exits zero.
Saved report: `.tmp/iteration-guide-routes.review-2.md`.

| Finding | Disposition |
| --- | --- |
| 1 medium: TRACKING retains run/reconcile iteration sentence | Fixed: describe separate invocations and actual completeness default. |
| 2 low: plan-route rationale promises reconcile iteration | Fixed: name authoring audits plus separate reconciliation/review. |
| 3 low: backlog recipes use removed mode | Fixed: three recipes use `reconcile-code`; source-investigation entry explicitly distinguishes dormant helper from available CLI route. |
| 4 low: touched detail example has unsupported no-walk/no-save | Fixed: remove both lines; standalone reconcile-plan flags stay. |
| 5 low: repo-local installed Claude copy remains stale | Refresh from canonical integration sources using the supported copy installer; retain copies as tracked artifacts, not a second authoring source. |
| 6 low: handoff pending text is stale | Fixed: name completed review snapshots in the overview. |
| 7 low: recovery entry-point list implies a live reconcile loop | Fixed: supported authoring entry points are separate from the retained internal helper, whose budget no CLI route enables. |
| 8 info: reconcile-code has no automatic commit | Clarified: workflow example says verify and commit separately. |
| 9 optional/unverified: detail iteration wording | Declined: current text explicitly requires a request for detail iteration and correctly states its off default. No conflicting claim is verified. |

Site enumeration expands to TRACKING's plan-route rationale and quality paragraph,
BACKLOG's three removed-mode recipes and one investigation claim, recovery's
session entry-point list, touched detail examples and the tracked Claude install.
Archive plans/evidence describe retained implementation/history rather than live
CLI recipes and stay. Protected CLAUDE.md, generated help and runtime warning
stay under the explicit follow-up entry.

Full suite at `99ffa33e6`: 14,698 passed, 66 skipped in 64.75s. Affected tests
pass again (58 in 0.80s). No runtime implementation changes are introduced.


### Claude review 3

Range `330441789..0ba7e8692`; actual built-in `code-review` Skill at high effort,
Sonnet 5.5, session `20aa6f74-8c4f-41fd-9db2-4bc2a8a9f3e6`; CLI exits zero.
Report: `.tmp/iteration-guide-routes.review-3.md`. No medium-or-higher finding;
the reviewer explicitly classifies the pass as low-yield.

| Finding | Disposition |
| --- | --- |
| 1 low: ordinary-run iteration flags remain in backlog | Fixed: remove ineffective flags from the enumerated ordinary-run recipes and replace the wizard's loop claim with fixture coverage and post-run review. |
| 2 low: hand-written run synopses list accepted but ineffective flags | Deferred with existing help-surface follow-up; add README and command reference to its Files list so help and synopses move together. |
| 3 generated pointer repeats deferred issue | Already tracked; no new finding. |
| 4 optional: restore iteration to run-oriented hints | Declined: iteration is documented at its authoring verbs, not ineffective run flags. |
| 5 optional: show literal commit command | Declined: workflow explicitly requires verifying and committing separately; reconcile-code accepts no commit flag. |
| 6 optional: capital letter after colon | Declined: no behavior/interpretation defect; avoid installer churn for typography. |

The third sweep covers ordinary-run ineffective iteration recipes, not only
reconcile aliases. Tracked Claude files byte-match their canonical sources;
review 3 independently verifies both copies. Full suite at `0ba7e8692`:
14,698 passed, 66 skipped in 63.72s; affected tests 58 passed in 0.67s.
Convergence window: one completed low-yield pass; independent confirmation pending.


### Claude review 4 and closure

Range `330441789..655c70b3a`; actual built-in `code-review` Skill at high effort,
Sonnet 5.5, session `0cb2fa6f-c51e-464b-982f-0f9336172154`; original CLI exits
zero. Report: `.tmp/iteration-guide-routes.review-4.md`. It independently
re-runs the 58 affected tests (pass in 0.73s), probes defaults/rejections and
verifies canonical/installed-copy equality. It reports no medium-or-higher issue
and explicitly classifies the pass as low-yield.

| Finding | Disposition |
| --- | --- |
| 1 low: recovery audit intro/crash text still says both loops | Fixed: name only the completeness loop, and give detail reconciliation its separate scoped-walk interruption guidance. Identifier/vocabulary sweep covers intro, refresh comparison, crash section and internal helper table. |
| 2 low: drift-detection module docstring advertises rejected invocation | Deferred in the existing policy/help follow-up: add the exact source docstring to its Files list. Runtime/source cleanup stays outside this instruction repair. |
| 3–4: backlog examples lose an execute step | Refuted by reviewer after inspecting base: both already contain a rejected reconcile-mode recipe, not execution. No execute step is removed by this change. |
| Optional: phase label, router typography/hints, operator voice | Retain existing dispositions; no newly verified route/default defect. |
| Protected policy, generated help and runtime warning/synopses | Already deferred explicitly; do not silently broaden this repair. |

Convergence is **low-yield**: two consecutive completed independent passes
(3 and 4) add only low/advisory findings, with no new material defect. Finish the
bounded recovery-text application and retain the named follow-up; stop here
under the repository policy rather than raising the pass cap for prose precision.
There is no claim of zero findings or a clean whole-branch review after the
final record/recovery edit.

Final verification: the installed Codex and tracked Claude skill/directive
files byte-match their canonical sources. `git diff --check` is clean. No
runtime behavior or parser change is introduced. Full suite at `0ba7e8692` is
14,698 passed / 66 skipped in 63.72s; later changes are backlog recipes,
recovery prose and review records. All findings have dispositions. Changes are
committed on `fix/iteration-guide-routes`; no push or PR is part of this action.


### Iteration policy/help follow-up — 2026-10-22

The protected-policy and CLI help/warning deferral is implemented in the
[run iteration guidance repair](docs-and-onboarding.md#run-iteration-guidance-accuracy).
That record owns current validation and review status; deferrals above retain
the provenance of these earlier review snapshots, not a remaining open bug.

## Run iteration guidance accuracy

*Opened 2026-10-22.*

Base: `e4ecd6e8b`, branch `fix/run-iteration-guidance`. Scope: the fulfilled
BUG_BACKLOG entry “Run iteration help and protected policy promise a reconcile
loop the CLI rejects”. Direct correction of diagnostic/help prose, policy and
documentation only; parsing, execution, warning dispatch and exit codes are
unchanged. CLAUDE.md changes require architect-tier PR review.

### Settled decisions

- No instruction promises a run or reconcile iteration loop. Ordinary `run` keeps its compatibility flags; its existing single-step warning names their lack of effect without recommending a rejected route. Reconcile rejection and authoring iteration behavior stay pinned by existing tests.
- Sites: CLAUDE iteration mandate; run_cmd warning/comment and iterate help; package catalog; drift_detection module docstring; README and command synopses; generated run reference and help golden; existing warning output test. Retained internal reconcile-loop machinery/tests are unchanged. Scratch: `.tmp/run-iteration-guidance.sites.md`.
- The existing warning test pinned the obsolete text and is updated and renamed for the new invariant (still checks successful execution, stderr routing, plain output). No prose-mirroring test is added.
- Validation: warning/style, reconcile dispatch, package-help and generated-reference checks 84 passed; mutation (recommending `detail --reconcile --iterate` again) fails the updated warning test; help regenerated through the supported golden route.
- Scope limits: do not remove compatibility flags, add execution loops, refactor dormant machinery, change authoring defaults, or absorb annotate input policy (#516) / configurable seed locations (#184). Earlier handoffs link this record so their historical deferral cannot read as pending work.

### Findings

Review 1, range `e4ecd6e8b..401644be8` (session `d112a224-c1dd-4f6b-90cf-f76f8d7d9a67`; report `.tmp/run-iteration-guidance.review-1.md`). Full suite at `401644be8`: 14,717 passed, 67 skipped.

- F1 medium, fixed (range `..1f99f9614`): inherited run loop-option descriptions misleading; run_cmd's local compatibility parent (used only by p_run) now describes all nine options as compatibility/no-effect; names, defaults, types, actions unchanged.
- F2 low, fixed (`..1f99f9614`): pipeline diagram labeled legacy value validation as a budget; now compatibility-only flags, no loop; validation stays.
- F3 low, fixed (`..1f99f9614`): helper docstring promised removed `run --mode reconcile` iteration; prose corrected only.
- F4 low, fixed (`..1f99f9614`): all-step dispatch bypasses the single-step warning; policy now says “may warn or reject”; no behavior change.
- Optional warning/style text: declined (wording retained); pending evidence placeholder replaced with actual evidence.

Review 2, range `e4ecd6e8b..1f99f9614` (session `7a70785e-373d-4532-b4dc-34c1b9eeae82`; report `.tmp/run-iteration-guidance.review-2.md`). Verified by callers, AST equivalence after removing guidance strings/docstrings, 177 targeted tests. Full suite 14,717 passed, 67 skipped.

- F-A low, fixed (`..488302fd5`): time-budget help now preserves flag/environment value-validation information; run reference regenerated.
- F-B low, fixed (`..488302fd5`): `_build_run_budget` has no production callers; docstring describes its retained compatibility delegation, as do the app re-export comment and the context test module's stale spy claim (comments only; the dated coverage baseline stays as provenance).
- F-C low, fixed (`..488302fd5`): run owns a separate compatibility parent; register docstring's verbatim/shared-parent claim removed.
- F-D declined: wording preference; existing warning is accurate.
- F-E refuted: accept-mode warning code and its existing test.
- F-F refuted: rejection tests and the recorded mutation; no prose-conformance test warranted.

Review 3, range `e4ecd6e8b..488302fd5` (session `c04a454e-d2fb-44cc-972b-4ead3d9b65d7`; report `.tmp/run-iteration-guidance.review-3.md`). Six candidates traced against dispatch/callers/tests; six-module normalized AST comparison repeated.

- D1 low, fixed (closing application, after `488302fd5`): budget value validation runs on ordinary and `--all` paths, not early-return accept/reconcile paths; all four help clauses qualified, reference regenerated, every validation branch preserved.
- D2 low, fixed (closing application): retained-wrapper/removed-alias comment sweep finished in the package header, tests/test_cli.py and both reconcile helper docstrings; package exports do not redirect handler globals, so comments describe command-module lookup ownership. No dormant code removed.
- Warning wording, silent all-step dispatch, synopsis selection, diagram precision: declined (preferences or earlier dispositions).
- Disabled-budget code removal: declined, out of scope. Backlog #517 stays tracking-only.

### Closure

Closure label: **low-yield convergence, not a clean review.** Reviews 2 and 3 contain only low-severity guidance findings and no material correctness/completeness gap. Review 3 reviews `488302fd5`, not the later closing prose/evidence commit. Under the stop-auditing-your-edits rule no further full review is launched to resample this advisory wording tail. Architect-tier PR review remains required for the protected policy change.

Closing validation: full suite 14,717 passed, 67 skipped; generated reference check included; six guidance-normalized production ASTs match the base; `git diff --check` passes.

## Demo workflow alignment

*Opened 2026-10-23.*

The dark-mode authored sample uses preferred step `description`; legacy
`title` remains accepted by the tool. Its excerpts remain intentionally
incomplete, with no new claim of captured output or live audit convergence.
The planning walkthrough already carries both audit/review boundaries,
current seed placement and local-only export, so it needs no workflow edit.

The TTRPG runbook places scaffold authoring after accepted roadmap publication,
asks readers to inspect plan IDs/outcomes/ownership/dependencies, and names
materialization/review before optional promotion. The promotion request shows
the complete target set and does not silently extend a selected demo batch to
missing or unreviewed sibling seeds. Direct reviewed draft use remains an
alternative. Later create reuses the selected row ID with a reported
repo-relative seed path. The prior phase-3 anchor remains valid through an
explicit anchor because the dated verification record links to it.

### Scope and sites

Invariant: demos teach the shipped workflow and preserve review/authorization
boundaries without implying a new rehearsal or remote publication. Identifier
searches cover step title/description, materialize/apply/create operands and
phase headings; vocabulary searches cover seed generation, scaffold timing,
promotion selection and legacy seed destinations. The four demo pages are
reviewed; only the sample and roadmap runbook need changes. Existing lifecycle
procedures remain owned by the shared directives and format/guide documents.

The plan-list review prompt reflects current stage-4 responsibilities; it is
not a stage-4 algorithm change or a semantic decomposition gate. Historical
preparation checkmarks and measurements remain dated provenance.

### Verification

- `uv run pytest tests/test_seed_paths.py tests/cli/test_cli_reference.py -q`: **15 passed**.
- All demo-local link targets and heading anchors resolve; prior phase-3
  incoming anchor from the verification record remains available.
- `git diff --check` passes.
- Existing `tests/test_roadmap_format.py` (including the demo documentation
  guard): **53 passed**. No full-suite repeat for this prose-only correction.
- Two independent completed reviews target
  `f7176a27a..ed29b1e97bba36e611453605a61ebf713a0d6b7c`, using actual built-in
  Claude Code `code-review` Skill calls with `claude-sonnet-5-5 --effort high`.
  Both session logs contain the actual Skill invocation; the second persisted
  report describes its inline recipe rather than that outer call.
- Outcome: **low-yield convergence**. No correctness/contract failure is
  confirmed against source. Retained low-severity observations: historical
  scaffold wording still names its stage-3 source (dated provenance, not timing
  instructions); later audit/detail placeholders retain the generic plan-id
  spelling; the generic reviewed-seed path covers either source. The promotion
  instruction already stops on missing/unreviewed siblings and offers direct
  draft use; a fuller all-or-nothing explanation belongs to the linked owner.
- Old heading text in completed plan details remains historical provenance;
  the explicit anchor preserves the live evidence-record link. Inline
  placeholders are explained substitution notation, not new CLI operands.
- A new parser test for deliberately incomplete reading excerpts is declined:
  it would turn authored samples into runnable fixtures outside this scope.
  The existing format/documentation guard passes instead.

### Preparation limits

No live plan-tool authoring, model rehearsal, feature implementation, tracker
publication or remote checkpoint update occurs in this task. Dark-mode remote
checkpoint refresh and a fresh TTRPG rehearsal remain pending as the demo index
and existing verification record state.

Review 1 session: `1f7a2c46-d325-4d2c-86b5-c2070e9a660c`.

Review 2 session: `16345ded-8227-4679-8e4c-bba6c593dbdd`.

## Direct-edit onboarding clarity

*Opened 2026-10-23.*

Single obvious edits can skip plan-tool's plan-authoring and execution pipeline
while retaining tests and review. The README's small first-plan example is a
learning exercise; small scope alone does not require a plan.

### Scope and review

The user authorizes clarifying the README opening and first-plan exercise,
contributor route selection, how-to index, and use-case entry-point table.
Identifier search covers `direct-pipeline`, `direct-run`, and direct-edit links;
vocabulary search covers `small`, `straightforward`, `lightweight`, `single
obvious edit`, and route selection. The index's deprecated pipeline recommendation
is removed. Small work that needs a durable plan or local Jira handoff retains
its reviewed planning route. Assistant policy and runtime behavior stay unchanged.

Two session review passes check the distinction between direct editing and the
deprecated direct pipeline, retained testing/review obligations, and the learning
example versus ordinary work. Neither pass identifies a further material gap.
These are session reviews, not independent backend reviews. Local links and
README heading anchors pass validation, and `git diff --check` passes.

Full validation: `uv run pytest tests/ -q -n auto` — **15,154 passed, 66 skipped**.

## General onboarding documentation

*Opened 2026-10-23.*

The README routes first-time users through installation, reviewed planning,
execution prerequisites and the operational guides. Detailed command, backend,
recovery, logging and gate procedures live in their existing guides. Existing
README heading anchors remain available for incoming links.

### Scope and sources

The user requests correction of the onboarding review's five findings:
execution prerequisites, the frontmatter example, deprecated apply guidance,
contributor setup/work selection, and README duplication. Runtime behavior and
assistant policy remain unchanged.

Identifier searches cover `intent`, `format_version`, `require_merged_plan`,
`completeness-apply`, `--jobs`, and README links. Vocabulary searches cover
execution, default branch, planning artifacts, interactive application,
installation, picking work, and recovery. Relevant sites are README's first-plan
handoff, plan example, operational sections and install options; CONTRIBUTING's
short version and setup; common workflows' execution handoff; and the run guide's
entry prerequisites. The correction applies at these sites. Deeper independent
reference prose remains outside this onboarding edit.

Sources are `plan_tool/cli/run_cmd.py:_preflight_merged_plan_guard`,
`plan_tool/plan_merge_guard.py`, `plan_tool/review.py:check_intent_presence`,
`plan_tool/parser.py:parse_plan_text`, the completeness CLI options, and the
existing task/reference guides. The merge-check description distinguishes
missing artifacts, drift warnings, absent origin and unverifiable remote state.

### Verification and review

- Full suite: `uv run pytest tests/ -q -n auto` — **15,154 passed, 66 skipped**.
- The README frontmatter example parses through `parse_plan_text` and produces
  no `check_intent_presence` findings.
- Local link and fragment checks pass for all four edited onboarding documents.
  All original README heading anchors outside fenced examples remain available.
- `git diff --check` passes.
- Session review round 1 catches a nonexistent lessons reference and a stale
  contributor pull-request anchor; both links receive corrections. A second
  correctness/completeness pass checks the execution state cases, example,
  deprecated commands, setup prerequisites and preserved routes, with no new
  findings. These are session reviews, not independent backend reviews.

No implementation or model-backed plan-tool command is necessary for this
bounded documentation correction. The installation instructions are checked
against tracked sources; no fresh external installation is exercised.

## README roadmap seed handoff

*Opened 2026-10-23.*

The README's entry-point table and roadmap overview state that stage 4 publishes
the plan mapping, not seed files. The handoff materializes a selected plan ID,
uses `--view seeds` for per-plan state, and reviews the reported seed before
create. A default-directory direct draft example is distinct from optional
promotion, which requires materializing/reviewing its candidate drafts and
uses the actual create handoff. New nested publications and retained legacy
paths both remain supported. The ordinary two audit gates remain explicit.

### Scope and evidence

Invariant: the README never implies stage completion alone supplies a seed
that create can consume. Identifier search for `seeds/`, `--materialize`,
`--apply`, and vocabulary search for `draft seed` / `ordered create` locate
the core workflow row, entry-point row, roadmap overview and plan handoff. Those sites receive
the bounded correction; existing lifecycle/status prose is not redesigned.

Sources: `docs/how-to/roadmap.md` section 7, `plan_tool/seed_paths.py`,
the generated roadmap CLI reference and the corrected common-workflows guide.

- `uv run pytest tests/test_seed_paths.py tests/cli/test_cli_reference.py -q`: **15 passed**.
- Added seed-preparation link and heading anchor resolve.
- `git diff --check` passes.
- Initial actual Claude Code reviews at `457809890` both identify the missed
  core-workflow table row as the same defect class. The correction changes it
  to separate materialization/review before create, then commits `ed029fb3d`.
- Two independent final actual built-in Claude Code reviews at
  `ed029fb3db4eadfac54e4039860f253471713a87` (range `4cf28503e..ed029fb3d`),
  using `claude-sonnet-5-5 --effort high`, find **zero confirmed README defects**.
  The all-README restatement sweep confirms no remaining claim that a stage
  run writes seed files. Retained advisories concern optional wording for
  the materialize-reported path and linked state-handling detail; these do
  not require another iteration at README altitude.
- Final focused checks repeat: **15 passed**; the guide anchor and whitespace
  checks pass. No runtime behavior is changed.
- The fulfilled README backlog entry is removed. A separate starting-point
  guide statement still claims seeds/emitted plans from roadmap; it is filed
  in BUG_BACKLOG rather than expanded into this README-only correction.
  The legacy promotion-summary bug remains separately tracked.

Review 1 session: `a10bbe21-8cac-4171-b3b5-69053cb2e38f`.

Review 2 session: `bab1f073-2300-4b4f-b100-97637a7c34e2`.

Review 3 session: `b2f31c7a-9405-40a4-b582-1cf2efede099`.

Review 4 session: `53aa6943-968a-40b3-9f48-b6bd1b910690`.

## Use-case guidance correction

*Opened 2026-10-23.*

The catalog in `docs/how-to/use-cases.md` routes users through reviewed seeds,
both plan audit gates, and separately requested execution or local export.
Its CI example explicitly uses `--fail-on-findings`; informal manual review
does not replace either audit gate. Small changes use the supported staged
route; deprecated direct commands appear only as compatibility guidance.
New seed examples use `docs/implementation-plans/plan-seeds/`, while recorded
legacy destinations remain valid. External drafts explicitly reach both gates.

The roadmap entry provides artifact review questions and links to the deeper
walkthrough instead of repeating lifecycle mechanics. It requires explicit
materialization after stage 4, grounded in `plan_tool/roadmap.py` and the
walkthrough's seed-preparation section. Materialization does not approve a seed.

### Scope and sites

Invariant: a use-case entry points to the supported route and does not imply
that generation, a zero exit code, or informal review proves audit convergence.
Identifier searches cover `direct-jira`, `direct-run`, `plan-seeds/`,
`verify-all`, and the retired section-9 anchor. Vocabulary searches cover
manual verification, skipping audits, seed promotion and draft generation.
The relevant sites are the fit table, shared review introduction, sections
1/2/4/9/11, the not-to-use list and the entry-point table. All are corrected
within this catalog; detailed lifecycle procedures remain with their owners.
No repository link targets the renamed section-9 heading.

### Verification

- Every local Markdown link target and heading anchor in the catalog resolves.
- `git diff --check` passes.
- `uv run pytest tests/cli/test_cli_reference.py -q`: **10 passed**.
- No runtime changes or live plan/backend invocations are part of this task.
- Initial reviews at `38cee4947` both invoke the actual built-in Claude Code
  `code-review` Skill with `claude-sonnet-5-5 --effort high`. Round 2 finds no
  confirmed defect. Round 1 identifies residual legacy-grade future wording
  and the linked common-workflows CI mismatch; both receive bounded fixes.
  Its claim that section 5 never states the pre-execution boundary is partly
  refuted by the existing “unexecuted plan” request; the correction also makes
  the boundary explicit in explanatory prose and names the applicable re-audit.
- Optional suggestions to restore roadmap lifecycle detail are declined: the
  linked walkthrough and format own those procedures, and the orientation page
  makes no conflicting claim. An undefined direct-change route gains its exact
  directives link. No runtime behavior or test-authoring work is implied.
- Two independent final actual Claude Code reviews at
  `46987e67e63bc1a939d3427f2d27bf8b586e65e3` (range `8a92bb504..46987e67e`)
  find no introduced defect in the changed guidance. Both retain optional
  wording suggestions without requiring further edits: low-yield convergence
  for this bounded documentation change.
- Both reviews confirm pre-existing roadmap seed examples in the untouched
  common-workflows roadmap subsection still use old paths and imply automatic
  materialization. They are deferred to BUG_BACKLOG, “Common-workflows roadmap
  examples point new users at seeds that do not exist.” No source behavior is
  changed or claimed fixed by that deferral.
- Final command-reference recheck: **10 passed**; links/anchors and whitespace
  checks pass again after the correction batch.

Initial round 1 session: `bc379312-afed-43aa-bd9f-07d840f65a50`.

Initial round 2 session: `8f750bc4-309f-4244-bb39-36555e53fb10`.

Final round 3 session: `33918a2a-ae91-451e-ac9e-632712e85f4a`.

Final round 4 session: `dc4c8019-0569-44b7-8f79-046680176630`.

## Onboarding guidance entry removal: code review ledger

*Opened 2026-11-13.*

One bounded change, fact-checked headlessly (`claude-personal -p`, report-only):
the `BUG_BACKLOG.md` entry "Onboarding and installed skill instructions conflict
with canonical audit and iteration rules" is removed with a dated record in
`docs/history/backlog-decisions.md`, two passages the entry's class still
reached (`docs/how-to/roadmap.md`, `RUNBOOK.md`) are corrected, and the
leftovers are filed as two `BUG_BACKLOG.md` entries. The drain procedure lives
in [`bug-backlog-drain.md`](bug-backlog-drain.md).

| Item | State |
| --- | --- |
| Review range | `origin/main..HEAD` at each pass's head. The branch also carries two housekeeping commits (the handoff trim `8b40cdbb0` and the ledger move `2c3e829aa`) |
| Heads reviewed | Pass 1: the head before `9ca3bb6b3` (that commit was amended before the first push, so the pre-amend hash is not cited). Pass 2: `c8dc895b7`. Pass 3: `881047f62`. Corrections to pass 3: `9bb43e535`, `71a053ece`, `3a6b9a773`, then this ledger revision (the next commit) |
| Checks | Full suite 14,916 passed, 66 skipped, 2026-11-13, after the last change; documentation and backlog only, no code. The reviewers read the repo and git history but could not run scripts, so the 24-hit sweep breakdown was re-derived by hand in pass 3 |
| Reviewer | Headless sessions on `claude-sonnet-5-5`. Findings files and stream logs are local scratch (`.tmp/onboarding-docs-entry-code-review-N.*`, gitignored); findings and dispositions are recorded here |
| Disposition | **Stopped at exit 2, 2026-11-13: neither converged nor clean.** See Closure |

### Settled decisions

- The entry's named files (README first-task path, `common-workflows.md`, the
  three routers) read correctly at `1d8a47974`; the entry is removed, not
  described as fixed by this change.
- The shorthand `create → detail → audit → run` collapses the two audit gates and
  does not contradict them; edits to `CLAUDE.md` need architect-tier review, and
  `AGENTS.md` is a symlink to it.
- The `BACKLOG.md` recipes and the `RUNBOOK.md` iteration budget were filed, not
  fixed here, as separate classes of defect and queue records; the
  iteration-budget entry was fixed afterwards in `9f8c67e9b`.
- Restructuring the first-task path belongs to onboarding #510.

### Evidence (this session's runs)

- Provenance from git: at the `9c10d74ca` snapshot `common-workflows.md` already
  put the bare-plan audit before `detail`; the routers' recipe row ran `detail`
  before any audit and their iteration paragraph called `--iterate` "on by
  default for `create`/`detail`"; `31fdf2f22` fixed both.
- The command-sequence sweep (a `plan-tool detail` command that follows a
  `plan-tool create` within 80 lines with no `plan-tool completeness-audit`
  between, over fenced blocks of the tracked instructional documents) returned
  24 hits: 2 in `docs/how-to/roadmap.md`, 11 in `BACKLOG.md`, 11 independent
  examples. The script was session-local; the rule is recorded in the filed
  entry and the history record.
- `plan_tool/convergence.py` gives `DEFAULT_ITERATION_BUDGET_SECONDS = 1800`, and
  `plan-tool create --help` describes `--iteration-budget` as a debounced
  no-progress deadline.
- `completeness-audit --commit` refuses a dirty working tree
  (`plan_tool/cli/completeness_cmd.py`).

### Findings and dispositions

Pass 1 (two medium, four low, one info):

1. The record said the routers had no one-shot wording at the snapshot (they did:
   the recipe row said "one-shot; not `detail --iterate`") — `fixed 9ca3bb6b3`.
2. The record attributed "a missing detail file is coverage, not a design defect"
   to README and the routers; only `common-workflows.md`, `DIRECTIVES.md` Gate 1
   and `docs/how-to/pipeline/audit.md` say it — `fixed 9ca3bb6b3`.
3. `docs/ITERATION.md` was cited for `run --iterate` having no effect; only
   `docs/cli/run.md` says it — `fixed 9ca3bb6b3`.
4. The sweep missed `RUNBOOK.md`, whose closing audit-iteration line recommended
   `detail --iterate` without the opt-in qualifier — `fixed c8dc895b7`.
5. Present-tense status in the record — `fixed 9ca3bb6b3` (checks anchored to
   `1d8a47974`, the "(blocked on #508)" parenthetical dropped).
6. The README table's detail row dropped "not a clean audit", and the "Stopped at
   exit 2" label was outside the Retention rule's closure kinds — `fixed
   9ca3bb6b3` (label), `fixed 881047f62` (Retention now names it).
7. Trailing blank line at the end of the history file — `fixed 9ca3bb6b3`.

Pass 2 (one medium, two low, one info):

1. `docs/how-to/roadmap.md` skipped Gate 1 in its command list and in section 8 —
   `fixed 977b02cbb` (the `--commit` flags added then are corrected in pass 3,
   finding 1).
2. The README lead-in contradicted Retention — `fixed 881047f62`.
3. The `RUNBOOK.md` "narrow variant" sentence — `fixed 977b02cbb`; the stale
   300-second budget — `tracked`: `BUG_BACKLOG.md`, filed in `94c9b4171` and fixed
   afterwards in `9f8c67e9b`.
4. Present-tense status that goes stale — `fixed 881047f62` ("as of 2026-11-13",
   "open on 2026-11-13").

Pass 3 (one medium, seven low):

1. The roadmap how-to's `--commit` audits follow a stage that leaves the tree
   dirty, so Gate 2 would exit 2 — `fixed 9bb43e535`: the two audits drop
   `--commit`. This was a regression from pass 2's fix.
2. The budget entry understated its class (the "Bump the cap ... 600" advice and
   the tuning example assume the same low default; the third quoted passage is an
   illustrative string no code prints) — `fixed 71a053ece`.
3. `integrations/shared/DIRECTIVES.md`'s headless block listed `create` and
   `detail` side by side without the "not a stage sequence" note the routers
   carry — `fixed 9bb43e535`.
4. The record's list of independent examples and shorthand sites was incomplete —
   `fixed 3a6b9a773`.
5. The record said "archived plans" for what the sweep skipped, which was all of
   `docs/implementation-plans/` — `fixed 3a6b9a773`.
6. The two filed entries lacked a Verification line — `fixed 71a053ece`.
7. Wording: "one `completeness-audit`" was not true of every recipe; the record said
   `Iterate:` for blocks labeled `Iterate:` or `Iteration:`; a "left as is" item
   gave no reason — `fixed 71a053ece` and `3a6b9a773`.
8. The Retention bullet said "the four are not interchangeable" while older
   table rows carry other labels — `fixed 3a6b9a773` (rows closed before the rule
   keep their label).

### Closure

**Stopped at exit 2 on 2026-11-13; neither converged nor clean.** Each of the
three passes returned a medium finding, so the two-consecutive-low-yield-passes
condition never held. The mediums moved from errors in the history record
(pass 1) to an uncovered member of the entry's own class (pass 2) to a regression
in pass 2's own fix (pass 3), which is the shape `CLAUDE.md` calls the loop
auditing its own edits. Every finding is applied or dispositioned above, and no
fourth pass is planned unless the owner asks for one.
