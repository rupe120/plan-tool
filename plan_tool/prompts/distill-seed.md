# Distill a free-form seed into a canonical plan body (or propose a split)

You are being called by `plan-tool create` as a **first pass** over a raw,
possibly large or messy seed document. Your job is pure reorganization: read
the seed and either (a) distill it into the canonical H2 body sections a single
plan needs, or (b) if the seed actually describes **multiple independent
plans**, propose splitting it into several plans instead.

**Do not inspect the codebase** (no file reads, no searches). This is a
text-reorganization pass only — work solely from the seed below.

## Seed-audit boundary

The caller should review this seed for correctness before `create`: material
correctness issues should be resolved until they converge. This distill pass
does **not** perform that review and must not invent corrections.

Seed completeness is intentionally narrow. Do not add concepts merely because
a finished plan would later need implementation edge cases, per-step mechanics,
fixtures, file lists, or wording polish. Only a **HIGH** or **CRITICAL**
conceptual omission — one that contradicts the seed's Outcome/scope fence,
leaves a settled decision without a necessary counterpart, or makes a coherent
plan impossible to derive — belongs in seed review. Preserve the seed's
decisions and boundaries exactly; later plan/detail audits own ordinary
completeness.

## Source seed (line-numbered)

Each line is prefixed with its 1-based line number followed by a tab. The
numbers are for split ranges and evidence citations; ignore them when writing
derived section prose.

```
${numbered_source}
```
${repair_block}

## Decide: one plan, or many?

Choose **split** only when the seed describes work that should be **separate
top-level plans** — distinct, independently-shippable efforts with little shared
implementation (e.g. "add OAuth login" + "migrate the billing cron to a queue" +
"redesign the settings page" crammed into one doc). When in doubt, prefer
**single**: a large seed about *one* cohesive effort is still one plan.

A seed's claim of shared implementation only counts as evidence for **single**
when it **names the shared implementation concretely** — a specific function,
module, or file both parts would modify. **Both parts reading or writing the
same data source is not shared implementation** — two efforts that both
consume the same table, log, or sidecar sequence are still separate plans
unless the seed also names the code they'd share. An unnamed or data-only
coupling claim counts as no claim: fall back to the default above.

A split proposal must contain **2 or more** plans. A "split" with a single plan
is just a single plan — emit `single` instead.

## Output

Respond with **ONLY** a single JSON object — no prose, no fences, no preamble,
no trailing remark. The first character of your response must be `{` and the
last `}`.

### Single-plan shape (`outcome: "single"`)

```json
{
  "outcome": "single",
  "sections": {
    "Overview": "<non-empty markdown body derived from the stated goal>",
    "Problem statement": "<non-empty markdown body derived from the stated need>",
    "Architecture": "<non-empty markdown body derived from the stated design>",
    "Out of scope": "<markdown body, or null>",
    "Risks": "<markdown body, or null>",
    "Testing": "<markdown body, or null>",
    "Acceptance criteria": "<markdown body, or null>",
    "Deferred": "<markdown body, or null>"
  },
  "evidence_spans": {
    "Out of scope": [{"start_line": 1, "end_line": 1}],
    "Risks": null,
    "Testing": null,
    "Acceptance criteria": null,
    "Deferred": null
  }
}
```

`sections` uses exactly these 8 keys (case-sensitive — note the lowercase
second word in `Problem statement`, `Out of scope`, `Acceptance criteria`).
The `Steps` and `References` sections are owned by separate round-trips —
**do not** emit them. Every one of the 8 keys must be present. `Overview`,
`Problem statement`, and `Architecture` must be non-empty strings for a
`single` result; only the five evidence-only fields may be `null`.

`evidence_spans` contains exactly `Out of scope`, `Risks`, `Testing`,
`Acceptance criteria`, and `Deferred`, plus `Input` only when `Input` comes
from ordinary source prose rather than a supplied `## Input` heading. Each
value is `null` or a non-empty source-ordered list of `{ "start_line": int,
"end_line": int }` objects. Ranges are inclusive, 1-based, non-overlapping
for their field, and select body text rather than a heading alone. Cite source
lines for every non-null evidence-only field and every prose-backed `Input`:
the caller publishes those lines, not your paraphrase. A prose-backed `Input`
must have a non-null span; do not add an `Input` span when preserving a supplied
`## Input` body.

