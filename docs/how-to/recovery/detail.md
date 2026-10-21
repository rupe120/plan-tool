# `detail` resume & recovery

Resume/recovery specifics for `plan-tool detail <name>`. The shared machinery
(iteration session, crash handler, checkpoint contract) is in
[`RESUME_FLOW.md`](README.md); the happy path is in
[`DETAIL_FLOW.md`](../pipeline/detail.md).

## TL;DR

- **Resume is per-step.** Each step's authored body is checkpointed under
  `detail-step-NN.json`. A re-run skips steps whose detail file already exists
  and is wired into the plan (`step.detail` set), unless `--force`.
- **The detail-quality convergence loop has no per-iteration checkpoint** — the
  on-disk detail file is the durable artifact, so an interrupted mid-loop step
  leaves a partially-iterated body that the next run skips entirely (already
  authored) rather than half-resuming.
- **A crash mid-step keeps finished work.** Steps already written + their
  checkpoints survive; `iteration_session` restores the SIGINT handler and emits
  any drift warning on the way out; the re-run continues from the next unauthored
  step.

## What resumes on a re-run

```
plan-tool detail <name>  (re-run after interrupt)
        │
   for each step in order:
        ├─ step.detail set AND detail file on disk?  → skip (already authored)
        │     (override with --force to re-author)
        ├─ else: render prompt → invoke claude → write file → wire step.detail
        │        → per-step convergence loop (detail-quality → apply → reaudit)
        ▼
   done
```

Granularity is the **step**, not the iteration: the per-step checkpoint
(`detail-step-NN.json`, hash-gated like every checkpoint) lets a re-run avoid
re-invoking claude for steps already authored. Within a step, the convergence
loop is *not* checkpointed — if a crash hits mid-iteration, the on-disk body is
whatever the last `apply_finding` wrote, and the next run treats that step as
done (skips it) unless `--force` re-authors from scratch.

## Crash / interrupt recovery

- `generate_detail`'s per-step convergence loop runs inside `iteration_session`,
  so a Ctrl-C or an unexpected exception still restores the SIGINT handler and
  emits any live-edit drift warning before unwinding.
- An unexpected exception propagates to `main()`'s crash handler: traceback
  saved to `.plan-tool/crashes/<slug>/`, clean message, exit `1`.
- Finished steps (file + `detail-step-NN.json`) are durable, so the re-run
  resumes at the first not-yet-authored step.

## Continuing quality iteration after the fact

The per-step detail-quality loop tightens a body in place at author time. To
re-drive quality on an already-authored plan without re-authoring, the
in-place continuation path is `plan-tool completeness-audit <slug>` (see
[`AUDIT_RESUME_FLOW.md`](audit.md)) or `detail <name> --step N
--force` to re-author a single step.

## Source map

| Concern | File |
|---------|------|
| Per-step orchestration + checkpoint | `plan_tool/detail.py` (`generate_detail`, `detail-step-NN.json`) |
| Skip-if-authored logic | `plan_tool/detail.py` (`generate_detail`; `--force` override) |
| Per-step convergence loop (no per-iter checkpoint) | `plan_tool/detail.py` (`collect_detail_quality_findings`) |
| Iteration session (drift + SIGINT cleanup) | `plan_tool/iteration_lock.py` (`iteration_session`) |
| Repair-retry shared by author prompts | `plan_tool/create.py` (`propose_*` retries — same pattern) |
| Shared engine | [`RESUME_FLOW.md`](README.md) |
| Tests | `tests/test_detail.py`, `tests/test_iteration_lock.py` |
