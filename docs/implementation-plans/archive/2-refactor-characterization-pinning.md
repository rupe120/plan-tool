---
title: Refactor Characterization Pinning
status: planning
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Add a detached option to worktree_add in gitcommit.py
  files:
  - plan_tool/cli/gitcommit.py
  - tests/cli/test_gitcommit.py
  complexity: low
  change_type: feature
  status: current
- id: 2
  title: Expand test_command with a files placeholder and reuse the test-gate runner
    for the sandbox
  files:
  - plan_tool/launcher.py
  - PLAN_FORMAT.md
  - tests/test_launcher.py
  complexity: low
  change_type: feature
- id: 3
  title: 'Add the throwaway pre-change sandbox: worktree at a SHA, copy test files
    in, always clean up'
  creates:
  - plan_tool/characterization_check.py
  - tests/test_characterization_check.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
- id: 4
  title: Run the copied tests in the sandbox and tell a failure apart from an uncollectable
    file
  files:
  - plan_tool/characterization_check.py
  - tests/test_characterization_check.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  - 3
- id: 5
  title: Add the characterization-pinning advisory finding and keep it out of the
    apply-eligible sources
  files:
  - plan_tool/review.py
  - plan_tool/characterization_check.py
  - tests/test_review.py
  - tests/test_characterization_check.py
  complexity: low
  change_type: feature
  depends_on:
  - 4
- id: 6
  title: Capture the pre-change commit at step start and decide whether the check
    can run
  files:
  - plan_tool/launcher.py
  - tests/test_launcher.py
  complexity: medium
  change_type: feature
  depends_on:
  - 5
- id: 7
  title: Run the check after the step's call and record the advisory to the run log
    without blocking advancement
  files:
  - plan_tool/launcher.py
  - tests/test_launcher.py
  complexity: medium
  change_type: feature
  depends_on:
  - 5
  - 6
- id: 8
  title: Add the --no-characterization-check flag and the per-step enforce_characterization_check
    opt-out
  files:
  - plan_tool/cli/run_cmd.py
  - plan_tool/schema.py
  - PLAN_FORMAT.md
  - tests/cli/test_run_cmd.py
  - tests/test_parser.py
  - docs/cli/run.md
  complexity: medium
  change_type: feature
  depends_on:
  - 7
- id: 9
  title: 'Document the check in the run flow and reconcile BACKLOG #203'
  files:
  - docs/RUN_FLOW.md
  - TESTING.md
  - CLAUDE.md
  - CAPABILITIES.md
  - BACKLOG.md
  complexity: low
  change_type: non-code
  depends_on:
  - 8
---
# Refactor Characterization Pinning

## Overview

`plan-tool run` appends a test-order directive to every `refactor` step — write the characterization tests and get them green **before touching the code** under change — but nothing verifies it. This plan mechanizes the verification: for a `refactor` step, capture the pre-change commit at step start, then after the step's call re-run the step's own new/changed test files against that **pre-change** code in a throwaway worktree and expect them to pass there. The result is one **advisory** finding: emitted at `info`, kept **out of** `review.py`'s `APPLY_ELIGIBLE_SOURCES`, never flipping an exit code and never blocking step advancement. It is scoped to `refactor` steps only, requires a clean tree at step start (skipping with a stated reason otherwise), and writes no new git plumbing — the worktree primitives in `plan_tool/cli/gitcommit.py` and `plan_tool/worktree.py` already ship.

## Problem statement

Every `refactor` step carries a prose directive: *"This is a **refactor** step — behavior-preserving. Write the characterization tests and run them green **BEFORE touching the code** under change; those same tests must pass unchanged after the refactor."* Nothing checks it. A characterization test written *after* the refactor pins whatever the refactor produced; it is worthless as a behavior-preservation guarantee and **indistinguishable from a correct one** by every signal the tool has — it is green, it lives in a test file, and the test-authoring gate (`launcher.py`, the post-call git-changed delta) is satisfied either way. `run --commit` compounds the problem by committing tests and refactor as one commit, so the ordering is invisible in git history too. Today the contract survives only as prose in a directive, so a refactor step can ship with tests that guarantee nothing and no signal ever says so.

