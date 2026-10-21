---
format_version: 1
title: Candidate Prose Correction
intent: Admitted candidate feedback can correct a bounded shared narrative block in
  an existing roadmap artifact without any typed-row change, and an approver sees
  and confirms the exact before/after text before promotion.
status: completed
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: plan-seeds/candidate-prose-correction.md
steps:
- id: 1
  title: 'Settle the shared-narrative correction contract in ROADMAP_FORMAT.md: the
    shared-block span definition and its ownership (a shared span is bound to the
    full set of live rows the block names, its owning set; spans carry one row_id
    today), authority binding, the refusal list with each value''s meaning, which
    typed-row operations may share a candidate with a correction and the application
    order, the one body state the existing artifact gates see at issuance, application,
    and replay, how a retained removed-row reference is treated, the candidate byte
    ceiling, and which routes carry it; replacement stays nonempty and removal is
    never an empty replacement and the candidate correction offers no delete'
  intent: 'Fixes the span-ownership and narrow span-widening rule before any code
    depends on them; replace/remove semantics follow the stage revision precedent.
    Settled here: a reference to a removed row neither joins nor is required of the
    owning set and never grants authority; a correction is refused when the same candidate
    adds, edits, or removes any row in its owning set; the correction applies before
    add-row appends; the corrected body must pass the existing artifact gates or no
    candidate is published; a shared span is issued only when every live row in its
    owning set is visible in the candidate context, else it is not issued. This is
    also where the stop condition is checked: if the widened span cannot be defined
    without granting authority beyond the named block, work stops here and goes to
    the user.'
  files:
  - ROADMAP_FORMAT.md
  complexity: medium
  change_type: non-code
  detail: docs/implementation-plans/plan-details/candidate-prose-correction/01-settle-shared-narrative-correction.md
  status: done
- id: 2
  title: Extract the exact-span splice and overlap refusal from _apply_stage_prose_amendments
    into a shared helper in roadmap_revision_patch.py, keeping stage-revision replace/delete/append
    behavior and its "stage prose amendments overlap" refusal byte-identical
  intent: Lets candidate corrections reuse the existing exact-span application and
    overlap protection instead of writing a second, drifting copy.
  files:
  - plan_tool/roadmap_revision_patch.py
  - tests/test_roadmap_revision_patch.py
  complexity: low
  change_type: refactor
  detail: docs/implementation-plans/plan-details/candidate-prose-correction/02-extract-exact-span-splice-overlap.md
  status: done
- id: 3
  title: Widen candidate span issuance in project_row_owned_prose_spans so one blank-line
    narrative block naming several live rows is issued as an authorized shared span
    bound to the full set of live rows it names (its owning set; a removed-row reference
    neither joins nor is required of that set), issued only when every row in the
    owning set is visible in the candidate context, carried through roadmap_candidate_context.py
    with legacy capsules still loading; the local revision selector _select_row_owned_prose_spans
    deliberately stays narrow
  intent: Lets a stale shared paragraph such as the Integration Decisions block become an
    authorized correction target without any typed row changing, and without a reference
    to a removed row ever granting authority.
  files:
  - plan_tool/roadmap_revision.py
  - plan_tool/roadmap_candidate_context.py
  - tests/test_roadmap_revision.py
  - tests/test_roadmap_candidate_context.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: the shared-block span definition and its authority boundary
  detail: docs/implementation-plans/plan-details/candidate-prose-correction/03-widen-candidate-span-issuance-project.md
  status: done
- id: 4
  title: 'Add the standalone existing-prose correction operation to candidate deltas:
    closed parsing and diagnostics, a candidate-local fragment byte ceiling, binding
    to the issued span (predecessor version, artifact, span text and digest, admitted
    feedback, owning-set row ids), refusal of unknown/ambiguous/stale/duplicate/overlapping/oversized/unauthorized
    spans and of a correction whose candidate also adds, edits, or removes a row in
    its owning set, application that replaces only the issued span bytes before add-row
    appends, and refusal when the corrected body fails the existing artifact gates;
    one feedback item may carry a correction alongside its other operations'
  intent: Gives admitted feedback a bounded way to correct existing shared narrative.
    A refusal publishes no candidate, and body text outside the span and the frontmatter
    delimiters stays byte-identical.
  files:
  - plan_tool/roadmap_candidate.py
  - tests/test_roadmap_candidate.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 2
  - 3
  depends_on_notes:
    1: replace/remove semantics, refusal list, and byte ceiling
    2: the shared exact-span splice and overlap helper
    3: issued shared spans in candidate context
  detail: docs/implementation-plans/plan-details/candidate-prose-correction/04-standalone-existing-prose-correction.md
  status: done
