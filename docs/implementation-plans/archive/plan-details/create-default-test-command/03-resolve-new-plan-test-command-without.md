# Step 3 — Resolve a new plan's test command without guessing

## Summary

Update `plan_tool/create.py` so a new plan receives the optional command qualified by step 2 before it reaches `write_new_plan`. When step 2 returns unknown, let an interactive operator supply one command for the current invocation; `--yes` and non-TTY runs omit the field without prompting. The key decision is fixed source precedence and exact placeholder normalization, while preserving an accepted operator command as shell text. On green, `tests/test_create.py` proves each new plan either contains an authorized non-empty `test_command` or omits the frontmatter key safely.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the command-resolution change.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — The missing connection between qualification and new-plan output.
- [Input](#input) — The qualified result and persisted plan-field contract.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two existing files this step changes.
- [Implementation](#implementation) — Source precedence, normalization, and unattended behavior.
- [Tests](#tests) — Coverage for qualified, interactive, and omission paths.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Field contract and deferred follow-up.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this step.
- [Deferred](#deferred) — Work that remains outside this change.

## Why

`plan_tool/create.py:_prepare_create_plan` enables `enforce_step_tests` for every new plan but currently constructs `Plan` without a `test_command`. Step 2 supplies a safe optional source for that field, but `create` must connect it to frontmatter without turning an unknown repository or a placeholder answer into a shell command that `plan_tool/launcher.py:run_step` will later execute.

## Input

- **Step 2 qualified result:** Step 2 produces either its one preflight-qualified command or `None`. Treat that result as the automatic source; do not repeat its marker checks or process execution in `plan_tool/create.py`.

- **Plan field contract:** `plan_tool/schema.py:Plan` defines `test_command` as optional, and `plan_tool/parser.py:write_plan` omits it when its value is `None`. Preserve that distinction: unknown input produces no frontmatter key, not an empty string.

- **Runtime consumer:** `plan_tool/launcher.py:run_step` sends a truthy `Plan.test_command` to `plan_tool/launcher.py:_run_test_gate`. This step decides whether the value is present; it does not change execution, failure, or retry behavior.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/create.py` — Integrate step 2’s qualified result into `_prepare_create_plan`, resolve the interactive fallback, and pass the resulting optional value into `Plan`.
  - `tests/test_create.py` — Add focused create-flow coverage for source precedence, normalization, unattended omission, and non-persistence.

## Implementation

- **Foundational logic:** qualified-command precedence with interactive fallback normalization.

- **Resolve once before plan assembly:** In `plan_tool/create.py:_prepare_create_plan`, call step 2’s qualifier once with the resolved repository root before constructing `Plan`. A qualified result becomes the plan’s `test_command` and bypasses the operator prompt.

- **Use the operator only for unknown results:** When the qualifier returns `None`, prompt exactly once only when this is an interactive invocation. A concrete answer is the second authorized source of `test_command`; do not infer a command from repository files, model output, or prompt defaults.

- **Skip prompting when unattended:** Under `yes=True` or non-TTY stdin, keep an unknown result as `None`, write one stderr note that the test command was omitted, and continue creating the plan. Still allow a qualified command in these modes.

- **Normalize without rewriting shell syntax:** Strip leading and trailing whitespace from an interactive answer, but preserve all remaining command text. Do not split, quote, escape, collapse internal whitespace, validate, execute, or preflight an operator-supplied command during `create`.

- **Define the complete placeholder policy:** After trimming, omit only an empty value or one of these case-insensitive whole-value placeholders: `TODO`, `(TODO)`, `_(TODO)_`, `TBD`, `(TBD)`, and `_(TBD)_`. `plan_tool/scope_fence.py:is_placeholder_intent` already recognizes that exact six-value set and is a suitable shared predicate; do not reject a concrete command merely because it contains `todo` or `tbd` as part of longer text.

- **Keep omission separate from a command:** Pass the resolved optional value into the existing `Plan(...)` construction. Leave `plan_tool/create.py:write_new_plan` on its current canonical serialization path so `None` stays absent from frontmatter and an accepted command round-trips normally.

- **Keep the answer invocation-local:** Do not add a checkpoint, resume source, command-history field, or public `create_plan` parameter. The operator supplies the answer again on a later unknown invocation.

## Tests

### Tests for this step

Every test below must be green before this feature step is finished.

- `test_create_plan_uses_preflight_qualified_test_command` — A qualified result writes the exact candidate to parsed and raw plan frontmatter without an operator prompt.
- `test_create_plan_prompts_once_for_unknown_test_command` — An unknown result on a TTY accepts one concrete operator command for the created plan.
- `test_create_plan_trims_operator_test_command_without_rewriting_it` — Leading and trailing whitespace are removed while internal shell syntax remains unchanged.
- `test_create_plan_omits_blank_or_placeholder_test_command` — Blank, whitespace-only, and each of the six defined placeholder values leave `test_command` absent from frontmatter.
- `test_create_plan_keeps_command_containing_placeholder_text` — A concrete command containing `TODO` or `TBD` as part of longer text is not mistaken for a placeholder.
- `test_create_plan_unknown_test_command_omits_without_prompt_under_yes` — `--yes` does not consume an operator answer, omits an unknown command, and writes one omission note.
- `test_create_plan_unknown_test_command_omits_without_prompt_on_non_tty` — Non-TTY stdin follows the same no-prompt, omitted-field, single-note behavior.
- `test_create_plan_does_not_reuse_operator_test_command_across_invocations` — A manual answer is not retained or reused by a later unknown create invocation.

## Acceptance criteria

- A qualified result from step 2 writes exactly `uv run pytest tests/ -q -n auto` as `test_command`.
- A qualified result takes precedence over the interactive fallback and does not prompt the operator.
- An unknown TTY invocation accepts one trimmed, concrete operator command without executing or validating it during `create`.
- Empty input and exactly the six defined placeholder spellings omit `test_command`; a longer command containing those words remains valid input.
- An unknown `--yes` or non-TTY invocation does not prompt, exits successfully, omits the frontmatter key, and emits one stderr notice.
- No checkpoint, resume path, or new `create_plan` argument stores an operator-supplied command.
- `tests/test_create.py` passes with every listed case green.

## References

- [PLAN_FORMAT.md](../../../../PLAN_FORMAT.md) — Read the `test_command` and `enforce_step_tests` field contract.
- [BACKLOG.md #234](../../../../BACKLOG.md) — Read the settled command-selection scope and remaining cost-bound follow-up.

## Applicable guardrails

- **The plan’s “## Plan intent”** — Emit a command only from step 2’s successful qualification or a concrete interactive answer, so the existing run gate gains coverage without guessed commands.

- **The plan’s “## Step intent”** — Keep resolution limited to writing the qualified value, one immediate operator fallback, or safe omission.

- **The plan’s “## Out of scope”** — Do not widen the runtime gate, retain operator input, inspect more repository signals, or add another command-selection path.

## Deferred

- Test-gate execution, failure attribution, and retry behavior — Remain owned by the existing `run` lane.
- Remembering an operator answer for a later invocation — Stays outside this step because the answer is deliberately invocation-local.
- Additional test ecosystems or broader command detection — Require a separate fixed rule and coverage.
- Test-command cost bounding — Remains tracked by `BACKLOG.md` #234.
