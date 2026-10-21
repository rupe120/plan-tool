> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Add impact-recurrence classifier

## Summary

Ship a deterministic classifier in `plan_tool/convergence_diagnosis.py` that reads collapsed completeness pass history (from step 2) and returns a populated `ImpactRecurrenceAdvisory` when the same still-open, explicit-`impact=high` seam has recurred without shrinkage across the newest three consecutive compatible passes. Touch only `plan_tool/convergence_diagnosis.py` and `tests/test_convergence_diagnosis.py`. The main design choice is to key eligibility on persisted `RunFinding.impact == "high"` only — not `is_blocking_impact`, not severity — and to reuse the existing `_matches` matcher for seam identity rather than a parallel token overlap rule. When green, `classify_impact_recurrence` returns `None` for every disqualifier and a frozen advisory for the fire case; `diagnose_convergence` and `render_diagnosis` stay unchanged until step 5.

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

Operators can finish a severity-clean completeness audit while the same high-impact design seam stays open across multiple passes. Today `plan-tool convergence` never names that pattern: `_structural_recurs_in_streak` only watches structural sources with a plain severity floor, and the retired region-trending layer that once covered impact recurrence is gone (`BACKLOG.md` `#251`). Step 1 carries `impact` onto `RunFinding`; step 2 builds the collapsed compatible-pass sequence and the `ImpactRecurrenceAdvisory` shell. This step adds the classifier that connects those pieces so step 5 can print a recommend-only warning without changing iterate stop reasons or exit codes.

## Input

**From step 1:** `RunFinding.impact` — classifier reads only explicit `"high"`; `None`, `"low"`, and `"medium"` never qualify.

**From step 2:** `build_collapsed_completeness_passes` (or the name step 2 lands) returning `tuple[CompatiblePass, ...]`; frozen `ImpactRecurrenceAdvisory` fields to populate (`window_audit_stage`, seam identity fields, `passes_present`, `newest_matched_count`). `CompatiblePass` carries `audit_stage`, `findings`, `annotations`, and `created_at` per pass.

**Shared matcher (existing):** `_matches`, `_title_slug`, `_finding_step_focus`, `_is_resolved_in_run`, `TITLE_SIMILARITY_CUTOFF` in `plan_tool/convergence_diagnosis.py`. Both advisories in this plan use this matcher — do not add a second identity tier.

**Window size:** `WINDOW_SIZE` (`3`) in the same module — same trailing length as the convergence verdict window.

**What this step does not verify:** whether the auditor assigned impact correctly (semantic quality); whether the printed advisory text reads well (step 5); whether completeness stderr shows it (step 6).

## Files (creates vs edits)

- **New files:** none

- **Existing files (edits only):**
  - `plan_tool/convergence_diagnosis.py` — add `classify_impact_recurrence` (public) and small private helpers for seam grouping, window selection, shrinkage check, and tie-break; populate `ImpactRecurrenceAdvisory` on fire; return `None` otherwise. No changes to `diagnose_convergence`, `render_diagnosis`, verdict constants, or structural recurrence.
  - `tests/test_convergence_diagnosis.py` — classifier cases using extended `_save` / `_completeness_rec` helpers (`impact`, `audit_stage` from steps 1–2); optional dedicated test class (e.g. `TestImpactRecurrenceClassifier`).

## Implementation

### Public surface

