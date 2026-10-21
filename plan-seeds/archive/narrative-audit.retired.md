> **Retired 2026-08-19** — #188 does not support a narrative-audit product.
> Preserve this seed as rejected scope and an optional human-review technique;
> do not re-seed it without new evidence that a product surface can establish
> more than a model retelling.

# Plan seed: `plan-tool narrative-audit` — the throughline audit

> Source: BACKLOG **#188** (2026-07-29). This seed elaborates that entry's
> scope contract — it does not invent a different fence. The resulting plan's
> **final step must update #188** (mark shipped, or record what remains) —
> authoring the plan alone does not touch the entry.

## Why

The completeness audit checks *local* coherence: a step against a criterion, a
seam between two files. It has no finding source for the *arc* — whether the
plan's motivation pays off, whether the built pieces ever meet, why a chapter
is where it is. Evidence: fifteen completeness rounds on
`jira-grade-01-detail-instrument` verified every seam and never asked "when
does an authored artifact first flow through all three consumers?" A one-pass
narrative retelling surfaced that, plus a component whose stage value was
unstated, plus a free analysis sitting in committed report history.

The mechanism that makes this an audit rather than an essay is the **edit
operation**: retell the plan faithfully (holes included), note each hole, then
retell it *with the holes closed*. The edited version is a costless prototype
of the fixes — each proposal must be small and concrete for the story to read
straight through — and the **character key** (every story element mapped to a
named plan element) is the honesty mechanism that blocks decorative
hallucination.

## Outcome

`plan-tool narrative-audit <name>` exists end to end: one Claude call over the
plan body + detail bundle produces a four-part narrative artifact plus
structured findings; deterministic gates reject malformed responses; the
artifact persists like other audits (timestamped report + JSON sidecar); exit
codes follow the convention; docs and the capability catalog are updated; and
a committed example shows the intended shape.

## Design

### The command

- `plan-tool narrative-audit <name>` — plan-scoped, read-only with respect to
  the plan (it never mutates plan or detail files), spends Claude (one call),
  and therefore **opens a run log** (the log exists iff the verb may spend
  Claude — the run-log coverage rule).
- Flags: `-y` (accepted, no-op — nothing prompts), `--json`,
  `--fail-on-findings` (flips rc on medium+), the standard backend/rate-limit
  flags inherited from the shared dispatch. **Reject `--iterate`** at rc 2:
  this is a one-shot judgment artifact; "convergence" of a story is an
  operator read, not a loop.
- No grade axis in v1: the bundle is the run-grade bundle, resolved the same
  way the completeness audit's conceptual pass resolves it (reuse the bundle
  formatter; do not fork it).
- **Arc context is part of the grounding.** The verb is plan-scoped, but the
  throughline that broke in the reference exercise was the *arc's*, not the
  plan's: the plan is stage 01 of an ordered five-stage group and the story
  described one stage. Feed the prompt whatever arc context the plan body
  already declares — its "stage N of M" sentence and the backlog anchor it
  names — and require the story to place the plan inside that sequence. This
  needs no new input surface and no cross-plan resolution: it is text already
  in the plan body. Without it the audit is structurally unable to notice a
  missing sibling stage, which was its single largest miss.

### The prompt (`plan_tool/prompts/narrative-audit.md`)

Written under the prompts' plain-English rules (it is itself a hand-authored
prose surface — say so in its own acceptance criterion). It instructs one
response with a **closed section contract**, in order:

