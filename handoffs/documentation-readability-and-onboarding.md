# Handoff: documentation readability and onboarding

## Status

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
[`developer-docs-and-tracking.md`](developer-docs-and-tracking.md),
nor does it change product behavior. Its target is how the existing, verified
information is structured and explained.

The work is now integrated on `main`. Treat this handoff's older branch and
pre-relocation path references as history; the current documentation map owns
the live paths.

## Settled direction

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

## Terminology sweep (cut 2026-09-15)

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

## New-contributor path (cut 2026-09-15)

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

## Task-first documentation layers (cut 2026-09-15; reviewed 2026-09-16)

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

## Scope

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

## Delivery sequence

### 1. Establish the standard

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

### 2. Make an audit before rewriting

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

### Current audit ledger (2026-09-16)

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

### 3. Prioritize reader journeys

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

### 4. Revise in bounded, fact-preserving batches

Use one reader journey or closely related document group per reviewable batch.
Before editing, enumerate every repeated rule by identifier and vocabulary;
update the class or record why a site differs. Preserve test-pinned wording or
update its owning test map deliberately. Keep the existing link checker and
factual-anchor checks in the validation set, and add focused checks only where
the new document structure creates a stable contract worth pinning.

Do not use a global word-count gate or a mechanical paraphrase pass. Automated
checks may report candidate paragraphs for review, but reviewer judgment will
decide whether density is necessary to state one cohesive contract.

### 5. Validate as onboarding material

For each batch, ask a reviewer with fresh context to follow the intended
reader task using only the edited documents. Record where they cannot find the
normal path, an exception, ownership, or a next action. Resolve material
findings before calling the batch ready. The team's general decision about
reviewer independence remains open; fresh-context review is the minimum for
this work until that decision lands.

End with one cross-document walkthrough of all four reader journeys. Confirm
that document links, terminology, and authority boundaries agree across the
journey rather than only inside a single file.

### 6. Make the standard durable

Add a documentation-readability item to the pull-request review checklist.
An advisory helper may flag unusually long prose blocks after a baseline
exists, but it must not reject precision-heavy reference material solely by
length. Revisit the audit on future major documentation changes and extend it
only to new live developer-facing material.

## Acceptance criteria

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

## Open decisions

1. Does the audit and pilot stay with the front-door pull request after review,
   or move to a follow-up branch before requesting review?
2. Does the team adopt the existing suggested three-round code-review-tail cap
   and reviewer-independence policy before this work starts, or use the
   fresh-context minimum stated above?

## Next action

1. Run a fresh-context walkthrough of the newcomer and operator routes using
   the README, `CONTRIBUTING.md`, and the task-first documentation map.
2. Review the remaining README headless, recovery, iteration, and gates sections
   as separate task routes; do not merge their exception contracts into the
   first-plan overview.
3. Add the readability item to the pull-request checklist after the walkthrough
   identifies the practical review prompt.
