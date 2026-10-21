> **Auto-archived**: this plan was swept on 2026-07-04 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 7 — Document `plan-tool split-criteria` across the guide docs

## Summary

Documents the read-only `plan-tool split-criteria [<plan>]` command (wired in step 6) for operators, so the surface steps 1–6 built is discoverable. Edits three human-guide docs: `README.md`, `RUNBOOK.md`, and `USE_CASES.md`. The key decision: describe both modes — no-argument prints the plan-independent legend, a plan argument prints the per-plan breakdown — and mirror `plan-tool convergence`'s read-only contract wording (no Claude, no mutation, always exits 0) rather than re-explaining the detectors. Follows `plan-tool convergence`'s precedent and defers the `integrations/*/SKILL.md` agent routers (see Deferred). On green, each doc names the command in its natural spot, the new table-of-contents anchors resolve, and no doc contradicts `plan-tool split-criteria --help`.

## Table of Contents

- [Summary](#summary) — what the step documents and the observable result on green
- [Why](#why) — the discoverability gap left after steps 1–6 land the code
- [Files (creates vs edits)](#files-creates-vs-edits) — the three docs this step edits, with the specific edit per file
- [Implementation](#implementation) — where the command slots into each doc, the wording to mirror, and the sync/anchor constraints
- [Tests](#tests) — verification appropriate to a docs-only step
- [Acceptance criteria](#acceptance-criteria) — checkable doc facts on green
- [References](#references) — argparse optional-positional, to describe the two modes accurately
- [Deferred](#deferred) — surfaces and owners left out of this step

## Why

Steps 1–6 land the recorder, the criteria catalog + legend, the per-plan evaluator, and the thin CLI command `plan-tool split-criteria [<plan>]` — but the only operator-facing doc step 6 touches is the generated `docs/cli/split-criteria.md` reference and its `docs/cli/README.md` index row. A developer scanning the narrative guides (`README.md`, `RUNBOOK.md`, `USE_CASES.md`) won't find the command, so "why is this plan shaped this way?" has an answer no one can reach. This step closes that gap: it names the command where a reader already looks — beside the convergence/scope-out material about a plan's shape — so the diagnostic is discoverable the same way `plan-tool convergence` and `plan-tool scope-out` are. Like `plan-tool convergence`, the `integrations/*/SKILL.md` agent routers are left out (see Deferred).

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `README.md` — add a short subsection describing `plan-tool split-criteria` near the convergence/scope-out material (after `### Carve a spinning region out (`plan-tool scope-out`)`), plus one matching table-of-contents line nested under the `Iterating to convergence` group.
  - `RUNBOOK.md` — add a `plan-tool split-criteria` row to the `**Discovery & inspection**` quick-reference table, and a short walkthrough subsection near `### Diagnosing convergence with `plan-tool convergence`` with its table-of-contents entry.
  - `USE_CASES.md` — add one command line for `plan-tool split-criteria` in use case 7 (`### 7. Drive a plan to "actually correct," not just "generated"`), beside the existing `convergence` / `scope-out` commands.

## Implementation

**Document the command, don't re-explain the detectors.** The behavior is owned upstream: step 6 wired the CLI handler (`plan_tool/cli/split_criteria_cmd.py:cmd_split_criteria`), step 2 built the legend renderer (`render_split_criteria()`), and step 3 built the per-plan evaluator + breakdown renderer (`evaluate_split_criteria(...)`). This step only names the command and its two modes in prose. State the two modes once and stop:

- **No argument** → prints the plan-independent legend: every split criterion the tool applies across the three altitudes, plus the remedy vocabulary.
- **A plan argument** → prints the per-plan breakdown: which criteria fire for that plan, which steps, and a one-line reason each.

**Mirror `plan-tool convergence`'s read-only contract wording.** `plan-tool split-criteria` is a "tell me the state" diagnostic like `plan-tool convergence` and `plan-tool status`: no Claude, no mutation, no run-log entry, and it always exits 0. Reuse the phrasing already in `README.md` (`### Carve a spinning region out (`plan-tool scope-out`)` and the convergence narrative) and `RUNBOOK.md` (`### Diagnosing convergence with `plan-tool convergence``) so the read-only promise reads consistently. Do **not** describe the telemetry write to operators — step 3 owns that record and it is internal detail, not an operator concern.

**Per-file placement and shape:**

- **`README.md`** — the numbered command sections (`### 1. `create``  through `### 9. `sweep``, under `## CLI usage`) are the pipeline verbs; diagnostics about a plan's shape live in the `## Iterating to convergence (`--iterate`)` area instead. Add a short H3 (one way: `### See a plan's split criteria (`plan-tool split-criteria`)`) right after `### Carve a spinning region out (`plan-tool scope-out`)`. Add exactly one table-of-contents line for it, nested under the `Iterating to convergence` group — the existing scope-out sub-entry (`- [Carve a spinning region out (`plan-tool scope-out`)]...`) sits at that same nesting, so a sibling H3 line matches the table's depth. Don't add a numbered `### N.` command section — split-criteria is not a pipeline verb. This deliberately gives split-criteria more README prominence than `plan-tool convergence` itself (which rides as a bullet inside the scope-out subsection): split-criteria's two distinct modes warrant their own H3, and "mirror convergence" governs the read-only *contract wording*, not structural doc prominence.

- **`RUNBOOK.md`** — two edits:
  - Add a row to the `**Discovery & inspection**` quick-reference table (beside `plan-tool status <name>` and `plan-tool validate <name>`), since split-criteria is a read-only inspection command. One way: `| `plan-tool split-criteria [<name>]` | See the tool's split criteria (no arg) or why one plan is shaped as it is |`.
  - Add a short walkthrough subsection near `### Diagnosing convergence with `plan-tool convergence``, framed as the companion read: convergence answers "is this loop spinning?"; split-criteria answers "which criteria decided this plan's shape?". Add its table-of-contents entry at the same nesting the scope-out sub-entry uses under `Workflow: completeness checks`.
  - Optional, only if it reads naturally: mention it in the `Command families and ordering` discovery row. Treat this as confirm-and-skip if it would duplicate the quick-reference row.

- **`USE_CASES.md`** — use case 7 already shows `plan-tool convergence` and `plan-tool scope-out` in one fenced block. Add one line, e.g. `plan-tool split-criteria my-feature   # why is this plan shaped this way?`, with a trailing comment matching the existing inline-comment style. Keep the surrounding prose intact.

**Constraints and gotchas:**

- **Match `--help`, don't contradict it.** The `help=` string on the subparser (owned by step 6) is authoritative. If the shipped `plan-tool split-criteria --help` summary phrases the two modes differently than a draft here, follow the help string. Don't edit any Python — this is a docs step.

- **Respect each table-of-contents' existing depth.** README's table lists the scope-out H3, so add the split-criteria H3 line there. Check RUNBOOK's table nesting before adding an entry — add a line only at a level that table already indexes (mirror the scope-out sub-entry).

- **No dead or partial references.** Write full command names and repo-root-relative paths. Describe only the forward state; no "previously" / "now also" narration.

## Tests

### Verification (non-code step)

This step changes no production code, so verification is doc-accuracy and link checks, not unit tests:

- **Command matches the parser** — `plan-tool split-criteria --help` runs and its two-mode summary agrees with the prose added to each doc; no doc names a flag or mode the parser doesn't have.
- **README anchor resolves** — the new table-of-contents line's anchor slug matches the new H3 heading (GitHub-style slug), and clicking it lands on the section.
- **RUNBOOK anchor resolves** — the new walkthrough subsection has a matching table-of-contents entry whose anchor resolves; the quick-reference table row renders as a valid markdown table row.
- **USE_CASES block still valid** — the added line sits inside the existing fenced block and the block still renders.
- **No dead references** — grep the three edited docs for `split-criteria`; every mention names the real command, with no partial/basename paths and no stale wording.

## Acceptance criteria

- `README.md` has a subsection naming `plan-tool split-criteria`, describing the no-arg legend mode and the per-plan breakdown mode, and states it spends no Claude, mutates nothing, and always exits 0.
- `README.md`'s table of contents has one new line for that subsection whose anchor resolves to the heading.
- `RUNBOOK.md`'s `**Discovery & inspection**` quick-reference table has a `plan-tool split-criteria` row.
- `RUNBOOK.md` has a walkthrough subsection for the command near the convergence-diagnosis section, with a resolving table-of-contents entry.
- `USE_CASES.md` use case 7 includes a `plan-tool split-criteria` command line beside `convergence` / `scope-out`.
- `plan-tool split-criteria --help` succeeds and no edited doc contradicts its mode/flag summary.
- Grepping the three docs for `split-criteria` returns only accurate, full-name references (no stale or partial paths).

## References

- [argparse — Parser for command-line options, arguments and subcommands (Python docs)](https://docs.python.org/3/library/argparse.html) — confirms the optional-positional (`nargs='?'`) behavior behind `split-criteria [<plan>]`, so the prose describing "no argument → legend, plan argument → breakdown" matches the real parser.

## Deferred

- **`integrations/claude/SKILL.md` and `integrations/codex/SKILL.md` agent routers** — leave `split-criteria` out of the SKILL decision-tree, `## Subcommands at a glance`, and frontmatter `description:` enumeration entirely, matching how `plan-tool convergence` (a peer read-only diagnostic) appears in neither router. The three human guides carry discoverability; the router surfaces are a later, separate concern to keep both diagnostics on the same precedent.
- **`docs/cli/split-criteria.md` and `docs/cli/README.md` index row** — generated reference, owned by step 6 (`python -m plan_tool.cli_reference --write`); not re-touched here.
- **`CAPABILITIES.md` surface entry** — owned by step 6's wiring.
- **`DATA_CONTRACT.md` / telemetry docs** — the `plan-criteria-breakdown` record is documented by step 1; this operator step does not describe telemetry.
- **Cross-plan aggregation docs** — there is no cross-plan aggregation surface yet (deferred by the earlier steps), so nothing to document.
