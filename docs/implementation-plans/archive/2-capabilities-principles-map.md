> **Auto-archived**: this plan was swept on 2026-06-22 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Capability–Principle Map
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Formalize a stable principle-id scheme in MISSION.md (add a position-
    and title-independent kebab slug anchor per principle; prose otherwise unchanged)
  files:
  - MISSION.md
  complexity: low
  change_type: non-code
  status: done
- id: 2
  title: Add plan_tool/capability_catalog.py (CAPABILITIES.md parser + MISSION principle-id
    extractor + CLI-subcommand enumerator) and author the initial CAPABILITIES.md
  creates:
  - plan_tool/capability_catalog.py
  - tests/test_capability_catalog.py
  - CAPABILITIES.md
  complexity: high
  change_type: feature
  depends_on:
  - 1
  status: done
- id: 3
  title: Add the deterministic no-Claude CAPABILITIES.md honesty check as a repo-wide
    function in capability_catalog.py, surfaced once from `validate` (cli/inspect.py),
    not the plan-scoped smell layer (absent-surface / no-valid-principle / orphan-subcommand
    [aliases collapsed, allowlist-aware] / unserved-principle / malformed-doc; advisory,
    inert when CAPABILITIES.md absent)
  files:
  - plan_tool/capability_catalog.py
  - plan_tool/cli/inspect.py
  - tests/test_capability_catalog.py
  - tests/cli/test_inspect_cmds.py
  complexity: high
  change_type: feature
  depends_on:
  - 2
  status: done
- id: 4
  title: 'Document the app-level CAPABILITIES.md catalog distinctly from the per-plan
    features: registry'
  files:
  - CLAUDE.md
  - PLAN_FORMAT.md
  complexity: low
  change_type: non-code
  depends_on:
  - 2
  - 3
  status: done
---
# Capability–Principle Map

## Overview

Adds an app-level **capability catalog** for plan-tool and a cheap deterministic check to keep it honest. Creates `CAPABILITIES.md` (repo root) mapping plan-tool's own capabilities to the **grounding principles** (in `MISSION.md`) each serves — the *testable* target, not the singular mission — and a **no-Claude** honesty check that flags a stale `CAPABILITIES.md` (a cited surface that no longer exists, a missing/invalid principle id, or a coverage gap). The capability list is derived from the CLI surface (`plan_tool/cli_reference.py` parser introspection), never hand-invented. A fingerprint-gated `reconcile-principles` command that *auto-re-fits* the map via Claude is **deferred** (see `## Deferred`): the deterministic check already catches the drift that matters and `CAPABILITIES.md` is small enough to hand-edit. This is a **distinct concept** from the per-plan `features:` registry (`Plan.features`/`Step.features`) — see the next section.

## Two distinct concepts (load-bearing)

This plan introduces **capabilities**, which are deliberately **not** the per-plan **`features:`** registry that already ships. Keeping them separate — and differently named — is the whole point:

- **Per-plan `features:`** (`Plan.features`/`Step.features`, `PLAN_FORMAT.md`) — a *logical identification of concepts within a single implementation plan*. Their job is to guide the planning process toward **brittle or under-refined concepts via convergence-gap analysis** across audit runs; `steps[].features` tags reference them and the smell checks / planned brittleness ledger consume them. They are **transient** — scoped to one plan, pointing *inward* at that plan's steps, and many never become shipped behavior (e.g. a concept that gets cut during refinement).
- **App-level capabilities** (`CAPABILITIES.md`, this plan) — *features of the implemented application* that **correlate to the grounding principles** in `MISSION.md`. They are **durable** — one catalog per repo, pointing *outward* at a code surface (subcommand/module) and the principle(s) that surface serves.

