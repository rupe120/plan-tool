> **Replaced**: this file has been superseded by `docs/implementation-plans/2-auto-bridge-structural-remedies.md`.
> Preserved here for history; do not edit.

## Overview

Builds the **auto-bridges arm** of BACKLOG **#70** (Structural-remedy vocabulary: remaining convenience arms). The detection and *recommendation* half of the split/merge/scope-out/re-seed vocabulary already ships, but several remedies today print a recommendation and stop short of running the actuator that already exists, forcing the operator to re-type the command by hand. This plan wires three of those bridges — scope-out (`convergence` → `scope_out_step`), merge (`granularity-merge` → `plan-tool merge`), and re-ground (reconcile's `_reground_already_built_recommendation` → mark-done / re-baseline) — each behind the tool's standard **apply-or-recommend gate** so the operator can actuate straight from the diagnosis. It adds only the gated wiring between existing producers and executors: no new detection, no new actuator logic, no new `review.Recommendation` source token, and no new structural primitive.

## Problem statement

The structural-remedy vocabulary detects mis-decompositions and prints runnable remedy commands, but the operator must copy and re-type them by hand — the diagnosis and the actuation are disconnected even though both the finding producer and the mutation executor already exist. Concretely: `plan-tool convergence` classifies `FORK_SCOPE_OUT` and prints `plan-tool scope-out <name> --step N` but never runs it; `granularity.py`'s `granularity-merge` finding is recommend-only (kept out of `APPLY_ELIGIBLE_SOURCES`) so re-combining is always hand-run via `plan-tool merge`; and reconcile's `_reground_already_built_recommendation` fires on already-built steps but its re-ground / re-baseline remedy has no bridged actuator. The user-visible symptom is friction and transcription error: a correct, already-computed remedy requires a manual round-trip to apply.

## Architecture

Three bridges, each reusing the **apply-or-recommend gate** shape already implemented twice — `launcher.py:escalate_to_split` and `scope_out.py:scope_out_step`. The gate: the default path spends no Claude and only *recommends*; it mutates **only** when all of (a) an explicit `--apply` opt-in, (b) an interactive TTY **confirm `yes`** (which `-y` deliberately bypasses), and (c) the relevant read-only **safety gate** hold. Every unattended / non-TTY / declined / unsafe path recommends only.

**Bridge 1 — Scope-out (`convergence` → `scope_out_step`).** `plan-tool convergence` is contractually read-only, no-mutation, always-exits-0, so the bridge must not silently break that. Resolve first between (a) keeping `convergence` pure and adding an explicit new opt-in flag (e.g. `--apply-scope-out`, gated exactly like `scope-out --apply`) that changes the contract only when passed, or (b) leaving `convergence` pure and adding the bridge on the `scope-out` side. Pick (a) or (b) and state why in the plan. Reuse `scope_out_step`'s `ScopeOutResult` outcomes verbatim (`applied` / `recommended` / `unsafe` / `empty-plan` / `step-missing`); only `applied` mutates.

**Bridge 2 — Merge (`granularity-merge` → `plan-tool merge`).** From a surfaced `granularity-merge` finding (adjacent fragmented dependent steps), offer the gated `plan-tool merge --steps N --steps M`. Reuse the existing merge executor and its safety gate (`_merge_is_safe` — no non-`PENDING` step after the region). The bridge selects the flagged contiguous member set as the merge args; the operator confirms. Recommend-only unless `--apply` + confirm hold, same gate as bridges 1 and 3.

