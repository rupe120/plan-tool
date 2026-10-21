> **Auto-archived**: this plan was swept on 2026-07-12 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Record an escalate-to-split outcome decision event in `escalate_to_split`

## Summary

Add a new decision-telemetry family, `escalate-split`, emitted once each time `plan_tool/launcher.py:escalate_to_split` finishes deciding how it handled a mixed refactor+feature step. Add one stdlib-only recorder wrapper (`record_escalate_split`) plus its `kind`/`decision` constants to `plan_tool/telemetry.py`, then call it once per `escalate_to_split` return, carrying the frozen `EscalateResult.outcome` (one of `applied` / `recommended` / `unsafe` / `proposal-unusable` / `step-missing`), whether the caller allowed the mutation (`allow_split`), the target step id, any `blocking` ids, and `plan_fingerprint` (only — `code_fingerprint` is not carried; escalate is a structure/safety decision, body ground rule 3). Document the new family in `DATA_CONTRACT.md` and add its per-kind context-key drift test. Everything is additive and best-effort: the recorder is a stdlib leaf, the caller-side fingerprint compute is wrapped so it can't raise, and `escalate_to_split`'s return values, control flow, and every one of its five outcomes stay exactly as they are — the only new write is one line to the gitignored `.plan-tool/telemetry/decisions.jsonl`.

## Table of Contents

