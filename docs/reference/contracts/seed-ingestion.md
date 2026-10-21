# Seed-to-`create` ingestion contract

This is the detailed contract for file-backed `create --from-existing` input
and matching `create_plan(..., from_existing_path=...)` calls. It defines the
source preflights, selected routes, authority boundaries, and terminal
lifecycle. [`CREATE_FROM_EXISTING_FLOW.md`](../../how-to/pipeline/create-from-existing.md)
shows the operator flow; it does not duplicate this table.

## Decisions

1. File-backed intake selects `seed_body` whenever it is present, including
   when it is empty; otherwise it selects `from_description`. A description
   cannot mask an empty provenance source.
2. Unmatched-fence protection and
   `plan_tool/create.py:validate_from_existing_seed` are distinct preflight
   refusals. The latter requires exactly one usable `## References` section
   and rejects a missing, duplicate, empty, or placeholder section. Both stop
   before slug resolution, a run record, routing checkpoint, model call, plan,
   or manifest entry. They are not selected routes.
3. The other canonical body headings are not universal preflight
   requirements. Missing, duplicate, empty, or placeholder body headings
   select preparation instead of rejecting the source.
4. Direct readiness is a shape decision, not a byte threshold: it requires
   exactly one non-empty, non-placeholder instance of each canonical body
   heading. Strict canonical `## Steps` remains the independent deterministic
   step-reader rule.
5. A direct-ready source receives a raw-source split assessment. Its
   single-plan result selects `direct`; a multi-plan result selects `split`;
   an invalid assessment selects `refused`. Invalid direct assessment never
   publishes raw text, enters preparation, or creates another public route.
6. Every non-direct file-backed source enters one preparation decision. It
   ends as `normalized`, `split`, or `refused`; bounded parser repair is an
   internal preparation action, not a route. Preparation cannot silently
   publish raw text or add a fallback route.
7. `create_plan` applies this same selected-source, route, and checkpoint
   contract without moving caller-owned source files. `cmd_create` alone owns
   clean route-specific archival.

## Section contract

| Source part | Direct treatment | Preparation treatment |
| --- | --- | --- |
| `## References` | Exactly one usable section is required before routing; its supplied content remains authoritative. | The same preflight applies; preparation cannot invent source evidence. |
| Eight canonical body H2s | Exactly one non-empty, non-placeholder occurrence of each selects direct readiness and retains its supplied body. | A missing, duplicate, empty, or placeholder heading selects preparation rather than a universal rejection. |
| `## Steps` | The strict canonical reader can lift steps without a proposal call. | The ordinary step proposal derives the graph when strict extraction cannot. |
| `## Outcome` and recognized guardrails | Preserve supplied context under their existing rules. | Preserve source-supported context; preparation does not invent a boundary or guardrail. |

The canonical body H2s are `Overview`, `Problem statement`, `Architecture`,
`Out of scope`, `Risks`, `Testing`, `Acceptance criteria`, and `Deferred`.
Canonical heading parsing ignores letter case and an optional closing ATX
sequence. #102 remains the separate semantic heading-alias proposal.

## Source authority

For a `direct` publication, the supplied raw canonical body and References
remain authoritative. The direct assessment is non-rewriting, and direct
publication bypasses generic post-write convergence. For a `normalized`
publication, source-materialized evidence-only fields remain authoritative.
Scope rendering, concept synchronization, and any applicable convergence
work preserve these protected ranges for that invocation. This does not bar a
later operator-directed audit from revising the published plan.

Preparation accepts only a usable normalized result. Its evidence-only body
fields materialize from source evidence; it does not invent risks, criteria,
tests, scope boundaries, or deferrals merely to complete a shape. An accepted
normalized result has the complete required canonical body and bypasses
generic body synthesis.

## Shipped route and lifecycle

The source/artifact column describes the CLI-only action. A public library
call returns its result while leaving its caller-owned source untouched.

| Outcome | Plan and manifest | Source, artifacts, and branch binding | Checkpoints and run record | Exit |
| --- | --- | --- | --- | --- |
| Unmatched-fence or References preflight refusal | Neither is written. | Raw source stays in place; no normalized artifact or collision-created branch cleanup is needed. | No routing checkpoint and no run record. | `2` |
| `direct` | One plan and manifest entry publish. | `cmd_create` archives the raw source chain only after clean finalization; it writes no normalized artifact. | Completed routing checkpoints are discarded; the run records `direct`. | `0` |
| `normalized`, clean finalization | One plan and manifest entry publish. | `cmd_create` materializes and archives the normalized artifact and archives the raw source chain only after clean finalization. | Completed preparation checkpoints are discarded; the run records `normalized`. | `0` |
| `normalized`, iteration incomplete | The published plan and manifest entry remain registered. | Raw source remains available; no normalized archive artifact is emitted. | Preparation and continuation checkpoints remain; the run records `iteration_incomplete`. Continue the registered plan with `plan-tool completeness-audit <slug> --iterate`, not a second create invocation. | `0` |
| `split` | Neither is written. | Raw source remains available for carving; `cmd_create` can save the `SplitProposal` worksheet. Any collision-created branch binding rolls back. | The versioned split result remains for retry; the run records `split`. | `0` |
| Post-preflight `refused` | Neither is written. | Raw source remains available; no normalized artifact remains. Any collision-created branch binding rolls back. | The terminal direct-assessment or preparation result is removed; the run records `refused` with its reason. | `2` |

`plan_tool/create.py:SplitProposal` and
`plan_tool/cli/authoring.py:_emit_split_proposal` make split a successful,
operator-visible no-plan result. The worksheet gives the next carving action;
it is not a hidden continuation as one plan.

## Compatibility and source maps

`--from-existing` follows this file-backed contract. Inline `--from` remains
a separate compatibility path: it has no References preflight and retains its
own legacy distill behavior. `--no-distill` is therefore not a file-backed
bypass.

| Concern | Owner |
| --- | --- |
| Selected source, intake, routes, preparation, and finalization | `plan_tool/create.py` (`select_file_backed_source`, `validate_from_existing_seed`, `FileBackedSourceRoute`, `SplitProposal`, `_prepare_create_plan`, `_finalize_create_plan`) |
| CLI preflight, route output, split worksheet, and archival | `plan_tool/cli/authoring.py` (`cmd_create`, `_emit_split_proposal`) |
| Route fixtures | `tests/test_create.py`, `tests/test_distill.py`, `tests/cli/test_authoring_cmds.py` |

Generated carryover sources may remain free-form. They need usable References
and then enter the selected preparation route when they are not direct-ready.
