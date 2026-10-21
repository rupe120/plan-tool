# Plan-seed authoring directives

Directives for authoring plan seeds — the `plan-seeds/*.md` briefs fed to
`plan-tool create <slug> --from-existing <path>`. `PLAN_FORMAT.md` governs the
plan a seed becomes; this document governs the seed itself. Where the two
could disagree about seed content, this document wins.

## What a seed is

A seed is a **concept-level brief**: it fixes the intent, the boundaries, and
the order of an effort so `create` can decompose it into steps. It is the
densest artifact in the pipeline — everything downstream (plan body, detail
files, jira stories) *expands* it. Author it accordingly: the seed carries
the **decisions**; the pipeline manufactures the detail.

## Core directives

**Maximize semantics per token.** Every sentence must move the design: name a
concept, a boundary, an ordering, an invariant, or a settled decision. Cut
anything the reader — human or `create` — can derive: restated context,
hedging, near-duplicate phrasings, and implementation minutiae the detail
phase will re-derive against live code anyway. The deletion test: if removing
a sentence would not change what gets built, remove it. Prefer one precise
identifier (`launcher.py:apply_finding`) over a paragraph locating it.

**Dense is not cryptic.** The plan body copies a seed's wording, and a person
reviews that body, so a seed written as fragments produces a plan nobody can
skim. Spend the density on decisions, not on compression: whole sentences, one
idea per bullet, plain words, and a short definition the first time a term of
art appears. The deletion test removes sentences that change nothing; it never
asks you to shorten a sentence that carries a decision.

**Stay on the concepts at hand.** One seed, one effort. Every paragraph
serves the seed's single Outcome; an adjacent idea — however good — goes to
`BACKLOG.md` / `BUG_BACKLOG.md` or its own seed, cited by name if the fence
must mention it. A seed that accretes side-concerns produces a plan that
audits as over-packed and ends up carved apart by `scope-out`; keep the
carving out of the seed instead.

**Destinations, not turn-by-turn.** The seed names the destinations and the order of
travel — what capabilities exist when it ships, what depends on what, which
stage of a group it is — not the turn-by-turn construction. Function
signatures, exact prompt prose, per-file edit lists, and test-case
enumerations belong to `detail`, which authors and audits them later against
the code as it then stands. A seed that pre-draws the schematic spends its
tokens twice (the detail phase re-derives them) and fossilizes low-level
choices the detail phase is better placed to make. Include a low-level
detail only when it is a **decision, not a derivation** — a contract,
default, or name that must not drift (exit codes, a flag's semantics, a
schema key).

**The trap is the section name, not the intent to be brief.** The canonical
H2s are named for the *plan body*, and several of them invite the wrong
altitude: `## Architecture` invites the design, `## Testing` invites the test
list, `## In scope` invites a file manifest. Each belongs one level up in a
seed — Architecture records the design **decisions** a later reader must not
re-litigate, Testing records **what would prove the Outcome**, In scope names
**surfaces and seams**. Apply the deletion test sentence by sentence: if
removing it would not change what gets built, it was derivation wearing the
costume of rigor. Type signatures, field optionality, registration sites, and
enumerated cases all fall to that test.

**Explicit scope boundaries — required, never implied.** Every seed declares
its fence with the scope-contract fields (`docs/TRACKING.md` § Scope contract and
anti-creep):

- **Outcome** — one measurable result. It is also **the seed's intent**:
  `create` maps its first non-empty paragraph to the new plan's `intent`
  frontmatter field, ignoring thematic-break-only lines, deterministically and
  with no Claude call. The read happens against the **selected raw source**
  before file-backed routing, because `Outcome` has no canonical-body
  counterpart — see
  [`docs/how-to/pipeline/create-from-existing.md`](docs/how-to/pipeline/create-from-existing.md) for
  the flow and [`PLAN_FORMAT.md`](PLAN_FORMAT.md) for the field itself.
- **In scope** — the surfaces and seams the effort touches, at concept
  altitude. Name a path only where the *name* is itself the decision; an
  enumerated file manifest is `detail`'s output, never the seed's.
