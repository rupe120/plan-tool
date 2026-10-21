> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Carry stage bar into finalize, `--json`, `--fail-on-findings`, and CLI help

## Summary

Wire the stage-aware conceptual bar from steps 2–5 into finalize, machine output, and CI gating: `_completeness_has_blocking_findings` switches its conceptual arm to `is_blocking_finding` under the hoisted `audit_stage`, `--json` exposes `stage`, `conceptual_bar_blocking_ids`, and `audit_incomplete`, and `--fail-on-findings` exits 1 on incomplete samples or bar-aware blockers. Finalize owns the clean signal (qualifying pass-conformance sample ∧ `not budget_limited` ∧ bar-aware `has_blocking_findings=false` ∧ eligible `outcome.stop_reason`) without a separate `clean` JSON key. `_render_coverage_confidence_markdown` and `emit_coverage_unconfirmed` warn whenever `budget_limited` is true, regardless of pass-conformance (corrected 2026-08-10 — see Implementation). Primary touch points: `plan_tool/cli/completeness_cmd.py`, `plan_tool/cli/completeness_phases.py`, `DATA_CONTRACT.md`, generated CLI reference, and `tests/cli/test_completeness_cmd.py`. Green means bar-aware blocking matches bare/detail rules in unit tests, JSON/fail-on-findings agree, incomplete audits never present an empty bar id list as “measured clean,” and `python -m plan_tool.cli_reference --write` plus `tests/cli/test_cli_reference.py` pass.

## Table of Contents

