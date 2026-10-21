> **Auto-archived**: this plan was swept on 2026-07-12 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Add `decision_id`, `run_id`, fingerprint, and `anchor` fields to `DecisionEvent`; bump schema to 2

## Summary

Enrich the base `DecisionEvent` in `plan_tool/telemetry.py` with the join keys a later outcome resolver will need: `decision_id` (a content hash computed inside `record_decision`), `run_id` (read from a new `telemetry`-owned `ContextVar`), `plan_fingerprint` / `code_fingerprint` (caller-supplied), and `anchor` (a defaulted finding-slug join key frozen into the schema now, with no phase-1 producer). Bump `TELEMETRY_SCHEMA_VERSION` from `1` to `2`, keep `read_decisions` tolerant of old v1 lines that lack the new keys, and update the drift-guarded `DATA_CONTRACT.md` `DecisionEvent` section (including the `str`/`int` `step_id` normalization contract). The five new fields are all defaulted, so the 8 wrapper recorders keep working unchanged (their migration is step 2) and `telemetry.py` stays a stdlib-only leaf (new imports are `hashlib` and `contextvars` only). On green, every newly recorded event carries a stable `decision_id`, an empty-by-default `run_id`, empty-by-default fingerprints, and an empty-by-default `anchor`; old lines still parse.

## Table of Contents

