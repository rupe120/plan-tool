> **Auto-archived**: this plan was swept on 2026-08-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Wrap a stage's authoring prompt in a shared revision prompt that asks the model to answer each open feedback item

## Summary

Create `plan_tool/prompts/roadmap-revision.md` — one shared template, not one per stage — and teach `plan_tool/roadmap.py` to render it around a stage's already-rendered authoring prompt when that stage has a predecessor artifact. The revision template adds three things the authoring prompts do not have: the prior artifact as a delimited block, an active-feedback block holding only the `open` rows, and the revision contract (preserve what feedback does not ask you to change, answer every open feedback id in `proposed_response`, never touch a request's source text, never delete or defer a row, keep settled decisions). The key design decision: **revision mode is chosen by predecessor presence and wraps the authoring prompt as a substituted value in one pass**, so a first run travels the same code and produces the same prompt it produces today, and a `$` in the brief is still never re-substituted. On green, `_render_stage_prompt` with no predecessor returns exactly what it returns at HEAD; with one, the invoker receives the prior artifact, the open feedback, and a rules block that sits *after* the wrapped authoring text so "re-author from scratch" is overridden rather than left as the last word.

## Table of Contents

- [Summary](#summary) — what lands and what is observable on green.
- [Why](#why) — the gates from step 2 are checking rules the model was never told.
- [Input](#input) — the position-01 prompt seam, steps 1–2's contracts, and what canned replies cannot prove.
- [Files (creates vs edits)](#files-creates-vs-edits) — one new template, two edits.
- [Implementation](#implementation) — the wrap, the feedback block, the template's own contract, and the parts not free to vary.
- [Tests](#tests) — the roster in `tests/test_roadmap.py`, the two cases this step repairs, and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — checkable facts a reviewer can run.
- [References](#references) — the prompting docs this step's ordering and output contract lean on.
- [Applicable guardrails](#applicable-guardrails) — which plan fences bind this step's prompt and code.
- [Deferred](#deferred) — what steps 5–8 own.

## Why

After step 2 lands, `plan_tool/roadmap_gates.py` holds three gates — `check_design_row_continuity`, `check_feedback_integrity`, `check_settled_decisions` — that judge a revision against its predecessor, and no prompt in the tree mentions any of their rules. A stage handed a predecessor would spend its whole `MAX_STAGE_ATTEMPTS` budget discovering by rejection that it may not delete a feedback row or re-decide a settled question. Two parametrized cases in `tests/test_roadmap.py` already encode exactly that objection — `test_domain_prompt_states_every_domain_gate_rule` and its constraints sibling fail for any gate in a shipped gate set whose rule no prompt states — so **step 2's landing leaves those two cases red, and this step owns the repair**: the three new gates' rules belong in the revision prompt, not in the authoring prompts, because they cannot fire on a first run. Beyond satisfying the gates, this is also the only step that asks the model for the thing the plan exists to deliver: a plain-language account, per feedback id, of what it proposes to do.

## Input

This step reads three contracts. Each must stay true.

- **`plan_tool/roadmap.py:_render_stage_prompt` is the one prompt-assembly seam.** It takes `(stage, *, slug, brief, upstream)`, looks the template up under `plan_tool/renderer.py:prompts_dir()`, and substitutes with `string.Template.safe_substitute`. Its docstring's "Every stage gets the same variable map" rule holds: the map is the slug, the brief, and every artifact *below* this stage as it sits on disk — never "written so far".
- **`_run_stage` renders the base prompt once, before the attempt loop, and appends `_corrections_block` per attempt.** Feedback must ride on the base prompt, not the corrections channel: corrections replace one another every attempt, and a reviewer's request is stable input across all of them.
- **`_LoadedArtifact` is the existing carrier for "an artifact as it sits on disk"** — `stage`, `path`, `text`, `artifact`, with the text and the parse coming from one read. It already holds both halves a revision needs, so this step reuses it rather than minting a second carrier. Step 5 produces one for the predecessor via `_load_stage_artifact`.
- **Step 1's review rows**, by owning step rather than by mechanism: step 1 produces `FeedbackRow` (`id`, `target`, `request`, `state`, optional `proposed_response`), `FeedbackTarget` / `FeedbackTargetKind` (`artifact` / `row`), `FeedbackState` (`open` / `awaiting-review` / `deferred`), `RemovalRecord` (`removed_id`, `rationale`, `feedback_ids`), the `REVIEW_ROW_KEYS` constant, and `feedback` / `removals` collections defaulting to `()` on both artifacts. Step 1 deliberately kept these keys **out** of `DOMAIN_ROW_KEYS` / `CONSTRAINTS_ROW_KEYS`, which is why the authoring prompts never name them and the revision template has to.
- **Step 2's three gates and their envelope field.** Step 2 produces `ArtifactEnvelope.predecessor` (defaulted to `None`) and the three gates listed above, all inert without a predecessor. This step states their rules in prose for the model; it never runs, wraps, or duplicates a gate.
- **The two authoring prompts are the wrapped text, and one of their statements is wrong in revision mode.** `plan_tool/prompts/roadmap-domain.md` and `plan_tool/prompts/roadmap-constraints.md` both say, under "The rules your artifact is checked against", that on a failure you get the same prompt again with no copy of what you wrote, "so you re-author the whole artifact from scratch". The wrapper must override that sentence explicitly — see [Implementation](#implementation).
- **What this step cannot verify.** Every test here drives canned replies through the real parser and gate sets. That proves the contract is *satisfiable* and that the prompt text says what it must; it proves nothing about how often a real model honors it. Hit-rate and prompt-pressure measurement need a real brief and somewhere to record the outcome — step 9's real-run exercise owns that.

## Files (creates vs edits)

**New files:**

- `plan_tool/prompts/roadmap-revision.md` — the shared revision wrapper. No packaging change: `pyproject.toml`'s wheel target ships the whole `plan_tool` package tree, so a file under `plan_tool/prompts/` is package data already.

**Existing files (edits only):**

- `TESTING.md` — extend the roadmap neutralization row to name the revision template beside the stage templates.
- `plan_tool/roadmap.py` — add `REVISION_PROMPT_FILENAME`, the revision variable-name constant, the `_NO_ACTIVE_FEEDBACK` line, an open-feedback reader, the active-feedback block renderer, the revision renderer, and a keyword-only `predecessor=None` threaded through `_render_stage_prompt` and `_run_stage`. Add the `FeedbackState` import.
- `tests/test_roadmap.py` — extend the `env` fixture with a revision-template stub, add the helpers and cases in [Tests](#tests), and repair the two parametrized gate-rule cases step 2 reddens.

## Implementation

### What must be true when this is done

- `_render_stage_prompt(stage, slug=…, brief=…, upstream=…)` with no predecessor returns the same string it returns at HEAD, and a first run's prompt shows no revision framing at all.
- With a predecessor, the rendered prompt holds the prior artifact's on-disk text, an active-feedback block naming every `open` row and no other row, and the revision rules — with the rules **after** the wrapped authoring text.
- One template serves every stage. `RoadmapStage` gains no field, and the run loop gains no branch on which stage it is running.
- `run_roadmap` still passes no predecessor, so production behavior is unchanged and the revision path is reachable only from a test until step 5 wires it. That is the same additive shape step 2 used for `ArtifactEnvelope.predecessor`.
- Both parametrized gate-rule cases in `tests/test_roadmap.py` are green again, with the three new gates' rules found in the revision prompt.

### The wrap, and why it is one substitution pass

Recommended shape: keep `_render_stage_prompt` as the single entry point and give it a keyword-only `predecessor` defaulting to `None`. Render the authoring prompt exactly as today; when there is no predecessor, return it; otherwise hand it to a `_render_revision_prompt(authoring_prompt, *, predecessor)` that reads `REVISION_PROMPT_FILENAME` and substitutes three values.

- **Annotate the parameter as `Optional["_LoadedArtifact"]`.** `_LoadedArtifact` is declared below this function, and the existing `upstream: Sequence["_LoadedArtifact"]` hint already uses the quoted form — match it.
- **The authoring prompt is a substituted *value*, never concatenated text that gets a second pass.** `Template.safe_substitute` scans the template once and inserts replacement values without rescanning them, so a `${slug}` a reviewer wrote in their brief survives into the revision prompt as literal text — which is how it already behaves at HEAD. Concatenating the two templates and substituting once over the join would silently start substituting the brief and the predecessor artifact. This is the one mechanism in the step that is genuinely not free to vary.
- **Three variables, and no more:** the authoring prompt, the predecessor artifact text, and the active-feedback block. Do **not** add a filename variable — deriving `01-domain.md` from a stage row needs a `plans_dir` the renderer does not have, and the wrapped authoring prompt already names its own file in its title. Do not add the brief or the slug either; they arrive inside the wrapped text.
- **Derive the test's allowed variable set from the code.** One way: a module constant naming the three variable names, which the renderer builds its map from and the placeholder test compares against — the same "derive, don't hand-copy" move `tests/test_roadmap.py:_allowed_variables` makes against `STAGES`.
- **Read the revision template with its own `is_file()` check and its own `RoadmapError` message**, naming the expected path the way the stage-template check does. Do **not** extract the two reads into a shared helper: that is a behavior-preserving refactor of existing code riding inside a feature step. The two bodies differ in their message literals, and `tests/test_duplication.py` normalizes past docstrings, function names, and parameter names only — string literals are compared — so keeping them separate does not add a duplicate group.

### The active-feedback block

- **Read the rows with `getattr(artifact, "feedback", ())`**, mirroring `_pending_decision_count`'s existing choice. Both artifacts carry the same field name, so there is no kind dispatch, and a stage carrying some other artifact type (the synthetic third stage in `tests/test_roadmap.py:TestSyntheticThirdStage`) still renders.
- **Send only `state == FeedbackState.OPEN` rows**, in artifact order. `awaiting-review` and `deferred` rows are visible to the model inside the predecessor artifact text and must be carried forward untouched; listing them as active guidance is what would make the model answer a deferred row and trip step 2's carried-response and state-transition rules.
- **Each entry names three things:** the feedback id (the model keys its `proposed_response` to it), the target (`artifact`, or `row` plus the `row_id`), and the request quoted exactly as written.
- **Quote the request verbatim, whole.** No truncation, no reflow, no per-row or per-block cap, no count limit — the plan's fence forbids any rejection or cap keyed on a request's length, shape, count, or semantics. A multi-line request keeps its lines.
- **No open rows is a real and common case** — a `--from-stage` re-entry over an artifact whose feedback is all `deferred`, or one carrying none at all. Render an explicit "no active feedback; preserve the artifact above except where a correction below requires a change" line from a module constant, so a test pins the wording once and the model never sees a dangling empty heading. Revision mode is selected by **predecessor presence, not feedback presence** — step 2's gates apply either way.

### What the revision template must say

The template's job is only what the authoring prompt cannot say. It inherits the schema, the check list, the prose-body rule, the writing style, the example skeleton, and the strict output format from the wrapped text.

- **Order the template for a long-context read:** the prior artifact block, then the active-feedback block, then the wrapped authoring contract, then the revision rules and the output reminder last. The wrapped authoring prompt ends with its own skeleton and its own "re-author from scratch" line, so anything placed before it loses to text the model reads later.
- **Override every wrapped statement revision mode falsifies, each by name — do not re-affirm the wrapped text wholesale.** "The schema and the checks below still apply" is false as written, and the four statements it wrongly re-affirms are each load-bearing:
  1. **The collection inventory.** `roadmap-domain.md` says "Everything above the closing `---` is YAML: four collections, in this order" (constraints: "three collections"). A revision emits **the wrapped inventory plus `feedback` and `removals`, in that order** — six for the domain stage, five for constraints. A model obeying the wrapped count drops both and trips `VIOLATION_DROPPED_FEEDBACK` on every carried row until the budget is gone. **State the override relative to the wrapped inventory, never as a fixed number:** one template wraps two prompts with different counts, so any literal count is wrong for one stage — and the constraints stage is the one #215 names as having no retry margin. The same rule governs every override below.
  2. **The no-questions-back rule.** Both prompts say "Do not hedge in the prose, and do not ask a question back: nothing answers." In revision mode something *does* answer — the reviewer — and a clarifying question in `proposed_response` is a contract this step defines and step 9 is obliged to exercise. Override it for `proposed_response` only; the artifact prose stays unhedged.
  3. **The gate count.** "Meet all six the first time" is the domain stage's authoring count, and constraints carries its own. Revision mode adds this step's three predecessor gates to whichever the wrapped prompt states, so phrase the override as *the checks above plus the three revision gates* rather than a number.
  4. **The skeleton's claim.** "The skeleton below shows the shape and clears every check above" — it carries no review rows, so against a predecessor it clears nothing. Say the skeleton is the authoring shape and the revision adds the two review collections.
- **Then override the re-author sentence by name**, as before: the starting point is the artifact above — including on a retry, where the rejected attempt is still not shown but the prior artifact still is.
- **Pin the overrides with a test per statement**, so a later edit to either authoring prompt that reintroduces one is caught here rather than in a burned retry budget.
- **State the revision contract:** preserve every row the feedback does not ask you to change; for each active feedback id set `state: awaiting-review` and write a `proposed_response` that names the design ids it affects and asks one focused question when the request is genuinely ambiguous or implies a scope the model cannot infer from the reviewer's words; carry every non-active feedback row through unchanged, response included.
- **State the prohibitions the gates enforce**, each as a move the model can actually make: never delete, close, or defer a feedback row; never change a row's `id`, `target`, or `request`; the only state move you may make is `open` → `awaiting-review`; do not invent a feedback row.
- **State the removal path:** dropping a design row requires a `removals` record naming the row, a non-blank rationale, and at least one id from the feedback above — and the row must not still be declared in the artifact you emit. Say that only an **`open`** feedback row may be cited: a `deferred` row is one the reviewer parked and an `awaiting-review` row is one you already answered, so neither authorizes a removal.
- **State the transitive block on removals.** A design row that a `settled` decision anchors to is not removable while that decision stays settled — refuse the removal and say in `proposed_response` that the reviewer must set that decision to `pending` first. This is the un-settle escape applied to a *removal*, not only to a change of the decision itself, and without it the stage oscillates between gate 3 and `check_decision_records`.
- **State that `removals` records are as un-authorable as feedback rows.** A fabricated removal is the more dangerous of the two: it lands on disk, becomes a *carried* removal that later revisions skip re-judging, and its always-on `VIOLATION_REMOVAL_NAMES_A_PRESENT_ROW` then permanently blocks re-declaring the row it names. Every removal must cite an `open` predecessor feedback row, and on a predecessor-free stage there is no legal removal at all.
- **State the two moves the model does *not* have, because both are reachable mistakes.** It may never delete or prune a carried `removals` record — restoring a previously removed design row is the reviewer's move, made by deleting that record in the editor, and attempting it from the model side trips gate 1. And it may never author a `feedback` row of its own: every feedback row in the artifact you emit must have come from the one you received.
- **State settled finality and its escape:** a decision the prior artifact marks `settled` keeps its id, `status`, `chosen_option`, and `anchor`; keep its `rationale` and `rejected_alternatives` too. When feedback asks for a change a settled decision blocks, say so in `proposed_response` and tell the operator to change the prior decision's `status` to `pending` first. Without that sentence the model has no move and burns the budget.
- **Restate the review-row schema inline.** No template under `plan_tool/prompts/` cites a repo doc, and none can: the verb runs inside whatever repo the operator is in, which has no copy of `ROADMAP_FORMAT.md`. Name every key of `REVIEW_ROW_KEYS`, `FeedbackRow`, `FeedbackTarget`, and `RemovalRecord`, both target kinds, and all three lifecycle values, and pin the restatement with a containment test against the landed constants.
- **Embed a small worked example of the two review collections only** — placeholder ids and `<one line>` bodies, following `plan_tool/prompts/roadmap-domain.md`'s skeleton convention. Show one answered feedback row and one cited removal. Do not embed a whole artifact: the wrapped authoring prompt already carries the skeleton, and a second full example invites the model to copy a domain that is not the project's.
- **Write it plain and short**, matching the two authoring prompts' voice: present tense, everyday words, one idea per sentence.

### Two mechanics that will bite

- **A literal `$` in the template must be written `$$`.** `safe_substitute` leaves an unknown `${name}` in place rather than raising, so a typo ships to the model as literal text with nothing red firing. No template at HEAD contains a bare `$`; keep it that way and pin it.
- **The two parametrized gate-rule cases need a third source, not a loosened assertion.** `_GATE_PROMPT_SUBJECTS` and `_CONSTRAINTS_GATE_PROMPT_SUBJECTS` are keyed by gate name so a gate joining a shipped set with no stated rule reddens a test instead of costing retry budget. Keep that property: add a revision-scoped map for the three new gate names and have the case fall back to it, checking the phrase against the revision template's text. Do not delete the `assert subjects` guard, and do not add the three gates to the authoring maps — their rules cannot appear in a prompt that has no predecessor to talk about.

## Tests

**`TESTING.md` is one of this step's declared files** — it appears in the step's `files:` list, in the Files section above, and in the footprint criterion, all three. **`TESTING.md`'s roadmap neutralization row is this step's to update.** It currently tells a test author to patch `roadmap.prompts_dir` to a tmp dir for the stage templates; once this step makes a stage with a predecessor read `plan_tool/prompts/roadmap-revision.md` and raise `RoadmapError` when it is absent, that advice reddens any future revision-mode case. This step creates the template, so it owns the row — add `TESTING.md` to the step's `files:` list and name the revision template beside the stage templates.

All new cases go in `tests/test_roadmap.py`, in the file's existing section-comment layout. Extend the `env` fixture to write a `roadmap-revision.md` stub carrying the three placeholders, so injected-stage revision cases stay hermetic; use `shipped_env` for every case that reads the real template. Add a `_revision_prompt_text()` helper beside `_domain_prompt_text()`, a `_predecessor(...)` helper building a `_LoadedArtifact` from `_domain(...)` plus its rendered text, and local `feedback_row(...)` / `removal(...)` builders. `_prompt_example` does not fit the revision template — it demands exactly one fenced block opening on `---`, and the revision example is a fragment while the two placeholder blocks are not fences at all — so add a sibling helper that finds the fragment by its leading `feedback:` key.

### Tests for this step

Approx. 39 new cases plus 2 repaired. Every one must be green before this step is done, and `tests/test_roadmap_artifacts.py`, `tests/test_roadmap_gates.py`, and `tests/cli/test_roadmap_cmd.py` must stay green **without being edited**.

Repaired (red after step 2 lands):

- `test_domain_prompt_states_every_domain_gate_rule` — falls back to the revision map for a predecessor-derived gate; still fails for a gate stated nowhere.
- `test_constraints_prompt_states_every_constraints_gate_rule` — same treatment.

First-run parity and mode selection:

- `test_no_predecessor_renders_the_authoring_prompt_unchanged` — the render equals the authoring template's own substitution.
- `test_first_run_prompt_shows_no_revision_framing` — end to end, the invoker's prompt names no revision heading.
- `test_a_predecessor_wraps_the_authoring_prompt_whole` — the entire authoring text appears inside the revision prompt.
- `test_revision_prompt_carries_the_predecessor_text_verbatim` — the on-disk bytes, not a re-render.
- `test_revision_rules_follow_the_wrapped_authoring_prompt` — the rules block's position is after the wrapped text.
- `test_missing_revision_template_raises_naming_the_expected_path` — pre-flight, invoker never called.
- `test_both_stages_use_the_one_shared_revision_template` — no per-stage revision file, no new `RoadmapStage` field.

The active-feedback block:

- `test_only_open_feedback_is_sent_as_active_guidance` — awaiting-review and deferred ids are absent from the block.
- `test_every_open_feedback_id_appears_in_the_active_block`.
- `test_active_block_preserves_artifact_order`.
- `test_a_request_is_quoted_verbatim` — including its punctuation and casing.
- `test_a_multi_line_request_keeps_its_lines`.
- `test_a_long_request_is_never_truncated` — the no-cap fence.
- `test_a_row_target_names_its_row_id`.
- `test_an_artifact_target_is_labelled_with_no_row_id`.
- `test_no_open_feedback_renders_the_explicit_no_active_feedback_line`.
- `test_deferred_rows_reach_the_model_only_through_the_predecessor_text`.
- `test_a_synthetic_stage_artifact_without_feedback_renders_the_block` — the `getattr` default.

The reflection contract, against the shipped template (phrase checks through `_flattened`):

- `test_revision_prompt_requires_a_response_for_every_open_feedback_id`.
- `test_revision_prompt_forbids_deleting_closing_or_deferring_feedback`.
- `test_revision_prompt_forbids_altering_an_id_target_or_request`.
- `test_revision_prompt_states_the_one_allowed_state_transition`.
- `test_revision_prompt_forbids_inventing_a_feedback_row`.
- `test_revision_prompt_requires_a_cited_rationale_bearing_removal`.
- `test_revision_prompt_pins_a_settled_decision_and_names_the_un_settle_action`.
- `test_revision_prompt_overrides_the_authoring_re_author_instruction`.
- `test_revision_prompt_tells_the_model_to_carry_non_active_feedback_unchanged`.
- `test_revision_prompt_names_every_review_row_key` — parametrized over the names `REVIEW_ROW_KEYS` and step 1's three row types declare, reusing `_row_key_names`.
- `test_revision_prompt_names_every_feedback_state_value`.
- `test_revision_prompt_names_both_feedback_target_kinds`.
- `test_revision_prompt_cites_no_repo_document` — no `FORMAT.md` reference.

Template mechanics:

- `test_revision_prompt_placeholders_are_a_subset_of_the_revision_variable_map`.
- `test_revision_prompt_renders_with_no_unresolved_placeholder`.
- `test_a_dollar_placeholder_in_the_brief_survives_into_the_revision_prompt` — the one-pass rule.
- `test_revision_template_holds_no_bare_dollar`.

The embedded example:

- `test_revision_example_parses_when_spliced_into_an_artifact` — through step 1's real parser.
- `test_revision_example_clears_the_gate_set_against_a_matching_predecessor` — through step 2's real gates, expecting an empty list.
- `test_revision_example_uses_placeholder_ids` — nothing project-shaped to copy.

Retry loop and logging:

- `test_corrections_append_after_the_revision_wrapper`.
- `test_the_active_feedback_block_is_identical_on_every_attempt` — feedback is stable input, not a correction.
- `test_prompt_bytes_records_the_wrapped_revision_prompt` — the run log's per-attempt count covers the whole prompt.
- `test_run_is_non_interactive` stays green unchanged — no confirm, no TTY branch enters here.

## Acceptance criteria

- `plan_tool/prompts/roadmap-revision.md` exists and holds exactly three template placeholders: the authoring prompt, the predecessor artifact, and the active-feedback block.
- `_render_stage_prompt` called without a predecessor returns a string equal to the authoring template's own `safe_substitute` output — no revision text, no trailing newline difference.
- `_render_stage_prompt` called with a predecessor returns a string containing the whole authoring prompt, the predecessor's on-disk text, and every `open` feedback row's id and request; the index of the revision-rules heading is greater than the index of the authoring prompt's first line.
- A predecessor whose feedback rows are all `awaiting-review` or `deferred` renders the no-active-feedback line and none of those ids in the active block.
- A brief containing the literal text `${slug}` renders into the revision prompt still reading `${slug}`.
- `rg -P '\$(?!\{)' plan_tool/prompts/roadmap-revision.md` returns nothing.
- `rg -n 'FORMAT\.md' plan_tool/prompts/roadmap-revision.md` returns nothing.
- The revision template's fenced example, spliced into a conforming domain artifact, parses through `parse_domain_artifact` and yields an empty list from `run_domain_gates` with a matching predecessor in the envelope.
- `rg -n 'stage\.(name|number) ==' plan_tool/roadmap.py` returns nothing, and `RoadmapStage` declares no revision-prompt field — the shared wrapper added no per-stage knowledge.
- `rg -n 'input\(|isatty' plan_tool/roadmap.py` returns nothing.
- `run_roadmap` passes no predecessor to `_run_stage`, so a production run's prompts are unchanged; step 5 supplies the predecessor.
- `uv run pytest tests/test_roadmap.py tests/test_roadmap_artifacts.py tests/test_roadmap_gates.py tests/cli/test_roadmap_cmd.py -q` is green, with the last three files unmodified.
- `uv run pytest tests/test_duplication.py -q` is green with no new `ALLOWED_DUPLICATE_GROUPS` entry.
- `git diff --name-only` lists exactly `plan_tool/roadmap.py`, `TESTING.md`, `tests/test_roadmap.py`, and the new `plan_tool/prompts/roadmap-revision.md`.

## References

- [Long context prompting tips — Claude Docs](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/long-context-tips) — read for why the prior artifact and the feedback block need explicit boundaries and why the revision rules belong after the wrapped documents rather than before them.
- [Prompting best practices (Claude 4) — Claude Docs](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/claude-4-best-practices) — the scoped-edit framing this template asks for: change the named rows, keep the rest, and re-emit the whole artifact under one output contract.
- [Increase output consistency — Claude Docs](https://docs.anthropic.com/en/docs/test-and-evaluate/strengthen-guardrails/increase-consistency) — read for why the review-row schema and the lifecycle vocabulary are restated inline with a worked example instead of described loosely.
- [Prompt caching — Claude Docs](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching) — relevant to keeping the base prompt identical across attempts, with only the corrections tail varying.

## Applicable guardrails

- **The plan's "## Out of scope", no cap or rejection on feedback length, shape, count, or semantics.** This binds this step hardest, because a prompt assembler is exactly where truncating a long request or dropping rows past a limit feels responsible. Render every open row whole; the prompt-budget advisory below `plan_tool/shell.py:claude_invoke` stays the only pressure signal and never fails a run.
- **The plan's "## Out of scope", no automatic transition out of awaiting-review, and no judging whether feedback was honored.** The template asks the model for one transition and one response, and this step writes no state and compares no response to anything.
- **The plan's "## Out of scope", cross-artifact feedback propagation.** The active-feedback block is built from the predecessor of the stage being rendered, and from nothing else. An upstream artifact's feedback is never active guidance for a later stage and never fills `ArtifactEnvelope.predecessor`; its text is still visible inside the upstream artifact text, which the prompt carries whole.
- **The plan's "## Out of scope", no TTY walk, confirmation prompt, or new command.** Nothing added here reads stdin or a terminal.
- **The plan's "## Out of scope", no second store or hidden feedback state.** The prompt is built from the predecessor artifact's own bytes and rows; no cache, no sidecar, no `.plan-tool/` file.
- **The plan's "## Architecture", the shared revision wrapper and a stage stays data.** One template and one renderer serve every stage; `RoadmapStage` gains no field and the run loop gains no per-stage branch.
- **The plan's "## Architecture", the one-way dependency line.** `plan_tool/roadmap.py` may import from `plan_tool/roadmap_artifacts.py` and `plan_tool/roadmap_gates.py`; nothing here reverses that, and no gate logic is duplicated in the renderer.
- **The plan's "## Acceptance criteria", first-run behavior unchanged.** The no-predecessor path returns the authoring prompt untouched, which is what makes this true rather than merely intended.

## Deferred

- **Loading the predecessor off disk and filling `ArtifactEnvelope.predecessor`** — step 5. Until it lands, `run_roadmap` passes no predecessor and the revision path is exercised only by tests.
- **Writing the revision, including the lifecycle-preserving write and the `RevisionFeedbackDelivered` event step 3 minted** — step 6. Nothing here writes an artifact or emits a log event beyond the existing per-attempt `claude_call_start`.
- **The operator summary counting feedback awaiting review** — step 7, in `plan_tool/cli/roadmap_cmd.py`.
- **Documenting the review loop, the lifecycle, and the revision prompt's contract** — step 8, which reads whatever actually lands here rather than transcribing this file.
- **Measuring first-attempt hit rate, prompt bytes, advisory level, and retry counts on a real brief** — step 9. Canned replies prove the contract is satisfiable, not that a model usually satisfies it.
- **Extracting the two prompt-template reads into one shared helper** — declined here as a behavior-preserving refactor inside a feature step. Route it to `BACKLOG.md` or a reconcile pass.
- **Any change to `plan_tool/prompts/roadmap-domain.md` or `plan_tool/prompts/roadmap-constraints.md`** — not taken. Revision mode wraps them; the step's intent is that first-run authoring prompts stay as they are.
- **Trimming the wrapped authoring prompt in revision mode** (dropping its skeleton or its brief block to save bytes) — not taken. It forks the authoring contract per mode and gives the two paths different rules for the same artifact. Revisit only if step 9 shows the size is actually a problem.
- **Calibrating `MAX_STAGE_ATTEMPTS` for the larger revision prompt** — BACKLOG #215's separate decision, per the plan's Deferred list.
