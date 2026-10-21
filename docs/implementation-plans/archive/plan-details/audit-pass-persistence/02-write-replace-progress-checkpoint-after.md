> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Persist completed sampler passes and retire terminal checkpoints

## Summary

Update `plan_tool/review.py:audit_plan_until_stable` so each completed pass that leads to another pass replaces the stable in-progress sampler checkpoint from step 1. Make the continuation decision only after the pass has updated its union, counters, and convergence state. On dry-stop, pass-cap, or plan-quota exits, transition any prior checkpoint to a non-resumable state before attempting cleanup. Green means interruption can retain only complete continuing-pass boundaries, while terminal results cannot leave resumable work behind.

## Table of Contents

- [Summary](#summary) — The completed behavior and its result.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why sampler progress needs a durable boundary.
- [Input](#input) — The checkpoint and sampler contracts this step uses.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two files this step changes.
- [Implementation](#implementation) — Pass ordering, terminal handling, and failure rules.
- [Tests](#tests) — Unit coverage for continuing and terminal paths.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Standard-library durability and exception references.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this step.
- [Deferred](#deferred) — Follow-on work owned by later steps.

## Why

`plan_tool/review.py:audit_plan_until_stable` keeps its finding union and convergence bookkeeping only in local variables, so an interruption after a successful pass loses work that the next pass would otherwise build on. The existing `plan_tool/cli/completeness_phases.py:write_pre_apply_audit_checkpoint` protects the later apply phase, not conceptual sampling. This step adds the missing pass boundary without changing finding, convergence, or final-report behavior.

## Input

- **Step 1 checkpoint contract** — Step 1 provides the stable saved-review checkpoint path, its non-final sampler role, conditionally persisted sampler payload, and focused save/load or transition helpers. Use that planned contract rather than adding another persistence format.

- **Sampler state** — `plan_tool/review.py:audit_plan_until_stable` owns `by_id`, per-finding materiality, observation history, pass counts, dry-streak state, failure counts, and the terminal reason. Persist the completed values that a later step needs to restore the sampler unchanged.

- **Pass boundary** — `plan_tool/review.py:check_plan_audit` owns one logical pass, including its bounded missing-heading retry. It catches `Exception` failures as an errored pass; a `BaseException` such as `KeyboardInterrupt` leaves the sampler before its pass boundary.

- **Existing pre-apply checkpoint** — `plan_tool/cli/completeness_phases.py:write_pre_apply_audit_checkpoint` remains a separate apply-phase recovery boundary. Do not merge it with sampler persistence.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/review.py` — Add pass-boundary checkpoint writes and terminal invalidation to `audit_plan_until_stable`.
  - `tests/test_review.py` — Extend `TestAuditPlanUntilStable` and related sampler tests with persistence ordering and failure cases.

## Implementation

- **Foundation: decide continuation after complete bookkeeping.** In `plan_tool/review.py:audit_plan_until_stable`, decide whether another logical pass can run only after the current pass has merged new findings, recorded materiality and observations, updated failure or conformance counts, and applied dry-streak or terminal rules.

- **Persist only a completed continuing pass.** When another pass remains, save the full completed sampler state through step 1’s stable checkpoint helper before the next pass builds its carried-findings prompt. The record must contain the current union in first-occurrence order and every loop value needed to preserve the existing convergence result when step 3 restores it.

- **Treat an errored nonterminal pass as completed sampler work.** A nonzero invoker result already consumes a logical pass and increments the existing failed-pass accounting. If the loop continues, persist that updated state too; do not re-spend its slot after recovery.

- **Do not checkpoint an in-flight pass.** Never save between the invoker call and the completed state update. A `KeyboardInterrupt` or other `BaseException` during that interval must leave only the prior durable boundary, so the interrupted pass is retried.

- **Use one sampler implementation.** Keep this behavior inside `plan_tool/review.py:audit_plan_until_stable`; both production paths already call it through `plan_tool/cli/completeness_phases.py:_sample_conceptual_audit` or the conceptual-audit call in `_run_iterate_convergence_loop`. Leave those callers unchanged.

- **Suppress resumable writes on every terminal route.** A dry-streak stop, terminal plan quota, and pass-cap exit must bypass the ordinary in-progress checkpoint replacement for that final pass. If an earlier checkpoint exists, publish its `terminal-residue` lifecycle first, then attempt deletion only after that transition publishes.

- **Handle publication-aware failures.** The terminal-transition boundary must distinguish failure before publication from an error reported after the non-resumable artifact is visible; an `OSError` alone cannot prove which occurred. Preserve the prior boundary and skip cleanup on a pre-publication failure. After publication, attempt cleanup; if cleanup fails, leave the residue non-resumable and log the condition without changing the audit result.

- **Keep writes best-effort.** A checkpoint save, terminal transition, or cleanup error must not crash an otherwise healthy conceptual audit or change its existing finding union, convergence verdict, or `budget_report` fields. Do not claim stronger recovery guarantees from an error after publication.

- **Reuse existing run-log vocabulary only when supplied.** When `run_logger` is present, record checkpoint saves and terminal discards through its existing checkpoint methods. Do not open a run log in `plan_tool/review.py`; audit-only callers remain without one.

## Tests

### Tests for this step

- `test_continuing_pass_checkpoint_contains_completed_sampler_state` — asserts a continuing pass saves the merged finding union, materiality, observations, counters, and dry-streak state before the next prompt is rendered.

- `test_continuing_pass_replaces_the_prior_sampler_checkpoint` — asserts successive continuing passes leave one stable checkpoint containing the later completed state.

- `test_nonterminal_errored_pass_persists_its_consumed_sampler_slot` — asserts an errored pass that continues records its incremented pass and failure counts without changing existing neutral-error convergence behavior.

- `test_keyboard_interrupt_does_not_checkpoint_the_inflight_pass` — raises `KeyboardInterrupt` during a later invoker call and asserts the stable checkpoint contains only the earlier completed boundary.

- `test_terminal_paths_skip_resumable_checkpoint_replacement` — covers dry-stop, pass-cap, and plan-quota exits, asserting none publishes a new resumable checkpoint for the terminal pass.

- `test_terminal_transition_before_publication_preserves_prior_boundary` — forces a pre-publication transition failure and asserts cleanup does not erase the prior resumable checkpoint.

- `test_terminal_transition_after_publication_leaves_no_resumable_prefix` — simulates an error after publication and asserts the on-disk artifact has the `terminal-residue` lifecycle, is non-resumable, and is not treated as the old boundary.

- `test_terminal_cleanup_error_is_nonfatal_after_nonresumable_transition` — asserts a cleanup failure is reported while the audit returns its normal result and any residue remains non-resumable.

- `test_sampler_checkpoint_events_use_existing_run_logger_methods` — asserts a supplied run logger receives save and terminal-discard events without `audit_plan_until_stable` creating a logger.

Every listed test must be green before this step is complete.

## Acceptance criteria

- A completed pass that leads to another pass replaces the one stable in-progress checkpoint only after all sampler bookkeeping is current.

- A nonterminal errored pass persists its consumed logical-pass slot and failed-pass count when sampling continues.

- An interrupted in-flight pass creates no new boundary and leaves the prior completed checkpoint unchanged.

- Dry-stop, pass-cap, and plan-quota exits do not write a resumable checkpoint for their terminal pass.

- A published terminal transition makes any cleanup residue non-resumable; a failure before publication preserves the prior recovery boundary.

- Checkpoint write and cleanup failures leave an otherwise healthy audit’s finding union, convergence behavior, and coverage record unchanged.

- `uv run pytest tests/test_review.py -q` is green.

## References

- [os — Miscellaneous operating system interfaceshttps: — Read `os.replace()` and `os.fsync()` for the publication boundary used by durable replacement.

- [tempfile — Generate temporary files and directorieshttps: — Read the same-directory temporary-file pattern used before atomic replacement.

- [Built-in Exceptions — the exception hierarchyhttps: — Read the `BaseException` and `Exception` relationship used to distinguish interruption from an ordinary errored pass.

## Applicable guardrails

- **The plan’s `## Step intent`, durable continuing-pass boundary** — Persist only complete passes that will continue; terminal sampler work must not become resumable.

- **The plan’s `## Architecture`, write and terminal-transition ordering** — Keep the save after complete bookkeeping and keep the non-resumable transition ahead of cleanup.

- **The plan’s `## Out of scope`, audit-surface and CLI boundary** — Do not extend checkpointing to other lanes or add flags.

- **The plan’s `## Out of scope`, final-evidence and JSON boundary** — Do not alter reusable-final selection, reader eligibility, finding behavior, or the public JSON payload.

- **The plan’s `## Out of scope`, terminal delivery boundary** — Do not retain or recover terminal sampler output after this function returns.

- **The plan’s `## Out of scope`, concurrency and artifact-history boundary** — Rely on stable atomic replacement; do not add locking, migration, backfill, or historical-artifact cleanup.

## Deferred

- **Checkpoint loading, identity comparison, and resumed execution** — Step 3 owns matching a saved boundary to a fresh sampler and restoring it at the next pass.

- **Final-evidence reader and ledger changes** — Step 4 owns explicit reader rejection coverage and sampler-lifecycle classification.

- **Resume provenance in reports and command presentation** — Step 5 owns reporting that an audit resumed without changing final evidence.

- **Pre-apply checkpoint consolidation** — `plan_tool/cli/completeness_phases.py:write_pre_apply_audit_checkpoint` protects a different phase and remains unchanged.
