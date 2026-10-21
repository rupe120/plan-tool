> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Add source-plan References to rebaseline seeds and preserve existing replacement behavior

## Summary

Update `plan_tool/reground.py:render_rebaseline_seed` so every rebaseline seed includes a body-level `## References` section naming its source plan. Keep `plan_tool/reground.py:reground_bridge` seed-first behavior and `_rebaseline_seed_path` collision handling unchanged. Extend `tests/test_reground.py` to prove the rendered seed passes the `--from-existing` References gate. On green, a rebaseline seed reaches normal create authoring without overwriting an earlier seed or changing create’s existing archive-and-replacement flow.

## Table of Contents

- [Summary](#summary) — The change and its observable result.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why the rendered seed currently stops before authoring.
- [Input](#input) — The renderer and create contracts this step uses.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed by this step.
- [Implementation](#implementation) — Required fallback rendering and preserved behavior.
- [Tests](#tests) — Focused regression coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Markdown and pytest references.
- [Applicable guardrails](#applicable-guardrails) — Scope limits for this step.
- [Deferred](#deferred) — Nearby work left with its owning steps.

## Why

`plan_tool/reground.py:render_rebaseline_seed` names its source in `## Provenance`, but it emits no `## References` section. The resulting seed advertises `plan-tool create --from-existing` yet fails `plan_tool/create.py:validate_from_existing_seed` before authoring begins. A source-plan fallback makes the generated seed usable while keeping the source path visible as the evidence for the re-decomposition.

## Input

- **Rebaseline renderer inputs** — `plan_tool/reground.py:render_rebaseline_seed` receives the parsed `Plan`, flagged step IDs, and `source_path`. Use `source_path` as the source-plan evidence; do not add a field to `Plan` or read extra files.

- **Create admission boundary** — `plan_tool/create.py:validate_from_existing_seed` requires a non-placeholder `## References` section before `plan_tool/create.py:create_plan` begins authoring. The rendered seed must satisfy that body-level contract.

- **Replacement owner** — `plan_tool/create.py:create_plan` and `plan_tool/create.py:archive_existing_source` own source archival and replacement after create accepts a seed. This step only makes rebaseline output eligible to reach that existing path.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/reground.py` — add the source-plan References fallback to `render_rebaseline_seed` without changing bridge lifecycle or path selection.
  - `tests/test_reground.py` — extend rebaseline seed coverage to prove the rendered output passes create’s admission gate and retains collision-safe behavior.

## Implementation

- **Render visible source evidence.** Make `plan_tool/reground.py:render_rebaseline_seed` emit one non-placeholder `## References` block in the Markdown body. Its entry must name the supplied `source_path`, matching the source-plan fallback shape already used by `plan_tool/scope_out.py:_references_block`.

- **Keep provenance separate.** Retain the existing `## Provenance` section and its source-plan record. Provenance metadata does not replace the References body contract.

- **Keep the renderer pure.** Build the fallback from the existing `source_path` argument. Do not load the source plan body, add a model call, or add filesystem work to `render_rebaseline_seed`.

- **Do not widen leaf dependencies.** Do not import `plan_tool.scope_out` or `plan_tool.create` into `plan_tool/reground.py`. `plan_tool/scope_out.py:_references_block` is a behavior reference only; importing it would break the leaf-import boundary guarded by `tests/test_reground.py`.

- **Preserve apply ordering.** Leave `plan_tool/reground.py:reground_bridge` writing the rendered seed before `mark_steps_done` and `write_plan`. The new section must not alter which steps become done or when the plan is replaced.

- **Preserve seed retention.** Leave `plan_tool/reground.py:_rebaseline_seed_path` as the sole owner of collision handling. A taken seed path must receive a numbered suffix, and an existing seed’s bytes must remain unchanged.

- **Reuse create’s replacement path unchanged.** Do not change `plan_tool/create.py:create_plan` or `plan_tool/create.py:archive_existing_source`. Once validation admits the rebaseline seed, create continues to own publishing the replacement plan and archiving the consumed source.

## Tests

### Tests for this step

- `test_rebaseline_seed_is_create_from_existing_consumable` — extend the existing test to assert a body-level `## References` block contains the source plan path and that `plan_tool.create.validate_from_existing_seed` accepts the rendered seed.

- `test_rebaseline_writes_seed_first_then_marks_done` — keep the successful rebaseline path proving a seed exists before the selected plan steps are persisted as done.

- `test_rebaseline_seed_never_overwrites` — keep the assertion that a later rebaseline uses a different seed path and leaves the first seed unchanged.

- `test_rebaseline_seed_collision_suffixes` — keep the assertion that an occupied base filename selects the numbered suffix and preserves the pre-existing file.

- `tests/test_create.py:TestCreatePlanFromExistingViaCli.test_happy_path_via_main` — run the existing unchanged integration regression to confirm accepted `--from-existing` sources retain create’s archive-and-replacement behavior.

Every listed test must be green before this step is complete.

## Acceptance criteria

- A seed returned by `plan_tool/reground.py:render_rebaseline_seed` contains one non-placeholder body-level `## References` section with a source-plan entry naming its `source_path`.

- `plan_tool/create.py:validate_from_existing_seed` accepts the rendered rebaseline seed.

- `plan_tool/reground.py:reground_bridge` still writes the seed before marking selected steps done and writing the plan.

- A rebaseline never overwrites an existing seed; collisions continue to use numbered filenames.

- The unchanged create integration regression passes, proving accepted source seeds still follow the existing replacement path.

## References

- [CommonMark Spec — ATX headingshttps: — Use this to keep the emitted `## References` heading valid Markdown.

- [pytest — temporary directorieshttps: — Use this for isolated seed and collision fixtures.

## Applicable guardrails

- **The plan’s “## Plan intent”, usable `--from-existing` routes** — make only the rebaseline seed’s missing fallback usable; keep authoring and validation authority where it already lives.

- **The plan’s “## Step intent”, source-plan naming** — use the source plan as the References evidence and do not substitute generic or empty reference content.

- **The plan’s “## Out of scope”, adjacent seed behavior** — do not expand this low-complexity change into other seed producers, schema work, or create-flow changes.

## Deferred

- Other seed producers and body-only validation changes — plan steps 1 and 2 own their declared files; this step reuses their resulting admission contract without modifying those paths.
