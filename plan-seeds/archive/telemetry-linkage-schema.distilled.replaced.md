> **Replaced**: this file has been superseded by `docs/implementation-plans/2-telemetry-linkage-schema.md`.
> Preserved here for history; do not edit.

## Overview

Phase 1 of BACKLOG #72 (decision/outcome telemetry): the schema-only slice. It enriches the base `DecisionEvent` in `plan_tool/telemetry.py` with the join keys a later resolver will need to tie a recorded heuristic *decision* to what actually *happened*, but ships **no new consumer** — the read-only `plan-tool telemetry` resolver/analysis surface is a separate later plan (phase 3). Concretely: add `decision_id` (a stdlib content hash computed inside `record_decision`), `run_id` (flowed via a `telemetry`-owned `ContextVar`), and `plan_fingerprint`/`code_fingerprint` (caller-supplied string args) to the base event; migrate the 8 existing recorders; bump `TELEMETRY_SCHEMA_VERSION` while keeping `read_decisions` tolerant of old v1 lines; and update the drift-guarded `DATA_CONTRACT.md`. The change is backward-compatible and keeps `telemetry.py` a stdlib-only leaf (no first-party imports).

## Problem statement

Outcome-linkage is **impossible from today's telemetry schema**. The spike (`.tmp/72-telemetry-linkage.spike.md`, 347 real events) found that decisions and every outcome source share only `(plan_slug, ts)` — coarse, and empty for 42% of real events — and no post-hoc join logic can recover what the events never carried. Nothing today can point at a specific decision, and the run-log stays an island because decision events carry no `run_id`. The prerequisite is therefore a schema change, cleanly separable from the analysis surface that consumes it. Shipping the schema first lets real events start accumulating the join keys now, so that when the resolver lands (phase 3) there is data to validate it against — the spike's smoke test can't run today because the fingerprint- and outcome-carrying recorders have never fired.

## Architecture

Five resolved design decisions ground the build:

1. **`decision_id` is a content hash computed inside `record_decision`.** A stable `sha256` over `(schema_version, kind, decision, plan_slug, plan_fingerprint, step_id-if-any, ts)`, truncated (e.g. 16 hex), using stdlib `hashlib` so `telemetry.py` stays stdlib-only. Its sole job is to make a decision referenceable by a later outcome. Two events with identical content+ts collide by design (they are the same decision); `ts` is second-precision, so genuinely distinct decisions differ on some field.

2. **`run_id` flows via a `telemetry`-owned `ContextVar`, not a per-recorder arg.** Mirror `plan_tool/shell.py:_active_sink` / `set_active_sink`: `telemetry.py` owns `_active_run_id: ContextVar[str]` (default `""`) plus `set_active_run_id()` / a scope helper, and `record_decision` reads it. The run/command entrypoints that already start a `RunLogWriter` (`plan_tool/run_log.py`, `new_run_id`, `RunLogWriter.start`) set it to the same `run_id` the run-log stamps, in a `finally`-cleared scope. `contextvars` is stdlib, so the leaf constraint holds. Stamp `run_id` only when a run is active; leave `""` otherwise (the prompt-budget shell backstop often has no run).

3. **`plan_fingerprint` (+ optional `code_fingerprint`) promoted to the base event, caller-supplied.** The renumber-proof anchor (survives `split` id renumbering, unlike `step_id`). It must be a string arg the caller passes (as `record_plan_criteria_breakdown` already does) — `telemetry.py` must not import `review_persistence`/`fingerprint`. Callers pass the digest from `compute_plan_fingerprint` / `compute_code_fingerprint`; optional/`""` when a decision has no plan context.

4. **Normalize `step_id` type across the seam.** Decisions store step ids as `str`, sidecars/recs as `int` — a silent join-breaker. Keep decision-side `step_id`/`step_ids` as `str` and have the future resolver cast, but document the canonical form here so phase 3 doesn't guess. Carry the finding `anchor` slug too where a decision is about a specific finding, so `convergence_diagnosis._matches`' step→anchor→title tiers apply unchanged in phase 3.

