> **Auto-archived**: this plan was swept on 2026-07-08 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Add the `target_signature` field and a `compute_target_signature` helper

## Summary

Adds the two building blocks the rest of the plan needs: a new `target_signature: Optional[str] = None` field on the `Recommendation` dataclass (`plan_tool/review.py`), and a pure helper `compute_target_signature(plan, target_ids) -> str` (`plan_tool/review_walk.py`) that hashes each target step id paired with its current title and change_type into one SHA-256 digest. The key decision is what the signature covers: the ordered `(id → title + change_type)` identity of just the directive's own target steps, **not** step bodies or the whole plan — so a renumber that makes a target id name a different step trips it, but an unrelated edit elsewhere does not (with the accepted same-title+change_type collision under-fire caught by the bridge's own target re-validation, not the signature). This step only defines and documents the field and helper; nothing stamps or reads them yet (steps 2–4). On green, `Recommendation` carries the new `None`-default field, it round-trips through the saved sidecar unchanged, `DATA_CONTRACT.md` documents it, and the helper returns a stable digest for a given plan + id set.

## Table of Contents

- [Why](#why) — what the coarse guard gets wrong and why these two pieces come first
- [Files (creates vs edits)](#files-creates-vs-edits) — the field, the helper, the doc, the tests
- [Implementation](#implementation) — the field, the helper's contract, and the gotchas
- [Tests](#tests) — helper unit cases and the round-trip/data-contract checks
- [Acceptance criteria](#acceptance-criteria) — observable results on green
- [References](#references) — stdlib docs for the field and the hash
- [Deferred](#deferred) — stamping, guard rewrite, split guard, backlog

## Why

The structural-remedy walk guards against applying a **stale saved directive** — a re-ground / merge finding whose saved step ids may now name different steps after a plan edit — with a **coarse whole-plan fingerprint** in `_saved_directive_is_stale` (`plan_tool/cli/review_actions.py`). It over-fires: in a mixed-finding walk, applying any earlier finding rewrites the plan file, so a later re-ground/merge directive is downgraded to recommend-only even though **its own target ids are still valid**. That makes `--apply-structural` a no-op for those remedies in any mixed walk. Fixing it needs a per-directive signature keyed on the directive's actual targets. This step lands the two shared pieces every later step depends on — the persisted field and the hashing helper — before anything stamps recs (step 2) or rewrites the guard (steps 3–4).

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/review.py` — add `target_signature: Optional[str] = None` to the `Recommendation` dataclass (`review.py`, the `class Recommendation` frozen dataclass), placed with the other optional trailing fields (`file_path`, `anchor`) so existing positional construction is unaffected. Add a short field comment matching the terse style of the neighbors.
  - `plan_tool/review_walk.py` — add the `compute_target_signature(plan, target_ids) -> str` helper. Add the imports it needs (`hashlib`; `Plan` from `plan_tool.schema`; `Iterable` from `typing`, which currently imports only `Callable, Optional`).
  - `DATA_CONTRACT.md` — add one row for `target_signature` to the `### Recommendation (review.py)` field table.
  - `tests/test_review_walk.py` — unit tests for the helper.

## Implementation

**Add the field to `Recommendation` (`plan_tool/review.py`).**
- Add `target_signature: Optional[str] = None` alongside the existing optional trailing fields on the frozen `Recommendation` dataclass. Order after `anchor` is fine — all callers construct with keywords, and a trailing default keeps positional construction working.
- `None` means **unknown** — legacy sidecars, non-directive recs, and any rec never stamped. Later steps' guard reads `None` as "fall back to the coarse whole-plan check", so nothing regresses.
- **It round-trips automatically.** `plan_tool/review_persistence.py` serializes recs with `asdict(r)` in both `save_review` and `update_annotation`, and rebuilds with `Recommendation(**r)` in `load_review`. Because both paths use `asdict`, the new field is written on save **and** preserved when the first annotation is written — no hand-built payload to update. Confirm this rather than adding plumbing; `review_persistence.py` is not in this step's scope and does not need editing.

**Add the helper (`plan_tool/review_walk.py`).** Target contract:

- **Signature:** `compute_target_signature(plan: Plan, target_ids: Iterable[int]) -> str`. Returns a hex digest string.
- **What it hashes:** the ordered `(id → title + change_type)` triples for each target id, resolved against `plan`. Look each id up in `plan` (the `Plan.step_by_id` method exists but **raises `KeyError` for a missing id** — see the gotcha below; iterating `plan.steps` into an `{id: (title, change_type)}` map and using `.get` is one clean way to avoid the raise). Include `change_type` (the `ChangeType` enum value) alongside `title`: it is a second stable identity dimension that makes a same-title collision (see below) require *also* a same change_type, materially rarer.
- **Not a content hash.** Hash only the id→(title, change_type) identity, never step bodies or detail files — hashing bodies would over-fire on any body edit and reintroduce the coarse guard's problem at step granularity. There is no per-step uuid (ids are positional), so title+change_type is the strongest stable plan-content identity available. **Two accepted failure directions, both low-severity:** (1) a deliberate title/change_type *rename* of a target over-fires to recommend-only (safe, rare); (2) a renumber aligning a *same-title + same-change_type* step onto a target id *under*-fires (signature matches, guard says fresh) — but this is **not** a silent wrong mutation, because the bridge re-validates its own target (`reground_bridge` confirms already-built, `merge_bridge` confirms mergeable/pending, `escalate_to_split`/`split_is_safe` re-parse and re-check) and refuses a wrong target. The signature is *precision*; the bridge is *safety*. Do not describe the guard as "unconditionally safe."
- **SHA-256 primitive, not the file hasher.** Use `hashlib.sha256(...).hexdigest()` on an encoded, delimited string of the triples — the same SHA-256 choice `plan_tool/drift_detection.py:compute_content_hash` makes. Do **not** call `compute_content_hash` itself: it hashes **file bytes** from a `Path` and can't hash an in-memory string. Build one canonical string (e.g. join `f"{id}\x1f{title}\x1f{change_type}"` triples with a separator) and hash it once.

Gotchas that are **not** free to vary:

- **Missing / renumbered-away id must not raise and must be distinguishable.** If a target id no longer names any step (deleted or shifted past the end), the helper must return a digest, not blow up — and a missing id must produce a **different** digest than a present one. Use a distinct sentinel for the absent title (something a real title can't collide with), not silent omission and not an empty string.
- **Order must be deterministic for the same id set.** The guard (step 3) recomputes the signature later and compares for equality, so the same ids must always hash the same way regardless of caller order. One way: sort `target_ids` to a canonical order inside the helper before hashing (matching how `plan_tool/review.py:parse_merge_action` already returns a sorted `step_ids` tuple). Dedupe defensively if you sort.
- **Pure, no shell-out, no `invoker`.** The helper reads only plan structure — it is deterministic and must never touch a backend seam.
- **Import direction.** `plan_tool/review_walk.py` already imports from `plan_tool.review` and `plan_tool.granularity`; adding `from plan_tool.schema import Plan`, `import hashlib`, and `Iterable` to the existing `from typing import ...` (currently `Callable, Optional`) keeps it a leaf below `review_actions.py` (which imports from both `review` and `review_walk`, so step 3's guard can reach the helper). Do not import anything from `plan_tool.cli` into `review_walk.py`.

**Why the helper lives in `review_walk.py`, not `review.py`.** The field belongs with the `Recommendation` definition in `review.py`; the helper belongs in `review_walk.py` so its unit tests sit in `tests/test_review_walk.py` (this step's declared test file) and every later consumer — the step-2 stamp call sites and the step-3/4 guard — can import it from the same leaf. It is a pure function of `Plan` + ids, so either module would work mechanically; the test-file placement is what settles it here.

**Foundational logic and where else it lives.** The core rule this step adds is *"a directive's freshness is the identity of its own target steps."* The existing freshness rule it will eventually replace is the coarse whole-plan comparison in `plan_tool/cli/review_actions.py:_saved_directive_is_stale` (keyed on `saved_plan_fingerprint` vs `compute_plan_fingerprint`). A **separate, parallel** staleness rule lives in `plan_tool/cli/convergence_cmd.py` (`classify_report_staleness`, keyed on convergence-history `plan_fingerprint` with a single `rec.step_focus` target) — it is a different contract and is **out of scope**; see Deferred. Do not consolidate the two here.

## Tests

Add to `tests/test_review_walk.py`. Build small `Plan` objects with the existing schema (a couple of `Step`s with explicit `id`/`title`); no backend, so no `@pytest.mark.allow_real_claude` and the conftest gate stays untouched.

- `test_compute_target_signature_stable_for_same_plan_and_ids` — same plan + same id set returns the identical digest across two calls.
- `test_compute_target_signature_changes_when_target_title_changes` — editing a target step's title changes the digest (the renumber case the guard will catch).
- `test_compute_target_signature_ignores_non_target_edits` — editing a step **not** in `target_ids` (title or body) leaves the digest unchanged (the over-fire this plan removes).
- `test_compute_target_signature_order_independent` — the same ids passed in different order produce the same digest.
- `test_compute_target_signature_missing_id_does_not_raise` — a target id absent from the plan returns a digest and does not raise `KeyError`.
- `test_compute_target_signature_missing_id_distinct_from_present` — a missing id yields a different digest than the same id when it names a real step.
- `test_recommendation_target_signature_round_trips` — a `Recommendation` with `target_signature` set survives `save_review` → `load_review` (and stays set after an `update_annotation` write) with the value intact; `None` stays `None`.

Data-contract suite (already exists; must stay green once the field is documented in `DATA_CONTRACT.md`):
- `tests/test_data_contract.py::test_contract_registry_discovers_dataclass_fields` — the new field is discovered and documented.
- `tests/test_data_contract.py::test_every_persisted_field_is_documented_in_own_section` — `target_signature` has a row in the `Recommendation` section.
- `tests/test_data_contract.py::test_update_annotation_preserves_saved_review_contract_keys` — the field survives the annotation-write path.

### Test-creation order (feature step)

This is a **feature** step. Add the helper unit tests in `tests/test_review_walk.py` **with** the helper, and add the round-trip test with the field. Run the data-contract suite after documenting the field in `DATA_CONTRACT.md`. Green-before-done gate: every new test above, plus the three named data-contract tests, must pass before this step is finished.

## Acceptance criteria

- `Recommendation` has a `target_signature: Optional[str] = None` field; constructing `Recommendation(...)` without it still works and defaults to `None`.
- A `Recommendation` with `target_signature` set round-trips through `save_review` → `load_review` and survives an `update_annotation` write with the value unchanged; `None` stays `None`.
- `compute_target_signature(plan, target_ids)` returns a stable hex digest; the digest changes when a target step's title changes and stays the same when a non-target step is edited.
- `compute_target_signature` is order-independent for the same id set and does not raise on an id absent from the plan (and a missing id yields a distinct digest from a present one).
- `DATA_CONTRACT.md`'s `Recommendation` table documents `target_signature`.
- `tests/test_review_walk.py` new cases and `tests/test_data_contract.py` (`test_contract_registry_discovers_dataclass_fields`, `test_every_persisted_field_is_documented_in_own_section`, `test_update_annotation_preserves_saved_review_contract_keys`) all pass.

## References

- [dataclasses — Data Classes (Python Standard Library)](https://docs.python.org/3/library/dataclasses.html) — adding a field with a default (`target_signature: Optional[str] = None`) on a frozen dataclass and the `asdict()` / `Recommendation(**r)` round-trip the sidecar relies on.
- [hashlib — Secure hashes and message digests (Python Standard Library)](https://docs.python.org/3/library/hashlib.html) — the `sha256().hexdigest()` primitive the helper uses to hash the ordered `(id → title)` pairs.
- [typing — Optional](https://docs.python.org/3/library/typing.html#typing.Optional) — the `Optional[str]` annotation and its `None` (legacy/unknown) sentinel meaning for the field.

## Deferred

- **Stamping `target_signature` onto directive recs** — step 2 walks recs after the audit and stamps the re-ground, pairwise-merge, and `granularity-split` findings via a shared post-audit pass; this step only defines the field and helper.
- **Rewriting `_saved_directive_is_stale`** to the per-directive check with the coarse fallback — step 3 (`plan_tool/cli/review_actions.py`).
- **Guarding the `granularity-split` escalation** with the same precise check — step 4.
- **`BACKLOG.md` #93 reconciliation** — step 5.
- **`convergence_cmd.py`'s `classify_report_staleness`** single-carve/single-split staleness — a separate contract; generalizing the precise idea there is a possible future follow-up, not this plan.
- **Title-rename over-fire** — a deliberate rename of a target step will downgrade its directive to recommend-only; accepted as safe and rare rather than pursuing a stable per-step identity that does not exist today.
