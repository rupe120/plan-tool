---
title: Lessons Reuse Instrumentation
status: planning
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Expose which lesson bullets survive selection, without changing the rendered
    block
  files:
  - plan_tool/lessons.py
  - tests/test_lessons.py
  complexity: medium
  change_type: feature
  status: current
- id: 2
  title: Add the lessons-events.jsonl writer and reader, modeled on lessons-warnings.jsonl
  files:
  - plan_tool/lessons.py
  - .gitignore
  - tests/test_lessons.py
  complexity: medium
  change_type: feature
- id: 3
  title: Record Tier 1 exposure events in detail's authoring and critique prompts
  files:
  - plan_tool/detail.py
  - tests/test_detail.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 2
- id: 4
  title: Record Tier 1 exposure events in create's and review's lessons prompts
  files:
  - plan_tool/create.py
  - plan_tool/review.py
  - tests/test_create.py
  - tests/test_review.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  - 2
- id: 5
  title: Let parse_lessons_extract_response read an optional applied rule_hash list
  files:
  - plan_tool/lessons.py
  - tests/test_lessons.py
  complexity: low
  change_type: feature
- id: 6
  title: Add a hash-indexed citation block and update both extraction prompts to solicit
    applied rule_hashes
  files:
  - plan_tool/lessons.py
  - plan_tool/detail.py
  - plan_tool/review.py
  - plan_tool/prompts/extract-lessons-detail.md
  - plan_tool/prompts/extract-lessons-review.md
  - tests/test_lessons.py
  - tests/test_detail.py
  - tests/test_review.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  - 5
- id: 7
  title: Record Tier 2 applied events with the surface-scope guard, dropping out-of-scope
    hashes
  files:
  - plan_tool/detail.py
  - plan_tool/review.py
  - plan_tool/lessons.py
  - tests/test_detail.py
  - tests/test_review.py
  - tests/test_lessons.py
  complexity: high
  change_type: feature
  depends_on:
  - 2
  - 3
  - 4
  - 6
- id: 8
  title: Add an end-to-end test that a detail/review run emits exposed and applied
    events
  files:
  - tests/test_detail.py
  - tests/test_review.py
  complexity: medium
  change_type: feature
  depends_on:
  - 7
- id: 9
  title: Point salience_select.py at real reuse counts instead of citation-creation
    counts
  files:
  - experiments/lessons-utility/salience_select.py
  - experiments/lessons-utility/LESSONS.md
  complexity: low
  change_type: feature
  depends_on:
  - 2
---
# Lessons Reuse Instrumentation

## Overview

Add instrumentation that records when a lesson is *reused* (injected into a prompt and, ideally, actually relied on), not just when it is created. Today `_append_citation_jsonl` in `lessons.py` writes exactly one record per bullet at append time — an audit of creation — but nothing is written when a lesson later shapes a `create`/`detail`/`review` output, so there is no signal separating a load-bearing lesson from a one-off that never mattered again. This plan adds two additive telemetry tiers — Tier 1 exposure (which bullets `_select_lessons_body` actually kept, per surface) and Tier 2 application (which injected `rule_hash`es the model reports relying on, piggybacked on the existing `extract-lessons-{detail,review}` extraction calls) — written to a new rolling `.plan-tool/lessons-events.jsonl` log modeled on the `lessons-warnings.jsonl` precedent. It changes no selection behavior: `_select_lessons_body` keeps its current recency truncation, and this plan only makes a later salience-based selector possible by giving it a non-circular signal to score on.

## Problem statement

The `lessons-utility` experiment (`experiments/lessons-utility/salience_select.py`, `measure_lessons.py`) measured the live store and found it has grown to 305+ bullets / ~400 KB / ~100K tokens, but the 48 KB inject cap means only ~35 bullets (≈12%) ever reach a prompt and ~270 (88%) never do, with truncation currently blind recency (`lessons.py:_select_lessons_body`). The experiment prototyped a salience selector joining bullets to citations by `rule_hash` at ~98% coverage, but found the signal is dead: every one of the 306 cited bullets has exactly 1 citation, because the citation sidecars (`project-citations.jsonl` / `general-citations.jsonl`) record creation, not reuse — so salience collapses to recency (LESSONS.md F2). This blocks any relevance/salience-based selection, which is the only lever that fixes the volume problem; selection itself is deliberately out of scope here (a later plan), but it cannot be built or evaluated until a reuse signal exists and has accumulated.

