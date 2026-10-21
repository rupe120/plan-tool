> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Headless Review Walk Annotation Entry
intent: When `PLAN_TOOL_HUMAN_IO=remote` is explicitly configured and stdin is not
  a TTY, `reconcile-plan-walk` and its `reconcile-walk` and `review-walk` aliases
  will let a remote operator record only skip or quit for an eligible final saved
  finding. That path will not dispatch an action, request feedback, mutate a plan
  or code, or change ordinary non-TTY and terminal behavior.
status: completed
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: plan-seeds/headless-review-walk-annotation-entry.md
steps:
- id: 1
  title: Let standalone saved-review walks accept remote skip or quit, limit authoritative
    review-state writes to the existing skip sidecar rewrite, and preserve full terminal
    actions
  intent: Give a remote operator a safe annotation path for eligible final saved findings
    without enabling feedback or plan and code actions.
  files:
  - plan_tool/cli/review_cmd.py
  - tests/test_review_walk.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/headless-review-walk-annotation-entry/01-let-standalone-saved-review-walks.md
  status: done
- id: 2
  title: Document both caller-specific restricted remote review entries
  intent: Keep the documented remote caller list, skip-or-quit behavior, and exclusions
    aligned with the implemented command boundaries.
  files:
  - HUMAN_IO_FORMAT.md
  complexity: low
  change_type: non-code
  depends_on:
  - 1
  depends_on_notes:
    1: Defines the standalone saved-review entry and its permitted annotation write.
  detail: docs/implementation-plans/plan-details/headless-review-walk-annotation-entry/02-document-both-caller-specific.md
  status: done
---
# Headless Review Walk Annotation Entry

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
and non-TTY stdin. When a promptable finding reaches the provider, it will
lazily validate `PLAN_TOOL_HUMAN_IO_DIR`; an absent or unusable directory keeps
the provider's existing configuration error. An unset or other mode remains on
the ordinary report-only route. The provider's request and matching resolution
records are permitted protocol traffic; the only review-state mutation this
path permits is the existing skip annotation.

The walk will reuse the established skip-or-quit response policy while keeping
actions unreachable. A remote skip will persist the existing annotation and
continue through later promptable findings under the normal walk selection;
quit and every rejected response will end that walk. Terminal walks retain
their full menu and action builder. Ordinary non-TTY input retains its
report-only path.

## References

- [io — Core tools for working with streamshttps: — Defines isatty() semantics for distinguishing terminal input from pipes and other non-interactive streams.
- [os — Miscellaneous operating system interfaceshttps: — Documents process-environment access needed to gate the restricted path on the exact PLAN_TOOL_HUMAN_IO value.
- [argparse — Parser for command-line options, arguments and subcommandshttps: — Covers subcommand aliases and handler dispatch relevant to preserving all three walk command names.
- [How to monkeypatch/mock modules and environmentshttps: — Explains pytest fixtures for replacing isatty behavior, environment variables, providers, and forbidden callbacks.
- [How to capture stdout/stderr outputhttps: — Documents capsys and related fixtures for verifying report-only warnings and walk output.
- [How to parametrize fixtures and test functionshttps: — Covers parametrized tests for skip, quit, blank, invalid, alias, TTY, and environment-mode cases.

## Steps

See the `steps:` block in the frontmatter.

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
ground the exact environment gate and existing usable provider-directory
prerequisite. It will prove the request/resolution records remain provider
traffic, while a remote request can only skip or quit without action or
feedback: a successful skip continues to each later promptable finding, while
quit or rejected input ends the walk. The direct entry's sidecar eligibility,
ordinary non-TTY report, terminal behavior, and configuration-error behavior
remain unchanged.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — tests covering the behavior this step changes; green before completion.
- step 2 (non-code) — verification appropriate to the artifacts rather than unit tests.

## Acceptance criteria

- Explicit `PLAN_TOOL_HUMAN_IO=remote`, a usable existing
  `PLAN_TOOL_HUMAN_IO_DIR`, and non-TTY stdin start the restricted annotation
  walk for a promptable selected final finding. A missing or unusable directory
  retains the provider's existing configuration error; an unset or other mode
  retains the current non-TTY report-only behavior.
- `s`/`skip` persists only the existing skip annotation and continues through
  later promptable findings. `q`/`quit`, blank, or every other spelling ends
  after that request without an annotation, feedback request, action callback,
  plan edit, or code edit. The request and matching resolution records remain
  permitted provider traffic rather than plan or report mutations.
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
