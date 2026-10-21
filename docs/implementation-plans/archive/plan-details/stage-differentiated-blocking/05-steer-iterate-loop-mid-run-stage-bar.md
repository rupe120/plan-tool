> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Steer the iterate loop mid-run with the stage bar

## Summary

Wire the stage-aware conceptual bar from step 4 into `_run_iterate_convergence_loop` so the `--iterate` path stops honestly when only conceptual bar blockers remain: remap leaf exits `converged`, `no_blocking_findings`, and `all_auto_apply_findings_deferred` to `terminal_hand_apply`, print class-mapped remedies on existing mid-run surfaces, and leave `ConvergenceState.has_blocking_findings` deterministic-only. Primary touch point is `plan_tool/cli/completeness_cmd.py`; tests live in `tests/cli/test_completeness_cmd.py`. Green means iteration-0 “converged” with bar blockers no longer reads as clean, remedy lines match finding class, and deterministic convergence behavior is unchanged.

## Table of Contents

- [Why](#why) — why the iterate loop misreports clean today and what this step fixes.
- [Input](#input) — contracts from steps 2–4 the loop must read.
- [Files (creates vs edits)](#files-creates-vs-edits) — touched paths only.
- [Implementation](#implementation) — bar re-decision hooks, stop remapping, remedies, and boundaries.
- [Tests](#tests) — new cases and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes for reviewers and CI.
- [References](#references) — typing and pytest docs.
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step.
- [Deferred](#deferred) — follow-ups explicitly not in this step.

## Why

Under the read-only-audit split (#85), `_run_iterate_convergence_loop` applies only deterministic well-formedness findings; conceptual gaps stay in `_audit_recs` and never enter `state.current_finding_ids`. `ConvergenceState.has_blocking_findings` is therefore severity-only over that deterministic set, so `should_continue` can return `no_blocking_findings` and the `not open_apply` branch can set `_loop_stop_reason="converged"` at iteration 0 while medium+ conceptual bar blockers still exist in `_audit_recs`. Step 4 computes `conceptual_bar_blocking_ids` via `is_blocking_finding` and the hoisted `audit_stage`, but without mid-run steering those ids do not change loop stop kind or operator guidance — the loop looks converged when the stage bar says it is not. This step closes that gap without putting conceptual ids into `current_finding_ids` or `has_blocking_findings` (which would break advisory `no_blocking_findings` and risk a busy loop).

## Input

**From step 2** (`plan_tool/convergence.py`):

- `is_blocking_finding(rec, *, stage, classify_domain=...)` with `STAGE_BARE` / `STAGE_DETAIL`.
- Detail stage: pass `classify_domain=classify_finding_domain` at bar-evaluation call sites (step 4’s helper does this).

**From step 3** (`plan_tool/cli/completeness_phases.py` / `plan_tool/cli/completeness_cmd.py`):

- Hoisted `audit_stage` from `derive_audit_stage(bundle_status)` and precomputed `bundle_status` threaded into `_run_iterate_convergence_loop`.
- **`audit_stage`** drives the bar; **`bundle_status.is_bare`** drives withhold vs hand-edit split for completeness remedies (do not replace with `audit_stage == STAGE_BARE` alone).

**From step 4** (`plan_tool/cli/completeness_cmd.py` and `plan_tool/cli/completeness_phases.py`):

- `compute_conceptual_bar_blocking_ids(recs, *, audit_stage, classify_domain=...)` — stable id tuple where the stage bar is true.
- `_IterateOutcome.conceptual_bar_blocking_ids` and `_IterateOutcome.audit_incomplete` populated **before the loop body** on live audit **and** on the iterate reuse branch (`reused_audit_recs is not None`) after stage hoist — step 5 remaps the same exits for both producers.
- When `audit_incomplete` is true, `conceptual_bar_blocking_ids` is empty or unmeasured — bar steering must not treat that as “bar clear.”

**Existing loop surfaces this step reuses (do not fork parallel copy):**

- `plan_tool/cli/completeness_phases.py:_sc_manual_fix_note` — hand-edit terminal note for **blocking** completeness (bare high/critical bar ids and detail-grounded completeness) and self-consistency parallels.
- `plan_tool/completeness_report.py:diagnostic_remedies` — structural diagnostic lines when a saved sidecar/checkpoint exists.
- Bare-withhold informational strings already printed in the `not open_apply` / `all_auto_apply_findings_deferred` branch — reuse **only** for medium completeness outside the bar set (never for high/critical ids in `conceptual_bar_blocking_ids`).
- `plan_tool/completeness_report.py:CORRECTNESS_INTRO` / `CORRECTNESS_INTRO_BARE` — semantic model for correctness → `completeness-apply` routing (one-line stderr hint is enough mid-run; full intro stays in the report).

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/completeness_cmd.py` — bar steering helper(s); hook `_run_iterate_convergence_loop` after `should_continue` and at `not open_apply`; set `_loop_stop_reason` / `_IterateOutcome.stop_reason` to `terminal_hand_apply` when remapping; emit class-mapped remedy lines.
  - `tests/cli/test_completeness_cmd.py` — `TestBarSteeringMidRun` (or equivalent) driving `_run_iterate_convergence_loop` with stubbed deterministic findings + conceptual `_audit_recs`.

## Implementation

### Foundational logic: bar re-decision after leaf loop exits

Add one or two small module-private helpers in `plan_tool/cli/completeness_cmd.py` (names are implementer’s choice; keep them pure where possible):

- **Inputs:** candidate `_loop_stop_reason`, `conceptual_bar_blocking_ids`, `audit_incomplete`, and the conceptual rec list (`_audit_recs`) for remedy dispatch.
- **Remap predicate:** when `conceptual_bar_blocking_ids` is non-empty **and** `audit_incomplete` is false **and** the candidate reason is one of:
  - `converged`
  - `no_blocking_findings`
  - `all_auto_apply_findings_deferred`
  → return stop reason `terminal_hand_apply` instead of the candidate.
- **Otherwise:** return the candidate unchanged (budget stops like `max_iterations`, `no_progress`, `manual_fix_blocking_findings`, `halted: *` are not remapped).

**Rejected alternative:** add conceptual bar ids to `state.current_finding_ids` or set `state.has_blocking_findings` from conceptual recs — breaks the settled split (deterministic mid-run vs bar-aware finalize) and can prevent the advisory `no_blocking_findings` path from firing when only demoted conceptual findings remain.

**Rejected alternative:** loop until conceptual gaps are gone — conceptual audit runs once per invocation; steering is a terminal stop + remedy, not extra apply rounds.

### Hook sites in `_run_iterate_convergence_loop`

Apply the same re-decision at **both** places the plan names:

1. **`should_continue` exit** — immediately after `_loop_stop_reason = reason` when `not cont`, before the stop banner `break` (the block that prints `completeness iteration loop stopped: {reason}`). If remapped to `terminal_hand_apply`, print conceptual remedies **in addition to** any deterministic hints already assembled (do not drop drift/self-consistency hints for real deterministic open findings).
2. **`not open_apply` exit** — when the branch would set `_loop_stop_reason` to `converged` (iteration 0, empty deterministic apply queue) or `all_auto_apply_findings_deferred`, run the re-decision **before** `break`. This is the iteration-0 false-converged case the plan calls out explicitly.

When remapped, ensure stderr does **not** imply mid-run clean (avoid wording that reads as “nothing left to do” without naming conceptual bar blockers). The existing `all_auto_apply_findings_deferred` copy that says findings are “saved for completeness-apply” is the template for correctness; replace or supplement it when the bar forces `terminal_hand_apply`.

Thread the final stop reason through `_IterateOutcome.stop_reason` as today (`stop_reason=_loop_stop_reason` at return) so step 6 can read `outcome.stop_reason` for clean eligibility.

### Remedy dispatch by bar-blocker class

Filter `_audit_recs` to ids in `conceptual_bar_blocking_ids`, then split by `source` and severity/withhold rules:

| Bar blocker class | When | Mid-run remedy surface |
| --- | --- | --- |
| **`plan-correctness`** | always walkable when a checkpoint/sidecar exists | Print `plan-tool completeness-apply <name>` (and `diagnostic_remedies` lines only when structural diagnostics are also open — same guard as the existing `should_continue` hint block). If `_audit_advisory_checkpoint_saved` / checkpoint path is false, still name completeness-apply when the pre-apply checkpoint was written (`write_pre_apply_audit_checkpoint`). |
| **`plan-completeness` bar-blocking (bare)** | id ∈ `conceptual_bar_blocking_ids` and `bundle_status.is_bare` (high/critical only under bare bar) | **Hand-edit** via `_sc_manual_fix_note` / report guidance — these are **not** clean-eligible; do **not** print withhold-style “informational until detail exists” for them. |
| **`plan-completeness` medium outside bar (bare)** | `bundle_status.is_bare` and id **not** in `conceptual_bar_blocking_ids` | Bare-withhold informational copy only (report/set-aside visibility; not a bar remap driver). |
| **`plan-completeness` detail-grounded** | id ∈ `conceptual_bar_blocking_ids` and `audit_stage == STAGE_DETAIL` | Hand-edit guidance — `_sc_manual_fix_note` adapted for conceptual completeness (do not claim auto-apply). |

Demoted detail mediums (docs/unit-test) never appear in `conceptual_bar_blocking_ids` — no remedy line for them.

Keep **`manual_fix_blocking_findings`** production as-is for self-consistency blocking (`sc_blocking` branch); the plan treats `blocked` as a clean-eligibility alias only — do not add a new `_loop_stop_reason="blocked"` writer.

### Invariants (must not change)

- **`state.current_finding_ids`** — still only deterministic + self-consistency ids from `_open_findings_now()`; never add conceptual audit ids.
- **`state.has_blocking_findings`** — still `any(is_blocking(r.severity) for r in current_findings)` before each `should_continue` check (the post-apply update around `record_iteration` stays severity-only).
- **`_completeness_has_blocking_findings`** — untouched in this step (step 6 switches its conceptual arm to the bar).
- **No extra Claude calls** — bar set is read from step 4’s once-computed `conceptual_bar_blocking_ids`, not recomputed from a second audit.
- **Deterministic apply path** — when `open_apply` is non-empty, the loop continues normally; bar steering does not preempt per-finding `apply_finding` dispatch.

### `_IterateOutcome` fields

Read `conceptual_bar_blocking_ids` and `audit_incomplete` from the step-4-populated outcome path (computed right after `_audit_recs` is seeded). This step does not add new outcome fields; it only changes `stop_reason` and stderr when the remap fires.

## Tests

Every test below must be green before this step is done. Stub `collect_deterministic_findings` / `collect_self_consistency_findings` to return `[]` unless the case needs deterministic work; stub `audit_plan_until_stable` to return hand-built conceptual recs (or pass `reused_audit_recs`); patch `compute_conceptual_bar_blocking_ids` only when testing steering logic in isolation — prefer driving the real helper from step 4 when landed.

### Tests for this step

- `test_iteration_zero_converged_with_bar_blockers_becomes_terminal_hand_apply` — empty deterministic open set, non-empty `conceptual_bar_blocking_ids` → `outcome.stop_reason == "terminal_hand_apply"`, not `converged`.
- `test_no_blocking_findings_with_conceptual_bar_blockers_remapped` — after one iteration, deterministic only nit/info, conceptual bar ids non-empty → `terminal_hand_apply`.
- `test_all_auto_apply_deferred_with_bar_blockers_remapped` — triage defers all deterministic applyables, bar blockers remain → `terminal_hand_apply`, not `all_auto_apply_findings_deferred`.
- `test_converged_when_bar_clear_unchanged` — empty `conceptual_bar_blocking_ids` → candidate `converged` preserved.
- `test_max_iterations_not_remapped_when_bar_blocks` — budget stop stays `max_iterations` even if bar ids non-empty.
- `test_bare_correctness_bar_blocker_prints_completeness_apply_hint` — stderr mentions `completeness-apply` for `plan-correctness` bar blocker.
- `test_bare_high_completeness_bar_blocker_prints_hand_edit` — `bundle_status.is_bare`, high/critical completeness **in** bar set → hand-edit / `_sc_manual_fix_note`-style line; **not** withhold “informational until detail” copy; no completeness-apply for completeness-only.
- `test_bare_medium_completeness_outside_bar_informational_only` — medium completeness not in bar set → withhold informational copy only (no `terminal_hand_apply` from that id alone).
- `test_detail_completeness_bar_blocker_prints_hand_edit_guidance` — detail stage completeness bar blocker → hand-edit / `_sc_manual_fix_note`-style line.
- `test_iterate_reuse_with_bar_blockers_remaps_terminal_hand_apply` — `reused_audit_recs` with medium correctness bar blockers + empty deterministic open set → `terminal_hand_apply` (reuse branch produces bar ids before loop body).
- `test_audit_incomplete_skips_bar_remap` — `audit_incomplete=True` with empty bar ids → no `terminal_hand_apply` solely from conceptual recs presence.
- `test_conceptual_ids_never_join_current_finding_ids` — source or runtime assertion: `state.current_finding_ids` disjoint from conceptual audit ids after loop.
- `test_has_blocking_findings_stays_deterministic_only` — `rg` or behavior test: post-apply `has_blocking_findings` ignores conceptual `_audit_recs`.

## Acceptance criteria

- `_run_iterate_convergence_loop` remaps `converged`, `no_blocking_findings`, and `all_auto_apply_findings_deferred` to `terminal_hand_apply` when `conceptual_bar_blocking_ids` is non-empty and `audit_incomplete` is false.
- Iteration-0 `not open_apply` with only conceptual bar blockers returns `stop_reason="terminal_hand_apply"`, not `converged`.
- Remedy stderr uses existing surfaces: completeness-apply for walkable correctness; hand-edit for bare high/critical completeness bar ids and detail-grounded completeness bar blockers; withhold informational copy only for bare medium completeness outside the bar.
- `ConvergenceState.has_blocking_findings` and `current_finding_ids` remain deterministic-only; conceptual audit ids are not merged into either.
- `_completeness_has_blocking_findings`, `--json` fields, finalize clean eligibility, and CLI help are unchanged (step 6).
- `rg 'terminal_hand_apply' plan_tool/cli/completeness_phases.py` shows the remap writer and remedy hook only in the iterate loop module (no duplicate stop-kind writers elsewhere in this step).
- All tests listed in [Tests](#tests) pass.

## References

- [typing](https://docs.python.org/3/library/typing.html) — helper signatures and optional callback typing.
- [PEP 3102](https://peps.python.org/pep-3102/) — keyword-only parameters on any new helper surfaced to tests.
- [pytest parametrize](https://docs.pytest.org/en/stable/how-to/parametrize.html) — bare vs detail remedy table cases.

## Applicable guardrails

- **Plan intent — mid-run steering, not finalize-only** — this step only changes `_run_iterate_convergence_loop` stop kind and stderr; finalize/`--json` bar exposure stays step 6.
- **Plan step intent** — remap to `terminal_hand_apply` with class-mapped remedies on existing surfaces; never claim clean mid-run; preserve deterministic `has_blocking_findings`.
- **Plan Out of scope** — reporting polish, reconcile/create/detail loops, persisted `Recommendation.domain`, expanding `is_blocking_impact`, changing unconditional `_completeness_has_blocking_findings` arms for `files_coh_issues`.
- **Plan Architecture — `has_blocking_findings` dual use** — do not write the stage bar into `ConvergenceState.has_blocking_findings`.
- **Plan Architecture — clean eligibility** — `terminal_hand_apply` is not clean-eligible; this step must emit that stop kind when remapping (finalize enforcement is step 6).

## Deferred

- Finalize / `--json` / `--fail-on-findings` bar-aware `has_blocking_findings`, `stage`, `conceptual_bar_blocking_ids`, and `audit_incomplete` exposure — step 6 (`plan_tool/cli/completeness_cmd.py:finalize_completeness_run`, `_completeness_has_blocking_findings`, `_render_completeness_json`).
- Full stop-reason vocabulary and report intro rewrites — plan Reporting polish / BACKLOG follow-up.
- `manual_fix_blocking_findings` → clean-eligibility alias `blocked` — step 6 finalize only; no new `blocked` writer here.
- Classifier live-rate accuracy gates — plan Out of scope.
