# Teach plan-tool through coding-assistant requests

## Outcome

A reader can ask a coding assistant to create a grounded seed, drive the plan-tool skill, monitor its results and bring decisions back for review, using the demos and learning examples as a coherent guide.

## Overview

The README introduces plan-tool through assistant-driven work. The planning demo
and learning examples still lead with shell commands or ask the reader to write
a seed. Convert the learning journey to concrete requests to the coding assistant,
with visible artifacts and honest result reporting. Keep CLI commands available
as supporting operator references.

## Problem statement

The first-use story changes when readers leave the README: they are asked to
operate individual stages rather than express an outcome and review the
assistant's work. A generated plan alone also hides the important part of the
workflow: the assistant monitors running work, reads saved results, judges
findings, reports uncertainty and asks the owner about material decisions.

## Architecture

Use the existing skill and shared directives as the workflow authority. Demo
narratives show what the user asks, what the assistant does, which artifact the
user reviews and what happens next. The assistant grounds and authors the seed
from the repository and the user's outcome; the user supplies constraints and
reviews scope instead of writing seed markdown or selecting every CLI flag.

Keep the current dark-mode-toggle planning scenario and TTRPG roadmap scenario.
A small starter or authored illustration may support the existing planning
scenario, but replacing it with the earlier task-list scenario or introducing a
third demo is outside this effort. The earlier task-list commit is useful design
input only. Preserve `docs/demos/` as the demo home and the four existing remote
demo branch names. Remote replacement remains separately authorized.

The assistant monitors the original command until confirmed exit, reports useful
progress with the current stage and evidence location, reads saved audits by
coverage and qualification, makes bounded judged corrections, and surfaces
material scope/design choices. Quiet output is not failure; an exit code alone
is not a clean result. A resumed request checks persisted state and live work
before starting another command. Use existing run/status/log surfaces; do not
invent monitoring capabilities or change their behavior.

Show the bare-plan audit before detail authoring and the detail-grounded audit
afterward. Planning stops before implementation unless the user requests it.
Local Jira export includes its paired developer handoff and does not imply
remote issue creation. An execution request includes the post-run code
reconciliation and review tail. The roadmap example retains accepted-head,
feedback/candidate, settlement and seed-materialization boundaries.

## In scope

- Convert the planning and roadmap demo guides and demo index to assistant-led
  requests for seed creation, planning, monitoring, review, resumption and the
  appropriate output. Refresh presenter guidance and local checkpoint cards
  where the current demo preparation is available.
- Align the README's first-plan prompts, the situation examples in
  `docs/how-to/use-cases.md`, `docs/how-to/choose-a-starting-point.md` and
  `docs/how-to/common-workflows.md`, and the RUNBOOK's entry route with that
  same interaction. Preserve specialist command procedures as supporting
  references; do not rewrite the entire command catalog or historical decks.
- Make example inputs and inspectable outputs easy to find. State whether each
  is an authored illustration, a prepared fixture, or a captured run. Update
  relevant retained demo fixtures, local seeds and references to current formats
  and real paths without registering sample plans as product work.
- Reconcile `handoffs/2026-10-21-demo-refresh.md` and demo status labels with the
  delivered local changes, actual verification and remaining publication work.

## Scope guardrails

This is a documentation and example conversion using existing skill behavior.
No CLI, prompt-template, schema, installer or monitoring implementation changes
belong here. Do not introduce a new workflow gate, automated prose-quality
checker, background service, parallel runner, broad docs reorganization or new
scenario. Do not push replacement demo refs, publish an Artifact, create remote
Jira issues, merge a PR, or change release tags or repository visibility as part
of the plan. Keep private recovery material private. Existing procedural
contracts remain authoritative; do not copy them into a new competing policy.

## Scope of work

Establish a single assistant-led demo narrative and its user/assistant/reviewer
responsibilities, convert the two demos and their local example artifacts,
propagate matching request examples through the learning entry points, then
validate the end-to-end reading and execution story and update preparation
status. Keep the plan small and group work by a reviewable reader outcome.

## Allowed behavior changes

