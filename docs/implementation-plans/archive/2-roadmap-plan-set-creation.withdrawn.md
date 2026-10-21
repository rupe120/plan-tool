> **Withdrawn 2026-10-16** — Owner correction 2026-10-16: improve existing roadmap mapping to seeds to plans; the separate opt-in plan-set layer exceeds the requested scope. Replacement effort: roadmap-plan-derivation, BACKLOG #496.
> Preserved here for history; do not edit.

---
format_version: 1
title: Roadmap Plan Set Creation
intent: An explicit opt-in roadmap-to-plan-set authoring route reads one pinned accepted
  roadmap artifact bundle and the current repository, derives a dependency-ordered
  set of bounded implementation plans, and authors their base plans through existing
  create machinery. The set retains accepted scope and source attribution while allowing
  several implementation slices beneath one roadmap row when necessary. A saved set
  record names the source version, derived members, responsibility assignments, dependencies
  and unresolved prerequisites; it is an inspectable authoring record, not certification
  of semantic completeness.
status: planning
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: plan-seeds/roadmap-plan-set-creation.md
steps:
- id: 1
  title: Define the source-bound plan-set record and structural checks
  intent: The implementation breakdown remains inspectable and traceable to one accepted
    roadmap version.
  creates:
  - plan_tool/roadmap_plan_set_artifacts.py
  - tests/test_roadmap_plan_set_artifacts.py
  - ROADMAP_PLAN_SET_FORMAT.md
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/roadmap-plan-set-creation/01-define-source-bound-plan-set-record.md
  status: current
- id: 2
  title: Derive the complete implementation set before authoring individual plans
  intent: Shared producers, consumers and acceptance responsibilities inform the breakdown
    before individual plans are drafted.
  files:
  - TESTING.md
  creates:
  - plan_tool/roadmap_plan_set.py
  - plan_tool/prompts/roadmap-plan-set.md
  - tests/test_roadmap_plan_set.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: Provides the record, source references and structural validation used to accept
      derived output.
  detail: docs/implementation-plans/plan-details/roadmap-plan-set-creation/02-derive-complete-implementation-set.md
- id: 3
  title: Author members serially with safe retry, replacing only owned progress records
    and preserving completed plans and seeds
  intent: Interrupted authoring resumes without losing source identity or overwriting
    completed or unrelated work.
  files:
  - plan_tool/roadmap_plan_set.py
  - tests/test_roadmap_plan_set.py
  complexity: high
  change_type: feature
  depends_on:
  - 2
  depends_on_notes:
    2: Provides the validated complete breakdown before any member authoring begins.
  detail: docs/implementation-plans/plan-details/roadmap-plan-set-creation/03-author-members-serially-safe-retry.md
- id: 4
  title: Expose opt-in plan-set creation through authoring while preserving existing
    single-plan behavior
  intent: One invocation derives and authors the set while existing create and roadmap-row
    routes retain their contracts.
  files:
  - plan_tool/cli/authoring.py
  - tests/cli/test_authoring_cmds.py
  - tests/cli/test_cli_parser.py
  - CAPABILITIES.md
  - docs/cli/create.md
  - plan_tool/roadmap_plan_set.py
  - tests/test_roadmap_plan_set.py
  complexity: medium
  change_type: feature
  depends_on:
  - 3
  depends_on_notes:
    3: Provides serial authoring, source rechecks, collision protection and retry
      outcomes for the CLI.
  detail: docs/implementation-plans/plan-details/roadmap-plan-set-creation/04-expose-opt-plan-set-creation-through.md
- id: 5
  title: Compare baseline and plan-set authoring on equivalent isolated Integration inputs
  intent: Raw output shows whether the new route addresses witnessed gaps without
    confusing plan count or session repairs with improvement.
  files:
  - docs/evidence/roadmap-plan-set-benchmark.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 4
  depends_on_notes:
    4: Provides the runnable opt-in route for comparison against the unchanged baseline.
  detail: docs/implementation-plans/plan-details/roadmap-plan-set-creation/05-compare-baseline-plan-set-authoring-on.md
