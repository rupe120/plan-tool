> **Auto-archived**: this plan was swept on 2026-06-22 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Region model & matching (tiered key, sticky closed-state, per-region trend)

## Summary

This step turns step 1's flat run history into a **per-region trend model**: it groups the findings across a plan's saved report runs into *regions* (the recurring thing the spin signature counts), using a tiered match (step focus → concept-slug anchor → fuzzy title) inside per-`kind` (and per-step, for reconcile) series. It edits only `plan_tool/convergence_diagnosis.py` and `tests/test_convergence_diagnosis.py` — the step declares no `files:`, so this set of files is an explicit, minimal extension of step 1's module. The key design decision is to apply both scoping filters (apply-eligible source + `medium+` severity) **once, here, while building regions**, so step 3's signature logic reads an already-scoped `RegionTrend` and never re-filters. On green, `build_region_trends(history)` returns, per series, a list of `RegionTrend` records carrying each region's sampled runs, per-run open-count trajectory, severity trend, source set, resolved step focus, and a sticky `closed` flag — with no verdict logic yet (that is step 3).

## Table of Contents

- [Why](#why) — what step 1 leaves unbuilt and why region matching is its own step
- [Files (creates vs edits)](#files-creates-vs-edits) — the two-file set and the no-`files:` note
- [Implementation](#implementation) — the region key, tiered matcher, trend record, closed-state, and the two reused primitives
- [Tests](#tests) — unit cases for keying, matching tiers, trend, closed-state, partitioning
- [Acceptance criteria](#acceptance-criteria) — checkable outputs of `build_region_trends`
- [References](#references) — difflib, json, datetime docs for this step's surfaces
- [Deferred](#deferred) — what stays for steps 3/4/5 and the producer-change limits

## Why

Step 1 lands a reader that loads each saved sidecar into a flat normalized model (`ReportHistory` → `RunSnapshot` → `RunFinding`) but does **not** decide which findings across runs are *the same problem re-flagged*. The spin signature (step 3) is defined over **regions that recur without shrinking**, and the fork (step 4) is defined over **which region(s) recur and on what step focus** — both need a stable cross-run identity for a finding that `apply_finding` only patched around. Anchors are Claude-minted and only *encouraged* stable, finding ids are content-addressed (they change the moment the body changes), and audit findings carry `step_id=None` — so there is no single field that is a reliable region identity. This step is the one place that derives that identity once, deterministically, and rolls the matched findings into a per-region trend the later steps consume without re-deriving it.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/convergence_diagnosis.py` — add the region key derivation, the per-series partitioner, the tiered matcher, the `RegionTrend` record, the sticky closed-state rule, and the `build_region_trends` entry point. Add top-level imports of `is_blocking` from `plan_tool/convergence.py` and `APPLY_ELIGIBLE_SOURCES` from `plan_tool/review.py`, plus `difflib`.
  - `tests/test_convergence_diagnosis.py` — add the region-model unit classes (keying, matching tiers, partitioning, trend, closed-state) alongside step 1's reader tests, driven off step 1's committed `tests/fixtures/convergence/sample-report-history.json` plus in-memory `RunSnapshot`/`RunFinding` built in-test.

> **Files note.** Step 2 omits the `files:` key entirely in the plan frontmatter (functionally equivalent to an empty list). It edits step 1's two created files (`plan_tool/convergence_diagnosis.py`, `tests/test_convergence_diagnosis.py`) — the same pair step 4 already declares — and creates nothing new. No file outside that pair is touched.

## Implementation

### Cross-step input contract (depends_on: 1)

This step consumes step 1's model. It reads these fields and nothing else; if step 1 names them differently, align there, not here:

- **`RunSnapshot`** — `kind: str` (`"completeness"` | `"detail-reconcile"` | `"run-reconcile"`), `step_id: int | None` (set only on reconcile kinds), `created_at`, `plan_fingerprint: str`, `code_fingerprint` (may be empty), `annotations: dict[str, Annotation]` (rec-id → `review_persistence.Annotation`), and the run's findings list of `RunFinding`.
- **`RunFinding`** — `id: str`, `source: str`, `severity: str`, `step_id: int | None`, `anchor: str | None`, `title: str`. **Step-1 contract requirement: `RunFinding.id` MUST equal `Recommendation.id`** (the content-addressed rec-id `review_persistence.update_annotation`/`save_review` use as the `annotations{}` key — `review_persistence.py:422`, `saved.annotations[rec_id] = annotation`). Closed-state's `snapshot.annotations.get(finding.id)` lookup fires only under this equality; if step 1 derives the finding id from anything else, the lookup silently always returns `None` (no error) and closed-state never closes. Pin this equality in step 1, not here.
- **`ReportHistory`** — the runs already ordered by `created_at` (tie-broken by filename), oldest→newest, as step 1's reader guarantees.

### `plan_tool/convergence_diagnosis.py` — symbols to add

- **Module constants**
  - `TITLE_SIMILARITY_CUTOFF: float = 0.85` — the `difflib.SequenceMatcher.ratio()` floor for the title tier. Name it; step 3/4 must not re-hardcode `0.85`.
  - `_SEVERITY_RANK: dict[str, int] = {"medium": 1, "high": 2, "critical": 3}` — the only ordering needed (sub-`medium` is filtered out before ranking). No shared severity-order constant exists in `plan_tool/review.py` or `plan_tool/convergence.py` to reuse (confirmed by grep), so this step mints it as the single source for `max_severity`; step 4's render reuses it rather than re-declaring. **Key the lookup on `finding.severity.lower()`**, never the raw value: the keys are lowercase but `is_blocking` lowercases internally, so an uppercase `"MEDIUM"` clears the floor and a raw `_SEVERITY_RANK[finding.severity]` would then `KeyError`. Lowercasing the rank key matches the codebase's defensive severity posture (the `severity.lower() == "info"` guards in `review.py`'s `triage_reason` and its open-deferred filter, plus `is_blocking`) and keeps `max_severity`/`first_severity`/`last_severity` robust to non-lowercase severities.

- **`@dataclass(frozen=True) class RegionTrend`** — one record per recurring region within one series. Fields:
  - `key: tuple[str, str]` — the canonical region key `(series_label, normalized_focus)` (see below).
  - `kind: str` and `step_id: int | None` — the series `kind` and, for reconcile series, the audited `snapshot.step_id`; carried so step 4 can label and so the classifier need not re-walk snapshots.
  - `focus: str` — the resolved `normalized_focus` string.
  - `anchor: str | None` and `title: str` — the **representative** (first-seen) finding's anchor and title, for render and for the title tier's representative compare.
  - `sources: frozenset[str]` — union of `finding.source` over the region's matched findings. Generic `str` set (do **not** import a granularity literal — see Deferred); step 4 reads it for localized-vs-structural shape.
  - `run_indices: tuple[int, ...]` — the **series-local** indices of the runs this region appears in (its *sampled runs*). `len(run_indices)` is the recurrence count step 3's M-of-N reads.
  - `open_counts: tuple[int, ...]` — open `medium+` apply-eligible finding count for this region **per sampled run**, aligned with `run_indices`. This is the trajectory step 3's no-shrinkage rule evaluates over the region's *own* sampled runs (never the two raw endpoints).
  - `max_severity: str`, `first_severity: str`, `last_severity: str` — the severity trend, computed over the same `medium+` findings the counts use; `first`/`last` are the region's earliest and latest sampled run.
  - `closed: bool` — the sticky region-level closed flag (see closed-state).

- **`def _normalized_focus(finding) -> str`** — the keying string, in priority order:
  1. `f"step{finding.step_id}"` when `finding.step_id is not None`;
  2. else `f"step{n}"` when `_step_token(finding.anchor)` parses a number;
  3. else the full concept-slug `finding.anchor` when non-empty;
  4. else `_title_slug(finding.title)` truncated.

- **`def _step_token(anchor: str | None) -> int | None`** — parse a leading step number with `re.compile(r"^step-?(\d+)")` against the anchor (matches `step5-over-pack` and `step-5-…`). Returns the int or `None`. This is the lower-level parse; step 4's classifier-facing `_region_step_focus` (which returns the int focus or `None` for the fork) reuses it — do not duplicate the regex there.

- **`def _title_slug(title: str) -> str`** and **`def _title_ratio(a: str, b: str) -> float`** — normalize a title to a lowercase hyphen slug, and compare two slugs with `difflib.SequenceMatcher(None, a, b).ratio()`. The title tier is fuzzy by design — exact-slug equality would scatter recurrence the moment Claude re-words a title.

- **`def series_key(snapshot) -> tuple[str, ...]`** — the **series partition** key: `(snapshot.kind,)` for `completeness`, `(snapshot.kind, snapshot.step_id)` for the two reconcile kinds. Reconcile sidecars each audit a *single* step, so partitioning on `kind` alone would compare findings across different steps and fabricate recurrence; including `snapshot.step_id` keeps the window comparing audits of the same step. Completeness snapshots carry `step_id=None`, so their series is just `kind`.

- **`def series_label(snapshot) -> str`** — the string form of `series_key` that prefixes a region key: `":".join(str(p) for p in series_key(snapshot))` (e.g. `"completeness"`, `"detail-reconcile:5"`). Derive it from `series_key` only — do not re-spell the `kind`/`step_id` composition — so a series and its regions never disagree on their partition. Every snapshot in one series yields the same `series_label`, so `recurring_regions` computes it once from the series' first snapshot.

- **`def partition_series(history) -> dict[tuple, list[RunSnapshot]]`** — group the ordered runs by `series_key`, preserving each group's chronological order. Use an insertion-ordered dict so output series order is deterministic.

- **`def recurring_regions(snapshots: list[RunSnapshot]) -> list[RegionTrend]`** — the per-series matcher. For one series:
  - **Scope first.** For each run, keep only findings that are both apply-eligible (`finding.source in APPLY_ELIGIBLE_SOURCES`) **and** `medium+` (`is_blocking(finding.severity)`). This single filter excludes advisory `plan-completeness` recs (not in `APPLY_ELIGIBLE_SOURCES`) and sub-`medium` `nit`/`info` from recurrence, no-shrinkage, *and* the trend at once — keeping the three mutually consistent.
  - **Greedy tiered match.** Walk runs oldest→newest, findings in list order. For each finding, test it against each already-seeded region's representative in creation order and join the first that matches; else seed a new region with this finding as representative. `match(candidate, representative)` returns True on the **highest applicable tier**:
    - **Tier 1 — step focus (authoritative):** both resolve a step focus (`finding.step_id` or `_step_token(anchor)`) and the focuses are equal.
    - **Tier 2 — concept-slug anchor (authoritative):** neither resolves a step focus, both have a non-empty anchor, and the anchors are equal. A stable concept-slug anchor must not break the streak just because no `step<N>` token is present.
    - **Tier 3 — title similarity (last resort):** `_title_ratio(_title_slug(candidate.title), _title_slug(representative.title)) >= TITLE_SIMILARITY_CUTOFF`.
    - Tiers 1/2 take precedence over tier 3, so a step-focused finding prefers a step-focused region. Matching is **pairwise against representatives**, not all-pairs clustering — deterministic and reproducible.
  - **Per-region aggregation.** For each region: collect `run_indices` (series-local run index for each run the region appears in — a region may match ≥1 finding in a run; count the run once), `open_counts` (number of matched scoped findings per sampled run), `sources` (union), and the severity trend (`max_severity` via `_SEVERITY_RANK`; `first_severity`/`last_severity` from earliest/latest sampled run). Build the `key` as `(series_label(snapshot), representative_focus)` using the `series_label` helper above (the `":"`-joined `series_key`, e.g. `"detail-reconcile:5"`) so two regions from different series never compare equal.
  - **Closed-state (sticky, region-level).** Set `closed=True` when **any** run in the **whole series** carries, for **any** finding mapped into this region, an annotation with `status == "skip"` **and** `halt_reason == ""` (look up `snapshot.annotations.get(finding.id)`). Rationale and edges:
    - **Only a deliberate decline closes.** `applied` and `open` (and absent) stay unresolved — an `applied`-yet-reappearing finding *is* the spin signature and must keep accumulating recurrence; a genuinely-fixed finding self-suppresses by not reappearing. **Deliberate override of the seed/schema-contract D2 "`applied` closes" rule:** the seed and schema-contract D2 say a finding is closed when `status ∈ {applied, skip}`, but treating `applied` as closed would suppress the exact apply→reappear loop this detector exists to catch (the audit re-finds what `apply_finding` only patched around), so v1 closes on `skip` **only**. This is an intentional, flagged divergence — when the seed/schema-contract are next revised, reconcile them to match.
    - **`halt_reason == "drift"` is NOT closed** — a pre-apply drift halt made no choice, so a region that keeps tripping the drift guard run after run must stay open. **Deliberate narrowing of the seed's "any `skip` closes" rule:** the seed (lines 33, 94) and its acceptance criterion close a region on any `status == "skip"`, but a `skip` carrying `halt_reason == "drift"` is a safety halt where no apply landed and no WONTFIX was chosen, so v1 additionally requires `halt_reason == ""` to close (matching `Annotation`'s deliberate-decline intent). This is an intentional, flagged divergence — when the seed/schema-contract are next revised, reconcile them to match.
    - **Sticky across the whole series.** Because ids/anchors drift, once one run skips a finding mapping to the region, the whole region is closed for the entire series even if it later reappears with a fresh id and no annotation — and even if the skip predates step 3's trailing recurrence window. The operator's WONTFIX is not re-asked every run.

- **`def build_region_trends(history) -> dict[tuple, list[RegionTrend]]`** — the step-2 entry point step 3 calls: `partition_series` → `recurring_regions` per series → return per-series-key region lists (drop empty series). This is the seam between the reader (step 1) and the verdict (step 3); it makes **no** recurrence/shrinkage/verdict decision.

### Reused primitives (single-source, no re-declaration)

- **`medium+` floor** — `from plan_tool.convergence import is_blocking`. `convergence.py` is a stdlib-only acyclic leaf; import at module top (same posture as the other top-level `convergence_diagnosis` imports). Do not re-declare a `{medium,high,critical}` set — this honors step 1's forward deferral of the threshold to this detector.
- **Apply-eligible source filter** — reuse `plan_tool/review.py:APPLY_ELIGIBLE_SOURCES`. `convergence_diagnosis` already imports `review`, so add the name to that import. Filtering on membership (not on `is_apply_eligible`, which takes a `Recommendation`) lets the rule run over step 1's lighter `RunFinding`. The set excludes `plan-completeness`, which is exactly the advisory-source exclusion the plan mandates.
- **`difflib`** — `import difflib` for the title tier.

### Acyclicity

No new cross-package edges beyond `convergence` (leaf), `review` (already imported), `review_persistence` (`Annotation`, already imported by step 1), and stdlib `re`/`difflib`. `convergence_diagnosis.py` stays a leaf below the CLI — no `plan_tool.cli` import.

## Tests

All new cases land in `tests/test_convergence_diagnosis.py`, unit (unmarked), built off step 1's `tests/fixtures/convergence/sample-report-history.json` (the 3-run spinning series) plus in-test `RunSnapshot`/`RunFinding` fixtures for edge cases. Mutate the loaded payload in-memory for variants — do not author new fixture files.

- `test_normalized_focus_prefers_finding_step_id` — `finding.step_id=5` → focus `"step5"` even when the anchor differs.
- `test_normalized_focus_parses_step_token_from_anchor` — `step_id=None`, anchor `step7-over-pack` → focus `"step7"`.
- `test_normalized_focus_falls_back_to_anchor_then_title` — no step focus, concept-slug anchor used; no anchor → truncated title slug.
- `test_step_token_matches_hyphen_and_plain` — `_step_token` parses both `step5-x` and `step-5-x`; returns `None` for `over-packed-step`.
- `test_match_tier1_step_focus_authoritative` — two findings with equal step focus but unrelated titles share one region.
- `test_match_tier2_anchor_equality` — no step token, equal concept-slug anchors → one region; differing anchors → two regions.
- `test_match_tier3_title_similarity_cutoff` — title-slug `ratio()` `>= 0.85` joins; just-below stays separate (assert against `TITLE_SIMILARITY_CUTOFF`).
- `test_match_greedy_against_representative` — a third finding joins the first-seeded matching region, not a later one; order-deterministic.
- `test_partition_series_completeness_by_kind` — completeness runs land in one `(kind,)` series.
- `test_partition_reconcile_by_kind_and_step_id` — two `detail-reconcile` runs with different `step_id` form two series (no fabricated recurrence).
- `test_no_cross_kind_region_match` — same anchor under `completeness` and `detail-reconcile` keys to two regions.
- `test_scope_excludes_plan_completeness_and_sub_medium` — advisory `plan-completeness` and `nit`/`info` findings never seed a region nor inflate `open_counts`.
- `test_region_trend_run_indices_and_open_counts` — a region present in runs 0 and 2 (absent in 1) yields `run_indices=(0,2)` and aligned `open_counts`.
- `test_region_trend_severity_first_last_max` — severity `medium→high` across sampled runs sets `first_severity="medium"`, `last_severity="high"`, `max_severity="high"`.
- `test_closed_state_skip_decline_closes_region` — one run with `status="skip"`, `halt_reason=""` sets `closed=True`.
- `test_closed_state_drift_skip_not_closed` — `status="skip"`, `halt_reason="drift"` leaves `closed=False`.
- `test_closed_state_applied_recurring_stays_open` — `status="applied"` that reappears keeps `closed=False`.
- `test_closed_state_sticky_across_window` — a region skipped once stays `closed=True` when it reappears later with a fresh id and no annotation.
- `test_build_region_trends_spinning_fixture` — on the committed spinning fixture, `build_region_trends` returns a region recurring across all runs with a non-shrinking `open_counts` (the input step 3 needs), and makes no verdict.

### Test-creation order (feature step)

This is a **feature** step — new behavior on step 1's module. Add every test above **with** the implementation in the same change. Green-before-done gate: all new `tests/test_convergence_diagnosis.py` cases (and step 1's existing reader cases) must pass before this step is complete. Run the fast loop `uv run pytest tests/test_convergence_diagnosis.py -q` during development.

## Acceptance criteria

- `build_region_trends(history)` returns a dict keyed by series key; each value is a list of `RegionTrend`, and empty series are dropped.
- A finding with `step_id=5` and a finding whose anchor is `step5-*` land in the **same** region (tier-1 step focus); two findings with equal concept-slug anchors and no step token land in the same region (tier-2); two findings whose title slugs score `>= TITLE_SIMILARITY_CUTOFF` land in the same region (tier-3).
- No region spans two `kind`s; reconcile runs with different `step_id` form separate series.
- A region built only from `plan-completeness` recs or only sub-`medium` findings does not appear (filtered out of recurrence, `open_counts`, and the trend alike).
- `RegionTrend.run_indices` lists exactly the runs the region appears in; `open_counts` aligns with it; `max_severity`/`first_severity`/`last_severity` reflect the medium+ trend.
- `closed=True` exactly when some run carries a `status=="skip"`, `halt_reason==""` annotation for a finding mapped to the region; `closed=False` for `halt_reason=="drift"`, for `applied`, and when no skip is present; the flag is sticky across the whole series.
- `convergence_diagnosis.py` imports no `plan_tool.cli` module and adds no import cycle.

## References

- [difflib — Helpers for computing deltas (Python docs)](https://docs.python.org/3/library/difflib.html) — `SequenceMatcher.ratio()` semantics backing the title-similarity tier and the `0.85` cutoff.
- [re — Regular expression operations (Python docs)](https://docs.python.org/3/library/re.html) — `re.compile`/`match` for the `^step-?(\d+)` anchor step-token parse.
- [json — JSON encoder and decoder (Python docs)](https://docs.python.org/3/library/json.html) — for reading the persisted sidecar fields (`annotations`, `recommendations`) the region model sits on; defensive parsing already lands in step 1.
- [How to use temporary directories and files in tests (pytest docs)](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — `tmp_path` for any hermetic test that materializes a report-history fixture rather than building snapshots in memory.

## Deferred

- **M-of-N recurrence decision, no-shrinkage rule, and the four-state verdict** — step 3 (`Signature & verdict`). This step only *builds* the inputs (`run_indices`, `open_counts`, `closed`); it makes no spinning/converging call.
- **Localized-vs-structural classification and `render_diagnosis` output** — step 4. The classifier-facing `_region_step_focus` (returns the int step focus or `None` for the fork) reuses this step's `_step_token`; render reuses `_SEVERITY_RANK`. Neither is built here.
- **`plan-tool convergence` CLI wiring** — step 5.
- **`granularity-split` consumption** — granularity `smell_recs` are dropped at the producer (`cli/completeness_phases.py:_persist_and_present_report` builds the persisted `sidecar_recs` from `correctness_recs + conceptual_recs` only; `cli/completeness_cmd.py` merely forwards `smell_recs` separately), so no `granularity-split` source reaches the sidecar in v1. `RegionTrend.sources` stays a generic `frozenset[str]` (no `GRANULARITY_SPLIT_SOURCE` import) so the v2 granularity-backed localized path can populate it once the producer change lands (plan `## Deferred`).
- **Closed-state on iterate-only history** — `write_completeness_report`→`save_review` persists **empty** annotations; only the interactive `completeness-apply` walk populates them. So `closed` only ever flips on history that went through an apply-walk; on the mandated `--iterate`-only workflow every region reads open. Persisting iterate disposition as annotations is the producer-change parked in the plan's `## Deferred` — out of scope here.
- **Combining per-series verdicts into one headline** — the worst-of ordering across `kind`s lives with the verdict logic (step 3/4), not the region model.
