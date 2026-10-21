> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Trace High Impact Contract
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Add tests that show which high-impact findings are non-blocking
  files:
  - tests/test_convergence.py
  - tests/test_review.py
  complexity: low
  change_type: non-code
  detail: docs/implementation-plans/plan-details/trace-high-impact-contract/01-tests-that-show-which-high-impact.md
  status: done
- id: 2
  title: Trace high-impact findings through the live continuation paths
  files:
  - tests/cli/test_completeness_cmd.py
  - tests/test_cli.py
  - tests/test_review.py
  complexity: medium
  change_type: non-code
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/trace-high-impact-contract/02-trace-high-impact-findings-through-live.md
  status: done
- id: 3
  title: 'Replace the stalled #152 plan with the evidence-based scope'
  files:
  - docs/implementation-plans/2-gate-convergence-by-impact.md
  - docs/implementation-plans/plan-details/gate-convergence-by-impact/01-impact-aware-blocking-rule.md
  - docs/implementation-plans/plan-details/gate-convergence-by-impact/02-use-impact-aware-rule-convergence-loops.md
  - docs/implementation-plans/plan-details/gate-convergence-by-impact/03-document-shipped-impact-aware-augment.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 1
  - 2
  detail: docs/implementation-plans/plan-details/trace-high-impact-contract/03-replace-stalled-152-plan-evidence-based.md
  status: done
- id: 4
  title: 'Record #157 evidence and keep #152 blocked'
  files:
  - BACKLOG.md
  complexity: low
  change_type: non-code
  depends_on:
  - 3
  detail: docs/implementation-plans/plan-details/trace-high-impact-contract/04-record-157-evidence-keep-152-blocked.md
  status: done
---
# Trace High Impact Contract

## Overview

Determine whether a parsed `Recommendation` can be non-blocking under the current severity rule while carrying `impact=high`, then use the evidence to define a valid future #152 augment scenario. This is a read/trace-and-re-scope decision only: it must not implement the #152 predicate or change production behavior. Update #157, #152, and their dependency wording accurately while keeping #152 blocked until a valid implementation scope is established.

## Problem statement

#152 uses a `medium`-severity, `impact=high` finding as the example newly promoted by its proposed augment predicate. At HEAD, `is_blocking` already blocks `medium`, and the parser maps Claude `LOW` to `medium`, so that example does not demonstrate added behavior. The plan must trace severity normalization, `Recommendation` construction, and continuation-gate input paths to determine whether a non-blocking `impact=high` recommendation can reach a #152 continuation site.

## Architecture

Trace `Recommendation`, `_CLAUDE_SEVERITY_MAP`, triage-tag parsing, and audit/reconcile construction paths in `plan_tool/review.py` to enumerate parsed recommendation shapes with `impact=high` and their normalized severities. Then trace `is_blocking`, `ConvergenceState`, and `should_continue` in `plan_tool/convergence.py`, along with the seven #152 continuation/materiality sites in `plan_tool/cli/completeness_cmd.py`, `plan_tool/cli/reconcile.py`, and `plan_tool/review.py`, to determine which collections each site observes.

Use the resulting evidence and a minimal deterministic fixture/test strategy to re-scope #152 and its archived/replacement seed as appropriate. If no reachable non-blocking, high-impact shape exists, state that the augment has no observable behavior today and treat any needed impact emission or plumbing as separate future work.

## Input

The plan consumes the existing `Recommendation` contract and its normalized severity and `impact` values as constructed in `plan_tool/review.py`, including `_CLAUDE_SEVERITY_MAP`, triage-tag parsing, and audit/reconcile paths. It also relies on the recommendation collections consumed by `is_blocking`, `ConvergenceState`, and `should_continue` in `plan_tool/convergence.py` and the named continuation/materiality sites. Verification is limited to deterministic fixtures/tests and must establish reachability without changing the contract or production behavior.

## References

- [Claude Code CLI reference](https://docs.anthropic.com/en/docs/claude-code/cli-usage) — Documents Claude Code print-mode JSON and stream-JSON output flags that define the external response format the parser consumes.
- [Python dataclasses documentation](https://docs.python.org/3/library/dataclasses.html) — Covers dataclass field construction and defaults relevant to tracing and safely fixture-building Recommendation instances.
- [Python unittest documentation](https://docs.python.org/3/library/unittest.html) — Defines the standard-library test and fixture mechanisms useful for deterministic continuation-gate coverage.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Implementing the #152 predicate or altering production behavior — this is a read/trace-and-re-scope decision.
- Adding a predicate/call-site change, prompt/schema change, or new plumbing — those changes require a separately established implementation scope.
- Treating #152 as unblocked before #157’s evidence is implemented and reconciled — the backlog status must remain accurate.

## Risks

- A `medium`-severity, `impact=high` example may already be blocking, so it cannot prove an augment effect; severity: high; mitigation: trace normalized severity before selecting a scenario; unresolved gap: a valid non-blocking shape may not exist.
- Continuation sites may inspect different recommendation collections, so a candidate can be reachable at some sites but not others; severity: high; mitigation: trace each named #152 site and prove the result with deterministic fixtures/tests.
- New impact emission or plumbing could expand #152 beyond its evidence; severity: high; mitigation: stop and create a separate backlog entry rather than implicitly expanding #152.
- Updating #157 or #152 as though implementation shipped would misstate status; severity: medium; mitigation: record plan-authored evidence and retain #152 as blocked until implementation scope is established.

## Testing

Use existing tests/fixtures that construct recommendations and exercise completeness, reconcile, and review convergence paths. Add or use minimal deterministic fixtures/tests that demonstrate whether the selected non-blocking, `impact=high` input reaches each claimed continuation gate, without adding production behavior. The verification must prove either the reachable scenario or that no observable augment exists today.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (non-code) — verification appropriate to the artifacts; no test-ordering directive.
- step 2 (non-code) — verification appropriate to the artifacts; no test-ordering directive.
- step 3 (non-code) — verification appropriate to the artifacts; no test-ordering directive.
- step 4 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- The plan identifies the exact normalized severity values, distinguishes them from prompt labels, and identifies every currently reachable non-blocking shape that can carry `impact=high`, or records grounded evidence that none exists.
- The plan identifies which #152 continuation sites can observe each candidate rather than assuming every site receives the same recommendation list.
- The verification uses existing test homes/fixtures and proves the selected result without adding production behavior.
- #152’s future implementation scope is corrected only from the evidence found; no predicate/call-site change, prompt/schema change, or new plumbing is added.
- `BACKLOG.md` records #157 as plan-authored while execution remains pending and retains #152 as blocked until #157’s evidence is implemented/reconciled.

## Deferred

- Any needed impact emission or plumbing — separate future work if no reachable non-blocking, high-impact shape exists today.