5. **Migrate all 8 recorders uniformly.** `record_decision` gains the enrichment; each wrapper (`record_granularity`, `record_code_reveals_split`, `record_create_granularity_assessment`, `record_create_step_outcome`, `record_audit_coverage`, `record_convergence`, `record_plan_criteria_breakdown`, `record_prompt_budget`) forwards the keys it can supply (fingerprint where the caller has a plan; `""`/omitted otherwise). `plan-criteria-breakdown` already carries the fingerprints in `context` — **promote** them to the base event and stop duplicating them (or keep one, documented) so there's a single home.

## Out of scope

- **The resolver / `plan-tool telemetry` analysis-and-recommend surface** — phase 3; no consumer of the new keys ships here.
- **Deriving outcome verdicts** (`acted-on` / `no-op` / `reverted`) — phase 3.
- **Backfilling historical events** — the 347 existing events stay v1; only new events carry the keys, with no migration of old data.
- **Adding new decision *sites*** (e.g. escalate-to-split, `--refresh` drift-gate) — a separate #72 slice; phase 1 only enriches the 8 recorders that exist.
- **Changing `telemetry.py`'s leaf status** — it stays stdlib-only; importing a fingerprint producer is the wrong design (callers pass strings).

## Risks

- **Leaf-purity regression** — the seductive wrong move is importing `review_persistence`/`fingerprint` into `telemetry.py`. Mitigation: fingerprints are caller-supplied string args; keep the stdlib-only import test green.
- **ContextVar leakage across threads/runs** — a crashed or timed-out run could leave a stale `run_id` wired for the next (the `bench` daemon-thread hazard the `_active_sink` docstring names). Mitigation: mirror `_active_sink`'s per-thread `ContextVar` + `finally`-clear.
- **Silent schema drift** — `DATA_CONTRACT.md` and its drift guard must move with the code; the version bump + tolerant reader are the compat contract.
- **`decision_id` instability** — if the hash inputs include a volatile field the id churns and can't be referenced. Mitigation: pin the input set (decision 1) and test stability.

## Testing

Follow the project's unit-first convention. Add recorder-level unit tests in `tests/test_telemetry.py` covering: the new fields populated on a recorded `DecisionEvent`; `decision_id` stability (same inputs → same id) and collision semantics (identical content+ts collide by design); `run_id` sourced from the `_active_run_id` ContextVar (set-and-cleared, `""` when no run active); `plan_fingerprint`/`code_fingerprint` passthrough from caller args; and old-line tolerance (a v1→v2 read-compat test proving `read_decisions` still parses pre-bump lines). Keep the stdlib-only leaf import test green. The `DATA_CONTRACT.md` drift guard (`tests/test_data_contract.py`) must stay green after the `DecisionEvent` table + per-kind context notes are updated.

## Acceptance criteria

- A newly recorded `DecisionEvent` carries `decision_id`, `run_id`, and `plan_fingerprint`/`code_fingerprint` (the latter `""`/omitted when the caller has no plan context); `schema_version` is bumped and old v1 lines still parse.
- `decision_id` is a stable content hash (same inputs → same id) computed with stdlib only; `telemetry.py` imports nothing first-party (leaf test green).
- `run_id` is populated from a `telemetry`-owned `ContextVar` set by the run/command entrypoints to the same value the run-log stamps, is `""` when no run is active, and is cleared in a `finally` so it never leaks across runs.
- All 8 recorders forward the new keys they can supply; `plan-criteria-breakdown`'s fingerprints live in one home (promoted), not duplicated silently.
- `DATA_CONTRACT.md` documents the new base-event fields and the schema-version bump, with the drift guard green; the change ships no analysis/resolver surface.
- BACKLOG #72 is updated in the plan's final step: phase-1 schema marked shipped, phases 2–3 left as remaining scope, spike reference retained.

## Deferred

- **Phase 2 (backfill the good keys everywhere)** — populate the new join keys across all remaining decision sites; postponed to a later #72 slice.
- **Phase 3 (resolver + `plan-tool telemetry` surface)** — the read-only resolver/analysis-and-recommend consumer of these keys; a separate later plan. Phase 1 lands only the keys it will need.
