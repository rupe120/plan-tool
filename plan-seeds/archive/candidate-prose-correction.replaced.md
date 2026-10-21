> **Replaced**: this file has been superseded by `docs/implementation-plans/2-candidate-prose-correction.md`.
> Preserved here for history; do not edit.

# Plan seed: candidate feedback corrects stale shared narrative without a typed-row change

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing plan-seeds/candidate-prose-correction.md
```

It is **not** itself a plan — `plan-tool create` consumes the prose below and
proposes a step decomposition; the author then runs `plan-tool detail` per
step.

Source: BUG_BACKLOG "Candidate feedback cannot reconcile stale shared narrative
without changing typed rows" → promoted to IPPT-18 (2026-10-01). This seed carries that entry's scope
contract; the ticket holds the working brief.

## Outcome

Admitted candidate feedback can correct a bounded shared narrative block in an
existing roadmap artifact without any typed-row change, and an approver sees and
confirms the exact before/after text before promotion.

## In scope

- A standalone existing-prose correction operation on candidate deltas
  (`roadmap_candidate.py`), alongside today's add-row-only, append-only
  `CandidateAddRowProseAmendment`.
- A narrow extension of context-issued source spans (`roadmap_candidate_context.py`
  via `roadmap_revision.py:project_row_owned_prose_spans`) so a shared narrative
  block that names several live rows can be issued as an authorized span.
- Authority bound to the exact predecessor version, artifact, span source text
  and digest, admitted feedback, and the relevant row identities, with stale
  references to removed rows accounted for from predecessor/lineage evidence.
- Reuse of the exact-span application and overlap protections already in
  `roadmap_revision_patch.py:_apply_stage_prose_amendments`.
- Persistence of normalized corrections with explicit schema compatibility,
  replay against the bound predecessor, and before/after text in candidate
  review, stack digest, and structured version comparison; applicable raw patch
  output retained.
- Candidate prompts and `ROADMAP_FORMAT.md` updated to match.

## Out of scope / Non-goals

- Arbitrary body replacement, marker-based editing, generic document editing,
  automatic scope changes, or weaker described-row gates.
- The review-evidence layer that detects unresolved narrative contradictions —
  the separate seed `plan-seeds/candidate-narrative-review-evidence.md`. This
  seed ships the remedy without it.
- Rewriting accepted Group 4 feedback or requiring a new feedback group.
- Any presence of a stale-row reference granting authority over the artifact
  body.

## Allowed behavior changes

Candidates gain one new operation kind and a widened span-issuance rule for
shared narrative blocks. A fresh approval is required after any edit. No other
candidate, promotion, or gate behavior changes.

## Allowed reorganization

None.

## Architecture

Decisions `create` must not re-litigate:

- Authority comes from the issued span, never from the presence of a removed-row
  reference. An omitted amendment is never read as deletion.
- Replacement and removal semantics, including whether an empty replacement is
  permitted, are decided before implementation; `create` makes this the first
  step's deliverable, and later steps depend on it.
- The fragment byte ceiling is defined directly for candidates, and the existing
  multiple-operations-per-feedback behavior is preserved.
- Unaffected body text and frontmatter delimiters stay byte-identical.
- Failure publishes no candidate: unknown, ambiguous, stale, duplicate,
  overlapping, oversized, or unauthorized spans are refused.
- The supported edit route is assessed first for carrying the new operation; the
  discard/rerun of the same batch is the fallback only if it cannot. The current
  Group 5 candidate stays as evidence until a corrected replacement exists.

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

## Stop / defer

Stop and surface to the user if the span-widening definition cannot be stated
without granting authority beyond the named block. File anything else found
along the way in `BUG_BACKLOG.md` or `BACKLOG.md`, never as plan expansion.

## References

- `plan_tool/roadmap_candidate.py` (`CandidateAddRowProseAmendment`,
  `candidate_prose_amendment_diffs`, the append at the candidate apply step) —
  the append-only operation this extends.
- `plan_tool/roadmap_revision.py` (`project_row_owned_prose_spans`,
  `_prose_blocks`, `contains_whole_row_id`) — the span-issuance rule that omits
  multi-row blocks.
- `plan_tool/roadmap_revision_patch.py` (`_apply_stage_prose_amendments`,
  `ReplaceRowProseAmendment`, `DeleteRowProseAmendment`) — exact-span
  application and overlap protections to reuse.
- `plan_tool/roadmap_candidate_context.py` — where spans reach candidate
  context.
- `ROADMAP_FORMAT.md`, `ROADMAP_FEEDBACK_FORMAT.md` — immutable artifacts and
  feedback ownership.

## Backlog reconciliation

When this work ships, the plan's final step removes nothing further: the
`BUG_BACKLOG.md` entry is a promotion stub, removed in the shipping pull
request per `docs/TRACKING.md` § "Promotion stubs".