Only documentation, presentation instructions, example/reference content and
preparation-status records change. Existing tool and skill behavior remains.

## Allowed reorganization

Keep established documentation destinations. Move or replace a sample only when
needed to keep the retained scenario and its artifact links coherent.

## Risks

A request-first rewrite can conceal prerequisites, remove useful operator detail,
blur owner decisions with assistant corrections, or claim that fixtures prove a
live run. Retain installation/backend prerequisites, link exact procedures,
show the two audit gates and keep provenance and actual coverage visible.
Unavailable private scratch preparations must not block the maintained guides;
record their absence rather than inventing replacement results.

## Testing

Review the journey from the README in a consuming repository: ask the assistant
to author a seed, inspect its scope and References, follow create and the bare
report, then detail and its grounded report, and inspect the selected output.
Use one available authenticated backend for a bounded live planning-to-local-Jira
rehearsal; retain actual command completion, report paths, coverage,
qualification and paired output evidence. If runtime/authentication is
unavailable, record the blocked live verification explicitly and retain the
needs-verification label rather than claiming success. Remote publication and
an example implementation run are not required for this authoring demo.

Check the larger roadmap narrative against its current procedure and contracts;
a fresh full TTRPG run and all four publication deliverables are outside this
conversion. Review monitoring and resumption requests against existing read-only
state surfaces. Check local links, parse retained plan/detail fixtures, lint
available local story exports, and run appropriate repository checks. Do not
add tests that merely match documentation wording.

## Acceptance criteria

- The learning journey starts with a request to use the plan-tool skill and
  author a grounded, scope-fenced seed; it does not require the reader to
  hand-author the seed or operate every stage.
- Both demo guides and the named learning entry points explain the assistant's
  actions, the owner's review/decision points and the artifacts/results to inspect.
- Monitoring and resume examples retain the original command's completion
  boundary, distinguish progress from audit verdicts and provider failures,
  and avoid overlapping invocations or quiet-process termination.
- The bare and detail-grounded audit gates remain ordered and visible; planning,
  execution and local story export requests retain their separate completion
  contracts and authorization boundaries.
- Current paths and formats resolve, authored/prepared/captured evidence is
  labeled accurately, and samples remain outside the active product manifest.
- The local rehearsal has actual evidence or a named external blocker and an
  explicit unverified status. The handoff and demo index agree with that result.

## Out of scope

No tool behavior changes, new demo scenario, exhaustive conversion of command
reference examples, rewrite of historical evidence or decks, full TTRPG
regeneration, remote publication, or release workflow changes.

## Stop / defer

Record unrelated product defects in BUG_BACKLOG.md and future capabilities in
BACKLOG.md. If the narrative requires behavior the skill does not supply, name
the gap instead of implementing it or asserting that it exists.

## Deferred

Remote demo branch publication and the release workflow retain their separate
owner and approval boundary.

## References

- README.md — assistant-first positioning, installation and first-plan requests.
- docs/demos/README.md — demo discovery and preparation status.
- docs/demos/planning-demo.md — the retained dark-mode planning scenario.
- docs/demos/roadmap-demo.md — the retained advanced roadmap scenario.
- docs/how-to/use-cases.md — situation-based learning examples.
- docs/how-to/choose-a-starting-point.md — input selection examples.
- docs/how-to/common-workflows.md — workflow entry and operator procedures.
- RUNBOOK.md — operational entry route and monitoring/recovery procedures.
- integrations/shared/DIRECTIVES.md — canonical seed, audit, monitoring and execution rules.
- integrations/codex/SKILL.md — a supported assistant integration and request routing.
- SEED_FORMAT.md — seed scope contract and References requirements.
- PLAN_FORMAT.md — plan artifact contract.
- DETAIL_FORMAT.md — detail artifact contract.
- JIRA_FORMAT.md — local story export and paired developer handoff.
- ROADMAP_FORMAT.md — immutable accepted-head artifact contract.
- ROADMAP_FEEDBACK_FORMAT.md — mutable ledger and candidate route contract.
- handoffs/2026-10-21-demo-refresh.md — current preparation and publication boundary.
- docs/reference/documentation-style.md — live documentation structure and review.
