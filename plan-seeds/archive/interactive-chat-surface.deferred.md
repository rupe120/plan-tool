> **Deferred 2026-08-19** — This broad interactive-chat hand-off is not part
> of #255. Preserve it as context for a future demonstrated workflow need; do
> not re-seed it merely to record a decomposition decision. #255 is completed;
> its consumed seed is `plan-seeds/archive/decomposition-decision-recorder.completed.md`.

# Plan seed: interactive chat surface for roadmap revision and plan-authoring workflow direction

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing plan-seeds/interactive-chat-surface.md
```

It is **not** itself a plan — `plan-tool create` consumes the prose below and
proposes a step decomposition; the author then runs `plan-tool detail` per
step.

---

## Outcome

An operator directs roadmap revision and plan-authoring/decomposition
judgment through a real, natural, multi-turn conversation — handed off to the
configured backend's own interactive session, never a bespoke chat loop
inside `plan_tool` — and can ask, at any point and only when they choose to,
that a decision be recorded. Roadmap decisions land in its existing, versioned
feedback/decision rows; project-level settled decisions live in the tracked,
uncategorized `decisions` list in `.plan-tool/project.json`. The tool never infers when the
conversation has concluded, never judges its quality or length, and never
records a decision the user did not explicitly ask for.

## Problem statement

Decomposition and roadmap-revision judgment already happens almost
exclusively in ad hoc chat sessions like the one that produced this seed —
not in any `plan-tool`-native surface — and its conclusions currently
evaporate into conversation history or hand-transcribed backlog prose instead
of landing anywhere the tool can see. Concretely, today:

- **Roadmap feedback requires hand-editing YAML.** Per
  `docs/ROADMAP_WALKTHROUGH.md` § "Re-entering with feedback": submitting
  feedback means uncommenting a stub at the end of an artifact's frontmatter,
  filling in fields by hand, and re-entering at that artifact's own stage.
  There is no conversational or CLI path to the same result.
- **`create`'s decomposition question is asked exactly once and never
  revisited.** Distill's "one plan, or many?" pass (tightened by BACKLOG
  #249) is the only place a plan's split/single verdict is decided. A prior
  investigation found 17 step-altitude granularity assessments for one plan's
  life, while the plan-altitude question that mattered left no project-level
  record. #255 establishes the smallest durable record for such conclusions.
- **The automated alternative was tried and failed twice.** The retired
  region-trending `spinning`/`FORK_*` layer (BACKLOG #251) that used to flag
  "this looks mis-decomposed" was starved of input (0.13% of findings) and
  its one lifetime firing was a false alarm; widening its input (the
  withdrawn `audit-trajectory-instrumentation` plan, BACKLOG #172) was
  measured to fire on 15 of 24 history prefixes instead. Re-asking the
  plan-altitude question automatically on every audit round risks the identical
  "fires on every plan, answered `single`, operators learn to skim" churn.

The fix is not a better automated detector; every attempt at one has already
failed here. It is giving the conversation that already happens somewhere to
record its own conclusion.

## Architecture

### Bootstrap, never an engine

Two call sites, one shared shape: a deterministic, no-Claude-call function
assembles a briefing (the plan or roadmap artifact, its steps/rows, open
feedback, settled decisions, recent audit/reconcile history) and hands off to
the configured backend's real interactive session with that briefing
pre-loaded — `roadmap <slug> --chat` (a new mode alongside `--apply`/
`--from-stage`/`--view` in the existing mutually-exclusive run-mode group,
`cli/roadmap_cmd.py`) and a new `plan-tool chat <plan>` verb. `plan_tool`
never re-implements a turn-taking loop: the interactive backend session
already *is* the chat, exactly as this seed's own authoring session
demonstrates. This is a first-class architectural choice, not an oversight —
see the next subsection.

### Why this does not reuse `walk-advisory-chat-mode.md`'s engine

`plan-seeds/walk-advisory-chat-mode.md` already proposes a chat key inside
the shared review/completeness-apply/reconcile walk, built as a Python loop
in `review_walk.py` calling an injectable one-shot `advisor_fn` per turn with
a manually accumulated transcript — the same `prompt: str -> str` invoker
shape every other Claude call in this codebase uses, and hermetically
testable the same way. That is the right engine for what it does: a bounded,
strictly read-only, no-mutation consult about one recommendation. It is the
wrong engine here, for two reasons that are not about cost: this feature's
whole point is letting the operator *direct* work (write a feedback row,
record a decomposition verdict, edit artifact prose) — a mutation contract
`walk-advisory-chat-mode.md` explicitly refuses by design — and it needs the
session's own file-read/file-edit/command-invocation tools available
mid-conversation the way a real assistant session has them, which a
re-sent-text-blob loop cannot offer without rebuilding an entire tool-use
layer. The two seeds are siblings at different altitudes; neither absorbs
the other.

### The recording actions

- **Roadmap side: no new recorder.** The feedback/decision-row mechanism
  (`FeedbackRow`, decision rows, `check_settled_decisions`) already exists
  and is durable and gated. The interactive session, briefed on the row
  shape from `ROADMAP_FORMAT.md`, edits the artifact file directly with its
  own tools — the same action a human hand-editing the stub performs today,
  just guided instead of self-taught. No new CLI surface is required for
  this to work on day one.
- **Project side: update the confirmed profile deliberately.** A session may
  add an operator-confirmed statement to `.plan-tool/project.json`'s ordered
  `decisions` list and commit it. The V1 list carries no category, plan key, or
  application mapping, and the session never infers a statement from chat
  content.

### Binary observable, and what may not be checked

Per `SEED_FORMAT.md` and CLAUDE.md § "Validating a semantic property you
cannot observe" — this is the discipline the two `spinning`/`FORK_*`
failures paid for, and it applies here without exception.

**The binary observable:** an operator-confirmed, non-empty decision statement
appears in the committed project profile after an explicit request. Nothing
about the conversation that preceded it is recorded or assessed.

**Not allowed — enumerated, because stating the principle does not hold it:**

- any inference of a decision from chat content without an explicit record
  command invocation;
- any judgment of the chat's length, quality, or whether it "reached a good
  decision" — by a gate, a completeness-audit finding, or otherwise;
- any code path that detects or acts on "the conversation has concluded";
- any automatic mutation (a split, a scope-out, an artifact edit) triggered
  purely by recording a decision — a profile statement records guidance; it
  does not itself split a plan, matching the recommend-only default this
  codebase already holds for every structural remedy;
- any gate, exit-code flip, or refusal to advance keyed on whether a chat
  happened at all — the surface is opt-in tooling, not a new precondition on
  `create`, `completeness-audit`, or `roadmap`.

## In scope

`plan_tool/cli/roadmap_cmd.py` (`--chat` mode), a new `plan_tool/cli/chat_cmd.py`
verb, the deterministic briefing-assembly functions for both call sites, the
interactive hand-off (backend launch with pre-loaded context), profile briefing
when it exists, and `RUNBOOK.md`.

## Out of scope

- A bespoke multi-turn chat/advisor engine inside `plan_tool` — that is
  `walk-advisory-chat-mode.md`'s shape, deliberately not reused here.
- Any automatic re-asking of the plan-altitude question. Any future discrete
  create-time necessity call remains #298's bounded, operator-reviewed work.
- Full interactive-mode parity across `codex`/`cursor` in this first cut —
  ship against `claude` first; name the other two as a follow-up once the
  per-backend interactive-launch contract is known.
- A `roadmap feedback add` convenience CLI command — the interactive
  session's own file-edit tools cover this from day one; add a thin
  helper later only if hand-editing proves to be the actual friction.
- Persisting or auditing the chat transcript as a `plan-tool` artifact.
- Structured decision categories, plan-name keys, application mapping, or a
  second decision store. The profile's plain decision list is the available V1
  record; #299's proposed evidence-led extension was withdrawn 2026-08-20.
- Any workflow-direction action beyond the decomposition decision on the
  plan side (re-scoping steps, re-ordering, editing acceptance criteria) —
  those already have their own commands (`scope-out`, direct edits); this
  seed only adds the one recorder that is missing.

## Risks

- **The interactive hand-off is the first `plan_tool` surface that is not a
  hermetically testable one-shot invoker call.** Every other Claude call in
  this codebase takes an injectable `invoker: str -> str` and is unit-tested
  without spawning a real backend (`tests/conftest.py`'s autouse gate).
  Handing off terminal control to a real interactive session cannot be
  exercised that way. Scope tests to what is deterministic: the
  briefing-assembly functions (given a plan/roadmap slug, produce the right
  context — pure, no Claude call) and profile loading. Treat the hand-off
  itself as a thin, manually-verified boundary, and say so plainly in
  `TESTING.md` rather than inventing a fake test for it.
- **Per-backend interactive launch may not be uniform.** `claude`, `codex`,
  and `cursor` may differ in how (or whether) they accept a pre-loaded
  system prompt for an interactive session; do not assume parity without
  checking each contract doc.
- **Scope creep into a general mutation API.** The recording surface must stay
  the two named actions (roadmap feedback/decision rows via the existing
  mechanism; deliberate profile edits for project guidance) — resist widening
  it into a free-form "chat can do anything" API.

## Testing

- Briefing-assembly functions for both call sites: given a plan/roadmap
  fixture, the produced context names the right steps/rows/open feedback/
  settled decisions — unit-tested, no real backend.
- Negative test: no code path edits the project profile or writes a roadmap
  feedback/decision row without an explicit operator request — assert this
  holds even when a stubbed session transcript contains language that reads
  like a conclusion.

## Acceptance criteria

- `plan-tool roadmap <slug> --chat` and `plan-tool chat <plan>` each hand off
  to a real interactive backend session pre-loaded with the relevant
  briefing.
- From within that session, the user can request that a roadmap
  feedback/decision row be written (via the session's own file-edit tools,
  briefed on the shape) or that a project decision statement be added to the
  profile, at any point, only when they ask.
- No `plan_tool` code path infers a decision from unstructured chat content,
  gates on chat length or quality, or detects/acts on conversation
  conclusion.
- `plan-tool convergence`, `completeness-audit`, and every existing gate are
  unchanged — this surface adds a recording action, not a new precondition.

## Deferred

- Multi-backend interactive parity beyond `claude`.
- A `roadmap feedback add` CLI convenience helper.
- Persisted/searchable chat transcripts.
- Widening decision storage beyond the uncategorized project-profile list.
