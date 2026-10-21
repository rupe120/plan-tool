> **Auto-archived**: this plan was swept on 2026-07-04 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Parallel Detail Authoring
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Extract a per-step detail worker function in generate_detail
  files:
  - plan_tool/detail.py
  - tests/test_detail.py
  complexity: medium
  change_type: refactor
  detail: docs/implementation-plans/plan-details/parallel-detail-authoring/01-extract-per-step-detail-worker-function.md
  status: done
- id: 2
  title: Add concurrent ThreadPoolExecutor dispatch to generate_detail behind a jobs
    argument
  files:
  - plan_tool/detail.py
  - tests/test_detail.py
  complexity: high
  change_type: feature
  enforce_test_authoring: false
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/parallel-detail-authoring/02-concurrent-threadpoolexecutor-dispatch.md
  status: done
- id: 3
  title: Add the --jobs N flag and thread it through cmd_detail into generate_detail
  files:
  - plan_tool/cli/authoring.py
  - tests/cli/test_authoring_cmds.py
  complexity: low
  change_type: feature
  depends_on:
  - 2
  detail: docs/implementation-plans/plan-details/parallel-detail-authoring/03-jobs-flag-thread-through-cmd-detail.md
  status: done
- id: 4
  title: Refuse --jobs > 1 with --iterate/--split and degrade --jobs > 1 --step to
    serial
  files:
  - plan_tool/cli/authoring.py
  - tests/cli/test_authoring_cmds.py
  complexity: low
  change_type: feature
  depends_on:
  - 3
  detail: docs/implementation-plans/plan-details/parallel-detail-authoring/04-refuse-jobs-iterate-split-degrade-jobs.md
  status: done
- id: 5
  title: Regenerate the detail CLI reference and document the concurrently-exercised
    invoker seam
  files:
  - docs/cli/detail.md
  - TESTING.md
  complexity: low
  change_type: non-code
  depends_on:
  - 2
  - 4
  detail: docs/implementation-plans/plan-details/parallel-detail-authoring/05-regenerate-detail-cli-reference.md
  status: done
---
# Parallel Detail Authoring

## Overview

Add an opt-in `--jobs N` flag to `plan-tool detail` that authors several steps' detail files concurrently instead of strictly one-at-a-time. The expensive part of `detail` is the per-step Claude authoring shell-out in `generate_detail` (`plan_tool/detail.py:1443`), run serially over `target_steps` (`detail.py:1630`). Because authoring step K is independent of authoring step J (each renders from the plan + its own step and writes its own file; `depends_on` is unused by detail), the authoring calls can be dispatched concurrently to cut the wall-clock of the *authoring* round-trips. The speedup is sub-linear, not linear: lesson extraction (`extract_and_append_detail_lessons`, a second per-step `claude` round-trip, default ON) stays in the serial post-join tail, so a `--jobs N` run still pays N serial lesson calls — the near-linear case is `--jobs N --no-lessons`. The flag defaults to `1` (serial — identical to the current path); every plan-mutating side effect (plan-file writes, structural split, lesson extraction) stays serialized and deterministically step-ordered. `--jobs > 1` is refused when combined with the plan-structure-mutating modes (`--iterate`/`--split`).

## Problem statement

Authoring per-step detail files is serial and slow: a plan with 8 undetailed steps pays 8 × (one Claude authoring round-trip) in sequence (`detail.py:1855` via `shell_detail_invoker`). The calls are subprocess/IO-bound — the process waits on the `claude` binary — so they are a natural fit for concurrent dispatch, yet nothing in `plan_tool/` runs concurrently today (no `ThreadPoolExecutor`/`asyncio`/`multiprocessing`; `concurrent` appears only in comments warning against concurrent runs). The blocker is that the `generate_detail` loop is stateful and plan-mutating mid-iteration: it writes the shared plan `.md` via `update_step_detail_field` (`detail.py:2043`), can run the structural split (`escalate_to_split`) that renumbers steps and repoints downstream detail files, and can run the per-step `--iterate` convergence loop (`detail.py:2161`, guarded by `budget.enabled`) that re-audits and `apply_finding`s against the live plan/detail on disk. Naive parallelism would race those writes and corrupt the frontmatter or scramble step numbering. The user-visible symptom is long serial wait time when bulk-authoring multi-step plans.

## Architecture

**Opt-in surface (`cli/authoring.py`).** Add `--jobs N` to the `detail` subparser (near the other `p_detail.add_argument` calls, ~`authoring.py:2147+`), default `1` (serial, unchanged). `--jobs` requires an explicit integer `N >= 1`; a value `< 1` is a usage error (the CLI rejects it via a custom `type=` callable). There is no `0`-means-auto convenience and no `cpu_count`-derived default — keeping concurrency explicit means the tool never silently fans out many `claude` subprocesses. Thread the value through `cmd_detail` (`authoring.py:1043`) into `generate_detail` as a new keyword arg (e.g. `jobs: int = 1`) at the call site (`authoring.py:1157`), and regenerate the CLI reference (`python -m plan_tool.cli_reference --write`).

