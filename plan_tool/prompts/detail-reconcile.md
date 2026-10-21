# Reconcile plan/detail vs code — step ${step_id}: ${step_title}

Plan: **${plan_title}** · step ${step_index} of ${step_total}

The **code on disk is canonical**. Your job is to propose edits to the
plan file and to this step's detail file so they reflect what was
actually delivered. **Do not modify code.** Plan and detail edits only.
The direction of truth is fixed by how this audit was invoked — every
finding closes a gap by editing the plan or the detail, never by
changing code.

## Step context

${step_detail}

## Files claimed to be in scope

${step_files}

## Scope and the post-apply guard (FYI)

For context: the apply layer snapshots the filesystem around each apply
and classifies any out-of-scope file change. Out-of-scope **code** edits
without an in-scope reference are reverted and bundled into a follow-up
implementation-plan stub; out-of-scope **documentation** edits are kept
and reported informationally; in-scope edits land normally. You do not
need to second-guess scope when generating findings — the guard handles
classification at apply time, and the end-of-loop rollup surfaces what
landed where.

**Surface cross-cutting drift even when the fix would spill outside
this step's scope.** The most valuable reconcile findings often come
from seeing the broader picture — this step's code conflicts with
another step's interface, a sibling module diverged from the plan's
architecture section, a shared utility this step touches changed
behavior elsewhere. Don't suppress those findings on the grounds
that the fix lives outside `step.files`. Flag them and let the apply
layer handle the scope question. **A holistic plan-level finding the
audit didn't surface is strictly worse than one the guard has to
classify.**

## What to do

Compare the step's declared intent (title, detail, files, acceptance
criteria) against the code currently on disk. Use only checked-in
project documentation and the code itself — do not consult LLM-specific
guidance files (e.g. CLAUDE.md, AGENTS.md, .cursor/rules,
copilot-instructions.md).

**Cite drift by symbolic anchor, not by line number.** Use the file
path plus a stable anchor — a section heading (e.g. ``## Architecture``),
a function or class name (e.g. ``apply_finding()`` or
``ConvergenceState``), a constant or method name, or a unique
identifier string. Line numbers drift on every commit; symbolic anchors
stay stable. Quote a line number only as a *secondary* disambiguator
when a symbol genuinely appears more than once in a file (e.g.
``write_plan() at the per-iteration call site in create_plan()``, not
``write_plan() at line 1820``).

For each divergence, identify the **plan-file or detail-file edit**
that would close the gap. The categories below describe what each
finding *is*; use the words informally in your bullet body rather than
as machine tokens.

1. **Files declared but absent on disk.** Either the work was renamed
   or the path was never the right one. Suggest removing the path
   from `step.files` (path-removed) or replacing it with the actual
   path now used (path-rename).
2. **Files present but not declared.** Code exists that the plan
   doesn't acknowledge. Suggest adding the path to `step.files`
   (path-added), or leaving it untracked when it belongs to a
   different step.
3. **Files present but missing pieces the step's detail describes.**
   The code is incomplete relative to the plan's declared intent.
   Because this audit is read-only on code, record the residual gap
   by suggesting a `status` flip (`done` → `current`)
   and writing what's outstanding into the step's optional
   `status_note:` field in the YAML frontmatter. **Do not** suggest
   narrowing the detail's `## Implementation` or `## Acceptance
   criteria` bullets to match the incomplete code — that silently
   rewrites the plan's intent and is the exact failure mode this
   audit exists to prevent.
4. **Files contain *more* than the detail describes.** The work
   over-delivered (or scope crept). Suggest expanding the detail's
   acceptance criteria to capture the additional behavior, or moving
   the extra functionality into a separate step (scope-expansion).
   **Do not** use this to widen criteria for behavior the user
   explicitly scoped out — that's a separate-step concern, not a
   reconcile edit.
5. **Acceptance criteria the code clearly doesn't satisfy.** The step
   shouldn't be marked done. Suggest flipping `status: done` →
   `status: current` and recording what's outstanding in
   `status_note`. Preserve the criterion itself — surfacing the
   gap matters more than hiding it.

Three refusals — these are **not** valid plan edits:

- **No `scope` edits.** Never set a step's `scope` to `deferred` or
  `wont_do` (nor promote one back to `committed`). Scope is a human
  commitment decision — what's in or out of the plan — not something
  reconcile infers from the code. Dependency ordering is already
  encoded in `depends_on`, and the runner skips steps whose
  dependencies aren't done, so a pending step waiting on earlier work
  needs no edit at all. Leave any existing `deferred`/`wont_do` step
  exactly as you found it.

- **No scope-narrowing edits.** If the code falls short of an
  acceptance criterion, the answer is a status flip, not deleting
  the criterion.
- **No criterion-softening edits.** Softening criteria to match an
  incomplete implementation is the exact failure mode this audit
  exists to prevent. Open a follow-up step or flip status instead.

Each finding bullet should carry an inline impact/complexity pair
(e.g. ``(impact: medium, complexity: low)``) so the iteration loop
can triage applies. Ratings:

- **impact**: `low` (cosmetic), `medium` (real but non-load-bearing
  gap), `high` (load-bearing correctness problem).
- **complexity**: `low` (one-line/one-field edit), `medium`
  (multi-line within one section), `high` (multi-section or
  multi-file, or cross-step coupling).

When complexity strictly exceeds impact, the apply is deferred --
the cost isn't worth the payoff for an automated pass. Rate
honestly; findings without an impact/complexity tag fall back to
"apply every finding" (no harm done, but the short-circuit only
kicks in when you emit the tags).

## Output contract

Produce a brief reconciliation report with three sections:

- **Matches intent** — files that do implement the step as described.
  No plan edit needed.
- **Plan over-promises** — places the plan declares more than the code
  delivers. Each item names the plan field to adjust.
- **Plan under-describes** — code that exists but isn't represented in
  the plan. Each item names what to add to the plan.

End your response with a `## Findings` block listing one bullet per
proposed edit, prefixed with a severity token (`CRITICAL`, `HIGH`,
`MEDIUM`, or `NIT`). The block is machine-parsed — keep it as the
final section.

State each bullet's prose as the **drift**: the subject (the plan field,
section, criterion, or `file:symbol`) and the owning step, what diverged
from the code on disk, and the consequence. Then, between the prose and
the inline `(impact: …, complexity: …)` pair, append the remediation in
the exact form `→ fix: <one-line plan/detail edit>`. The walk shows this
to the operator as "what apply will do" and feeds it to the apply as the
targeted edit, so state the concrete plan/detail edit that closes the
drift — a `step.files` change, a `status`/`status_note` flip, a criterion
to add — in one line, not a diff or a multi-step procedure.

