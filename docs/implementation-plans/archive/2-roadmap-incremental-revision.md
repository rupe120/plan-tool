> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Roadmap Incremental Revision
intent: '`plan-tool roadmap --revise-feedback <artifact>:<feedback-id>` will resolve
  one selected, same-artifact feedback row into a bounded update of its live target
  row and one proposed feedback response. It will preserve every other canonical row,
  relation, prose byte, and feedback row; it will conservatively invalidate existing
  seed state before backend work so a failed attempt can require regeneration. The
  local path makes no crash, power-loss, or recovery promise.'
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Define the same-artifact live-feedback selector, render-canonical preflight,
    closed text-field table, and two-operation revision schema
  intent: Gives selection, lossless-input preflight, prompts, parsing, and merging
    one closed contract that cannot turn a routine feedback reply into a cross-artifact,
    structural, or opaque-data-losing revision.
  files:
  - ROADMAP_FORMAT.md
  - tests/test_roadmap_format.py
  creates:
  - plan_tool/roadmap_revision.py
  - tests/test_roadmap_revision.py
  allowed_mentions:
  - plan_tool/roadmap_revision_patch.py
  - plan_tool/roadmap_revision_publish.py
  - plan_tool/roadmap_revision_run.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/roadmap-incremental-revision/01-define-same-artifact-live-feedback.md
  status: done
- id: 2
  title: Parse and merge one single-field target-row replacement and one feedback
    response
  intent: Enforces the selector-owned row and feedback identities while preserving
    every non-selected canonical structure and all artifact prose unchanged.
  files:
  - plan_tool/roadmap_artifacts.py
  - tests/test_roadmap_artifacts.py
  creates:
  - plan_tool/roadmap_revision_patch.py
  - tests/test_roadmap_revision_patch.py
  allowed_mentions:
  - plan_tool/roadmap_gates.py
  - plan_tool/roadmap_revision.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: supplies the selector, row-field, and operation contracts the parser enforces
  detail: docs/implementation-plans/plan-details/roadmap-incremental-revision/02-parse-merge-one-single-field-target-row.md
  status: done
- id: 3
  title: Serialize roadmap and seed-state writers, pre-invalidate seed state, and
    atomically publish one gate-valid artifact candidate
  intent: Prevents a participating writer from materializing or overwriting a mutable
    baseline, while making failed attempts conservatively invalidate rather than falsely
    refresh drafts.
  files:
  - plan_tool/roadmap.py
  - tests/test_roadmap.py
  - plan_tool/roadmap_seed_state.py
  - tests/test_roadmap_seed_state.py
  - plan_tool/cli/roadmap_cmd.py
  - tests/cli/test_roadmap_cmd.py
  - plan_tool/cli/authoring.py
  creates:
  - plan_tool/roadmap_revision_publish.py
  - tests/test_roadmap_revision_publish.py
  allowed_mentions:
  - plan_tool/roadmap_revision_run.py
  complexity: high
  change_type: feature
  depends_on:
  - 2
  depends_on_notes:
    2: supplies the fully merged one-artifact candidate and its deterministic validation
      input
  detail: docs/implementation-plans/plan-details/roadmap-incremental-revision/03-serialize-roadmap-seed-state-writers.md
  status: done
- id: 4
  title: Expose one exclusive --revise-feedback command with one physical backend
    request and machine-checkable event evidence
  intent: Gives operators one exclusive, machine-checkable local revision entry point
    without hiding a retry, structural, or cross-artifact expansion behind a backend
    call.
  files:
  - plan_tool/cli/roadmap_cmd.py
  - plan_tool/run_log.py
  - tests/cli/test_roadmap_cmd.py
  - tests/test_run_log.py
  - DATA_CONTRACT.md
  - TESTING.md
  creates:
  - plan_tool/roadmap_revision_run.py
  - plan_tool/prompts/roadmap-feedback-revision.md
  - tests/test_roadmap_revision_run.py
  allowed_mentions:
  - plan_tool/roadmap_revision.py
  - plan_tool/roadmap_revision_patch.py
  - plan_tool/roadmap_revision_publish.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  - 2
  - 3
  depends_on_notes:
    1: supplies the preflight selection contract and context fence
    2: supplies the two-operation response contract
    3: supplies writer serialization, conservative invalidation, and publication
  detail: docs/implementation-plans/plan-details/roadmap-incremental-revision/04-expose-one-exclusive-revise-feedback.md
  status: done
