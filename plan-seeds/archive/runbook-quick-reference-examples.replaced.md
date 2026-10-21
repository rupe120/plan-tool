> **Replaced**: this file has been superseded by `docs/implementation-plans/2-runbook-quick-reference-examples.md`.
> Preserved here for history; do not edit.

# Plan seed: add common-example rows to the RUNBOOK Quick reference

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing plan-seeds/runbook-quick-reference-examples.md
```

It is **not** itself a plan — `plan-tool create` consumes the prose below
and proposes a step decomposition; the author then runs `plan-tool detail`
per step.

---

## Goal

Make the [Quick reference](RUNBOOK.md#quick-reference) section teach the
*everyday power invocation* of a few more commands, the same way the
**Execution** family already shows `plan-tool run <name> --all --commit`
(run every step, committing each green step) rather than only the bare
`plan-tool run <name>`.

Today most families list only the minimal form of each command. For the
commands that have a canonical "do the whole job and commit" combo, add a
second row showing that combo, with a `…to` cell that explains the payoff —
exactly the shape of the existing `--all --commit` row.

## Scope — rows to add (documentation only)

This is a **docs-only** change to `RUNBOOK.md`. No code, no flags, no
behavior changes — every example must already be a valid, existing
invocation (verify each against `plan-tool <cmd> --help` before writing it).

Add these rows to the existing Quick-reference tables, keeping the
two-column `| Run | …to |` format and the family grouping:

1. **Plan audit** — under `completeness-audit`:
   `plan-tool completeness-audit <name> --iterate --commit`
   → *Converge the audit loop (gates → apply-finding → re-audit) and stage
   the applied edits.*

2. **Plan audit** — under `completeness-apply`:
   `plan-tool completeness-apply <name> --commit`
   → *Apply the conceptual gaps from the last audit and stage the result.*

3. **Authoring** — under `detail`:
   `plan-tool detail <name> --all --commit`
   → *Author every step's detail file in one pass, committing each.* This is
   the direct parallel to the existing `run --all --commit` row.

4. **State management** — under `sweep`:
   `plan-tool sweep --commit`
   → *Archive finished / adopt stray plans, then stage the manifest + moves.*

The exact wording of the `…to` cells is for the author to refine during
`detail`; the rows and the commands they document are fixed above.

## Constraints

- **Stay consistent with the section's own preamble.** The Quick-reference
  intro says niche flags (`--no-iterate`, `--reuse-audit`, `--dry-run`, …)
  live in the per-workflow sections, not here. The flags we are adding
  (`--commit`, `--iterate`) are *everyday* combos, not niche — that is the
  bar for inclusion. Do not turn the table into a flag dump.
- **One example row per command, max.** Mirror the `run` family, which keeps
  the bare form and adds exactly one power-combo row.
- **Verify each command/flag exists** (`--help`) so the runbook never
  documents a non-existent invocation.
- Keep `<name>` / `<slug>` placeholder usage consistent with the rest of the
  section and its "Placeholders used across this runbook" list.

## Non-goals

- No new CLI flags or behavior — documentation only.
- No restructuring of the Quick-reference families or the wider runbook.
- No new examples for commands whose minimal form is already the common
  form (`list`, `status`, `validate`, `jira`) or where `--iterate` is
  already the default (`create`); and no second row for `verify-all`, whose
  `--rollup` and `--mode <m>` rows are already concrete.

## Acceptance criteria

- The four rows above appear in their correct family tables, in the existing
  `| Run | …to |` format, each with a payoff-oriented `…to` cell.
- Every documented invocation is valid against the current CLI (`--help`).
- The Quick-reference preamble still reads true (niche flags still deferred
  to per-workflow sections; only everyday combos added).
- No other section of `RUNBOOK.md` is changed except as needed for internal
  consistency (e.g. anchor/TOC integrity if any heading shifts — none
  expected for table-row additions).
