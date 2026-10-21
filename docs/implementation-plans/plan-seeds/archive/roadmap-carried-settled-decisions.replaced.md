> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-carried-settled-decisions.md`.
> Preserved here for history; do not edit.

# Plan seed: Roadmap carried settled decisions

Source backlog entry: `BACKLOG.md` #363. The resulting plan updates that entry
when this work ships.

## Outcome

`plan-tool roadmap` will preserve a closed, approved set of upstream decisions
as visibly inherited Roadmap `decisions` rows. Every carried row will cite the
confirmed material in the recorded source that settled it. A Roadmap-derived
decision will remain visibly different and will retain its own deliberation
requirements.

## Overview

This effort carries confirmed upstream choices through the existing Roadmap
source and decision artifacts. It is the smallest next slice selected by the
approval-bound Integration Gate 1 comparison.

## Problem statement

The approval-bound Integration Gate 1 comparison at
`docs/evidence/roadmap-aidlc-intake-comparison-20260916.md` confirms this
smallest next slice. Both its one-brief and deterministic composed arms retain
the material box but re-author confirmed upstream choices as Roadmap `settled`
decisions, invent rejected alternatives, and emit no source citations. The
comparison does not select per-stage supplementary grounding (#362), a source
manifest, or an AI-DLC adapter.

## References

- `docs/evidence/roadmap-aidlc-intake-comparison-20260916.md` — frozen-corpus
  comparison that selects #363 and holds #362.
- `BACKLOG.md` #363 and
  `handoffs/2026-09-14-roadmap-aidlc-integration-delivery.md` — selected
  scope, non-goals, and delivery order.
- `ROADMAP_FORMAT.md` and `DATA_CONTRACT.md` — existing artifact, citation,
  prompt-boundary, and compatibility contracts that the new row meaning must
  extend without weakening.
- `plan_tool/roadmap_artifacts.py:DecisionRow`, `plan_tool/roadmap_gates.py`,
  and `plan_tool/roadmap.py` — current decision-row parsing, gate, source,
  and stage-publication owners.

## Architecture

- Accept one closed, generic block of carried decisions associated with the
  already recorded Roadmap source. The plan must select its exact input and
  citation syntax without coupling it to AI-DLC paths, artifact names, stage
  slugs, or runtime state.
- A carried decision creates a `decisions` row with `status: settled` and a
  resolvable `source` citation that marks it as inherited. It anchors to a live
  row in the artifact carrying it.
- The source citation proves a confirmed answer in the recorded source. It
  must resolve deterministically; an absent, ambiguous, unresolved, or
  unconfirmed citation refuses rather than dropping or silently converting the
  carried row.
- Roadmap-derived decisions keep the existing rejected-alternatives and
  rationale rules. A carried decision includes a rejected alternative only
  when the upstream record itself states a considered path and why it lost;
  unselected options in a question are not rejected alternatives.
- Existing roadmaps and handwritten briefs without the optional input retain
  current behavior and parse/render compatibly. Reader context grants no new
  writer authority, lifecycle authority, rebind authority, or stage-prompt
  authority beyond the selected decision rows.

## Scope guardrails

- The carried block grants authority only to the selected decision rows. It
  grants no other writer, lifecycle, rebind, or stage-prompt authority.
- Keep #362's per-stage supplementary grounding and multi-source identity
  outside this plan. If the selected input needs those capabilities, defer
  that work rather than extending this source route.
- Do not add AI-DLC-specific parsing or runtime knowledge to Plan-tool.

## In scope

- Generic Roadmap source parsing, decision-row schema/rendering, stage prompt
  routing, deterministic gates, compatibility readers, and focused tests and
  documentation.
- The exact affected Roadmap stages and whether a carried decision appears in
  one or multiple artifacts are plan decisions, bounded by its anchor and
  citation contract.
- Allowed behavior changes: a closed carried-decision block may produce
  inherited settled rows; invalid carried provenance or anchoring refuses
  publication. No other Roadmap route changes behavior.
- Allowed reorganization: none unless a concrete ownership boundary blocks
  this behavior; the plan must name that boundary before proposing a move.

## Out of scope

- Per-stage supplementary sources, a generic manifest, source roles, broader
  multi-source identity, obligations, open-question workflow, selected rule
  reader, shared revision frame, coverage projection, status JSON, or any
  Integration/runtime change.
- Parsing free-form decision logs, question menus, source directories, or
  positional prose. Connector-side mapping remains outside Plan-tool.
- A new requirement that Roadmap derive rationale or rejected alternatives
  from upstream material.

## Testing

Use focused parser, renderer, prompt-boundary, gate, compatibility, and
mutation tests. Cover inherited and Roadmap-derived rows separately, every
citation and anchor refusal, legacy reads, and unchanged handwritten-brief
behavior. Do not test or invoke Integration, AI-DLC runtime paths, or a connector.

## Acceptance criteria

- A recorded source with a closed carried-decision block produces inherited,
  settled, cited decision rows and retains the source reference in every
  relevant rendered artifact.
- Each refusal class—missing anchor, missing citation, ambiguous citation,
  unconfirmed citation, invalid carried status, and a model attempt to mutate
  carried provenance—stops publication at the relevant gate.
- A Roadmap-authored decision still requires rejected alternatives and a
  rationale; a carried decision remains valid without generated alternatives.
- Legacy artifacts and a project using only a handwritten brief remain valid,
  and no input changes Roadmap source admission or non-stage routes.
- The final plan step reconciles `BACKLOG.md` #363 only after the capability
  ships.

## Risks

- A prose-only carrier can become an enumeration channel and let upstream
  content preselect roadmap rows. Keep the block closed and independently
  validated.
- A citation that merely looks plausible can misrepresent approval. Resolution
  must bind it to confirmed source material, not an unselected option or a
  decision-log repetition.
- Extending the source reader now can accidentally ship #362. Stop if the
  selected input needs per-stage roles, multiple independent source identities,
  or prompt authority beyond carried decisions.

## Deferred

Per-stage supplementary grounding (#362), a source manifest, and AI-DLC
adapter work remain separate. Out-of-scope discoveries go to `BACKLOG.md` or
`BUG_BACKLOG.md` rather than expanding this plan.
