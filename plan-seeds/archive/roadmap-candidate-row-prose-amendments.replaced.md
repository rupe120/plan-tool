> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-candidate-row-prose-amendments.md`.
> Preserved here for history; do not edit.

# Plan seed: Candidate row-owned prose amendments

## Outcome

A batch structural candidate can add prose-enabled Domain and Components rows,
append bounded row-owned narrative, pass the unchanged `undescribed-row` gate,
and expose each amendment to structural approval while remaining inert until
promotion.

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

## In scope

- Candidate add-row parsing, validation, materialization, immutable replay,
  review diff, stack presentation, and digest binding for row-owned appended
  prose.
- The existing append-only prose invariants and hard byte ceiling, reused at
  the candidate boundary.
- Proposal and correction guidance plus focused materialization, candidate-run,
  review, and promotion regressions.
- Removing the source `BUG_BACKLOG.md` entry after the shipped behavior is
  covered.

## Out of scope

- Replace-row or remove-row prose, source-span replacement, body regions or
  markers, whole-body edits, and synthesized narrative.
- Weakening or bypassing `undescribed-row`.
- Changing candidate authority, the existing candidate-driven ledger proposal
  transition, accepted-head selection, seed effects, or the adjacent
  correction-diagnostics effort.

## Allowed behavior changes

Eligible candidate additions require and append bounded prose fragments, and
candidate review surfaces their immutable amendment diffs. All candidate
publication and approval behavior remains unchanged.

## Allowed reorganization

Only the smallest shared extraction needed to reuse row-owned append-only
validation or application semantics at the candidate boundary.

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

## Stop / defer

Defer any need to replace or remove existing prose, change body structure, or
redesign candidate authority to a separate backlog entry.

## References

- `BUG_BACKLOG.md` — “Structural candidates cannot satisfy described-row gates for newly added rows”, the source contract and Integration evidence.
- `plan_tool/roadmap_candidate.py` — candidate operation admission, assembly, immutable identity, and replay boundary.
- `plan_tool/roadmap_revision.py` and `plan_tool/roadmap_revision_patch.py` — existing row-owned append-only prose invariants.
- `plan_tool/roadmap_diff.py` and `plan_tool/roadmap_candidate_review.py` — immutable review diff and structural stack digest surfaces.
- `plan_tool/roadmap_gates.py:check_inventory_has_prose` — unchanged `undescribed-row` enforcement.
- `plan_tool/project_config.py:HARD_MAX_PROSE_AMENDMENT_BYTES` — project-wide fragment ceiling.

## Deferred

Replacement-span semantics and all general artifact-body editing remain separate work.
