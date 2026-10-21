> **Replaced**: this file has been superseded by `docs/implementation-plans/2-purity-findings-cache.md`.
> Preserved here for history; do not edit.

## Overview

Adds a per-step cache for the expensive MIXED-STEP purity/quality judgment so a step whose detail content and declared-files content are unchanged incurs no Claude call on a subsequent `detail` or `completeness-audit` run. The cache is a new persisted file under `.plan-tool/purity-cache/<slug>.json`, keyed by step id on a combined fingerprint (detail-file content hash + a fingerprint of the step's declared `files:` at their current content). A single shared cache-check helper wraps the Claude-judged portion of `plan_tool/detail.py:collect_detail_quality_findings`, and all three call sites — `detail.py`'s two intra-authoring sites and `completeness_phases._collect_purity_split_findings` — route through it so whichever runs first pays the cost once. It also folds in BACKLOG #144's resolved magnitude-threshold decision: on a cache miss in the `completeness-audit` path only, a below-0.5% Implementation/Tests section diff (with no frontmatter change) reuses the cached verdict, while an at/above-threshold miss surfaces a non-Claude advisory line.

## Problem statement

The per-step MIXED-STEP purity judgment (`plan_tool/detail.py:collect_detail_quality_findings`, prompt at `plan_tool/prompts/detail-quality.md`) is expensive — BACKLOG #133 measured ~130-255s per step (~130-150KB prompts) — and is invoked from two independent call sites with no cache between them:

1. `plan_tool/detail.py`'s own post-authoring per-step convergence loop (the initial scan around `detail.py:3524` and the loop's re-scan around `detail.py:3982`) — the "detail's post-detail completeness sweep" BACKLOG #115 documents.
2. `plan_tool/cli/completeness_phases.py:_collect_purity_split_findings` (around line 498), called whenever `completeness-audit` runs with purity on (`run_purity=True`, gated by the shipped `--no-purity` flag) — a separate process, possibly run hours or days after `detail` last validated the same step.

A step whose detail content is byte-identical to what `detail` already validated still pays a full Claude call the next time a standalone `completeness-audit` runs on it — pure waste. Because `render_detail_quality_prompt` (`plan_tool/detail.py:932`) also folds in the current on-disk contents of the step's declared `files:` (`files_contents_block` via `_format_files_contents_block`), a naive cache keyed only on the detail file's hash is unsound: a step whose detail prose is byte-identical but whose declared files changed underneath it (a sibling step landed first, or a hand-edit) could legitimately purity-flag differently, and a detail-hash-only cache would silently serve a stale verdict.

## Architecture

**Combined cache key (decision 1).** The key is the detail-file content hash plus a fingerprint of the step's own declared `files:` at their current content. Reuse `plan_tool/fingerprint.py`'s existing primitives rather than inventing new hashing: `compute_detail_bundle_fingerprint(plan, plan_path, repo_root)` already produces a `{step-detail-relpath: sha256}` map (the detail-file half); for the declared-files half, hash each of `step.files` the same way `compute_code_fingerprint` hashes `step.files`/`creates` (via `plan_tool/drift_detection.py:compute_content_hash`) and fold the per-file digests into one combined key (a stable sorted-items digest is likely simplest). Lessons-file content is intentionally excluded from the key (decision 5).

**Cache scope (decision 2).** Cache only the Claude-derived structural/MIXED-STEP purity finding(s) (present or absent) per step — not the full `collect_detail_quality_findings` return. The deterministic grounding findings folded into that return (`collect_step_grounding_findings` — file-check, files-coherence, detail-coverage, detail-body) are cheap and re-run fresh on every call regardless of this cache. On a cache hit, `detail.py`'s own loop and `_collect_purity_split_findings` each still run the cheap deterministic grounding findings fresh and splice in the cached purity verdict instead of calling Claude. Practically, the shared cache-checking helper wraps the *Claude call + parse* portion (rendering the prompt, invoking, and lifting `## Structural findings`), not the deterministic-findings portion.

**Persistence (decision 3).** Persist the cache in a small dedicated file under `.plan-tool/` — not the audit-run sidecar. The audit JSON sidecars under `.plan-tool/runs/<slug>/` are timestamped report history, not a stable lookup target. Use `.plan-tool/purity-cache/<slug>.json`, following the existing `.plan-tool/` tool-state convention (alongside `runs/`, `checkpoints/`), keyed by step id, storing the combined fingerprint key (decision 1) and the cached purity finding(s) — or an explicit "no finding" marker, not just an absent key, so a confirmed-pure step isn't re-checked every time. Needs a `DATA_CONTRACT.md` entry.

**Shared helper wiring (decision 4).** Build one small function — e.g. `plan_tool/detail.py:_cached_purity_findings(plan_path, step, *, repo_root, plan_name, invoker, cache_path, ...) -> list[Recommendation]` — that computes the combined key, checks the cache, calls `collect_detail_quality_findings` only on a miss, and writes the result back. Both `detail.py` call sites (`:3524`, `:3982`) and `_collect_purity_split_findings` call this instead of `collect_detail_quality_findings` directly for the Claude-judged portion. Filter the cached/fresh findings on `plan_tool/granularity.py:GRANULARITY_SPLIT_SOURCE`, the same source literal `_collect_purity_split_findings` already keys on.

