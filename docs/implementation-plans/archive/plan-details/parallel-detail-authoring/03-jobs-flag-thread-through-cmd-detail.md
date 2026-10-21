> **Auto-archived**: this plan was swept on 2026-07-04 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Add the `--jobs N` flag and thread it through `cmd_detail` into `generate_detail`

## Summary

Add a `--jobs N` flag to the `detail` subparser and pass its value into the `generate_detail` call inside `cmd_detail`. Both live in `plan_tool/cli/authoring.py`. The flag is `type=int, default=1`; at `default=1` the call is identical to what it is today, so every existing detail run is unchanged. At `N > 1` the value reaches `generate_detail`'s `jobs` parameter (added by step 2), which overlaps the per-step authoring calls. Step 2 owns the mutual-exclusion guard that raises `DetailError` when `jobs > 1` meets the `--iterate` convergence loop; `cmd_detail`'s existing `except DetailError` arm already turns that raise into `rc=2`, so this step adds no new guard — it only wires the flag and records it in the run-log flags. `--split` (also default ON) is the other half of the refused plan-structure-mutating combination, but its CLI refusal is owned by step 4, not this step — so the `--no-iterate` examples below still leave `--split` set, and step 3 wires only the flag, not the `--split` refusal. On green: `plan-tool detail <plan> --jobs 4 --no-iterate` runs up to 4 authoring calls concurrently; `plan-tool detail <plan> --jobs 4` (iterate still on by default) exits 2 with the conflict message from step 2's guard.

## Table of Contents

