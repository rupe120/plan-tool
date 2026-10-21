> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Roadmap 01 Domain Constraints
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Add a roadmap artifact contract leaf with paths, enums, and frontmatter parsing
  creates:
  - plan_tool/roadmap_artifacts.py
  - tests/test_roadmap_artifacts.py
  allowed_mentions:
  - plan_tool/roadmap_gates.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/roadmap-01-domain-constraints/01-roadmap-artifact-contract-leaf-paths.md
  status: done
- id: 2
  title: Add the deterministic roadmap response gates and their violation messages
  creates:
  - plan_tool/roadmap_gates.py
  - tests/test_roadmap_gates.py
  allowed_mentions:
  - plan_tool/roadmap_artifacts.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/roadmap-01-domain-constraints/02-deterministic-roadmap-response-gates.md
  status: done
- id: 3
  title: Write ROADMAP_FORMAT.md specifying both artifacts and naming the code that
    enforces them
  creates:
  - ROADMAP_FORMAT.md
  complexity: low
  change_type: non-code
  depends_on:
  - 1
  - 2
  detail: docs/implementation-plans/plan-details/roadmap-01-domain-constraints/03-write-roadmap-format-md-specifying-both.md
  status: done
- id: 4
  title: 'Add the roadmap orchestrator: assembly, run log, gate retry loop, and --from-stage
    re-entry'
  files:
  - TESTING.md
  creates:
  - plan_tool/roadmap.py
  - tests/test_roadmap.py
  allowed_mentions:
  - plan_tool/roadmap_artifacts.py
  - plan_tool/roadmap_gates.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 2
  detail: docs/implementation-plans/plan-details/roadmap-01-domain-constraints/04-roadmap-orchestrator-assembly-run-log.md
  status: done
- id: 5
  title: 'Add the domain stage: its prompt and the gates that check 01-domain.md'
  files:
  - plan_tool/roadmap.py
  - tests/test_roadmap.py
  creates:
  - plan_tool/prompts/roadmap-domain.md
  allowed_mentions:
  - plan_tool/roadmap_artifacts.py
  - plan_tool/roadmap_gates.py
  - plan_tool/prompts/roadmap-constraints.md
  complexity: medium
  change_type: feature
  depends_on:
  - 3
  - 4
  detail: docs/implementation-plans/plan-details/roadmap-01-domain-constraints/05-domain-stage-its-prompt-gates-that.md
  status: done
- id: 6
  title: Add the constraints stage with the attribute-totality gate and the cross-artifact
    anchor gate
  files:
  - plan_tool/roadmap.py
  - tests/test_roadmap.py
  creates:
  - plan_tool/prompts/roadmap-constraints.md
  allowed_mentions:
  - plan_tool/roadmap_artifacts.py
  - plan_tool/roadmap_gates.py
  - plan_tool/prompts/roadmap-domain.md
  - tests/test_roadmap_gates.py
  complexity: medium
  change_type: feature
  depends_on:
  - 5
  detail: docs/implementation-plans/plan-details/roadmap-01-domain-constraints/06-constraints-stage-attribute-totality.md
  status: done
- id: 7
  title: Wire the roadmap command into the CLI, the help catalog, and the generated
    docs/cli reference
  files:
  - plan_tool/cli/parser.py
  - plan_tool/cli/app.py
  - plan_tool/cli/__init__.py
  - tests/cli/package_surface_help.golden.txt
  - docs/cli/README.md
  - CAPABILITIES.md
  creates:
  - plan_tool/cli/roadmap_cmd.py
  - tests/cli/test_roadmap_cmd.py
  - docs/cli/roadmap.md
  complexity: medium
  change_type: feature
  depends_on:
  - 6
  detail: docs/implementation-plans/plan-details/roadmap-01-domain-constraints/07-wire-roadmap-command-cli-help-catalog.md
  status: done
- id: 8
  title: 'Document the roadmap verb in the operator docs and reconcile BACKLOG #208'
  files:
  - USE_CASES.md
  - RUNBOOK.md
  - integrations/claude/SKILL.md
  - CLAUDE.md
  - BACKLOG.md
  complexity: low
  change_type: non-code
  depends_on:
  - 7
  detail: docs/implementation-plans/plan-details/roadmap-01-domain-constraints/08-document-roadmap-verb-operator-docs.md
  status: done
---
# Roadmap 01 Domain Constraints

