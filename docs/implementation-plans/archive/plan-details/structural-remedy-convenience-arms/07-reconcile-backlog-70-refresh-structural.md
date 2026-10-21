> **Auto-archived**: this plan was swept on 2026-07-09 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 7 — Reconcile BACKLOG #70 and refresh the structural-remedy docs for the three shipped arms

## Summary

This non-code step closes the paperwork on the three convenience arms this plan shipped. It updates `BACKLOG.md` #70 to mark the multi-step/multi-region carve arm, the per-remedy `--merge`/`--reground` walk flags, and the re-ground `create --from-existing` re-baseline arm as shipped (naming this plan's slug and the new CLI flags), while leaving the code-reveals-a-split producer as the one remaining arm and **not** deleting #70. It refreshes the two operator/architecture doc surfaces — the "Structural remedy vocabulary", "Granularity advisor", and "Convergence diagnostic" paragraphs in `CLAUDE.md`, and the "four structural remedies" model, the scope-out walkthrough, and the walk-dispatch section in `RUNBOOK.md` — so they describe the `--through M` range carve, the multi-region `FORK_SCOPE_OUT` actuation, the per-remedy walk flags, and the re-baseline disposition. On green, `grep -n '#70' BACKLOG.md` shows the three arms marked shipped with the remaining arm intact, and no doc still describes scope-out as single-step-only or `--apply-structural` as the only per-remedy control.

## Table of Contents