**Fold-in of BACKLOG #144 (decision 6).** On a cache miss, before spending a Claude call, compute a magnitude signal — a diff ratio (`difflib.SequenceMatcher`) scoped to the concatenated `## Implementation` + `## Tests` sections of the detail body only (not the whole file), comparing the cached content against the current content — plus an unconditional OR on any change to the step's `files:`/`change_type:`/`depends_on:` frontmatter. Below 0.5% (and no frontmatter change), treat the miss as low-risk and reuse the cached verdict (no Claude call, no advisory). At or above the threshold (or frontmatter changed), surface a `completeness-audit` advisory line (`purity recommended for step N — changed M% of Implementation/Tests since last check`, or `— frontmatter changed`) instead of auto-triggering Claude — keeping the audit path non-Claude for this decision. This applies only in the `completeness-audit` path (`_collect_purity_split_findings`); `detail.py`'s own authoring-time convergence loop keeps calling Claude for real on every genuine miss. Storing the previous content needed for this diff (at minimum the `## Implementation` + `## Tests` section text, not just its hash) is a consequence of decision 1's key shape, since a hash alone detects *that* something changed but not *how much*.

## Out of scope

- Redesigning `render_detail_quality_prompt`'s inputs — this plan caches around the existing prompt contract, it doesn't change what the prompt reads.
- Including lessons-file content in the cache key (decision 5) — an accepted, documented staleness window, not a gap to close here.
- Any change to `detail.py`'s own authoring-time behavior on a genuine miss — it always calls Claude for real; only the `completeness-audit` path gets #144's below-threshold short-circuit.
- BACKLOG #133 (speeding up the purity call itself) and #103/#115 (related purity-pass observability items) — this plan is about not re-paying the cost on unchanged content, not about making a genuine call faster.

## Risks

- Stale verdict if the cache key omits something the purity prompt reads. Mitigation: the combined key (decision 1) includes both the detail-file hash and the declared-`files:` content fingerprint, exactly the inputs beyond the detail bytes that `render_detail_quality_prompt` folds in.
- Lessons-file staleness (decision 5): `render_detail_quality_prompt` folds in `load_lessons(...)`'s current content, so a lessons update could in principle change the purity judgment; lessons content is excluded from the key, so a step's cached verdict can be stale after a lessons update. Severity low — lessons change far less often than code/detail and their effect on the *purity* (not grounding) judgment is marginal. Documented as an accepted staleness window; a future BACKLOG item can revisit if it proves to matter.
- #144's below-threshold short-circuit could reuse a verdict across a small-but-material Implementation/Tests edit. Mitigation: the 0.5% diff is scoped to the Implementation+Tests sections and OR'd with an unconditional frontmatter-change trigger, and it only applies in the audit path — `detail.py`'s authoring loop still validates every genuine miss for real.

## Testing

Follow the project's unit-first convention (`TESTING.md`): default to unit tests exercising one function/class in isolation with the invoker seam overridden so no real backend binary spawns; add `@pytest.mark.integration` only for cross-module wiring driving an orchestrator end-to-end. Required behaviors to cover:
- A step whose detail content is byte-identical to its last purity check makes no Claude call on a second check (cache hit).
- A step whose declared `files:` changed underneath an unchanged detail body still re-checks (proves the key isn't detail-file-only).
- A below-threshold miss in the `completeness-audit` path reuses the cached verdict with no Claude call and no advisory.
- An at/above-threshold miss (or a frontmatter change) in the audit path surfaces the advisory without calling Claude.
- `detail.py`'s own loop still calls Claude for real on every genuine miss regardless of magnitude.
Existing purity/detail-quality and completeness-audit suites must still pass. Mirror new modules to their `tests/test_X.py` per the project convention (e.g. cache-key and persistence helpers under their owning module's test file).

## Acceptance criteria

- A step whose detail content **and** declared-files content are both byte-identical to what was last purity-checked incurs **no Claude call** on a subsequent `detail.py` or `completeness-audit` invocation — the cached verdict (present or absent finding) is reused.
- A step whose declared `files:` content changed, even with an unchanged detail body, is **not** served a stale cached verdict — the combined key (decision 1) forces a fresh check.
- In the `completeness-audit` path, a miss whose Implementation+Tests section-diff ratio is below 0.5% (and no `files:`/`change_type:`/`depends_on:` change) reuses the cached verdict with **no Claude call and no advisory**; a miss at or above that threshold (or with a frontmatter change) surfaces an advisory line **without** calling Claude.
- `detail.py`'s own authoring-time convergence loop is unaffected by #144's threshold — every genuine miss there still calls Claude for real.
- The cache is a new persisted file under `.plan-tool/`, documented in `DATA_CONTRACT.md`.
- `BACKLOG.md`'s #144 and #145 entries are marked shipped/removed once the fix lands.
