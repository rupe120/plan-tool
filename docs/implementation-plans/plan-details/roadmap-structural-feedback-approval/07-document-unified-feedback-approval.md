# Step 7 — Document the unified feedback approval lifecycle and reconcile the approval work record

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Document the completed ordinary-feedback lifecycle across the roadmap format references, operator guide, architecture overview, command reference, capability catalog, and project overview. Describe one intake that produces either a bounded candidate or an inert structural proposal, with explicit approval as the only path that enables promotion. Update the documentation drift guards and regenerate `docs/cli/roadmap.md` from the live parser. On green, developers and operators can trace the lifecycle, its failure preservation rules, seed effects, and later-revision predecessor rule without treating legacy structural routes as alternatives.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the documentation outcome.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Why the public roadmap references need one current lifecycle.
- [Input](#input) — Landed contracts from steps 1–6 that the documentation reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — Documentation, generated reference, guard, and work-record changes.
- [Implementation](#implementation) — Documentation ownership, lifecycle rules, and record reconciliation.
- [Tests](#tests) — Focused drift guards and non-code verification.
- [Acceptance criteria](#acceptance-criteria) — Observable documentation and work-record results.
- [References](#references) — Current contracts that define the lifecycle.
- [Applicable guardrails](#applicable-guardrails) — Boundaries this documentation must preserve.
- [Deferred](#deferred) — Work outside this documentation step.

## Why

The current references describe the enrolled ledger-to-candidate lifecycle, but they do not yet present the structural proposal decision as part of the same ordinary feedback route. Without one current explanation, an operator can mistake a sealed candidate, an edit, or a structural receipt route for accepted-head publication, while `BACKLOG.md` #423 continues to describe work this plan completes.

## Input

- **Steps 1–2 candidate facts:** Read the landed typed operation classification and stored route evidence from `plan_tool/roadmap_candidate.py:materialize_candidate` and `plan_tool/roadmap_candidate_run.py:CandidateProposalEvidence`. The landed names and serialized fields win over wording in this plan.

- **Steps 3–5 decision and promotion facts:** Read the landed decision records from `plan_tool/roadmap_candidate_review.py` and the final promotion checks in `plan_tool/roadmap_version_promotion.py:promote_review_seal`. Preserve `plan_tool/roadmap_versions.py:AcceptedRoadmapHead` as the canonical selector.

- **Step 6 command surface:** Read `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_candidate_lifecycle`, its action-conflict checks, result renderers, and the parser registration in `plan_tool/cli/roadmap_cmd.py:register`. Generate CLI reference text from this landed parser rather than maintaining a second flag inventory.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `ROADMAP_FEEDBACK_FORMAT.md` — Document mutable-ledger ownership, proposal routing, structural decision states, and the exact effects of approval, edit, rejection, failure, and staleness.
  - `ROADMAP_FORMAT.md` — Update the immutable candidate lifecycle section so artifact authority, structural approval, promotion, seed effects, and later revision ancestry agree with the landed code.
  - `DATA_CONTRACT.md` — Document only the persisted candidate, decision, promotion, and publication facts that the implementation actually stores; retain the existing redaction boundary.
  - `README.md` — Update the roadmap capability overview and command examples to point readers to the unified ordinary-feedback route.
  - `CAPABILITIES.md` — Revise the existing roadmap capability entry to describe the completed approval behavior and its owned surfaces.
  - `docs/ARCHITECTURE.md` — Update the roadmap architecture section with the actual ownership boundary between ledger, candidate, review decision, promotion, and publication.
  - `docs/how-to/roadmap.md` — Give operators the end-to-end proposal, review, approve/edit/reject, promotion, and follow-up revision workflow.
  - `docs/cli/roadmap.md` — Regenerate the parser-derived roadmap command reference after step 6’s CLI surface lands.
  - `tests/test_roadmap_feedback_format.py` — Extend document-contract checks for ledger authority and the unified lifecycle.
  - `tests/test_roadmap_format.py` — Extend format-reference checks for immutable candidate authority and the documented lifecycle boundaries.
  - `tests/cli/test_cli_reference.py` — Keep the generated roadmap reference and its structural approval wording synchronized with the parser.
  - `BACKLOG.md` — Reconcile #423 with the completed plan and remove stale “not started” framing while retaining warranted provenance.
  - `handoffs/2026-09-22-roadmap-feedback-revision-approval.md` — Replace obsolete pickup state with the completed approval-plan result and any remaining follow-up boundary.

## Implementation

- **Describe one ordinary intake.** Make `ROADMAP_FEEDBACK_FORMAT.md` and `docs/how-to/roadmap.md` clear that reviewers submit ordinary ledger feedback and never select a structural feedback type or route. Explain that validated typed operations, not request wording, select the bounded or structural candidate path.

- **Keep proposals inert.** Across `ROADMAP_FORMAT.md`, `DATA_CONTRACT.md`, and `docs/ARCHITECTURE.md`, state that candidate creation, review, replacement, rejection, and staleness do not advance `AcceptedRoadmapHead` or rewrite canonical roadmap artifacts. Keep the existing distinction between mutable ledger input, immutable stored candidate evidence, and accepted-head selection.

- **Describe the structural decision as one exact binding.** Document the landed step 3 decision record and step 6 operator surface using the identifiers that exist after implementation. Approval must bind one reviewed candidate identity; an edit must produce a replacement requiring a fresh decision; rejection must release only the active candidate while preserving immutable history.

- **Keep promotion separate from approval.** State that approval authorizes promotion but does not itself make a version canonical. `plan_tool/roadmap_version_promotion.py:promote_review_seal` remains the promotion boundary, including its accepted-root and active-candidate freshness checks and its journaled publication effects.

- **Make failure preservation explicit.** Document the common rule that invalid output, failed gates, rejection, edit, interruption, and stale bindings must not advance the accepted head or rewrite canonical artifacts or seeds. Explain selected-ledger updates only where the landed lifecycle records them; do not imply that unselected feedback changes.

- **Cover seed effects and later revisions.** Explain the enrolled structural promotion’s seed-state effect only as the landed publication contract specifies it. State that later feedback proposals use the promoted accepted version as their predecessor, rather than a prior candidate, a live artifact, or current mutable ledger state.

- **Preserve separate routes.** Keep selector-shaped reopening, decision settlement, escalation, impact analysis, and exact-pair structural rewrite documentation distinct from ordinary ledger feedback. Do not reframe those routes as alternate ways to approve an ordinary structural proposal.

- **Use each document for its audience.** Keep schema and field details in `ROADMAP_FEEDBACK_FORMAT.md`, `ROADMAP_FORMAT.md`, and `DATA_CONTRACT.md`; keep operator sequence and commands in `docs/how-to/roadmap.md`; keep architecture ownership in `docs/ARCHITECTURE.md`; and keep `README.md` concise with links to the owning references.

- **Generate, do not hand-maintain, the CLI reference.** Regenerate `docs/cli/roadmap.md` through `plan_tool/cli_reference.py:write_reference` after the parser is final. Update `tests/cli/test_cli_reference.py` only for assertions that the generated text communicates the approved route without granting transaction authority.

- **Close the work record accurately.** Reconcile `BACKLOG.md` #423 and `handoffs/2026-09-22-roadmap-feedback-revision-approval.md` against the landed plan, tests, and lifecycle. Retain dated provenance that helps a future reader understand the decision, but remove stale current-tense work-order and status claims.

## Tests

- `test_ledger_format_documents_one_ordinary_feedback_intake` — asserts `ROADMAP_FEEDBACK_FORMAT.md` says users do not choose a structural feedback type and preserves ledger ownership.

- `test_ledger_format_distinguishes_proposal_decision_and_promotion` — asserts proposal storage and review stay inert while exact approval and promotion have separate documented roles.

- `test_roadmap_format_preserves_accepted_head_as_sole_selector` — asserts `ROADMAP_FORMAT.md` names `AcceptedRoadmapHead` as canonical authority and does not grant artifact authority to mutable or pending records.

- `test_roadmap_format_documents_structural_failure_preservation` — asserts failure, rejection, edit, and staleness remain non-publication outcomes.

- `test_data_contract_documents_only_landed_approval_records` — asserts `DATA_CONTRACT.md` names persisted approval and publication facts from the landed code without adding reviewer prose or invented fields.

- `test_roadmap_reference_documents_structural_approval_lifecycle` — asserts the generated CLI reference includes the landed structural decision surface and preserves promotion-only accepted-head authority.

### Verification (non-code step)

1. Run `uv run pytest tests/test_roadmap_feedback_format.py tests/test_roadmap_format.py tests/cli/test_cli_reference.py -q`.

2. Run `uv run python -m plan_tool.cli_reference --write`, then confirm `git diff --exit-code -- docs/cli/roadmap.md` after the intended generated update is committed.

3. Compare every documented flag and command sequence with `plan_tool/cli/roadmap_cmd.py:register` and `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_candidate_lifecycle`.

4. Compare every documented persistence claim with the landed candidate, review, promotion, and publication symbols; remove any field or lifecycle name that code does not ship.

5. Search the declared documentation files for stale wording that makes structural escalation, exact-pair rewrite, or settlement appear to be ordinary proposal approval.

6. Check relative Markdown links in the edited documents and confirm `BACKLOG.md` #423 and the handoff no longer present superseded work as current.

## Acceptance criteria

- The roadmap references describe one ordinary feedback intake that routes from validated candidate operations, not user-selected structural labels.

- The references distinguish mutable ledger input, inert candidate and review records, explicit structural approval, and `AcceptedRoadmapHead` promotion.

- The operator guide gives a complete approved route and makes clear that edit, rejection, failed validation, interruption, and staleness do not publish canonical roadmap state.

- The references state that a replacement candidate needs a fresh structural decision and that later feedback revisions start from the promoted accepted version.

- `docs/cli/roadmap.md` is generated from the final parser and `tests/cli/test_cli_reference.py` passes.

- `ROADMAP_FEEDBACK_FORMAT.md`, `ROADMAP_FORMAT.md`, and `DATA_CONTRACT.md` document only fields and lifecycle behavior that the landed implementation provides.

- `BACKLOG.md` #423 and `handoffs/2026-09-22-roadmap-feedback-revision-approval.md` accurately record the completed work and any remaining separate follow-up.

## References

- [Roadmap feedback revision and approval handoff](../../handoffs/2026-09-22-roadmap-feedback-revision-approval.md) — Read the approved reuse boundary and work-record context.

- [Roadmap feedback ledger format](../../ROADMAP_FEEDBACK_FORMAT.md) — Owns mutable reviewer input, migration, and lifecycle vocabulary.

- [Roadmap artifact format](../../ROADMAP_FORMAT.md) — Owns canonical artifact authority and candidate lifecycle placement.

- [Data contract](../../DATA_CONTRACT.md) — Read persisted roadmap candidate, review, promotion, and publication contracts.

- [Roadmap operator guide](../../docs/how-to/roadmap.md) — Owns the end-to-end operator workflow.

- [Revision-history prerequisite plan](../2-roadmap-versioned-feedback-revision-chain.md) — Read the immutable candidate-chain contract this plan extends.

## Applicable guardrails

- **The plan’s “## Scope guardrails”, one intake and one active structural decision** — Document one lifecycle without adding a second feedback type, parallel approval queue, or user route-selection concept.

- **The plan’s “## Scope guardrails”, canonical authority** — Keep `AcceptedRoadmapHead` as the only canonical selector in every reference; do not describe proposal, review, edit, rejection, or validation as publication.

- **The plan’s “## Scope guardrails”, exact approval and promotion** — Describe approval as a binding for one reviewed candidate and promotion as the only accepted-head writer.

- **The plan’s “## Scope guardrails”, failure preservation** — State non-publication outcomes consistently without inventing compensating writes or recovery behavior.

- **The plan’s “## Out of scope”** — Keep workflow authoring, voting, automatic approval, user-authored route selection, general transactions, and feedback grouping out of the documented lifecycle.

## Deferred

- Broader workflow authoring or multi-user approval design — outside the plan’s “## Out of scope” boundary.

- New persistence or diagnostic schemas — require a separate plan-level decision rather than documentation-driven expansion.