- id: 5
  title: Teach roadmap-candidate-delta.md (the batch route) the correction operation,
    with a test that the prompt names every key the parser requires; the selector-era
    prompt deliberately does not offer it
  intent: Makes the operation reachable from real candidate runs. Without this, the
    parser accepts something the model is never told it may produce.
  files:
  - plan_tool/prompts/roadmap-candidate-delta.md
  - tests/test_roadmap_candidate_run.py
  complexity: low
  change_type: feature
  depends_on:
  - 4
  depends_on_notes:
    4: the landed operation keys and limits the prompt restates
  detail: docs/implementation-plans/plan-details/candidate-prose-correction/05-teach-roadmap-candidate-delta-md-batch.md
  status: done
- id: 6
  title: 'Persist and replay correction operations: keep them in normalized_operations,
    replay them against the bound predecessor in _require_reproducible_batch_operations
    in the contract''s application order (correction before add-row appends), keep
    legacy and selector-era candidates loading unchanged, and recover an interrupted
    publication'
  intent: Makes a stored correction immutable and reproducible from stored bytes,
    so promotion and review never trust an unreplayable candidate.
  files:
  - plan_tool/roadmap_candidate_run.py
  - plan_tool/roadmap_candidate.py
  - tests/test_roadmap_candidate_run.py
  complexity: medium
  change_type: feature
  depends_on:
  - 4
  depends_on_notes:
    4: the operation record and its replayable authority binding
  detail: docs/implementation-plans/plan-details/candidate-prose-correction/06-persist-replay-correction-operations.md
  status: done
- id: 7
  title: Show the exact before/after correction in structural candidate review and
    the stack digest, confirm that the edit route carries the operation and that any
    edit requires a fresh approval, and prove the Integration Decisions paragraph correction
    end to end with Group 4 untouched, using that paragraph (1,288 bytes) checked
    in as a test fixture copied from integration-aidlc-mvp's 01-domain.md
  intent: Lets an approver see and confirm the exact text change before promotion.
    It also closes the plan's acceptance case on the real motivating paragraph.
  files:
  - plan_tool/roadmap_candidate.py
  - plan_tool/roadmap_candidate_review.py
  - plan_tool/cli/roadmap_cmd.py
  - tests/test_roadmap_candidate_review.py
  - tests/cli/test_roadmap_cmd.py
  complexity: medium
  change_type: feature
  depends_on:
  - 5
  - 6
  depends_on_notes:
    5: candidate runs that can emit the operation
    6: stored, replayable correction evidence
  detail: docs/implementation-plans/plan-details/candidate-prose-correction/07-show-exact-before-after-correction.md
  status: done
- id: 8
  title: Sync ROADMAP_FORMAT.md to the landed symbols, replacing the add-row-only
    prose-authority sentence, record the delivery route (edit first, discard-and-rerun
    only as fallback, Group 5 candidate kept as evidence until replaced), and remove
    the IPPT-18 promotion stub from BUG_BACKLOG.md
  intent: Keeps the format reference true to what ships, leaves operators a stated
    path for delivering the Integration correction, and closes the originating backlog record.
  files:
  - ROADMAP_FORMAT.md
  - BUG_BACKLOG.md
  complexity: low
  change_type: non-code
  depends_on:
  - 7
  depends_on_notes:
    7: landed review surface and confirmed edit-route behavior
  detail: docs/implementation-plans/plan-details/candidate-prose-correction/08-sync-roadmap-format-md-landed-symbols.md
  status: done
---
# Candidate Prose Correction

## Overview

This plan lets admitted candidate feedback correct a bounded shared narrative block in an existing roadmap artifact, with no change to any typed row. It adds a standalone existing-prose correction operation to candidate deltas (`roadmap_candidate.py`), next to today's add-row-only, append-only `CandidateAddRowProseAmendment`. It also narrowly widens context-issued source spans so that a shared narrative block naming several live rows can be issued as an authorized span. An approver sees and confirms the exact before/after text before promotion, and any edit requires a fresh approval. Failures publish no candidate.

## Problem statement

