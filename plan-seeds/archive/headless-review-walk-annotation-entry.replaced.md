> **Replaced**: this file has been superseded by `docs/implementation-plans/2-headless-review-walk-annotation-entry.md`.
> Preserved here for history; do not edit.

# Headless standalone saved-review annotation entry

## Outcome

When `PLAN_TOOL_HUMAN_IO=remote` is explicitly configured and stdin is not a
TTY, `reconcile-plan-walk` and its `reconcile-walk` and `review-walk` aliases
will let a remote operator record only skip or quit for an eligible final saved
finding. That path will not dispatch an action, request feedback, mutate a
plan or code, or change ordinary non-TTY and terminal behavior.

## In scope

This seed covers only the standalone `cmd_review_walk` entry in
`plan_tool.cli.review_cmd`, its three aliases, the existing closed
`WalkResponsePolicy.SKIP_OR_QUIT` use at that entry, focused walk/CLI coverage,
and the human-input reference if its caller list changes. It derives from
BACKLOG #322 and the current-code inventory at
`docs/implementation-plans/backlog-arcs/analysis/headless-process-route-inventory.md`.

## Allowed behavior changes

The exact `remote` plus non-TTY environment will become an opt-in restricted
walk for the direct command's existing eligible final saved sidecars. `s` and
`skip` may persist the existing skip annotation; `q`, `quit`, blank, and every
other response will end after the one annotation request without an
annotation. The direct entry's current sidecar selection, including `--id`,
`--rewalk`, and its current-qualified completeness eligibility, remains
authoritative.

## Allowed reorganization

None. The existing provider and response policy are sufficient for the
selected contract.

## Overview

This is the next isolated headless-process proof after the completed
`cmd_review` entry. It adds a caller-specific remote annotation path to the
separate direct walk instead of declaring every `walk_recommendations` caller
headless-capable.

## Problem statement

`cmd_review_walk` currently reports final saved findings and returns when
stdin is non-TTY. Its terminal path can apply, run, give feedback, or invoke
structural actions, so opening that path without a closed response set would
weaken the caller's mutation boundary.

## Architecture

The direct entry will admit the restricted walk only for explicit remote mode
with non-TTY stdin. It will reuse the established filesystem provider and
skip-or-quit response policy, while keeping actions unreachable from that
path. Terminal walks retain their full menu and action builder. Ordinary
non-TTY input retains its report-only path.

## Out of scope

- `cmd_review`, its completed proof, inline reconciliation, `run --reconcile`,
  and every other `walk_recommendations` caller.
- Remote feedback, apply/run/apply-all, structural remedies, terminal
  confirmation, default-policy changes, cancellation, transport changes, and
  a general TTY abstraction.
- Response-record retention or cleanup. #322 will select a lifecycle owner
  only when a route requires one.
- Completeness, data-contract, gate, authoring, configuration, destructive,
  collision, and rate-limit routes identified by the inventory.

## Risks

- A loose environment gate could turn ordinary non-TTY execution into a
  remote walk. The gate must require the exact existing remote mode and leave
  invalid or unset mode on the current report-only route.
- An action callback or feedback prompt could make a remote annotation mutate
  an authoritative artifact. The restricted path must not construct or reach
  them.
- The direct command is kind-agnostic. Its existing final-sidecar eligibility
  must remain the selector; remote skip is not an apply or completion result.

## Testing

The bare-plan audit will judge only the caller-specific remote annotation
property and defer transport, lifecycle, and peer-route policy. Detail will
ground the exact environment gate and prove a remote request can only skip or
quit without action or feedback, while the direct entry's sidecar eligibility,
ordinary non-TTY report, and terminal behavior remain unchanged.

## Acceptance criteria

- Explicit `PLAN_TOOL_HUMAN_IO=remote` plus non-TTY stdin reaches one
  restricted annotation request for a promptable selected final finding;
  unset or invalid mode retains the current non-TTY report-only behavior.
- `s`/`skip` persists only the existing skip annotation, and `q`/`quit`, blank,
  or every other spelling ends after that request without an annotation,
  feedback request, action callback, plan edit, or code edit.
- The direct command keeps its existing final-sidecar selection and
  current-qualified completeness gate, `--id`, `--rewalk`, info selection,
  ordinary non-TTY reporting, and full terminal walk behavior.
- The human-input reference names both caller-specific restricted entries and
  continues to exclude all other direct-input and availability routes.
- Before completion, sweep `cmd_review_walk`, its three aliases,
  `WalkResponsePolicy.SKIP_OR_QUIT`, direct-sidecar eligibility,
  `PLAN_TOOL_HUMAN_IO`, and `walk_recommendations`, plus the vocabulary
  `remote`, `non-TTY`, `terminal`, `skip`, `quit`, `action`, `feedback`,
  `headless`, `annotation`, `completeness`, and `lifecycle`. Keep each site
  only when it serves this caller-specific property.

## Deferred

Any route that needs remote feedback, a response able to mutate an
authoritative artifact, a new absent-mode default, or record cleanup remains
with #322 until its own caller, operator consequence, and record owner are
selected.
