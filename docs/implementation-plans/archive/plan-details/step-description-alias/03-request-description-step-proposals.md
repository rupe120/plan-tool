> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Request description in step proposals and preserve create behavior

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Update `plan_tool/create.py` to request `description` in generated step proposals and accept legacy `title` responses. Keep `Step.title` as the internal API and reuse step 1’s alias policy. Preserve proposal validation, initial writes, archive moves, source deletion, and failure recovery. Extend `tests/test_create.py` so both response spellings reach usable plans through the existing authoring pipeline.

## Table of Contents

- [Summary](#summary) — The change and observable result.
- [Table of Contents](#table-of-contents) — Navigation through this detail.
- [Why](#why) — Why proposal generation needs the preferred spelling.
- [Input](#input) — Contracts supplied by dependencies and existing code.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two files this step edits.
- [Implementation](#implementation) — Proposal changes and preserved lifecycle behavior.
- [Tests](#tests) — Cases that pin compatibility and recovery.
- [Acceptance criteria](#acceptance-criteria) — Checkable completion conditions.
- [References](#references) — Scope and format sources.
- [Applicable guardrails](#applicable-guardrails) — Boundaries on this change.
- [Deferred](#deferred) — Responsibilities outside this step.

## Why

`plan_tool/create.py:_STEP_PROPOSAL_RESPONSE_CONTRACT` requests `title`, and `plan_tool/create.py:_parse_steps_json` rejects objects without it. `plan_tool/create.py:_propose_step_split` also requests that spelling through a separate prompt. Updating only schema acceptance and serialization leaves generated proposals teaching the legacy field. This step aligns those authoring requests while keeping existing responses usable and protecting the create pipeline’s file operations.

## Input

- **Step 1 supplies input compatibility.** Read its landed `plan_tool/schema.py:Step` implementation before adapting proposals. Its accepted aliases and dual-key policy remain authoritative.
- **Step 2 supplies preferred serialization.** Reuse its output through `plan_tool/parser.py:write_plan`; this step adds no YAML shaping.
- **Proposal parsing has additional rules.** `plan_tool/create.py:_parse_steps_json` rejects missing, non-string, empty, and whitespace-only step text. Preserve that proposal-specific boundary even where the schema accepts a broader string value.
- **Canned responses prove compatibility, not model reliability.** Injected invokers demonstrate that valid preferred and legacy replies travel through the real parser and writer. They do not measure how often a model follows the prompt.

## Files (creates vs edits)

- **New files:** None.
- **Existing files (edits only):**
  - `plan_tool/create.py` — Update step-proposal requests and accept both step-text spellings without changing lifecycle behavior.
  - `tests/test_create.py` — Add alias cases and exercise preferred responses through existing create, replacement, and recovery coverage.

## Implementation

- **Foundational logic: accept either proposal spelling without discarding conflicting or invalid supplied text.** Adapt `plan_tool/create.py:_parse_steps_json` to use step 1’s shared validation. A recommended approach is to pass only the supplied step-text keys into `Step` alongside the parser’s existing normalized fields. Do not pass the entire response object: proposal-only fields such as `rationale` have separate handling.

- **Check both supplied keys before choosing text.** The parser must accept description-only, title-only, and agreeing dual-key responses. It must return `None` for conflicts or an invalid value under either supplied key. Do not use truthiness fallback or alias precedence that hides a supplied value. Preserve accepted text exactly and retain the proposal-specific rejection of blank text.

- **Request the preferred field everywhere this parser receives generated steps.** Update `plan_tool/create.py:_STEP_PROPOSAL_RESPONSE_CONTRACT` and the field-specific wording in `plan_tool/create.py:_render_from_prompt`, including its plain-language instruction. Update the output-key request in `plan_tool/create.py:_propose_step_split` too. Its input display of `step.title` remains valid.

- **Preserve the parser’s other contracts.** Keep dependency coercion, dependency-note handling, concept IDs, complexity validation, change-type tolerance, intent normalization, rationale capture, and ignored generated gates unchanged. Keep existing return values and caller signatures.

- **Reuse both parser callers unchanged in purpose.** `plan_tool/create.py:propose_steps_from_claude` handles initial proposals and retries; `plan_tool/create.py:_propose_step_split` handles replacement pairs. Both must accept either spelling without changing retry budgets, split ownership, or deterministic dependency wiring.

- **Leave internal and unrelated titles alone.** Keep `Step.title`, checkpoint model data, review displays, and `plan_tool/create.py:_preserve_on_disk_step_fields` matching behavior. Reference objects in `plan_tool/create.py:_REFERENCE_RESPONSE_CONTRACT` and `plan_tool/create.py:_ROADMAP_REFERENCE_RESPONSE_CONTRACT` retain their own `title` fields.

- **Preserve file-operation ordering and recovery.** Keep `plan_tool/create.py:write_new_plan` routing through the existing stub and canonical writer. Keep `plan_tool/create.py:archive_existing_source` archive publication, source deletion, detail-directory cleanup, and restoration behavior. Keep parse-breaking apply recovery in `plan_tool/create.py:_converge_create_plan`. Exercise these paths with the new input spelling rather than restructuring them.

## Tests

Use injected invokers and temporary repositories in `tests/test_create.py`. Retain legacy fixtures where they provide compatibility coverage instead of converting the whole suite.

### Tests for this step

The following names describe proposed additions or extensions. Every affected case must be green before this step is finished.

- `test_step_proposal_contract_requests_description_in_both_prompt_arms` — Both `_render_from_prompt` arms request the preferred key without a competing step-output `title` instruction.
- `test_split_proposal_requests_description_and_accepts_either_spelling` — The split prompt requests `description`; preferred and legacy replies retain existing pair validation and wiring.
- `test_proposal_accepts_either_step_text_spelling_without_changing_text` — Description-only, title-only, and equal dual-key objects produce the same internal step text.
- `test_proposal_rejects_conflicting_or_invalid_supplied_step_text` — Unequal strings and invalid values under either key reject the proposal, including when the other key is valid.
- `test_proposal_requires_nonblank_step_text_for_both_spellings` — Missing text, empty strings, and whitespace-only strings retain proposal rejection behavior.
- `test_description_proposal_preserves_other_step_fields` — Preferred input retains dependency notes, concept IDs, intent, rationale capture, and existing field validation.
- `test_description_proposal_creates_a_parseable_plan_with_preferred_output` — A canned preferred response crosses the real proposal parser and initial writer; parsed text is unchanged and authored steps use `description`.
- `test_legacy_proposal_still_creates_a_parseable_plan` — A legacy response reaches the same usable plan through the existing authoring path.
- `test_description_proposal_preserves_replacement_archive_and_source_cleanup` — Extend `TestCreatePlanReplaceOnCollision` coverage to verify archived content, replacement content, and existing source/detail cleanup.
- `test_description_steps_preserve_archive_failure_restoration` — Fault-inject archive publication failure around `archive_existing_source` and assert existing restoration and cleanup guarantees.
- `test_description_steps_preserve_create_failure_recovery` — Extend `TestCreatePlanRecoveryBoundaries` coverage without replacing retained invalid stubs or partial artifacts with a new rollback policy.
- `TestCreatePlanDriftHalt.test_iterate_loop_reverts_parse_broken_apply` — Retain the existing parse-breaking apply recovery contract.

Verify new assertions by temporarily breaking the behavior they pin and observing failure, then restore the implementation.

## Acceptance criteria

- Preferred and legacy proposal responses produce usable `Step` objects with unchanged internal `title` values.
- Agreeing dual keys pass; conflicts and invalid supplied values fail without silently losing text.
- Both main proposal prompt arms and the split output request use `description`.
- New plans produced from either response spelling serialize step text using step 2’s preferred output.
- Existing archive moves, source deletions, detail cleanup, partial-write retention, and rollback behavior remain covered and unchanged.
- Changes remain confined to `plan_tool/create.py` and `tests/test_create.py`.
- The affected tests and full pytest suite pass.

## References

- [BACKLOG.md — #517](../../../../../BACKLOG.md) — Read the alias scope and owner-confirmed compatibility exception.
- [PLAN_FORMAT.md](../../../../../PLAN_FORMAT.md) — Read the step field semantics and authored frontmatter contract.
- [DATA_CONTRACT.md](../../../../../DATA_CONTRACT.md) — Read the format-version boundary this step preserves.
- [plan_tool/schema.py](../../../../../plan_tool/schema.py) — Use `Step` as the shared owner of alias validation.
- [plan_tool/parser.py](../../../../../plan_tool/parser.py) — Use the canonical writer supplied by step 2.

## Applicable guardrails

- **The plan’s “Scope guardrails,” compatibility boundary:** Keep this change inside proposal authoring and its tests; consume the dependency steps’ validation and serialization outcomes.
- **The plan’s “Out of scope,” internal APIs and lifecycle:** Do not rename internal step attributes or alter execution, detail requirements, or existing file-operation semantics.
- **The plan’s “Scope guardrails,” unrelated findings:** Route unrelated defects through the existing backlog process instead of broadening these edits.

## Deferred

- Format-policy and reference-document updates — Other plan work owns those documents; this step consumes their contract.
- Shared response-contract redesign in `plan_tool/response_contract.py:JsonResponseContract` — Its existing decoding and prompt rendering support this focused change without modification.
- Real-model prompt adherence measurement — Canned-response tests cannot establish a hit rate; this requires representative briefs and separate measurement.
- Internal terminology cleanup — Retain existing attributes, displays, and matching rules because preferred authoring does not require their renaming.
