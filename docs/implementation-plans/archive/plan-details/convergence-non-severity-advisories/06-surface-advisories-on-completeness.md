> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Surface advisories on completeness-audit stderr when history is sufficient

## Summary

After a run-grade completeness audit persists a new sidecar, load saved report history from disk, run `diagnose_convergence`, and print only the impact-recurrence and edit-drift advisory lines to stderr — reusing step 5’s `_impact_recurrence_lines` / `_edit_drift_lines`, not the full `render_diagnosis` headline block. Touch `plan_tool/cli/completeness_cmd.py` and `tests/cli/test_completeness_cmd.py` only. The main design choice is to hook this in `finalize_completeness_run` immediately after `_persist_and_present_report` returns, gated on a sidecar actually being written this run, so the window’s newest pass is the audit that just finished. When green, operators see the same recommend-only warnings `plan-tool convergence` would show, without a second command and without spending Claude; exit code, `stop_reason`, and `--fail-on-findings` stay unchanged.

## Table of Contents

- [Summary](#summary) — what changes and what stays the same
- [Why](#why) — why completeness stderr needs the advisories
- [Input](#input) — upstream contracts this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — paths touched
- [Implementation](#implementation) — hook point, gating, and output shape
- [Tests](#tests) — cases and green gate
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — docs and symbols to read first
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — explicitly out of scope here

## Why

Step 5 makes impact-recurrence and edit-drift visible on `plan-tool convergence`, but operators who stop after `completeness-audit` never see those signals unless they run a second command. The classifiers only need persisted sidecar history — `load_report_history` is cheap and spends no Claude — and the plan requires the evaluation window to treat the just-finished audit as the newest pass. Wiring stderr output into the completeness tail closes that gap without duplicating classifier logic or touching iterate stop reasons.

## Input

**From step 5:** `ConvergenceDiagnosis.impact_recurrence` and `ConvergenceDiagnosis.edit_drift` populated by `diagnose_convergence`; private render helpers `_impact_recurrence_lines` and `_edit_drift_lines` in `plan_tool/convergence_diagnosis.py` (names per step 5’s land). Do **not** print full `render_diagnosis` output — that includes the convergence headline, series breakdown, churn, structural recurrence, and run-readiness blocks completeness stderr does not need.

**History load path:** `load_report_history(path)` → `diagnose_convergence(history, audit_stage=..., classify_domain=...)` — same call shape as `plan_tool/cli/convergence_cmd.py:cmd_convergence`, using the `audit_stage` `finalize_completeness_run` already received from `cmd_completeness` (hoisted from `derive_audit_stage`).

**From step 5 / CLI (read-only timing context):** `plan_tool/cli/completeness_cmd.py:finalize_completeness_run` is the shared tail; persist timing lives in `plan_tool/cli/completeness_phases.py:_persist_and_present_report` (not in this step’s `files:`).

**Sidecar suppression (existing):** jira grade (`detail_grade == GRADE_JIRA`) writes no sidecar — no history, no advisories (same as `_warn_sidecar_suppressed`’s contract). Audit-only `--reuse-audit` sets `skip_sidecar_write=True` when `not budget.enabled` — no new final this run, so do not claim the just-completed pass as newest.

**What this step does not verify:** classifier correctness (steps 3–4); convergence headline accuracy; telemetry payloads; `docs/AUDIT_FLOW.md` prose updates (step 7).

## Files (creates vs edits)

- **New files:** none

- **Existing files (edits only):**
  - `plan_tool/cli/completeness_cmd.py` — add a small stderr emitter (e.g. `_emit_convergence_loop_advisories`); call it from `finalize_completeness_run` after `_persist_and_present_report`; pass through `audit_stage`, `detail_grade`, and whether a sidecar was persisted this run.
  - `tests/cli/test_completeness_cmd.py` — integration cases seeding sidecar history that fires each advisory; stderr substring assertions; non-interference case for exit code / `stop_reason` / `--fail-on-findings`; jira-grade and reuse skip guards.

## Implementation

### Behavior change

Operators running run-grade `completeness-audit` (audit-only or `--iterate`) may see zero, one, or two `⚠` advisory blocks on **stderr** after the report is saved, when saved history is enough for step 3/4 classifiers to fire. Nothing in the grouped report, JSON payload, blocking gates, or iterate loop reads these fields.

### Recommended hook point

**`finalize_completeness_run`** in `plan_tool/cli/completeness_cmd.py` — the shared tail for audit-only and iterate (including halt paths that still persist). Call the emitter **after** `_persist_and_present_report(...)` returns and **before** `--commit`, `early_exit_code`, and `--fail-on-findings` handling so presentation cannot influence rc computation.

Capture `_persist_and_present_report`’s return value (`report_path`) to know the write succeeded.

**Rejected alternative:** emit from `plan_tool/cli/completeness_phases.py:_persist_and_present_report`. That module is out of this step’s file list; the orchestration decision (when history is sufficient, which grade, reuse skip) already lives in `finalize_completeness_run`.

**Rejected alternative:** print full `render_diagnosis(diagnosis)` on stderr. Too noisy and duplicates convergence output the operator did not ask for; step 5 split line builders for this reuse.

### Gating (all must pass to emit)

- **`detail_grade` is run grade** — skip at jira grade (no sidecar, no `load_report_history` signal for this run).
- **Sidecar persisted this run** — `skip_sidecar_write` was false **and** `report_path is not None`. When audit-only reuse skips the sidecar write, skip emission (no new newest pass; showing stale-only history would violate the plan’s “includes the just-completed pass” acceptance).
- **At least one advisory populated** — after `diagnose_convergence`, print only when `impact_recurrence` and/or `edit_drift` is not `None`.

When gating fails, emit nothing (no “insufficient history” stub — that remains `plan-tool convergence`’s job).

### Diagnosis call

Mirror `cmd_convergence`:

```python
history = load_report_history(path)
diagnosis = diagnose_convergence(
    history,
    audit_stage=audit_stage,
    classify_domain=lambda f: f.domain or "unknown",
)
```

- Pass the **live** `audit_stage` from `finalize` (same bar as the report’s conceptual gate) — classifiers still read **persisted** `audit_stage` from sidecars internally (step 3/4 contract).
- Do **not** thread `diagnosis` into `_completeness_has_blocking_findings`, `compute_conceptual_bar_blocking_ids`, `should_continue`, `ConvergenceState`, or `_run_iterate_convergence_loop` stop logic.

### Stderr output shape

For each populated advisory, extend the corresponding line list from step 5 and print every line to stderr:

- Use `print(line, file=sys.stderr)` (or equivalent) — lines already carry `⚠` from the render helpers; do **not** wrap each line in `plan_tool.style.warn` (that adds a second `warning:` prefix).
- Print impact-recurrence before edit-drift when both fire (same order as `render_diagnosis`’s loop-signal block).
- No extra banner like `convergence:` — the prose is self-describing.

Optional thin wrapper in `completeness_cmd.py` that imports `_impact_recurrence_lines` / `_edit_drift_lines` and returns `list[str]` keeps `finalize` readable; do not duplicate advisory prose in the CLI module.

### Paths that do not emit

- **`--json` branch** — `finalize_completeness_run` returns before `_persist_and_present_report` today, so no new sidecar and no “just-completed” newest pass. Do not add emission on the JSON early-return path in this step.
- **Jira grade** — suppressed with the sidecar.
- **Audit-only `--reuse-audit`** — `skip_sidecar_write=True` → gated off.
- **Failed report write** — `report_path is None` → gated off.

### Invariants

- Advisory emission is **presentation-only** — no new imports of `plan_tool.cli` inside `convergence_diagnosis.py`.
- No changes to `plan_tool/cli/completeness_phases.py`, `convergence_cmd.py`, classifiers, or `is_blocking_*` predicates.
- `rg 'spinning|FORK_|RegionTrend|classify_fork|recurring_regions' plan_tool/cli/completeness_cmd.py` introduces no new production matches beyond pre-existing comments.
- Iterate `stop_reason`, `outcome.early_exit_code`, and `_completeness_finalize_is_clean` inputs are computed exactly as before this emitter runs.

### Shared locations (read-only / out of footprint)

| Location | This step | Reason |
|---|---|---|
| `plan_tool/convergence_diagnosis.py` | No edit (step 5) | Line builders and `diagnose_convergence` wiring land in step 5 |
| `plan_tool/cli/convergence_cmd.py` | No edit | Already prints via `render_diagnosis` |
| `plan_tool/cli/completeness_phases.py` | No edit | Out of declared `files:` list; hook stays in `finalize_completeness_run` |
| `docs/AUDIT_FLOW.md` | Deferred — step 7 | Flow doc still says the report does not embed convergence diagnosis |

## Tests

### Tests for this step

Every test below must be green before this step is finished. All pre-existing `tests/cli/test_completeness_cmd.py` cases must stay green.

**Fixture pattern:** seed two (or more) prior completeness finals under `plan_reports_dir(plan_path)` via `save_review` / `write_completeness_report` (reuse helpers from `tests/cli/test_convergence_cmd.py:_save` or local equivalents with `audit_stage`, `impact`, and annotations as needed). Stub `plan_tool.review.audit_plan_until_stable` (and deterministic checks if needed) so the third `main(["completeness-audit", ...])` completes quickly and writes a third sidecar. Assert on `capsys.readouterr().err`.

**`tests/cli/test_completeness_cmd.py`**

- `test_completeness_stderr_prints_impact_recurrence_when_history_fires` — three compatible run-grade finals including the live audit → stderr contains impact-recurrence distinctive substring (e.g. high-impact seam / `⚠` line from step 5); rc 0.
- `test_completeness_stderr_prints_edit_drift_when_history_fires` — history fixture that fires edit-drift → stderr contains edit-drift distinctive substring; rc 0.
- `test_completeness_stderr_prints_both_advisories_when_both_fire` — combined fixture → both substrings on stderr.
- `test_completeness_stderr_silent_when_classifiers_do_not_fire` — fewer than three compatible passes or disqualifying history → stderr lacks both advisory substrings (no false positive).
- `test_completeness_stderr_skips_advisories_on_jira_grade` — `--grade jira` clean audit → no impact-recurrence / edit-drift advisory text on stderr (sidecar suppressed).
- `test_completeness_stderr_skips_when_sidecar_not_written` — audit-only `--reuse-audit` with fresh fingerprints → reuse path skips sidecar write → no new advisory emission attributable to this run (substring absent or unchanged from pre-run).
- `test_completeness_advisories_do_not_change_exit_code` — history fires advisory; audit returns no blocking findings → rc 0 with and without advisory-eligible history; with `--fail-on-findings` still rc 0 when findings are clean.
- `test_completeness_advisories_do_not_change_iterate_stop_reason` — `--iterate` run with seeded history that fires advisory but deterministic/conceptual loop converges → `stop_reason` matches the no-advisory control (same fixture without third pass seeded, or advisory lines stubbed to empty while diagnosis otherwise runs — pick one stable approach).
- `test_completeness_advisories_do_not_change_audit_only_rc` — audit-only run with seeded history that fires advisory → exit code and `--fail-on-findings` outcome match the no-advisory control.

Prefer driving `plan_tool.cli.main` through `registered_plan.argv(...)` for integration fidelity; direct `finalize_completeness_run` unit tests are optional if the `main` cases cover the hook.

**Green-before-done gate:** `uv run pytest tests/cli/test_completeness_cmd.py -q` (or the project’s parallel equivalent).

## Acceptance criteria

- After a successful run-grade sidecar write in `finalize_completeness_run`, stderr shows impact-recurrence text when step 3’s classifier fires on history that includes the just-written final as newest.
- Same path shows edit-drift text when step 4’s classifier fires under the same rule.
- Emission uses `_impact_recurrence_lines` / `_edit_drift_lines` (or a thin local wrapper around them), not full `render_diagnosis`.
- No emission on jira grade, when `skip_sidecar_write` prevented a new final this run, or when `report_path` is `None`.
- No emission on the `--json` early-return path in `finalize_completeness_run`.
- `completeness-audit` exit code, `--fail-on-findings`, and iterate `stop_reason` are unchanged when advisories print (covered by non-interference tests).
- Advisory stderr does not appear in grouped report markdown or `--json` payload.
- `rg 'diagnosis\.(impact_recurrence|edit_drift)' plan_tool/cli/completeness_cmd.py` shows use only in the stderr emitter, not in blocking or iterate gate paths.

## References

- [`docs/implementation-plans/2-convergence-non-severity-advisories.md`](docs/implementation-plans/2-convergence-non-severity-advisories.md) — step 6 intent, acceptance criteria, non-interference fence.
- [`docs/implementation-plans/plan-details/convergence-non-severity-advisories/05-wire-both-advisories-diagnose.md`](docs/implementation-plans/plan-details/convergence-non-severity-advisories/05-wire-both-advisories-diagnose.md) — `ConvergenceDiagnosis` fields, line builders, `render_diagnosis` ordering.
- [`docs/AUDIT_FLOW.md`](docs/AUDIT_FLOW.md) — sidecar persistence, checkpoint exclusion, standalone `plan-tool convergence` (step 7 updates stderr integration prose).
- [`DATA_CONTRACT.md`](DATA_CONTRACT.md) — persisted `audit_stage`, `impact`, disposition fields the classifiers read.
- `plan_tool/cli/completeness_cmd.py` — `finalize_completeness_run`, `_warn_sidecar_suppressed`, `skip_sidecar_write` wiring.
- `plan_tool/cli/completeness_phases.py` — `_persist_and_present_report`, `write_completeness_report` (read-only for timing).
- `plan_tool/cli/convergence_cmd.py` — `cmd_convergence`, `_current_audit_stage` (call-shape precedent).
- `plan_tool/convergence_diagnosis.py` — `load_report_history`, `diagnose_convergence`, `_impact_recurrence_lines`, `_edit_drift_lines`.
- `plan_tool/style.py` — `warn` / stderr conventions (contrast: do not double-prefix advisory lines).

## Applicable guardrails

- **Plan intent (recommend-only advisories):** stderr is presentation only — no `stop_reason`, `--fail-on-findings`, or exit-code changes; no plan mutation.
- **Step intent:** surface advisories during `completeness-audit` when history is already on disk after persist; newest pass is the run that just finished.
- **Out of scope — loop control:** do not connect advisories to `should_continue`, iterate halt reasons, or reconcile loops.
- **Out of scope — retired vocabulary:** no `spinning`, `FORK_*`, or region-trending strings in new stderr copy (reuse step 5 render text unchanged).
- **Out of scope — automatic remedies:** stderr must not auto-invoke split, scope-out, or re-seed.
- **Out of scope — hard exit / provenance:** no `#231` provenance or loop-terminating edit-drift exit.

## Deferred

- `docs/AUDIT_FLOW.md` and `CLAUDE.md` convergence policy prose — `AUDIT_FLOW` is plan-Deferred post-ship doc work (not step 7); `CLAUDE.md` is step 7.
- `--json` completeness path emitting advisories — carve-out in plan acceptance; would need persisting before the JSON return or accepting history without the just-finished pass; not in this step’s file list.
- `record_convergence` telemetry fields for advisory payloads — not required for stderr visibility.
- Embedding advisories in the grouped markdown report or `console_summary` stdout — stderr only per plan architecture.
- Moving the hook into `plan_tool/cli/completeness_phases.py` — out of declared footprint; reconcile if duplication becomes painful.