Different lifecycle (per-plan/transient vs repo-wide/durable), different referent (inward at steps vs outward at code + principles), different purpose (convergence diagnostics vs principle-alignment governance). The only thing they ever shared was the word "feature", so the app-level concept is named **capability** to remove the collision. There is **no shared id space and no cross-reference** between them. (A future, optional one-way bridge — a per-plan concept noting which capability it advances — is explicitly out of scope here.)

## Problem statement

`plan-tool` ships a `MISSION.md` (now a distinct mission + five grounding principles) and a fully-featured CLI, but **nothing maps the app's own capabilities to the principles they serve**, and nothing keeps such a map honest as the CLI surface and `MISSION.md` move. There is no canonical artifact a reader can consult to see which capability serves which principle, and no mechanism to flag when that relationship rots after a subcommand or principle changes. Mapping against the *principles* (each a testable rule) rather than the *mission* (a single, unfalsifiable purpose) is what makes the check concrete.

## Architecture

Three reinforcing parts (A, C, D). Part B — the fingerprint-gated auto-re-fit command — is **deferred**; see `## Deferred`.

**Part A — `CAPABILITIES.md`, machine-parseable, principle-linked.** A canonical doc at the repo root. Each capability entry carries a stable **kebab-case `id`** and human **`title`**; the **surfaces** it is implemented by — one or more CLI subcommands (e.g. `create`, `detail`, `run`) and/or orchestrator module(s) (e.g. `plan_tool/launcher.py`), since a capability may be internal (a module surface with no subcommand); and the **principles** it serves — references to MISSION.md principle ids (Part D). Format is lightweight but **parseable** so Part C validates it without Claude (a small structured block per capability — table or per-capability heading with `surfaces:`/`principles:` lines, author's choice, but parser and doc must agree). Build the initial catalog by walking the subcommand set (leaning on the same parser surface `cli_reference` reads), grouping subcommands into capabilities, and mapping each to the principle(s) it serves.

The capability `id` is a **diff-stable handle, nothing more**: it lets honesty-check findings (and a future `reconcile-principles`) address a specific capability consistently across runs even when its title is reworded. Unlike a per-plan `features:` id, **nothing tags against it** — there is no `steps[].features` analog and no step renumber to survive — so the id is an addressing convenience, **not** a referent. Do **not** justify the *capability* id by the per-plan "a `split`/`merge` renumber can't dangle a slug" rationale; nothing references the capability id. That same rationale **does** apply to the **principle** ids, which are load-bearing referents (capabilities cite them) and must survive a principle reorder/merge — the MISSION 9→5 redesign is the proof; see Part D. The load-bearing joins in Part C key on **surfaces** and **principle ids**, never on the capability id.

**Part C — deterministic honesty check (no Claude), repo-wide.** A cheap check living in `plan_tool/capability_catalog.py`, surfaced **once** from `plan-tool validate` (`cli/inspect.py:cmd_validate`) at **repo scope** — *not* inside `review.collect_smell_findings`, which is plan-scoped (`(plan, repo_root, *, plan_name)`): the capability check reads no `plan`, needs the CLI parser surface that seam isn't handed, and folded there would re-emit identical findings once per validated plan and misattribute them. Its findings are labeled repo-wide, not tied to a plan. Checks: every capability cites **≥1 surface that exists at HEAD** (cited subcommand is real, cited module path exists); every capability references **≥1 valid principle id**; **coverage gaps** — a subcommand with no owning capability, and a principle with no capability serving it. Two enumeration rules keep it honest: subcommands are enumerated by **primary name only** (collapsing aliases the way `cli_reference` does, so `reconcile`/`review`/`verify` don't read as orphans), and a subcommand may be marked **intentionally capability-less** via a small allowlist so a deliberately-omitted command doesn't nag forever. A `CAPABILITIES.md` that is **present but malformed** (unparseable block, a capability missing `surfaces:`/`principles:`, a duplicate `id`) yields a finding rather than a crash or a silent pass (principle #2 — *validate, don't trust*). All findings **advisory, lowest severity, dismissible**; none flips the exit code. Inert when `CAPABILITIES.md` is absent.

