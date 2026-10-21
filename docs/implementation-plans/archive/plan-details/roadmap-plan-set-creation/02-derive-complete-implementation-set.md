> **Withdrawn 2026-10-16** — Owner correction 2026-10-16: improve existing roadmap mapping to seeds to plans; the separate opt-in plan-set layer exceeds the requested scope. Replacement effort: roadmap-plan-derivation, BACKLOG #496.
> Preserved here for history; do not edit.

# Step 2 — Derive the complete implementation set before authoring individual plans

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Create `plan_tool/roadmap_plan_set.py` and `plan_tool/prompts/roadmap-plan-set.md` to derive a complete implementation breakdown from one pinned accepted roadmap and the current repository. Reuse step 1’s record and structural checks instead of defining another output contract. Derive shared responsibilities, consumers, dependencies and acceptance ownership together before any individual plan authoring begins. Add hermetic tests in `tests/test_roadmap_plan_set.py` and document the backend seam in `TESTING.md`; on green, callers receive a structurally valid, source-bound set or an explicit derivation failure.

## Table of Contents

- [Summary](#summary) — Deliverables and observable result.
- [Table of Contents](#table-of-contents) — Section navigation.
- [Why](#why) — Why per-row authoring cannot supply this boundary.
- [Input](#input) — Source authority, upstream contract and evidence limits.
- [Files (creates vs edits)](#files-creates-vs-edits) — New modules, prompt and testing documentation.
- [Implementation](#implementation) — Source selection, whole-set prompting and validation.
- [Tests](#tests) — Cases that establish the derivation boundary.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Source contracts and relevant examples.
- [Applicable guardrails](#applicable-guardrails) — Boundaries on generation and enforcement.
- [Deferred](#deferred) — Persistence, member authoring and later integration.

## Why

`plan_tool/prompts/roadmap-seed.md` limits generation to one accepted row and forbids changing its plan mapping. `plan_tool/roadmap.py:materialize_plan_seed` implements that boundary, while `plan_tool/prompts/distill-seed.md` addresses an individual seed rather than the complete roadmap. Neither boundary gives shared producers, their consumers and eventual acceptance routes a common breakdown before individual plans are drafted. This step adds that common derivation without changing accepted roadmap membership or either existing authoring route.

## Input

- **Step 1’s output:** Step 1 provides the source-bound set record, parser, renderer, structural checks and dependency ordering in `plan_tool/roadmap_plan_set_artifacts.py`. Read the landed names and signatures before implementing; they take precedence over names suggested in earlier detail prose.
- **Accepted selection:** `plan_tool/roadmap_versions.py:load_accepted_version` returns a `ResolvedRoadmapVersion` or no accepted version. Its `record`, `brief_bytes`, `artifact_bytes` and `artifact_keys` provide the selected identity and exact source content.
- **Accepted relationships:** `plan_tool/roadmap_artifacts.py:PlansArtifact`, `PlanRow`, `OrderingEntry` and `AssumptionRow` supply source attribution, intent, non-goals, ordering and assumptions. Derived member identities remain separate from those accepted row identities.
- **Repository grounding:** Supply the current repository location and require inspection before deriving the set, following the grounding stance in `plan_tool/prompts/roadmap-seed.md`.
- **Evidence limits:** Canned responses prove that the prompt contract is satisfiable and that orchestration preserves supplied content. They do not prove that a real model usually derives a complete or appropriately sized set.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_plan_set.py` — Accepted-source selection, prompt assembly, injectable backend call and bounded structural-validation loop.
  - `plan_tool/prompts/roadmap-plan-set.md` — Whole-set derivation instructions and the step 1 output contract.
  - `tests/test_roadmap_plan_set.py` — Source, prompt, validation, retry and side-effect boundary tests.

- **Existing files (edits only):**
  - `TESTING.md` — Add the new production invoker and its neutralization method to the backend fallback seam table.

## Implementation

- **Foundational logic: derive and structurally validate the whole set before member authoring.** Add a focused entry point in `plan_tool/roadmap_plan_set.py`; a name such as `derive_plan_set` is recommended. It must return step 1’s validated record with its dependency order, or report a failure without returning rejected output as usable content.

- **Pin accepted source once.** Use `plan_tool/roadmap_versions.py:load_accepted_version` and retain its selected identity and bytes throughout derivation and correction attempts. Missing accepted content must fail before a backend call. Do not combine separately selected artifact versions or silently reload a newer head during retry.

- **Deliver the complete source context.** Render the selected brief and every artifact in the pinned bundle, with their identities and clear boundaries. Supply the current repository location and instruct the model to inspect relevant code. Do not substitute only `plan_tool/roadmap_artifacts.py:PlansArtifact` or a selected row for the complete bundle.

- **Derive responsibilities together.** The prompt must ask for bounded members with source attribution, shared producer ownership, consumer integration, dependencies, unresolved prerequisites and eventual acceptance ownership. Permit several members beneath one source row and one shared member attributed to several rows. Recommend splitting by independently bounded responsibilities rather than directories or a desired member count.

- **Preserve accepted obligations in generated content.** The prompt must retain source prohibitions, settled choices and accepted ordering constraints. Account for every accepted plan row through at least one derived member and give every member source attribution; step 1 mechanically checks this representation without certifying semantic coverage. It must assign an accepted live-evidence obligation to a route whose completion requires that evidence, rather than treating a written procedure as completion. Unknown provider or owner evidence must remain an explicit prerequisite; source conflicts must be surfaced without inventing a resolution.

- **Keep judgments in the prompt and structure in code.** Reuse step 1’s checks against the pinned inventory and caller-resolved destination roots. Do not add prose classifiers for coverage, granularity or acceptance quality. A structurally valid record must not acquire a completeness certification.

- **Use the existing prompt-loading convention.** Load the template through `plan_tool/renderer.py:prompts_dir` and substitute with `string.Template.safe_substitute`, matching `plan_tool/roadmap.py:_render_stage_prompt`. The plan renderer’s `plan_tool/renderer.py:render_prompt` requires plan-specific inputs, so do not manufacture a plan merely to call it. Missing templates must produce an error naming the expected path.

- **Make the installed prompt self-contained.** Describe step 1’s landed output schema inside `plan_tool/prompts/roadmap-plan-set.md`; do not require the consuming repository to contain `ROADMAP_PLAN_SET_FORMAT.md`. Keep template placeholders aligned with the supplied variable map. If an example is included, use placeholder content and validate it through the real parser and checks.

- **Expose an injectable backend seam.** Follow the `(rc, stdout)` shape of `plan_tool/roadmap.py:shell_roadmap_invoker`, delegating production invocation to `plan_tool/shell.py:claude_invoke`. Keep the new orchestration independent of the stage runner and row materializer. Document the actual landed seam in `TESTING.md`.

- **Bound correction attempts.** Recommend one initial attempt and two corrections under one named constant. Nonzero invocation results, empty output, parse failures and structural violations must consume that shared budget. Feed self-contained errors into the next prompt while retaining the same pinned source; leave transport recovery to `plan_tool/shell.py:claude_invoke`.

- **Keep response tolerance outside the parser.** If lifting fences or preamble is necessary, do it locally before calling step 1’s strict parser. Do not weaken the persisted contract to accommodate backend formatting. Return parsed records rather than exposing raw model text as the accepted result.

- **Leave authoring state untouched.** This entry point must not write set records, seeds or plans, register manifest members, or call individual create machinery. Reuse step 1’s dependency ordering unchanged. Step 3 consumes the complete validated result and owns durable writes and serial member authoring.

## Tests

### Tests for this step

Add the following in `tests/test_roadmap_plan_set.py`. Use fake invokers and temporary repositories; every case must be green before completion. Run the focused suite and repository suite. For rejection and ordering guarantees, temporarily disable the relevant behavior and confirm the named test fails.

- `test_derivation_uses_one_accepted_version_for_the_complete_bundle` — Every supplied artifact and source identity comes from one accepted selection.
- `test_missing_accepted_source_fails_before_backend_invocation` — No accepted head produces an explicit failure without calling the invoker.
- `test_prompt_contains_pinned_brief_all_artifacts_and_repository_location` — Whole-set generation receives complete source content and grounding instructions.
- `test_retry_keeps_the_original_selected_source` — Advancing the accepted head during a fake call does not switch correction inputs.
- `test_one_source_row_can_produce_ordered_implementation_slices` — A canned valid breakdown retains several members beneath one accepted row.
- `test_shared_producer_retains_multiple_source_rows_and_consumers` — Shared ownership and all supplied consumer relationships survive parsing and validation.
- `test_prompt_preserves_source_fences_and_executable_acceptance_ownership` — The template instructs preservation of prohibitions, settled choices and completion evidence.
- `test_unresolved_prerequisites_remain_valid_without_invented_resolution` — Unknown evidence survives in the returned record.
- `test_structural_violations_feed_the_next_attempt_with_identifiers` — Real step 1 violations reach the correction prompt with their relevant references.
- `test_invocation_empty_parse_and_validation_failures_share_one_budget` — Failure kinds do not receive separate attempt allowances.
- `test_exhaustion_returns_no_usable_set` — Rejected output never becomes the result after the budget expires.
- `test_valid_set_uses_step_one_dependency_order` — Dependencies precede consumers and unrelated members retain the upstream ordering rule.
- `test_response_lifting_does_not_weaken_the_artifact_parser` — Supported response wrapping is handled locally while malformed artifact content remains rejected.
- `test_prompt_schema_matches_the_landed_record_contract` — Required schema names and vocabulary agree with step 1’s implementation.
- `test_prompt_placeholders_are_supplied_and_fully_rendered` — No unresolved template variables reach the invoker.
- `test_missing_prompt_error_names_the_expected_path` — Template-loading failures identify the missing asset.
- `test_derivation_does_not_author_or_mutate_project_outputs` — Source files, accepted seed state, manifest and plan destinations remain unchanged.
- `test_production_invoker_delegates_to_the_existing_shell_seam` — A patched shell call proves delegation without spawning a backend.

## Acceptance criteria

- The three declared new files exist, and `TESTING.md` documents the landed backend seam.
- Derivation supplies one accepted bundle, its brief and repository grounding before requesting the complete breakdown.
- Valid records preserve many-to-many attribution, shared responsibilities, acceptance ownership and unresolved prerequisites.
- Structural failures receive bounded correction attempts against the same pinned source.
- Exhaustion returns an explicit failure and no usable rejected record.
- Successful derivation returns step 1’s validated record and dependency order without authoring plans or changing accepted state.
- Prompt checks verify the installed template’s schema and variable contract without requiring repository-root format documentation at runtime.
- `uv run pytest tests/test_roadmap_plan_set.py -q` and `uv run pytest tests/ -q -n auto` pass.

## References

- [BACKLOG.md](../../../BACKLOG.md) — Entry #496 owns the outcome and scope contract.
- [ROADMAP_FORMAT.md](../../../ROADMAP_FORMAT.md) — Read accepted-source authority and roadmap relationships.
- [plan_tool/roadmap_versions.py](../../../plan_tool/roadmap_versions.py) — Use verified accepted-version selection and pinned content.
- [plan_tool/prompts/roadmap-seed.md](../../../plan_tool/prompts/roadmap-seed.md) — Preserve its existing per-row boundary and repository-grounding stance.
- [docs/explanations/roadmap-plan-handoff.md](../../../docs/explanations/roadmap-plan-handoff.md) — Read the limits of existing source-context delivery.
- [docs/evidence/roadmap-plan-set-benchmark.md](../../../docs/evidence/roadmap-plan-set-benchmark.md) — Read witnessed producer, integration and acceptance gaps without treating them as quality certification.
- [MISSION.md](../../../MISSION.md) — Keep judged generation bounded by deterministic validation.

## Applicable guardrails

- **The plan’s “## Scope guardrails,” structural enforcement:** The new retry loop must act on step 1’s structural results without adding semantic quality decisions.
- **The plan’s “## Architecture,” accepted authority:** Prompting must preserve accepted scope while deriving separate implementation identities.
- **The plan’s “## Out of scope,” existing behavior:** Keep existing row materialization, single-plan creation and execution policy unchanged.
- **The plan’s “## Deferred,” unknown evidence:** Generated prerequisites must expose missing evidence without choosing mechanisms dependent on it.
- **The plan’s “## Scope guardrails,” feature boundary:** The prompt and orchestrator must remain within the plan’s listed exclusions; derivation must not execute application work.

## Deferred

- Durable set records, source-bound seeds, source rechecks before further authoring and safe retry of completed outputs — Step 3 owns persistence and serial authoring.
- `plan_tool/cli/authoring.py:cmd_create` and `plan_tool/create.py:create_plan` integration — Steps 3 and 4 connect validated members to existing authoring machinery.
- Changes to `plan_tool/roadmap.py:materialize_plan_seed`, `plan_tool/roadmap_seed_manifest.py:classify_draft_seeds` or accepted seed-state ownership — Existing per-row behavior remains separate; changing its authority requires intentional shared work.
- Refactoring sibling generation loops in `plan_tool/roadmap.py` or `plan_tool/create.py` — Similar control flow does not require shared authority or a consolidation in this step.
- Real-model decomposition quality and hit-rate evidence — Step 5 owns the isolated comparison; canned-response tests cannot establish those properties.
- Operator recovery documentation and backlog shipment reconciliation — Step 6 owns those outcomes.
