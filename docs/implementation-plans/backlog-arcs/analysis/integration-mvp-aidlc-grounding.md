# AI-DLC as actually defined, and how Integration's MVP maps onto it

**Status (2026-09-08):** dated grounding. The AI-DLC facts (five phases, the `mob` stage mode, the contribution-file shape, the approval gates) remain evidence of what upstream defines at v2.5.62. The "how Integration maps onto it" prose and the vocabulary map describe the retired 2026-08-28 two-phase mob-loop definition, not Integration's product; Integration's four-phase definition is in `integration/docs/concepts/integration-mvp-domain-disposition.md`.

Grounded in `<methodology-root>` (v2.5.62), read
directly. Three corrections to the loose reading matter for the MVP.

## Correction 1 — there are five phases, not three

`initialization` (0, 3 stages) · `ideation` (1, 7) · `inception` (2, 8) ·
`construction` (3, 7) · `operation` (4, 7). Enum in
`core/aidlc-common/protocols/stage-definition.md`; 32 stage files on disk.
Phases are strictly sequential with a verification gate at each boundary.

**Ideation, not Inception, owns intake.** Ideation ends at stage 1.7 with
`initiative-brief.md` + `decision-log.md` — "a one-pager combining: Intent and
problem statement, Market validation summary, Feasibility and risk highlights,
Scope boundary, Concept visuals, Team plan, Go/no-go recommendation."

**AI-DLC Inception is requirements→design→decomposition**: requirements
analysis (2.3) → user stories (2.4) → mockups (2.5) → application design (2.6)
→ units generation (2.7) → delivery planning (2.8). It ends with `bolt-plan.md`
plus `unit-of-work-dependency.md`'s machine-readable DAG.

**So Integration's stated "inception phase" spans AI-DLC Ideation 1.x plus the front
of Inception 2.x**, and Integration's stated "construction phase" — plan-tool from
roadmap to application — absorbs the *back* of AI-DLC Inception (2.6 application
design, 2.7 units generation) because that is exactly what `plan-tool roadmap`
stages 3 and 4 already do. Name the divergence rather than claiming alignment.

## Correction 2 — "mob" means two different things, and Integration wants both halves

- **Sense A, mechanical:** `mode: mob` is a stage *communication topology* —
  "mesh: one room, cross-talk, dissent recorded". One **lead agent** owns the
  artifacts; N **support agents** are dispatched **in parallel, mutually
  blind**, each writing a contribution file; the lead integrates; unresolved
  items are triaged — judgment calls go to the human mid-stage, knowledge
  disputes get **round 2, two rounds maximum**. Exactly one shipped mob stage:
  **2.4 User Stories** (lead `aidlc-product-agent`; supports design, developer,
  quality).
- **Sense B, organizational:** a mob is a **human team**. Stage 1.5 is
  "Team Formation & Mob Planning" and produces `mob-composition.md`; 2.8
  produces `team-allocation.md`, "Bolt-to-mob assignment".

**Integration's design is sense A's round structure with sense B's human groups in the
collaborator slots.** That is a coherent, faithful extension — and the stated
divergence ("don't inject live chat feedback, it breaks the discussion flow")
is *literally the methodology's own `mutually blind` property*, applied to
people instead of agents. It is not a departure from AI-DLC; it is the same
rule at a different participant type. Say so in the brief.

## Correction 3 — the contribution file is the return channel, and it has a shape

`stage-protocol.md` §11 fixes it:

```markdown
**Collaborator:** [agent-slug]

## Contribution
[substantive content, written so the lead can integrate it directly]

## Positions
- AGREE: [aspect endorsed] — [one-line rationale]
- OBJECT: [aspect disputed or missing] — [one-line rationale]
```

The identity-marker first line is mandatory and is the **deterministic
completion evidence**: the engine refuses approval while any declared
collaborator's contribution file is missing or unmarked. Maintained dissent is
"quoted verbatim in the completion summary at the gate — never silently
averaged away."

**Integration gets its mob-response contract for free here.** A mob's return artifact
is a contribution document with `Contribution` + `Positions (AGREE/OBJECT)`,
and "every seeded mob has returned a marked contribution" is a checkable,
binary completion condition — exactly the kind of observable
`CLAUDE.md` § "Validating a semantic property you cannot observe" demands.

## The pattern worth stealing outright: questions files

Every stage writes `<stage>-questions.md` with `[Answer]:` tags and options
A–E plus a mandatory "X. Other (please specify)", then offers a **tri-mode
flow — guided (interactive) / self-guided (edit the file) / chat — and "All
three converge on the file."**

For a chat-centric product this is the load-bearing idea: **the document is
canonical; chat is one of several ways to fill it in.** It is also the answer
to "how does a chat UI avoid becoming the source of truth", which
`rule-durable-artifacts` already requires of Integration.

Two more gates worth copying verbatim in spirit:
- **Consolidated Summary Confirmation** — before generating, restate what was
  understood and require the exact answer `Looks correct`.
- **Approval is a hard stop** — "cannot be inferred, auto-approved, or
  skipped"; after 3 rejections an `Accept as-is` escape appears.

## Vocabulary map — AI-DLC to Integration/plan-tool

| AI-DLC | Integration MVP | plan-tool |
| --- | --- | --- |
| Ideation 1.1–1.6 intake | Inception chat: ingest the project definition | — |
| 1.5 `mob-composition` | the groups a project seeds | — |
| 2.4 mob elaboration + contribution files | **seeded mob conversations, returned as contributions** | — |
| 1.7 `initiative-brief` + `decision-log` | **the synthesized business need + workflow description** (the phase handoff) | becomes the `roadmap --from-existing` concept brief |
| 2.3 requirements / 2.6 application design | — | `roadmap` stages 1–3 (`01-domain`, `02-constraints`, `03-components`) |
| 2.7 `unit-of-work` + dependency DAG | — | `roadmap` stage 4 plan rows + `ordering`/`assumptions` |
| 2.8 `bolt-plan` sequencing | — | plan-seed promotion order; `create` per row |
| 3.1–3.4 per-unit design | — | `detail` per step + the completeness audits |
| 3.5 code-generation (`workspace_requires`) | one bounded step in the worker | `run --commit` (its test-authoring gate is the analog) |
| 3.6 build-and-test | — | `run`'s per-step suite gate; `reconcile-code` |
| stories → Jira | optional epic/story export | `jira --epic` (Markdown/JSON, no tracker API) |
| Bolt autonomy ladder / halt-and-ask | run approval + status stream | `run` step gating |

**The honest gap:** AI-DLC has no equivalent of plan-tool's completeness audit
and reconcile loop, and plan-tool has no equivalent of AI-DLC's mob topology or
its questions-file gate ritual. The MVP's whole thesis is that the second half
of one and the first half of the other compose.
