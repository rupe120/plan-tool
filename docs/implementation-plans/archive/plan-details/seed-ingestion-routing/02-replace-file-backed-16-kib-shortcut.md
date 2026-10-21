> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Replace the file-backed 16 KiB shortcut with a source-authoritative direct route that performs one raw-only split check and bypasses generic post-write convergence

## Summary

Route a direct-ready file-backed source through one raw-source split assessment in `plan_tool/create.py`. Keep its body and References source-backed, preserve the existing `SplitProposal` handoff, and bypass `_converge_create_plan` after publication. Clarify in `plan_tool/distill_thresholds.py` and `plan_tool/split_criteria.py` that the 16 KiB shortcut remains an inline compatibility rule, not a file-backed routing rule. On green, a direct source either publishes without generic body or References authoring, returns the existing split result, or fails before writing anything.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the direct route and its result.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — The size-based branch and generic authoring paths this step replaces.
- [Input](#input) — The classifier result and existing create contracts this route reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files this step changes.
- [Implementation](#implementation) — Direct routing, split assessment, and convergence boundaries.
- [Tests](#tests) — Focused coverage for direct, split, invalid, and inline paths.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Invocation and test-fixture references.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain the route.
- [Deferred](#deferred) — Lifecycle and preparation work owned by later steps.

## Why

`plan_tool/create.py:_prepare_create_plan` currently treats a small canonical source as a reason to skip `propose_distilled_seed_from_claude`, so source size decides whether split assessment runs. The remaining generic References and convergence paths can then replace or edit content that a file-backed source already supplied. The direct route needs to make one deliberate single-versus-split decision from the selected raw source, then publish the single-plan result without model-authored body or References content.

## Input

- **Step 1 intake result:** Consume step 1’s file-backed classification and any lifted strict `Step` graph. Direct readiness comes from that result, not from a second heading scan or source-size check.
- **Selected source text:** Consume step 1’s shared selected-source value — `seed_body` when present, otherwise `from_description` — as the sole raw input to the direct assessment and publication path. Do not add a truthiness fallback.
- **Existing split handoff:** Reuse `plan_tool/create.py:SplitProposal`, `plan_tool/create.py:SplitProposalEntry`, and `plan_tool/create.py:_validate_split_plans` for a multi-plan result.
- **Publication boundary:** `plan_tool/create.py:create_plan` currently publishes through `_publish_create_plan` and then invokes `_converge_create_plan`; direct state must reach this boundary so the latter call is skipped.
- **Inline compatibility:** Calls without `from_existing_path` retain their existing `distill` behavior, including the inline small-canonical skip.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/create.py` — dispatch direct-ready file-backed sources, run the raw split assessment, preserve raw source sections, and bypass generic convergence.
  - `plan_tool/distill_thresholds.py` — state the remaining scope of the 16 KiB and large-seed thresholds accurately.
  - `plan_tool/split_criteria.py` — render altitude-1 guidance without presenting the inline 16 KiB rule as a file-backed direct-route decision.
  - `tests/test_create.py` — add public create-path coverage for raw authority, strict steps, invalid assessments, and convergence bypass.
  - `tests/test_distill.py` — update distill-threading coverage for direct routing and retain the inline compatibility case.
  - `tests/test_split_criteria.py` — pin the revised threshold and legend meaning.

## Implementation

- **Foundational logic:** Dispatch a direct-ready file-backed source through one raw-only single-versus-split assessment.

- **Select the direct route before distillation.** In `plan_tool/create.py:_prepare_create_plan`, branch from step 1’s direct-ready result only when `from_existing_path` is present. This branch must not depend on `distill`, source length, or a reclassification of transformed text. Inline inputs and file-backed inputs that need preparation stay on their existing or later-owned paths.

- **Make one decision call.** Add a narrow direct-assessment path near `plan_tool/create.py:propose_distilled_seed_from_claude`. One approach is a small helper whose single result means only “one plan” and whose split result uses the existing split entry contract. The assessment must receive the selected raw source and must not return or apply replacement body sections.

- **Fail closed after one invalid decision.** A malformed, schema-invalid, or non-decision assessment must stop create before plan or manifest publication. Do not retry, use `DistillOutcome.is_passthrough`, or route the source into preparation: each would turn an untrusted split decision into an unprotected direct publication.

- **Reuse the existing split shape.** A split result must become the existing `CreateResult.split_proposal` path, with no plan or manifest write. Keep `SplitProposal` and `_validate_split_plans` as the shared authority for proposal entries rather than creating a second split representation.

- **Keep source prose authoritative on a single result.** Preserve the raw source-backed `seed_sections`, including `## References`, through `write_new_plan`. Skip generic `propose_references_from_claude` and `propose_body_sections` on this route, since either can take precedence over supplied prose in `plan_tool/create.py:_render_plan_body`.

- **Keep strict steps independent.** Use the lifted graph from step 1 when it exists. When it is absent, retain `plan_tool/create.py:propose_steps_from_claude` only to build required frontmatter; it must not change the direct source’s body or References route.

- **Skip generic post-write convergence.** Carry direct-route state from `PreparedCreatePlan` to `plan_tool/create.py:create_plan` and bypass `_converge_create_plan` even when `IterativeBudget.enabled` is true. Keep the normal publication and finalization path intact; this step does not add lifecycle cleanup.

- **Fence every remaining create writer.** Carry a direct source-authority
  envelope containing its complete raw canonical body and References through
  publish and finalization. Do not let scope-decision rendering, concept
  synchronization, or finalization persistence replace those ranges. A writer
  that proposes a protected-range change restores the source range and reports
  no successful direct mutation; frontmatter, manifest, and other non-body
  bookkeeping remain allowed.

- **Limit the threshold change to its real reach.** Keep `plan_tool/distill_thresholds.py:DISTILL_SKIP_BELOW_BYTES` as an inline compatibility rule if inline distillation still consumes it, but direct file-backed routing must never read it. Keep `DISTILL_ADVISE_ABOVE_BYTES` limited to conventional preparation advice.

- **Keep the split legend truthful.** Update `plan_tool/split_criteria.py:SPLIT_CRITERIA`, `_reference_lines`, and `_altitude1_result` so the rendered explanation distinguishes inline threshold behavior from the file-backed direct assessment. Preserve the existing `distill-oversize` identifier and its read-only role.

- **Leave the CLI handoff unchanged here.** `plan_tool/cli/authoring.py:cmd_create` already consumes `CreateResult.split_proposal`; step 5 owns route reporting and exit wording, so this step must not change that file.

## Tests

### Tests for this step

- `test_direct_split_assessment_accepts_only_single_or_valid_split` — a direct assessment accepts a single decision or existing valid split entries, and rejects replacement body content or malformed decisions.
- `test_direct_single_assesses_the_selected_raw_source_once` — a direct-ready file-backed source reaches exactly one assessment with the original selected source text.
- `test_direct_single_preserves_source_body_and_references_without_generic_authoring` — published direct content keeps the supplied body and References while generic References and body authoring remain uncalled.
- `test_direct_single_uses_lifted_strict_steps_without_step_proposal` — a strict graph from step 1 reaches frontmatter without `propose_steps_from_claude`.
- `test_direct_single_uses_step_proposal_only_when_strict_steps_are_absent` — an otherwise direct source with no liftable graph uses the existing step proposal without entering preparation.
- `test_direct_split_returns_existing_proposal_without_plan_or_manifest` — a split assessment returns `SplitProposal` and produces neither a plan nor a manifest entry.
- `test_direct_invalid_assessment_fails_closed_after_one_call` — an invalid assessment makes one call, writes nothing, and cannot fall back to distillation or preparation.
- `test_direct_single_bypasses_convergence_when_iteration_is_enabled` — direct publication never calls `_converge_create_plan` or its post-write authoring paths.
- `test_direct_source_authority_survives_scope_and_concept_sync` — approved
  concept decisions cannot replace a direct source’s canonical body or
  References during initial publication or finalization.
- `test_inline_small_canonical_seed_retains_distill_flag_compatibility` — a non-file-backed canonical source keeps its existing small-seed distill behavior.
- `test_altitude_one_guidance_distinguishes_inline_thresholds_from_direct_assessment` — the split-criteria legend does not present the 16 KiB value as a direct file-backed route decision.

Every listed test in `tests/test_create.py`, `tests/test_distill.py`, and `tests/test_split_criteria.py` must be green before this step is complete.

## Acceptance criteria

- A direct-ready source with `from_existing_path` receives one raw-only single-versus-split assessment regardless of its byte length or `distill` value.
- A single direct assessment publishes one plan and manifest entry with source-backed body and References content.
- A strict graph from step 1 skips step proposal; an absent graph does not make the source leave the direct route.
- A split result returns the existing `SplitProposal` shape and writes no plan or manifest entry.
- An invalid direct assessment performs no preparation fallback, no retry, and no durable create-side write.
- Direct publication bypasses `plan_tool/create.py:_converge_create_plan`, including when iteration is enabled.
- Direct source authority persists through every create-owned scope and concept
  writer; only later operator-directed plan workflows may revise that body.
- Inline inputs retain their existing `distill` behavior.
- `plan_tool/split_criteria.py:render_split_criteria` describes threshold scope without claiming that 16 KiB selects a file-backed direct route.
- `uv run pytest tests/test_create.py tests/test_distill.py tests/test_split_criteria.py -q` passes.

## References

- [Claude Code CLI referencehttps: — Check the non-interactive invocation contract used by the single direct assessment.
- [pytest — How to use temporary directories and files in testshttps: — Use hermetic source files and no-write assertions for direct, split, and refusal paths.
- [Python enum — Support for enumerationshttps: — Use the existing closed route vocabulary without expanding it.

## Applicable guardrails

- **The plan’s “## Plan intent”, supplied-source authority:** keep the direct branch limited to preserving the selected source through publication; it must not accept model-authored replacement prose.
- **The plan’s “## Step intent”, deliberate pre-write decision:** make the raw split assessment the direct route’s only new decision surface and bypass generic post-write edits.
- **The plan’s “## Out of scope”, validation boundary:** consume step 1’s classifier result without broadening source validation or heading recognition.
- **The plan’s “## Out of scope”, split delivery boundary:** continue using the in-create `SplitProposal` path and do not create another command or split system.
- **The plan’s “## Out of scope”, authoring-contract boundary:** leave shared step, References-research, and body-synthesis contracts unchanged except where the direct route must skip them.

## Deferred

- Preparation result contract — step 3 owns normalized and refused preparation outcomes; this step must not use preparation as a fallback for an invalid direct assessment.
- Terminal route lifecycle (`22a740fdbaa54ae54299f4be8f7189fd05c322dc42e247bba3ec3e71d1b4abdc`) — steps 5 and 6 own operator reporting, checkpoints, archival, and final exit behavior; this step adds no lifecycle policy.
