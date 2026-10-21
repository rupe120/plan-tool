> **Replaced**: this file has been superseded by `docs/implementation-plans/2-runbook-quick-reference-examples.md`.
> Preserved here for history; do not edit.

## Overview

Add four "power invocation" example rows to the [Quick reference](RUNBOOK.md#quick-reference) section of `RUNBOOK.md`, mirroring the existing `plan-tool run <name> --all --commit` row in the Execution family. Each new row pairs an everyday "do the whole job and commit" command with a payoff-oriented `…to` cell, keeping the two-column `| Run | …to |` format and family grouping. This is documentation-only: no code, no flags, no behavior changes, and every example must already be a valid invocation.

## Problem statement

Today most command families in the Quick-reference tables list only the minimal form of each command. Only the Execution family shows a canonical power combo (`plan-tool run <name> --all --commit`, run every step committing each green step). For commands that have an equivalent "do the whole job and commit" combo — `completeness-audit`, `completeness-apply`, `detail`, and `sweep` — the everyday power invocation is undocumented, so readers don't learn it from the Quick reference.

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
