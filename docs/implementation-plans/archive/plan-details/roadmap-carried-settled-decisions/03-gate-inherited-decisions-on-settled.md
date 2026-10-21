> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Gate inherited decisions on settled status, owning-artifact anchors, and confirmed citations against the current recorded source

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Extend `plan_tool/roadmap_gates.py` so inherited decision rows are accepted only when they exactly match a confirmed carried decision from the current recorded source. Update `tests/test_roadmap_gates.py` with focused unit cases for settled status, source citation resolution, owning-artifact placement, same-artifact anchors, and model mutations. Keep Roadmap-derived decision checks unchanged. On green, a gate refusal prevents any carried row that is missing, altered, unconfirmed, duplicated ambiguously, or placed against the wrong artifact from reaching publication.

## Table of Contents

- [Summary](#summary) — The completed gate behavior and affected files.
- [Table of Contents](#table-of-contents) — Quick links to this detail.
- [Why](#why) — Why inherited rows need deterministic source checks.
- [Input](#input) — The upstream source and artifact contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed by this step.
- [Implementation](#implementation) — The gate rules, integration points, and fixed boundaries.
- [Tests](#tests) — Focused gate coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Contracts and scope evidence to consult.
- [Applicable guardrails](#applicable-guardrails) — Scope boundaries that bind this work.
- [Deferred](#deferred) — Routing and lifecycle work owned by later steps.

## Why

`plan_tool/roadmap_gates.py:check_decision_records` currently treats every decision as Roadmap-authored and permits anchors to resolve through any artifact available in `ArtifactEnvelope`. After steps 1 and 2 add source-side carried records and an inherited row form, that behavior would let a model change an approved choice, cite something merely plausible, or place the row beside an upstream anchor. This step adds the deterministic boundary that makes inherited provenance meaningful before the stage writer can publish an artifact.

## Input

- **Step 1 source contract:** Step 1 provides validated carried decisions and confirmed citation targets from the current digest-bound brief block. This step consumes that typed result; it must not parse brief text or reinterpret confirmation rules.
- **Step 2 artifact contract:** Step 2 makes `plan_tool/roadmap_artifacts.py:DecisionRow` visibly inherited through its source citation. This step uses that distinction rather than inferring inherited status from `DecisionStatus`, empty alternatives, or prose.
- **Gate envelope:** `plan_tool/roadmap_gates.py:ArtifactEnvelope` is the shared input for `run_domain_gates`, `run_constraints_gates`, `run_components_gates`, and `run_plans_gates`. Extend it only as needed to carry the already-parsed current source facts into a pure gate call.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_gates.py` — Add inherited-decision validation, any required `ArtifactEnvelope` input, violation kinds, and ordered registration in the four stage gate sets.
  - `tests/test_roadmap_gates.py` — Add direct dataclass-based gate tests and retain the existing conforming parser seam coverage.

## Implementation

- **Make carried provenance a closed match.** Add a pure inherited-decision check near `check_decision_records` that compares each inherited `DecisionRow` against the carried-decision records supplied from step 1. A valid row must match one unambiguous current-source record on its identity, selected option, source citation, required settled status, owning artifact, anchor, and any optional source-provided rationale or rejected alternatives. Do not accept a citation because it has the right shape or because similar source text exists.

- **Require one owning artifact and a local anchor.** The carried record’s owning artifact must equal `ArtifactEnvelope.filename_under_check`, and the inherited row’s anchor must name a live row in that same artifact. Keep `check_decision_records` unchanged for Roadmap-derived decisions, which may retain its existing cross-artifact anchor behavior. The inherited rule is deliberately narrower because its approved source record assigns one publication location.

- **Reject omissions, extras, and mutations.** For the artifact being checked, require every carried decision owned by that artifact to appear exactly once as its inherited row. Refuse an inherited row with no source record, more than one matching source record, a changed id, selected option, anchor, citation, owner, or status, and refuse an inherited row that does not remain settled. Give each failure a distinct violation kind when the correction differs.

- **Compare supplied evidence exactly.** Continue the existing `check_settled_decisions` rule that does not semantically compare Roadmap-authored prose across revisions. For inherited rows, source-provided rationale and rejected alternatives are approval facts: require exact equality with the current block, including absence, rather than judging paraphrases. Never require deliberation absent from the block.

- **Keep gate calls uniform and ordered.** Register the new check in `DOMAIN_GATES`, `CONSTRAINTS_GATES`, `COMPONENTS_GATES`, and `PLANS_GATES` so the existing `run_*_gates` functions retain one `ArtifactEnvelope` call shape and deterministic violation ordering. Preserve the first-run behavior when no carried-decision input exists: legacy artifacts and handwritten-brief runs must receive the same decision findings they receive now.

- **Keep the module deterministic.** `plan_tool/roadmap_gates.py:Violation` messages feed retry text, so each message must name the inherited decision id, relevant artifact filename, and citation or anchor involved. Do not add filesystem reads, source loading, prompt work, or an invoker seam to this gate module.

## Tests

- `test_inherited_decision_owned_by_current_artifact_with_confirmed_citation_passes` — `tests/test_roadmap_gates.py` proves a matching settled inherited row clears the new gate.
- `test_roadmap_derived_decision_keeps_existing_deliberation_requirements` — proves `check_decision_records` still requires rationale and rejected alternatives only for Roadmap-derived rows.
- `test_inherited_decision_requires_settled_status` — proves a pending inherited row is rejected even though pending Roadmap-derived decisions remain allowed.
- `test_inherited_decision_requires_its_owning_artifact` — proves a carried row cannot be published in a different stage artifact.
- `test_inherited_decision_anchor_must_exist_in_its_owning_artifact` — proves an inherited row cannot use an otherwise valid upstream anchor.
- `test_every_carried_decision_owned_by_the_artifact_must_appear_once` — proves a missing required inherited row and a duplicate emitted row both refuse.
- `test_inherited_decision_with_missing_ambiguous_or_unconfirmed_citation_refuses` — proves each current-source citation failure is reported without parser changes.
- `test_inherited_decision_mutating_approved_fields_refuses` — proves changed identity, selected option, anchor, source citation, owner, or status cannot pass.
- `test_inherited_deliberation_must_equal_source_or_be_absent` — proves source-provided alternatives and rationale are retained exactly and model-invented alternatives refuse.
- `test_rebind_current_source_rejects_existing_inherited_row_with_stale_citation` — proves gates judge the supplied current source rather than accepting an older artifact citation.
- `test_legacy_envelope_without_carried_decisions_keeps_existing_gate_results` — proves no-source runs retain current behavior.
- `test_inherited_decision_gate_runs_in_every_stage_gate_set` — proves all four `run_*_gates` paths apply the same inherited-decision rule.

Every listed test must be green before this step is complete.

## Acceptance criteria

- An inherited decision passes only when one current recorded-source carried record confirms its settled status, selected option, citation, owner, and local anchor.
- An inherited decision with a missing, ambiguous, unresolved, or unconfirmed citation produces a blocking `Violation` that names the decision id and relevant source reference.
- An inherited decision placed outside its owning artifact, or anchored to a row outside that artifact, produces a blocking `Violation`.
- A carried decision owned by the artifact under check cannot be omitted or emitted more than once.
- A model mutation of an inherited decision’s structured approval facts produces a blocking `Violation`.
- Roadmap-derived decisions retain `check_decision_records` requirements for rejected alternatives, rationale, and resolvable anchors.
- `run_domain_gates`, `run_constraints_gates`, `run_components_gates`, and `run_plans_gates` retain one shared `ArtifactEnvelope` call shape and deterministic violation order.
- `tests/test_roadmap_gates.py` passes.

## References

- [Roadmap Carried Settled Decisions plan](../../2-roadmap-carried-settled-decisions.md) — Read the architecture for single-artifact placement, current-source revalidation, and compatibility rules.
- [Roadmap intake comparison](../../../evidence/roadmap-aidlc-intake-comparison-20260916.md) — Read the selected scope and the reason inherited choices need citations.
- [Roadmap integration delivery handoff](../../../handoffs/2026-09-14-roadmap-aidlc-integration-delivery.md) — Read the approved delivery boundary and citation expectations.
- [ROADMAP_FORMAT.md](../../../../ROADMAP_FORMAT.md) — Read the existing artifact and decision-row contract before extending gate behavior.
- [DATA_CONTRACT.md](../../../../DATA_CONTRACT.md) — Read the current compatibility and validation contract.

## Applicable guardrails

- **The plan’s “## Scope guardrails”, selected-row authority** — Limit this gate to inherited decision rows and their proof; it must not grant source input authority over other Roadmap rows or writers.
- **The plan’s “## Scope guardrails”, rebind boundary** — Validate against the current accepted source when a later artifact is gated, but do not make gate work mutate artifacts, feedback, seeds, or the rebind baseline.
- **The plan’s “## Scope guardrails”, supplementary grounding boundary** — Keep the envelope input limited to the one recorded source’s closed carried records; do not add multi-source identity or stage-wide grounding.
- **The plan’s “## Out of scope”, input parsing boundary** — Do not parse free-form logs, source directories, positional prose, or connector-specific formats in these files.
- **The plan’s “## Out of scope”, deliberation boundary** — Do not require inherited rows to manufacture rationale or rejected alternatives.

## Deferred

- `plan_tool/roadmap.py` source loading, stage routing, and publication sequencing — Step 4 passes the current brief facts into the gate envelope, sends each carried row only to its owner, and applies refusal before atomic publication.
- Shared revision-frame or multi-source provenance work — The plan’s deferred #383 scope remains outside this focused gate change.
