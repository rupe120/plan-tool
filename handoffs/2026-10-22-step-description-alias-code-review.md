# Step description alias: implementation review ledger

| Item | Record |
| --- | --- |
| Base | `b2e46f5a4` (merged plan PR #139) |
| Branch | `feat/step-description-alias` |
| Scope | BACKLOG #517, four approved steps; plan-canonical reconciliation and review tail |
| Execution | All four steps green and committed |
| Current review state | Three reconciliation sweeps complete; final two clean; two independent Claude Code passes confirm logic convergence |

## Settled decisions

Keep format v1 and legacy title input/writes working without an upgrade.
Preferred authored output is description, including ordinary legacy rewrites.
Equal valid dual-key strings succeed; conflicts and invalid peers fail.
Step.title/default model dumps remain internal contracts. Plan and feature
titles, unrelated schema/version checks and execution semantics stay unchanged.
Older installations rejecting newly emitted description plans is documented.
No bulk migration or upgrade command belongs here.

## Execution and known runner failure

Explicit backend/model on all runs: Codex / gpt-6.1-sol; stdin closed, -y,
--commit. Each code subprocess commits its implementation/tests before returning.
The tracked BUG_BACKLOG issue “Run's test-authoring gate misses tests committed
inside the backend call” then sees no dirty test delta and refuses advancement.
No gate is disabled and no step status is hand-edited. Each recovery inspects
the committed implementation and test diff, runs the full suite, then uses
run --step N --accept --commit, which reruns the plan gate before advancement.

| Step | Implementation | Recovery suite | Accepted checkpoint |
| --- | --- | --- | --- |
| 1 | `9ef7859e6` | 14,911 passed, 67 skipped, 74.19s | `24bec3d0b` |
| 2 | `ced7f8ab1` | 14,959 passed, 67 skipped, 78.00s | `d28e647f0` |
| 3 | `6941fd103` | 14,989 passed, 67 skipped, 72.25s | `183065759` |
| 4 | `891c48995` | ordinary run full test gate passes in 90.7s | `cbf788665` |

Every accepted step is pushed after its required pre-push full suite passes.
The existing gate defect is not repaired or reclassified in this effort.
Scratch logs: `.tmp/step-description-alias.run-N.log`, `.accept-N.log`,
`.step-N-recovery-tests.log`, `.push-N.log`.

## Reconcile sweep 1

Command: `uv run plan-tool --backend codex --model gpt-6.1-sol reconcile-code
step-description-alias --all --no-walk --no-reuse -y < /dev/null`.
Complete eligible set: steps 1, 2, 3, including done steps; non-code step 4
excluded. Exit zero; reports below are relative to
`docs/implementation-plans/plan-details/step-description-alias/reports/`.

| Step | Report | Result |
| --- | --- | --- |
| 1 | `20261022-145151-run-reconcile.json` | No findings |
| 2 | `20261022-145242-run-reconcile.json` | One medium body-byte preservation gap |
| 3 | `20261022-145315-run-reconcile.json` | No findings |

Finding `step2-run-reconcile-52952d9c` is confirmed. The governing property is
step 2's exact body preservation on an ordinary rewrite. Existing
TestRoundTrip.test_body_preserved_byte_for_byte reads normalized text and does
not pin newline bytes. The loss predates this alias, but contradicts that
explicit acceptance property. It is a bounded parser I/O correction, not a
request to redesign serialization.

Pre-edit site enumeration: identifier search covers write_plan, parse_plan,
_frontmatter_hash and raw file reads/writes; vocabulary search covers newline,
CRLF, body bytes and byte-for-byte in parser/tests/detail. Direct sites:
parse_plan's provenance read, write_plan's current-file read and publication.
render_plan_text already preserves its supplied body string; provenance refresh
already hashes its supplied text. Keep both unchanged.

New raw-byte tests span LF/CRLF/CR and both step key spellings, repeated writes,
body-only edits and rejection of external frontmatter edits. Before the fix,
the six-case newline test has four failures (CRLF/CR) and two LF passes. The
minimal correction reads raw UTF-8 bytes at both disk read sites and publishes
raw UTF-8 bytes, so provenance and body preservation agree. Focused parser and
consumer suites: 2,812 passed, 1 skipped in 13.72s. Full result and the fresh
reconciliation/review evidence follow as each completes.

Full suite after the correction: 14,996 passed, 67 skipped in 76.59s.

## Reconcile sweep 2

Same explicit command, after `06ee36b41`; completes all three code steps.
Reports `20261022-145655-run-reconcile.json`,
`20261022-145723-run-reconcile.json`, and
`20261022-145752-run-reconcile.json` each contain zero recommendations.
The body-byte finding is closed by the raw-byte reproduction and regression.

## Reconcile sweep 3

Same explicit command after `cd23db696`; all three code steps complete with
zero recommendations. Reports: `20261022-145853-run-reconcile.json`,
`20261022-145925-run-reconcile.json`, `20261022-150003-run-reconcile.json`.
The final two full sweeps are clean against the corrected implementation.
No further full sweep is warranted without a material code correction.

## Claude Code review 1

Range `b2e46f5a4..09338c987`; actual built-in code-review Skill at high effort,
Sonnet 5.5; session `45c78b9d-5b2d-4dad-b50b-7ec168e67f4a`, CLI exit zero.
Report `.tmp/step-description-alias.review-1.md`. The Skill supplies five
candidates; supervising review verifies callers, code and existing tests,
performs throwaway-input probes, and runs 4,138 targeted tests (1 skipped).
No confirmed logic defect; first clean logic pass after `06ee36b41`.

| Item | Disposition |
| --- | --- |
| D1 low stale annotate raw-key instructions and create comment | Confirmed; correct both sibling statements. Identifier/vocabulary sweep covers raw step title keys in prompts and authoring comments; story/plan titles and generic YAML quoting examples stay. No semantic parser change. |
| D2 low legacy-only diagnostics | Confirmed output, non-blocking: title remains accepted/actionable. Track “Step-field diagnostics advertise only legacy title after description alias support” in BUG_BACKLOG; avoid a partial formatter-only remedy that leaves raw Pydantic errors different. |
| M1 key order | Declined preference; canonical step text position is not an acceptance property. The minimal boundary translation preserves meaning. |
| M2 mixed frontmatter/body newlines | Accepted: frontmatter is reserialized; the explicit property preserves body bytes. |
| M3 separate callers normalize newlines | Verified source sites; track “Concept sync and scope-out rollback normalize existing plan body newlines” in BUG_BACKLOG. No end-to-end reproduction claimed for those separate paths. |

D1 changes only prompt/comment accuracy. It does not reset the clean logic
window. The next independent full-diff review must verify that correction and
the latest committed snapshot before the tail closes.

D1 correction validation: annotate/create tests 1,132 passed in 5.10s; full
suite 14,996 passed, 67 skipped in 78.87s. Diff whitespace check passes.

## Claude Code review 2 and final disposition

Range `b2e46f5a4..db6e63807`; actual built-in code-review Skill at high effort,
Sonnet 5.5; session `7a1b7b7f-21e6-4693-b06d-4281e4ecfe6d`, CLI exit zero.
Report `.tmp/step-description-alias.review-2.md`. The Skill returns six
candidates; supervising verification checks each against the approved plan,
existing tests, actual callers and independent probes. Targeted tests:
4,322 passed, 1 skipped in 25s. No confirmed in-scope logic defect.

- C2 rejected-conflicting/invalid proposal peers is refuted as a bug: the
  approved dual-key rule requires rejection and the existing tests pin it.
- C4 cross-flow provenance mismatch is refuted as a regression: each flow
  captures and compares its own representation. Remaining separate-path
  newline loss is the already-filed bug, not a reason to widen this fix.
- DOC-1 low confirms two sibling raw-key comments in annotate.py and
  annotate_render.py. Finish the D1 class sweep there with description/legacy
  title wording. The implementation reads step.title, populated by either key;
  no runtime change or prose-conformance test is needed. Session accuracy
  review compares both comments with those callers and the approved prompt.
- Key position, error-shape differences and generic colon-quoting examples
  remain wording/preferences. Legacy-only diagnostics stay in BUG_BACKLOG.
- The D1 prompt correction and maintained format docs are independently
  verified accurate by review 2.

**Logic convergence is confirmed:** two independent consecutive passes against
ranges containing latest logic change `06ee36b41` find no logic defect.
Both carry a low documentation tail, corrected through the closing comment
sweep; do not call this a completely clean all-prose audit. Review 2 covers
`db6e63807`, not the later comment/bookkeeping commit. Repository policy permits
finishing advisory prose corrections without resetting the logic window.
No additional full reconciliation is warranted on those comment findings.

BACKLOG #517 is removed only after four green steps, complete reconciliations,
full tests and the two independent reviews establish delivery. The two bounded
follow-up bugs remain in BUG_BACKLOG. Retire the plan-only pickup handoff and
route the index here; source plan PR #139 and its committed artifacts preserve
authoring provenance. Runtime code, the approved version-1 exception and
compatibility decisions are unchanged by this final bookkeeping.

Closing comment accuracy checks: annotate/annotate-render tests 83 passed in
0.32s; diff whitespace check passes. Last complete full suite remains 14,996
passed, 67 skipped; the closing change contains comments and bookkeeping only.
