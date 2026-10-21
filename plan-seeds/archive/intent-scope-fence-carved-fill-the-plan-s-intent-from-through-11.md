<!-- plan-tool scope-out carved-seed
source: docs/implementation-plans/2-intent-scope-fence.md
carved_steps: 6, 7, 8, 9, 10, 11
-->

> **SUPERSEDED 2026-08-03 — do not `create` from this.** Steps 6–7 and 11
> shipped via `2-intent-required`. The open residual (structural-verb
> propagation + conceptual-audit delivery) is the slim seed
> `plan-seeds/intent-structural-propagation.md`. Kept for provenance only.

# Plan seed: carved steps 6..11 from Intent Scope Fence

This is a `plan-tool create --from-existing` input. It re-plans **only the carved region** in the **Scope to re-plan** sections below (one per carved step). The **Done-context**, **Upstream prerequisites**, and **External prerequisites** sections are already-implemented context, not work to re-plan.

## Scope to re-plan (source step 6)

**Fill the plan's intent from the seed's Outcome section in create**

Files:
- plan_tool/create.py
- tests/test_create.py

Change type: feature

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


## Done-context (already done — do not re-plan; source step 6)

Everything in this section is **already implemented** done-context. Do **not** re-plan or re-implement it.

The carved step was left **attempted/partial** (status `pending`) — account for this in the re-plan, but treat its work (in **Scope to re-plan** above) as not yet complete.

## Scope to re-plan (source step 7)

**Ask create's step proposal for a one-line intent per step and parse it**

Files:
- plan_tool/create.py
- tests/test_create.py

Change type: feature

# Step 7 — Ask create's step proposal for a one-line intent per step and parse it

## Summary

This step makes `plan-tool create`'s step proposal ask the model for a one-line `intent` per step and lands the answer on step 1's `Step.intent`. Two edits in `plan_tool/create.py`: `_render_from_prompt` gains an instruction plus the `intent` key in its JSON-shape line, and `_parse_steps_json` reads the key and passes it to the `Step(...)` it already builds. The main design decision is that **intent goes straight onto the `Step`, not into a caller-supplied side dict** — the neighbouring `rationale` uses `rationales_out` only because it has no schema slot, and copying that shape is the tempting mistake. The read is soft like `change_type` and `gate`: a missing, null, non-string, or blank `intent` becomes `None` and never sinks the proposal. On green, a proposal that returns intents produces a plan whose steps each carry one, and a proposal that returns none produces exactly the plan file `create` writes today.

## Table of Contents

