> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Fill the plan's intent from the seed's Outcome section in create

## Summary

This step makes `plan-tool create` carry a seed's `## Outcome` into the new plan's frontmatter as step 1's `Plan.intent`. It adds one small private helper to `plan_tool/create.py` that lifts the `## Outcome` H2 out of the seed and squeezes it onto one line, plus a `intent=` argument at the single real `Plan(...)` assembly inside `create_plan`. The main design decision is **where the text is read from**: the original seed, before the distill pass rebinds `from_description` / `seed_body` — because `Outcome` is not a recognized plan-body section, so distillation drops it and the plan body never shows it. There is **no new Claude call**: the lift is deterministic, exactly like the guardrail lift sitting beside it. On green, a seed that states an Outcome produces a plan whose frontmatter carries a one-line `intent:`, and a seed that states none produces the same plan file `create` writes today.

## Table of Contents

- [Summary](#summary) — what ships, the read-the-original-seed decision, and the result on green.
- [Why](#why) — the one place a seed's stated purpose is dropped on the floor.
- [Input](#input) — the five contracts this step reads and does not own, and what the tests cannot prove.
- [Files (creates vs edits)](#files-creates-vs-edits) — two edited files, no new files.
- [Implementation](#implementation) — the helper, the call site, the rejected alternatives, and six gotchas.
- [Tests](#tests) — approx. 18 new cases in `tests/test_create.py` and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — greps and equalities a reviewer can run.
- [References](#references) — the YAML and pytest docs behind the one-line rule and the table-driven cases.
- [Applicable guardrails](#applicable-guardrails) — the fence entries that bind, and the one place breaking them is tempting.
- [Deferred](#deferred) — what steps 2, 3, 7, 8, 9, and 10 own, and the one finding routed to the backlog.

## Why

A seed's `## Outcome` is the single densest sentence an author writes — `SEED_FORMAT.md` calls it "one measurable result" and lists it first among the required scope-contract fields. `create` reads it exactly once, as raw prose inside the seed text handed to the step proposal, and then loses it. It is not one of `plan_tool/create.py:PLAN_BODY_SECTIONS`, and it is not in `OPTIONAL_PLAN_BODY_SECTION_SHAPES` either, so `_render_distilled_markdown` drops the heading during distillation and `_render_plan_body` never has a slot to put it in. The written plan keeps the author's boundaries (the guardrail sections ride through verbatim) and throws away their goal. Step 1 gives `Plan` a field to hold it; this is the step that fills it, and it is the plan's own claim applied one level up — the seed states the purpose, so the plan should not have to re-derive it.

## Input

Five contracts this step reads and does not own. Read each off HEAD before you start; where a landed name differs from a name below, the landed name wins.

- **Step 1's plan-level field.** `Plan.intent` (created by step 1 in `plan_tool/schema.py`; not at HEAD), `Optional[str] = None`, storing whatever it is handed with no stripping, no cap, and no validator. This step is the first producer of a non-`None` value.
- **The pre-distill seed variable.** `plan_tool/create.py:create_plan` resolves `raw_seed = seed_body if seed_body is not None else from_description` and immediately calls `_extract_supplied_guardrails(raw_seed)`. Both happen **before** the distill block rebinds `from_description` and `seed_body` to the distilled text. That ordering is the whole reason the guardrail lift works, and it is the reason this step's lift must sit in the same place.
- **The H2 splitter.** `plan_tool/create.py:extract_h2_sections(text) -> dict[str, str]` keys sections by lowercased heading, drops a section whose body is empty, keeps the **first** of duplicate headings, and strips a CommonMark closing sequence (`## Outcome ##`) before lowercasing. Every one of those behaviors is free for this step — reuse the function, do not write a second matcher.
- **How the frontmatter is serialized.** `plan_tool/parser.py:render_plan_text` dumps with `model_dump(exclude_defaults=True, exclude_none=True)`, so `intent=None` never reaches the file. It then calls `yaml.safe_dump(..., default_flow_style=False, sort_keys=False, allow_unicode=True)` with **no `width`**, so PyYAML's default 80-column wrap applies: a long one-line intent is written across several physical lines in the file and folds back to the same single-line string on re-parse. Verified at HEAD for a 200-character value.
- **What the `--iterate` loop does with the plan.** The convergence loop re-reads the plan from disk (`edited = parse_plan(plan_path)`), swaps only the step list (`edited.model_copy(update={"steps": merged_steps})`), and writes back with `write_plan`. A plan-level `intent` set in round 0 therefore survives every round with no loop edit. Confirm this rather than assume it — it is the difference between this step touching one call site and touching three.

**What the tests cannot prove.** Nothing here checks whether the lifted sentence is a *good* intent. The suite proves the text arrives, arrives on one line, and arrives from the right source. Quality is deliberately unjudged (see [Applicable guardrails](#applicable-guardrails)).

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**

- `plan_tool/create.py`
  - Add one private helper — suggested name `_intent_from_seed_outcome(seed_text: Optional[str]) -> Optional[str]` — placed next to `_extract_supplied_guardrails`, its sibling in shape and purpose.
  - In `create_plan`, compute the value beside the existing `supplied_guardrails = _extract_supplied_guardrails(raw_seed)` line.
  - Pass `intent=` at the real `Plan(...)` assembly in `create_plan` (the one carrying `title=title`, `enforce_step_tests=True`, `steps=steps`). The other `Plan(...)` constructions in this module are throwaway `title="dry-run"` objects used to validate a step graph; leave all of them alone.
- `tests/test_create.py`
  - New class for the helper's unit cases, plus new cases on the `create_plan` paths (see [Tests](#tests)).

## Implementation

**What must be true on green:** a seed carrying `## Outcome` produces a plan whose frontmatter has a one-line `intent:` holding that section's text; a seed carrying none, or no seed at all, produces exactly the plan file `create` writes today.

### The helper

One function, no invoker, no I/O. Recommended shape:

- **Take the seed text, return `Optional[str]`.** `None` in → `None` out, so the caller needs no guard.
- **Find the section with `extract_h2_sections`**, then read the `"outcome"` key. Absent key → `None`. The splitter already drops an empty-body heading, so a bare `## Outcome` with nothing under it returns `None` for free.
- **Refuse a placeholder body.** A body whose stripped text is `_(TODO)_` returns `None`. `create` writes that literal itself in `_render_plan_body`, and a seed round-tripped through a previous plan can carry it back in. One way: match the same literal `_find_placeholder_body_sections` matches — do **not** reach for the looser `review._BODY_PLACEHOLDER_RE`, for the reason that helper's docstring already gives.
- **Collapse to one line.** Replace every run of whitespace — newlines included — with a single space, then strip. This is the only shaping the helper does.

**Two things the helper must not do**, and both are tempting:

- **No sentence splitting.** Taking "the first sentence" needs a period-splitter, and the text this runs on is full of `e.g.`, version numbers, and file names like `plan_tool/create.py`. A splitter that cuts one of those ships a half sentence that reads complete and says something else. The whole Outcome, collapsed, is honest; a mangled first clause is not.
- **No truncation.** An over-long intent is a mechanical property the plan explicitly routes to the advisory channel (`## Risks`: "over-length is advisory like absence"). Cutting the text at N characters manufactures a false statement to dodge an advisory finding, which is the "stale intent is worse than an absent one" failure the plan opens with.

**Why single spaces matter, concretely.** PyYAML wraps the value at 80 columns and folds each break back to one space on re-parse. A value whose internal whitespace is already single spaces round-trips unchanged; one carrying a double space can lose it at a fold point. Collapsing runs is what makes `parse_plan(write_plan(plan)).intent == plan.intent` hold for a long value.

### The call site

Compute it where `supplied_guardrails` is computed, from the same `raw_seed`, and thread the result to the `Plan(...)` assembly. Two facts pin this placement:

- **Distillation destroys the evidence.** `_render_distilled_markdown` emits only `_canonical_body_section_keys()` and `_OPTIONAL_PLAN_BODY_SECTIONS`; `Outcome` is in neither, so the distilled seed has no `## Outcome` heading and the later `body_source` variable is useless for this. Read `raw_seed` or read nothing.
- **`raw_seed` is already resolved and already used for exactly this.** No new variable, no re-derived precedence ladder. Reusing the resolved value is what keeps this step from re-opening the bug the `body_source` comment describes, where two consumers re-derived the same ladder and disagreed.

### What deliberately does not change

- **The plan body.** No `## Outcome` H2 is added to `PLAN_BODY_SECTIONS`, to `OPTIONAL_PLAN_BODY_SECTION_SHAPES`, or to the distill vocabulary. The intent is frontmatter, not prose. Adding a canonical section would change every plan's rendered body and would trip the fail-loud `_(TODO)_` gate on every seed that lacks the heading.
- **The `--iterate` loop.** It preserves the field through disk already (see [Input](#input)). Pin it with a test; do not add code to it.
- **The interactive path.** With no seed there is nothing to lift, so `prompt_metadata` gains no question and a blank-skeleton create writes no `intent:` key.

### Which Outcome shapes are recognized

Only the `## Outcome` H2. That is what the seed and the plan name, and it is what `extract_h2_sections` can see. Measured at HEAD across 156 files under `plan-seeds/` (including `plan-seeds/archive/`): 2 use the `## Outcome` heading and 7 use a `- **Outcome:** …` bullet inside a scope-contract subsection. The bullet form is a real shape and it is **out of this step's boundary** — see [Deferred](#deferred). A test pins the boundary so the exclusion is deliberate rather than accidental.

### Step 3's move

Step 3 relocates `extract_h2_sections` into `plan_tool/scope_fence.py` and re-exports it back into `plan_tool/create.py`, so calling it by its `plan_tool/create.py` name keeps working either way. This step's declared dependency is step 1 only — call the name as it exists in `plan_tool/create.py` and let step 3's re-export absorb the move.

## Tests

All new cases land in `tests/test_create.py`. The helper cases fit a new class (suggested `TestIntentFromSeedOutcome`), sitting near `TestExtractH2Sections`, which covers the splitter it reuses. The end-to-end cases extend the existing `create_plan` classes — `TestCreatePlanWithSeedBody` for the seeded path, `TestCreatePlanBlankSkeleton` for the no-seed path — reusing their `_queue_input` / `_basic_metadata_answers` / recording-invoker helpers rather than adding fixtures.

### Tests for this step

Helper cases (approx. 11):

- `test_h2_outcome_becomes_the_intent` — a one-line `## Outcome` body comes back unchanged.
- `test_multi_line_outcome_collapses_to_one_line` — a three-line Outcome comes back with no newline in it.
- `test_whitespace_runs_collapse_to_single_spaces` — double spaces and tabs become one space each.
- `test_no_seed_text_returns_none` — `None` input, no exception.
- `test_seed_without_outcome_heading_returns_none` — a seed with only canonical headings.
- `test_empty_outcome_body_returns_none` — `## Outcome` immediately followed by the next H2.
- `test_todo_placeholder_outcome_returns_none` — a `_(TODO)_` body is not an intent.
- `test_long_outcome_is_not_truncated` — a 400-character Outcome comes back whole.
- `test_duplicate_outcome_headings_keep_the_first` — the second `## Outcome` is ignored.
- `test_outcome_atx_closing_sequence_is_recognized` — `## Outcome ##` is matched.
- `test_bullet_form_outcome_is_not_extracted` — `- **Outcome:** …` inside a scope-contract section yields `None`, pinning the declared boundary.

End-to-end cases on `create_plan` (approx. 7):

- `test_seed_outcome_lands_in_plan_frontmatter_intent` — re-parse the written plan; `plan.intent` equals the collapsed line.
- `test_seed_without_outcome_writes_no_intent_key` — the written file has no `intent:` line.
- `test_outcome_read_from_original_seed_not_the_distilled_one` — a distill invoker returns canonical sections with no `## Outcome`; the intent still lands.
- `test_plan_body_gains_no_outcome_section` — `## Outcome` never appears below the frontmatter.
- `test_long_intent_round_trips_through_the_written_file` — a 200-character Outcome wraps in the YAML and re-parses to the identical string.
- `test_intent_survives_the_iteration_loop` — under `--iterate`, the round-0 intent is still on disk after the loop.
- `test_interactive_create_without_a_seed_writes_no_intent` — the blank-skeleton path is unchanged.

**Green-before-done gate:** every case above, plus the existing `tests/test_create.py` and `tests/test_parser.py` suites with no edits to their assertions, must be green before this step is finished.

## Acceptance criteria

- For a seed whose `## Outcome` body is `Ship X.\nMeasured by Y.`, `parse_plan(<written plan>).intent == "Ship X. Measured by Y."`.
- `"\n" not in plan.intent` for every plan `create` writes with a non-`None` intent.
- A seed with no `## Outcome` produces a plan file where `rg '^intent:' <plan>` returns nothing, and the file matches the bytes `create` writes at HEAD for the same seed.
- `rg '^## Outcome' <written plan>` returns nothing — the lift adds no body section.
- A create run over a seed **with** an Outcome makes the same number of backend calls as the same run over a seed **without** one (assert on the recording invoker's captured prompt list).
- The new helper's signature takes the seed text only — `rg 'invoker' ` over its definition returns nothing.
- A 200-character Outcome re-parses from the written file to the identical single-line string.
- `uv run pytest tests/test_create.py tests/test_parser.py -q` is green.

## References

- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — `safe_dump`'s scalar styles and default line width, which decide how a long one-line intent is written to the file.
- [YAML Ain't Markup Language (YAML™) revision 1.2.2](https://yaml.org/spec/1.2.2/) — the normative rule that a single line break inside a plain scalar folds to one space, which is what makes the wrapped value re-parse unchanged.
- [How to parametrize fixtures and test functions — pytest](https://docs.pytest.org/en/stable/how-to/parametrize.html) — table-driven cases for the helper's absent / empty / placeholder / duplicate / bullet-form inputs.

## Applicable guardrails

- **Nothing becomes required at parse time, and no plan on disk is migrated.** This step writes `intent:` only when the seed states an Outcome. A seed without one produces a plan with no `intent:` key, and `create` neither refuses nor warns. No existing plan file is touched.
- **No check comparing an intent against prose or against a diff.** This step never compares the Outcome to the plan's steps, its body, or anything else. It copies text from one file to another.
- **Allowed behavior changes are two optional frontmatter fields, one advisory finding class, and two prompts gaining rendered input.** Filling one of those two fields at authoring time is what the plan's own scope names ("`create` … fills a plan's from the seed's `## Outcome`"). Nothing else may ride along — no new body section, no new flag, no new report line beyond an optional one-line note.

**The place breaking this is tempting:** when the seed has no `## Outcome`, synthesizing one. `create` already does exactly that for three sections — `_DERIVE_FROM_INTENT_SECTIONS` tells the distill and synthesis passes to author Overview, Problem statement, and Architecture from any stated goal — so extending the same treatment to intent looks consistent. Refuse it. A synthesized intent is the tool's guess printed in the field reserved for the author's stated purpose, and every downstream reader (steps 4 and 5 put it in front of the model that writes code) treats that field as authoritative. Absence is the honest answer, and step 2's advisory check is what asks the author to fix it.

## Deferred

- **Per-step intents** — step 7 owns them, by asking `create`'s step proposal for a one-line intent per step and parsing it.
- **The `- **Outcome:** …` bullet form** — 7 of the 156 files under `plan-seeds/` state their Outcome as a bullet inside a scope-contract subsection rather than as an H2. Supporting it widens the extraction surface past what this plan's scope names, so file it in `BACKLOG.md` as a follow-up rather than adding a second matcher here.
- **Surfacing an over-long or missing intent** — step 2's advisory check owns it, and it fires on the written plan. This step reads no cap constant, since its declared dependency is step 1 alone.
- **Getting the intent in front of a model** — step 4 renders it into the detail prompt, step 5 into the run and run-jira prompts.
- **Keeping an intent defensible through a structural edit** — step 8 for split and merge, step 9 for the scope-out and reground forward seeds.
- **Documenting the rule** — step 11 states both fields and the propagation rules in `PLAN_FORMAT.md` and `SEED_FORMAT.md`, and gives this plan its own intent.
- **Consolidating the H2 splitter** — step 3 owns the move of `extract_h2_sections` into the shared leaf; this step reuses whatever name `plan_tool/create.py` exposes.
