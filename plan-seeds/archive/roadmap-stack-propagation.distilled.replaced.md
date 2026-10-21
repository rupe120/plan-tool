> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-stack-propagation.md`.
> Preserved here for history; do not edit.

## Overview

A draft seed materialized from an accepted roadmap will carry the hosting and store choices its plan depends on as settled constraints. `materialize_plan_seed` renders that stack deterministically from the accepted version — every hosting row, plus every store row named by the plan row's components, with category, sharing, and product. `create` carries the stack into the plan as settled, and `detail` treats it as fixed. When either would pick a technology that contradicts the stack, or name a product the roadmap leaves open, the conflict is reported rather than silently resolved. Reporting is advisory and never a gate on plan prose.

## Problem statement

The accepted roadmap already defines the stack: the constraints gates require one hosting row per facet (`compute`, `model`, `topology`), and every component names its store rows, each with a category and an optional `product`. The stack is lost at seed materialization. `plan_tool/prompts/roadmap-seed.md` asks the seed to bind its domain rows, constraints, and assumptions, but not its hosting or store rows, and it leaves storage schemas to `create` and `detail`. So a draft seed names `store-app-db` by id without saying what it is, and `create`, grounding against a repository with no database, picks its own.

Observed 2026-10-08 in Integration (`integration-aidlc-mvp`): `03-components.md` declares `store-app-db` as `relational`, `pool`, `PostgreSQL` under the settled `decision-shared-database`. All six draft seeds cite `store-app-db` by id, and none names PostgreSQL. The plan `2-connector-registry-seed.md`, derived from one of them, persists to "the shared SQLite database". No draft seed carries `hosting-compute: managed-containers` either.

Source: BACKLOG.md #460. The entry is marked plan-authored while execution is pending. The plan reconciles that backlog entry when the work ships: it is removed only after full shipment, and any separately deferred follow-up is kept.

## Architecture

**Deterministic stack rendering at materialization.** `plan_tool/roadmap.py:materialize_plan_seed` renders a stack section from the accepted version (`plan_tool/roadmap_artifacts.py` — `HostingRow`, store rows, and their `product` fields). The renderer builds it, not model output. It includes every hosting row and every store row named by the plan row's components, each with category, sharing, and product. A row with no `product` says explicitly that the product is not fixed by the accepted roadmap, so an open vendor can be told apart from an unstated one. The checkable fact is that the seed's rendered stack equals the accepted rows. #461 extends this renderer with stack collection and review callouts.

**Survival through draft-seed validation and identity.** The rendered section sits inside model-authored draft text. It must pass `plan_tool/roadmap_gates.py:validate_draft_seed_content` and `plan_tool/roadmap_seed_manifest.py:classify_draft_seeds` so that a rematerialized draft does not read as drifted. A changed accepted store or hosting row changes the rendered stack when the draft is rematerialized.

**Carrying the stack through `create` and `detail`.** `create` carries the seed's stack into the plan as settled constraints. `plan_tool/create.py:_load_roadmap_research_targets` already reads accepted hosting and store products. `detail` treats the plan's stack as fixed.

**Advisory conflict reporting.** When `create` or `detail` would choose a technology that contradicts a carried store or hosting choice, or would name a specific product for a row whose product is not fixed, the conflict is reported instead of resolved silently. Whether a plan's prose honours the stack is surfaced, not gated: gating it would mean judging meaning rather than checking a fact.

**Stop / defer.** A stack choice the accepted roadmap cannot express, or a conflict whose resolution would change an accepted decision, is surfaced without inventing a technology. Unrelated defects are routed separately.

## Out of scope

- **Out of scope / Non-goals:** requiring hosting input in the brief, emitting a hosting question, owner-provenance tracking on hosting rows, and an "inapplicable hosting" answer — deliberately not built: the hosting gates already guarantee a defined stack, and clarifying a vendor or runtime (e.g. whether Integration targets AWS) is roadmap content settled through the existing feedback lifecycle (decided 2026-10-08). Also out: new hosting facets, values, or a provider field; a dedicated stack or foundation plan workflow; review-aid rendering; cloud provisioning or infrastructure configuration; correcting existing Integration plans or drafts.

## Risks

- Drafts materialized before this change lack the stack section until rematerialized; promoted seeds and plans already derived from them, such as Integration's `2-connector-registry-seed.md`, keep their current text.
- Conflict reporting is advisory: it must surface a contradiction without becoming a gate on plan prose, which would judge meaning rather than a checkable fact.
- A rendered section inside model-authored draft text must survive draft-seed validation and identity classification, or every rematerialized draft would read as drifted.

## Testing

- **Verification:** replay the Integration case — the `connector-registry-seed` draft names PostgreSQL for `store-app-db` and the managed-containers hosting, and a plan built from it cannot select SQLite without a reported conflict. A row without `product` renders it explicitly as not fixed, and a plan naming a vendor for Integration's open `hosting-compute` product reports a conflict without being blocked. A changed accepted store or hosting row changes the rendered stack on rematerialization. Existing draft-seed validation and hosting gates stay green.

## Acceptance criteria

- **Verification:** replay the Integration case — the `connector-registry-seed` draft names PostgreSQL for `store-app-db` and the managed-containers hosting, and a plan built from it cannot select SQLite without a reported conflict. A row without `product` renders it explicitly as not fixed, and a plan naming a vendor for Integration's open `hosting-compute` product reports a conflict without being blocked. A changed accepted store or hosting row changes the rendered stack on rematerialization. Existing draft-seed validation and hosting gates stay green.

## Input

The accepted roadmap already defines the stack: the constraints gates require one hosting row per facet (`compute`, `model`, `topology`), and every component names its store rows, each with a category and an optional `product`. The loss happens at seed materialization. `roadmap-seed.md` asks the seed to bind its domain rows, constraints, and assumptions — not its hosting or store rows — and leaves storage schemas to `create` and `detail`, so a draft seed names `store-app-db` by id without its content, and `create`, grounding against a repository with no database, chooses its own.
