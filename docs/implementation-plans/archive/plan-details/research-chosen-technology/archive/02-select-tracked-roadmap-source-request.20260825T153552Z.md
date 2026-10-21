> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Select a tracked roadmap source and request source evidence for every recorded product row

## Summary

Extend `plan_tool/create.py` so a tracked `--from-existing` roadmap seed supplies the initial References research targets. Build one immutable snapshot of named hosting and store products, then require the research response to return a separate source verdict for every snapshot target. Keep the current generic References path for all other create origins. On green, every recorded product row has distinct source evidence available for step 3 without changing the rendered References location.

## Table of Contents

- [Summary](#summary) — Scope and expected green result.
- [Table of Contents](#table-of-contents) — Quick links to this detail.
- [Why](#why) — Why generic research cannot prove coverage of roadmap products.
- [Input](#input) — Source, artifact, and existing research contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed by the step.
- [Implementation](#implementation) — Source-selection and per-row evidence rules.
- [Tests](#tests) — Focused regression coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — External contracts for the research protocol and tests.
- [Applicable guardrails](#applicable-guardrails) — Scope limits that bind this step.
- [Deferred](#deferred) — Later work deliberately left to step 3.

## Why

`plan_tool/create.py:_build_research_context` currently gives generic References research a title, steps, and seed prose, but no durable connection to a chosen roadmap product. `plan_tool/roadmap_seed_state.py:locate_tracked_seed` can identify a tracked seed and its roadmap, yet `plan_tool/create.py:_prepare_create_plan` does not use that identity to bind research results to rows. This step makes product coverage observable before step 3 adds the hard refusal.

## Input

- **Step 1 row metadata:** step 1 supplies optional descriptions on `plan_tool/roadmap_artifacts.py:HostingRow` and `plan_tool/roadmap_artifacts.py:StoreRow`. Preserve each row’s field origin and description in this step’s snapshot; do not judge description content here.

- **Tracked source identity:** `plan_tool/roadmap_seed_state.py:locate_tracked_seed` returns `TrackedSeedLocation` with the roadmap slug and sidecar path. `plan_tool/cli/authoring.py:_confirm_invalidated_roadmap_seed` already performs the stale-seed confirmation before calling `create`; this step consumes that accepted identity and adds no second prompt.

- **Roadmap artifacts:** `plan_tool/roadmap_artifacts.py:load_constraints_artifact` and `plan_tool/roadmap_artifacts.py:load_components_artifact` load the two selected artifacts. Their `ConstraintsArtifact.hosting` and `ComponentsArtifact.stores` tuples preserve source order, which the target identity needs.

- **Existing References flow:** `plan_tool/create.py:Reference`, `_REFERENCE_RESPONSE_CONTRACT`, `_render_references_prompt`, `_parse_references_json`, and `propose_references_from_claude` own today’s generic request, decoding, checkpointing, and rendered-reference behavior.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/create.py` — Select tracked roadmap inputs, retain per-row targets and verdicts through pre-publication preparation, request a strict per-target response, and include the selected snapshot in the References checkpoint key.
  - `plan_tool/cli/authoring.py` — Resolve and carry an accepted tracked-seed location before seed-driven repository-root relocation changes the publication root.
  - `tests/test_create.py` — Cover tracked-source selection, target identity, strict response handling, checkpoint invalidation, and unchanged generic behavior.
  - `tests/cli/test_direct_cmd.py` — Cover a promoted tracked seed whose marker remains rooted in the source repository while its seed paths relocate authoring to a sibling repository.

## Implementation

- **Foundational logic:** map every trimmed, named roadmap product row to exactly one source-evidence verdict.

- **Resolve before relocation and carry identity:** when `from_existing_path` is present, resolve `TrackedSeedLocation` against the initially resolved root before `plan_tool/cli/authoring.py:find_umbrella_root` can relocate the repository. After stale-seed confirmation accepts it, pass that immutable location — including its absolute sidecar path, roadmap slug, and plan id — into `create_plan` / `_prepare_create_plan`. Do not call `locate_tracked_seed` a second time against the relocated publication root, and do not infer a roadmap from a filename, seed prose, or an inline `--from` value.

- **Keep stale-seed handling in its current owner:** rely on `plan_tool/cli/authoring.py:_confirm_invalidated_roadmap_seed` having accepted the source. Do not duplicate its confirmation or add an interactive branch in `plan_tool/create.py`.

- **Load one snapshot before research:** derive the roadmap root from the tracked sidecar and load the artifacts named by `plan_tool/roadmap_artifacts.py:CONSTRAINTS_FILENAME` and `COMPONENTS_FILENAME` through their existing loaders. A selected artifact that cannot be read or parsed must stop this path with its artifact error; never fall back to generic seed prose after selection succeeds.

- **Create a target for each named row:** walk `ConstraintsArtifact.hosting` first and `ComponentsArtifact.stores` second, in their existing tuple order. Include a target only when `product.strip()` is non-empty. Carry the trimmed product, the row’s optional description from step 1, and an origin that identifies the artifact, collection, source-order position, and row id.

- **Keep row identity separate from product text:** give every target a stable token based on its collection and source-order position. Do not key targets or verdicts by product string or row id: repeated products and duplicate row ids must remain separate records.

- **Use a strict product-research protocol:** extend `plan_tool/create.py:_render_references_prompt` and `propose_references_from_claude`, or add a private helper beside them, so a selected snapshot asks for one tagged result per target. Each result identifies one requested token and carries either decoded `Reference` values or an explicit empty source list; keep the individual reference shape and URL rules aligned with `Reference`.

- **Reject protocol defects, not empty evidence:** reject an unparseable response, an invalid member of a non-empty source list, and any missing, duplicate, or foreign target record before publication. A member is invalid when it cannot decode as `Reference` under the existing title, URL, and description rules. An explicit empty source list is the only no-source verdict step 3 evaluates; it is not a parse failure and does not silently disappear.

- **Retain both views of the result:** keep the selected snapshot and per-target verdicts in the pre-publication state that step 3 will consume. Flatten valid decoded references only for the existing References renderer, so rendering does not discard the row-to-verdict link.

- **Preserve generic behavior:** leave `_REFERENCE_RESPONSE_CONTRACT` and the legacy request shape in place for inline, interactive, and untracked `--from-existing` creates. A tracked roadmap with no named products also uses that existing generic path and creates no product verdict.

- **Invalidate only selected-source checkpoints:** update `plan_tool/create.py:_references_input_hash` and its `propose_references_from_claude` call path so the selected snapshot’s tokens, products, origins, and descriptions affect the References checkpoint. Keep the legacy hash unchanged when no snapshot is selected, so existing generic cache reuse remains valid.

## Tests

### Tests for this step

- `tests/test_create.py:test_tracked_roadmap_source_selects_hosting_and_store_products_in_source_order` — A tracked `--from-existing` seed loads both artifact rows and creates targets in hosting-then-store order.

- `tests/test_create.py:test_roadmap_research_target_trims_products_and_preserves_row_origin_and_description` — Whitespace-only products create no target, while a named product retains its trimmed value, origin, and step-1 description.

- `tests/test_create.py:test_roadmap_research_target_tokens_keep_duplicate_products_and_row_ids_distinct` — Repeated product strings and duplicate row ids produce separate stable tokens and separate target records.

- `tests/test_create.py:test_tracked_roadmap_research_prompt_requests_one_tagged_result_per_target` — The selected research prompt contains each requested token and enough row context to return a matching verdict.

- `tests/test_create.py:test_tracked_roadmap_research_rejects_missing_duplicate_and_foreign_target_records` — Each incomplete or mismatched response is a protocol failure rather than an empty-source verdict.

- `tests/test_create.py:test_tracked_roadmap_research_rejects_invalid_reference_members` — A non-empty source list with an invalid title, URL, or description member is a protocol failure rather than a description-fallback candidate.

- `tests/test_create.py:test_tracked_roadmap_research_accepts_explicit_empty_source_list` — A complete response with an empty list for one target remains a valid per-row verdict for the next step.

- `tests/test_create.py:test_tracked_roadmap_artifact_failure_does_not_fall_back_to_generic_research` — A selected artifact read or parse failure stops before the research invoker runs.

- `tests/test_create.py:test_untracked_and_no_product_sources_keep_generic_references_research` — Untracked, inline, interactive, and no-product tracked sources retain the existing generic request and produce no product-target protocol.

- `tests/test_create.py:test_references_checkpoint_hash_changes_with_roadmap_snapshot_but_not_legacy_input` — Changing a selected row’s target data invalidates its cached response, while a legacy request retains its existing checkpoint key.

- `tests/cli/test_direct_cmd.py:test_relocated_promoted_tracked_seed_keeps_original_roadmap_research` — A promoted marker relative to the source root, whose seed triggers sibling-root relocation, still sends its original roadmap products through the per-target request rather than the generic path.

**Green-before-done:** every listed test and the existing References parsing, rendering, and checkpoint tests in `tests/test_create.py` are green before this step is complete.

## Acceptance criteria

- A tracked `--from-existing` source selects one readable constraints artifact and one readable components artifact before product research begins.

- Seed-driven repository-root relocation preserves the already accepted `TrackedSeedLocation`; it changes the publication root but never silently degrades a promoted seed to generic research.

- Every trimmed, non-empty hosting or store product produces one target containing a stable token, its product value, field origin, and optional description.

- Duplicate product strings and duplicate row ids remain separate targets and cannot share a source verdict.

- A selected response has exactly one result for every requested target; missing, duplicate, foreign, unparseable, and invalid-reference-member results stop before publication.

- An explicit empty source list remains a valid verdict, while valid decoded references continue to render through the existing References body path.

- Inline, interactive, untracked, and no-product tracked creates retain the current generic References request behavior.

- Changing a selected roadmap snapshot invalidates its References checkpoint without changing the checkpoint key for a legacy request.

- `uv run pytest tests/test_create.py -q` passes.

## References

- [Claude Code CLI reference](https://code.claude.com/docs/en/cli-usage) — Review non-interactive invocation and structured-output behavior for the research subprocess.

- [Claude Code Tools reference](https://code.claude.com/docs/en/tools-reference) — Review WebSearch behavior and permissions that produce source evidence.

- [json — JSON encoder and decoder](https://docs.python.org/3.13/library/json.html) — Review strict JSON decoding and error handling for the per-target response.

- [How to monkeypatch/mock modules and environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Review hermetic ways to stub the research invoker and tracked-source inputs.

## Applicable guardrails

- **The plan’s “## Plan intent,” source-grounded research:** make research evidence follow the technologies the selected roadmap records; do not substitute broader plan prose for those targets.

- **The plan’s “## Step intent,” row fidelity:** retain each target’s field origin, optional fallback description, and repeated-product identity through the research result.

- **The plan’s “## Out of scope,” existing roadmap contracts:** consume the hosting and store artifacts without redesigning their schema, vocabularies, or gates.

- **The plan’s “## Out of scope,” research boundary:** limit this work to technology products in the selected roadmap and leave other research domains alone.

- **The plan’s “## Out of scope,” execution lanes:** keep the change in `create`; do not thread this evidence into later commands.

## Deferred

- `plan_tool/create.py:_converge_create_plan` roadmap-specific iteration behavior — step 3 owns preserving accepted References and preventing a later re-research call.

- Hard refusal for a valid empty verdict without a usable description — step 3 owns the decision, message, and checkpoint-retention behavior.
