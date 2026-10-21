> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-02-feedback-channel.md`.
> Preserved here for history; do not edit.

## Overview

Arc position 02 of the `roadmap-NN-*` group (anchor: `BACKLOG.md` #208) makes a re-run roadmap stage **revise its previous artifact against human feedback** instead of re-authoring from the brief. The operator writes feedback against any row — an entity, a rule, a workflow, a disposition, a constraint, a decision — re-enters at that stage with `--from-stage N`, and the next proposal is the previous one carried forward with that feedback applied. Two deterministic guards hold the line: id continuity (every previous row id appears in the revision or is named in a removal record) and settled finality (a decision the operator marked `settled` survives with its id and status). No new flag, no interactive surface, and a first run with nothing on disk behaves exactly as position 01 ships. Position 01 shipped stages 1–2 (`01-domain.md`, `02-constraints.md`, the eight relation gates, the bounded retry, `--from-stage N` re-entry); later positions own the components artifact, seed derivation, and the framework lenses, and this position reaches into none of them.

## Problem statement

**The proposal is subjective in its essence.** There is no correct roadmap for a brief, only a defensible one, and the only quality function that exists is the human reading it. That makes the feedback loop the system's *other half*, not an enhancement — and today only the first half exists.

Two structural gaps:

**Re-proposal is regeneration.** `roadmap.py:_render_stage_prompt` receives `slug`, `brief` and the artifacts of stages *below* the one running. A stage never sees its own previous output, so `--from-stage N` re-authors from scratch. Measured 2026-08-02 on two identical-input runs: entity ids **85%** shared, workflow **60%**, business-rule **30%**, decision **25%**, and **0 of 11** shared entities kept the same field-name set. Every direct edit an operator makes is destroyed by the re-run intended to incorporate their feedback, and feedback naming a row is stale before it is read.

**Feedback has no channel at all.** `_corrections_block` already prepends corrections to a retried stage prompt, replace-never-accumulate, and has exactly one producer: gate violations. A human's "this decomposition is wrong because X" cannot reach a stage. The only correction available is hand-editing — the operator doing the work.

`pending` is already a channel in one direction: the stage guessing at a load-bearing tradeoff and asking. What is missing is the answer, and an answer that can say **"neither — do C"** rather than only yes or no.

## Architecture

**Revision, not regeneration.** A stage being re-run with a previous version of its own artifact on disk receives that artifact and revises it. This is a deliberate reversal of a documented property — arc lesson 4, "re-entry regenerates; it does not revise," recorded as a finding rather than a defect — and it is the change that makes everything else here meaningful: feedback on an entity means nothing if the entity is rebuilt from nothing next round. Every re-run stage that has a predecessor revises, at every level, so contributions survive wherever the operator made them. A first run, with nothing on disk, authors exactly as position 01 ships.

**Feedback is its own row collection, anchoring to any row.** Not a field on six row types: one row kind carrying the operator's text plus an `anchor`, reusing the anchor concept the artifacts already have and the gates already resolve. That is what lets feedback redirect or correct *any* concept rather than only the decisions the stage happened to record. A feedback row anchoring to the artifact as a whole covers "the shape of this is wrong."

**Feedback is consumed, and git is the audit trail.** A revision clears the feedback it acted on; the artifacts are committed docs, so the previous version and its feedback are in history. Replace-never-accumulate already governs why — re-asserting a correction the artifact no longer needs is how a retry loop spins.

**Two deterministic guards, and they are the only things checked.**

- **Id continuity.** Every row id in the previous artifact appears in the revision, or is named in its removal record. A revision may drop a row; it may not drop one *silently*. This converts an invisible loss into a declared one the operator can review, and it is a set check over ids — not a judgment about whether dropping was right.
- **Settled finality.** A decision the operator marked `settled` survives with its id and status. Declaring its removal is not enough: `settled` means the human decided, and the tool does not overturn it. An operator who wants it gone changes its status first. The gate protects their acceptance and never overrules them.

Feedback rows are exempt from id continuity — disappearing is what they are for.

**The binary observable, stated once:** the previous artifact and the unresolved feedback are **present in the stage prompt** for a revision that has them, and the run log records that they were delivered. Delivery is the feature. Whether the revision *honored* the feedback is subjective on both sides and is not checked — see Out of scope.

**Gates check well-formedness, never merit.** Does this id resolve, is this value in the closed vocabulary, did this row survive. No gate may acquire an opinion about whether a proposal is *good*; that is the human's role, and it is the whole reason this position exists.

**Nothing decides the roadmap is finished.** Quality being subjective, the loop has no fixed point the tool can compute — it ends when the operator stops giving feedback. No convergence verdict, no completeness score, no "0 pending" success signal.

**Touched surfaces.** `roadmap_artifacts.py` owns the feedback row kind, the removal record, and their shape rules. `roadmap_gates.py` owns the two guards. `roadmap.py` reads the previous artifact before overwrite, threads it and the feedback into the stage prompt through the existing corrections seam, and writes a run-log record of what was delivered. `prompts/roadmap-{domain,constraints}.md` carry the revision contract: each stage now has an authoring mode and a revision mode, and whether that is one prompt with two modes or a second prompt file per stage is the plan's call, under one constraint — **do not bloat the authoring prompt**, which #215 says already runs close to its retry budget. `ROADMAP_FORMAT.md` and `RUNBOOK.md` carry the schema and the operator loop. Tests follow `TESTING.md`, invokers stubbed.

**Allowed behavior changes.** A stage re-run over an existing artifact revises rather than re-authors. One new row kind, one removal record, two new gates, one new run-log record. A first run is unchanged. No new flag; `--from-stage N` keeps its meaning. Nothing new on stdout beyond the existing pending/overwrite summary.

**Allowed reorganization.** The corrections seam is widened where it is; it does not move. A second prompt file per stage is permitted if the plan chooses that split — the stage table is already `(prompt file, …)` data.

## Out of scope

- **Judging whether the revision honored the feedback**, or scoring the proposal's quality. The enumerated not-allowed list CLAUDE.md § "Validating a semantic property you cannot observe" requires: **no** quality judgment of feedback or of the response to it; **no** agreement check between feedback text and the revised artifact; **no** length, shape or count cap on feedback; **no** gate, finding, warning or exit-code flip keyed on either. Both sides of that comparison are subjective — there is nothing to check against.
- **Any convergence or done-ness verdict** for a roadmap.
- **Interactive surfaces.** The verb stays non-interactive by construction (#208): no confirm, no `-y`, no TTY branch, no review walk. The operator's editor and git are the interface.
- **Preserving feedback text past the revision it feeds.**
- **A second store** — no sidecar, no comment file, no `.plan-tool/` state. The artifact is the channel.
- **Guaranteeing id stability in general.** The guards make loss *declared*, not impossible.
- **The components artifact, seed derivation, and the framework lenses** — positions 03, 04 and 05.

## Risks

- **Revision is harder for a model than authoring.** "Change this and leave the rest" over a long artifact is exactly what models do badly; the likely failure is a wholesale rewrite that trips id continuity and burns the retry budget. This is the position's central bet, and #215 says stage 2 has twice come within one attempt of exhausting three. Treat the budget decision as forced here rather than deferred again.
- **Two modes double the prompt surface** that #215 already finds tight.
- **Declared removal becomes a loophole** if the model learns to declare everything. The guard makes loss visible, not rare; if declarations become noise, that is a finding for the next position, not a reason to gate merit.
- **Stage-as-data holds or it does not.** Position 01 called this bet untested. A second input, a second mode, and a per-stage prompt pair are its first real load; if the table has to widen, that is the finding.

## Testing

What would prove the Outcome, hermetically: a re-run with a previous artifact present has that artifact and the feedback in its prompt; a row present before is present after or named as removed, and the guard catches a silent drop; a `settled` decision survives, and cannot be removed by declaration alone; an operator who un-settles first is allowed to lose it; feedback anchored to a non-decision row reaches the prompt; a first run with nothing on disk is unchanged from today.

One real run against `.tmp/roadmap-smoke.cfp-concept.md` giving **real feedback on a real proposal**, including feedback that redirects rather than confirms — the loop is the thing under test, so a run that receives no feedback tests nothing (arc lesson 1: read stdout and stderr together, not just the artifact). Measure id continuity across that revision and compare it to the 85/60/30/25 regeneration baseline: that number is the position's headline result.

Tests follow `TESTING.md` with invokers stubbed.

## Acceptance criteria

- An operator can write feedback against any row kind, re-enter, and see it in the prompt the revision was authored from.
- A row present before the revision is present after, or named as removed.
- A `settled` decision survives its id and status.
- A run with no prior artifact is byte-for-byte unchanged.
- `ROADMAP_FORMAT.md` documents the feedback row, the removal record, and both guards, naming the code that enforces each.
- **`BACKLOG.md` #208 is reconciled when this ships** — arc position 02 marked shipped, the Framing bullet's "there is no feedback path" paragraph replaced by what landed, arc lesson 4's regenerate-not-revise finding marked superseded, and any deferral this plan creates filed rather than left implicit. Authoring the plan does not discharge this; shipping does.

## Deferred

- Whether a revision honored its feedback, and any measurement of it.
- Feedback that spans artifacts, or that redirects an upstream stage from a downstream one.
- An interactive review walk (#208 already names it a follow-up).
- #215's retry-budget decision, which this position forces but does not own.

## Input

This plan consumes contracts position 01 already ships:

- `roadmap.py:_render_stage_prompt` — receives `slug`, `brief`, and the artifacts of stages *below* the one running; this plan widens what it receives to include the stage's own previous artifact and its unresolved feedback.
- `_corrections_block` — already prepends corrections to a retried stage prompt, replace-never-accumulate, with exactly one producer today (gate violations); this is the seam feedback threads through, widened in place.
- The stage table's `(prompt file, artifact path, parser, renderer, gate set)` row shape — already data, so a second prompt file per stage needs no orchestrator edit.
- `01-domain.md` and `02-constraints.md` as shipped by position 01: their row kinds (entity, business rule, workflow, quality attribute with exactly one disposition, constraint, decision), their anchor concept, and the `settled` decision status.
- The eight relation gates in `roadmap_gates.py`, which *return* `Violation`s and never raise, and the bounded retry with `--from-stage N` re-entry semantics.
