> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 7 — Update CLAUDE.md, AUDIT_FLOW.md, and BACKLOG #83 for the axis-split bare-plan fence

## Summary

Three documents still describe the bare-plan apply fence as one blanket rule, and steps 2–5 replace it with a split by axis. This step corrects them: `CLAUDE.md` § "Correctness gates" loses the blanket claim, `docs/AUDIT_FLOW.md`'s completeness section gains an explicit statement of the fence it never had, and `BACKLOG.md` **#83** narrows its harness premise to the half that stays structural-only. The key decision is to fix the whole claim, not just the sentence the step's `gate:` greps for — the same blanket rule is restated in #106 and #114, and an identifier-only sweep leaves prose still arguing for the fence this plan removed. On green, the `gate:` grep finds nothing, and no document in the repo says a bare plan's conceptual-correctness gaps have no apply route.

## Table of Contents

- [Summary](#summary) — what the step does and the observable result.
- [Why](#why) — three stale claims, and what each one costs.
- [Input](#input) — what steps 2–5 land, and what stays withheld.
- [Files (creates vs edits)](#files-creates-vs-edits) — the three files and the edits per file.
- [Implementation](#implementation) — what each document must say, the sweep, and the alternative rejected.
- [Verification (non-code step)](#verification-non-code-step) — the runnable checks that replace unit tests.
- [Acceptance criteria](#acceptance-criteria) — checkable facts.
- [References](#references) — what to read before starting.
- [Applicable guardrails](#applicable-guardrails) — the plan fences that bind this step.
- [Deferred](#deferred) — nearby doc work this step does not take, and why.

## Why

`CLAUDE.md` § "Correctness gates" says the `completeness` action surface is gated on detail-bundle presence and that "detail-level actions unlock only once a complete detail bundle exists". That file loads into every later session, so a stale claim there is not a documentation bug that sits quietly — it actively tells the next session the route steps 2–5 open does not exist. `docs/AUDIT_FLOW.md` has the opposite problem: it documents the jira-grade fence in detail (`### Auditing against the jira-grade bundle`) and never states the bare-plan one at all, so the flow doc's gate map is missing the gate this plan changes. And `BACKLOG.md` **#83** proposes a harness that would pin "the whole operator surface stays structural-only" and that "next steps must not emit `plan-tool detail`" — after step 3 the bare-plan BLOCKED bullet leads with `plan-tool detail` on purpose, so an unedited #83 would have someone build a test asserting the defect this plan fixes.

## Input

This step reports what steps 2–5 land. Read the landed code before writing a sentence about it — an earlier detail file's proposed wording is a proposal, and the landed behavior wins on any disagreement.

- **Step 2 — the report and console next steps, plus two prose sites.** A bare plan's conceptual-**correctness** gaps name `plan-tool completeness-apply`; its conceptual-**completeness** gaps still do not. Both `suggested_next_steps` and `suggested_next_step_commands` in `plan_tool/completeness_report.py` read one fence, and the same step axis-scopes `build_report_md`'s bare-plan withheld paragraph and `console_summary`'s conceptual-completeness line.
- **Step 3 — the BLOCKED remedy.** On a bare plan the BLOCKED bullet leads with `plan-tool detail <name>` and keeps `plan-tool split` as the second option; a fully-detailed plan's bullet is unchanged (`_blocked_next_step` and the BLOCKED branch of `suggested_next_step_commands`).
- **Step 4 — the apply verb.** `cmd_completeness_apply` in `plan_tool/cli/completeness_cmd.py` walks `plan-correctness` gaps on a bare plan; every other saved source stays reported-and-skipped.
- **Step 5 — the grouped report.** `_render_grouped_report` in `plan_tool/cli/completeness_phases.py` says the same thing in its `### Suggested next steps` block.

**What stays withheld on a bare plan — do not sweep these away.** The docs must keep saying so, because they are still true:

- The **deterministic detail-level findings**: `DETAIL_LEVEL_FINDING_SOURCES` in `plan_tool/completeness_report.py` (`detail-coverage`, `files-coherence`, `detail-body`). These are not conceptual sources and this plan does not touch them.
- The **files-coherence writer** — `cmd_completeness_apply` still skips `_apply_files_coherence` on a bare plan.
- **Conceptual-completeness gaps** — still no apply route on a bare plan.
- **Jira grade** — unchanged for its own separate reason (no sidecar to replay).

**One limit on checking this.** These are prose documents; nothing machine-checks that a sentence describes the code correctly. The `gate:` grep proves one phrase is gone, not that what replaced it is true. The verification list below closes that with per-claim reads of the landed code.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `CLAUDE.md` — rewrite the detail-bundle-gate clause in § "Correctness gates" so it states the axis split and the bare BLOCKED remedy. Leave the `#85` read-only-audit-split sentence and the parallel-apply sentence in that same paragraph alone.
  - `docs/AUDIT_FLOW.md` — add the bare-plan fence to the `## completeness — conceptual audit` section, and add a `## Source map` row for each newly cited symbol.
  - `BACKLOG.md` — narrow **#83**'s premise; correct the same blanket claim where **#106** and **#114** restate it.

## Implementation

### `CLAUDE.md` — the headline fix

The target is the clause in § "Correctness gates" beginning *"The `completeness` action surface is additionally gated on **detail-bundle presence**…"*. What must be true when it is done:

- The literal string the step's `gate:` greps for is gone. That is necessary, not sufficient.
- The clause states the split by axis: a bare or partially-detailed plan keeps the `completeness-apply` route for conceptual-**correctness** gaps, and still withholds it for conceptual-**completeness** gaps, the deterministic detail-level findings, and the files-coherence writer.
- It names the bare BLOCKED remedy in a few words — bare plan → `plan-tool detail` leads, `split` second.
- The parenthetical principle *"a completeness action can only target what exists"* still holds and is worth keeping; what changes is its consequence. A correctness gap targets the plan body, step titles, and acceptance criteria, which exist on a bare plan. Say that, rather than deleting the principle.
- The word **structure-only** is the part that goes stale even after the gate literal is removed. Applying a correctness gap edits plan-body prose, so "a bare plan gets a structure-only review" is no longer an accurate summary. Rewrite the framing, don't patch around it.

Keep it to a clause or two. `CLAUDE.md`'s architecture paragraphs are deliberately terse and the depth belongs in `docs/AUDIT_FLOW.md`.

### `docs/AUDIT_FLOW.md` — state the fence it never stated

The doc currently describes the bare state nowhere outside the jira-grade subsection. Add one bold-lead paragraph to `## completeness — conceptual audit (deterministic + multi-pass claude audit)` covering, in the doc's own voice:

- what `is_bare` is and where it comes from (`audit_detail_bundle_status` / `DetailBundleStatus.is_bare` in `plan_tool/review.py`);
- correctness gaps keep the `completeness-apply` route; completeness gaps and the deterministic detail-level sources do not;
- the BLOCKED remedy is coverage-aware at plan level — never keyed on which step a finding sits on;
- the two next-step renderers and the grouped block all read one fence, so they cannot disagree.

**Placement — one way.** Put it immediately before `### Auditing against the jira-grade bundle (--grade jira)`. That subsection already carries the parallel paragraph *"Next steps name no verb this grade cannot serve"*, so the coverage axis and the grade axis read as siblings. Any placement inside the completeness section works; this one costs the reader the least.

**Conventions that are not free to vary:**

- **Match this doc, not `docs/RUN_FLOW.md`.** `AUDIT_FLOW.md` uses bold lead-in paragraphs and tables and carries **zero** `[BLOCK]` / `[WARN]` markers; `RUN_FLOW.md` carries 15. Do not import that idiom here.
- **Update the `## Source map` table** for every symbol the new text cites. This is the doc's standing contract and the row is the only thing that keeps a cited symbol findable after a rename. Likely rows: the fence helper and `_blocked_next_step` in `plan_tool/completeness_report.py`, `audit_detail_bundle_status` / `DetailBundleStatus` in `plan_tool/review.py`, and `cmd_completeness_apply` in `plan_tool/cli/completeness_cmd.py`.
- **Cite symbols, never line numbers.**
- **Do not touch the high-level flow diagram.** It maps `completeness-audit` and `reconcile-plan`; `completeness-apply` is not in it, so the fence needs no box.
- **Check the jira subsection still reads as jira-scoped.** Its sentence *"the report never suggests `completeness-apply` or `--iterate`"* is true of jira grade and must not be readable as a claim about bare plans once the new paragraph sits above it.

### `BACKLOG.md` — #83, then the class

**#83** stays open — this plan authors no harness. Narrow it:

- Its "What" bullet asserts the surface stays structural-only across every renderer and that next steps must not emit `plan-tool detail`. Both halves are now wrong. Rewrite so the harness would pin the *post-split* baseline: the completeness axis and the deterministic detail-level writers stay withheld, the correctness axis has a route, and the bare BLOCKED bullet leads with `plan-tool detail` on purpose.
- Add a dated provenance line naming this plan as what narrowed it (2026-08-03), per the repo's rule that history gets dated and framed as past.
- Do not mark it shipped and do not delete it.

**Then fix the class.** The same blanket claim is restated twice more in this file, and these are exactly the "vocabulary half" of the sweep — grep for the concept's words, not only for `#83`:

- **#106** — two edits, not one.
  - Its **"What"** says the gate `return 0`s and skips the **entire** saved walk when any step lacks a detail bundle. The entry's subject survives (a `granularity-split` finding against a fully-detailed step on a partial plan is still skipped, so the entry is still worth doing), but that description of the gate becomes false after step 4. Correct the description; keep the entry.
  - Its **"Scope caution"** bullet asks for per-finding target-detailed-ness across **all** conceptual sources. That is the routing this plan's `## Out of scope` refuses with a measurement: only **6.0%** of conceptual findings resolve to a step (116 of 1,933; `plan-completeness` 4.5%, `plan-correctness` 8.1%), so a per-finding gate over those sources classifies ~94% as ungrounded and collapses back to the binary it replaces. Narrow the bullet to the sources that **do** carry a reliable `step_id` — `granularity-split` is the one the entry's own example uses — and cite the 6.0% figure as the reason the conceptual sources are excluded. Leaving it as written would have someone build the refused routing under a different entry's number.
- **#114** — its per-command filter predicate cites "the existing bare-plan apply gate at `completeness_cmd.py:341`". The picker predicate itself is unaffected, but the parenthetical describes a gate that no longer works that way, and it cites a line number. Replace with a symbol anchor and a one-clause correction.

Sweep only these; leave unrelated line-number citations elsewhere in the file alone.

### The alternative rejected

Satisfying the `gate:` grep by deleting the one offending fragment from `CLAUDE.md` and stopping. It passes the gate and leaves three documents still describing a blanket fence — the "structure-only" framing in the same sentence, plus #106 and #114. A finding naming one spot names one instance of a defect that has siblings; the cited spot is where you start, not where you stop.

## Verification (non-code step)

This step is `change_type: non-code`, so the plan's `enforce_step_tests: true` gate does not fire — the test-authoring gate keys on `change_type` and only runs for `feature` / `refactor` steps. These runnable checks stand in for tests:

1. `! grep -q 'detail-level actions unlock only once a complete detail bundle exists' CLAUDE.md` — the step's declared `gate:`, exits 0.
2. `grep -n 'structure-only' CLAUDE.md` — no remaining hit claims a bare plan's whole completeness action surface is structure-only.
3. `grep -rn 'completeness-apply' docs/AUDIT_FLOW.md` — the new paragraph exists and the jira-subsection mention still reads as grade-scoped.
4. Every symbol newly cited in `docs/AUDIT_FLOW.md` resolves at HEAD: `rg '<symbol>' plan_tool/` returns a definition for each.
5. `docs/AUDIT_FLOW.md`'s `## Source map` has a row for each module the new text cites.
6. No line numbers appear in any text added to the three files.
7. Each doc claim is read back against the landed code: the fence helper and `_blocked_next_step` in `plan_tool/completeness_report.py`, the bare branch of `cmd_completeness_apply`, and `_render_grouped_report`'s bare-plan bullet. Any disagreement resolves toward the code.
8. `grep -n 'complete detail bundle\|structural-only\|only target what exists' BACKLOG.md` — every surviving hit is either correct after the split or carries a dated past framing.
9. `uv run pytest -m "not integration" tests/ -q` stays green — this step changes no production code, so a red suite means an edit landed somewhere it should not have.
10. `git status` shows only `CLAUDE.md`, `docs/AUDIT_FLOW.md`, and `BACKLOG.md` changed.

## Acceptance criteria

- `grep -q 'detail-level actions unlock only once a complete detail bundle exists' CLAUDE.md` returns non-zero.
- `CLAUDE.md` § "Correctness gates" names both axes: correctness gaps have the `completeness-apply` route on a bare plan, completeness gaps and the deterministic detail-level findings do not.
- `CLAUDE.md` § "Correctness gates" names the bare-plan BLOCKED remedy as `plan-tool detail`.
- `docs/AUDIT_FLOW.md`'s completeness section contains a paragraph stating the bare-plan fence, and its `## Source map` gained a row for each newly cited module.
- `BACKLOG.md` **#83**'s "What" bullet no longer asserts the bare-plan surface is structural-only across every renderer, and no longer forbids `plan-tool detail` in next steps.
- `BACKLOG.md` **#83** is still open and carries a dated line naming this plan as what narrowed it.
- `BACKLOG.md` **#106** and **#114** no longer describe the apply gate as skipping every conceptual source on a bare plan; **#114** cites a symbol rather than a line number.
- `BACKLOG.md` **#106**'s "Scope caution" bullet is scoped to sources carrying a reliable `step_id` and cites the 6.0% step-resolution measurement as the reason the conceptual sources are excluded.
- After this step, no repo document describes the bare-plan conceptual apply fence as one blanket rule — the plan's matching acceptance criterion, and the reason verification check 8 greps the concept's words rather than a single phrase.
- No text added by this step claims jira-grade behavior changed, or describes per-finding coverage routing as existing or planned.
- `uv run pytest -m "not integration" tests/ -q` is green and `git diff --stat` lists exactly three files.

## References

- `CLAUDE.md` § "Correctness gates" — holds the blanket contract this step replaces; loaded into every later session, which is why it is the headline edit.
- `docs/AUDIT_FLOW.md` — the audit flow's gate/sequence reference; its `## completeness` section is where the fence goes and its `## Source map` is the table that must follow.
- `BACKLOG.md` **#83** — the harness entry whose premise narrows to the completeness axis; **#106** and **#114** restate the same blanket claim.
- `plan_tool/completeness_report.py` — the fence helper steps 1–2 land, `_blocked_next_step`, and `DETAIL_LEVEL_FINDING_SOURCES` / `DETAIL_LEVEL_DIAGNOSTIC_SOURCES` (the sources that stay withheld).
- `plan_tool/review.py` — `audit_detail_bundle_status` and `DetailBundleStatus.is_bare`, the observable every doc sentence here routes on.
- `plan_tool/cli/completeness_cmd.py` — `cmd_completeness_apply`'s bare branch and its `_apply_files_coherence` gate; read both before writing what the verb does.
- `plan_tool/cli/completeness_phases.py` — `_render_grouped_report`, the third next-steps surface step 5 aligns.

## Applicable guardrails

- **The plan's "## Out of scope", three refusals.** No text this step adds may describe per-finding coverage routing, excluding bare runs from the convergence series, or a persisted detail-coverage field as existing, planned, or open. They are settled refusals — documenting one as future work reopens it by the back door.
- **The plan's "## Out of scope", the "Also out" list.** This step may not document a new gate, exit-code flip, or blocking severity; may not describe jira-grade behavior as changed; may not re-describe `#85`'s read-only-audit split; and may not edit anything belonging to **#224**.
- **The plan's "## Architecture", decisions 1 and 2 (plan level).** Both the fence and the BLOCKED remedy key on the plan-level bare flag. The docs must say that, never imply the tool routes per finding.
- **The plan's "## Architecture", decision 3 (claim only what it is).** Do not carry the plan's bare-vs-detailed finding-rate measurement into any of these three documents, and never restate it as saturation. A number restated in a second place becomes load-bearing there; it belongs in the plan.
- **The plan's "## Risks", the six-surfaces bullet.** Describe one fence. A doc that describes the report prose, the console block, and the grouped report as separate rules re-creates the drift step 1 removed.
- **The plan's "## Testing", per-step strategy for step 7 (non-code).** Verification appropriate to the artifacts, not unit tests.
- **The step's own `gate:`.** It checks one phrase in `CLAUDE.md`. Treat it as the floor, not the finish line.

## Deferred

- **Building the #83 harness** — this step narrows the entry's premise; the entry stays open and the harness is still someone's work.
- **`docs/AUDIT_FLOW.md`'s `--iterate` paragraph**, which says the conceptual audit's blocking correctness findings are applied via `apply_finding` alongside the deterministic ones. That describes `#85`'s read-only-audit split, which the plan's "## Out of scope" fences off — do not fix it here. If reading the landed loop shows it disagrees with HEAD, it is a doc claim wrong about code, which routes to `BUG_BACKLOG.md` under the plan's "## Deferred"; that file is outside this step's declared list, so surface it to the operator rather than editing it.
- **`plan-tool completeness-apply --help`** — step 4 owns the verb's own help text.
- **The report and console prose strings in `plan_tool/completeness_report.py` and `plan_tool/cli/completeness_phases.py`** — steps 2, 3, and 5 own them; this step describes what they say, it does not write them.
- **`DETAIL_FORMAT.md`, `DATA_CONTRACT.md`, `CAPABILITIES.md`, `RUNBOOK.md`** — checked, none restates the bare-plan apply fence, so none needs an edit. No schema or capability moves in this plan.
- **#106's actual fix** — this step corrects the entry's description of the gate and narrows its Scope caution to sources with a reliable `step_id`; the work the entry proposes stays open and unclaimed under that narrower fence. Per-finding routing over the *conceptual* sources stays refused (the plan's `## Out of scope`), so it may not reappear as #106's remaining work.

## Tests

This is a `change_type: non-code` step; its proof is the runnable checks in [Verification (non-code step)](#verification-non-code-step), not unit tests.

