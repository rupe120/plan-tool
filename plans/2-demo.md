---
title: Demo
status: planning
priority: medium
effort: 1 week, splittable
steps:
- id: 1
  title: first
  complexity: low
  status: current
---
# Demo

## Overview

This plan is a deliberately minimal fixture used by the `plan-tool` skill (see `plan_tool/cli.py`) to exercise its audit, apply, and iterate flow without coupling tool development to real in-flight plans. It introduces no runtime code or infrastructure — only the plan file itself at `plans/2-demo.md` and, if Step 1 ever gains one, a corresponding detail file under `plans/details/2-demo/`. The single-step shape (`id: 1`, `title: first`, `complexity: low`, `status: current`) is intentional: it gives the iterator a fixed target for status, files, and detail edits. Load-bearing constraint: this plan must not advance beyond `status: planning` while sections remain generic — promotion requires first attaching real scope, which is a separate plan rather than an in-place rewrite.

## Problem statement

The `plan-tool` skill needs a minimal, well-formed fixture plan to exercise its audit/apply/iterate loop against. Without one, every change to the tool has to be validated against real, in-flight project plans — which couples tool development to unrelated work and risks corrupting live plans during development. The user-visible symptom is that contributors hacking on `plan-tool` (see `plan_tool/cli.py`) have no isolated target to dry-run findings against, so iteration on the tool is slower and riskier than it should be. This plan fills that gap by serving as a stable, deliberately minimal scaffold.

## Architecture

- **Scope of this plan**: a demonstration plan used to exercise the `plan-tool` flow (completeness audit, apply, iteration). No production components are introduced and the existing dependency graph is untouched — nothing in `amplify/`, `apps/`, or `packages/shared/` is wired in or modified by this plan.
- **Components introduced**: only the plan file itself (`plans/2-demo.md`) and, if Step 1 ever gains a detail file, the corresponding `plans/details/2-demo/step-1.md`. No runtime code, no Lambdas, no schema changes, no infrastructure constructs.
- **How it interacts with the codebase**: the plan sits inside `.agents/skills/plan-tool/plans/` and is consumed exclusively by the `plan-tool` skill. It does not import from, deploy alongside, or reference any application module. The single step ("first", low complexity) is a placeholder slot so the tooling has a concrete target for status, files, and detail edits.
- **Design trade-offs**: kept deliberately minimal because the plan's purpose is structural rather than feature-bearing. The trade-off is that sections like Overview, Problem statement, and Acceptance criteria stay generic — that is the right shape for a demo, but it means this plan must not be promoted to `in-progress` as-is without first attaching real scope. Once concrete work is assigned, this section should be rewritten to describe the actual components and interactions rather than the demo framing.

## References

- `.agents/skills/plan-tool/SKILL.md` — defines the `plan-tool` skill this fixture is exercised by; pins the audit/apply/iterate contract that the plan must remain valid against.
- `.agents/skills/plan-tool/PLAN_FORMAT.md` — canonical plan schema (frontmatter shape, required section headings, status values); this fixture's structure is asserted against it in the Acceptance criteria.
- `.agents/skills/plan-tool/plan_tool/cli.py` — entry point cited in Overview and Problem statement as the tool consuming this plan; relevant when verifying that audit/apply commands dispatch correctly on the fixture.
- `.agents/skills/plan-tool/README.md` — human-facing overview of the skill and its commands; useful context for contributors who pick up this fixture without prior exposure to the tool.
- `.agents/skills/plan-tool/RUNBOOK.md` — operational guidance for running the iterator; matters here because this plan is the target the runbook examples can be safely demonstrated against.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- **Runtime/application code changes**: nothing under `amplify/`, `apps/`, or `packages/shared/` is touched — this plan exercises the `plan-tool` flow only, so wiring into the app would defeat its purpose.
- **Promotion beyond `planning` status**: this plan must not advance to `in-progress` while Overview, Problem statement, and Acceptance criteria remain generic — concrete scope must be attached first, and that re-scoping is a separate plan.
- **Additional steps beyond Step 1**: the single-step shape is intentional so the iterator has a fixed target; expanding to multi-step is deferred until a real workload justifies it (and would supersede this plan rather than amend it).
- **Infrastructure, CI/CD, and deployment artifacts**: no CDK constructs, buildspec edits, or pipeline changes — the demo is a pure plan-file exercise and any infra coupling would obscure that.
- **Cross-repo work in `example-app-infra`**: this plan lives in the Amplify repo's `.agents/skills/plan-tool/plans/` and does not coordinate with the infra repo; cross-repo demos are a separate concern.

