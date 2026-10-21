# Lint and format for step ${step_id}: ${step_title}

Plan: **${plan_title}** · step ${step_index} of ${step_total}

## Step context

${step_detail}

## Files in scope

${step_files}

## What to do

Run the project's lint, format, and type-check tools against the files
above. Figure out which tools apply from `README.md`, `package.json`,
`pyproject.toml`, or equivalent project config. Do not consult
LLM-specific guidance files (e.g. CLAUDE.md, AGENTS.md, .cursor/rules,
copilot-instructions.md) — rely only on checked-in project
documentation and config.

For each tool:

1. Run it (scoped to the files above where the tool supports scoping).
2. Report output. If clean, say so.
3. Apply fixes **only if purely mechanical**:
   - Import order / unused imports
   - Whitespace, trailing newline, quote style
   - Type annotations the tool can infer and insert safely
4. For substantive issues (real type errors, real lint violations that
   require code changes), report and stop — do not rewrite logic under the
   guise of linting.

End your response with a `## Findings` block — one bullet per
unresolved lint/type/format issue, prefixed with a severity token. The
block is machine-parsed; keep it as the final section.

${findings_response_format_block}

Severity guidance:

- **CRITICAL** — real type error or lint violation that breaks the build
- **HIGH** — substantive lint violation requiring code changes
- **MEDIUM** — ordinary lint issue
- **NIT** — style or formatting nit

## Writing style (strict)

Findings are re-read on every audit and CI gate — keep them tight.

- **One finding per bullet, one or two sentences max.**
- **Active voice, imperative mood.**
- **No historical narration.** Drop "previously", "used to", and
  parenthetical asides like "(was: X)". State the current state.
- **Strip filler** — cut "it is worth noting that…", "in this case…".
${lessons_section}
