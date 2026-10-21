# Write tests for step ${step_id}: ${step_title}

Plan: **${plan_title}** · step ${step_index} of ${step_total}

## Step context

${step_detail}

## Files in scope

${step_files}

## What to do

Write unit tests for the code in the files above. Before writing tests:

1. Look at the project's existing test conventions. Check `README.md` and
   the test files closest to the code you're testing to match their style,
   framework, and patterns. Do not consult LLM-specific guidance files
   (e.g. CLAUDE.md, AGENTS.md, .cursor/rules, copilot-instructions.md) —
   rely only on checked-in project documentation and existing tests.
2. Use the repo's existing test infrastructure — don't introduce a new
   harness, mocking library, or assertion style.

Coverage goals:

- The golden path for each public function / route / handler
- Error paths the code explicitly handles (what happens on bad input, timeout,
  auth failure, etc.)
- Any edge case the step description calls out by name

Do **not** write integration tests unless the project already uses them for
similar code. Keep each test tight and named for what it asserts, not for
the function it exercises.

End your response with a `## Findings` block — one bullet per coverage
gap you covered (or flagged but chose not to cover), prefixed with a
severity token reflecting the risk of leaving the gap open. The block is
machine-parsed; keep it as the final section.

${findings_response_format_block}

Severity guidance:

- **CRITICAL** — untested error path that could ship a bug
- **HIGH** — untested edge case the step description names
- **MEDIUM** — ordinary coverage gap
- **NIT** — stylistic test polish

## Writing style (strict)

Findings are re-read on every audit and CI gate — keep them tight.

- **One finding per bullet, one or two sentences max.**
- **Active voice, imperative mood.**
- **No historical narration.** Drop "previously", "used to", and
  parenthetical asides like "(was: X)". Describe the current
  coverage and the gap.
- **Strip filler** — cut "it is worth noting that…", "in this case…".
${lessons_section}
