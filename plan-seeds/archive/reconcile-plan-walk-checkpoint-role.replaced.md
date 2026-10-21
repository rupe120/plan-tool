> **Replaced**: this file has been superseded by `docs/implementation-plans/2-reconcile-plan-walk-checkpoint-role.md`.
> Preserved here for history; do not edit.

# Safe direct reconcile-plan walk selection

## Outcome

`reconcile-plan-walk` can walk the newest eligible saved artifact, or an
eligible exact `--id`, without ever applying findings from a pre-apply audit
checkpoint or an artifact whose checkpoint role is unknown.

Source: `BUG_BACKLOG.md` RISK, `reconcile-plan-walk` can walk a partial
checkpoint. Remove that entry only after the shipped behavior and its
verification are complete.

## In scope

Define a direct-walk selection contract at the `reconcile-plan-walk` boundary.
It remains kind-agnostic for ordinary-final saved reviews: unpinned selection
loads candidates newest-first, skips unreadable, marked-checkpoint, and
unknown-role artifacts, then walks the newest ordinary-final artifact of any
kind. An exact `--id` selects only that one artifact; a missing, unreadable,
marked-checkpoint, or unknown-role pin explains why it cannot be walked and
exits without selecting another artifact. A no-eligible-candidate result also
exits without walking or mutating annotations. Operator-facing guidance must
distinguish a pre-apply checkpoint from a malformed or unknown role.

The generic persistence resolver stays role-agnostic so checkpoint-recovery
and other consumers can still locate and read a checkpoint. The direct-walk
selector, CLI behavior, regression coverage, command documentation, and the
source backlog/handoff closure belong to this effort.

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
never widened into fallback selection.

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
checkpoint unrecoverable. An unpinned scanner must not let one unreadable or
ineligible newest artifact block an older ordinary final, while an exact pin
must not silently substitute an older artifact. Existing legacy unmarked v1/v2
finals remain walkable through their normalized `False` role.

## Testing

Prove the direct command walks the newest ordinary-final artifact after newer
unreadable, marked-checkpoint, and unknown-role sidecars; ordinary finals of
multiple kinds stay eligible. Prove each rejected exact-pin state is terminal
and does not fall back or write annotations. Preserve a regression that the
generic resolver can still return a checkpoint for recovery consumers. Exercise
interactive and non-interactive direct-walk outcomes as applicable, then run
the focused persistence and walk suites plus generated CLI-reference drift
checks if command help changes.

## Acceptance criteria

- A marked pre-apply checkpoint is never walked by `reconcile-plan-walk`,
  whether newest or supplied through `--id`.
- An unknown-role sidecar is never walked.
- The unpinned direct walk selects the newest loaded ordinary-final sidecar
  regardless of its supported kind, after skipping newer unusable candidates.
- A rejected or missing exact pin never falls back to another saved artifact
  and makes no annotation or plan mutation.
- Recovery-oriented lookup still resolves a checkpoint, and legacy unmarked
  final sidecars retain their existing direct-walk eligibility.
- The backlog record and direct-walk documentation accurately state the
  completed boundary, with no claim that generic recovery readers reject
  checkpoints.

## Deferred

Future changes to any other saved-artifact consumer require their own reader
contract. This plan only closes the direct `reconcile-plan-walk` RISK.
