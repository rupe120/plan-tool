> **Replaced**: this file has been superseded by `docs/implementation-plans/2-parallel-detail-authoring.md`.
> Preserved here for history; do not edit.

# Plan seed: optionally parallel `detail` processing — author N steps' detail files concurrently behind a `--jobs` opt-in

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing plan-seeds/parallel-detail-processing.md --iterate
```

It is **not** itself a plan — `plan-tool create` consumes the prose below and
proposes a step decomposition; the author then runs `plan-tool detail` per step.

> **Scope: wall-clock parallelism for the per-step authoring call in
> `generate_detail`, opt-in and off by default.** The expensive part of `detail`
> is the per-step Claude authoring shell-out, run serially for every step.
> Add an opt-in to run those authoring calls concurrently across steps, while
> keeping every plan-mutating side effect (plan-file writes, structural split,
> lesson extraction) serialized and deterministically ordered. At the default
> job count the behavior is **byte-for-byte the current serial path**.

---

## Overview

`generate_detail` (`plan_tool/detail.py:1443`) authors per-step detail files by
walking `target_steps` in a single serial loop (`detail.py:1630`,
`for step in target_steps:`). Each iteration does, in order:

1. render the step's authoring prompt (`render_detail_prompt`),
2. **shell out to Claude** via the `invoker=` seam (`shell_detail_invoker`,
   the call at `detail.py:1855`) — the slow part, minutes per step,
3. write the detail file to disk,
4. **mutate the shared plan `.md`** via `update_step_detail_field`
   (`detail.py:2043`; sets `step.detail`),
5. optionally run the per-step `--iterate` convergence loop (gates →
   `apply_finding` → re-audit; `detail.py:2161`, guarded by `budget.enabled`),
6. optionally escalate a mixed/structural step to a split
   (`escalate_to_split`), which **renumbers the plan and breaks the loop**,
7. extract lessons, write checkpoints, emit run-log phases / progress.

For an N-step plan the authoring calls dominate wall-clock and run strictly
one-at-a-time even though, in the common case, **authoring step K is
independent of authoring step J** — each renders from the plan + its own step
and writes its own file (the exploration confirmed detail generation is
step-order-agnostic: `depends_on` exists in the schema but is unused by detail,
and sibling details are read-only context). Parallelizing the authoring calls
can cut `detail` wall-clock roughly linearly in the job count for plans with
several not-yet-detailed steps.

The catch is that the loop is **stateful and plan-mutating**, so naive
parallelism would corrupt the plan file and scramble step numbering. This plan
adds parallelism **only to the independent authoring work**, keeps every
mutating side effect serial and ordered, and makes the whole thing opt-in.

## Problem statement

- **Authoring is serial and slow.** A plan with 8 undetailed steps pays
  8 × (one Claude authoring round-trip) in sequence. The calls are
  subprocess/IO-bound (the process waits on the `claude` binary), so they are a
  natural fit for concurrent dispatch — but nothing in `plan_tool/` runs
  concurrently today (no `ThreadPoolExecutor`/`asyncio`/`multiprocessing`
  anywhere; `concurrent` appears only in comments *warning against* concurrent
  runs), so this sets the precedent.

- **The loop mutates shared state mid-iteration.** Concurrent iterations cannot
  safely:
  - write the plan `.md` (`update_step_detail_field`) — concurrent writes race
    and corrupt the frontmatter (the primary hazard);
  - run the structural split (`escalate_to_split`), which renumbers steps
    1..N and repoints downstream detail files out from under any other
    in-flight iteration;
  - run the per-step `--iterate` convergence loop, which re-audits and
    `apply_finding`s against the live plan / detail file on disk.

- **Checkpoints have no locking.** `checkpoint.py` is file-based and explicitly
  warns against concurrent runs against the same checkpoint dir. Per-step
  checkpoints are keyed by step id (independent), but the design must not
  introduce cross-step checkpoint contention.

- **Output must stay deterministic.** Per-step result rows, run-log phases
  (`detail-step-NN`), and the `[N/M]` progress denominator are emitted in step
  order today. Under concurrency, completion order is nondeterministic — but the
  *rendered* output and persisted artifacts must remain reproducible and
  step-ordered (the mission's *deterministically driven non-determinism*: the
  nondeterministic latency of N concurrent calls, deterministically ordered on
  the way out).

## Design

### The opt-in surface (`cli/authoring.py`)

Add `--jobs N` to the `detail` subparser (near the other `p_detail.add_argument`
calls, ~`authoring.py:2147+`), default **`1`** (serial — current behavior,
unchanged). `--jobs 0` resolves to a sensible small cap (e.g.
`min(cpu_count, 4)` or a fixed small default — let the design pick; keep it
small so we don't fan out dozens of `claude` subprocesses). Thread the resolved
value through `cmd_detail` (`authoring.py:1043`) into `generate_detail` as a new
keyword arg (e.g. `jobs: int = 1`) at the call site (`authoring.py:1157`).
Regenerate the CLI reference (`python -m plan_tool.cli_reference --write`).

### Extract an independent per-step worker (behavior-preserving refactor)

The per-step body that is safe to run concurrently is steps **1–3** above
(render → invoke → write the detail file) plus computing the **deferred
plan-update** `(step_id, repo_relative_detail_path)`. Lift that into a worker
function that:

- takes the step (+ the immutable context it needs: plan snapshot, repo_root,
  invoker, reporter handle, checkpoint config),
- performs render → invoke → write,
- returns a `DetailResult` **and** the deferred plan-update record, **without
  mutating the plan file**.

At `jobs == 1` the caller invokes the worker inline in the existing loop and
then applies the plan-update exactly as today (`update_step_detail_field`) —
proving the refactor is behavior-preserving before any concurrency is
introduced.

### Concurrent dispatch (the feature)

When `jobs > 1`, dispatch the workers over a
`concurrent.futures.ThreadPoolExecutor` (threads, not processes — the workers
share the in-memory `plan` object and the GIL is released while the `claude`
subprocess runs; processes would force pickling and lose the shared invoker
seam). After the pool joins:

- **apply plan-file updates serially, in ascending step order** — one writer,
  no races on the `.md`;
- **emit result rows and run-log phases in step order**, not completion order —
  buffer per-step output/log events in the worker and flush them ordered after
  the join (or hold a lock around the run-logger; ordered-flush is preferred for
  reproducibility);
- preserve **failure isolation**: a worker that throws or whose invoker fails
  becomes a failed `DetailResult` for that step and never aborts its siblings
  (matches the current "per-step failures aggregate, plan-level failures raise"
  contract).

The `invoker=` seam is untouched — workers call the same `shell_detail_invoker`
(or the test override), so the conftest real-`claude` gate and TESTING's
neutralization table keep working as-is. Note in TESTING.md that the seam is now
exercised concurrently.

### Mutual exclusion with plan-mutating modes (the guard)

`--jobs > 1` is **incompatible** with the modes that mutate plan structure
mid-loop:

- the `--iterate` / convergence loop (`budget.enabled`), and
- structural split escalation (`allow_split` / `--split`).

When the operator combines them, **refuse with a clear error** (preferred over
silent degrade — the mission favors predictable behavior; an explicit message
tells the operator the right sequence). Recommend the two-pass workflow in the
message: run parallel authoring first to get all bodies down fast, then a serial
`--iterate` pass to converge:

```
--jobs > 1 cannot combine with --iterate/--split (those mutate plan structure
mid-loop). Author in parallel first, then converge serially:
    plan-tool detail <plan> --jobs 4
    plan-tool detail <plan> --iterate
