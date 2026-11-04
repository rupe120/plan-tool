# Resume & recovery — the shared engine

This document maps the **shared resume/recovery machinery** every iterative
command plugs into — the iteration session (SIGINT-safe cleanup + live-edit
drift detection), the crash handler, the checkpoint contract, and the
fail-fast/short-circuit rules. Per-flow specifics
live in the correlating docs:

> - `create --from-existing` resume → [`CREATE_RESUME_FLOW.md`](create.md)
>   (flow: [`CREATE_FROM_EXISTING_FLOW.md`](../pipeline/create-from-existing.md))
> - `detail` resume → [`DETAIL_RESUME_FLOW.md`](detail.md)
>   (flow: [`DETAIL_FLOW.md`](../pipeline/detail.md))
> - `completeness-audit` / `detail --reconcile` resume →
>   [`AUDIT_RESUME_FLOW.md`](audit.md)
>   (flow: [`AUDIT_FLOW.md`](../pipeline/audit.md))

## TL;DR

- **Signal cleanup + drift detection always run.** Every convergence loop wraps
  its body in `iteration_session` (`iteration_lock.py`): it installs a SIGINT
  handler and content-hashes the watched files on entry, then on *every* exit —
  clean stop, early return, Ctrl-C, or an unexpected exception — restores the
  handler and warns about any watched file whose content changed mid-run.
- **Unexpected errors fail clean, not loud.** An unhandled exception is caught
  at the top of `main()`, its traceback is written to
  `.plan-tool/crashes/<label>/<ts>.txt`, and the user sees a one-line message +
  that path instead of a raw stack trace. Exit `1`.
- **Checkpoints memoize claude work** keyed by a content hash, saved **only on
  success**, discarded **only on a clean finish** — so a crash or a fail-fast
  abort preserves them and a re-run skips the cached claude round-trips.
- **Checkpoints cache *claude calls*, not *plan state*.** A checkpoint memoizes
  a claude response so a re-run skips that round-trip — it is **not** a snapshot
  of the edits the loop applied. Those edits live on disk and survive a crash;
  the recovery action is flow-specific. `detail` keeps already-authored steps
  and resumes at the next one, while a published normalized file-backed create
  that stops iteration-incomplete continues with
  `plan-tool completeness-audit <slug> --iterate`. See
  [`CREATE_RESUME_FLOW.md`](create.md) for create route ownership.

## The iteration session (`iteration_session`)

The supported authoring loops (`create_plan`, `generate_detail`, and
`cmd_completeness`) wrap their loop body in the session below. The retained
internal `_iterate_reconcile_loop` helper also uses it, but no current
reconciliation CLI route enables that helper's iteration budget.

```
with iteration_session(repo_root, enabled=..., slug=..., command=...,
                       loop_name=..., watched_paths=..., file_to_step=...) as lock:
    while True:
        ... apply findings / re-author / re-audit ...
```

`iteration_session` (`iteration_lock.py`) is a context manager that:

1. **snapshots** the watched files' SHA-256 content hashes (`acquire_lock`) so
   the end-of-run and mid-iteration drift checks can tell whether the user
   edited an in-scope file while the loop ran;
2. **installs** a SIGINT handler so Ctrl-C cleans up and emits the drift warning
   before unwinding;
3. on **every** exit path (normal, `return`, `break`, or exception unwinding
   through it) runs the `finally`: `emit_drift_warning(release_lock(lock), …)`
   then `restore_sigint_release_handler(…)`.

`enabled=False` (the non-`--iterate` paths) yields `None` and installs nothing;
in-loop drift checks already guard on `lock is not None`.

This is what guarantees a crashed or Ctrl-C'd loop still restores the SIGINT
handler and surfaces any live-edit drift before unwinding.

## The crash handler (`main()`)

`main()`'s dispatch is wrapped in a catch-all *after* the specific handlers
(`FileNotFoundError` / `ManifestError` / `ParseError`/`ValidationError`):

```
except Exception as exc:        # KeyboardInterrupt / SystemExit pass through
    repo_root = args.repo_root (if given) else find_repo_root_from_cwd() else cwd
    save_crash_traceback(repo_root, label, tb_text=traceback.format_exc())
    print clean message + crash-file path + "report this"
    return 1
```

- `save_crash_traceback` (`crash.py`) writes `.plan-tool/crashes/<label>/<ts>.txt`
  best-effort (swallows `OSError`, returns `None`); `<label>` is the plan
  slug/name/command, sanitized so it can't escape the crashes dir.
- The crash file lands in the repo the command **targeted** (`--repo-root` is
  honored first).
- The convergence loop's `iteration_session` `finally` runs *before* the
  exception reaches `main()`, so by the time the handler fires the drift warning
  has been emitted, the SIGINT handler restored, and checkpoints (see below)
  preserved.

## The checkpoint contract

Checkpoints (`checkpoint.py`) memoize an expensive claude response under a
content hash:

- **Key:** `compute_input_hash(...)` over the call's normalized inputs.
- **Save:** `save_checkpoint` runs **only after a fully-successful** parse/validate
  (a broken response is never cached — it would lock the user out of a real
  retry). Runs even under `--no-resume` (primes the cache for next time).
- **Load:** `load_if_valid` returns the payload iff the hash matches **and** it
  isn't older than `DEFAULT_MAX_AGE_SECONDS` (30 days). Miss and stale are
  indistinguishable → fall through to a fresh claude call.
- **Discard:** swept **only on a clean finish**. A crash (exception) skips the
  sweep; a fail-fast stage-failure abort skips it too (see below). Either way the
  checkpoints survive so a re-run resumes the cached stages.

