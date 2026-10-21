> **Auto-archived**: this plan was swept on 2026-06-19 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Document the `plan-tool merge` command in `PLAN_FORMAT.md` and `RUNBOOK.md` alongside `split`

## Summary

Document the new `plan-tool merge` operator verb on the two reference surfaces this plan owns: `RUNBOOK.md` and `PLAN_FORMAT.md`. The load-bearing decision is **mirror where `split` actually lives, surface by surface, after verifying each at HEAD** — `split` is documented as a command in exactly one place (`RUNBOOK.md`'s `## Quick reference` → **Authoring** table), and `PLAN_FORMAT.md` names both verbs only in passing — the `**features**` bullet already states a `split`/`merge` step renumber "cannot dangle" a feature tag. So this step adds one merge row beside the split row in `RUNBOOK.md`, and adds a short structural-edit note (covering both `split` and `merge`) to `PLAN_FORMAT.md`'s `steps[].id` field-semantics entry — complementary to that existing `features` mention, where the contiguous-id-renumbering invariant these commands maintain actually belongs. The second load-bearing decision is **disambiguation**: `plan-tool merge` (the subcommand that folds steps) must read as distinct from the bare word "merge" already in `RUNBOOK.md` (git "before merge") on every line it touches. On green, `grep "plan-tool merge"` returns hits in both files, the merge row sits immediately after the split row, no new H2 (and thus no TOC churn) is introduced, and no surface calls `merge` a `--mode` or conflates it with git merge.

## Table of Contents

- [Why](#why) — `merge` ships as a CLI verb in step 3 but has no reference documentation
- [Files (creates vs edits)](#files-creates-vs-edits) — the two reference docs this step edits
- [Implementation](#implementation) — the exact merge row, the PLAN_FORMAT note, and the deliberate non-edits
- [Tests](#tests) — pointer to the verification subsection (non-code step)
- [Verification (non-code step)](#verification-non-code-step) — grep/anchor/disambiguation checks
- [Acceptance criteria](#acceptance-criteria) — checkable artifact states on green
- [References](#references) — the doc-format specs and argparse reference relevant here
- [Deferred](#deferred) — README/SKILL surfaces and the families-table sync left to other steps

## Why

Steps 1–3 build the merge engine end-to-end — `plan_tool/create.py:_apply_step_merge` (pure transform), `plan_tool/detail.py:merge_steps` (orchestrator), and `plan_tool/cli/authoring.py:cmd_merge` + the `merge` subparser (the operator entry point). Step 3 also regenerates the **generated** reference (`docs/cli/merge.md` + the `docs/cli/README.md` row) via `python -m plan_tool.cli_reference --write`. But the **hand-authored** reference docs — `RUNBOOK.md` (operational walkthroughs) and `PLAN_FORMAT.md` (the format spec) — still describe a tool with only `split`. A reader scanning the everyday-commands table in `RUNBOOK.md` sees `plan-tool split` and no inverse, and the `steps[].id` semantics in `PLAN_FORMAT.md` document that ids are "not required to be sequential (gaps are allowed) but conventionally 1, 2, 3…" without naming the structural-edit commands that renumber survivors to a contiguous `1..N`. This step closes that gap so the human-facing references match the shipped CLI.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `RUNBOOK.md` — add one `plan-tool merge` row to the **Authoring** table under `## Quick reference`, immediately after the existing `plan-tool split <name> --step N --into "…" --into "…"` row. No other RUNBOOK edits (see [non-edits](#implementation)).
  - `PLAN_FORMAT.md` — extend the `**steps[].id**` bullet under `### Field semantics` with a short note that the structural-edit commands `plan-tool split` and `plan-tool merge` renumber surviving steps to a contiguous `1..N` and rewire `depends_on`. No frontmatter-schema-table edits (the schema is unchanged).

## Implementation

### Confirm the step-3 seam at HEAD before writing flag prose

- **`cmd_merge` and the `merge` subparser do not exist at HEAD** — steps 1–3 are unimplemented when this step is detailed. Pin every cited flag to step 3's detail (`docs/implementation-plans/plan-details/merge-steps-executor/03-cmd-merge-cli-command-merge-subparser.md`), not to disk.
- **Before writing, `grep "merge"` against `plan_tool/cli/authoring.py:register` at HEAD.** If step 3 shipped a different flag spelling than this prose assumes, adapt the documented invocation to the **real** shipped surface — do not transcribe flag names that exist only here. Attribute the verb to "step 3" in your own reasoning, never cite it as already-present in a way that survives into the doc.
- **The merge flag surface mirrors `split`** (`plan_tool/cli/authoring.py` `p_split` block under `register`): repeatable `--steps ID` (pass ≥2) in place of split's `--step`/`--into`, optional `--title`, `--iterate` (`BooleanOptionalAction`, **default ON**, mirroring split), `--no-detail`, `--no-completeness`, `--dry-run`, and the shared `--yes` parent. The quick-reference row need only show the minimal `--steps ID --steps ID` form (split's row shows only `--step`/`--into`); deeper flags live in `plan-tool merge --help` and the generated `docs/cli/merge.md` (step 3, out of scope here).

### `RUNBOOK.md` — the merge row in the Authoring quick-reference table

- **Anchor:** the **Authoring** table under `## Quick reference` — the five-row table whose last row is the `plan-tool split <name> --step N --into "…" --into "…"` entry.
- **Add one row directly below the split row**, matching the table's two-column `| Run | …to |` shape:

  ```markdown
  | `plan-tool merge <name> --steps ID --steps ID` | Fold a contiguous, dependency-connected set of steps into one (the structural inverse of `split`); re-author the combined detail file, renumber survivors to `1..N`, then re-audit |
  ```
- **Disambiguation is load-bearing.** The bare word "merge" already appears in `RUNBOOK.md` meaning git merge — at `## Quick reference`'s **Code audit** row (`verify-all --rollup` … "before merge") and in `## Command families and ordering` ("judges the `done` steps *after* … before merge"). The new row must read unambiguously as the **`plan-tool merge` subcommand that folds plan steps**. Keep the full `plan-tool merge` verb in the `Run` cell and the "fold … steps … inverse of `split`" gloss in the `…to` cell so no reader mistakes it for the git operation. Do **not** edit the existing "before merge" lines — they are a different, correct sense of the word (deliberate non-edit).
- **No `--mode` framing.** `merge` is a standalone subcommand, not a mode/flag of another command. Never write `--mode merge` or imply `merge` is an alias of `split`; the gloss states it is the *inverse* of `split`.

### `PLAN_FORMAT.md` — structural-edit note on `steps[].id`

- **Anchor:** the `**steps[].id**` bullet under `### Field semantics` — currently "integer unique within the plan. Not required to be sequential (gaps are allowed) but conventionally 1, 2, 3…".
- **Append a short note** to that bullet (not a new section, not a schema-table change):

  ```markdown
  The structural-edit commands `plan-tool split` and `plan-tool merge` keep ids contiguous: `split` replaces one step with its named sub-steps and `merge` folds a contiguous, dependency-connected set into one, each renumbering the surviving steps to a contiguous `1..N` and rewiring every `depends_on` edge to the new ids. (`plan-tool merge` is the plan-step fold, unrelated to a git merge.)
  ```
- **Why here, not a command section:** `PLAN_FORMAT.md` documents no commands as commands. It is **not** silent on the structural-edit verbs, though — the `**features**` field bullet already states that "a `split`/`merge` step renumber **cannot dangle it**" (the tag rides with the step), so both verbs already appear by name in this file. This `steps[].id` note is **complementary** to that mention: the `features` bullet asserts that a renumber cannot dangle a feature tag, while the `steps[].id` bullet is the one place the spec states *what* the renumber does (renumber survivors to a contiguous `1..N`, rewire every `depends_on`). The existing bullet documents that ids are gaps-allowed and only conventionally `1, 2, 3…`; frame the note as describing the renumber these commands perform — not as restating a pre-existing contiguity invariant and not as a first mention of either verb — so the gaps-allowed baseline and the split/merge renumber-to-contiguous behavior read as consistent, and the note stays about that renumber behavior (contiguous survivor ids + valid `depends_on`), not a CLI tutorial. The parenthetical re-states the git-merge disambiguation for this surface independently.
- **No schema-field addition.** `merge` adds **no** new frontmatter field — the merged step takes the dominant `change_type` (see the plan's architecture note), so there is no `type_impure` or other field to document. The frontmatter schema table, `### Defaults`, and `### Validation rules` stay untouched.

### Foundational logic and its other surfaces (deliberate non-edits / deferrals)

The core "fact" this step documents is **the `plan-tool merge` verb exists as the inverse of `split`.** The same fact lives on, or is omitted from, several other surfaces — surface each here so the scope is explicit:

- **`RUNBOOK.md` `## Command families and ordering` → Authoring row** (the `create`, `detail` row): this row already **omits `split`**. Leave it unchanged — adding `merge` here while `split` is absent creates exactly the asymmetry the docs should avoid, and the row's preface ("keep this table in sync with [the cli package docstring]") ties it to a code-side catalog updated in the subcommand's own step, not this docs step. **Deliberate non-edit.**
- **`RUNBOOK.md` `## Table of contents`** lists **H2 workflow sections only**. This step adds no H2 (only a table row and an inline note), so **no TOC line** — adding one would be a dangling anchor / churn. **Deliberate non-edit.**
- **`README.md`, `integrations/claude/SKILL.md`, `integrations/codex/SKILL.md`** all document `split` (the two SKILLs carry it in their decision-tree + "Subcommands at a glance" rows; README mentions only the unrelated *multi-plan* split). These are **outside this step's `files:`** — routed to [Deferred](#deferred), not edited here.
- **`docs/cli/merge.md` + `docs/cli/README.md`** are **generated** by `python -m plan_tool.cli_reference --write` and land in **step 3**. Never hand-author them here.

## Tests

This is a non-code step — no unit tests. See [Verification (non-code step)](#verification-non-code-step) for the artifact checks that stand in for tests. No test-ordering directive applies; no production code changes.

## Verification (non-code step)

Greppable, falsifiable checks — each doubles as an acceptance criterion:

- `grep -n "plan-tool merge" RUNBOOK.md` — returns the new Authoring-table row (≥1 hit).
- `grep -n "plan-tool merge" PLAN_FORMAT.md` — returns the `steps[].id` structural-edit note (≥1 hit).
- **Merge row adjacency** — in `RUNBOOK.md`, the `plan-tool merge` row appears as the line **immediately after** the `plan-tool split <name> --step N --into …` row inside the **Authoring** quick-reference table (same `| Run | …to |` table, no blank line between).
- **Markdown table integrity** — the new row has exactly two `|`-delimited cells; the Authoring table still renders (no broken pipe counts).
- **No mode/alias mislabeling** — `grep -n "mode merge" RUNBOOK.md PLAN_FORMAT.md` returns **zero** hits; no line describes `merge` as a `--mode` or as an alias of `split`.
- **Git-merge disambiguation intact** — the pre-existing "before merge" lines in `RUNBOOK.md` (`## Quick reference` Code-audit row and `## Command families and ordering`) are unchanged, and both new mentions explicitly tie `merge` to folding plan steps.
- **TOC unchanged** — `RUNBOOK.md`'s `## Table of contents` is byte-identical (no new H2 was added).
- **HEAD-accuracy of the documented invocation** — the `--steps`/`--title` spelling in the merge row matches the shipped `merge` subparser in `plan_tool/cli/authoring.py:register` after step 3 lands (re-grep before finalizing; adapt the row if step 3's shape diverged).
- **Schema untouched** — `PLAN_FORMAT.md`'s frontmatter schema block, `### Defaults`, and `### Validation rules` are unchanged.

## Acceptance criteria

- `RUNBOOK.md` has a `plan-tool merge` Authoring-table row immediately after the `plan-tool split` row, glossed as the structural inverse of `split` (fold steps → one, renumber `1..N`, re-author detail, re-audit).
- `PLAN_FORMAT.md`'s `**steps[].id**` bullet names both `plan-tool split` and `plan-tool merge` as the structural-edit commands that keep ids contiguous and rewire `depends_on`.
- Both files distinguish `plan-tool merge` from a git merge on every line that mentions it.
- No new H2 heading and no `## Table of contents` change in `RUNBOOK.md`.
- No edits to `RUNBOOK.md`'s `## Command families and ordering` Authoring row, to the generated `docs/cli/*`, or to README/SKILL surfaces.
- `grep "plan-tool merge"` succeeds in both `RUNBOOK.md` and `PLAN_FORMAT.md`; `grep "mode merge"` returns zero hits in both.

## References

- [`PLAN_FORMAT.md`](PLAN_FORMAT.md) — the spec being edited; the `### Field semantics` → `steps[].id` bullet is the anchor for the structural-edit note.
- [`RUNBOOK.md`](RUNBOOK.md) — the operational doc being edited; `## Quick reference` → **Authoring** table is the anchor for the merge row.
- [argparse — Parser for command-line options, arguments and subcommands — Python documentation](https://docs.python.org/3/library/argparse.html) — confirm the shipped `merge` subparser's `action='append'` repeatable `--steps` and `BooleanOptionalAction --iterate` so the documented invocation matches HEAD.

## Deferred

- **README.md / both `integrations/*/SKILL.md` merge documentation** — these document `split` and need a parallel `merge` entry (SKILL decision-tree row + "Subcommands at a glance" row, in lockstep across both SKILLs), but they are outside this step's `files:`. Route to a follow-up docs step or reconcile.
- **`RUNBOOK.md` `## Command families and ordering` Authoring-row sync** — this row already omits `split`; bringing it (and the cli package-docstring catalog it mirrors) up to date for both `split` and `merge` is a separate decision tied to the code-side catalog/golden, not this step.
- **`docs/cli/merge.md` + `docs/cli/README.md` row** — generated artifacts emitted by `python -m plan_tool.cli_reference --write` in step 3; never hand-authored here.
