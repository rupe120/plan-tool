> **Auto-archived**: this plan was swept on 2026-08-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Reconcile Plan Walk Checkpoint Role
intent: '`reconcile-plan-walk` can walk the newest eligible saved artifact, or an
  eligible exact `--id`, without ever applying findings from a pre-apply audit checkpoint
  or an artifact whose checkpoint role is unknown. Source: `BUG_BACKLOG.md` RISK,
  `reconcile-plan-walk` can walk a partial checkpoint. Remove that entry only after
  the shipped behavior and its verification are complete.'
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Select only final saved reviews for direct walks
  intent: Prevents reconcile-plan-walk from applying findings from checkpoints or
    sidecars with an unknown role.
  files:
  - plan_tool/cli/review_cmd.py
  - tests/cli/test_review_cmds.py
  - tests/test_review_walk.py
  - tests/test_review_persistence.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/reconcile-plan-walk-checkpoint-role/01-select-only-final-saved-reviews-direct.md
  status: done
- id: 2
  title: Document safe saved review selection and close the risk
  intent: Tells operators which saved reviews direct walks can use and records that
    generic recovery readers still accept checkpoints.
  files:
  - BUG_BACKLOG.md
  - docs/AUDIT_FLOW.md
  - docs/cli/README.md
  - docs/cli/reconcile-plan-walk.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/reconcile-plan-walk-checkpoint-role/02-document-safe-saved-review-selection.md
  status: done
---
# Reconcile Plan Walk Checkpoint Role

## Overview

Saved reviews carry a persisted three-state checkpoint role. The plan-wide
`reconcile-plan` reuse prompt already validates its loaded payload, but the
standalone walk still resolves the newest filename and applies it without that
gate. An interrupted completeness audit can therefore make its partial
checkpoint the next artifact the direct walk applies.

## Problem statement

Recency and an exact filename locate a sidecar but do not prove it is a final
review. The direct walk needs its own loaded-payload eligibility decision while
keeping recovery-oriented readers capable of accessing checkpoint evidence.

## Architecture

Separate locating from walk eligibility. Preserve the shared raw resolver for
callers that need every artifact, including checkpoints. At the direct-walk
boundary, decide eligibility from the loaded role only: `False` is an
ordinary final and is walkable; `True` is a pre-apply checkpoint and is never
walkable; `None` is unknown and is never walkable. Kind is intentionally not
an eligibility discriminator in this command. Selection keeps the existing
newest-first ordering, but the first eligible loaded payload wins. A pin is
never widened into fallback selection. A direct-walk `--id` is only one unique
report basename or stem from the resolved plan's reports directory; it is
compared against that directory's listed candidates and never passed unchecked
to the shared raw resolver. Every direct candidate must also resolve within
that reports directory, so a listed symlink cannot redirect a walk to another
plan. A path-bearing, missing, ambiguous, out-of-directory, unreadable,
checkpoint, or unknown-role pin reports its specific refusal, exits `2`, and
makes no annotation or plan mutation. If an unpinned scan exhausts every
candidate, including because candidates fail the resolved-directory boundary,
the command reports that no eligible saved review is available, exits `2`, and
makes no annotation or plan mutation.

## References

- [argparse — Python Standard Library](https://docs.python.org/3/library/argparse.html) — Defines subcommand arguments, help text, and CLI exit behavior needed for the exact --id selection contract.
- [pathlib — Python Standard Library](https://docs.python.org/3/library/pathlib.html) — Covers scanning, sorting, status checks, and read failures for newest-first saved-artifact selection.
- [json — Python Standard Library](https://docs.python.org/3/library/json.html) — Documents JSON loading and JSONDecodeError handling for skipping unreadable or malformed saved sidecars.
- [pytest monkeypatch guide](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Explains isolated replacement of filesystem or resolver behavior for regression tests of rejected and fallback-free selections.
- [pytest API reference](https://docs.pytest.org/en/stable/reference/reference.html) — Documents tmp_path fixtures for constructing isolated saved-review artifacts and checkpoint scenarios in tests.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Changing `reconcile-plan` prompt reuse, which already has its own
  `kind="review"` and ordinary-final eligibility policy.
- Changing checkpoint writing, schema versions, role normalization, or legacy
  role interpretation.
- Changing checkpoint crash recovery, `resolve_saved_review`,
  `completeness-apply`, data-contract application, or any other consumer's
  ability to load a pinned checkpoint.
- Adding freshness checks, a fresh-audit fallback, new flags, filename
  migrations, cleanup, pruning, or heuristic reclassification of artifacts.
- Narrowing the direct walk by sidecar kind or redesigning recommendation
  application semantics.

## Risks

The same resolver serves recovery readers; filtering it globally would make a
checkpoint unrecoverable. An unpinned scanner must not let one unreadable,
ineligible, or foreign-target symlink artifact block an older ordinary final,
while an exact pin must not silently substitute an older artifact, choose an
ambiguous basename/stem collision, or leave the selected plan's reports
directory. Existing legacy unmarked v1/v2 finals remain walkable through their
normalized `False` role.

## Testing

Prove the direct command walks the newest ordinary-final artifact after newer
unreadable, marked-checkpoint, and unknown-role sidecars; ordinary finals of
multiple kinds stay eligible. Prove each rejected exact-pin state is terminal
and does not fall back or write annotations, including a path-bearing pin that
would otherwise name another plan's ordinary-final sidecar. Prove every
rejected pin prints its state-specific reason and exits `2`; an ambiguous
basename/stem collision and a listed symlink that resolves to another plan are
both refused. An exhausted unpinned scan does the same with its no-eligible
result. Preserve a regression that the generic resolver can still return a
checkpoint for recovery consumers. Exercise interactive and non-interactive
direct-walk outcomes as applicable, then run the focused persistence and walk
suites plus generated CLI-reference drift checks if command help changes.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — tests covering the behavior this step changes; green before completion.
- step 2 (non-code) — verification appropriate to the artifacts rather than unit tests.

## Acceptance criteria

- A marked pre-apply checkpoint is never walked by `reconcile-plan-walk`,
  whether newest or supplied through `--id`.
- An unknown-role sidecar is never walked.
- The unpinned direct walk selects the newest loaded ordinary-final sidecar
  regardless of its supported kind, after skipping newer unusable candidates.
- A rejected or missing exact pin never falls back to another saved artifact
  and makes no annotation or plan mutation; every rejected-pin state reports
  its reason and exits `2`.
- A direct-walk pin containing a path component cannot select a sidecar outside
  the resolved plan's reports directory, even if that sidecar is an
  ordinary-final artifact.
- A listed sidecar that resolves outside the selected reports directory, and an
  `--id` that matches more than one listed basename/stem, are refused without
  walking or mutation.
- An unpinned scan with no eligible saved artifact reports that outcome, exits
  `2`, and makes no annotation or plan mutation.
- Recovery-oriented lookup still resolves a checkpoint, and legacy unmarked
  final sidecars retain their existing direct-walk eligibility.
- The backlog record and direct-walk documentation accurately state the
  completed boundary, with no claim that generic recovery readers reject
  checkpoints.

## Deferred

Future changes to any other saved-artifact consumer require their own reader
contract. This plan only closes the direct `reconcile-plan-walk` RISK.
