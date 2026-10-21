> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Make plan_tool/detail.py the sole authority for the current run-grade detail marker, keeping the archive-then-overwrite of a prior detail file unchanged

## Summary

`plan_tool/detail.py` gains one small normalizing helper that runs at the single place a run-grade detail body is written to disk — the `output_path.write_text(...)` call at the end of `_author_step_detail` — and makes the first non-blank line after the body's H1 exactly the current marker step 3 renders (`render_detail_format_version_marker()` from `plan_tool/detail_artifacts.py`), dropping any marker-shaped line a model proposed in that slot first. The main authoring prompt (`plan_tool/prompts/detail.md`, the `## What to produce` block) and the retry suffix (`plan_tool/detail.py:_REPROMPT_SUFFIX`) both tell the model that the line after the H1 belongs to plan-tool and neither names a version number, so the model can never make a file refuse itself. `parse_detail_response`'s preamble skip is tightened so the accepted body starts with a real H1 rather than any `#`-prefixed line, which is what guarantees every accepted body has a slot to stamp. `_archive_existing_detail` and the archive-then-write order around it are not edited at all. `plan_tool/cli/authoring.py:cmd_detail` accepts the explicit `--recover-refused` signal only for a targeted forced recovery with the tail disabled: that serial route suppresses every pre-existing-detail block before it archives and replaces the target, while ordinary forced re-authoring, forced review regeneration, and merge retain their context. `DETAIL_FORMAT.md` describes the marker, its placement before `Summary`, and the refusal a reader gives an unsupported value. On green, every file `plan-tool detail` writes reads back cleanly through step 3's shared gate, and every existing marker-free detail file keeps parsing exactly as it does today.

## Table of Contents

