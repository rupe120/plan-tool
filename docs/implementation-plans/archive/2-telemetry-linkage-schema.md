> **Auto-archived**: this plan was swept on 2026-07-12 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Telemetry Linkage Schema
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Add decision_id, run_id, and fingerprint fields to DecisionEvent and record_decision;
    bump schema to 2
  files:
  - plan_tool/telemetry.py
  - plan_tool/data_contract.py
  - DATA_CONTRACT.md
  - tests/test_telemetry.py
  - tests/test_data_contract.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/telemetry-linkage-schema/01-decision-id-run-id-fingerprint-fields.md
  status: done
- id: 2
  title: Forward the new keys through the 8 recorder wrappers and dual-home plan-criteria's
    fingerprints onto the base event (kept in context)
  files:
  - plan_tool/telemetry.py
  - DATA_CONTRACT.md
  - tests/test_telemetry.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/telemetry-linkage-schema/02-forward-new-keys-through-recorder.md
  status: done
- id: 3
  title: Set the telemetry run_id ContextVar from the run-log run_id at the run entrypoints
    and clear it in a finally
  files:
  - plan_tool/run_log.py
  - plan_tool/cli/run_cmd.py
  - tests/test_run_log.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/telemetry-linkage-schema/03-set-telemetry-run-id-contextvar-run-log.md
  status: done
- id: 4
  title: 'Update BACKLOG #72 to mark the phase-1 schema shipped and leave phases 2-3
    as remaining scope'
  files:
  - BACKLOG.md
  complexity: low
  change_type: non-code
  depends_on:
  - 1
  - 2
  - 3
  detail: docs/implementation-plans/plan-details/telemetry-linkage-schema/04-update-backlog-72-mark-phase-schema.md
  status: done
---
# Telemetry Linkage Schema

## Overview

Phase 1 of BACKLOG #72 (decision/outcome telemetry): the schema-only slice. It enriches the base `DecisionEvent` in `plan_tool/telemetry.py` with the join keys a later resolver will need to tie a recorded heuristic *decision* to what actually *happened*, but ships **no new consumer** — the read-only `plan-tool telemetry` resolver/analysis surface is a separate later plan (phase 3). Concretely: add `decision_id` (a stdlib content hash computed inside `record_decision`), `run_id` (flowed via a `telemetry`-owned `ContextVar`), `plan_fingerprint` (a caller-supplied `str`) / `code_fingerprint` (a caller-supplied `dict[str, str]` path→hash map, always serialized — `{}` when absent), and `anchor` (a defaulted `str` join key, no phase-1 producer) to the base event; migrate the 8 existing recorders; bump `TELEMETRY_SCHEMA_VERSION` while keeping `read_decisions` tolerant of old v1 lines; and update the drift-guarded `DATA_CONTRACT.md`. The change is backward-compatible and keeps `telemetry.py` a stdlib-only leaf (no first-party imports). Plan-criteria's `plan_fingerprint` is **dual-homed** in phase 1 — written to the new base field *and* left in `context` — so the existing `split_criteria.py` drift consumer keeps reading it; `code_fingerprint` is **base-homed only** (nothing reads it from `context`, and dual-homing the big map would risk the line cap). Dropping the `plan_fingerprint` `context` copy is phase-2 work.

## Problem statement

Outcome-linkage is **impossible from today's telemetry schema**. The spike (`.tmp/72-telemetry-linkage.spike.md`, 347 real events) found that decisions and every outcome source share only `(plan_slug, ts)` — coarse, and empty for 42% of real events — and no post-hoc join logic can recover what the events never carried. Nothing today can point at a specific decision, and the run-log stays an island because decision events carry no `run_id`. The prerequisite is therefore a schema change, cleanly separable from the analysis surface that consumes it. Shipping the schema first lets real events start accumulating the join keys now, so that when the resolver lands (phase 3) there is data to validate it against — the spike's smoke test can't run today because the fingerprint- and outcome-carrying recorders have never fired.

