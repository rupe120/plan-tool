# Prompt-mode A/B: combined vs split

`plan-tool` keeps two implementations of the `create` step-proposal and
`detail` authoring prompts so their quality and cost can be compared with data
instead of intuition:

- **`combined`** (default) — the pre-split baseline. One claude call per
  phase. The proposal inlines the foundational-logic sweep (item 9); the
  detail authoring prompt greps for shared logic itself and runs the
  mixed-step purity self-check inline.
- **`split`** — the lifted-out arm. The foundational-logic sweep runs as a
  **separate focused claude call**, and the inline instruction is dropped
  from the proposal/authoring prompts — one more call than `combined`. The
  hypothesis: a divergent repo-wide search competes badly with convergent
  JSON / section emission, so giving it its own call raises quality — at
  the cost of more calls/tokens/latency.

**Both arms are live, not one frozen baseline and one experiment.** Items
1-8 of the proposal prompt are identical string literals in both arms —
only item 9 (foundational-logic) differs, inlined in `combined` and lifted
to its own call in `split`. So an ordinary fixed-item edit (e.g. item 8's
destructive-operation disposition audit) lands in both arms' `create`
output identically; `combined` is not "the legacy prompt" preserved
unchanged, it is the default arm that keeps receiving every fixed-item
edit same as `split` does.

## Selecting the arm

```bash
plan-tool --prompt-mode split  create my-plan --from-description "…"
plan-tool --prompt-mode split  detail my-plan
# generic (works for any registered experiment):
plan-tool --experiment-arm prompt-mode=split  create my-plan …
# or via env:
PLAN_TOOL_PROMPT_MODE=split  plan-tool create my-plan --from-description "…"
```

Precedence: **`--prompt-mode` (dedicated flag) > `--experiment-arm prompt-mode=…`
(generic) > `PLAN_TOOL_PROMPT_MODE` env > `combined` (default)**. Any
unrecognized value falls back to the default arm so a typo never silently
changes call volume. The prompt-mode arm is resolved via the experiment registry
(`PROMPT_MODE_EXPERIMENT.resolve_arm`); in the `split` arm the CLI wires
`foundational_invoker` (both create and detail), which drives both the extra
call and the lean prompts (`_render_from_prompt(omit_foundational_item)`,
`render_detail_prompt(split_mode=True)`).

## Capturing real-world scenarios

To build a corpus of real invocations to replay through both arms, set:

```bash
PLAN_TOOL_CAPTURE_SCENARIOS=1  plan-tool create my-plan --from-description "…"
```

Each **relevant** run appends one JSON line per phase under
`<repo-root>/.plan-tool/scenarios/<kind>.jsonl`:

Records are serialized canonically (**sorted keys**) so a record is a
deterministic function of its inputs — only `captured_at` (a seamed clock)
varies, and it is excluded from scenario identity:

```json
{"arm":"combined","captured_at":"…","categories":["foundational-logic"],
 "dirty":false,"experiment":"prompt-mode","inputs":{"description":"…"},
 "kind":"propose_steps","outcome":{"n_steps":4,"titles":["…"]},
 "repo_sha":"<git HEAD>","run_id":"<run>","v":2}
```

Record fields:
- **`experiment`** + **`arm`** — which A/B this record belongs to
  (`"prompt-mode"`) and the variant that ran (`"combined"`/`"split"`). One corpus
  holds many experiments, filterable by `experiment`.
- **`inputs`** — everything needed to **re-run** the scenario (create
  `description`; detail plan path + `step_id` + `plan_sha`).