```

A single-step run (`--step N`) with `--jobs > 1` is a no-op-degrades-to-serial
(one step, nothing to parallelize) — note it, don't error.

## Step decomposition (apply the single-concern rule — BACKLOG #58)

Propose **pure, single-concern steps**. Suggested shape:

- **Refactor step (behavior-preserving)** — extract the independent per-step
  worker (render → invoke → write → return result + deferred plan-update) and
  have the existing serial loop apply the plan-update from the returned record
  instead of inline. No concurrency yet; `jobs` defaults to 1. Existing `detail`
  tests stay green.
- **Feature step** — add the `ThreadPoolExecutor` dispatch path taken when
  `jobs > 1`: concurrent workers, then serial/ordered plan-update application
  and step-ordered output/log flush after join. Failure isolation preserved.
- **Feature step** — wire the `--jobs` CLI flag through `cli/authoring.py` to
  `generate_detail`, resolve `0 → small cap`, regenerate the CLI reference.
- **Guard step** — refuse `--jobs > 1` with `--iterate`/`--split` (clear
  error + recommended two-pass command); degrade single-step parallel to serial
  with a note.
- **Docs/tests step** — a detail-flow doc + TESTING.md note on the
  concurrently-exercised seam; tests for no plan-file corruption under
  concurrency, deterministic step-ordered output, failure isolation, and the
  guard's error path.

Keep the worker extraction (refactor) and the executor dispatch (feature) as
**separate** steps — the refactor must be green and behavior-preserving on its
own before concurrency lands.

## Out of scope

- Parallelizing `create`, `run`, `jira`, or the convergence loop itself — this
  is the `detail` authoring call only.
- Parallelizing across plans or across the `escalate_to_split`/reconcile paths.
- Changing *what* a detail file contains or how a step is authored — only *how
  many* author concurrently.
- A process-pool / distributed backend — in-process threads only.

## Risks

- **Plan-file corruption under concurrent writes.** Severity: high. Mitigation:
  workers never touch the `.md`; a single post-join writer applies updates in
  step order. Test asserts the plan frontmatter is intact and all `step.detail`
  pointers are set after a parallel run.
- **Nondeterministic output ordering.** Severity: medium. Mitigation: buffer
  per-step result/log events and flush in ascending step id after join; assert
  output is identical regardless of completion order.
- **Fanning out too many `claude` subprocesses** (resource/rate-limit
  pressure). Severity: medium. Mitigation: small default cap on `--jobs 0`;
  document it; the executor bounds in-flight workers to the job count.
- **Sibling-detail context degraded.** `_discover_siblings` reads
  already-written detail files for cross-step context; concurrently-authored
  siblings won't be visible to each other. Severity: low (authoring is
  per-step-independent in the common case). Mitigation: document; the serial
  `--iterate` follow-up pass sees all siblings.
- **Hidden shared mutable state in the worker.** Severity: medium. Mitigation:
  the refactor step isolates worker inputs to immutable context + the step;
  no shared accumulator is mutated without a lock.

## Acceptance criteria

- `plan-tool detail <plan>` with no `--jobs` (or `--jobs 1`) behaves
  byte-for-byte as today (serial; existing tests green).
- `plan-tool detail <plan> --jobs N` (N>1) authors the undetailed steps'
  detail files concurrently and writes a valid plan with every `step.detail`
  pointer set; result rows and run-log phases render in ascending step order
  regardless of completion order.
- A failing step under `--jobs N` yields a failed `DetailResult` for that step
  and does not abort the others.
- `--jobs > 1` combined with `--iterate` or `--split` errors with a clear
  message recommending the two-pass (parallel-then-serial) workflow; rc is the
  usage-error code (not a findings code — exit-code convention).
- `--jobs > 1 --step N` degrades to serial with a note (no error).
- The `invoker=` seam is unchanged; the conftest real-`claude` gate still holds
  and TESTING.md documents the concurrently-exercised seam.
- CLI reference regenerated; `docs/cli` drift guard passes.

## Deferred

- Auto-tuning the default job count from observed authoring latency.
- A `--jobs`-aware progress bar (live concurrent [N/M] with per-step spinners) —
  ordered post-join rendering is enough for v1.
- Parallelizing the convergence/`--iterate` loop (requires a fundamentally
  different concurrency model since it mutates plan structure).
- Extending `--jobs` to `create`/`run`.