## Risks

- **Scope ambiguity from unfilled sections**: Overview, Problem statement, Architecture, Testing, and Acceptance criteria are all `_(TODO)_`, so implementation can drift from intent unnoticed. Severity: high. Mitigation: fill those sections before Step 1 begins. Unresolved gap: no concrete success signal exists yet.
- **Step 1 has no detail file**: "first" is declared at low complexity with no detail file, so its scope is implicit and reviewers cannot pin down what "done" means. Severity: medium. Mitigation: add a detail file or expand the step title to be self-describing. Unresolved gap: files-coherence cannot be checked without a declared `files:` set.
- **Single-step plan offers no incremental checkpoints**: with only one step, partial progress cannot be validated and a stall blocks the whole plan. Severity: medium. Mitigation: split the step if the work turns out non-trivial. Unresolved gap: splittability claim (`effort: 1 week, splittable`) is asserted but unproven.
- **Risks register itself is shallow**: this section was just promoted out of `_(TODO)_` against a near-empty plan, so the failure modes listed here are structural rather than domain-specific. Severity: low. Mitigation: revisit this section as Overview/Problem statement concretize. Unresolved gap: domain-specific risks (data, dependencies, rollout) are not yet enumerable.

## Testing

- **Convention**: unit-first. Default to tests that exercise one function or class in isolation, colocated with the code they cover. Reserve integration tests for cross-module wiring that a unit test would miss (Lambda handlers driven end-to-end, AppSync resolver pipelines, cross-package flows through `@example-app/shared`).
- **Tier markers**: there is no repo-root `TESTING.md`, so follow the existing per-area conventions — Jest for `amplify/test/*.test.ts` (run via `pnpm test:unit`), Vitest for Lambda handlers under `amplify/test/lambda/*.test.ts` (run via `pnpm test:vitest`), Vitest + jsdom for `apps/web/src/**/*.test.{ts,tsx}` (run via `pnpm --filter @example-app/web test`), and Python tests for the Bedrock agent (run via `pnpm test:python`). Use `*.integration.test.ts` for any new cross-module suites and keep them out of the default unit run.
- **New tests to add**: cannot be enumerated yet — Step 1 ("first") has no detail file and no declared `files:` set, so specific paths and test-case names would be fabricated. Populate this list once Step 1's scope is pinned down (file paths + the `describe`/`it` or function names that will be added).
- **Existing suites that must still pass**: `pnpm lint`, `pnpm test` (which runs `test:unit`, `test:vitest`, and `test:python`), and `pnpm --filter @example-app/web test`. Any change touching `packages/shared/src/**` must also be exercised through a consumer (web or mobile) since the shared library is compiled, not bundled.
- **Integration tests to re-run on touched areas**: deferred until Step 1 declares which conceptual area it touches (auth, data/AppSync resolvers, Lambda handlers, mentor chat, LaborDataService pipeline, etc.). Each of those areas has an associated Vitest or Jest suite that the iterator must run when the corresponding source files change.

## Acceptance criteria

- `plans/2-demo.md` parses cleanly: YAML frontmatter loads without error and the body contains the canonical section headings (`## Overview`, `## Problem statement`, `## Architecture`, `## References`, `## Steps`, `## Out of scope`, `## Risks`, `## Testing`, `## Acceptance criteria`, `## Deferred`).
- Running `plan-tool completeness plans/2-demo.md` reports no finding against the `## Acceptance criteria` section (specifically, no `_(TODO)_` placeholder remains here).
- The frontmatter `steps:` block contains exactly one entry with `id: 1`, `title: first`, `complexity: low`, and `status: current`; no other step entries exist.
- The frontmatter `status:` field is one of the recognized values (`planning`, `in-progress`, `done`, `blocked`) — currently `planning` — so downstream `plan-tool` commands can dispatch on it without falling through.

## Deferred

- None postponed yet — populate this list during implementation as items get pushed out, each as a one-line bullet naming the item and the reason (too large for this plan, blocked on external work, separate concern). Items here are candidates to revisit; permanent exclusions belong in `## Out of scope`.
