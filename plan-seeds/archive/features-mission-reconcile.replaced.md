> **Replaced**: this file has been superseded by `docs/implementation-plans/2-features-mission-reconcile.md`.
> Preserved here for history; do not edit.

# Plan seed: features↔mission map + drift-gated reconciliation

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing plan-seeds/features-mission-reconcile.md
```

It is **not** itself a plan — `plan-tool create` consumes the prose below and
proposes a step decomposition; the author then runs `plan-tool detail` per step.

---

## Overview

`plan-tool` has a `MISSION.md` (the mission + nine numbered grounding
principles) and a fully-featured CLI, but **nothing maps the app's own
capabilities to the mission they serve**, and nothing keeps such a map honest as
the CLI and mission move. This plan creates that map and the machinery to
reconcile it.

> **Disambiguation (load-bearing).** This is about **plan-tool's own feature
> catalog** — the capabilities the *app* ships — not the per-plan `features:`
> registry in plan frontmatter (`Plan.features` / `Step.features` in
> `schema.py`, documented in `PLAN_FORMAT.md`). That registry is per-plan
> metadata a plan declares about itself; this artifact is app-level and
> describes plan-tool. Name and document the new artifact so the two never read
> as the same thing.

Three deliverables, all reinforcing the mission's own principles applied to the
tool itself:

1. **`FEATURES.md`** (repo root) — the canonical, machine-parseable map of
   plan-tool's capabilities → the MISSION.md principle(s) each serves.
2. **A fingerprint-gated reconcile command** (suggest `plan-tool
   reconcile-mission`, mirroring `reconcile-plan --refresh`) that re-fits the
   map when the CLI surface or the mission drifts — spending **no Claude** on a
   no-drift run.
3. **A cheap, no-Claude honesty check** in the existing advisory layer (surfaced
   from `validate` and the completeness deterministic layer) that flags a
   `FEATURES.md` that has fallen out of sync with the code or the mission.

## The features list is derived from the code, not invented

The authoritative source of "what features does the app have" is the **CLI
surface** — the argparse subcommands and their flags — together with the
orchestrators behind them (`create.py`, `detail.py`, `launcher.py`/run,
`review.py`, `completeness_report.py`, `jira.py`, reconcile, annotate, …).
`plan_tool/cli_reference.py` already introspects the parser to generate
`docs/cli/`; lean on that same surface so the feature inventory is grounded in
what actually exists, never hand-invented. Build the initial `FEATURES.md` by
walking the subcommand set and grouping subcommands into capabilities, then
mapping each capability to the principle(s) it serves.

This grounding is what makes drift detection possible: the reconcile command and
the honesty check fingerprint **the same CLI surface** `cli_reference` reads, so
a new/renamed/removed subcommand or flag mechanically flags `FEATURES.md` as
possibly stale.

## Architecture

### Part A — `FEATURES.md`, machine-parseable, principle-linked

A canonical doc at the repo root. Each feature entry carries:

- a stable **kebab-case `id`** and a human **`title`**;
- the **surfaces** it is implemented by — one or more CLI subcommands
  (e.g. `create`, `detail`, `run`) and/or orchestrator module(s)
  (e.g. `plan_tool/launcher.py`). A feature may be internal (an orchestrator/
  module surface with no subcommand of its own);
- the **principles** it serves — references to MISSION.md principle ids
  (see Part D).

Keep the format lightweight but **parseable** so Part C can validate it without
Claude (a small structured block per feature — a table or a per-feature heading
with `surfaces:` / `principles:` lines — author's choice, but the parser and the
doc must agree). This is a "documentation is for people" artifact (principle 5/6):
terse, every entry earning its place, the *why* (which principle, which surface)
explicit.

### Part B — `reconcile-mission`: fingerprint-gated re-fit (mirror `reconcile-plan --refresh`)

A new subcommand that keeps the map honest over time, modeled on the existing
cheap fingerprint-gated reconcile (`reconcile-plan --refresh`):

- Track a **baseline fingerprint** under `.plan-tool/` covering (a) `MISSION.md`,
  (b) the CLI surface (the subcommand/flag inventory `cli_reference` reads), and
  (c) `FEATURES.md` itself — content-hash, the way completeness reports already
  carry a `code_fingerprint`.
- **No drift → spend no Claude, exit clean** (principle 3 — let code decide
  whether to spend the model at all).
- **Drift → re-reconcile only the changed surfaces.** A Claude pass — through the
  standard `invoker=` seam, never a bare shell-out — proposes `FEATURES.md`
  edits: a new feature for a new subcommand, an edited/removed entry for a
  renamed/removed surface, a re-mapping when a principle's prose changes. Output
  lands as advisory findings; under `--iterate` it converges (gates →
  `apply_finding` → re-audit), same as `create`/`detail`/reconcile.
- Re-running after a clean reconcile re-stamps the baseline so the next no-drift
  run stays cheap.

Wire it through the existing CLI layering: a new orchestrator (suggest
`plan_tool/mission_reconcile.py`), a **thin** `cli/` handler, and a parser entry.
The orchestrator owns the fingerprint/diff/Claude-pass logic; the handler only
wires args.

### Part C — deterministic honesty check (no Claude)

A cheap heuristic in the advisory smell/validation layer (`review.py`,
`collect_smell_findings`), surfaced from `plan-tool validate` and the
completeness deterministic layer so it fires before any Claude spend:

- every `FEATURES.md` feature cites **≥1 surface that exists at HEAD** — a cited
  subcommand is a real subcommand, a cited module path exists (stale-surface
  drift);
- every feature references **≥1 valid MISSION principle id**;
- **coverage gaps** — a CLI subcommand with no owning feature, and a principle
  with no feature that serves it.

All findings are **advisory, lowest severity, dismissible**; none flips the exit
code (exit-code convention — completion, not findings, drives rc;
`--fail-on-findings` stays the only opt-in). Inert when `FEATURES.md` is absent.

### Part D — stable principle ids in MISSION.md (minimal)

`FEATURES.md` references and the Part C check both need **stable principle
anchors**. MISSION.md already numbers its principles `1`–`9` with titles;
formalize that numbering (or a kebab slug per title) as the canonical id scheme —
mirroring how the per-plan feature registry uses stable `id`s. This is a tiny,
non-disruptive edit: do **not** rewrite principle prose (human-owned), only
ensure each principle has a referenceable, stable id and document the scheme.

## Seam citations (verify at HEAD before building)

- `MISSION.md` — the mission + 9 numbered grounding principles; the principle-id
  source (Part D).
- `plan_tool/cli/parser.py` (argparse assembly) and `plan_tool/cli_reference.py`
  (parser introspection → `docs/cli/`) — the feature-inventory source **and** the
  drift-fingerprint source; `tests/cli/test_cli_reference.py` is the drift guard
  to extend for the new subcommand.
- `reconcile-plan --refresh` (its handler/orchestrator) + `plan_tool/
  drift_detection.py` + the `code_fingerprint` shape in completeness reports —
  the cheap fingerprint-gated reconcile pattern to mirror (Part B).
- `plan_tool/project_config.py` and `.plan-tool/` — where the baseline
  fingerprint is stored (alongside the grounding baseline `reconcile-plan
  --refresh` already keeps).
- `plan_tool/review.py` (`collect_smell_findings` / advisory layer) and
  `plan-tool validate` — where the Part C honesty check attaches.
- CLI layering (`plan_tool/cli/app.py`, `parser.py`, one intent handler module)
  + the `invoker=`/`claude_invoker=` seam — for the new command and its Claude
  pass. `docs/cli/` is regenerated with `python -m plan_tool.cli_reference
  --write` (drift-guarded).

## Out of scope

- **The per-plan `features:` registry** (`Plan.features`/`Step.features`,
  `PLAN_FORMAT.md`, the existing feature-ref/self-referential smell checks). This
  plan does not touch it; it builds a distinct app-level catalog.
- **Changing `run`/`detail`/`jira` behavior.** They never read `FEATURES.md`.
- **Rewriting MISSION.md principle prose.** Part D adds only stable id anchors.
- **Hard-gating coverage.** The checks are advisory; exit code reflects
  completion (exit-code convention), never finding count.
- **Auto-generating principle→feature mappings without review** — the reconcile
  pass proposes, the operator (and `--iterate` gates) dispose.

## Risks

- **Conflation with the per-plan `features:` registry.** Severity: UX/conceptual.
  Two "features" concepts in one repo. Mitigation: name and document
  `FEATURES.md` distinctly as the app capability map; cross-link both ways so
  neither reads as the other.
- **Feature granularity is subjective.** Severity: scoping. Mitigation: anchor
  every feature to a concrete CLI subcommand or orchestrator module, not free
  invention — granularity follows the code surface.
- **Drift false positives on internal-only capabilities.** Severity: UX. A
  capability with no subcommand (e.g. the invoker seam, fingerprint gating).
  Mitigation: let a feature cite a module/orchestrator surface, not only a
  subcommand; the check resolves either.
- **Principle ids must stay stable** or `FEATURES.md` references rot. Severity:
  maintenance. Mitigation: reuse the existing 1–9 numbering as the stable id;
  document it as the contract.
- **`reconcile-mission` is a Claude-shelling command** — must default to the real
  invoker yet be fully test-neutralizable. Mitigation: route every Claude call
  through `invoker=`; add it to the TESTING.md neutralization table.

## Acceptance criteria

- `FEATURES.md` exists at the repo root, lists plan-tool's capabilities derived
  from the CLI/orchestrator surface, and each feature carries a stable
  kebab-case `id`, a `title`, ≥1 real surface, and ≥1 MISSION principle id. Its
  format is machine-parseable and the Part C check parses it.
- MISSION.md principles carry a stable, documented id scheme (the existing 1–9
  numbering or kebab slugs); principle prose is unchanged.
- `plan-tool reconcile-mission` (or the settled name) exists: on **no drift** in
  MISSION.md / the CLI surface / `FEATURES.md` it spends **no Claude** and exits
  clean; on drift it re-reconciles only the changed surfaces via the `invoker=`
  seam and converges under `--iterate`. The baseline fingerprint is re-stamped
  after a clean reconcile. Its `docs/cli/` entry is generated and the
  `test_cli_reference` drift guard passes.
- A deterministic, no-Claude honesty check runs from `validate` and the
  completeness deterministic layer: it flags a feature citing a surface absent at
  HEAD, a feature with no valid principle id, a subcommand with no owning
  feature, and a principle with no feature. All advisory, dismissible, lowest
  severity; none flips the exit code (exit-code convention). Inert when
  `FEATURES.md` is absent.
- The plan never touches the per-plan `features:` registry, and `run`/`detail`/
  `jira` parse a repo with `FEATURES.md` present byte-identically to today.
- Tests cover: `FEATURES.md` parsing, the honesty check's trip/non-trip cases,
  the reconcile command's no-drift (no Claude) and drift (fingerprint→Claude
  pass, neutralized invoker) paths, and the `cli_reference` drift guard for the
  new subcommand. The new Claude-shelling seam is added to TESTING.md's
  neutralization table.
- New code respects CLI layering (thin handler, logic in a top-level
  orchestrator) and introduces no import cycles.
