> **Auto-archived**: this plan was swept on 2026-07-12 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Backfill plan/code fingerprints onto the review, completeness, and convergence telemetry recorders

## Summary

Thread caller-computed fingerprints into the three authoring-time decision telemetry recorder calls that today rely on the empty defaults: `record_code_reveals_split` in `plan_tool/review.py`, `record_granularity` and `record_audit_coverage` in `plan_tool/cli/completeness_phases.py`, and `record_convergence` in `plan_tool/cli/convergence_cmd.py`. Each site already has (or can cheaply reach) the plan on disk, so it computes `plan_fingerprint` (via `review_persistence.compute_plan_fingerprint`) and passes it to the recorder. `code_fingerprint` (the large path→hash map) is added **only** at the code-grounded, rarely-firing `record_code_reveals_split` site — **not** at `record_granularity`/`record_audit_coverage`, which are about plan structure / audit coverage, don't hold the map in hand, and fire every `--iterate` round (carrying it there would re-hash the whole footprint per round). The one design wrinkle: `review.py:extract_recommendations` (where the split recorder fires) has no `plan_path` in scope, so this step threads an optional `plan_path` from its reconcile caller `review_plan_full`. Every change is purely additive and best-effort — wrapped so a fingerprint-compute or record error never changes the host command's exit code or output. On green, a newly recorded event at each of these four sites carries a non-empty `plan_fingerprint` (plus `code_fingerprint` at the split site only), while `record_prompt_budget` stays fingerprint-less.

## Table of Contents

