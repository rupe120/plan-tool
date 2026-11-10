# Synthesize plan body sections from existing seed prose

You are being called by `plan-tool create --from-existing` to read a free-form
seed document and emit the canonical H2 body sections a new plan file needs.
Your output populates the entries of `PLAN_BODY_SECTIONS` defined in
`plan_tool/create.py` — every section except `Steps` (covered by a separate
round-trip that maps `### N.` headings to the frontmatter `steps:` list) and
`References` (covered by a separate web-research round-trip). Do not emit
those two keys; they are owned elsewhere.

${project_context_block}## Source seed

```
${source_text}
```

## Reference documentation

Text extracted from the authoritative documentation URLs gathered for this plan.
Use it to **ground** the sections you synthesize: you may draw concrete facts from
it — API/method names, parameters, defaults, constraints, version requirements,
error semantics — when they make a section more accurate or actionable. This is
context, not a section to summarize: pull in only what a section the seed already
motivates actually needs, and do not invent sections, risks, or scope the seed
does not raise just because the docs mention them. When this block says "None
fetched", synthesize from the seed and any local repository evidence below.

${reference_docs_block}

## Smallest proof first

In Architecture, identify one concrete end-to-end proof using existing commands,
owners and platform behavior before describing new machinery. Each added
abstraction, process boundary, persisted record, lifecycle or configuration
surface needs a current requirement that fails without it and a concrete reason
unchanged reuse or a direct call cannot meet that requirement. Future reuse,
symmetry and generic robustness do not establish necessity. Keep required
safety, compatibility, authority and audit properties intact. Preserve explicit
owner choices; surface an oversized fixed step-list for owner review rather
than inventing justification or silently changing it. Use existing sections and
response keys, not a new proof document or framework.

## Dependency cohesion

This plan's steps are already fixed. These `depends_on` edges connect two
steps whose declared `files`/`creates` share no production source file —
nothing else in the plan's frontmatter backs the claim that they are
related, so they are the claims most worth checking against the evidence
below before any other Architecture claim. If `## Architecture` in the seed
explains what the dependent step actually consumes from the antecedent,
verify that explanation against the local repository code below and keep it;
if it does not explain the connection, do not invent one — leave the gap for
a human reviewer rather than authoring a justification the seed never gave.

${dependency_cohesion_block}

## Local repository code

This contains bounded excerpts for inline symbolic anchors the seed explicitly
names in its `## Architecture` section. It is the authoritative source for
claims about those existing mechanisms. Use it to check each named anchor
before writing Architecture, Risks, or Testing; do not widen this into a
repository review or infer behavior from files the seed did not name.

${local_code_context_block}

## Required local code citations

When an anchor is listed here, it resolved to exactly one repository
declaration. Preserve every listed `path:symbol` anchor verbatim in the
generated `Architecture` value so a reader can trace the claim to its source.
An ambiguous or unresolved block above has no citation requirement: do not pick
one of its look-alikes.

${local_code_anchor_requirements_block}
${repair_block}

## Section catalog

The keys below are the canonical required body-section keys, plus any
recognized optional section explicitly marked conditional. Each bullet names
the key, a policy tag (`[derive from intent]`, `[evidence-only]`, or
`[conditional]` — see Field rules), and the shape the section should take:

${section_shapes_block}

## What to produce

Respond with **ONLY** a single JSON object — no prose, no fences, no preamble,
no trailing remark. The first character of your response must be `{` and the
last `}`.

```json
{
  "Overview": "<markdown body for the Overview section, or null>",
  "Problem statement": "<markdown body, or null>",
  "Architecture": "<markdown body, or null>",
  "Out of scope": "<markdown body, or null>",
  "Risks": "<markdown body, or null>",
  "Testing": "<markdown body, or null>",
  "Acceptance criteria": "<markdown body, or null>",
  "Deferred": "<markdown body, or null>"
}
```

Key names match `PLAN_BODY_SECTIONS` exactly (case-sensitive — note the
lowercase second word in `Problem statement`, `Out of scope`, and
`Acceptance criteria`). The `Steps` and `References` keys are deliberately
omitted from this object — emitting either is a shape error and the caller
will reject your response.

