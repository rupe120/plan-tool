# Step 8 — Have detail generation return prepared writes

## Summary

Refactor `plan_tool/detail.py` so `plan_tool/detail.py:_author_step_detail` returns a prepared detail write instead of archiving or writing the active detail file itself. The serial publication paths in `plan_tool/detail.py:generate_detail` and `plan_tool/detail.py:_generate_detail_concurrent` will consume that record while preserving the existing detail-file, plan-pointer, checkpoint, reporting, and concept-deferral behavior. Keep `plan_tool/detail.py:generate_detail` and its `list[DetailResult]` return contract unchanged. On green, serial and concurrent runs produce the same durable artifacts and failure results, but generated detail content has one clear publication owner ready for step 9.

## Table of Contents

- [Summary](#summary) — The result and boundaries of the refactor.
- [Why](#why) — Why authoring must stop publishing active detail files.
- [Input](#input) — Existing parsed-response, checkpoint, and concept-preparation contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — The source and tests changed by this step.
- [Implementation](#implementation) — The prepared-write boundary and preserved publication rules.
- [Tests](#tests) — Characterization and focused refactor coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable proof that behavior remains unchanged.
- [References](#references) — Primary testing guidance for the failure seams.
- [Deferred](#deferred) — Transactional publication work owned by later steps.

## Why

`plan_tool/detail.py:_author_step_detail` currently combines the Claude round-trip and response parsing with active-file archival and writing. Both the serial loop in `plan_tool/detail.py:generate_detail` and the worker pool in `plan_tool/detail.py:_generate_detail_concurrent` therefore depend on a producer that has already changed the filesystem before the caller can coordinate the plan pointer and concept deferrals. Step 9 needs those artifacts available as prepared inputs before any live publication begins. This step creates that boundary without changing the public `generate_detail` behavior or adopting the publication authority before its owning steps land.

## Input

- `plan_tool/detail.py:ParsedDetailResponse` supplies the validated Markdown body and transport-only `DetailDeferral` records. The deferral envelope must remain absent from the prepared Markdown file content.
- `plan_tool/detail.py:_StepAuthoringOutcome` is the internal carrier between `_author_step_detail` and the serial publication tails. Extend or reshape this carrier so one successful outcome has exactly one prepared detail write and a failed parse has none.
- `plan_tool/detail.py:DetailResult` remains the public per-step result. Its `written` field continues to describe durable publication, not successful generation.
- `plan_tool/checkpoint.py:Checkpoint` behavior, as used by `_author_step_detail`, remains operational recovery state rather than an active plan artifact. A successful parse may still save a checkpoint before publication, and the caller may discard it only after the detail file and plan pointer are durable.
- Step 1 supplies the shared, write-free concept candidate preparation used for successful detail deferral replacements. This refactor must preserve that dependency outcome and leave concept publication in its current caller-owned tail until step 9.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/detail.py` — add the prepared-detail-write carrier, make `_author_step_detail` return it without publishing the active detail, and move active detail publication into the serial caller-owned paths.
  - `tests/test_detail.py` — add pre-refactor characterization and focused tests for the write-free producer, serial publication ownership, concurrent ordering, and unchanged failure behavior.

## Implementation

The foundational logic is: **a successfully parsed detail response becomes a prepared write, and only the serial publication owner may apply it to the active plan artifacts.**

- **Represent one complete detail write.** Introduce a small frozen internal record, likely named `_PreparedDetailWrite`, containing the values the publication tail must not recompute: step ID, canonical output path, stored `detail` path, final Markdown content, and validated deferrals. Store the exact content to write, including the existing trailing-newline rule, so generation and publication cannot disagree about final bytes.

- **Avoid parallel fields that can drift.** Prefer one optional prepared-write field on `plan_tool/detail.py:_StepAuthoringOutcome` over separate `update`, `body`, and `deferrals` values describing the same artifact. Progress handles, elapsed time, purity findings, raw response size, and failure details may remain on the outcome because they describe authoring rather than the prepared artifact.

- **Make the producer publication-free.** Change `plan_tool/detail.py:_author_step_detail` so a valid response returns the prepared write without calling `Path.mkdir`, `plan_tool/detail.py:_archive_existing_detail`, or `Path.write_text` for the active detail path. An unparseable response must keep returning a failed outcome with no prepared write; do not raise merely because the model response cannot be parsed.

- **Keep operational recovery writes distinct.** `_author_step_detail` may retain `save_checkpoint` and `_log_parse_failure`, including their fail-soft behavior. They write diagnostic or recovery state under `.plan-tool`, not the active detail, plan, or concept artifacts. Do not broaden this refactor into a fully side-effect-free Claude producer.

- **Use one detail publication helper.** One recommended approach is a narrow helper in `plan_tool/detail.py` that consumes the prepared write, creates the parent directory, calls `_archive_existing_detail`, and writes the exact prepared content. Both the ordinary serial loop in `generate_detail` and the serial tail in `_generate_detail_concurrent` should use this helper so write failures and archive behavior have one owner.

- **Preserve publication order.** For each successful prepared write, publish the active detail before calling `plan_tool/detail.py:update_step_detail_field`. Set the in-memory `Step.detail`, discard the checkpoint with the existing `"durable_write"` reason, archive orphan details through `_archive_orphan_details`, complete progress, capture scenarios, extract lessons, and append a successful `DetailResult` only after the plan pointer succeeds.

- **Preserve partial-failure reporting for now.** If the detail write raises `OSError`, return the same not-written `DetailResult`, reporter failure, and run-log error reason used today, while leaving the checkpoint available. If `update_step_detail_field` fails after the detail write, retain the current result text explaining that the file exists without its plan pointer. Step 9, not this refactor, replaces that partial state with recoverable bundle publication.

- **Keep concurrent workers read/compute-only for active artifacts.** `_generate_detail_concurrent` may still invoke and parse in worker threads, but active detail writes must occur after the workers join and in deterministic step order. A write failure for one prepared result must remain isolated to that step while later prepared results are still considered.

- **Preserve unexpected-worker-exception partial publication.** Before propagating an unexpected worker exception, the serial tail must publish every earlier or successful worker result that the current implementation would already have written, in the same deterministic order, and retain the same returned and logged failure boundary. Deferring all successful writes until after every future is known-good would be a new all-or-nothing behavior and belongs to step 9.

- **Preserve concurrent cross-step semantics.** The current concurrent path finishes worker authoring before its serial plan-mutation tail. Keep all active publication in that tail, and ensure returned `DetailResult` rows remain ordered by plan step rather than worker completion. The existing single concept-deferral preparation and save at the end of `generate_detail` must still see only successfully published results.

- **Leave the public API stable.** `plan_tool/detail.py:generate_detail` must continue returning `list[DetailResult]`; callers such as `plan_tool/bench.py`’s `generate_detail` call, `plan_tool/cli/authoring.py:cmd_detail`, `plan_tool/cli/review_actions.py`’s regeneration path, and the recursive calls from `plan_tool/detail.py:split_step` and `plan_tool/detail.py:merge_steps` should not need a new publication argument or return type.

- **Do not introduce the common transaction API early.** A generic publication intent would couple this dependency-only refactor to steps 2 and 3. Keep the prepared-detail record local to `plan_tool/detail.py`; step 9 can adapt it to the publication authority once both prerequisites exist.

## Tests

- `test_generate_detail_success_preserves_detail_and_pointer` — the public serial path writes the same Markdown body, omits the transport envelope, and sets the same repo-relative `step.detail`.
- `test_generate_detail_parse_failure_preserves_active_artifacts` — exhausted parse retries return `written=False` without changing the detail file, plan pointer, or concept deferrals.
- `test_generate_detail_write_failure_preserves_result_and_checkpoint` — an active-detail `OSError` produces the existing skip reason and reporter/run-log failure while retaining recovery state.
- `test_generate_detail_frontmatter_failure_preserves_partial_state_report` — a plan-pointer failure still reports that the detail file exists and requires cleanup.
- `test_generate_detail_overwrite_preserves_archive_behavior` — replacing an active detail archives its prior content and leaves the new content at the canonical path.
- `test_generate_detail_success_discards_checkpoint_after_pointer_update` — checkpoint save precedes active publication and discard follows the successful plan-pointer update.
- `test_generate_detail_concurrent_results_remain_in_step_order` — worker completion order does not change publication or returned-result order.
- `test_generate_detail_concurrent_write_failure_is_per_step` — one prepared write failing does not prevent later prepared writes from publishing.
- `test_generate_detail_concurrent_deferrals_remain_single_save_in_step_order` — successful concurrent publications still prepare deferral replacements once, in deterministic result order.
- `test_author_step_returns_prepared_write_without_publishing` — direct `_author_step_detail` success returns the canonical path, exact content, stored path, and deferrals while leaving the active detail and plan unchanged.
- `test_author_step_parse_failure_returns_no_prepared_write` — direct producer failure returns no prepared artifact and performs no active publication.
- `test_serial_and_concurrent_paths_share_detail_publisher` — a publisher spy observes the same prepared-write contract from both paths and no worker-thread active write.

### Test-creation order (refactor step)

Write the public-behavior characterization tests first:

1. `test_generate_detail_success_preserves_detail_and_pointer` — pin successful detail content, frontmatter mutation, and `DetailResult`.
2. `test_generate_detail_parse_failure_preserves_active_artifacts` — pin the no-write parse-failure path.
3. `test_generate_detail_write_failure_preserves_result_and_checkpoint` — pin write-failure isolation and recovery-state retention.
4. `test_generate_detail_frontmatter_failure_preserves_partial_state_report` — pin the current detail-written/plan-pointer-missing result.
5. `test_generate_detail_overwrite_preserves_archive_behavior` — pin replacement archival and canonical-path behavior.
6. `test_generate_detail_success_discards_checkpoint_after_pointer_update` — pin checkpoint ordering.
7. `test_generate_detail_concurrent_results_remain_in_step_order` — pin deterministic concurrent output.
8. `test_generate_detail_concurrent_deferrals_remain_single_save_in_step_order` — pin the existing whole-run concept update.

Run these tests against the pre-refactor implementation. After restructuring, keep the same characterization tests green and unmodified. Then add the direct producer and shared-publisher tests that prove the new internal boundary.

## Acceptance criteria

- Calling `plan_tool/detail.py:_author_step_detail` with a valid structured response returns one prepared detail write and does not create, replace, archive, or remove the active detail file.
- An unparseable response returns a failed `_StepAuthoringOutcome` with no prepared write and no active artifact changes.
- `plan_tool/detail.py:generate_detail` retains its current signature and returns `list[DetailResult]`.
- A successful serial run writes the prepared Markdown, updates `step.detail`, discards its checkpoint after both writes, and returns `DetailResult.written=True`.
- A successful concurrent run performs active detail publication outside worker threads and returns results in plan-step order.
- Active-detail write failures and plan-pointer failures retain their existing `DetailResult`, reporter, run-log, checkpoint, and continuation behavior.
- Overwrite archival and post-success orphan archival remain unchanged.
- Concept deferral replacements include only successfully published details and remain one deterministic whole-run update.
- The characterization and focused refactor tests in `tests/test_detail.py` pass.

## References

- [pytest — Monkeypatching functions and environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Use controlled write, checkpoint, reporter, and publication seams to characterize failure ordering without changing production behavior.

## Deferred

- **Transactional detail and concept publication** — Step 9 will send prepared detail files and prepared deferral changes through the common all-or-recoverable publication authority.
- **Common publication intents and recovery coordinator** — Steps 2 and 3 own the typed request model, staging, rollback, durability, and uncertain-path reporting.
- **Removal of the detail-written/plan-pointer-missing partial state** — Preserve that failure contract in this refactor; step 9 replaces it with recoverable bundle publication.
- **Split, merge, and re-ground transformation policy** — This step preserves their existing calls into `generate_detail` and does not redesign their ownership or deferral rules.
