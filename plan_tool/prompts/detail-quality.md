# Detail-quality review for step ${step_id}: ${step_title}

Plan: **${plan_title}** · step ${step_id} · complexity ${step_complexity} · depends on ${step_depends_on}

${project_context_block}${risk_context_block}## Step files (declared)

${step_files_block}

## Current contents of declared files

${files_contents_block}

## Plan-level guardrails and scope fence (authoritative)

${plan_guardrails_block}

## What to do

Verify the detail body — provided at the **end** of this prompt under
"## Detail body to review" — is **grounded**: that every concrete claim
it makes holds against the code at HEAD — so a developer can implement
the step without discovering the instructions diverge from reality. The
loop already runs deterministic checks for declared-path resolution,
cited-vs-declared coherence, and missing sections; **your job is the
semantic grounding those checks can't do.** Use your tools: Read and
Grep the producer symbols, IaC/runtime-definition files, and sibling
modules the body cites — including files **not** in the declared list
when the body's correctness depends on them. **Read/Grep only — do not
edit any file**; report findings and a separate apply pass acts on them.

Grounding failure modes to hunt for. **When a claim recurs** — the same
symbol's behavior, guardrail reference, or metric name restated in more
than one section of the body (e.g. Why and Implementation both describe
what a producer returns) — **check every occurrence before writing the
finding, and name each site the finding covers.** A fix applied at the
first mention you hit and left standing at a later restatement ships a
document that still contradicts itself.

- **Plan-guardrail drift.** The detail must not relax, contradict, or omit a
  guardrail or scope-fence entry that applies to this step. When one applies,
  require an `## Applicable guardrails` entry that **references** it — plan
  section plus a short label — and names the boundary it imposes on this step.
  Flag a concrete conflict, or a missing step-relevant entry; do not demand a
  section when this block says no plan-level guardrails or scope fence, or when
  none applies.
- **A guardrail reproduced instead of referenced.** An entry that quotes the
  plan's wording, or carries over its counts and enumerations ("the four
  templates"), is a copy that silently goes stale on the next plan edit, in a
  file unrelated to that edit. Flag it and say which reference should replace
  it. Do **not** flag a short identifier or section name, nor a boundary stated
  in terms of this step — naming the constraint and its consequence is the
  point; reproducing its specifics is the defect.

- **Cited symbols that don't resolve at HEAD.** Every file path plus
  stable identifier (function, class, constant, metric name) the body
  treats as fact must exist in code, or be explicitly labeled
  not-yet-created (produced by an earlier step / out of tree). Grep the
  producer to confirm — don't trust the body's prose.
- **Names transcribed from the plan/title instead of the producer.**
  Metric names, dimensions, ARNs, identifiers, and inventory counts are
  routinely stale or illustrative in a step's title/body. Re-derive them
  from the producing symbol at HEAD; flag any the body hardcodes without
  confirming (e.g. a CDK helper's `SessionCount` when the live service
  vends `Sessions`; a count the plan supplies vs what the producer emits).
- **Config the code reads but nothing sets.** When the body's code reads
  an env var / SSM param / secret / flag, confirm every deploy target
  that runs it actually sets the value and that the consuming role's IAM
  scope covers the path. A missing wire ships a feature that's silently
  un-enableable.
- **Cross-step contracts that assume a not-yet-merged signature.** When
  the step consumes a symbol an earlier step produces, the body must
  instruct confirming the exported name/arity at HEAD and pass only what
  the current signature accepts — not a future shape. Name the section of
  *this* step's body where the cross-step claim is asserted (Why, Input,
  Implementation, …) — full cross-step tracing is the plan-wide
  completeness audit's job, not this pass's, but a concrete anchor here
  is what lets that later pass pick the claim up instead of re-deriving
  it from scratch.
- **Unverifiable property claims.** "Standalone / decoupled / not wired
  into X" and decision/ADR constraints are only real if backed by a
  negative-assertion or invariant-preservation grep. Acceptance criteria
  must be CI-checkable ("returns X for Y", "`grep -n` returns one match"),
  not vibes ("code is clean").
- **`## Tests` section that contradicts the step's declared type.** If a
  test directive appears below, the `## Tests` section must honor it; a
  Tests section that ignores it — a code step naming no tests, or a
  `non-code` step prescribing unit tests for production behavior it does
  not change — is a finding. Do **not** flag a code step for the *order*
  in which it writes tests relative to the implementation: that contract
  was withdrawn 2026-07-30 and is no longer part of this
  review.${change_type_directive_block}

**Grounding is about the claims the body *does* make — not about forcing
it to prescribe more.** Detail files aim for intent over mechanics: they
state what must be true when the step is done (the acceptance criteria)
and recommend an approach, deliberately leaving exact code to the
implementer. Do **not** raise a finding because the Implementation
section recommends rather than dictates, omits line-level steps, or
leaves a "how" open — that latitude is intended. Flag only when a claim
the body *asserts as fact* is wrong or ungrounded, when the acceptance
criteria aren't CI-checkable, when the intended *outcome* itself is
missing or ambiguous, or when the Implementation names **no real anchors
at all** and recommends no approach — leaving the reader with no idea
*where* the work lives (naming the files/symbols involved is still
required even when the exact code is left open). An open *how* is fine;
an open *what* or *where* is not.

## Step purity (refactor vs feature)

