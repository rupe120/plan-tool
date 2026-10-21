> **Replaced**: this file has been superseded by `docs/implementation-plans/2-deferred-select-promote.md`.
> Preserved here for history; do not edit.

# Plan seed: select surfaced deferrals and promote them to backlog entries + plan seeds

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing plan-seeds/deferred-select-promote.md
```

It is **not** itself a plan — `plan-tool create` consumes the prose below and
proposes a step decomposition; the author then runs `plan-tool detail` per step.

> **This is Plan B of a two-plan split.** Plan A
> (`plan-seeds/deferred-scan-digest.md`) ships the read-only `plan-tool deferred`
> scan: the `DeferredItem` model, the four harvest sources, dedup, classify, and
> a digest that assigns each surfaced item a **stable id** (`d1`, `d2`, …). This
> plan adds the **select** and **promote** layers on top and **must not** re-do
> the scan — it consumes Plan A's `DeferredItem` and command. **Depends on Plan A
> having shipped.** Assume the read-only `plan-tool deferred` command and its
> module exist and extend them.

---

## Overview

Extend the read-only `plan-tool deferred` scan (Plan A) with two phases:

1. **Select.** Present the surfaced concepts and let the operator choose which to
   move forward with — an interactive walk at a TTY, plus a non-interactive
   selection path (ids / `--all`) so a Claude session or an unattended run can
   drive it without silently skipping.
2. **Promote (mutation, gated).** For each selected concept, emit a correctly
   shaped, origin-backlinked **backlog entry** (routed to `BACKLOG.md` vs
   `BUG_BACKLOG.md`) and/or scaffold a **plan seed** under `plan-seeds/<slug>.md`,
   depending on the item's `direct`-vs-`plan-tool` tag and the operator's choice.

The digest (Plan A) was read-only by design; the gap this closes is that a
maintainer still had to hand-copy every surfaced item into a backlog entry or a
seed. This makes the promotion one selection away while keeping the scan itself
read-only and the mutation explicitly gated.

## Problem statement — the parked work is surfaced but never promoted

Plan A surfaces parked work from four sources (plan-body sections, report
`open_deferred` / skipped findings, and `concepts.json` `defer`/`wont_do`
records) and prints a digest. But moving any surfaced item into a backlog entry
or a seed is still a manual, easily-skipped step. The user's ask — "let the user
select the concepts to move forward with" — maps directly onto the concept
records especially: they are the tool's own decisions to park a concept, and a
*confirmed* `defer`/`wont_do` otherwise never rolls up into forward-looking work.

## Design

### Consume Plan A, add a promoter module + command phases

- **`plan_tool/deferred_digest.py`** (from Plan A) is reused as-is for the scan;
  do not re-implement harvest/dedup/classify.
- **`plan_tool/seed_render.py`** (new shared leaf): extract the common
  `create --from-existing` seed-skeleton renderer that `plan_tool/scope_out.py`
  (`render_carved_seed`) and `plan_tool/reground.py` (`render_rebaseline_seed`)
  each already hand-roll, so the promoter reuses one renderer instead of adding a
  third copy. Refactor those two call sites onto it (behavior-preserving;
  characterization tests pinned first).
- **`plan_tool/deferred_promote.py`** (new orchestrator leaf): given a set of
  selected `DeferredItem`s, render backlog entries and/or seed scaffolds (via
  `seed_render.py`). Pure rendering plus an injectable `invoker=` for the optional
  Claude call that crisps a bullet into a one-line concept and a seed brief
  (defaults to the real shell-out, stubbed in tests).
- **`plan_tool/cli/deferred_cmd.py`** (from Plan A): add the `--select` and
  `--apply` flags, the interactive walk, and the mutation gate; add the command
  to the **mutation lock set** and refresh the CLI reference.

Keep the new leaves below the CLI; lazy-import if a cycle would close.

### Phase — select

Plan A already assigns each surfaced item a stable id (`d1`, `d2`, …). Selection
has two modes, per the CLAUDE.md session-vs-operator split:

- **Interactive (TTY, human operator):** a `--select` walk that presents each
  item (summary, provenance, tag) and takes `promote` / `skip` / `both`
  (backlog + seed) / quit — the intended review-and-choose surface.
- **Non-interactive (Claude session / unattended):** `--select d1,d3,d7`
  (explicit ids) or `--select all`, plus a required `-y` for the mutation. The
  interactive walk **must not run on a non-interactive stdin** and silently skip
  (the `completeness-apply` bug the codebase already learned from) — with no
  `--select` and no TTY, print the digest and exit 0 without mutating.

### Phase — promote (gated mutation)

For each selected item, the default emission follows the tag, overridable per
item in the interactive walk:

- **`direct`** → append a backlog entry to the routed file. Routing rule: a
  report finding with `high`/`critical` severity → `BUG_BACKLOG.md`; everything
  else → `BACKLOG.md` (per "Which file does my entry go in?"). The entry carries
  a title, one-line summary, an `Origin:` backlink to the source plan/report/
  concept, and the `Approach:` tag — shaped so it needs no hand-editing.
- **`plan-tool`** → scaffold `plan-seeds/<slug>.md` (via `seed_render.py`) with
  Overview / Problem / Design-stub / Acceptance sections seeded from the item,
  **including the backlog-reconciliation requirement** (name the originating
  deferral; require the resulting plan to update the backlog when it ships) so
  every generated seed is itself CLAUDE.md-compliant.
- **`both`** → emit a backlog entry that references the scaffolded seed.

Mutation is **recommend-only unless `--apply` (+ a TTY confirm, or `-y`
non-interactively)** — the apply-or-recommend gate shape used by `scope_out_step`
/ `escalate_to_split`. Emission is **seed/entry-first and idempotent**: re-running
skips an item whose backlog entry or seed already exists (Plan A's dedup catches
it on the next scan anyway). Never mutate a source plan, its reports, or a concept
record — promotion only *writes* backlog entries and new seed files.

### Concept-deferral promotion is distinct from `scope-review`

`scope-review` confirms a pending deferral *within a plan* (include / defer /
wont_do); this feature takes an *already-decided* `defer`/`wont_do` concept and
promotes it into *forward-looking* work (a backlog entry / a new seed). They
compose — confirm in `scope-review`, later promote here — and this feature must
not re-open or mutate the concept record.

## Open questions — resolve during `create`/`detail`

- **Default emission for a `direct` item — entry only, or offer a seed too.**
  Lean entry-only by default (a `direct` item is by definition not plan-worthy),
  with `both` available in the interactive walk.
- **Confirmed vs pending concept deferrals — promote both or only confirmed.**
  Lean: surface both, but tag pending ones so the operator knows they haven't
  been `scope-review`-signed yet.

## Out of scope

- **Re-implementing the scan.** Harvest/dedup/classify/render live in Plan A.
- **Implementing the promoted work.** This writes backlog entries and seed files;
  it never authors a plan (`create`), writes code, or runs a plan.
- **Mutating source plans, reports, or concept records.** Read-only over all
  sources; the only writes are new backlog entries and new `plan-seeds/*.md`.
- **Re-opening or re-deciding concept deferrals.** That is `scope-review`'s job.

## Risks

- **Interactive walk skips on non-interactive stdin** (the `completeness-apply`
  trap). Mitigation: require explicit `--select` ids/`all` off a TTY; never run
  the interactive walk without a TTY; no `--select` + no TTY → print-and-exit.
- **Generated seed/entry shape drifts from the hand-authored convention.**
  Mitigation: render via the shared `seed_render.py`; a test asserts a generated
  seed carries the backlog-reconciliation requirement.
- **`seed_render` refactor changes scope-out/reground seed output.** Mitigation:
  pin characterization tests on `render_carved_seed` / `render_rebaseline_seed`
  before the extraction; they must pass unchanged after.
- **Double-promotion on re-run.** Mitigation: idempotent, entry/seed-first
  emission skips an item whose entry/seed already exists.
- **Import-cycle pressure.** Mitigation: keep the new leaves below the CLI;
  lazy-import if a cycle would close.

## Acceptance criteria

- `--select` drives an **interactive** promote/skip/both/quit walk at a TTY;
  `--select d1,d3` / `--select all` drive it non-interactively; with no `--select`
  and no TTY nothing mutates and the command exits 0.
- Promotion is gated behind `--apply` (+ TTY confirm, or `-y` non-interactively);
  without it, promotion is recommend-only.
- A promoted `direct` item appends a correctly shaped, `Origin:`-backlinked entry
  to the routed file (`high`/`critical` report finding → `BUG_BACKLOG.md`, else
  `BACKLOG.md`); a promoted `plan-tool` item scaffolds `plan-seeds/<slug>.md`
  **carrying the backlog-reconciliation requirement**.
- `plan_tool/seed_render.py` is the single seed-skeleton renderer; `scope_out.py`
  and `reground.py` use it and their pinned characterization tests pass unchanged.
- Emission is idempotent: re-running skips an item whose entry/seed already exists.
- No source plan, report, or concept record is mutated.
- The command is added to the mutation lock set; completion exits 0 regardless of
  how many items were surfaced or promoted (exit-code convention); the classify
  and seed-synthesis Claude calls route through the `invoker=` seam and are
  stubbed in tests (no real `claude` spawn); the new modules add no import cycle.
- The final docs step records the select/promote capability in `CAPABILITIES.md`
  / `USE_CASES.md` / `README.md` and updates `BACKLOG.md`.

## Deferred

- **Scope-guard `steps: []` out-of-scope stubs** as a fifth harvest source
  (belongs to Plan A's harvester if added; low-signal).
- **`--fail-on-findings`** — flip rc non-zero when the untriaged remainder is
  non-empty, for a CI "backlog has drifted from the plans" gate.
- **Auto-authoring a plan** from a promoted `plan-tool` seed (`create` chaining).
  Kept out: promotion stops at the seed so a human still reviews before `create`.
