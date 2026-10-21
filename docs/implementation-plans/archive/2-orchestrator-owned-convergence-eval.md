---
title: Run-Grade Plan-Audit Convergence Eval
intent: Add one non-mutating `plan-tool convergence-eval` command that gives a
  developer an evidence-bound advisory outlook for one explicitly selected,
  current run-grade plan-audit report. It replaces the public mechanical
  convergence verdict without changing finding-application authority.
status: planning
priority: medium
risk_profile: standard
risk_profile_rationale: The command is advisory and read-only, but it must not
  represent stale report evidence as current or admit a conclusion its selected
  report cannot support.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: plan-seeds/convergence-eval-plan-audit-v1.md
steps:
- id: 1
  title: Freeze the run-grade convergence-evaluation corpus and safety predicate
  intent: It fixes representative accepted, refused, malformed, stale, and
    ambiguous-report cases before prompt tuning. Only an accepted `converged`
    that conflicts with the existing qualified clean-or-low-yield allowance is
    unsafe.
  creates:
  - benchmarks/corpus/convergence-eval/cases.json
  - benchmarks/corpus/convergence-eval/README.md
  - tests/test_convergence_eval_corpus.py
  complexity: medium
  change_type: non-code
- id: 2
  title: Define the run-grade report envelope and deterministic refusal contract
  intent: It gives the supported context one immutable in-memory evidence
    envelope, current material finding identities, outcome eligibility,
    response fields, a closed `next_action` shape, and refusal conditions
    without a history reader, code-state claim, or persisted evaluator record.
  creates:
  - plan_tool/convergence_eval.py
  - tests/test_convergence_eval.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: the corpus safety rule and input cases shape the shared contract
- id: 3
  title: Validate and render a judge reply against the selected envelope
  intent: It rejects unknown or multiple outcomes, incomplete or extra material
    finding coverage, unresolved citations, and any next action other than the
    envelope-bound review form. It renders accepted advice and deterministic
    refusals at exit zero, uses exit two for parser or selector usage errors,
    and uses exit one for evaluator operational failures.
  creates:
  - plan_tool/convergence_eval_response.py
  - tests/test_convergence_eval_response.py
  complexity: high
  change_type: feature
  depends_on:
  - 2
  depends_on_notes:
    2: the envelope supplies the closed vocabulary, eligible outcomes, and
      exact current finding set
- id: 4
  title: Admit one current final run-grade plan-audit report
  intent: It resolves exactly one plan and explicit final report, verifies the
    selected report's canonical-plan and run-grade detail-bundle binding at
    envelope construction, and otherwise returns `insufficient-evidence`. It
    does not infer a report, read report history, or claim that live code,
    project configuration, or source material remains current.
  files:
  - plan_tool/review.py
  - plan_tool/review_persistence.py
  - tests/test_review.py
  - tests/test_review_persistence.py
  creates:
  - plan_tool/convergence_eval_plan_audit.py
  - tests/test_convergence_eval_plan_audit.py
  complexity: high
  change_type: feature
  depends_on:
  - 2
  depends_on_notes:
    2: the admitted envelope and refusal vocabulary determine the adapter's
      validation boundary
- id: 5
  title: Run one isolated non-persistent plan-audit judge
  intent: It sends only the admitted in-memory envelope to one fixed, read-only
    Codex invocation, makes no retry or fallback call, validates the reply, and
    leaves no evaluator log, telemetry event, cache, or repository artifact.
    The prompt requires the shared closed response schema rather than a
    model-authored command or scope instruction.
  files:
  - CODEX_CLI_CONTRACT.md
  - TESTING.md
  creates:
  - benchmarks/corpus/convergence-eval/trials.md
  - plan_tool/convergence_eval_run.py
  - plan_tool/prompts/convergence-eval.md
  - tests/test_convergence_eval_run.py
  complexity: high
  change_type: feature
  depends_on:
  - 3
  - 4
  depends_on_notes:
    3: the reply gate determines accepted output
    4: the adapter supplies the only permitted judge input