**Part D — stable principle ids in MISSION.md.** `CAPABILITIES.md` references and the Part C check need **stable principle anchors**, and they are load-bearing (capabilities cite them). MISSION.md's principle *numbering is not a stable id* — the mission/principles redesign reordered, renamed, and merged 9 principles into 5, so principle `1` no longer denotes what it did. The canonical scheme is therefore a **position- and title-independent kebab slug**, assigned once per principle and never changed on reorder/reword, with a documented rule for **retiring** a slug when principles merge (a capability still citing the retired slug then trips the Part C no-valid-principle check). Add the slug anchor to each principle; do **not** rewrite principle prose (human-owned).

## References

- [argparse — Parser for command-line options, arguments and subcommands](https://docs.python.org/3/library/argparse.html) — Official Python stdlib reference for ArgumentParser, subparsers, and Action objects — the parser surface the catalog is introspected from.
- [How to use fixtures (pytest)](https://docs.pytest.org/en/stable/how-to/fixtures.html) — Official pytest fixtures reference (incl. tmp_path) for writing the hermetic parsing and honesty-check tests.

(References for the deferred `reconcile-principles` machinery — `hashlib` for the baseline fingerprint, the Claude Code CLI reference for the `invoker=` pass — return with that work; see `## Deferred`.)

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- **The per-plan `features:` registry** (`Plan.features`/`Step.features`, `PLAN_FORMAT.md`, the existing feature-ref/self-referential smell checks) — this plan builds a distinct app-level capability catalog and does not touch it. The two are different concepts (see [Two distinct concepts](#two-distinct-concepts-load-bearing)).
- **A cross-reference or shared id space between capabilities and per-plan features** — including the future one-way "this plan concept advances capability X" bridge.
- **Changing `run`/`detail`/`jira` behavior** — they never read `CAPABILITIES.md`.
- **Rewriting MISSION.md principle prose** — Part D adds only stable id anchors.
- **Hard-gating coverage** — the checks are advisory; exit code reflects completion, never finding count.
- **Auto-generating or auto-re-fitting principle→capability mappings** — the MVP catalog is authored and maintained by hand; the deferred `reconcile-principles` would propose edits for the operator (and `--iterate` gates) to dispose, never apply them unreviewed.

## Risks

- **Conflation with the per-plan `features:` registry.** Severity: UX/conceptual. Mitigation (now baked in): the app-level concept is named **capability** (`CAPABILITIES.md`), not "feature", removing the homonym; the [Two distinct concepts](#two-distinct-concepts-load-bearing) section and step 4's docs state the distinction explicitly and cross-link both ways.
- **Capability granularity is subjective.** Severity: scoping. Mitigation: anchor every capability to a concrete CLI subcommand or orchestrator module, not free invention — granularity follows the code surface.
- **Drift false positives on internal-only capabilities.** Severity: UX — a capability with no subcommand (e.g. the invoker seam, fingerprint gating). Mitigation: let a capability cite a module/orchestrator surface, not only a subcommand; the check resolves either.
- **Principle ids must stay stable** or `CAPABILITIES.md` references rot — and positional numbering is *not* stable (the 9→5 mission redesign reordered and merged principles, so `1` changed meaning). Severity: maintenance. Mitigation: a position- and title-independent kebab slug per principle, assigned once and surviving reorder/reword; document it as the contract and define slug retirement on merge.
- **Principle #2 is a near-universal baseline.** Severity: signal. Nearly every capability serves *deterministically driven non-determinism*, so a capability→#2 link carries little information and the "principle with no capability" check is trivially green. Mitigation: treat #2 as an architectural baseline; the discriminating value is each capability's link to the *narrow* principles (keep-the-plan-true-to-code, survive-interruption) and convergence — author and review the map for those, not for #2 coverage.

## Testing

Tests cover: `CAPABILITIES.md` parsing; and the honesty check's trip and non-trip cases (capability citing an absent surface, capability with no valid principle id, subcommand with no owning capability, principle with no capability). Default to unit tests for parsing and the deterministic honesty check. Existing suites — including `tests/cli/test_cli_reference.py` and the `review.py`/`collect_smell_findings` smell-check tests — must still pass.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (non-code) — verification appropriate to the artifacts; no test-ordering directive.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- `CAPABILITIES.md` exists at the repo root, lists plan-tool's capabilities derived from the CLI/orchestrator surface, and each capability carries a stable kebab-case `id`, a `title`, ≥1 real surface, and ≥1 MISSION principle id; its format is machine-parseable and the Part C check parses it.
- The plan/docs state explicitly that app-level capabilities and the per-plan `features:` registry are distinct concepts (distinct names, lifecycle, referent, and purpose), with no shared id space; the capability `id` is documented as a diff-stable handle, not a referent, and is **not** justified by the per-plan renumber rationale.
- MISSION.md principles carry a stable, documented id scheme — a position- and title-independent kebab slug per principle (not the volatile numbering), surviving reorder/reword with a defined retirement rule on merge; principle prose is unchanged.
- A deterministic, no-Claude, **repo-wide** honesty check runs once from `validate` (in `capability_catalog.py`, not the plan-scoped smell layer): it flags a capability citing a surface absent at HEAD, a capability with no valid principle id, a subcommand (primary name, aliases collapsed, allowlist-aware) with no owning capability, a principle with no capability, and a present-but-malformed `CAPABILITIES.md`; all advisory, dismissible, lowest severity; none flips the exit code; inert when `CAPABILITIES.md` is absent.
- The plan never touches the per-plan `features:` registry, and `run`/`detail`/`jira` parse a repo with `CAPABILITIES.md` present byte-identically to today.
- New code respects CLI layering (thin handler, logic in a top-level orchestrator) and introduces no import cycles.

## Deferred

- **`reconcile-principles` — fingerprint-gated auto-re-fit (former Part B + steps 4–5).** A subcommand modeled on `reconcile-plan --refresh`: a **baseline fingerprint** under `.plan-tool/` over (a) `MISSION.md`, (b) the CLI surface, and (c) `CAPABILITIES.md`; **no drift → no Claude, exit clean**; **drift → re-fit the changed surfaces** via a Claude pass through the `invoker=` seam (never a bare shell-out) proposing `CAPABILITIES.md` edits, converging under `--iterate`, then re-stamping the baseline. When built it must resolve the issues the prior audit surfaced for this command: (i) author its **own** capability entry so Part C's orphan check doesn't flag it the moment it ships; (ii) fingerprint the CLI surface via a **defined deterministic serialization** — argparse introspection has no backing file for `compute_code_fingerprint` to hash, and a single combined hash can't attribute *which* surface drifted, so use per-surface fingerprints; (iii) re-stamp the baseline **after** its own `CAPABILITIES.md` edit (else it re-detects its own write as drift and never converges); and (iv) drive convergence over a **non-`Plan` target** (`CAPABILITIES.md`), which the `Plan`-centric `apply_finding`/`auto_reconcile` loop doesn't support as-is. Wiring: `plan_tool/principle_reconcile.py` orchestrator + a thin `cli/principle_cmd.py` handler + parser/package registration, the generated `docs/cli/` entry with the `test_cli_reference` extension, and the new Claude seam added to TESTING.md's neutralization table.
- **Why deferred:** the deterministic Part C check already flags the drift that matters (absent surface, invalid principle id, coverage gap) for **no Claude**, and `CAPABILITIES.md` is small enough to hand-edit. Spending a Claude pass to regenerate it is in tension with principle #2 (*let code find the patterns — what a check can decide shouldn't cost an LLM round-trip*). Revisit only if real drift appears that the deterministic check can't cheaply resolve by hand.
