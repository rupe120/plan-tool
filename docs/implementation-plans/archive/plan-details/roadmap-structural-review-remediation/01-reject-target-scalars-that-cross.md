# Step 1 — Reject target scalars that cross physical YAML lines before building the bounded replacement candidate

## Summary

Make the structural patcher reject an existing target scalar whose YAML source range crosses a physical line boundary. Update `plan_tool/roadmap_structural_revision_patch.py` at `_single_line_scalar_span` and add a regression in `tests/test_roadmap_structural_revision_patch.py`. The key decision is to judge source positions, not the parsed scalar value, because YAML folding can hide a physical line break. On green, the merger fails before applying replacements for a canonically rendered wrapped target scalar while ordinary one-line rewrites still pass.

## Table of Contents

- [Summary](#summary) — Quick review of the change and its green result.
- [Table of Contents](#table-of-contents) — Links to each detail section.
- [Why](#why) — Explains the source-span safety gap.
- [Input](#input) — Names the preflight and YAML-node contracts this change reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — Lists the two edited files.
- [Implementation](#implementation) — Defines the source-line admission rule and its boundaries.
- [Tests](#tests) — Covers the new rejection case and retained positive behavior.
- [Acceptance criteria](#acceptance-criteria) — States observable completion checks.
- [References](#references) — Points to the YAML and PyYAML behavior behind the rule.
- [Applicable guardrails](#applicable-guardrails) — Applies the plan’s merge-safety and scope limits.
- [Deferred](#deferred) — Records work this narrow remediation leaves out.

## Why

`plan_tool/roadmap_structural_revision_patch.py:_single_line_scalar_span` currently accepts a scalar by its parsed node shape, even when its source text covers more than one YAML line. YAML can fold that source into one logical string, so value-based checks cannot protect the bounded source replacement. Rejecting the source before candidate construction keeps `merge_structural_revision_patch` limited to replacing one physical scalar line and preserves its exact-patch safety contract.

## Input

- **Preflight source contract:** `plan_tool/roadmap_structural_revision.py:StructuralRevisionPreflight` carries the canonical `selected_artifact_text`, paired with `selected_stage`, `target_row`, and selected feedback.
- **YAML source locations:** `plan_tool/roadmap_structural_revision_patch.py:_compose_frontmatter` supplies PyYAML nodes whose source marks distinguish physical lines even when `ScalarNode.value` has folded them.
- **Replacement scalar contract:** `plan_tool/roadmap_structural_operations.py:render_structural_scalar` already admits only replacement values that render as one YAML scalar line. Keep that outbound rule unchanged; this step closes the matching inbound-source gap.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_structural_revision_patch.py` — Strengthen `_single_line_scalar_span` so it refuses a scalar source range that crosses physical YAML lines.
  - `tests/test_roadmap_structural_revision_patch.py` — Add a canonical wrapped-scalar regression for `merge_structural_revision_patch`.

## Implementation

- **Foundational rule:** Treat a target scalar as patchable only when its complete YAML source span is on one physical line. This rule applies even when YAML parses a continued plain or quoted scalar into a single string.

- **Put the check in the shared span admission helper:** Update `plan_tool/roadmap_structural_revision_patch.py:_single_line_scalar_span` after it admits a string `ScalarNode` and before it derives offsets or returns `_ScalarSpan`. Every selected row id, selected editable field, selected feedback id, and selected feedback state already reaches this helper through `_locate_row_field_scalar` or `_locate_selected_feedback_state`; do not add a special-case bypass.

- **Use source positions, not scalar content:** Compare the node’s physical source-line boundaries from PyYAML marks, or use an equivalent raw-source-range check. Do not inspect `ScalarNode.value` for a newline: YAML plain-scalar folding can remove the physical break from that value.

- **Fail before candidate assembly:** A rejected span must prevent `merge_structural_revision_patch` from appending `_Replacement` entries or reaching `_apply_replacements`. Preserve the existing error type, `StructuralRevisionPatchError`, with a message that identifies the one-line source requirement.

- **Keep the one-line contract narrow:** Retain the existing allowed scalar styles and existing checks for aliases, tags, block scalars, inline syntax, indentation, and final line breaks. Rejecting a line-spanning source is an additional admission condition, not a reason to normalize the artifact or accept a wider source patch.

- **Leave adjacent ownership unchanged:** Do not alter `plan_tool/roadmap_artifacts.py:_render` to force a global YAML wrapping policy, and do not alter `plan_tool/roadmap_structural_operations.py:render_structural_scalar`. Keep `plan_tool/roadmap_structural_revision_run.py:run_structural_revision` unchanged; it already maps merger failures to its existing rejection outcome.

## Tests

- **Existing positive control:** `test_merge_applies_selected_row_field_operations_and_feedback_response` in `tests/test_roadmap_structural_revision_patch.py` remains green, proving ordinary one-line selected-field rewrites still produce a canonical candidate.

### Tests for this step

- `test_merge_rejects_canonical_target_scalar_that_crosses_a_physical_yaml_line` — Build a normal rendered preflight whose selected target field wraps over physical YAML lines, assert `merge_structural_revision_patch` raises `StructuralRevisionPatchError`, and prove replacement application is not reached.

Green-before-done gate: every test in `tests/test_roadmap_structural_revision_patch.py` is green.

## Acceptance criteria

- A canonically rendered selected target scalar that crosses physical YAML lines causes `merge_structural_revision_patch` to raise `StructuralRevisionPatchError`.
- The rejection occurs before `_apply_replacements` can build a bounded replacement candidate.
- A one-line selected target scalar still produces a candidate whose text equals `selected_stage.render(candidate.artifact)`.
- `tests/test_roadmap_structural_revision_patch.py` passes.

## References

- [YAML 1.2.2 Specification](https://yaml.org/spec/1.2.2/) — Read the plain-scalar folding and multiline presentation rules that separate logical values from physical source lines.
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — Read the composition-node and source-mark behavior used to locate safe scalar spans.

## Applicable guardrails

- **The plan’s “## Plan intent”, merge-safety contract:** Keep this as a local source-span admission check that protects the existing one-artifact structural rewrite.
- **The plan’s “## Step intent”, physical-line-safe patching:** Reject unsafe source spans rather than trying to patch them across several lines.
- **The plan’s “## Out of scope”, writer and route ownership:** Limit edits to the patcher and its tests; leave broader patch language, artifact authority, and execution routing untouched.

## Deferred

- **Generic support for multiline YAML source patches** — This step deliberately rejects that source shape; supporting it needs a separate plan-level design decision.