- id: 5
  title: Document local feedback revision and the explicit broad-reentry boundaries
  intent: Makes clear that routine same-artifact feedback uses the bounded mode while
    structural, cross-artifact, prose, and recovery workflows remain on existing surfaces.
  files:
  - ROADMAP_FORMAT.md
  - README.md
  - docs/cli/roadmap.md
  - docs/ARCHITECTURE.md
  - docs/ROADMAP_WALKTHROUGH.md
  - CAPABILITIES.md
  - tests/test_roadmap_format.py
  complexity: medium
  change_type: non-code
  depends_on:
  - 4
  depends_on_notes:
    4: settles the command spelling, preflight outcomes, and attempt output
  detail: docs/implementation-plans/plan-details/roadmap-incremental-revision/05-document-local-feedback-revision.md
  status: done
---
# Roadmap Incremental Revision

## Overview

`plan-tool roadmap` adds one feedback-targeted revision mode for routine local updates. It accepts exactly one artifact-qualified feedback selector only when that artifact already round-trips byte-for-byte through its current parser and renderer, updates at most one explicitly allowed text field on the selected live target row, writes one proposed response to that feedback row, and atomically replaces only that artifact after its existing parser and gates pass. It preserves every other row, relationship, prose byte, feedback state, and accepted serialized data. Structural, cross-artifact, prose, and full-stage changes remain explicit broad `--from-stage` work.

## Problem statement

Routine feedback currently requires broad `--from-stage` re-entry, which re-emits a whole stage or its later artifacts and may repeat full-artifact retries even when one existing row needs a small textual correction. Existing gates already preserve carried `awaiting-review` feedback. The local mode makes exactly one bounded backend attempt, rather than adopting the broad path's retry loop; it does not replace those gates or change the existing broad path's publication and recovery behavior.

## Architecture

Step 1 owns the selector, render-canonical preflight, closed presentation-field policy, and bounded prompt input. It permits only one eligible same-artifact feedback row and live target row, while checking every retained feedback row against the broad validity rules. Rejection happens before seed invalidation or backend work whenever the local mode cannot preserve the selected artifact exactly.

Step 2 owns the strict two-operation reply contract and deterministic merge. The only local changes are one allowed presentation field on the selected target row, when requested, and the selected feedback row's proposed response and `awaiting-review` state. Every other row, relation, feedback row, removal, identifier, and prose body remains unchanged.

Step 3 owns participating-writer serialization, conservative seed-state invalidation, candidate validation, and single-artifact publication. The local runner becomes a participating writer: it acquires the same guard before its first artifact or seed-state read and keeps the token through publication. The sidecar's temporary file is flushed and `fsync`ed before its atomic replacement and backend work. This is the decided pre-backend write seam, not a destination-directory, whole-publication power-loss, or recovery guarantee. A gate-valid candidate replaces only its selected artifact; all other outcomes leave canonical artifacts unchanged.

Step 4 owns the exclusive local command, one physical backend request with no recovery retry, and machine-checkable run-log evidence. Its events record phase progress and terminal outcomes without reviewer, artifact, prompt, or backend text. Step 5 documents the local route and the existing broad re-entry boundaries.

## Input

The local mode consumes one render-canonical artifact, its selected feedback and target row, the current feedback lifecycle, and seed-state sidecar. Its backend context excludes sibling artifacts, rows, feedback, roadmap prose, draft seed prose, an external plans-directory contract, and a Git worktree requirement. Candidate validation can use normal read-only upstream artifacts but never a same-artifact predecessor. Broad `--from-stage` keeps its current command, write, seed-invalidation, and recovery behavior.

## References

