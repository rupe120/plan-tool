> **Auto-archived**: this plan was swept on 2026-06-27 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Document the new create telemetry context keys and decision values

## Summary

Document the two new create-stage decision telemetry shapes (steps 3–5) in `DATA_CONTRACT.md`: the `create-review` per-pass assessment and the `create-step-outcome` per-step outcome, both under the existing `kind="granularity"` family. The `DecisionEvent` dataclass gains no fields — the new data rides the open `context` bag — so the existing field drift-guard stays green; this step adds the per-decision `context` key tables the doc currently lacks. The main design call: document the additive change without bumping `TELEMETRY_SCHEMA_VERSION`, and add a small drift-guard test to `tests/test_data_contract.py` that fails if the new decision values, context-key vocabulary, or checkpoint-mode aggregation rule leave the doc. On green, `DATA_CONTRACT.md` names every create-stage decision value and context key steps 3–5 write, explains which assessment counts are findings versus distinct steps, and a CI test pins that naming.

## Table of Contents

- [Summary](#summary) — what this step ships and the result on green
- [Why](#why) — the doc gap the create-stage telemetry opens
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files touched
- [Implementation](#implementation) — the doc additions and the drift-guard test
- [Tests](#tests) — drift-guard cases added, plus doc verification
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors
- [References](#references) — the contract doc's own rules and the JSONL format
- [Deferred](#deferred) — work left to other steps

## Why

`DATA_CONTRACT.md` is the reference humans and agents read for the persisted decision-telemetry shape, and `tests/test_data_contract.py` is the drift guard that fails when the on-disk schema grows past the doc. Steps 3–5 add two new create-stage decision shapes under `kind="granularity"` — a `create-review` assessment and a `create-step-outcome` outcome — each carrying new `context` keys (`file_footprint`, `split_steps`, `split_step_ids`, `predicate_counts`, `can_split`, `mode`, `action`, `had_split_hint`, the split-attempt counts, `error_class`). The `DecisionEvent` dataclass itself does not change, so the existing field-name guard stays green and the doc would silently lag the real on-disk shape. This step closes that gap: it writes the per-decision `context` tables and adds a focused test so the create-stage vocabulary can't drift out of the doc.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `DATA_CONTRACT.md` — under the `## Decision telemetry log` section's `### DecisionEvent` table, add the create-stage decision values to the `decision` row and add a short subsection (one small table per decision) documenting the `context` keys for `create-review` and `create-step-outcome`, including the omit-when-absent split-only keys and the checkpoint-mode filtering rule. State that the change is additive and `TELEMETRY_SCHEMA_VERSION` is unchanged.
  - `tests/test_data_contract.py` — add one drift-guard test asserting the new decision values and their context-key vocabulary appear in the doc, mirroring the existing `test_report_kinds_documented` / `test_schema_version_named` style.

## Implementation

**What changes.** This step documents data that steps 3–5 produce; it adds no production code. Read the real literals at HEAD before writing — by the time this step runs, steps 3–5 have landed, so the decision values, the `CREATE_MODE_*` / `CREATE_ACTION_*` constant values, and the exact `context` key names live in `plan_tool/telemetry.py` (the `record_create_granularity_assessment` and `record_create_step_outcome` recorders) and `plan_tool/create.py`. **Treat the names below as a descriptive list, not the contract — copy the exact strings from the code, since the recorders own them.**

**Document the two new decision values.** The `### DecisionEvent` table in `DATA_CONTRACT.md` currently describes `decision` as "the specific call within the kind (e.g. `"assessed"` / `"passes"` / `"diagnosed"`)". Extend the granularity family's documented decisions to name:
- **`create-review`** — one event per change-type review pass over a candidate step list (step 4, recorded at all four return branches of `plan_tool/create.py:_review_step_change_types`).
- **`create-step-outcome`** — one event per operator gesture in the interactive change-type loop (step 5).

Keep the `kind` row unchanged: both reuse the existing `kind="granularity"`, so the kind vocabulary (`granularity` / `audit-coverage` / `convergence`) does not grow. Keep `plan_slug` top-level, not in either `context` table: both create recorders forward the current plan slug into the existing `DecisionEvent.plan_slug` field so events remain groupable per plan in the shared JSONL log.

**Add the per-decision context tables.** The `context` bag is open per-kind, so the field-level table can't carry these. Add a short subsection below the `DecisionEvent` table — one small table per decision — listing the keys. From steps 3–5 (confirm names against the recorders):
- **`create-review` context** — `mode` (`CREATE_MODE_*`: interactive / yes / non_tty / checkpoint), `steps` (candidate step count), `candidate_fingerprint` (stable digest of the incoming candidate step list, used with `plan_slug` to dedupe repeated observations), `file_footprint` (distinct declared file path count across candidate steps' full file footprints: `files` plus `creates`), `split` and `merge` (finding counts), `split_steps` (distinct count of steps with at least one split finding), `split_step_ids` (deduplicated step ids that carried a split hint, stored as strings in candidate-list order), `predicate_counts` (deterministic create-stage predicate key → count, from step 2's `split_predicate_key`: `mixed-verbs`, `two-clauses`, `multi-area`), `can_split` (whether split was mechanically available; pair with `mode` to know whether a UI was presented).
- **`create-step-outcome` context** — `action` (`CREATE_ACTION_*`: accept / override / unclassified-accepted / unclassified-classified / split-requested / split-applied / split-unusable / split-invalid / split-error), `had_split_hint` (bool), and the split-only keys `before_steps` / `after_steps` (split-applied) and `error_class` (split-invalid or split-error).

**State the omit-when-absent rule.** Document that the split-only outcome keys (`before_steps`, `after_steps`, `error_class`) are present **only when the gesture was a split attempt** — an `accept` / `override` event carries none of them, so a missing key reads as "not applicable", never zero. This matches the absent-vs-zero rule the recorders follow.

**State the count semantics and dedupe rules.** Document that `split` is a finding count, while `split_steps` / `split_step_ids` are distinct-step signals. Also state that `mode="checkpoint"` assessment events are resume observations and should be excluded from "fresh signal fired" counts so a resumed review does not double-count the original pass, and that repeated observations of the same candidate list can be collapsed by `plan_slug` + `candidate_fingerprint`.

**State the action-classification semantics.** Document that `action="accept"` means the resolved change type equals the proposed change type. It covers both pressing Enter and explicitly re-typing the same proposed type because step 5 classifies by value comparison rather than by preserving the raw keystroke. Also document that `unclassified-classified` means the operator assigned a concrete type to a step that had no proposed type, while `override` is reserved for changing an existing proposal.

**State that the schema version is unchanged.** This is additive evolution — new decision values plus new optional `context` keys under an existing event family. A tolerant reader (`read_decisions`) already ignores unknown keys and older lines, so `TELEMETRY_SCHEMA_VERSION` stays `1`. Say this in the doc so a future editor doesn't bump it on the next additive change.

**Keep the source-of-truth boundary.** The doc's existing preamble says code wins when doc and code disagree. Don't restate the recorder mechanism — describe the persisted shape only. The recorders in `plan_tool/telemetry.py` and their call sites in `plan_tool/create.py` are step 3/4/5 deliverables; reference them, don't re-specify them.

**The drift-guard test.** The existing `tests/test_data_contract.py:test_every_persisted_field_is_documented` checks `DecisionEvent` *dataclass fields* — which don't change here, so it can't catch a missing create-stage key. Add a sibling test in the same file (next to `test_report_kinds_documented`) that reads the doc text and asserts the new decision values and a representative set of the new context keys are present. This is a doc-presence check, the same shape as `test_report_kinds_documented` and `test_schema_version_named` — a substring scan over `_doc_text()`, no new dataclass introspection.

**One gotcha — keep the test's expected strings sourced from code, not this detail.** When you add the new test, pull the decision values and context-key names from the recorders (or import the `CREATE_*` constants step 3 exports) rather than hardcoding paraphrases, so the test fails if the doc and the real literals disagree. If you hardcode strings in the test, they must match the code literals exactly; an import-and-assert approach is sturdier.

## Tests

Test file: `tests/test_data_contract.py`.

- `test_create_decisions_documented` — asserts `"create-review"` and `"create-step-outcome"` appear in `DATA_CONTRACT.md`.
- `test_create_context_keys_documented` — asserts the new context keys (`candidate_fingerprint`, `file_footprint`, `split_steps`, `split_step_ids`, `predicate_counts`, `can_split`, `mode`, `action`, `had_split_hint`, `before_steps`, `after_steps`, `error_class`) each appear in the doc.
- `test_create_context_semantics_documented` — asserts the doc names the finding-count versus distinct-step distinction and says checkpoint-mode assessment events are excluded from fresh-signal counts while `candidate_fingerprint` dedupes repeated observations.
- `test_create_action_semantics_documented` — asserts the doc says `accept` means resolved change type equals proposed change type, not necessarily a raw Enter keypress.
- (existing, must stay green) `test_every_persisted_field_is_documented[DecisionEvent]` — still passes because no dataclass field is added.
- (existing, must stay green) `test_schema_version_named` — `TELEMETRY_SCHEMA_VERSION` is still named.

### Verification (non-code step)

This step changes no production code — only `DATA_CONTRACT.md` prose and one test. Verify by:
- **Doc accuracy** — every decision value and context key written in the doc matches a real literal in `plan_tool/telemetry.py` (`record_create_granularity_assessment`, `record_create_step_outcome`) and the create call sites at HEAD. No invented keys.
- **Aggregation semantics** — the doc clearly states `split` is a finding count, `split_steps` / `split_step_ids` are distinct-step signals, `mode="checkpoint"` assessment events are excluded from fresh-signal counts, and `candidate_fingerprint` dedupes repeated observations.
- **Outcome semantics** — the doc clearly states `action="accept"` means resolved equals proposed.
- **Schema-version claim** — confirm `TELEMETRY_SCHEMA_VERSION` is still `1` in `plan_tool/telemetry.py`; the doc must not claim a bump.
- **Internal links** — the new subsection's anchor and any cross-links inside `DATA_CONTRACT.md` resolve.
- **Drift guard runs** — `uv run pytest tests/test_data_contract.py -q` passes, including the two new cases.

## Acceptance criteria

- `DATA_CONTRACT.md` names both `create-review` and `create-step-outcome` as `granularity`-family `decision` values.
- `DATA_CONTRACT.md` documents the `context` keys for each: `mode` / `steps` / `candidate_fingerprint` / `file_footprint` / `split` / `split_steps` / `merge` / `split_step_ids` / `predicate_counts` / `can_split` for `create-review`, and `action` / `had_split_hint` / `before_steps` / `after_steps` / `error_class` for `create-step-outcome`.
- `DATA_CONTRACT.md` states that `split` is a finding count, `split_steps` / `split_step_ids` are distinct-step signals, `mode="checkpoint"` assessment events are excluded from fresh-signal counts, and `candidate_fingerprint` supports dedupe of repeated observations.
- `DATA_CONTRACT.md` states that `action="accept"` means resolved change type equals proposed change type, and that `unclassified-classified` is distinct from `override`.
- The doc states the split-only outcome keys are omitted when the gesture is not a split (absent ≠ zero).
- The doc states the change is additive and `TELEMETRY_SCHEMA_VERSION` is unchanged (`1`).
- `tests/test_data_contract.py` gains tests asserting the new decision values, context keys, and count/checkpoint semantics are present; `uv run pytest tests/test_data_contract.py -q` passes.
- `test_every_persisted_field_is_documented[DecisionEvent]` still passes (no new dataclass field).

## References

- [DATA_CONTRACT.md](../../../../DATA_CONTRACT.md) — the doc this step edits; its preamble fixes the "code wins, fix the doc" rule and the drift-guard contract this step extends.
- [JSON Lines (jsonlines.org)](https://jsonlines.org/) — the one-object-per-line format the decision log follows, for documenting the append-only event shape accurately.
- [json — JSON encoder and decoder — Python documentation](https://docs.python.org/3/library/json.html) — `json.dumps`/`loads` behavior backing the serialized `context` bag the new keys live in.

## Deferred

- Adding the create-side recorders and constants (`record_create_granularity_assessment`, `record_create_step_outcome`, `CREATE_MODE_*`, `CREATE_ACTION_*`) — owned by step 3.
- Wiring the assessment event into the review loop — step 4.
- Wiring the per-step outcome events into the interactive loop — step 5.
- Any `DecisionEvent` dataclass field change or `TELEMETRY_SCHEMA_VERSION` bump — out of scope; this change is additive under the open `context` bag.
- The outcome-linkage and `plan-tool telemetry` analysis surface — already deferred in the telemetry module's phase-1 scope.
