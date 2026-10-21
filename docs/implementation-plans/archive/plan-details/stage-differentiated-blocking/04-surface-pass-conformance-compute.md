> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Surface pass-conformance and compute conceptual bar-blocking set

## Summary

Add run-level pass-conformance aggregates (`conforming_pass_count`, `failed_or_malformed_pass_count`) on every live conceptual audit and on accepted reuse coverage, extend the coverage persistence chain so those keys survive sidecar round-trips, and compute `conceptual_bar_blocking_ids` as the stable finding ids where `is_blocking_finding` is true under the hoisted `audit_stage`. Wire all three conceptual sources — live `audit_plan_until_stable`, live `_sample_conceptual_audit`, and accepted reuse — plus reuse conformance gating (auto-decline vs explicit `audit_incomplete`). Primary touch points: `plan_tool/review.py` (per-pass outcome), `plan_tool/review_persistence.py` (exact-key normalize), `plan_tool/cli/completeness_cmd.py` and `completeness_phases.py` (bar set + reuse). Green means conformance counts land in `budget_report`/coverage, bar ids are computed with `classify_domain=classify_finding_domain` at detail stage, and reuse without conformance follows the settled auto-decline / `audit_incomplete` split — with `_completeness_has_blocking_findings`, JSON fields, and mid-run steering left for later steps.

## Table of Contents