1. `## Character key` — a two-column table; every story element on the left,
   the named plan element it renders on the right (step id + title, section
   name, file path, or symbol). Every subsequent story element must appear
   here. An element the model cannot map is not allowed in the story.
   **Coverage runs both ways.** The reference exercise enforced only story →
   plan and paid for it: a whole sibling stage (the arc's stage 02) never
   appeared in the story, the key had no row for it, and nothing flagged the
   absence — while a later decision moved the arc's evidence gate onto exactly
   that stage, so the narrative was silently missing the piece carrying the
   payoff. So the key must also cover plan → story: every step of the plan,
   and every sibling stage the plan body names as its arc context, gets a
   row or an explicit `— not in the story:` row stating why it was left out.
   A stage or step that earns no scene is itself a finding worth reading.
2. `## The draft` — the plan retold faithfully as a short story, **plot holes
   included**. The prompt must say explicitly: where the plan is awkward, the
   draft must be awkward; disjointedness is data, not something to smooth.
3. `## Editor's notes` — one note per hole. Each note names the story
   problem, the plan element(s) it maps to (by key), a concrete proposal, and
   a severity. Suggested (not closed) hole taxonomy, from the reference
   exercise: `unpaid-setup` (motivation whose payoff never comes),
   `missing-integration-scene` (built pieces never meet),
   `side-quest-on-critical-path`, `character-without-lines` (a component
   whose value in this plan is unstated), `unstaged-element` (a plan element
   or sibling stage the story never depicts at all — the reverse-coverage
   hole), `evidence-in-the-drawer` (existing
   data unexamined).
4. `## The edited version` — the story with the holes closed. Each edit must
   be traceable to a note; no new unmapped elements.
5. `## Proposals` — a table: story edit → proposed plan change → cost. This
   is the delta between draft and edit, made explicit.
6. `## Findings` — **last, machine-parsed**: one finding line per editor's
   note in the same line grammar the plan audit's findings use, so parsing
   reuses existing machinery rather than minting a second format.

Retry loop: on a gate failure (below), reprompt once with a suffix naming the
missing/violated sections — the `detail` reprompt pattern, not a silent
acceptance.

### Deterministic gates (no Claude)

- All six sections present, in order, `## Findings` last; closed schema (no
  extra top-level sections).
- Every character-key row's plan element **resolves deterministically where
  possible**: step ids exist in the plan; cited file paths exist; cited
  symbols grep to the cited file. Rows that name prose concepts (a section
  title, a criterion) are checked for literal presence in the plan body.
  Per #188's stop rule: keep the deterministic subset; anything needing
  judgment is out of scope for the gate.
- Findings parse cleanly into `Recommendation`s; a finding whose note maps to
  no character-key row is a gate failure (the honesty mechanism, enforced).
- **Reverse coverage, deterministic half:** every step id in the plan appears
  in the character key, either as a mapped row or as an explicit not-in-the-
  story row. A missing step id is a gate failure. This is the cheaper
  direction to check and, on the reference exercise, the one that would have
  caught the larger hole — see the character-key contract above.
- **A key row is not a scene.** Every mapped key row's story label must appear
  in `## The draft` or `## The edited version`; a row whose element the story
  never mentions is a gate failure. This is not hypothetical pedantry — it is
  the exact shape of the reference exercise's *failed first fix*: a row was
  added for the missing stage, the key then looked complete, and the story
  still never described it. Reverse coverage without this gate can be
  satisfied by bookkeeping.

### Structured output

- Source token: `narrative-coherence` — **new**, advisory, and **kept out of
  `APPLY_ELIGIBLE_SOURCES`** (never reaches `apply_finding`; the granularity-
  advisor precedent). Severity cap: `medium`. Never flips an exit code except
  under `--fail-on-findings`.
- Persistence: timestamped markdown report (the full four-part artifact)
  under the plan's `reports/` dir with a `-narrative` suffix, plus a JSON
  sidecar via `save_review` with `kind="narrative"`.
- **The sidecar kind is a persisted-vocabulary addition.** `DATA_CONTRACT.md`
  gains the row, and the plan must **enumerate every consumer that filters or
  dispatches on `kind`** (`resolve_reusable_audit`,
  `convergence_diagnosis.load_report_history`, review listings/walks, any
  `kind`-keyed filename logic) and pin per consumer — with a test — that the
  new kind is ignored or handled. Enumerate; do not argue safety from any one
  consumer's behavior (the stage-01 lesson, learned twice).
- `--json`: findings, the report path, and the plan fingerprint at audit time.

### The committed example

The reference artifact from the exercise lives in `.tmp/` (gitignored,
transient). The plan must commit a durable example —
`docs/examples/narrative-audit.md` or equivalent — showing the four-part
shape on a real plan, cited from the prompt's docs and `USE_CASES.md`.
Do not cite `.tmp/` paths from committed files.

### When to run (docs content, not mechanism)

`USE_CASES.md` guidance: at *shape* boundaries — after `create`, after any
structural mutation (split / merge / scope-out), once before close-out — not
every convergence round. The completeness audit stays the per-round loop;
this is the complement, and the docs should say both lenses are complements,
not substitutes.

## Suggested decomposition (advisory)

1. **Prompt + response contract + parser** — the prompt file, the section
   gate, the character-key resolution checks, findings → `Recommendation`s.
   Invoker-stubbed tests; no CLI yet.
2. **Command wiring + persistence** — CLI module, run log, report + sidecar
   (`kind="narrative"`), the kind-consumer enumeration with per-consumer
   tests, `DATA_CONTRACT.md`.
3. **Output surface + docs** — `--json`, `--fail-on-findings`, the committed
   example, `CAPABILITIES.md` (validate's catalog check must pass),
   `USE_CASES.md`, generated CLI docs; final step updates BACKLOG #188.

## Scope fence (inherited from #188 — audits stay inside it)

- **In scope:** the new prompt, a small orchestrator leaf, CLI wiring, the
  `narrative` sidecar kind + `DATA_CONTRACT.md`, capability/docs entries,
  tests per `TESTING.md`'s invoker-neutralization table.
- **Out of scope / non-goals:** auto-applying any narrative finding; a grade
  axis; folding narrative findings into completeness reports or convergence
  history; multi-pass convergence; changes to any existing verb's behavior.
- **Allowed behavior changes:** none to existing surfaces — purely additive.
- **Allowed reorganization:** none.
- Out-of-scope findings during this plan's audits route to
  `BACKLOG.md`/`BUG_BACKLOG.md`, never expand the plan.

## Verification

- Stubbed-invoker tests: gates, retry-once, parse, persistence, rc
  convention, `--json` shape; a malformed response (missing section, unmapped
  character-key element) is rejected and reprompted.
- The kind-consumer enumeration: one test per consumer pinning
  ignore-or-handle for `kind="narrative"`.
- `tests/test_data_contract.py` green; `plan-tool validate`'s capability
  check green; generated CLI docs drift guard green.
- Full suite green with zero edits to existing cases.

## Stop / defer

- Character-key resolution needing judgment beyond step-id/path/symbol/
  literal checks → keep the deterministic subset, defer the rest to a
  follow-up entry.
- Sidecar-kind fallout beyond the enumerated consumers → stop and re-scope
  before shipping the kind.
- Any pressure toward making findings auto-appliable → refuse; it is the
  entry's explicit non-goal.
