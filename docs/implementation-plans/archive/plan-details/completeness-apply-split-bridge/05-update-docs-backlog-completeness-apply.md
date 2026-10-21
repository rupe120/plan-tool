> **Auto-archived**: this plan was swept on 2026-07-08 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Update docs and backlog for the completeness-apply split bridge

## Summary

This is the docs-and-backlog wrap-up for the completeness-apply split bridge that steps 1–4 built. It teaches four artifacts about the new wiring: `CLAUDE.md`'s escalate-to-split bridge paragraph gains `completeness-apply` as a caller; `RUNBOOK.md` gets the operator walkthrough of the `--apply-structural` opt-in, its recommend-only default, and the halt-on-applied behavior; `docs/cli/completeness-apply.md` is regenerated so the new `--apply-structural` flag row (added by step 4) shows up; and `BACKLOG.md` #70 loses its "Completeness-apply split bridge" bullet from *Remaining* with a ship note. The key rule: `docs/cli/completeness-apply.md` is a generated file — regenerate it with `python -m plan_tool.cli_reference --write`, never hand-edit. On green, all four docs describe the shipped bridge, the CLI-reference drift test stays green, and no #70 reference still frames the bridge as pending.

## Table of Contents

- [Why](#why) — the doc/backlog debt this step closes now that steps 1–4 shipped
- [Input](#input) — the shipped behavior this step describes and the generated-doc contract it must respect
- [Files (creates vs edits)](#files-creates-vs-edits) — the four artifacts this step touches
- [Implementation](#implementation) — what each doc must say and how to regenerate the CLI reference
- [Tests](#tests) — verification for a non-code step
- [Acceptance criteria](#acceptance-criteria) — checkable states on green
- [References](#references) — the docs worth reading for this step
- [Deferred](#deferred) — what this step deliberately leaves out

## Why

Steps 1–4 ship the completeness-apply split bridge: the completeness audit produces and persists a `medium` `granularity-split` MIXED-STEP finding, and `completeness-apply --apply-structural` routes it through the shipped `escalate_to_split` bridge under an opt-in plus an interactive confirm. But the docs still describe the old world. `CLAUDE.md`'s "Escalate-to-split bridge" paragraph says "Two callers wire it" and names only `detail` and the review/reconcile apply walk — an operator reading it would not know the completeness-apply lane now reaches the bridge. `RUNBOOK.md`'s escalate-to-split section and its "Address conceptual gaps (`completeness-apply`)" section say nothing about the new structural opt-in. `docs/cli/completeness-apply.md` has no `--apply-structural` row because it is generated and hasn't been regenerated since step 4 added the flag. And `BACKLOG.md` #70 still lists "Completeness-apply split bridge" under *Remaining*, so future triage would treat shipped work as open. This step makes the docs match the code and retires the backlog item.

## Input

- **Describes shipped behavior from steps 1–4, does not re-specify it.** Step 4 produces the `--apply-structural` flag on the `completeness-apply` subparser and the serial-walk gate `allow_split = bool(args.apply_structural) and not bool(getattr(args, "yes", False))`. This step documents the observable operator path (opt-in + confirm → applied split on a safe plan; every other path recommend-only) and cites the shipped anchors as orientation — it must not restate the flag-threading or gate mechanics that step 4 owns.
- **`docs/cli/completeness-apply.md` is a generated artifact.** It is written by `plan_tool/cli_reference.py` from the argparse parser and guarded by `tests/cli/test_cli_reference.py` (drift, index-link, and orphan-file checks). The `--apply-structural` flag row and any help-text change reach the page only by regenerating, never by hand-editing. The generator also rewrites `docs/cli/README.md`.
- **`BACKLOG.md` #70 is a multi-arm entry.** Only the "Completeness-apply split bridge" bullet under *Remaining* belongs to this plan. The other #70 arms (multi-step/region carve, per-remedy walk flags + dispatcher consolidation, code-reveals-a-split reconcile producer) stay open — leave them untouched.

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**

- `CLAUDE.md` — in the **"Escalate-to-split bridge (`launcher.py:escalate_to_split`)"** paragraph, update the callers list so the completeness-apply serial walk is named as a caller that reaches the bridge through `cli/review_actions.py:_dispatch_structural_escalation` for a persisted `medium` `granularity-split` finding.
- `RUNBOOK.md` — extend the **"### The escalate-to-split bridge (auto split-or-recommend)"** section to name completeness-apply as a wiring/surface, and extend **"### Address conceptual gaps (`completeness-apply`)"** to cover `--apply-structural`, the recommend-only default, and halt-on-applied.
- `docs/cli/completeness-apply.md` — **regenerate** (output of `python -m plan_tool.cli_reference --write`); do not hand-edit. Regeneration also refreshes `docs/cli/README.md` if the help text changed.
- `BACKLOG.md` — remove the "Completeness-apply split bridge" bullet from #70's *Remaining* list and record a ship note (2026-07-08).

Note: `docs/cli/README.md` may change as a side effect of regeneration. It is not in the declared `files:` list. If regeneration touches only the `completeness-apply.md` page (no help-text change), `README.md` stays unchanged and no addition is needed; if the generator does rewrite `README.md`, that is a required generated output — commit it and note the addition rather than reverting it.

## Implementation

**Goal:** four artifacts that describe the shipped bridge accurately, with the generated CLI page regenerated rather than edited by hand.

- **`CLAUDE.md` — add completeness-apply to the bridge callers list.** The "Escalate-to-split bridge" paragraph currently reads "Two callers wire it: the `detail` Phase-B purity check plus convergence loop … and the interactive review/reconcile apply walk (`cli/review_actions.py:_dispatch_structural_escalation` …)." Update it so the completeness-apply serial walk is named as a caller too: the persisted `medium` `granularity-split` MIXED-STEP finding dispatches through `_dispatch_structural_escalation` → `escalate_to_split`, gated by `--apply-structural`. Keep the `create`-side "does not yet route through it (create-side trigger deferred)" clause — that is still true. One way: change "Two callers" to "Three callers" (or drop the count) and add the completeness-apply clause beside the review/reconcile-walk clause, since both share `_dispatch_structural_escalation`. Keep the edit tight to this paragraph; the "Structural remedy vocabulary" re-split bullet already names `granularity-split → escalate_to_split` at the vocabulary altitude and does not need a completeness-apply mention.

- **`RUNBOOK.md` — the escalate-to-split section.** The "### The escalate-to-split bridge" section lists "The two `detail` triggers" and "Where you see it" (three surfaces). Add the completeness-apply lane so a reader knows it is now a surface: the saved `medium` `granularity-split` finding, walked by `completeness-apply --apply-structural`, routes through `plan_tool/cli/review_actions.py:_dispatch_structural_escalation` to the same bridge — recommend-only unless the walk opts in. Match the existing bullet voice.

- **`RUNBOOK.md` — the completeness-apply section.** In "### Address conceptual gaps (`completeness-apply`)", add the structural opt-in. Cover, grounded in the shipped behavior:
  - **`--apply-structural` is the opt-in** for dispatching a saved `medium` `granularity-split` MIXED-STEP finding ("step mixes refactor + feature") to the split bridge; without it the finding recommends only (prints the runnable `plan-tool split <plan> --step N --into … --into …`).
  - **Recommend-only in every unsafe/unattended path** — without `--apply-structural`, under `-y`, in the `--jobs > 1` parallel lane, on an unsafe plan (a non-`PENDING` step at or after the target), or a declined/non-TTY confirm. Only the safe + opted-in + interactively-confirmed path applies the 1→2 split.
  - **Halt-on-applied.** An applied split renumbers every step from the target onward, so later saved findings now name the wrong step; the walk halts and instructs a re-audit rather than applying them against stale ids. This mirrors the applied-merge halt already documented in the walk-dispatch list ("Structural-directive findings").
  - **No exit-code change and no Claude on mutation-decline** — the finding never flips `--fail-on-findings`; the recommend-only path spends no Claude on mutation.

- **`docs/cli/completeness-apply.md` — regenerate.** Run `python -m plan_tool.cli_reference --write` after step 4's flag lands. The generator reads the argparse parser and writes the page, adding the `--apply-structural` option row (default off; recommend-only unless the flag is set and the run is interactive). Do not edit the page by hand — a hand-edit drifts from the generator and fails `tests/cli/test_cli_reference.py`. Confirm the new row is present and the index link in `docs/cli/README.md` is intact.

- **`BACKLOG.md` — retire the arm.** Remove the "Completeness-apply split bridge" bullet from #70's *Remaining (convenience, not blocking)* list. Record that this arm shipped on 2026-07-08 (e.g. a short note in #70's Shipped line or an updated *Remaining* preamble), consistent with how the adjacent "Auto-bridges — **SHIPPED (scope-out + re-ground + merge)**" note is written. Leave the other three #70 arms and the #70 Origin/Effort/Approach lines intact. Before editing, grep `BACKLOG.md` for the feature phrase and `#70` so no sibling reference still frames the completeness-apply bridge as pending.

**Constraint — foundational rule this step encodes:** the generated CLI page must come from the generator, and only the completeness-apply arm of #70 is retired. Everything else is prose describing already-shipped behavior; do not introduce new behavior or new schema obligations in a docs step.

## Tests

### Verification (non-code step)

This step changes no production code. Verify the artifacts:

- **CLI reference drift guard** — `uv run pytest tests/cli/test_cli_reference.py -q` passes after regenerating, proving `docs/cli/completeness-apply.md` matches the parser and `docs/cli/README.md` has the index link with no orphan files.
- **Generated-page content** — `docs/cli/completeness-apply.md` shows a `--apply-structural` option row; the page was produced by `python -m plan_tool.cli_reference --write`, not hand-edited (re-running the generator yields no diff).
- **CLAUDE.md accuracy** — the escalate-to-split bridge paragraph names the completeness-apply lane as a caller and still notes the create-side deferral.
- **RUNBOOK.md accuracy** — the escalate-to-split section and the "Address conceptual gaps" section describe `--apply-structural`, the recommend-only default, and halt-on-applied; the documented flag/command names match the shipped CLI surface.
- **BACKLOG.md reconciliation** — `rg "Completeness-apply split bridge"` in `BACKLOG.md` returns no live *Remaining* bullet; a ship note dated 2026-07-08 is present; the other three #70 arms remain.
- **Full suite** — `uv run pytest tests/ -q` stays green (no production code changed; only the drift guard matters here).

## Acceptance criteria

- `docs/cli/completeness-apply.md` contains a `--apply-structural` option row and re-running `python -m plan_tool.cli_reference --write` produces no diff.
- `tests/cli/test_cli_reference.py` passes.
- `CLAUDE.md`'s "Escalate-to-split bridge" paragraph names `completeness-apply` (via `_dispatch_structural_escalation`) as a bridge caller and keeps the create-side-deferred note.
- `RUNBOOK.md`'s "### The escalate-to-split bridge" section names the completeness-apply lane, and "### Address conceptual gaps (`completeness-apply`)" documents `--apply-structural`, the recommend-only default (no flag / `-y` / `--jobs > 1` / unsafe / declined), and the halt-on-applied re-audit instruction.
- `rg "Completeness-apply split bridge" BACKLOG.md` returns no active *Remaining* bullet; #70 carries a 2026-07-08 ship note for this arm; the multi-step carve, per-remedy walk flags, and code-reveals-a-split arms are untouched.
- `uv run pytest tests/ -q` is green.

## References

- `plan_tool/cli_reference.py` — the generator that writes `docs/cli/completeness-apply.md` (and `docs/cli/README.md`) from the argparse parser; regenerate with `python -m plan_tool.cli_reference --write` rather than hand-editing the page.
- `tests/cli/test_cli_reference.py` — the drift/index-link/orphan guard that must stay green after regenerating, proving the page matches the parser.
- `CLAUDE.md` — the "Escalate-to-split bridge (`launcher.py:escalate_to_split`)" paragraph whose callers list this step extends with the completeness-apply lane.
- `RUNBOOK.md` — the "### The escalate-to-split bridge (auto split-or-recommend)" and "### Address conceptual gaps (`completeness-apply`)" sections this step extends with the `--apply-structural` opt-in, recommend-only default, and halt-on-applied.

## Deferred

- **Regenerating any CLI page other than `completeness-apply.md`** — no other subcommand changed; regeneration should touch only `completeness-apply.md` (and `docs/cli/README.md` if its help text changed).
- **Retiring the other three #70 arms** — multi-step/region carve, per-remedy `--merge`/`--reground` walk flags + dispatcher consolidation, and the code-reveals-a-split reconcile producer stay open under #70; this step retires only the completeness-apply split bridge bullet.
- **`create`-side bridge docs** — the create convergence loop still does not route through `escalate_to_split`; the CLAUDE.md/RUNBOOK notes keep the create-side-deferred wording rather than describing wiring that does not exist.
- **New operator recipes beyond the four named artifacts** — `README.md`, `USE_CASES.md`, and `CAPABILITIES.md` are out of this step's declared `files:` list; if a gap surfaces there, route it to reconcile or a follow-up rather than expanding this step.
