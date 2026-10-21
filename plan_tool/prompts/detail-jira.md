# Jira-grade detail for step ${step_id}: ${step_title}

You are writing the compact detail for one step of the plan
**"${plan_title}"** (status ${plan_status} · priority ${plan_priority}).

**Audience: someone who decides and tracks the work, not the person typing
the code.** A product owner, a reviewer, or an engineer sizing the ticket
reads this before opening the repo. Say what the step is for, what it
changes, what rules it must obey, when it is finished, and what it leaves
alone. Leave the line-by-line mechanics out — the developer-facing detail
file carries those.

Be short. The whole file should read in under a minute.

${project_context_block}## Step

**${step_id}. ${step_title}** (complexity: ${step_complexity})

depends_on: ${step_depends_on}

### Files in scope

${step_files_block}

### Current file contents

${files_contents_block}

### Plan-level guardrails and scope fence (authoritative)

${scope_fence_block}

## Read the code first

Ground every claim in what is on disk today. Grep for the symbols and paths
you plan to name, and use only checked-in project documentation and the code
itself — do not consult LLM-specific guidance files (e.g. CLAUDE.md,
AGENTS.md, .cursor/rules, copilot-instructions.md).

Write file paths in full from the repo root (`plan_tool/cli/authoring.py`,
never a bare `authoring.py`). Cite symbols by name — function, class,
constant, heading — and skip line numbers, which move on every commit.

## Output format (strict)

Respond with the Markdown file body and nothing else. The first character
must be `#` (the H1 title). No preamble, no fence around the whole file, no
closing commentary.
${output_path_block}

Emit exactly these five `##` sections, in this order:

- `## Intent` — why this step exists and who gets something from it.
- `## Change` — what the step builds or alters, described so a reader can
  picture it. Name the files and surfaces it touches.
- `## Constraints` — the rules the change must obey: contracts it cannot
  break, steps it depends on, decisions already settled.
- `## Done when` — the acceptance surface, as a bulleted list. Each bullet
  is one statement someone can check and call true or false.
- `## Out of scope` — what this step deliberately leaves alone, and who owns
  each of those things instead.

**The schema is closed.** No other `##` heading may appear — no Summary, no
Table of Contents, no Files, no Implementation, no Tests, no Acceptance
criteria, no References, no Deferred. Use `###` subheadings inside a section
when you need structure. Every one of the five sections needs a body; an
empty section is rejected, and nothing is stubbed in for you.

## Writing style (strict)

A gate reads this file before it is saved and rejects padded or over-long
prose, so write it plain the first time.

- **Short, direct sentences.** Split a long one with a period rather than
  stacking clauses behind commas.
- **Everyday words.** Write it the way you would say it out loud to a
  teammate. Keep the exact technical names — types, fields, flags, paths —
  and swap out only decorative wording.
- **No filler.** Cut phrases like "in order to", "it is worth noting that",
  "the fact that", and "at the end of the day". Say the thing directly.
- **Compact sections.** Each section stays well short of a page. This file
  is a summary, not a spec.
- **Active voice, present tense.** "Adds the `--grade` flag", not "the flag
  was added".
- **No history.** Describe the state this step leaves behind. Drop
  "previously", "used to", and "(was: X)".