- id: 6
  title: Replace public mechanical convergence with the evaluator
  intent: It exposes `convergence-eval NAME --context plan-audit --audit-report
    REVIEW_ID`, refuses zero or multiple canonical-plan matches before reading
    a report, preserves its zero, two, and one exit-status policy, and sweeps
    command ordering, help/reference, continuation guidance, and their tests
    before superseding the unimplemented arm-clustering route and removing the
    old mechanical command surface.
  files:
  - CAPABILITIES.md
  - docs/cli/README.md
  - docs/cli/convergence.md
  - docs/implementation-plans/2-arm-clustering-cross-round-consensus.md
  - docs/implementation-plans/plan-details/arm-clustering-cross-round-consensus/01-build-arm-clustering-consensus-targets.md
  - docs/implementation-plans/plan-details/arm-clustering-cross-round-consensus/02-cross-round-arm-clustering-advisory.md
  - docs/implementation-plans/plan-details/arm-clustering-cross-round-consensus/03-parse-plan-once-cmd-convergence-instead.md
  - docs/implementation-plans/plan-details/arm-clustering-cross-round-consensus/04-pass-committed-step-ids-diagnosis.md
  - docs/implementation-plans/plan-details/arm-clustering-cross-round-consensus/05-update-docs-cross-round-advisory-settle.md
  - plan_tool/cli/__init__.py
  - plan_tool/cli/app.py
  - plan_tool/cli/completeness_cmd.py
  - plan_tool/cli/context.py
  - plan_tool/cli/convergence_cmd.py
  - plan_tool/cli/parser.py
  - plan_tool/cli/split_criteria_cmd.py
  - plan_tool/locator.py
  - tests/cli/package_surface_help.golden.txt
  - tests/cli/test_cli_reference.py
  - tests/cli/test_completeness_cmd.py
  - tests/cli/test_context_helpers.py
  - tests/cli/test_convergence_cmd.py
  - tests/cli/test_package_surface.py
  - tests/cli/test_telemetry_cmd.py
  - tests/test_locator.py
  - tests/test_split_criteria.py
  creates:
  - docs/cli/convergence-eval.md
  complexity: high
  change_type: feature
  depends_on:
  - 5
  depends_on_notes:
    5: the complete isolated evaluator entry point owns command execution
- id: 7
  title: Retire the unused mechanical convergence telemetry writer
  intent: It removes the old command's dead durable-verdict writer while
    preserving compatibility for existing telemetry readers. The evaluator
    introduces no replacement telemetry record.
  files:
  - plan_tool/telemetry.py
  - tests/test_telemetry.py
  complexity: medium
  change_type: refactor
  depends_on:
  - 6
  depends_on_notes:
    6: removal of the only live mechanical convergence caller exposes the
      retained compatibility boundary
- id: 8
  title: Document the bounded evaluator and publish future handoffs
  intent: It makes explicit report selection, report-to-artifact binding,
    advisory limits, current application authority, and separately selectable
    follow-up work discoverable from the owning docs.
  files:
  - AI_SDLC_POLICY.md
  - BACKLOG.md
  - CLAUDE.md
  - CONTRIBUTING.md
  - DATA_CONTRACT.md
  - LESSONS_LEARNED.md
  - README.md
  - RUNBOOK.md
  - TESTING.md
  - USE_CASES.md
  - docs/ARCHITECTURE.md
  - docs/AUDIT_FLOW.md
  - docs/GLOSSARY.md
  - docs/ITERATION.md
  - docs/NONDETERMINISM_PLAN_DESIGN.md
  - docs/PROCESS_CONTRACTS.md
  - docs/TRACKING.md
  - docs/WORKFLOWS.md
  - docs/implementation-plans/backlog-arcs/backlog-arc-convergence-evidence.md
  - handoffs/2026-09-14-developer-docs-and-tracking.md
  - integrations/claude/SKILL.md
  - integrations/codex/SKILL.md
  - integrations/shared/DIRECTIVES.md
  - plan-seeds/convergence-handoff-guide.md
  complexity: high
  change_type: non-code
  depends_on:
  - 6
  - 7
  depends_on_notes:
    6: the landed public command defines user-facing behavior
    7: the retained legacy-reader boundary defines telemetry documentation
---
# Run-Grade Plan-Audit Convergence Eval

