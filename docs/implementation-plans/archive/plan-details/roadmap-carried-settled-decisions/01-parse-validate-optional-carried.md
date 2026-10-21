> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Parse the optional carried-decision block from the recorded Roadmap brief through the existing source-admission path

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Parse one optional, closed carried-decision block from the brief supplied through the existing `--from-existing` path. Keep `source.json` limited to its current brief path and digest, including on first recording and confirmed same-path rebind. On green, downstream steps receive validated, typed carried decisions from the current accepted brief without requiring a caller to edit an internal record.

## Table of Contents

- [Summary](#summary) — The step outcome and main design choice.
- [Table of Contents](#table-of-contents) — Quick links to this detail.
- [Why](#why) — Why Roadmap needs an approved-decision input.
- [Input](#input) — The persisted source contract this step extends.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed by this step.
- [Implementation](#implementation) — Source parsing, persistence, and lifecycle rules.
- [Tests](#tests) — Focused parser and orchestration coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Contracts and scope evidence to consult.
- [Applicable guardrails](#applicable-guardrails) — Scope boundaries that bind this work.

## Why

`plan_tool/roadmap_source.py:read_recorded_brief_source` currently proves only which brief Roadmap accepted. Roadmap therefore has no fail-closed, typed place to receive approved upstream decisions, and later stages cannot distinguish a confirmed upstream choice from a decision they made themselves. Add the smallest persisted input that carries only the facts needed for inherited decision rows, while retaining the established source-admission and rebind guarantees.

## Input

- **Recorded source record:** `plan_tool/roadmap_artifacts.py:brief_source_path` identifies `source.json`; `plan_tool/roadmap_source.py:RecordedBriefSource` exposes its raw bytes, resolved brief path, source digest, and optional decoded-text brief digest. The brief itself is the new block's input.
- **Source lifecycle:** `plan_tool/roadmap.py:_resolve_brief_path`, `_write_brief_source`, and `_run_roadmap` own source selection, admission, first-write persistence, and confirmed rebind replacement.
- **Future consumer boundary:** step 2 defines the Roadmap artifact representation, step 3 owns citation and anchor enforcement, and step 4 owns stage routing. This step supplies only validated source-side records and confirmed citation targets.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_source.py` — Parse the one closed block from decoded brief text into typed carried decisions and confirmed answers.
  - `plan_tool/roadmap.py` — Parse the block from the selected brief before stage work while preserving the existing `source.json` writer and admission order.
  - `tests/test_roadmap_source.py` — Cover valid, absent, malformed, and closed-shape source records.
  - `tests/test_roadmap.py` — Cover initial persistence and confirmed rebind replacement without artifact, feedback, or seed mutation.

## Implementation

- **Use the existing caller path.** The optional `## Carried decisions` heading in the selected brief contains exactly one fenced `json` object. Its only top-level members are `confirmed_answers` and `decisions`. Each confirmed answer has `id`, `answer`, and `status: confirmed`; each decision has `id`, `owner`, `anchor`, `chosen_option`, and `source`, where `source` names one confirmed answer id and `chosen_option` exactly equals that answer. Optional `rationale` and `rejected_alternatives` on a decision carry only upstream-stated deliberation; each alternative has an option and the reason it lost. The owner is one of the four established artifact keys. The absence of the heading yields empty collections. A connector may generate this generic brief block, but Plan-tool reads only the committed brief supplied through `--from-existing`.

- **Reject unsupported shapes at the brief boundary.** The new brief-block parser raises `RoadmapSourceError` before a stage call for duplicate or malformed headings/fences, invalid JSON or collection shapes, missing or blank required values, unknown fields, duplicate ids, unsupported owners, unresolved citations, unconfirmed answers, and answer/option mismatch. Do not accept free-form prose, positional references, question menus, source paths, or arbitrary metadata as alternate input.

- **Keep absence compatible.** A brief without the block yields no carried decisions and retains current handwritten-brief behavior. Do not treat absence as a legacy or changed source baseline.

- **Preserve source-record fidelity.** Keep `RecordedBriefSource.source_bytes` and `source_digest` bound to the exact raw `source.json` bytes. The block parser reads the selected decoded brief and never rewrites the source record.

- **Keep recording unchanged.** `_write_brief_source` continues to persist only the path and digest of the selected brief after the first successful artifact publication. The admitted block is recoverable from that same digest-bound brief on later stage runs; an initial failed stage still leaves no `source.json`.

- **Keep source-admission precedence.** A changed or legacy brief without explicit confirmation refuses before the new block parser runs. `accepted-rebind` retains its existing path/digest replacement and stage-selection behavior; parsing the newly accepted brief cannot authorize artifact, feedback, or seed mutation. Step 3 revalidates inherited rows before a later publication.

- **Reuse the existing lifecycle owners unchanged.** Keep `_resolve_brief_path` responsible for path identity and `read_brief_text` responsible for decoded-text reads. `plan_tool/roadmap_impact_snapshot.py:_capture_recorded_brief_digests` remains a reader of the source contract and needs no new source-authority or lifecycle branch in this step.

- **Keep the source module a leaf.** `plan_tool/roadmap_source.py` may continue to import only `plan_tool.roadmap_artifacts` among first-party modules. Do not import `plan_tool.roadmap`, artifact parsers, gates, prompt code, or connector-specific code to validate the optional block.

## Tests

### Tests for this step

- `test_brief_without_carried_decisions_is_compatible` — `tests/test_roadmap_source.py` proves a brief without the heading yields an empty carried collection.
- `test_brief_exposes_closed_carried_decisions` — `tests/test_roadmap_source.py` proves a valid block retains typed decisions, optional upstream deliberation, and confirmed answers.
- `test_invalid_carried_decision_block_raises_naming_brief` — `tests/test_roadmap_source.py` proves invalid heading, fence, JSON, collection, and entry shapes fail closed with a path-bearing source error.
- `test_carried_decision_rejects_unknown_or_free_form_fields` — `tests/test_roadmap_source.py` proves the input cannot become a generic log or metadata channel.
- `test_carried_decision_rejects_duplicate_or_unconfirmed_citation_targets` — `tests/test_roadmap_source.py` proves answer ids are unique, confirmed, and exactly matched by the selected option.
- `test_brief_digest_binds_carried_block_changes` — `tests/test_roadmap_source.py` proves a changed block changes the selected brief digest while the raw source-record digest contract stays unchanged.
- `test_source_module_does_not_import_roadmap_or_orchestrator_modules` — `tests/test_roadmap_source.py` keeps the source reader’s leaf-import rule green after the new types and parser land.
- `test_initial_brief_block_reaches_stage_without_manual_source_record_edit` — `tests/test_roadmap.py` proves the existing CLI brief path admits the block before stage authoring and records only path/digest after successful publication.
- `test_confirmed_rebind_admits_new_brief_block_without_extra_writes` — `tests/test_roadmap.py` proves the changed brief follows the existing confirmed admission route, and the block grants no extra artifact, feedback, draft, or seed write.
- `test_unconfirmed_changed_source_with_carried_decisions_writes_nothing` — `tests/test_roadmap.py` proves changed content remains refused without explicit rebind confirmation and reaches neither artifact handling nor source replacement.

Every listed test must be green before this step is complete.

## Acceptance criteria

- A valid brief without the block retains current behavior; a brief with the closed block supplied through `--from-existing` yields typed decisions and confirmed citation targets.
- A malformed, ambiguous, unconfirmed, or open-ended brief block raises `RoadmapSourceError` before artifact processing or a stage call.
- `RecordedBriefSource.source_digest` continues to represent exact raw `source.json` bytes; no carried collection is persisted there.
- Initial `source.json` creation remains atomic and occurs only after the first successful stage artifact publication.
- Confirmed same-path rebind retains its existing path/digest baseline replacement and stage behavior; the block grants no extra publication authority.
- `tests/test_roadmap_source.py` and `tests/test_roadmap.py` pass with the new source contract.

## References

- [Roadmap carried settled decisions plan](docs/implementation-plans/2-roadmap-carried-settled-decisions.md) — Read the architecture, rebind rule, and source-scope boundary this step establishes.
- [Roadmap format](ROADMAP_FORMAT.md) — Preserve the existing `source.json` lifecycle and compatibility contract.
- [Data contract](DATA_CONTRACT.md) — Preserve source-admission event meanings and redacted lifecycle evidence.
- [Roadmap intake comparison](docs/evidence/roadmap-aidlc-intake-comparison-20260916.md) — Read the confirmed provenance failure that selects this narrow capability.
- [AI-DLC integration delivery handoff](handoffs/2026-09-14-roadmap-aidlc-integration-delivery.md) — Read the selected #384 scope and held #383 work.
- [BACKLOG.md #384](BACKLOG.md) — Read the inherited-decision and citation requirements that this source input supports.

## Applicable guardrails

- **The plan’s “## Scope guardrails”, selected-row authority:** Limit the new source contract to approved carried-decision data. Do not let it authorize any other writer, lifecycle action, or prompt input.
- **The plan’s “## Scope guardrails”, baseline-only rebind:** Preserve the existing rebind as a source-record replacement only. Later validation may block publication, but this step must not make rebind mutate Roadmap artifacts or seed-related state.
- **The plan’s “## Scope guardrails”, held supplementary grounding:** Keep the source reader single-source and generic. Do not add stage-specific supplements, identity composition, or prompt-routing behavior.
- **The plan’s “## Scope guardrails”, runtime neutrality:** Do not encode AI-DLC, Integration, connector, runtime, or external artifact vocabulary in source parsing.
- **The plan’s “## Out of scope”, closed input shape:** Do not accept logs, question menus, source directories, positional prose, or derived rejected alternatives as alternate carried-decision input.
