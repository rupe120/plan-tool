> **Auto-archived**: this plan was swept on 2026-06-24 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Define `CarriedFinding` record + deterministic assembly in `audit_plan_until_stable`

## Summary

Add a small, frozen `CarriedFinding` record and a pure `assemble_carried_findings` function in `plan_tool/review.py`, plus a `carried_resolution_from_annotations` adapter in `plan_tool/review_persistence.py`. The record widens the audit loop's carry-forward from `(anchor, title)` pairs to anchor + title + severity + a length-capped body excerpt + a resolution (applied/blocked/skipped/open + reason). `assemble_carried_findings` turns the `by_id` accumulator in `review.audit_plan_until_stable` into a stably-ordered `list[CarriedFinding]` (sorted by severity, then anchor) and becomes the single source the existing `known_anchors` slug-reuse list is derived from — so the slug-reuse dedup behavior is unchanged. On green: the assembly is deterministic and unit-pinned, and the audit loop still feeds the same `(anchor, title)` slug set into later passes.

## Table of Contents

- [Why](#why) — what the identity-only carry-forward can't express today
- [Files (creates vs edits)](#files-creates-vs-edits) — the two source edits plus tests
- [Implementation](#implementation) — the record, the assembly, the adapter, and the loop rewiring
- [Tests](#tests) — pure-function assembly/ordering/excerpt tests + adapter tests
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — dataclasses + sorting docs
- [Deferred](#deferred) — what steps 2–4 own

## Why

`review.audit_plan_until_stable` accumulates each pass's findings in `by_id: dict[str, Recommendation]` and feeds later passes only `known_anchors=[(r.anchor, r.title) for r in by_id.values() if r.anchor]` (the `check_plan_audit` call inside the loop). That `(slug, title)` list exists purely so Claude re-uses an established slug and the union-by-id merge collapses rephrasings — a later pass cannot see a finding's severity, its body, or whether a prior apply already handled or blocked it. This step defines the richer in-memory record and the deterministic assembly that produce it, without changing what the prompt currently emits. It is the foundation the next three steps build on: step 2 renders the widened record into `prompts/plan-audit.md`, and steps 3–4 thread the resolved-finding view into `apply_finding`.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/review.py` — add the `CarriedFinding` frozen dataclass beside `Recommendation`, the `CARRIED_RESOLUTION_*` string constants, the `_CARRIED_BODY_EXCERPT_CHARS` cap, the `_carried_severity_rank` helper, and the `assemble_carried_findings` function; rewire `audit_plan_until_stable` to derive `known_anchors` from the assembled list.
  - `plan_tool/review_persistence.py` — add `carried_resolution_from_annotations`, the one place that maps the saved `Annotation` vocabulary into the carry-forward resolution vocabulary.
  - `tests/test_review.py` — unit tests for the record, the assembly ordering/excerpt/determinism, and the unchanged slug-reuse derivation.

## Implementation

### `plan_tool/review.py`

- **Add resolution vocabulary constants** near the `Recommendation` dataclass, single-sourced so steps 2–4 key on them instead of bare strings:
  - `CARRIED_RESOLUTION_OPEN = "open"` — surfaced but not yet acted on (the default during the audit-only loop).
  - `CARRIED_RESOLUTION_APPLIED = "applied"` — a prior apply landed.
  - `CARRIED_RESOLUTION_BLOCKED = "blocked"` — a prior apply refused (BLOCKED / BLOCKED-STRUCTURAL verdict). Defined now; populated only by the live apply path wired in steps 3–4, not derivable from a saved `Annotation` at HEAD.
  - `CARRIED_RESOLUTION_SKIPPED = "skipped"` — declined or safety-skipped.
- **Add `_CARRIED_BODY_EXCERPT_CHARS = 280`** — the per-finding body cap (roughly 2–3 sentences). This is the per-finding cap only; choosing/truncating the whole rendered *set* is step 2's size cap (`prompts/plan-audit.md`).
- **Add the `CarriedFinding` frozen dataclass** (`@dataclass(frozen=True)`), mirroring `Recommendation`'s posture of holding plain strings (no `Plan`/`Step` references), so it is cheap to construct and compare:
  - `anchor: Optional[str]` — mirrors `Recommendation.anchor` exactly: the `[anchor-slug]` when Claude honored the slug contract, `None` for deterministic/sluggless findings. Do **not** substitute the id here — keeping `None` is what lets the slug-reuse derivation stay the same set as today.
  - `title: str`, `severity: str` — copied from the source `Recommendation`.
  - `body_excerpt: str` — `Recommendation.body` carried whole when within `_CARRIED_BODY_EXCERPT_CHARS`; when longer, trimmed to `_CARRIED_BODY_EXCERPT_CHARS - 1` chars plus a trailing `…`, so the total length stays at most `_CARRIED_BODY_EXCERPT_CHARS`. The `…` appears only when truncation actually dropped characters.
  - `resolution: str = CARRIED_RESOLUTION_OPEN`, `resolution_reason: str = ""`.
- **Add `_carried_severity_rank(severity: str) -> int`** — reuse the existing `_SEVERITY_BANNER_ORDER` tuple (`("critical", "high", "medium", "nit", "info")`) as the ordering source rather than minting a second severity scale. Lowercase the input before the index lookup, and fall back to a rank past the end (`len(_SEVERITY_BANNER_ORDER)`) for any unknown severity so an unexpected level sorts last instead of raising. (Note: `convergence_diagnosis.py:_SEVERITY_RANK` is a *separate, medium+-only* rank for the spinning-region trend; do not reuse it here — it omits `nit`/`info` and would `KeyError`. Consolidating the two severity scales is out of scope.)
- **Add `assemble_carried_findings(recs, *, resolution_by_id=None) -> list[CarriedFinding]`** — the deterministic assembly:
  - `recs`: an iterable of `Recommendation` (the loop passes `by_id.values()`).
  - `resolution_by_id`: an optional `Mapping[str, tuple[str, str]]` keyed by `Recommendation.id`, each value `(resolution, reason)`. Default `None` → every finding is `open`/`""`. **Take plain tuples, not `Annotation`** — `review.py` must not import `Annotation` (that would cycle: `review_persistence.py` already does `from plan_tool.review import Recommendation`). The translation from `Annotation` lives in `review_persistence.py` (below). Add `Mapping` to `review.py`'s `from typing import …` line (currently `Callable, Optional, Sequence`) for this hint.
  - For each rec: build the excerpt, read `(resolution, reason)` from `resolution_by_id.get(rec.id)` when present, else the open default.
  - Sort with a fixed key `key=lambda c: (_carried_severity_rank(c.severity), c.anchor or "", c.title)` — highest-severity first, ties broken by anchor then title. This is the only ordering rule; it never depends on dict iteration order or input order.
- **Rewire `audit_plan_until_stable`** so the assembly is the single source of carry-forward truth:
  - Inside the pass loop, before the `check_plan_audit` call, build `carried = assemble_carried_findings(by_id.values())` (no `resolution_by_id` — apply has not run during the audit loop, so every finding is `open`).
  - Replace the inline `known_anchors=[(r.anchor, r.title) for r in by_id.values() if r.anchor]` with a derivation from `carried`: `known_anchors=[(c.anchor, c.title) for c in carried if c.anchor]`.
  - This is behavior-preserving for dedup: the same `(anchor, title)` *set* of slugged findings reaches `_format_known_findings_block`. The only change is order — insertion order becomes (severity, anchor) order — which is deterministic and does not affect slug-reuse correctness (dedup keys on the slug identity, not list position). No test pins the loop's `known_anchors` order (`test_prompt_lists_known_anchors_for_slug_reuse` passes `known_anchors` to `render_plan_audit_prompt` directly).
  - Leave `_format_known_findings_block`, `render_plan_audit_prompt`, `check_plan_audit`, and `prompts/plan-audit.md` untouched — widening the rendered block is step 2.

### `plan_tool/review_persistence.py`

- **Add `carried_resolution_from_annotations(annotations: dict[str, Annotation]) -> dict[str, tuple[str, str]]`** — the single place that knows the `Annotation` → carry-forward-resolution mapping. This is why the module is in scope: it owns `Annotation`, it already imports `review`, so it can import the `CARRIED_RESOLUTION_*` constants from `review` (no cycle) and emit the plain `(resolution, reason)` tuples `assemble_carried_findings` consumes.
  - `status == "applied"` → `(CARRIED_RESOLUTION_APPLIED, "")`.
  - `status == "skip"` and `halt_reason == "drift"` → `(CARRIED_RESOLUTION_SKIPPED, "drift")` — a safety skip, no choice made.
  - `status == "skip"` otherwise → `(CARRIED_RESOLUTION_SKIPPED, ann.halt_reason)` — a deliberate decline.
  - `status == "open"` (and any unrecognized status) → `(CARRIED_RESOLUTION_OPEN, "")`.
  - Return a dict keyed by the same recommendation id the `annotations` dict is keyed by (`Recommendation.id`; see `review_walk.py` writing `saved.annotations[rec.id] = annotation`).
  - **Do not emit `CARRIED_RESOLUTION_BLOCKED`** — the `BLOCKED` / `BLOCKED-STRUCTURAL` apply verdict (parsed by `launcher.py:parse_apply_verdict`, then consumed/dispatched in `cli/review_actions.py:_dispatch_structural_escalation`) is not persisted into `Annotation` at HEAD. `blocked` is reserved for the live apply path threaded in steps 3–4; this adapter maps only what a saved review actually records.
- **Import note:** add `CarriedFinding` is not needed here (the adapter returns plain tuples, not records); import only the `CARRIED_RESOLUTION_*` constants from `plan_tool.review`.

#### Foundational logic and shared call sites

- **Core rule added:** "turn accumulated `Recommendation`s into a stably-ordered, length-bounded carry-forward set." The only existing carry-forward in the app is the inline `known_anchors` comprehension in `audit_plan_until_stable` — this step subsumes it. No other module builds a parallel carry-forward set today.
- **Resolution-vocabulary translation** is a single source by design (`carried_resolution_from_annotations`). Do not re-spell the `applied`/`skipped`/`open` mapping at the step-4 call site — call this adapter there.
- **Consolidating the two severity scales** (`review._SEVERITY_BANNER_ORDER` vs `convergence_diagnosis._SEVERITY_RANK`) is a behavior-preserving cross-module refactor `detail` cannot mint — left to `## Deferred`, not pulled into this step's set of files.

## Tests

All assembly tests construct `Recommendation` objects directly (no `tmp_path`, no invoker, no integration marker) — `assemble_carried_findings` is a pure function. In `tests/test_review.py`:

- `test_assemble_carried_findings_basic` — one `CarriedFinding` per input rec, carrying the source severity, title, and anchor.
- `test_carried_body_excerpt_capped` — a body longer than `_CARRIED_BODY_EXCERPT_CHARS` is truncated to the cap and ends with `…`; a short body is carried whole with no `…`.
- `test_carried_findings_sorted_by_severity_then_anchor` — mixed severities/anchors return critical → high → medium → nit → info, ties broken by anchor then title.
- `test_assemble_carried_findings_is_deterministic` — two calls on the same input return equal lists in the same order (the determinism property a sorter most silently regresses on).
- `test_carried_resolution_defaults_open` — with `resolution_by_id=None`, every record is `CARRIED_RESOLUTION_OPEN` with empty reason.
- `test_carried_resolution_from_map` — a supplied `resolution_by_id` keyed by `rec.id` sets `resolution`/`resolution_reason`; an id absent from the map falls back to open.
- `test_carried_anchor_none_for_sluggless` — a `Recommendation` with `anchor=None` yields `CarriedFinding.anchor is None` and still sorts without raising.
- `test_unknown_severity_sorts_last` — a record with an off-vocabulary severity sorts after every known level rather than raising.

Adapter tests belong in `tests/test_review_persistence.py` (mirrors the module under test) — **a genuinely required test-file addition beyond the declared `tests/test_review.py`**, because the adapter lives in `review_persistence.py` and the project convention is `plan_tool/X.py` → `tests/test_X.py`:

- `test_carried_resolution_applied` — `Annotation(status="applied")` → `("applied", "")`.
- `test_carried_resolution_skip_drift` — `Annotation(status="skip", halt_reason="drift")` → `("skipped", "drift")`.
- `test_carried_resolution_skip_decline` — `Annotation(status="skip")` → `("skipped", "")`.
- `test_carried_resolution_open` — `Annotation(status="open")` → `("open", "")`.
- `test_carried_resolution_keys_by_rec_id` — the returned dict keys match the `annotations` dict keys.

Loop-level regression (drives `audit_plan_until_stable` with an injected fake invoker — add it as an unmarked unit test in (or beside) `TestAuditPlanUntilStable`, matching that sibling class's established pattern; the autouse no-backend gate stays satisfied because the invoker is injected):

- `test_audit_loop_slug_reuse_set_unchanged` — across two passes where the second re-finds a concept under a reworded title, assert on the **second pass's captured prompt**: `_sampling_invoker.calls[1]`'s prompt still carries the first pass's `[anchor-slug]` slug-reuse block (the `_format_known_findings_block` output) after rewiring `known_anchors` to derive from `assemble_carried_findings`. Asserting on the captured prompt is required because dedup keys on `rec.id` parsed from the fake invoker's response (`_parse_plan_audit_findings` → `by_id[rec.id]`), independent of `known_anchors` — so a final-deduped-rec-set assertion is tautological and passes even if the `assemble_carried_findings`-derived `known_anchors` breaks.

### Test-creation order (feature step)

This is a **feature** step — new behavior. Add each test above **with** the implementation it covers (record + cap → excerpt test; sort key → ordering/determinism tests; adapter → resolution tests; loop rewiring → slug-reuse regression). Green-before-done gate: every new test must pass and the existing `tests/test_review.py` suite must stay green before the step is considered finished.

## Acceptance criteria

- `assemble_carried_findings` returns a `list[CarriedFinding]` sorted by `(severity rank, anchor, title)` — `_carried_severity_rank` puts `critical` first and `info` last, and an unknown severity sorts last without raising.
- A `CarriedFinding.body_excerpt` is at most `_CARRIED_BODY_EXCERPT_CHARS` characters and ends with `…` exactly when the source body was longer.
- With `resolution_by_id=None`, every `CarriedFinding.resolution == "open"` and `resolution_reason == ""`; a supplied map sets them per `Recommendation.id`.
- `carried_resolution_from_annotations` maps `applied`→`applied`, `skip`+`drift`→`skipped`/`"drift"`, `skip`→`skipped`, `open`→`open`, and never emits `blocked`.
- `audit_plan_until_stable` derives `known_anchors` from `assemble_carried_findings(by_id.values())`; the slugged `(anchor, title)` set fed to later passes is unchanged and rephrased-duplicate dedup still collapses (regression test passes).
- Two `assemble_carried_findings` calls on identical input return equal lists in identical order.
- `prompts/plan-audit.md`, `_format_known_findings_block`, and `check_plan_audit` are unchanged in this step.

## References

- [dataclasses — Python 3 documentation](https://docs.python.org/3/library/dataclasses.html) — `@dataclass(frozen=True)` and default-field semantics for the new `CarriedFinding` record beside `Recommendation`/`Annotation`.
- [Sorting Techniques — Python 3 documentation](https://docs.python.org/3/howto/sorting.html) — `sorted()` key functions and stability, the basis for the fixed `(severity, anchor, title)` sort that keeps the carried set order deterministic.

## Deferred

- Rendering the widened `CarriedFinding` into `prompts/plan-audit.md` (a sibling renderer beside `_format_known_findings_block`, plus the block size cap) — step 2.
- The `carried_findings` kwarg on `apply_finding` and its `prompts/apply-finding.md` rendering — step 3.
- Wiring the accumulated set (and `carried_resolution_from_annotations`) from the convergence loop into both apply call sites, where `CARRIED_RESOLUTION_BLOCKED` is populated from the live apply verdict — step 4.
- Consolidating `review._SEVERITY_BANNER_ORDER` and `convergence_diagnosis._SEVERITY_RANK` into one shared severity scale — a behavior-preserving cross-module refactor for `reconcile`, not this step.
- A persisted cross-run carried-finding store and any `--json` surface — out of scope per the plan (within-run loop memory only).
- A `DATA_CONTRACT.md` entry — `CarriedFinding` is an in-memory, within-run record, never serialized, so the drift-guarded persisted-schema contract is unaffected.
