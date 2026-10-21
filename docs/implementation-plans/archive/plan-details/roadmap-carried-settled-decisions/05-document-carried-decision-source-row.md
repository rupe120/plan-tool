> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Document the carried-decision source and row contracts, then close BACKLOG.md #384

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Document the shipped carried-decision contract in `ROADMAP_FORMAT.md`, `DATA_CONTRACT.md`, and `docs/how-to/roadmap.md`, then remove the delivered work from `BACKLOG.md`. Use the implementation from steps 1–4 as the source of truth for field names, row forms, placement, and gate behavior. Keep inherited decisions visibly distinct from Roadmap-derived decisions without expanding Roadmap’s source authority. On green, an operator can understand how to provide, inspect, and trust a carried decision, and #384 no longer appears as active backlog work.

## Table of Contents

- [Summary](#summary) — The completed documentation and backlog outcome.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why the new source and row meanings need one clear contract.
- [Input](#input) — Landed source, row, gate, and routing contracts this step documents.
- [Files (creates vs edits)](#files-creates-vs-edits) — Documentation and backlog files changed by this step.
- [Implementation](#implementation) — Documentation ownership, required distinctions, and closure approach.
- [Tests](#tests) — Non-code verification for the updated contracts.
- [Acceptance criteria](#acceptance-criteria) — Observable documentation and backlog results.
- [References](#references) — Authoritative scope and contract reading.
- [Applicable guardrails](#applicable-guardrails) — Boundaries that keep this a narrow documentation step.
- [Deferred](#deferred) — Nearby work that remains outside #384.

## Why

`plan_tool/roadmap_artifacts.py:DecisionRow` and `plan_tool/roadmap_gates.py:check_decision_records` currently describe only Roadmap-derived decisions. Steps 1–4 add a closed brief block, inherited row form, deterministic citation checks, and one-stage placement rule; reference and operator guidance must show how a caller supplies the block and how a reviewer verifies its rows.

## Input

- **Step 1 source contract:** Step 1 reads the optional `## Carried decisions` JSON block from the brief supplied through `--from-existing`. Read its landed parser and the unchanged `source.json` path/digest writer rather than transcribing names from this plan.

- **Step 2 row contract:** Step 2 lands the inherited `DecisionRow` form and its parser/renderer rules in `plan_tool/roadmap_artifacts.py:_parse_decision_rows` and `_decision_mapping`. The landed names and omission behavior win if they differ from earlier detail text.

- **Step 3 gate contract:** Step 3 defines the accepted source match, settled status, owning-artifact placement, and local-anchor requirements in `plan_tool/roadmap_gates.py:check_decision_records` and its inherited-decision checks.

- **Step 4 routing contract:** Step 4 establishes that a carried decision appears once, in the artifact that owns its anchor. Document that result without restating prompt mechanics or granting prompts any new authority.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `ROADMAP_FORMAT.md` — Document the brief's closed JSON block, inherited `decisions` row form, source citation meaning, placement rule, compatibility behavior, and gate distinctions.
  - `DATA_CONTRACT.md` — Document the unchanged `source.json` path/digest baseline and its binding to the new brief block; retain redaction and lifecycle boundaries.
  - `docs/how-to/roadmap.md` — Explain when an operator supplies carried decisions, what Roadmap preserves, and how inherited rows differ during review.
  - `BACKLOG.md` — Remove delivered #384 and sweep its active references so #383 remains accurately described as separate deferred work.

## Implementation

- **Make `ROADMAP_FORMAT.md` the artifact-contract home.** Extend `## Concept-brief source admission and lifecycle`, the four artifact schemas, and `## Relations — return violations` to describe the landed carried-decision shape. State that a carried row has a confirmed source citation, remains `settled`, anchors locally in its owning artifact, and appears in only that artifact.

- **Keep the two decision forms separate.** Document the inherited form from `plan_tool/roadmap_artifacts.py:DecisionRow` alongside the Roadmap-derived form. A carried row retains optional upstream rationale or rejected alternatives exactly when the brief block supplies them, and omits them otherwise. A Roadmap-derived row retains its existing rationale and rejected-alternatives requirements.

- **Describe source authority narrowly.** Explain that the carried block arrives in the accepted, digest-bound brief and is validated before stage authoring. `source.json` records its path/digest, not a second copy of the block. Only owner-selected typed decisions enter stage prompts; the raw JSON is excluded from shared prompt context.

- **Preserve the existing source lifecycle.** `DATA_CONTRACT.md` and `ROADMAP_FORMAT.md` must retain the current `source.json` brief-path and digest semantics, including the narrow confirmed-rebind outcome. Document the inherited-decision provenance behavior that steps 1–3 land, without claiming that a baseline-only rebind publishes or repairs an artifact.

- **Explain bounded feedback.** Document that material feedback operations cannot add, edit, or remove a source-owned inherited decision. An unrelated revision preserves that row and must revalidate its citation against the current accepted brief before publication.

- **Write operator guidance at review level.** In `docs/how-to/roadmap.md`, direct readers to inspect a carried row’s source citation, settled status, owner artifact, and anchor. Explain that a carried row records an approved upstream choice rather than a Roadmap trade-off; keep implementation symbols and wire-shape detail in the reference docs.

- **Close #384 rather than archive it in place.** Remove the active #384 entry from `BACKLOG.md`, following its opening backlog maintenance rule. Sweep the file for references that describe #384 as pending or as a dependency, and update only those statements needed to keep #383 and the Roadmap arc accurate. Do not add a historical backlog entry or broaden this step into #383.

- **Use landed symbols as the final authority.** Before publishing prose, compare every cited code symbol with steps 1–4’s landed modules. If a future-facing implementation detail used a different field or helper name, document the code that exists.

## Tests

No new automated test file is required for this non-code step.

### Verification (non-code step)

1. `tests/test_roadmap_format.py` — Run the existing Roadmap format-document checks after updating examples, lifecycle guidance, and gate descriptions.

2. `tests/test_data_contract.py` — Run the data-contract drift guard after documenting the durable source-record shape.

3. Documentation example check — Parse every new or changed YAML example through the relevant `plan_tool/roadmap_artifacts.py:parse_*_artifact` function, render it with the matching `render_*_artifact` function, and run the appropriate `plan_tool/roadmap_gates.py` gate set with no violations.

4. Symbol check — Confirm every code symbol named in `ROADMAP_FORMAT.md` and `DATA_CONTRACT.md` exists at HEAD, and every future module reference remains path-only.

5. Backlog sweep — Search `BACKLOG.md` for `#384` and confirm remaining occurrences do not present it as active, planned, or a dependency.

## Acceptance criteria

- `ROADMAP_FORMAT.md` documents the exact landed brief JSON block, its `--from-existing` submission path, and both `DecisionRow` meanings without weakening Roadmap-derived row requirements.

- `ROADMAP_FORMAT.md` states that an inherited row is settled, cites confirmed recorded-source material, anchors in its owning artifact, and appears once in that artifact.

- `DATA_CONTRACT.md` documents how the unchanged durable brief path/digest binds carried decisions while retaining existing source-admission and redaction boundaries.

- `docs/how-to/roadmap.md` gives operators enough information to recognize and review inherited decisions without requiring them to read implementation code.

- Updated format examples parse, render, and clear their relevant deterministic gates.

- `tests/test_roadmap_format.py` and `tests/test_data_contract.py` pass.

- `BACKLOG.md` no longer lists #384 as active work, and its remaining Roadmap references describe #383 independently.

## References

- [Roadmap carried settled decisions plan — Read the approved scope, step order, and boundaries.](../../2-roadmap-carried-settled-decisions.md)

- [Roadmap AI-DLC intake comparison — Read the evidence that selects #384 and holds #383.](../../../../docs/evidence/roadmap-aidlc-intake-comparison-20260916.md)

- [Roadmap format contract — Read the current source lifecycle, row schemas, and gate table.](../../../../ROADMAP_FORMAT.md)

- [Data contract — Read the existing Roadmap lifecycle-event and redaction contract.](../../../../DATA_CONTRACT.md)

- [Roadmap walkthrough — Read the operator-facing source and review flow.](../../../../docs/how-to/roadmap.md)

- [AI-DLC integration delivery handoff — Read the selected delivery order and connector boundary.](../../../../handoffs/2026-09-14-roadmap-aidlc-integration-delivery.md)

## Applicable guardrails

- **The plan’s “## Scope guardrails”, carried-block authority** — Document only the approved decision-row input path; this step must not describe it as authority over other writers, lifecycle behavior, or stage inputs.

- **The plan’s “## Scope guardrails”, rebind boundary** — Preserve the distinction between source-baseline acceptance and artifact publication; documentation must not imply a rebind changes artifacts, feedback, or seeds.

- **The plan’s “## Scope guardrails”, #383 separation** — Keep per-stage supplementary grounding and multi-source identity outside these docs except where needed to state that they are not part of this contract.

- **The plan’s “## Out of scope”** — Do not add AI-DLC-specific names, parsing rules, runtime layout, or broad source-management concepts to user-facing documentation.

## Deferred

- Per-stage supplementary sources and declared roles (#383) — This capability remains separate from the carried-decision input and needs its own selected scope.
