> **Replaced**: this file has been superseded by `docs/implementation-plans/2-purity-findings-cache.md`.
> Preserved here for history; do not edit.

# Plan seed: cache per-step purity findings by detail-file + declared-files fingerprint

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing docs/implementation-plans/plan-seeds/purity-findings-cache.md --iterate
```

It is **not** itself a plan — `plan-tool create` consumes the prose below and
proposes a step decomposition; the author then runs `plan-tool detail` per step.

> **Source:** `BACKLOG.md` **#145** — "Cache per-step purity/quality findings by
> detail-file fingerprint; share the cache between `detail`'s own sweep and
> standalone `completeness-audit`." Companion to **#144** (the magnitude-threshold
> decision, resolved 2026-07-17 — see `BACKLOG.md`'s `#144` entry for the chosen
> metric/threshold this plan should also wire in; see "Fold in #144" below). This
> seed's final step must remove or mark shipped both `BACKLOG.md` entries #144 and
> #145 once the fix lands, per the file's own bookkeeping convention.

## Problem statement

The per-step MIXED-STEP purity judgment (`plan_tool/detail.py:collect_detail_quality_findings`,
prompt at `plan_tool/prompts/detail-quality.md`) is expensive — BACKLOG #133
measured ~130-255s per step (~130-150KB prompts) — and is invoked from **two
independent call sites with no cache between them**:

1. `plan_tool/detail.py`'s own post-authoring per-step convergence loop (two
   call sites: the initial scan around `detail.py:3524`, and the loop's re-scan
   around `detail.py:3982`) — this is "detail's post-detail completeness sweep"
   BACKLOG #115 documents.
2. `plan_tool/cli/completeness_phases.py:_collect_purity_split_findings`,
   called whenever `completeness-audit` runs with purity on (`run_purity=True`,
   gated by the shipped `--no-purity` flag) — a **separate process**, possibly
   run hours or days after `detail` last validated the same step.

A step whose detail content is byte-identical to what `detail` already
validated still pays a full Claude call the next time a standalone
`completeness-audit` runs on it — pure waste. Persist each step's purity
verdict and skip the Claude call on a cache hit.

## Ground truth on what the purity call actually reads (confirmed at HEAD)

`render_detail_quality_prompt` (`plan_tool/detail.py:932`) builds the prompt from:

- `plan.title`, `step.title`/`complexity`/`depends_on` (frontmatter — cheap, changes rarely)
- `step_files_block` — the step's **declared** `files:` list (frontmatter)
- `files_contents_block` — the **current on-disk contents** of those declared
  files, via `_format_files_contents_block(step, repo_root, ...)` — this is
  the part that makes the prompt (and therefore the judgment) depend on more
  than the detail file's own bytes
- `detail_body_block` — the step's detail markdown, verbatim
- `lessons_block` — repo-wide lessons (`load_lessons(repo_root, surfaces=_DETAIL_LESSON_SURFACES)`)

`collect_detail_quality_findings` (`plan_tool/detail.py:1380`) returns a
**merged** list: deterministic per-step grounding findings
(`collect_step_grounding_findings` — file-check, files-coherence,
detail-coverage, detail-body; these read current code state, not just the
detail file) **plus** the Claude-derived findings (grounding-semantic findings,
the `## Structural findings` MIXED-STEP purity bullet, `## Advisory altitude
findings`, and `## Findings`). `_collect_purity_split_findings` (the
completeness-audit call site) keeps only the `granularity-split`/`medium`
(MIXED-STEP) subset from that merged list; `detail.py`'s own loop needs the
full set to converge.

**This is why a naive cache keyed only on the detail file's hash is unsound**:
the prompt (and therefore the Claude judgment) also depends on the current
contents of the step's declared `files:` — a step whose detail prose is
byte-identical but whose declared files changed underneath it (a sibling step
landed first, or a hand-edit) could legitimately purity-flag differently on a
second call. Caching only the detail-file hash would silently serve a stale
verdict in that case.

## Resolved design decisions

