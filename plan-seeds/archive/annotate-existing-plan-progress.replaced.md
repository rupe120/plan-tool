> **Replaced**: this file has been superseded by `docs/implementation-plans/2-annotate-plan-implementation-status.md`.
> Preserved here for history; do not edit.

# Plan seed: `plan-tool annotate <plan-file>` — annotate an existing plan with implementation status to seed the next plan

This file is a `plan-tool create` input. Use it via:

```
plan-tool create annotate-existing-plan-progress --iterate -y \
  --from-existing plan-seeds/annotate-existing-plan-progress.md \
  --output-dir docs/implementation-plans
```

It is **not** itself a plan — `plan-tool create` consumes the prose
below and proposes a step decomposition; the author then runs
`plan-tool detail --iterate` per step. Implements BACKLOG.md item
**#47**.

---

## Goal

Add a `plan-tool annotate <plan-file>` command that takes an existing
implementation-plan (or rough notes) file, compares it against the
current codebase, and emits **two artifacts from one ingestion + one
comparison**:

- **A — the annotated report** (`<name>.annotated.md`): the original
  preserved verbatim with section-by-section status blocks marking **what
  has been implemented and how** (concrete code references) and **what has
  not**, plus a coverage summary. Lossless, human-facing, the audit
  trail. **Never distilled.**
- **B — the create seed** (`<name>.seed.md`): a separate, purpose-built
  compact brief whose scope is the carryover (NOT-IMPLEMENTED / PARTIAL)
  work, with IMPLEMENTED items carried as done-context so they aren't
  re-planned. This is the create-ready file: `create --from-existing
  <name>.seed.md` produces the *next* plan.

The seed is a **second renderer over the same classification result**,
not a distill pass over the report — annotate already holds the
per-section judgement, so it renders the compact carryover brief directly.
Distill stays a no-op safety net, not a load-bearing step.

Two non-negotiable properties:

1. **Reuse the existing `--from-existing` *reader*** — do not invent a
   new file reader/parser. `read_existing_description` already reads
   arbitrary files as prose with no size limit and no format requirement;
   `annotate` ingests through it so any file `create --from-existing`
   accepts, `annotate` accepts. This is the reader only — the lossy
   distill *output* step is **not** reused (see below).
2. **Lose no information from the original.** The report is purely
   additive — original headings and prose are preserved verbatim, status
   notes are inserted around them, and provenance pointers tie the
   artifacts together. The author always has a clear trail: original plan
   → annotated report → create seed → next plan.

## Compare to the existing from-existing logic (what to reuse, verbatim)

Verified anchors — the new command composes these rather than
duplicating them:

1. **Ingestion.** `read_existing_description(path)`
   (`plan_tool/create.py:482`) reads the file in full as prose, with
   **no canonical-format requirement and no size limit**. This is the
   single reader `annotate` reuses — it is why a separate "tolerant
   parser" is unnecessary: the file never has to be valid plan
   frontmatter to be ingested.
