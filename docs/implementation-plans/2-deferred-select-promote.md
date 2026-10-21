---
title: Deferred Select Promote
status: planning
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Extract the shared seed skeleton into plan_tool/seed_render.py and move scope_out
    onto it
  files:
  - plan_tool/scope_out.py
  - tests/test_scope_out.py
  creates:
  - plan_tool/seed_render.py
  - tests/test_seed_render.py
  complexity: medium
  change_type: refactor
  status: current
- id: 2
  title: Move reground's render_rebaseline_seed onto plan_tool/seed_render.py
  files:
  - plan_tool/reground.py
  - tests/test_reground.py
  complexity: low
  change_type: refactor
  depends_on:
  - 1
- id: 3
  title: Add plan_tool/deferred_promote.py with the backlog-entry renderer and severity
    routing
  creates:
  - plan_tool/deferred_promote.py
  - tests/test_deferred_promote.py
  complexity: medium
  change_type: feature
- id: 4
  title: Add the plan-seed scaffold renderer to deferred_promote.py
  files:
  - plan_tool/deferred_promote.py
  - tests/test_deferred_promote.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  - 3
- id: 5
  title: Add the optional Claude crisp/brief synthesis behind the invoker seam in
    deferred_promote.py
  files:
  - plan_tool/deferred_promote.py
  - tests/test_deferred_promote.py
  complexity: medium
  change_type: feature
  depends_on:
  - 3
  - 4
- id: 6
  title: Add the promote orchestrator with idempotent seed/entry-first emission and
    a recommend-vs-apply result
  files:
  - plan_tool/deferred_promote.py
  - tests/test_deferred_promote.py
  complexity: medium
  change_type: feature
  depends_on:
  - 3
  - 4
  - 5
- id: 7
  title: Add --select ids/all, the --apply gate, and the promoter wiring to plan-tool
    deferred
  files:
  - plan_tool/cli/deferred_cmd.py
  - plan_tool/cli/app.py
  - tests/cli/test_deferred_cmd.py
  complexity: high
  change_type: feature
  depends_on:
  - 6
- id: 8
  title: Add the interactive --select walk to plan-tool deferred
  files:
  - plan_tool/cli/deferred_cmd.py
  - tests/cli/test_deferred_cmd.py
  complexity: medium
  change_type: feature
  depends_on:
  - 7
- id: 9
  title: Document the select/promote capability and regenerate the CLI reference
  files:
  - CAPABILITIES.md
  - USE_CASES.md
  - README.md
  - BACKLOG.md
  - docs/cli/deferred.md
  - docs/cli/README.md
  complexity: low
  change_type: non-code
  depends_on:
  - 7
  - 8
---
# Deferred Select Promote

## Overview

Extend the read-only `plan-tool deferred` scan (Plan A) with two new phases layered on top of Plan A's `DeferredItem` model and command. **Select** presents the surfaced concepts — each already carrying a stable id (`d1`, `d2`, …) from Plan A — and lets the operator choose which to move forward with, via an interactive `--select` walk at a TTY plus a non-interactive selection path (`--select d1,d3`, `--select all`) so a Claude session or unattended run can drive it without silently skipping. **Promote** is the gated mutation: for each selected item it emits a correctly shaped, origin-backlinked backlog entry (routed to `BACKLOG.md` vs `BUG_BACKLOG.md`) and/or scaffolds a plan seed under `plan-seeds/<slug>.md`, per the item's `direct`-vs-`plan-tool` tag. Mutation is recommend-only unless `--apply` (+ TTY confirm, or `-y` non-interactively), emission is seed/entry-first and idempotent, and the command joins the mutation lock set. Depends on Plan A having shipped; it consumes Plan A's scan and must not re-implement harvest/dedup/classify.

## Problem statement

Plan A surfaces parked work from four sources (plan-body sections, report `open_deferred` / skipped findings, and `concepts.json` `defer`/`wont_do` records) and prints a read-only digest, but moving any surfaced item into a backlog entry or a seed is still a manual, easily-skipped step. The user's ask — "let the user select the concepts to move forward with" — maps directly onto the concept records especially: they are the tool's own decisions to park a concept, and a *confirmed* `defer`/`wont_do` otherwise never rolls up into forward-looking work. This plan closes that gap by making promotion one selection away, while keeping the scan itself read-only and the mutation explicitly gated.

## Architecture

