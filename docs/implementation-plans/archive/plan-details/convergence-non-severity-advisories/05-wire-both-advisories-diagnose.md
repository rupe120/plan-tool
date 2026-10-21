> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Wire both advisories into diagnose_convergence and render_diagnosis

## Summary

Extend `ConvergenceDiagnosis` with optional `impact_recurrence` and `edit_drift` fields, call `classify_impact_recurrence` and `classify_edit_drift` from `diagnose_convergence`, and render both through new line builders in `render_diagnosis` using the same `⚠` advisory pattern as `finding_churn` and `structural_recurrence`. Touch `plan_tool/convergence_diagnosis.py`, `tests/test_convergence_diagnosis.py`, and `tests/cli/test_convergence_cmd.py`. The main design choice is to treat these as recommend-only signals on the diagnosis object — same as churn and structural recurrence — not as inputs to verdict roll-up or run-readiness logic. When green, `plan-tool convergence` prints both warnings on histories that fire the step 3/4 classifiers, still exits 0, and leaves the headline verdict and existing advisories unchanged.

## Table of Contents

- [Summary](#summary) — what changes and what stays the same
- [Why](#why) — why wiring lands after the classifiers
- [Input](#input) — upstream classifier contracts this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — paths touched
- [Implementation](#implementation) — diagnosis fields, diagnose wiring, render helpers
- [Tests](#tests) — cases and green gate
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — docs and symbols to read first
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — explicitly out of scope here

## Why

Steps 3 and 4 ship deterministic classifiers that return frozen `ImpactRecurrenceAdvisory` and `EditDriftAdvisory` records, but they deliberately leave `diagnose_convergence` and `render_diagnosis` untouched so classifier tests stay isolated. Operators still get no signal: `plan-tool convergence` only shows the three-state verdict, run-readiness blocking/drift, finding churn, and structural recurrence. This step connects classifier output to the CLI print path so severity-clean convergence is no longer the only visible exit signal — without changing iterate stop reasons, exit codes, or the headline verdict.

## Input

**From step 3:** `classify_impact_recurrence(history, *, window=WINDOW_SIZE) -> ImpactRecurrenceAdvisory | None` — reads collapsed completeness passes internally via `build_collapsed_completeness_passes`; eligibility and window stage come from **persisted** `audit_stage` on saved sidecars, not the live `audit_stage` argument `diagnose_convergence` already takes for `_finding_churn`.

**From step 4:** `classify_edit_drift(history, *, window=WINDOW_SIZE, classify_domain=...) -> EditDriftAdvisory | None` — same history input; `classify_domain` must match the callable shape `_open_medium_plus` accepts (e.g. `lambda f: f.domain or "unknown"`).

**From step 2:** frozen `ImpactRecurrenceAdvisory` (e.g. `window_audit_stage`, seam identity fields, `passes_present`, `newest_matched_count`) and `EditDriftAdvisory` (`window_audit_stage`, `matched_findings`, `new_eligible_count`, `matched_count`).

**Existing render patterns:** `_finding_churn_lines`, `_structural_recurrence_lines`, `_advisory_lines` in `plan_tool/convergence_diagnosis.py` — same `⚠` prefix, indented follow-up lines, explicit “does not alter the verdict” / “not a … gate” phrasing.

**CLI path:** `plan_tool/cli/convergence_cmd.py:cmd_convergence` already calls `load_report_history` → `diagnose_convergence` → `print(render_diagnosis(...))` with no handler changes required unless tests need fixture helpers.

**What this step does not verify:** whether classifiers assigned impact or matched findings correctly (semantic quality); completeness-iterate stderr (step 6); telemetry fields on `record_convergence`.

## Files (creates vs edits)

- **New files:** none

- **Existing files (edits only):**
  - `plan_tool/convergence_diagnosis.py` — add optional fields on `ConvergenceDiagnosis`; call both classifiers inside `diagnose_convergence`; add `_impact_recurrence_lines` and `_edit_drift_lines` (names are the implementer’s choice); extend `render_diagnosis` to append them; update module/class docstrings to list the two new diagnosis signals.
  - `tests/test_convergence_diagnosis.py` — end-to-end `diagnose_convergence` + `render_diagnosis` cases using histories that fire each classifier (reuse step 3/4 fixture patterns); extend `_diag` / `_adv_diag` helpers with the new optional fields for focused render tests; regression guard that pre-existing render/advisory tests stay green.
  - `tests/cli/test_convergence_cmd.py` — one or two `main(argv)` cases seeding real sidecars that fire an advisory and assert distinctive output substrings plus `rc == 0`.

## Implementation

### `ConvergenceDiagnosis` fields

Add two optional fields with defaults so every existing constructor and test helper compiles unchanged:

- `impact_recurrence: ImpactRecurrenceAdvisory | None = None`
- `edit_drift: EditDriftAdvisory | None = None`

Extend the class docstring: these are recommend-only completeness-loop signals (like `finding_churn` and `structural_recurrence`), not run-readiness gates and not inputs to `verdict` roll-up.

**Rejected alternative:** stuffing advisory text into classifier return types. Classifiers stay data-only; render owns operator-facing prose so step 6 can reuse the same line builders on stderr.

### `diagnose_convergence` wiring

After the existing series/headline computation and alongside the other newest-run signals, call:

- `impact_recurrence = classify_impact_recurrence(history, window=window)`
- `edit_drift = classify_edit_drift(history, window=window, classify_domain=classify_domain or (lambda f: getattr(f, "domain", None) or "unknown"))`

Pass them into the `ConvergenceDiagnosis(...)` constructor.

**Constraints:**

- **Do not** pass the live `audit_stage` keyword into either classifier — they read persisted stage from collapsed passes (step 3/4 contract).
- **Do** pass the same `window` plumbed through `diagnose_convergence` so tests shrinking the window affect all window-sized signals consistently.
- **Do** pass `classify_domain` only to `classify_edit_drift` (same as `_finding_churn` already receives). When the caller omits it, default to `lambda f: getattr(f, "domain", None) or "unknown"` so detail-stage demotion still holds when live `audit_stage` resolution fails (`cmd_convergence` parse-failure branch today calls `diagnose_convergence(history)` with neither arg — both branches should pass the same domain callback; the diagnose default covers callers that forget).
- **Do not** change `headline` computation, `_series_verdict`, `_latest_blocking_findings`, `_code_drifted_since_prior`, `_finding_churn`, or `structural_recurrence` selection.
- **Do not** pass the live `audit_stage` into either new classifier — they read persisted stage from history. `_finding_churn` continues to use the live stage for every snapshot; that divergence is intentional (Architecture) and must not be “fixed” by rewiring churn here.
- **Do not** add new calls to `is_blocking_impact`, `material_new`, or retired fork/region APIs.

Both classifiers may each call `build_collapsed_completeness_passes` internally — duplicate correlator work is acceptable here; optimizing to a single build is optional and not required for this step.

`diagnose_convergence`’s public signature stays the same (`history`, optional `window`, `audit_stage`, `classify_domain`).

### Render helpers

Add two private line builders modeled on `_finding_churn_lines` / `_structural_recurrence_lines`:

**Impact-recurrence lines** (input: `ImpactRecurrenceAdvisory`):

- Head line with `⚠` naming a **high-impact seam recurrence** across the trailing window (use `passes_present` and `window` / `WINDOW_SIZE` so “3 of 3” is visible when `passes_present == window`).
- Name the seam using fields the advisory already carries — at minimum `seam_source` plus a step/anchor focus (`seam_step_id`, `seam_anchor`, or `_finding_step_focus` on a representative if step 3 stored one). Include `seam_title_slug` or a short title fragment when it helps disambiguation.
- Follow-up line with a **conservative discuss-first action** — e.g. surface the seam to the operator before another hand-apply round; do **not** print runnable `split` / `scope-out` / re-seed commands (those remain out of plan scope).
- Closing clause that this is **recommend-only** and does **not** alter the convergence verdict or act as a run-readiness gate (mirror churn/structural phrasing).

**Edit-drift lines** (input: `EditDriftAdvisory`):

- Head line with `⚠` stating a **strict majority** of new edit-drift-eligible findings in the newest pass matched the window-local prior-apply set — cite `matched_count` and `new_eligible_count` (e.g. “2 of 3”).
- One indented line naming matched findings — titles from `matched_findings` (cap at a small number, then “and N more” if needed); ids are optional secondary detail.
- Follow-up noting further **hand-apply may be auditing your edits** rather than gaps in the original artifact — complements the `self-seeded-finding` audit shape without claiming provenance (no `#231` hard-exit vocabulary).
- Same recommend-only / verdict-agnostic closing clause.

**Rejected alternative:** a single combined block when both advisories fire. Render each independently when populated so operators can see both patterns and step 6 can print them separately on stderr.

### `render_diagnosis` integration

Append new lines in the **loop-signal advisory block** with churn and structural recurrence — after `finding_churn` and `structural_recurrence`, **before** the run-readiness block (`latest_blocking` / `code_drift` via `_advisory_lines`):

```
if diagnosis.impact_recurrence is not None:
    lines.extend(_impact_recurrence_lines(diagnosis.impact_recurrence))
if diagnosis.edit_drift is not None:
    lines.extend(_edit_drift_lines(diagnosis.edit_drift))
```

Show on **every verdict** when populated (same rule as churn and run-readiness advisories — including `insufficient-history`).

Update `render_diagnosis`’s docstring to mention the two new optional blocks.

### Module docstring

The file header still describes “two newest-run advisories” — update it to reflect the fuller advisory set (blocking/drift, churn, structural recurrence, impact recurrence, edit drift) without reviving retired `spinning` vocabulary.

### Shared locations

| Location | This step | Reason |
|---|---|---|
| `plan_tool/cli/convergence_cmd.py` | No edit required | Existing `print(render_diagnosis(diagnosis))` picks up new lines automatically |
| `plan_tool/cli/completeness_cmd.py` | Deferred — step 6 | Stderr reuses render helpers after step 5 lands them |
| `plan_tool/telemetry.py:record_convergence` | Deferred | Telemetry context need not carry advisory payloads for this step |

### Invariants

- `cmd_convergence` still always exits 0 on a resolved plan.
- No changes to `is_blocking_finding`, `is_blocking_impact`, completeness iterate, or reconcile iterate stop reasons.
- `rg 'spinning|FORK_|RegionTrend|classify_fork|recurring_regions' plan_tool/convergence_diagnosis.py` introduces no new matches beyond pre-existing comments.
- Module remains a cycle-free leaf — no `plan_tool.cli` imports.

## Tests

### Tests for this step

Every test below must be green before this step is finished. All pre-existing `diagnose_convergence`, `render_diagnosis`, and `tests/cli/test_convergence_cmd.py` cases must stay green.

**`tests/test_convergence_diagnosis.py`**

- `test_diagnose_populates_impact_recurrence_when_classifier_fires` — history that step 3’s fire fixture uses → `diagnose_convergence(...).impact_recurrence` is not `None` with expected `passes_present` / seam fields; `verdict` unchanged from pre-wiring expectation.
- `test_diagnose_populates_edit_drift_when_classifier_fires` — history that step 4’s fire fixture uses (with `classify_domain` when needed) → `edit_drift` populated with expected counts; `verdict` unchanged.
- `test_diagnose_leaves_advisories_none_when_classifiers_silent` — history that does not fire either classifier → both fields `None` (e.g. fewer than three compatible passes).
- `test_render_impact_recurrence_advisory_names_seam_and_is_recommend_only` — build `ConvergenceDiagnosis` with a populated `impact_recurrence` (via `_diag` helper) → output contains `⚠`, seam-identifying text (source and step/anchor), discuss-before-apply phrasing, and explicit non-gate language; headline verdict line unchanged.
- `test_render_edit_drift_advisory_names_majority_and_matched_findings` — populated `edit_drift` → `⚠`, majority counts (`matched_count` / `new_eligible_count`), at least one matched finding title, hand-apply-may-not-help phrasing, non-gate language.
- `test_render_both_advisories_together` — both fields populated → both blocks present in one `render_diagnosis` call.
- `test_render_impact_recurrence_shown_on_insufficient_history_verdict` — advisory present while `verdict=insufficient-history` → warning still printed (verdict-agnostic rule).
- `test_render_advisory_mutation_deleting_helpers_goes_red` — mutation: deleting `_impact_recurrence_lines` / `_edit_drift_lines` (or emptying their return) makes the render tests above fail — assign plan § Testing’s “deleting the advisory render goes red” to this step.
- `test_end_to_end_impact_recurrence_through_load_and_render` — `save_review` sidecars with `audit_stage` and `impact=high` through `load_report_history` → `diagnose_convergence` → `render_diagnosis` contains impact-recurrence distinctive text; no handler involved.
- `test_end_to_end_edit_drift_through_load_and_render` — similar for edit-drift fire history with applied annotations / window-local prior-apply pattern.

Prefer reusing extended `_save` helpers from steps 1–4 (`audit_stage`, `impact`, annotations) rather than hand-built JSON except for disposition overrides.

**`tests/cli/test_convergence_cmd.py`**

- `test_convergence_prints_impact_recurrence_advisory` — seed three compatible completeness runs that fire impact recurrence → `main(...)` rc 0, output contains impact-recurrence distinctive substring, headline still shows `converging` (or applicable verdict).
- `test_convergence_prints_edit_drift_advisory` — seed edit-drift fire history → rc 0, output contains edit-drift distinctive substring.
- `test_convergence_parse_failure_still_passes_classify_domain` — force `_current_audit_stage` → `None`; seeded detail-window history with medium `plan-completeness` `domain="docs"` → edit-drift does not treat those rows as eligible (same demotion as success path).

Extend `_save` in the CLI test module to accept `audit_stage` / `impact` / annotations if the seeded histories need them.

**Green-before-done gate:** full `tests/test_convergence_diagnosis.py` and `tests/cli/test_convergence_cmd.py` for this step’s modules, plus `uv run pytest tests/test_convergence_diagnosis.py tests/cli/test_convergence_cmd.py -q`.

## Acceptance criteria

- `ConvergenceDiagnosis` carries `impact_recurrence` and `edit_drift` optional fields defaulting to `None`.
- `diagnose_convergence` calls `classify_impact_recurrence` and `classify_edit_drift` on every non–`no-history` path (and on `no-history` the calls are harmless / return `None`).
- `classify_domain` is passed to `classify_edit_drift` only; live `audit_stage` is **not** passed into either classifier.
- `render_diagnosis` prints both advisory blocks when populated, in the loop-signal section before run-readiness advisories.
- Impact-recurrence render names the seam and states recommend-only / verdict-agnostic language; no `split` / `scope-out` / re-seed command lines.
- Edit-drift render cites majority counts and names matched findings; includes hand-apply-may-not-help language without hard-exit / provenance claims.
- `plan-tool convergence` (CLI integration tests) exits 0 and shows advisory text when history fires.
- Headline `verdict`, `finding_churn`, `structural_recurrence`, and `_advisory_lines` behavior unchanged for existing tests.
- `rg 'spinning|FORK_|RegionTrend|classify_fork|recurring_regions' plan_tool/convergence_diagnosis.py` introduces no new production matches beyond pre-existing comments.
- `_impact_recurrence_lines` and `_edit_drift_lines` exist as reusable helpers (step 6 stderr can call them without duplicating prose).

## References

- [`docs/implementation-plans/2-convergence-non-severity-advisories.md`](docs/implementation-plans/2-convergence-non-severity-advisories.md) — plan acceptance criteria for CLI output and non-interference with gates.
- [`docs/implementation-plans/plan-details/convergence-non-severity-advisories/03-impact-recurrence-classifier.md`](docs/implementation-plans/plan-details/convergence-non-severity-advisories/03-impact-recurrence-classifier.md) — `classify_impact_recurrence` contract and fire/disqualifier fixtures.
- [`docs/implementation-plans/plan-details/convergence-non-severity-advisories/04-edit-drift-classifier.md`](docs/implementation-plans/plan-details/convergence-non-severity-advisories/04-edit-drift-classifier.md) — `classify_edit_drift` contract and fire/disqualifier fixtures.
- [`docs/AUDIT_FLOW.md`](docs/AUDIT_FLOW.md) — convergence diagnostic source map; stderr integration pointer for step 6.
- [`DATA_CONTRACT.md`](DATA_CONTRACT.md) — persisted fields the classifiers read through history loading.
- `plan_tool/convergence_diagnosis.py` — `diagnose_convergence`, `render_diagnosis`, `_finding_churn_lines`, `_structural_recurrence_lines`, `_advisory_lines`.
- `plan_tool/cli/convergence_cmd.py` — `cmd_convergence` print path.
- `plan_tool/audit_shapes.py` — `self-seeded-finding` stays `judgment_only`.
- [`BACKLOG.md`](BACKLOG.md) `#158`, `#248` — shipped thin-advisory portions; loop stop and hard exit remain open.

## Applicable guardrails

- **Plan intent (recommend-only advisories):** wiring and render only — no `stop_reason`, `--fail-on-findings`, or exit-code changes; no plan mutation.
- **Step intent:** make both advisories visible on convergence output without altering the headline verdict or any gate.
- **Out of scope — retired vocabulary:** do not revive `spinning`, `FORK_*`, `recurring_regions`, or region-trending types in render text.
- **Out of scope — loop control:** do not connect advisories to `should_continue`, reconcile iterate, or completeness iterate stop reasons.
- **Out of scope — automatic remedies:** render may discuss scope; do not auto-invoke split, scope-out, or re-seed.
- **Out of scope — hard exit / provenance:** no `#231` provenance tracking or loop-terminating edit-drift exit in render copy.
- **Convergence policy boundary:** do not widen `is_blocking_impact` or `material_new` in this step.

## Deferred

- Completeness-iterate stderr surfacing — step 6 reuses `_impact_recurrence_lines` / `_edit_drift_lines`.
- `BACKLOG.md` / `CLAUDE.md` updates and seed archival — step 7.
- Hard edit-drift exit or durable apply→finding provenance — `BACKLOG.md` `#231`.
- Enriching `record_convergence` telemetry with advisory payloads — not required for CLI visibility.
- Single `build_collapsed_completeness_passes` call shared between classifiers — optional performance tidy; classifiers currently own correlator invocation.
- Splitting render or diagnosis into a new leaf module — only if file size forces it; not required here.
