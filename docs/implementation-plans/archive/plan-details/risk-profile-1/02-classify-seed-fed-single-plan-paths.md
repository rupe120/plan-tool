> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Classify seed-fed single-plan paths and default no-source create to standard

## Summary

Add one private risk-classification boundary to `plan_tool/create.py` for every seed-fed create that can publish a single plan. Create a strict seed-only prompt at `plan_tool/prompts/classify-risk-profile.md`, a representative low-risk deletion fixture, and focused parser, routing, resume, and fallback coverage in `tests/test_create.py`. The key decision is that only affirmative seed evidence with no independently detected positive counter-signal can propose `low`; malformed, ambiguous, counter-signalled, unavailable-classifier, and no-source cases start at `standard`. On green, split proposals remain no-write exits, no-source create makes no classifier call, and step 3 receives one bounded internal proposal to resolve with the operator.

## Table of Contents

- [Summary](#summary) — Reviewer-level result and main design choice.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why seed classification needs one safe create boundary.
- [Input](#input) — Existing source and split contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files created and changed.
- [Implementation](#implementation) — Classification policy, routing, and safety rules.
- [Tests](#tests) — Focused test coverage and green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary documentation for the response and terminal boundaries.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that limit this step.
- [Deferred](#deferred) — Adjacent work owned by later steps.

## Why

`plan_tool/create.py:_prepare_create_plan` currently knows whether it has seed prose and whether distillation returned a single plan or a split, but it has no shared way to turn affirmative low-risk evidence into a bounded proposal. Putting that judgment inside `propose_distilled_seed_from_claude` would miss canonical-small and `--no-distill` sources, while allowing a missing or bad response to choose `low` would weaken the safety signal before it reaches the operator. This step adds one conservative seam before publication so every eligible source route behaves the same way.

## Input

- **Step 1 declaration vocabulary:** Step 1 creates the risk-tier vocabulary and plan-frontmatter fields. Use that landed vocabulary for the private proposal and fallback values; do not redefine the tier set in this step.
- **Seed selection:** `plan_tool/create.py:_prepare_create_plan` already chooses `raw_seed` from `seed_body` before `from_description`, then derives `body_source` after distillation. Classify the original selected seed so provenance-backed seed evidence is not lost during distillation.
- **Split boundary:** `plan_tool/create.py:DistillOutcome`, `propose_distilled_seed_from_claude`, and `_parse_distill_json` distinguish a single result, a passthrough, and a multi-plan split. A split remains a no-write exit and must bypass classification.
- **Caller boundary:** `plan_tool/cli/authoring.py:cmd_create` already passes inline and file-derived source text into `create_plan`. Keep the public `plan_tool/create.py:create_plan` signature stable and make the policy private to the existing create flow.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/prompts/classify-risk-profile.md` — Define the seed-only, JSON-only classifier contract and the evidence needed for a low proposal.
  - `tests/fixtures/create/remove-vendor-scraper-poc-seed.md` — Provide a self-contained deletion-shaped seed with the affirmative evidence used by the low-risk characterization test.

- **Existing files (edits only):**
  - `plan_tool/create.py` — Add the private proposal/result parsing, conservative fallback, checkpoint handling, prompt rendering, and single-plan route through `_prepare_create_plan`.
  - `TESTING.md` — Extend the `create_plan(claude_invoker=...)` guidance so tests also neutralize the new classifier call with a canned response or a module-level stub.
  - `tests/test_create.py` — Add isolated contract tests and create-flow coverage for every source route, fallback, split, no-source, and resume rule affected here.

## Implementation

- **Classify once after split admission.** Add a private proposal record near `DistillOutcome` and its helpers in `plan_tool/create.py`. It must carry the proposed tier, a non-empty one-line evidence-based rationale, and the lowest tier step 3 may later persist. Keep it inside `PreparedCreatePlan` or an equivalent pre-publication handoff; do not add it to `CreateResult`.

- **Use the original selected seed.** In `plan_tool/create.py:_prepare_create_plan`, preserve the existing `seed_body`-before-`from_description` precedence when building classifier input. Run the classifier after distillation has established that the result is not a split, but do not classify the distilled replacement text: the original seed is the evidence source.

- **Cover every single-plan seed route with the same policy.** The classification helper must serve inline `--from`, direct `--from-existing`, provenance-backed `seed_body`, canonical-small distill skips, successful distillation, distill passthrough, and `--no-distill`. Do not add a second policy in `plan_tool/cli/authoring.py:cmd_create` or `plan_tool/create.py:propose_distilled_seed_from_claude`.

- **Keep split behavior unchanged.** When `DistillOutcome.is_split` is true, return the existing `CreateResult.split_proposal` before a classifier call, plan write, manifest update, or risk-proposal handoff. A single-entry or malformed split remains governed by `_parse_distill_json` and its existing fallback behavior.

- **Make `low` an admitted result, not a guess.** The classifier response must carry one non-empty supporting excerpt for each admission condition—deletion dominance, no consumer, and no new external, schema, API, contract, or runtime surface—and the parser must verify that every excerpt occurs in the original selected seed. Before accepting a `low` response, a small policy-owned deterministic source screen must examine that same seed for the plan’s positive counter-signal classes: named consumer, contract, migration, auth/authz concern, and new external, schema, API, or runtime surface. The screen distinguishes explicit negative evidence such as a no-consumer claim from a positive signal; it is not derived from the model response. Any detected positive counter-signal sets the lowest allowed tier to `standard`, even when the response supplies otherwise valid low evidence and omits the signal.

- **Fail closed to `standard`.** Treat an unavailable or failed classifier invocation, absent source text, malformed JSON, unknown fields or tier values, a blank or multiline rationale, missing required evidence, support absent from the original selected seed, contradictory evidence, and an otherwise ambiguous response as an explicit `standard` proposal with a non-empty one-line fallback rationale. The model may not make `high` automatic; reserve that escalation for step 3’s operator decision.

- **Skip the model with no source.** A create with neither `seed_body` nor `from_description` must build the explicit standard proposal deterministically, make no classifier invoker call, and ask no risk-tier question. It may continue through the existing manual step-entry path.

- **Keep the prompt narrow and hermetic.** Render `plan_tool/prompts/classify-risk-profile.md` through `plan_tool/renderer.py:prompts_dir` and the established `string.Template` path used by `_render_distill_prompt`. Tell the model to use only supplied seed text, return one closed JSON shape with a non-empty one-line rationale, and cite the affirmative evidence in that rationale; do not tell it to inspect the repository or open repository-local format documents.

- **Give the classifier its own revision-aware resume identity.** Follow the checkpoint pattern in `plan_tool/create.py:propose_distilled_seed_from_claude` rather than storing a classification response in the distill checkpoint. The cache key must change when the selected source, full predicted plan target, or classifier prompt/policy revision changes; resume may reuse only a matching non-replacement proposal, `resume=False` must invoke fresh, and normal completed create must clean the new checkpoint. A registered collision at the same target stops before this checkpoint is read, an explicitly authorized replacement starts with a fresh proposal, and target identity prevents another filename or output location from consuming a prior attempt's proposal.

- **Leave declaration ownership with step 3.** This step supplies a bounded internal proposal and fallback only. Do not prompt for acceptance or override, write `Plan.risk_profile` or `Plan.risk_profile_rationale`, emit the final risk-decision run-log record, or change the completion summary.

## Tests

- `test_risk_profile_prompt_requires_seed_only_closed_json` — Asserts that `plan_tool/prompts/classify-risk-profile.md` requires seed-only evidence, the allowed automatic tiers, and JSON-only output.
- `test_parse_risk_profile_low_requires_seed_grounded_admission_evidence` — Asserts that a low proposal needs a non-empty excerpt from the selected seed for every affirmative condition as well as a one-line rationale.
- `test_parse_risk_profile_source_counter_signal_sets_standard_floor` — Asserts that each named consumer, contract, migration, auth/authz, external, schema, API, and runtime-surface counter-signal in the selected seed sets the standard floor, while the fixture’s explicit negative evidence does not; the model cannot avoid that floor by omitting the signal from its response.
- `test_parse_risk_profile_unsupported_or_ambiguous_response_defaults_to_standard` — Asserts that malformed, unknown, incomplete, invented-support, blank-rationale, multiline-rationale, and contradictory responses fail closed with a one-line standard rationale.
- `test_risk_classifier_invocation_failure_defaults_to_standard` — Asserts that an invoker failure on any seed-fed single-plan route records the deterministic standard proposal rather than aborting create.
- `test_remove_vendor_scraper_fixture_proposes_low` — Uses `tests/fixtures/create/remove-vendor-scraper-poc-seed.md` to prove the deletion-shaped characterization input can produce a low proposal only from its stated evidence.
- `test_seed_body_precedence_controls_risk_classification_input` — Asserts that a provenance-backed `seed_body` is classified instead of the canonical `from_description`.
- `test_seed_fed_single_plan_routes_share_risk_classification_policy` — Covers inline, direct-file, canonical-small, distilled-single, distill-passthrough, and `--no-distill` routes with the same classifier result contract.
- `test_split_proposal_skips_risk_classification_and_publication` — Asserts that the existing split exit invokes neither the classifier nor publication.
- `test_no_source_create_uses_standard_without_classifier_call` — Asserts that source-free creation receives the deterministic standard proposal and does not call the injected invoker.
- `test_risk_classification_checkpoint_reuses_matching_source_target_and_revision` — Asserts that a resumed non-replacement create reuses a matching classifier response and that source, full predicted target, or classifier policy changes invalidate it.
- `test_replacement_create_does_not_reuse_risk_classification_checkpoint` — Asserts that an explicitly authorized replacement resolves a fresh proposal even if its source and output otherwise match a saved checkpoint.
- `test_no_resume_risk_classification_invokes_fresh` — Asserts that `resume=False` does not consume a saved classifier response.
- `test_create_plan_signature_is_exact` — Remains unchanged to prove this private behavior adds no public `create_plan` parameter.

### Tests for this step

Every test above must be green before this step is complete. Run `uv run pytest tests/test_create.py -q` during implementation, then run the plan’s configured test command before handoff.

## Acceptance criteria

- A seed-fed single-plan create produces one private proposal using `RiskProfile` from step 1.
- A low proposal is possible only when parser-verified excerpts from the selected source support every affirmative low-risk condition and the deterministic source screen detects no positive counter-signal; counter-signals and ambiguous input have a standard minimum.
- Inline, file-backed, provenance-backed, distill-skipped, distilled-single, passthrough, and `--no-distill` sources use the same classifier boundary.
- A split proposal follows the existing no-write path and does not invoke classification.
- No-source create produces an explicit standard proposal and rationale without invoking the classifier or prompting for a risk decision.
- An invalid classifier response or invocation failure, including one with a blank or multiline rationale, produces a one-line standard declaration rather than a model-selected low or high result.
- A matching classifier checkpoint resumes only for the same source, full predicted target, and classifier revision on a non-replacement create; `--no-resume` and explicit replacement call the classifier again, normal finalization removes the checkpoint, and a registered collision at the same target is refused before classification resumes.
- `plan_tool/create.py:create_plan` keeps its existing callable signature.
- `TESTING.md` tells contributors how to keep classifier tests hermetic, and `uv run pytest tests/test_create.py -q` passes.

## References

- [Claude Code CLI referencehttps: — Review the non-interactive invocation boundary that the existing create invoker uses.
- [json — JSON encoder and decoderhttps: — Review JSON decoding and parse-failure handling for the closed classifier response.
- [io — Core tools for working with streamshttps: — Review terminal detection used to keep source-free and silent create paths non-blocking.

## Applicable guardrails

- **The plan’s “## Plan intent”, operator-owned declaration:** Produce an evidence-bound proposal only; final acceptance and persistence remain with step 3.
- **The plan’s “## Step intent”, conservative declaration policy:** Admit `low` only from affirmative seed evidence and use standard when no source supports a lower tier.
- **The plan’s “## Out of scope”, downstream consumers:** Do not change detail authoring, completeness, apply, run, or Jira behavior.
- **The plan’s “## Out of scope”, non-TTY model acceptance:** Do not create a silent model-acceptance path; source-free and other fallback results remain standard inputs for step 3.
- **The plan’s “## Out of scope”, existing-plan and split behavior:** Do not migrate old plans, change split handling, or extend annotate and scope-out seed flows.

## Deferred

- Operator acceptance, override, decline, final frontmatter write, and risk-decision logging — Step 3 owns the final declaration before publication.
- Create completion output — Step 4 owns rendering the persisted declaration.
- Downstream tier consumption and corpus calibration — remain outside this plan step’s create classification boundary.