- id: 6
  title: 'Document plan-set ownership and recovery and reconcile BACKLOG #496 after
    shipment'
  intent: Users understand the set's authority limits, retry procedure and remaining
    obligations.
  files:
  - ROADMAP_PLAN_SET_FORMAT.md
  - ROADMAP_FORMAT.md
  - docs/how-to/roadmap.md
  - docs/ARCHITECTURE.md
  - BACKLOG.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 4
  - 5
  depends_on_notes:
    4: Supplies the implemented command, ownership boundaries and recovery behavior
      to document.
    5: Supplies comparison evidence and explicit limitations for the shipment record.
  detail: docs/implementation-plans/plan-details/roadmap-plan-set-creation/06-document-plan-set-ownership-recovery.md
---
# Roadmap Plan Set Creation

## Overview

An explicit opt-in roadmap-to-plan-set authoring route reads one pinned accepted roadmap artifact bundle and the current repository, derives a dependency-ordered set of bounded implementation plans, and authors their base plans through existing create machinery. The set retains accepted scope and source attribution while allowing several implementation slices beneath one roadmap row when necessary. A saved set record names the source version, derived members, responsibility assignments, dependencies and unresolved prerequisites; it is an inspectable authoring record, not certification of semantic completeness.

## Problem statement

Existing roadmap materialization is scoped to one accepted row: plan_tool/prompts/roadmap-seed.md authors one selected accepted row and forbids changing the plan mapping, while plan_tool/roadmap.py:materialize_plan_seed owns per-row seed materialization. Existing create remains single-plan scoped, and unrelated split suggestions in plan_tool/prompts/distill-seed.md do not supply whole-set derivation. Local per-plan success can therefore hide an absent shared producer, consumer integration or acceptance route. This effort adds whole-set derivation before individual authoring, preserving accepted scope while allowing the implementation breakdown to differ from roadmap-row identities.

## Architecture

Derive the implementation breakdown across the complete accepted roadmap bundle before authoring individual plans. Treat accepted roadmap rows as scope/provenance anchors and keep logical components distinct from implementation routes. Split cohesive work when producer, consumer integration or acceptance responsibilities require independently bounded, dependency-ordered routes; do not split merely by directory or inflate the plan count. Assign shared implementation ownership once and identify its consumers. Explicit source prohibitions remain binding, and conflicts are surfaced rather than reinterpreted.

Expose the route explicitly through the existing authoring command group. Reuse accepted-version readers, authoring invokers and create orchestration. A small dedicated orchestrator and artifact leaf may own the set boundary where per-row materialization cannot represent it. Existing accepted-row membership and lifecycle ownership in plan_tool/roadmap_seed_manifest.py and plan_tool/roadmap_seed_state.py remain untouched; unrelated roadmap and create flows are not refactored.

Persist a small derived-set record and source-bound seeds. The record binds the selected source version, derived member identities, roadmap-row attribution, responsibility assignments, ordered dependencies, unresolved prerequisites and actual authored destinations. Structural validation checks identities and relationships, including invalid source references, unsafe paths, cycles and conflicting output targets. Every accepted plan row must be attributed to at least one derived member, and every derived member must cite at least one accepted plan row. These are source-representation checks only; they do not validate semantic coverage or implementation granularity. A failed or interrupted serial run retains completed outputs, reports uncompleted members and supports retry without silently overwriting unrelated or previously authored plans. Recheck source identity before further authoring after drift, without silently switching to a newer accepted head.

Reuse plan_tool/cli/authoring.py:cmd_create and plan_tool/create.py:create_plan for individual base-plan authoring, registration and native logging. Deliver complete compact set/source/ownership context through seeds and References. Detail and completeness-audit remain their existing stages. Generated plans preserve shared producer/consumer obligations and assign eventual observed acceptance proof to an executable route whose completion requires that evidence; a written procedure does not discharge an accepted live-demonstration outcome. Unknown provider or owner evidence remains an explicit prerequisite rather than an invented mechanism.

