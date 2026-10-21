> **Auto-archived**: this plan was swept on 2026-06-15 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Document `annotate`: RUNBOOK quick-ref row + per-flag bullets, README synopsis, CLAUDE.md pipeline note, BACKLOG #47 closed, and the forward-seed vs reconcile-plan live-mutation contrast

## Summary

- Document the `annotate` subcommand (delivered by steps 1–3) across the five operator-facing docs so it is discoverable and its intent is unambiguous: `RUNBOOK.md` (a quick-reference row + a per-flag workflow section), `README.md` (a one-line synopsis + a Decision-flow entry + a CLI-usage block + placeholder rows), `CLAUDE.md` (a one-line forward-seed bridge note under the pipeline line), `integrations/claude/SKILL.md` (a catalog-sync row in **Subcommands at a glance**), and `BACKLOG.md` (flip #47's `**Status:**` to shipped).
- **Load-bearing decision:** the single recurring claim every surface must carry is the **forward-seed vs. live-plan-mutation contrast** — `annotate` never mutates its source plan; it judges an old plan against current code and emits two artifacts (`<stem>.annotated.md`, `<stem>.seed.md`) to seed the *next* `create`, whereas `reconcile-plan` mutates a *live* plan in place to match drifted code. Live-plan upkeep stays `reconcile-plan`; `annotate` starts the next iteration.
- **No production code, no tests.** This is a pure-docs step: prose edits to five `.md` files, verified by grepping every cited flag against step 3's argparse source and confirming intra-doc anchors/links resolve.
- On green: `annotate` appears in the RUNBOOK quick reference and a dedicated workflow section, in the README synopsis/Decision-flow/CLI-usage blocks, as a pipeline note in CLAUDE.md, and BACKLOG #47 reads shipped — and every annotate flag named in the docs matches `plan_tool/cli/annotate_cmd.py:register`.

## Table of Contents

- [Why](#why) — annotate ships unreferenced; operators can't find it and may confuse it with reconcile-plan.
- [Files (creates vs edits)](#files-creates-vs-edits) — five existing docs, no new files.
- [Implementation](#implementation) — the exact edit per doc, with the contrast text single-sourced.
- [Tests](#tests) — none; see Verification.
- [Verification (non-code step)](#verification-non-code-step) — grep flags against the argparse source, resolve links/anchors, negative no-contradiction grep.
- [Acceptance criteria](#acceptance-criteria) — checkable doc states a reviewer can confirm.
- [References](#references) — the step-relevant subset of the plan's links.
- [Deferred](#deferred) — PLAN_FORMAT.md edits, BACKLOG entry removal, `--iterate` doc churn.

## Why

`annotate` lands fully wired by step 3 (subparser, dispatch, `--help` catalog group) but is named in **zero** operator docs — `grep -n "annotate" RUNBOOK.md README.md CLAUDE.md` returns only unrelated hits (the adjective "annotated" in RUNBOOK's saved-review examples at lines 673, 689, 711). An operator scanning `RUNBOOK.md`'s quick reference or `README.md`'s Decision flow cannot find it, and worse, its closest neighbor — `reconcile-plan` — is documented as the "plan-vs-code" command, so a reader reasonably concludes `annotate` is a redundant alias. The risk this step closes is **conceptual collision**: both commands compare a plan against code, but `reconcile-plan` mutates the live plan (code-canonical upkeep) while `annotate` is read-only on its source and emits a forward seed for the next `create`. That distinction must be stated wherever either command appears, not just appended once.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `RUNBOOK.md` — (1) add an **Annotate** quick-reference block after the **Authoring** block under `## Quick reference`; (2) add an `annotate` row/note to the `## Command families and ordering` discussion; (3) add a new `## Workflow: annotate an existing plan to seed the next one` section with one bullet per flag and the reconcile contrast; (4) add its ToC line; (5) add an `annotate` note to `## Mutating vs. read-only modes` (read-only except `--archive`).
  - `README.md` — (1) a one-line synopsis under `## Core subcommand workflow` (a forward-seed bridge note, not a new numbered pipeline step); (2) a Decision-flow row under `## Decision flow`; (3) an `# Annotate` block in the `## CLI usage` fenced listing; (4) a `<path>`-style placeholder note (annotate's positional is a filesystem path, like `create --from-existing`).
  - `CLAUDE.md` — one line under the `Pipeline:` line (`CLAUDE.md` line 9) describing `annotate` as the old-plan→next-plan forward-seed bridge.
  - `integrations/claude/SKILL.md` — add an `annotate` row to the **Subcommands at a glance** table (`SKILL.md:87`/`:123`) so the `cli/__init__.py`-docstring↔SKILL.md catalog sync covers the new verb.
  - `BACKLOG.md` — flip `#47`'s `**Status:** not started …` line to shipped with a pointer to `docs/implementation-plans/2-annotate-plan-implementation-status.md` (the annotate plan); leave the entry in place (see Deferred for the remove-on-ship alternative).

## Implementation

### Single-source the contrast text (write once, reuse verbatim)

- **Canonical sentence** to drop into RUNBOOK (`## Workflow: annotate …` + the families discussion), README (synopsis), and CLAUDE.md (pipeline note), lightly trimmed per surface:
  > `reconcile-plan` mutates a *live* plan in place to match code that drifted under it (code-canonical upkeep). `annotate` never touches its source — it judges an old plan against current code and emits a `<stem>.seed.md` to seed the *next* `create`. Live-plan progress upkeep → `reconcile-plan`; starting the next plan from "what we built vs. what we wrote" → `annotate`.
- **Source of truth for the wording:** BACKLOG #47's existing `**Note — distinct from `reconcile-plan`:**` bullet already states this. Reuse it; do not re-derive a divergent framing.

### `RUNBOOK.md`

- **Quick reference (`## Quick reference`).** Add a bolded block after the **Authoring** table (annotate produces the seed that feeds `create`):
  ```
  **Annotate (forward seed)**

  | Run | …to |
  | --- | --- |
  | `plan-tool annotate <path>` | Judge an old plan against current code; emit `<name>.annotated.md` + a `<name>.seed.md` for the next `create` |
  | `plan-tool annotate <path> --archive` | …and move the original (and its `plan-details/<slug>/` bundle for an `N-slug.md` plan) into `archive/` with a notice pointing at the report |
  ```
  - `<path>` (not `<name>`) is correct: the positional is a **filesystem path** (`p.add_argument("plan_file", type=Path, …)` in `plan_tool/cli/annotate_cmd.py:register`), not a registered plan slug — match the existing `create --from-existing <path>` row.
- **Command families (`## Command families and ordering`).** `annotate` has its own catalog group in `plan_tool/cli/__init__.py`'s module docstring (the source this table is told to stay in sync with). Add a short paragraph after the **Code audit (4)** table noting `annotate` sits **outside** the numbered 1–7 pipeline families as a forward-seed bridge (old plan + current code → next `create` seed), read-only on both plan and code except the opt-in `--archive`, and carry the contrast sentence so a reader who knows `reconcile-plan` immediately sees the difference. Do **not** invent a family number 8 — the numbered families mirror the pipeline; annotate is a bridge into it.
- **New workflow section.** Add `## Workflow: annotate an existing plan to seed the next one`, placed near the authoring/reconcile workflows (e.g. after `## Workflow: author detail files for developer hand-off`). Structure:
  - A one-line intent + the contrast sentence.
  - A fenced example: `plan-tool annotate docs/implementation-plans/2-old-plan.md` then `plan-tool create next-plan --from-existing 2-old-plan.seed.md --iterate`.
  - **Per-flag bullets** (one per `add_argument` in step 3's `register`):
    - `plan_file` (positional) — path to the existing plan/notes file judged against the current repo; a non-file errors (`CreateError` → rc 1), like `create --from-existing`.
    - `--output-dir <dir>` — directory for the derived `<stem>.annotated.md` / `<stem>.seed.md`; defaults beside the source file.
    - `--report <path>` — explicit path for the annotated report; overrides the derived name and `--output-dir`.
    - `--seed <path>` — explicit path for the create-seed; overrides the derived name and `--output-dir`.
    - `--archive` — the **only** mutation of the source: move the original (and, for an `N-slug.md` plan, its sibling `plan-details/<slug>/` bundle) into `archive/` with a one-line notice pointing at the report. Default: leave the source in place. **Caveat — manifest-registered plans:** archiving moves the file but does **not** touch `.plan-tool/plans.json`, so archiving a plan registered there leaves a dangling entry that `locator.py` resolution then fails on; annotate warns when it detects this but does not deregister (manifest mutation is out of scope), so update or remove the entry by hand. annotate's typical input is an unregistered old plan or rough-notes file, where this does not arise.
    - `--iterate` / `--no-iterate` — **reserved and inert**: annotate is single-pass today (one classification + two renderers, no convergence loop). Defaults OFF; passing it changes nothing. State this so an operator does not expect a convergence loop.
  - Note the two outputs explicitly: `<stem>.annotated.md` is the **verbatim original plus per-section IMPLEMENTED / PARTIAL / NOT-IMPLEMENTED status blocks** and a coverage summary; `<stem>.seed.md` is the carryover brief (NOT-IMPLEMENTED whole plus each PARTIAL's remaining work as scope; IMPLEMENTED plus each PARTIAL's already-implemented half as done-context — a PARTIAL is split, never re-planned whole) ready for `create --from-existing`. Re-running overwrites both (idempotent refresh, no prompt).
- **ToC.** Add `- [Workflow: annotate an existing plan to seed the next one](#workflow-annotate-an-existing-plan-to-seed-the-next-one)` to the `## Table of contents` list, positioned to match the section's placement.
- **Mutating vs. read-only modes (`## Mutating vs. read-only modes`).** Add a sentence: `annotate` is read-only on both the plan and the code — it never advances step status and never edits its source — **except** the opt-in `--archive`, which moves (not edits) the original. This mirrors the section's existing "never touch the plan file" framing.

### `README.md`

- **Synopsis (`## Core subcommand workflow`).** Add a short paragraph **after** the numbered list (do not insert a numbered pipeline step — annotate is not on the `create → detail → audit → run/jira` spine): one line introducing `annotate` as the old-plan→next-plan forward-seed bridge, carrying the contrast sentence. Keep the ASCII pipeline diagram unchanged.
- **Decision flow (`## Decision flow`).** Add a row to the entry-point table:
  ```
  | An *old* plan + current code — start the next iteration from what's built | `annotate <old-plan-path>` → `create <slug> --from-existing <name>.seed.md` |
  ```
  This is the only table row whose entry point is not a bare `create` variant; the surrounding prose says "Pick your `create` entry point", so frame annotate as the step that *produces* a `create --from-existing` seed, not a `create` mode itself.
- **CLI usage (`## CLI usage`).** Add a fenced block (a new comment group, e.g. after the Author group):
  ```bash
  # Annotate — judge an old plan against current code; emit a forward seed for the next create.
  plan-tool annotate <path> [--output-dir <dir>] [--report <path>] [--seed <path>] [--archive] [--iterate | --no-iterate]
  ```
  Match the existing blocks' inline-comment style. `--iterate` is listed for surface-completeness but is inert — no `--max-iterations`/`--iteration-budget` companions (step 3 deliberately omits the `iterate_parent` cluster), so do **not** copy those onto the annotate line.
- **Placeholders (`### Placeholders` table).** annotate's positional is a `<path>`, not `<name>`; if the `<path>` placeholder row exists, append `annotate` to its "Where it appears" column. Do **not** add `annotate` to the `<name>` row.

### `CLAUDE.md`

- **Pipeline note (line 9, the `Pipeline:` line).** Add one line directly below it, e.g.:
  > `annotate` is a forward-seed bridge, not a pipeline stage: it judges an existing plan against current code and emits a `create --from-existing` seed for the *next* iteration — never mutating its source (contrast `reconcile-plan`, which mutates a live plan in place).
- Keep it to one sentence per the project's concise-docs preference. Do not restate the full per-flag surface here — that lives in RUNBOOK.

### `integrations/claude/SKILL.md`

- **Subcommands at a glance (`SKILL.md:87`/`:123`).** Add an `annotate` row to the catalog table that mirrors `plan_tool/cli/__init__.py`'s module docstring, so the docstring↔SKILL.md sync contract covers the new verb. State the one-line forward-seed intent (judge an old plan against current code → emit `<stem>.annotated.md` + `<stem>.seed.md` for the next `create`) and keep it terse — the full per-flag surface stays in RUNBOOK. This closes the orphaned sync left by step 3's Deferred routing.

### `BACKLOG.md`

- **Flip #47's status.** The entry ends with `- **Status:** not started — seed authored at `plan-seeds/annotate-existing-plan-progress.md`.` Change it to a shipped state with a pointer to the implementation plan (the annotate plan under `docs/implementation-plans/`) and note delivery across steps 1–4. Leave the rest of the entry as a paper trail.
- **Convention note (call out, do not silently violate):** `BACKLOG.md`'s own `## Purpose` says *"Remove a feature's entry when it ships."* The step title says *mark #47 done*, which this step follows by flipping the Status line. Full removal of the #47 block is the stricter reading of that convention — route the removal decision to Deferred rather than deleting the entry here, so the choice is explicit and not an accidental contradiction.

## Tests

None — this step changes no production code and adds no importable surface. See [Verification](#verification-non-code-step).

### Verification (non-code step)

- **Flag spellings resolve to the argparse source.** For each flag named in the docs, grep it against step 3's definition:
  - `grep -n "plan_file\|--output-dir\|--report\|--seed\|--archive\|--iterate" plan_tool/cli/annotate_cmd.py` — every flag the docs cite must appear in `register`'s `add_argument` calls. (Step 4 is `depends_on: 3`; this verification presumes step 3's source exists at HEAD.)
- **Subcommand name resolves.** `grep -n "annotate" plan_tool/cli/parser.py` (in `CANONICAL_COMMAND_ORDER`) and `plan_tool/cli/app.py` (in `COMMAND_MODULES`) — confirm the documented verb is registered, not aspirational.
- **Artifact names match the renderers.** `grep -rn "annotated.md\|seed.md" plan_tool/cli/annotate_cmd.py` — the `<stem>.annotated.md` / `<stem>.seed.md` names the docs promise must match the path derivation in `cmd_annotate`.
- **Intra-doc anchors resolve.** The new RUNBOOK ToC entry's GitHub slug (`#workflow-annotate-an-existing-plan-to-seed-the-next-one`) must match the new `##` heading; confirm the README Decision-flow/CLI-usage edits don't break the existing `## Table of contents` anchors.
- **Cross-doc links resolve.** Any `README.md` / `RUNBOOK.md` mutual references added still point at live headings.
- **Negative — no contradiction survives.** `grep -n "annotate" RUNBOOK.md README.md` must not leave any sentence implying annotate **mutates** the source plan or is a `run --mode` / `reconcile` alias; and `grep -n "Status:.*not started" BACKLOG.md` near #47 must return nothing after the flip.
- **Inert-flag claim is accurate.** Confirm `cmd_annotate` does **not** branch on `args.iterate` (step 3 parses-but-ignores it) before the docs call `--iterate` inert: `grep -n "args.iterate\|\.iterate" plan_tool/cli/annotate_cmd.py` should show no behavioral branch.

## Acceptance criteria

- `grep -n "annotate" RUNBOOK.md` returns the new quick-reference block, the families note, the workflow section, the ToC line, and the mutating-modes note.
- `grep -n "annotate" README.md` returns the synopsis, the Decision-flow row, and the CLI-usage block.
- `grep -n "annotate" CLAUDE.md` returns the one-line forward-seed bridge note under the `Pipeline:` line.
- Every annotate flag named in the docs (`--output-dir`, `--report`, `--seed`, `--archive`, `--iterate`/`--no-iterate`, positional `plan_file`/`<path>`) is present in `plan_tool/cli/annotate_cmd.py:register`.
- The reconcile-plan contrast sentence appears in at least RUNBOOK (workflow section) and README (synopsis), and no doc sentence describes annotate as mutating its source plan.
- BACKLOG #47's `**Status:**` line reads shipped (no `not started`) with a pointer to the implementation plan.
- The new RUNBOOK ToC entry's anchor slug matches its `##` heading; no pre-existing anchor in the five docs is broken by the edits.

## References

- [argparse — Parser for command-line options, arguments and sub-commands — Python docs](https://docs.python.org/3/library/argparse.html) — Confirm the exact flag names/`dest`s of `annotate`'s subparser when documenting `--output-dir`/`--report`/`--seed`/`--archive`/`--iterate`, so the prose matches `register`'s `add_argument` calls.
- [GitHub Flavored Markdown Spec](https://github.github.com/gfm/) — The anchor-slug rules used to verify the new RUNBOOK ToC link resolves to its `##` heading.

## Deferred

- **PLAN_FORMAT.md mentions of `annotate`** — out of this step's `files:` scope; `RUNBOOK.md` cross-links to it but documenting annotate there is a separate, lower-priority pass. Track for a follow-up doc step. (SKILL.md is now in scope — its catalog-sync row is added under [Implementation](#implementation).)
- **Removing the #47 entry entirely** — `BACKLOG.md`'s "remove a feature's entry when it ships" convention argues for deletion, but the step title says *mark done*; the removal decision (vs. keeping it as a shipped-status paper trail) is left for a maintainer to make deliberately.
- **`--iterate` convergence documentation** — annotate is single-pass; once step 3's Deferred `--iterate` loop is actually wired, the docs' "inert/reserved" framing must be revised. No-op until that behavior lands.
- **A worked annotate→create round-trip walkthrough with sample output** — the new RUNBOOK workflow section gives the commands and per-flag bullets; a full annotated-report excerpt + seed excerpt is richer than this step needs and can follow once real fixtures exist.
