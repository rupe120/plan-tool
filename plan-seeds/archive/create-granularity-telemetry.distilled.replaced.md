> **Replaced**: this file has been superseded by `docs/implementation-plans/2-create-granularity-telemetry.md`.
> Preserved here for history; do not edit.

## Overview

Wire decision telemetry into `plan-tool create`'s existing granularity and interactive split surfaces so the tool can observe when split signals fire, when operators act on them, and whether split proposals are usable. This is passive, observational telemetry only: it adds no new split threshold, warning, or auto-split path, and does not change create behavior. The create flow already has the hooks — `_granularity_split_hints(steps)`, `_ask_change_type(...)`, `_propose_step_split(...)`, and `_apply_step_split(...)` — what is missing is observation. Events use the existing `plan_tool.telemetry` substrate (append-only JSONL under `.plan-tool/telemetry/decisions.jsonl`, best-effort, gitignored), and a telemetry failure must never affect command success.

## Problem statement

The remaining plan-splitting question is plan-level: when should create tell the operator "this is probably more than one plan" rather than just "split this one mixed step"? A static threshold would be noisy — a cohesive plan with many files may be correct as one plan, a small plan may still be structurally wrong if one step mixes refactor and feature work, and the current precision-first granularity advisor deliberately avoids raw count smells because they false-flag cohesive large steps. The tool needs data before it can tune that boundary. Today create can show a split hint and accept a split action, but it does not persist the context or outcome, so after a session there is no way to answer: how often did create-stage `granularity-split` fire, which predicate fired (mixed verbs, conjoined action clauses, unrelated source areas), did the operator accept/override/request-split/skip, did Claude return a usable proposal, did deterministic `_apply_step_split` accept or reject it, and how large was the plan when the signal fired. BACKLOG #51 says per-step split hints are mostly shipped and rejects raw static thresholds for plan size or file count; BACKLOG #72 says create-side granularity is a decision site worth instrumenting. Without this record, the plan-level split remainder in BACKLOG #51 cannot be calibrated and will keep relying on anecdote.

## Architecture

Extend decision telemetry, not run logs. Reuse the existing `plan_tool.telemetry` substrate (append-only JSONL at `.plan-tool/telemetry/decisions.jsonl`, best-effort writes that never affect command success, per-kind convenience recorders, local/gitignored). Add a create-focused granularity recorder or extend `record_granularity` with enough context to distinguish create outcomes; keep `telemetry.py` stdlib-only, and have callers compute all plan/step/finding details before recording. The event family should remain `kind="granularity"` unless there is a strong schema reason to split it — prefer a new `decision` value such as `"create-review"` / `"create-step-outcome"` over a new kind so future aggregation can group all split/merge decisions together.

Record two layers of create-side data. (1) An **assessment event**, once per change-type review pass over a candidate step list, with context: `stage: "create"`, `steps` (current step count), `split` (number of `granularity-split` findings), `merge` (number of `granularity-merge` findings, even if create does not surface merge advice interactively), `split_step_ids` (ids that carried split findings), `predicate_counts` (counts grouped by stable predicate key when available — `mixed-verbs`, `conjoined-clauses`, `unrelated-areas`), `can_split` (whether the UI could offer `(s)plit`), and `mode` (one of `interactive`, `yes`, `non_tty`, `checkpoint`). This can be emitted from `_granularity_split_hints` or from the review loop around the advisor call; prefer the review loop if it can record mode without threading mode into the leaf helper. (2) An **operator/proposal outcome event**, once per reviewed step answer and for each split attempt, with context: `step_id`, `had_split_hint`, `proposed_change_type`, `resolved_change_type`, `action` (`accept`, `override`, `split-requested`, `split-applied`, `split-unusable`, `split-invalid`, `unclassified-accepted`), `before_steps` / `after_steps` for split attempts, `proposal_len` for split proposals where parse succeeded, and `error_class` for deterministic split rejection (message omitted or shortened to avoid noisy telemetry). This stays strictly observational: a telemetry failure must not change any prompt, retry, split, or checkpoint behavior.

