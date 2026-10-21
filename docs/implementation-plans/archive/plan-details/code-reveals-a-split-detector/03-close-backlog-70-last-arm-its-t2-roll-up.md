> **Auto-archived**: this plan was swept on 2026-07-12 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Close BACKLOG #70's last arm and its T2 roll-up

## Summary

Retire BACKLOG #70 now that step 1 ships its final arm — the code-grounded split producer in the reconcile lane. This is a docs-only edit to `BACKLOG.md`: delete the whole #70 entry (all four convenience arms are now shipped) and repair the three open-work roll-ups that still name "#70's remaining code-reveals-a-split arm" as open T2 work — the T2 tier list, the Readiness-lens Concrete "highest open by tier" line, and the "Next concrete pick" line. The load-bearing rule: the deletion is a claim that step 1's producer shipped, so gate it on grep-confirming that producer exists at HEAD (expected `plan_tool/review.py:_code_reveals_split_recommendations`) and, on any gap, stop and route back to step 1 rather than patching code here. On green, `grep -n '#70' BACKLOG.md` finds no line asserting #70 has open work, and the next-pick prose points at the new highest concrete item (#72 / the #97 build) instead of the retired arm.

## Table of Contents

- [Why](#why) — the last #70 arm ships, so the entry and its open-work roll-ups go stale
- [Input](#input) — step 1's producer (the shipped surface this deletion asserts) and the roll-ups this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — one edited doc, no new files
- [Implementation](#implementation) — the HEAD gate, the entry deletion, and the three roll-up repairs
- [Tests](#tests) — verification for a docs-only step
- [Acceptance criteria](#acceptance-criteria) — observable checks a reviewer can run
- [References](#references) — the source module to grep-verify before deleting
- [Deferred](#deferred) — the promotion residue and the #70 mentions left as design context

## Why

BACKLOG #70 ("Structural-remedy vocabulary: remaining convenience arms") tracked several convenience arms over the shipped structural-remedy bridges. Three of its arms — multi-step carve, auto-bridges, and the completeness-apply split bridge — are already marked SHIPPED in the entry. Its one open arm is **Code-reveals-a-split detection**: "reconcile can reveal a step that *must split*; no producer for it lands yet." Step 1 of this plan lands that producer. Once it ships, #70 has no open work, so the entry contradicts the doc's own "Remove a feature's entry when it ships" rule, and three roll-ups that steer the reader — the T2 tier list, the Readiness-lens Concrete line, and the "Next concrete pick" — still name the now-shipped arm as the highest concrete open item. Left alone, the next `plan-tool reconcile-plan` audit flags the stale entry as drift, and an operator reading the priority section is pointed at work that no longer exists.

## Input

- **Step 1's producer (the fact this deletion asserts).** Step 1 (this plan's `depends_on: 1`) lands a reconcile-lane-only producer in `plan_tool/review.py` that emits one advisory `granularity-split` recommendation for a single non-`DONE` step whose `heuristic_already_done` hits reveal a built/un-built seam. The expected shipped symbol is `plan_tool/review.py:_code_reveals_split_recommendations`, called inside the reconcile-lane block `if reconcile_lane and step_filter is None:` of `extract_recommendations` (the same block that already hosts `_reground_already_built_recommendation`). **Confirm the shipped name at HEAD before deleting the arm** (grep `plan_tool/review.py`); follow step 1's shipped name if it differs. Do not restate step 1's trigger mechanics — this step only needs the producer to exist.
- **The roll-ups this step reads and repairs (all in `BACKLOG.md`).** The #70 entry block (starts at the `**#70 — Structural-remedy vocabulary: remaining convenience arms**` heading), the **T2** tier bullet (starts `- **T2 — convergence & structural-remedy machinery (P1/P3):**`), the Readiness-lens **Concrete (ready to implement)** bullet's "Highest open by tier" sentence, and the **Next concrete pick** line. Each names #70's code-reveals-a-split arm as open; the Quality/accuracy lens roll-up does **not** reference #70 and needs no edit (verified: its facet lists cite #97/#38/#30/#82/#66/#102/#91/#87/#108/#72, not #70).

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `BACKLOG.md` — four edits:
    - Delete the entire **#70** entry block (heading through its `**Origin:**` line, ending just before the `**#66 — …**` heading).
    - In the **T2** tier bullet, drop the `**#70** (…)` clause so the bullet lists only `**#71** (theoretical — decision-first)`, rewording the bullet so it reads cleanly with #70 gone.
    - In the Readiness-lens **Concrete** bullet, drop the `**#70's remaining code-reveals-a-split arm** (T2, trust core) →` clause from the "Highest open by tier" chain so it starts at `**#72** / the **#97** build (T3)`.
    - Rewrite the **Next concrete pick** line to name the new highest concrete item (**#72**, per the Concrete "highest open by tier" chain) instead of #70's arm.

## Implementation

**Gate the whole edit on a HEAD check of step 1's producer — this is the one non-negotiable.** Before touching `BACKLOG.md`, grep `plan_tool/review.py` for the code-grounded split producer (expected `_code_reveals_split_recommendations`) and confirm it is wired inside the `if reconcile_lane and step_filter is None:` block of `extract_recommendations`. Deleting the arm is a claim that this code shipped; a wrong deletion silently destroys the only forward-looking record that the work was pending. If the producer is absent or unwired, **stop and route back to step 1 — do not add or patch any code in this docs step** (a code change here would be unscoped and skip the convergence loop). This mirrors the shipped rule for a record-deleting docs step.

**Retire the #70 entry by deleting the whole block, not by leaving a slimmed stub.** All four arms are now shipped, so no open work remains under #70. Delete the entire entry (heading through `**Origin:**`). Do **not** keep a trimmed #70 entry alive to hold the plan's forward-looking residue — step 1 defers "promotion" of the info-level split finding to a blocking / auto-dispatch severity, but that residue already lives in this plan's own `## Deferred`, which survives because the plan is archived rather than deleted. A slimmed carry-over entry would contradict the delete-whole call and resurrect a "still open" record the deletion was meant to remove. The rejected alternative — marking the arm `SHIPPED (date)` in place like the other three arms and keeping #70 as a fully-shipped record — is wrong here precisely because it's the *last* arm: with no open work left, keeping the entry violates the doc's remove-on-ship rule.

**Repair the three open-work roll-ups so none still points at the retired arm.** These are the sites where #70 steers reader priority:
- **T2 tier bullet** (`- **T2 — convergence & structural-remedy machinery (P1/P3):** …`). It currently reads `**#70** (… shipped; one remaining convenience arm — code-reveals-a-split), **#71** (theoretical — decision-first).` Drop the `#70` clause entirely, leaving `#71` as T2's only open item. Reword the surrounding sentence so it doesn't dangle (the tier header names "structural-remedy machinery," which #70 owned — keep the header, just fix the item list).
- **Readiness-lens Concrete bullet.** Its "Highest open by tier" chain leads with `**#70's remaining code-reveals-a-split arm** (T2, trust core) → **#72** / the **#97** build (T3) → hygiene …`. Remove the #70 lead so the chain starts at `**#72** / the **#97** build (T3)`. #71 stays theoretical (already in the Theoretical list), so it does not become the new highest *concrete* item.
- **Next concrete pick line** (`**Next concrete pick:** **#70's remaining code-reveals-a-split arm** — …`). Rewrite it to name the new highest concrete pick — **#72**, derived from the Concrete "highest open by tier" chain (which now leads with `**#72** / the **#97** build (T3)` once #70's lead is removed) — with a one-line rationale in the same shape as the existing sentence. Keep it consistent with that Concrete bullet's chain so the two don't disagree on what's next. Do **not** justify the pick from the recommended-execution ordering, which foregrounds T2 (incl. the ready-to-run `#101` plan) ahead of #72 and would introduce a fresh contradiction.
- **Bridge the residual tension with the Recommended-execution-order line (`BACKLOG.md:549-552`).** That line stays intact and still foregrounds `→ T2 (incl. the authored rate-limit-loop-extraction / #101) → T3`, so with the next-pick now at `#72` (T3) a reader sees two roll-ups naming different next actions. Do **not** re-decide the pick; instead add a short bridging clause (to the Next-pick line or the execution-order line) making explicit that they answer *different* questions: the **execution order** is the sequence to work *through* — it correctly runs already-authored/ready plans (`#101`) and open T2 first; the **Next concrete pick** is the highest concrete item still to *author* once that ready work is drained. Framed this way the two are complementary, not contradictory.

**Sweep every remaining `#70` mention and decide per-site — repair open-work roll-ups, leave design-context mentions.** After the three repairs, `grep -n '#70' BACKLOG.md` will still find mentions that are *not* open-work assertions and should stay:
- The general cluster/tax mentions (e.g. "every plan authored for #70/#66 pays that tax", the "#70, #66" cluster line, the "#70-spawned branching-workflow enabler" origin note for `parallel-plan-worktrees`) describe shipped context, not open work — leave them.
- The **#103** and **#106** entries reference "#70 arm 4" / "#70, shipped" as the origin of the *completeness-apply split bridge* — a different, already-shipped arm. These are accurate origin citations for those live entries; leave them.
- The **`#70/C shipped`** citations (the "narrower unit/command pins for #70/C", the "**#70/C shipped in `53b6438`**" dependency line, and the "surfaced … while tightening #70/C" origin line — a separate, already-shipped arm) cite a shipped surface as regression-harness context — leave them.
- The **"builds on the fingerprint infra and the #70 structural actuators"** dependency line (in another live entry) cites #70's shipped structural actuators as a build-on dependency — leave it.
- The "#70 auto-bridge work" motivation line inside another entry (the structural-observation ledger entry) describes shipped split/merge/scope-out/re-ground logic as design context — leave it.

The rule: repair anything that says or implies #70 has open work (the three roll-ups); leave anything that cites #70's shipped surfaces or origins as context. The load-bearing check is that after the edit, no line frames #70 as an open backlog item — confirm by reading each `#70` hit, not by an ID-only delete.

## Tests

### Verification (non-code step)

This step changes no production code — verify the doc edit by inspection and grep, not unit tests.

- `grep -n '#70' BACKLOG.md` — every surviving hit is a shipped-context / origin mention; none asserts #70 has open work, and the #70 entry block is gone.
- `grep -n 'code-reveals-a-split\|Code-reveals-a-split' BACKLOG.md` — no hit frames the arm as remaining/open (the T2 clause, the Readiness lead, and the Next-pick line no longer name it).
- Read the **T2** bullet — it lists `#71` as its only open item and reads cleanly with #70 removed.
- Read the **Readiness-lens Concrete** bullet and the **Next concrete pick** line — they agree on the new highest concrete pick (#72) and neither names #70's arm.
- Read the **Quality/accuracy lens** roll-up — unchanged and still correct (it never named #70).
- Confirm the deletion gate held: `grep -n '_code_reveals_split_recommendations' plan_tool/review.py` (or step 1's shipped name) returns the producer inside `extract_recommendations`'s `reconcile_lane and step_filter is None` block — the proof step 1's work shipped before the arm was closed.

## Acceptance criteria

- The `**#70 — Structural-remedy vocabulary: remaining convenience arms**` entry block is fully removed from `BACKLOG.md`.
- `grep -n '#70' BACKLOG.md` returns no line asserting #70 has open/remaining work; every remaining `#70` mention is a shipped-context or origin citation (including the #103/#106 "#70 arm 4" origin references, which stay).
- The T2 tier bullet no longer lists #70; its only open item is `#71`.
- The Readiness-lens "Highest open by tier" chain and the "Next concrete pick" line no longer name #70's code-reveals-a-split arm and instead point at #72 / the #97 build.
- No slimmed-down #70 stub remains; the promotion follow-up is not re-filed as a #70 carry-over entry.
- Step 1's producer (`_code_reveals_split_recommendations`, or its shipped name) is present and wired in `plan_tool/review.py` at HEAD before the entry is deleted.

## References

- [`plan_tool/review.py`](plan_tool/review.py) — grep for step 1's code-grounded split producer (expected `_code_reveals_split_recommendations`) and the `reconcile_lane and step_filter is None` block before deleting the arm; this is the shipped surface the deletion asserts.

## Deferred

- **Promoting the code-grounded split finding from advisory `info` to a blocking / auto-dispatch severity** — out of scope; it lives in this plan's own `## Deferred` (kept durable via plan archival). Filing a fresh forward-looking backlog entry for it is optional implementer judgment and is explicitly **not** a reason to keep a trimmed #70 entry alive.
- **The non-open-work `#70` mentions** (the "pays that tax" / cluster / "#70-spawned" origin lines, the #103/#106 "#70 arm 4" origin citations, the `#70/C shipped` regression-harness citations, and the "builds on … #70 structural actuators" dependency line) — left as accurate shipped-context references; this step does not de-reference them.
- **Any edit to CLAUDE.md / RUNBOOK prose** — owned by step 2 (documenting the producer); this step touches only `BACKLOG.md`.
