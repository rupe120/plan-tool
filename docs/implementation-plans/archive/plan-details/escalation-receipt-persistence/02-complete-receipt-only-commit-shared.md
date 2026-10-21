> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Complete the receipt-only commit and shared-read lifecycle

## Summary

Wire step 1’s receipt-only commit helper into the existing escalation lifecycle and make shared Git history the admission boundary for trusted receipt use. Update `plan_tool/roadmap_escalation_run.py`, receipt consumers, CLI wiring, and receipt telemetry so a newly published receipt is trusted only after its exact stored bytes are in `HEAD`. Narrow `.gitignore` so escalation receipts can be committed while impact analyses remain local runtime evidence. On green, a fresh receipt commits only itself, a matching local receipt resumes only when its `HEAD` path is absent, and views or downstream routes reject an unshared receipt.

## Table of Contents

- [Summary](#summary) — The completed lifecycle and visible result.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why local receipt bytes cannot grant shared authority.
- [Input](#input) — The receipt, Git, lock, and telemetry contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — The files this step changes.
- [Implementation](#implementation) — Receipt commit, shared-read, and local-analysis rules.
- [Tests](#tests) — Focused lifecycle, admission, and contract coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Git and subprocess behavior used by this step.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that limit this work.
- [Deferred](#deferred) — Related work left outside this step.

## Why

`plan_tool/roadmap_escalation_run.py:run_roadmap_escalation_receipt` currently treats successfully stored local evidence as a trusted receipt, while `plan_tool/cli/roadmap_cmd.py:_render_escalation_receipts`, `plan_tool/roadmap_impact_run.py:_load_requested_receipt`, and `plan_tool/roadmap_structural_revision.py:load_structural_revision_preflight` can consume the same local bytes. That allows a receipt left behind by a failed or interrupted commit to expose a handoff or authorize downstream work before it is shared. The lifecycle must make the exact `HEAD` bytes the common authority boundary without turning impact analyses into committed evidence.

## Input

- **Step 1 receipt commit helper:** Step 1 provides the scoped Git operation and its `(returncode, stderr-tail)` result shape. Inject that operation from `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_escalation_receipt` into `plan_tool/roadmap_escalation_run.py:run_roadmap_escalation_receipt`; preserve its `KeyboardInterrupt` behavior for the lifecycle to classify.

- **Immutable evidence:** `plan_tool/roadmap_evidence_store.py:EvidenceNamespace` supplies `ESCALATIONS`; `publish_evidence`, `read_evidence_final`, and `namespace_relative_components` continue to own opaque storage and the final path. Compare the stored receipt bytes with the exact file bytes available from `HEAD`; do not derive authority from a semantic id alone.

- **Controlling Git worktree:** Derive the receipt Git worktree from the directory that contains `plans_dir`, not from the independently resolved command repository root. An explicit external plans directory uses its own containing Git worktree; if it has none or the receipt cannot be represented beneath it, reject before publication.

- **Reader coordination:** Keep `plan_tool/roadmap_revision_publish.py:bootstrap_roadmap_reader_lock` and `roadmap_reader_guard` as the protection for receipt admission, recheck, publication, and the receipt commit decision. Receipt persistence must not weaken writer serialization.

- **Closed output contracts:** Extend `plan_tool/roadmap_escalation_run.py:EscalationRunResult` and `plan_tool/run_log.py:RoadmapEscalationResult` together. `created`, `committed-existing`, and `reused` are the only successful shared receipt outcomes; `commit-failed` and `interrupted` retain no receipt identity or trusted handoff.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `.gitignore` — Replace the broad evidence ignore entry with an impact-analysis-only rule, leaving escalation receipt finals available to the scoped commit helper.
  - `DATA_CONTRACT.md` — Update the `RoadmapEscalationResult` outcome, identity, handoff, ordering, and status documentation for receipt commits.
  - `ROADMAP_FORMAT.md` — State the receipt commit boundary, matching-local recovery behavior, `HEAD`-based reader admission, and the unchanged local impact-analysis boundary.
  - `TESTING.md` — Update roadmap receipt and impact-analysis test guidance for temporary Git repositories, shared receipt admission, and local analysis publication.
  - `plan_tool/cli/roadmap_cmd.py` — Import step 1’s helper, inject it into receipt creation, pass repository context to receipt inspection, and keep rendered output redacted.
  - `plan_tool/roadmap_escalation_run.py` — Add the receipt commit and recovery lifecycle, shared-byte predicate, result mapping, and guarded ordering.
  - `plan_tool/roadmap_impact_run.py` — Reject a named receipt unless its stored local bytes match the exact `HEAD` path; leave analysis publication local.
  - `plan_tool/roadmap_structural_revision.py` — Apply the same shared receipt admission before an exact receipt-analysis pair can build structural preflight context.
  - `plan_tool/run_log.py` — Admit the new closed escalation outcomes and keep receipt identity and handoff absent for non-shared results.
  - `tests/cli/test_roadmap_cmd.py` — Cover helper injection, redacted CLI outcomes, and receipt views that withhold a local-only handoff.
  - `tests/test_roadmap_escalation_run.py` — Cover fresh commit, `HEAD` reuse, matching-local recovery, failed commit, interruption, guard ordering, and unrelated Git state.
  - `tests/test_roadmap_impact_run.py` — Make receipt fixtures shared where needed, reject unshared receipts, and prove impact-analysis finals remain ignored.
  - `tests/test_roadmap_revision_publish.py` — Keep structural-publication fixtures shared when they invoke receipt preflight under the writer guard.
  - `tests/test_roadmap_structural_revision.py` — Make exact-pair fixtures commit the receipt and add a local-only receipt refusal case.
  - `tests/test_run_log.py` — Pin the expanded receipt outcome vocabulary and its identity/handoff nullability.

## Implementation

- **Bind every receipt Git operation to the roadmap worktree.** Resolve the Git worktree from `plans_dir` once for receipt publication, inspection, impact analysis, and structural revision; do not use the separately resolved command root for any receipt `HEAD` comparison. An explicit external plans directory uses the worktree that contains it. If no controlling Git worktree exists or the receipt path is outside it, reject before immutable publication and emit no trusted receipt fact.

- **Make exact `HEAD` bytes the shared predicate.** Keep one shared receipt-admission check in `plan_tool/roadmap_escalation_run.py` and reuse it from `current_escalation_receipt`, `plan_tool/roadmap_impact_run.py:_load_requested_receipt`, and `plan_tool/roadmap_structural_revision.py:load_structural_revision_preflight`. It must use the receipt’s controlling-worktree-relative evidence path and compare raw bytes, not only a final name or semantic id. A missing `HEAD` path, unreadable Git result, or byte mismatch must fail closed.

- **Keep local receipt reads limited to recovery.** `run_roadmap_escalation_receipt` is the sole consumer allowed to use matching local receipt bytes that are not in `HEAD`. `current_escalation_receipt` must return an existing no-handoff state rather than `fresh`; impact analysis and structural preflight must reject before snapshot capture, route construction, or publication.

- **Commit after immutable publication and before success.** Keep the current selected-source preflight and final recheck intact. After `publish_evidence` creates a receipt, invoke step 1’s helper for that exact final path while the reader guard remains active. Do not report `created`, a receipt identity, or a handoff until the commit succeeds.

- **Distinguish the four matching-receipt cases.** A matching receipt already present with byte-identical `HEAD` bytes returns `reused` without another commit. A matching local receipt whose `HEAD` path is absent invokes only its own receipt commit and returns `committed-existing` on success. Different bytes at an existing `HEAD` path return `collision` even when the local receipt is otherwise valid, and neither variant may overwrite the other. A malformed existing final remains `invalid-existing-receipt` and must not be committed.

- **Keep failures recoverable and untrusted.** A nonzero or process-launch failure from the injected commit helper returns `commit-failed`, keeps the immutable receipt bytes on disk, and exposes neither identity nor handoff. The helper unwinds only its receipt staging when staging occurred; a launch failure before staging changes nothing. A `KeyboardInterrupt` returns `interrupted` without deleting or resetting receipt bytes. A later matching request must decide between `reused` and `committed-existing` from the current exact `HEAD` comparison.

- **Preserve user-owned Git state through tool operations.** Rely on step 1’s scoped helper rather than `plan_tool/cli/gitcommit.py:commit_all`. The lifecycle must not add a broad staging or reset path, inspect unrelated changes, or change unrelated index entries or worktree files. Repository hooks remain external Git policy; do not add a hook sandbox or an attempt to repair arbitrary hook effects.

- **Keep impact analyses local.** Edit `.gitignore` only enough to release `EvidenceNamespace.ESCALATIONS`. `plan_tool/roadmap_impact_run.py:_run_while_guarded` must keep publishing `EvidenceNamespace.IMPACT_ANALYSES` without Git operations, and a successful analysis must not leave an untracked impact final in status output.

- **Keep telemetry closed and redacted.** Update `RunLogWriter.roadmap_escalation_result` and the `RoadmapEscalationResult` type so only `created`, `committed-existing`, and `reused` carry `receipt_id` and `requires-scope-review`. Add `commit-failed` as a non-durable terminal outcome. Do not add commit text, paths, hook output, reviewer text, raw receipt bytes, or Git diagnostics to events.

- **Keep the CLI thin.** `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_escalation_receipt` owns dependency injection and result rendering only. Do not add a flag, prompt, backend call, broad Git action, or a second receipt-selection path.

- **Update contract prose at its owning surfaces.** In `ROADMAP_FORMAT.md` update the receipt lifecycle and reader-status rules; in `DATA_CONTRACT.md` update the run-log contract; in `TESTING.md` update the test-location guidance. Keep `plan_tool/roadmap_evidence_store.py` unchanged because this step changes authority over stored bytes, not storage representation.

## Tests

### Tests for this step

- `tests/test_roadmap_escalation_run.py::test_fresh_receipt_commits_only_its_final_before_created` — A fresh receipt is published, committed through the injected helper, reported as `created`, and leaves no receipt dirt.

- `tests/test_roadmap_escalation_run.py::test_matching_head_receipt_reuses_without_a_second_commit` — Matching local and `HEAD` bytes return `reused` without invoking another commit.

- `tests/test_roadmap_escalation_run.py::test_matching_local_receipt_resumes_only_when_head_path_is_absent` — Matching local bytes with an absent `HEAD` path invoke only the receipt commit and return `committed-existing`.

- `tests/test_roadmap_escalation_run.py::test_same_final_different_head_bytes_returns_collision_without_commit` — Two valid same-final receipt byte variants do not overwrite shared evidence; the local variant returns `collision` and invokes no commit.

- `tests/test_roadmap_escalation_run.py::test_commit_failure_keeps_matching_local_receipt_without_handoff` — A failed commit preserves the receipt for recovery, returns `commit-failed`, and leaves receipt identity and handoff empty.

- `tests/test_roadmap_escalation_run.py::test_commit_process_launch_failure_keeps_matching_local_receipt_without_handoff` — A helper launch failure has the same recoverable, redacted `commit-failed` result.

- `tests/test_roadmap_escalation_run.py::test_commit_interruption_preserves_receipt_without_handoff` — An interrupted commit returns `interrupted` without deletion, reset, identity, or handoff.

- `tests/test_roadmap_escalation_run.py::test_receipt_commit_tool_operations_preserve_unrelated_staged_and_unstaged_changes` — The full lifecycle's own operations preserve separate user-owned index and worktree changes while committing the receipt.

- `tests/test_roadmap_escalation_run.py::test_reader_guard_covers_receipt_commit_decision` — The reader guard remains active through source recheck, immutable publication, and receipt commit handling.

- `tests/cli/test_roadmap_cmd.py::test_receipt_command_injects_the_scoped_commit_helper` — The CLI passes step 1’s helper and repository context to the receipt runner without adding a new command surface.

- `tests/cli/test_roadmap_cmd.py::test_external_plans_dir_binds_receipt_to_its_controlling_git_worktree` — An explicit external plans directory commits and admits the receipt through its own containing worktree, not the command’s independently resolved root.

- `tests/cli/test_roadmap_cmd.py::test_external_plans_dir_without_git_rejects_receipt_before_publication` — A supported directory-mode invocation with no containing Git worktree returns the existing pre-publication refusal and writes no receipt.

- `tests/cli/test_roadmap_cmd.py::test_escalation_view_withholds_handoff_for_receipt_not_in_head` — A locally valid but unshared receipt never renders as fresh and never prints a handoff.

- `tests/test_roadmap_impact_run.py::test_impact_analysis_rejects_receipt_not_matching_head` — A named local-only receipt cannot capture a snapshot, calculate a route, or publish an analysis.

- `tests/test_roadmap_impact_run.py::test_impact_analysis_publication_remains_ignored_after_receipt_ignore_change` — A successful analysis writes local evidence without creating an untracked worktree entry.

- `tests/test_roadmap_structural_revision.py::test_structural_preflight_rejects_receipt_not_matching_head` — A local-only receipt cannot bind a structural receipt-analysis pair.

- `tests/test_roadmap_structural_revision.py::test_exact_pair_preflight_accepts_a_byte_identical_head_receipt` — Existing exact-pair coverage uses a committed receipt and still admits current evidence.

- `tests/test_roadmap_revision_publish.py::test_structural_publication_fixture_uses_shared_receipt_evidence` — The writer-guard publication path keeps its valid receipt fixture committed rather than relying on local bytes.

- `tests/test_run_log.py::test_escalation_result_accepts_shared_outcomes_and_redacts_unshared_failures` — `created`, `committed-existing`, and `reused` require identity and handoff; `commit-failed` and `interrupted` forbid both.

Every listed test and `uv run pytest tests/ -q -n auto` must be green before this step is complete.

## Acceptance criteria

- A newly published escalation receipt reaches `HEAD` through a commit containing only that receipt before the command returns `created`.

- A matching receipt returns `reused` only when the exact stored bytes match its exact path in `HEAD`.

- A matching local receipt returns `committed-existing` only when its `HEAD` path is absent and its receipt-only commit succeeds.

- Different bytes at an existing `HEAD` receipt path return `collision` and do not overwrite the shared receipt or invoke another commit.

- An explicit external plans directory binds receipt publication and every `HEAD` reader to its containing Git worktree; a directory without one rejects before publication.

- A nonzero or process-launch receipt-commit failure, and an interruption, keep the local receipt recoverable and return no trusted receipt identity or handoff.

- Receipt inspection never renders a local-only receipt as fresh or trusted.

- Impact analysis and structural revision reject a local-only receipt before downstream work begins.

- The shared receipt predicate compares raw bytes at the exact evidence path and fails closed for missing, unreadable, or mismatched `HEAD` content.

- `.gitignore` leaves escalation receipts available for scoped commits and continues to ignore local impact analyses.

- A successful impact-analysis publication performs no Git operation and leaves no untracked impact-analysis file.

- `RoadmapEscalationResult` accepts the three shared success outcomes and excludes identity and handoff from all other outcomes.

## References

- [Git — git-add Documentationhttps: — Verify exact-path staging and ignored-file handling at the receipt boundary.
- [Git — git-commit Documentationhttps: — Verify path-limited commits that preserve unrelated index entries.
- [Git — git-status Documentationhttps: — Check receipt cleanliness and local impact-analysis ignore behavior.
- [Git — gitignore Documentationhttps: — Define the narrowed nested ignore rule.
- [Git — githooks Documentationhttps: — Keep hook rejection visible as a recoverable commit failure.
- [subprocess — Subprocess managementhttps: — Handle Git return codes, captured diagnostics, and interruption correctly.
- [pytest monkeypatch documentationhttps: — Make commit failure and interruption paths deterministic.

## Applicable guardrails

- **The plan’s `## Overview` and step intent** — Grant trusted receipt authority only after exact shared persistence, while preserving unrelated user index and worktree state.

- **The plan’s `## Out of scope`, general commit framework** — Keep Git behavior limited to the exact escalation receipt and step 1’s helper.

- **The plan’s `## Out of scope`, CLI surface** — Use the existing roadmap receipt command and do not add flags or prompts.

- **The plan’s `## Out of scope`, evidence storage** — Keep `plan_tool/roadmap_evidence_store.py` and the immutable evidence representation unchanged.

## Deferred

- General shared-evidence Git admission — Keep the exact-`HEAD` check limited to escalation receipts; broader evidence policy needs separate planning.

- Public operator guidance — Step 3 updates the user-facing roadmap, runbook, capability, and architecture documentation after this lifecycle is implemented.
