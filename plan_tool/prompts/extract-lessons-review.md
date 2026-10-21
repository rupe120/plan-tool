# Distill lessons from this review

You just produced a `plan-tool reconcile-plan` report for plan **${plan_title}**
(slug `${plan_slug}`). Your job now is to read the findings and extract
**lessons-learned** that will make future `plan-tool create`,
`plan-tool detail`, and `plan-tool reconcile-plan` runs more correct and complete
— *more efficiently* than re-discovering the same issue from scratch.

There are two destination files:

- **General lessons** → `.agents/skills/plan-tool/lessons/general.md`
  (lives with the skill). Generalizable plan-authoring rules that apply
  regardless of the project's domain. Example: *"When a step proposes
  modifying a function, grep for the function name to confirm it exists
  before drafting detail."*
- **Project lessons** → `.plan-tool/lessons/project.md`
  (lives with the codebase). Facts about *this* codebase that future
  plans should treat as load-bearing. Example: *"AppSync auto-generated
  subscriptions only fire on mutations routed through AppSync resolvers;
  direct DynamoDB writes bypass them."*

## Existing lessons (do NOT duplicate)

${lessons_block}

## Findings from this review

${findings_block}

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
Return `{"general": [], "project": []}` when the findings produced
nothing worth capturing.

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

**Choosing well:** if the finding pinned one command's output as the
problem, pick that command's tag. If it pointed at a handoff that
didn't close or a step whose shape was mis-recognized, pick the
cross-cutting tag. If unsure, omit `surface` (empty string) — better
empty than miscategorized. Untagged bullets are kept but treated as
"inject everywhere" until a future pass classifies them.

## Trigger predicate

`trigger` is a short "when X" clause that tells the future loader
when this rule matches. Examples:

- `"when create proposes files:[] for a step whose title contains
  'logging', 'alarm', or 'instrumentation'"`
- `"when review fires a single-token match on a generic project doc"`
- `"when a finding flags a TODO marker in a step's source file"`

Triggers don't need to be machine-parseable yet — they're free-form
prose now and will inform the controlled trigger vocabulary later.
Skip when you can't write one without redundantly restating the rule.

## Guidelines

- **Treat finding confidence as evidence support only.** A
  `confidence: supported`, `confidence: limited`, or `confidence: unknown`
  label may qualify the evidence support of a synthesized lesson, but never
  weaken, reclassify, or suppress the source finding.

- **Generalize.** A finding like "step 3's `files:` lists a typo'd
  path" becomes the general lesson "verify every declared path exists
  under repo root before proposing a step". Project-specific findings
  ("the AppSync schema is at `amplify/data/schema/misc.ts:48`") become
  project lessons.
- **Skip the obvious.** Don't capture lessons that are already implicit
  in the tool's prompts (e.g. "respond in JSON"). Capture *the part the
  tool didn't already know to ask for*.
- **Don't repeat existing lessons.** Re-read the "Existing lessons"
  block above. If a candidate rule's text already appears (even
  loosely), skip it. The append-time dedupe will drop substring matches
  anyway, but you'll save a wasted bullet by checking now.
- **Prefer fewer, sharper rules** over many vague ones. One precise
  lesson beats five fuzzy ones.
- **Don't over-claim.** If the review surfaced one finding, you may not
  have evidence for a general rule yet — return an empty list for the
  bucket you can't support.
- **Tag honestly.** A miscategorized `surface` is worse than a missing
  one — the loader will inject it into the wrong command and waste
  context. If unsure, omit.
