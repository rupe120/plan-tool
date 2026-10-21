# Step 6 — Ground conceptual audits in the source contract

## Summary

Ground `completeness-audit` in the plan’s originating scope contract, using step 4’s stored `Plan.source_seed` or step 5’s explicit `--seed` override. Update the review-layer prompt assembly, the two completeness audit entry paths, and the model-facing audit contract so the source defines the audit boundary while the plan body and detail bundle remain the implementation evidence. Document the added prompt input in `docs/AUDIT_FLOW.md` and cover safe resolution, precedence, truncation, and shared command behavior. On green, conceptual findings stay inside the supplied source contract without weakening audits for plans that have no usable source.

## Table of Contents

- [Summary](#summary) — The source-contract grounding delivered by this step.
- [Table of Contents](#table-of-contents) — Links to each detail section.
- [Why](#why) — Why the conceptual audit needs the original scope boundary.
- [Input](#input) — Upstream provenance and audit-call contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — The files changed for prompt grounding.
- [Implementation](#implementation) — Source selection, safe rendering, and audit rules.
- [Tests](#tests) — Prompt and command-path regression coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary documentation for path and prompt handling.
- [Deferred](#deferred) — Work intentionally left outside this step.

## Why

`plan_tool/prompts/plan-audit.md` already tells the model to stay inside a source scope contract, but `plan_tool/review.py:render_plan_audit_prompt` currently supplies only the plan body and detail bundle. That leaves the audit to infer exclusions and allowed changes from rewritten plan prose, so it can raise adjacent work as a completeness gap. Steps 4 and 5 establish durable and explicit provenance; this step makes that provenance a real audit input.

## Input

- **Step 4 provenance** — Step 4 provides optional `Plan.source_seed`, a verified repo-relative path to the source that supplied the plan’s body and guardrails. Do not infer a replacement from a slug, neighboring files, or archive naming.

- **Step 5 override** — Step 5 adds `args.seed` for `completeness-audit`. A supplied override takes precedence over `Plan.source_seed` and has already forced a fresh audit; this step owns resolving its path and rendering its content.

- **Existing audit inputs** — `plan_tool/review.py:render_plan_audit_prompt` collects the plan body through `_collect_plan_body`, detail status through `audit_detail_bundle_status`, and detail content through `_format_audit_detail_bundle`. Preserve these inputs and their current missing-detail behavior.

- **Shared audit paths** — Audit-only mode enters through `plan_tool/cli/completeness_phases.py:_sample_conceptual_audit`; iterative mode calls `plan_tool/review.py:audit_plan_until_stable` from `plan_tool/cli/completeness_cmd.py:_run_iterate_convergence_loop`. Both must receive the same source-contract behavior.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `docs/AUDIT_FLOW.md` — describe the source contract as a conceptual-audit input, its boundary role, and the safe no-contract fallback.
  - `plan_tool/cli/completeness_cmd.py` — pass the step 5 `--seed` value through both conceptual-audit entry paths without adding a second source-reading policy.
  - `plan_tool/prompts/plan-audit.md` — tell the audit how to use a supplied source contract and how to handle out-of-scope observations.
  - `plan_tool/review.py` — resolve, bound, and render the source-contract block from stored provenance or an explicit override as part of `render_plan_audit_prompt`.
  - `tests/cli/test_completeness_cmd.py` — cover override forwarding and parity between audit-only and iterative paths.
  - `tests/test_review.py` — cover source selection, repository safety, prompt placement, and bounded contract rendering.

## Implementation

- **Foundational logic: resolved-contract prompt grounding.** Extend `plan_tool/review.py:render_plan_audit_prompt` so a usable source contract is rendered beside the plan body and detail bundle, augmented only with author-approved guardrail sections that the source lacked. Label those additions as author-approved plan guardrails; do not treat either input as a second plan or a replacement for the other.

- **Keep source selection in the review layer.** A small helper near `render_plan_audit_prompt` is a good fit for choosing the explicit override first and otherwise `Plan.source_seed`, validating the candidate, and returning a display-ready block. Thread the override through `check_plan_audit` and `audit_plan_until_stable`; do not duplicate file reads in `plan_tool/cli/completeness_cmd.py` or `plan_tool/cli/completeness_phases.py`.

- **Honor explicit override precedence.** When `args.seed` is present, use that value as the only candidate. If it is unsafe or unreadable, continue with no source-contract block rather than falling back to stored provenance, guessing another file, failing the audit, or reading outside the repository.

- **Enforce the repository boundary.** Accept only a readable source file contained by `repo_root`. Reject absolute paths, escaping relative paths, directories, and unreadable files. `Plan.source_seed` is repo-relative provenance from step 4; apply the same containment rule to the override after resolving it.

- **Keep no-contract behavior non-fatal.** Legacy plans, ordinary creates, missing files, and invalid paths must still reach `check_plan_audit` and `audit_plan_until_stable`. When neither candidate yields a usable source, render no source block and preserve the existing plan-body/detail-bundle prompt content.

- **Use the contract as a fence.** Update `plan_tool/prompts/plan-audit.md` so source `Outcome`, `In scope`, `Out of scope` or `Non-goals`, `Allowed behavior changes`, `Allowed reorganization`, and any supplied `Scope guardrails`, `Audit guardrails`, or `Expected placement` constrain what can become a correctness or completeness finding. The plan body and implementation bundle still decide whether an in-scope promise is operationalized.

- **Carry accepted additions into the resulting fence.** When step 2 has written an author-approved guardrail that was absent from the source, append that exact plan-body section to the resolved-contract block with its approval provenance. Do not use arbitrary plan prose, rewrite a source-supplied guardrail, or infer approval from a generated heading that never passed step 2's decision.

- **Keep out-of-scope work deferred.** Preserve the prompt’s `[out-of-scope-deferred]` convention: adjacent ideas receive an INFO or LOW deferred finding with a filing destination, not a proposed step or a broadened plan. A source contract must never revive an explicitly excluded idea.

- **Bound large source input without hiding fences.** Use a named contract-size limit. When a source exceeds it, retain every present scope-contract heading in source order with a bounded excerpt and an explicit truncation marker; do not use a simple first-bytes cut that can drop exclusions or guardrails.

- **Preserve prompt and parser contracts.** Keep static instructions ahead of dynamic inputs in `plan_tool/prompts/plan-audit.md`, and keep the source block with the existing plan body, detail-status, detail-bundle, and carried-findings inputs. Do not change `_PLAN_AUDIT_REQUIRED_HEADINGS`, `_parse_plan_audit_findings`, stable anchor handling, or the two finding sources.

- **Document the same rule operators receive.** Update the `completeness` conceptual-layer description in `docs/AUDIT_FLOW.md` to say that source grounding is optional, uses recorded provenance or `--seed`, and limits audit scope without replacing plan or detail evidence.

## Tests

- `test_plan_audit_prompt_embeds_stored_source_contract` — a readable in-repository `Plan.source_seed` appears in the rendered conceptual-audit prompt.

- `test_plan_audit_prompt_seed_override_wins_over_stored_provenance` — the explicit source is rendered instead of the stored source.

- `test_plan_audit_prompt_rejects_unsafe_or_unreadable_source` — absolute, escaping, directory, missing, and unreadable candidates are never read and do not suppress the audit prompt.

- `test_plan_audit_prompt_without_usable_source_preserves_existing_inputs` — a legacy plan still renders its plan body and detail bundle with no source-contract block.

- `test_plan_audit_prompt_places_contract_after_static_instructions` — dynamic source content stays outside the stable prompt prefix.

- `test_oversized_source_contract_retains_present_scope_headings` — each present scope and guardrail heading remains represented and the prompt marks truncation.
- `test_audit_prompt_includes_author_approved_missing_guardrail` — a plan-body guardrail approved through step 2 supplements a source that lacked it, while unapproved or source-supplied sections are not duplicated.

- `test_audit_only_forwards_seed_override_to_review_audit` — `plan_tool/cli/completeness_phases.py:_sample_conceptual_audit` reaches the shared review seam with the override.

- `test_iterative_audit_forwards_seed_override_to_review_audit` — the conceptual call in `plan_tool/cli/completeness_cmd.py:_run_iterate_convergence_loop` uses the same source-contract path.

### Test-creation order (feature step)

1. Add `tests/test_review.py` cases for stored provenance, explicit override precedence, and invalid-path fallback with the review-layer implementation.

2. Add `tests/test_review.py` coverage for prompt placement and bounded source rendering.

3. Add `tests/cli/test_completeness_cmd.py` cases proving audit-only and iterative mode forward the same override into the shared review path.

4. Every new test must be green before this step is considered finished.

## Acceptance criteria

- A readable, in-repository `Plan.source_seed` from step 4 appears as a distinct source-contract block in the prompt from `plan_tool/review.py:render_plan_audit_prompt`.

- `--seed` takes precedence over stored provenance for both audit-only and iterative `completeness-audit` runs.

- An unsafe, unreadable, missing, or directory source is not read, does not fall back from an explicit override to stored provenance, and does not prevent the conceptual audit from running.

- The prompt directs the model to use supplied source scope, exclusions, allowed changes, allowed reorganization, and guardrails as the boundary for findings.

- The plan body and detail bundle remain the evidence for whether an in-scope idea is already covered.

- An oversized source contract retains every present scope-contract heading with a bounded excerpt and visible truncation marker.

- `docs/AUDIT_FLOW.md`, `tests/test_review.py`, and `tests/cli/test_completeness_cmd.py` reflect the same source-grounding behavior.

## References

- [pathlib — Python Standard Library](https://docs.python.org/3/library/pathlib.html) — Use for containment checks and readable-path handling.

- [Claude API Messages Reference](https://platform.claude.com/docs/en/api/messages) — Use for prompt-input and instruction ordering considerations.

## Deferred

- Backfilling `source_seed` on older plans — step 4 records provenance for newly created seeded plans; inferring historical provenance needs a separate migration decision.

- Parsing source contracts into a persisted schema — this step supplies bounded source text to the audit and keeps the source document as the contract of record.