- [Why](#why) — why the CLI needs to expose the `jobs` knob now
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files this step touches
- [Implementation](#implementation) — the argparse flag, the threaded kwarg, the iterate/reconcile interactions
- [Tests](#tests) — flag-parse default, threading, the iterate conflict surfacing
- [Test-creation order (feature step)](#test-creation-order-feature-step) — the green-before-done gate for the new wiring tests
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — the argparse docs for this flag
- [Deferred](#deferred) — the `run`/`create` knobs and the worker logic left to other work

## Why

Step 1 extracted the per-step authoring worker and step 2 added the `jobs: int = 1` parameter to `plan_tool/detail.py:generate_detail` that overlaps those worker calls when `jobs > 1`. Both are function-level changes — no operator can reach the new path yet because `cmd_detail` always calls `generate_detail` without a `jobs` argument and the `detail` subparser has no flag to set it. This step closes that last gap: it makes the parallelism an operator-visible option. It is deliberately small and low-risk — a flag plus one threaded keyword — so the concurrency machinery (step 2) and its operator entry point (this step) land as separate, independently reviewable diffs.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/authoring.py` — add the `--jobs` argument to the `detail` subparser (in `register`, beside the other `p_detail.add_argument(...)` calls); pass `jobs=args.jobs` into the `generate_detail(...)` call in `cmd_detail`; add `"jobs"` to the `RunLogWriter.start(...)` `flags` dict in `cmd_detail`.
  - `tests/cli/test_authoring_cmds.py` — add wiring tests: the flag parses with the right default, the value threads into `generate_detail`, `--jobs 0`/`-1` is rejected with `rc=2` before `generate_detail` is called, and the `jobs > 1` + default-`--iterate` conflict surfaces as `rc=2`.

## Implementation

**Add the flag to the `detail` subparser.** In `plan_tool/cli/authoring.py:register`, add one `p_detail.add_argument("--jobs", ...)` next to the existing `p_detail` flags (e.g. near `--step`, which is the other `type=int` option on this parser).
- Use `default=1, dest="jobs"` and a custom `type=` callable (e.g. `_positive_int`) that parses the value and **rejects `< 1` as a usage error** — `--jobs 0` and `--jobs -1` exit `2` with an argparse error message. There is **no `0`/auto mode** and no `os.cpu_count()`-derived default: the operator must name an explicit `N >= 1`. This is the deliberate "no magic concurrency" decision — keeping the flag explicit means the tool never silently picks a worker count that could fan out many `claude` subprocesses. Use `argparse.ArgumentTypeError` (raised from the `type=` callable) so the message renders through argparse's standard `prog: error: argument --jobs: ...` formatting, consistent with other bad-value errors.
- Write the help text to name the two facts an operator needs: `N` is the max authoring calls in flight (an explicit integer `>= 1`), and `N > 1` requires `--no-iterate` (it conflicts with the convergence loop — see below). One way to phrase it: *"run up to N per-step authoring calls concurrently (explicit integer >= 1; default 1 = serial). N>1 requires --no-iterate; it is incompatible with the --iterate convergence loop."*

**Thread the value into the orchestrator.** In `cmd_detail`, the single `generate_detail(...)` call already passes a long list of keyword arguments built from `args`. Add `jobs=args.jobs` to that call. This is the only behavioral wiring in the step. Because step 2 defaults `generate_detail`'s `jobs` to 1, passing `args.jobs` (default 1) leaves the serial path selected unless the operator opts in.

**Record the knob in the run log.** `cmd_detail` opens `RunLogWriter.start(...)` with a `flags={...}` dict that currently carries `force`, `dry_run`, `no_lessons`, `no_resume`, `commit`. Add `"jobs": args.jobs` so a run's parallelism is captured for later inspection, consistent with the other tuning flags recorded there.

**Do not add a CLI-level guard for the iterate conflict — let step 2's guard surface.** Step 2 owns the rule that `jobs > 1` with `budget.enabled` (the `--iterate` convergence loop) raises `DetailError` naming the conflict, because the in-loop `escalate_to_split` renumbers steps out from under the held worker snapshots. `cmd_detail` already wraps the `generate_detail` call in `try: ... except DetailError as exc:` that prints the message and sets `rc = 2`. So the conflict is surfaced for free through the existing arm — adding a second guard in `cmd_detail` would duplicate step 2's predicate and risk drifting from it.
- **Consequence to call out in help text:** `detail` defaults `--iterate` ON (via `p_detail_mode`'s `BooleanOptionalAction` default `True`), so the bare `plan-tool detail <plan> --jobs 4` hits the guard. The operator must pass `--no-iterate` alongside `--jobs N` for `N > 1`. This is the deliberate "raise, don't silently serialize" design from step 2 — the help text makes it discoverable so the rc=2 isn't a surprise.

**`--split` is the other half of the refused combination — but step 4 owns its CLI refusal, not this step.** `--split` defaults ON (`p_detail`'s `--split` `BooleanOptionalAction default=True`), so the headline `plan-tool detail <plan> --jobs 4 --no-iterate` still leaves `--split` set, and `--no-iterate` alone does not disable it. The plan couples both modes (step 4 = "Refuse --jobs > 1 with --iterate/--split"; Architecture §"Mutual exclusion with plan-mutating modes"): step 2's worker dispatch tolerates `--split` only serially (its Phase-B purity check / `escalate_to_split` renumbers steps and cannot run under concurrent workers), and the CLI-level refusal of `--jobs > 1` with `--split` is step 4's job. This step wires only the flag and the threaded kwarg — it adds no `--split` refusal and assumes none yet exists, so the help text above names only the `--iterate` conflict (step 4 extends it to `--split`).

**`--reconcile` does not reach the authoring path.** When `args.reconcile` is set, `cmd_detail` returns early through `app._cmd_detail_reconcile(...)` before the `generate_detail` authoring call, so `--jobs` has no effect on the reconcile audit. That's acceptable (the reconcile path has its own one-call-per-step sweep), but the value is silently ignored there rather than rejected — note it in the help text or leave it to Deferred; do not add a `--jobs --reconcile` rejection in this step.

**Constraints that must hold:**
- `generate_detail`'s public signature gains only the `jobs` keyword (step 2); `cmd_detail` passes it by keyword, matching every other argument in that call. No positional coupling.
- At `args.jobs == 1` the `generate_detail` call must be observably identical to today (same kwargs, same serial loop). The default-1 path is the regression guarantee for every existing `detail` test.

## Tests

All in `tests/cli/test_authoring_cmds.py`, driven through `main(argv)` on a registered plan, no claude invoked. Follow the existing pattern in this file that patches `plan_tool.cli.authoring`-level globals (e.g. the `split_step` tests patch `authoring.split_step`) — here patch `authoring.generate_detail` with a fake that captures kwargs and returns a `list[DetailResult]`.

- `test_jobs_defaults_to_one` — `plan-tool detail <plan>` (no `--jobs`) calls `generate_detail` with `jobs == 1`.
- `test_jobs_threads_into_generate_detail` — `plan-tool detail <plan> --jobs 4 --no-iterate` calls `generate_detail` with `jobs == 4`.
- `test_jobs_zero_rejected` — `--jobs 0 --no-iterate` exits `2` (the custom `type=` rejects `< 1`); `generate_detail` is never called. Same for `--jobs -1`.
- `test_jobs_recorded_in_run_log_flags` — after a `--jobs 2 --no-iterate` run, the run-log flags dict carries `jobs == 2` (assert against the written run-log JSONL, or capture the `RunLogWriter.start` flags via the fake).
- `test_jobs_with_default_iterate_conflicts` — `plan-tool detail <plan> --jobs 4` (iterate left at its ON default) exits `2`. Drive this with a fake `generate_detail` that raises `DetailError("...iterate...")` to confirm `cmd_detail`'s `except DetailError` arm returns `rc=2` and prints the message; the real conflict predicate is step 2's and is tested in `tests/test_detail.py`.

### Test-creation order (feature step)

This is a **feature** step. Write the five tests above alongside the flag wiring:
1. Add the `--jobs` argument and the `jobs=args.jobs` threading first.
2. Add `test_jobs_defaults_to_one`, `test_jobs_threads_into_generate_detail`, `test_jobs_zero_passes_through` — they pin the parse + threading contract.
3. Add the run-log flag and `test_jobs_recorded_in_run_log_flags`.
4. Add `test_jobs_with_default_iterate_conflicts` to pin the conflict-surfacing path.

Green-before-done gate: all five new tests pass, and the existing `tests/cli/test_authoring_cmds.py`, `tests/test_detail.py`, and the detail happy-path suites stay green (the default-1 path proves no behavior change).

## Acceptance criteria

- `plan-tool detail --help` lists `--jobs N` with default `1` and help text naming the explicit-`>= 1` requirement.
- `cmd_detail` passes `jobs=args.jobs` into its `generate_detail(...)` call.
- `plan-tool detail <plan>` (no flag) reaches `generate_detail` with `jobs == 1`.
- `plan-tool detail <plan> --jobs 4 --no-iterate` reaches `generate_detail` with `jobs == 4`.
- `plan-tool detail <plan> --jobs 0` (and `--jobs -1`) exits `2` with an argparse usage error; `generate_detail` is never called (no `0`/auto mode).
- `plan-tool detail <plan> --jobs 4` (iterate at default ON) exits `2` via the existing `except DetailError` arm.
- The `detail` run-log flags dict includes `"jobs"` with the run's value.
- The five new tests in `tests/cli/test_authoring_cmds.py` pass; the existing authoring and detail suites stay green.

## References

- [argparse — Parser for command-line options and subcommands — Python documentation](https://docs.python.org/3/library/argparse.html) — `add_argument` with `type=int`/`default`/`dest`/`help` for the new `--jobs` option on the `detail` subparser.

## Deferred

- The `jobs` parameter, the concurrent `ThreadPoolExecutor` dispatch, and the `jobs > 1` + `--iterate` mutual-exclusion guard — owned by step 2 in `plan_tool/detail.py:generate_detail`; this step only exposes the value.
- A `--jobs` flag on `run` or `create` — out of scope; this plan parallelizes detail authoring only.
- Rejecting `--jobs N --reconcile` — the reconcile path returns before the authoring call so the value is ignored there; no rejection is added in this step.
- Refusing `--jobs > 1` with `--split` — `--split` defaults ON and is the other half of the refused plan-structure-mutating combination, but its CLI refusal (and the extended help text) is owned by step 4, not wired here.
- Auto-defaulting `--iterate` OFF when `--jobs N (>1)` is passed — not done; the design is to raise on the conflict (step 2) and require an explicit `--no-iterate`, not to silently flip iterate off.
