> **Replaced**: this file has been superseded by `docs/implementation-plans/2-parallel-detail-authoring.md`.
> Preserved here for history; do not edit.

## Overview

Add an opt-in `--jobs N` flag to `plan-tool detail` that authors several steps' detail files concurrently instead of strictly one-at-a-time. The expensive part of `detail` is the per-step Claude authoring shell-out in `generate_detail` (`plan_tool/detail.py:1443`), run serially over `target_steps` (`detail.py:1630`). Because authoring step K is independent of authoring step J (each renders from the plan + its own step and writes its own file; `depends_on` is unused by detail), the authoring calls can be dispatched concurrently to cut wall-clock roughly linearly in the job count. The flag defaults to `1` (serial — byte-for-byte the current path); every plan-mutating side effect (plan-file writes, structural split, lesson extraction) stays serialized and deterministically step-ordered. `--jobs > 1` is refused when combined with the plan-structure-mutating modes (`--iterate`/`--split`).

## Problem statement

Authoring per-step detail files is serial and slow: a plan with 8 undetailed steps pays 8 × (one Claude authoring round-trip) in sequence (`detail.py:1855` via `shell_detail_invoker`). The calls are subprocess/IO-bound — the process waits on the `claude` binary — so they are a natural fit for concurrent dispatch, yet nothing in `plan_tool/` runs concurrently today (no `ThreadPoolExecutor`/`asyncio`/`multiprocessing`; `concurrent` appears only in comments warning against concurrent runs). The blocker is that the `generate_detail` loop is stateful and plan-mutating mid-iteration: it writes the shared plan `.md` via `update_step_detail_field` (`detail.py:2043`), can run the structural split (`escalate_to_split`) that renumbers steps and repoints downstream detail files, and can run the per-step `--iterate` convergence loop (`detail.py:2161`, guarded by `budget.enabled`) that re-audits and `apply_finding`s against the live plan/detail on disk. Naive parallelism would race those writes and corrupt the frontmatter or scramble step numbering. The user-visible symptom is long serial wait time when bulk-authoring multi-step plans.

## Architecture

**Opt-in surface (`cli/authoring.py`).** Add `--jobs N` to the `detail` subparser (near the other `p_detail.add_argument` calls, ~`authoring.py:2147+`), default `1` (serial, unchanged). `--jobs 0` resolves to a small cap (e.g. `min(cpu_count, 4)` or a fixed small default — kept small to avoid fanning out dozens of `claude` subprocesses). Thread the resolved value through `cmd_detail` (`authoring.py:1043`) into `generate_detail` as a new keyword arg (e.g. `jobs: int = 1`) at the call site (`authoring.py:1157`), and regenerate the CLI reference (`python -m plan_tool.cli_reference --write`).

**Independent per-step worker (behavior-preserving refactor).** Steps 1–3 of the loop body (render via `render_detail_prompt` → shell out via the `invoker=` seam → write the detail file) plus computing the deferred plan-update record `(step_id, repo_relative_detail_path)` are the concurrency-safe part. Lift them into a worker function that takes the step plus the immutable context it needs (plan snapshot, repo_root, invoker, reporter handle, checkpoint config), performs render → invoke → write, and returns a `DetailResult` and the deferred plan-update record **without mutating the plan file**. At `jobs == 1` the caller invokes the worker inline in the existing loop and applies the plan-update exactly as today (`update_step_detail_field`), proving the refactor is behavior-preserving before any concurrency lands.

**Concurrent dispatch (the feature).** When `jobs > 1`, dispatch the workers over a `concurrent.futures.ThreadPoolExecutor` — threads, not processes, because the workers share the in-memory `plan` object and the GIL is released while the `claude` subprocess runs (processes would force pickling and lose the shared invoker seam). After the pool joins: apply plan-file updates serially in ascending step order (one writer, no `.md` races); emit result rows and run-log phases (`detail-step-NN`) in step order, not completion order, by buffering per-step output/log events in the worker and flushing them ordered after the join (ordered-flush preferred over a run-logger lock for reproducibility); and preserve failure isolation — a worker that throws or whose invoker fails becomes a failed `DetailResult` for that step and never aborts its siblings (matching the current "per-step failures aggregate, plan-level failures raise" contract). The `invoker=` seam is untouched — workers call the same `shell_detail_invoker` (or the test override) — so the conftest real-`claude` gate and TESTING's neutralization table keep working; the seam is now exercised concurrently. This realizes the mission's *deterministically driven non-determinism*: nondeterministic latency of N concurrent calls, deterministically ordered on the way out.

**Mutual exclusion with plan-mutating modes (the guard).** `--jobs > 1` is incompatible with the modes that mutate plan structure mid-loop — the `--iterate`/convergence loop (`budget.enabled`) and structural split escalation (`allow_split`/`--split`). When combined, refuse with a clear error (preferred over silent degrade) recommending the two-pass workflow: parallel authoring first to get all bodies down fast, then a serial `--iterate` pass to converge. A single-step run (`--step N`) with `--jobs > 1` degrades to serial with a note (one step, nothing to parallelize) rather than erroring.

## Out of scope

- Parallelizing `create`, `run`, `jira`, or the convergence loop itself — this is the `detail` authoring call only.
- Parallelizing across plans or across the `escalate_to_split`/reconcile paths.
- Changing *what* a detail file contains or how a step is authored — only *how many* author concurrently.
- A process-pool / distributed backend — in-process threads only.

## Risks

- **Plan-file corruption under concurrent writes.** Severity: high. Mitigation: workers never touch the `.md`; a single post-join writer applies updates in step order. Test asserts the plan frontmatter is intact and all `step.detail` pointers are set after a parallel run.
- **Nondeterministic output ordering.** Severity: medium. Mitigation: buffer per-step result/log events and flush in ascending step id after join; assert output is identical regardless of completion order.
- **Fanning out too many `claude` subprocesses** (resource/rate-limit pressure). Severity: medium. Mitigation: small default cap on `--jobs 0`; document it; the executor bounds in-flight workers to the job count.
- **Sibling-detail context degraded.** `_discover_siblings` reads already-written detail files for cross-step context; concurrently-authored siblings won't be visible to each other. Severity: low (authoring is per-step-independent in the common case). Mitigation: document; the serial `--iterate` follow-up pass sees all siblings.
- **Hidden shared mutable state in the worker.** Severity: medium. Mitigation: the refactor step isolates worker inputs to immutable context + the step; no shared accumulator is mutated without a lock.

## Testing

Follow the project's unit-first convention. Add tests for: no plan-file corruption under concurrency (frontmatter intact, every `step.detail` pointer set after a parallel run); deterministic step-ordered output (result rows and run-log phases identical regardless of completion order); failure isolation (a failing step yields a failed `DetailResult` and does not abort siblings); and the guard's error path (`--jobs > 1` with `--iterate`/`--split` errors with the usage-error rc, `--jobs > 1 --step N` degrades to serial with a note). The behavior-preserving worker-extraction refactor must keep existing `detail` tests green (characterization-first). The concurrency path that drives `generate_detail` end-to-end through the `invoker=` seam belongs to the integration tier. Note in TESTING.md that the `invoker=` seam (`shell_detail_invoker`) is now exercised concurrently; the conftest real-`claude` gate and the neutralization table must keep holding.

## Acceptance criteria

- `plan-tool detail <plan>` with no `--jobs` (or `--jobs 1`) behaves byte-for-byte as today (serial; existing tests green).
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
