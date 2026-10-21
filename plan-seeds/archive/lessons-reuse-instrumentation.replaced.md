> **Replaced**: this file has been superseded by `docs/implementation-plans/2-lessons-reuse-instrumentation.md`.
> Preserved here for history; do not edit.

# Plan seed: instrument lesson *reuse* (the missing salience signal)

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing plan-seeds/lessons-reuse-instrumentation.md
```

It is **not** itself a plan — `plan-tool create` consumes the prose below and
proposes a step decomposition; the author then runs `plan-tool detail` per step.

---

## Goal

Make the lessons store record **when a lesson is reused**, not just when it is
created. Today `project-citations.jsonl` / `general-citations.jsonl` write
exactly one record per bullet *at append time* (audit of creation). Nothing is
written when a lesson is later injected into a prompt or actually shapes an
output. So there is no signal that distinguishes a load-bearing lesson cited in
fifty later runs from a one-off that has never mattered again.

This blocks relevance/salience-based selection — the only lever that fixes the
volume problem (see below). Add the signal; selection is a separate, later plan.

## Why now — the evidence (experiments/lessons-utility)

The `lessons-utility` experiment measured the live store and prototyped a
salience selector (`experiments/lessons-utility/salience_select.py`,
`measure_lessons.py`):

- The store is **305+ bullets / ~400 KB / ~100 K tokens**, but the 48 KB inject
  cap means **~35 bullets (≈12%) reach the prompt and ~270 (88%) never do** —
  truncation is blind recency (`lessons.py:_select_lessons_body`).
- The selector proved the right *mechanism* (join bullets→citations by
  `rule_hash` at ~98% coverage, top-K packing) but found the *signal is dead*:
  **every one of the 306 cited bullets has exactly 1 citation** — because the
  citation is a creation record, not a reuse record. Salience therefore
  collapses to recency (LESSONS.md **F2**).

**Conclusion that motivates this plan:** the first shippable change toward
fixing lessons volume is *instrumentation (record reuse), not selection*.
Selection cannot be evaluated until the reuse signal exists and has accumulated.

## Context already in place (pre-this-plan)

- **Citations sidecars** (`lessons.py`): `_append_citation_jsonl` writes
  `{"rule_hash", "rule_preview", "added", "source"}` per appended bullet;
  `rule_hash = _rule_hash(rule)` = `sha256(rule.strip().lower())[:16]`
  (`lessons.py:_rule_hash`). Append-only, best-effort, safe to lose.
- **`load_lessons(repo_root, *, surfaces, max_bytes)`** → `LessonsBundle`, via
  `_select_lessons_body` (`lessons.py:~449`) which already knows exactly which
  bullets it keeps — but currently returns only the rendered string.
- **Consumption sites** that inject `${lessons_block}`: `create.py:~1446-1447`,
  `detail.py:~822-823` and `~970-971` (surface-filtered to `detail-authoring` +
  `cross-step` + `domain-shape` — `_DETAIL_LESSON_SURFACES`, `detail.py:159-161`),
  `review.py:~3075/3082`.
- **Extraction round-trips** that *already* run with a lessons block in
  context and already parse a JSON response: `extract_and_append_detail_lessons`
  (`detail.py:5673`; prompt built by `_render_extract_detail_lessons_prompt`,
  `detail.py:5791`) / `extract_and_append_review_lessons` (`review.py:6740`;
  prompt block at `review.py:6806`), prompts
  `prompts/extract-lessons-{detail,review}.md`, parser
  `parse_lessons_extract_response` (shape `{"general": [...], "project": [...]}`).
- **Surface-scope asymmetry (load-bearing for Tier 2 — see scope-of-work step
  3).** `review`'s main prompt and its extraction prompt both call
  `load_lessons(repo_root)` unfiltered, so they see identical bullets — no
  mismatch. `detail` does **not** match: its main authoring prompt filters to
  `_DETAIL_LESSON_SURFACES`, but its extraction prompt (`detail.py:5791`)
  deliberately loads **all** surfaces — including `create-heuristic` and
  `review-heuristic` — "so dedupe stays global" (`detail.py:157-158`). So the
  extraction call can see lessons the model never saw while authoring the
  detail body. Tier 2 must not attribute "applied" against that superset.
- **Rolling-telemetry precedent:** `.plan-tool/lessons-warnings.jsonl` —
  gitignored, append-only, ~5000-entry cap. The reuse log should follow this
  exact pattern (telemetry, not source of truth), NOT bloat the citations
  sidecar.

## The circularity trap (read before designing — load-bearing)

A naive "count every injection" signal is **circular**: under today's recency
truncation the newest ~35 bullets are *always* injected, so a raw retrieval
counter just re-encodes recency and salience selection built on it would chase
its own tail. The design must separate two tiers:

- **Tier 1 — exposure (deterministic, ~free, weak signal).** Record which
  bullets `_select_lessons_body` actually kept, per command/surface. Honest
  value despite the circularity: it identifies bullets that are **never**
  injected to **any** consumer (the ~270 dead ones — archival candidates) and
  gives differential exposure across surface filters (a `domain-shape` bullet
  create sees but detail never does). It is *not* a sufficient salience signal
  on its own; treat it as a floor / dead-weight detector.
- **Tier 2 — application (judgment, ~free marginal cost, the real signal).** The
  `extract-lessons-{detail,review}` prompts already run with the full lessons
  block in context. Extend them to *also* report the `rule_hash`es of the
  injected lessons they actually relied on. This is the non-circular signal:
  it reflects influence on output, not mere presence, and it costs no new
  Claude round-trip (it piggybacks on a call that already happens).

Salience selection (a later plan) should score on **Tier 2** counts, optionally
backstopped by Tier 1 for cold-start; this plan only needs to *emit and
accumulate* both, plus give the experiment a way to read them.

## Scope of work

1. **Reuse-events log + writer.** Add a rolling, gitignored, append-only
   `.plan-tool/lessons-events.jsonl` (mirror the `lessons-warnings.jsonl`
   precedent: same cap/rotation, telemetry not truth). One record per event:
   `{"rule_hash", "kind": "exposed"|"applied", "source", "ts"}` (+ optional
   `surface`, `command`). New writer in `lessons.py` (`record_lesson_events` or
   similar), best-effort like `_append_citation_jsonl` — a failed write must
   never break the run that triggered it. Decide in detail: extend the citations
   sidecar with a `kind` field vs. a separate events log. **Recommend separate**
   — citations are an audit-of-creation read by `consolidate`; reuse is
   high-volume telemetry with different retention.

2. **Tier 1 exposure capture.** Have `_select_lessons_body` / `load_lessons`
   expose which bullets were kept (e.g. return their `rule_hash`es alongside the
   bundle, or a sibling accessor). Keep the rendered-string contract for
   existing callers intact — add, don't break. At each consumption site
   (`create`/`detail`/`review`) record an `exposed` event per kept bullet,
   tagged with command + surface set. Hot-path-safe: a single batched append,
   gated so it's a no-op when the store is empty.

3. **Tier 2 application attribution.** Extend `prompts/extract-lessons-detail.md`
   and `prompts/extract-lessons-review.md` to additionally return the
   `rule_hash`es (or verbatim rule snippets the tool can hash) of injected
   lessons the run actually relied on — a new optional key in the JSON response.
   Extend `parse_lessons_extract_response` to read it (absent/garbled →
   empty, never an error: this is advisory telemetry). Record an `applied` event
   per reported hash from `extract_and_append_{detail,review}_lessons`.
   **Scope the eligible set to what the model actually authored against, not
   whatever the extraction call happens to load:** for `detail`, thread the
   kept-hash set from the authoring call's surface-filtered `load_lessons`
   (Tier 1's exposure set, step 2) through to `extract_and_append_detail_lessons`,
   and drop any reported `rule_hash` that falls outside it (e.g. a
   `create-heuristic`/`review-heuristic` bullet the extraction prompt's
   unfiltered reload can see but the authoring prompt never showed the model).
   `review` needs no such guard today since its main and extraction prompts
   already load the same unfiltered set, but apply the same validation there
   too, defensively, in case that ever diverges.

4. **Decay / windowing.** Raw lifetime counts drift toward whatever was created
   most (older lessons accrue more exposure forever). Define the read-time
   aggregation so salience can be recency-weighted: either store `ts` and let
   readers compute a windowed/decayed count, or keep a rolling last-N. Keep
   *writes* dumb (append `ts`); put the decay math in the reader so the policy
   can change without a migration. Document the chosen half-life / window.

5. **Experiment integration.** Update
   `experiments/lessons-utility/salience_select.py` to join on the new `applied`
   (and optionally `exposed`) counts instead of the constant creation count, and
   drop its degeneracy warning once the signal is live. Re-run `--compare` and
   record whether C3 now diverges from C1 (LESSONS.md F2 follow-up). This closes
   the loop the experiment opened.

6. **Tests.** Unit coverage for: the events writer (append + cap/rotation +
   best-effort swallow on IO error); `load_lessons` exposing kept hashes without
   changing the rendered block; `parse_lessons_extract_response` tolerating
   present / absent / malformed application lists; an integration check that a
   `detail`/`review` run emits the expected event records (with the invoker seam
   stubbed per TESTING.md — do not spawn real `claude`). Mirror source→test
   layout (`tests/test_lessons.py`).

7. **Docs.** Update `RUNBOOK.md` (the new log, retention, how to read reuse
   counts), the `lessons.py` module docstring, and TESTING.md's neutralization
   table if a new seam is added. Keep it terse per repo norms.

## Non-goals

- **No selection change in this plan.** `_select_lessons_body` keeps recency
  truncation; consuming salience is a *separate* later plan (this one only makes
  it possible). Resist the urge to wire scoring into the loader here.
- **No new Claude round-trip.** Tier 2 must piggyback on the existing extraction
  call. If attribution can't ride along for free, ship Tier 1 only and defer
  Tier 2 — do not add a dedicated judge call.
- **No change to the citations sidecar's creation semantics** — `added` /
  `source` per-creation records stay; reuse is additive telemetry.
- **No restructure of the store format** — that's
  [`lessons-store-restructure.md`](lessons-store-restructure.md) (surfaces /
  sectioning), an orthogonal axis. This plan is signal-only and applies to both
  `project.md` and `general.md` stores as they are today.

## Acceptance criteria (plan-level)

- A `plan-tool detail` or `review` run on a repo with a non-empty lessons store
  appends `exposed` records for the injected bullets and (when the extraction
  reports them) `applied` records, to `.plan-tool/lessons-events.jsonl`.
- The events log is gitignored, append-only, capped/rotated like
  `lessons-warnings.jsonl`, and a forced write failure does not fail the run.
- `load_lessons` returns the same rendered block as before (byte-identical for a
  given input) plus a way to learn which bullets were kept.
- `parse_lessons_extract_response` returns the same `{general, project}` for
  legacy responses and additionally surfaces the application list when present;
  malformed/absent application data is ignored, not raised.
- An `applied` `rule_hash` reported for a `detail` run that falls outside the
  authoring call's surface-filtered kept set is dropped, not recorded, before
  it reaches the events log.
- `salience_select.py --compare` reads real reuse counts; after some accumulated
  runs it reports whether C3 salience now diverges from C1 recency (the F2
  follow-up), with the degeneracy warning gone.

## Risks

- **Circularity (the central risk).** Building salience on Tier 1 exposure alone
  re-encodes recency. The plan must keep Tier 1 and Tier 2 distinct and steer
  the *future* selector toward Tier 2. Call this out wherever exposure counts
  are surfaced so a later plan doesn't naively rank on them.
- **Hot-path cost.** Exposure recording runs on every lessons-consuming call;
  batch the append and no-op on an empty store so it can't add per-bullet IO.
- **Self-reference in extraction.** The extraction prompt already guards against
  reading its own output (pending-quarantine); confirm attribution reports
  *injected* lessons, not the freshly-extracted ones, so a run can't cite itself.
- **Surface-scope mismatch (`detail` only).** The extraction prompt's lessons
  block is deliberately broader than the authoring prompt's (all surfaces vs.
  `_DETAIL_LESSON_SURFACES`) so dedupe stays global. Without the step-3 guard,
  Tier 2 could credit a `create-heuristic`/`review-heuristic` bullet the model
  never saw while authoring the detail body — inflating exactly the signal
  this plan exists to make trustworthy.
- **Telemetry growth.** Reuse events are higher-volume than creation citations;
  the cap/rotation is mandatory, and the log must stay out of `consolidate`'s
  read path so it doesn't slow dedup.
- **Attribution honesty.** Tier 2 is Claude self-report of "what I used" — noisy
  by nature. Treat it as a weak ranking signal aggregated over many runs, never
  as ground truth for any single run; the experiment, not this plan, validates
  whether it's good enough to drive selection.

## Do not regress

- **Best-effort telemetry never breaks a run** — same contract as the citations
  sidecar and warnings log.
- **Invoker seam** — any test driving `detail`/`review` stubs the Claude
  invoker per TESTING.md; the autouse gate must stay green.
- **Acyclic layering** — `lessons.py` stays a leaf below the orchestrators;
  don't import `create`/`detail`/`review` into it.
- **Exit-code convention / concise docs** per repo norms.