**Independent per-step worker (behavior-preserving refactor).** Steps 1–3 of the loop body (render via `render_detail_prompt` → shell out via the `invoker=` seam → write the detail file) plus computing the deferred plan-update record `(step_id, repo_relative_detail_path)` are the concurrency-safe part. Lift them into a worker function that takes the step plus the immutable context it needs (plan snapshot, repo_root, invoker, reporter handle, checkpoint config), performs render → invoke → write, and returns a `DetailResult` and the deferred plan-update record **without mutating the plan file**. At `jobs == 1` the caller invokes the worker inline in the existing loop and applies the plan-update exactly as today (`update_step_detail_field`), proving the refactor is behavior-preserving before any concurrency lands.

**Concurrent dispatch (the feature).** When `jobs > 1`, dispatch the workers over a `concurrent.futures.ThreadPoolExecutor` — threads, not processes, because the workers share the in-memory `plan` object and the GIL is released while the `claude` subprocess runs (processes would force pickling and lose the shared invoker seam). After the pool joins: apply plan-file updates serially in ascending step order (one writer, no `.md` races); emit result rows and run-log phases (`detail-step-NN`) in step order, not completion order, by buffering per-step output/log events in the worker and flushing them ordered after the join (ordered-flush preferred over a run-logger lock for reproducibility); and preserve failure isolation with the **same exception taxonomy as the serial loop** — only the two cases the current loop already aggregates become a per-step failed `DetailResult` that never aborts its siblings: a handled `OSError` on the detail-file write, and a `None` body from `parse_detail_response` (an unparseable response). Every other exception propagating out of `render_detail_prompt`, `invoker(attempt_prompt)`, or `parse_detail_response` stays a **plan-level abort** exactly as today (the `generate_detail` docstring's "plan-level failures raise") — the dispatch must not swallow it into a per-step skip. To keep the abort deterministic, collect such an exception across the pool and re-raise the first one in step order after the workers join, rather than tearing the pool down mid-flight. The `invoker=` seam is untouched — workers call the same `shell_detail_invoker` (or the test override) — so the conftest real-`claude` gate and TESTING's neutralization table keep working; the seam is now exercised concurrently. This realizes the mission's *deterministically driven non-determinism*: nondeterministic latency of N concurrent calls, deterministically ordered on the way out.

**Mutual exclusion with plan-mutating modes (the guard).** `--jobs > 1` is incompatible with the modes that mutate plan structure mid-loop — the `--iterate`/convergence loop (`budget.enabled`) and structural split escalation (`allow_split`/`--split`). The guard is enforced **inside `generate_detail`** for *both* arms: `jobs > 1` raises when `budget.enabled` is set **and** when `allow_split` is set. Guarding only the iterate arm leaves a gap, because the post-loop Phase-B split (`escalate_to_split`) fires independent of `budget.enabled` — a non-CLI caller invoking `generate_detail(jobs > 1, allow_split=True)` with iterate off would run concurrent dispatch and then a serial-tail split that renumbers steps against siblings already authored under the old numbering. Self-protecting `generate_detail` regardless of entry point is the mutual-exclusion promise; step 4's CLI guard in `cmd_detail` stays as the operator-facing message. When combined, refuse with a clear error (preferred over silent degrade) recommending the two-pass workflow: parallel authoring first to get all bodies down fast, then a serial `--iterate` pass to converge. A single-step run (`--step N`) with `--jobs > 1` degrades to serial with a note (one step, nothing to parallelize) rather than erroring.

**Surface the un-converged first pass (always-iterate mandate).** Because `--jobs > 1` is only runnable with `--no-iterate`/`--no-split`, a parallel run by construction emits detail bodies that **never ran the convergence loop** — an intentionally un-converged first pass that the two-pass workflow expects the operator to follow with a serial `--iterate` pass. To honor the project's always-`--iterate` mandate, a `--jobs > 1` authoring run must end with a **terminal warning** naming the bodies as un-converged and printing the exact follow-up command (`plan-tool detail <plan> --iterate`). Without it, an operator who stops after the fast pass ships unconverged details with no signal. This is advisory output only (rc unaffected — exit-code convention), the parallel-run analogue of the serial loop's convergence guarantee.

## References

- [concurrent.futures — Launching parallel tasks — Python documentation](https://docs.python.org/3/library/concurrent.futures.html) — Canonical reference for ThreadPoolExecutor, submit/map, Future objects, and as_completed — the exact primitives the concurrent-dispatch worker pool is built on.
- [threading — Thread-based parallelism (GIL semantics) — Python documentation](https://docs.python.org/3/library/threading.html) — Explains the Global Interpreter Lock and that it is released around blocking I/O, which is the core premise that threads (not processes) make the subprocess-bound authoring calls concurrent.
- [subprocess — Subprocess management — Python documentation](https://docs.python.org/3/library/subprocess.html) — Reference for spawning and waiting on the `claude` binary per worker thread, including return-code/failure handling needed for per-step failure isolation.
- [argparse — Parser for command-line options and subcommands — Python documentation](https://docs.python.org/3/library/argparse.html) — API for adding the new `--jobs N` option (custom `type=` callable rejecting `< 1`, default, help) to the detail subparser and enforcing its mutual-exclusion guard.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Parallelizing `create`, `run`, `jira`, or the convergence loop itself — this is the `detail` authoring call only.
- Parallelizing across plans or across the `escalate_to_split`/reconcile paths.
- Changing *what* a detail file contains or how a step is authored — only *how many* author concurrently.
- A process-pool / distributed backend — in-process threads only.

## Risks

- **Plan-file corruption under concurrent writes.** Severity: high. Mitigation: workers never touch the `.md`; a single post-join writer applies updates in step order. Test asserts the plan frontmatter is intact and all `step.detail` pointers are set after a parallel run.
- **Nondeterministic output ordering.** Severity: medium. Scope the guarantee precisely — only the *durable, step-attributed* artifacts are ordered: the returned `DetailResult` sequence, the run-log `phase_start`/`phase_end` pairs, and the final result rows are buffered and flushed in ascending step id after join. Two classes are explicitly **not** buffer-ordered and interleave by design under `--jobs N`: (a) the per-attempt run-log JSONL events emitted *inside* the worker region (`claude_call_start`, `ClaudeCallEnd`, `parse_failure`, `checkpoint_save`) — these append live via `_append_jsonl_line`, so the append must be **thread-safe** (a lock around the writer) but lands in completion order, which is acceptable since each line carries its `step_id`; and (b) the `StderrReporter` live per-step heartbeat thread, which by its nature streams in real time and cannot be buffered without defeating its purpose. Mitigation: lock the JSONL append; assert the ordered artifacts (results, phases) are identical regardless of completion order, and document that live heartbeats/per-attempt events interleave.
- **Fanning out too many `claude` subprocesses** (resource/rate-limit pressure). Severity: medium. Mitigation: `--jobs` has no auto/`0` mode — the operator must pass an explicit `N >= 1`, so concurrency is never implicitly large; the executor bounds in-flight workers to `min(jobs, step_count)`.
- **Sibling-detail context degraded.** `_discover_siblings` reads already-written detail files for cross-step context; concurrently-authored siblings won't be visible to each other. Severity: low (authoring is per-step-independent in the common case). Mitigation: document; the serial `--iterate` follow-up pass sees all siblings.
- **Hidden shared mutable state in the worker.** Severity: medium. Mitigation: the refactor step isolates worker inputs to immutable context + the step; no shared accumulator is mutated without a lock.

## Testing

Follow the project's unit-first convention. Add tests for: no plan-file corruption under concurrency (frontmatter intact, every `step.detail` pointer set after a parallel run); deterministic step-ordered output (result rows and run-log phases identical regardless of completion order); failure isolation (a failing step yields a failed `DetailResult` and does not abort siblings); and the guard's error path (`--jobs > 1` with `--iterate`/`--split` errors with the usage-error rc, `--jobs > 1 --step N` degrades to serial with a note). The behavior-preserving worker-extraction refactor must keep existing `detail` tests green (characterization-first). The concurrency path that drives `generate_detail` end-to-end through the `invoker=` seam belongs to the integration tier. Note in TESTING.md that the `invoker=` seam (`shell_detail_invoker`) is now exercised concurrently; the conftest real-`claude` gate and the neutralization table must keep holding. A `--jobs > 1` run also drives a **second** backend seam concurrently — `foundational_invoker` (`run_foundational_logic_sweep`), distinct from `shell_detail_invoker` — when the foundational sweep is wired; it is OFF by default (no production caller), so impact is bounded to eval harnesses, but name it alongside `shell_detail_invoker` as a concurrently-exercised seam so the neutralization table stays complete.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (refactor) — characterization tests pinned before the change; pass unchanged after.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (feature) — unit tests added with the implementation; green before completion.
- step 5 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- `plan-tool detail <plan>` with no `--jobs` (or `--jobs 1`) behaves identically to today (serial; existing tests green).
- `plan-tool detail <plan> --jobs N` (N>1) authors the undetailed steps' detail files concurrently and writes a valid plan with every `step.detail` pointer set; result rows and run-log phases render in ascending step order regardless of completion order.
- A failing step under `--jobs N` yields a failed `DetailResult` for that step and does not abort the others.
- `--jobs > 1` combined with `--iterate` or `--split` errors with a clear message recommending the two-pass (parallel-then-serial) workflow; rc is the usage-error code (not a findings code — exit-code convention).
- `--jobs > 1 --step N` degrades to serial with a note (no error).
- The `invoker=` seam is unchanged; the conftest real-`claude` gate still holds and TESTING.md documents the concurrently-exercised seam.
- CLI reference regenerated; `docs/cli` drift guard passes.

## Deferred

- Auto-tuning the default job count from observed authoring latency.
- A `--jobs`-aware progress bar (live concurrent [N/M] with per-step spinners) — ordered post-join rendering is enough for v1.
- Parallelizing the convergence/`--iterate` loop (requires a fundamentally different concurrency model since it mutates plan structure).
- Extending `--jobs` to `create`/`run`.
