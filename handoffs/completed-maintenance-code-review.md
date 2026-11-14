# Completed maintenance review ledger

Historical review evidence, compressed 2026-11-05. All five fixes are merged.
Closure: each change converged through a clean review or confirmation; no findings remain pending.
This ledger owns review dispositions; `BUG_BACKLOG.md` owns remaining work.

| Change and delivered code | Publication | Review closure | Session validation |
| --- | --- | --- | --- |
| Single-render correctness report, `b0a38caf4` | [PR #165](https://bitbucket.org/protagona/plan-tool/pull-requests/165) | Codex confirmation: no findings; independently passes 1,110 focused tests | 14,705 passed, 67 skipped, 62.41s |
| Class-method citations, `87c87c53d` | PR #165 | Codex confirmation: no findings; independently passes 206 data-contract tests | 14,716 passed, 67 skipped, 74.71s |
| Grounded same-batch self-reference, `53f1e4cc1` | [PR #166](https://bitbucket.org/protagona/plan-tool/pull-requests/166) | Codex: no findings; independently passes 189 candidate tests | 14,722 passed, 67 skipped, 75.05s |
| Feature-field diagnostics, `5df11f2b2`, `d11e350c0` | [PR #167](https://bitbucket.org/protagona/plan-tool/pull-requests/167) | Claude confirmation: no findings; independently passes four new cases; Codex also passes 473 parser tests | Final rerun: 14,726 passed, 67 skipped, 62.89s |
| Jira declared-detail collision, `32ef6b685` | [PR #169](https://bitbucket.org/protagona/plan-tool/pull-requests/169) | Claude `engineering:code-review`: no findings; independently passes 304 Jira/detail-artifact tests | 14,730 passed, 67 skipped, 80.62s |

The Codex reviews for the first two fixes cover their working-tree diffs before
commit. Each correction is followed by a clean confirmation; both loops close
as converged. The feature-diagnostic and Jira Claude reviews explicitly invoke the plugin
skill in high-effort, report-only local-diff mode through the personal Claude
configuration, model `claude-sonnet-5-5`. No remote comments or publication occur
inside the reviews. Pre-push full-suite gates also pass for the published PRs.

## Findings and dispositions

| Review finding or observation | Disposition and retained reason |
| --- | --- |
| Report checkpoint test uses `_corr_rec`, which actually creates `granularity-split` | `fixed b0a38caf4`: use an explicit conceptual-correctness fixture; the checkpoint asserts one occurrence. The initial full run fails this test; the corrected focused and full runs pass. |
| Embedded empty correctness points to an absent dedicated section | `fixed b0a38caf4`: retain the empty-state message and test its absence of a section pointer. |
| Three-part citation test expects rejection outside the recognized grammar | `fixed 87c87c53d`: remove the unsupported expectation; keep the grammar unchanged. Two-part function-local citations remain separately tracked. |
| Same-batch entry's endpoint-kind table lacks exhaustiveness coverage | `refuted` by existing `test_relation_endpoint_table_types_every_kind_but_the_deliberately_untyped_decision_anchor`; no policy change. |
| Same-batch endpoint allowance is considered for removed relations | `declined`: no supported failing input established. The exact reopen condition is in [backlog decisions](../docs/history/backlog-decisions.md#same-batch-relation-follow-ups-2026-11-04); this is retirement of an unproven risk, not a claimed fix. |
| Claude feature review 1: trailing placement advice escapes prefix/key assertions | `fixed d11e350c0`: assert that the feature diagnostic ends at the allowed-key list. Suffix injection fails all four cases; restoring source returns 473 parser tests to green. |
| Claude feature review 2: hypothetical suffix also ends in `)` | `declined`: reviewer explicitly labels it non-actionable; no further hardening. |
| Feature formatter docstring wording | `declined`: cosmetic, no inaccurate rule or actionable defect established. |
| Deeper feature locations and other nested-model diagnostics | `declined` as scope expansion without a current supported failing feature location; not assessed by these reviews. |
| Jira review: `is not None` versus truthiness on an empty detail string | `declined`: no incorrect refusal or acceptance established; no speculative change. |
| Jira review: protected-path sentence wording | `declined`: accurate wording; cosmetic only. |
| Post-Claude suite reports 99 run IDs from 100 calls | `tracked BUG_BACKLOG.md`, RISK “Run IDs can collide within one second because their random suffix has only 24 bits.” Generator and test are unchanged by this fix. |

## Review ranges and coverage limits

- **Report rendering:** one shared renderer, checkpoint and final writers,
  unchanged standalone findings, deterministic diagnostics, and persisted data.
  Restoring duplicate rendering makes both iteration-mode regressions fail.
- **Citations:** ordinary, private, and async methods resolve; absent members,
  runtime dict keys, and wrong owners fail. Bypassing registry precedence fails
  its test; removing method support fails all three positive method cases.
- **Same-batch self-reference:** the review covers the working-tree diff against
  PR #165's merged `9364cc7d0`. Six regressions fail before the fix. Marking every
  added row reached fails the two self-only cases; source is restored and all
  189 candidate tests pass. Exact endpoint identity, grounding, and the
  single-feedback opt-out remain intact.
- **Feature Claude round 1:** `949ce72e3..d3f577558`, static review and ad-hoc
  probes; no pytest or mutation run. Round 2: `949ce72e3..d11e350c0`, four focused
  cases; full-suite and mutation evidence comes from the session. Validation,
  structured errors, missing feature-title messages, and plan/step aliases and
  placement hints retain their contracts.
- **Jira Claude review:** uncommitted diff against `416ebae2f`, including the
  changelog. The reviewer passes 304 focused tests but does not rerun the full
  suite. Its original-source substitution attempts are sandbox-blocked; the
  session supplies the actual four pre-fix failures. Symlink and empty-string
  detail pointers receive no new end-to-end test. Canonical/bundle checks,
  ordinary exports, and done-step historical fallback remain covered.

The first post-Claude feature full run reports one unrelated run-ID failure,
14,725 passed and 67 skipped in 70.48s, on worker `gw8`. The isolated run-ID test
and parser suite then pass together (474 tests), followed by the green full
rerun in the table. This does not establish that the collision is fixed.

## Remaining work

The reader/writer subprocess timeout and `GateCleanCandidate` forward-reference
failure are deferred by user direction, not fixed. Their reproduction evidence
and recurrence triggers belong in `BUG_BACKLOG.md`; no timeout or initialization
change is selected. The six-order cold import probe, 136-test module run, ten
guard repetitions, and 14,716-test full run do not reproduce either failure.
Nested-function citations and the run-ID collision also remain backlog work.
Broad consolidation, convergence heuristics, telemetry, and shared terminal-failure
receipts remain separate backlog efforts. No continuation route depends on the
retired pickup handoff.

## Archive cleanup review, 2026-11-05

Claude `engineering:code-review` reviews the 26-plan sweep and handoff
retirement against `fc4af85a0`. Round 1 identifies five low reference,
readiness, closure, and provenance gaps; all are corrected. Round 2 verifies
those corrections and identifies two further low evidence-retention gaps:
the reconcile heuristic disposition and an unsupported historical test count.
The disposition is restored and the count is removed. These findings describe
the prior cleanup edits; the corrections are complete. The final full suite
passes 14,730 tests with 67 skipped; the confirmation reviewer independently
passes 433 documentation and related tests. The review does not re-verify
archive byte equality or pre-existing dangling links.