> **Superseded; do not execute.** Withdrawn 2026-09-15 (owner-confirmed): the
> convergence judgment stays in the orchestrating session (the Codex or
> Claude Code chat driving `plan-tool` and reviewing progress), not in a
> command. After the v1 narrowing, the evaluator's eligibility gate already
> fixes the outcome whenever only one is eligible, so the model decides at
> most `converged` vs `continue` on a qualified low-yield report with
> remaining material findings — a choice the driving session can make with
> more evidence than the evaluator's envelope permits (history, live code,
> the source seed), without stacking a second judge on top of the audit.
> 25 bare-plan audits (2026-09-14/15) never converged: the scope moved
> under the audit four times (four evidence contexts to one, 13 steps to 8,
> persistent run logs to none), and each reshape brought new surface rather
> than the same gap recurring. `.tmp/2026-09-15-convergence-eval-experiment-handoff.md`
> (untracked) has the full analysis. `BACKLOG.md` #367 and #369 continue as
> the direct `completeness-apply`/`apply_finding` authority migration this
> decision also motivated, decoupled from this evaluator's evidence gate.
> #368 and #370–#375 (evaluator adapters and governance) are retired as
> moot. Do not revive this evaluator; `plan-tool convergence` and
> `list --status` remain the supported read-only convergence surfaces.

## Overview

Add one non-mutating `plan-tool convergence-eval` command for one explicitly
selected, final, current run-grade plan-audit report. It replaces the public
mechanical `plan-tool convergence` verdict with a bounded advisory outlook. It
does not apply findings, alter plan scope, advance a pipeline, or create an
evaluator-owned record.

The first release supports exactly `--context plan-audit`. It evaluates the
selected report and its current canonical plan/detail artifacts; it does not
claim currentness for live code, project configuration, source material, or a
historical audit trajectory.

## Steps

The machine-readable step list is in the `steps:` frontmatter block.

## Problem statement

The existing mechanical convergence command can summarize saved audit history,
but it cannot provide a developer-owned, evidence-bound next outlook for an
explicit current report. A broad evaluator that tries to add code-state
admission, profile selection, source provenance, durable run records,
historical trajectory, and scope-redesign authority at once does not have a
bounded first implementation contract.

This plan limits v1 to evidence the selected report and current plan/detail
artifacts can establish deterministically. That yields a useful review handoff
now while leaving separately designed authority and evidence models to named
future work.

## Architecture

`plan-tool convergence-eval NAME --context plan-audit --audit-report REVIEW_ID`
is the complete public invocation. `--context` must equal `plan-audit`; no
detail-grade selector exists because this release accepts run-grade evidence
only. `NAME` resolves to exactly one canonical plan before the command reads an
audit report. Zero or multiple matches are usage errors at exit two; the
resolver never chooses the first, newest, or an inferred plan.

`REVIEW_ID` selects exactly one root-contained, final saved run-grade audit
report belonging to that canonical plan. The adapter rejects missing, escaped,
ambiguous, malformed, non-final, or other-grade evidence with the deterministic
`insufficient-evidence` refusal. It reads no preceding report and forms no
trajectory.

The adapter constructs one in-memory envelope after verifying that the selected
report's recorded canonical-plan digest and run-grade detail-bundle revision
match the canonical plan and bundle at envelope construction. A missing or
mismatched binding refuses. This is artifact currentness only: the command does
not re-admit live code, a project profile, a source seed, or any other external
subject. The envelope contains only the selected report identity and digest,
the canonical plan identity and digest, run-grade bundle state and revision,
the report qualification, and the report's final current findings. It never
writes an envelope to the repository.

A current material finding has a complete stable finding identity in the
selected final report and critical, high, or medium severity. The final report
state, not an earlier action annotation, determines whether a finding is open.
Missing identity, severity, final-state, qualification, plan binding, or bundle
facts refuse rather than being inferred.

The allowed outlooks are `converged` and `continue`; `insufficient-evidence`
and `invalid-evaluation` are refusals, not outlooks. `converged` is eligible
only when the selected report meets the existing qualified clean-or-low-yield
allowance. `continue` is eligible only when the selected report has one or more
current material findings. If neither condition holds, the command refuses.
Both outcomes can be eligible for a qualified low-yield report with remaining
material findings, leaving the judge to explain the bounded developer handoff.
Neither outcome decides scope, labels a premise false, requests a redesign, or
changes application authority.

The response gate accepts exactly one eligible outcome and a set-equal
`finding_coverage` row for every current material finding, with an
envelope-resolved citation in every row. Its sole permitted `next_action` is
`{"kind":"review-selected-report","finding_ids":[...]}`, where
`finding_ids` is set-equal to the envelope's current material finding IDs and
has no model-authored free-text field. The renderer, not the model, explains
that the developer reviews the selected report and hand-triages those IDs. The
gate rejects a missing, extra, duplicate, or uncited material finding; unknown
outcome; missing or noncanonical action; or any action that requests a scope
change, invokes an application command, or states a new evidence fact.

