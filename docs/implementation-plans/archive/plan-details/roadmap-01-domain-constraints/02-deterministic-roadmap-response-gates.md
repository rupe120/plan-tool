> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Add the deterministic roadmap response gates and their violation messages

## Summary

This step creates `plan_tool/roadmap_gates.py` — the seven relation checks that decide whether a stage's written artifact is good enough to hand to the next stage — plus `tests/test_roadmap_gates.py`. Each gate is a pure function over the parsed artifacts step 1 produces: workflows *and business rules* reference defined entities, row ids are unique, every quality attribute carries exactly one disposition, every constraint anchors to something `01-domain.md` defines, every decision names a rejected alternative, a rationale, and a resolving anchor, the artifact is not empty, and every inventory row is described in the prose below the fence. The last two are what stop the other five from passing vacuously on an artifact with no rows. The main design decision is that violations are **retry text, not a report**: the message is written to be pasted straight into the retried stage prompt, so it names the offending row id, the artifact it lives in, and the correction — and `pending` decisions are deliberately not violations. On green the module imports exactly one first-party module (`plan_tool.roadmap_artifacts`), opens no file, spawns no subprocess, and returns violations in a stable order for any given input.

## Table of Contents

- [Summary](#summary) — what the step ships and the one design decision behind it.
- [Why](#why) — why the gates have to exist, and exist separately from the orchestrator.
- [Input](#input) — what step 1 hands this module and what it may assume about it.
- [Files (creates vs edits)](#files-creates-vs-edits) — the two new files; no edits anywhere.
- [Implementation](#implementation) — the violation type, the seven gates, the two stage gate sets, and the rules that are not free to vary.
- [Tests](#tests) — the 55 cases and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — checkable facts a reviewer can run.
- [References](#references) — the two external docs that bear on this step's rules.
- [Applicable guardrails](#applicable-guardrails) — the plan-level fences that bind this step.
- [Deferred](#deferred) — what other steps own, and the consolidation question routed away.

## Why

Step 1 parses roadmap artifacts and deliberately accepts nonsense: a workflow naming an entity that does not exist, two rows sharing an id, a constraints artifact missing half the quality attributes, a decision with no alternatives. That was the right split — shape at parse time, relations elsewhere — but it leaves the relations unchecked by anything. Without them the verb's whole correctness story is missing: `MISSION.md`'s *deterministically driven non-determinism* principle says Claude runs only inside a stage and deterministic code decides whether its output counts, and right now there is no code to decide. The gates also have to land before the orchestrator (step 4), not inside it, for two reasons: a gate that needs an orchestrator to run cannot be unit-tested against a hand-built artifact, and the plan's stage-as-data bet requires a stage's gate set to be a value the stage table holds rather than a branch in the run loop.

## Input

This step consumes step 1's outcome — `plan_tool/roadmap_artifacts.py`, the parsed-artifact contract — and nothing else.

- **The parsed row types and the two artifact types.** Step 1 produces frozen row types for entities, business rules, workflows, quality-attribute dispositions, constraints, and decisions, held on two artifact types as ordered tuples. Gates read those tuples directly; they never re-parse text.
- **Duplicates survive parsing.** Step 1 keeps rows as an ordered tuple rather than a dict keyed by id, specifically so the duplicate-id gate here has something to find. Do not collapse them on the way in either.
- **Two of the three vocabularies are already enforced; the third is this module's.** Step 1's parser raises on an unknown decision *status* or constraint *disposition*, naming the bad value, so this module re-checks neither — a second membership check would be a rule with two owners. **Quality-attribute membership is the opposite case:** step 1 carries the list as a plain constant and coerces nothing against it, precisely so `check_attribute_totality` below can report an unknown attribute as a violation with its row id. Were the parser to reject attributes too, that gate arm could never fire.
- **The quality-attribute list is step 1's constant.** The totality gate reads that ordered tuple. It does not define its own copy, and it reads no config (see [Applicable guardrails](#applicable-guardrails)).
- **A missing required key is already a parse error; an empty collection is not.** Step 1 raises when a workflow row has no entity-references key at all, but a present-and-empty list parses fine. That empty list is this module's to reject — and so is an empty **row set**, which is the sharper case. Every other gate is a check *over rows*, so an artifact with no rows clears all of them vacuously: a domain defining no entities and no workflows, or a constraints artifact carrying seven `not-load-bearing` dispositions and zero constraint rows, would pass and be written. The retry loop makes that actively dangerous, because violations come back as corrections and **deleting the offending rows is always the cheapest way to clear them** — so a model under correction pressure converges on the emptiest passing artifact, for a constraints file whose entire point is ranked tradeoffs.
- **The envelope is the uniqueness scope, not just the anchor scope.** Because `check_duplicate_row_ids` now spans every artifact in the envelope, it needs the envelope for the same reason the anchor and decision gates do — a third gate whose bespoke single-artifact signature would have been wrong. That is three of seven reading the upstream, which is the strongest evidence for the one-call-shape decision below.
- **What this module cannot verify on its own:** that the domain artifact it is handed is the one on disk. Reading files is step 4's job. The anchor gate checks against whatever domain artifact it is given, which is what makes `--from-stage 2` re-entry work once step 4 passes it a freshly-loaded one.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_gates.py` — the violation type, its kind constants, the seven gate functions, and the two stage gate sets.
  - `tests/test_roadmap_gates.py` — the suite listed under [Tests](#tests).
- **Existing files (edits only):** none. Nothing calls these gates until step 4, and `ROADMAP_FORMAT.md` (step 3) is the doc that names them.

## Implementation

### The violation type

- **One frozen dataclass, one kind constant per defect.** Model it on `plan_tool/jira_grade.py:JiraGradeFinding` and its `FINDING_*` constants — a `kind` token, a `message`, plus the two anchors a roadmap violation needs: which artifact it came from and which row id is at fault. Names are this step's to mint and step 3 documents them, so settle them here rather than leaving them to the implementation.
- **Drop the `blocking` field `JiraGradeFinding` carries.** Every violation here blocks: it feeds a retry of the same stage. `jira_grade` needs the flag because its prose gate is advisory; nothing in this module is. A severity axis nobody reads is a field that invites someone to invent an advisory tier later — see [Deferred](#deferred).
- **Name the artifact by its filename constant, not a path.** Step 1 defines `DOMAIN_FILENAME` / `CONSTRAINTS_FILENAME`; use those. The module never sees a `Path`, and the message still tells the operator (and the retried prompt) which file to fix.

### Messages are retry text

This is the decision that shapes the rest of the module.

- **Write each message as a self-contained correction, addressed to whoever writes the next attempt.** Step 4 will feed violations back into the retried stage prompt; the existing precedent is `plan_tool/detail.py:_jira_retry_suffix`, which renders each rejected finding as a `- {message}` bullet above the contract reminder. A message like `workflow row invalid` survives that trip carrying nothing.
- **Name every identifier involved.** A reference failure names both ids — the row that refers and the id that is missing. A duplicate names the id and how many rows carry it. An anchor failure names the constraint id, the missing anchor id, and that `01-domain.md` is where it should be defined. `plan_tool/review.py:validate_feature_refs` is the in-repo model for this wording (its dangling-tag body names the step, the tag, and the registry that should declare it).
- **When the offending row is absent, name the expected identifier instead.** A missing quality attribute has no row id; the message names the attribute. That keeps the plan's "every violation names the offending row's id" criterion satisfiable for the totality gate rather than quietly unmet.
- **No line numbers, no byte offsets.** Ids are the only anchor. The artifact is regenerated on every retry, so a positional anchor is stale before it is read.

### The seven gates

Each is an individually callable pure function over parsed artifacts. Suggested names — adjust if something reads better, but keep them descriptive enough that step 3 can document them without a glossary:

- **`check_entity_references(envelope)`** — every entity id a **workflow *or business-rule*** row names is defined by an entity row in the same artifact. An empty reference list is a violation too: the rule is *every workflow and every rule references a defined entity*, and a row touching nothing is the shape that rule exists to catch. Rules are in scope, not just workflows, because step 6 lets a constraint anchor to the union of entity, rule, and workflow ids — a rule connected to no entity would be a legal anchor target that silently breaks the entity→constraint traceability chain. Report every bad reference, not the first.
- **`check_duplicate_row_ids(envelope)`** — ids must be unique across **all row kinds in every artifact the envelope carries**, not per kind and not per file. Cross-kind uniqueness inside one artifact is the obvious half: constraint anchors resolve against the union of entity, rule, and workflow ids, so an entity and a workflow sharing an id makes an anchor ambiguous. The cross-*artifact* half follows from the same argument and is easy to miss — `check_constraint_anchors` and `check_decision_records` both resolve against a union spanning the artifact under check *and* its upstream, so a `checkout` workflow in `01-domain.md` beside a `checkout` constraint in `02-constraints.md` makes such an anchor resolve two ways while every gate passes. **The uniqueness scope must equal the anchor-resolution scope**, or the ambiguity this gate exists to prevent simply moves up one level. Emit one violation per duplicated id rather than one per occurrence — the same choice `validate_feature_refs` makes with its already-flagged set — and name both artifacts when the collision spans two.
- **`check_attribute_totality(envelope)`** — exactly one disposition row per attribute in step 1's shipped list, **and every constraint row's `attribute` value is a member of that same list**. **Five defects**: an attribute with no disposition row, an attribute with two, a disposition row naming something outside the list, a *constraint* row naming something outside it, and a *constraint* row serving an attribute this same artifact disposed `not-load-bearing` — declaring a concern deliberately traded away and then constraining for it is incoherent, and it is the shape a model produces when it pads to satisfy totality. The constraint-row arm matters because step 1 mints `attribute` on constraint rows precisely so a constraint links to the attribute it discharges — and without this check nothing validates that value: the anchor gate reads only anchor ids, and the non-empty gate only counts rows. This gate owns attribute membership, so it owns it everywhere the word appears rather than leaving one row kind unguarded. Treating extras as violations mirrors `plan_tool/jira_grade.py:validate_jira_grade_body`'s closed-schema rule, and it is what makes "exactly once" mean what it says. The `not-load-bearing` disposition counts as a real disposition — it is the honest answer the plan's Risks section keeps expressible, never an omission.
- **`check_constraint_anchors(envelope)`** — every constraint's anchor ids resolve to an entity, rule, or workflow id defined in the domain artifact. A constraint with no anchor at all is a violation. It reads the upstream domain out of the envelope rather than taking a second positional argument, which is what keeps every gate one call shape.
- **`check_decision_records(envelope)`** — runs over either artifact's decision rows. Like the anchor gate it reads the envelope, **not** a bare artifact: a constraints-artifact decision may anchor to a domain id, so a single-artifact signature could never resolve it. Two gates therefore need the upstream, and the envelope is why neither needs a bespoke signature. Each decision carries at least one rejected alternative, each alternative carries its own reason, the rationale is non-empty after stripping whitespace, and **its anchor resolves to a row id defined in the artifact it belongs to** (or, for a constraints decision, to a domain id passed in the envelope). The resolvable set is exactly step 1's: entity, rule, and workflow ids in the domain artifact; disposition, constraint, and other row ids in the constraints artifact, plus the upstream domain ids. **A quality attribute is reachable only through its disposition row's id** — attribute names are a constant rather than rows, so a decision anchored to a bare attribute name resolves nowhere and is a violation. The anchor check is what makes a `pending` decision actionable — an unanchored one names a tradeoff but not the thing it binds, leaving the operator who must confirm it, and any later stage inheriting it as a fence, with nothing to attach it to. **`pending` status is never a violation** — it is the plan's review channel, and gating on it would make the verb fail on exactly the artifacts it is designed to produce.
- **`check_artifact_non_empty(envelope)`** — the domain artifact declares at least one entity and at least one workflow; the constraints artifact declares at least one constraint row. Dispositions alone do not satisfy it: seven `not-load-bearing` rows and no constraints is the degenerate output the retry loop drifts toward, and it is exactly what this gate exists to refuse. This gate is what stops every other gate from passing vacuously.
- **`check_inventory_has_prose(envelope)`** — every frontmatter row id appears somewhere in the prose body below the fence. This is the seed's no-orphan-inventory rule, and it survives the plan's ban on prose gates because it is **decidable on ids**: it never judges whether the prose is *good*, only whether the row was described at all. It is the "a key row is not a scene" failure recorded in BACKLOG #188 — an inventory row with no prose reads as covered and is not.
  - **Match a row id as a whole token, never as a bare substring.** A naive `id in body` lets a body mentioning only `entity-10` satisfy the check for a separate `entity-1` row nothing describes — precisely the orphan this gate exists to catch, and precisely the shape the placeholder id schemes in steps 5 and 6 (`entity-1`, `constraint-1`) make routine. Bound the match on both sides so a longer id containing a shorter one as a prefix does not discharge it.

### The two stage gate sets

- **Ship one aggregate per stage** — the domain set and the constraints set — running their gates in a fixed declared order. That aggregate is the "gate set" third of step 4's `(prompt file, output path, gate set)` stage entry.
- **The binding constraint: the two aggregates must share one call shape.** If the domain aggregate takes one artifact and the constraints aggregate takes two, step 4's stage table needs a branch, and the stage-as-data bet the plan is making dies in its first instantiation. One way: a small frozen input type holding the artifact under check plus the already-parsed upstream artifacts, with both aggregates taking it. The alternative — let step 4 adapt two differently-shaped aggregates — is rejected because it puts knowledge of which gate needs what back into the orchestrator.
- **Violation order must be stable.** Gate order first, then row order as parsed. Two runs over the same input produce the same list, so the retried prompt is reproducible and tests can assert whole lists instead of sets.

### The same rule elsewhere in the repo

The core logic here — *a referenced id must resolve to a defined one; ids must be unique; a fixed vocabulary must be covered exactly once* — already exists twice, over different data:

- `plan_tool/review.py:validate_feature_refs` — duplicate registry ids and steps tagging unknown features, over the plan schema.
- `plan_tool/jira_grade.py:validate_jira_grade_body` — missing, duplicate, and unknown members of a closed token set.

**Mirror their message shape; import neither.** `review.py` is a large orchestrator-level module whose import would end this module's leaf status outright, and `jira_grade` describes a different artifact. Only the rule is shared, not any code worth moving — see [Deferred](#deferred) for why consolidation is not proposed.

### Constraints that are not free to vary

- **Exactly one first-party import: `plan_tool.roadmap_artifacts`.** At column 0 or inside a function. Asserted by test.
- **No filesystem.** No `Path` parameter, no `open`, no `read_text`. Step 4 reads; these gates judge what it read.
- **No `invoker=` seam and no subprocess.** Gates never ask Claude anything — that is the whole point of keying them on ids.
- **No prose checks.** Do not pattern-match the artifact body for keywords. The plan's Architecture section is explicit: a prose gate can only check that a response used the expected vocabulary, while id-keyed relations stay decidable and let a message name the offending row. `docs/NONDETERMINISM_PLAN_DESIGN.md` Rule 4 (closed vocabulary, anchoring, totality) is the doctrine these seven gates instantiate.
- **No retry policy, budget, or exit code.** Gates decide only what is wrong. What happens next is step 4's.
- **Do not confuse this module with `plan_tool/gates.py`.** That one proposes `gate:` shell commands for a plan's steps and is unrelated. Neither imports the other, and neither name changes.

## Tests

All cases live in `tests/test_roadmap_gates.py`. Plain unit tests (unmarked, no `@pytest.mark.integration`) — the module drives no orchestrator and touches no disk. It has no backend seam, so the suite passes under `tests/conftest.py`'s autouse gate with no `@pytest.mark.allow_real_claude` opt-out.

Build fixtures by constructing step 1's row dataclasses directly rather than by parsing text. That keeps the gate suite independent of the frontmatter format, so a step-1 formatting change cannot redden it. The one exception is `test_gates_accept_a_parsed_conforming_artifact`, which exists precisely to prove the two modules fit together.

### Tests for this step

55 cases. Every one must be green before this step is finished.

**Workflow-reference gate**

- `test_workflow_referencing_defined_entities_passes` — a workflow naming only defined entity ids yields no violation.
- `test_workflow_referencing_undefined_entity_violates` — an unknown id is reported.
- `test_workflow_violation_message_names_both_ids` — the message contains the workflow id and the missing entity id.
- `test_workflow_with_no_entity_references_violates` — an empty reference list is a violation, not a pass.
- `test_every_undefined_reference_is_reported` — two bad ids on one workflow yield two violations.

**Duplicate-id gate**

- `test_unique_row_ids_pass` — a clean artifact yields nothing.
- `test_duplicate_entity_id_violates_naming_the_id` — the id appears in the message.
- `test_duplicate_id_reported_once_per_id` — three rows sharing an id yield one violation, not three.
- `test_id_shared_across_row_kinds_violates` — an entity and a workflow sharing an id is reported, because anchors resolve against the union.
- `test_id_shared_across_artifacts_violates` — a `checkout` workflow in the domain artifact and a `checkout` constraint in the constraints artifact collide, because a decision anchor resolves against both and would otherwise resolve two ways.
- `test_cross_artifact_collision_names_both_artifacts` — the message identifies each artifact the duplicated id lives in, so the retried prompt knows which one to rename.

**Attribute-totality gate**

- `test_every_attribute_disposed_exactly_once_passes` — a complete disposition set is clean.
- `test_missing_attribute_violates_naming_it` — the absent attribute's name is in the message.
- `test_duplicate_attribute_disposition_violates` — the same attribute disposed twice is reported.
- `test_not_load_bearing_counts_as_a_disposition` — the honest-answer value satisfies totality.
- `test_attribute_outside_the_shipped_list_violates` — an extra disposition row is reported.
- `test_constraint_row_naming_an_unknown_attribute_violates` — the `attribute` field on a *constraint* row is checked against the same list, naming the constraint id.
- `test_constraint_row_attribute_is_validated_even_when_dispositions_are_complete` — a complete disposition set does not excuse a constraint pointing at an attribute that does not exist.
- `test_constraint_serving_a_not_load_bearing_attribute_violates` — a constraint whose `attribute` names an attribute the same artifact disposed `not-load-bearing` is a violation: declaring a concern deliberately traded away and then constraining for it is incoherent, and it is the shape a model produces when it pads to satisfy totality.

**Cross-artifact anchor gate**

- `test_constraint_anchored_to_a_defined_entity_passes` — the clean path.
- `test_constraint_anchored_to_a_rule_or_workflow_id_passes` — the anchor target set is the union of the three domain row kinds.
- `test_constraint_anchored_to_an_unknown_id_violates` — the message names the constraint id, the missing id, and `01-domain.md`.
- `test_constraint_with_no_anchor_violates` — an empty anchor list is reported.
- `test_anchor_gate_judges_the_domain_artifact_it_is_given` — dropping an entity from the passed domain artifact turns a previously clean constraint into a violation, which is what makes step 4's `--from-stage 2` re-read meaningful.

**Decision-record gate**

- `test_decision_with_alternatives_and_rationale_passes` — the clean path.
- `test_decision_with_no_rejected_alternative_violates` — reported, naming the decision id.
- `test_decision_with_blank_rationale_violates` — whitespace-only counts as missing.
- `test_alternative_without_a_reason_violates` — each rejected alternative needs its own reason.
- `test_pending_decision_is_not_a_violation` — a `pending` decision that is otherwise complete passes.
- `test_settled_and_pending_decisions_are_judged_alike` — status changes nothing about the alternatives-and-rationale rule.
- `test_decision_gate_runs_over_both_artifacts` — decision rows on the constraints artifact are checked the same way.
- `test_decision_with_unresolvable_anchor_violates` — an anchor naming no row in the artifact is reported, naming both the decision id and the missing anchor id.
- `test_pending_decision_still_needs_a_resolving_anchor` — `pending` exempts the status check, not the anchor: the review channel is the reason the anchor exists.
- `test_constraints_decision_anchoring_to_a_domain_id_resolves` — the case the envelope signature exists for: a decision on `02-constraints.md` whose anchor names an `01-domain.md` row passes.
- `test_constraints_decision_with_an_id_in_neither_artifact_violates` — the same path rejects an anchor that resolves in neither the constraints artifact nor the upstream domain.
- `test_decision_anchored_to_a_disposition_row_id_resolves` — a constraints decision about a tradeoff anchors to the disposition row's id and passes; this is the only spelling that puts a quality attribute in the anchor space.
- `test_decision_anchored_to_a_bare_attribute_name_violates` — an attribute *name* is not a row id and resolves nowhere, so it is reported like any other dangling anchor.

**Non-empty gate**

- `test_domain_with_no_entities_violates` — an entity-less domain artifact is rejected rather than passing every row-wise gate vacuously.
- `test_domain_with_no_workflows_violates` — entities alone do not satisfy it.
- `test_constraints_with_dispositions_but_no_constraint_rows_violates` — the degenerate artifact the retry loop drifts toward: seven `not-load-bearing` dispositions, zero constraints.
- `test_populated_artifacts_pass_the_non_empty_gate` — the clean path.

**Inventory-prose gate**

- `test_every_row_id_mentioned_in_prose_passes` — the clean path.
- `test_row_id_absent_from_prose_violates` — an inventoried row the body never describes is reported, naming the row id.
- `test_prose_gate_judges_presence_not_quality` — a body that merely names the id passes; the gate stays decidable on ids and never rates the prose.
- `test_a_longer_id_sharing_a_prefix_does_not_discharge_a_shorter_one` — a body mentioning only `entity-10` still violates for an undescribed `entity-1` row. A substring match would pass it, and the placeholder id schemes steps 5 and 6 ship make this collision routine rather than exotic.
- `test_row_id_matched_as_a_whole_token` — the id is matched with both ends bounded, so neither a prefix nor a suffix overlap satisfies the gate.

**Gate sets and ordering**

- `test_domain_gate_set_runs_every_domain_gate` — one artifact breaking three rules yields all three violations.
- `test_constraints_gate_set_runs_every_constraints_gate` — same for the constraints stage, including the cross-artifact anchor gate.
- `test_both_gate_sets_share_one_call_shape` — the two aggregates are callable identically, so step 4's stage table needs no branch.
- `test_violation_order_is_stable` — repeated calls on the same input return an equal list in the same order.
- `test_clean_artifacts_yield_no_violations` — a fully conforming pair produces an empty list from both sets.
- `test_every_violation_names_its_row_id` — parametrized over one violating fixture per gate; each message contains the offending row id (or, for a missing attribute, the attribute name).
- `test_gates_accept_a_parsed_conforming_artifact` — feed step 1's parser a conforming fixture text and run both gate sets over the result; expect no violations.

**Layering**

- `test_module_imports_only_the_artifact_leaf` — importing it in a subprocess under a stub `plan_tool` package leaves only `plan_tool.roadmap_artifacts` among the `plan_tool.*` entries in `sys.modules`, following `tests/test_jira_grade.py:TestLeafImportDiscipline::test_jira_grade_is_stdlib_only_leaf`. Pair it with the source grep from `tests/test_rate_limit_loop.py:test_leaf_has_no_first_party_runtime_import`, which also catches a lazy import inside a function.
- `test_module_touches_no_filesystem_and_no_subprocess` — no `invoker`/`claude_invoker` parameter, no `subprocess` import, no `open`/`read_text` call anywhere in the module.

## Acceptance criteria

- `plan_tool/roadmap_gates.py` and `tests/test_roadmap_gates.py` exist; no other file in the repo changes.
- `rg '^(from|import) plan_tool' plan_tool/roadmap_gates.py` returns only imports of `plan_tool.roadmap_artifacts`, and importing the module under a stub `plan_tool` package leaves no other `plan_tool.*` module in `sys.modules`.
- `rg 'invoker|subprocess|open\(|read_text' plan_tool/roadmap_gates.py` returns nothing, and no gate takes a `Path` parameter.
- Every gate is callable directly with parsed artifacts and no other argument, and returns a list of violations (never raises, never mutates its input).
- The workflow gate rejects a domain artifact whose workflow names an entity id that artifact does not define; the message contains both ids.
- The duplicate-id gate rejects two rows sharing an id — across different row kinds *and* across the artifacts the envelope carries — with one violation per duplicated id, naming both artifacts on a cross-artifact collision. Its uniqueness scope equals the scope a decision anchor resolves against.
- The inventory-prose gate matches a row id as a whole token: a body naming only `entity-10` does not discharge an undescribed `entity-1` row.
- The totality gate accepts a constraints artifact where every attribute in step 1's list carries exactly one disposition (including `not-load-bearing`), and rejects one that omits an attribute, disposes one twice, names an attribute outside the list on a disposition *or* a constraint row, or carries a constraint serving an attribute the same artifact disposed `not-load-bearing`.
- The anchor gate rejects a constraint whose anchor id is absent from the domain artifact it is passed, and rejects a constraint with no anchor.
- The decision gate rejects a decision with no rejected alternative, an alternative with no reason, or a blank rationale — and returns no violation for a complete decision whose status is `pending`.
- Every violation message contains the offending row's id, or the expected attribute name when the row is absent.
- The two stage gate sets take the same argument shape, and repeated calls on identical input return an equal list in the same order.
- No membership check against the decision-status or constraint-disposition vocabularies appears in this module — step 1's parser owns that.
- The 55 cases in `tests/test_roadmap_gates.py` pass under `uv run pytest tests/test_roadmap_gates.py -q`, and the full suite (`uv run pytest tests/ -q`) stays green.
- `plan_tool/schema.py`, `plan_tool/parser.py`, `plan_tool/locator.py`, `plan_tool/review.py`, and `plan_tool/gates.py` carry no diff.

## References

- [MADR — Markdown Architectural Decision Records](https://adr.github.io/madr/) — the decision-record field set (status, considered options with why each lost, outcome); read it to judge what the decision gate should demand and what it should let through.
- [ISO/IEC 25010 — Product quality model (characteristics and subcharacteristics)](https://iso25000.com/index.php/en/iso-25000-standards/iso-25010) — the canonical quality-attribute names, useful for wording the totality gate's missing-attribute message so it reads like the thing it is asking for.

## Applicable guardrails

- **No standalone audit or reconcile surface over roadmap artifacts.** This module returns violations to a caller. No report file, no findings roll-up, no `--fail-on-findings`-style verdict, no exit code, no CLI wiring.
- **No per-project configuration of the quality-attribute list.** The totality gate reads step 1's constant. Do not read `plan_tool/project_config.py`, any config file, or the environment — the single-import rule blocks it anyway.
- **No interactive or TTY surface.** Pure functions, no prompts, no `input()`, no confirm gate.
- **No change to plan discovery, the plan schema, or the manifest.** Nothing here touches `plan_tool/schema.py`, `plan_tool/parser.py`, `plan_tool/locator.py`, or `plans.json`.
- **Nothing for the later stages.** No gates for `03-components.md` or `04-roadmap.md`, no component or seed traceability checks, and no actuator for the `FORK_STRUCTURAL` re-seed arm.

## Deferred

- **Reading artifacts from disk, the retry loop, the retry budget, and halting the arc** — step 4's orchestrator owns all of it. This module says what is wrong; step 4 decides what that costs.
- **Assembling violations into a retried prompt** — step 4. This step's obligation is only that each message survives being quoted verbatim into one.
- **`--from-stage 2` re-entry** — step 4. The anchor gate makes it possible by judging whatever domain artifact it is handed, and does nothing else about it.
- **Reporting the `pending` decision count in the run summary** — step 4 owns the summary. This module's contribution is the guarantee that `pending` never becomes a violation.
- **Documenting each gate and its message wording in `ROADMAP_FORMAT.md`** — step 3, which names the code enforcing each rule.
- **Re-checking the closed vocabularies** — step 1's parser raises on an unknown member. A second check here would give one rule two owners and two different failure modes.
- **A severity or advisory tier on violations** — every violation blocks a stage. Nothing in this plan consumes a softer tier, and inventing one now would invite a gate that reports without stopping anything.
- **Consolidating the repo's id-relation checkers** — `plan_tool/review.py:validate_feature_refs`, `plan_tool/jira_grade.py:validate_jira_grade_body`, and this module apply the same rules to three different data types and return three different result types. Only the rule is shared, not code worth moving, so no consolidation is proposed; if a future audit raises it, that is the reason to record rather than a refactor to mint.
- **Extending `tests/test_data_contract.py` to the roadmap contract** — the plan defers this while the artifact contract is still settling; this suite and step 1's are the only checks for now.
