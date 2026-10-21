> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-incremental-revision.md`.
> Preserved here for history; do not edit.

## Overview

`plan-tool roadmap` adds an explicit, feedback-targeted revision mode that turns selected stable feedback row ids into small, schema-checked patches for only the affected roadmap collections. It preserves every non-targeted canonical row and reviewer-owned review state, validates affected artifacts and relations, and publishes the complete revision atomically. The initial four-stage roadmap creation path and broad `--from-stage` re-entry remain available, while incremental revision becomes the preferred path after feedback exists.

## Problem statement

Responding to routine roadmap feedback currently requires a backend to re-emit an entire stage or every later roadmap artifact through `--from-stage`. That broad rewrite exposes unrelated artifact prose and feedback, can rewrite unaffected later stages, and relies on prompt instructions rather than a deterministic fence to protect `awaiting-review` content. The targeted mode limits backend judgment and writes to the explicitly selected feedback and the collections that genuinely depend on it.

## Architecture

Treat the canonical roadmap files as the source of truth and each revision as a transaction over named artifact collections rather than a text replacement. The revision planner deterministically validates stable feedback row ids, rejects unknown, duplicate, incompatible, or reviewer-closed selections before a backend call, and derives the minimal affected collections and their dependency order from canonical row ids and declared relations.

Each affected collection receives a bounded patch request containing the selected feedback, target collection, immutable dependency summary, stable identifiers, and only the context needed for that patch. The backend supplies constrained semantic edits through a closed operation set whose exact vocabulary `create` defines; it never chooses rows or widens scope. Unsupported operations and edits outside the session allowlist are gate failures.

The deterministic merger is the sole writer of canonical artifacts. It preserves non-targeted rows, IDs, settled decisions, removals, feedback outside the selected rows, and protected `awaiting-review` content. A small extraction from `roadmap.py`'s existing per-stage gate-evaluation loop and `_write_artifact` gives the full-stage and targeted paths one shared artifact validation and publish boundary without moving the artifact schema, gate definitions, or review views.

Downstream collections receive separate bounded patch requests only after upstream patches validate. Publication is atomic at the revision-session boundary: the complete gate-valid collection set replaces the current state, or no canonical artifact changes. On success, the revision creates a small Git checkpoint and marks derived drafts for the affected plan IDs stale in the roadmap's seed-state sidecar, changing status only and never draft prose.

The command surface must distinguish targeted revision from broad `--from-stage` re-entry. Selection is explicit and machine-checkable, the exact write set is reported before backend invocation, no unselected artifact becomes writable, and read-only views continue to render the on-disk canonical artifacts, including a review view showing selected rows and the session outcome. The plan may choose the final flag or subcommand spelling, but it may not provide a generic mode that silently expands to every open feedback row.

Each session records selected feedback, affected collections, input/output digests, proposed artifact changes, validation results, deliberately deferred downstream work, context size, and selected collection counts.

## Out of scope

- Replacing the four canonical roadmap artifacts, their existing gate model, or their role as the canonical design record.
- Changing the reviewer-owned feedback lifecycle, auto-accepting proposed responses, or using an AWS/IAM/SCM identity as an application-reviewer role.
- Generating, promoting, overwriting, or refreshing roadmap-derived plan seeds; that belongs to `roadmap-seed-materialization.md`, which lands first.
- Building a general-purpose YAML diff engine, arbitrary human text editing through the CLI, collaborative real-time editing, or a new external persistence service.
- Rewriting the full `--from-stage` path merely to share abstractions unless a named ownership boundary makes that necessary.
- Treating model agreement, prose quality, document length, or token count as correctness gates; correctness is whether a patch stays within its declared allowlist and the resulting canonical artifacts satisfy their existing shape and relation gates.
- Adding arbitrary document editing, review workflow redesign, seed regeneration, or new persistence infrastructure to this effort.

## Risks

- **Publication-blocking:** A parse failure, fence violation, exhausted retry, interrupt, or incomplete downstream patch could leave a partial revision. Mitigation: preserve the pre-session canonical artifacts and derived seeds unless the complete affected collection set passes validation.
- **Publication-blocking:** A backend could patch an unselected row or collection, replace a whole document, alter a settled decision, or change protected `awaiting-review` content. Mitigation: use a closed patch-operation set, an explicit allowlist, and deterministic merger fences before gate evaluation.
- **Schema decision required:** An existing roadmap relation might not be expressible as a bounded collection dependency. Stop and surface that schema decision instead of silently falling back to a full-artifact rewrite.
- **Drift risk:** Duplicating the existing artifact validation and publish rule for the targeted path could diverge from the full-stage path. Mitigation: extract only the shared deterministic boundary from `roadmap.py`'s per-stage gate-evaluation loop and `_write_artifact`.

## Testing

Use unit tests for selection validation, impact calculation, dependency ordering, patch parsing, allowlist enforcement, deterministic merging, context-bound reporting, and atomic session behavior. Cover empty, unknown, and duplicate selections; incompatible feedback; attempts to patch an unselected row, replace an entire document, invent a feedback/removal row, alter a settled decision, or alter unselected `awaiting-review` content; retry and interrupt recovery; parse and gate rejection; and Git-clean failure paths without a live backend.

Use integration coverage only for cross-module behavior that unit tests cannot establish: a selected feedback row produces backend requests and a write set limited to its owning and genuinely dependent collections; valid multi-collection revisions publish together through the existing artifact parsers and cross-stage gates; any failure preserves prior files byte-for-byte; and the initial full roadmap path, `--from-stage`, seed promotion/refresh, and all read-only views retain their documented behavior.

## Acceptance criteria

- A selected single feedback row produces requests bounded to its owning and genuinely dependent collections; an unrelated row and its prose never enter the backend input or output write set.
- Unknown, duplicate, incompatible, reviewer-closed, and empty selections are rejected before a backend call.
- Operations outside the closed supported set and changes outside the session's allowlisted collections fail rather than becoming silent no-ops.
- Attempts to patch an unselected row, replace an entire document, invent a feedback/removal row, alter a settled decision, or alter unselected `awaiting-review` content fail before publication.
- The merger preserves non-targeted rows, IDs, settled decisions, removals, and feedback outside the selected rows.
- Valid multi-collection revisions publish together and pass the existing artifact parsers and cross-stage gates; a failure at any point preserves the prior files byte-for-byte and leaves derived seeds untouched.
- The targeted mode reports its exact write set before invoking a backend and makes no unselected artifact writable.
- A successful session records selected feedback, affected collections, input/output digests, proposed changes, validation results, deliberately deferred downstream work, context size, and selected collection counts, and creates a small Git checkpoint.
- Successful publication marks only the derived drafts for affected plan IDs stale in the roadmap's seed-state sidecar and does not change draft prose.
- The initial full roadmap path, `--from-stage`, seed promotion/refresh, and all read-only views retain their documented behavior.

## Deferred

- The targeted materializer mechanics remain assigned to `roadmap-seed-materialization.md`; this plan supplies only the per-plan-id staleness signal that it consumes.
- Any downstream work deliberately deferred by a revision remains recorded in the reviewable session record rather than being silently expanded into the current session.
- File discoveries outside the Outcome go to `BACKLOG.md` or `BUG_BACKLOG.md` with the supporting session evidence.

## Input

The revision consumes the four canonical roadmap artifacts as the source of truth, including stable feedback row ids, owning stages, target collections, declared relations, existing artifact parsers, cross-stage gates, reviewer-owned feedback state, settled decisions, removals, and `awaiting-review` state. It also writes per-plan-id staleness status to the roadmap's seed-state sidecar for consumption by `roadmap-seed-materialization.md`, without generating or refreshing draft prose. Existing `--from-stage` remains the broad authoring-stage re-entry contract, and read-only views continue to render the on-disk canonical artifacts.
