# Optimization review for step ${step_id}: ${step_title}

Plan: **${plan_title}** · step ${step_index} of ${step_total}

## Step context

${step_detail}

## Files in scope

${step_files}

## What to do

Review the code in the files above for opportunities to simplify or tighten.
Use only checked-in project documentation and the code itself — do not
consult LLM-specific guidance files (e.g. CLAUDE.md, AGENTS.md,
.cursor/rules, copilot-instructions.md). Look for:

- Dead code or unused imports/variables
- Duplicated logic that could be factored out
- Over-broad exception handling that masks real errors
- Premature abstractions that could be inlined without loss
- Over-commented "what" explanations that well-named identifiers already cover
- Unintuitive names — vague or jargon-y identifiers a reader can't grasp without
  a glossary (suggest a self-descriptive rename, e.g. `decomposition` →
  `multi_plan_split`, ambiguous `skip_bytes` → directional `skip_below_bytes`)
- Stale historical references — comments/docstrings narrating what the code
  "used to" do or "the old X" (the behavior is gone; git history holds the past)
- Obviously-hot paths that could avoid allocations or redundant work

Propose concrete changes inline using **symbolic anchors** (file path plus
function/class/section name, e.g. `apps/foo.ts:handleSubmit()`), not raw
`file:line` references. Line numbers drift on every commit; symbolic
anchors stay stable. Do **not** apply the changes yet — the goal is a list
for the user to review. Prefer fewer, higher-signal suggestions over a
long list of micro-tweaks.

End your response with a `## Findings` block — one bullet per suggestion,
prefixed with a severity token reflecting the cost of *not* applying the
change. The block is machine-parsed; keep it as the final section.

${findings_response_format_block}

Severity guidance:

- **CRITICAL** — bug-like or security-tinged simplification
- **HIGH** — substantive simplification or dead-code removal
- **MEDIUM** — ordinary cleanup
- **NIT** — cosmetic tightening

## Writing style (strict)

Findings are re-read on every audit and CI gate — keep them tight.

- **One finding per bullet, one or two sentences max.**
- **Active voice, imperative mood.**
- **No historical narration.** Drop "previously", "used to", and
  parenthetical asides like "(was: X)". State the current state.
- **Strip filler** — cut "it is worth noting that…", "in this case…".
${lessons_section}