Consume Plan A and add a promoter module plus command phases. `plan_tool/deferred_digest.py` (from Plan A) is reused as-is for the scan — harvest/dedup/classify are not re-implemented. A new shared leaf `plan_tool/seed_render.py` extracts the common `create --from-existing` seed-skeleton renderer that `plan_tool/scope_out.py` (`render_carved_seed`) and `plan_tool/reground.py` (`render_rebaseline_seed`) each hand-roll today, so the promoter reuses one renderer instead of adding a third copy; those two call sites are refactored onto it behavior-preservingly (covered by tests proving the extraction preserves today's output). A new orchestrator leaf `plan_tool/deferred_promote.py` takes a set of selected `DeferredItem`s and renders backlog entries and/or seed scaffolds via `seed_render.py` — pure rendering plus an injectable `invoker=` for the optional Claude call that crisps a bullet into a one-line concept and a seed brief (defaults to the real shell-out, stubbed in tests). `plan_tool/cli/deferred_cmd.py` (from Plan A) gains the `--select` and `--apply` flags, the interactive walk, and the mutation gate, is added to the mutation lock set, and refreshes the CLI reference. New leaves sit below the CLI; lazy-import if a cycle would close.

**Select** has two modes per the CLAUDE.md session-vs-operator split: an interactive `--select` walk (TTY, human operator) presenting each item (summary, provenance, tag) with `promote` / `skip` / `both` / `quit`; and a non-interactive path (`--select d1,d3,d7` or `--select all` plus a required `-y`) for a Claude session or unattended run. The interactive walk must not run on a non-interactive stdin and silently skip (the `completeness-apply` trap the codebase already learned from) — with no `--select` and no TTY, print the digest and exit 0 without mutating.

**Promote** follows the tag per selected item, overridable in the interactive walk: `direct` → append a backlog entry to the routed file (a report finding with `high`/`critical` severity → `BUG_BACKLOG.md`, everything else → `BACKLOG.md`) carrying a title, one-line summary, an `Origin:` backlink, and the `Approach:` tag, shaped to need no hand-editing; `plan-tool` → scaffold `plan-seeds/<slug>.md` via `seed_render.py` with Overview / Problem / Design-stub / Acceptance sections seeded from the item and **including the backlog-reconciliation requirement** so every generated seed is itself CLAUDE.md-compliant; `both` → emit a backlog entry that references the scaffolded seed. Mutation is recommend-only unless `--apply` (+ TTY confirm, or `-y` non-interactively) — the apply-or-recommend gate shape used by `scope_out_step` / `escalate_to_split`. Emission is seed/entry-first and idempotent: re-running skips an item whose backlog entry or seed already exists (Plan A's dedup catches it on the next scan anyway). Concept-deferral promotion is distinct from `scope-review`: `scope-review` confirms a *pending* deferral within a plan (include / defer / wont_do); this feature takes an *already-decided* `defer`/`wont_do` concept and promotes it into forward-looking work — they compose, and this feature must never re-open or mutate the concept record.

## References

- [argparse — Parser for command-line options, arguments and subcommands (Python docs)https: — Official reference for add_argument/subparsers/nargs used to wire the new --select and --apply flags and the -y non-interactive opt-in onto the deferred command.
- [io — Core tools for working with streams: IOBase.isatty() (Python docs)https: — Defines the isatty() stream check that backs the TTY-vs-non-interactive gate deciding whether the interactive select walk runs or the command prints-and-exits-0.
- [subprocess — Subprocess management (Python docs)https: — run()/Popen reference for the real-CLI invoker= shell-out that crisps a bullet into a one-line concept and seed brief, and how to shape it for hermetic stubbing.
- [How to monkeypatch/mock modules and environments (pytest docs)https: — Official how-to for overriding attributes and functions in tests — the mechanism for stubbing the injectable invoker= seam so no real claude binary spawns.
- [Claude Code CLI reference (Anthropic docs)https: — Documents the claude CLI commands and non-interactive/print-mode flags an implementer needs when constructing and validating the promoter's subprocess invocation.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- **Re-implementing the scan** — harvest/dedup/classify/render live in Plan A.
- **Implementing the promoted work** — this writes backlog entries and seed files; it never authors a plan (`create`), writes code, or runs a plan.
- **Mutating source plans, reports, or concept records** — read-only over all sources; the only writes are new backlog entries and new `plan-seeds/*.md`.
- **Re-opening or re-deciding concept deferrals** — that is `scope-review`'s job.

## Risks

- **Interactive walk skips on non-interactive stdin** (the `completeness-apply` trap). Mitigation: require explicit `--select` ids/`all` off a TTY; never run the interactive walk without a TTY; no `--select` + no TTY → print-and-exit.
- **Generated seed/entry shape drifts from the hand-authored convention.** Mitigation: render via the shared `seed_render.py`; a test asserts a generated seed carries the backlog-reconciliation requirement.
- **`seed_render` extraction changes scope-out/reground seed output.** Mitigation: cover `render_carved_seed` / `render_rebaseline_seed` with tests proving the extraction preserves today's output, green before the step finishes.
- **Double-promotion on re-run.** Mitigation: idempotent, entry/seed-first emission skips an item whose entry/seed already exists.
- **Import-cycle pressure.** Mitigation: keep the new leaves below the CLI; lazy-import if a cycle would close.

## Testing

Follow the project's unit-first convention (`plan_tool/X.py` → `tests/test_X.py`), stubbing the `invoker=` seam so no real `claude` spawns. Cover `render_carved_seed` (`scope_out.py`) and `render_rebaseline_seed` (`reground.py`) with tests proving `seed_render.py`'s extraction preserves today's output, green before the step finishes. Add a test asserting a generated `plan-tool` seed carries the backlog-reconciliation requirement. Cover the select modes: interactive walk (`promote`/`skip`/`both`/`quit`), non-interactive `--select d1,d3` / `--select all`, and the no-`--select`-no-TTY print-and-exit-0 path (assert no mutation). Cover promote routing (`high`/`critical` report finding → `BUG_BACKLOG.md`, else `BACKLOG.md`), the `--apply` + confirm/`-y` gate, and idempotent re-run skipping. Assert the classify and seed-synthesis Claude calls route through `invoker=` and are stubbed. Add an integration test driving the `plan-tool deferred --select … --apply` command end-to-end only where cross-module CLI wiring would be missed by a unit test.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (refactor) — tests covering the behavior it changes; green before it finishes.
- step 2 (refactor) — tests covering the behavior it changes; green before it finishes.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (feature) — unit tests added with the implementation; green before completion.
- step 5 (feature) — unit tests added with the implementation; green before completion.
- step 6 (feature) — unit tests added with the implementation; green before completion.
- step 7 (feature) — unit tests added with the implementation; green before completion.
- step 8 (feature) — unit tests added with the implementation; green before completion.
- step 9 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- `--select` drives an interactive promote/skip/both/quit walk at a TTY; `--select d1,d3` / `--select all` drive it non-interactively; with no `--select` and no TTY nothing mutates and the command exits 0.
- Promotion is gated behind `--apply` (+ TTY confirm, or `-y` non-interactively); without it, promotion is recommend-only.
- A promoted `direct` item appends a correctly shaped, `Origin:`-backlinked entry to the routed file (`high`/`critical` report finding → `BUG_BACKLOG.md`, else `BACKLOG.md`); a promoted `plan-tool` item scaffolds `plan-seeds/<slug>.md` carrying the backlog-reconciliation requirement.
- `plan_tool/seed_render.py` is the single seed-skeleton renderer; `scope_out.py` and `reground.py` use it and their tests confirm the extraction preserves today's output.
- Emission is idempotent: re-running skips an item whose entry/seed already exists.
- No source plan, report, or concept record is mutated.
- The command is added to the mutation lock set; completion exits 0 regardless of how many items were surfaced or promoted (exit-code convention); the classify and seed-synthesis Claude calls route through the `invoker=` seam and are stubbed in tests (no real `claude` spawn); the new modules add no import cycle.
- The final docs step records the select/promote capability in `CAPABILITIES.md` / `USE_CASES.md` / `README.md` and updates `BACKLOG.md`.

## Deferred

- **Scope-guard `steps: []` out-of-scope stubs** as a fifth harvest source (belongs to Plan A's harvester if added; low-signal).
- **`--fail-on-findings`** — flip rc non-zero when the untriaged remainder is non-empty, for a CI "backlog has drifted from the plans" gate.
- **Auto-authoring a plan** from a promoted `plan-tool` seed (`create` chaining). Kept out: promotion stops at the seed so a human still reviews before `create`.

Open questions to resolve during `create`/`detail`: default emission for a `direct` item (lean entry-only, with `both` available in the interactive walk); confirmed vs pending concept deferrals (lean: surface both, tag pending ones as not yet `scope-review`-signed).
