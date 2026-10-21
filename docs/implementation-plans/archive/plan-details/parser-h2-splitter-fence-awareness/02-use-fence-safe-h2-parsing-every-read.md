> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Use fence-safe H2 parsing in every read consumer and strip examples only for matching

## Summary

Apply step 1’s opt-in fence-safe H2 parsing to every plan and seed reader in this step’s file list. Update the review, create, detail, grounding, handoff, inspection, and scope-review paths so a fenced pseudo-heading never replaces or truncates a real plan section. Preserve fenced code in readers that copy or render section bodies, and strip it only for readers that use section text as evidence for a pattern match. On green, every listed consumer follows the real H2 outline without changing parser defaults or write-time unmatched-fence handling.

## Table of Contents

- [Summary](#summary) — The completed behavior and main design choice.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — The reader-level corruption this step prevents.
- [Input](#input) — The upstream parser contract this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — The production and test files in scope.
- [Implementation](#implementation) — Consumer-by-consumer fence-safety and content rules.
- [Tests](#tests) — Regression coverage for every reader category.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Markdown and test references.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this work.
- [Deferred](#deferred) — Related work owned by later steps.

## Why

`plan_tool/parser.py:parse_body_sections` and `split_body_sections` feed completeness, review, concept, grounding, and handoff decisions, while `plan_tool/scope_fence.py:extract_h2_sections` feeds seed and reference reads. A fenced example can contain a valid-looking H2, so every reader must opt into step 1’s safe boundary behavior before it interprets a plan or seed. Readers that render source text must retain the example, but matching readers must not treat an example path, symbol, or suppression phrase as an actual claim.

## Input

- **Step 1’s fence-safe parser modes** — Use the explicit boundary-safe and content-stripping modes supplied by step 1 through `plan_tool/parser.py:parse_body_sections`, `split_body_sections`, and `plan_tool/scope_fence.py:extract_h2_sections`. Preserve their default behavior for callers outside this step.

- **`plan_tool/parser.py:BodySection`** — Keep normalized names, source order, headings, and section bodies compatible with `plan_tool/concept_bootstrap.py:bootstrap_concepts`. Fence safety changes which headings form sections; it does not redefine the section data shape.

- **Unmatched-opening signal** — Consume step 1’s fence interpretation consistently, but leave route-specific refusal, target preservation, and error reporting to step 3.

- **Unmatched-opening read semantics** — In every fence-safe read, an unmatched opener makes its opener-through-EOF tail code, so later heading-looking lines do not form sections. The returned shared result remains distinguishable for step 3’s pre-write refusal; this step does not turn a read into a route error.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/review.py` — Make each plan and seed H2 read fence-safe; preserve section bodies for prompt and report inputs, and strip fenced examples only before claim, path, symbol, or suppression matching.
  - `plan_tool/create.py` — Keep seed-section transfer fence-safe and preserve examples; prevent fenced architecture anchors, artifact references, and `--from-existing` reference eligibility from treating examples as evidence.
  - `plan_tool/detail.py` — Make candidate concept buckets fence-safe and retain the existing fence-safe, source-preserving References extraction.
  - `plan_tool/grounding.py` — Read `Out of scope` and `Deferred` through safe boundaries without changing their verbatim fingerprint input.
  - `plan_tool/jira_handoff.py` — Render context from real plan headings while preserving fenced examples in displayed context.
  - `plan_tool/cli/inspect.py` — Use real section boundaries for pending-concept context excerpts.
  - `plan_tool/cli/scope_review_cmd.py` — Use real section boundaries for flat-record bucket checks and legacy concept derivation.
  - `tests/test_review.py` — Cover safe plan/seed reads, matching-only stripping, and preserved prompt content.
  - `tests/test_create.py` — Cover safe seed transfer and fenced-example exclusion from code-anchor and artifact-reference matching.
  - `tests/test_detail.py` — Cover reference extraction and candidate bucket derivation around fenced pseudo-headings.
  - `tests/test_grounding.py` — Cover verbatim scope extraction after a fenced pseudo-heading.
  - `tests/test_jira_handoff.py` — Cover rendered handoff context with fenced examples.
  - `tests/cli/test_inspect_cmds.py` — Cover safe pending-context excerpts in `status`.
  - `tests/cli/test_scope_review_cmd.py` — Cover safe bucket lookup and legacy concept derivation.

## Implementation

- **Use one fence interpretation.** Build every changed reader on step 1’s explicit modes instead of adding local heading regexes or fence scans. Keep `plan_tool/parser.py` and `plan_tool/scope_fence.py` as the owners of parsing behavior.

- **Keep boundary safety separate from content stripping.** Boundary-safe reads must ignore pseudo-headings inside fenced blocks while retaining those blocks in the selected real section. Content stripping must apply only when the reader searches extracted text for evidence; it must not become the default for rendering, copying, fingerprinting, or prompt context.

- **Use the same unmatched-tail rule everywhere.** The boundary-safe reader retains an unmatched opener and its EOF tail in the preceding real section while treating all of it as code; a content-stripping matcher excludes that tail. Do not let one reader surface a later pseudo-heading as a section while another hides it.

- **Sweep `plan_tool/review.py` completely.** Make `check_body_completeness`, `_plan_body_sections`, `_check_decision_record_coverage`, `_extract_acceptance_criteria`, and `_extract_seed_scope_contract` select real H2 boundaries. Their returned prose must retain fenced examples. Ensure the matching inputs used by `build_plan_footprint`, `detect_claim_vs_delivery`, and `_summary_and_why_text` exclude fenced examples so an example path, symbol, or suppression phrase cannot create a finding.

- **Keep review outputs faithful to source.** `_plan_body_sections`, `_extract_acceptance_criteria`, and `_extract_seed_scope_contract` feed prompt or report context. Do not make these helpers destructive merely to support a downstream matcher; use a matching-only projection where needed.

- **Sweep `plan_tool/create.py` by reader intent.** Keep body transfer through `_extract_supplied_guardrails`, `_intent_from_seed_outcome`, canonical seed reuse, and the concept source passed to `bootstrap_concepts` boundary-safe and source-preserving. `validate_from_existing_seed` is an eligibility predicate, so it must inspect a content-stripped projection of the real `References` section: a fenced example cannot authorize `--from-existing`, while the source text remains available for later transfer. Make `_architecture_code_anchors` ignore inline-code examples inside fences, and retain `find_dropped_references` as a content-stripping matcher so an example cannot corroborate or manufacture an artifact reference.

- **Preserve existing `scope_fence` choices.** `plan_tool/detail.py:extract_plan_references` already requests fence-safe boundaries because it passes References text into the detail prompt. Retain fenced reference examples in its returned text. Apply the parser-safe mode to the `parse_body_sections` call that feeds `_candidate_body_bucket_names`.

- **Keep scope text verbatim.** `plan_tool/grounding.py:extract_scope_bearing_sections` must use real boundaries while returning the real `Out of scope` and `Deferred` text unchanged, because `compute_step_authoring_fingerprint` depends on those bytes as scope evidence.

- **Keep rendered and inspected context intact.** `plan_tool/jira_handoff.py:_plan_context_sections` and `plan_tool/cli/inspect.py:_print_pending_decisions` must find only real headings but must retain fenced examples in their displayed section bodies.

- **Keep concept readers aligned.** `plan_tool/cli/scope_review_cmd.py:_sign_off_decision_record` and the legacy `cmd_scope_review` derivation path must use the same safe section boundary rule as `plan_tool/review.py:_check_decision_record_coverage`. A fenced pseudo-heading must not make one path report a missing bucket while the other accepts it.

- **Do not widen into write handling.** This step must not change parser defaults, alter `plan_tool/detail.py:parse_detail_file_sections`, or add unmatched-opening refusal behavior. Step 3 owns route-specific failures before target changes, and step 4 owns concept-sync replacement safety.

## Tests

### Tests for this step

- `tests/test_review.py:test_body_completeness_uses_real_heading_after_fenced_pseudo_heading` — asserts completeness finds the real later section instead of treating a fenced H2 as a boundary.

- `tests/test_review.py:test_review_matching_ignores_fenced_paths_symbols_and_suppression_text` — asserts plan-claim and suppression checks do not treat fenced examples as evidence.

- `tests/test_review.py:test_review_prompt_section_reads_preserve_fenced_examples` — asserts acceptance and seed-scope prompt inputs retain fenced text after selecting the real section.

- `tests/test_review.py:test_fence_safe_read_hides_later_pseudo_heading_after_unmatched_opener` — asserts the shared EOF-tail rule keeps later heading-looking lines out of reader sections without issuing a write-route error.

- `tests/test_review.py:test_decision_record_bucket_lookup_ignores_fenced_pseudo_heading` — asserts review’s bucket check recognizes a real section after a fenced lookalike.

- `tests/test_create.py:test_seed_section_transfer_uses_real_headings_and_preserves_fenced_examples` — asserts seed content reaches the rendered plan from the real section without dropping fenced content.

- `tests/test_create.py:test_architecture_code_anchors_ignore_fenced_inline_code` — asserts only inline-code anchors outside fences request local repository grounding.

- `tests/test_create.py:test_dropped_reference_matching_ignores_fenced_artifact_examples` — asserts a fenced artifact mention neither creates nor clears a dropped-reference finding.

- `tests/test_create.py:test_from_existing_reference_eligibility_ignores_fenced_example` — asserts a real `References` section containing only a fenced example does not authorize `--from-existing`, while unfenced evidence still does.

- `tests/test_detail.py:test_extract_plan_references_ignores_fenced_pseudo_heading_and_preserves_body` — asserts References extraction uses the real heading and returns its fenced example unchanged.

- `tests/test_detail.py:test_candidate_body_buckets_ignore_fenced_pseudo_heading` — asserts detail deferral candidates derive from real plan-body sections only.

- `tests/test_grounding.py:test_extract_scope_bearing_sections_uses_real_headings_and_preserves_fenced_text` — asserts scope fingerprint input comes from the real `Out of scope` and `Deferred` sections.

- `tests/test_jira_handoff.py:test_handoff_plan_context_ignores_fenced_pseudo_heading` — asserts the handoff renders real context sections and keeps their fenced examples.

- `tests/cli/test_inspect_cmds.py:test_status_pending_context_uses_real_section_after_fenced_pseudo_heading` — asserts `status` prints context from the pending concept’s real bucket.

- `tests/cli/test_scope_review_cmd.py:test_scope_review_uses_real_sections_for_flat_and_legacy_concepts` — asserts both concept-record paths agree on section existence after a fenced pseudo-heading.

Every listed test and the full suite must be green before this step is complete.

## Acceptance criteria

- Every H2 reader in this step’s production file list explicitly selects fence-safe boundaries.

- A fenced pseudo-heading never truncates, replaces, or hides the real later section read by completeness, review, concept, grounding, handoff, inspection, detail, or create flows.

- Readers that render, copy, fingerprint, or pass section bodies into prompts retain fenced examples from the selected real section.

- Every fence-safe reader treats an unmatched opener through EOF as code, retains that tail only for boundary-safe reads, and does not expose later heading-looking lines as sections.

- `plan_tool/create.py:_architecture_code_anchors`, `plan_tool/create.py:find_dropped_references`, `plan_tool/create.py:validate_from_existing_seed`, and review’s text-matching paths do not treat fenced examples as real evidence.

- `plan_tool/review.py:_check_decision_record_coverage` and `plan_tool/cli/scope_review_cmd.py:_sign_off_decision_record` reach the same bucket-existence result for the same fenced plan body.

- Parser defaults remain unchanged; callers outside this explicit sweep retain their existing behavior.

- The focused tests and the full suite pass.

## References

- [CommonMark Spec — Fenced code blockshttps: — Use the fence-opening and closure rules when checking the shared parser behavior.

- [CommonMark Spec — ATX headingshttps: — Use the heading rules to distinguish real H2 boundaries from code content.

- [pytest documentation — How to parametrize fixtures and test functionshttps: — Use parameterized regressions where several readers share the same fenced-heading fixture.

## Applicable guardrails

- **The plan’s “Plan intent” section** — Apply fence-safe reads across the listed consumers so the real plan outline remains authoritative.

- **The plan’s “## Out of scope”, allowed behavior changes** — Limit behavior changes to correct handling of fenced pseudo-headings in the swept readers; leave unrelated user-visible behavior unchanged.

- **The plan’s “## Out of scope”, allowed reorganization** — Keep the consumer sweep focused. Do not consolidate parsers or reorganize modules in this step.

- **The plan’s “## Risks” section** — Select safety explicitly per consumer rather than changing parser defaults for the whole repository.

- **The plan’s “## Out of scope”, detail-file schema carve-out** — Do not change `plan_tool/detail.py:parse_detail_file_sections`.

- **The plan’s “## Out of scope”, legacy Jira-grade scanner carve-out** — Do not change or test `plan_tool/jira_grade.py` through this work.

## Deferred

- Unmatched-opening-fence refusal and target-preservation behavior — Step 3 owns route-specific pre-write failures.

- `plan_tool/concept_sync.py` section comparison and replacement — Step 4 owns its in-place mutation and rollback contract.

- Default-on fence handling for `plan_tool/scope_fence.py:extract_h2_sections` — The plan keeps this separate follow-up open.

- Further consolidation between `plan_tool/parser.py` and `plan_tool/scope_fence.py` — Leave broader shared-parser design outside this focused consumer sweep.
