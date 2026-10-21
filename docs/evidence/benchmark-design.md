# Backend-quality benchmark — corpus & scoring rubric

This document is the **rubric** for the synthetic backend-quality benchmark
(`claude` vs `codex` vs future CLI backends). It defines the corpus under
`benchmarks/corpus/**`, the deterministic metric that scores each task family,
and why every metric is **judge-free**. The bench engine (step 2), scorers
(step 3), report (step 4), and live matrix run (step 5) consume these artifacts;
this step ships only the corpus and this doc — no production code.

## Core correctness claim: no LLM judge

Every score in this benchmark is a **count, a set comparison, or a process exit
code** — never a subjective rating produced by a model. Ground truth is
hand-authored and frozen *before* any backend runs: expected step-count ranges,
`change_type` labels, a seeded-defect manifest, a pre-written hidden test file,
and known target edits. A backend cannot game a score it has never seen, and a
failing score is reproducible and debuggable. This is the dual of the
codex-contract capture (which transcribed ground truth *from* a live binary);
here we fabricate it on purpose so the backend has never seen the answer key.

## Corpus layout

```
benchmarks/corpus/
  proposal/
    seed-feature.md            clean single-feature prose seed + label block
    seed-mixed-must-split.md   refactor+feature seed that MUST split
    seed-non-code.md           docs/config-only seed (must classify non-code)
  detail/
    fixture-plan.md            2-step plan + embedded repo map
  reconcile/
    seeded-defects.json        2 scratch repos + seeded-drift manifest
  implementation/
    hidden-tests.py            2 step specs + embedded seed + hidden pytest
  apply/
    findings.json              2 saved findings + known target edits
```

### Scratch repos live *inside* the corpus files

The detail, reconcile, implementation, and apply families each need a small
source tree at run time. Rather than scatter loose fixture files, each family's
manifest/seed embeds its tree as a **`repo` map** (path → file contents). The
step-2 engine materializes the map into a tempdir + `git init` before invoking
the backend. This keeps the declared file footprint exact and co-locates each
answer key with its inputs — one parse, one diff target, one place to
re-baseline. The maps:

- **detail** — a fenced ```json``` block in `fixture-plan.md`'s body with a
  top-level `repo` object.
- **reconcile / apply** — a `repo` object on each entry in the JSON manifest.
- **implementation** — a fenced text block in the `hidden-tests.py` docstring.

## Families

Each family maps one-to-one onto a production code path a future `bench` engine
drives. The metric column names the deterministic primitive that decides the
score.

### Proposal family — `create`

**Input:** three prose seeds, each with a fenced answer-key block.
**Production path:** `create` proposal + `plan_tool/create.py:_propose_step_split`
/ `_apply_step_split`.

