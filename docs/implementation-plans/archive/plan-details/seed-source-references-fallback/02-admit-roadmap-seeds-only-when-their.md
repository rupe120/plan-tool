> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Admit roadmap seeds only when their body References cites all accepted artifacts

## Summary

Require each materialized roadmap seed to include a body-level `## References` section that cites `01-domain.md`, `02-constraints.md`, `03-components.md`, and `04-roadmap.md`. Update `plan_tool/prompts/roadmap-seed.md` to ask for that section and extend `plan_tool/roadmap_gates.py:validate_draft_seed_content` to enforce it. Materialization, hand acceptance, and manifest classification already use the validator; batch promotion also captures and validates the exact source bytes it stages after classification. On green, a seed missing any accepted artifact citation retries or refuses before state or promoted seed content changes.

## Table of Contents

- [Summary](#summary) — The change and its green result.
- [Table of Contents](#table-of-contents) — Links to every section.
- [Why](#why) — Why provenance needs visible body evidence.
- [Input](#input) — The seed and roadmap contracts this rule reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed for the prompt, gate, and coverage.
- [Implementation](#implementation) — Required admission behavior and preserved boundaries.
- [Tests](#tests) — Focused regression coverage for every admission path.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Format, template, and test references.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that limit this step.
- [Deferred](#deferred) — Nearby work left out of this step.

## Why

`plan_tool/roadmap_gates.py:validate_draft_seed_content` currently validates only provenance frontmatter and plan-component ownership. That lets a generated or hand-edited seed become current without visible proof that its body used every accepted roadmap artifact. Requiring literal citations in the body’s References section keeps the derived seed tied to the accepted domain, constraints, components, and roadmap artifacts before `plan_tool/roadmap.py:materialize_plan_seed` writes it or `plan_tool/roadmap.py:accept_roadmap_seed` records a hand edit. Batch promotion currently reads a source again after manifest classification, so it must stage only a freshly read body that it validates before promotion.

## Input

- **Draft seed text** — `plan_tool/roadmap_artifacts.py:parse_draft_seed_provenance` owns the leading frontmatter shape, including `roadmap_components` and `cross_cutting`. Keep that contract unchanged.

- **Accepted artifact names** — `plan_tool/roadmap_artifacts.py:DOMAIN_FILENAME`, `CONSTRAINTS_FILENAME`, `COMPONENTS_FILENAME`, and `PLANS_FILENAME` identify the four artifacts a seed must cite.

- **Admission consumers** — `plan_tool/roadmap.py:_materialize_plan_seed`, `plan_tool/roadmap.py:_accept_roadmap_seed`, and `plan_tool/roadmap_seed_manifest.py:classify_draft_seeds` already call `validate_draft_seed_content`. `plan_tool/roadmap.py:_apply_roadmap_seeds` must validate the exact post-classification bytes it stages.

- **Classification order** — `plan_tool/roadmap_seed_manifest.py:classify_draft_seeds` returns `digest-mismatched` before content validation. A changed hand edit therefore reaches the new content rule through `accept_roadmap_seed`; an unchanged invalid draft classifies as `malformed`.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/prompts/roadmap-seed.md` — require `## References` as part of the seed body contract and require citations to every accepted artifact.
  - `plan_tool/roadmap_gates.py` — extend `validate_draft_seed_content` with body-only accepted-artifact reference validation and a clear violation kind and message.
  - `plan_tool/roadmap.py` — capture, validate, and stage one post-classification batch-promotion source snapshot rather than promoting a later reread.
  - `tests/test_roadmap.py` — update compliant seed fixtures and cover prompt, materialization retry, hand-acceptance refusal, batch snapshot refusal, and the real create preflight on successful outputs.
  - `tests/test_roadmap_seed_manifest.py` — update compliant seed fixtures and prove a digest-matching draft without a required citation is `malformed`.
  - `tests/test_roadmap_gates.py` — add this existing direct-validator test file to the step footprint because its `draft_seed_text` fixture and `validate_draft_seed_content` cases define the unit contract.
  - `tests/cli/test_roadmap_cmd.py` and `tests/cli/test_authoring_cmds.py` — update their tracked-draft fixtures with the four accepted artifact citations so existing CLI routing tests continue to model a current, promotable roadmap seed.

## Implementation

- **Require one visible source list.** Update `plan_tool/prompts/roadmap-seed.md` so `References` is an explicit required section rather than conflicting with the current exact-section list. The prompt must require the body’s `## References` section to cite each accepted artifact by its literal filename.

- **Make the gate body-only.** Extend `plan_tool/roadmap_gates.py:validate_draft_seed_content` so a filename in provenance frontmatter or another prose section does not count. A `## References` heading and its content must occur after the leading frontmatter block.

- **Use the accepted artifact constants.** Check the four filename constants in their settled roadmap order rather than duplicating alternate names or discovering artifacts from disk. The rule is a fixed admission predicate, not a general reference system.

- **Report every missing artifact.** Add an explicit violation kind, such as `VIOLATION_MISSING_DRAFT_SEED_ARTIFACT_REFERENCE`, and emit one self-contained violation for each missing filename. Each message must name the owning plan id, draft-seed basename, missing artifact filename, and `References` section so materialization’s retry text can be applied without surrounding context.

- **Preserve existing provenance behavior.** Keep malformed-frontmatter handling, component ownership validation, and the cross-cutting exception intact. The new body rule applies only after provenance parsing succeeds and must not change `DraftSeedProvenance` or roadmap artifact schemas.

- **Keep one admission predicate and one admitted batch snapshot.** `plan_tool/roadmap.py:_materialize_plan_seed`, `plan_tool/roadmap.py:_accept_roadmap_seed`, and `plan_tool/roadmap_seed_manifest.py:classify_draft_seeds` continue to use the existing validator. After its fresh classification, `_apply_roadmap_seeds` reads each target once, validates that exact text against its fresh plan row, and derives the staged promotion from that same text. A failed post-classification validation refuses the batch without creating a destination; do not reread a source after this check.

- **Keep the leaf boundary.** `plan_tool/roadmap_gates.py` must retain its stdlib-plus-`plan_tool.roadmap_artifacts` import boundary. Do not import `plan_tool/scope_fence.py:extract_h2_sections` or add filesystem reads to the gate.

- **Keep prompt substitution unchanged.** `plan_tool/roadmap.py:_render_seed_materialize_prompt` already supplies the accepted artifact bodies. The prompt change must not add an unresolved template placeholder.

## Tests

### Tests for this step

- `tests/test_roadmap_gates.py:test_validate_draft_seed_content_accepts_complete_body_references` — a valid provenance block plus a body References section citing all four accepted filenames returns no violations.

- `tests/test_roadmap_gates.py:test_validate_draft_seed_content_reports_each_missing_accepted_artifact_reference` — parameterized omissions produce one violation per missing accepted artifact and each message names that filename.

- `tests/test_roadmap_gates.py:test_validate_draft_seed_content_does_not_count_frontmatter_or_non_references_mentions` — filenames outside the body References section do not satisfy the admission rule.

- `tests/test_roadmap.py:TestSeedPromptTemplate.test_seed_prompt_requires_references_to_all_accepted_artifacts` — the shipped prompt names `References` and all four accepted filenames while retaining its current placeholder contract.

- `tests/test_roadmap.py:TestMaterializePlanSeed.test_materialize_missing_accepted_artifact_reference_retries_without_writing` — an invalid model reply receives the gate message on retry and an exhausted attempt leaves draft and sidecar state untouched.

- `tests/test_roadmap.py:TestAcceptRoadmapSeed.test_accept_refuses_hand_edit_missing_accepted_artifact_reference` — a digest-mismatched hand edit without a required citation is refused without changing the sidecar or promoted copy.

- `tests/test_roadmap.py:TestRoadmapApply.test_apply_refuses_a_post_classification_reference_regression` — a draft changed after fresh classification but before staging is rejected, with no promoted destination, rather than publishing the reread body.

- `tests/test_roadmap.py:TestMaterializePlanSeed.test_materialized_and_promoted_seed_passes_create_preflight` — successful materialized and promoted bodies pass `plan_tool.create.validate_from_existing_seed`, proving the roadmap gate and create boundary agree.

- `tests/test_roadmap_seed_manifest.py:test_classify_malformed_when_digest_matching_seed_omits_accepted_artifact_reference` — a current-digest draft without one required citation classifies as `malformed` and includes the missing filename in its detail.

- Existing tracked-draft helpers in `tests/cli/test_roadmap_cmd.py` and `tests/cli/test_authoring_cmds.py` include all four accepted artifact references, so their current-state assertions exercise CLI behavior rather than an intentionally malformed draft.

- **Green-before-done gate** — `uv run pytest tests/test_roadmap_gates.py tests/test_roadmap.py tests/test_roadmap_seed_manifest.py -q` must pass.

## Acceptance criteria

- A draft seed passes `plan_tool/roadmap_gates.py:validate_draft_seed_content` only when its valid provenance is accompanied by a body `## References` section that cites all four accepted artifact filenames.

- A missing artifact citation produces one deterministic violation per absent filename, in accepted artifact order.

- A filename in YAML frontmatter or another body section does not satisfy the References requirement.

- `plan_tool/roadmap.py:_materialize_plan_seed` retries an invalid candidate with the violation message and writes neither accepted draft bytes nor current sidecar state for an exhausted first attempt.

- `plan_tool/roadmap.py:accept_roadmap_seed` refuses an invalid hand edit without changing its sidecar entry or promoted seed.

- `plan_tool/roadmap_seed_manifest.py:classify_draft_seeds` marks a digest-matching invalid draft as `malformed`.

- Batch promotion validates and stages one post-classification source snapshot; a later source change cannot be promoted without passing the same gate.

- Successful materialized and promoted roadmap seeds pass `plan_tool.create.validate_from_existing_seed`.

- The focused pytest command passes.

## References

- [CommonMark Spec — ATX headingshttps: — Use this for the accepted `## References` heading form.

- [Python 3.13 — Regular expression operationshttps: — Use this for body-heading and artifact-name matching.

- [Python 3.13 — Template stringshttps: — Use this for the roadmap seed prompt’s substitution rules.

- [pytest — Parametrizing testshttps: — Use this for one case per missing accepted artifact.

- [pytest — Temporary directorieshttps: — Use this for isolated materialization, acceptance, and manifest-state tests.

## Applicable guardrails

- **The plan’s “## Plan intent”.** Keep this step focused on making roadmap seeds valid inputs for their existing authoring route; do not change that route’s broader behavior.

- **The plan’s “## Step intent”.** Use the existing draft-seed admission rule for generated, accepted, and classified seeds while preserving separate roadmap-provenance validation.

- **The plan’s “## Out of scope”.** Limit the work to this References admission rule and its focused tests; do not expand adjacent authoring, routing, or seed-contract surfaces.

## Deferred

- **Shared Markdown-section extraction** — Consolidating `plan_tool/roadmap_gates.py` body handling with `plan_tool/scope_fence.py:extract_h2_sections` changes a shared ownership boundary and belongs in a separate reconcile or refactor step.

- **Reference quality beyond accepted-artifact citation** — URL validity, source-content quality, and new mandatory body sections remain outside this fixed admission predicate.
