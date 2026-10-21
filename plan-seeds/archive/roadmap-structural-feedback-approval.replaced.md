> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-structural-feedback-approval.md`.
> Preserved here for history; do not edit.

## Outcome

Ordinary roadmap feedback that requires typed structural changes produces one inert, fully validated successor revision and reaches one explicit approve/edit/reject gate. For a structural proposal, only approval may advance the accepted head; rejection, edit, staleness, invalid model output, and failed application leave canonical roadmap state unchanged.

## Overview

Add the structural-approval layer that follows the versioned feedback revision chain. Users continue to submit ordinary feedback without classifying it. Plan Tool classifies a valid typed operation set internally, lets bounded presentation changes proceed through the current batch candidate lifecycle without structural approval, and routes broader same-artifact or cross-artifact operations to one reviewable proposal. The proposal reuses the existing immutable candidate, review binding, promotion, and publication authorities.

The approval-gate capability and its Integration provenance are recorded in `handoffs/2026-09-22-roadmap-feedback-revision-approval.md` and BACKLOG #423.

## Problem statement

The candidate delta vocabulary in `plan_tool/roadmap_candidate.py` admits `add-row`, `replace-row`, and `remove-row` operations with separate reviewer responses. Ordinary CLI feedback enters the candidate batch route, but no user-facing structural approval decision follows a valid structural candidate. The user should see the exact proposed roadmap change and a decision without choosing a structural feedback type or interpreting a generic parser failure. The older selected-local revision runner is not a CLI route (BACKLOG #429).

The immutable revision-history contract makes ordinary enrolled feedback enter the selector-free `--propose-candidate` batch route in `plan_tool/roadmap_candidate_run.py:run_initial_candidate_proposal()` from the current `AcceptedRoadmapHead` in `plan_tool/roadmap_versions.py`. A batch candidate binds its accepted root, its direct source, the eligible ledger-item snapshot, derived context, exact candidate bytes, and its receipt. This plan begins at that candidate boundary. It does not recreate enrollment, candidate storage, accepted-head selection, review sealing, promotion, or recovery.

## Architecture

Route selection is deterministic over a successfully parsed and authority-valid candidate delta, never over feedback wording. Bounded presentation changes retain their current candidate behavior without the new structural gate. Any authorized row addition, removal, non-presentation replacement, relation or ordering change, or multi-artifact effect becomes a structural proposal.

Each structural feedback process creates an immutable successor candidate from the current accepted head: accepted predecessor -> proposed successor -> reviewed replacement when edited -> approved promotion. This is a commit-like revision chain. The next feedback process starts from the successor promoted by the previous one, so revision history and feedback lineage remain explicit.

The successor candidate binds the admitted feedback identities, accepted root and direct source, brief identity, exact proposed artifact bytes, typed operation set, and validation result. Candidate construction carries changes through the full proposed artifact chain so downstream stages validate references and ordering against proposed upstream bytes. Invalid or incomplete proposals never reach approval.

One approval surface presents the requested outcome, affected artifacts and rows, relation or ordering effects, material consequences, and explicit non-goals. `approve` binds the exact reviewed candidate; `edit` returns a replacement proposal for a fresh decision; `reject` releases the active candidate. The plan must define how these choices consume the existing review, replacement, seal, and terminal-resolution contracts. An answer to a review question is not structural approval.

The approval binds persisted candidate and review facts. Initial batch evidence does not retain the model response, so a question cannot anchor on that response; replacement evidence retains what its identity recheck needs. The read-only ledger current/stale label (#428) and selector-era lineage release gap (#395) remain separate work.

Approved promotion rechecks the stored brief, recorded feedback binding, current accepted root and active candidate, candidate bytes, and validation binding before advancing `AcceptedRoadmapHead`. It uses the stored batch rather than rediscovering live ledger eligibility; unrelated reviewer edits do not invalidate recorded evidence. The existing publication journal and recovery boundary own the accepted-head write. The plan must identify any necessary feedback and seed effects within their existing owners. No failure may leave a partial accepted-head update or partial effects tied to that update.

Create must derive the per-outcome contract for `approve`, `edit`, and `reject`: producer, precedence, persisted binding, consumers, invalidation rule, operator-visible result, and exit path. It must also derive the structural-route boundary for each existing operation kind without broadening stage authority.

## Input

The immutable feedback revision-history surface supplies the ordinary-feedback handoff to an inert candidate rooted at the current accepted head. The existing candidate, review, promotion, and publication records are the contracts this effort consumes. This plan does not own their delivery or migration.

## In scope

- Internal bounded-versus-structural classification after strict typed-operation validation.
- A complete inert structural candidate spanning the affected roadmap stages and bound to the accepted root, direct source, and admitted feedback.
- One approve/edit/reject surface whose decision binds or invalidates the exact reviewed candidate.
- Same-artifact and cross-artifact structural changes that existing stage authority and full-roadmap gates can validate.
- Freshness rechecks and exact-candidate promotion through existing version, publication, feedback-state, and seed-invalidation owners.
- Plain-language proposal and refusal output sufficient to distinguish an invalid response, stale proposal, rejected proposal, failed gate, and successful promotion without retaining raw model output.
- Documentation and contract tests for the unified feedback path and its structural approval lifecycle.

## Scope guardrails

There is one user-facing feedback intake and one active structural decision per proposal. An edit presents a replacement for a fresh decision. Users never pre-classify feedback as structural. Classification operates only on validated typed operations and grants no operation authority beyond the current candidate and stage policies.

`AcceptedRoadmapHead` remains the sole canonical selector for enrolled roadmaps. Proposal creation, review, edit, rejection, candidate storage, and validation never advance it or rewrite live top-level roadmap artifacts. Approval authorizes only the exact reviewed candidate; promotion remains the sole accepted-head writer and must reject a stale accepted root or active candidate, or a broken stored brief, feedback, candidate, decision, or gate binding. It does not rediscover live ledger eligibility. Every later feedback revision selects the promoted accepted version as its predecessor.

The implementation reuses the existing immutable candidate, review-seal, promotion, publication-journal, recovery, feedback, and seed-invalidation contracts wherever they satisfy this outcome. It may extend their structural metadata and user decision surface, but it must not create a second candidate store, accepted-head writer, version schema, checkpoint system, or publication transaction.

No proposal may be approved while invalid. Failed, rejected, edited, interrupted, and stale proposals cannot advance the accepted head or rewrite canonical artifacts or seeds. The existing lifecycle may retain immutable candidate/review history and update selected ledger items as the proposal progresses. Unselected feedback remains byte-for-byte unchanged.

## Out of scope

- A second feedback type, structural flag, or user-authored route selection.
- Silent enrollment, automatic approval, automatic promotion, or acceptance without an exact user decision.
- New immutable-version, candidate-storage, accepted-head, checkpoint, recovery, or general transaction subsystems.
- Weakening candidate-delta or stage operation authority, or reviving the unreachable selected-local CLI route.
- Arbitrary project editing, workflow authoring, multi-user review, voting, assignments, or parallel approval queues.
- Automatic feedback grouping or splitting, and any specific scope-narrowing recommendation; broad or incoherent feedback may receive only the existing generic guidance outside this plan.
- A new raw-response retention or parser-forensics subsystem. Invalid model envelopes produce no proposal and use the existing safe failure-reporting boundary; richer protocol diagnostics remain separate work.
- Structural operations that current full-roadmap gates or stage authority cannot validate.

## Allowed behavior changes

Structural operations proposed from ordinary feedback may reach one approval gate and, after exact approval, advance the accepted roadmap version. Bounded presentation feedback may continue through the current candidate lifecycle without that structural gate. No other roadmap authoring, review, or publication behavior changes.

## Allowed reorganization

No ownership reorganization is authorized. Existing candidate, review, promotion, publication, feedback, and seed owners may expose the smallest new integration seams required by the approval flow, but their authority boundaries remain in place.

## Risks

Reusing candidate review can accidentally expose multiple user gates or treat a stored candidate as approved. Building only the selected stage can validate against stale upstream bytes and admit a cross-artifact contradiction. Regenerating after approval can apply bytes the user never reviewed. Coupling new feedback or seed effects to promotion can leave partial state after recovery unless those effects use the existing publication boundary. A natural-language classifier can misroute requests and silently expand authority. The plan must keep these risks visible as ordering and identity properties.

## Testing

Use a stage-separated replay covering both route classes. At bare-plan stage, retain the properties that classification follows validated operations, one decision binds exact inert bytes, and every nonpublication exit preserves all canonical state; leave storage layout and prompt mechanics to detail. At detail-grounded stage, require focused coverage for presentation-only feedback, same-artifact addition/removal/edit, cross-artifact relation change, approve/edit/reject, stale predecessor or feedback, invalid envelope, pre-approval gate failure, post-approval gate or interruption recovery, unselected feedback preservation, and a second revision based on the first promoted successor.

The recovered Integration current-question case is the representative structural replay: a valid typed response requiring a Domain entity plus downstream ownership and plan references reaches one proposal and approval decision, or a specific authority/gate refusal. Invalid operation syntax creates neither a candidate nor a canonical write.

## Acceptance criteria

- Ordinary feedback needs no user-selected type; validated typed operations deterministically select the bounded or structural route.
- The structural route presents exactly one approve/edit/reject decision over a complete, gate-valid, inert proposal identifying all affected artifacts, rows, consequences, and non-goals.
- Approval can promote only the exact reviewed candidate after currentness rechecks; edit and reject end the prior candidate's eligibility for structural approval.
- Each feedback revision has one explicit accepted predecessor, preserves its immutable successor history, and makes the next revision derive from the newly promoted head.
- Existing candidate/version, review binding/replacement/seal, promotion, publication/recovery, feedback-state, and seed-invalidation owners are reused rather than duplicated.
- Presentation-only feedback retains its current candidate authority and behavior without the structural approval gate.
- Same-artifact and cross-artifact proposals consume proposed upstream bytes and pass existing full-roadmap gates before approval and again where required before promotion.
- Invalid, stale, rejected, interrupted, or failed proposals cannot advance the accepted head, rewrite canonical artifacts or seeds, or promote a candidate; selected ledger items and immutable candidate/review history follow the existing lifecycle.
- Unselected feedback remains byte-for-byte unchanged on every route.
- A valid typed Integration current-question replay reaches the structural approval path or a specific authority/gate refusal.

## Deferred

Read-only feedback-breakdown advice, automatic subset generation, richer parser/protocol failure receipts, and structural operations outside current roadmap stage authority remain separate backlog work. None is a prerequisite for the approval gate.

## Stop / defer

File newly discovered needs in `BACKLOG.md` or `BUG_BACKLOG.md` when they require broader stage authority, a new version or transaction subsystem, automatic feedback decomposition, raw-response retention, or unrelated roadmap repair. Stop this plan if the prerequisite candidate lifecycle cannot provide one exact inert proposal and one accepted-head promotion without duplicating authority.

## References

- [`handoffs/2026-09-22-roadmap-feedback-revision-approval.md`](../handoffs/2026-09-22-roadmap-feedback-revision-approval.md) — Approved work order, reconstruction provenance, and prerequisite boundaries.
- [`ROADMAP_FORMAT.md`](../ROADMAP_FORMAT.md) — Canonical roadmap artifacts, feedback rows, stage authority, and structural rewrite contracts.
- [`DATA_CONTRACT.md`](../DATA_CONTRACT.md) — Persisted roadmap version, candidate, review, and publication contracts.
- [`docs/how-to/roadmap.md`](../docs/how-to/roadmap.md) — Operator-facing roadmap, candidate review, and promotion workflow.
- [`docs/implementation-plans/2-roadmap-versioned-feedback-revision-chain.md`](../docs/implementation-plans/2-roadmap-versioned-feedback-revision-chain.md) — Prerequisite routing of ordinary enrolled feedback into the immutable candidate chain.
- [`plan_tool/roadmap_candidate.py`](../plan_tool/roadmap_candidate.py) — Typed candidate operations, authority checks, and full-roadmap materialization.
- [`ROADMAP_FEEDBACK_FORMAT.md`](../ROADMAP_FEEDBACK_FORMAT.md) — Mutable ledger ownership and feedback lifecycle.
- [`plan_tool/roadmap_candidate_run.py`](../plan_tool/roadmap_candidate_run.py) — Existing inert full-roadmap candidate construction and accepted-predecessor binding.
- [`plan_tool/roadmap_candidate_review.py`](../plan_tool/roadmap_candidate_review.py) — Existing reviewer question, answer, replacement, and exact review-seal bindings.
- [`plan_tool/roadmap_version_promotion.py`](../plan_tool/roadmap_version_promotion.py) — Sole promotion path for a sealed candidate and current accepted predecessor.
- [`plan_tool/roadmap_versions.py`](../plan_tool/roadmap_versions.py) — Immutable version records and `AcceptedRoadmapHead` selector.
