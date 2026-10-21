> **Auto-archived**: this plan was swept on 2026-08-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Add the components stage with roadmap-components.md and a STAGES table row

## Summary

This step makes stage 3 real in `plan_tool/roadmap.py` by appending a third `RoadmapStage` row to `STAGES` and shipping `plan_tool/prompts/roadmap-components.md`. The row holds step 1's `components_path` / parse / render symbols and step 3's `run_components_gates` by identity — no wrapper, no loop branch. The prompt restates the components contract inline (brief plus both upstream artifacts as `${domain_artifact}` and `${constraints_artifact}`), with a placeholder skeleton that clears the real gate set. On green, a three-stage run against the shipped table writes `03-components.md`, upstream text reaches the components prompt, gate violations retry verbatim, and `--from-stage 3` re-reads hand-edited domain and constraints without re-invoking earlier stages.

## Table of Contents

- [Summary](#summary) — the STAGES row, the new prompt, and the observable three-stage run.
- [Why](#why) — why the orchestrator step waits until the contract, gates, and format doc exist.
- [Input](#input) — symbols and behaviors this step reads from steps 1–4 without re-implementing them.
- [Files (creates vs edits)](#files-creates-vs-edits) — the three paths in scope and what each gains.
- [Implementation](#implementation) — table row, prompt authoring, test-suite sweep, and rules that are not free to vary.
- [Tests](#tests) — new and rewritten cases plus the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — checkable facts a reviewer or CI can run.
- [References](#references) — docs worth skimming while authoring YAML and templates.
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step's code and prompt.
- [Deferred](#deferred) — work readers might expect but that stays out of scope.

## Why

Steps 1–3 land the typed `03-components.md` contract, a three-slot `ArtifactEnvelope`, and `run_components_gates`, but `plan_tool/roadmap.py` still ships a two-row `STAGES` table and has no components prompt. `tests/test_roadmap.py:TestSyntheticThirdStage` documents the workaround — a fake third row reuses `artifact_key="constraints"` because the envelope had no components slot before step 2. Until this step appends the real row with `artifact_key="components"`, the retry loop, disk write path, and `--from-stage` re-entry never exercise the third artifact against real upstream files. Step 4 makes the schema copy-safe for humans; this step makes it copy-safe for the model at run time.

## Input

Open the landed modules at HEAD before authoring — **landed names win** over any name in earlier details or plan prose.

**From step 1 (`plan_tool/roadmap_artifacts.py`):**

- Path: `COMPONENTS_FILENAME`, `components_path`
- Wire inventory: `COMPONENTS_ROW_KEYS` (expected: `system_patterns`, `component_patterns`, `components`, `decisions`)
- Row types: `PatternRow`, `ComponentRow`, `ComponentsArtifact`
- Parse/render/load: `parse_components_artifact`, `render_components_artifact`, `load_components_artifact`
- Review collections: same `feedback` / `removals` shape as domain and constraints

**From steps 2–3 (`plan_tool/roadmap_gates.py`):**

- Stage aggregate: `COMPONENTS_GATES`, `run_components_gates`
- Five traceability gates (names at HEAD — expected from step 3 detail): `check_component_entity_references`, `check_entity_component_coverage`, `check_component_pattern_references`, `check_component_constraint_references`, `check_prioritized_constraint_discharge`
- Shared gates the components prompt must restate: `check_artifact_non_empty`, `check_duplicate_row_ids`, `check_decision_records`, `check_inventory_has_prose`, plus revision-only gates named in `roadmap-revision.md`

**From step 4 (`ROADMAP_FORMAT.md`):**

- The gate-clean components example and its upstream id story (`order`, prioritized constraints, both pattern collections non-empty). The prompt skeleton should compose with that example's id choices where practical — the gates check structure, not product fit.

**From the existing orchestrator (`plan_tool/roadmap.py`):**

- `_render_stage_prompt` already builds `${slug}`, `${brief}`, and `${<artifact_key>_artifact}` for every stage below the current one — **no signature change needed**; appending the row is enough for prompt variables.
- `_build_envelope`, `_write_artifact`, `_run_stage`, and `_load_and_regate_below` already dispatch through `RoadmapStage` fields — **no loop edits** beyond imports and the tuple entry.
- `REVISION_PROMPT_FILENAME` and `_render_revision_prompt` are shared; components revisions use the same revision template as stages 1–2.

**What this step cannot verify:** canned-response tests prove the contract is *satisfiable* through the real parser and gates, not that a real model usually satisfies it on the first attempt. Hit-rate measurement needs real briefs and a recording surface — route that to [Deferred](#deferred).

## Files (creates vs edits)

- **New files:**
  - `plan_tool/prompts/roadmap-components.md` — third-stage authoring prompt: inputs, closed output contract, frontmatter inventory, gate rules restated inline, placeholder skeleton example.

- **Existing files (edits only):**
  - `plan_tool/roadmap.py` — extend imports from `plan_tool/roadmap_artifacts` and `plan_tool/roadmap_gates`; append the third `RoadmapStage` to `STAGES`; update the module docstring / comment above `STAGES` so it describes three shipped stages. **No other control-flow changes** — the loop module diff should be imports, the new tuple entry, and comment/docstring wording.
  - `plan_tool/cli/roadmap_cmd.py` — only if three-stage overwrite messaging needs a code change after the tests below; prefer proving the existing table-driven `_overwrite_summary_lines` first.
  - `tests/test_roadmap.py` — rewrite shipped-table assertions for three stages; add components fixtures/helpers and prompt/end-to-end test classes; update `TestSyntheticThirdStage` to use `artifact_key="components"`; sweep full-table invoker call sites that today pass only two canned replies; extend revision/shared-template cases that enumerate authoring prompts from two to three; add predecessor-preflight and revision-prompt cases for a components predecessor with component-targeted feedback.
  - `tests/cli/test_roadmap_cmd.py` — three-stage overwrite-pointer stubs and cases (see Implementation).

## Implementation

### Governing design decision

**Variation stays in the table row, not in the loop.** Append one `RoadmapStage`; do not add `if stage.number == 3` (or `stage.name == "components"`) anywhere in `plan_tool/roadmap.py`. The rejected alternative — a local wrapper around `run_components_gates` to "normalize" the signature — puts per-stage knowledge back into code the table exists to keep dumb.

### The `STAGES` row

Append a third frozen entry after the constraints row:

| Field | Value (by identity — no adapters) |
| --- | --- |
| `number` | `3` |
| `name` | `"components"` |
| `prompt_filename` | `"roadmap-components.md"` |
| `artifact_key` | `"components"` |
| `artifact_path` | `components_path` |
| `parse` | `parse_components_artifact` |
| `render` | `render_components_artifact` |
| `gates` | `run_components_gates` |

- **Import the symbols** from `plan_tool/roadmap_artifacts` and `plan_tool/roadmap_gates` at module top — same pattern as the two existing rows.
- **Update the comment** above `STAGES` ("complete at two stages" → three stages). The module docstring opening paragraph still applies; only the stage count claim changes.

### Prompt authoring (`roadmap-components.md`)

Follow the two shipped authoring prompts and the plan's prompt lessons:

- **Archetypes:** closed single-call output like `plan_tool/prompts/detail-jira.md`; input-only stance like `plan_tool/prompts/distill-seed.md` ("work from the supplied text; do not read the repository").
- **Inputs section** with three fenced blocks: `${brief}`, `${domain_artifact}`, `${constraints_artifact}`. State plainly that entity ids on components come from `01-domain.md` and discharge claims cite `02-constraints.md` — copy ids exactly.
- **Output format (strict):** response *is* the artifact; first characters are `---`; no preamble, no wrapping fence, no file-write instruction (the orchestrator owns disk).
- **Frontmatter inventory:** restate every key in `COMPONENTS_ROW_KEYS` and every required field on `PatternRow`, `ComponentRow`, and `DecisionRow` — whole tokens, matching wire names from step 1. Include both decision-status values (`settled`, `pending`). Mention `feedback` / `removals` only if the revision template does not already cover them for this stage (mirror constraints: design collections here; review collections deferred to revision framing).
- **Gate rules section:** one numbered rule per gate in `COMPONENTS_GATES` that applies on a **first** authoring pass (shared gates + five traceability gates). Pull wording from `ROADMAP_FORMAT.md` and the landed `check_*` implementations at write time — especially:
  - every domain entity must appear on some component;
  - both pattern collections must be non-empty on the artifact;
  - every component lists at least one entity id and one defined pattern id;
  - `constraint_ids` entries must name real constraint rows;
  - only `prioritized` constraints require discharge (explicitly say `traded-away` and `not-load-bearing` do not);
  - duplicate-id scope spans every artifact in the envelope (domain, constraints, and components) — matching `check_duplicate_row_ids`, which walks `_envelope_rows`, not a domain+components subset;
  - prose-body inventory check for every design-row id.
  Predecessor-only gates (`check_design_row_continuity`, `check_feedback_integrity`, `check_settled_decisions`) stay in `roadmap-revision.md` only — same split constraints uses.
- **Placeholder skeleton:** one ```markdown block opening on `---`, using generic ids (`pattern-audit-before-response`, `component-checkout`, `<one line>` statements) — not a believable product story the model might copy wholesale. Align upstream anchors with the test fixtures' domain/constraints ids (`order`, `con-1`, etc.) so the example clears gates when paired with `_domain()` / `_constraints()`.
- **No repo doc pointers:** `rg -l 'FORMAT\.md' plan_tool/prompts/` must stay empty. Do not tell the model to open `ROADMAP_FORMAT.md`.
- **Template mechanics:** `${...}` placeholders only; literal `$` in prose as `$$` if ever needed. Every `${name}` must be supplied by `_render_stage_prompt` (`slug`, `brief`, `domain_artifact`, `constraints_artifact`).

### Test helpers and fixture sweep

Add to `tests/test_roadmap.py` (local mirrors of `_domain` / `_constraints`, not imports from `tests/test_roadmap_gates.py` — keeps orchestrator tests independent of gate-suite internals):

- `_components_stage()` → `roadmap.STAGES[2]`
- `_components()` / `_components_text()` — conforming `ComponentsArtifact` that clears `run_components_gates(ArtifactEnvelope(domain=_domain(), constraints=_constraints(), components=…))`. One way: start from step 2's `make_components` shape described in step 3's detail, adapted to `_domain()` / `_constraints()` ids.
- `_required_components_row_keys()` via `_row_key_names(COMPONENTS_ROW_KEYS, (PatternRow, ComponentRow, DecisionRow, RejectedAlternative))`
- `_COMPONENTS_GATE_PROMPT_SUBJECTS` — phrase map for each components-stage gate, same pattern as `_CONSTRAINTS_GATE_PROMPT_SUBJECTS`
- `_Env.components_file` and `write_components()` — parallel to domain/constraints helpers

**Rewrite inherited shipped-table tests** (named rewrites, not silent "fixes"):

- `test_stage_table_ships_both_stages` → `test_stage_table_ships_three_stages`
- `test_shipped_table_run_writes_both_artifacts` → three-artifact variant (or add a sibling and keep the two-stage slice test on `STAGES[:2]`)

**Update `TestSyntheticThirdStage`:**

- `artifact_key="components"`, `artifact_path=components_path`, components parse/render, real `run_components_gates` or a recorder — drop the comment about reusing the constraints slot.
- `test_the_shipped_table_is_unchanged_by_the_synthetic_stage_case` expects `len(roadmap.STAGES) == 3`.

**Sweep full-table invoker sites:** roughly 33 call sites use `_StubInvoker(_domain_text(), _constraints_text())` with `roadmap.STAGES`. Any test driving the **full** shipped table needs a third canned reply (`_components_text()`). Tests intentionally scoped to `STAGES[:1]` or `STAGES[:2]` stay on two (or one) reply. Grep is the acceptance check.

**Extend shared revision tests:**

- `test_both_authoring_prompts_carry_the_say_it_aloud_test` → iterate all three authoring prompts.
- `test_the_plain_english_block_does_not_drift_between_the_two_prompts` → three-way equality or pairwise against domain as canonical.
- `test_revision_prompt_cites_no_repo_document` → include `roadmap-components.md`.
- `_predecessor()` helper — dispatch `ComponentsArtifact` to `_components_stage()`.

**Do not migrate** `TestWorktreeList`-style fixtures through the new API where tests deliberately build state by hand — not applicable here, but keep `TestSyntheticThirdStage`'s injected prompts separate from shipped prompt containment tests.

### End-to-end seams (first time real modules meet)

Add one case per boundary (mirroring `TestDomainStageAgainstTheRealGates` / `TestBothShippedStagesAgainstTheRealGates`):

- Conforming components response → real gates → `components_file` written (`@pytest.mark.integration`)
- Written bytes → `load_components_artifact` equals parsed fixture
- Gate violation message appears verbatim in second attempt prompt
- Stage exhaustion writes no components file, leaves domain/constraints intact
- `--from-stage 3` invokes only stage 3 when upstream artifacts exist; hand-deleted domain entity breaks a components gate on re-entry without calling stage 1
- Upstream artifact text (`marker-entity`, etc.) appears in the components prompt
- Gate envelope for stage 3 carries parsed domain and constraints from disk
- **Revision re-entry (not first-run only):** existing `03-components.md` on disk with an `open` feedback row targeting a component id — `_check_predecessor_review_rows` accepts the target; `--from-stage 3` wraps `roadmap-components.md` through `roadmap-revision.md` and the rendered prompt carries predecessor text plus the active feedback block (extend `TestPredecessorPreFlight` / add a dedicated integration case; step 2's `test_feedback_integrity_on_components_envelope` is gate-only and does not discharge this)

### Constraints that are not free to vary

- **No loop branches on stage identity:** `rg 'stage\.(name|number)\s*==' plan_tool/roadmap.py` returns nothing after the edit.
- **Row holds function identity:** `assert stage.gates is run_components_gates` (and same for path/parse/render) — not `==` on behavior alone.
- **Persist rendered artifact, not raw reply** — already enforced by `_write_artifact`; add/keep a loader round-trip test for components.
- **No interactive surfaces:** `rg 'input\(|isatty' plan_tool/roadmap.py` unchanged; no new `sys.exit` in the orchestrator.
- **No partition-quality gates in prompt or code** — do not invent merit checks; restate only what `COMPONENTS_GATES` enforces.
- **No seed emission or CAPABILITIES edits** — those belong to later plan steps. CLI overwrite-summary cases for three stages *are* in this step (below).
- **Packaging:** no `pyproject.toml` edit — prompts under `plan_tool/prompts/` ship with the package automatically.

### CLI overwrite pointer (three stages)

`plan_tool/cli/roadmap_cmd.py:_overwrite_summary_lines` is table-driven off `RoadmapResult.stages_run` / `overwritten_stages`. Extend `tests/cli/test_roadmap_cmd.py` so three-stage results are covered — do not leave the suite on two-stage stubs only:

- Add a `_three_stage_completed` (or equivalent) stub with `stages_run=(1, 2, 3)`.
- Overwriting stage 2 (lowest) points the operator at `--from-stage 3` and names that `03-components.md` is still rewritten.
- Overwriting only stage 3 prints the no-out-of-range-pointer / copy-aside guidance for `03-components.md` (parallel to today's last-stage case with `overwritten=(2,)`).
- Touch `plan_tool/cli/roadmap_cmd.py` only if a three-stage path actually needs a code change; prefer proving the existing table-driven path first.

## Tests

All new/changed cases live in `tests/test_roadmap.py` unless noted. Integration-marked classes follow the existing domain/constraints precedent. **Every listed test must be green before this step is done**, and the full suite must stay green.

### Tests for this step

**Shipped table / row identity**

- `test_stage_table_ships_three_stages` — `len(roadmap.STAGES) == 3`; numbers, names, and `artifact_key` values are `domain`, `constraints`, `components`.
- `test_components_stage_row_reuses_step_ones_path_helper_and_parser` — row fields are `components_path`, `parse_components_artifact`, `render_components_artifact` by identity.
- `test_components_stage_row_carries_the_landed_components_gate_set` — `roadmap.STAGES[2].gates is run_components_gates`.
- `test_shipped_table_run_writes_all_three_artifacts` — full `roadmap.STAGES` run writes domain, constraints, and components paths.

**Prompt containment (`TestComponentsPromptTemplate`)**

- `test_components_prompt_template_ships_under_prompts_dir`
- `test_components_prompt_placeholders_are_a_subset_of_the_variable_map`
- `test_components_prompt_renders_with_no_unresolved_placeholder`
- `test_brief_and_upstream_artifacts_reach_the_components_prompt` — markers in brief, domain, and constraints text appear in the stage-3 prompt.
- `test_components_prompt_names_every_required_row_key` — parametrized over `_required_components_row_keys()`.
- `test_components_prompt_names_both_decision_status_values`
- `test_components_prompt_states_every_components_gate_rule` — parametrized over `COMPONENTS_GATES` with `_COMPONENTS_GATE_PROMPT_SUBJECTS` / revision fallback.
- `test_components_prompt_cites_no_repo_document` — no `FORMAT.md`, no `ROADMAP_FORMAT.md`.
- `test_prompt_example_parses_through_the_components_parser`
- `test_prompt_example_clears_the_components_gate_set` — example + `_domain()` + `_constraints()` envelope returns `[]`.

**Revision / shared template updates**

- `test_all_three_authoring_prompts_carry_the_say_it_aloud_test` — replaces two-prompt variant.
- `test_the_plain_english_block_does_not_drift_across_authoring_prompts` — domain, constraints, components blocks match.

**Synthetic third stage**

- `test_a_synthetic_third_stage_drives_through_the_loop_unchanged` — updated table uses `artifact_key="components"`.
- `test_the_synthetic_stage_receives_all_shipped_artifacts_below_it` — domain and constraints text in stage-3 prompt; envelope carries both.

**Integration — components stage**

- `test_conforming_components_response_clears_the_real_gates_and_writes`
- `test_written_components_artifact_reparses_through_the_loader`
- `test_gate_violation_is_retried_with_the_message_verbatim` — e.g. orphan entity or undefined pattern id.
- `test_always_violating_components_response_exhausts_and_leaves_upstream_intact`
- `test_pending_components_decision_does_not_fail_the_run`

**Integration — three-stage arc**

- `test_three_stage_run_writes_all_artifacts_and_completes`
- `test_stage_two_exhaustion_never_invokes_stage_three` — halting rule with downstream invoker uncalled.
- `test_components_gate_envelope_carries_domain_and_constraints_from_disk`

**Re-entry**

- `test_from_stage_three_invokes_only_the_components_stage`
- `test_hand_edited_upstream_is_visible_to_components_gates_on_re_entry` — delete a domain entity by hand; components stage fails pre-flight or gate with no stage-1 invoke.
- `test_components_predecessor_feedback_targeting_a_component_id_clears_preflight` — existing `03-components.md` with `open` feedback targeting a component id; `_check_predecessor_review_rows` does not raise.
- `test_from_stage_three_revision_wraps_prompt_with_predecessor_and_feedback` — predecessor on disk + active feedback → rendered prompt carries predecessor text, the feedback request, and is wrapped by `roadmap-revision.md` (not authoring-only).

**CLI overwrite pointer (`tests/cli/test_roadmap_cmd.py`)**

- `test_overwriting_stage_two_of_three_points_at_from_stage_three` — `stages_run=(1, 2, 3)`, `overwritten_stages` lowest is 2 → summary names `--from-stage 3` and that `03-components.md` is still rewritten.
- `test_overwriting_only_the_last_stage_of_three_prints_no_out_of_range_pointer` — overwritten stage 3 alone → copy-aside for `03-components.md`, no `--from-stage 4`.

**Regression guards**

- `test_stages_run_in_table_order` — still true with three injected stages.
- `test_gate_envelope_carries_every_artifact_written_so_far` — extend to three artifacts.
- `test_the_shipped_table_is_unchanged_by_the_synthetic_stage_case` — expects three shipped rows.

## Acceptance criteria

- `plan_tool/prompts/roadmap-components.md` exists; `pyproject.toml` unchanged.
- `len(plan_tool/roadmap.py:STAGES) == 3`; third row uses `artifact_key="components"`, `prompt_filename="roadmap-components.md"`, and holds `components_path`, `parse_components_artifact`, `render_components_artifact`, and `run_components_gates` **by identity** (`is`, not merely equal behavior).
- `rg 'stage\.(name|number)\s*==' plan_tool/roadmap.py` returns nothing.
- `rg -l 'FORMAT\.md' plan_tool/prompts/` returns nothing (components prompt included).
- `_allowed_variables(_components_stage()) == {"slug", "brief", "domain_artifact", "constraints_artifact"}`.
- A full run with canned conforming replies for all three stages completes with `outcome == "completed"` and writes `<plans_dir>/roadmaps/<slug>/01-domain.md`, `02-constraints.md`, and `03-components.md`.
- Written `03-components.md` bytes re-parse through `load_components_artifact` equal to the parsed conforming fixture.
- A gate violation on stage 3 produces a second prompt containing `- {message}\n` for that violation (verbatim retry channel).
- Stage 3 exhaustion writes no `03-components.md`, does not delete upstream artifacts, and never invokes a hypothetical stage 4.
- `--from-stage 3` with valid upstream artifacts on disk calls the invoker once (components only) and reads upstream from disk into the prompt and envelope.
- `--from-stage 3` with a missing or gate-failing upstream artifact raises `RoadmapError` before any invoker call.
- `--from-stage 3` over an existing `03-components.md` with `open` feedback targeting a component id revises: pre-flight accepts the target, and the rendered prompt includes predecessor text plus the active feedback block under the shared revision wrapper.
- CLI overwrite summary for a three-stage completed run: overwriting stage 2 points at `--from-stage 3`; overwriting only stage 3 prints copy-aside for `03-components.md` with no out-of-range pointer.
- `TestSyntheticThirdStage` uses `artifact_key="components"` (not `"constraints"`).
- `uv run pytest tests/test_roadmap.py tests/cli/test_roadmap_cmd.py -q` passes; `uv run pytest -m "not integration" tests/test_roadmap.py -q` passes for unit portions; full `uv run pytest tests/ -q -n auto` stays green.

## References

- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — `safe_load` / `safe_dump` behavior for the embedded skeleton example.
- [YAML Ain't Markup Language (YAML) revision 1.2.2](https://yaml.org/spec/1.2.2/) — list and mapping rules for pattern and component rows.
- [string — Template strings](https://docs.python.org/3/library/string.html#template-strings) — `${name}` substitution via `Template.safe_substitute` in `_render_stage_prompt`.
- [pytest: temporary directories (tmp_path)](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — hermetic `env` / `shipped_env` fixtures for orchestrator tests.

## Applicable guardrails

- **The plan's step intent.** Wire the third stage through the existing retry loop only — read upstream off disk, write `03-components.md` on green. No new convergence loop, no second feedback channel.
- **The plan's Out of scope — positions 04–05 and seed emission.** Do not emit seeds, plan-derivation rows, or lens types; no CAPABILITIES work. Three-stage overwrite-pointer CLI coverage *is* in this step.
- **The plan's Out of scope — partition quality and pattern merit.** The prompt restates id-presence gates only; do not instruct the model to optimize component count or pattern wording beyond what gates check.
- **The plan's Out of scope — pre-emptive skeleton redesign.** Smallest change: one tuple entry, one prompt file, test sweep — not a new stage type or per-stage orchestrator module.
- **No interactive operator branch in the retry loop** — failures quote gate text back; no TTY prompt path (same guardrail that binds stage 4's loop module).

## Deferred

- **Position 04 plan derivation and draft seed emission** — unauthored; this plan stops at a reviewable components artifact.
- **Position 05 framework lenses** — unauthored.
- **Real-backend first-attempt hit rate for `roadmap-components.md`** — needs production briefs and a recording surface; canned tests prove satisfiability only.
- **Consolidating the three generate-parse-retry loops** (`detail.py`, `create.py`, `roadmap.py`) — cross-module refactor; route to reconcile or `BACKLOG.md`, not this step.
- **A components revision before/after example in `ROADMAP_FORMAT.md`** — step 4 optional parity; domain revision already demonstrates review collections.
- **Extracting a shared prompt prose block across three authoring templates** — duplication is intentional until a dedicated consolidation effort says otherwise.
