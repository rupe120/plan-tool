# Cleanup for focus and stability

BACKLOG #376 is shipped. The next pickup is the separately tracked reporting
and citation defects; the backlog remains the queue and scope owner.

| Item | Current state |
| --- | --- |
| Verified baseline | `origin/main` at `cf303fe29`, fetched 2026-11-04 |
| Retirement plan | [PR #162](https://bitbucket.org/protagona/plan-tool/pull-requests/162), merged |
| Retirement implementation | [PR #163](https://bitbucket.org/protagona/plan-tool/pull-requests/163), merged before the plan-status PR |
| Plan status and evidence | [PR #164](https://bitbucket.org/protagona/plan-tool/pull-requests/164), merged; six steps done |
| Validation | 14,702 passed, 67 skipped; two plan-canonical reconciliation sweeps; five Claude skill reviews to low-yield convergence |
| Durable evidence | [Implementation ledger](2026-11-04-completeness-apply-retirement-implementation.md), including every finding and disposition |

Both Bitbucket states and the matching code/plan artifact snapshots are verified
against the fetched remote. No unmerged implementation remains in this effort.
The CLI retires `completeness-apply`, `direct-run`, and `direct-jira`; saved
reports and legacy annotations remain readable. Deterministic repair and
existing review/reconcile authority remain unchanged. #369 stays independent;
#519 owns structural opt-in disposition and #520 owns stale lesson guidance.

## Next independent efforts

Keep each effort independently reviewable; do not combine them into a cleanup
plan or fold them into the shipped retirement.

| Priority | Backlog work | Pickup route |
| --- | --- | --- |
| 1 | Duplicated conceptual-correctness findings | Verify `completeness_report.py:build_report_md` and existing rendering tests. Render each finding once while preserving correctness in standalone grouped reports. Use a focused direct fix and the review convergence loop. |
| 2 | Valid class-method citations reported missing | Verify `data_contract.py:_module_level_symbol_exists` and supported dotted-symbol tests. Resolve valid class-method citations while preserving rejection of absent symbols. Bare-filename guessing and prose-negation inference remain separate design questions. |
| 3 | Full-suite worker/subprocess and `GateCleanCandidate` forward-reference failures | Reproduce surviving reports before selecting a fix. Do not stabilize tests for retired commands, widen timeouts, or alter initialization speculatively. |

Read each current `BUG_BACKLOG.md` entry before editing. Search by identifier
and vocabulary, verify reported bugs against existing tests, fix the invariant
across relevant sites, and retain focused/full validation and review evidence.
Use `claude-personal` for Claude skill review; the ordinary Claude CLI cannot
renew its expired login in this session.

## Deferred work

Broad consolidation, compact-detail redesign (#149), new convergence
heuristics, expanded telemetry, and shared terminal-failure receipts remain
separate efforts. The pre-existing Jira export collision with a missing custom
detail destination remains tracked in `BUG_BACKLOG.md`.

The [plan review record](2026-11-04-completeness-apply-retirement-review.md)
retains bare/detail audit provenance; do not repeat design auditing or mutate
the executed plan toward its implementation. The [Jira-grade retirement ledger](2026-11-03-jira-grade-retirement-plan.md)
is provenance for the preceding retirement, not current publication instructions.
