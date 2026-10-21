> **Auto-archived**: this plan was swept on 2026-07-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Add structured detail deferrals and regenerate on include

## Summary

Extend `plan_tool/detail.py:generate_detail` so detail authoring returns machine-readable concept deferrals alongside the Markdown body, validates them against the signed-off concept record, and persists them through the shipped concept-record contract. Update `plan_tool/prompts/detail.md` to require concept IDs for deferred material instead of leaving `## Deferred` as an untracked prose-only decision. When a later review changes one of those concepts to `include`, regenerate each affected step’s detail through the normal authoring path and remove the stale deferral link only after the replacement succeeds. Wire the operator gate through `plan_tool/cli/authoring.py:cmd_detail`; on green, plan ownership, concept decisions, and generated detail remain connected in serial and concurrent runs.

## Table of Contents

- [Summary](#summary) — The structured-deferral and regeneration outcome.
- [Why](#why) — Why prose-only deferrals leave concept commitments untracked.
- [Input](#input) — Contracts supplied by steps 2 and 3 and by the shipped concept core.
- [Files (creates vs edits)](#files-creates-vs-edits) — Changes to detail authoring, its prompt, CLI wiring, and tests.
- [Implementation](#implementation) — Parsing, validation, serial persistence, and include-triggered regeneration.
- [Tests](#tests) — Unit and CLI cases for valid, invalid, concurrent, and recovery paths.
- [Acceptance criteria](#acceptance-criteria) — Observable requirements for completion.
- [References](#references) — Authoritative structured-output, executor, and publication semantics.
- [Deferred](#deferred) — Completeness and structural-remedy work owned by later steps.

## Why

`plan_tool/detail.py:generate_detail` currently treats `## Deferred` as Markdown only, so the tool cannot tell whether a signed-off concept was deliberately postponed, accidentally omitted, or later changed back to included. That gap also leaves an included concept described by stale deferral prose until someone notices and forces regeneration manually. Structured links to stable concept IDs make the decision checkable, while include-triggered regeneration ensures the generated detail catches up with the reviewed concept record.

## Input

- **Step 2 — evidence-only enrichment:** step 2 supplies the optional concept producer used when supported evidence yields additional candidates. This step consumes its output through the shipped concept-record APIs and does not add another concept model or model invoker.
- **Step 3 — reviewed ownership:** step 3 leaves create output with a persisted reviewed concept record and accepted concept IDs assigned through `plan_tool/schema.py:Step.concept_ids`. Detail must treat those stable IDs and review states as authoritative.
- **Shipped concept-record core:** confirm the landed public read, merge, review, synchronization, and save symbols in `plan_tool/concept_tree.py` before implementation. Use its state vocabulary, stable identity, stale-record handling, and single-writer contract rather than recreating them in `plan_tool/detail.py`.
- **Existing detail response contract:** `plan_tool/detail.py:parse_detail_response` validates the Markdown body, while `plan_tool/detail.py:_author_step_detail` owns invoke, parse, checkpoint, and detail-file publication. The structured result must extend this flow without weakening the required-heading checks.
- **Concurrent authoring contract:** `plan_tool/detail.py:_generate_detail_concurrent` lets workers author independent details but keeps plan mutation serial. Structured deferrals must follow the same rule: workers may return parsed data, but only the caller may merge and persist shared concept state.

## Files (creates vs edits)

- **New files:**

  - None.

- **Existing files (edits only):**

  - `plan_tool/detail.py` — represent and parse structured deferrals, carry them through per-step outcomes, validate them against the reviewed concept record and step ownership, merge them serially, and regenerate affected details after a deferred concept becomes included.
  - `plan_tool/prompts/detail.md` — require a bounded structured deferral payload tied to stable concept IDs while preserving the developer-facing Markdown body.
  - `plan_tool/cli/authoring.py` — pass `args.yes` and the interactive prompt seam from `cmd_detail` into `generate_detail` so concept review follows the existing unattended-versus-interactive rules.
  - `tests/test_detail.py` — cover response parsing, validation, persistence ordering, include-triggered regeneration, concurrency, and failure recovery.
  - `tests/cli/test_authoring_cmds.py` — prove `cmd_detail` forwards the operator-gate arguments and reports regeneration failures through the existing command result.

## Implementation

- **Make deferrals structured and ID-based.** Extend the detail response contract with a small structured payload containing each deferred concept’s stable ID and the step that emitted the deferral. Use the exact ID and state contracts shipped by the concept core and step 3; titles or similar prose are never substitutes for IDs.

- **Keep one model response per authored step.** Update `plan_tool/prompts/detail.md` so the normal authoring response carries both the Markdown body and its structured deferral data. Do not add a second model call that tries to rediscover deferrals from completed prose. One reasonable shape is a clearly delimited JSON object outside the body, provided `plan_tool/detail.py` can split it unambiguously and still write only the Markdown portion to the detail file.

- **Require complete accounting for `## Deferred`.** The prompt must tell the author that every signed-off concept intentionally routed to `## Deferred` appears in the structured payload. An empty deferral list is valid when the body defers no signed-off concept. Free-form follow-up tasks that are not part of the signed-off concept set may remain prose, but they must not invent concept IDs.

- **Separate envelope parsing from body validation.** Keep `plan_tool/detail.py:parse_detail_response` responsible for the established Markdown rules, or place a thin structured-response parser directly before it. The important invariant is that malformed structured data never gets written as if it were a valid detail result. Preserve the existing retry behavior driven by `_MAX_INVOKE_ATTEMPTS` and `_REPROMPT_SUFFIX`, updating the retry instructions so a missing or invalid deferral payload can be corrected.

- **Use an explicit parsed value.** A small immutable result such as a detail body plus deferral records is preferable to passing loosely shaped dictionaries. Carry that value through `plan_tool/detail.py:_StepAuthoringOutcome` and `plan_tool/detail.py:DetailResult` only as far as callers need it. Preserve existing fields and defaults so skip, dry-run, merge, split, and CLI summary paths do not need unrelated rewrites.

- **Validate against reviewed state.** Before accepting a deferral, verify that its ID exists in the current signed-off concept record and is allowed to be deferred under that record’s state. Reject unknown IDs, duplicate links for the same step and concept, and links that conflict with the step’s accepted ownership. Do not infer a replacement ID from a title when validation fails.

- **Fail safely without losing sibling results.** A malformed response should follow the current per-step failure model: return a failed `DetailResult`, retain successful sibling results, and avoid publishing that step’s new detail or deferral state. Do not silently drop an invalid deferral and accept the Markdown, because that recreates the untracked-deferral gap.

- **Keep shared mutation serial.** `plan_tool/detail.py:_author_step_detail` and workers used by `_generate_detail_concurrent` may parse and return deferrals, but they must not update the shared concept record. After all worker outcomes are collected in target-step order, `generate_detail` should merge successful deferrals through the concept core and persist once through its public writer. This preserves deterministic ordering and avoids races on the per-plan record.

- **Publish detail before its link, but preserve the old link until success.** A deferral must never point to a detail body that failed to write. Conversely, replacing an existing detail must not erase its prior structured links before the new body and new links are ready. Follow the existing `_author_step_detail` pattern: workers publish their detail result, then the serial caller updates shared metadata. If concept persistence fails, return an error that leaves enough prior state for a later run to recover rather than claiming the step is synchronized.

- **Detect include transitions from durable state.** When concept review changes a previously deferred concept to `include`, find every detail step linked to that deferral. Do not scan Markdown text or match titles. Regenerate only those affected steps, even if their `step.detail` files already exist; unrelated steps keep the normal idempotent skip behavior.

- **Regenerate through the normal authoring pipeline.** Feed each affected step back through the same prompt rendering, parsing, checkpoint, archive, write, and plan-pointer path used by `generate_detail`. Pass the updated concept decision and current ownership context into `render_detail_prompt` so the new body treats the concept as included. Avoid a second bespoke renderer that edits `## Deferred` text in place.

- **Remove stale deferrals only after replacement succeeds.** A successful regenerated result replaces that step’s old deferral set with the newly parsed set. If regeneration fails, retain the old link as an explicit stale/recovery signal and return a failed result; never report synchronization while the old body still describes the included concept as deferred.

- **Run include regeneration once per call.** Place transition detection and any resulting regeneration in the serial orchestration owned by `generate_detail`, outside both the serial per-step loop and concurrent workers. Deduplicate affected step IDs when several included concepts point to the same detail, so that step is regenerated once with the full updated scope.

- **Avoid recursive regeneration.** Mark the internally scheduled affected steps or use a bounded second authoring phase so parsing their replacement deferrals cannot restart the same include-trigger check indefinitely. One pass over the transition snapshot is sufficient; unresolved failures return to the caller for an explicit retry.

- **Respect dry runs and unattended execution.** `dry_run=True` may show which details would be regenerated and render their prompts, but it must not write detail files, plan frontmatter, or concept state. Add `yes: bool = False` to `generate_detail` if the shipped review integration requires it, reuse its existing `prompt_fn`, and have `plan_tool/cli/authoring.py:cmd_detail` pass `yes=args.yes` plus an interactive prompt function. Only the core’s interactive confirm path may create operator sign-off; `--yes` and non-TTY runs must use its safe unsigned outcome.

- **Preserve the existing prompt inputs.** Add concept ownership, reviewed decisions, and current deferral links as a compact block in `render_detail_prompt`. Keep the existing file excerpts, sibling details, `prior_body`, references, lessons, and foundational-logic blocks unchanged. Thread the new block through both the serial render call and the dispatch preparation in `_generate_detail_concurrent`.

- **Treat the concept core as the single authority.** Do not add a parallel JSON sidecar, a second state enum, or a local save routine in `plan_tool/detail.py`. If the landed core lacks a public operation needed to replace a step’s deferral links safely, route that API gap back to its owning prerequisite instead of copying core logic into this step.

## Tests

Tests in `tests/test_detail.py`:

- `test_parse_structured_detail_response_returns_body_and_deferrals` — a valid response yields the unchanged Markdown body and ordered concept-ID links.
- `test_parse_structured_detail_response_accepts_empty_deferrals` — a body with no signed-off concept deferrals accepts an empty structured list.
- `test_parse_structured_detail_response_rejects_missing_payload` — omission of the required structured payload enters the existing retry path.
- `test_parse_structured_detail_response_rejects_unknown_concept_id` — an ID absent from the signed-off record is not accepted or persisted.
- `test_parse_structured_detail_response_rejects_duplicate_link` — the same step and concept cannot be recorded twice.
- `test_invalid_deferral_does_not_publish_detail` — invalid structured data cannot leave a newly written Markdown file without matching metadata.
- `test_valid_deferrals_persist_after_detail_write` — successful detail publication is followed by one serial concept-record update.
- `test_concurrent_workers_return_deferrals_without_saving` — workers parse structured results but never write shared concept state.
- `test_concurrent_deferrals_merge_in_step_order` — successful worker results merge deterministically after all workers finish.
- `test_one_worker_failure_preserves_sibling_deferrals` — one malformed response does not erase valid sibling results.
- `test_include_transition_regenerates_linked_detail` — changing a deferred concept to included forces its linked detail through authoring despite an existing file.
- `test_include_transition_does_not_regenerate_unrelated_steps` — steps without a link to the included concept keep normal skip behavior.
- `test_multiple_included_concepts_regenerate_step_once` — several changed concepts linked to one step produce one replacement authoring call.
- `test_successful_regeneration_replaces_stale_deferrals` — new structured links replace the prior set only after the replacement detail succeeds.
- `test_failed_regeneration_retains_prior_deferral_link` — a failed replacement leaves the old link available for recovery and returns a failed result.
- `test_include_regeneration_is_bounded` — replacement parsing cannot recursively schedule the same step.
- `test_dry_run_reports_regeneration_without_writes` — dry-run output identifies affected details while leaving all artifacts unchanged.
- `test_serial_and_concurrent_prompts_receive_concept_scope` — both render paths include current ownership, decisions, and deferral context.
- `test_unattended_detail_does_not_forge_concept_signoff` — `yes=True` or non-TTY execution leaves operator-only sign-off unset.

Tests in `tests/cli/test_authoring_cmds.py`:

- `test_cmd_detail_forwards_yes_and_prompt_fn` — `cmd_detail` passes the CLI unattended flag and interactive input seam to `generate_detail`.
- `test_cmd_detail_returns_failure_when_include_regeneration_fails` — a failed affected-detail replacement produces the command’s existing nonzero failure result.
- `test_cmd_detail_dry_run_does_not_mutate_concept_state` — CLI dry-run preserves both detail and concept artifacts.

### Test-creation order (feature step)

Add the parser and validation tests first, followed by serial persistence and include-transition tests. Add concurrent merge, failure recovery, dry-run, and CLI-routing tests with their corresponding integration changes. Every new test must be green before this step is considered finished.

## Acceptance criteria

- Every newly authored detail response contains a structured deferral list, including an explicitly empty list when no signed-off concept is deferred.
- `plan_tool/detail.py` accepts only concept IDs present in the current signed-off concept record and rejects duplicate or conflicting step links.
- The Markdown written to a detail file contains no response-envelope JSON or other structured transport markers.
- Successful serial and concurrent runs persist deferral links through the shipped concept-record writer in deterministic step order.
- Concurrent workers never write the shared concept record.
- A deferred-to-included concept causes every linked detail step, and only linked steps, to regenerate through the normal detail authoring pipeline.
- Several included concepts linked to one step trigger one regeneration for that step.
- Successful regeneration replaces stale deferral links with the replacement response’s links.
- Failed regeneration preserves the prior deferral link and returns a failed `DetailResult`.
- `dry_run=True` performs no detail, plan-frontmatter, or concept-record writes.
- `plan_tool/cli/authoring.py:cmd_detail` forwards `args.yes` and interactive prompting to `generate_detail`.
- Unattended and non-TTY detail runs do not set an operator-only concept sign-off flag.
- All new cases in `tests/test_detail.py` and `tests/cli/test_authoring_cmds.py` pass.

## References

- [Structured outputs — Claude API Docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) — Use the schema and invalid-output guidance for the detail deferral payload.
- [Structured model outputs — OpenAI API](https://developers.openai.com/api/docs/guides/structured-outputs) — Keep the injected backend’s structured result compatible with schema-conforming model output.
- [JSON Schema Validation: A Vocabulary for Structural Validation of JSON](https://json-schema.org/draft/2020-12/json-schema-validation) — Apply object, required-field, identifier, array, and uniqueness validation consistently.
- [concurrent.futures — Launching parallel tasks — Python documentation](https://docs.python.org/3/library/concurrent.futures.html) — Follow executor result collection and exception behavior while keeping shared persistence serial.
- [os.replace — Python documentation](https://docs.python.org/3/library/os.html#os.replace) — Preserve the concept core’s atomic same-filesystem publication behavior during synchronized updates.

## Deferred

- **Missing-owner and missing-deferral completeness findings** — step 5 compares signed-off concepts with explicit ownership and structured detail links.
- **Split and merge preservation** — step 6 distributes or unions concept IDs when structural remedies replace steps.
- **Re-ground and scope-out preservation** — later integration steps carry ownership through re-grounding and record deferrals when scope-out removes the last owner.
- **Cross-file transaction recovery** — this step orders detail and concept publication safely but does not add a transaction spanning both artifacts.
- **Inferring deferrals from existing prose-only details** — existing Markdown without structured links is not parsed heuristically; it becomes structured when explicitly regenerated.
