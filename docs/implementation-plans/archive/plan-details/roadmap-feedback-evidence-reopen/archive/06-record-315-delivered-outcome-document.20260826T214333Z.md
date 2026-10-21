# Step 6 — Record #315's delivered outcome and document the recovery boundary for #242

## Summary

Update the six roadmap operator, architecture, and backlog documents to describe the shipped bounded evidence-recovery workflow. Keep it separate from ordinary reviewer lifecycle actions, stage runs, structural rewrites, and #242’s later retention redesign. Use step 5’s landed command forms and outcomes as the source for user-facing wording, with `docs/cli/roadmap.md` remaining the flag reference. On green, no selected document claims that an evidence-blocked response requires a raw edit, and #242 has a clear, limited recovery input.

## Table of Contents

- [Summary](#summary) — The documentation outcome and its boundary.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — The stale claims this step removes.
- [Input](#input) — The landed workflow and existing documentation contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — The narrative and backlog files to update.
- [Implementation](#implementation) — The recovery story, architecture boundary, and backlog closure.
- [Tests](#tests) — Existing drift checks and non-code verification.
- [Acceptance criteria](#acceptance-criteria) — Observable documentation and backlog results.
- [References](#references) — CLI option-reference guidance.
- [Applicable guardrails](#applicable-guardrails) — Scope limits for the documentation.
- [Deferred](#deferred) — Work that remains with #242 and later designs.

## Why

`BACKLOG.md` #315 and the linked `BUG_BACKLOG.md` incident currently say that a response-bearing feedback row has no supported reopen path and requires a raw `proposed_response` edit. After step 5 lands the bounded workflow, those statements become false and would steer operators around the history, confirmation, and recovery safeguards. #242 must record the delivered recovery boundary as an input without treating the narrower feature as its broader retention redesign.

## Input

- **Step 5 operator workflow:** Use step 5’s landed fixed-root retirement, documented-version-1 archive import, reopen, and recovery command forms, exclusive-mode rules, confirmations, safe terminal outcomes, and review-view wording. Its implementation and generated `docs/cli/roadmap.md` output override flag names or result names proposed by this detail.

- **Existing route boundary:** `RUNBOOK.md:### Record structural feedback without revising the roadmap` and `docs/ROADMAP_WALKTHROUGH.md:### Record structural feedback, then analyze its current route` define the separate receipt, analysis, and structural-rewrite flow. Preserve their exact-pair and no-fallback boundaries.

- **Selection and publication anchors:** `plan_tool/roadmap_escalation_selection.py:select_receipt_feedback()` expresses ordinary already-responded protection, while `plan_tool/roadmap_revision_publish.py:roadmap_writer_guard()` is the existing guarded publication seam. Document the landed narrow exception without describing it as a general selection change.

- **Future retention work:** `BACKLOG.md` #242 and `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md:## Ordered route` retain #242’s separate re-grounding and audit conditions.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `RUNBOOK.md` — Add a concise operator recovery procedure near `### Record structural feedback without revising the roadmap`, including the safe response to a recoverable terminal-log outcome and a link to the generated CLI reference.
  - `docs/ROADMAP_WALKTHROUGH.md` — Distinguish ordinary reviewer reopening from the separate evidence-recovery workflow in `## 5. Ask for a revision with feedback`.
  - `docs/ARCHITECTURE.md` — Extend `### Immutable roadmap evidence` and the roadmap ownership description with the landed retirement, reopen-admission, guarded-publication, recovery, and redacted-review boundaries.
  - `BACKLOG.md` — Replace #315’s open proposal with a concise delivered-outcome record and update #242 to name the landed recovery contract as a redesign input.
  - `BUG_BACKLOG.md` — Remove the stale claim that the incident leaves rows with no supported recovery path while preserving the evidence-schema incident and its separate #313 follow-up.
  - `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md` — Update `## Real-world evidence source` and ordered route item 3 so #242 consumes #315’s delivered boundary without implying that retention work has shipped.

## Implementation

- **Document one bounded recovery rule.** Explain that recovery handles an eligible response whose supporting immutable evidence is unusable through the landed dedicated workflow. It preserves response and redacted reopen history, uses explicit confirmation where required, remains backend-free, and can recover only the bound terminal-log completion after publication.

- **Keep ordinary review separate.** In `docs/ROADMAP_WALKTHROUGH.md:## 5. Ask for a revision with feedback`, retain the reviewer-owned lifecycle path, but stop presenting a manual state change or clearing `proposed_response` as the remedy for evidence failure. State that a ledgered clear does not restore ordinary eligibility; only the bounded reopen’s recorded fresh attempt does. Point operators to that workflow instead.

- **Keep existing routes closed.** In `RUNBOOK.md` and `docs/ROADMAP_WALKTHROUGH.md`, state that recovery is not a local revision, structural rewrite, `--from-stage` rerun, general re-escalation, or feedback editor. Do not weaken the existing structural writer’s exact-pair, selected-artifact, and no-transaction limits.

- **Use one flag authority.** Give `RUNBOOK.md` enough command context to guide the sequence, but direct complete option syntax, defaults, and validation to the landed `docs/cli/roadmap.md`. Do not duplicate a full option inventory across narrative guides.

- **Describe the architecture by responsibility.** In `docs/ARCHITECTURE.md:### Immutable roadmap evidence`, place fixed-root retirement evidence, the one documented archive import, reopen admission, guarded publication, recovery, and the safe review projection on their respective sides of the existing selection and writer boundaries. Explain that `plan_tool/roadmap_view.py:render_decision_ledger()` exposes only safe persisted reopen metadata, not response text, evidence bytes, or attestation prose.

- **Close #315 without erasing its design input.** Replace `BACKLOG.md` #315’s future-tense scope contract with a dated delivered-outcome record that links the plan and its verification. Remove stale claims such as “no reopen mechanism exists,” but retain the boundary that ordinary already-responded rows do not become generally eligible.

- **Keep #242 deliberately incomplete.** Update `BACKLOG.md` #242 and `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md:## Ordered route` to name #315’s bounded recovery and preserved history as inputs. Leave #242’s receipt-preflight, re-grounding, redesign, and fresh-audit conditions intact; do not assign #315 implementation work to an ambiguous future #242 step.

- **Preserve the bug’s actual owner.** In `BUG_BACKLOG.md:### Version-1 roadmap evidence receipts appeared through the CLI escalation path after the schema lock landed, contradicting the retirement plan's own guarantee`, replace only the stale no-recovery assertion. Keep the incident’s evidence, unresolved cause, and #313 direction separate from #315’s delivered operator recovery.

- **Sweep the claim class before closing.** Search the declared documents by identifier (`#315`, `#242`) and by vocabulary (`no reopen mechanism`, `raw hand-edit`, `already-responded`, `reissue`, `version-1 archive`, and `recovery`). Resolve each stale statement or record why it remains accurate in its local context.

## Tests

- **Test-authoring exemption:** This `non-code` step does not trigger the plan’s feature/refactor test-authoring gate; do not add a test file solely for documentation wording.

- `tests/test_roadmap_format.py::test_structural_rewrite_route_guidance_sweep_covers_every_named_public_guide` — Existing structural-route guidance remains exact-pair and non-transactional after a separate recovery procedure is documented.

- `tests/test_roadmap_format.py::test_architecture_reference_assigns_baseline_publication_to_writers_and_admission_to_readers` — The updated architecture keeps reader admission and writer publication responsibilities separate.

- `tests/cli/test_cli_reference.py::TestCliReferenceDrift::test_every_generated_file_matches_disk` — The step 5 CLI reference remains generated from the landed parser rather than contradicted by a hand-maintained flag list.

### Verification (non-code step)

1. Run `uv run pytest tests/test_roadmap_format.py tests/cli/test_cli_reference.py -q`.

2. Compare every command example and terminal outcome in the changed narrative docs with step 5’s landed `docs/cli/roadmap.md`.

3. Sweep the six declared documents by #315/#242 identifiers and recovery vocabulary; confirm no statement says that an evidence-blocked response can be recovered only through a raw edit, a ledgered clear restores ordinary eligibility, or arbitrary history paths are importable.

4. Follow every changed Markdown link and heading reference, then run `git diff --check`.

## Acceptance criteria

- `RUNBOOK.md` gives an operator a bounded recovery sequence and directs complete flag details to `docs/cli/roadmap.md`.

- `docs/ROADMAP_WALKTHROUGH.md` distinguishes ordinary reviewer lifecycle actions from evidence recovery and does not recommend clearing a response to bypass evidence failure.

- `docs/ARCHITECTURE.md` describes the landed recovery as a narrow admission and guarded-publication path with persisted redacted review output and one documented archive import, not a broad roadmap writer.

- `BACKLOG.md` #315 is a delivered-outcome record, and its former no-reopen proposal text is absent.

- `BACKLOG.md` #242 and `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md` name #315’s shipped contract as an input while retaining #242’s separate redesign gate.

- `BUG_BACKLOG.md` preserves the evidence-schema incident and #313 direction but no longer claims there is no supported recovery path.

- The listed focused tests pass, all edited links resolve, and `git diff --check` passes.

## References

- [argparse — Parser for command-line options, arguments and subcommands](https://docs.python.org/3.13/library/argparse.html) — Use the generated CLI reference as the operator-facing representation of the parser’s exclusive recovery actions.

## Applicable guardrails

- **Plan’s “## Plan intent”** — Describe recovery as preserving history and ordinary already-responded protection; do not frame it as an unrestricted eligibility bypass.

- **Plan’s “## Step intent”** — Limit this step to documentation and backlog alignment for #315 and the future #242 boundary.

- **Plan’s “## Out of scope”** — Do not document a general feedback editor or imply that ordinary evidence issuance now has a recovery route.

## Deferred

- Roadmap revision retention #242 — Its broader retention design remains separate until its own re-grounding conditions are met.

- Additional evidence-failure recovery routes — Any route beyond the landed bounded workflow needs its own scoped design rather than an expanded narrative promise.
