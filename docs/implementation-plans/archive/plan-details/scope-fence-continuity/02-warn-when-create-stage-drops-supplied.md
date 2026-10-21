> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Warn when a create stage drops a supplied guardrail heading

## Summary

Add deterministic create-time warnings when distillation or body synthesis drops a supplied `Scope guardrails`, `Audit guardrails`, or `Expected placement` H2 heading. Update `plan_tool/create.py` to compare the known guardrail headings at each lossy stage boundary, and update `tests/test_create.py` with focused stage-level coverage. Step 1 preserves the original guardrail text for final rendering; this step makes an intermediate omission visible instead of letting that fallback hide it. On green, each dropped supplied heading produces one clear advisory finding, while retained or never-supplied headings produce none.

## Table of Contents

- [Summary](#summary) — The warning behavior and its observable result.
- [Table of Contents](#table-of-contents) — Links to the sections in this detail.
- [Why](#why) — Why preservation alone does not expose stage failures.
- [Input](#input) — The heading contracts compared at each create boundary.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two existing files this step changes.
- [Implementation](#implementation) — The exact-heading comparison and warning rules.
- [Tests](#tests) — Focused regression cases for both create stages.
- [Acceptance criteria](#acceptance-criteria) — Verifiable completion conditions.
- [References](#references) — Primary documentation for matching and test doubles.
- [Deferred](#deferred) — Semantic-loss detection left outside this step.

## Why

Step 1 keeps supplied guardrails in the rendered plan, but that preservation can mask a model stage that omitted the heading it was told to retain. `plan_tool/create.py:create_plan` already has a deterministic advisory pattern for lossy distillation in `find_dropped_references`; create needs the same visibility for the three supplied scope-fence headings before their original seed bodies act as rendering fallback.

## Input

- **Supplied-heading contract** — Build on step 1’s recognized optional headings: `Scope guardrails`, `Audit guardrails`, and `Expected placement`. Treat only non-empty H2 sections returned by `plan_tool/create.py:extract_h2_sections` as supplied.
- **Distill boundary** — Compare headings from `create_plan`’s `raw_seed` with the single-plan `DistillOutcome.distilled` output from `plan_tool/create.py:propose_distilled_seed_from_claude`.
- **Synthesis boundary** — Compare headings in the source passed to `plan_tool/create.py:propose_body_sections` with its parsed section mapping. A missing optional key or `None` value means that stage dropped the heading.
- **Verification limit** — Check exact heading continuity only. Do not infer whether guardrail prose was materially folded into another section.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/create.py` — add deterministic supplied-guardrail heading comparison and emit advisory findings from the distill and synthesis paths in `create_plan`.
  - `tests/test_create.py` — cover dropped and retained headings for each stage without real model calls.

## Implementation

- **Foundational logic: exact supplied-guardrail heading continuity check.** Compare the three recognized guardrail heading names at each create stage that can reorganize prose. Report a finding for every heading present in that stage’s input and absent from its output.

- **Use normalized H2 names as the source of truth.** Base heading detection on `plan_tool/create.py:extract_h2_sections`, stripping CommonMark-valid ATX closing sequences before matching the recognized names and ignoring empty bodies. Keep the check limited to the recognized optional guardrail headings introduced by step 1; arbitrary H2 headings must not become warning candidates or accepted optional sections.

- **Check distillation before rebinding the seed.** In the single-plan branch of `plan_tool/create.py:create_plan`, retain the headings from `raw_seed` long enough to compare them with `DistillOutcome.distilled` before `from_description` and `seed_body` are replaced. Do not warn for skipped distillation, passthrough outcomes, or split proposals because no single distilled replacement exists to compare.

- **Check synthesis at its actual output shape.** When `create_plan` receives a result from `plan_tool/create.py:propose_body_sections`, compare the guardrails present in `synth_source` with the returned mapping. An absent key and a null key are both omissions for this warning; a non-empty value retains the heading.

- **Keep warnings advisory and deterministic.** Follow the create-time reporting style around `plan_tool/create.py:find_dropped_references`: emit clear stderr-facing findings that identify the dropped heading and the stage that dropped it, but do not reject the create, retry a model call, or alter the stage output. Step 1’s original-seed rendering precedence remains unchanged.

- **Avoid duplicate and false-positive findings.** Emit at most one finding per heading per stage. A heading absent from the stage input must never warn, even if another stage has a different guardrail heading. A heading retained by both stages must produce no preservation finding.

- **Preserve the closed section contract.** Do not widen `OPTIONAL_PLAN_BODY_SECTION_SHAPES`, `_parse_body_sections_json`, or `_validate_distilled_sections` beyond step 1’s three guardrails. This step observes stage loss; it does not redesign optional-section parsing, rendering order, or model prompts.

## Tests

- `test_distill_guardrail_heading_drop_emits_deterministic_finding` — A seed with all recognized guardrails and mocked single-plan distillation missing one heading reports that heading and the distill stage.
- `test_distill_guardrail_headings_retained_emit_no_finding` — A mocked distilled result retaining every supplied guardrail emits no guardrail-preservation warning.
- `test_synthesis_guardrail_heading_drop_emits_deterministic_finding` — A synthesis source with supplied guardrails and a mocked body-section result that omits or nulls one optional key reports that heading and the synthesis stage.
- `test_synthesis_guardrail_headings_retained_emit_no_finding` — Non-empty synthesized values for every supplied guardrail produce no preservation finding.
- `test_unsupplied_guardrail_heading_does_not_warn` — A stage output lacking a guardrail never present in its input remains quiet.
- `test_atx_closing_sequence_guardrail_heading_is_recognized` — `## Audit guardrails ##` is normalized to the same recognized supplied heading as `## Audit guardrails`.
- `test_guardrail_drop_warnings_do_not_block_create_or_remove_rendered_seed_body` — The advisory leaves `create_plan` successful and preserves the supplied guardrail section through step 1’s rendering behavior.

### Test-creation order (feature step)

1. `test_distill_guardrail_heading_drop_emits_deterministic_finding` — Establish the raw-seed-to-distill comparison.
2. `test_synthesis_guardrail_heading_drop_emits_deterministic_finding` — Establish the distill-input-to-synthesis comparison.
3. `test_distill_guardrail_headings_retained_emit_no_finding` and `test_synthesis_guardrail_headings_retained_emit_no_finding` — Pin the quiet retained paths.
4. `test_unsupplied_guardrail_heading_does_not_warn` and `test_guardrail_drop_warnings_do_not_block_create_or_remove_rendered_seed_body` — Pin the scope boundary and advisory behavior.

Every new test must be green before this step is considered finished.

## Acceptance criteria

- A single-plan distill output that omits a supplied recognized guardrail heading emits one deterministic advisory identifying that heading and the distill stage.
- A body-synthesis result that omits or returns `null` for a supplied recognized guardrail heading emits one deterministic advisory identifying that heading and the synthesis stage.
- Create emits no guardrail-preservation finding when every supplied guardrail heading is retained at a stage.
- Create emits no guardrail-preservation finding for guardrail headings absent from that stage’s input.
- Guardrail-drop findings do not fail `plan_tool/create.py:create_plan`, trigger another model call, or change step 1’s final rendering preservation.
- The focused cases in `tests/test_create.py` pass.

## References

- [Python regular expression operations](https://docs.python.org/3/library/re.html) — Reference for the exact H2 matching behavior behind `extract_h2_sections`.
- [pytest monkeypatch guide](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Use fakes to return stage outputs that retain or omit headings.
- [unittest.mock](https://docs.python.org/3/library/unittest.mock.html) — Reference for asserting deterministic warning output without model calls.
- [CommonMark Specification](https://spec.commonmark.org/current/) — Reference for ATX H2 heading syntax.

## Deferred

- Detect guardrail content materially folded into another section — Heading continuity cannot prove semantic continuity; leave this for BACKLOG #163.
