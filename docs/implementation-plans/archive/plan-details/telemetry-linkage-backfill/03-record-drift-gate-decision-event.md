> **Auto-archived**: this plan was swept on 2026-07-12 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Record a drift-gate decision event in refresh_plan (no-baseline / no-drift / drifted)

## Summary

Add the third of Part B's three new decision families: a **drift-gate** telemetry event emitted by `plan_tool/refresh.py:refresh_plan`. Add one new stdlib-only recorder wrapper (`record_drift_gate`) plus its `kind`/`decision`/verdict constants to `plan_tool/telemetry.py`, then call it once per refresh at each of the function's three verdicts — `no-drift` (the only fast no-op early return, zero counts), `drifted` (a scoped reconcile ran), and `no-baseline` (absent/unreadable baseline — runs a **whole-surface reconcile** through the *same* tail as `drifted`, so it carries real `findings`/`drifted_files`, not zero; `needs_grounding` is the discriminator, not a separate no-op return) — carrying the verdict, the drifted-file count, the findings count, and fingerprints: `code_fingerprint` (the already-computed `current_code_fp`) on every verdict, and `plan_fingerprint` on `no-baseline`/`drifted` only — **skipped on the hot `no-drift` path** to keep that no-op free of the extra plan-file read (`refresh_plan` already holds `current_code_fp` and imports `compute_plan_fingerprint`). Document the new family in `DATA_CONTRACT.md` and extend the drift guard. Everything is additive and best-effort: the recorder is a stdlib leaf, the caller-side fingerprint compute is guarded, and `refresh_plan`'s returned `RefreshOutcome`, control flow, and no-op purity stay exactly as they are — the only new write is one line to the gitignored `.plan-tool/telemetry/decisions.jsonl`.

## Table of Contents

