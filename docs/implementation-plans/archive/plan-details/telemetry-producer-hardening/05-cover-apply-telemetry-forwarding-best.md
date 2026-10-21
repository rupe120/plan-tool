> **Auto-archived**: this plan was swept on 2026-07-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Cover apply telemetry forwarding and best-effort guards

## Summary

Add direct regression coverage for the four apply callers in `plan_tool/create.py`, `plan_tool/detail.py`, `plan_tool/cli/completeness_cmd.py`, and `plan_tool/cli/review_actions.py`. Prove that each caller forwards the finding anchor and one shared plan fingerprint; the first three retain authoritative launcher recording, while interactive review uses step 4's deferred keep/reject ownership. Complete the best-effort coverage for the code-reveals-split and escalate-to-split producers, reusing existing tests where they already prove the contract. On green, telemetry argument preparation can fail without changing any host result, and all six scoped test suites pass without production-code edits.

## Table of Contents

- [Summary](#summary) — Reviewer-level overview of the coverage added by this step.
- [Why](#why) — Why producer tests alone do not prove caller forwarding.
- [Input](#input) — Step 3 and step 4 contracts this coverage consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Scoped test-only changes.
- [Implementation](#implementation) — Coverage rules for forwarding, hoisting, and failure guards.
- [Tests](#tests) — Direct regression cases for every named site.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [Deferred](#deferred) — Production behavior and duplicate lower-level coverage left to other steps.

## Why

The apply producer tests cover `plan_tool/launcher.py:apply_finding`, but they do not prove that its four callers preserve each finding's optional `anchor` from `plan_tool/review.py:Recommendation`, compute the plan fingerprint once per loop or walk, and select the correct authoritative or deferred owner after step 4. Existing coverage already checks parts of the best-effort rule in `tests/test_create.py:TestStepReviewOutcomeTelemetry`, `tests/cli/test_completeness_cmd.py:TestFingerprintTelemetry`, and `tests/test_launcher.py:TestEscalateToSplit`; the missing work is a direct, consistent forwarding sweep plus the uncovered code-reveals-split failure guard. Closing those gaps prevents a later caller edit from silently producing unjoinable or premature events or turning telemetry preparation into a command failure.

## Input

- **Step 3 output** — `plan_tool/launcher.py:apply_finding` classifies usable and unusable primary/follow-up backend outcomes while preserving host disposition. This step tests caller forwarding, not that classification again.
- **Step 4 output** — authoritative non-interactive `apply_finding` callers record by default, isolated parallel calls defer durable recording to `plan_tool/cli/completeness_apply_parallel.py:replay_results`, and interactive review defers until a user keeps the edit. The tests must pin the correct owner for each path.
- **Apply join keys** — each serial caller receives a `plan_tool/review.py:Recommendation` with an optional `anchor` and owns a pre-loop plan path. It forwards `rec.anchor or ""` and one guarded `plan_fingerprint` snapshot to `apply_finding`.
- **Best-effort boundary** — `plan_tool/telemetry.py:record_decision` protects work inside the sink. Fingerprint computation happens in the caller and therefore needs its own failure coverage.
- **Existing producer guards** — `plan_tool/review.py:extract_recommendations` guards the fingerprint work for `record_code_reveals_split`; `plan_tool/launcher.py:escalate_to_split` guards both its fingerprint preparation and its `_record_and_return` recorder call.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `tests/test_create.py` — directly cover anchor and shared plan-fingerprint forwarding from the per-finding loop in `create_plan`, including a raising fingerprint computation.
  - `tests/test_detail.py` — add the same direct coverage for the detail-quality loop in `generate_detail`.
  - `tests/test_launcher.py` — keep the step 3 and step 4 serial-default assertions and complete the `TestEscalateToSplit` best-effort matrix without duplicating its per-outcome telemetry tests.
  - `tests/test_review.py` — prove that fingerprint preparation failure at the code-reveals-split producer does not change the recommendations returned by `extract_recommendations`.
  - `tests/cli/test_completeness_cmd.py` — directly cover forwarding and compute-once behavior in `_run_iterate_convergence_loop`, separate from step 4’s parallel command tests.
  - `tests/cli/test_review_actions.py` — directly cover forwarding and failure fallback in `_build_review_action_fn`’s `_dispatch_apply_finding` branch.

## Implementation

The foundational logic is: **every serial apply caller forwards one guarded, loop-stable telemetry snapshot without changing host behavior**.

- **Test the four real owners.** Drive these existing entry points rather than creating a shared fake forwarding helper:
  - `plan_tool/create.py:create_plan`, at its per-finding `apply_finding` call;
  - `plan_tool/detail.py:generate_detail`, at its detail-quality apply loop;
  - `plan_tool/cli/completeness_cmd.py:_run_iterate_convergence_loop`, at its deterministic-finding apply call;
  - `plan_tool/cli/review_actions.py:_build_review_action_fn`, at `_dispatch_apply_finding`.

  Patch each module’s established `apply_finding` seam and capture its keyword arguments. Keep the surrounding fixture as small as the existing loop tests allow.

- **Use at least two findings per forwarding test.** Give the findings distinct non-empty anchors. Assert that each call receives its own `anchor`, while every call receives the same non-empty `plan_fingerprint`. Also spy on `plan_tool/review_persistence.compute_plan_fingerprint` and assert one call per enclosing loop or review-action builder, not one call per finding.

- **Pin recording ownership.** After step 4 lands, assert that create, detail, and serial completeness convergence do not opt into deferred recording. Assert that interactive review does opt in and records only after keep; rejection/restoration and `APPLIED` with an empty diff emit no verdict. Use the final step 4 parameter or observer name rather than guessing it in advance.

- **Pin the empty-anchor rule.** Include one recommendation whose `anchor` is `None` where the fixture supports it, and assert the launcher receives `""`. Do not let callers forward `None` into the persisted base-event field.

- **Test caller-side compute failure separately.** Force `compute_plan_fingerprint` to raise before dispatch. Each caller must still reach `apply_finding`, pass `plan_fingerprint=""`, preserve the anchor, and retain its normal return value, result list, walk status, or command return code. Do not treat “the sink never raises” as proof of this rule because argument preparation runs before the sink.

- **Keep assertions focused on telemetry threading.** Existing loop suites already cover convergence, deduplication, drift halts, structural escalation, carried findings, and operator feedback. Reuse those fixtures, but do not copy their behavioral assertions into this step’s tests.

- **Complete the Part-A guard in review.** In `tests/test_review.py`, drive the reconcile-lane split case through `plan_tool/review.py:extract_recommendations` with a real `plan_path`, then force either `compute_plan_fingerprint` or `compute_code_fingerprint` to raise. Assert that the same code-reveals-split recommendation is returned, no exception escapes, and any recorded event uses the established empty fingerprint sentinel. Keep `collect_deterministic_findings`’s silent non-reconcile path unchanged.

- **Cover the Part-A recorder wrapper too.** Independently replace `record_code_reveals_split` with a raising stub after successful fingerprint preparation. Assert that `extract_recommendations` returns the identical split recommendation and the recorder exception does not escape. Fingerprint-helper coverage alone does not prove the convenience-recorder call is guarded.

- **Retain the escalate guard as one contract.** `tests/test_launcher.py:TestEscalateToSplit.test_escalate_fingerprint_failure_does_not_break_bridge` and `TestEscalateToSplit.test_raising_recorder_does_not_perturb_bridge` already cover the two failure boundaries. Strengthen or parameterize them only if steps 3–4 change the surrounding telemetry seam: the required result is that the same `EscalateResult.outcome` returns and neither failure escapes.

- **Do not edit production code in this step.** If a new regression test exposes missing forwarding or an unguarded computation, route the fix back to the production step that owns that behavior. This step’s declared `change_type` is non-code and its file list contains tests only.

## Tests

- `tests/test_create.py:test_create_apply_loop_hoists_and_forwards_telemetry_keys` — two findings keep distinct anchors, share one plan fingerprint, and use ordinary serial recording.
- `tests/test_create.py:test_create_apply_loop_fingerprint_failure_is_best_effort` — a raising fingerprint computation falls back to `""` without changing `create_plan`’s result.
- `tests/test_detail.py:test_detail_apply_loop_hoists_and_forwards_telemetry_keys` — the detail-quality loop computes once and forwards each finding’s anchor.
- `tests/test_detail.py:test_detail_apply_loop_fingerprint_failure_is_best_effort` — detail authoring and apply dispatch continue with an empty fingerprint after a compute failure.
- `tests/cli/test_completeness_cmd.py:test_iterate_apply_loop_hoists_and_forwards_telemetry_keys` — deterministic findings receive distinct anchors and one shared pre-loop fingerprint.
- `tests/cli/test_completeness_cmd.py:test_iterate_apply_loop_fingerprint_failure_is_best_effort` — the convergence loop retains its normal outcome or return code and forwards `plan_fingerprint=""`.
- `tests/cli/test_review_actions.py:test_apply_dispatch_hoists_and_forwards_telemetry_keys` — repeated actions from one builder share one fingerprint while forwarding each recommendation anchor.
- `tests/cli/test_review_actions.py:test_apply_dispatch_fingerprint_failure_is_best_effort` — builder creation and dispatch remain usable after fingerprint computation raises.
- `tests/test_review.py:test_code_reveals_split_fingerprint_failure_is_best_effort` — `extract_recommendations` returns the same split finding and does not raise when either fingerprint helper fails.
- `tests/test_review.py:test_code_reveals_split_recorder_failure_is_best_effort` — a raising convenience recorder does not change or suppress the returned split finding.
- `tests/test_launcher.py:test_escalate_fingerprint_failure_does_not_break_bridge` — a fingerprint failure preserves the selected `EscalateResult`.
- `tests/test_launcher.py:test_raising_recorder_does_not_perturb_bridge` — a recorder failure preserves the selected `EscalateResult`.
- `tests/test_launcher.py:test_apply_finding_records_applied_verdict` — the step 4 recording-control change leaves ordinary serial callers recording by default.

### Verification (non-code step)

- Run `pytest tests/test_create.py tests/test_detail.py tests/test_launcher.py tests/test_review.py tests/cli/test_completeness_cmd.py tests/cli/test_review_actions.py`.
- Confirm each forwarding test observes at least two dispatches and exactly one fingerprint computation for its enclosing loop or builder.
- Confirm the failure cases compare the host result, command return code, or returned recommendations rather than merely asserting that no exception was raised.
- Confirm the step’s diff contains only the six declared test paths and no changes under `plan_tool/`.
- Confirm no test invokes a real backend; patch the established launcher or domain seams used by the surrounding test class.

## Acceptance criteria

- Direct tests cover all four `apply_finding` callers named in `plan_tool/create.py`, `plan_tool/detail.py`, `plan_tool/cli/completeness_cmd.py`, and `plan_tool/cli/review_actions.py`.
- For at least two findings at each caller, the captured `anchor` matches that finding’s anchor and all calls share one non-empty plan fingerprint.
- Each enclosing loop or review-action builder computes the plan fingerprint exactly once.
- A missing recommendation anchor reaches `apply_finding` as `""`.
- Create, detail, and serial completeness retain launcher recording; interactive review defers recording until keep and emits nothing for rejected/restored or empty-diff outcomes.
- A raising plan-fingerprint computation at each serial caller still dispatches the finding with `plan_fingerprint=""` and preserves the caller’s normal result.
- A fingerprint failure in `plan_tool/review.py:extract_recommendations` does not change or suppress the code-reveals-split recommendation.
- A `record_code_reveals_split` failure in `plan_tool/review.py:extract_recommendations` does not change or suppress that recommendation.
- Fingerprint and recorder failures in `plan_tool/launcher.py:escalate_to_split` preserve its selected outcome.
- The six focused test suites pass, and this step changes no production file.

## Deferred

- **Apply outcome classification and failure-token behavior** — owned and tested by step 3; this step only checks caller forwarding.
- **Parallel worker suppression, canonical replay, conflicts, and run-id binding** — owned and tested by step 4 in `tests/cli/test_completeness_apply_parallel.py`; this step checks only that serial callers do not opt into that path.
- **Production fixes exposed by these regressions** — return them to the owning implementation step rather than editing `plan_tool/` from this non-code step.
- **Telemetry producers outside the four apply loops, code-reveals-split, and escalate-to-split** — no repo-wide best-effort audit is part of this focused coverage step.
