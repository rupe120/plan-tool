# Plan seed: collect deferred / out-of-scope findings into a triage digest

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing plan-seeds/deferred-findings-digest.md
```

It is **not** itself a plan — `plan-tool create` consumes the prose below
and proposes a step decomposition; the author then runs `plan-tool detail`
per step.

> **Scope: this is the lean v1.** Two sources, dedup, classify, print —
> nothing else. Three further sources and two file-emitters are deliberately
> parked in `## Deferred`; do not pull them in. The point of v1 is a read-only
> digest that surfaces the *retrospective* gap (deferrals in already-shipped
> plans that were never triaged into the backlog) at the lowest credible cost.

---

## Overview

Add a read-only command — **`plan-tool deferred`** — that sweeps every plan the
tool can see (live *and* archived), harvests the work the authors consciously
parked, dedups it against what is already in the backlog files, classifies each
remaining item as `direct` (apply now) vs `plan-tool` (author a plan first), and
prints a digest. Read-only: no edits to plans, no files written. Just a list a
maintainer can scan to answer "what cheap follow-ups are sitting unbuilt, and
which need a plan?"

## Problem statement — the parked work is real but never rolls up

When a plan ships, the author routinely names work they did *not* do, in two
high-signal places:

1. **Plan-body `## Out of scope` / `## Deferred` sections** — `- **Title** —
   rationale` bullets in every plan `.md`. Example,
   `2-feature-health-declaration-and-smell-checks.md`: *"Unfalsifiable-feature
   smell check — postponed: it needs an acceptance-criteria → feature tagging
   convention that does not exist today."*
2. **Completeness / reconcile report JSON** — under
   `docs/implementation-plans/plan-details/<slug>/reports/*.json`, the
   **`open_deferred`** bucket (triage declined: complexity > impact, NIT/INFO,
   or diagnostic source) and any `recommendations[]` entry whose
   `annotations[id].status == "skip"` (an operator passed on it during a walk).
   These are findings the convergence loop *surfaced and declined* — they never
   resurface.

The backlog files (`BACKLOG.md`, `BUG_BACKLOG.md`) are the canonical sink, and
good entries already cite their origin (`#43 — … Origin: Deferred from
2-from-existing-body-synthesis.md`). But moving a deferral into the backlog is a
manual, easily-skipped step. The completeness walk *does* route findings at
**emit time** — so the live gap is narrower than "collect all deferrals": it's
the **retrospective** remainder in already-shipped plans where that routing was
skipped, plus **archived** plans the manifest no longer lists. Nothing surveys
that remainder today; the only way to find it is to read every plan.

## Design

### One module + a thin CLI seam

- **`plan_tool/deferred_digest.py`** (orchestrator leaf): harvest → dedup →
  classify → render. Pure logic plus an injectable `invoker=` for the single
  optional Claude classification call (per the invoker-seam rule — defaults to
  the real shell-out, stubbed in tests).
- **`plan_tool/cli/deferred_cmd.py`** (thin handler, registered in `parser.py`).

### Harvest — two collectors → a normalized item

Each source yields a `DeferredItem` dataclass: `title`, `summary`,
`source_kind` (`plan-deferred | plan-out-of-scope | report-deferred`),
`source_path`, `archived: bool`, `origin_slug`, and any `severity` / `impact` /
`complexity` carried from a report finding.

- **Plan-body sections.** Parse `## Out of scope` and `## Deferred` H2 blocks
  from every plan `.md`, splitting `- **Title** — body` bullets.
- **Report JSON.** Read each `reports/*.json`; emit the `open_deferred` bucket
  and any `status == "skip"` recommendation, carrying its severity/triage so the
  classifier has signal.

### Enumerate live AND archived plans

- Live: `locator.load_manifest_plan_paths(repo_root)`.
- Archived: glob `docs/implementation-plans/**/archive/**/*.md` (archived plans
  are deliberately absent from `.plan-tool/plans.json`, so a manifest-only sweep
  silently misses them). Mark `archived=True`; an archived source does **not**
  mean the deferral is moot — surface it, sorted below live sources.

### Dedup against the backlog (convergent re-runs)

Build the "already-triaged" set from `BACKLOG.md` + `BUG_BACKLOG.md` — every
entry title plus every `Origin:` backlink — and drop any item matching by
origin-slug (exact) or normalized-title (fuzzy). Once a concept is triaged into
a backlog file it stops appearing, so the digest trends toward the untriaged
remainder rather than re-listing known work.

### Classify direct vs. plan — reuse the existing heuristic

Tag each surviving item with BACKLOG.md's existing closed vocabulary —
`direct`, `plan-tool`, or `direct unless <condition>` — applying its
[Direct implementation vs. plan-tool plan] heuristic verbatim, so a digest line
can be pasted straight into a backlog entry:

