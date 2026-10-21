> **Replaced**: this file has been superseded by `docs/implementation-plans/2-trace-high-impact-contract.md`.
> Preserved here for history; do not edit.

## Overview

Establish whether a parsed `Recommendation` can be both non-blocking under the current severity rule and `impact=high`, then use that evidence to define a valid future #152 augment scenario. This is a read/trace-and-re-scope decision: it must not implement the #152 predicate or alter production behavior. The resulting evidence must accurately update #157, #152, and their dependency wording while leaving #152 blocked until a valid implementation scope is established.

## Problem statement

#152 uses a `medium`-severity, `impact=high` finding as the example newly promoted by its proposed augment predicate. At HEAD, `is_blocking` already blocks `medium`, and the parser maps Claude `LOW` to `medium`, so that example does not demonstrate added behavior. The plan must trace severity normalization, `Recommendation` construction, and continuation-gate input paths to determine whether a non-blocking `impact=high` recommendation can reach a #152 continuation site.

## Architecture

Trace `Recommendation`, `_CLAUDE_SEVERITY_MAP`, triage-tag parsing, and audit/reconcile construction paths in `plan_tool/review.py` to enumerate parsed recommendation shapes with `impact=high` and their normalized severities. Then trace `is_blocking`, `ConvergenceState`, and `should_continue` in `plan_tool/convergence.py`, along with the seven #152 continuation/materiality sites in `plan_tool/cli/completeness_cmd.py`, `plan_tool/cli/reconcile.py`, and `plan_tool/review.py`, to determine which collections each site observes.

Use the resulting evidence and a minimal deterministic fixture/test strategy to re-scope #152 and its archived/replacement seed as appropriate. If no reachable non-blocking, high-impact shape exists, state that the augment has no observable behavior today and treat any needed impact emission or plumbing as separate future work.

## Risks

- A `medium`-severity, `impact=high` example may already be blocking, so it cannot prove an augment effect; severity: high; mitigation: trace normalized severity before selecting a scenario; unresolved gap: a valid non-blocking shape may not exist.
- Continuation sites may inspect different recommendation collections, so a candidate can be reachable at some sites but not others; severity: high; mitigation: trace each named #152 site and prove the result with deterministic fixtures/tests.
- New impact emission or plumbing could expand #152 beyond its evidence; severity: high; mitigation: stop and create a separate backlog entry rather than implicitly expanding #152.
- Updating #157 or #152 as though implementation shipped would misstate status; severity: medium; mitigation: record plan-authored evidence and retain #152 as blocked until implementation scope is established.

## Testing

Use existing tests/fixtures that construct recommendations and exercise completeness, reconcile, and review convergence paths. Add or use minimal deterministic fixtures/tests that demonstrate whether the selected non-blocking, `impact=high` input reaches each claimed continuation gate, without adding production behavior. The verification must prove either the reachable scenario or that no observable augment exists today.

## Acceptance criteria

- The plan identifies the exact normalized severity values, distinguishes them from prompt labels, and identifies every currently reachable non-blocking shape that can carry `impact=high`, or records grounded evidence that none exists.
- The plan identifies which #152 continuation sites can observe each candidate rather than assuming every site receives the same recommendation list.
- The verification uses existing test homes/fixtures and proves the selected result without adding production behavior.
- #152’s future implementation scope is corrected only from the evidence found; no predicate/call-site change, prompt/schema change, or new plumbing is added.
- `BACKLOG.md` records #157 as plan-authored while execution remains pending and retains #152 as blocked until #157’s evidence is implemented/reconciled.