Today candidate feedback can only append prose for added rows (`CandidateAddRowProseAmendment`). The span-issuance rule (`roadmap_revision.py:project_row_owned_prose_spans`, via `_prose_blocks` and `contains_whole_row_id`) leaves out blocks that name more than one row. So a shared narrative paragraph that has gone stale cannot be corrected through candidate feedback unless a typed row also changes. The motivating case is the Integration shared Decisions paragraph. It needs to correct pending `decision-runtime-granularity` and remove the obsolete `decision-exclude-repo-browsing` reference, and neither change touches a typed Domain row. Source: BUG_BACKLOG "Candidate feedback cannot reconcile stale shared narrative without changing typed rows", promoted to IPPT-18 (2026-10-01).

## Architecture

**New candidate operation.** Candidate deltas in `plan_tool/roadmap_candidate.py` gain one new kind: a standalone existing-prose correction. It sits next to `CandidateAddRowProseAmendment` and does not replace it. The existing behavior of allowing several operations per feedback item stays as it is. The fragment byte ceiling is defined directly for candidates.

**Widened span issuance.** `roadmap_revision.py:project_row_owned_prose_spans` is extended narrowly, and its spans reach candidate context through `plan_tool/roadmap_candidate_context.py`. A shared narrative block that names several live rows can then be issued as an authorized span. This is the change that carries authority. Authority comes from the issued span and never from the mere presence of a reference to a removed row. An omitted amendment is never read as a deletion.

**Authority binding.** Each correction is bound to the exact predecessor version, the artifact, the span's source text and digest, the admitted feedback, and the owning-set row identities. A removed-row reference is not part of the binding.

**Application reuse.** Corrections are applied through the existing exact-span application and overlap protections in `roadmap_revision_patch.py:_apply_stage_prose_amendments` (alongside `ReplaceRowProseAmendment` and `DeleteRowProseAmendment`). Body text outside the spans and the frontmatter delimiters stay byte-identical.

**Span ownership comes first.** A shared span is bound to the full set of live rows its block names (its owning set); today a span carries exactly one `row_id`, so step 1 defines the multi-row binding and the narrow widening rule. A reference to a removed row neither joins nor is required of the owning set and never grants authority. Replacement stays nonempty and is never an empty removal, as in `_apply_stage_prose_amendments`. Later steps depend on that decision.

**Issuance.** A shared span is issued only when every live row in its owning set is visible in the candidate context; otherwise it is not issued. Legacy single-row spans load unchanged and are valid correction targets, as an owning set of one. How a shared span is represented in context is a detail-stage choice. Without full visibility the interaction refusal below cannot be checked.

**Interaction with typed-row operations.** The owning set is computed from the predecessor's live rows only. A correction is refused when the same candidate adds, edits, or removes any row in its owning set; naming a row the same candidate adds, which is not in the owning set, is allowed. Unrelated operations may share the candidate. The correction applies first and add-row appends follow, in one order that issuance, application, and replay all use.

**Post-correction validity.** The existing artifact gates run against one defined body state, the same at issuance, application, and replay. That state includes the same candidate's add-row appends, so a correction may name a row that candidate adds; step 1 names it exactly. Because of that one state, a stored candidate replays to the accept/refuse result it had at publication. A retained reference to a removed row gets no special handling: the correction neither requires it removed nor is exempted, and the existing gates decide. A correction that fails them, for example by dropping a live row's only description, is refused and publishes no candidate.

**Refusal.** Unknown, ambiguous, stale, duplicate, overlapping, oversized, or unauthorized spans are refused, and a refusal publishes no candidate.

**Persistence and review.** Normalized corrections are persisted with explicit schema compatibility, so legacy candidates still load. They are replayed against the bound predecessor. Before/after text appears in candidate review and in the stack digest. Version comparison keeps showing the raw patch; a labeled correction card there is carved to BACKLOG #436. Applicable raw patch output is kept. Candidate prompts and `ROADMAP_FORMAT.md` are updated to match.

**Allowed behavior change.** Candidates gain one new operation kind and a widened span-issuance rule for shared narrative blocks. A fresh approval is required after any edit. No other candidate, promotion, or gate behavior changes. No reorganization is allowed.

**Delivery route.** The supported edit route is checked first to see whether it can carry the new operation. Discarding and rerunning the same batch is the fallback only if it cannot. The current Group 5 candidate stays as evidence until a corrected replacement exists.

