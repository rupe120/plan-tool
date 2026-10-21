> **Replaced**: this file has been superseded by `docs/implementation-plans/2-seed-source-references-fallback.md`.
> Preserved here for history; do not edit.

# Seed: restore References fallbacks for file-backed create sources

## Outcome

Every maintained seed that instructs an operator to run
`plan-tool create --from-existing` includes a non-placeholder `## References`
fallback, so it reaches its intended authoring route instead of failing before
slug inference or a model call.

## In scope

- Add source-evidence References blocks to every current top-level
  `plan-seeds/*.md` file. Each block cites the backlog item, decision record,
  plan, report, or source document that the seed already relies on; it does
  not invent an external URL.
- Extend `plan_tool/prompts/roadmap-seed.md` so a materialized roadmap seed
  contains `## References` naming its four accepted roadmap artifacts. Keep
  the existing provenance validation independent from this create preflight.
- Make `plan_tool/reground.py:render_rebaseline_seed` emit the same source-plan
  References fallback used by the scope-out renderer.
- Prove direct preflight compatibility for representative hand-authored,
  annotate, single- and region-scope-out, rebaseline, and roadmap-materialized
  sources using `plan_tool.create.validate_from_existing_seed`.

## Overview

`create --from-existing` already rejects a source without a non-placeholder
References H2 before any authoring work. The active seed corpus and two
maintained producers can nevertheless write or advertise sources without that
fallback. Align those producers and live inputs with the existing deterministic
contract, without changing what `create` considers valid.

## Problem statement

The one hard source preflight is correct because a failed reference-research
response cannot replace source evidence. Its guarantee is currently
undermined by inputs the project itself supplies: they promise a
`--from-existing` handoff, then deterministically refuse at that handoff. The
failure hides the intended preparation route and blocks the active seed queue
before a user can evaluate it.

## Architecture

Keep `validate_from_existing_seed` as the single create-owned check. Each
producer owns its own fallback: hand-authored seeds cite the source that
already grounds their work, roadmap materialization cites the accepted
roadmap artifacts, and rebaseline cites the source plan. Tests call the real
create preflight against rendered output rather than reimplementing its H2 or
placeholder recognition. Annotate and scope-out already emit an equivalent
fallback, so their tests become compatibility coverage rather than a shared
producer abstraction.

## Out of scope

- Adding canonical-body H2 requirements beyond References.
- Altering distillation, body synthesis, direct-ready routing, split proposals,
  or model-call ordering; BACKLOG #327 owns those changes.
- Rewriting archived seeds or introducing a seed schema.
- Treating a placeholder, a generic fabricated URL, or an empty list as
  reference evidence.

## Risks

- A rote corpus sweep could add stale or irrelevant links. Each new block must
  cite the seed's actual source evidence and retain existing citations.
- A roadmap-only provenance test could pass while the emitted seed still fails
  `create` validation. Exercise the create preflight on the materialized and
  promoted body.
- Rebaseline currently receives the parsed plan rather than its body text.
  Keep the repair minimal by naming the source plan rather than adding another
  source-body reader to preserve its References section.

## Testing

Run focused create, annotate, scope-out, reground, and roadmap suites. Add a
parameterized preflight test that loads every root `plan-seeds/*.md`, and test
one absent/placeholder References control through the actual validator with an
invoker that would fail if called. Exercise each generated source after its
renderer/prompt path, including the roadmap promoted form, and assert
`validate_from_existing_seed` accepts it.

## Acceptance criteria

- Every top-level file under `plan-seeds/` passes
  `validate_from_existing_seed`; archive files are not changed.
- A roadmap materialized draft and its promoted `plan-seeds/` copy both carry
  a non-placeholder References H2 and pass the create validator without
  weakening roadmap provenance gates.
- A rebaseline seed emits a source-plan References fallback, and both scope-out
  renderers and annotate remain validator-clean.
- A missing or placeholder References control still fails before the first
  authoring invoker, output, checkpoint, archive, plan, or manifest write.

## Deferred

- The direct-ready versus preparation result table, optional-section rendering,
  and source-authority changes belong to BACKLOG #327 after this compatibility
  repair.
- Conservative aliases for near-miss canonical H2s remain BACKLOG #102.

## References

- `docs/CREATE_SEED_INGESTION_CONTRACT.md` — current section classifications,
  generated-source inventory, and the decision that References remains the
  universal preflight.
- `BACKLOG.md` #351 — selected scope and verification boundary.
- `plan_tool/create.py:validate_from_existing_seed` — the create-owned
  deterministic check this work satisfies without changing.
- `plan_tool/annotate_render.py:render_create_seed`,
  `plan_tool/scope_out.py:render_carved_seed`,
  `plan_tool/reground.py:render_rebaseline_seed`, and
  `plan_tool/prompts/roadmap-seed.md` — maintained source producers.
