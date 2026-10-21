> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Add stage-aware `is_blocking_finding` with `classify_domain` callback

## Summary

Add `is_blocking_finding(rec, *, stage, classify_domain=...)` to `plan_tool/convergence.py` as the stage-aware blocking predicate for completeness conceptual findings. Bare stage blocks by source axis plus severity (no domain call); detail stage demotes medium docs/unit-test conceptual findings via an injected `classify_domain` callback from step 1. Leave `is_blocking`, `is_blocking_impact`, and `should_continue` unchanged — no caller wiring in this step. Tests in `tests/test_convergence.py` pin bare/detail arms, a synthetic BACKLOG #248 four-round count fixture at `tests/fixtures/convergence/bare-bar-four-round-sample.json`, and separate conceptual fixtures for domain demotion. Green means the predicate exists, old helpers behave as today, and the bare bar would not have exited early on the #248 sample.

## Table of Contents

- [Why](#why) — why severity-only blocking is wrong for completeness and what this step adds.
- [Input](#input) — contracts from step 1 and `Recommendation` fields the predicate reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — touched paths only.
- [Implementation](#implementation) — predicate shape, bare/detail rules, fixture, and boundaries.
- [Tests](#tests) — new cases and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes for reviewers and CI.
- [References](#references) — typing and pytest docs.
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step.
- [Deferred](#deferred) — follow-ups explicitly not in this step.

## Why

`completeness-audit` needs different blocking bars at bare vs detail-grounded stages, but `plan_tool/convergence.py:is_blocking` keys only on severity. That mislabels BACKLOG #248’s bare-plan sample: medium `plan-completeness` findings should not stop a bare gate, while medium `plan-correctness` findings should — and at detail, medium docs/unit-test findings should be advisory while medium code-logic stays blocking (#91). Step 1 supplies `classify_finding_domain`; this step adds the stage-aware predicate that consumes it through a callback so `convergence.py` stays a leaf module with no runtime import of `plan_tool.review`.

## Input

**From step 1** (`plan_tool/review.py`):

- `classify_finding_domain(rec) -> str` returning only `FINDING_DOMAIN_CODE_LOGIC` (`"code-logic"`), `FINDING_DOMAIN_DOCS` (`"docs"`), `FINDING_DOMAIN_UNIT_TEST` (`"unit-test"`), or `FINDING_DOMAIN_UNKNOWN` (`"unknown"`).
- Tests may import `classify_finding_domain` and the #91 conceptual `Recommendation` builders from `tests/test_review.py`; production `plan_tool/convergence.py` must not.

**`Recommendation` fields this step reads:**

- `source` — distinguishes conceptual (`plan-correctness`, `plan-completeness`) from everything else.
- `severity` — `critical` | `high` | `medium` | `nit` | `info`.
- **Not read:** `impact`, `complexity`, `anchor`, `id`, `body`/`title` (except indirectly when tests pass `classify_finding_domain`, which reads them).

**Closed stage vocabulary** (mint module constants, spellings load-bearing for later JSON):

- `STAGE_BARE` → `"bare"`
- `STAGE_DETAIL` → `"detail"`

Invalid `stage` values should raise `ValueError` (or equivalent) rather than falling through to a default — later steps thread the same strings into finalize JSON.

## Files (creates vs edits)

- **New files:**
  - `tests/fixtures/convergence/bare-bar-four-round-sample.json` — synthetic per-round source/severity counts from BACKLOG #248’s four-round measurement table (counts only, not full finding prose).
- **Existing files (edits only):**
  - `plan_tool/convergence.py` — stage constants, conceptual-source helper, `is_blocking_finding`; docstring on `is_blocking` unchanged in behavior.
  - `tests/test_convergence.py` — `TestIsBlockingFinding` (or equivalent), fixture loader, regression guard that `is_blocking` / `is_blocking_impact` cases still pass unchanged.

## Implementation

### Public API

Add keyword-only:

```text
is_blocking_finding(
    rec: Recommendation,
    *,
    stage: str,
    classify_domain: Callable[[Recommendation], str] | None = None,
) -> bool
```

Export `is_blocking_finding`, `STAGE_BARE`, and `STAGE_DETAIL`. Keep `is_blocking`, `is_blocking_impact`, `BLOCKING_SEVERITIES`, `should_continue`, and `ConvergenceState.has_blocking_findings` **unchanged** — mid-run deterministic blocking and reconcile materiality stay on the old helpers until later steps wire the stage bar at call sites.

**Leaf discipline:** `Recommendation` stays under `TYPE_CHECKING` only; do not add a runtime `from plan_tool.review import …` in `convergence.py`. Domain labeling is entirely the injected `classify_domain` callback (callers pass `classify_finding_domain` starting in step 4).

**Design choice:** a new function beside `is_blocking` / `is_blocking_impact`, not an extension of either. Rejected alternative: folding stage into `is_blocking_impact` — that helper owns reconcile/convergence-diagnosis materiality and must stay separate per the plan’s convergence policy boundary.

### Conceptual vs non-conceptual

Treat `rec.source in {"plan-correctness", "plan-completeness"}` as conceptual (a private `_CONCEPTUAL_SOURCES` frozenset is fine). All other sources are **non-conceptual** and use severity-only via `is_blocking(rec.severity)` at every stage — no `classify_domain` call, no source-axis split.

### Bare stage (`stage=STAGE_BARE`)

**Never call `classify_domain`.** Pin that with a test whose callback raises if invoked.

| Finding kind | Blocks when |
| --- | --- |
| `plan-correctness` | `is_blocking(severity)` — medium, high, or critical |
| `plan-completeness` | severity is `high` or `critical` only |
| Either conceptual source | `nit` / `info` → never |
| Non-conceptual | `is_blocking(severity)` |

This is the #248 bar: correctness unsoundness blocks at medium+; completeness gaps at bare block only when high/critical.

### Detail stage (`stage=STAGE_DETAIL`)

**Conceptual findings:**

| Severity | Behavior |
| --- | --- |
| `high` / `critical` | always block |
| `nit` / `info` | never block |
| `medium` | call `classify_domain(rec)` when provided; if `classify_domain is None`, treat domain as `"unknown"` (blocks). Block iff domain is `code-logic` or `unknown`; do **not** block for `docs` or `unit-test`. |

**Non-conceptual:** `is_blocking(rec.severity)` only — no domain call.

One way to structure the medium branch: compute `domain = classify_domain(rec) if classify_domain is not None else "unknown"`, then block when `domain in {"code-logic", "unknown"}`.

### #248 synthetic fixture

Author `tests/fixtures/convergence/bare-bar-four-round-sample.json` with four rounds mirroring BACKLOG #248’s count table (round → breakdown by `plan-correctness` / `plan-completeness` and severity buckets). Include a `_comment` stating counts are synthetic and prose is not from the original run.

Tests expand each round into minimal `Recommendation` rows (one rec per count cell, distinct ids) and assert:

1. **`is_blocking` tallies** — document how many findings per round would block under the legacy severity-only rule (sanity anchor for the fixture).
2. **Bare bar not over-permissive** — for **every** round, `any(is_blocking_finding(rec, stage=STAGE_BARE) for rec in round_recs)` is `True`. A round that would have allowed `no_blocking_findings` under the bare bar is a defect (#248 Verification: rounds 3–4 still carried genuine high correctness defects; the bar must not exit early).

Do **not** claim the fixture’s prose matches the example app audit; domain/detail behavior uses separately authored conceptual fixtures (reuse step 1’s #91 builders where helpful).

### Call sites (read-only at HEAD — zero edits this step)

At HEAD, conceptual blocking in finalize flows through `plan_tool/cli/completeness_cmd.py:_completeness_has_blocking_findings`, which ends with `any(is_blocking(r.severity) for r in audit_recs)`. That line and every completeness iterate/mid-run path stay untouched until steps 3–6. **In-repo caller set for `is_blocking_finding` at step 2 completion: empty** — keyword-only API with no production imports yet.

Shared logic note: `plan_tool/convergence_diagnosis.py` also partitions on `plan-correctness` / `plan-completeness` sources; it does not use blocking predicates and is out of scope.

### Gotchas

- **`impact` is ignored** — `is_blocking_finding` is not `is_blocking_impact`; do not consult `rec.impact`.
- **Folded LOW→medium** — accepted plan cost; bare blocks medium correctness even when the model meant “low.”
- **Callback default at detail** — missing `classify_domain` → `unknown` → medium blocks; callers in step 4+ must pass `classify_domain=classify_finding_domain` at detail stage.
- **Do not write the stage bar into `ConvergenceState.has_blocking_findings`** — settled mid-run rule 2; wiring is step 5.

## Tests

Green-before-done: every test below must pass before the step is finished. Existing `tests/test_convergence.py` cases for `is_blocking`, `is_blocking_impact`, `should_continue`, and related helpers must remain green without behavior changes.

### Tests for this step

**Regression (unchanged behavior — run full file, not only new class):**

- All existing `test_is_blocking*` / `test_is_blocking_impact*` / `should_continue` cases — no edits to expected outcomes unless a test was incorrectly coupled to a symbol this step adds (there should be none).

**Bare stage (`TestIsBlockingFinding` or split sub-classes):**

- `test_bare_medium_plan_correctness_blocks` — `source="plan-correctness"`, `severity="medium"` → `True`.
- `test_bare_medium_plan_completeness_non_blocking` — `source="plan-completeness"`, `severity="medium"` → `False`.
- `test_bare_high_or_critical_completeness_blocks` — parametrized `high` / `critical` on `plan-completeness` → `True`.
- `test_bare_low_correctness_non_blocking` — `severity="low"` is not in `BLOCKING_SEVERITIES`; if the parser never emits `low`, use the lowest non-blocking conceptual severity the schema allows and document the pin.
- `test_bare_nit_info_conceptual_never_block` — both conceptual sources at `nit` / `info` → `False`.
- `test_bare_non_conceptual_uses_severity_only` — e.g. `source="data-contract"`, `severity="medium"` → `True`.
- `test_bare_never_invokes_classify_domain` — callback raises; bare medium completeness still returns `False`.

**Detail stage:**

- `test_detail_high_critical_conceptual_always_blocks` — both conceptual sources.
- `test_detail_nit_info_conceptual_never_blocks` — both conceptual sources.
- `test_detail_medium_code_logic_blocks` — inject callback returning `"code-logic"` → `True`.
- `test_detail_medium_docs_advisory` — callback returns `"docs"` → `False`.
- `test_detail_medium_unit_test_advisory` — callback returns `"unit-test"` → `False`.
- `test_detail_medium_unknown_blocks` — callback returns `"unknown"` → `True`.
- `test_detail_missing_callback_treats_medium_as_unknown` — `classify_domain=None`, medium conceptual → `True`.
- `test_detail_non_conceptual_skips_domain` — callback raises; non-conceptual medium still follows `is_blocking`.
- `test_detail_docs_fixture_demoted_with_classify_finding_domain` — step 1 docs-shaped #91 `Recommendation` + `classify_finding_domain` + `stage=STAGE_DETAIL` → `False`.
- `test_detail_code_logic_fixture_blocks_with_classify_finding_domain` — step 1 code-logic #91 fixture → `True`.

**#248 fixture:**

- `test_bare_bar_four_round_sample_is_blocking_tallies` — load JSON; per-round `is_blocking` counts match fixture metadata (or computed expectations documented in the test).
- `test_bare_bar_four_round_sample_stays_blocking_all_rounds` — every round has ≥1 rec with `is_blocking_finding(..., stage=STAGE_BARE)` true.

**Leaf discipline (recommended):**

- `test_convergence_has_no_runtime_review_import` — source scan of `plan_tool/convergence.py` finds no runtime `plan_tool` import (mirror `tests/test_rate_limit_loop.py:test_leaf_has_no_first_party_runtime_import` pattern).

## Acceptance criteria

- `is_blocking_finding`, `STAGE_BARE`, and `STAGE_DETAIL` exist in `plan_tool/convergence.py`.
- Bare: medium+ `plan-correctness` blocks; `plan-completeness` blocks only at high/critical; `classify_domain` never called.
- Detail: medium conceptual blocks only for `code-logic` and `unknown`; `docs` / `unit-test` medium demoted; missing callback → `unknown`.
- Non-conceptual findings use `is_blocking(severity)` at both stages with no domain call.
- `is_blocking` and `is_blocking_impact` behavior unchanged (full `tests/test_convergence.py` green).
- `tests/fixtures/convergence/bare-bar-four-round-sample.json` exists; four-round bare-bar-not-over-permissive test passes.
- Detail demotion test uses `classify_finding_domain` on a docs-domain conceptual fixture.
- `rg 'is_blocking_finding' plan_tool/` shows only `plan_tool/convergence.py` (no premature completeness wiring).
- `rg 'from plan_tool.review' plan_tool/convergence.py` shows `TYPE_CHECKING` guard only (or zero runtime imports).

## References

- [typing](https://docs.python.org/3/library/typing.html) — `Callable[[Recommendation], str] | None` on `classify_domain`; keep `Recommendation` under `TYPE_CHECKING`.
- [PEP 3102](https://peps.python.org/pep-3102/) — keyword-only `stage` and `classify_domain` after `*`.
- [pytest parametrize](https://docs.pytest.org/en/stable/how-to/parametrize.html) — bare/detail severity and source matrices.

## Applicable guardrails

- **Plan Out of scope — reporting polish** — no CLI help, JSON fields, report copy, or stop-reason vocabulary in this step.
- **Plan Out of scope — stage bar in other loops** — do not wire into reconcile, create, or detail iteration loops.
- **Plan Out of scope — persisted `Recommendation.domain`** — predicate uses ephemeral callback output only.
- **Plan Out of scope — `is_blocking_impact`** — do not fold stage or domain into reconcile materiality.
- **Plan Out of scope — `_completeness_has_blocking_findings` arms** — leave `files_coh_issues` and other non-conceptual arms untouched (`plan_tool/cli/completeness_cmd.py:_completeness_has_blocking_findings`).
- **Step intent** — ship the predicate and tests only; synthetic #248 counts for `is_blocking` tallies plus bare-bar-not-over-permissive check; detail/domain cases on separate conceptual fixtures.

## Deferred

- Stage hoisting before iterate/audit-only branch — step 3 (`plan_tool/cli/completeness_cmd.py`, `plan_tool/cli/completeness_phases.py`).
- Pass-conformance, `conceptual_bar_blocking_ids`, and mid-run bar steering — steps 4–5.
- `_completeness_has_blocking_findings` conceptual arm swap to `is_blocking_finding` — step 6.
- Finalize/`--json`/`--fail-on-findings`/`DATA_CONTRACT.md` stage fields — step 6.
- Reporting polish (BACKLOG #260) — follow-up after core ships.
- Classifier live-rate corpus — plan Deferred.
- Persisted domain on `Recommendation` — plan Out of scope.
