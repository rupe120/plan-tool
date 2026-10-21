> **Auto-archived**: this plan was swept on 2026-07-07 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 8 — Document the prompt-budget advisory in RUNBOOK.md and reconcile BACKLOG.md #95

## Summary

Document the pre-send prompt-budget advisory that steps 1–7 shipped, and reconcile its BACKLOG entry. Add a new operator-facing section to `RUNBOOK.md` (plus its table-of-contents line) explaining what the advisory is, which commands emit it, what the per-block breakdown shows, how `--dry-run` surfaces it, and that it never blocks a call or changes the exit code — then point operators at the structural remedies (`scope-out`, split, re-decompose, seed splitting, lower audit `--max-passes`) for what to do about a warning. In `BACKLOG.md`, mark **#95** plan-authored rather than removing it: the advisory itself has shipped, but the shared-seam double-warn / double-telemetry suppression is deliberately **not** part of this plan (the backstop and the named-block hooks both fire on a named-block send — an accepted residual), so it is filed as its own forward-looking entry **#99**, which #95 names as its retained remainder. Fold #95's other deferred follow-up (capping `run`'s uncapped full-detail embed) into **#97** where the embed-budget work already lives, and fix every cross-reference so none frames the shipped advisory as unstarted. This is a **non-code** step — no production code changes. On green, `RUNBOOK.md` has a discoverable advisory section reachable from the ToC, `BACKLOG.md` #95 reads as plan-authored with the double-fire suppression tracked as #99, and the test suite stays green.

## Table of Contents

