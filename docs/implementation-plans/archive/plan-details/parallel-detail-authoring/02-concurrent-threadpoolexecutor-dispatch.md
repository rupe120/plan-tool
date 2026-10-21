> **Auto-archived**: this plan was swept on 2026-07-04 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Add concurrent ThreadPoolExecutor dispatch to generate_detail behind a jobs argument

## Summary

Add a `jobs: int = 1` parameter to `plan_tool/detail.py:generate_detail` that, when set above 1, runs step 1's per-step authoring worker concurrently across the steps that need a fresh claude call instead of one at a time. Only the worker prefix (render → invoke → parse → checkpoint-save → write the step's own detail file) runs on threads; every plan-mutating and cross-step-ordered piece — `update_step_detail_field`, `discard_checkpoint`, the `budget.enabled` convergence loop, `escalate_to_split`, lesson extraction, run-log phases — stays serial and runs in step order after the workers join. Threads (not processes) are correct because the work is subprocess/IO-bound: the `claude` shell-out releases the GIL. At `jobs=1` the existing serial loop is taken unchanged, so the characterization tests stay green; the observable win at `jobs>1` is wall-clock — N authoring calls overlap — with the same on-disk plan, the same set of detail files, and `DetailResult`s returned in step order.

## Table of Contents

- [Why](#why) — why authoring calls should overlap and what blocks it today
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files this step touches
- [Implementation](#implementation) — the dispatch branch, the serial tail, the mutual-exclusion guard, and what must stay ordered
- [Tests](#tests) — concurrency, ordering, failure isolation, and the guard
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — the stdlib primitives the pool is built on
- [Deferred](#deferred) — the CLI flag, the iterate combination, and the sibling-visibility change left out

## Why

`generate_detail` authors one step at a time. Each step's slow part is a single blocking `claude` call through the `invoker=` seam, and those calls are independent — step 5's authoring call does not depend on step 3's output. A plan with a dozen steps pays the full sum of those round-trips in series even though the host sits idle waiting on each subprocess. Step 1 already cut the per-step body into a worker that takes an immutable snapshot of context and returns everything the serial tail needs (the `DetailResult`, the deferred `(step_id, detail_rel)` record, the parsed body, and the purity findings), without touching the plan `.md`. This step spends that seam: hand the worker calls to a small thread pool so the authoring round-trips overlap, while leaving every plan write and cross-step decision exactly where step 1 left it — serial.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/detail.py` — add the `jobs: int = 1` parameter to `generate_detail`; add a concurrent-dispatch branch over the worker that runs when `jobs > 1`; add the in-function mutual-exclusion guard and the worker-count resolution. Leave the `jobs == 1` path on the existing serial loop.
  - `tests/test_detail.py` — add unit tests for concurrent dispatch, step-order results, per-step failure isolation, the iterate guard, and worker-count resolution, all driven through a fake `invoker=`.

## Implementation

**Goal.** When `jobs > 1`, overlap the per-step authoring calls; keep every plan mutation and cross-step decision serial and in step order. When `jobs == 1` (the default), run the existing loop with no behavior change.

**Add the parameter.** Give `generate_detail` a keyword `jobs: int = 1`, placed beside the other tuning kwargs (e.g. near `budget`/`triage`). It is the max number of authoring calls in flight. The CLI `--jobs N` flag and its argparse guard are a later wiring step (the parser is not in this step's files) — here `jobs` is a function parameter only.

**Resolve the worker count once, up front.**
- `jobs` is always an explicit `>= 1` (the CLI rejects `< 1` as a usage error — step 3; the parameter default is `1`). There is no `0`/auto mode and no `os.cpu_count()`-derived default — the operator names the concurrency explicitly, so this step never picks a worker count on its own. Defensive floor only: treat any `jobs < 1` that still reaches the function as `1` (serial) rather than raising — the CLI is the validation point.
- Clamp the worker count to the number of steps that actually need a fresh invoke — never spin more threads than there is work (`min(jobs, invoke_count)`).
- A single explicit `step_id` (one target) or a fully-cached/already-done run means there is at most one invoke; take the serial path regardless of `jobs`.

**Confirm step 1's worker before wiring it in.** This step consumes step 1's per-step worker (its `DetailResult`, the deferred `(step_id, detail_rel)` record, the parsed body, and the purity findings). Before passing it to the pool, read the worker as it actually landed in `plan_tool/detail.py` at HEAD — confirm the exported function name and the exact return shape/order step 1 settled on — and key the dispatch off that signature, not off the names this body uses. If step 1's worker has not landed yet, it is a hard dependency: do not synthesize a worker here.

**Compute one pre-dispatch sibling snapshot.** Step 1 made the sibling snapshot a worker *input* (`_discover_siblings` runs in the caller, never inside the worker). Here, run `_discover_siblings` **once before the pool starts** and pass that single snapshot into every worker. Discovering per-worker under the pool would make which siblings a worker sees (and embeds in its authoring prompt via `_format_sibling_details_block`) depend on thread schedule — a worker queued behind another would read its already-written `NN-*.md`, and could read a file mid-`write_text`. A single up-front snapshot makes the authored content schedule-independent: every worker reads the same pre-run sibling set. This is the within-run sibling-visibility difference from serial mode (workers do not see each other's just-written files); it is intentional, not a bug.

**Keep the worker prefix as the only concurrent unit.** Dispatch step 1's worker — render → `invoker(...)` (with its retry loop) → `parse_detail_response` → `save_checkpoint` → write this step's own detail file. Each step writes a distinct canonical path under `plan-details/<slug>/NN-*.md`, so the file writes do not collide. One way: build the final list of steps that need a fresh authoring call, submit one worker per step to a `concurrent.futures.ThreadPoolExecutor(max_workers=resolved)` passing the shared pre-dispatch sibling snapshot, and collect each worker's return keyed by `step.id`.

**Run the serial tail after the workers join, in step order.** Everything from `update_step_detail_field` onward must stay serial and ordered by step id, exactly as the current loop runs it for one step:
- `update_step_detail_field` then `step.detail = detail_rel` (plan frontmatter — shared mutable file).
- `discard_checkpoint` — **must stay after** the `update_step_detail_field` write. The checkpoint is the "claude succeeded but the plan pointer isn't set yet" hedge; discarding it before the pointer write breaks that durability guarantee. `save_checkpoint` belongs in the worker (right after a good parse); `discard_checkpoint` belongs in the serial tail.
- the mixed-step heads-up (`tool(... mixed-step ...)` + `mixed_steps.append`), orphan-detail archiving, and scenario capture.
- lesson extraction (`extract_and_append_detail_lessons`) — a second claude call against the written body; keep it serial.
- the run-log `phase_start`/`phase_end` pairing.

**Order results deterministically.** Append `DetailResult`s in `target_steps` order, not worker-completion order. Keep the `results` list keyed/sorted by step id so a `jobs>1` run returns the same sequence a serial run would.

**Scope the ordering guarantee — and make the in-worker run-log append thread-safe.** Only the *durable, step-attributed* artifacts are ordered: the returned `DetailResult` sequence, the final result rows, and the run-log `phase_start`/`phase_end` pairs (which already live in the serial tail). Two classes emitted from *inside* the concurrent worker region are **not** buffer-ordered and interleave by design — name this so an implementer doesn't mistake it for a bug to fix:
- **Per-attempt run-log JSONL events** — `claude_call_start`, the shell sink's `ClaudeCallEnd`, `parse_failure`, and `checkpoint_save` are written by the worker during the live overlapping calls. They land in completion order, which is acceptable because each line already carries its `step_id`; but the underlying `RunLogWriter._append_jsonl_line` is **not currently thread-safe** (concurrent appends can interleave bytes within a line). Wrap the writer's append in a lock (a `threading.Lock` held only around the file write) so lines stay whole. This is the one shared-mutable-state mutation a worker legitimately performs — it must be synchronized.
- **The `StderrReporter` live per-step heartbeat** streams progress in real time from each worker; it cannot be buffered-and-flushed without defeating its purpose, so heartbeats interleave on stderr under `jobs > 1`. Accepted — the durable result rows and phases remain ordered.

**Guard both plan-structure-mutating arms.** `jobs > 1` is mutually exclusive with **both** `--iterate` (`budget.enabled`) **and** `--split` (`allow_split`). Raise `DetailError` naming the conflict when `jobs > 1` and *either* is set (rather than silently serializing — be explicit).
- The `budget.enabled` case is the load-bearing one: the convergence loop re-reads the live plan and detail from disk each iteration, and its in-loop `escalate_to_split` (the `BLOCKED-STRUCTURAL` path inside `if budget.enabled:`) renumbers steps out from under workers holding step snapshots.
- The `allow_split` case is **defense-in-depth, by deliberate policy** — not strict necessity. Phase B (the post-loop `escalate_to_split` over `mixed_steps`) does run serially *after* the pool joins, so it is technically tolerable. But "author concurrently, then auto-restructure the plan in the same call" has no real use case and contradicts the two-pass workflow (structural changes belong in the serial `--iterate` follow-up). Guarding it keeps `generate_detail` self-protecting regardless of entry point — a direct (non-CLI) caller passing `generate_detail(jobs > 1, allow_split=True)` is refused at the function, not just at step 4's CLI guard. The two layers are complementary: step 4 gives the friendly operator-facing message; this guard is the backstop.

**Keep interactive prompts off the worker threads.** `_confirm_replace` and `_confirm_resume` read from a TTY and must never fire from multiple threads at once. Resolve them serially before dispatch (the `cached_by_id` pre-scan already resolves cache state up front; fold the replace/resume decisions into the same pre-dispatch pass) so only the confirmed fresh-invoke set is handed to the pool. A `jobs>1` run in a non-TTY context auto-declines as it does today.

**Constraints a developer must respect:**
- **`jobs == 1` is identical to the current behavior.** Route it through the unchanged serial loop; do not re-implement the single-step path on top of the pool.
- **No plan write from a worker thread.** The worker returns the deferred `(step_id, detail_rel)` record; the serial tail applies it. This is step 1's contract — do not move `update_step_detail_field`, `discard_checkpoint`, `mixed_steps.append`, or lesson extraction into the worker.
- **Per-step failure isolation holds, with the serial loop's exception taxonomy.** Match what the current loop already aggregates and nothing more: only a `None` body from `parse_detail_response` (an unparseable response) and a handled `OSError` on the detail-file write yield a not-written `DetailResult` with a `skipped_reason`; the other steps still complete. Every other exception out of `render_detail_prompt`, `invoker(...)` (including its retry loop), or `parse_detail_response` is a **plan-level abort today** (`generate_detail`'s docstring: "plan-level failures raise") and must stay one — do **not** collect every future's exception into a per-step skip, which would silently downgrade today-fatal errors. Concretely: in each worker, let those two cases produce a failed `DetailResult` as they do now, and let any other exception escape; when collecting futures, re-raise the first plan-level exception in step order after the pool joins (rather than mid-flight) so the abort is deterministic while a per-step parse/write failure stays isolated.
- **Threads, not processes.** `ThreadPoolExecutor`, not `ProcessPoolExecutor`: the shared `invoker=` seam, reporter, and run-logger are in-process objects that would not survive process boundaries, and the workload is IO-bound on the subprocess.

**Sibling-visibility note.** In serial mode a later step's `_discover_siblings` can see the detail files earlier steps just wrote this run. Under concurrent dispatch every worker reads **one pre-dispatch sibling snapshot** computed before the pool starts (see "Compute one pre-dispatch sibling snapshot"), so authored content is independent of thread schedule and no worker reads a half-written sibling. The cost is that concurrently-authored siblings do not see each other's just-written files — an accepted difference of the concurrent path, not a bug. At `jobs == 1` sibling discovery is unchanged: the caller computes it per step inline, so a later step still sees earlier steps' fresh files.

## Tests

All in `tests/test_detail.py`, driven through a fake `invoker=` (never real claude — the conftest gate forbids it) and `extract_lessons=False` per the file's convention.

- `test_jobs_one_matches_serial` — `generate_detail(..., jobs=1)` writes the same detail files and returns the same `DetailResult` sequence as the default serial call (characterization of the unchanged path).
- `test_jobs_above_one_runs_workers_concurrently` — a fake invoker that records peak in-flight count (via a shared counter or `threading.Barrier`) proves more than one authoring call overlaps when `jobs=2+`.
- `test_results_in_step_order_regardless_of_completion` — a fake invoker whose per-step latency scrambles completion order still yields `DetailResult`s ordered by step id, and the plan's `detail:` pointers are all set.
- `test_jobs_with_iterate_raises` — `jobs=2` with `budget.enabled=True` raises `DetailError` naming the conflict; nothing is written.
- `test_jobs_with_split_raises` — `jobs=2` with `allow_split=True` (iterate off) raises `DetailError` naming the conflict; nothing is written (the defense-in-depth backstop for direct callers).
- `test_concurrent_run_log_lines_intact` — under `jobs>1` with overlapping fake invokers, every line in the run-log JSONL parses as whole JSON (no interleaved bytes), proving the `_append_jsonl_line` lock holds.
- `test_concurrent_per_step_failure_isolated` — one step's fake invoker returns an unparseable response; the other steps are written and that step's `DetailResult` carries the unparseable `skipped_reason`.
- `test_worker_count_bounded_by_work` — with `jobs` larger than the number of invoke targets, the pool is sized to the target count, not `jobs` (never more threads than work).
- `test_jobs_below_one_floored_to_serial` — `jobs=0` (a defensive value the CLI would normally reject) runs the serial path to completion rather than raising or auto-resolving a worker count — the CLI is the validation point.
- `test_single_step_id_ignores_jobs` — `jobs=4` with one explicit `step_id` takes the serial path (one invoke).
- `test_concurrent_plan_pointers_all_set` — after a `jobs>1` run, every authored step's frontmatter `detail:` pointer resolves to its on-disk file (the serial tail ran for each).

### Test-creation order (feature step)

This is a feature step — new behavior. Write each test above alongside the dispatch code it covers: start with `test_jobs_one_matches_serial` to pin the unchanged default, then the concurrency, ordering, and isolation tests as the pool lands, then the guard and resolution tests. Green-before-done gate: every new test, and the existing `TestGenerateDetail*` suite, must pass before this step is finished.

## Acceptance criteria

- `generate_detail` accepts `jobs: int = 1`; `jobs=1` produces identical results and files to the pre-change serial path (characterization suite green).
- `jobs > 1` overlaps the per-step authoring calls — a test observing peak in-flight invocations sees more than one.
- `DetailResult`s come back ordered by step id for any `jobs` value, independent of worker completion order.
- After a `jobs>1` run, every authored step's plan `detail:` pointer is set and resolves to its written file.
- A per-step authoring failure under `jobs>1` is isolated for the two cases the serial loop aggregates (unparseable `None` body, write `OSError`): siblings are written; the failed step's `DetailResult` is not written and carries a `skipped_reason`. Any other exception (out of `render_detail_prompt`, `invoker`, or `parse_detail_response`) remains a plan-level abort — collected across the pool and re-raised in step order after the join, not downgraded to a per-step skip.
- `jobs > 1` with `budget.enabled=True` **or** `allow_split=True` raises `DetailError` and writes nothing.
- Under `jobs > 1`, the per-attempt run-log JSONL events (`claude_call_start`, `ClaudeCallEnd`, `parse_failure`, `checkpoint_save`) append through a thread-safe lock so every line stays whole; they may land in completion order (each carries its `step_id`). Live stderr heartbeats interleaving under concurrency is accepted, not a failure.
- The worker count is `min(jobs, invoke_count)` — never more threads than there is work; `jobs` reaching the function is already an explicit `>= 1` (the CLI is the validation point), and any `jobs < 1` slipping through is floored to `1` (serial), not auto-resolved.
- No plan-mutating call (`update_step_detail_field`, `discard_checkpoint`, lesson extraction, `escalate_to_split`) runs on a worker thread; the serial tail runs them in step order.
- Under `jobs > 1`, `_discover_siblings` runs **once** before the pool starts and the same snapshot is passed to every worker; no worker calls `_discover_siblings`, so authored content does not depend on thread schedule.

## References

- [concurrent.futures — Launching parallel tasks](https://docs.python.org/3/library/concurrent.futures.html) — `ThreadPoolExecutor`, `submit`, `as_completed`, and `Future` result/exception handling — the primitives the dispatch branch is built on.
- [threading — Thread-based parallelism](https://docs.python.org/3/library/threading.html) — the GIL is released around blocking I/O, which is why threads make the subprocess-bound authoring calls overlap.
- [subprocess — Subprocess management](https://docs.python.org/3/library/subprocess.html) — return-code/failure handling for the `claude` spawn per worker thread, the basis for per-step failure isolation.

## Deferred

- The `--jobs N` CLI flag on the detail subparser and its argparse mutual-exclusion guard — owned by the CLI-wiring step (the same step that wires `--iterate`); this step adds only the `jobs` function parameter and the in-function guard. The parser is not in this step's files.
- Running `jobs > 1` together with `--iterate` (`budget.enabled`) — out of scope and rejected by the guard; the convergence loop and its in-loop `escalate_to_split` need serial, ordered, plan-mutating execution.
- Restoring within-run sibling visibility under concurrency (workers seeing each other's just-written detail files) — accepted behavior difference, not addressed here.
- Parallel STEP execution as a general model — unrelated; this step parallelizes only the authoring call within one `generate_detail` run, not step execution at `run` time.
