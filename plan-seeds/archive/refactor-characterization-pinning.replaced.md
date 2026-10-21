> **Replaced**: this file has been superseded by `docs/implementation-plans/2-refactor-characterization-pinning.md`.
> Preserved here for history; do not edit.

# Plan seed: verify a `refactor` step's characterization tests actually pin *prior* behavior

This file is a `plan-tool create` input. Use it via:

```
plan-tool create refactor-characterization-pinning --from-existing plan-seeds/refactor-characterization-pinning.md --iterate
```

> **Source and lifecycle.** Implements BACKLOG **#203** and inherits its full
> scope contract. The final docs/status step must reconcile `BACKLOG.md`: mark
> #203 plan-authored while execution is pending and remove it only after the
> check ships. **#202** (claim-to-test coverage) is a *separate* entry that this
> plan does not ship — leave it in place, and do not let this plan drift into
> its claim-vs-test matching. Deferred follow-ups named below (promotion to
> blocking, `feature`-step coverage) stay in the backlog, not in this plan.

---

## Overview

`plan-tool run` appends a test-order directive to every `refactor` step:

> *"This is a **refactor** step — behavior-preserving. Write the
> characterization tests and run them green **BEFORE touching the code** under
> change; those same tests must pass unchanged after the refactor."*

Nothing verifies it. A characterization test written *after* the refactor pins
whatever the refactor produced; it is worthless as a behavior-preservation
guarantee and **indistinguishable from a correct one** by every signal the tool
has — it is green, it lives in a test file, and the test-authoring gate
(`launcher.py`, the post-call git-changed delta) is satisfied either way.
`run --commit` compounds it by committing tests and refactor as one commit, so
the ordering is invisible in git history too. Today the contract survives only
as prose in a directive.

This plan adds the missing check: for a `refactor` step, run the step's own
new/changed test files against the **pre-change** code and expect them to pass
there. Advisory only.

## First principles (these drive the gates)

- **The check is a re-run of the step's tests against older source.** It asserts
  nothing about test *quality* — only that the tests are *capable* of passing
  before the refactor, which is the entire content of "characterization".
- **A test that cannot even be collected pre-change is a finding, not an
  obstacle.** If a characterization file imports a symbol the refactor
  *created*, it cannot describe prior behavior by construction. The remedy is
  separating characterization cases into a module importing only pre-existing
  symbols.
- **Never edit the copied tests to force a green.** Stripping a failing import
  to make the check pass makes the check vacuous — the exact failure mode this
  work exists to catch.
- **A false alarm is more expensive than a miss here.** An advisory operators
  learn to ignore is worse than no advisory, so every case where the check
  cannot draw a sound conclusion must *skip and say why*, never emit a finding.

## Design

### The mechanism (proven by hand, 2026-07-30)

Step 8 of `jira-grade-01-detail-instrument` — the deterministic-battery
registry refactor — was verified this way by hand. Mechanize exactly this:

1. **At step start**, capture the pre-change commit (`git rev-parse HEAD`).
2. **After the step's call**, collect the step's new/changed **test** files (the
   same post-call git-changed delta the test-authoring gate already computes).
3. Create a worktree at the captured SHA.
4. Copy the **post-change** test files into it, unmodified.
5. Run **only those files** there.
6. Green → silent. Red, or uncollectable → one advisory finding naming which
   files failed and why.
7. Remove the worktree and prune, always — including on every error path.

### The precondition that is easy to miss

The captured SHA is the pre-change source **only when the tree is clean at step
start.** `--commit` provides that and is already mandated for multi-step runs.
Without it, a worktree at HEAD is missing every earlier uncommitted step, so a
characterization test can fail there because code it depends on has not landed
yet — nothing to do with test ordering. **Require a clean tree, or skip the
check and report why.** Do not emit a finding for the dirty case.

Note the existing `launcher.py` pre-call baseline is a *set of changed paths*
for the test-authoring gate, not a SHA — this is a new capture alongside it, not
a value to reuse.

### Primitives already shipped — write no new git plumbing

