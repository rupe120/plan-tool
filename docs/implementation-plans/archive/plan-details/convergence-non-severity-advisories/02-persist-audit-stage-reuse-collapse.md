> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Persist audit_stage, reuse-collapse correlator, and advisory result types

## Summary

This step makes the compatible-pass window readable from saved completeness history. It adds `audit_stage` to `SavedReview` and writes it on every new completeness sidecar, documents the field in `DATA_CONTRACT.md`, carries it onto `RunSnapshot`, and ships a reuse-collapse correlator that filters to completeness finals, requires a persisted stage, breaks on bare→detail transitions, and merges adjacent passes with identical finding-id sets. It also defines frozen `CompatiblePass`, `ImpactRecurrenceAdvisory`, and `EditDriftAdvisory` types for steps 3–5 — no classifier logic or `diagnose_convergence` wiring here. Primary touch points are `plan_tool/review_persistence.py`, `plan_tool/completeness_report.py`, and `plan_tool/convergence_diagnosis.py`. The main design choice is to derive `audit_stage` inside `write_completeness_report` when the caller omits it (so `completeness_phases.py` stays out of this step’s file list) rather than inferring stage from the plan’s current bundle at read time. When green, new completeness sidecars round-trip `audit_stage`, legacy sidecars load as `None` and are excluded from correlated sequences, and adjacent reuse-audit replays collapse to one logical pass.

## Table of Contents

