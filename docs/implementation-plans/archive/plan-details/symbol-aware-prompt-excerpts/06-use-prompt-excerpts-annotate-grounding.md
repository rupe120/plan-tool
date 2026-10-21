> **Auto-archived**: this plan was swept on 2026-07-07 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Use Prompt Excerpts for Annotate Grounding

## Summary

This step updates `plan_tool/annotate.py` so the annotate prompt's `## Code grounding` blocks use the prompt excerpt helper from step 1 instead of always showing the first bytes of each resolved file. The production change is centered on `plan_tool/annotate.py:_ground_source`, with focused prompt-capture coverage in `tests/test_annotate.py`. The key design decision is to keep annotate's path extraction, umbrella-root resolution, binary/unreadable skips, detail-file exclusion, and low-grounding accounting in `plan_tool/annotate.py`, while delegating only readable source text selection to `plan_tool/prompt_excerpt.py`. On green, annotate grounding can surface a relevant function, class, or constant past a small byte cap without changing `PlanAnnotation` shape or grounding counts.

## Table of Contents

- [Summary](#summary) — Quick review of the annotate grounding change and expected result.
- [Why](#why) — Why annotate needs better source previews.
- [Files creates vs edits](#files-creates-vs-edits) — The scoped production and test files.
- [Implementation](#implementation) — Required behavior, likely call sites, and constraints to preserve.
- [Tests](#tests) — Focused tests to add in `tests/test_annotate.py`.
- [Acceptance criteria](#acceptance-criteria) — Observable checks for completion.
- [References](#references) — Relevant stdlib docs behind the excerpt and symbol-selection behavior.
- [Deferred](#deferred) — Related prompt and helper work left outside this step.

## Why

`plan_tool/annotate.py:_ground_source` currently reads every resolved cited file and passes the body through `plan_tool/annotate.py:_bound_for_block`, which keeps only the leading slice. That can hide the symbol the plan or notes ask annotate to judge, so Claude sees imports and setup while the implemented code sits past `_MAX_GROUND_FILE_BYTES`. Step 1 supplies the shared source excerpt helper for this problem; this step applies it only to annotate's readable code grounding while preserving the annotate-specific contracts that make low-grounding and skip reports reliable.

## Files (creates vs edits)

- **New files:**
  - None. `plan_tool/prompt_excerpt.py` is owned by step 1 and consumed here after that dependency has landed.

- **Existing files (edits only):**
  - `plan_tool/annotate.py` — Use the step 1 prompt excerpt helper for readable files in `_ground_source`, and derive a conservative candidate-symbol set from the annotate input before rendering grounded file bodies.
  - `tests/test_annotate.py` — Add prompt-capture tests proving annotate grounding includes relevant symbols past a small byte cap while existing skip, exclusion, and low-grounding contracts stay unchanged.

## Implementation

- **Foundational logic:** annotate code-grounding excerpt selection.

- **Use `_ground_source` as the integration point.**
  - Keep `plan_tool/annotate.py:classify_plan_implementation` orchestration the same: read source text with `read_existing_description`, load specs with `_load_step_specs`, exclude `_resolved_detail_paths`, call `_ground_source`, render with `render_annotate_prompt`, then parse with `_parse_annotation_response`.
  - In `plan_tool/annotate.py:_ground_source`, replace only the successful-read `_bound_for_block(body, max_file_bytes)` path for grounded code files.
  - Keep `plan_tool/annotate.py:_bound_for_block` available for `_load_step_specs`. Step specs are the thing to judge against, not implementation evidence, and this step is about the `## Code grounding` block.

- **Delegate text selection, not filesystem behavior.**
  - Keep `extract_file_path_candidates(source_text)`, `find_umbrella_root(...)`, duplicate detection, `exclude`, `resolved.is_file()`, `_read_grounding_text`, and all `skip_reasons` strings in `plan_tool/annotate.py`.
  - Call the helper from `plan_tool/prompt_excerpt.py` only after `_read_grounding_text` returns text.
  - Pass the existing `max_file_bytes` budget through. Do not introduce a second annotate code-grounding cap.

- **Use conservative candidate symbols.**
  - Annotate does not have a one-step owner for each cited file, so do not force review/detail/Jira's per-step ownership model onto this path.
  - For plan-tool plan input, one reasonable approach is to parse once with `_try_parse_plan(source_text)` and gather candidates from each step title using `plan_tool/review.py:_derive_symbols`, plus any useful detail-title context already available from the parsed plan. Use a body-local import if that keeps imports lighter.
  - For rough notes or non-plan input, derive candidates from compact text surfaces such as markdown headings and nearby prose rather than from file paths alone. Reuse `plan_tool/review.py:_derive_symbols` for token filtering instead of adding a second stopword/tokenizer rule in `plan_tool/annotate.py`.
  - Bound and de-duplicate the final candidate list before passing it to the helper. A broad annotate-level list is acceptable; an unbounded list made from the whole source body is not.

- **Preserve prompt block shape.**
  - Keep `plan_tool/annotate.py:_format_grounded_block` headers as `### \`path\`` and keep fenced code blocks around each grounded body.
  - Keep `GroundedSource.files` as `(Path, str)` pairs and `PlanAnnotation.grounded_files` as the resolved `Path` tuple.
  - Keep low-grounding behavior in `_has_incomplete_grounding` and `_apply_grounding_floor` based on counts, not on whether the helper found a symbol.

- **Keep helper ownership with step 1.**
  - Do not edit `plan_tool/prompt_excerpt.py` in this step. If step 1's public helper cannot accept a repo-relative path string, full file text, candidate symbols, and a byte budget, reconcile that upstream instead of expanding this step beyond `plan_tool/annotate.py` and `tests/test_annotate.py`.
  - Do not reimplement AST parsing, symbol windows, fallback slicing, or truncation-marker rules in `plan_tool/annotate.py`.

- **Respect annotate-specific prompt wording.**
  - `plan_tool/prompts/annotate.md` is not in this step's file list. Keep this step scoped to the rendered grounded body text.
  - Preserve the step 1 fallback metadata vocabulary when embedding helper output: `excerpt_kind`, `fallback_reason`, `truncated`, the visible "fallback preview" cue, and the literal `_(truncated)_` marker. Keep annotate output compatible with the current prompt's "marked truncated" low-confidence instruction, and do not silently remove truncation cues from grounded blocks.

## Tests

- `test_grounding_prompt_uses_symbol_excerpt_for_plan_step_title` — A plan step title names a function defined past a tiny `max_file_bytes` cap in a cited file, and the captured annotate prompt includes that function in `## Code grounding`.
- `test_grounding_prompt_uses_symbol_excerpt_for_rough_notes_heading` — A non-plan notes file names a symbol in a heading or nearby prose, cites a file where that symbol appears past the cap, and the captured prompt includes the symbol.
- `test_grounding_excerpt_preserves_skip_counts_and_resolved_paths` — A mix of resolved, missing, duplicate, and excluded detail-file candidates keeps the existing `grounding_candidate_count`, `grounding_skipped_count`, `grounding_skip_reasons`, and `grounded_files` behavior while readable files use excerpts.
- `test_grounding_excerpt_fallback_keeps_truncation_signal` — When no candidate symbol matches, the grounded block remains bounded and still carries a truncation/fallback cue that supports annotate's low-confidence instruction.
- Existing `test_prompt_includes_source_and_grounded_block` — Continues to prove `render_annotate_prompt` receives the original source and grounded code block.
- Existing `test_step_detail_files_excluded_from_grounding` — Continues to prove `detail:` specs are not treated as implementation evidence.
- Existing low-grounding tests in `tests/test_annotate.py` — Continue to prove excerpt selection does not change confidence demotion rules.

### Test-creation order (feature step)

This is a feature step. Add the prompt-capture tests for symbol-past-cap behavior alongside the implementation in `tests/test_annotate.py`, then run the existing annotate grounding and prompt-rendering tests as regression coverage. Every new test must be green before this step is considered finished.

## Acceptance Criteria

- `plan_tool/annotate.py:_ground_source` uses the step 1 prompt excerpt helper for readable grounded code files.
- `plan_tool/annotate.py:_load_step_specs` still bounds step spec text without treating specs as implementation grounding.
- A cited Python file with a matching function, class, or constant past a small byte cap appears in the captured annotate prompt.
- Missing, duplicate, binary, unreadable, and excluded `detail:` candidate handling keeps the existing skip reason strings and counts.
- `PlanAnnotation.grounded_files`, `grounding_candidate_count`, `grounding_skipped_count`, and `grounding_skip_reasons` keep their current meanings.
- New and existing `tests/test_annotate.py` tests pass.

## References

- [Python ast - Abstract Syntax Trees](https://docs.python.org/3/library/ast.html) — Read for the upstream helper behavior that finds Python function, class, and assignment windows.
- [Python re - Regular Expression Operations](https://docs.python.org/3/library/re.html) — Read for candidate-token extraction rules reused through `plan_tool/review.py:_derive_symbols`.
- [Python pathlib - Object-Oriented Filesystem Paths](https://docs.python.org/3/library/pathlib.html) — Read for the path resolution and file-reading APIs that remain owned by `plan_tool/annotate.py`.

## Deferred

- `plan_tool/prompts/annotate.md` wording updates — The prompt template is not in this step's declared files; revisit only if a later plan expands scope to distinguish leading slices from symbol-centered excerpts in the template prose.
- `plan_tool/prompt_excerpt.py` API redesign — Step 1 owns the helper contract; this step only consumes it.
- Per-file candidate ownership for annotate — Annotate grounds arbitrary notes and plans, so this step uses a conservative shared candidate set rather than trying to assign each cited file to one exact section.
