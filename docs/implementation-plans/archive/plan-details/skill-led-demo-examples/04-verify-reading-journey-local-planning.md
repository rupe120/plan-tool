> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Verify the reading journey and local rehearsal, then reconcile demo status

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Verify the learning journey delivered by steps 1–3 and rehearse the dark-mode planning route through local Jira export in an isolated consuming repository. Record observed results and verification limits in `docs/evidence/skill-led-demo-examples-verification.md`. Update `docs/demos/README.md` and `handoffs/2026-10-21-demo-refresh.md` from that evidence, keeping documentation readiness, live verification and publication status distinct. Completion requires either recorded live results or a named external blocker with an explicit needs-verification status.

## Table of Contents

- [Summary](#summary) — Deliverable and observable result.
- [Table of Contents](#table-of-contents) — Section navigation.
- [Why](#why) — Where current preparation status needs reconciliation.
- [Input](#input) — Dependency outputs and evidence limits.
- [Files (creates vs edits)](#files-creates-vs-edits) — The bounded documentation footprint.
- [Implementation](#implementation) — Reading checks, rehearsal and status updates.
- [Tests](#tests) — Reviewer-run verification for this non-code step.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Existing procedural and artifact owners.
- [Applicable guardrails](#applicable-guardrails) — Boundaries on verification and reporting.
- [Deferred](#deferred) — Work outside this verification step.

## Why

`docs/demos/README.md` labels the planning refresh as deferred, while `handoffs/2026-10-21-demo-refresh.md` combines pickup instructions, local fixture provenance and outstanding live verification. Its “Outcome and scope for the new plan” also proposes assessing a task-list scenario, whereas the accepted plan retains dark mode. After steps 1–3, these entry points need current evidence and next actions so readers do not confuse updated guides or prepared fixtures with a verified live workflow or approved publication.

## Input

- **Step 1:** Read the resulting dark-mode walkthrough, reading samples and minimal fixture. Their authored examples establish teaching material, not captured model results.
- **Step 2:** Read the resulting TTRPG walkthrough and check its narrative against the roadmap contracts. This step consumes that narrative without regenerating the roadmap.
- **Step 3:** Read the resulting first-use, situation, monitoring and recovery examples as one learning journey.
- **Preparation provenance:** Use `handoffs/2026-10-21-demo-refresh.md:Local candidate` and “Verification and presentation boundary” only for the snapshots they identify. Check whether referenced scratch material exists; absence does not invalidate the maintained guides.
- **Export contract:** Use `JIRA_FORMAT.md:Output pair`, “Paired developer handoff” and “Lints” to assess actual local outputs. Successful lint does not establish qualified audit convergence or model reliability.

## Files (creates vs edits)

**New files:**

- `docs/evidence/skill-led-demo-examples-verification.md` — Record the reviewed snapshot, reading checks, rehearsal results, evidence locations, blockers and remaining verification.

**Existing files (edits only):**

- `docs/demos/README.md` — Update discovery links and preparation status to match observed results.
- `handoffs/2026-10-21-demo-refresh.md` — Replace superseded pickup instructions with current status and next actions; preserve necessary dated preparation provenance and publication ownership.

## Implementation

- **User review checkpoints.** Verify the reading journey and local rehearsal show user review of the actual seed, bare plan and details before their next consuming stages, or identify the explicit prior delegation authorizing continuation. Record this evidence separately from model audit results. The assistant links each artifact, summarizes changes and asks for corrections or continuation. Wait for the user unless explicit existing delegation covers that transition; do not infer approval from elapsed time. This changes the demo interaction, not tool enforcement.

- **Foundational logic: readiness follows observed evidence.** Use the evidence record as the detailed account and link to it from the index and handoff. Reject a blanket “verified” label based only on fixture checks, command exit codes or documentation review.

- **Review the complete reading journey.** Follow `README.md:Your first plan` through the step 3 guides, `docs/demos/planning-demo.md:Prepare the example` and “Present the workflow,” and step 1’s reading samples. Check that readers encounter a usable request, an artifact to inspect and a clear owner decision at each boundary.

- **Check shared rules without copying them.** Compare monitoring and recovery examples with `integrations/shared/DIRECTIVES.md:Monitor command liveness and recover safely`. Compare both audit stages and separate completion requests with the existing procedural owners. Record discrepancies against the dependency step that owns the affected guide; this step must not silently expand into another guide rewrite.

- **Review the roadmap narrative without a full run.** Check `docs/demos/roadmap-demo.md` around “Phase 2 — the review loop,” “Phase 3 — promote the draft seeds” and “Phases 4–6 — one plan to full depth.” Verify its authority and review boundaries against `ROADMAP_FORMAT.md` and `ROADMAP_FEEDBACK_FORMAT.md`. Label this as contract review, not live TTRPG verification.

- **Rehearse the retained dark-mode route locally.** Use a disposable consuming repository with working tests and one available authenticated backend. Follow the landed walkthrough and existing skill procedures: assistant-authored grounded seed, create, bare-plan audit, detail, detail-grounded audit, then a separately requested local Jira export. Keep generated rehearsal artifacts and audit history outside this product repository’s active plan manifest.

- **Observe completion and report qualification.** Monitor each original command through confirmed exit using existing state surfaces. Read saved reports and record their actual coverage, qualification, convergence outcome and unresolved findings. Do not start an overlapping invocation or treat quiet output as permission to terminate work.

- **Inspect both export companions.** Check the story artifact and paired developer handoff against `JIRA_FORMAT.md:Paired developer handoff`. Use the existing `plan_tool/cli/jira_cmd.py:cmd_jira_lint` route to lint the exported stories without another model call. Record warnings separately from failures and audit outcomes.

- **Retain useful, bounded evidence.** Record date, tested repository revision, tool revision, backend/model, actual commands, completion outcomes, report paths and artifact identities. Include enough report conclusions and provenance to assess the result when disposable paths disappear. Distinguish authored samples, prepared fixtures and captured results; omit credentials and private recovery contents.

- **Handle unavailable runtime honestly.** If authentication or runtime availability prevents the live rehearsal, record the failed prerequisite, completed checks, stages not reached and the action needed to resume. Keep the live route labeled needs verification. An external blocker must not become a successful rehearsal claim.

- **Reconcile current status throughout the handoff.** Review its opening, “Next-session instruction: use the plan-tool skill,” “Outcome and scope for the new plan,” “Skill-driven sequence and verification” and “Work to resume when the demo is needed.” Remove instructions that restart completed work or reopen scenario selection. Retain dated local-candidate facts only where they explain current recovery or publication decisions.

- **Keep discovery and evidence aligned.** Update `docs/demos/README.md:Demonstrations` with links to the reading samples and verification record. State documentation readiness, live rehearsal status and remaining publication work separately. Before renaming headings, check inbound fragment links and update links within this step’s files.

## Tests

This is a `non-code` step. The test-authoring gate in `plan_tool/launcher.py:_step_requires_test_authoring` applies to code changes, so it does not require a new test file here. No matching demo-status test module exists; use reviewer-run checks and existing artifact tests rather than adding wording assertions.

### Verification (non-code step)

1. `reading_journey_exposes_requests_artifacts_and_decisions` — Walk the step 1–3 outputs and record whether seed authoring, both audit stages and separate completion requests remain visible.
2. `monitoring_preserves_original_command_completion` — Compare monitoring and resume examples with the existing procedure; record any observed live monitoring separately from narrative review.
3. `retained_artifacts_pass_existing_contracts` — Parse available plan fixtures with `plan_tool/parser.py:parse_plan`; use `render_plan_text` and `parse_plan_text` for round-trip checks, and check detail artifacts against `DETAIL_FORMAT.md`. Existing coverage lives in `tests/test_parser.py` and `tests/test_detail.py`.
4. `live_rehearsal_records_both_audits_or_external_blocker` — Verify that the evidence names actual stage outcomes, report coverage and qualification, or identifies the blocker and every unverified stage.
5. `local_export_records_story_and_developer_handoff` — Inspect both available outputs and run story lint; record failures and advisories. Existing behavior coverage lives in `tests/test_jira.py`, `tests/test_jira_handoff.py` and `tests/cli/test_jira_cmds.py`.
6. `roadmap_review_does_not_claim_live_regeneration` — Verify that the recorded roadmap check describes contract review and preserves accepted-head, candidate, settlement and materialization boundaries.
7. `status_claims_match_evidence_and_links` — Check local paths and fragments in the three deliverables, then compare every readiness claim with the evidence record.
8. `repository_checks_preserve_existing_behavior` — Run `uv run pytest tests/ -q -n auto` and record the actual result; do not present suite success as live model verification.

## Acceptance criteria

- The step’s deliverables show explicit user review of seeds, plans and details at the correct stage boundaries, including artifact links, change summaries and correction/continuation requests; continuation follows a user response or explicit prior delegation.
- `docs/evidence/skill-led-demo-examples-verification.md` identifies the reviewed snapshot, checks performed, results and verification limits.
- The record covers the learning journey produced by steps 1–3 and identifies any unresolved discrepancies by owning surface.
- The live rehearsal records actual command completion, bare/detail audit coverage and qualification, and paired local export evidence; alternatively, it records a named external blocker and explicit unverified stages.
- Available retained fixtures pass their applicable format checks, and available local story exports have recorded lint results.
- `docs/demos/README.md` and `handoffs/2026-10-21-demo-refresh.md` agree with the evidence and distinguish preparation, live verification and publication.
- The handoff’s active instructions retain dark mode and describe remaining work without restarting completed dependency steps.
- Changed links and fragments point to real targets; the evidence remains understandable without disposable scratch files.
- Repository check results are recorded separately from live rehearsal results.

## References

- [Plan and scope](../../2-skill-led-demo-examples.md) — Read “Testing,” “Acceptance criteria” and the scope fence.
- [Demo preparation handoff](../../../../../handoffs/2026-10-21-demo-refresh.md) — Read preparation provenance and publication ownership.
- [Jira export format](../../../../../JIRA_FORMAT.md) — Check paired outputs, provenance and lint interpretation.
- [Plan format](../../../../../PLAN_FORMAT.md) — Check retained plan fixtures.
- [Detail format](../../../../../DETAIL_FORMAT.md) — Check retained run-grade details.
- [Roadmap format](../../../../../ROADMAP_FORMAT.md) — Check accepted-head artifact authority.
- [Roadmap feedback format](../../../../../ROADMAP_FEEDBACK_FORMAT.md) — Check ledger, candidate and settlement boundaries.
- [Documentation style](../../../../reference/documentation-style.md) — Keep discovery, procedures and evidence in their existing roles.

## Applicable guardrails

- **The plan’s “Scope guardrails,” existing behavior:** Use existing verification and monitoring surfaces; keep implementation changes outside this step.
- **The plan’s “Scope guardrails,” publication boundary:** Report remaining publication work without performing it or exposing private recovery material.
- **The plan’s “Out of scope,” scenario and regeneration limits:** Verify the dependency outputs within the retained scenarios and use contract review for the advanced walkthrough.
- **The plan’s “Scope guardrails,” procedural ownership:** Link existing rules from the evidence and handoff instead of creating another workflow policy.

## Deferred

- Remote demo checkpoint publication — The release workflow retains ownership and separate authorization.
- Full TTRPG regeneration and example implementation execution — Neither is required to verify this authoring journey.
- Changes to shared procedural authority or tool behavior — Verification consumes those contracts unchanged; any required change needs separate intentional work.
