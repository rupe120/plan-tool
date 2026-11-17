# Step 2 — Deliver sibling `creates:` paths to the plan audit as a prompt input block

<!-- plan-tool:detail-format-version: 1 -->

## Summary

- Add a `${sibling_planned_paths_block}` placeholder to `plan_tool/prompts/plan-audit.md`. It lists same-roadmap sibling `creates:` paths, one per line, and says a listed path is a sibling plan's planned work, not a missing file.
- `render_plan_audit_prompt` in `plan_tool/review.py` fills the block. It reads step 1's captured set from `audit_input_snapshot` when one is passed, and otherwise calls step 1's helper.
- An empty set renders an explicit "no sibling plan paths apply" statement, never an empty slot.
- The block's size goes into the `collect_blocks` budget list.
- On green, plan 2 of a two-plan roadmap sees plan 1's `creates:` path in its audit prompt. The step delivers facts and checks only that they were delivered.

## Table of Contents

- [Why](#why) — what the model-driven audit cannot see today
- [Input](#input) — what step 1 provides and the renderer's current shape
- [Files (creates vs edits)](#files-creates-vs-edits) — footprint
- [Implementation](#implementation) — block text, renderer wiring, budget, docstring, prose sweep
- [Tests](#tests) — case roster
- [Acceptance criteria](#acceptance-criteria) — observable checks
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — what this step leaves out

## Why

- The deterministic missing-file check already treats sibling `creates:` as planned work. The conceptual audit prompt carries no sibling facts, so the model re-reports those paths as missing every round.
- Step 1 selects and captures the sibling set. Nothing puts it in front of the auditor yet.

## Input

- **Step 1 output:** a helper in `plan_tool/review.py` that returns the same-roadmap sibling `creates:` paths, and a sorted-tuple field on `AuditInputSnapshot` (`plan_tool/review_persistence.py`) that holds the captured result. Read the landed names off the code, not off this file. At the time of writing, neither exists in `plan_tool/review.py` or `plan_tool/review_persistence.py`; the landed names win.
- **Empty means "no siblings to list":** no roadmap identity, uncertain identity and no other registered plans all yield an empty set from step 1. This step renders all of them the same way and adds no selection rule.
- **Renderer today:** `render_plan_audit_prompt` loads `plan-audit.md` through `prompts_dir()` and fills it with `Template.safe_substitute`. An unknown `${name}` stays in the output as literal text with nothing red firing. The placeholder-coverage test below is the only mechanical check.
- **Existing placeholders in `plan-audit.md`:** `plan_title`, `response_format_block`, `carried_findings_block`, `intent_block`, `scope_contract_block`, `project_context_block`, `plan_body_block`, `detail_bundle_framing_block`, `detail_bundle_status_block`, `detail_files_block`. Confirm the list at HEAD with a grep before editing.
- **Verification limit:** tests render the prompt and inspect text. They cannot show how a real model responds.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/prompts/plan-audit.md`: add the placeholder and the sentence that tells the auditor how to read it.
  - `plan_tool/review.py`: build the block in `render_plan_audit_prompt`, pass it to `safe_substitute`, extend the `collect_blocks` list, update the docstring.
  - `tests/test_review.py`: add the cases below beside the existing `render_plan_audit_prompt` tests.

## Implementation

- **Put the placeholder beside the other input blocks.** One way: on its own line near `${carried_findings_block}` and `${project_context_block}`, with a short lead-in so the block reads as an input section. Do not put it on the `${intent_block}${scope_contract_block}` line, which is joined without a separator on purpose.
- **Block text, when the set is non-empty:**
  - A one-line statement that the listed paths are planned work of other plans in the same roadmap and must not be reported as missing files.
  - The paths from step 1's normalized, deduplicated set, one per line, exactly as captured in the snapshot. Use a fenced block or a bullet list; either way keep one path per line.
  - Take the paths in the order step 1 stored them (sorted). Do not re-sort or re-select.
- **Block text, when the set is empty:** an explicit sentence saying no sibling plan paths apply to this plan. This follows the repo's "state the empty case" preference. It must not render an empty string.
- **Source of the set:**
  - When `audit_input_snapshot` is passed, read the snapshot's captured set. Do not recompute; the snapshot pins the inputs of a multi-pass audit.
  - When it is not passed, call step 1's helper with the plan, `plan_path` and `repo_root`.
  - Keep the same branch shape the renderer already uses for `project_context_rendered`.
- **Formatter placement:** one small private formatter in `plan_tool/review.py` that takes the path sequence and returns the block text. A direct function is enough; no config knob and no new module.
- **Budget:** add `("sibling planned paths", len(block.encode("utf-8")))` to the `collect_blocks.extend([...])` list, reusing the just-built string like the other entries.
- **Docstring:** add a paragraph to the renderer docstring describing the block, its two sources, and the explicit empty statement. Keep it to a few lines.
- **Prose sweep of `plan-audit.md`:** grep the template for wording that says or implies the auditor sees no other plans' footprints, or that every path not in the plan or repo is missing. Reword any such text to defer to the new block. Existing hits for "sibling" (lines about sibling steps and sibling sites) are unrelated and stay.
- **No `$` hazard:** block text containing a literal `$` must write `$$`. Prefer wording with none. Rendered paths are substituted values, so a `$` inside a path is safe.
- **Not free to vary:**
  - The block never filters or post-processes model findings.
  - The block adds no selection rule beyond step 1's.
  - The placeholder must be supplied on every render path, including the no-snapshot path.

## Tests

In `tests/test_review.py`, using `tmp_path` repos with a real manifest and real plan files; use no mocks for the identity cases.

- `test_audit_prompt_for_plan_two_lists_plan_one_creates_path_and_not_its_own` — two-plan same-roadmap fixture; plan 2's rendered prompt contains plan 1's path and does not contain plan 2's own `creates:` path in the block.
- `test_audit_prompt_without_roadmap_identity_renders_the_empty_statement` — a no-identity plan renders the explicit no-sibling statement, not an empty slot.
- `test_audit_prompt_with_uncertain_identity_renders_the_empty_statement` — an uncertain-identity plan (for example an unreadable seed, built with a real file) renders the same statement and does not raise.
- `test_audit_prompt_omits_a_different_roadmaps_path` — a registered plan from another roadmap contributes nothing to the block.
- `test_snapshot_backed_render_uses_the_captured_set_not_a_recompute` — pass an `audit_input_snapshot` whose captured set differs from the on-disk state; the rendered block shows the captured set. This pins that a multi-pass audit reads pinned inputs.
- `test_every_plan_audit_placeholder_is_supplied_and_none_is_left_in_the_render` — extract every `${name}` from `plan-audit.md` and assert each is supplied by the renderer; assert `"${"` is absent from a rendered prompt on both the snapshot and no-snapshot paths.
- `test_collect_blocks_reports_the_sibling_paths_block_size` — a render with `collect_blocks` passed adds a sibling-paths entry whose size matches the block.

Green-before-done gate: every test above must pass, along with the existing `tests/test_review.py` render tests that assert prompt content. No test asserts how a real model responds.

## Acceptance criteria

- Rendering the audit prompt for plan 2 of a two-plan same-roadmap fixture lists plan 1's `creates:` path, one per line, and states it is planned work, not a missing file.
- The same render for a no-identity or uncertain-identity plan contains an explicit "no sibling plan paths apply" statement.
- A snapshot-backed render shows the snapshot's captured set.
- No `${` remains in any rendered `plan-audit.md` prompt.
- `collect_blocks` includes the sibling-paths block size.
- `plan-audit.md` carries no text implying the auditor sees no sibling footprints.
- The renderer docstring describes the block.
- `uv run pytest tests/test_review.py -q` is green.

## Applicable guardrails

- **The plan's "Scope guardrails" (no filtering, no new selection rule):** this step delivers step 1's set as-is and never matches finding text against paths.
- **The plan's "Scope guardrails" (deterministic check unchanged):** this step does not touch `_eligible_planned_paths` or the missing-file check.
- **The plan's "Audit guardrails":** plans outside the roadmap are never listed. When identity is uncertain, the block renders the empty statement. It does not widen the selection.
- **The plan's "Out of scope":** blocking predicates, convergence policy, severity and exit codes are untouched.

## Deferred

- Snapshot capture, fingerprint and revision v4 — owned by step 1.
- `integrations/shared/DIRECTIVES.md` § "T — tool artifacts" wording — owned by the plan's later docs step.
- Checking that the model honored the block — refused by the plan's "Out of scope" (deliver, don't verify).