For an admitted envelope, the runner makes one fixed isolated Codex request
using `gpt-5.6-terra`. The child receives only the rendered envelope and prompt;
it has no plan-root or repository input. The runner makes no retry, fallback,
or model override. It validates the reply before rendering it to stdout. The
command creates no run log, telemetry event, cache, report sidecar, or other
repository artifact. Parser and selector errors exit two; deterministic
refusals and accepted advisory outcomes exit zero; transport, process, or other
operational failures exit one.

The existing `ConvergenceDiagnosis` command and its unimplemented
arm-clustering extension are superseded together. Existing saved reports and
telemetry remain readable, but the first evaluator release does not use their
history or create a replacement writer. Retirement updates the canonical
command order, CLI reference, capability inventory, Jira-grade sidecar warning,
and split-criteria's sibling-command reference, plus their focused tests; it
does not alter generic convergence-loop terminology or legacy report readers.

## Scope guardrails

- The evaluator remains advisory and ephemeral. It never applies a finding,
  changes a plan, writes a decision, advances a stage, or changes another
  command's exit policy.
- The canonical-plan name and report id are mandatory and exact. The command
  fails closed rather than inferring either selector.
- Run-grade final-report evidence and its current plan/detail binding are the
  whole v1 subject. No live code, project configuration, source input, or
  historical comparison can enlarge that subject.
- `next_action` is the fixed, envelope-bound `review-selected-report` object;
  the model cannot author a command, scope request, or free-text instruction.
- The response gate can reject an unsafe or malformed judge reply, but it does
  not make the model a policy or scope authority.
- Current completeness application and direct-pipeline behavior stay unchanged.

## Out of scope

- A Jira-grade evaluator, a grade-neutral report reader, or report conversion.
- Historical trajectories, recurrence classifications, a finish-current-fix
  state, or a redesign-or-rescope state.
- Audit-produced premise or scope evidence, report-schema changes, and any
  evaluator-directed scope decision.
- Live-code, project-profile, source-seed, or other external-subject admission.
- Evaluator run logs, telemetry, cache, persistent outlooks, remote integration,
  or CI authority.
- A free-text or multi-form action recommendation.
- Code-reconcile, local-review, and pull-request-review evaluator adapters.
- Retiring `completeness-apply`, `direct-run`, `direct-jira`, or other
  `apply_finding` callers.

## Risks

- **Medium — A stale report sounds current.** Mitigate it with exact final
  report selection and a matching canonical-plan and run-grade-bundle binding
  before any model call. The remaining gap is that the binding establishes
  artifact currentness only, not live-subject currentness.
- **Medium — A model answer omits a material gap.** Mitigate it with set-equal
  coverage and envelope-resolved citations for every current material finding.
  The remaining gap is bounded to citations and report facts the envelope can
  resolve.
- **High — A clean-looking unqualified report becomes a convergence claim.**
  Mitigate it by permitting `converged` only under the existing qualified
  clean-or-low-yield allowance. No unresolved gap remains within v1's subject.
- **Medium — The evaluator accumulates a second unowned evidence store.**
  Mitigate it by keeping every v1 artifact in memory and creating no log,
  cache, telemetry event, or sidecar. No unresolved gap remains within v1.
- **Medium — The bounded slice silently defers necessary work.** Mitigate it by
  recording each excluded concern with an independently selectable,
  evidence-gated backlog item. The remaining gap is intentionally deferred
  pending the evidence those items require.

## Testing

Default to unmarked unit/component tests that isolate one function or class,
use `tmp_path` for repository state, and inject a fake judge invoker. Keep the
following coverage in the named suites:

- `tests/test_convergence_eval_corpus.py::TestConvergenceEvalCorpus` verifies
  accepted `converged` and `continue` cases, qualified low-yield overlap, and
  `test_safety_predicate_rejects_unqualified_converged`.
- `tests/test_convergence_eval.py::TestConvergenceEvalEnvelope` verifies
  normalization, material-finding identity selection, outcome eligibility,
  and deterministic refusals for incomplete evidence.
- `tests/test_convergence_eval_response.py::TestConvergenceEvalResponse`
  verifies `test_rejects_non_set_equal_finding_coverage`, unresolved citations,
  unknown outcomes, and
  `test_rejects_noncanonical_or_authority_crossing_next_action`.