`Input`, `Scope guardrails`, `Audit guardrails`, `Expected placement`, and `Stack` are
the only recognized optional keys. Add `"Input": "<markdown body>"` only when
the seed clearly says this plan consumes an existing data structure, persisted
schema, API surface, saved audit, output format, or dependency-step output whose
shape affects correctness. Add each guardrail key only when the seed supplies
its matching H2 heading; preserve that body as a separate section without
rewriting, expanding, or replacing its constraints. Omit optional keys entirely
when their condition is not met; do not return them as `null` just to acknowledge
the rule.

## Field rules

- Each value is either a markdown string or `null`. Strings preserve the
  seed's markdown formatting (bullets stay bullets, paragraphs stay
  paragraphs). Do **not** include a leading H2 line in the value — the
  renderer writes the `## <Section name>` heading itself, so a value
  beginning with `## Overview` would produce a duplicate heading in the
  rendered plan.
- Honor each section's policy tag from the catalog above:
  - **`[derive from intent]`** (Overview, Problem statement, Architecture):
    author these whenever the seed states a goal, even when it carries no
    matching heading. A seed describing *what* to build is the source for its
    Overview; the *why* behind that goal is its Problem statement; the design
    that goal implies is its Architecture. Return `null` only when the seed is
    so empty there is no goal to summarize. Stay grounded — derive what the
    stated work implies; do not invent components, motivations, or scope the
    seed never raises.
  - **`[evidence-only]`** (Out of scope, Risks, Testing, Acceptance criteria,
    Deferred): emit only what the seed, fetched reference docs, or local code
    excerpts directly support, and return `null` otherwise. Do **not** invent
    risks, tests,
    deferred items, scope boundaries, or acceptance criteria to fill an empty
    section. A fabricated value here is worse than `null` — the downstream
    conceptual audit treats an invented criterion or aspirational risk as a
    real commitment. For these sections, when in doubt return `null`.
- **`[conditional]`** (`Input`, `Scope guardrails`, `Audit guardrails`,
  `Expected placement`, `Stack`): emit `Input` only when the seed names an existing
  contract this plan reads before it writes. Its body should answer what
  existing contract is consumed, which fields or code locations are depended
  on, and what limits apply to verifying that contract. Emit a guardrail key
  only when its matching H2 is supplied, preserving its body verbatim; never
  invent a guardrail or make a new scope, audit, placement, or stack decision.
- **Architecture altitude:** keep `Architecture` at the observable-contract
  level. Retain source- or local-code-supported outer ownership, ordering,
  bypass, terminal, and independently observable handoff claims, along with
  every seed-stated feature outcome the plan supports. Do not promote a guard,
  predicate, accumulator, rebuild, callback, or fixture into Architecture
  merely because an excerpt names it; leave those inner mechanics to detail
  unless the available evidence establishes their own observable contract.
  Do not manufacture a refactor phase map, dependency graph, or phase count
  from source mechanics or `depends_on` cohesion notes: a dependency edge is
  not proof of an ownership boundary, and a conditional branch is not
  automatically independent. Preserve a supported outer boundary even when it
  has no dependency edge.
- **Proportionality:** keep the plan no broader than the seed's intended
  outcome. Do not add a more general abstraction, adjacent workflow, or future
  capability merely because it would be useful; include it only when the
  stated outcome, acceptance, or safety boundary cannot be true without it.
  Otherwise preserve the seed's fence or leave the concern for later review.
- **Mechanism reach:** classify ownership from the seed's focused property,
  not from a shared path, duplicate-looking code, parallel caller, relation
  label, or consumer count. Reuse a current common owner unchanged when its
  existing contract already makes the property true. Otherwise allow the
  smallest local adapter or bounded additive extension that keeps existing
  consumer behavior and schema interpretation unchanged. Otherwise leave a
  required shared semantic change out of the focused plan as separate work.
  An available local adapter does not rule out a compatible bounded additive
  extension, and common ownership does not require a local duplicate when
  unchanged reuse works. Apply this rule within the existing body sections;
  do not add a route field or a new body section for it.
- **This is the mechanism axis, not the boundary axis above — over-building
  the capability you were asked for is scope creep too.** When the seed's
  outcome is reachable with a single-purpose design, architect that: a
  fixed check instead of a rule engine, one direct call instead of a
  pluggable interface, a literal instead of a config knob. The general
  version can stay entirely on the seed's topic and still be the wrong
  call. Escalate to it only when the stated outcome, an acceptance
  criterion, or a named safety/ordering property cannot be true under the
  narrow version.
- Every key listed in the section catalog must appear in the object, even
  when the value is `null`, except conditional keys such as `Input`, `Scope
  guardrails`, `Audit guardrails`, `Expected placement`, and `Stack`, which
  appear only when their condition is met. A missing canonical key is a shape
  error.
