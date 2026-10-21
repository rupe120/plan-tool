> **Auto-archived**: this plan was swept on 2026-07-08 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Compute the convergence diagnosis in `_persist_and_present_report` and count the current run exactly once

## Summary

Wire the spinning-loop convergence section (step 3) into the completeness report by computing a `ConvergenceDiagnosis` inside `plan_tool/cli/completeness_phases.py:_persist_and_present_report` and passing it to `build_report_md` through step 3's `convergence_diagnosis=` parameter. The one hard thing is run-counting: one iterate invocation writes **two** `kind="completeness"` sidecars — the pre-apply checkpoint (`write_pre_apply_audit_checkpoint`) and the final report — and `load_report_history` returns both, so a naive load makes this invocation look like two runs and can mis-fire the spinning verdict. The step must count the current run **exactly once** across both code paths: the fresh-write audit-only run (current run only in memory) and the iterate run (current run partly already on disk as the checkpoint). On green: a spinning completeness loop renders the "loop is spinning" section in its report, a converging/healthy loop renders unchanged, and the diagnosis handed to `build_report_md` reflects the current run once — never zero, never twice.

## Table of Contents

- [Why](#why) — a silently spinning completeness loop needs an in-report signal, and the report is the natural place
- [Input](#input) — the saved report history and step-3 renderer this step consumes
- [Files (creates vs edits)](#files-creates-vs-edits) — one module edit plus its test file
- [Implementation](#implementation) — where to compute the diagnosis, and the count-once rule
- [Tests](#tests) — the run-counting and section-gating cases to add
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes on green
- [References](#references) — the Python/pytest docs relevant to this seam
- [Deferred](#deferred) — the shared snapshot-flattening helper and other-command surfaces

## Why

A completeness audit/apply loop can spin — re-surface the same over-packed region across runs with no shrinkage — and today the report says nothing. The operator only learns the loop is stuck by running the separate `plan-tool convergence <name>` command, which most never think to do mid-loop. Step 3 built the pure half of the fix: `render_convergence_section` in `plan_tool/completeness_report.py`, gated to emit only on `VERDICT_SPINNING`, plus an optional `convergence_diagnosis` parameter on `build_report_md` that defaults to `None` and leaves the report unchanged. This step supplies the missing half — computing the diagnosis and threading it into the report — so the report gains the section automatically whenever the loop is spinning. The design subtlety this step owns, called out in the plan's step-4 risk, is counting the current run exactly once: a double-count or a miss skews the recurrence/no-shrinkage trend and either mis-fires or suppresses the spinning verdict.

## Input

This step consumes two existing contracts and defines no new schema.

- **Saved report history — `load_report_history(plan_path)` / `ReportHistory` / `RunSnapshot`** (`plan_tool/convergence_diagnosis.py`). `load_report_history` reuses `list_saved_reviews` / `load_review`, keeps only reviews whose `kind` is in `HISTORY_KINDS` (`completeness`, `detail-reconcile`, `run-reconcile`), flattens each to a `RunSnapshot`, and returns them sorted oldest→newest. `diagnose_convergence(history)` turns that into a `ConvergenceDiagnosis` (its `verdict` is one of the four `VERDICT_*` constants). Key fact for correctness: **every `kind="completeness"` sidecar under the plan's reports dir becomes one `RunSnapshot`**, including this invocation's own pre-apply checkpoint.
- **Step 3's renderer hook.** Step 3 owns `plan_tool/completeness_report.py:render_convergence_section(diagnosis)` (returns `""` unless `diagnosis.verdict == VERDICT_SPINNING`) and the `build_report_md(..., convergence_diagnosis=None)` parameter that places the rendered section at its fixed slot. This step passes a computed diagnosis into that parameter and does **no** rendering of its own — the fork/remedy prose stays single-sourced in `render_diagnosis`.

Verification limit: the diagnosis reads only the persisted recommendation/annotation/fingerprint subset, so a count-once test is best driven by seeding real sidecars on disk (via `plan_reports_dir` / `write_completeness_report`) and inspecting the diagnosis handed to `build_report_md`, rather than by mocking history internals.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/completeness_phases.py` — in `_persist_and_present_report`, compute the `ConvergenceDiagnosis` once and pass it as `build_report_md(..., convergence_diagnosis=…)`; add the count-once logic. Because `write_pre_apply_audit_checkpoint` delegates to this same `_persist_and_present_report`, add a guard so the checkpoint call suppresses the diagnosis (e.g. a new keyword param on `_persist_and_present_report`, set by that caller alongside the existing `quiet_presentation`), leaving exactly one call site — the final report — that computes the diagnosis.
  - `tests/cli/test_completeness_cmd.py` — add cases under the existing `_persist_and_present_report` test group covering count-once on both the fresh-write and iterate paths, plus the spinning-vs-healthy section gate.

## Implementation

**What changes.** `_persist_and_present_report` currently builds the report with `build_report_md(...)` (no convergence input) and then writes the sidecar. This step computes a `ConvergenceDiagnosis` before that `build_report_md` call and passes it through step 3's `convergence_diagnosis=` parameter. When the loop is spinning the report gains the section; otherwise step 3's renderer returns `""` and the report is unchanged.

**Scope the diagnosis to the completeness series.** The completeness report's section reflects only the *completeness* loop, not `diagnose_convergence`'s plan-wide worst-of headline across the `detail-reconcile` / `run-reconcile` series. A reconcile-series spin must not render the section in a completeness report (that spin is the standalone `plan-tool convergence` command's job). So the diagnosis this step hands to `render_convergence_section` must gate on the completeness series' verdict alone — e.g. restrict the loaded history to `kind="completeness"` snapshots (plus the in-memory current run) before `diagnose_convergence`, so its worst-of collapses to the completeness series. Achieve this without touching `convergence_diagnosis.py` (per out-of-scope): filter the `ReportHistory.runs` in the CLI layer. A spinning `detail-reconcile` / `run-reconcile` series with a converging completeness series must leave the completeness report unchanged.

**Where to compute it.** Do it inside the `if not skip_sidecar_write:` block, right before the existing `build_report_md(...)` call (the fresh-write branch that rebuilds the report). `path` and `ctx.repo_root` are already in scope there, but the `sidecar_recs` / `plan_fp` / `code_fp` locals the write uses are computed *after* `build_report_md` (inside the inner `try`), so to reuse them for the current-run snapshot you must **hoist** their computation above the `build_report_md(...)` call — the diagnosis needs them before the report is built, and the write below then reuses the hoisted values. Note that `write_pre_apply_audit_checkpoint` reaches this same block (it delegates to `_persist_and_present_report` without `skip_sidecar_write`), so gate the diagnosis computation on the checkpoint-suppression guard (below) — compute it only on the final, non-checkpoint call. In the `skip_sidecar_write` reuse branch `build_report_md` never runs, so there is nothing to wire; leave it alone.

**The count-once rule — the key decision.** `load_report_history(path)` returns one `RunSnapshot` per on-disk `kind="completeness"` sidecar. That creates two hazards this step must close:

- **Double-count (iterate path).** `write_pre_apply_audit_checkpoint` already wrote a `kind="completeness"` sidecar for *this* invocation before the loop. At the final `_persist_and_present_report`, `load_report_history` returns that checkpoint **and** — if you also add the about-to-be-written final — the same invocation appears twice.
- **Miss (audit-only fresh path).** A non-iterate run writes no checkpoint, so the current run is only in memory. Load history and it is absent — the run that triggered the report is not in its own diagnosis.

Recommended approach — **count the current run through exactly one representation:**

1. Compute the diagnosis at **one** call site. `write_pre_apply_audit_checkpoint` does not call `build_report_md` itself — it delegates to this same `_persist_and_present_report`, so both the checkpoint and the final report enter the `if not skip_sidecar_write:` block. Add a guard so the checkpoint delegation suppresses the diagnosis (e.g. a new keyword param on `_persist_and_present_report`, set by the checkpoint caller alongside the `quiet_presentation=True` it already passes), leaving only the final report to compute a diagnosis. This keeps the section out of the rarely-read checkpoint report and localizes the count-once logic to one place.
2. Load `history = load_report_history(path)`.
3. Add the current run **once** by loading history and appending a single in-memory `RunSnapshot` built from `sidecar_recs` (the same list the write persists) plus `plan_fp` / `code_fp` as the current run, and **always drop this invocation's own earlier checkpoint** so it is never also counted (e.g. the newest same-plan sidecar written in this process) — the checkpoint-drop is required because on the iterate path the checkpoint sidecar stays on disk. The diagnosis is computed **before** `build_report_md` from this loaded-history-plus-in-memory-current-run set, so it embeds in the single report the write persists. Reloading history *after* the final write is not viable: `build_report_md` consumes the diagnosis and runs before the write, so a post-write reload cannot reach that report without a second build+write. The invariant is one snapshot per invocation, checkpoint always excluded.

**Known limit — the count-once rule is scoped to the current invocation only.** The checkpoint-drop above removes only *this* invocation's own earlier checkpoint. `load_report_history` still returns both the pre-apply checkpoint and the final sidecar for every *prior* iterate run (both are `kind="completeness"`), so the shared trend baseline stays uneven: each past iterate run counts twice, each audit-only run once, and a past invocation's checkpoint-then-final can read as an artificial recurrence-then-shrink. This is an accepted residual, not a regression this step introduces — the same skewed history feeds the standalone `plan-tool convergence` command. The clean fix is a per-invocation checkpoint+final dedup inside `load_report_history`, which lives in `convergence_diagnosis.py`, outside this step's declared files and the plan's out-of-scope for that leaf; see [Deferred](#deferred).

Constraints and gotchas a developer must respect:

- **Never render here.** Only `render_convergence_section` (step 3) may turn a spinning verdict into markdown; this step passes the diagnosis object and nothing more. Do not inline the `"spinning"` literal or re-derive the remedy line.
- **Default must stay inert.** A converging / insufficient-history / no-history verdict must leave the report exactly as it is today. Step 3's renderer already returns `""` for those, so passing a non-spinning diagnosis is safe — but the existing `_persist_and_present_report` tests (`test_writes_report_and_returns_path`, `test_persist_passes_union_and_fingerprints`, …) must stay green unchanged.
- **Reuse the write's own values.** Build the in-memory snapshot's findings from `sidecar_recs` and its fingerprints from the same `plan_fp` / `code_fp` the write uses, so the current run's counted data matches what lands on disk for the next run's diagnosis. A `RunSnapshot` needs `report_bytes`; the final `report_md` size is not known before `build_report_md` runs, so an approximate value is acceptable — the current run's contribution to the verdict is its findings and fingerprints, not an exact byte count.
- **Do not touch the diagnostic leaf.** Per the plan's out-of-scope, do not change `convergence_diagnosis.py`'s inputs, fork classification, or trend heuristics; this step only computes and threads the existing diagnosis.

**Shared logic to note.** Flattening a `SavedReview` (or a recommendation list) into a `RunSnapshot` already lives in `plan_tool/convergence_diagnosis.py:_snapshot_from_saved_review` / `_finding_from_recommendation`. Building an in-memory current-run snapshot from `sidecar_recs` in `completeness_phases.py` re-implements that flattening. If you take the in-memory-append route, keep the duplication small and local; a clean fix is a shared public constructor (e.g. `snapshot_from_recommendations(...)`) in `convergence_diagnosis.py`, but that file is outside this step's declared list — see [Deferred](#deferred).

## Tests

Add cases to `tests/cli/test_completeness_cmd.py`, in the existing test group that drives `_persist_and_present_report` directly (keeps `build_report_md` real, spies only the write seam on `plan_tool.completeness_report`). Seed prior runs by writing real `kind="completeness"` sidecars under `plan_reports_dir(path)` (via `write_completeness_report`) so `load_report_history` reads them. Spy on `plan_tool.completeness_report.build_report_md` to capture the `convergence_diagnosis` kwarg when a test needs to inspect the run count.

### Test-creation order (feature step)

This is a **feature** step. Add these unit tests with the implementation; each must be green before the step is done.

- `test_spinning_history_renders_convergence_section` — with seeded spinning prior runs plus this run, the persisted report contains the step-3 section (assert a stable marker from `render_diagnosis`).
- `test_converging_history_renders_no_section` — a healthy/converging history leaves the report unchanged (no section marker); default output matches the pre-step-4 report.
- `test_current_run_counted_once_audit_only` — fresh non-iterate run (no checkpoint on disk): the diagnosis handed to `build_report_md` includes the current run exactly once (not missed).
- `test_current_run_counted_once_iterate_after_checkpoint` — a pre-apply checkpoint sidecar for this invocation already on disk: the current run is counted once, not twice (the invocation's checkpoint + final collapse to one run).
- `test_checkpoint_call_renders_no_section` — the `write_pre_apply_audit_checkpoint` path suppresses the diagnosis via its guard param, so the checkpoint report renders no convergence section and only the final report computes the diagnosis.
- `test_no_history_renders_no_section` — empty reports dir yields a no-history verdict and no section; report unchanged.
- `test_reconcile_series_spin_renders_no_section` — a spinning `detail-reconcile` / `run-reconcile` series with a converging completeness series renders no section (scoping to the completeness series, not the plan-wide worst-of).
- Existing `_persist_and_present_report` cases stay green unchanged (default wiring preserves current output and the fingerprint/union persistence).

Green-before-done gate: all new cases above and the whole existing `_persist_and_present_report` group pass before the step is considered finished.

## Acceptance criteria

- `_persist_and_present_report` computes a `ConvergenceDiagnosis` and passes it to `build_report_md` via `convergence_diagnosis=` on the fresh-write path.
- A spinning completeness loop's persisted report contains the convergence section; a converging / insufficient-history / no-history loop's report is unchanged from before this step.
- The diagnosis handed to `render_convergence_section` gates on the completeness series alone, not `diagnose_convergence`'s plan-wide worst-of; a spinning `detail-reconcile` / `run-reconcile` series with a converging completeness series renders no section — asserted by `test_reconcile_series_spin_renders_no_section`.
- The diagnosis handed to `build_report_md` counts the current audit run exactly once on both the audit-only (in-memory) path and the iterate (checkpoint-already-on-disk) path — asserted by `test_current_run_counted_once_audit_only` and `test_current_run_counted_once_iterate_after_checkpoint`.
- The pre-apply checkpoint call renders no convergence section and does not cause its invocation to be counted twice.
- No rendering logic is added to `completeness_phases.py`; the section text comes only from step 3's `render_convergence_section` / `render_diagnosis`.
- `convergence_diagnosis.py` is unchanged (no edits to its inputs, fork classification, or heuristics).
- The existing `_persist_and_present_report` tests pass unchanged, and the new `test_completeness_cmd.py` cases are green.

## References

- `plan_tool/convergence_diagnosis.py` — `load_report_history(plan_path)` (one `RunSnapshot` per on-disk `kind="completeness"` sidecar, the fact the count-once rule turns on) and `diagnose_convergence(history) -> ConvergenceDiagnosis`; the contract this step computes and threads into the report.
- `plan_tool/completeness_report.py` — step 3's `render_convergence_section(diagnosis)` (returns `""` unless `VERDICT_SPINNING`) and the `build_report_md(..., convergence_diagnosis=None)` parameter this step passes the computed diagnosis into; rendering stays single-sourced there, never here.

## Deferred

- **A shared `snapshot_from_recommendations(...)` constructor in `convergence_diagnosis.py`** — if the in-memory current-run snapshot re-implements `_snapshot_from_saved_review` / `_finding_from_recommendation`, consolidating that flattening into one public constructor is the clean fix, but it edits a file outside this step's declared list; route to reconcile rather than expanding this step's footprint.
- **Surfacing the convergence section in reconcile or other report-producing commands** — the plan scopes the in-report projection to the completeness report only.
- **Actuating any fork from this surface** — this step is a read-only projection; `--apply-split` / `--apply-scope-out` actuation lives in `plan-tool convergence` (steps 1–2).
- **Changing `convergence_diagnosis.py`'s trend heuristics or `HISTORY_KINDS`** — out of scope; this step consumes the existing diagnosis and history contract as-is.
- **Deduping prior invocations' checkpoint+final in shared history** — this step counts only the current run once; collapsing each *past* iterate run's checkpoint and final into one `RunSnapshot` belongs in `load_report_history` (`convergence_diagnosis.py`), outside this step's files and the plan's out-of-scope for that leaf. Route to a dedicated diagnostic change.
