# Cleanup for focus and stability

BACKLOG #376 and the fixes in PRs #165–167 are shipped. The user
defers full-suite stability work; continue from the live BUG queue.

| Item | Current state |
| --- | --- |
| Verified baseline | `origin/main` at `416ebae2f`, fetched 2026-11-04 |
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
| Merged in PR #165 | Duplicated conceptual-correctness findings | Embedded checkpoint and final reports render conceptual correctness once; standalone grouped output retains the findings. See validation below. |
| Merged in PR #165 | Valid class-method citations reported missing | Direct normal, private, and async methods resolve; registry field validation stays authoritative. Nested functions retain a separate backlog entry. |
| Deferred by user | Full-suite worker/subprocess and `GateCleanCandidate` forward-reference failures | No failure reproduces in the current environment. Investigation evidence is committed at `fd07b7734` on `investigate/full-suite-stability`; no initialization or timeout change is selected. |
| Merged in PR #166 | Same-batch added row self-reference | Endpoint lookup accepts exact typed self-references; the row still needs independent grounding in reached predecessor context. |
| Merged in PR #167 | Feature-container unknown-field diagnostics | Feature entries list Feature keys and name the correct container; plan/step diagnostics retain their behavior. |
| Complete locally | Jira outputs colliding with absent declared detail paths | Protect both declared and canonical paths for both export destinations before rendering or model invocation. |

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

## Same-batch self-reference fix

The first bounded BUG item reproduces through the existing
`parse_candidate_delta` / `materialize_candidate` test helpers. A new entity
that cites itself is refused even with an outgoing or incoming connection to a
reached predecessor. Endpoint lookup excludes the owning operation although it
is also the exact endpoint producer.

Pre-edit identifier searches cover `_same_batch_added_endpoint_identity` and
both consumers (`_validate_relation_authority`, `_refuse_unanchored_additions`).
Vocabulary searches cover self-references, owner/endpoint comparisons, reached
anchors, and mutually citing additions in source, tests, and `ROADMAP_FORMAT.md`.
The shared helper is the sole matching exclusion; the fixed-point reachability
rules and the single-feedback opt-out remain intact.

The fix deletes the owning-operation exclusion and retains exact type,
artifact, row-id, uniqueness, and candidate-membership checks. Six regression
cases cover outgoing grounding, incoming grounding, and self-only refusal in
both operation orders. All six fail against the original implementation; all
189 candidate tests pass after the fix. The code review finds no actionable
issues and independently passes all 189 tests. The format doc and changelog
state the self-reference/grounding boundary.

The source bug entry is removed. Its endpoint-kind observation is already
covered by an existing exhaustive test; its unproven removed-relation concern
is retired with an exact reopen condition in `docs/history/backlog-decisions.md`.
No removed-relation policy or endpoint table changes accompany this fix.
Full regression validation passes: 14,722 passed, 67 skipped in 75.05 seconds.
Temporarily marking every added row reached makes both self-only cases fail;
the source is restored immediately, then all 189 candidate tests pass again.
`git diff --check` passes. Transient evidence uses
`/private/tmp/same-batch-self-reference.*`.

## Feature-container diagnostics

The ready direct BUG item reproduces through `parse_plan_text` followed by
`format_validation_errors`: extra `description`, `depends_on`, `steps`, and typo
keys in `features[0]` are rejected but called plan-level fields. All four new
cases fail against the original formatter.

Pre-edit identifier searches cover `_explain_extra_field`, its formatter and
callers, `Feature.model_fields`, and feature error locations. Vocabulary
searches cover unknown fields, allowed fields, and placement hints across
parser code, mirrored tests, and format/reference documentation. One shared
formatter owns the defect; there are no separate caller implementations.

The bounded correction recognizes a feature-entry location
`("features", index, field)` and lists the actual `Feature` keys. Validation,
structured errors, plan/step messages, missing feature-title messages, and step
alias hints retain their contracts. Regression tests compare the exact allowed
key list and verify that formatting leaves the structured errors unchanged.
The focused parser suite passes all 473 tests. The code review finds no
actionable issues and independently passes all 473 parser tests. Full regression
validation passes 14,726 tests with 67 skipped in 76.49 seconds;
`git diff --check` passes. The format doc and changelog include feature entries;
the resolved bug entry is removed.

Branch: `fix/feature-field-diagnostics`. Transient validation and review logs
use `/private/tmp/feature-field-diagnostics.*`.

### Claude Code review follow-through

Both reviews use the personal Claude Code configuration, model
`claude-sonnet-5-5`, high effort, report-only local-diff form, and explicitly
invoke the `engineering:code-review` skill. The prior Codex review is additional
evidence; it does not stand in for these Claude skill reviews.

