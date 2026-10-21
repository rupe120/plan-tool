# Reconcile code vs plan/detail — step ${step_id}: ${step_title}

Plan: **${plan_title}** · step ${step_index} of ${step_total}

The **plan file and this step's detail are canonical**. Your job is to
propose edits to the **code files** so the implementation matches what
the plan and detail describe. **Do not modify the plan file or any
detail file.** Code edits only — the files you MAY edit are the ones
declared in this step's `step.files` (or their close neighbors when the
declared path is stale) that are *not* the plan and *not* a detail
file. The direction of truth is fixed by how this audit was invoked.

If a divergence's root cause is in the plan itself (a stale path, a
wrong acceptance criterion, a missing detail section), do **not**
silently invent a code edit to paper over it — emit the
refuse-and-redirect signal described under `## Refuse-and-redirect
signal schema` below and let the operator re-route the audit.

## Step context

${step_detail}

${completed_sibling_context}

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
layer handle the scope question.

When the completed-sibling ownership block appears in `## Step context`,
its ownership rule takes priority over this cross-cutting instruction: an
otherwise out-of-footprint sibling-owned path is context only, never a
removal recommendation or selected-step drift. Shared selected-footprint
paths remain eligible for normal selected-step findings.

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
when a symbol genuinely appears more than once in a file.

For each divergence, identify the **code edit** that would close the
gap. The categories below describe what each finding *is*:

1. **File declared in `step.files` is absent on disk.** Create the
   file with the implementation the plan describes.
2. **File declared but missing pieces the detail's `## Implementation`
   describes.** Add the missing pieces.
3. **File present but its public symbols / behavior diverge from the
   detail.** Align the code with the plan's stated intent.
4. **File over-delivers** (more exports or behavior than the plan
   describes) but the extras are unwanted. Trim back to plan scope.
5. **Plan-rooted gap.** The divergence's root cause is in the plan
   itself — `step.files` lists a stale path, an acceptance criterion
   contradicts the implementation's stated intent elsewhere, or the
   detail's `## Implementation` section is missing the guidance a code
   edit would need. Emit the refuse-and-redirect signal described
   below and do **not** propose a code edit for that finding.

**Before proposing a category-3 edit, check the mirrored test file**
(`tests/test_<module>.py` for `plan_tool/<module>.py`) for an assertion
that already pins the current behavior. A passing test proving the
current behavior is deliberate is evidence the *plan text* is what's
stale, not the code — route that case through category 5 (`##
Redirect`) instead of a code edit. Reading the diff alone can be
internally consistent and still wrong about which side is correct; a
code edit that "fixes" tested, intentional behavior back toward a
stale plan description breaks something real to satisfy something
outdated.

**Report drift at the level of the defect class, not the first file you
noticed it in.** Before writing a finding, check whether the divergence
you found is one instance of something the code gets wrong in more than
one place — a shared predicate updated at one of its call sites, a
contract restated in a sibling module, a rule applied to three of seven
members of a set, a new behavior added with no test obliging it. Two
searches find these and they miss different things: **by identifier**
(the symbol, path, or flag) and **by vocabulary** (the concept's words,
in other phrasings). When the drift is class-wide, write **one** finding
that names every site rather than one finding per site — a finding
scoped to a single file gets applied to a single file, and the next
audit re-derives the same drift at a sibling, which reads as a loop that
will not converge when it is really under-application. Rate its
complexity for the whole sweep, not for the one file.

Each finding bullet should carry an inline impact/complexity pair
(e.g. ``(impact: medium, complexity: low)``) so the iteration loop
can triage applies. Ratings:

- **impact**: `low` (cosmetic), `medium` (real but non-load-bearing
  gap), `high` (load-bearing correctness problem).
- **complexity**: `low` (one-line edit), `medium` (multi-line within
  one function/file), `high` (multi-file or cross-module reasoning).

When complexity strictly exceeds impact, the apply is deferred --
the cost isn't worth the payoff for an automated pass.

## Refuse-and-redirect signal schema

When a finding's root cause lives in the plan, attach a `## Redirect`
sub-block to that finding's bullet. The block sits immediately after
the bullet (separated by a blank line). The `## Redirect` heading must
sit at the start of its line — do not indent it as a list continuation.
Field labels are exact strings; they are machine-parsed.

The schema:

```
## Redirect

- **Reason**: <one sentence on why the plan, not the code, is the wrong piece>
- **Suggested next**: detail --reconcile
```

