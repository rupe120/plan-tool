> **Withdrawn 2026-10-16** — Owner correction 2026-10-16: improve existing roadmap mapping to seeds to plans; the separate opt-in plan-set layer exceeds the requested scope. Replacement effort: roadmap-plan-derivation, BACKLOG #496.
> Preserved here for history; do not edit.

# Step 6 — Document plan-set ownership and recovery and reconcile BACKLOG #496 after shipment

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Complete `ROADMAP_PLAN_SET_FORMAT.md` with the landed ownership, source-binding and recovery contracts. Update `ROADMAP_FORMAT.md`, `docs/how-to/roadmap.md` and `docs/ARCHITECTURE.md` so readers can choose the new route and understand which records it owns. Keep exact schema details in the format reference and operational recovery in the walkthrough. Reconcile `BACKLOG.md` #496 only against demonstrated shipment, retaining any remaining obligations explicitly.

## Table of Contents

- [Summary](#summary) — Deliverables and observable result.
- [Table of Contents](#table-of-contents) — Section navigation.
- [Why](#why) — Why the new route needs clear ownership and recovery guidance.
- [Input](#input) — Upstream contracts and shipment evidence.
- [Files (creates vs edits)](#files-creates-vs-edits) — Documentation changes within scope.
- [Implementation](#implementation) — Documentation ownership, recovery and backlog reconciliation.
- [Tests](#tests) — Reviewer checks for this non-code step.
- [Acceptance criteria](#acceptance-criteria) — Checkable completion conditions.
- [References](#references) — Relevant contracts and documentation guidance.
- [Applicable guardrails](#applicable-guardrails) — Boundaries on documentation and closure.
- [Deferred](#deferred) — Separate work this step does not deliver.

## Why

`ROADMAP_FORMAT.md:Immutable candidate-version authority` defines accepted roadmap authority, while `docs/how-to/roadmap.md:7. Promote accepted draft seeds, or create directly from them` explains accepted-row authoring. The derived set adds a separate record and recovery boundary without replacing either contract. Readers need to distinguish accepted scope, derived membership and individual-plan progress so an interrupted authoring run does not become an instruction to overwrite useful work or reinterpret generated plans as accepted roadmap decisions.

## Input

- **Steps 1–3’s contracts:** Read the landed record, validation and recovery behavior in `plan_tool/roadmap_plan_set_artifacts.py` and `plan_tool/roadmap_plan_set.py`. Landed identifiers, paths and state meanings take precedence over proposals in sibling details.
- **Step 4’s outcome:** Read the actual source option, supported argument combinations and result messages in `plan_tool/cli/authoring.py:register` and `plan_tool/cli/authoring.py:cmd_create`. Use `docs/cli/create.md` as the generated option reference.
- **Step 5’s evidence:** Read `docs/evidence/roadmap-plan-set-benchmark.md:Comparison contract` and the completed matched comparison. Preserve its distinction between raw output, session corrections and reviewer judgments.
- **Source authority:** `plan_tool/roadmap_versions.py:load_accepted_version` selects accepted content; `plan_tool/roadmap_versions.py:load_resolved_stored_version` verifies an explicit stored bundle. Verification alone does not establish accepted selection.
- **Closure contract:** `BACKLOG.md` #496 supplies the Outcome and scope contract. `docs/TRACKING.md:Promotion stubs` distinguishes pending plan-authored work from shipment and defines removal of unpromoted entries.

## Files (creates vs edits)

- **New files:** None. Step 1 creates `ROADMAP_PLAN_SET_FORMAT.md`; this step completes it.

- **Existing files (edits only):**
  - `ROADMAP_PLAN_SET_FORMAT.md` — Align the reference and examples with landed fields, structural checks, source binding and record ownership.
  - `ROADMAP_FORMAT.md` — Add the derived-set boundary and links without changing accepted artifact or seed contracts.
  - `docs/how-to/roadmap.md` — Add route selection, normal use, interruption recovery and remaining review duties.
  - `docs/ARCHITECTURE.md` — Describe the new modules and their relationships to accepted-version readers, authoring and individual create.
  - `BACKLOG.md` — Reconcile #496 and its live references against actual shipment; retain separately tracked work.

## Implementation

- **Foundational logic: document each authority once and recover only within its ownership boundary.** Recommend a compact ownership table in `ROADMAP_PLAN_SET_FORMAT.md`, an ordered procedure in `docs/how-to/roadmap.md` and short cross-links elsewhere. Reject repeating the full schema or recovery procedure across all documents.

- **Read the landed implementation before naming its contract.** Document the fields, states, output locations and enforcing symbols supplied by steps 1–4. The reference must name its enforcing code and explain that a documentation disagreement requires correcting the document; this step must not settle a disagreement by changing code or inventing a new state.

- **Keep the three ownership boundaries explicit.** Accepted roadmap content remains under `ROADMAP_FORMAT.md:Immutable candidate-version authority`. The derived record owns its set membership and authoring progress; `plan_tool/create.py:create_plan` retains individual authoring and registration. A derived member must not read as a newly accepted roadmap row or as replacement state for `plan_tool/roadmap_seed_state.py` and `plan_tool/roadmap_seed_manifest.py`.

- **Document the set’s authority limits in its home reference.** Explain source attribution, responsibility assignments, dependencies and unresolved prerequisites using the landed schema. Distinguish structural validation from human or model judgment about missing obligations and suitable plan boundaries. Successful authoring must not imply semantic certification or application completion.

- **Place route selection beside the existing handoff.** Extend `docs/how-to/roadmap.md:7. Promote accepted draft seeds, or create directly from them` with the explicit whole-set alternative delivered by step 4. Preserve the existing accepted-row procedure and `Direct fallback`; use actual supported commands and resolved-path behavior rather than assuming the default plans directory.

- **Separate normal use from recovery.** Show initial derivation and serial base-plan authoring first, then provide a recovery matrix grounded in step 3’s outcomes:
  - Interrupted authoring reuses the saved breakdown and pinned source.
  - Recorded completed members remain untouched, including valid operator edits.
  - Source drift stops further authoring without rebinding the saved set.
  - Conflicting destinations, missing or malformed completed outputs, and a plan written without trustworthy completion progress require explicit review.
  - Failure preserves completed outputs and prevents later member calls.

- **Make recovery advice safe on the common retry path.** Each documented condition must identify what remains on disk, what the operator inspects and which landed action is supported next. The guide must not recommend deleting progress, forcing replacement or rerunning derivation over existing outputs as a general repair. If no automated repair exists, state the limitation and require inspection instead of inventing a command.

- **Describe remaining work after base-plan creation.** Link to `docs/how-to/roadmap.md:8. Continue as an ordinary plan` and the existing bare/detail audit guidance. Explain that recorded prerequisites and eventual acceptance responsibilities still need review and fulfillment; their presence in generated content does not satisfy them.

- **Keep architecture descriptive.** Add the artifact leaf and orchestrator to `docs/ARCHITECTURE.md`, citing landed symbols and actual import relationships. Describe `plan_tool/cli/authoring.py:cmd_create` as the entry boundary and `plan_tool/create.py:create_plan` as the unchanged individual authoring owner. Do not turn this documentation step into a layering refactor.

- **Describe representation separately from fulfillment.** Structural row-attribution totality proves that every accepted plan row is named by at least one derived member, not that those members implement all its obligations. Keep the two claims distinct in format examples and the operator guide.

- **Qualify evidence claims.** Link the step 5 comparison from the relevant discussion, retaining its observed gaps and limits. Do not turn plan count, clean individual audits or repaired outputs into a general improvement claim.

- **Close #496 only when the whole contracted effort ships.** Check implementation, compatibility verification, documentation and step 5’s evidence against the source entry. If execution remains pending, retain #496 as plan-authored with the plan pointer and remaining obligations. If fully shipped, remove the entry or its promotion stub under `docs/TRACKING.md:Promotion stubs`; retain any genuine deferred follow-up in `BACKLOG.md`.

- **Sweep identifiers and wording within the declared documents.** Search for #496 references, affected headings and descriptions of one-row authoring or set completion. Update claims that conflict with the new route while preserving claims about the existing route. Check inbound anchors before renaming headings, and preserve #462, #493 and #494 as separate efforts.

## Tests

This is a `non-code` step. The test-authoring gate keys on `change_type` and does not apply here; no new test file is required.

### Verification (non-code step)

1. `verify_documented_contract_matches_landed_owners` — Compare documented fields, states, paths, flags and symbols with steps 1–4’s landed modules and parser declarations.
2. `verify_plan_set_examples_parse` — Feed each complete set-record example through the real parser supplied by step 1.
3. `verify_plan_set_examples_round_trip` — Render and reparse each complete example, asserting record equality.
4. `verify_plan_set_examples_pass_structural_checks` — Validate examples against their declared pinned source inventory and destination inputs; reuse step 1’s checks in `tests/test_roadmap_plan_set_artifacts.py`.
5. `verify_recovery_advice_preserves_owned_and_unrelated_outputs` — Trace every recovery-matrix row against step 3’s behavior and `tests/test_roadmap_plan_set.py`, including source drift and the completion-write gap.
6. `verify_existing_roadmap_contracts_remain_accurate` — Run `tests/test_roadmap_format.py` and review the existing accepted-row instructions for unintended changes.
7. `verify_links_and_symbols_point_to_real_targets` — Check relative links, section anchors and cited symbols across the five edited documents; confirm newly written citations use symbolic anchors.
8. `verify_backlog_closure_matches_shipment` — Compare #496’s disposition with its scope contract and step 5’s evidence; confirm independent entries retain their own status.
9. `verify_required_suite_passes` — Run the plan’s `uv run pytest tests/ -q -n auto` backstop without invoking a real backend.

## Acceptance criteria

- The diff changes only the five declared documentation files.
- `ROADMAP_PLAN_SET_FORMAT.md` names the landed schema and enforcing symbols, and distinguishes accepted roadmap authority, derived-set ownership and individual-plan authoring.
- Complete set-record examples parse, round-trip and pass structural checks with their documented inputs.
- `docs/how-to/roadmap.md` provides supported initial-use and retry procedures, with explicit handling of source drift, completed outputs, collisions and ambiguous completion.
- The existing accepted-row route and direct fallback remain documented accurately.
- `docs/ARCHITECTURE.md` describes the landed module relationships without proposing new code behavior.
- Documentation distinguishes authored base plans from satisfied prerequisites, reviewed completeness and fulfilled application acceptance.
- #496 remains plan-authored while contracted work is pending, or is removed only after full shipment; remaining work has an explicit record.
- Links and cited symbols point to real targets, and the required suite passes.

## References

- [BACKLOG.md](../../../BACKLOG.md) — Read #496 for the shipment contract and neighboring entries for separate scope.
- [ROADMAP_FORMAT.md](../../../ROADMAP_FORMAT.md) — Read accepted-version authority and existing seed provenance before describing the derived boundary.
- [docs/how-to/roadmap.md](../../how-to/roadmap.md) — Preserve the accepted-row handoff and ordinary-plan continuation.
- [docs/ARCHITECTURE.md](../../ARCHITECTURE.md) — Match the existing descriptive module documentation.
- [docs/evidence/roadmap-plan-set-benchmark.md](../../evidence/roadmap-plan-set-benchmark.md) — Ground claims in the matched comparison and its limits.
- [docs/TRACKING.md](../../TRACKING.md#promotion-stubs) — Apply the pending-versus-shipped backlog rules.
- [docs/reference/documentation-style.md](../../reference/documentation-style.md) — Use ownership tables, ordered procedures and separate recovery guidance.
- [integrations/shared/DIRECTIVES.md](../../../integrations/shared/DIRECTIVES.md) — Reference the existing bare/detail gates without redefining them.

## Applicable guardrails

- **The plan’s “## Scope guardrails”, structural enforcement boundary:** Document what the shipped checks establish and leave content judgments with their existing reviewers.
- **The plan’s “## Out of scope”, authority and compatibility boundaries:** Keep documentation descriptive; do not introduce new authority, approval or execution behavior through recovery instructions.
- **The plan’s “## Out of scope”, separate follow-on work:** Preserve the independent tracking and readiness of adjacent efforts when reconciling `BACKLOG.md`.
- **The source contract’s “Verification”, evidence limits:** Use step 5’s retained comparison to qualify claims; documentation must not substitute for missing shipment evidence.
- **The source contract’s “Stop / defer”, unresolved evidence:** Explain remaining prerequisites without choosing mechanisms that depend on unknown results.

## Deferred

- Cross-plan review, shared-context admission and prerequisite status projection — `BACKLOG.md` #462, #493 and #494 own these separate efforts.
- Changes to accepted-row lifecycle owners in `plan_tool/roadmap_seed_state.py` and `plan_tool/roadmap_seed_manifest.py` — reuse their contracts unchanged; documenting derived membership does not require changing shared authority.
- New recovery commands or automatic adoption of ambiguous outputs — this step documents step 3’s supported behavior; additional recovery capability requires separately scoped work.
