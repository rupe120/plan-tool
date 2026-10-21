> **Auto-archived**: this plan was swept on 2026-07-07 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Make the re-ground finding emit a distinct, parseable suggested action

## Summary

Reconcile's code-grounded re-ground finding (`plan_tool/review.py:_reground_already_built_recommendation`) reuses the shared `granularity-merge` source token, so a consumer can't read off which steps it targets without parsing human prose. This step adds a small, single-owned machine directive grammar in `plan_tool/review.py` — a `reground` kind constant, one builder that renders a directive marker, and one parser that recovers `(kind, step_ids)` from a finding — then makes the re-ground producer append its directive to `suggested_action`. The grammar is **kind-carrying** (it also defines the `merge` kind and can parse it), so the deferred merge bridge follow-up extends it without rework; this step wires **only** the re-ground producer — the merge producer edit ships with that follow-up, not here (merge bridge is deferred; see the plan Deferred section). The key design decision: the grammar lives in `review.py` (the module step 5's walk imports; `review` must never import `granularity`), and the finding ids/fingerprints stay unchanged (only the `suggested_action` string grows). On green, a re-ground finding's target step ids can be read off without parsing human prose, and a re-ground finding never misclassifies as `merge` despite its merge-mentioning prose — which is exactly what step 5 (`depends_on: 4`) needs to route the finding to the re-ground bridge.

## Table of Contents

- [Summary](#summary) — what the step adds and the result on green.
- [Table of Contents](#table-of-contents) — this list.
- [Why](#why) — the unreadable-target-ids ambiguity this closes for step 5.
- [Files (creates vs edits)](#files-creates-vs-edits) — the two in-scope files and their edits.
- [Implementation](#implementation) — the grammar owner, the builder/parser pair, the re-ground producer edit, and the invariants.
- [Tests](#tests) — the parser round-trip and producer cases to add.
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors.
- [References](#references) — frozen dataclasses, regex.
- [Deferred](#deferred) — out-of-scope follow-ups.

## Why

`plan_tool/review.py:STRUCTURAL_SOURCES` and the `triage_reason` branch already keep the `granularity-merge` producers on the neutral, producer-agnostic path so neither gets sent to the split bridge. But that same neutrality is now a problem: step 5's walk must send the **re-ground** finding to step 3's `reground_bridge` (mark-done / re-baseline) — a remedy the plan's risk section says must **never** be conflated with a structural merge. The re-ground finding sets `step_id=None` and hides the id set in its fingerprint, so it carries the target ids nowhere a consumer can read them: `_make_rec_id` hashes the fingerprint, so the split-side trick of re-deriving the key by recomputing candidate ids (`granularity.py:split_predicate_key`) does not generalize to a variable-length re-ground id set. This step closes the gap by carrying the kind and the ids in a small parseable directive on `suggested_action` — the re-ground analog of step 1's `split_predicate_key`. It adds only a recovery vocabulary; it changes no detection, mints no new source token, and adds no field to `review.Recommendation`.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/review.py` — add the kind constants (`merge` / `reground`), a frozen result carrying `(kind, step_ids)`, the `render_merge_action` builder, and the `parse_merge_action` parser; place them near the existing `_GRANULARITY_MERGE_SOURCE` constant and `triage_reason`. Update `_reground_already_built_recommendation` to append the `reground` directive to its `suggested_action`.
  - `tests/test_review.py` — add cases proving the re-ground finding carries a `reground` directive with its full id set, plus the parser round-trip and the merge-vs-reground discrimination.

## Implementation

- **What changes.** Give the re-ground producer a machine-parseable directive that names the remedy kind (`reground`) and the target step ids, and add one parser that recovers it. Nothing about *detection* changes — the same finding fires on the same inputs; only its `suggested_action` string grows a directive, and a new recovery helper reads it back.

- **Put the grammar in `plan_tool/review.py`, one owner for builder and parser.** `review` must **not** import `granularity` (that reverse cycle is why `_GRANULARITY_MERGE_SOURCE` is a duplicated literal, not an import). So the directive builder must live where the producer and step 5's consumers can reach it without a cycle — that is `review.py`. `_reground_already_built_recommendation` (in `review.py`) calls it directly; step 5's `review_walk.py` imports the parser from `review.py`. This is the same reasoning that placed `_GRANULARITY_MERGE_SOURCE` in `review.py`.

- **Add two kind constants and a frozen result.** One way:
  - `MERGE_ACTION_MERGE = "merge"` and `MERGE_ACTION_REGROUND = "reground"`. Both are public and stable-valued; `MERGE_ACTION_REGROUND` is what this step's producer and step 5 key on. `MERGE_ACTION_MERGE` is kept as forward-compatible vocabulary so the deferred merge bridge follow-up can wire its producer without reworking the grammar, and so the parser's discrimination guard (below) is a real, testable property; **no producer in this plan emits a `merge` directive.** The naming carries "merge" because the grammar keys on the shared **`granularity-merge` source token** — not the merge remedy.
  - A frozen `MergeAction` dataclass with `kind: str` and `step_ids: tuple[int, ...]`, matching the frozen-result style already used across the codebase (`ScopeOutResult`, `EscalateResult`). This is an **in-memory** classification result, not a persisted shape — do not touch `DATA_CONTRACT.md` (see Deferred).

- **Single-source the directive grammar so the producer and the parser can't drift.** Add one builder — one way `render_merge_action(kind: str, step_ids) -> str` — that returns a stable marker such as `→ reground steps: 3, 4, 5`. The producer appends the builder's output to its own prose; the parser reverses only the builder's marker. This mirrors how `granularity.py:_STRUCTURAL_BLOCK_RE` is single-sourced and imported back so a strip consumer and a parse kernel can't fork into two copies.

- **`render_merge_action` returns the marker; the producer keeps its human prose.** The walk prints `suggested_action` to the operator (`review.py`'s report render loop does `print(f"      {rec.suggested_action}")`), so the string must stay readable. Append the marker to the existing prose rather than replacing it:
  - `_reground_already_built_recommendation`: keep its re-baseline prose, then append the `reground` marker carrying the full `step_ids` set it already computes.

- **`parse_merge_action(rec) -> Optional[MergeAction]` keys on the marker, never the prose.** Rules:
  - Return `None` when `rec.source != _GRANULARITY_MERGE_SOURCE` — only `granularity-merge` producers are in scope.
  - Return `None` when `rec.suggested_action` is `None` or carries no well-formed marker (defensive; a well-formed producer always emits one).
  - Otherwise regex the **first** directive marker — one option: `→\s*(merge|reground)\s+steps:\s*([0-9,\s]+)` — take `kind` from group 1 and parse the id list from group 2 into a sorted `tuple[int, ...]`.
  - **Gotcha — the discriminator is the marker kind, not the prose.** The re-ground finding's prose deliberately mentions `merge` and `plan-tool merge` (it tells the operator to merge *only if* the set is contiguous). The parser must not see that word and misclassify. Because it anchors on the exact `→ (merge|reground) steps:` marker and the re-ground producer emits `kind=reground`, a re-ground finding always classifies as `reground` and never as `merge`. This is what keeps step 5 from routing a re-ground finding to a merge bridge — the plan's "Conflating re-ground with structural merge" risk, resolved at the source.

- **Invariant — ids and fingerprints must not change.** `_make_rec_id` hashes `(step_id, source, fingerprint)`; `suggested_action` is not part of it. Appending the marker changes only the displayed/persisted `suggested_action` string, so every existing id stays stable (`tests/test_review.py:test_reground_id_stable_for_same_set` stays green). Do **not** fold the directive into the fingerprint.

- **Foundational logic and where else it lives.** The core rule this step adds is "recover `(remedy kind, target step ids)` from a `granularity-merge` finding." The one parallel is the split side's `granularity.py:split_predicate_key` (recovers a split predicate key by re-deriving `_make_rec_id`). That is a **different recovery path** for a different source (`granularity-split`) and stays as-is — do not try to unify the two, and do not route through `split_predicate_key`. The `granularity-merge` producers are a closed set (`review.py`'s comment on `_GRANULARITY_MERGE_SOURCE` documents both); only the re-ground member is wired here, and the deterministic `granularity.py:_merge_rec` producer stays untouched (its directive wiring is the deferred merge bridge follow-up).

## Tests

### Test-creation order (feature step)

This is a **feature** step. Add every test below **with** the implementation; each must be green before the step is done.

`tests/test_review.py` (extend `TestRegroundBuilder` / add `TestMergeActionGrammar`):
- `test_reground_suggested_action_carries_reground_directive` — the re-ground finding parses to `kind=reground`.
- `test_reground_directive_carries_full_id_set` — the parsed `step_ids` equal the full distinct already-built set (e.g. `(3, 4, 5)`), sorted.
- `test_reground_directive_kind_is_reground_despite_merge_prose` — even though the prose says `merge` / `plan-tool merge`, the parsed kind is `reground` (never `merge`).
- `test_parse_merge_action_returns_none_for_non_merge_source` — a non-`granularity-merge` rec (e.g. a `deps` or `heuristic` rec) parses to `None`.
- `test_parse_merge_action_returns_none_without_marker` — a `granularity-merge`-sourced rec whose `suggested_action` has no marker parses to `None`.
- `test_reground_directive_does_not_change_rec_id` — adding the directive leaves the id stable (guards the fingerprint invariant alongside `test_reground_id_stable_for_same_set`).
- `test_merge_action_constants_pin_values` — `MERGE_ACTION_MERGE == "merge"` and `MERGE_ACTION_REGROUND == "reground"` (stable-value pin, mirroring `test_split_predicate_constants_pin_existing_values`).
- `test_render_parse_round_trip_for_reground` — `render_merge_action(MERGE_ACTION_REGROUND, (3, 4, 5))` embedded in prose parses back to `kind=reground`, `step_ids=(3, 4, 5)`.

Green-before-done gate: run `uv run pytest tests/test_review.py -q`; all new and existing cases pass. Confirm the pre-existing `test_reground_builder_emits_for_two_distinct_steps` (asserts `re-baseline` and `merge` appear in `suggested_action`) still passes — the change appends to that prose, it does not replace it.

## Acceptance criteria

- `parse_merge_action` returns a `MergeAction` with `kind == "reground"` and `step_ids` equal to the full distinct already-built set for a `_reground_already_built_recommendation` finding.
- `parse_merge_action` returns `None` for any rec whose `source` is not `granularity-merge`, and for a `granularity-merge` rec whose `suggested_action` carries no directive marker.
- The re-ground finding always classifies as `kind == "reground"` and never `"merge"`, even though its prose mentions `merge`.
- The `id` of every re-ground finding is unchanged from before this step (marker is not part of the fingerprint).
- `render_merge_action` is the only place the directive marker is written; the re-ground producer calls it.
- The deterministic `granularity.py:_merge_rec` producer is not edited in this step — its directive wiring ships with the deferred merge bridge follow-up.
- No new `review.Recommendation` source token, no new field on `review.Recommendation`, and no `DATA_CONTRACT.md` change.
- `uv run pytest tests/test_review.py -q` is green.

## References

- [dataclasses — Data Classes (frozen=True)](https://docs.python.org/3/library/dataclasses.html) — the frozen-result pattern for `MergeAction`, matching `ScopeOutResult` / `EscalateResult`.
- [re — Regular expression operations](https://docs.python.org/3/library/re.html) — for the directive-marker parser; anchor on the exact `→ (merge|reground) steps:` shape.

## Deferred

- **The merge producer directive edit** — wiring `granularity.py:_merge_rec` to append a `merge` directive ships with the deferred merge bridge follow-up (plan Deferred: the whole merge bridge — executor, this producer edit, and step 5 dispatch — waits for a walk-surfaced pairwise-merge producer). This step ships the kind-carrying grammar so that follow-up needs no grammar rework, and wires only the re-ground producer.
- **Wiring the walk to dispatch on the directive** — step 5 (`depends_on: 4`) imports `parse_merge_action` / `MERGE_ACTION_REGROUND` and routes re-ground findings to step 3's `reground_bridge`. Step 4 ships only the parseable directive and its recovery helper.
- **`DATA_CONTRACT.md` update** — `MergeAction` is an in-memory classification result, never serialized; `suggested_action` is already documented generically as "follow-up command/check, or None", and its field shape is unchanged. No drift-guard obligation attaches here.
- **Unifying with the split-side recovery** — `granularity.py:split_predicate_key` (for `granularity-split`) stays a separate path; merging the two recovery helpers is not in scope and has no motivating need.