- `tests/test_convergence_eval_plan_audit.py::TestPlanAuditAdmission` verifies
  `test_rejects_report_before_judge_request` for missing, ambiguous, escaped,
  malformed, non-final, wrong-grade, plan-binding, and bundle-binding evidence.
- `tests/test_convergence_eval_run.py::TestConvergenceEvalRunner` verifies one
  isolated invocation, no retry or fallback, operational failure handling, and
  no evaluator-owned repository artifact.
- `tests/test_review.py::TestConvergenceEvalPlanResolution`,
  `tests/test_review_persistence.py::TestConvergenceEvalReportBinding`,
  `tests/test_locator.py::TestConvergenceEvalLocator`, and
  `tests/test_telemetry.py::TestConvergenceEvalLegacyCompatibility` verify
  canonical-plan resolution, report binding, exact locator behavior, and
  legacy telemetry-reader compatibility.
- `tests/cli/test_telemetry_cmd.py::test_telemetry_registered_and_ordered`,
  `tests/cli/test_completeness_cmd.py::TestGradeJiraReportSurfaces`, and
  `tests/test_split_criteria.py` verify the retirement sweep's command order,
  sidecar guidance, and sibling-command reference.

Mark `tests/cli/test_convergence_cmd.py::TestConvergenceEvalCommand` with
`@pytest.mark.integration` because it drives `main()` through selector
validation, the admitted evaluator, and exit-status rendering. Keep
`tests/cli/test_cli_reference.py::TestConvergenceEvalReference`,
`tests/cli/test_context_helpers.py::TestConvergenceEvalContext`, and
`tests/cli/test_package_surface.py::TestConvergenceEvalPackageSurface`
unmarked unless they cross that command boundary; they verify help, context,
and package-surface wiring in isolation.

Run `uv run pytest -m "not integration" tests/ -q` during implementation,
`uv run pytest -m integration tests/ -q` when changing the evaluator, adapter,
or CLI boundary, and `uv run pytest tests/ -q -n auto` before completion. The
corpus checks and the full suite must be green.

## Acceptance criteria

- `convergence-eval` requires one exact plan, `--context plan-audit`, and one
  exact final run-grade report id; it never infers a selector.
- It refuses missing, ambiguous, escaped, malformed, non-final, wrong-grade, or
  artifact-mismatched report evidence before a judge request.
- It accepts only `converged` or `continue` when the selected envelope makes
  that result eligible, and every accepted answer maps every current material
  finding to an envelope-resolved citation and the sole set-equal
  `review-selected-report` action object.
- An accepted `converged` always satisfies the existing qualified
  clean-or-low-yield allowance.
- A run creates no evaluator-owned repository artifact, and the single isolated
  judge request has no retry or fallback path.
- Public command, docs, help, command ordering, continuation guidance, and
  focused tests no longer retain the mechanical convergence command; saved
  legacy reports and telemetry remain readable.
- Application/direct pipelines retain their current behavior and authority.
- Focused tests, corpus checks, and the full suite are green.

## Deferred

- BACKLOG #367 owns an evidence-gated decision on `completeness-apply` and
  direct-pipeline migration after v1 has developer-use evidence.
- BACKLOG #368 owns evaluator governance after representative developer-use
  evidence; v1 remains ephemeral and advisory.
- BACKLOG #369 owns the separate inventory of other `apply_finding` authorities.
- BACKLOG #370, #371, and #372 own code-reconcile, local-review, and
  pull-request-review adapters respectively.
- BACKLOG #373 owns any later live-subject admission model for code,
  configuration, source, or invocation-observation evidence.
- BACKLOG #374 owns evidence-bound historical or redesign-oriented outcomes,
  including any audit-report schema change they require.
- BACKLOG #375 owns any later Jira-grade evaluator decision and reader contract.

## References

- `docs/AUDIT_FLOW.md` — qualified-result and clean-or-low-yield contract.
- `plan-seeds/convergence-eval-plan-audit-v1.md` — source scope contract.
- `docs/implementation-plans/backlog-arcs/backlog-arc-convergence-evidence.md`
  — evidence order and deferred pickup boundaries.
- `handoffs/2026-09-14-developer-docs-and-tracking.md` — dated convergence
  evidence and the owner-confirmed v1 reset.
