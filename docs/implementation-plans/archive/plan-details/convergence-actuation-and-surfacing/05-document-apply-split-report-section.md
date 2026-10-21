> **Auto-archived**: this plan was swept on 2026-07-08 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Document `--apply-split` and the in-report convergence section, and retire BACKLOG #57

## Summary

This is a docs-only step. It updates the four documentation surfaces that describe `plan-tool convergence` and the completeness report so they match what steps 2 and 4 shipped: `CLAUDE.md` and `RUNBOOK.md` gain the `--apply-split` actuator beside the existing `--apply-scope-out` text, `docs/AUDIT_FLOW.md` notes that the completeness report now renders a spinning-loop convergence section, and `BACKLOG.md` retires entry `#57` (both its tracked levers shipped) plus every inbound reference that still frames it as pending. The key call to get right is the multi-site sweep in `BACKLOG.md` — `#57` appears in its own block, two Quality/accuracy roll-up bullets, a T2 tier line, and three `#72`-telemetry example lists — so a naive "delete the block" leaves the roll-up and sibling entries disagreeing about its status. On green: the docs describe two actuation flags (`--apply-scope-out`, `--apply-split`) and the in-report section, and `grep -n "#57" BACKLOG.md` returns nothing that reads as unstarted or gating.

## Table of Contents

