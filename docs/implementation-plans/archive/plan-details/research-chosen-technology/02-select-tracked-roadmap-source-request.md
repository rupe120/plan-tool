> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Select a tracked roadmap source and request source evidence for every recorded product row

## Summary

Extend `plan_tool/create.py` so a tracked `--from-existing` roadmap seed supplies product-specific References research targets. Build one immutable snapshot of named hosting and store products, then require one source verdict for every target explicitly marked for external research. Local and unmarked targets remain in-process and use their recorded description without an outbound request. Keep the current generic References request for every other create origin. On green, step 3 receives separate, traceable evidence for every recorded product row.

## Table of Contents

- [Summary](#summary) — Scope and green result.
- [Table of Contents](#table-of-contents) — Quick links.
- [Why](#why) — Why generic research cannot prove product coverage.
- [Input](#input) — Source and research contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed by this step.
- [Implementation](#implementation) — Source selection and per-row evidence rules.
- [Tests](#tests) — Regression coverage for the new research path.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — External contracts for the research protocol.
- [Applicable guardrails](#applicable-guardrails) — Boundaries that apply here.
- [Deferred](#deferred) — Work owned by later steps.

## Why

`plan_tool/create.py:_build_research_context` gives generic References research plan and seed prose, but no durable link to a roadmap product. `plan_tool/roadmap_seed_state.py:locate_tracked_seed` can identify a tracked seed and its roadmap, yet `plan_tool/create.py:_prepare_create_plan` does not use that identity to bind research evidence to rows. This step makes product coverage observable before step 3 decides whether a valid empty verdict blocks publication.

## Input

- **Step 1 outcome:** step 1 provides the optional operator description and `research_disclosure` beside each hosting or store product. Preserve both locally in the target snapshot without judging their content or passing an unapproved product to research.

- **Tracked seed identity:** `plan_tool/roadmap_seed_state.py:locate_tracked_seed` returns `TrackedSeedLocation`; `plan_tool/cli/authoring.py:_confirm_invalidated_roadmap_seed` consumes that already-resolved location for stale-seed confirmation.

- **Roadmap artifacts:** `plan_tool/roadmap_artifacts.py:load_constraints_artifact` and `plan_tool/roadmap_artifacts.py:load_components_artifact` provide the ordered `ConstraintsArtifact.hosting` and `ComponentsArtifact.stores` rows. Use `plan_tool/roadmap_artifacts.py:constraints_path` and `plan_tool/roadmap_artifacts.py:components_path` to locate them.

- **Existing References flow:** `plan_tool/create.py:Reference`, `plan_tool/create.py:_render_references_prompt`, `plan_tool/create.py:_parse_references_json`, `plan_tool/create.py:propose_references_from_claude`, and `plan_tool/create.py:_references_input_hash` own the current request, response, rendering, and checkpoint behavior.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/create.py` — Add selected-roadmap targets, per-target source verdicts, strict product-mode response handling, and selected-snapshot checkpoint identity.
  - `plan_tool/cli/authoring.py` — Resolve and carry the accepted tracked-seed identity before repository-root relocation.
  - `tests/test_create.py` — Cover selection, target identity, response validation, checkpoint invalidation, and legacy behavior.
  - `tests/cli/test_direct_cmd.py` — Cover a promoted tracked seed whose create root relocates to a sibling repository.
  - `tests/cli/test_authoring_cmds.py` — Cover one-time tracked-source resolution across stale-seed confirmation and creation.

## Implementation

- **Foundational logic:** map every trimmed, recorded roadmap product row to exactly one source-evidence verdict.

- **Resolve once before relocation:** in `plan_tool/cli/authoring.py:cmd_create`, resolve `TrackedSeedLocation` from `plan_tool/roadmap_seed_state.py:locate_tracked_seed` once against the initially selected repository root. Pass that exact location to `plan_tool/cli/authoring.py:_confirm_invalidated_roadmap_seed` and, after it admits the source, to `plan_tool/create.py:create_plan` and its preparation path.

- **Do not re-resolve the source:** no confirmation or preparation helper calls `locate_tracked_seed` after `cmd_create` selects the location. `plan_tool/cli/authoring.py:find_umbrella_root` may change where the plan publishes, but must not change which accepted roadmap supplies product evidence. A marker or sidecar locator changed after selection therefore cannot alter the approved source. Do not infer a roadmap from the filename, seed prose, or an inline `--from` value.

- **Load a fixed source snapshot before research:** derive the selected roadmap root from the carried location, then load the constraints and components artifacts with their existing loaders. A selected artifact that cannot be read or parsed must fail this path before the research invoker runs; do not fall back to generic seed-prose research after selection succeeds.

- **Create one target per named row:** walk hosting rows first, then store rows, using their existing tuple order. Include only products whose trimmed value is non-empty. Each target retains its trimmed product, optional step-1 description, disclosure decision, and an origin that identifies the artifact, collection, row position, and row id.

- **Keep identity independent of text:** use a stable target token based on the row’s collection and source position. Do not key targets or verdicts by product text or row id: repeated products and duplicate row ids remain separate targets.

- **Fail closed per target:** only `research_disclosure: external` makes a target requestable. A `local` or omitted disclosure creates a deterministic local no-source result and never renders its product literal into an external or generic prompt. It requires a nonblank description; otherwise raise `CreateError` before the invoker runs, naming its local origin and asking for a description or explicit external disclosure.

- **Keep private target metadata local:** an external target sends only its stable token and trimmed product literal. It never renders an operator description, origin, row id, row position, roadmap path, sidecar path, raw artifact, or local/unmarked product into the external prompt. Keep those fields in the target snapshot for cache identity, diagnostics, and step 3's local refusal.

- **Use a product-mode response contract:** extend the References request near `plan_tool/create.py:_render_references_prompt` and `plan_tool/create.py:propose_references_from_claude`, or add a focused private helper beside them. The selected path requests exactly one tagged result per external target; each result contains its requested token and either valid `Reference` values or an explicit empty source list. Local no-source results are derived without a response record. The prompt's product list has no other target metadata.

- **Treat protocol defects as errors:** a malformed response, missing, duplicate, or foreign external-target result, or an invalid member of a non-empty source list is a research-protocol failure before publication. Do not use the generic `plan_tool/create.py:_parse_references_json` behavior that drops malformed entries silently for this selected mode. An explicit empty list is the only valid external no-source verdict; a local result is derived separately and remains available for step 3.

- **Preserve both result views:** retain the immutable target snapshot and per-target verdicts in the prepared create state for step 3. Flatten only validated `Reference` values for the existing References renderer, so rendering never loses the row-to-verdict relationship.

- **Keep legacy behavior unchanged:** inline, interactive, and untracked `--from-existing` creates keep the existing generic request and response contract. A tracked roadmap with no named products also takes that generic path and creates no product verdicts. A tracked roadmap with named local/unmarked products never falls back to generic research; if all targets are local and described, it makes no research invocation.

- **Make selected evidence part of cache identity:** update `plan_tool/create.py:_references_input_hash` and the selected call path so target tokens, products, origins, descriptions, and disclosure decisions invalidate stale selected-source responses. Preserve the legacy hash input when no snapshot is selected.

## Tests

### Tests for this step

- `test_tracked_roadmap_source_selects_hosting_and_store_products_in_source_order` — A tracked source produces hosting targets before store targets.

- `test_roadmap_research_target_trims_products_and_preserves_origin_description_and_disclosure` — Whitespace-only products create no target; named products retain trimmed text, local origin, step-1 description, and disclosure decision.

- `test_roadmap_research_target_tokens_keep_duplicate_products_and_row_ids_distinct` — Repeated product text and duplicate ids produce separate target records and verdict slots.

- `test_tracked_roadmap_research_prompt_requests_only_external_targets` — The selected request contains every external token and product literal, but no description, origin, row metadata, roadmap/sidecar path, or local/unmarked product.

- `test_local_or_unmarked_target_requires_description_without_invoking_research` — A local/unmarked product without a nonblank description fails before the invoker runs; a description-backed local product yields a local no-source result.

- `test_all_local_targets_skip_research_without_generic_fallback` — A selected roadmap of described local products makes no external or generic references call.

- `test_tracked_roadmap_research_rejects_missing_duplicate_and_foreign_target_records` — Incomplete or mismatched records fail as protocol errors rather than empty evidence.

- `test_tracked_roadmap_research_rejects_invalid_reference_members` — A malformed member in a non-empty source list cannot become a description-fallback verdict.

- `test_tracked_roadmap_research_accepts_explicit_empty_source_list` — A complete response with an empty list remains a valid verdict for step 3.

- `test_tracked_roadmap_artifact_failure_does_not_fall_back_to_generic_research` — An unreadable or malformed selected artifact stops before the invoker runs.

- `test_untracked_and_no_product_sources_keep_generic_references_research` — Inline, interactive, untracked, and no-product tracked sources keep the existing generic behavior.

- `test_references_checkpoint_hash_changes_with_roadmap_snapshot_but_not_legacy_input` — A changed description or disclosure decision invalidates selected research without changing legacy cache keys.

- `test_relocated_promoted_tracked_seed_keeps_original_roadmap_research` — A promoted seed retains its original tracked roadmap when authoring relocates to a sibling repository.

- `test_tracked_seed_location_is_resolved_once_before_confirmation_and_create` — A marker or sidecar locator changed after initial selection cannot make stale-seed confirmation and creation consume different roadmaps.

Every listed test and the affected existing References parsing, rendering, and checkpoint tests in `tests/test_create.py` must be green before this step is complete.

## Acceptance criteria

- A tracked `--from-existing` source loads its constraints and components artifacts before product research starts.

- Repository-root relocation preserves the accepted tracked-source identity, and stale-seed confirmation consumes the same location without a second lookup or a fallback to generic research.

- Every trimmed, non-empty hosting or store product produces one target with a stable token, product value, field origin, optional description, and disclosure decision. Only an external target's token and product literal reach the external request.

- Duplicate product strings and duplicate row ids remain separate targets and cannot share a verdict.

- A local or unmarked target never sends its product literal to research and requires a nonblank description; failure to provide one stops before the invoker runs. A fully local, description-backed selected source skips research rather than falling back to generic seed-prose research.

- A selected response has exactly one valid result for every requested external target; malformed, missing, duplicate, foreign, and invalid-member results stop before publication. Described local/unmarked targets receive their deterministic local no-source result instead.

- An explicit empty source list remains a valid per-target verdict, while valid decoded references use the current References body renderer.

- Inline, interactive, untracked, and no-product tracked creates retain the generic References request.

- Changing a selected source snapshot invalidates its References checkpoint without changing the legacy checkpoint key.

- `uv run pytest tests/test_create.py -q` passes.

## References

- [Claude Code CLI referencehttps: — Review non-interactive invocation and structured-output behavior for the research subprocess.

- [Claude Code Tools referencehttps: — Review WebSearch behavior and permissions that produce source evidence.

- [json — JSON encoder and decoderhttps: — Review JSON decoding and failure handling for the per-target response.

- [How to monkeypatch/mock modules and environmentshttps: — Review hermetic invoker and filesystem stubbing for this path.

## Applicable guardrails

- **The plan’s “## Plan intent,” source-grounded research:** select recorded roadmap technologies as the product-research inputs; do not replace them with inferred prose terms.

- **The plan’s “## Step intent,” row fidelity:** preserve field origin, optional fallback description, and repeated-product identity through the returned verdicts.

- **The plan’s “## Out of scope,” roadmap contracts:** consume hosting and store artifacts without redesigning their schema, vocabularies, or gates.

- **The plan’s “## Out of scope,” research boundary:** limit product targets to recorded technology fields and do not expand this work into other roadmap facts or framework-lens behavior.

- **The plan’s “## Out of scope,” execution lanes and offline operation:** keep this behavior in `create`’s existing online research path; do not thread it into later commands or add an offline alternative.

## Deferred

- `plan_tool/create.py:_converge_create_plan` roadmap-specific iteration behavior — step 3 owns preserving accepted References and preventing a later research request from replacing them.

- Hard refusal for a valid empty verdict without a usable description — step 3 owns the decision, message, and checkpoint-retention behavior.
