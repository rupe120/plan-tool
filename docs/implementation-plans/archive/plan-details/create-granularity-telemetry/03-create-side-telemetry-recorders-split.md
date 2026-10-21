> **Auto-archived**: this plan was swept on 2026-06-27 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Add create-side telemetry recorders for split assessment and step outcomes

## Summary

Add two new convenience recorders to `plan_tool/telemetry.py` that pin the `context` shape for create-stage granularity decisions, so steps 4 and 5 can record events without re-deriving the key set at each call site. One records a per-review-pass **assessment event** (step list size, distinct file footprint, split/merge finding counts, distinct split-step count, which steps carried split hints, predicate counts, whether split was mechanically available, and the review mode). The other records a per-step **outcome event** (what the operator did with one reviewed step, plus split-attempt details when a split was tried). Both reuse the existing `kind="granularity"` family with new `decision` values (`"create-review"` / `"create-step-outcome"`), take only JSON-friendly primitives so `telemetry.py` stays a stdlib-only leaf, and inherit `record_decision`'s best-effort write. On green, a caller can record either event and read it back through `read_decisions` with every documented context key present.

## Table of Contents

- [Summary](#summary) — what this step ships and the result on green
- [Why](#why) — the recorders steps 3 and 4 need before they can wire create
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files touched
- [Implementation](#implementation) — the two recorders, their context shapes, and the constants that lock the vocabulary
- [Tests](#tests) — unit cases added with the implementation
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors
- [References](#references) — stdlib and pytest docs for this step
- [Deferred](#deferred) — work left to the consumer steps

## Why

`plan_tool/telemetry.py` already has one recorder per decision family — `record_granularity`, `record_audit_coverage`, `record_convergence` — each fixing a consistent `context` shape so a later aggregation can rely on the keys. The create-side instrumentation (steps 4 and 5) needs two new shapes that no existing recorder covers: a create-review **assessment** with `split_step_ids` / `predicate_counts` / `can_split` / `mode`, and a per-step **outcome** with `action` / `had_split_hint` / split-attempt details. Without dedicated recorders, steps 4 and 5 would each hand-build a `record_decision` context dict, and the two call sites would drift on key names — exactly the fragility the per-kind recorders exist to prevent. This step adds the recorders and tests only; it wires nothing into `plan_tool/create.py` (that is steps 4 and 5's job) and changes no create behavior.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/telemetry.py` — add two convenience recorders (`record_create_granularity_assessment` and `record_create_step_outcome`) beside the existing `record_granularity` / `record_audit_coverage` / `record_convergence` block, plus a small set of exported `action` / `mode` string constants the outcome recorder's vocabulary uses.
  - `tests/test_telemetry.py` — add unit tests pinning each recorder's `decision` value, full context shape, the omit-when-absent behavior of the split-only outcome keys, the constant values, and best-effort write.

## Implementation

**What changes.** Add two recorders mirroring the existing per-kind block (see the `--- per-kind convenience recorders ---` comment and `record_granularity` in `plan_tool/telemetry.py`). Both call `record_decision` with `kind="granularity"` and a new `decision` value, keep every argument a primitive (ints, strings, bools, `list[str]`, `dict[str, int]`), and add no first-party import — `telemetry.py` must stay the stdlib-only leaf its module docstring promises, so the caller computes all counts from its own plan/finding types and hands them in.

**Recorder 1 — the assessment event.** One event per change-type review pass over a candidate step list.

- **Name it `record_create_granularity_assessment`** — this symbol name is the export contract (steps 3/4 consumers and Acceptance criteria depend on it), not a free choice. Match the sibling recorder style: positional `repo_root`, keyword-only `plan_slug`, then keyword-only context primitives. `plan_slug` is required and is forwarded to `record_decision`; it is the top-level event key that groups create telemetry by plan.
- **Decision value:** `"create-review"`.
- **Context keys** (contract): `stage` (set to `"create"` inside the recorder so callers don't repeat it), `steps: int`, `candidate_fingerprint: str`, `file_footprint: int`, `split: int`, `split_steps: int`, `merge: int`, `split_step_ids: list[str]`, `predicate_counts: dict[str, int]`, `can_split: bool`, `mode: str`. Keeping `stage` in context keeps these events groupable with `record_granularity`'s `assessed` events, which also carry `stage`.
- **`candidate_fingerprint` is the stable candidate-list identity.** Step 4 computes it from the incoming candidate steps before the interactive loop mutates anything. The recorder treats it as an opaque string. Aggregation uses it with `plan_slug` to collapse repeated assessment observations of the same candidate list across abort/retry paths.
- **Finding count versus step count is intentional.** `split` counts `granularity-split` findings; a single step can contribute more than one finding when multiple deterministic predicates fire. `split_steps` is the distinct step count, and `split_step_ids` is the deduplicated string id list in candidate-list order. Step 4 owns computing those primitives; this recorder records them exactly as supplied.
- **`file_footprint` is the distinct full declared-file count.** Step 4 computes it from the candidate steps' full file footprints (`files` plus `creates`, matching `step.all_files`) before recording. This preserves the plan-level hypothesis named in the overview and deferred advisory without adding a raw threshold now, and keeps the metric aligned with the `multi-area` split predicate.
- **The recorder is agnostic to `predicate_counts` keys.** Step 4 builds that dict from step 2's exported predicate-key vocabulary (`plan_tool/granularity.py` — the `SPLIT_PREDICATE_*` constants and `split_predicate_key`). This recorder must not import `granularity` to validate the keys; treating `predicate_counts` as an opaque `dict[str, int]` is what keeps `telemetry.py` a leaf.

**Recorder 2 — the step outcome event.** One event per reviewed step answer, and one per split attempt.

- **Name it `record_create_step_outcome`** — this symbol name is the export contract (steps 3/4 consumers and Acceptance criteria depend on it), not a free choice. Match the sibling recorder style: positional `repo_root`, keyword-only `plan_slug`, then keyword-only outcome primitives. `plan_slug` is required and is forwarded to `record_decision`.
- **Decision value:** `"create-step-outcome"`.
- **Always-present context keys:** `step_id: str`, `had_split_hint: bool`, `action: str`, `proposed_change_type: Optional[str]`, `resolved_change_type: Optional[str]`.
- **Split-only context keys, included only when given (not `None`):** `before_steps: int`, `after_steps: int`, `error_class: str`. An `accept`/`override` event then carries no empty split fields, and a split event carries the rich set. One way to do this: accept these three as `Optional[...] = None` kwargs and add each to the context dict only when it is not `None`. State this omit-when-absent rule in the docstring so step 5's callers know an absent key means "not a split attempt", not "zero".
- **`error_class` carries the exception class name only**, never the message — the plan calls for omitting/shortening the message to avoid noisy telemetry. For a deterministic `_apply_step_split` rejection (which raises `CreateError` in `plan_tool/create.py`), step 5 passes `error_class="CreateError"`; for proposal-time failures it passes the thrown exception class with `action="split-error"`.

**Lock the vocabulary with exported constants.** The outcome `action` set is closed — `accept`, `override`, `split-requested`, `split-applied`, `split-unusable`, `split-invalid`, `split-error`, `unclassified-accepted`, `unclassified-classified` — and the assessment `mode` set is closed — `interactive`, `yes`, `non_tty`, `checkpoint`. Promote these into named module-level constants (e.g. `CREATE_ACTION_ACCEPT = "accept"`, `CREATE_MODE_INTERACTIVE = "interactive"`, …) and export them, so step 5 references the constant instead of spelling a literal and step 6 documents the same source. This mirrors how step 1 lifted the split predicate keys into exported constants. The **string values are the contract** — step 6 will document them and aggregation will group on them — so pin the values with a test; the names may read clearly but the values stay exactly as listed. The recorders themselves do **not** validate `action`/`mode` against the constants: `record_decision` is best-effort and must never raise, so an unexpected value is recorded as-is, not rejected.

**Constraints and gotchas.**

- **Do not bump `TELEMETRY_SCHEMA_VERSION`.** Adding new `decision` values and new context keys under the existing `kind="granularity"` is additive; the reader already tolerates unknown keys and older lines. The version bumps only on a breaking event-shape change.
- **Keep both recorders best-effort by construction.** They must do nothing but build a context dict and delegate to `record_decision`, which already swallows every error. Do not add a second try/except or any I/O of their own.
- **Stay stdlib-only.** No import of `plan_tool.granularity`, `plan_tool.schema`, or any first-party module. The callers (steps 3/4) own all type-to-primitive conversion.
- **`record_granularity` stays unchanged.** The create assessment is a separate recorder, not an extension of `record_granularity`, because its context shape is wider; leave the existing recorder and its `decision="assessed"` events alone.

**Shared logic.** The foundational logic here — "one convenience recorder fixes the context shape for one decision family" — already lives in the `record_granularity` / `record_audit_coverage` / `record_convergence` block of `plan_tool/telemetry.py`. This step adds two siblings to that block; there is no duplicated rule to consolidate elsewhere, so nothing routes to Deferred for a refactor.

## Tests

All cases go in `tests/test_telemetry.py`, asserting through `read_decisions` (never by inspecting raw file bytes), each with a pinned `clock=lambda: "..."`. Enumerate (approx. 9 tests):

- `test_record_create_assessment_roundtrips` — `record_create_granularity_assessment` writes one event with `kind="granularity"`, `decision="create-review"`, and a context carrying `stage="create"`, `steps`, `candidate_fingerprint`, `file_footprint`, `split`, `split_steps`, `merge`, `split_step_ids`, `predicate_counts`, `can_split`, `mode`.
- `test_create_assessment_forwards_plan_slug` — the read-back event has the supplied `plan_slug` as its top-level `DecisionEvent.plan_slug` value.
- `test_assessment_records_finding_and_distinct_step_counts` — a context with `split=3`, `split_steps=2`, and two `split_step_ids` round-trips unchanged, pinning that finding count and distinct-step count are separate signals.
- `test_assessment_records_file_footprint` — the recorder round-trips `file_footprint` as supplied.
- `test_assessment_stage_is_create` — the recorder sets `stage="create"` itself; caller passes no stage.
- `test_assessment_predicate_counts_passthrough` — an arbitrary `predicate_counts` dict round-trips unchanged, proving the recorder does not interpret its keys.
- `test_record_step_outcome_accept_omits_split_fields` — an `accept` outcome (no split kwargs) writes `decision="create-step-outcome"` and a context with no `before_steps` / `after_steps` / `error_class` keys.
- `test_record_step_outcome_split_applied_carries_counts` — a `split-applied` outcome includes `before_steps` and `after_steps`.
- `test_record_step_outcome_split_invalid_carries_error_class` — a `split-invalid` outcome includes `error_class="CreateError"` and no message text.
- `test_step_outcome_change_types_round_trip` — `proposed_change_type` / `resolved_change_type` and `had_split_hint` are recorded as given.
- `test_step_outcome_forwards_plan_slug` — the read-back event has the supplied `plan_slug`, matching the assessment recorder and sibling telemetry recorders.
- `test_create_action_and_mode_constants_have_expected_values` — locks the exact string values of every exported `action` and `mode` constant.
- `test_create_recorders_are_best_effort` — both recorders return without raising when `repo_root` can't hold the file (a regular file, not a dir), mirroring `test_record_is_best_effort_never_raises`.

### Test-creation order (feature step)

This is a **feature** step. Write each test above alongside the recorder it covers. **Green-before-done gate:** every new test in `tests/test_telemetry.py` must pass, and the existing `tests/test_telemetry.py` cases must stay green, before this step is considered finished. Run at minimum `uv run pytest tests/test_telemetry.py -q`.

## Acceptance criteria

- `plan_tool/telemetry.py` exports `record_create_granularity_assessment` and `record_create_step_outcome`.
- `record_create_granularity_assessment(repo_root, *, plan_slug, ...)` writes one event readable via `read_decisions` with `kind="granularity"`, `decision="create-review"`, top-level `plan_slug`, and context keys `stage` (`="create"`), `steps`, `candidate_fingerprint`, `file_footprint`, `split`, `split_steps`, `merge`, `split_step_ids`, `predicate_counts`, `can_split`, `mode`.
- The assessment contract states that `split` is the finding count, `split_steps` is the distinct step count, and `split_step_ids` is deduplicated and ordered by the candidate step list.
- `record_create_step_outcome(repo_root, *, plan_slug, ...)` writes one event with `decision="create-step-outcome"`, top-level `plan_slug`, and context keys `step_id`, `had_split_hint`, `action`, `proposed_change_type`, `resolved_change_type`; the keys `before_steps`, `after_steps`, `error_class` appear only when their argument is not `None`.
- Exported `action` constants resolve to `accept`, `override`, `split-requested`, `split-applied`, `split-unusable`, `split-invalid`, `split-error`, `unclassified-accepted`, `unclassified-classified`; exported `mode` constants resolve to `interactive`, `yes`, `non_tty`, `checkpoint`.
- Both recorders return `None` without raising when the write target is invalid.
- `TELEMETRY_SCHEMA_VERSION` is unchanged.
- `plan_tool/telemetry.py` imports no first-party module.
- All new and existing `tests/test_telemetry.py` cases pass.

## References

- [dataclasses — Data Classes — Python documentation](https://docs.python.org/3/library/dataclasses.html) — `asdict()` and field semantics behind `DecisionEvent`, which the recorders build through `record_decision`.
- [json — JSON encoder and decoder — Python documentation](https://docs.python.org/3/library/json.html) — confirms `list`/`dict[str,int]`/`bool` context values serialize cleanly through the existing `json.dumps` write path.
- [JSON Lines (jsonlines.org)](https://jsonlines.org/) — the one-object-per-line format these append-only events follow.
- [How to use temporary directories and files in tests — pytest documentation](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — the `tmp_path` fixture the new hermetic tests use to drive `read_decisions`.

## Deferred

- **Wiring the recorders into create.** Step 4 records the assessment event from create's change-type review loop; step 5 records per-step outcome events for accept / override / split paths. This step only defines the recorders.
- **Building `predicate_counts`.** Step 4 derives that dict from step 2's exported predicate-key vocabulary in `plan_tool/granularity.py`; the recorder treats it as an opaque dict.
- **`DATA_CONTRACT.md` documentation.** Step 6 documents the new `granularity` decision values and context keys and updates `tests/test_data_contract.py`; this step writes no contract doc.
- **Validating `action`/`mode` against the constants.** The recorders stay best-effort and record any value as-is; no enforcing layer is added here.