This effort originates in BACKLOG #496. Update the originating backlog when the work ships: authoring alone retains a plan-authored entry; remove it only after full shipment, keeping deferred work explicit.

## Input

An explicit opt-in roadmap-to-plan-set authoring route reads one pinned accepted roadmap artifact bundle and the current repository, derives a dependency-ordered set of bounded implementation plans, and authors their base plans through existing create machinery. The set retains accepted scope and source attribution while allowing several implementation slices beneath one roadmap row when necessary. A saved set record names the source version, derived members, responsibility assignments, dependencies and unresolved prerequisites; it is an inspectable authoring record, not certification of semantic completeness.

Hermetic tests prove the route reads one selected accepted version, supplies the complete artifact bundle and repository grounding to set derivation, validates structural output, carries each slice’s source/owner/dependency content into its seed and create input, and registers only its actual authored plans. Cover one row producing several ordered slices, several rows sharing a necessary producer, retained integration and live-acceptance responsibilities, unknown prerequisites, source drift, existing destinations, partial failure and safe retry without overwriting unrelated or completed work. Existing one-row seed materialization and ordinary create keep their contracts. Run the changed tool and baseline against equivalent isolated Integration inputs with the same model, source version and declared context; retain raw outputs and session corrections separately. Review uncovered obligations, overly broad routes, dependency/ownership gaps and acceptance dilution against a frozen witnessed-gap corpus. A greater plan count or a clean audit is not evidence of improvement by itself.

- ROADMAP_FORMAT.md — accepted-head authority, component-to-plan dispositions and seed provenance.
- plan_tool/prompts/roadmap-seed.md — currently authors only one selected accepted row and forbids changing the plan mapping.
- plan_tool/roadmap.py:materialize_plan_seed — owns per-row seed materialization; do not overload its accepted-row state.
- plan_tool/roadmap_seed_manifest.py and plan_tool/roadmap_seed_state.py — current accepted-row membership/lifecycle ownership.

- docs/evidence/roadmap-plan-set-benchmark.md — frozen Integration source, witnessed gaps, generated artifacts, intervention limits and tool-instrument observations.

## Scope guardrails

Preserve the exact Outcome and all seven scope fields from BACKLOG #496 above. The target is creation of the implementation plan set from the roadmap artifact bundle, not repair of Integration or a new audit product. Machine enforcement covers structural state only; semantic completeness and appropriate granularity remain judged content. Do not add scores, fixed plan counts, semantic gates, acceptance weakening, automatic approval, source mutation, live application execution, provider probes, or cross-plan-audit/status/shared-context features.

## References

- BACKLOG.md — #496 owns this effort and its scope contract; #462, #493 and #494 remain separate.
- MISSION.md — deterministically driven non-determinism and downstream impact.
- ROADMAP_FORMAT.md — accepted-head authority, component-to-plan dispositions and seed provenance.
- plan_tool/prompts/roadmap-seed.md — currently authors only one selected accepted row and forbids changing the plan mapping.
- plan_tool/roadmap.py:materialize_plan_seed — owns per-row seed materialization; do not overload its accepted-row state.
- plan_tool/roadmap_seed_manifest.py and plan_tool/roadmap_seed_state.py — current accepted-row membership/lifecycle ownership.
- plan_tool/cli/authoring.py:cmd_create and plan_tool/create.py:create_plan — existing individual authoring boundary and manifest integration.
- plan_tool/prompts/distill-seed.md — currently prefers a single plan for a large cohesive effort; unrelated split suggestions do not supply whole-set derivation.
- docs/explanations/roadmap-plan-handoff.md — existing prose/reference input delivery works with session verification; it does not establish whole-set decomposition quality.
- docs/evidence/roadmap-plan-set-benchmark.md — frozen Integration source, witnessed gaps, generated artifacts, intervention limits and tool-instrument observations.
- SEED_FORMAT.md and integrations/shared/DIRECTIVES.md — seed-altitude review and the bare/detail gates.