- **`repo_sha`** + **`dirty`** — git HEAD at capture and whether the working
  tree had uncommitted changes. The proposal/detail are functions of the **tree**
  the run audited, not just `inputs`; a faithful replay pins `repo_sha` and
  should **skip `dirty` captures** (the commit can't reproduce them).
- **`run_id`** — links to the run-log telemetry under `.plan-tool/runs/`. The
  split arm's extra call (`foundational_sweep`) is **instrumented** there too,
  so the scorer can measure it (call count, cost, first-pass compliance from
  the per-attempt `claude_call_start` events).
- **`v`** — record schema version, for corpus evolution.

Capture is best-effort, off by default, **scoped to operator runs** (only
`plan-tool create` / `plan-tool detail`; not `bench` / reconcile / the Phase-B
self-call), **de-duplicated** (same kind + `experiment` + `arm` + `repo_sha` +
`inputs` + failure-class written once — a later *success* of a previously
*failed* input is kept), and the corpus dir is gitignored. See
`plan_tool/scenario_capture.py`.

### Detection & relevance — only A/B-worthy runs are saved

A run is recorded **only when it is categorized** — i.e. it exercised a behavior
the experiment changes (a trivial run matches nothing and is dropped, keeping
the corpus signal-dense). Cached/resumed runs are skipped. **Failures are
captured** (category `failure`): the inputs that broke one arm are re-runnable
and the most discriminating A/B case.

**Categories are arm-independent** — derived from the proposal/step + plan
*structure*, never from the split-only sweep or combined-only purity check — so
the **same input tags the same way in either arm**, letting the replay consumer
build balanced per-category cohorts.

| Category | Detected when… | Scope |
|---|---|---|
| `foundational-logic` | a step has the shared-logic footprint — edits ≥2 existing files, **or** creates a new file while editing an existing one (extract-shared-module). Broadened past refactor-only to catch non-refactor consolidations (recall over precision) | create + detail |
| `mixed-step` | a refactor→feature `depends_on` pair — in the proposal (create) or the step's plan (detail, so the self-check axis is detectable in split too) | create + detail |
| `failure` | the run failed to parse / produce output (re-runnable, discriminating) | create + detail |

## Defining a new experiment

The capture/detect/categorize substrate is **multi-experiment**: an experiment
is described by one `Experiment` value and the corpus carries an `experiment` +
`arm` dimension on every record. Some of the wiring is generic (you get it by
registering); some is necessarily per-experiment (you write it). This section is
explicit about which is which, so the work is predictable.

### The `Experiment` descriptor

`Experiment` (in `plan_tool/scenario_capture.py`) is a frozen dataclass:

| Field | Meaning |
|---|---|
| `name` | Stable id stored in every record's `experiment` field (e.g. `"prompt-mode"`). The key under which it's registered in `EXPERIMENTS`. |
| `arms` | The variants compared, as a tuple (e.g. `("combined", "split")`). The first/default arm should be the safe, legacy behavior. |
| `default_arm` | The arm used when nothing is selected — must be one of `arms`. |
| `categories` | The behavior categories this experiment can tag a scenario with. **Load-bearing** (see below) — not just documentation. `failure` is universal and must *not* be listed here. |
| `env_var` | Optional env var that selects an arm for this experiment. |

`resolve_arm(flag)` on the descriptor returns `flag > env_var env > default_arm`,
and an unrecognized value falls back to `default_arm` (a typo never silently
changes behavior).

### Steps to add one

1. **Register it.** Add an `Experiment(...)` to the `EXPERIMENTS` dict in
   `scenario_capture.py`. Registering alone gives you, for free: the record
   `experiment`/`arm` dimension, dedup/provenance/run-log linkage keyed on it,
   env-var + default arm resolution, generic `--experiment-arm <name>=<arm>`
   CLI/env selection, the experiment's contribution to the derived
   `KNOWN_CATEGORIES`, and the capture-time category vocabulary gate.

2. **Declare the arm's effect at its orchestrator.** This is *not* generic — you
   write it. At the orchestrator (e.g. `create` / `detail`), translate the
   resolved arm into whatever prompt knobs each arm flips. The prompt-mode
   experiment wires its invokers / `omit_*` / `split_mode`. Resolve the arm in
   the CLI via `resolve_experiment_arm(<YOUR_EXPERIMENT>, args)` and thread the
   resolved `arm` string down to the capture call (don't re-derive it — see
   `arm_from_split`, which exists only as the `arm=None` fallback for non-CLI
   callers).

3. **Detect + capture.** Compute the experiment's **arm-independent** signals
   (derived from structure that's identical across arms, so the same input tags
   the same way in either arm — this is what lets the replay consumer build
   balanced per-arm cohorts) and call:
   ```python
   capture_scenario(kind, experiment=<YOUR_EXPERIMENT>.name, arm=resolved_arm,
                    categories=categorize_scenario(signals), inputs=…, …)
   ```
   `categorize_scenario` is open-vocabulary, **but** `capture_scenario` then
   filters the categories to the experiment's declared `categories` ∪ `failure`
   (`valid_categories_for`). So a category only lands in the corpus if you
   declared it on the `Experiment` — declare new categories there (a typo or an
   undeclared category is silently dropped; if *nothing* survives, the run is
   treated as not-relevant and skipped, same as the empty-categories gate).

### What's generic vs. what you write

- **Generic (registration buys it):** the `experiment`/`arm` record columns,
  dedup, provenance (`repo_sha`/`dirty`), `run_id` linkage, env+default arm
  resolution, `--experiment-arm <name>=<arm>`, the derived `KNOWN_CATEGORIES`,
  the category vocabulary gate, the universal `failure` category, and a **new
  scenario `kind`** (just a new string — records land in `<kind>.jsonl`).
- **You write:** the per-arm behavior at the orchestrator (step 2), the
  detection signals and `capture_scenario` call sites (step 3), and — if you
  want a short dedicated flag like `--prompt-mode` instead of the generic
  `--experiment-arm name=arm` — an entry in `resolve_experiment_arm`'s
  `dedicated` map in `cli/authoring.py`.

### Known boundary

Capture is **single-experiment per run**: each capture site records exactly one
`(experiment, arm)`. If two experiments were ever active in the same `create`
run, only one would be recorded. The record shape can't express a point in the
*product* of several experiments' arms, so combined/factorial experiments aren't
modeled — revisit the record shape and capture sites if a second experiment
needs to run concurrently with prompt-mode.

## Running the A/B from the corpus

The corpus gives a fixed input set. For each captured `inputs`, run both arms
and compare. Objective metrics available without a human judge:

- **First-pass gate compliance** — did the response satisfy the JSON schema /
  7-section gate without the repair retry? (`run_log` records `parse_failure`
  / `attempt`.)
- **Cost** — tokens, wall-clock, call count per arm (from `run_log`).
- **Recall on planted ground truth** — seed a repo with known duplicate-logic
  sites / a known mixed step and count how many each arm surfaces.

Decide per axis: keep `split` only if the quality delta clears a pre-set bar
and is worth the token delta. Until then, `combined` stays the default.
