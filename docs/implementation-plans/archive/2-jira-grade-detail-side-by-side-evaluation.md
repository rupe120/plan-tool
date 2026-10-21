---
title: Jira Grade Detail Side By Side Evaluation
status: planning
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Share detail artifact paths while keeping legacy run details
  files:
  - plan_tool/detail.py
  - plan_tool/fingerprint.py
  - plan_tool/review.py
  - plan_tool/scope_out.py
  - tests/test_detail.py
  - tests/test_fingerprint.py
  - tests/test_review.py
  - tests/test_scope_out.py
  creates:
  - plan_tool/detail_artifacts.py
  - tests/test_detail_artifacts.py
  complexity: high
  change_type: refactor
  detail: docs/implementation-plans/plan-details/jira-grade-detail-side-by-side-evaluation/01-share-detail-artifact-paths-while.md
  status: current
- id: 2
  title: Add jira-grade detail authoring with separate files
  files:
  - DETAIL_FORMAT.md
  - docs/DETAIL_FLOW.md
  - docs/cli/README.md
  - docs/cli/detail.md
  - plan_tool/cli/authoring.py
  - plan_tool/detail.py
  - tests/cli/test_authoring_cmds.py
  - tests/cli/test_cli_reference.py
  - tests/test_detail.py
  creates:
  - plan_tool/prompts/detail-jira.md
  complexity: high
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/jira-grade-detail-side-by-side-evaluation/02-jira-grade-detail-authoring-separate.md
- id: 3
  title: Let jira read jira-grade details
  files:
  - JIRA_FORMAT.md
  - docs/cli/README.md
  - docs/cli/jira.md
  - plan_tool/cli/jira_cmd.py
  - plan_tool/jira.py
  - tests/cli/test_cli_reference.py
  - tests/cli/test_jira_cmds.py
  - tests/test_jira.py
  creates:
  - plan_tool/prompts/jira-jira.md
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  detail: docs/implementation-plans/plan-details/jira-grade-detail-side-by-side-evaluation/03-let-jira-read-jira-grade-details.md
- id: 4
  title: Let run use jira-grade details when requested
  files:
  - docs/cli/README.md
  - docs/cli/run.md
  - plan_tool/cli/run_cmd.py
  - plan_tool/launcher.py
  - plan_tool/renderer.py
  - tests/cli/test_cli_reference.py
  - tests/cli/test_run_cmd.py
  - tests/test_launcher.py
  - tests/test_renderer.py
  creates:
  - plan_tool/prompts/run-jira.md
  complexity: high
  change_type: feature
  depends_on:
  - 2
  detail: docs/implementation-plans/plan-details/jira-grade-detail-side-by-side-evaluation/04-let-run-use-jira-grade-details-when.md
- id: 5
  title: Add a paired detail evaluation helper
  files:
  - docs/PROMPT_AB_TESTING.md
  creates:
  - docs/JIRA_GRADE_EVALUATION.md
  - plan_tool/detail_evaluation.py
  - tests/fixtures/detail_evaluation/paired-trial.json
  - tests/test_detail_evaluation.py
  complexity: high
  change_type: feature
  depends_on:
  - 3
  - 4
  detail: docs/implementation-plans/plan-details/jira-grade-detail-side-by-side-evaluation/05-paired-detail-evaluation-helper.md
- id: 6
  title: Run the paired evaluation and record the result
  files:
  - BACKLOG.md
  creates:
  - docs/JIRA_GRADE_EVALUATION_RECORD.json
  - docs/JIRA_GRADE_EVALUATION_REPORT.md
  complexity: high
  change_type: non-code
  depends_on:
  - 5
  detail: docs/implementation-plans/plan-details/jira-grade-detail-side-by-side-evaluation/06-run-paired-evaluation-record-result.md
---
# Jira Grade Detail Side By Side Evaluation

## Overview

Add an explicit jira-grade detail mode beside the existing run-grade path so the same plan can retain comparable detail bundles for `jira` and an opt-in `run` path. Run-grade remains the default, legacy bundles remain run-grade, and both contracts must be selected without ambiguity. Record a small, reproducible paired evaluation so a later plan can decide whether jira-grade should become the default.

## Problem statement

Today `detail` creates implementation-grade prose for `run`, while `jira` down-converts it into a story. Run-grade detail commits to volatile facts such as precise edits, named call sites, test rosters, and prescribed mechanics; after scope changes, those commitments can become stale and cause audit churn even when the design is still correct. Jira-grade detail may reduce that contradiction surface, but changing the default without a matched control would leave its effect on execution quality, retries, and diff scope adherence unknown.

## Architecture

Keep the existing run-grade detail format, parser, artifact selection, and `run` renderer as the control. Add a compact jira-grade contract with `Intent`/problem, `Change`, `Constraints`, `Done when`, and `Out of scope`, aligned with or sequenced after BACKLOG #149's compact schema; it should describe outcomes and boundaries rather than prescribe edits, tests, or algorithms unless a declared constraint requires them.

Add explicit depth selection and separate, collision-safe artifact routing so run-grade and jira-grade bundles can coexist for one plan. Legacy bundles are always read as run-grade and must never be silently rewritten or reinterpreted. `jira` consumes jira-grade detail directly, while an opt-in jira-grade `run` renderer receives the same schema plus normal plan/repository grounding and leaves implementation choices to the executor.

Provide a repeatable paired-evaluation harness or documented command sequence using the same baseline, plan steps, repository revision, and verification command for both depths. Predeclare the adoption threshold before measurement; only a later plan may invert the default if the report shows jira-grade is no worse on the Boolean per-run first-pass verification outcome and scope adherence/diff quality, does not materially regress retries, elapsed time, or available cost telemetry, and reduces scope-change audit churn.

