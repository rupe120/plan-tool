> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Select eligible sibling creates using existing roadmap identity

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Add read-only sibling selection in `plan_tool/review.py`, with coverage in `tests/test_review.py`. Select registered plans within the audited repository and restrict roadmap-derived plans to siblings from the same roadmap. Use existing source-seed and accepted-head readers without changing their contracts. Return an immutable set of explicit creation paths that preserves the audited plan’s own creates when sibling discovery provides nothing.

## Table of Contents

- [Summary](#summary) — Scope and observable result.
- [Table of Contents](#table-of-contents) — Section map.
- [Why](#why) — The missing selection capability.
- [Input](#input) — Existing plan, manifest, and roadmap contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two files this step changes.
- [Implementation](#implementation) — Eligibility, containment, and failure behavior.
- [Tests](#tests) — Selection and rejection cases.
- [Acceptance criteria](#acceptance-criteria) — Checkable completion conditions.
- [References](#references) — Relevant contract owners.
- [Applicable guardrails](#applicable-guardrails) — Boundaries on this implementation.
- [Deferred](#deferred) — Consumer wiring owned by the next step.

## Why

`plan_tool/review.py:_planned_paths` returns only the audited plan’s explicit creates. Both Input-reference consumers use that set, so an absent file promised by a legitimate sibling still produces a missing-path finding. The source entry in `BUG_BACKLOG.md` identifies the resulting noise in roadmap-derived plans. This step supplies the missing eligibility rule without changing the underlying anchor validator or weakening its rejection cases.

## Input

- **Audited plan:** Read `plan_tool/schema.py:Plan` (`source_seed`) and `plan_tool/schema.py:Step` (`creates`). Preserve the supplied plan’s own creates even when it is not registered.
- **Registered candidates:** Read paths through `plan_tool/locator.py:load_manifest_plan_paths(repo_root, manifest_path=None)`. It returns resolved paths, but does not enforce repository containment for relative traversal entries.
- **Parsed siblings:** Use `plan_tool/parser.py:parse_plan`. A missing, unreadable, or malformed sibling supplies no creation promise.
- **Source identity:** `plan_tool/review_persistence.py:_resolve_source_seed_path` supports live seeds and conventional archives. `plan_tool/roadmap_seed_state.py:locate_tracked_seed` returns `TrackedSeedLocation` with `plan_id`, `roadmap_slug`, and `state_path`.
- **Accepted roadmap:** `plan_tool/roadmap_versions.py:load_accepted_version` reads the selected immutable version. `plan_tool/roadmap_artifacts.py:parse_plans_artifact` provides the plan-row contract when membership needs confirmation against that version.
- **Verification limit:** These inputs establish declared creation paths and roadmap membership. They do not prove delivery or agreement between sibling contracts.

## Files (creates vs edits)

- **New files:** None.
- **Existing files (edits only):**
  - `plan_tool/review.py` — add bounded sibling discovery and eligibility selection beside `_planned_paths`.
  - `tests/test_review.py` — add hermetic tests for the selector and its exclusion rules.

## Implementation

- **Foundational logic: repository-scoped sibling-create eligibility.** Add a small read-only helper that takes the audited plan, its path, and the repository root, and returns a `frozenset[str]`. Recommend keeping `_planned_paths` as the unchanged own-plan primitive and composing its result with eligible sibling creates.

- **Discover through the manifest only.** Use `plan_tool/locator.py:load_manifest_plan_paths`; do not scan plan directories for additional candidates. Check resolved candidate containment before reading or parsing it, including symlink escapes. Deduplicate repeated registrations and avoid treating the audited plan’s disk copy as a separate sibling.

- **Collect only explicit creates.** Read `Step.creates`, never infer creation from `Step.files`, prose references, filenames, or dependency notes. Candidate creation paths must remain within the audited repository. Match the existing declared-path interpretation rather than introducing suffix matching or a new path format.

- **Choose the eligibility branch from evidence.**
  - For an ordinary plan without roadmap identity, include valid registered plans in the repository.
  - For a roadmap-derived plan, include only candidates whose existing durable identity establishes membership in the same roadmap.
  - Keep unavailable or malformed identity distinct from an established ordinary plan. Uncertain roadmap evidence must not trigger the unrestricted branch.
  - A candidate with uncertain identity supplies no exemption to a roadmap-restricted audit.

- **Use existing identity readers unchanged.** Resolve live or archived sources with `plan_tool/review_persistence.py:_resolve_source_seed_path`, then evaluate tracked identity through `plan_tool/roadmap_seed_state.py:locate_tracked_seed`. Confirm membership using the accepted version where needed; do not read an unselected roadmap artifact as current authority. Compare repository-contained roadmap ownership, not the slug alone, so separate roadmap roots with matching names cannot become siblings.

- **Support the reproduced plain-frontmatter form.** The saved replay’s archived seeds contain existing `roadmap` and `plan_id` frontmatter but no lifecycle marker, so `locate_tracked_seed` alone returns no identity. Read that existing metadata from the source selected by `_resolve_source_seed_path`, including the conventional prepended replacement notice. Confirm the named row in the selected accepted roadmap at the repository-contained owning location. Missing or conflicting lifecycle/frontmatter evidence must not become an ordinary-plan fallback. No new seed key or lifecycle is introduced.

- **Keep identity lookup bounded.** Honor the owning readers’ archive and lifecycle interpretation. Do not invent new rules for archived generations, seed freshness, or plan status. Derive the owning plans directory from existing resolved inputs rather than hardcoding the default directory.

- **Preserve import direction.** `plan_tool/review_persistence.py` imports `plan_tool/review.py`; any reuse of its source resolver must use a function-local import, matching existing local persistence imports in `plan_tool/review.py`. Do not extract or relocate shared readers in this feature step.

- **Fail closed without losing own creates.** Missing manifests, invalid manifest data, unavailable roadmap evidence, and unusable sibling records must add no unsupported paths. A broken individual sibling must not discard valid siblings that the existing manifest reader successfully returns. Handle expected read and parse failures without hiding programming errors.

- **Return data without side effects.** Discovery must not write seeds, lifecycle state, manifests, accepted heads, or placeholder files. Keep any reuse of parsed candidates or roadmap reads local to the selection operation; do not introduce a persistent cache.

- **Leave consumers for step 2.** `plan_tool/review.py:check_plan_input_contract_references` and `plan_tool/review.py:check_step_input_contract_references` are the two consumers of `_planned_paths`. This step supplies their common selection capability; step 2 owns using it consistently, including reuse across a detail sweep. Reject the broader alternative of changing `plan_tool/data_contract.py:_code_anchor_resolves`, which already separates missing-path exemptions from validation of existing symbols.

## Tests

Add selector tests in `tests/test_review.py`. Use small temporary manifests, plans, and existing-format roadmap evidence; no backend invocation is needed.

### Tests for this step

- `test_eligible_creates_preserve_own_plan_without_manifest` — returns own creates for an explicitly supplied unregistered plan.
- `test_ordinary_plan_accepts_registered_sibling_creates` — includes explicit creates from valid repository-registered candidates.
- `test_unregistered_plan_cannot_supply_creates` — ignores an otherwise valid plan beside registered plans.
- `test_edit_only_paths_never_supply_creation_exemptions` — excludes paths declared only in `Step.files`.
- `test_roadmap_plan_accepts_only_same_roadmap_siblings` — includes a confirmed sibling and excludes ordinary or different-roadmap candidates.
- `test_same_slug_in_different_roadmap_roots_is_not_shared_identity` — prevents slug-only identity matching.
- `test_archived_source_preserves_roadmap_membership` — obtains the same membership from an archive selected by the existing source reader.
- `test_archived_plain_frontmatter_without_marker_preserves_membership` — mirrors the replay: replacement notice, then existing `roadmap`/`plan_id` frontmatter, no lifecycle marker; eligible connector creates are included only after accepted-row confirmation. Add malformed and conflicting variants to pin the non-broadening boundary.
- `test_unknown_roadmap_identity_does_not_enable_repository_wide_selection` — excludes unrelated candidates when source or membership evidence is unavailable or malformed.
- `test_membership_uses_accepted_roadmap_content` — ignores contradictory unselected content and rejects membership absent from the accepted evidence used by the selector.
- `test_invalid_sibling_is_skipped_without_losing_valid_sibling_creates` — covers missing, unreadable, and malformed candidate records.
- `test_invalid_manifest_preserves_own_creates_without_broadening` — returns no sibling exemption when manifest loading fails.
- `test_sibling_selection_rejects_repository_escapes` — covers traversal and symlink escapes in candidate plans, identity evidence, and candidate creates.
- `test_duplicate_and_self_registrations_do_not_change_selected_paths` — keeps selection stable and preserves the supplied audited plan as the own-create authority.
- `test_sibling_selection_does_not_mutate_source_artifacts` — verifies that selection leaves manifest, seed, state, and roadmap bytes unchanged.

Every added or changed test must be green before completion. Run the affected existing tests in `tests/test_review.py` and the full suite. Verify the positive exemption and negative eligibility boundaries by targeted mutation: remove a valid sibling contribution and bypass a restriction separately, and confirm the corresponding tests fail.

## Acceptance criteria

- The selector returns own creates plus explicit creates from eligible registered siblings.
- An ordinary plan accepts valid repository-registered candidates; a roadmap-derived plan accepts only confirmed same-roadmap candidates.
- Missing or malformed roadmap evidence never enables unrestricted sibling selection.
- Archived-source identity remains usable through the existing reader.
- Unregistered plans, edit-only declarations, and repository escapes contribute no paths.
- Invalid discovery inputs preserve the audited plan’s own creates.
- Selection leaves source artifacts unchanged and invokes no model.
- Changes remain confined to `plan_tool/review.py` and `tests/test_review.py`.
- All affected tests and the full suite pass; targeted mutations demonstrate that exemption and exclusion tests detect broken behavior.

## References

- [Source bug and eligibility contract](../../../../../BUG_BACKLOG.md) — Read the entry about Input checks reporting sibling-created paths as missing.
- [Plan architecture and scope](../../2-sibling-planned-input-paths.md#architecture) — Read the repository and same-roadmap selection requirements.
- [Manifest reader](../../../../../plan_tool/locator.py) — Inspect `load_manifest_plan_paths` and its containment limits.
- [Source-seed resolution](../../../../../plan_tool/review_persistence.py) — Inspect `_resolve_source_seed_path` and `_read_source_seed_bytes` for archive handling.
- [Tracked seed identity](../../../../../plan_tool/roadmap_seed_state.py) — Inspect `locate_tracked_seed` and `TrackedSeedLocation`.
- [Accepted roadmap reader](../../../../../plan_tool/roadmap_versions.py) — Inspect `load_accepted_version` for immutable accepted-head authority.
- [Roadmap contract](../../../../../ROADMAP_FORMAT.md) — Read accepted versions and draft-seed identity.
- [Anchor validation](../../../../../plan_tool/data_contract.py) — Inspect `_code_anchor_resolves` for the unchanged missing-path and existing-symbol boundary.
- [Architecture](../../../../ARCHITECTURE.md) — Check import direction before adding reader dependencies.
- [Testing guide](../../../../../TESTING.md) — Keep filesystem fixtures isolated and backend calls neutralized.

## Applicable guardrails

- **Plan “## Scope guardrails,” creation exemption:** Limit the selector’s output to the declared creation promises permitted by that section.
- **Plan “## Architecture,” existing identity:** Reuse current identity authority; this step must not change its interpretation or add provenance.
- **Plan “## Out of scope,” validation policy:** Keep anchor validation, conceptual audit behavior, and reporting policy outside this selector change.
- **Plan “## Out of scope,” source mutation:** Treat all discovery inputs as read-only.
- **Plan “## Risks,” repeated discovery:** Keep the result suitable for reuse by step 2 without adding a cache lifecycle.

## Deferred

- Consumer integration in `plan_tool/review.py:check_plan_input_contract_references` and `plan_tool/review.py:check_step_input_contract_references` — step 2 owns applying the selected set consistently and testing both routes.
- Existing-symbol rejection coverage in `tests/test_data_contract.py` — step 2 owns proving that eligible creation promises do not excuse stale symbols in real files.
- Shared-reader restructuring or changes to roadmap identity authority — separate intentional work if required; this step only composes existing readers.
- Contract documentation and source backlog removal — step 3 owns these after the complete repair is verified.