## Overview

`plan-tool roadmap <slug>` is a new project-altitude authoring verb, one rung above `create`: it reads a concept brief (`--from-existing <concept.md>`) and turns it into staged architecture artifacts that later plans in the arc extend into component design and an ordered set of `create` seeds. Two numberings meet in this work and are kept distinct throughout: an **arc position** is one plan of the four in BACKLOG #208's arc, while an **artifact stage** is one numbered file this pipeline writes. They do not line up, so this plan names them and never numbers a bare "stage". This plan is **arc position 01**; it builds the verb skeleton, the artifact contract (`ROADMAP_FORMAT.md` plus a frontmatter-parsing leaf), and **artifact stages 1–2**, which write `01-domain.md` (entities, business rules, workflows) and `02-constraints.md` (quality attributes ranked as tradeoffs, not a checklist) under `docs/implementation-plans/roadmaps/<slug>/`. `--from-stage N` always takes an **artifact stage** number. Claude runs only inside a stage; deterministic gates check each response between stages — every workflow references a defined entity, every quality attribute carries exactly one disposition, every constraint anchors to something in `01-domain.md`, every decision names its alternatives and rationale — and a failing gate retries the stage rather than letting bad output reach the next one. The run is non-interactive: at each option point it guesses, records the choice as a decision, and marks genuinely load-bearing tradeoffs `pending` for an operator to confirm later; because every artifact is re-read from disk, `--from-stage N` is the correction loop after a hand edit, and the verb keeps the repo's exit-code convention — non-zero only when it fails to finish, never on gate findings alone.

## Problem statement

`create` is the highest-altitude authoring verb the tool ships: one seed in, one plan out. Above it there is nothing. An operator opening a project-sized effort does the architecture reasoning — which entities exist, which quality attributes genuinely trade off against each other, which components fall out, how those components partition into plans — in their head, then hand-authors each `plan-seeds/` seed from that unwritten model. The reasoning itself is never captured, so it cannot be reviewed, corrected and re-entered, or cited by the plans it produced.

The user-visible symptom is that a project-sized concept fed straight into `create` yields one over-packed plan whose completeness audit never converges. The tool recognizes the shape and says so: `convergence_diagnosis.py` classifies it `FORK_STRUCTURAL` and prints `_reseed_command`'s `plan-tool create <slug> --from-existing <seed.md> --iterate` — where `<seed.md>` is a **placeholder the operator hand-authors**. `create`'s own distill short-circuit (`SplitProposal`) detects the oversized input just as early and likewise has nothing to hand off to. Both of the tool's cheaper structural remedies have actuators (`FORK_LOCALIZED` → `--apply-split`, `FORK_SCOPE_OUT` → `--apply-scope-out`); the re-seed arm — the one a project-altitude input always lands on — has none. So the tool's answer to *decompose before auditing, so each unit is individually convergeable* terminates in the manual decomposition the operator started with.

The second half of the gap is durability. The decisions that should bind every plan in an arc — the tradeoff chosen, the alternatives rejected, why — survive only as whatever prose reached an individual seed. Nothing holds them at project altitude, so sibling plans re-litigate settled tradeoffs and a plan's scope-contract fence has no upstream constraint to inherit. A domain model and a ranked constraint set written **as durable artifacts, re-read from disk by whatever consumes them**, are what make both the decomposition and the traceability chain behind it possible.