**Metrics (all set/range comparisons against the seed's label block):**

1. **Step-count validity** — the proposal's step count falls inside the seed's
   `expected_step_count_range`.
2. **`change_type` agreement** — every emitted step's `change_type` is drawn
   from the seed's `expected_change_types`, validated against
   `plan_tool/schema.py:ChangeType` (`refactor` / `feature` / `non-code`).
3. **Split detection (mixed seed)** — when `must_split` is true, the proposal
   must emit exactly two type-pure steps wired `refactor` → `feature` with the
   feature `depends_on` the refactor, matching `_apply_step_split`'s "make the
   change easy FIRST, then make the easy change SECOND" mandate.
4. **Footprint classification (non-code seed)** — when
   `expected_source_footprint` is false, no step may declare a source-file
   footprint; only docs/config paths are allowed.

**Why judge-free:** every check compares the proposal's structure to the seed's
fixed label block — a range test and three set comparisons.

**Answer-key block fields:** `expected_step_count_range` (`[min, max]`),
`expected_change_types` (allowed label set), `expected_dependency_shape`
(`linear` | `refactor->feature` | `any`), `must_split` (bool),
`expected_source_footprint` (bool), and the optional `split_contract`
(`first_step_change_type`, `second_step_change_type`, `second_depends_on_first`).

### Detail-drafting family — `generate_detail` + coherence checks

**Input:** `detail/fixture-plan.md` — a 2-step plan that parses under
`plan_tool/schema.py:Plan`, with an embedded `repo` map.
**Production path:** `generate_detail`, then
`plan_tool/review.py:check_files_coherence` and the detail parsers in
`plan_tool/detail.py`.

**Metrics (each a count from an existing checker):**

1. **Required-H2 presence** — the drafted detail body contains all seven
   sections in `plan_tool/detail.py:_REQUIRED_H2_TOKENS`
   (`summary`, `table`, `why`, `files`, `implementation`, `tests`,
   `acceptance`). This is the same set `plan_tool/review.py` enforces via
   `_REQUIRED_DETAIL_SECTION_NAMES` and `check_detail_body_completeness`.
   *Authoring note: this set was copied by grep at authoring time, not from
   memory — re-grep both constants if scoring drifts.*
2. **Files-coherence cleanliness** — finding count from `check_files_coherence`
   across its two directions: `files_only` (a declared footprint path the
   detail never mentions → `nit`) and `detail_only` (the detail cites a path
   that resembles but does not match a declared one → `info`, the near-miss
   drift signal). A faithful draft of `fixture-plan.md` yields zero of both.
3. **Acceptance-bullet parseability** —
   `plan_tool/detail.py:parse_acceptance_bullets` returns a non-empty list
   from the drafted `## Acceptance criteria`.

**Why judge-free:** each metric is a count produced by an existing
deterministic checker over the drafted text.

### Reconcile/audit family — `plan_tool/review.py` drift + criteria checks

**Input:** `reconcile/seeded-defects.json` — two scratch repos with a manifest
of seeded drift.
**Production path:** `collect_deterministic_findings` (drift/coherence
aggregation) plus `check_criteria_fulfillment` (the LLM-backed semantic check,
excluded from `collect_deterministic_findings`) for the unimplemented-criterion
defect.

**Metric:** **recall and precision** of the backend's reported findings against
the seeded-defect manifest. A reported finding matches a seeded defect when
their `file` agrees and the finding text fuzzily mentions the defect `symbol`,
so wording differences don't zero an otherwise-correct catch. Recall =
matched_defects / total_seeded_defects; precision = matched_findings /
total_reported_findings.

**Seeded drift kinds** (the three the title names, spread across the two repos):

- `renamed_function` — plan claims the old name, code defines a new one
  (`auth-service`: plan says `validate_token`, code defines `verify_token`).
- `dropped_flag` — plan/criteria promise a flag the code never wires
  (`auth-service`: `--strict` is never registered).
- `unimplemented_criterion` — an acceptance criterion the code never satisfies
  (`report-exporter`: `export()` promises retry-on-transient-failure but has no
  retry loop). This defect exercises the LLM-backed
  `check_criteria_fulfillment`; it is still scored by manifest overlap, not by
  any model rating.

**Why judge-free:** the *scoring* is set overlap against a fixed manifest,
independent of which checks (deterministic or semantic) the backend ran to
surface a finding.

**JSON shape:** top-level `{ "repos": [ ... ] }`. Each repo carries `id`,
`plan_path`, a `repo` map (path → contents, including the plan file and the
drifting code), and a `defects` array; each defect has `kind`
(`renamed_function` | `dropped_flag` | `unimplemented_criterion`), `file`,
`symbol`, and a human `note`. Every embedded `plan.md` parses under `Plan`.

### Implementation family — `run_step` + hidden tests + scope guard

**Input:** `implementation/hidden-tests.py` — two step specs and an embedded
scratch-repo seed in the module docstring; the `test_*` functions are withheld
from the backend until scoring.
**Production path:** `run_step` against the spec'd step, then the hidden tests,
then `plan_tool/scope_guard.py:evaluate_apply_scope`.

**Metrics:**

1. **Hidden-test pass** — run the backend on the spec + seed, then run
   `hidden-tests.py` (which the backend never saw) with the benchmark-supplied
   hidden-test command. The pytest **exit code** is the pass/fail signal; pass
   rate across the four tests is recorded.
2. **Scope-guard cleanliness** — out-of-scope file count from
   `evaluate_apply_scope`: paths the backend touched that fall outside
   `compute_in_scope_paths` for the step, excluding `is_documentation` files.

**Why judge-free:** a pytest exit code plus a path-set count — no rating.

*Note: `Plan.test_command` remains optional when absent. Normal `create` writes
`uv run pytest tests/ -q -n auto` only after that fixed candidate qualifies and
passes preflight, can accept a concrete interactive operator command, and
otherwise omits the field. None of those creation outcomes configures or scores
this benchmark: the engine explicitly supplies `uv run pytest
<hidden-tests.py> -q --tb=no` and runs it in the scratch repo, not the project
suite. The hidden tests import the implementation lazily inside each test body
so the file collects under pytest before the seed is implemented — collection
is the step-1 verification gate; passing requires an implementation.*

### Apply-finding family — `plan_tool/launcher.py:apply_finding`

**Input:** `apply/findings.json` — two saved findings, each with an embedded
`repo` map (a valid plan + its on-disk detail file) and a known target edit.
**Production path:** `apply_finding` → `ApplyFindingResult`.

**Metrics:**

1. **Target edit landed** — the `expected_edit` marker appears in
   `ApplyFindingResult.diff_text`.
2. **Scope cleanliness** — no unrelated hunks. `apply_finding`'s diff is scoped
   to the plan file plus the step's detail file only, so `target_file` and
   `expected_edit` always describe a **plan or detail** edit, never a
   source-file edit.

**Why judge-free:** a diff-hunk substring presence test plus a hunk-scope count.

**JSON shape:** top-level `{ "findings": [ ... ] }`. Each finding has `id`,
`plan_path`, `target_step_id`, `target_file`, `finding_body` (a
`plan_tool/launcher.py:FindingBullet`-shaped string — a severity token + body,
e.g. `HIGH: ...`), `expected_edit` (the diff substring the post-apply
`diff_text` must contain), and a `repo` map.

## Trial counts and affordability

- **Trials per cell:** 3 (median over three runs absorbs single-run backend
  variance while keeping the matrix cheap).
- **Cell inventory:** proposal 3 seeds + detail 2 steps + reconcile 2 repos +
  implementation 2 steps + apply 2 findings = **11 cells**.
- **Backends:** 2 (`claude`, `codex`) for the initial matrix; the registry is
  `plan_tool/backend.py:registered_binaries()`, so adding a backend rescales
  this linearly.

**Full-matrix cost: 11 cells × 2 backends × 3 trials = 66 backend
invocations.**

**Observed cost and duration** (run `2026-06-07T00-23-38+00-00-4376bf` —
`claude` 2.1.163, `codex` 0.137.0, corpus `e9305fc3`; transcribed from the
committed run, not fabricated): the full 66-invocation matrix took **~60 minutes**
of wall-clock (3,621,981 ms summed across all trials, run sequentially on one
machine). Per-family median wall-clock (both backends, all trials for that
family):

| Family | Trials | Median wall-clock |
| --- | --- | --- |
| proposal | 18 | ~107 s |
| detail | 12 | ~65 s |
| reconcile | 12 | ~13 s |
| implementation | 12 | ~60 s |
| apply | 12 | ~15 s |

Per-call **dollar cost** is reported only by the *streaming* families —
`implementation` (via `run_step`) and `apply` (via `apply_finding`) — and only
under `claude`: the *batch* families (`proposal`, `detail`, `reconcile`) report
no token/cost, and `codex` reports no `cost_usd` for any family. Across
`claude`'s 12 cost-bearing trials the per-call cost ran **$0.10–$0.39** (median
$0.30/call for `implementation`, $0.10/call for `apply`); that cost-reporting
slice — the only dollars this matrix can name — totalled **~$2.45** ($1.83
implementation + $0.61 apply). Wall-clock covers all 66 invocations; the dollar
figure is the claude run/apply trials only. Numbers are directional, not a
per-call average across families with different call shapes; re-derive them from
the run with `plan-tool bench report --stamp <s>`.

> **Note (2026-07-04, BACKLOG #74):** the "batch families report no token/cost"
> statement above predates the batch usage-capture fix. `claude`'s batch invoker
> now emits `stream-json`, so the batch families (`proposal`, `detail`,
> `reconcile`) report token/cache — and `cost_usd` — just like the streaming
> families. Re-run the benchmark to refresh the historical figures above.

## What this benchmark does not do

- **No LLM judge** — restated because it is the core claim: no metric is a
  model's opinion.
- **No backend-captured ground truth** — every answer key is hand-authored so
  the backend has never seen it. Unlike the codex-contract step, no fixture
  here is transcribed from a live binary.
- **No loose scratch-repo trees** — scratch sources are embedded as `repo` maps
  to keep the declared footprint exact. Splitting them into loose files is a
  follow-up that must also extend the plan's `creates:` list.
