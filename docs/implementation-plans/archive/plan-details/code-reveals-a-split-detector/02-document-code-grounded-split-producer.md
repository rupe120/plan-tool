> **Auto-archived**: this plan was swept on 2026-07-12 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Document the code-grounded split producer in CLAUDE.md and RUNBOOK

## Summary

Refresh the durable prose in `CLAUDE.md` and `RUNBOOK.md` so it names the new code-grounded **split** producer that step 1 lands in the reconcile lane — the inverse of the already-documented code-grounded **re-ground** finding. The main edit is registering `granularity-split` as now having a **second producer** (reconcile's code finding) in `CLAUDE.md`'s **Granularity advisor** paragraph, mirroring how that paragraph already registers re-ground as `granularity-merge`'s second producer. `RUNBOOK.md` gets a sibling operator callout next to the existing **Code-grounded re-ground finding** callout, plus a one-line note in the completeness `Smells (advisory)` write-up. No production code changes. On green, a reader of either doc learns the reconcile lane can now flag a single step that code reveals should split, that the finding is advisory `info` and recommend-only, and where the producer lives.

## Table of Contents

- [Why](#why) — the docs lag the new producer step 1 ships
- [Input](#input) — the producer step 1 owns and the doc sites this step edits
- [Files (creates vs edits)](#files-creates-vs-edits) — two edited docs, no new files
- [Implementation](#implementation) — which paragraphs/callouts change and the shape each edit takes
- [Tests](#tests) — verification for a docs-only step
- [Acceptance criteria](#acceptance-criteria) — observable checks a reviewer can run
- [References](#references) — the source modules to grep-verify before writing
- [Deferred](#deferred) — what this docs step leaves out

## Why

Step 1 adds a code-grounded split producer to the reconcile lane in `plan_tool/review.py` — the inverse of the existing re-ground producer `_reground_already_built_recommendation`. The docs already describe re-ground in several durable spots (the `CLAUDE.md` **Granularity advisor** paragraph, the `RUNBOOK.md` **Code-grounded re-ground finding** callout, the completeness `Smells (advisory)` write-up). Every one of those spots names re-ground as the *only* code-grounded producer and describes `granularity-split` as coming only from the static `granularity.py` detectors and the `detail` MIXED-STEP path. Once step 1 ships, that prose is stale: `granularity-split` now has a code-grounded producer too. A docs-refresh that mirrors the re-ground write-up keeps the durable prose honest, so the next reconcile audit doesn't flag it as drift and a reader isn't told the split detector is unbuilt.

## Input

This step reads two things; it writes no schema and consumes no runtime contract.

- **Step 1's producer (the fact this step documents).** Step 1 lands a reconcile-lane-only producer in `plan_tool/review.py` that emits one advisory `granularity-split` recommendation at `severity="info"` for a single non-`DONE` step whose `heuristic_already_done` hits reveal a built/un-built seam. Step 1 owns its exact symbol name and prose — the expected name is `review.py:_code_reveals_split_recommendations`; **confirm the shipped name at HEAD before writing it into the docs** (grep `plan_tool/review.py`), and follow step 1's shipped name if it differs. Do not restate step 1's trigger mechanics beyond the one-line summary the docs need.
- **The current doc sites (what this step edits).** The existing re-ground write-ups this step mirrors — `CLAUDE.md`'s **Granularity advisor** paragraph, and `RUNBOOK.md`'s **Code-grounded re-ground finding** callout plus the `Smells (advisory)` paragraph. Match their wording and structure so the split note reads as the intentional inverse.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `CLAUDE.md` — in the **Granularity advisor** paragraph, add that `granularity-split` now has a second producer (reconcile's code-grounded split finding), mirroring the sentence that already registers re-ground as `granularity-merge`'s second producer.
  - `RUNBOOK.md` — add a sibling operator callout next to the **Code-grounded re-ground finding** callout; add a one-line note in the completeness `Smells (advisory)` paragraph that the reconcile lane also emits a code-grounded split finding reusing the `granularity-split` literal at `info`; and add the reconcile code-grounded producer to the **four-remedies model** re-split entry (`~:2347`) so the re-split producer enumeration isn't left stale.
  - **Also update the re-split *producer enumeration* in `CLAUDE.md`** — the structural-remedy-vocabulary **re-split bullet** (which lists `granularity-split` → `escalate_to_split` / `plan-tool split`, and the `convergence` `FORK_LOCALIZED` producer) gains a new recommender (the reconcile code-grounded split finding); add it so the model isn't stale for the next reconcile audit. **Do NOT edit the escalate-to-split paragraph** — a recommend-only `info` producer never routes through that bridge, so it has nothing to add there.

## Implementation

The job is to make three durable prose spots name the new producer, matching the shape of the re-ground write-up that already sits beside each. Keep every edit additive and short — one clause or one callout per spot, not a rewrite.

- **`CLAUDE.md` — Granularity advisor paragraph (the one starting `**Granularity advisor (`granularity.py`).**`).** This paragraph already says `granularity-merge` **now has a second producer outside `granularity.py`: reconcile's code-grounded re-ground finding**. Add the parallel fact for `granularity-split`: it now also has a second producer outside `granularity.py` — reconcile's code-grounded **split** finding (the inverse of re-ground), which fires on a single non-`DONE` step whose `heuristic_already_done` hits reveal a built/un-built seam, is scoped to the reconcile lane, reuses the `granularity-split` literal at `severity="info"`, and stays **recommend-only** (never auto-dispatched to `escalate_to_split`, never flips an exit code, stays out of `APPLY_ELIGIBLE_SOURCES`). One way to place it: a sentence right after the existing per-stage-surfaces sentence, before or beside the `granularity-merge` second-producer sentence, so both second-producer facts read together.
- **Say why `info` + `granularity-split` stays recommend-only.** The reader may worry that reusing the `granularity-split` literal makes the finding auto-splittable. State the reason plainly: `review_walk.py:split_escalation_target` gates auto-dispatch on `severity == "medium"` **and** the source being in `extra_apply_sources`, so an `info` finding can't reach the split bridge. This is the same reasoning the existing re-ground note relies on for its neutral routing — keep it to one clause.
- **`RUNBOOK.md` — add a callout beside `> **Code-grounded re-ground finding.**`** Write a sibling blockquote, e.g. `> **Code-grounded split finding.**`, matching the re-ground callout's voice: `reconcile-plan` now surfaces a per-step **split** finding when one non-`DONE` step's code reveals it fuses a built part (some of its declared files already built) and an un-built part; it is **advisory**, sourced `granularity-split` at `info`, tallied in the `Findings:` banner, **never flips the exit code**, and is **recommend-only** — it points at `plan-tool split` and is not auto-applied. Carry over the same low-confidence-heuristic caveat the re-ground callout ends with (the built/un-built signal is a proxy, so confirm before splitting). Place it right after the re-ground callout so the two code-grounded findings sit together.
- **`RUNBOOK.md` — completeness `Smells (advisory)` paragraph (the one that mentions `granularity-split` / `granularity-merge` and the reconcile re-ground note in parentheses).** That paragraph already carries a parenthetical: *the reconcile lane's code-grounded re-ground finding reuses the same `granularity-merge` literal but is not this merge advice*. Add the inverse one-liner: the reconcile lane also emits a code-grounded **split** finding reusing the `granularity-split` literal at `info`, distinct from the advisor's static split hint, recommend-only. Keep it to one sentence.

Constraints and gotchas that are not free to vary:

- **Never touch production code in this step.** The step's declared files are `CLAUDE.md` and `RUNBOOK.md` only. If grep at HEAD shows step 1's producer is missing or named differently than assumed, **stop and route back to step 1** — do not add or rename code here.
- **Match the shipped source name exactly.** The docs must name the real symbol step 1 ships. A guessed name (`_code_reveals_split_recommendation` vs `_code_reveals_split_recommendations`) becomes a stale reference the next reconcile flags. Grep-confirm before writing it.
- **Do not describe the finding as blocking, applyable, or auto-splitting.** It is advisory `info`, recommend-only, out of `APPLY_ELIGIBLE_SOURCES`. Any prose implying it gates or auto-applies contradicts step 1's contract.
- **Keep it additive; don't rewrite the re-ground prose.** The re-ground write-ups stay as-is. This step adds the split's parallel note beside each, so a reviewer sees the deliberate inverse.

## Tests

### Verification (non-code step)

This step changes no production code; verify the docs read correctly and match HEAD.

- Grep `plan_tool/review.py` at HEAD for the split producer (expected `_code_reveals_split_recommendations`) and confirm the exact symbol name the docs will cite exists — the doc edit is only correct once step 1 has shipped this.
- Grep `plan_tool/review.py` for `granularity-split` and confirm the code-grounded emit is at `severity="info"` and inside the `if reconcile_lane and step_filter is None:` block, matching the docs' claim of reconcile-lane-only + advisory `info`.
- Grep `plan_tool/review_walk.py:split_escalation_target` and confirm it gates on `severity == "medium"`, so the docs' "info stays recommend-only" clause is true.
- Read the edited `CLAUDE.md` **Granularity advisor** paragraph and confirm the new second-producer sentence reads as the intentional inverse of the existing re-ground second-producer sentence.
- Read the edited `RUNBOOK.md` callout and `Smells (advisory)` note and confirm every symbol/source token named (`granularity-split`, `_code_reveals_split_recommendations`, `plan-tool split`) resolves to a real symbol at HEAD.
- Run `plan-tool reconcile-plan` against this plan (or a docs link/accuracy pass) and confirm no drift finding fires on the two edited docs.

## Acceptance criteria

- `CLAUDE.md`'s **Granularity advisor** paragraph names a second producer of `granularity-split` — reconcile's code-grounded split finding — and states it is reconcile-lane-only, `info`, recommend-only, and out of `APPLY_ELIGIBLE_SOURCES`.
- `RUNBOOK.md` has a **Code-grounded split finding** callout beside the **Code-grounded re-ground finding** callout, describing an advisory `granularity-split` `info` finding that never flips the exit code and is recommend-only.
- `RUNBOOK.md`'s completeness `Smells (advisory)` paragraph notes the reconcile lane's code-grounded split finding reuses the `granularity-split` literal, mirroring the existing re-ground parenthetical.
- Every source symbol the new prose cites (the step-1 producer name, `granularity-split`, `split_escalation_target`, `plan-tool split`) resolves to a real symbol at HEAD.
- No production `.py` file is modified by this step.

## References

- `plan_tool/review.py` — grep-verify step 1's shipped split producer, the `granularity-split` `info` emit, and the `if reconcile_lane and step_filter is None:` block before writing the docs (the source the prose cites).
- `plan_tool/review_walk.py` — `split_escalation_target`, the gate whose `severity == "medium"` clause is why the `info` split finding stays recommend-only.
- `plan_tool/reground.py` — `reground_bridge`, the re-ground actuator the existing callouts name; read it to keep the split callout's voice parallel and honest about the inverse.

## Deferred

- **Any production code change** — this step only edits docs; the producer itself is step 1's.
- **Generated CLI reference docs (`docs/cli/*.md`)** — this step adds no CLI flag, so `python -m plan_tool.cli_reference --write` is not run and no generated doc is in scope.
- **BACKLOG.md close-out** — retiring BACKLOG #70's last arm and its roll-up is step 3's job; don't touch `BACKLOG.md` here.
- **A dedicated auto-apply/bridge write-up for the split finding** — the finding is recommend-only by design, so it needs no escalate-bridge trigger documentation beyond the recommend-only note; the escalate-bridge trigger prose (`RUNBOOK.md`'s `## Two detail triggers` / four-surfaces list) stays as-is.
