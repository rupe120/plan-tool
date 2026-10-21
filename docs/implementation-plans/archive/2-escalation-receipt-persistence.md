> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Escalation Receipt Persistence
intent: Make escalation receipts durable as shared evidence while its own Git operations
  leave unrelated user index and worktree state unchanged.
status: completed
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
steps:
- id: 1
  title: Add a single-path receipt commit helper that preserves unrelated staged and
    unstaged changes
  intent: Receipt persistence needs a Git primitive whose own operations affect only
    the receipt path and leave unrelated index entries and worktree paths unchanged.
  files:
  - plan_tool/cli/gitcommit.py
  - tests/cli/test_gitcommit.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/escalation-receipt-persistence/01-single-path-receipt-commit-helper-that.md
  status: done
- id: 2
  title: Complete the receipt-only commit and shared-read lifecycle, retain local
    impact analyses, and remove the stopgap ignore rule
  intent: Only a receipt whose exact stored bytes are in shared Git history grants
    a trusted handoff or downstream work; failure and interruption stay recoverable.
  files:
  - .gitignore
  - DATA_CONTRACT.md
  - ROADMAP_FORMAT.md
  - TESTING.md
  - plan_tool/cli/roadmap_cmd.py
  - plan_tool/roadmap_escalation_run.py
  - plan_tool/roadmap_impact_run.py
  - plan_tool/roadmap_structural_revision.py
  - plan_tool/run_log.py
  - tests/cli/test_roadmap_cmd.py
  - tests/test_roadmap_escalation_run.py
  - tests/test_roadmap_impact_run.py
  - tests/test_roadmap_revision_publish.py
  - tests/test_roadmap_structural_revision.py
  - tests/test_run_log.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: Provides the scoped commit operation the CLI injects into the receipt lifecycle.
  detail: docs/implementation-plans/plan-details/escalation-receipt-persistence/02-complete-receipt-only-commit-shared.md
  status: done
- id: 3
  title: Document the committed receipt path, replace stale receipt no-Git claims,
    and keep impact-analysis no-Git claims unchanged
  intent: Operators and maintainers need accurate guidance about where shared receipts
    live and when receipt creation changes Git state.
  files:
  - CAPABILITIES.md
  - README.md
  - RUNBOOK.md
  - docs/ARCHITECTURE.md
  - docs/how-to/roadmap.md
  - docs/cli/roadmap.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 2
  depends_on_notes:
    2: Establishes the final receipt persistence and outcome behavior the documentation
      describes.
  detail: docs/implementation-plans/plan-details/escalation-receipt-persistence/03-document-committed-receipt-path-replace.md
  status: done
- id: 4
  title: Remove the fixed receipt-persistence backlog records while preserving the
    remaining evidence bugs and risks
  intent: The bug queue and draining arc stop routing work to receipt persistence
    once the fix ships.
  files:
  - BACKLOG.md
  - BUG_BACKLOG.md
  - docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md
  - docs/implementation-plans/backlog-arcs/bug-backlog-draining-arc.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 3
  depends_on_notes:
    3: Confirms the implemented behavior and its public documentation are complete
      before the records are retired.
  detail: docs/implementation-plans/plan-details/escalation-receipt-persistence/04-remove-fixed-receipt-persistence.md
  status: done
---
# Escalation Receipt Persistence

## Overview

Fix the reproduced `BUG_BACKLOG` escalation receipt persistence failure by committing each newly published immutable escalation receipt. The Git worktree that contains `plans_dir` controls both receipt commits and every `HEAD` reader; a plans directory without one rejects receipt publication. A matching receipt left local by an earlier failed or interrupted commit resumes only when its path is absent from that worktree's `HEAD`; different `HEAD` bytes are an immutable collision. Ordinary reuse and every trusted receipt consumer require the exact receipt bytes in `HEAD`. The tool's own Git operations include only the receipt and preserve unrelated staged and unstaged user changes; repository hooks remain external Git policy. Impact analyses remain local no-Git evidence. The work keeps roadmap evidence storage opaque and unchanged and adds no general commit framework or CLI surface.

## Problem statement

Fresh immutable escalation receipts are published but are not reliably persisted as shared commits, causing the reproduced `BUG_BACKLOG` escalation receipt persistence failure and potentially leaving the worktree dirty. The stopgap evidence ignore rule cannot be removed until receipt commits are scoped so unrelated user changes are never staged.

## Architecture

The Git worktree that contains the roadmap plans controls both publication and receipt admission, including an explicit external `--plans-dir`; no controlling Git worktree rejects before publication. After fresh immutable publication, the receipt lifecycle stages and commits only its exact path. The helper's own operations preserve every unrelated staged entry and every unrelated unstaged path; on a noncommitted Git failure, including process launch failure, it unwinds only the receipt staging it introduced. Replacing the broad stopgap ignore releases only escalation receipts for this behavior and preserves the impact-analysis namespace's local no-Git behavior.

