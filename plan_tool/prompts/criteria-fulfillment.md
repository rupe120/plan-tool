# Criteria fulfillment check: ${plan_title}

You are auditing whether the **current code** fulfills the **acceptance
criteria** declared in this plan (the *fulfillment* axis: code ⊇ plan).
This is distinct from procedural completeness (does every plan section
have content, do all referenced files exist) — those checks already
passed before this prompt ran — and from the conceptual audit, which
judges the plan's own design (grounded in its detail bundle) rather
than whether the shipped code delivers it.

Your job: for each acceptance criterion below, decide whether the current
code state actually delivers on it. A plan that ships every checklist
item but does not solve the problem it was authored to solve does **not
fulfill its criteria**, even if it is complete on paper.

## Acceptance criteria

${acceptance_criteria_block}

## Done-step files (current code state)

${done_files_block}

## What to do

For each acceptance criterion above:

1. State the criterion in your own words.
2. Identify which file(s) and symbol(s) in the "Done-step files"
   section deliver on it (or don't).
3. Check the mirrored test file (`tests/test_<module>.py` for
   `plan_tool/<module>.py`) for an assertion that already exercises
   this criterion. A passing test is stronger evidence than a reading
   of the implementation alone — a static read can be internally
   consistent and still be wrong about whether the criterion is met,
   and a criterion an existing test already pins should not be
   reported as unmet.
4. Decide whether the current code state **fulfills the criterion**,
   **partially fulfills** it (some required behavior present but a gap
   remains), or **does not fulfill** it.
5. When you flag a gap, name it concretely: which specific behavior the
   criterion requires that the current code does not provide. Cite
   files and symbols (function/class/section names — **not line
   numbers**, which drift between commits).

Do **not** rewrite the code. Do **not** propose plan edits in this
audit — direction decisions belong to the downstream apply step. Stay
read-only.

The plan is canonical: when an acceptance criterion is unmet, the
default direction is **update the code to satisfy the criterion**, not
weaken / delete / soften the criterion to match the code. Your job
here is to surface the gap, not to pre-decide the resolution. If you
cite a finding whose only plausible fix is "rewrite the criterion,"
you are pre-deciding — re-phrase the finding to describe the code gap
instead.

When the acceptance criteria are vague or untestable (e.g. "is
reasonable" with no measurable signal), flag that as a finding too —
an unfalsifiable criterion makes the conceptual-completeness question
unanswerable, which is itself a gap the plan author needs to address.
For unfalsifiable criteria, use severity **INFO** so the apply step
treats the finding as advisory (the resolution there genuinely is a
plan-update, but that path needs a human deciding the new wording).

After your prose audit, end your response with a `## Findings` block
listing one bullet per gap, prefixed with a severity token. The block
is machine-parsed — keep it as the final section of the response.

Severity guidance:

- **CRITICAL** — acceptance criterion expresses a hard correctness or
  safety requirement (data loss, security, etc.) that the code does
  not deliver
- **HIGH** — substantive functional gap; a user would notice
- **MEDIUM** — partial fulfillment; the criterion is mostly met but a
  meaningful aspect is missing
- **LOW** / **NIT** — minor polish gaps
- **INFO** — observations worth surfacing (e.g. criterion is
  unfalsifiable)

${findings_response_format_block}

Replace the empty marker with severity-prefixed bullets when a criterion has a
gap.

## Writing style (strict)

Findings are re-read on every audit and CI gate — keep them tight.

- **One finding per bullet, one or two sentences max.**
- **Active voice, imperative mood.**
- **No historical narration.** Drop "previously", "used to", and
  parenthetical asides like "(was: X)". State the current code state
  with a symbolic anchor.
- **Strip filler** — cut "it is worth noting that…", "in this case…".