2. **Oversize/free-form gate (downstream, not in `annotate`).**
   `propose_distilled_seed_from_claude` (`create.py:2827`) is the distill
   first-pass `create` runs on a free-form or oversize seed — and it is
   **lossy by design** ("reorganizes the raw seed into a compact canonical
   body"). `annotate` does **not** route either artifact through it: the
   report must stay verbatim, and the seed is already rendered compact
   from the classification. The gate remains where it is — when the author
   later runs `create --from-existing <name>.seed.md`, a compact seed
   passes through it as a no-op (and a genuinely multi-effort carryover
   still surfaces `create`'s split proposal at that point).
3. **Preserve-original + lineage.** `archive_existing_source`
   (`create.py:514`) already moves a superseded source into `archive/`
   and **prepends a one-line notice pointing at the successor**. This is
   the exact "don't discard the original / clear path forward" pattern —
   `annotate` reuses (or mirrors) it so the original is retained with a
   pointer to the annotated artifact, and the annotated artifact points
   at the original.
4. **Code-grounding helpers.** `extract_file_path_candidates`
   (`create.py:456`) + `find_umbrella_root` (`locator.py`) already pull
   the file references out of a seed and resolve the owning repo —
   `annotate` reuses them to decide *which code* to compare the plan
   against.
5. **The implemented-vs-spec comparison itself.** `verify_plan`
   (`plan_tool/launcher.py:2425`) — the `reconcile-plan --rollup`
   engine — already judges per-step whether code satisfies a spec.
   `annotate` reuses that judgement style for the "implemented and how"
   determination; it does **not** add a second comparison engine. The
   difference is purely the output: `annotate` emits additive markdown
   annotations + a create-ready seed, not plan/detail mutations or a
   pass/warn/fail rollup.

## Design decisions to lock early (do not relitigate downstream)

- **Two new files, never an in-place edit.** Bare `annotate <file>`
  writes the report (`<name>.annotated.md`) and the seed
  (`<name>.seed.md`) beside the original (override with `--output-dir` /
  `--report` / `--seed`). The original is never modified; if `--archive`
  is passed, the original is moved via the `archive_existing_source`
  pattern with a notice pointing at the report.

- **The report is additive and section-scoped.** Original content is
  copied through verbatim. Under each meaningful section the command
  inserts a status block, e.g.:
  - `> **IMPLEMENTED** — `plan_tool/foo.py:120-160` (`do_thing`); matches the spec.`
  - `> **PARTIAL** — table exists (`schema.py:40`) but the resolver in step 6 is missing.`
  - `> **NOT IMPLEMENTED** — no code found; carries into the next plan.`
  A top-of-file summary lists overall coverage and the carryover scope.
  The report is never distilled — verbatim preservation is asserted in
  tests.

- **The seed is rendered directly from the classification.** It is a
  compact, create-ready brief — NOT-IMPLEMENTED / PARTIAL items as the
  scope, IMPLEMENTED items as a short done-context block, a pointer back
  to the report. It is **not** produced by distilling the report; it is a
  second renderer over the same per-section judgement the report uses. It
  must round-trip: `create --from-existing <name>.seed.md` produces a plan
  whose scope is the carryover. Verify this round-trip in tests.

- **Provenance is explicit and chained.** original → report → seed → next
  plan. The report records the original's path (and, if resolvable, the
  commit/state compared against); the seed records the report's path; the
  original (when `--archive`d) records the report's path. Lineage is on
  disk, not implied.

- **Read-only by default.** Bare `annotate <file>` writes only the two
  new artifacts and prints a coverage summary. `--archive` is the only
  mutation of the original and is opt-in.

## Scope of work

1. **`annotate` orchestrator + thin CLI handler.** New `cli/` handler
   wiring args (`<plan-file>`, `--output`, `--archive`, the iterate
   flags) to a new top-level orchestrator. Resolve the target via the
   per-project discovery model; ingest via `read_existing_description`.

2. **Code-grounded annotation pass.** Build the comparison input from
   the ingested prose + the repo files resolved by
   `extract_file_path_candidates`/`find_umbrella_root`; run the
   `verify_plan`-style judgement to classify each section
   IMPLEMENTED / PARTIAL / NOT-IMPLEMENTED with a concrete "how"
   (file:line, symbol). Claude seam defaults to the real shell invoker
   and must be overridable in tests (per the invoker-seam rule).

3. **Report renderer (additive).** Emit `<name>.annotated.md`: original
   verbatim + inserted status blocks + top-of-file coverage summary +
   provenance to the original. Guarantee no original line is dropped or
   reworded (assert in tests). Never distilled.

4. **Seed renderer (direct) + round-trip.** From the same classification
   result, render `<name>.seed.md`: carryover scope + done-context for
   IMPLEMENTED + a pointer to the report. Then verify the round-trip —
   `create --from-existing <name>.seed.md` is accepted and the resulting
   plan's scope is the carryover items. The seed is compact enough that
   `create`'s distill gate is a no-op; do not run the seed through distill
   inside `annotate`.

5. **Original preservation / `--archive`.** Reuse
   `archive_existing_source` (or its notice-prepending helper) so the
   original is retained with a pointer to the report when `--archive` is
   set; untouched otherwise.

6. **Docs.** RUNBOOK.md walkthrough (old plan + current code → report +
   seed → next plan) and a README command-list entry. State plainly that
   `annotate` reuses the from-existing *reader* and the `verify_plan`
   comparison, renders report and seed from one classification, and does
   **not** distill either artifact.

7. **Tests.** Unit: report renderer is strictly additive (original
   content fully preserved, never distilled); seed renderer emits the
   carryover scope + done-context; classification mapping; provenance
   fields on both files. Integration: drive `main(["annotate", ...])` over
   a temp plan + fixture code where some steps are implemented and some
   aren't, assert the report's status blocks are correct, then feed
   `<name>.seed.md` to `create --from-existing` (invoker stubbed) and
   assert the new plan's scope is the carryover set. Neutralize every
   claude seam per TESTING.md.

## Non-goals

- **No new file parser / no new comparison engine.** Ingestion reuses
  `read_existing_description`; the implemented-vs-spec judgement reuses
  the `verify_plan` (`reconcile-plan --rollup`) style. `annotate` adds
  only the two renderers (additive report + direct seed).
- **No distilling either artifact inside `annotate`.** The seed is
  rendered directly from the classification, not produced by running the
  report through `propose_distilled_seed_from_claude`. The distill gate
  stays where it lives, in `create`, and acts as a no-op on the already
  compact seed.
- **No in-place mutation of the original** beyond the opt-in `--archive`
  move (which preserves it with a lineage notice).
- **No manifest registration.** `annotate` produces a report and a seed
  file, not a registered plan; registration happens when the author runs
  `create` on the seed.
- **No portfolio/multi-plan sweep.** One plan file per invocation;
  per-plan `reconcile-plan --rollup` remains the live-plan progress view.
- **No cross-project enumeration.** Discovery stays scoped to the cwd's
  git tree per `locator.py`.

## Acceptance criteria (plan-level)

- `annotate <plan-file>` writes a report (`<name>.annotated.md`) whose
  every original line is present verbatim, with section status blocks
  added and a top-of-file coverage summary, plus a seed
  (`<name>.seed.md`).
- For a fixture where some steps are implemented in the repo and some
  are not, each section is classified IMPLEMENTED / PARTIAL /
  NOT-IMPLEMENTED with a concrete code reference for the implemented and
  partial cases.
- `create --from-existing <name>.seed.md` accepts the seed and produces a
  plan whose scope is the carryover (NOT-IMPLEMENTED / PARTIAL) items;
  IMPLEMENTED items are carried as done-context, not re-planned. The seed
  passes through `create`'s distill gate as a no-op (never distilled
  inside `annotate`).
