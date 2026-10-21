> **Auto-archived**: this plan was swept on 2026-07-04 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Add a plan-criteria telemetry recorder and document its decision kind

## Summary

Adds one new telemetry decision family, `kind="plan-criteria-breakdown"`, plus a convenience recorder `record_plan_criteria_breakdown` in `plan_tool/telemetry.py`, sitting beside the existing per-kind recorders (`record_convergence`, `record_create_granularity_assessment`). The recorder fixes the `context` shape for a per-plan split-criteria evaluation: a caller-supplied `plan_fingerprint`, an optional `code_fingerprint`, the per-criterion result rows, and derived counts. It takes only JSON primitives so `telemetry.py` stays a stdlib-only leaf — the future evaluator (step 3) computes the fingerprint via `review_persistence.compute_plan_fingerprint` and hands it in as a string. On green: `record_plan_criteria_breakdown(...)` appends one `DecisionEvent` that round-trips through `read_decisions`, `DATA_CONTRACT.md` documents the new kind and its context keys, and both drift-guard lanes in `tests/test_data_contract.py` stay green with a new substring-scan test covering the added vocabulary.

## Table of Contents

- [Summary](#summary) — what the step adds and the observable result on green
- [Why](#why) — the metrics/drift gap this recorder fills before the visualizer lands
- [Files (creates vs edits)](#files-creates-vs-edits) — the four files this step touches
- [Implementation](#implementation) — the recorder shape, the context contract, and the leaf/doc constraints
- [Tests](#tests) — unit tests in test_telemetry.py plus the doc drift-guard tests
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — JSONL + hashlib docs relevant to this step
- [Deferred](#deferred) — the evaluator, CLI, and fingerprint call sites owned by later steps

## Why

The "Visualize Split Criteria" plan adds a read-only surface that answers "why is this plan shaped this way?" and captures the answer over time so decomposition drift is detectable. Drift detection needs a durable, fingerprint-tagged record of each per-plan criteria evaluation — but no such record exists today. `plan_tool/telemetry.py` records `granularity`, `audit-coverage`, and `convergence` decisions, none of which carry a per-criterion breakdown tagged with a plan fingerprint. This step lands the recording contract first — its own file set (recorder + doc + tests) — so the evaluator and CLI in steps 3 and 4 have a stable, documented seam to write through. Landing the recorder before its caller keeps the telemetry vocabulary reviewable on its own and matches how `plan-tool convergence` already leans on `record_convergence`.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/telemetry.py` — add the new decision-kind constant(s) and the `record_plan_criteria_breakdown` convenience recorder beside the existing per-kind block.
  - `tests/test_telemetry.py` — add unit tests for the new recorder (roundtrip, optional `code_fingerprint` omission, criteria passthrough, best-effort-never-raises).
  - `DATA_CONTRACT.md` — add the `plan-criteria-breakdown` kind to the `DecisionEvent` `kind` list and a new context-keys subsection under "Decision telemetry log".
  - `tests/test_data_contract.py` — add substring-scan drift-guard test(s) for the new decision kind and its context keys.

## Implementation

**Add one new per-kind recorder — a sibling, not a new event shape.** The change is purely additive. `DecisionEvent` (`plan_tool/telemetry.py`) keeps its six fields unchanged (`schema_version`, `ts`, `kind`, `decision`, `plan_slug`, `context`); the new work is a convenience recorder that fixes the `context` bag for one more decision family and delegates to the already-best-effort `record_decision`. Do **not** bump `TELEMETRY_SCHEMA_VERSION` — the event shape is unchanged, only a new `kind`/`decision` value fills the existing open bag.

**Name a new kind, not a new `granularity` decision.** The create-stage telemetry reuses `kind="granularity"` with new `decision` values (`create-review`, `create-step-outcome`). This step is different: it is a distinct decision family, so use a **new top-level kind** `"plan-criteria-breakdown"`. Export it as a module-level constant next to the create constants (e.g. `PLAN_CRITERIA_BREAKDOWN_KIND = "plan-criteria-breakdown"`) so the recorder, the future evaluator, and the drift-guard test all read one source rather than re-spelling the literal. Pick a `decision` value for the specific call — one way: a `PLAN_CRITERIA_DECISION = "evaluated"` constant. The exact `decision` string is yours to choose; the `kind` string is the contract other steps key on, so pin that one.

**Recommended recorder signature** (adapt names as needed, keep the keyword-only + primitives shape):

- `record_plan_criteria_breakdown(repo_root, *, plan_slug, plan_fingerprint, criteria, code_fingerprint=None)`
- `plan_fingerprint: str` — a caller-computed digest. The recorder must **not** compute it; see the leaf constraint below.
- `code_fingerprint: dict[str, str] | None` — a caller-supplied path→hash map (the opaque code axis defined by `review_persistence.compute_plan_fingerprint`), stored **verbatim** (already JSON-serializable) — never stringified into a digest. Omit the key from `context` when `None`, mirroring how `record_create_step_outcome` omits `before_steps`/`after_steps`/`error_class` when absent (absence means "not recorded", not zero/empty).
- `criteria: list[dict]` — one row per criterion the evaluator ran. Treat the list as a passthrough bag exactly like `predicate_counts` in `record_create_granularity_assessment` (copy it defensively with a list/dict comprehension; do not validate against a first-party type). Each row's shape is the contract this step defines: `id: str`, `fired: bool`, `severity: str | None`, `step_ids: list[str]`.

**Derive the counts inside the recorder** so the caller and recorder can't drift on key names. One way: set `criteria_count = len(criteria)` and `fired_count = sum(1 for c in criteria if c.get("fired"))`. Deriving them stays stdlib-only (just `len`/a comprehension) and single-sources the counts. If you instead take them as parameters, follow the `record_create_granularity_assessment` precedent of explicit `split`/`merge` int args — but deriving is simpler here and avoids a second source of truth.

**Resulting `context` shape** (the documented contract):
- `plan_fingerprint` — caller-supplied plan digest, always present.
- `code_fingerprint` — present only when the caller passed one.
- `criteria` — the per-criterion rows (`id`/`fired`/`severity`/`step_ids`).
- `criteria_count` — number of criteria evaluated.
- `fired_count` — number that fired.

**Hard constraint — `telemetry.py` stays a stdlib-only leaf.** It must import nothing first-party. The recorder therefore takes `plan_fingerprint` as a plain string and `code_fingerprint` as a plain path→hash dict — both already JSON-serializable; the caller (step 3's evaluator in `plan_tool/split_criteria.py`) is the one that imports `plan_tool/review_persistence.py:compute_plan_fingerprint` and converts its plan/finding types into the primitive `criteria` rows. This matches the established pattern in `plan_tool/telemetry.py`'s per-kind block ("callers compute the counts from their own plan/finding types") and the module's leaf docstring. Adding any `plan_tool.*` import to this module is out of bounds.

**Delegate, don't re-guard.** The new recorder only builds a `dict` and calls `record_decision`, which already swallows every error and never raises. Do not wrap the recorder in a second `try/except` — that would be redundant with `record_decision`'s best-effort contract (`plan_tool/telemetry.py:record_decision`).

**Shared logic — the per-kind recorder block.** The foundational logic here is "one convenience recorder that pins the `context` shape for a single decision family." The other places that exercise the same rule are the existing siblings in `plan_tool/telemetry.py`: `record_granularity`, `record_create_granularity_assessment`, `record_create_step_outcome`, `record_audit_coverage`, and `record_convergence`. This step **adds** to that block; it does not touch the existing recorders. The one downstream call site that will *use* the new recorder (the split-criteria evaluator) is owned by step 3 — see Deferred.

**Document the new kind in `DATA_CONTRACT.md`.** Under "Decision telemetry log" → `DecisionEvent`, extend the `kind` field row to list `"plan-criteria-breakdown"` alongside `"granularity" | "audit-coverage" | "convergence"`. Then add a new subsection (mirroring "Create granularity decisions") that names the `plan-criteria-breakdown` kind, its `decision` value, and a context-keys table listing `plan_fingerprint`, `code_fingerprint` (noting it is omitted when absent), `criteria` (with the per-row `id`/`fired`/`severity`/`step_ids` shape), `criteria_count`, and `fired_count`. Keep to the doc's existing table style; state the drift meaning (same `plan_slug`, a changed `plan_fingerprint` with a changed criteria result-set) so the later drift note in step 3 traces back to a documented definition.

**Add the drift-guard test to the right lane.** `tests/test_data_contract.py` has two lanes: `test_every_persisted_field_is_documented` introspects **dataclass fields** and is blind to keys inside the open `context` bag, while the per-vocabulary tests (`test_report_kinds_documented`, `test_create_granularity_context_keys_documented`, …) are substring scans over the doc text. The new context keys live inside `context`, so the field lane stays green untouched — add a **substring-scan** sibling test that asserts the doc names `plan-criteria-breakdown` and each new context key. Do not expect the field lane to catch a missing context key.

## Tests

Add to `tests/test_telemetry.py` (unit, mirror the existing create-recorder tests):

- `test_record_plan_criteria_breakdown_roundtrips` — recording with a pinned `clock` then `read_decisions` returns one event with `kind="plan-criteria-breakdown"`, the chosen `decision`, `plan_slug`, and a `context` carrying `plan_fingerprint`, `criteria`, `criteria_count`, and `fired_count`.
- `test_plan_criteria_omits_code_fingerprint_when_absent` — calling without `code_fingerprint` leaves the key out of `context` (asserts `"code_fingerprint" not in context`); passing one includes it.
- `test_plan_criteria_criteria_rows_passthrough` — an arbitrary `criteria` list round-trips verbatim (each row's `id`/`fired`/`severity`/`step_ids` preserved), like `test_assessment_predicate_counts_passthrough`.
- `test_plan_criteria_counts_derived` — `criteria_count` equals `len(criteria)` and `fired_count` equals the number of rows with `fired` true (drop this if you take counts as params instead).
- `test_plan_criteria_recorder_is_best_effort` — pointing `repo_root` at a regular file (not a dir) does not raise and `read_decisions` returns `[]`, mirroring `test_create_recorders_are_best_effort`.
- `test_plan_criteria_kind_constant_value` — the exported `PLAN_CRITERIA_BREAKDOWN_KIND` constant equals `"plan-criteria-breakdown"` (pins the literal other steps depend on).

Add to `tests/test_data_contract.py` (substring-scan lane):

- `test_plan_criteria_decision_documented` — `DATA_CONTRACT.md` names `plan-criteria-breakdown`.
- `test_plan_criteria_context_keys_documented` — the doc names each new context key (`plan_fingerprint`, `code_fingerprint`, `criteria`, `criteria_count`, `fired_count`).

### Test-creation order (feature step)

This is a **feature** step. Write each unit test alongside the recorder and doc edit it covers: the telemetry tests with the recorder, the substring-scan tests with the `DATA_CONTRACT.md` additions. Every new test — and the existing `test_every_persisted_field_is_documented[DecisionEvent]` and `test_schema_version_named` guards — must be green before this step is done.

## Acceptance criteria

- `record_plan_criteria_breakdown(repo_root, plan_slug=..., plan_fingerprint=..., criteria=[...])` appends exactly one line that `read_decisions` parses into a `DecisionEvent` with `kind == "plan-criteria-breakdown"`.
- The recorded `context` carries `plan_fingerprint`, `criteria`, `criteria_count`, and `fired_count`; `code_fingerprint` is present only when the caller supplies it.
- The recorder never raises when `repo_root` cannot hold the file (best-effort), returning without writing.
- `plan_tool/telemetry.py` imports no `plan_tool.*` module (stdlib-only leaf preserved) and `TELEMETRY_SCHEMA_VERSION` is unchanged.
- `DATA_CONTRACT.md` lists `plan-criteria-breakdown` in the `DecisionEvent` `kind` values and documents each new context key.
- `uv run pytest tests/test_telemetry.py tests/test_data_contract.py -q` is green, including the unchanged `test_every_persisted_field_is_documented[DecisionEvent]` and `test_schema_version_named`.

## References

- [JSON Lines (jsonl) format specification](https://jsonlines.org/) — the newline-delimited JSON format `record_decision` appends to `.plan-tool/telemetry/decisions.jsonl`; each `DecisionEvent` must be one valid line.
- [json — JSON encoder and decoder (Python docs)](https://docs.python.org/3/library/json.html) — `json.dumps` serialization of the `context` bag (per-criterion rows, fingerprints, counts); confirms the `criteria` rows must be JSON-serializable primitives.
- [hashlib — Secure hashes and message digests (Python docs)](https://docs.python.org/3/library/hashlib.html) — background on the SHA-256 digest behind `compute_plan_fingerprint`, whose string output this recorder stores as `plan_fingerprint` (the caller computes it, not this module).

## Deferred

- **The split-criteria evaluator that calls this recorder** — owned by step 3 (`plan_tool/split_criteria.py`); it computes `plan_fingerprint` via `plan_tool/review_persistence.py:compute_plan_fingerprint`, builds the primitive `criteria` rows from detector output, and calls `record_plan_criteria_breakdown`. Out of scope here; this step only lands the recorder + contract.
- **The drift note (diffing the latest breakdown against the most recent event with a different `plan_fingerprint`)** — the *rendering* of drift is step 3's report layer; this step only documents the drift definition and records the fingerprint-tagged events that make it possible.
- **The `plan-tool split-criteria` CLI handler** — owned by step 4 (`plan_tool/cli/split_criteria_cmd.py`).
- **`compute_plan_fingerprint` / `code_fingerprint` computation** — stays in `plan_tool/review_persistence.py` and the caller; `telemetry.py` must not import it (stdlib-only leaf).
- **`TELEMETRY_SCHEMA_VERSION` bump** — not needed; the event shape is unchanged, only a new `kind` value fills the existing open `context` bag.
