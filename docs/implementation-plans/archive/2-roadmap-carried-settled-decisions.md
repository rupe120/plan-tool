> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
format_version: 1
title: Roadmap Carried Settled Decisions
intent: '`plan-tool roadmap` will preserve a closed, approved set of upstream decisions
  as visibly inherited Roadmap `decisions` rows. Every carried row will cite the confirmed
  material in the recorded source that settled it. A Roadmap-derived decision will
  remain visibly different and will retain its own deliberation requirements.'
status: completed
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
enforce_step_tests: true
source_seed: docs/implementation-plans/plan-seeds/roadmap-carried-settled-decisions.md
steps:
- id: 1
  title: Parse the optional carried-decision block from the recorded Roadmap brief
    through the existing source-admission path
  intent: Give Roadmap a generic, fail-closed source of approved decisions without
    admitting free-form logs, positional prose, extra sources, or stage-wide grounding.
  files:
  - plan_tool/roadmap_source.py
  - plan_tool/roadmap.py
  - tests/test_roadmap_source.py
  - tests/test_roadmap.py
  complexity: high
  change_type: feature
  detail: docs/implementation-plans/plan-details/roadmap-carried-settled-decisions/01-parse-validate-optional-carried.md
  status: done
- id: 2
  title: Extend DecisionRow parsing and rendering to distinguish cited inherited decisions
    from Roadmap-derived decisions
  intent: Keep inherited decisions visibly attributable while retaining the existing
    rationale and rejected-alternative shape for decisions Roadmap makes.
  files:
  - plan_tool/roadmap_artifacts.py
  - tests/test_roadmap_artifacts.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/roadmap-carried-settled-decisions/02-extend-decisionrow-parsing-rendering.md
  status: done
- id: 3
  title: Gate inherited decisions on settled status, owning-artifact anchors, and
    confirmed citations against the current recorded source
  intent: Refuse missing, ambiguous, unconfirmed, mis-anchored, or model-mutated carried
    decisions before any artifact can be published.
  files:
  - plan_tool/roadmap_gates.py
  - tests/test_roadmap_gates.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 2
  depends_on_notes:
    1: Provides the validated closed carried-decision input and its confirmed citation
      targets.
    2: Provides the artifact representation that identifies inherited rows and retains
      their citations.
  detail: docs/implementation-plans/plan-details/roadmap-carried-settled-decisions/03-gate-inherited-decisions-on-settled.md
  status: done
- id: 4
  title: Route each carried decision only to its owning stage and preserve gate-before-atomic-overwrite
    publication with seed writes unchanged
  intent: Emit each approved inherited row once in the artifact that owns its anchor,
    while handwritten briefs, legacy artifacts, re-entry paths, and non-stage Roadmap
    routes keep their current behavior.
  files:
  - plan_tool/roadmap.py
  - plan_tool/roadmap_revision.py
  - plan_tool/prompts/roadmap-domain.md
  - plan_tool/prompts/roadmap-constraints.md
  - plan_tool/prompts/roadmap-components.md
  - plan_tool/prompts/roadmap-plans.md
  - tests/test_roadmap.py
  - tests/test_roadmap_revision.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 2
  - 3
  depends_on_notes:
    1: Supplies the admitted carried-decision block without widening the recorded
      source route.
    2: Defines the inherited row shape each prompt must emit.
    3: Provides the publication gates and retry messages for every refusal class.
  detail: docs/implementation-plans/plan-details/roadmap-carried-settled-decisions/04-route-each-carried-decision-only-its.md
  status: done
- id: 5
  title: 'Document the carried-decision source and row contracts, then close BACKLOG.md
    #384'
  intent: 'Make the input syntax, citation and anchor rules, compatibility boundary,
    and deferred #383 scope discoverable before recording the backlog item as delivered.'
  files:
  - ROADMAP_FORMAT.md
  - DATA_CONTRACT.md
  - docs/how-to/roadmap.md
  - BACKLOG.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 4
  depends_on_notes:
    4: 'Provides the shipped behavior and landed identifiers that the documentation
      records before #384 is closed.'
  detail: docs/implementation-plans/plan-details/roadmap-carried-settled-decisions/05-document-carried-decision-source-row.md
  status: done
