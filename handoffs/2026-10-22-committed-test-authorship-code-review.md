# Committed test authorship gate repair

| Item | Record |
| --- | --- |
| Base | `db0b81151`, merged alias PR #140 |
| Branch | `fix/committed-test-authorship` |
| Route | Bounded direct fix; existing BUG_BACKLOG condition permits direct repair when no evidence redesign is needed |
| Current state | Implementation and focused tests complete; full validation and Claude Code review pending |

## Property and scope

A test added or modified in commits between the pre-call HEAD and post-call
HEAD can satisfy the existing file-authorship gate. It must not need to remain
dirty when the backend returns. Preserve existing dirty-path subtraction for
both sources of evidence, enforcement eligibility, mode exclusions, normal
test/gate execution, failure persistence and advancement contracts.
No coverage-quality judgment, automatic acceptance, test-ordering contract,
retry-guard redesign, or exemption expansion belongs here.

Existing BUG_BACKLOG entry “Run's test-authoring gate misses tests committed
inside the backend call” names this repair. Observed alias steps in PR #140
supply three more real reproductions; their full-suite acceptance recovery is
recorded in the alias implementation ledger. Keep the entry until verification
and the actual Claude Code review loop establish delivery.

## Pre-edit site enumeration

Defect class: dirty-path evidence loses tests committed during the backend call.
Identifier search: `_git_changed_paths`, `git_test_baseline`,
`_step_requires_test_authoring`, HEAD/revision helpers and test-authoring tests.
Vocabulary search: authorship, pre-call baseline, changed/modified test files,
porcelain, dirty tests and commit evidence across source/tests/run docs.

- launcher.py has one enforcement consumer, with a pre-call dirty snapshot and
  post-call set difference. Extend only its evidence set with the commit delta.
- git_state.py owns git reads below launcher/shell. Add commit snapshot/delta
  reads there; keep the launcher-local dirty-read monkeypatch seam unchanged.
- tests/test_launcher.py owns real-git gate regressions and existing opt-outs.
  tests/test_git_state.py owns git read/error behavior.
- docs/how-to/pipeline/run.md's gate diagram describes only porcelain and
  incorrectly promises a non-git skip. Describe the actual evidence/failure
  contract. docs/ARCHITECTURE.md lists the leaf's new read helpers.
- Protected CLAUDE.md and shared driving directives still correctly mandate
  committing between steps: pre-existing dirty paths remain excluded. No policy
  change is needed. Retry-guard consumers retain their existing evidence.

## Chosen evidence boundary

Capture a readable pre-call commit only when the gate applies. Union the
post-call working-tree paths with the net pre-call-HEAD/post-call-HEAD added or
modified paths, then subtract all pre-call dirty paths and filter test paths.
NUL-delimited diff output preserves spaces and rename destinations; committed
deletions are excluded. No known pre-call HEAD or a failed diff supplies no
additional evidence; existing working-tree behavior remains. Unborn/no-HEAD
commit-only execution is not newly certified by this bounded repair.

Focused tests cover clean, unstaged, staged and untracked pre-call test paths
against committed test, production-only, deletion and uncommitted-test actions;
multiple backend commits, new tests with spaces and feature/refactor eligibility;
unknown git/HEAD and helper error paths. Existing gate opt-out tests stay.
Initial focused run: 51 passed in 6.79s. Restoring the old dirty-only logic makes
both feature/refactor multi-commit regressions fail (2 failures); source is
restored after mutation. Dirty-exclusion mutation and full results follow.

Removing dirty-path subtraction produces 9 failures and 7 passes in the
16-case matrix; the source is restored afterward. Full suite: 15,016 passed,
67 skipped in 70.41s. `git diff --check` passes.

## Claude Code review 1

Range `db0b81151..b877be0d9`; actual built-in code-review Skill at high effort,
Sonnet 5.5, session `fbfb31e0-5d5f-4c5d-a1db-00d1562e0f99`, CLI exit zero. Report
`.tmp/committed-test-authorship.review-1.md`. The Skill supplies seven
candidates; supervising review independently verifies callers and existing
tests. It runs no tests because its test shell request requires approval;
its verdict relies on static verification and the recorded author tests.
**No logic defect**; first independent clean logic pass against `59e13bc32`.

- D1 low confirmed: stale non-git skip claims in git_state.changed_paths,
  launcher._git_changed_paths and the launcher test comment. Correct all three
  and explicitly document the existing enforced-gate failure in the run guide.
  Add an actual run_step regression: creating a test outside git supplies no
  git evidence and cannot advance an enforced step. This pins existing behavior,
  not a product policy change. Identifier/vocabulary sweep covers never block,
  never blocks, non-git, changed-path readers and the gate diagram.
- D2 info confirmed: module summary now names working-tree and commit reads.
- Unborn HEAD extension and retry-guard redesign are outside the bounded task.
  Dirty-path subtraction is required, not a defect. Committed rename destinations
  agree with the existing test that credits dirty rename destinations.
- Subprocess factoring, diff short-circuiting and test formatting are declined
  maintenance preferences; no verified consolidation is claimed or taken.

The correction changes comments/docs and adds coverage only. Enforcement,
return values and all production logic remain the reviewed implementation.

D1/D2 verification: 52 focused tests pass in 6.65s; the non-git regression fails
when unreadable HEAD is incorrectly made an exemption (1 mutation failure).
Full suite after the coverage/doc correction: 15,017 passed, 67 skipped in
77.67s. Source is restored after mutation; diff whitespace checks pass.

## Claude Code review 2: independent triage overrides two labels

Range `db0b81151..9a626fd7e`, actual built-in code-review Skill at high effort,
Sonnet 5.5, session `091d62b0-8a93-48ec-be73-57c2b9c8ef89`, CLI exit zero. Report
`.tmp/committed-test-authorship.review-2.md`. Five candidates receive
supervising verification; 37 focused tests pass. The report calls the change
clean but explicitly describes a new false-pass route and a decoding crash.
Those classifications do not override the actual gate property.

- B1 is confirmed with a real-git run_step reproduction: prepare existing test
  history, diverge the pre-call branch, and let the fake backend only checkout
  that history. The current gate incorrectly advances. Committed evidence must
  extend the captured HEAD; add an ancestry check before accepting its delta.
  This narrows the new evidence source and leaves working-tree evidence intact.
- B2 is confirmed via raw-byte subprocess output: UnicodeDecodeError escapes
  the current path decoder. A first on-disk fixture cannot create invalid UTF-8
  names on this macOS filesystem, so it is not counted as a code reproduction.
  A real subprocess emitting the raw bytes reproduces the decoder failure
  independently of that filesystem limitation. Use surrogateescape at all three
  existing/new git subprocess readers so the shared evidence class stays whole.
  Identifier/vocabulary sweep: subprocess.run, text=True, changed_paths_or_none,
  committed_changed_paths, head_revision, path bytes, UnicodeDecodeError and
  HEAD movement. The retry policy itself remains unchanged.
- C1 dirty exclusion and C2 unborn commit-only extension remain pinned/deferred
  scope, not defects. Diagnostic taxonomy and factoring remain preferences.
- Fix the informational known-limit comment's porcelain wording while touching
  that exact contract; its dirty-path exclusion remains the intended rule.

The production corrections reset the two-pass logic confirmation window.
Do not count reviews 1/2 as clean passes against the changed implementation.

Post-correction validation: 54 focused tests pass in 6.89s; full suite 15,019
passed, 67 skipped in 74.27s. The new ancestry regression reproduces a false
pass before correction; the path-output regression reproduces UnicodeDecodeError
before correction. Both now pass. Fixes are committed separately by concern.
