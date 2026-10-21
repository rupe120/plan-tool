> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Align Roadmap operator guides and close the route-local brief-drift record after all three route policies ship

## Summary

Align the Roadmap operator guides with the landed changed-brief and legacy-brief policies from steps 2 through 5. Update the public command descriptions, architecture and capability records, agent-facing guidance, and backlog routing without changing production behavior. Keep each non-stage route’s result, write boundary, and stage-run separation clear. On green, operators can tell which routes refuse, which inspection result remains successful, and why `--from-existing` does not repair a non-stage route.

## Table of Contents

- [Summary](#summary) — States the completed documentation outcome.
- [Table of Contents](#table-of-contents) — Links to the detail sections.
- [Why](#why) — Explains the operator-facing gap this step closes.
- [Input](#input) — Names the landed route contracts that guide wording must follow.
- [Files (creates vs edits)](#files-creates-vs-edits) — Lists the documentation and drift-guard edits.
- [Implementation](#implementation) — Defines the route-specific guide updates and backlog closure.
- [Tests](#tests) — Names the documentation drift checks.
- [Acceptance criteria](#acceptance-criteria) — Lists observable completion conditions.
- [References](#references) — Points to the route contracts and delivery scope.
- [Applicable guardrails](#applicable-guardrails) — Applies the plan boundaries to this documentation work.
- [Deferred](#deferred) — Records adjacent work outside this step.

## Why

The stage-run source-admission guidance already explains changed and legacy briefs, while the three non-stage routes have separate authority and result contracts. Without a focused update, an operator can mistake a redacted non-stage refusal for stage-run admission, use `--from-existing` as an unsupported repair path, or miss that a log-free impact view reports a no-route state successfully. Closing the route-local brief-drift record must leave one current explanation of the delivered policies and retain #367 as the separate stage-run operator-intent decision.

## Input

- **Steps 2 and 3 route outcome:** Read the landed `plan_tool/roadmap_impact_run.py:ImpactRunCommandOutcome`, `plan_tool/roadmap_impact_run.py:ImpactAnalysisCurrentStatus`, `plan_tool/roadmap_impact_run.py:run_roadmap_impact_analysis`, and `plan_tool/roadmap_impact_run.py:current_impact_analysis` contracts before documenting analysis creation and inspection.

- **Step 4 route outcome:** Read the landed `plan_tool/roadmap_structural_revision.py:load_structural_revision_preflight`, `plan_tool/roadmap_structural_revision_run.py:run_structural_revision`, and `plan_tool/roadmap_structural_revision_run.py:StructuralRevisionResult` contracts before documenting structural rewrite ordering and refusals.

- **Step 5 route outcome:** Read the landed `plan_tool/roadmap.py:enroll_roadmap_root`, `plan_tool/roadmap.py:ImmutableRootEnrollmentResult`, and `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_enroll_version` contracts before documenting immutable-root enrollment.

- **Source and disclosure contracts:** Treat `ROADMAP_FORMAT.md:Concept-brief source admission and lifecycle` and the Roadmap lifecycle sections in `DATA_CONTRACT.md` as the source for digest meaning, redaction, and route-specific events. The landed code wins if an earlier detail file differs.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `README.md` — align the command synopsis and `### 0. roadmap` operator flow with the three non-stage policies.
  - `RUNBOOK.md` — update the quick reference and Roadmap recovery workflow with route-specific changed and legacy outcomes.
  - `CLAUDE.md` — correct the top-level Roadmap structural-feedback overview without expanding it into an operator runbook.
  - `CAPABILITIES.md` — update the `## Architecture roadmap` capability record for analysis, structural rewrite, and root enrollment.
  - `docs/ARCHITECTURE.md` — describe the landed boundaries in `## Roadmap`’s impact, structural, and brief-source sections.
  - `docs/CODEX_CLI_CONTRACT.md` — update `## Structural evaluator capability profile` with the structural route’s brief-drift ordering and no-write result.
  - `docs/ROADMAP_WALKTHROUGH.md` — add the route-local operator guidance to the command sequence and structural-feedback walkthrough.
  - `integrations/claude/SKILL.md` — align the Roadmap command-selection and rewrite entries with the landed route policies.
  - `BACKLOG.md` — replace the open route-local brief-drift decision language with a concise closed delivery record and retain #367 as separate work.
  - `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md` — update the source-admission summary and `## Ordered route` sequence after the route-local record closes.
  - `handoffs/2026-09-14-roadmap-aidlc-integration-delivery.md` — record the route-local policy as delivered with the plan, audit, and review evidence while retaining #367 as the successor decision.
  - `tests/test_roadmap_format.py` — add a focused guide and backlog drift guard for the delivered policies.

## Implementation

- **Use route-local wording.** Document the current matching-baseline path as unchanged, then document changed and legacy states beside the command that owns them. Do not create a generic non-stage admission policy section.

- **Keep analysis creation and inspection distinct.** In `README.md`, `RUNBOOK.md`, `CAPABILITIES.md`, `docs/ARCHITECTURE.md`, `docs/ROADMAP_WALKTHROUGH.md`, and `integrations/claude/SKILL.md`, describe `--analyze-escalation` as a redacted status-`1` refusal with no immutable analysis publication for changed and legacy briefs. Describe `--view impact-analyses` separately: it reports `changed-brief` or `legacy-brief`, returns `0`, exposes no route or workflow, and remains log-free.

- **Use the supported creation commands everywhere.** Remove `--impact-analysis` and `--structural-revision` from the route-local closure and the edited operator guidance. Use `--analyze-escalation` for analysis creation and `--rewrite-structural` for structural rewrite, including durable run provenance; keep `--view impact-analyses` as the separate inspection command.

- **Preserve structural ordering.** In the structural-rewrite sections of `README.md`, `RUNBOOK.md`, `CLAUDE.md`, `CAPABILITIES.md`, `docs/ARCHITECTURE.md`, `docs/CODEX_CLI_CONTRACT.md`, `docs/ROADMAP_WALKTHROUGH.md`, and `integrations/claude/SKILL.md`, state that evaluator admission and guarded recovery keep their existing place before the route-local brief refusal. A changed or legacy brief must produce the landed redacted status-`1` result without artifact, baseline, or seed publication. Do not imply that the evaluator receives brief contents or that the route bypasses its existing evaluator-availability check.

- **Document immutable-root enrollment independently.** In the operator guides that describe Roadmap lifecycle actions, state that `--enroll-version` returns a redacted status-`1` changed-brief or legacy-brief refusal and makes no immutable version or accepted-head claim. Keep its backend-free and exclusive-command properties intact.

- **Keep stage-run recovery separate.** State that same-path `--from-existing` baseline acceptance and stage-run lifecycle events belong only to `plan_tool/roadmap.py:_run_roadmap`. The non-stage guides must not present either as a way to continue analysis, structural rewrite, or root enrollment.

- **Keep digest and disclosure language exact.** Refer to `brief_digest` only as the accepted decoded UTF-8 text digest. Do not equate it with the raw `source.json` digest or immutable stored-brief bytes, and do not add brief text, absolute paths, receipt contents, or new diagnostics to guide examples.

- **Use the existing guide roles.** Keep `docs/ARCHITECTURE.md` focused on ownership boundaries, `CAPABILITIES.md` focused on durable behavior, `docs/ROADMAP_WALKTHROUGH.md` and `RUNBOOK.md` focused on operator choices, and `docs/CODEX_CLI_CONTRACT.md` focused on the evaluator profile. One way to avoid repeated schema prose is to link route-detail readers to `ROADMAP_FORMAT.md`.

- **Close the route-local record without leaving an open premise.** Replace its open `BACKLOG.md` decision record with a closed summary of the three delivered policies and their tests. Update `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md` so its early source-admission summary and ordered route no longer describe that record as pending, while #367 remains the next distinct operator-intent decision. Update `handoffs/2026-09-14-roadmap-aidlc-integration-delivery.md` at the same closeout point to record the policy as delivered, link its plan, final audit, and review evidence, and retain #367 as the next successor decision.

- **Guard the guide family as one contract.** Extend `tests/test_roadmap_format.py` with a data-driven inventory of the affected public guides. Assert the landed vocabulary, route-specific status behavior, no-write boundaries, and no-rebind rule rather than checking only one document.

## Tests

- `test_non_stage_brief_drift_guidance_sweep_matches_landed_contract` — asserts every named operator guide states the landed changed and legacy policy for its relevant non-stage route.

- `test_non_stage_brief_drift_guidance_keeps_analysis_creation_and_view_distinct` — asserts analysis creation refuses with no publication while impact inspection returns a redacted, log-free no-route status.

- `test_non_stage_brief_drift_structural_guidance_preserves_evaluator_first_ordering` — asserts structural guides retain evaluator admission and guarded recovery before the redacted brief refusal.

- `test_non_stage_brief_drift_guidance_does_not_offer_stage_rebind_to_non_stage_routes` — asserts the guides keep same-path baseline acceptance and stage lifecycle wording out of analysis, structural rewrite, and root enrollment recovery.

- `test_non_stage_brief_drift_backlog_retirement_keeps_367_separate` — asserts the route-local brief-drift record is closed in `BACKLOG.md` and `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md`, while #367 remains the separate next decision.

- `test_non_stage_brief_drift_handoff_records_delivery_and_367_successor` — asserts the delivery handoff records the route-local policy with its evidence and retains #367 as the separate successor decision.

- `test_non_stage_brief_drift_guidance_uses_supported_creation_commands` — asserts the edited guidance and route-local closure use `--analyze-escalation` and `--rewrite-structural`, never `--impact-analysis` or `--structural-revision`.

### Verification (non-code step)

The plan’s test-authoring gate does not apply because this step has `non-code` change type. Use these checks instead:

1. Run `uv run pytest tests/test_roadmap_format.py -q`.

2. Run `uv run pytest tests/ -q -n auto`.

3. Search the edited guide set and delivery handoff for `changed-brief`, `legacy-brief`, `--analyze-escalation`, `--impact-analysis`, `--view impact-analyses`, `--rewrite-structural`, `--structural-revision`, and `--enroll-version`; review each match for the route-local policy and confirm unsupported creation spellings are absent.

4. Review the diff to confirm only the declared documentation and test paths changed, then run `git diff --check`.

5. Open each edited local Markdown link and confirm it resolves to its intended contract section.

## Acceptance criteria

- Every edited guide describes a matching recorded decoded-text baseline as retaining the route’s existing behavior.

- `--analyze-escalation`, `--rewrite-structural`, and `--enroll-version` guidance describes changed and legacy brief outcomes as redacted status-`1` refusals with no persisted claim from that route.

- `--view impact-analyses` guidance describes `changed-brief` and `legacy-brief` as successful, log-free no-route states that omit route and workflow fields.

- No edited guide presents same-path `--from-existing` baseline acceptance or stage-run lifecycle events as available to a non-stage route.

- The edited guide text preserves the decoded-text meaning of `brief_digest` and does not disclose sensitive source or evidence content.

- `BACKLOG.md` records the route-local policy as closed, `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md` retains #367 as separate future work, and the delivery handoff records the policy with audit and review evidence.

- Edited guidance, the route-local closure, and durable provenance use `--analyze-escalation` and `--rewrite-structural` as the sole supported creation commands.

- `tests/test_roadmap_format.py` and the full test suite pass.

## References

- [BACKLOG.md closed route-local brief-drift record](../../../../../BACKLOG.md) — Read the route-specific policy scope that this step closes.

- [Roadmap delivery handoff](../../../../../handoffs/2026-09-14-roadmap-aidlc-integration-delivery.md) — Read the delivery order and scope fence for the three route policies.

- [plan_tool/roadmap_impact_snapshot.py](../../../../../plan_tool/roadmap_impact_snapshot.py) — Read the recorded-source capture and final-recheck classification shared by the routes.

- `plan_tool/roadmap_impact_run.py` (source at the plan’s revision) — Read impact-analysis creation and inspection outcomes.

- `plan_tool/roadmap_structural_revision.py` (source at the plan’s revision) — Read structural preflight ownership and snapshot binding.

- [plan_tool/roadmap.py](../../../../../plan_tool/roadmap.py) — Read immutable-root enrollment and stage-run admission boundaries.

- [ROADMAP_FORMAT.md](../../../../../ROADMAP_FORMAT.md) — Read source identity, impact analysis, and structural rewrite contracts.

- [DATA_CONTRACT.md](../../../../../DATA_CONTRACT.md) — Read the existing redacted lifecycle vocabulary and result fields.

## Applicable guardrails

- **The plan’s “## Step intent”:** Limit this step to consistent public vocabulary and route-local record retirement after steps 2 through 5 land. Do not change route behavior.

- **The plan’s “## Out of scope”:** Do not add a generic source-admission system, non-stage baseline acceptance, stage-run changes, prompts, stages, or broader rewrite authority through documentation wording.

- **The plan’s “### Contracts and constraints,” digest meaning:** Keep every guide’s baseline description tied to decoded UTF-8 text and separate from other digest types.

- **The plan’s “### Contracts and constraints,” capture and recheck rule:** Describe each route’s landed currentness check without weakening its writer-window requirement.

- **The plan’s “### Contracts and constraints,” disclosure boundary:** Keep operator output descriptions within the existing redacted contracts.

- **The plan’s “### Contracts and constraints,” hand-written-brief compatibility rule:** Do not claim a new transition or refusal outside the selected route policies.

## Deferred

- `ROADMAP_FORMAT.md`, `DATA_CONTRACT.md`, and `docs/cli/roadmap.md` contract changes — steps 2 through 5 own those route-specific source, lifecycle, and parser-help updates; this step only aligns the remaining operator guides.

- `BACKLOG.md` #367 stage-run operator-intent decision — it remains separate from non-stage documentation and route policy.
