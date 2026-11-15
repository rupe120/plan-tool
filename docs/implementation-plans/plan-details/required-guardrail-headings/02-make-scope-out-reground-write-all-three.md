# Step 2 — Carry the three guardrail headings into scope-out and reground seeds

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step adds one block helper to `plan_tool/scope_fence.py`, next to `source_references_block`. For each of the three required guardrail headings, the helper copies the source plan's body verbatim when step 1's rule accepts it, and otherwise writes `_(TODO)_`. `scope_out.render_carved_seed`, `scope_out.render_carved_region_seed` and `reground.render_rebaseline_seed` call the helper, and step 3's `annotate` will call it too. The seed callers (`scope_out_step` and `reground_bridge`) pass the source plan body, and the printed next steps list each heading as "inherited, review before `create`" or "unfilled, fill in by hand". Only seed text and printed text change. On green, a carved or re-baselined seed always has all three headings, so it can pass step 1's check without anyone inventing a fence.

## Table of Contents

- [Why](#why) — why seeds need all three headings
- [Input](#input) — what step 1 provides and how the source body is read
- [Files (creates vs edits)](#files-creates-vs-edits) — the seven files touched
- [Implementation](#implementation) — helper contract, call sites, next-step text
- [Tests](#tests) — cases per test file
- [Acceptance criteria](#acceptance-criteria) — observable results
- [References](#references) — code and docs to read
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — work left to other steps

## Why

The three renderers write `## References` and an intent line, but no guardrail headings. Once `create --from-existing` refuses a seed missing them (step 1's check, wired in a later step), every carved or re-baselined seed would be refused. The parent plan's fence is the only real source for these headings. Copying it forward keeps the fence. Writing `_(TODO)_` where the parent has nothing usable keeps the operator from mistaking an invented fence for an inherited one. Today `scope_out_step` and `reground_bridge` read only the `references` section from the source body, so the guardrail bodies are never read.

## Input

- **Step 1's check.** Step 1 adds the required-heading constant and a pure function in `plan_tool/scope_fence.py` that reports headings that are missing, duplicated, empty or placeholders. This step reuses that rule through the shared constant and `extract_h2_section_occurrences`. Read the landed names off the module at implementation time. The landed names win over any spelling in this file.
- **Source body.** Both callers already read the source plan body from disk: `scope_out_step` via `_split_frontmatter(...).body`, and `reground_bridge` via `_strip_frontmatter`. The helper takes that body text.
- **Limit on verification.** `extract_h2_sections` drops empty bodies and keeps the first non-empty duplicate, so it cannot tell "duplicated" or "empty" from "absent". The helper must read `extract_h2_section_occurrences` instead.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/scope_fence.py`: add the block helper (and one small companion that reports which headings were inherited) next to `source_references_block`.
  - `plan_tool/scope_out.py`:
    - `render_carved_seed` and `render_carved_region_seed` accept the source body (or the helper's rendered result) and write the three headings.
    - `scope_out_step` passes the source body in.
    - `ScopeOutResult` gains the inherited and unfilled heading lists the CLI prints.
  - `plan_tool/reground.py`:
    - `render_rebaseline_seed` writes the three headings.
    - `reground_bridge` passes the source body in.
    - The confirmation notice in the function that prints "A `plan-tool create --from-existing` re-baseline seed will also be written" names the headings.
    - `RegroundResult` carries the same two lists if the notice needs them after the write.
  - `plan_tool/cli/scope_out_cmd.py`: `render_scope_out_result` prints the inherited and unfilled headings in the `applied` branch.
  - `tests/test_scope_out.py`, `tests/test_reground.py`, `tests/cli/test_scope_out_cmd.py`: new cases below.

## Implementation

- **Helper contract.**
  - Name it something like `guardrail_headings_block(source_body: str | None) -> tuple[list[str], tuple[str, ...], tuple[str, ...]]`, returning the seed lines, the inherited headings and the unfilled headings. Keep the final shape the implementer's call.
  - It emits the three H2 headings in constant order, each followed by a blank line, the body, and a blank line. This mirrors `source_references_block`'s shape.
  - **Copy rule.** Copy the body verbatim only when step 1's rule accepts it:
    - exactly one fence-safe occurrence of the heading;
    - a non-empty body;
    - `_is_placeholder_section` false.
  - A body of `None` is accepted and copied as `None`. Do not touch `_SECTION_PLACEHOLDER_RE` or add `None` handling.
  - **Every other source state** writes `_(TODO)_`: absent, empty, duplicated, or `_(TODO)_`. This includes a `None` source body.
  - Build it from the same calls step 1 uses: `_strip_frontmatter`, `_fenced_code_spans` once, then `extract_h2_section_occurrences(..., strip_fenced_code=True, fenced_spans=...)`. Do not write a second fence recognizer.
  - **Verbatim body.** The check runs with fenced text stripped, but the copied text must be the real body, fences included. Take the body from the occurrence found without stripping fences (`ignore_fenced_code=True`), as `source_references_block`'s callers do. Pin this with a test. If the two readings disagree about whether exactly one occurrence exists, one way to settle it is to decide acceptance from the stripped reading and copy from the unstripped one.
- **One shared rule.** The renderers must not each re-derive the rule. They take the helper's output. This is the same rule step 3's `annotate` uses, so keep the helper's signature free of scope-out or reground types.
- **Model-supplied bodies (step 3 only).** The helper takes an optional mapping of model-written bodies, one per heading; `scope-out` and `reground` pass none. Where the source heading is not accepted, a model body is used only if step 1's `is_acceptable_guardrail_body` accepts it; the source-copy path uses the same function. Any other model body, including one missing from the mapping, gives `_(TODO)_`, and the companion reports that heading as unfilled. `None` is an accepted body. The decision is per heading: a heading the source carries acceptably is always inherited, the model body is consulted only for a heading the source lacks, and a model body never replaces an inherited one. A partial response fills what it can.
- **Call sites.**
  - `render_carved_seed` and `render_carved_region_seed` both end their body with `source_references_block(...)`. Add the helper's lines just before it.
  - `render_rebaseline_seed` does the same before `source_references_block(...)`.
  - The renderers stay pure string builders, with no file IO. Pass the already-read body in as a keyword argument defaulting to `None`, so existing callers and tests still render (every heading `_(TODO)_`).
  - `scope_out_step` has one place that builds `source_references` from the body. Both the single-step and the region render call sites use that body.
- **Next-step text.**
  - **Scope-out.** In the `applied` branch of `render_scope_out_result`, after the `wrote seed` line, print one line per group:
    - inherited headings: "review before `create`: the parent's fence can be wrong for the narrower plan";
    - `_(TODO)_` headings: "fill in by hand before `create`".
  - Print a group only when it is non-empty. When neither group exists, nothing is printed.
  - **Reground.** Extend the re-baseline notice with the same two lines. Use a `RegroundResult` field if the printed text comes after the write.
  - Neither path gains a model call. Do not change the `recommended`, `unsafe`, `empty-plan` or `step-missing` branches.
- **Destructive operations stay as they are.** This step must not change:
  - scope-out narrowing the source plan and archiving carved detail files;
  - the seed-file writes and their ordering;
  - reground's mark-done and the seed-first ordering.
  - Only the string passed to `seed_path.write_text` changes.
- **Shared locations found.**
  - `plan_tool/create.py` already has a parallel copy-or-TODO path for `create`'s own plan body (`_render_plan_body` with `GUARDRAIL_BODY_SECTIONS`). It copies guardrails and `Stack` from the original seed. This step leaves it unchanged (see Deferred).
  - `render_scope_fence` and `extract_plan_guardrails` read the guardrail sections from a plan body. They answer a different question: what to feed downstream prompts. Do not reuse them for seed rendering.
- **Smallest proof.** The shortest path is: read the source body, accept or reject each heading by step 1's rule, write the copy or `_(TODO)_`. A new persisted record, config option or per-heading state object is not needed. The result lists on `ScopeOutResult` and `RegroundResult` are needed only because the printed text cannot recompute them from the seed.

## Tests

Test files: `tests/test_scope_out.py`, `tests/test_reground.py`, `tests/cli/test_scope_out_cmd.py`. Add a helper-level case to `tests/test_scope_fence.py` only if step 1's class there makes it cheap; otherwise the renderer tests cover the helper.

### Tests for this step

All of these must be green before the step is done.

- `tests/test_scope_out.py`:
  - `test_carved_seed_copies_guardrails_verbatim_from_source` — all three bodies appear unchanged under their headings.
  - `test_carved_seed_copies_a_none_body_verbatim` — a `None` body is copied and not replaced with `_(TODO)_`.
  - `test_carved_seed_writes_todo_for_absent_empty_duplicated_or_placeholder_heading` — parametrized over the four source states; each gives `_(TODO)_` under that heading only.
  - `test_carved_seed_keeps_fenced_text_in_a_copied_body` — a copied body that contains a fenced block comes back with the fence intact.
  - `test_carved_region_seed_applies_the_same_copy_rule` — the region renderer matches the single-step renderer.
  - `test_scope_out_step_seed_file_carries_all_three_headings` — end-to-end through `scope_out_step` on a source plan with a mix of states; the written seed passes step 1's check when no heading is `_(TODO)_`, and fails it only on the `_(TODO)_` ones.
  - `test_scope_out_narrowing_and_detail_archival_unchanged_by_guardrail_copy` — the narrowed plan and archived detail files match the pre-change behavior (the carve-out is deliberate and pinned).
- `tests/test_reground.py`:
  - `test_rebaseline_seed_copies_guardrails_verbatim_including_none` — verbatim copy, `None` included.
  - `test_rebaseline_seed_writes_todo_for_absent_empty_duplicated_or_placeholder_heading` — parametrized over the four states.
  - `test_rebaseline_notice_names_inherited_and_unfilled_headings` — the confirmation text lists both groups.
  - `test_reground_mark_done_unchanged_when_seed_gains_guardrails` — marking and seed-first ordering are unchanged.
- `tests/cli/test_scope_out_cmd.py`:
  - `test_next_steps_name_inherited_headings_for_review` — output names each inherited heading.
  - `test_next_steps_name_todo_headings_to_fill_in` — output names each `_(TODO)_` heading.
  - `test_next_steps_omit_a_group_that_is_empty` — no stray line when every heading is inherited, or when every heading is `_(TODO)_`.
  - `test_next_steps_unchanged_for_recommended_unsafe_and_step_missing_outcomes` — the other branches print the same text.

Verify by mutation: change the helper to accept an empty body, then to treat `None` as a placeholder, and confirm each change turns a test red.

## Acceptance criteria

- Every seed written by `scope_out_step` (single-step and region) and by `reground_bridge` under re-baseline contains all three headings, in constant order, each exactly once.
- A heading whose source state is exactly-one, non-empty and not a placeholder (a `None` body included) has a body copied verbatim from the source plan.
- A heading that is absent, empty, duplicated or `_(TODO)_` in the source has the body `_(TODO)_`.
- `render_scope_out_result` and the re-baseline notice name each inherited heading as one to review before `create`, and each `_(TODO)_` heading as one to fill in by hand.
- No new model call: neither renderer imports or takes an invoker.
- The narrowed source plan, archived detail files and mark-done results are identical to the results before this step.
- `plan_tool/scope_fence.py` still has no first-party imports beyond what it has at HEAD.
- `uv run pytest tests/test_scope_out.py tests/test_reground.py tests/cli/test_scope_out_cmd.py tests/test_duplication.py -q` passes. The duplication guard stays at baseline zero.

## References

- `plan_tool/scope_fence.py` (`source_references_block`, `extract_h2_section_occurrences`, `GUARDRAIL_BODY_SECTIONS`, `_is_placeholder_section`)
- `plan_tool/scope_out.py` (`render_carved_seed`, `render_carved_region_seed`, `scope_out_step`)
- `plan_tool/reground.py` (`render_rebaseline_seed`, `reground_bridge`)
- `plan_tool/cli/scope_out_cmd.py` (`render_scope_out_result`)
- `SEED_FORMAT.md`; `docs/how-to/pipeline/create-from-existing.md`

## Applicable guardrails

- **The plan's "## Scope guardrails", presence-only check.** This step copies or writes `_(TODO)_` by presence state. It must not judge, compare or shorten guardrail content, and must not warn about what a copied body says.
- **The plan's "## Scope guardrails", `None` must pass.** The helper must not add `None` to the placeholder pattern; a `None` body is copied like any other content.
- **The plan's "## Scope guardrails", no new model call.** Both renderers fill headings only from the source plan they already read. Neither gains an invoker.
- **The plan's "## Out of scope", `## Stack`, `## Outcome`, `## In scope`.** The helper writes only the three required headings. It must not write `## Stack`, `## Outcome` or `## In scope`.
- **The plan's "## Out of scope", archived seeds and inline `--from`.** Existing seed files on disk are not rewritten.

## Deferred

- `annotate`'s use of the shared helper — step 3 owns it; this step only makes the helper's signature reusable.
- Wiring step 1's check into `create --from-existing` and the roadmap draft gate — later steps own the refusal; this step only makes these seeds pass it.
- Consolidating this copy-or-`_(TODO)_` rule with `create._render_plan_body`'s guardrail handling — a cross-module merge that needs its own home decision and tests; file in `BACKLOG.md` if wanted, not part of this step.
- Updating the docs that describe seed shape (`SEED_FORMAT.md`, `docs/how-to/pipeline/create-from-existing.md`) — the plan's docs step owns it.
