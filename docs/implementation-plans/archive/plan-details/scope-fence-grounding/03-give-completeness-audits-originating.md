# Step 3 — Give completeness audits the originating scope contract

## Summary

Make the conceptual completeness audit read the originating seed’s scope contract when step 1 has recorded a plan’s `source_seed`, or when an older plan supplies the settled `--seed <path>` override. Update `plan_tool/review.py` to prepare that bounded input for the existing plan-audit prompt, and thread it through the normal `completeness-audit` path without any other CLI surface. Update `plan_tool/prompts/plan-audit.md` and `docs/AUDIT_FLOW.md` so the audit treats the contract as a hard boundary while still using the plan body and detail bundle to judge in-scope coverage. On green, seeded plans receive findings grounded in their real Outcome and exclusions; plans without a resolvable contract receive the exact current prompt.

## Table of Contents

- [Summary](#summary) — What this step delivers.
- [Table of Contents](#table-of-contents) — Quick links to each section.
- [Why](#why) — Why the audit needs the source scope in its prompt.
- [Input](#input) — The upstream provenance contract this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed by this step.
- [Implementation](#implementation) — Required scope-contract grounding behavior.
- [Tests](#tests) — Regression coverage for prompt and command behavior.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary reference for safe path handling.
- [Deferred](#deferred) — Provenance work left outside this step.

## Why

`plan_tool/prompts/plan-audit.md` tells the model to stay inside a seed/backlog scope contract, but `plan_tool/review.py:render_plan_audit_prompt` currently gives it only the plan body and detail bundle. The only plan-body sections that carry parts of that boundary are `## Out of scope` and `## Deferred`, so the audit cannot reliably distinguish an in-scope completeness gap from adjacent work the originating seed excluded. Step 1 records the durable source path; this step turns that provenance into audit input rather than asking the model to infer scope from a rewritten plan.

## Input

- **Step 1 provenance:** step 1 adds optional `Plan.source_seed`, a repo-relative path to the durable source used to create the plan. Treat it as the only source-contract pointer; do not guess from the plan slug or search nearby seed directories.
- **Prompt inputs:** `plan_tool/review.py:render_plan_audit_prompt` already reads the plan body and `_format_audit_detail_bundle`. Preserve those inputs and their missing/unreadable detail behavior.
- **Audit call path:** `plan_tool/cli/completeness_phases.py:_sample_conceptual_audit` calls `plan_tool/review.py:audit_plan_until_stable`, while `plan_tool/cli/completeness_cmd.py:cmd_completeness` also reaches the same audit during iteration. Both must receive the same contract through the shared review-layer path.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/review.py` — load and render the originating scope-contract block as part of `render_plan_audit_prompt`.
  - `plan_tool/cli/completeness_cmd.py` — keep both audit entry paths aligned with the shared scope-contract grounding behavior.
  - `plan_tool/prompts/plan-audit.md` — state how the supplied originating contract constrains completeness findings.
  - `docs/cli/completeness-audit.md` — regenerate the tracked CLI reference for the explicit `--seed` override.
  - `tests/test_review.py` — cover rendered scope-contract states and audit prompt safety.
  - `tests/cli/test_completeness_cmd.py` — cover completeness command forwarding through the shared audit seam.
  - `docs/AUDIT_FLOW.md` — document the contract as a real prompt input and its fallback behavior.

## Implementation

- **Foundational logic: scope-contract prompt grounding.** Give `plan_tool/review.py:render_plan_audit_prompt` the source material named by `Plan.source_seed`, then render it as a distinct input alongside the plan body and implementation bundle.

- **Use recorded provenance only.** Resolve `plan.source_seed` against `repo_root` and read that exact file when it is present and safe to read. The create path records the actual originating source when an existing canonical provenance pointer supplied the seed body; review must not re-walk provenance or search for another seed. The recommended approach is a small review-layer helper that returns a displayable contract block rather than making `check_plan_audit` or the CLI own file-path policy.

- **Keep the repository boundary.** Do not follow an absolute path, a path that escapes `repo_root`, or a malformed provenance value. Treat each as unresolved: emit no scope-contract block instead of reading outside the repository or silently substituting another seed.

- **Make absence non-fatal and invisible.** Existing plans and ordinary creates may have no `source_seed`. In that case, emit no scope-contract block and keep the rendered prompt byte-identical to current plan-body and detail-bundle behavior. A missing or unreadable recorded file must likewise produce no block, not turn `render_plan_audit_prompt` into `None` or suppress the conceptual audit.

- **Treat the source contract as a fence, not a second plan.** Update `plan_tool/prompts/plan-audit.md` so the model uses Outcome, In scope, Out of scope / Non-goals, Allowed behavior changes, Allowed reorganization, and `Audit guardrails` from the supplied source to decide whether a proposed gap belongs in this plan and whether audit conduct is permitted. Preserve the existing rule that in-scope gaps strengthen the plan and adjacent work becomes an INFO/LOW `[out-of-scope-deferred]` finding with a filing destination.

- **Do not let source prose override completed design detail.** The plan body and detail bundle remain the evidence for whether the plan operationalizes an in-scope concept. The originating contract sets the boundary; it must not cause the audit to resurrect source ideas that the source itself excluded or to disregard a detail file that already closes a plan-body gap.

- **Preserve prompt caching and audit parsing contracts.** Keep the static instructions before changing inputs in `plan_tool/prompts/plan-audit.md`; place the rendered source-contract block with the plan body, detail-bundle status, and detail files. Do not change `_PLAN_AUDIT_REQUIRED_HEADINGS`, `_parse_plan_audit_findings`, recommendation sources, stable anchors, or the two-section response format.

- **Truncate without hiding the fence.** Define a named fixed byte budget for the scope-contract block. When the resolved source exceeds it, render the contract headings `Outcome`, `In scope`, `Out of scope / Non-goals`, `Allowed behavior changes`, `Allowed reorganization`, `Scope guardrails`, `Audit guardrails`, and `Expected placement` in their source order, retain a bounded excerpt under every present heading, and append an explicit truncation marker. Do not silently first-bytes-clip the seed or omit an available constraint heading; no truncation occurs when the full contract fits the budget.

- **Keep both completeness modes consistent.** `plan_tool/cli/completeness_phases.py:_sample_conceptual_audit` and the `--iterate` audit call in `plan_tool/cli/completeness_cmd.py:_run_iterate_convergence_loop` must rely on `audit_plan_until_stable` rather than adding separate seed reads. This keeps audit-only, iterative, reused-report, JSON, and grouped-report behavior on one prompt contract.

- **Add only the settled override.** Add `--seed <path>` to the completeness-audit surface as an explicit override for plans authored before `source_seed` existed. It must take precedence over stored provenance, reject unsafe or unresolvable paths without guessing, and leave output byte-identical when neither source resolves. Do not add any other CLI surface or infer a seed by slug.

- **Do not reuse a different prompt.** An explicit `--seed` changes the conceptual-audit input, so it must force a fresh audit even when `--reuse-audit` is requested or a saved report otherwise matches the plan and code fingerprints. Record and test this precedence rather than returning findings generated against stored provenance or no contract.

- **Regenerate the affected CLI reference.** Run the repository's CLI-reference generator after adding `--seed`, and commit the resulting `docs/cli/completeness-audit.md` update. This is the generated artifact required by the existing drift gate, not a separate documentation initiative.

## Tests

- `tests/test_review.py:test_plan_audit_prompt_embeds_originating_scope_contract` — a plan with a repo-relative `source_seed` renders that source text in the conceptual-audit prompt.
- `tests/test_review.py:test_plan_audit_prompt_with_unresolvable_source_is_byte_identical` — a missing, unsafe, or escaping source produces no contract block and preserves the current prompt byte-for-byte.
- `tests/test_review.py:test_plan_audit_prompt_rejects_outside_repo_source_seed` — absolute or escaping provenance is not read and cannot expose outside-repository content.
- `tests/test_review.py:test_plan_audit_prompt_without_source_seed_is_byte_identical` — legacy or ordinary plans render no contract block and remain byte-identical to the current prompt.
- `tests/test_review.py:test_originating_scope_contract_trails_stable_prompt_instructions` — source content stays outside the reusable static prompt prefix.
- `tests/test_review.py:test_oversized_scope_contract_preserves_all_present_fence_headings` — an oversized seed has a visible marker while each present contract heading remains represented under the named block budget.
- `tests/cli/test_completeness_cmd.py:test_sample_conceptual_audit_uses_review_scope_contract_path` — the normal completeness phase reaches the shared review audit seam once with no duplicate CLI-level source handling.
- `tests/cli/test_completeness_cmd.py:test_iterate_conceptual_audit_uses_review_scope_contract_path` — the iterative conceptual audit uses the same shared seam.
- `tests/cli/test_completeness_cmd.py:test_seed_override_takes_precedence_and_rejects_unresolvable_paths` — the explicit `--seed` override wins over `source_seed`, and unsafe or unresolvable values produce no contract block without guessing.
- `tests/cli/test_completeness_cmd.py:test_seed_override_forces_fresh_audit_over_reuse` — an explicit `--seed` cannot reuse a saved audit whose prompt did not include that override.
- `tests/cli/test_cli_reference.py:test_every_generated_file_matches_disk` — the generated reference, including `--seed`, matches the argparse source.

### Test-creation order (feature step)

1. `tests/test_review.py` prompt-rendering cases — add the seeded, absent, unsafe, and legacy provenance cases with the review-layer implementation.
2. `tests/cli/test_completeness_cmd.py` command-path cases — add coverage that audit-only and iterative flows continue through the shared review seam.
3. `tests/cli/test_cli_reference.py` drift check — run the existing generated-reference gate after the command behavior is complete.

Every new test must be green before this step is considered finished.

## Acceptance criteria

- A plan whose step 1-provided `Plan.source_seed` points to a readable repo file includes that file’s scope contract in the prompt produced by `plan_tool/review.py:render_plan_audit_prompt`.
- The prompt tells the conceptual audit to treat the supplied Outcome, In scope, Out of scope / Non-goals, Allowed behavior changes, and Allowed reorganization as the boundary for completeness findings.
- The prompt also requires the conceptual audit to honor supplied `Audit guardrails`, including any explicit call-budget or deferral constraints.
- A missing, unreadable, absolute, or repository-escaping `source_seed` emits no scope-contract block without reading outside `repo_root`, failing the command, or suppressing the plan audit.
- A plan with no resolvable source (neither stored provenance nor `--seed`) renders a prompt byte-identical to the current plan-body and detail-bundle prompt.
- `--seed <path>` takes precedence over stored provenance; unsafe or unresolvable override paths are not read or guessed and fall back to the byte-identical no-contract prompt.
- `--seed <path>` forces a fresh conceptual audit rather than reusing findings generated without that override.
- An oversized scope contract retains every present scope-contract heading with a bounded excerpt and a visible marker rather than silently first-bytes-clipping the fence.
- Audit-only and `--iterate` completeness flows both reach `audit_plan_until_stable` with the same scope-contract behavior.
- `tests/test_review.py`, `tests/cli/test_completeness_cmd.py`, and `tests/cli/test_cli_reference.py` pass.

## References

- [Python pathlib](https://docs.python.org/3/library/pathlib.html) — Use path resolution and relative-path checks when validating a recorded repository-relative source path.

## Deferred

- Backfilling `source_seed` on existing plans — step 1 makes provenance available for newly seeded plans; inferring it for older plans would require a separate, reviewable migration policy.
- Parsing the source contract into a new persisted schema — this step supplies the original text as audit context and does not create a second canonical representation of scope.
