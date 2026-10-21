> **Auto-archived**: this plan was swept on 2026-07-12 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Record a per-finding apply verdict decision event where parse_apply_verdict is consumed

## Summary

Add a new decision-telemetry family, `apply-verdict`, emitted once each time `plan_tool/launcher.py:apply_finding` parses an apply-finding response. Add one stdlib-only recorder wrapper (`record_apply_verdict`) plus its `kind`/`decision` constants to `plan_tool/telemetry.py`, then call it at the single site that consumes `parse_apply_verdict` (inside `apply_finding`, right after `verdict = parse_apply_verdict(stdout) or "UNKNOWN"`), carrying the parsed verdict token, the resolved step id, the finding `anchor`, and `plan_fingerprint`. `apply_finding` holds neither the `anchor` nor a hoisted digest, so both are **threaded into its signature** as defaulted keyword params, by the **four per-finding apply loops that own `rec.anchor`**: the review/reconcile apply walk (`plan_tool/cli/review_actions.py`), the serial completeness-apply walk (`plan_tool/cli/completeness_cmd.py`), the `detail` convergence loop (`plan_tool/detail.py:generate_detail`), and the `create` convergence loop (`plan_tool/create.py:create_plan`). Each computes `plan_fingerprint` **once before its loop** and passes `rec.anchor` + that digest on each call; any non-loop caller passes the defaults and still records the verdict + `step_id`. `code_fingerprint` is **not** carried (per the body's plan_fingerprint-only, no-per-finding-map rule). Document the new family in `DATA_CONTRACT.md` and add its per-kind context-key test. Everything is additive and best-effort: the recorder is a stdlib leaf, the recorder call is wrapped so it can't raise, and `apply_finding`'s return value, control flow, and exit code stay exactly as they are — the only new write is one line to the gitignored `.plan-tool/telemetry/decisions.jsonl`.

## Table of Contents

- [Why](#why) — the apply verdict is the natural outcome anchor and today emits nothing
- [Input](#input) — the recorder API and the `apply_finding` state this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — one leaf + apply_finding + two apply walks + doc + test files
- [Implementation](#implementation) — the new recorder, the threaded call site, hoisted digest, and the best-effort guard
- [Tests](#tests) — recorder roundtrip, the call site fires per verdict, best-effort, and doc drift
- [Acceptance criteria](#acceptance-criteria) — observable checks a reviewer runs
- [References](#references) — the telemetry/format docs relevant here
- [Deferred](#deferred) — behavior owned by other steps / phase 3

## Why

`parse_apply_verdict` is the tool's read of what an apply-finding call actually did — APPLIED / NOT-APPLICABLE / BLOCKED / BLOCKED-STRUCTURAL, or UNKNOWN when Claude ignored the contract. That verdict is the closest thing in the whole pipeline to an *outcome*: it's the result that a phase-3 resolver would want to join back to the granularity / audit-coverage / convergence *decisions* that led to the apply. Today `apply_finding` parses the verdict, uses it to gate the diff/delta work, and records **nothing** — no `DecisionEvent` fires, so the distribution of apply outcomes (how often applies land vs get blocked, per plan and per step) is invisible to any later aggregation. This step makes the apply verdict observable — one telemetry line per apply — without changing what `apply_finding` decides, returns, or edits.

## Input

This step populates the phase-1 `DecisionEvent` contract and reads state `apply_finding` already computes. It changes neither.

- **`record_decision` and its wrappers** in `plan_tool/telemetry.py` — every per-kind wrapper (e.g. `record_convergence`, `record_audit_coverage`, `record_prompt_budget`) is a thin call over `record_decision(repo_root, *, kind, decision, plan_slug, context=..., plan_fingerprint=..., code_fingerprint=..., step_id=...)` taking primitives only. `record_decision` already mints `decision_id`, reads `run_id` from the `_active_run_id` ContextVar, folds `step_id` into the `decision_id` hash, and swallows every error. The new recorder mirrors this shape exactly.
- **The verdict vocabulary** — `plan_tool/launcher.py:parse_apply_verdict` returns one of `"APPLIED"` / `"NOT-APPLICABLE"` / `"BLOCKED"` / `"BLOCKED-STRUCTURAL"`, or `None` when no recognized token is found. The consumption site normalizes `None` to `"UNKNOWN"` (`verdict = parse_apply_verdict(stdout) or "UNKNOWN"`). The recorded event carries this normalized string, so its possible values are those four plus `"UNKNOWN"`.
- **`apply_finding`'s in-scope state** — at the consumption site the function already holds `plan_path`, `repo_root`, the parsed `plan` (parsed at the top of `apply_finding`), the resolved `step` (from `resolve_step`), the optional `plan_name`, and `run_logger`. `plan_slug` is reachable via `plan_name` or `plan_tool/locator.py:slug_from_filename` (already imported in `plan_tool/launcher.py`). What `apply_finding` does **not** hold: the finding `anchor` (only the walk caller's `rec.anchor` has it) and a pass-hoisted digest — both are threaded in as new defaulted params (see Implementation).
- **The four walk callers that own the anchor + the hoist point** — `plan_tool/cli/review_actions.py`'s apply walk, `plan_tool/cli/completeness_cmd.py`'s serial completeness-apply walk, `plan_tool/detail.py:generate_detail`'s convergence loop, and `plan_tool/create.py:create_plan`'s convergence loop each invoke `apply_finding` once per recommendation inside a per-`rec` loop and hold `rec.anchor` + `plan_path`/`repo_root`. Each passes `anchor=rec.anchor` and a `plan_fingerprint` computed **once before** its loop (`review_persistence.compute_plan_fingerprint(plan_path)`), satisfying the body's "hoist above per-finding loops" rule. Threading from all four matters because every apply-eligible decision family (review/reconcile, completeness, detail, create) resolves through `apply_finding` here — without it those apply verdicts would carry no join key. Any non-loop `apply_finding` caller passes neither and records with `anchor=""`, `plan_fingerprint=""`.
- **`run_id` needs no work here** — it auto-flows from the telemetry-owned `_active_run_id` ContextVar. Under `plan-tool run` the run scope is bound, so events carry a real `run_id`; when `apply_finding` runs inside a review/reconcile/completeness walk (not a `run`), the ContextVar is unset and `run_id=""`. This step wires nothing for it.
- **Open-bag context keys are not gated** — a recorder may emit `context` keys that are not in `plan_tool/data_contract.py:registered_open_bag_keys()`. `record_convergence` already emits `"verdict"` / `"runs"` there without registering them; registration only matters for validating `## Input` prose references. So this step touches **no** `plan_tool/data_contract.py`, and the new `verdict` context key needs no registration.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/telemetry.py` — add `APPLY_VERDICT_KIND` / `APPLY_VERDICT_DECISION` constants and the `record_apply_verdict(...)` wrapper next to the other per-kind recorders.
  - `plan_tool/launcher.py` — extend the existing `from plan_tool.telemetry import record_prompt_budget` line to also import `record_apply_verdict`; add two defaulted keyword params (`anchor: str = ""`, `plan_fingerprint: str = ""`) to `apply_finding`'s signature; and add one best-effort `record_apply_verdict` call at the `parse_apply_verdict` consumption site inside `apply_finding`.
  - `plan_tool/cli/review_actions.py`, `plan_tool/cli/completeness_cmd.py`, `plan_tool/detail.py` (`generate_detail`), and `plan_tool/create.py` (`create_plan`) — in each module's per-`rec` apply loop, compute `plan_fingerprint` once before the loop and pass `anchor=(rec.anchor or "")` + that digest into the `apply_finding` call. (These four loops thread the new params; any non-loop caller keeps the defaults.)
  - `DATA_CONTRACT.md` — add an `apply-verdict` sub-section under the Decision telemetry log, listing the `kind`/`decision` values and the context keys; add `"apply-verdict"` to the `kind` value list in the `DecisionEvent` field table.
  - `tests/test_telemetry.py` — add recorder roundtrip + verdict-value + best-effort tests.
  - `tests/test_launcher.py` — add tests that `apply_finding` emits the event with the parsed verdict.
  - `tests/test_data_contract.py` — add a doc-drift test for the new kind and its context keys (mirroring `test_prompt_budget_context_keys_documented`).

## Implementation

### The new recorder (`plan_tool/telemetry.py`)

- **Add two module-level constants** next to `PROMPT_BUDGET_KIND` / `PROMPT_BUDGET_DECISION`:
  - `APPLY_VERDICT_KIND = "apply-verdict"`
  - `APPLY_VERDICT_DECISION = "recorded"` (there is one call, so a single decision value is right; name it for the act, not the outcome — the outcome lives in `context["verdict"]`).
- **Add `record_apply_verdict(...)`** mirroring `record_convergence`'s shape — a thin, keyword-only wrapper over `record_decision` taking primitives: the `repo_root`, `plan_slug`, and the parsed `verdict` token, plus the optional `step_id` (`str | None`), the finding `anchor` (`str = ""`), and the defaulted `plan_fingerprint` base-event key (e.g. `record_apply_verdict(repo_root, *, plan_slug, verdict, step_id=None, anchor="", plan_fingerprint="") -> None`). **No `code_fingerprint` param** — the per-finding site is `plan_fingerprint`-only by the body's rule 3 (dozens of per-finding lines each carrying a ~45 KB map is wasteful volume).
  - Build `context={"verdict": verdict}` and add `context["step_id"] = step_id` when it is not `None` (follow the "omit when absent" convention the other wrappers use). The `anchor` rides the **base event** (via `record_decision(..., anchor=anchor)`), not `context` — it is a first-class join key phase 1 added as a base field. **Coerce `anchor` to `""` when falsy** — `Recommendation.anchor` is `Optional[str] = None` (an anchorless finding, e.g. a deterministic review finding, has `rec.anchor is None`), and `record_decision` does `str(anchor)`, so an un-coerced `None` would serialize the literal string `"None"` (worse than `""`). The wrapper must normalize: `anchor=str(anchor) if anchor else ""` (so both `None` and `""` land as the schema's `""`), and the callers should pass `anchor=(rec.anchor or "")` as belt-and-suspenders.
  - Forward `step_id=step_id` to `record_decision` so it folds into the `decision_id` hash — `apply_finding` has a single resolved step, so this is the singular-producer case that *does* forward a step id (contrast `record_code_reveals_split`, which holds a plural set and abstains). Note that `anchor` is **not** folded into the `decision_id` hash (phase 1 froze the hash inputs; `anchor` is a join key, not identity) — so two plan-wide findings resolving to the same step in the same second share a `decision_id` and the stored `anchor` is their only discriminator. That is acceptable: `decision_id` is a phase-1 class handle, not a unique id.
  - Pass `plan_fingerprint` and `anchor` straight through as the base-event keys.
- **Keep it stdlib-only.** Do not import `review_persistence` or `fingerprint` here — the digests are caller-supplied already-computed values, same as every other wrapper.

### The one call site (`plan_tool/launcher.py:apply_finding`)

- **Fire exactly once, at the `parse_apply_verdict` consumption site** — right after `verdict = parse_apply_verdict(stdout) or "UNKNOWN"`. This is the single spot the step title names. Emit one event per `apply_finding` invocation that reaches this line.
- **Do not emit on the early returns — and know what the recorded `UNKNOWN` therefore means.** The `dry_run` return (no invoke) and the **non-zero-exit / backend-failure** return both leave before this line and never consume `parse_apply_verdict`, so they record nothing. That keeps "one recorded verdict = one real apply parse" true. **Consequence (document it):** a recorded `UNKNOWN` means exactly one thing — *the apply ran (exit 0) but Claude emitted no recognized verdict token* (a contract violation) — **never** "the backend crashed." A backend-failure apply (exit ≠ 0) is not an `apply-verdict` event at all; it is already captured in the **run-log** (its `outcome=error`/`rc`), joinable to the same run by `run_id`. So the two failure modes are not conflated — they live in two stores, correlatable via `run_id` — and phase-3's apply-outcome distribution reads backend failures from the run-log, contract-violation `UNKNOWN`s from here. Note this scoping in the code with a one-line `# See DATA_CONTRACT.md` pointer.
- **No fingerprint compute inside `apply_finding`.** The digest is **threaded in** via the new `plan_fingerprint` param (computed once by the walk caller, ground rule 4). `apply_finding` does not call `compute_plan_fingerprint`/`compute_code_fingerprint` — doing so would recompute per finding across the walk's per-`rec` loop, the exact hot-site cost the body forbids. So there is no caller-side fingerprint `try/except` inside `apply_finding`; only the `record_apply_verdict(...)` call sits here, and `record_decision` already swallows its own errors. (Wrap the single record call in a `try/except` too if you want belt-and-suspenders, but it adds no compute that can raise.)
- **Thread the two new params through `apply_finding`.** Add `anchor: str = ""` and `plan_fingerprint: str = ""` to its signature (keyword, defaulted, so any non-loop caller is byte-for-byte unaffected). In each of the **four** per-`rec` apply loops — `cli/review_actions.py`, `cli/completeness_cmd.py`, `detail.py:generate_detail`, `create.py:create_plan` — compute `plan_fingerprint` **once before** the loop and pass `anchor=(rec.anchor or "")` + that digest into each `apply_finding` call, wrapped so a compute failure there degrades to `""` and never fails the loop.
- **Resolve `plan_slug`** from `plan_name` when present, else `slug_from_filename(plan_path.name)` (already imported).
- **Pass the resolved `step.id` as a string** for `step_id`, the threaded `anchor`, and the threaded `plan_fingerprint`. **Do not** carry `code_fingerprint`. The threaded `plan_fingerprint` reflects the plan state the walk observed *before* its per-finding loop, which is the correct join anchor (it is not re-read per apply).

### Constraints that are not free to vary

- **The recorder call must not change `apply_finding`'s behavior.** No new return path, no altered `verdict`, no effect on the diff/delta or auto-fix pass. The event write sits beside those, not in front of them.
- **Best-effort end to end.** Inside `apply_finding` the only telemetry statement is the `record_apply_verdict` call (which swallows its own errors); in the walk caller the once-per-pass fingerprint compute is wrapped in a `try/except` degrading to `""`. Neither a fingerprint-compute error (caller) nor a recorder error (sink) can propagate. A telemetry failure must leave the apply's `exit_code` / `verdict` / diff and the walk's convergence loop untouched.
- **Single writer stays single.** All events still funnel through `record_decision`; this step adds a wrapper and a call site, nothing that writes `decisions.jsonl` directly.
- **Foundational logic — the verdict token classification — lives only in `parse_apply_verdict`.** This step reads its output; it does not re-derive or re-classify the verdict anywhere. Grep confirms the only other `parse_*_verdict` sibling (`parse_deep_verdict`) is a separate token set for the deep-verify flow and is out of scope here.

## Tests

### Test-creation order (feature step)

This is a **feature** step. Add these unit tests with the implementation; every one must be green before the step is done.

`tests/test_telemetry.py`:
- `test_record_apply_verdict_roundtrips` — records with a fixed `clock`, then `read_decisions` returns one event with `kind == "apply-verdict"`, `decision == "recorded"`, `context["verdict"]` equal to the passed token, and `context["step_id"]` present when a step id was passed.
- `test_apply_verdict_step_id_folds_into_decision_id` — two records that differ only in `step_id` produce different `decision_id`s (proves the step id is forwarded into the hash).
- `test_apply_verdict_omits_step_id_when_none` — a record with `step_id=None` writes no `step_id` context key.
- `test_apply_verdict_carries_plan_fingerprint_and_anchor` — a passed `plan_fingerprint` and `anchor` land on the base event fields; `code_fingerprint` stays `{}` (no map carried).
- `test_apply_verdict_anchor_none_coerced_to_empty` — calling `record_apply_verdict(..., anchor=None)` (the anchorless-finding case, `Recommendation.anchor is None`) records the base `anchor` as `""`, **not** the string `"None"` — proving the falsy-coercion.
- `test_apply_verdict_best_effort` — a record into an unwritable telemetry path (or with a pathologically large context) does not raise.

`tests/test_launcher.py` (extend `TestApplyFindingHappyPath` / a new sibling class, using a `fake_invoker` and `repo_root=tmp_path`, then `read_decisions(tmp_path)`):
- `test_apply_finding_records_applied_verdict` — a fake invoker returning `## Verdict\nAPPLIED` yields exactly one `apply-verdict` event with `context["verdict"] == "APPLIED"` and `context["step_id"]` equal to the resolved step.
- `test_apply_finding_threads_anchor_and_plan_fingerprint` — calling `apply_finding(..., anchor="some-slug", plan_fingerprint="pf123")` records an event whose base `anchor == "some-slug"` and `plan_fingerprint == "pf123"`; a call omitting them records `anchor == ""` / `plan_fingerprint == ""` (default-caller path).
- `test_apply_walk_hoists_and_threads` (one per apply-loop module — `tests/test_review_actions.py`, the completeness-apply walk's module, `tests/test_detail.py`, `tests/test_create.py`) — each of the four apply loops computes `plan_fingerprint` once and passes `rec.anchor` per finding; assert the recorded events carry each rec's anchor and share one plan_fingerprint, and that `compute_plan_fingerprint` is invoked once, not per finding, in each loop. (At minimum cover the review/reconcile and completeness walks directly; the detail/create loops share the identical hoist-and-thread shape.)
- `test_apply_finding_records_blocked_verdict` — a `BLOCKED` response records `context["verdict"] == "BLOCKED"`.
- `test_apply_finding_records_unknown_when_no_verdict` — a response with no `## Verdict` records `context["verdict"] == "UNKNOWN"`.
- `test_apply_finding_dry_run_records_nothing` — a `dry_run=True` call writes no `apply-verdict` event.
- `test_apply_finding_nonzero_exit_records_nothing` — a fake invoker returning a non-zero exit code writes no `apply-verdict` event.
- `test_apply_finding_telemetry_is_best_effort` — monkeypatch `record_apply_verdict` (or the fingerprint helper it calls) to raise; `apply_finding` still returns its normal `ApplyFindingResult` with the correct verdict.

`tests/test_data_contract.py`:
- `test_apply_verdict_decision_documented` — `"apply-verdict"` appears in `DATA_CONTRACT.md`.
- `test_apply_verdict_context_keys_documented` — `verdict` and `step_id` are documented under the new sub-section (mirror `test_prompt_budget_context_keys_documented`).

## Acceptance criteria

- `plan_tool/telemetry.py` exposes `record_apply_verdict`, `APPLY_VERDICT_KIND == "apply-verdict"`, and `APPLY_VERDICT_DECISION == "recorded"`.
- A successful `apply_finding(...)` with `repo_root=tmp_path` writes exactly one line to `<tmp_path>/.plan-tool/telemetry/decisions.jsonl` whose `kind` is `"apply-verdict"` and whose `context["verdict"]` equals the parsed token.
- `apply_finding` with `dry_run=True` or a non-zero invoker exit writes no `apply-verdict` event.
- `apply_finding` gains defaulted `anchor=""` / `plan_fingerprint=""` params; the review/reconcile apply walk passes `rec.anchor` + a once-computed `plan_fingerprint`, and the recorded event carries them on the base fields with no `code_fingerprint` map.
- A raised error from the recorder (or the walk-caller's once-per-pass fingerprint compute) does not change `apply_finding`'s returned `verdict`, `exit_code`, or diff, nor the walk's convergence loop.
- `DATA_CONTRACT.md` documents the `apply-verdict` kind, its `recorded` decision, and its `verdict` / `step_id` context keys; `"apply-verdict"` is in the `kind` value list.
- The full suite is green: `uv run pytest tests/test_telemetry.py tests/test_launcher.py tests/test_data_contract.py -q`.

## References

- [contextvars — Context Variables (Python 3.13)](https://docs.python.org/3/library/contextvars.html) — the `_active_run_id` ContextVar whose value auto-flows into the new event as `run_id`; nothing to wire here, but explains why a `run` binds it and a walk does not.
- [JSON Lines](https://jsonlines.org/) — the one-object-per-line append contract the recorder emits into `decisions.jsonl`.
- [hashlib — Secure hashes and message digests (Python 3.13)](https://docs.python.org/3/library/hashlib.html) — the digest API behind `compute_plan_fingerprint` / `compute_code_fingerprint` that this step threads as the join keys.
- [dataclasses — Data Classes (Python 3.13)](https://docs.python.org/3/library/dataclasses.html) — the `DecisionEvent` machinery the new context key rides on with no schema bump.
- [How to mark test functions with attributes — pytest](https://docs.pytest.org/en/stable/how-to/mark.html) — placing the new recorder tests under the project's unit-first convention.

## Deferred

- **Enriching the event with the introduced/resolved findings delta** — those counts are computed after the verdict (only for `APPLIED` with a diff) and are not needed to make the verdict observable; carrying them is a phase-3 enrichment, not this step.
- **Recording backend-invocation-failure applies (`exit_code != 0`) as a distinct `apply-verdict` event** — deliberately deferred. Those applies return before the `parse_apply_verdict` line and emit no `apply-verdict` event; the failure is **already captured in the run-log** (`outcome=error`/`rc`), joinable to the same apply by `run_id`, so no signal is lost — it lives in the other store (matching the spike's "outcomes ride the existing run-log, #72 reads and correlates" architecture). Giving invocation failures their own `apply-verdict` verdict token (e.g. `INVOCATION-FAILED`) so the apply-outcome distribution is complete from a single family is a **phase-3 completeness enhancement**, tracked in the BACKLOG #72 phase-3 scope (step 6). Phase 2's recorded `UNKNOWN` therefore means exactly "apply ran (exit 0) but Claude emitted no verdict token" — the contract-violation case — never a crash.
- **The phase-3 outcome resolver** that joins this apply verdict back to the granularity/audit/convergence decision that led to it — deferred with the rest of BACKLOG #72's resolver and the `plan-tool telemetry` analysis surface.
- **Backfilling other decision sites** (create-stage and drift-gate recorders) — owned by steps 1–3; this step covers only the `apply_finding` verdict site.
- **Capturing apply-verdicts under `completeness-apply --jobs N` (parallel mode)** — the event is written inside `apply_finding` to `repo_root/.plan-tool/telemetry/decisions.jsonl`, but the parallel apply worker (`cli/completeness_apply_parallel.py`) runs `apply_finding` in an **isolated git worktree** whose only replay onto the canonical tree is captured content changes, not the telemetry side-effect — so per-finding verdicts under `--jobs N` (N>1) land in the discarded worktree and never reach the canonical log. Serial `--jobs 1` (the default + the interactive walk) records normally. Routing the worker's telemetry write to the canonical `repo_root` is a bounded hardening follow-up, out of scope for this backfill slice (see the plan's Known limitations). Documented, not fixed here.
- **Registering `verdict` in `plan_tool/data_contract.py:registered_open_bag_keys()`** — not required (recorders emit unregistered context keys today, e.g. `record_convergence`), and `plan_tool/data_contract.py` is out of this step's file set; a later step may register it if an `## Input` reference ever needs it.