**Bridge 3 — Re-ground (reconcile's `_reground_already_built_recommendation` → mark-done / re-baseline).** This finding fires on **≥2 distinct already-built steps** and reuses the `granularity-merge` literal, but its remedy is **re-ground / re-baseline (mark the already-built steps done, or re-decompose), NOT a blind `merge`** — so this bridge is deliberately different from bridge 2 and must **not** route to `plan-tool merge` (that would conflate re-ground with structural merge, the exact confusion the neutral-`triage_reason` routing already guards). Open design point: the actuator ('mark these steps done / re-baseline') may not have a first-class command yet; decide whether to (a) reuse an existing status-advance path behind the gate, or (b) add a small `--apply` mark-done actuator.

## Out of scope

- **Structural re-seed limit** (split-everything / `create --from-existing`) — stays human-authored; an auto-re-decompose that guesses wrong silently reshapes the plan's spine.
- **Multi-step / multi-region carve** — `scope-out`'s single-`--step N` limitation and the multi-region `convergence` focus are a separate #70 arm.
- **Code-reveals-a-split detection** — the missing producer is the third #70 arm, not a bridge (nothing to bridge until it emits a finding).
- **Any change to how findings are detected** — this plan only actuates existing findings; it adds no new detection.

## Risks

- **Breaking `convergence`'s read-only / always-exits-0 contract** — bridge 1 must not silently mutate from a command defined as pure; mitigated by requiring the mutation path behind an explicit new opt-in flag (or moving the bridge to the `scope-out` side) so the contract changes only when the flag is passed.
- **Conflating re-ground with structural merge** — bridge 3 reuses the `granularity-merge` literal but has a different remedy; routing it to `plan-tool merge` would defeat the neutral-`triage_reason` guard. Mitigated by keeping bridge 3 on a mark-done / re-baseline actuator, never `merge`.
- **Double-building with #57** — bridge 1 overlaps the opt-in auto-execution lever tracked in BACKLOG #57; mitigated by stating the chosen split in the plan (fold bridge 1 into #57 if that's picked up first, otherwise carry it here).
- **Unattended mutation** — the reused gate must recommend-only on every unattended / non-TTY / declined / unsafe path; a gap would let a bridge mutate without confirmation.
- **Re-ground actuator may not exist yet** — the 'mark steps done / re-baseline' path may need a small new `--apply` actuator, an open design point that could widen scope if a first-class command has to be added.

## Testing

Follow the project's unit-first convention (TESTING.md): default to unit tests exercising one function/class in isolation, mirroring source modules (`plan_tool/X.py` → `tests/test_X.py`), and neutralize the invoker seam — though these bridges spend no Claude on the default path, so most coverage is deterministic. Unit-test each bridge's gate decision across the matrix: unattended, non-TTY, declined confirm, `-y` bypass, unsafe safety-gate, and the `--apply` + confirm success path — asserting only `applied` outcomes mutate and every other path recommends only and spends no Claude. Assert bridge 3 never routes to `plan-tool merge`. Add `@pytest.mark.integration` tests only for the CLI wiring — driving `plan-tool convergence` (or the chosen bridge-1 surface) and `plan-tool merge` entry points end-to-end to confirm the flag parses, the safety gate fires, and the frozen result object reports recommended-vs-applied. Existing suites for the reused surfaces must still pass (`tests/test_scope_out.py`, the merge executor tests, `tests/test_convergence*`, `tests/test_review.py`, `tests/test_granularity.py`).

## Acceptance criteria

- The scope-out bridge mutates a plan **only** when `--apply` (or the chosen opt-in flag) + TTY confirm + safety gate all hold; every unattended / non-TTY / declined / unsafe invocation exits without mutation and spends no Claude.
- If bridge 1 keeps `convergence` pure, `plan-tool convergence <name>` with no bridge flag still exits 0, mutates nothing, and writes no run-log entry.
- The scope-out bridge reuses `ScopeOutResult`'s outcomes verbatim (`applied` / `recommended` / `unsafe` / `empty-plan` / `step-missing`) and only `applied` mutates.
- From a `granularity-merge` finding, the merge bridge offers `plan-tool merge` over the flagged contiguous member set and applies it only when `--apply` + confirm + `_merge_is_safe` hold.
- The re-ground bridge never routes to `plan-tool merge`; its actuator is mark-done / re-baseline behind the same gate.
- No new `review.Recommendation` source token and no new structural primitive are introduced.
- Each bridge reports its outcome so the caller can distinguish recommended-vs-applied.

## Deferred

- **Re-ground first-class mark-done actuator** — if the mark-done / re-baseline path has no existing status-advance command to reuse, adding a small `--apply` actuator may be deferred or scoped as its own step pending the open design decision.
- **Bridge 1 vs #57 ownership** — if BACKLOG #57 (opt-in auto-execution) is picked up first, bridge 1 folds into it rather than shipping here; the chosen split is stated in the plan so the two entries don't double-build.
