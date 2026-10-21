> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Add edit-drift classifier

## Summary

Ship a deterministic classifier in `plan_tool/convergence_diagnosis.py` that reads collapsed completeness pass history (from step 2) and returns a populated `EditDriftAdvisory` when a strict majority of new edit-drift-eligible findings in the newest window pass match the prior-apply set built inside that same three-pass window. Touch only `plan_tool/convergence_diagnosis.py` and `tests/test_convergence_diagnosis.py`. The main design choice is to key eligibility on `is_blocking_finding` at the window’s persisted `audit_stage` — the same bar `_open_medium_plus` uses — not plain `is_blocking`, not `is_blocking_impact`, and not `material_new`; identity for both “new” and “match” uses the existing `_matches` helper only. When green, `classify_edit_drift` returns `None` for every disqualifier and a frozen advisory for the fire case; `diagnose_convergence` and `render_diagnosis` stay unchanged until step 5.

## Table of Contents

- [Summary](#summary) — what changes and what stays the same
- [Why](#why) — why the classifier lands now
- [Input](#input) — upstream contracts this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — paths touched
- [Implementation](#implementation) — classifier behavior and approach
- [Tests](#tests) — cases and green gate
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — docs and symbols to read first
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — explicitly out of scope here

## Why

Operators can finish a severity-clean completeness audit while the loop keeps surfacing findings that mostly restate prior hand-applies rather than gaps in the original artifact. Today `plan-tool convergence` never names that pattern: the `self-seeded-finding` audit shape stays judgment-only (`plan_tool/audit_shapes.py`), and the retired region-trending layer that once approximated edit-drift is gone (`BACKLOG.md` `#251`). Step 2 builds the collapsed compatible-pass sequence and the `EditDriftAdvisory` shell. This step adds the classifier that connects those pieces so step 5 can print a recommend-only warning without changing iterate stop reasons or exit codes.

## Input

**From step 2:** `build_collapsed_completeness_passes` (or the name step 2 lands) returning `tuple[CompatiblePass, ...]`; frozen `EditDriftAdvisory` fields to populate (`window_audit_stage`, `matched_findings`, `new_eligible_count`, `matched_count`). `CompatiblePass` carries `audit_stage`, `findings`, `annotations`, and `created_at` per pass.

**Shared matcher (existing):** `_matches`, `_title_slug`, `_finding_step_focus`, `_is_resolved_in_run`, `TITLE_SIMILARITY_CUTOFF` in `plan_tool/convergence_diagnosis.py`. Both advisories in this plan use this matcher — do not add a second identity tier.

**Eligibility bar (existing):** `plan_tool/convergence.py:is_blocking_finding` with `stage=<window_audit_stage>` and optional `classify_domain` — same call shape as `_open_medium_plus` in `plan_tool/convergence_diagnosis.py`. `RunFinding` duck-types the `Recommendation` fields the predicate reads (`source`, `severity`, `domain`).

**Window size:** `WINDOW_SIZE` (`3`) in the same module — same trailing length as the impact-recurrence classifier and the convergence verdict window.

**Disposition markers:** `plan_tool/review_persistence.py:Annotation` — terminal hand work for the prior-apply set is `_is_resolved_in_run`: `status == "applied"` (loader rewrites legacy `"done"` → `"applied"`) **or** decline-close (`_is_decline_close`: `status == "skip"` with empty `halt_reason`). Do not require `status == "applied"` alone.

**What this step does not verify:** whether matched findings were truly caused by the operator’s last edit (semantic provenance — `BACKLOG.md` `#231`); whether the printed advisory text reads well (step 5); whether completeness stderr shows it (step 6).

## Files (creates vs edits)

- **New files:** none

- **Existing files (edits only):**
  - `plan_tool/convergence_diagnosis.py` — add `classify_edit_drift` (public) and small private helpers for compatible-window selection, prior-apply-set construction, newest-pass novelty, eligibility filtering, and majority check; populate `EditDriftAdvisory` on fire; return `None` otherwise. No changes to `diagnose_convergence`, `render_diagnosis`, verdict constants, structural recurrence, or impact-recurrence classifier.
  - `tests/test_convergence_diagnosis.py` — classifier cases using extended `_save` helpers (`audit_stage` from step 2) and in-memory `_finding` / `_snapshot` / `_history` helpers; optional dedicated test class (e.g. `TestEditDriftClassifier`).

## Implementation

### Public surface

Add one public entry point (name is the implementer’s choice; `classify_edit_drift` matches the plan and `BACKLOG.md` `#248` vocabulary):

- **Input:** `ReportHistory` (calls `build_collapsed_completeness_passes` internally), optional `window: int = WINDOW_SIZE`, optional `classify_domain` (same type/shape `_open_medium_plus` accepts — keyed off `RunFinding.domain` when present).
- **Output:** `EditDriftAdvisory | None`. `None` means insufficient evidence or no qualifying pattern — not an error.

**Rejected alternative:** scoring against the full report history’s apply dispositions. The plan’s prior-apply set accumulates **only inside the trailing three-pass window** so long-ago applies do not inflate matches; a long-history test must prove older passes drop out.

### Compatible trailing window

Mirror step 3’s window walk (reuse a shared private helper if one already exists from step 3; otherwise duplicate the short walk — consolidation is optional, not required):

1. Build collapsed passes from history via step 2’s correlator.
2. If the sequence is empty, return `None`.
3. Let the newest pass define `window_audit_stage = newest.audit_stage`.
4. Walk backward from the newest pass while `audit_stage` matches — that is the compatible run for this window.
5. If fewer than `window` passes in that run, return `None`.
6. Take the last `window` passes as the evaluation window, oldest→newest: `p0`, `p1`, `p2`.

Do not mix reconcile kinds or bare/detail stages inside one window — the correlator and stage walk already enforce that.

### Prior-apply set (window-local only)

Build a set of `RunFinding` representatives from **only** the three window passes:

- **Resolved dispositions:** for each pass `p` in the window and each finding `f` in `p.findings`, if `_is_resolved_in_run(p.annotations.get(f.id))` (applied **or** decline-close), include `f`.
- **Closed-between-passes proxy:** for each adjacent pair `(p_i, p_{i+1})` inside the window, include every finding `f` in `p_i.findings` such that no finding in `p_{i+1}.findings` matches `f` via `_matches`.

Union the two sources. One way to store matches: keep a flat list/tuple of representatives; matching uses `_matches` against any member (no second identity tier). Deduplication is optional — duplicate representatives do not change the majority math.

Entries from passes **older than** `p0` must not appear. A long-history fixture with applies/disappearances only before the window is a required negative case.

### New findings in the newest pass

In the newest window pass `p2`, a finding is **new** when no finding in the immediately prior window pass `p1` matches it via `_matches`.

- A restated finding (new id, same anchor/title tier as an older row) is **not** new — `_matches` handles it.
- Novelty is **only** newest-vs-immediate-prior inside the window, not newest-vs-full-history.

### Edit-drift-eligible filter

From the new findings in `p2`, keep only those that pass **both**:

- `is_blocking_finding(finding, stage=window_audit_stage, classify_domain=classify_domain)` — same stage-aware bar `_open_medium_plus` uses.
- `not _is_resolved_in_run(p2.annotations.get(finding.id))` — still open in the newest pass (aligns with `_open_medium_plus`’s unresolved filter).

Call the result `new_eligible`. **Zero `new_eligible` → return `None` immediately** (no fire on an empty eligible set).

Do **not** call `is_blocking_impact`, plain `is_blocking`, or completeness `material_new` predicates. Do not add a parallel `CONCEPTUAL_SOURCES`-only gate or a “deterministic well-formedness” source filter beyond what `is_blocking_finding` already encodes — bare-stage medium `plan-completeness` is excluded by the stage bar, and deps/file-check/detail-coverage rows are excluded because they never enter `sidecar_recs` / completeness JSON (`completeness_phases._persist_and_present_report`), not because this classifier filters them.

### Match and fire rule

For each `new_eligible` finding, it **matches** the prior-apply set when `_matches(candidate, representative)` is true for any representative in that set.

- **`matched_count`** — number of `new_eligible` findings that match.
- **`new_eligible_count`** — `len(new_eligible)`.

**Fire when** `new_eligible_count > 0` and `matched_count * 2 > new_eligible_count` (strict majority). Tie at 50% does not fire.

On fire, populate `EditDriftAdvisory`:

- `window_audit_stage`
- `matched_findings` — the `new_eligible` rows that matched (tuple, stable pass order then finding list order)
- `new_eligible_count`, `matched_count`

Do **not** add `blocking`, severity tiers, verdict/stop-reason enums, or `spinning` / `FORK_*` vocabulary to the advisory type.

### Invariants — do not change

- `diagnose_convergence`, `render_diagnosis`, `_open_medium_plus`, `_finding_churn`, `_structural_recurs_in_streak`, `classify_impact_recurrence` (step 3), and verdict roll-up — unchanged behavior and signatures.
- Do not import retired fork/region APIs (`RegionTrend`, `classify_fork`, `recurring_regions`).
- Module stays a cycle-free leaf — no `plan_tool.cli` imports.

### Shared locations (read-only consumers)

| Location | This step | Reason |
|---|---|---|
| `plan_tool/cli/convergence_cmd.py` | Deferred — step 5 | Live `diagnose_convergence` wiring arrives with step 5 |
| `plan_tool/cli/completeness_cmd.py` | Deferred — step 6 | Stderr surfacing after step 5 |
| `plan_tool/telemetry_analysis.py` | No edit | Uses `_matches` only; unaffected |
| `plan_tool/audit_shapes.py` | No edit | `self-seeded-finding` stays `judgment_only`; this advisory complements but does not gate on it |

## Tests

### Tests for this step

Every test below must be green before this step is finished. Existing `diagnose_convergence` / `render_diagnosis` / `classify_impact_recurrence` cases must stay green unchanged.

**`tests/test_convergence_diagnosis.py`**

- `test_edit_drift_fires_on_strict_majority_match` — three same-stage completeness passes; newest pass has three new eligible conceptual findings, two `_matches` members of the window-local prior-apply set (one via applied annotation in `p1`, one via disappear-between-`p0`/`p1`) → non-`None` advisory; `matched_count == 2`, `new_eligible_count == 3`, `window_audit_stage` matches saved stage.
- `test_edit_drift_decline_close_joins_prior_apply` — a finding with decline-close disposition (`skip` + empty `halt_reason`) in a window pass is a prior-apply member; a restated new eligible row that `_matches` it counts toward the majority.
- `test_edit_drift_no_fire_on_minority_match` — same shape but only one of three new eligible matches → `None`.
- `test_edit_drift_no_fire_when_zero_new_eligible` — newest pass adds no findings unmatched in `p1`, or all new rows fail eligibility → `None`.
- `test_edit_drift_rested_finding_not_new` — newest pass finding has a new id but `_matches` a row in `p1` → not counted in `new_eligible`; majority cannot fire on it alone.
- `test_edit_drift_no_fire_when_fewer_than_three_compatible_passes` — only two same-stage collapsed passes → `None`.
- `test_edit_drift_no_fire_on_stage_boundary` — bare→detail transition leaves fewer than three same-stage passes in the trailing window → `None`.
- `test_edit_drift_bare_stage_medium_completeness_excluded` — `audit_stage="bare"`, medium `plan-completeness` findings fail `is_blocking_finding` → not eligible → `None`.
- `test_edit_drift_bare_stage_medium_data_contract_still_eligible` — `audit_stage="bare"`, medium `data-contract` (or `concept-coverage` / medium `granularity-split`) in the window’s findings remains `is_blocking_finding`-eligible and can contribute to a fire/majority when other conditions hold — pins the `sidecar_recs` persistence boundary beside the plan-completeness bare carve.
- `test_edit_drift_detail_stage_docs_domain_demoted` — `audit_stage="detail"`, medium `plan-completeness` with `domain="docs"` excluded when `classify_domain` is supplied (mirror `test_open_medium_plus_demotes_docs_domain_at_detail_stage`) → `None`.
- `test_edit_drift_deterministic_only_churn_no_fire` — window passes whose only new rows fail `is_blocking_finding` (e.g. `nit`/`info`, or sources that never enter `sidecar_recs`) → `None`. Do **not** add a parallel source-axis filter in the classifier — exclusion of deterministic well-formedness rows is a persistence boundary (`sidecar_recs`), not a classifier rule.
- `test_edit_drift_prior_apply_outside_window_ignored` — four+ passes; applied/disappeared findings only in passes before `p0`; newest pass has new eligible rows that would match only those old entries → `None` (window-local prior-apply set is empty or insufficient).
- `test_edit_drift_reuse_collapse_not_triple_confirm` — two adjacent finals with identical finding-id sets collapse to one logical pass; third pass differs → trailing compatible window length 2 → `None`.
- `test_edit_drift_uses_matches_not_raw_id` — prior-apply member and new eligible row share anchor/title tier but differ in id; match counts via `_matches`.
- `test_edit_drift_classifier_imports_no_retired_fork_apis` — mutation: introducing retired fork/region imports into the classifier path fails the `rg` gate below.

Build multi-pass histories through `save_review` / extended `_save` with `audit_stage` where end-to-end load matters; use `_history` / `_snapshot` for focused classifier unit cases.

## Acceptance criteria

- `classify_edit_drift` exists in `plan_tool/convergence_diagnosis.py` and returns `EditDriftAdvisory | None`.
- Fire case: strict majority of new edit-drift-eligible findings in the newest window pass match the window-local prior-apply set → populated advisory with correct counts and `matched_findings`.
- Disqualifiers return `None`: minority match, zero new eligible, fewer than three compatible collapsed passes, stage change breaking the window, reuse-collapse leaving fewer than three logical passes, eligibility failures (including bare-stage medium conceptual and detail-stage demoted docs domain).
- “New” uses `_matches` against the immediately prior window pass only; restated ids do not count as new.
- Prior-apply set includes `_is_resolved_in_run` dispositions (applied **and** decline-close) and disappear-between-adjacent-pairs **only inside** the three-pass window — older history excluded.
- Eligibility uses `is_blocking_finding` at `window_audit_stage` plus unresolved-in-newest; no new `is_blocking_impact` / `material_new` calls on the classifier path.
- `rg 'is_blocking_impact' plan_tool/convergence_diagnosis.py` shows no new calls from the edit-drift classifier path.
- `rg 'spinning|FORK_|RegionTrend|classify_fork|recurring_regions' plan_tool/convergence_diagnosis.py` introduces no new matches beyond pre-existing comments, if any.
- `diagnose_convergence` / `render_diagnosis` outputs unchanged for existing tests (classifier not wired yet).

## References

- [`docs/implementation-plans/2-convergence-non-severity-advisories.md`](docs/implementation-plans/2-convergence-non-severity-advisories.md) — Architecture § edit-drift binary observable, prior-apply set definition, and acceptance criteria.
- [`DATA_CONTRACT.md`](DATA_CONTRACT.md) — `SavedReview.audit_stage`, `Recommendation` fields, and `Annotation` disposition markers the classifier reads.
- [`docs/AUDIT_FLOW.md`](docs/AUDIT_FLOW.md) — checkpoint vs final roles (already enforced before this classifier runs); stage bar context for `_open_medium_plus`.
- `plan_tool/convergence_diagnosis.py` — `_matches`, `_open_medium_plus`, `_is_resolved_in_run`, `WINDOW_SIZE`, `FindingChurn` / `ImpactRecurrenceAdvisory` (sibling advisory patterns).
- `plan_tool/convergence.py` — `is_blocking_finding`, `STAGE_BARE`, `STAGE_DETAIL`, `CONCEPTUAL_SOURCES`.
- `plan_tool/audit_shapes.py` — `self-seeded-finding` registry entry (`judgment_only`).
- [`BACKLOG.md`](BACKLOG.md) `#248` — edit-drift thin advisory scope; `#231` — hard-exit provenance explicitly not implemented here.

## Applicable guardrails

- **Plan intent (recommend-only advisories):** classifier only returns a frozen record — no `stop_reason`, exit-code, or `--fail-on-findings` changes; no plan mutation.
- **Step intent:** detect strict-majority self-seed pattern over the newest three compatible passes; eligibility is `is_blocking_finding` at persisted stage, not `material_new` / `is_blocking_impact`; zero new eligible never fires.
- **Out of scope — retired vocabulary:** do not revive `spinning`, `FORK_*`, `recurring_regions`, or region-trending types.
- **Out of scope — loop control:** do not integrate with `should_continue`, reconcile iterate, or completeness iterate stop reasons.
- **Out of scope — automatic remedies / hard exit:** do not implement provenance tracking or loop termination — `BACKLOG.md` `#231`.
- **Out of scope — audit-shape gate:** do not promote `self-seeded-finding` from `judgment_only` to a software gate.
- **Convergence policy boundary:** do not widen `is_blocking_impact` or completeness `material_new` rules for this advisory.

## Deferred

- Wiring `classify_edit_drift` into `diagnose_convergence` and `render_diagnosis` — step 5.
- Conservative warning text naming matched findings — step 5 (classifier supplies counts and `matched_findings` only).
- Completeness-iterate stderr surfacing — step 6.
- Impact-recurrence classifier — step 3 (shares correlator and window walk only).
- Hard edit-drift exit or durable apply→finding provenance — `BACKLOG.md` `#231`.
- Explicit on-disk reuse marker beyond identical-id collapse — plan deferred follow-up.
- Splitting the classifier into a separate leaf module — only if `convergence_diagnosis.py` growth forces it; not required for this step.
