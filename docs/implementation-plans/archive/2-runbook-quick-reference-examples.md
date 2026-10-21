> **Auto-archived**: this plan was swept on 2026-06-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Runbook Quick Reference Examples
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Add four power-invocation rows to RUNBOOK.md Quick reference (completeness-audit
    --iterate --commit, completeness-apply --commit, detail --all --commit, sweep
    --commit)
  files:
  - RUNBOOK.md
  complexity: low
  change_type: non-code
  gate:
  - uv run plan-tool completeness-audit --help | grep -q -- --iterate && uv run plan-tool
    completeness-audit --help | grep -q -- --commit
  - uv run plan-tool completeness-apply --help | grep -q -- --commit
  - uv run plan-tool detail --help | grep -q -- --all && uv run plan-tool detail --help
    | grep -q -- --commit
  - uv run plan-tool sweep --help | grep -q -- --commit
  - grep -qF 'plan-tool completeness-audit <name> --iterate --commit' RUNBOOK.md &&
    grep -qF 'plan-tool completeness-apply <name> --commit' RUNBOOK.md && grep -qF
    'plan-tool detail <name> --all --commit' RUNBOOK.md && grep -qF 'plan-tool sweep
    --commit' RUNBOOK.md
  status: done
---
# Runbook Quick Reference Examples

## Overview

Add four "power invocation" example rows to the [Quick reference](RUNBOOK.md#quick-reference) section of `RUNBOOK.md`, mirroring the existing `plan-tool run <name> --all --commit` row in the Execution family. Each new row pairs an everyday "do the whole job and commit" command with a payoff-oriented `…to` cell, keeping the two-column `| Run | …to |` format and family grouping. This is documentation-only: no code, no flags, no behavior changes, and every example must already be a valid invocation.

## Problem statement

Today most command families in the Quick-reference tables list only the minimal form of each command. Only the Execution family shows a canonical power combo (`plan-tool run <name> --all --commit`, run every step committing each green step). For commands that have an equivalent "do the whole job and commit" combo — `completeness-audit`, `completeness-apply`, `detail`, and `sweep` — the everyday power invocation is undocumented, so readers don't learn it from the Quick reference.

## Architecture

This plan introduces no components; it edits `RUNBOOK.md` only. The single design decision is which "do the whole job and commit" rows belong in the Quick reference and where each sits, governed by the existing table structure: rows live under their command's family table (Plan audit, Authoring, State management) in the established two-column `| Run | …to |` format, one power-combo row per command alongside its bare form — mirroring the Execution family's `plan-tool run <name> --all --commit` precedent.

The selection follows a single inclusion rule, traded off against table bloat: a row qualifies only when a command has an everyday `--commit`/`--iterate` combo that materially differs from its minimal form. That rule excludes commands whose minimal form is already the everyday form (`list`, `status`, `validate`, `jira`), `create` (where `--iterate` is the default), and `verify-all` (whose concrete rows already exist), and it keeps niche flags (`--no-iterate`, `--reuse-audit`, `--dry-run`) in the per-workflow sections per the section preamble. Placeholder usage (`<name>` / `<slug>`) inherits from the section's "Placeholders used across this runbook" list rather than introducing new conventions.

## References

- `RUNBOOK.md` — the Quick reference section being edited; its existing Execution-family `plan-tool run <name> --all --commit` row is the precedent each new row mirrors, and its "Placeholders used across this runbook" list and section preamble set the placeholder/scope conventions.
- `plan-tool completeness-audit --help`, `plan-tool completeness-apply --help`, `plan-tool detail --help`, `plan-tool sweep --help` — authoritative source for the exact flags of each documented invocation; every row must validate against these.
- `CLAUDE.md` (Authoring plans with plan-tool) — establishes the `--iterate` / `--commit` everyday-combo conventions the inclusion rule encodes.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- No new CLI flags or behavior — documentation only.
- No restructuring of the Quick-reference families or the wider runbook.
- No new examples for commands whose minimal form is already the common form (`list`, `status`, `validate`, `jira`) — their minimal form is the everyday form.
- No second example for `create`, where `--iterate` is already the default.
- No second row for `verify-all`, whose `--rollup` and `--mode <m>` rows are already concrete.
- Niche flags (`--no-iterate`, `--reuse-audit`, `--dry-run`, …) stay in the per-workflow sections per the section preamble; only everyday combos (`--commit`, `--iterate`) qualify for the table.

## Risks

- Documenting a non-existent invocation: each command/flag must be verified against `plan-tool <cmd> --help` before writing it, so the runbook never documents an invalid command.
- Turning the table into a flag dump: mitigated by the one-example-row-per-command cap, mirroring the `run` family which keeps the bare form plus exactly one power-combo row.
- Placeholder inconsistency: `<name>` / `<slug>` usage must stay consistent with the rest of the section and its "Placeholders used across this runbook" list.

## Testing

Documentation-only change; verification is manual. Confirm each new invocation is valid against the current CLI via `plan-tool <cmd> --help` for `completeness-audit`, `completeness-apply`, `detail`, and `sweep`. Confirm the Quick-reference preamble still reads true after the edits and that no other `RUNBOOK.md` section changed except as needed for internal consistency (anchor/TOC integrity — none expected for table-row additions).

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- The four rows appear in their correct family tables in the existing `| Run | …to |` format, each with a payoff-oriented `…to` cell:
  - **Plan audit** / `completeness-audit`: `plan-tool completeness-audit <name> --iterate --commit` → *Converge the audit loop (gates → apply-finding → re-audit) and stage the applied edits.*
  - **Plan audit** / `completeness-apply`: `plan-tool completeness-apply <name> --commit` → *Apply the conceptual gaps from the last audit and stage the result.*
  - **Authoring** / `detail`: `plan-tool detail <name> --all --commit` → *Author every step's detail file in one pass, committing each.*
  - **State management** / `sweep`: `plan-tool sweep --commit` → *Archive finished / adopt stray plans, then stage the manifest + moves.*
- Every documented invocation is valid against the current CLI (`plan-tool <cmd> --help`).
- The Quick-reference preamble still reads true: niche flags remain deferred to per-workflow sections; only everyday combos (`--commit`, `--iterate`) were added.
- No other section of `RUNBOOK.md` is changed except as needed for internal consistency.
- `<name>` / `<slug>` placeholder usage stays consistent with the section's "Placeholders used across this runbook" list.

## Deferred

- Exact wording of the `…to` cells is left for the author to refine during `plan-tool detail`; the rows and the commands they document are fixed.
