> **Auto-archived**: this plan was swept on 2026-06-27 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Create Granularity Telemetry
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Promote granularity split predicate literals to stable constants
  files:
  - plan_tool/granularity.py
  - tests/test_granularity.py
  complexity: low
  change_type: refactor
  detail: docs/implementation-plans/plan-details/create-granularity-telemetry/01-promote-granularity-split-predicate-literals.md
  status: done
- id: 2
  title: Expose split predicate recovery helper from the granularity advisor
  files:
  - plan_tool/granularity.py
  - tests/test_granularity.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/create-granularity-telemetry/02-expose-split-predicate-recovery-helper.md
  status: done
- id: 3
  title: Add create-side telemetry recorders for split assessment and step outcomes
  files:
  - plan_tool/telemetry.py
  - tests/test_telemetry.py
  complexity: low
  change_type: feature
  detail: docs/implementation-plans/plan-details/create-granularity-telemetry/03-create-side-telemetry-recorders-split.md
  status: done
- id: 4
  title: Record a create-stage granularity assessment event in the change-type review
    loop
  files:
  - plan_tool/create.py
  - tests/test_create.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  - 3
  detail: docs/implementation-plans/plan-details/create-granularity-telemetry/04-record-create-stage-granularity.md
  status: done
- id: 5
  title: Record per-step outcome events for accept, override, and split actions
  files:
  - plan_tool/create.py
  - tests/test_create.py
  complexity: medium
  change_type: feature
  depends_on:
  - 3
  - 4
  detail: docs/implementation-plans/plan-details/create-granularity-telemetry/05-record-per-step-outcome-events-accept.md
  status: done
- id: 6
  title: Document the new create telemetry context keys and decision values
  files:
  - DATA_CONTRACT.md
  - tests/test_data_contract.py
  allowed_mentions:
  - DATA_CONTRACT.md
  complexity: low
  change_type: non-code
  depends_on:
  - 3
  - 4
  - 5
  detail: docs/implementation-plans/plan-details/create-granularity-telemetry/06-document-new-create-telemetry-context.md
  status: done
---
# Create Granularity Telemetry

## Overview

Wire decision telemetry into `plan-tool create`'s existing granularity and interactive split surfaces so the tool can observe when split signals fire, when operators act on them, and whether split proposals are usable. This is passive, observational telemetry only: it adds no new split threshold, warning, or auto-split path, and does not change create behavior. The create flow already has the hooks — `_granularity_split_hints(steps)`, `_ask_change_type(...)`, `_propose_step_split(...)`, and `_apply_step_split(...)` — what is missing is observation. Events use the existing `plan_tool.telemetry` substrate (append-only JSONL under `.plan-tool/telemetry/decisions.jsonl`, best-effort, gitignored), and a telemetry failure must never affect command success.

## Problem statement

The remaining plan-splitting question is plan-level: when should create tell the operator "this is probably more than one plan" rather than just "split this one mixed step"? A static threshold would be noisy — a cohesive plan with many files may be correct as one plan, a small plan may still be structurally wrong if one step mixes refactor and feature work, and the current precision-first granularity advisor deliberately avoids raw count smells because they false-flag cohesive large steps. The tool needs data before it can tune that boundary. Today create can show a split hint and accept a split action, but it does not persist the context or outcome, so after a session there is no way to answer: how often did create-stage `granularity-split` fire, which predicate fired (mixed verbs, two action clauses, multiple source areas), did the operator accept, override, or request a split, did the split proposal return usable replacements, did deterministic `_apply_step_split` accept or reject it, did the proposal mechanism itself fail, and how large was the plan when the signal fired. Ignoring a fired split hint is represented as `action="accept"` or `action="unclassified-accepted"` with `had_split_hint=true`; there is no separate skip gesture in the create UI. BACKLOG #51 says per-step split hints are mostly shipped and rejects raw static thresholds for plan size or file count; BACKLOG #72 says create-side granularity is a decision site worth instrumenting. Without this record, the plan-level split remainder in BACKLOG #51 cannot be calibrated and will keep relying on anecdote.

## Architecture

