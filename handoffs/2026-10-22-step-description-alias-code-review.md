# Step description alias: implementation review ledger

| Item | Record |
| --- | --- |
| Base | `b2e46f5a4` (merged plan PR #139) |
| Branch | `feat/step-description-alias` |
| Scope | BACKLOG #517, four approved steps; plan-canonical reconciliation and review tail |
| Execution | All four steps green and committed (Codex / gpt-6.1-sol, `-y`, `--commit`) |
| Reviews | Three `reconcile-code --all --no-walk --no-reuse -y` sweeps; two Claude Code `/code-review` passes (built-in skill, high effort, Sonnet 5.5), reports `.tmp/step-description-alias.review-N.md` |
| Closure | **Logic convergence confirmed** (two independent consecutive passes against ranges containing the latest logic change `06ee36b41`); low documentation tail, not a completely clean all-prose audit |
| Checks | Last complete suite 14,996 passed, 67 skipped; `git diff --check` clean |

## Settled decisions

- Keep format v1; legacy title input/writes keep working without an upgrade. Preferred authored output is description, including ordinary legacy rewrites.
- Equal valid dual-key strings succeed; conflicts and invalid peers fail (pinned by existing tests).
- `Step.title`/default model dumps stay internal contracts; plan and feature titles, unrelated schema/version checks and execution semantics are unchanged. Older installations rejecting newly emitted description plans is documented.
- No bulk migration or upgrade command.

## Execution record

Each code subprocess committed its own implementation and tests, so the tracked BUG_BACKLOG issue "Run's test-authoring gate misses tests committed inside the backend call" refused advancement. No gate was disabled and no status hand-edited; each recovery inspected the committed diff, ran the full suite, then `run --step N --accept --commit` (which reruns the gate). The gate defect is not repaired here. Every accepted step was pushed after its pre-push full suite passed. Logs: `.tmp/step-description-alias.{run,accept,step-N-recovery-tests,push}-N.log`.

| Step | Implementation | Recovery suite | Accepted checkpoint |
| --- | --- | --- | --- |
| 1 | `9ef7859e6` | 14,911 passed, 67 skipped | `24bec3d0b` |
| 2 | `ced7f8ab1` | 14,959 passed, 67 skipped | `d28e647f0` |
| 3 | `6941fd103` | 14,989 passed, 67 skipped | `183065759` |
| 4 | `891c48995` | ordinary run gate passed | `cbf788665` |

## Findings

| Source | Finding | Disposition |
| --- | --- | --- |
| Reconcile 1, step 2 | `step2-run-reconcile-52952d9c` medium: ordinary rewrite loses body bytes (CRLF/CR); `TestRoundTrip.test_body_preserved_byte_for_byte` reads normalized text | fixed `06ee36b41`: raw UTF-8 bytes read at `parse_plan` provenance read and `write_plan` current-file read and published raw; six-case LF/CRLF/CR newline test (both step key spellings) had four failures before; focused parser/consumer suites 2,812 passed; full 14,996 passed |
| Reconcile 1 | Steps 1 and 3: no findings (non-code step 4 excluded) | none |
| Reconcile 2, 3 | Zero recommendations on all three code steps (after `06ee36b41` and `cd23db696`); the final two full sweeps are clean | none; no further full sweep without a material code correction |
| CR 1 (`09338c987`) | D1 low: stale annotate raw-key instructions and a create comment | fixed: prompt/comment accuracy only (annotate/create 1,132 passed; full 14,996 passed); sibling raw-key comments in `annotate.py` and `annotate_render.py` finished under DOC-1 below |
| CR 1 | D2 low: diagnostics advertise only legacy `title` | tracked BUG_BACKLOG "Step-field diagnostics advertise only legacy title after description alias support" (a formatter-only remedy would leave raw Pydantic errors different) |
| CR 1 | M1 key order | declined: canonical position is not an acceptance property |
| CR 1 | M2 mixed frontmatter/body newlines | declined: frontmatter is reserialized; the property preserves body bytes |
| CR 1 | M3 other callers normalize body newlines | tracked BUG_BACKLOG "Concept sync and scope-out rollback normalize existing plan body newlines" (no end-to-end reproduction claimed) |
| CR 2 (`db6e63807`) | C2 rejected conflicting/invalid peers | refuted: the approved dual-key rule requires rejection; existing tests pin it |
| CR 2 | C4 cross-flow provenance mismatch | refuted: each flow captures and compares its own representation; remaining separate-path newline loss is the filed bug |
| CR 2 | DOC-1 low: two sibling raw-key comments | fixed: description/legacy-title wording in both; no runtime change (annotate/annotate-render 83 passed) |
| CR 2 | Key position, error shapes, colon-quoting examples | declined: wording/preferences |

Review 1 ran 4,138 targeted tests (1 skipped) with throwaway-input probes; review 2 ran 4,322 (1 skipped) and verified the D1 prompt correction and maintained format docs accurate.

## Closure

**Logic convergence confirmed.** Review 2 covers `db6e63807`, not the later comment/bookkeeping commit; repository policy lets advisory prose corrections finish without resetting the logic window. BACKLOG #517 is removed after four green steps, complete reconciliations, full tests and both reviews. Retired the plan-only pickup handoff and routed the index here; plan PR #139 preserves authoring provenance. Runtime code, the version-1 exception and compatibility decisions are unchanged by the closing bookkeeping.

Tracked: the two BUG_BACKLOG follow-ups above. Pending: none.
