> **Auto-archived**: this plan was swept on 2026-07-12 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Telemetry Linkage Backfill
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Add fingerprints to the on-disk telemetry recorder calls (review, completeness,
    convergence)
  files:
  - plan_tool/review.py
  - plan_tool/cli/completeness_phases.py
  - plan_tool/cli/convergence_cmd.py
  - tests/test_review.py
  - tests/cli/test_completeness_cmd.py
  - tests/cli/test_convergence_cmd.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/telemetry-linkage-backfill/01-fingerprints-on-disk-telemetry-recorder.md
  status: done
- id: 2
  title: Source and pass fingerprints into create.py's two telemetry recorder calls
  files:
  - plan_tool/create.py
  - tests/test_create.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/telemetry-linkage-backfill/02-source-pass-fingerprints-create-py-two.md
  status: done
- id: 3
  title: Record a drift-gate decision event in refresh_plan (no-baseline / no-drift
    / drifted)
  files:
  - plan_tool/telemetry.py
  - plan_tool/refresh.py
  - DATA_CONTRACT.md
  - tests/test_telemetry.py
  - tests/test_data_contract.py
  - tests/test_refresh.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/telemetry-linkage-backfill/03-record-drift-gate-decision-event.md
  status: done
- id: 4
  title: Record a per-finding apply verdict decision event where parse_apply_verdict
    is consumed
  files:
  - plan_tool/telemetry.py
  - plan_tool/launcher.py
  - DATA_CONTRACT.md
  - tests/test_telemetry.py
  - tests/test_data_contract.py
  - tests/test_launcher.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/telemetry-linkage-backfill/04-record-per-finding-apply-verdict.md
  status: done
- id: 5
  title: Record an escalate-to-split outcome decision event in escalate_to_split
  files:
  - plan_tool/telemetry.py
  - plan_tool/launcher.py
  - DATA_CONTRACT.md
  - tests/test_telemetry.py
  - tests/test_data_contract.py
  - tests/test_launcher.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/telemetry-linkage-backfill/05-record-escalate-split-outcome-decision.md
  status: done
- id: 6
  title: 'Update BACKLOG #72 to mark phase 2 shipped and narrow the remaining scope
    to phase 3'
  files:
  - BACKLOG.md
  complexity: low
  change_type: non-code
  depends_on:
  - 1
  - 2
  - 3
  - 4
  - 5
  detail: docs/implementation-plans/plan-details/telemetry-linkage-backfill/06-update-backlog-72-mark-phase-shipped.md
  status: done
---
# Telemetry Linkage Backfill

## Overview

