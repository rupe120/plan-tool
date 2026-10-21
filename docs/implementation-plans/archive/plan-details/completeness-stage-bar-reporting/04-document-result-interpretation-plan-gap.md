> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Document result interpretation and plan-gap handoff

## Summary

Document the qualified completeness-result contract and its operator handoff in `CLAUDE.md`, `docs/AUDIT_FLOW.md`, and `integrations/shared/DIRECTIVES.md`. Make the audit-flow documentation the detailed home for headline precedence, explicit no-sample qualifiers, audit-time versus view-time plan/detail revision status, bare-plan meaning, and Jira-grade limits. State plainly that a conceptual audit uses live project context to explain why an issue matters; only the plan and grade-selected detail revision identify what the saved result is about. Keep the assistant-led plan-gap map advisory and human-owned. On green, an operator can interpret a final audit result and choose the safe next conversation or command without reading implementation code.

## Table of Contents

- [Summary](#summary) — Reviewer-level outcome of the documentation update.
- [Why](#why) — The operator-facing gap this step closes.
- [Input](#input) — Result and authoring contracts supplied by steps 1–3.
- [Files (creates vs edits)](#files-creates-vs-edits) — Documentation files this step changes.
- [Implementation](#implementation) — Required interpretation and handoff rules.
- [Tests](#tests) — Existing behavior coverage and non-code verification.
- [Acceptance criteria](#acceptance-criteria) — Observable documentation outcomes.
- [References](#references) — JSON references relevant to the documented payload.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries for this documentation-only step.
- [Deferred](#deferred) — Work this step intentionally leaves elsewhere.

## Why

The existing audit guidance explains stages, coverage, checkpoints, and apply routes in separate places, while steps 1–3 establish one final qualified result and authoring handoff. Without a single interpretation path, an operator can mistake a bare-plan result, noncurrent sidecar, checkpoint, Jira-grade report, or `terminal_hand_apply` stop for evidence that supports the wrong next command. It can also leave an operator unsure why the model was allowed to use project context while the result only identifies plan/detail artifacts. This step makes both meanings clear without changing the audit policy it describes.

## Input

- **Step 1 result contract:** Step 1 supplies the ordered final headlines: `no-qualified-current-evidence`, `awaiting-human-action`, `advisory-only`, and `clean`. Its result facts distinguish confirmed audit coverage and audit-time stage from the audited plan revision and selected-detail revision.

- **Live project context:** Code, prompts, lessons, configuration, and previous audits provide context for the model to explain why a plan issue is an issue. They remain live context: this plan neither freezes them nor makes their later change a reason to label a saved plan/detail result stale.

- **Step 2 presentation and persistence:** Step 2 exposes `qualified_result` through `plan_tool/cli/completeness_phases.py:_render_completeness_json()`, `plan_tool/completeness_report.py:build_report_md()`, and the `SavedReview` persistence boundary in `plan_tool/review_persistence.py`. Its immutable `revision_status` differs from the later read-time `view_revision_status`, which compares only the plan and grade-selected details identified by the result. A v4 completeness sidecar carries this new contract; v1–3 records remain legacy-readable and an older reader rejects v4 rather than dropping it.

- **Step 3 authoring handoff:** Step 3 makes `plan_tool/cli/authoring.py:_run_completeness_tail()` and the create/detail/split/merge commands use only final, current evidence with matching audited plan/detail artifacts. The documentation must describe that result without rebuilding its selection policy.

- **Existing flow anchors:** Use `docs/AUDIT_FLOW.md:### Stage bar and mid-run steering`, `### Pre-apply checkpoint vs. final report — the persisted role`, and `### Auditing against the jira-grade bundle (--grade jira)` as the nearby operator contracts.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `CLAUDE.md` — Update the `## Reference docs` entry and concise audit-lifecycle guidance so future authoring sessions point to `docs/AUDIT_FLOW.md` for qualified-result interpretation and grade-aware handoff.
  - `docs/AUDIT_FLOW.md` — Add the detailed result-precedence, plan/detail revision, bare-plan, Jira-grade, live-context, and assistant handoff guidance; update `## Source map` with the settled result and authoring anchors.
  - `integrations/shared/DIRECTIVES.md` — Align the two audit gates, assistant-driven conceptual-gap handling, and the `Present plan gaps before making a scope decision` guidance with the qualified-result contract.

## Implementation

- **Foundational logic: qualified-result interpretation and assistant-led plan-gap handoff.** Document one reader-facing interpretation order: qualification comes before the headline, and the headline comes before a next-step suggestion. Do not ask readers to infer the result from a finding count, an exit code, a stage name, or a report filename.

- **Make `docs/AUDIT_FLOW.md` the detailed operator reference.** Add a compact result section near `### Stage bar and mid-run steering` that names all four headlines and states their precedence. Explain that `no-qualified-current-evidence` wins when final current evidence is unavailable; `awaiting-human-action` names qualified work requiring judgment; `advisory-only` preserves qualified non-blocking findings; and `clean` requires the existing clean finalization conditions and no result-bearing finding.

- **Keep result facts separate.** Explain the separate meanings of audit stage, audit coverage, and audit-time plan/detail revision. An absent, skipped, or pre-capture failed audit has explicit `not-sampled` stage/coverage/revision and null audit revision, while a completed fresh but incomplete audit preserves its bare/detail stage with `unconfirmed` coverage. A bare-stage audit can be qualified for plan-level work, while incomplete coverage, stale/unknown revision evidence, or missing/incomplete/nonmatching plan/detail revision cannot become current qualified evidence. Do not describe detail-bundle coverage as the same fact as conceptual-audit coverage.

- **Explain live context without weakening provenance.** State that the audit intentionally reads the live project so its feedback can say why an issue matters in this project. Code, prompts, lessons, configuration, and history are explanation context, not an asserted frozen input set. The saved audit revision identifies the audited plan and selected detail bundle; a later change to either makes the saved result noncurrent, while a later change to live context alone does not claim to invalidate or reproduce it.

- **Preserve audit-time history and schema compatibility.** In the persisted-role discussion, describe `qualified_result.revision_status` and `qualified_result.audit_revision` as facts captured when the audit completes. Describe `view_revision_status` as a later plan/detail comparison. Explain that both new final and checkpoint completeness sidecars write schema version 4, while v1–3 remain legacy-readable and a pre-v4 reader rejects v4 rather than silently losing `qualified_result`. The later view or an annotation rewrite must not rewrite the saved result, downgrade its version, or make a checkpoint, legacy payload, incomplete revision, or noncurrent sidecar appear current.

- **Explain bare-plan withholding precisely.** Keep `DetailBundleStatus.is_bare`, `plan_tool/completeness_report.py:_actionable_conceptual_gaps()`, and `plan_tool/cli/completeness_cmd.py:cmd_completeness_apply()` as source anchors for the existing split. State that a bare plan does not turn missing detail-level work into an automatic apply target; it may still leave plan-level findings for human review or the permitted plan-level route.

- **Describe Jira grade as a separate evidence lane.** Extend `### Auditing against the jira-grade bundle (--grade jira)` to state that Jira-grade output uses its selected bundle and fresh audit route, never a run-grade sidecar as substitute evidence. Preserve the documented report-only, no-reuse, no-iterate, and no-apply limits; this documentation must not imply that `cmd_completeness_apply()` can consume Jira-grade findings.

- **Connect authoring output to the same rule.** Describe the final-only handoff from `plan_tool/cli/completeness_phases.py:_persist_and_present_report()` to `plan_tool/cli/authoring.py:_run_completeness_tail()`. A create or authoring change that has no current qualified result with matching plan/detail artifacts leads to a fresh grade-matched audit; only an ordinary final, current qualified result retains its existing result-aware guidance.

- **Keep plan-gap presentation human-owned.** Update `integrations/shared/DIRECTIVES.md` around `Who is driving decides how conceptual gaps get closed` and `Present plan gaps before making a scope decision`. When qualified evidence leaves plan-level gaps requiring discussion, the assistant starts with the plan intent and groups related findings by responsibility before proposing a possible next step. Keep deterministic diagnostics, implementation mechanics, out-of-scope suggestions, and telemetry separate from that map.

- **Do not turn the map into a verdict.** The plan-gap map preserves source, severity, and stable anchors, but it does not label a plan ready, choose an apply/defer/carve action, or create a new gate. When no current qualified evidence exists, direct the operator to a fresh audit instead of presenting stale findings as a plan-gap decision surface.

- **Avoid duplicate policy prose.** Use `CLAUDE.md:## Reference docs` as a terse pointer and keep detailed semantics in `docs/AUDIT_FLOW.md`. Update `docs/AUDIT_FLOW.md:## Source map` to orient readers to `finalize_completeness_run()`, `_render_completeness_json()`, `_persist_and_present_report()`, `build_report_md()`, `SavedReview.qualified_result`, and `_run_completeness_tail()` without restating their implementation.

## Tests

No test files change in this documentation-only step. Confirm the documented behavior against the coverage supplied by the prerequisite steps:

- `tests/cli/test_completeness_cmd.py:test_qualified_result_precedence_and_advisory_remainder` — Confirms unavailable evidence takes precedence over a stop state and that qualified non-blocking work remains advisory.
- `tests/test_completeness_report.py:test_completeness_json_keeps_qualified_result_additive` — Confirms the final JSON result object retains its existing payload contract.
- `tests/test_completeness_report.py:test_report_renders_qualified_result_and_routes_unqualified_to_audit` — Confirms reports present the qualified result and route unavailable evidence to a fresh audit.
- `tests/cli/test_authoring_cmds.py:TestDetailTailAuditFollowUp.test_unqualified_or_missing_run_tail_routes_to_fresh_audit` — Confirms authoring does not reuse unsafe tail guidance.
- `tests/cli/test_authoring_cmds.py:TestDetailGradeRouting.test_grade_jira_skips_the_completeness_tail` — Confirms Jira-grade authoring does not expose the run-grade sidecar tail.

### Verification (non-code step)

1. Check every result headline in `docs/AUDIT_FLOW.md` against Step 1’s final result contract and confirm the precedence wording does not create another classifier.

2. Check the documented JSON and sidecar terms against Step 2’s `qualified_result`, including `not-sampled` qualifiers, immutable plan/detail audit revision fields, v4 final/checkpoint write behavior, v1–3 legacy readability, and plan/detail read-time freshness language.

3. Check the live-context explanation against the plan intent: it must explain why project context is used without claiming to capture, freeze, sandbox, or reproduce it.

4. Check the bare-plan and Jira-grade wording against `plan_tool/completeness_report.py:_actionable_conceptual_gaps()`, `plan_tool/cli/completeness_cmd.py:cmd_completeness_apply()`, and the Jira-grade section of `docs/AUDIT_FLOW.md`.

5. Check the authoring handoff language against Step 3’s final-only parent transport and confirm it offers a fresh grade-matched audit when qualified current evidence is absent.

6. Check Markdown links, `docs/AUDIT_FLOW.md:## Source map` anchors, and `CLAUDE.md:## Reference docs`; use symbolic anchors only and add no raw line-number references.

## Acceptance criteria

- `docs/AUDIT_FLOW.md` names the four final result headlines and explains their qualification and precedence without changing stage-bar or exit-code policy.
- The documentation distinguishes audit stage, audit coverage, explicit no-sample qualification, immutable audit-time plan/detail revision status, and later plan/detail `view_revision_status`.
- The documentation explains that final and checkpoint completeness sidecars carrying `qualified_result` use v4, v1–3 sidecars remain legacy-readable, and annotation writes preserve v4 rather than silently dropping the contract.
- The documentation states that project code and other project context remain live explanation context, and that only a plan or selected-detail change makes a saved audit result noncurrent.
- The bare-plan guidance states both that bare audits can provide plan-level evidence and that withheld detail-level work does not become an automatic apply route.
- The Jira-grade guidance directs readers to grade-matched fresh audits and does not suggest run-grade reuse, iteration, or apply commands for Jira findings.
- `integrations/shared/DIRECTIVES.md` requires an assistant to present qualified in-scope plan gaps by responsibility, with plan intent and source evidence, before a scope discussion.
- The plan-gap map remains advisory: it does not assign user decisions, create a new gate, or mix non-plan output into the map.
- `CLAUDE.md` points readers to `docs/AUDIT_FLOW.md` for the detailed contract, and the flow document’s source map names the finalization, rendering, persistence, and authoring handoff anchors.
- Only `CLAUDE.md`, `docs/AUDIT_FLOW.md`, and `integrations/shared/DIRECTIVES.md` change.

## References

- [json — JSON encoder and decoder](https://docs.python.org/3.13/library/json.html) — Use the standard-library JSON model when describing additive result objects and `null` checkpoint values.
- [RFC 8259: The JavaScript Object Notation (JSON) Data Interchange Format](https://datatracker.ietf.org/doc/html/rfc8259) — Use interoperable JSON terminology when documenting persisted and `--json` result fields.

## Applicable guardrails

- **The plan’s “## Plan intent”** — Describe one qualified result contract across reports, JSON, failures, and authoring handoffs; do not introduce a competing interpretation rule.
- **The plan’s “## Step intent”** — Keep this step focused on making precedence, bare-plan meaning, revision qualification, live-context meaning, Jira-grade handoff, and assistant-led gap presentation understandable.
- **The plan’s “## Out of scope”, audit policy** — Do not alter stage bars, finding thresholds, pass policy, automatic-apply eligibility, or exit semantics while documenting them.
- **The plan’s “## Out of scope”, process behavior** — Do not create a new approval gate, automatic plan decision, or project-context snapshot through documentation.

## Deferred

- **Broad audit policy redesign** — Finding taxonomy, scoring, stage-bar policy, exit semantics, and apply policy remain outside this reporting/documentation plan.
- **Unrelated directives cleanup** — Preserve directives that do not concern qualified audit-result interpretation or plan-gap handoff.
