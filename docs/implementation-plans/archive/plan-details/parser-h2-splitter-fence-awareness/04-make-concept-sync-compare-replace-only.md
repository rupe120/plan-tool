> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Make concept sync compare and replace only real headings, preserve atomic plan and sidecar overwrite and rollback, and leave both files unchanged on fence errors

## Summary

Make `plan_tool/concept_sync.py:synchronize_concepts` use step 1’s fence-safe H2 boundaries for its owned-section compare-and-swap and section replacement. Keep fenced examples as plan content while ensuring only real `Deferred` and `Out of scope` headings participate in synchronization. Reject an unmatched opening fence before either the plan or concept sidecar can change. Preserve the existing per-file atomic publish, paired rollback, scope mapping, and fingerprint behavior.

## Table of Contents

- [Summary](#summary) — The completed behavior and main design choice.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — The concept-sync corruption this step prevents.
- [Input](#input) — The plan, sidecar, and step 1 contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed by this step.
- [Implementation](#implementation) — Safe comparison, replacement, refusal, and publication rules.
- [Tests](#tests) — Regression coverage for sync behavior and rollback.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Markdown and Python references for the boundary rules.
- [Applicable guardrails](#applicable-guardrails) — Plan limits that bind this step.
- [Deferred](#deferred) — Related work owned elsewhere.

## Why

`plan_tool/concept_sync.py:synchronize_concepts` compares owned bodies through `plan_tool/parser.py:parse_body_sections` and replaces them through `plan_tool/parser.py:replace_body_sections`. A fenced example containing an owned-looking H2 can therefore look like a concurrent edit or become a replacement target, damaging the plan while concept decisions are synchronized. This writer also updates `plan_tool/concept_tree.py:concepts_path`, so fence rejection must happen before its paired publication begins.

## Input

- **Step 1 fence-safe parser contract** — Use step 1’s explicit boundary-safe mode for `plan_tool/parser.py:parse_body_sections` and `plan_tool/parser.py:replace_body_sections`, plus its shared unmatched-opening-fence signal. Preserve fenced content; concept sync does not pattern-match section bodies and must not select content-stripping mode.

- **Concept-sync snapshots** — `plan_tool/concept_sync.py:synchronize_concepts` receives `plan_snapshot`, `original_tree`, `reviewed_tree`, and optional `source_plan_text`. Keep its comparison between the snapshot source, on-disk plan, and serialized sidecar intact.

- **Paired target paths** — `plan_tool/parser.py:split_plan_document` supplies the frontmatter-stripped bodies, and `plan_tool/concept_tree.py:concepts_path` identifies the sidecar that must stay paired with the plan.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/concept_sync.py` — Select fence-safe real-heading parsing and replacement in `synchronize_concepts`; refuse unmatched fences before publication while retaining the existing paired rollback path.
  - `tests/test_concept_sync.py` — Cover fenced pseudo-headings, unmatched-fence preservation, and rollback when an existing sidecar has already been overwritten.

## Implementation

- **Make real H2 headings the sync boundary.** In `plan_tool/concept_sync.py:synchronize_concepts`, use step 1’s boundary-safe parser mode when deriving the source and current `deferred` / `out of scope` maps. A heading-looking line inside a closed fence must not participate in the owned-body comparison.

- **Replace only real owned sections.** Pass the same boundary-safe choice to `plan_tool/parser.py:replace_body_sections` when applying `render_scope_decisions`. A fenced pseudo-heading must remain unchanged, and a real heading after the fence must still receive the decision text. Keep the existing normalization, missing-section append behavior, and real-heading ordering contract.

- **Preserve fenced content.** Keep boundary safety separate from content stripping. `plan_tool/parser.py:split_plan_document`, `render_plan_text`, and the replacement path must carry closed fenced examples through unchanged except for the intended real owned-section update.

- **Reject unsafe source text before publication.** Check both the snapshot source body and current on-disk body for step 1’s unmatched-opening-fence result before calculating final output or calling `publish`. Return a normal non-success `ConceptSyncResult` with an actionable fence error; do not create, overwrite, restore, or refresh either target for this refusal.

- **Keep compare-and-swap semantics.** Continue rejecting changed frontmatter, a changed real owned section, or a changed serialized sidecar. Continue allowing concurrent edits outside the two real owned sections to flow through, including edits inside a closed fenced example.

- **Keep the paired publication protocol.** Retain `plan_tool/concept_sync.py:_atomic_publish`, `_restore`, and the `published` tracking in `synchronize_concepts`. Each file must publish atomically, and a failure after the sidecar write must restore the prior plan and prior sidecar state. Do not move fence handling after the first publish or replace this focused writer with a broader transaction mechanism.

- **Reuse the direct callers unchanged.** `plan_tool/create.py:_publish_create_plan`, `plan_tool/create.py:_finalize_create_plan`, and `plan_tool/cli/scope_review_cmd.py:cmd_scope_review` continue calling `synchronize_concepts` through its existing API. The callee owns this final write-boundary check.

## Tests

### Tests for this step

- `test_sync_ignores_changed_fenced_pseudo_owned_heading_in_compare` — Changing an owned-looking H2 and its body inside a closed fence does not report source divergence, and the edited example remains in the published plan.
- `test_sync_replaces_only_real_owned_heading_and_preserves_fenced_example` — A sync updates the real `Deferred` or `Out of scope` body while leaving an identically named fenced example unchanged.
- `test_sync_rejects_unmatched_opening_fence_without_changing_plan_or_sidecar` — An unmatched opening fence returns failure before either target changes, covering both an existing sidecar and an absent sidecar.
- `test_sync_detects_changed_owned_section_without_writes` — A change to a real owned section still reports source divergence and preserves the current plan.
- `test_second_publication_failure_rolls_back_new_sidecar` — A failure on the plan publication removes a newly created sidecar and restores the plan.
- `test_second_publication_failure_restores_existing_plan_and_sidecar` — A failure after overwriting an existing sidecar restores both original file contents.
- `test_sync_renders_decisions_preserves_markdown_and_maps_steps` — A successful safe sync keeps unrelated markdown, applies step scopes, and stores the fingerprint paired with the final plan.

Every listed test must be green before this feature step is complete.

## Acceptance criteria

- `plan_tool/concept_sync.py:synchronize_concepts` compares and replaces only H2 headings outside fenced code blocks.
- A closed fenced example containing `## Deferred` or `## Out of scope` remains unchanged after successful synchronization.
- A real owned heading after a fenced pseudo-heading receives the rendered concept decision without losing adjacent plan content.
- An unmatched opening fence in either source text causes synchronization to fail before changing the plan or `concepts.json`, whether the sidecar exists or not.
- A real frontmatter or owned-section edit still reports source divergence, while an edit outside those real sections remains allowed by the existing compare-and-swap contract.
- A failure during the second paired publish restores both the previous plan and previous sidecar.
- `tests/test_concept_sync.py` passes.

## References

- [CommonMark Spec — Fenced code blockshttps: — Read the opener, closer, and end-of-document rules used by step 1’s shared fence result.
- [CommonMark Spec — ATX headingshttps: — Read the heading rules that apply only outside fenced code.
- [Python 3.13 documentation — re: Regular expression operationshttps: — Read the multiline matching and span APIs behind line-oriented boundary detection.
- [pytest documentation — Parametrize fixtures and test functionshttps: — Use parametrization where it keeps sidecar-present and sidecar-absent fence-refusal cases compact.

## Applicable guardrails

- **The plan’s “Plan intent”** — Keep this work focused on fence-safe plan-body H2 handling; do not alter parser defaults or unrelated readers.

- **The plan’s “Step intent”** — Limit the change to concept decisions, fenced examples, and the plan/sidecar synchronization boundary.

- **The plan’s “Out of scope”, allowed behavior changes** — Restrict user-visible changes to correcting fenced pseudo-heading handling and refusing unsafe writes.

- **The plan’s “Out of scope”, allowed reorganization** — Keep the existing concept-sync publication structure; do not add a consolidation or transaction refactor.

- **The plan’s “Out of scope”, other heading-regex implementations** — Do not modify artifact-specific scanners or document-shape parsers outside this step’s two files.

## Deferred

- Parser-reader rollout and route-level write refusal — Steps 2 and 3 own the broader consumer and command paths; this step only consumes step 1’s shared parser and fence contracts at the concept-sync boundary.
- Further consolidation of `plan_tool/parser.py` and `plan_tool/scope_fence.py` — Keep their separate section semantics unless the plan’s architecture decision explicitly authorizes a minimal shared-primitive change.
