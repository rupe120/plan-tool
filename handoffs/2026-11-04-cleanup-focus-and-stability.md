# Cleanup for focus and stability

BACKLOG #376 is shipped. The next pickup is the separately tracked full-suite stability work; the backlog remains the queue and scope owner.

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
| Complete locally | Duplicated conceptual-correctness findings | Embedded checkpoint and final reports render conceptual correctness once; standalone grouped output retains the findings. See validation below. |
| Complete locally | Valid class-method citations reported missing | Direct normal, private, and async methods resolve; registry field validation stays authoritative. Nested functions retain a separate backlog entry. |
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

## Single-render report fix

The 2026-11-04 direct fix separates embedded grouped rendering from standalone
console rendering at both production call sites: the pre-apply checkpoint and
final report writer. The enclosing report owns conceptual-correctness bullets;
the embedded group points there only when findings exist. Deterministic path
and dependency diagnostics remain in that group. Empty reports have no dangling
section pointer. Persisted findings and audit policy retain their contracts.

Identifier searches cover `_render_grouped_report`, `build_report_md`, and both
persistence callers; vocabulary searches cover correctness sections, grouped
reports, and duplicate findings. Existing standalone multiline-body coverage
remains. New assertions cover single rendering in both iteration modes, the
checkpoint artifact, and the empty-state exception. Restoring the duplicate
loop makes both single-render cases fail; the source is restored immediately.
Focused validation passes 1,110 tests. Full regression validation passes
14,705 tests with 67 skipped in 62.41 seconds. `git diff --check` passes.
The resolved bug entry is removed from `BUG_BACKLOG.md`.

The first Codex review confirms the test fixture mistake (`_corr_rec` produces
`granularity-split`), corrected with an explicit conceptual-correctness fixture.
The confirmation Codex review reports no findings and independently passes
all 1,110 focused tests. The direct-change review loop converges. Review and
full-suite logs are transient under `/private/tmp/completeness-report-single-render.*`.

## Class-method citation fix

Ordinary Python anchors resolve direct method definitions on a module-level
class, including private and async methods. The shared AST helper keeps its
module-symbol behavior. Registered contract owners continue field and owner-path
validation before AST fallback. Runtime dict keys, absent members, and methods
on a different class do not resolve. Citation grammar, path guessing, and
prose-negation interpretation retain their contracts. Nested-function support
remains a separate decision in `BUG_BACKLOG.md`.

Identifier searches cover both symbol helpers and their callers; vocabulary
searches cover dotted symbols, methods, missing anchors, and registered fields.
The pre-edit tests pin missing module symbols and registry fields but carry no
class-method case. The new matrix covers ten recognized symbol shapes; a
separate test pins registry precedence. Disabling method resolution fails the
normal/private/async cases. Bypassing the registry fails its carve-out test.
Both mutations are restored immediately. Focused new tests: 11 passed. Full
suite: 14,716 passed, 67 skipped in 74.71 seconds. `git diff --check` passes.

The first Codex review confirms that a three-part test is outside the existing
citation grammar, so that test is removed rather than expanding the grammar.
The confirmation Codex review finds no actionable regressions and independently
passes all 206 data-contract tests. The direct-change review loop converges.
Transient review and validation logs use `/private/tmp/class-method-citations.*`.
