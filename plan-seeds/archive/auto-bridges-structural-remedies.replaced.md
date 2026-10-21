> **Replaced**: this file has been superseded by `docs/implementation-plans/2-auto-bridge-structural-remedies.md`.
> Preserved here for history; do not edit.

# Plan seed: auto-bridges — gate-and-actuate the recommend-only structural remedies

Builds the **auto-bridges arm** of BACKLOG **#70** (Structural-remedy vocabulary:
remaining convenience arms). The detection + *recommendation* half of the
split/merge/scope-out/re-seed vocabulary is shipped; several remedies today print
a recommendation but stop short of running the actuator that already exists. This
plan wires those bridges — each behind the tool's standard **apply-or-recommend
gate** — so the operator can actuate from the diagnosis without re-typing the
command by hand.

> **Scope: bridges only — no new detection, no new actuator logic.** Every
> producer (the finding) and every executor (the mutation) already exists. This
> plan adds the *gated wiring between them* and nothing else. It introduces no new
> `review.Recommendation` source token and no new structural primitive.

## Guiding principle

**Detection is unconditional; mutation stays gated + confirmed.** Mirror the
apply-or-recommend gate shape already used twice in the codebase —
`launcher.py:escalate_to_split` and `scope_out.py:scope_out_step`: the default
path spends no Claude and only *recommends*; it mutates **only** when all of
(a) an explicit `--apply` opt-in, (b) an interactive TTY **confirm `yes`** (which
`-y` deliberately bypasses), and (c) the relevant read-only **safety gate** hold.
Every unattended / non-TTY / declined / unsafe path recommends only. This is the
third+ instance of that gate shape; reuse it, don't reinvent it.

**Never mutate the plan's spine unattended.** The *structural re-seed* limit
(split-everything / `create --from-existing`) stays human-authored and is **out of
scope** here — an auto-re-decompose that guesses wrong silently reshapes the plan.
Only the *localized / bounded* remedies below get a bridge.

## The three bridges

### 1. Scope-out bridge — `convergence` → `scope_out_step`
`plan-tool convergence` (read-only diagnostic) already classifies
`FORK_SCOPE_OUT` and **prints** the runnable `plan-tool scope-out <name> --step N`;
the executor (`scope_out.py:scope_out_step`) already exists and already carries the
apply-or-recommend gate. Bridge: let the operator actuate the printed carve behind
an explicit opt-in.
- **Contract decision (resolve first):** `convergence` is defined as read-only,
  no-mutation, always-exits-0. Do **not** silently break that. Either (a) keep
  `convergence` pure and treat the bridge as an explicit new opt-in flag that
  changes the contract only when passed (e.g. `--apply-scope-out`, gated exactly
  like `scope-out --apply`), or (b) leave `convergence` pure and add the bridge on
  the `scope-out` side. Pick (a) or (b) and state why in the plan.
- Reuse `scope_out_step`'s `ScopeOutResult` outcomes verbatim (`applied` /
  `recommended` / `unsafe` / `empty-plan` / `step-missing`); only `applied` mutates.

### 2. Merge bridge — `granularity-merge` → `plan-tool merge`
`granularity.py` emits `granularity-merge` for adjacent fragmented dependent steps;
it is recommend-only today (kept out of `APPLY_ELIGIBLE_SOURCES`), so re-combining
is always hand-run via `plan-tool merge`. Bridge: from a surfaced `granularity-merge`
finding, offer the gated `plan-tool merge --steps N --steps M`.
- Reuse the existing merge executor and its safety gate (`_merge_is_safe` — no
  non-`PENDING` step after the region). The bridge selects the flagged contiguous
  member set as the merge args; the operator confirms.
- Keep it recommend-only unless `--apply` + confirm hold, same as bridges 1 and 3.

### 3. Re-ground bridge — reconcile's code-grounded re-ground finding → mark-done / re-baseline
Reconcile's `review.py:_reground_already_built_recommendation` fires on **≥2 distinct
already-built steps** and reuses the `granularity-merge` literal — but its remedy is
**re-ground / re-baseline (mark the already-built steps done, or re-decompose),
NOT a blind `merge`.** So this bridge is deliberately *different* from bridge 2.
- **Open design point:** the actuator here is "mark these steps done / re-baseline,"
  which may not have a first-class command yet. Decide whether to (a) reuse an
  existing status-advance path behind the gate, or (b) add a small `--apply`
  mark-done actuator. Do **not** route this finding to `plan-tool merge` — that
  would conflate re-ground with structural merge (the exact confusion the
  `granularity-merge`-literal-but-neutral-`triage_reason` routing already guards).

## Invariants to hold (carry into every step)
- One reused gate shape across all three bridges: `--apply` + TTY confirm (`-y`
  bypasses confirm) + the remedy's own read-only safety gate; unattended / non-TTY /
  declined / unsafe ⇒ recommend-only, spends no Claude.
- No new `review.Recommendation` source token; no new structural primitive; the
  actuators (`scope_out_step`, merge executor) are reused as-is, re-parsing the plan
  from disk on each call.
- Frozen result objects only `applied` outcomes mutate; every bridge reports its
  outcome so the caller can distinguish recommended-vs-applied.

## Explicitly out of scope
- The **structural re-seed** limit (`create --from-existing`) — stays manual.
- **Multi-step / multi-region carve** — `scope-out`'s single-`--step N` limitation
  and the multi-region `convergence` focus are a *separate* #70 arm.
- **Code-reveals-a-split detection** — the missing producer is the third #70 arm,
  not a bridge (there is nothing to bridge until it emits a finding).
- Any change to how the findings are *detected* — this plan only actuates existing
  findings.

## Reused surfaces (verify before extending)
- `launcher.py:escalate_to_split` + `scope_out.py:scope_out_step` — the two existing
  apply-or-recommend gate implementations to mirror.
- `scope_out.py` (`scope_out_step`, `compute_narrow` blockers, `ScopeOutResult`).
- The merge executor + `detail.py:_merge_is_safe` / `split_safety.split_is_safe`.
- `convergence_diagnosis.py` (`classify_fork` → `FORK_SCOPE_OUT`, `render_diagnosis`).
- `review.py` (`granularity-merge` routing via the neutral `triage_reason`;
  `_reground_already_built_recommendation`).
- `granularity.py` (`granularity-merge` producer).

## Relationship to #57
Bridge 1 overlaps the **opt-in auto-execution** lever tracked in BACKLOG **#57**
(wire the recommended localized `plan-tool split` / scope-out to run behind a flag).
If #57 is picked up first, fold bridge 1 into it; otherwise this plan can carry it.
State the chosen split in the plan so the two entries don't double-build.
