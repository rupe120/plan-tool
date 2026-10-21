# Experiment design — lessons-utility

**Question.** Do injected "lessons learned" actually pay for themselves — in
output quality — given what they cost in tokens and latency? And how does that
utility scale as the store accumulates (the *volume* axis)?

This is the natural follow-on to **minimize-claude** (which cut *redundant*
Claude round-trips). That experiment asked "are we calling Claude too often?";
this one asks "is the context we *stuff into* each call earning its keep?".

## Why now — the volume problem is already real

`measure_lessons.py` against the live store (2026-06-18):

| metric | value |
|---|---|
| disk size | 405,408 bytes (~101 K tok) |
| total bullets | 305 |
| avg / max bullet | 1,327 / 2,358 bytes |
| inject budget (`_MAX_INJECT_BYTES`) | 49,152 bytes |
| **bullets actually injected** | **35 of 305 (11.5%)** |
| **bullets dropped by truncation** | **270 (88.5%)** |
| injected size | ~49 KB (~12 K tok) per consuming prompt |

Two findings fall straight out of the baseline:

1. **88.5% of accumulated lessons never reach the prompt.** Truncation is
   blind recency (`_select_lessons_body` keeps the newest bullets that fit).
   So the store *grows unboundedly on disk* but the prompt only ever sees an
   arbitrary newest-48 KB slice — accumulation past ~35 bullets buys nothing
   except a heavier disk file and slower consolidation passes.
2. **~12 K tokens are spent on lessons in every `create`/`detail`/`review`
   prompt** — and we have never measured whether that slice changes the
   output. The whole premise ("lessons make future plans more correct") is
   currently an article of faith.

`domain-shape` (204 bullets) dominates the corpus but is consumed by *no*
prompt surface (detail injects only `cross-step` + `detail-authoring`; create
and review inject everything). So a large majority of bytes are dead weight to
most consumers even before truncation.

## Hypotheses

- **H1 (utility).** Removing the lessons block measurably degrades output
  quality on tasks the lessons are about. *If we can't detect a quality drop
  with lessons OFF, the block isn't earning its tokens.*
- **H2 (volume → diminishing returns).** Beyond a small K, additional injected
  bullets do not improve quality — utility per token falls as volume rises.
- **H3 (selection beats recency).** Top-K *relevance/salience* selection at a
  fraction of the byte budget matches or beats today's blind newest-48 KB
  injection.
- **H4 (latency).** Lessons injection adds measurable wall-clock per Claude
  call that scales with injected bytes (TTFT / throughput effect).

## Conditions (independent variable: what lessons reach the prompt)

| # | condition | how |
|---|---|---|
| C0 | **OFF** — no lessons block | inject the empty-bundle placeholder |
| C1 | **FULL (control)** — current behavior | unchanged: newest-48 KB recency truncation |
| C2 | **half budget** | `_MAX_INJECT_BYTES = 24576` — does halving hurt? |
| C3 | **top-K salience** | inject only the K bullets ranked by recency + citation count (from `project-citations.jsonl`), small byte budget |
| C4 | **top-K lexical** | inject only the K bullets a BM25/FTS5 query (task title + files) retrieves |
| C5 | **volume ladder** | C1 behavior over corpora at 25 / 50 / 100% size, plus a **synthetic 2× / 4× inflation** to project future scale |

C3/C4 are *prototype* conditions — they need a small selection shim (see
"Plumbing"). C0–C2 and C5 need no code beyond an env knob and corpus slicing.

## Dependent variables (metrics)

**Cost / volume** — from `measure_lessons.py` + run logs:
- injected bytes / estimated tokens per consuming prompt (per condition)
- % of corpus injected; bullets dropped
- wall-clock per `claude_call_end`, bucketed by phase (reuse
  `scripts/analyze_run_log.py`)

**Utility / quality** — the hard part, measure deliberately:
- **Lesson-hit attribution.** For a fixed task whose lessons are known (e.g.
  the `review.py` severity-vocabulary or `check_file_existence` fan-out
  bullets), does the OFF output regress on exactly the thing the lesson warns
  about? This is the cleanest signal — a *named* lesson with a *checkable*
  consequence.
- **Pairwise LLM-judge.** Blind A/B of C0 vs C1 outputs for the same task,
  scored by an independent Claude judge on correctness/completeness. Run both
  orderings to cancel position bias; N≥2 per task for the noise floor.
- **Manual rubric.** Spot-check a sample by hand — the minimize-claude lesson
  "measure quality, not just speed" applies: don't trust the judge blindly.

