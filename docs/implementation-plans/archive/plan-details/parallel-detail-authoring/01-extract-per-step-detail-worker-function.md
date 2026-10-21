> **Auto-archived**: this plan was swept on 2026-07-04 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Extract a per-step detail worker function in generate_detail

## Summary

Pull the concurrency-safe part of `generate_detail`'s per-step loop body — render the prompt, shell out through the `invoker=` seam, parse, checkpoint, and write the detail file — into a single worker function in `plan_tool/detail.py`. The worker returns the step's `DetailResult` plus a deferred plan-update record `(step_id, detail_rel)` and **never mutates the plan `.md`**. The loop keeps every plan-mutating and cross-step side effect (the `update_step_detail_field` write, the `budget.enabled` convergence loop, `escalate_to_split`/Phase B, lesson extraction) exactly where it is and calls the worker inline, one step at a time. This is a behavior-preserving refactor: at the current single-threaded path the on-disk plan, the `DetailResult` list, the run-log phases, and stderr output are all unchanged. It exists only to give step 2 a clean unit to dispatch concurrently.

## Table of Contents

- [Why](#why) — why the loop body must be split before concurrency can land
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files this step touches
- [Implementation](#implementation) — the worker boundary, what it returns, and what must stay serial
- [Tests](#tests) — characterization tests that pin the serial behavior, plus a focused worker test
- [Test-creation order (refactor step)](#test-creation-order-refactor-step) — write/confirm characterizations first, keep them green after
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — the stdlib docs relevant to this step
- [Deferred](#deferred) — concurrency, the guard, and the CLI flag left to later steps

## Why

`generate_detail` in `plan_tool/detail.py` does all its per-step work inline in one long `for step in target_steps:` loop. Inside that body, the cheap-to-parallelize part (render → invoke → write) is fused with the parts that **must** stay serial: the `update_step_detail_field` call that rewrites the shared plan frontmatter, the `--iterate` convergence loop that re-audits and `apply_finding`s against the live plan/detail on disk, and the `escalate_to_split` path that renumbers steps. There's no seam to hand one step's authoring work to a thread without dragging the plan-mutating tail along with it. Step 2 needs exactly that seam. Extracting the worker now — and proving the extraction changes nothing at the single-threaded path — lets step 2 add the `ThreadPoolExecutor` dispatch as a small, low-risk diff instead of restructuring a 600-line loop and adding concurrency in the same change.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/detail.py` — extract a per-step worker function out of `generate_detail`'s loop body; call it inline from the loop. Add a small return record if you choose that shape (see Implementation). No public signature change to `generate_detail`.
  - `tests/test_detail.py` — confirm the existing `generate_detail` integration suite still passes unchanged (the characterization gate); optionally add a focused unit test that drives the worker directly with a fake invoker.

## Implementation

**Goal:** lift the per-step body of `generate_detail`'s `for step in target_steps:` loop into a worker function, and have the loop call it inline. The cut line is "does this mutate the plan file or depend on cross-step ordered state?" — if no, it belongs in the worker; if yes, it stays in the loop.

**Put in the worker (the concurrency-safe prefix).** Everything a single step needs to turn itself into a written detail file, given an immutable snapshot of context:
- Derive `output_path` via `derive_detail_path`, take the **sibling snapshot as a worker input** (the caller runs `_discover_siblings` and passes the result in — `_discover_siblings` is *not* called inside the worker), run the optional foundational sweep, and render the prompt via `render_detail_prompt`. Passing the snapshot in (rather than discovering inside the worker) is what lets step 2 hand every worker one pre-dispatch snapshot; step 2 is authoritative on within-run sibling visibility under concurrency.
- Handle the `dry_run` early-return (a `DetailResult` carrying the rendered `prompt`, no write) and the already-exists / resume skip paths — these only produce a `DetailResult`, they don't touch the plan. **No interactive stdin read inside the worker.** The skip paths today call `_confirm_resume(prompt_fn, …)` on a checkpoint hit and the replace-existing-detail prompt, both driven by `prompt_fn` (default `builtins.input`). Under `jobs > 1` the only runnable invocation (`--jobs N --no-iterate --no-split`) can fan many workers at concurrent checkpoints/existing files, racing a single stdin into garbled prompts and a nondeterministic keystroke→step mapping. So the resume/replace confirm must be **resolved serially in the pre-scan before any worker is dispatched** (or auto-declined when `jobs > 1`) — never read from a worker thread. At `jobs == 1` the confirm stays inline exactly as today.
- The retry-invoke loop: call `invoker(attempt_prompt)` (the seam stays the literal `invoker` parameter — do not rename or wrap it), strip the structural block with `_STRUCTURAL_BLOCK_RE`, parse with `parse_detail_response`, log parse failures via `_log_parse_failure`, and capture `step_purity_findings` on the parsing attempt.
- Save the checkpoint right after a successful parse (`save_checkpoint`) — keep this ordering; it's the "claude succeeded but the file isn't durable yet" hedge.
- The missing-files soft `warn`, the `_archive_existing_detail` call, the `output_path.write_text(body + "\n", ...)`, and the `_archive_orphan_details` sweep.
- Compute the deferred plan-update record `(step.id, _repo_relative(output_path, repo_root))` and return it **instead of calling `update_step_detail_field`**.

**Keep in the loop (serial, plan-mutating, or cross-step).** After the worker returns, the loop does, in order, exactly what it does today:
- The adoption pre-pass that reattaches orphaned `detail:` pointers (it calls `update_step_detail_field`) — leave it ahead of the loop, untouched.
- Compute the sibling snapshot (`_discover_siblings`) for the step **before** calling the worker, and pass it in. At `jobs == 1` this runs inline per step exactly when it does today, so a later step still sees earlier steps' just-written files — behavior is unchanged. Hoisting it to one pre-dispatch snapshot for all workers is step 2's concern.
- `update_step_detail_field(plan_path, step.id, detail_rel)` for the returned record, then `step.detail = detail_rel`.
- `discard_checkpoint` — keep it **after** the plan-update, not in the worker, so the durability hedge holds (the checkpoint must survive until the plan pointer is set).
- Accumulating `mixed_steps` from the returned purity findings; the `budget.enabled` convergence loop; lesson extraction; and the `escalate_to_split` Phase B at the end of `generate_detail`.

**Recommended return shape.** One way: a small frozen record (e.g. `_StepAuthoringOutcome`) carrying the `DetailResult`, the `Optional[(step_id, detail_rel)]` update (None when nothing was written — dry-run, skip, parse failure, write failure), the `step_purity_findings`, and whatever the serial tail still reads (the parsed `body`, the byte/elapsed counts the run-log and convergence entry consume). The exact field set is the implementer's call — pull across the boundary only what the tail actually uses, and keep the record frozen so a worker can't smuggle in shared mutable state. Returning a `DetailResult` alone is not enough: the convergence loop and lessons pass need the parsed `body` and the purity findings.

**Constraints that are not free to vary:**
- **No plan-file write inside the worker.** The whole point is that a worker can run off-thread later. `update_step_detail_field`, `step.detail =`, the convergence loop, and `escalate_to_split` must not move into it.
- **The `invoker=` seam stays identical.** Workers call the same `invoker` parameter (defaulting to `shell_detail_invoker`). This keeps the conftest real-`claude` gate and the TESTING.md neutralization table valid — step 2 just exercises the same seam concurrently.
- **Behavior is unchanged at the single-threaded path.** The returned `DetailResult` objects, their order in the result list, the plan frontmatter, the `detail-step-NN` run-log phases, and the stderr/reporter output must all match the pre-refactor run. This is the gate for the refactor.
- **Per-attempt run-log events stay per-step.** `claude_call_start`, `bind_shell_sink`, and `parse_failure` are emitted per attempt inside the worker for now; making them thread-safe / ordered is step 2's job, not this one.
- **The reporter `start_step` handle and the `invoke_idx`/`invoke_total` counter** can move into the worker or be passed in — at the single-threaded path either reads the same. Don't redesign the counter here; step 2 owns ordered post-join emission.

**Foundational logic for this step:** the per-step "render → invoke → write a detail file" sequence. The only other authoring sites — `split_step` and the in-loop split halves around `escalate_to_split` in `plan_tool/detail.py` — re-enter `generate_detail` recursively rather than duplicating the sequence, so they ride the new worker for free; no separate consolidation is needed. The other `invoker(prompt)` calls in `collect_detail_quality_findings` drive the *review* prompt (`prompts/detail-quality.md`), not authoring, so they are out of scope and must not be folded into the worker.

## Tests

Existing integration suite in `tests/test_detail.py` (these are the characterization tests — confirm each stays green, unmodified):
- `TestGenerateDetailHappyPath` — a clean multi-step run writes every detail file and sets every `step.detail` pointer.
- `TestGenerateDetailIdempotency` — a re-run skips steps whose detail file already exists.
- `TestGenerateDetailResume` — a valid checkpoint resumes without a claude call; the checkpoint is discarded after a durable write.
- `TestGenerateDetailDryRun` — `dry_run=True` returns prompts, writes nothing, makes no plan change.
- `TestGenerateDetailFailures` — an unparseable response yields a failed `DetailResult` for that step and does not abort siblings.
- `TestGenerateDetailOrphanSweep` — stale `NN-*.md` siblings are archived after a successful write.
- `TestGenerateDetailParseFailureLogging` — a rejected response is dumped under `parse-failures/` before retry.
- `TestGenerateDetailProgress` — reporter start/complete and the `detail-step-NN` run-log phases fire in the expected shape.
- `TestInteractiveSplit` / `TestUnattendedSplitRecommendation` — the `escalate_to_split` Phase-B behavior is unchanged after the tail stays in the loop.

New (optional) unit test, `tests/test_detail.py`:
- `test_author_step_worker_writes_and_returns_update_record` — drive the worker directly with a fake invoker; assert it writes the file, returns the `(step_id, detail_rel)` record, and makes no change to the plan `.md` on disk.
- `test_author_step_worker_parse_failure_returns_no_update` — a worker whose invoker returns garbage returns a failed `DetailResult` and a `None` update record (no write, no plan change).

### Test-creation order (refactor step)

This is a behavior-preserving refactor, so the characterization tests come **first**:
1. Before touching `generate_detail`, run the existing integration suite above and confirm it is green at HEAD — it already pins the serial behavior (happy path, idempotent skip, resume/checkpoint discard, dry-run, failure isolation, orphan sweep, parse-failure logging, progress/run-log phases, split). Treat these as the characterization set; do not edit them.
2. Extract the worker and rewire the loop to call it inline.
3. **Pass-unchanged gate:** the same characterization tests must pass again with no edits. Any required change to those tests means the refactor altered behavior and is wrong — fix the extraction, not the test.
4. Only then add the focused worker-level unit tests, which pin the new seam directly.

## References

- [concurrent.futures — Launching parallel tasks](https://docs.python.org/3/library/concurrent.futures.html) — read only for context on what the extracted worker will be dispatched into in step 2; this step adds no concurrency.
- [subprocess — Subprocess management](https://docs.python.org/3/library/subprocess.html) — how the `invoker` seam ultimately spawns and waits on the `claude` binary, relevant to keeping per-step failure isolation intact during the extraction.

## Deferred

- The `ThreadPoolExecutor` concurrent dispatch — step 2. This step only creates the worker and calls it inline.
- The `--jobs N` flag (explicit integer `>= 1`; no `0`/auto mode) and its `cmd_detail` threading — step 3.
- Refusing `--jobs > 1` with `--iterate`/`--split` and degrading `--jobs > 1 --step N` to serial — step 4.
- Buffering/ordering per-step run-log and reporter events for completion-order independence — step 2 owns this; for this step the events stay inline and in step order naturally.
- CLI reference regeneration and the TESTING.md note about the concurrently-exercised seam — step 5.

## Acceptance criteria

- The per-step render → invoke → parse → checkpoint → write sequence lives in a single extracted worker function; the `for step in target_steps:` loop calls it inline, one step at a time.
- The worker performs **no plan-file write**: `update_step_detail_field`, `step.detail =`, the `budget.enabled` convergence loop, and `escalate_to_split` stay in the loop and do not move into the worker.
- The sibling snapshot is a worker **input**, not an in-worker call: `_discover_siblings` runs in the caller and the result is passed in. At `jobs == 1` the caller computes it inline per step, so a later step still sees earlier steps' just-written files — unchanged behavior.
- The worker returns the step's `DetailResult` plus a deferred plan-update record `(step_id, detail_rel)` (and the parsed `body` / purity findings the serial tail reads); the record is `None` on dry-run, skip, parse failure, or write failure.
- The `invoker=` seam is unchanged: the worker calls the same `invoker` parameter (defaulting to `shell_detail_invoker`), so the conftest real-`claude` gate and the TESTING.md neutralization table still hold.
- Behavior is unchanged at the single-threaded path: the `DetailResult` objects and their order in the result list, the plan frontmatter on disk, the `detail-step-NN` run-log phases, and the stderr/reporter output all match the pre-refactor run.
- Pass-unchanged gate: every characterization test in `tests/test_detail.py` listed under `## Tests` stays green with no edits; any required edit to those tests means the extraction altered behavior and is wrong.
- `discard_checkpoint` runs after the plan-update (not in the worker), and `save_checkpoint` runs in the worker right after a successful parse, preserving the durability hedge.

