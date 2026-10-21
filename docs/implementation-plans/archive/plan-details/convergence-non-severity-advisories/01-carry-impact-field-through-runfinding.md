> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Carry impact field through RunFinding

## Summary

Add an `impact` field to the `RunFinding` dataclass in `plan_tool/convergence_diagnosis.py` and copy it from each saved `Recommendation` during history flattening. This is a data-plumbing step only: step 3's impact-recurrence classifier needs explicit `impact=high` on flattened findings, and that value already lives on persisted recommendations but is dropped today. Touch `plan_tool/convergence_diagnosis.py` and `tests/test_convergence_diagnosis.py` only. The main design choice is to carry `impact` verbatim with a `None` default and leave `complexity` out — downstream only needs the explicit high-impact signal. When green, `load_report_history` round-trips `impact` from sidecar JSON into `RunFinding`, and every existing `diagnose_convergence` / `render_diagnosis` test still passes unchanged.

## Table of Contents

- [Summary](#summary) — what changes and what stays the same
- [Why](#why) — why `RunFinding` needs `impact` now
- [Input](#input) — upstream `Recommendation.impact` contract this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — paths touched
- [Implementation](#implementation) — field, flatten wiring, and invariants
- [Tests](#tests) — cases and green gate
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — docs and symbols to read first
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — explicitly out of scope here

## Why

Saved completeness sidecars already persist `Recommendation.impact` (`low` / `medium` / `high`, or `None` when the triage tag is absent — see `DATA_CONTRACT.md`). `RunFinding` is the in-memory shape `load_report_history` produces for every downstream convergence helper, but `_finding_from_recommendation` currently copies only a subset of persisted fields and drops `impact`. Step 3's impact-recurrence classifier must filter on explicit `impact=high` seams across report history; without this field on `RunFinding`, that classifier would have to re-read raw sidecars or re-parse recommendations, duplicating the flatten path and drifting from the model every other helper already uses.

## Input

**Upstream contract:** `plan_tool/review.py:Recommendation.impact` — optional triage tag populated by `check_plan_audit` and reconcile extractors from inline `(impact=…, complexity=…)` tags. Persisted on every saved review recommendation per `DATA_CONTRACT.md` (`impact` row under the `Recommendation` table). Values are `"low"`, `"medium"`, `"high"`, or `None`.

**Read path:** `_snapshot_from_saved_review` → `_finding_from_recommendation` over `SavedReview.recommendations` (`plan_tool/review_persistence.py:SavedReview.recommendations`, persisted recommendation list on each sidecar) inside `load_report_history`. No new I/O or schema changes — the JSON already carries the field.

**What this step does not verify:** whether `impact` was assigned correctly by the auditor (semantic quality). This step only asserts the flatten path preserves whatever was saved.

## Files (creates vs edits)

- **New files:** none

- **Existing files (edits only):**
  - `plan_tool/convergence_diagnosis.py` — add `impact: Optional[str] = None` to `RunFinding`; update the class docstring to list `impact` among carried persisted fields; set `impact=rec.impact` in `_finding_from_recommendation`.
  - `tests/test_convergence_diagnosis.py` — add flatten and end-to-end history cases; optionally extend the local `_finding` helper with an `impact` keyword (default `None`) so later classifier tests can set it without positional churn.

## Implementation

### What changes

- **`RunFinding` gains one optional field:** `impact: Optional[str] = None`, typed like `Recommendation.impact`. Copy the value as-is at flatten time — no normalization, coercion, or defaulting to a sentinel other than `None`.
- **`_finding_from_recommendation` wires it:** `impact=rec.impact` in the `RunFinding(...)` constructor call. No other flatten logic changes.
- **Everything else stays the same:** `diagnose_convergence`, `render_diagnosis`, `_open_medium_plus`, `_latest_blocking_findings`, `_finding_churn`, and all other helpers must not start reading `impact`. This step does not call `is_blocking_impact` and does not change blocking or verdict behavior.

### Recommended approach

One way to land this cleanly:

1. Add `impact` to `RunFinding` after `severity` (triage metadata sits naturally beside severity; exact position is the implementer's call as long as required fields stay ordered before defaulted ones).
2. Extend the `RunFinding` docstring with one line: `impact` is the persisted triage tag, copied verbatim, `None` when the saved recommendation had no tag.
3. Pass `rec.impact` through `_finding_from_recommendation` — mirror how `severity` and `source` are copied without transformation.
4. Stop. Do not touch `_open_medium_plus`, rendering, or classifier stubs.

### Fields deliberately still dropped

`RunFinding` remains a persisted-field subset, not a full `Recommendation`. Still omitted (unchanged by this step):

- `body`, `suggested_action` — prose volume; identity matching uses `title` / `anchor` / `_matches`
- `complexity` — not needed for impact-recurrence (step 3 keys on explicit `impact=high` only)
- `redirect` — replaced by the existing `redirect_present: bool`
- `file_path`, `target_signature` — apply-path metadata unused in convergence diagnosis

**Rejected alternative:** carrying `complexity` now "for symmetry." It has no step-3 consumer and would widen every test helper and fixture for no current reader.

### Call sites and zero-diff files

**Must update (in scope):**

- `plan_tool/convergence_diagnosis.py:_finding_from_recommendation` — the sole production writer of `RunFinding` from saved data.

**Compile unchanged on the default (no file edits required):**

- `plan_tool/telemetry_analysis.py` — two inline `RunFinding(...)` constructions; `impact=None` default keeps them valid.
- `tests/test_telemetry_analysis.py` — positional `RunFinding(...)` helpers; same default covers them.
- `tests/test_convergence_diagnosis.py` — inline `RunFinding(...)` at the committed fixture loader and `_finding` helper; default `None` is correct for existing cases.

Do not edit `telemetry_analysis.py` or `test_telemetry_analysis.py` in this step — their constructors should keep working via the new default alone.

### Invariants to preserve

- **No diagnostic behavior change.** `impact` is stored and returned; no function in `convergence_diagnosis.py` may branch on it until step 3.
- **Raw carry, no inference.** Missing or legacy-unknown impact stays `None`; do not parse `body` for inline tags at flatten time (that work already happened when the recommendation was extracted).
- **Frozen dataclass.** Keep `RunFinding` `frozen=True`; add the field with a default so existing positional construction at call sites that only pass the original six positional args still works where those sites exist.

## Tests

Green-before-done gate: full `tests/test_convergence_diagnosis.py` passes, and every new case below is green.

### Tests for this step

- `test_finding_from_recommendation_carries_impact` — `_finding_from_recommendation` copies `impact="high"`, `"medium"`, and `"low"` verbatim from a `Recommendation`.
- `test_finding_from_recommendation_impact_none_when_absent` — a `Recommendation` with default `impact=None` flattens to `RunFinding.impact is None`.
- `test_load_report_history_preserves_impact` — `_save` a completeness sidecar whose recommendation has `impact="high"`, then `load_report_history` and assert the loaded `RunFinding.impact == "high"`.
- Existing `diagnose_convergence` / `render_diagnosis` / `_open_medium_plus` tests — unchanged expectations; the full pre-existing suite is the regression guard that no diagnostic or rendering behavior moved.

## Acceptance criteria

- `RunFinding` exposes `impact: Optional[str] = None`.
- `_finding_from_recommendation` sets `impact` from `rec.impact` with no transformation.
- `load_report_history` returns findings whose `impact` matches the saved sidecar recommendation.
- `rg '\.impact' plan_tool/convergence_diagnosis.py` matches only the dataclass field, `_finding_from_recommendation`, and (if present) the docstring — no reads inside `diagnose_convergence`, `render_diagnosis`, `_open_medium_plus`, `_latest_blocking_findings`, or `_finding_churn`.
- `uv run pytest tests/test_convergence_diagnosis.py -q` passes with zero failures.
- `plan_tool/telemetry_analysis.py` and `tests/test_telemetry_analysis.py` require no edits (compile and pass on defaults).

## References

- [`DATA_CONTRACT.md`](DATA_CONTRACT.md) — `Recommendation.impact` persisted-field definition and allowed values.
- [`plan_tool/review.py`](plan_tool/review.py) — `Recommendation` dataclass; `impact` field docstring on the triage tag.
- [`plan_tool/convergence_diagnosis.py`](plan_tool/convergence_diagnosis.py) — `RunFinding`, `_finding_from_recommendation`, `_snapshot_from_saved_review`, `load_report_history`.
- [`plan_tool/convergence.py`](plan_tool/convergence.py) — `is_blocking_impact` (step 3's high-impact filter is separate from this step; do not wire it here).
- [`docs/AUDIT_FLOW.md`](docs/AUDIT_FLOW.md) — completeness report history and checkpoint context (read for orientation; no edits in this step).

## Applicable guardrails

- **Plan step intent** — this step only makes `impact=high` evidence available on `RunFinding`. No new classifiers, stderr advisories, or rendering changes.
- **Plan "## Out of scope"** — do not add impact-recurrence detection, edit-drift logic, loop stop reasons, exit-code changes, `spinning` / `FORK_*` vocabulary, or changes to stage blocking bars. Do not re-implement checkpoint/final filtering owned by `load_report_history`.
- **Declared `files:` list** — edits limited to `plan_tool/convergence_diagnosis.py` and `tests/test_convergence_diagnosis.py`.

## Deferred

- Impact-recurrence classifier and `ImpactRecurrenceAdvisory` result type — step 3 (`depends_on` this step's `RunFinding.impact`).
- `audit_stage` persistence, reuse-collapse correlator, and compatible-pass window — step 2.
- `complexity` on `RunFinding` — no current reader; impact-recurrence keys on explicit `impact=high` only.
- Completeness-iterate stderr advisory wiring — step 6.
- `DATA_CONTRACT.md` documentation of `RunFinding` — not in this step's file list; `RunFinding` is not currently a persisted contract type (step 2 owns `SavedReview` schema docs).
- `plan_tool/telemetry_analysis.py` helper cleanup — optional future ergonomics; not required for correctness once the default exists.
