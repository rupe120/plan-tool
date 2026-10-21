> **Replaced**: this file has been superseded by `docs/implementation-plans/2-create-granularity-telemetry.md`.
> Preserved here for history; do not edit.

# Plan seed: create-side granularity telemetry for split decisions

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing plan-seeds/create-granularity-telemetry.md
```

It is **not** itself a plan — `plan-tool create` consumes the prose below
and proposes a step decomposition; the author then runs `plan-tool detail`
per step.

> **Scope: passive telemetry only.** This seed does not add a new split
> threshold, warning, or auto-split path. It records the create-time decisions
> needed to make future plan-level split advice evidence-based instead of
> another static-size heuristic.

---

## Overview

Wire decision telemetry into `plan-tool create`'s existing granularity and
interactive split surfaces so the tool can learn when split signals fire, when
operators act on them, and whether split proposals are usable.

The create flow already has the right hooks:

- `_granularity_split_hints(steps)` builds a dry-run `Plan`, calls
  `assess_granularity(..., stage="create", invoker=None)`, and surfaces
  `granularity-split` hints during the change-type review.
- `_ask_change_type(...)` offers `(s)plit` when an invoker is available.
- `_propose_step_split(...)` asks Claude for a two-step refactor-then-feature
  decomposition.
- `_apply_step_split(...)` performs deterministic renumbering and dependency
  rewiring.

What is missing is observation. BACKLOG #51 says per-step split hints are
mostly shipped and explicitly rejects raw static thresholds for plan size or
file count. BACKLOG #72 says create-side granularity is a decision site worth
instrumenting. This seed implements that bridge: record what create saw and
what happened, without changing create behavior.

## Problem statement

The remaining plan-splitting question is plan-level: when should create tell
the operator "this is probably more than one plan" rather than just "split this
one mixed step"? A static threshold would be noisy:

- A cohesive plan with many files may be correct as one plan.
- A small plan may still be structurally wrong if one step mixes refactor and
  feature work.
- The current precision-first granularity advisor deliberately avoids raw
  count smells because they false-flag cohesive large steps.

The tool needs data before it can tune that boundary. Today create can show a
split hint and accept a split action, but it does not persist the context or
outcome. After the session, there is no way to answer:

- How often did create-stage `granularity-split` fire?
- Which predicate fired: mixed verbs, conjoined action clauses, unrelated
  source areas?
- Did the operator accept the proposed step, override its change type, request
  a split, or skip the hint?
- Did Claude return a usable split proposal?
- Did deterministic `_apply_step_split` accept or reject the proposal?
- How large was the plan when the signal fired?

Without that record, the plan-level split remainder in BACKLOG #51 cannot be
calibrated and will keep relying on anecdote.

## Design

### Extend decision telemetry, not run logs

Use the existing `plan_tool.telemetry` substrate:

- append-only JSONL under `.plan-tool/telemetry/decisions.jsonl`
- best-effort writes that never affect command success
- per-kind convenience recorders that keep context shape consistent
- local, gitignored, observational data

Add a create-focused granularity recorder or extend `record_granularity` with
enough context to distinguish create outcomes. Keep `telemetry.py` stdlib-only.
Callers compute all plan/step/finding details before recording.

The event family should remain `kind="granularity"` unless there is a strong
schema reason to split it. Prefer a new `decision` value such as
`"create-review"` / `"create-step-outcome"` over a new kind, so future
aggregation can group all split/merge decisions together.

### Record two layers of create-side data

1. **Assessment event** — once per change-type review pass over a candidate
   step list.

   Context should include:

   - `stage: "create"`
   - `steps`: current step count
   - `split`: number of `granularity-split` findings
   - `merge`: number of `granularity-merge` findings, even if create does not
     surface merge advice interactively
   - `split_step_ids`: ids that carried split findings
   - `predicate_counts`: counts grouped by stable predicate key when available
     (`mixed-verbs`, `conjoined-clauses`, `unrelated-areas`)
   - `can_split`: whether the UI could offer `(s)plit`
   - `mode`: one of `interactive`, `yes`, `non_tty`, `checkpoint`

   This can be emitted from `_granularity_split_hints` or from the review loop
   around the advisor call. Prefer the review loop if it can record mode
   without threading mode into the leaf helper.

2. **Operator/proposal outcome event** — once per reviewed step answer, and for
   each split attempt.

   Context should include:

   - `step_id`
   - `had_split_hint`
   - `proposed_change_type`
   - `resolved_change_type`
   - `action`: `accept`, `override`, `split-requested`, `split-applied`,
     `split-unusable`, `split-invalid`, `unclassified-accepted`
   - `before_steps` / `after_steps` for split attempts
   - `proposal_len` for split proposals where parse succeeded
   - `error_class` for deterministic split rejection, with message omitted or
     shortened to avoid noisy telemetry

   Keep this strictly observational. A telemetry failure must not change any
   prompt, retry, split, or checkpoint behavior.

### Stable predicate keys

The granularity recommendations today expose human text, not an explicit
machine predicate. Do not parse prose if it can be avoided. The preferred shape
is a small internal helper in `granularity.py` that returns the predicate key
alongside the `Recommendation`, or a tiny parser over the already-stable
recommendation id suffix if that is the least invasive option.

Acceptance should pin the chosen mechanism with tests so a future wording edit
does not silently break `predicate_counts`.

### No behavioral changes

This plan must not:

- add a plan-level oversized advisory
- add or tune split thresholds
- change `assess_granularity` detectors
- change which prompts appear
- auto-accept or auto-apply splits
- make create fail when telemetry cannot be written

The point is to gather the evidence that lets a later #51/#72 follow-up decide
whether a plan-level split advisory is worth building.

## Seam citations to verify at HEAD

- `plan_tool/create.py:_granularity_split_hints` — create-stage call to
  `assess_granularity(... stage="create", invoker=None)`.
- `plan_tool/create.py:_review_step_change_types` — the review loop that knows
  mode, prompt answers, and split outcomes.
- `plan_tool/create.py:_ask_change_type` — returns `_SPLIT`, a `ChangeType`, or
  `None`.
- `plan_tool/create.py:_propose_step_split` — Claude split proposal parse seam.
- `plan_tool/create.py:_apply_step_split` — deterministic graph rewrite and
  validation.
- `plan_tool/granularity.py:_split_findings` and the three split detectors —
  source of predicate-level split signals.
- `plan_tool/telemetry.py` — `DecisionEvent`, `record_decision`,
  `record_granularity`, and `read_decisions`.
- `DATA_CONTRACT.md` — decision telemetry schema docs.
- `tests/test_create.py` — existing create split-review tests.
- `tests/test_telemetry.py` and `tests/test_data_contract.py` — telemetry
  contract tests.

## Acceptance criteria

- A create run records a granularity assessment event for the reviewed step
  list, including create stage, step count, split/merge counts, split step ids,
  predicate counts, `can_split`, and review mode.
- Interactive review records per-step outcome events for accept, override,
  unclassified accept, split requested, split applied, unusable split proposal,
  and invalid deterministic split.
- `--yes`, non-TTY, and checkpoint-resume paths record mode accurately without
  introducing prompts or changing reviewed steps.
- Telemetry write failures remain swallowed; create output, return behavior,
  and plan content are unchanged.
- Predicate counting is pinned by tests and does not depend on fragile prose
  wording unless the test explicitly locks that id format as the contract.
- `DATA_CONTRACT.md` documents any new `granularity` context keys or decision
  values.
- Existing create split tests still pass, and new tests assert telemetry events
  through `read_decisions` rather than by inspecting private file contents.

## Test plan

- Unit tests in `tests/test_create.py`:
  - split-hint assessment emits one create-stage granularity event
  - accepting a hinted step records `had_split_hint=true` and `action=accept`
  - overriding change type records `action=override`
  - split success records `split-requested` and `split-applied` with step counts
  - unusable proposal records `split-unusable` and leaves steps unchanged
  - deterministic `_apply_step_split` rejection records `split-invalid`
  - `--yes`, non-TTY, and checkpoint restore carry the right `mode`
- Unit tests in `tests/test_telemetry.py` for any new convenience recorder.
- Contract drift test update in `tests/test_data_contract.py` if the documented
  telemetry schema changes.
- Run at minimum:

```
pytest tests/test_create.py tests/test_telemetry.py tests/test_data_contract.py
```

## Out of scope

- A `plan-tool telemetry` aggregation command.
- Outcome linkage across later completeness/reconcile runs.
- Plan-level oversized-plan warnings.
- New granularity detectors or raw size thresholds.
- Any mutation-gated split automation.
- Changing the `granularity-split` / `granularity-merge` recommendation
  semantics.

## Deferred

- **Plan-level split advisory.** Once enough create-side telemetry exists, use
  #72's aggregate/recommend surface to decide whether step count, aggregate file
  footprint, or repeated split hints predict later churn. Only then add an
  advisory.
- **Outcome linkage.** Tie create split decisions to later convergence data:
  did a plan with ignored split hints spin, require `scope-out`, or get
  manually split later?
- **Read-only telemetry report.** A future `plan-tool telemetry` command can
  summarize how often create split hints fire and how often operators act on
  them.
- **Reconcile-side split telemetry.** #70 still has a code-reality-reveals-a-
  split remainder; record it under the same family when that producer exists.
