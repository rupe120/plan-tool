> **Replaced**: this file has been superseded by `docs/implementation-plans/2-telemetry-linkage-schema.md`.
> Preserved here for history; do not edit.

# Plan seed: decision→outcome linkage schema (BACKLOG #72, phase 1)

The **schema** slice of #72 (decision/outcome telemetry). It enriches the
`DecisionEvent` so a recorded heuristic *decision* can later be tied to what
*happened* — but ships **no new consumer**: the read-only `plan-tool telemetry`
resolver/analysis surface is a **separate later plan** (phase 3). This plan lands
the join keys the resolver will need, and nothing more.

> **Source.** Distilled from **BACKLOG #72** ("Decision/outcome telemetry →
> understand heuristics across scenarios over time, recommend tuning"), phase 2
> (outcome-linkage), via the schema spike at
> **`.tmp/72-telemetry-linkage.spike.md`**. The resulting plan **must update
> BACKLOG #72** when it ships (see the docs/status step in Scope + the final AC):
> mark the phase-1 schema done and leave phases 2–3 (backfill, resolver) as the
> remaining scope. This backlog reconciliation is a plan requirement, not an
> operator afterthought.

## Why a separate, schema-only plan

The spike's empirical finding (347 real telemetry events): outcome-linkage is
**impossible from today's schema**, and no post-hoc join logic recovers what the
events don't carry. Decisions and every outcome source share only
`(plan_slug, ts)` — coarse, and empty for 42% of real events. So the prerequisite
is a schema change, cleanly separable from the analysis surface that consumes it.
Shipping the schema first lets real events start accumulating the join keys **now**,
so that when the resolver lands (phase 3) there is data to validate it against — the
spike's smoke test can't run today because the fingerprint-carrying and
outcome-carrying recorders have never fired.

## What phase 1 delivers

Enrich the base `DecisionEvent` (`telemetry.py`) with three linkage keys, wire the
one that needs a source (`run_id`), migrate the 8 existing recorders, and document
+ drift-guard the new shape. **Backward-compatible**: bump
`TELEMETRY_SCHEMA_VERSION`, keep `read_decisions` tolerant of old lines.

## Resolved design decisions (ground the build on these — from the spike)

1. **`decision_id` is a content hash computed *inside* `record_decision`.** A stable
   `sha256` over `(schema_version, kind, decision, plan_slug, plan_fingerprint,
   step_id-if-any, ts)`, truncated (e.g. 16 hex). Computed with stdlib `hashlib` so
   **`telemetry.py` stays a stdlib-only leaf** — no first-party import. Its sole job
   is to make a decision *referenceable* by a later outcome; nothing today can point
   at a specific decision. Two events with identical content+ts collide by design
   (they are the same decision) — acceptable; `ts` is second-precision so genuine
   distinct decisions differ on some field.

2. **`run_id` flows via a `telemetry`-owned `ContextVar`, not a per-recorder arg.**
   Mirror `shell._active_sink`: `telemetry.py` owns `_active_run_id: ContextVar[str]`
   (default `""`) + `set_active_run_id()` / a scope helper; `record_decision` reads
   it. The **run/command entrypoints that already start a `RunLogWriter`** set it to
   the same `run_id` the run-log stamps (`run_log.new_run_id`), in a `finally`-cleared
   scope. `contextvars` is stdlib, so the leaf constraint holds and the run-log stops
   being an island — decision→run→`IterationEnd.outcome`/`rc` becomes a free join. See
   the spike's open decision: **stamp `run_id` only when a run is active, leave `""`
   otherwise** (the prompt-budget shell backstop often has no run — same tolerance as
   `plan_slug`).

3. **`plan_fingerprint` (+ optional `code_fingerprint`) promoted to the base event,
   caller-supplied.** The renumber-proof anchor (survives `split` id renumbering,
   unlike `step_id`). It must be a **string arg the caller passes** (as
   `record_plan_criteria_breakdown` already does) — `telemetry.py` must **not** import
   `review_persistence`/`fingerprint`. Callers already hold the plan; they pass the
   digest from `compute_plan_fingerprint` / `compute_code_fingerprint`. Optional/`""`
   when a decision has no plan context (prompt-budget backstop).

