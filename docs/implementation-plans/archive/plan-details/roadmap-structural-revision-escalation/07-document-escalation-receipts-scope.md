> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 7 — Document escalation receipts, scope-review handoff, and the no-write boundary

## Summary

Document the receipt-only escalation flow across the roadmap format reference, operator guides, architecture reference, testing guide, and project pointers. The primary decision is that a receipt is immutable noncanonical evidence for one feedback row, not a fifth roadmap artifact or approval for a structural change. Build on the landed contracts from steps 3–6 rather than restating their implementation. When green, readers can create or inspect a receipt, understand its `requires-scope-review` handoff, and know that neither action starts a broad revision or mutates canonical roadmap state.

## Table of Contents

- [Summary](#summary) — Reviewer-level outcome and documentation boundary.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Why the receipt boundary needs one consistent explanation.
- [Input](#input) — Landed receipt, lifecycle, and CLI contracts this step documents.
- [Files (creates vs edits)](#files-creates-vs-edits) — Documentation and drift-guard changes.
- [Implementation](#implementation) — Required documentation rules and ownership split.
- [Tests](#tests) — Documentation-contract regression coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable documentation outcomes.
- [References](#references) — Primary references for the documented contracts.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries the documentation must preserve.
- [Deferred](#deferred) — Follow-on routing and writer work outside this step.

## Why

`ROADMAP_FORMAT.md` currently distinguishes four staged artifacts, draft-seed side outputs, bounded local feedback revision, and broad re-entry, but it has no discoverable explanation for a request that is too structural for the local writer. Without a clear receipt-only route, readers can mistake evidence for a fifth canonical artifact, treat an operator-selected reason as an impact decision, or use `--from-stage` as an automatic response. This step makes the existing boundaries legible before later impact-routing work adds any broader analysis.

## Input

- **Step 3 receipt contract:** Document the landed versioned receipt schema, deterministic identity, source-freshness rule, and redaction boundary. Read names and allowed values from the implemented contract; it overrides this plan and its detail on any disagreement.
- **Step 4 lifecycle contract:** Document only the landed receipt-creation outcomes and observable immutable-evidence behavior, including which outcomes have no trusted handoff.
- **Step 6 command surface:** Document the final `--escalate-feedback` / `--escalation-reason` creation form and `--view escalations` inspection form, including creation telemetry and log-free views.
- **Existing route documentation:** Preserve the bounded route in `ROADMAP_FORMAT.md:## Local feedback revision contract`, the broad-re-entry guidance in `docs/ROADMAP_WALKTHROUGH.md:## 5. Ask for a revision with feedback`, and the plan-concept workflow in `RUNBOOK.md:## Workflow: review concept decisions and ownership (`scope-review`)`.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `ROADMAP_FORMAT.md` — Add the source-of-truth ownership for receipt evidence and a receipt-reference section that distinguishes the closed receipt schema from the four canonical artifacts.
  - `tests/test_roadmap_format.py` — Extend the format-document drift guard for the receipt schema example, documented values, command forms, and route boundary.
  - `README.md` — Add the structural-feedback route to the roadmap overview without turning it into an implementation workflow.
  - `CLAUDE.md` — Keep the terse reference-doc and roadmap architecture pointers current without duplicating the format reference.
  - `docs/ARCHITECTURE.md` — Describe the receipt selection, lifecycle, and view layers as a separate noncanonical roadmap boundary.
  - `docs/ROADMAP_WALKTHROUGH.md` — Add receipt creation and inspection to the command sequence and feedback walkthrough.
  - `RUNBOOK.md` — Explain the operator handoff from a receipt to explicit scope review, including the boundary between a handoff label and a command that edits plan scope.
  - `TESTING.md` — Add the receipt test seams and no-backend/no-write expectations for future changes to this area.

## Implementation

- **Foundational logic:** Document one receipt-only handoff for structural feedback without selecting or performing the structural work.

- **Make `ROADMAP_FORMAT.md` the schema home.** Extend its source-of-truth block and add a focused receipt section near the existing feedback-route material. Document the version-1 field set, closed values, semantic identity, source freshness, and redaction rules from the landed step 3 contract. Include a runnable safe example only if it can be validated through the real receipt parser and identity checks.

- **Keep the artifact count stable.** `ROADMAP_FORMAT.md:## What a roadmap is, and what it is not`, `ROADMAP_FORMAT.md:## Path convention`, and `ROADMAP_FORMAT.md:## Draft seeds under the roadmap slug` must continue to identify only `01-domain.md` through `04-roadmap.md` as canonical staged artifacts. Describe a receipt as immutable noncanonical evidence; do not add it to artifact tables, stage numbering, or the canonical path inventory.

- **Show the command boundary exactly once per reader level.** Document the landed creation and inspection forms in `README.md:### 0. \`roadmap\` — stage a project-sized concept`, `docs/ROADMAP_WALKTHROUGH.md:## Command sequence at a glance`, and the feedback section. Point detailed flag semantics to the command reference produced by step 6 instead of reproducing option-validation rules across these guides.

- **State the no-write rule as an observable contract.** Creation records only its declared receipt and creation lifecycle evidence. `--view escalations` is read-only and log-free, including when the evidence namespace is absent or evidence is invalid. Neither path invokes a backend, changes a canonical roadmap artifact, feedback state, seed or draft state, or Git state, and neither begins `--from-stage` re-entry.

- **Describe the handoff without inventing a route.** Explain that `requires-scope-review` is a signal for an operator to conduct explicit scope review; it is neither a complete impact set nor authorization to change a roadmap. `RUNBOOK.md:## Workflow: review concept decisions and ownership (\`scope-review\`)` remains the workflow for a known plan and selected concept IDs. Do not imply that a roadmap slug can be passed to `scope-review`, that receipt creation runs the command, or that the receipt chooses a later writer.

- **Keep the architectural layer split clear.** Add a concise receipt entry beside `docs/ARCHITECTURE.md:### Immutable roadmap evidence` that separates the opaque evidence store from the receipt contract and CLI behavior. The entry must name the receipt layer’s read/write boundary while leaving immutable-publication internals to their existing owner.

- **Make the test guide actionable.** Update `TESTING.md:## Adding a new conceptual area` or the roadmap testing guidance to direct future changes toward focused contract tests, CLI boundary tests, and no-backend assertions. Keep documentation-only verification separate from the implementation tests introduced by steps 3–6.

- **Guard the documentation against drift.** Extend the established `tests/test_roadmap_format.py:test_local_feedback_route_reference_marks_broad_reentry_boundaries` pattern. The receipt checks should derive documented closed values and the example’s validity from the landed contract, rather than pinning a second hand-maintained schema.

## Tests

- `tests/test_roadmap_format.py:test_escalation_receipt_reference_matches_landed_contract` — asserts the documented version, field inventory, closed vocabulary, command forms, and handoff token match the landed receipt and CLI contracts.
- `tests/test_roadmap_format.py:test_escalation_receipt_example_is_valid_and_identity_bound` — parses the documentation example through the real receipt contract and proves its rendered identity is valid.
- `tests/test_roadmap_format.py:test_escalation_receipt_route_preserves_local_and_broad_boundaries` — proves the format guide keeps local revision, receipt creation, log-free inspection, broad re-entry, and deferred scope review as distinct routes.

### Verification (non-code step)

This non-code step is exempt from the plan’s test-authoring gate; its substitute checks are:

1. Run `uv run pytest tests/test_roadmap_format.py -q`.
2. Compare every documented receipt field, outcome, and command form with the landed outputs from steps 3–6.
3. Verify links and headings from `README.md`, `docs/ROADMAP_WALKTHROUGH.md`, and `RUNBOOK.md` reach the intended receipt and scope-review sections.
4. Review the four canonical-artifact inventories and confirm none adds receipt evidence as a stage or canonical artifact.
5. Run `git diff --check` and confirm the diff changes only the declared documentation and drift-guard files.

## Acceptance criteria

- `ROADMAP_FORMAT.md` documents the landed closed receipt schema, identity and freshness rule, redaction boundary, and `requires-scope-review` handoff.
- The four canonical roadmap artifacts remain the only numbered or staged artifacts in every edited guide.
- `README.md` and `docs/ROADMAP_WALKTHROUGH.md` show the exact receipt creation and inspection forms and direct detailed option questions to `docs/cli/roadmap.md`.
- `RUNBOOK.md` states that a receipt does not invoke `scope-review`, select an impact route, or authorize a structural writer.
- Every edited operator-facing document states that receipt views are log-free and read-only, and that receipt creation does not start broad re-entry or a backend call.
- `tests/test_roadmap_format.py` validates the receipt reference against the landed contract and passes.
- `TESTING.md` identifies the focused receipt contract, CLI-boundary, and no-write test expectations without recommending a real backend.

## References

- [argparse — Parser for command-line options, arguments and subcommands](https://docs.python.org/3.13/library/argparse.html) — Use for the documented exclusive command forms.
- [json — JSON encoder and decoder](https://docs.python.org/3.13/library/json.html) — Use for the versioned receipt representation and canonical JSON terminology.
- [hashlib — Secure hashes and message digests](https://docs.python.org/3.13/library/hashlib.html) — Use for the receipt identity and source-digest description.
- [pytest: How to use temporary directories and files](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — Use for future receipt no-write fixtures.

## Applicable guardrails

- **The plan’s “Plan intent”** — Document one selected-row receipt and its scope-review handoff; do not present it as impact analysis or a structural edit.
- **The plan’s “Step intent”** — Keep supporting evidence discoverable without treating it as another canonical roadmap artifact.
- **The plan’s “## Out of scope”, routing and writer work** — Do not document a relation closure, broad command recommendation, patch workflow, or transaction as part of receipt handling.
- **The plan’s “## Out of scope”, local revision and broad-stage behavior** — Preserve the existing local-revision and `--from-stage` contracts as separate routes.
- **The plan’s “## Out of scope”, immutable-evidence storage** — Describe only receipt-visible behavior; do not make the documentation an alternate specification of storage internals.

## Deferred

- Impact analysis and route classification — `roadmap-escalation-impact-routing` owns relation closure, coherent snapshots, and deciding whether later work has enough evidence.
- Same-artifact structural patching — `roadmap-same-artifact-structural-revision` owns any writer that may consume a current receipt or later analysis.
- Cross-artifact structural writing — `roadmap-cross-artifact-revision-transaction` owns coordinated multi-artifact changes and recovery.
- Detailed CLI option reference — `docs/cli/roadmap.md` remains the step 6 owner; this step links to it rather than duplicating its validation table.
