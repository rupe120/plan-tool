# Step 6 — Turn on the guardrail-heading refusal in `classify_file_backed_source`

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step makes `plan_tool/create.py:classify_file_backed_source` call step 1's shared check and raise one `CreateError` before any model call. The error names every offending guardrail heading, together with the `## References` problem when both fail. The three guardrail entries in `OPTIONAL_PLAN_BODY_SECTION_SHAPES` change from "Conditional" wording to required-and-verbatim wording, and `Stack` stays conditional. The seed fixtures that feed `--from-existing` gain the three headings, and new tests pin each refusal at the CLI and `create_plan` seams. No seed writer changes here; steps 2 to 5 already make the writers emit the headings. On green, a seed lacking a guardrail heading is refused with no backend call, and a seed whose heading body is `None` is accepted.

## Table of Contents

- [Input](#input) — what steps 1 to 5 provide and the existing call sites
- [Why](#why) — why the refusal turns on last
- [Files (creates vs edits)](#files-creates-vs-edits) — files touched
- [Implementation](#implementation) — the check, the error, the shape text, the fixture sweep
- [Tests](#tests) — refusal, acceptance and mutation cases
- [Acceptance criteria](#acceptance-criteria) — observable results
- [References](#references) — code and docs to read
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — work left to other steps

## Input

- **Step 1.** It adds a constant for the three headings and a pure function in `plan_tool/scope_fence.py` that returns every heading that is missing, duplicated, empty or a placeholder. `None` passes. At HEAD of this drafting neither name exists (`rg missing_required_guardrail_headings plan_tool` returns nothing). Read the landed names off `plan_tool/scope_fence.py`. The landed names win over any spelling here.
- **Steps 2 to 5.** Steps 2, 3 and 4 make `scope-out`, `reground`, `annotate` and roadmap materialization write the headings. Step 5 edits the live seeds by hand. Turning the refusal on before they land would refuse their output.
- **Call sites at HEAD.** One function owns the rule, and three paths reach it:
  - `plan_tool/create.py:validate_from_existing_seed` is a one-line wrapper around `classify_file_backed_source`.
  - `plan_tool/cli/authoring.py` calls `validate_from_existing_seed` before the slug is resolved.
  - `plan_tool/create.py:create_plan` calls `validate_from_existing_seed` in its intake, before any invoker call.
- **Existing rule shape.** `classify_file_backed_source` already raises `CreateError` for `## References` when the heading count is not exactly one, the body is empty, or `_is_placeholder_section` is true.
- **Limit on verification.** The tests prove the refusal fires before an invoker call. They do not prove operators will find the error text clear. That needs real use.

## Why

The plan's outcome is that a `--from-existing` seed states each guardrail, with `None` as a valid answer, so a missing fence cannot pass as a deliberate one. Only `## References` has a presence rule today, and the three guardrail headings pass through `create` as optional text. The refusal goes in the one function every path shares, so no route skips it. The step comes last because turning it on makes every seed without the headings fail. The writers (steps 2 to 4) and the live seeds (step 5) must emit them first.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/create.py`:
    - `classify_file_backed_source` calls step 1's check and raises the combined error.
    - The three guardrail entries in `OPTIONAL_PLAN_BODY_SECTION_SHAPES` change to required-and-verbatim wording.
  - `plan_tool/cli/authoring.py`: expected to need no edit, because the pre-slug call already reaches the function. Edit only if a test shows the error is caught or reworded before it prints.
  - `tests/test_create.py`: fixture sweep plus the new `create_plan`-seam and `None` carry-through cases.
  - `tests/cli/test_authoring_cmds.py`: fixture sweep plus the CLI-seam refusal cases.
  - `tests/test_cli.py`, `tests/test_distill.py`, `tests/test_review.py`: fixture sweep.
  - `tests/test_scope_fence.py`: add the `render_scope_fence` downstream-fence assertion for a `None` body, only if step 1 did not already add it.
  - Other test files that a grep for `from_existing` returns get the same fixture sweep. At HEAD that grep also lists `tests/test_reground.py`, `tests/test_scope_out.py`, `tests/test_roadmap.py`, `tests/test_annotate_render.py`, `tests/cli/test_roadmap_cmd.py`, `tests/cli/test_manifest_cmds.py` and `tests/cli/test_scope_out_cmd.py`. Edit one only if it goes red, and say so in the handoff because those paths are outside the declared list.

## Implementation

- **Where the check goes.**
  - Call step 1's function inside `classify_file_backed_source`, on the text the function already prepared (frontmatter stripped, fence scan done). One way: call the step 1 function on `source_text` directly, since it does its own strip and scan. Do not write a second heading reader or fence recognizer.
  - Run it after the unmatched-fence rejection (`reject_unmatched_create_fence`), so an unclosed fence still reports its own error first.
- **One error, every offender.**
  - Collect the `## References` problem and the guardrail offenders first, then raise once. An operator with a bad `References` and two bad guardrails sees all three in one message.
  - Name each guardrail heading with its `## ` spelling. Say what a valid heading is: exactly one section with a non-empty, non-placeholder body, where `None` counts as an answer.
  - Keep the existing `References` wording. Add the new text beside it.
  - Keep the closing line "no authoring model was invoked" so the refusal still says it happened before any model call.
- **Rejected alternatives.**
  - A second `CreateError` raised from the CLI layer. The function is the shared owner, and a CLI-only check leaves `create_plan` callers unguarded.
  - A warning instead of a refusal. The plan requires refusal.
- **Do not touch the placeholder rule.** `_is_placeholder_section` and `_SECTION_PLACEHOLDER_RE` stay unchanged so `None` counts as content. Do not add `None`, `N/A` or similar to the pattern.
- **Shape text.**
  - Rewrite the three entries in `OPTIONAL_PLAN_BODY_SECTION_SHAPES` to say the section is required and the supplied body is preserved verbatim, with no invention or revision.
  - Leave `Input` and `Stack` unchanged.
  - `_render_section_shapes_block` tags every entry in `_OPTIONAL_PLAN_BODY_SECTIONS` as `[conditional]`, so a required entry would carry a wrong tag. Decide the smallest fix: a direct check that tags the three headings differently, or wording in the shape text that already makes the tag harmless. Check `rg "\[conditional\]" tests plan_tool` before choosing.
  - Run `rg "Conditional, source-backed" tests plan_tool` to find tests that pin the old wording.
- **Fixture sweep (the expected red).**
  - Run the suite once with the refusal on. Each red test that feeds `--from-existing` a seed without the headings gets the three headings added to its fixture.
  - A heading body of `None` is enough where the test does not care about the fence.
  - Do not narrow the rule to turn a test green. A red sibling is expected here and not a reason to weaken the check.
  - Where a test deliberately uses a seed without a heading (for example, the existing `References` refusal tests), add the headings so the test still isolates its own failure.
  - Prefer one shared fixture helper per test file over repeating the block, if a file has more than two seeds to fix.
- **Seed-writer tests.**
  - For `scope-out`, `reground`, `annotate` and roadmap materialization, feed each writer's seed output into `classify_file_backed_source` when the source carries guardrails, and assert it passes. Use the writers' own entry points from steps 2 to 4. Read their landed names off those modules.
  - Feed a deterministic renderer's `_(TODO)_` output in and assert refusal.
- **Constraint: refusal only.** This step touches no write path. If a writer test fails, fix it in the writer's own step, not here.
- **Verify by mutation.** After the tests pass, break the check (for example, return an empty tuple from the step 1 call inside `classify_file_backed_source`) and confirm every refusal test goes red. Restore it.

## Tests

- `tests/test_create.py` and `tests/cli/test_authoring_cmds.py` use an invoker that fails if called.

### Tests for this step

- `test_missing_guardrail_heading_is_refused_before_any_model_call` — parametrized over the three headings; each missing heading raises `CreateError` naming it; invoker never called; `create_plan` seam.
- `test_duplicated_guardrail_heading_is_refused_before_any_model_call` — same, for a heading present twice.
- `test_empty_guardrail_heading_is_refused_before_any_model_call` — same, for an empty body.
- `test_todo_placeholder_guardrail_heading_is_refused_before_any_model_call` — same, for a `_(TODO)_` body.
- `test_cli_refuses_seed_with_bad_guardrail_heading_before_slug_resolution` — parametrized over the four offences at the `main(["create", ...])` seam; non-zero return; error text names the heading; invoker never called.
- `test_two_missing_guardrail_headings_are_both_named_in_one_error` — one `CreateError` lists both.
- `test_guardrail_offence_and_references_problem_are_reported_together` — bad `References` plus a bad guardrail yields one error naming both.
- `test_none_guardrail_body_is_accepted_and_written_verbatim` — a seed with `None` under all three headings is accepted; the written plan body carries `None` under each heading.
- `test_none_guardrail_body_reaches_the_rendered_scope_fence` — `render_scope_fence` on that plan carries `None` verbatim (in `tests/test_scope_fence.py` unless step 1 already pinned it).
- `test_seed_from_each_writer_passes_when_source_carries_guardrails` — parametrized over `scope-out`, `reground`, `annotate` and roadmap materialization.
- `test_deterministic_renderer_todo_guardrail_is_refused` — a renderer's `_(TODO)_` body is refused, since the operator must fill it.
- `test_stack_heading_stays_optional` — a seed with the three guardrails and no `## Stack` is accepted. This is the deliberate carve-out.
- `test_guardrail_shape_text_is_required_and_stack_stays_conditional` — pins the new wording on the three entries and the unchanged `Stack` wording.
- Fixture-swept tests in the five named files and any others that went red; each must be green.
- **Gate:** every test above, plus the full suite (`uv run pytest tests/ -q -n auto`, background it), must be green before the step is done. Then run the mutation check from Implementation and confirm each refusal test goes red.

## Acceptance criteria

- `classify_file_backed_source` raises `CreateError` for a seed with any guardrail heading missing, duplicated, empty or `_(TODO)_`, and the error names each offender.
- `create_plan` and `plan-tool create --from-existing` both refuse such a seed with the invoker uncalled.
- A seed whose guardrail body is `None` is accepted, and `None` appears in the written plan and its fence.
- A seed without `## Stack` is accepted.
- `rg "_is_placeholder_section|_SECTION_PLACEHOLDER_RE" plan_tool/scope_fence.py` shows no new placeholder token.
- The shape text of the three guardrail entries is required-and-verbatim, and `Stack` is unchanged.
- No file under `plan_tool/` other than `plan_tool/create.py` (and `plan_tool/cli/authoring.py` only if needed) has a diff.
- Breaking the check turns every refusal test red.
- The full suite is green.

## References

- `plan_tool/create.py` (`classify_file_backed_source`, `validate_from_existing_seed`, `OPTIONAL_PLAN_BODY_SECTION_SHAPES`, `_render_section_shapes_block`) — the refusal site and the shape text.
- `plan_tool/scope_fence.py` (`GUARDRAIL_BODY_SECTIONS`, `_is_placeholder_section`, `render_scope_fence`, step 1's additions) — the shared check and the fence a `None` body must reach.
- `SEED_FORMAT.md`; `PLAN_FORMAT.md` § "Scope fence"; `docs/how-to/pipeline/create-from-existing.md` — the seed contract the refusal enforces; the docs themselves are outside this step.
- `TESTING.md` — the invoker neutralization table for the "never called" assertions.

## Applicable guardrails

- The plan's "## Scope guardrails", presence-only check: this step adds the refusal and no judgment of guardrail content. The step 1 predicate is the only rule applied.
- The plan's "## Scope guardrails", `None` must pass: do not touch the placeholder pattern.
- The plan's "## Scope guardrails", required headings: do not require `Stack`, `Outcome` or `In scope`. Do not touch inline `--from`, `--from-plan` or archived seeds.
- The plan's "## Scope guardrails", no new model call: this step adds none, and the refusal happens before any call.
- The plan's "## Out of scope": no quality check, no agreement check against `Out of scope`, no length or shape cap, and no exit-code change beyond the refusal.
- The plan's "## Audit guardrails" and "## Expected placement" set no extra boundary for this step.

## Deferred

- Seed-writing changes in `scope-out`, `reground`, `annotate` and roadmap materialization — owned by steps 2, 3 and 4; this step only consumes their output.
- Hand edits to live seeds — owned by step 5.
- Real-model measurement of how often a roadmap or annotate draft writes the headings correctly — needs real runs the suite cannot supply.
- Documentation of the new refusal in `SEED_FORMAT.md`, `PLAN_FORMAT.md` and `docs/how-to/pipeline/create-from-existing.md` — outside this step's declared files.
- Consolidating duplicate seed fixtures across test files — a separate refactor, routed to `BACKLOG.md` if wanted.
