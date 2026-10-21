> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-stack-propagation.md`.
> Preserved here for history; do not edit.

# Roadmap stack propagation into seeds and plans

## Outcome

A seed materialized from an accepted roadmap carries the hosting and store choices its plan depends on as settled constraints, and `create` and `detail` surface a conflict with them rather than substituting a different technology.

## Source

BACKLOG.md #460. Mark the entry plan-authored while execution is pending. The resulting plan must reconcile the originating backlog entry when the work ships; remove it only after full shipment, retaining any separately deferred follow-up.

## Architecture

The accepted roadmap already defines the stack: the constraints gates require one hosting row per facet (`compute`, `model`, `topology`), and every component names its store rows, each with a category and an optional `product`. The loss happens at seed materialization. `roadmap-seed.md` asks the seed to bind its domain rows, constraints, and assumptions — not its hosting or store rows — and leaves storage schemas to `create` and `detail`, so a draft seed names `store-app-db` by id without its content, and `create`, grounding against a repository with no database, chooses its own.

Observed 2026-10-08 in Integration (`integration-aidlc-mvp`): `03-components.md` declares `store-app-db` as `relational`, `pool`, `PostgreSQL` under the settled `decision-shared-database`; all six draft seeds cite `store-app-db` by id and none names PostgreSQL; the plan `2-connector-registry-seed.md` derived from one of them persists to "the shared SQLite database". No draft seed carries `hosting-compute: managed-containers` either.

`materialize_plan_seed` renders the stack deterministically from the accepted version, rather than relying on model output: every hosting row, and every store row named by the plan row's components, with category, sharing, and product. A row without a product renders it explicitly as not fixed by the accepted roadmap, so an open vendor is distinguishable from an unstated one. `create` carries that stack into the plan as settled, and `detail` treats the plan's stack as fixed. Where either would choose a technology that contradicts it, or name a specific product for a row whose product is not fixed, the conflict is reported instead of resolved silently. The checkable fact is that the seed's rendered stack equals the accepted rows; whether a plan's prose honours it is surfaced, not gated.

## Risks

- Drafts materialized before this change lack the stack section until rematerialized; promoted seeds and plans already derived from them, such as Integration's `2-connector-registry-seed.md`, keep their current text.
- Conflict reporting is advisory: it must surface a contradiction without becoming a gate on plan prose, which would judge meaning rather than a checkable fact.
- A rendered section inside model-authored draft text must survive draft-seed validation and identity classification, or every rematerialized draft would read as drifted.

## Scope contract

- **In scope:** deterministic stack rendering in materialized draft seeds and its draft-seed validation; carrying the stack from seed into `create` output; conflict reporting in `create` and `detail` when a chosen technology contradicts a carried store or hosting choice, or fixes a product the roadmap leaves open. The stack collection and its review callouts are #461; this renderer is what #461 extends.
- **Out of scope / Non-goals:** requiring hosting input in the brief, emitting a hosting question, owner-provenance tracking on hosting rows, and an "inapplicable hosting" answer — deliberately not built: the hosting gates already guarantee a defined stack, and clarifying a vendor or runtime (e.g. whether Integration targets AWS) is roadmap content settled through the existing feedback lifecycle (decided 2026-10-08). Also out: new hosting facets, values, or a provider field; a dedicated stack or foundation plan workflow; review-aid rendering; cloud provisioning or infrastructure configuration; correcting existing Integration plans or drafts.
- **Allowed behavior changes:** draft seeds gain a rendered stack section; `create` and `detail` report contradictions with carried store or hosting choices.
- **Allowed reorganization:** none beyond the stated outcome.
- **Verification:** replay the Integration case — the `connector-registry-seed` draft names PostgreSQL for `store-app-db` and the managed-containers hosting, and a plan built from it cannot select SQLite without a reported conflict. A row without `product` renders it explicitly as not fixed, and a plan naming a vendor for Integration's open `hosting-compute` product reports a conflict without being blocked. A changed accepted store or hosting row changes the rendered stack on rematerialization. Existing draft-seed validation and hosting gates stay green.
- **Stop / defer:** surface a stack choice the accepted roadmap cannot express, or a conflict whose resolution would change an accepted decision, without inventing a technology; route unrelated defects separately.

## References

- `plan_tool/roadmap.py:materialize_plan_seed` — draft-seed materialization this seed extends.
- `plan_tool/prompts/roadmap-seed.md` — seed-drafting prompt that omits hosting and store rows.
- `plan_tool/roadmap_gates.py:validate_draft_seed_content` and `plan_tool/roadmap_seed_manifest.py:classify_draft_seeds` — draft-seed validation and identity.
- `plan_tool/roadmap_artifacts.py` — `HostingRow`, store rows, and their `product` fields.
- `plan_tool/create.py:_load_roadmap_research_targets` — the existing `create` read of accepted hosting and store products.
- `ROADMAP_FORMAT.md` — `02-constraints.md` hosting schema, `03-components.md` store schema, and § "Draft seeds under the roadmap slug".
- Integration evidence (`rupe120/integration`): `docs/implementation-plans/roadmaps/integration-aidlc-mvp/03-components.md` (`store-app-db`), its `plan-seed-drafts/`, and `docs/implementation-plans/2-connector-registry-seed.md` step 3.