This plan closes the upstream half: the verb skeleton, the artifact contract, and the two stages that ground everything downstream — `01-domain.md`'s entities/rules/workflows and `02-constraints.md`'s ranked tradeoffs. It deliberately stops short of turning those into components and seeds (BACKLOG #208's `roadmap-02-components` and `roadmap-03-plan-derivation` stages), so the deliverable here is narrower than the symptom above: a repo that can produce gated, decision-carrying, re-enterable architecture artifacts, on which the actuator the re-seed arm is missing is later built.

## Architecture

**Four new modules in one strict dependency line, plus one prompt file per stage.** `plan_tool/roadmap_artifacts.py` is a cycle-free leaf (stdlib plus the YAML loader the repo already parses frontmatter with) owning the artifact contract: where a roadmap's files live, what its frontmatter inventory holds, and the closed vocabularies — decision status, constraint disposition — that everything downstream keys on. `plan_tool/roadmap_gates.py` sits directly above it and imports no other first-party module: each gate is a pure function with its own message, taking a **stage envelope** — the artifact under check plus the already-parsed upstream artifacts — and returning violations. The envelope rather than a bare artifact is deliberate: a cross-artifact gate such as `check_constraint_anchors` needs the upstream domain to resolve anchors, and one uniform signature keeps the orchestrator's stage table free of per-gate branching. `plan_tool/roadmap.py` is the orchestrator — stage assembly, the Claude call, the gate retry loop, the run log, `--from-stage` re-entry — and is the only module in the group that shells out. `plan_tool/cli/roadmap_cmd.py` stays thin arg-to-orchestrator wiring, matching the CLI package's thin-handler layering. The stage prompts (`plan_tool/prompts/roadmap-domain.md`, `roadmap-constraints.md`) are files beside the existing prompts. The line is deliberate rather than a cluster: gates must be unit-testable without an orchestrator, and the artifact contract must be testable without gates. `roadmap.py` carries the repo's `invoker=` seam, defaulting to the real CLI shell-out so tests substitute canned stage responses and never spawn a backend.

**Disk is the interface between stages.** A stage writes its artifact; the next stage re-reads it from disk rather than receiving in-memory state. One mechanism buys three things: `--from-stage N` after a hand edit is just *start at N and read what is there*; the cross-artifact anchor gate — every constraint anchors to an entity, rule, or workflow defined in `01-domain.md` — reads upstream exactly the way a later run or a human does; and what the operator sees on disk is authoritative rather than a rendering of hidden state. The cost is a re-parse per stage, negligible against a Claude call and paid deliberately.

**Frontmatter carries what the gates check; the prose below carries what humans read.** Entities, workflows, quality attributes with their dispositions, and decision records are structured frontmatter rows with ids. Gates therefore assert relations over identifiers — does this workflow name an entity id `01-domain.md` defines, does every attribute in the shipped generic list appear exactly once with a disposition, does every decision carry at least one rejected alternative, a rationale, and an anchor that resolves to a defined row, does each artifact carry any rows at all, and is every inventoried row actually described in the prose below it — instead of pattern-matching prose. A prose gate can only check that a response used the expected vocabulary; keying on ids keeps every gate decidable and lets a violation message name the offending row.

**Gates are separate from the policy applied to them.** The gate functions decide only *what is wrong*; the orchestrator decides *what happens next*: violations are fed back as corrections into a bounded retry of the same stage, and an exhausted retry budget halts the arc before the next stage rather than admitting an artifact every downstream stage will read as ground truth. This is where the repo's exit-code convention lands precisely — a violation inside the retry budget is a retry input, not an operator-facing finding; failing to get a stage past its gates is a failure to finish and exits non-zero; residual advisory content on a written artifact, `pending` decisions above all, never flips the code.

**Non-interactive by construction, with `pending` as the review channel.** At an option point the stage guesses and records the guess as a decision naming the alternatives it rejected and why; a tradeoff genuinely load-bearing for downstream design is marked `pending` instead of quietly settled. There is no TTY interview to skip or hang on, so the verb behaves the same unattended as under an operator, whose loop is instead: read the artifact, edit it, re-enter at `--from-stage N`. **Accepting a `pending` decision means editing its status to the settled value by hand** — the vocabulary ships two members, and the settled one denotes *this is the decision of record*, not *a machine guessed it*. So the reported `pending` count is a live to-review queue that an operator works down to zero, not a permanent tally: without that, accepting a decision would have nowhere to be written and the count could only ever rise. A distinct `confirmed` value stays deferred because nothing downstream distinguishes an accepted guess from a settled decision yet; when a consumer needs that distinction, the vocabulary grows and the count splits with it. Non-determinism stays confined to stage *content*; control flow — which stage runs, whether its output is acceptable, what follows — stays deterministic.

**Artifacts are committed docs; only run state goes to `.plan-tool/`.** `docs/implementation-plans/roadmaps/<slug>/` puts them beside the plans and seeds that will cite them, reviewable and diffable, because a domain model and a ranked constraint set are the durable record this plan exists to produce. The run log alone lands under `.plan-tool/runs/<slug>/` with every other verb's.

**A new artifact leaf rather than an extension of the plan schema.** Roadmap artifacts are not plans — different frontmatter shape, no step/status/`depends_on` machinery, a different lifecycle, and nothing in plan discovery should resolve them. Folding them into the plan schema and manifest would push an artifact type no plan-pipeline surface reads into the plan pipeline's data contract, and every plan-side audit would inherit a shape it cannot judge. The accepted cost is a second frontmatter-parsing path, kept small by reusing the same safe-load approach rather than inventing a parser.

**A stage is data, which is what makes the rest of the arc additive.** A stage is (prompt file, output path, gate set); the domain and constraints stages shipped here are two instantiations of that shape, not two code paths. BACKLOG #208's later components and plan-derivation stages then add entries rather than orchestrator branches, and the retry loop, run log, and `--from-stage` re-entry are written once. That is this plan's main structural bet, and the reason artifact stages 1–2 are worth building behind a general skeleton instead of as a bespoke two-step script.

## References

- [Structured outputs — Claude API Docs](https://docs.claude.com/en/docs/build-with-claude/structured-outputs) — Official reference for `output_format` JSON-schema responses and strict tool inputs, which is how each stage's one directed call gets a forced, machine-checkable output contract instead of free prose.
- [argparse — Parser for command-line options, arguments and subcommands](https://docs.python.org/3/library/argparse.html) — Python stdlib reference for `add_subparsers`, `set_defaults`, and typed/choice-constrained options — the mechanics for wiring the new `roadmap` verb and its `--from-stage` / `--from-existing` flags into the existing parser.
- [YAML Ain't Markup Language (YAML™) revision 1.2.2](https://yaml.org/spec/1.2.2/) — The normative YAML grammar and type-resolution rules, needed when specifying `ROADMAP_FORMAT.md`'s frontmatter inventory so id lists, enums, and nested rows have a precisely defined serialization.
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — API reference for the library this repo already parses frontmatter with (`yaml.safe_load` in `canonical.py`), covering safe loading, error types, and dump options used by the artifact writer and its re-entry re-parse.
- [Standard Library Types — Pydantic Docs](https://docs.pydantic.dev/latest/api/standard_library_types/) — How Pydantic v2 validates `Enum` and `Literal` fields and what it raises on an unknown member — the direct mechanism for the closed-vocabulary gate on decision status and constraint disposition.
- [ISO/IEC 25010 — Product quality model (characteristics and subcharacteristics)](https://iso25000.com/index.php/en/iso-25000-standards/iso-25010) — Enumerates the nine product-quality characteristics and their subcharacteristics, the canonical source for the generic quality-attribute list the constraints stage ships inline and whose totality gate demands exactly one disposition per attribute.
- [MADR — Markdown Architectural Decision Records](https://adr.github.io/madr/) — Maintained template defining the decision-record fields (status, considered options with why each lost, decision outcome, consequences), the established shape to model `settled-by-guess` / `pending` records and their required-alternative rule on.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- **The components and plan-derivation stages** (BACKLOG #208's `roadmap-02-components`, `roadmap-03-plan-derivation`) — this plan ships the stage-as-data skeleton those instantiate; adding them here would fuse three stages' design into one plan and reproduce the over-packing this arc exists to avoid.
- **An actuator for the `FORK_STRUCTURAL` re-seed arm** — `convergence_diagnosis.py` keeps printing its hand-authored `<seed.md>` placeholder, because there is nothing to hand off until a stage emits `create` seeds.
- **Any change to plan discovery, the plan schema, or the manifest** — roadmap artifacts are a separate artifact type by deliberate design; making a plan-pipeline surface resolve or audit them contradicts the architecture decision above.
- **A standalone audit/reconcile verb over roadmap artifacts** — correctness here is the in-run deterministic gates; a `completeness`-style surface is a distinct effort that presumes a stable artifact contract this plan is still establishing.
- **A sign-off command for `pending` decisions** — the review channel is a hand edit plus `--from-stage N` re-entry, so a `scope-review` analog needs the arc's downstream consumers before its semantics are decidable.
- **Any interactive/TTY surface on the verb** — non-interactive-by-construction is the design, not a shortfall; an interview would add a path that behaves differently unattended.
- **Per-project configuration of the quality-attribute list** — the constraints stage ships one generic list inline so the totality gate stays decidable; configurability is an option only once real roadmaps show the list is wrong.
- **Authoring the concept brief `--from-existing` reads** — the brief is the operator's input to this verb, the same way a seed is `create`'s.
- **Retrofitting existing plans or seeds to cite a roadmap** — no roadmap exists yet to cite, and back-filling provenance is separable work.

## Risks

- **The gates may be unreachable by the stage prompts.** The id-keyed gates assert relations Claude has to express as frontmatter rows — every workflow naming an entity id `01-domain.md` defines, every quality attribute disposed exactly once, every constraint anchored upstream, every decision carrying a rejected alternative and a rationale — and a model that writes the prose well but the rows badly fails every retry, halting the arc before the next stage. Severity: high — the verb then produces nothing at all. Mitigation: violations are fed back as named corrections into a bounded retry of the same stage rather than a blind re-ask, and an exhausted budget exits non-zero rather than admitting an artifact every downstream stage reads as ground truth. Unresolved: neither the retry budget nor the prompts' hit rate against the contract is measured until real briefs run; if exhaustion proves systematic the remedy is prompt work or a narrower gate, and this plan designs neither.
- **The shipped quality-attribute list is a guess that the totality gate makes mandatory.** Demanding exactly one disposition per attribute forces every roadmap to dispose of attributes that may be irrelevant to it, producing filler dispositions that read like considered judgments. Severity: medium — artifact signal degrades without the run failing. Mitigation: the closed disposition vocabulary (step 1) carries an explicit *not load-bearing here* value, so the honest answer stays expressible under a total gate. Unresolved: per-project configuration of the list is out of scope, so a list that is wrong for a project stays wrong until someone edits the shipped one.
- **A disposition set that prioritizes everything clears every gate while being the checklist this plan says it is not producing.** `02-constraints.md` is promised as "quality attributes ranked as tradeoffs, not a checklist", but the artifact carries no ordering field — the three-value disposition vocabulary is the whole ranking mechanism, and `check_attribute_totality` asks only for exactly one disposition per attribute. Disposing all seven `prioritized` is therefore gate-clean, and it is also the cheapest answer under retry pressure, the same drift the non-empty gate already reasons about for the degenerate empty artifact. Severity: medium — artifact signal degrades without the run failing. Mitigation: the constraints prompt requires the ranking to trade something away and to say what it cost, so the honest shape is the one the writer is asked for; the totality gate's fifth defect also makes the inverse padding (constraining for an attribute disposed `not-load-bearing`) a violation. Unresolved: **no gate enforces that a ranking ranks.** A "at least one attribute not prioritized" check was considered and deliberately not built — it would be a new gate in a step whose fence forbids one, and a project may legitimately prioritize broadly — so an all-prioritized artifact stays valid and is accepted as operator-reviewable residue, visible in the committed diff like every other tradeoff.

- **Stage-as-data is a bet placed before the stages that would test it exist.** The (prompt file, output path, gate set) shape generalizes from two structurally alike stages — each one upstream read, one artifact written — while BACKLOG #208's components and plan-derivation stages may need fan-out, multi-file output, or rewrites of an upstream artifact, forcing back the orchestrator branches the shape exists to avoid. Severity: medium, and it lands on the next plan rather than this one. Mitigation: keep the skeleton small enough that a third stage can widen it cheaply. Unresolved: accepted deliberately — nothing here validates the shape, and `roadmap-02-components` is its first real test.
- **Hand edits are load-bearing and validated only where a gate happens to look.** Disk as the interface between stages means `--from-stage N` re-reads whatever the operator left behind, so an edit can break frontmatter or delete an entity id a downstream constraint anchors to. Severity: medium. Mitigation: gates run over the parsed artifact whatever wrote it, so a broken anchor surfaces in-run with the offending row named, and a malformed upstream artifact surfaces as a parse error at re-entry rather than silently. Unresolved: a violation message does not distinguish an operator-introduced break from a model-introduced one, so the operator reads their own edit as a stage failure.
- **Re-entry re-litigates settled decisions.** Re-running a stage regenerates its decision rows from a fresh guess, so editing `01-domain.md` and re-entering at `--from-stage 2` can quietly flip a tradeoff the operator already accepted in `02-constraints.md`. Severity: medium — the artifact stays gate-valid while disagreeing with a prior review. Mitigation: decisions are rows carrying their rejected alternatives and rationale in a committed artifact, so the flip is visible in the diff. Unresolved: nothing pins a confirmed decision across re-entry, and a pin needs the sign-off surface this plan defers.
- **`pending` marks the load-bearing tradeoffs and nothing consumes it.** The verb never blocks on `pending` — correct under the exit-code convention — and no sign-off command exists, so an arc can proceed on artifacts whose central tradeoffs were never confirmed. Severity: medium — a deliberate design gap becomes silent debt. Mitigation: `pending` is a closed-vocabulary frontmatter value, so it is greppable and countable and the run summary can report the count rather than burying it; acceptance is expressible today by hand-editing the status to the settled value, so the count is a queue an operator can work to zero. Unresolved: nothing *verifies* that a status flipped to settled was actually reviewed, so enforcement stays operator discipline until the arc's downstream consumers make sign-off semantics decidable.
- **The second frontmatter path drifts from the plan-side one.** The artifact leaf parses and writes YAML frontmatter beside the plan schema's existing path, and divergence in error handling or writer formatting yields artifacts that round-trip differently from plans. Severity: low — the two contracts are separate by design and no surface reads both. Mitigation: reuse the repo's safe-load approach rather than inventing a parser. Unresolved: the plan-side data-contract drift guard does not cover the roadmap contract, so the artifact leaf's own tests are the only check.

## Testing

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — tests covering the behavior this step changes; green before completion.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.
- step 3 (non-code) — verification appropriate to the artifacts rather than unit tests.
- step 4 (feature) — tests covering the behavior this step changes; green before completion.
- step 5 (feature) — tests covering the behavior this step changes; green before completion.
- step 6 (feature) — tests covering the behavior this step changes; green before completion.
- step 7 (feature) — tests covering the behavior this step changes; green before completion.
- step 8 (non-code) — verification appropriate to the artifacts rather than unit tests.

## Acceptance criteria

- `plan-tool roadmap <slug> --from-existing <concept.md>` on a brief whose stage responses clear every gate exits 0 and leaves exactly two artifacts on disk — `docs/implementation-plans/roadmaps/<slug>/01-domain.md` and `02-constraints.md` — each of which round-trips through `plan_tool/roadmap_artifacts.py`'s loader without error.
- The run writes no roadmap artifact under `.plan-tool/`, and writes its run log under `.plan-tool/runs/<slug>/` alongside every other verb's.
- A completed run exits 0 even when the written artifacts carry `pending` decisions or other advisory residue; the verb exits non-zero only when a stage exhausts its retry budget without passing its gates. `tests/cli/test_roadmap_cmd.py` covers both **exit-code** arms — `plan_tool/roadmap.py` never calls `sys.exit`, so the rc mapping lives in the CLI handler and is asserted there; `tests/test_roadmap.py` owns the matching **outcome-vocabulary** arms it returns.
- Exhausting a stage's retry budget halts the arc before the next stage: the test asserts the next stage's invoker is never called, and that the failed stage's violations are fed back into the retried prompt rather than the stage being blindly re-asked.
- Every gate in `plan_tool/roadmap_gates.py` is callable as `(stage envelope) -> violations` — the envelope carrying the artifact under check plus its already-parsed upstream artifacts — with no orchestrator, no invoker, and no filesystem beyond the artifacts it reads; `tests/test_roadmap_gates.py` exercises a passing and a violating case for each gate, and each violation message names the offending row's id.
- The workflow-reference gate rejects an `01-domain.md` whose workflow row names an entity id the same artifact does not define, naming both ids in the message.
- The attribute-totality gate rejects an `02-constraints.md` that omits an attribute from the shipped generic list, disposes one twice, names an attribute outside the list on a disposition or a constraint row, or carries a constraint serving an attribute the same artifact disposed *not load-bearing here*; it accepts one where every attribute carries exactly one disposition — including the *not load-bearing here* value, which is a valid disposition rather than an omission.
- The cross-artifact anchor gate rejects a constraint anchored to an id absent from `01-domain.md` **as read from disk**, so deleting an entity by hand and re-entering at `--from-stage 2` surfaces the broken anchor without re-running stage 1.
- The decision-record gate rejects a decision row carrying no rejected alternative, no rationale, or an anchor that resolves to no defined row — `pending` status exempts none of these — and the closed vocabularies for decision status and constraint disposition reject an unknown member with a message naming the offending value. An anchor resolves against row ids only: entity, rule, and workflow ids in `01-domain.md`; the constraints artifact's own row ids plus the upstream domain's in `02-constraints.md`. A quality attribute is reachable through its disposition row's id and never through its bare name. Quality-attribute membership is deliberately *not* a parser check: an unknown attribute is reported by the totality gate with its row id.
- The non-empty gate rejects a domain artifact declaring no entities or no workflows, and a constraints artifact carrying dispositions but no constraint rows; the inventory-prose gate rejects a frontmatter row whose id appears nowhere in the body below the fence.
- `plan-tool roadmap <slug> --from-stage 2` invokes only stage 2, reads stage 1's artifact from disk (a hand-edited entity added there is visible to the stage and its gates), and leaves `01-domain.md` unmodified.
- Re-entry re-runs each loaded upstream artifact through **its own stage's gate set**, not merely the parser, and fails pre-flight — before any Claude call, without re-invoking the upstream stage — when one violates it, naming the offending row. A hand edit that breaks a relation inside `01-domain.md` stops the run rather than becoming ground truth for `02-constraints.md`.
- Re-entry rewrites every artifact stage from `N` up, so it overwrites like any other run: the result records the stage numbers whose write replaced an existing artifact, and the warning names `--from-stage <lowest overwritten + 1>` — or, when that exceeds the last artifact stage, says a re-run rewrites everything and names copying the file aside.
- Import layering holds and is asserted by test: `roadmap_artifacts.py` imports no first-party module, `roadmap_gates.py` imports no first-party module but `roadmap_artifacts`, `plan_tool/roadmap.py` is the only module in the group that shells out, and `plan_tool/cli/roadmap_cmd.py` contains no assembly, gate, or retry logic.
- `plan_tool/roadmap.py` carries the repo's `invoker=` seam defaulting to the real CLI shell-out, and `tests/test_roadmap.py` passes under `tests/conftest.py`'s autouse backend gate with no `@pytest.mark.allow_real_claude` opt-out.
- A stage is data, not a code path: a test registers a synthetic third stage as a full `RoadmapStage` entry — stage number, prompt file, output path, parser, gate set, and log name — and drives it through the same orchestrator with no change to control flow.
- A roadmap run leaves plan discovery untouched — `.plan-tool/plans.json` is byte-identical afterward and `plan-tool list` resolves no roadmap artifact.
- `ROADMAP_FORMAT.md` specifies the frontmatter inventory of both artifacts and names the code that enforces each rule, so every gate in `roadmap_gates.py` is traceable to a stated contract clause.
- `plan-tool roadmap --help` documents the verb's flags; `plan-tool --help` lists it in the intent-organized catalog (golden `tests/cli/package_surface_help.golden.txt`); `docs/cli/roadmap.md` regenerates clean under `python -m plan_tool.cli_reference --write` with `tests/cli/test_cli_reference.py` green; and `plan-tool validate`'s no-Claude catalog check passes with the verb's new `CAPABILITIES.md` entry mapped to its MISSION principle(s).
- `USE_CASES.md`, `RUNBOOK.md`, `integrations/claude/SKILL.md`, and `CLAUDE.md` describe the shipped verb and its non-interactive/`--from-stage` operator loop, and BACKLOG #208 is reconciled — arc position 01 recorded as shipped, the components and plan-derivation positions left as the remaining arc.

## Deferred

- **Calibrating the retry budget and the prompts' hit rate against the gates** — the budget ships as a fixed constant because nothing measures how often a stage response clears the id-keyed gates until real concept briefs run; if exhaustion proves systematic, the remedy (prompt work or a narrower gate) is a follow-up this plan deliberately does not design.
- **Pinning a confirmed decision across `--from-stage` re-entry** — re-running a stage regenerates its decision rows from a fresh guess, so a tradeoff an operator already accepted can flip; a pin presumes the sign-off surface whose semantics stay undecidable until the arc's downstream consumers exist.
- **Distinguishing operator-introduced from model-introduced gate violations** — the violation message names the offending row either way, so an operator can read the consequence of their own hand edit as a stage failure; separating the two is message work worth doing once the re-entry loop has real use.
- **Extending the data-contract drift guard to the roadmap frontmatter** — `tests/test_data_contract.py` covers the plan-side persisted schemas only, leaving the artifact leaf's own tests as the sole check; adding coverage is cheap but premature while the artifact contract is still being established here.
- **Widening the stage shape for fan-out, multi-file output, or upstream rewrites** — the (prompt file, output path, gate set) entry generalizes from two structurally alike stages, and the shape stays deliberately small until BACKLOG #208's components stage shows which of those it actually needs.
