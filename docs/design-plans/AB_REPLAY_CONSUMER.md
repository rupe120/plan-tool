# Seed: A/B replay + scoring consumer

> **Purpose of this document.** Seed an implementation plan (`plan-tool create
> --from-existing docs/design-plans/AB_REPLAY_CONSUMER.md`) for the *consumer*
> that closes the prompt-mode A/B loop: read the captured scenario corpus,
> replay each scenario through both prompt arms, score them on objective
> metrics, and report the deltas. This is a design brief, not the plan — it
> states intent, the seams to reuse, the decisions to make, and acceptance
> criteria. The planner will derive the concrete steps.

## Context / problem

We added a prompt-mode A/B for `create`/`detail` (combined vs split — see
`docs/explanations/prompt-ab-testing.md`). Today the loop is **open**:

- **Producer exists.** `PLAN_TOOL_PROMPT_MODE=combined|split` selects an arm;
  `PLAN_TOOL_CAPTURE_SCENARIOS=1` records *relevant, categorized* scenarios to
  `<repo>/.plan-tool/scenarios/<kind>.jsonl` (`plan_tool/scenario_capture.py`).
- **Consumer is missing.** Nothing reads that corpus, replays it through both
  arms, or scores anything. So we can collect inputs and run either arm, but we
  cannot answer the question the A/B exists to answer: *does split produce
  better output, and is it worth the extra calls?*

Without the consumer the corpus just accumulates. This plan builds it.

## Goals

- **G1.** Read the scenario corpus and replay each scenario through **both**
  arms (combined and split) for a given `kind` (`propose_steps`, `detail`).
- **G2.** Score both arms on **objective, no-human-judge** metrics first:
  first-pass gate compliance, cost (tokens / latency / call count), and
  structural deltas (how much each arm surfaces).
- **G3.** Support **planted-ground-truth** recall as the sharpest signal
  (known duplicate-logic sites / a known mixed step → count what each arm
  catches).
- **G4.** Emit a **report** (machine-readable + human table) of per-arm,
  per-category metrics with a clear, threshold-based verdict helper.
- **G5.** Be **deterministic-friendly**: handle LLM non-determinism with N
  reps per scenario per arm and report distributions, not single runs.

## Non-goals (for the first cut)

- LLM-as-judge quality scoring (leave a clean extension point; do not build).
- Auto-promoting an arm to default based on results — the human decides.
- A UI/dashboard — JSON + a terminal table is enough.
- Scoring `jira`/`run`/other phases — start with `propose_steps` + `detail`.

## What this builds on (reuse, don't reinvent)

- **Corpus format** — `plan_tool/scenario_capture.py` (schema **v2**): records
  are `{v, kind, experiment, arm, categories, repo_sha, dirty, run_id,
  captured_at, inputs, outcome}`. The corpus is **multi-experiment** — every
  record carries the `experiment` it belongs to (today only `"prompt-mode"`) and
  the `arm` that ran — so a reader **must** filter by `experiment` or it mixes
  unrelated A/Bs. `inputs` is re-runnable (`propose_steps` → `description`;
  `detail` → `plan` path + `step_id` + `plan_sha`); `repo_sha`/`dirty` pin the
  audited tree. **There is no reader yet** — add one (see Design).
- **Invoker seam** — every orchestrator takes injectable invokers. The consumer
  drives the two arms by toggling the *split* invokers:
  - combined: `create_plan(...)` / `propose_steps_from_claude(...)` with
    `foundational_invoker=None`; `generate_detail(...)` with
    `foundational_invoker=None`.
  - split: wire `shell_claude_invoker` / `shell_detail_invoker` into those
    params. Mode is inferred from invoker presence (so the prompt and the call
    stay consistent — see `_render_from_prompt(omit_*)`,
    `render_detail_prompt(split_mode=...)`).
- **Telemetry** — `plan_tool/run_log.py` already records, per call:
  `tokens_input` / `tokens_output` / `cache_*_tokens`, `cost_usd`,
  `duration_ms`, `parse_failure`, `claude_call_start`, `phase_end`, `run_end`,
  under `<repo>/.plan-tool/runs/<slug>/<run_id>.jsonl`. The cost + first-pass
  compliance metrics come straight from these — **do not re-instrument**.
- **Run-log readers** — `plan_tool/cli/runs.py` already walks/parses/profiles
  those JSONL logs (`runs list|show|diff|profile`). Reuse its parsing rather
  than writing a new JSONL reader.