- With `--archive`, the original is moved and annotated with a notice
  pointing at the report; without it the original is untouched.
- Provenance chains: report → original, seed → report; no information
  from the original is lost.
- Every claude seam is overridden in tests; no test spawns the real
  backend.

## Risks

- **Annotation accuracy depends on the code-grounding being complete.**
  If `extract_file_path_candidates` under-resolves the relevant files,
  sections may be misclassified NOT-IMPLEMENTED. Mitigation: allow the
  comparison to widen to the resolved repo root, and mark low-confidence
  classifications explicitly rather than asserting.
- **Round-trip drift — largely designed out.** Because the seed is
  rendered compact directly (not the report pushed through distill),
  there is no lossy second pass to mangle annotations. Residual risk: the
  seed renderer itself drops a carryover item. Mitigation: render the seed
  from the structured classification, and test the round-trip explicitly
  (step 4/7) — `create`'s distill should be a no-op on it.
- **Additive guarantee is easy to regress.** A report-renderer change
  could silently drop original content. Mitigation: a test that diffs
  original lines against the report and fails on any omission.
- **Overlap with `reconcile-plan`.** `reconcile` mutates a live plan to
  match code; `annotate` produces a forward-seed and never mutates the
  source plan. Keep the intents distinct in docs so users pick the right
  verb (live plan upkeep → reconcile; start the next iteration from an
  old plan + current code → annotate).