`Input`, `Scope guardrails`, `Audit guardrails`, `Expected placement`, and `Stack` are
the only recognized optional keys. Emit `Input` only when the seed establishes
an existing contract this plan consumes. Omit each guardrail key unless the
source seed supplies its matching H2 heading with content. When the seed
supplies one of the four guardrail headings, include that exact key and
preserve its body as a separate section without rewriting, expanding, or
replacing its constraints.

### Multi-plan split shape (`outcome: "split"`)

```json
{
  "outcome": "split",
  "plans": [
    {
      "title": "<short human title for this plan>",
      "suggested_slug": "<kebab-case-slug>",
      "rationale": "<one sentence: what this plan covers and why it's its own plan>",
      "start_line": <1-based inclusive first seed line for this plan>,
      "end_line": <1-based inclusive last seed line for this plan>
    }
  ]
}
```

## Field rules

- **Single-plan section catalog** — each bullet names the key, a policy tag
  (`[derive from intent]` or `[evidence-only]`), and the shape the section
  should take:

${section_shapes_block}

- Each section value is either a markdown string or `null`. Do **not** include a
  leading `## Heading` line in the value — the renderer writes the heading.
- **Preserve every concrete file path, symbol, identifier, command, and config
  key verbatim.** Downstream steps verify these against the real codebase, so a
  paraphrased or invented path breaks them. Copy them exactly as the seed wrote
  them.
- **Compress prose, never invent facts** — honor each section's policy tag:
  - `[derive from intent]` (Overview, Problem statement, Architecture):
    structure these from the seed's stated goal even when it carries no
    matching heading — a seed describing *what* to build is the source for its
    Overview, the *why* is its Problem statement, the implied design is its
    Architecture. This is restating intent, not inventing facts. A `single`
    response cannot leave these fields blank or use placeholders.
  - `[evidence-only]` (Out of scope, Risks, Testing, Acceptance criteria,
    Deferred): do not add claims, risks, tests, criteria, or scope the seed
    doesn't state. `null` is the right answer for one the seed doesn't address
    — do not fabricate.
  - `[conditional]` (`Input`, `Scope guardrails`, `Audit guardrails`,
    `Expected placement`, `Stack`): emit `Input` only for a seed-established existing
    contract. For an `Input` established outside `## Input`, cite the exact
    raw-source lines in `evidence_spans.Input`; they replace your summary at
    publication. Emit guardrails only for their matching supplied headings.
    Preserve supplied guardrail text verbatim; never invent a guardrail or
    make a new scope, audit, placement, or stack decision.
- **Concept-owned scope abstention** — `Out of scope` and `Deferred` are
  finalized by the reviewed concept record. Keep both keys in the eight-key
  object, but return `null` unless copying explicit seed evidence for that
  later review; never decide, expand, or reconcile those boundaries here.
- **Stage-separated replay preservation** — When source `Testing` or
  `Acceptance criteria` contrasts what a bare plan must establish with what
  step detail may establish, retain the named property, the routes it covers,
  and both stage dispositions. This is scope and acceptance evidence, not an
  implementation test list. Do not collapse it into “add tests,” move a
  detail-owned mechanism into `Architecture`, or invent a carrier, attachment,
  ordering rewrite, or fixture the source does not settle.
- For split plans, `suggested_slug` is lowercase kebab-case (`a-z`, `0-9`,
  hyphens). `start_line`/`end_line` are 1-based inclusive line numbers from the
  numbered seed above; ranges should cover the seed without gaps where possible
  and must satisfy `start_line <= end_line`. They are advisory carving aids — the
  `title` and `rationale` carry the authoritative boundary.

## Constraints

- Output JSON only — the caller pipes your response through `json.loads`. Any
  prose before or after the object causes a parse failure and triggers a single
  repair retry; a second failure aborts.
- Emit exactly one of the two shapes. `outcome` must be `"single"` or `"split"`.
- Do not emit a refusal shape. The caller owns refusal after this prompt's one
  repair retry remains invalid.
- Do not emit a `Steps` or `References` key in `sections`; do not add keys
  outside the documented shapes.
