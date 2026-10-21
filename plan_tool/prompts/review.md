# Plan review: ${plan_title}

You are performing a plan-vs-codebase reality check. Read the plan's steps
**and their implementation status**, their per-step acceptance criteria (the
"Step details" section below), and the current contents of the files they
declare, then report whether anything looks off.

The embedded file contents below are a truncated preview for orientation, not
the full repository context. A clipped file is marked `_(truncated)_`, and an
unmarked preview may still omit related files the plan did not declare. Use
your tools: Read and Grep the repository at HEAD before relying on a code claim,
especially for producer symbols, implementation bodies, dependency declarations,
or done-step verification. Read/Grep only; do not edit any file.

Each step is tagged with its status in brackets — `[pending]`, `[current]`,
or `[done]`. A parked step also shows its commitment axis, e.g.
`[pending, deferred]` or `[pending, wont_do]`. The status changes what
you're looking for:

- **Not-yet-implemented steps** (`pending` / `current`) are
  checked **before** they execute — the usual reality check.
- **Parked steps** (`deferred` / `wont_do`) are intentionally out of the
  current scope — note them, but don't flag them as missing work.
- **`done` steps assert their work is already on disk** — check them
  **against the code** to confirm they delivered what they claim, not as
  pending work.

This is distinct from per-step review: do not audit a single step for
correctness. Look across the whole plan (or the single step you were given)
for mismatches between intent and current state.

## Steps

${all_steps_block}

## Step details (acceptance criteria)

${step_details_block}

## Current file contents

${files_contents_block}

## Accumulated lessons (from prior `plan-tool reconcile-plan` and `detail` runs)

${lessons_block}

## What to produce

Use only checked-in project documentation and the code itself when judging
intent vs. reality — do not consult LLM-specific guidance files (e.g.
CLAUDE.md, AGENTS.md, .cursor/rules, copilot-instructions.md).

Return a short markdown section (no headers above level 3).

**For not-yet-implemented steps** (`pending` / `current`) — a
pre-execution reality check. Call out:

- Steps that look **already implemented** by code that's already on disk
  (cite the file and a symbol or two that give it away). When step
  details list acceptance criteria, cite which criteria appear to be met.
- Steps whose **declared files don't match** what the title or details
  describe (wrong path, wrong module, abandoned location). A step's declared
  files are its `files:` (edited) **plus** the ones marked `(new)` (its
  `creates:`) — treat both as declared. A `(new)` file is created *by* this
  step, so for a pending step its absence on disk is expected, not a finding;
  never report a step as "declares no files" or "omits `<file>`" when it lists
  `(new)` paths. Judge whether the declared set matches the code — not whether
  the plan allocated files across steps the way you would (that is the plan's
  own completeness concern, not this code-currency audit's).
- **Missing runtime dependencies** the steps imply but aren't in
  `package.json` / `pyproject.toml` / equivalent — if any file listed above
  makes the answer obvious.

**For `done` steps** — a verification check, not a reality check. The work is
*expected* to be on disk, so:

- **Do not** report a done step as "already implemented" — that is the
  expected, correct state, not a finding.
- **Before flagging a divergence, check the mirrored test file**
  (`tests/test_<module>.py` for `plan_tool/<module>.py`) for an assertion
  that already pins the exact behavior you're about to call wrong. A
  static reading of the diff can be internally consistent and still
  wrong — behavior that looks like a regression is often a deliberate
  correction a test already locks in. A finding contradicted by an
  existing passing test is a false positive; read the test before
  writing the finding, not just the implementation.
- Flag a done step whose code **does not deliver** what its title and details
  describe: a missing, partial, or stubbed implementation, or behavior that
  diverged from the step's acceptance criteria. Cite the file and what's
  missing or wrong.
- Flag a done step whose **declared files don't hold** the described work —
  empty, absent, or the logic landed somewhere else.

Across every status, also call out anything else a reviewer would want to
know.

If nothing is surprising, say so in one line. Do not modify anything —
this is a read-only audit.

After your prose review, end your response with a `## Findings` block
listing one bullet per issue, prefixed with a severity token. The block is
machine-parsed (it is what `reconcile-plan-walk` walks) — keep it as the final
section of the response.

State each bullet's prose as the **problem**: the subject (the `file:symbol`,
plan field, step, or acceptance criterion at issue) and, when the issue
belongs to a specific step, that step's id and title; what's wrong relative
to the code on disk; and the consequence. Then append the remediation in the
exact form `→ fix: <one-line plan/detail edit>` — the concrete edit that
closes the issue. The walk shows it to the operator as "what apply will do"
and feeds it to the apply as the targeted edit, so state the intended
plan/detail edit in one line (a `step.files` change, a `status`/`status_note`
flip, a criterion to add/clarify), not a code change, a diff, or a multi-step
procedure.

${findings_response_format_block}

Severity tokens are `CRITICAL` / `HIGH` / `MEDIUM` / `NIT`. Replace the empty
marker with severity-prefixed problem-and-remediation bullets when there are
issues.

## Writing style (strict)

The review is re-read on every walk, reconcile, and CI gate, and the
operator triages each finding against `(a)pply / (s)kip` from the prose
alone — keep it tight *and* self-contained.

- **Lead with the concrete subject and name the step.** Open with the
  thing the operator acts on — the `file:symbol`, plan field, step, or
  acceptance criterion — and when the issue belongs to a specific step,
  name it by id and title (e.g. "step 4 ('persist the cache')"). The walk
  clips your first line into the finding's title, so an opening like "The
  plan says…" or a bare "a step" yields a title that names nothing
  actionable. Lead with the subject, not the plan's framing of it.
- **Make each finding decidable on its own.** State what the plan
  declares, how the code on disk diverges, and the consequence —
  concretely enough that the operator can choose apply-or-skip without
  re-reading the plan. Don't force the reader to resolve a back-reference
  ("that step", "the section above") to recover the subject.
- **One bullet per concern; two or three sentences if that is what it
  takes to state subject + problem + consequence — but no padding.**
- **Active voice, imperative mood.** "Drop `foo.ts` from step.files
  — file no longer exists" not "It may be worth considering whether
  `foo.ts` should be dropped".
- **No historical narration.** Drop "previously", "used to", and
  parenthetical asides like "(was: X)". State what's on disk now
  and the proposed forward state.
- **Strip filler** — cut "it is worth noting that…", "in this case…",
  "this means that…".
