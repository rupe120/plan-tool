# Step 1 — Cite each roadmap file by its repo-relative version-store path in the seed prompt

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step makes `_materialize_plan_seed` in `plan_tool/roadmap.py` turn the four accepted-version member paths into repo-root-relative strings. It passes them to `_render_seed_materialize_prompt` as new template variables. `plan_tool/prompts/roadmap-seed.md` then asks for those exact paths wherever the seed body names a roadmap file, and the "literal filenames" wording is gone. The key design decision is to take the paths from the same `loaded` read as the artifact text. A plans directory outside `repo_root` stops with a `RoadmapError`. On green, a newly written seed cites `.roadmap-versions/<version-id>/…` files instead of bare `0N-*.md` names.

## Table of Contents

- [Why](#why) — what bare-name citations cost today
- [Input](#input) — the accepted-version read this step builds on
- [Files (creates vs edits)](#files-creates-vs-edits) — the three files and their edits
- [Implementation](#implementation) — approach, rejected alternative, constraints
- [Tests](#tests) — cases and the green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — observable checks
- [References](#references) — docs for path handling and prompt tests
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — work this step leaves out

## Why

`plan_tool/prompts/roadmap-seed.md` tells the model to cite the four artifacts "by their literal filenames". Seeds therefore name bare `01-domain.md` … `04-roadmap.md`. Once a roadmap has an accepted head, top-level `0N-*.md` files beside it are inert and can be stale. A reader or an audit that opens a bare name can read stale content instead of the accepted version. The loader already knows the accepted member paths, so the prompt can ask for them directly.

## Input

- **`load_accepted_roadmap_artifacts` in `plan_tool/roadmap.py`** returns four `_LoadedArtifact` values in stage order. Each carries `stage`, `path`, `text`, and `artifact`.
- **`_LoadedArtifact.path`** is the accepted version's stored member file. `_materialize_plan_seed` already derives the version id from `loaded[0].path.parent.name`, so the same read is already trusted for citations.
- **The variable-map key** is `f"{item.stage.artifact_key}_artifact"` in `_render_seed_materialize_prompt`. The placeholders the template uses today are `${domain_artifact}`, `${constraints_artifact}`, `${components_artifact}`, and `${plans_artifact}`. Confirm the `artifact_key` values against `RoadmapStage` at HEAD before naming the new variables.
- **Verification limit:** canned-response tests prove the contract is satisfiable. They do not show how often a real model follows it on the first attempt.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/roadmap.py`: compute four repo-relative POSIX path strings in `_materialize_plan_seed`, raise `RoadmapError` when a path is outside `repo_root`, and extend `_render_seed_materialize_prompt` to accept and substitute them.
  - `plan_tool/prompts/roadmap-seed.md`: ask for the exact paths everywhere the seed body names a roadmap file, and drop the "literal filenames" wording.
  - `tests/test_roadmap.py`: add the prompt-render, placeholder-subset, and conforming-response cases.

## Implementation

- **Compute the paths in `_materialize_plan_seed`**, right after `loaded` is read.
  - Resolve each `item.path` and `repo_root`, then use `Path.relative_to(...).as_posix()`.
  - The existing helper near `resolved.relative_to(Path(repo_root).resolve()).as_posix()` in `plan_tool/roadmap.py` is the pattern to follow. Reuse it if its contract fits.
  - Do not write a second normalizer if that helper can be reused unchanged.
- **Fail closed outside the repository.**
  - Catch `ValueError` from `relative_to` and raise `RoadmapError`.
  - The message names the plans directory and `repo_root`, and says no repo-relative citation exists.
  - Never fall back to a bare member name. Do this before any backend call so no tokens are spent.
- **Pass the paths into the renderer.**
  - Add a keyword parameter to `_render_seed_materialize_prompt`: one mapping or four strings, whichever is smaller.
  - Merge them into `variables` beside the artifact text.
  - Name them after the artifact key, for example `domain_path` and `plans_path`, so each is self-describing.
  - This function is private, so check its callers with `grep -n "_render_seed_materialize_prompt"`. Today the only call site is in `_materialize_plan_seed`.
- **Rewrite the prompt.**
  - Replace the sentence that cites the files "by their literal filenames" with a rule: every time the seed body names a roadmap artifact, write the exact path shown for it.
  - The rule covers `## References`, Architecture, Risks, and fenced text.
  - The rule also covers accepted artifact text the writer carries over: a member filename that appears in `${domain_artifact}` … `${plans_artifact}` is rewritten to its version-store path, never copied bare. A response that still fails the gates after the bounded retry is the existing materialize failure; no new failure path is added.
  - List the four paths once in the prompt as `${domain_path}` … `${plans_path}`.
  - The `### \`01-domain.md\`` … `### \`04-roadmap.md\`` input headings keep the bare names. They label prompt inputs, not seed text.
  - The prompt must still never ask for a `source_artifacts` key.
- **Constraints that are not free to vary:**
  - The paths and the artifact text come from the same `loaded` read. Do not re-derive paths with `stored_artifact_path` separately.
  - Use `Template.safe_substitute` as today. Write a literal `$` as `$$`.
  - Every `${name}` in the template must be a key the caller supplies.
  - The materialize write path is unchanged: it replaces the draft atomically as before, and no gate is added or loosened here.
- **Rejected alternative:** a post-generation rewrite that swaps bare names for paths in the model's output. It edits text the gates already accepted and needs a body scanner. The prompt rule is the smaller change.

## Tests

All new cases go in `tests/test_roadmap.py`, using the existing roadmap fixture helpers and an invoker stub (never the real backend).

- `test_seed_prompt_contains_each_version_store_path` — the rendered prompt has all four repo-relative `.roadmap-versions/<version-id>/…` paths.
- `test_seed_prompt_leaves_no_unresolved_placeholder` — the rendered prompt has no `${`.
- `test_seed_prompt_placeholders_are_a_subset_of_the_variable_map` — every `${name}` the template uses is a key the caller supplies. This is the only mechanical check, because the variable map lives in the caller.
- `test_seed_prompt_no_longer_asks_for_literal_filenames` — the template no longer says "literal filenames", and it still never asks for `source_artifacts`.
- `test_plans_dir_outside_repo_root_stops_with_roadmap_error` — a plans directory outside `repo_root` raises `RoadmapError` naming the problem. It does not fall back to a bare name, and the invoker is never called.
- `test_conforming_response_with_version_store_paths_is_written` — a canned conforming response citing version-store paths passes the existing gates and the draft is written.
- `test_materialize_write_still_replaces_draft_atomically` — an existing draft is replaced as before (reuse the existing assertion if one already covers it).

### Tests for this step

The cases above are the full roster. The prompt, placeholder, and fence-wording cases are written alongside the template edit. The outside-repo case is the one that protects the fail-closed rule. Every case must be green before the step is finished, along with the existing `tests/test_roadmap.py` seed cases, which must still pass unchanged.

## Acceptance criteria

- A rendered seed prompt for an accepted roadmap contains each of the four repo-relative version-store paths.
- The rendered prompt has no unresolved `${`.
- Every placeholder in `plan_tool/prompts/roadmap-seed.md` is supplied by `_render_seed_materialize_prompt`.
- `plan_tool/prompts/roadmap-seed.md` has no "literal filenames" wording and no `source_artifacts` request.
- A plans directory outside `repo_root` raises `RoadmapError` before any invoker call.
- A canned conforming response with version-store paths is accepted and written.
- `uv run pytest tests/test_roadmap.py -q` is green.
- No file outside the three declared files changes.

## References

- [pathlib — PurePath.relative_to and as_posix (Python 3 docs)](https://docs.python.org/3/library/pathlib.html) — read for the repo-relative POSIX conversion and the `ValueError` raised outside the root.
- [pytest — How to use temporary directories and files in tests](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — read for the hermetic roadmap fixture with an accepted head.

## Applicable guardrails

- **The plan's "## Scope guardrails", completeness audit:** this step does not touch the audit or its prompts, and adds no quote-matches-file check.
- **The plan's "## Scope guardrails", legacy seeds and top-level files:** no existing seed text is rewritten, and no top-level `0N-*.md` file is touched or deleted.
- **The plan's "## Scope guardrails", `create` behavior:** nothing changes in how `create` synthesizes plan prose.
- **The plan's "## Audit guardrails", plans directory outside the repository:** this step stops with `RoadmapError` rather than inventing a citation, and surfaces the case instead of adding a new link record or changing the version layout.

## Deferred

- Bare roadmap file names in prose `create`'s model writes during synthesis — new `create` behavior; the plan's "## Out of scope" records the decision and the follow-up on the source `BUG_BACKLOG.md` entry.
- Rewriting legacy seed text in place — dropped by the plan's "## Out of scope", with the reason recorded there.
- Draft-seed gates that check citation form — owned by a separate step of this plan, not this one.