- [Summary](#summary) — what ships, the field-not-side-dict decision, and the result on green.
- [Why](#why) — why the one moment a model decides *why* each step exists is the cheapest place to capture it.
- [Input](#input) — the six contracts this step reads and does not own, and what the tests cannot prove.
- [Files (creates vs edits)](#files-creates-vs-edits) — two edited files, no new files.
- [Implementation](#implementation) — the parse, the prompt item, the rejected alternative, and six gotchas.
- [Tests](#tests) — approx. 19 new cases, two rewritten assertions, and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — checkable facts a reviewer can run.
- [References](#references) — the YAML, pytest, and prompt-wording docs this step leans on.
- [Applicable guardrails](#applicable-guardrails) — the fence entries that bind, and the two places breaking them is tempting.
- [Deferred](#deferred) — what steps 8, 9, and 10 own, and the producers left without an intent on purpose.

## Why

Step 6 fills a plan's intent from the seed's `## Outcome`. Nothing fills a *step's*, and the step-level why is exactly what the plan says gets thrown away and re-derived on every `detail` pass. `create`'s step proposal is the one moment where a model has just decided why each step exists: item 6 of the prompt already makes it argue the decomposition out loud, asking for a one-line `rationale` defending each `change_type` classification. That reasoning is captured, shown once in the interactive review, and dropped — `_parse_steps_json` keeps it in a caller-supplied dict because `Step` had nowhere to put it. Step 1 gives it somewhere. So the marginal cost here is one instruction and one assignment, and the payoff is that every step a `create` run authors arrives with its purpose already stated instead of waiting for an author to backfill it.

## Input

Six contracts this step reads and does not own. Read each off HEAD before you start; where a landed name differs from a name below, the landed name wins.

- **Step 1's step-level field.** `Step.intent` (created by step 1 in `plan_tool/schema.py`; not at HEAD), `Optional[str] = None`, storing whatever it is handed with no stripping, no cap, and no validator. This step is the first producer of a per-step value, so whatever shaping happens has to happen here.
- **Step 6's one-line rule.** Step 6 fills `Plan.intent` from the seed's `## Outcome` and settles what "one line" means for this plan: collapse every whitespace run to a single space, no truncation, no sentence splitting. Apply the same rule to the step-level value. Read what step 6 actually landed — if the collapse is a standalone helper, call it; if it is inline in step 6's lift, either lift it out or repeat the two-line collapse. Do not invent a second, different rule for the same field.
- **`_parse_steps_json`'s strict-vs-soft split.** The function already treats its keys two ways, and the two sit within a few lines of each other. `complexity`, `files`, `creates`, `depends_on`, and `concept_ids` **reject the whole proposal** on a bad value (`return None`). `change_type`, `rationale`, and `gate` are **soft** — a bad value is dropped and the loop continues. `intent` joins the soft group; the existing comments in the function explain why the split exists and are worth reading before adding to it.
- **The parser's three callers.** `propose_steps_from_claude` calls it for the primary response and again for the one repair retry, and `_propose_step_split` calls it for the create-wizard's `(s)plit` action. One read site in the parser covers all three; there is no second parse to update.
- **The checkpoint contract.** `_initial_steps_input_hash` keys the `create-initial-steps` checkpoint on slug + description + output dir (+ iteration when non-zero). It does **not** hash the prompt text, so a checkpoint saved before this change still validates and replays a response with no `intent` keys.
- **The step-review round trip.** `_review_step_change_types` checkpoints its result as `Step.model_dump(mode="json", exclude_none=True)` and `_deserialize_reviewed_steps` rebuilds it with `Step(**item)`. Intent rides both directions with no edit, and `exclude_none=True` keeps an absent intent out of the payload. Pin it with a test; do not add code to it.

**What the tests cannot prove.** Every case here drives a canned invoker response. That shows the parse handles what a model can return and that the prompt states a contract a model *can* satisfy — it says nothing about how often a real model returns a useful intent rather than a restated title. Measuring that needs real briefs and somewhere to record the result; it is out of this step.

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**

- `plan_tool/create.py`
  - `_render_from_prompt` — add the per-step intent instruction and the `intent` key to the JSON-shape object line; adjust the dynamic numbering start for the gate / foundational tail items.
  - `_parse_steps_json` — read `intent` softly, collapse it to one line, and pass it to the `Step(...)` construction.
- `tests/test_create.py`
  - New parser cases, new prompt cases, new end-to-end cases.
  - Rewrite the two `TestRenderFromPromptABMode` assertions that pin the current six-item core (named in [Implementation](#implementation)).

## Implementation

**What must be true on green:**

- A proposal whose objects carry a usable `"intent"` produces steps whose `Step.intent` holds that text as one line.
- A proposal that omits the key, or returns a bad value for it, produces exactly the steps `create` produces today — `intent` is `None`, the step list is not rejected, nothing warns.
- The proposal prompt asks for the key in **all four** `_render_from_prompt` arms, and its numbered items stay contiguous in each.

### The parse

- **Put the value on the `Step`, not in a side dict.** The `rationale` handling three lines away writes into a caller-supplied `rationales_out` because `rationale` has no `Step` field. `intent` does. Adding an `intents_out` parameter mirrors the wrong half of the neighbour and creates a second channel for a value that already has a home.
- **Read it softly.** A missing key, JSON `null`, a non-string (int, list, mapping), or a blank / whitespace-only string all become `None` and the loop continues. Never `return None` for the whole list on a bad `intent`.
- **Collapse to one line, then strip.** Per step 6's rule. A JSON string can legally carry `\n`, and a multi-line value here becomes a multi-line YAML scalar in the written plan.
- **Do not truncate.** An over-long intent is a mechanical property this plan routes to step 2's advisory channel. Cutting the text at N characters manufactures a false statement to dodge an advisory finding.
- **Nothing here judges the value.** No comparison against the step's title, `files`, or `rationale`.

### The prompt

**Recommended shape:** a new numbered item **7**, sitting after item 6 and before the dynamic tail, so it survives both A/B arms the way item 6 does. The tail's `next_num` then starts at 8, and the existing renumbering machinery keeps the gate and foundational items gap-free when either is omitted. Add `"intent": str` to the JSON-shape object line beside `"rationale": str`.

What the instruction has to say:

- **One line, stating what the step is for** — the purpose, not a restatement of the title and not a summary of the file list.
- **How it differs from `rationale`, explicitly.** `rationale` defends the `change_type` classification; `intent` states why the step exists. The two keys are adjacent in the shape line and adjacent in the instructions, so without a stated contrast the model returns the same sentence twice and the field carries nothing new.
- **Plain, everyday words**, matching the rule the trailing paragraph already imposes on `title`.

**The alternative, and its trade:** hang the instruction off the trailing shape paragraph instead — the place the plain-words `title` rule already lives. That is lower churn: no renumbering, and the two A/B numbering tests below stay green. It also buries a per-step contract in a paragraph about JSON shape, which is why the numbered item is the recommendation. Either is defensible; if you take the trailing-paragraph path, the two rewritten test cases below are unnecessary and the rest of the roster stands.

### Gotchas

- **Two A/B tests are correct-by-design today and this reddens them.** `TestRenderFromPromptABMode::test_split_renumbers_when_gate_omitted` asserts the foundational item takes number 7 when the gate item is omitted, and `test_split_both_omitted_drops_to_six_items` asserts `"7. "` never appears with both omitted. A fixed item 7 makes both wrong. Rewrite them — including the second's name, which states a count — and keep them asserting contiguity rather than a hardcoded ceiling.
- **`_DERIVE_FROM_INTENT_SECTIONS` is a different thing entirely.** Grepping `intent` in `plan_tool/create.py` lands on the body-section synthesis policy — the `[derive from intent]` tag `_render_section_shapes_block` emits, which tells the distill and synthesis passes which plan-body sections may be authored from a stated goal. It has nothing to do with `Step.intent`. Leave it alone, and do not name the new work anything that reads like it.
- **A stale checkpoint replays without intents.** Because the prompt text is not hashed, a `create-initial-steps` checkpoint from before this change resumes cleanly and yields steps with no intent. The soft parse makes that harmless and `--no-resume` is the operator's out. Do **not** fix it by hashing the prompt — that invalidates every checkpoint on disk on every future prompt edit, which is the scenario the hash's docstring says it exists to avoid.
- **The create-wizard split clears intent, and that is the decision.** `_propose_step_split`'s prompt names a closed key list that does not include `intent`, so both replacement halves come back `None` and the original step's value disappears with the step. That matches this plan's rule that a propagation must be able to *clear* the field rather than carry a value the split made false. Pin it with a test so it stays a decision instead of an accident. The `plan-tool split` / `merge` verbs (`plan_tool/detail.py:split_step`) are step 8's, not this step's.
- **Do not move any other key across the strict/soft line.** The change is additive; `complexity` keeps rejecting the list, `gate` keeps dropping bad entries.
- **No prompt-budget bookkeeping to add.** `_maybe_warn_create_budget` measures the rendered prompt, so the extra instruction is accounted for already.

## Tests

All cases land in `tests/test_create.py`, reusing its existing `_queue_input` / `_basic_metadata_answers` / recording-invoker helpers rather than adding fixtures. Parser cases fit a new class beside `TestParseStepsJsonChangeType` and `TestParseStepsJsonGate` (suggested `TestParseStepsJsonIntent`); prompt cases extend `TestRenderFromPromptABMode`; the end-to-end cases extend the `create_plan` classes that already drive a canned proposal.

### Tests for this step

Parser cases (approx. 9):

- `test_intent_lands_on_the_step` — a one-line `"intent"` comes back on `Step.intent` unchanged.
- `test_missing_intent_key_leaves_none` — an object with no `intent` key parses, `intent is None`.
- `test_null_intent_leaves_none` — JSON `null` is not an error.
- `test_non_string_intent_leaves_none` — parametrized over int, list, and mapping.
- `test_whitespace_only_intent_leaves_none` — `"   "` is absence, not a value.
- `test_multi_line_intent_collapses_to_one_line` — a `\n`-bearing string comes back with no newline and single spaces.
- `test_bad_intent_does_not_reject_the_proposal` — one step with a bad `intent` still yields the full list with every other step's fields intact.
- `test_long_intent_is_not_truncated` — a 400-character intent comes back whole.
- `test_intent_is_not_captured_in_rationales_out` — the two keys stay separate channels; `rationales_out` holds only rationales.

Prompt cases (approx. 5, in `TestRenderFromPromptABMode`):

- `test_prompt_asks_for_a_per_step_intent` — the instruction is present in the combined arm and in the both-omitted arm.
- `test_prompt_declares_the_intent_json_key` — `"intent": str` appears in the shape line in every arm.
- `test_prompt_separates_intent_from_rationale` — the sentence distinguishing the two keys is present.
- `test_split_renumbers_when_gate_omitted` *(rewritten)* — with the gate item omitted, the foundational item takes the number right after the intent item and no number is skipped.
- `test_split_both_omitted_drops_to_seven_items` *(rewritten and renamed from `..._six_items`)* — with both omitted, items 1–7 are present, nothing higher is, and the intent item is one of them.

End-to-end cases (approx. 5):

- `test_proposed_step_intents_land_in_the_written_plan` — canned proposal with intents; re-parse the written plan and check each `step.intent`.
- `test_proposal_without_intents_writes_no_intent_key` — no `intent:` line anywhere in the written file, and the same number of backend calls as the intent-bearing run.
- `test_intent_survives_the_step_review_checkpoint` — seed a `create-step-review` checkpoint holding intents and confirm the restored steps still carry them.
- `test_stale_checkpoint_without_intent_still_creates` — a cached `create-initial-steps` payload with no `intent` keys resumes and writes a plan whose steps have none, with no warning and no failure.
- `test_create_split_replacements_carry_no_intent` — `_propose_step_split`'s two halves both come back with `intent is None`.

**Green-before-done gate:** every case above, plus the existing `tests/test_create.py` and `tests/test_parser.py` suites with no assertion edits beyond the two rewritten A/B numbering cases, must be green before this step is finished.

## Acceptance criteria

- `_parse_steps_json(json.dumps([{"title": "t", "intent": "Make X true."}]))[0].intent == "Make X true."`.
- A proposal object carrying `"intent": 3` still yields a one-step list, and that step's `intent is None` — the list is not rejected.
- `"\n" not in step.intent` for every step the parser returns with a non-`None` intent.
- `_render_from_prompt("x")` and `_render_from_prompt("x", omit_gate_item=True, omit_foundational_item=True)` both contain the intent instruction and the literal `"intent": str`.
- In all four `_render_from_prompt` arms the numbered items run contiguously from 1 with no gap — asserted on the rendered numbers, not against a hardcoded maximum.
- A `create_plan` run over a canned proposal carrying intents writes a plan where `rg '^  intent:' <plan>` matches once per step; the same run with the key removed writes a file where it matches nothing.
- Both replacements returned by `_propose_step_split` have `intent is None`.
- `rg 'intents_out' plan_tool/create.py` returns nothing — no second side channel was added.

## References

- [YAML Ain't Markup Language (YAML™) revision 1.2.2](https://yaml.org/spec/1.2.2/) — scalar styles and line folding: what "one line" has to mean for a value that gets written into frontmatter.
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — `safe_dump` wrapping and re-parse folding, the round-trip behavior a long collapsed intent depends on.
- [Be clear, direct, and detailed — Claude Docs](https://docs.claude.com/en/docs/build-with-claude/prompt-engineering/be-clear-and-direct) — phrasing the new prompt item so it constrains what the model returns instead of restating the title.
- [How to parametrize fixtures and test functions — pytest](https://docs.pytest.org/en/stable/how-to/parametrize.html) — table-driven form for the bad-value cases (int, list, mapping, blank, null).

## Applicable guardrails

- **Nothing becomes required at parse time, and no plan on disk is migrated.** A missing or malformed `intent` must never reject a proposal, never warn, and never block a create. **The place breaking this is tempting:** the parser's strict arm. `complexity` sits a few lines above and rejects the entire step list on a bad value, so copying the nearest neighbour is exactly the wrong move here — copy the `change_type` / `gate` treatment instead.
- **No check comparing an intent against prose or against a diff.** This step parses a value and stores it. **The second tempting place:** the change-type review loop, where the operator already sees the title and the rationale side by side and a "these two disagree" nudge would be one line. Do not add it; the plan bans intent-vs-work agreement checking at every level, and cites the withdrawn per-`change_type` test-ordering contract as the precedent.
- **Findings asking for more than presence go to the backlog.** A finding that a proposal should be rejected for a missing intent, or that intent should become required, is outside this fence — file it in `BACKLOG.md` rather than applying it.
- **Allowed behavior changes.** The fence's list covers rendering the two fields *into* the detail and run prompts (steps 4 and 5). This step changes the create step-proposal prompt in the other direction — asking the model to *produce* the field, which is what the plan's own scope names ("`create` proposes step intents"). It renders no intent into any prompt, adds no flag, no report line, and no body section.

## Deferred

- **The interactive step wizard** — the hand-authored path that builds a step from `input_fn` answers gains no intent question. There is no model to ask, and step 6 made the same call for the plan-level field on the no-seed path. An author adds `intent:` by hand.
- **Canonical seed import** — `extract_steps_from_canonical` copies fields out of `plan_tool/canonical.py`'s strict `## Steps` shape, which has no `Intent:` line. Adding one means changing that module's re-render round-trip equality check, outside this step's files. File it in `BACKLOG.md`.
- **Showing the intent in the change-type review loop** — `_ask_change_type` already displays the proposed `change_type` and its rationale; adding the intent beside them is display-only polish with no bearing on whether the value lands.
- **Consolidation steps from the foundational-logic sweep** — `plan_tool/foundational_logic.py:merge_sweep_into_steps` appends a fresh `refactor` step with no intent. Another module, and step 2's advisory check surfaces the absence.
- **`plan-tool split` and `plan-tool merge`** — step 8 states what those verbs do with a step's intent, in `plan_tool/detail.py`. This step covers only the create wizard's own `(s)plit` action, whose two halves come back cleared.
- **The scope-out and reground forward seeds** — step 9.
- **Surfacing a missing or over-long intent** — step 2's advisory check owns it and fires on the written plan; this step reads no cap constant.
- **Getting the intent in front of a model** — step 4 renders it into the detail prompt, step 5 into the run and run-jira prompts.
- **Documenting the field and the propagation rules** — step 11, in `PLAN_FORMAT.md` and `SEED_FORMAT.md`.


## Done-context (already done — do not re-plan; source step 7)

Everything in this section is **already implemented** done-context. Do **not** re-plan or re-implement it.

The carved step was left **attempted/partial** (status `pending`) — account for this in the re-plan, but treat its work (in **Scope to re-plan** above) as not yet complete.

## Scope to re-plan (source step 8)

**Decide what split and merge do with a step's intent**

Files:
- plan_tool/detail.py
- tests/test_detail.py

Change type: feature

# Step 8 — Decide what split and merge do with a step's intent

## Summary

This step settles what `plan_tool/detail.py`'s two structural verbs do with step 1's `Step.intent` and writes the answer down as a contract instead of leaving it to whatever the code happens to do. **Split never copies the target's intent onto a half** — that needs no production edit, so its work is the stated rule plus the tests that pin it. **Merge keeps an intent only when every folded member states the same one, and clears it otherwise** — one small fold added beside the existing `merged_change_type` / `merged_eta` folds in `merge_steps`. The main design decision is that a member's intent never survives a fold on its own: the survivor also does the other members' work, so a one-line why that covers part of a step reads as authoritative while fencing the model away from the rest. On green, both verbs leave every surviving step with an intent that is true of it or with none at all, and a plan carrying no intent anywhere splits and merges to frontmatter with no `intent:` key in it.

## Table of Contents

- [Summary](#summary) — the two rules, and the one that costs no production code.
- [Why](#why) — why a carried-over why is worse than no why at all.
- [Input](#input) — the four contracts this step reads from step 1 and from `create.py`'s transforms.
- [Files (creates vs edits)](#files-creates-vs-edits) — two edited files, no new files.
- [Implementation](#implementation) — the split rule, the merge fold, the rejected alternatives, and seven gotchas.
- [Tests](#tests) — 13 new cases across four existing classes, and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — checkable facts a reviewer can run.
- [References](#references) — the pydantic, YAML, and pytest behavior this step leans on.
- [Applicable guardrails](#applicable-guardrails) — the fence entries that bind, and the two places breaking them is tempting.
- [Deferred](#deferred) — what steps 9 and 10 own, and the four things routed out.

## Why

Split and merge are the two verbs that change which steps exist. A split takes one step that did two things and makes two steps; a merge takes several and makes one. Both rewrite `files`, `change_type`, `complexity`, `depends_on`, `status`, and `concept_ids` deterministically, and every one of those folds is written down — `_MERGE_CHANGE_TYPE_RANK` picks the dominant type, `_apply_step_split` owns the edges and the first half's status, `_apply_step_merge` owns the ordered union of concept ownership. Once step 1 lands, there is one more field on `Step` and no rule for it. The default that falls out of the code is not obviously wrong, but nobody stated it, so nobody can rely on it: the next person to touch the `replacements = [Step(...)]` list in `split_step` sees `change_type` and `complexity` being passed down and adds `intent=target.intent` in the same spirit, and that one line puts a claim about the parent's purpose on two steps that each do half of it. The plan's rule for propagation is that every surviving step ends with a defensible value — carried, composed, or cleared — and never one that is quietly false. This step is where that rule gets written for split and merge.

## Input

Four contracts this step reads and does not own. Read each off HEAD before you start; where a landed name differs from a name below, the landed name wins.

- **Step 1's step-level field.** `Step.intent` (created by step 1 in `plan_tool/schema.py`; not at HEAD), `Optional[str] = None`, storing whatever YAML handed over with no stripping and no cap. So this step must handle `None`, `""`, `"   "`, a normal one-liner, and a value with real newlines — step 1 preserves all of them, so the merge fold decides what each one means.
- **`plan_tool/create.py:_apply_step_split`'s ownership split.** It trusts the caller for content and owns only `id`, `depends_on`, and `status`, applying them through `rep.model_copy(update={...})` on each replacement. It never adds a field the caller left unset, so whatever `split_step` does (or does not) put on a replacement is what lands on disk. It also refuses replacements that drop or invent `concept_ids`; there is no matching conservation rule for `intent`, and this step does not add one.
- **`plan_tool/create.py:_apply_step_merge`'s ownership split.** Same shape, inverted: it trusts the `merged` step for authored content and owns `id`, `depends_on`, `status`, and `concept_ids`, applied through `merged.model_copy(update={...})`. So an `intent` set on the `merged = Step(...)` assembly in `merge_steps` survives the fold unchanged, and `plan_tool/create.py` needs no edit.
- **`plan_tool/parser.py:write_plan`'s dump flags.** It dumps with `model_dump(exclude_defaults=True, exclude_none=True)`, so a field left at `None` writes no key. That is the whole mechanism behind "a plan with no intent is rewritten with no `intent:` line" — this step gets it for free and must not defeat it by writing `""`.

**What the tests here cannot prove.** Nothing in this suite can show that a kept intent actually reaches the model doing the merged re-author — that path runs through step 4's fence renderer, and this step depends only on step 1. See [Deferred](#deferred).

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/detail.py` — add the unanimous-intent fold helper beside `_MERGE_CHANGE_TYPE_RANK` / `_MERGE_COMPLEXITY_RANK`; pass its result as `intent=` in `merge_steps`'s `merged = Step(...)` assembly; extend the comment above `split_step`'s `replacements = [Step(...)]` list and both verbs' docstrings so each states its intent rule.
  - `tests/test_detail.py` — add an `intents=` parameter to the `_build_merge_plan` helper; add 13 cases across `TestSplitStepOnDemand`, `TestInteractiveSplit`, `TestMergeSteps`, and `TestMergeBridge`.

Deliberate zero-diff files, named so a reviewer can check them: `plan_tool/create.py` (both transforms already carry whatever the caller sets), `plan_tool/launcher.py` (see the split rule below), `plan_tool/cli/authoring.py` and `plan_tool/cli/convergence_cmd.py` (no new flag — `plan-tool split --into` and `plan-tool merge --title` keep their current surface).

## Implementation

### The two rules

State both in the verbs' docstrings, in these terms:

- **Split: a half never inherits the target's intent.** The target's one line describes the whole of what the target was for; the split exists because that was two things. Copying it onto both halves makes it authoritative and wrong on both. Each half starts with no intent, and step 2's advisory finding is what asks the author to fill one in.
- **Merge: the survivor keeps an intent only when every folded member states the same one.** Anything else clears it. "The same" means equal after collapsing runs of whitespace; a missing or blank intent on any member clears.

Neither verb touches the plan-level `Plan.intent`. A split or a merge changes how the work is cut up, not what the plan is for.

### Split — no production edit, two comments and a docstring

`split_step` builds its replacements as `Step(id=0, title=t, change_type=..., complexity=..., concept_ids=...)` and never passes `intent`, so each half starts at `None`. `_apply_step_split` copies replacements without adding fields. The rule already holds; what is missing is the statement of it.

- Extend the comment above the `replacements` list. It enumerates what the halves inherit from the parent, so leaving `intent` out of that list silently reads as an oversight and invites the one-line "fix". Say plainly that intent is *not* inherited and why.
- Add the rule to `split_step`'s docstring next to the existing sentence about replacements inheriting `change_type`/`complexity`.

**The second producer of split halves needs no edit either.** `plan_tool/launcher.py:escalate_to_split` — the bridge `generate_detail`'s Phase-B purity check and the review/reconcile walk use — builds its two halves from `plan_tool/create.py:_propose_step_split`, which parses a fresh model proposal through `_parse_steps_json`. Those replacements are built from the model's JSON, never from the target `Step`, so the parent's intent has no path onto them. After step 7 that parse reads an `intent` key when one is present, but the split proposal prompt does not ask for one — and a per-half intent the model volunteers is the half's own, which the rule allows. Pin this path with a test rather than an edit: `tests/test_detail.py` already drives the real bridge end to end through `generate_detail`, so the case lands inside this step's declared files.

### Merge — one small fold

Add a helper beside the two rank tables in `plan_tool/detail.py`, named for what it returns — one way: `_unanimous_intent(member_steps) -> Optional[str]`. Contract:

- Return `None` when any member's intent is `None`, empty, or whitespace-only.
- Return `None` when the members' intents differ after collapsing runs of whitespace.
- Otherwise return **the first member's text as written**. The collapsed form is only the comparison key; merge does not rewrite the string it keeps.

Then pass `intent=_unanimous_intent(member_steps)` in the `merged = Step(...)` assembly, beside `merged_files`, `merged_change_type`, and `merged_eta`. It belongs in that block because that block is exactly where the other per-field folds live, and because `merge_bridge` and `cmd_merge` both reach the fold through `merge_steps` — putting it anywhere else creates a second rule.

Treating blank as absent matches step 2's precedence rule, which classifies a whitespace-only value as *missing* rather than over-long. Keep the two consistent; a value the advisory check calls missing must not be a value merge treats as a statement.

**Rejected alternatives, and why:**

- **Join the distinct member intents with `"; "`.** Composition is allowed by the plan, and this is the only composition available without a Claude call — but it produces machine prose that then reads as the author's stated purpose. It also fails on size: two members with ~100-character intents already clear step 2's 200-character cap, so a routine two-step merge would manufacture its own advisory finding. Clearing loses information; joining invents authority.
- **Keep the one member that has an intent when the others are silent.** This is the tempting middle ground and it is the case the rule exists to refuse. The survivor also does the silent member's work, so an intent covering only part of the merged step is exactly the "authoritative but wrong" shape — worse here than elsewhere, because after step 5 that line reaches the `run` prompt as a boundary and tells the model the rest of the step is out of scope.
- **Ask Claude to compose one from the folded detail bodies.** New token spend the plan does not allow, and it is a judgment about what a good intent says — the one thing the plan bans anywhere in this feature.
- **Add `intent=` parameters to `split_step` / `merge_steps` so an operator can name the halves' purposes.** No CLI file is in this step's list, so the parameter would have no caller. Routed out — see [Deferred](#deferred).

### Gotchas

- **Never write `""`.** `write_plan` drops `None` fields, so a cleared intent leaves no key in the rewritten frontmatter. An empty string would be written, adding an `intent:` line to plans that never had one — which is the migration the plan forbids.
- **Leave `plan.intent` alone.** Both verbs persist through `plan.model_copy(update={"steps": new_steps})`, which carries every other plan-level field through untouched. Keep that call shape.
- **Keep the fold out of `merge_bridge`.** The bridge's job is opt-in, confirmation, and outcome mapping; it calls `merge_steps` for both its dry-run preview and its real apply, so it inherits the rule automatically. A second copy there would drift.
- **Leave the dry-run previews as they are.** `SplitResult.new_plan` and `MergeResult.new_plan` rows are `(id, title, depends_on)`. Adding intent changes a public dataclass shape, which is outside what the plan allows to change.
- **Do not hand the survivor's intent to the re-author separately.** `merge_steps` writes the folded plan before it re-authors, and `generate_detail` re-parses the plan from disk, so the re-author already sees whatever the fold decided.
- **Reuse step 6's whitespace collapse if it is reusable, otherwise repeat it.** If step 6 landed a standalone collapse helper in `plan_tool/create.py`, call it through the lazy `from plan_tool.create import ...` that `merge_steps` already does for `_apply_step_merge`. If the collapse is baked into step 6's `## Outcome` lift, repeat the one expression here rather than exporting a private name — and see [Deferred](#deferred) for the consolidation.
- **The comparison is intents against each other.** It never compares an intent to plan prose, to a detail body, or to a diff. That is what keeps this step inside the plan's fence, and the folded members' full bodies sitting right there in `prior_body` are the temptation to watch for.

## Tests

### Tests for this step

All 13 land in `tests/test_detail.py`, in the four classes that already cover these verbs. `_build_merge_plan` gains an `intents:` mapping parameter, mirroring its existing `concept_ids:` and `statuses:` parameters; the split cases seed the target's intent by parsing `_SPLIT_PLAN_PENDING`, setting the field, and writing the plan back, the way `_owned_pending_plan` already does for `concept_ids`.

`TestSplitStepOnDemand`:

- `test_split_halves_do_not_inherit_the_target_intent` — target carries an intent; after the split both halves have `intent is None`.
- `test_split_leaves_the_plan_intent_untouched` — the plan-level intent is unchanged by the split's write.
- `test_split_writes_no_intent_key_when_nothing_carries_one` — on a plan with no intent anywhere, the rewritten file contains no `intent:` line.

`TestInteractiveSplit`:

- `test_phase_b_split_halves_do_not_inherit_the_target_intent` — drives the real `escalate_to_split` path through `generate_detail`; neither half's intent equals the mixed target's, and both are `None` under the `_SPLIT_JSON` fixture.

`TestMergeSteps`:

- `test_merged_step_keeps_a_unanimous_member_intent` — both members state the same intent; the survivor keeps it.
- `test_merged_step_keeps_the_first_members_text_verbatim` — members differ only in spacing; the stored value is the first member's string, not a collapsed rewrite.
- `test_merged_step_clears_on_differing_member_intents` — two different intents; the survivor has `None`.
- `test_merged_step_clears_when_a_member_has_no_intent` — one member `None`, the other set; the survivor has `None`.
- `test_merged_step_clears_when_a_member_intent_is_blank` — whitespace-only counts as absent, so the survivor has `None`.
- `test_merged_step_has_no_intent_when_no_member_carries_one` — the legacy case: no member has one, the fold returns `None`, nothing raises.
- `test_merge_leaves_the_plan_intent_untouched` — the plan-level intent survives the fold's write.
- `test_merge_writes_no_intent_key_when_nothing_carries_one` — on a plan with no intent anywhere, the rewritten file contains no `intent:` line.

`TestMergeBridge`:

- `test_merge_bridge_applied_fold_uses_the_same_intent_rule` — through the bridge's applied path, the survivor's intent obeys the same rule, proving the bridge holds no second copy of it.

**Green-before-done gate:** every case above, plus the existing `TestSplitStepOnDemand`, `TestInteractiveSplit`, `TestMergeSteps`, `TestMergeBridge`, `TestMergeIsSafe`, and `TestSplitIsSafe` classes, must pass before this step is finished. Run `uv run pytest tests/test_detail.py -q` for the loop and the full suite before closing — no existing plan fixture anywhere in `tests/` may need an edit, which is this step's share of the plan's no-migration proof.

## Acceptance criteria

- Splitting a step whose `intent` is set leaves both halves with `intent is None` in the written plan.
- Splitting through `plan_tool/launcher.py:escalate_to_split` (the Phase-B path) likewise leaves neither half carrying the target's intent text.
- Merging two steps that state the same intent (ignoring whitespace differences) leaves the survivor carrying the first member's text exactly as written.
- Merging two steps that state different intents, or where any member's intent is missing, empty, or whitespace-only, leaves the survivor with `intent is None`.
- After either verb, `parse_plan(plan_path).intent` equals what it was before.
- After either verb on a plan where no step and no plan carries an intent, `"intent:" not in plan_path.read_text()`.
- `plan_tool/detail.py`'s `split_step` and `merge_steps` docstrings each state their verb's intent rule.
- `git diff --stat` for this step names exactly `plan_tool/detail.py` and `tests/test_detail.py`.
- `rg "intent" plan_tool/create.py plan_tool/launcher.py plan_tool/cli/authoring.py plan_tool/cli/convergence_cmd.py` shows no change from HEAD in those four files.
- `uv run pytest tests/test_detail.py -q` passes, and the full suite passes with no edits to existing plan fixtures.

## References

- [pydantic BaseModel API](https://docs.pydantic.dev/latest/api/base_model/) — `model_copy(update=...)` semantics: it copies the model and overrides only the named fields, which is why a field set (or left unset) on a replacement or on the `merged` step survives `create.py`'s two transforms untouched.
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — `safe_dump` behavior behind `write_plan`; read it for why a `None` field writes no key and a plan with no intent is rewritten without one.
- [YAML Ain't Markup Language (YAML™) revision 1.2.2](https://yaml.org/spec/1.2.2/) — scalar styles and line folding: why a plain multi-line scalar arrives space-joined while a `|` literal block keeps its newlines, which decides what the whitespace-collapse comparison actually compares.
- [How to parametrize fixtures and test functions — pytest](https://docs.pytest.org/en/stable/how-to/parametrize.html) — table-driven cases for the merge fold's five member-intent combinations.

## Applicable guardrails

- **"Nothing becomes required at parse time, and no plan on disk is migrated."** This binds the write path on both verbs: a cleared intent must be `None`, never `""`, so a plan that had no `intent:` key still has none after a split or a merge. Two of this step's acceptance criteria exist to check exactly that.
- **"No step ships a check comparing an intent against prose or against a diff."** The merge fold compares members' intents to each other, which is not what the fence forbids. The tempting breach is right beside the fold: `merge_steps` reads the folded members' full detail bodies into `prior_body`, so checking a kept intent against them, or composing one from them, is one short reach away. Do neither.
- **"Allowed behavior changes: two optional frontmatter fields; one advisory finding class; and rendered input reaching three consumers across five templates — `detail.md` and `detail-jira.md`, `run.md` and `run-jira.md`, and `plan-audit.md`. The run lane additionally gains the plan's existing guardrail and `## Out of scope` sections whether or not an intent is set. Nothing else."** So this step adds no CLI flag, no new finding source, and no change to the `SplitResult` / `MergeResult` shapes. It sets a field the plan already allows, at the two places that assemble a step.
- **"Allowed reorganization: one named move (step 3). Nothing else."** So no extracting a shared one-line collapse helper out of `create.py` here, even though this step is its second user.
- **Audit fence:** a finding asking that intent propagation widen past the four structural verbs, or that intent become required, belongs in `BACKLOG.md`, not in this step.

## Deferred

- **Scope-out and reground propagation** — step 9 owns `plan_tool/scope_out.py` and `plan_tool/reground.py` and the forward seeds they write.
- **Writing the four propagation rules down in the reference docs** — step 11 owns `PLAN_FORMAT.md`, `SEED_FORMAT.md`, `CLAUDE.md`, and the flow docs.
- **A test that a kept intent reaches the merged step's re-author prompt** — that runs through step 4's fence renderer, and this step depends only on step 1, so the assertion cannot be relied on to be available when this step runs. Worth adding once step 4 has landed.
- **Operator-named intents on the CLI** (`plan-tool split --into "…" --intent "…"`, `plan-tool merge --intent "…"`) — no CLI file is in this step's list, so the parameter would have no caller, and the fence caps what behavior may change. File in `BACKLOG.md` if wanted.
- **Showing the intent decision in the dry-run preview** — `SplitResult.new_plan` / `MergeResult.new_plan` rows would have to grow a field, changing a public dataclass. `BACKLOG.md`.
- **Asking the split proposal for a per-half intent** — the rule here permits a freshly authored per-half value, but the prompt lives in `plan_tool/create.py:_propose_step_split`, which is not in this step's file list.
- **A conservation check for `intent` in `plan_tool/create.py:_apply_step_split`**, mirroring the one it enforces for `concept_ids` — unnecessary (this step's rule is that nothing is conserved) and `plan_tool/create.py` is not in scope.
- **One shared one-line collapse helper** across `plan_tool/create.py` (steps 6 and 7) and `plan_tool/detail.py` — a consolidation across modules that `detail` cannot mint. Route it to reconcile or `BACKLOG.md` rather than widening this step.


## Done-context (already done — do not re-plan; source step 8)

Everything in this section is **already implemented** done-context. Do **not** re-plan or re-implement it.

The carved step was left **attempted/partial** (status `pending`) — account for this in the re-plan, but treat its work (in **Scope to re-plan** above) as not yet complete.

## Scope to re-plan (source step 9)

**Carry intent into the scope-out and reground forward seeds**

Files:
- plan_tool/scope_out.py
- plan_tool/reground.py
- tests/test_scope_out.py
- tests/test_reground.py

Change type: feature

# Step 9 — Carry intent into the scope-out and reground forward seeds

## Summary

This step makes the three `create --from-existing` seed renderers carry step 1's `Plan.intent` and `Step.intent` into their output: `plan_tool/scope_out.py`'s `render_carved_seed` and `render_carved_region_seed`, and `plan_tool/reground.py`'s `render_rebaseline_seed`. The main design decision is that **an intent renders attached to the thing it describes and is never re-pointed at a different thing** — a carved step's intent rides its own `## Scope to re-plan` block, and the source plan's intent renders once, labeled as the *source* plan's, never as the new effort's `## Outcome`. The second decision is that a blank or multi-line value is squeezed to one line or dropped before it reaches the seed, because a raw newline in a markdown seed can forge a heading. Neither `compute_narrow` nor `mark_steps_done` needs a production edit — both already copy every other step field through — so their intent rules ship as stated contract plus tests. On green, a carve or a re-baseline hands the next `create` the why behind each carried step, and a plan carrying no intent anywhere produces the same seed text it produces today.

## Table of Contents

- [Summary](#summary) — what ships, the attached-to-its-owner rule, and the result on green.
- [Why](#why) — the two structural verbs whose forward seeds drop the why on the floor.
- [Input](#input) — the five contracts this step reads and does not own, and what the tests cannot prove.
- [Files (creates vs edits)](#files-creates-vs-edits) — four edited files, no new files.
- [Implementation](#implementation) — the two propagation rules, the three renderers, the rejected alternatives, and eight gotchas.
- [Tests](#tests) — approx. 30 new cases plus one extended existing case, and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — greps and equalities a reviewer can run.
- [References](#references) — the YAML, CommonMark, and pytest behavior this step leans on.
- [Applicable guardrails](#applicable-guardrails) — the fence entries that bind, and the two places breaking them is tempting.
- [Deferred](#deferred) — what steps 2, 6, 8, and 10 own, and the two things routed out.

## Why

`scope-out` and `reground` are two of the four structural verbs the plan owes a propagation rule (step 8 covers the other two, split and merge). Both end by writing a **forward seed** — a `create --from-existing` input that becomes the next plan. That seed already carries almost everything a re-decomposition needs: the carried step's title, files, change type, feature tags, `concept_ids`, scope disposition, and full detail body. What it never carries is the *why*. So the one artifact whose entire job is to hand work forward drops exactly the field this plan exists to make durable, and the next `create` run re-derives each step's purpose from its title — the defect the plan opens with, reappearing at the handoff point where the loss is permanent. The seed is also the cheapest place to fix it: all three renderers are pure string builders with no Claude call and no file IO, and the values are already sitting on the `Step` and `Plan` objects each renderer holds.

## Input

Five contracts this step reads and does not own. Read each off HEAD before you start; where a landed name differs from a name below, the landed name wins.

- **Step 1's two schema fields.** `Plan.intent` (created by step 1 in `plan_tool/schema.py`; not at HEAD) and `Step.intent` (created by step 1 in `plan_tool/schema.py`; not at HEAD), each `Optional[str] = None`, storing whatever YAML handed over with no stripping, no cap, and no validator. All five shapes are legal parses and reach these renderers: `None`, `""`, `"   "`, a normal one-liner, and a value with real newlines. This step decides what each one renders.
- **`plan_tool/scope_out.py`'s renderer signatures.** `render_carved_seed` and `render_carved_region_seed` are keyword-only and take **`plan_title: str`, not a `Plan`** — so the plan-level intent has no path into them today and needs a new parameter. Both delegate the per-step body to the shared `_scope_block` helper, which the region renderer calls once per carved step, so a change there lands in both seeds at once.
- **`plan_tool/reground.py:render_rebaseline_seed`'s signature.** It already takes `plan: Plan` plus `flagged_ids`, so both `plan.intent` and every `step.intent` are already in hand — **no signature change**. Its three per-step blocks (`_rebaseline_done_context_block`, `_rebaseline_scope_block`, `_rebaseline_deferred_block`) all render through the one `_rebaseline_step_bullet` helper.
- **`compute_narrow`'s survivor copy.** In `plan_tool/scope_out.py:compute_narrow`, each survivor is built with `s.model_copy(update={"id": ..., "depends_on": ..., "detail": ...})` and the narrowed plan with `plan.model_copy(update={"steps": ..., ...})`. Only the named keys change, so a **survivor's** intent already carries through a carve untouched — that half ships as a stated contract plus a pinning test, with no code edit, the same shape step 8 uses for its split rule. The **plan's own** intent is different: the plan-altitude rule in `## Architecture` requires a carve to **clear** `Plan.intent`, and because `model_copy` touches only the named keys, that clearing does **not** happen for free. Add `"intent": None` to the narrowed plan's `model_copy` update — a real production edit to `compute_narrow`, not a no-edit contract. `plan_tool/reground.py:mark_steps_done` stays a no-edit contract: it sets `step.status` and nothing else, and a re-baseline is not a carve.
- **`plan_tool/reground.py`'s import fence.** `tests/test_reground.py:test_imports_neither_launcher_nor_detail_at_module_level` and `test_reground_still_imports_no_detail_or_launcher` grep the module's own source and fail on any `plan_tool.detail`, `plan_tool.launcher`, or `plan_tool.scope_out` import. That closes the door on borrowing a shared one-line helper from `plan_tool/create.py` or `plan_tool/detail.py` here (see [Implementation](#implementation)).

**What the tests cannot prove.** Nothing here checks whether a carried intent is a *good* one, or whether it still describes the carved work accurately. The suite proves the text arrives, arrives on one line, arrives attached to its own step, and never arrives as a heading. Quality is deliberately unjudged (see [Applicable guardrails](#applicable-guardrails)).

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/scope_out.py` — add a keyword-only `plan_intent` parameter to `render_carved_seed` and `render_carved_region_seed`; render the source-plan line in each renderer's intro block; render the step intent inside `_scope_block`; add the module's one-line normalizer; pass `plan.intent` from `scope_out_step`'s two seed call sites; state the survivor rule in `compute_narrow`'s docstring.
  - `plan_tool/reground.py` — render the source-plan line in `render_rebaseline_seed`'s intro block; append the step intent in `_rebaseline_step_bullet`; add the module's one-line normalizer; state the mark-done rule in `mark_steps_done`'s docstring.
  - `tests/test_scope_out.py` — approx. 17 new cases across the renderer, narrow, and orchestrator sections.
  - `tests/test_reground.py` — approx. 13 new cases plus one extended existing case.

## Implementation

**What must be true on green:** a carved step's intent and a re-baselined step's intent appear in the seed inside the block that describes that step and nowhere else; the source plan's intent appears once, labeled as the source plan's; a plan and steps carrying no intent render the seed text they render today; and no seed contains an `## Outcome` heading.

### The one rule, stated two ways

**An intent renders attached to the thing it describes, and is never re-pointed at a different thing.** That is the seed-altitude form of the plan's propagation contract, and it settles both verbs:

- **scope-out.** A carve changes *which steps exist*, never what a surviving step is *for*. So every survivor's intent carries unchanged (no edit — `compute_narrow` copies it), and the carved step's intent travels into its own `## Scope to re-plan (source step N)` block in the seed. The **narrowed plan's own `Plan.intent` is cleared**, per the plan-altitude rule in `## Architecture`: a carve removes a step, so a plan-level intent written for the un-narrowed plan may now over-claim — the same "authoritative but wrong" hazard the Risks section names, one altitude up. Clearing is the default; a plan keeps its intent through a carve only by stating and pinning why its purpose survives the loss.
- **reground.** Marking a step `done` is a lifecycle transition, not a change of purpose. So every step's intent survives `mark_steps_done` unchanged (no edit), and under the `re-baseline` disposition each rendered step's intent rides its own bullet — done-context, scope-to-re-plan, and parked-deferred alike.

The closest in-repo precedent is `concept_ids`, which both renderers already carry under exactly this rule: `tests/test_scope_out.py:test_region_seed_keeps_concept_ids_attached_to_source_steps` and `tests/test_reground.py:test_rebaseline_seed_does_not_union_concept_ids` both exist to pin "attached to its own source step, never merged across steps." Mirror their shape.

### The three renderers

- **`_scope_block` (both scope-out seeds).** Render the carved step's intent as a labeled line inside the block. One way: `Intent: <one line>` directly under the bolded title, before `Files:` — the why reads first, ahead of the footprint. The exact position is yours as long as it sits inside the block and vanishes when there is no intent.
- **`_rebaseline_step_bullet` (all three re-baseline blocks).** Append the intent to the existing one-line bullet, next to the `— concept_ids: [...]` suffix it already builds. Pick one order for the two suffixes, state it in the docstring, and pin it with a test — an unstated order is the kind of thing a later edit flips silently.
- **The source plan's intent, in all three seeds.** Render one labeled line in each renderer's intro block, beside the existing "This is a `plan-tool create --from-existing` input…" framing sentence. It must carry a short clause saying whose intent it is, because the two verbs stand in different relationships to it:
  - **carved seed / region seed** — the plan the region was carved *out of*. The carved region serves part of that purpose, so the line says the re-plan states its own Outcome rather than inheriting this one.
  - **re-baseline seed** — the same effort, re-decomposed from current code, so the line says the re-decomposition still serves it.

  Same label, one differing clause. That asymmetry is deliberate: it is the difference between the two verbs, not an inconsistency to iron out.

### Rejected alternatives

- **Promote an intent into an `## Outcome` H2 so the next `create` adopts it as the new plan's intent.** This is the tempting one, because step 6 lifts a seed's `## Outcome` into `Plan.intent` and it would close a satisfying loop. Refuse it here for three reasons. A **region seed carries N step intents** and no single one is the region's Outcome, so the renderer would have to invent one. A **carved seed's source plan intent over-claims** — it describes the whole plan, and the seed re-plans a slice, which is exactly the "authoritative but wrong" shape the plan's Risks section names. And it would make this step depend on step 6's lift, which step 9 does not declare in `depends_on`. Writing the intent as labeled prose gets it in front of the model that decomposes the seed without minting a claim about a plan that does not exist yet.
- **Join a region's step intents into one plan-level line.** Same failure as step 8's rejected `"; "` join for merge: it manufactures machine prose that then reads as an author's stated purpose.
- **Import a shared one-line helper from `plan_tool/create.py` or `plan_tool/detail.py`.** `plan_tool/reground.py` cannot — two existing tests grep its source for exactly those edges. Give each module its own small normalizer instead (see the gotcha below) and route the consolidation out.

### Gotchas — the parts not free to vary

- **Collapse before rendering; a raw newline is a heading injection.** A step intent containing `\n## Out of scope\n` renders a real H2 into a `create --from-existing` seed, silently forging a scope-contract section in the next plan's input. Replace every run of whitespace (newlines included) with a single space, then strip — the same shaping step 6 settled for the plan-level lift. Read what step 6 landed and match its rule; do not invent a second one.
- **Absent, empty, and whitespace-only all render nothing.** No label, no blank line, no `Intent: ` with nothing after it. This is the clearing behavior at seed altitude, and it is what keeps the no-intent case producing today's text.
- **`plan_tool/reground.py` gets its own normalizer, always.** Both `render_rebaseline_seed`'s docstring and the two import-discipline tests already record why the module mirrors rather than imports. `plan_tool/scope_out.py` may reuse a suitable existing helper if one is public on a module it already imports (it imports `plan_tool.detail`); otherwise it gets its own copy too. Either way, name it for what it does — `_one_line_intent(value) -> str | None`, returning `None` for absent/blank.
- **The new `plan_intent` parameter is keyword-only with a `None` default.** Every existing caller and test helper (including `tests/test_scope_out.py:_render`) constructs these renderers without it, and they must keep compiling and producing the same output.
- **`render_rebaseline_seed`'s signature does not change.** It already takes the whole `Plan`. Adding a parallel `plan_intent=` parameter would create two sources for one value.
- **Do not enforce step 2's length cap.** Step 2's advisory check judges presence and length; rendering is not checking. A 500-character intent renders in full, collapsed to one line. Truncating here would create a second, silent rule for the same field.
- **Pick one home for the source-plan line.** The intro block or `## Provenance`, not both. Two copies of the same value in one seed is the divergence risk the plan's Risks section names, scaled down.
- **`scope_out_step` and `reground_bridge` both re-parse the plan from disk** before rendering, so the intent that reaches the seed is the on-disk value at carve/re-ground time, not a caller's in-memory `Plan`. Keep the value read from that same parse — the two orchestrators already treat the disk parse as the only trustworthy source.
- **Seed-first ordering is unchanged.** `scope_out_step` writes the seed before `apply_narrow`, and `reground_bridge` writes it before `mark_steps_done`. Nothing here reorders that.

## Tests

### Tests for this step

**`tests/test_scope_out.py`** — approx. 17 new cases, landing in the existing renderer, preview-math, and orchestrator sections.

- `test_scope_block_renders_step_intent` — a carved step with an intent shows it inside its `## Scope to re-plan` block.
- `test_scope_block_omits_absent_step_intent` — `intent=None` renders no label.
- `test_scope_block_omits_blank_step_intent` — `"   "` renders no label.
- `test_step_intent_collapses_to_one_line` — a three-line intent renders with no newline inside it.
- `test_multi_line_step_intent_forges_no_heading` — an intent containing `\n## Out of scope\n` produces no new H2 in the seed.
- `test_seed_names_the_source_plan_intent` — the plan's intent appears once, under a label naming it as the source plan's.
- `test_seed_omits_source_plan_intent_when_absent` — `plan_intent=None` renders no label.
- `test_source_plan_intent_is_framed_as_source_not_as_the_new_outcome` — the rendered line carries the clause telling the re-plan to state its own Outcome.
- `test_seed_writes_no_outcome_heading` — neither seed contains `## Outcome`.
- `test_region_seed_keeps_intents_attached_to_source_steps` — two carved steps with different intents; each appears only inside its own block.
- `test_region_seed_renders_source_plan_intent_once` — a region seed names the plan intent one time, not once per carved step.
- `test_plan_intent_parameter_defaults_to_none` — calling `render_carved_seed` and `render_carved_region_seed` without `plan_intent` still renders.
- `test_no_intent_anywhere_renders_no_intent_line` — a plan and carved step with no intent produce output with no intent label of any kind.
- `test_intent_rendering_is_deterministic` — two renders of the same input are equal.
- `test_narrow_preserves_survivor_intents` — after `compute_narrow`, every survivor's intent is unchanged, including renumbered ones.
- `test_narrow_clears_plan_intent` — the narrowed plan's own `Plan.intent` is cleared by the carve, per the plan-altitude rule in `## Architecture`.
- `test_carved_step_and_plan_intents_reach_the_written_seed` — through `scope_out_step`'s applied path, both values appear in the seed on disk.

**`tests/test_reground.py`** — approx. 13 new cases plus one extended existing case.

- `test_rebaseline_seed_carries_flagged_step_intents` — done-context bullets show each flagged step's intent.
- `test_rebaseline_seed_carries_remaining_step_intents` — scope-to-re-plan bullets show theirs.
- `test_rebaseline_seed_carries_deferred_step_intents` — parked bullets show theirs.
- `test_rebaseline_seed_does_not_union_intents` — a step's intent never appears on another step's bullet.
- `test_rebaseline_seed_omits_absent_step_intent` — `intent=None` adds no suffix.
- `test_rebaseline_seed_omits_blank_step_intent` — `"   "` adds no suffix.
- `test_rebaseline_step_intent_collapses_to_one_line` — a multi-line intent stays inside its bullet.
- `test_rebaseline_bullet_suffix_order_is_stable` — the intent and `concept_ids` suffixes render in the stated order.
- `test_rebaseline_seed_names_the_source_plan_intent` — the plan's intent appears once, labeled as the source plan's.
- `test_rebaseline_seed_omits_source_plan_intent_when_absent` — no label when unset.
- `test_rebaseline_seed_writes_no_outcome_heading` — the seed contains no `## Outcome`.
- `test_rebaseline_no_intent_anywhere_renders_no_intent_line` — the legacy case renders today's text.
- `test_mark_steps_done_preserves_intents` — the actuator flips status only; every step's intent survives, including steps outside the marked set.
- `test_bridge_round_trip_preserves_intents` — re-parse the written plan after an applied `reground_bridge`; every intent is unchanged.
- **Extend `test_reground_still_imports_no_detail_or_launcher`** — add `plan_tool.create` to the forbidden-import list, since that module is the new temptation once a one-line helper lands there in step 6.

**Green-before-done gate:** every case above, plus the existing suites in both files, must pass before this step is finished. Run `uv run pytest tests/test_scope_out.py tests/test_reground.py -q`, then the full suite.

## Acceptance criteria

- `render_carved_seed` and `render_carved_region_seed` each accept a keyword-only `plan_intent` with a `None` default; called without it they render as they do today.
- `inspect.signature(render_rebaseline_seed).parameters` is unchanged from HEAD — no new parameter.
- `rg '## Outcome' plan_tool/scope_out.py plan_tool/reground.py` returns nothing.
- `rg 'plan_tool\.(detail|launcher|scope_out|create)' plan_tool/reground.py` returns nothing.
- A carved seed rendered from a plan and step that both carry an intent contains each value exactly once, and the step's value appears inside its own `## Scope to re-plan (source step N)` block.
- A region seed rendered from two carved steps with different intents keeps each value inside its own block and names the source plan's intent once.
- A re-baseline seed rendered from a plan whose done-context, remaining, and deferred steps each carry an intent shows each value on its own bullet and on no other.
- A seed rendered from a plan and steps with `intent=None` contains no intent label anywhere.
- An intent containing embedded newlines renders on one line, and the rendered seed gains no H2 heading from it.
- After `compute_narrow`, every survivor's intent equals its pre-narrow value and the narrowed plan's `Plan.intent` is cleared; after `mark_steps_done`, every step's intent equals its pre-mark value.
- `uv run pytest tests/test_scope_out.py tests/test_reground.py -q` is green, and the full suite passes with no edits to existing plan fixtures.

## References

- [YAML Ain't Markup Language (YAML™) revision 1.2.2](https://yaml.org/spec/1.2.2/) — scalar styles and line folding, which decide what a "one line" intent is once it round-trips through a plan file and reaches these renderers.
- [ATX headings — CommonMark Spec](https://spec.commonmark.org/0.31.2/#atx-headings) — the rule that makes a line starting with `##` a heading, and therefore why a raw newline inside an intent can forge a section in a seed.
- [How to parametrize fixtures and test functions — pytest](https://docs.pytest.org/en/stable/how-to/parametrize.html) — table-driven cases for the absent / empty / whitespace-only / one-line / multi-line intent combinations, repeated across three renderers.
- [Be clear, direct, and detailed — Claude Docs](https://docs.claude.com/en/docs/build-with-claude/prompt-engineering/be-clear-and-direct) — phrasing the source-plan-intent line so it reads as context for the re-plan rather than as an instruction to adopt it.

## Applicable guardrails

- **"Nothing becomes required at parse time, and no plan on disk is migrated."** This binds every renderer here: an absent or blank intent must produce no label and no placeholder line, so a plan with no intent carves and re-grounds to the seed text it produces today. Two acceptance criteria exist to check exactly that.
- **"No step ships a check comparing an intent against prose or against a diff."** This step renders; it never judges. The temptation sits in the re-baseline seed, where each flagged step's intent lands one bullet away from the code that was actually built — comparing the two is precisely the agreement check the plan bans, and precisely what "already implemented — the code is the ground truth" invites. Render both, compare neither.
- **The fence's allowed behavior changes ("two optional frontmatter fields; one advisory finding class; rendered input across five templates").** These seeds are the propagation the plan's Architecture section requires for two of the four structural verbs, and they add no field, no finding class, and no check. The second tempting spot: neither `_confirm_scope_out` nor `_confirm_reground` gains an intent line — a change to an operator-facing confirm prompt is outside what the fence allows.
- **"Every rule must be able to clear the field."** At seed altitude the clearing form is rendering nothing rather than writing an empty label, and that is what a blank or absent value does.

## Deferred

- **Split's and merge's intent rules** — step 8 owns them in `plan_tool/detail.py`; this step covers only the other two structural verbs.
- **The advisory presence, placeholder, and length check** — step 2 owns it in `plan_tool/review.py`. Nothing here validates a rendered intent.
- **Lifting a seed's `## Outcome` into the next plan's `Plan.intent`** — step 6 owns that lift. These seeds deliberately write no `## Outcome`, so nothing they emit is auto-adopted as a new plan's intent.
- **Documenting the four propagation rules** — step 11 owns `PLAN_FORMAT.md`. This step records its two rules in the touched docstrings only.
- **Consolidating the one-line collapse copies** — after this step the same two-line squeeze exists in `plan_tool/create.py` (step 6), `plan_tool/detail.py` (step 8), `plan_tool/scope_out.py`, and `plan_tool/reground.py`. Merging them needs a shared leaf below all four and touches modules outside this step's file list; route it to `BACKLOG.md` or to reconcile. The mirror is the repo's standing answer where importing would cost a module its leaf status.
- **Re*writing* a narrowed plan's `Plan.intent` to describe what the plan now does** — this step **clears** it on a carve (see `## Implementation`), which is the plan's stated rule; composing a *new* plan-level intent from the survivors would require judging what the narrowed plan is for, and that is its own `BACKLOG.md` entry.
- **Intent in the two confirm prompts** (`plan_tool/scope_out.py:_confirm_scope_out`, `plan_tool/reground.py:_confirm_reground`) — an operator-facing surface change beyond the plan's allowed behavior changes.
- **The CLI operator summaries** (`plan_tool/cli/scope_out_cmd.py`, `plan_tool/cli/convergence_cmd.py`, `plan_tool/cli/review_actions.py`) — not in this step's file list and needing no edit; they read the frozen result objects, which gain no field here.


## Done-context (already done — do not re-plan; source step 9)

Everything in this section is **already implemented** done-context. Do **not** re-plan or re-implement it.

The carved step was left **attempted/partial** (status `pending`) — account for this in the re-plan, but treat its work (in **Scope to re-plan** above) as not yet complete.

## Scope to re-plan (source step 10)

**Pass the plan and step intent into the conceptual audit prompt**

Files:
- plan_tool/review.py
- plan_tool/prompts/plan-audit.md
- tests/test_review.py

Change type: feature

# Step 10 — Pass the plan and step intent into the conceptual audit prompt

## Summary

This step delivers step 1's `Plan.intent` and `Step.intent` to the conceptual audit, whose only plan input today is the **frontmatter-stripped** body (`plan_tool/review.py:_collect_plan_body`) — so a frontmatter field is invisible to it. It adds one formatter, `_format_intent_block`, to `plan_tool/review.py`, one new `${intent_block}` slot to `plan_tool/prompts/plan-audit.md`, and one more keyword in `render_plan_audit_prompt`'s `safe_substitute` call. The main design decision is that **every word this step adds to the prompt lives inside the dynamic block, never in the template's static prose** — so a plan carrying no intent renders exactly the prompt bytes it renders today, and the template diff is one line (a blank line becomes the slot). On green, an intent-carrying plan's audit sees the plan's stated purpose and each step's, framed as input to the `Stay inside the declared scope contract` rule the prompt already carries, and an intent-free plan's audit is untouched.

## Table of Contents

- [Summary](#summary) — what ships, the all-text-inside-the-block decision, and the result on green.
- [Why](#why) — the one consumer a frontmatter field cannot reach by accident.
- [Input](#input) — the five contracts this step reads and does not own, and what the tests cannot prove.
- [Files (creates vs edits)](#files-creates-vs-edits) — three edited files, no new files.
- [Implementation](#implementation) — the formatter, the one-line template edit, the rejected alternatives, and eight gotchas.
- [Tests](#tests) — approx. 17 new cases, four existing cases that must stay green unchanged, and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — greps and diffs a reviewer can run.
- [References](#references) — the `string.Template` and prompt-placement behavior this step leans on.
- [Applicable guardrails](#applicable-guardrails) — the fence entries that bind, and the one line where breaking them is tempting.
- [Deferred](#deferred) — what step 11 and BACKLOG #162 own, and the plan-body defect routed to reconcile.

## Why

The conceptual audit is the consumer where scope creep actually happens — a completeness pass proposing work the plan's author deliberately fenced out — and it is the one consumer a new frontmatter field cannot reach as a side effect. `plan_tool/review.py:render_plan_audit_prompt` builds its plan input from `_collect_plan_body`, which strips the frontmatter and hands over the markdown body only. So steps 4 and 5 can thread intent into `detail` and `run` through the shared fence renderer and the audit still sees nothing. The gap is sharper than "one more consumer": the prompt's `## Rules` section **already** tells the judge to "Stay inside the declared scope contract… within the plan/seed Outcome, In scope, Out of scope / Non-goals" — and the plan/seed Outcome is the one item on that list the prompt never receives. Step 6 makes `Plan.intent` exactly that Outcome, lifted from the seed. This step supplies the missing input to a rule that is already written.

## Input

Five contracts this step reads and does not own. Read each off HEAD before you start; where a landed name differs from a name below, the landed name wins.

- **Step 1's two schema fields.** `Plan.intent` (created by step 1 in `plan_tool/schema.py`; not at HEAD) and `Step.intent` (created by step 1 in `plan_tool/schema.py`; not at HEAD), each `Optional[str] = None`, storing whatever YAML handed over with no stripping, no cap, and no validator. All five shapes are legal parses and reach this formatter: `None`, `""`, `"   "`, a normal one-liner, and a value with real newlines. This step decides what each one renders into the prompt.
- **`render_plan_audit_prompt`'s signature and its early return.** It already takes the parsed `plan` object, so both fields are in hand with no re-parse and no new parameter. Its first act is `body = _collect_plan_body(plan_path)`; `body is None` returns `None` and no Claude call is made. That ordering is a contract — `tests/test_review.py:TestCheckPlanAudit::test_render_prompt_returns_none_for_bodyless_plan` pins it, and a plan that carries an intent but has no body must still return `None`.
- **The template substitution contract.** `plan_tool/prompts/plan-audit.md` is loaded with `string.Template` and rendered with `safe_substitute`. Two consequences bind this step: an unsupplied `${name}` is left in the prompt **literally** rather than raising, so the new key must be passed at the call site; and substitution is a **single pass**, so a `$` or a `${…}` inside an intent value is never re-expanded and needs no escaping.
- **How a dynamic block carries its own framing.** `_format_detail_bundle_status_block` and `_format_carried_findings_block` both put their *instructions* inside the returned string and return `""` when they have nothing to say, so the fully-grounded prompt is unchanged. That is the shape this step copies — it is what makes "unchanged when no intent is set" true for a prompt whose static prose is shared by every plan.
- **The one prompt-render call site.** `render_plan_audit_prompt` is called from exactly two places in the package: `check_plan_audit` and `audit_plan_until_stable` (the multi-pass sampler), both inside `plan_tool/review.py`. The completeness surface reaches the audit through `audit_plan_until_stable` (`plan_tool/cli/completeness_phases.py`, `plan_tool/cli/completeness_cmd.py`), which passes the same parsed `plan`. So one edit reaches every audit pass on every surface, and no CLI file changes.

**What this step cannot verify.** The tests drive canned invoker responses through the real renderer, so they prove the intent text is *delivered* to the prompt and that the prompt is well-formed. They cannot show that a judge actually narrows its findings because of it — that needs a real backend and a corpus of plans, and it is not in this step.

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**

- `plan_tool/review.py` — add `_format_intent_block(plan)`; pass `intent_block=` in `render_plan_audit_prompt`'s `safe_substitute` call; one clause in `render_plan_audit_prompt`'s docstring (and, if it reads stale, `check_plan_audit`'s) naming the new input.
- `plan_tool/prompts/plan-audit.md` — one line: the blank line between `${carried_findings_block}` and `## Plan body` becomes `${intent_block}`.
- `tests/test_review.py` — approx. 17 new cases in a new `TestAuditPromptIntentBlock` class.

## Implementation

**What must be true on green**

- An intent-carrying plan's audit prompt states the plan's intent and every step intent that is set, framed as authoritative scope input.
- A plan carrying no intent anywhere renders the audit prompt **exactly as today**, byte for byte.
- The prompt never asks the judge to compare an intent against plan prose, a detail file, or code.

**The formatter**

Add `_format_intent_block(plan: Plan) -> str` next to the other audit-prompt block formatters in `plan_tool/review.py` (`_format_carried_findings_block`, `_format_detail_bundle_status_block`, `_format_bundle_framing_block`). It takes the `Plan` and nothing else — it reads no file and needs no `plan_path`, `repo_root`, or `detail_grade`.

- **Return `""` when nothing survives.** No plan intent and no step intent → empty string. This is half of the unchanged-prompt property.
- **Squeeze each value to one line.** Collapse every whitespace run to a single space and strip the ends — the `" ".join(value.split())` idiom `plan_tool/review.py` already uses in `_split_audit_fix`'s fix capture and in `check_plan_audit`'s response-tail log line. A real newline in a value would otherwise let a `##` at line start forge a heading in a markdown prompt. Steps 6, 7, and 9 settle the same one-line rule for their own producers; if step 4 or step 6 landed a public one-line helper you can import without a cycle, reuse it rather than minting a third copy — otherwise repeat the two-line collapse here and see the Deferred note.
- **Drop a value that is empty after the squeeze**; treat `None`, `""`, and `"   "` identically.
- **Render a placeholder value as written.** A literal `TODO` goes into the prompt unchanged. Step 2 owns the advisory judgment of whether an intent is any good; this block's job is to deliver the field, and an audit that can see the plan states `TODO` is better off than one that cannot see the field at all. *Rejected:* reusing step 2's placeholder predicate to filter here — it splits ownership of one judgment across two steps and hides the state from the judge.
- **List every step that carries an intent, in `plan.steps` order, keyed by id and title** — `step 3 (Move the plan scope-fence rendering into a shared leaf module)`. The plan body's `## Steps` section says only "See the `steps:` block in the frontmatter", so the bundle headers are the audit's only other source of step titles; keying by both id and title makes each line resolvable on its own. Do **not** filter by `status` — the bundle does not either, and the prompt already has its own rule for how to treat a `done` step.
- **Put the framing inside the returned string**, following `_format_detail_bundle_status_block`. Recommended shape: a bold lead line marking the block authoritative, one sentence saying these lines are the positive half of the fence and pointing at the prompt's existing `Stay inside the declared scope contract` rule, the bullet list, then the use-and-limits sentence: use it to decide whether a gap you are about to raise is inside the plan's declared purpose; a gap outside it is `[out-of-scope-deferred]`, not a completeness finding; do **not** audit the intent itself — do not compare it against the plan's prose, a detail file's `## Why`, or a step's implementation, and do not raise a finding that a step's work disagrees with its stated intent. That last clause is the plan's fence written into the artifact that would otherwise be most tempted to break it.
- **Own the trailing blank line**, as the sibling blocks do (they end their line list with `""`), so the block separates cleanly from `## Plan body`.

**The template edit**

Replace the blank line that sits between `${carried_findings_block}` and the `## Plan body` heading with `${intent_block}`. One line changes. This placement does three things at once: an empty substitution puts a blank line exactly where a blank line already was, so the no-intent prompt is unchanged; the block lands with the other input blocks at the end of the prompt, where the opening paragraph already tells the judge to look for its inputs; and it stays **after** the style guidance, so `TestCheckPlanAudit::test_plan_audit_phrase_guidance_stays_in_stable_prefix` (which asserts guidance precedes `## Plan body`) is unaffected.

*Rejected: adding a sentence to the template's static `## Rules` or opening paragraph.* Static text changes the prompt for every plan, including intent-free ones, which forfeits the unchanged property for no gain — the block's own framing reaches exactly the runs that have something to frame.

*Rejected: rendering step intent into `_format_audit_detail_bundle`'s `### Step NN — <title>` headers.* Adjacency to each step's detail body is the argument for it, and it loses: that formatter is shared by both grades, its output is excerpted and byte-capped per step, its header shape is pinned by `TestJiraGradeAuditBundle`, and a bare step already renders a note in place of a body. One block with one owner is cheaper to reason about and to test.

*Rejected: calling step 4's `plan_tool/scope_fence.py:render_scope_fence` here.* It renders the negative half too — the guardrail sections and `## Out of scope` — and the audit prompt already embeds the whole plan body, so those sections would arrive twice. The plan is explicit that step 10 delivers the intent fields to this prompt and nothing more.

**Gotchas**

- **Supply the key.** `safe_substitute` leaves an unsupplied `${intent_block}` in the prompt as literal text with nothing raising. Add `intent_block=_format_intent_block(plan)` to the existing `safe_substitute` call and cover it with a no-leftover-`${` test.
- **Keep the bodyless early return first.** Build the block after `_collect_plan_body` returns, not before — a plan with an intent and no body must still return `None`.
- **Leave `collect_blocks` alone.** The out-param names the *major* byte contributors for the prompt-budget advisory; `_format_carried_findings_block` is already omitted from it on the same grounds, and `tests/test_review.py:TestAuditPromptBudgetAdvisory::test_plan_audit_collect_blocks_names_major_blocks` asserts the list equals `["plan body", "detail bundle", "detail-bundle status"]` exactly. An intent block is a handful of one-line entries. If you do decide to collect it, that exact-equality assertion must be rewritten in the same edit.
- **No cap, no truncation.** An over-long intent renders whole. Step 2 flags length advisorily; silently clipping here would make the block disagree with the finding.
- **The block is grade-independent.** `detail_grade` selects detail artifacts; intent comes from frontmatter, so both grades render the same block. Don't thread the grade into the formatter.
- **A `$` in an intent value is safe.** Single-pass substitution means a value containing `$` or `${x}` reaches the model literally. Don't add escaping — and don't build the block by pre-substituting into the template.
- **Read the fields off the in-memory `plan`.** `_collect_plan_body` re-reads the file for the body; the intent must not trigger a second parse.
- **Don't touch `_PLAN_AUDIT_REPROMPT_SUFFIX`.** The one-retry path appends to the already-rendered prompt, so the block rides along with no change.

## Tests

All new cases land in `tests/test_review.py`, in a new `TestAuditPromptIntentBlock` class that writes its own plan fixtures (the existing `_write_plan` helper belongs to `TestCheckPlanAudit` and emits no `intent:` keys). This step's `change_type` is `feature` under a plan with `enforce_step_tests: true`, so the test-authoring gate applies and `tests/test_review.py` is in the declared file list.

### Tests for this step

Formatter cases (approx. 9):

- `test_intent_block_is_empty_when_no_intent_is_set` — a plan with no plan intent and no step intent returns `""`. This plus the blank-line slot is what makes the no-intent prompt unchanged.
- `test_intent_block_is_empty_for_blank_and_whitespace_values` — `""` and `"   "` on both the plan and a step return `""`.
- `test_intent_block_renders_the_plan_intent` — the plan-level line carries the value verbatim.
- `test_intent_block_renders_each_step_intent_with_id_and_title` — one line per carrier, keyed by both id and title, in `plan.steps` order.
- `test_intent_block_skips_steps_with_no_intent` — a plan where two of four steps carry one lists exactly those two.
- `test_intent_block_renders_with_only_a_plan_intent` — no step carries one; the block still renders.
- `test_intent_block_renders_with_only_step_intents` — no plan intent; the block still renders.
- `test_intent_block_collapses_a_multi_line_intent_to_one_line` — a value with real newlines renders on one line, so a leading `##` cannot forge a heading.
- `test_intent_block_renders_a_placeholder_value_as_written` — `TODO` reaches the prompt rather than being dropped.

Prompt cases (approx. 8):

- `test_prompt_carries_the_plan_and_step_intent` — both values appear in the rendered prompt.
- `test_prompt_places_the_intent_block_before_the_plan_body` — the block's index precedes `## Plan body`.
- `test_prompt_has_no_unresolved_template_placeholder` — no `${` survives in the rendered prompt.
- `test_no_intent_prompt_inserts_nothing_before_the_plan_body` — for an intent-free plan, the text preceding `## Plan body` is whitespace only after the last style bullet.
- `test_bodyless_plan_returns_none_even_with_an_intent_set` — the early return is preserved.
- `test_intent_block_renders_the_same_at_jira_grade` — the block is unaffected by `detail_grade`.
- `test_dollar_sign_in_an_intent_reaches_the_prompt_literally` — a value containing `${x}` renders unchanged (single-pass substitution).
- `test_prompt_never_asks_for_an_intent_agreement_check` — the block's framing routes an out-of-scope gap to `[out-of-scope-deferred]` and states the do-not-compare rule; assert on that deliberate phrase set, not on a broad word blocklist.

Existing cases that must stay green **unchanged** (do not edit them; if one reddens, the placement or the empty-return is wrong):

- `TestCheckPlanAudit::test_render_prompt_returns_none_for_bodyless_plan`
- `TestCheckPlanAudit::test_plan_audit_phrase_guidance_stays_in_stable_prefix`
- `TestAuditPromptBudgetAdvisory::test_plan_audit_collect_blocks_names_major_blocks`
- every case in `TestJiraGradeAuditBundle` and `TestDetailBundleStatus`

**Green-before-done gate:** every case above, plus `uv run pytest tests/test_review.py -q` and the full suite, must be green before this step is finished.

## Acceptance criteria

- `rg -n 'intent_block' plan_tool/prompts/plan-audit.md` returns exactly one line, and `git diff --stat plan_tool/prompts/plan-audit.md` shows one insertion and one deletion.
- `rg -n 'intent_block' plan_tool/review.py` shows the formatter definition and one `safe_substitute` keyword — no other production site.
- `_format_intent_block(plan)` returns `""` for a plan whose `Plan.intent` is `None` and whose every `Step.intent` is `None`.
- For a plan carrying `intent:` at plan level and on at least one step, `render_plan_audit_prompt` returns a prompt containing both values, positioned before `## Plan body`.
- No rendered audit prompt contains the substring `${`.
- `render_plan_audit_prompt` still returns `None` for a plan with frontmatter (including an intent) and an empty body.
- The blocks list passed to `collect_blocks` still equals `["plan body", "detail bundle", "detail-bundle status"]`.
- The prompt gains no instruction to compare an intent against plan prose, a detail file, or a diff; the block's framing states the opposite explicitly.
- `uv run pytest tests/test_review.py -q` is green, and so is the full suite, with no edits to existing plan fixtures.

## References

- [Template strings — `string` (Python 3 documentation)](https://docs.python.org/3/library/string.html#template-strings) — `safe_substitute`'s leave-unknown-placeholders-in-place behavior and its single substitution pass, which decide whether the new key must be supplied and whether a `$` in an intent value needs escaping.
- [Long context prompting tips — Claude Docs](https://docs.claude.com/en/docs/build-with-claude/prompt-engineering/long-context-tips) — where authoritative context belongs relative to instructions in a long prompt, which informs putting the block with the other inputs before the plan body.
- [Be clear, direct, and detailed — Claude Docs](https://docs.claude.com/en/docs/build-with-claude/prompt-engineering/be-clear-and-direct) — phrasing the block's framing so it constrains which findings the judge raises instead of reading as decoration.
- [YAML Ain't Markup Language (YAML™) revision 1.2.2](https://yaml.org/spec/1.2.2/) — scalar styles and line folding, which set what a parsed intent value can contain and why the one-line squeeze is needed before it reaches a markdown prompt.
- [How to parametrize fixtures and test functions — pytest](https://docs.pytest.org/en/stable/how-to/parametrize.html) — table-driven cases for the five value shapes (`None`, `""`, `"   "`, one-liner, multi-line).

## Applicable guardrails

- **"No step ships a check comparing an intent against prose or against a diff."** This binds this step hardest, because the audit prompt is the one artifact in the plan that instructs a judge. The tempting line is a single sentence asking the judge to confirm each step's design serves its stated intent — it would read as rigor and is exactly the withdrawn prose-conformance shape the plan's `## Out of scope` names. The block's framing carries the opposite instruction in so many words, and `test_prompt_never_asks_for_an_intent_agreement_check` guards it.
- **"Nothing becomes required at parse time, and no plan on disk is migrated."** The formatter must handle an absent intent as the normal case and render nothing for it.
- **"Step 10 delivers the intent fields to that prompt and nothing more"** (the `## Out of scope` entry on BACKLOG #162). Render `Plan.intent` and `Step.intent` only — not the seed's In scope / Non-goals, not the plan-body guardrail sections (already inside `${plan_body_block}`), not a re-rendered `## Out of scope`.
- **Audit guardrails.** A finding out of this audit proposing that intent become required, that an agreement check be added, or that propagation widen past the four structural verbs goes to `BACKLOG.md`, not into this plan.

## Deferred

- **BACKLOG #162's full delivery** — rendering the seed/backlog scope contract (Outcome, In scope, Non-goals) into this prompt as an authoritative block. This step opens the channel with the two intent fields; #162 fills it.
- **Any intent-vs-work agreement instruction, at any altitude** — banned by the plan's fence; if it is ever revisited it is its own entry and must first answer what makes it different from the withdrawn per-`change_type` test-ordering contract.
- **Documenting this hop in `docs/AUDIT_FLOW.md`, `PLAN_FORMAT.md`, and `CLAUDE.md`** — step 11 owns every doc edit in this plan.
- **Threading intent into the reconcile prompt (`plan_tool/review.py:render_review_prompt`) or `run --mode check`** — the plan names three consumers (`detail`, `run`, the conceptual audit); a fourth is a `BACKLOG.md` entry, not an expansion here.
- **Step intent inside `_format_audit_detail_bundle`'s step headers** — the rejected placement; revisit only with evidence that block-level placement loses the judge.
- **Adding the intent block to `collect_blocks`' byte accounting** — the block is small and the carried-findings block sets the precedent for omitting one.
- **Consolidating the one-line squeeze rule** — steps 6, 7, 9, and this step each need "collapse whitespace to one line, drop if empty". If three or more copies land, that is a cross-module extraction a feature step cannot mint; route it to reconcile or `BACKLOG.md` rather than widening this step's footprint.
- **The plan body's stale per-step test-strategy list** — it labels step 10 `non-code` and omits step 11, while the frontmatter has step 10 as `feature` and step 11 as `non-code`. This step follows the frontmatter; correcting the body prose is a plan edit for reconcile.
- **The `Allowed behavior changes` clause's "two prompts" count** — the plan's Overview, Architecture, Acceptance criteria, and this step's own `files:` all name the conceptual audit prompt as the third consumer. This step follows those; the stale numeral is a plan-body fix for reconcile, not something to reinterpret here.


## Done-context (already done — do not re-plan; source step 10)

Everything in this section is **already implemented** done-context. Do **not** re-plan or re-implement it.

The carved step was left **attempted/partial** (status `pending`) — account for this in the re-plan, but treat its work (in **Scope to re-plan** above) as not yet complete.

## Scope to re-plan (source step 11)

**Document both intent fields and the four propagation rules, and close BACKLOG #206**

Files:
- PLAN_FORMAT.md
- SEED_FORMAT.md
- CLAUDE.md
- docs/DETAIL_FLOW.md
- docs/RUN_FLOW.md
- docs/AUDIT_FLOW.md
- BACKLOG.md

Change type: non-code

# Step 11 — Document both intent fields and the four propagation rules, give this plan its own intent, and close BACKLOG #206

## Summary

This step writes down what steps 1–10 built. It states both intent fields in `PLAN_FORMAT.md` (schema rows, semantics, the one-line rule and the cap, the advisory `intent-presence` check, and the four structural verbs' propagation rules), tells seed authors in `SEED_FORMAT.md` that `## Outcome` now becomes durable plan data, records one hop per flow doc (`docs/DETAIL_FLOW.md`, `docs/RUN_FLOW.md`, `docs/AUDIT_FLOW.md`), adds one terse paragraph plus two bullet updates to `CLAUDE.md`, and removes BACKLOG **#206** entirely. The main design decision is **one home per fact**: the field schema and the four rules live only in `PLAN_FORMAT.md`, every other doc cross-links to it, so the contract cannot drift six ways. It also gives this plan its own `intent` — plan-level and all eleven steps — which needs the plan file added to the declared list (noted below). On green, `plan-tool validate intent-scope-fence` reports no `intent-presence` smell, `rg '#206' BACKLOG.md` returns nothing, and every code symbol the seven docs cite resolves at HEAD.

## Table of Contents

- [Summary](#summary) — what ships, the one-home-per-fact decision, and the result on green.
- [Why](#why) — a feature nobody can find is a feature nobody uses, and a shipped backlog entry reads as unstarted work.
- [Input](#input) — the eight upstream outcomes this step describes, and the rule for reading their names.
- [Files (creates vs edits)](#files-creates-vs-edits) — seven declared files plus one added, with the per-file edit.
- [Implementation](#implementation) — the ownership map, the per-file edits, the backlog close, and eight gotchas.
- [Tests](#tests) — the test-authoring gate does not apply; the substitute is a numbered verification list.
- [Acceptance criteria](#acceptance-criteria) — greps and commands a reviewer can run.
- [References](#references) — the YAML, PyYAML, and markdown-anchor behavior this step leans on.
- [Applicable guardrails](#applicable-guardrails) — the fence entries that bind, and the two places breaking them is tempting.
- [Deferred](#deferred) — the sibling-detail sweep and the four things routed out.

## Why

Ten steps land two schema fields, an advisory check, a shared fence renderer, three prompt slots, two `create` producers, four propagation rules, and three seed renderers — and not one line anywhere tells an author the `intent:` key exists. `PLAN_FORMAT.md` is the doc a plan author actually opens, and today it lists eleven step fields and none of them is this one; a field absent from the schema doc reads as a typo, not a feature. The flow docs have the same gap in the other direction: `docs/DETAIL_FLOW.md`'s prompt-input list, `docs/RUN_FLOW.md`'s render step, and `docs/AUDIT_FLOW.md`'s "the plan body plus the per-step detail bundle" sentence each describe a prompt that now carries more than they say. And BACKLOG **#206** — the entry that asked for all of this — still sits in the backlog describing unstarted work, where `BACKLOG.md`'s own rule is "remove a feature's entry when it ships." This step also makes the plan the first user of its own feature: the plan's acceptance criteria require it, and a plan that adds `intent` while carrying none is the exact "documented but unadopted" shape the advisory check exists to flag.

## Input

Eight upstream outcomes this step describes. **Read every name off the landed module, not off this file or the sibling detail that proposed it — the landed name wins.** Each detail file was written before its code existed; where they disagree, correct this doc's citation rather than the code.

- **Step 1 — the two fields.** `plan_tool/schema.py` carries `Plan.intent` and `Step.intent`, both optional and left out of rewritten frontmatter when unset. That elision is the fact the `Defaults` table entry rests on.
- **Step 2 — the advisory check.** `plan_tool/review.py` ships `check_intent_presence` plus a `SMELL_DETECTORS` entry, a public source token (`intent-presence`) and a private character cap. Read both constants' landed values; the cap's number goes in `PLAN_FORMAT.md` and nowhere else.
- **Step 3 — the shared leaf.** `plan_tool/scope_fence.py` now owns the plan-body fence renderer that `PLAN_FORMAT.md` currently cites at its old home in `plan_tool/detail.py`. The re-export keeps the old import path working, so the stale citation will not fail anything — it just names the wrong module.
- **Step 4 — the detail prompt's fence.** The fence renders both halves through one function in `plan_tool/scope_fence.py`, and `plan_tool/prompts/detail.md`'s slot is renamed. `plan_tool/prompts/detail-quality.md` keeps the old slot and deliberately gets guardrails only.
- **Step 5 — the run lane's fence.** `plan_tool/renderer.py` builds the same block for `plan_tool/prompts/run.md` and `plan_tool/prompts/run-jira.md`, rendering nothing when there is no fence.
- **Steps 6 and 7 — the two `create` producers.** A seed's `## Outcome` fills the plan's intent; the step proposal supplies a one-line intent per step. Step 6 settles what "one line" means (a whitespace collapse, no truncation) — quote that rule, do not restate it in different words.
- **Step 8 — split and merge.** Two rules: a split half never inherits the target's intent; a merge survivor keeps one only when every folded member states the same one.
- **Step 9 — scope-out and reground.** Two more rules: survivors carry their intent unchanged, and a carved or re-baselined step's intent rides its own block or bullet in the forward seed, attached to its source step.
- **Step 10 — the audit prompt.** `plan_tool/review.py` formats an intent block into a new `plan-audit.md` slot, which makes the audit prompt's substituted-block count one higher than BACKLOG **#162** currently claims.

**What this step cannot verify.** Nothing here proves the documented behavior is the shipped behavior beyond symbol existence and grep. The checks below confirm every cited symbol resolves and every claim's home is unique; they cannot confirm a sentence describes the code correctly. Read the module when a claim feels uncertain rather than transcribing this file.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `PLAN_FORMAT.md` — five edits: the two `intent:` rows in the frontmatter schema block; two field-semantics entries (the step-level one carries the four propagation rules); the `Defaults` table row plus the optional-plan-level-fields sentence under it; a sentence in `### Validation rules` saying only the type is enforced; the `### Plan-level scope fence …` section rewritten for both halves and the moved renderer; and one new entry in `## Smell checks (advisory)`.
  - `SEED_FORMAT.md` — two bounded edits: the `**Outcome**` bullet gains what `create` now does with it, and the "Canonical H2s pay for themselves" convention's existing omitted-`Outcome` warning gains the new consequence.
  - `CLAUDE.md` — one new architecture paragraph for `plan_tool/scope_fence.py`; the `PLAN_FORMAT.md` and `SEED_FORMAT.md` reference-doc bullets updated; one cross-link clause in the **Structural remedy vocabulary** section; `docs/DETAIL_FLOW.md` added to the per-flow-docs bullet, which omits it today.
  - `docs/DETAIL_FLOW.md` — the `## The per-step author round-trip` prompt-input bullet gains the fence, and `## Source map` gains a row for the leaf.
  - `docs/RUN_FLOW.md` — the `run_step()` gauntlet's render-prompt step gains the fence, the jira-grade section notes both templates carry it, and `## Source map` gains a row.
  - `docs/AUDIT_FLOW.md` — the conceptual-layer paragraph's "plan body plus the per-step detail bundle" sentence gains the intent block, and `## Source map` gains a row.
  - `BACKLOG.md` — delete the whole **#206** entry; delete its clause from the grounding roll-up in the Quality/accuracy lens; correct **#162**'s four-block count; refresh the two entries citing the moved renderer and the renamed detail slot (the fold note inside **#161** and **#197**'s worked example).
  - `docs/implementation-plans/2-intent-scope-fence.md` — **an addition to the step's declared `files:` list.** The step title requires giving this plan its own intent, and a plan's intent lives in its own frontmatter, so the file has to be in the footprint; add the path to the step's `files:` when you start. Two bounded edits: the `intent:` values (plan-level plus all eleven steps), and the `## Testing` per-step test-strategy list, which labels step 10 `non-code` and has no step 11 line — stale after the renumber that inserted the audit step. Step 10's detail routed that correction to reconcile; it lands here instead, now that the file is in this step's footprint.

## Implementation

**What must be true on green.** An author who opens `PLAN_FORMAT.md` learns the field exists, what it holds, what happens to it under each of the four structural verbs, and that nothing enforces it. Each other doc states only its own share and links out for the rest. `BACKLOG.md` carries no trace of **#206**. This plan carries its own intent at both levels.

### The ownership map — one home per fact

Pick the home first, then write. Restating a fact class in a second doc is how six copies drift six ways.

- **`PLAN_FORMAT.md`** — the sole home of the field schema, the one-line rule and its numeric cap, the `intent-presence` source token, and the four propagation rules.
- **`SEED_FORMAT.md`** — the sole home of what a *seed author* must do differently: `## Outcome` becomes the plan's intent, so write it as one sentence.
- **Each flow doc** — its own command's hop, and nothing else. `docs/DETAIL_FLOW.md` owns the authoring prompt's fence input; `docs/RUN_FLOW.md` owns the run/run-jira slot; `docs/AUDIT_FLOW.md` owns the audit prompt's intent block.
- **`CLAUDE.md`** — the module map and the pointers. One paragraph naming the leaf, its two callers, and where the rules live.
- **`BACKLOG.md`** — no ownership at all here; it loses the entry.

### `PLAN_FORMAT.md` — the schema home

- **Frontmatter schema block.** Two rows, each with the same short comment shape the neighbours use: a plan-level `intent` near `title`, and a `steps[].intent` among the step fields. Say "optional" and "one line" in the comment.
- **Field semantics.** Two entries in the existing `**\`field\`** — prose` style. The plan-level one says what it holds and that `create` fills it from a seed's `## Outcome` (step 6). The step-level one is the longer of the two and carries the four propagation rules as a short list, one line each:
  - **split** — neither half inherits the target's intent; both start unset, because the target's line described work that turned out to be two things.
  - **merge** — the survivor keeps an intent only when every folded member states the same one; anything else clears it.
  - **scope-out** — every surviving step's intent carries unchanged and the narrowed plan's own `Plan.intent` is cleared; the carved step's intent travels into its block in the forward seed.
  - **reground** — marking a step `done` changes its lifecycle, not its purpose, so every intent survives unchanged; under the re-baseline disposition each step's intent rides its own bullet in the seed.

  Close the list with the rule the four share: **every rule can clear the field, and clearing beats carrying a value that is no longer true.** A stale intent reads as authoritative while being wrong, and after step 5 it reaches the `run` prompt as a boundary.
- **`Defaults` table + the sentence under it.** One `steps[].intent | null` row; add `intent` to the sentence listing the optional plan-level fields.
- **`### Validation rules`.** One short paragraph beside the existing feature-fields exception: the parser enforces the **type** only. One-line-ness, the cap, and placeholder detection are advisory and live in the smell layer — link to `## Smell checks (advisory)` the same way the feature paragraph does.
- **`### Plan-level scope fence …`.** The heading says "reaches the `detail` prompt" and that is now half the truth. Rename it to name both lanes; `rg` shows no inbound link to its current anchor, so the rename is safe (re-check before you edit). Inside:
  - The fence has **two halves** — the positive half is the plan's and the step's intent, the negative half is the four body sections already listed. Keep the existing four-section list exactly as it is; it is still correct.
  - Repoint the renderer citation from `plan_tool/detail.py:extract_plan_guardrails` to the landed function in `plan_tool/scope_fence.py`, naming both the whole-fence renderer and the guardrail extractor.
  - Name the slot: the implementation prompts (`plan_tool/prompts/detail.md`, `run.md`, `run-jira.md`) share one `${...}` name, while `plan_tool/prompts/detail-quality.md` keeps the older guardrails-only slot **on purpose** — handing a reviewer both the intent and the authored prose sets up the comparison this plan bans. Say that, in one sentence; it is the fact most likely to be "fixed" by a later editor.
  - Keep the existing paragraph about the channel carrying fence content only. It still holds for the negative half and now needs one clause saying the positive half is the author's stated purpose, not a claim about what the plan delivers.
- **`## Smell checks (advisory)`.** One entry in the existing style, naming the check function, the source token, the cap number, and the cardinality decision step 2 settled: absences roll up into one plan-wide finding naming every carrier; a placeholder or over-long value gets its own. Say it never flips an exit code — the section already says that of the whole layer, so one clause is enough.

### `SEED_FORMAT.md` — two sentences, not a section

The seed doc is short and dense; resist adding a heading. Both edits attach to text that already exists.

- The **`Outcome`** bullet gains what now happens to it: `create` lifts it into the new plan's `Plan.intent`, collapsed to one line, so it stops being prose the pipeline re-derives. The authoring consequence is the point — write Outcome as one sentence, because that sentence becomes the plan's durable statement of purpose.
- The **canonical-H2 convention** already warns that a seed shaped for the canonical body silently omits `Outcome` and `In scope`. Add the new cost: no `Outcome` means the plan ships with no `Plan.intent`, and the advisory check will say so.

### `CLAUDE.md` — one paragraph and three bullet fixes

Match the file's per-module paragraph shape (`**Rate-limit recovery loop (\`rate_limit_loop.py\`).**` is the closest model — a leaf, its callers, its one rule). Keep it to a paragraph; depth belongs in `PLAN_FORMAT.md`.

The paragraph should carry: the leaf's path and that it imports no first-party code; the whole-fence renderer and the guardrail extractor by name; the two callers (`plan_tool/detail.py` for authoring, `plan_tool/renderer.py` for `run`/`run-jira`) and the shared slot name; the deliberate exclusion of the review prompt; the audit's separate intent-only block via `plan_tool/review.py`; that presence is advisory and never blocking; and a pointer to `PLAN_FORMAT.md` for the field schema and the four rules.

Then three small fixes: the `PLAN_FORMAT.md` bullet gains "both intent fields"; the `SEED_FORMAT.md` bullet gains that Outcome becomes the plan's intent; the **Structural remedy vocabulary** section gets one cross-link clause saying each remedy carries an intent propagation rule, stated in `PLAN_FORMAT.md`. Do not restate the rules there. While in the reference-docs list, add `docs/DETAIL_FLOW.md` to the per-flow bullet — the new paragraph cites it and the list omits it.

### The three flow docs — each doc's own idiom

These are gate/sequence maps, not prose. Match what is already there.

- **`docs/DETAIL_FLOW.md`** — the `## The per-step author round-trip` **Prompt:** bullet enumerates every input `render_detail_prompt` fills in. Add the fence to that enumeration in the same clipped style, naming both halves. Add a `## Source map` row for `plan_tool/scope_fence.py`.
- **`docs/RUN_FLOW.md`** — the gauntlet's `[4] render prompt` line is where the fence appears. It is a fixed-width ASCII block: keep the alignment, add no `[BLOCK]`/`[WARN]` marker (nothing blocks here), and add no line number. Note in the jira-grade section that both templates carry the same slot. Add a `## Source map` row.
- **`docs/AUDIT_FLOW.md`** — the conceptual-layer paragraph's sentence about rendering the prompt "with the plan body **plus the per-step detail bundle**" gains the intent block as a third named input, framed as what makes the `Stay inside the declared scope contract` rule's Outcome item reachable. Add a `## Source map` row for the formatter.

### Closing BACKLOG #206

- **Delete the entry outright.** `BACKLOG.md`'s stated rule is removal on ship, not a status flip, and nothing of #206 remains open: its one deliberately-unshipped item — the intent-vs-`## Why` agreement check — is refused permanently by this plan's `## Out of scope`, whose durable record is `CLAUDE.md` § "Withdrawn: the per-`change_type` test-ordering contract". **Do not leave a stub entry for that check.** A stub is exactly the "argues for the thing you removed" residue the delete-on-sight rule names.
- **Sweep the roll-up.** The Quality/accuracy lens' `grounding:` list names **#206** with a parenthetical description. Delete that clause and leave the surrounding list punctuation clean.
- **Correct #162's block count.** It states `render_plan_audit_prompt` "substitutes exactly four blocks" and names them. Step 10 makes it five. Update the count and the list, and add a short clause saying the intent fields already ride that prompt so #162's remaining scope is the seed/backlog contract — which keeps the sibling relationship the plan's `## Out of scope` declares.
- **Refresh the two stale renderer citations.** The fold note inside **#161** says `detail` "receives only the headings `extract_plan_guardrails` recognizes (`detail.py`)"; **#197**'s worked example cites `extract_plan_guardrails` → the old detail slot name. Repoint both at the leaf and, for #197, at the renamed slot. Both claims stay true otherwise — this is a name fix, not a rewrite.

### Giving this plan its own intent

- **Plan-level.** Write it by hand; step 6's lift is for plans `create` authors from a seed, and this plan predates the field. The plan's `## Scope guardrails` opens with the sentence that already says it ("make a plan's and a step's *why* durable data that reaches every model acting on it…"). Condense that to one line inside the cap; step 2's detail measured that sentence at roughly 135 characters, so it fits with room.
- **Per step.** One line each, for all eleven steps, saying why the step exists — not what it does, which the title already carries. The step's detail `## Why` is the natural source to condense from.
- **Then run the check.** `plan-tool validate intent-scope-fence` is the fastest confirmation that every carrier is covered and nothing is a placeholder or over-long.

### Gotchas — the parts not free to vary

- **Editing the plan file mid-run is safe, and the reason is specific.** `plan_tool/parser.py:write_plan` does a compare-and-swap and raises `ConcurrentModificationError` when the on-disk frontmatter moved since it was parsed. `plan_tool/launcher.py:_reread_plan_for_writeback` re-reads the plan before every status write-back precisely so an operator edit is not clobbered. Add `intent:` keys only — do not touch `status`, `steps` ordering, or ids while the step is running.
- **Adding intent moves the plan fingerprint.** `plan_tool/review_persistence.py:compute_plan_fingerprint` hashes the plan file's bytes, so this plan's saved completeness and reconcile sidecars go stale and a later reuse prompt reports drift. That is expected, not a defect — say nothing about it in the docs, just do not be surprised.
- **Cite symbols, never line numbers.** `docs/RUN_FLOW.md` carries a few pre-existing `file.py:NNNN` anchors; leave them alone and add none.
- **The renamed heading changes an anchor.** Grep for inbound links to the current `### Plan-level scope fence …` anchor before renaming (`rg 'plan-level-scope-fence'`); at the time of writing there are none, and `PLAN_FORMAT.md`'s own in-file links target `#body-sections-advisory-checked` and `#smell-checks-advisory`, neither of which this step touches.
- **`PLAN_FORMAT.md` has no `## See also` tail** — unlike `DETAIL_FORMAT.md` and `JIRA_FORMAT.md`. Do not add one; cross-link inline the way the file already does.
- **Do not restate the four propagation rules outside `PLAN_FORMAT.md`.** `CLAUDE.md` and the flow docs get a pointer. The moment a second copy exists, the next verb change updates one of them.
- **Do not document a check that does not exist.** Nothing compares an intent to prose, to a `## Why`, or to a diff, at any level. Write presence and shape as the only checked properties, and do not phrase the advisory finding as though it judged quality.
- **The seed doc is a directive doc, not a schema doc.** `SEED_FORMAT.md` tells an author what to write; it must not grow a field table. Two sentences attached to existing bullets is the whole edit.

## Tests

This is a `change_type: non-code` step. The plan sets `enforce_step_tests: true`, but the test-authoring gate keys on `change_type` and fires only for `feature` and `refactor` steps, so it does not apply here and no test file is owed. The substitute is the check list below.

### Verification (non-code step)

Run each from the repo root. Every one is mechanical.

1. **Every cited symbol resolves.** Extract each backticked `plan_tool/…:symbol` citation added by this step and confirm the symbol exists (`rg "def <symbol>" <path>`). Zero misses.
2. **Every cited path exists.** Same for the module and prompt paths added — `plan_tool/scope_fence.py`, `plan_tool/prompts/run-jira.md`, and the rest.
3. **No new line numbers.** `rg -n '\.(py|md):[0-9]+' PLAN_FORMAT.md SEED_FORMAT.md docs/DETAIL_FLOW.md docs/AUDIT_FLOW.md CLAUDE.md` shows nothing this step added; `docs/RUN_FLOW.md`'s pre-existing anchors are unchanged in `git diff`.
4. **The stale renderer citation is gone.** `rg -n 'detail\.py:extract_plan_guardrails' PLAN_FORMAT.md BACKLOG.md` returns nothing.
5. **The four rules have one home.** They appear in `PLAN_FORMAT.md` and are referenced — not restated — everywhere else. Read the `CLAUDE.md` and flow-doc additions and confirm each is a pointer.
6. **The cap number has one home.** No character cap for intent appears outside `PLAN_FORMAT.md`.
7. **#206 is gone, completely.** `rg -n '#206' BACKLOG.md BUG_BACKLOG.md CLAUDE.md README.md` returns nothing, and the grounding roll-up reads cleanly with the clause removed.
8. **#162 is accurate.** Its named block list matches what `render_plan_audit_prompt` substitutes at HEAD.
9. **The plan validates and carries its intent.** `plan-tool validate intent-scope-fence` exits 0 and prints no `intent-presence` line under `smells (advisory):`.
10. **The plan parses and round-trips.** `plan-tool status intent-scope-fence` succeeds after the frontmatter edit.
11. **Section links resolve.** Any new in-file `#anchor` link matches a real heading slug in its target file.
12. **The renamed anchor breaks nothing.** `rg` for the old anchor slug across the repo returns nothing.
13. **Tense check.** Every added sentence is present or future tense, and no removed concept is described in the present tense beside current design.
14. **Clean tree.** `git status` shows only the eight files this step declares (seven declared plus the plan file added above).

## Acceptance criteria

- `PLAN_FORMAT.md`'s frontmatter schema block contains a plan-level `intent:` row and a `steps[].intent:` row, each marked optional and one line.
- `PLAN_FORMAT.md` has a field-semantics entry for each field, and the step-level entry lists all four propagation rules (split, merge, scope-out, reground) plus the shared clearing rule.
- `PLAN_FORMAT.md`'s `Defaults` table has a `steps[].intent | null` row, and the sentence beneath it names `intent` among the optional plan-level fields.
- `PLAN_FORMAT.md`'s `## Smell checks (advisory)` names the check function, the `intent-presence` source, the cap's number, and the roll-up-vs-per-carrier cardinality.
- `rg -n 'detail\.py:extract_plan_guardrails' PLAN_FORMAT.md BACKLOG.md` returns nothing; the scope-fence section cites the function's landed home in `plan_tool/scope_fence.py`.
- `PLAN_FORMAT.md`'s scope-fence section states that `plan_tool/prompts/detail-quality.md` deliberately receives the guardrails half only.
- `SEED_FORMAT.md`'s `**Outcome**` bullet states that `create` lifts it into the new plan's `Plan.intent`, and the canonical-H2 convention names the missing-intent consequence.
- `CLAUDE.md` has one paragraph naming `plan_tool/scope_fence.py`, its two callers, and the pointer to `PLAN_FORMAT.md`; its `PLAN_FORMAT.md` and `SEED_FORMAT.md` reference bullets mention intent; its per-flow-docs bullet lists `docs/DETAIL_FLOW.md`.
- Each of `docs/DETAIL_FLOW.md`, `docs/RUN_FLOW.md`, `docs/AUDIT_FLOW.md` describes its own command's intent hop and has a `## Source map` row for every newly cited symbol.
- `rg -n '#206' BACKLOG.md` returns nothing, and no stub entry for an intent-vs-work agreement check exists anywhere in `BACKLOG.md`.
- BACKLOG **#162**'s substituted-block list matches `render_plan_audit_prompt` at HEAD and notes the intent fields already ride that prompt.
- `docs/implementation-plans/2-intent-scope-fence.md` carries a plan-level `intent:` and an `intent:` on each of its eleven steps, all within the cap and none a placeholder.
- The plan body's `## Testing` per-step list labels step 10 `feature` and carries a step 11 `non-code` line.
- `plan-tool validate intent-scope-fence` exits 0 with no `intent-presence` finding.
- `git status` shows changes to exactly the eight files named in [Files](#files-creates-vs-edits).

## References

- [YAML Ain't Markup Language (YAML™) revision 1.2.2](https://yaml.org/spec/1.2.2/) — scalar styles and line folding, behind the "one line" wording in the schema rows and field semantics.
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — `safe_dump` key ordering and scalar emission, behind the `Defaults` table's elision claim.
- [Basic writing and formatting syntax — GitHub Docs](https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax#section-links) — how a heading's anchor is derived, the reason the scope-fence heading rename needs an inbound-link grep first.

## Applicable guardrails

- **"No step ships a check comparing an intent against prose or against a diff."** This is the guardrail that binds this step hardest, because a docs step is where a checker gets *described* into existence. The tempting line is in `PLAN_FORMAT.md`'s scope-fence section: having explained that `detail-quality.md` gets guardrails only, it reads naturally to add "so a future check could compare the intent to the authored `## Why`." Do not write it. State the exclusion and its reason, and stop.
- **"Nothing becomes required at parse time, and no plan on disk is migrated."** Every sentence about the fields must say optional and advisory. Avoid "should always", "must declare", and any wording that reads as a requirement — an author reading a schema doc treats emphasis as enforcement.
- **"Allowed behavior changes: two optional frontmatter fields; one advisory finding class; and rendered input reaching three consumers across five templates — `detail.md` and `detail-jira.md`, `run.md` and `run-jira.md`, and `plan-audit.md`. The run lane additionally gains the plan's existing guardrail and `## Out of scope` sections whether or not an intent is set. Nothing else."** This step ships no behavior at all. If a doc edit seems to need a code change to be true, the doc claim is wrong — fix the claim.
- **"A finding that this plan's own artifacts fail to carry their intent **is** in scope."** This is what puts the plan file in the footprint and makes the eleven step intents a deliverable rather than a nicety.
- **"Findings proposing that intent be made required, that an agreement check be added, or that propagation widen past the four structural verbs are outside this fence — defer them to `BACKLOG.md`."** Applies directly to the backlog close: do not re-file the refused check as a fresh entry while removing #206.

## Deferred

- ~~The sibling detail files that said "step 10 owns the docs"~~ — **closed 2026-08-01 by a hand sweep** of all nine (details 01–09), which were stale after the renumber that made the audit step 10 and this step 11. Nothing remains for this step. Recorded because the original routing named `plan-tool reconcile-code`, which is the wrong verb for it: `reconcile-code` treats the plan as canonical and edits **code**, so it cannot rewrite detail prose. The only remedies for stale detail prose are a hand sweep or a follow-up `detail` re-author pass.
- **The rest of BACKLOG #162** — the seed/backlog scope contract as an authoritative audit-prompt block. This step only corrects #162's block count and notes that intent already rides that prompt; the entry stays open.
- **Any intent-vs-work agreement check** — refused permanently by the plan's `## Out of scope`, with `CLAUDE.md` § "Withdrawn: the per-`change_type` test-ordering contract" as the durable record. Not deferred to a future entry; deliberately not filed.
- **A `CAPABILITIES.md` entry** — this plan registers no new subcommand, so `plan_tool/capability_catalog.py:check_capabilities` has nothing to flag in either direction. Checked, no edit owed.
- **Threading intent into the jira export and its docs (`JIRA_FORMAT.md`)** — out of the plan's scope; the story summary already carries the motivation.
- **A `DATA_CONTRACT.md` edit** — that doc covers persisted runtime schemas (sidecars, fingerprints, manifest) and enumerates no `Plan`/`Step` field, so the new fields add nothing there.


## Done-context (already done — do not re-plan; source step 11)

Everything in this section is **already implemented** done-context. Do **not** re-plan or re-implement it.

The carved step was left **attempted/partial** (status `pending`) — account for this in the re-plan, but treat its work (in **Scope to re-plan** above) as not yet complete.

## External prerequisites (not done yet)

- step 1 [current]: Add optional intent fields to Plan and Step
- step 2 [pending]: Add an advisory check that flags a missing, placeholder, or over-long intent
- step 4 [pending]: Render the plan and step intent in the shared fence and pass it to the detail prompt
- step 5 [pending]: Pass both fence halves into the run and run-jira prompts through renderer.py

## Provenance

- Source plan: docs/implementation-plans/2-intent-scope-fence.md
- Carved steps: 6, 7, 8, 9, 10, 11
