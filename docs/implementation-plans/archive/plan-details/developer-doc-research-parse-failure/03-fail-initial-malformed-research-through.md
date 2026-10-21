> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Fail initial malformed research before publication

## Summary

Make the initial generic developer-document research result a hard create failure when it remains unparseable after step 2’s bounded repair. Update `plan_tool/create.py` at the pre-publication create path and cover it through `tests/test_create.py`. The resulting diagnostic names terminal developer-document reference research and tells the operator to retry the original `plan-tool create …` command. Reject only the typed unparseable outcome; a valid empty result remains a non-failing result. On green, a failed initial research result cannot write or replace a plan, archive a collision, or update the manifest.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the create failure boundary.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — The ambiguity removed from the initial create path.
- [Input](#input) — Upstream research-result and publication contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed by this step.
- [Implementation](#implementation) — Required failure boundary and preserved behavior.
- [Tests](#tests) — Focused end-to-end create coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary parsing and test references.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that apply here.
- [Deferred](#deferred) — Work outside this initial-create boundary.

## Why

`plan_tool/create.py:_prepare_create_plan` currently reduces both an unparseable generic research reply and an explicit empty result to false values before publication, so malformed research can produce a plan that appears to have simply found no sources. Step 1 makes the outcomes distinguishable and step 2 gives malformed output one bounded repair; this step makes the remaining terminal failure stop the initial create before `plan_tool/create.py:_publish_create_plan` can alter a colliding plan or its manifest registration.

## Input

- **Step 1 typed research result:** Step 1 supplies the generic research outcome that distinguishes populated, valid-empty, and unparseable replies. This step consumes that distinction without changing the parser’s tolerated-response or reference-row filtering rules.

- **Step 2 repair result:** Step 2 returns the repaired result when its one retry succeeds and leaves a second malformed reply as the terminal unparseable outcome. This step treats that terminal outcome as a create failure rather than adding another retry.

- **Publication ordering:** `plan_tool/create.py:_prepare_create_plan` finishes before `plan_tool/create.py:_publish_create_plan`, whose replacement and manifest work includes `archive_existing_source`, `remove_from_manifest`, `write_new_plan`, and `append_to_manifest`.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/create.py` — reject the terminal unparseable generic research outcome during initial preparation, before publication begins.
  - `tests/test_create.py` — add complete-create tests for malformed and valid-empty generic research outcomes and their publication side effects.
  - `tests/test_bench.py` — make the realistic proposal fixture express no references as the valid empty JSON array rather than malformed blank output.

## Implementation

- **Foundational logic: terminal unparseable initial research refuses publication.** In the generic-research branch of `plan_tool/create.py:_prepare_create_plan`, inspect the typed result from `plan_tool/create.py:propose_references_from_claude`. Raise `plan_tool/create.py:CreateError` for the unparseable outcome, including when it comes through normal create orchestration rather than a direct proposal test. The error identifies terminal developer-document reference research after its bounded repair and directs the operator to retry the original `plan-tool create …` command; preserve the existing CLI error renderer rather than adding a second presentation path.

- **Classify the failed phase before raising.** Set the surrounding initial `propose_references` phase outcome to `error` before the terminal unparseable result raises, so its existing finalizer records the failed phase rather than `ok` or `skipped`. A valid-empty result remains the existing `skipped` no-output outcome and continues toward publication.

- **Test the outcome discriminator, not list truthiness.** A populated result supplies its retained `plan_tool/create.py:Reference` entries and a valid-empty result remains allowed to continue through the existing empty References rendering path. Do not reject an empty result merely because it has no entries; the rejected alternative is using `if not references`, which recreates the malformed-versus-empty ambiguity this plan removes.

- **Keep retry and checkpoint ownership at the research boundary.** Leave the one-repair limit, attempt provenance, raw-response handling, and checkpoint eligibility with `plan_tool/create.py:propose_references_from_claude` from step 2. This step consumes its final outcome and must not introduce another retry or mutate the reference checkpoint contract.

- **Fail before every publication mutation.** Keep the new check in `_prepare_create_plan`, before `create_plan` calls `_publish_create_plan`. A terminal malformed result must therefore prevent collision archival, collision-manifest removal, initial plan writing, and manifest append. Collision discovery and the operator’s replacement decision may remain preparatory reads and choices.

- **Preserve the separate roadmap path.** Apply the failure boundary only to generic developer-document research. `plan_tool/create.py:propose_roadmap_references_from_claude` and its selected-roadmap validation policy remain unchanged.

- **Keep iteration policy unchanged.** `plan_tool/create.py:_converge_create_plan` remains the post-publication References-update path. Do not use this initial pre-publication gate to change how later iteration proposals preserve an existing References section.

## Tests

### Tests for this step

- `test_initial_terminal_unparseable_research_aborts_create_before_plan_write` — drive `create_plan` through terminal malformed generic research and assert it raises `CreateError` without creating the predicted plan or manifest.

- `test_initial_terminal_unparseable_research_preserves_collision_and_manifest` — start with a colliding plan and manifest entry, then assert terminal malformed research leaves the existing plan and manifest unchanged and creates no replacement archive.

- `test_initial_terminal_unparseable_research_stops_fetch_and_synthesis` — assert terminal malformed research invokes neither reference-document fetching nor body-section synthesis before `CreateError` reaches the caller.

- `test_initial_terminal_unparseable_research_records_error_phase` — inspect the create run log and assert the initial `propose_references` phase ends as `error`, not `ok` or `skipped`.

- `test_initial_terminal_unparseable_research_has_retry_diagnostic` — assert the propagated `CreateError` names terminal developer-document reference research and directs retry of the original `plan-tool create …` command.

- `test_initial_valid_empty_research_continues_to_publish` — return the typed valid-empty generic research outcome and assert create completes its normal plan and manifest publication path with the `propose_references` phase ending `skipped`.

- `tests/test_bench.py::test_proposal_realistic_trial_succeeds` — retain the successful realistic proposal scenario by returning `[]` for generic reference research; a blank reply is terminal malformed output, not a no-references fixture.

Every test in `tests/test_create.py` must be green before this step is finished.

## Acceptance criteria

- A terminal unparseable result from initial generic reference research raises `CreateError` through `plan_tool/create.py:create_plan`; its diagnostic names terminal developer-document reference research and directs retry of the original `plan-tool create …` command.

- The initial terminal result ends `propose_references` as `error` and invokes neither reference-document fetching nor body-section synthesis.

- That failure occurs before `plan_tool/create.py:_publish_create_plan` writes a new plan, archives a collision, removes a manifest entry, or appends a manifest entry.

- A valid empty generic research result ends `propose_references` as `skipped`, does not raise the malformed-research failure, and can complete initial plan publication.

- `tests/test_create.py` covers phase outcome, downstream short-circuit, publication side effects, and valid-empty continuation; the realistic proposal bench fixture also supplies explicit valid-empty research.

## References

- [json — JSON encoder and decoderhttps: — Use the parsing behavior to preserve the distinction between a valid empty array and malformed JSON.

- [pytest API Referencehttps: — Use `raises`, temporary paths, and monkeypatching for hermetic publication-boundary tests.

## Applicable guardrails

- **Plan intent:** The plan’s “## Plan intent” requires malformed developer-document research to remain visible as failure at the initial create boundary.

- **Step intent:** The plan’s “## Step intent” limits this change to initial create behavior, so the failure check belongs before publication rather than in later update paths.

- **Out of scope:** The plan’s “## Out of scope” keeps separate research modes, retrieval work, generalized recovery machinery, and unrelated create behavior outside these two files.

## Deferred

- Post-publication generic References re-proposals in `plan_tool/create.py:_converge_create_plan` — retain their existing iteration policy because this step owns only the initial pre-publication boundary.
