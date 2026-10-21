# Distill lessons from this detail-drafting run

You just drafted the implementation detail for step **${step_id}.
${step_title}** of plan **${plan_title}**. Your job now is to look back
at what you had to do during that drafting — what the create step got
right, what it got wrong, what you had to discover the hard way, what
shortcut would make future runs more efficient — and extract
**lessons-learned** that will make future `plan-tool create`,
`plan-tool detail`, and `plan-tool reconcile-plan` runs more correct and
complete — *with less effort than this run required*.

The scope is broader than "what create got wrong". Capture any takeaway
that future runs would benefit from, including:

- Patterns in how the codebase is structured (where related code lives,
  how features are wired together) that the create-time codebase audit
  missed.
- Conventions that the detail should have applied from the start (e.g.
  always cite the test file path next to the source file path).
- Failure modes you noticed in the heuristic / create proposal that
  weren't worth blocking on but should inform future complexity ratings
  or step decomposition.
- Tooling or library quirks specific to this codebase that future
  detail / review calls should treat as load-bearing.

Two destination files:

- **General lessons** → `.agents/skills/plan-tool/lessons/general.md`
  (lives with the skill). Generalizable plan-authoring rules that apply
  regardless of project domain.
- **Project lessons** → `.plan-tool/lessons/project.md` (lives with the
  codebase). Facts about *this* codebase that future plans should treat
  as load-bearing.

## Existing lessons (do NOT duplicate)

${lessons_block}

## Original step proposed by `plan-tool create`

- **id:** ${step_id}
- **title:** ${step_title}
- **complexity:** ${step_complexity}
- **files:** ${step_files_inline}
- **depends_on:** ${step_depends_on}

## Already-implemented signal that was passed in

${already_implemented_block}

## Detail body you just produced

${detail_body_block}

## What to produce

Return **only** a JSON object of the shape:

```json
{
  "general": [
    {
      "rule": "<one-line takeaway>",
      "why": "<short reason>",
      "example": "<optional concrete pointer>",
      "surface": "<one of: create-heuristic | detail-authoring | review-heuristic | cross-step | domain-shape>",
      "trigger": "<one-line predicate: when does this rule apply?>"
    }
  ],
  "project": [
    {"rule": "...", "why": "...", "example": "...", "surface": "...", "trigger": "..."}
  ]
}
```

Either array may be empty when no new lesson belongs in that bucket.
Return `{"general": [], "project": []}` when the run produced nothing
worth capturing — this is a perfectly valid outcome for a step where
create's proposal was accurate and detail-drafting was straightforward.

## Surface tags (controlled vocabulary)

`surface` declares **where this lesson should be injected at prompt
time** — not what the lesson is about. Pick exactly one of the five.

The list is a hybrid: three tags are aligned to the three plan-tool
commands that inject lessons today (`create`, `detail`, `review`),
and two tags are cross-cutting clusters that span multiple commands.

**Command-aligned surfaces** (the lesson primarily improves one
command's prompt):

- `create-heuristic` — rules about what `plan-tool create` should
  propose: file lists, complexity floors, `depends_on` propagation,
  step decomposition. Example: *"steps that introduce a new DB model
  + new Lambda + new shared util are L-complexity minimum, never
  unknown."*
- `detail-authoring` — rules about what `plan-tool detail` should
  produce in the detail file: acceptance-criteria shape, sibling-
  template citation, Deferred bullet patterns, file:line anchoring,
  test-section structure. Covers both `detail.md` (initial drafting)
  and `detail-quality.md` (the critique pass) — same artifact, two
  prompts. Example: *"detail must cite the sibling feature folder
  by file:line as the layout template before authoring the new step."*
- `review-heuristic` — rules about what `plan-tool reconcile-plan` should
  flag, suppress, or roll up: false-positive filters, stub-plan
  collapsing, sentinel-value handling. Example: *"single-token
  matches on common English words in unrelated docs are noise; require
  ≥2-token overlap or a code-side match."*

**Cross-cutting surfaces** (the lesson applies during multiple
commands; forcing it into one command's bucket would miscategorize):

- `cross-step` — rules about how steps hand off to each other:
  deferred-bullet contracts, stub-replacement obligations, frozen-
  artifact `git diff` invariants, citing prior-step placeholders by
  file:line. Apply during detail (authoring the consuming step) AND
  review (checking the handoff closed). Example: *"when step N
  intentionally leaves stubs for step N+1, step N+1's detail must
  enumerate the stub locations and assert their removal."*
- `domain-shape` — rules that classify a step by shape (UI-feature,
  schema-definition, infra-wiring, migration, operability,
  retention/policy) and dictate files/complexity/test patterns for
  that shape. Apply during create (set complexity floor and propose
  skeleton), detail (mirror the shape's conventions), and sometimes
  review (flag shape-vs-content mismatches). Example: *"UI-feature
  steps that span web + mobile + shared library are L-complexity
  minimum and never `files: []`."*

**Choosing well:** if the lesson is mostly about one command's
output, pick that command's tag. If it's about handoffs between
steps or recognizing step shapes, pick the cross-cutting tag. If
unsure, omit `surface` (empty string) — better empty than
miscategorized. Untagged bullets are kept but treated as "inject
everywhere" until a future pass classifies them.

## Trigger predicate

`trigger` is a short "when X" clause that tells the future loader
when this rule matches. Examples:

- `"when create proposes files:[] for a step whose title contains
  'logging', 'alarm', or 'instrumentation'"`
- `"when detail introduces a new helper module alongside an existing
  sibling module of the same shape"`
- `"when review fires a single-token match on a generic project doc"`

Triggers don't need to be machine-parseable yet — they're free-form
prose now and will inform the controlled trigger vocabulary later.
Skip when you can't write one without redundantly restating the rule.

## Guidelines

- **Generalize.** "Step said `files: [foo.ts]` but I had to read
  `foo.test.ts` and `bar.ts` to write the Tests section" → general
  lesson "create-time codebase audit should glob for `*.test.*` siblings
  of every proposed file".
- **Skip the obvious.** Don't capture rules already implicit in the
  tool's prompts.
- **Don't repeat existing lessons.** Re-read the "Existing lessons"
  block above. Substring matches are deduped at append time anyway.
- **Don't over-claim.** A single run is one data point. If a candidate
  rule rests on this run alone and might just be project-specific
  noise, file it under project (not general).
- **Tag honestly.** A miscategorized `surface` is worse than a missing
  one — the loader will inject it into the wrong command and waste
  context. If unsure, omit.
