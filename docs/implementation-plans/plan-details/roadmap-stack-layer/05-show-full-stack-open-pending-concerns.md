# Step 5 — Show the full stack in the first run's completion output and in INDEX.md, both fed by one summary producer

<!-- plan-tool:detail-format-version: 1 -->

## Summary

- Adds `plan_tool/roadmap_stack_summary.py`, the only place that turns a parsed `02-constraints.md` into stack summary lines. It lists every stack row, with open concerns and pending concerns in separate groups.
- `plan_tool/cli/roadmap_cmd.py:_print_completed` prints those lines after a first stage run publishes. This is the only route to acceptance that has no candidate review, so it is the only place the reviewer would otherwise miss the stack.
- `plan_tool/roadmap_index.py:render_roadmap_index` adds a `## Stack` section, with the same lines, to the generated `INDEX.md`. `write_roadmap_index` stays a whole-file atomic rewrite.
- Key decision: the producer returns plain text lines and nothing else. It does not gate, judge, or write anything. A version with no `stack` collection shows an explicit "stack not recorded" line.
- On green, a first run prints the full stack with its open and pending groups, and `INDEX.md` shows the same text for the accepted head.

## Table of Contents

- [Summary](#summary) — what the step does and the result on green
- [Why](#why) — the unseen-acceptance gap on the first run
- [Input](#input) — what steps 1 and 2 hand this step
- [Files (creates vs edits)](#files-creates-vs-edits) — the six files touched
- [Implementation](#implementation) — producer, the two consumers, and what must not vary
- [Tests](#tests) — the cases that pin the behavior
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [Applicable guardrails](#applicable-guardrails) — the plan fences that bind this step
- [Deferred](#deferred) — work that belongs elsewhere

## Why

- A first stage run publishes the root version without candidate review. `cmd_roadmap` calls `_print_completed`, which prints artifact paths, create handoff lines, and a pending-decision count. It says nothing about the stack, so a stack choice or open stack question can be accepted unseen.
- `render_roadmap_index` (called through `write_roadmap_index` from `plan_tool/roadmap.py`) lists the four artifact links and the version table. A reader of `INDEX.md` cannot tell what the stack is, or that it was never recorded.
- Two consumers need the same facts. If each formats its own, they drift. One producer keeps one wording.
- Versions that predate the collection must read "stack not recorded", never an empty stack. Step 1 made that difference exist in the parsed type.

## Input

- **Step 1 output.** `ConstraintsArtifact.stack` is `None` (not recorded), `()` (present, empty), or an ordered tuple of stack rows. Each row has an id, a `concern`, and either a `choice` or an `open` marker.
- **Step 2 output.** Stack ids are in the anchor union, so a decision can anchor to a stack row. Pending is derived from decisions, never stored on the row.
- **Names come from the landed code.** HEAD has no `stack` symbol in `plan_tool/roadmap_artifacts.py` when this file was written. Read the landed row type, field names, and decision row type. Landed names win over every name used here.
- **Pending source.** A decision in the constraints, components, or plans artifact can anchor to a stack row, because stack ids join the anchor union those stages resolve against. Pending is read from the decision rows of all three. Check the landed `check_decision_records` and `_envelope_rows` for the exact source before choosing what the producer accepts.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_stack_summary.py` — the single producer.
  - `tests/test_roadmap_stack_summary.py` — its unit tests.
- **Existing files (edits only):**
  - `plan_tool/roadmap_index.py`:
    - read the head's `02-constraints.md` and the pending decisions of `02-constraints.md`, `03-components.md`, and `04-roadmap.md`;
    - add the `## Stack` section to `render_roadmap_index`;
    - keep `write_roadmap_index` as one atomic whole-file write.
  - `plan_tool/cli/roadmap_cmd.py`: have `_print_completed` print the summary lines. Locate the constraints artifact the way `_plans_artifact_path` locates `04-roadmap.md`.
  - `tests/test_roadmap_index.py`: add the INDEX cases below. Update only assertions the new section breaks.
  - `tests/cli/test_roadmap_cmd.py`: add the completion-output cases below.

## Implementation

**The producer.** One function, for example `stack_summary_lines(constraints, pending_anchor_ids)`, returning `list[str]`.
- Inputs are parsed values: the `ConstraintsArtifact` and the set of row ids that have a `pending` decision anchored to them. It does no file I/O and no backend call.
- **`stack is None`** returns one line saying the stack is not recorded for this version. It must not print an empty-stack message.
- **`stack == ()`** returns a line saying the stack collection is present and has no rows. This differs from the `None` line.
- **Otherwise** it prints, in source order:
  - every row as `<concern>: <choice>` or `<concern>: open`, with the row id;
  - an "Open concerns" group listing rows marked `open`;
  - a "Pending concerns" group listing rows with a pending decision anchored to their id.
- **Empty groups keep their heading and say `none`**, so a reader can tell the question was asked.
- A row can sit in both groups. An `open` row with a pending decision shows in each.
- Lines are plain text. No severity, blocking flag, or verdict. Rows with unknown concerns or duplicate ids print as stored; reporting them is step 2's gate.

**Where pending ids come from.** Pending is derived, not stored (step 1). Keep the derivation in the producer's module as a small helper over parsed decision rows, so both consumers get the same set. Do not duplicate it in either consumer.

**Consumer 1: completion output.**
- In `_print_completed`, find the written `02-constraints.md` in `result.artifacts` by filename, load it with the existing artifact loader, and `detail(...)` each producer line.
- Print only on a completed first run. `_print_completed_no_change` stays as it is, because it publishes nothing.
- A load error must not fail the run. Mirror `_create_handoff_lines`: call `error(...)` with a self-contained message and print nothing else.
- Rejected alternative: add the lines to `RoadmapResult`. The CLI layer already owns summary text, and `RoadmapResult` is "facts only".

**Consumer 2: INDEX.md.**
- `render_roadmap_index` takes the producer lines as a new argument and places `## Stack` between "Accepted head" and "Versions".
- Collect the lines in `write_roadmap_index` (or `collect_index_rows`' caller) by loading the head's constraints artifact from the version store. `roadmap_index.py` already imports from `plan_tool.roadmap_artifacts`, so the producer module must import only `plan_tool.roadmap_artifacts` to keep the leaf rule.
- Keep `INDEX.md` a full replacement via `atomic_write_text`. No append, no merge.
- A stored head whose constraints artifact cannot be parsed must raise the same `RoadmapVersionError` family the index already uses for malformed records, not print a misleading "not recorded".

**Constraints.**
- The producer must not import `plan_tool.roadmap`, `plan_tool.roadmap_index`, or `plan_tool.cli`.
- It must not pass judgment on any choice. It shows facts.
- `render_roadmap_index` stays a pure function of its arguments.

## Tests

`tests/test_roadmap_stack_summary.py`:
- `test_not_recorded_stack_prints_not_recorded_not_empty` — `stack=None` returns the not-recorded line, which differs from the `()` line.
- `test_empty_stack_prints_present_but_empty` — `stack=()` gets its own line.
- `test_every_row_is_listed_in_source_order` — all rows appear with id, concern, and choice or `open`.
- `test_open_and_pending_concerns_are_listed_separately` — an open row appears only under open; a pending-anchored chosen row appears only under pending.
- `test_row_both_open_and_pending_appears_in_both_groups` — one row shows in each group.
- `test_empty_groups_keep_their_heading_and_say_none` — explicit `none`, not a missing heading.
- `test_unknown_concern_and_duplicate_id_print_as_stored` — the producer reports no violation; step 2 owns that.
- `test_producer_imports_only_the_artifacts_leaf` — a source scan finds no import of `roadmap`, `roadmap_index`, or `cli`.

`tests/test_roadmap_index.py`:
- `test_index_stack_section_lists_every_row_with_groups` — the accepted head's stack appears in `## Stack`.
- `test_index_for_stackless_head_says_not_recorded` — a head with no `stack` key shows the not-recorded line.
- `test_index_stack_text_equals_producer_output` — the section lines are exactly the producer's lines (one source).
- `test_index_rewrite_is_whole_file_and_replaces_prior_stack_section` — a second write after the stack changes leaves no stale rows.
- `test_index_with_unparseable_head_constraints_raises_version_error` — no silent "not recorded".

`tests/cli/test_roadmap_cmd.py`:
- `test_first_run_completion_prints_the_full_stack_with_open_and_pending_groups` — output has every row and both groups.
- `test_first_run_without_a_stack_prints_not_recorded` — the explicit line, not silence.
- `test_no_change_regate_prints_no_stack_block` — `_print_completed_no_change` output is unchanged.
- `test_unloadable_constraints_artifact_reports_error_and_keeps_exit_code` — the run's exit code is unchanged.

### Tests for this step

All tests above are added in this step. Every one must be green before the step is done, along with the existing `tests/test_roadmap_index.py` and `tests/cli/test_roadmap_cmd.py` suites after the assertions the new output breaks are updated.

## Acceptance criteria

- A first stage run that publishes prints each stack row, an open group, and a pending group.
- A version with no `stack` collection prints "not recorded" in the completion output and in `INDEX.md`, and this differs from the empty-collection line.
- `INDEX.md` has a `## Stack` section whose lines equal `stack_summary_lines` output.
- `write_roadmap_index` still replaces the file whole through `atomic_write_text`.
- `rg 'import' plan_tool/roadmap_stack_summary.py` shows no `plan_tool.roadmap`, `plan_tool.roadmap_index`, or `plan_tool.cli` import.
- `rg 'stack' plan_tool/cli/roadmap_cmd.py plan_tool/roadmap_index.py` shows no row formatting outside calls to the producer.
- Exit codes of `plan-tool roadmap` are unchanged.

## Applicable guardrails

- **The plan's "## Out of scope", non-goals.** This step must not add a fifth artifact, an approval block on stack content, or any judgment of whether a choice is good. The summary only reports what is stored.
- **The plan's "## Out of scope", non-goals on existing versions.** The step must not rewrite or regenerate an accepted version. `INDEX.md` is a generated view, and it is rewritten whole as it already is.
- **The plan intent and this step's intent.** Only the first-run and index surfaces change here. Candidate-review surfaces belong to the plan's other steps.

## Deferred

- Candidate-review callout of the stack — belongs to the plan's candidate-review step, not this one.
- Format documentation of the summary wording — belongs to the plan's documentation step.
- Gate reports for unknown concerns and duplicate ids — step 2 owns them.
- Integration's HTML review aid — follows separately in Integration, per the plan's out-of-scope list.