- Do not add keys outside the catalog. Unknown keys (including `Steps`,
  `References`, or any free-form addition beyond recognized optional keys) are
  a shape error.
- For sections whose shape is bulleted (`Out of scope`, `Risks`, `Deferred`,
  `Acceptance criteria`), prefer a bulleted markdown list over prose
  paragraphs — that matches the catalog shape and the convention downstream
  tooling expects.
- Keep `Deferred` and `Out of scope` consistent with the in-scope sections.
  Never place an item in `Deferred` or `Out of scope` that `Overview`,
  `Architecture`, or `Acceptance criteria` presents as work this plan
  delivers. If the seed itself both promises and defers the same outcome,
  lift the in-scope claim and drop the conflicting deferral rather than
  emitting both — a body that simultaneously commits to and defers a fact is
  an internal contradiction the downstream conceptual audit flags.
- Draw content from the seed above, the fetched reference documentation, and
  the local repository-code excerpts only. Live web search and unstated outside
  knowledge are still off-limits — the `References` round-trip already chose
  the external sources, and local code is limited to Architecture anchors the
  seed itself named. A section must still be motivated by the seed; evidence
  sharpens its content, it does not license scope the seed never raised.
- If local code directly contradicts an Architecture claim in the seed, make
  the conflict explicit at the start of `Architecture` as a concise
  `> **Seed/code conflict:**` callout naming the seed claim and the code anchor.
  Do not silently replace the claim with prose that hides the disagreement.
  A missing repository match is not itself a conflict: the seed may name code
  this plan will add.
- If an Architecture anchor resolves to multiple repository declarations, make
  the ambiguity explicit at the start of `Architecture` as a concise
  `> **Seed/code ambiguity:**` callout and ask the seed author to choose a
  `path:symbol`; never select one of the listed look-alikes yourself.

## Writing style

The reviewer reads these sections to decide whether the plan is right, so write
them for that reader. The wording rules below change how a section reads, never
what it says: keep every fact, identifier, path, condition, and boundary.
Every rule in this section applies only to text you write, never to text you
lift.

**Reword only a `[derive from intent]` section that you author** (`Overview`,
`Problem statement`, `Architecture`) because the seed has no matching content
for it. Content the seed supplies under another heading (a `Goal` that maps to
`Overview`) counts as supplied. Lift a section the seed supplies, every `[evidence-only]` section, `Input`, and
every guardrail as written: they carry the seed's scope fence and acceptance
bar, and a paraphrase can quietly move a boundary.

- **Use plain, everyday words.** Write the way you would explain the plan out
  loud to a teammate who is new to this codebase. Swap decorative words for the
  common one: "key" not "load-bearing", "level of detail" not "altitude". Never swap a
  precise term ("byte-identical", "short-circuit") for a looser one. Keep exact
  technical identifiers and named project concepts.
- **Open with the point.** Start each section and each paragraph with the
  outcome or decision, then give the reason. The one exception is a
  `> **Seed/code conflict:**` or `> **Seed/code ambiguity:**` callout, which
  always opens `Architecture`.
- **Use bullets for options, conditions, and ordered steps.** Keep a paragraph
  to about five lines; when it holds two independent ideas, split it. Give each
  non-obvious `Architecture` choice its own short paragraph that names the
  choice first.
- **Say what a term means the first time you use it.** Spell out an abbreviation
  or term of art on first use, and name what a number counts.
- **Describe the forward state.** In what the plan builds, drop "previously",
  "used to", and similar history. `Problem statement` still says what is broken
  today. Keep history the seed states on purpose:
  a dated decision not to reopen, an approach that failed and why, a legacy
  behavior that still ships, and where a number came from.
- **Plain wording never overrides a verbatim rule.** Where this prompt says to
  preserve or lift a body verbatim, do that; the rules above apply only where you
  reword. When you are not sure a
  rewording keeps every condition and boundary, lift the text as written.

## Worked examples

The examples are illustrative — pattern-match on shape, not on text. Both
examples below show the seed on the left and the synthesis JSON on the
right.

