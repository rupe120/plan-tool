> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Define the generated Jira developer-handoff format and lifecycle

> **Historical delivery evidence — superseded 2026-08-23.** This detail records
> the completed opt-in companion design. The unified paired-export contract in
> `JIRA_FORMAT.md` replaces its story-only compatibility claims.

## Summary

Create `plan_tool/jira_handoff.py` as the deterministic renderer and shared-provenance contract for the generated developer handoff, with focused contract tests in `tests/test_jira_handoff.py`. The renderer consumes step 1’s captured inputs and produces Markdown that separates the committed plan path from the selected detail’s suggested implementation route. Its format-specific writers and readers make later publication recognize only a same-plan, complete generated-source pair on either terminal source. On green, every committed step has an ordered handoff section, while parked steps remain visible only as non-actionable history and missing done-step sources remain visible historical fallbacks rather than invented guidance.

## Table of Contents

- [Summary](#summary) — Reviewer-level outcome and affected surfaces.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Why stories alone cannot provide a safe developer handoff.
- [Input](#input) — Captured plan, detail, and provenance data this renderer consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Exact new-file footprint.
- [Implementation](#implementation) — Handoff structure, ordering, provenance, and lifecycle rules.
- [Tests](#tests) — Focused rendering and provenance contract coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Standard-library and test-fixture references.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that limit this renderer.
- [Deferred](#deferred) — Later publication, CLI, and documentation work.

## Why

`plan_tool/jira.py:format_markdown` and `plan_tool/jira.py:format_json` produce concise story artifacts, but neither preserves the plan body’s developer context, dependency path, or the distinction between required outcomes and implementation suggestions. The companion needs a deterministic format that carries those facts from one captured source state without turning selected-detail mechanics into new requirements or making a generated file look safe to overwrite without proof.

## Input

- **Captured companion inputs:** Step 1 supplies the immutable plan document, committed render set, parked-step history, selected-detail bodies and paths, declared-file excerpt states, resolved settings, normalized destinations, pair identity, and rendering-contract revisions. Render only those captured values; do not reopen a plan, detail, or source path.

- **Plan structure:** `plan_tool/schema.py:Plan`, `plan_tool/schema.py:Step`, and `plan_tool/schema.py:StepStatus` provide the complete step path, declared dependencies, titles, intents, statuses, and file footprints. `plan_tool/schema.py:Plan` rejects invalid graphs, but it does not order steps for display.

- **Plan-body context:** `plan_tool/parser.py:parse_body_sections` provides the captured-body section shape. Render the selected developer-facing sections from the snapshot, including present Scope guardrails and Expected placement, while excluding Audit guardrails.

- **Intent meaning:** `plan_tool/scope_fence.py:collapse_intent_to_one_line` and `plan_tool/scope_fence.py:is_placeholder_intent` define whether a `Step.intent` supplies meaningful purpose text. Use the shared predicate rather than creating a second placeholder vocabulary.

- **Selected-detail content:** `plan_tool/jira_grade.py:parse_jira_grade_sections` shows the compact Jira-grade source shape, while step 1 supplies the selected grade and exact validated body. Captured excerpts originate from `plan_tool/prompt_excerpt.py:build_prompt_excerpt`; retain them as captured route evidence rather than rebuilding them.

- **Story lifecycle boundary:** Step 3 owns regenerated story state, keys, and dropped-history handling. This renderer receives the current captured plan path only; it must not turn prior story records or dropped history into handoff plan-path sections.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/jira_handoff.py` — Add the deterministic developer-handoff renderer, input-fingerprint/provenance representation, and strict generated-handoff provenance reader.
  - `tests/test_jira_handoff.py` — Add direct rendering, fallback, provenance, and import-boundary tests.

- **Existing files (edits only):** None. Step 5 will connect this contract to companion publication.

## Implementation

- **Foundational logic — render one captured plan path into deterministic Markdown.** Add a small handoff contract in `plan_tool/jira_handoff.py` that turns step 1’s snapshot into text and defines the shared companion provenance that later publication serializes on both the handoff and story source. Keep rendering and provenance parsing pure: this module must not write files, invoke a model, or reread a path.

- **Keep the module below `plan_tool/jira.py`.** Do not import `plan_tool/jira.py` from `plan_tool/jira_handoff.py`; later companion orchestration will need to call the handoff renderer from the Jira lane. Accept the step 1 snapshot through a narrow render-input boundary so the new module does not create a reverse import or depend on append-mode internals such as `plan_tool/jira.py:_ExistingExport`.

- **Render a visible document contract.** Produce a Markdown document with a clear generated-handoff title, a visible provenance block, captured plan context, one ordered section per captured committed step, and a separate **Parked plan history** appendix. Each committed section starts with **Plan path**; only a non-done committed step with selected detail separately labels **Suggested implementation route**.

- **Make the active plan path binding.** In every committed step’s **Plan path**, render the step id, title, `Status: <pending|current|done>`, stated outcome, meaningful intent, and each declared edge as `Depends on: <step id> — <step title>` in declared dependency order. Render `Depends on: none` when no edge exists. Treat titles and meaningful intents on committed non-done steps as required input; refuse rendering when either is missing rather than filling it from selected detail.

- **Use stable committed dependency order.** Topologically order all captured committed steps, using their order in `Plan.steps` to break ties between independent steps. A dependent listed before its prerequisite must still render after that prerequisite. Do not use story grouping, story ids, step status, or file order as an ordering shortcut.

- **Keep suggested routes non-binding.** For non-done steps, render selected-detail text, declared file paths, captured excerpts, non-dependency sequencing, risks, anchors, and technical approach only below **Suggested implementation route**. State visibly that a developer may choose another compliant mechanism that still fulfills the plan path. Do not let selected detail add, remove, replace, collapse, or reorder plan-path entries.

- **Give scope and placement priority.** Render present Scope guardrails and Expected placement from the captured plan body as binding context. When either is present, include a visible statement alongside every suggested route that those constraints win over route prose and require a compliant alternative when they conflict. Do not inspect the prose for conflicts, reject a route because of a conflict, or render Audit guardrails.

- **Render completed and parked work as non-actionable history.** A committed done step visibly says `Status: done — historical; no implementation action`. A blank done title renders `_(title not recorded)_`; a done step with no meaningful intent or selected detail says which source is absent and omits the corresponding invented purpose or suggested route. A done step with selected detail or declared-file excerpts may include them only as historical context, never as a suggested route. The **Parked plan history** appendix lists every deferred or `wont_do` step's id, title, scope, and status note, with no dependency edge, outcome, detail, excerpt, or suggested route; a deferred step is non-actionable until promoted, while a `wont_do` step is non-delivery history.

- **Define generated provenance for both readers and writers.** Define one structured `CompanionProvenance` value for the Markdown handoff and companion-only Markdown/JSON story source. It includes an explicit format revision, generation mode, selected grade, source plan path, selected detail source paths, both normalized destinations, the complete pair identity, both rendering-contract revisions, and the full captured-input fingerprint. Provide format-specific writers and strict readers; ordinary story-only output carries no companion marker and keeps its current shape.

- **Fingerprint the complete shared render input, not prior output.** Derive a deterministic SHA-256 digest from a canonical representation of every captured value that can change either source, including plan-body context, normalized destinations, and every carried existing story record's complete rendered representation, canonical covered-step set, normalized lifecycle state, and Jira key. Exclude predecessor-output ownership evidence, including raw target content proofs, timestamps, and other non-render data so an unchanged rerun keeps the same fingerprint and does not create false lifecycle changes.

- **Make ownership recognition strict.** The format-specific provenance readers accept an output only when its generated marker, format revision, required fields, and complete pair identity are well-formed. A missing or malformed marker remains unrecognized for step 5’s target-protection decision; do not guess ownership from filename, title, or a matching fingerprint.

- **Keep lifecycle work in its owner step.** Return rendered text and parsed provenance only. Step 5 owns staging, final target confirmation, replacement, and recovery; step 6 owns operator-facing flags and output.

## Tests

### Tests for this step

- `test_handoff_renders_every_committed_step_in_stable_dependency_order` — A plan that lists a committed dependent before its prerequisite renders all committed steps exactly once, with prerequisites first and original plan order breaking ties between independent steps.

- `test_handoff_renders_committed_dependency_edges_or_none` — Every committed step renders each declared dependency with its captured title, while an independent step renders `Depends on: none`.

- `test_handoff_keeps_committed_plan_outcome_and_intent_binding_separate_from_route` — The title and meaningful `Step.intent` render in **Plan path**, while non-done committed selected-detail material remains under **Suggested implementation route** with an explicit alternative-mechanism allowance.

- `test_handoff_uses_captured_detail_and_excerpt_values_without_reading_live_paths` — A handoff renders the detail and excerpt state held by the snapshot after source files change.

- `test_handoff_renders_selected_plan_context_and_excludes_audit_guardrails` — Overview, Problem statement, Architecture, Out of scope, Risks, Acceptance criteria, Scope guardrails, and Expected placement render from the captured body when present, while Audit guardrails do not appear.

- `test_handoff_scope_and_expected_placement_override_suggested_route` — Present scope or placement context produces the visible compliant-alternative rule without adding a conflict classifier or refusing a rendered route.

- `test_handoff_rejects_non_done_step_without_title_or_meaningful_intent` — A non-done step missing either binding field raises a handoff-input error rather than borrowing text from selected detail.

- `test_handoff_renders_done_step_status_and_missing_sources_as_visible_history` — A committed done step visibly says no implementation action, names an absent selected detail or meaningful intent, and has no invented route or purpose.

- `test_handoff_renders_done_step_excerpts_only_as_historical_context` — A done step's captured declared-file excerpt renders as history rather than as an implementation route.

- `test_handoff_renders_blank_done_title_as_not_recorded` — A done step with a blank title renders `_(title not recorded)_` without inventing an outcome.

- `test_handoff_lists_parked_steps_as_non_actionable_history_only` — Deferred and `wont_do` steps appear only in **Parked plan history**, with scope and status note but no plan path, dependency, detail, excerpt, or route.

- `test_handoff_never_renders_dropped_story_history_as_a_committed_plan_path_step` — Prior dropped-story records cannot add, suppress, or alter the committed captured plan path.

- `test_companion_provenance_records_complete_pair_identity_for_both_output_formats` — The shared provenance carries the required generated marker, revisions, source paths, both destinations, generation mode, complete pair identity, and fingerprint for handoff, Markdown story, and JSON story writers.

- `test_handoff_fingerprint_changes_for_carried_story_records_but_excludes_predecessor_ownership_evidence` — A carried story record's rendered content, state, or Jira key changes the fingerprint; its covered-step order, predecessor provenance, and raw target content proof do not.

- `test_handoff_fingerprint_changes_for_every_companion_render_setting` — Every captured setting that changes a story or shared provenance changes the fingerprint.

- `test_companion_provenance_readers_reject_missing_or_malformed_generated_metadata` — A hand-edited or incomplete handoff or story target is not recognized as a same-pair generated source.

- `test_jira_handoff_does_not_import_plan_tool_jira_at_runtime` — The new renderer has no runtime dependency on `plan_tool/jira.py`, preventing a reverse-import cycle when later Jira orchestration calls it.

Every listed case in `tests/test_jira_handoff.py` must be green before this step is complete.

## Acceptance criteria

- `plan_tool/jira_handoff.py` renders a deterministic Markdown handoff from step 1’s captured input without filesystem reads, model calls, or writes.

- Every captured committed plan step appears exactly once in stable topological order, with visible status and declared dependencies or `Depends on: none`; deferred and `wont_do` steps appear only as non-actionable parked history.

- Each committed non-done step renders its title and meaningful intent as binding plan-path content; selected detail never replaces that content.

- For a non-done committed step, selected detail, file paths, excerpts, and route mechanics render only as a suggested implementation route, with visible scope and placement priority when those plan sections are present. A done step may render selected detail and captured excerpts only as non-actionable historical context.

- A committed done step visibly states its historical no-action status and remains visible through the required fallback, including `_(title not recorded)_` for a blank title; parked steps cannot look actionable.

- The shared companion provenance identifies each generated format, complete story-and-handoff pair, captured inputs, normalized destinations, rendering revisions, generation mode, and deterministic fingerprint on both outputs without changing story-only output.

- A malformed or incomplete provenance block is not recognized as generated ownership data, and predecessor ownership evidence does not affect a new fingerprint.

- `uv run pytest tests/test_jira_handoff.py -q` passes.

## References

- [hashlib — Secure hashes and message digestshttps: — Use SHA-256 for the deterministic captured-input fingerprint.

- [How to use temporary directories and files in testshttps: — Use isolated snapshot and generated-handoff fixtures.

## Applicable guardrails

- **The plan’s “## Plan intent”, one captured source state:** Render only step 1’s immutable inputs so the handoff cannot drift from its paired story source.

- **The plan’s step 4 intent, binding path:** Preserve complete step coverage, dependency ordering, step outcomes, and visible route-versus-constraint priority in the generated format.

- **The plan’s “## Out of scope”, source authority:** Do not change detail grades, mutate plans, add Jira sync, or add prose-conflict classification or publication refusal behavior.

- **The plan’s “## Risks”, story-only compatibility:** Keep this new renderer separate from current story-only export behavior until the later opt-in companion path uses it.

## Deferred

- Paired target staging, final ownership confirmation, replacement, and recovery — Step 5 owns publication.

- Companion flags, output precedence, and created-ticket notices — Step 6 owns CLI behavior.

- User-facing format documentation and BACKLOG delivery status — Step 7 owns documentation and delivery recording.

- Jira-native attachment or synchronization — Remains outside this terminal generated-source workflow.