The mechanism is not speculative: step 8 of `jira-grade-01-detail-instrument` — the deterministic-battery registry refactor — was verified this way by hand on 2026-07-30. This plan mechanizes exactly that procedure.

## Architecture

**The check is a re-run of the step's tests against older source.** It asserts nothing about test *quality* — only that the tests are *capable* of passing before the refactor, which is the entire content of "characterization". Four first principles drive the gates:

- **A test that cannot even be collected pre-change is a finding, not an obstacle.** If a characterization file imports a symbol the refactor *created*, it cannot describe prior behavior by construction. The remedy is separating characterization cases into a module importing only pre-existing symbols.
- **Never edit the copied tests to force a green.** Stripping a failing import to make the check pass makes the check vacuous — the exact failure mode this work exists to catch.
- **A false alarm is more expensive than a miss here.** An advisory operators learn to ignore is worse than no advisory. This cuts two ways, and the line between them is *whether the sandbox produced a result at all*:
  - **No result → skip and say why, emit nothing.** The preconditions failed, so there is nothing to report: a dirty tree, an unresolvable SHA, a worktree that could not be created, or no changed test files to copy.
  - **A red result → emit the advisory, with its ambiguity stated.** The sandbox ran and the tests did not pass. The check cannot distinguish a post-hoc test from one needing a fixture that does not exist pre-change, so the finding must name that ambiguity rather than assert a verdict. Suppressing it would discard the plan's only real signal.

  These are not in tension: the first is *no evidence*, the second is *evidence that admits more than one reading*.

**The mechanism**, mechanizing the hand-proven procedure:

