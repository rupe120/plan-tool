> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Convert the TTRPG demo to assistant requests

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Convert `docs/demos/roadmap-demo.md` into an assistant-led walkthrough of the retained TTRPG scenario. Pair requests with artifacts to inspect and decisions to bring back to the reader. Preserve accepted-head authority, separate candidate review from settlement, and keep seed materialization distinct from promotion. On completion, readers can guide the existing workflow without treating a proposal or presentation request as approval to publish.

## Table of Contents

- [Summary](#summary) — Deliverable and observable result.
- [Table of Contents](#table-of-contents) — Section navigation.
- [Why](#why) — Gaps in the current teaching route.
- [Input](#input) — Contracts and dependency output.
- [Files (creates vs edits)](#files-creates-vs-edits) — The bounded documentation change.
- [Implementation](#implementation) — Requests, review points and authority boundaries.
- [Tests](#tests) — Reviewer-run documentation checks.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Existing procedural and artifact owners.
- [Applicable guardrails](#applicable-guardrails) — Scope constraints on this conversion.
- [Deferred](#deferred) — Related work outside this step.

## Why

`docs/demos/roadmap-demo.md` teaches the TTRPG workflow mainly through commands and presenter instructions. Its bare-plan audit section assumes a human-operated interactive apply walk, while its deliverables section calls for a published Artifact and a refusal-then-unlock sequence without establishing a supported unlock route. Readers need usable assistant requests that preserve the review boundaries, expose actual evidence and distinguish preparation from completed demonstration results.

## Input

- **Step 1:** Build on step 1’s assistant-led teaching outcome. Match its request → artifact → human decision pattern without copying its dark-mode content.
- **Roadmap authority:** Read `ROADMAP_FORMAT.md:Immutable candidate-version authority` and `ROADMAP_FEEDBACK_FORMAT.md:Lifecycle and ownership`. Accepted versions supply canonical content; the mutable ledger supplies reviewer input.
- **Review routes:** Use `ROADMAP_FEEDBACK_FORMAT.md:Ledger-to-candidate workflow` and `Settlement confirmation`, with `docs/how-to/roadmap.md` as the operational guide. A candidate’s stored route determines its review procedure.
- **Preparation evidence:** Read `handoffs/2026-10-21-demo-refresh.md:Outcome and scope for the new plan`. Local preparation and retained measurements do not establish a fresh model run, qualified audit convergence or publication approval.
- **Verification limits:** This step checks the runbook’s instructions and references. It does not establish model response quality or reproduce the TTRPG run.

## Files (creates vs edits)

**New files:**

- None.

**Existing files (edits only):**

- `docs/demos/roadmap-demo.md` — Make assistant requests the main route, connect them to reviewable outputs, correct conflicting procedural claims and preserve preparation and publication boundaries.

## Implementation

- **User review checkpoints.** In the TTRPG workflow, preserve roadmap review and additionally present each selected plan seed, bare plan and detail bundle for user review before its next consuming stage. Seed materialization or promotion is not approval of the seed content. The assistant links each artifact, summarizes changes and asks for corrections or continuation. Wait for the user unless explicit existing delegation covers that transition; do not infer approval from elapsed time. This changes the demo interaction, not tool enforcement.

- **Foundational logic: assistant request → inspectable artifact → human decision.** Apply this pattern across `docs/demos/roadmap-demo.md`, especially “Phase 1 — the four roadmap stages,” “Phase 2 — the review loop,” “Phase 3 — promote the draft seeds” and “Phases 4–6 — one plan to full depth.” Keep commands as supporting examples where useful; reject a second procedural policy embedded in the demo.

- **Lead with requests readers can reuse.** Include requests to prepare an isolated consuming repository, invoke the plan-tool skill on the existing concept brief, inspect the accepted roadmap, propose feedback changes, materialize selected seeds and carry one representative plan through both audit gates. Each request must identify the output to inspect and the decision the assistant must bring back.

- **Preserve the scaffold’s purpose and ordering.** In “Why the demo repo carries a scaffold” and “Phase 0b — the scaffold, authored after stage 3,” retain grounding in actual component and entity IDs. Requests must use the accepted component artifact and keep behavior design with the plans. Preserve the traceability check and its mutation checks as requirements for a future demo preparation run.

- **Teach accepted-head review explicitly.** Requests must ask the assistant to distinguish accepted content, mutable ledger items and inert candidates. `ROADMAP_FORMAT.md:Immutable candidate-version authority` remains the authority; proposing or comparing a candidate must not read as accepting it. Keep read-only inspection available before any requested mutation.

- **Separate feedback, candidate review and settlement.** In “Phase 2 — the review loop,” give each responsibility its own request and review point. Follow `ROADMAP_FEEDBACK_FORMAT.md:Ledger-to-candidate workflow` for bounded versus structural review, including whole-stack disclosure and digest confirmation where required. Follow `ROADMAP_FEEDBACK_FORMAT.md:Settlement confirmation` for receipt-bound settlement responses. Link to these owners rather than reproducing every flag and recovery branch.

- **Retain the refused-feedback demonstration with accurate limits.** In “The refused feedback row — the highest-value thing to film,” require inspection of a real settled predecessor decision before choosing the request. Ground the explanation in `plan_tool/roadmap_gates.py:check_settled_decisions` and `plan_tool/roadmap_gates.py:check_decision_records`. Distinguish a model leaving a commitment unchanged from a deterministic rejection; record whichever actually occurs. Do not claim an end-to-end promotion guarantee: `ROADMAP_FORMAT.md:Closed vocabularies` documents the candidate-promotion predecessor-check gap.

- **Remove the unsupported unlock promise.** Sweep “Phase 7 — build the four deliverables,” the capture guidance and the checklist for instructions promising that the same request succeeds after an unlock. Preserve the refusal demonstration without inventing an un-settle route or directing edits to immutable artifacts.

- **Keep seed materialization and promotion separate.** In “Phase 3 — promote the draft seeds,” requests must inspect the accepted plan mapping, materialize eligible drafts and review the promotion preview before an authorized copy. Use `docs/how-to/roadmap.md:7. Promote accepted draft seeds, or create directly from them` for procedure. An active candidate must not silently supply the seeds.

- **Use the assistant-driven audit route.** Replace the human-TTY assumption in “Phase 5 — audit the bare plan, before detail” with requests for session-directed conceptual triage under the existing directives. Preserve bare-before-detail and detail-grounded-after ordering, report paths, coverage and qualification. Keep quota-stopped results visibly incomplete and retain the authoring-only stopping point.

- **Keep preparation and publication visible.** Rework “Demo setup and outputs,” “Phase 7 — build the four deliverables” and “Execution checklist” so deliverables are requested preparation outputs, not claims of completed work. Artifact publication requires separate authorization. Do not replace checked preparation entries with new completion claims or expose private recovery material.

- **Reuse shared owners unchanged.** `docs/demos/planning-demo.md` supplies the sibling teaching pattern; `docs/how-to/roadmap.md` owns roadmap procedure; `integrations/shared/DIRECTIVES.md` owns audit and monitoring rules. Link to them. Before changing headings, search inbound anchors and internal section references; preserve or repair navigation within this file.

## Tests

This is a non-code step. The test-authoring gate keys on `change_type` and does not require a new test file for this documentation edit. No dedicated roadmap-demo test file exists; roadmap contract suites are supporting evidence, not tests of the walkthrough’s teaching quality.

### Verification (non-code step)

1. **Assistant requests expose review points** — Inspect `docs/demos/roadmap-demo.md` for a request, inspectable output and reader decision at each major transition.
2. **Canonical content stays distinct from proposals** — Compare the review requests against `ROADMAP_FEEDBACK_FORMAT.md:Ledger-to-candidate workflow` and `ROADMAP_FORMAT.md:Immutable candidate-version authority`.
3. **Settlement remains a separate operation** — Check settlement requests against `docs/how-to/roadmap.md:5. Settle a pending decision`, including receipt-bound confirmation when applicable.
4. **Refusal claims match enforcement limits** — Inspect `plan_tool/roadmap_gates.py:check_settled_decisions`, `tests/test_roadmap_gates.py` and the documented promotion gap; verify the runbook makes no broader claim.
5. **Seed preview precedes authorized promotion** — Trace the seed requests against `docs/how-to/roadmap.md:7. Promote accepted draft seeds, or create directly from them`.
6. **Audit requests preserve both gates** — Verify the session-driven route, qualified-result interpretation and quota-stop branch against `integrations/shared/DIRECTIVES.md` and `docs/how-to/pipeline/audit.md`.
7. **Links and section references remain valid** — Check local targets, inbound anchors for renamed headings and internal numbered references.
8. **Evidence and publication remain separate** — Review the deliverables and checklist for invented results, unsupported unlock instructions, automatic publication or private recovery details.
9. **The diff stays bounded** — Confirm that only `docs/demos/roadmap-demo.md` changes and that no model run or remote operation is needed to verify this conversion.

## Acceptance criteria

- The step’s deliverables show explicit user review of seeds, plans and details at the correct stage boundaries, including artifact links, change summaries and correction/continuation requests; continuation follows a user response or explicit prior delegation.
- `docs/demos/roadmap-demo.md` provides reusable assistant requests covering roadmap generation, accepted-head inspection, ledger feedback, candidate review, settlement, seed materialization and representative-plan authoring.
- Each major request identifies evidence to inspect and the decision to return to the reader.
- Candidate proposal and comparison remain distinct from acceptance; settlement follows its separate confirmed route.
- The refused-feedback section retains the settled-predecessor precondition and states the enforcement limits without promising an unsupported unlock.
- Seed materialization, preview and authorized promotion remain separate actions based on accepted content.
- Both audit gates remain visible, with incomplete quota-stopped results excluded from completion claims.
- Presentation outputs remain preparation work until actual evidence exists; Artifact publication remains separately authorized.
- Local links and section references point to their intended targets.
- The implementation diff changes only `docs/demos/roadmap-demo.md`.

## References

- [ROADMAP_FORMAT.md](../../../../ROADMAP_FORMAT.md) — Read accepted-head authority, settled-decision limits and immutable artifact rules.
- [ROADMAP_FEEDBACK_FORMAT.md](../../../../ROADMAP_FEEDBACK_FORMAT.md) — Read ledger ownership, candidate review and settlement confirmation.
- [docs/how-to/roadmap.md](../../../how-to/roadmap.md) — Use the existing inspection, settlement, feedback and seed procedures.
- [integrations/shared/DIRECTIVES.md](../../../../integrations/shared/DIRECTIVES.md) — Follow the canonical assistant-driven authoring, audit and monitoring rules.
- [docs/how-to/pipeline/audit.md](../../../how-to/pipeline/audit.md) — Interpret audit coverage, qualification and incomplete results.
- [handoffs/2026-10-21-demo-refresh.md](../../../../handoffs/2026-10-21-demo-refresh.md) — Preserve preparation evidence and publication boundaries.
- [docs/reference/documentation-style.md](../../../reference/documentation-style.md) — Review task-first structure and scanning clarity.

## Applicable guardrails

- **The plan’s “Scope guardrails,” documentation conversion:** Keep implementation inside the declared runbook; reference existing procedural owners without changing their behavior.
- **The plan’s “Scope guardrails,” consequential decisions:** Requests must bring roadmap review and publication choices back to the reader.
- **The plan’s “Out of scope,” retained scenario and evidence:** Preserve the TTRPG scenario and avoid regenerating its artifacts or rewriting historical evidence.
- **The plan’s “Scope guardrails,” private material:** Use the public preparation boundary without copying recovery contents into the runbook.

## Deferred

- `docs/demos/planning-demo.md` — Step 1 owns the sibling planning-demo conversion; use its outcome without editing it here.
- `docs/how-to/use-cases.md` and `docs/how-to/choose-a-starting-point.md` — Their learning examples belong to the plan’s separate documentation work.
- `docs/how-to/roadmap.md`, `ROADMAP_FORMAT.md` and `ROADMAP_FEEDBACK_FORMAT.md` — Reuse these authorities unchanged; shared lifecycle changes require separate intentional work.
- Full TTRPG execution, new transcripts, decks and Artifact publication — This step describes the preparation route; producing or publishing those outputs falls outside its footprint.
