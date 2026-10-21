# Step 2 — Ask before adding missing guardrails

## Summary

Let `plan-tool create` offer model-proposed `Scope guardrails`, `Audit guardrails`, and `Expected placement` only when the original seed lacks that heading. Update `plan_tool/create.py` and both body-generation prompt contracts so proposals remain candidates until the author explicitly accepts each one. Preserve step 1’s supplied-text rule, and omit all proposals in `--yes` and non-TTY runs. On green, accepted proposals appear under their own H2 headings; rejected or unreviewed proposals do not reach the plan.

## Table of Contents

- [Summary](#summary) — The approval-gated guardrail proposal behavior.
- [Table of Contents](#table-of-contents) — Links to each detail section.
- [Why](#why) — Why generated scope fences need author approval.
- [Input](#input) — The guardrail and proposal contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Existing files changed by the work.
- [Implementation](#implementation) — Proposal filtering, approval, and rendering rules.
- [Tests](#tests) — Focused approval and non-interactive regression coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Test guidance for interactive output.
- [Deferred](#deferred) — Follow-up work outside the approval gate.

## Why

Step 1 preserves an author’s existing guardrails, but a seed without them still has no way to develop a scope fence. `plan_tool/create.py:create_plan` already receives model-produced body content, so it can surface a candidate without another authoring flow; it must not let that candidate become an author constraint merely because it appeared in distillation or synthesis output.

## Input

- **Step 1’s recognized sections** — Depend on step 1’s outcome: `Scope guardrails`, `Audit guardrails`, and `Expected placement` are conditional plan-body sections handled through `plan_tool/create.py:OPTIONAL_PLAN_BODY_SECTION_SHAPES` and rendered by `plan_tool/create.py:_render_plan_body`.

- **Original seed authority** — Use `plan_tool/create.py:extract_h2_sections` against the original seed before `plan_tool/create.py:create_plan` replaces `seed_body` with `DistillOutcome.distilled`. Only that original heading set decides whether a guardrail is supplied or missing.

- **Existing proposal outputs** — Consume optional guardrail values returned by `plan_tool/create.py:propose_distilled_seed_from_claude` and `plan_tool/create.py:propose_body_sections` as candidates, not as already-approved seed content.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/create.py` — keep original supplied guardrails separate from model candidates, ask for explicit per-heading approval, and render only accepted candidates.
  - `plan_tool/prompts/distill-seed.md` — permit grounded proposals for missing recognized guardrails while preserving supplied ones.
  - `plan_tool/prompts/synthesize-body.md` — use the same missing-only proposal and non-rewrite rules.
  - `tests/test_create.py` — cover candidate selection, approval, rejection, and safe non-interactive omission.

## Implementation

- **Foundational logic: approval-gated missing-guardrail proposals.** Treat a recognized guardrail as eligible for a proposal only when it was absent from the original seed. A supplied heading remains step 1’s authoritative text and must never be offered for replacement.

- **Keep source categories separate.** `plan_tool/create.py:create_plan` currently rebinds `seed_body` after a `DistillOutcome.distilled` result. Retain the original extracted guardrail set separately so a model-added heading in distilled text cannot be mistaken for author-supplied content on the synthesis or rendering path.

- **Use the existing optional-section contract.** Extend the proposal rules around `OPTIONAL_PLAN_BODY_SECTION_SHAPES`, `_render_section_shapes_block`, `_validate_distilled_sections`, `_parse_body_sections_json`, `_render_distilled_markdown`, and `_render_plan_body` rather than opening arbitrary H2 passthrough. The three recognized guardrail names remain the complete allowlist.

- **Ask before rendering.** Present each non-empty candidate for a missing recognized heading and require an explicit accept or reject decision before adding it to the section data passed to `_render_plan_body`. Rejection omits the heading entirely; do not add a placeholder or preserve the candidate for implicit later acceptance.

- **Make approval safe by default.** Follow the safety pattern in `plan_tool/create.py:_review_step_gates`: interactive runs may prompt through the injected `input_fn`; `yes=True` and non-TTY runs must omit proposals rather than accept them. Do not treat Enter, a silent input function, or a cached model response as approval.

- **Avoid candidate rewriting and duplicate authority.** A proposal may fill only a missing heading. If distillation and synthesis both offer a value for one missing heading, choose a single candidate using a documented deterministic precedence or show one resolved candidate; do not merge their prose or ask the author to reconcile generated text in this step.

- **Keep prompt behavior grounded.** Update `plan_tool/prompts/distill-seed.md` and `plan_tool/prompts/synthesize-body.md` so they may propose a missing recognized guardrail from the seed’s stated work, but cannot invent arbitrary optional sections or revise supplied guardrails. The prompts must still keep `Steps` and `References` outside their JSON ownership.

- **Preserve existing body precedence.** Accepted proposals become normal optional-section input for `plan_tool/create.py:_render_plan_body`; supplied guardrails still outrank all generated content under step 1’s rule. Canonical section synthesis and the `Input` optional section keep their current behavior.

## Tests

- `test_missing_guardrails_are_exposed_as_candidates` — asserts only recognized headings absent from the original seed become proposal candidates.

- `test_supplied_guardrails_are_never_proposed_for_replacement` — asserts all three supplied headings bypass the approval prompt and retain their original bodies.

- `test_accepting_a_guardrail_candidate_renders_it` — asserts an explicit interactive acceptance writes the accepted heading and candidate body under its own H2.

- `test_rejecting_a_guardrail_candidate_omits_it` — asserts an explicit rejection leaves no heading or placeholder in the rendered plan.

- `test_yes_mode_omits_unapproved_guardrail_candidates` — asserts `create_plan(..., yes=True)` does not write model-proposed guardrails.

- `test_non_tty_omits_unapproved_guardrail_candidates` — asserts a non-interactive run does not call for approval or write candidates.

- `test_distilled_guardrail_candidate_is_not_mistaken_for_seed_content` — asserts rebinding `seed_body` after `DistillOutcome.distilled` cannot turn a generated proposal into supplied guardrail text.

- `test_prompt_contract_allows_missing_guardrail_proposals_only` — asserts `plan_tool/prompts/distill-seed.md` and `plan_tool/prompts/synthesize-body.md` describe missing-only proposals and supplied-text preservation.

### Test-creation order (feature step)

- Add candidate-classification tests with the implementation — cover original-seed presence, missing headings, and model-output separation.

- Add approval tests with the implementation — cover explicit accept, reject, `--yes`, and non-TTY behavior.

- Add the end-to-end `create_plan` regression — prove only accepted candidates reach the written plan.

Every new test must be green before this step is considered finished.

## Acceptance criteria

- A missing recognized guardrail may be proposed from existing distill or synthesis output, but it is not rendered until the author explicitly accepts it.

- A supplied `Scope guardrails`, `Audit guardrails`, or `Expected placement` section is never offered as a replacement and retains its supplied body.

- Rejecting a candidate leaves that heading absent from the new plan.

- `yes=True` and non-TTY creation omit all unapproved guardrail candidates without blocking for input.

- Generated headings from `DistillOutcome.distilled` cannot change which guardrails count as author-supplied.

- Unknown optional JSON keys remain rejected by `plan_tool/create.py:_parse_body_sections_json` and `plan_tool/create.py:_validate_distilled_sections`.

- `tests/test_create.py` passes.

## References

- [pytest output capturing](https://docs.pytest.org/en/stable/how-to/capture-stdout-stderr.html) — Use it to verify approval prompts and safe non-interactive messages without relying on terminal output.

## Deferred

- Broader create-wizard redesign for editing a proposed guardrail before acceptance — this step only accepts or rejects the generated candidate.

- Review or removal of guardrails after plan creation — keep proposal approval separate from concept storage and later plan editing workflows.
