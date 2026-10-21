> **Replaced**: this file has been superseded by `docs/implementation-plans/2-features-mission-reconcile.md`.
> Preserved here for history; do not edit.

## Overview

Adds an app-level capability catalog for plan-tool and the machinery to keep it honest. Creates `FEATURES.md` (repo root) mapping plan-tool's own capabilities to the MISSION.md grounding principles each serves, a fingerprint-gated `reconcile-mission` command (mirroring `reconcile-plan --refresh`) that re-fits the map when the CLI surface or mission drifts while spending **no Claude** on a no-drift run, and a cheap no-Claude honesty check in the advisory layer that flags a stale `FEATURES.md`. The features list is derived from the CLI surface (`plan_tool/cli_reference.py` parser introspection), never hand-invented, so the same surface that generates the catalog also fingerprints its drift. This is distinct from the per-plan `features:` registry (`Plan.features`/`Step.features`); the new artifact is app-level and describes plan-tool itself.

## Problem statement

`plan-tool` ships a `MISSION.md` (the mission + nine numbered grounding principles) and a fully-featured CLI, but **nothing maps the app's own capabilities to the mission they serve**, and nothing keeps such a map honest as the CLI and mission move. There is no canonical artifact a reader can consult to see which capability serves which principle, and no mechanism to flag when that relationship rots after a subcommand or principle changes.

## Architecture

Four reinforcing parts.

