> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 11 — Document the ledger-to-candidate workflow and remove ordinary embedded-feedback and selector guidance

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Document the completed ledger-based roadmap feedback lifecycle across the roadmap references and create `ROADMAP_FEEDBACK_FORMAT.md` as the operator-facing contract for the mutable ledger. Update `ROADMAP_FORMAT.md`, `DATA_CONTRACT.md`, `README.md`, `CAPABILITIES.md`, `CLAUDE.md`, `docs/ARCHITECTURE.md`, `docs/cli/roadmap.md`, and `docs/how-to/roadmap.md` so they describe the same selector-free ordinary workflow. The key decision is that ordinary reviewer feedback begins with eligible ledger items and produces an inert root-bound candidate; artifact selectors remain only where their separate structural or legacy routes still own them. On green, developers and operators can follow one accurate workflow, copied format examples remain checked against landed contracts, and ordinary embedded-feedback guidance is gone.

## Table of Contents

- [Summary](#summary) — Reviewer-level outcome of the documentation sweep.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Why the existing documentation now points at the wrong feedback authority.
- [Input](#input) — Landed lifecycle contracts and documentation sources this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — Documentation and drift-test footprint.
- [Implementation](#implementation) — Ledger workflow, documentation ownership, and removal sweep.
- [Tests](#tests) — Named documentation-contract checks.
- [Verification (non-code step)](#verification-non-code-step) — Checks appropriate for this documentation-only change.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Serialization and validation references behind the documented contract.
- [Applicable guardrails](#applicable-guardrails) — Authority and scope limits for this documentation step.
- [Deferred](#deferred) — Work intentionally outside the documentation sweep.

## Why

The current references describe ordinary feedback as an embedded artifact row selected by `ARTIFACT:FEEDBACK_ID`, including a local live-artifact revision path. Steps 1 through 10 replace that path with a reviewer-owned ledger, an exact root/source batch, and an inert candidate lifecycle. Leaving both stories in public and developer documentation would invite operators to use an authority path that the command surface no longer accepts and would hide the separation between mutable feedback and canonical roadmap artifacts.

## Input

- **Steps 1 through 10 lifecycle:** Read the landed contracts from `plan_tool/roadmap_feedback_ledger.py`, `plan_tool/roadmap_feedback_ledger_run.py`, `plan_tool/roadmap_candidate_context.py`, `plan_tool/roadmap_candidate.py`, `plan_tool/roadmap_candidate_run.py`, `plan_tool/roadmap_candidate_review.py`, `plan_tool/roadmap_version_promotion.py`, and `plan_tool/cli/roadmap_cmd.py`. The landed names, command arguments, result values, and persisted fields win over this detail and earlier step proposals.

- **Accepted-head authority:** Preserve `plan_tool/roadmap_versions.py:AcceptedRoadmapHead`, `plan_tool/roadmap_versions.py:load_accepted_version`, `plan_tool/roadmap_version_promotion.py:promote_review_seal`, and `plan_tool/roadmap_decision_settlement_enrolled.py:run_enrolled_decision_settlement` as the documented canonical-content selector and accepted-head writers.

- **Existing documentation guard:** Extend `tests/test_roadmap_format.py` around `_immutable_candidate_version_reference_block`, `test_immutable_candidate_version_reference_matches_landed_authority_contract`, and the existing cross-document guide maps instead of starting an unrelated documentation test pattern.

- **CLI reference source:** Treat `plan_tool/cli/roadmap_cmd.py:register` and `plan_tool/cli/roadmap_cmd.py:cmd_roadmap` as the source for ordinary command spelling and exclusivity. Keep `docs/cli/roadmap.md` aligned with the parser after step 10’s selector-free route lands.

## Files (creates vs edits)

- **New files:**
  - `ROADMAP_FEEDBACK_FORMAT.md` — Define the mutable feedback-ledger file, its ownership boundary, lifecycle vocabulary, migration boundary, candidate-batch relationship, and operator-safe examples.
  - `tests/test_roadmap_feedback_format.py` — Check the new format reference against the landed ledger parser, renderer, and public workflow contract.

- **Existing files (edits only):**
  - `ROADMAP_FORMAT.md` — Replace ordinary embedded-feedback and fixed-selector lifecycle guidance with the ledger-to-candidate authority map; cross-link the ledger format rather than duplicating its schema.
  - `DATA_CONTRACT.md` — Update roadmap feedback and candidate lifecycle event documentation to match the landed redacted records; remove obsolete bounded stage-feedback delivery claims.
  - `README.md` — Update the roadmap overview and command examples to direct ordinary feedback through the ledger lifecycle.
  - `CAPABILITIES.md` — Update the `architecture-roadmap` capability’s surfaces and behavior description for the ledger, batch candidate, review, and promotion chain.
  - `CLAUDE.md` — Update the terse architecture and reference-document pointers so future development sessions find the correct workflow without copying the full contract.
  - `docs/ARCHITECTURE.md` — Describe responsibility boundaries among ledger persistence, candidate storage, review, promotion, and the command layer.
  - `docs/cli/roadmap.md` — Reflect the selector-free ordinary lifecycle flags, their required inputs, and their exclusivity rules.
  - `docs/how-to/roadmap.md` — Replace the embedded-feedback revision walkthrough with the operator sequence from ledger edit or migration through candidate review and promotion.
  - `tests/test_roadmap_format.py` — Replace obsolete embedded-feedback assertions and add a focused cross-document sweep for the new authority and retained special-purpose selector routes.

## Implementation

- **Make `ROADMAP_FEEDBACK_FORMAT.md` the schema home for mutable reviewer input.** Follow the root-level format-document family’s source-of-truth banner convention, naming the landed ledger parser, renderer, and validation anchors from `plan_tool/roadmap_feedback_ledger.py`; state that code wins on disagreement. Document the human-edited ledger shape, closed lifecycle values, target binding and stale-target behavior, explicit legacy migration, and the fact that immutable roadmap artifacts do not carry mutable reviewer feedback.

- **Keep schema facts in one home.** Put field inventories, examples, and editing rules for the ledger only in `ROADMAP_FEEDBACK_FORMAT.md`. In `ROADMAP_FORMAT.md`, `README.md`, `docs/how-to/roadmap.md`, and `docs/cli/roadmap.md`, describe the workflow and link to the format reference instead of restating ledger field lists.

- **Document one ordinary workflow.** Across the public references, make the normal sequence clear: enroll or explicitly migrate when required; edit validated reviewer-owned ledger items; run the selector-free candidate proposal; inspect or answer the active candidate’s review requirement when present; then promote only an exactly sealed active candidate. Explain that an ordinary proposal snapshots eligible items and the current roadmap-derived context into one batch, then produces an inert candidate rather than changing an accepted artifact.

- **Document the two-call settlement confirmation.** Describe the exact operator sequence step 7 and step 10 land: a settlement that would stale an active candidate returns `confirmation-required` and prints a confirmation-evidence receipt's exact final name; the operator (or a frontend) runs `--respond-decision-settlement RECEIPT_FINAL` with a yes/no value in a separate invocation to bind and apply the response. State plainly that this is non-interactive by design — no prompt, no `-y` shortcut — so it works the same from a script, a container, or a human at a terminal.

- **Preserve the authority split.** State consistently that `AcceptedRoadmapHead` selects canonical artifact content, the ledger is mutable reviewer input, and candidate, review, and promotion records cannot substitute later ledger state. Document that an unrelated ledger edit does not invalidate already recorded evidence, while a changed processing pair or changed admitted item refuses candidate storage without consuming the reviewer edit.

- **Remove the obsolete ordinary route by vocabulary and identifier.** Sweep every in-scope document and `tests/test_roadmap_format.py` for `--revise-feedback`, ordinary `ARTIFACT:FEEDBACK_ID` proposal wording, selected embedded feedback rows, and claims that ordinary feedback can overwrite live artifacts. Remove or rewrite each ordinary-use site. Retain selector language only for routes that still own it after step 10, such as structural evidence, decision settlement, escalation, reopening where applicable, and legacy compatibility boundaries.

- **Keep special routes distinct from ordinary feedback.** Do not make the new documentation imply that all selector-shaped inputs disappear. `plan_tool/cli/roadmap_cmd.py:cmd_roadmap` still owns separate structural and decision routes, and the references must identify those as separate operations rather than alternate ways to run ordinary ledger feedback.

- **Update architecture and capability ownership, not implementation mechanics.** In `docs/ARCHITECTURE.md` and `CAPABILITIES.md`, name each landed module family’s responsibility: ledger contract and mutation, batch construction, candidate materialization and storage, review lifecycle, promotion, and CLI dispatch. Do not turn either document into a duplicate API reference.

- **Keep `CLAUDE.md` terse.** Update its reference-doc and architecture pointers for the new root-level format document and lifecycle boundary. Point readers to `ROADMAP_FEEDBACK_FORMAT.md` and `ROADMAP_FORMAT.md` for detail rather than copying field names or workflow branches into session guidance.

- **Make the CLI page parser-grounded.** Update `docs/cli/roadmap.md` only from the options registered by `plan_tool/cli/roadmap_cmd.py:register`; document conflict and confirmation rules that the command actually enforces. Do not leave a selector-form ordinary proposal example after the CLI route is removed.

- **Test examples as executable contract material.** In `tests/test_roadmap_feedback_format.py`, parse each machine-readable worked example with the landed ledger loader, render it through the ledger renderer, and assert the parsed value round-trips. Where an example represents a current eligible item or a stale item, validate it through the landed eligibility or target-checking entry point rather than asserting prose alone.

- **Use the existing format guard for the cross-document sweep.** In `tests/test_roadmap_format.py`, assert the authority statements and retained selector exceptions across all declared documentation files. Keep the assertions scoped to ordinary feedback so a valid structural selector does not make the removal criterion impossible.

## Tests

- `test_ledger_format_examples_parse_and_round_trip` — `ROADMAP_FEEDBACK_FORMAT.md` examples parse through the landed ledger contract and render back to the same ledger value.

- `test_ledger_format_example_uses_landed_lifecycle_vocabulary` — Every documented lifecycle value and required record field matches the ledger’s landed closed vocabulary.

- `test_ledger_format_explains_mutable_ledger_without_artifact_authority` — The new reference states that ledger edits do not select, enroll, advance, or rewrite canonical roadmap artifacts.

- `test_ledger_format_documents_explicit_legacy_migration_boundary` — The migration example and guidance require the landed explicit migration route and do not present embedded feedback as a second writable source.

- `test_ledger_format_documents_batch_snapshot_and_unrelated_edit_preservation` — The reference distinguishes admitted-item and processing-pair refusal from unrelated later ledger edits.

- `test_ordinary_feedback_documentation_uses_selector_free_candidate_proposal` — `ROADMAP_FORMAT.md`, `README.md`, `CAPABILITIES.md`, `docs/ARCHITECTURE.md`, `docs/cli/roadmap.md`, and `docs/how-to/roadmap.md` direct ordinary feedback to the landed selector-free proposal route.

- `test_ordinary_embedded_feedback_guidance_is_removed_but_special_selector_routes_remain` — The documentation sweep removes ordinary embedded-feedback selector guidance while preserving documented structural and settlement routes that still require selectors.

- `test_roadmap_format_authority_block_matches_landed_ledger_candidate_lifecycle` — The replacement for `_immutable_candidate_version_reference_block` cites the landed selector, ledger, batch, review, and promotion anchors without naming obsolete selector-bound candidate behavior.

### Verification (non-code step)

1. Run `uv run pytest tests/test_roadmap_format.py tests/test_roadmap_feedback_format.py -q`.

2. Run the repository’s CLI-reference verification for `docs/cli/roadmap.md` so the generated option documentation matches `plan_tool/cli/roadmap_cmd.py`.

3. Search the declared documentation files for obsolete ordinary-route vocabulary and inspect every remaining selector match to confirm it belongs to a retained special-purpose route.

4. Check every new or changed markdown link, including the new `ROADMAP_FEEDBACK_FORMAT.md` links, and confirm headings still match their inbound anchors.

5. Compare each command example in `README.md`, `docs/cli/roadmap.md`, and `docs/how-to/roadmap.md` with the parser’s registered options and required argument combinations.

## Acceptance criteria

- `ROADMAP_FEEDBACK_FORMAT.md` exists, names the landed ledger contract as its enforcing source, and contains parseable, round-trippable worked examples.

- The new format reference identifies the ledger as mutable reviewer input and does not describe it as canonical artifact content or an accepted-head selector.

- `ROADMAP_FORMAT.md` links to `ROADMAP_FEEDBACK_FORMAT.md` for ledger schema details and documents the ordinary ledger-to-batch-to-inert-candidate lifecycle.

- The ordinary workflow documentation does not advertise `--revise-feedback` or an ordinary candidate proposal that takes an embedded-artifact `ARTIFACT:FEEDBACK_ID` selector.

- Documentation retains selector requirements for routes that still own them and does not describe those routes as ordinary ledger feedback alternatives.

- `docs/cli/roadmap.md` matches the options and exclusivity behavior registered by `plan_tool/cli/roadmap_cmd.py:register`.

- `CAPABILITIES.md` and `docs/ARCHITECTURE.md` name the landed ledger and candidate lifecycle modules with responsibility boundaries that agree with the code.

- `CLAUDE.md` links future developers to the new reference without duplicating its schema.

- `uv run pytest tests/test_roadmap_format.py tests/test_roadmap_feedback_format.py -q` passes.

## References

- [Pydantic Models — strict models, frozen records, and forbidden extra fields](https://docs.pydantic.dev/latest/concepts/models/)  
- [PyYAML Documentation — safe YAML loading and deterministic dumping controls](https://pyyaml.org/wiki/PyYAMLDocumentation)  
- [Python `json` — stable serialization options for immutable snapshot evidence](https://docs.python.org/3.13/library/json.html)  
- [RFC 8785 — JSON Canonicalization Scheme for reproducible JSON identities](https://www.rfc-editor.org/rfc/rfc8785.html)  

## Applicable guardrails

- **The plan’s “Plan intent” and “Scope guardrails,” authority boundary** — Document the ledger as mutable reviewer input and retain `AcceptedRoadmapHead` as the only canonical-artifact selector; this step must not present documentation as granting any new writer authority.

- **The plan’s “Scope guardrails,” candidate evidence boundary** — Describe a candidate as bound to its root, direct source, and immutable batch evidence. The documentation must not imply that promotion or review rereads live eligibility or can consume later reviewer edits.

- **The plan’s “Scope guardrails,” publication boundary** — Keep candidate storage, review actions, and promotion separate from artifact rewriting in every workflow description.

- **The plan’s “Out of scope”** — Do not document a broader approval protocol, automatic retargeting, concurrent candidate branches, new derived-feedback families, or a general editing interface beyond the ledger and focused lifecycle actions.

## Deferred

- Structural-feedback classification and broader review protocols — Remain outside this plan’s documented ordinary ledger workflow and retain their existing route-specific documentation.