- **Out of scope / Non-goals** — what this deliberately does *not* do, and
  the sibling or adjacent work it must not absorb. The most load-bearing
  field: completeness audits stay inside it, and a valid out-of-scope
  finding is deferred to the backlog, never applied as plan expansion.
- **Allowed behavior changes** — none beyond Outcome, or the listed deltas.
- **Allowed reorganization** — none, or the smallest named move plus the
  concrete ownership-boundary blocker that proves it necessary.
- **Verification** — how success is checked without expanding scope. In a
  seed file, write this under the canonical `## Testing` heading (case and an
  optional closing ATX sequence normalize), not `## Verification`:
  file-backed ingestion recognizes `Testing` as canonical source content,
  while `Verification` has no canonical counterpart. Repeat
  any non-negotiable result in
  `## Acceptance criteria`.
- **Stop / defer** — where out-of-scope discoveries get filed.

**A scope boundary you want machine-enforced, not just documented, needs one
of three literal top-level headings.** The scope-contract fields above become
plan prose through the ordinary canonical-H2 mapping (`In scope`, `Out of
scope`, …) — readable, but not carried into `detail`/`run` prompts as a hard
fence. `PLAN_FORMAT.md` § "Scope fence" reserves `## Scope guardrails`,
`## Audit guardrails`, and `## Expected placement` for exactly that (a roadmap
draft seed also carries a tool-written `## Stack`, preserved the same way and
never hand-authored): `create`
captures each **verbatim from the raw selected source, before file-backed
routing**, and it
overrides all model output downstream — so a model call can never invent or
soften a guardrail. The capture is a literal, top-level, case-insensitive
heading match; a subsection (`### Scope contract` under `## In scope`) or a
differently-worded heading is always absent from the plan, since the capture
never sees it. If preparation or body synthesis separately recognizes that
content and reproduces it under a canonical guardrail heading of its own,
`create` warns that the heading was dropped — but the content stays absent
either way; only a literal top-level canonical heading in the raw seed is
ever rendered. Use the reserved heading verbatim, as a standalone `##`
section, whenever a boundary must survive into every downstream prompt rather
than only into the plan's own prose.

A backlog-derived seed **inherits the source entry's contract verbatim** and
elaborates it — it never invents a different fence — and names its source
entry (and its Jira ticket key, once promoted) plus the requirement that the
resulting plan updates the originating backlog file when the work ships. For a
promoted item the entry is a one-line stub and its ticket holds the contract,
so copy the contract from the ticket into the seed (the seed is the in-repo
copy that `create` reads), and the plan's final step removes the stub. See
`docs/TRACKING.md` § "Promotion stubs".

**Keep a stage-separated replay when it protects the effort's level of
detail.** When an outcome depends on a decision belonging to the bare-plan or
detail-grounded stage, put one compact replay in canonical `## Testing` and
repeat its result in `## Acceptance criteria`. It names: (1) the property and
the routes it must cover, (2) what the bare stage must retain or defer, and
(3) what the detail-grounded stage may require. This is acceptance evidence,
not a test-case inventory: state the property and its owning stage, not a
carrier, attachment API, dependency rewrite, fixture, or other implementation
choice unless that choice is itself settled. A replay left only in background
rationale is historical context and may be correctly compressed by preparation.

**An In-scope item whose core design question sits in the same seed's
`## Deferred` list is a second effort — fence it out.** Deferring the decision
while keeping the deliverable in scope hands `create` an undecidable arm: the
plan carries steps that cannot be authored until the deferred question is
answered, and audits flag the arm until a `scope-out` carves it. Measured
2026-08-12 (`batch-authoring-observability`): raw-NDJSON transcript capture
sat In scope while Deferred held its central open question (capture trigger);
the arm drew four material findings including a CRITICAL in two rounds and
forced a 12→9-step carve. Move the item — and its open question — to the
backlog or its own seed.

