> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Human Input Seam Vertical Slice
intent: Prove that a remote operator can answer review-walk prompts through one injectable
  seam and filesystem records while preserving review walk's existing terminal-input
  behavior. The proof deliberately migrates no other human-input or human-availability
  route.
status: completed
priority: medium
risk_profile: standard
risk_profile_rationale: The proof writes no production state except its explicitly
  configured filesystem request and resolution records.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: plan-seeds/archive/human-input-seam.replaced.md
steps:
- id: 1
  title: Add an injectable review-walk human-input seam with an always-ask filesystem
    remote provider
  intent: Give one existing interactive flow a small, explicit path for receiving
    a remote operator response.
  files:
  - TESTING.md
  creates:
  - plan_tool/human_io.py
  - tests/test_human_io.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/human-input-seam/01-injectable-review-walk-human-input-seam.md
  status: done
- id: 2
  title: Route review-walk command and feedback reads through the seam without changing
    terminal behavior
  intent: Prove the remote provider against a real command and free-text feedback
    path while retaining annotation persistence.
  files:
  - plan_tool/review_walk.py
  - tests/test_review_walk.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: provides the typed request, resolution, and remote provider used for both review-walk
      reads
  detail: docs/implementation-plans/plan-details/human-input-seam/02-route-review-walk-command-feedback.md
  status: done
- id: 3
  title: Document the vertical-slice record protocol and retain the wider migration
    as a deferred backlog item
  intent: Make the proof operable without representing its single consumer as repository-wide
    coverage.
  files:
  - BACKLOG.md
  creates:
  - HUMAN_IO_FORMAT.md
  complexity: low
  change_type: non-code
  depends_on:
  - 1
  - 2
  depends_on_notes:
    1: provides the record and configuration behavior the operator document describes
    2: proves that the documented protocol serves one real prompt consumer
  detail: docs/implementation-plans/plan-details/human-input-seam/03-document-vertical-slice-record-protocol.md
  status: done
---
# Human Input Seam Vertical Slice

## Overview

This plan proves a remote human-input seam through one existing consumer:
`review_walk.walk_recommendations`. `PLAN_TOOL_HUMAN_IO=remote` selects a
filesystem provider for that walk; the provider writes a request record and
waits for a matching resolution record. The existing `input_fn` terminal path
remains intact. The proof begins after a caller starts the walk; it does not
make a top-level review command headless. This plan does not claim tool-wide
human-input coverage.

## Problem statement

`review_walk.walk_recommendations` already receives an injectable `input_fn`,
but a headless operator cannot answer its command or feedback reads. A small
remote path through that walk demonstrates that request records, resolution
records, and response parsing can support an actual operator interaction
without committing the repository to a policy for every other prompt. The
callers that decide whether a review walk may start remain unchanged.

## Architecture

### Slice-local seam

Add `plan_tool/human_io.py` with a small injectable callable that accepts a
request with a generated `request_id`, stable `prompt_id`, and prompt text,
then returns the operator's text response. `walk_recommendations` constructs
the callable at its first human read and reuses it for the rest of that walk;
it does not re-read the selected mode for each prompt. Tests may inject a
callable directly.

With no explicit remote mode, the callable delegates to the walk's existing
`input_fn`, preserving its prompts and terminal behavior. With
`PLAN_TOOL_HUMAN_IO=remote`, `PLAN_TOOL_HUMAN_IO_DIR` is required and names the
single directory for both record types. A missing, unreadable, or non-directory
value fails before the walk writes a request. No `absent` provider, per-site
default, advisory event, provider registry, or transport abstraction belongs
to this proof.

### Filesystem records

For each remote prompt, the provider serializes the complete request, then
uses `plan_tool.fileio.durable_create_text` to publish
`<request_id>.request.json` in `PLAN_TOOL_HUMAN_IO_DIR`. The operator writes a
complete resolution to a sibling temporary path and publishes
`<request_id>.resolution.json` with the same no-clobber, complete-before-visible
rule. The provider polls only the final resolution path, so an in-progress
temporary record is not an answer. It requires the same request id and a text
value, and rejects a malformed or mismatched final record. An existing final
request or resolution path is an error; neither publisher overwrites it. The
remote path always waits for an answer rather than applying a default.

