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
