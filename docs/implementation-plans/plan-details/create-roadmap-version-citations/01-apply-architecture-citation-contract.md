# Step 1 — Preserve selected roadmap citations in generated create prose

<!-- plan-tool:detail-format-version: 1 -->

## Summary

When a covered `create --from-existing` writer cites a roadmap artifact, it uses the exact repository-relative version-store path that the selected source ties to the claim. `plan_tool/create.py` carries the original citation evidence into step proposal and fallback synthesis even when preparation drops it. The body prompts and the split-mode sweep apply the same rule, including on repairs. Saved step and body proposals are reusable only when their citation evidence matches the selected source.

## Table of Contents

- [Summary](#summary) — The outcome and the main design decision.
- [Table of Contents](#table-of-contents) — The sections in this detail.
- [Why](#why) — Where create can lose the path that supports a claim.
- [Input](#input) — Source authority, citation format, and checkpoint inputs.
- [Files (creates vs edits)](#files-creates-vs-edits) — The prompts, orchestration code, and tests in scope.
- [Implementation](#implementation) — The citation rule and how it reaches each writer.
- [Tests](#tests) — Prompt capture, writer routing, and checkpoint replay cases.
- [Acceptance criteria](#acceptance-criteria) — Observable conditions for completing this step.
- [References](#references) — The source contracts and existing coverage.
- [Applicable guardrails](#applicable-guardrails) — The boundaries on this change.
- [Deferred](#deferred) — Follow-up work outside this step.

## Why

`plan_tool/create.py:_prepare_create_plan` gives preparation the selected raw seed, then replaces the working description with normalized Markdown and restores the source's `## References`. A citation in another section can disappear from the text later writers receive. A saved step or synthesis response can also replay against identical normalized prose even when the omitted path changes versions. A bare member filename can send a reader to an inert top-level copy or a missing file instead of the artifact that supports the claim.

## Input

- **Selected source.** `plan_tool/create.py:select_file_backed_source` gives `seed_body` precedence when supplied, including when empty. Otherwise it selects `from_description`. Use that same source for citation evidence, including claim context outside `## References`.
- **Citation form.** `ROADMAP_FORMAT.md` under “Citing roadmap files” defines the repository-relative form, such as `docs/implementation-plans/roadmaps/<slug>/.roadmap-versions/<version-id>/04-roadmap.md`. The plan's `## Architecture` makes the path tied to the claim authoritative even after the accepted head moves.
- **Saved proposals.** `plan_tool/create.py:_distill_seed_input_hash`, `plan_tool/create.py:_initial_steps_input_hash`, and `plan_tool/create.py:_body_sections_input_hash` govern reuse of preparation, step, and synthesis responses. Preparation already keys on raw source and prompt identity. The downstream keys currently use the working description or body source.
- **Verification limit.** Canned invokers establish which instructions and evidence reach a writer and how its response flows through create. Step 2 owns the fresh-run proof of model compliance in generated body prose and step text.

## Files (creates vs edits)

**New files**

- None.

**Existing files**

- `plan_tool/create.py` — Retain selected-source evidence across normalization, supply it to the covered prompts and re-proposals, and include it in step and synthesis replay identity.
- `plan_tool/prompts/distill-seed.md` — Make the roadmap citation rule explicit in the preparation instructions.
- `plan_tool/prompts/synthesize-body.md` — State the rule and expose selected-source citation evidence alongside the working seed.
- `tests/test_create.py` — Cover step and synthesis prompts, consolidation, re-proposal, resume, and route regressions.
- `tests/test_distill.py` — Cover the preparation prompt and repair using the selected raw source.

## Implementation

The core rule is **preserve the selected source's full version-store path when citing the claim it supports**. Render one shared instruction block only for file-backed authoring, including when its source provides no usable citation. When the source supplies no usable path, or cites multiple versions without tying one to the claim, the writer must omit the file citation. It may still state a supported claim in prose. Apply the omission rule only to generated prose. Copy protected source text verbatim when the existing route requires it. A head change or another version found during codebase inspection cannot supply the citation.

- **Capture evidence before normalization.** Retain the selected raw source's citation evidence in `plan_tool/create.py:_prepare_create_plan` before it rebinds `seed_body` and `from_description`. Keep enough surrounding text to tell which claim each path supports, including when two versions name the same member. A small prompt-only source excerpt is one way to carry that context. Reuse the raw source already present in a writer's prompt where it supplies the evidence. Keep the evidence out of the normalized body and References inputs so adding it cannot change what gets copied or researched.
- **Preparation.** Render the file-backed instruction block alongside the existing concrete-path rule in `plan_tool/prompts/distill-seed.md`. The numbered source already supplies citation evidence. `plan_tool/create.py:propose_distilled_seed_from_claude` already calls `_render_distill_prompt` with the same numbered raw source for both attempts. Preserve the split and refusal decisions and the source spans that materialize evidence-only fields.
- **Fallback synthesis.** Supply the evidence through `plan_tool/create.py:propose_body_sections` and `plan_tool/create.py:_render_synthesis_prompt` on the first call and the re-rendered repair. Make the citation block an explicit permitted source of citation evidence in the rendered synthesis instructions. Existing limits on the sources of plan claims still apply. The normal `plan_tool/create.py:_prepare_create_plan` branch still decides when synthesis runs. An accepted normalized map with no `Deferred` text can exercise the fallback, while a complete normalized map and direct source authority bypass it. Preserve the existing precedence of preparation and source-materialized sections over fallback output, as well as the separate local-code and documentation inputs.
- **Combined and split step proposal.** Render the conditional block in the common part of `plan_tool/create.py:_render_from_prompt` and supply the evidence at both initial `propose_steps_from_claude` call sites. The existing repair appends to the original prompt. A direct source with strict steps still lifts those steps without a proposal. Carry the evidence through `plan_tool/create.py:_CreatePlanContinuation` into `_CreatePlanConvergence` so `_converge_create_plan` supplies it when a round re-proposes steps. Retain the existing skip for eligible prose-only rounds and the fresh invocation for rounds that do re-propose.
- **Split-mode consolidation.** `plan_tool/create.py:propose_steps_from_claude` passes `_render_sweep_context` into `plan_tool/foundational_logic.py:run_foundational_logic_sweep`. Give that create call the rule and source evidence. Its repair already appends to the rendered prompt. Cover the consolidation title, intent, and rationale because `plan_tool/foundational_logic.py:merge_sweep_into_steps` can publish the rationale as the step's intent. Include the create-only block in the existing caller-supplied sweep context. The shared sweep renderer and detail callers use their existing interfaces. This sweep belongs to `--prompt-mode split`. The raw-source split assessment and a preparation result that proposes multiple plans retain their separate routes.
- **Resume.** Extend `plan_tool/create.py:_initial_steps_input_hash` and `plan_tool/create.py:_body_sections_input_hash` with the selected citation evidence used for generation. The identity distinguishes a file-backed prompt that received the rule with empty citation evidence from a legacy prompt that lacked the rule. A saved affected proposal whose key cannot establish that match must miss. Identical evidence remains eligible for reuse under the current resume rules, and unrelated callers keep their existing cache behavior. Use the existing checkpoint records and the source selected on re-entry. Preserve the current split sweep behavior on a step checkpoint hit.
- **Publication and scope.** Keep citation handling at prompt assembly and checkpoint identity. A publish-time filename replacement would lose the relationship between the claim and its source version, and could change copied text. Preserve `plan_tool/create.py:_publish_create_plan` and `_finalize_create_plan`, the tracked-seed checks in `plan_tool/cli/authoring.py:cmd_create`, and the separate References research calls.

## Tests

### Tests for this step

Use the existing fake invokers to capture the actual prompts. Every case below must be green before the step is complete.

- `tests/test_distill.py::test_preparation_and_repair_receive_selected_source_citation_rule` — Both sends carry a full path found only outside References and explain when to omit the citation. The normalized fixture may drop the path while keeping the source-supported section contract.
- `tests/test_create.py::test_normalized_step_proposal_and_repair_keep_selected_citation_evidence` — Both proposal modes and their repairs see the path dropped during normalization. A conflicting path in the unselected description supplies no citation evidence.
- `tests/test_create.py::test_normalized_fallback_synthesis_and_repair_keep_dropped_citation_evidence` — An accepted incomplete preparation takes the existing fallback route. Both synthesis sends carry the omitted path and the omission instruction. Source-materialized sections retain precedence.
- `tests/test_create.py::test_split_sweep_and_repair_keep_citation_evidence_for_consolidation` — Both sweep sends carry the rule and source context. A canned result carrying the exact path reaches the consolidation title or intent, including the rationale fallback.
- `tests/test_create.py::test_iteration_step_reproposal_keeps_original_citation_evidence` — A round that actually re-proposes steps supplies the original evidence to ordinary proposal and, in split mode, to its sweep even when the working description lacks the path.
- `tests/test_create.py::test_resume_reuses_only_proposals_for_matching_selected_citation_evidence` — Exercise both step and synthesis checkpoints. With the same slug, destination, and working prose, matching evidence permits a cache hit, while changing only the omitted version path forces a live call that receives the replacement path. A legacy key misses for a file-backed seed without citations, and inline input retains its historical key.
- `tests/test_create.py::test_covered_prompts_require_claim_specific_paths_and_allow_omission` — Across the covered writers, inspect the instructions for exact path preservation, omission when the path is missing, and omission when two cited versions cannot be tied to the claim. Use source text with both versions to verify that the evidence keeps their claim context. Check that protected copied sections retain their source bytes, that synthesis admits the citation block as evidence, and that inline preparation, proposal, and synthesis do not receive it.

Keep the existing direct-source copy, strict-step lift, normalized References restoration, complete-preparation synthesis skip, and publication regression cases green in `tests/test_create.py` and `tests/test_distill.py`. Run `uv run pytest tests/test_create.py tests/test_distill.py tests/test_foundational_logic.py -q` for the focused suite. `tests/test_foundational_logic.py` is verification-only.

## Acceptance criteria

- Captured preparation, fallback synthesis, step proposal, and split consolidation prompts carry the claim-specific citation instruction and selected-source evidence on each applicable send, including repairs and step re-proposals.
- A full path present only outside References is still available to later writers when the normalized Markdown omits it. Paths for different versions of the same member retain their supporting context.
- Changing only an omitted version path prevents replay of both affected step and fallback synthesis responses. Matching evidence still allows replay under the existing resume policy.
- Inline authoring, direct source body copying, strict step lifting, normalized source protections, References research, and create publication pass their existing regression checks.

## References

- [Originating bug](BUG_BACKLOG.md#bare-roadmap-file-names-in-prose-creates-model-writes-during-synthesis-resolve-to-inert-top-level-copies-beside-an-accepted-head) — Describes how a shortened citation can send readers to an inert copy.
- [Roadmap path convention](ROADMAP_FORMAT.md#path-convention) — Defines the immutable version store. See also “Citing roadmap files” in the same document.
- [File-backed create workflow](docs/how-to/pipeline/create-from-existing.md#file-backed-decision-flow) — Describes direct, normalized, split, and refused outcomes and who owns their prose.
- [Create recovery](docs/how-to/recovery/create.md#what-resumes-on-a-re-run) — Lists the proposal checkpoints and their replay rules.

## Applicable guardrails

- **The plan's `## Architecture`, claim and version authority** — Use the originally selected source for every covered writer and for the replay decision.
- **The plan's `## Scope guardrails`, source and publication authority** — Apply the change to authoring inputs while preserving the existing routing and write boundaries.
- **The plan's `## Audit guardrails`, prompt proof** — Verify the named property through prompt evidence and the existing workflow.
- **The plan's `## Expected placement` and `## Out of scope`, writer boundary** — Limit edits to the covered create writers and focused tests. The neighboring authoring and roadmap routes keep their current contracts.

## Deferred

- Deterministic post-synthesis citation checks and path rewriting — The plan reserves any such change for separate evidence from a fresh run.
- Model compliance measurement beyond the representative proof — Step 2 owns that proof and the resulting backlog disposition. Estimating compliance across sources would require more live runs.
