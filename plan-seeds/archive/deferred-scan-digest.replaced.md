> **Replaced**: this file has been superseded by `docs/implementation-plans/2-deferred-scan-digest.md`.
> Preserved here for history; do not edit.

# Plan seed: read-only `plan-tool deferred` — scan all plans for parked work and print a triage digest

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing plan-seeds/deferred-scan-digest.md
```

It is **not** itself a plan — `plan-tool create` consumes the prose below and
proposes a step decomposition; the author then runs `plan-tool detail` per step.

> **This is Plan A of a two-plan split** (read-only scan/digest here; select +
> promote in `plan-seeds/deferred-select-promote.md`, which builds on the
> `DeferredItem` model and the `plan-tool deferred` command this plan ships).
> It **supersedes the read-only design in `plan-seeds/deferred-findings-digest.md`**
> — that seed's harvest → dedup → classify → print v1 is exactly this plan, plus
> one added harvest source (concept-deferral records). This plan's final docs
> step **retires `deferred-findings-digest.md`**. Keep this plan strictly
> read-only: no plan/backlog/seed mutation lands here — that is Plan B.

---

## Overview

Add a read-only command — **`plan-tool deferred`** — that sweeps every plan the
tool can see (live *and* archived), harvests the work authors and the tool
consciously parked, dedups it against what is already in the backlog files,
classifies each remaining item `direct` (apply now) vs `plan-tool` (author a plan
first), and prints a digest. Read-only: no edits to plans, no files written. Just
a list a maintainer can scan to answer "what parked follow-ups are sitting
unbuilt, and which need a plan?"

## Problem statement — the parked work is real but never rolls up

When a plan ships, the author (and the tool) routinely name work that was *not*
done, in four high-signal places:

1. **Plan-body `## Out of scope` / `## Deferred` sections** — `- **Title** —
   rationale` bullets in every plan `.md` (live and archived).
2. **Completeness / reconcile report JSON** — under
   `docs/implementation-plans/plan-details/<slug>/reports/*.json`, the
   **`open_deferred`** bucket (triage declined) and any `recommendations[]` entry
   whose `annotations[id].status == "skip"` (an operator passed on it in a walk).
3. **Concept-deferral records** — `plan-details/<slug>/concepts.json` flat
   `decision-record` nodes tagged `defer` / `wont_do` (the lazy-deferral MVP):
   the tool's *own* deferral ledger. Pending ones already surface non-blocking in
   `status` / the completeness report (`concept-unsigned-deferral`) and are
   confirmed via `scope-review`, but a *confirmed* `defer`/`wont_do` never rolls
   up into forward-looking work.

The backlog files (`BACKLOG.md`, `BUG_BACKLOG.md`) are the canonical sink, and
good entries already cite their origin (`Origin: Deferred from <plan>.md`). But
moving a deferral into the backlog is a manual, easily-skipped step. The
completeness walk *does* route findings at emit time — so the live gap is the
**retrospective** remainder in already-shipped plans where routing was skipped,
plus **archived** plans the manifest no longer lists, plus confirmed concept
deferrals. Nothing surveys that remainder today; the only way to find it is to
read every plan.

## Design

### One module + a thin CLI seam

- **`plan_tool/deferred_digest.py`** (orchestrator leaf): harvest → dedup →
  classify → render. Pure logic plus an injectable `invoker=` for the single
  optional Claude classification call (per the invoker-seam rule — defaults to
  the real shell-out, stubbed in tests). Keep it a **leaf below the CLI**;
  lazy-import report/concept parsing if it would close an import cycle.
- **`plan_tool/cli/deferred_cmd.py`** (thin handler, registered in `parser.py`,
  added to the CLI reference). Ships the read-only command only — no mutation
  flags in this plan.

### Harvest — three collectors → a normalized item

Each source yields a `DeferredItem` dataclass: `title`, `summary`, `source_kind`
(`plan-deferred | plan-out-of-scope | report-deferred | concept-deferral`),
`source_path`, `archived: bool`, `origin_slug`, and any `severity` / `impact` /
`complexity` carried from a report finding, plus (for concept records) `node_id`,
`bucket`, and reviewed/pending state.

- **Plan-body sections.** Parse `## Out of scope` and `## Deferred` H2 blocks
  from every plan `.md`, splitting `- **Title** — body` bullets.
- **Report JSON.** Read each `reports/*.json`; emit the `open_deferred` bucket
  and any `status == "skip"` recommendation, carrying severity/triage so the
  classifier has signal.
- **Concept-deferral records.** Read each `concepts.json`; emit confirmed and
  pending `defer` / `wont_do` decision-record nodes, tagging pending ones so the
  digest shows they are not yet `scope-review`-signed. This plan only *reads* the
  records — it never re-opens or mutates them (that is `scope-review`'s job).

### Enumerate live AND archived plans

- Live: `locator.load_manifest_plan_paths(repo_root)`.
- Archived: glob `docs/implementation-plans/**/archive/**/*.md` (archived plans
  are deliberately absent from `.plan-tool/plans.json`, so a manifest-only sweep
  silently misses them). Mark `archived=True`; an archived source does **not**
  mean the deferral is moot — surface it, sorted below live sources.

### Dedup against the backlog (convergent re-runs)

Build the "already-triaged" set from `BACKLOG.md` + `BUG_BACKLOG.md` — every
entry title plus every `Origin:` backlink — and drop any item matching by
origin-slug (exact) or normalized-title (fuzzy). Once a concept is triaged into a
backlog file it stops appearing, so the digest trends toward the untriaged
remainder rather than re-listing known work.

### Classify direct vs. plan — reuse the existing heuristic

Tag each surviving item with BACKLOG.md's existing closed vocabulary — `direct`,
`plan-tool`, or `direct unless <condition>` — applying its
[Direct implementation vs. plan-tool plan] heuristic verbatim, so a digest line
can be pasted straight into a backlog entry (and consumed by Plan B's promoter):

- **Deterministic pre-score (no Claude):** count files/symbols named in the
  bullet; detect multi-module / multi-phase language ("first … then …", "open
  question", "design choice"); read any `complexity`/`impact` from a report
  finding. Single-file + obvious criteria + no open decision → lean `direct`;
  multi-module / open decision / 2+ phases → lean `plan-tool`.
- **Optional Claude refinement (`--classify`, default ON; `--no-classify`
  skips):** one batched call crisps each bullet into a one-line concept and
  confirms or overrides the pre-scored tag. On disagreement take the more
  cautious `plan-tool`. `--no-classify` runs the whole sweep with zero Claude.

### Output — the digest

Print to stdout, grouped by Approach (`direct` first), then live before
archived. Assign each surfaced item a **short stable id** (`d1`, `d2`, … — Plan B
consumes these as selection tokens). Each line carries the one-line summary,
provenance (source path + kind + archived flag), and the tag:

```
[direct]     d3  Synthesis output caching across reruns
                 ↳ from 2-from-existing-body-synthesis.md (archived) · plan-deferred