- **Deterministic pre-score (no Claude):** count files/symbols named in the
  bullet; detect multi-module / multi-phase language ("first … then …", "open
  question", "design choice"); read any `complexity`/`impact` from a report
  finding. Single-file + obvious criteria + no open decision → lean `direct`;
  multi-module / open decision / 2+ phases → lean `plan-tool`.
- **Optional Claude refinement (`--classify`, default ON; `--no-classify`
  skips):** one batched call crisps each bullet into a one-line concept and
  confirms or overrides the pre-scored tag with a one-clause justification. When
  pre-score and Claude disagree, take the more cautious `plan-tool` — mirroring
  the heuristic's own "when unsure, default to authoring a plan." `--no-classify`
  runs the whole sweep deterministically with zero Claude calls.

### Output — the digest

Print to stdout, grouped by Approach (`direct` first — the cheap actionable
pile), then live before archived. Each line carries the one-line summary,
provenance (source path + kind + archived flag), and the tag:

```
[direct]     Synthesis output caching across reruns
             ↳ from 2-from-existing-body-synthesis.md (archived) · plan-deferred
[plan-tool]  Verify plan against developer-doc links during iteration
             ↳ from <plan> · plan-deferred
```

Preserve the **exit-code convention**: a completed digest exits 0 regardless of
how many items it surfaces (no `--fail-on-findings` in v1 — see Deferred).

## Open question — subcommand vs. flag

v1 assumes a standalone `plan-tool deferred`. But the report-JSON collector and
the dedup logic lean on the same plumbing `completeness` already owns, so this
could instead ship as `completeness --deferred-digest` (report-only, no plan
named). Resolve during `create`/`detail`: standalone reads better as "survey all
plans," a flag reuses more. Lean standalone unless the report-parsing reuse is
large enough to make a flag clearly cheaper.

## Out of scope

- **Implementing or authoring anything.** The digest classifies and prints; it
  never edits code, writes a backlog entry, or authors a plan.
- **A new code checker.** This aggregates deferrals authors already recorded; it
  adds no new audit of the code.
- **Mutating source plans.** Read-only over plans + reports.

## Risks

- **Dedup misses → re-listing triaged work.** Severity: UX / convergence. Fuzzy
  title match is imperfect. Mitigation: dedup on the `Origin:` backlink first
  (exact), fall back to normalized-title.
- **Classifier over-tags `direct`.** Severity: recommendation quality. A
  mis-tagged "direct" invites an under-scoped inline change. Mitigation: on
  pre-score/Claude disagreement take the cautious `plan-tool`.
- **Import-cycle pressure.** Severity: architecture. Mitigation: keep
  `deferred_digest.py` a leaf below the CLI; lazy-import report parsing if it
  would close a cycle, per codebase precedent.

## Acceptance criteria

- `plan-tool deferred` harvests `## Out of scope` / `## Deferred` plan-body
  sections and report-JSON deferrals (`open_deferred` + `status: skip`) across
  both live (manifest) and archived (`**/archive/**`) plans.
- Items already in a backlog file (by `Origin:` backlink or normalized-title)
  are dropped, so a second run with no new deferrals prints an empty remainder.
- Each item carries a one-line summary, provenance (path + kind + archived
  flag), and an `Approach` tag from `{direct, plan-tool, direct unless …}`.
- `--no-classify` runs the full sweep with zero Claude calls (pre-score tags
  only); `--classify` (default) refines via one batched call.
- Completion exits 0 regardless of count (exit-code convention).
- `deferred_digest.py` adds no import cycle and uses the `invoker=` seam so the
  classification call is stubbable in tests (no real `claude` spawn).

## Deferred

- **Three more harvest sources** — per-step detail `## Deferred` sections (need
  an intra-plan "deferred to step N" filter; mostly low-signal), step
  frontmatter `scope: deferred | wont_do` + `status_note`, and scope-guard
  `steps: []` out-of-scope stubs (the CLAUDE.md "migrate to backlog"
  anti-pattern). Add once v1 proves the two high-signal sources are worth it.
- **`--emit-backlog`** — append correctly-shaped, origin-backlinked entries to
  the routed file, including the `BACKLOG.md` vs `BUG_BACKLOG.md` decision-rule
  routing (report findings with `high`/`critical` severity → BUG_BACKLOG). v1
  only prints; a human pastes.
- **`--emit-seed`** — scaffold `plan-seeds/<slug>.md` per `plan-tool` concept.
- **`--fail-on-findings`** — flip rc non-zero when the untriaged remainder is
  non-empty, for a CI "backlog has drifted from the plans" gate.

## References

- `BACKLOG.md` and `BUG_BACKLOG.md` — existing destination ledgers used to
  detect already-triaged deferred work.
- `plan_tool/completeness_report.py` — saved report format that supplies the
  report-JSON deferral source.
- `TESTING.md` — invoker-seam convention for the optional batched classifier.