## Architecture

Five resolved design decisions ground the build:

1. **`decision_id` is a content hash computed inside `record_decision`.** A stable `sha256` over `(schema_version, kind, decision, plan_slug, plan_fingerprint, step_id-if-any, ts)`, truncated (e.g. 16 hex), using stdlib `hashlib` so `telemetry.py` stays stdlib-only. Its sole job is to make a decision referenceable by a later outcome. Only a **scalar** `step_id` folds into the hash (from `record_create_step_outcome`); the **plural-`step_ids`** recorders (`record_code_reveals_split`) deliberately contribute nothing to the hash's `step_id` slot — a list does not map to the single optional string — so two same-`ts` fires of such a recorder on one plan collide by design. That is acceptable (the code-reveals-split detector fires at most once per reconcile audit), not an oversight. Two events with an identical hash tuple+ts collide by design; but because the tuple omits `context`, genuinely-distinct same-family decisions sharing a second-precision `ts` (differing only in `context`) also collide, so `decision_id` is **not** globally unique — a downstream resolver must not treat it as a unique key. This collision is **accepted for phase 1** (no line-ordinal/sequence tiebreaker is added — that would force `record_decision` to read the append-only log and break its stdlib-only, best-effort leaf shape). `decision_id` is therefore a stable handle to a *class* of content-identical decisions, not a per-row key: because `ts`/`plan_slug`/`plan_fingerprint` are already folded into the hash, two rows that collide share those too, so the only field that distinguishes them is `context` itself. The phase-3 resolver treats `decision_id` as non-unique and, when it must pick a specific row, matches additionally on `context` (or the line's position in the log) — for outcome-linkage the id-class is usually sufficient. This semantics is documented in `DATA_CONTRACT.md` so phase 3 doesn't guess.