- [Why](#why) — why the docs and backlog must catch up to the shipped code
- [Input](#input) — the shipped surfaces from steps 2, 3, 4, 6 this step describes
- [Files (creates vs edits)](#files-creates-vs-edits) — the three docs this step edits
- [Implementation](#implementation) — what each doc must say, and the verify-before-retire rule
- [Tests](#tests) — verification for a non-code step
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — docs relevant to this step
- [Deferred](#deferred) — what this step intentionally leaves alone

## Why

The three arms have landed in code (steps 2, 3, 4, 6) but the docs and backlog still describe the pre-arm world. `BACKLOG.md` #70 lists "multi-step carve", "per-remedy walk flags", and "re-ground re-baseline" as *remaining*; the T2 tier roll-up, the readiness lens, and the "Next concrete pick" line all repeat that stale list. `CLAUDE.md`'s "Structural remedy vocabulary" and "Convergence diagnostic" paragraphs still say scope-out carves a single `--step N` and that `FORK_SCOPE_OUT` prints `plan-tool scope-out <name> --step N`. `RUNBOOK.md`'s "four structural remedies" model and its walk-dispatch section describe only the `--apply-structural` umbrella and mark-done-only re-ground. Left unreconciled, an operator reads that these arms are unbuilt, and the next reconcile audit flags the docs as drifted from the code. This step makes the durable docs match what shipped.

## Input

This step describes surfaces its `depends_on` siblings shipped — cite them, do not restate their mechanism. Confirm each exists at HEAD before writing about it (see Implementation):

- **Step 2 — `scope-out --through M` range carve.** `plan-tool scope-out <name> --step N --through M` carves the inclusive `N..M` region into one forward-seed (`plan_tool/cli/scope_out_cmd.py:cmd_scope_out`, `plan_tool/scope_out.py:scope_out_step`), built on step 1's set-based `compute_narrow`/`apply_narrow`.
- **Step 3 — multi-region `FORK_SCOPE_OUT` actuation.** `plan_tool/convergence_diagnosis.py:classify_fork` recognizes a contiguous ascending range of severe, not-improving steps and emits a `FORK_SCOPE_OUT` whose remedy is the range carve; `plan-tool convergence <name> --apply-scope-out` (`plan_tool/cli/convergence_cmd.py`) actuates it.
- **Step 4 — per-remedy `--merge` / `--reground` walk flags.** `reconcile-plan` / `reconcile-plan-walk` gain two `store_true` flags that each enable only their own bridge; `--apply-structural` stays the enable-all umbrella (`plan_tool/cli/review_cmd.py`, `plan_tool/cli/review_actions.py`).
- **Step 6 — re-ground re-baseline disposition flag.** `reconcile-plan` / `reconcile-plan-walk` gain `--reground-rebaseline`, which forwards step 5's re-baseline disposition to `plan_tool/reground.py:reground_bridge` so an applied re-ground writes a `create --from-existing` seed **in addition to** marking the flagged steps done; mark-done stays the default.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `BACKLOG.md` — mark the three shipped arms under #70's entry (with this plan's slug and the new CLI flags), keep #70 alive with a dated SHIPPED note, leave the code-reveals-a-split producer listed, and sweep every other #70 cross-reference (the T2 tier line, the readiness-lens "concrete" list, the "Next concrete pick" line, the recommended-execution-order line) so none still names a now-shipped arm as remaining.
  - `CLAUDE.md` — refresh the "Structural remedy vocabulary", "Granularity advisor", and "Convergence diagnostic" paragraphs in the Architecture section for the range carve, multi-region actuation, per-remedy flags, and re-baseline disposition.
  - `RUNBOOK.md` — refresh the "four structural remedies, as one model" block, the "Carve a spinning region out of a plan (`plan-tool scope-out`)" walkthrough, the convergence FORK_SCOPE_OUT walkthrough, and the walk-dispatch "Structural-directive findings" item.

## Implementation

**Foundational rule: verify each shipped symbol/flag at HEAD before you write about it, and route back to the owning step on a gap.** This is a docs step depending on code steps 2, 3, 4, 6. Its whole value is naming real, landed surfaces. Before editing:

- **Grep for the actual CLI flags and symbols** — `--through`, `--apply-scope-out` (range path in `plan_tool/cli/convergence_cmd.py`), `--merge` / `--reground` (in `plan_tool/cli/review_cmd.py`), `--reground-rebaseline`, and the re-baseline disposition constants in `plan_tool/reground.py`. Use whatever names actually shipped; the flag/constant names above are what the sibling details proposed, not a guarantee.
- **On a gap, stop and route back to the owning code step** — do not patch code from this docs step, and do not mark an arm shipped whose surface you can't find. A docs step that patches code is an unscoped change with no convergence loop.

**`BACKLOG.md` #70 — retire three arms, keep the entry alive.** #70 is a multi-arm entry with one live arm remaining, so shed the shipped arms' bullets and add a SHIPPED note — do **not** delete the whole entry (that shape is for a fully-resolved single-purpose entry).

- **In the #70 entry block**, under "Remaining (convenience, not blocking)":
  - Mark "Multi-step / multi-region carve" shipped — name this plan's slug (`structural-remedy-convenience-arms`) and the flags (`scope-out --step N --through M`, `convergence --apply-scope-out` multi-region), dated 2026-07-09, matching the existing "SHIPPED (…, 2026-07-06/07-08)" note style already in the entry.
  - Under the auto-bridges "Remaining follow-ups (convenience)" line, mark both `per-remedy --merge / --reground walk flags` and `re-ground's create --from-existing re-baseline arm` shipped by the same plan; if that leaves the "Remaining follow-ups" line empty, drop the line.
  - Leave "Code-reveals-a-split detection" listed as remaining — the plan's "Out of scope" section keeps it as the one arm not built here.
- **Sweep the whole file for `#70`.** The lesson holds: a retired-arm reference lives in more than the entry block. Repair each so it no longer names a shipped arm as remaining:
  - The **T2 tier** line (`- **T2 — convergence & structural-remedy machinery…`) enumerates "remaining convenience arms — multi-step carve, code-reveals-a-split, per-remedy walk flags, re-ground re-baseline" — reduce it to just code-reveals-a-split.
  - The **readiness-lens "Concrete (ready to implement)"** line and the **"Next concrete pick"** line both name "#70's remaining convenience arms / arms" as the top open pick — reword so they point at only the remaining code-reveals-a-split arm (or move the "next pick" to the next-highest item if code-reveals-a-split is theoretical/spike-gated; use judgment against the surrounding tier text).
  - The **"Recommended execution order"** line references T2 — check it still reads correctly once #70's shipped arms are gone.
  - Contextual `#70` mentions in *other* entries (e.g. the perf-tax and cluster lines) are historical framing; leave them unless they assert an arm's status.

**`CLAUDE.md` — three Architecture paragraphs.** Keep edits surgical and in the existing terse style; do not restate mechanism the sibling steps own.

- **"Structural remedy vocabulary"** — in the **scope-out** bullet, update "which now prints the runnable `plan-tool scope-out <name> --step N`" and the single-id framing of `compute_narrow`/`apply_narrow` so both name the `--through M` range form (the narrow now carves an ordered id set). In the **merge / re-ground** bullet, note `reground_bridge` now has a second disposition (a `create --from-existing` re-baseline seed) alongside mark-done, and that the walk's `--apply-structural` umbrella is now narrowable by per-remedy `--merge` / `--reground` and the re-baseline `--reground-rebaseline` flag. The closing "reachable now from two commands" sentence still holds — just make sure it doesn't imply scope-out is single-step-only.
- **"Convergence diagnostic"** — the `FORK_SCOPE_OUT` clause says it "prints the runnable `plan-tool scope-out <name> --step N`". Widen it: a multi-region focus prints/actuates the range form `--step N --through M`, and `--apply-scope-out` actuates that range carve.
- **"Granularity advisor"** — the paragraph describes `_dispatch_merge_remedy` and `reground_bridge` gated behind `--apply-structural`. Add that each remedy now has its own opt-in (`--merge` / `--reground`), that `--apply-structural` stays the enable-all superset, and that re-ground can additionally write a re-baseline seed under `--reground-rebaseline`.

**`RUNBOOK.md` — operator walkthroughs.** These are the operator-facing surface; be concrete about the runnable commands.

- **"The four structural remedies, as one model."** In the **scope-out** bullet, add the `--through M` range form beside `plan-tool scope-out <plan> --step N` and note `convergence --apply-scope-out` actuates a multi-region focus. In the **merge / re-ground** bullet, add that an applied re-ground can also write a `create --from-existing` re-baseline seed (`--reground-rebaseline`), and that `--merge` / `--reground` are the per-remedy opt-ins narrowing `--apply-structural`.
- **"Carve a spinning region out of a plan (`plan-tool scope-out`)."** Add the range form to the example block (e.g. `plan-tool scope-out my-feature --step 2 --through 4 --apply`), state it writes **one** seed for the whole region and narrows atomically, and note the CLI rejects an out-of-order range. Keep the single-`--step` examples.
- **The convergence FORK_SCOPE_OUT walkthrough** (the "Severe-and-not-improving region → scope-out / defer" step and the `--apply-scope-out` description) — note that a contiguous multi-step spinning region prints and actuates the range carve, not just a single `--step N`.
- **The walk-dispatch "Structural-directive findings" item** — add that `--merge` / `--reground` enable a single remedy while `--apply-structural` enables both, and that `--reground-rebaseline` makes an applied re-ground also write a re-baseline seed (still needing `--include-info` to surface the re-ground finding — visibility and apply are independent gates).
- **Check the ToC** if you add or rename any heading; the "Carve a spinning region" heading already exists, so a body edit alone needs no ToC change.

**Do not add the generated `docs/cli/*.md` reference files to this step.** Those were regenerated by steps 2/4/6 as part of their own file set; this step touches only the three hand-authored docs in its file list.

## Tests

### Verification (non-code step)

This step changes no production code. Verify the artifacts by inspection and grep:

- `grep -n '#70' BACKLOG.md` — every hit that describes arm status shows the three arms shipped and code-reveals-a-split remaining; no hit still lists a shipped arm as "remaining".
- Confirm #70's entry block is still present (not deleted) and carries a dated SHIPPED note naming `structural-remedy-convenience-arms` and the new flags.
- `grep -n -- '--through' CLAUDE.md RUNBOOK.md` — the `--through M` range form appears in both, confirming no doc describes scope-out as single-step-only.
- `grep -n -- '--merge\|--reground\|--reground-rebaseline\|--apply-scope-out' CLAUDE.md RUNBOOK.md` — the per-remedy flags, the re-baseline flag, and the multi-region actuation are named.
- Cross-check every flag/symbol named in the edited prose against a HEAD grep of the source (`plan_tool/cli/scope_out_cmd.py`, `plan_tool/cli/convergence_cmd.py`, `plan_tool/cli/review_cmd.py`, `plan_tool/reground.py`) — every cited flag resolves to a real argparse dest or symbol.
- Run `python -m plan_tool.cli_reference --write` **only if** a doc edit implies a generated-doc change; this step should not need it, and `tests/cli/test_cli_reference.py` must stay green either way.
- `plan-tool validate` (the no-Claude capability-catalog check) still passes — no CAPABILITIES/MISSION drift introduced by the doc edits.

## Acceptance criteria

- `grep -n '#70' BACKLOG.md` returns the entry with the multi-step carve, per-remedy walk flags, and re-ground re-baseline arms marked shipped (naming plan slug `structural-remedy-convenience-arms` and the CLI flags), and the code-reveals-a-split producer still listed as remaining.
- #70's entry block is present, not deleted; the T2 tier line, the readiness-lens concrete list, the "Next concrete pick" line, and the recommended-execution-order line no longer name any shipped arm as remaining.
- `CLAUDE.md`'s "Structural remedy vocabulary" and "Convergence diagnostic" paragraphs describe the `--through M` range carve and the multi-region `FORK_SCOPE_OUT` actuation; the "Granularity advisor" paragraph names `--merge` / `--reground` / `--reground-rebaseline`.
- `RUNBOOK.md`'s four-remedies model, scope-out walkthrough, and walk-dispatch item all describe the range carve, the per-remedy flags, and the re-baseline disposition; the scope-out example block includes a `--through` command.
- Every CLI flag and symbol named in the edited docs resolves to a real dest/symbol at HEAD.
- `tests/cli/test_cli_reference.py` and `plan-tool validate` still pass.

## References

- `docs/implementation-plans/plan-details/structural-remedy-convenience-arms/02-contiguous-range-carve-scope-out.md` — the `--through M` range carve this step documents; source of truth for the scope-out flag names to grep before writing.
- `docs/implementation-plans/plan-details/structural-remedy-convenience-arms/03-make-convergence-actuate-multi-region.md` — the multi-region `FORK_SCOPE_OUT` actuation and `--apply-scope-out` range path this step describes.
- `docs/implementation-plans/plan-details/structural-remedy-convenience-arms/04-per-remedy-merge-reground-opt-flags.md` — the per-remedy `--merge` / `--reground` walk flags this step names as shipped.
- `docs/implementation-plans/plan-details/structural-remedy-convenience-arms/06-wire-re-ground-re-baseline-disposition.md` — the `--reground-rebaseline` re-baseline disposition flag this step documents.
- `plan_tool/cli/scope_out_cmd.py`, `plan_tool/cli/convergence_cmd.py`, `plan_tool/cli/review_cmd.py`, `plan_tool/reground.py` — the source files to grep at HEAD to confirm every flag/symbol named in the edited docs resolves before marking an arm shipped.

## Deferred

- **Code-reveals-a-split detection producer** — the one remaining #70 arm; a new detection with its own design, tracked in a sibling plan. This step leaves it listed in #70 and does not build or document a producer for it.
- **Regenerating `docs/cli/*.md`** — the generated per-subcommand flag reference is owned by the flag-adding steps (2, 4, 6), not this docs step; no `docs/cli/` file is in this step's file set.
- **Consolidating the three `create --from-existing` seed renderers** — `scope_out.render_carved_seed`, `annotate_render.render_create_seed`, and `reground.render_rebaseline_seed` still mirror rather than share one shape; a reconcile-owned refactor, not a doc change here.
- **MISSION.md / CAPABILITIES.md edits** — these arms extend already-cataloged surfaces (scope-out, reconcile walk, reground bridge); no new capability is added, so those catalogs need no change beyond the `plan-tool validate` sanity check.
