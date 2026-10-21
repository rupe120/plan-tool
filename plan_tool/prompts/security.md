# Security audit for step ${step_id}: ${step_title}

Plan: **${plan_title}** · step ${step_index} of ${step_total}

## Step context

${step_detail}

## Files in scope

${step_files}

## What to do

Audit the code in the files above for security issues. Use only
checked-in project documentation and the code itself — do not consult
LLM-specific guidance files (e.g. CLAUDE.md, AGENTS.md, .cursor/rules,
copilot-instructions.md). Cover at minimum:

- **Injection**: SQL, shell, template, log-forging
- **Authorization / ownership**: does the code verify the caller owns the
  resource before mutating it? See `mark-notification-read` for the repo's
  ownership pattern.
- **Data exposure**: returning secrets, tokens, emails, or internal ids the
  client doesn't need
- **Auth handling**: JWT verification, session token lifetime, logout flow
- **Input validation** at system boundaries (API, webhook, user input, file
  upload, external service response)
- **Secret handling**: hardcoded credentials, secrets in logs, secrets in
  GraphQL responses
- **IAM**: least-privilege on Lambda roles, broad resource ARNs, `*` actions

Report findings with severity (**critical / high / medium / low / nit**),
**symbolic anchors** (file path plus function/class/section name; line
numbers only as a secondary disambiguator), and a one-line remediation
suggestion. Do not apply fixes — produce a list the user can triage.

End your response with a `## Findings` block — one bullet per finding,
prefixed with an UPPERCASE severity token. The block is machine-parsed;
keep it as the final section.

${findings_response_format_block}

Replace the empty marker with severity-prefixed bullets when the audit finds an
issue.

## Writing style (strict)

Findings are re-read on every audit and CI gate — keep them tight.

- **One finding per bullet, one or two sentences max** (issue + one
  remediation sentence).
- **Active voice, imperative mood.**
- **No historical narration.** Drop "previously", "used to", and
  parenthetical asides like "(was: X)". State the current
  vulnerable state with a symbolic anchor.
- **Strip filler** — cut "it is worth noting that…", "in this case…".
${lessons_section}
