# Lessons learned — lessons-utility experiment

Living methodology log. Findings land here as conditions run; pair with
`DESIGN.md` (the plan), `RESEARCH.md` (the library survey), and
`measure_lessons.py` (the volume tool). Reuses the minimize-claude harness
conventions.

## Methodology (carried from minimize-claude, applied here)

1. **Instrument before measuring.** Confirm every consuming prompt
   (`create`/`detail`/`review`) logs the injected-lessons byte/token count via
   `run_logger=` *before* any A/B run, so cost is attributable per condition.
   `measure_lessons.py` covers the static side; the run log must cover the
   per-call side.
2. **`claude_call_end` is authoritative** for wall-clock — not `phase_end`.
   Reuse `scripts/analyze_run_log.py` unchanged.
3. **Noise floor first.** N≥2 runs of C1 (full lessons) per task; record the
   quality-score and wall-clock variance band. A condition only "wins" above it.
4. **Measure quality, not just speed.** A token/latency cut that regresses
   output is not a win. Use lesson-hit attribution + LLM-judge + manual rubric
   (DESIGN.md "Dependent variables").
5. **Let data re-rank priorities.** The a-priori guess is "selection beats
   recency" (H3); don't assume — C0 (lessons OFF) might show the whole block is
   marginal, which would be the bigger result.

## Findings

### F1 — Baseline volume: the store is 88.5% dead weight at the prompt (2026-06-18)

`measure_lessons.py` on the live store:

- 305 bullets, 405,408 bytes (~101 K tok) on disk.
- Only **35 bullets (11.5%, ~49 KB / ~12 K tok)** fit the inject cap.
- **270 bullets (88.5%) dropped** by blind recency truncation every call.
- Surface mix: `domain-shape` 204, `cross-step` 60, `detail-authoring` 25,
  `create-heuristic` 13, untagged 3.
- **`domain-shape` (the largest surface, 204 bullets) is injected by no prompt**
  — `detail` filters to `cross-step`+`detail-authoring`; create/review inject
  all surfaces but then recency-truncate, so most `domain-shape` bullets are
  doubly unlikely to surface.
- Citations: 304 records; concentrated in a handful of `detail:*` sources;
  accumulation is almost entirely 2026-06 (303 of 304) — the store is young and
  growing fast, so the volume problem is *accelerating*.

**Implication.** Accumulation past ~35 bullets currently changes nothing at the
prompt except a heavier disk file and slower `lessons consolidate` passes. The
cost/volume problem is a **selection** problem (which 35?) not a storage or
recall problem. This is the strongest argument for H3 (top-K selection) before
any A/B run is even done.

### F2 — Citations record CREATION, not reuse → salience signal is dead (2026-06-18)

Built the C3 prototype (`salience_select.py`): join bullets→citations by
`rule_hash` (98% coverage), score by citation count + recency, pack top-K under
a budget. The join and packing work, but the signal doesn't:

- **Every bullet has exactly 1 citation** (306 distinct bullets, 306 records,
  max 1/bullet). `project-citations.jsonl` writes one audit record when a lesson
  is *appended*, never again. So citation *count* is 1:1 with bullet existence —
  a constant, not a salience measure.
- With the default 0.5/0.5 score the citation term is constant, so **C3
  degenerates to pure recency** — Jaccard 0.87 vs C1, the 3 "rescued" bullets
  are recency near-misses, not high-value lessons.
- Cranking `--w-cite 1.0 --w-recency 0.0` makes it *worse*, not better: with a
  constant signal and no recency tiebreak, selection becomes arbitrary (oldest-
  first by stable sort), Jaccard 0.00 — a vivid demonstration that the signal
  carries no information.

**This kills H3 as currently specified, and it's the most actionable result so
far:** salience-based selection is the right idea, but it requires a signal the
tool does not yet emit. The prerequisite change is to **record a reuse event** —
increment a per-lesson counter (or append a `retrieved`/`applied` citation
record) each time a lesson actually surfaces in or influences a run. The earlier
"by-source skew" (F1: `detail:security-check-command` = 36) was a red herring:
that's 36 *different* bullets from one detail run, not one bullet reused 36×.

The scoring machinery in `salience_select.py` is correct and ready for a real
reuse signal; it just has nothing to chew on. So the experiment's first shipped
change may need to be **instrumentation (log reuse), not selection** — selection
can't be evaluated until the signal exists. Recency truncation, for all its
bluntness, is currently the *only* signal available.

**Follow-up plan drafted:** `plan-seeds/lessons-reuse-instrumentation.md` — adds
a two-tier reuse signal (deterministic exposure + Claude-attributed application,
the latter piggybacking on the existing extraction call so it costs no new
round-trip) writing to a rolling `.plan-tool/lessons-events.jsonl`. Its step 5
rewires `salience_select.py` onto the real counts and re-runs `--compare`. Note
the circularity trap it calls out: exposure counts re-encode recency, so the
*non-circular* signal is Tier 2 application, not Tier 1 exposure.

### F3 — _(pending: noise floor for C1)_

### F4 — _(pending: C0 vs C1 utility — does OFF regress?)_

### F5 — _(pending: latency vs injected bytes, H4)_

## Open questions

- Does the LLM-judge detect *any* C0-vs-C1 quality difference above the noise
  floor? If not, H1 is in trouble and the whole block is suspect.
- ~~Is citation count a usable salience signal?~~ **Answered (F2): no — it's a
  creation artifact, constant at 1/bullet. Needs a reuse event first.**
- Would surface-correct filtering alone (stop injecting `domain-shape` where
  unused) recover most of the budget without any new dependency?
