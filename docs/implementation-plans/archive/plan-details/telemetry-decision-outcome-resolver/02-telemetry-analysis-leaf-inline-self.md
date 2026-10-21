> **Auto-archived**: this plan was swept on 2026-07-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Add the telemetry_analysis leaf with inline self-recording outcome verdicts

## Summary

Creates `plan_tool/telemetry_analysis.py`, the read-only decision→outcome resolver leaf, plus its test file. This step ships only the **inline** half of the two-tier outcome model: the three decision families that already record their own result in-call (`apply-verdict`, `escalate-split`, and create's `create-step-outcome`) get their recorded result mapped straight to one outcome verdict. The key decision: the leaf owns the shared verdict vocabulary (`acted-on` / `no-op` / `reverted` / `still-open`) and a per-event `resolve_decision_inline` mapper now, and the top-level `resolve_decisions(repo_root)` marks every non-self-recording event `unresolved` — a branch step 3 swaps for the async run-log/sidecar join. On green, `resolve_decisions` reads the whole decision log via `telemetry.read_decisions`, returns a frozen `ResolvedDecision` per event, and the module imports no `plan_tool.cli`.

## Table of Contents

- [Why](#why) — what the resolver adds and why the inline slice lands first
- [Input](#input) — the `DecisionEvent` schema and the three self-recording families this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — the two new files
- [Implementation](#implementation) — the verdict vocabulary, the inline mapper, the top-level reader, and the leaf-boundary rule
- [Tests](#tests) — the unit cases added with the code and the green gate
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — stdlib/format docs relevant to this step
- [Deferred](#deferred) — the async join, aggregation, CLI, and cache left for later steps

## Why

Phases 1–2 shipped the `DecisionEvent` schema and the producers that populate its join keys, but nothing reads the keys back into an outcome. The plan's design (spike §6) splits outcome resolution two ways: some decisions record their own result in the same call (`apply-verdict.context.verdict`, `escalate-split.context.outcome`, `create-step-outcome.context.action`), while others only become clear many runs later and need a run-log/sidecar join. This step lands the leaf module and the **easy, self-contained half** — the inline families that need nothing but their own recorded context. It gives step 3 (the async join), step 4 (aggregation), and step 5 (the `plan-tool telemetry` command) a module to build in, a settled verdict vocabulary to reuse, and a top-level entry seam (`resolve_decisions`) whose `unresolved` branch step 3 fills. Shipping inline first means the leaf is independently green and fully tested before the harder cross-run join lands.

## Input

This step reads the **decision-log JSONL** through `plan_tool/telemetry.py:read_decisions(repo_root) -> list[DecisionEvent]`. It does not parse the log itself — `read_decisions` is the single tolerant reader (skips blank/malformed/forward-version lines). The `DecisionEvent` fields this step uses: `kind`, `decision`, `plan_slug`, `context`, and `decision_id`.

The three self-recording families and the context key each records its result in:

- **`apply-verdict`** — `kind == telemetry.APPLY_VERDICT_KIND` (`"apply-verdict"`), result in `context["verdict"]`. Values: `APPLIED` / `NOT-APPLICABLE` / `BLOCKED` / `BLOCKED-STRUCTURAL` / `UNKNOWN` (see `launcher.py:parse_apply_verdict`; `UNKNOWN` is the ran-but-no-token normalization).
- **`escalate-split`** — `kind == telemetry.ESCALATE_SPLIT_KIND` (`"escalate-split"`), result in `context["outcome"]`. Values: the frozen `EscalateResult.outcome` set — `applied` / `recommended` / `unsafe` / `proposal-unusable` / `step-missing`.
- **`create-step-outcome`** — `kind == "granularity"` **and** `decision == telemetry.CREATE_DECISION_STEP_OUTCOME` (`"create-step-outcome"`), result in `context["action"]`. Values: the `telemetry.CREATE_ACTION_*` constants — `accept` / `override` / `split-requested` / `split-applied` / `split-unusable` / `split-invalid` / `split-error` / `unclassified-accepted` / `unclassified-classified`.

Note the `granularity` kind is overloaded: `record_granularity` (decision `"assessed"`), `record_code_reveals_split` (decision `"code-reveals-split"`), and `record_create_granularity_assessment` (decision `"create-review"`) all share `kind == "granularity"`. Only `decision == "create-step-outcome"` is self-recording; the others are async and belong to step 3. Match on the `(kind, decision)` pair, not `kind` alone.

Import the family/action string constants **from `telemetry.py`** rather than re-typing the literals — they are the contract, and re-typing them lets the two modules drift.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/telemetry_analysis.py` — the resolver leaf: verdict + resolution constants, the `ResolvedDecision` frozen dataclass, the per-event `resolve_decision_inline` mapper, and the top-level `resolve_decisions(repo_root)` reader.
  - `tests/test_telemetry_analysis.py` — unit tests for the mapper, the reader, tolerance of the mixed/ownerless tail, and the leaf-import boundary.
- **Existing files (edits only):** none.

## Implementation

**Foundational logic:** map a self-recording decision's recorded result to one outcome verdict. Ship it as a per-event pure mapper plus a top-level reader.

**Create the module as a cycle-free leaf, like `plan_tool/convergence_diagnosis.py`.**
- Its only first-party import in this step is `from plan_tool.telemetry import read_decisions, DecisionEvent, APPLY_VERDICT_KIND, ESCALATE_SPLIT_KIND, CREATE_DECISION_STEP_OUTCOME, CREATE_ACTION_*` (the constants you match on). Import at module top — these are all leaves that don't import back.
- **Never import `plan_tool.cli`.** This is the plan's named "leaf-cycle regression" risk. Step 3 adds `run_log` / `convergence_diagnosis` / `review_persistence` / `locator` imports for the async join; step 2 needs only `telemetry`. Keep the boundary a test asserts (see Tests).

**Define the shared verdict vocabulary as module constants** — step 3 (async) and step 4 (aggregation) key on these, so name them, don't inline the literals:
- `OUTCOME_ACTED_ON = "acted-on"` — the heuristic's suggested action was taken and stuck in-call.
- `OUTCOME_NO_OP = "no-op"` — deliberately not acted on, or nothing was applicable to act on.
- `OUTCOME_REVERTED = "reverted"` — acted on, then undone. Async-only; the inline mapper never emits it (an in-call result can't observe a later revert). Define it here so the vocabulary is complete and step 3 reuses it.
- `OUTCOME_STILL_OPEN = "still-open"` — attempted-but-unresolved, awaiting a later step, or an unrecognized result value.

Also define resolution markers so a reader can tell how an outcome was decided: `RESOLUTION_INLINE = "inline"` and `RESOLUTION_UNRESOLVED = "unresolved"`. Step 3 adds `RESOLUTION_ASYNC = "async"` as one more marker — do not fold "inline vs unresolved" into a bool, keep it a small string set the later step extends (mirrors the "model a growing response vocabulary as an enum, not a bool" lesson).

**The `ResolvedDecision` output shape** — a frozen dataclass (mirror `convergence_diagnosis.py`'s frozen records). Recommended fields:
- `decision_id: str`, `kind: str`, `decision: str`, `plan_slug: str` — the identity/grouping keys step 4 buckets on (copied off the event so a consumer needn't re-hold the whole `DecisionEvent`).
- `outcome: str` — one of the `OUTCOME_*` constants.
- `resolution: str` — one of the `RESOLUTION_*` markers.
- `evidence: str` — the raw recorded result string that drove the verdict (e.g. the `verdict` / `outcome` / `action` value), so a later render can show *why* without re-reading context.

One way to keep it lean: carry the whole `DecisionEvent` plus `outcome`/`resolution`/`evidence`. Either is fine — the constraint is that step 4 can group by `kind`/`decision`/`plan_slug` and read the outcome off the result.

**The per-event mapper `resolve_decision_inline(event: DecisionEvent) -> Optional[str]`:**
- Returns an `OUTCOME_*` verdict for a self-recording family, or `None` when the event is not self-recording (its outcome is async — step 3's job). `None` is the signal that separates the two tiers.
- Split by `(kind, decision)` / `kind`, then read the family's result key and map it. A recommended mapping (the implementer owns the exact table; state the principle in a comment):
  - **apply-verdict** `context["verdict"]`: `APPLIED` → `acted-on`; `NOT-APPLICABLE` → `no-op`; `BLOCKED` / `BLOCKED-STRUCTURAL` / `UNKNOWN` → `still-open`.
  - **escalate-split** `context["outcome"]`: `applied` → `acted-on`; `recommended` → `still-open` (proposed, awaiting the operator); `unsafe` / `proposal-unusable` / `step-missing` → `no-op` (couldn't act).
  - **create-step-outcome** `context["action"]`: `split-applied` → `acted-on`; `accept` / `override` / `unclassified-accepted` / `unclassified-classified` → `no-op` (the split hint was not taken); `split-requested` / `split-error` / `split-unusable` / `split-invalid` → `still-open` (asked-for but not landed).
- **An unrecognized result value maps to `still-open`, never drops the event.** The whole surface exists to *count* decisions; silently dropping an event with an unexpected `verdict`/`action` string would recreate the blind spot #72 closes. This mirrors the "unknown enum → safe visible default, never drop" lesson. `still-open` is the safe "we saw it but can't call it resolved" bucket.
- Read context values defensively: `str(event.context.get("verdict", ""))` etc. A malformed/absent key must not raise — the resolver stays total, like every reader in this subsystem.

**The top-level reader `resolve_decisions(repo_root: Path) -> list[ResolvedDecision]`:**
- Calls `read_decisions(repo_root)`, then for each event: if `resolve_decision_inline` returns a verdict, emit a `ResolvedDecision(resolution=RESOLUTION_INLINE, outcome=<verdict>, evidence=<result string>)`; otherwise emit `resolution=RESOLUTION_UNRESOLVED` with `outcome=OUTCOME_STILL_OPEN` (nothing joined yet).
- **This `unresolved` branch is the step-3 seam.** Step 3 replaces "emit unresolved" with "attempt the async join, fall back to unresolved on no match" — an added branch, not a signature change. Keep `resolve_decisions` returning one `ResolvedDecision` per event so the shape is stable across the two steps.
- An empty or missing log yields `[]` (inherited free from `read_decisions`, which returns `[]` on any `OSError`).

**Related logic, deliberately not consolidated.** `convergence_diagnosis.py:_is_resolved_in_run` maps a finding's `Annotation.status` to a resolved/open call — a sibling "map a recorded state to a verdict" rule, but over *findings/annotations*, not *decisions*, with a different vocabulary. Do not try to share a mapper: the input types and the outcome sets differ. Keep this step's mapping self-contained in `telemetry_analysis.py`.

## Tests

All cases in `tests/test_telemetry_analysis.py` (unit tier; mirror `tests/test_telemetry.py`'s style of building `DecisionEvent`s directly). Approx 14–16 tests.

- `test_apply_verdict_applied_is_acted_on` — `apply-verdict` with `context.verdict == "APPLIED"` → `acted-on`.
- `test_apply_verdict_not_applicable_is_no_op` — `NOT-APPLICABLE` → `no-op`.
- `test_apply_verdict_blocked_is_still_open` — `BLOCKED` and `BLOCKED-STRUCTURAL` → `still-open`.
- `test_apply_verdict_unknown_is_still_open` — `UNKNOWN` → `still-open`.
- `test_escalate_split_applied_is_acted_on` — `escalate-split` outcome `applied` → `acted-on`.
- `test_escalate_split_recommended_is_still_open` — `recommended` → `still-open`.
- `test_escalate_split_unsafe_is_no_op` — `unsafe` / `proposal-unusable` / `step-missing` → `no-op`.
- `test_create_step_outcome_split_applied_is_acted_on` — `create-step-outcome` action `split-applied` → `acted-on`.
- `test_create_step_outcome_accept_is_no_op` — `accept` / `override` → `no-op`.
- `test_create_step_outcome_split_error_is_still_open` — `split-error` → `still-open`.
- `test_unknown_result_value_is_still_open` — a self-recording family with an unrecognized `verdict`/`action` string maps to `still-open`, not dropped.
- `test_granularity_assessed_is_not_inline` — `kind == "granularity"`, `decision == "assessed"` (and `"code-reveals-split"`, `"create-review"`) → `resolve_decision_inline` returns `None` (async, step 3).
- `test_non_self_recording_family_returns_none` — a `drift-gate` / `convergence` event → `None`.
- `test_inline_mapper_never_emits_reverted` — no inline input produces `OUTCOME_REVERTED`.
- `test_resolve_decisions_marks_non_inline_unresolved` — over a mixed log, inline families get `resolution == "inline"`, everything else `resolution == "unresolved"` / `outcome == "still-open"`.
- `test_resolve_decisions_empty_log_returns_empty` — no log file → `[]`.
- `test_resolve_decisions_tolerates_missing_context_keys` — an `apply-verdict` event with no `verdict` key resolves (to `still-open`) rather than raising.
- `test_telemetry_analysis_does_not_import_cli` — read the module source (or inspect its imports) and assert no `plan_tool.cli` reference, guarding the leaf boundary the plan's risk names.
- `test_resolved_decision_is_frozen` — mutating a `ResolvedDecision` field raises (`FrozenInstanceError`).

**Test-creation order (feature step):** write each mapping test alongside the mapper and each reader test alongside `resolve_decisions`. Every test above must be green before this step is considered done.

## Acceptance criteria

- `plan_tool/telemetry_analysis.py` exists and imports no `plan_tool.cli` (asserted by a test).
- `resolve_decision_inline(event)` returns the mapped `OUTCOME_*` verdict for `apply-verdict`, `escalate-split`, and `create-step-outcome` events, and `None` for every other family.
- An unrecognized result value in a self-recording family maps to `OUTCOME_STILL_OPEN` — no event is dropped.
- The inline mapper never returns `OUTCOME_REVERTED`.
- `resolve_decisions(repo_root)` returns one `ResolvedDecision` per event, `resolution == "inline"` for self-recording families and `"unresolved"` otherwise; an empty/absent log returns `[]`.
- `ResolvedDecision` is a frozen dataclass carrying at least `decision_id`, `kind`, `decision`, `plan_slug`, `outcome`, `resolution`.
- The verdict constants (`OUTCOME_ACTED_ON` / `OUTCOME_NO_OP` / `OUTCOME_REVERTED` / `OUTCOME_STILL_OPEN`) and resolution markers are module-level names, not inlined literals.
- `uv run pytest tests/test_telemetry_analysis.py -q` is green.

## References

- [dataclasses — Data Classes (Python 3.13)](https://docs.python.org/3/library/dataclasses.html) — `@dataclass(frozen=True)` for the `ResolvedDecision` output shape, mirroring `convergence_diagnosis.py`'s frozen records.
- [json — JSON encoder and decoder (Python 3.13)](https://docs.python.org/3/library/json.html) — context for how `telemetry.read_decisions` parses the per-line records this step consumes.
- [JSON Lines format specification](https://jsonlines.org/) — the newline-delimited JSON format of the decision log `read_decisions` streams.

## Deferred

- **Async / derived outcome joins** — the `run_id`→run-log and `plan_fingerprint`-transition path plus the reused `convergence_diagnosis` matcher (spike §6), deriving `acted-on` / `no-op` / `reverted` / `still-open` for the un-inline tail. Owned by step 3 (depends on 1 and 2); it fills `resolve_decisions`' `unresolved` branch and adds `RESOLUTION_ASYNC`.
- **Aggregation across plans by `kind`/`decision`** and the advisory tuning recommendations — step 4.
- **The `plan-tool telemetry` command** wiring the leaf (`cli/telemetry_cmd.py`, `--json`) — step 5.
- **Persisting derived verdicts as a cache sidecar** — the plan defaults to compute-on-read (design decision #4), so this step adds no persisted shape and touches no `DATA_CONTRACT.md` / drift guard; a cache lands only if a later step proves it necessary.
- **Time-windowing / capping the log read** — added only if a full `read_decisions` proves too slow (plan Deferred).
