# Step 4 — Add the un-enrolled settlement runner `plan_tool/roadmap_decision_settlement_run.py`: commit the receipt first, then publish one stage generation

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step adds `plan_tool/roadmap_decision_settlement_run.py` and its test file, and adds three tests to `tests/test_roadmap_revision_publish.py` that pin behavior this step depends on. The new runner settles one decision on an un-enrolled roadmap, all under one writer lease:

1. It runs the existing journal recovery.
2. It builds step 2's candidate.
3. It publishes and commits step 3's receipt.
4. It checks the source again.
5. It writes the settled artifact through `publish_stage_artifact` with default seed invalidation. That one journaled generation updates the stage file, its baseline record, and `seed-state.json` together.

The key design decision is where the last staleness check runs. Step 2's full currency check runs just before `publish_stage_artifact`. Inside `publish_stage_artifact`'s `before_replace` callback, a raw-byte digest check runs instead. Step 2's check cannot run there: the in-flight journal names this stage's baseline, and baseline admission refuses while that journal exists. `plan_tool/roadmap_revision_publish.py` keeps a zero-line diff. On green, one confirmed call moves a `pending` row to `settled`. Only that row's status line changes in the stage file, and a committed receipt proves the change.

## Table of Contents

- [Why](#why) — why the hand-edit and the reopen writer both fail here, and what is missing at HEAD
- [Input](#input) — the step 2 and step 3 surfaces, the publisher's contract, and the pending-journal gotcha
- [Files (creates vs edits)](#files-creates-vs-edits) — the new runner and tests, the pinning tests, and the files that stay unchanged
- [Implementation](#implementation) — the public surface, outcomes, run order, the two staleness checks, what the write changes, and rejected alternatives
- [Tests](#tests) — named cases per area, which ones are green at HEAD, and the breaks each case must catch
- [Acceptance criteria](#acceptance-criteria) — checks a reviewer can run
- [References](#references) — plan-level references that bear on this step
- [Applicable guardrails](#applicable-guardrails) — the plan fences that bind this runner, and where breaking them is tempting
- [Deferred](#deferred) — work owned by later steps or deliberately left out

## Why

At HEAD, no command settles a decision on an un-enrolled roadmap, and the two nearby routes both break the stage's baseline:

- **The documented hand edit fails source admission.** A decision's `status` is part of `canonical_projection`. A hand-flipped row no longer matches its `.roadmap-baselines` record, and re-entry refuses it. `tests/test_roadmap.py::TestBoundedReentryRoutes::test_semantic_reentry_drift_returns_invalid_without_invocation` pins that refusal.
- **The closest confirmed runner writes only the artifact.** `plan_tool/roadmap_feedback_reopen.py:run_confirmed_feedback_reopen` publishes through `publish_feedback_reopen_candidate`, a one-member `confirmed-feedback-reopen` generation. That works for reopen only because feedback is outside the projection. A status change through the same writer would leave the baseline stale, and every later `admit_baseline_backed_source` on that stage would refuse.
- **The right writer exists but nothing settles through it.** `plan_tool/roadmap_revision_publish.py:publish_stage_artifact` already writes the artifact, its baseline, and invalidated seed state as one journaled generation. Its only production caller is the stage loop in `plan_tool/roadmap.py`, and no caller at HEAD passes `invalidate_seeds`.
- **Steps 2 and 3 provide the preflight and the receipt, but nothing combines them** with the lease, recovery, and write in the order the plan requires, with the receipt committed before the write.

The already-implemented signal flagged `publish_stage_artifact`. The match is real, and the step title expects it: this step reuses that function unchanged. The new work is the runner that calls it.

## Input

- **Step 2's preflight** (`plan_tool/roadmap_decision_settlement.py`):
  - `resolve_decision_settlement_selector(decision_value, evidence_value, *, artifact_keys)`
  - `build_decision_settlement_candidate(selector, *, plans_dir, slug, stages)`
  - `decision_settlement_candidate_is_current(candidate, *, plans_dir, slug, stages) -> bool`
  - `DecisionSettlementRefusal.verdict`
  - `DecisionSettlementCandidate`, whose fields include `settled_artifact`, `source_digest`, `settled_digest`, and `accepted_version_id`
  - Step 2 names `source-changed` in its verdict vocabulary; runners return it when the currency check fails.
  - Step 2 has a detail file but has not landed at HEAD. Read the names off the landed module; the landed names win over this file.
- **Step 3's receipt** (`plan_tool/roadmap_decision_settlement_receipt.py`):
  - `build_decision_settlement_receipt(candidate, *, resulting_version_id)`
  - `publish_decision_settlement_receipt(receipt, *, plans_dir, slug, receipt_committer)`, which returns `DecisionSettlementReceiptPublication(outcome, receipt_id)`
  - `DECISION_SETTLEMENT_RECEIPT_SUCCESS_OUTCOMES`
  - The outcome `Literal`
  - `decision_settlement_receipt_proves_completion`, used by tests only
  - Step 3 has not landed either; its landed names win.
- **`publish_stage_artifact`'s contract, read from the code**:
  - It calls `require_unenrolled_roadmap_writer` itself.
  - It renders `stage.render(artifact)`, parses the result again, and builds the baseline member with `baseline_record` over the parsed artifact.
  - `invalidate_seeds=None` resolves to `True`. It loads the seed state, and `invalidated_seed_state` marks every entry `invalidated`. A malformed seed state raises `RoadmapRevisionPublishError` before the journal is written.
  - The generation kind is `"stage-publication"`. Its members are the artifact, the stage baseline, and `seed-state.json`, in that order.
  - `before_replace` runs after `publish_roadmap_generation` has durably written the journal and before any member is replaced. If the callback raises anything, the journal is deleted and the exception is re-raised, so no member changes.
  - It runs no stage gates.
- **`recover_roadmap_publication`'s un-enrolled branch ignores the generation kind**:
  - A generation that is wholly old or wholly new has its journal dropped.
  - A mix of recorded old and new bytes is restored to the old bytes.
  - Any unrecorded bytes, or a malformed journal, raise `RoadmapPublicationRecoveryError` and leave the journal in place.
- **The pending-journal gotcha.** `plan_tool/roadmap_escalation_selection.py:admit_versioned_artifact_source` calls `plan_tool/roadmap_source_identity.py:admit_baseline_backed_source` with its default `require_no_pending_generation=True`.
  - That call refuses ("roadmap source baseline is pending publication") whenever the journal has a member at the stage's baseline path. A `stage-publication` journal always does.
  - Step 2's build and currency check both admit through that function. During `before_replace`, they therefore return a refusal or `False` every time.
  - Two existing writers handle the same window differently:
    - `plan_tool/roadmap_structural_revision.py` takes an `allowed_pending_generation` argument.
    - The stage loop in `plan_tool/roadmap.py` compares against an in-memory baseline (`recheck_admitted_artifact`).
- **`run_confirmed_feedback_reopen`** is the runner shape to follow: confirmation, then mode, then slug, then lease, then the enrolled refusal, then recovery, then the selector, the candidate, and finally publication with a recheck inside the window. It also supplies the outcome-to-status mapping (`_reopen_result`) and the exception mapping.
- **`plan_tool/roadmap_escalation_run.py:run_roadmap_escalation_receipt`** lazily defaults `receipt_committer` to `plan_tool.cli.gitcommit.commit_receipt` and defines the `ReceiptCommitter` type. Step 3 leaves that default to the runners.
- **Enrollment takes the same writer guard.** `plan_tool/roadmap.py:enroll_roadmap_root` runs under the roadmap writer lease, so a roadmap cannot become enrolled while this runner holds it.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_decision_settlement_run.py` holds the runner, its result type, and its outcome and refusal vocabulary.
  - `tests/test_roadmap_decision_settlement_run.py` holds the runner cases listed under Tests.
- **Existing files (edits only):**
  - `tests/test_roadmap_revision_publish.py` gains three tests that pin `publish_stage_artifact` behavior the runner relies on (see Tests). No existing case changes.
  - `plan_tool/roadmap_revision_publish.py` is declared, but its production code has a **zero-line diff**. That is deliberate: the step reuses `publish_stage_artifact`, its default seed invalidation, its `before_replace` hook, and `recover_roadmap_publication` exactly as they are.
- **Unchanged:**
  - `plan_tool/roadmap_feedback_reopen.py` and `plan_tool/roadmap_escalation_run.py` are precedents only.
  - `plan_tool/roadmap_decision_settlement.py` belongs to step 2, and `plan_tool/roadmap_decision_settlement_receipt.py` belongs to step 3.
  - `plan_tool/roadmap.py` stays unchanged.
  - `plan_tool/cli/roadmap_cmd.py` belongs to step 6.

## Implementation

### Public surface

These names are this step's to choose. Step 6's handler and step 7's docs read them off the landed module.

- **`run_unenrolled_decision_settlement(slug, decision_value, evidence_value, confirmation, *, plans_dir, stages=STAGES, mode_rejected=False, receipt_committer=None) -> DecisionSettlementRunResult`**
  - `decision_value` and `evidence_value` are the raw selector strings. Step 2 parses them.
  - `confirmation` must be exactly `True`, as in the reopen runner.
- **`DecisionSettlementRunResult`** is a frozen dataclass with `outcome`, `status`, `refusal`, and `receipt_id`. It is redacted: no `request`, `proposed_response`, `rationale`, or other row text.
- **`DecisionSettlementOutcome`** is a `Literal`; its members are the five outcomes in the table below.
- **`DecisionSettlementRunRefusal`** is a type alias that joins three sets of names:
  - step 2's verdict `Literal`;
  - this runner's own names: `confirmation-required`, `mode-rejected`, `enrolled-roadmap-rejected`, and `journal-unrecoverable`;
  - step 3's non-success receipt outcomes.

### Outcomes and refusals

| Outcome | `status` | `refusal` |
| --- | --- | --- |
| `settled` | `0` | `None` |
| `preflight-rejected` | `2` | one of: `confirmation-required`, `mode-rejected`, `enrolled-roadmap-rejected`, `journal-unrecoverable`, or any step 2 verdict, including `source-changed` |
| `receipt-rejected` | `1` | the receipt publisher's outcome, copied exactly (every outcome outside `DECISION_SETTLEMENT_RECEIPT_SUCCESS_OUTCOMES`) |
| `write-failed` | `1` | `None` |
| `interrupted` | `130` | `None` |

- **Each plan refusal case keeps its own name.** Step 2's verdicts cover cases 1–11. `journal-unrecoverable` covers case 12 on this lineage. The receipt outcome names cover case 15.
- **Treat receipt failures as one outcome with one status.** `no-worktree` included, every non-success receipt outcome is a failure to complete the receipt lifecycle, so all get `status` `1`. The operator reads the specific reason in `refusal`.
- **`receipt_id` is set whenever step 3's publisher returned a success outcome**, no matter what happens afterward. A later `source-changed`, `write-failed`, or `interrupted` still reports it, so the operator can find the receipt left by the attempt. It is `None` on every path that stops before the receipt.

### Run order

The order below must hold. Each refusal returns right away and skips the remaining steps.

1. `confirmation is not True` → `confirmation-required`. Nothing on this path touches the filesystem.
2. `mode_rejected` → `mode-rejected`.
3. `roadmap_dir(plans_dir, slug)` raises `TypeError` or `ValueError` → `mode-rejected`, matching the reopen runner.
4. Default `receipt_committer` to `plan_tool.cli.gitcommit.commit_receipt` through a lazy import inside the function, as `run_roadmap_escalation_receipt` does.
5. Enter `roadmap_writer_guard(plans_dir, slug)`. Steps 6–13 all run inside this one lease.
6. `require_unenrolled_roadmap_writer` raises `EnrolledRoadmapWriteError` or `RoadmapWriterGuardError` → `enrolled-roadmap-rejected`. Recovery does not run on an enrolled roadmap here; step 5's runner owns that lineage.
7. `recover_roadmap_publication(...)`. A `RoadmapPublicationRecoveryError` from **this call only** → `journal-unrecoverable`. The journal stays where recovery left it; this runner never repairs it.
8. `resolve_decision_settlement_selector(...)` returns a refusal → that verdict. Following the reopen runner, selector parsing may also run before the lease. Either placement is acceptable, as long as the build in step 9 never reads before recovery.
9. `build_decision_settlement_candidate(...)` returns a refusal → that verdict. Nothing has been written yet, and no receipt exists.
10. `build_decision_settlement_receipt(candidate, resulting_version_id=None)`, then `publish_decision_settlement_receipt(...)`. An outcome outside the success set → `receipt-rejected` with that outcome name. **Stop here. No canonical write happens.**
11. **Full recheck:** `decision_settlement_candidate_is_current(candidate, ...)` returns `False` → `source-changed`. The receipt stays as evidence of the attempt.
12. `publish_stage_artifact(candidate.settled_artifact, stage=<the selector's stage>, plans_dir=..., slug=..., writer_token=..., before_replace=<the byte check below>)`.
13. Return `settled` with the receipt id.

### The two staleness checks

- **The full recheck (step 11) runs outside the journal window.** It proves again that admission, canonical form, the decision checks, the evidence checks, and step 1's one-line byte contract all still hold. It catches anything that moved while the receipt was being committed, including a Git hook editing files and a changed or deleted baseline record, which the byte check cannot see.
- **The byte check runs inside `before_replace`.** It compares the SHA-256 of the stage file's raw bytes (`stage.artifact_path(plans_dir, slug).read_bytes()`) with `candidate.source_digest`. This is the same raw-byte rule as `CanonicalArtifactSnapshot.source_digest`.
  - A mismatch or a read failure raises a private stale-source exception, which the runner reports as `source-changed`.
  - `publish_roadmap_generation` then deletes the journal, and no member changes.
- **Never call step 2's build or currency check, `admit_versioned_artifact_source`, or `admit_baseline_backed_source` inside `before_replace`.** The journal names this stage's baseline at that moment, so each of them refuses on every run. See Input → the pending-journal gotcha.
- **The byte check is enough inside the window.** Under the lease, only a non-participating edit can change the stage file, and any such edit changes its bytes. The byte check is also stricter than admission, because it sees a feedback-only edit.
- **Do not pass `expected_feedback_snapshot`.** The byte check already covers every feedback row.

### What the write changes

- **The only canonical members written are the stage file, its baseline record, and `seed-state.json`.** The only other new file under the roadmap root is the receipt final from step 10, which lives in the evidence namespace. No other stage file, baseline, or artifact is rewritten.
- **Call `publish_stage_artifact` without `invalidate_seeds`, `allow_existing_baseline_without_artifact`, or `expected_feedback_snapshot`.**
  - Never pass `invalidate_seeds`, not even an explicit `True`. The default is the contract the plan names, and its absence from the call is checked by a spy test and an `rg` criterion.
  - Every tracked draft seed is marked `invalidated`, the same as for any other stage-level content change (`ROADMAP_FORMAT.md` § "Invalidation and explicit refresh").
- **The generation kind stays `"stage-publication"`.** This lineage mints no new `PendingGeneration.kind`, and `recover_roadmap_publication` is unchanged; its un-enrolled branch ignores the kind.
- **The written bytes equal `candidate.settled_bytes`.** `publish_stage_artifact` renders the same `settled_artifact` with the same `stage.render` step 2 used. So the receipt's `resulting_artifact_digest` names exactly the file's new bytes, and a test pins that.
- **No gate runs on this lineage.**
  - `publish_stage_artifact` runs none, and this runner adds none.
  - The plan's gate refusal (Testing case 14) applies to the enrolled lineage only.
  - Step 2 has already proved that the only change is one status line on an admitted, canonical source.
- **Downstream stages are not re-run or rewritten.** Their draft seeds are covered by the seed-state member.
- **The cited feedback row is unchanged**, including its state and `proposed_response`. Step 1's helper preserves every row except the selected decision.

### Exception mapping

- The private stale-source exception → `preflight-rejected` / `source-changed`.
- `KeyboardInterrupt` → `interrupted` (`130`).
  - The `with` block releases the lease.
  - If the interrupt lands during member replacement, the journal stays behind, and the next run's step 7 recovers it.
- The following all map to `write-failed` (`1`):
  - `OSError`;
  - `RoadmapArtifactError`;
  - `RoadmapRevisionPublishError`, including `EnrolledRoadmapWriteError` and a `RoadmapPublicationRecoveryError` raised by publication rather than recovery;
  - `RoadmapWriterGuardError`;
  - `ValueError`, which covers step 2's byte-contract `ValueError`, `RoadmapVersionError`, and step 3's `DecisionSettlementReceiptError`.
- **Catch the recovery error at the recovery call only.** A `RoadmapPublicationRecoveryError` from `publish_roadmap_generation` ("did not commit its recorded generation") is a failed write, not an unrecoverable leftover journal.
- **An enrolled candidate cannot reach the write.** The lease rules out enrollment after step 6. Even so, step 3's builder rejects `resulting_version_id=None` on an enrolled candidate, and `publish_stage_artifact` checks enrollment again. So this path fails closed without an extra check here.

### Module rules

- **No backend call, no invoker seam, and no run log**, matching `run_confirmed_feedback_reopen`, which writes a canonical artifact with neither.
- **Writes go only through step 3's publisher and `publish_stage_artifact`.** The module makes no direct file writes and calls neither `publish_roadmap_generation` nor any accepted-head helper.
- **Imports:**
  - `plan_tool.roadmap` (for `STAGES` and `RoadmapStage`, as the reopen runner does);
  - `plan_tool.roadmap_artifacts`;
  - step 2's module;
  - step 3's module;
  - `plan_tool.roadmap_revision_publish`.
  - `plan_tool.cli` is imported only lazily, for the committer default.
  - Never import `plan_tool.roadmap_feedback_reopen`, whose `_admitted_stage_source` is private.

### Rejected alternatives

- **Writing through `publish_feedback_reopen_candidate` or any artifact-only generation.** The baseline would go stale on the first settlement, and every later admission on that stage would fail.
- **`publish_revision_candidate`.** It runs stage gates over caller-admitted upstream artifacts and uses the `feedback-publication` kind. The plan names `publish_stage_artifact`, and it asks for no gate run on this lineage.
- **A new `PendingGeneration.kind` for un-enrolled settlement.** Recovery on this lineage ignores the kind, and the step title keeps recovery unchanged. The new kind belongs to step 5's enrolled write only.
- **Adding a pending-generation allowance to step 2's currency check** (like `allowed_pending_generation`), so it could run inside the window. That changes step 2's module and its tested contract, and the byte check already closes the window.
- **Relying on the full recheck alone.** That leaves the gap between the check and the journal write unguarded. The reopen runner and the stage loop both recheck inside the window, and this runner must too.
- **Publishing the receipt under a reader lease, then taking a writer lease for the write.** Two leases leave a gap in which another writer can move the source between the receipt and the write. One writer lease covers both.
- **Committing the receipt after the canonical write.** The plan requires the receipt to come first, so an interrupted write always leaves inspectable evidence.

## Tests

**Fixture approach:**

- Give the runner test file an autouse fixture that runs `git init` in `tmp_path` and sets `user.email` / `user.name`, as `tests/test_roadmap_escalation_run.py` does. Use the real `commit_receipt` unless a case injects a committer.
- Write stage files with the real renderers and `plan_tool.roadmap.STAGES`.
- Write baselines with `baseline_record` + `render_baseline_record`, as `tests/test_roadmap_feedback_reopen.py:_write_baseline` does.
- Write seed state with `write_seed_state`, and write journals with `render_pending_generation`.
- **Never build fixtures through this runner**, `publish_stage_artifact`, or `enroll_roadmap_root`. Keeping fixtures raw keeps each suite independent of the writer it guards. Write the enrolled refusal case's accepted head by hand with `render_accepted_head`.

### Tests for this step

**`tests/test_roadmap_revision_publish.py` (3 cases, all green at HEAD).** They pin current `publish_stage_artifact` behavior with no production change, so write them first. They guard the reused contract while the runner is built.

- `test_stage_publication_default_invalidates_every_tracked_seed_and_rewrites_the_stage_baseline`: with seed state holding a current unpublished entry and a current published entry, a call without `invalidate_seeds` marks both `invalidated`, and the baseline file equals `render_baseline_record(baseline_record(<published artifact>, ...))`.
- `test_stage_publication_before_replace_refusal_leaves_artifact_baseline_and_seed_state_unchanged`: a raising callback leaves all three files with their old bytes and leaves no journal.
- `test_stage_publication_journal_names_the_stage_baseline_during_before_replace`: inside the callback, the journal exists, its kind is `stage-publication`, and it has a member at the stage's baseline path. This pins the fact that makes admission-based rechecks refuse inside the window.

**`tests/test_roadmap_decision_settlement_run.py`.** The module is new, so every case lands with it.

*Refusals before the lease:*

- `test_missing_or_non_true_confirmation_refuses_before_any_filesystem_access` (parametrized: `None`, `False`, `"yes"`): `confirmation-required` with status `2`, and neither the writer lock file nor an evidence directory exists.
- `test_mode_rejected_refuses_before_any_filesystem_access`: `mode-rejected`.
- `test_invalid_slug_is_mode_rejected`.

*Lease, lineage, and recovery:*

- `test_enrolled_roadmap_is_refused_before_recovery_and_preflight`: with a hand-written accepted head, the result is `enrolled-roadmap-rejected`, a recovery spy is never called, and the stage file is unchanged.
- `test_recovery_rolls_back_a_half_written_generation_before_the_preflight_reads`: a mixed-member journal is rolled back, and the run then settles against the restored bytes.
- `test_unrecoverable_journal_is_refused_as_journal_unrecoverable_and_left_in_place`: the journal bytes are unchanged, no receipt is published, and nothing is written.
- `test_publication_recovery_error_after_the_receipt_is_a_write_failure_not_journal_unrecoverable`: a stubbed `publish_stage_artifact` raises `RoadmapPublicationRecoveryError`, and the result is `write-failed`. This pins that the name belongs to the recovery call only.

*Preflight wiring:*

- `test_preflight_refusals_are_reported_verbatim_and_publish_no_receipt` (parametrized over representative step 2 verdicts: `malformed-decision-selector`, `missing-decision`, `inherited-decision`, `decision-not-pending`, `feedback-not-targeting-decision`, `empty-request`, `source-not-admitted`, `source-not-canonical`): `preflight-rejected` with `refusal` equal to the verdict, no evidence directory, and the stage file, baseline, and seed state unchanged.
- `test_documented_hand_edit_is_refused_until_the_pre_edit_bytes_are_restored`: hand-flipping another decision's status gives `source-not-admitted`. After the original bytes are restored, the same call settles.

*Receipt ordering:*

- `test_receipt_is_committed_to_head_before_the_stage_publication_starts`: a spy wrapping the runner's module-global `publish_stage_artifact` asserts that, at call time, `HEAD`'s last commit lists the receipt path.
- `test_each_non_success_receipt_outcome_stops_before_any_canonical_write` (parametrized over every member of step 3's outcome `Literal` outside the success set, taken from `typing.get_args` so a new failure outcome is covered automatically): with the module-global publisher stubbed, the result is `receipt-rejected` with `refusal` equal to the outcome and status `1`, `publish_stage_artifact` is never called, the three files are unchanged, and `receipt_id is None`.
- `test_no_git_worktree_is_refused_as_receipt_rejected_with_no_write`: the real publisher with no Git repository gives `no-worktree`, and the stage file is unchanged.
- `test_commit_failure_stops_the_write_and_a_retry_settles_as_committed_existing`: a failing committer, then the real one. The second run settles, a publisher spy sees `committed-existing`, and exactly one receipt final exists.

*Staleness:*

- `test_source_change_during_the_receipt_commit_refuses_as_source_changed` (parametrized: a canonical feedback-only edit to the stage file; deleting the stage's baseline file): a committer makes the change, then commits. The result is `source-changed` with `receipt_id` set, the receipt is at `HEAD`, the baseline (where not deleted) and seed state are unchanged, and `decision_settlement_receipt_proves_completion` returns `False`.
- `test_source_edit_inside_the_journal_window_refuses_and_leaves_no_journal`: `roadmap_revision_publish.durable_write_bytes` is patched so that writing the journal also edits the stage file. The result is `source-changed`, no journal remains, and the baseline and seed state are unchanged.
- `test_no_admission_check_runs_while_the_stage_publication_journal_exists`: a spy on step 2's module-global admission call records whether the journal exists at each call. Every recorded value is `False`, and the run settles.

*The write:*

- `test_settlement_changes_only_the_selected_status_line`: the stage file differs from its prior bytes in exactly one line, `status: pending` → `status: settled`.
- `test_settlement_rewrites_the_stage_baseline_so_later_admission_still_passes`: the baseline equals `baseline_record` of the new artifact, and `admit_versioned_artifact_source` over the new file returns an admission. That is the check `--escalate-feedback` runs.
- `test_feedback_reopen_on_the_settled_stage_still_succeeds`: `run_confirmed_feedback_reopen` on another `awaiting-review` row in the same stage returns `reopened`.
- `test_settlement_marks_every_tracked_seed_invalidated`: current entries, including a published one, are all `invalidated`.
- `test_runner_relies_on_the_default_seed_invalidation`: a spy on `publish_stage_artifact` sees no `invalidate_seeds` keyword.
- `test_only_the_stage_file_its_baseline_seed_state_and_one_receipt_change`: a byte snapshot of every file under the roadmap root before and after shows exactly those four paths changed or added. Other stage files and baselines are unchanged.
- `test_cited_feedback_row_keeps_its_state_and_response`: an `awaiting-review` row with a `proposed_response`, the plan's motivating case, is unchanged after settlement.
- `test_written_bytes_match_the_receipts_resulting_digest_and_the_receipt_proves_completion`: `sha256(stage file) == candidate.settled_digest`, and step 3's read-back returns `True`.

*Failures and retries:*

- `test_write_failure_after_the_receipt_reports_write_failed_and_keeps_the_receipt` (parametrized: `OSError`, `RoadmapRevisionPublishError`, `ValueError` raised by a stubbed `publish_stage_artifact`): the result is `write-failed` with status `1`, and `receipt_id` is set.
- `test_interrupted_write_is_recovered_and_a_retry_reuses_the_same_receipt`: the first run fails while writing the baseline member and leaves a journal. The retry recovers it and settles, the publisher spy sees `reused`, and exactly one receipt final exists.
- `test_keyboard_interrupt_reports_interrupted_and_releases_the_lease`: the result is `interrupted` (`130`), and `roadmap_writer_guard` can be entered afterward.
- `test_retry_after_a_completed_settlement_is_refused_as_decision_not_pending`: a second identical call returns `decision-not-pending`, publishes no second receipt, and changes no file.

*Result and module rules:*

- `test_result_carries_only_outcome_status_refusal_and_receipt_id`: the dataclass has exactly those fields, and the fixture's `request`, `rationale`, and `proposed_response` strings are absent from its `repr`.
- `test_every_outcome_maps_to_its_status` (parametrized over the five outcomes).
- `test_module_writes_only_through_the_receipt_publisher_and_publish_stage_artifact`: a source scan finds no `write_bytes`, `write_text`, `durable_write`, `publish_roadmap_generation`, `accepted_head`, `invalidate_seeds`, `unlink`, `invoker`, `RunLogWriter`, or top-level `plan_tool.cli` import.

That is 3 cases in the publish file and approximately 31 in the runner file. Every one must be green before this step counts as finished, and so must `uv run pytest tests/ -q -n auto`.

**Verify by breaking the code, not by reading it.** Each break below must turn at least one case red:

| Deliberate break | Case that must go red |
| --- | --- |
| Call step 2's currency check inside `before_replace` | the no-admission-in-window case, and every case expecting `settled` |
| Drop the byte check inside the window | the journal-window edit case |
| Drop the full recheck after the receipt | the baseline-deleted variant of the commit-window case |
| Pass `invalidate_seeds=False` | the seed-invalidation case and the default-spy case |
| Publish the receipt after the write | the receipt-before-publication case |
| Continue after a non-success receipt outcome | the non-success receipt outcomes case |
| Write through `publish_feedback_reopen_candidate` | the baseline-rewrite / later-admission case |
| Map every `RoadmapPublicationRecoveryError` to `journal-unrecoverable` | the publication-recovery-error case |
| Skip recovery | the half-written-generation case |

## Acceptance criteria

- `run_unenrolled_decision_settlement` returns `settled` with status `0` for a Roadmap-derived pending decision cited by a `ROW`-targeted feedback row with a non-blank `request`, on an un-enrolled roadmap with a recorded baseline.
- After a settled run:
  - the stage file differs from its prior bytes in exactly the selected row's `status` line;
  - its baseline equals `baseline_record` of the new artifact;
  - every seed-state entry is `invalidated`;
  - the only paths changed under the roadmap root are the stage file, its baseline, `seed-state.json`, and one receipt final.
- The receipt is committed to `HEAD` before `publish_stage_artifact` is called, and its `resulting_artifact_digest` equals the SHA-256 of the new stage file.
- Every refusal before the receipt leaves no evidence directory and no canonical write. Every refusal or failure after the receipt leaves the receipt in place, makes no canonical write, and reports `receipt_id`.
- Each non-success receipt outcome is reported as `receipt-rejected` with that outcome's own name.
- A source edit inside the journal window returns `source-changed` and leaves no journal.
- An unrecoverable journal returns `journal-unrecoverable` and stays in place.
- `rg -n "invalidate_seeds|accepted_head|publish_roadmap_generation|durable_write|write_bytes|write_text|unlink" plan_tool/roadmap_decision_settlement_run.py` returns nothing.
- `rg -n "^from plan_tool\.cli|^import plan_tool\.cli|roadmap_feedback_reopen" plan_tool/roadmap_decision_settlement_run.py` returns nothing.
- `git diff --stat` shows no change to `plan_tool/roadmap_revision_publish.py`, `plan_tool/roadmap_feedback_reopen.py`, `plan_tool/roadmap_escalation_run.py`, `plan_tool/roadmap.py`, or `plan_tool/cli/roadmap_cmd.py`.
- `uv run pytest tests/test_roadmap_decision_settlement_run.py tests/test_roadmap_revision_publish.py -q` passes, and so does `uv run pytest tests/ -q -n auto`.

## References

- `plan_tool/roadmap_revision_publish.py` (`publish_stage_artifact`, `publish_roadmap_generation`, `recover_roadmap_publication`, `require_unenrolled_roadmap_writer`) is the multi-member generation and journal recovery this step reuses unchanged.
- `plan_tool/roadmap_feedback_reopen.py` (`run_confirmed_feedback_reopen`) and `plan_tool/roadmap_escalation_selection.py` (`CanonicalArtifactSnapshot.source_digest`, `admit_versioned_artifact_source`) supply the runner shape, the recheck inside the window, and the raw-byte digest rule.
- `plan_tool/roadmap_escalation_run.py` (`run_roadmap_escalation_receipt`, `ReceiptCommitter`) supplies the lazy `commit_receipt` default and the receipt-before-anything-else precedent.
- `plan_tool/roadmap_structural_revision.py` (`allowed_pending_generation`) is the other in-repo answer to the pending-journal problem, recorded under Rejected alternatives.
- `docs/how-to/roadmap.md` §4 ("Settle a pending decision or re-gate an existing stage") is the hand-edit procedure this runner replaces.
- `ROADMAP_FORMAT.md` § "Invalidation and explicit refresh" is the seed-invalidation rule the default applies.

## Applicable guardrails

- **The plan's "## Scope guardrails": only `pending → settled` on exactly one Roadmap-derived row per call.**
  - The runner takes one decision value and one evidence value, and it writes only step 2's `settled_artifact`.
  - The tempting site is a non-canonical or drifted source: "fixing" it by re-rendering or re-admitting other rows. Refuse instead.
  - Checked by the one-line diff case.
- **The plan's "## Scope guardrails": no other field or row changes.**
  - The four-path snapshot case and the one-line diff case pin this.
  - The tempting site is passing a freshly parsed artifact rather than the candidate's `settled_artifact`.
- **The plan's "## Scope guardrails": no judgment of the cited feedback, and the row's state never changes.**
  - The runner reads no row text, and its result is redacted.
  - The tempting site is the result type, where echoing the `request` "for confirmation" looks harmless.
  - Checked by the redaction case and the cited-row case.
- **The plan's "## Scope guardrails": no accepted-head write outside the guarded swap.**
  - This runner refuses an enrolled roadmap before recovery, and the `rg` criterion bans accepted-head helpers from the module.
- **The plan's "## Scope guardrails": not a batch operation.**
  - One call settles one decision. The runner has no loop over selectors.
- **The plan's "## Out of scope": no recovery of a malformed or interrupted journal.**
  - The runner calls the existing recovery, reports what it refuses as `journal-unrecoverable`, and leaves the journal in place. It never repairs one.
- **The plan's "## Out of scope": no change to `--apply`'s count-only reporting.**
  - This runner does not touch it.

## Deferred

- **The enrolled lineage** (versioned write, the new `"decision-settlement"` generation kind, the candidate-lineage refusal, and the gate refusal) — step 5. Step 5 may reuse `DecisionSettlementRunResult` and extend the refusal alias with its own names; that choice is step 5's.
- **The CLI flags, the confirm flag, two-way exclusivity with every other roadmap mode, and regenerating `docs/cli/roadmap.md`** — step 6.
- **The cross-lineage identical-row assertion, and the `check_settled_decisions` drift test on a row this route settled** — step 6.
- **Docs** — step 7. That covers the route itself, the `docs/ARCHITECTURE.md` module entry, CLAUDE.md's import list, and extending the `BUG_BACKLOG.md` journal entry. On this lineage the generation shape is the existing `stage-publication` kind.
- **A pending-generation allowance in step 2's currency check** — not built. The byte check closes the window. If one is wanted later, it is a change to step 2's module, not this runner.
- **A run log or telemetry for settlement** — deliberately none, matching `run_confirmed_feedback_reopen`: no backend call is made. File a `BACKLOG.md` entry if one is wanted.
- **Re-gating the settled stage or running downstream stages again on the un-enrolled lineage** — deliberately not done. The plan's gate refusal is enrolled only, and downstream draft seeds are already marked invalidated.
- **Sharing runner scaffolding (status mapping, exception mapping) with the reopen runner** — not in this step, because the two vocabularies differ. Any merge needs a `BACKLOG.md` entry with machine-verified identity evidence and its excluded look-alikes.