Extend decision telemetry, not run logs. Reuse the existing `plan_tool.telemetry` substrate (append-only JSONL at `.plan-tool/telemetry/decisions.jsonl`, best-effort writes that never affect command success, per-kind convenience recorders, local/gitignored). Add a create-focused granularity recorder or extend `record_granularity` with enough context to distinguish create outcomes; keep `telemetry.py` stdlib-only, and have callers compute all plan/step/finding details before recording. Both create recorders accept and forward a `plan_slug` to `record_decision` (matching the sibling `record_granularity` / `record_audit_coverage` / `record_convergence` recorders — `plan_slug` is the only top-level key tying an event to a plan in the repo-wide shared `decisions.jsonl`), and the per-step outcome helper threads the review loop's `slug` the same way the assessment helper does, so create's assessment and outcome events stay groupable per plan. The event family should remain `kind="granularity"` unless there is a strong schema reason to split it — prefer a new `decision` value such as `"create-review"` / `"create-step-outcome"` over a new kind so future aggregation can group all split/merge decisions together.

Record two layers of create-side data. (1) An **assessment event**, once per change-type review pass over a candidate step list, with context: `stage: "create"`, `steps` (current step count), `candidate_fingerprint` (stable digest of the incoming candidate step list for de-duplicating repeated observations of the same list), `file_footprint` (count of distinct declared file paths across those candidate steps, using each step's full footprint: `files` plus `creates`), `split` (number of `granularity-split` findings), `split_steps` (number of distinct steps with at least one split finding), `merge` (number of `granularity-merge` findings, even if create does not surface merge advice interactively), `split_step_ids` (deduplicated ids for steps that carried one or more split findings, stored as strings in candidate order), `predicate_counts` (counts grouped by stable deterministic create-stage predicate key when available — `mixed-verbs`, `two-clauses`, and `multi-area`), `can_split` (whether an invoker was wired and split was mechanically available; `mode` tells whether a UI was actually presented), and `mode` (one of `interactive`, `yes`, `non_tty`, `checkpoint`). This can be emitted from `_granularity_split_hints` or from the review loop around the advisor call; prefer the review loop if it can record mode without threading mode into the leaf helper. Checkpoint resume records a `mode="checkpoint"` assessment for the resumed pass; `mode="checkpoint"` events must be excluded from "fresh signal fired" counts and treated as resume observations, and aggregators can use `candidate_fingerprint` to collapse any repeated observations of the same candidate list across abort/retry paths. (2) An **operator/proposal outcome event**, once per reviewed step answer and for each split attempt, with context: `step_id`, `had_split_hint`, `proposed_change_type`, `resolved_change_type`, `action` (`accept`, `override`, `split-requested`, `split-applied`, `split-unusable`, `split-invalid`, `split-error`, `unclassified-accepted`, `unclassified-classified`; `accept` means the resolved change type equals the proposed one, covering both pressing Enter and re-typing the same value, since actions are classified by value comparison rather than by threading the raw keystroke out of `_ask_change_type`; `override` is reserved for a step that carried a proposal the operator changed to a different concrete value, while first-time classification of a previously-unproposed step (`change_type is None` resolved to a concrete value) records `unclassified-classified`, not `override`, so the override signal stays a clean "operator disagreed with the model's proposal" count), `before_steps` / `after_steps` for successful split attempts, and `error_class` for deterministic split rejection or proposal-time failure (message omitted to avoid noisy telemetry). `had_split_hint` records whether a split hint was *surfaced* for the step (gated by `can_split`), not whether a split signal fired; consumers correlate it against the assessment event's `can_split` rather than its `split` count, since an interactive pass with no wired invoker records `split>=1` in the assessment while leaving every paired `had_split_hint` false. No separate proposal-size field is recorded: `_propose_step_split` already returns either exactly two replacement steps or `None`, so action partitioning carries the usability signal. This stays strictly observational: a telemetry failure must not change any prompt, retry, split, or checkpoint behavior.

Stable predicate keys. The granularity recommendations today expose human text, not an explicit machine predicate. Do not parse prose if it can be avoided — the preferred shape is a small internal helper in `granularity.py` that returns the predicate key alongside the `Recommendation`, or a tiny parser over the already-stable recommendation id suffix if that is the least invasive option. Acceptance pins the chosen mechanism with tests so a future wording edit does not silently break `predicate_counts`.

## References

- [dataclasses — Data Classes — Python documentation](https://docs.python.org/3/library/dataclasses.html) — Reference for the @dataclass decorator, field defaults, and asdict() used to define the DecisionEvent/telemetry context records the recorders construct.
- [json — JSON encoder and decoder — Python documentation](https://docs.python.org/3/library/json.html) — Authoritative json.dumps/loads behavior (ensure_ascii, separators, default serialization) needed to write and read the append-only decisions.jsonl events correctly.
- [JSON Lines (jsonlines.org)](https://jsonlines.org/) — The one-JSON-object-per-line format spec the telemetry substrate follows, clarifying newline/encoding rules for append-only, record-at-a-time writes.
- [How to use temporary directories and files in tests — pytest documentation](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — The tmp_path fixture used by the hermetic unit tests that assert telemetry events through read_decisions without touching shared state.
- [Fixtures reference — pytest documentation](https://docs.pytest.org/en/stable/reference/fixtures.html) — Built-in fixture and marker reference (monkeypatch, function scope) for stubbing invokers and isolating the new create-stage telemetry tests.
- [io — Core tools for working with streams / open() — Python documentation](https://docs.python.org/3/library/functions.html#open) — Semantics of append mode ('a') and write buffering relevant to best-effort, append-only writes that must never raise into the calling command.

## Steps

See the `steps:` block in the frontmatter.

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
  - split-hint assessment emits one create-stage granularity event, including distinct step count and file footprint
  - accepting a hinted step records `had_split_hint=true` and `action=accept`
  - overriding change type records `action=override`
  - split success records `split-requested` and `split-applied` with step counts
  - unusable proposal records `split-unusable` and leaves steps unchanged
  - deterministic `_apply_step_split` rejection records `split-invalid`
  - `--yes`, non-TTY, and checkpoint restore carry the right `mode`, with checkpoint mode documented as excluded from fresh-signal counts
- Unit tests in `tests/test_telemetry.py` for any new convenience recorder.
- Contract drift test update in `tests/test_data_contract.py` if the documented telemetry schema changes.
- Run at minimum: `pytest tests/test_create.py tests/test_telemetry.py tests/test_data_contract.py`.
- Existing create split-review tests in `tests/test_create.py` must still pass.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (refactor) — characterization/value-pinning tests first; rec ids stay unchanged.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (feature) — unit tests added with the implementation; green before completion.
- step 5 (feature) — unit tests added with the implementation; green before completion.
- step 6 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- A create run records a granularity assessment event for the reviewed step list, including create stage, step count, candidate fingerprint, distinct full file footprint (`files` plus `creates`), split finding count, distinct split-step count, split/merge counts, deduplicated string-valued split step ids, deterministic create-stage predicate counts, structural `can_split`, and review mode.
- Both create recorders forward `plan_slug` to `record_decision` so assessment and outcome events group per plan in the shared `decisions.jsonl`, matching the sibling recorders.
- Interactive review records per-step outcome events for accept, override, unclassified accept, unclassified classify (first-time classification of an unproposed step, distinct from override), split requested, split applied, unusable split proposal, invalid deterministic split, and proposal-time split errors.
- `--yes`, non-TTY, and checkpoint-resume paths record mode accurately without introducing prompts or changing reviewed steps; contract docs and acceptance state that checkpoint-mode assessment events are excluded from fresh-signal counts.
- Telemetry write failures remain swallowed; create output, return behavior, and plan content are unchanged.
- Predicate counting is pinned by tests and does not depend on fragile prose wording unless the test explicitly locks that id format as the contract.
- `DATA_CONTRACT.md` documents any new `granularity` context keys or decision values, and its `create-step-outcome` table notes that `accept` means "resolved == proposed".
- Existing create split tests still pass, and new tests assert telemetry events through `read_decisions` rather than by inspecting private file contents.

## Deferred

- **Plan-level split advisory.** Once enough create-side telemetry exists, use #72's aggregate/recommend surface to decide whether step count, aggregate file footprint, or repeated split hints predict later churn. Only then add an advisory.
- **Outcome linkage.** Tie create split decisions to later convergence data: did a plan with ignored split hints spin, require `scope-out`, or get manually split later?
- **Read-only telemetry report.** A future `plan-tool telemetry` command can summarize how often create split hints fire and how often operators act on them.
- **Reconcile-side split telemetry.** #70 still has a code-reality-reveals-a-split remainder; record it under the same family when that producer exists.