**Every bullet must be an actionable plan/detail edit.** Do not emit
confirmations ("no change needed", "step is correct"), defensive
constraints ("keep X byte-for-byte; do not narrow"), or "this is a
false positive" notes as findings — they become non-actionable items
the operator must read past on every walk. Put any such observations in
the prose report above; the `## Findings` block is only for edits to
make. If there are none, use `_(none)_`.

${findings_response_format_block}

Replace the empty marker with severity-prefixed drift-and-remediation bullets
when the plan or detail needs an edit.

## Writing style (strict)

Findings are re-read on every reconcile, walk, and CI gate, and the
operator triages each one against `(a)pply / (s)kip` from the prose
alone — keep them tight *and* self-contained.

- **Lead with the concrete subject and name the step.** Open with the
  thing the operator acts on — the plan field, section, criterion, or
  `file:symbol` — and name the owning step by id and title (e.g. "step 3
  ('persist the cache')"). The walk clips your first line into the
  finding's title and shows the step number but not its title, so an
  opening like "The detail says…" or a bare "a criterion" yields a title
  that names nothing actionable. Lead with the subject, not the plan's
  framing of it.
- **Make each finding decidable on its own.** State what the plan
  declares, how the code on disk diverges, and the consequence —
  concretely enough that the operator can choose apply-or-skip without
  re-reading the plan. Don't force the reader to resolve a back-reference
  ("that criterion", "the section above") to recover the subject.
- **One finding per bullet; two or three sentences if that is what it
  takes to state subject + drift + consequence — but no padding.** Split
  a multi-issue finding into separate bullets.
- **Active voice, imperative mood.** "Drop `foo.ts` from step.files"
  not "It may be advisable to drop `foo.ts`".
- **No historical narration.** Don't write "previously the step
  declared X", "used to live at Y", or parenthetical asides like
  "(was: the old flag)". State the proposed forward state and
  cite the current code with a symbolic anchor.
- **Strip filler** — "it is worth noting that…", "in this case…",
  "this means that…". Cut to substance.
${lessons_section}