Separately from grounding, judge whether this is a **mixed** code step —
one whose detail describes *both* behavior-preserving restructuring (a
move / rename / extract that leaves behavior unchanged) *and* new or
changed behavior in code. The detail body is the richest evidence: look
in `## Implementation` and `## Tests` for a "preserve existing behavior"
thread and a "now it also does X" thread living in the *same* step (e.g.
a `Promise.all` parallelization that preserves behavior bundled with an
auth removal that changes the failure mode from throw to fail-soft).

Non-trigger: non-code elements (docs, config, CI wiring) riding along
inside a code step are **not** mixing — only refactor-vs-feature *in
code* counts. A `non-code` step is never mixed.

If — and only if — the step mixes the two, emit a `## Structural
findings` block (separate from `## Findings`) containing a single bullet
naming both halves. Place it **immediately before** the final
`## Findings` block:

```
## Structural findings

- MIXED-STEP: <one line — the behavior-preserving part, the
  behavior-changing part, and why they must be two steps>
```

Omit the `## Structural findings` block entirely when the step is
type-pure. This is a *structural* finding: it is reported, never
auto-applied — the remedy is splitting the step into a
refactor-then-feature pair, not editing prose.

## Conceptual altitude advisories

Also look for detail prose that is too mechanically prescriptive for an
implementation detail file: full pseudo-code, exact speculative helper
names, magic constants copied from the source plan, API argument
literals, full config/IAM snippets, or exhaustive test rosters that make
incidental mechanics look mandatory. These are **advisory conceptual
altitude** issues only. Recommend demoting the material to `e.g.`
examples, placeholders, executor notes, or ticket notes; do not ask the
apply pass to delete or rewrite the detail body.

Also flag the opposite direction: an implementation that reaches for a
more general mechanism than the step's stated acceptance criteria and
invariants require — a rule engine where a fixed check would do, a
pluggable interface for one direct call, a config knob nobody asked for,
an extensibility seam for a hypothetical future step. This is the same
overreach `plan-audit.md`'s proportionality rule refuses at the plan
level, aimed here at the chosen mechanism instead of the scope boundary.
Recommend narrowing to what the acceptance criteria actually need; do not
ask the apply pass to delete working code outright.

Do **not** flag exact specificity when it is the required constraint:
real file/symbol anchors, fixed names already present at HEAD, ordering
rules, event boundaries, rejected alternatives, failure modes, and
acceptance checks are allowed and often required.

When you find conceptual-altitude issues, emit a separate block
immediately before the final `## Findings` block. Do not include these
advisory bullets in the final `## Findings` block:

```
## Advisory altitude findings

- ALTITUDE: <one line — what reads as mandatory mechanics and how to demote it>
```

Omit the advisory block entirely when there are no altitude issues.
The final `## Findings` section below remains mandatory and must stay the
final section.

Also flag at **NIT**: `should`, `shall`, or `will` used to state an
obligation in `## Acceptance criteria`, `## Implementation` guarantees, or
`## Constraints` — the detail prompt locks obligation language to
`must` / `must not` / `may` / `can`, and any of the three reads as
ambiguous about whether it's required or merely recommended.

Style nits (flag at **NIT**, never block): vague intensifiers ("a lot",
"various"), filler ("it is worth noting"), historical narration
("previously…", "(was: X)"), prose blocks >~5 lines that should be
bullets, and fancy/uncommon vocabulary where a plain word reads the
same — "load-bearing", "byte-identical", "elision/elided", "footprint",
"self-referential", "posture", "tenet", "short-circuit",
"fall-through", "kind-dispatch", "vacuous", "tautological",
"unfalsifiable", "by construction", "orthogonal", "altitude",
"fan-out" → "key/most important", "unchanged",
"left out/dropped", "set of files", "refers to itself",
"approach/rule", "stop early", "falls back", "splits by kind",
"always true so it can never fail", "true by definition",
"nothing could prove it wrong", "by the way it is built",
"independent", "level of detail", "one call that runs several
checks". The test
is whether you'd say the word aloud to a teammate; if not, flag it.
Don't flag exact technical identifiers (type/field/flag names, library
concepts, named project terms like "leaf module") — only decorative
word choices.

Severity guidance:

- **CRITICAL** — the body contradicts code or frontmatter: a cited
  symbol/path doesn't exist, a name won't match what the producer emits,
  the dependency chain is wrong.
- **HIGH** — a load-bearing wire is missing (unset env var, too-narrow
  IAM, consumed symbol absent from the producer's surface) so the step
  ships broken; or the step gives a developer nothing actionable — no
  acceptance criteria, an Implementation that names no real files/symbols
  and recommends no approach, or a Why/Implementation that leaves a reader
  unable to tell what "done" means or where the work lives (an open *how*
  is fine; an open *what* or *where* is not).
- **MEDIUM** — an unverified claim that's probably right but uncited, an
  acceptance criterion that isn't CI-checkable.
- **NIT** — style / clarity.

Report findings using **symbolic anchors** (file path plus a stable
identifier — function, class, heading, constant, unique string), not raw
`file:line` references; line numbers drift on every commit. Cite a line
number only as a secondary disambiguator when a symbol appears more than
once. End your response with a `## Findings` block — one bullet per
issue, prefixed with a severity token. The block is machine-parsed; keep
it as the final section.

${findings_response_format_block}

Replace the empty marker with severity-prefixed bullets when the detail has an
issue.

## Recurring failure modes from prior runs

For each lesson below that applies to this step, confirm the body does
**not** commit that failure; if it does, raise it as a finding.

${lessons_block}

## Detail body to review

The freshly-written prose to review. Apply all the guidance above to it.

${detail_body_block}
