# Correctness review for step ${step_id}: ${step_title}

Plan: **${plan_title}** · step ${step_index} of ${step_total}

## Step context

${step_detail}

## Files in scope

${step_files}

## What to do

Review the code in the files above for correctness as an implementation of
this step. Use only checked-in project documentation and the code itself —
do not consult LLM-specific guidance files (e.g. CLAUDE.md, AGENTS.md,
.cursor/rules, copilot-instructions.md). Look for:

- Bugs and logic errors
- Missing input validation on external/user boundaries
- Error paths that silently swallow failures
- Edge cases the step description implies but the code doesn't handle
- Mismatches between what the step says it should do and what the code does

Do **not** rewrite the code. Report findings inline using **symbolic anchors**
(file path plus a stable identifier — a function name, class name, section
heading, or constant — e.g. `apps/foo.ts:handleSubmit()`), not raw
`file:line` references. Line numbers drift on every commit; symbolic
anchors stay stable. Quote a line number only as a secondary
disambiguator when a symbol appears more than once in a file. Provide a
brief explanation of each issue. Group by severity (critical → nit).
If the implementation looks correct, say so plainly.

After your prose review, end your response with a `## Findings` block
listing one bullet per issue, prefixed with a severity token. The block is
machine-parsed — keep it as the final section of the response.

${findings_response_format_block}

Severity tokens are `CRITICAL` / `HIGH` / `MEDIUM` / `NIT`; state each bullet
as a one-line description with file:symbol.

## Writing style (strict)

Findings are re-read on every audit and CI gate — keep them tight.

- **One finding per bullet, one or two sentences max.**
- **Active voice, imperative mood.** "Add validation in X" not "It
  may be advisable to add validation".
- **No historical narration.** Drop "previously", "used to", and
  parenthetical asides like "(was: X)". Describe the current code
  state with a symbolic anchor.
- **Strip filler** — cut "it is worth noting that…", "in this case…",
  "this means that…".
${lessons_section}
