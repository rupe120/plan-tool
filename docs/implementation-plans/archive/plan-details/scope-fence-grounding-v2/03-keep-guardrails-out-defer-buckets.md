# Step 3 — Keep guardrails out of defer buckets

## Summary

Keep `Scope guardrails`, `Audit guardrails`, and `Expected placement` out of the body-section buckets that `plan-tool create` and `plan-tool detail` can defer. Update `plan_tool/create.py` and `plan_tool/detail.py` to use one guardrail eligibility rule, then cover both authoring paths in `tests/test_create.py` and `tests/test_detail.py`. The key decision is to exclude only the three guardrail sections, not every optional section. On green, guardrails remain visible plan constraints but cannot be proposed, accepted, or persisted as deferred concepts.

## Table of Contents

- [Summary](#summary) — The defer-bucket restriction delivered by this step.
- [Table of Contents](#table-of-contents) — Links to the detail sections.
- [Why](#why) — Why guardrails must remain active constraints.
- [Input](#input) — The guardrail contract supplied by step 1.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed for the restriction.
- [Implementation](#implementation) — The shared eligibility rule and both authoring paths.
- [Tests](#tests) — Regression coverage for create and detail.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Test guidance.
- [Deferred](#deferred) — Work outside this step.

## Why

Step 1 makes guardrail sections part of a plan body, and step 2 can add approved missing guardrails, but the current concept bootstrap treats every H2 section as a possible defer bucket. That lets a later create or detail flow classify the plan’s scope fence itself as postponed work, which weakens the boundary the guardrail was added to preserve.

## Input

- **Step 1 guardrail contract** — Depend on step 1’s outcome: `Scope guardrails`, `Audit guardrails`, and `Expected placement` are recognized conditional body sections rooted in `plan_tool/create.py:OPTIONAL_PLAN_BODY_SECTION_SHAPES`.

- **Normalized section names** — Match the lowercase names produced by `plan_tool/parser.py:parse_body_sections` and the concept IDs derived through `plan_tool/concept_tree.py:concept_id`; do not rely on a heading’s display case.

- **Existing defer protocol** — Preserve `plan_tool/detail.py:parse_structured_detail_response` and its transport envelope shape. This step changes which concept IDs are eligible, not the envelope schema or signed-off decision workflow.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/create.py` — define the shared guardrail exclusion rule and keep guardrail concepts out of the create-time deferral review.
  - `plan_tool/detail.py` — omit guardrail sections from `derive_candidate_buckets` so prompts, validation, and persistence share the same eligible set.
  - `tests/test_create.py` — cover create-time exclusion while preserving normal body-section deferrals.
  - `tests/test_detail.py` — cover candidate generation, prompt rendering, and rejection of guardrail deferral envelopes.

## Implementation

- **Foundational logic: defer-bucket eligibility excludes guardrails.** Treat `Scope guardrails`, `Audit guardrails`, and `Expected placement` as active plan constraints, never as body sections a model or author can route to `## Deferred`.

- **Keep one exact guardrail-name rule.** Build on step 1’s recognized-section contract in `plan_tool/create.py:OPTIONAL_PLAN_BODY_SECTION_SHAPES`, but do not exclude every optional section: `Input` remains eligible under the existing general body-section behavior. A small named guardrail subset or predicate shared by the two files is preferable to repeating three string comparisons.

- **Filter the create review before decisions are collected.** In `plan_tool/create.py:create_plan`, apply the rule to the concept tree passed into `plan_tool/create.py:_review_create_concepts`. Guardrails must not produce an interactive question, an unattended pending decision, or a flat `decision-record` node. Continue to let non-guardrail sections follow the existing `review_concept_scope` and `render_scope_decisions` flow.

- **Filter the detail candidate source once.** In `plan_tool/detail.py:derive_candidate_buckets`, derive the normal body-section concepts through `bootstrap_concepts` and then remove only the guardrail entries before returning the ID-to-section map. `plan_tool/detail.py:generate_detail` already threads that map to `render_detail_prompt`, `parse_structured_detail_response`, and `_record_flat_deferrals`; keep that single-map flow so a guardrail ID is absent from the prompt and rejected before a detail file or concept record is published.

- **Do not change generic concept derivation.** Leave `plan_tool/concept_bootstrap.py:bootstrap_concepts` able to represent arbitrary H2 sections. The exclusion is specific to the create/detail defer workflow; changing the generic bootstrap contract would affect `plan_tool/cli/scope_review_cmd.py:cmd_scope_review` and other consumers outside this step’s file list.

- **Preserve normal deferrals and existing approval rules.** Continue allowing ordinary sections such as `Risks` and `Deferred` to be proposed and recorded, preserve the existing “unreviewed until scope-review signs off” behavior in `plan_tool/detail.py:_record_flat_deferrals`, and do not alter the detail envelope fields.

## Tests

- `test_create_guardrail_sections_are_not_offered_for_deferral` — a guardrail-bearing seed reaches `plan_tool/create.py:create_plan` without prompting for or recording any of the three guardrail concepts, while a normal section can still be deferred.

- `test_create_non_guardrail_sections_keep_existing_defer_behavior` — the create-time filter does not suppress a valid non-guardrail decision record entry.

- `test_derive_candidate_buckets_excludes_guardrail_sections` — `plan_tool/detail.py:derive_candidate_buckets` omits IDs for all three guardrail headings and retains ordinary H2 sections.

- `test_detail_prompt_omits_guardrail_defer_buckets` — a dry-run detail prompt does not advertise guardrail IDs as proposable buckets.

- `test_detail_rejects_guardrail_deferral_envelope` — `plan_tool/detail.py:generate_detail` refuses a guardrail deferral before publishing the detail output or a new concept record.

- `test_detail_keeps_non_guardrail_deferrals_valid` — an ordinary bucket still passes the structured-response gate and persists through the existing flow.

### Test-creation order (feature step)

1. `test_create_guardrail_sections_are_not_offered_for_deferral` — add with the create-time eligibility change and verify the three guardrails cannot enter its decision record.

2. `test_derive_candidate_buckets_excludes_guardrail_sections` — add with the shared eligibility rule and verify ordinary sections remain present.

3. `test_detail_prompt_omits_guardrail_defer_buckets` — add with prompt wiring and verify the model never receives those IDs.

4. `test_detail_rejects_guardrail_deferral_envelope` — add with validation wiring and verify an attempted guardrail deferral cannot publish output.

Every new test must be green before this step is considered finished.

## Acceptance criteria

- `plan_tool/create.py:create_plan` does not offer `Scope guardrails`, `Audit guardrails`, or `Expected placement` as defer decisions.

- A create-time decision record contains no newly recorded node for any of the three guardrail sections.

- `plan_tool/detail.py:derive_candidate_buckets` returns no concept ID for any guardrail section while retaining eligible non-guardrail body sections.

- A `plan-tool detail` prompt does not list guardrails as proposable body-section buckets.

- A structured detail response that names a guardrail concept ID fails validation and does not publish a detail file or a new pending deferral.

- The focused tests in `tests/test_create.py` and `tests/test_detail.py` pass.

## References

- [pytest output capturing](https://docs.pytest.org/en/stable/how-to/capture-stdout-stderr.html) — Use injected input and captured output when proving that create-time guardrail prompts are absent.

## Deferred

- `plan_tool/cli/scope_review_cmd.py:cmd_scope_review` legacy full-tree review path — keep generic H2 concept derivation unchanged; deciding whether legacy records need a guardrail-specific migration requires a separate reconciliation step.
