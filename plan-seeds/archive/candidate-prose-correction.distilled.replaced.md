> **Replaced**: this file has been superseded by `docs/implementation-plans/2-candidate-prose-correction.md`.
> Preserved here for history; do not edit.

## Overview

This plan lets admitted candidate feedback correct a bounded shared narrative block in an existing roadmap artifact, with no change to any typed row. It adds a standalone existing-prose correction operation to candidate deltas (`roadmap_candidate.py`), next to today's add-row-only, append-only `CandidateAddRowProseAmendment`. It also narrowly widens context-issued source spans so that a shared narrative block naming several live rows can be issued as an authorized span. An approver sees and confirms the exact before/after text before promotion, and any edit requires a fresh approval. Failures publish no candidate.

## Problem statement

Today candidate feedback can only append prose for added rows (`CandidateAddRowProseAmendment`). The span-issuance rule (`roadmap_revision.py:project_row_owned_prose_spans`, via `_prose_blocks` and `contains_whole_row_id`) leaves out blocks that name more than one row. So a shared narrative paragraph that has gone stale cannot be corrected through candidate feedback unless a typed row also changes. The motivating case is the Integration shared Decisions paragraph. It needs to correct pending `decision-runtime-granularity` and remove the obsolete `decision-exclude-repo-browsing` reference, and neither change touches a typed Domain row. Source: BUG_BACKLOG "Candidate feedback cannot reconcile stale shared narrative without changing typed rows", promoted to IPPT-18 (2026-10-01).

## Architecture

**New candidate operation.** Candidate deltas in `plan_tool/roadmap_candidate.py` gain one new kind: a standalone existing-prose correction. It sits next to `CandidateAddRowProseAmendment` and does not replace it. The existing behavior of allowing several operations per feedback item stays as it is. The fragment byte ceiling is defined directly for candidates.

**Widened span issuance.** `roadmap_revision.py:project_row_owned_prose_spans` is extended narrowly, and its spans reach candidate context through `plan_tool/roadmap_candidate_context.py`. A shared narrative block that names several live rows can then be issued as an authorized span. This is the change that carries authority. Authority comes from the issued span and never from the mere presence of a reference to a removed row. An omitted amendment is never read as a deletion.

**Authority binding.** Each correction is bound to the exact predecessor version, the artifact, the span's source text and digest, the admitted feedback, and the relevant row identities. Stale references to removed rows are accounted for using predecessor and lineage evidence.

**Application reuse.** Corrections are applied through the existing exact-span application and overlap protections in `roadmap_revision_patch.py:_apply_stage_prose_amendments` (alongside `ReplaceRowProseAmendment` and `DeleteRowProseAmendment`). Body text outside the spans and the frontmatter delimiters stay byte-identical.

**Replacement/removal semantics come first.** The first step decides the replacement and removal semantics, including whether an empty replacement is allowed. Later steps depend on that decision.

**Refusal.** Unknown, ambiguous, stale, duplicate, overlapping, oversized, or unauthorized spans are refused, and a refusal publishes no candidate.

**Persistence and review.** Normalized corrections are persisted with explicit schema compatibility, so legacy candidates still load. They are replayed against the bound predecessor. Before/after text appears in candidate review, in the stack digest, and in structured version comparison. Applicable raw patch output is kept. Candidate prompts and `ROADMAP_FORMAT.md` are updated to match.

**Allowed behavior change.** Candidates gain one new operation kind and a widened span-issuance rule for shared narrative blocks. A fresh approval is required after any edit. No other candidate, promotion, or gate behavior changes. No reorganization is allowed.

**Delivery route.** The supported edit route is checked first to see whether it can carry the new operation. Discarding and rerunning the same batch is the fallback only if it cannot. The current Group 5 candidate stays as evidence until a corrected replacement exists.

**Stop condition.** If the span-widening definition cannot be stated without granting authority beyond the named block, stop and raise it with the user. Anything else found along the way goes into `BUG_BACKLOG.md` or `BACKLOG.md`, never into plan expansion.

**Backlog reconciliation.** No final-step removal is needed. The `BUG_BACKLOG.md` entry is a promotion stub, and it is removed in the shipping pull request per `docs/TRACKING.md` § "Promotion stubs".

## Out of scope

- Arbitrary body replacement, marker-based editing, generic document editing,
  automatic scope changes, or weaker described-row gates.
- The review-evidence layer that detects unresolved narrative contradictions —
  the separate seed `plan-seeds/candidate-narrative-review-evidence.md`. This
  seed ships the remedy without it.
- Rewriting accepted Group 4 feedback or requiring a new feedback group.
- Any presence of a stale-row reference granting authority over the artifact
  body.

## Risks

Widening span issuance is the authority-bearing change. A definition that is
too loose becomes the refused "arbitrary body replacement"; one that is too
tight leaves the Integration Decisions paragraph uncorrectable.

## Testing

- The actual Integration shared Decisions paragraph corrects pending
  `decision-runtime-granularity` and removes obsolete
  `decision-exclude-repo-browsing` with no typed Domain row change.
- Standalone prose changes, removed-row references, every refusal above,
  byte-preservation outside spans, immutable replay, reviewer-visible diff and
  digest changes, legacy candidate loading, fresh approval after edit, and
  interrupted publication/recovery.

## Acceptance criteria

- The Testing cases pass, and Group 4 remains accepted with no rewritten
  feedback and no new feedback group.
- An approver sees the exact before/after correction in candidate review.

## Deferred

Narrative-consistency review evidence and dispositions (separate seed).