2. **`run_id` flows via a `telemetry`-owned `ContextVar`, not a per-recorder arg.** Mirror `plan_tool/shell.py:_active_sink` / `set_active_sink`: `telemetry.py` owns `_active_run_id: ContextVar[str]` (default `""`) plus `set_active_run_id()` / a scope helper, and `record_decision` reads it. `contextvars` is stdlib, so the leaf constraint holds. **Phase 1 wires the two `run_cmd.py` entrypoints** (`cmd_run` and `_cmd_run_sweep`) — they set the ContextVar to the same `run_id` the run-log stamps, in a `finally`-cleared scope. This binding is **not inert in phase 1**: the recorders that fire *inside* a `run` on the main thread get a non-empty `run_id` — notably `record_prompt_budget(phase="run-step")` at `launcher.py:run_step` and the run invoker's prompt-budget check in `shell.py`. What stays `""` in phase 1: the authoring-time recorders whose entrypoints are deferred to phase 2 (the ~13 other `RunLogWriter.start` sites in create/detail/completeness — so `create-step-outcome`, `plan-criteria-breakdown`, `audit-coverage`, `convergence` still record `run_id=""`), the prompt-budget shell backstop when no run is active, **and the whole reconcile family** (see below). Note on `record_code_reveals_split` (the #117 detector, #72's flagship first consumer): it fires **only** inside `review.py:extract_recommendations` (`reconcile_lane and step_filter is None`), reached via `review_plan_full` from the **standalone** `reconcile-plan` / `review` commands and `bench.py` — **not** from `run --reconcile`. `run --reconcile` (`_cmd_run_reconcile`) runs `run_step(mode="run-reconcile")`, a code-editing claude subprocess that never enters the in-process review pipeline, so it fires no `record_code_reveals_split`. Therefore `_cmd_run_reconcile` is **deferred to phase 2** with the standalone `reconcile`/`reconcile-all`/`reconcile-plan` commands; the flagship detector gains its `run_id` when those review-lane entrypoints are wired in phase 2, not here. (Wiring `_cmd_run_reconcile` in phase 1 would stamp `run_id` only on its low-value `run-step` prompt-budget check — not worth widening scope, and the flagship-signal benefit is illusory.) Stamp `run_id` only when a run is active; leave `""` otherwise. (Note: a `record_decision` fired from a **worker thread** spawned inside a run reads the ContextVar default `""` — Python threads start with a fresh context, not the parent's — so off-main-thread decisions are unbound in phase 1; propagating into worker threads is phase-2 scope.)

3. **`plan_fingerprint` (+ optional `code_fingerprint`) added to the base event, caller-supplied and dual-homed.** The renumber-proof anchor (survives `split` id renumbering, unlike `step_id`). `plan_fingerprint` is a `str`; `code_fingerprint` is a `dict[str, str]` path→hash map (matching the shipped `record_plan_criteria_breakdown` signature), always serialized on the base event — `{}` when the caller has none, so the old "omitted from `context`" distinction does not exist on the base field. Both are caller-supplied — `telemetry.py` must not import `review_persistence`/`fingerprint`; callers pass the digest from `compute_plan_fingerprint` / `compute_code_fingerprint` (`""`/`{}` when a decision has no plan context). In phase 1 the sole real producer, `record_plan_criteria_breakdown`, dual-homes `plan_fingerprint` (base field **and** its `context` copy — a short digest, cheap) so the in-repo consumer `split_criteria.py:compute_criteria_drift` / `_last_different_fingerprint_event` (which reads `event.context["plan_fingerprint"]`) is not broken. `code_fingerprint` is **base-homed only** — nothing reads it from `context`, and it is the largest field, so dual-homing the big map would double it against `_MAX_LINE_BYTES` and could drop the whole event on a large-grounding plan (a correctness fix landed post-run; see Risks). Dropping the `plan_fingerprint` `context` copy and migrating that reader to the base field is deferred to phase 2.

4. **Freeze the join-key schema now: add `anchor`, and document `step_id` normalization.** Two halves, both operationalized in phase 1 (not deferred). (a) Add a defaulted `anchor: str = ""` base field to `DecisionEvent` (step 1), carrying the finding `anchor` slug where a decision is about a specific finding, so phase 3 can reuse `convergence_diagnosis._matches`' step→anchor→title matching *logic* (it currently resolves `Recommendation.anchor`; phase 3 applies the same tiers to `DecisionEvent.anchor` — same algorithm, different record type, not a literal drop-in). It has **no phase-1 producer** — the same freeze-the-schema pattern as `run_id` and the fingerprint-forwarding params, whose callers also land in phase 2 — and it stays **out of the `decision_id` hash** (a join key, not identity, like `run_id`/`code_fingerprint`). (b) Document the `step_id` type contract in `DATA_CONTRACT.md` (step 1): decisions store `step_id`/`step_ids` as `str`, sidecars/recs as `int` — a silent join-breaker — so the phase-3 resolver casts. Keeping the decision side `str` and documenting the canonical form pre-empts phase 3 guessing.

5. **Migrate all 8 recorders uniformly.** `record_decision` gains the enrichment; each wrapper (`record_granularity`, `record_code_reveals_split`, `record_create_granularity_assessment`, `record_create_step_outcome`, `record_audit_coverage`, `record_convergence`, `record_plan_criteria_breakdown`, `record_prompt_budget`) forwards the keys it can supply (fingerprint where the caller has a plan; `""`/`{}` otherwise). `plan-criteria-breakdown` already carries the fingerprints in `context` — in phase 1 it forwards both to the new base fields; `plan_fingerprint` is **dual-homed** (also kept in `context`, so `split_criteria.py`'s `context`-reading drift diff is not broken) while `code_fingerprint` is **base-homed only** (its `context` copy dropped to avoid doubling the big map against `_MAX_LINE_BYTES` — see Risks). Collapsing `plan_fingerprint` to a single home (drop the `context` copy, migrate the reader) is deferred to phase 2.

## References

- [contextvars — Context Variables — Python 3.13 documentation](https://docs.python.org/3/library/contextvars.html) — Official reference for ContextVar / set() / reset() and Token semantics, the exact primitive the plan uses to flow run_id through a telemetry-owned per-thread variable with finally-clear.
- [hashlib — Secure hashes and message digests — Python 3.13 documentation](https://docs.python.org/3/library/hashlib.html) — Official reference for sha256 and hexdigest(), needed to compute the stable stdlib-only decision_id content hash while keeping telemetry.py a leaf.
- [JSON Lines](https://jsonlines.org/) — The primary spec for the newline-delimited JSON (one object per line) format that decisions.jsonl uses, relevant to keeping append-per-line records and old-line tolerant reads well-formed.
- [json — JSON encoder and decoder — Python 3.13 documentation](https://docs.python.org/3/library/json.html) — Official reference for json.dumps/loads used to serialize each DecisionEvent line and to parse pre-bump v1 lines tolerantly in read_decisions.
- [dataclasses — Data Classes — Python 3.13 documentation](https://docs.python.org/3/library/dataclasses.html) — Official reference for dataclass/field(default=...)/asdict, relevant to adding decision_id/run_id/plan_fingerprint/code_fingerprint fields to the base DecisionEvent with backward-compatible defaults.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- **The resolver / `plan-tool telemetry` analysis-and-recommend surface** — phase 3; no consumer of the new keys ships here.
- **Deriving outcome verdicts** (`acted-on` / `no-op` / `reverted`) — phase 3.
- **Backfilling historical events** — the 347 existing events stay v1; only new events carry the keys, with no migration of old data.
- **Adding new decision *sites*** (e.g. escalate-to-split, `--refresh` drift-gate) — a separate #72 slice; phase 1 only enriches the 8 recorders that exist.
- **Changing `telemetry.py`'s leaf status** — it stays stdlib-only; importing a fingerprint producer is the wrong design (callers pass strings).

## Risks

- **Leaf-purity regression** — the seductive wrong move is importing `review_persistence`/`fingerprint` into `telemetry.py`. Mitigation: fingerprints are caller-supplied primitives (`plan_fingerprint` a `str`, `code_fingerprint` a `dict[str, str]`); keep the stdlib-only import test green.
- **ContextVar leakage across threads/runs** — a crashed or timed-out run could leave a stale `run_id` wired for the next (the `bench` daemon-thread hazard the `_active_sink` docstring names). Mitigation: mirror `_active_sink`'s per-thread `ContextVar` + `finally`-clear. **Accepted phase-1 limit:** per-thread isolation is a two-sided coin — it prevents stale leakage but also means a decision recorded on a *worker* thread spawned inside a run reads the default `""` (the parent's binding does not propagate to a fresh thread context). Phase-1 producers record on the main thread, so this is a coverage gap for future off-thread recorders, not a phase-1 correctness bug; propagation is phase-2 scope.
- **Dual-home line-cap (fixed post-run)** — `record_decision` drops the *entire* event when the serialized line exceeds `_MAX_LINE_BYTES` (64 KiB). The original design dual-homed `code_fingerprint` (base + `context`), doubling the largest field — a ~45 KiB grounding baseline doubled to ~90 KiB and was silently dropped. The "safe in practice" assessment here underweighted large-repo grounding baselines; a post-run code review caught it. **Resolution:** `code_fingerprint` is **base-homed only** (its `context` copy dropped — nothing read it there), so the big map is serialized once; `plan_fingerprint` stays dual-homed (short digest). The cap and per-field truncation are untouched (out of scope).
- **Silent schema drift** — `DATA_CONTRACT.md` and its drift guard must move with the code; the version bump + tolerant reader are the compat contract.
- **`decision_id` instability** — if the hash inputs include a volatile field the id churns and can't be referenced. Mitigation: pin the input set (decision 1) and test stability.

## Testing

Follow the project's unit-first convention. Add recorder-level unit tests in `tests/test_telemetry.py` covering: the new fields populated on a recorded `DecisionEvent`; `decision_id` stability (same inputs → same id) and collision semantics (identical content+ts collide by design); `run_id` sourced from the `_active_run_id` ContextVar (set-and-cleared, `""` when no run active); `plan_fingerprint`/`code_fingerprint` passthrough from caller args; and old-line tolerance (a v1→v2 read-compat test proving `read_decisions` still parses pre-bump lines). Keep the stdlib-only leaf import test green. The `DATA_CONTRACT.md` drift guard (`tests/test_data_contract.py`) must stay green after the `DecisionEvent` table + per-kind context notes are updated.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — unit tests added with the implementation; green before completion.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- A newly recorded `DecisionEvent` carries `decision_id`, `run_id`, `plan_fingerprint` (a `str`, `""` when the caller has no plan context), `code_fingerprint` (a `dict[str, str]`, always serialized — `{}` when absent), and `anchor` (a `str`, `""` with no phase-1 producer); `schema_version` is bumped to `2` and old v1 lines still parse.
- `decision_id` is a stable content hash (same inputs → same id) computed with stdlib only; `telemetry.py` imports nothing first-party (leaf test green). Its deliberate non-uniqueness (a stable class-handle, not a per-row key; the phase-3 resolver falls back to `context`/log-position) is documented in `DATA_CONTRACT.md`.
- `run_id` is populated from a `telemetry`-owned `ContextVar` set by the **two `run_cmd.py` entrypoints** (`cmd_run`, `_cmd_run_sweep`) to the same value the run-log stamps, is `""` when no run is active (including the authoring-time recorders, the `run --reconcile` lane, and the standalone `reconcile*` commands — all deferred to phase 2), and is cleared in a `finally` so it never leaks across runs. Its concrete phase-1 producer is `record_prompt_budget(phase="run-step")` at `launcher.py:run_step`.
- All 8 recorders forward the new keys they can supply; `plan-criteria-breakdown`'s `plan_fingerprint` is **dual-homed** in phase 1 (base field *and* `context`) so `split_criteria.py`'s drift consumer keeps working, while `code_fingerprint` is **base-homed only** (avoids doubling the big map against the line cap). `tests/test_split_criteria.py` stays green untouched.
- `anchor` is a defaulted base field frozen into the schema now (phase-2 producers fill it); `DATA_CONTRACT.md` documents the `str` (decision-side) / `int` (sidecar/rec-side) `step_id` normalization contract.
- `DATA_CONTRACT.md` documents the new base-event fields and the schema-version bump, with the drift guard green; the change ships no analysis/resolver surface.
- BACKLOG #72 is updated in the plan's final step: phase-1 schema marked shipped, phases 2–3 left as remaining scope, spike reference retained.

## Deferred

- **Phase 2 (backfill the good keys everywhere)** — populate the new join keys across all remaining decision sites; wire the `run_id` ContextVar at the ~13 other `RunLogWriter.start` entrypoints (create/detail/completeness/reconcile); backfill `anchor` at the finding-scoped producers; postponed to a later #72 slice.
- **Single-home `plan_fingerprint`** — drop its dual-homed `context` copy from `record_plan_criteria_breakdown`, remove it from the `("DecisionEvent", "context")` open-bag registration, and migrate `split_criteria.py`'s drift diff (`compute_criteria_drift` / `_last_different_fingerprint_event`) + `tests/test_split_criteria.py` to read the base `plan_fingerprint` field; a reader that spans the boundary must read from **both** homes. (`code_fingerprint` is already base-homed as of the post-run fix.) Deferred to phase 2 to keep phase 1 additive and non-breaking.
- **Phase 3 (resolver + `plan-tool telemetry` surface)** — the read-only resolver/analysis-and-recommend consumer of these keys; a separate later plan. Phase 1 lands only the keys it will need.