**State the seed's commitments; the audit traces exactly what a seed stakes
out.** The completeness audit discovers defects by inventorying the plan's
commitments — closed vocabularies, promised field sets, lifecycles,
precedence rules, guarantees, rule→counterpart obligations, checkable claims
about code — and tracing each end-to-end (`plan_tool/prompts/plan-audit.md`
§ Method). A commitment the seed implies but never states gets reconstructed
by the audit instead, one finding arc at a time. Two kinds carry an explicit
mandate; state each in the seed, or assign it to `create` in one line — never
leave it implicit:

- **A guarantee names its mechanism, its owning destination, and its ordering
  fence.** "Never X" / "always X" / "only Y" is an adjective until the seed
  says what mechanism delivers it, which destination owns that mechanism, and
  where it lands in build order relative to the surfaces it must cover.
  Measured 2026-08-12/13 (`batch-authoring-observability`): one "never
  credentials … redacted summary only" guarantee naming no mechanism — none
  existed at HEAD — seeded ~17 findings across 9 of 10 bare-plan audit
  rounds, one newly discovered unreached surface per round. This is the
  seed-level face of CLAUDE.md § "Validating a semantic property you cannot
  observe": the guarantee's *mechanism, owner, and ordering* are the binary
  observables; the adjective alone is the unobservable property.
- **A closed vocabulary obliges a per-value contract.** Naming an enum, state
  set, or reason set commits the effort, per value, to: definition, producer,
  precedence against sibling values, consumers, and — for states an operator
  can land in — an exit path. Carry the table, or say in one line that
  deriving it is `create`'s job. Measured 2026-08-12/13
  (`roadmap-seed-materialization`): a six-state draft-seed vocabulary named
  with none of this seeded findings in seven of nine audit rounds — that
  plan's largest single finding source; a seven-value termination-reason
  enum in the sibling plan drew ~10 findings the same way.

**Both failure modes compound when a seed carries several of them at once and
the guarantee's own mechanism keeps getting redesigned.** A later
evaluator-command seed (2026-09-14/15) named several unmechanized guarantees
in one Architecture — non-mutating, isolated, current, ephemeral — plus
several under-specified vocabularies (outcome kinds, refusal reasons, exit
codes, a next-action shape) with none of the per-value contract above. 95
findings across 25 bare-plan audit rounds never converged: roughly a quarter
concentrated on the non-mutation guarantee's mechanism alone (which state
counts as protected, in what order it is checked, what a race between
checkpoints leaks), and most of the rest split between artifact-currentness
selection and the missing vocabulary contracts. The owner narrowed the design
twice in response, and the count still never fell, because each round's fix
patched one mechanism detail while the guarantee's shape was still being
renegotiated — a redesign restarts the search for the next unswept corner
instead of ever completing one exhaustive pass against a fixed target. This
is independent confirmation of the same pattern on a different plan, not new
evidence about that plan's history, which is not the durable record here —
this paragraph is. **When a fix round is reshaping the guarantee's mechanism
itself rather than filling in a fixed one, stop iterating rounds and rewrite
the seed's guarantee and vocabulary tables wholesale instead.**

**A seed for a validation feature names its observable and enumerates what may
not be checked.** When the seed proposes a check, gate, finding, or enforcement
of any kind, two things are required rather than optional: the **binary
observable** the check asserts, in one sentence — if you cannot state it, there
is no feature yet — and an **enumerated not-allowed list** inside the scope
fence: quality judgments, agreement checks between two prose artifacts, shape
or length caps, gates and exit-code flips. Stating the principle in prose
("deliver, don't verify") does **not** hold the line; only the enumeration
does. See CLAUDE.md § "Validating a semantic property you cannot observe" for
why this class inflates without bound and the two instances that paid for the
rule.

