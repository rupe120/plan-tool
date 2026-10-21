> **Auto-archived**: this plan was swept on 2026-08-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Roadmap 02 Feedback Channel
intent: Give the human a durable, reviewable way to redirect a subjective roadmap
  proposal, so a re-run revises their contribution and reflects its understanding
  instead of regenerating over it.
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Add lifecycle feedback rows, proposed responses, and cited removals
  intent: Let a reviewer state a natural-language redirect against a precise target
    and keep that source visible until the reviewer, rather than the model, closes
    it.
  files:
  - plan_tool/roadmap_artifacts.py
  - tests/test_roadmap_artifacts.py
  complexity: high
  change_type: feature
  detail: docs/implementation-plans/plan-details/roadmap-02-feedback-channel/01-lifecycle-feedback-rows-proposed.md
  status: done
- id: 2
  title: Add predecessor continuity, feedback-integrity, and settled-choice gates
  intent: Prevent a revision from silently losing a design row, rewriting the reviewer’s
    request, or changing a settled decision’s actual choice.
  files:
  - plan_tool/roadmap_gates.py
  - tests/test_roadmap_gates.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/roadmap-02-feedback-channel/02-predecessor-continuity-feedback.md
  status: done
- id: 3
  title: Record revision feedback delivery without recording the feedback text
  intent: Make the delivery and review lifecycle auditable without duplicating potentially
    sensitive human guidance into the local run log.
  files:
  - plan_tool/run_log.py
  - plan_tool/data_contract.py
  - DATA_CONTRACT.md
  - README.md
  - tests/test_run_log.py
  complexity: low
  change_type: feature
  detail: docs/implementation-plans/plan-details/roadmap-02-feedback-channel/03-record-revision-feedback-delivery.md
  status: done
- id: 4
  title: Add the shared revision prompt and its LLM reflection contract
  intent: Have the model explain its proposed handling of each open feedback item,
    while keeping first-run authoring prompts unchanged.
  files:
  - plan_tool/roadmap.py
  - TESTING.md
  - tests/test_roadmap.py
  creates:
  - plan_tool/prompts/roadmap-revision.md
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 2
  detail: docs/implementation-plans/plan-details/roadmap-02-feedback-channel/04-shared-revision-prompt-its-llm.md
  status: done
- id: 5
  title: Load a stage’s predecessor and build the revision envelope
  intent: Give the gates the exact prior artifact and let feedback targets resolve
    against what the reviewer actually read, including a row the revision removes.
  files:
  - plan_tool/roadmap.py
  - tests/test_roadmap.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  - 4
  detail: docs/implementation-plans/plan-details/roadmap-02-feedback-channel/05-load-stage-predecessor-build-temporal.md
  status: done
- id: 6
  title: Write lifecycle-preserving revisions without automatic feedback removal
  intent: 'Close the mechanical loop without falsely closing the human review loop:
    a model can propose a response, but only a human can remove or defer feedback.'
  files:
  - plan_tool/roadmap.py
  - tests/test_roadmap.py
  complexity: high
  change_type: feature
  depends_on:
  - 3
  - 4
  - 5
  detail: docs/implementation-plans/plan-details/roadmap-02-feedback-channel/06-write-lifecycle-preserving-revisions.md
  status: done
- id: 7
  title: Surface feedback awaiting review in the roadmap completion summary
  intent: Point the operator to the model’s reflected response and the next document-native
    action without adding a TTY or another command.
  files:
  - plan_tool/cli/roadmap_cmd.py
  - tests/cli/test_roadmap_cmd.py
  complexity: low
  change_type: feature
  depends_on:
  - 6
  detail: docs/implementation-plans/plan-details/roadmap-02-feedback-channel/07-surface-feedback-awaiting-review.md
  status: done
- id: 8
  title: Document feedback lifecycle, targets, and the roadmap review loop
  intent: Make a natural-language feedback-and-response exchange discoverable without
    requiring the operator to infer state transitions from YAML or source.
  files:
  - ROADMAP_FORMAT.md
  - RUNBOOK.md
  - USE_CASES.md
  - CAPABILITIES.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 1
  - 2
  - 4
  - 5
  - 6
  - 7
  detail: docs/implementation-plans/plan-details/roadmap-02-feedback-channel/08-document-feedback-lifecycle-targets.md
  status: done
