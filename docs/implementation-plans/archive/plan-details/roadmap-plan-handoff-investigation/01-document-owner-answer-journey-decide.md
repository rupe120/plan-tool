> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Document the owner-answer journey and shared consumer inputs

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Create `docs/explanations/roadmap-plan-handoff.md` as the reviewed design record for the roadmap-to-plan handoff investigation. The record traces one selected Integration owner-answer journey from an accepted roadmap outcome through evidence, responsible layers, and a bounded next increment. Its key decision is to separate immutable accepted-roadmap authority from observed implementation and an unresolved provider question and separate owner-owned decisions. On green, the record names the smallest shared input each of `create`, `detail`, and `completeness-audit` needs and gives each follow-on a build, use-existing, or no-action disposition.

## Table of Contents

- [Summary](#summary) — States the document’s result and central decision.
- [Table of Contents](#table-of-contents) — Routes readers through the design record.
- [Why](#why) — Explains the handoff gap this investigation resolves.
- [Input](#input) — Names the authoritative roadmap and existing prompt inputs.
- [Files (creates vs edits)](#files-creates-vs-edits) — Defines this documentation-only footprint.
- [Implementation](#implementation) — Describes the journey, ownership map, and consumer decisions.
- [Tests](#tests) — Lists non-code verification for the new record.
- [Acceptance criteria](#acceptance-criteria) — Defines reviewer-checkable completion conditions.
- [References](#references) — Links the evidence and contracts behind the record.
- [Applicable guardrails](#applicable-guardrails) — Keeps the investigation inside its approved boundary.
- [Deferred](#deferred) — Routes implementation and adjacent ownership to their existing work.

## Why

`BACKLOG.md` #492 identifies that roadmap-derived plans can lack the shared evidence needed to turn an accepted outcome into bounded work without confusing approved intent, current code, provider evidence, and unresolved owner choices. Existing prompt inputs already supply project context, plan intent, scope contracts, and detail bundles, but their sufficiency for this journey is not decided. A focused design record lets later work use those inputs unchanged where they already meet the need and limits any new delivery surface to a demonstrated gap.

## Input

- **Accepted roadmap authority:** Read accepted roadmap content only through `plan_tool/roadmap_versions.py:load_accepted_version` and the immutable accepted-head contract in `ROADMAP_FORMAT.md`. The record must distinguish this authority from candidate material, source-checkout observations, and proposals.
- **Current authoring context:** Inspect `plan_tool/create.py:_project_context_block`, `plan_tool/detail.py:render_detail_prompt`, and `plan_tool/project_profile.py:project_profile_context` to identify project context already supplied to authoring.
- **Current audit context:** Inspect `plan_tool/review.py:render_plan_audit_prompt`, `plan_tool/review.py:_format_audit_detail_bundle`, and `plan_tool/review.py:audit_detail_bundle_status` to identify the plan, detail, scope, and project-context inputs already supplied to completeness auditing.
- **Read-only status baseline:** Use `plan_tool/cli/inspect.py:cmd_status` and `_print_status` only to assess whether #494 needs a separate status projection; do not treat the current output as a complete readiness contract.
- **Evidence limit:** Treat `docs/evidence/integration-roadmap-to-plan-handoff.md` as bounded investigation evidence. It supports the journey selection and questions, not claims that a new input improves plan quality or execution readiness.

## Files (creates vs edits)

- **New files:**
  - `docs/explanations/roadmap-plan-handoff.md` — Record the selected owner-answer journey, authority boundaries, evidence map, consumer-input decisions, a remaining provider question, and any separate owner decisions.

- **Existing files (edits only):**
  - None.

## Implementation

- **Document one bounded journey.** Make `docs/explanations/roadmap-plan-handoff.md` start with the reader’s task: deciding whether a roadmap-derived plan needs information beyond the inputs `create`, `detail`, and `completeness-audit` already receive. Trace one representative path from an accepted roadmap outcome to its responsible layer, the evidence that supports the next increment, and any provider evidence or separate owner decision still needed for that increment.

- **Keep authority separate.** State that `plan_tool/roadmap_versions.py:load_accepted_version` selects the immutable accepted version, as required by `ROADMAP_FORMAT.md`. Mark observed Integration implementation, provider evidence, consumer fixtures, and proposals as evidence with limits rather than as replacements for accepted roadmap intent.

- **Use a compact ownership-and-evidence map.** One way is a table with the outcome or obligation, owning layer or owner, available evidence, authority level, and the next unanswered question. Include pointers to the fuller Integration outcome coverage named by `docs/evidence/integration-roadmap-to-plan-handoff.md`; do not copy it into this record or turn the document into a general inventory.

- **Compare existing consumer inputs before proposing delivery.** For each consumer, record the current input path and a disposition:
  - `create` — assess `plan_tool/create.py:_project_context_block` and its authoring prompt path.
  - `detail` — assess `plan_tool/detail.py:render_detail_prompt` and its existing project-context, plan-reference, and scope-fence blocks.
  - `completeness-audit` — assess `plan_tool/review.py:render_plan_audit_prompt` and its project context, plan body, detail-bundle, intent, and scope-contract inputs.
  
  Use `use-existing` when those inputs already carry the selected evidence, `build` only when a specific missing delivery is demonstrated, and `no-action` when the consumer does not need shared input for this journey. Do not imply that all three consumers need new support.

- **Name the compatibility decision.** State how projects without selected shared context remain on their existing prompt and status behavior. The record may recommend a later compatibility rule, but it must not introduce a schema, persistence format, fallback source, or automatic source substitution.

- **Record a remaining provider question separately from owner decisions.** Include at least one provider capability or behavior question unresolved at the inspected revision, with its evidence limits and responsible provider or investigation owner. Do not substitute an owner product decision or a question already answered by the probe. Record any separate unresolved product decisions with their owner; cite evidence rather than choosing an answer. These may remain open only when they do not prevent the required tool-side conclusions.

- **Produce the initial follow-on dispositions consumed by step 2.** Separately from the three consumer decisions, record an evidenced `build`, `use-existing` or `no-action` recommendation for #493, #462 and #494 under the plan's “Decision targets” contract. #493 follows demonstrated consumer delivery needs; #494 requires a distinct status-information need. For #462, record applicability and its independent gate status: an unmet gate permits only a conditional build recommendation, does not change #462 eligibility and does not hold #492 open by itself. Missing evidence needed for the recommendation itself keeps #492 open. Do not implement or close these follow-ons.

- **Keep adjacent work outside this document’s decision scope.** Mention #493 only as the potential delivery follow-on, #462 as the separate cross-plan advisory route, #494 as the separate status need, #490 as finding-disposition ownership, #485 as deliberate-roadmap-departure ownership, #262 as bare-plan audit guidance, and #403 as installation-readiness work. The record must not merge their contracts into “shared context.”

- **Use explanation-document structure.** Follow `docs/reference/documentation-style.md`: put the normal journey before exceptions, use tables for ownership mappings and ordered lists for the journey, and link to deeper contracts instead of repeating their full procedures.

## Tests

- `docs/explanations/roadmap-plan-handoff.md` — Verify every cited `plan_tool/` symbol exists at HEAD and each repository-relative path is complete.
- `docs/explanations/roadmap-plan-handoff.md` — Verify the selected journey names an accepted outcome, responsible layer, available evidence, evidence limit, a remaining provider question, and any separate unresolved owner decision.
- `docs/explanations/roadmap-plan-handoff.md` — Verify each of `create`, `detail`, and `completeness-audit` has one explicit need decision, and #493, #462 and #494 each have a separate evidenced disposition; verify #462’s conditional recommendation and independent gate status where applicable.
- `docs/explanations/roadmap-plan-handoff.md` — Verify the record distinguishes accepted-roadmap authority from observed code and proposal evidence.
- `docs/explanations/roadmap-plan-handoff.md` — Verify no new command, schema, persisted version, execution gate, or Integration-side change is presented as part of this step.

### Verification (non-code step)

1. Confirm the document follows the scanning structure in `docs/reference/documentation-style.md`.
2. Confirm `plan_tool/roadmap_versions.py:load_accepted_version` remains the only accepted-content selector cited for roadmap authority.
3. Confirm the consumer descriptions match the current prompt-rendering symbols and do not claim an input is absent without evidence.
4. Confirm local Markdown links and heading anchors resolve.
5. Confirm `git diff --check` passes for the documentation change.

## Acceptance criteria

- `docs/explanations/roadmap-plan-handoff.md` exists and identifies one selected owner-answer journey from accepted outcome to bounded proposed increment.
- The record distinguishes accepted roadmap content, observed implementation, provider evidence, consumer fixtures, and unresolved owner questions.
- The record cites `plan_tool/roadmap_versions.py:load_accepted_version` as the accepted-roadmap authority.
- The record identifies the current shared-input path for `create`, `detail`, and `completeness-audit`, with one explicit build, use-existing, or no-action disposition per consumer.
- The record names an unresolved provider question and any separate unresolved owner decisions and does not answer it by inference.
- The record points to fuller outcome coverage without duplicating it as a second roadmap or unrelated inventory.
- The record supplies initial, evidenced dispositions for #493, #462 and #494 for step 2 to review, separately from consumer decisions, with #462 applicability and gate status recorded under the plan contract. #490, #485, #262 and #403 remain consulted ownership boundaries only.
- The change modifies only `docs/explanations/roadmap-plan-handoff.md`.

## References

- [BACKLOG.md #492 — Defines the investigation outcome, scope fence, stage arc, and follow-on ownership.](../../../../BACKLOG.md)
- [Integration evidence for the roadmap to plan handoff — Supplies the bounded observations and their stated limits.](../../../evidence/integration-roadmap-to-plan-handoff.md)
- [Roadmap format — Defines immutable accepted-head authority and accepted-version readers.](../../../../ROADMAP_FORMAT.md)
- [Developer documentation style — Defines the scanning structure for this explanation record.](../../../reference/documentation-style.md)
- [plan_tool/create.py — Inspect `_project_context_block` and the existing create-side context path.](../../../../plan_tool/create.py)
- [plan_tool/detail.py — Inspect `render_detail_prompt` and its current authoring inputs.](../../../../plan_tool/detail.py)
- [plan_tool/review.py — Inspect `render_plan_audit_prompt` and detail-bundle grounding.](../../../../plan_tool/review.py)
- [plan_tool/cli/inspect.py — Inspect `cmd_status` and `_print_status` before proposing any status follow-on.](../../../../plan_tool/cli/inspect.py)

## Applicable guardrails

- **The plan’s “## Scope guardrails”, documentation-only investigation:** Create only the design record; do not change production code, CLI behavior, schemas, persistence, validation, gates, or exit behavior.
- **The plan’s “## Out of scope”, implementation follow-ons:** Describe possible follow-ons only through their existing backlog owners. Do not implement or design their detailed contracts here.
- **The plan’s “## Plan intent”, observable record:** Make the reviewed record and its named consumer dispositions the completion result. Do not claim that the journey proves a good decomposition.
- **The plan’s “## Step intent”, missing evidence:** Leave the step incomplete if the selected journey lacks required authority or evidence; do not fill the gap with inferred product answers.
- **The plan’s “## Out of scope”, Integration changes and probes:** Use the checked-in evidence record only. Do not write to Integration or run a new live probe.

## Deferred

- Shared-context delivery for authoring and auditing (#493) — Depends on this record demonstrating a missing input and selecting its authority and compatibility treatment.
- Cross-plan accepted-roadmap conflict reporting (#462) — Remains a separate saved advisory route.
- Status projection for unresolved prerequisites (#494) — Requires a distinct demonstrated status need and selected source contract.
- Audit-finding dispositions (#490) — Remains owned by the convergence-evidence route.
- Deliberate departures from accepted roadmap rows (#485) — Requires its separate authority decision.
- Bare-plan detail-readiness advice (#262) — Remains an audit-stage recommendation, not shared-context delivery.
- Installation and repository readiness inspection (#403) — Remains separate from the selected application journey.
