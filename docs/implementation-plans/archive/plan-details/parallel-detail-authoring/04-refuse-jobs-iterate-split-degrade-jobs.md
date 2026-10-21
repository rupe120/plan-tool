> **Auto-archived**: this plan was swept on 2026-07-04 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Refuse `--jobs > 1` with `--iterate`/`--split`, degrade `--jobs > 1 --step` to serial

## Summary

Add a CLI-level guard in `plan_tool/cli/authoring.py:cmd_detail` that refuses `--jobs > 1` when either plan-structure-mutating mode is on — `--iterate` (the convergence loop re-reads the live plan each pass) or `--split` (the post-loop split renumbers steps) — exiting `2` with a message naming which flag to drop. Separately, when `--jobs > 1` is combined with a single-step run (`--step N`), there's no parallelism to gain, so the run degrades to serial: it warns and passes `jobs=1` into `generate_detail` instead of erroring. Both flags default ON (step 3 added `--jobs`; `--iterate` and `--split` already default ON in the `detail` subparser), so the only way to actually run parallel authoring is `--jobs N --no-iterate --no-split` across the full step set. On green: `plan-tool detail <plan> --jobs 4` exits `2` (iterate on), `--jobs 4 --no-iterate --no-split --step 2` runs serially with a warning, and `--jobs 4 --no-iterate --no-split` reaches `generate_detail(jobs=4)`.

## Table of Contents

