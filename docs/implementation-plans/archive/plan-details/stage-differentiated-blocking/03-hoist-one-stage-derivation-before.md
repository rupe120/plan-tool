> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Hoist one stage derivation before the iterate or audit-only branch

## Summary

Behavior-preserving refactor in `plan_tool/cli/completeness_cmd.py` and `plan_tool/cli/completeness_phases.py`: call `audit_detail_bundle_status` once per `completeness-audit` invocation (with `detail_grade`), derive closed stage `bare` | `detail` from the plan Architecture table via a new pure helper, and thread the resulting `DetailBundleStatus` and stage string into `emit_bare_plan_banner`, `_run_iterate_convergence_loop`, `finalize_completeness_run`, and `write_pre_apply_audit_checkpoint` so none of them re-derive bundle status independently. The key rule is `total == 0 → bare` before `is_fully_bare` / otherwise `detail` — never equate stage with `DetailBundleStatus.is_bare` alone. No `is_blocking_finding` wiring, JSON fields, or loop stop behavior changes; green means one hoisted derivation, correct stage for step-less plans, and existing completeness suites unchanged.

## Table of Contents

- [Why](#why) — duplicate bundle-status calls and the step-less `is_bare` trap.
- [Input](#input) — contracts from steps 1–2 and `DetailBundleStatus` fields this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — touched paths only.
- [Implementation](#implementation) — hoist site, stage table, threading, and boundaries.
- [Tests](#tests) — new cases and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes for reviewers and CI.
- [References](#references) — typing and pytest docs.
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step.
- [Deferred](#deferred) — follow-ups explicitly not in this step.

## Why

`completeness-audit` will apply different blocking bars at bare vs detail-grounded stages (steps 4–6), but HEAD derives `DetailBundleStatus` in four separate places reachable from one invocation: `cmd_completeness` does not hoist; `_run_iterate_convergence_loop` calls `audit_detail_bundle_status` without `detail_grade`; `finalize_completeness_run` calls it again; and `write_pre_apply_audit_checkpoint` calls it without `detail_grade`. That duplication will drift once stage feeds `is_blocking_finding`, and it already misclassifies step-less plans: `DetailBundleStatus` for `steps: []` has `total=0`, `is_bare=False`, and `is_fully_bare=False` (`plan_tool/review.py:audit_detail_bundle_status`), while the plan Architecture table requires stage `bare` when `total == 0`. Step 2 supplies `STAGE_BARE` / `STAGE_DETAIL`; this step hoists derivation once and threads it before the iterate vs audit-only branch.

## Input

**From step 2** (`plan_tool/convergence.py` — must land before this step runs):

- `STAGE_BARE` → `"bare"`
- `STAGE_DETAIL` → `"detail"`

**From `plan_tool/review.py`:**

- `DetailBundleStatus` — fields/properties this step reads: `total`, `detailed_count`, `is_fully_bare`, `is_bare`, `bare_step_ids`, `detailed_step_ids`.
- `audit_detail_bundle_status(plan, plan_path, repo_root, *, detail_grade=...)` — sole producer of `DetailBundleStatus`; must be called with the same `detail_grade` the audit uses (`plan_tool/jira_grade.py:GRADE_RUN` default; jira grade selects jira artifact paths).

**Stage vs `is_bare` (do not conflate):**

- **`audit_stage`** — closed `bare` | `detail` for the stage bar (steps 4–6). Uses the Architecture table below; `total == 0` → `bare` even when `is_bare` is `False`.
- **`bundle_status.is_bare`** — existing withhold / diagnostic-filter signal in the iterate loop (`_bundle_status.is_bare` branches in `_run_iterate_convergence_loop`). Keep reading `is_bare` for those paths; do not replace them with `audit_stage == STAGE_BARE`.

**Hoist placement in `cmd_completeness`:** after plan parse, `detail_grade` resolution, and saved-audit reuse resolution; **before** `if budget.enabled:` and before `finalize_completeness_run`.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/completeness_phases.py` — add `derive_audit_stage`; extend `emit_bare_plan_banner`, `write_pre_apply_audit_checkpoint`, and `_sample_conceptual_audit` to accept precomputed `bundle_status` (and `detail_grade` where missing); optional `audit_stage` on `_IterateOutcome` if the cleanest handoff path needs it.
  - `plan_tool/cli/completeness_cmd.py` — hoist `audit_detail_bundle_status` + `derive_audit_stage` in `cmd_completeness`; thread `bundle_status`, `audit_stage`, and `detail_grade` into `_run_iterate_convergence_loop` and `finalize_completeness_run`; remove redundant `audit_detail_bundle_status` calls from those paths; pass threaded values into `write_pre_apply_audit_checkpoint`.
  - `tests/cli/test_completeness_cmd.py` — `TestDeriveAuditStage` (or equivalent), hoist/threading characterization tests, step-less plan case.

**Out of footprint (explicit zero-diff):** `cmd_completeness_apply`'s `audit_detail_bundle_status` call (~line 391) is a different command surface — leave it untouched.

## Implementation

### Foundational logic: `derive_audit_stage`

Add a pure helper in `plan_tool/cli/completeness_phases.py` (alongside `emit_bare_plan_banner`):

```text
derive_audit_stage(status: DetailBundleStatus) -> str
```

Import `STAGE_BARE` and `STAGE_DETAIL` from `plan_tool/convergence.py`. Evaluate in order (first match wins):

| Condition | Return |
| --- | --- |
| `status.total == 0` | `STAGE_BARE` (step-less plans; `is_bare` may be `False`) |
| `status.is_fully_bare` | `STAGE_BARE` (no detail files at selected grade, including all-`done` never-detailed) |
| Otherwise | `STAGE_DETAIL` (partial or full detail bundle at selected grade) |

**Rejected alternative:** deriving stage from `status.is_bare` — wrong for `total == 0` and collapses partial-detail plans into bare.

Invalid inputs are not expected (helper takes a real `DetailBundleStatus`); no silent default stage.

### Hoist site: `cmd_completeness`

In `plan_tool/cli/completeness_cmd.py:cmd_completeness`, after reuse resolution and before the iterate branch:

1. `bundle_status = audit_detail_bundle_status(plan, path, ctx.repo_root, detail_grade=detail_grade)`
2. `audit_stage = derive_audit_stage(bundle_status)`

Pass both into `_run_iterate_convergence_loop(...)` and `finalize_completeness_run(...)` as keyword-only parameters. `audit_stage` may be unused in function bodies until step 4 — still thread it so step 4 does not reopen signatures.

### Stop re-deriving at downstream sites

Thread `bundle_status` (and `detail_grade` where absent) so these paths do **not** call `audit_detail_bundle_status` again for the same invocation:

| Site | Current behavior | Target |
| --- | --- | --- |
| `_run_iterate_convergence_loop` | Calls `audit_detail_bundle_status` then sometimes `emit_bare_plan_banner` (re-calls status) | Use hoisted `bundle_status`; `emit_bare_plan_banner(..., bundle_status=bundle_status, detail_grade=detail_grade)` |
| `finalize_completeness_run` | Calls `audit_detail_bundle_status` before `_render_grouped_report` | Use caller-supplied `bundle_status` |
| `write_pre_apply_audit_checkpoint` | Calls `audit_detail_bundle_status` without `detail_grade` | Require caller-supplied `bundle_status`; add `detail_grade` for deterministic-check parity |
| `emit_bare_plan_banner` | Always calls `audit_detail_bundle_status` | Optional `bundle_status=` — when set, skip the internal status call and only print the banner |
| `_sample_conceptual_audit` | Calls `emit_bare_plan_banner` without precomputed status | Accept optional `bundle_status=` and forward |

**Rule for future sites:** any `audit_detail_bundle_status` reachable from `cmd_completeness` must receive the hoisted `bundle_status`, not call the function again. Do not fix a fixed count — grep the module after edits.

### What does not change (behavior-preserving)

- **No `is_blocking_finding` calls** — stage is computed and threaded only; blocking predicates stay on `is_blocking` / `_completeness_has_blocking_findings` as today.
- **No JSON / report / `--fail-on-findings` stage fields** — step 6.
- **Iterate loop withhold logic** — keep using `bundle_status.is_bare` for `DETAIL_LEVEL_DIAGNOSTIC_SOURCES` filtering and bare-plan completeness withhold copy; stage bar steering is step 5.
- **`cmd_completeness_apply`** — separate entry point; not in this step's file intent.
- **Pass-conformance / `conceptual_bar_blocking_ids`** — step 4.

### Gotchas

- **`detail_grade` must match everywhere** — the hoisted `audit_detail_bundle_status` call, `emit_bare_plan_banner`, deterministic checks, and conceptual audit grounding must all use the same grade (jira-grade audits classify bareness against jira artifacts, not run-grade pointers).
- **Re-parse after iterate** — `bundle_status` is computed on the pre-loop plan in `cmd_completeness`. Do not re-hoist mid-loop; step 5+ may revisit if apply changes detail presence (out of scope here).
- **Monkeypatch seams** — tests patch `plan_tool.review.audit_plan_until_stable` and `shell_review_invoker` on the domain module; hoisting does not move those calls.

## Tests

Green-before-done: every test below passes, and `uv run pytest -m "not integration" tests/cli/test_completeness_cmd.py -q` stays green.

### Tests for this step

- `test_total_zero_is_bare_stage` — `DetailBundleStatus(total=0, detailed_step_ids=(), bare_step_ids=())` → `STAGE_BARE` even though `is_bare` is `False`.
- `test_fully_bare_plan_is_bare_stage` — `total=3`, `detailed_count=0` → `STAGE_BARE`.
- `test_partial_detail_is_detail_stage` — `total=3`, one detailed step → `STAGE_DETAIL`.
- `test_fully_detailed_is_detail_stage` — all steps detailed → `STAGE_DETAIL`.
- `test_cmd_completeness_hoists_bundle_status_once` — `inspect.getsource(cmd_completeness)`: `audit_detail_bundle_status` appears in the pre-branch hoist block; `derive_audit_stage` is called there.
- `test_iterate_loop_does_not_call_audit_detail_bundle_status` — `inspect.getsource(_run_iterate_convergence_loop)`: no `audit_detail_bundle_status(` (uses threaded `bundle_status`).
- `test_finalize_does_not_call_audit_detail_bundle_status` — `inspect.getsource(finalize_completeness_run)`: no `audit_detail_bundle_status(`.
- `test_checkpoint_accepts_threaded_bundle_status` — `inspect.getsource(write_pre_apply_audit_checkpoint)`: accepts `bundle_status` (and `detail_grade`); no unconditional internal `audit_detail_bundle_status` when status is supplied (or helper removed entirely).
- `test_emit_bare_plan_banner_uses_passed_status` — when `bundle_status=` is provided, `audit_detail_bundle_status` is not invoked (monkeypatch raises if called).
- `test_step_less_plan_stage_bare_via_hoist` — drive `main(["completeness-audit", ...])` on a `steps: []` plan with conceptual audit stubbed; assert internal hoist yields `STAGE_BARE` (via a small test hook, outcome field, or spy on `derive_audit_stage` — pick the least invasive approach).

Regression: existing `TestEmitBarePlanBanner`, `test_iterate_loop_writes_pre_apply_checkpoint`, and `TestFinalizeCompletenessRun` cases stay green without behavior changes to banners, reports, or exit codes.

## Acceptance criteria

- `derive_audit_stage` exists in `plan_tool/cli/completeness_phases.py` and returns only `STAGE_BARE` or `STAGE_DETAIL` imported from `plan_tool/convergence.py`.
- `total == 0` → `STAGE_BARE` regardless of `is_bare` / `is_fully_bare`.
- `cmd_completeness` calls `audit_detail_bundle_status` exactly once per invocation (with `detail_grade`) before the iterate vs audit-only branch.
- `_run_iterate_convergence_loop`, `finalize_completeness_run`, and `write_pre_apply_audit_checkpoint` do not call `audit_detail_bundle_status` for the hoisted plan/path/grade tuple.
- `audit_stage` and `bundle_status` are threaded into the loop, finalize, and checkpoint paths (signatures updated even if `audit_stage` is unused in bodies until step 4).
- `write_pre_apply_audit_checkpoint` receives `detail_grade` from the orchestrator.
- `rg 'is_blocking_finding' plan_tool/cli/completeness_cmd.py plan_tool/cli/completeness_phases.py` returns nothing (no premature bar wiring).
- `_completeness_has_blocking_findings` and `ConvergenceState.has_blocking_findings` behavior unchanged.
- All new and existing tests in `tests/cli/test_completeness_cmd.py` relevant to completeness orchestration pass.

## References

- [typing](https://docs.python.org/3/library/typing.html) — keyword-only threaded parameters on `finalize_completeness_run` / `_run_iterate_convergence_loop`.
- [PEP 3102](https://peps.python.org/pep-3102/) — keyword-only `bundle_status`, `audit_stage`, `detail_grade` on extended signatures.
- [pytest parametrize](https://docs.pytest.org/en/stable/how-to/parametrize.html) — `derive_audit_stage` stage table cases.

## Applicable guardrails

- **Step intent — behavior-preserving refactor only** — hoist and thread; no new bar behavior, no loop stop remapping, no finalize JSON changes.
- **Plan Out of scope — reporting polish** — no stop-reason vocabulary, set-aside handoff copy, or CLI help edits.
- **Plan Out of scope — stage bar in reconcile / create / detail loops** — completeness-audit orchestration only.
- **Plan Out of scope — `_completeness_has_blocking_findings` arms** — leave `files_coh_issues` and other non-conceptual arms untouched.
- **Plan Out of scope — pass-conformance / `conceptual_bar_blocking_ids`** — step 4; do not add coverage keys or bar-blocking sets here.
- **Plan Architecture — stage selection** — follow the table (`total == 0` first); do not delegate stage to `is_bare` alone.

## Deferred

- Pass-conformance aggregates and `conceptual_bar_blocking_ids` computation — step 4 (`plan_tool/cli/completeness_cmd.py`, `plan_tool/review.py`, `DATA_CONTRACT.md`).
- Mid-run bar steering (`terminal_hand_apply` remap) — step 5.
- `is_blocking_finding` wiring into `_completeness_has_blocking_findings` and `--json` `stage` / `has_blocking_findings` bar-awareness — step 6.
- Re-hoisting `bundle_status` after iterate apply mutates detail presence — only if a later step proves it necessary; not assumed here.
- Reporting polish (BACKLOG #260) — follow-up after core ships.
