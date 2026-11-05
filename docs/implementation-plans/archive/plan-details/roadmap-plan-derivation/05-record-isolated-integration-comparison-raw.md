> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Record the isolated Integration comparison and reconcile BACKLOG #496

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Create `docs/evidence/roadmap-plan-derivation-comparison.md` with a matched baseline and candidate comparison of generated mappings, materialized seeds, and raw plans. Use the workflow verified by step 4 and preserve outputs before session-directed repairs. Separate mapping omissions from obligations lost during materialization or create, and record uncertainty without semantic scores. Update `BACKLOG.md` #496 according to verified shipment and any remaining work.

## Table of Contents

- [Summary](#summary) — Deliverables and observable result.
- [Table of Contents](#table-of-contents) — Section index.
- [Why](#why) — Why the existing replay needs a matched comparison.
- [Input](#input) — Benchmark identity and upstream contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — Bounded documentation changes.
- [Implementation](#implementation) — Isolation, evidence retention, comparison, and bookkeeping.
- [Tests](#tests) — Verification for this non-code step.
- [Acceptance criteria](#acceptance-criteria) — Observable completion requirements.
- [References](#references) — Source contracts and comparison guidance.
- [Applicable guardrails](#applicable-guardrails) — Boundaries on the exercise.
- [Deferred](#deferred) — Work outside this comparison.

## Why

`docs/evidence/roadmap-plan-set-benchmark.md`, under “Reproduction identity” and “Witnessed failures to retain,” identifies useful Integration cases but also documents retrospective context, session-directed repairs, and lost local References. Those inputs do not establish which gaps originate in mapping and which appear during later handoffs. A matched comparison makes the focused changes inspectable without attributing every difference to granularity or treating repaired plans as raw generation evidence.

## Input

- **Step 4 output:** Use the verified existing handoffs and accepted-head boundaries after steps 1–4 land. Read the landed implementation; its names and behavior take precedence over sibling detail proposals.
- **Pinned benchmark:** Use `docs/evidence/roadmap-plan-set-benchmark.md:Reproduction identity` for the Integration repository baseline, accepted roadmap identity, later evidence source, and tool baseline. Verify available bytes against these identities rather than assuming temporary directories still exist.
- **Comparison contract:** Follow `docs/evidence/roadmap-plan-set-benchmark.md:Comparison contract`. The accepted store includes ignored members; a Git checkout alone does not prove the source is complete.
- **Authority:** `plan_tool/roadmap.py:load_accepted_roadmap_artifacts` supplies accepted content, and `plan_tool/roadmap.py:_materialize_plan_seed` consumes it. `plan_tool/create.py:select_file_backed_source` owns source selection for ordinary create.
- **Verification limits:** This exercise supplies judged evidence about the recorded runs. It does not establish a model success rate, semantic certification, or measured efficiency.

## Files (creates vs edits)

- **New files:**
  - `docs/evidence/roadmap-plan-derivation-comparison.md` — Record comparison setup, source identities, raw-output evidence, obligation traces, interventions, limitations, and conclusions.
- **Existing files (edits only):**
  - `BACKLOG.md` — Reconcile #496 against delivered work and the recorded comparison; retain explicit pending scope when shipment is incomplete.

## Implementation

- **Foundational logic: trace each witnessed obligation through equivalent isolated generation runs.** Use a human-reviewed evidence record rather than a new comparison runner or semantic checker. Reuse existing roadmap, materialization, and create routes unchanged.

- **Fix the comparison inputs before generating output.** Record the exact baseline and candidate tool commits, Integration repository commit, model/backend identities, invocation options, concept, upstream artifact digests, and declared contextual evidence. Hold these inputs equivalent except for the intended tool changes. Treat later Integration evidence as declared retrospective context; do not silently present it as baseline code.

- **Keep each arm independent.** Use separate full clones with independent Git and `.plan-tool` state. Keep generated plans and reports outside the development plan’s report history. Scratch outputs belong to the experiment, not the repository’s committed deliverables; the step’s repository changes remain limited to its declared files.

- **Preserve the frozen accepted source.** For stage-four generation, use fresh isolated first-run stores with equivalent concept and upstream inputs. Follow the existing first-run and accepted-version procedures in `docs/how-to/roadmap.md` and `ROADMAP_FORMAT.md`; do not overwrite the benchmark head or bypass review to make a generated mapping usable.

- **Distinguish two questions in the record.** Compare fresh mappings to examine stage-four guidance. Also use the same frozen accepted mapping in both arms to examine materialization and create retention independently of mapping changes. Label which source mapping each seed and plan consumes; do not attribute downstream differences to handoff changes when the source mappings differ.

- **Capture raw output before repairs.** Retain mappings, seeds, and first published base plans, along with refusals, failed attempts, and any automatic iterations. Record exact commands and intervention points. If review requires a change before downstream generation can proceed, preserve the original and label the changed input separately.

- **Make evidence survive scratch cleanup.** Include an artifact inventory with identities and digests, plus the excerpts needed to support each judgment in `docs/evidence/roadmap-plan-derivation-comparison.md`. Keep raw outputs available at identified locations for review. A temporary path or digest alone is insufficient evidence for a claim once the underlying bytes disappear.

- **Compare obligations by responsibility.** Use a table linking each witnessed obligation to its source, baseline and candidate mapping, seed, and raw plan. Record its producer, consumers, dependency order, bounded implementation route, and eventual acceptance evidence. Include the cases identified under `docs/evidence/roadmap-plan-set-benchmark.md:Witnessed failures to retain`, including local References retention.

- **Locate the first visible gap without inventing causation.** Distinguish an obligation absent from supplied context, missing from mapping, dropped during materialization, or lost during create. Cite artifact identifiers and supporting excerpts. Record ambiguous attribution, unavailable evidence, and reviewer disagreement explicitly.

- **Preserve eventual acceptance requirements.** Inspect whether generated plans retain the required observed proof even though this exercise stops at drafting. Local document checks must not substitute for eventual deployment or runtime evidence. Do not implement Integration or execute providers to settle that question here.

- **Report unfavorable results plainly.** Describe retained obligations, remaining gaps, and unmatched conditions. Do not use plan counts, file counts, or clean per-plan audits as evidence that the plan set is complete. If matching inputs or required source artifacts are unavailable, record the blocked comparison rather than substituting repaired replay output.

- **Reconcile shipment separately from experiment outcome.** Apply `docs/TRACKING.md:The life of an item` to `BACKLOG.md` #496. Remove the entry only after its full in-scope work ships; otherwise retain it with accurate pending scope and a link to the evidence. A drafted detail, completed run, or favorable sample alone must not trigger removal. Preserve follow-up tracking without absorbing the neighboring efforts named by the plan’s fence.

## Tests

No test file changes belong to this step. `plan_tool/launcher.py:_step_requires_test_authoring` exempts `non-code` steps from the test-authoring gate. Existing regression coverage in `tests/test_roadmap.py` and `tests/test_create.py` supports steps 1–4; it does not replace this comparison.

### Verification (non-code step)

1. **Matched-input review** — Verify recorded commits, model settings, source digests, declared evidence, and intentional differences for both arms.
2. **Isolation and authority review** — Verify independent stores, unchanged frozen benchmark content, and use of existing accepted-head routes.
3. **Raw-output review** — Confirm retained mappings, seeds, plans, refusals, and intervention records precede session-directed repairs.
4. **Obligation-trace review** — Check each comparison judgment against cited source and generated excerpts, including missing or uncertain evidence.
5. **Acceptance-preservation review** — Confirm drafting restrictions do not weaken generated plans’ eventual observed-proof requirements.
6. **Documentation review** — Check links, cited symbols, artifact inventory, and the distinction between observation and inference.
7. **Backlog review** — Confirm #496’s disposition matches actual shipment and that unresolved scope remains explicitly tracked.

## Acceptance criteria

- Explicitly assess plan-level granularity against the overly high-level Integration baseline: identify broad responsibilities split into cohesive implementation routes, the resulting seed/plan boundaries and any remaining overly broad routes. Context retention or extra steps alone do not demonstrate improvement. A greater plan count is useful only where the source responsibilities justify those boundaries.

- `docs/evidence/roadmap-plan-derivation-comparison.md` records exact baseline and candidate identities, equivalent inputs, declared evidence, invocation settings, and all unmatched conditions.
- The record distinguishes fresh mapping comparisons from same-accepted-mapping handoff comparisons.
- Raw mappings, seeds, and base plans remain inspectable before repairs; refusals and interventions are recorded rather than excluded.
- Every witnessed obligation has a source-backed comparison covering producer, consumers, ordering, implementation responsibility, and eventual acceptance evidence.
- Claims remain supported by durable excerpts and identified artifacts; unknowns and reviewer disagreement remain explicit.
- The frozen accepted benchmark source and the development plan’s report history remain unchanged.
- The record states the comparison’s limits and makes no semantic-certification or efficiency claim from counts, clean audits, or one sample.
- `BACKLOG.md` #496 reflects verified shipment, links to the evidence while retained, and preserves any remaining scope.
- The repository diff contains only the declared evidence document and backlog reconciliation.

## References

- [Benchmark evidence](../../../evidence/roadmap-plan-set-benchmark.md) — Read “Reproduction identity,” “Witnessed failures to retain,” and “Comparison contract” for the pinned inputs and comparison limits.
- [Roadmap contract](../../../../ROADMAP_FORMAT.md) — Follow accepted-version authority and existing mapping dispositions.
- [Roadmap workflow](../../../how-to/roadmap.md) — Use the existing staged generation, seed handoffs, and review routes.
- [Backlog tracking](../../../TRACKING.md) — Apply “The life of an item” and “Scope contract and anti-creep” when reconciling #496.
- [Layering measurement](../../../evidence/roadmap-layering-measurement.md) — Read “How to read this result” before drawing conclusions from a limited comparison.
- [Documentation style](../../../reference/documentation-style.md) — Structure provenance and comparison tables for review.

## Applicable guardrails

- **The plan’s “Scope guardrails,” existing workflow:** Exercise existing commands; this evidence step must not introduce production orchestration or change accepted-row ownership.
- **The plan’s “Scope guardrails,” judgment boundary:** Keep comparison judgments in the evidence document without adding machine assessments of semantic quality.
- **The plan’s “Out of scope,” execution boundary:** Stop at generated planning artifacts and inspection of their acceptance requirements.
- **The plan’s “Out of scope,” neighboring efforts:** Record limitations without turning this comparison into the separately excluded capabilities.
- **The plan’s “Acceptance criteria,” backlog bookkeeping:** Tie #496’s disposition to shipment rather than authoring progress or a favorable sample.

## Deferred

- General model reliability and efficiency measurement — This matched Integration exercise cannot establish population-level results.
- Application execution and observed deployment proof — Generated plans retain these requirements; performing them lies outside this tool-development step.
- Separate comparison infrastructure or shared-authority changes — Reuse existing routes; surface any need for broader machinery through the plan’s existing stop/defer process.
