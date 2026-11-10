# Implementation detail for step ${step_id}: ${step_title}

You are drafting a per-step implementation detail file for the plan
**"${plan_title}"** (status ${plan_status} · priority ${plan_priority}).

**Audience: a developer who will implement this step.** They have the
plan's frontmatter, the file list below, and (if you write it well)
your detail file. **Aim for intent over mechanics:** pin down what must
be true when the step is done and recommend an approach, but leave the
exact code to the implementer — real development rarely follows a
line-by-line script, and an over-specified detail file goes stale the
moment reality diverges. Be grounded, not prescriptive: don't invent,
and cite specific file paths and **symbolic anchors** — function names,
class names, section headings, constants, or unique identifier strings —
as orientation for where the work lives, not a mandate to reproduce them
verbatim (e.g.
``apps/foo.ts:handleSubmit()``, ``plan_tool/cli.py:cmd_create``,
``review.py: BLOCKING_SEVERITIES constant``). **Always write file
paths in full from the repo root** — ``amplify/bedrock/chat-agent/agent.py``,
never a partial ``chat-agent/agent.py`` or bare ``agent.py``. Partial
and basename-only paths get flagged downstream as stale/typo
references against the step's declared paths and add validation noise.
Line numbers drift on
every commit and are the single biggest source of churn findings when
the reconcile audit runs later; **do not cite raw line numbers as the
primary anchor**. If a symbol genuinely appears more than once in a
file, use the surrounding context as the disambiguator (e.g.
``the per-iteration apply_finding call in cmd_completeness``) rather
than quoting a line range.

${project_context_block}${risk_context_block}## Step

**${step_id}. ${step_title}** (complexity: ${step_complexity})

depends_on: ${step_depends_on}

### Files in scope

${step_files_block}

### Current file contents

${files_contents_block}

### Existing sibling detail files (tone/structure reference)

${sibling_details_block}

${prior_body_block}
### Plan-level references (start here for the References section)

${plan_references_block}

### Plan-level guardrails and scope fence (authoritative)

${scope_fence_block}

### Already-implemented signal (deterministic heuristic)

${already_implemented_block}

### Accumulated lessons (from prior `plan-tool reconcile-plan` and `detail` runs)

${lessons_block}

### Signed-off concept scope and current detail deferrals

${concept_scope_block}
${foundational_finds_section}
## Codebase audit (do this first)

The file contents and signals above are a starting point, not the full
picture. Use only checked-in project documentation and the code itself
during this audit — do not consult LLM-specific guidance files (e.g.
CLAUDE.md, AGENTS.md, .cursor/rules, copilot-instructions.md). Before
drafting the detail body:

- Use Grep to find the public symbols you intend to mention in the
  Implementation section. The names and signatures you cite must match
  HEAD, not guesses derived from the title. Cite symbols by name, not
  by line number — line numbers shift the moment any earlier line in
  the file changes, and reconcile will flag the drift on every audit.
- Use Read on sibling files in the same directories as the `files:`
  entries when they're plausibly involved (imports, tests, callers).
  The pre-inlined contents above are truncated — go back to source
  when you need more.
- If the already-implemented signal above flagged any hits, confirm
  them by reading the cited file and decide whether this step is
  partially done. If it is, scope the Implementation section to the
  remaining work and say so explicitly in the Why section.
- Use Glob to locate the matching test file(s) for each `files:`
  entry so the Tests section can reference real paths.
${foundational_audit_directive}
- **Choose shared-location reach from the focused property's semantic need,
  not from its shape.** A shared file, helper, caller count, or
  Foundational-logic relation is evidence to inspect, never by itself a reason
  to widen this focused detail. Choose exactly the smallest applicable route:
  - **Reuse unchanged:** retain a shared owner when its existing contract
    already makes the focused property true; do not make a local copy merely
    to make the plan look self-contained.
  - **Bounded local work:** use a local adapter or additive extension only
    when it preserves existing consumer behavior and current schema
    interpretation, and keep it inside this step's declared scope.
  - **Separate shared work:** when the focused property requires changing
    shared authority, lifecycle, identity, precedence, schema interpretation,
    or existing consumer behavior, leave that work out of this focused
    implementation and identify it as separate intentional work in the
    existing `## Deferred` channel. Do not add a plan step, durable handoff,
    or shared-work mechanism here.

Do not narrate the audit in the response — let the symbolic citations
in the body show that you did the work.

## What to produce