---
# Roadmap Carried Settled Decisions

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
comparison does not select per-stage supplementary grounding (#383), a source
manifest, or an AI-DLC adapter.

## Architecture

- Accept one closed, generic block of carried decisions associated with the
  already recorded Roadmap brief. A caller supplies one `## Carried decisions`
  fenced JSON block in the brief passed to the existing `--from-existing`
  route. It names confirmed answers by id and decisions that cite those ids;
  a selected option must equal its cited confirmed answer. Parse it before
  authoring, exclude the raw block from general brief context, and route only
  each stage's selected decisions. No AI-DLC path or runtime state enters the
  syntax.
- A carried decision creates a `decisions` row with `status: settled` and a
  resolvable `source` citation that marks it as inherited. The closed input
  assigns it exactly one owning artifact; it appears only there and anchors to
  a live row in that same artifact. Later stages read the owning artifact as
  upstream context rather than repeating its decision row.
- The source citation proves a confirmed answer in the recorded source. It
  must resolve deterministically; an absent, ambiguous, unresolved, or
  unconfirmed citation refuses rather than dropping or silently converting the
  carried row.
- Confirmed same-path brief rebind retains its baseline-only behavior: it does
  not rewrite or endorse existing artifacts. Before any later stage or revision
  publishes, re-gate existing carried rows against the newly accepted source
  and refuse if a cited confirmation no longer resolves. A material change to
  that confirmation starts a successor roadmap lineage; rebind alone cannot
  migrate a settled decision.
- Bounded feedback can revise Roadmap-derived decisions. Its operations cannot
  add, edit, or remove a source-owned inherited decision; unrelated feedback
  preserves inherited rows and re-gates them against the current brief before
  publication.
- Roadmap-derived decisions keep the existing rejected-alternatives and
  rationale rules. A carried decision includes a rejected alternative only
  when the upstream record itself states a considered path and why it lost;
  unselected options in a question are not rejected alternatives. Optional
  inherited rationale or rejected alternatives match the approved block
  exactly; a model cannot add them.
- Existing roadmaps and handwritten briefs without the optional input retain
  current behavior and parse/render compatibly. Reader context grants no new
  writer authority, lifecycle authority, rebind authority, or stage-prompt
  authority beyond the selected decision rows.

## Scope guardrails

- The carried block grants authority only to the selected decision rows. It
  grants no other writer, lifecycle, rebind, or stage-prompt authority.
- The raw block is not general stage grounding; only validated rows selected
  for the owning stage reach that stage's prompt.
- Revalidation after rebind may refuse a later write, but cannot make the
  baseline-only rebind itself mutate artifacts, feedback, or seeds.
- Keep #383's per-stage supplementary grounding and multi-source identity
  outside this plan. If the selected input needs those capabilities, defer
  that work rather than extending this source route.
- Do not add AI-DLC-specific parsing or runtime knowledge to Plan-tool.

## References

- `docs/evidence/roadmap-aidlc-intake-comparison-20260916.md` — frozen-corpus
  comparison that selects #384 and holds #383.
- `BACKLOG.md` #384 and
  `handoffs/2026-09-14-roadmap-aidlc-integration-delivery.md` — selected
  scope, non-goals, and delivery order.
- `ROADMAP_FORMAT.md` and `DATA_CONTRACT.md` — existing artifact, citation,
  prompt-boundary, and compatibility contracts that the new row meaning must
  extend without weakening.
- `plan_tool/roadmap_artifacts.py:DecisionRow`, `plan_tool/roadmap_gates.py`,
  and `plan_tool/roadmap.py` — current decision-row parsing, gate, source,
  and stage-publication owners.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Per-stage supplementary sources, a generic manifest, source roles, broader
  multi-source identity, obligations, open-question workflow, selected rule
  reader, shared revision frame, coverage projection, status JSON, or any
  Integration/runtime change.
- Parsing free-form decision logs, question menus, source directories, or
  positional prose. Connector-side mapping remains outside Plan-tool.
- A new requirement that Roadmap derive rationale or rejected alternatives
  from upstream material.

## Risks

- A prose-only carrier can become an enumeration channel and let upstream
  content preselect roadmap rows. Keep the block closed and independently
  validated.
- A citation that merely looks plausible can misrepresent approval. Resolution
  must bind it to confirmed source material, not an unselected option or a
  decision-log repetition.
- Extending the source reader now can accidentally ship #383. Stop if the
  selected input needs per-stage roles, multiple independent source identities,
  or prompt authority beyond carried decisions.

## Testing

Use focused parser, renderer, prompt-boundary, gate, compatibility, and
mutation tests. Cover inherited and Roadmap-derived rows separately, every
citation and anchor refusal, single-artifact placement with later-stage
consumption, legacy reads, and unchanged handwritten-brief behavior. Verify
that rebind itself changes only the source baseline and that the next stage
refuses stale carried citations before publication. Do not test or invoke
Integration, AI-DLC runtime paths, or a connector. Cover initial and rebind submission
through `--from-existing`, raw-block exclusion from shared brief prompts, and
bounded feedback's refusal to mutate inherited rows.

## Acceptance criteria

- A recorded source with a closed carried-decision block produces inherited,
  settled, cited decision rows in each decision's single owning artifact,
  anchored to a live row there; later artifacts consume that upstream record
  without duplicating it.
- The existing `--from-existing` brief route admits the closed block on an
  initial run and confirmed same-path rebind without a manual `source.json`
  edit.
- Each refusal class—missing anchor, missing citation, ambiguous citation,
  unconfirmed citation, invalid carried status, and a model attempt to mutate
  carried provenance—stops publication at the relevant gate.
- A Roadmap-authored decision still requires rejected alternatives and a
  rationale; a carried decision remains valid without generated alternatives.
- Legacy artifacts and a project using only a handwritten brief remain valid,
  and no input changes Roadmap source admission or non-stage routes.
- A confirmed brief rebind still replaces only the source baseline. A later
  stage or revision cannot publish while an existing carried citation fails to
  resolve against that accepted source.
- Bounded feedback on an unrelated row preserves inherited provenance; an
  operation targeting an inherited decision refuses before publication.
- The final plan step reconciles `BACKLOG.md` #384 only after the capability
  ships.

## Deferred

Per-stage supplementary grounding (#383), a source manifest, and AI-DLC
adapter work remain separate. Out-of-scope discoveries go to `BACKLOG.md` or
`BUG_BACKLOG.md` rather than expanding this plan.
