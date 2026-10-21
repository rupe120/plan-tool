# Plan seed: granular per-stage resume (+ cooperative time-budget backstop)

> **SUPERSEDED (2026-07-12) — do not `create` from this as-is.** §A (the per-stage
> **stage manifest**, BACKLOG **#88**) is **obsolete**: tracing the code showed
> resume is already durable at per-`claude`-call granularity everywhere
> (`checkpoint.py`, per-finding saved-review annotations, plan pointers, **#122**
> per-step commits), so a second ledger would only duplicate it — see the #88
> backlog entry. §D (the cooperative **`--time-budget`**, BACKLOG **#123**) **shipped**
> for the convergence loops (a hard wall-clock cap in `convergence.py`, no manifest
> needed) — see the #123 entry for remaining surfaces. Kept for history; the live
> follow-ups are the narrowed #88 (`run`-step `claude` memoization) and the #123
> apply-walk / run-batch surfaces. §E/#124 (floor-breaker) is still open.

This file is a `plan-tool create` input. Use it via:

    plan-tool create --from-existing plan-seeds/granular-stage-resume.md --iterate

It is **not** itself a plan — `plan-tool create` consumes the prose below and proposes a step
decomposition; the author then runs `plan-tool detail` per step.

> **Scope boundary — make durable progress fine-grained, then add a deadline backstop.** The primary
> fix is a **per-stage operation manifest** so a long op checkpoints after **every `claude` round-trip**
> and resumes at the first incomplete stage — a kill loses ≤1 call, not the whole op. The secondary,
> folded-in layer is a **cooperative `--time-budget`** that stops cleanly at a stage boundary before an
> external execution ceiling. It does **not** change what the ops *produce*, redesign the checkpoint
> staleness model, or attempt to resume *inside* a single `claude` call (impossible — the granularity
> floor; see §E).

Source: **BACKLOG #88** (per-stage manifest — the primary/substrate) with **#123** (cooperative
time-budget — the backstop) folded in on top; relates to **#122** (per-step commit) and **#108**
(durable per-step run marker). When this work ships, its final docs/status step must reconcile
**both #88 and #123** in `BACKLOG.md` (remove or mark plan-authored) per BACKLOG.md's rule.

---

## Overview

Today a killed long op loses everything since its last **coarse** durable boundary, because resume is
whole-unit: `checkpoint.py` memoizes **one opaque artifact per named checkpoint** and auto-discards on
success (`checkpoint.py:66,145,212`), `run` advances at **whole-step** granularity, and `detail --commit`
commits once per **whole batch** (#122). So a `detail` step interrupted mid-authoring, or a
`completeness-audit` killed after its expensive `claude` pass but before it saved, re-runs from the top.

Make progress **fine-grained**: a **stage manifest** records the ordered internal stages each long op
already passes through (for a `detail` step: `render → invoke → parse → checkpoint → write → post-gates`),
with each stage's inputs-fingerprint and a completed/failed marker, so a re-run **resumes at the first
incomplete stage** and spends **no `claude`** on completed ones. Then layer a **cooperative
`--time-budget`** on top: check a deadline **at each stage boundary** and, when near budget, stop cleanly
(the manifest is already durable), commit under `--commit`, print a resume hint, and exit 0 — instead of
being SIGKILL'd mid-op.

## Problem statement — grounded in a real case

Driving `deferred-concept-signoff-gate` through `detail` + completeness under a harness's hard **10-min
per-command execution cap** (2026-07-11) required *repeated* manual commit-and-resume: `detail` steps
authored but uncommitted at the kill, a parallel `completeness-apply` killed after its replay writes but
before its commit, an audit killed on a trailing step after it had already saved its report. The root is
**granularity**: the natural units (one `detail` step, one audit pass) are 3–6+ min because each wraps
one or more `claude` round-trips, so a 10-min cap catches you **mid-unit**, and coarse checkpointing loses
that unit's work. A time-budget alone can't help when a *single unit* exceeds the budget — only finer
durable stages can. (`run_log.py` already emits `phase_start`/`phase_end` around these stages —
`run_log.py:125,133,635,641` — so the boundaries exist; nothing persists a resumable ledger over them.)

## Architecture

### A. The stage-manifest leaf (`plan_tool/stage_manifest.py`, NEW) — generalizes `checkpoint.py`

A stdlib-only ledger leaf, a **sibling / generalization of `checkpoint.py`** (which it reuses, not
forks). Persists an ordered `StageManifest` under `.plan-tool/…/<slug>/` (beside checkpoints), keyed by
**operation + step**. Each `Stage` carries: `name` (matches the run-log phase), an **inputs-fingerprint**
(reuse `compute_input_hash`, `checkpoint.py:102`), a `completed | failed` marker, and a pointer to (or
inline of) its artifact. Top-level: `plan_slug`, `op`, `step_id`, ordered `stages`, `updated_at`.
**Preserve `checkpoint.py`'s conventions**: the staleness/expiry model (`load_if_valid` +
`DEFAULT_MAX_AGE_SECONDS`, `checkpoint.py:145`) and **auto-discard-on-clean-success** — a fully-completed
op clears its manifest (`discard_checkpoint`-style, `checkpoint.py:212`), so steady-state on-disk state
and behavior are unchanged. Register a `PersistedDataclassContract` in `data_contract.py` + a paired
`DATA_CONTRACT.md` section (drift-guarded), and document the flow in `docs/*_RESUME_FLOW.md`.

### B. Stages come from the run-log — one source of truth

Do **not** invent a second list of stages. The stage boundaries are exactly the `phase_start` /
`phase_end` events `run_log.py` already emits (`run_log.py:635,641`); the manifest records completion +
fingerprint **at those same boundaries**, so the run log and the manifest share one definition of "stage."
A resumed stage **re-emits** its run-log phases so telemetry isn't silently truncated. Keep stages
**coarse and named to match the phases** — stage granularity is a contract; too fine and the manifest
churns and drifts from the code.

### C. Wiring the resume — consult the manifest, skip completed stages

Teach the long-op loops to consult the manifest and resume at the first incomplete/failed stage,
reusing the completed-stage artifacts:
- **`detail` per-step loop** (`detail.py`) — the highest-value case: an interrupted step resumes at its
  failed stage (e.g. re-use a succeeded `invoke` artifact, redo only `write`/`post-gates`) instead of
  re-spending the authoring `claude` call.
- **`run` step executor** (`launcher.py:run_step`).
- **completeness** — audit **passes** and `completeness-apply` **findings/replay items** as stages, so a
  killed audit/apply resumes at the first unfinished pass/finding rather than re-running all.
An invalidated inputs-fingerprint (a stage's inputs changed) discards that stage and everything after it
(no stale-stage reuse — mirror `load_if_valid`).

### D. The cooperative time-budget backstop (#123, folded in)

A tiny deadline leaf with an **injected clock** (the `rate_limit_loop.py:117` `clock=time.time` seam is
the precedent — inject for tests, never call `time.time` inline): `Deadline(budget_s, clock)` exposing
`remaining()` and `should_stop(headroom)`. Resolution: `--time-budget <sec>` flag →
`PLAN_TOOL_TIME_BUDGET` env → unlimited (**default off** — no budget set means no clock is consulted and
behavior is byte-for-byte unchanged). Check `should_stop()` **only at stage boundaries** (§B); on stop:
let the current stage finish (its manifest entry is already durable from §A), commit under `--commit`
(#122), close the run log as a **clean partial** (not a crash), print `resume with <cmd>`, and **exit 0**.

**Design target: aim for ≤5 minutes per unit of work, not the ~10-minute hard cap.** Callers' execution
ceilings vary and some (a foreground-capped harness) sit near 10 min, but the arc is designed to a
**5-minute target** so every resumable unit and the cooperative stop land with real headroom — never at
the cliff. The recommended/documented default budget targets ~5 min. This target is what makes the
floor-breaker (§E / #124) *central rather than deferred*: a single `claude` call is already 3–6 min, so
hitting a 5-min unit ceiling requires shortening the long calls, not just stage-granularity + a backstop.

### E. The granularity floor — binding against the 5-minute target

The finest atomic unit is **one `claude` round-trip** (~3–6 min); you cannot checkpoint *inside* a call.
So even perfect stage-granularity leaves a floor: a single over-long call can overrun the budget on its
own. Against the ~10-min hard cap that floor was slack; against the **≤5-min design target (§D) it is
binding** — a 6-min call already exceeds it. This seed still delivers its own value (a kill loses ≤1 call
and resumes cheaply, and the backstop stops cleanly), but hitting the 5-min target is a **co-equal
requirement handled by the floor-breaker arc (#124), not a deferred nicety**: measure the long single
calls (a `detail` step's authoring call, a `completeness-audit` conceptual pass) and shorten them (split
one big call into several checkpointed sub-calls) and/or run them async so wall-clock isn't held. #124 is
elevated by the 5-min target; sequence it right after #88 lands (profile first — split only where the
quality cost is acceptable).

## Out of scope

- Resuming *inside* a single `claude` round-trip — impossible (the §E floor).
- Reducing individual call length (prompt-splitting) or async/background call execution — the
  floor-breaker; a separate arc.
- Auto-detecting the caller's execution ceiling (CI/cron/harness) — MVP is explicit `--time-budget`/env.
- Synthesis-output caching across reruns — overlaps **#43**; coordinate, don't absorb.
- Any change to what the ops *produce* — this is purely durability/resume + a deadline.

## Risks

- **Stage granularity is a contract** — too fine and the manifest churns / drifts from the code; keep
  stages coarse and named to the run-log phases.
- **Stale-artifact reuse** — a resumed stage must not reuse an artifact whose later-stage assumptions
  changed; the inputs-fingerprint must cover **every** input the resumed stage depends on, not just the
  first stage's.
- **Truncated telemetry** — a resumed stage must re-emit its run-log phases, or the run log looks
  truncated; interacts with drift detection and the `--commit`/gate flow.
- **Boundary-only stop** — the time-budget must be checked *only* at stage boundaries; a mid-stage stop
  reintroduces the partial-state problem it solves.
- **Deadline exit must not read as failure** — exit 0 + an explicit "stopped: N of M stages done, resume
  with …", and a clean run-log close.
- **Concurrent runs** — carry forward (or tighten) `checkpoint.py`'s concurrent-run caveat.

## Testing

- **Manifest leaf unit tests** (`tests/test_stage_manifest.py`): record/complete/fail stages; a
  mismatched inputs-fingerprint invalidates a stage and everything after it (parity with
  `load_if_valid`); a fully-successful op **leaves no manifest** (auto-discard parity).
- **Resume-at-stage-k** per op: an op forced to fail at stage *k* (stages `0..k-1` complete + unchanged)
  re-runs executing **only** stages `≥ k` and spends **no `claude`** on the completed earlier stages
  (assert via a fake invoker call-count); the resumed stage re-emits its run-log phases.
- **Time-budget** (fake clock): a run with `--time-budget T` whose work exceeds T stops at the first
  stage boundary past T, commits every completed stage (under `--commit`), exits **0** with a resume
  hint, and a re-run finishes the remainder; a stage in progress when the budget elapses is allowed to
  finish (**never** a mid-stage kill); with no budget set, output and call-count are unchanged.
- **Resolution precedence:** `--time-budget` flag > `PLAN_TOOL_TIME_BUDGET` env > unlimited.
- **data-contract drift:** `tests/test_data_contract.py` green with the registered `StageManifest`
  contract + new `DATA_CONTRACT.md` section.

## Acceptance criteria

- An op that fails/stops at stage *k* (stages `0..k-1` complete and unchanged) re-runs and executes
  **only** stages `≥ k`, spending no `claude` on the completed earlier stages.
- A fully-successful op **leaves no manifest** behind (parity with `checkpoint.py` auto-discard).
- A manifest whose inputs-fingerprint no longer matches is invalidated — no stale-stage reuse (matching
  `load_if_valid`).
- A resumed stage **re-emits** its run-log `phase_start`/`phase_end`, so telemetry is not truncated.
- With `--time-budget T`, a long op stops at the first stage boundary past T with every completed stage
  committed (under `--commit`), exits **0** with a resume hint, and a re-run completes the remainder; a
  stage already running when the budget elapses finishes (never a mid-stage kill).
- With **no** budget set, output, call-count, and timing are unchanged (no clock is consulted).
- The stage list is **sourced from the run-log phases**, not a second hand-maintained list.
- `tests/test_data_contract.py` passes with `StageManifest` registered + documented in `DATA_CONTRACT.md`.
- The final step reconciles **BACKLOG #88 and #123**.

## Deferred

- **Floor-breaker (BACKLOG #124) — NOT deferred under the 5-min target; see §D/§E.** Shorter `claude`
  calls (prompt-splitting / fewer jobs per call) and/or async execution are what fit a *single* over-long
  call (3–6 min) under the ≤5-min target, so #124 is a **co-equal layer** to be sequenced right after #88
  (profile the long calls first, split only where the quality cost is acceptable) — not left to "someday".
- Auto-detecting the caller's execution ceiling.
- Synthesis-output caching across reruns (**#43** — coordinate separately).