**Part A — `FEATURES.md`, machine-parseable, principle-linked.** A canonical doc at the repo root. Each feature entry carries a stable **kebab-case `id`** and human **`title`**; the **surfaces** it is implemented by — one or more CLI subcommands (e.g. `create`, `detail`, `run`) and/or orchestrator module(s) (e.g. `plan_tool/launcher.py`), since a feature may be internal (a module surface with no subcommand); and the **principles** it serves — references to MISSION.md principle ids (Part D). Format is lightweight but **parseable** so Part C validates it without Claude (a small structured block per feature — table or per-feature heading with `surfaces:`/`principles:` lines, author's choice, but parser and doc must agree). Build the initial catalog by walking the subcommand set (leaning on the same parser surface `cli_reference` reads), grouping subcommands into capabilities, and mapping each to the principle(s) it serves.

**Part B — `reconcile-mission`: fingerprint-gated re-fit.** A new subcommand modeled on `reconcile-plan --refresh`. Tracks a **baseline fingerprint** under `.plan-tool/` covering (a) `MISSION.md`, (b) the CLI surface (the subcommand/flag inventory `cli_reference` reads), and (c) `FEATURES.md` itself — content-hash, the way completeness reports carry a `code_fingerprint`. **No drift → spend no Claude, exit clean.** **Drift → re-reconcile only the changed surfaces** via a Claude pass through the standard `invoker=` seam (never a bare shell-out) that proposes `FEATURES.md` edits; output lands as advisory findings and under `--iterate` converges (gates → `apply_finding` → re-audit). Re-running after a clean reconcile re-stamps the baseline. Wire through existing CLI layering: a new orchestrator (suggest `plan_tool/mission_reconcile.py`), a **thin** `cli/` handler, and a parser entry; the orchestrator owns fingerprint/diff/Claude-pass logic, the handler only wires args.

**Part C — deterministic honesty check (no Claude).** A cheap heuristic in the advisory smell/validation layer (`review.py`, `collect_smell_findings`), surfaced from `plan-tool validate` and the completeness deterministic layer so it fires before any Claude spend. Checks: every feature cites **≥1 surface that exists at HEAD** (cited subcommand is real, cited module path exists); every feature references **≥1 valid MISSION principle id**; **coverage gaps** — a subcommand with no owning feature, and a principle with no feature serving it. All findings **advisory, lowest severity, dismissible**; none flips the exit code. Inert when `FEATURES.md` is absent.

**Part D — stable principle ids in MISSION.md (minimal).** `FEATURES.md` references and the Part C check need **stable principle anchors**. MISSION.md already numbers its principles `1`–`9` with titles; formalize that numbering (or a kebab slug per title) as the canonical id scheme, mirroring how the per-plan feature registry uses stable `id`s. A tiny, non-disruptive edit: do **not** rewrite principle prose (human-owned), only ensure each principle has a referenceable, stable id and document the scheme.

## Out of scope

- **The per-plan `features:` registry** (`Plan.features`/`Step.features`, `PLAN_FORMAT.md`, the existing feature-ref/self-referential smell checks) — this plan builds a distinct app-level catalog and does not touch it.
- **Changing `run`/`detail`/`jira` behavior** — they never read `FEATURES.md`.
- **Rewriting MISSION.md principle prose** — Part D adds only stable id anchors.
- **Hard-gating coverage** — the checks are advisory; exit code reflects completion, never finding count.
- **Auto-generating principle→feature mappings without review** — the reconcile pass proposes, the operator (and `--iterate` gates) dispose.

## Risks

- **Conflation with the per-plan `features:` registry.** Severity: UX/conceptual — two "features" concepts in one repo. Mitigation: name and document `FEATURES.md` distinctly as the app capability map; cross-link both ways so neither reads as the other.
- **Feature granularity is subjective.** Severity: scoping. Mitigation: anchor every feature to a concrete CLI subcommand or orchestrator module, not free invention — granularity follows the code surface.
- **Drift false positives on internal-only capabilities.** Severity: UX — a capability with no subcommand (e.g. the invoker seam, fingerprint gating). Mitigation: let a feature cite a module/orchestrator surface, not only a subcommand; the check resolves either.
- **Principle ids must stay stable** or `FEATURES.md` references rot. Severity: maintenance. Mitigation: reuse the existing 1–9 numbering as the stable id; document it as the contract.
- **`reconcile-mission` is a Claude-shelling command** — must default to the real invoker yet be fully test-neutralizable. Mitigation: route every Claude call through `invoker=`; add it to the TESTING.md neutralization table.

## Testing

Tests cover: `FEATURES.md` parsing; the honesty check's trip and non-trip cases (feature citing an absent surface, feature with no valid principle id, subcommand with no owning feature, principle with no feature); the reconcile command's no-drift path (asserts **no Claude** is invoked) and drift path (fingerprint → Claude pass through a **neutralized invoker**, never a bare shell-out); and the `cli_reference` drift guard (`tests/cli/test_cli_reference.py`) extended for the new subcommand. The new Claude-shelling seam is added to TESTING.md's neutralization table. Default to unit tests for parsing and the deterministic honesty check; reserve `@pytest.mark.integration` for driving the `reconcile-mission` command end-to-end across the orchestrator/handler/parser wiring. Existing suites — including `tests/cli/test_cli_reference.py` and the `review.py`/`collect_smell_findings` smell-check tests — must still pass.

## Acceptance criteria

- `FEATURES.md` exists at the repo root, lists plan-tool's capabilities derived from the CLI/orchestrator surface, and each feature carries a stable kebab-case `id`, a `title`, ≥1 real surface, and ≥1 MISSION principle id; its format is machine-parseable and the Part C check parses it.
- MISSION.md principles carry a stable, documented id scheme (the existing 1–9 numbering or kebab slugs); principle prose is unchanged.
- `plan-tool reconcile-mission` (or the settled name) exists: on **no drift** in MISSION.md / the CLI surface / `FEATURES.md` it spends **no Claude** and exits clean; on drift it re-reconciles only the changed surfaces via the `invoker=` seam and converges under `--iterate`; the baseline fingerprint is re-stamped after a clean reconcile; its `docs/cli/` entry is generated and the `test_cli_reference` drift guard passes.
- A deterministic, no-Claude honesty check runs from `validate` and the completeness deterministic layer: it flags a feature citing a surface absent at HEAD, a feature with no valid principle id, a subcommand with no owning feature, and a principle with no feature; all advisory, dismissible, lowest severity; none flips the exit code; inert when `FEATURES.md` is absent.
- The plan never touches the per-plan `features:` registry, and `run`/`detail`/`jira` parse a repo with `FEATURES.md` present byte-identically to today.
- New code respects CLI layering (thin handler, logic in a top-level orchestrator) and introduces no import cycles.
