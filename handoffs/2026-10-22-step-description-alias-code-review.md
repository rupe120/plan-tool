# Step description alias: implementation review ledger

| Item | Record |
| --- | --- |
| Base | `b2e46f5a4` (merged plan PR #139) |
| Branch | `feat/step-description-alias` |
| Scope | BACKLOG #517, four approved steps; plan-canonical reconciliation and review tail |
| Execution | All four steps green and committed |
| Current review state | First reconciliation complete; bounded newline correction under validation; Claude Code reviews not yet run |

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