1. **At step start**, capture the pre-change commit (`git rev-parse HEAD`).
2. **After the step's call**, collect the step's new/changed **test** files from the post-call git-changed set. This is the *same shape* the test-authoring gate computes, but it is **not a reuse of that gate's value**: `plan_tool/launcher.py` captures `git_test_baseline` only when the gate applies (`if enforce_step_tests else set()`, itself gated on `_step_requires_test_authoring` and the per-step `enforce_test_authoring: false` opt-out), so on a plan with `enforce_step_tests` unset there is no delta to borrow. The clean-tree precondition settles this: with a clean tree at step start, the post-call changed set *is* the step's delta, so the check computes it independently and runs regardless of whether the test-authoring gate is on.
3. **Prune any stale administrative entry, then create** a worktree at the captured SHA. The prune comes *first* because a previous crashed run leaves a `$GIT_DIR/worktrees` entry and possibly a leftover directory behind, and `git worktree add` fails on a non-empty target. The sandbox path is derived per-step, not per-plan — `derive_worktree_path` returns a deterministic `base / slug` for the same inputs, so a plan-level slug would collide between two steps of one run and between a run and its own interrupted predecessor. A step-scoped slug plus an entry prune plus a pre-create `classify_target` check (treating `NON_EMPTY` as *remove-then-recreate*, never *reuse*) is what makes the sandbox genuinely throwaway.
4. Copy the **post-change** test files into it, unmodified.
5. Run **only those files** there, through the **existing** test-gate runner rather than a new one — **received as an injected callable, never imported** (see the runner-injection constraint below). `plan_tool/launcher.py`'s `_run_test_gate(command, repo_root, *, timeout_s=600)` already takes its working directory as a parameter, so the sandbox needs `cwd=<worktree>` and nothing more: it is `shell=True`, non-raising, returns `(rc, tail)` with the last ~500 chars, and reports `124` on timeout / `127` on spawn failure — the right shape for an advisory. Whether a non-zero rc *blocks* is decided by the caller, so the gate's blocking semantics and this check's advisory ones coexist on one primitive.

   **What the command is** comes from the plan's existing `test_command`, expanded (step 2) with a `{files}` placeholder — **not** a new frontmatter field. Today's values are not templates (`PLAN_FORMAT.md`'s own example, `cd plan-tool && uv run pytest tests/test_run_log.py -q --tb=no`, bakes in both a path and a `cd`), so appending paths is not viable: the baked-in file would run too and trailing flags would land in the wrong position. A plan whose `test_command` carries no `{files}` placeholder — which is **every plan today** — is a **skip with a stated reason**, never a guess. Substituted paths are relative to the shell's *final* directory, so a command that `cd`s into a subdirectory relocates them with it.
6. Green → silent. Red, or uncollectable → one advisory finding naming which files failed and why.
7. Remove the worktree and prune, always — including on every error path.

The worktree is a throwaway checkout of a commit, not a branch: `git worktree add -d <path> <commit-ish>` (the `--detach` form) is the shape that applies here, since detaching avoids git's refusal to check the same branch out in two worktrees at once. Cleanup is `git worktree remove` (which refuses an unclean worktree unless forced) followed by `git worktree prune`, which clears the `$GIT_DIR/worktrees` administrative entry left behind when a working tree goes missing.

**Import-layering constraint (binding on steps 3, 6, and 7).** `plan_tool/characterization_check.py` is imported by `plan_tool/launcher.py`, and it needs `plan_tool/cli/gitcommit.py`'s worktree primitives — but importing *anything* from the `plan_tool.cli` package executes `plan_tool/cli/__init__.py`, which does `from plan_tool.cli import app`, and `plan_tool/cli/app.py` imports `plan_tool.launcher` at module top. A module-top import of the primitives from a module that `launcher` imports is therefore a **circular import**. The plan's no-new-git-plumbing fence forbids relocating the primitives, so the resolution is the one already established in this codebase: **defer the import into the function body**, exactly as `plan_tool/capability_catalog.py` does (`from plan_tool.cli import build_parser` inside a function, with a docstring naming cycle-avoidance as the reason). No top-level module imports `plan_tool.cli` at module scope today, and this plan must not become the first.

**Runner-injection constraint (binding on steps 2, 4, 6, and 7) — the second cycle, and why *reuse* must not mean *import*.** Reusing `_run_test_gate` creates a cycle of its own, in the opposite direction from the one above: the runner lives in `plan_tool/launcher.py`, and steps 6–7 make `launcher` import `plan_tool/characterization_check.py`. If the check imported the runner back, `launcher → characterization_check → launcher` closes the loop. **The resolution is injection, not extraction:** `launcher` owns `_run_test_gate` and **passes it in**, along with the plan's `test_command` template; `characterization_check` declares it structurally (`Callable[[str, Path], tuple[int, str]]`) and imports nothing from `launcher`. The parameter takes **no first-party default** — defaulting it to `_run_test_gate` would reintroduce the very import it exists to avoid, so the caller always supplies it.

Two reasons injection beats lifting the runner into a stdlib-only leaf (the `plan_tool/rate_limit_loop.py` shape, which would also break the cycle):

- **The plan already requires this seam.** Its own Testing section states that *"the pre-change test run itself must be seam-injected rather than shelling out to a real pytest in a real worktree."* Injection is therefore not merely cycle-avoidance — it is the design the test strategy already assumes, and it matches the invoker-seam idiom the codebase is built on.
- **Extraction would make step 2 a mixed step.** Moving `_run_test_gate` out of `launcher` is a behavior-preserving **refactor**; adding the `{files}` placeholder is a **feature**. Fusing them is exactly the refactor+feature mixture this tool's own granularity advisor splits — and a plan whose subject is the integrity of `refactor` steps must not ship one. Injection keeps step 2 type-pure.

**The precondition that is easy to miss.** The captured SHA is the pre-change source **only when the tree is clean at step start.** `--commit` provides that and is already mandated for multi-step runs. Without it, a worktree at HEAD is missing every earlier uncommitted step, so a characterization test can fail there because code it depends on has not landed yet — nothing to do with test ordering. **Require a clean tree, or skip the check and report why.** Do not emit a finding for the dirty case. Note the existing `launcher.py` pre-call baseline is a *set of changed paths* for the test-authoring gate, not a SHA — this is a new capture alongside it, not a value to reuse. The clean-tree probe is a `git status` read over both tracked modifications and untracked files (`--porcelain` is the stable, config-independent form for scripts).

**Primitives already shipped — write no new git plumbing.** `plan_tool/cli/gitcommit.py` ships `worktree_add`, `worktree_list`, `worktree_remove`, `worktree_prune`. All four are non-raising; the three mutating ones are `(rc, tail)`-style, while `worktree_list` returns `list[WorktreeEntry]` (`[]` on failure). `plan_tool/worktree.py` owns path derivation (`worktree_base`, `derive_worktree_path`) and keeps the base a **sibling** of the repo, never inside it.

**Finding calibration.** Advisory, matching the existing fuzzy-matcher calibration and BACKLOG #202's: emitted at `info`; **out of** `review.py`'s `APPLY_ELIGIBLE_SOURCES` — it must never reach `apply_finding`; never flips an exit code; never blocks step advancement. Promotion to blocking is explicitly deferred until precision is measured.

**Where the advisory goes: the run log, not just the console (step 7).** Every outcome — flagged, silent, and *skipped-with-reason* — is appended to the step's run-log entry via `plan_tool/run_log.py`'s `append_event` under its own event kind. `Event.kind` is a free-form `str`, so this needs no run-log schema change and adds no drift-guarded contract. Console output remains, but is **not** the system of record.

This is load-bearing for a reason outside this plan: **BACKLOG #204 has to count how often the check fires, and it cannot count what was never written down.** Deferring the measurement therefore made durable recording *more* necessary, not less — a console-only advisory would have quietly guaranteed its own follow-up could never be performed. Skips are recorded for the same reason: a check that skipped on a dirty tree and a check that ran and stayed silent are indistinguishable in a rate calculation unless both are on the record.

**Opt-out shape: per-step only (step 8).** Two surfaces, deliberately not three. The `--no-characterization-check` flag on `plan-tool run` suppresses the check for one invocation, and a per-step `enforce_characterization_check: false` records a **durable, reviewable** exemption for a step whose tests legitimately cannot run pre-change — mirroring the sibling test-authoring gate's `enforce_test_authoring: false`, including its tri-state `Optional[bool] = None` default. There is deliberately **no plan-level toggle**: plan-wide suppression is already served by the CLI flag and by the check being `refactor`-only, and a third surface would add a way to silence the check without recording *why*. The per-step field is the only one that carries that information, and an exemption worth keeping is worth reviewing in the plan file.

**Which steps are checked.** `refactor` steps only. `feature` steps are **never** checked — their tests legitimately fail pre-change, which is the point of the contract's other half — and `non-code` steps have no test contract at all.

**Open design calls to settle during authoring.**

1. **Default-on for refactor steps, or opt-in behind a flag?** The cost is one worktree (~200–500 ms plus disk) and one targeted test run per refactor step. Recommendation: on by default for refactor steps *because* it is scoped that narrowly, with an opt-out.
2. **Which changed test files count.** The whole post-call test delta is the cheap answer and the one to start with; whether characterization cases can be distinguished from new-structure tests within a file is the harder question and should not block a first version.

**Suggested decomposition** (a starting shape, not a fence — let the audit re-decompose it): (1) the pre-step SHA capture and the clean-tree precondition, with its skip-and-explain path; (2) the pre-change verification run itself — worktree, copy, targeted run, guaranteed cleanup; (3) the advisory finding surface and its calibration; (4) docs and the BACKLOG #203 close-out.

## Input

The check consumes four existing contracts and writes no new one. Three are consumed unchanged; the fourth (`test_command`) is **expanded** by step 2 in a backward-compatible way — a new optional placeholder in a field that already ships, not a parallel field:

- **`test_command` and its runner** (`plan_tool/schema.py`, documented in `PLAN_FORMAT.md`, executed by `plan_tool/launcher.py`'s `_run_test_gate` with `shell=True` and a caller-supplied cwd). Step 2 adds an optional `{files}` placeholder so the same command can name the copied files; absent the placeholder the check skips. Reusing this keeps **one** shell-execution surface rather than adding a second beside `test_command` and `steps[].gate`, and inherits the runner's timeout, output-tail capture, and non-raising failure handling. Its blocking semantics are **not** inherited — the caller decides what a non-zero rc means. **Consumed by injection, not import:** `launcher` passes the runner and the command template into the check, which imports nothing from `launcher` (see the runner-injection constraint in Architecture).

- **`plan_tool/launcher.py`'s post-call git-changed delta** (the test-authoring gate's file set) supplies the step's new/changed test files. What is depended on is the *set of changed paths* the gate already computes post-call. The gate's pre-call baseline is a **path set, not a commit SHA** — it cannot supply the pre-change source, so the SHA capture is a new value taken alongside it, not a reuse of it. The gate's known limit carries over: on a dirty tree, edits to an already-dirty file fall inside the baseline and are masked out of the delta.
- **`plan_tool/cli/gitcommit.py`'s worktree primitives** — `worktree_add`, `worktree_list`, `worktree_remove`, `worktree_prune`. All four are non-raising; the three mutating ones return `(rc, tail)` and `worktree_list` returns `list[WorktreeEntry]` (`[]` on failure). No new git plumbing is written against them; the sole change is step 1's additive detached-checkout option on `worktree_add`, which existing callers do not see.
- **`plan_tool/worktree.py`'s path derivation** — `worktree_base` and `derive_worktree_path`, which keep the worktree base a **sibling** of the repo, never inside it.

Also read, not written: the step's `change_type` (`refactor` / `feature` / `non-code`) selects whether the check runs at all, and `plan_tool/review.py`'s `APPLY_ELIGIBLE_SOURCES` is the membership list the new finding source must stay **out of**.

**Limit on verifying these contracts.** The pre-change source is only what the captured SHA holds, so the check's conclusion is sound only under the clean-tree precondition; on a dirty tree the contract cannot be verified and the check skips rather than concluding.

## References

- [Git - git-worktree Documentation](https://git-scm.com/docs/git-worktree) — Official reference for `worktree add/list/remove/prune`, including the same-branch-checkout restriction, detached-HEAD checkout of a commit-ish, and what `prune` reclaims — the exact primitives the pre-change verification run drives via `gitcommit.py`.
- [Git - git-rev-parse Documentation](https://git-scm.com/docs/git-rev-parse) — Plumbing reference for resolving a revision to a raw SHA, needed to capture the pre-change commit at step start and to feed that SHA as the worktree's start point.
- [Git - git-status Documentation](https://git-scm.com/docs/git-status) — Specifies the `--porcelain` / `-z` machine-parseable formats and their backwards-compatibility guarantee — the sound way to implement the clean-tree-at-step-start precondition that decides between checking and skipping-with-reason.
- [Git - git-diff Documentation](https://git-scm.com/docs/git-diff) — Documents `--name-only`, `--name-status`, and `--diff-filter` selectors used to collect the step's new/changed test files as the post-call git-changed delta that gets copied into the worktree.
- [How to invoke pytest — pytest documentation](https://docs.pytest.org/en/stable/how-to/usage.html) — Canonical reference for running only specified test files/node ids and for pytest's exit-code table, which is how the check distinguishes a red run from an uncollectable one when running the copied tests against pre-change source.
- [pytest import mechanisms and sys.path/PYTHONPATH — pytest documentation](https://docs.pytest.org/en/stable/explanation/pythonpath.html) — Explains rootdir, `--import-mode` (prepend/append/importlib), and package-root inference — essential because copied test files execute under a different working copy and must import the worktree's source, not the main tree's.
- [Changing standard (Python) test discovery — pytest documentation](https://docs.pytest.org/en/stable/example/pythoncollection.html) — Covers collection and `conftest.py` loading relative to the test path, plus `--collect-only`, which is the cheapest way to detect the 'cannot even be collected pre-change' case the plan requires to be reported distinctly.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- **`feature` steps.** Their tests legitimately fail pre-change.
- **Blocking on the finding before precision is measured.**
- **Coverage measurement or thresholds; blanket mutation testing.**
- **Reordering how `--commit` commits.** The concealment is context for why this check is needed, not a thing to fix here.
- **BACKLOG #202's claim-to-test matching.** Separate entry, separate mechanism.
- **Editing, patching, or import-stripping the copied test files.**
- **New git plumbing.** The worktree primitives in `plan_tool/cli/gitcommit.py` and the path derivation in `plan_tool/worktree.py` already ship. Step 1 adds exactly one **additive** option to `worktree_add` — detached checkout, which the primitive cannot express today (it takes a `branch` on both arms) and which this check requires, since the sandbox checks out a bare commit rather than a branch. Nothing beyond that: no new primitive, no new subprocess call site, no change to any existing caller's behavior.

## Risks

- **False alarms on tests that legitimately need new fixtures.** Mitigation: advisory-only, and the finding text must state that a new-fixture dependency is a plausible benign cause.
- **Sandbox cost per refactor step, which is dominated by the *environment*, not the worktree.** `git worktree add` is the cheap part (~200–500 ms plus disk). The expensive and previously unstated part is that a fresh worktree carries **no interpreter environment** — `.venv` is gitignored, so a command like `uv run pytest` resolves and builds an environment there before a single test executes, which can dwarf the worktree cost. Mitigation: refactor-only scope, targeted file selection, and an opt-out. **Open, and deliberately not measured inside this plan** (carved out 2026-07-30 to BACKLOG #204): whether the sandbox can borrow the main tree's already-resolved environment while taking only its *source* from the worktree. If it cannot, and a full environment build is required per refactor step, the per-step advisory shape may be untenable and the check belongs behind an explicit opt-*in* instead. **This plan ships the check with that question open** — the cost is real and unquantified at merge, which is the accepted trade of deferring the measurement.
- **Leaked worktrees on an error path.** Mitigation: cleanup in a `finally`, and a prune on entry — this is the one failure that leaves durable mess behind. `git worktree remove` refuses an unclean worktree, so removal must tolerate that rc and fall through to `worktree prune`, which clears the stale `$GIT_DIR/worktrees` administrative entry.
- **A dirty tree silently invalidating the pre-change baseline.** Without `--commit`, the captured SHA is missing earlier uncommitted steps, so a failure there says nothing about test ordering. Mitigation: require a clean tree at step start and *skip with a stated reason*, emitting no finding.

## Testing

Cross-cutting guidance, unit-first per the project convention (`TESTING.md`; `plan_tool/X.py` → `tests/test_X.py`):

- **Default to unit tests** over the check's decomposable pieces — the `refactor`-only step selector, the clean-tree precondition and its skip-and-explain path, the changed-test-file selection, and the finding's calibration (source string, `info` severity, absence from `review.py`'s `APPLY_ELIGIBLE_SOURCES`). Each of these is answerable without spawning git or pytest.
- **Stub the git primitives.** `worktree_add`, `worktree_list`, `worktree_remove`, and `worktree_prune` are non-raising and return `(rc, tail)` / `list[WorktreeEntry]`, so their failure and success shapes are cheap to fake; a unit test asserting cleanup-on-every-path should drive an injected failure through each error branch and assert removal + prune still ran.
- **Reserve `@pytest.mark.integration`** (class level) for the cross-module wiring only: driving a `run` step end-to-end far enough to prove the pre-step SHA capture, the post-call delta hand-off, and the advisory finding surface connect. A unit test on any single piece would miss a mis-wired hand-off between them.
- **Hermetic and non-spawning.** Tests own their `tmp_path`, and none may spawn the real backend — `tests/conftest.py`'s autouse gate raises if a registered backend binary is launched. The pre-change test run itself must be seam-injected rather than shelling out to a real pytest in a real worktree.
- **Existing suites that must still pass**: `tests/test_launcher.py` (the test-authoring gate's pre-call baseline is adjacent to the new SHA capture — it must be unchanged by it), `tests/test_review.py` (the `APPLY_ELIGIBLE_SOURCES` membership contract), `tests/test_worktree.py` and the `gitcommit` worktree-primitive tests, and `tests/test_data_contract.py` if the finding's persisted shape touches a drift-guarded schema. Run the full suite (`uv run pytest tests/ -q`) before close-out.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — unit tests added with the implementation; green before completion.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (feature) — unit tests added with the implementation; green before completion.
- step 5 (feature) — unit tests added with the implementation; green before completion.
- step 6 (feature) — unit tests added with the implementation; green before completion.
- step 7 (feature) — unit tests added with the implementation; green before completion.
- step 8 (feature) — unit tests added with the implementation; green before completion.
- step 9 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- A characterization suite that passes against pre-change code is **silent**.
- A test suite **coupled to the refactor's output** is **flagged** — one that references a symbol, module, or signature the step created or renamed, so it cannot run against pre-change source. A step whose "refactor" actually changed behavior is flagged for the same reason: its tests describe the new behavior and fail pre-change.
- **What the check does *not* catch, stated so no one reads more into it than it delivers:** a test written *after* a genuinely behavior-preserving refactor, in terms of symbols that already existed, passes against pre-change source and the check stays **silent**. That is not a defect in the mechanism — it is what behavior-preservation *means*. What the re-run proves is that the tests **describe pre-change behavior**; it does not and cannot prove they were **authored** before the change. Ordering is unobservable after the fact; behavioral scope is observable, and that is what is being pinned.
- A test file that cannot be *collected* pre-change is **flagged**. The message distinguishes "could not be collected" from "ran and failed" **when the runner makes that observable** — pytest separates them by exit code (`2` for a collection/usage error, `1` for test failures), so a pytest-shaped `test_command` gets the split. An arbitrary configured command returns non-zero for both, and there the finding reports "did not pass against pre-change source" without claiming a distinction it cannot see. The check never infers the cause from output text.
- A `feature` step is **never** checked; a `non-code` step is never checked.
- A dirty tree at step start **skips** the check with a stated reason and emits **no** finding.
- The finding never flips an exit code and is never apply-eligible (it stays out of `review.py`'s `APPLY_ELIGIBLE_SOURCES`, so it can never reach `apply_finding`).
- The copied test files are run unmodified — no edit, patch, or import-strip is applied to force a green.
- Every outcome — flagged, silent, **and skipped-with-reason** — is appended to the step's run log, so BACKLOG #204 has a countable record. A console-only outcome fails this criterion.
- A step carrying `enforce_characterization_check: false` is **never** checked, and that exemption travels with the plan file rather than depending on an operator remembering a flag. There is **no** plan-level toggle.
- Worktrees are removed on every path, including failures — and a **prune runs on entry** as well as on exit, so a prior run's leaked administrative entry cannot block the next sandbox.
- A leftover sandbox directory at the derived path is **removed and recreated, never reused**, so a second run of the same plan (or a run following an interrupted one) does not collide.
- `BACKLOG.md` #203 is reconciled per the lifecycle note: mark #203 plan-authored while execution is pending and remove it only after the check ships; leave **#202** in place.

**Stop condition — retained in full, but deliberately *not evaluated by this plan*.** If most real characterization files cannot run pre-change for legitimate reasons, that means the contract itself needs restating before it can be mechanized at all — a design finding, not a precision-tuning problem, and never grounds for loosening what counts as a pass.

**Recorded deviation from BACKLOG #203's scope contract (decided 2026-07-30; do not re-open without revisiting this paragraph).** That contract said *"do not skip the measurement."* This plan skips it: the measurement was carved out to **BACKLOG #204** so the check could ship without close-out blocking on field data that does not exist yet. The consequence is explicit — **the check ships before its own stop condition has ever been evaluated.** If #204 later finds the rate is high, the remedy is to restate the contract and reconsider the check's default, *not* to relax the check. Step 9 reconciles #203 on the basis of the mechanism shipping; it does **not** claim the stop condition was cleared.

## Deferred

- Promoting the finding from advisory to blocking (needs measured precision).
- Distinguishing characterization cases from new-structure tests *within* one file.
- Any equivalent contract check for `feature` steps.
