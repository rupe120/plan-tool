# Step 4 — Require the three guardrail headings in roadmap draft seeds

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step makes roadmap draft seeds carry `Scope guardrails`, `Audit guardrails` and `Expected placement`. `plan_tool/prompts/roadmap-seed.md` adds the three headings to its required section list and says to write them from the accepted plan row, using `None` where the row sets no fence. `plan_tool/roadmap_gates.py:validate_draft_seed_content` calls step 1's shared check and returns one violation per offending heading. Every existing caller of that gate then picks the rule up with no edit to `plan_tool/roadmap.py` or `plan_tool/roadmap_seed_manifest.py`. A draft missing a heading uses up an attempt in `materialize_plan_seed`'s retry loop, with the violation message as the correction. A draft written before this change is classified malformed, and its message names `--refresh-seeds`.

## Table of Contents

- [Input](#input) — what step 1 provides and the existing gate call sites
- [Why](#why) — why the draft gate must match `create`
- [Files (creates vs edits)](#files-creates-vs-edits) — the files touched
- [Implementation](#implementation) — prompt edit, gate edit, message contract, constraints
- [Tests](#tests) — gate, retry, prompt and existing-draft cases
- [Acceptance criteria](#acceptance-criteria) — observable results
- [References](#references) — code and docs to read
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — work left to other steps

## Input

- **Step 1.** Step 1 adds a constant naming the three headings and a pure function in `plan_tool/scope_fence.py`. The function reports every heading that is missing, duplicated, empty or a placeholder, and `None` passes. Neither exists at HEAD of this drafting (`rg missing_required_guardrail_headings plan_tool` returns nothing). Read the landed names off `plan_tool/scope_fence.py` at implementation time. The landed names win over any spelling here.
- **Gate call sites at HEAD.** All of these call `validate_draft_seed_content` and need no edit:
  - the `--accept-seed` path in `plan_tool/roadmap.py` (after the digest-mismatch classification, before the copy)
  - the promotion path in `plan_tool/roadmap.py` (the `post_classification_refusals` loop, which also builds a `DRAFT_SEED_STATE_MALFORMED` classification)
  - the materialize retry loop in `plan_tool/roadmap.py` (`candidate_violations` on the lifted response)
  - the unmatched-fence pre-check that picks out `VIOLATION_DRAFT_SEED_UNMATCHED_FENCE`
  - the classifier in `plan_tool/roadmap_seed_manifest.py`
- **Early return.** The gate returns early on an unmatched opening fence or invalid provenance. The new check runs on the same path as the `## References` and `## Risks` checks, after those two early returns.
- **Limit on verification.** Canned-reply tests show the contract can be met. They do not show a real model usually writes the headings, or writes `None` only where the row sets no fence. That needs real runs.

## Why

`create --from-existing` refuses a seed missing a guardrail heading. Today the roadmap gate has no such rule, so `--accept-seed` can promote a draft that `create` then refuses. The step's intent is that a seed the roadmap accepts is never one `create` refuses. The gate already checks `## References` and `## Risks` by the same shape of rule, so the headings belong in the same function. Putting the check there also feeds the retry loop for free: a draft missing a heading is corrected at materialization, before the operator reviews it.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/prompts/roadmap-seed.md`: add the three headings to the "Use these sections exactly" list and one short instruction on how to fill them.
  - `plan_tool/roadmap_gates.py`:
    - add one `VIOLATION_*` kind constant for a bad guardrail heading
    - extend `validate_draft_seed_content` to call step 1's check and append one violation per offender
    - import the step 1 names from `plan_tool/scope_fence.py`
  - `tests/test_roadmap_gates.py`: gate cases, plus a one-line import of the new kind constant.
  - `tests/test_roadmap.py`: update the canned seed replies, add the retry case, the prompt-containment case and the existing-draft case.
  - `tests/cli/test_roadmap_cmd.py`: update any canned draft seed text that goes through the real gate. Check each fixture; most patch `materialize` and need no change.
- **Not edited, deliberately:** `plan_tool/roadmap.py` and `plan_tool/roadmap_seed_manifest.py`. Every caller already routes through the gate, so a gate edit reaches them. A test failing in either file's suite means a canned draft lacks the headings, so fix the fixture.

## Implementation

- **Prompt edit.**
  - Add the three headings to the section list, in the order step 1's constant uses.
  - Name the sources per heading. `## Scope guardrails` comes from the plan row's `non_goals` and from the settled decisions and constraints the row's components own in the accepted artifacts. `## Audit guardrails` and `## Expected placement` come only from content in those artifacts that states an audit boundary or a placement for this row; the roadmap schema has no field for either, so they are usually `None`.
  - Use the step 3 proportionality wording for both model-written paths: write only fences the row and its accepted artifacts already imply, use `None` when they imply none, and add no scope, mechanism or requirement.
  - Say to write the bare word `None` as the body where those sources set no fence. Do not tell the model to leave a heading out, and do not suggest `N/A` or `_(TODO)_`.
  - Restate the rule inline. No template under `plan_tool/prompts/` cites a `*_FORMAT.md` doc, and none can.
  - If you need a literal `$`, write `$$`. The template renders with `safe_substitute`.
  - Keep the edit to a few lines. The prompt already carries long scope-fence guidance, and this step adds no new input variable.
- **Gate edit.**
  - Call step 1's function on the draft text and emit one `Violation` per returned heading. Do not stop at the first.
  - Reuse the existing `Violation` shape and message style: `artifact=PLANS_FILENAME`, `row_id=plan.id`, a message naming the plan id and the draft basename.
  - Each message must be self-contained, because the retry loop pastes it as a bare bullet. It must name the heading, say what is wrong in plain terms (missing, duplicated, empty or a placeholder), and give the remedy: write the section, or write `None` if the row sets no fence.
  - Do not reproduce step 1's reason text if the function returns only titles. Say "missing, duplicated, empty or a placeholder" once and keep the message short.
  - Do not use line numbers or offsets.
  - Place the new check beside the `## Risks` check, so a draft failing several rules reports them together.
  - Take the `_(TODO)_` rule from `plan_tool/scope_fence.py`. Do not restate the placeholder pattern here.
- **Refusal message names the route.**
  - A draft materialized before this change fails the gate when classified, accepted or promoted.
  - Its one stated route is `plan-tool roadmap <slug> --refresh-seeds`, which re-materializes it with the headings.
  - Put that route in every guardrail violation message, so the classifier's malformed detail, the `--accept-seed` refusal and the promotion refusal all carry it. One way: end the message with "re-run `--refresh-seeds` to rewrite this draft".
  - Confirm the exact flag spelling against `plan_tool/cli/parser.py` (`rg refresh-seeds plan_tool/cli`) before writing the text.
  - The same text goes to the model in the retry loop, where mentioning `--refresh-seeds` is harmless. Do not add a second message variant for it.
- **Destructive operations unchanged.**
  - The draft-seed write and the sidecar that commits last stay as they are, so an interrupted write is still detectable.
  - Do not touch the write order, the digest recording or the refresh's replacement rules. The refresh already rewrites a malformed draft. This step adds only a new reason for a draft to be malformed.
- **Smallest proof.** The shortest path is one added call in the gate plus a prompt edit. Do not add a new classification state, a migration pass for old drafts or a bulk rewrite command. The existing `--refresh-seeds` is the route.
- **Constraints the implementer must keep.**
  - The check is presence only, by the same rule as `## References`. Do not judge, compare or cap guardrail content.
  - `None` must pass. Do not add `None`, `N/A` or similar to the placeholder pattern.
  - Do not require `## Stack`, `## Outcome` or `## In scope` here.
  - `roadmap_gates.py` must keep its single first-party edge set, plus `scope_fence`, which it already imports. Do not import `review` or `create`.
  - `plan_tool/gates.py` is the unrelated `gate:` command suggester. Do not touch it.

## Tests

### Gate cases in `tests/test_roadmap_gates.py`

Build the draft text with the existing draft-seed helper in that file, and add the three headings to its conforming fixture. Without that, every existing draft-seed case turns red for the wrong reason.

- `test_draft_seed_missing_guardrail_heading_is_a_violation` — a draft lacking one heading yields exactly one violation of the new kind naming that heading.
- `test_every_offending_guardrail_heading_is_reported_not_the_first` — a draft lacking all three yields three violations in constant order.
- `test_duplicated_guardrail_heading_is_a_violation` — two `## Scope guardrails` sections are flagged.
- `test_empty_guardrail_heading_is_a_violation` — a heading with no body is flagged.
- `test_todo_placeholder_guardrail_heading_is_a_violation` — a `_(TODO)_` body is flagged.
- `test_none_guardrail_body_is_accepted_as_content` — a body of `None` passes. This pins the deliberate carve-out: `None` is how a row says it sets no fence.
- `test_guardrail_heading_inside_a_code_fence_does_not_count` — a heading shown only in a fenced example is treated as missing.
- `test_guardrail_violation_message_names_refresh_seeds_route` — the message names `--refresh-seeds` and the heading, so a retry bullet and a refusal are both actionable alone.

### Cases in `tests/test_roadmap.py`

- Update every existing canned seed reply that passes the real gate so it carries all three headings. Use `None` bodies where no fence is needed.
- `test_materialize_retries_when_a_guardrail_heading_is_missing` — the first reply lacks a heading, the second has it. The invoker is called twice, the second prompt contains the violation message, and the written draft is the second reply.
- `test_materialize_exhausts_budget_on_persistently_missing_heading` — every reply lacks a heading. The run ends in the same exhausted outcome as for any other violation, and writes no draft and no sidecar entry.
- `test_roadmap_seed_prompt_names_all_three_guardrail_headings` — the rendered template contains each of the three headings and the word `None`. It is a containment test against step 1's constant, so a rename turns it red.
- `test_roadmap_seed_prompt_has_no_unresolved_placeholder` — rendering with the existing variable map leaves no `${`. This guards the `$$` rule.
- `test_pre_change_draft_without_guardrail_headings_is_malformed_and_refresh_clears_it` — one test over four steps, using a draft on disk with a matching sidecar digest:
  - classification returns `DRAFT_SEED_STATE_MALFORMED` with a detail naming `--refresh-seeds`
  - `--accept-seed` refuses with that same message and does not promote
  - a refresh with a canned reply carrying the headings rewrites the draft
  - the draft then classifies as current

### Tests for this step

Every case above must be green before this step is finished, and the tests above cover the one behavior this step changes: the draft gate's guardrail rule and its reach through the retry loop, the classifier and the refusals. Run `uv run pytest tests/test_roadmap_gates.py tests/test_roadmap.py tests/cli/test_roadmap_cmd.py tests/test_scope_fence.py -q`, then the full suite with `-n auto`. A red sibling test in `tests/test_roadmap.py` or `tests/cli/test_roadmap_cmd.py` is expected where a canned draft lacks the headings. Read each one and update the fixture. Do not narrow the gate. Check the new cases by mutation: remove the gate call and confirm the missing-heading and retry cases go red.

## Acceptance criteria

- `validate_draft_seed_content` returns one violation per missing, duplicated, empty or `_(TODO)_` guardrail heading, and none for a body of `None`.
- A draft missing a guardrail heading uses one attempt in `materialize_plan_seed`'s retry loop, and the next prompt contains the violation message.
- `plan_tool/prompts/roadmap-seed.md` names all three headings, names each one's source in the row and its accepted artifacts, carries the step 3 proportionality line, and tells the model to write `None` where those sources set no fence.
- A draft without the headings classifies as `DRAFT_SEED_STATE_MALFORMED`. Its detail, and the `--accept-seed` refusal, name `--refresh-seeds`.
- A `--refresh-seeds` run on such a draft produces a draft that classifies as current.
- `git diff --stat` shows only the five declared files. In particular `plan_tool/roadmap.py` and `plan_tool/roadmap_seed_manifest.py` have no diff.
- `rg "N/A" plan_tool/scope_fence.py` shows the placeholder pattern unchanged by this step.
- The full test suite passes.

## References

- `plan_tool/roadmap_gates.py` (`validate_draft_seed_content`, `_draft_seed_sections`, `VIOLATION_MISSING_DRAFT_SEED_RISKS`) — the gate to extend and the nearest existing rule.
- `plan_tool/scope_fence.py` (step 1's check, `_is_placeholder_section`) — the shared rule to call.
- `plan_tool/roadmap.py` (`materialize_plan_seed`) — the retry loop that consumes the violations.
- `plan_tool/roadmap_seed_manifest.py` — the classifier that turns violations into the malformed state.
- `plan_tool/prompts/roadmap-seed.md` — the template to edit.
- `plan_tool/create.py` (`classify_file_backed_source`) — the `## References` rule the headings mirror.
- `ROADMAP_FORMAT.md` and `SEED_FORMAT.md` — the draft-seed contract; step 5 or the docs step owns edits to them.
- BACKLOG #532 — the source entry for this plan.

## Applicable guardrails

- **The plan's "## Scope guardrails", presence-only check.** This step adds only the presence rule. It must not judge, compare or cap what a guardrail says, so the gate stays one call to step 1's check.
- **The plan's "## Scope guardrails", `None` must pass.** The prompt and the gate must both treat `None` as content. The placeholder pattern in `plan_tool/scope_fence.py` is not edited here.
- **The plan's "## Scope guardrails", headings not required.** This step must not require `## Stack`, `## Outcome` or `## In scope`, and must not touch inline `--from`, `--from-plan` or archived seeds.
- **The plan's "## Scope guardrails", no new model call.** The materialize prompt gains text only. The retry loop's existing budget is the only extra attempt path, and this step adds no call.
- **The plan's "## Out of scope", no quality checks.** No agreement check against `Out of scope`, no length or shape cap, and no exit-code change beyond the refusal. The new tempting spot is the gate: do not compare a guardrail body with the plan row's `non_goals`.

## Deferred

- Docs for the new draft-seed rule in `ROADMAP_FORMAT.md`, `SEED_FORMAT.md` and `docs/how-to/pipeline/create-from-existing.md` — outside this step's declared files; a later docs step owns them.
- A bulk or automatic rewrite of existing drafts — `--refresh-seeds` is the one stated route, and a new command needs its own decision.
- Whether the roadmap plan row should carry guardrail fields the prompt copies from — the plan's fence says to write from the existing row; adding row fields changes the roadmap artifact schema and needs a plan-level decision.
- Measuring how often a real model writes the headings on the first attempt — canned tests cannot show it, and it needs real briefs.
