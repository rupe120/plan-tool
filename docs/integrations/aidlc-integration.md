# AI-DLC integration

How `plan-tool`'s `roadmap` verb relates to the AI-DLC framework and the
orchestration layer above it: the boundary, where they touch, and what's
shipped. For backend CLIs (Claude Code, Codex, Cursor), see `integrations/`.
Full design and provenance are in the handoffs linked below.

## What AI-DLC and the orchestration layer are

**AI-DLC** is an external workflow framework from AWS Labs
([awslabs/aidlc-workflows](https://github.com/awslabs/aidlc-workflows)) with five
phases: **Initialization → Ideation → Inception → Construction → Operation**.
Each phase is built of stages with typed artifacts, epistemic tags on claims
(`[assumption]`, open questions, etc.), and gated approval.

An **orchestration layer** sits above `plan-tool`. It runs a real project (an
"intent") through the framework, produces the framework's artifacts, and owns
the **connector** — the layer that maps those artifacts onto `plan-tool`'s
generic vocabulary. `plan-tool` never has a connector of its own; that mapping
is entirely the orchestration layer's.

`plan-tool` depends on no orchestration layer and works standalone, but it is
built to be driven from above: any caller can use its documented interfaces —
[headless operation](../OPERATIONS.md#running-headlessly), plan frontmatter,
saved reports, and exit codes.

`plan-tool`'s `roadmap` verb is the Inception-stage engine: it writes
`01-domain.md` → `02-constraints.md` → `03-components.md` →
`04-roadmap.md` (`ROADMAP_FORMAT.md`). It is deliberately **framework-
ignorant** — the central design rule, settled 2026-09-11 and not reopened,
is that `roadmap` never learns AI-DLC artifact kind names, stage slugs, or
record paths.

## The boundary: three layers, one rule

| Layer | What it is | Who owns the mapping |
| --- | --- | --- |
| Framework semantics | Artifact kinds, epistemic conventions, question/review shapes, phase-boundary checks | AI-DLC's workflow profile and the orchestration layer's connector |
| Runtime layout | Record paths under `aidlc/spaces/<space>/intents/<dir>/`, hooks, audit shards | The orchestration layer's AI-DLC connector only |
| Engine contract | What `roadmap` accepts, produces, and gates | `plan-tool` |

`roadmap` learns **generic concepts** the framework happens to need — typed
input roles, inherited-versus-derived decisions, open questions,
obligations, coverage output, and a shared frame for the model requests that
can change what artifacts mean — never AI-DLC's own names for them. A
connector mapping can change with an orchestration-layer workflow profile without a
`plan-tool` release, and a `plan-tool` role can serve a non-AI-DLC producer
just as well.

## Where the two systems touch

### 1. Input roles — the source-material touchpoint

This is the actual seam: the typed roles `roadmap` accepts, and how the
connector maps AI-DLC artifacts onto them.

| Role | Carries | Reaches | Class |
| --- | --- | --- | --- |
| `intent` | Problem, users, success signal | Stages 1–4, as content | grounding |
| `scope` | Central outcome and fence | The seam frame (§4 below) | grounding |
| `constraints` | Hosting facets, quality dispositions, operating limits | The seam frame | grounding |
| `experience` | User flows, screen sketches | Stage 1 only, as content | grounding |
| `decisions` | Confirmed answers, recorded settled decisions | The seam frame | inherited |
| `open-questions` | Unresolved upstream items | The seam frame | open |
| `obligations` | Accepted-risk findings with a required action | The seam frame | obligation |
| `rules` | Selected workflow rule sections | The seam frame | grounding |
| `approval-evidence` | Approval memo, decision log, phase check | Nowhere — provenance only | provenance only |
| `judgment` | Proto-decomposition (e.g. a prioritized backlog), the stakeholder map | Nowhere — never rendered into a stage prompt | review-time only |

The connector maps `intent-statement` → `intent`, `scope-document` →
`scope`, the feasibility/constraint artifacts → `constraints`, `wireframes`/
`user-flow` → `experience`, question files and rule layers' `Decided`
entries → `decisions`, each artifact's open entries → `open-questions`, the
audit's accepted-risk findings → `obligations`, selected rule sections →
`rules`, approval-handoff output → `approval-evidence`, and the intent
backlog / stakeholder map → `judgment`. `judgment` and `approval-evidence`
are excluded from every stage prompt at the prompt boundary itself, not by
documentation convention — a prioritized backlog handed to a stage as
grounding is exactly the enumeration hazard that produces spurious plan
rows.

### 2. Source identity and change control

The source set (whatever roles are present) is frozen at the first artifact
write: a content digest per source plus a root digest over the set, bound
via `roadmap_source_identity.py`. On drift, behavior follows a declared
policy — `strict` refuses and names the two supported routes (feedback rows
or a successor lineage); `relaxed` records the change, announces it, and
continues. The connector also passes the upstream approval receipt as
provenance, so the set is provably the approved snapshot.

### 3. Citation snapshots — finer-grained, item-level checking

On top of the file-level identity above: cited items are snapshotted and
compared on every run. A changed cited item marks its rows stale and raises
one question per changed item; a broken anchor does the same. A stale plan
row blocks seed materialization until resolved. Uncommitted sources block
the run outright.

### 4. Carried (inherited) vs. derived decisions

A decision row gains an origin: **inherited** (citing the source item that
settled it — `roadmap` may anchor to it but not re-decide it) or **derived**
(`roadmap` made it, and the rejected-alternative gate applies). An inherited
decision carries a rejected alternative only when the upstream record
itself states one, verbatim — the other options in an upstream question are
never recorded as if `roadmap` considered and rejected them. A fence entry
becomes an inherited decision only when a real row exists to anchor to; a
carried decision with no anchor is a hard refusal, not a forced one.

### 5. Open questions and obligations

An unresolved point becomes one open question with a stable id, options, a
recommendation, and a blank answer — raised once, cited by every later
stage rather than re-guessed. A declared mode (`stop` or `provisional`)
governs what happens next. Upstream open questions (and RAID-log
assumptions) seed this same list before stage 1 runs. Separately, an
accepted-risk finding from the framework's approval records becomes an
**obligation**: it needs exactly one disposition — discharged, deferred, or
not applicable — and a gate refuses an undisposed one.

### 6. The seam frame — which model requests see the box

Each run builds one deterministic, closed frame from the box roles
(`scope`, `constraints`, `decisions`, `open-questions`, `obligations`,
`rules`), fenced as data that bounds the work without instructing the
model. It reaches the requests that can change what artifacts mean first:
the four authoring stages, stage feedback revision, structural revision,
candidate revision, and seed drafting — and seed drafting copies the frame
items a plan row cites into the seed, so `create`, `detail`, and `run`
inherit the box transitively. A project with no typed upstream box (a plain
hand-written brief) gets an empty frame and `roadmap` behaves exactly as it
does today.

### 7. Coverage output — the Inception → Construction boundary

A machine-readable coverage projection, per source item: `covered`,
`deferred`, `not-applicable`, `gap`, or `stale`. The connector maps this
onto the framework's phase check — the evidence it needs for
"explicit coverage or an explicit skip for every step in the selected
scope."

## Current status

**Design is settled; implementation is a narrow slice of it so far, and no
`roadmap` run has ever used the real AI-DLC corpus.** Don't read "settled
design" as "shipped code" — they're tracked separately below.

| Item | Status | Reference |
| --- | --- | --- |
| The boundary, the role vocabulary, and touchpoints 1–7 above | Settled design, 2026-09-11; none reopened without new evidence | `handoffs/2026-09-11-roadmap-aidlc-inception-fit.md` § "Settled decisions" |
| Stage-run source-identity + strict/relaxed drift policy | **Shipped** | `handoffs/2026-09-14-roadmap-aidlc-integration-delivery.md` |
| Changed-brief rebind confirmation (`BACKLOG` #367) | **Shipped, closed** | `docs/history/backlog-decisions.md` |
| Carried settled decisions with citations (`BACKLOG` #384) | **Shipped, closed** | `docs/history/backlog-decisions.md` |
| Per-stage supplementary sources with declared roles (`BACKLOG` #383) | **Held** — waiting on a comparison-proven per-stage grounding gap, not scheduled | `BACKLOG.md`, entry #383 |
| `roadmap --view status --json` (`BACKLOG` #385) | **Held** — evidence-gated on an orchestration layer having a concrete connector consumer | `BACKLOG.md`, entry #385 |
| Citation snapshots, obligations, the seam frame, coverage projection (touchpoints 3, 5, 6, 7) | Settled design; not yet built as running code | Same handoff, § "The design" |
| An orchestrated `roadmap` run against the real AI-DLC corpus | **Has never happened** | Both 2026-09-11 and 2026-09-14 handoffs state this explicitly |

**Explicitly still open** (not decided; don't treat any of these as settled).
Only the source carrier has been decided, for now: #384 ships on the single
brief and #383 stays held. The rest wait on an evidence trigger:

- RAID mapping, hosting and quality facts reaching stage 2, and the
  open-question default mode wait on the unbuilt obligations and settle-once
  questions capabilities.
- Framework requirement IDs and the Inception-step coverage decision (does
  `roadmap` take on requirements analysis, or does the orchestration layer's
  workflow profile explicitly skip it) wait on that workflow profile and connector.
- Frame reach, size, scope-list rendering, and fit review are parked with the
  shared seam frame, which is selected only when a revision route changes
  meaning outside the proven box.

The list, its options, and dependencies live in
`handoffs/2026-09-11-roadmap-aidlc-inception-fit.md` § "Open design choices".

## What stays out of scope for `plan-tool`

- Running AI-DLC, mutating the orchestration layer, or starting a `roadmap` run
  against its corpus.
- The connector mapping itself, rule selection, and question presentation —
  orchestration-layer application work, recorded here only as the other half of each
  touchpoint.
- AI-DLC runtime paths, intent directories, stage slugs, hooks, audit
  shards, and approval-receipt storage — the orchestration layer's entirely.

## Where the full detail lives

- `handoffs/2026-09-11-roadmap-aidlc-inception-fit.md` — the full design,
  settled decisions, and open choices (this page's primary source).
- `handoffs/2026-09-14-roadmap-aidlc-integration-delivery.md` — the
  delivery record: what shipped, the seam contract, and the ordered
  delivery path.
- `handoffs/2026-09-11-integration-seam-resume-order.md` — the cross-repository
  checkpoint and orchestration-side execution fence.
- `docs/evidence/roadmap-aidlc-intake-comparison-20260916.md` — the
  controlled comparison against a real, approval-bound Gate-1 corpus
  that confirmed #384 and continues to hold #383.
- `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md` — the
  canonical order of remaining work: corpus comparison → #384 → #383;
  #385 stays independent and evidence-gated.
