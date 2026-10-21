> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Render fresh arm advice and retire count-only guidance

## Summary

Render the step 2 `AuditShapeAdvisory` at completeness-audit and completeness-apply decision points when its source-plan fingerprint matches the current plan. Update `plan_tool/cli/completeness_cmd.py`, `plan_tool/cli/completeness_phases.py`, and `plan_tool/completeness_report.py` so fresh, reused, checkpoint, report, concise-console, and JSON paths consume the same stored advisory. Retire `plan_tool/review.py:recommend_audit_passes()` and its count-series operator guidance while retaining the three public compatibility keys as `null`. When green, users see an evidence-bearing, non-blocking keep-or-carve prompt only for current evidence, and neither serial nor parallel apply behavior changes.

## Table of Contents

- [Summary](#summary) — The completed behavior and main files.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — The missing decision prompt and obsolete count route.
- [Input](#input) — Upstream advisory, freshness, and JSON contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — All in-scope code, tests, and docs.
- [Implementation](#implementation) — Freshness, rendering, apply, and compatibility rules.
- [Tests](#tests) — Focused test coverage for every presentation path.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Relevant primary references.
- [Applicable guardrails](#applicable-guardrails) — Boundaries on this advisory-only step.
- [Deferred](#deferred) — Work intentionally left outside this step.

## Why

`plan_tool/review.py:recommend_audit_passes()` currently turns pass-count trends into operator advice, but that cannot tell a user where the plan’s material conceptual gaps concentrate. Steps 1 and 2 provide a typed, evidence-bearing arm result instead; this step must make that result visible only while it still describes the current plan, without turning it into a recommendation target or an apply control.

## Input

- **Step 1 and step 2 advisory:** consume the registry-owned optional saved-review advisory. Treat its shape ID, ordered evidence, counts, and source-plan fingerprint as settled input; do not re-evaluate arm clustering in this step. Step 2 loads an invalid optional advisory as unavailable while leaving an otherwise valid saved review usable, so this step sees it exactly as no advisory.

- **Freshness source:** compare the advisory’s stored source fingerprint with the current result from step 2's dedicated exact audit-input snapshot helper. Do not use the generic saved-review `compute_plan_fingerprint()` for advisory freshness. A missing or mismatched fingerprint makes the advisory unavailable for presentation.

- **Reuse contract:** `plan_tool/completeness_report.py:resolve_reusable_audit()` returns the saved completeness review and its existing reuse verdict. A reusable finding list does not by itself prove that the advisory is fresh; apply the advisory’s own source-plan check.

- **Compatibility JSON:** preserve `coverage.recommendation_kind`, `coverage.recommended_passes`, and `coverage.recommendation_advice` in `plan_tool/cli/completeness_phases.py:_render_completeness_json()`. They remain schema-compatible fields with `null` values, not a second advice channel.

- **Apply queue:** keep the conceptual `Recommendation` list used by `plan_tool/cli/completeness_cmd.py:cmd_completeness_apply()` unchanged. The advisory is presentation data only and never participates in source filtering, anchoring, annotations, or dispatch.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/review.py` — remove `recommend_audit_passes()` and count-series recommendation output while keeping budget and confirmation facts available.
  - `plan_tool/cli/completeness_cmd.py` — carry the stored advisory through fresh and reused audit paths; present it before serial saved-apply work; update generated-CLI help text.
  - `plan_tool/cli/completeness_phases.py` — render the advisory in grouped and JSON audit output, carry it through checkpoint/final reporting, and remove count-based coverage advice.
  - `plan_tool/cli/completeness_apply_parallel.py` — ensure the parallel path receives the one parent-process pre-apply presentation before workers or replay begin.
  - `plan_tool/completeness_report.py` — render the advisory in persisted reports and concise iterate output using the same freshness rule.
  - `tests/test_completeness_report.py` — cover report and concise-summary presentation.
  - `tests/test_review.py` — cover retired count guidance and compatibility-null coverage output.
  - `tests/test_cli.py` — cover end-to-end fresh, reused, stale, and JSON command behavior.
  - `tests/cli/test_completeness_cmd.py` — cover grouped, checkpoint, reuse, and JSON handoffs.
  - `tests/cli/test_completeness_apply_parallel.py` — cover one-time parallel pre-dispatch presentation.
  - `DATA_CONTRACT.md` — document the saved advisory and additive JSON object; mark the retained coverage fields as compatibility-only nulls.
  - `docs/AUDIT_FLOW.md` — replace count-trend routing with the stored-advisory flow and update the source map.
  - `docs/cli/README.md` — regenerate the command summary from parser help.
  - `docs/cli/completeness-audit.md` — regenerate the audit reference with advisory and JSON behavior.
  - `docs/cli/completeness-apply.md` — regenerate the apply reference with the fresh pre-apply prompt behavior.

## Implementation

- **Make source-snapshot freshness the foundational logic.** Call the same exact audit-input snapshot helper that step 2 used at capture time; accept a stored advisory only when its source fingerprint equals the current fingerprint of the plan and exact resolved run-grade detail inputs. Missing, malformed, or mismatched optional-advisory data must produce no advisory while the existing saved findings and annotations remain usable. Do not use the generic saved-review fingerprint, and do not rebuild an arm from current findings, report history, or finding prose.

- **Thread one stored payload through every supported result path.** Extend the run-grade handoffs around `plan_tool/cli/completeness_cmd.py:finalize_completeness_run()`, `_run_iterate_convergence_loop()`, and `plan_tool/cli/completeness_phases.py:write_pre_apply_audit_checkpoint()` so fresh and accepted-reuse runs retain the same advisory alongside their conceptual findings. Step 2 may omit a candidate only before its initial checkpoint save when sampling drifted; after that save, an iterate edit must preserve the original payload into the final sidecar and suppress only its presentation rather than restamping or clearing it. JIRA-grade audits deliberately have no advisory producer or renderer.

- **Render bounded evidence, not a derived conclusion.** Use `plan_tool/cli/completeness_phases.py:_render_grouped_report()` and `plan_tool/completeness_report.py:build_report_md()` to show the `arm-clustering` ID, ordered arm step numbers and titles from the fingerprint-matching plan, the stored material/arm counts, and the stored anchor slugs grouped by their audit axis. The normal audit output remains the location of finding text; do not persist or reconstruct finding prose from opaque IDs. State plainly that continuing with the current arm overrides the signal; the prompt itself must not block, command, or require acknowledgement.

- **Keep reports and concise output aligned.** `plan_tool/completeness_report.py:console_summary()` should surface the same current advisory in the compact iterate result, while the persisted report and audit-only grouped output retain the evidence needed to make the decision. Use a shared renderer or a single prepared display value so the wording and freshness rule cannot drift.

- **Add the advisory to public JSON without changing gates.** Have `plan_tool/cli/completeness_phases.py:_render_completeness_json()` emit the documented additive `audit_shape_advisory` object only when the stored payload is fresh. Keep `has_blocking_findings`, `--fail-on-findings`, and process exit behavior unchanged.

- **Retire count-only guidance completely.** Remove `plan_tool/review.py:recommend_audit_passes()` and `_fmt_audit_series()`, plus `plan_tool/cli/completeness_phases.py:_coverage_advice()` and `_COVERAGE_FALLBACK_ADVICE`. `emit_coverage_unconfirmed()` may retain its budget-limited fact, pass count, cap, and confirmation-kind reporting, but must not read `recommendation_advice` or append either a specific recommendation or the generic “re-run with a higher `--audit-passes`” fallback. Never recommend a pass count, label a trend, or redirect to `plan-tool convergence` from this audit budget path.

- **Keep the legacy coverage schema stable.** Populate `recommendation_kind`, `recommended_passes`, and `recommendation_advice` as `None` in every budget outcome, including budget-limited ones. Do not remove or repurpose them; the new advisory is a separate additive output field.

- **Present before apply, never inside apply.** In `plan_tool/cli/completeness_cmd.py:cmd_completeness_apply()`, load and freshness-check the saved advisory after loading the completeness sidecar and before filtering or dispatching findings. For `--jobs > 1`, use `plan_tool/cli/completeness_apply_parallel.py:run_parallel_apply()`’s parent-side handoff so the message appears once before worker provisioning or replay. Do not render from workers and do not change their `Recommendation` inputs.

- **Suppress stale advice without changing the saved walk.** A stale advisory must not display in serial or parallel mode, but the existing detail-staleness warning, saved findings, annotations, queue order, and normal apply behavior remain available. Do not rewrite the sidecar or clear annotations as part of suppression.

- **Regenerate CLI reference docs.** Update the relevant parser help in `plan_tool/cli/completeness_cmd.py:register()`, then run the documented `python -m plan_tool.cli_reference --write` workflow rather than hand-editing `docs/cli/README.md`, `docs/cli/completeness-audit.md`, or `docs/cli/completeness-apply.md`.

## Tests

### Tests for this step

Every test below must be green before this step is complete.

- `tests/test_review.py:test_budget_limited_audit_keeps_legacy_coverage_advice_fields_null` — a capped audit retains budget facts while all three retired advice fields are `None`.

- `tests/test_review.py:test_audit_plan_until_stable_emits_no_count_based_operator_route` — the audit no longer emits taper, one-short, non-converging, or suggested-pass guidance.

- `tests/cli/test_completeness_cmd.py:test_budget_limited_coverage_reports_facts_without_a_passes_fallback` — a recommendation-less budget-limited result may report its cap and confirmation state but contains neither a specific recommendation nor the generic higher-`--audit-passes` directive.

- `tests/test_completeness_report.py:test_fresh_audit_shape_advisory_renders_evidence_and_override` — report and concise output show the stored evidence and the user-owned override statement.

- `tests/test_completeness_report.py:test_stale_audit_shape_advisory_is_not_rendered` — a fingerprint mismatch removes only the advisory from report surfaces.

- `tests/test_cli.py:test_malformed_optional_audit_shape_advisory_does_not_block_apply_walk` — an otherwise valid sidecar with a malformed advisory still reaches the unchanged saved conceptual walk and renders no advisory.

- `tests/test_completeness_report.py:test_audit_shape_advisory_renders_typed_evidence_without_finding_prose` — a fresh advisory names the committed arm, counts, and stored anchor/axis evidence without displaying opaque finding IDs or persisting finding text.

- `tests/cli/test_completeness_cmd.py:test_grouped_and_json_audit_output_share_a_fresh_advisory` — grouped output and JSON expose the same current payload without changing blocking status.

- `tests/cli/test_completeness_cmd.py:test_checkpoint_and_final_report_apply_the_current_fingerprint_rule` — the checkpoint can show fresh advice while a later plan change suppresses it in the final report.

- `tests/cli/test_completeness_cmd.py:test_iterate_preserves_a_stale_saved_advisory_for_final_sidecar` — a post-checkpoint plan edit retains the original payload in the final sidecar while every later renderer suppresses it.

- `tests/cli/test_completeness_cmd.py:test_reused_audit_uses_saved_advisory_only_when_its_source_plan_matches` — accepted reuse presents the saved evidence verbatim and suppresses an advisory with a mismatched source fingerprint.

- `tests/test_cli.py:test_completeness_audit_json_keeps_compatibility_fields_and_adds_fresh_arm_advice` — command-level JSON keeps the old keys null and adds the advisory only when current.

- `tests/test_cli.py:test_completeness_apply_stale_arm_advice_does_not_change_saved_finding_walk` — stale advice is hidden while the saved conceptual walk and return behavior remain unchanged.

- `tests/cli/test_completeness_cmd.py:test_jira_grade_has_no_audit_shape_advisory_surface` — JIRA-grade audit output and JSON retain their existing no-advisory contract.

- `tests/cli/test_completeness_apply_parallel.py:test_parallel_apply_presents_fresh_arm_advice_once_before_dispatch` — the parent process presents fresh advice before workers run, with no worker-side duplicate output or queue mutation.

## Acceptance criteria

- A fresh qualifying completeness audit presents one evidence-bearing `arm-clustering` keep-or-carve prompt in grouped output, persisted report text, concise iterate output, and documented JSON.

- A reused audit presents exactly its stored advisory only when the advisory’s source-plan fingerprint matches the current plan.

- A plan change after a checkpoint or before serial or parallel apply suppresses the advisory without blocking, rewriting, retargeting, or removing saved findings.

- A malformed optional advisory is suppressed without preventing serial or parallel saved-finding review; malformed core sidecar data continues to follow the existing error path.

- Serial and `--jobs N` completeness-apply present fresh advice before normal conceptual work starts; neither path adds the advisory to an apply queue or worker input.

- `coverage.recommendation_kind`, `coverage.recommended_passes`, and `coverage.recommendation_advice` remain present and `null` for every JSON outcome.

- A budget-limited audit can report coverage facts but never tells the operator to increase `--audit-passes`, whether through a data-specific route or an absent-advice fallback.

- `has_blocking_findings`, `--fail-on-findings`, normal apply ordering, annotations, and process exit codes are unchanged by advisory presence or absence.

- `rg -n 'recommend_audit_passes|one-short|tapering|non-converging' plan_tool/review.py plan_tool/cli/completeness_phases.py plan_tool/completeness_report.py` returns no matches.

- Regenerated `docs/cli/README.md`, `docs/cli/completeness-audit.md`, and `docs/cli/completeness-apply.md` match the parser help, and all listed tests pass.

## References

- [Python dataclasses](https://docs.python.org/3.13/library/dataclasses.html) — Reference immutable advisory payloads without adding mutable routing state.

- [Python JSON encoder and decoder](https://docs.python.org/3.13/library/json.html) — Preserve the additive JSON contract and null compatibility fields.

- [Python hashlib](https://docs.python.org/3.13/library/hashlib.html) — Understand the fingerprint comparison that controls presentation freshness.

- [pytest parametrization](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Cover fresh, reused, stale, serial, and parallel cases compactly.

## Applicable guardrails

- **The plan’s `intent`, dedicated advisory transport** — render only the typed stored payload; do not use `Recommendation.step_id` or finding prose to recreate attribution.

- **The plan’s step 3 intent, fresh decision aid** — show keep-or-carve advice only when its own source-plan fingerprint matches current plan content.

- **The plan’s `## Out of scope`, dispatch and automation fence** — do not change generic walks, launcher behavior, software blocking, exits, automatic carving, automatic apply, or product-level acknowledgement. Preserve the separate agent-facing override policy documented by step 4.

- **The plan’s `## Out of scope`, audit-shape boundary** — do not add presentation or emitter behavior for the other audit shapes.

## Deferred

- Cross-run convergence interpretation in `plan_tool/convergence_diagnosis.py:diagnose_convergence()` — it remains separate from this single-audit advisory.

- Additional audit-shape emitters — remain outside this step under the plan’s audit-shape scope fence.

- Registry documentation validation and backlog alignment — step 4 owns the `CLAUDE.md`, inspect, test, and backlog work.