## Procedure

1. **Baseline volume** (done): `measure_lessons.py` numbers above. Re-run per
   condition with `--max-bytes` / `--surfaces` to get the cost side for free.
2. **Pick attribution tasks.** Choose 2–3 tasks whose relevant lessons are
   named and whose violation is *checkable* (severity vocabulary, shared-
   primitive fan-out, path-style). These give a deterministic-ish utility
   signal independent of the judge.
3. **Establish the noise floor** (minimize-claude lesson #3): N≥2 runs of C1
   per task; measure quality-score and wall-clock variance. Wins only count
   above that band.
4. **A/B the conditions.** For each task run C0 vs C1 (and C2/C5 as budget
   allows), isolated per minimize-claude's harness conventions:
   - `--output-dir <scratch>` + `PLAN_TOOL_PLANS_DIR=<scratch-manifest>` so
     runs never touch the real plans dir.
   - slug-prefix every run (`lutil-c0-…`, `lutil-c1-…`) for filterable logs.
   - run re-creations **sequentially** (shared `.plan-tool/plans.json` races).
5. **Score.** LLM-judge pairwise + manual rubric + attribution check.
6. **Analyze.** `analyze_run_log.py` for wall-clock; `measure_lessons.py` for
   bytes/tokens; tabulate quality vs cost per condition in `LESSONS.md`.

## Plumbing (smallest seams to enable the conditions)

- **C0 / C2 (no code, or one knob).** `load_lessons(..., max_bytes=...)` already
  parameterizes the budget. Add a `PLAN_TOOL_LESSONS_MAX_BYTES` env read (and
  a `PLAN_TOOL_LESSONS_DISABLE=1` that returns an empty bundle) so conditions
  are set without editing source between runs. *Behavior-preserving when unset*
  — gate on the env var, default to today's constant. **This is the only
  source change the experiment needs; keep it minimal and out of the hot path.**
- **C3 (salience).** Prototype built (`salience_select.py`): ranks bullets by
  `w_cite·citations + w_recency·recency`, joins on `rule_hash` (98% coverage),
  packs top-K under a budget; `--compare` diffs it against C1. **Blocked finding
  (LESSONS.md F2): `project-citations.jsonl` records creation, not reuse, so
  every bullet has exactly 1 citation and the score collapses to recency.** C3
  cannot be fairly evaluated until the tool logs a *reuse* event (per-lesson
  retrieval/apply counter). That instrumentation is the real prerequisite plan
  (drafted: `plan-seeds/lessons-reuse-instrumentation.md`); the selector is ready
  to consume the signal once it exists.
- **C4 (lexical).** Prototype with **bm25s** or stdlib **SQLite FTS5** over the
  bullets, query = task title + `files:` list, keep top-K. No new runtime dep
  if FTS5.
- **C5 (volume ladder).** Pure data: slice/concat `project.md` into 25/50/100%
  and synthetic 2×/4× corpora in scratch, point `load_lessons` at them via a
  copied `.plan-tool/lessons/` under `--output-dir`. No code.

## What would change based on the result

- **H1 fails (no detectable quality drop with lessons OFF):** the block isn't
  worth ~12 K tokens/call — shrink the default budget hard or gate injection on
  task relevance. Biggest possible win.
- **H1 holds but H2/H3 also hold:** keep lessons, but switch from blind recency
  truncation to **top-K salience/lexical selection** (RESEARCH.md §3) — same or
  better quality at a fraction of the tokens. Most likely outcome given the
  baseline.
- **H4 holds strongly:** latency alone justifies the budget cut even before
  quality.

Whatever wins becomes a real plan (`plan-seeds/` → `create --from-existing`),
not a change made inside this experiment. The experiment's job is the evidence.

## Threats to validity

- **Non-determinism.** Claude output varies run-to-run; the noise floor (step 3)
  is mandatory, not optional.
- **Judge bias.** LLM judges favor longer/more-confident outputs and first
  position — run both orderings, blind the conditions, cross-check by hand.
- **Attribution-task selection bias.** Tasks chosen *because* a lesson exists
  for them over-state utility; balance with tasks unrelated to any lesson.
- **Token estimate ≠ real tokenizer.** `measure_lessons.py` uses ~4 chars/tok;
  fine for ranking conditions, not for billing. The run log's real durations are
  the authoritative latency metric.
- **Corpus inflation realism.** Synthetic 2×/4× duplicates skew dedup/selection
  signals; generate inflated corpora by *paraphrase*, not copy, where possible.
