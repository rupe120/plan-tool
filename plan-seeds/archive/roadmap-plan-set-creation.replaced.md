> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-plan-set-creation.md`.
> Preserved here for history; do not edit.

# Derive the implementation plan set from accepted roadmap artifacts

## Outcome

An explicit opt-in roadmap-to-plan-set authoring route reads one pinned accepted roadmap artifact bundle and the current repository, derives a dependency-ordered set of bounded implementation plans, and authors their base plans through existing create machinery. The set retains accepted scope and source attribution while allowing several implementation slices beneath one roadmap row when necessary. A saved set record names the source version, derived members, responsibility assignments, dependencies and unresolved prerequisites; it is an inspectable authoring record, not certification of semantic completeness.

## In scope

Whole-set derivation before individual plan authoring; an explicit CLI entry through the existing authoring command group; accepted-head loading; a small persisted derived-set record and its source-bound seeds; serial reuse of existing create, registration and native logging seams; preservation of shared producer/consumer obligations and executable integration/acceptance ownership in generated content; documentation and focused tests; an isolated Integration comparison of raw tool output before session repairs.

## Out of scope

No application implementation or execution in Integration, deployments, provider probes, publication, or manual Integration restructuring as the feature deliverable. No accepted roadmap mutation, new roadmap stage, approval lifecycle, source migration or replacement of accepted seed-state ownership. No cross-plan audit command (#462), shared-context admission system (#493), prerequisite status projection (#494), automatic completeness certification, semantic quality gate, coverage score, plan/step size cap, target plan count or automatic approval. No changes to completeness blocking predicates, exit-code conventions, run scheduling, Jira export or the existing single-plan create behavior. No concurrent authoring or shared-state merge machinery.

## Allowed behavior changes

Only an explicitly selected whole-set authoring route may derive several implementation plans beneath accepted roadmap rows and persist its own source-bound membership record and seeds. Existing roadmap materialization remains one-row scoped and existing create stays single-plan scoped. New output may show declared obligations, owners, dependencies and unknown prerequisites for review. Structural validation may reject malformed identities, invalid source references, unsafe paths, cycles and conflicting output targets; it must not claim to validate semantic coverage or implementation granularity.

## Allowed reorganization

None by default. Reuse accepted-version readers, authoring invokers and create orchestration. A small dedicated orchestrator and artifact leaf may own the new set boundary where existing per-row materialization cannot represent it; do not refactor unrelated roadmap or create flows.

## Testing

Hermetic tests prove the route reads one selected accepted version, supplies the complete artifact bundle and repository grounding to set derivation, validates structural output, carries each slice’s source/owner/dependency content into its seed and create input, and registers only its actual authored plans. Cover one row producing several ordered slices, several rows sharing a necessary producer, retained integration and live-acceptance responsibilities, unknown prerequisites, source drift, existing destinations, partial failure and safe retry without overwriting unrelated or completed work. Existing one-row seed materialization and ordinary create keep their contracts. Run the changed tool and baseline against equivalent isolated Integration inputs with the same model, source version and declared context; retain raw outputs and session corrections separately. Review uncovered obligations, overly broad routes, dependency/ownership gaps and acceptance dilution against a frozen witnessed-gap corpus. A greater plan count or a clean audit is not evidence of improvement by itself.

## Stop / defer

Surface an accepted-scope or settled-decision conflict instead of broadening the roadmap. A derived implementation slice is not a new accepted roadmap row. Missing provider or owner evidence remains an explicit prerequisite; do not invent mechanisms that depend on its unknown result. If the smallest whole-set route requires a new approval/source-authority system or changes existing execution policy, stop and propose separately scoped work. File unrelated defects in BUG_BACKLOG.md and forward-looking work in BACKLOG.md. Keep #462/#493/#494 independently gated.

## Architecture

Treat accepted roadmap rows as scope/provenance anchors and derive the implementation breakdown across the complete bundle before authoring individual plans. Keep logical components distinct from implementation routes. Split cohesive work when its producer, consumer integration or acceptance responsibilities require independently bounded, dependency-ordered routes; do not split merely by directory or inflate the plan count. Assign shared implementation ownership once and identify its consumers. An explicit source prohibition remains binding and conflicts are surfaced, not reinterpreted.

The saved set record binds the selected source version, derived member identities and their roadmap-row attribution, ordered dependencies and actual authored destinations. Preserve declared obligations and unresolved evidence in generated content; structural code checks identities and relationships only. Existing per-row seed state remains untouched. A failed or interrupted serial authoring run retains completed outputs, reports uncompleted members, and cannot silently overwrite unrelated or previously authored plans on retry. Recheck source identity before further authoring after drift; do not silently switch to a newer accepted head.

Reuse existing per-plan create for base-plan authoring, with complete compact set/source/ownership context delivered through seeds and References. Detail and completeness-audit remain their existing stages. The new route must not manufacture passing runtime evidence or mark a set semantically complete. A written procedure does not discharge an accepted live-demonstration outcome: generated plans must assign the eventual observed proof to an executable route whose completion requires that evidence. This session authors tool plans only; that restriction must not narrow what the generated plans eventually implement or verify.

## Risks

- Confusing accepted roadmap rows with implementation plan identities can either forbid useful refinement or silently change accepted scope; keep the source relationship explicit.
- Local per-plan success can hide an absent shared producer or acceptance route; whole-set context must be delivered before individual authoring rather than inferred from a final count.
- The existing Integration replay includes retrospective evidence and session corrections, so it is a failure corpus, not a matched efficiency result. New comparisons require equivalent inputs and separately retained raw output.

## Acceptance criteria

One explicit opt-in invocation derives and authors a source-bound implementation set from the complete accepted roadmap bundle. Structural validation and serial retry preserve source identity, dependencies, completed members and unrelated project files. Generated content assigns shared producers, consumer integration and eventual acceptance responsibilities, with unknown evidence explicit. Existing single-plan and roadmap-row authoring remain compatible. The isolated comparison records raw output and judged gap coverage without claiming semantic certification or savings from one sample.

Source entry: BACKLOG #496. Update the originating backlog when this work ships: authoring alone retains a plan-authored entry; remove it only after full shipment, keeping any deferred work explicit.

## Scope guardrails

Preserve the exact Outcome and all seven scope fields from BACKLOG #496 above. The target is creation of the implementation plan set from the roadmap artifact bundle, not repair of Integration or a new audit product. Machine enforcement covers structural state only; semantic completeness and appropriate granularity remain judged content. Do not add scores, fixed plan counts, semantic gates, acceptance weakening, automatic approval, source mutation, live application execution, provider probes, or cross-plan-audit/status/shared-context features.

## References

- BACKLOG.md — #496 owns this effort and its scope contract; #462, #493 and #494 remain separate.
- MISSION.md — deterministically driven non-determinism and downstream impact.
- ROADMAP_FORMAT.md — accepted-head authority, component-to-plan dispositions and seed provenance.
- plan_tool/prompts/roadmap-seed.md — currently authors only one selected accepted row and forbids changing the plan mapping.
- plan_tool/roadmap.py:materialize_plan_seed — owns per-row seed materialization; do not overload its accepted-row state.
- plan_tool/roadmap_seed_manifest.py and plan_tool/roadmap_seed_state.py — current accepted-row membership/lifecycle ownership.
- plan_tool/cli/authoring.py:cmd_create and plan_tool/create.py:create_plan — existing individual authoring boundary and manifest integration.
- plan_tool/prompts/distill-seed.md — currently prefers a single plan for a large cohesive effort; unrelated split suggestions do not supply whole-set derivation.
- docs/explanations/roadmap-plan-handoff.md — existing prose/reference input delivery works with session verification; it does not establish whole-set decomposition quality.
- docs/evidence/roadmap-plan-set-benchmark.md — frozen Integration source, witnessed gaps, generated artifacts, intervention limits and tool-instrument observations.
- SEED_FORMAT.md and integrations/shared/DIRECTIVES.md — seed-altitude review and the bare/detail gates.
