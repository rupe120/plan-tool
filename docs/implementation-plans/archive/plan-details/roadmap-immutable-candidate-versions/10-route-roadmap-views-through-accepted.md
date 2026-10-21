> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 10 — Route roadmap views through accepted head while keeping unversioned reads unchanged

## Summary

Update `plan_tool/roadmap_view.py` so `load_roadmap()` reads an enrolled roadmap from the accepted head resolved through step 3's contract. Keep the current live-artifact path unchanged when no accepted head exists. The key rule is that one loaded view uses one complete source bundle, never a mix of stored and live artifacts. On green, promotion changes every existing roadmap view’s input while later top-level edits cannot override an enrolled view.

## Table of Contents

- [Summary](#summary) — The reader-routing result and compatibility boundary.
- [Table of Contents](#table-of-contents) — Links to each detail section.
- [Why](#why) — Why promotion needs a visible downstream effect.
- [Input](#input) — The accepted-head and existing view contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two existing files this step changes.
- [Implementation](#implementation) — Selected-content loading, unchanged legacy reads, and view invariants.
- [Tests](#tests) — Focused accepted-head and regression coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [Applicable guardrails](#applicable-guardrails) — Boundaries on this reader conversion.
- [Deferred](#deferred) — Other reader and writer work outside this step.

## Why

`plan_tool/roadmap_view.py:load_roadmap()` currently builds every view from live artifact paths, so an accepted-head move would alter only metadata rather than what an operator reads. Step 9 makes one sealed replacement the accepted version; this step makes that selection visible through the existing view boundary while preserving behavior for roadmaps without a selector.

## Input

- **Accepted-head result:** Step 3 supplies the read-only accepted-head outcome and its leaf-safe fixed four-member inventory: either no selector, or one validated complete root-or-candidate bundle in that order. A present but invalid selector remains an error, not an unversioned result.

- **Promotion:** Step 9 moves only the accepted-head selector. This step reads that result and does not validate seals, rerun gates, or move the selector.

- **View model:** `plan_tool/roadmap_view.py:LoadedRoadmap`, `MODE_CURRENT`, and `MODE_REVIEW` define the parsed-artifact and visibility inputs consumed by all view renderers.

- **Artifact parsing:** `plan_tool/roadmap_artifacts.py:parse_domain_artifact()`, `parse_constraints_artifact()`, `parse_components_artifact()`, and `parse_plans_artifact()` remain the typed parsing boundary for selected stored text. The existing `load_*_artifact()` helpers remain the unversioned live-path boundary.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_view.py` — Route enrolled reads through step 3’s accepted-head result while retaining the current unversioned loader, `LoadedRoadmap` shape, indexes, and mode behavior.
  - `tests/test_roadmap_view.py` — Add accepted-head coverage and update reader-import hygiene without weakening the existing unversioned cases.

## Implementation

- **Foundational logic: select one complete source bundle before parsing.** Make `plan_tool/roadmap_view.py:load_roadmap()` choose either the complete accepted bundle from step 3 or the current live artifact paths. It must not select per artifact.

- **Parse accepted content in fixed artifact order.** Map the four accepted artifact texts to `parse_domain_artifact()`, `parse_constraints_artifact()`, `parse_components_artifact()`, and `parse_plans_artifact()`. Build `LoadedRoadmap` and every index from that one parsed set.

- **Import only the leaf-safe version contract.** `plan_tool/roadmap_view.py` may import the accepted-version reader and fixed inventory from `plan_tool/roadmap_versions.py`; it must not import `plan_tool/roadmap.py`, `STAGES`, or a writer module. Step 3's parity test, not a production reader import, keeps the version inventory aligned with the orchestrator table.

- **Do not mix or replace selected content.** After accepted-head resolution succeeds, `load_roadmap()` must not call live artifact loaders, inspect top-level artifact paths, scan stored versions, or use a newer candidate. A selected bundle must remain the only source for that call.

- **Fail closed for a present invalid head.** Preserve step 3’s accepted-head failure when selected storage is unavailable or invalid. Do not treat that state as missing enrollment or fall back to live artifacts.

- **Keep unversioned loading unchanged.** When step 3 reports no selector, retain the existing `roadmap_dir()`, `domain_path()`, `constraints_path()`, `components_path()`, `plans_path()`, and `load_*_artifact()` behavior. Partial bundles must keep their current absent-versus-unparseable diagnostics, and invalid slugs must keep their current error behavior.

- **Apply mode after source selection.** Keep `build_design_row_index()`, `build_removal_index()`, and `build_feedback_index()` based on the same parsed bundle in both modes. `MODE_CURRENT` and `MODE_REVIEW` may differ only in the existing feedback and removal visibility fields.

- **Keep existing callers on the seam.** `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_view()` must continue to call `load_roadmap()` with its current arguments. `plan_tool/roadmap_html.py:render_roadmap_html()` already consumes `LoadedRoadmap`, so it receives selected content without another reader path.

- **Retain reader-only boundaries.** Update `tests/test_roadmap_view.py:test_module_imports_only_the_artifact_gates_relations_seed_manifest_and_version_leaves` to admit the accepted-head reader dependency and its required contract dependencies only. Do not add publication, promotion, model, subprocess, or write behavior to `plan_tool/roadmap_view.py`.

## Tests

### Tests for this step

- `test_load_roadmap_reads_the_complete_bundle_selected_by_the_accepted_head` — A valid accepted bundle supplies all four parsed artifacts even when live files contain different valid content.

- `test_load_roadmap_does_not_read_live_artifacts_after_accepted_head_selection` — A selected accepted bundle does not call live artifact loaders or combine stored and live members.

- `test_load_roadmap_observes_the_candidate_selected_after_promotion` — Moving the selector to step 9’s promoted candidate changes a new loaded view while earlier stored content remains unchanged.

- `test_load_roadmap_preserves_accepted_head_failure_without_live_fallback` — A present but invalid accepted head reports its contract failure before live artifact content can become canonical.

- `test_current_and_review_modes_share_the_accepted_head_bundle` — Both modes use the same selected rows and retain only their established feedback and removal visibility difference.

- `test_load_roadmap_parses_all_four_when_present` — An unversioned complete roadmap keeps its live-path result.

- `test_load_roadmap_names_absent_artifacts_in_stage_order` — An unversioned partial roadmap keeps its current absent-artifact diagnostics.

- `test_load_roadmap_names_unparseable_artifact_distinctly_from_absent` — An unversioned malformed artifact remains a rendering diagnostic rather than an accepted-head behavior change.

- `test_module_imports_only_the_artifact_gates_relations_seed_manifest_and_version_leaves` — The import check permits the selected-version reader and fixed inventory but rejects `plan_tool.roadmap`, writer, and orchestrator dependencies.

- `test_module_reads_disk_only_through_the_artifact_loaders_and_the_draft_seed_read` — `plan_tool/roadmap_view.py` does not add direct version-file scanning or write behavior.

Every listed test in `tests/test_roadmap_view.py` must be green before this step is complete.

## Acceptance criteria

- `plan_tool/roadmap_view.py:load_roadmap()` returns parsed artifacts from step 3’s accepted bundle for an enrolled roadmap, even when live artifact files contain different valid content.

- A step 9 promotion changes the artifact content returned by a new `load_roadmap()` call to the promoted candidate.

- A present invalid accepted head does not fall back to top-level roadmap artifacts.
- Accepted-head loading uses Step 3's leaf-safe fixed inventory without importing `plan_tool.roadmap` or `STAGES` in the reader path.

- `MODE_CURRENT` and `MODE_REVIEW` use the same selected artifact set and retain their existing visibility difference.

- A roadmap with no accepted selector keeps the current complete, partial, absent, and unparseable live-read behavior.

- `tests/test_roadmap_view.py` passes, including the updated import and direct-read boundaries.

## Applicable guardrails

- **The plan’s “## Scope guardrails”, binary observables** — Prove the change through selected content and returned view data, not version recency or prose judgments.

- **The plan’s “## Scope guardrails”, allowed behavior changes** — Limit this step to accepted-head reads and preserve unversioned behavior.

- **The plan’s “## Scope guardrails”, allowed reorganization** — Use the shared accepted-head boundary as the only version-aware read seam; do not reorganize roadmap artifacts or unrelated pipeline code.

- **The plan’s “## Out of scope”, reader migration** — Convert only `plan_tool/roadmap_view.py`; do not migrate every roadmap consumer.

- **The plan’s “## Scope guardrails”, model and promotion authority** — Do not add model calls or selector mutation to this read-only path.

## Deferred

- Other live artifact readers — `plan_tool/create.py:_load_roadmap_research_targets()` and `plan_tool/cli/authoring.py:_confirm_invalidated_roadmap_seed()` remain on their current sources; converting them needs separately authorized reader-migration work.

- Legacy mutation and seed paths — `plan_tool/roadmap.py:_load_stage_artifact()`, `plan_tool/roadmap.py:_apply_roadmap_seeds()`, and `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_materialize_owned()` are not view readers. Step 4 owns their enrolled-roadmap refusal boundary.