- [Why](#why) — the writer half of the detail carrier, and why the writer, not the model, owns the value
- [Input](#input) — the step 3 contract and the checkpoint contract this step builds on
- [Files (creates vs edits)](#files-creates-vs-edits) — the twelve declared files and the edits in each
- [Implementation](#implementation) — the stamp helper, the one write site, the H1 rule, the prompt and suffix edits, the doc edits
- [Tests](#tests) — the cases this step adds, by class, and the existing cases that pin what must not change
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — the plan-level docs and seams this step follows
- [Applicable guardrails](#applicable-guardrails) — which plan fences bind this step
- [Deferred](#deferred) — what steps 5, 6, and 7 own, and the in-place edit paths this step leaves alone

## Why

Step 3 gives every semantic run-grade detail reader a gate that refuses an unsupported marker, but nothing writes a marker yet: every detail file this build authors today has no declaration, and the reader treats that as version 1 only because the plan's Architecture says absent means version 1 by an explicit default. That default is a legacy accommodation for files that predate the carrier, not the target state. The plan's step 4 intent is that every run-grade detail file this build authors carries its declaration, so the reader gate has something real to read the first time a version 2 ever ships.

The plan's Architecture also settles who owns the value: the writer, not the model. A detail body is model-authored prose, and the authoring prompt shows the model the exact response shape it must produce. If the prompt showed a literal `<!-- plan-tool:detail-format-version: 1 -->` line, a future model could just as easily propose `2` — and the reader gate would then refuse the file the writer just wrote. So the prompt reserves the slot without naming a version, and `detail.py` overwrites whatever landed there with the build's own current marker. That is what makes `detail.py` the sole authority: the marker's spelling and its recognizer come from step 3's leaf, but the decision of what value goes on disk is made once, in the writer, after the model has answered.

The only write of a *current run-grade* detail body in the codebase is the `output_path.write_text(body + "\n", ...)` call in `plan_tool/detail.py:_author_step_detail`. Both the serial loop and the concurrent worker path reach it, and the merge re-author reaches it through `generate_detail`, so stamping there covers every authored file with one edit. `plan_tool/sweep.py:_archive_plan_details` and `plan_tool/create.py:_copy_details_bundle_for_archive` also write Markdown, but only while moving an archived plan bundle into its historical snapshot: each prepends a breadcrumb before the H1, so that copy intentionally leaves the live run-grade carrier, support window, and upgrade obligation with its archived plan. The archive-then-overwrite that runs immediately before the current-body write (`_archive_existing_detail`) is what the step title says to leave alone: it is also the plan's named recovery route for a refused file, and it works only because forced recovery neither reads the target nor supplies any pre-existing sibling body to prompt assembly.

## Input

- **Step 3's detail-carrier contract (`plan_tool/detail_artifacts.py`).** Step 3 lands the marker's spelling, the renderer for the exact line a writer stamps (`render_detail_format_version_marker()`), the reader gate (`require_supported_detail_format_version(text, *, path=None)`), the constants `DETAIL_FORMAT_VERSION` / `SUPPORTED_DETAIL_FORMAT_VERSIONS`, and `DetailFormatError`. The slot rule this step must match is the plan's: leading blank lines are ignored, then the document's first non-blank line must be an unindented H1 matching the shared carrier recognizer, and the carrier is the first non-blank line after it; a non-blank preamble, an indented H1, or no H1 has no slot. Read the landed names off the module when implementing; the names in step 3's detail file are its proposal, and the landed name wins on any disagreement.
- **Step 3's named carrier locator and marker recognizer.** The `locate_detail_format_carrier` helper in `plan_tool/detail_artifacts.py` is the one H1-and-slot decision; the leaf's marker recognizer matches the `plan-tool:detail-format-version:` prefix with any payload, well-formed or not. This step imports both landed helpers rather than copying either regex or slot scan into `plan_tool/detail.py` (see the constraint in [Implementation](#implementation)).
- **The checkpoint contract (`plan_tool/checkpoint.py:Checkpoint`).** `_author_step_detail` saves a checkpoint after a successful parse and before the write, with `payload` set to the parsed body (or the raw response when a deferral envelope is required). `tests/test_detail.py::TestGenerateDetailResume` pins that the payload equals `parse_detail_response(...)` of the response. This step must not change what the checkpoint holds; a resumed payload goes through the same stamp at write time.
- **The two response parsers in `plan_tool/detail.py`.** `parse_detail_response` accepts a body and `parse_structured_detail_response` splits the trailing `<!-- plan-tool-detail-deferrals ... -->` envelope off first. The format-version marker's text (`plan-tool:detail-format-version:`) does not match `_DETAIL_DEFERRALS_RE` or the literal `<!-- plan-tool-detail-deferrals` membership check, and an HTML comment line does not match `_H2_HEADING_RE`, so neither parser needs to know about the marker. Verify both facts with the round-trip tests below rather than by reading.
- **The direct authoring boundary (`plan_tool/cli/authoring.py:cmd_detail`).** It is the only caller that receives the operator's `--recover-refused` request. It requires that opt-in flag alongside `--step N`, `--force`, and `--no-completeness`, then sets `recovery_only=True` only for that exact direct route before calling `generate_detail`; the `_dispatch_detail` closure in `plan_tool/cli/review_actions.py:_build_review_action_fn` and `merge_steps` never set it, even when they pass `force=True`.

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**

- `plan_tool/detail.py` — add the stamp helper; call it once in `_author_step_detail` right before the existing `output_path.write_text(...)`; tighten `parse_detail_response`'s first-heading rule to require a real H1; reword item 4 of `_REPROMPT_SUFFIX` to reserve the marker slot. Zero-line diff to `_archive_existing_detail`, `_archive_orphan_details`, the `try:` block that archives then writes, and `parse_jira_detail_response`.
- `plan_tool/sweep.py`, `plan_tool/create.py` — **no code change.** Their archive writers keep prepending the existing breadcrumb before the H1; this step adds the carrier-exemption regression tests that hold that snapshot boundary.
- `plan_tool/cli/authoring.py` — add `--recover-refused`; require its exact `--step N --force --no-completeness` companion shape before any prompt or mutation, and derive `recovery_only=True` only there. Do not change any other authoring flags or review-action dispatch.
- `plan_tool/prompts/detail.md` — in the `## What to produce` block, say the line after the H1 is plan-tool's and the model must not write a format-version marker; no version number anywhere in the template.
- `DETAIL_FORMAT.md` — the source-of-truth banner, `## What writes detail`, `## Format`, `## Section schema`, `### Field semantics`, a new marker subsection, `## Validation rules`, `## Parsing helpers (for consumers)`, and the abridged example each gain the marker; the jira-grade section gains one sentence saying it carries no marker.
- `docs/cli/detail.md` — add the documented `--recover-refused` option, its required targeted-force/no-tail companion shape, and the fresh-audit follow-up after the last repaired target.
- `tests/test_detail.py` — the new cases enumerated in [Tests](#tests).
- `tests/test_sweep.py`, `tests/test_create.py` — archive snapshots each remain outside the run-grade carrier contract.
- `tests/cli/test_authoring_cmds.py` — assert the direct CLI boundary supplies the recovery signal only for the exact `--step N --force --recover-refused --no-completeness` shape and rejects every incomplete combination before mutation.
- `tests/cli/test_review_actions.py` — retain the forced-review negative control that supplies no recovery signal.

## Implementation

### 1. The stamp helper in `plan_tool/detail.py`

Add one module-level helper, near `_archive_existing_detail` or near the parsers — one way is `stamp_detail_format_version_marker(body: str) -> str`. The name is the implementer's; the properties are not:

- **It takes a parsed body and returns a body whose first non-blank line after the H1 is exactly `render_detail_format_version_marker()`** from `plan_tool/detail_artifacts.py`. Import the renderer; do not spell the marker string in `detail.py`. The step's `depends_on_notes` for step 3 says why: the writer must stamp exactly what the reader accepts, not restate the recipe.
- **It replaces, never appends beside, a model-proposed marker in the slot.** If the first non-blank line after the H1 is marker-shaped — the `plan-tool:detail-format-version:` prefix with *any* payload, including `1`, `999`, `banana`, or empty — that line is dropped and the current marker takes its place. Recommended: drop every consecutive marker-shaped line at the head of the slot, so two stacked proposals also collapse to one. The recognizer must be step 3's, imported from the leaf under whatever name it landed (the same way this module already imports `_SLUG_STOPWORDS` and `_MAX_SLUG_LEN` from that leaf); writing a second marker regex in `detail.py` is the one thing this helper must not do.
- **It touches nothing outside the slot.** A marker-shaped line anywhere else — inside `## Implementation`, inside a fenced code block, or as prose between the marker and `## Summary` — is ordinary prose under the plan's Architecture and stays byte-for-byte as the model wrote it. Do not scan the body for markers; locate the slot and stop.
- **It is idempotent.** Stamping an already-stamped body returns it unchanged. This is what lets the helper run on a resumed checkpoint payload, a merge re-author, or a body that already carried the current marker without any caller having to ask "was this stamped yet?".
- **It requires an H1 and may assume one.** Section 3 below makes the parser guarantee the body's first line is a real H1 before the helper ever sees it. The helper may treat a body whose first line is not an H1 as a programming error (an assertion or a raised `DetailError`), because that shape can no longer reach the write. It must not synthesize an H1 from the step title — the plan's step 6 upgrader refuses the same shape for the same reason: inventing content.
- **Layout is the implementer's choice; the property is not.** One blank line between the H1 and the marker and one between the marker and the first H2 matches the rest of the file's style and is the recommended shape. Tests pin only "first non-blank line after the H1", not the blank-line count.

### 2. Where it runs: the one write site in `_author_step_detail`

- **Call the helper immediately before `output_path.write_text(body + "\n", ...)`**, assigning back to `body`, so the returned `_StepAuthoringOutcome.body` is the stamped text and matches what is on disk. Both the serial `generate_detail` loop and the concurrent worker dispatch reach this one function, and `merge` re-authors through `generate_detail(force=True, ...)`, so one call covers every authored file.
- **After the checkpoint save, not before.** `save_checkpoint` runs right after a successful parse; its `payload` stays the parsed body (or the raw envelope response). A resumed step takes the `cached is not None` branch, re-parses the payload to `body`, and reaches the same stamp at the write. Stamping earlier would change the checkpoint contract for no benefit and would turn `TestGenerateDetailResume`'s payload assertion red.
- **Inside the existing archive-then-write order, after the archive.** The `try:` block does `mkdir` → `_archive_existing_detail(output_path)` → `write_text`. The stamp is a pure string operation on `body`; run it before entering that block (so a stamp failure cannot leave a prior file archived with nothing written in its place) and leave the block's three lines exactly as they are.
- **`dry_run` and the parse-failure return are untouched.** Neither reaches the write, so neither stamps.

### 3. The H1 rule: tighten `parse_detail_response`'s preamble skip

`parse_detail_response` finds the body's start as the first line whose first non-whitespace character is `#`. That accepts a response that begins with `## Summary` and never has an H1 — and, unless tightened further, could accept an indented H1 that the shared carrier locator rejects. Both shapes have no carrier slot, so the writer could not stamp them. The plan's Scope guardrails already describe `parse_detail_response` as "the separate authoring-time H1 validator", and both `_REPROMPT_SUFFIX` item 1 and `DETAIL_FORMAT.md` validation rule 1 already say the first character is "the H1 title", so this is the code catching up to the documented contract.

- **Required:** keep the preamble skip only for prose preceding an unindented heading, then require that accepted first heading to make `locate_detail_format_carrier` return a slot — exactly one column-0 `#` followed by whitespace and content — and return `None` otherwise. Do not `lstrip()` the candidate before this check. A rejected response consumes an attempt and gets `_REPROMPT_SUFFIX` exactly as a missing-sections rejection does today; the existing `skipped_reason` text ("missing required H2 sections, or no `#` heading") already covers it well enough, and may be reworded to say "no H1".
- **One recognizer, not a lookalike.** Import `locate_detail_format_carrier` and the marker recognizer from step 3; do not copy either regex or slot scan into `plan_tool/detail.py`. A response the parser accepts must be exactly a body the stamp helper and the reader call carrier-bearing.
- **Rejected alternative: write an H1-less body without a marker.** It reads as absent (version 1) under step 3's gate, so nothing would fail — which is exactly why it is wrong: it silently breaks the step's intent that every authored file carries its declaration.
- **Rejected alternative: refuse in the stamp helper at write time.** By then the checkpoint is saved, so a resume would hit the same refusal with no retry available. Rejecting at parse time keeps the failure inside the existing two-attempt loop.
- **Do not touch `parse_jira_detail_response`.** Its docstring records that its envelope cleanup is a deliberate copy, that consolidating the two is reconcile's job, and jira-grade authoring is disabled and out of this plan's scope.

### 4. The archive-then-overwrite stays unchanged, and forced recovery reads no existing bundle detail

The step title's second half is a zero-diff requirement, and it is also what makes the plan's recovery route work:

- `_archive_existing_detail`, `_archive_orphan_details`, and the `try:` block around the write are not edited. `tests/test_detail.py::TestGenerateDetailOrphanSweep::test_canonical_overwrite_archives_prior_content` and `TestGenerateDetailReplacePrompt::test_accept_archives_prior_and_writes_new` pin the archive order and the archived bytes today and must stay green untouched.
- A direct `plan-tool detail <slug> --step N --force --recover-refused --commit --no-completeness` is the one explicit exception to semantic reuse: it must not interpret **any** pre-existing detail body in the bundle, not only the target. `plan_tool/cli/authoring.py:cmd_detail` rejects `--recover-refused` unless it has that targeted forced/no-tail companion shape, then sets `recovery_only=True` for this exact serial route and no other caller. In recovery mode suppress every prompt input that reads an existing detail: `_format_sibling_details_block`, `_format_already_implemented_block`, and `collect_step_grounding_findings`; each receives an empty/no-op input before it can reach a gate. `--no-completeness` skips the automatic whole-bundle tail, which otherwise re-reads refused siblings; after every refused target is replaced, an operator runs a fresh completeness audit. Leave their normal semantic gate intact outside recovery, and leave `${prior_body_block}` available only to merge's explicit `prior_body` argument. Do not key this on `force` or `--no-completeness`: `merge_steps` and the `_dispatch_detail` closure in `plan_tool/cli/review_actions.py:_build_review_action_fn` also pass `force=True`, while ordinary operators may legitimately skip the tail, and all retain their prior-body, sibling, and grounding context. This is a narrow direct-recovery suppression, not a fallback for ordinary authoring, review regeneration, reconcile, quality, or merge. `--jobs` has no recovery meaning because `--step N` is serial by construction.
- The written replacement carries the current marker, so the recovery route produces a file the reader accepts.

### 5. `plan_tool/prompts/detail.md`: reserve the slot without declaring a version

In the `## What to produce` block, where the fenced "Required structure" shows `# Step ${step_id} — <one-line title>` followed by `## Summary`:

- **Add prose, outside the fence, saying the line after the H1 belongs to plan-tool**: plan-tool writes its own `plan-tool:detail-format-version` marker there after the response is parsed; the model must not write one, and one it writes is replaced. Name the marker's prefix so the model knows what not to produce; do not show a complete marker with a number.
- **Keep the fenced structure marker-free.** Showing a comment line inside the fence invites the model to echo it. The blank line between the H1 and `## Summary` is the reserved position; the writer fills it.
- **Do not add a `${...}` placeholder** — nothing in the variable map changes — and write no bare `$` (the template renders through `string.Template.safe_substitute`).
- `tests/test_detail.py::TestRenderDetailPromptABMode.REQUIRED_HEADINGS` asserts the seven H2 headings still appear in the rendered prompt; keep that green.

### 6. `_REPROMPT_SUFFIX`: same reservation on retry

Item 4 currently says `## Summary` belongs immediately after the H1. Reword it so the retry states the same H1 → reserved marker line → `## Summary` sequence the plan's Architecture names: the model leaves the line after the H1 to plan-tool, which stamps its format-version marker there, and `## Summary` is the first H2. No version number. Item 1 ("the very first character must be `#`, the H1 title") already matches the tightened parser and stays. `_JIRA_REPROMPT_SUFFIX` is out of scope and untouched.

### 7. `DETAIL_FORMAT.md`: describe the marker and its refusal

This file is reference reading, not runtime input; keep its family conventions (source-of-truth banner naming the enforcing code, and "if the doc and the code disagree, the code wins"). Read the landed names off `plan_tool/detail_artifacts.py` when writing these:

- **Banner.** Add the writer (`plan_tool/detail.py`'s stamp helper) and the reader gate (`plan_tool/detail_artifacts.py:require_supported_detail_format_version`) to the run-grade enforcing-code list.
- **`## What writes detail`.** One sentence: the writer stamps the current format-version marker after parsing the response, replacing any the model proposed.
- **`## Format`.** Keep "pure markdown — no YAML frontmatter"; add that the body carries exactly one machine-read line, the format-version marker, and nothing else is machine metadata.
- **`## Section schema`.** Insert the marker line between the H1 and `## Summary` in the fenced schema, annotated as required, written by `plan-tool detail`, first non-blank line after the H1.
- **`### Field semantics`.** Change "`Summary` belongs immediately after the H1" to "immediately after the marker line" (the H1, then the marker, then `Summary`).
- **New subsection (one way: `### Format version marker`).** State: the exact spelling with `N`; the slot rule (first non-blank line after the unindented H1; `## Summary` is the next H2); a marker-shaped line anywhere else is ordinary prose; a body with no valid carrier H1 has no marker slot and resolves to legacy version 1 through the support-window check; the writer owns the value and replaces a proposed one; a reader meeting an unsupported or malformed value refuses with `DetailFormatError` naming the declared value and the supported set, before using the body; reading never upgrades; and the direct recovery route is `plan-tool detail <slug> --step N --force --recover-refused --commit --no-completeness`, which archives the refused or carrier-less target, suppresses every pre-existing-detail prompt block, and skips the whole-bundle tail until every refused target is replaced. Cite the constants and the gate by name.
- **`## Validation rules`.** Add the H1 requirement to rule 1 (a `##`-first response is rejected, not stripped), and add a rule that the parsed body is stamped at write time after these rules pass.
- **`## Parsing helpers (for consumers)`.** Add `require_supported_detail_format_version` with its raise-or-return contract, and say consumers call it on the full text right after reading, before any truncation.
- **`## Example (abridged)`.** Add the marker line after the H1.
- **`## Jira grade`.** One sentence: jira-grade files carry no format-version marker; the marker is run-grade only.

### 8. Constraints and gotchas

- **`plan_tool/detail.py` must import the marker string and the recognizer from `plan_tool/detail_artifacts.py`; it must not define either.** Two spellings of the marker is the drift this plan exists to prevent.
- **The stamp runs only on a freshly parsed body about to be written.** It must not be applied to an existing on-disk file by any reader path — that would be an upgrade at read time, which the plan's Scope guardrails forbid. Step 6 owns the explicit absent-to-1 upgrader for existing files.
- **No version number in any prompt text.** A grep of `plan_tool/prompts/detail.md` and of `_REPROMPT_SUFFIX` for `plan-tool:detail-format-version:` followed by a digit must return nothing.
- **`_DETAIL_DEFERRALS_RE` and `_H2_HEADING_RE` need no change.** The marker's text does not match the deferrals marker, and an HTML comment is not a heading. `parse_detail_file_sections` puts the marker in the pre-`Summary` region no consumer reads as a section.
- **Do not add a warning, finding, or advisory** when a model proposes a marker. Replacing it silently is the contract.

## Tests

Name each case for the property it pins, so a later reader can tell a deliberate rule from a regression. All cases live in `tests/test_detail.py`; import the marker renderer and reader gate from `plan_tool.detail_artifacts` for the round-trip cases.

### Tests for this step

New class `TestDetailFormatVersionStamp` (unit, no invoker, over the helper directly):

- `test_stamp_makes_current_marker_the_first_nonblank_line_after_h1` — a marker-free body comes back with `render_detail_format_version_marker()` as the first non-blank line after the H1 and `## Summary` still the first H2.
- `test_stamp_replaces_a_model_proposed_marker_rather_than_adding_beside_it` (parametrized over proposed payloads `1`, `999`, `banana`, empty) — the result carries the current marker once in the slot and none of the proposed payloads anywhere; pins the "a model cannot cause a self-refusing file" rule.
- `test_stamp_collapses_stacked_proposed_markers_to_one` — two consecutive marker-shaped lines in the slot become one current marker.
- `test_stamp_leaves_marker_shaped_prose_outside_the_slot_untouched` — a marker-shaped line inside `## Implementation` and one inside a fenced block survive byte-for-byte while the slot still gets exactly one current marker.
- `test_stamp_is_idempotent` — stamping a stamped body returns the same string.
- `test_stamp_writes_exactly_the_string_the_reader_renders` — the inserted line equals `render_detail_format_version_marker()`; pins that `detail.py` restates nothing.
- `test_stamped_body_passes_the_shared_reader_gate` — `require_supported_detail_format_version` raises nothing on the stamped body; pins the writer/reader round trip.
- `test_stamped_body_still_parses_into_all_seven_sections` — `parse_detail_file_sections` on the stamped body returns every required token with the `summary` body unchanged; pins that the marker sits outside every section.

`TestParseDetailResponse` additions:

- `test_response_whose_first_heading_is_an_h2_has_no_h1_and_is_rejected` — a body starting at `## Summary` with all seven sections returns `None`; pins the tightened rule.
- `test_response_with_an_indented_h1_is_rejected_before_checkpoint` — a body whose first apparent heading is `  # Step …` returns `None`, so no accepted response can later miss the column-0 carrier slot.
- `test_preamble_before_a_real_h1_is_still_stripped` — the existing preamble-skip leniency survives the tightening.
- `test_stamped_body_reparses_through_parse_detail_response_and_the_envelope_parser` — a stamped body, with and without a trailing deferrals envelope, parses to the same body; pins that neither parser treats the marker as a heading or as the envelope.
- `test_reprompt_suffix_reserves_the_marker_slot_without_declaring_a_version` — `_REPROMPT_SUFFIX` names the marker prefix and contains no `plan-tool:detail-format-version:` followed by a digit.

`TestRenderDetailPrompt` addition:

- `test_detail_prompt_reserves_the_marker_slot_without_declaring_a_version` — the rendered prompt names the marker prefix and contains no versioned marker; a `$` check over the rendered text finds no unresolved `${`.

`TestGenerateDetailIdempotency` / `TestGenerateDetailOrphanSweep` additions (integration, fake invoker):

- `test_authored_file_carries_the_current_marker_after_the_h1` — `generate_detail` with `_GOOD_BODY` writes a file whose first non-blank line after the H1 is the current marker, and `results[0].output_path.read_text()` passes the reader gate.
- `test_model_proposed_marker_never_reaches_disk` — an invoker returning `_GOOD_BODY` with `<!-- plan-tool:detail-format-version: 999 -->` in the slot writes a file carrying `1`, not `999`.
- `test_direct_recovery_archives_a_refused_file_without_reading_any_bundle_detail` — the target and at least two sibling canonical files declare `999` in their slots; direct `detail --step N --force --recover-refused --no-completeness` for the target raises no `DetailFormatError`, archives the target byte-for-byte, leaves sibling bytes untouched, renders no sibling, already-implemented, or deterministic-grounding excerpt, skips the automatic completeness tail, and writes a stamped target. Exercise only the serial path: `--step N` cannot reach the concurrent assembler. Ordinary `--force` and `--force --no-completeness` are negative controls that retain their normal context. Merge with `force=True` remains a negative control too: it preserves explicit `prior_body` and ordinary sibling/grounding context.
- `test_direct_recovery_reauthors_a_carrierless_detail_without_reading_it` — a target with no valid H1 follows the same `--force --recover-refused --no-completeness` route, is archived byte-for-byte, and is replaced with a stamped current body; pins the declared path to current for the carrier-less legacy shape.
- `test_concurrent_worker_path_stamps_the_same_way` — the `--jobs` dispatch writes a stamped file too (one case; the write site is shared, so this is the seam check, not a second roster).

`TestGenerateDetailResume` addition:

- `test_resumed_checkpoint_body_is_stamped_at_write` — a seeded checkpoint whose payload is a marker-free parsed body resumes and writes a stamped file; the existing payload-equality case in this class stays green and pins that the checkpoint itself is not stamped.

Existing cases that must stay green untouched: `test_canonical_overwrite_archives_prior_content`, `test_accept_archives_prior_and_writes_new`, `test_force_overwrites_existing_detail`, `TestDetailStyleOutput::test_archived_previous_detail_plain`, and `TestRenderDetailPromptABMode`'s seven-heading assertion. A red among them means the archive order or the checkpoint contract changed, which this step forbids.

`tests/test_sweep.py` and `tests/test_create.py` additions:

- `test_archived_detail_snapshot_has_no_run_grade_carrier` — exercise each archive writer with an H1-bearing run-grade body, then pass the archived bytes to `detail_artifacts.locate_detail_format_carrier` and assert it reports no valid carrier because the existing breadcrumb remains before the H1. The tests pin this archive-only exemption without changing either writer.

`tests/cli/test_authoring_cmds.py` addition:

- `test_recover_refused_flag_is_targeted_and_opt_in` — only direct `--step N --force --recover-refused --no-completeness` passes `recovery_only=True` and disables the tail. Each missing companion and each ordinary force/no-tail combination fails or retains normal context before mutation. `docs/cli/detail.md` renders the same required shape. `tests/cli/test_review_actions.py` keeps a negative control that a forced review regeneration passes no recovery signal.

Green-before-done gate: every case above (approx. 19 new) must be green, and the full suite (`uv run pytest tests/ -q -n auto`) must be green, before this step is finished. Roughly 16 other test files drive `generate_detail`; none found asserts exact written bytes of an authored body, but a red there is the expected signal of one that does and is fixed by comparing through the stamp, not by weakening the stamp.

## Acceptance criteria

- Every file written by `_author_step_detail` has `render_detail_format_version_marker()` as the first non-blank line after its H1, and `## Summary` as its first H2.
- A response carrying any marker-shaped line in the slot — well-formed or malformed, any value — produces a written file carrying only the current marker there.
- A marker-shaped line outside the slot is preserved byte-for-byte in the written file.
- `require_supported_detail_format_version(written_text)` raises nothing for every file `plan-tool detail` writes.
- `parse_detail_response` returns `None` for a body whose first heading is not an unindented H1 matching step 3's carrier recognizer; prose preamble before a real H1 is still stripped.
- The checkpoint payload saved by `_author_step_detail` is unchanged by this step; a resumed checkpoint still produces a stamped file.
- `_archive_existing_detail`, `_archive_orphan_details`, and the archive-then-write block in `_author_step_detail` have a zero-line diff.
- Only direct `detail --step N --force --recover-refused --no-completeness` passes `recovery_only=True`; its serial prompt assembly archives and replaces one refused or carrier-less target without reading its sibling, already-implemented, or deterministic-grounding bodies or invoking the whole-bundle tail. Ordinary forced re-authoring, merge, and forced review regeneration remain outside that mode despite their own `force=True` calls and retain their normal context.
- `plan_tool/prompts/detail.md` and `_REPROMPT_SUFFIX` each name the `plan-tool:detail-format-version` prefix as plan-tool's to write, and neither contains that prefix followed by a digit; the template contains no bare `$`.
- `DETAIL_FORMAT.md` and `docs/cli/detail.md` name the marker's spelling, slot, writer ownership, absent-means-1, malformed-refuses, the reader's `DetailFormatError` refusal with the declared and supported values, and the explicit forced-regeneration recovery route that reads no existing bundle detail; the format document's schema block and example show the marker between the H1 and `## Summary`.
- Every existing marker-free detail file in this repo still parses identically; no reader emits a warning or finding about a supported or absent version.
- `plan_tool/sweep.py` and `plan_tool/create.py` each preserve their breadcrumb before the H1; tests prove their archived snapshots have no valid run-grade carrier and therefore stay outside the live support window.
- `parse_jira_detail_response`, `_JIRA_REPROMPT_SUFFIX`, and every jira-grade path are unchanged.

## References

- `DETAIL_FORMAT.md` § Format, § Section schema, § Validation rules — the pure-markdown contract and the H1-first rule this step's marker slot lives inside.
- `docs/implementation-plans/plan-details/authored-artifact-format-version/03-fixed-run-grade-detail-body-marker.md` — step 3's marker spelling, renderer, recognizer, and reader gate; the names this step imports.
- `plan_tool/roadmap_seed_state.py:render_seed_state_marker` and its `_MARKER_RE` — the in-repo precedent for a writer-rendered, reader-parsed marker inside a markdown body; a different subsystem, not imported.
- `plan_tool/checkpoint.py:Checkpoint` — the payload contract the stamp must not change.
- `DATA_CONTRACT.md` § "Version-evolution policy" — writers emit current only; the reason the writer, not the model, picks the value.

## Applicable guardrails

- **The plan's "## Architecture", the writer-owns-the-marker-value contract.** This step's writer replaces any proposed marker in the fixed slot with the build's current one and leaves marker-shaped prose elsewhere alone; the prompt and the retry suffix reserve the slot and may not name a version.
- **The plan's "## Scope guardrails", the not-allowed list.** The stamp is a write-time act on a freshly parsed body only; it must not be applied to an existing file by any reader path, must not emit a warning or advisory about a proposed or supported version, and must not check whether the body's content matches the version it declares.
- **The plan's "## Out of scope", detail-file carve-outs.** No YAML frontmatter, no grade in the marker, no version other than the current one, no jira-grade changes, and no preservation check for in-place edits by `apply_finding` or reconcile — those remain the accepted residual the plan names.
- **The plan's "## Architecture", the forced-regeneration recovery route.** The archive-then-overwrite must stay unchanged, and targeted `--recover-refused` recovery must suppress target and sibling body reads and skip the tail, so `detail --step N --force --recover-refused --commit --no-completeness` remains the one way to replace a refused or carrier-less file even when the bundle has no supported sibling.

## Deferred

- The explicit absent-to-1 upgrader over a raw existing detail body, and its coverage test — step 6, which owns the only path that adds a marker to a file already on disk; this step's stamp never runs on an existing file.
- The version-only `data_contract.py` record and `DATA_CONTRACT.md`'s class rules for the detail constants — step 5.
- `CLAUDE.md`'s format-doc bullets naming the marker, and removing `BACKLOG.md` #356 — step 7.
- Back-stamping the detail files that already exist in this repo, including this plan's own steps 1–3 files — they read as version 1 under step 3's gate and gain a marker only when re-authored or explicitly upgraded (step 6).
- In-place edits by `launcher.py:apply_finding` or a `detail --reconcile` walk that drop a stamped marker — the plan's accepted residual; it persists until a deliberate authoring write re-stamps it.
- `bench.py`'s temp-dir write of a drafted body for `check_files_coherence` — not a durable artifact write; it stays unstamped and reads as absent.
- Consolidating `parse_jira_detail_response`'s copied envelope cleanup with `parse_detail_response`, or tightening its H1 rule — its docstring routes that to reconcile, and jira-grade authoring is disabled and out of scope.
- Any shared helper between this step's stamp and step 6's upgrader — the plan's acceptance says fresh writers never invoke the upgrader; if step 6 finds the slot-insertion bodies identical, step 6 owns the duplication guard's narrowly named allowlist entry and its stated reason, not a merge.