Respond with the markdown body followed by the structured deferral envelope
specified below. No fences, preamble, or closing remark. The first character
of your response must be `#`. plan-tool writes only the Markdown portion. If
you genuinely cannot avoid adding text before or after the file (or wrapping
it in a fence), bracket the file exactly between two lines, each used exactly
once and alone on its own line — `<!-- plan-tool:detail-response-start -->`
before the `#` title and `<!-- plan-tool:detail-response-end -->` immediately
after the last line of the file, before the deferral envelope (which always
comes last, after the end marker, never inside it); only the content between
the two markers is read.
${output_path_block}

Required structure (top-level headings, in this order):

The line immediately after the H1 is reserved for plan-tool's own
`plan-tool:detail-format-version` marker — plan-tool stamps it there after
your response is parsed, replacing anything found in that slot. Leave that
line blank; do not write a `plan-tool:detail-format-version` comment
yourself. `## Summary` is the first heading you write.

```
# Step ${step_id} — <one-line title>

## Summary

3-5 sentence overview written for a reviewer skimming the file. State
what the step does, the primary files affected, the most important
design decision, and the observable result on green. No motivation
prose here — save the "why we're doing this" for the Why section.
This is the elevator pitch a reviewer reads before deciding which
sections to drill into.

## Table of Contents

Bulleted list of every H2 in this file, in document order, each line
formatted `- [<Section name>](#<anchor>) — <one-line blurb>`. The
anchor is the GitHub-style slug of the section name (lowercase, spaces
→ hyphens, punctuation dropped — e.g. `## Acceptance criteria` →
`#acceptance-criteria`). The blurb tells the reviewer what they'll
find in that section in plain language. Include every required H2
listed below plus any optional sections (References, Deferred) you
actually emit. Skip ToC entries for sections you omit.

## Why

One paragraph: motivation in the codebase's terms. What's broken /
missing / unclear today, why fixing it matters now.

## Files (creates vs edits)

Two bullet lists:
- **New files:** paths the step creates.
- **Existing files (edits only):** paths the step modifies. List the
  specific edits per file.

## Implementation

Describe the **intended change and a recommended approach to get there** —
what should be true when the step is done, and a path a developer can
adapt as reality demands. Name the real files and symbols involved so the
reader knows where to work, but don't script every line: the implementer
owns the exact code.

Cover, grounded in real anchors:
- what behavior changes, and the shape of the approach — the key design
  decision and the main alternative you rejected
- the files and public symbols the change touches, and the call sites
  that likely need updating
- the constraints and gotchas a developer must respect — the parts that
  are *not* free to vary (a required signature, an ordering that must
  hold, an invariant to preserve)

This is the most important section. Be concrete about **what** must hold
and **why**; leave room on the **how**. Prescribe an exact mechanism only
where it is genuinely the constraint, not as the default — and when you're
recommending rather than requiring, say so ("one way: …", "likely …") so
the developer knows where they have latitude.

## Tests

What test cases cover this step. Reference test file paths. Each test
case is one line: `<test name> — <what it asserts>`. Don't write code
— just enumerate.

For any invariant or gotcha named in `## Implementation` — a required
precedence, a guarantee that looks avoidable, a contract that must omit
something rather than null it — name and describe its test case so the
intent is explicit in the name/assertion itself, not just the code path
it happens to exercise (`test_context_is_copied_and_cannot_override_event_identity`,
not `test_emit_extra`). A later audit checks this exact test file before
flagging that behavior as a defect; it can only tell deliberate from
broken if the test states which one it is.${change_type_directive_block}

## Acceptance criteria

Bulleted list of observable behaviors:
- function returns X for input Y
- test Z passes
- DB column W exists with type V

Not "code is clean" or "docs are good". Things a CI bot or a reviewer
could check.

## References

Start from the **Plan-level references** block above when one is
provided — those are the curated authoritative docs the plan author
already collected. Keep the subset directly relevant to *this step's*
files / surfaces, drop the rest, and only web-search for additional
references when the plan-level list leaves a gap for this step
(e.g. a step-specific SDK or RFC the plan didn't cover). When the
plan-level block is `_no plan-level references available_`, web-search
from scratch.

Bulleted list of links, each line: `- [<title> — <one-sentence
note on what to read it for>`. Prefer official vendor docs and primary
API references over blog posts, tutorials, or Q&A threads. Omit the
section entirely (don't emit `## References` at all) if no good
references exist for this step.

## Applicable guardrails

When one or more **Plan-level guardrails and scope fence** entries above bind
this step, emit this section. For each entry, **name it and state the boundary
it imposes on this step's files or behavior** — that step-specific consequence
is the whole reason the section exists.

**Reference the constraint; do not reproduce its text.** Cite it by its plan
section plus a short label — `the plan's "## Out of scope", allowed behavior
changes` — rather than quoting the plan's wording. A quoted clause is a copy
that goes stale the moment the plan is edited, inside a file that had nothing
to do with that edit; a reference cannot go stale. Never weaken, reinterpret,
or add a constraint.

**State the boundary without restating the constraint's specifics.** Say what
*this step* may or may not do; do not carry over counts, enumerations, or exact
wording, because those are what drift. Where a constraint enumerates, point at
the plan's list instead of copying it — "only the templates the plan's fence
names", never "only the four templates". The specifics live in one place and
the reader can follow the citation to them.

Omit this section entirely when no guardrail or fence entry applies. Include a
Table of Contents entry when you emit it.

## Deferred

Bulleted list of explicitly out-of-scope items. Things a reader might
expect to be covered but aren't. Each line: `<item> — <reason or
follow-up tracking>`. Every signed-off concept named here must use its exact
stable concept ID from the concept-scope block and must also appear in the
structured envelope. Free-form follow-up work may remain prose but must not
invent a concept ID.
```

After the Markdown, always emit exactly this transport envelope, including an
explicitly empty list when the body defers no signed-off concept:

```
<!-- plan-tool-detail-deferrals
{"deferrals":[{"concept_id":"<stable 64-character concept ID>","step_id":${step_id}}]}
-->
```

Each object must contain exactly `concept_id` and `step_id`; preserve the
concept order shown above, never substitute a title for an ID, and never link
a concept owned by a different step. Do not add this envelope to the Table of
Contents or discuss it in the Markdown body.

Optional conditional section: emit `## Input` only when this step consumes an
existing data structure, persisted schema, API surface, saved audit, output
format, or dependency-step output whose shape affects correctness. Place it
near the design context, usually after `## Why` and before `## Files`, and list
what contract the step reads, which fields or code locations it depends on, and
what limits apply to verifying it. When the input comes from another plan step,
cite the owning step id and outcome (for example, "step 1 produces the drift
audit JSON") instead of restating that step's implementation details. Include a
Table of Contents entry when you emit the section; omit both the section and
the ToC entry when the step has no contract input.

## Constraints

**Smallest proof first.**

Before expanding this step, trace its shortest concrete path through existing
code to the required observable result. Prefer unchanged reuse, a direct call
or a fixed check. For every new abstraction, process boundary, persisted record,
lifecycle or configuration surface, identify the current requirement that fails
without it and the code or platform evidence that rules out the narrower path.
Future reuse, symmetry and generic robustness are not evidence. Unknown facts
remain explicit uncertainties, not permission to build both possible designs.
Keep required safety, compatibility, authority and audit properties and explicit
owner choices intact. If the approved contract itself prevents a smaller proof,
surface that scope decision; do not silently weaken it. Put this reasoning in
the existing Implementation section; do not add a required artifact or section.

- **Treat every author-supplied plan guardrail above as a constraint on this
  step.** Do not relax, contradict, replace, or silently omit it while
  translating the plan into implementation detail. Apply only the portion that
  bears on this step; do not invent a new guardrail when the block is empty.
- **Keep the detail proportional to the plan.** Do not turn a useful adjacent
  capability, generalization, or cleanup into this step's work merely because
  it is nearby. Include it only when the step's stated outcome, acceptance
  criterion, or invariant cannot hold without it; otherwise retain the plan's
  boundary and defer it through the plan's existing process.
- **Do not mistake sharing for shared semantic reach.** Follow the semantic
  reach decision in the codebase audit above; a common path, helper, or sweep
  finding cannot override this step's scope fence.
- **Same axis, aimed at the mechanism instead of the boundary: over-building
  what was asked for is scope creep too.** Implement the smallest thing
  that satisfies this step's acceptance criteria — a fixed check over a
  rule engine, one direct call over a pluggable interface, a literal over
  a config knob — even when the more general version stays on-topic for
  the step. Escalate to it only when an acceptance criterion or invariant
  cannot hold under the narrow version.
- Stay within the step's declared `files:` list unless adding a file
  is genuinely required by the step. Note any additions explicitly.
- Don't propose schema changes that aren't already in the plan's
  frontmatter — those need plan-level decisions first.
- If `depends_on` lists upstream steps, reference their numbers when
  describing how this step builds on them.
- **Every file your body claims this step writes must be in the
  declared `files:`/`creates:` set.** If the Files, Implementation, or
  Acceptance sections say the step creates or edits a path, that path
  must appear in the step's frontmatter file list — add it (and note
  the addition) or drop the claim. A write claimed in the body but
  absent from the file list reads downstream as an un-operationalized
  concept and gets flagged.
- **`## Deferred` must not contradict the rest of this file.** Deferred
  lists only work this step does *not* do. Never defer something the
  Summary, Files, Implementation, or Acceptance sections say the step
  *does* — a line that is both an acceptance criterion and a Deferred
  item is a self-contradiction the conceptual audit flags on every run.
  When a fact moves into scope during iteration, delete its Deferred
  bullet in the same edit, and sweep the file for any older phrasing
  that still frames the now-in-scope work as deferred or "out of scope".
- **Reference a fact another step owns; don't restate its mechanism.**
  When this step depends on an artifact a sibling produces (a seeded
  row, a shared helper, a schema field), cite it by owning step id and
  outcome ("step 3 seeds the `LEARNING` row") rather than re-specifying
  how that step does it. A restated mechanism goes stale the moment the
  owner is edited, and the divergence surfaces as a contradiction.
- When sibling detail files are present above, match their tone and
  section conventions. When they aren't, set the conventions yourself
  for future siblings to follow.
- Prefer concrete quantities (byte counts, test counts, iteration
  caps) over vague intensifiers ("a lot", "complicated"). When you
  don't know a number, say so explicitly: "(approx. N tests)" beats
  "many tests". Do **not** include line ranges in the count: cite the
  symbol by name (function/class/section) and let the reader find it
  fresh from HEAD.
- When you name new symbols or concepts, choose intuitive,
  self-descriptive names a reader grasps without a glossary (prefer
  `multi_plan_split` over `decomposition`; directional names like
  `skip_below_bytes`, not an ambiguous `skip_bytes`).

## Writing style (strict)

This file is re-read by future agents on every reconcile, review, and
run — token cost compounds. Apply these rules; deviations get flagged
by the detail-quality review.

**Plain language is the top rule — write it the way you'd say it out
loud to a teammate.** A detail file is instructions for another
engineer, not an essay. If a phrase sounds clever, abstract, or
academic, rewrite it plainer. The rules below all serve that goal.

- **Use plain, everyday words — this is what readers notice most.**
  Write so a competent engineer who is new to this codebase gets it on
  the first read, without a dictionary. Swap any decorative or unusual
  word for the common one that means the same thing:
  - "key" / "most important" — not "load-bearing"
  - "unchanged" / "the same" — not "byte-identical"
  - "left out" / "dropped" — not "elided" / "elision"
  - "covers" — not "spans its footprint"
  - "points to a real X" — not "resolves"
  - "stop early" / "skip the rest" — not "short-circuit"
  - "falls back to the next level" — not "falls through" / "fall-through"
  - "approach" / "stance" / "rule" — not "posture" / "tenet"
  - "splits by kind" — not "kind-dispatch"
  - "always true, so it can never fail" — not "vacuous"
  - "true by definition" — not "tautological"
  - "nothing could prove it wrong" — not "unfalsifiable"
  - "by the way it is built" — not "by construction"
  - "independent" / "unrelated" — not "orthogonal"
  - "level of detail" — not "altitude"
  - "one call that runs several checks" — not "fan-out"

  Rule of thumb: if you wouldn't say the word aloud explaining the step
  to a teammate, replace it. Keep the exact technical identifiers a
  reader needs — type, field, flag, and library names, plus named
  project concepts like "leaf module" — only swap out decorative
  wording, never the precise terms.
- **Default to bulleted lists** for options, conditions, behaviors,
  gotchas, or steps. Prose blocks longer than ~5 lines are a smell.
- **Lead each bullet with the rule or fact**, then the explanation
  (bold the key term when it helps scanning).
- **Active voice, imperative mood.** "Use X when…" not "X may be used
  when…". One thought per bullet — split if it runs over two
  sentences. Prefer short, direct sentences over long ones stacked with
  clauses and dashes.
- **Lock modal verbs to one meaning each** in `## Acceptance criteria`,
  `## Implementation` guarantees, and `## Constraints`: `must` = a hard
  requirement, `must not` = a hard prohibition, `may` = explicitly
  optional/permitted, `can` = a capability that exists. Never write
  `should`, `shall`, or `will` to state an obligation — none of the three
  says whether it's required or merely recommended, so a reviewer or a
  later audit can't tell either.
- **No historical narration.** Describe the desired forward state.
  Drop sentences starting with "previously", "used to", "the previous
  version", "this was changed because", and parenthetical asides like
  "(was: X)". Git history captures what changed.
- **Strip filler.** Cut "it is worth noting that…", "in this case…",
  "this means that…". Get to the substance.
${purity_self_check_block}