### Review-walk integration

Route only the command read and the feedback read in
`review_walk._prompt_for_annotation` through the slice-local seam. Their
prompt ids are `review-walk.annotation` and `review-walk.feedback`.
`input_fn`, `output_fn`, persistence, action dispatch, and annotation semantics
remain unchanged; the seam supplies only the text that those paths already
consume.

## Input

- `HUMAN_IO_FORMAT.md` records the landed filesystem protocol for this
  vertical proof.
- `plan_tool/review_walk.py:walk_recommendations` and
  `_prompt_for_annotation` define the existing terminal and feedback behavior
  that remains intact.
- `BACKLOG.md` #322 holds all remaining prompt and human-availability routes.

## References

- [Built-in Functions — input()https: — defines the terminal-input behavior the default path preserves.
- [pathlib — Object-oriented filesystem pathshttps: — covers exclusive record creation and path validation.
- [json — JSON encoder and decoderhttps: — defines request and resolution serialization.
- [How to monkeypatch/mock modules and environmentshttps: — covers isolated environment and filesystem testing.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Migrating any human-input or human-availability route other than the two
  reads in `review_walk._prompt_for_annotation`; #322 owns that future work.
- The caller-side checks that decide whether a review walk starts.
- `sys.stdin.isatty()` or `_stdin_has_pending_input()` refactors.
- Defaults, advisory events, or policy tables for remote answers.
- HTTP, integration-specific, or pluggable transports.
- Timeouts, multi-reader authorization, or resolution-conflict rules.

## Risks

- A malformed or mismatched resolution can make an operator believe a response
  was accepted when it was not. The provider fails clearly and tests reject
  those records.
- A record collision can overwrite another operator's request. Exclusive
  complete-before-visible publication and an existing-path refusal preserve
  both paths.
- Moving the two reads can change terminal prompt behavior. Existing
  `input_fn`-driven tests remain and cover the same annotation outcomes.

## Testing

- Test remote configuration validation, complete-before-visible request and
  resolution publication, matching resolution parsing, mismatched or malformed
  final-resolution rejection, and preservation of pre-existing request and
  resolution files.
- Test a remote `review_walk` interaction end to end: observe the request,
  write its matching resolution, and confirm the normal annotation or feedback
  outcome persists.
- Retain and run the existing `input_fn` tests for terminal command and
  feedback behavior.

**Per-step test strategy**:

- step 1 — focused unit tests for configuration and record behavior.
- step 2 — focused review-walk regression tests for terminal and remote paths.
- step 3 — manually verify the documented record examples and deferred scope
  match the landed code and backlog state.

## Acceptance criteria

- With `PLAN_TOOL_HUMAN_IO=remote` and a valid `PLAN_TOOL_HUMAN_IO_DIR`, a
  review-walk command and feedback prompt each write a request record and
  resume only after receiving a matching text resolution.
- Missing or invalid remote-directory configuration, malformed records,
  mismatched request ids, and existing request or resolution paths fail without
  overwriting a record.
- Final request and resolution paths become visible only after their complete
  JSON is durable; an in-progress temporary resolution is not accepted as an
  answer.
- With remote mode unset, `walk_recommendations` retains its existing
  `input_fn` prompts, annotation persistence, and feedback behavior.
- The only production consumer changed by this plan is `review_walk`; the
  caller-side start checks and remaining migration are explicitly deferred to
  #322.
- `HUMAN_IO_FORMAT.md` tells an operator how to configure the proof, answer a
  request, and recognize a rejected resolution.

## Deferred

- #322: a future, freshly inventoried migration of remaining prompt and
  human-availability routes, after this proof establishes which policy and
  interface are actually needed.
- Any generalization beyond the filesystem transport after a second real
  consumer demonstrates a concrete need.
