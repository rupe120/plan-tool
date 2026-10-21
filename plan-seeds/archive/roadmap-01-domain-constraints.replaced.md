> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-01-domain-constraints.md`.
> Preserved here for history; do not edit.

# Plan seed: roadmap 01 — the verb skeleton, the artifact contract, and the domain + constraints stages

This file is a `plan-tool create` input. Use it via:

```
plan-tool create roadmap-01-domain-constraints --from-existing plan-seeds/roadmap-01-domain-constraints.md --iterate
```

> **Source and lifecycle.** Implements BACKLOG **#208** — stage **01 of 04**
> in the ordered `roadmap` group (full arc lives in #208, the group anchor;
> naming per the "Ordered efforts" directive in `BACKLOG.md`) — and inherits
> #208's scope contract, narrowed to this stage. The final docs/status step
> must reconcile `BACKLOG.md` #208: mark it plan-authored while execution is
> pending and record stage 01 as shipped, but **leave the entry in place** —
> it is the arc anchor and is removed only when all four stages ship.
> Out-of-scope findings route to the backlog files, never into this plan.
>
> **Stage tool state.** No predecessor: at HEAD there is no `roadmap` verb and
> no roadmap artifact family. This stage must not reach into **02**
> (`03-components.md` and its convergence loop), **03** (component→plan
> mapping, draft-seed emission, the `create` `SplitProposal` hand-off line),
> or **04** (the framework-lens registry and `--framework`). It ships the
> generic quality-attribute list **inline at the seam a lens descriptor will
> later supply**, so stage 04 plugs in rather than redesigns.

---

## Overview

`plan-tool roadmap <slug> --from-existing <concept.md>` opens a
project-altitude authoring pipeline one rung above `create`: a concept brief
becomes an ordered set of plan seeds, by way of explicit abstraction layers
rather than one call. This stage builds the verb, fixes the artifact family
and its contract, and ships the first two layers — the **domain model**
(entities, business rules, workflows) and the **system constraints** (quality
attributes as prioritized tradeoffs).

When it ships, a repo can turn a concept brief into gated `01-domain.md` and
`02-constraints.md` under `docs/implementation-plans/roadmaps/<slug>/`, and
re-enter the pipeline at any stage after hand-editing an earlier artifact.
No seeds and no plans are produced yet — that is stage 03.

## Problem statement

`create` decomposes one effort into steps. Nothing decomposes a *project* into
efforts, so a project-sized concept enters the pipeline as a single oversize
seed. `create` already detects this — the distill first-pass returns a
`SplitProposal` when a seed spans independent efforts — but its remedy is
reactive text partitioning by line range, which carves prose the author
already wrote. It cannot supply the architecture judgment that decides what
the efforts *should* be, so the resulting units are as good as the brief and
no better, and a plan too large to audit as one entity stays that way.

The layering is the fix, not a garnish. Components and their design patterns
are the joint of domain shape against system constraints; deriving them
without first fixing both inputs produces patterns selected for a system
nobody described. Staged artifacts also make a wrong turn cheap: a bad domain
model is visible and correctable at the point it is made, instead of silently
poisoning every layer beneath it.

## Architecture

**Rule 1 layering (deterministic core, judged edge).** Each stage is one
directed judged call fenced on both sides by deterministic work:

1. **Assembly (no Claude):** read the concept brief; resolve the roadmap
   directory; on re-entry, load and re-gate every artifact below the target
   stage from disk.
2. **One directed call per stage,** with a forced output contract — required
   sections, closed vocabulary, machine-readable frontmatter inventory.
3. **Response gates,** below; a failing reply is re-prompted with the
   violation named, bounded by a retry cap (`detail`'s pattern).
4. **Consumption:** write the artifact, render next steps, exit.

**Two calls, not one — settled here.** #208 leaves open whether domain and
constraints collapse into a single call. They do not: constraints anchor to
domain ids, so a single call would let an ungated domain model become the
anchor set for its own constraints, and the cross-artifact gate could never
fail. The gate between them is the reason the layer exists.

**Artifacts.** `docs/implementation-plans/roadmaps/<slug>/` (a sibling of
`plan-details/`), one file per stage, each carrying the plan dual contract:
YAML frontmatter is the machine-readable inventory and source of truth, the
prose below it is for humans. A new `ROADMAP_FORMAT.md` governs the family the
way `PLAN_FORMAT.md` governs plans; stages 02–04 extend it rather than
re-specifying it.

- `01-domain.md` — `entities`, `rules`, `workflows`, `decisions`. Rules and
  workflows reference entity ids.
- `02-constraints.md` — the quality attributes as **prioritized tradeoffs**
  with rationale, each anchored to the domain elements it bears on, plus the
  stage's decisions. Not a checklist: a constraint set that ranks nothing has
  decided nothing.

**Decision records (the guess-vs-ask mechanism).** The pipeline is
non-interactive, so every option point becomes a durable record rather than a
prompt: the chosen option, at least one alternative with why it lost, an
anchor to the element it bears on, and exactly one status from a closed
enum — `settled-by-guess` for marginal calls, `pending` for load-bearing ones
a later operator must confirm. Pending records surface in the command's
summary and never block. Confirming them interactively is deferred; the
artifact shape is identical either way, so that follow-up adds a walk, not a
redesign.

**Response gates (deterministic, per Rule 4).**

- *Closed vocabulary:* decision status and constraint disposition are enums;
  an unknown token fails the gate rather than opening a category.
- *Referential integrity:* every entity id a rule or workflow cites resolves
  to a defined entity.
- *Anchoring:* every constraint cites at least one `01-domain.md` id — the
  first link of the entity → component → plan chain the later stages extend.
- *Totality:* every quality attribute in the active list carries exactly one
  disposition — prioritized with a rationale, or deferred with a decision
  record. No silent omissions.
- *No orphan inventory:* every frontmatter row has prose describing it. A row
  is not a description — the "a key row is not a scene" failure recorded in
  #188, which shipped once as a fix and was not one.

**CLI shape.** One verb with resumable stages, not four verbs: `--from-stage
N` re-runs from stage N, re-reading and re-gating the artifacts below it, so
the correction loop is *edit the artifact, re-run downstream* with no special
mode. The verb spends Claude, so it opens a run log. Per the exit-code
convention it exits 0 on any completed run — pending decisions and unresolved
tradeoffs are output, not failure — and non-zero only on failure-to-complete.
Recommend-only throughout: it writes its own artifacts and nothing else, never
invokes `create`, and never touches a plan or the manifest.

**Ladder position (Rule 3).** Naming a domain and ranking constraint
tradeoffs from a prose brief is irreducibly rung 5 — no restructuring makes
the question disappear, and there is no consumer to observe or prior artifact
to count. Everything *around* it is pulled down the ladder: referential
integrity, disposition totality, vocabulary legality, and orphan-row
detection are rung-2 mechanical checks, so the judged surface is confined to
the naming and the ranking.

Suggested decomposition: the artifact contract and `ROADMAP_FORMAT.md`; the
verb skeleton with assembly, run log, and the `--from-stage` seam; the domain
stage with its prompt and gates; the constraints stage with its prompt,
totality gate, and cross-artifact anchor gate.

## Out of scope

- Everything owned by later stages: `03-components.md` and pattern selection
  (02), component→plan mapping, draft-seed emission and the `create`
  `SplitProposal` hand-off line (03), the lens registry and `--framework`
  (04). A finding about any of them is deferred to that stage's backlog entry.
- Interactive confirmation of `pending` decisions — the artifact records
  them; resolving them by walk is a follow-up.
- Any convergence loop. This stage ships the bounded re-prompt-on-gate-failure
  retry only; the full loop is stage 02's, on components.
- Invoking `create`, writing seeds, registering anything in the manifest, or
  mutating any plan or detail file.
- Cross-artifact *coherence auditing* beyond the named gates; a roadmap-level
  audit surface is a separate effort.
- Grounding the domain model against an existing codebase. The input is a
  concept brief; a greenfield project has no code to read.

## Risks

- **A wrong domain model poisons every layer beneath it.** Mitigated
  structurally rather than by prompt quality: the artifact is written before
  constraints run, gated on its own contract, and re-enterable by hand edit —
  the operator corrects at the cheapest point instead of at the end.
- **Guessing in the dangerous direction** — a load-bearing tradeoff silently
  recorded as `settled-by-guess`. Mitigated by biasing the prompt toward
  `pending` when unsure, the same default-to-cautious posture #181 takes; a
  spurious `pending` costs a glance, a wrong `settled-by-guess` costs the
  architecture.
- **Ceremony proportionate to nothing.** A concept brief for a small project
  can produce an elaborate domain model that reads as authoritative. The
  artifacts are recommend-only and cheap to discard, and the seed's own
  Overview says what shipping looks like; nothing downstream consumes them
  until stage 03 exists.
- **A gate that needs judgment isn't a gate.** If a check cannot be made
  deterministic, it ships as prose guidance in the prompt, not as a gate that
  passes on vocabulary conformance while asserting nothing — the withdrawn
  test-ordering contract is the recorded precedent.
- **Contract churn across stages.** `ROADMAP_FORMAT.md` is authored here and
  extended three more times. Mitigated by specifying only what stages 1–2
  need, and by pinning the lens seam so stage 04 adds a descriptor rather than
  reshaping the constraints artifact.

## Testing

Hermetic and fixture-driven, with every invoker stubbed per `TESTING.md`; the
autouse backend gate must stay green, so no test spawns a real backend. Per
Rule 2 the assertions are about contract conformance, never judgment content —
no test asserts which entities a brief yields.

- Each gate rejects a violating stub reply and re-prompts with the violation
  named: an unresolvable entity reference, an illegal status token, a quality
  attribute with no disposition, a constraint anchored to nothing, an
  inventory row with no prose.
- A conforming stub reply round-trips: artifact written, frontmatter parses,
  ids unique, run log opened and closed.
- `--from-stage 2` reads a hand-edited `01-domain.md` from disk, re-gates it,
  and regenerates downstream; a stage-1 artifact that fails its own gate on
  re-entry stops with a non-zero rc rather than building on it.
- The retry cap terminates on a persistently violating reply instead of
  looping.
- A completed run with `pending` decisions exits 0 and names them in its
  summary.
- `plan-tool validate`'s capability-catalog check stays green with the new
  surface registered, and the generated `docs/cli/` reference matches the
  parser.

## Acceptance criteria

- `plan-tool roadmap <slug> --from-existing <concept.md>` writes gated
  `01-domain.md` and `02-constraints.md` under
  `docs/implementation-plans/roadmaps/<slug>/`, and writes nothing else.
- `ROADMAP_FORMAT.md` specifies both artifacts' frontmatter and required
  prose sections, and the shipped gates enforce exactly what it specifies.
- Every gate above demonstrably rejects a violating reply and re-prompts
  naming the violation; a conforming reply passes.
- Every quality attribute in the active list carries exactly one disposition
  in a passing `02-constraints.md`, and every constraint resolves to at least
  one `01-domain.md` id.
- Every decision record carries a chosen option, at least one alternative
  with its rationale, an anchor, and exactly one enum status.
- `--from-stage N` regenerates from a hand-edited lower artifact; a lower
  artifact failing its gate stops the run non-zero.
- A completed run exits 0 regardless of pending decisions; non-zero is
  reserved for failure-to-complete.
- The verb writes a run log, invokes no other command, and mutates no plan,
  detail, seed, or manifest.
- `CAPABILITIES.md`, `USE_CASES.md`, `RUNBOOK.md`, and generated `docs/cli/`
  cover the new surface; `BACKLOG.md` #208 is reconciled per the lifecycle
  note above.

## Deferred

- Interactive resolution of `pending` decision records (the `scope-review`
  pattern, human-at-TTY only).
- Grounding a roadmap against an existing codebase rather than a greenfield
  brief.
- Roadmap-level coherence auditing across artifacts.
- Decision telemetry for roadmap stages.
- Any convergence loop over roadmap artifacts.
