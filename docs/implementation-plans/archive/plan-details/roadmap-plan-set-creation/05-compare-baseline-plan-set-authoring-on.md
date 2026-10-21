> **Withdrawn 2026-10-16** — Owner correction 2026-10-16: improve existing roadmap mapping to seeds to plans; the separate opt-in plan-set layer exceeds the requested scope. Replacement effort: roadmap-plan-derivation, BACKLOG #496.
> Preserved here for history; do not edit.

# Step 5 — Compare baseline and plan-set authoring on equivalent isolated Integration inputs

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Extend `docs/evidence/roadmap-plan-set-benchmark.md` with a matched comparison of baseline authoring and step 4’s opt-in plan-set route. Use equivalent isolated Integration inputs and preserve raw outputs before any session repairs. Review both outputs against the same frozen witnessed obligations, keeping source facts, reviewer judgments and interventions distinct. Completion produces inspectable evidence of improvements, remaining gaps and comparison limits without certifying semantic completeness.

## Table of Contents

- [Summary](#summary) — Deliverable and observable result.
- [Table of Contents](#table-of-contents) — Section navigation.
- [Why](#why) — Why the existing replay cannot establish improvement.
- [Input](#input) — Source identities, upstream output and evidence limits.
- [Files (creates vs edits)](#files-creates-vs-edits) — The evidence document to extend.
- [Implementation](#implementation) — Comparable inputs, raw-output preservation and review.
- [Tests](#tests) — Reviewer checks for this non-code step.
- [Acceptance criteria](#acceptance-criteria) — Checkable evidence requirements.
- [References](#references) — Relevant contracts and evidence.
- [Applicable guardrails](#applicable-guardrails) — Limits on the comparison.
- [Deferred](#deferred) — Separate work this comparison does not deliver.

## Why

`docs/evidence/roadmap-plan-set-benchmark.md:Reproduction identity` identifies a retrospective replay with added owner decisions and session corrections, so its authored plans cannot serve as a matched baseline. Its `Witnessed failures to retain` section supplies concrete obligations that a whole-set route needs to address, while `Comparison contract` requires equivalent inputs and raw-output review. A fresh comparison makes the new route’s contribution inspectable without mistaking session repairs, additional plans or clean individual audits for improvement.

## Input

- **Step 4’s output:** Use the landed opt-in authoring route and its reported results. Read its actual flags and output locations from `plan_tool/cli/authoring.py:register` and `cmd_create`; landed names take precedence over earlier detail proposals.
- **Frozen source identity:** Start from `docs/evidence/roadmap-plan-set-benchmark.md:Reproduction identity`. Verify access to the named Integration commit and the complete accepted roadmap store before running either arm.
- **Accepted content:** `plan_tool/roadmap_versions.py:load_accepted_version` selects accepted content; `ResolvedRoadmapVersion` carries the resolved bundle. Both arms must receive the same accepted version and artifact bytes, including ignored store members that Git alone does not preserve.
- **Review corpus:** Freeze the obligations from `docs/evidence/roadmap-plan-set-benchmark.md:Witnessed failures to retain` before inspecting new outputs. Keep later Integration evidence distinct from baseline implementation facts.
- **Evidence limits:** Real authoring runs demonstrate observed behavior on this input. They do not establish typical model performance, universal granularity rules or application feasibility.

## Files (creates vs edits)

- **New files:** None.
- **Existing files (edits only):**
  - `docs/evidence/roadmap-plan-set-benchmark.md` — Add the matched-run identities, procedure, retained-output inventory, obligation comparison, intervention record and qualified conclusions. Preserve the existing retrospective evidence and its limits.

## Implementation

- **Foundational logic: compare uncorrected authoring outputs under equivalent inputs.** The evidence must distinguish changes attributable to the route from differences in source content, model configuration or session assistance. Reject using the corrected retrospective replay as the baseline arm.

- **Declare the two routes before running them.** Use the existing accepted-row seed and individual-create route for the baseline, oriented by `plan_tool/roadmap.py:materialize_plan_seed` and `plan_tool/create.py:create_plan`. Use step 4’s whole-set route for the candidate. Record exact commands and tool commits; preserve each route’s native authoring behavior rather than manually forcing matching plan membership.

- **Establish equivalent isolated starting states.** Recommend independent disposable clones with separate Git and `.plan-tool` state. Record the Integration commit, accepted roadmap identity and member digests, model/backend identity, effective authoring options, supplied contextual files and their digests, and initial generated-output state for each arm.
  - Both arms must receive the same declared context and owner decisions.
  - Keep later evidence supplied as context explicitly labeled as retrospective knowledge.
  - If required inputs are unavailable or differ, record the mismatch and stop the matched comparison rather than inventing replacements.

- **Freeze a review checklist before generation.** Give each witnessed obligation a stable local label and source citation in the evidence document. Include the named corrections and acceptance-route weakness from `Witnessed failures to retain`. Keep these labels as review aids, not a persisted schema or automatic checker.

- **Capture raw output before session edits.** Preserve each arm’s generated seeds, base plans, refusals, failures and available native logs; retain the candidate’s saved set record as well. Record missing outputs explicitly. Tool-internal retries belong to the raw run; developer-directed corrections belong to a separate intervention record.

- **Keep retained evidence inspectable.** Within the declared evidence document, inventory exact retained locations and content digests, and include the excerpts needed to assess each comparison claim. Do not rely solely on transient `.tmp` paths or a statement that logs exist. This step adds no separately tracked evidence files or benchmark harness.

- **Review responsibilities rather than counts.** Recommend a table with one row per frozen obligation and columns for baseline evidence, candidate evidence, remaining uncertainty and reviewer explanation. For each arm, inspect:
  - The producer and its consumers.
  - Dependency order and ownership of shared work.
  - A bounded implementation route, including extensions to existing contracts.
  - Integration responsibility and eventual acceptance evidence.
  - Explicit unresolved prerequisites rather than invented provider behavior.

- **Preserve the execution acceptance contract.** Inspect whether generated plans retain required deployment or other live proof as eventual completion evidence. The comparison itself must not perform that execution or treat local/document checks as an equivalent substitute.

- **Separate input delivery from breakdown quality.** Track the References-replacement observation in `docs/evidence/roadmap-plan-set-benchmark.md:Witnessed failures to retain` independently. Record what context enters each invocation and what survives in generated artifacts; do not repair References before preserving raw plans or attribute missing context automatically to granularity.

- **State conclusions at the strength the evidence supports.** Cite concrete raw artifacts for improvements and regressions. Record unknowns, reviewer disagreement, incomplete runs and unequal interventions. Plan counts and available timing or usage observations may describe the run, but must not become scores, targets or proof of efficiency.

- **Reuse adjacent evidence unchanged.** `docs/evidence/roadmap-aidlc-intake-comparison-20260916.md:Frozen corpus and method` provides an isolation/provenance example. `docs/evidence/integration-roadmap-to-plan-handoff.md:Source identity` separates observations from supported claims. Neither document needs editing; this comparison’s procedure and conclusions remain in the declared file.

## Tests

This is a `non-code` step. The test-authoring gate does not apply: `plan_tool/launcher.py:_step_requires_test_authoring` limits it to `feature` and `refactor` steps. No matching unit-test module is required for this evidence document.

### Verification (non-code step)

1. **Equivalent inputs are demonstrated** — Compare both arms’ recorded source identities, bundle digests, context digests and model configuration; explain every difference.
2. **Raw output precedes repairs** — Check retained artifact digests and the intervention record against the cited raw excerpts.
3. **Every frozen obligation has evidence or an explicit unknown** — Check the review table against the frozen checklist, including acceptance dilution and References delivery.
4. **Claims remain bound to their sources** — Open the cited artifacts and verify that they support the producer, consumer, dependency and acceptance observations.
5. **Retained evidence remains usable** — Verify retained locations and digests; ensure the document includes the excerpts supporting its conclusions.
6. **Documentation references remain valid** — Check repo-relative links and symbolic anchors. Before renaming an existing heading, search for inbound links to its current anchor.
7. **Scope remains unchanged** — Review the diff and run records for application execution, source mutation, semantic scoring or new tooling outside the declared deliverable.

## Acceptance criteria

- The evidence document records a fresh baseline run and candidate run using equivalent isolated Integration inputs, the same selected accepted roadmap bundle, model and declared context.
- Exact tool identities, commands, effective options, input digests and retained-output locations make each arm identifiable.
- Raw seeds, base plans and failures are preserved before session repairs; candidate evidence also includes its saved set record.
- Every frozen witnessed obligation has a comparison entry citing raw evidence or naming what remains unknown.
- The comparison explicitly examines shared ownership, dependency order, bounded implementation routes and retained eventual acceptance requirements.
- References delivery and session interventions are recorded separately from breakdown judgments.
- Conclusions identify observed improvements and remaining gaps without using plan count or clean audits as semantic certification.
- The tracked change is limited to `docs/evidence/roadmap-plan-set-benchmark.md`.

## References

- [BACKLOG.md](../../../BACKLOG.md) — Read #496 for the governing scope and comparison requirement.
- [Benchmark evidence](../../../docs/evidence/roadmap-plan-set-benchmark.md) — Use its reproduction identity, witnessed failures and comparison contract.
- [ROADMAP_FORMAT.md](../../../ROADMAP_FORMAT.md) — Read accepted-head authority and accepted-row seed provenance.
- [Roadmap handoff explanation](../../../docs/explanations/roadmap-plan-handoff.md) — Read the existing input-delivery boundary.
- [Integration handoff evidence](../../../docs/evidence/integration-roadmap-to-plan-handoff.md) — Distinguish observations from claims about tool improvement.

## Applicable guardrails

- **The plan’s “Step intent”:** Judge raw authoring output before repairs; keep conclusions tied to witnessed gaps.
- **The plan’s “Scope guardrails”:** Keep the evidence document observational. Do not turn the review checklist into enforcement or certification.
- **The plan’s “Out of scope”:** Keep benchmark activity within authoring and inspection; follow the plan’s excluded-activity list when preparing and running both arms.
- **BACKLOG #496’s “Stop / defer”:** Surface source or settled-decision conflicts and missing prerequisite evidence instead of changing the accepted input to make the comparison succeed.

## Deferred

- **General benchmark automation in `plan_tool/bench.py` and `tests/test_bench.py`** — A reusable benchmark engine is separate work; this step records one focused comparison.
- **Changes to adjacent evidence documents** — Reuse their methods and limits without broadening this step’s file footprint.
- **Application execution and broader semantic validation** — Follow the plan’s scope fence; this evidence does not deliver those capabilities.
