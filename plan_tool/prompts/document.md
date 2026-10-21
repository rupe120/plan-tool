# Documentation pass for step ${step_id}: ${step_title}

Plan: **${plan_title}** · step ${step_index} of ${step_total}

## Step context

${step_detail}

## Files in scope

${step_files}

## What to do

Add documentation to the files above where it pays for itself. Use only
checked-in project documentation and the code itself when judging the
project's conventions — do not consult LLM-specific guidance files (e.g.
CLAUDE.md, AGENTS.md, .cursor/rules, copilot-instructions.md). Focus on:

- Non-obvious invariants a reader would have to reverse-engineer
- Error contracts: what raises, what's swallowed, what's retried
- "Why" comments for decisions that would surprise a reader (workarounds,
  trade-offs, external constraints)
- Module- or class-level docstrings when the purpose isn't self-evident

Do **not** add:

- Comments that explain WHAT well-named identifiers already express
- Doc comments on every method regardless of complexity
- References to the current task, fix, or PR — those belong in git history

Make edits in place. Keep additions short and targeted.

End your response with a `## Findings` block — one bullet per
documentation gap you addressed (or chose not to address), prefixed with
a severity token reflecting how load-bearing the missing comment was.
The block is machine-parsed; keep it as the final section.

${findings_response_format_block}

Severity guidance:

- **CRITICAL** — undocumented invariant a reader would have to reverse-engineer
- **HIGH** — error-contract or workaround comment added
- **MEDIUM** — module/class purpose docstring added
- **NIT** — minor clarification

## Writing style (strict)

Findings are re-read on every audit and CI gate — keep them tight.

- **One finding per bullet, one or two sentences max.**
- **Active voice, imperative mood.**
- **No historical narration** in either the findings *or* any
  proposed comments / docstrings. Drop "previously", "used to", and
  parenthetical asides like "(was: X)". Describe what the code does
  now and the invariants it holds.
- **Strip filler** — cut "it is worth noting that…", "in this case…".
${lessons_section}
