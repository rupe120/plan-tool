> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Add the constraints stage: its prompt, the attribute-totality gate, and the cross-artifact anchor gate

## Summary

This step completes the arc. It creates `plan_tool/prompts/roadmap-constraints.md` — the prompt that asks for `02-constraints.md`'s quality-attribute dispositions, constraints, and decision rows — adds the second `RoadmapStage` entry to `STAGES` in `plan_tool/roadmap.py`, and extends `tests/test_roadmap.py`. The main design decision is that **the constraints prompt is the first one that reads an upstream artifact**: the rendered `01-domain.md` arrives through step 4's uniform variable map, and the prompt tells the model to copy anchor ids out of it verbatim — which is what makes the cross-artifact anchor gate reachable instead of guaranteed to fail. On green, a run over the shipped table writes both artifacts, the two gates that need two stages to run finally run, `--from-stage 2` works against real stages, and the run loop in `plan_tool/roadmap.py` still has no branch on stage identity.

## Table of Contents

- [Summary](#summary) — what the step ships and the one design decision behind it.
- [Why](#why) — why the second stage is where three separate bets get their verdict.
- [Input](#input) — the five upstream steps this one consumes and what it may assume.
- [Files (creates vs edits)](#files-creates-vs-edits) — one new prompt file plus two edits.
- [Implementation](#implementation) — the stage row, the prompt's contents, the anti-drift guard, and the rules that are not free to vary.
- [Tests](#tests) — the 31 new cases, the two step-5 cases this step rewrites, and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — checkable facts a reviewer can run.
- [References](#references) — the docs worth reading for the attribute list and the decision rows.
- [Applicable guardrails](#applicable-guardrails) — the plan-level fences that bind this step.
- [Deferred](#deferred) — what other steps own, and the drift question routed away.

## Why

Two of the seven gates in `plan_tool/roadmap_gates.py` have never run inside a real arc. The attribute-totality gate needs a constraints artifact, and the cross-artifact anchor gate needs both artifacts at once — neither is reachable from a one-stage table, so step 5 left them exercised only by hand-built fixtures in `tests/test_roadmap_gates.py`. They are also the two gates the plan's own acceptance criteria single out. Three bets settle here at the same time:

- **Step 2's one-envelope decision.** Two gates need the upstream domain — the constraint-anchor gate, and the decision-record gate whenever a constraints decision anchors to a domain id. Step 2 gave every gate one envelope-shaped call signature specifically so step 4's stage table would not need a branch for either. This step is the first time that shape carries gates that genuinely need more than their own artifact.
- **Step 4's "fill the envelope with every artifact below this stage".** Stage 2 is the first stage with a non-empty upstream, so it is the first proof the loop hands the envelope down without learning which gate wants what.
- **The plan's structural bet.** If the second stage is one tuple entry plus one prompt file, stage-as-data holds and BACKLOG #208's later stages are cheap. If it needs a branch, the bet failed, and that failure is worth seeing in this diff rather than in the next plan.

## Input

This step consumes the outcomes of steps 1, 2, 3, 4, and 5. **The landed names win over any name this file suggests** — open each module and use what actually shipped.

- **Step 1 produces the constraints half of the artifact contract** — `plan_tool/roadmap_artifacts.py`: the constraints path helper, the constraints parser, `CONSTRAINTS_FILENAME`, the ordered quality-attribute tuple, the constraint-disposition vocabulary (including `not-load-bearing`), the decision-status vocabulary, and the field names on the disposition, constraint, and decision rows. The prompt restates exactly these names; the stage row references these functions.
- **Step 2 produces the constraints gate set** — `plan_tool/roadmap_gates.py`: the aggregate the stage row holds, plus the **six** gates that apply to `02-constraints.md`: attribute totality, cross-artifact anchors, duplicate row ids, decision records (alternatives, rationale, **and a resolving anchor**), **artifact non-empty**, and **inventory-has-prose**. The prompt's requirements are written so a compliant response clears all six. The non-empty gate is the one to state loudest: **dispositions alone do not satisfy it — at least one constraint row is required**, so the degenerate reply of seven `not-load-bearing` rows and zero constraints must be ruled out by the prompt, not discovered by the gate.
- **Step 4 produces the loop, the row type, and the variable map** — `plan_tool/roadmap.py`. The map carries the slug, the brief text, and the rendered text of every artifact below this stage, always loaded back from disk — a fresh run re-reads what stage 1 just wrote rather than carrying it in memory, so this stage sees identical bytes either way. **Read the module for the exact key spellings; do not guess them from this file.** This step adds a row and changes no control flow.
- **Step 5 produces the domain stage and the pattern to copy** — the stage-1 row, `plan_tool/prompts/roadmap-domain.md`, and the containment tests that pin that prompt against step 1's constants. Step 5 also already rewrote step 4's two empty-table cases; this step rewrites two of step 5's in the same way.
- **Step 3 produces `ROADMAP_FORMAT.md`** — the schema reference at the root of **this** repo. It is what the prompt author reads while writing. It is **not** something the prompt can tell the model to open: `plan-tool` is installed as a tool and the verb runs in whatever repo the operator is in. `rg -l 'FORMAT\.md' plan_tool/prompts/` returns nothing across all 27 templates at HEAD, and that is the rule, not an oversight.
- **The domain artifact's ids are the anchor target set.** Anchors resolve against the union of entity, rule, and workflow ids in `01-domain.md` — not entities alone. The prompt must say so, because a model that anchors only to entities is writing valid constraints that pass but ignores two thirds of the available anchors.
- **What this step cannot verify.** Nothing here measures how often a real model clears the gates on the first attempt. The tests drive canned responses through the real parser and the real gates, which proves the contract is *satisfiable*, not that it is *usually satisfied*. The plan names the hit rate as an open risk and defers measuring it.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/prompts/roadmap-constraints.md` — the constraints stage's prompt, described under [Implementation](#implementation). Files under `plan_tool/prompts/` ship as package data with the wheel; no packaging change is needed.
- **Existing files (edits only):**
  - `plan_tool/roadmap.py` — add one `RoadmapStage` entry to `STAGES`, and delete step 5's comment saying step 6 joins the tuple. Nothing else: no new field on the row type, no change to the variable map, the loop, the lift, the retry policy, the writer, the run log, or the result type.
  - `tests/test_roadmap.py` — add the cases listed under [Tests](#tests), and rewrite the two step-5 cases that pin a one-stage table (`test_stage_table_ships_the_domain_stage` and `test_shipped_table_run_writes_no_constraints_artifact`). Every other case in the file either injects its own stage table or is scoped to stage 1, and stays untouched.

No `TESTING.md` row: step 4 registered `run_roadmap`'s `invoker=` seam, and this step adds no second backend seam.

## Implementation

### The stage row

- **One entry in `STAGES`, holding step 1's and step 2's symbols directly.** Stage number 2, a short name for the run log (`constraints` reads well), the prompt filename `roadmap-constraints.md`, step 1's constraints path helper, step 1's constraints parser, and step 2's constraints gate set. The row holds references; it never wraps a symbol in an adapter, because an adapter is where per-stage knowledge starts creeping back toward the loop.
- **Delete step 5's placeholder comment.** The table is complete for this plan. Leave at most a one-line comment saying BACKLOG #208's later stages append here; keep it short.
- **The loop diff must be empty.** If adding this stage seems to need a branch, a special case in prompt assembly, an extra variable for the upstream artifact, or a second envelope shape, stop — that belongs as a field on `RoadmapStage`, and the plan's structural bet is exactly what is being tested. `rg 'stage\.(name|number) ==' plan_tool/roadmap.py` still returns nothing after this step.

### The prompt file

Write `plan_tool/prompts/roadmap-constraints.md` as a self-contained brief for one directed call. `plan_tool/prompts/detail-jira.md` is the closest shape in the repo — a strict, closed output contract in 82 lines — and `plan_tool/prompts/distill-seed.md` is the precedent for the *work from the supplied text, do not inspect the codebase* stance. Cover these subjects; the exact wording and section split are yours:

- **What the artifact is and who reads it.** `02-constraints.md` ranks quality attributes as tradeoffs, not a checklist. Its readers are BACKLOG #208's later stages and a human who may hand-edit it and re-enter the arc.
- **There are two inputs, and the domain artifact is the one that governs.** The brief gives the project; the rendered `01-domain.md` gives the ids. Say plainly: read the entity, rule, and workflow ids in the supplied domain artifact and anchor every constraint to one or more of them, copying each id exactly as written. Say why — a made-up id fails the anchor gate and costs an attempt. Do not read the repository and do not invent scope the brief does not imply.
- **The attribute list, restated in full.** Name every attribute in step 1's shipped tuple, and require exactly one disposition row for each. Name all three disposition values. Say directly that `not-load-bearing` is a real, expected answer for an attribute this project genuinely does not trade on — it is what keeps a total gate satisfiable without filler, and a prompt that shames it produces seven invented tradeoffs that read like considered judgments.
- **Require the ranking to rank.** The artifact carries no ordering field, so the dispositions *are* the ranking — and disposing all seven `prioritized` is gate-clean while being exactly the checklist this artifact exists not to be. Tell the writer plainly: a ranking that prioritizes everything has ranked nothing; name what this project trades away and say in the prose body what that costs. **No gate enforces this** (see the plan's Risks entry — a "not everything prioritized" check would be a new gate this step's fence forbids, and broad prioritization can be legitimate), so the prompt is the only place the rule can be stated. That makes stating it load-bearing rather than stylistic.
- **The frontmatter inventory**, field by field with step 1's spellings and **omitting no required key**: disposition rows; constraint rows carrying their anchor ids and the attribute each serves; and decision rows with their chosen option, rejected alternatives with a reason each, rationale, status, and **anchor**. A required key the prompt never names is a key the model omits, and step 1's parser raises on it — an attempt spent on a rule the writer was never given.
- **The rules the gates check, stated as requirements the writer must meet — all six, because the prompt claims to cover all six.** Every attribute disposed exactly once and nothing outside the list; **every constraint's `attribute` a member of that same list, and never one this artifact disposed `not-load-bearing`** — declaring a concern deliberately traded away and then constraining for it is incoherent, and it is the shape a model produces when it pads to satisfy totality; every constraint anchored to at least one id defined in `01-domain.md`; ids unique across all row kinds; every decision naming at least one rejected alternative with its own reason, a non-empty rationale, **and an anchor that resolves to a row id in this artifact — a disposition row's id, a constraint id — or to an `01-domain.md` id**; **at least one constraint row** (dispositions alone do not satisfy the non-empty gate); and **every frontmatter row id appearing in the prose body** (see the prose-body bullet below). Give the reason for each — a writer who understands a rule produces conforming rows more often than one following a checklist.
- **Decisions and `pending`.** Take a position at every option point and record it as a decision row rather than hedging in prose. Mark a tradeoff `pending` when it genuinely binds downstream design and the brief does not settle it. Say that `pending` is never a failure — it is how the operator is asked to confirm something.
- **The output format, strictly.** The response is the artifact and nothing else — no preamble, no closing remark, no code fence around the file. The first characters are the opening `---`. Step 4's lift tolerates a stray fence or preamble, but tolerance is the safety net, not the contract.
- **The prose body, and the one gate that reads it.** Everything after the closing `---` is a short narrative of why this ranking and not another. It is checked: `check_inventory_has_prose` requires **every frontmatter row id to appear in the body**, so the narrative has to name each disposition, constraint, and decision by its id while explaining it. Say both halves — name every row id, and do not re-tabulate the rows as prose — because a writer told the body is unread writes a narrative naming no ids, fails the gate on every attempt, and the arc halts.
- **Writing style.** Short, plain, present tense — the same directive `detail-jira.md` carries.

Two content gotchas worth a sentence each in the file itself:

- **Keep the worked example a visible skeleton, and make it complete.** Placeholder ids (`constraint-1`), placeholder anchors (`entity-1`), and `<one line>` bodies keep the shape clear without offering anything to copy wholesale. But the example must dispose **every** attribute — showing two and trailing off with "and so on" ships an example that fails the totality gate it illustrates, and a model follows the example over the prose. One line per disposition row keeps a complete example short. It must also carry **at least one constraint row** (dispositions alone fail the non-empty gate), **no constraint serving an attribute the example disposed `not-load-bearing`**, and a **prose body naming every row id it declares** — an example that fails any gate it illustrates teaches the mistake that halts the arc.
- **Escape any literal `$`.** `safe_substitute` leaves an unknown `${name}` in place, and a stray `$` is still a placeholder character; write `$$` when the prose needs a dollar sign. No template at HEAD contains a bare `$`, so there is no in-repo example to copy.

### Keeping the attribute list and the prompt in step

Step 1 named this drift risk and routed it here: a static prompt file cannot import a constant, so `plan_tool/prompts/roadmap-constraints.md` restates the attribute list that `plan_tool/roadmap_artifacts.py` owns. That restatement is sharper than step 5's, because the totality gate turns a stale prompt into a **guaranteed stage failure**: list six of seven attributes and every response omits one, every attempt fails the gate, the budget is spent, and the arc halts — with a violation message blaming the model for something the prompt never asked for.

- **The repo already has this bug waiting to happen.** `plan_tool/jira_grade.py`'s `JIRA_GRADE_REQUIRED_H2S` carries the comment "every jira-grade consumer imports these and never re-declares them", and `plan_tool/prompts/detail-jira.md` restates all five tokens in prose anyway — with no test pinning them together (`rg -rn 'detail-jira' tests/` returns nothing). Do not add a second instance of that.
- **Guard it with a test, not a convention.** Assert that the prompt text contains every member of step 1's attribute tuple, every disposition value, both decision-status values, and every required row-key name. A rename then reddens this suite instead of silently producing prompts that ask for the old spelling.
- **Guard the example the same way.** Drive the skeleton artifact embedded in the prompt through step 1's real constraints parser and step 2's real constraints gate set. The gate set needs a domain artifact, so **the test builds a small domain fixture whose ids are the example's anchors** rather than embedding a second artifact's schema in the prompt. One way: construct step 1's row types directly, the same fixture style `tests/test_roadmap_gates.py` uses. That keeps the prompt describing one artifact while still proving its example clears the gates.
- **The rejected alternative: generate the attribute block from the constants** and inject it as a new stage-table field. It removes the drift risk outright, but it moves prompt prose into Python, needs a renderer both stage prompts share, and widens step 4's deliberately uniform variable map. Prompts stay prose; the test carries the guarantee. Step 5 recorded the same rejection — see [Deferred](#deferred).

### The first stage with an upstream

- **Nothing new is built for this.** Step 4's variable map already carries the rendered text of every artifact below this stage, loaded from disk, and step 4's envelope already carries every parsed artifact. Stage 2 is the first consumer of both. If either turns out to need a change, that is a step 4 defect surfacing here, not new work this step designs — fix it in place and say so.
- **Both halves need a test, because they fail differently.** A missing prompt variable produces a model guessing at ids with nothing red firing until the anchor gate rejects it; a missing envelope entry produces an anchor gate that rejects every correct constraint. Cover each separately.
- **Stage 1 must still render cleanly with nothing upstream.** The shared map is filled for every stage, so stage 1 gets an empty upstream value. Pin it, so a later change that makes the upstream variable required does not break stage 1 silently.

### Constraints that are not free to vary

- **No third *shipped* stage.** `STAGES` gains exactly one entry, and the tuple is complete at two. This bounds what the module ships, not what the tests may construct: the synthetic-third-stage case above builds a `RoadmapStage` in the test and passes it through step 4's `stages=` seam over a **copy** of the tuple. Nothing under `plan_tool/` gains a third entry, a third prompt file, or a third artifact path.
- **No gate edit and no artifact-leaf edit.** `plan_tool/roadmap_gates.py` and `plan_tool/roadmap_artifacts.py` carry no diff. If the prompt seems to need a rule the gates do not check, that is a prompt directive, not a new gate.
- **No new module, no CLI wiring, no docs sweep.** Steps 7 and 8 own those.
- **No interactive surface.** Nothing here adds `input()`, an `isatty` check, or a confirm gate to `plan_tool/roadmap.py`.
- **The prompt never tells the model to write a file.** The stage response is text; step 4's writer owns disk.
- **No change to `--from-stage` behavior.** Step 4 built re-entry; this step is the first to run it over two real stages and must not adjust it to make that work.

## Tests

All cases live in `tests/test_roadmap.py`, beside steps 4's and 5's. Most are plain unit tests driving `run_roadmap` over the shipped table with a fake invoker returning canned artifact text. Mark the end-to-end cases that drive the real parsers, the real gate sets, and real disk writes `@pytest.mark.integration`; keep the rest unmarked. The suite passes under `tests/conftest.py`'s autouse gate with no `@pytest.mark.allow_real_claude` opt-out.

This is a `feature` step in a plan with `enforce_step_tests: true`, so the test-authoring gate applies and these cases land with the prompt and the table entry.

### Tests for this step

31 new cases, plus two of step 5's rewritten. Every one must be green before this step is finished.

**The stage row and the shipped table**

- `test_stage_table_ships_both_stages` — replaces step 5's `test_stage_table_ships_the_domain_stage`: `STAGES` has exactly two entries, numbered 1 then 2.
- `test_shipped_table_run_writes_both_artifacts` — replaces step 5's `test_shipped_table_run_writes_no_constraints_artifact`: a clean two-stage run puts a file at each of step 1's paths.
- `test_constraints_stage_row_reuses_step_ones_path_helper_and_parser` — the row's fields are the landed symbols themselves, not local wrappers.
- `test_constraints_stage_row_carries_the_landed_constraints_gate_set` — the row's gate set is step 2's constraints aggregate.

**The prompt file**

- `test_constraints_prompt_template_ships_under_prompts_dir` — the file exists where the stage row says it does.
- `test_constraints_prompt_placeholders_are_a_subset_of_the_variable_map` — every `${name}` in the file is a key step 4's loop supplies.
- `test_constraints_prompt_renders_with_no_unresolved_placeholder` — a rendered stage-2 prompt contains no leftover `${`.
- `test_constraints_prompt_names_every_quality_attribute` — every member of step 1's attribute tuple appears in the prompt text.
- `test_constraints_prompt_names_every_disposition_value` — all three, including `not-load-bearing`.
- `test_constraints_prompt_names_every_required_row_key` — each required field name on step 1's disposition, constraint, and decision rows, including the constraint row's `attribute` and the decision row's anchor.
- `test_constraints_prompt_names_both_decision_status_values` — the settled and `pending` spellings both appear.
- `test_constraints_prompt_states_every_constraints_gate_rule` — parametrized over the gates in step 2's landed constraints aggregate, each gate's subject appears in the prompt text. Parametrizing over the aggregate rather than a hardcoded list is the point: a gate added to the set without a matching prompt sentence reddens this case instead of costing retry budget at run time.
- `test_constraints_prompt_forbids_constraining_a_not_load_bearing_attribute` — the prompt states the totality gate's fifth defect, so the model is told the rule rather than discovering it through a rejected attempt.

**The prompt's embedded example**

- `test_prompt_example_parses_through_the_constraints_parser` — the skeleton artifact loads into typed rows without raising.
- `test_prompt_example_disposes_every_attribute_exactly_once` — the example is complete, not a trailing-off excerpt.
- `test_prompt_example_clears_the_constraints_gate_set` — the parsed example, paired with a domain fixture holding the example's anchor ids, produces an empty violation list.

**The upstream artifact reaches stage 2**

- `test_domain_artifact_text_reaches_the_constraints_prompt` — an entity id written by stage 1 appears in stage 2's rendered prompt.
- `test_stage_one_prompt_carries_no_upstream_artifact` — stage 1 renders cleanly with nothing written yet.
- `test_constraints_gate_envelope_carries_the_domain_artifact` — stage 2's gate set receives stage 1's parsed artifact.

**End to end over both real stages**

- `test_two_stage_run_writes_both_artifacts_and_completes` — one invoker call per stage, both files on disk, the completed outcome.
- `test_written_constraints_artifact_reparses_through_the_loader` — the bytes on disk load back through step 1's constraints loader.
- `test_missing_attribute_is_retried_with_the_totality_gate_message` — a response omitting one attribute produces a second attempt whose prompt carries that violation's message verbatim.
- `test_unresolvable_anchor_is_retried_with_the_anchor_gate_message` — same for a constraint anchored to an id `01-domain.md` does not define.
- `test_anchor_gate_resolves_against_stage_ones_written_artifact` — a constraint anchored to an id stage 1 actually wrote passes; the anchor target set is the union of entity, rule, and workflow ids.
- `test_always_violating_constraints_response_exhausts_and_leaves_domain_intact` — the budget is spent, no `02-constraints.md` appears, `01-domain.md` is unchanged, and the result names stage 2.
- `test_pending_constraints_decision_does_not_fail_the_run` — an artifact whose decisions are all `pending` still completes and is written.

**A stage is data, not a code path**

- `test_a_synthetic_third_stage_drives_through_the_loop_unchanged` — the plan criterion this step owns. Build a full `RoadmapStage` for a synthetic stage 3 — its own stage number, log name, prompt file, output path callable, parser, and gate set — append it to a **copy** of the shipped `STAGES`, pass that through step 4's `stages=` injection seam, and drive a three-stage run. All three artifacts are written, the third stage's own parser and gate set are the ones invoked for it, and `plan_tool/roadmap.py` carries no diff. This is the case that makes the stage-as-data bet falsifiable: if a third stage needs a loop change, it fails here rather than in `roadmap-02-components`.
- `test_the_synthetic_stage_receives_both_shipped_artifacts` — stage 3's **prompt map** carries the rendered text of both artifacts below it, so "every artifact below this stage" holds past the two stages that ship. Deliberately the prompt half only: `ArtifactEnvelope` declares exactly two slots, so a third `artifact_key` makes `_build_envelope` raise `TypeError` and reusing `constraints` silently drops stage 2 in the dict comprehension. Widening the envelope is a real change to `plan_tool/roadmap_gates.py`, which this step's own fence declares carries no diff — so it belongs to the arc position that adds a third artifact kind (`roadmap-02-components`), not here.
- `test_the_shipped_table_is_unchanged_by_the_synthetic_stage_case` — the injected table is a copy; `STAGES` itself still has exactly two entries after the suite runs.

**`--from-stage 2` over the shipped table**

- `test_from_stage_two_over_the_shipped_table_invokes_only_the_constraints_stage` — stage 1's invoker is never called and `01-domain.md` is left unchanged.
- `test_hand_deleted_entity_breaks_the_anchor_on_re_entry` — deleting an entity from `01-domain.md` by hand turns a previously clean constraint into an anchor violation on re-entry, without re-running stage 1.

## Acceptance criteria

- `plan_tool/prompts/roadmap-constraints.md` exists; `plan_tool/roadmap.py` and `tests/test_roadmap.py` are the only other files that change.
- `STAGES` in `plan_tool/roadmap.py` has exactly two entries, and stage 2's prompt filename, path helper, parser, and gate set are the landed symbols from steps 1 and 2.
- The diff to `plan_tool/roadmap.py` is the stage entry plus its comment — no change to `RoadmapStage`, the variable map, the attempt loop, the lift, the writer, the run log, or the result type. `rg 'stage\.(name|number) ==' plan_tool/roadmap.py` returns nothing.
- A run over the shipped table with canned conforming responses writes both `<plans_dir>/roadmaps/<slug>/01-domain.md` and `02-constraints.md`, calls the invoker once per stage, and returns the completed outcome.
- Both written files load back through step 1's loaders without error and produce no violations from step 2's gate sets.
- Every `${name}` in `plan_tool/prompts/roadmap-constraints.md` is a key step 4's loop supplies, and a rendered stage-2 prompt contains no leftover `${`.
- The prompt text contains every member of step 1's quality-attribute tuple, all three disposition values including `not-load-bearing`, both decision-status values, and every required row-key name from step 1's constraints row types.
- The prompt's embedded example parses through step 1's constraints parser, disposes every attribute exactly once, and returns an empty violation list from step 2's constraints gate set when paired with a domain fixture holding its anchor ids.
- Stage 2's rendered prompt contains an entity id that stage 1 wrote, and stage 2's gate envelope holds stage 1's parsed artifact.
- A response omitting an attribute, and a response anchoring a constraint to an undefined id, are each retried with that gate's message quoted verbatim as a `- {message}` bullet.
- A constraints stage that never clears its gates spends the whole budget, writes no `02-constraints.md`, leaves `01-domain.md` unchanged, and returns the stage-exhausted outcome naming stage 2.
- `--from-stage 2` over the shipped table invokes only stage 2, and hand-deleting an entity from `01-domain.md` surfaces as an anchor violation without stage 1 running.
- A synthetic third `RoadmapStage` — its own stage number, log name, prompt file, output path, parser, and gate set — appended to a copy of `STAGES` and driven through `run_roadmap`'s `stages=` seam completes a three-stage run, writes all three artifacts, and hands stage 3's **prompt map** the rendered text of both shipped artifacts, with no diff to `plan_tool/roadmap.py` and `STAGES` itself still two entries long. The gate **envelope** is deliberately not part of this criterion: it holds exactly two slots by design in `plan_tool/roadmap_gates.py`, which this step declares carries no diff, so a third slot is owned by the arc position that introduces a third artifact kind.
- `rg 'input\(|isatty' plan_tool/roadmap.py` returns nothing, and the prompt file contains no instruction to write, edit, or create a file.
- The 31 new cases pass under `uv run pytest tests/test_roadmap.py -q`, and the full suite (`uv run pytest tests/ -q`) stays green.
- `plan_tool/roadmap_artifacts.py`, `plan_tool/roadmap_gates.py`, `plan_tool/renderer.py`, `plan_tool/prompts/roadmap-domain.md`, `ROADMAP_FORMAT.md`, `TESTING.md`, and everything under `plan_tool/cli/` carry no diff.

## References

- [ISO/IEC 25010 — Product quality model (characteristics and subcharacteristics)](https://iso25000.com/index.php/en/iso-25000-standards/iso-25010) — a **spelling reference only**, matching step 1's ruling: it is *not* the source of this list's structure. Its hierarchy nests availability and fault tolerance under reliability, while this plan keeps all seven flat and independently disposable. This step writes the prompt's attribute descriptions, so it is the one place the nesting could leak back in — word each description as a standalone concern, and never imply one attribute subsumes another.
- [MADR — Markdown Architectural Decision Records](https://adr.github.io/madr/) — the decision-record fields (status, considered options with why each lost, outcome); useful wording for the prompt's decision-row instructions and its `pending` guidance.
- [Structured outputs — Claude API Docs](https://docs.claude.com/en/docs/build-with-claude/structured-outputs) — what a forced, machine-checkable output contract looks like; read it when deciding how strictly the prompt should pin the response shape before the lift.
- [YAML Ain't Markup Language (YAML™) revision 1.2.2](https://yaml.org/spec/1.2.2/) — type-resolution rules for the frontmatter the prompt asks for, so anchor id lists and enum values serialize one way.

## Applicable guardrails

- **No per-project configuration of the quality-attribute list.** This is the guardrail that binds this step hardest, because this is the step that ships the list into a prompt and the first place someone would think to make it configurable. The list stays step 1's constant. The prompt restates it as literal text and reads no config file or environment variable, and neither does the stage row.
- **No components or plan-derivation stages.** One stage entry, one prompt file. No `03-components.md` path, row kind, or prompt, and no seed emission.
- **No actuator for the `FORK_STRUCTURAL` re-seed arm.** `plan_tool/convergence_diagnosis.py` keeps its hand-authored placeholder; nothing here writes a `create` seed.
- **No change to plan discovery, the plan schema, or the manifest.** This step writes one prompt file and one tuple entry. Nothing reads or writes `plans.json`.
- **No standalone audit or reconcile surface.** Correctness is the in-run gates. No report, no sidecar, no findings roll-up.
- **No sign-off command for `pending` decisions.** The prompt tells the model when to mark a decision `pending`; nothing in this step consumes, blocks on, or confirms one.
- **No interactive or TTY surface.** The stage behaves the same unattended as under an operator.
- **The concept brief is the operator's input.** The prompt reads the brief and the domain artifact. It never rewrites, distills, or asks for a better brief.

## Deferred

- **The CLI verb, its flags, the help catalog, and `CAPABILITIES.md`** — step 7. Nothing here parses argv, prints an operator summary, or maps an outcome to an exit code.
- **Operator docs and the BACKLOG #208 reconciliation** — step 8.
- **Measuring how often a real model clears the gates first try** — the plan names this as an open risk and designs no instrument for it. These tests prove the contract is satisfiable; a hit-rate measurement needs real briefs and a place to record them.
- **Generating the prompt's attribute and vocabulary blocks from step 1's constants** — it would need a shared renderer both stage prompts use and a wider variable map than step 4 settled on. Step 5 rejected the same change for the same reason; route it to reconcile or a `BACKLOG.md` entry if the pinning tests prove too coarse.
- **Pinning `plan_tool/prompts/detail-jira.md` against `JIRA_GRADE_REQUIRED_H2S`** — the same unguarded restatement exists there today. Fixing it is a change to a different lane's prompt and test file, outside this step's declared list; route it to a `BACKLOG.md` entry.
- **Framework lenses** (BACKLOG #208's `roadmap-04-framework-lenses`) — the constraints prompt ships one generic shape with no lens selection and no `--framework` hook.
- **Durable logging of rejected stage responses** — step 4 routed this to reconcile; the run log's per-attempt events remain the accounting.
- **Extending `tests/test_data_contract.py` to the roadmap contract** — the plan defers this while the artifact contract is still settling.