| Round | Reviewed range | Finding and disposition |
| --- | --- | --- |
| 1 | `949ce72e3..d3f577558` | No correctness defects; one low optional test gap at the feature error assertion: a trailing placement hint can escape its prefix/key checks. Fixed at `d11e350c0` with an end-of-message assertion. |
| 2 | `949ce72e3..d11e350c0` | Approve, no actionable findings. Confirms the low finding is closed and no new issues appear. |

The finding's class is an unasserted diagnostic suffix. Identifier and
vocabulary searches cover the feature diagnostic return, its sole regression
test, allowed keys, and placement hints. The suffix assertion applies to all
four parametrized fields. Temporarily appending placement advice to the feature
message makes all four cases fail at the new assertion. The source is restored
immediately; all 473 parser tests then pass. No runtime change follows the
Claude reviews.

Coverage limits remain explicit: round 1 uses static review and ad-hoc probes,
without pytest or mutation runs; round 2 runs the four focused cases but relies
on the session's parser/full-suite and mutation evidence. Other nested-model
diagnostics and currently unreachable deeper feature locations remain outside
this fix. Round 2 notes a hypothetical suffix ending in `)` as non-actionable;
no additional hardening follows. Cosmetic docstring wording is declined as
non-actionable. Transient review captures are
`/private/tmp/feature-field-diagnostics.claude-review-1.log` and
`/private/tmp/feature-field-diagnostics.claude-review-2.log`.

Post-review full validation first reports 1 failed, 14,725 passed, 67 skipped in
70.48 seconds: `test_new_run_id_is_unique_per_call` on worker `gw8` produces 99
IDs from 100 calls. `new_run_id` and its tests are unchanged by this branch;
the seconds prefix plus `secrets.token_hex(3)` admits random collisions. The
observed bug is filed separately in `BUG_BACKLOG.md` under RISK. No run-ID
implementation or test change accompanies the feature diagnostic fix.

The isolated run-ID test plus all parser tests pass (474 tests). The standalone
full-suite rerun passes: 14,726 passed, 67 skipped in 62.89 seconds. This is the
final regression evidence after the review correction; it does not establish
that the separately tracked run-ID collision is fixed. The failed run and its
scope disposition remain above. No runtime source change follows the clean
Claude confirmation review.

## Jira declared-detail collision fix, 2026-11-05

Branch `fix/jira-declared-detail-collision` starts at merged PR #167's
`416ebae2f`. The ready BUG item is the absent custom-detail destination collision
retained from IPPT-17's retirement reconciliation. It is a bounded direct fix;
publication, recovery, formats, historical fallback, and target normalization
retain their contracts.

Defect class: the export preflight reserves only conventional detail paths,
while capture reads declared `steps[].detail` pointers. Identifier searches
cover `_all_detail_artifact_paths`, `_capture_target_preflight`, both render and
publication routes, `step.detail`, and `derive_detail_path`. Vocabulary searches
cover detail-artifact collisions, declared pointers, custom details, and missing
paths. One shared set builder supplies both story and handoff checks. The
format contract in `JIRA_FORMAT.md` is its one detailed restatement.

The fix adds each non-null declared pointer as `repo_root / step.detail` to
the existing protected set using `_repo_relative_posix`, preserving canonical
paths and their normalization. Every plan step is considered. Capture preflight
rejects matching story or handoff outputs before detail capture, rendering, or
backend invocation.

Four end-to-end regression cases cover story/handoff crossed with markdown/JSON.
They fail on the original implementation by reaching the forbidden handoff
renderer. After the fix they raise the collision error and create no output.
All 247 Jira tests pass. Existing tests preserve canonical and bundle checks,
noncolliding paired exports, and missing-detail historical fallback for done
steps. Full suite: **14,730 passed, 67 skipped in 80.62 seconds**.
`git diff --check` passes. The resolved bug entry is removed; the changelog is
`changelog.d/jira-declared-detail-collision.md`.

Claude Code uses the personal configuration with `claude-sonnet-5-5` at high
effort and explicitly invokes `engineering:code-review` in report-only mode.
It reviews the uncommitted working-tree diff against `416ebae2f`, including the
changelog, and returns **Approve, no findings**. Its independent validation
passes 304 Jira/detail-artifact tests. Coverage limits: it does not rerun the
full suite or reproduce the original failure because its source-substitution
attempts are sandbox-blocked; the session's actual pre-fix run supplies that
evidence. Symlinked pointers and empty-string detail pointers receive no new
end-to-end test. No speculative change follows the review's non-actionable
truthiness or wording observations.

Transient evidence uses `/private/tmp/jira-declared-detail-collision.*`.
Stability and run-ID risks remain separate; this green suite does not establish
that those intermittent defects are fixed.
