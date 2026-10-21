> **Replaced**: this file has been superseded by `docs/implementation-plans/2-audit-shape-registry.md`.
> Preserved here for history; do not edit.

# Step 2 — Replace the taper route with arm-clustering scope advice

## Summary

Add validated per-finding step attribution to the conceptual-audit contract, then use step 1’s registry to evaluate one optional arm-clustering advisory from the final normalized audit result. Update `plan_tool/review.py`, the completeness command/report paths, and `plan_tool/prompts/plan-audit.md` so audit-only and `--iterate` reports present the same evidence and user-owned keep-or-carve decision. Retire the tapering and non-converging guidance while retaining the existing coverage-confidence facts. When green, only a concentrated, explicitly attributed arm can produce advisory-only scope advice; it never blocks, applies, or changes an exit code.

## Table of Contents

- [Summary](#summary) — The behavior this step adds and retires.
- [Table of Contents](#table-of-contents) — Quick links to each section.
- [Why](#why) — Why count trends are not enough for a scope decision.
- [Input](#input) — The registry, audit findings, and plan ordering this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — Every in-scope production and test edit.
- [Implementation](#implementation) — Attribution, pure clustering, shared rendering, and retired routing.
- [Tests](#tests) — Focused coverage for the new advisory and removed route.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Standard-library references for the data and test boundaries.
- [Applicable guardrails](#applicable-guardrails) — The advisory and scope limits that bind this work.
- [Deferred](#deferred) — Related history-based and judgment-only work left out.

## Why

`plan_tool/review.py:recommend_audit_passes()` currently reads only per-pass counts and can direct a current audit toward cross-run convergence history. That does not identify the plan arm receiving the findings or force the user to decide whether it belongs. This step replaces that weak route with a fail-closed advisory based on explicit current findings, so the report gives the user the evidence needed to keep the arm with a stated reason or carve it before manually applying conceptual findings.

## Input

- **Step 1 registry.** Depend on step 1’s `plan_tool/audit_shapes.py:is_advisory_emitter_eligible()` and its `arm-clustering` record. Keep classification authority in that module; do not add a second allowlist in report code.

- **Conceptual findings.** `plan_tool/review.py:Recommendation`, produced by `plan_tool/review.py:_parse_plan_audit_findings()` and unioned by `plan_tool/review.py:audit_plan_until_stable()`, is the only finding set the evaluator reads. A non-`None` `Recommendation.step_id` means the one plan step that the finding's remedy may target; it is not a hint about a step merely mentioned by the finding. Deterministic findings, smells, and report history are not inputs.

- **Plan step order.** Use the current `Plan.steps` order and IDs supplied to `plan_tool/review.py:check_plan_audit()` to validate attribution and judge whether an arm is contiguous. An anchor, title, or prose mention is not a substitute for explicit attribution.

- **Shared report handoff.** `plan_tool/cli/completeness_cmd.py:finalize_completeness_run()` selects the final conceptual result for audit-only, fresh iterate, and staleness-approved reuse paths. Reuse supplies one accepted normalized finding set, not cross-run evidence. `plan_tool/cli/completeness_phases.py:write_pre_apply_audit_checkpoint()` receives the same result before the iterate loop applies deterministic findings. A conceptual target is valid only while the audited plan fingerprint still matches. Before final iterate persistence and before filtering or either serial, parallel, or replayed dispatch, compare the saved/audited fingerprint with the current plan. On equality the advice may be recomputed; on mismatch suppress it and use `dataclasses.replace(..., step_id=None)` (or an equivalent in-memory copy) for every remaining saved walk recommendation, preserving the human gap walk without allowing a stale numeric target to route any apply.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/audit_shapes.py` — add the leaf-safe arm-clustering evaluation result and predicate.
  - `plan_tool/prompts/plan-audit.md` — require an optional, machine-readable single-step attribution tag on conceptual-audit findings.
  - `plan_tool/review.py` — validate and preserve explicit attribution, evaluate the final conceptual result, and retire taper-route production.
  - `plan_tool/cli/completeness_phases.py` — render the advisory consistently in grouped, JSON, and pre-apply report paths while keeping coverage reporting separate.
  - `plan_tool/cli/completeness_cmd.py` — prepare and pass one advisory through audit-only and iterate finalization.
  - `plan_tool/cli/completeness_apply_parallel.py` — preserve the target-fingerprint guard through isolated-worker startup and any canonical replay that re-runs an apply.
  - `plan_tool/completeness_report.py` — include the advisory in persisted report and concise iterate presentation.
  - `plan_tool/convergence_diagnosis.py` — ignore conceptual-audit remedy targets while loading cross-run report history.
  - `BACKLOG.md` — retire active operator guidance that treats coverage recommendation fields as populated; leave the bounded #224 record update to step 3.
  - `CLAUDE.md` — replace Shape 1's retired taper/convergence description with the bounded arm-clustering contract while retaining the human override rule.
  - `DATA_CONTRACT.md` — document null-only legacy coverage recommendation fields and the additive output-only arm-advisory object.
  - `docs/AUDIT_FLOW.md` — document the new within-report scope advice, remove the retired budget route, and update `## Source map`.
  - `docs/cli/completeness-audit.md` — document the JSON compatibility and arm-advisory output.
  - `docs/cli/completeness-apply.md` — document the advisory repeated before saved-finding dispatch.
  - `tests/test_audit_shapes.py` — cover pure arm evaluation without weakening the leaf checks.
  - `tests/test_review.py` — cover attribution parsing, final-result evaluation, and removed taper behavior.
  - `tests/test_completeness_report.py` — cover persisted Markdown and concise report rendering.
  - `tests/cli/test_completeness_cmd.py` — cover shared audit-only, checkpoint, iterate, and JSON handoff.
  - `tests/cli/test_completeness_apply_parallel.py` — cover the parallel pre-dispatch advisory handoff.
  - `tests/cli/test_review_actions.py` — pin that a populated `Recommendation.step_id` still selects the existing apply target.
  - `tests/test_convergence_diagnosis.py` — pin that conceptual audit targets do not become cross-run focus evidence.
  - `tests/test_cli.py` — cover the public completeness command output contract.

## Implementation

- **Add one literal attribution grammar.** Update `plan_tool/prompts/plan-audit.md` so the only valid optional target form is `- SEVERITY: [anchor-slug] [step-id:N] finding text → fix: ... (impact=..., complexity=...)`, where `N` matches `0` or `-?[1-9][0-9]*` and names an integer ID from the audited plan (including negative IDs). The tag must appear immediately after the anchor and exactly once. It means the remedy targets that one step, preserving the existing `Recommendation.step_id` apply-routing semantics; a plan-wide, multi-step, uncertain, or cross-step-remedy finding must omit it.

- **Validate rather than infer, then reach cross-sample consensus.** Extend `plan_tool/review.py:_parse_plan_audit_findings()` and its `plan_tool/review.py:check_plan_audit()` caller so the literal tag becomes a candidate `Recommendation.step_id` only at the documented position and only when it canonicalizes to one current plan ID. Missing, malformed, unknown, repeated, multi-step, and plan-wide tags leave it `None`; do not recover an ID from an anchor such as `step3-*`, the title, or prose, and do not discard an otherwise valid finding because its tag is unusable. In `audit_plan_until_stable()`, preserve first-occurrence wording but collect every occurrence's candidate target by stable finding ID. Keep a final `step_id` only when every occurrence agrees on the same valid ID; any missing, invalid, or conflicting observation makes it `None`. This in-memory consensus changes neither saved-review schema nor ordinary apply-target semantics.

- **Keep clustering pure and leaf-safe.** Put the foundational logic — the validated contiguous-arm strict-majority predicate — in `plan_tool/audit_shapes.py`. Keep it independent of `Recommendation`, CLI modules, report code, filesystem access, and report wording. One workable boundary is for `plan_tool/review.py` to supply the ordered valid step IDs and the already-qualified material attribution records, while the leaf returns either one small evidence record or no result.

- **Use the settled eligibility boundary.** Consult `plan_tool/audit_shapes.py:is_advisory_emitter_eligible()` before producing the result. The evaluator must fail closed if the shape is not eligible; do not open-code an `arm-clustering` string check that could drift from step 1’s registry.

- **Apply the exact evidence and selection rule.** Let the denominator be *every* final normalized material conceptual finding, using the existing materiality result. Emit nothing unless there are at least three and every one has a consensus-validated target. Count each finding once by target, divide the represented target steps into maximal runs contiguous in declared plan order, and treat any declared step between endpoints without a target as a gap that partitions those runs. A run is eligible only when it is a proper subset of the full plan and its count is a strict majority of the full material denominator. A gap disqualifies only a proposed span that crosses it; a strict-majority run on one side remains eligible. Maximal runs are disjoint, so at most one can have a strict majority; report that unique run. A tie, insufficient support, any unattributed material finding, or a whole-plan run produces no advisory.

- **Reuse existing materiality semantics without widening them.** Let `plan_tool/review.py:audit_plan_until_stable()` remain the owner of the current audit’s materiality rule through `plan_tool/convergence.py:is_blocking_impact()`. Pass its outcome into the pure arm evaluator rather than duplicating severity/impact rules in `plan_tool/audit_shapes.py` or changing `plan_tool/convergence.py`.

- **Evaluate the final normalized result, not the pass series.** Build the advisory after the conceptual findings have been parsed and unioned, using the same selected `audit_recs` that `finalize_completeness_run()` renders. A fingerprint-approved `reused_audit_recs` set is an allowed selected result; it is not an input to cross-run diagnosis. Do not use `new_counts`, compare prior sidecars, add report checkpoints, use Git history, or persist reusable advisory state beyond normal rendered report text. For `--iterate`, calculate it before `write_pre_apply_audit_checkpoint()` and carry the same result through the final report.

- **Render one shared advisory, separately from coverage and again before apply.** Thread the optional result through `plan_tool/cli/completeness_phases.py:_render_grouped_report()`, `plan_tool/cli/completeness_phases.py:_render_completeness_json()`, `plan_tool/cli/completeness_phases.py:write_pre_apply_audit_checkpoint()`, and `plan_tool/completeness_report.py:console_summary()` / `build_report_md()`. Every populated surface must state the `arm-clustering` ID, the unique arm, countable evidence, and the rule that the user must either state why the arm belongs or propose a carve, and must explicitly say that continuing overrides the signal. At the start of `cmd_completeness_apply()`, after loading the saved review and current plan but before filtering, files-coherence work, serial walking, or parallel worktree dispatch, compare `saved.plan_fingerprint` with `compute_plan_fingerprint(plan_path)`. Only on equality recompute and print the same advisory from the saved conceptual recommendations. On mismatch, suppress the advice and replace every remaining saved walk recommendation's `step_id` with `None` in memory before filtering and dispatch, retaining the existing staleness warning and saved-finding walk without allowing a stale ID to change an apply target. Repeat that equality check immediately before each serial dispatch and every canonical replay that reruns `apply_finding`; parallel workers may receive a target only when their clean worktree starts at the saved audit fingerprint. When deterministic iterate edits change the plan after `write_pre_apply_audit_checkpoint()`, clear conceptual target IDs before final report persistence so its new plan fingerprint never falsely certifies an old target. These checks make no model call, do not mutate the sidecar or save reusable advice (normal report text may record the concurrent advisory), do not prompt or gate, and cover `--anchor`, `--jobs 1`, and `--jobs N` alike.

- **Keep the advice advisory and contain its output contract.** Do not represent it as a `Recommendation`, add it to blocking findings, include it in an apply queue, or change `has_blocking_findings` or command exit behavior. Existing `Recommendation.step_id` persistence is sufficient for normal apply targeting; do not add fields to saved reviews. The public JSON gains only a documented additive nullable `audit_shape_advisory` object for this report-time result. Preserve the established `coverage.recommendation_kind`, `recommended_passes`, and `recommendation_advice` keys as compatibility keys whose fresh values are always `null`; never repurpose them for arm advice.

- **Retire only the old route.** Remove the tapering, one-short, and non-converging recommendation behavior from `plan_tool/review.py:recommend_audit_passes()` and its `audit_plan_until_stable()` budget handoff. Keep coverage-limited status, pass counts, caps, and confirmation semantics intact; `plan_tool/cli/completeness_phases.py:emit_coverage_unconfirmed()` should still report uncertainty without a replacement action. Update active operator guidance in `BACKLOG.md` and `CLAUDE.md`, the `DATA_CONTRACT.md` JSON contract, CLI JSON/help, `docs/cli/`, and `docs/AUDIT_FLOW.md` so none advertises populated legacy recommendation fields or the retired route; document the null compatibility fields plus output-only arm advisory instead. Step 3 separately records the bounded #224 outcome in `BACKLOG.md`.

- **Isolate the target from cross-run diagnosis.** Keep `plan_tool/convergence_diagnosis.py`'s established anchor-based behavior for `plan-correctness` and `plan-completeness` report findings: while loading historical recommendations, ignore their new current-report `step_id` values rather than allowing `_finding_step_focus()` to use them. Do not change the diagnosis decision rules, fork thresholds, persistence shape, or other finding sources. A cross-run step focus would need its own identity and staleness contract, which is outside this plan.

- **Keep cross-run diagnosis separate.** `plan_tool/convergence_diagnosis.py:diagnose_convergence()` also reasons about repeated regions and contiguous step ranges, but it requires saved multi-run history and has a different decision purpose. Do not route this within-report advisory to it or alter its diagnosis decision rules; the narrow loader-side ignore rule above is only a compatibility fence for the new conceptual target.

## Tests

### Tests for this step

Every case below must be green before this step is complete.

- `tests/test_audit_shapes.py:test_arm_clustering_emits_one_advisory_for_a_unique_maximal_gap_free_strict_majority_arm` — three or more fully attributed material findings produce one evidence record for the unique maximal represented run.

- `tests/test_audit_shapes.py:test_arm_clustering_fails_closed_for_unattributed_ties_plan_wide_and_insufficient_support` — an untagged material finding and every other ambiguous or incomplete boundary produce no result.

- `tests/test_audit_shapes.py:test_arm_clustering_selects_a_strict_majority_maximal_run_on_one_side_of_a_gap` — a gap partitions runs but does not suppress a majority run that does not span it.

- `tests/test_audit_shapes.py:test_arm_clustering_respects_registry_eligibility` — the evaluator cannot emit when the registry does not mark the shape eligible.

- `tests/test_review.py:test_plan_audit_parser_accepts_only_the_literal_leading_step_id_target_tag` — the documented grammar reaches `Recommendation.step_id`, while prose and misplaced lookalikes do not.

- `tests/test_review.py:test_plan_audit_parser_accepts_zero_and_negative_schema_valid_step_ids` — every schema-valid integer step ID accepted by the prompt grammar can become a target.

- `tests/test_review.py:test_plan_audit_parser_and_union_fail_closed_on_invalid_or_conflicting_target_tags` — unknown, multi-step, plan-wide, missing, repeated, inferred-looking, and cross-sample-conflicting tags remain unattributed without losing the finding or redirecting apply.

- `tests/test_review.py:test_final_conceptual_audit_uses_arm_clustering_not_pass_taper` — the final unioned findings drive the advisory and the per-pass count route no longer does.

- `tests/test_review.py:test_budget_limited_audit_keeps_coverage_facts_with_null_legacy_advice_fields` — budget confidence remains available with all three retired compatibility fields `None`.

- `tests/test_completeness_report.py:test_report_renders_arm_clustering_evidence_and_override_rule` — saved Markdown includes the ID, arm, evidence count, keep-or-carve instruction, and explicit override wording.

- `tests/test_completeness_report.py:test_console_summary_renders_arm_clustering_without_creating_an_action` — iterate output exposes the scope decision without presenting an apply result.

- `tests/cli/test_completeness_cmd.py:test_audit_only_reuse_checkpoint_and_iterate_share_arm_clustering_advice` — each fresh or approved-reuse report route receives the same prepared optional advisory.

- `tests/cli/test_completeness_cmd.py:test_completeness_json_exposes_output_only_arm_advice_without_changing_blocking_state` — JSON emits the documented additive advisory while preserving the null legacy coverage keys and existing gate result.

- `tests/cli/test_completeness_cmd.py:test_completeness_apply_recomputes_fingerprint_fresh_arm_advice_before_serial_dispatch` and `tests/cli/test_completeness_apply_parallel.py:test_completeness_apply_recomputes_fingerprint_fresh_arm_advice_before_parallel_dispatch` — fingerprint-fresh saved findings produce the same non-gating message before either apply lane runs; a plan-fingerprint mismatch suppresses it, preserves the existing gap walk, and clears every in-memory `step_id` before the serial or parallel dispatcher sees it.

- `tests/cli/test_completeness_cmd.py:test_completeness_apply_clears_remaining_targets_after_a_serial_plan_edit`, `tests/cli/test_completeness_apply_parallel.py:test_parallel_replay_clears_target_when_canonical_plan_drifted`, and `tests/cli/test_completeness_cmd.py:test_iterate_final_persistence_clears_targets_after_deterministic_plan_edits` — a target never outlives the fingerprint it was audited against, including the checkpoint-to-final-report seam.

- `tests/test_convergence_diagnosis.py:test_history_ignores_plan_audit_step_id_for_cross_run_focus` — a persisted `plan-correctness` or `plan-completeness` target retains anchor-based cross-run behavior and cannot alter a fork.

- `tests/cli/test_review_actions.py:test_apply_finding_uses_attributed_step_id_as_its_existing_target` — a valid tag preserves rather than repurposes the existing apply target.

- `tests/test_cli.py:test_completeness_audit_output_has_no_taper_or_non_converging_route` — public command output no longer presents the retired guidance while normal coverage reporting still works.

- `tests/test_cli.py:test_active_operator_docs_do_not_advertise_legacy_coverage_recommendations` — the explicitly owned `CLAUDE.md`, `DATA_CONTRACT.md`, `docs/AUDIT_FLOW.md`, `docs/cli/`, and the active BACKLOG #125 stopping-rule and “Auditing Plans” guidance retain coverage facts but do not present populated legacy recommendation fields or the retired route. Historical backlog evidence may describe the retired behavior without acting as instructions.

## Acceptance criteria

- A conceptual-audit finding receives `Recommendation.step_id` only from the literal leading tag for one audited plan step that its remedy targets; the grammar covers every schema-valid integer ID. Prose, anchors, unknown IDs, aggregate tags, or a cross-sample disagreement do not supply attribution.

- The arm evaluator produces one result only for at least three material findings when every one has consensus-validated attribution and a unique maximal, non-plan-wide, gap-free contiguous arm has a strict majority.

- Tied, missing, invalid, conflicting, plan-wide, and insufficient attribution produce no arm-clustering advisory; gaps partition maximal arms and a majority arm that does not span one remains eligible.

- Markdown, concise iterate output, pre-apply checkpoint, JSON, and the serial and parallel saved-apply entry points show the same populated advisory with its stable ID, evidence, and user-owned override rule.

- A stale saved review never routes an apply by a reused numeric `step_id`: it
  remains reviewable with in-memory target IDs unset, and its advisory remains
  suppressed until a fresh audit is saved.

- A target is cleared whenever its audited fingerprint no longer equals the
  current plan—before final iterate persistence, every remaining serial apply,
  and a canonical replay. Cross-run diagnosis ignores conceptual-audit target
  IDs rather than treating them as historical step focus.

- The advisory is not a `Recommendation`, does not enter an apply path, and does not affect blocking state, exit codes, or plan mutation.

- Coverage-limited reporting retains its confidence facts and null-compatible legacy fields but no longer emits tapering, non-converging, or `plan-tool convergence` guidance as a coverage remedy.

- `CLAUDE.md`, `DATA_CONTRACT.md`, `docs/AUDIT_FLOW.md`, and `docs/cli/` describe the within-report arm-clustering route, compatibility boundary, and its owning symbols without replacing documentation for the independent cross-run convergence command.

- All listed tests pass.

## References

- [Python dataclasses documentation](https://docs.python.org/3/library/dataclasses.html) — Reference for the small immutable evidence result returned by the pure evaluator.

- [Python unittest documentation](https://docs.python.org/3/library/unittest.html) — Reference for focused boundary and rendering tests.

## Applicable guardrails

- **The plan’s `intent`, advisory classification boundary** — use step 1’s registry to limit this implementation to the currently eligible advisory shape; do not add an emitter for another classification.

- **The plan’s step 2 intent, user-owned scope decision** — present the concentrated arm before conceptual findings are manually acted on, but leave the keep-or-carve choice with the user.

- **The plan’s `## Out of scope`, persistence and automation fence** — keep this work in the current report flow with no new history contract, no automatic remedy, and no behavior that turns the advice into a gate.

## Deferred

- `plan_tool/convergence_diagnosis.py:diagnose_convergence()` — cross-run diagnosis remains a separate saved-history feature and is not a fallback for this current-report advisory.

- `plan-seeds/audit-shape-saturation-and-provenance.md` — future observable contracts for the deferred audit shapes remain outside this implementation.