- [Summary](#summary) — what changes and what stays the same
- [Why](#why) — why persisted stage and a correlator are needed now
- [Input](#input) — upstream contracts this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — paths touched
- [Implementation](#implementation) — persistence, flatten, correlator, and types
- [Tests](#tests) — cases and green gate
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — docs and symbols to read first
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — explicitly out of scope here

## Why

Steps 3 and 4 classify impact-recurrence and edit-drift over the **newest three consecutive compatible completeness passes**. “Compatible” means same `kind`, same persisted audit stage, and a logical sequence where reuse-audit replays do not count as separate confirmations. Today completeness sidecars persist fingerprints and findings but not which bare/detail bar the audit ran under; `diagnose_convergence` takes a live `audit_stage` argument from `convergence_cmd._current_audit_stage` instead of history. Without a persisted stage, a plan that moves from bare to detail would let classifiers mix passes audited under different bars, and without reuse collapse, `--reuse-audit --iterate` can write multiple timestamped finals with identical finding-id sets that look like independent confirmations. Checkpoint exclusion already lives in `load_report_history` via `_is_final_report_role`; this step adds the stage stamp and the collapsed pass sequence both downstream classifiers share.

## Input

**Stage vocabulary:** `plan_tool/convergence.py:STAGE_BARE` (`"bare"`) and `STAGE_DETAIL` (`"detail"`), validated by `_VALID_STAGES`.

**Stage derivation at save time (same rule completeness-audit already uses):** `plan_tool/cli/completeness_phases.py:derive_audit_stage` — `total == 0` or `is_fully_bare` → bare; otherwise detail. Never `status.is_bare` alone (step-less plans).

**History flatten path:** `load_report_history` → `_snapshot_from_saved_review` over finals whose `kind` is in `HISTORY_KINDS`. Checkpoint/final pairing is already done; this step does not duplicate it.

**Reuse-collapse identity:** finding-id set equality (`frozenset(f.id for f in snapshot.findings)`). Adjacent finals only; order is `ReportHistory.runs` (oldest→newest).

**What this step does not verify:** whether classifiers fire correctly (steps 3–4), whether advisories render (step 5), or whether completeness stderr shows them (step 6).

## Files (creates vs edits)

- **New files:** none

- **Existing files (edits only):**
  - `plan_tool/review_persistence.py` — add `audit_stage: Optional[str] = None` to `SavedReview`; add `audit_stage` kwarg to `save_review`; persist on completeness payloads; normalize on load via a small validator (accept only `_VALID_STAGES`, else `None`); thread through `load_review`.
  - `plan_tool/completeness_report.py` — add `audit_stage` kwarg to `write_completeness_report`; when writing a sidecar (`recommendations is not None`), ensure a stage is stamped (explicit kwarg or derive from `parse_plan` + `audit_detail_bundle_status` + `derive_audit_stage`); pass through to `save_review`.
  - `plan_tool/convergence_diagnosis.py` — add `audit_stage` to `RunSnapshot`; wire in `_snapshot_from_saved_review`; add frozen `CompatiblePass`, `ImpactRecurrenceAdvisory`, `EditDriftAdvisory`; add correlator (e.g. `build_collapsed_completeness_passes`) implementing completeness-only filter, missing-stage exclusion, stage-boundary breaks, and adjacent identical-id collapse.
  - `DATA_CONTRACT.md` — document `SavedReview.audit_stage` in the field table (completeness sidecars; `None`/absent = legacy unknown).
  - `plan_tool/data_contract.py` — add `audit_stage` to the `SavedReview` registry (`conditionally_persisted` is appropriate).
  - `tests/test_review_persistence.py` — save/load round-trip, invalid value → `None`, non-completeness kinds unaffected.
  - `tests/test_completeness_report.py` — derive-at-write path through `write_completeness_report` when `audit_stage` is omitted.
  - `tests/test_data_contract.py` — `audit_stage` registered under `SavedReview` `conditionally_persisted` (sibling of advisory/coverage fields).
  - `tests/test_convergence_diagnosis.py` — correlator cases using extended `_save` helper; `RunSnapshot.audit_stage` flatten case.

## Implementation

### Persist `audit_stage` on completeness sidecars

- **`SavedReview.audit_stage`:** `Optional[str] = None`. Meaning: the bare/detail bar under which the completeness audit ran (`STAGE_BARE` or `STAGE_DETAIL`). `None` means legacy or malformed — readers must not guess from the live plan.
- **`save_review`:** add keyword-only `audit_stage: Optional[str] = None`. When `kind == "completeness"`, write JSON key `audit_stage` only for validated values. Reject or raise when `kind == "completeness"` and the caller passes a non-`None` but invalid stage (invalid means not in `_VALID_STAGES`). Non-completeness kinds omit the key (same pattern as `plan_mass`).
- **No schema version bump:** treat `audit_stage` as an additive optional field like `plan_mass` / `audit_coverage` — older readers ignore unknown keys; older sidecars load as `None`.
- **`load_review`:** read optional `audit_stage`; normalize through the validator; never raise on bad legacy values.

### Thread stage through the completeness write path

`write_completeness_report` is the only production writer of completeness sidecars (called from `completeness_phases._persist_and_present_report`, which is **not** in this step’s file list).

- Add `audit_stage: Optional[str] = None` to `write_completeness_report`.
- When `recommendations is not None` and `audit_stage is None`, derive it at write time: `parse_plan(plan_path)` → `audit_detail_bundle_status(plan, plan_path, repo_root, detail_grade=GRADE_RUN)` → `derive_audit_stage(status)`. Use a lazy import of `derive_audit_stage` from `completeness_phases` inside the function to avoid widening import-time cycles (`completeness_phases` already lazy-imports `write_completeness_report`).
- Pass the resolved stage to `save_review(..., kind="completeness", audit_stage=stage)`.
- **Unconditional for run-grade sidecars:** whenever a completeness JSON sidecar is written, it carries `audit_stage`. Jira-grade runs that pass `recommendations=None` write no sidecar — unchanged.

**Rejected alternative:** inferring stage at correlator read time from the plan’s current bundle. That would attribute old reports to today’s stage after a bare→detail transition and break the plan’s “persisted stage per pass” rule.

### Carry stage on `RunSnapshot`

- Add `audit_stage: Optional[str] = None` to `RunSnapshot`.
- Set `audit_stage=review.audit_stage` in `_snapshot_from_saved_review`.
- Do not change `load_report_history` filtering — checkpoints stay excluded via `_is_final_report_role`.

### Reuse-collapse correlator

Add a public function in `convergence_diagnosis.py` (name is the implementer’s choice; e.g. `build_collapsed_completeness_passes`) that returns `tuple[CompatiblePass, ...]`:

1. **Source:** `ReportHistory.runs` (already finals-only, chronological).
2. **Completeness filter:** keep only `snapshot.kind == "completeness"`.
3. **Stage gate:** drop snapshots with `audit_stage is None` (legacy sidecars → insufficient evidence, not coerced).
4. **Adjacent collapse:** walk in order; when the current pass has the same `audit_stage` as the previous kept pass **and** `frozenset(f.id for f in findings)` equals the previous pass’s set, replace the previous logical pass with a **merged** snapshot: keep the newer pass’s `created_at`, `findings`, and `audit_stage`, and build `annotations` by finding id for **every id in either map** — any terminal disposition under `_is_resolved_in_run` (applied or decline-close) from **either** side beats any non-terminal annotation; only when both sides are non-terminal or both terminal does the newer pass win. Do not collapse across a stage boundary even if id sets match. Rationale: `save_review` defaults `annotations={}`, and a future reuse path may write explicit non-terminal markers; neither must erase older terminal dispositions.
5. **Stage boundary:** a change in `audit_stage` always starts a new logical pass (bare→detail starts a fresh sequence).

Expose a frozen **`CompatiblePass`** holding at least: `audit_stage`, `created_at`, `findings` (tuple), `annotations` (dict), and optionally `collapsed_count: int` (how many raw finals merged — useful for step 3 tests). One way: wrap the representative `RunSnapshot` plus `audit_stage` if you prefer not to duplicate fields.

**Rejected alternative:** re-filtering checkpoints inside the correlator. `load_report_history` already owns that; duplicating it risks drift.

### Advisory result types (shells only)

Define frozen dataclasses modeled on `FindingChurn` — recommend-only payloads, no blocking/severity tier, no verdict fields:

- **`ImpactRecurrenceAdvisory`** — fields steps 3/5 will populate, e.g. `window_audit_stage`, seam identity (`seam_source`, `seam_anchor`, `seam_step_id`, `seam_title_slug` or a single `seam_key` tuple), `passes_present`, `newest_matched_count`. No classifier function in this step.
- **`EditDriftAdvisory`** — e.g. `window_audit_stage`, `matched_findings: tuple[RunFinding, ...]`, `new_eligible_count`, `matched_count`. No classifier function in this step.

**Fields deliberately omitted** (exist on other finding types but not here): `blocking`, `severity`, verdict/stop-reason enums, any `RegionTrend` / `spinning` / `FORK_*` vocabulary.

### Invariants — do not change

- `diagnose_convergence`, `render_diagnosis`, `_open_medium_plus`, `_finding_churn`, and existing verdict logic — unchanged.
- `HISTORY_KINDS` and reconcile kinds in history — unchanged; correlator simply ignores non-completeness runs.
- No imports of retired fork/region APIs.
- `convergence_diagnosis.py` stays a cycle-free leaf (no `plan_tool.cli` imports at module level; lazy import inside `write_completeness_report` only).

### Shared locations (same logic, different steps)

| Location | This step | Reason |
|---|---|---|
| `plan_tool/cli/completeness_phases.py:_persist_and_present_report` | Deferred explicit `audit_stage=` threading | Out of `files:` list; self-derive in `write_completeness_report` satisfies acceptance |
| `plan_tool/cli/convergence_cmd.py:_current_audit_stage` | Deferred | Still used for live `diagnose_convergence` stage; history-backed classifiers arrive in steps 3–5 |
| `derive_audit_stage` in `completeness_phases.py` | Read-only / lazy-import | Consolidating into a leaf module is a separate refactor |

## Tests

### Tests for this step

Every test below must be green before this step is finished.

**`tests/test_review_persistence.py`**

- `test_completeness_sidecar_round_trips_audit_stage` — `save_review(kind="completeness", audit_stage="bare")` → JSON carries key → `load_review` returns `"bare"`.
- `test_audit_stage_invalid_on_load_becomes_none` — raw sidecar with `audit_stage: "bogus"` loads with `audit_stage is None`.
- `test_non_completeness_kind_omits_audit_stage` — `save_review(kind="review", audit_stage="detail")` does not persist the key (or load ignores it).
- `test_save_review_rejects_invalid_stage_for_completeness` — invalid stage on completeness save raises.

**`tests/test_completeness_report.py`**

- `test_write_completeness_report_derives_audit_stage_when_omitted` — call `write_completeness_report` with `recommendations` set and `audit_stage=None` → sidecar JSON / loaded review carries a valid `bare` or `detail` stage derived from the plan’s detail-bundle status (production path, not only direct `save_review`).

**`tests/test_data_contract.py`**

- `test_saved_review_audit_stage_is_conditionally_persisted` — `audit_stage` is registered on `SavedReview` under `conditionally_persisted` (same pattern as advisory/coverage siblings) so registry/doc drift fails if the field disappears.

**`tests/test_convergence_diagnosis.py`**

- `test_snapshot_carries_audit_stage_from_saved_review` — save with stage → `load_report_history` → newest `RunSnapshot.audit_stage` matches.
- `test_collapsed_passes_exclude_reconcile_kinds` — mix completeness + `detail-reconcile` finals → correlator output ignores reconcile runs.
- `test_collapsed_passes_exclude_missing_audit_stage` — legacy sidecar without stage omitted from output.
- `test_stage_change_breaks_compatible_sequence` — bare, bare, detail → correlator yields two stage groups (or trailing window over `"detail"` has length 1); three bare-only passes yield three logical passes.
- `test_adjacent_identical_id_sets_collapse` — two consecutive completeness finals with same finding ids → one `CompatiblePass`; ids differ → two passes.
- `test_adjacent_collapse_merges_annotations_from_older_final` — older final has `applied` (or decline-close) on an id; newer reuse replay has the same finding-id set and empty `annotations` → collapsed pass retains the terminal disposition for that id.
- `test_adjacent_collapse_terminal_beats_newer_non_terminal` — older final has terminal disposition on an id; newer adjacent final has explicit non-terminal/`open` annotation on the same id → collapsed pass keeps the terminal disposition.
- `test_checkpoint_final_pair_not_double_counted` — pre-apply checkpoint excluded by `load_report_history`; only finals feed correlator (regression guard).

Extend local `_save` / `_rewrite_role_payload` helpers to accept `audit_stage` so correlator tests do not hand-build JSON unless testing malformed load.

## Acceptance criteria

- `SavedReview.audit_stage` is documented in `DATA_CONTRACT.md` and registered in `plan_tool/data_contract.py` (`conditionally_persisted`; covered by `tests/test_data_contract.py`).
- Every new run-grade completeness sidecar written through `write_completeness_report` includes a valid `audit_stage` (`bare` or `detail`) — including when the caller omits the kwarg (derive-at-write; covered by `tests/test_completeness_report.py`).
- `load_review` round-trips `audit_stage`; absent or invalid values load as `None`.
- `load_report_history` sets `RunSnapshot.audit_stage` from the sidecar.
- `build_collapsed_completeness_passes` (or chosen name) returns only completeness passes with non-`None` stage, collapses adjacent identical finding-id sets within the same stage (merging annotations so older terminal dispositions survive an empty reuse replay), and does not collapse across stage changes.
- Frozen types `CompatiblePass`, `ImpactRecurrenceAdvisory`, and `EditDriftAdvisory` exist in `convergence_diagnosis.py`.
- `diagnose_convergence` / `render_diagnosis` behavior is unchanged (existing suite green).
- `rg 'spinning|FORK_|RegionTrend|classify_fork' plan_tool/convergence_diagnosis.py` returns nothing new beyond pre-existing comments, if any.

## References

- [`docs/implementation-plans/2-convergence-non-severity-advisories.md`](docs/implementation-plans/2-convergence-non-severity-advisories.md) — Architecture § compatible passes, reuse collapse, and acceptance criteria for `audit_stage`.
- [`DATA_CONTRACT.md`](DATA_CONTRACT.md) — `SavedReview` persisted-field table (add `audit_stage` row here).
- [`docs/AUDIT_FLOW.md`](docs/AUDIT_FLOW.md) — checkpoint vs final role; `derive_audit_stage` source map.
- `plan_tool/convergence.py` — `STAGE_BARE`, `STAGE_DETAIL`, `_VALID_STAGES`, `is_blocking_finding`.
- `plan_tool/cli/completeness_phases.py:derive_audit_stage` — stage derivation rule to mirror at save time.
- `plan_tool/convergence_diagnosis.py:load_report_history`, `_is_final_report_role`, `FindingChurn` — patterns for history loading and advisory result types.

## Applicable guardrails

- **Plan intent (recommend-only advisories):** this step persists evidence and builds the shared correlator only — no classifier, render, or stderr output.
- **Step intent (checkpoint pairing):** do not re-implement checkpoint/final filtering; consume `load_report_history` output as-is.
- **Out of scope — loop control:** no changes to iterate `stop_reason`, exit codes, or `--fail-on-findings`.
- **Out of scope — retired vocabulary:** do not import or reference `spinning`, `FORK_*`, `recurring_regions`, or region-trending types.
- **Out of scope — stage bars:** do not change `is_blocking_finding` / `is_blocking_impact` predicates.

## Deferred

- Impact-recurrence classifier (`classify_impact_recurrence` or equivalent) — step 3; consumes `CompatiblePass` sequences and returns `ImpactRecurrenceAdvisory`.
- Edit-drift classifier — step 4; returns `EditDriftAdvisory`.
- Wiring advisories into `diagnose_convergence` / `render_diagnosis` — step 5.
- Completeness-iterate stderr surfacing — step 6.
- Explicit `audit_stage=` argument threading in `completeness_phases._persist_and_present_report` — optional hardening once that module is in scope; self-derive in `write_completeness_report` covers acceptance for this step.
- Moving `derive_audit_stage` into a shared leaf module — consolidation refactor, not required here.
- Explicit on-disk reuse marker instead of identical-id collapse — plan defers to backlog if collapse proves insufficient.
- `RunFinding.impact` flatten (step 1) — independent; correlator does not need it.