- [Why](#why) — the shipped actuator and report section are undocumented, and #57 is now stale
- [Input](#input) — the flag surface (step 2) and report section (step 4) whose shape the docs must match
- [Files (creates vs edits)](#files-creates-vs-edits) — four existing docs, no new files
- [Implementation](#implementation) — what each file must say, and the #57 multi-site repair
- [Tests](#tests) — verification for a non-code step: link/anchor checks and accuracy sweeps
- [Acceptance criteria](#acceptance-criteria) — checkable doc outcomes on green
- [References](#references) — the sibling docs and generated CLI page this step mirrors
- [Deferred](#deferred) — the generated `docs/cli/convergence.md` and structural-arm docs owned elsewhere

## Why

Steps 2 and 4 added real behavior that no operator-facing doc yet describes. Step 2 gave `plan-tool convergence` a `--apply-split` flag (with repeated `--into "TITLE"`) that actuates a spinning `FORK_LOCALIZED` verdict through the split executor, and step 4 made the completeness report render the convergence diagnosis as a section when the loop is spinning. The docs that teach this command — `CLAUDE.md`'s **Convergence diagnostic** and **Structural remedy vocabulary** paragraphs, `RUNBOOK.md`'s *Diagnosing convergence with `plan-tool convergence`* section, and `docs/AUDIT_FLOW.md`'s report-artifact description — still describe only the scope-out arm and a report with no convergence section, so an operator reading them wouldn't know the split arm or the in-report signal exists. Separately, `BACKLOG.md` `#57` tracks exactly the two levers this plan ships ("opt-in auto-execution of the localized re-split" and "report-section surfacing"); once they land, the entry is fully resolved and its inbound references become stale forward-looking work. This step makes the docs match reality and retires `#57` cleanly.

## Input

This step describes behavior owned by two sibling steps; the docs must match their shipped shape, not restate their mechanism.

- **`--apply-split` flag surface — step 2.** Step 2 adds `--apply-split` to `plan-tool convergence`, mutually exclusive with `--apply-scope-out`, plus repeated `--into "TITLE"` (append, not argparse-required). It actuates only a spinning `FORK_LOCALIZED` verdict, stays recommend-only unless a TTY confirm or `-y`, dispatches `plan_tool/detail.py:split_step` with `author_details=False` (zero Claude), and follows the command's exit convention — 0 on every completed outcome (including recommend-only when `--into` titles are absent), non-zero only on a mid-split failure. The docs describe this observable surface; they must not re-specify the dry-run-first refusal-vs-failure split or the staleness helper (those are step 1/2 internals).
- **In-report convergence section — step 4.** Step 4 computes a `ConvergenceDiagnosis` in `plan_tool/cli/completeness_phases.py:_persist_and_present_report` and threads it into `plan_tool/completeness_report.py:build_report_md`, which renders a section only on a spinning verdict (via step 3's `render_convergence_section`). The docs state that the completeness report gains this section when spinning and stays unchanged otherwise; they do not restate the count-the-current-run-once rule (step 4's internal).

Limit on verifying this input: these are prose-accuracy claims, not executable contracts. Verification is reading the shipped flag/section behavior (or the generated `docs/cli/convergence.md`) and confirming the prose agrees — there is no drift-guard test that fails if the prose lags.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `CLAUDE.md` — in the **Convergence diagnostic (`convergence_diagnosis.py`)** paragraph, add `--apply-split` as a second opt-in mutation flag beside `--apply-scope-out` (both exceptions to the no-mutation default path) and note it dispatches the split executor; in the **Structural remedy vocabulary** section's **re-split** bullet, name `convergence … --apply-split` as the actuation entry point for the `FORK_LOCALIZED` fork (today the bullet only says it "emits the same `plan-tool split` recommendation").
  - `RUNBOOK.md` — in the *Diagnosing convergence with `plan-tool convergence`* section, document `--apply-split` alongside `--apply-scope-out`: update the "one opt-in `--apply-scope-out` flag" sentence to cover two flags, extend the exit-code paragraph, add actuation to the **Localized over-pack** remedy bullet, and add a second-entry-point clause to the **re-split** bullet in *The four structural remedies, as one model*.
  - `docs/AUDIT_FLOW.md` — in the **Report artifact.** paragraph of the `completeness` section, note the report now renders a convergence-diagnosis section when the loop is spinning (and nothing when it isn't).
  - `BACKLOG.md` — remove the `#57` entry block and repair every inbound reference (two roll-up bullets, one T2 tier line, three `#72`-telemetry example lists).

## Implementation

The whole step is prose accuracy across four docs. Land each file's edits to match what steps 2 and 4 shipped; verify against the shipped flag/section behavior before writing, not against this file's summaries.

**`CLAUDE.md` — the Convergence diagnostic paragraph.** Today it reads that the command "on the **default (no-flag) path** performs **no mutation** — the one exception is the opt-in `--apply-scope-out` flag." Change "the one exception" to two: `--apply-scope-out` (actuates the scope-out carve) and `--apply-split` (actuates a spinning `FORK_LOCALIZED` re-split by dispatching the split executor, zero Claude). Extend the exit-code sentence so `--apply-split` shares the same rule already stated for `--apply-scope-out` — 0 on every completed outcome, non-zero only on a mid-actuation failure. Keep it terse (this file's house style); one clause per flag is enough. Do **not** describe `--into`, the mutual-exclusion group, or the dry-run refusal mechanics here — that depth belongs in `RUNBOOK.md`.

**`CLAUDE.md` — the Structural remedy vocabulary re-split bullet.** The **re-split** bullet currently ends "the `convergence` localized fork `FORK_LOCALIZED` / `_split_command`, which emits the same `plan-tool split` recommendation." Add that `convergence … --apply-split` now *actuates* that fork (not just recommends it), so re-split has a second entry point — mirroring how the **scope-out** bullet already names `--apply-scope-out` as a second entry point beside `plan-tool scope-out`. The last paragraph of that section says "mutation stays **gated** — a plan is narrowed only through `scope_out_step`'s … gate": that sentence is specifically about *narrowing* (scope-out), so a re-split actuation does not belong inside it. One safe option: leave that narrowing sentence alone and let the re-split bullet carry the split gate. Another: add a parallel clause noting the split arm is gated by the split executor's own recommend-or-confirm path. Pick whichever keeps the paragraph accurate without conflating narrow and split.

**`RUNBOOK.md` — the Diagnosing convergence section.** This is the fullest operator surface. Weave `--apply-split` in, don't add a new `##`/`###` section — the section already exists (`### Diagnosing convergence with plan-tool convergence`), so no Table-of-contents wiring is needed. Concretely:
- The sentence "on its **default (no-flag) path mutates nothing** — the one opt-in `--apply-scope-out` flag actuates the printed scope-out carve" must now cover two opt-in flags.
- The exit-code paragraph ("`--apply-scope-out` also exits 0 for every *completed* outcome … exits **1 only** when a `NarrowError` fails the plan narrow mid-carve") should state that `--apply-split` follows the same completed-vs-failed convention, with a mid-split failure as its non-zero case.
- The **Localized over-pack** remedy bullet currently prints only "a **pre-filled** `plan-tool split <plan> --step N --into … --into …`." Add that `plan-tool convergence <plan> --apply-split --into "…" --into "…"` actuates that same re-split directly from the diagnosis, and that with no `--into` titles it stays recommend-only and prints the recipe (the operator supplies the sub-step titles because the diagnosis knows the over-packed step but not the concern names).
- In *The four structural remedies, as one model*, the **re-split** bullet should gain a "second entry point" clause the way the **scope-out** bullet already has one ("its `--apply-scope-out` flag is a second entry point").

**`docs/AUDIT_FLOW.md` — the Report artifact paragraph.** After the existing description of what the completeness report records (dispositions, per-category rationale), add that when the loop is *spinning* the report now renders a convergence-diagnosis section near the top, and that a converging/healthy loop renders unchanged. Keep it to one or two sentences and point at `plan-tool convergence` for the standalone form. Do not restate the run-counting rule.

**`BACKLOG.md` — retire `#57` and repair inbound references.** `#57` tracks exactly the two levers this plan ships, and its structural re-seed arm is explicitly recommend-only steady state (not deferred work), so nothing remains to track — remove the entry, don't mark it fixed-in-place. This file is a cross-linked graph, so sweep every site (`grep -n "#57" BACKLOG.md` is the checklist):
- **Its own block** — the `**#57 — Decomposition convergence loop…**` entry under `### A. New capability, well-scoped`. Delete the whole block.
- **audit-coverage roll-up bullet** — the list under *Current quality/accuracy-impacting items* contains `**#57** (decomposition convergence diagnostic — remaining levers)`. Drop the `#57` item.
- **convergence roll-up bullet** — the same roll-up's `convergence:` line ends `**#57** (convergence loop, above)`. Drop it; if that leaves only `#41`, keep the bullet with `#41` alone.
- **T2 tier line** — `T2 — convergence & structural-remedy machinery (P1/P3)` lists `**#70** …, **#57**, **#71**`. Remove `#57` from the enumeration.
- **Three `#72`-telemetry example lists** — `#72`'s Why ("convergence detection (#57)"), its Dependencies ("#59/#60, #57, #38"), and the T3 tier line ("future plan-level size tuning, #59-60/#57/#38"). These cite `#57` as an example heuristic telemetry would ground. The convergence-*detection* heuristic still exists after this plan (only the levers shipped, not the diagnostic), so the meaning is worth keeping — but the `#57` id is now dead. Repair each by keeping the heuristic name ("convergence detection") and dropping the retired `(#57)` id, so no line still points at a removed entry. This is a judgment call per site; the invariant is that no surviving line frames `#57` as unstarted, pending, or gating other work.

If the implementer finds a genuinely unshipped remainder of `#57` (neither lever fully landed), keep a trimmed entry naming only that remainder instead of deleting the block — but per this plan both levers ship, so the expected outcome is full removal.

## Tests

### Verification (non-code step)

This step changes no production code, so verification is doc-accuracy and reference-integrity checks, not unit tests. There is no test-ordering directive.

- `grep -n "#57" BACKLOG.md` returns no line — confirms the block and all inbound roll-up/tier/telemetry references were swept.
- `grep -n "apply-split" CLAUDE.md RUNBOOK.md` shows the flag documented in both — confirms the actuator is described where operators read.
- Read the `CLAUDE.md` Convergence diagnostic paragraph — it names both `--apply-scope-out` and `--apply-split` as the two opt-in mutation exceptions to the no-flag default path.
- Read the `RUNBOOK.md` Diagnosing convergence section — the Localized over-pack bullet shows the `convergence … --apply-split --into …` actuation form and the recommend-only-without-titles fallback.
- Read the `docs/AUDIT_FLOW.md` Report artifact paragraph — it states the completeness report renders a convergence section on a spinning verdict and nothing otherwise.
- Anchor/link check: every markdown link touched still resolves. In particular, `BACKLOG.md`'s `#57` block linked to `RUNBOOK.md#diagnosing-convergence-with-plan-tool-convergence`; removing the block removes the only such inbound link, so no dangling anchor is introduced. Confirm no *other* doc links to a `#57`-derived anchor.
- Word-level sweep for stale framing: `grep -ni "remaining levers\|convergence loop" BACKLOG.md` surfaces no surviving phrase that still describes `#57`'s work as open.

## Acceptance criteria

- `grep -n "#57" BACKLOG.md` prints nothing.
- `CLAUDE.md` documents `--apply-split` as a second opt-in mutation flag on `plan-tool convergence`, beside `--apply-scope-out`, in the Convergence diagnostic paragraph.
- The `CLAUDE.md` Structural remedy vocabulary **re-split** bullet names `convergence … --apply-split` as an actuation entry point (not only a recommendation).
- The `RUNBOOK.md` Diagnosing convergence section documents `--apply-split` (actuation form with `--into`, recommend-only fallback without titles, and the exit-0-on-completed / non-zero-on-mid-split-failure convention), with no new `##`/`###` heading added.
- `docs/AUDIT_FLOW.md`'s Report artifact paragraph states the completeness report renders a convergence-diagnosis section when the loop is spinning and is unchanged otherwise.
- The `BACKLOG.md` Quality/accuracy roll-up (audit-coverage and convergence bullets) and the T2 tier line no longer list `#57`, and the `#72`-telemetry example lists cite "convergence detection" without a dead `#57` id.
- No markdown link in the edited files points at a removed `#57` anchor.

## References

- [argparse — mutually exclusive groups and `append` action (Python docs)](https://docs.python.org/3/library/argparse.html) — background for accurately describing the `--apply-split` vs `--apply-scope-out` exclusivity and the repeated `--into` flag the RUNBOOK prose documents.
- `docs/cli/convergence.md` — the generated per-command flag reference (produced by step 2); read it as the source of truth for the exact `--apply-split` / `--into` flag text before writing the hand-authored prose in `RUNBOOK.md` and `CLAUDE.md`.
- `RUNBOOK.md` *Carve a spinning region out of a plan (`plan-tool scope-out`)* and *Diagnosing convergence with `plan-tool convergence`* sections — the sibling operator prose whose structure and depth the `--apply-split` additions should mirror.

## Deferred

- Editing `docs/cli/convergence.md` — the generated CLI reference is regenerated by step 2 from the parser, not hand-edited here; this step only reads it as the source of truth.
- Documenting a `FORK_STRUCTURAL` actuation flag — the re-seed/re-decompose arm stays recommend-only by design (see the plan's Out of scope), so there is nothing new to document for it.
- Surfacing the convergence section in reconcile or other report-producing commands — step 4 lands the section only in the completeness report; other-command surfaces are out of this plan's scope.
- Restating step 4's count-the-current-run-once rule or step 2's staleness/dry-run internals — those are owned by their steps; this doc step describes only observable behavior.
