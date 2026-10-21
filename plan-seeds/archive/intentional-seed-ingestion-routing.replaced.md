> **Replaced**: this file has been superseded by `docs/implementation-plans/2-seed-ingestion-routing.md`.
> Preserved here for history; do not edit.

# Plan seed: intentional seed ingestion and visible preparation routing

## Overview

`create --from-existing` ingests a deterministically direct-ready source as
the authoring source without a model rewrite. A source that needs assistance
enters exactly one visible in-`create` preparation route: a normalized
single-plan candidate, a `SplitProposal`, or a bounded refusal/repair result.

## Problem statement

The current distill pass mixes source canonicalization, split assessment, and
downstream source replacement. It can replace supplied prose even when the
source already supplies the body and References that plan authoring needs, and
its size-based shortcut does not express why a model call is necessary. The
existing safe split proposal must remain inside `create`, but the selected
route and artifact authority must be visible to operators, headless callers,
run records, checkpoints, and archival handling.

## Architecture

Define one deterministic direct-ready gate at the file-backed intake seam. It
retains the existing non-placeholder References refusal and uses the selected
canonical body and strict-step properties to decide whether model preparation
is needed. The direct route retains the source text and source References as
authoritative, bypasses distillation and body completion, and invokes step
proposal only when strict step extraction cannot supply the graph.

Preparation returns a closed, observable result vocabulary before a plan or
manifest write. Its normalized candidate may map source-supported evidence
into canonical body sections, but it never silently becomes the original
source. Split remains a no-plan, no-manifest success with an operator-visible
next action. Unsupported evidence and malformed preparation output take the
bounded refusal/repair path instead of reaching a late TODO gate after
unrelated model calls.

## Out of scope

- A general semantic seed audit or a new universal canonical-heading
  preflight beyond References.
- Removing `SplitProposal`, moving split assessment into a separate command,
  or silently continuing a split as one plan.
- Changing step, References-research, or body-synthesis contracts beyond the
  selected source and preparation routing they consume.
- Rewriting historical seeds or artifacts, or implementing #102's broader
  heading-alias proposal without an explicit reconciliation decision.

## Risks

- An over-permissive direct-ready gate can publish from an unusable source;
  an over-narrow gate preserves unnecessary model cost and hidden rewriting.
- Checkpoints, archived raw/normalized artifacts, CLI exit behavior, and run
  records form one compatibility surface across terminal and headless modes.
- A preparation result must not fabricate scope, risks, tests, acceptance
  criteria, or deferrals merely to complete a canonical shape.

## Testing

- Cover a direct-ready source that performs no distill or body-synthesis call
  and retains its raw text and References as authoring input.
- Cover each preparation terminal result: normalized single candidate, split,
  and refusal/repair; prove split writes no plan or manifest entry.
- Cover absent optional context so it reaches neither an implied model call
  nor a late placeholder rejection, while missing References still refuses
  before every authoring call and write.
- Pin TTY, `--yes`, and non-TTY reporting, run-log outcomes, checkpoint reuse,
  and archival behavior for the selected direct and preparation routes.

## Acceptance criteria

- A direct-ready file-backed source remains authoritative through plan
  rendering and skips unnecessary distillation, References research, and body
  synthesis.
- Every non-direct-ready source enters one named preparation result before
  publication; model output never silently replaces the source authority.
- Split stays an automatic, discoverable no-plan/no-manifest outcome.
- References remains the only universal source fallback and refuses before
  cost when absent or placeholder.
- Route outcome, archive/checkpoint behavior, and command behavior are
  explicit and covered for interactive and headless operation.

## Deferred

- Conservative aliases for near-miss canonical headings remain BACKLOG #102
  unless this plan records a narrower compatible mechanism.
- A general seed-quality or semantic-audit policy remains outside this route.

## References

- [`BACKLOG.md` #327](../BACKLOG.md) — selected outcome, scope, compatibility
  constraints, and acceptance surface.
- [`CREATE_SEED_INGESTION_CONTRACT.md`](../docs/CREATE_SEED_INGESTION_CONTRACT.md)
  — approved direct-ready, preparation, optionality, and lifecycle contract.
- [`backlog-arc-seed-ingestion.md`](../docs/implementation-plans/backlog-arcs/backlog-arc-seed-ingestion.md)
  — ordered route, decision gates, and explicit exclusions.
- [`CREATE_FROM_EXISTING_FLOW.md`](../docs/CREATE_FROM_EXISTING_FLOW.md) —
  current file-backed create lifecycle that this plan will change.
