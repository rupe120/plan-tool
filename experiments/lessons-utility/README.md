# lessons-utility experiment

**Does the injected "lessons learned" context earn its tokens — and how does
its utility scale as the store accumulates?**

The lessons store (`.plan-tool/lessons/project.md` + `project-citations.jsonl`,
plus user-wide `~/.plan-tool/lessons/general.md`) is appended to on every
`detail`/`review` run and injected wholesale (recency-truncated to 48 KB) into
`create`/`detail`/`review` prompts. We have never measured whether that slice
changes the output, and the store grows unboundedly on disk while only the
newest ~12% ever reaches a prompt. This experiment measures the **utility** of
lessons against their **processing-time and volume cost**, and surveys
libraries for maintaining this kind of store properly.

## Files

| file | what |
|---|---|
| `DESIGN.md` | the experiment: question, hypotheses, conditions (C0–C5), metrics, procedure, plumbing, threats to validity |
| `RESEARCH.md` | library/technique survey (mem0/Letta/Zep/Cognee, sqlite-vec/LanceDB/Chroma, FTS5/bm25s, datasketch) + recommendation matrix |
| `measure_lessons.py` | stdlib, read-only volume + salience accounting tool (mirrors production truncation) |
| `salience_select.py` | C3 prototype: top-K salience selection (citation+recency) with a C1-vs-C3 `--compare`; see LESSONS.md F2 |
| `LESSONS.md` | methodology log + findings (filled as runs complete) |
| `CLEANUP.md` / `cleanup.sh` | what to keep vs remove; safe dry-run-by-default cleanup |

## Quick start

```bash
# Baseline volume report on the live store (auto-discovers .plan-tool/lessons/)
uv run python experiments/lessons-utility/measure_lessons.py

# Simulate a smaller inject budget (condition C2)
uv run python experiments/lessons-utility/measure_lessons.py --max-bytes 24576

# What does detail actually see? (its surface filter)
uv run python experiments/lessons-utility/measure_lessons.py --surfaces cross-step,detail-authoring

# Machine-readable, for diffing conditions
uv run python experiments/lessons-utility/measure_lessons.py --json

# C3 prototype: salience-rank, and diff against today's recency truncation
uv run python experiments/lessons-utility/salience_select.py --compare
uv run python experiments/lessons-utility/salience_select.py --render --max-bytes 24576
```

For the wall-clock/latency side, reuse the run-log analyzer from minimize-claude:

```bash
python scripts/analyze_run_log.py .plan-tool/runs/lutil-*/
```

## Headline baseline (2026-06-18)

305 bullets, ~400 KB, ~101 K tokens on disk — but only **35 bullets (11.5%)**
fit the 48 KB inject cap, so **270 (88.5%) never reach the prompt**. Truncation
is blind recency, so accumulation past ~35 bullets currently buys nothing but a
heavier file. `domain-shape` (204 bullets, the largest surface) is injected by
*no* prompt at all. See `DESIGN.md` for what this implies.

## Status

Scaffolding + baseline measurement + the C3 prototype are complete; A/B runs
not yet executed. The C3 prototype already produced a blocking finding
(LESSONS.md **F2**): citations record *creation*, not *reuse*, so the salience
score collapses to recency — selection can't be evaluated until the tool logs a
reuse signal. The conditions in `DESIGN.md` define the remaining runs; findings
land in `LESSONS.md`; any shipped change goes through a real `plan-seeds/` plan,
not edits inside this experiment.

## Relationship to minimize-claude

minimize-claude cut *redundant Claude round-trips* (how often we call). This
cuts *wasted context per call* (what we stuff in). It reuses that experiment's
harness conventions: isolated `--output-dir` + `PLAN_TOOL_PLANS_DIR`, slug-
prefixed runs, `analyze_run_log.py`, and the methodology lessons (noise floor
first, measure quality not just speed).
