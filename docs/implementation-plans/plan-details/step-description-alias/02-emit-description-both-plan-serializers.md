# Step 2 — Emit description from both plan serializers

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Update `plan_tool/parser.py:render_plan_text` and `plan_tool/parser.py:write_plan` to emit step text under `description`. Keep `Step.title` and ordinary model dumps unchanged. Preserve validation, format-version checks, guarded replacement, and body preservation. Add serializer and consumer regression coverage so rewritten plans remain usable throughout the pipeline.

## Table of Contents

- [Summary](#summary) — The change and observable result.
- [Why](#why) — Why input compatibility also needs preferred output.
- [Input](#input) — Contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Production and test changes.
- [Implementation](#implementation) — Output mapping and preserved writer guarantees.
- [Tests](#tests) — Cases that pin serialization and compatibility.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Scope and format contracts.
- [Applicable guardrails](#applicable-guardrails) — Boundaries on this change.
- [Deferred](#deferred) — Work owned elsewhere.

## Why

Both serializers in `plan_tool/parser.py` currently dump the internal model fields directly, so accepting `description` alone does not make ordinary output use it. Step 1 supplies input compatibility; this step completes the output boundary without changing the internal API that prompts, detail authoring, review, execution, and Jira export already consume.

## Input

- **Step 1 owns alias acceptance.** Its outcome lets preferred and legacy frontmatter parse into the same `plan_tool/schema.py:Step.title` attribute. Read the landed implementation before choosing the serializer change.
- **Model dumps remain internal data.** Both serializers call `Plan.model_dump(exclude_defaults=True, exclude_none=True)` and validate the resulting mapping with `Plan.model_validate`.
- **Version stamping remains authoritative.** `plan_tool/parser.py:_stamp_current_format_version` checks writer eligibility and supplies the explicit declaration.
- **The writer owns current disk content.** `plan_tool/parser.py:write_plan` reads the current body and checks `_FRONTMATTER_PROVENANCE` before replacing frontmatter.

## Files (creates vs edits)

- **New files:** None.
- **Existing files (edits only):**
  - `plan_tool/parser.py` — Apply the preferred step key at both YAML output boundaries.
  - `tests/test_parser.py` — Cover both serializers, round trips, unchanged internal dumps, and guarded writes.
  - `tests/test_renderer.py` — Verify serialized plans retain execution-prompt step text.
  - `tests/test_detail.py` — Verify detail rendering and pointer updates retain step text.
  - `tests/test_review.py` — Verify review rendering consumes rewritten plans.
  - `tests/test_launcher.py` — Verify status write-back retains step text and preferred output.
  - `tests/test_jira.py` — Verify export consumes rewritten plans without changing story titles.

## Implementation

- **Foundational logic: translate internal step `title` into authored step `description` only at serialization.** Apply the rule to every step in both `plan_tool/parser.py:render_plan_text` and `plan_tool/parser.py:write_plan`.

- **Keep the translation narrow.** One recommended approach is a small parser-local mapping operation over the dumped `steps` entries, reused by both serializers. It must not recursively rename arbitrary `title` keys: plan and feature titles retain their existing meaning.

- **Keep internal state unchanged.** Serialization must not mutate the supplied `Plan`, its steps, or the ordinary `model_dump` contract. Reject a global serialization alias or internal attribute rename that changes unrelated consumers.

- **Preserve validation before publication.** Keep `Plan.model_validate` and `_stamp_current_format_version` effective in both paths. Retain `_coerce_enums` before `yaml.safe_dump`, along with existing default omission and Unicode handling. Invalid post-construction mutations must still fail before a disk write.

- **Emit one spelling.** Each serialized step must contain `description` and omit `title`, including plans read from legacy title-only input or accepted equal dual-key input. Preserve the supplied string exactly after parsing the output; YAML quoting and scalar style may change.

- **Preserve the two body contracts.** `render_plan_text` must append its supplied body unchanged. `write_plan` must retain the current on-disk body, including body-only edits made after parsing. Do not rebuild prose from the model or replace it with an earlier snapshot.

- **Preserve guarded replacement.** Keep `write_plan(path, plan, *, expect_unchanged=True)` unchanged. A concurrent frontmatter edit must still raise `ConcurrentModificationError` without modifying the file; the explicit override and unparsed-path behavior remain available. Refresh provenance from the published frontmatter so a second write after converting legacy keys succeeds.

- **Reuse consumer APIs unchanged.** `plan_tool/renderer.py:render_prompt`, `plan_tool/detail.py:render_detail_prompt`, `plan_tool/review.py:render_review_prompt`, `plan_tool/launcher.py:run_step`, and `plan_tool/jira.py:export_jira` consume the retained internal step text. Exercise these boundaries through the declared tests rather than editing their production modules.

- **Keep fixtures independent where useful.** Retain legacy title-only fixtures as compatibility inputs. Update assertions that inspect rewritten YAML to check parsed step keys, rather than replacing every `title:` occurrence or banning the word across a whole document.

## Tests

### Tests for this step

The following are proposed test names. Extend nearby existing cases where that keeps the contract clearer. Every added or changed case must be green before this step is finished.

- `tests/test_parser.py:test_both_serializers_emit_description_and_omit_step_title` — Parameterize both serializers and accepted input spellings; inspect parsed YAML keys for every step.
- `tests/test_parser.py:test_serialization_preserves_plan_and_feature_titles` — Assert that only step keys change.
- `tests/test_parser.py:test_serialization_does_not_mutate_internal_step_text_or_dump_keys` — Assert unchanged `Step.title` values and ordinary model dumps after both output paths.
- `tests/test_parser.py:test_description_output_round_trips_exact_step_text` — Cover empty, multiline, Unicode, and YAML-sensitive strings through render, parse, and disk rewrite.
- `tests/test_parser.py:test_render_preserves_supplied_body_exactly` — Compare the returned body with the supplied body, including whitespace and code fences.
- `tests/test_parser.py:test_legacy_rewrite_preserves_current_body_and_refreshes_provenance` — Add a body-only edit after parsing, rewrite to preferred keys, then write again without reparsing.
- `tests/test_parser.py:test_description_rewrite_refuses_concurrent_frontmatter_edit_without_writing` — Assert the exception and unchanged file bytes after an external frontmatter edit.
- `tests/test_parser.py:TestConcurrentModificationGuard` — Retain coverage for explicit override, body-only edits, and unparsed paths.
- `tests/test_parser.py:TestRoundTrip` — Retain invalid-mutation rejection and default omission; strengthen failure cases to assert no disk change.
- `tests/test_parser.py:test_both_serializers_keep_version_one_and_reject_ineligible_versions` — Cover legacy undeclared and explicit version-1 input while retaining unsupported-version refusal.
- `tests/test_renderer.py:test_run_prompt_keeps_step_text_after_description_round_trip` — Reparse serializer output and assert the execution prompt contains the original text.
- `tests/test_detail.py:test_detail_render_and_pointer_update_keep_description_step_text` — Exercise `render_detail_prompt` and `update_step_detail_field` with preferred-key input and inspect rewritten YAML.
- `tests/test_review.py:test_review_prompt_keeps_step_text_after_description_round_trip` — Assert unchanged step text in `render_review_prompt`.
- `tests/test_launcher.py:test_run_writeback_keeps_description_and_step_text` — Use the existing fake invoker approach to verify status advancement, preferred keys, and reparsed text.
- `tests/test_jira.py:test_export_accepts_rewritten_description_plan_without_changing_story_title` — Use a fake invoker and assert the plan text reaches export without renaming Jira story fields.

Run the affected test modules during development and the plan’s full test command before completion. Keep backend calls stubbed. Verify new key-selection and guard assertions by temporarily breaking the behavior they pin and confirming the relevant tests fail.

## Acceptance criteria

- Both serializers emit `steps[].description` and omit `steps[].title`.
- Preferred-key output reparses into unchanged `Step.title` values for every accepted input spelling.
- Plan titles, feature titles, ordinary model dumps, and serializer signatures remain unchanged.
- Legacy plans rewrite successfully with an explicit format-version declaration of `1`, without an upgrade operation.
- Invalid model mutations and ineligible versions still fail before publication.
- Rendering preserves the supplied body; writing preserves the current on-disk body.
- Concurrent frontmatter edits remain protected, and repeated successful writes do not reject their own output.
- Renderer, detail, review, launcher, and Jira regression cases pass without production edits outside `plan_tool/parser.py`.
- All added and affected tests pass, followed by the full suite.

## References

- [BACKLOG.md — #517](BACKLOG.md) — Defines the preferred spelling and the owner-confirmed compatibility exception.
- [PLAN_FORMAT.md](PLAN_FORMAT.md) — Owns authored step fields and plan frontmatter semantics.
- [DATA_CONTRACT.md](DATA_CONTRACT.md) — Owns the format-version policy whose narrow amendment belongs to the documentation step.
- [plan_tool/parser.py](plan_tool/parser.py) — Contains both serializers and the frontmatter provenance guard.
- [plan_tool/schema.py](plan_tool/schema.py) — Owns the internal model and step 1’s input compatibility.

## Applicable guardrails

- **The plan’s “## Scope guardrails,” version compatibility:** Keep the existing version machinery effective at both serializer boundaries; do not introduce an upgrade dependency.
- **The plan’s “## Out of scope,” migration:** Limit preferred-key conversion to requested rendering and ordinary writes. Do not sweep stored plans.
- **The plan’s “## Scope guardrails,” internal APIs:** Keep downstream production consumers on their current step-text API; use their tests to demonstrate compatibility.
- **The plan’s “## Out of scope,” unrelated cleanup:** Leave writer lifecycle, execution behavior, and schema cleanup outside this change.

## Deferred

- Proposal authoring in `plan_tool/create.py` — Step 3 owns requesting the preferred spelling and accepting legacy model responses.
- Format-policy documentation and backlog reconciliation — Step 4 owns these changes.
- Broad serializer or writer restructuring — Neither output-key conversion nor its compatibility tests require changing shared lifecycle or publication behavior.