- [Why](#why) — missing pass-conformance signal and severity-only conceptual blocking today.
- [Input](#input) — contracts from steps 1–3 and coverage shapes this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — touched paths only.
- [Implementation](#implementation) — pass outcome tracking, coverage keys, bar set, reuse gates, and boundaries.
- [Tests](#tests) — new cases and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes for reviewers and CI.
- [References](#references) — typing and pytest docs.
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step.
- [Deferred](#deferred) — follow-ups explicitly not in this step.

## Why

`completeness-audit` will gate finalize on a qualifying audit sample and a stage-aware conceptual bar, but HEAD has neither signal. Pass quality is approximated only by `advisory_valid` inside `plan_tool/review.py:_AuditSampleEvidence`, which is grade-gated arm-clustering input — not a conformance counter — and inner heading retries inside `check_plan_audit` are invisible to any outer-pass aggregate. Conceptual blocking in finalize still flows through `plan_tool/cli/completeness_cmd.py:_completeness_has_blocking_findings` via severity-only `is_blocking`, so bare/detail bars from steps 1–2 are unused. Coverage persistence is exact-key: `plan_tool/review_persistence.py:normalize_audit_coverage` rejects any dict whose keys are not exactly `_AUDIT_COVERAGE_KEYS`, so writer-only conformance fields are dropped and reuse cannot see them. Step 4 closes that gap before steps 5–6 steer the loop and expose JSON.

## Input

**From step 1** (`plan_tool/review.py`):

- `classify_finding_domain(rec) -> str` returning only `FINDING_DOMAIN_CODE_LOGIC`, `FINDING_DOMAIN_DOCS`, `FINDING_DOMAIN_UNIT_TEST`, or `FINDING_DOMAIN_UNKNOWN`.

**From step 2** (`plan_tool/convergence.py`):

- `is_blocking_finding(rec, *, stage, classify_domain=...)` with `STAGE_BARE` / `STAGE_DETAIL`.
- Detail stage: pass `classify_domain=classify_finding_domain` at every bar-evaluation call site in this step.
- Bare stage: do not pass `classify_domain` (predicate ignores domain).

**From step 3** (`plan_tool/cli/completeness_phases.py` / `plan_tool/cli/completeness_cmd.py`):

- Hoisted `audit_stage` (`derive_audit_stage(bundle_status)`) and `bundle_status` threaded into `_run_iterate_convergence_loop`, `finalize_completeness_run`, `_sample_conceptual_audit`, and `write_pre_apply_audit_checkpoint` before the iterate branch. Ordering in `cmd_completeness`: `_resolve_audit_reuse` → `derive_audit_stage` → iterate/finalize — bar evaluation must not run inside `_accept_reuse` (stage not hoisted yet).
- **`audit_stage`** (bar) vs **`bundle_status.is_bare`** (withhold/diagnostic): keep using `is_bare` for withhold paths; bar evaluation uses `audit_stage` only.

**HEAD audit/coverage shapes this step extends:**

- `plan_tool/review.py:check_plan_audit` — one **outer** pass per call; inner heading retry (`attempt` 1→2) stays inside that pass.
- `plan_tool/review.py:audit_plan_until_stable` — multi-pass loop; writes `budget_report` keys `budget_limited`, `passes_used`, `cap`, `confirmation_kind`, …
- `plan_tool/review.py:_PLAN_AUDIT_REQUIRED_HEADINGS` — both headings must be present for a conforming pass.
- `plan_tool/cli/completeness_phases.py:_coverage_input_from_reusable_audit` / `_coverage_for_sidecar` — unwrap and normalize coverage for reuse and sidecar write.
- `plan_tool/cli/completeness_phases.py:_IterateOutcome` — `.budget` dict carries coverage through the iterate path (reuse seeds it via `_coverage_input_from_reusable_audit`).

**Qualifying sample rule** (from plan Architecture; this step implements, step 6 consumes for clean):

- Qualifies when `conforming_pass_count >= 1` and `failed_or_malformed_pass_count == 0`.
- Bar clearance (`conceptual_bar_blocking_ids` empty) is **separate** from sample qualification.

**Already-implemented signal:** `tests/test_review.py` matches `def bar` in fixtures only — not prior art for this step.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `plan_tool/review.py` — per-outer-pass outcome on `_AuditSampleEvidence`; aggregate `conforming_pass_count` / `failed_or_malformed_pass_count` into `budget_report` from `audit_plan_until_stable`; pure qualifying-sample helper (recommended: `audit_coverage_qualifies_sample(coverage) -> bool`).
  - `plan_tool/review_persistence.py` — add keys to `_AUDIT_COVERAGE_KEYS`; extend `normalize_audit_coverage` and `project_audit_coverage` together.
  - `plan_tool/cli/completeness_cmd.py` — `compute_conceptual_bar_blocking_ids`; reuse conformance in `_resolve_audit_reuse` / `_accept_reuse`; thread `audit_incomplete` and `conceptual_bar_blocking_ids` through orchestration (`cmd_completeness`, `_run_iterate_convergence_loop`, `finalize_completeness_run` inputs); extend `_coverage_input_from_reusable_audit`.
  - `plan_tool/cli/completeness_phases.py` — compute bar set after `_sample_conceptual_audit`; extend `_IterateOutcome` with `conceptual_bar_blocking_ids` and `audit_incomplete`; pass `audit_stage` into audit paths that lack it.
  - `DATA_CONTRACT.md` — document `conforming_pass_count`, `failed_or_malformed_pass_count`, and `conceptual_bar_blocking_ids` (producer coverage keys + JSON field name for the id list).
  - `tests/test_review.py` — pass-conformance cases on `check_plan_audit` / `audit_plan_until_stable`.
  - `tests/test_convergence.py` — `compute_conceptual_bar_blocking_ids` / qualifying-sample cases using step-2 fixtures.
  - `tests/cli/test_completeness_cmd.py` — reuse conformance, bar set on three entry points, `audit_incomplete` on explicit reuse without conformance.
  - `tests/test_data_contract.py` — drift guard for new coverage fields in `DATA_CONTRACT.md`.

## Implementation

### Foundational logic: outer-pass conformance

**Per-outer-pass outcome** — extend `plan_tool/review.py:_AuditSampleEvidence` with a closed outcome (module-level string constants recommended), distinct from `advisory_valid`:

| Outcome | When |
| --- | --- |
| **conforming** | Invoker returned 0 **and** both `_PLAN_AUDIT_REQUIRED_HEADINGS` present after the inner retry loop finishes (a recovered inner retry still counts as one conforming outer pass). |
| **failed_or_malformed** | Invoker non-zero or raised; **or** headings still missing after the second attempt; **or** `audit_plan_until_stable`'s `pass_errored` flag is true for that outer pass. |
| **skipped** | No invoker attempt (e.g. `invoker is None`, no plan body) — increments **neither** counter. |

**Do not** repurpose `advisory_valid` / `advisory_invalid` for conformance — those remain arm-clustering inputs.

In `check_plan_audit`, classify each call's final outcome into `_AuditSampleEvidence`. In `audit_plan_until_stable`, walk every outer pass, increment `conforming_pass_count` or `failed_or_malformed_pass_count`, and write both totals into `budget_report` alongside existing keys. Skipped-without-attempt passes leave both counts unchanged.

Add a small pure helper (in `review.py` or `review_persistence.py`):

```text
audit_coverage_qualifies_sample(coverage: object) -> bool
```

Return `True` only when normalized coverage has `conforming_pass_count >= 1` and `failed_or_malformed_pass_count == 0`; `False` for missing, legacy-unknown, or malformed coverage.

### Coverage persistence (update together)

Extend `_AUDIT_COVERAGE_KEYS` with `conforming_pass_count` and `failed_or_malformed_pass_count`. Update in the **same change**:

- `normalize_audit_coverage` — exact-key gate; validate both as non-negative `int` (reject `bool`).
- `project_audit_coverage` — emit both on `"observed"`; `null` on `"unknown-legacy"`.
- `plan_tool/cli/completeness_phases.py:_coverage_input_from_reusable_audit` — forward both keys on unwrap.
- `_coverage_for_sidecar` — unchanged call shape; benefits automatically once normalize accepts the wider key set.

Legacy sidecars without the new keys normalize to `None` → unknown conformance (intended).

### Foundational logic: conceptual bar-blocking set

Add a pure helper (recommended home: `plan_tool/cli/completeness_cmd.py` or `completeness_phases.py`):

```text
compute_conceptual_bar_blocking_ids(
    recs,
    *,
    audit_stage: str,
    classify_domain=None,
) -> tuple[str, ...]
```

- Iterate conceptual recs (`plan-correctness` and `plan-completeness`); collect `rec.id` where `is_blocking_finding(rec, stage=audit_stage, classify_domain=classify_domain)` is true.
- **Detail** (`audit_stage == STAGE_DETAIL`): always pass `classify_domain=classify_finding_domain` (import from `plan_tool.review` at call sites only — not inside `convergence.py`).
- **Bare**: omit `classify_domain`.
- Return stable ids only (sorted tuple recommended for test determinism).
- Do **not** persist a `domain` field on `Recommendation`.

### Wire the three conceptual sources

Compute conformance + bar set over the **unioned** conceptual rec list before finalize/`--json` (step 6 reads the values; this step must produce them). `_resolve_audit_reuse` / `_accept_reuse` do **conformance gating and coverage unwrap only** — they must **not** call `compute_conceptual_bar_blocking_ids` (no `audit_stage` yet).

1. **Live iterate path** — after `audit_plan_until_stable` in `_run_iterate_convergence_loop`, read conformance from that call’s `budget_report`; run `compute_conceptual_bar_blocking_ids` on `_audit_recs` with hoisted `audit_stage`.
2. **Live audit-only path** — after `_sample_conceptual_audit`, same computation on returned recs + `_noniter_budget`.
3. **Accepted reuse (post-hoist)** — after `derive_audit_stage` in `cmd_completeness`, and again inside `_run_iterate_convergence_loop` when `reused_audit_recs is not None` (skips live `audit_plan_until_stable`), and on finalize’s reused-recs branch: read `conforming_pass_count` / `failed_or_malformed_pass_count` from threaded reusable coverage via `_coverage_input_from_reusable_audit` / normalized sidecar coverage (not live `budget_report`); run `compute_conceptual_bar_blocking_ids(..., audit_stage=..., classify_domain=classify_finding_domain when stage is detail)` on `reused_audit_recs`. Qualifying sample from persisted conformance only when it qualifies.

Store on `plan_tool/cli/completeness_phases.py:_IterateOutcome`:

- `conceptual_bar_blocking_ids: tuple[str, ...]`
- `audit_incomplete: bool`

**Every `_IterateOutcome` exit** — including `_halt()` (`early_exit_code=2`) — must populate those two fields when audit/reuse already ran (use values computed before the halt). Do not drop bar/incomplete on drift/parse halts while the normal return (~2833) carries them.

Thread parallel fields through the audit-only path into `finalize_completeness_run` (keyword-only parameters or a small frozen result bundle — pick one shape and use it at both entry points).

### `audit_incomplete` signal

Set `audit_incomplete=True` when there is **no** qualifying sample:

- **Live audit:** `failed_or_malformed_pass_count > 0` **or** `conforming_pass_count < 1` (includes errored-empty and skipped-without-attempt unions).
- **Explicit reuse** (`--reuse-audit` or `--reuse-audit-id` accepted): coverage does not qualify (missing/legacy conformance counts).
- **Auto-reuse** (non-interactive accept): do **not** set `audit_incomplete` — **decline** reuse and run a fresh audit instead (see below).

When `audit_incomplete`, leave `conceptual_bar_blocking_ids` empty or omit measurement — do not present an empty set as “measured none” (step 6 JSON follows the same rule).

Print the settled operator route on incomplete producers (reuse without conformance, failed invoker, malformed headings): re-run with a live sample (`--no-reuse-audit` when a weak sidecar caused it); do **not** suggest raising `--audit-passes` as the primary fix.

### Reuse conformance gates (`_resolve_audit_reuse`)

After freshness checks, before `_accept_reuse`:

- **`audit_coverage_qualifies_sample(ru.audit_coverage)` is false:**
  - **Explicit** `--reuse-audit` or pinned `--reuse-audit-id`: accept reuse (findings flow through) but set `audit_incomplete=True` on the outcome path.
  - **Auto-accept** (`--yes`, `--json`, non-TTY, or interactive Yes): **decline** — return `None` and run a fresh audit (same as stale decline; no non-zero exit from reuse alone).

Accepted reuse **with** conformance may count as the qualifying sample with **no** live Claude pass; bar ids are still computed separately from the saved union.

### What stays unchanged

- **`_completeness_has_blocking_findings`** — conceptual arm still uses `is_blocking(r.severity)` until step 6.
- **`ConvergenceState.has_blocking_findings`** — deterministic-only; no stage bar (step 5).
- **Mid-run stop remapping** to `terminal_hand_apply` — step 5.
- **`--json` / `--fail-on-findings` / CLI help** exposure of `stage`, `conceptual_bar_blocking_ids`, `audit_incomplete` — step 6 (this step computes and threads internally).
- **`emit_coverage_unconfirmed` / `_render_coverage_confidence_markdown`** qualifying-sample alignment — step 6.
- **Unconditional `_completeness_has_blocking_findings` arms** (`files_coh_issues`, etc.) — plan Out of scope.

### Rejected alternative

Using `advisory_valid` as conformance — conflates heading presence with arm-clustering grade gating and breaks the inner-retry / outer-pass cardinality rule.

## Tests

Green-before-done: every test below passes before the step is done.

### Tests for this step

**`tests/test_review.py`**

- `test_check_plan_audit_conforming_pass_both_headings` — exit 0 + both headings → conforming outcome; inner retry not required.
- `test_check_plan_audit_inner_retry_still_one_conforming_outer_pass` — first response missing heading, second recovers → one conforming, zero failed.
- `test_check_plan_audit_failed_invoker_increments_failed_not_conforming` — non-zero exit → failed_or_malformed.
- `test_check_plan_audit_missing_headings_after_retry_is_failed` — still missing after attempt 2 → failed_or_malformed.
- `test_check_plan_audit_skipped_without_invoker_counts_neither` — `invoker=None` → skipped; both aggregate counts stay 0.
- `test_audit_plan_until_stable_writes_conformance_counts_to_budget_report` — multi-pass stub: totals in `budget_report`.
- `test_audit_plan_until_stable_pass_errored_counts_as_failed` — `pass_errored` outer pass increments `failed_or_malformed_pass_count`.

**`tests/test_convergence.py`** (or `tests/cli/test_completeness_cmd.py` if the helper lives there)

- `test_compute_conceptual_bar_blocking_ids_bare_medium_correctness_blocks` — bare stage: medium `plan-correctness` id present.
- `test_compute_conceptual_bar_blocking_ids_bare_medium_completeness_advisory` — bare stage: medium `plan-completeness` id absent.
- `test_compute_conceptual_bar_blocking_ids_detail_docs_medium_demoted` — detail + `classify_finding_domain`: docs-shaped medium absent.
- `test_compute_conceptual_bar_blocking_ids_detail_unknown_medium_blocks` — detail: `unknown` domain medium present.
- `test_audit_coverage_qualifies_sample_requires_conforming_and_no_failures` — parametrized qualifying-sample predicate.

**`tests/cli/test_completeness_cmd.py`**

- `test_auto_reuse_declines_when_conformance_missing` — non-interactive fresh sidecar without new keys → reuse declined, fresh audit path.
- `test_explicit_reuse_without_conformance_sets_audit_incomplete` — `--reuse-audit` with legacy coverage → reuse accepted, `audit_incomplete=True`.
- `test_explicit_reuse_with_conformance_qualifies_sample` — sidecar with conforming≥1, failed=0 → qualifying sample without live audit.
- `test_iterate_path_computes_bar_blocking_ids_with_audit_stage` — stubbed audit + hoisted stage → non-empty ids when bar blocks.
- `test_iterate_reuse_path_computes_bar_after_hoist` — `reused_audit_recs` + empty live audit; bar ids computed with hoisted `audit_stage` before loop body; `_accept_reuse` does not call bar helper.
- `test_audit_only_reuse_path_computes_bar_after_hoist` — `--no-iterate` + accepted reuse → finalize inputs carry bar ids / `audit_incomplete` from post-hoist computation.
- `test_halt_outcome_carries_bar_and_incomplete` — after audit seeded, `_halt(...)` return includes `conceptual_bar_blocking_ids` and `audit_incomplete`.
- `test_reuse_conformance_reads_coverage_input_not_live_budget_report` — reuse iterate seeds conformance from `_coverage_input_from_reusable_audit`, not `audit_plan_until_stable`’s `budget_report`.
- `test_audit_incomplete_omits_measured_empty_bar_set` — incomplete path does not assert “measured clean” via empty ids alone.

**`tests/test_data_contract.py`**

- `test_data_contract_documents_conformance_coverage_keys` — `DATA_CONTRACT.md` `coverage` table lists `conforming_pass_count` and `failed_or_malformed_pass_count`.
- `test_normalize_audit_coverage_accepts_extended_key_set` — full producer dict with new keys normalizes non-`None`.

## Acceptance criteria

- `_AuditSampleEvidence` (or equivalent) records per-outer-pass conforming / failed_or_malformed / skipped outcomes; inner heading retry does not create a second outer failed pass.
- `audit_plan_until_stable` writes `conforming_pass_count` and `failed_or_malformed_pass_count` into `budget_report`.
- `_AUDIT_COVERAGE_KEYS`, `normalize_audit_coverage`, `project_audit_coverage`, `_coverage_input_from_reusable_audit`, and `_coverage_for_sidecar` all accept the extended key set together.
- `compute_conceptual_bar_blocking_ids` uses `is_blocking_finding` with `classify_domain=classify_finding_domain` when `audit_stage == STAGE_DETAIL`.
- All three conceptual sources (live iterate, live audit-only, accepted reuse post-hoist) produce `conceptual_bar_blocking_ids` and conformance-aware `audit_incomplete` on `_IterateOutcome` / finalize inputs; `_accept_reuse` does not compute the bar; `_halt()` preserves bar/incomplete when already computed.
- Accepted-reuse conformance reads `_coverage_input_from_reusable_audit` / normalized sidecar coverage on both iterate and audit-only paths.
- Auto-reuse without conformance declines to a fresh audit; explicit `--reuse-audit` / `--reuse-audit-id` without conformance accepts reuse with `audit_incomplete=True`.
- Accepted reuse with qualifying conformance counts as the qualifying sample without a live pass.
- `DATA_CONTRACT.md` documents the new coverage keys and names `conceptual_bar_blocking_ids` for the JSON field.
- `rg 'is_blocking_finding' plan_tool/cli/completeness_phases.py` shows bar evaluation only through `compute_conceptual_bar_blocking_ids` (not yet in `_completeness_has_blocking_findings`).
- Full pytest on the four test modules above is green.

## References

- [typing](https://docs.python.org/3/library/typing.html) — `Callable` for the `classify_domain` callback at CLI call sites.
- [PEP 3102](https://peps.python.org/pep-3102/) — keyword-only `audit_stage` / coverage threading on extended signatures.
- [pytest parametrize](https://docs.pytest.org/en/stable/how-to/parametrize.html) — qualifying-sample and per-pass outcome tables.

## Applicable guardrails

- **Plan step intent** — pass-conformance + bar set + coverage-key extension + reuse conformance only; do not wire finalize clean, JSON exposure, or mid-run `terminal_hand_apply` remapping here.
- **Plan Out of scope** — no changes to `_completeness_has_blocking_findings` unconditional arms; no `Recommendation.domain` persistence; no `is_blocking_impact` expansion; no reporting polish.
- **Plan Architecture qualifying sample** — sample qualification uses conformance aggregates only; `confirmation_kind` and `budget_limited` do not gate qualification in this step (step 6 aligns callouts).

## Deferred

- Mid-run `terminal_hand_apply` remapping and remedy surfaces — step 5 (`plan_tool/cli/completeness_phases.py:_run_iterate_convergence_loop`).
- Finalize `clean`, `--json` `stage` / `has_blocking_findings` bar-awareness, `--fail-on-findings`, CLI help — step 6.
- `emit_coverage_unconfirmed` and `_render_coverage_confidence_markdown` qualifying-sample suppression — step 6.
- Reporting polish (stop-reason vocabulary, set-aside handoff copy) — plan Deferred / BACKLOG.
- Persisted `Recommendation.domain` — plan Out of scope.