4. **Normalize `step_id` type across the seam.** Decisions store step ids as **str**,
   sidecars/recs as **int** — the spike flagged this as a silent join-breaker. Pick
   one normalization (recommend: keep decision-side `step_id`/`step_ids` as `str`, and
   have the *future resolver* cast — but document the canonical form here so phase 3
   doesn't guess). Carry the finding **`anchor`** slug too where a decision is about a
   specific finding, so `convergence_diagnosis._matches`' step→anchor→title tiers
   apply unchanged in phase 3.

5. **Migrate all 8 recorders uniformly.** `record_decision` gains the enrichment;
   each wrapper (`record_granularity`, `record_code_reveals_split`,
   `record_create_granularity_assessment`, `record_create_step_outcome`,
   `record_audit_coverage`, `record_convergence`, `record_plan_criteria_breakdown`,
   `record_prompt_budget`) forwards the new keys it can supply (fingerprint where the
   caller has a plan; `""`/omitted otherwise). `plan-criteria-breakdown` already
   carries the fingerprints in `context` — **promote** them to the base event and stop
   duplicating them in `context` (or keep one, documented) so there's a single home.

## Seams to reuse / extend (verify at HEAD during detail)

- `plan_tool/telemetry.py` — `DecisionEvent`, `record_decision`, the 8 wrappers,
  `read_decisions`, `TELEMETRY_SCHEMA_VERSION`. The whole change lands here + the
  entrypoints that set the ContextVar.
- `plan_tool/shell.py:_active_sink` / `set_active_sink` — the **ContextVar pattern to
  mirror** for `_active_run_id` (per-thread, finally-cleared).
- `plan_tool/run_log.py` — `new_run_id`, `RunLogWriter.start`; the run/command
  entrypoints that open a writer are exactly where `set_active_run_id` is set (same
  value, same scope).
- `plan_tool/review_persistence.py:compute_plan_fingerprint` and
  `plan_tool/fingerprint.py:compute_code_fingerprint` — the **caller-side** digest
  producers (telemetry never imports them; callers pass the string).
- `plan_tool/convergence_diagnosis.py` — **not touched in phase 1**, but its
  `series_key`/`_matches`/fingerprint-stability logic is the resolver phase-3 reuses;
  phase-1's job is to make the decision events carry the keys those tiers need.
- `DATA_CONTRACT.md` + `tests/test_data_contract.py` (drift guard) — the schema doc
  is the contract; update the `DecisionEvent` table + the per-kind context notes.

## Scope of work (indicative — let `create` decompose)

1. **Extend `DecisionEvent` + `record_decision`**: add `decision_id` (computed),
   `run_id` (from ContextVar), `plan_fingerprint`/`code_fingerprint` (args); bump the
   schema version; keep `read_decisions` tolerant of v1 lines.
2. **The `_active_run_id` ContextVar** in `telemetry.py` + `set_active_run_id` scope
   helper, and wire it at the run/command entrypoints that already start a
   `RunLogWriter`.
3. **Migrate the 8 recorders** to forward the new keys (fingerprint where available;
   `step_id`/`anchor` normalization per decision 4).
4. **DATA_CONTRACT.md** update (new top-level fields + the promotion note) with the
   drift guard kept green; a schema-version-bump migration note.
5. **Tests**: recorder-level (new fields populated, `decision_id` stable + collision
   semantics, `run_id` from ContextVar, fingerprint passthrough, old-line tolerance),
   plus a v1→v2 read-compat test.
6. **Docs/status step**: update **BACKLOG #72** — mark phase-1 schema shipped, leave
   phases 2 (backfill the good keys everywhere) and 3 (resolver + `plan-tool
   telemetry` surface) as remaining; keep the spike reference.

## Non-goals / out of scope (these are later #72 plans)

- **The resolver / `plan-tool telemetry` analysis-and-recommend surface** — phase 3;
  no consumer of the new keys ships here.
- **Deriving outcome verdicts** (`acted-on` / `no-op` / `reverted`) — phase 3.
- **Backfilling historical events** — the 347 existing events stay v1; only new
  events carry the keys. No migration of old data.
- **Adding new decision *sites*** (e.g. escalate-to-split, `--refresh` drift-gate) —
  a separate #72 slice; phase 1 only enriches the 8 that exist.
- **Changing `telemetry.py`'s leaf status** — it stays stdlib-only; any temptation to
  import a fingerprint producer is the wrong design (callers pass strings).

## Risks

- **Leaf-purity regression** — the seductive wrong move is importing
  `review_persistence`/`fingerprint` into `telemetry.py`. Guard: fingerprints are
  caller-supplied string args; keep the stdlib-only import test green.
- **ContextVar leakage across threads/runs** — mirror `_active_sink`'s per-thread
  `ContextVar` + `finally`-clear so a crashed/timed-out run can't leave a stale
  `run_id` wired for the next (the `bench` daemon-thread hazard the sink docstring
  names).
- **Silent schema drift** — DATA_CONTRACT + drift guard must move with the code;
  the version bump + tolerant reader are the compat contract.
- **`decision_id` instability** — if the hash inputs include a volatile field the id
  churns and can't be referenced; pin the input set (decision 1) and test stability.

## Acceptance criteria (plan-level)

- A newly recorded `DecisionEvent` carries `decision_id`, `run_id`, and
  `plan_fingerprint`/`code_fingerprint` (the latter `""`/omitted when the caller has
  no plan context); `schema_version` is bumped and old v1 lines still parse.
- `decision_id` is a **stable content hash** (same inputs → same id) computed with
  stdlib only; `telemetry.py` imports nothing first-party (leaf test green).
- `run_id` is populated from a `telemetry`-owned `ContextVar` set by the run/command
  entrypoints to the **same** value the run-log stamps, and is `""` when no run is
  active; it is cleared in a `finally` so it never leaks across runs.
- All 8 recorders forward the new keys they can supply; `plan-criteria-breakdown`'s
  fingerprints live in **one** home (promoted), not duplicated silently.
- `DATA_CONTRACT.md` documents the new base-event fields and the schema-version bump,
  with the drift guard green; the change ships **no** analysis/resolver surface.
- **BACKLOG #72 is updated** in the plan's final step: phase-1 schema marked shipped,
  phases 2–3 left as remaining scope, spike reference retained.