- [Why](#why) — what's unjoinable today and why fingerprints fix it
- [Input](#input) — the recorder API and fingerprint helpers this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — the three source modules and three test files touched
- [Implementation](#implementation) — how each site computes and passes fingerprints, and the `plan_path` threading in review.py
- [Tests](#tests) — per-site fingerprint assertions plus the best-effort invariant
- [Acceptance criteria](#acceptance-criteria) — the observable checks a reviewer runs
- [References](#references) — the fingerprint/telemetry docs relevant here
- [Deferred](#deferred) — sites and behavior owned by other steps

## Why

Phase 1 gave `DecisionEvent` a place to carry the join keys (`plan_fingerprint`/`code_fingerprint`), but every authoring-time recorder call verified at HEAD still passes nothing for them and relies on the `""`/`{}` defaults. So new events from these three families stay unjoinable on the renumber-proof fingerprint anchor a phase-3 resolver will correlate on. The recorders already accept the defaulted params — the callers just never wired them. This step is the review/completeness/convergence slice of Part A (`create.py`'s two recorders are step 2): make the producers that have a plan in hand actually stamp the keys, without touching control flow, exit codes, or operator-visible output.

## Input

This step populates two fixed contracts without changing either.

- **Existing recorder signatures** in `plan_tool/telemetry.py` — `record_code_reveals_split`, `record_granularity`, `record_audit_coverage`, `record_convergence` each already accept `plan_fingerprint: str = ""` and `code_fingerprint: Optional[dict[str, str]] = None`. This step relies on those defaults' presence to pass digests in with no signature change. `record_decision` already swallows every error, so the recorder call itself is safe; the added risk is only the fingerprint-compute above it.
- **Fingerprint compute helpers** — `plan_tool/review_persistence.py:compute_plan_fingerprint(plan_path)` returns the plan+detail-bundle SHA-256 hex string (reads the plan file). `plan_tool/fingerprint.py:compute_code_fingerprint(plan, plan_path, repo_root)` returns the `{repo-relative-posix-path: sha256-hex}` map over the plan's in-scope code files (needs a parsed `Plan`). Their inputs decide what each site can carry: a site with only a resolved plan path can compute `plan_fingerprint`; a site that also holds a parsed `Plan` can compute `code_fingerprint`.
- **`run` telemetry state** — `run_id` needs no backfill here. It auto-flows from the `telemetry`-owned `_active_run_id` ContextVar, bound only at the two `run` entrypoints. These three commands (`reconcile-plan`, `completeness-audit`, `convergence`) are not runs, so `run_id=""` is correct, not a gap.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/review.py` — add an optional `plan_path: Optional[Path] = None` param to `extract_recommendations`; thread the real `plan_path` from `review_plan_full`'s call; inside the reconcile-lane `if split_recs:` block, compute the fingerprints best-effort and pass them to `record_code_reveals_split`.
  - `plan_tool/cli/completeness_phases.py` — at the `record_granularity` site (deterministic-checks phase) and the `record_audit_coverage` site (conceptual-audit phase), compute `plan_fingerprint` best-effort from `path` and pass it (no `code_fingerprint` — these fire every `--iterate` round).
  - `plan_tool/cli/convergence_cmd.py` — at the `record_convergence` site in `cmd_convergence`, compute `plan_fingerprint` best-effort from `path` and pass it.
  - `tests/test_review.py` — assert the code-reveals-split event carries the fingerprints.
  - `tests/cli/test_completeness_cmd.py` — assert the granularity and audit-coverage events carry the fingerprints.
  - `tests/cli/test_convergence_cmd.py` — assert the convergence event carries `plan_fingerprint`.

## Implementation

The foundational logic is one rule applied at four call sites: **compute the caller-side fingerprint(s) and pass them into the recorder's already-defaulted `plan_fingerprint`/`code_fingerprint` params, wrapped so a compute error can't fail the host command.** Follow the existing pattern in `plan_tool/cli/completeness_phases.py`'s sidecar-persist tail, which already computes `compute_plan_fingerprint(path)` and `compute_code_fingerprint(plan, path, ctx.repo_root)` together — mirror that shape, don't invent a new one.

**Which fingerprints each site carries.** Design decision 3 of the plan: carry `plan_fingerprint` everywhere (short digest, renumber-proof anchor); carry the full `code_fingerprint` map only where the decision is about code state or the module already reaches it cheaply.

- **`record_code_reveals_split` (review.py, reconcile lane)** — carry **both**. This detector is code-grounded (it reads which of a step's files look built vs un-built), so `code_fingerprint` is the state the decision is about. It fires rarely (only the full reconcile lane, only when `split_recs` is non-empty), so computing the map here is bounded. If threading proves awkward, `plan_fingerprint` alone is an acceptable fallback — but prefer both.
- **`record_granularity` + `record_audit_coverage` (completeness_phases.py)** — carry **`plan_fingerprint` only**, not `code_fingerprint`. These two events describe **plan structure** and **audit coverage**, not code state, and the map is **not** in hand at these sites (the module's only `compute_code_fingerprint` call is inside a *different* function, `_persist_and_present_report`'s sidecar-persist tail). Carrying `code_fingerprint` here would hash the whole footprint fresh, and under `--iterate` these fire **every audit round**, writing a full ~code map per line each round — the exact volume/re-hash cost the plan's Line-volume rule forbids. So add only the `compute_plan_fingerprint` body-local import at each record site and pass `plan_fingerprint`; leave `code_fingerprint` at its `None` default.
- **`record_convergence` (convergence_cmd.py)** — carry **`plan_fingerprint` only**. `cmd_convergence` resolves a plan `path` but never parses a `Plan`, and the convergence verdict is about the saved-report recurrence keyed to the plan, not code state. It already imports `compute_plan_fingerprint`. Do **not** parse a `Plan` just to add `code_fingerprint` — that would be new work the decision doesn't need.

**Site-by-site shape.**

- **completeness_phases.py `record_granularity`** — this call sits in the deterministic-checks phase with `path` in scope. Right before the record call, in a local `try/except`, compute `plan_fp = compute_plan_fingerprint(path)` (default `""` on failure) and pass `plan_fingerprint=plan_fp`. Do **not** compute or pass `code_fingerprint`. Add the `compute_plan_fingerprint` import body-locally next to the existing `from plan_tool.telemetry import record_granularity`, matching the lazy-import style already used at that site.
- **completeness_phases.py `record_audit_coverage`** — same shape (`plan_fingerprint` only), in the conceptual-audit phase. It resolves `plan_slug` via `slug_from_filename(path)`; reuse `path` for the fingerprint compute.
- **convergence_cmd.py `record_convergence`** — `cmd_convergence` has `path` and `ctx.repo_root`. Compute `plan_fingerprint = compute_plan_fingerprint(path)` best-effort and pass it. The `compute_plan_fingerprint` import already exists at module top — no new import needed. Keep the compute inside a `try/except` (or reuse a defaulted-empty local) so a fingerprint error never perturbs the always-exits-0 read-only contract of this command.
- **review.py `record_code_reveals_split`** — this is the only site needing plumbing. The recorder fires inside `extract_recommendations`, which today receives `plan`, `plan_name`, and `repo_root` but **no `plan_path`**. Add an optional `plan_path: Optional[Path] = None` param to `extract_recommendations`. Thread the real `plan_path` from `review_plan_full` (the reconcile caller, which already holds it). The other caller, `collect_deterministic_findings`, passes `heuristic_hits=[]` and leaves `reconcile_lane=False`, so the split producer never fires there — leaving its call unchanged (default `None`) is correct. Inside the existing `if split_recs:` block, guard on `plan_path is not None`, compute the fingerprints best-effort (lazy-import `compute_plan_fingerprint`/`compute_code_fingerprint` inside the block, mirroring review.py's existing body-local imports like `from plan_tool.granularity import ...`), and pass them to `record_code_reveals_split`.

**Constraints and gotchas.**

- **Best-effort is mandatory.** Every added fingerprint-compute must be wrapped so an exception returns empty/skips rather than raising. `record_decision` already swallows its own errors, but `compute_plan_fingerprint`/`compute_code_fingerprint` are the caller's code and would otherwise escape. Convergence's read-only always-exits-0 contract and completeness's/reconcile's exit codes must be untouched.
- **`telemetry.py` stays a stdlib-only leaf.** Do not import a fingerprint producer into `telemetry.py`. Fingerprints are computed caller-side and passed as already-computed values (`str` / `dict[str, str]`). The leaf's `grep -E '^(from|import) plan_tool' plan_tool/telemetry.py` must stay empty.
- **No signature change on the recorders and no schema bump.** The recorders already accept the params; do not add fields, and do not bump `TELEMETRY_SCHEMA_VERSION` (phase 2 adds no base field — the reader already tolerates existing kinds).
- **The `extract_recommendations` param is additive only.** Default it `None` so `collect_deterministic_findings` and any direct test callers keep working unchanged; it changes no behavior on its own path (the split producer is already gated on `reconcile_lane` + non-empty hits).
- **No new loop to hoist above here.** `record_code_reveals_split` fires once with a list of `step_ids`; the "hoist compute above per-finding loops" rule (design decision 4) targets the Part-B per-finding sites in later steps, not this step.

**Parallel locations (for orientation, not this step's work).** `plan_tool/create.py`'s `record_create_granularity_assessment` and `record_create_step_outcome` are the same backfill pattern — owned by **step 2**, out of scope here. The Part-B new recorders (drift-gate, apply-verdict, escalate-to-split) are steps 3–5. The sidecar-persist tail in `completeness_phases.py` already computes both fingerprints — mirror its shape, but it is a separate computation for report staleness and is not consolidated by this step.

## Tests

Reuse the established pattern: drive the site, then read events with `plan_tool.telemetry.read_decisions(repo_root)` and assert on `.plan_fingerprint` / `.code_fingerprint` of the matching `.decision`. **Assert equality, not non-emptiness:** each `plan_fingerprint` assertion must compare the recorded value to `compute_plan_fingerprint(<the real on-disk plan path the test drove>)` — `compute_plan_fingerprint` returns a stable *non-empty* digest even for a missing/wrong path, so a non-empty-only check would pass even if the site fingerprinted the wrong path. Equality to the real digest proves the site fingerprinted the actual plan.

`tests/test_review.py`:
- `test_code_reveals_split_event_carries_fingerprints` — a full reconcile drive (via `review_plan_full` or `extract_recommendations` with `reconcile_lane=True`, real heuristic hits producing a split, and a real `plan_path`) records a `code-reveals-split` event whose `plan_fingerprint` is non-empty and whose `code_fingerprint` is a non-empty path→hash map.
- `test_extract_recommendations_without_plan_path_still_records_split` — when `plan_path` is `None`, the split event still records (fingerprints empty) and nothing raises — proving the optional param is safe.
- `test_collect_deterministic_findings_records_no_split` — unchanged behavior: the non-reconcile caller (empty hits) emits no split event, so its unchanged call is correct.

`tests/cli/test_completeness_cmd.py`:
- `test_granularity_event_carries_plan_fingerprint_only` — driving the deterministic-checks phase records a `granularity` (`stage="completeness"`) event with non-empty `plan_fingerprint` and `code_fingerprint == {}` (no map — avoids the per-round re-hash).
- `test_audit_coverage_event_carries_plan_fingerprint_only` — driving the conceptual-audit phase (conceptual audit stubbed at the domain seam `plan_tool.review.audit_plan_until_stable`, no real Claude) records an `audit-coverage` event with non-empty `plan_fingerprint` and `code_fingerprint == {}`.
- `test_completeness_fingerprint_compute_failure_is_best_effort` — a forced-raising `compute_plan_fingerprint`/`compute_code_fingerprint` (monkeypatched) leaves the phase's return value and rc unchanged; the event still records with empty fingerprints.

`tests/cli/test_convergence_cmd.py`:
- `test_convergence_event_carries_plan_fingerprint` — a `main(["convergence", ...])` drive against a seeded plan records a `convergence` event with a non-empty `plan_fingerprint`.
- `test_convergence_event_has_empty_code_fingerprint` — the same event carries `code_fingerprint == {}` (convergence carries no code map).
- `test_convergence_fingerprint_failure_keeps_exit_zero` — a forced-raising `compute_plan_fingerprint` leaves the command exit code at 0 and stdout unchanged.

### Test-creation order (feature step)

This is a **feature** step. Write these unit tests alongside the implementation at each site. Green-before-done gate: every new test above must pass before the step is considered finished, the leaf invariant stays intact (`grep -E '^(from|import) plan_tool' plan_tool/telemetry.py` returns empty), and the affected suites (`tests/test_review.py`, `tests/cli/test_completeness_cmd.py`, `tests/cli/test_convergence_cmd.py`) must stay green.

## Acceptance criteria

- A newly recorded `code-reveals-split` event (review reconcile lane) carries a `plan_fingerprint` equal to `compute_plan_fingerprint(<real plan path>)` and a non-empty `code_fingerprint` map.
- A newly recorded `granularity` (`stage="completeness"`) event and a newly recorded `audit-coverage` event each carry a `plan_fingerprint` equal to `compute_plan_fingerprint(<real plan path>)` and `code_fingerprint == {}` (no map, to avoid the per-`--iterate`-round re-hash).
- A newly recorded `convergence` event carries a `plan_fingerprint` equal to `compute_plan_fingerprint(<real plan path>)` and `code_fingerprint == {}`.
- A forced failure in `compute_plan_fingerprint`/`compute_code_fingerprint` at any of these sites leaves the host command's exit code and stdout unchanged (test-proven for at least the completeness and convergence sites).
- `extract_recommendations` accepts an optional `plan_path` param defaulting to `None`; `collect_deterministic_findings`'s call is unchanged and records no split event.
- `plan_tool/telemetry.py` still imports nothing first-party (`grep -E '^(from|import) plan_tool' plan_tool/telemetry.py` returns empty); `TELEMETRY_SCHEMA_VERSION` is unchanged.
- `record_prompt_budget` is not touched by this step and stays fingerprint-less.

## References

- [hashlib — Secure hashes and message digests (Python 3.13)](https://docs.python.org/3/library/hashlib.html) — the digest API under `compute_plan_fingerprint`/`compute_code_fingerprint`; useful when reasoning about what each fingerprint covers.
- [contextvars — Context Variables (Python 3.13)](https://docs.python.org/3/library/contextvars.html) — confirms `run_id` auto-flows from the `_active_run_id` ContextVar, so these non-run sites correctly leave it `""`.
- [How to mark test functions with attributes — pytest](https://docs.pytest.org/en/stable/how-to/mark.html) — for placing the convergence/completeness CLI-drive tests under `@pytest.mark.integration` when they call `main([...])`, per the project's unit-first convention.

## Deferred

- **`create.py`'s two recorders** (`record_create_granularity_assessment`, `record_create_step_outcome`) — owned by step 2; same backfill pattern, different module.
- **The three new Part-B recorders and their call sites** (drift-gate in `refresh.py`, apply-verdict and escalate-to-split in `launcher.py`) — steps 3–5.
- **`code_fingerprint` on the convergence event** — intentionally omitted; the verdict is about report recurrence, not code state, and the site holds no parsed `Plan`.
- **Consolidating the fingerprint compute with the sidecar-persist tail in `completeness_phases.py`** — a separate computation for report staleness; not merged here.
- **`record_prompt_budget` fingerprints** — by design it stays the ownerless pre-send backstop with no plan context (spike §3); not in scope.