- **Test gate** — `tests/conftest.py` raises if a real backend spawns; the
  consumer must be drivable with stub invokers (offline) and only hit the real
  CLI behind `@pytest.mark.allow_real_claude` / explicit opt-in.

## Proposed design

A new orchestrator `plan_tool/ab_replay.py` + a thin CLI handler
`plan_tool/cli/ab_cmd.py` (mirrors the `authoring.py`/`runs.py` split), wired as
a new subcommand. Components:

1. **Scenario reader** (extend `scenario_capture.py`): `read_scenarios(kind, *,
   repo_root, experiment=PROMPT_MODE_EXPERIMENT.name, categories=None) ->
   list[ScenarioRecord]`. The `experiment` filter is **required in spirit** (the
   corpus is multi-experiment) — default it to prompt-mode for the first cut but
   make it a first-class parameter, and tolerate v1 records (`mode` → `arm`,
   absent `experiment`) the way `_existing_keys` already does. The `categories`
   filter validates against `KNOWN_CATEGORIES` (now derived from the registry).
   Closes the write-only gap. Keep `scenario_capture.py` a leaf.
2. **Arm runner**: given one scenario's `inputs` and an arm (`combined`/
   `split`), runs the real orchestrator (`propose_steps_from_claude` or
   `generate_detail`) with the matching invoker wiring, inside an isolated
   working copy, with a dedicated `RunLogWriter` so its telemetry is
   attributable. Returns `(output, run_log_path)`.
3. **Scorer**: reads the run-log + the structured output and computes the
   metrics (below) per arm. Pure function over `(output, telemetry,
   ground_truth?)` — unit-testable without a backend.
4. **Replay driver**: for each scenario × arm × rep, calls the arm runner, then
   the scorer; aggregates into distributions; applies the verdict helper.
5. **Reporter**: `--json` payload + a grouped terminal table (per `kind`, per
   `category`, per arm: medians + deltas). Follow the exit-code convention
   (exit 0 on a completed replay regardless of verdict; a `--fail-on-regress`
   flag flips rc).

### The critical fork: live vs offline replay (DECISION REQUIRED)

- **Live replay** — re-run each scenario against the real backend. True quality
  signal, non-deterministic (needs N reps), costs tokens. Works with today's
  corpus: each record carries `inputs` **plus `repo_sha`** (and `plan_sha` for
  detail), so a faithful replay checks out / verifies that tree first — the
  proposal and detail are functions of repo state, not just `inputs`. The
  consumer should warn/skip when the working tree's HEAD ≠ the record's
  `repo_sha`.
- **Offline replay** — replay against *recorded* prompt+response pairs. Cheap,
  deterministic, CI-friendly — but **the corpus does not store prompts or
  responses today** (only inputs/outcome), and offline can only score
  *gate-compliance / structural* metrics, never fresh quality. Enabling it
  requires extending capture to optionally persist the rendered prompt + raw
  response per call (gated, larger files).

**Recommendation:** build **live replay first** (it answers the real question),
keep the scorer's telemetry/structural metrics backend-agnostic so the **same
scorer** later powers an offline mode once capture is extended. Treat
prompt/response capture as a follow-up the plan can scope but not block on.

## Metrics (objective-first)

| Metric | Source | What it tells us |
|---|---|---|
| **First-pass gate compliance** | `run_log` `parse_failure` / `claude_call_start` attempt counts | Did the response satisfy the JSON schema / 7-section gate / required headings *without* the repair retry? Split should retry **less** if focus helps. |
| **Cost** | `run_log` `tokens_*`, `cost_usd`, `duration_ms`, call count | The price of split (more calls). The denominator for "worth it?". |
| **Structural yield** | the arm's structured output | Did split surface **more** real foundational-logic finds / mixed-step splits than combined for the same input? (Count per `category`.) |
| **Planted-ground-truth recall** | a seeded fixture repo (known duplicates / mixed step) vs the arm's output | The sharpest signal — removes LLM-judge noise. Recall + precision per arm. |
| *(later)* **LLM-as-judge** | rubric over both outputs | Quality the structural metrics can't capture. Extension point only. |

**Decision rule (per category):** keep `split` only when the quality delta
(compliance ↑ and/or recall ↑) clears a pre-set bar **and** is worth the token
delta. Report the delta and the bar; let the human decide. Default stays
`combined` until the data clears it.

## CLI surface (proposed)

```
plan-tool ab-replay <kind> [--experiment NAME] [--scenarios-dir DIR]
    [--category C ...] [--arms a,b] [--reps N] [--live|--offline]
    [--planted-fixtures DIR] [--json] [--out report.json]
    [--fail-on-regress]
```