**Review at seed altitude before handing the seed to `create`.** Verify the
seed's claims against live code and its source backlog, resolve material
correctness problems, and re-review until correctness converges or only an
explicitly recorded advisory tail remains. Claim verification is mechanical,
not judgment: every checkable claim the seed makes about existing code — a
count, an "X has none today", an exit code, a persisted field, a named
convention — gets grep/read-verified against HEAD, with the anchor
(file:symbol) recorded in the seed, before `create` runs. A false code fact
that survives seed review is repeated verbatim by `create` and then costs
audit rounds until something greps it — measured 2026-08-12/13: a seed's
claim that `draft_seed_bundle` was a persisted field needing migration (it is
transient, in-memory) survived create plus three audit rounds; a sibling
seed's same-slug-clobber Testing claim was contradicted by the docstring of
the very module it named. Do not make a seed pass a
finished-plan completeness audit: a seed intentionally lacks per-step
mechanics, edge cases, fixtures, file manifests, and prose refinements. Raise
a conceptual-completeness issue only when it is **HIGH** or **CRITICAL** and
the omission contradicts the Outcome/scope fence, leaves a settled decision
without the counterpart it requires, or makes a coherent plan impossible to
derive. Everything else waits for the plan or detail stage.

## Conventions

- **Placement and naming.** Seeds live in `plan-seeds/`. Ordered groups use
  `<group>-NN-<slug>.md` (zero-padded, matching the plan slug so manifests
  and run dirs sort in execution order); a standalone seed keeps a plain
  slug. A staged seed pins its stage's tool state — which earlier stages
  shipped, which later stages it must not reach into — and cites the group's
  anchor backlog entry for the arc rather than restating it.
- **References are a preflight requirement.** `create --from-existing` requires
  exactly one usable `## References` body before slug inference or any
  authoring-model call. Missing, duplicate, empty, or placeholder References
  refuse the source; an unmatched fence is a separate input-syntax refusal.
  List the developer/API documents or other evidence the plan relies on in
  that section. This source fallback is intentionally narrower than a complete
  canonical body: it prevents a failed reference-research response from
  turning a locally visible seed gap into a late no-write failure.
- **Canonical H2s can select direct ingestion.** A seed with exactly one
  non-empty, non-placeholder instance of each canonical body heading
  (Overview, Problem statement, Architecture, Out of scope, Risks, Testing,
  Acceptance criteria, Deferred) is direct-ready. Its supplied body and
  References remain authoritative after the required raw-source split
  assessment. The canonical step layout (`PLAN_FORMAT.md § canonical step
  layout`) independently skips step decomposition. Canonical matching
  normalizes case and an optional closing ATX sequence, but
  `## Verification` is not `## Acceptance criteria`, and
  `## Out of scope / Non-goals` is not `## Out of scope`. A missing, duplicate,
  empty, or placeholder canonical body heading selects visible preparation;
  it does not create a broader source rejection. Use canonical names where
  the content exists, but never pad a section or add heading aliases merely to
  select direct ingestion. **The scope contract and the canonical
  body are two halves of one requirement — carry both.** The shortcut does
  not discharge the scope contract: `Outcome` and `In scope` have no
  canonical-H2 counterpart, so a seed shaped for the canonical body silently
  omits two required fields unless they are added deliberately. The inverse
  hole is just as expensive: a seed shaped only around the scope contract
  leaves `Risks`, `Testing`, and `Acceptance criteria` absent and selects
  preparation, so state those commitments when the seed depends on them.
  Canonical `## Out of scope` also supplies the audit fence's `Out of scope /
  Non-goals` field, so it needs no duplicate heading; if both headings exist,
  the explicit scope-contract heading supplies that field.
  Omitting `Outcome`
  costs more than the field: with no usable `## Outcome` there is nothing to
  map, so the new plan carries no `intent` and `create` falls back to offering
  a drafted one in its review wizard.

  **One why-section, not two** (decided 2026-08-02; do not re-open). The seed
  format gains no second why/intent section — `## Outcome` is it. Two prose
  fields at the same altitude that can disagree with each other is the
  duplication this was decided against.
- **Tense and hygiene.** Present/future tense throughout (CLAUDE.md
  § Documentation is forward-looking). After any structural change to the
  effort — cut, split, merge, scope-out, reversed decision — sweep the seed
  for both invalidated identifiers and the removed concept's vocabulary.
- **Judged (non-deterministic) features.** A seed whose plan adds
  Claude-judged behavior also satisfies the seed-time checklist in
  `docs/explanations/nondeterministic-plan-design.md`.
