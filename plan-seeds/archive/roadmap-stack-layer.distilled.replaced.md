> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-stack-layer.md`.
> Preserved here for history; do not edit.

## Overview

A roadmap records its technology stack as a distinct concern layer: a `stack` collection in `02-constraints.md` with one row per required concern (deployment platform, store engine, language/runtime), each holding a choice or an explicit `open`. The stack is shown to the reviewer in the first stage run's completion output, in the generated `INDEX.md`, and in every candidate review. That way no stack choice and no open stack question is accepted without being seen. The callout is a standing summary and never blocks approval. An existing roadmap gains its stack through the ordinary feedback and candidate lifecycle, never by regeneration. Source: BACKLOG.md #461.

## Problem statement

Stack facts have no single home today. Hosting rows in `02-constraints.md` record vendor-neutral categories with an optional compute `product`. These rows are identity-only: they are never decision anchors or prose-inventory rows, and they have no undecided value. Store rows in `03-components.md` carry an optional `product`. Language and runtime are recorded nowhere. The constraints prompt (`plan_tool/prompts/roadmap-constraints.md`) forbids inventing a vendor or a pending hosting decision, so a brief that explicitly says "not decided" has nowhere to put that fact.

Observed 2026-10-08 in Integration (`integration-aidlc-mvp`): the brief says "No AWS account or specific service is fixed yet" and names only "a relational store". The accepted roadmap:

- records `managed-containers` without a product;
- gives no trace that the vendor is open;
- introduces PostgreSQL, which the brief does not name;
- carries zero pending decisions.

The plan derived from that roadmap chose Python. The roadmap entered versioning when an older folder was enrolled by hand (2026-09-21). Neither hand enrollment nor a first stage run (which publishes the root version once all four stages pass) goes through candidate review. Candidate review's narrative evidence reports only removed ids still named in prose. So stack choices and open stack questions reach acceptance without the reviewer ever seeing them.

## Architecture

**The `stack` collection.** `02-constraints.md` gains a `stack` collection with one row per required concern: deployment platform, store engine, and language/runtime. Each row carries either a choice or an explicit `open`. Stack rows can be targeted by feedback, and a choice may be `pending`. The collection sits alongside the existing constraints rows (`ConstraintsArtifact`, `HostingRow`, `stage_row_collections`, `_STAGE_ROW_OPERATION_POLICIES` in `plan_tool/roadmap_artifacts.py`). It is deliberately not a fifth roadmap artifact: stack choices are constraints, and the four-member version layout runs through every roadmap surface (decided 2026-10-08).

**One source of truth.** Each stack fact has exactly one source of truth across the roadmap. How the existing hosting `product` and store `product` fields relate to the collection is decided in `create`, under that rule.

**Totality and version compatibility.** A totality gate sits next to `check_hosting_totality` in the constraints gate tuple (`plan_tool/roadmap_gates.py`). It refuses an artifact that is missing a required concern, accepts a concern recorded as `open`, and reports an unknown concern or a duplicate id. Totality binds a first stage run and any version that already carries the collection. An accepted version without the collection reads as "stack not recorded", never as an empty stack. A candidate in a lineage without the collection is not refused for that absence, so unrelated feedback on an existing roadmap keeps working until some candidate introduces the stack.

**Constraints-stage authoring.** The constraints prompt records chosen and open concerns. When the brief leaves a concern open, the prompt records `open` instead of inventing a choice. Loosening the prompt for stack concerns must not let the model invent a vendor the brief leaves open.

**Callouts.** The stack is shown in two places:

- The first stage run's completion output and the generated `INDEX.md` (`plan_tool/roadmap_index.py:write_roadmap_index`) list the full stack, with open and pending concerns listed separately.
- Every candidate review (`plan_tool/roadmap_candidate_review.py`, `plan_tool/roadmap_candidate_narrative.py`) shows the current stack and what that candidate adds, changes, or opens.

The callout is a standing summary, not a narrative-evidence defect class, and it never blocks approval.

**Seed rendering.** Seed materialization (#460) renders the stack collection alongside hosting and store rows.

**Documentation.** `ROADMAP_FORMAT.md` (the `02-constraints.md` schema, § "Hosting facets and values", § "Narrative review evidence", root-version publication) and `ROADMAP_FEEDBACK_FORMAT.md` (feedback targets and the candidate lifecycle) describe the collection.

**Backlog reconciliation.** While execution is pending, BACKLOG.md #461 is marked plan-authored. When the work ships, the plan reconciles that entry: it is removed only after full shipment, and any separately deferred follow-up is kept.

## Out of scope

- **Out of scope / Non-goals:** a fifth roadmap artifact — deliberately not built, since the four-member version layout runs through every roadmap surface and stack choices are constraints (decided 2026-10-08); stack concerns beyond the three named; a closed vendor or product vocabulary; a narrative-evidence defect class or any approval block on stack content; judging whether a choice is good; Integration's HTML review aid, which follows this work separately in Integration; regenerating or rewriting existing accepted versions.

## Risks

- Existing accepted versions lack the collection; reading them as an empty stack, or refusing their candidates for the absence, would break every current roadmap lineage.
- Hosting `product`, store `product`, and stack rows can state the same fact twice; without one source of truth they can disagree.
- The constraints prompt currently forbids pending hosting decisions; loosening it for stack concerns must not let the model invent a vendor the brief leaves open.
- Review callouts that grow into approval blocks would turn a summary into a gate on stack content.

## Testing

- Parse and gate tests for the `stack` collection: a first-run constraints artifact missing a required concern is refused, a concern recorded as `open` is accepted, and an unknown concern or duplicate id is reported.
- A parametrized test over the version-compatibility cases: a version without the collection reads as "stack not recorded", and an unrelated candidate in that lineage is not refused for the absence.
- Callout tests that assert keys rather than words: first-run output and `INDEX.md` list open and pending concerns separately; a candidate review shows the stack and the added, changed, or opened rows; a review callout never changes whether approval is blocked.
- A feedback round-trip test: a stack row is targeted by feedback and revised through a candidate.
- A Integration-brief replay under the invoker seam, never a real backend: the deployment platform is recorded as open.
- Existing hosting gate and candidate-review evidence tests stay green.

## Acceptance criteria

- **Verification:** a Integration-brief replay records the deployment platform as open and every required concern as chosen or open; first-run output and `INDEX.md` list open concerns separately; a candidate that opens, adds, or changes a stack row shows that delta in review; an accepted version without the collection reads and renders as "stack not recorded", and an unrelated candidate in that lineage is not refused for the absence; a stack row can be targeted by feedback and revised through a candidate; existing hosting gates and candidate-review evidence stay green.

## Deferred

- **Stop / defer:** surface a stack concern the collection cannot express or a conflict with an accepted hosting or store choice without inventing one; route unrelated defects separately.