- [Python `os.replace`](https://docs.python.org/3.13/library/os.html#os.replace) — Defines the single-path replacement used for a validated local artifact candidate.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Cross-artifact feedback targets, dependency-closure traversal, or multi-artifact patch sessions.
- Adding, removing, splitting, merging, or reordering rows; changing any relation endpoint, identifier, decision state, or plan draft-seed path.
- Editing roadmap prose blocks or inventing an enrollment/migration format for that prose.
- Sharing local-mode publication or recovery semantics with broad `--from-stage`, adding recovery markers, or revising broad-stage overwrite behavior.
- Creating a Git checkpoint, requiring a Git worktree, or providing a persistent revision-session record or review view.
- Generating, promoting, overwriting, or refreshing roadmap-derived plan seeds.
- Promise of atomic visibility across the artifact and seed-state sidecar, a reader snapshot across artifacts, or protection from out-of-protocol filesystem writers.

## Risks

- **Scope-blocking:** A request can require structural, prose, cross-artifact, or combined-mode work. Mitigation: reject it locally and direct the operator to broad `--from-stage`.
- **Conservative invalidation:** A failed attempt can invalidate seeds without changing an artifact. Mitigation: this intentional safe false positive requires the existing explicit seed workflow, never a local draft refresh.
- **Opaque preservation:** The current renderer cannot preserve every accepted input. Mitigation: reject a noncanonical artifact before invalidation or backend work rather than rewrite or drop data.
- **Concurrency-blocking:** A broad, seed, or local writer can otherwise derive a result from a mutable baseline. Mitigation: serialize the defined writer set, including the local runner before preflight, around baseline reads and writes.

## Testing

Use the per-step details for exhaustive unit cases: selection and canonical preflight (step 1), strict reply parsing and candidate preservation (step 2), writer ownership, pre-backend sidecar `fsync`, and publication (step 3), then runner-held guard interleaving, CLI exclusivity, single-shot transport, and redacted evidence (step 4). Step 5 verifies the generated CLI reference and route documentation.

Use one composed integration case with another open feedback row present. It must make one physical backend request, transition only the selected feedback to `awaiting-review`, update at most one selected artifact, preserve every other canonical value, persist seed invalidation first, and write safe event evidence. Rejections must stop before invalidation and backend work where the relevant phase has not started; broad re-entry, seed workflows, and roadmap views keep their existing behavior.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — tests covering the behavior this step changes; green before completion.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.
- step 3 (feature) — tests covering the behavior this step changes; green before completion.
- step 4 (feature) — tests covering the behavior this step changes; green before completion.
- step 5 (non-code) — verification appropriate to the artifacts rather than unit tests.

## Acceptance criteria

- Only one eligible, same-artifact feedback selector can begin the local flow. Preflight validates the selected artifact and every retained feedback row before invalidation or backend work.
- The backend receives only selected feedback and target-row context. Its reply can propose at most one allowed target-row presentation change and one response to the selected feedback; all other canonical content remains unchanged.
- A gate-valid candidate updates only the selected artifact. Candidate validation uses required read-only upstream artifacts but no same-artifact predecessor.
- Before backend work, the local flow invalidates existing seed state and flushes and `fsync`s its temporary sidecar before the atomic sidecar replacement. It does not promise destination-directory persistence, whole-publication power-loss durability, or recovery.
- The defined mutation owners, including the local runner, share one writer guard before mutable baseline reads. Local failures leave completed invalidation conservative and never promote, refresh, or rewrite draft seed prose.
- `--revise-feedback` is exclusive and makes one physical backend request without recovery retry. It records one safe, machine-checkable preflight result and, after accepted preflight, one terminal attempt result without text-bearing data.
- Broad `--from-stage`, seed promotion or refresh, and roadmap views retain their documented publication and recovery behavior. The local mode makes no broader transaction or reader-snapshot guarantee.

## Deferred

- Cross-artifact closure and any multi-artifact revision protocol require a separately grounded follow-up plan.
- Prose-block editing and enrollment require a separately grounded follow-up plan.
- Git checkpoints, durable recovery markers, and cross-file publication recovery require a separately grounded follow-up plan.
- Lossless preservation or editing of opaque YAML extensions and noncanonical serialized formatting requires a separately grounded follow-up plan.
- File discoveries outside this outcome go to `BACKLOG.md` or `BUG_BACKLOG.md` with supporting evidence.
