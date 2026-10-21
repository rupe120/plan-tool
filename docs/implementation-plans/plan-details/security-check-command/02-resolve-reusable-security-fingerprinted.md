# Step 2 — Add `resolve_reusable_security` + fingerprinted `<ts>-security-<target>.json` persistence

## Summary

Adds two composable functions to `plan_tool/security_audit.py` (created in step 1): `write_security_report(...)` persists a `SecurityAuditResult` as a fingerprinted `<ts>-security-<target>.json` sidecar via `plan_tool/review_persistence.py:save_review(kind=f"security-{target}")` — the target (`plan` vs `code`) is **encoded in the filename suffix** so reuse is scoped by target, structurally, never serving a `target="code"` report to a plan-axis caller (`security --target plan`, step 3) or a plan report to `--target code` — and `resolve_reusable_security(...)` reads the newest sidecar *for the requested target* back and renders a freshness verdict. `resolve_reusable_security` is a member-for-member clone of `plan_tool/completeness_report.py:resolve_reusable_audit` minus the correctness/conceptual axis split — security saves are **single-axis** (one save = one `--target`, one `source`), so it uses a flat single-bucket shape — like `plan_tool/cli/reconcile.py:ReusableReconcile`, but adding a `security_recs` field `ReusableReconcile` lacks — rather than the audit's dual buckets. The load-bearing decision: reuse the existing fingerprint producers (`compute_plan_fingerprint`, `compute_code_fingerprint`) and the `save_review`/`list_saved_reviews`/`load_review` persistence leaf verbatim, and gate code-staleness on `saved.code_fingerprint_present` (not dict truthiness) so a legacy/never-computed save reads stale, never falsely fresh. On green, a save→reload round-trip over a stubbed audit reproduces the same fingerprints, a fresh sidecar verdicts `fresh=True`, and an edited/deleted/new in-scope file surfaces as `drifted_code`. `run_security_audit` is **not** modified — it stays in-memory; the CLI (step 3) owns calling these two functions.

## Table of Contents

