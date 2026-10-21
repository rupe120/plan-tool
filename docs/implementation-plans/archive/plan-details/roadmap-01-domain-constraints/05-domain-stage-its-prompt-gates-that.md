> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Add the domain stage: its prompt and the gates that check `01-domain.md`

## Summary

This step turns the empty stage table from step 4 into a working one-stage arc. It creates `plan_tool/prompts/roadmap-domain.md` — the prompt that asks for `01-domain.md`'s entities, business rules, workflows, and decision rows — adds a single `RoadmapStage` entry to `STAGES` in `plan_tool/roadmap.py`, and extends `tests/test_roadmap.py`. The main design decision is that **the prompt file states the artifact's shape in its own text**: the verb runs inside a consuming repo that has no copy of `ROADMAP_FORMAT.md`, so the prompt cannot point at that doc and must be self-contained — and a test pins the prompt's wording against step 1's constants so the restatement cannot drift. On green, a run over the shipped table turns a conforming stage response into a gate-clean `01-domain.md` on disk and stops there, with the run loop in `plan_tool/roadmap.py` carrying no new branch.

## Table of Contents

- [Summary](#summary) — what the step ships and the one design decision behind it.
- [Why](#why) — why the first real stage has to land before anything is proven.
- [Input](#input) — the four upstream steps this one consumes and what it may assume.
- [Files (creates vs edits)](#files-creates-vs-edits) — one new prompt file plus two edits.
- [Implementation](#implementation) — the stage row, the prompt's contents, the anti-drift guard, and the rules that are not free to vary.
- [Tests](#tests) — the 19 new cases, the two step-4 cases this step rewrites, and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — checkable facts a reviewer can run.
- [References](#references) — the docs worth reading for the output contract and the decision rows.
- [Applicable guardrails](#applicable-guardrails) — the plan-level fences that bind this step.
- [Deferred](#deferred) — what other steps own, and the drift question routed away.

## Why

Step 4 shipped a run loop, a retry budget, a writer, a run log, and `--from-stage` re-entry against an **empty** stage table. Every test drives fake stages with canned parsers and canned gate sets, so nothing yet shows that a real prompt can produce an artifact the real gates accept — the plan's top risk, stated plainly in its Risks section, is that the id-keyed gates are unreachable by the prompts. This step is the first evidence either way. It is also the first test of the plan's structural bet: if adding the domain stage means one entry in a tuple plus one new file, the stage-as-data design holds; if it means a branch in the loop, it does not, and step 6 will cost twice as much. Landing the domain stage alone — rather than both stages at once — keeps that answer readable in one diff.

## Input

This step consumes the outcomes of steps 1, 2, 3, and 4. **The landed names win over any name this file suggests** — open each module and use what actually shipped.

- **Step 4 produces the loop and the row type** — `plan_tool/roadmap.py`: the frozen `RoadmapStage` record, the `STAGES` tuple, `run_roadmap`, the attempt budget constant, the tolerant lift, the corrections block, and the atomic writer. This step adds a row; it changes no control flow.
- **Step 4 also fixes the prompt variable map** — every stage gets the same small set: the slug, the brief text, and the rendered text of every artifact below this stage, always loaded back from disk on the fresh path as well as on re-entry. It is substituted with `string.Template.safe_substitute`. The domain prompt's placeholders must be a subset of that map. Read `plan_tool/roadmap.py` for the exact key spellings; do not guess them from this file.
- **Step 1 produces the artifact contract** — `plan_tool/roadmap_artifacts.py`: the domain path helper, the domain parser, the filename constants, the decision-status vocabulary, and the field names on every row type. The prompt describes exactly these names, and the stage row references these functions rather than wrapping them.
- **Step 2 produces the domain gate set** — `plan_tool/roadmap_gates.py`: the aggregate the stage row holds, and the **five** gates that apply to `01-domain.md`: entity references (**from business rules as well as workflows** — every rule names the entity ids it governs), duplicate row ids, decision records (alternatives, rationale, **and a resolving anchor**), **artifact non-empty** (at least one entity *and* at least one workflow), and **inventory-has-prose** (every frontmatter row id appears in the body below the fence). The prompt's requirements are written so a compliant response clears all five. Every gate the prompt does not state is retry budget spent discovering a rule the model was never told — the plan's top-named risk.
- **Step 3 produces `ROADMAP_FORMAT.md`** — the human-facing schema reference, at the root of **this** repo. It is the source the prompt author reads while writing; it is **not** something the prompt can tell the model to open, because `plan-tool` is installed as a tool and the verb runs in whatever repo the operator is in. No prompt under `plan_tool/prompts/` cites a `*_FORMAT.md` doc today, for exactly this reason.
- **What this step cannot verify.** Nothing here measures how often a real model clears the gates on the first attempt. The plan names that as an open risk and defers measuring it; these tests drive canned responses through the real parser and the real gates, which proves the contract is *satisfiable*, not that it is *usually satisfied*.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/prompts/roadmap-domain.md` — the domain stage's prompt, described under [Implementation](#implementation). Files in `plan_tool/prompts/` ship as package data with the wheel, like the 27 templates already there; no packaging change is needed.
- **Existing files (edits only):**
  - `plan_tool/roadmap.py` — add one `RoadmapStage` entry to `STAGES`. Nothing else: no new field on the row type, no change to the variable map, no change to the loop, the lift, the retry policy, the writer, or the run log.
  - `tests/test_roadmap.py` — add the cases listed under [Tests](#tests), and rewrite the two step-4 cases that pin the empty table (`test_stage_table_ships_empty` and `test_empty_stage_table_completes_writing_nothing`). Every other step-4 case injects its own stage table and stays untouched.

No `TESTING.md` row: step 4 registered `run_roadmap`'s `invoker=` seam, and this step adds no second backend seam.

## Implementation

### The stage row

- **One entry in `STAGES`, holding step 1's and step 2's symbols directly.** Stage number 1, a short name for the run log (`domain` reads well), the prompt filename `roadmap-domain.md`, step 1's domain path helper, step 1's domain parser, and step 2's domain gate set. The row holds references; it never wraps a symbol in an adapter, because an adapter is where per-stage knowledge starts creeping back toward the loop.
- **Delete step 4's placeholder comment** naming steps 5 and 6 as the tuple's future entries, and leave a one-line comment saying step 6's constraints stage joins it. Keep it short.
- **The loop diff must be empty.** If adding this stage seems to need a branch, a special case in prompt assembly, or a second write path, stop — that belongs as a field on `RoadmapStage`, and the plan's structural bet is what is being tested here. `rg 'stage\.(name|number) ==' plan_tool/roadmap.py` still returns nothing after this step.

### The prompt file

Write `plan_tool/prompts/roadmap-domain.md` as a self-contained brief for one directed call. `plan_tool/prompts/detail-jira.md` is the closest shape in the repo — a strict, closed output contract in under a hundred lines — and `plan_tool/prompts/distill-seed.md` is the precedent for the *work from the supplied text, do not inspect the codebase* stance. Cover these subjects; the exact wording and section split are yours:

- **What the artifact is and who reads it.** `01-domain.md` is the first of a roadmap's staged architecture artifacts: entities, business rules, and workflows for one project. Its readers are the next stage (which anchors constraints to these ids) and a human who may hand-edit it and re-enter the arc.
- **The input is the concept brief.** Substitute it through step 4's brief variable. Say plainly: build the domain model from the brief; do not read the repository, and do not invent scope the brief does not imply. A greenfield concept has no code to inspect, and a stage that goes reading is slower and less reproducible for nothing.
- **The output format, strictly.** The response is the artifact and nothing else — no preamble, no closing remark, no code fence around the file. The first characters are the opening `---` of the frontmatter. Step 4's lift tolerates a stray fence or preamble, but tolerance is the safety net, not the contract.
- **The frontmatter inventory**, named field by field with step 1's spellings and **omitting no required key**: entity rows; business-rule rows **carrying the entity ids each governs**; workflow rows carrying the entity ids each touches; and decision rows with their chosen option, rejected alternatives with a reason each, rationale, status, and **anchor**. A required key the prompt never names is a key the model omits, and step 1's parser raises on it — an attempt spent on a rule the writer was never given.
- **The rules the gates check, stated as requirements the writer must meet — all five, because the prompt claims to cover all five.** Every **workflow *and* business rule** names at least one entity id defined in the same artifact; ids are unique across all row kinds, not just within one kind; every decision names at least one rejected alternative with its own reason, carries a non-empty rationale, **and carries an anchor that resolves to an entity, rule, workflow, *or decision* id in this artifact** — `check_decision_records` resolves against every row kind including `decisions`, so a decision-to-decision anchor is valid and the prompt says so; the artifact declares **at least one entity and at least one workflow**; and **every frontmatter row id appears in the prose body** (see the prose-body bullet below). Say why for each — a workflow touching nothing is not a workflow, a rule connected to no entity breaks the traceability chain constraints later anchor into, an unanchored decision names a tradeoff but not the thing it binds, and an empty artifact clears every row-wise rule vacuously. A writer who understands the rule produces conforming rows more often than one following a checklist.
- **Decisions and `pending`.** At every option point, take a position and record it as a decision row rather than hedging in prose. Mark a tradeoff `pending` when it genuinely binds downstream design and the brief does not settle it; use the settled status otherwise. Say that `pending` is never a failure — it is how the operator is asked to confirm something.
- **The prose body, and the one gate that reads it.** Everything after the closing `---` is a short narrative of the domain that the frontmatter rows cannot carry. It is checked: `check_inventory_has_prose` requires **every frontmatter row id to appear in the body**, so the narrative has to name each entity, rule, workflow, and decision by its id while describing it. Say both halves — name every row id, and do not re-tabulate the rows as prose — because a writer told the body is unread writes a narrative naming no ids, fails the gate on every attempt, and the arc halts.
- **Writing style.** Short, plain, present tense — the same directive `detail-jira.md` carries.

Two content gotchas worth spending a sentence on each in the file itself:

- **Keep the worked example a visible skeleton — but a gate-clean one.** An example realistic enough to be plausible gets copied, and copied rows clear every gate while describing the wrong project. Placeholder ids (`entity-1`) and `<one line>` bodies make the shape clear without offering anything to lift. The skeleton must still satisfy the gates it illustrates: every row carries its required keys, at least one entity and one workflow are present, and **the example's own prose body names every row id it declares**, because a model follows the example over the prose and an example failing `check_inventory_has_prose` teaches exactly the mistake that halts the arc.
- **Escape any literal `$`.** `safe_substitute` leaves unknown `${name}` text alone, but a stray `$` is still a placeholder character; write `$$` when the prose needs a dollar sign.

### Keeping the prompt and the code contract in step

The prompt restates names that live in `plan_tool/roadmap_artifacts.py`. That restatement is a real drift risk — step 1 flagged the same class of risk for step 6's attribute list.

- **Guard it with a test, not a convention.** Assert that the prompt text contains every required row-key name step 1's domain rows declare, and both decision-status values. A renamed field then reddens this suite instead of silently producing prompts that ask for the old spelling.
- **Guard the example the same way.** The skeleton artifact embedded in the prompt goes through step 1's real parser and step 2's real domain gate set in the suite. A prompt whose own example would fail the gates it describes is the worst thing this step could ship — the same check step 3 applies to `ROADMAP_FORMAT.md`'s examples.
- **The rejected alternative: generate the schema block from the constants** and inject it as a new stage-table field. It would remove the drift risk outright, but it moves prompt prose into Python, needs a renderer both stage prompts share, and widens step 4's deliberately uniform variable map. Prompts stay prose; the test carries the guarantee. Route the shared-renderer question to [Deferred](#deferred).

### Constraints that are not free to vary

- **No second stage.** `STAGES` gains exactly one entry. `plan_tool/prompts/roadmap-constraints.md` and the constraints row are step 6's.
- **No new gate and no gate edit.** `plan_tool/roadmap_gates.py` carries no diff. If the prompt seems to need a rule the gates do not check, that is a prompt directive, not a new gate.
- **No new module, no CLI wiring, no docs sweep.** Steps 7 and 8 own those.
- **No interactive surface.** Nothing here adds `input()`, an `isatty` check, or a confirm gate to `plan_tool/roadmap.py`.
- **The prompt never tells the model to write a file.** The stage response is text; step 4's writer owns disk.

## Tests

All cases live in `tests/test_roadmap.py`, beside step 4's. Most are plain unit tests driving `run_roadmap` over the shipped table with a fake invoker returning canned artifact text. Mark the end-to-end cases that drive the real parser, the real gate set, and real disk writes `@pytest.mark.integration`; keep the rest unmarked. The suite passes under `tests/conftest.py`'s autouse gate with no `@pytest.mark.allow_real_claude` opt-out.

This is a `feature` step in a plan with `enforce_step_tests: true`, so the test-authoring gate applies and these cases land with the prompt and the table entry.

### Tests for this step

19 new cases, plus two of step 4's rewritten. Every one must be green before this step is finished.

**The stage row and the shipped table**

- `test_stage_table_ships_the_domain_stage` — replaces step 4's `test_stage_table_ships_empty`: `STAGES` has exactly one entry, and it is stage 1.
- `test_shipped_table_run_writes_the_domain_artifact` — replaces step 4's `test_empty_stage_table_completes_writing_nothing`: a canned conforming response puts a file at step 1's domain path.
- `test_shipped_table_run_writes_no_constraints_artifact` — the arc ends after stage 1; step 6 adds the second.
- `test_domain_stage_row_reuses_step_ones_path_helper_and_parser` — the row's fields are the landed symbols themselves, not local wrappers.
- `test_domain_stage_row_carries_the_landed_domain_gate_set` — the row's gate set is step 2's domain aggregate.

**The prompt file**

- `test_domain_prompt_template_ships_under_prompts_dir` — the file exists where the stage row says it does.
- `test_domain_prompt_placeholders_are_a_subset_of_the_variable_map` — every `${name}` in the file is a key step 4's loop supplies.
- `test_domain_prompt_renders_with_no_unresolved_placeholder` — a rendered stage-1 prompt contains no leftover `${`.
- `test_brief_text_reaches_the_domain_prompt` — a marker string in the brief appears in the rendered prompt.
- `test_domain_prompt_names_every_required_row_key` — each required field name on step 1's domain row types appears in the prompt text, including the business-rule row's entity ids and the decision row's anchor.
- `test_domain_prompt_names_both_decision_status_values` — the settled and `pending` spellings both appear.
- `test_domain_prompt_states_every_domain_gate_rule` — parametrized over the gates in step 2's landed domain aggregate, each gate's subject appears in the prompt text. Parametrizing over the aggregate rather than a hardcoded list is the point: a gate added to the set without a matching prompt sentence reddens this case instead of costing retry budget at run time.

**The prompt's embedded example**

- `test_prompt_example_parses_through_the_domain_parser` — the skeleton artifact in the prompt loads into typed rows without raising.
- `test_prompt_example_clears_the_domain_gate_set` — the same parsed example produces an empty violation list.

**End to end against the real gates**

- `test_conforming_response_clears_the_real_domain_gates_and_writes` — one invoker call, one artifact, the completed outcome.
- `test_written_domain_artifact_reparses_through_the_loader` — the bytes on disk load back through step 1's loader.
- `test_undefined_entity_reference_is_retried_with_the_gate_message` — a response whose workflow names an undefined entity produces a second attempt whose prompt carries that violation's message verbatim.
- `test_always_violating_domain_response_exhausts_and_writes_nothing` — the budget is spent, no file appears, and the result names stage 1.
- `test_pending_decision_does_not_fail_the_domain_stage` — a conforming artifact whose decisions are all `pending` still completes and is written.

## Acceptance criteria

- `plan_tool/prompts/roadmap-domain.md` exists; `plan_tool/roadmap.py` and `tests/test_roadmap.py` are the only other files that change.
- `STAGES` in `plan_tool/roadmap.py` has exactly one entry, whose prompt filename, path helper, parser, and gate set are the landed symbols from steps 1 and 2.
- The diff to `plan_tool/roadmap.py` is the stage entry and its comment — no change to `RoadmapStage`, the variable map, the attempt loop, the lift, the writer, the run log, or the result type. `rg 'stage\.(name|number) ==' plan_tool/roadmap.py` returns nothing.
- A run over the shipped table with a canned conforming response writes `<plans_dir>/roadmaps/<slug>/01-domain.md`, returns the completed outcome, and writes no `02-constraints.md`.
- The written file loads back through step 1's domain loader without error and produces no violations from step 2's domain gate set.
- Every `${name}` in `plan_tool/prompts/roadmap-domain.md` is a key step 4's loop supplies, and a rendered stage-1 prompt contains no leftover `${`.
- The prompt text contains every required row-key name from step 1's domain row types and both decision-status values.
- The prompt's embedded example artifact parses through step 1's domain parser and returns an empty violation list from step 2's domain gate set.
- A response whose workflow names an undefined entity id is retried with that gate's message quoted verbatim as a `- {message}` bullet; a response that never clears the gates spends the whole budget, writes nothing, and stops the run.
- `rg 'input\(|isatty' plan_tool/roadmap.py` returns nothing, and the prompt file contains no instruction to write, edit, or create a file.
- The 19 new cases pass under `uv run pytest tests/test_roadmap.py -q`, and the full suite (`uv run pytest tests/ -q`) stays green.
- `plan_tool/roadmap_artifacts.py`, `plan_tool/roadmap_gates.py`, `plan_tool/renderer.py`, `ROADMAP_FORMAT.md`, `TESTING.md`, and everything under `plan_tool/cli/` carry no diff.

## References

- [Structured outputs — Claude API Docs](https://docs.claude.com/en/docs/build-with-claude/structured-outputs) — what a forced, machine-checkable output contract looks like; read it when deciding how strictly the prompt should pin the response shape before the lift.
- [MADR — Markdown Architectural Decision Records](https://adr.github.io/madr/) — the decision-record fields (status, considered options with why each lost, outcome); useful wording for the prompt's decision-row instructions and its `pending` guidance.
- [YAML Ain't Markup Language (YAML™) revision 1.2.2](https://yaml.org/spec/1.2.2/) — type-resolution rules for the frontmatter the prompt asks for, so the id lists and enum values it describes serialize one way.

## Applicable guardrails

- **No components or plan-derivation stages.** One stage entry, one prompt file. No `03-components.md` path, row kind, or prompt, and no seed emission.
- **No actuator for the `FORK_STRUCTURAL` re-seed arm.** `plan_tool/convergence_diagnosis.py` keeps its hand-authored placeholder; nothing here writes a `create` seed.
- **No change to plan discovery, the plan schema, or the manifest.** This step writes one prompt file and one tuple entry. Nothing reads or writes `plans.json`.
- **No standalone audit or reconcile surface.** Correctness is the in-run gates. No report, no sidecar, no findings roll-up.
- **No sign-off command for `pending` decisions.** The prompt tells the model when to mark a decision `pending`; nothing in this step consumes, blocks on, or confirms one.
- **No interactive or TTY surface.** The stage behaves the same unattended as under an operator.
- **No per-project configuration of the quality-attribute list.** That list belongs to the constraints stage; this prompt does not mention it and reads no config or environment variable.
- **The concept brief is the operator's input.** The prompt reads the brief and builds a domain model from it. It never rewrites, distills, or asks for a better brief.

## Deferred

- **The constraints stage** — step 6 creates `plan_tool/prompts/roadmap-constraints.md`, adds the second `STAGES` entry, and brings the attribute-totality and cross-artifact anchor gates into play. This step's arc ends after `01-domain.md`.
- **The CLI verb, its flags, and `CAPABILITIES.md`** — step 7. Nothing here parses argv or maps an outcome to an exit code.
- **Operator docs and the BACKLOG #208 reconciliation** — step 8.
- **Measuring how often a real model clears the gates first try** — the plan names this as an open risk and designs no instrument for it. These tests prove the contract is satisfiable; a hit-rate measurement needs real briefs and a place to record them.
- **Generating the prompt's schema block from step 1's constants** — it would need a shared renderer both stage prompts use and a wider variable map than step 4 settled on. That is a cross-step change this step cannot mint; route it to reconcile or a `BACKLOG.md` entry if the pinning test proves too coarse.
- **Framework lenses** (BACKLOG #208's `roadmap-04-framework-lenses`) — the domain prompt ships one generic shape with no lens selection and no `--framework` hook.
- **Durable logging of rejected stage responses** — step 4 routed this to reconcile; the run log's per-attempt events remain the accounting.
- **Extending `tests/test_data_contract.py` to the roadmap contract** — the plan defers this while the artifact contract is still settling.
