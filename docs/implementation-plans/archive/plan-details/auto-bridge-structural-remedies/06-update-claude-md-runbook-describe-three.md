> **Auto-archived**: this plan was swept on 2026-07-07 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Update CLAUDE.md and RUNBOOK to describe the two new bridges and drop stale recommend-only wording

## Summary

This step is docs-only. It edits `CLAUDE.md` and `RUNBOOK.md` so they describe the two actuation bridges this plan ships — `plan-tool convergence --apply-scope-out` (step 1) and the re-ground bridge `plan_tool/reground.py:reground_bridge` (step 3), the latter wired into the review/reconcile walk by step 5 — and drops the now-false "recommend-only / print-and-retype / hand-edit `status:`" claims those two bridges replace. The **merge** remedy stays hand-run: its bridge is deferred (plan Deferred), so any doc sentence saying a `granularity-merge` *merge* pair is resolved by hand-running `plan-tool merge` remains accurate and is **left intact**. The key decision: weave the updates into the existing sections that carry the stale wording rather than add new headings, so the RUNBOOK table of contents stays put. On green, a reader of either doc learns that a spinning scope-out region can be carved straight from `convergence` and a code-grounded re-ground finding can be actuated straight from the walk, while the still-manual merge path is described honestly.

## Table of Contents

