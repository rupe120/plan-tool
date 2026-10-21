> **Auto-archived**: this plan was swept on 2026-07-07 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Add `record_prompt_budget` telemetry recorder and document its event shape in `DATA_CONTRACT.md`

## Summary

Add a `record_prompt_budget` convenience recorder to `plan_tool/telemetry.py`, mirroring the existing per-kind seams (`record_convergence`, `record_plan_criteria_breakdown`). It writes one best-effort `DecisionEvent` with a new `kind="prompt-budget"`, capturing the pre-send budget check's `phase`, `total_bytes`, and `advisory` level, plus optional tuning primitives (`estimated_tokens`, `context_window`, `headroom_ratio`) and the per-block breakdown. The recorder takes plain ints/strings — it never imports `plan_tool/prompt_budget.py`, so `telemetry.py` stays a stdlib-only leaf and this step lands independently of step 1's code. Then document the event shape in `DATA_CONTRACT.md` under the existing Decision-telemetry section and add a targeted drift-guard test. On green, `record_prompt_budget(...)` round-trips through `read_decisions`, swallows all errors, and the doc names the new kind and every context key.

## Table of Contents

- [Why](#why) — why the recorder exists and where it sits.
- [Files (creates vs edits)](#files-creates-vs-edits) — the two modules and two test files this step edits.
- [Implementation](#implementation) — the recorder signature, its context shape, the doc edit, and the leaf rule.
- [Tests](#tests) — the telemetry round-trip cases and the doc drift-guard case.
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green.
- [References](#references) — the token-counting docs that ground the recorded fields.
- [Deferred](#deferred) — orchestrator wiring, outcome-linkage, and the `DecisionEvent` schema (all unchanged here).

## Why

The pre-send budget check (step 1's `plan_tool/prompt_budget.py`) returns a `PromptBudget`, but nothing records the verdict yet — so there's no distribution to tune the `warn`/`high` thresholds against later. BACKLOG #72's whole point is retuning heuristics from recorded decisions instead of single-session anecdote, and `plan_tool/telemetry.py` already carries the seam for exactly this: `record_granularity`, `record_audit_coverage`, `record_convergence`, and `record_plan_criteria_breakdown` each project one heuristic decision's primitives into a `DecisionEvent`. This step adds the parallel `record_prompt_budget` seam so the wiring steps (3–7) can log each budget check, and documents the event in `DATA_CONTRACT.md` so the drift guard covers it. It records the decision only — outcome-linkage to actual `CONTEXT_OVERFLOW` failures stays deferred to #72's later phases.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `plan_tool/telemetry.py` — add the `PROMPT_BUDGET_KIND` / `PROMPT_BUDGET_DECISION` constants and the `record_prompt_budget` function, placed alongside the other per-kind recorders (after `record_plan_criteria_breakdown`, before `read_decisions`).
  - `DATA_CONTRACT.md` — under the existing `## Decision telemetry log` section, add `"prompt-budget"` to the `DecisionEvent` `kind` row and add a new `#### Prompt-budget advisory` subsection documenting the context keys.
  - `tests/test_telemetry.py` — add round-trip and omit-when-absent unit tests for the new recorder.
  - `tests/test_data_contract.py` — add a targeted test asserting the new kind and its context keys are documented (mirroring `test_plan_criteria_context_keys_documented`).

## Implementation

**Add one recorder and its two literal constants to `plan_tool/telemetry.py`.** It is a passthrough over the existing `record_decision`, matching the siblings in the `# --- per-kind convenience recorders ---` block.

- **Name the kind and decision as module constants**, mirroring `PLAN_CRITERIA_BREAKDOWN_KIND` / `PLAN_CRITERIA_DECISION`:
  - `PROMPT_BUDGET_KIND = "prompt-budget"` — the new decision family; the `kind` literal the drift-guard test and any later aggregation key on.
  - `PROMPT_BUDGET_DECISION = "estimated"` — the single decision value within the kind.

- **`record_prompt_budget(repo_root, *, plan_slug, phase, total_bytes, advisory, estimated_tokens=None, context_window=None, headroom_ratio=None, blocks=None) -> None`** is the recorder:
  - **Required core** (the plan's named trio): `phase` (which assembly point the check ran at — e.g. `"detail"`, `"create-steps"`, `"run-step"`, `"shell-backstop"`), `total_bytes` (the prompt's measured byte count), and `advisory` (the `PromptBudget.level` string — `"ok"` / `"warn"` / `"high"`). The recorder takes `advisory` as a plain `str`; it must **not** import step 1's `LEVEL_*` constants or `PromptBudget` — the caller passes `budget.level`.
  - **Optional tuning primitives** — `estimated_tokens`, `context_window`, `headroom_ratio`. Include them so a later pass can retune the headroom thresholds (the level alone can't); the caller projects them straight off the `PromptBudget`. Omit each key when its argument is `None`, following `record_create_step_outcome`'s "missing key means not-applicable, not zero" convention.
  - **Optional breakdown** — `blocks`, the per-block name→bytes pairs. `PromptBudget.blocks` is a `tuple[tuple[str, int], ...]`; store it verbatim as a list of `[name, bytes]` pairs (JSON has no tuples) when passed and non-empty, omit the key otherwise. One way: `context["blocks"] = [[str(n), int(b)] for n, b in blocks]`.
  - **Build the context bag, then delegate** to `record_decision(repo_root, kind=PROMPT_BUDGET_KIND, decision=PROMPT_BUDGET_DECISION, plan_slug=plan_slug, context=context)`. Do not re-open the file or re-implement the append — `record_decision` already owns the best-effort write, the byte cap, and the swallow-all-errors guard, so `record_prompt_budget` inherits all of it for free.

- **`plan_slug` may be empty.** The `shell.claude_invoke` backstop (step 7) often has no resolved plan; pass `""` there, matching the documented `plan_slug` (`""` if unresolved) convention. The recorder does not require a slug.

- **Do not filter by level.** The recorder is a dumb passthrough — it records whatever `advisory` it's given, including `"ok"`. Whether to record every check or only `warn`/`high` is the caller's call (wiring steps 3–7); keeping the filter out of the recorder matches the other seams, which never inspect their own inputs.

- **Leaf rule — keep `telemetry.py` stdlib-only.** The module docstring's first bullet is "imports nothing first-party." `record_prompt_budget` takes only ints/strings/list, so it holds that line. The `PromptBudget`→primitives projection happens in the wiring steps' callers, never here — this is the same discipline the other recorders follow (callers compute counts from their own plan/finding types).

**Foundational logic and its siblings.** The core behavior added is *project one budget-check verdict into a `DecisionEvent`*. Every existing per-kind recorder in `plan_tool/telemetry.py` is the same shape; there is no duplicated budget-logging block anywhere else to consolidate (step 2 is the first and only recorder for this kind — the wiring steps 3–7 call this one function, they don't re-implement it). No shared-location cleanup is needed.

**`DATA_CONTRACT.md` edit — document the event, don't restate the schema.**

- **Add `"prompt-budget"` to the `DecisionEvent` `kind` row** in the `### DecisionEvent (telemetry.py)` table (the row currently listing `"granularity"` | `"audit-coverage"` | `"convergence"` | `"plan-criteria-breakdown"`).
- **Add a `#### Prompt-budget advisory` subsection** after `#### Plan split-criteria breakdown`, following that subsection's format: one sentence naming `kind="prompt-budget"` and `decision="estimated"`, then a context-keys table with `phase`, `total_bytes`, `advisory`, `estimated_tokens`, `context_window`, `headroom_ratio`, and `blocks`. Note which keys are always present (`phase` / `total_bytes` / `advisory`) and which are omitted when absent (the three tuning primitives and `blocks`).
- **No `DecisionEvent` field change.** This step adds a new `kind` and new `context` keys, not a new dataclass field — `DecisionEvent`'s six fields (`schema_version`, `ts`, `kind`, `decision`, `plan_slug`, `context`) are unchanged and already documented, so `test_every_persisted_field_is_documented` needs nothing new and `TELEMETRY_SCHEMA_VERSION` stays `1`.

## Tests

All telemetry cases live in `tests/test_telemetry.py`; the doc case lives in `tests/test_data_contract.py`. This is a **feature** step: write these unit tests alongside the recorder, and every one must be green before the step is done.

In `tests/test_telemetry.py` (import `record_prompt_budget`, `PROMPT_BUDGET_KIND`, `PROMPT_BUDGET_DECISION` from `plan_tool.telemetry`):

- `test_record_prompt_budget_roundtrips` — a call with all fields round-trips through `read_decisions`: `kind == PROMPT_BUDGET_KIND`, `decision == PROMPT_BUDGET_DECISION`, `plan_slug` set, and the context carries `phase` / `total_bytes` / `advisory` / `estimated_tokens` / `context_window` / `headroom_ratio` / `blocks`.
- `test_record_prompt_budget_omits_optional_keys` — a call passing only the required trio (`phase` / `total_bytes` / `advisory`) writes a context with exactly those three keys; `estimated_tokens`, `context_window`, `headroom_ratio`, and `blocks` are absent (not present with a `null` value).
- `test_record_prompt_budget_blocks_serialize_as_pairs` — passing `blocks=(("detail", 1200), ("lessons", 300))` reads back as list-of-pairs preserving order/values.
- `test_record_prompt_budget_empty_slug_ok` — `plan_slug=""` (the backstop case) records without error and reads back with an empty slug.
- `test_record_prompt_budget_is_best_effort` — an unwritable `repo_root` (a regular file, per `test_record_is_best_effort_never_raises`) does not raise and yields no events.
- `test_prompt_budget_constants_have_expected_values` — `PROMPT_BUDGET_KIND == "prompt-budget"` and `PROMPT_BUDGET_DECISION == "estimated"` (pins the literals the doc and drift guard key on).

In `tests/test_data_contract.py`:

- `test_prompt_budget_decision_documented` — `"prompt-budget"` appears in the doc (mirrors `test_plan_criteria_decision_documented`).
- `test_prompt_budget_context_keys_documented` — every context key (`phase`, `total_bytes`, `advisory`, `estimated_tokens`, `context_window`, `headroom_ratio`, `blocks`) appears as `` `<key>` `` in the doc (mirrors `test_plan_criteria_context_keys_documented`).

Green-before-done gate: `uv run pytest tests/test_telemetry.py tests/test_data_contract.py -q` passes, and the full suite stays green.

## Acceptance criteria

- `plan_tool/telemetry.py` exposes `record_prompt_budget`, `PROMPT_BUDGET_KIND == "prompt-budget"`, and `PROMPT_BUDGET_DECISION == "estimated"`.
- `record_prompt_budget(repo_root, plan_slug=…, phase=…, total_bytes=…, advisory=…)` writes one `DecisionEvent` with `kind="prompt-budget"`, `decision="estimated"`, and a context containing `phase` / `total_bytes` / `advisory`; it round-trips through `read_decisions`.
- Passing only the required trio omits `estimated_tokens`, `context_window`, `headroom_ratio`, and `blocks` from the recorded context entirely (absent keys, not `null`).
- `blocks` passed as a tuple of `(name, bytes)` pairs reads back as an ordered list of `[name, bytes]` pairs.
- The recorder never raises: an unwritable `repo_root` produces no events and no exception.
- `plan_tool/telemetry.py` imports nothing first-party (no import of `plan_tool.prompt_budget`); `TELEMETRY_SCHEMA_VERSION` is still `1`.
- `DATA_CONTRACT.md` lists `"prompt-budget"` in the `DecisionEvent` `kind` row and has a `#### Prompt-budget advisory` subsection naming `decision="estimated"` and every context key.
- `uv run pytest tests/test_telemetry.py tests/test_data_contract.py -q` passes.

## References

- [Anthropic — Token counting](https://docs.anthropic.com/en/docs/build-with-claude/token-counting) — grounds why `total_bytes` / `estimated_tokens` / `context_window` are the primitives worth recording for later threshold tuning.
- [Anthropic — Models overview (context windows)](https://docs.anthropic.com/en/docs/about-claude/models/overview) — per-model window sizes, the reference for the recorded `context_window` and `headroom_ratio`.

## Deferred

- **Orchestrator wiring** (`generate_detail`, `create_plan`, `audit_plan_until_stable`, `run_step`, `shell.claude_invoke`) that computes a `PromptBudget` and calls `record_prompt_budget` — steps 3–7. This step adds the recorder and its doc only; no caller invokes it yet.
- **The `PromptBudget`→primitives projection** — lives in each wiring step's caller (they hold the `PromptBudget`); the recorder takes primitives so `telemetry.py` stays a stdlib-only leaf.
- **Outcome-linkage** of a recorded advisory to the actual `CONTEXT_OVERFLOW` failure it predicted, and the analysis/recommend-tuning surface — BACKLOG #72 phases 2–3, not here.
- **Any `DecisionEvent` field change or `TELEMETRY_SCHEMA_VERSION` bump** — this step adds a new `kind` and context keys within the existing open `context` bag, so the persisted dataclass and its version are untouched.