- [Why](#why) — why persistence + a reuse resolver land now, before the CLI
- [Files (creates vs edits)](#files-creates-vs-edits) — both edits live in `security_audit.py` + its test file
- [Implementation](#implementation) — the writer, the `ReusableSecurity` dataclass, the target-scoped resolver, and the three-way diff
- [Tests](#tests) — round-trip, fresh/stale, drift, legacy-absent, and id-pin cases
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — fingerprint/persistence grounding
- [Deferred](#deferred) — CLI wiring, resolver consolidation

## Why

Step 1 left `run_security_audit` returning findings **in memory only** — every plan-wide security audit re-spends a Claude call even when neither the plan nor the watched code changed. The completeness and reconcile families already solved this with fingerprint-gated reuse (`resolve_reusable_audit` ↔ `resolve_reusable_reconcile`, the deliberate structural siblings); security needs the parallel resolver so the standalone `security` command's fingerprint-gated reuse short-circuit (step 3's CLI, extended by the step-4 reconcile target and the step-8 `--iterate` loop) can offer "reuse the saved security audit when the plan and code fingerprints still match" instead of re-spending a Claude call. Landing persistence + the resolver as standalone composable functions now (before any CLI wiring) keeps the step inside the `security_audit.py` footprint and lets step 3 be a thin carve over them.

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**
- `plan_tool/security_audit.py` — add `write_security_report(...)` (the `<ts>-security-<target>.json` writer), the `@dataclass ReusableSecurity`, and `resolve_reusable_security(...)` (the target-scoped read/verdict resolver). Add top-imports for the persistence/fingerprint leaves (see Implementation). `run_security_audit` and the step-1 symbols are unchanged.
- `tests/test_security_audit.py` — add the round-trip / fresh / stale / drift / legacy-absent / id-pin unit tests below.

## Implementation

### `plan_tool/security_audit.py`

**Top-imports (leaf-safe — these are the same leaves `plan_tool/completeness_report.py` top-imports, so no cycle).** Step 1 kept `review`/`launcher` lazy because they're heavy; the persistence and fingerprint modules are dependency leaves and may be hoisted:
- `from plan_tool.fingerprint import compute_code_fingerprint`
- `from plan_tool.review_persistence import compute_plan_fingerprint, list_saved_reviews, load_review, save_review, SavedReview`
- `from plan_tool.parser import parse_plan` (step 1 already imports this)
- `from plan_tool.locator import slug_from_filename`
- Keep `Recommendation` under the existing step-1 `TYPE_CHECKING` block; the resolver only *reads* `saved.recommendations` (already-rehydrated `Recommendation`s from `load_review`), so no runtime `review` import is needed.

#### `write_security_report(...)` — the persistence writer

A thin `save_review` delegator. Take the same fingerprint/path inputs as `plan_tool/completeness_report.py:write_completeness_report`, but **diverge from it deliberately**: `write_completeness_report` writes a `<ts>-completeness.md`, returns that markdown path (discarding `save_review`'s return), takes `recommendations` as `Optional`, and has no `step_id`. This function does none of that — it takes `recommendations` as a required `list`, threads `step_id` through, and returns the `.json` path that `save_review` returns. Follow the explicit `return save_review(...)` instruction below rather than copying `write_completeness_report`'s body.

```python
def write_security_report(
    plan_path: Path,
    report_md: str,
    *,
    repo_root: Path,
    recommendations: list["Recommendation"],
    plan_rel_path: str,
    target: str = "plan",
    plan_fingerprint: str = "",
    code_fingerprint: Optional[dict[str, str]] = None,
    step_id: Optional[int] = None,
    now: Optional[datetime] = None,
) -> Path:
```

- **Derive the slug, then delegate to `save_review` with `kind=f"security-{target}"`.** `slug = slug_from_filename(plan_path)` (assert non-`None`, matching `write_completeness_report`), assert `target in ("plan", "code")` (guard against a typo silently minting an unfilterable third bucket), then `return save_review(plan_slug=slug, plan_path=plan_rel_path, repo_root=repo_root, report_md=report_md, recommendations=recommendations, plan_fingerprint=plan_fingerprint, code_fingerprint=code_fingerprint or {}, kind=f"security-{target}", step_id=step_id, now=now)`.
- **`kind=f"security-{target}"` yields `<ts>-security-plan.json` / `<ts>-security-code.json` for free** — `plan_tool/review_persistence.py:_timestamp_filename` embeds any non-`"review"` kind verbatim (`f"{ts}-{kind}.json"`), so **no edit to `plan_tool/review_persistence.py` is required** (the suffix is generic, not a hardcoded enum). This keeps the step inside its two-file footprint. **The target lives in the filename, not just in `Recommendation.source`** — that is the load-bearing scoping decision: a target token derived from `rec.source` would be unreadable for an *empty-recs* sidecar (a clean audit with no findings), and skipping empty sidecars to dodge that would forfeit reuse on the common clean-plan case; encoding the target in the suffix makes the resolver's filter total and keeps clean-audit reuse intact.
- **Caller supplies the target, the fingerprints, and the repo-relative plan path**, exactly as `write_completeness_report` takes `plan_fingerprint`/`code_fingerprint`/`plan_rel_path`. The writer stays filesystem-naming-agnostic; step 3's CLI computes the rel path and the two fingerprints, and passes `target="plan"` or `target="code"` (and, for code, `step_id`). Pass `step_id` through (set for code-target single-step audits, `None` for plan-target).

#### `ReusableSecurity` dataclass — single-axis

Use a flat single-bucket shape — like `plan_tool/cli/reconcile.py:ReusableReconcile`, but with an added `security_recs` field `ReusableReconcile` doesn't carry — **not** `ReusableAudit`'s dual buckets (which split `correctness_recs`/`conceptual_recs`). A security sidecar is one `--target` → one `source` (`"security-plan"` *or* `"security-code"`), so there is no axis to split:

```python
@dataclass
class ReusableSecurity:
    saved: SavedReview          # the loaded sidecar (carries both fingerprints)
    security_recs: list["Recommendation"]  # == saved.recommendations (target lives in each rec.source)
    fresh: bool                 # plan_match and code_match
    plan_match: bool            # saved plan fingerprint non-empty and == current
    code_match: bool            # code fingerprint computed and saved→current diff empty
    drifted_code: list[Path]    # abs-resolved, sorted paths that changed | deleted | landed
```

- **`security_recs` is the full `saved.recommendations` list, unsplit.** A sidecar is single-target by construction (its filename suffix is `-security-plan` or `-security-code`), so every rec in it already shares one `Recommendation.source` (`"security-plan"`/`"security-code"`); there is no axis to split. Scoping reuse to the requested target is done *before* load by the suffix filter (see the resolver), so the caller never has to inspect `rec.source` to reject a cross-target sidecar.

#### `resolve_reusable_security(...)` — the read/verdict resolver

Clone `plan_tool/completeness_report.py:resolve_reusable_audit` exactly, swapping the suffix and dropping the axis split:

```python
def resolve_reusable_security(
    plan_slug: str,
    repo_root: Path,
    *,
    plan_path: Path,
    target: str = "plan",
    step_id: Optional[int] = None,
    review_id: Optional[str] = None,
) -> Optional[ReusableSecurity]:
```

- **`target` scopes the lookup** (`"plan"` or `"code"`; assert membership). It selects which sidecar family the resolver returns — a `target="plan"` call never resolves a `-security-code.json` save and vice versa. This is the fix for the cross-target reuse-poisoning the Architecture warns about: `security --target plan` (step 3) calls `target="plan"`, `security --target code` (step 3) calls `target="code"`, and the two can never serve each other's reports.
- **`step_id` additionally scopes the `target="code"` lookup.** The `-security-code.json` suffix encodes only the target, not the step, so two steps' code audits write same-suffix sidecars; a target-suffix-only filter would serve one step's saved code audit to a different step's caller. For `target="code"`, after the suffix filter, keep only candidates whose `saved.step_id == step_id` (mirroring the reconcile family's per-step `plan_tool/cli/reconcile.py:_find_saved_for_step`, **not** the whole-plan `resolve_reusable_audit` newest-wins shape it is otherwise cloned from); a `target="code"` call therefore requires a non-`None` `step_id` (assert it). For `target="plan"`, `step_id` is unused (plan-target saves carry `step_id=None`).
- **Locate by target-scoped literal suffix, like completeness — not via `_RECONCILE_KINDS`.** Filter `list_saved_reviews(plan_slug, repo_root, plan_path=plan_path)` (newest-first) to `[p for p in ... if p.name.endswith(f"-security-{target}.json")]`, then for `target="code"` further restrict to the matching `step_id` (above). The `-security-<target>` suffix is unique per target, so it matches completeness's `endswith("-completeness.json")` approach; it does **not** need reconcile's `name_excludes` machinery (which exists only because `-run-reconcile`/`-detail-reconcile` overlap as substrings). The suffix is also disjoint from step 4's `-security-reconcile.json` (`endswith("-security-plan.json")` cannot match a `-reconcile` filename), so the three security sidecar families never collide.
- **Honor `review_id` by stem** exactly as `resolve_reusable_audit` does: `wanted = {review_id, f"{review_id}-security-{target}"}`, keep candidates whose `.stem` is in `wanted`. Return `None` when no candidate remains.
- **Load the newest candidate** with `load_review(candidates[0])`.
- **Plan-fingerprint match:** `current_plan_fp = compute_plan_fingerprint(plan_path)`; `plan_match = bool(saved.plan_fingerprint) and saved.plan_fingerprint == current_plan_fp`.
- **Code-fingerprint match — gate on `code_fingerprint_present`, the three-way diff:**
  - If `not saved.code_fingerprint_present` → `code_match = False`, `drifted_rel = set()` (legacy/never-computed reads stale — the load-bearing correctness gate; a `{}`-defaulted dict would otherwise look like "no drift").
  - Else `plan = parse_plan(plan_path)`; `current_code_fp = compute_code_fingerprint(plan, plan_path, repo_root)`; then `changed = {rel for rel, d in saved.code_fingerprint.items() if rel in current_code_fp and current_code_fp[rel] != d}`, `deleted = set(saved.code_fingerprint) - set(current_code_fp)`, `new = set(current_code_fp) - set(saved.code_fingerprint)`, `drifted_rel = changed | deleted | new`, `code_match = not drifted_rel`.
- **Resolve drifted paths to absolutes** so they align key-for-key with `plan_tool/scope_guard.py:build_file_to_step_map` (which the CLI's drift-attribution printer keys on): `root = repo_root.resolve(); drifted_code = sorted((root / rel).resolve() for rel in drifted_rel)`.
- **Return** `ReusableSecurity(saved=saved, security_recs=saved.recommendations, fresh=plan_match and code_match, plan_match=plan_match, code_match=code_match, drifted_code=drifted_code)`.

**Error posture — let parse errors propagate (do not swallow).** `resolve_reusable_security` is a deterministic resolver over a caller-supplied, known-good plan path; `parse_plan(plan_path)` raising `ParseError`/`ValidationError` should surface, not be swallowed into a misleading "no reusable result". This matches `resolve_reusable_audit` / `resolve_reusable_reconcile` (strict resolvers) and is the opposite posture from the best-effort *writer* seams. Any interactive caller that must not crash (step 3's reuse prompt) wraps the call locally — that wrapping is the call site's property, not this resolver's.

**Foundational-logic shared locations** (cited here, not under a new heading):
- `plan_tool/completeness_report.py:resolve_reusable_audit` + `plan_tool/cli/reconcile.py:resolve_reusable_reconcile` — the two existing fingerprint-reuse resolvers `resolve_reusable_security` joins as a third structural sibling. They live in different import tiers and stay **separate producers**; a `kind`-parametrized merge of all three (plus a shared `changed|deleted|new` `diff_fingerprint_maps` helper) is a refactor `detail` cannot mint → Deferred.
- `plan_tool/review_persistence.py:compute_plan_fingerprint` and `plan_tool/fingerprint.py:compute_code_fingerprint` — the single source for both digests. **Reuse verbatim**; do not re-author hashing. `compute_code_fingerprint`'s watched surface (`plan_tool/scope_guard.py:compute_drift_watched_paths`) already excludes the plan markdown and per-step detail files, so it captures only the code the audit reasons about.
- `plan_tool/review_persistence.py:save_review` / `_timestamp_filename` — the single persistence funnel; `kind="security-plan"` / `kind="security-code"` are new values flowing through the existing generic suffix logic, requiring no change to that module.

## Tests

All in `tests/test_security_audit.py`, extending step 1's file. Unmarked unit tests; drive `write_security_report` / `resolve_reusable_security` directly with `Recommendation`s built in-test (or via the step-1 stubbed-invoker `run_security_audit` to produce a real `SecurityAuditResult`). No `main()`, no `allow_real_claude` marker — the conftest real-backend gate staying green is itself an assertion.

### Test-creation order (feature step)

This is a **feature** step — write these alongside the implementation; every one must be green under `uv run pytest tests/test_security_audit.py -q` before the step is done.

- `test_write_security_report_writes_target_suffix` — `write_security_report(..., target="plan")` returns a path whose name ends `-security-plan.json` and whose loaded `kind == "security-plan"`; `target="code"` ends `-security-code.json` / `kind == "security-code"`.
- `test_write_security_report_rejects_unknown_target` — `target="bogus"` raises (the `assert target in ("plan", "code")` guard), so a typo can never mint an unfilterable bucket.
- `test_write_security_report_persists_fingerprints` — pass a `plan_fingerprint` + `code_fingerprint` map; `load_review(path)` round-trips both, and `code_fingerprint_present is True`.
- `test_resolve_reusable_security_fresh_round_trip` — write a sidecar with fingerprints computed from disk via `compute_plan_fingerprint`/`compute_code_fingerprint`, then resolve: `fresh is True`, `plan_match`, `code_match`, `drifted_code == []`. This is the load-bearing save→reload boundary — fingerprints computed at write time must reproduce at resolve time over an **unpatched** persistence path.
- `test_resolve_reusable_security_stale_by_plan` — edit the plan body after saving; `plan_match is False`, `fresh is False`, `drifted_code == []`.
- `test_resolve_reusable_security_stale_by_code_edit` — edit an in-scope code file after saving; `code_match is False`, `fresh is False`, `drifted_code == [edited_abs_path]`.
- `test_resolve_reusable_security_drift_on_deletion` — delete an in-scope file; it appears in `drifted_code` (the `deleted` branch).
- `test_resolve_reusable_security_drift_on_new_file` — a watched file lands after capture; it appears in `drifted_code` (the `new` branch).
- `test_resolve_reusable_security_legacy_absent_reads_stale` — seed a sidecar with `code_fingerprint_present=False` (legacy save); `code_match is False` even though the dict is empty (gates on the marker, not truthiness).
- `test_resolve_reusable_security_empty_code_surface_stays_fresh` — `code_fingerprint={}` with `code_fingerprint_present=True` (docs-only / pre-impl plan); `code_match is True` on plan-match alone.
- `test_resolve_reusable_security_picks_newest` — two `-security-plan.json` saves at distinct timestamps; resolver (`target="plan"`) loads the newer.
- `test_resolve_reusable_security_pinned_by_id` — `review_id="<stem>"` (and the `"<stem>-security-plan"` form) selects exactly that sidecar; a non-matching id yields `None`.
- `test_resolve_reusable_security_none_when_no_sidecar` — no `-security-plan.json` present → `None` (and a stray `-completeness.json` is ignored by the suffix filter).
- `test_resolve_reusable_security_scopes_by_target` — **the cross-target poisoning guard.** Save one `-security-code.json` and resolve with `target="plan"` → `None` (the code sidecar is never served to a plan caller); save one `-security-plan.json` and resolve with `target="code"` → `None`. With *both* present, each `target` resolves its own. Cover the empty-recs case explicitly: a clean (`recommendations=[]`) `-security-code.json` is still **not** returned for `target="plan"` — the filter is total because the target lives in the filename, not in any `rec.source`.
- `test_resolve_reusable_security_scopes_code_target_by_step` — write two `-security-code.json` sidecars for distinct `step_id`s; `resolve_reusable_security(target="code", step_id=1)` returns the step-1 save and never the step-2 save (and vice versa), even when the other step's sidecar is newer; a `target="code"` call with `step_id=None` raises.
- `test_resolve_reusable_security_ignores_security_reconcile_sidecar` — a step-4 `-security-reconcile.json` save is **not** returned for `target="plan"` or `target="code"` (suffix disjointness across the three security families).
- `test_resolve_reusable_security_propagates_parse_error` — point at an unparseable plan; `resolve_reusable_security` raises (does **not** swallow into `None`).

**Brittleness guards (apply the captured lessons):**
- **Never assert on sidecar file *count* across two same-second saves** — a second-precision timestamp filename collides at the identical stem. Capture any needed stem **before** the second save; assert on content/stem, not count.
- **Assert reuse-was-skipped via the call *delta*** if a test counts Claude invocations: snapshot the stub's call list length immediately before the operation and compare after (reuse → delta 0), never an absolute count.

## Acceptance criteria

- `write_security_report(..., target="plan")` writes a file named `<YYYYMMDD-HHMMSS>-security-plan.json` whose `load_review` round-trips `kind == "security-plan"`, the `recommendations`, `plan_fingerprint`, `code_fingerprint`, and `code_fingerprint_present`; `target="code"` writes `-security-code.json` / `kind == "security-code"`; an unknown `target` raises.
- `resolve_reusable_security(..., target="plan")` over a sidecar saved with matching plan+code fingerprints returns `ReusableSecurity(fresh=True, plan_match=True, code_match=True, drifted_code=[])`, and **never** resolves a `-security-code.json` (or `-security-reconcile.json`) save — the cross-target poisoning guard.
- `resolve_reusable_security(..., target="code", step_id=N)` scopes its lookup to the matching `step_id` (mirroring `_find_saved_for_step`), so one step's saved code audit is never served to a different step's caller; a `target="code"` call with `step_id=None` raises.
- An edited plan yields `plan_match=False`; an edited / deleted / newly-landed in-scope code file yields `code_match=False` with the absolute path in `drifted_code`.
- A `code_fingerprint_present=False` sidecar yields `code_match=False` (stale) regardless of dict contents; a `present=True` empty-map sidecar yields `code_match=True`.
- `review_id` selects by stem (both `<stem>` and `<stem>-security-<target>` forms); absent id loads newest; no `-security-<target>.json` → `None`.
- `resolve_reusable_security` raises (not `None`) on an unparseable plan path.
- `run_security_audit` and the step-1 symbols are byte-unchanged; `plan_tool/review_persistence.py` is **not** edited.
- Every `tests/test_security_audit.py` test is green with no `allow_real_claude` marker.

## References

- [OWASP Top 10 (2021)https: — the risk taxonomy whose findings (carried as `Recommendation`s with `source="security-plan"`/`"security-code"`) this step persists and replays.
- [CWE — Common Weakness Enumeration (MITRE)https: — the weakness catalog labeling the persisted findings consistently across save/reload.

## Deferred

- **CLI wiring** — step 3 (`plan_tool/cli/security_cmd.py`): computing the repo-relative plan path + the two fingerprints, calling `write_security_report(..., target=...)` after an audit, calling `resolve_reusable_security(..., target=...)` behind a reuse prompt, and the interactive `try/except (ParseError, ValidationError, OSError)` wrap of the resolver. This step adds the composable functions only; `run_security_audit` does not auto-save. (Per-target reuse *scoping* now lands **here**, in the resolver's `target` parameter — only the interactive reuse-*prompt* call site is deferred to step 3.)
- **Drift-attribution rendering of `drifted_code`** — emitting the `path (step N: title)` warning via `plan_tool/cli/reconcile.py:_print_attributed_files` + `reconcile_drift_hint` belongs to the CLI/reconcile steps (3/4), not this resolver.
- **`security-reconcile` ReconcileKind + auto-reconcile hook** — step 4; this step adds no `_RECONCILE_KINDS` entry.
- **Consolidating `resolve_reusable_security` / `resolve_reusable_audit` / `resolve_reusable_reconcile` into one `kind`-parametrized resolver (and a shared `diff_fingerprint_maps` helper)** — a refactor `detail` cannot mint; left for reconcile to surface rather than expanding this footprint.