- [Summary](#summary) — what the step changes and the result on green.
- [Table of Contents](#table-of-contents) — this list.
- [Why](#why) — the docs now contradict the two shipped bridges.
- [Files (creates vs edits)](#files-creates-vs-edits) — the two docs and the edits each needs.
- [Implementation](#implementation) — every stale claim to fix and the forward-state wording to replace it.
- [Tests](#tests) — points to the Verification block (non-code step).
- [Verification (non-code step)](#verification-non-code-step) — grep and link/accuracy checks.
- [Acceptance criteria](#acceptance-criteria) — checkable doc states.
- [References](#references) — the authoritative docs behind the bridge behavior.
- [Deferred](#deferred) — doc surfaces intentionally left alone.

## Why

Steps 1, 3, and 5 close two diagnosis-vs-actuation gaps: `convergence` can now run the scope-out carve it prints (`--apply-scope-out`), and the walk can actuate a code-grounded re-ground `granularity-merge` finding through `reground_bridge`. But `CLAUDE.md` and `RUNBOOK.md` still tell the reader the opposite for those two: the granularity-advisor paragraph and the reconcile re-ground callout describe re-ground as hand-edit / recommend-only, and the convergence sections describe the scope-out line as print-and-retype with "no mutation / always exits 0" read as absolutes even though `--apply-scope-out` mutates. This step makes the two docs match the two shipped bridges — and leaves the merge path described as still-manual, since the merge bridge is deferred and no merge actuator lands here.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `CLAUDE.md` — update three Architecture paragraphs: **Granularity advisor** (the re-ground clause — note re-ground now has its own `reground_bridge` actuator the walk dispatches; leave the merge "hand-running `plan-tool merge`" clause intact, as that bridge is deferred), **Convergence diagnostic** (name `--apply-scope-out`; re-qualify its "no mutation / always exits 0" claims as default-path guarantees), and **Structural remedy vocabulary** (the merge / re-ground bullet's re-ground half and the closing "the only path that narrows a plan" sentence).
  - `RUNBOOK.md` — update the sections that carry the stale wording for the two shipped bridges: the **completeness** `granularity-merge` re-ground half, the **per-subcommand reconcile** code-grounded re-ground callout, the **Diagnosing convergence** remedy fork and "four structural remedies as one model" block, the **Carve a spinning region** section, and the review **walk-through** apply-paths list (item that today says a re-ground `granularity-merge` finding is "recorded `applied` for you to address manually").

## Implementation

- **Frame the two shipped bridges consistently across both docs.** Name them the same way everywhere:
  - **scope-out actuation** — `plan-tool convergence <name> --apply-scope-out` runs the carve `convergence` already prints, calling the same deterministic `scope_out_step` (step 1). Reference step 1 for the flag; don't restate its gate.
  - **re-ground bridge** — `plan_tool/reground.py:reground_bridge` (step 3) marks the already-built steps `done` (re-baseline), never routing to `plan-tool merge`. It reaches the operator through the **review/reconcile walk** (step 5): applying a re-ground `granularity-merge` finding dispatches on its parsed `reground` directive kind (step 4) to `reground_bridge`.
  - **merge — still manual (deferred).** The merge bridge is deferred (plan Deferred), so a fragmented adjacent `granularity-merge` *merge* pair is still resolved by hand-running `plan-tool merge`. Do **not** claim a merge actuator; leave those sentences accurate.

- **CLAUDE.md — Granularity advisor paragraph.** Keep the sentence "`granularity-merge` is recommend-only: no automatic bridge wires a merge finding to an actuating command, so the operator resolves a flagged pair by hand-running `plan-tool merge` (the executor exists) or re-plans." — it stays true for the *merge* remedy (bridge deferred). Update only the **re-ground** clause: in the existing "second producer / re-ground finding" sentences, change "the remedy is re-ground / re-baseline … not a blind `merge`" to note the re-ground remedy now has its own actuator (`reground_bridge` marks done), which the review/reconcile walk dispatches behind the apply-or-recommend gate — so re-ground is no longer merge and no longer hand-only, while merge itself is still hand-run. Keep the "still out of `APPLY_ELIGIBLE_SOURCES`, still never flips an exit code" framing for both.

- **CLAUDE.md — Convergence diagnostic paragraph.** This is the docstring-softening rule applied to the doc: `--apply-scope-out` flips the command's headline invariant (read-only → can mutate; always-exits-0 stays absolute). Re-qualify only the "no mutation" claim as a **default (no-flag) path** guarantee, and name `--apply-scope-out` as the one flag that actuates the printed carve (via `scope_out_step`, so still no Claude). Keep "no run-log entry" as an absolute — `scope_out_step` writes no run-log entry even under `--apply-scope-out` (it journals the mutation inside `apply_narrow`, not the run log). Keep "always exits 0 for every verdict" as an absolute — every `ScopeOutResult` outcome still returns 0.

- **CLAUDE.md — Structural remedy vocabulary.** Two edits:
  - The **merge / re-ground** bullet: add that the walk actuates the **re-ground** finding through `reground_bridge` (re-ground / mark-done), keeping the "re-ground is not `merge`" distinction the plan's risk section requires; leave the **merge** half describing `plan-tool merge` as hand-run (bridge deferred).
  - The closing sentence "scope-out's `--apply` opt-in plus a TTY confirm is the only path that narrows a plan": widen it — narrowing is reachable from two commands now (`plan-tool scope-out … --apply` and `plan-tool convergence … --apply-scope-out`), both funneling through the same `scope_out_step` gate, so the gate — not the command — is what's "the only path." Don't claim a new gate; the actuator is unchanged.

- **RUNBOOK.md — completeness `granularity-merge` paragraph.** Keep the sentence that a fragmented adjacent *merge* pair is resolved by hand-running `plan-tool merge <name> --steps ID --steps ID` (bridge deferred). Update only the **re-ground** half: applying the code-grounded re-ground finding in the review/reconcile walk now runs `reground_bridge` (mark done), behind the apply-or-recommend gate — the advice is still advisory and never gates (rc stays 0). Leave the "only surface that shows merge advice" and `--fail-on-findings` sentences intact.

- **RUNBOOK.md — per-subcommand reconcile re-ground callout.** In the "Code-grounded re-ground finding" blockquote, keep the "remedy is re-ground / re-baseline — mark done or re-decompose — not a blind `plan-tool merge`" wording (still true), but add one clause: the walk can actuate it via `reground_bridge`, which marks the already-built steps `done` behind the apply-or-recommend gate — you no longer have to hand-edit `status:` fields. Keep the low-confidence-heuristic caveat.

- **RUNBOOK.md — Diagnosing convergence + four-remedies block.** In the `spinning` remedy fork, the scope-out / defer bullet says `convergence` "prints the **recommend-only / preview** form … carries **no `--apply` and no `-y`**" and "The always-exit-0, zero-Claude contract is unchanged." Update: `convergence` prints the preview by default, and `--apply-scope-out` actuates that exact carve (still always-exits-0; spends no Claude but does mutate the plan under the gate). In the "four structural remedies, as one model" block, update the **merge / re-ground** bullet to name `reground_bridge` as the walk actuator for re-ground (leave merge as hand-run) and the **scope-out** bullet to note `convergence --apply-scope-out` as a second entry point; then adjust the closing "mutation stays gated — scope-out narrows a plan only under its `--apply` opt-in plus a TTY confirm" to cover both entry points (both go through `scope_out_step`'s gate).

- **RUNBOOK.md — 2c scope-out / defer step and Carve a spinning region section.** Add a one-line pointer in 2c that `plan-tool convergence --apply-scope-out` runs the same carve straight from the diagnosis. In the "Carve a spinning region" section, keep the `plan-tool scope-out` examples and gate description; add that `convergence --apply-scope-out` is the shortcut that carves the step the diagnosis already resolved without re-typing `--step N`.

- **RUNBOOK.md — review walk-through apply paths.** The apply-paths list ends with "**Anything else** … the rec is recorded `applied` for you to address manually." Add that a re-ground `granularity-merge` finding is no longer in that bucket — the walk dispatches it to `reground_bridge` by its `reground` directive kind, rendering one status line and recording `applied` only when the bridge actually mutated (otherwise `skip`). Reference step 5 for the dispatch, not the mechanism. Leave the still-manual merge case as-is.

- **Constraint — keep the RUNBOOK table of contents stable.** Weave every change into the existing sections above. Do **not** add a new H2/H3, so the ToC (which indexes the completeness H3 subsections `Carve a spinning region…` and `See a plan's split criteria…`) needs no new line. If a rewrite renames a heading, update its ToC entry and any in-doc anchor link that points at it in the same edit.

- **Constraint — no new terms, cite real symbols.** Use the names the code ships at HEAD after steps 1/3/5: the flag `--apply-scope-out`, the function `plan_tool/reground.py:reground_bridge`, and the module `plan_tool/reground.py`. Do **not** cite `plan_tool/detail.py:merge_bridge` — that symbol is deferred and does not exist at HEAD. Don't invent a collective label for the bridges beyond "the re-ground / scope-out bridges."

## Tests

No unit tests — this step changes no production code. See [Verification (non-code step)](#verification-non-code-step).

### Verification (non-code step)

- **Stale wording is gone for the shipped bridges** — the re-ground callouts no longer say the operator must hand-edit `status:` or that re-ground is recommend-only-only; the convergence sections no longer read "no mutation" as an absolute. `grep -n "hand-edit" RUNBOOK.md` returns nothing for the re-ground callout.
- **The still-manual merge wording is intact and accurate** — `grep -n "hand-running \`plan-tool merge\`\|no automatic bridge" RUNBOOK.md CLAUDE.md` still returns the *merge* sentences (the merge bridge is deferred, so these stay); confirm each surviving line refers to merge, not re-ground.
- **Every command / flag / symbol named exists at HEAD** — `plan-tool convergence --help` lists `--apply-scope-out` (step 1); `plan_tool/reground.py` exists with `reground_bridge` (step 3); the walk dispatch is present in `plan_tool/cli/review_actions.py` (step 5). Grep each before citing it. **No doc line cites `plan_tool/detail.py:merge_bridge`** — that symbol is deferred and absent at HEAD; `grep -n "merge_bridge" CLAUDE.md RUNBOOK.md` returns nothing.
- **The convergence claims read as default-path guarantees** — the CLAUDE.md and RUNBOOK convergence text says "no mutation" only of the default (no-flag) path, and still says "always exits 0" without qualification.
- **RUNBOOK links resolve** — no heading was added or renamed, so the ToC anchors are unchanged; if any anchor text changed, its ToC line and every in-doc `#...` link to it were updated. Spot-check with a markdown link checker or by matching each `](#slug)` against a heading slug.
- **No drift-guard fires** — `CLAUDE.md` and `RUNBOOK.md` are hand-maintained (not generated under `docs/cli/`), so no `tests/cli/test_cli_reference.py`-style byte-match test covers them; confirm the run's suite stays green as a sanity check.

## Acceptance criteria

- `grep -n "merge_bridge" CLAUDE.md RUNBOOK.md` returns no matches (the merge bridge is deferred and not documented as shipped).
- The CLAUDE.md **Granularity advisor** paragraph names `reground_bridge` and states the walk actuates a re-ground `granularity-merge` finding, while leaving the merge "hand-running `plan-tool merge`" clause intact.
- The CLAUDE.md **Convergence diagnostic** paragraph names `--apply-scope-out` and qualifies its "no mutation" claim as the default-path guarantee while keeping "always exits 0" absolute.
- The CLAUDE.md **Structural remedy vocabulary** merge / re-ground bullet names `reground_bridge` for re-ground (and leaves merge as hand-run), and the closing narrowing sentence covers both `scope-out --apply` and `convergence --apply-scope-out`.
- The RUNBOOK completeness and reconcile re-ground callouts say the walk actuates the re-ground finding via `reground_bridge`, and no longer tell the operator to hand-edit `status:` for it.
- The RUNBOOK **Diagnosing convergence** remedy fork and four-remedies block mention `--apply-scope-out` and `reground_bridge`.
- Every command string, flag, and symbol quoted in the edited paragraphs resolves against HEAD (`plan-tool convergence --help`, `plan_tool/reground.py:reground_bridge`); no line cites `merge_bridge`.
- The RUNBOOK table of contents is unchanged (no heading added or renamed), and every `](#anchor)` link in the edited sections still points at a real heading.

## References

- [argparse — Parser for command-line options, arguments and subcommands](https://docs.python.org/3/library/argparse.html) — background for the `--apply-scope-out` flag this step documents (defined in step 1).
- [dataclasses — Data Classes (frozen=True)](https://docs.python.org/3/library/dataclasses.html) — the frozen `ScopeOutResult` / `RegroundResult` outcome objects the bridge prose refers to.

## Deferred

- **Documenting a merge bridge** — the merge bridge is deferred (plan Deferred); until its producer + executor land, `CLAUDE.md` / `RUNBOOK.md` keep describing the merge remedy as hand-run `plan-tool merge`. Documenting `merge_bridge` ships with that follow-up.
- Editing `plan_tool/cli/convergence_cmd.py`'s docstrings — step 1 owns the code-side docstring softening for `--apply-scope-out`; this step only mirrors it in `CLAUDE.md` / `RUNBOOK.md`.
- `docs/cli/convergence.md` and other generated `docs/cli/` reference pages — regenerated by `python -m plan_tool.cli_reference --write` in step 1, not hand-edited here.
- `USE_CASES.md`, `README.md`, and the `integrations/*/SKILL.md` routers — out of scope; this step is scoped to `CLAUDE.md` and `RUNBOOK.md` only, and read-only diagnostics/bridges are not advertised in the SKILL routers by convention.
- `CAPABILITIES.md` / `MISSION.md` — no new CLI surface or principle is introduced (the bridges reuse existing gates), so no capability-catalog or mission edit is required here.