- [Why](#why) — severity-only finalize blocking hides the stage bar from JSON and CI.
- [Input](#input) — contracts from steps 2–5 this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — touched paths only.
- [Implementation](#implementation) — bar-aware gate, finalize clean, JSON, coverage callouts, help, and boundaries.
- [Tests](#tests) — new cases and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes for reviewers and CI.
- [References](#references) — typing and pytest docs.
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step.
- [Deferred](#deferred) — follow-ups explicitly not in this step.

## Why

Steps 2–5 add `is_blocking_finding`, hoisted `audit_stage`, pass-conformance + `conceptual_bar_blocking_ids`, and mid-run `terminal_hand_apply` steering — but finalize and `--json` still gate on `_completeness_has_blocking_findings` via severity-only `is_blocking` over conceptual recs. That keeps bare-plan medium `plan-completeness` findings blocking CI, hides which conceptual ids the bar selected, and lets `budget_limited` warn operators that clean is “not fully validated” even when pass-conformance already qualifies. This step makes machine consumers and `--fail-on-findings` read the same bar the loop steered on, and ties finalize clean to `outcome.stop_reason` after step 5’s remap.

## Input

**From step 2** (`plan_tool/convergence.py`):

- `STAGE_BARE` / `STAGE_DETAIL` — closed stage strings.
- `is_blocking_finding(rec, *, stage, classify_domain=...)` — bare arm ignores domain; detail arm needs `classify_domain=classify_finding_domain`.

**From step 1** (`plan_tool/review.py`):

- `classify_finding_domain(rec) -> str` — import at CLI call sites only, not inside `plan_tool/convergence.py`.

**From step 3** (`plan_tool/cli/completeness_phases.py` / `plan_tool/cli/completeness_cmd.py`):

- Hoisted `audit_stage` from `derive_audit_stage(bundle_status)` and precomputed `bundle_status` passed into `finalize_completeness_run`.
- `audit_stage` is the bar; `bundle_status.is_bare` stays on withhold/hand-edit remedy paths only.

**From step 4** (`plan_tool/cli/completeness_cmd.py`, `plan_tool/review.py`, `plan_tool/review_persistence.py`):

- `compute_conceptual_bar_blocking_ids(recs, *, audit_stage, classify_domain=...)` — stable id tuple where the bar is true (post-hoist on reuse consumers).
- `audit_coverage_qualifies_sample(coverage) -> bool` — true only when normalized coverage has `conforming_pass_count >= 1` and `failed_or_malformed_pass_count == 0`.
- `conceptual_bar_blocking_ids` and `audit_incomplete` on `_IterateOutcome` and parallel finalize inputs (audit-only and reused-recs branches; `_halt` preserves them).
- Coverage persistence exposes `conforming_pass_count` / `failed_or_malformed_pass_count` through `project_audit_coverage` / `_project_audit_coverage_for_public_output`.

**From step 5** (`plan_tool/cli/completeness_cmd.py`):

- `_IterateOutcome.stop_reason` after bar remap — finalize reads this for clean eligibility, not the loop-local `_loop_stop_reason` variable alone.
- `terminal_hand_apply`, `manual_fix_blocking_findings`, and halt reasons (`halted: *`) are not clean-eligible; `blocked` is treated as an alias of `manual_fix_blocking_findings` at eligibility check only (no new writer).

**HEAD shapes this step extends (do not re-derive):**

- `plan_tool/cli/completeness_cmd.py:_completeness_has_blocking_findings` — non-conceptual arms stay as today (`files_coh_issues` still accepted but not read).
- `plan_tool/cli/completeness_phases.py:_render_completeness_json` — caller supplies `has_blocking`; this step adds stage/bar/incomplete fields.
- `plan_tool/cli/completeness_phases.py:emit_coverage_unconfirmed` and `_render_coverage_confidence_markdown` — both key off `budget_limited` today without qualifying-sample checks.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/completeness_cmd.py` — bar-aware `_completeness_has_blocking_findings`; finalize clean eligibility helper; thread stage/bar/incomplete into blocking + fail-on-findings; completeness-specific argparse help (`completeness-audit` summary, `--json`, shared `--fail-on-findings` completeness clause).
  - `plan_tool/cli/completeness_phases.py` — extend `_render_completeness_json` payload; align `emit_coverage_unconfirmed` and `_render_coverage_confidence_markdown` with `audit_coverage_qualifies_sample`; optional small shared helper for “suppress budget-limited unconfirmed warning.”
  - `DATA_CONTRACT.md` — document `stage`, `conceptual_bar_blocking_ids`, `audit_incomplete`, bar-aware `has_blocking_findings`, and conformance keys on `coverage` (if step 4 landed producer keys but not doc rows).
  - `docs/cli/completeness-audit.md` — regenerate via `python -m plan_tool.cli_reference --write` (not hand-edited).
  - `docs/cli/README.md` — regenerated index entry for completeness-audit summary drift.
  - `tests/cli/test_completeness_cmd.py` — bar-aware blocking, JSON fields, fail-on-findings + incomplete, coverage callout suppression, finalize stop-reason eligibility.
  - `tests/cli/test_cli_reference.py` — no logic change expected; must stay green after help regeneration.

## Implementation

### Foundational logic: bar-aware finalize blocking

Switch the **conceptual arm only** of `plan_tool/cli/completeness_cmd.py:_completeness_has_blocking_findings`:

- Add keyword-only `audit_stage: str` (required at finalize/JSON call sites once steps 3–4 thread it).
- Replace `any(is_blocking(r.severity) for r in audit_recs)` with a bar check over conceptual sources:
  - **Detail** (`audit_stage == STAGE_DETAIL`): `any(is_blocking_finding(r, stage=audit_stage, classify_domain=classify_finding_domain) for r in audit_recs)`.
  - **Bare**: `any(is_blocking_finding(r, stage=audit_stage) for r in audit_recs)` — do not pass `classify_domain`.
- Leave every non-conceptual arm unchanged (path style, deps, body, detail coverage/body, lessons, data-contract, self-consistency, purity coverage). Do not start reading `files_coh_issues` (plan Out of scope / `BUG_BACKLOG.md`).

**Rejected alternative:** recomputing bar ids inside `_completeness_has_blocking_findings` instead of trusting step 4’s `conceptual_bar_blocking_ids` — duplicates logic; use `is_blocking_finding` here for the boolean gate and pass through the precomputed id tuple for JSON.

When `audit_incomplete` is true, treat the audit as **not clean** for finalize/`--fail-on-findings` even if the deterministic arms are clear (see below). The boolean gate may still evaluate deterministic arms; incomplete is enforced explicitly on exit paths.

### Foundational logic: finalize clean eligibility

Add a small pure helper in `plan_tool/cli/completeness_cmd.py` (name is implementer’s choice), used only on the finalize tail:

**Inputs:** `audit_incomplete`, bar-aware `has_blocking` (from `_completeness_has_blocking_findings`), `selected_audit_coverage` (budget / sidecar projection), `outcome.stop_reason` (after step 5 remap; `None` on audit-only empty `_IterateOutcome`).

**Clean when all hold:**

1. `audit_incomplete` is false.
2. `has_blocking` is false (bar-aware predicate above).
3. `audit_coverage_qualifies_sample(selected_audit_coverage)` is true **and** the coverage is not `budget_limited`. `audit_incomplete` (`_conceptual_bar_from_audit_recs`) is what actually implements this: it is `True` whenever `coverage.get("budget_limited")`, independent of `audit_coverage_qualifies_sample`. **Do not fold `budget_limited` into the shared `audit_coverage_qualifies_sample` predicate** — `_resolve_audit_reuse` also consults it for an unrelated reuse-acceptance decision, and its pass-conformance-only meaning is correct there. (Corrected 2026-08-10: the version of this step that shipped treated a well-formed-but-budget-limited sample as qualifying for clean, which is wrong — `normalize_audit_coverage` guarantees `confirmation_kind is None` whenever `budget_limited` is `True`, so a still-discovering run's passes are ordinarily *all* well-formed, and pass-conformance alone could never distinguish "confirmed" from "still discovering.")
4. `outcome.stop_reason` is clean-eligible per the plan Architecture table:
   - **Eligible:** `None` (audit-only / no loop), `converged`, `no_blocking_findings`, `all_auto_apply_findings_deferred` when the bar did not force `terminal_hand_apply` (step 5 already remapped blocked cases).
   - **Not eligible:** `terminal_hand_apply`, `manual_fix_blocking_findings` (and alias `blocked`), `max_iterations`, `no_progress`, `marginal`, `deadline_exceeded`, `time_budget_exceeded`, any `halted: *`, and `audit_incomplete` as a stop reason if ever written.

Do **not** add a top-level JSON `clean` key — machine consumers derive clean from `audit_incomplete=false` ∧ `has_blocking_findings=false` ∧ eligible `outcome.stop_reason` (expose `stop_reason` on JSON when the iterate loop ran, mirroring markdown halt/stop reporting where practical).

`confirmation_kind` remains reporting-only; never consult it to deny clean when pass-conformance qualifies (`budget_limited` is the separate, load-bearing check for confirmation — see above).

### `finalize_completeness_run` wiring

Thread into the existing finalize signature (step 4 should have added `audit_stage`, `conceptual_bar_blocking_ids`, `audit_incomplete`; this step consumes them):

1. Compute `has_blocking = _completeness_has_blocking_findings(..., audit_stage=audit_stage, audit_recs=audit_recs, ...)`.
2. Pass `audit_stage`, `conceptual_bar_blocking_ids`, `audit_incomplete`, and `has_blocking` into `_render_completeness_json`.
3. **`--json` path:** return rc from `_render_completeness_json` (see fail-on-findings below); `early_exit_code` still wins.
4. **Markdown path:** `_render_grouped_report` may keep using `bundle_status`; stage bar copy polish is Deferred — only wire blocking/coverage callouts that already exist.
5. **`--fail-on-findings` (markdown path, after halt rc check):** return `1` when `audit_incomplete` **or** `has_blocking`; return `0` otherwise on a completed audit.
6. **`audit_incomplete` operator route:** if not already printed on the live-audit path (step 4 producers), print the settled re-run guidance once at finalize when `audit_incomplete` is true: re-run with a live sample (`--no-reuse-audit` when reuse caused it); do **not** suggest raising `--audit-passes` as the primary fix.

### `_render_completeness_json` payload

Extend `plan_tool/cli/completeness_phases.py:_render_completeness_json` with top-level keys (always emit booleans/strings; stable sort order within existing conventions):

| Key | Value |
| --- | --- |
| `stage` | hoisted `audit_stage` (`"bare"` \| `"detail"`) |
| `audit_incomplete` | bool from step 4 |
| `conceptual_bar_blocking_ids` | list of stable ids when `audit_incomplete` is false; **`null` when `audit_incomplete` is true** (never `[]` as “measured none”) |
| `has_blocking_findings` | bar-aware `has_blocking` (includes deterministic + conceptual arms) |
| `stop_reason` | optional — include when `outcome.stop_reason` is set (iterate / halt context) |

Ensure `coverage` in JSON continues to flow through `_project_audit_coverage_for_public_output` so conformance counts are visible when step 4 extended projection.

**`--fail-on-findings` on the JSON path** (inside `_render_completeness_json` today): exit `1` when `audit_incomplete` **or** `has_blocking_findings`; `early_exit_code` still wins. This tightens CI on incomplete samples relative to HEAD.

### Coverage callout alignment

**Corrected 2026-08-10** — the shipped version of this step suppressed both callouts under `audit_coverage_qualifies_sample(...)` even when `budget_limited` was `True`, which silenced the warning for the ordinary well-formed-but-still-discovering case (see the finalize-clean correction above; same root cause). Both callouts fire on `budget_limited` alone, unconditionally — no qualifying-sample suppression:

- **`emit_coverage_unconfirmed`** — fires whenever `budget.get("budget_limited")` is true. No-op otherwise.
- **`_render_coverage_confidence_markdown`** — renders the `"> **Coverage unconfirmed:** … budget-limited …"` block whenever `coverage["budget_limited"]` is true. Keep the `confirmed-low-yield` callout and `unknown-legacy` callout behavior unchanged.

There is no shared "suppress budget-limited" helper — the two callouts each check `budget_limited` directly, and `audit_coverage_qualifies_sample` is not involved.

### CLI help (minimal)

Update only completeness-facing strings in `plan_tool/cli/completeness_cmd.py:register`:

- **`completeness-audit` subparser `help=`** — replace “gate CI on medium+ findings” with stage-aware wording: bare vs detail bars differ; `--json` exposes `stage`, `conceptual_bar_blocking_ids`, `audit_incomplete`, and bar-aware `has_blocking_findings`; `--fail-on-findings` also fails on incomplete audit samples.
- **`--json` help** — name the three new top-level fields and that `has_blocking_findings` is bar-aware (not flat medium+ on conceptual findings).
- **`--fail-on-findings` parent help** — update only the completeness clause in the shared parent (keep verify-all / validate clauses accurate).

Regenerate `docs/cli/completeness-audit.md` and `docs/cli/README.md` with `python -m plan_tool.cli_reference --write`; `tests/cli/test_cli_reference.py` guards drift.

### What stays unchanged

- **`ConvergenceState.has_blocking_findings`** — deterministic-only; step 5 owns mid-run behavior.
- **Mid-run stop remap and remedies** — step 5; this step does not add loop hooks.
- **`compute_conceptual_bar_blocking_ids` implementation** — step 4; finalize reads its output.
- **Unconditional `_completeness_has_blocking_findings` arms** — `files_coh_issues` remains unread.
- **Reporting polish** — set-aside handoff lists, gate-2 tail naming, full stop-reason vocabulary (plan Deferred).
- **`tests/test_cli.py` end-to-end completeness tests** — update only if a shared assertion still assumes flat medium+ conceptual blocking; prefer new focused cases in `tests/cli/test_completeness_cmd.py` over duplicating full `main()` drives.

### Gotchas

- **Single source for bar evaluation** — `_completeness_has_blocking_findings` and JSON `conceptual_bar_blocking_ids` must agree; ids come from step 4’s tuple, boolean from `is_blocking_finding` with the same `audit_stage` and `classify_domain` wiring.
- **`audit_incomplete` + empty ids** — JSON `null` for `conceptual_bar_blocking_ids`; tests must assert `is not []`.
- **Reuse path** — finalize uses `selected_audit_coverage` from iterate budget, reused sidecar projection, or `_noniter_budget`; qualifying-sample checks must use the same object passed to coverage projection.
- **Jira grade** — thread the same `audit_stage` computed at the requested grade; do not fork a second stage derivation inside finalize.
- **Shared `--fail-on-findings` parent** — wording change must remain truthful for validate and verify-all arms.

## Tests

Green-before-done: every test below passes, `uv run pytest -m "not integration" tests/cli/test_completeness_cmd.py tests/cli/test_cli_reference.py -q` is green, and `python -m plan_tool.cli_reference --write` leaves `docs/cli/` clean.

### Tests for this step

**`tests/cli/test_completeness_cmd.py` — extend `TestCompletenessHasBlockingFindings`**

- `test_bare_medium_completeness_not_blocking_under_bar` — medium `plan-completeness` rec does not block when `audit_stage=STAGE_BARE`.
- `test_bare_medium_correctness_still_blocks` — medium `plan-correctness` blocks at bare stage.
- `test_detail_docs_medium_demoted_under_bar` — detail stage + docs-shaped medium conceptual rec does not block (use step-1-style fixture or parametrized `Recommendation`).
- `test_detail_code_logic_medium_blocks` — detail stage + code-logic medium blocks.
- `test_non_conceptual_arms_unchanged` — existing path-style / dep / self-consistency cases still pass without `audit_stage` changing deterministic behavior.

**`tests/cli/test_completeness_cmd.py` — extend `TestRenderCompletenessJson`**

- `test_json_includes_stage_audit_incomplete_and_bar_ids` — payload contains `stage`, `audit_incomplete`, `conceptual_bar_blocking_ids`, bar-aware `has_blocking_findings`.
- `test_json_conceptual_bar_ids_null_when_audit_incomplete` — `audit_incomplete=True` → `conceptual_bar_blocking_ids is None` (not empty list).
- `test_json_fail_on_findings_exits_one_on_audit_incomplete` — `--fail-on-findings` + incomplete → rc 1 even when deterministic checks are clear.
- `test_json_fail_on_findings_exits_one_on_bar_blocker` — rc 1 when bar-aware `has_blocking_findings` true.
- `test_json_includes_stop_reason_when_iterate_ran` — when outcome carries `stop_reason`, JSON exposes it.

**`tests/cli/test_completeness_cmd.py` — coverage callouts**

- `test_emit_coverage_unconfirmed_fires_even_when_sample_qualifies` — `budget_limited=True` with qualifying conformance counts still prints the stderr warning (`TestEmitCoverageUnconfirmed`; corrected 2026-08-10 from the shipped `..._suppressed_...` version, which pinned the wrong behavior).
- `test_render_coverage_confidence_fires_even_when_sample_qualifies` — the budget-limited markdown callout still renders when the sample otherwise qualifies (`TestRenderCoverageConfidenceMarkdown`; same correction).
- `test_budget_limited_marks_incomplete_even_when_pass_conformance_qualifies` — `_conceptual_bar_from_audit_recs` reports `audit_incomplete=True` for a `budget_limited=True`, conformance-qualifying coverage.

**`tests/cli/test_completeness_cmd.py` — finalize / fail-on-findings integration**

- `test_finalize_fail_on_findings_incomplete_exits_one` — drive `finalize_completeness_run` with `audit_incomplete=True`, `--fail-on-findings` → rc 1.
- `test_finalize_clean_requires_eligible_stop_reason` — bar clear + qualifying, non-budget-limited sample + `stop_reason="terminal_hand_apply"` → `--fail-on-findings` rc 1; same arms with `stop_reason=None` (audit-only) → rc 0.
- `test_bare_deferred_medium_completeness_clean_when_sample_qualifies` — end-to-end style: bare stage, only deferred medium completeness in bar set, qualifying non-budget-limited conformance, eligible stop → `has_blocking_findings` false.

**`tests/cli/test_cli_reference.py`**

- `test_every_generated_file_matches_disk` — passes after `--write` (no test code change unless generator behavior changes).

## Acceptance criteria

- `_completeness_has_blocking_findings` uses `is_blocking_finding` for `audit_recs` with `classify_domain=classify_finding_domain` at detail stage; non-conceptual arms unchanged.
- `--json` emits `stage`, `audit_incomplete`, `conceptual_bar_blocking_ids` (`null` when incomplete), and bar-aware `has_blocking_findings`.
- `--fail-on-findings` returns rc 1 on `audit_incomplete` or bar-aware blocking (JSON and markdown finalize paths); `early_exit_code` still wins.
- Finalize clean eligibility requires pass-conformance (`audit_coverage_qualifies_sample`) **and** `not budget_limited`; `confirmation_kind` alone does not deny clean; `outcome.stop_reason` gates clean per the plan Architecture table.
- `emit_coverage_unconfirmed` and `_render_coverage_confidence_markdown` fire their budget-limited “not fully validated” warnings whenever `budget_limited` is true, regardless of pass-conformance.
- `DATA_CONTRACT.md` documents the new JSON fields and bar-aware `has_blocking_findings` semantics.
- `docs/cli/completeness-audit.md` and `docs/cli/README.md` match regenerated argparse help; `tests/cli/test_cli_reference.py` is green.
- `rg 'is_blocking\(r\.severity\) for r in audit_recs' plan_tool/cli/completeness_cmd.py` returns nothing (conceptual arm migrated).
- `ConvergenceState.has_blocking_findings` and mid-run `terminal_hand_apply` behavior unchanged (step 5).

## References

- [typing](https://docs.python.org/3/library/typing.html) — keyword-only finalize parameters and optional coverage inputs.
- [PEP 3102](https://peps.python.org/pep-3102/) — keyword-only `audit_stage` on `_completeness_has_blocking_findings`.
- [pytest parametrize](https://docs.pytest.org/en/stable/how-to/parametrize.html) — bare/detail bar tables and qualifying-sample cases.

## Applicable guardrails

- **Plan step intent** — finalize clean ownership, minimal JSON/help/coverage alignment only; no reporting polish or new loop behavior.
- **Plan Out of scope** — do not change `files_coh_issues` handling, persist `Recommendation.domain`, expand `is_blocking_impact`, or add stage bars to reconcile/create/detail.
- **Plan Architecture — `has_blocking_findings` dual use** — stage bar stays out of `ConvergenceState.has_blocking_findings`; only finalize/`--json`/`--fail-on-findings` use the bar-aware predicate.
- **Plan Architecture — qualifying sample** — finalize clean and coverage callouts require pass-conformance **and** `not budget_limited` (corrected 2026-08-10); `confirmation_kind` does not gate clean.

## Deferred

- Reporting polish (full stop-reason vocabulary, set-aside handoff copy, gate-2 tail bar naming, jira clean next-steps) — plan Deferred / BACKLOG follow-up.
- Fixing unused `files_coh_issues` parameter in `_completeness_has_blocking_findings` — `BUG_BACKLOG.md` (plan Out of scope).
- Classifier live-rate accuracy gates — plan Out of scope.
- Persisted `Recommendation.domain` — plan Out of scope.
