> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Extend DecisionRow parsing and rendering to distinguish cited inherited decisions from Roadmap-derived decisions

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Extend `plan_tool/roadmap_artifacts.py:DecisionRow` and its parser/renderer helpers so a decision row can preserve an inherited source citation separately from a Roadmap-derived decision. Keep the existing fields and behavior for Roadmap-derived rows, including their rationale and rejected alternatives. Update `tests/test_roadmap_artifacts.py` with focused parse, render, compatibility, and round-trip coverage. On green, an artifact retains the distinction needed by later citation gates without changing legacy artifact behavior.

## Table of Contents

- [Summary](#summary) — The step outcome and main design choice.
- [Table of Contents](#table-of-contents) — Quick links to this detail.
- [Why](#why) — Why decision rows need an explicit inherited form.
- [Input](#input) — The source and artifact contracts this row shape consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed by this step.
- [Implementation](#implementation) — Decision-row representation, parsing, and rendering rules.
- [Tests](#tests) — Focused artifact-contract coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Contracts and scope evidence to consult.
- [Applicable guardrails](#applicable-guardrails) — Scope boundaries that bind this work.
- [Deferred](#deferred) — Later gate and stage-routing work.

## Why

`plan_tool/roadmap_artifacts.py:DecisionRow` currently represents every decision as if Roadmap deliberated it: it always reads and writes a rationale plus rejected alternatives, with no citation that identifies an approved upstream choice. That makes an inherited choice indistinguishable from a Roadmap-authored one and encourages generated deliberation where the source already settled the decision.

## Input

- **Artifact row contract:** `plan_tool/roadmap_artifacts.py:DecisionRow`, `_parse_decision_rows`, and `_decision_mapping` define the shared `decisions` row used by `DomainArtifact`, `ConstraintsArtifact`, `ComponentsArtifact`, and `PlansArtifact`.
- **Source-side input:** Step 1 supplies validated carried-decision records and confirmed citation targets. This step defines only how an artifact row retains inherited provenance; it must not duplicate source-record parsing or confirmation checks.
- **Existing compatibility:** `plan_tool/roadmap_artifacts.py:parse_domain_artifact`, `parse_constraints_artifact`, `parse_components_artifact`, and `parse_plans_artifact` accept existing artifact text, while their matching `render_*_artifact` functions preserve typed artifacts through a parse/render round trip.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_artifacts.py` — Extend `DecisionRow`, `_parse_decision_rows`, and `_decision_mapping` with the closed inherited-decision representation while preserving existing artifact parsers and renderers.
  - `tests/test_roadmap_artifacts.py` — Add focused tests for inherited rows, Roadmap-derived rows, renderer omission rules, compatibility, and round trips.

## Implementation

- **Represent provenance explicitly.** Give `DecisionRow` a typed optional source-citation value that marks a row as inherited when present. Use the plan’s `source` citation concept in the artifact wire shape; do not infer inheritance from `status`, an empty alternatives list, or prose content.

- **Keep the two row meanings separate.** A Roadmap-derived row retains the existing rationale and rejected-alternatives contract. An inherited row retains its citation without generated deliberation. It may carry optional rationale or alternatives supplied by the approved source; absence stays absent, and unselected question-menu options never become alternatives.

- **Keep parsing structural.** Update `_parse_decision_rows` to recognize both valid forms and retain the row’s distinction in the typed result. Do not make this parser decide whether a citation is confirmed, unique, current, associated with the row’s owning artifact, or valid after a rebind; `plan_tool/roadmap_gates.py` owns those cross-record checks in step 3.

- **Render the same meaning that parsed.** Update `_decision_mapping` so an inherited row emits its source citation and only fields its representation permits. A Roadmap-derived row must not render a null or empty provenance key. The existing `render_domain_artifact`, `render_constraints_artifact`, `render_components_artifact`, and `render_plans_artifact` paths must continue to share this one mapping helper.

- **Preserve existing callers.** `plan_tool/roadmap_candidate.py:_parse_stage_row`, `plan_tool/roadmap_revision.py:DecisionRowPayload.to_row`, and roadmap test builders construct Roadmap-derived decisions. Keep those constructors compatible. The bounded feedback decoder is `plan_tool/roadmap_revision.py:_decode_row_payload`; step 4 owns its inherited-row policy and tests.

- **Keep collection behavior unchanged.** Continue returning ordered tuples from `_parse_decision_rows`; do not deduplicate, sort, or resolve row ids while adding provenance. Duplicate detection, anchor checks, and source-citation checks remain later gate work.

## Tests

### Tests for this step

- `test_roadmap_derived_decision_requires_existing_deliberation_fields` — `tests/test_roadmap_artifacts.py` proves a row without a source citation retains the current rationale and rejected-alternatives parsing contract.
- `test_inherited_decision_parses_with_a_source_citation` — `tests/test_roadmap_artifacts.py` proves an inherited row retains its citation and does not require generated deliberation fields.
- `test_inherited_decision_renders_source_without_null_or_generated_fields` — `tests/test_roadmap_artifacts.py` proves the renderer writes inherited provenance and omits fields the inherited form does not carry.
- `test_roadmap_derived_decision_renders_without_source_key` — `tests/test_roadmap_artifacts.py` proves legacy and newly authored Roadmap decisions do not gain an empty provenance field.
- `test_decision_rows_round_trip_for_inherited_and_roadmap_derived_forms` — `tests/test_roadmap_artifacts.py` proves parse/render equality preserves both meanings.
- `test_legacy_decision_artifact_parses_and_renders_unchanged` — `tests/test_roadmap_artifacts.py` proves existing fixtures without inherited provenance remain compatible.
- `test_inherited_decision_with_unresolved_or_unconfirmed_source_still_parses` — `tests/test_roadmap_artifacts.py` proves citation resolution and confirmation remain gate-owned, not parser-owned.

Every listed test must be green before this step is complete.

## Acceptance criteria

- `DecisionRow` represents whether a decision is inherited through an explicit optional source citation.
- A Roadmap-derived decision retains the current rationale and rejected-alternatives behavior.
- An inherited decision retains its source citation without requiring Roadmap-generated deliberation content.
- All four artifact parsers and renderers preserve inherited and Roadmap-derived decision meanings through parse/render round trips.
- Rendered Roadmap-derived rows omit the source key rather than emitting a null or empty value.
- Existing decision artifacts without a source citation remain parseable and render compatibly.
- `tests/test_roadmap_artifacts.py` passes.

## References

- [Roadmap carried settled decisions plan](docs/implementation-plans/2-roadmap-carried-settled-decisions.md) — Read the architecture’s inherited-row, citation, and compatibility rules.
- [Roadmap format](ROADMAP_FORMAT.md) — Read the current decision-row schema and parser/renderer contract.
- [Data contract](DATA_CONTRACT.md) — Preserve existing artifact and source-admission contract boundaries.
- [Roadmap intake comparison](docs/evidence/roadmap-aidlc-intake-comparison-20260916.md) — Read the provenance gap this narrow capability closes.
- [AI-DLC integration delivery handoff](handoffs/2026-09-14-roadmap-aidlc-integration-delivery.md) — Read the selected delivery scope and held work.
- [BACKLOG.md #384](BACKLOG.md) — Read the approved inherited-decision scope.

## Applicable guardrails

- **The plan’s “## Scope guardrails”, selected-row authority:** Limit the artifact change to provenance on selected decision rows; do not add writer, lifecycle, or prompt authority.
- **The plan’s “## Scope guardrails”, baseline-only rebind:** Do not add rebind behavior or artifact mutation logic in this parser and renderer step.
- **The plan’s “## Scope guardrails”, held supplementary grounding:** Keep the row representation single-source and generic; do not introduce source roles or stage-specific identity.
- **The plan’s “## Scope guardrails”, runtime neutrality:** Do not add AI-DLC, Integration, connector, or runtime-specific vocabulary.
- **The plan’s “## Out of scope”, closed input shape:** Do not add support for free-form logs, question menus, directories, positional prose, or derived alternatives.

## Deferred

- Citation confirmation, source-currentness, anchor ownership, and model-mutation refusals — Step 3 owns these cross-record gates.
- Single-artifact placement and stage prompt routing — Step 4 owns which artifact receives each inherited row.
- Bounded feedback operations on inherited rows — Step 4 owns refusal and preservation through the existing revision decoder.
- Source-record syntax and admission — Step 1 owns the validated carried-decision input.