- [Why](#why) — what the current schema can't do and why the schema must change first
- [Input](#input) — the v1 event shape and the drift-guard contract this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — the files this step touches
- [Implementation](#implementation) — the five new fields, the hash, the ContextVar, and the reader tolerance
- [Tests](#tests) — unit tests for the hash, the run-id scope, and old-line tolerance
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — stdlib docs for the primitives used
- [Deferred](#deferred) — what this step deliberately leaves to steps 2 and 3

## Why

Outcome-linkage is impossible from today's telemetry schema: a recorded decision and every later outcome share only `(plan_slug, ts)`, which is coarse and empty for a large share of real events, and nothing points at a specific decision or ties it to a run. The fix is a schema change, cleanly separable from the analysis surface that will consume it. Shipping the schema first lets real events start carrying the join keys now, so when the resolver lands (a later phase) there is data to validate it against. This step is the base-event slice: it adds the keys to `DecisionEvent` and `record_decision` and bumps the version, without touching the 8 wrappers (step 2) or wiring any caller (step 3).

## Input

This step reads two existing contracts and must not break either:

- **The v1 `DecisionEvent` JSONL line** (`plan_tool/telemetry.py`, `read_decisions`). Each line today has `schema_version`, `ts`, `kind`, `decision`, `plan_slug`, `context`. After the bump, real logs will hold a mix of v1 lines (no new keys) and v2 lines. `read_decisions` reconstructs the event key-by-key with `d.get(...)`, so it must add `.get(...)` reads for the five new keys, each defaulting so a v1 line parses without raising. Do **not** filter or reject a line by version — the module's contract is "tolerant of older/forward lines".
- **The `DecisionEvent` drift-guard contract** (`plan_tool/data_contract.py`, the `PersistedDataclassContract(owner="DecisionEvent", …)` entry; `tests/test_data_contract.py`, `test_every_persisted_field_is_documented_in_own_section` and `test_schema_constants_are_documented_from_registry`). The registry discovers `DecisionEvent`'s fields dynamically via `dc.fields`, so the five new fields are picked up automatically — but the guard then requires each one to appear as `` `name` `` in the `DecisionEvent` section of `DATA_CONTRACT.md`. That doc edit is mandatory, not polish.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/telemetry.py` — add five fields to `DecisionEvent` (`decision_id`, `run_id`, `plan_fingerprint`, `code_fingerprint`, `anchor`); add `_active_run_id` `ContextVar` + both a `set_active_run_id` setter and a `scoped_run_id` scope contextmanager wrapping it; compute `decision_id` inside `record_decision`; read `run_id` from the ContextVar; accept `plan_fingerprint` / `code_fingerprint` / `anchor` (and an optional `step_id` used only for the hash); bump `TELEMETRY_SCHEMA_VERSION` to `2`; extend `read_decisions` to read the new keys with defaults.
  - `DATA_CONTRACT.md` — add the five new fields to the `DecisionEvent` field table; update the `schema_version` row prose that currently says "**`1` = `TELEMETRY_SCHEMA_VERSION`**" to `2`; add a note documenting `decision_id`'s deliberate non-uniqueness (a stable handle to a class of content-identical rows; the resolver falls back to `context`/log-position to pick a single row); add a note documenting the `step_id` normalization contract (decisions store `step_id`/`step_ids` as `str`; sidecars/recs as `int`; the phase-3 resolver casts).
  - `plan_tool/data_contract.py` — **likely no code change.** The registry entry already discovers fields dynamically and already lists `schema_constants=("TELEMETRY_SCHEMA_VERSION",)`. Listed here because it owns the `DecisionEvent` contract the drift guard reads; confirm the five fields auto-discover and stay documented. Leave `registered_open_bag_keys` alone — `plan_fingerprint` / `code_fingerprint` stay registered as `context` keys through phase 1 (dual-home keeps writing them into `context`; removing the registration is phase-2 work).
  - `tests/test_telemetry.py` — adapt the existing roundtrip test; add hash / run-id / fingerprint / old-line tests.
  - `tests/test_data_contract.py` — the parametrized doc-coverage test already enforces the new fields once documented; optionally add one focused assertion.

## Implementation

**Foundational logic:** `record_decision` becomes the single place that stamps a decision's identity — it mints `decision_id`, pulls `run_id` from a telemetry-owned `ContextVar`, and stores caller-supplied fingerprints. `record_decision` is the one writer of the log; every wrapper funnels through it, so enriching it here is enough for step 2 to just forward args.

**Add five defaulted fields to `DecisionEvent`.** Append them after `context` so no existing field moves and every field with a default stays after the non-default ones:

- `decision_id: str = ""` — always set by `record_decision`; the `""` default is only for `read_decisions` reconstructing an old v1 line.
- `run_id: str = ""` — read from the ContextVar; `""` when no run is active.
- `plan_fingerprint: str = ""` — caller-supplied digest.
- `code_fingerprint: dict[str, str] = field(default_factory=dict)` — caller-supplied path→hash map; empty when absent.
- `anchor: str = ""` — a caller-supplied finding-slug join key (the `[anchor-slug]` a decision is about), so `convergence_diagnosis._matches`' step→anchor→title tiers apply in phase 3. Frozen into the schema now; **no phase-1 producer** (the wrappers that would supply it are wired in phase 2), so every phase-1 event records `""`. This mirrors `run_id` — the field ships before its producer.

All five defaulted keeps the wrappers green without edits — that back-compat is the constraint step 2 relies on. Do not add these as positional/required args anywhere.

**Compute `decision_id` as a stable stdlib hash.** Follow the plan's Architecture decision 1: `sha256` over `(schema_version, kind, decision, plan_slug, plan_fingerprint, step_id-if-any, ts)`, truncated to 16 hex chars. Use `hashlib.sha256` on a canonical UTF-8 string of those fields joined by a delimiter (or `json.dumps(..., sort_keys=True)`) — pick one canonical form and keep it. Key constraints:

- **Call `clock()` exactly once** and reuse that `ts` for both the hash and the stored `ts`. Calling it twice would compute the id over a different timestamp than the one stored.
- **`run_id`, `code_fingerprint`, and `anchor` are deliberately out of the hash.** A decision's identity should not depend on which run observed it, its code fingerprint, or the finding slug it references (all join keys, not identity). Follow the plan's tuple exactly.
- **`decision_id` is not globally unique — `context` is deliberately out of the hash.** Two events with an identical hash tuple + `ts` collide by design, but because the tuple omits `context`, genuinely-distinct same-family decisions sharing a second-precision `ts` (e.g. `record_granularity` with different `split`/`merge`, or repeated `record_audit_coverage` for one plan) also collide despite carrying different `context`. So a downstream resolver must not treat `decision_id` as a globally-unique key. This collision is **accepted for phase 1** — no line-ordinal/sequence tiebreaker is added, because that would force `record_decision` to read the append-only log and break its stdlib-only, best-effort leaf shape. State in the code comment (terse) and the `DATA_CONTRACT.md` note that `decision_id` is a stable handle to a *class* of content-identical decisions, not a per-row key — because `ts`/`plan_slug`/`plan_fingerprint` are already hash inputs, colliding rows share them, so only `context` distinguishes the rows; the phase-3 resolver treats `decision_id` as non-unique and falls back to `context` (or log position) when it must pick a single row.
- **`step_id-if-any`:** add an optional `step_id: Optional[str] = None` param to `record_decision`, folded into the hash as its normalized string form when present and as `""` when `None`. Default `None` so no wrapper is affected here; wiring the outcome recorder to pass it is step 2's call.

**Add a `telemetry`-owned run-id `ContextVar` + helper.** Mirror the pattern in `plan_tool/shell.py` (`_active_sink` / `set_active_sink`, and the token-reset `push_active_notifier` / `pop_active_notifier` pair):

- `_active_run_id: contextvars.ContextVar[str]` with `default=""` (name it e.g. `"plan_tool_active_run_id"`).
- Two helpers the run entrypoints will use in step 3: a bare `set_active_run_id(run_id)` setter (returns the reset `Token`, mirroring `set_active_sink`) and a `@contextlib.contextmanager` `scoped_run_id(run_id)` that calls it and resets the token in a `finally`, so nested/sequential runs restore correctly. The contextmanager is the intended entrypoint call shape; the bare setter is the primitive it wraps. `record_decision` reads the var via `_active_run_id.get()`; **read it at call time inside `record_decision`**, not captured earlier, so a run-id bound mid-process is honored. `contextvars` and `contextlib` are stdlib, so the leaf constraint holds.

Ship the ContextVar and helper here even though no caller sets them yet — step 3 wires the run entrypoints (`plan_tool/run_log.py`, `plan_tool/cli/run_cmd.py`). Until then every event records `run_id == ""`, which is correct.

**Accept the fingerprints and anchor as caller args.** `record_decision` gains `plan_fingerprint: str = ""`, `code_fingerprint: Optional[dict[str, str]] = None` (stored as `dict(code_fingerprint or {})`, matching how `record_plan_criteria_breakdown` already handles its optional map), and `anchor: str = ""`. `telemetry.py` must **not** import `review_persistence` or `fingerprint` — callers pass the already-computed digest. `anchor` takes no phase-1 producer here (step 2 leaves the wrappers unwired for it); it is accepted and stored so phase-2 callers can supply it without another schema change.

**Bump the version and keep the reader tolerant.** Set `TELEMETRY_SCHEMA_VERSION = 2`. Extend `read_decisions` to reconstruct the five new fields defensively, each defaulting to its empty form when the key is absent (e.g. `str(d.get("decision_id", ""))`, `dict(d.get("code_fingerprint", {}))`, `str(d.get("anchor", ""))` — mirror the module's existing per-field `d.get(...)` reconstruction style). `read_decisions` must read the **stored** `decision_id`, never recompute it. Old v1 lines (missing all five keys) must parse with defaults, unchanged from today's `test_read_skips_malformed_lines` behavior.

**Rejected alternative:** passing `run_id` as a per-recorder argument. That would force all 8 wrappers plus every call site to thread it, and the run entrypoint is the natural owner of "which run is active" — a `ContextVar` set once at the run boundary is the same shape the run-log and `shell.py` sink already use.

## Tests

### Test-creation order (feature step)

This is a feature step — write these unit tests alongside the implementation. Every new test must be green before the step is done.

In `tests/test_telemetry.py`:

- `test_record_then_read_roundtrips` (adapt existing) — the recorded event now carries a non-empty `decision_id`; update the expected event or assert the non-id fields plus `decision_id` being a 16-char hex string, rather than equality against an id-less `DecisionEvent`.
- `test_decision_id_is_stable` — same inputs and same pinned `clock` produce the same `decision_id` across two calls; the id is 16 hex chars.
- `test_decision_id_changes_with_content` — changing any of `kind` / `decision` / `plan_slug` / `plan_fingerprint` / `step_id` / `ts` yields a different `decision_id`.
- `test_run_id_read_from_contextvar` — inside the run-id scope, a recorded event's `run_id` equals the bound value; outside any scope it is `""`.
- `test_run_id_scope_clears_on_exit` — after the scope exits, the next recorded event's `run_id` is back to `""` (token reset in `finally`).
- `test_plan_and_code_fingerprint_recorded` — passing `plan_fingerprint` and `code_fingerprint` stores them on the base event and reads back unchanged.
- `test_anchor_recorded_and_defaults_empty` — passing `anchor="x"` stores it on `event.anchor` and reads back unchanged; omitting it yields `""`; `anchor` does not change `decision_id` (it is out of the hash).
- `test_reads_old_v1_line_without_new_fields` — a hand-written v1 JSONL line (no `decision_id` / `run_id` / fingerprints / `anchor`) reads back with all five defaults and does not raise.
- `test_schema_version_is_two` — `TELEMETRY_SCHEMA_VERSION == 2`, guarding the bump.
- Confirm `test_record_is_best_effort_never_raises` and `test_non_serializable_context_is_dropped_not_raised` still pass unchanged — the never-raise guarantee must survive the added hashing/ContextVar read.

In `tests/test_data_contract.py`:

- The parametrized `test_every_persisted_field_is_documented_in_own_section` already covers `DecisionEvent`; it turns red until the five fields are added to `DATA_CONTRACT.md`, which is the wiring proof. Optionally add `test_decision_event_new_fields_documented` asserting `` `decision_id` ``, `` `run_id` ``, `` `plan_fingerprint` ``, `` `code_fingerprint` ``, `` `anchor` `` appear in the `DecisionEvent` section.

## Acceptance criteria

- `DecisionEvent` has fields `decision_id`, `run_id`, `plan_fingerprint`, `code_fingerprint`, `anchor`, all defaulted.
- `record_decision` stamps a non-empty 16-hex-char `decision_id` on every event, deterministic for identical inputs + `ts`.
- `record_decision` reads `run_id` from a `telemetry`-owned `ContextVar` defaulting to `""`; both a `set_active_run_id` setter and a `scoped_run_id` scope contextmanager exist, and the scope resets on exit.
- `record_decision` accepts and stores `plan_fingerprint` (str), `code_fingerprint` (path→hash map), and `anchor` (str), all optional/defaulted; `anchor` is out of the `decision_id` hash.
- `TELEMETRY_SCHEMA_VERSION == 2`.
- `read_decisions` parses both a v2 line (with new keys) and a v1 line (without them), the latter yielding defaults, and never raises on a malformed line.
- `telemetry.py` imports no first-party module (`grep -E '^(from|import) plan_tool' plan_tool/telemetry.py` stays empty).
- All 8 existing wrapper recorders compile and their existing tests pass with no edits to the wrappers.
- `DATA_CONTRACT.md`'s `DecisionEvent` section documents the five new fields, states version `2`, the `decision_id` non-uniqueness (class-handle semantics; resolver falls back to `context`/log-position), and the `str`/`int` `step_id` normalization contract; `tests/test_data_contract.py` and `tests/test_telemetry.py` pass.

## References

- [hashlib — Secure hashes and message digests](https://docs.python.org/3/library/hashlib.html) — `sha256` / `hexdigest()` for the stable stdlib `decision_id` content hash.
- [contextvars — Context Variables](https://docs.python.org/3/library/contextvars.html) — `ContextVar` / `set()` / `reset()` / `Token` semantics for the telemetry-owned `run_id` variable with `finally`-clear.
- [dataclasses — Data Classes](https://docs.python.org/3/library/dataclasses.html) — `field(default_factory=...)` / `asdict`, for adding the five backward-compatible defaulted fields.
- [json — JSON encoder and decoder](https://docs.python.org/3/library/json.html) — `dumps` / `loads` for serializing each line and tolerantly parsing pre-bump v1 lines.
- [JSON Lines](https://jsonlines.org/) — the one-object-per-line format `decisions.jsonl` uses; keep append-per-line and old-line-tolerant reads well-formed.

## Deferred

- **Forwarding the new keys through the 8 wrapper recorders** — owned by step 2; step 1 keeps `record_decision`'s new params defaulted so the wrappers stay unchanged.
- **Dual-homing `plan_fingerprint` / `code_fingerprint` onto the base event in `record_plan_criteria_breakdown`** — owned by step 2 (forward to the base fields *and keep* the `context` copies). In step 1 the base fields are defaulted-empty and the fingerprints live only in that wrapper's `context`. Dropping the `context` copy and removing the keys from `registered_open_bag_keys` is **phase 2**, not step 2 — the open-bag registration stays as-is through phase 1.
- **Setting the run-id `ContextVar` at the run entrypoints and clearing it in a `finally`** — owned by step 3 (`plan_tool/run_log.py`, `plan_tool/cli/run_cmd.py`); step 1 only ships the variable, the helper, and the read.
- **Wiring `step_id` into the outcome wrapper** — step 1 only adds the optional `step_id` hash input to `record_decision`; the outcome recorder (`record_create_step_outcome`) passing it is step 2. **Wiring a producer for `anchor`** is phase 2 — step 1 ships the defaulted field, no wrapper supplies it in phase 1.
- **The read-only `plan-tool telemetry` resolver / analysis surface** — a separate later phase; this step ships no consumer.
- **Updating BACKLOG #72** — owned by step 4.
