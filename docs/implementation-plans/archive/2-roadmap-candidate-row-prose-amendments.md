> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
format_version: 1
title: Roadmap Candidate Row Prose Amendments
intent: A batch structural candidate can add prose-enabled Domain and Components rows,
  append bounded row-owned narrative, pass the unchanged `undescribed-row` gate, and
  expose each amendment to structural approval while remaining inert until promotion.
status: completed
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: plan-seeds/roadmap-candidate-row-prose-amendments.md
steps:
- id: 1
  title: Share the existing prose append rule while preserving stage replacements
    and deletions
  intent: Candidate additions can use the same spacing rule as stage revisions.
  files:
  - plan_tool/roadmap_revision_patch.py
  - tests/test_roadmap_revision_patch.py
  complexity: low
  change_type: refactor
  detail: docs/implementation-plans/plan-details/roadmap-candidate-row-prose-amendments/01-share-existing-prose-append-rule-while.md
  status: done
- id: 2
  title: Require bounded prose for new candidate additions and preserve removal, feedback
    stripping, and legacy replay
  intent: New describable rows clear the unchanged prose gate while stored candidates
    remain reproducible.
  files:
  - plan_tool/roadmap_candidate.py
  - plan_tool/roadmap_candidate_run.py
  - tests/test_roadmap_candidate.py
  - tests/test_roadmap_candidate_run.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: Provides the existing append rule for candidate assembly.
  detail: docs/implementation-plans/plan-details/roadmap-candidate-row-prose-amendments/02-require-bounded-prose-new-candidate.md
  status: done
- id: 3
  title: Show row-linked prose amendments in structural review without changing approval
    or promotion writes
  intent: An approver can inspect each artifact, row id, and exact fragment before
    confirming the stack.
  files:
  - plan_tool/roadmap_candidate.py
  - plan_tool/cli/roadmap_cmd.py
  - tests/test_roadmap_candidate_review.py
  - tests/cli/test_roadmap_cmd.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  depends_on_notes:
    2: Stores amendments in normalized candidate operations.
  detail: docs/implementation-plans/plan-details/roadmap-candidate-row-prose-amendments/03-show-row-linked-prose-amendments.md
  status: done
- id: 4
  title: Ask for row-owned prose in candidate proposals and corrections while preserving
    publication writes
  intent: A proposal or retry can supply the prose that the candidate contract requires.
  files:
  - plan_tool/roadmap_candidate_run.py
  - plan_tool/prompts/roadmap-candidate-delta.md
  - plan_tool/prompts/roadmap-candidate-delta-selector.md
  - tests/test_roadmap_candidate_run.py
  - tests/test_roadmap_candidate_review.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  depends_on_notes:
    2: Defines which additions require an amendment and how it is validated.
  detail: docs/implementation-plans/plan-details/roadmap-candidate-row-prose-amendments/04-ask-row-owned-prose-candidate-proposals.md
  status: done
- id: 5
  title: Document the candidate contract and remove the source bug after regressions
    pass
  intent: The documented contract matches shipped candidate behavior and the resolved
    bug leaves the backlog.
  files:
  - ROADMAP_FEEDBACK_FORMAT.md
  - ROADMAP_FORMAT.md
  - BUG_BACKLOG.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 2
  - 3
  - 4
  depends_on_notes:
    2: Establishes the validated candidate and replay contract.
    3: Establishes the structural review disclosure.
    4: Completes proposal and correction guidance and its regressions.
  detail: docs/implementation-plans/plan-details/roadmap-candidate-row-prose-amendments/05-document-candidate-contract-remove.md
  status: done
---
# Roadmap Candidate Row Prose Amendments

## Overview

Extend candidate additions with the minimum prose capability required to make
new design rows describable. The resulting plan closes the source entry in
`BUG_BACKLOG.md` when the implementation and regressions ship.

## Problem statement

Candidate `add-row` operations change frontmatter rows while retaining the
predecessor body, so an added prose-enabled row fails `undescribed-row`. The
existing row-owned append path defines the necessary bounded operation, but
batch candidate evidence and review do not yet carry it.

## Architecture

Only candidate `add-row` gains `prose_amendment: {row_id, fragment}`. It is
required for prose-enabled row types and forbidden otherwise; its row id
matches the added row, and its nonblank fragment names that whole id. Candidate
validation applies `HARD_MAX_PROSE_AMENDMENT_BYTES` directly to each fragment.

Batch candidates retain their current ability to bind multiple admitted
additions and amendments to one feedback item; they do not adopt the
stage-revision one-material-operation limit. Materialization appends admitted
fragments in deterministic normalized-operation order without changing
predecessor prose. The parent operation's admitted `feedback_id` remains the
amendment's authority.

The immutable candidate record and replay bind amendments through normalized
operations. A deterministic row-id-linked amendment diff exposes each
artifact key, row id, and fragment to review and the structural stack digest.
Proposal and correction prompts require the amendment beside every eligible
addition.

## References

- `BUG_BACKLOG.md` — “Structural candidates cannot satisfy described-row gates for newly added rows”, the source contract and Integration evidence.
- `plan_tool/roadmap_candidate.py` — candidate operation admission, assembly, immutable identity, and replay boundary.
- `plan_tool/roadmap_revision.py` and `plan_tool/roadmap_revision_patch.py` — existing row-owned append-only prose invariants.
- `plan_tool/roadmap_diff.py` and `plan_tool/roadmap_candidate_review.py` — immutable review diff and structural stack digest surfaces.
- `plan_tool/roadmap_gates.py:check_inventory_has_prose` — unchanged `undescribed-row` enforcement.
- `plan_tool/project_config.py:HARD_MAX_PROSE_AMENDMENT_BYTES` — project-wide fragment ceiling.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Replace-row or remove-row prose, source-span replacement, body regions or
  markers, whole-body edits, and synthesized narrative.
- Weakening or bypassing `undescribed-row`.
- Changing candidate authority, the existing candidate-driven ledger proposal
  transition, accepted-head selection, seed effects, or the adjacent
  correction-diagnostics effort.

## Risks

- A prose change bound only by an artifact digest is invisible to an approver;
  the review diff and stack digest must carry the exact row-linked fragment.
- Applying stage-revision cardinality limits to a ledger batch would reject
  existing valid multiple-addition feedback; preserve batch cardinality.
- A fragment that names the wrong or partial identifier could clear prose
  coverage incorrectly; retain whole-id and byte-limit enforcement before
  candidate assembly.

## Testing

Prove that one batch adding a Domain business rule and workflow plus a
Components decision, with their append-only prose, clears complete gates,
stores inertly, and reaches structural approval with amendment records in the
review diff and stack digest. Preserve refusal for omitted, non-prose-enabled,
mismatched-id, blank, non-naming, over-limit, or unadmitted amendments.
Prove multiple additions for one admitted feedback item remain valid. Replay
the Integration-shaped recovery batch and prove no canonical artifact, accepted head,
or seed changes before approval while the existing ledger proposal transition
remains unchanged; stale promotion continues to refuse.

## Acceptance criteria

- Every eligible candidate addition has exactly one bounded row-owned prose
  fragment, and the complete gate sees its row id after assembly.
- Immutable candidate replay, review output, and the structural stack digest
  agree on every amendment's artifact, row id, and fragment.
- Candidate additions for one admitted feedback item remain multi-operation.
- The source bug entry is removed only after focused tests and the relevant
  suite are green.

## Deferred

Replacement-span semantics and all general artifact-body editing remain separate work.
