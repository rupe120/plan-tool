> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Render base-then-target-ordered comparison cards, complete patches, and deterministic JSON

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Create `plan_tool/roadmap_compare_render.py` to render step 4’s bound comparison result as terminal cards, complete raw patch output, and deterministic JSON. Add `tests/test_roadmap_compare_render.py` to cover ordering, labels, changed-field projection, evidence preservation, and stable machine-readable output. Keep presentation separate from snapshot resolution and typed comparison: this module consumes their facts without loading files, invoking Git, or changing roadmap state. On green, every supported output form describes the same two snapshots and retains the exact raw evidence.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the rendering surface.
- [Table of Contents](#table-of-contents) — Links to each detail section.
- [Why](#why) — Why comparison facts need one stable presentation owner.
- [Input](#input) — Bound comparison and evidence contracts from steps 2 and 4.
- [Files (creates vs edits)](#files-creates-vs-edits) — New renderer and focused tests.
- [Implementation](#implementation) — Terminal, patch, and JSON rendering requirements.
- [Tests](#tests) — Focused rendering and determinism coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Relevant roadmap comparison contracts.
- [Applicable guardrails](#applicable-guardrails) — Read-only, evidence, identity, and scope boundaries.
- [Deferred](#deferred) — CLI wiring and interactive presentation left to later work.

## Why

Step 4 returns complete, identified comparison facts, but operators and tools still need one presentation owner that does not invent a second ordering rule, label rule, or version of the raw evidence. Rendering directly from the bound result makes card output useful for review while keeping Git’s patch and the structured comparison tied to the same snapshots.

## Input

- **Step 2 typed comparison:** Consume step 2’s ordered cards, changed non-relation fields, separate relation occurrences, unmapped raw-text facts, and raw-evidence identity. Preserve their identity and order rather than rebuilding comparison facts.
- **Step 4 bound operation result:** Consume step 4’s base and target snapshot metadata, per-artifact digests, comparison result, and retained patch results. Rendering must not reread a snapshot or recompute a digest.
- **Display labels:** Use `plan_tool/roadmap_view.py:display_label` for human labels. The renderer supplies row-kind context where `PatternRow` needs it and must not recreate the label rules.
- **Fixed inventory:** Use `plan_tool/roadmap_versions.py:VERSION_ARTIFACT_INVENTORY` only to preserve configured artifact order in output. Do not introduce a renderer-owned inventory.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_compare_render.py` — Renders the bound comparison result as cards, complete patch output, and deterministic JSON.
  - `tests/test_roadmap_compare_render.py` — Covers the public rendering contract.

- **Existing files (edits only):**
  - None.

## Implementation

- **Foundational logic:** Render one ordered, bound roadmap comparison result without changing or reinterpreting its facts.

- **Keep rendering downstream of comparison.** Accept the result produced by step 4 and expose focused render entry points for the human card report, raw patch view, and JSON payload. The module must not load versions, parse artifacts, invoke Git, calculate typed differences, or mutate state.

- **Preserve base-then-target ordering.** Render cards in the order supplied by step 2: fixed artifact order, row-kind order, then base-side removals and changes before target-only additions. Do not sort cards by display label, stable id, field name, or patch text.

- **Render complete cards.** Each card must identify its artifact, row kind, stable id, and `added`, `removed`, or `changed` state. Use `plan_tool/roadmap_view.py:display_label` for the available row endpoint, show complete endpoints where the comparison contract provides them, and show before/after values only for changed non-relation fields.

- **Keep relations separate.** Render added and removed declared relations as their own occurrence-level entries. Do not fold relation changes into a row’s changed-field list or collapse repeated occurrences.

- **Make raw-only changes visible.** Render every unmapped/raw-text fact as explicit
  evidence associated with its raw-only artifact. A formatting, narrative, comment,
  or reorder-only patch must not acquire an invented concept card merely to make
  the terminal report look complete. A mixed artifact’s complete patch remains
  available without a renderer-invented byte-level split.

- **Preserve patches exactly.** The patch renderer must emit the retained Git unified output in fixed inventory order without truncating, normalizing, reconstructing, or substituting it. Successful identical pairs remain part of the bound result even when their empty patch contributes no patch text.

- **Bind every form to the same snapshots.** The terminal report and JSON must state base and target identities, including immutable version and brief identity when available, plus per-snapshot artifact digests and compact artifact/concept counts. A working snapshot must not gain an invented immutable identity.

- **Identify each artifact’s evidence outcome.** The terminal report and JSON must
  identify every fixed artifact pair as byte-identical or differing from the
  retained per-pair Git result. The raw patch view remains the exact Git stream:
  an identical pair retains its empty evidence without synthetic marker text.

- **Make JSON deterministic and complete.** Project the same structured cards, relation facts, unmapped evidence, snapshot metadata, artifact digests, and raw-evidence identity into JSON with a documented fixed field and collection order. Serialize typed row values through an explicit JSON-safe projection; do not rely on `str()`, model-specific repr output, or map iteration that can change the contract.

- **Keep display-only decisions local.** Reuse `plan_tool/roadmap_view.py:display_label` unchanged. Do not move label ownership, roadmap-wide indexes, candidate policy, selector parsing, or output-mode selection into this module.

## Tests

### Tests for this step

- `tests/test_roadmap_compare_render.py:test_terminal_cards_preserve_base_then_target_comparison_order` — removed and changed base-side cards render before target-only additions without label or id sorting.
- `tests/test_roadmap_compare_render.py:test_terminal_card_uses_display_label_and_complete_endpoints` — a card uses `display_label` for its available row and retains the comparison endpoints.
- `tests/test_roadmap_compare_render.py:test_changed_card_renders_only_non_relation_field_differences` — changed-field output excludes declared relations.
- `tests/test_roadmap_compare_render.py:test_relation_occurrences_render_separately_without_deduplication` — added and removed relation occurrences remain separate, including duplicates.
- `tests/test_roadmap_compare_render.py:test_unmapped_raw_text_renders_without_an_invented_card` — a raw-only artifact is visible but creates no structured concept.
- `tests/test_roadmap_compare_render.py:test_mixed_typed_and_raw_text_preserves_complete_patch_without_partition` — a typed card and its artifact’s complete patch remain visible without an invented raw-text split.
- `tests/test_roadmap_compare_render.py:test_patch_render_preserves_complete_git_output_in_inventory_order` — patch output retains supplied Git text unchanged and follows the configured inventory order.
- `tests/test_roadmap_compare_render.py:test_terminal_report_binds_snapshot_metadata_digests_and_counts` — the card report identifies both snapshots and shows their digest and count facts.
- `tests/test_roadmap_compare_render.py:test_terminal_and_json_identify_each_identical_or_differing_artifact` — a mixed bundle identifies every artifact’s byte-identical or differing result in both forms without adding text to an empty patch.
- `tests/test_roadmap_compare_render.py:test_json_contains_the_same_comparison_facts_as_terminal_rendering` — JSON includes cards, relations, unmapped evidence, snapshot metadata, digests, and raw-evidence identity.
- `tests/test_roadmap_compare_render.py:test_json_is_deterministic_for_equivalent_bound_results` — equivalent input facts produce identical JSON bytes.
- `tests/test_roadmap_compare_render.py:test_json_serializes_pattern_labels_with_row_kind_context` — pattern cards supply the context required by `display_label`.

Every listed test must be green before this step is complete.

## Acceptance criteria

- `plan_tool/roadmap_compare_render.py` renders only facts supplied by steps 2 and 4.
- Terminal cards retain the typed comparison’s base-then-target order and stable identities.
- Each card names its state, artifact, row kind, stable id, and established display label.
- Changed fields exclude declared relations, while relation occurrences remain separate and repeated occurrences remain visible.
- Unmapped/raw-text evidence appears explicitly for raw-only artifacts; a mixed
  artifact retains its complete patch without an invented byte-level partition.
- Patch output retains the complete supplied Git evidence in configured artifact order without rewriting it.
- Terminal and JSON output identify both snapshots, include per-artifact digests,
  expose the raw-evidence identity, and identify every artifact as byte-identical
  or differing without changing the raw patch stream.
- Equivalent bound comparison results produce identical JSON.
- `tests/test_roadmap_compare_render.py` passes.

## References

- [BACKLOG.md #402](BACKLOG.md) — Read the card ordering, patch-evidence, and machine-readable output contract.
- [ROADMAP_FORMAT.md](ROADMAP_FORMAT.md) — Read the fixed artifact, row, relation, and stable-id contracts.
- [plan_tool/roadmap_compare.py](plan_tool/roadmap_compare.py) — Read step 2’s typed cards, raw-only unmapped evidence, and raw-evidence identity contract.
- [plan_tool/roadmap_compare_run.py](plan_tool/roadmap_compare_run.py) — Read step 4’s bound snapshot metadata, digests, and patch result contract.
- [plan_tool/roadmap_view.py](plan_tool/roadmap_view.py) — Read `display_label` for established human labels.
- [plan_tool/roadmap_versions.py](plan_tool/roadmap_versions.py) — Read `VERSION_ARTIFACT_INVENTORY` for configured output order.

## Applicable guardrails

- **The plan’s “## Scope guardrails”, read-only behavior:** `plan_tool/roadmap_compare_render.py` must only transform supplied facts into text or JSON and must not change roadmap lifecycle state.
- **The plan’s “## Scope guardrails”, raw evidence role:** Cards and JSON may describe evidence but must not hide, replace, or rewrite the retained Git patches.
- **The plan’s “## Scope guardrails”, stable identity:** Render stable-id identities as supplied; do not match changed ids by labels or prose.
- **The plan’s “## Scope guardrails”, deterministic comparison:** Output must remain model-free and deterministic, with no generated recommendation or judgment.
- **The plan’s “## Scope guardrails”, compatibility:** Reuse `plan_tool/roadmap_view.py:display_label` without changing existing views or lifecycle writers.
- **The plan’s “## Out of scope”:** Do not add acceptance actions, selector parsing, generalized repository diffs, other artifact families, HTML, or interactive rendering.

## Deferred

- **CLI selector parsing and output-mode selection** — Step 6 owns the command surface that selects these renderers.
- **HTML or interactive cards** — The plan’s out-of-scope boundary requires separate evidence after terminal and JSON contracts ship.
- **Snapshot loading, patch capture, and refusal handling** — Step 4 remains the owner of bound input facts.
- **Candidate and lifecycle policy** — Comparison rendering remains read-only and does not change proposal, acceptance, or promotion behavior.