- `<kind>`: `propose_steps` | `detail`.
- `--experiment` selects which registered A/B to replay (default `prompt-mode`,
  the only one today). Validated against `EXPERIMENTS`; the corpus is filtered to
  records with that `experiment`.
- `--arms` defaults to the **selected experiment's** `arms` (so `prompt-mode` →
  `combined,split`) rather than a hard-coded pair — read them from the
  `Experiment` descriptor, don't inline them.
- Other defaults: `--reps 3` (LLM noise), `--live`, reads
  `<repo>/.plan-tool/scenarios/`.
- `--category` filters the corpus by tag (validates against `KNOWN_CATEGORIES`,
  which is derived from the registry).
- Mirror the backend-selection precedence style and the `runs` subcommand UX.

## Architecture fit / file layout

- `plan_tool/ab_replay.py` — orchestrator (reader → runner → scorer →
  aggregate). Domain logic, injectable invokers, no CLI imports.
- `plan_tool/cli/ab_cmd.py` — thin handler (parse/banner → delegate → render),
  registered in `cli/parser.py` + dispatched in `cli/app.py`.
- `plan_tool/scenario_capture.py` — add the reader (`read_scenarios`,
  `ScenarioRecord`); keep it a leaf.
- Reuse `cli/runs.py` run-log parsing for the scorer's telemetry side.
- Planted fixtures under `tests/fixtures/ab/` (a generator that writes a small
  repo with N known duplicate-logic sites + one known mixed step).

## Suggested phasing (the planner will refine)

1. **Reader + record type** in `scenario_capture.py` (+ tests). Smallest,
   unblocks everything.
2. **Scorer** over `(output, run-log telemetry)` for compliance + cost +
   structural yield — pure, fully unit-tested with canned telemetry. No backend.
3. **Arm runner + replay driver** (live), wiring the invoker seam per arm in an
   isolated working copy, with per-run `RunLogWriter`. Stub-invoker tests.
4. **Reporter** (JSON + table) + verdict helper + exit-code wiring.
5. **Planted-ground-truth fixtures + recall metric**.
6. *(follow-up)* Offline replay: extend capture to persist prompt+response;
   reuse the same scorer.

## Risks / open questions (for the human)

- **Live vs offline** (see fork) — recommend live-first. Confirm.
- **Isolation cost** — replaying `create`/`detail` mutates a working copy
  (writes plan/detail files). Use a throwaway temp clone per scenario×arm×rep?
  (Recommended.) Token/time budget for a full corpus replay at `--reps 3`?
- **Structural-yield ground truth** — "more finds" isn't strictly "better"
  (could be noise). Planted ground truth is the trustworthy version; weight it
  above raw structural counts.
- **Corpus skew** — capture runs in whatever arm the operator chose, so a
  record's `arm` field is mixed across the corpus. Replay ignores it (re-runs
  every arm of the selected experiment), but confirm we don't want a "capture in
  the default arm only" convention for a clean input set.
- **Multi-experiment corpus** — records are partitioned by `experiment`; the
  reader filters to one experiment per replay. If two experiments are ever
  active in the same run, capture records only one of them (single-experiment
  per capture site today) — revisit if/when a second experiment ships.
- **Non-determinism budget** — is `--reps 3` enough to separate signal from
  variance for the metrics that matter? May need more for recall.

## Acceptance criteria

- `plan-tool ab-replay propose_steps --reps 3` reads the corpus, runs both arms
  per scenario, and writes a report with per-category compliance/cost/yield
  medians and combined-vs-split deltas.
- The scorer is a pure function with unit tests over canned telemetry +
  outputs — no backend spawn (conftest gate stays green).
- A planted-ground-truth fixture yields a recall number per arm.
- Exit 0 on a completed replay regardless of verdict; `--fail-on-regress`
  flips rc when split underperforms its bar.
- `docs/explanations/prompt-ab-testing.md` updated to point at the replay command; a row
  added to `TESTING.md`'s neutralization table for the arm-runner seam.

## Verification (end-to-end)

- Unit: scorer + reader + signal/verdict helpers (hermetic, stub telemetry).
- Component: drive `ab_replay` with stub invokers returning canned arm outputs;
  assert the report aggregates and the verdict helper fires correctly.
- Integration (opt-in, `@pytest.mark.allow_real_claude` or a manual run):
  one live scenario through both arms, confirm telemetry attribution and a
  populated report.
- Smoke: capture a couple of real scenarios (`PLAN_TOOL_CAPTURE_SCENARIOS=1`),
  then `plan-tool ab-replay` over them and read the table.
