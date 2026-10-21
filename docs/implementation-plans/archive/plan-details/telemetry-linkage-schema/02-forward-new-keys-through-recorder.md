> **Auto-archived**: this plan was swept on 2026-07-12 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Forward the fingerprint/step_id keys through the 8 recorder wrappers and dual-home plan-criteria's fingerprints onto the base event (kept in context)

## Summary

Wire the base-event join keys added in step 1 through the 8 convenience recorders in `plan_tool/telemetry.py`. The headline change is **dual-homing**: `record_plan_criteria_breakdown` **also** forwards `plan_fingerprint`/`code_fingerprint` to `record_decision`'s new base-event fields **while keeping** its existing `context` copies, so the base event carries the join key without breaking the in-repo consumer that reads it from `context` (`split_criteria.py`'s drift diff). The other wrappers gain defaulted `plan_fingerprint`/`code_fingerprint` forwarding params so a caller with a plan can supply them, and `record_create_step_outcome` forwards its existing `step_id` into the `decision_id` hash. The `("DecisionEvent", "context")` open-bag registration in `plan_tool/data_contract.py` and the plan-criteria context table in `DATA_CONTRACT.md` are **left intact** (both fingerprints stay context keys); the doc gains a note that they now *also* live on the base fields. On green, a recorded plan-criteria event carries the fingerprints on **both** the base event and `context`, `split_criteria.py` and its tests are untouched and green, and `telemetry.py` stays a stdlib-only leaf. Collapsing to a single home (dropping the `context` copy, migrating the reader) is deferred to phase 2.

## Table of Contents

