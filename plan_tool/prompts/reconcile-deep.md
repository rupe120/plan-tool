# Verify acceptance criterion for step ${step_id}: ${step_title}

Plan: **${plan_title}** · step ${step_index} of ${step_total}

This step is marked done. Verify whether the codebase satisfies a single
acceptance criterion taken from the step's design notes.

## Step context

${step_detail}

## Files claimed to be in scope

${step_files}

## Acceptance criterion to verify

> ${acceptance_bullet}

## What to do

1. Read the step's design notes and the files in scope. Use only
   checked-in project documentation and the code itself — do not
   consult LLM-specific guidance files (e.g. CLAUDE.md, AGENTS.md,
   .cursor/rules, copilot-instructions.md).
2. Check the mirrored test file (`tests/test_<module>.py` for
   `plan_tool/<module>.py`) for an assertion that already exercises this
   criterion. A passing test is stronger evidence than a reading of the
   implementation — a static read can be internally consistent and
   still wrong about whether the criterion holds.
3. Decide whether the code as it stands today satisfies *this specific*
   acceptance criterion. Don't grade the step as a whole — focus on the
   single bullet above.
4. Cite the file path(s) plus a **symbolic anchor** (function name,
   class name, section heading, constant, or unique identifier) that
   demonstrates the criterion is met or is missing. Avoid bare line
   numbers; they drift on every commit and are the single biggest
   source of churn findings on subsequent audits.

Do not modify anything. This is a read-only audit.

## Output contract

${verdict_response_format_block}

The token is machine-parsed. Its meaning is:

- `PASS` — the codebase satisfies this criterion. Cite the evidence
  in the prose above the verdict.
- `FAIL` — the criterion is not satisfied. Cite the specific gap.
- `UNKNOWN` — you cannot determine satisfaction from the available
  context (e.g. the criterion references runtime behavior, external
  systems, or files outside the step's declared scope).

${lessons_section}