- id: 9
  title: Exercise real redirect and clarification feedback and record human outcomes
  intent: Demonstrate that people can understand and control the revision loop; id
    continuity remains a safety metric, not a proxy for feedback quality.
  files:
  - BACKLOG.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 6
  - 7
  detail: docs/implementation-plans/plan-details/roadmap-02-feedback-channel/09-exercise-real-redirect-clarification.md
  status: done
- id: 10
  title: Reconcile BACKLOG 208 and sweep the roadmap architecture description
  intent: Leave no project document describing automatic feedback consumption or re-entry
    regeneration after the lifecycle-preserving loop ships.
  files:
  - BACKLOG.md
  - docs/ARCHITECTURE.md
  - CLAUDE.md
  - integrations/claude/SKILL.md
  complexity: low
  change_type: non-code
  depends_on:
  - 8
  - 9
  detail: docs/implementation-plans/plan-details/roadmap-02-feedback-channel/10-reconcile-backlog-208-sweep-roadmap.md
  status: done
---
# Roadmap 02 Feedback Channel

## Overview

Arc position 02 of the roadmap-NN-* group (anchor: BACKLOG.md #208) makes a
re-run roadmap stage revise its previous artifact against human feedback rather
than re-authoring from the brief. The operator writes ordinary natural-language
feedback against a row or against the artifact as a whole, re-enters at that
stage with --from-stage N, and sees both the changed proposal and the model's
plain-language account of what it proposed to do. The model cannot resolve,
delete, or defer feedback on the human's behalf.

This is a roadmap-only, document-native first increment. The editor and the
committed artifact remain the review surface; there is no TTY interview, no
new command, and no generic feedback framework for the rest of plan-tool. The
increment does make the review exchange legible enough to inform that later
framework: source feedback is stable, the model's response is visible, and the
human decides whether to close, reopen, or defer it.

Position 01 shipped stages 1–2 (01-domain.md and 02-constraints.md), their
eight relation gates, bounded retry, and --from-stage re-entry. This position
adds no components artifact, plan derivation, or framework lens.

## Problem statement

The proposal is subjective in its essence. There is no correct roadmap for a
brief, only a defensible one, and the only quality function is the human
reading it. A useful tool therefore needs more than a one-shot proposal: it
must let a human say, in their own words, what is wrong or missing, let the LLM
interpret that direction against the existing artifact, and make the proposed
interpretation easy to inspect.

Today re-proposal is regeneration. roadmap.py:_render_stage_prompt receives
the brief and artifacts below the current stage, but never the stage's own
previous artifact. A --from-stage N re-entry therefore starts that artifact
again from the brief. On two identical-input runs measured 2026-08-02, entity
ids were 85% shared, workflow ids 60%, business-rule ids 30%, and decision ids
25%; none of 11 shared entities retained the same field-name set. A reviewer
cannot safely refer to a row that the re-run might recreate with different
meaning.

There is also no feedback channel. _corrections_block can feed a retry gate
violation to the next attempt, but a human cannot say “this decomposition is
wrong because X,” and can only replace the artifact text themselves. That
does not use the LLM's ability to interpret a concise, high-level correction
against a detailed proposal.

Finally, prompt delivery alone is not a usable review contract. Automatically
clearing feedback after a write gives no way to distinguish “the model saw it”
from “the human accepted its response.” Git history is useful evidence, but it
is not the normal interaction path a reviewer needs to use.

## Architecture

### Revision, not regeneration

A stage re-run over an artifact of its own receives that exact artifact and
revises it. A first run, with no artifact on disk, follows the position-01
authoring path byte-for-byte. Revision mode wraps the stage's existing
authoring contract; it does not bloat or fork the authoring prompt. Its inputs
are explicitly delimited as the prior artifact and the active feedback block,
and its output remains the complete artifact that the existing parser,
renderer, and gates own.

### Feedback has a target, a source, and a human-owned lifecycle

Each artifact gets an optional feedback collection. A feedback row has a stable
id, a target, a request, a state, and an optional proposed_response:

- target is an explicit tagged union: artifact for feedback on the artifact's
  overall shape, or row plus a row_id for feedback on one design row in this
  artifact. There is no magic root-id sentinel.
- request is the human's natural-language guidance. The model must copy it
  unchanged; it is source input, not model-authored prose.
- state is open, awaiting-review, or deferred. Only open rows are active
  feedback and enter the next revision prompt. A successful revision changes
  an open row only to awaiting-review and supplies a proposed_response. A
  deferred row is retained but not sent as active guidance; its text still
  travels to the model inside the prior artifact, because a revision carries
  that artifact whole. Deferring parks a request, it does not hide it. The
  operator reopens it by changing it to open and clearing or replacing its
  response.
- proposed_response is the model's concise reflection: which rows it proposes
  to alter, preserve, or remove and any clarification it still needs. It is
  review aid, never a claim the tool treats as true.

The human closes feedback by deleting its awaiting-review row after reading
the response and the artifact diff. Git then supplies the historical record.
The model may not delete feedback rows; a row absent from the artifact it
received is already a deliberate operator action. This avoids an accumulating
retry instruction while still preventing automatic consumption. Feedback and
removal records are operational review metadata: they are excluded from the
design-row prose-inventory gate.

Feedback is local to the artifact that contains it in this position. Re-running
stage 1 hands stage 2 the revised 01-domain.md, as it already does for every
upstream artifact, but does not hand stage 1's active feedback text to stage 2.
A reviewer who wants a cross-artifact instruction records it in each affected
artifact. A later generic feedback position may introduce explicit propagation
semantics; silently applying a local comment everywhere is not safe.

### Deterministic safeguards preserve authorship, not merit

The prior artifact becomes part of the gate envelope on a revision.

- Design-row continuity remains a set check: every predecessor design-row id
  is present in the revision or appears in a removal record. A removal record
  names the removed row, gives a non-blank rationale, and cites one or more
  predecessor feedback ids that were open — a deferred row is one the reviewer
  parked and an awaiting-review row is one the model already answered, so
  neither authorizes a removal. A model therefore cannot silently delete a row
  or declare arbitrary cleanup without a reviewer-originated reason. A removal
  record is model-permanent and reviewer-prunable: the model may never drop
  one, and deleting it in the editor is how the reviewer asks for a removed
  row back.
- Feedback integrity is structural. Every predecessor feedback row survives;
  its id, target, and request are immutable *to the model*. The only model
  transition is open to awaiting-review with a non-blank proposed_response.
  Awaiting-review and deferred rows are carried unchanged. Targets resolve
  against the predecessor inventory, so feedback can request removal of the
  row it names. Immutability does not bind the reviewer: when the model
  answers a request with a clarifying question, the reviewer answers it by
  amending that row's request in place (or adding a follow-up row) and
  reopening it. The predecessor is snapshotted after the reviewer's edits, so
  the amended request is the source the gate compares against. Reopening an
  unchanged request only re-asks the model the same ambiguous thing.
- Model-authored review metadata is refused in the attempt loop rather than
  by a gate, because a predecessor-free stage has no gate that could see it.
  The three gates below are not the whole guard.
- Settled finality protects a decision's actual commitment. A predecessor
  decision still marked settled must retain its id, status, chosen_option, and
  anchor. The prompt also tells the model to preserve its rationale and
  rejected alternatives; the gate deliberately does not pretend it can decide
  whether a wording change has the same meaning. An operator who wants a
  substantive revision first changes the prior decision to pending.

These guards intentionally do not judge whether the feedback was honored or
whether a change is a good roadmap decision. They judge only visible,
deterministic facts: source retention, explicit lifecycle state, identifiers,
declared removals, and fields whose equality has unambiguous human meaning.

### LLM reflection makes document review more efficient

The shared revision prompt asks the model to preserve the artifact unless
feedback or a correction requires a change. For each open feedback id, it must
return a proposed_response tied to that id, naming the affected design ids and
asking one focused question when the request is ambiguous or implies a scope
the model cannot infer from the reviewer's words. The model does not
write resolved or deferred states. This gives the reviewer a compact statement
of the model's understanding before they decide whether the proposed change is
acceptable; it is not an automated agreement check.

The CLI stays non-interactive but reports the number of feedback rows awaiting
human review — on a completed re-entry and on one a later stage exhausted
alike, since a stage can answer feedback and write it before a subsequent
stage runs out of attempts — and points to the artifact and the
reopen/defer/close actions. This is the smallest useful interaction: the
human works in a normal editor, and the LLM's response is visible in the same
reviewable document.

### Prompt capacity and logging

Revision mode adds a full predecessor artifact plus active feedback, so prompt
pressure is an operational risk. It imposes no semantic, length, shape, or
count limit on a human request. Instead it sends only open feedback as active
instructions, retains the existing total-prompt budget advisory in the shell
path, and continues recording prompt_bytes for every attempt. The real-run
exercise records whether that advisory fired and the attempt count; it does
not turn prompt size into a feedback-quality gate.

The run log records a revision-feedback-delivered event with stage number,
predecessor artifact digest, feedback ids, and counts by lifecycle state. It
does not record raw feedback or model response text, which already live in the
committed artifact and may contain project-sensitive context.

### Touched surfaces and boundaries

roadmap_artifacts.py owns the target union, lifecycle vocabulary, feedback
row, response field, removal record, parser, and renderer. roadmap_gates.py
owns three predecessor-aware gates — continuity (with cited-removal as one of
its rules), feedback-integrity, and settled-choice; it remains a pure
relation-gate layer that returns violations. roadmap.py reads the predecessor before any overwrite, renders
revision mode, provides the predecessor envelope, persists the feedback state
transition the model made — it never edits a feedback row itself — and emits
the run-log event. cli/roadmap_cmd.py only renders
the operator summary. ROADMAP_FORMAT.md and the operator docs own the
discoverable workflow.

The one-way dependency line remains roadmap_artifacts.py → roadmap_gates.py →
roadmap.py → cli/roadmap_cmd.py. A stage is still data, and the revision wrapper
is shared rather than a per-stage branch.

## Input

This plan extends contracts position 01 already ships:

- roadmap.py:_render_stage_prompt, which currently receives slug, brief, and
  upstream artifacts. Revision mode adds the stage's predecessor artifact and
  a separately rendered active-feedback block.
- _corrections_block, the existing replace-never-accumulate gate-retry seam.
  Feedback is not put in this correction channel: it is stable author input
  across retries, while corrections replace one another per attempt.
- The stage table's prompt file, artifact path, parser, renderer, and gate-set
  data shape. The shared revision wrapper retains that shape.
- The domain and constraints artifact rows, their anchors, their settled and
  pending decision status, and the eight relation gates.
- The shell path's existing total-prompt budget advisory and the roadmap
  run-log's per-attempt prompt_bytes event.

## References

- [Long context prompting tips — Claude Docs](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/long-context-tips) —
  the prior artifact and active feedback need clear document boundaries and a
  stable instruction ordering.
- [Prompting best practices (Claude 4) — Claude Docs](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/claude-4-best-practices) —
  scoped editing and an explicit output contract support a revision that
  changes named rows while retaining the rest.
- [Increase output consistency — Claude Docs](https://docs.anthropic.com/en/docs/test-and-evaluate/strengthen-guardrails/increase-consistency) —
  structured output examples and stable schemas are relevant to feedback
  lifecycle preservation.
- [Claude Code CLI reference](https://docs.claude.com/en/docs/claude-code/cli-reference)
  and [headless mode](https://docs.claude.com/en/docs/claude-code/headless) —
  the invocation and exit-status contract below the stage orchestrator.
- [Prompt caching — Claude Docs](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching) —
  relevant when measuring the revision prompt because prior-artifact prefixes
  can be stable across retries.
- [YAML 1.2.2](https://yaml.org/spec/1.2.2/) — the normative frontmatter
  grammar for tagged targets, lifecycle rows, and removal records.

## Steps

See the steps block in the frontmatter.

## Out of scope

- Judging whether a revision honored feedback, scoring the proposal, or
  automatically transitioning feedback from awaiting-review to closed. A
  human-recorded outcome in the real-run exercise is evidence, not a gate.
- A TTY review walk, confirmation prompt, new feedback subcommand, or a
  generic feedback framework for create, detail, audit, or run. This position
  remains non-interactive and roadmap-only.
- Cross-artifact feedback propagation. Local feedback affects its artifact;
  reviewers explicitly place an instruction in each artifact it should guide.
- Any cap or rejection based on the length, shape, count, or semantics of
  feedback. The existing prompt-budget warning remains operational advice, not
  a feedback gate.
- A second store, sidecar, or hidden feedback state. The artifact carries the
  active review state; Git history records a feedback row after a human closes
  it.
- General value-stability guarantees for non-settled design rows. Continuity
  makes disappearance declared, not arbitrary semantic rewrites decidable.
- Optimistic write conflicts for simultaneous editors. This local,
  document-native loop assumes the reviewer edits before invoking; a general
  multiwriter interaction surface owns that later safety mechanism.
- Components, seed derivation, framework lenses, and any roadmap completion or
  convergence verdict.

## Risks

- Revision is harder for a model than authoring. A wholesale rewrite can still
  retain ids while changing too much, or consume the retry budget on a
  structural violation. The predecessor, source-preservation guards, focused
  responses, and human diff make the failure visible; they do not make a
  subjective proposal objectively correct.
- A broad artifact-level feedback item can authorize many cited removals.
  Requiring an explicit rationale and feedback-id citation exposes that action,
  but the human must review the diff and the proposed response. This is
  deliberate human authority, not a loophole for a merit gate.
- The lifecycle adds frontmatter complexity. The documentation must show a
  complete short example for open, awaiting-review, deferred, reopened, and
  human-closed feedback; otherwise a reviewer may accidentally resend a
  response or remove a request too early.
- Stage 2 already has little retry margin. The revision's predecessor and
  active-feedback content can increase prompt cost or exhaust the budget.
  Total-prompt advisory and real-run measurement make the pressure observable;
  calibration of MAX_STAGE_ATTEMPTS remains BACKLOG #215's separate decision.
- Local-only feedback can require deliberate duplication for a cross-artifact
  concern. That is accepted here because automatic propagation has ambiguous
  scope and would make the first interaction mechanism less trustworthy.
- Revision mode is selected by predecessor presence, not feedback presence, so
  a re-entry that carries no feedback is still a revision: the model may add
  design rows but cannot drop one, because every removal must cite a feedback
  id and none exists. A reviewer who rewrote the brief and expected a fresh
  authoring pass instead gets a locked revision. The escape is deleting the
  artifact file, which the operator docs must state — it is not discoverable
  from the error.
- A design row that a settled decision anchors to cannot be removed at all
  until the reviewer un-settles that decision. A redirect asking for the drop
  is answered by a refusal and a proposed_response naming the un-settle, not
  by the removal; left unstated the stage oscillates between the settled gate
  and the dangling-anchor check until its budget is gone. This fires inside a
  single artifact, so placing feedback elsewhere does not help.
- A domain redirect that drops a design row can exhaust the constraints
  stage. On a --from-stage 1 run, if stage 1 removes an entity, 02-constraints
  must drop the constraint anchored to it — but an uncited removal is a
  violation and keeping the row trips the shipped anchor check, so the stage
  can spend its whole budget and the run exits 1 with no 02-constraints.md.
  The design's answer is that the reviewer places a matching request in each
  affected artifact, which requires predicting what the model will remove; the
  operator docs must say so before a reviewer pays for it.
- Open feedback in an artifact below the re-entry point is never delivered. On
  a --from-stage 2 run, 01-domain.md is loaded as upstream, gets no predecessor
  and no revision, and its open rows are neither sent nor answered. The
  reviewer sees no proposed_response and cannot distinguish "the model ignored
  me" from "I re-entered above it", so the docs must say that feedback is
  delivered only by re-entering at that artifact's own stage.
- The stage-as-data model must carry an additional revision input without
  leaking stage-specific branches into the orchestrator. A shared wrapper and
  the existing per-stage parser/gate fields are the test of that structural bet.

## Testing

Hermetic tests prove deterministic contracts, never semantic merit:

- feedback parse/render round-trips the tagged artifact and row targets,
  lifecycle states, optional response, and cited removals; invalid target
  combinations and invalid state/response combinations fail shape validation;
- a revision target resolves against the predecessor row inventory, including a
  target that the revision removes; artifact-level feedback needs no synthetic
  row id;
- a model response cannot delete feedback or mutate its id, target, or request,
  and cannot author a feedback row or removal record its predecessor did not
  carry — including on a predecessor-free stage, where no gate can see it;
  an open row must become awaiting-review with a non-blank response, while
  awaiting-review and deferred rows survive unchanged; deleting a row before
  the run is accepted as a human close because it is absent from the
  predecessor;
- every predecessor design row survives or has a rationale-bearing removal
  cited to predecessor feedback; a settled decision cannot change status,
  chosen option, or anchor unless the human changed the predecessor status to
  pending first;
- revision prompts contain the prior artifact and only open feedback in
  explicit blocks, require a per-feedback reflection, and retain the existing
  gate-correction retry behavior. First-run prompts and output remain
  byte-for-byte unchanged;
- a delivered revision emits ids, counts, stage, and artifact digest to the
  run log but never the request or response text;
- a stage-1 local feedback revision passes the revised domain artifact to
  stage 2 without treating stage-1 feedback as stage-2 active instruction;
- the completion summary identifies awaiting-review feedback and gives the
  document-native next action;
- a revision path continues to surface the existing total-prompt budget
  advisory and logs prompt_bytes. No test makes the warning fail a run.

One real run against .tmp/roadmap-smoke.cfp-concept.md uses at least two
non-confirming items: one domain redirect and one genuinely ambiguous request.
The reviewer records, per feedback id, whether the model's reflected response
was accepted, partially accepted, declined, or required clarification; the
record also notes feedback state after review, ids retained/removed, prompt
bytes, advisory level, attempts, and cost. This is a human evaluation of the
loop, not a model-scored quality test. Compare id continuity to the existing
85/60/30/25 regeneration baseline as a safety observation, never as the
headline proof of success.

Tests follow TESTING.md with invokers stubbed.

Per-step test strategy:

- steps 1–7 are feature work and add or update focused tests before completion.
- steps 8–10 are non-code work verified against their rendered contracts,
  operator examples, and the recorded real-run evidence.

## Acceptance criteria

- A reviewer can add a stable, natural-language feedback row targeting either
  the current artifact or a current design row, then re-enter at its stage.
- A revision receives the exact predecessor artifact plus only open feedback
  as active guidance and leaves first-run behavior byte-for-byte unchanged.
- For every open feedback row, the written artifact retains the reviewer's
  request — unchanged but for trailing whitespace, which the integrity gate
  normalizes before comparing so a YAML block scalar re-emitted without its
  trailing newline is not a false violation — and carries an awaiting-review
  model response; a model cannot
  close, defer, or delete it — nor author one. A reply carrying a feedback row
  or removal record its predecessor did not have is rejected and retried, and
  on a predecessor-free stage any such row is rejected, so review metadata is
  reviewer-originated on every path.
- The reviewer can close feedback by removing it, defer it so it is no longer
  sent as active guidance, or reopen it for another revision, entirely in the
  artifact.
- A predecessor artifact that exists but cannot be read or parsed fails
  pre-flight — no invoke, no write — and never degrades to authoring mode.
- A predecessor design row is retained or explicitly removed with a rationale
  and cited feedback id. A settled predecessor decision retains its status,
  chosen option, and anchor until the human un-settles it.
- The run log proves delivery with ids, counts, and predecessor digest while
  omitting feedback and response text.
- The roadmap completion summary identifies feedback awaiting review without
  adding a TTY branch, prompt, or new command.
- The operator docs warn about every trap the Risks route to them: the
  delete-the-file escape from a locked no-feedback revision, the removal-
  bearing redirect that can exhaust the constraints stage, open feedback
  below the re-entry point never being delivered, and the un-settle-first
  block on removing a row a settled decision anchors to. The criterion is
  the Risks' own set, not a fixed count — a Risk that routes a warning to
  the docs and is not covered here is a gap.
- ROADMAP_FORMAT.md documents the exact target union, lifecycle states,
  response contract, human-close action, removal citation, local-only scope,
  and enforcing code. RUNBOOK.md and USE_CASES.md include a concise end-to-end
  operator example.
- The real-run record contains redirect and clarification feedback plus the
  reviewer’s human outcomes, id-continuity observation, prompt-budget
  observation, retries, and cost.
- BACKLOG.md #208 is reconciled only when this ships: position 02 is marked
  shipped, the no-feedback and regenerate-not-revise statements are replaced,
  and any newly created deferral is filed explicitly.
- CLAUDE.md's roadmap architecture paragraph and integrations/claude/SKILL.md
  no longer tell a reader that a re-entry overwrites a hand-edited artifact or
  that editing in place is the only way to redirect a stage.

## Deferred

- A generic interactive feedback framework and review walk across all
  plan-tool authoring and audit flows.
- Cross-artifact propagation, including a downstream artifact intentionally
  redirecting an upstream stage.
- Optimistic conflict handling for feedback edited while a model invocation is
  in flight.
- Automatic semantic evaluation of feedback outcomes or a roadmap done-ness
  verdict.
- BACKLOG #215's retry-budget calibration decision. This position measures
  revision prompt pressure but does not change the budget.