- [Why](#why) — refresh emits no decision event today
- [Input](#input) — the recorder API and refresh_plan state this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — one leaf + one caller + doc + three test files
- [Implementation](#implementation) — the new recorder, the three verdict call sites, and the best-effort guard
- [Tests](#tests) — recorder roundtrip, three verdict sites, best-effort, and doc drift
- [Acceptance criteria](#acceptance-criteria) — observable checks a reviewer runs
- [References](#references) — the telemetry/format docs relevant here
- [Deferred](#deferred) — behavior owned by other steps / phase 3

## Why

`plan_tool/refresh.py:refresh_plan` is the drift-gate that decides, with zero Claude, whether a plan is still grounded against the code — the single most-run heuristic in the reconcile/`--refresh` lane. It answers one of three ways (`no-baseline` / `no-drift` / `drifted`) and today records **nothing**: no `DecisionEvent` fires, so a phase-3 aggregation has no way to see how often the gate clears clean vs reconciles, how many files drift, or how many findings a drift produces. BACKLOG #72's spike named this gate as one of three high-leverage decisions emitting no event at all. This step makes the gate observable — one telemetry line per refresh — without changing what the gate decides or returns.

## Input

This step populates the phase-1 `DecisionEvent` contract and reads state `refresh_plan` already computes. It changes neither.

- **`record_decision` and its wrappers** in `plan_tool/telemetry.py` — every per-kind wrapper (e.g. `record_convergence`, `record_audit_coverage`) is a thin call over `record_decision(repo_root, *, kind, decision, plan_slug, context=..., plan_fingerprint=..., code_fingerprint=...)` taking primitives only. `record_decision` already mints `decision_id`, reads `run_id` from the `_active_run_id` ContextVar, and swallows every error. The new recorder mirrors this shape exactly.
- **`refresh_plan`'s in-scope state** — the function already computes `current_code_fp = compute_code_fingerprint(plan, plan_path, repo_root)` before the grounding read (available on all three branches), resolves `plan_slug` via `slug_from_filename`, and imports `plan_tool.review_persistence.compute_plan_fingerprint` at module top (used today only in the `findings == 0` restamp branch). Both fingerprints are reachable at every verdict.
- **The three verdicts** are already distinct code points: `grounding is None` sets `needs_grounding = True`; `code_match` returns `RefreshOutcome(plan_slug=plan_slug)` early; the shared reconcile tail returns `drifted=True` with `findings` and `drifted_files`. The `findings` count exists only after the reconcile tail runs — the `no-drift` verdict is always `findings=0`, `drifted_files=0`. **Note on `no-baseline`:** `read_grounding` returns `None` both on a genuine first stamp *and* on a corrupt/unreadable sidecar (the code comment reads "pre-feature or corrupt sidecar"), so the `no-baseline` verdict telemeters both cases identically. The literal stays accurate (no readable baseline existed either way) — this is a known coarseness, not a mislabel; a phase-3 resolver reading `no-baseline` should not assume it means exclusively "first ever refresh."
- **`run_id` needs no work here** — reconcile/`--refresh` is an authoring command, not a `run`, so `_active_run_id` is unset and `run_id=""` is the correct recorded value (Out of scope in the plan: "Binding `run_id` at non-run commands").

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/telemetry.py` — add the `record_drift_gate` wrapper plus its module constants (`DRIFT_GATE_KIND`, `DRIFT_GATE_DECISION`, and the three verdict literals), mirroring the `PROMPT_BUDGET_KIND` / `CREATE_ACTION_*` constant style.
  - `plan_tool/refresh.py` — import the new recorder (+ verdict constants), and call it at the three verdict points inside `refresh_plan`, each wrapped best-effort.
  - `DATA_CONTRACT.md` — add `"drift-gate"` to the `kind` value list in the `DecisionEvent` field table, and add a new `#### Reconcile drift-gate` subsection documenting the `kind`/`decision` literals and the context-key table.
  - `tests/test_telemetry.py` — unit tests for `record_drift_gate` (roundtrip + fingerprint carry).
  - `tests/test_data_contract.py` — drift-guard tests that the new family and its context keys are documented.
  - `tests/test_refresh.py` — tests that each of the three verdicts records the right event, plus the best-effort invariant.

## Implementation

**Add one stdlib-only recorder in `plan_tool/telemetry.py`.** Follow the exact shape of `record_convergence` / `record_audit_coverage`:

- **New constants**, placed beside `PROMPT_BUDGET_KIND` / `PROMPT_BUDGET_DECISION`:
  - `DRIFT_GATE_KIND = "drift-gate"` and `DRIFT_GATE_DECISION = "gated"` — the `kind`/`decision` literals downstream aggregation keys on.
  - Three verdict literals — one way: `DRIFT_VERDICT_NO_BASELINE = "no-baseline"`, `DRIFT_VERDICT_NO_DRIFT = "no-drift"`, `DRIFT_VERDICT_DRIFTED = "drifted"` (mirrors the `CREATE_ACTION_*` string-constant convention so the caller passes a named constant, not a bare string).
- **New wrapper** `record_drift_gate(repo_root, *, plan_slug, verdict, drifted_files, findings, plan_fingerprint="", code_fingerprint=None)` that calls `record_decision` with `kind=DRIFT_GATE_KIND`, `decision=DRIFT_GATE_DECISION`, and `context={"verdict": verdict, "drifted_files": drifted_files, "findings": findings}`. Take primitives only (verdict string, two int counts, already-computed fingerprint string/dict) — **never** import `review_persistence` or `fingerprint` into `telemetry.py`; the stdlib-only leaf test (`grep -E '^(from|import) plan_tool' plan_tool/telemetry.py` stays empty) must stay green.

Do **not** bump `TELEMETRY_SCHEMA_VERSION` — the reader already tolerates a new `kind`, and this adds no base-event field (plan Out of scope).

**Wire the three verdict call sites in `plan_tool/refresh.py:refresh_plan`.** The decision must fire once per refresh at whichever verdict is reached:

- **`no-drift`** — before the early `return RefreshOutcome(plan_slug=plan_slug)` in the `code_match` branch. Record `verdict="no-drift"`, `drifted_files=0`, `findings=0`.
- **`no-baseline`** and **`drifted`** — at the shared reconcile tail's final `return`, where `findings` and `drifted_files` are known. Pick the verdict off the existing `needs_grounding` flag (`True` → `no-baseline`, else `drifted`); pass `drifted_files=len(drifted_files)` and `findings=findings`.
- **Fingerprints (cost-scoped).** Pass `code_fingerprint=current_code_fp` at **every** verdict — it is already computed (that is how the gate detected drift), so it is free, and it fully anchors a code-vs-plan-drift decision on its own. Compute `plan_fingerprint=compute_plan_fingerprint(plan_path)` **only on the `no-baseline` / `drifted` verdicts** (both already ran a reconcile, so one extra small plan-file read is negligible), and **skip it on the hot `no-drift` path** — `no-drift` is "the single most-run heuristic," billed as a fast no-op, and `compute_plan_fingerprint` reads the plan markdown *plus its detail bundle*; adding that I/O to the byte-identical no-op path contradicts the same cost discipline that refuses the `code_fingerprint` map on the every-round granularity/audit sites. So `no-drift` events carry `code_fingerprint` (in hand) and `plan_fingerprint=""`. The drift-gate is a plan-wide decision, so leave `step_id`/`anchor` unset.

**Recommended shape — a single guarded local emitter.** One way to keep it DRY and best-effort: define a small closure near the top of `refresh_plan`, e.g. `_emit_drift_gate(verdict, drifted_count, findings_count)`, that computes `plan_fingerprint` best-effort (its own `try/except`, default `""`) **only when `verdict != "no-drift"`** (skip the plan-file read on the hot path), and calls `record_drift_gate(repo_root, plan_slug=plan_slug, verdict=verdict, drifted_files=drifted_count, findings=findings_count, plan_fingerprint=..., code_fingerprint=current_code_fp)`, with the whole body wrapped so any error returns without touching the refresh. Call it at the two return points (the `no-drift` call gets `plan_fingerprint=""`). The developer may instead inline two guarded blocks — the constraint is the guard and the placement, not the closure.

**Constraints that are not free to vary:**

- **Best-effort at the caller, not just the leaf.** `record_decision` swallows its own errors, but `compute_plan_fingerprint(plan_path)` runs in *refresh's* code before the call — wrap the fingerprint-compute + record in a local `try/except` that returns/continues on failure. A raising fingerprint compute must not change `refresh_plan`'s returned `RefreshOutcome` or raise (mirrors create.py's `_record_*` helpers and the "best-effort guarantee covers only code inside the sink" lesson).
- **No behavior change to the gate.** The `RefreshOutcome` fields, the early-return control flow, the `findings == 0` restamp rule, and the "no Claude on no-drift" guarantee must all stay identical. The recorder spends no Claude and spawns no invoker, so `test_no_drift_spawns_no_invoker` (which patches `launcher.run_step` to raise) stays green.
- **No-op purity holds for tracked files.** `refresh_plan`'s docstring/comment says the no-drift path leaves the working tree unchanged. The recorder writes only to the **gitignored** `.plan-tool/telemetry/decisions.jsonl` — not the grounding sidecar and no tracked file — so `test_no_drift_does_not_rewrite_sidecar` (compares sidecar bytes) stays green. If you touch the no-drift comment, keep it honest: the fast path still rewrites no *tracked* file and spawns no invoker.
- **Import placement.** `telemetry.py` is a stdlib-only leaf, so importing `record_drift_gate` at `refresh.py`'s module top is cycle-free and cheap — unlike the deliberately function-local `run_auto_reconcile_on_drift` import (which exists to keep the no-drift path from pulling in `launcher`/`review`). A module-top telemetry import does not weaken that guarantee.

**Foundational logic and shared sites.** The core rule this step adds is "emit one drift-gate decision per refresh verdict." `refresh_plan` is the sole drift-gate; its one caller, `plan_tool/cli/review_cmd.py:cmd_review` (the `reconcile-plan --refresh` shim at the `_render_refresh(refresh_plan(...))` call), needs **no** change — recording lives inside `refresh_plan` so any current or future caller of `refresh_plan` gets the event for free. No parallel drift-gate implementation exists elsewhere to keep in sync.

## Tests

Unit-first, mirroring `plan_tool/X.py → tests/test_X.py`. Reuse `test_refresh.py`'s existing helpers (`_seed_plan`, `_ground`, `_spy_reconcile`) and `test_telemetry.py`'s `read_decisions` + injectable `clock`.

`tests/test_telemetry.py`:
- `test_record_drift_gate_roundtrips` — `record_drift_gate` with a verdict + counts + both fingerprints records one event whose `kind == DRIFT_GATE_KIND`, `decision == DRIFT_GATE_DECISION`, `context` carries `verdict`/`drifted_files`/`findings`, and `plan_fingerprint`/`code_fingerprint` land on the base event.
- `test_drift_gate_leaves_step_and_anchor_unset` — a recorded drift-gate event has `anchor == ""` and its `decision_id` is a stable 16-hex string (no `step_id` folded in).

`tests/test_refresh.py`:
- `test_no_drift_records_drift_gate_decision` — no-drift refresh records one event with `verdict="no-drift"`, `drifted_files=0`, `findings=0`, a non-empty `code_fingerprint`, and `plan_fingerprint == ""` (skipped on the hot path).
- `test_no_baseline_records_drift_gate_decision` — the no-baseline path (no sidecar) records `verdict="no-baseline"`.
- `test_drift_records_drift_gate_decision` — a drift with the reconcile spy returning N findings records `verdict="drifted"`, `drifted_files == len(drifted_files)`, `findings == N`.
- `test_drift_gate_record_is_best_effort` — monkeypatch `record_drift_gate` (or `compute_plan_fingerprint`) to raise; `refresh_plan` still returns the same `RefreshOutcome` and does not raise.
- Existing `test_no_drift_spawns_no_invoker` and `test_no_drift_does_not_rewrite_sidecar` stay green unmodified — pin them as regression oracles that the recorder spawns no invoker and rewrites no tracked sidecar.

`tests/test_data_contract.py`:
- `test_drift_gate_decision_documented` — `"drift-gate"` appears in `DATA_CONTRACT.md`.
- `test_drift_gate_context_keys_documented` — each of `verdict`, `drifted_files`, `findings` is documented (mirrors `test_prompt_budget_context_keys_documented`).

### Test-creation order (feature step)

This is a **feature** step. Add every test above *with* the implementation: the `record_drift_gate` roundtrip tests as the recorder lands, the three verdict-site tests and the best-effort test as the `refresh.py` wiring lands, and the two doc-drift tests as `DATA_CONTRACT.md` is edited. Green-before-done gate: all new tests plus the unchanged no-op regression pins in `tests/test_refresh.py` must pass before the step is finished, and the `telemetry.py` stdlib-only leaf test must stay green.

## Acceptance criteria

- `plan_tool/telemetry.py` exports `record_drift_gate` plus `DRIFT_GATE_KIND` (`"drift-gate"`), `DRIFT_GATE_DECISION` (`"gated"`), and three verdict constants; `grep -E '^(from|import) plan_tool' plan_tool/telemetry.py` is still empty.
- A `no-drift` refresh records exactly one `drift-gate` event with `context.verdict == "no-drift"`, `drifted_files == 0`, `findings == 0`, a non-empty `code_fingerprint`, and `plan_fingerprint == ""`.
- A `no-baseline` refresh records `verdict == "no-baseline"`; a drifted refresh records `verdict == "drifted"` with `drifted_files` and `findings` matching the reconcile outcome.
- A forced failure in the fingerprint compute or the recorder leaves `refresh_plan`'s returned `RefreshOutcome` unchanged and raises nothing.
- `test_no_drift_spawns_no_invoker` and `test_no_drift_does_not_rewrite_sidecar` still pass — no invoker spawned, no tracked sidecar rewritten.
- `DATA_CONTRACT.md` lists `"drift-gate"` among the `kind` values and has a `#### Reconcile drift-gate` subsection with the `verdict`/`drifted_files`/`findings` context keys; `tests/test_data_contract.py` is green.
- No `TELEMETRY_SCHEMA_VERSION` bump; `run_id` on the recorded event is `""`.

## References

- [JSON Lines](https://jsonlines.org/) — the one-object-per-line append format `decisions.jsonl` uses; the new event is one more line.
- [contextvars — Context Variables (Python 3.13)](https://docs.python.org/3/library/contextvars.html) — get/set semantics for `_active_run_id`, explaining why `run_id` stays `""` at this non-run authoring command.
- [dataclasses — Data Classes (Python 3.13)](https://docs.python.org/3/library/dataclasses.html) — the defaulted-field behavior on `DecisionEvent` that lets the new event carry `plan_fingerprint`/`code_fingerprint` with no schema bump.
- [How to mark test functions with attributes — pytest](https://docs.pytest.org/en/stable/how-to/mark.html) — the unit-first marker convention the new tests follow.

## Deferred

- **Any consumer of the drift-gate events** — no resolver or `plan-tool telemetry` read surface ships here; nothing reads the recorded verdicts (phase 3, plan Out of scope).
- **A per-step or per-file drift-gate breakdown** — this step records plan-wide counts only (`drifted_files`, `findings`); a per-drifted-file event is not in scope.
- **The other two Part-B recorders** — the `apply_finding` verdict recorder (step 4) and the escalate-to-split outcome recorder (step 5) own their own `kind` families and call sites; this step adds only `drift-gate`.
- **`code_fingerprint` volume tuning** — the drift-gate carries the full map by design (the decision is about code state); the per-line-volume tradeoff that makes step 4's apply site `plan_fingerprint`-only does not apply here.