- [Why](#why) — the split bridge's disposition is the missing structural-remedy outcome anchor
- [Input](#input) — the recorder API and the `escalate_to_split` state this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — one leaf + one caller + doc + three test files
- [Implementation](#implementation) — the new recorder, the one-event-per-call site, fingerprint carry, and the best-effort guard
- [Tests](#tests) — recorder roundtrip, each outcome fires once, best-effort, and doc drift
- [Acceptance criteria](#acceptance-criteria) — observable checks a reviewer runs
- [References](#references) — the telemetry/format docs relevant here
- [Deferred](#deferred) — sibling structural bridges and phase-3 behavior owned elsewhere

## Why

`escalate_to_split` is the single seam that decides, for one mixed refactor+feature step, whether to **apply** a refactor→feature split, **recommend** it, or decline (`unsafe` / `proposal-unusable` / `step-missing`). That disposition is the closest thing the structural-remedy vocabulary has to an *outcome* — it tells a later aggregation how often the bridge actually mutates a plan versus recommends versus can't act, per plan and per step. Today the function returns a frozen `EscalateResult` and records **nothing** — no `DecisionEvent` fires — so the distribution of split-bridge outcomes is invisible to any phase-3 resolver that would want to join it back to the `granularity` decisions that flagged the step. BACKLOG #72's phase-2 backfill names the untracked heuristic decisions; the split bridge is one. This step makes the bridge observable — one telemetry line per call — without changing what it decides, returns, or writes.

## Input

This step populates the phase-1 `DecisionEvent` contract and reads state `escalate_to_split` already computes. It changes neither.

- **`record_decision` and its wrappers** in `plan_tool/telemetry.py` — every per-kind wrapper (e.g. `record_convergence`, `record_audit_coverage`, `record_prompt_budget`) is a thin call over `record_decision(repo_root, *, kind, decision, plan_slug, context=..., plan_fingerprint=..., code_fingerprint=..., step_id=...)` taking primitives only. `record_decision` already mints `decision_id`, reads `run_id` from the `_active_run_id` ContextVar, folds `step_id` into the `decision_id` hash, and swallows every error. The new recorder mirrors this shape exactly.
- **The outcome vocabulary** — the frozen `plan_tool/launcher.py:EscalateResult` dataclass's `outcome` field is exactly one of `"applied"` / `"recommended"` / `"unsafe"` / `"proposal-unusable"` / `"step-missing"` (documented in its own docstring). The recorded event carries this string verbatim; `blocking` is populated only on `"unsafe"`.
- **`escalate_to_split`'s in-scope state** — after `plan = parse_plan(plan_path)` succeeds, the function holds `plan`, `plan_path`, `repo_root`, `step_id` (the always-present int target), and `allow_split`. `plan_slug` is reachable via `plan_tool/locator.py:slug_from_filename` (already imported at module top in `plan_tool/launcher.py`). Only `plan_fingerprint` is carried (body ground rule 3) — `compute_plan_fingerprint(plan_path)` — not `code_fingerprint`; the escalate decision is about plan structure/safety, not code footprint.
- **`run_id` needs no work here** — `escalate_to_split` is reached from the `detail` convergence loop and the `review_actions` structural apply walk, not a `run`; `_active_run_id` is unset on those paths, so `run_id` defaults to `""` and needs no threading.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/telemetry.py` — add `ESCALATE_SPLIT_KIND` / `ESCALATE_SPLIT_DECISION` constants and the `record_escalate_split` wrapper (mirrors `record_convergence`'s shape).
  - `plan_tool/launcher.py` — inside `escalate_to_split`, record one `escalate-split` event carrying the final `EscalateResult` outcome, guarded so the fingerprint compute can't raise into the bridge. Add the two fingerprint helpers as body-local imports.
  - `DATA_CONTRACT.md` — add `"escalate-split"` to the `kind` value list in the base `DecisionEvent` table and a new `#### Escalate-to-split outcome` subsection documenting its context keys.
  - `tests/test_telemetry.py` — recorder roundtrip + context-shape unit tests for `record_escalate_split`.
  - `tests/test_data_contract.py` — a `test_escalate_split_context_keys_documented` test mirroring `test_prompt_budget_context_keys_documented`.
  - `tests/test_launcher.py` — assert each `escalate_to_split` outcome path records exactly one event with the right outcome, plus the best-effort invariant.

## Implementation

**Add the recorder wrapper to `plan_tool/telemetry.py`.** Mirror `record_convergence` — the closest sibling, which keeps its varying value (`verdict`) in `context` under a fixed `decision`. Add two module-level constants next to the existing `PROMPT_BUDGET_KIND` block:

- `ESCALATE_SPLIT_KIND = "escalate-split"` — the new decision family literal.
- `ESCALATE_SPLIT_DECISION = "resolved"` — the single decision value; the varying outcome lives in `context`, matching how `convergence`'s `verdict` does.

Then add `record_escalate_split(repo_root, *, plan_slug, outcome, allow_split, step_id, blocking=None, plan_fingerprint="")`. It builds a small `context` bag and calls `record_decision` with `kind=ESCALATE_SPLIT_KIND`, `decision=ESCALATE_SPLIT_DECISION`, forwarding `step_id` (so it folds into the `decision_id` hash). **No `code_fingerprint` param** — per the body's ground rule 3, escalate carries `plan_fingerprint` only; the escalate decision is about plan *structure*/safety, not code footprint, and the full path→hash map earns its bytes only on the drift-gate (which holds it in hand) and the code-grounded code-reveals-split detector (which fires rarely). Keep telemetry a **stdlib-only leaf** — the wrapper takes primitives only and never imports a first-party fingerprint producer; the caller computes the digest and passes it in.

- **Context keys (recommended):** `outcome` (the `EscalateResult.outcome` string), `allow_split` (bool), and `step_id` (str) always present; `blocking` (list of str) added only when non-empty (i.e. the `unsafe` outcome). Omit `blocking` when empty — absence means "no blockers", consistent with how `record_create_step_outcome` omits split-only keys.
- **`step_id` is dual-used** — kept as a context key *and* forwarded into `record_decision(..., step_id=str(step_id))` so the `decision_id` hash separates step-scoped escalate decisions that share a second-precision `ts`. Store it as `str` to match telemetry's step-id normalization.

**Record once per call in `escalate_to_split`.** The function has multiple returns, one per outcome. The invariant to hold: **one recorded event equals one completed `escalate_to_split` call**, carrying that call's final outcome — never one per outcome-arm-that-didn't-fire, never zero.

- **Recommended approach:** compute the shared inputs once, right after `plan = parse_plan(plan_path)` succeeds (so `plan` and `plan_slug` are available on every path, including `step-missing`), then route all returns through one tiny local helper — e.g. `def _record_and_return(result: EscalateResult) -> EscalateResult:` that calls `record_escalate_split(...)` reading `result.outcome`/`result.blocking`, then returns `result`. Change each `return EscalateResult(...)` to `return _record_and_return(EscalateResult(...))`. This single-sources the context bag and guarantees exactly one event per return.
- **Alternative (more latitude, if you prefer no closure):** record inline just before each `return`. It works but repeats the recorder call at every arm; the closure is cleaner and less drift-prone. Either is acceptable as long as every completed call records exactly once.
- **Snapshot at decision time.** Compute `plan_fingerprint` *before* the `applied` path calls `write_plan`, so the event captures the plan state the bridge observed and acted on, not the post-split file. Hoisting the compute above the returns gives this for free (and escalate fires rarely — once per structural finding — so there is no per-finding-loop hot-site concern like the apply-verdict site had).

**Carry `plan_fingerprint` only, guarded.** Escalate is `plan_fingerprint`-only (body ground rule 3); do **not** compute or carry `code_fingerprint`:

- `plan_fingerprint` via `plan_tool/review_persistence.py:compute_plan_fingerprint(plan_path)`.
- **Add it as a body-local import** inside `escalate_to_split` (or a small local fingerprint helper), mirroring the lazy-import style already used for `_apply_step_split` / `_confirm_split` in this function; `plan_tool/launcher.py` does not import the fingerprint helper at module top.
- **Wrap the compute in a local `try/except`** returning `""` on any failure. `record_decision` swallows errors inside the sink, but the fingerprint-compute expression is caller code and would otherwise escape — a fingerprint error must never perturb `escalate_to_split`'s outcome or the callers' convergence loops. `plan_slug` resolution (`slug_from_filename(plan_path) or ""`) is cheap and can share the same guard.

**Constraints that are not free to vary:**

- **No signature or outcome change.** `escalate_to_split`'s parameters, its five `EscalateResult.outcome` values, `blocking`/`recommendation` population, and the "apply-or-recommend, never half-do-it" contract stay identical. The recording is a pure side effect.
- **The no-Claude paths stay no-Claude.** Recording adds no subprocess; it must sit outside the `_propose_step_split` invoker call so the `unsafe` / recommend-only / `step-missing` paths still spend zero tokens. The existing `_raise_invoker` tests prove this.
- **No caller edits.** `escalate_to_split`'s three callers — the two `plan_tool/detail.py:generate_detail` sites and `plan_tool/cli/review_actions.py:_dispatch_structural_escalation` — get the event for free because it fires inside the bridge. Do not touch them.
- **No `data_contract.py` change.** `DecisionEvent`'s fields are unchanged (a new `kind`, not new fields), and a fresh recorder's context keys need no `registered_open_bag_keys()` entry — that registration gates only the `## Input` prose-reference validator, not what a recorder writes. The required doc gate is the new `DATA_CONTRACT.md` subsection plus its drift test.

**Document the new family in `DATA_CONTRACT.md`.** Adding a new event **family** is a different obligation than adding fields: mirror an existing sibling `kind`'s prose subsection and its per-kind context-key test rather than the field-level drift guard. Add `"escalate-split"` to the `kind` value list in the base `DecisionEvent` field table, and add a `#### Escalate-to-split outcome` subsection modeled on `#### Prompt-budget advisory`, with a context-keys table for `outcome` / `allow_split` / `step_id` (always present) and `blocking` (omitted unless the outcome is `unsafe`).

## Tests

Add unit tests with the implementation; every new test must be green before this step is done.

**`tests/test_telemetry.py`** (recorder-shape unit tests; import `record_escalate_split`, `ESCALATE_SPLIT_KIND`, `ESCALATE_SPLIT_DECISION`):

- `test_record_escalate_split_roundtrips` — records one event; read back asserts `kind == "escalate-split"`, `decision == "resolved"`, and `context["outcome"]`/`context["allow_split"]`/`context["step_id"]` match the args.
- `test_escalate_split_blocking_omitted_when_empty` — no `blocking` arg (or empty) → `"blocking"` absent from context.
- `test_escalate_split_blocking_present_on_unsafe` — `blocking=[2]` → `context["blocking"] == ["2"]` (stored as strings).
- `test_escalate_split_step_id_folds_into_decision_id` — two events differing only in `step_id` get different `decision_id`s.
- `test_escalate_split_carries_plan_fingerprint_only` — a passed `plan_fingerprint` lands on the base event field; `code_fingerprint` stays `{}` (the wrapper has no `code_fingerprint` param).

**`tests/test_launcher.py`** (extend `TestEscalateToSplit`, reusing its `_write_plan` helper and the module-level `_split_invoker` / `_raise_invoker` helpers; read events via `read_decisions(tmp_path)`):

- `test_step_missing_records_one_event` — the `step_id=99` path records exactly one event with `outcome == "step-missing"`.
- `test_unsafe_records_blocking` — the downstream-done path records `outcome == "unsafe"` with `context["blocking"] == ["2"]`.
- `test_recommend_only_records_event` — `allow_split=False` records `outcome == "recommended"`, `allow_split` false, no Claude spent.
- `test_proposal_unusable_records_event` — non-JSON invoker records `outcome == "proposal-unusable"`.
- `test_applied_records_event` — `_split_invoker` + confirming `prompt_fn` records `outcome == "applied"`, and the recorded `plan_fingerprint` reflects the pre-split plan (present/non-empty, computed before `write_plan`).
- `test_escalate_records_exactly_one_event_per_call` — any single call yields exactly one `escalate-split` line (guards against double-record or per-arm leakage).
- `test_escalate_fingerprint_failure_does_not_break_bridge` — monkeypatch `compute_plan_fingerprint` to raise; the call still returns the correct outcome and does not propagate the error.

**`tests/test_data_contract.py`:**

- `test_escalate_split_context_keys_documented` — asserts `outcome`, `allow_split`, `step_id`, `blocking` each appear as `` `key` `` in `DATA_CONTRACT.md` (mirrors `test_prompt_budget_context_keys_documented`).
- Confirm the existing `kind`-list / decision-event drift tests stay green after adding `"escalate-split"` to the documented `kind` values.

Green-before-done gate: the full `tests/test_telemetry.py`, `tests/test_launcher.py`, and `tests/test_data_contract.py` suites pass.

## Acceptance criteria

- `plan_tool/telemetry.py` exports `record_escalate_split`, `ESCALATE_SPLIT_KIND == "escalate-split"`, and `ESCALATE_SPLIT_DECISION == "resolved"`.
- Each of the five `escalate_to_split` outcomes records exactly one `escalate-split` `DecisionEvent` whose `context["outcome"]` equals that outcome string.
- The `unsafe` event carries `context["blocking"]` as a list of string ids; the other four omit `blocking`.
- `escalate_to_split`'s return values, five outcomes, control flow, and no-Claude paths are unchanged; the `_raise_invoker` tests still pass.
- A raising fingerprint compute does not change any `escalate_to_split` outcome or propagate an error (best-effort holds).
- `DATA_CONTRACT.md` lists `"escalate-split"` among the `kind` values and has an `#### Escalate-to-split outcome` subsection; `test_escalate_split_context_keys_documented` passes.
- No edits to `plan_tool/data_contract.py`, `escalate_to_split`'s three callers, or the `EscalateResult` dataclass.

## References

- [JSON Lines](https://jsonlines.org/) — the one-object-per-line append contract the recorder emits to `decisions.jsonl`.
- [contextvars — Context Variables (Python 3.13)](https://docs.python.org/3/library/contextvars.html) — how the telemetry-owned `_active_run_id` ContextVar auto-flows `run_id` (unset on the escalate path, so `""`).
- [dataclasses — Data Classes (Python 3.13)](https://docs.python.org/3/library/dataclasses.html) — the defaulted `DecisionEvent` fields (`plan_fingerprint`/`code_fingerprint`) the new event carries, and the frozen `EscalateResult` this step reads.
- [How to mark test functions with attributes — pytest](https://docs.pytest.org/en/stable/how-to/mark.html) — placing the new recorder tests under the project's unit-first convention.

## Deferred

- **Instrumenting the sibling structural bridges** — `plan_tool/scope_out.py:scope_out_step`, `plan_tool/reground.py:reground_bridge`, and `plan_tool/detail.py:merge_bridge` have their own outcomes but are not touched here; each would be its own telemetry family if ever wanted (phase-2/3 candidate, not this step).
- **Outcome linkage / resolution** — tying this `escalate-split` event back to the `granularity` decision that flagged the step is the phase-3 resolver's job, owned by BACKLOG #72's later phases.
- **The `plan-tool telemetry` analysis-and-recommend surface** — reading and aggregating these events is deferred; this step only records.
