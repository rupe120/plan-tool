> **Replaced**: this file has been superseded by `docs/implementation-plans/2-scan-select-promote-deferred-work.md`.
> Preserved here for history; do not edit.

# Plan seed: scan all plans for deferred work, let the operator select, and promote to backlog entries + plan seeds

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing plan-seeds/deferred-work-scan-select-promote.md
```

It is **not** itself a plan — `plan-tool create` consumes the prose below and
proposes a step decomposition; the author then runs `plan-tool detail` per step.

> **Supersedes `plan-seeds/deferred-findings-digest.md`.** That seed's read-only
> v1 (harvest → dedup → classify → print) is the *scan* foundation this feature
> is built on; this seed pulls in its two parked emitters (`--emit-backlog`,
> `--emit-seed`) and adds the missing piece both lacked: an **operator selection**
> surface. The `create`/`detail` author should treat the digest seed as the
> already-designed read-only core and this seed as the promotion layer above it,
> then **retire `deferred-findings-digest.md`** (its scope is fully absorbed here).
> Backlog reconciliation: the shipping plan's final docs step must remove the old
> seed and record this capability in `BACKLOG.md`/`CAPABILITIES.md`.

---

## Overview

Extend the planned read-only `plan-tool deferred` sweep into a three-phase
**scan → select → promote** flow:

1. **Scan (read-only).** Sweep every plan the tool can see — live *and* archived
   — plus the report sidecars and concept-deferral records, harvest the work the
   authors consciously parked, dedup it against the backlog files, and classify
   each remaining item `direct` vs `plan-tool`. This is exactly the
   `deferred-findings-digest.md` design; reuse it verbatim.
2. **Select.** Present the surfaced concepts and let the operator choose which to
   move forward with — an interactive walk at a TTY, plus a non-interactive
   selection path (ids / `--all`) so a Claude session or an unattended run can
   drive it without silently skipping.
3. **Promote (mutation, gated).** For each selected concept, emit a correctly
   shaped, origin-backlinked **backlog entry** (routed to `BACKLOG.md` vs
   `BUG_BACKLOG.md`) and/or scaffold a **plan seed** under `plan-seeds/<slug>.md`,
   depending on the item's `direct`-vs-`plan-tool` tag and the operator's choice.

The digest was read-only by design ("just a list a maintainer can scan"); the
gap this closes is that a maintainer still had to hand-copy every surfaced item
into a backlog entry or a seed. This makes the promotion one selection away while
keeping the scan itself read-only and the mutation explicitly gated.

## Problem statement — the parked work is real, surfaced, but never promoted

Authors routinely name work they did *not* do, in four high-signal places:

1. **Plan-body `## Out of scope` / `## Deferred` sections** — `- **Title** —
   rationale` bullets in every plan `.md` (live and archived).
2. **Completeness / reconcile report JSON** — the `open_deferred` bucket and any
   `recommendations[]` entry whose `annotations[id].status == "skip"`, under
   `docs/implementation-plans/plan-details/<slug>/reports/*.json`.
3. **Concept-deferral records** — `plan-details/<slug>/concepts.json` flat
   `decision-record` nodes tagged `defer` / `wont_do` (the lazy-deferral MVP).
   These are operator/tool decisions to park a concept; pending ones already
   surface non-blocking in `status` / the completeness report
   (`concept-unsigned-deferral`) and are confirmed via `scope-review`, but a
   *confirmed* `defer`/`wont_do` never rolls up into forward-looking work.
4. **Scope-guard `steps: []` out-of-scope stubs** — the CLAUDE.md "migrate to
   backlog" anti-pattern (low-signal; keep behind a flag — see Deferred).

Sources 1–2 are already designed in `deferred-findings-digest.md`. Source 3 is
new here and important: it's the tool's *own* deferral ledger, and the user's ask
("let the user select the concepts to move forward with") maps directly onto
these concept records. The backlog files are the canonical sink, but moving any
of these into a backlog entry or a seed is a manual, easily-skipped step, and
nothing promotes them today.

## Design

### Reuse the digest core, add one harvest source

- **`plan_tool/deferred_digest.py`** (from the superseded seed) stays the
  read-only harvest → dedup → classify → render leaf. Add a **third/fourth
  collector** for concept-deferral records (read `concepts.json`, emit confirmed
  and pending `defer`/`wont_do` nodes as `DeferredItem`s with
  `source_kind = concept-deferral`, carrying `node.id`, `bucket`, and the
  reviewed/pending state). Keep the `invoker=` seam for the optional classify call.
- **`plan_tool/deferred_promote.py`** (new orchestrator leaf): given a set of
  selected `DeferredItem`s, render backlog entries and/or seed scaffolds. Pure
  rendering plus an injectable `invoker=` for the optional Claude call that
  crisps a bullet into a one-line concept and a seed brief (defaults to the real
  shell-out, stubbed in tests).
- **`plan_tool/cli/deferred_cmd.py`** (thin handler, registered in `parser.py`):
  wires the three phases and owns the interactive walk + the mutation gate.

### Phase 1 — scan (read-only, unchanged from the digest seed)

Harvest across live (`locator.load_manifest_plan_paths`) and archived
(`docs/implementation-plans/**/archive/**/*.md`) plans plus the report sidecars
and `concepts.json`; dedup against `BACKLOG.md` + `BUG_BACKLOG.md` by `Origin:`
backlink (exact) then normalized title (fuzzy); classify each survivor `direct` /
`plan-tool` / `direct unless <cond>` using BACKLOG.md's heuristic. `--no-classify`
keeps the whole scan Claude-free. Default `plan-tool deferred` with no promote
flag prints the digest and exits — the read-only behavior the digest seed
specified is preserved as the no-flag default.

### Phase 2 — select

Assign each surfaced item a short stable id (e.g. `d1`, `d2`, …) in the printed
digest. Selection has two modes, per the CLAUDE.md session-vs-operator split:

- **Interactive (TTY, human operator):** an `--select` walk that presents each
  item (summary, provenance, tag) and takes `promote` / `skip` / `both`
  (backlog + seed) / quit — the intended review-and-choose surface.
- **Non-interactive (Claude session / unattended):** `--select d1,d3,d7` (explicit
  ids) or `--select all`, plus a required `-y` for the mutation. The interactive
  walk **must not run on a non-interactive stdin** and silently skip (the
  `completeness-apply` bug the codebase already learned from) — with no `--select`
  and no TTY, print the digest and exit 0 without mutating.

### Phase 3 — promote (gated mutation)

For each selected item, the default emission follows the tag, overridable per
item in the interactive walk:

- **`direct`** → append a backlog entry to the routed file. Routing rule: a
  report finding with `high`/`critical` severity → `BUG_BACKLOG.md`; everything
  else → `BACKLOG.md` (per "Which file does my entry go in?"). The entry carries
  a title, one-line summary, an `Origin:` backlink to the source plan/report/
  concept, and the `Approach:` tag — shaped so it needs no hand-editing.
- **`plan-tool`** → scaffold `plan-seeds/<slug>.md` with Overview / Problem /
  Design-stub / Acceptance sections seeded from the item, **including the
  backlog-reconciliation requirement** (name the originating deferral; require
  the resulting plan to update the backlog when it ships) so every generated seed
  is itself CLAUDE.md-compliant.
- **`both`** → emit a backlog entry that references the scaffolded seed.

Mutation is **recommend-only unless `--apply` (+ a TTY confirm, or `-y`
non-interactively)** — the apply-or-recommend gate shape used by
`scope_out_step` / `escalate_to_split`. Emission is **seed/entry-first and
idempotent**: re-running skips an item whose backlog entry or seed already exists
(dedup catches it on the next scan anyway). Never mutate a source plan or its
reports — promotion only *writes* backlog entries and new seed files.

### Concept-deferral promotion is distinct from `scope-review`

`scope-review` confirms a pending deferral *within a plan* (include / defer /
wont_do); this feature takes an *already-decided* `defer`/`wont_do` concept and
promotes it into *forward-looking* work (a backlog entry / a new seed). They
compose — confirm in `scope-review`, later promote here — and this feature must
not re-open or mutate the concept record.

## Open questions — resolve during `create`/`detail`

- **Subcommand vs. flag.** Inherit the digest seed's open question: standalone
  `plan-tool deferred` vs `completeness --deferred-digest`. Lean standalone (the
  select/promote phases make it clearly its own verb).
- **Default emission for a `direct` item — entry only, or offer a seed too.**
  Lean entry-only by default (a `direct` item is by definition not plan-worthy),
  with `both` available in the interactive walk.
- **Confirmed vs pending concept deferrals — promote both or only confirmed.**
  Lean: surface both, but tag pending ones so the operator knows they haven't
  been `scope-review`-signed yet.

## Out of scope

- **Implementing the promoted work.** This writes backlog entries and seed files;
  it never authors a plan (`create`), writes code, or runs a plan.
- **Mutating source plans, reports, or concept records.** Read-only over all
  sources; the only writes are new backlog entries and new `plan-seeds/*.md`.
- **A new code audit.** This aggregates deferrals authors/tools already recorded.
- **Re-opening or re-deciding concept deferrals.** That is `scope-review`'s job.

## Risks

- **Dedup misses → promoting already-triaged work.** Mitigation: dedup on
  `Origin:` backlink first (exact), fall back to normalized title; idempotent
  emission skips an item whose entry/seed already exists.
- **Interactive walk skips on non-interactive stdin** (the `completeness-apply`
  trap). Mitigation: require explicit `--select` ids/`all` off a TTY; never run
  the interactive walk without a TTY; no `--select` + no TTY → print-and-exit.
- **Generated seed/entry shape drifts from the hand-authored convention.**
  Mitigation: template from an existing seed and the backlog entry shape; a test
  asserts a generated seed carries the backlog-reconciliation requirement.
- **Import-cycle pressure.** Mitigation: keep `deferred_digest.py` /
  `deferred_promote.py` leaves below the CLI; lazy-import report/concept parsing
  if it would close a cycle.

## Acceptance criteria

- `plan-tool deferred` with no promote flag prints the read-only digest
  (harvest + dedup + classify across live/archived plans, reports, and
  `concepts.json` `defer`/`wont_do` records) and exits 0 — the digest seed's
  read-only behavior, preserved.
- Each surfaced item carries a stable id, a one-line summary, provenance
  (path + kind + archived flag), and an `Approach` tag.
- `--select` drives an **interactive** promote/skip/both/quit walk at a TTY;
  `--select d1,d3` / `--select all` drive it non-interactively; with no `--select`
  and no TTY nothing mutates and the command exits 0.
- Promotion is gated behind `--apply` (+ TTY confirm, or `-y` non-interactively);
  without it, promotion is recommend-only.
- A promoted `direct` item appends a correctly shaped, `Origin:`-backlinked entry
  to the routed file (`high`/`critical` report finding → `BUG_BACKLOG.md`, else
  `BACKLOG.md`); a promoted `plan-tool` item scaffolds `plan-seeds/<slug>.md`
  **carrying the backlog-reconciliation requirement**.
- Emission is idempotent: re-running skips an item whose entry/seed already exists.
- No source plan, report, or concept record is mutated.
- Completion exits 0 regardless of how many items were surfaced or promoted
  (exit-code convention); the classify and seed-synthesis Claude calls route
  through the `invoker=` seam and are stubbed in tests (no real `claude` spawn);
  the new modules add no import cycle.
- The shipping plan's final docs step **removes `plan-seeds/deferred-findings-digest.md`**
  (its scope is absorbed here) and records the capability in `BACKLOG.md` /
  `CAPABILITIES.md`.

## Deferred

- **Scope-guard `steps: []` out-of-scope stubs** as a fifth harvest source
  (low-signal; the CLAUDE.md anti-pattern). Add behind a flag once the four
  primary sources prove out.
- **`--fail-on-findings`** — flip rc non-zero when the untriaged remainder is
  non-empty, for a CI "backlog has drifted from the plans" gate.
- **Auto-authoring a plan** from a promoted `plan-tool` seed (`create` chaining).
  Kept out: promotion stops at the seed so a human still reviews before `create`.
