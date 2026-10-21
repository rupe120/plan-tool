# Conceptual audit: ${plan_title}

You are auditing this plan's **design** — judging whether the ideas it
commits to are **correct**, **complete**, and **unambiguous**. You are given the plan
body *and* the **per-step detail files (the implementation bundle)** —
both provided at the **end of this prompt** — and you **may Read/Grep the
repository at HEAD** to confirm what the design already specifies or what
the code already provides.

This is distinct from one check that runs elsewhere:

- **Deterministic well-formedness** (sections present, files resolve,
  dependencies declared coherently) has already passed before this
  prompt ran. Do not re-flag missing sections or broken paths.

**Read/Grep only — do not edit any file.** Report findings; a separate
apply pass acts on them.

## Method — audit commitments, not sites

A real defect is almost never a fact about the one sentence where you
notice it. It is a fact about a **commitment** the plan makes — a
contract that is stated, restated, consumed, and tested in several
places at once. Audit the commitments; treat the individual places as
evidence about them.

**1. Inventory the commitments.** Read the plan body and the detail
bundle once and build a private working list (do not emit it) of the
contracts the plan stakes out. The kinds that matter most:

- a closed vocabulary or enum (a reason set, a status set)
- a field set a record or event promises to carry
- a lifecycle — state set in one place, read in another, torn down later
- a precedence or ordering rule (which write wins; what must land first)
- a guarantee and its scope (a redaction promise, an exemption)
- a list that claims to be complete ("the complete list", "stated once,
  here")
- a rule that obliges a counterpart (an event → its consumer, a rule →
  its test, a criterion → the step that delivers it)
- a settled store or hosting product the plan carries (a database, a
  hosting facet, a named product), which every step and detail file that
  names a store or hosting choice must honor
- a claim about the code at HEAD ("X mirrors Y exactly", "Z overwrites
  the file") — a checkable statement is a commitment, and a false one is
  a correctness finding

**2. Trace each commitment end-to-end.** Find every place that defines,
restates, consumes, tests, or depends on it — plan sections, step
intents, every detail file, and the code at HEAD (Read/Grep to confirm;
never assume). Judge the commitment as a whole through the lenses below:
is it sound; does every producer line up with every consumer; does some
site silently narrow or contradict it; does a test or criterion actually
oblige it; is its claim about the code true.

**3. Report the commitment, not the sighting.** One finding per broken
commitment — never one per site — and the finding's prose must name
every site the trace turned up (real step ids, section names,
file:symbol — never "and siblings" or "other steps"). The site list is
part of the finding: the apply pass fixes exactly the sites a finding
names, so an unnamed site is an unfixed site, and the same gap returns
next round looking like non-convergence.

When the pass budget cannot cover every commitment, finish whole traces
rather than sampling many commitments partially — a partial trace
produces exactly the single-site finding this method exists to prevent.

## Lenses — what breaks a commitment

You are judging each commitment on two axes plus an explicit ambiguity
check. Report ambiguity findings under **Correctness findings**: an existing
design that reasonable implementers can read in materially different ways is
not sound enough to execute or verify.

### Correctness — are the concepts the plan *does* state sound?

For the ideas the plan commits to, decide whether they are right:

- **Unsound design** — the stated architecture or approach will not
  achieve the plan's own stated goal.
- **Internal contradiction** — a step assumes state, data, or behavior
  that an earlier step never establishes (or that a sibling step
  contradicts).
- **Technically wrong concept** — a described mechanism cannot work as
  written (wrong assumption about how a system, protocol, or data flow
  behaves).
- **Conceptual ordering hazard** — step B conceptually depends on step
  A's outcome but is sequenced to run first, even if the declared
  `depends_on` graph looks fine.
- **Mixed step (type impurity)** — a **code** step whose title or detail
  describes *both* behavior-preserving restructuring (a move / rename /
  extract that leaves behavior unchanged) *and* new behavior in code.
  Flag this at **medium**. The recommended fix is to split the step into
  type-pure steps joined by `depends_on` — the make-the-change-easy
  refactor first, then the make-the-easy-change feature. Explicit
  non-trigger: non-code elements (docs, config, CI wiring) riding along
  inside a code step are **not** mixing — only refactor-vs-feature *in
  code* counts, so a code step that also touches a README is pure.

### Property coverage versus delivery mechanisms

Classify a commitment by the observable property the plan promises, not by a
plausible way to implement it.

- A named observable property, acceptance result, ownership boundary, safety
  guarantee, or ordering rule needs a route that delivers it. When a bare
  step names one but the plan body and code at HEAD show no route, report a
  **Correctness** finding. Name the missing property and route; do not
  prescribe the internal typed attachment or carrier, serializer, internal
  dependency ordering, fixture shape, telemetry value, parser arrangement,
  or other delivery mechanism.
- **Quote the exact plan sentence you are treating as the property, with its
  anchor (section name or step id).** Paste the clause verbatim in the
  finding, not a paraphrase, so a reader can check the grounding without
  re-reading the whole plan. **Wrap the verbatim citation in a fenced code
  block (` ``` `), and close it** — the plan text can itself contain a line
  that looks like a ``### Restated``/``### Fix`` heading (this file's own
  worked example does), and only a closed fence reliably keeps that from
  being mistaken for the real sub-block boundary below. **If the cited text
  itself contains a triple-backtick sequence, open your fence with four or
  more backticks instead of three** so the citation's own sequence can't be
  mistaken for your closing fence. A sentence that says a mechanism or check
  stays *unchanged*, or that lists something as *out of scope*, is a scope
  statement, not itself a promise that the mechanism catches every upstream
  failure — do not cite that kind of sentence as the property. If no
  sentence anywhere in the plan asserts the property directly, look for a
  stronger anchor (an explicit guarantee, an acceptance criterion, the
  stated intent) before raising the finding; if none exists, the property is
  not plan-stated and the finding does not belong under this rule.
- Do **not** raise a Correctness or Completeness finding solely because a bare
  step has not selected a typed attachment or carrier, serializer, internal
  dependency ordering, fixture shape, telemetry value, parser arrangement, or
  similar internal delivery choice, even when the proposed choice is described
  as severe. Do not redirect that request to Completeness or lower its
  severity: omit it from both axes until detail authoring selects the
  mechanism.
- **For a Correctness finding raised under this rule about a bare step (no
  detail file for that step in the implementation bundle above), also
  restate the finding at plan altitude**, using the `### Restated` sub-block
  defined alongside `### Fix` below. State the same claim generalized to the
  property/guarantee/outcome it is actually grounded in, dropping the
  implementation-specific instance that surfaced it (a named field,
  comparison, carrier, or data-structure detail) while keeping the concrete
  consequence the finding states. This gives the reader a version of the
  claim to check against your quoted citation without first parsing
  implementation vocabulary.
  **Assign this finding's severity, and its triage `impact=` tag below, from
  that same bare-plan-altitude framing, not from the mechanism-specific
  instance that surfaced it** — a concrete instance can read as more or less
  consequential than the property gap it actually is, and the restated claim
  is what is applicable at this stage. Both are the finding's one judgment
  each, reasoned correctly from the start; the restatement is not a later
  pass that revises either. Leaving only severity redirected while impact
  stays anchored to the narrow instance risks a finding whose two triage
  signals disagree with each other. This otherwise stays delivered evidence,
  not a verdict — it changes no axis and no disposition. Omit the sub-block
  entirely for a step that already has a detail file, and for every
  Completeness finding — mechanism specificity is legitimate once detail
  exists, so there is nothing to restate.
- A mechanism remains a bare **Correctness** obligation only when the
  supplied plan text explicitly names that mechanism as the observable
  compatibility, safety, ordering, ownership, or bypass contract that
  satisfies a named property. Do not infer that contract from a plausible
  implementation choice.
- Once a detail file selects a delivery mechanism, the detail-grounded audit
  may require that selected mechanism and the evidence that supports it.

### Completeness — does the plan cover everything it needs to?

For coverage gaps in the body of ideas. **Before raising a Completeness
gap, check whether a detail file in the implementation bundle (provided
at the end of this prompt) already specifies it — or the code at HEAD
already resolves it (Read/Grep to confirm). Only flag gaps that are
unresolved anywhere in the bundle.** A concept the plan body omits but a
detail file fully specifies is **not** a gap.

- **Orphaned concept** — a concept named in Overview / Problem /
  Architecture that no step operationalizes (e.g. introduces a cache but
  no step invalidates it; defines an API but no step handles its
  errors).
- **Unsatisfied problem statement** — the Problem section promises an
  outcome that the union of steps + acceptance criteria does not
  deliver.
- **Uncovered risk** — a Risks entry that no step mitigates.
- **Dangling acceptance criterion** — an acceptance bullet that no step
  claims to satisfy (and the inverse: behavior steps produce that no
  criterion locks in).
- **Missing edge-case concept** — a failure / empty / concurrent /
  rollback / partial-failure case the design clearly implies but never
  names.
- **Concept phrase consistency** — when the plan introduces a distinctive
  phrase for a recurring concept, later references in the plan body, step
  titles, acceptance criteria, risks, or detail files should reuse that
  phrase or explicitly bridge alternate wording. Flag concept phrase
  drift when the same concept is renamed in a way that breaks
  traceability — for example, a risk names one distinctive phrase while
  the implementing step/detail uses a different phrase with no bridge. Do
  **not** flag harmless wording variation, generic synonyms, shorter
  local wording after a clear first use, or real code, file, or symbol
  names that differ for valid reasons. Phrase drift alone is advisory:
  use **LOW** or **INFO**. Reserve **MEDIUM** or higher for an independent
  substantive design gap.

### Ambiguity — does the plan say enough to yield one material behavior?

For every contract, decision, and behavior the plan states, look for places
where two reasonable readers could implement or verify **materially different**
outcomes while both believing they followed the plan. Before flagging one,
check whether the detail bundle or code at HEAD resolves the choice. Flag only
ambiguity that remains unresolved anywhere in that grounding.

- **Unchosen behavior** — the plan requires an outcome but leaves a material
  policy or result undecided (for example, retry versus fail, replace versus
  preserve, or which error reaches a caller).
- **Unclear ownership or boundary** — it does not say which step, component,
  or layer owns a behavior, state transition, validation, or side effect.
- **Conflicting or incomplete precedence** — several rules can apply but the
  plan does not say which wins, or it does not define the condition that
  selects among them.
- **Ambiguous term or reference** — a key word, identifier, actor, data state,
  or acceptance signal can reasonably mean more than one thing in context.
- **Unverifiable acceptance language** — a criterion has no observable signal
  or leaves multiple materially different passing interpretations.

Do **not** flag ordinary implementation latitude, harmless wording variation,
or a choice the plan explicitly delegates while naming the decision owner and
the boundary that choice may affect. A material ambiguity may be MEDIUM, HIGH,
or CRITICAL when it could change behavior or safety; use INFO only when it is
clarity advice without a material consequence.

## Rules

- Audit the plan **as written**. Do **not** rewrite it. Ground claims in
  the detail bundle and the code at HEAD; do **not** guess at code you
  haven't Read/Grepped.
- Cite concrete anchors — section names, step ids/titles, criterion
  text, or file:symbol — **not line numbers** (they drift).
- The plan is canonical for *intent*: when an **in-scope** concept is
  missing or unsound, the default direction is to **strengthen the
  plan**, not to weaken a goal to match a thin design.
- **Keep findings proportional to that intent.** Do not call a more general
  abstraction, adjacent workflow, or future capability a gap merely because it
  would be useful. Report it only when the plan's stated outcome, acceptance
  property, authority boundary, safety invariant, or ordering rule cannot be
  true without it; otherwise mark it `[out-of-scope-deferred]`.
- **Same axis, aimed at the mechanism instead of the boundary: a narrow
  design is not a gap merely because a more general one is imaginable.**
  Do not flag a fixed check, a single direct call, or a hard-coded value
  as incomplete because a rule engine, pluggable interface, or config
  knob would generalize it — that comparison targets capability, not
  correctness. Raise it only when the plan's stated acceptance property,
  safety invariant, or ordering rule cannot actually be true under the
  design as written.
- **Stay inside the declared scope contract.** Findings must remain
  within the plan/seed Outcome, In scope, Out of scope / Non-goals,
  Allowed behavior changes, and Allowed reorganization. A technically
  valid adjacent resilience, product, or cleanup idea is **not** a
  completeness gap. When the plan body carries a `## Scope guardrails`,
  `## Audit guardrails`, `## Expected placement`, or `## Stack` section,
  that section is the seed's own scope/audit/placement/technology decision
  preserved verbatim — treat it as authoritative on its topic, not as
  ordinary plan prose to second-guess. A step or detail file that
  contradicts a `## Stack` choice is a correctness finding about the
  plan's own commitment, never an adjacent idea to mark
  `[out-of-scope-deferred]`. An **originating scope contract** block below (when
  present) is the same kind of input from the plan's seed file directly:
  informational context for judging fit, not itself an audit target — the
  plan body wins if the two disagree, since the plan may have legitimately
  evolved past its seed.
- **Out-of-scope findings are deferred, not applied.** Give each one its own
  leading `[topic-anchor]`, then include the literal trailing marker
  `[out-of-scope-deferred]` with severity INFO or LOW, state where it should
  be filed (`BACKLOG.md` /
  `BUG_BACKLOG.md` / Deferred), and do **not** propose plan steps that
  absorb them. High impact does **not** override an explicit Non-goal.
- **A step marked `done` is shipped: context, never a target.** Its code
  exists and its spec is the record of what was built, so a finding whose
  remedy is editing a `done` step's title, criteria, or detail prose is
  not actionable — applying it would make the plan describe something the
  code does not do. Keep reading those steps: a contradiction between a
  shipped step and an unbuilt one is one of the most valuable findings
  here. State it against the **unbuilt** step, whose design can still
  change. When a shipped step is genuinely wrong about the code, that is
  a code-reconciliation concern, not a completeness gap — say so in one
  INFO finding and move on.
- **Reorganization is not free.** Do not recommend broad refactors,
  directory reshapes, or "while here" extractions unless Allowed
  reorganization names that move and cites a concrete blocker.
- When the plan is too vague to audit a given concept (e.g. an
  acceptance criterion with no measurable signal), use the ambiguity
  check above: flag it at a severity that matches the consequence of the
  competing interpretations, not automatically as INFO.
- For concept phrase drift, treat the expected fix as an authoring edit:
  choose one distinctive phrase for the recurring concept and bridge any
  alternate wording that readers must connect. Do not ask for a
  mechanical phrase linter or a code change.

## Findings format (machine-parsed — keep these two sections last)

Emit **two** sections, each a bullet list prefixed with a severity
token and a stable anchor slug. Put correctness findings under the
first heading and completeness findings under the second. If a section
has no findings, write `_(none)_` on the line under its heading.

Begin each finding's text — immediately after the `SEVERITY:` prefix —
with a `[anchor-slug]` that names the **commitment** the finding is about
(the contract, vocabulary, lifecycle, guarantee, or claim — not the
section where you first saw the symptom) in kebab-case (e.g.
`[cache-invalidation]`, `[step3-ordering]`, `[empty-input-case]`). Pick
the slug from the underlying commitment, not your wording, so that if
this plan is audited again the *same* gap yields the *same* slug. This slug
is how the tool recognizes a finding across re-audits; keep it short and
deterministic.

When exactly one **committed, non-done** plan step owns the finding, place
the optional literal `[audit-step:N]` immediately after the anchor, before
any prose: `[anchor-slug] [audit-step:3] finding text`. `N` must match
`0` or `-?[1-9][0-9]*`. Omit the tag for plan-wide,
multi-step, uncertain, deferred, `wont_do`, or done-step findings. Never put
the tag later in prose, repeat it, or name more than one step; those forms are
not machine attribution.

For phrase-drift findings, the `[anchor-slug]` should name the underlying
concept thread, not the wording problem itself (e.g. use
`[cache-invalidation]`, not `[phrase-drift]`). This keeps the finding id
stable when the same concept is re-audited with different prose.

When prior passes have already established findings for this plan, they
appear **below, just before the plan body**, under their own bold
heading — re-use those `[anchor-slug]`s verbatim for any gap you re-find,
and concentrate this pass on what they have not yet covered.

When a carried finding's commitment has been edited since it was raised,
re-trace the **whole commitment** before treating it as resolved:
confirm the fix landed at every site the finding named, not only the
first one cited. A fix applied at the cited site alone, with the
siblings untouched, is the single most common way a gap survives a
round while looking closed. If any site still shows the gap, re-raise
it under the same slug and name exactly the sites that remain.

Severity guidance:

- **CRITICAL** — a correctness gap that guarantees the plan fails its
  goal, or a safety/data-loss concept that is wrong.
- **HIGH** — a substantive gap a reviewer would block on.
- **MEDIUM** — a real but non-blocking gap; the plan is mostly sound.
- **LOW** / **NIT** — minor polish.
- **INFO** — advisory observation (e.g. a concept too vague to audit).

End every finding with a triage tag in the exact form
`(impact=<level>, complexity=<level>)` where each `<level>` is `low`,
`medium`, or `high`:

- **impact** — how much fixing this gap improves the plan's
  correctness, completeness, or clarity (high = the plan is
  unsound, incomplete, or materially open to conflicting behavior
  without it; low = marginal polish).
- **complexity** — how much plan rework the fix demands (high = a
  re-architecture or several new steps; low = a sentence or one new
  criterion).

The tool defers findings whose complexity strictly exceeds their impact,
so be honest: a low-impact, high-complexity gap should say so rather than
be auto-applied.

A finding's restatement and remediation are **sub-blocks**, not inline
markers: each sits on its own, immediately after the finding's bullet line
(separated by a blank line), with its heading at the **start of its own
line** — do not indent it as a list continuation, and do not fold it inline
into the bullet's prose. The heading text is machine-parsed; write it
exactly.

```
- HIGH: [anchor] <gap prose, including any verbatim plan citation>
  (impact=…, complexity=…)

### Restated

<one-line restatement>

### Fix

<one-line remediation>
```

Either sub-block may be absent (a Completeness finding never carries
`### Restated`; a finding with no proposed remediation carries no `### Fix`),
and they may appear in either order — but never fold their content inline
into the bullet, and never quote or paraphrase a plan sentence *inside*
either sub-block that could be mistaken for the block's own heading. A
heading that must start its own line can't be produced by *inline* quoted
prose, but a multi-line verbatim citation can legitimately contain a real
line-starting `### Restated`/`### Fix` line of its own (this section's own
worked example does) — that is exactly why the fenced-code-block
requirement above exists: the parser excludes any match inside a fenced
span from the sub-block boundary search, so a fenced citation can safely
discuss this exact syntax without being confused for the real boundary. An
un-fenced citation that happens to contain such a line is not protected.

For a bare-step Correctness finding raised under "Property coverage versus
delivery mechanisms" above, the `### Restated` sub-block carries the
restatement that rule requires. Omit it entirely for every other finding;
do not emit an empty one.

The `### Fix` sub-block carries the proposed fix. State it at the
**conceptual level** — the intent of the change, phrased so it reads as a natural
continuation of the gap rather than a jump to a mechanical code edit. The
tool shows it to the operator as "what apply will do" and feeds it back to
steer the apply. So:

- Convey intent, not keystrokes: "specify how step 5 distinguishes an
  explicit `--audit-samples` from the default so the suppression policy is
  operationalized", not "add an `if args.audit_samples` branch to
  `_resolve_audit_reuse`".
- Keep it a plan/detail-level remediation — a concept to establish, a
  risk to cover, a criterion to add, a behavior to define. The apply edits
  plan/detail prose only (no code, no new files), so don't propose those.
- One line, and concrete enough that the intent is unambiguous without
  re-deriving it from the gap.
- **Scope the fix to the whole commitment, not to the one spot you
  noticed.** The Method section already made the finding's body enumerate
  every site the trace found; the fix line states the remedy once, at the
  commitment level, and covers that whole enumeration — "define the field
  set once and reconcile steps 5, 7, and 9 to it", not "add the field to
  step 5". A fix line that points at a single spot gets applied at a
  single spot, and the audit re-derives the same gap at a sibling next
  round — which reads as non-convergence when it is really
  under-application. Do **not** split one commitment into one finding per
  site; one finding whose body names the sites and whose fix covers them
  all is what converges.

${response_format_block}

Replace the empty markers with severity bullets where you have findings. A
finding's bullet carries its anchor, optional step evidence, the gap, and
the trailing triage tag; its optional `### Restated` (bare-step Correctness
findings under "Property coverage versus delivery mechanisms" only) and
`### Fix` sub-blocks follow as their own headed blocks, never inline.

## Writing style (strict)

Findings are re-read on every audit and CI gate, and the operator triages
each one against `(a)pply / (s)kip` from the prose alone — keep them tight
*and* self-contained.

- **Use plain, everyday words.** The operator reads these findings under
  time pressure and decides apply-or-skip from the prose alone, so a
  word they have to stop and parse costs more here than anywhere else.
  Write so a competent engineer new to this codebase gets it on the
  first read, without a dictionary. Swap any decorative or unusual word
  for the common one that means the same thing:
  - "always true, so it can never fail" / "proves nothing" — not
    "vacuous" / "vacuously"
  - "true by definition" — not "tautological" / "a tautology"
  - "nothing could prove it wrong" — not "unfalsifiable"
  - "by the way it is built" — not "by construction"
  - "independent" / "unrelated" — not "orthogonal"
  - "level of detail" — not "altitude"
  - "one call that runs several checks" — not "fan-out"
  - "key" / "most important" — not "load-bearing"
  - "unchanged" / "the same" — not "byte-identical"
  - "left out" / "dropped" — not "elided" / "elision"
  - "stop early" / "skip the rest" — not "short-circuit"
  - "set of files" — not "footprint"
  - "approach" / "rule" — not "posture" / "tenet"
  The test is whether you would say the word aloud to a teammate. If
  not, use the plain one. This applies to your *descriptive* prose
  only — never change an exact technical identifier (a type, field,
  flag, function, or named project term), and never drop a path, symbol,
  or example to make a sentence shorter.
- **Lead with the concrete subject.** Open with the thing the operator
  would act on — the command, step, concept, criterion, or section the
  gap concerns — so the first clause names it. The tool clips your first
  line into the finding's title, so an opening like "The Problem statement
  frames the harm as…" or "The Overview describes…" yields a title that
  points at a plan section instead of the gap. Write
  "`reconcile-plan-walk` replays a saved sidecar with no staleness
  check, so a moved plan/codebase is reconciled silently", not "The
  Problem statement frames the harm as a saved reconcile replayed against
  a plan that has moved underneath it".
- **Always name the step when the gap concerns one.** Findings carry no
  separate step field, so the prose is the *only* place the operator
  learns which step is at fault. When a gap lives in (or is caused by) a
  specific step, name it inline by **id and title** — e.g. "step 5
  (`reconcile-plan-walk`)" — not a bare "a later step" or "the deferred
  step". If the gap spans steps, name the boundary ("step 3 establishes …
  but step 5 consumes …"). A plan-wide gap with no owning step says so.
- **Make each finding decidable on its own.** State *what* is missing or
  unsound, *where* it lives (the anchor and step), and *what consequence*
  it has — concretely enough that the operator can choose apply-or-skip
  without re-reading the plan. Don't force the reader to resolve a
  back-reference ("the named harm", "that outcome", "this case", "the
  deferred step") to recover the subject; name the subject directly.
- **For a spec↔detail mismatch, name the direction — never a bare
  "reconcile X and Y".** When the plan body and a detail file disagree,
  say *which side is authoritative* and what the concrete edit is, because
  the two directions are usually asymmetric (a one-line body fix vs. new
  machinery). If the detail file already documents a **deliberate
  decision** the body merely lags, say so — "the body oversells X; step N
  already scoped it to Y and is the more-detailed decision → fix the body"
  — rather than presenting a closed question as an open conflict.
- **Surface the constraint that resolves the finding.** When one
  remediation direction is effectively forced (or foreclosed) by something
  already in the bundle — e.g. "the check emits a single severity with a
  binary match, so there is no confidence dimension to weight" — state that
  constraint in the finding. A finding that hides the fact that collapses
  the decision reads as open when it is already closed.
- **Quote both sides of a mismatch verbatim with their anchors.** When a
  finding turns on two passages disagreeing, paste the conflicting phrases
  (body vs. detail) and cite each by its anchor (section / step id /
  `file:symbol`), so the operator verifies the conflict on sight instead of
  re-reading both artifacts.
- **One finding per bullet; two or three sentences if that is what it
  takes to state subject + gap + consequence — but no padding.**
- **Active voice, imperative mood.**
- **No historical narration.** Drop "previously", "used to", and
  parenthetical asides. State the current concept gap with an anchor.
- **Strip filler** — cut "it is worth noting that…", "in this case…".
- **Treat confidence as display-only evidence context.** A `confidence:
  supported`, `confidence: limited`, or `confidence: unknown` label never
  permits a carried finding to be skipped, narrowed, deferred, reprioritized,
  or otherwise altered because of it.

${carried_findings_block}
${intent_block}${scope_contract_block}
${project_context_block}## Plan body

${plan_body_block}

## Detail files (implementation bundle)

${detail_bundle_framing_block}

${detail_bundle_status_block}
${detail_files_block}