A successful fresh receipt reports `created`; a matching receipt already at its exact path with byte-identical `HEAD` content reports `reused`. A matching local receipt whose exact `HEAD` path is absent resumes only its own commit and reports the distinct successful `committed-existing` outcome. Different bytes at an existing `HEAD` path report `collision` and do not commit or overwrite shared evidence. Commit failure reports `commit-failed` with the evidence retained locally, and an interruption reports `interrupted` without reset or deletion; a later matching request determines whether the retained receipt is committed or may resume. Receipt inspection cannot expose a non-`HEAD` receipt as a trusted current handoff, and impact analysis and structural revision admit only byte-identical `HEAD` receipts; the receipt creation/recovery route is the sole local-receipt consumer. The tool's own staging and cleanup operations never alter unrelated state; repository hook effects remain external Git policy. Invalid-existing-receipt paths do not commit. The result, telemetry, exit, and documentation contracts carry these distinctions. Roadmap evidence storage remains opaque and unchanged.

## References

- [Git - git-add Documentationhttps: — Defines exact-path staging, pathspec handling, ignored-file behavior, and the distinction from git add -A.
- [Git - git-commit Documentationhttps: — Documents path-limited commits that exclude changes already staged for unrelated paths.
- [Git - git-status Documentationhttps: — Specifies stable porcelain output for verifying receipt cleanliness while preserving unrelated worktree changes.
- [Git - gitignore Documentationhttps: — Defines anchored, nested, and double-asterisk ignore patterns relevant to removing the evidence stopgap safely.
- [Git - githooks Documentationhttps: — Explains commit-hook execution and how nonzero pre-commit or commit-msg hooks abort receipt commits.
- [subprocess — Subprocess management — Python 3.13 documentationhttps: — Covers invoking Git, capturing return codes and stderr, and handling process-launch and nonzero-exit failures.
- [How to monkeypatch/mock modules and environments — pytest documentationhttps: — Shows how to replace subprocess boundaries to test commit failure and interruption deterministically.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- A general commit framework — this fix remains limited to escalation receipt persistence.
- A new CLI surface — the behavior uses the existing interface.
- Changes to roadmap evidence storage — its representation remains opaque and unchanged.

## Risks

- Commit failure — a nonzero Git result or process launch failure reports `commit-failed`, retains the receipt locally, and unwinds only helper-owned receipt staging when staging occurred.
- Interruption — report `interrupted` without reset or deletion; a later matching request checks whether the receipt is already in `HEAD` before deciding to reuse or resume it.
- Accidental staging of unrelated user changes — the tool's own staging, commit, and cleanup operations preserve pre-existing staged entries and unstaged paths separately while handling only the receipt; repository hooks remain external Git policy.
- Immutable-byte conflict — different bytes at an existing `HEAD` receipt path report `collision` and do not overwrite shared evidence.
- Unshared receipt use — receipt inspection, analysis, and structural revision deny trusted or downstream use until the exact receipt is in `HEAD`.
- Impact-analysis dirt — retain its namespace's local no-Git rule while releasing escalation receipts for scoped commits.
- Git-root mismatch — bind creation and every `HEAD` reader to the Git worktree containing `plans_dir`; a plans directory without one refuses receipt publication.

## Testing

The smallest proof covers separate unrelated staged and unstaged changes under the tool's own operations, fresh receipt creation, byte-identical reuse from `HEAD`, a same-final byte conflict, nonzero and process-launch commit failure followed by recovery only when `HEAD` lacks the path, and interruption. It proves that an uncommitted receipt grants neither a trusted inspection handoff nor impact analysis or structural revision, that an explicit external plans directory uses its own Git worktree, and that impact-analysis publication remains local and clean.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — tests covering the behavior this step changes; green before completion.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.
- step 3 (non-code) — verification appropriate to the artifacts rather than unit tests.
- step 4 (non-code) — verification appropriate to the artifacts rather than unit tests.

## Acceptance criteria

- After a fresh immutable escalation receipt is published, only that receipt is staged and committed.
- Receipt persistence's own Git operations leave every pre-existing unrelated staged entry and every unrelated unstaged path unchanged; repository hook effects remain external Git policy.
- Successful receipt persistence does not leave the receipt as an uncommitted worktree change.
- A matching receipt reports ordinary `reused` only when its exact bytes are already at its path in `HEAD`; a matching local receipt resumes its receipt-only commit only when that `HEAD` path is absent and reports `committed-existing`.
- Different bytes at an existing `HEAD` receipt path report `collision` without overwriting shared evidence.
- An explicit external plans directory uses the Git worktree that contains it for receipt commit and `HEAD` admission; a plans directory with no controlling Git worktree rejects before publication.
- Receipt inspection, impact analysis, and structural revision do not grant a trusted handoff or downstream work from a non-`HEAD` receipt; only receipt recovery can use the matching local bytes.
- The stopgap evidence ignore rule is removed only when scoped receipt commits are in place.
- Impact-analysis publication remains local no-Git evidence and does not create a dirty worktree after the escalation-receipt ignore change.
- A nonzero Git result or process-launch failure reports `commit-failed`, and interruption reports `interrupted`; neither is reported as ordinary reuse.
- Roadmap evidence storage remains opaque and unchanged.
- The committed per-roadmap evidence path is documented.
- Proof covers fresh creation, byte-identical `HEAD` reuse, missing-`HEAD` recovery, same-final byte conflict, nonzero and process-launch commit failure, interruption, external-plans Git-root binding, separate staged and unstaged unrelated changes under tool operations, shared-read admission, and local impact-analysis publication.

## Deferred

- None — implementation does not intentionally postpone any in-scope work.