[plan-tool]  d7  Verify plan against developer-doc links during iteration
                 ↳ from <plan> · plan-deferred
```

Preserve the **exit-code convention**: a completed digest exits 0 regardless of
how many items it surfaces (no `--fail-on-findings` — deferred to Plan B/later).

## Open question — subcommand vs. flag

This assumes a standalone `plan-tool deferred`. The report-JSON collector and the
dedup logic lean on plumbing `completeness` already owns, so it could ship as
`completeness --deferred-digest`. Lean standalone (Plan B's select/promote phases
make it clearly its own verb); resolve during `create`/`detail`.

## Out of scope (this plan)

- **Selection and promotion.** No `--select`, no `--apply`, no writing backlog
  entries or seed files — that is Plan B (`deferred-select-promote.md`).
- **Mutating any source.** Read-only over plans, reports, and concept records.
- **A new code audit.** This aggregates deferrals already recorded; it adds no
  new audit of the code.
- **Scope-guard `steps: []` stubs** as a harvest source (low-signal) and
  `--fail-on-findings` — both deferred.

## Risks

- **Dedup misses → re-listing triaged work.** Mitigation: dedup on the `Origin:`
  backlink first (exact), fall back to normalized-title.
- **Classifier over-tags `direct`.** Mitigation: on pre-score/Claude disagreement
  take the cautious `plan-tool`.
- **Import-cycle pressure.** Mitigation: keep `deferred_digest.py` a leaf below
  the CLI; lazy-import report/concept parsing if it would close a cycle.

## Acceptance criteria

- `plan-tool deferred` harvests `## Out of scope` / `## Deferred` plan-body
  sections, report-JSON deferrals (`open_deferred` + `status: skip`), and
  `concepts.json` `defer`/`wont_do` decision records across both live (manifest)
  and archived (`**/archive/**`) plans.
- Items already in a backlog file (by `Origin:` backlink or normalized-title) are
  dropped, so a second run with no new deferrals prints an empty remainder.
- Each item carries a **stable id**, a one-line summary, provenance (path + kind +
  archived flag), and an `Approach` tag from `{direct, plan-tool, direct unless …}`.
- `--no-classify` runs the full sweep with zero Claude calls (pre-score tags
  only); `--classify` (default) refines via one batched call.
- Completion exits 0 regardless of count (exit-code convention).
- `deferred_digest.py` adds no import cycle and uses the `invoker=` seam so the
  classification call is stubbable in tests (no real `claude` spawn).
- No plan, report, or concept record is mutated (read-only).
- The final docs step **removes `plan-seeds/deferred-findings-digest.md`** (its
  read-only scope is absorbed here) and records the read-only digest capability
  in `CAPABILITIES.md` / `USE_CASES.md` / `README.md`. Because this seed is split
  from the shipped `2-scan-select-promote-deferred-work.md` plan, that plan is
  retired in favor of this Plan A + Plan B pair; note the split in `BACKLOG.md` if
  a tracking line helps.

## Deferred (to Plan B or later)

- **Selection + promotion** (`--select`, `--apply`, backlog-entry / seed
  emitters, routing, idempotency) — the whole of `deferred-select-promote.md`.
- **Scope-guard `steps: []` out-of-scope stubs** as a fifth harvest source.
- **`--fail-on-findings`** — flip rc non-zero when the untriaged remainder is
  non-empty, for a CI "backlog has drifted from the plans" gate.