- [graphlib — Functionality to operate with graph-like structures](https://docs.python.org/3.13/library/graphlib.html) — Documents topological ordering and cycle detection for validating dependencies and ordering serial plan authoring.
- [pathlib — Object-oriented filesystem paths](https://docs.python.org/3.13/library/pathlib.html) — Documents path resolution and filesystem operations for checking destination containment and conflicting output targets.
- [argparse — Parser for command-line options, arguments and subcommands](https://docs.python.org/3.13/library/argparse.html) — Provides the API reference for adding the explicit opt-in authoring route to the existing CLI.
- [os — Miscellaneous operating system interfaces](https://docs.python.org/3.13/library/os.html#os.replace) — Documents file creation and atomic replacement semantics needed to persist retry state while protecting existing outputs.
- [pytest API Reference](https://docs.pytest.org/en/latest/reference/reference.html) — Documents temporary-directory and monkeypatch fixtures for hermetic source-drift, partial-failure and safe-retry tests.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

No application implementation or execution in Integration, deployments, provider probes, publication, or manual Integration restructuring as the feature deliverable. No accepted roadmap mutation, new roadmap stage, approval lifecycle, source migration or replacement of accepted seed-state ownership. No cross-plan audit command (#462), shared-context admission system (#493), prerequisite status projection (#494), automatic completeness certification, semantic quality gate, coverage score, plan/step size cap, target plan count or automatic approval. No changes to completeness blocking predicates, exit-code conventions, run scheduling, Jira export or the existing single-plan create behavior. No concurrent authoring or shared-state merge machinery.

## Risks

- Confusing accepted roadmap rows with implementation plan identities can either forbid useful refinement or silently change accepted scope; keep the source relationship explicit.
- Local per-plan success can hide an absent shared producer or acceptance route; whole-set context must be delivered before individual authoring rather than inferred from a final count.
- The existing Integration replay includes retrospective evidence and session corrections, so it is a failure corpus, not a matched efficiency result. New comparisons require equivalent inputs and separately retained raw output.

## Testing

Hermetic tests prove the route reads one selected accepted version, supplies the complete artifact bundle and repository grounding to set derivation, validates structural output, carries each slice’s source/owner/dependency content into its seed and create input, and registers only its actual authored plans. Cover one row producing several ordered slices, several rows sharing a necessary producer, retained integration and live-acceptance responsibilities, unknown prerequisites, source drift, existing destinations, partial failure and safe retry without overwriting unrelated or completed work. Existing one-row seed materialization and ordinary create keep their contracts. Run the changed tool and baseline against equivalent isolated Integration inputs with the same model, source version and declared context; retain raw outputs and session corrections separately. Review uncovered obligations, overly broad routes, dependency/ownership gaps and acceptance dilution against a frozen witnessed-gap corpus. A greater plan count or a clean audit is not evidence of improvement by itself.

## Acceptance criteria

- Every accepted plan row is represented in at least one member attribution, every member has accepted-row attribution, and omitted or foreign rows are reported by identifier. Passing this structural check makes no claim about the quality or completeness of the represented implementation.

One explicit opt-in invocation derives and authors a source-bound implementation set from the complete accepted roadmap bundle. Structural validation and serial retry preserve source identity, dependencies, completed members and unrelated project files. Generated content assigns shared producers, consumer integration and eventual acceptance responsibilities, with unknown evidence explicit. Existing single-plan and roadmap-row authoring remain compatible. The isolated comparison records raw output and judged gap coverage without claiming semantic certification or savings from one sample.

Source entry: BACKLOG #496. Update the originating backlog when this work ships: authoring alone retains a plan-authored entry; remove it only after full shipment, keeping any deferred work explicit.

## Deferred

Surface an accepted-scope or settled-decision conflict instead of broadening the roadmap. A derived implementation slice is not a new accepted roadmap row. Missing provider or owner evidence remains an explicit prerequisite; do not invent mechanisms that depend on its unknown result. If the smallest whole-set route requires a new approval/source-authority system or changes existing execution policy, stop and propose separately scoped work. File unrelated defects in BUG_BACKLOG.md and forward-looking work in BACKLOG.md. Keep #462/#493/#494 independently gated.
