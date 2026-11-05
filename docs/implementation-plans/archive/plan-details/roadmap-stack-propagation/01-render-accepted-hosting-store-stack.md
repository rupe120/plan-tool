> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Render the accepted hosting and store stack into each draft seed

<!-- plan-tool:detail-format-version: 1 -->

## Summary

`_materialize_plan_seed` in `plan_tool/roadmap.py` gains one deterministic text edit between the lift and the validation of the model's reply. The tool replaces any model-authored `## Stack` section with its own. The section names the accepted version id, lists every hosting row, and lists the store rows owned by the plan row's components. The draft write, the promoted-seed rewrite, and the digest and sidecar write all use the stack-bearing text. Both `materialize_plan_seed` and the refresh path (`refresh_roadmap_seeds`) therefore carry the stack, and a rewritten promoted seed does too. On green, every freshly materialized draft contains exactly one tool-rendered `## Stack` section, and a changed accepted hosting or store row changes the section on the next rematerialization.

## Table of Contents

- [Why](#why) — what draft seeds drop today
- [Input](#input) — the accepted artifacts the step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — the footprint
- [Implementation](#implementation) — the rendered section, replacement rule, and placement
- [Tests](#tests) — the test roster and the green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — observable checks
- [Applicable guardrails](#applicable-guardrails) — the plan fence as it binds this step
- [Deferred](#deferred) — items left out

## Why

The model writes each draft seed from the four accepted artifacts. The accepted hosting rows (`ConstraintsArtifact.hosting`) and store rows (`ComponentsArtifact.stores`) reach the draft only if the model chooses to restate them. Nothing in the code carries them forward, so `create` and `detail` can work from a seed that has lost the stack. The tool, not the model, must put the stack in the draft, so the content comes from the accepted bytes and cannot drift.

## Input

- **Accepted artifacts:** `load_accepted_roadmap_artifacts` returns the four `_LoadedArtifact` entries in stage order. `loaded[1].artifact` is a `ConstraintsArtifact` with `hosting: tuple[HostingRow, ...]`. `loaded[2].artifact` is a `ComponentsArtifact` with `components` and `stores`.
- **Row fields** (`plan_tool/roadmap_artifacts.py`):
  - `HostingRow` has `id`, `facet`, `value`, `product: Optional[str]`.
  - `StoreRow` has `id`, `category`, `sharing`, `product: Optional[str]`.
  - `ComponentRow.store_ids` names the stores a component uses.
  - `PlanRow.component_ids` names the components a plan owns.
- **Version id:** `load_accepted_roadmap_artifacts` does not return it. `plan_tool/roadmap_versions.py:load_accepted_version(...).record.version_id` does. The writer guard is held for the whole materialization, so a second call to it cannot race an accept.
- **Not checked here:** the hosting and component gates already guarantee the references resolve. This step does not re-validate them (see Implementation).

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/roadmap.py` — add a stack renderer and a section-replacement helper, and call them from `_materialize_plan_seed`.
  - `plan_tool/prompts/roadmap-seed.md` — tell the model that the tool writes `## Stack` and that it must not author one.
  - `tests/test_roadmap.py` — the stack tests (the roster below).
  - `tests/test_roadmap_seed_manifest.py` — a classification case for a stack-bearing seed.

## Implementation

**Intended behavior**

- **Always emitted.** Every materialized draft carries a `## Stack` section, even when the roadmap has no hosting rows and no stores. In that case the section says so explicitly. It always names the accepted version id.
- **Hosting rows:** list all of them: id, facet, value, product.
- **Store rows:**
  - Take the plan row's `component_ids`.
  - Look up each in `ComponentsArtifact.components`, take the union of their `store_ids`, and resolve it against `ComponentsArtifact.stores`.
  - Render each store once (id, category, sharing, product), in the order of `ComponentsArtifact.stores`.
- **Cross-cutting plan row:** treated the same way, using its listed `component_ids`.
- **No components on the plan row:** render the hosting rows alone, with no store lines and no error.
- **Open product:** a row whose `product` is `None` says in words that the accepted roadmap leaves the product open. Do not print `None`, an empty value, or omit the row.
- **Replacement:** remove any model-authored `## Stack` section and put the tool's section in its place.

**Recommended approach**

- **Module-private helpers:** add two helpers in `plan_tool/roadmap.py`, for example `_render_stack_section(...)` and `_replace_stack_section(text, section)`. Keep them module-private. Skip a rule engine or configuration.
- **Placement:** insert the stack after the frontmatter, in a fixed place. One way: immediately before `## References`, or at the end when there is none. `validate_draft_seed_content` reads provenance frontmatter and the `## References` section, so keep the frontmatter fence first and `## References` a normal H2.
- **Where it runs:** apply the replacement right after `_lift_artifact_text` succeeds and before `validate_draft_seed_content`. The validated text then equals the written text. The write, the promoted-seed body, and `digest_text(...)` must all use the stack-bearing variable. The existing `lifted` is the natural one to rebind, so the draft and promoted overwrites and the sidecar rewrite need no other edits.
- **Replacement scan:** a line-anchored scan that skips fenced code. Reuse `plan_tool/jira_grade.py:fenced_spans` (length-matching, tilde-aware, CRLF-safe; an unclosed fence runs to end of text) rather than a new regex. This matches `plan_tool/scope_fence.py:extract_h2_section_occurrences`, which returns bodies, not positions.
  - Replace only a real `## Stack` H2 outside any fence. Match the heading text exactly (after trimming), so `## Stacked`, `### Stack`, and `## Stack` inside a fenced block are left alone.
  - Replace each real `## Stack` H2, including repeats, with one tool section. The tool section's body runs to the next H2 or end of text.
- **Heading is structural:** the tool's `## Stack` heading starts its own line. Any text the model authored is never parsed as part of it.
- **Rejected alternative:** asking the model to copy the stack from the prompt. Nothing could then check it, and it drifts.
- **Rejected alternative:** having the model-facing prompt include the rendered stack and validating that it came back. That adds a check on prose, which the repo's rules rule out.

**Constraints**

- **Deterministic text:** the rendered section is a pure function of the accepted rows, the plan row, and the version id. Same inputs give identical bytes, so an unchanged roadmap rematerializes to an identical stack, and a changed row changes the digest.
- **Don't validate references here.** A dangling `store_ids` entry is a gate finding in the existing component gates. Skip the id quietly, and do not raise from the renderer.
- **Existing seed validation unchanged:** `validate_draft_seed_content` is not edited. The rendered section must pass it as is, and `classify_draft_seeds` must classify the written file `current`, not `digest-mismatched` or `malformed`.
- **Prompt edit:** in `plan_tool/prompts/roadmap-seed.md`, say the tool inserts `## Stack`, so the model leaves it out. The template's placeholders (`${domain_artifact}` and the others) stay as they are; a literal `$` in prose must be `$$`.
- **Version-id call:** if `load_accepted_version` returns `None` inside the writer guard, raise `RoadmapError` (as the sibling loaders do). Do not render without a version id.

## Tests

`tests/test_roadmap.py`, using the existing fake-invoker fixtures and `publish_accepted_root`:

- `test_materialized_seed_has_stack_section_naming_the_accepted_version_id` — the written draft contains one `## Stack` section with the accepted version id.
- `test_stack_lists_every_hosting_row_with_id_facet_value_product` — all hosting rows render all four fields.
- `test_stack_lists_only_stores_named_by_the_plans_components` — a store used only by another plan's component is absent; a shared store appears once.
- `test_row_without_product_states_the_product_is_left_open` — the open-product wording appears, and neither `None` nor an empty value does (hosting and store rows).
- `test_changed_accepted_row_changes_the_rendered_stack_on_rematerialization` — advance the accepted head with a changed hosting or store value, rematerialize, and the section and digest change; an unchanged roadmap rematerializes to identical bytes.
- `test_cross_cutting_plan_stack_includes_its_listed_components_stores` — a cross-cutting plan row renders the stores of its listed components.
- `test_plan_with_no_components_renders_hosting_rows_alone` — no store lines and no error.
- `test_roadmap_with_no_hosting_or_stores_still_emits_an_explicit_stack_section` — the section is always emitted and says it is empty.
- `test_model_authored_stack_section_is_replaced_not_kept` — a model-authored `## Stack` (with wrong content) is gone and the tool's section is the only one; repeated `## Stack` headings collapse to one.
- `test_lookalike_stack_headings_and_fenced_stack_text_are_not_replaced` — `## Stacked`, `### Stack`, and a `## Stack` line inside a fenced block (including a `~~~` fence) survive unchanged, and a real `## Stack` beside them is still replaced.
- `test_promoted_seed_rewritten_after_materialization_carries_the_stack` — when the plan already has a `plan-seeds/` copy, the rewritten promoted seed contains the section.
- `test_rendered_stack_passes_draft_seed_content_validation` — `validate_draft_seed_content` returns no violations for the written draft.

`tests/test_roadmap_seed_manifest.py`:

- `test_classify_current_for_a_draft_that_carries_a_stack_section` — a stack-bearing draft with a matching sidecar digest classifies `current`, not drifted.

Also add a prompt test beside the existing roadmap-seed prompt tests in `tests/test_roadmap.py`: `test_seed_prompt_tells_the_model_not_to_author_a_stack_section`.

**Green-before-done gate:** every test above must pass, along with the existing roadmap and seed-manifest tests, before this step is finished. Check each new test by mutation: remove the replacement and the replacement tests go red; skip the open-product branch and the open-product test goes red.

## Acceptance criteria

- A materialized draft contains exactly one `## Stack` section whose text names the accepted version id.
- Every accepted hosting row appears with id, facet, value, and product; a row with no product says the product is left open.
- Store rows appear only for stores reached through the plan row's `component_ids`, each once.
- A plan row with no components renders hosting rows alone; a roadmap with neither hosting nor stores still renders an explicit section.
- A model-authored `## Stack` section is replaced; lookalike headings and fenced text are untouched.
- `validate_draft_seed_content` returns no violations and `classify_draft_seeds` reports `current` for the written draft.
- The sidecar digest equals `digest_text` of the written (stack-bearing) draft, and a promoted seed rewritten by this path contains the section.
- `plan_tool/prompts/roadmap-seed.md` tells the model not to author `## Stack`.
- `plan_tool/roadmap_gates.py` has no diff.

## Applicable guardrails

- **The plan's "## Out of scope"** bars hosting questions, provenance tracking, and conflict surfacing. This step only renders accepted rows, and adds no comparison of technology names and no notes.
- **The same section** bars carrying the stack into the Jira handoff, and bars new facets, values, or a provider field. This step touches only draft-seed materialization; `HostingRow` and `StoreRow` are read, not changed.
- **The plan's step intent** limits this step to rendering and its own tests. How `create` and `detail` carry the section forward is left to later steps.

## Deferred

- Carrying the `## Stack` section through `create` and `detail` — later steps of this plan own it.
- Plan-audit tracing of the stack as commitments — a later step of this plan owns it.
- Cross-plan audit of derived plans against the roadmap — BACKLOG.md #462.
- Folding the three frontmatter and fence scanners into one — a cross-module refactor for BACKLOG.md, not this step.