## Architecture

The core design decision is separating two tiers so salience selection never gets built on a circular signal. A naive 'count every injection' metric is circular under today's recency truncation: the newest ~35 bullets are always injected, so a raw retrieval counter just re-encodes recency. **Tier 1 — exposure** is deterministic and near-free: record which bullets `_select_lessons_body`/`load_lessons` actually kept, per command/surface, at each consumption site (`create.py:~1446-1447`, `detail.py:~822-823`/`~970-971`, `review.py:~3075/3082`). It's an honest floor / dead-weight detector (identifies bullets never injected to any consumer) but not sufficient salience on its own. **Tier 2 — application** is the real signal: extend the `extract-lessons-{detail,review}` prompts (`prompts/extract-lessons-{detail,review}.md`), which already run with the full lessons block in context and already parse a JSON response via `parse_lessons_extract_response`, to additionally report the `rule_hash`es of injected lessons the run actually relied on — no new Claude round-trip, since it piggybacks on `extract_and_append_detail_lessons` (`detail.py:5673`) / `extract_and_append_review_lessons` (`review.py:6740`).

Telemetry is written to a new rolling, gitignored, append-only `.plan-tool/lessons-events.jsonl`, mirroring the `lessons-warnings.jsonl` precedent (same cap/rotation, telemetry not source of truth) rather than extending the citations sidecar — citations are an audit-of-creation read by `consolidate`, while reuse is high-volume telemetry with different retention needs, so keeping them separate avoids slowing consolidate's read path. Each event record is `{"rule_hash", "kind": "exposed"|"applied", "source", "ts"}` plus optional `surface`/`command`, written by a new best-effort writer in `lessons.py` (e.g. `record_lesson_events`) following the same never-break-the-run contract as `_append_citation_jsonl`.

A load-bearing guard sits at the Tier 2 boundary for `detail`: its main authoring prompt filters lessons to `_DETAIL_LESSON_SURFACES`, but its extraction prompt (`detail.py:5791`) deliberately reloads all surfaces — including `create-heuristic` and `review-heuristic` — so dedupe stays global (`detail.py:157-158`). Without a guard, Tier 2 could credit the model for relying on a bullet it never actually saw while authoring. The fix is to thread the kept-hash set from the authoring call's surface-filtered `load_lessons` (the Tier 1 exposure set) through to `extract_and_append_detail_lessons`, and drop any reported `rule_hash` outside it before it reaches the events log. `review`'s main and extraction prompts already load the same unfiltered set, so it needs no such guard today, but the same validation is applied there defensively in case that ever diverges.

**Tier 2's carrier is now opt-in (capture default flipped 2026-07-31).** Lesson capture — the `extract-lessons-{detail,review}` round-trip Tier 2 rides on — no longer runs on an ordinary `detail` / `reconcile-plan` invocation; it fires only under `--lessons`. Tier 1 is unaffected: exposure rides the *injection* path, which still runs on every lessons-consuming call. So the two tiers now accrue at different rates, and Tier 2 accrues only as fast as operators opt in. This does not invalidate the design — the piggyback is still free when capture runs, and the no-new-round-trip fence below still binds — but it does mean **Tier 2 cannot be evaluated on ordinary-run volume**. An implementer has three honest options, and should pick one explicitly rather than discover the gap after building: run the evaluation window with `--lessons` on deliberately; ship Tier 1 first and let Tier 2 accumulate slowly; or re-open whether attribution should ride a carrier that no longer runs by default. Do **not** resolve it by re-enabling capture by default — that default was set deliberately.

Writes stay dumb (append `ts` per event); the decay/windowing policy (recency-weighted aggregation vs. a rolling last-N) lives at read time so it can change without a data migration. Finally, `experiments/lessons-utility/salience_select.py` is updated to join on the new `applied` (and optionally `exposed`) counts instead of the constant creation count, dropping its degeneracy warning once the signal is live, and re-run with `--compare` to check whether C3 salience now diverges from C1 recency (the LESSONS.md F2 follow-up).