1. **Cache key = detail-file content hash + a fingerprint of the step's own
   declared `files:` at their current content — not the detail file alone.**
   Reuse `plan_tool/fingerprint.py`'s existing primitives rather than
   inventing new hashing: `compute_detail_bundle_fingerprint(plan, plan_path,
   repo_root)` already produces a `{step-detail-relpath: sha256}` map (the
   detail-file half of the key); for the declared-files half, hash each of
   `step.files` the same way `compute_code_fingerprint` hashes `step.files`/
   `creates` (via `plan_tool/drift_detection.py:compute_content_hash`) and
   fold the per-file digests into one combined key (e.g. a stable
   concatenation-then-hash, or a `dict` compared key-for-key — pick whichever
   is simpler to persist as a single cache-lookup key; a stable sorted-items
   digest is likely simplest). This closes BACKLOG #145's own flagged risk
   ("cache invalidation must include everything the purity prompt actually
   reads, not just the detail file's own hash") rather than leaving it
   undecided for `create` to rediscover. Lessons-file content is intentionally
   **excluded** from the key (decision 5) — see below.

2. **Scope the cache to the purity (`granularity-split`/MIXED-STEP) verdict
   specifically — not the full `collect_detail_quality_findings` return.**
   The deterministic grounding findings folded into that return
   (`collect_step_grounding_findings`) are cheap (no Claude call) and already
   re-run fresh on every call regardless of this cache — cache only the
   **Claude-derived structural/MIXED-STEP purity finding(s)** (present or
   absent) per step. This matches BACKLOG #145's own title ("cache per-step
   purity/quality findings") and keeps the cache's correctness surface to
   exactly the expensive, cacheable part. On a cache hit, `detail.py`'s own
   loop and `_collect_purity_split_findings` each still run the cheap
   deterministic grounding findings fresh (unchanged, no new cost) and splice
   in the cached purity verdict instead of calling Claude for it.
   - **Practically**: the shared cache-checking helper this plan builds wraps
     the *Claude call + parse* portion of `collect_detail_quality_findings`
     (rendering the prompt, invoking, and lifting `## Structural findings`),
     not the deterministic-findings portion, which callers keep invoking
     directly as they do today.

3. **Persist the cache in a small dedicated file under `.plan-tool/`, not the
   audit-run sidecar.** The audit JSON sidecars under `.plan-tool/runs/<slug>/`
   are timestamped report history (one per audit invocation) — not a stable
   lookup target for "the last known verdict for step N." Use a small
   dedicated cache file instead, following the existing `.plan-tool/` tool-state
   convention (alongside `runs/`, `checkpoints/`) — e.g.
   `.plan-tool/purity-cache/<slug>.json` — keyed by step id, storing the
   combined fingerprint key (decision 1) and the cached purity finding(s) (or
   an explicit "no finding" marker, not just an absent key, so a confirmed-pure
   step doesn't get re-checked every time either). Needs a `DATA_CONTRACT.md`
   entry since this is a new persisted shape.

4. **Both call sites read and write the same cache.** `detail.py`'s two call
   sites (`detail.py:3524`, `detail.py:3982`) and
   `completeness_phases._collect_purity_split_findings` all route through the
   same shared cache-check helper (decision 2), so whichever one runs first
   for a given step's current (detail + declared-files) content pays the
   Claude cost once and the other reuses it. Concretely: build one small
   function — e.g. `plan_tool/detail.py:_cached_purity_findings(plan_path,
   step, *, repo_root, plan_name, invoker, cache_path, ...) -> list[Recommendation]`
   — that computes the combined key, checks the cache, calls
   `collect_detail_quality_findings` only on a miss, and writes the result
   back; both call sites and `_collect_purity_split_findings` call this
   instead of `collect_detail_quality_findings` directly for the
   Claude-judged portion.

5. **Lessons-file content is excluded from the cache key — accept the
   (rare, low-severity) staleness this implies.** `render_detail_quality_prompt`
   folds in `load_lessons(...)`'s current content, so in principle a lessons
   update could change what the purity prompt would judge. Including repo-wide
   lessons content in the key would invalidate *every* step's cache entry on
   any lessons update, defeating the cache's purpose for an unrelated reason.
   Given lessons content changes far less often than code/detail content and
   its effect on the *purity* (not grounding) judgment specifically is
   marginal, exclude it from the key. Document this explicitly as an accepted
   staleness window, not a silent gap — a future BACKLOG item can revisit if
   it proves to matter in practice.

6. **Fold in BACKLOG #144's resolved magnitude-threshold decision as an
   extension of the same call sites.** #144 (resolved 2026-07-17, see
   `BACKLOG.md`) decided: on a cache **miss** (decision 1's key doesn't match),
   before spending a Claude call, compute a magnitude signal — a diff ratio
   (`difflib.SequenceMatcher`) scoped to the concatenated `## Implementation` +
   `## Tests` sections of the detail body only (not the whole file), comparing
   the cached content against the current content — plus an unconditional
   OR on any change to the step's `files:`/`change_type:`/`depends_on:`
   frontmatter. When that combined signal is **below 0.5%** (and no
   frontmatter change), treat the miss as low-risk: reuse the cached purity
   verdict anyway (no Claude call, no advisory) rather than falling through to
   a real call. When **at or above** the threshold (or frontmatter changed),
   surface a `completeness-audit` advisory line (`purity recommended for step
   N — changed M% of Implementation/Tests since last check`, or `— frontmatter
   changed`) instead of auto-triggering Claude — matching #144's explicit ask
   to keep the audit path itself non-Claude for this decision. This only
   applies in the `completeness-audit` path
   (`_collect_purity_split_findings`); `detail.py`'s own authoring-time
   convergence loop keeps calling Claude for real on every genuine miss, since
   that loop's whole job is to actually validate the freshly-authored content,
   not economize on it.
   - Storing the previous content needed for this diff (not just its hash)
     is a consequence of decision 1's key shape: the cache entry must retain
     enough of the previous detail body (at minimum, its `## Implementation` +
     `## Tests` section text) to diff against on a miss, not only the hash —
     a hash alone can detect *that* something changed but not *how much*.

## Seams to reuse (verified at HEAD)

- `plan_tool/fingerprint.py` — `compute_detail_bundle_fingerprint` (the
  detail-file half of the cache key), `compute_code_fingerprint`'s hashing
  approach for the declared-files half (reuse the pattern, not necessarily
  the function verbatim, since that one is scoped to the *whole plan's*
  watched surface, not one step's `files:`).
- `plan_tool/drift_detection.py:compute_content_hash` — the streamed
  SHA-256 primitive both fingerprint functions already build on.
- `plan_tool/detail.py:collect_detail_quality_findings` (line ~1380),
  `render_detail_quality_prompt` (line ~932) — the function this plan wraps,
  not replaces; its deterministic-grounding portion
  (`collect_step_grounding_findings`) stays outside the cache (decision 2).
- `plan_tool/detail.py:3524` and `:3982` — the two intra-`detail` call sites
  to route through the new cache-check helper.
- `plan_tool/cli/completeness_phases.py:_collect_purity_split_findings`
  (line ~498) — the completeness-audit call site; also where #144's
  magnitude-threshold advisory (decision 6) surfaces as an additional
  advisory finding when a miss is above threshold.
- `plan_tool/granularity.py:GRANULARITY_SPLIT_SOURCE` — the source literal
  identifying a MIXED-STEP purity finding, used to filter the cached/fresh
  findings the same way `_collect_purity_split_findings` already does.
- `DATA_CONTRACT.md` — needs a new entry for the persisted cache-file shape
  (decision 3).

## Scope of work (indicative — let create decompose)

1. The combined cache-key computation (detail-file hash + declared-files
   fingerprint), reusing `fingerprint.py`'s primitives (decisions 1, 5).
2. The cache persistence format + read/write helpers under
   `.plan-tool/purity-cache/<slug>.json` (decision 3), plus the
   `DATA_CONTRACT.md` entry.
3. The shared cache-check helper wrapping `collect_detail_quality_findings`'s
   Claude-judged portion (decisions 2, 4), wired into both `detail.py` call
   sites and `_collect_purity_split_findings`.
4. #144's magnitude-threshold miss-handling: the section-scoped diff ratio +
   frontmatter-change OR, and the advisory-line surfacing in the
   `completeness-audit` path only (decision 6).
5. Tests: a byte-identical step's second purity check makes no Claude call
   (cache hit); a step whose declared files changed underneath an unchanged
   detail body still re-checks (proves the key isn't detail-file-only); a
   below-threshold miss reuses the cached verdict with no Claude call and no
   advisory; an at/above-threshold miss (or a frontmatter change) surfaces the
   advisory without calling Claude in the audit path; `detail.py`'s own loop
   still calls Claude for real on every genuine miss regardless of magnitude.
6. Docs/status step: mark BACKLOG #144 and #145 shipped/removed per the
   file's own convention.

## Non-goals / out of scope

- Redesigning `render_detail_quality_prompt`'s inputs — this plan caches
  around the existing prompt contract, it doesn't change what the prompt reads.
- Including lessons-file content in the cache key (decision 5) — an accepted,
  documented staleness window, not a gap to close here.
- Any change to `detail.py`'s own authoring-time behavior on a genuine miss —
  it always calls Claude for real; only the `completeness-audit` path gets
  #144's below-threshold short-circuit.
- BACKLOG #133 (speeding up the purity call itself) and #103/#115 (related
  purity-pass observability items) — this plan is about not re-paying the
  cost on unchanged content, not about making a genuine call faster.

## Acceptance criteria (plan-level)

- A step whose detail content **and** declared-files content are both
  byte-identical to what was last purity-checked incurs **no Claude call** on
  a subsequent `detail.py` or `completeness-audit` invocation — the cached
  verdict (present or absent finding) is reused.
- A step whose declared `files:` content changed, even with an unchanged
  detail body, is **not** served a stale cached verdict — the combined key
  (decision 1) forces a fresh check.
- In the `completeness-audit` path, a miss whose Implementation+Tests
  section-diff ratio is below 0.5% (per BACKLOG #144, and no
  files:/change_type:/depends_on: change) reuses the cached verdict with
  **no Claude call and no advisory**; a miss at or above that threshold (or
  with a frontmatter change) surfaces an advisory line **without** calling
  Claude.
- `detail.py`'s own authoring-time convergence loop is unaffected by #144's
  threshold — every genuine miss there still calls Claude for real.
- The cache is a new persisted file under `.plan-tool/`, documented in
  `DATA_CONTRACT.md`.
- `BACKLOG.md`'s #144 and #145 entries are marked shipped/removed once the
  fix lands.
