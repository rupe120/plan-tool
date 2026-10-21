> **Auto-archived**: this plan was swept on 2026-07-09 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Reconcile BACKLOG #100 and update the audit-coverage roll-up reference

## Summary

This is a **non-code, docs-only** step over one file, `BACKLOG.md`. Once steps 1–4 ship the three checks (`self_consistency_recs` bucket, elevated `suppression-shape`, `orphaned-deliverable`, and advisory `claim-vs-delivery`), retire the **#100** backlog entry and drop its clause from the **audit-coverage** facet of the Quality/accuracy lens roll-up. The key decision: #100 is a **single-purpose** entry whose whole core ships in this plan, so it is **deleted in full** (like #93), not left with a "SHIPPED" note the way multi-arm #70 was. On green, a `grep -n '#100' BACKLOG.md` returns no live-entry or roll-up hits (only archived copies, which stay untouched), and the audit-coverage facet reads cleanly with `#66` as its sole member.

## Table of Contents

- [Why](#why) — the two live references to #100 that go stale when the code ships
- [Input](#input) — the shipped symbols from steps 1–4 this step verifies before deleting
- [Files (creates vs edits)](#files-creates-vs-edits) — the one file touched
- [Implementation](#implementation) — verify-then-delete the entry, repair the facet, decide the deferred follow-up
- [Tests](#tests) — verification by grep and by-eye read (non-code step)
- [Acceptance criteria](#acceptance-criteria) — observable grep/read checks
- [References](#references) — none needed
- [Deferred](#deferred) — the one forward item this reconcile does not itself build

## Why

`BACKLOG.md` carries **two live references to #100** that become wrong the moment steps 1–4 land the code: the full entry block **"#100 — Deterministic plan self-consistency gate …"** (near the end of the file), and its clause in the **audit-coverage** facet of the **"Current quality/accuracy-impacting items"** roll-up (under the `### Quality/accuracy lens (cross-cutting)` heading, where the facet lists `#66` then `#100`). Leaving either in place asserts the work is still forward-looking after it has shipped, which misleads triage and leaves a dangling `#100` a grep still finds. This step brings the backlog into agreement with the code that steps 1–4 delivered.

## Input

- **Steps 1–4 ship #100's three checks.** This step depends on all four (`depends_on: 1, 2, 3, 4`) and must confirm their symbols exist at HEAD before it deletes the entry that claims them. Reference their outcomes, not their mechanism:
  - **Step 1** adds the blocking-capable `self_consistency_recs` field on `_DeterministicReport` in `plan_tool/cli/completeness_phases.py`, wired into the gate and both renderers.
  - **Step 2** elevates `detect_suppression_shape` (`plan_tool/review.py`) to `severity="medium"` and moves it onto `self_consistency_recs`.
  - **Step 3** adds `detect_orphaned_deliverable` plus the shared `build_plan_footprint` matcher in `plan_tool/review.py`, wired into `_run_deterministic_checks`.
  - **Step 4** adds `detect_claim_vs_delivery` (advisory, on `smell_recs`) in `plan_tool/review.py`.
- **Verification limit:** confirm the symbols exist by name at HEAD (a grep is enough); this docs step does not judge whether they are correct — that is the steps' own test gates.

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**

- `BACKLOG.md`
  - Delete the entire **"#100 — Deterministic plan self-consistency gate (claim-vs-delivery, orphaned deliverable, elevate suppression-shape)"** entry block — its heading and every field bullet (`What` / `Why` / `Scope` / `Effort` / `Risks` / `Approach` / `Quality` / `Dependencies` / `Iterate`).
  - Remove the **#100** clause from the **audit-coverage** facet bullet in the roll-up so it ends cleanly on the `#66` clause; repair the comma/period so the surviving member reads as a single clean sentence.

## Implementation

**Foundational logic:** retire one shipped single-purpose backlog entry and its one roll-up cross-reference, without touching sibling entries or archived copies.

**Do the shipped-symbol check first — stop and route back on a gap.**

- **Grep HEAD for each step's landed symbol** before deleting anything: `self_consistency_recs` (`plan_tool/cli/completeness_phases.py`), `detect_orphaned_deliverable` and `build_plan_footprint` and `detect_claim_vs_delivery` (`plan_tool/review.py`), and confirm `detect_suppression_shape` emits `severity="medium"` (not `info`).
- **On any gap, STOP** — do not delete the entry and do not patch code here. Route back to the owning code step (1, 2, 3, or 4). Deleting #100 while its code is missing loses the only forward-looking record; patching code turns this docs-only step into an unscoped code change with no convergence loop.

**Delete the whole #100 entry — it is single-purpose, not multi-arm.**

- **Pick delete-whole by whether any live arm remains, not by the ship event alone.** #100 describes exactly the three checks this plan delivers; nothing in the entry survives as separate live work, so it is deleted in full — the same call made for #93. This is the opposite of #70, a multi-arm entry that kept a `2026-07-08` SHIPPED note and shed only one bullet because sibling arms stayed live. #100 has no sibling arms, so no note is left behind.
- **Grep the entire file for `#100`, not just the entry block.** The roll-up facet is a second live reference in the same file; a `#100` left in the audit-coverage bullet is a dangling ID that the post-edit grep still finds.

**Repair the audit-coverage facet.**

- The facet currently lists two members — `#66` (contract-trace / path-enumeration) and `#100` (the intent-consistency complement to #66). Drop the `#100` clause and its lead-in punctuation so the bullet ends on the `#66` clause with a clean period.
- **Leave the other four facets untouched** (`grounding`, `convergence`, `gate-signal`, `heuristic-tuning`) and leave `#66` itself intact — it is still live.

**Leave archived copies alone.** A `#100` grep may also hit `plan-seeds/archive/` and `docs/implementation-plans/archive/` copies. Those are historical artifacts outside this reconcile's file scope (only `BACKLOG.md` is in `files:`); editing them rewrites deferral/history language that was true when written.

**Handle the one genuine remaining follow-up.** The plan's own `## Deferred` section keeps **"Promoting `claim-vs-delivery` to blocking"** as future work once its false-positive rate is measured. That record lives in the plan file, which is archived rather than deleted, so it survives #100's removal. Filing it as a fresh standalone `BACKLOG.md` entry is **optional** and left to the implementer's judgment — if filed, add it to the audit-coverage roll-up in #100's place; if not, the plan's Deferred section is the tracking record. Do **not** keep a slimmed-down #100 alive solely for this — that would contradict the delete-whole call above.

## Tests

### Verification (non-code step)

This step changes no production code — verify by grep and by-eye read of `BACKLOG.md`:

- `grep -n '#100' BACKLOG.md` returns no live hits — no entry block, no roll-up clause (archived-path copies are out of this file's scope and are not matched by a `BACKLOG.md`-scoped grep).
- The audit-coverage facet bullet still names `#66` and reads as a clean single sentence with correct trailing punctuation.
- The other four roll-up facets (`grounding`, `convergence`, `gate-signal`, `heuristic-tuning`) and the `#66` entry are unchanged (diff shows only the #100 entry block and the #100 facet clause removed).
- `git diff BACKLOG.md` touches only the two intended regions and no other file changed.
- The shipped-symbol grep (see Implementation) confirms `self_consistency_recs`, `detect_orphaned_deliverable`, `build_plan_footprint`, `detect_claim_vs_delivery`, and the `medium` `suppression-shape` severity all exist at HEAD before the deletion lands.

## Acceptance criteria

- `grep -n '#100' BACKLOG.md` returns nothing (no entry block, no roll-up cross-reference).
- The `### Quality/accuracy lens (cross-cutting)` roll-up's **audit-coverage** facet lists `#66` only and ends with clean punctuation.
- No other `BACKLOG.md` entry or facet is altered; `git diff` shows removals confined to the #100 entry block and its audit-coverage clause.
- No file other than `BACKLOG.md` is modified by this step.
- The shipped code from steps 1–4 (`self_consistency_recs`, `detect_orphaned_deliverable`, `detect_claim_vs_delivery`, `build_plan_footprint`, and `suppression-shape` at `medium`) is present at HEAD.

## Deferred

- **Promoting `claim-vs-delivery` to blocking** — tracked in the plan's `## Deferred` section; this reconcile does not build it, and filing a fresh backlog entry for it is optional (see Implementation).
- **Editing archived `#100` copies** under `plan-seeds/archive/` or `docs/implementation-plans/archive/` — historical artifacts outside this step's `BACKLOG.md`-only file scope; left untouched.
- **Any code change in steps 1–4** — this step only reconciles the backlog; on a missing symbol it stops and routes back to the owning code step rather than patching.