## Input

This plan consumes the existing run-grade detail format, parser, artifact selection, and `run` renderer as its unchanged control, with legacy bundles interpreted as run-grade. It also depends on BACKLOG #164's scope/lifecycle contract, BACKLOG #149's compact-schema alignment, `CLAUDE.md` manual-convergence policy, and saved `completeness-audit` reports; the paired report must record the plan, steps, repository revision, backend/model settings, commands, timestamps, raw artifact/report locations, and outcomes.

## References

- [Pydantic Configuration](https://pydantic.dev/docs/validation/latest/api/pydantic/config/) — Defines strict model configuration such as rejecting unknown fields, needed for unambiguous jira- and run-grade artifact validation.
- [Pydantic Validators](https://pydantic.dev/docs/validation/latest/concepts/validators/) — Covers field and model validators for enforcing cross-field detail-contract and selection invariants.
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — Documents safe YAML loading and dumping behavior relevant to preserving and parsing legacy detail bundles.
- [pytest API Reference](https://docs.pytest.org/en/stable/reference/reference.html) — Provides fixture, parametrization, and temporary-directory APIs for contract, routing, and paired-evaluation tests.
- [Git rev-parse Documentation](https://git-scm.com/docs/git-rev-parse) — Specifies reliable repository-revision resolution for recording reproducible paired-evaluation provenance.
- [pathlib — Object-oriented filesystem paths](https://docs.python.org/3/library/pathlib.html) — Documents Python path operations useful for collision-safe artifact routing and isolated bundle storage.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Making jira-grade detail the default for `detail`, `run`, or `jira`; default inversion requires a later evidence-backed plan.
- Re-authoring or bulk-rewriting existing run-grade bundles; legacy compatibility is preserved instead.
- Changing plan-body schema, step decomposition, `change_type`, or completeness audit logic; this experiment is limited to detail contracts and consumers.
- Weakening audit checks to make the experiment appear more successful; evidence must remain comparable.
- A corpus-wide benchmark or broad model comparison; this is a focused decision experiment with recorded provenance.

## Risks

- **Run quality regression:** thinner detail may cause more rediscovery, retries, or incorrect diffs. Severity: high. Mitigation: unchanged run-grade control, paired inputs, a predeclared gate, and no default flip here.
- **Artifact ambiguity:** mixed-depth files could cause a run to consume the wrong contract. Severity: high. Mitigation: explicit mode/depth selection, isolated storage or unambiguous metadata, and tests that reject ambiguous selection.
- **Metric noise:** backend nondeterminism can swamp one-off outcomes. Severity: medium. Mitigation: record every setting and raw result, compare matched runs, and mark thin evidence indeterminate rather than extrapolating.
- **Schema duplication with #149:** two compact contracts could drift. Severity: medium. Mitigation: sequence #149 first or define one shared token/alias layer; do not create competing required-section authorities.

## Testing

Test both contracts, legacy run-grade read compatibility, explicit artifact selection, ambiguous or mislabeled selection failures, and prompt routing while confirming no default changed. Add fixture coverage for paired-run provenance and metric calculations.

Run the paired evaluation against at least one real plan with nontrivial implementation work and a deliberately scoped change. Record matched baseline inputs, repository revision, backend/model settings, commands, timestamps, first-pass result, retries, elapsed time, available cost/tool-use telemetry, verification outcome, human-reviewed scope-adherence/diff-quality verdict, controlled scope-change replay, and `completeness-audit` findings.

After the detail bundle exists, follow `CLAUDE.md` manual-convergence policy: run `completeness-audit` with `--iterate`, save and review reports, apply in-scope conceptual corrections with judgment, and re-audit without auto-driving `completeness-apply`. Capture baseline, post-correction, and third audit snapshots; compare stable finding identities and material severities, and stop patching when high-impact findings recur, material findings stay flat, or an architecture contradiction emerges.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (refactor) — characterization tests pinned before the change; pass unchanged after.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (feature) — unit tests added with the implementation; green before completion.
- step 5 (feature) — unit tests added with the implementation; green before completion.
- step 6 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- Run-grade detail remains the default, and legacy run-grade bundles remain readable and executable without a rewrite.
- An explicit jira-grade mode produces and selects artifacts independently from run-grade for the same plan; ambiguous or mislabeled selection fails clearly.
- Jira-grade detail validates a compact schema focused on intent, change, constraints, acceptance, and exclusions, aligned with #149 where applicable.
- `jira` consumes jira-grade detail directly, and an opt-in `run` path renders from it while the existing run-grade renderer remains available as the control.
- Tests cover both contracts, legacy read compatibility, artifact selection, prompt routing, and that no default changed.
- A durable structured paired-evaluation record and derived report preserve the matched baseline, commands, raw outcomes, specified execution metrics, controlled scope-change audit result, and recommendation against a threshold declared before measurement.
- No default inversion ships from this plan; a later plan may propose one only when the report passes its declared gate.
- The final documentation/status step reconciles BACKLOG #164 without removing it merely because this plan was authored; out-of-scope audit findings are routed to `BACKLOG.md` or `BUG_BACKLOG.md`.

## Deferred

- Default inversion and any migration or re-authoring policy for the existing corpus; require passing evidence and a separate plan.
- An escape hatch for individual jira-grade steps that need mechanically prescriptive supplemental detail; determine this from experiment failures rather than expanding the base schema preemptively.
- Wider benchmark automation and repeated-sample statistical confidence beyond the focused paired experiment.