- [Why](#why) — why the fingerprints are dual-homed onto the base event and the wrappers need the forwarding params
- [Input](#input) — the step-1 base-event fields and the open-bag/doc contracts this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — the files this step touches
- [Implementation](#implementation) — the dual-home forwarding, the per-wrapper forwarding, and the doc note
- [Tests](#tests) — unit tests for the dual-home, step_id forwarding, and the base-field assertions
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — stdlib docs for the primitives used
- [Deferred](#deferred) — call-site backfill and other work left to later slices

## Why

Step 1 added `decision_id`, `run_id`, `plan_fingerprint`, `code_fingerprint`, and `anchor` to the base `DecisionEvent` but left the 8 wrappers untouched, so today the fingerprints live only in `record_plan_criteria_breakdown`'s `context` bag while the base fields sit empty. A later resolver wants the fingerprint on the base event so every decision family exposes it uniformly. This step puts it there — but **additively**: it forwards the fingerprints to the base fields *and keeps* the `context` copies (dual-home), because the existing in-repo consumer `split_criteria.py` (`compute_criteria_drift` / `_last_different_fingerprint_event`) reads `event.context["plan_fingerprint"]`, and #72's own cited "first concrete consumer" must not break. Removing the `context` copy and migrating that reader to the base field is deliberately deferred to phase 2; phase 1 stays non-breaking. This step also adds the forwarding plumbing to the remaining wrappers so a caller that has a plan can supply the keys uniformly, and folds `record_create_step_outcome`'s `step_id` into the `decision_id` hash, so step-scoped create decisions that share a second-precision `ts` stop colliding.

## Input

This step builds on **step 1** (base-event fields + `record_decision` enrichment) and reads two contracts it must keep consistent:

- **Step 1's enriched `record_decision`** (`plan_tool/telemetry.py`). Step 1 added `plan_fingerprint: str = ""`, `code_fingerprint: Optional[dict[str, str]] = None`, `anchor: str = ""`, and `step_id: Optional[str] = None` params (the last folded into the `decision_id` hash), all defaulted. This step forwards wrapper args into those params — it does not re-specify how step 1 stamps `decision_id`/`run_id`. Follow step 1's shipped signature; if its final param names differ, follow what step 1 shipped.
- **The open-bag registration + doc for the `DecisionEvent` `context` bag** (`plan_tool/data_contract.py`, `registered_open_bag_keys()`). It lists `plan_fingerprint` and `code_fingerprint` under the `("DecisionEvent", "context")` key, and `DATA_CONTRACT.md`'s "Plan split-criteria breakdown" section documents them as context keys. Under dual-home both **stay** — the wrapper keeps writing the fingerprints into `context`, so the registration and the context table remain accurate and must **not** be edited to remove them (the doc gains only a note that they *also* live on the base fields). The consumer's `context` read (`plan_tool/split_criteria.py:654`/`:677`) and its `tests/test_split_criteria.py` assertions (`:414`/`:450`) therefore stay valid, untouched.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/telemetry.py` — dual-home the fingerprints in `record_plan_criteria_breakdown` (forward to the base fields *and keep* the `context` writes); add defaulted `plan_fingerprint`/`code_fingerprint` forwarding params to the other 7 wrappers and forward them to `record_decision`; forward `record_create_step_outcome`'s `step_id` into the hash.
  - `DATA_CONTRACT.md` — **keep** the `plan_fingerprint`/`code_fingerprint` rows in the plan-criteria "Context keys" table; add a short note that both **also** live on the base `DecisionEvent` fields (added to the base table in step 1).
  - `tests/test_telemetry.py` — extend the plan-criteria tests to assert the fingerprints on **both** the base fields and `context`; add step_id-forwarding and per-wrapper forwarding tests.
- **Deliberately not touched (dual-home leaves them as-is):**
  - `plan_tool/data_contract.py` — `registered_open_bag_keys()` keeps listing `plan_fingerprint`/`code_fingerprint` under `("DecisionEvent", "context")` (the wrapper still writes them there); no code change.
  - `tests/test_data_contract.py` — `test_plan_criteria_context_keys_documented` still passes unchanged (the context keys are unchanged); adding the base-field note to `DATA_CONTRACT.md` is prose and does not disturb the field-coverage drift guard.
  - `plan_tool/split_criteria.py` + `tests/test_split_criteria.py` — the dual-home invariant: they read the fingerprint from `context`, which is preserved, so both stay green untouched. Migrating them to the base field is phase-2 work.

## Implementation

**Foundational logic:** forward `plan_fingerprint`/`code_fingerprint` from the plan-criteria wrapper onto the base event **in addition to** its existing `context` writes (dual-home), and add the same base-field forwarding path to every other wrapper — the base event carries the join key uniformly while the `context` copy keeps the existing consumer working.

**Dual-home the fingerprints in `record_plan_criteria_breakdown`.** This is the one wrapper that already carries fingerprints; make its base-field forwarding additive.

- Keep the wrapper's signature the same (`plan_fingerprint: str`, `code_fingerprint: Optional[dict[str, str]] = None`) — its sole caller `plan_tool/split_criteria.py` (the `record_plan_criteria_breakdown(...)` call in `_record_breakdown`) passes them and is out of this step's scope, so its call must stay unchanged.
- **Keep** adding `plan_fingerprint` and `code_fingerprint` to the `context` dict exactly as today (including the `if code_fingerprint is not None:` guard that omits an absent code fingerprint from `context`) — plus `criteria`/`criteria_count`/`fired_count`. The `context` shape does not change.
- **Also** forward the two fingerprints to `record_decision(..., plan_fingerprint=plan_fingerprint, code_fingerprint=code_fingerprint)` so they land on the base event as well.
- **Consequence to document, not fix:** on the **base field**, `code_fingerprint` defaults to `{}` and is always serialized, so a base-field reader sees `{}` for an absent code fingerprint (no `code_fingerprint_present` marker, and the plan does not add one). The **`context` copy** still preserves the omitted-when-absent distinction, so the `plan_tool/split_criteria.py` consumer is unaffected. Note the base-field always-`{}` behavior in the doc; do not invent a presence marker (not in the plan's frontmatter).
- **Line-cap edge (name it, don't fix it in phase 1):** dual-home writes `code_fingerprint`'s path→hash map **twice** on a plan-criteria event (base field + `context`), and `record_decision` drops the **entire** event when the serialized line exceeds `_MAX_LINE_BYTES` (64 KiB, `plan_tool/telemetry.py`). So doubling the largest variable-size payload could tip a near-ceiling event over and silently lose it. Assessment: a real `code_fingerprint` is a modest map (tens of entries × ~80 bytes ≈ low-single-KiB), far under the cap, so this is safe in practice — but it is a real edge the plan owns. Phase 2's single-home removes the duplication; **do not** raise the cap or add per-field truncation here (out of scope). Add a test asserting a plan-criteria event with a realistic `code_fingerprint` stays well under `_MAX_LINE_BYTES` and records (not drops).

**Add fingerprint forwarding to the other 7 wrappers.** For `record_granularity`, `record_code_reveals_split`, `record_create_granularity_assessment`, `record_create_step_outcome`, `record_audit_coverage`, `record_convergence`, and `record_prompt_budget`:

- Add `plan_fingerprint: str = ""` and `code_fingerprint: Optional[dict[str, str]] = None` params (defaulted) and forward them to `record_decision`.
- Defaulted params keep every current call site unchanged — this is plumbing so a caller that has a plan *can* supply the keys. Populating those call sites is phase 2 (deferred); most callers pass nothing here and the base fields stay empty.
- Do **not** move or remove any wrapper's existing `context` keys (e.g. `record_code_reveals_split`'s `step_ids`, `record_create_granularity_assessment`'s `candidate_fingerprint`) — the only base-field addition to an already-populated wrapper this step is the plan-criteria fingerprint dual-home, which is additive.

**Forward `step_id` into the hash for the step-scoped wrapper.** `record_create_step_outcome` already receives `step_id: str` and writes it into `context`. Also forward it to `record_decision(..., step_id=step_id)` so the `decision_id` hash folds it in. Keep the `context["step_id"]` write too — it stays a documented context key; the forward is additive.

- `record_code_reveals_split` carries `step_ids` (plural) with no single step focus, so leave its `record_decision` `step_id` unset. The `decision_id` hash's `step_id` input is a single optional string; a plural set does not map to it.

**Leave the open-bag registration intact.** `plan_tool/data_contract.py`'s `registered_open_bag_keys()` keeps listing `"plan_fingerprint"` and `"code_fingerprint"` under `("DecisionEvent", "context")` — the wrapper still writes them into `context`, so the registration still tracks reality. `registered_open_bag_keys()` feeds `registry_fingerprint()` and the `## Input`-section reference validator (`check_input_contract_references`); because the `context` keys are unchanged, no edit is needed here. (Removing the registration is phase-2 work, paired with dropping the `context` copy.)

**Update `DATA_CONTRACT.md` (additive note only).** In the "Plan split-criteria breakdown" section's Context keys table, **keep** the `plan_fingerprint` and `code_fingerprint` rows (still written to `context`). Add one line noting both are **also** carried on the base `DecisionEvent` fields as of phase 1 (the base field table gained them in step 1), and that phase 2 will drop the `context` copy. Leave `criteria`/`criteria_count`/`fired_count` rows in place.

**Constraints that must hold:**

- **`telemetry.py` stays a stdlib-only leaf** — `grep -E '^(from|import) plan_tool' plan_tool/telemetry.py` stays empty. Fingerprints remain caller-supplied strings/dicts; never import `review_persistence` or `fingerprint`.
- **`record_decision` stays the single writer.** All 8 wrappers keep funneling through it; the enrichment already lives there from step 1.
- **Never-raise guarantee holds.** The wrappers add no new failure path — forwarding args is inert; `record_decision` still swallows every error.

## Tests

### Test-creation order (feature step)

This is a **feature** step — write these unit tests alongside the implementation. Every new/updated test must be green before the step is done.

In `tests/test_telemetry.py`:

- `test_record_plan_criteria_breakdown_roundtrips` (extend existing) — assert `event.plan_fingerprint == "pf123"` on the base event **and** `event.context["plan_fingerprint"] == "pf123"` (dual-home: both present); keep the `criteria`/`criteria_count`/`fired_count` context assertions.
- `test_plan_criteria_code_fingerprint_dual_homed` (extend existing `..._omits_code_fingerprint_when_absent`) — with a map: `event.code_fingerprint == {"plan_tool/foo.py": "deadbeef"}` on the base field **and** `event.context["code_fingerprint"] == {"plan_tool/foo.py": "deadbeef"}`. Without a map: `event.code_fingerprint == {}` on the base field (always serialized) **and** `"code_fingerprint"` is **absent** from `event.context` (the `context` copy keeps its omitted-when-absent guard).
- `test_create_step_outcome_forwards_step_id_to_hash` — two `record_create_step_outcome` calls differing only in `step_id` (same `plan_slug`/`ts`) yield different `decision_id`.
- `test_wrappers_forward_plan_fingerprint` — a wrapper (e.g. `record_granularity`) called with `plan_fingerprint="pf"` stores it on `event.plan_fingerprint`; that wrapper does not write it into `context` (only the plan-criteria wrapper dual-homes).
- `test_dual_home_code_fingerprint_stays_under_line_cap` — a plan-criteria event with a realistic `code_fingerprint` (e.g. ~50 path→hash entries) serializes well under `_MAX_LINE_BYTES` even with the fingerprint written twice, and the event **records** (reads back), not drops — guarding the dual-home line-cap edge.
- Confirm `test_plan_criteria_criteria_rows_passthrough`, `test_plan_criteria_counts_derived`, and `test_plan_criteria_recorder_is_best_effort` still pass with no change (their context assertions are unaffected).

In `tests/test_split_criteria.py` (no edit — a green-untouched proof):

- Confirm the existing `context["plan_fingerprint"]` assertions (`:414`/`:450`) and the `compute_criteria_drift` tests stay green unchanged — the dual-home invariant that phase 1 does not break the drift consumer.

`tests/test_data_contract.py` needs **no step-2 edit**: `test_plan_criteria_context_keys_documented` still lists `plan_fingerprint`/`code_fingerprint` as context keys (unchanged), and the field-coverage drift guard is undisturbed by the additive `DATA_CONTRACT.md` note.

## Acceptance criteria

- A recorded plan-criteria event carries `plan_fingerprint` on **both** `event.plan_fingerprint` and `event.context["plan_fingerprint"]` (dual-home); `code_fingerprint` likewise on `event.code_fingerprint` and, when the caller supplies a map, `event.context["code_fingerprint"]`.
- `event.code_fingerprint == {}` (base field, always serialized) when the caller passes no code fingerprint, and `"code_fingerprint"` is absent from `event.context` in that case; `criteria`/`criteria_count`/`fired_count` remain in `event.context`.
- Two `record_create_step_outcome` calls differing only in `step_id` produce different `decision_id` values.
- The other wrappers accept defaulted `plan_fingerprint`/`code_fingerprint` params and forward them to the base event; every existing call site compiles unchanged.
- `registered_open_bag_keys()[("DecisionEvent", "context")]` **still** contains `plan_fingerprint` and `code_fingerprint` (unchanged — the wrapper still writes them into `context`).
- `DATA_CONTRACT.md`'s plan-criteria Context keys table **still** lists the two fingerprints and adds a note they are also base fields (dropped from `context` in phase 2); the drift guard (`tests/test_data_contract.py`) is green.
- `split_criteria.py` and `tests/test_split_criteria.py` are unchanged and green (the dual-home no-break proof).
- `telemetry.py` imports no first-party module.
- `tests/test_telemetry.py` passes.

## References

- [dataclasses — Data Classes — Python 3.13 documentation](https://docs.python.org/3/library/dataclasses.html) — `asdict` and default fields, for how the dual-homed base fields serialize (including `code_fingerprint` always emitting `{}`).
- [hashlib — Secure hashes and message digests — Python 3.13 documentation](https://docs.python.org/3/library/hashlib.html) — `sha256`/`hexdigest`, for confirming `step_id` folds into the step-1 `decision_id` hash.
- [json — JSON encoder and decoder — Python 3.13 documentation](https://docs.python.org/3/library/json.html) — `dumps`/`loads`, the serialization the dual-homed fields flow through.

## Deferred

- **Single-home the fingerprints** — dropping the dual-homed `context` copies from `record_plan_criteria_breakdown`, removing them from the `("DecisionEvent", "context")` open-bag registration, and migrating `split_criteria.py`'s drift diff (+ `tests/test_split_criteria.py`) to read the base `plan_fingerprint` field is **phase 2**. Phase 1 keeps both homes so the consumer never breaks.
- **Backfilling the fingerprint keys at every call site** — populating `plan_fingerprint`/`code_fingerprint` at the create/audit/convergence/prompt-budget call sites is phase 2 (`plan_tool/create.py`, `plan_tool/review.py`, `plan_tool/cli/completeness_phases.py`, `plan_tool/cli/convergence_cmd.py`, etc.); this step only adds the forwarding params so those sites can pass them later.
- **Setting the `run_id` ContextVar at run entrypoints** — owned by step 3 (`plan_tool/run_log.py`, `plan_tool/cli/run_cmd.py`); until then every event records `run_id == ""`.
- **A `code_fingerprint_present` marker on the base event** — the base field is always `{}`/populated with no omitted-vs-empty distinction; the `context` copy still preserves that distinction, so no presence marker is needed and none is added (not in the plan's frontmatter).
- **Wiring an `anchor` producer** — step 1 ships the defaulted `anchor` base field, but no wrapper supplies it in phase 1; a finding-scoped producer is phase 2. `anchor` stays **out of the `decision_id` hash** by design (a join key, not identity). This step forwards only the single `step_id` a wrapper already holds.
- **Updating BACKLOG #72** — owned by step 4.
