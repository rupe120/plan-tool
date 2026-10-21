# Implement step ${step_id}: ${step_title}

You are implementing one step of the plan **"${plan_title}"**.

## Plan context
- Status: ${plan_status} · Priority: ${plan_priority}
- Progress: step ${step_index} of ${step_total} (${done_count} previously done)

## This step

**${step_id}. ${step_title}**

The detail below is a compact contract with five sections. Read them this way:

- **Intent** — why the step exists.
- **Change** — what to build.
- **Constraints** — rules the change must obey.
- **Done when** — the acceptance surface. You are finished when every line
  there is true.
- **Out of scope** — the fence. Do not build what it rules out.

The detail states the behavior, not every edit. The step title and the files
list carry the footprint.

${step_detail}

## Files in scope

${step_files}
${scope_fence_block}
## What to do

Implement this step against the current codebase. Follow the project's
conventions (see `README.md` and the files you touch for local patterns).
Do not consult LLM-specific guidance files (e.g. CLAUDE.md, AGENTS.md,
.cursor/rules, copilot-instructions.md) — rely only on checked-in project
documentation and the existing code. Edit existing files before creating
new ones. Touch only the files listed above unless the step requires a
new one.

**Naming.** Pick names that explain themselves — a reader should get the
intent without a glossary (prefer `multi_plan_split` over `decomposition`;
use directional names like `skip_below_bytes`, not an ambiguous
`skip_bytes`). When you rename or remove something, update every reference
so nothing dangles.

When you finish:
- The files above are in the state **Change** describes, and every **Done
  when** line holds.
- If the plan declares a `test_command`, the launcher runs it as the
  authoritative post-flight gate after you exit. Run a narrow check only to
  confirm your own change; do not add a new test harness unless the step
  asks for one.
- Do not mark the step done in the plan file — the launcher does that when
  you exit cleanly.
${lessons_section}
When you are done, print TWO final sections in exactly this format, with
nothing after them:

## Validation
<two to five bullets naming what you ran (tests, lints, type checks) and the
result. If your environment denies Bash and you could not run anything, say
so and list what you would have run.>

## Summary
<one line, max 120 chars, on the most useful thing a future reader would want
to know about what you just did>

## Writing style (strict)

Every later review, reconcile, and lessons pass re-reads Summary and
Validation. Keep them tight.

- **Validation: one bullet per check**, one sentence each. Skip filler like
  "I also ran…" or "additionally…".
- **Summary: forward-looking, one line.** Describe the state you left, not
  the path that got there. **No** "previously did X", "used to be Y",
  "was: Z" — git history holds that.
- **Active voice, imperative mood.** "Adds JWT validation in
  `handleSubmit()`" not "JWT validation was added".