Only `create` and `detail` write checkpoints; `completeness-audit` / `reconcile` do
not. They split their work along two axes: the **deterministic layer**
(file-existence / deps / path-style / coverage / the looks-already-done
heuristic) is re-derived from the on-disk plan on **every** run, while the
**single-claude-call conceptual axis** is reused from a **fingerprint-fresh
saved sidecar** — a separate memoization from checkpoints, gated on the saved
plan **AND** code fingerprints both still matching disk (not on a 30-day TTL).
A plan edit or in-scope code change declines the reuse and re-audits. The
fingerprint-verdict mechanics live in [`AUDIT_RESUME_FLOW.md`](audit.md).

## Fail-fast, repair-retry, and the post-apply short-circuit

Three rules govern how the `create` convergence loop handles a failed stage
(detailed in [`CREATE_RESUME_FLOW.md`](create.md)):

- **Repair-retry:** the create proposal and file-backed preparation paths each
  use their bounded parse/validation repair rules before reporting their
  flow-specific failure result.
- **Post-apply short-circuit:** when an iteration deferred findings and applying
  the eligible ones leaves nothing apply-eligible, the loop stops cleanly
  *before* the fragile re-proposal (which can't fix structural findings anyway).
- **Fail-fast abort:** terminal generic-reference research (after its bounded
  repair) or a failed step re-proposal records `stage_failure`, prints a
  distinct **FAILURE banner**, and preserves checkpoints. The published plan
  remains resumable, so `cmd_create` exits `0` and records
  `iteration_incomplete` in the run log.

## Exit codes (create)

| Code | Meaning |
|------|---------|
| `0`  | published plan, clean convergence, resumable `iteration_incomplete`, or a successful file-backed split proposal |
| `1`  | hard authoring error, including an unexpected crash via the `main()` handler |
| `2`  | usage/input refusal and a selected file-backed `refused` result |

The unmatched-fence and References preflights exit `2` before a file-backed
run record exists. The per-route source, checkpoint, archival, and branch
cleanup rules are in [`CREATE_RESUME_FLOW.md`](create.md).

## Cooperative time-budget (`--time-budget`, #123)

A caller's execution environment often imposes a ceiling — a CI job timeout, a
cron limit, an orchestrating harness's per-command cap. Left to hit it, a long
iterate loop is SIGKILL'd mid-`claude`-call. `--time-budget <sec>` (or
`PLAN_TOOL_TIME_BUDGET`, flag > env > off) is a **cooperative** stop: the loop
finishes the current round, then stops cleanly at the boundary, prints a
`resume with <cmd>` hint, and exits **0** — a clean partial, not a crash.

It is a **hard wall-clock cap**, deliberately distinct from `--iteration-budget`:

| | `--iteration-budget` (`budget_seconds`) | `--time-budget` (`hard_budget_seconds`) |
|---|---|---|
| Anchor | `last_activity_at` (**debounced** — resets on every `touch`/`record_iteration`) | `op_started_at` — stamped once at command entry, **never moves** |
| Means | "no *forward progress* for this long → stop" | "this much *total op wall-clock* → stop, even mid-progress" |
| Stop reason | `deadline_exceeded` | `time_budget_exceeded` |

The `op_started_at` anchor is stamped once (in `_resolve_iterative_budget`, before
the round-0 authoring pass) and rides on the `IterativeBudget`, so it survives the
per-step budget rebuilds `detail` does and measures the **whole op's** elapsed —
not a single loop's. It falls back to the per-loop `ConvergenceState.started_at`
when unset.

A steadily-converging loop never trips `--iteration-budget` but can still blow a
hard ceiling — which is exactly what `--time-budget` catches. The check runs
**last** in `should_continue`, so a natural stop (converged / marginal /
max_iterations) keeps its own reason; the cap only preempts a round that *would
otherwise continue*. **Default off**: with no budget set, no clock is consulted
and behavior is byte-for-byte unchanged.

Covered surfaces (they route through `should_continue`): `create --iterate`,
`detail --iterate` and `completeness-audit --iterate`. Reconcile routes do
not expose an iteration loop; ordinary `run --iterate` has no effect.
Completed rounds are durable at the stop via per-finding annotations, plan
pointers, and `--commit` per-step commits (see
[`DETAIL_RESUME_FLOW.md`](detail.md)). Because the cap is checked
only at round boundaries, a single over-long round (one `claude` call) can still
overrun it — the granularity floor (BACKLOG #124). The `run` per-step batch and the `detail` step-to-step boundary don't yet
consult the cap (BACKLOG #123 follow-up).

## Source map

| Concern | File |
|---------|------|
| Iteration session (drift + SIGINT cleanup) | `plan_tool/iteration_lock.py` (`iteration_session`, `acquire_lock`, `release_lock`, `check_drift`, `install/restore_sigint_release_handler`, `emit_drift_warning`) |
| Crash traceback persistence | `plan_tool/crash.py` (`save_crash_traceback`, `CRASHES_REL`) |
| Top-level crash handler | `plan_tool/cli/app.py` (`main`) |
| Checkpoint primitive | `plan_tool/checkpoint.py` (`compute_input_hash`, `save_checkpoint`, `load_if_valid`, `discard_checkpoint`, `DEFAULT_MAX_AGE_SECONDS`) |
| Convergence budget / stop | `plan_tool/convergence.py` (`ConvergenceState`, `should_continue`) |
| Cooperative time-budget resolution | `plan_tool/cli/context.py` (`_resolve_iterative_budget`, `_resolve_time_budget_seconds`) |
| Fail-fast / short-circuit / exit code | `plan_tool/create.py` (`create_plan`), `plan_tool/cli/authoring.py` (`cmd_create`) |
| Tests | `tests/test_iteration_lock.py`, `tests/test_crash.py`, `tests/test_create.py`, `tests/test_cli.py` |