Example 1 — free-form seed with partial coverage. The seed names a goal,
some non-goals, and a risk; nothing else. Synthesis maps `Goal` to `Overview`,
**derives** Problem statement and Architecture from the stated goal (the two
`[derive from intent]` sections the seed implies but never spells out under a
heading), maps
`Non-goals` / scope-contract exclusions to `Out of scope`, lifts the risk
as written, and returns `null` for the `[evidence-only]` sections the seed does
not address. When the seed carries a full scope contract (Outcome, In scope,
Allowed behavior/reorganization, Verification, Stop/defer), preserve those
boundaries — do not invent reorganization or behavior changes the seed did
not authorize:

```markdown
# Seed

## Goal
Replace the legacy cron poller with an event-driven webhook so we stop
re-scanning the entire inbox every five minutes.

## Non-goals
- Migrating the historical archive — that's a separate effort.
- Touching the retention policy.

## Risks
- The webhook provider can drop events under sustained load; we need a
  reconciliation tail to catch missed messages.
```

```json
{
  "Overview": "Replace the legacy cron poller with an event-driven webhook so we stop re-scanning the entire inbox every five minutes.",
  "Problem statement": "The cron poller re-scans the entire inbox every five minutes regardless of whether anything changed, wasting work and adding up to five minutes of latency between a message arriving and being processed.",
  "Architecture": "Stand up a webhook endpoint that receives message events from the provider and processes each as it arrives, retiring the five-minute polling loop. Pair it with a reconciliation tail that periodically sweeps for events the webhook may have dropped.",
  "Out of scope": "- Migrating the historical archive — that's a separate effort.\n- Touching the retention policy.",
  "Risks": "- The webhook provider can drop events under sustained load; we need a reconciliation tail to catch missed messages.",
  "Testing": null,
  "Acceptance criteria": null,
  "Deferred": null
}
```

Example 2 — seed already uses the canonical section names. Synthesis
lifts each body as written, because the seed supplies every one of them:

```markdown
# Seed

## Overview
Add a `--dry-run` flag to `plan-tool create` so authors can preview the
generated plan without writing the file.

## Problem statement
Authors currently have no way to inspect a generated plan before commit.

## Architecture
Wire `--dry-run` through the CLI parser into `create_plan`; when set,
short-circuit the file-write call and emit the rendered plan to stdout.

## Risks
- Dry-run output drifts from real output if the writer accumulates side
  effects in future refactors.

## Testing
- Unit test: `create_plan(dry_run=True)` returns the rendered string and
  does not touch the filesystem.

## Acceptance criteria
- `plan-tool create --dry-run` exits 0 and prints the plan to stdout.

## Deferred
- A `--diff` mode that compares against an existing plan file.

## Out of scope
- Changing the default behavior (writes still happen without the flag).
```

```json
{
  "Overview": "Add a `--dry-run` flag to `plan-tool create` so authors can preview the generated plan without writing the file.",
  "Problem statement": "Authors currently have no way to inspect a generated plan before commit.",
  "Architecture": "Wire `--dry-run` through the CLI parser into `create_plan`; when set, short-circuit the file-write call and emit the rendered plan to stdout.",
  "Out of scope": "- Changing the default behavior (writes still happen without the flag).",
  "Risks": "- Dry-run output drifts from real output if the writer accumulates side effects in future refactors.",
  "Testing": "- Unit test: `create_plan(dry_run=True)` returns the rendered string and does not touch the filesystem.",
  "Acceptance criteria": "- `plan-tool create --dry-run` exits 0 and prints the plan to stdout.",
  "Deferred": "- A `--diff` mode that compares against an existing plan file."
}
```

## Constraints

- Output JSON only — the caller pipes your response through `json.loads`.
  Any prose before or after the object causes a parse failure and triggers
  a single repair retry; a second failure aborts the create.
- Do not invent content for `[evidence-only]` sections — `null` is the correct
  answer when neither the seed, fetched reference docs, nor local code excerpts
  give them source material. `[derive from intent]` sections are authored from
  the seed's stated goal, not invented: structuring the *what*/*why*/*how* a
  goal already implies is derivation, not fabrication. Evidence enriches
  sections the seed already motivates; it does not justify a section the seed
  is silent on.
- Do not emit a `Steps` key or a `References` key — those sections are
  handled by separate round-trips and the validator will reject your
  response if it sees either.
- Do not emit extra keys outside the catalog. The validator rejects unknowns
  other than the four recognized optional keys.
- Preserve the seed's markdown structure inside each string value (bullets
  stay bullets). Lift every section the seed supplies as written; only a
  `[derive from intent]` section you author from the seed's goal follows the
  Writing style rules, and its facts still come only from the seed and the
  evidence above.