Phase 2 of the decision/outcome telemetry effort (BACKLOG #72) fills the telemetry producers so new `DecisionEvent`s actually carry the join keys a phase-3 resolver will correlate on. Phase 1 gave the base event a *place* to carry `decision_id`/`run_id`/`plan_fingerprint`/`code_fingerprint`/`anchor`; this plan makes producers *populate* them. Two coordinated parts: **Part A** threads caller-computed fingerprints into six existing recorder call sites, and **Part B** adds three new per-kind recorders (drift-gate, `apply_finding` verdicts, escalate-to-split outcomes) in `telemetry.py` plus one call site each. Everything is purely additive and best-effort: telemetry is observational and must never change a command's control flow, exit code, or output. It ships **no** new consumer — the resolver/analysis surface and outcome-verdict derivation remain phase 3.

## Problem statement

The spike's empirical finding over 347 real events: the recorders that carry the good join keys (fingerprints, outcome actions) are exactly the ones that haven't fired, and 81% of events are ownerless prompt-budget checks — no post-hoc join logic recovers linkage the events don't carry. Phase 1 gave the event a place to carry `plan_fingerprint`/`code_fingerprint`/`anchor`, but every authoring-time recorder call site verified at HEAD still passes nothing for them (relies on the `""`/`{}` defaults), so new events remain unjoinable on the renumber-proof fingerprint anchor. And three of the highest-leverage heuristic decisions the backlog names — the reconcile/`--refresh` drift-gate, per-finding `apply_finding` verdicts, and escalate-to-split outcomes — emit no decision event at all. Until the producers carry the keys, phase 3's resolver has nothing to correlate and its smoke test (spike §7) cannot run.

## Architecture

**Part A — backfill fingerprints onto existing recorders' call sites.** The recorders already accept `plan_fingerprint`/`code_fingerprint` (defaulted); their callers just don't pass them. Thread the caller-computed digests (`review_persistence.compute_plan_fingerprint`, `fingerprint.compute_code_fingerprint`) into each site that has a plan in hand: `plan_tool/create.py` — `record_create_granularity_assessment` (~3504) and the `record_create_step_outcome` wrapper `_record_step_outcome` (~3539); `plan_tool/review.py` — `record_code_reveals_split` (~3457, reconcile lane); `plan_tool/cli/completeness_phases.py` — `record_granularity` (~664) and `record_audit_coverage` (~816) (both modules already import the compute helpers); `plan_tool/cli/convergence_cmd.py` — `record_convergence` (~119). **Create-site timing caveat:** the two `create.py` recorders fire inside `_review_step_change_types` **before** `write_new_plan`, so the plan file is not yet on disk. `compute_plan_fingerprint` on a missing file returns not `""` but a *stable constant* (the empty/missing-file digest) — identical for every fresh create, so it is a **useless join key** and the create sites deliberately **do not call it** (leaving `plan_fingerprint=""`, its default). They carry `code_fingerprint` instead, computed from the in-memory `plan` + footprint (needs no written file). Caveat within the caveat: `compute_code_fingerprint` hashes only files that exist on disk, so for a **greenfield** plan whose steps `create:` new files, the map is `{}` and the create event carries *no* fingerprint join key — a documented weak-anchor limitation (see Known limitations), acceptable because create decisions are also joinable by `plan_slug`+`ts` and the phase-3 resolver treats a keyless create event as weakly-anchored. The four already-on-disk sites (code-reveals-split, granularity[completeness], audit-coverage, convergence) carry a real `plan_fingerprint`. `record_prompt_budget` stays fingerprint-less by design (ownerless pre-send backstop, no plan context, spike §3). `run_id` needs no backfill: it auto-flows from the `telemetry`-owned `_active_run_id` ContextVar, which phase 1 binds only at the two `run` entrypoints; these are authoring-time commands (`create`/`completeness`/`convergence`), not runs, so `run_id=""` is correct. `anchor` is carried only where a decision is about one specific finding — no Part-A site is (they're plan-/step-wide), so Part A adds fingerprints, not anchors.

**Part B — add recorders + call sites for the three un-wired decision families.** New per-kind convenience recorders in `telemetry.py`, each a thin wrapper over `record_decision` taking primitives (so the module stays a stdlib-only leaf), each with a new `kind`/`decision` literal exported as a module constant (the contract downstream aggregation keys on), plus one call site each: (1) **reconcile / `--refresh` drift-gate** (`plan_tool/refresh.py:refresh_plan`) — record the gate verdict per refresh: `no-drift` (the only true fast no-op — early return, zero counts), `drifted` (a scoped reconcile ran), and `no-baseline` (absent/unreadable grounding baseline — this branch runs a **whole-surface reconcile** and returns through the *same* tail as `drifted`, so it carries **real** `findings`/`drifted_files` counts, not zero — it is not a no-op, just a different discriminator, `needs_grounding`, on that shared tail). Record the drifted-file count and findings count; `refresh_plan` already computes `current_code_fp = compute_code_fingerprint(...)` and imports `compute_plan_fingerprint`, so both fingerprints are in hand — this decision is about code-vs-plan drift, so it carries `code_fingerprint`. (2) **`apply_finding` verdicts** (`plan_tool/launcher.py`, where `parse_apply_verdict`'s result is consumed) — record the per-finding verdict (`APPLIED`/`NOT-APPLICABLE`/`BLOCKED`/`BLOCKED-STRUCTURAL`, plus `UNKNOWN` normalized from a `None` parse when Claude ignored the apply contract — the contract-violation case is the most diagnostically interesting for phase-3 aggregation, so it is recorded, not dropped) with the finding `anchor` slug + its `step_id` (folded into `decision_id` so per-step verdicts sharing a second-precision `ts` don't collide) + `plan_fingerprint`. `apply_finding` holds neither the `anchor` nor a hoisted digest (its params are `finding_body` + `step_id`), so both are **threaded in** as defaulted keyword params (`anchor=""`, `plan_fingerprint=""`) by the **per-finding apply loops that own `rec.anchor`** — all four: the review/reconcile apply walk (`cli/review_actions.py`), the serial completeness-apply walk (`cli/completeness_cmd.py`), the `detail` convergence loop (`detail.py:generate_detail`), and the `create` convergence loop (`create.py:create_plan`). Each iterates `rec` objects (so holds `rec.anchor`) and holds `plan_path`/`repo_root`; each computes its `plan_fingerprint` **once before its loop** (ground rule 4) and passes `rec.anchor` + that digest on every `apply_finding` call — so apply verdicts across all four families (review/reconcile, completeness, detail, create) are joinable, not just one. Any non-loop `apply_finding` caller (e.g. a one-shot dispatch) passes the defaults and still records the verdict + `step_id`. `code_fingerprint` is **not** carried here (ground rule 3). **Hoisted-digest semantics (documented tradeoff):** because ground rule 4 hoists the digest above the loop for cost, and `apply_finding` *mutates* the plan when a finding is APPLIED (a structural apply can renumber steps), the `plan_fingerprint` on every verdict after the first is the walk's **entry** snapshot, not the exact plan-state that later finding acted on. It is therefore a **walk-entry coarse anchor** ("the plan-state this apply walk began from"), not a per-decision digest — the correct reading for a phase-3 resolver, which orders events *within* a walk by `run_id`+`ts`. Per-decision precision would require recomputing per finding, the cost ground rule 4 forbids; the coarse anchor is the deliberate choice (see Known limitations). (Note: `decision_id` folds only `step_id`, not `anchor`, so two plan-wide findings resolving to the same next-runnable step in the same second share a `decision_id`; the stored `anchor` is their discriminator — decision_id is a class handle per phase-1, not a unique id, so this is acceptable and not re-litigated here.) (3) **escalate-to-split outcomes** (`plan_tool/launcher.py:escalate_to_split`, or its three callers on the frozen `EscalateResult`) — record `EscalateResult.outcome` (`applied`/`recommended`/`unsafe`/`proposal-unusable`/`step-missing`) with the target `step_id` + `plan_fingerprint`.

**Ground rules.** (1) `telemetry.py` stays a stdlib-only leaf — new recorders take primitives (verdict strings, ids, counts, already-computed fingerprint strings/dicts) exactly as existing wrappers do; callers import and run the compute helpers, the leaf never imports `review_persistence`/`fingerprint`. (2) Best-effort and control-flow-neutral everywhere — `record_decision` already swallows errors; each new call site additionally wraps its fingerprint-compute + record in a local `try/except` that returns/continues on failure (mirroring create.py's `_record_*` helpers), so a fingerprint error never fails an apply/refresh/escalate; no new non-zero exit path, no new operator-visible stdout. (3) Carry `plan_fingerprint` on every site that has a written plan (short digest, renumber-proof anchor). Carry the full `code_fingerprint` path→hash map **only** where the decision is genuinely *about* code state **and** the map is either already in hand or the site fires rarely enough that a fresh hash is bounded: the **drift-gate** (holds `current_code_fp` already) and the **code-reveals-split** detector (a code-grounded built/un-built signal that fires only on the full reconcile lane when `split_recs` is non-empty). It is **not** carried on `record_granularity` / `record_audit_coverage` — those describe plan structure / audit coverage, not code state, don't hold the map in hand (it is computed in a *different* function, `_persist_and_present_report`), and fire **every `--iterate` round**, so carrying it would re-hash the whole footprint and write a full ~code map per line each round (the volume/re-hash cost) — they carry `plan_fingerprint` only. Nor on the per-finding **apply-verdict** site (dozens of per-finding lines × a ~45 KB map is wasteful volume, phase 1's `_MAX_LINE_BYTES` lesson) nor **escalate** (a structure/safety decision) — both `plan_fingerprint` only. The **create** sites are the inverse: no useful `plan_fingerprint` pre-write, so they carry `code_fingerprint` (from the in-memory plan) and leave `plan_fingerprint=""`. Make each per-site choice explicit with its rationale. (4) Hoist fingerprint computation above per-item loops **where a loop exists** — the `apply_finding` apply-verdict site fires once per finding inside the review/reconcile walk's per-`rec` loop, so its `plan_fingerprint` is computed **once by the walk caller before the loop** and threaded in, never recomputed per finding. Escalate is **not** a per-loop hot site (it fires once per structural finding and its seam already re-parses the plan from disk per call, so a per-call compute adds nothing measurable) — it computes `plan_fingerprint` inline, and ground rule 4's hoist requirement is scoped to the apply-verdict loop, not escalate.

## Input

This plan consumes the phase-1 `DecisionEvent` schema and the existing recorder API as fixed contracts it must populate without changing.
- **`DecisionEvent` persisted schema** (`plan_tool/telemetry.py`, documented in `DATA_CONTRACT.md`) — the join-key fields phase 1 added (`decision_id`, `run_id`, `plan_fingerprint`, `code_fingerprint`, `anchor`) plus the base `kind`/`decision`/`ts`/context shape. Phase 2 populates these fields on new events; the tolerant reader already accepts new `kind` values, so no `TELEMETRY_SCHEMA_VERSION` bump is needed.
- **Existing recorder signatures** — `record_create_granularity_assessment`, `record_create_step_outcome`/`_record_step_outcome`, `record_code_reveals_split`, `record_granularity`, `record_audit_coverage`, `record_convergence`, and the base `record_decision`. These already accept defaulted `plan_fingerprint`/`code_fingerprint` params; Part A relies on those defaults' presence to thread digests in without signature changes.
- **Fingerprint compute helpers** — `review_persistence.compute_plan_fingerprint` (reads the plan file) and `fingerprint.compute_code_fingerprint` (hashes the code footprint into a path→hash map). Their return shapes determine what the recorders carry and the line-volume tradeoff.
- **`run` telemetry state** — the `telemetry`-owned `_active_run_id` ContextVar, bound only at the two `run` entrypoints, is depended on to leave `run_id=""` correctly at authoring-time commands.
- **Part-B consumption points** — `parse_apply_verdict`'s result in `plan_tool/launcher.py` (the four verdict tokens), the frozen `EscalateResult.outcome` (five outcome tokens) from `escalate_to_split`, and `refresh_plan`'s already-computed `current_code_fp` + `compute_plan_fingerprint` import in `plan_tool/refresh.py`.

Limit on verifying the contract: this plan reads the recorder signatures and fingerprint helpers at HEAD; if any of those defaulted params or helper return shapes have drifted since the spike, the backfill sites must be re-checked before wiring.

## References

- [contextvars — Context Variables (Python 3.13 Standard Library)](https://docs.python.org/3/library/contextvars.html) — Official reference for ContextVar get/set semantics that back the telemetry-owned `_active_run_id` variable whose value must auto-flow into recorders.
- [JSON Lines](https://jsonlines.org/) — Primary spec for the newline-delimited JSON format used by `decisions.jsonl`, defining the one-object-per-line append contract the recorders emit.
- [hashlib — Secure hashes and message digests (Python 3.13)](https://docs.python.org/3/library/hashlib.html) — Official reference for the digest APIs underlying `compute_plan_fingerprint`/`compute_code_fingerprint`, useful when threading and hoisting fingerprint computation.
- [json — JSON encoder and decoder (Python 3.13)](https://docs.python.org/3/library/json.html) — Standard-library reference for serializing each `DecisionEvent` line and understanding the tolerant reader that must accept new `kind` values without a schema bump.
- [dataclasses — Data Classes (Python 3.13)](https://docs.python.org/3/library/dataclasses.html) — Reference for the dataclass machinery and default-field behavior relevant to the `DecisionEvent` carrying defaulted `plan_fingerprint`/`code_fingerprint`/`anchor` fields.
- [How to mark test functions with attributes — pytest](https://docs.pytest.org/en/stable/how-to/mark.html) — Official pytest guide to custom markers such as `@pytest.mark.integration`, needed to place the new recorder tests under the project's unit-first convention.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- **The resolver / `plan-tool telemetry` analysis-and-recommend surface** — no consumer of the keys ships here; nothing reads the backfilled fingerprints (phase 3).
- **Deriving outcome verdicts** (`acted-on`/`no-op`/`reverted`/`still-open`) — phase 3 correlates decision→outcome; phase 2 only makes the keys exist.
- **Backfilling historical events** — existing events stay as-is; only new events carry the enriched producers. No migration of old data.
- **A `TELEMETRY_SCHEMA_VERSION` bump** — phase 2 adds no base field; the tolerant reader already accepts new `kind` values. Do not bump.
- **Binding `run_id` at non-run commands** — `run_id` means "the run this happened in"; create/detail/completeness/convergence are not runs, so leaving `run_id=""` there is correct, not a gap.
- **Changing `telemetry.py`'s leaf status** — it stays stdlib-only.

## Known limitations (documented, not fixed in phase 2)

These are inherent to backfilling the join keys without new machinery; phase 2 records them honestly rather than papering over them, and a phase-3 resolver must account for them.

- **Greenfield create events are weakly-anchored.** The two create recorders fire pre-`write_new_plan`, so `plan_fingerprint` is not carried (a missing-file digest is a useless constant), and `compute_code_fingerprint` hashes only on-disk files — so a greenfield plan whose steps `create:` new files yields `code_fingerprint == {}`. Such create events carry *no* fingerprint join key and are joinable only by `plan_slug`+`ts`. Acceptable: create-stage decisions are the least outcome-linkable of the families, and the resolver treats a keyless create event as weakly-anchored rather than dropping it.
- **Apply-verdict `plan_fingerprint` is a walk-entry snapshot, not per-decision state.** The hoist (ground rule 4) computes it once before the per-finding loop, but an APPLIED finding can mutate/renumber the plan mid-walk, so later verdicts carry the walk's entry digest. It is a coarse "plan-state the walk began from" anchor; a phase-3 resolver orders within-walk events by `run_id`+`ts` rather than treating each verdict's digest as its own plan-state. Per-decision digests would need the per-finding recompute the cost rule forbids.
- **Large-footprint drift-gate / code-reveals-split events can be silently dropped.** The full `code_fingerprint` map pushes those lines toward the 64 KB `_MAX_LINE_BYTES` cap `record_decision` enforces; on a very-large-grounding plan the event exceeds the cap and is dropped with no signal. Accepted for phase 2 (normal plans are well under the cap). Phase-3 hardening candidates: a dropped-event counter so loss is visible, or scoping the drift-gate's map to just `drifted_files` rather than the whole footprint. See the Risks entry.
- **Backend-invocation-failure applies emit no `apply-verdict` event.** An apply whose backend invocation exits non-zero returns from `apply_finding` *before* the `parse_apply_verdict` line, so it records nothing here. No signal is lost — the failure is captured in the **run-log** (`outcome=error`/`rc`), joinable to the same apply by `run_id` (matching the spike's "outcomes ride the existing run-log" architecture). Consequence: a recorded `apply-verdict` `UNKNOWN` means *only* "apply ran (exit 0) but Claude emitted no verdict token" (contract violation), never a crash. Giving invocation failures their own verdict token so the apply-outcome distribution is complete from one family is a phase-3 enhancement.
- **`completeness-apply --jobs N` (parallel) apply-verdicts are not reliably captured.** The apply-verdict event is written inside `apply_finding` to `repo_root/.plan-tool/telemetry/decisions.jsonl`. The parallel apply worker (`cli/completeness_apply_parallel.py`) runs `apply_finding` in an **isolated git worktree** whose only replay onto the canonical tree is captured *content* changes — so a worker's telemetry write either lands in the discarded worktree (lost) or, for a canonical-tree conflict rerun, reaches the canonical log **unkeyed** (empty `anchor`/`plan_fingerprint`, since that non-loop caller was not threaded). Per-finding apply-verdicts are therefore reliable only in **serial** (`--jobs 1`, the default and the interactive walk). Routing the worker's telemetry to the canonical `repo_root` and threading its keys is a bounded phase-3 hardening item, out of scope for this backfill slice.

## Risks

- **Leaf-purity regression** — the seductive wrong move is importing a fingerprint producer into `telemetry.py`. Severity: high (breaks the module's contract). Mitigation: fingerprints are caller-supplied; keep the stdlib-only import test green (`grep -E '^(from|import) plan_tool' plan_tool/telemetry.py` stays empty).
- **Control-flow / exit-code perturbation** — a recorder or fingerprint-compute throwing at the apply/refresh/escalate site must not fail that operation. Severity: high. Mitigation: best-effort try/except at every new site plus the existing swallow in `record_decision`; a test that a raising `compute_*`/record leaves the host command's rc and output unchanged.
- **Line-volume / cost at hot sites** — per-finding apply verdicts × a big `code_fingerprint` map would bloat the log and re-hash the footprint each finding. Severity: medium. Mitigation: `plan_fingerprint`-only on the per-finding site + hoist the compute above the loop (design decisions 3–4).
- **Silent schema drift** — DATA_CONTRACT + drift guard must move with the new `kind` families' context shapes. Severity: medium. Mitigation: update `DATA_CONTRACT.md` and `tests/test_data_contract.py` together.
- **`decision_id` collision on per-step verdicts** — many `apply_finding` verdicts can share a second-precision `ts`. Severity: medium. Mitigation: fold `step_id` into the hash (as `create-step-outcome` already does) so distinct per-step verdicts stay distinguishable.
- **`_MAX_LINE_BYTES` silent drop on the `code_fingerprint`-carrying sites** — `record_decision` silently drops any event whose serialized line exceeds 64 KB (`telemetry.py`: `if len(line) > _MAX_LINE_BYTES: return`), and the full `code_fingerprint` path→hash map is the largest variable field (the `record_plan_criteria_breakdown` docstring already warns a big map "could drop the whole event on a large-grounding plan"). The two sites that carry the full map — the **drift-gate** (every verdict, incl. the hot `no-drift`) and **code-reveals-split** — can therefore silently lose events on a very-large-footprint plan, exactly where the drift-gate's observability matters most, with no signal that events were dropped. Severity: medium. Mitigation for phase 2: **documented, accepted** — normal-size plans record fine; single-homing the map (no dual-home, as phase-1's PR #11 established) keeps the line as small as the map allows; a dropped-event counter / map-scoping to `drifted_files` is a phase-3 hardening item (see Known limitations). This is the reason the map is **not** spread to the every-round `record_granularity`/`record_audit_coverage` sites.

## Testing

Follow the project's unit-first convention (mirror `plan_tool/X.py` → `tests/test_X.py`; add `@pytest.mark.integration` only for cross-module CLI/orchestrator drives). Coverage the plan must land:
- **Part A backfill** — tests assert the fingerprints now land on recorded events at each of the six call sites (create ×2, code-reveals-split, granularity[completeness], audit-coverage, convergence), and that `record_prompt_budget` stays fingerprint-less.
- **Drift-gate recorder** — each of `no-baseline` / `no-drift` / `drifted` records the right verdict + drifted-file/findings counts + `code_fingerprint` on every verdict; `plan_fingerprint` on `no-baseline`/`drifted` and `plan_fingerprint==""` on the hot `no-drift` path.
- **Apply-verdict recorder** — tests over the five verdict tokens (`APPLIED`/`NOT-APPLICABLE`/`BLOCKED`/`BLOCKED-STRUCTURAL`/`UNKNOWN`) asserting anchor + step_id + `plan_fingerprint` land and no `code_fingerprint` is carried; a test that the walk caller threads `rec.anchor` and a once-computed digest through `apply_finding` (default `anchor=""` for the other callers); a test that distinct per-step verdicts sharing a `ts` stay distinguishable via the folded `step_id`.
- **Escalate-to-split recorder** — tests over the five outcomes (`applied`/`recommended`/`unsafe`/`proposal-unusable`/`step-missing`) asserting outcome + step_id + `plan_fingerprint`.
- **Best-effort invariant** — a forced failure in `compute_*`/`record_*` leaves the host command's exit code and stdout unchanged (test-proven for at least the apply and refresh sites).
- **Leaf purity** — the stdlib-only import test for `telemetry.py` stays green.
- **Drift guard** — `tests/test_data_contract.py` stays green with the three new `kind` families documented.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — unit tests added with the implementation; green before completion.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (feature) — unit tests added with the implementation; green before completion.
- step 5 (feature) — unit tests added with the implementation; green before completion.
- step 6 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- A newly recorded event at each of the four on-disk backfilled call sites (code-reveals-split, granularity[completeness], audit-coverage, convergence) carries a `plan_fingerprint` that **equals `compute_plan_fingerprint(<the real on-disk plan path>)`** — asserting equality to the actual plan's digest, **not** mere non-emptiness (a missing/wrong path also yields a stable non-empty digest, so a non-empty-only check is weakly falsifiable and would pass on the wrong path); `code_fingerprint` is additionally carried **only** on code-reveals-split (not on granularity[completeness]/audit-coverage, which are `plan_fingerprint`-only to avoid the per-round re-hash). The two create sites — which fire before the plan file is written — carry `code_fingerprint` (from the in-memory plan) and leave `plan_fingerprint=""`; for a greenfield plan whose files don't yet exist the map is `{}` (a documented weak-anchor limitation). `record_prompt_budget` stays fingerprint-less.
- Three new decision families record: a drift-gate verdict (`no-baseline`/`no-drift`/`drifted`) with `code_fingerprint` on every verdict and `plan_fingerprint` on `no-baseline`/`drifted` only (**skipped on the hot `no-drift` path** — `no-drift` carries `code_fingerprint` + `plan_fingerprint==""`) plus counts; a per-finding apply verdict (`APPLIED`/`NOT-APPLICABLE`/`BLOCKED`/`BLOCKED-STRUCTURAL`/`UNKNOWN`) with anchor + step_id + `plan_fingerprint` (anchor and the digest threaded in from the walk caller; digest computed once above the per-finding loop); and an escalate-to-split outcome (`applied`/`recommended`/`unsafe`/`proposal-unusable`/`step-missing`) with step_id + `plan_fingerprint`.
- Every new/changed call site is best-effort: a forced failure in `compute_*`/`record_*` leaves the host command's exit code and stdout unchanged (test-proven for at least the apply and refresh sites).
- `telemetry.py` imports nothing first-party (leaf test green); no `TELEMETRY_SCHEMA_VERSION` bump; the per-finding apply site carries no full `code_fingerprint` map; fingerprint compute is hoisted above per-finding loops.
- `DATA_CONTRACT.md` documents the three new `kind` families with the drift guard green; the change ships no resolver/analysis/read surface.
- **BACKLOG #72 is updated** in the plan's final step: phase-2 backfill + new sites marked shipped, phase 3 (resolver + `plan-tool telemetry` surface + outcome-verdict derivation) left as remaining scope, provenance cited via the **tracked, durable** plan docs (`docs/implementation-plans/2-telemetry-linkage-backfill.md`, `2-telemetry-linkage-schema.md`) — **not** the gitignored `.tmp/` spike path, which would dangle when the scratch is cleaned.

## Deferred

- **Full `code_fingerprint` map on the per-finding apply-verdict site** — carrying `plan_fingerprint` only to avoid the per-line volume/re-hash cost (design decision 3); revisit if phase 3's resolver needs per-finding code state.
- **Recording escalate-to-split from each of the three callers separately** — postponed in favor of a single record at the `escalate_to_split` seam; revisit if a caller needs context the seam can't see.
