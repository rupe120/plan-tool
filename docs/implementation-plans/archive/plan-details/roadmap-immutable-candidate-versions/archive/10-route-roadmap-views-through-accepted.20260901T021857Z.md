> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 10 — Route roadmap views through the accepted head while keeping unversioned reads unchanged

## Summary

Update `plan_tool/roadmap_view.py` so `load_roadmap()` reads an enrolled roadmap from the accepted head selected by step 3. Keep the existing live artifact loading path unchanged when no accepted head exists. Preserve `LoadedRoadmap`, mode visibility, renderers, and CLI call shape so every existing view sees one coherent selected artifact set. On green, a promoted head changes rendered roadmap content, while later edits to top-level artifacts cannot alter an enrolled view.

## Table of Contents

- [Summary](#summary) — The reader-routing result and compatibility boundary.
- [Table of Contents](#table-of-contents) — Links to each detail section.
- [Why](#why) — Why promotion needs a downstream reader effect.
- [Input](#input) — The accepted-head and view contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two existing files this step changes.
- [Implementation](#implementation) — Accepted-head selection, unchanged unversioned reads, and view invariants.
- [Tests](#tests) — Focused version-aware and regression coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that limit this reader conversion.
- [Deferred](#deferred) — Reader and writer work outside this proof.

## Why

`plan_tool/roadmap_view.py:load_roadmap()` currently builds every view from the live artifact paths, so moving an accepted head would change only selector metadata rather than what a user reads. Step 9 promotes one exact candidate through step 3’s accepted-head boundary; this step makes that approval visible in the existing roadmap views without changing the established behavior for roadmaps that have not enrolled.

## Input

- **Accepted-head selection:** Step 3 provides `plan_tool/roadmap_versions.py:load_accepted_version()` as the sole way to determine whether a roadmap is enrolled and to obtain complete artifact content from the shared root-or-candidate stored-version contract. Do not derive a version from a root-only record, private candidate path, directory order, version names, or live artifact paths.

- **Promotion result:** Step 9 updates the accepted-head selector to the sealed candidate. The view must consume that selection as read-only input and must not validate seals, run gates, or move the head itself.

- **View model:** `plan_tool/roadmap_view.py:LoadedRoadmap` holds parsed artifacts, absence and parse diagnostics, and the indexes every renderer uses. Keep its public fields and the `MODE_CURRENT` / `MODE_REVIEW` visibility contract intact.

- **Unversioned artifact loading:** `plan_tool/roadmap_view.py:load_roadmap()` currently uses the path helpers and `load_*_artifact()` functions from `plan_tool/roadmap_artifacts.py`. Preserve that route when accepted-head resolution reports no enrollment.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_view.py` — Route enrolled reads through step 3’s accepted-head boundary while retaining the current unversioned loader, diagnostic behavior, indexes, and rendering inputs.
  - `tests/test_roadmap_view.py` — Add accepted-head reader coverage and keep the existing unversioned and leaf-import checks accurate.

## Implementation

- **Select the read root before loading artifacts.** Make `plan_tool/roadmap_view.py:load_roadmap()` choose exactly one source for its full artifact bundle: step 3’s selected accepted version for an enrolled roadmap, or the current top-level artifact paths for an unversioned roadmap. The foundational rule is one selected root per loaded view.

- **Read the accepted version as a complete bundle.** Parse all staged artifacts from the root or candidate content selected and validated by `plan_tool/roadmap_versions.py:load_accepted_version()`. Do not combine an accepted artifact with a live artifact, dispatch to a second candidate resolver, infer a newer version from storage, or inspect live files after accepted-head selection succeeds.

- **Keep the unversioned branch unchanged.** Retain the current `roadmap_dir()`, `domain_path()`, `constraints_path()`, `components_path()`, `plans_path()`, and `load_*_artifact()` behavior when no accepted version exists. Existing partial-roadmap handling must still distinguish absent from unparseable artifacts and must continue to raise only for an invalid slug.

- **Do not silently bypass accepted-head authority.** If accepted-head resolution identifies an enrolled roadmap but cannot provide the selected content, preserve that boundary’s refusal or unavailable result. The loader must not fall back to top-level artifact files, because that would let a live edit override promotion.

- **Apply modes after selecting content.** Keep `MODE_CURRENT` and `MODE_REVIEW` as visibility rules over the same loaded artifact set. `build_design_row_index()`, `build_removal_index()`, `build_feedback_index()`, and the `LoadedRoadmap` indexes must use the accepted version in both modes; only the existing feedback and removal exposure differs.

- **Keep callers and renderers on the existing seam.** `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_view` must continue to call `load_roadmap()` with the same arguments. `plan_tool/roadmap_html.py:render_roadmap_html` already consumes `LoadedRoadmap`, so it receives accepted content through that object without a separate disk-read path or a file change in this step.

- **Retain reader-only layering.** Extend the import allowance checked by `tests/test_roadmap_view.py:test_module_imports_only_the_artifact_gates_relations_and_seed_manifest_leaves` for the accepted-head reader dependency. Do not add publication, promotion, model, subprocess, or write behavior to `plan_tool/roadmap_view.py`.

## Tests

### Tests for this step

- `test_load_roadmap_reads_one_complete_accepted_head_bundle` — asserts all parsed artifact fields come from one selected accepted version when matching live artifacts contain different valid content.

- `test_load_roadmap_observes_the_promoted_head_not_the_prior_version` — arranges step 9’s promoted selector and asserts the loaded content reflects its selected replacement while the earlier stored version remains unchanged.

- `test_load_roadmap_never_falls_back_to_live_artifacts_after_accepted_head_refusal` — asserts an enrolled roadmap with unavailable selected content does not render live artifact content as canonical.

- `test_current_and_review_modes_share_the_accepted_head` — asserts both modes use the same selected content while preserving current-mode feedback and removal hiding.

- `test_load_roadmap_parses_all_four_when_present` — keeps the existing unversioned live-read characterization green without an accepted-head record.

- `test_load_roadmap_names_absent_artifacts_in_stage_order` — keeps the existing unversioned partial-roadmap diagnostic behavior green.

- `test_module_imports_only_the_artifact_gates_relations_and_seed_manifest_leaves` — updates the direct and transitive import allowlist for the accepted-head read dependency without admitting a writer or orchestrator dependency.

Every listed test in `tests/test_roadmap_view.py` must be green before this step is complete.

## Acceptance criteria

- `plan_tool/roadmap_view.py:load_roadmap()` returns parsed content from the version selected by step 3 for an enrolled roadmap, even when live artifact files contain different valid content.

- A step 9 promotion changes the content returned by a new `load_roadmap()` call to the promoted candidate’s content.

- An enrolled roadmap with unavailable selected content does not fall back to live artifact files.

- `MODE_CURRENT` and `MODE_REVIEW` load the same selected artifact set and retain their existing feedback and removal visibility difference.

- An unversioned roadmap keeps the current live-path behavior, including complete, partial, absent, and unparseable artifact cases.

- `tests/test_roadmap_view.py` passes, including its updated import-discipline check.

## Applicable guardrails

- **The plan’s “## Scope guardrails”, binary observables** — prove this reader change with selected artifact content and returned view data, not with inferred version recency or prose-quality checks.

- **The plan’s “## Scope guardrails”, allowed behavior changes** — limit behavior changes to the accepted-head read path and preserve unversioned reads.

- **The plan’s “## Scope guardrails”, allowed reorganization** — use the shared accepted-head selection boundary as the only version-aware seam; do not reorganize roadmap artifacts or unrelated pipeline code.

- **The plan’s “## Out of scope”, reader migration** — convert this one downstream reader only. Do not extend version-aware loading to every roadmap consumer.

## Deferred

- Other direct roadmap readers — remain outside this step under the plan’s reader-migration boundary.

- Legacy in-place writer refusal — step 4 owns the protection against writers bypassing an enrolled roadmap’s accepted head.
