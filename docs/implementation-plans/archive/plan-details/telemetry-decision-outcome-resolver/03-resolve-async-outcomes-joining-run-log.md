> **Auto-archived**: this plan was swept on 2026-07-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Resolve async outcomes by joining the run-log and sidecar transitions, reusing the convergence_diagnosis matcher

## Summary

Fills the `unresolved` branch step 2 left in `plan_tool/telemetry_analysis.py:resolve_decisions`. For every decision that does *not* record its own result in-call, this step tries an **async join**: it ties the decision to what happened later by two evidence sources — the completed run's outcome (via step 1's `run_log.read_run_outcome`, keyed on `DecisionEvent.run_id`) and a later **plan_fingerprint transition** confirmed with the `convergence_diagnosis.py` region matcher (via `load_report_history`). From that it derives one of `acted-on` / `no-op` / `reverted` / `still-open` and marks the row `RESOLUTION_ASYNC`; a decision that joins to nothing stays `unresolved` / `still-open`. The one design rule that matters: **reuse the tested matcher, do not build a second one** — synthesize the decision's focus and feed it through the existing `_normalized_focus` / `_step_token` / region-trend machinery. On green, the §7 smoke test passes end-to-end (a `code-reveals-split` fire at fingerprint P → a split → a later sidecar at P′ where the flagged step became two steps → `acted-on`), and the leaf still imports no `plan_tool.cli`.

## Table of Contents