- [Why](#why) — why the refusal and the degrade belong at the CLI, not deeper
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files this step touches
- [Implementation](#implementation) — the guard placement, the refuse vs degrade split, the normalized `jobs` value
- [Tests](#tests) — refuse on iterate, refuse on split, degrade on single-step, allow when all clear
- [Test-creation order (feature step)](#test-creation-order-feature-step) — green-before-done gate for the new guard tests
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — argparse docs for the namespace attrs this reads
- [Deferred](#deferred) — step 2's deep guard, the `run`/`create` knobs, worker logic left elsewhere

## Why

Step 3 wired `--jobs N` into `cmd_detail` and threads it into `generate_detail`. Step 2 already raises `DetailError` inside `generate_detail` when `jobs > 1` meets the `--iterate` convergence loop (the in-loop `escalate_to_split` renumbers steps out from under workers holding step snapshots), and `cmd_detail`'s `except DetailError` arm turns that into `rc=2`. Two gaps remain. First, `--split` (also default ON) drives a plan-structure-mutating path the operator shouldn't be allowed to combine with parallelism either, and its refusal isn't wired anywhere yet. Second, `--jobs > 1 --step N` is a nonsense combination — one step can't be parallelized — and today it would silently spin up a pool of one. This step closes both at the CLI: it makes the refusal explicit and operator-facing (a clean usage error naming the conflicting flag, per the "raise naming the conflict, don't silently serialize" rule), and it degrades the single-step case to serial with a warning rather than pretending to parallelize.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/authoring.py` — add the `--jobs`-conflict guard in `cmd_detail`, placed beside the existing early dispatch guards (the `--all requires --reconcile` block and the `--commit` clean-tree block); compute a normalized `jobs` value and pass it into the `generate_detail(...)` call where step 3 added `jobs=args.jobs`.
  - `tests/cli/test_authoring_cmds.py` — add a guard test class covering the iterate-refuse, split-refuse, single-step degrade, and all-clear paths.

## Implementation

**Where the guard lives.** Add the check inside `plan_tool/cli/authoring.py:cmd_detail`, in the early-guard run of `error(...) → return 2` blocks that already sit before the run log opens — right after the `--all requires --reconcile` guard and near the `--commit` clean-tree guard. The `--reconcile` early-return happens first (line near `if getattr(args, "reconcile", False):`), so this guard only sees the authoring path; that's correct — `--jobs` has no meaning on the reconcile audit path.

**Refuse on iterate or split (error, `rc=2`).** When `args.jobs > 1` and either `--iterate` or `--split` is on, call `error(...)` and `return 2`.
- Read the flags with `getattr(args, "iterate", True)` and `getattr(args, "split", False)` — match the existing `getattr` defaults already used at the `generate_detail` call (`allow_split=getattr(args, "split", False)`). The `iterate` namespace attr comes from the `--iterate` `BooleanOptionalAction` in `register`.
- The message must name the conflict and the way out — tell the operator to re-run with `--no-iterate --no-split`, or drop `--jobs`. One way: name whichever flag(s) are actually on so the message is specific (e.g. "`--jobs > 1` cannot combine with `--iterate`"). Keep it one line, like the sibling guards.
- This is the operator-facing usage error. It fires before `generate_detail`, so step 2's deep `DetailError` guard never triggers from this path — that guard stays in place as defense for direct `generate_detail` callers and tests; **do not remove it** (it is owned by step 2).

**Degrade the single-step case (warn, proceed serial).** When `args.jobs > 1` and `args.step is not None` (and the refuse guard above didn't fire — i.e. iterate and split are both off), there's exactly one step to author, so parallelism buys nothing.
- Call `warn(...)` (imported from `plan_tool.style` alongside `error`) noting the degrade, and run serially.
- Do **not** error here — this is a soft normalization, not a conflict. The distinction is deliberate: iterate/split are incompatible modes (error); a single-step parallel request is merely pointless (degrade). This matches the title's two verbs — *refuse* vs *degrade*.

**Carry the normalized value into `generate_detail`.** Step 3 passes `jobs=args.jobs` into the `generate_detail(...)` call. Change that to pass a normalized local — e.g. compute `jobs = 1 if (args.jobs > 1 and args.step is not None) else args.jobs` after the refuse guard, and pass `jobs=jobs`. Don't mutate `args.jobs` in place if you can avoid it (the run-log flags dict and any later read should see the operator's requested value); a local keeps the requested-vs-effective distinction clean.
- Constraint: the refuse guard must run **before** the degrade computation, so `--jobs 4 --step 2` (iterate still on by default) errors `rc=2` rather than degrading — iterate-refuse outranks the single-step degrade.

**Emit the un-converged-pass terminal warning.** After a `--jobs > 1` authoring run completes (effective `jobs > 1` — i.e. the refuse guard didn't fire and the single-step degrade didn't normalize it to 1), print a terminal warning before `cmd_detail` returns, naming the authored bodies as an intentionally **un-converged first pass** and printing the exact follow-up: `plan-tool detail <plan> --iterate`. The only runnable parallel invocation is `--no-iterate --no-split`, so a parallel run by construction skips the convergence loop; the project's always-`--iterate` mandate means the operator must not be left thinking the fast pass is finished work. Gate it on the *effective* jobs value (the normalized local, not `args.jobs`) so a degraded single-step run — which actually ran serial — does not print it. This is advisory output only; it must not change the return code (exit-code convention). Place it after the `generate_detail` call returns successfully, alongside the existing "Next steps" rendering.

**Why CLI *and* deeper (two layers).** Step 2's in-function guard raises on `jobs > 1` for **both** the `budget.enabled` (iterate) **and** the `allow_split` arms — the post-loop Phase-B `escalate_to_split` renumbers steps against siblings already authored under the old numbering, so a direct `generate_detail(jobs > 1, allow_split=True)` caller must be protected even with iterate off. That in-function guard is the defense-in-depth backstop. This step's CLI guard is the **operator-facing front door**: it fires *first* in `cmd_detail`, before `generate_detail` is called, with a clean usage error naming the conflicting flag (`--iterate`/`--split`) and the way out — far friendlier than letting step 2's `DetailError` surface as a generic `rc=2`. The two are complementary, not redundant: keep both. (This reconciles with the Architecture "Mutual exclusion" guard, which the audit corrected to raise on both arms.)

## Tests

All tests live in `tests/cli/test_authoring_cmds.py`, driven through `main(argv)` on a `registered_plan`, matching the existing `TestDetailDispatchGuards` and `TestDetailCommitCmd` conventions. The refuse tests halt at the guard before any `generate_detail` boundary call (no claude); the degrade and all-clear tests monkeypatch `authoring.generate_detail` with a fake that records the `jobs` kwarg (the `fake_gen` pattern already used by `TestDetailCommitCmd`).

- `test_jobs_gt_one_with_iterate_rejected` — `detail demo --jobs 4` (iterate default on) returns `2`; stderr names `--iterate`.
- `test_jobs_gt_one_with_split_rejected` — `detail demo --jobs 4 --no-iterate` (split default on) returns `2`; stderr names `--split`.
- `test_jobs_gt_one_no_iterate_no_split_allowed` — `detail demo --jobs 4 --no-iterate --no-split` reaches the fake `generate_detail` with `jobs == 4`; rc reflects the fake's result.
- `test_jobs_gt_one_with_step_degrades_to_serial` — `detail demo --jobs 4 --no-iterate --no-split --step 2` calls the fake `generate_detail` with `jobs == 1` and emits a warning to stderr; rc is not `2`.
- `test_jobs_one_is_unaffected` — `detail demo` (default `--jobs 1`) reaches `generate_detail` with `jobs == 1` and no warning (guards are no-ops at `jobs == 1`).
- `test_jobs_gt_one_step_with_iterate_still_rejected` — `detail demo --jobs 4 --step 2` (iterate on) returns `2`, proving the refuse guard outranks the single-step degrade.
- `test_jobs_gt_one_emits_unconverged_warning` — `detail demo --jobs 4 --no-iterate --no-split` prints a terminal warning naming the bodies as an un-converged first pass and the `--iterate` follow-up command; rc is unchanged (the warning never flips the exit code).
- `test_degraded_single_step_no_unconverged_warning` — `detail demo --jobs 4 --no-iterate --no-split --step 2` (effective `jobs == 1`) does **not** print the un-converged warning, since it actually ran serial.

### Test-creation order (feature step)

This is a **feature** step. Write the guard tests alongside the guard edit:
1. Add the refuse + degrade block and the normalized `jobs` pass-through in `cmd_detail`.
2. Add the test class to `tests/cli/test_authoring_cmds.py`.
3. Green-before-done gate: every new test above must pass, and the existing `TestDetailDispatchGuards` / `TestDetailCommitCmd` tests must stay green (the new guard sits beside theirs and must not perturb their paths).

## Acceptance criteria

- `plan-tool detail <plan> --jobs 4` (defaults: iterate on, split on) exits `2` and prints an error naming `--iterate`.
- `plan-tool detail <plan> --jobs 4 --no-iterate` exits `2` and prints an error naming `--split`.
- `plan-tool detail <plan> --jobs 4 --no-iterate --no-split` calls `generate_detail` with `jobs=4`.
- `plan-tool detail <plan> --jobs 4 --no-iterate --no-split --step 2` calls `generate_detail` with `jobs=1`, prints a warning, and does not exit `2`.
- `plan-tool detail <plan> --jobs 4 --step 2` (iterate on) exits `2` — the iterate refuse outranks the single-step degrade.
- `plan-tool detail <plan>` (default `--jobs 1`) is unchanged: no warning, `generate_detail` receives `jobs=1`.
- A completed `--jobs 4 --no-iterate --no-split` run prints a terminal warning naming the bodies as un-converged and the `plan-tool detail <plan> --iterate` follow-up; rc is unaffected. A degraded single-step run (effective `jobs=1`) prints no such warning.
- All new tests in `tests/cli/test_authoring_cmds.py` pass; existing authoring-guard tests stay green.

## References

- [argparse — Parser for command-line options and subcommands — Python documentation](https://docs.python.org/3/library/argparse.html) — for how `--iterate`/`--split` `BooleanOptionalAction` flags and `--jobs`/`--step` land on the `args` namespace this guard reads.

## Deferred

- The deep `jobs > 1 + budget.enabled` guard inside `generate_detail` — owned by step 2; this step adds the CLI usage error in front of it and does not remove or change it.
- Any change to `--jobs` parsing/threading — owned by step 3; this step only reads `args.jobs` and normalizes the value passed onward.
- Parallel-authoring worker logic (`ThreadPoolExecutor` dispatch, the serial tail) — owned by steps 1–2 in `plan_tool/detail.py`, outside this step's files.
- A `--jobs` knob on `run`/`create` — out of scope; this plan parallelizes `detail` authoring only.