Add one public entry point (name is the implementer's choice; `classify_impact_recurrence` matches the plan and backlog vocabulary):

- **Input:** `ReportHistory` (calls `build_collapsed_completeness_passes` internally), plus optional `window: int = WINDOW_SIZE`.
- **Output:** `ImpactRecurrenceAdvisory | None`. `None` means insufficient evidence or no qualifying seam — not an error.

**Rejected alternative:** a new `plan_tool/impact_recurrence.py` leaf module (the blocked `impact-recurrence-01-classifier` seed). This plan keeps correlator and classifier together in `convergence_diagnosis.py` until a later refactor proves the split is worth the extra module and import surface.

### Compatible trailing window

1. Build collapsed passes from history via step 2's correlator.
2. If the sequence is empty, return `None`.
3. Let the newest pass define `window_audit_stage = newest.audit_stage`.
4. Walk backward from the newest pass while `audit_stage` matches — that is the compatible run for this window.
5. If fewer than `window` passes in that run, return `None` (legacy missing `audit_stage` passes are already dropped by the correlator).
6. Take the last `window` passes from that run as the evaluation window (oldest→newest within the slice).

Do not mix reconcile kinds or bare/detail stages inside one window — the correlator and stage walk already enforce that.

### What counts as a seam

A **seam** is an identity group of findings clustered with the same representative pattern as `_structural_recurs_in_streak`: walk findings in a pass, match each to an existing representative via `_matches`, or mint a new representative.

**Eligibility filter per finding** (all must hold for membership in impact-recurrence analysis):

- `finding.impact == "high"` — string equality only; no inference from severity or `is_blocking_impact`.
- For the **newest pass fire check**, the finding must also be **open**: `not _is_resolved_in_run(pass.annotations.get(finding.id))`.

Findings with missing or non-high impact are ignored entirely — they do not disqualify other seams.

### Per-seam metrics over the window

For each representative (seam) that has at least one high-impact finding in the newest pass and at least one **open** high-impact finding in the newest pass:

- **`matched_count(pass)`** — count of findings in that pass with `impact == "high"` that `_matches` the representative (open or closed — recurrence is presence in the pass, shrinkage is count of matched high-impact rows).
- **`passes_present`** — number of window passes where `matched_count(pass) > 0`.
- **`newest_matched_count`** — `matched_count` on the newest window pass.

**Shrinkage (no-shrinkage rule):** for each adjacent pair in the window `(pass_i, pass_{i+1})`, require `matched_count(pass_{i+1}) >= matched_count(pass_i)`. A drop in matched high-impact count between consecutive window passes disqualifies the seam. This is **not** severity shrinkage and **not** step-span shrinkage.

**Recurrence across three passes:** require `passes_present >= window` (all three window passes show at least one matched high-impact finding). With a length-3 window, that means presence in every pass.

**Still open in newest:** require at least one open high-impact finding matching the representative in the newest window pass (not only closed/applied rows).

### Tie-break when multiple seams qualify

Pick exactly one seam deterministically:

1. **Highest `passes_present`** (most window passes with a match).
2. Then **highest `newest_matched_count`**.
3. Then **lowest seam sort key** from the **first-seen** representative in window order (oldest pass first, then finding list order): `(source, anchor_or_step, title_slug)` where `anchor_or_step` is `step_id` when set, else `anchor` if set, else `""`; `title_slug` from `_title_slug(representative.title)`.

### Populating `ImpactRecurrenceAdvisory`

On fire, fill the step 2 shell (extend only if a field is genuinely missing for step 5 render — prefer using existing fields):

- `window_audit_stage`
- Seam identity: `seam_source`, `seam_anchor`, `seam_step_id`, `seam_title_slug` (or the single `seam_key` tuple if step 2 chose that shape)
- `passes_present`, `newest_matched_count`

Optional but useful for step 5 without widening scope: carry `step_focus` via `_finding_step_focus(representative)` on the advisory if step 2 left a slot, or derive it at render time from `seam_step_id` / `seam_anchor`.

Do **not** add `blocking`, severity-based gates, verdict enums, or `spinning` / `FORK_*` vocabulary to the advisory type.

### Invariants — do not change

- `diagnose_convergence`, `render_diagnosis`, `_open_medium_plus`, `_finding_churn`, `_structural_recurs_in_streak`, and verdict roll-up — unchanged behavior and signatures.
- Do not call `is_blocking_impact` or widen `is_blocking_finding` for this classifier.
- Do not import retired fork/region APIs (`RegionTrend`, `classify_fork`, `recurring_regions`).
- Module stays a cycle-free leaf — no `plan_tool.cli` imports.

### Shared locations (read-only consumers)

| Location | This step | Reason |
|---|---|---|
| `plan_tool/cli/convergence_cmd.py` | Deferred — step 5 | Live `diagnose_convergence` still passes live `audit_stage`; history-backed advisory wiring arrives with step 5 |
| `plan_tool/cli/completeness_cmd.py` | Deferred — step 6 | Stderr surfacing after step 5 |
| `plan_tool/telemetry_analysis.py` | No edit | Uses `_matches` only; unaffected |

## Tests

### Tests for this step

Every test below must be green before this step is finished. Existing `diagnose_convergence` / `render_diagnosis` cases must stay green unchanged.

**`tests/test_convergence_diagnosis.py`**

- `test_impact_recurrence_fires_on_three_pass_stable_seam` — three same-stage completeness passes with the same open `impact=high` finding (matched via shared anchor/title) → non-`None` advisory; `passes_present == 3`, `newest_matched_count >= 1`, `window_audit_stage` matches saved stage.
- `test_impact_recurrence_tie_break_most_passes_then_count_then_key` — two qualifying seams; higher `passes_present` wins; if tied, higher `newest_matched_count`; if still tied, lower seam key wins.
- `test_impact_recurrence_no_fire_when_impact_not_high` — same history shape but `impact` is `None`, `"medium"`, or `"low"` → `None`.
- `test_impact_recurrence_no_fire_on_shrinkage` — matched high-impact count drops between adjacent window passes → `None`.
- `test_impact_recurrence_partial_close_still_present_does_not_shrink` — two matched `impact=high` rows in the seam; one is disposition-closed but still present in the pass → `matched_count` unchanged; advisory still fires when the seam remains open and other fire conditions hold.
- `test_impact_recurrence_no_fire_when_resolved_in_newest` — seam present across three passes but newest pass has `applied` or decline-close annotation on the matched finding → `None`.
- `test_impact_recurrence_no_fire_when_fewer_than_three_compatible_passes` — only two same-stage collapsed passes → `None`.
- `test_impact_recurrence_no_fire_on_stage_boundary` — three passes but bare→detail transition splits the compatible run so the trailing window has fewer than three → `None`.
- `test_impact_recurrence_reuse_collapse_not_triple_confirm` — two adjacent finals with identical finding-id sets collapse to one logical pass; a third pass with a different id set → trailing window length 2 → `None` (reuse-audit replay does not fake three confirmations).
- `test_impact_recurrence_uses_matches_not_raw_id` — same seam with restated title above `TITLE_SIMILARITY_CUTOFF` and new id in newest pass still counts as one seam (matched count and recurrence follow `_matches`, not id equality).
- `test_impact_recurrence_classifier_imports_no_retired_fork_apis` — mutation: introducing `from … import RegionTrend` / `classify_fork` / `recurring_regions` (or equivalent retired symbols) into the classifier path fails the `rg` gate below.

Build histories through `save_review` / extended `_save` with `audit_stage` and `impact` on recommendations — avoid hand-built JSON except for annotation/disposition overrides.

## Acceptance criteria

- `classify_impact_recurrence` exists in `plan_tool/convergence_diagnosis.py` and returns `ImpactRecurrenceAdvisory | None`.
- Fire case: same open explicit-`impact=high` seam across the newest three consecutive same-`audit_stage` collapsed passes with non-decreasing matched high-impact counts → populated advisory.
- Disqualifiers return `None`: non-high/missing impact, shrinkage between adjacent window passes, resolved in newest, fewer than three compatible passes, stage change breaking the window, reuse-collapse leaving fewer than three logical passes.
- Multi-seam tie-break is deterministic: `passes_present` → `newest_matched_count` → lowest `(source, step_id-if-set-else-anchor, title_slug)` key.
- Seam identity uses `_matches` only — no parallel token-overlap matcher added in this module.
- `rg 'is_blocking_impact' plan_tool/convergence_diagnosis.py` shows no new calls from the classifier path (pre-existing references elsewhere in the file, if any, unchanged).
- `rg 'spinning|FORK_|RegionTrend|classify_fork|recurring_regions' plan_tool/convergence_diagnosis.py` introduces no new matches beyond pre-existing comments.
- `diagnose_convergence` / `render_diagnosis` outputs unchanged for existing tests (classifier not wired yet).

## References

- [`docs/implementation-plans/2-convergence-non-severity-advisories.md`](docs/implementation-plans/2-convergence-non-severity-advisories.md) — Architecture § impact-recurrence, shrinkage definition, tie-break, and acceptance criteria.
- [`DATA_CONTRACT.md`](DATA_CONTRACT.md) — `Recommendation.impact` and `SavedReview.audit_stage` persisted shapes the classifier reads.
- [`docs/AUDIT_FLOW.md`](docs/AUDIT_FLOW.md) — checkpoint vs final roles (already enforced before this classifier runs).
- `plan_tool/convergence_diagnosis.py` — `_matches`, `_structural_recurs_in_streak`, `_is_resolved_in_run`, `WINDOW_SIZE`, `FindingChurn` (sibling advisory type pattern).
- `plan_tool/convergence.py` — `STAGE_BARE`, `STAGE_DETAIL`; stage bars intentionally **not** used for impact eligibility.
- [`BACKLOG.md`](BACKLOG.md) `#158` — original impact-recurrence outcome; this step ships detection only, not loop stop.

## Applicable guardrails

- **Plan intent (recommend-only advisories):** classifier only returns a frozen record — no `stop_reason`, exit-code, or `--fail-on-findings` changes; no plan mutation.
- **Step intent:** detect recurrence without shrinkage for explicit high-impact seams only; one seam via deterministic tie-break — do not widen to structural sources or severity-as-impact proxy.
- **Out of scope — retired vocabulary:** do not revive `spinning`, `FORK_*`, `recurring_regions`, or region-trending types.
- **Out of scope — loop control:** do not integrate with `should_continue`, reconcile iterate, or completeness iterate stop reasons.
- **Out of scope — automatic remedies:** do not invoke split, scope-out, or re-seed — conservative next-action **text** is step 5 render.
- **Convergence policy boundary (`CLAUDE.md`):** do not widen `is_blocking_impact` or completeness `material_new` rules for this advisory.

## Deferred

- Wiring `classify_impact_recurrence` into `diagnose_convergence` and `render_diagnosis` — step 5.
- Conservative next-action rendering strings — step 5 (classifier supplies seam identity counts only).
- Completeness-iterate stderr surfacing — step 6.
- Edit-drift classifier — step 4 (shares correlator only).
- Hard structural stop / `recurring_high_impact_seam` loop termination — `BACKLOG.md` `#158` remainder and `#231` provenance; explicitly out of plan scope.
- Splitting classifier into a separate leaf module — only if `convergence_diagnosis.py` growth forces it; not required for this step.