**Stop condition.** If the span-widening definition cannot be stated without granting authority beyond the named block, stop and raise it with the user. Anything else found along the way goes into `BUG_BACKLOG.md` or `BACKLOG.md`, never into plan expansion.

**Backlog reconciliation.** The `BUG_BACKLOG.md` entry is a promotion stub (IPPT-18). The final step removes it in the shipping pull request, per `docs/TRACKING.md` § "Promotion stubs".

## References

- [difflib — Helpers for computing deltas (Python standard library)](https://docs.python.org/3/library/difflib.html) — Covers unified_diff and SequenceMatcher, which are useful for showing the approver the exact before/after correction text in candidate review.
- [hashlib — Secure hashes and message digests (Python standard library)](https://docs.python.org/3/library/hashlib.html) — Reference for the SHA-256 digest API used to bind each correction to the exact source text of its issued span and to verify that span on replay.
- [CommonMark Spec](https://spec.commonmark.org/) — Defines Markdown paragraphs, headings, and fenced code blocks, which you need to delimit shared narrative blocks precisely when widening span issuance.
- [YAML Ain't Markup Language (YAML) Version 1.2](https://yaml.org/spec/1.2.2/) — The YAML specification behind roadmap frontmatter, relevant to keeping the frontmatter delimiters and typed rows byte-identical while body prose changes.
- [RFC 3629 — UTF-8, a transformation format of ISO 10646](https://www.rfc-editor.org/rfc/rfc3629) — The UTF-8 encoding standard, relevant to defining the candidate fragment byte ceiling and byte-exact span offsets on non-ASCII text.
- [dataclasses — Data Classes (Python standard library)](https://docs.python.org/3/library/dataclasses.html) — Covers frozen dataclasses and field defaults, which are useful for modeling the new immutable correction operation next to CandidateAddRowProseAmendment and for keeping legacy schema loading compatible.
- [os.replace — Miscellaneous operating system interfaces (Python standard library)](https://docs.python.org/3/library/os.html#os.replace) — Documents atomic file replacement, which applies to the requirement that failed or interrupted candidate publication leaves no partial candidate behind.

## Steps

See the `steps:` block in the frontmatter.

## Scope guardrails

This plan does not:

- add arbitrary body replacement, marker-based editing, generic document
  editing, automatic scope changes, or weaker described-row gates;
- build the review-evidence layer that detects unresolved narrative
  contradictions (IPPT-19); this plan ships the remedy without it;
- rewrite accepted Group 4 feedback or require a new feedback group;
- let a stale-row reference grant authority over the artifact body.

## Out of scope

- Arbitrary body replacement, marker-based editing, generic document editing,
  automatic scope changes, or weaker described-row gates.
- The review-evidence layer that detects unresolved narrative contradictions
  (IPPT-19). This plan ships the remedy without it.
- Rewriting accepted Group 4 feedback or requiring a new feedback group.
- Any presence of a stale-row reference granting authority over the artifact
  body.
- A labeled correction card in structured version comparison: carved to
  BACKLOG #436. Comparison keeps showing the raw patch.

## Risks

Widening span issuance is the authority-bearing change. A definition that is
too loose becomes the refused "arbitrary body replacement"; one that is too
tight leaves the Integration Decisions paragraph uncorrectable. Partial context
visibility has the same effect: a shared span is withheld, never silently
narrowed, when any row in its owning set is missing from the candidate context,
and step 7's end-to-end case proves the Integration paragraph's context shows them all.

## Testing

- The actual Integration shared Decisions paragraph corrects pending
  `decision-runtime-granularity` and removes obsolete
  `decision-exclude-repo-browsing` with no typed Domain row change.
- Standalone prose changes, removed-row references, every refusal above,
  a correction sharing a candidate with a typed-row operation on its owning set,
  a block naming a removed row, a correction that fails the existing artifact
  gates, a correction naming a row the same candidate adds, a retained removed-row reference, replay reproducing the publication-time accept/refuse result, a shared block whose owning set is only partly visible in context (not
  issued), byte-preservation outside spans, immutable replay, reviewer-visible diff and
  digest changes, legacy candidate loading, fresh approval after edit, and
  interrupted publication/recovery.

## Acceptance criteria

- The Testing cases pass, and Group 4 remains accepted with no rewritten
  feedback and no new feedback group.
- An approver sees the exact before/after correction in candidate review.
- The IPPT-18 promotion stub is removed from `BUG_BACKLOG.md`.

## Deferred

Narrative-consistency review evidence and dispositions (separate seed).