A finding with a `## Redirect` block must **not** also propose a code
edit in its bullet body — the two are mutually exclusive. The CLI
surfaces a redirect by printing `[REDIRECT]` on stderr (naming
`detail --reconcile`) and returning a non-zero verdict for that
finding without applying anything. Use this signal sparingly — only
when the code is correct (or unambiguously cannot be made correct
without first amending the plan) and the plan/detail is the wrong
piece. If the code is simply incomplete relative to a correct plan,
that's category 1–4 above, not a redirect.

## Output contract

Produce a brief reconciliation report with three sections:

- **Code matches plan** — files that do implement the step as
  described. No code edit needed.
- **Code under-delivers** — places the code falls short of the plan's
  declared intent. Each item names the file and the specific gap.
- **Code diverges from plan intent** — places the code does something
  different from what the plan describes (not just incomplete —
  divergent).

End your response with a `## Findings` block listing one bullet per
proposed edit, prefixed with a severity token (`CRITICAL`, `HIGH`,
`MEDIUM`, or `NIT`). Each plan-rooted finding is followed (after a
blank line) by its `## Redirect` block. The block is machine-parsed —
keep it as the final section.

Between the finding prose and the inline `(impact: …, complexity: …)`
pair, append the one-line remediation in the exact form
`→ fix: <one-line code remediation>` — the concrete code edit that
closes the gap, named at the `file:symbol` level. The walk surfaces it
to the operator as the finding's suggested fix, so state the intent of
the edit in one line (e.g. `→ fix: call validateForm() before the
dispatch in handleSubmit()`), not a diff or a multi-step procedure. A
**redirect** finding carries no code edit and therefore **no `→ fix:`
line** — the `## Redirect` block stands in its place.

${findings_response_format_block}

Replace the empty marker with severity-prefixed code-edit or redirect bullets
when the plan and code diverge.

## Examples

A code-edit finding (no redirect — the plan is correct, the code is
incomplete):

```
- HIGH: `handleSubmit()` in `apps/foo.ts` (step 2 "wire submit
  validation") dispatches before the validation step the detail's
  `## Implementation` section requires, so invalid payloads reach the
  store unchecked → fix: call `validateForm()` ahead of the dispatch in
  `handleSubmit()` (impact: high, complexity: low)
```

A redirect finding (the plan is wrong; refuse the code edit and
re-route the operator):

```
- MEDIUM: `apps/old-foo.ts` declared in step 2's `step.files` does not
  exist; `apps/foo.ts` is the actual location of `handleSubmit()` and
  fulfills the detail's intent, so the code is correct and the plan path
  is stale (impact: medium, complexity: low)

## Redirect

- **Reason**: step.files declares a stale path; the code is correct, the plan needs a path-rename edit
- **Suggested next**: detail --reconcile
```

A mixed `## Findings` block can contain both kinds of bullets — each
`## Redirect` block attaches only to the bullet immediately above it.

## Writing style (strict)

Findings + redirect text are re-read on every reconcile, walk, and CI
gate, and the operator triages each one against `(a)pply / (s)kip` from
the prose alone — keep them tight *and* self-contained.

- **Lead with the concrete subject and name the step.** Open with the
  `file:symbol` that diverged, and name the owning step by id and title
  (e.g. ``handleSubmit() in apps/foo.ts (step 2 "wire submit
  validation")``). The walk clips your first line into the finding's
  title and shows the step number but not its title, so an opening like
  "The detail says…" or a bare "a function" yields a title that names no
  code — lead with the symbol, not the plan's framing of it.
- **Make each finding decidable on its own.** State what the code does
  now, the plan intent it diverges from, and the consequence — concretely
  enough that the operator can choose apply-or-skip without re-reading the
  plan. Don't force the reader to resolve a back-reference ("that
  behavior", "the section above") to recover the subject.
- **One finding per bullet; two or three sentences if that is what it
  takes to state subject + drift + consequence — but no padding.**
- **Active voice, imperative mood.** "Add validation in
  `handleSubmit()` before dispatch" not "It might be a good idea to…".
- **No historical narration.** Don't write "previously", "used to",
  "this was changed because", or parenthetical asides like
  "(was: X)". State the current code state with a symbolic anchor
  and the desired forward state.
- **Strip filler.** Cut "it is worth noting that…", "in this case…",
  "this means that…".
${lessons_section}