- [Why](#why) — what the inline slice can't resolve and why the async join lands now
- [Input](#input) — the contracts this step joins across (steps 1–2, convergence_diagnosis, telemetry)
- [Files (creates vs edits)](#files-creates-vs-edits) — the two edited files
- [Implementation](#implementation) — the async resolver, the two evidence sources, the injected-evidence seam, and the reuse rule
- [Tests](#tests) — unit cases for the derivation plus the §7 integration smoke test
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — stdlib/format docs relevant to this step
- [Deferred](#deferred) — the cache, aggregation, CLI, and time-windowing left for later steps

## Why

Step 2 shipped the inline half: the three families that record their own result (`apply-verdict`, `escalate-split`, `create-step-outcome`) map straight to a verdict. Everything else — `granularity/assessed`, `granularity/code-reveals-split`, `drift-gate`, `convergence`, `audit-coverage`, and the ownerless tail — currently returns `resolution=unresolved` / `outcome=still-open` because nothing joins the decision to its later effect. That is the hard case BACKLOG #72 names: *an outcome can be many runs later*. Without this join the mission payoff (tune a threshold from the distribution of what a signal actually led to, not by anecdote) is out of reach, and the spike's §7 smoke test — did `code-reveals-split` firing on step N actually lead to step N being split? — cannot run at all. This step lands that join by extending the same read-only leaf, reusing the already-tested cross-run matcher rather than inventing a parallel one.

## Input

This step joins across four contracts. It reads them; it owns none of their shapes.

- **Step 2's resolver seam** (`plan_tool/telemetry_analysis.py`). Step 2 produces the `ResolvedDecision` frozen dataclass, the verdict constants (`OUTCOME_ACTED_ON` / `OUTCOME_NO_OP` / `OUTCOME_REVERTED` / `OUTCOME_STILL_OPEN`), the resolution markers (`RESOLUTION_INLINE` / `RESOLUTION_UNRESOLVED`), and `resolve_decisions(repo_root)` returning **one `ResolvedDecision` per event**. This step swaps the body of that function's `unresolved` branch and adds `RESOLUTION_ASYNC` — it does not change the signature or the per-event contract.
- **Step 1's completed-run reader** (`plan_tool/run_log.py`). Step 1 produces `read_run_outcome(path) -> Optional[RunOutcome]` and the frozen `RunOutcome` (fields `run_id`, `completed`, `outcome`, `rc`, `duration_ms`, `error`, `iteration_outcomes`). Key contract this step relies on: `None` means *no run log at that path*, while `completed=False` means *events exist but no terminal `run_end`* (a crashed or still-running invocation). The path is built with `plan_tool/run_log.py:run_log_path(repo_root, slug, run_id)`. Note `iteration_outcomes` is empty on every real log today (`IterationEnd` has no producer), so the run-log signal available now is `RunEnd`-level (`completed` + `outcome` + `rc`).
- **The `convergence_diagnosis.py` matcher** (`plan_tool/convergence_diagnosis.py`). Reuse `load_report_history(plan_path) -> ReportHistory`, the `RunSnapshot` / `RunFinding` shapes, and the focus/matching primitives `_normalized_focus`, `_step_token`, `_matches`, `TITLE_SIMILARITY_CUTOFF`, and the region layer (`build_region_trends` / `RegionTrend`). Every `RunSnapshot` carries `plan_fingerprint` and `code_fingerprint` — the transition signal this join reads.
- **The decision stream** (`plan_tool/telemetry.py`). `read_decisions(repo_root) -> list[DecisionEvent]` (already called by step 2). This step reads more of the `DecisionEvent`: `run_id`, `plan_fingerprint`, `anchor`, and `context` (e.g. `code-reveals-split` carries `context["step_ids"]`, a plural list of flagged steps — see `record_code_reveals_split`). `step_id` is **not** a stored field on `DecisionEvent` (it folds into the `decision_id` hash only), so the decision's step focus comes from `context` / `anchor`, never a `step_id` attribute.

**Verification limit:** the only end-to-end async link the plan commits to proving is the §7 smoke test (`code-reveals-split` → split → sidecar transition). Treat other async families' verdicts as best-effort — join where the keys allow, fall back to `still-open` otherwise.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/telemetry_analysis.py` — add `RESOLUTION_ASYNC`; add the async resolver function(s) (the per-event derivation over injected evidence); add the module-top leaf imports for `run_log`, `convergence_diagnosis`, `review_persistence`, and `locator`; rewrite the `unresolved` branch inside `resolve_decisions` to attempt the join and fall back.
  - `tests/test_telemetry_analysis.py` — add unit tests for each async verdict over injected evidence, the ownerless/unjoinable-tail degradation, the leaf-boundary guard staying green with the new imports, and the §7 integration smoke test.

## Implementation

**Foundational logic:** derive an outcome verdict for a decision whose effect lands *later*, by joining on `run_id` (run-log) and on a `plan_fingerprint` transition confirmed with the reused region matcher. Grep confirms this cross-run correlation exists in exactly one place — `plan_tool/convergence_diagnosis.py` (`_normalized_focus`, `_matches`, `build_region_trends`). Reuse it; do **not** add a second matcher in `telemetry_analysis.py`.

**Add `RESOLUTION_ASYNC = "async"` beside step 2's resolution markers.** Keep the marker set a small string set the reader extends — do not collapse inline/async/unresolved into a bool or enum reshape. `RESOLUTION_ASYNC` labels a row whose verdict came from the join; `RESOLUTION_UNRESOLVED` still labels a row nothing joined.

**Add the module-top leaf imports.** Step 2's boundary rule (`grep -E '^(from|import) plan_tool' <leaf>` finds only `telemetry`) now widens to the read APIs the plan's design decision #2 names: `plan_tool.run_log`, `plan_tool.convergence_diagnosis`, `plan_tool.review_persistence`, and `plan_tool.locator`. All four are cycle-free leaves that never import back, so they sit at module top. **`plan_tool.cli` stays forbidden** — the leaf-cycle risk the plan names; the boundary test must still pass with the wider import set.

**Shape the async derivation as a pure function over injected evidence.** This is the key testability decision — mirror how `convergence_diagnosis` keeps its verdict pure over `ReportHistory` and lets the CLI wire the disk read. Recommended shape:

- `resolve_decision_async(event, *, run_outcome, history) -> Optional[tuple[str, str]]` — returns `(outcome, evidence)` or `None` when nothing joined. `run_outcome` is an `Optional[RunOutcome]` and `history` is an `Optional[ReportHistory]`, both supplied by the caller. Injecting the evidence (not reading disk inside) keeps every derivation test hermetic against hand-built `RunOutcome` / `ReportHistory` values, and keeps the disk reads in one place.
- The **caller** (`resolve_decisions`) does the wiring: build `run_log_path(repo_root, event.plan_slug, event.run_id)` and call `read_run_outcome` when `run_id` is non-empty; resolve the plan path for `event.plan_slug` and call `load_report_history` for the sidecar history.

**The two evidence sources and how to combine them** (state the principle; the exact table is the implementer's to refine against the §7 test):

- **Run-log join (on `run_id`).** When `event.run_id` is empty or `run_outcome is None`, there is no run evidence — skip this source. When `run_outcome.completed is False`, the run crashed or is still running → lean `still-open`. When `completed is True`, the terminal `outcome`/`rc` is a coarse signal that the decision's run finished; carry it as evidence but do not treat a green run alone as `acted-on` for a decision whose real effect is a plan-structure change (that is the sidecar source's job).
- **Sidecar-transition join (on `plan_fingerprint` + the matcher).** This is the source that carries the §7 smoke test. Compute the decision's **focus** from what the event actually stores — `context["step_ids"]` for `code-reveals-split`, else a `step<N>` token parsed from `event.anchor` via the reused `_step_token`, else the fuzzy-title path. Then read the plan's report history:
  - A **plan_fingerprint transition** — the decision fired at `event.plan_fingerprint` (P) and a later `RunSnapshot.plan_fingerprint` differs (P′) — means the plan changed after the decision. Confirm the change is the one the decision asked for by checking, with the reused matcher, that the flagged focus's region **resolved / is gone** in the later snapshots → `acted-on`.
  - **No transition** (the latest snapshot's `plan_fingerprint` still equals P, or the flagged region keeps recurring without shrinking) → `still-open`.
  - **Resolved then recurring again** (the region disappears after P, then reappears) → `reverted`. This is the verdict only the async source can produce — the inline mapper can never emit it.
  - **No matching region ever existed** to act on → `no-op`.
- **Precedence when both sources speak:** let the sidecar-transition verdict win for the plan-structure families (that is where the meaningful outcome lives); use the run-log signal as the fallback / tie-breaker and as `evidence`. State the chosen precedence in a one-line comment.

**Rewrite the `unresolved` branch in `resolve_decisions`.** Per step 2's seam, replace "emit `RESOLUTION_UNRESOLVED` / `still-open`" with: gather evidence, call `resolve_decision_async`; on a verdict emit `ResolvedDecision(resolution=RESOLUTION_ASYNC, outcome=<verdict>, evidence=<evidence>)`; on `None` fall back to the exact old `RESOLUTION_UNRESOLVED` / `OUTCOME_STILL_OPEN` row. Keep it **one `ResolvedDecision` per event** — the shape step 4 groups on must not change.

**Constraints and gotchas that are not free to vary:**

- **Load each plan's history once per `plan_slug`, not once per event.** Many events share a slug; `load_report_history` re-globs and re-parses the sidecar dir, so cache it in a `dict[str, Optional[ReportHistory]]` across the event loop. This mirrors the "hoist the invariant snapshot above the loop" rule.
- **Resolve `plan_slug` → plan path tolerantly, and degrade to `history=None` on a miss.** The resolver holds `repo_root` + `plan_slug`; `load_report_history` needs a real `plan_path` (it derives the reports dir from the plan file's bundle location). One way: build a slug→path map from `locator.list_plans_from_manifest(repo_root)` once. A slug not in the manifest (a deleted/renamed plan, `plan_slug == ""`) resolves to no history → the sidecar source is simply skipped. This is what keeps the ownerless / `plan_slug=""` tail counted-but-not-correlated rather than crashing.
- **Stay total — never raise.** Every reader in this subsystem degrades: `read_run_outcome` returns `None`, `load_report_history` returns an empty history, `read_decisions` returns `[]`. Wrap the per-event join so a surprise (a malformed context value, a missing key) falls back to `still-open` for that one event, not an exception that sinks the whole read. Read context defensively (`event.context.get("step_ids", [])`, `str(...)`), exactly as step 2 reads its result keys.
- **`run_id == ""` and `plan_fingerprint == ""` are the "no anchor here" signals, not errors.** Authoring-time decisions (create) carry `run_id=""`; a pre-write decision carries the empty-file `plan_fingerprint`. Both correctly skip their respective source and, if neither source joins, the event stays `unresolved`.
- **Do not persist derived verdicts.** Design decision #4 is compute-on-read; this step adds no cache sidecar and touches no `DATA_CONTRACT.md` / drift guard. (Deferred names the cache.)

**Related logic, deliberately not consolidated.** `convergence_diagnosis.py:_is_resolved_in_run` and the region-trend `closed` rule map an `Annotation` to a resolved/open call — close in spirit to this step's "did the flagged region resolve" question, but keyed on per-run annotations, not a decision's fingerprint transition. Reuse the *matcher* primitives (`_normalized_focus` / `_matches` / `build_region_trends`); do not try to fold this step's decision-level derivation into `_is_resolved_in_run` — the inputs and the verdict vocabulary differ.

## Tests

All in `tests/test_telemetry_analysis.py` (extend step 2's file). Build `DecisionEvent`, `RunOutcome`, and `ReportHistory` values directly; inject them so the derivation tests need no disk and no Claude. Approx 12–16 unit tests plus one integration test.

**Async derivation (pure, injected evidence):**
- `test_async_run_completed_carries_run_evidence` — a non-inline event with a `run_id` and a `completed=True` `RunOutcome` resolves via the run-log source with the run's outcome as evidence.
- `test_async_run_incomplete_is_still_open` — a `completed=False` `RunOutcome` (crashed/running) → `still-open`.
- `test_async_no_run_id_skips_run_source` — `run_id == ""` → the run-log source is skipped, no crash.
- `test_code_reveals_split_fingerprint_transition_is_acted_on` — a `code-reveals-split` at P with a later snapshot at P′ where the flagged step's region is gone → `acted-on`.
- `test_no_fingerprint_transition_is_still_open` — same flagged focus but the latest snapshot still at P (or the region still recurring) → `still-open`.
- `test_region_resolved_then_reappears_is_reverted` — the flagged region disappears after P then returns → `reverted`.
- `test_no_matching_region_is_no_op` — a decision whose focus never matches any region → `no-op`.
- `test_async_resolver_returns_none_when_no_evidence` — no run outcome and no history → `None` (caller falls back to unresolved).
- `test_async_reuses_convergence_matcher_focus` — the focus keys via `_normalized_focus` / `_step_token` (e.g. a `step5-…` anchor resolves to step 5), proving no second matcher.

**Top-level reader (`resolve_decisions`):**
- `test_resolve_decisions_marks_async_rows` — over a mixed log, a joinable non-inline event gets `resolution == "async"` with an `OUTCOME_*` verdict; inline families stay `resolution == "inline"`.
- `test_resolve_decisions_unjoinable_stays_unresolved` — an ownerless / `plan_slug==""` / `run_id==""` event that joins to nothing stays `resolution == "unresolved"` / `outcome == "still-open"`.
- `test_resolve_decisions_loads_history_once_per_slug` — a spy/stub on the history loader is called once per distinct `plan_slug`, not once per event.
- `test_resolve_decisions_tolerates_missing_plan_path` — a slug not in the manifest → history skipped, event resolves (to unresolved) rather than raising.
- `test_resolve_decisions_still_one_row_per_event` — output length equals input event count (the per-event contract step 4 depends on).
- `test_telemetry_analysis_does_not_import_cli` — still green with the four new leaf imports; asserts no `plan_tool.cli` reference.

**Integration (the §7 smoke test) — `@pytest.mark.integration`:**
- `test_smoke_code_reveals_split_leads_to_split_is_acted_on` — seed a real scenario on `tmp_path`: record a `code-reveals-split` decision at fingerprint P (via `telemetry.record_code_reveals_split`), write the plan's saved sidecars so a later report at P′ shows the flagged step became two steps, then assert `resolve_decisions(repo_root)` emits `acted-on` for that decision. This drives telemetry + sidecar (+ run-log where present) together, so it belongs in the integration tier per the plan's Testing section.

### Test-creation order (feature step)

This is a **feature** step — new behavior. Write each derivation test alongside `resolve_decision_async`, each reader test alongside the rewritten `resolve_decisions` branch, and the §7 smoke test last (it exercises the whole chain). Green-before-done gate: every new test above must pass (`uv run pytest tests/test_telemetry_analysis.py -q`, and the integration marker included) before this step is considered finished.

## Acceptance criteria

- `resolve_decision_async(event, *, run_outcome, history)` returns an `(outcome, evidence)` for a joinable non-inline decision and `None` when neither source joins; `outcome` is one of `OUTCOME_ACTED_ON` / `OUTCOME_NO_OP` / `OUTCOME_REVERTED` / `OUTCOME_STILL_OPEN`.
- The async source is the only path that can emit `OUTCOME_REVERTED` (a region resolved-then-recurring).
- `resolve_decisions(repo_root)` marks joined non-inline rows `RESOLUTION_ASYNC` and leaves unjoinable rows `RESOLUTION_UNRESOLVED` / `still-open`; it still returns exactly one `ResolvedDecision` per event.
- The plan's history is loaded at most once per distinct `plan_slug` across the event loop.
- An event with `run_id == ""`, `plan_slug == ""`, or a slug missing from the manifest resolves without raising (falls back to unresolved).
- The join reuses `convergence_diagnosis.py`'s matcher primitives — no new focus/similarity matcher is added to `telemetry_analysis.py`.
- `plan_tool/telemetry_analysis.py` imports `run_log`, `convergence_diagnosis`, `review_persistence`, `locator` at module top and **no** `plan_tool.cli` (asserted by the boundary test).
- The §7 integration smoke test passes: `code-reveals-split` at P → split → sidecar at P′ → `acted-on`.
- `uv run pytest tests/test_telemetry_analysis.py -q` is green (unit and integration).

## References

- [difflib — Helpers for computing deltas (Python 3.13)](https://docs.python.org/3/library/difflib.html) — `SequenceMatcher.ratio()`, the basis for the reused fuzzy title tier (`TITLE_SIMILARITY_CUTOFF = 0.85`) in `convergence_diagnosis.py`.
- [dataclasses — Data Classes (Python 3.13)](https://docs.python.org/3/library/dataclasses.html) — `@dataclass(frozen=True)` for any new frozen record and for reading `RunOutcome` / `ReportHistory` values.
- [json — JSON encoder and decoder (Python 3.13)](https://docs.python.org/3/library/json.html) — context for how the run-log and decision JSONL this join reads is parsed by the step-1 reader and `read_decisions`.
- [JSON Lines format specification](https://jsonlines.org/) — the newline-delimited format of both the decision log and the run-log JSONL streamed on the join.

## Deferred

- **Aggregation across plans by `kind`/`decision`** and the advisory tuning recommendations — step 4 (depends on 3).
- **The `plan-tool telemetry` command** wiring the leaf (`cli/telemetry_cmd.py`, `--json`) — step 5.
- **Persisting derived verdicts as a cache sidecar** — design decision #4 defaults to compute-on-read; a cache lands only if a later step proves it necessary, and would own the `DATA_CONTRACT.md` drift-guard work.
- **Time-windowing / capping the log or history read** — added only if a full `read_decisions` + per-slug `load_report_history` proves too slow (plan Deferred).
- **Emitting `IterationEnd` run-log events** — no producer writes them today, so the per-step run-log outcome map stays empty; this step reads what exists and does not add an emitter (owned by whatever step wires per-step run-log outcomes, if ever).
- **Richer run-outcome verdicts** — beyond `completed` + `RunEnd.outcome`/`rc`; deferred until a producer emits per-step run signal.
