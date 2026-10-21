> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-stack-layer.md`.
> Preserved here for history; do not edit.

# Roadmap stack layer

## Outcome

A roadmap records its technology stack as a distinct concern layer — each stack concern either chosen or explicitly open — and that layer is called out to the reviewer at first publish and in every candidate review, so a stack choice or an open stack question is never accepted unseen.

## Source

BACKLOG.md #461. Mark the entry plan-authored while execution is pending. The resulting plan must reconcile the originating backlog entry when the work ships; remove it only after full shipment, retaining any separately deferred follow-up.

## Architecture

Stack facts have no single home today. Hosting rows in `02-constraints.md` record vendor-neutral categories with an optional compute `product`, are identity-only (never decision anchors or prose-inventory rows), and have no undecided value; store rows in `03-components.md` carry an optional `product`; language and runtime are recorded nowhere. The constraints prompt forbids inventing a vendor or a pending hosting decision, so a brief's explicit "not decided" has nowhere to land.

Observed 2026-10-08 in Integration (`integration-aidlc-mvp`): the brief says "No AWS account or specific service is fixed yet" and names only "a relational store"; the accepted roadmap records `managed-containers` without a product, gives no trace that the vendor is open, introduces PostgreSQL, which the brief does not name, and carries zero pending decisions. The plan derived from it chose Python. That roadmap entered versioning by hand enrollment of an older folder (2026-09-21); neither enrollment nor a first stage run, which publishes the root version once all four stages pass, goes through candidate review; candidate review's narrative evidence reports only removed ids still named in prose.

A `stack` collection in `02-constraints.md` holds one row per required concern — deployment platform, store engine, and language/runtime — each carrying a choice or an explicit `open`. Stack rows are feedback-targetable, and a choice may be `pending`. Each stack fact has one source of truth across the roadmap; how existing hosting and store `product` fields relate to the collection is decided in `create`, under that rule. An accepted version without the collection reads as "stack not recorded", never as an empty stack, and an existing roadmap gains its stack through the ordinary feedback and candidate lifecycle — never by regeneration. Stack totality therefore binds a first stage run and any version that already carries the collection; a candidate in a lineage without it is not refused for that absence, so unrelated feedback on an existing roadmap keeps working until a candidate introduces the stack.

The stack is called out in two places. The first stage run's completion output and the generated `INDEX.md` list the full stack, with open and pending concerns listed separately. Every candidate review shows the current stack and what that candidate adds, changes, or opens. The callout is a standing summary, not a narrative-evidence defect class, and never blocks approval. Seed materialization (#460) renders the stack collection alongside hosting and store rows.

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

## Scope contract

- **In scope:** the `stack` collection's schema, parsing, totality gate, and feedback/candidate operations; constraints-stage authoring of chosen and open concerns; the first-publish and `INDEX.md` stack callout; the candidate-review stack summary and delta; inclusion in #460's seed rendering; `ROADMAP_FORMAT.md` and feedback-format documentation.
- **Out of scope / Non-goals:** a fifth roadmap artifact — deliberately not built, since the four-member version layout runs through every roadmap surface and stack choices are constraints (decided 2026-10-08); stack concerns beyond the three named; a closed vendor or product vocabulary; a narrative-evidence defect class or any approval block on stack content; judging whether a choice is good; Integration's HTML review aid, which follows this work separately in Integration; regenerating or rewriting existing accepted versions.
- **Allowed behavior changes:** the constraints stage authors stack rows and records an open concern instead of inventing a choice; first-run output, `INDEX.md`, and candidate review display the stack; stack rows become feedback targets.
- **Allowed reorganization:** none beyond the stated outcome.
- **Verification:** a Integration-brief replay records the deployment platform as open and every required concern as chosen or open; first-run output and `INDEX.md` list open concerns separately; a candidate that opens, adds, or changes a stack row shows that delta in review; an accepted version without the collection reads and renders as "stack not recorded", and an unrelated candidate in that lineage is not refused for the absence; a stack row can be targeted by feedback and revised through a candidate; existing hosting gates and candidate-review evidence stay green.
- **Stop / defer:** surface a stack concern the collection cannot express or a conflict with an accepted hosting or store choice without inventing one; route unrelated defects separately.

## References

- `ROADMAP_FORMAT.md` — `02-constraints.md` schema, § "Hosting facets and values", § "Narrative review evidence", and root-version publication.
- `plan_tool/roadmap_artifacts.py` — `ConstraintsArtifact`, `HostingRow`, `stage_row_collections`, and `_STAGE_ROW_OPERATION_POLICIES`.
- `plan_tool/roadmap_gates.py` — `check_hosting_totality` and the constraints gate tuple.
- `plan_tool/prompts/roadmap-constraints.md` — the constraints-stage hosting and pending-decision rules.
- `plan_tool/roadmap_index.py:write_roadmap_index` — the generated `INDEX.md`.
- `plan_tool/roadmap_candidate_review.py` and `plan_tool/roadmap_candidate_narrative.py` — candidate-review output.
- `ROADMAP_FEEDBACK_FORMAT.md` — feedback targets and the candidate lifecycle.
- Integration evidence (`rupe120/integration`): `aidlc/spaces/default/intents/260909-integration-mvp/ideation/approval-handoff/initiative-brief.md` § "Feasibility and Constraints" and `docs/implementation-plans/roadmaps/integration-aidlc-mvp/02-constraints.md`.