`plan_tool/cli/gitcommit.py` ships `worktree_add`, `worktree_list`,
`worktree_remove`, `worktree_prune`. All four are non-raising; the three
mutating ones are `(rc, tail)`-style, while `worktree_list` returns
`list[WorktreeEntry]` (`[]` on failure). `plan_tool/worktree.py` owns path
derivation (`worktree_base`, `derive_worktree_path`) and keeps the base a
**sibling** of the repo, never inside it.

### Finding calibration

Advisory, matching the existing fuzzy-matcher calibration and BACKLOG #202's:

- emitted at `info`,
- **out of** `review.py`'s `APPLY_ELIGIBLE_SOURCES` — it must never reach
  `apply_finding`,
- never flips an exit code,
- never blocks step advancement.

Promotion to blocking is explicitly **deferred** until precision is measured.

### Which steps are checked

`refactor` steps only. `feature` steps are **never** checked — their tests
legitimately fail pre-change, which is the point of the contract's other half —
and `non-code` steps have no test contract at all.

### Open design calls to settle during authoring

1. **Default-on for refactor steps, or opt-in behind a flag?** The cost is one
   worktree (~200–500 ms plus disk) and one targeted test run per refactor step.
   Recommendation: on by default for refactor steps *because* it is scoped that
   narrowly, with an opt-out.
2. **Which changed test files count.** The whole post-call test delta is the
   cheap answer and the one to start with; whether characterization cases can be
   distinguished from new-structure tests within a file is the harder question
   and should not block a first version.

## Suggested decomposition

Roughly: (1) the pre-step SHA capture and the clean-tree precondition, with its
skip-and-explain path; (2) the pre-change verification run itself — worktree,
copy, targeted run, guaranteed cleanup; (3) the advisory finding surface and its
calibration; (4) docs and the BACKLOG #203 close-out. Let the audit re-decompose
this — it is a starting shape, not a fence.

## Out of scope / Non-goals

- **`feature` steps.** Their tests legitimately fail pre-change.
- **Blocking on the finding before precision is measured.**
- **Coverage measurement or thresholds; blanket mutation testing.**
- **Reordering how `--commit` commits.** The concealment is context for why this
  check is needed, not a thing to fix here.
- **BACKLOG #202's claim-to-test matching.** Separate entry, separate mechanism.
- **Editing, patching, or import-stripping the copied test files.**

## Allowed behavior changes

One new advisory finding, and an optional pre-change verification run on
`refactor` steps. Nothing else.

## Allowed reorganization

None.

## Risks and mitigations

- **False alarms on tests that legitimately need new fixtures.** Mitigation:
  advisory-only, and the finding text must state that a new-fixture dependency
  is a plausible benign cause.
- **Worktree cost per refactor step.** Mitigation: refactor-only scope, targeted
  file selection, and an opt-out.
- **Leaked worktrees on an error path.** Mitigation: cleanup in a `finally`, and
  a prune on entry — this is the one failure that leaves durable mess behind.

## Acceptance criteria

- A characterization suite that passes against pre-change code is **silent**.
- A test suite written to match post-refactor output is **flagged**.
- A test file that cannot be *collected* pre-change is **flagged**, with the
  uncollectable case distinguished from the failing case in the message.
- A `feature` step is **never** checked; a `non-code` step is never checked.
- A dirty tree at step start **skips** the check with a stated reason and emits
  **no** finding.
- The finding never flips an exit code and is never apply-eligible.
- Worktrees are removed on every path, including failures.
- `BACKLOG.md` #203 is reconciled per the lifecycle note above.

## Stop / defer

**Stop condition, and it is a real one:** if most real characterization files
cannot run pre-change for legitimate reasons, stop and report that rate rather
than tuning. It would mean the contract itself needs restating before it can be
mechanized at all — a design finding, not a precision-tuning problem. Do not
skip the measurement, and do not respond to a high rate by loosening what counts
as a pass.

## Deferred

- Promoting the finding from advisory to blocking (needs measured precision).
- Distinguishing characterization cases from new-structure tests *within* one
  file.
- Any equivalent contract check for `feature` steps.
