> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Classify every file-backed source at the create intake seam with unique normalized direct-ready headings, References preflight, and strict-steps properties

## Summary

Add a deterministic file-backed source classifier in `plan_tool/create.py` and cover it in `tests/test_create.py`. The intake separates unmatched-fence input safety, References evidence preflight, direct-ready body shape, and strict `## Steps` lifting into independent facts. It normalizes canonical heading case and an optional closing ATX sequence, ignores frontmatter and fenced examples, and preserves the existing strict step reader. On green, a file-backed source has one stable intake result before any authoring work begins.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the intake classifier and its result.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — The current ambiguity at the file-backed create boundary.
- [Input](#input) — Source text, heading, and strict-step contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed by this step.
- [Implementation](#implementation) — Required intake classification behavior and boundaries.
- [Tests](#tests) — Test cases that pin the classifier and preflight behavior.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary syntax and test-fixture references.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that limit this step.
- [Deferred](#deferred) — Later routing and lifecycle work.

## Why

`plan_tool/create.py:validate_from_existing_seed` currently proves only that one usable References section can be extracted, while `plan_tool/scope_fence.py:extract_h2_sections` intentionally keeps the first duplicate and cannot state whether the rest of the source is ready to preserve as supplied. `plan_tool/create.py:_prepare_create_plan` therefore has no one deterministic answer for duplicate required evidence, incomplete canonical body headings, or whether `plan_tool/create.py:extract_steps_from_canonical` can lift the graph without a proposal. The intake must expose those facts before later work selects direct publication or visible preparation.

## Input

- **File-backed boundary:** Apply this only when `plan_tool/create.py:create_plan` receives `from_existing_path`; inline `--from` prose remains outside this classifier.
- **Selected raw source:** Select `seed_body` when it is not `None`, otherwise `from_description`, once at the file-backed intake seam. Classify those exact original bytes rather than a distilled or synthesized replacement; an empty `seed_body` never falls through to a non-empty description.
- **Heading semantics:** Reuse `plan_tool/scope_fence.py:_strip_frontmatter`, `plan_tool/scope_fence.py:_fenced_code_spans`, and `plan_tool/scope_fence.py:_is_placeholder_section` so frontmatter and fenced examples do not count as source evidence.
- **Strict steps:** Reuse `plan_tool/create.py:extract_steps_from_canonical`, backed by `plan_tool/canonical.py:extract_canonical_steps`, as the sole strict graph reader. A `None` result means the graph is not liftable, not that the body requires normalization.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/create.py` — add the typed file-backed intake result and normalized-heading classifier; make `validate_from_existing_seed` and `_prepare_create_plan` use that one source of truth.
  - `tests/test_create.py` — add classifier, duplicate-heading, preflight-order, and strict-step independence coverage.

## Implementation

- **Foundational logic:** Classify a file-backed source into a References-preflight verdict, a direct-ready body verdict, and an independent strict-steps result.

- **Use one closed route vocabulary.** Define a typed closed set for `direct`, `normalized`, `split`, and `refused` near the create intake types. Keep the classifier’s direct-ready versus preparation-needed facts separate from terminal route dispatch; later steps select and report the final route.

- **Represent the classifier result explicitly.** One approach is an immutable result carrying the direct-ready boolean and the lifted strict-step list or absence result. Preserve this result in the pre-publication state, such as `PreparedCreatePlan`, so later routing consumes the original scan rather than reclassifying transformed source text.

- **Keep two distinct preflight refusals.** Retain `plan_tool/create.py:reject_unmatched_create_sources` and `reject_unmatched_create_fence` as input-syntax protection before route selection; an unmatched fence raises `CreateError` before a run record and is not a selected route. Update `plan_tool/create.py:validate_from_existing_seed` to delegate its References evidence check to the classifier while retaining its compatibility role for `plan_tool/cli/authoring.py:cmd_create` and existing producer tests. Missing, placeholder-only, fenced-only, frontmatter-only, or duplicate real `## References` evidence must likewise raise `CreateError` before any authoring invoker, checkpoint, plan, manifest, or archive work.

- **Count heading occurrences before extracting values.** Do not use `plan_tool/scope_fence.py:extract_h2_sections` alone for direct-readiness decisions because its first-occurrence behavior hides duplicates. Use its shared fence-safe, frontmatter-free occurrence view to distinguish each normalized canonical H2 from semantic aliases, lookalikes, and fenced examples.

- **Keep the direct-ready rule narrow.** A direct-ready body requires exactly one occurrence of each key in `plan_tool/create.py:_BODY_SECTIONS_CANONICAL_KEYS`, with non-empty content that `plan_tool/scope_fence.py:_is_placeholder_section` does not classify as a placeholder. Do not add length, quality, or semantic-content heuristics.

- **Route non-References shape gaps to preparation facts.** A missing, duplicate, empty, placeholder, or noncanonical body heading must mark the source as needing preparation without raising an intake error. Do not turn the eight body headings into a second universal refusal gate.

- **Keep strict steps independent.** Use `plan_tool/create.py:extract_steps_from_canonical` to expose whether a strict `## Steps` section yields a graph. A source can be direct-ready when strict steps are absent or malformed; that state only means later work must obtain the graph through its existing proposal path.

- **Run the classifier once at the library intake seam.** In `plan_tool/create.py:_prepare_create_plan`, classify every `from_existing_path` source after the existing unmatched-fence protection and before metadata, collision, distillation, or authoring calls. Preserve `plan_tool/create.py:reject_unmatched_create_sources` for independently supplied source strings.

- **Share selected-source identity with the CLI.** Expose one narrow selected-source helper or typed intake value from `plan_tool/create.py`. `plan_tool/cli/authoring.py:cmd_create` uses it for its pre-log `validate_from_existing_seed` call; `_prepare_create_plan` uses the same value for classification and every later file-backed route decision. Do not use `seed_body or from_description` at either site.

- **Leave shared parsers unchanged.** Keep `plan_tool/scope_fence.py` as the owner of placeholder and fence behavior and keep `plan_tool/canonical.py:extract_canonical_steps` as the strict parser. Do not copy their parsing rules.

- **Do not dispatch routes yet.** This step must not invoke a split assessment, normalize source prose, alter `SplitProposal`, change model-call ordering, or modify publication and convergence behavior.

## Tests

### Tests for this step

- `test_file_backed_route_vocabulary_is_closed` — the intake route type contains only `direct`, `normalized`, `split`, and `refused`.
- `test_classify_file_backed_source_requires_one_non_placeholder_references_heading` — missing, placeholder, empty, and duplicate real References headings raise `CreateError`.
- `test_classify_file_backed_source_ignores_frontmatter_and_fenced_reference_examples` — headings in YAML frontmatter or fenced Markdown do not satisfy or duplicate the References preflight.
- `test_file_backed_unmatched_fence_is_a_no_route_preflight_refusal` — a source with otherwise valid References and an unmatched fence exits before route selection, run-log start, model invocation, or write.
- `test_classify_file_backed_source_requires_each_normalized_direct_ready_body_heading_once` — each missing, empty, placeholder, or duplicated canonical body heading selects preparation without becoming a References refusal.
- `test_classify_file_backed_source_rejects_heading_lookalikes_for_direct_readiness` — semantic aliases and noncanonical H2 text do not satisfy a canonical direct-ready heading.
- `test_classify_file_backed_source_does_not_use_source_size_as_a_property` — equivalent small and large sources receive the same direct-ready classification.
- `test_classify_file_backed_source_lifts_strict_steps_when_available` — a strict canonical `## Steps` block returns the expected `Step` graph.
- `test_classify_file_backed_source_keeps_direct_readiness_when_steps_are_not_strict` — missing or malformed strict steps leave the step result absent without changing an otherwise direct-ready body verdict.
- `test_create_plan_rejects_duplicate_references_before_every_invoker_or_write` — a file-backed duplicate References source reaches no invoker, output directory, checkpoint, manifest, or archive path.
- `test_cmd_create_preflight_uses_empty_selected_provenance_source` — an empty `seed_body` alongside a valid description refuses before slug resolution, run-log start, model invocation, or write.
- `test_create_plan_file_backed_route_uses_empty_selected_provenance_source` — the library classifier refuses the same empty selected source instead of classifying the fallback description.
- `test_create_plan_without_from_existing_path_keeps_inline_input_outside_file_backed_preflight` — inline prose does not gain the file-backed References requirement.

Every listed test in `tests/test_create.py` must be green before this step is complete.

## Acceptance criteria

- A file-backed source has exactly one typed intake classification derived from its original selected source text.
- CLI preflight and library routing select `seed_body` whenever it is present, including an empty value, and otherwise `from_description`; neither path uses truthiness fallback.
- Missing, placeholder, empty, or duplicate real `## References` headings raise before any authoring model call or durable create-side write.
- An unmatched source fence is a separate input-syntax refusal before any selected route or run log; it does not alter the References evidence rule or add a route name.
- Frontmatter and fenced pseudo-headings do not count toward References or direct-ready heading counts.
- Each direct-ready body heading matches its canonical name after case and optional closing-ATX normalization, is unique, non-empty, and non-placeholder; any body-shape gap selects preparation rather than refusal.
- Direct readiness does not depend on source byte size.
- A strict canonical `## Steps` block yields a `Step` graph, while absent or malformed strict steps leave direct readiness unchanged.
- `plan_tool/cli/authoring.py:cmd_create` and direct `plan_tool/create.py:create_plan` calls continue to share `validate_from_existing_seed` preflight behavior.
- `uv run pytest tests/test_create.py -q` passes.

## References

- [CommonMark Spec 0.31.2 — ATX Headings and Fenced Code Blockshttps: — Read the heading and fenced-block grammar used by the normalized, fence-safe intake scan.
- [Python enum — Support for enumerationshttps: — Use for the closed observable route vocabulary.
- [pytest — How to use temporary directories and files in testshttps: — Use hermetic source fixtures and no-write assertions.

## Applicable guardrails

- **The plan’s “## Plan intent”, supplied-source authority:** limit this step to deterministic classification; it must not rewrite source text or spend model calls to decide source evidence.
- **The plan’s “## Step intent”, intake facts:** provide the direct-ready, preparation-needed, References, and strict-step facts that later steps consume without selecting their implementation route here.
- **The plan’s “## Out of scope”, heading-recognition boundary:** accept only the canonical headings the plan identifies; leave aliases and broader source preflight changes out of this step.
- **The plan’s “## Out of scope”, split boundary:** retain `SplitProposal` and existing source-consuming contracts unchanged until their owning steps.

## Deferred

- Architecture (`bafd6791befc230e29100c87744ed929a6cb00c4e71a1168fdcba790706ccf06`) — steps 2 and 3 consume this classifier to select source-authoritative dispatch and preparation outcomes; this step does not run a split assessment or normalize source prose.
- Terminal route lifecycle (`22a740fdbaa54ae54299f4be8f7189fd05c322dc42e247bba3ec3e71d1b4abdc`) — step 6 owns checkpoints, artifacts, archiving, run records, and exit behavior for the classifier’s later route selections.
