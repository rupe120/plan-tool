# Implement step ${step_id}: ${step_title}

You are implementing a single step of the plan **"${plan_title}"**.

## Plan context
- Status: ${plan_status} · Priority: ${plan_priority}
- Progress: step ${step_index} of ${step_total} (${done_count} previously done)

## This step

**${step_id}. ${step_title}**

${step_detail}

## Files in scope

${step_files}
${scope_fence_block}
## What to do

**Smallest proof first.**

Implement the shortest end-to-end path that satisfies the approved step using
existing commands, owners and platform behavior. A new abstraction, process
boundary, persisted record, lifecycle or configuration surface must close a
current requirement that unchanged reuse or a direct call cannot satisfy; name
that requirement and the concrete blocker before adding it. Future reuse,
symmetry and generic robustness are not sufficient. Keep required safety,
compatibility, authority and audit properties and explicit owner decisions.
If satisfying the approved contract requires disproportionate machinery, surface
the scope tradeoff instead of silently expanding or weakening the contract.
Record a necessary departure in the existing Validation/Summary output; do not
create a separate proof framework or mandatory document.

Implement this step against the current codebase. Follow the project's
conventions (see `README.md` and the files you touch for local
patterns). Do not consult LLM-specific guidance files (e.g. CLAUDE.md,
AGENTS.md, .cursor/rules, copilot-instructions.md) — rely only on
checked-in project documentation and the existing code. Prefer editing
existing files to creating new ones. Only touch files listed above
unless adding a file is explicitly required by the step.

**Naming.** Choose intuitive, self-descriptive names for variables,
functions, types, and concepts — a reader should grasp intent without a
glossary (prefer `multi_plan_split` over `decomposition`; use directional
names like `skip_below_bytes`, not an ambiguous `skip_bytes`). When you
rename or remove behavior, update **every** reference so nothing dangles.

When finished:
- The files listed above should be in the state described by the step.
- If the plan declares a `test_command`, the launcher runs it as the
  authoritative post-flight gate after you exit — you don't need to run the
  full suite yourself. Run a narrowly relevant check only if it helps you
  confirm the specific change you made; don't introduce new test harnesses
  unless the step asks for them.
- When a test you write pins a deliberate, non-obvious, or corrected
  behavior — one a future reader could plausibly mistake for a bug —
  name it and state its assertion so that intent is explicit
  (`test_context_is_copied_and_cannot_override_event_identity`, not
  `test_emit_extra`). A later audit checks this test before flagging
  the behavior as a regression; it can only tell deliberate from
  broken if the test says which.
- Do not mark the step done in the plan file — the launcher handles that on
  successful exit.
${lessons_section}
When you've finished implementing this step, print TWO final sections
exactly in this format (no additional text after them):

## Validation
<two to five bullets describing what you ran (tests, lints, type checks)
to verify the change, with results. If your environment denies Bash and
you could not run anything, say so explicitly and list what you *would*
have run.>

## Summary
<one line, max 120 chars, describing the most useful thing a future reader
would want to know about what you just did>

## Writing style (strict)

Summary + Validation are re-read by every future review, reconcile,
and lessons-extract — keep them tight.

- **Validation: one bullet per check**, one sentence each. Skip
  filler like "I also ran…", "additionally…".
- **Summary: forward-looking, one line.** Describe the resulting
  state, not the path that got there. **No** "previously did X",
  "used to be Y", "was: Z" — git history captures the rest.
- **Active voice, imperative mood.** "Adds JWT validation in
  `handleSubmit()`" not "JWT validation was added".