## Input

This plan extends existing lessons-pipeline contracts rather than building on a green field, so their current shapes bound what Tier 1/Tier 2 can safely add:
- `_select_lessons_body` / `load_lessons` in `plan_tool/lessons.py` — the function that assembles the injected lessons block for `create`/`detail`/`review`. Tier 1 must learn which bullets it kept per surface without altering its output: the rendered block has to stay byte-identical for a given input, so the kept-hash signal has to be a side channel, not a change to the return value consumers already depend on.
- `parse_lessons_extract_response` and the `extract-lessons-{detail,review}` prompts (`prompts/extract-lessons-{detail,review}.md`, consumed by `detail.py:5673` `extract_and_append_detail_lessons` and `review.py:6740` `extract_and_append_review_lessons`) — Tier 2 piggybacks on this existing extraction round-trip and its parsed `{general, project}` response shape, so the prompt and parser extension must keep accepting legacy responses that carry no application list.
- The `lessons-warnings.jsonl` precedent — the existing rolling, gitignored, append-only log whose cap/rotation behavior and best-effort swallow-on-IO-error contract this plan's new `.plan-tool/lessons-events.jsonl` is modeled on.
- `experiments/lessons-utility/salience_select.py`'s `--compare` join — the experiment's existing logic currently keyed on the citation sidecar's constant per-bullet creation count, which this plan's `applied`/`exposed` counts must be able to feed into so the experiment can re-run its comparison.

Verifying these contracts is limited to what the seed describes; the exact current signatures and return shapes of `load_lessons`, `_select_lessons_body`, and `parse_lessons_extract_response` should be re-confirmed against `plan_tool/lessons.py` at implementation time rather than assumed from this synthesis.

## References