- [Why](#why) — the operator-facing gap this closes now that the advisory ships.
- [Files (creates vs edits)](#files-creates-vs-edits) — the two docs this step edits.
- [Implementation](#implementation) — the new RUNBOOK section, the ToC wiring, and the BACKLOG reconcile.
- [Tests](#tests) — none; this step changes no code.
- [Verification (non-code step)](#verification-non-code-step) — the doc-accuracy and stale-claim grep sweeps.
- [Acceptance criteria](#acceptance-criteria) — checkable states on green.
- [References](#references) — the token-counting and context-window docs behind the advisory.
- [Deferred](#deferred) — CLAUDE.md architecture prose and other follow-ups left out of this step's file scope.

## Why

Steps 1–7 land a pre-send advisory that warns an operator when an assembled prompt is close to the context window — across `detail`, `create`, plan-audit, `run`, and a generic backstop at the batch shell seam — but nothing in the operator docs explains it. An operator who sees a new `warning:` line on stderr, or a per-block breakdown under `--dry-run`, has no doc to tell them what it means, that it is advisory-only (never blocks the call, never flips the exit code), or what to do about a tight-headroom warning. `RUNBOOK.md` is where operators already go to interpret prompts (the [Inspecting prompts before they run](#inspecting-prompts-before-they-run) and [Mutating vs. read-only modes](#mutating-vs-read-only-modes) sections), so the advisory belongs there. Separately, `BACKLOG.md` #95 is the entry that scoped this whole plan; the advisory ships here, but the shared-seam double-warn / double-telemetry suppression does not — the step-7 backstop and the named-block hooks both fire on a named-block send, an accepted residual filed as its own forward-looking entry **#99**. So #95 is **plan-authored with a retained remainder** (→ #99) rather than fully shipped — per the backlog rule to mark an entry plan-authored when work is still pending. Leaving the cross-references framing the shipped advisory as future work is the other half to fix.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `RUNBOOK.md`:
    - Add one new top-level `##` section documenting the prompt-budget advisory (recommended title: **The prompt-budget advisory**).
    - Add the matching bullet to the `## Table of contents` list so the section is discoverable.
  - `BACKLOG.md`:
    - Mark the **#95 — Pre-send prompt budget advisory** entry plan-authored: set its `- **Status:**` line to plan-authored (this plan) and name the outstanding shared-seam double-warn / double-telemetry suppression — filed as **#99** — as the entry's tracked remainder. Do **not** delete the block.
    - Fix every remaining reference to #95 so none frames the shipped advisory as not-started: the `grounding:` line in the quality/accuracy roll-up index, the **T3** tier line, the "Remaining prompt-context quality (#95/#97)" note above `### A`, and the #97 cross-references that say #95 "should ship first." These should read that the advisory has shipped (with the #99 suppression remainder still open).
    - Fold #95's other deferred follow-up — the optional cap on `run`'s uncapped full-detail embed — into **#97**, which already documents that asymmetry.

## Implementation

Describe the shipped behavior in operator terms and reconcile the backlog. Reference the shipped surfaces by their owning step; don't restate how each hook works.

**Add the RUNBOOK advisory section — document observable behavior, not internals.** Cover, in bullets an operator can act on:

- **What it is:** a pre-send, advisory-only headroom check. Before a command sends a prompt to the backend, the tool estimates the prompt's size against the model's context window and, only when headroom is tight, prints a color-gated `warning:` line to stderr with a per-block breakdown showing which sections of the prompt dominate. It never blocks the call and never changes the exit code — same "surface unconditionally, mutate/block never" stance as the [`plan-tool convergence`](#diagnosing-convergence-with-plan-tool-convergence) diagnostic.
- **When it fires:** on the real send of every Claude-invoking command. The named-block breakdown is wired into `detail` (step 3), `create`'s distill / steps / synthesis phases (step 4), the plan-audit loop (step 5), and `run`/`check`/`security`/`reconcile` steps (step 6). Callers with no named blocks — `jira`, `lessons`, `annotate` — still get a total-bytes backstop at the shared batch seam (step 7). It does **not** fire on a resumed-from-checkpoint step or a `--dry-run` (no send).
- **The three levels:** the advisory stays silent at `ok`, and warns at `warn` and `high` (tighter headroom). State that the estimate rounds the token count up on purpose, so it errs toward warning early rather than missing an overflow — an occasional early warning is the intended bias.
- **Inspecting before you spend:** `detail --dry-run` and `run --dry-run` print the full per-block breakdown to stderr **at every level** (even `ok`) for each step they would author or run, so an operator can see headroom before burning a call. The breakdown goes to stderr because the dry-run prompt itself goes to stdout; a dry run records no telemetry. Tie this into the existing [Inspecting prompts before they run](#inspecting-prompts-before-they-run) section (recommended: place the new advisory section right after it, one way).
- **What to do about a warning:** the advisory tells you a prompt is large; it does not shrink it. Point operators at the existing structural remedies rather than re-describing them: carve an over-packed step with [`plan-tool scope-out`](#carve-a-spinning-region-out-of-a-plan-plan-tool-scope-out), split a step, [re-decompose a spinning plan](#when-repeated-auditapply-doesnt-converge--re-decompose-dont-keep-patching), split a seed that covers multiple plans ([a seed that's too large](#workflow-a-seed-thats-too-large-or-covers-multiple-plans)), or lower an audit's pass count. Frame these as the response to a tight-headroom warning.
- **Telemetry note (brief):** each real send records one `prompt-budget` decision event locally under `.plan-tool/telemetry/` for later threshold tuning; a dry run records nothing. Keep this to a sentence — the event shape lives in `DATA_CONTRACT.md` (step 2), not here.

**Constraints on the RUNBOOK section:**

- **Document behavior, not constants or internals.** Do not name `BYTES_PER_TOKEN`, `DEFAULT_CONTEXT_WINDOW`, the `PromptBudget` dataclass, or the leaf function names — those are code/test surfaces that churn. Describe "conservative token estimate," "per-block breakdown," and "warn / high" as observable behavior. This mirrors the docs-only lesson that operator docs explain what an operator sees, not helper internals.
- **Match the existing RUNBOOK voice and the sibling reference sections.** Use the same terse, bulleted style as [Inspecting prompts before they run](#inspecting-prompts-before-they-run) and [Mutating vs. read-only modes](#mutating-vs-read-only-modes); end the section with the `---` separator those sections use.
- **Wire the ToC.** Add the new section's bullet to the `## Table of contents` list in document order (next to the `Inspecting prompts before they run` / `Mutating vs. read-only modes` entries if you place the section there), with the GitHub-slug anchor of your chosen title.

**Reconcile BACKLOG.md #95 — mark it plan-authored with a retained remainder, and repair every cross-reference.** The key rule: no surviving line may present the shipped advisory as unstarted, and the still-open shared-seam suppression must survive as #95's tracked remainder (→ #99).

- **Mark the #95 entry block plan-authored** under `### A. New capability, well-scoped` (the `**#95 — Pre-send prompt budget advisory …**` block): flip its `- **Status:** not started.` line to plan-authored (this plan), and add/keep a `- **Remainder:**`-style line naming the outstanding work — the shared-seam double-warn / double-telemetry suppression, filed as **#99** (the step-7 backstop and the named-block hooks both fire on a named-block send). Keep the block; do not delete it.
- **Fix the roll-up index** in the quality/accuracy lens (the `- **grounding:**` bullet that lists `**#95** (pre-send prompt-budget advisory — catch overflow before it truncates the analysis)`): note #95's advisory as shipped/plan-authored rather than pending, leaving #97 and the others.
- **Fix the T3 tier line** (`**#95/#97** (prompt-context quality — pre-send budget advisory and symbol-aware file excerpts …)`) and the note just above `### A` (`Remaining prompt-context quality (#95/#97) sits in the same T3 grounding band.`): reflect that #95's budget-advisory half has shipped (only its mark-wiring remainder remains), with #97 still open.
- **Update the #97 cross-references** that treat #95 as a prerequisite — the Risks line ("**#95** should ship first or in parallel") and the Dependencies line ("**#95** (budget advisory) for operator visibility when excerpts still clip") — so they read as "#95 has shipped" rather than "#95 must ship first." Line 626–628's "count toward **#95** advisory" can stay as a live pointer to the shipped advisory.
- **Fold the other deferred follow-up into #97.** #95's "Not in scope" deferred capping `run`'s uncapped full-detail embed as a "separate follow-up." #97 already documents this exact asymmetry (its embed-budget table row for `run` / `renderer._load_detail` marked "**full detail today** — document asymmetry; optional follow-up cap"). Confirm that note still reads as the live home for the run-embed cap; add a short pointer there if needed. Do **not** create a new standalone entry for it. (The shared-seam double-fire suppression is filed as **#99** and named as #95's retained remainder — only the embed-cap follow-up moves to #97.)
- **Leave #72 untouched.** The `record_prompt_budget` recorder shipped as #95's telemetry extension, but the broader #72 decision/outcome telemetry item is still open; its references to prompt-budget are context, not deliverables this step closes.

**Constraint — no code, no schema, no CLI-doc regeneration.** This step edits only the two named docs. It does not touch `docs/cli/` (nothing in the argparse parser changes) and does not run `python -m plan_tool.cli_reference --write`.

## Tests

No unit tests — this step changes no production code. See [Verification (non-code step)](#verification-non-code-step) for the doc checks.

### Verification (non-code step)

- **ToC ↔ section anchor match** — the new `## Table of contents` bullet's anchor is the GitHub slug of the new section's `##` heading, and clicking it lands on the section. Check by eye or with an anchor-lint pass.
- **In-doc links resolve** — every `#…` link the new RUNBOOK section adds (`scope-out`, re-decompose, seed-too-large, inspecting-prompts, convergence) points at a heading that exists in `RUNBOOK.md`. `grep -n "^### Carve a spinning region\|^## Inspecting prompts\|^### When repeated audit"` should confirm each target.
- **Accuracy against shipped behavior** — the section's claims (advisory-only, never blocks / never changes rc, warns at warn/high, silent at ok, dry-run prints at all levels to stderr and records nothing) match what steps 1–7 actually do. Spot-check against the shipped `plan_tool/prompt_budget.py` and the wired call sites rather than the BACKLOG's aspirational wording.
- **#95 status sweep** — `grep -n "#95" BACKLOG.md` returns no line that calls the advisory "not started" or a prerequisite that "should ship first"; the standalone `**#95 — …**` entry block survives, marked plan-authored, and names the outstanding shared-seam suppression (**#99**) as its retained remainder. A `grep -n "#99" BACKLOG.md` shows the new entry exists and #95 points to it.
- **Follow-up preserved** — `grep -n "full detail\|follow-up cap\|_load_detail" BACKLOG.md` shows the run-embed cap follow-up still documented under #97.
- **Suite stays green** — `uv run pytest -m "not integration" tests/ -q`. `RUNBOOK.md` and `BACKLOG.md` are hand-maintained and not covered by any drift-guard test (only `docs/cli/*` is, via `tests/cli/test_cli_reference.py`), so a green suite is only a sanity check, not proof the doc is accurate — the greps above are the real gate.

## Acceptance criteria

- `RUNBOOK.md` has a new top-level `##` section documenting the prompt-budget advisory, and a matching bullet in `## Table of contents` whose anchor resolves to it.
- The new section states the advisory is advisory-only: it never blocks a call and never changes the exit code.
- The new section names the commands that emit the advisory (`detail`, `create`, plan-audit, `run`, plus the `jira`/`lessons`/`annotate` backstop) and says `--dry-run` prints the breakdown without sending.
- The new section links an operator to at least the `scope-out`, split/re-decompose, and seed-splitting remedies for a tight-headroom warning.
- The new section names no code-level identifier (`PromptBudget`, `estimate_prompt_budget`, `BYTES_PER_TOKEN`, `DEFAULT_CONTEXT_WINDOW`).
- `grep -n "#95" BACKLOG.md` returns no line presenting the shipped advisory as unstarted or as a pending prerequisite; the #95 entry block survives, marked plan-authored, and retains the shared-seam suppression (**#99**) as its tracked remainder.
- The run-embed full-detail cap follow-up survives in `BACKLOG.md` under #97.
- `uv run pytest -m "not integration" tests/ -q` passes.

## References

- [Anthropic — Token counting](https://docs.anthropic.com/en/docs/build-with-claude/token-counting) — grounds the advisory's byte/token estimate; useful for a one-line doc note on why the estimate is conservative.
- [Anthropic — Models overview (context windows)](https://docs.anthropic.com/en/docs/about-claude/models/overview) — the per-model context-window sizes the advisory compares against; background for the "headroom" framing.

## Deferred

- **CLAUDE.md architecture paragraph for the `prompt_budget` leaf** — a short "Prompt-budget advisory" leaf paragraph in `CLAUDE.md`'s Architecture section would parallel the `telemetry.py` / `convergence_diagnosis.py` leaf write-ups, but `CLAUDE.md` is outside this step's declared `files:` list (RUNBOOK.md, BACKLOG.md). Leave it for a reconcile follow-up rather than expanding this step's footprint.
- **Capping `run`'s uncapped full-detail embed** — not this step's work; it stays a forward-looking follow-up folded into #97's embed-budget note, not a code change here.
- **`docs/cli/` regeneration** — no argparse flag or help string changes in this plan, so the generated per-subcommand reference needs no rebuild.
- **#72 telemetry entry edits** — the broader decision/outcome telemetry item stays open; this step does not close or rewrite it.