Stable predicate keys. The granularity recommendations today expose human text, not an explicit machine predicate. Do not parse prose if it can be avoided — the preferred shape is a small internal helper in `granularity.py` that returns the predicate key alongside the `Recommendation`, or a tiny parser over the already-stable recommendation id suffix if that is the least invasive option. Acceptance pins the chosen mechanism with tests so a future wording edit does not silently break `predicate_counts`.

## Out of scope

- A `plan-tool telemetry` aggregation command.
- Outcome linkage across later completeness/reconcile runs.
- Plan-level oversized-plan warnings.
- New granularity detectors or raw size thresholds.
- Any mutation-gated split automation.
- Changing the `granularity-split` / `granularity-merge` recommendation semantics.

## Risks

- Predicate keys depend on fragile prose wording. The granularity recommendations expose human text, not an explicit machine predicate; deriving `predicate_counts` by parsing prose could silently break on a wording edit. Mitigated by preferring a small internal helper in `granularity.py` that returns the predicate key alongside the `Recommendation` (or a parser over the stable recommendation id suffix), and pinning the chosen mechanism with tests.
- Telemetry could leak into command behavior. Recording at create-time decision sites risks changing prompts, retries, splits, or checkpoint flow. Mitigated by best-effort writes that swallow every error and never raise into the caller, with callers computing all details before recording.

## Testing

Follow the project's unit-first convention; new tests assert telemetry events through `read_decisions` rather than by inspecting private file contents.

- Unit tests in `tests/test_create.py`:
  - split-hint assessment emits one create-stage granularity event
  - accepting a hinted step records `had_split_hint=true` and `action=accept`
  - overriding change type records `action=override`
  - split success records `split-requested` and `split-applied` with step counts
  - unusable proposal records `split-unusable` and leaves steps unchanged
  - deterministic `_apply_step_split` rejection records `split-invalid`
  - `--yes`, non-TTY, and checkpoint restore carry the right `mode`
- Unit tests in `tests/test_telemetry.py` for any new convenience recorder.
- Contract drift test update in `tests/test_data_contract.py` if the documented telemetry schema changes.
- Run at minimum: `pytest tests/test_create.py tests/test_telemetry.py tests/test_data_contract.py`.
- Existing create split-review tests in `tests/test_create.py` must still pass.

## Acceptance criteria

- A create run records a granularity assessment event for the reviewed step list, including create stage, step count, split/merge counts, split step ids, predicate counts, `can_split`, and review mode.
- Interactive review records per-step outcome events for accept, override, unclassified accept, split requested, split applied, unusable split proposal, and invalid deterministic split.
- `--yes`, non-TTY, and checkpoint-resume paths record mode accurately without introducing prompts or changing reviewed steps.
- Telemetry write failures remain swallowed; create output, return behavior, and plan content are unchanged.
- Predicate counting is pinned by tests and does not depend on fragile prose wording unless the test explicitly locks that id format as the contract.
- `DATA_CONTRACT.md` documents any new `granularity` context keys or decision values.
- Existing create split tests still pass, and new tests assert telemetry events through `read_decisions` rather than by inspecting private file contents.

## Deferred

- **Plan-level split advisory.** Once enough create-side telemetry exists, use #72's aggregate/recommend surface to decide whether step count, aggregate file footprint, or repeated split hints predict later churn. Only then add an advisory.
- **Outcome linkage.** Tie create split decisions to later convergence data: did a plan with ignored split hints spin, require `scope-out`, or get manually split later?
- **Read-only telemetry report.** A future `plan-tool telemetry` command can summarize how often create split hints fire and how often operators act on them.
- **Reconcile-side split telemetry.** #70 still has a code-reality-reveals-a-split remainder; record it under the same family when that producer exists.