- [JSON Lineshttps: — Format specification for the JSONL log format the plan's new .plan-tool/lessons-events.jsonl file must conform to (one JSON record per line, UTF-8, no embedded newlines).
- [json — JSON encoder and decoder — Python documentationhttps: — Standard-library reference for encoding each lessons event to a JSON line and decoding/parsing the extraction call's application-list JSON response.
- [logging.handlers — Logging handlers — Python documentationhttps: — Documents RotatingFileHandler's maxBytes/backupCount rollover model, the reference pattern for the cap/rotation behavior the new events log must mirror from lessons-warnings.jsonl.
- [pathlib — Object-oriented filesystem paths — Python documentationhttps: — Covers Path.open()/append-mode semantics needed to implement the best-effort, never-break-the-run append writer for lesson events.
- [Structured outputs — Claude Platform Docshttps: — Anthropic's official guide to constraining/parsing Claude's JSON responses, relevant to hardening the extract-lessons-{detail,review} prompt so applied rule_hash reporting parses reliably.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- No selection change in this plan — `_select_lessons_body` keeps recency truncation; consuming the new salience signal to change what gets injected is a separate, later plan. This plan only makes that later selector possible.
- No new Claude round-trip — Tier 2 attribution must piggyback on the existing `extract-lessons-{detail,review}` extraction call; if attribution can't ride along for free, ship Tier 1 only and defer Tier 2 rather than adding a dedicated judge call.
- No change to the citations sidecar's creation semantics — `added`/`source` per-creation records in `project-citations.jsonl`/`general-citations.jsonl` stay as-is; reuse is additive telemetry in a separate log.
- No restructure of the store format — surfaces/sectioning of `project.md`/`general.md` is the orthogonal concern of `lessons-store-restructure.md`; this plan is signal-only and applies to both stores as they are today.

## Risks

- Circularity (the central risk) — building salience on Tier 1 exposure alone re-encodes recency; the plan must keep Tier 1 and Tier 2 distinct and steer any future selector toward Tier 2, calling this out wherever exposure counts are surfaced.
- Hot-path cost — exposure recording runs on every lessons-consuming call; must batch the append and no-op on an empty store so it can't add per-bullet IO.
- Tier 2 signal starvation — its carrier (the lesson-capture call) is opt-in as of 2026-07-31, so `applied` counts accrue only on `--lessons` runs while `exposed` counts accrue on every run. A comparison drawn across the two without accounting for that reads Tier 2's smaller sample as "lessons are rarely relied on" when it may only mean capture was off. Record the opt-in rate alongside the counts, or scope the comparison to runs that had capture enabled.
- Self-reference in extraction — the extraction prompt already guards against reading its own output (pending-quarantine); attribution must be confirmed to report injected lessons, not the freshly-extracted ones, so a run can't cite itself.
- Surface-scope mismatch (`detail` only) — the extraction prompt's lessons block is deliberately broader than the authoring prompt's (all surfaces vs. `_DETAIL_LESSON_SURFACES`) so dedupe stays global; without the surface-filtered guard, Tier 2 could credit a `create-heuristic`/`review-heuristic` bullet the model never saw while authoring the detail body, inflating exactly the signal this plan exists to make trustworthy.
- Telemetry growth — reuse events are higher-volume than creation citations; the cap/rotation is mandatory, and the log must stay out of `consolidate`'s read path so it doesn't slow dedup.
- Attribution honesty — Tier 2 is Claude self-report of "what I used," noisy by nature; treat it as a weak ranking signal aggregated over many runs, never as ground truth for a single run — the experiment, not this plan, validates whether it's good enough to drive selection.

## Testing

Unit coverage (mirroring `tests/test_lessons.py`, source→test layout) for: the events writer (append + cap/rotation + best-effort swallow on IO error, same contract as `_append_citation_jsonl`); `load_lessons` exposing kept `rule_hash`es without changing the rendered block (byte-identical for a given input); and `parse_lessons_extract_response` tolerating present/absent/malformed application lists. Add an integration check that a `detail`/`review` run emits the expected `exposed`/`applied` event records, with the invoker seam stubbed per TESTING.md's neutralization table — never spawn the real `claude` binary. Update TESTING.md's neutralization table if this plan introduces a new invoker seam. Existing suites covering `lessons.py`, `detail.py`, and `review.py` must still pass, including the autouse gate that raises if a registered backend binary is spawned.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — unit tests added with the implementation; green before completion.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (feature) — unit tests added with the implementation; green before completion.
- step 5 (feature) — unit tests added with the implementation; green before completion.
- step 6 (feature) — unit tests added with the implementation; green before completion.
- step 7 (feature) — unit tests added with the implementation; green before completion.
- step 8 (feature) — unit tests added with the implementation; green before completion.
- step 9 (feature) — unit tests added with the implementation; green before completion.

## Acceptance criteria

- A `plan-tool detail` or `review` run on a repo with a non-empty lessons store appends `exposed` records for the injected bullets and, when the extraction reports them, `applied` records, to `.plan-tool/lessons-events.jsonl`.
- The events log is gitignored, append-only, capped/rotated like `lessons-warnings.jsonl`, and a forced write failure does not fail the run.
- `load_lessons` returns the same rendered block as before (byte-identical for a given input) plus a way to learn which bullets were kept.
- `parse_lessons_extract_response` returns the same `{general, project}` shape for legacy responses and additionally surfaces the application list when present; malformed/absent application data is ignored, not raised.
- An `applied` `rule_hash` reported for a `detail` run that falls outside the authoring call's surface-filtered kept set is dropped, not recorded, before it reaches the events log.
- `salience_select.py --compare` reads real reuse counts; after some accumulated runs it reports whether C3 salience now diverges from C1 recency (the F2 follow-up), with the degeneracy warning gone.

## Deferred

- Docs updates (`RUNBOOK.md`'s reuse-log/retention notes, the `lessons.py` module docstring) — no step in this plan's decomposition owns `.md`/docstring changes outside `experiments/lessons-utility/LESSONS.md` (step 9); land these as a small follow-up once the steps above ship.
- Decay/windowed-read aggregation policy (recency-weighted vs. rolling last-N, and the half-life/window choice) — this plan keeps writes dumb (append `ts` only) and leaves the read-time decay math to whichever later plan builds the salience selector, since tuning it before Tier 2 data has accumulated would be guesswork.
