> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 8 — Make the completeness audit's deterministic detectors individually dispatchable (behavior-preserving)

## Summary

Restructure the completeness audit's deterministic battery so every detector it runs is reachable **through one registry** rather than through hard-coded call sites — with **no behavior change at all**. Today `_run_deterministic_checks` makes thirteen direct calls, two of which (`collect_smell_findings`, `_self_consistency_from_smells`) are fan-outs that call five and one further detectors inside themselves. That shape is why a per-detector policy cannot be applied: you cannot admit or skip `detect_suppression_shape` without either splitting the fan-out or dropping its grade-independent siblings with it. This step splits those fan-outs behind a registry and routes the battery through it; the registry has **one policy — run everything** — so output is byte-for-byte identical. Step 9 then adds the grade axis as a policy over the same registry. The key design decision: **the closure guarantee is a source-level guard, not a reachability assertion.** A test that says "a check reachable from the battery must be registered" is vacuous once unregistered checks are unreachable; instead a test parses the battery and the two fan-outs for detector calls made *outside* the registry dispatch and fails if any exist, so adding a detector without registering it breaks the build. On green, characterization tests pinned before the change pass unchanged, the full suite is green, and no command behaves differently.

## Table of Contents

- [Summary](#summary) — what the refactor does and the one design decision
- [Why](#why) — why step 9 is unbuildable without this, and why it must be its own step
- [Input](#input) — the exact call structure at HEAD this refactor must preserve
- [Files (creates vs edits)](#files-creates-vs-edits) — per-file edits; no new files
- [Implementation](#implementation) — the registry, the fan-out split, and the closure guard
- [Tests](#tests) — characterization first, then the guard
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes on green
- [References](#references) — the references relevant to this step
- [Deferred](#deferred) — the grade axis and everything downstream

## Why

Step 9 needs to run a different subset of deterministic detectors per grade. At HEAD it cannot: the battery's detectors are not individually addressable, and the two fan-outs mix grade-independent and run-grade-only detectors in the same call. Any attempt to make the battery grade-aware *in place* runs into the plan's own fence — skipping a whole fan-out to skip one detector drops grade-independent checks with it, which Out of scope forbids ("Weakening audit checks in any form"). That is not a prose gap; it is a structural precondition, and this plan's audit rounds kept re-deriving it because the precondition was never a step.

So this repeats the shape the plan already used successfully at its start: **step 1 extracted a shared leaf as a pure refactor and step 2 built the small feature on it.** This step is that extraction for the battery; step 9 is the feature. Keeping them apart is what lets the refactor be proven behavior-preserving by characterization tests — a guarantee that becomes impossible to state once new behavior rides along.

Note this step touches the audit's *plumbing*, not its judgment. No finding, source, severity, threshold, or blocking rule changes; the same detectors run on the same inputs in the same order and produce the same records. The fence amendment authorizing it is recorded in the plan body's Out of scope.

## Input

**The battery's call structure at HEAD** (verified; re-verify before implementing — this is the surface the refactor reshapes):

- `plan_tool/cli/completeness_phases.py:_run_deterministic_checks` calls directly: `check_file_existence`, `detect_path_style_mismatch`, `validate_deps`, `check_body_completeness`, `check_detail_coverage`, `check_detail_body_completeness`, `check_files_coherence`, `check_lessons_coverage`, `assess_granularity`, `collect_smell_findings`, `_collect_data_contract_drift`, `check_input_contract_references`, and `_self_consistency_from_smells`.
- `plan_tool/review.py:collect_smell_findings` fans out to `validate_feature_refs`, `detect_self_referential_features`, `detect_suppression_shape`, `detect_claim_vs_delivery`, and `check_concept_coverage`.
- `plan_tool/review.py:_self_consistency_from_smells` filters `smell_recs` by `SELF_CONSISTENCY_SOURCES` **and** calls `detect_orphaned_deliverable` (`review.py:2999`). It is *not* computed beside `collect_smell_findings` — an earlier draft of this plan asserted that and was wrong; only `check_detail_coverage` is beside.
- **`check_test_strategy_alignment` is not in the battery.** Its only call site is `plan_tool/review.py:collect_deterministic_findings` (`review.py:5138`), the reconcile/review lane. Do not add it to the registry, and do not let step 9 classify it — it is out of this surface entirely.
- `collect_self_consistency_findings` computes `detect_suppression_shape` + `detect_orphaned_deliverable` + `check_concept_coverage` independently for the `--iterate` loop, and its docstring pins **membership parity** with `_self_consistency_from_smells` (`TestCollectSelfConsistencyFindings`). The refactor must keep that parity true and keep the test passing.

**Constraint from the plan:** the deterministic battery's *outputs* are a judgment surface this plan does not touch. This step is behavior-preserving by construction; if any characterization test needs editing to pass, the refactor is wrong, not the test.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `plan_tool/review.py` — introduce the detector registry; split `collect_smell_findings` and `_self_consistency_from_smells` so each detector is an individually addressable registry entry rather than a hard-coded call; keep both functions' public signatures and return values identical.
  - `plan_tool/cli/completeness_phases.py` — route `_run_deterministic_checks`' direct calls through the registry; the assembled `_DeterministicReport` is unchanged field-for-field.
  - `tests/test_review.py` — characterization tests for the fan-outs and the registry's default policy.
  - `tests/cli/test_completeness_cmd.py` — battery-level characterization plus the source-level closure guard.

## Implementation

### The registry

One table of detector entries, each carrying a stable key, the callable, and how its results land in `_DeterministicReport`. Shape is the implementer's call, but it must satisfy:

- **Ordering is preserved exactly.** Findings are rendered and compared in order in several places; the registry iterates in the current call order so output bytes do not move.
- **Result routing is explicit per entry** — which `_DeterministicReport` field (or smell/self-consistency bucket) the entry's output joins. Today that mapping is implicit in the call sites; making it data is most of the value.
- **One policy in this step: run everything.** No conditional. Step 9 adds a policy parameter; this step must not anticipate its shape beyond leaving the seam obvious.
- **Argument shapes differ per detector** (some take `plan, repo_root`, some `plan, path, repo_root`, some keywords). Adapt per entry rather than forcing a uniform signature — a uniform signature would change call semantics and risk behavior drift.
- **An entry that consumes another entry's output says so.** The battery has exactly one such chain at HEAD: `detect_path_style_mismatch(file_checks, repo_root)` reads `check_file_existence`'s results. Record that dependency on the entry — a producer key, or whatever the chosen shape expresses — rather than leaving it implicit in iteration order. Under this step's run-everything policy the distinction is invisible, which is precisely why it must land here: **step 9 layers a policy that can skip entries**, and nothing otherwise stops a grade class from skipping the producer while running the consumer, which would feed the consumer an empty result set and silently weaken it rather than fail. Declaring the chain lets step 9's policy keep a consumer and its producer together, or fail loudly when it cannot.

### Splitting the two fan-outs

- `collect_smell_findings` keeps its name, signature, and returned list, but its five detectors become registry entries it dispatches. Callers outside the battery are unaffected.
- `_self_consistency_from_smells` keeps its contract — the `SELF_CONSISTENCY_SOURCES` filter over `smell_recs` plus `detect_orphaned_deliverable` — with the `detect_orphaned_deliverable` call becoming a registry entry. The filter over already-computed smell recs is **not** a detector and does not get an entry; it is assembly.
- Because `detect_suppression_shape`, `detect_claim_vs_delivery`, and `check_concept_coverage` feed *both* `collect_smell_findings` and (via the source filter) the self-consistency bucket, the split must not compute them twice. Preserve the current single-computation-then-partition structure; the registry addresses *which detectors run*, not how many times.
- **Keep `collect_self_consistency_findings` in parity.** It deliberately computes its three detectors independently; after the refactor it should source them from the same registry entries so the parity the docstring pins cannot silently drift.

### The closure guard (the part that must not be vacuous)

An earlier draft specified a test asserting "a check reachable from `_run_deterministic_checks` is in the registry." That is **true by construction** once the dispatch only calls registry entries, so it can never fail — it would have passed in every audit round of this plan. Two guards that *can* fail:

**`check_input_contract_references` splits into two registry entries.** It is one call with two arms in different grade classes: a plan-level arm gated on `step_filter is None`, and a per-step loop that reads `step.detail` bodies under the run-grade seven-section contract. Step 9 requires them separately classified and explicitly forbids itself the local workaround ("if step 8 did not split it, that is a step 8 gap to fix there, not to branch around here"), so the split belongs here, in the behavior-preserving refactor, where characterization tests can pin that the two entries together produce byte-identical output to the single call. This is the third fan-out this step splits, alongside `collect_smell_findings` and `_self_consistency_from_smells`.

**`_collect_purity_split_findings` is named and allowlisted.** It is the one claude-judged per-step call `_run_deterministic_checks` makes directly, folding into `smell_recs` under `run_purity`. It is not a deterministic detector, so it does not become a registry entry — but a guard that fails on any detector-shaped direct call will fire on it unless the allowlist says otherwise. Add it to the allowlist explicitly, with a one-line reason (claude-judged, not deterministic; already forced off under jira grade by step 7), so step 9 has nothing unclassified to account for and the guard stays specific.

1. **Source-level: the registry is the only path.** A test that parses `_run_deterministic_checks`, `collect_smell_findings`, and `_self_consistency_from_smells` (AST over the module source) and fails if any of them calls a detector-shaped function directly instead of going through the registry dispatch. Adding a detector with a hard-coded call breaks the build — which is the behaviour the guard exists for. Maintain an explicit small allowlist for the assembly helpers that are legitimately called directly (the source filter, the report assembly), so the guard stays specific.
2. **Behavioural: characterization parity.** Fixture plans exercising every detector, with their full `_DeterministicReport` captured before the refactor; the registry-driven battery must reproduce them byte-for-byte. This catches a detector silently dropped from the registry, which the source guard alone would not.

Both are required. The first catches "added and not registered", the second catches "registered wrong or dropped". Write a deliberately-failing case for each (a hard-coded call; a removed entry) and confirm each guard fires, so neither can rot into a tautology.

### Test-creation order (refactor step)

**Characterization tests are pinned before the change and pass unchanged after** — the plan's per-step test strategy for a refactor. Concretely: capture `_DeterministicReport` for the fixture corpus against HEAD, commit those as assertions, then refactor until they pass without edits. If a characterization assertion has to change, stop — the refactor has altered behavior and the change is wrong.

## Tests

`tests/test_review.py`:
- `test_collect_smell_findings_characterization` — the five detectors' combined output for fixture plans, captured pre-refactor, unchanged after.
- `test_self_consistency_from_smells_characterization` — the filter-plus-`detect_orphaned_deliverable` output unchanged, including the `SELF_CONSISTENCY_SOURCES` membership.
- `test_collect_self_consistency_findings_parity_preserved` — the existing parity between `collect_self_consistency_findings` and `_self_consistency_from_smells` still holds after both source from the registry.
- `test_registry_default_policy_runs_every_detector` — with the run-everything policy, every registry entry is invoked exactly once per audit (no double-computation of the shared detectors).

`tests/cli/test_completeness_cmd.py`:
- `test_deterministic_report_characterization` — the full `_DeterministicReport` for the fixture corpus is byte-for-byte identical pre- and post-refactor, field by field, order included.
- `test_registry_is_the_only_dispatch_path` — the source-level guard; plus a negative case injecting a direct detector call and asserting the guard fails.
- `test_registry_covers_the_battery` — the behavioural guard; plus a negative case removing an entry and asserting the characterization test fails.

## Acceptance criteria

- Every detector the completeness battery runs is dispatched through the registry, and the registry holds **eighteen** entries. The arithmetic, stated so it cannot be miscounted: the Input census's **thirteen** direct calls, **minus the two fan-outs** `collect_smell_findings` and `_self_consistency_from_smells` (this step demotes the first to a dispatcher and the second to assembly over already-computed recs — neither is a detector, so neither gets an entry), **plus the six detectors inside them** (five and one), **plus one** for `check_input_contract_references`, which contributes **two** entries rather than one (see below). 11 + 6 + 1 = 18. Do not restate this as "the thirteen direct calls plus the five plus the one": that counts the two fan-outs twice, once as calls and once as their contents, and an implementer checking the criterion by counting entries will land on 18 and read a correct registry as wrong.
- `check_test_strategy_alignment` is **not** in the registry — it belongs to `collect_deterministic_findings` (the reconcile/review lane), not this battery.
- The source-level guard fails when a detector is called directly instead of through the registry, demonstrated by a negative case; the characterization guard fails when a registry entry is removed, likewise demonstrated.
- `collect_smell_findings` and `_self_consistency_from_smells` keep their names, signatures, and return values; `collect_self_consistency_findings` keeps membership parity with the latter and its existing test passes unmodified.
- The shared detectors are computed once per audit, not once per consumer.
- **Zero behavior change:** characterization tests pinned before the refactor pass unchanged after, and the whole existing suite passes with no test edited. `uv run pytest tests/ -q` is green.

## References

- [pytest — How to monkeypatch/mock modules and environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — stubbing detector seams for the registry-dispatch tests.
- [ast — Abstract Syntax Trees](https://docs.python.org/3/library/ast.html) — parsing the battery and fan-out functions for the source-level closure guard.

## Deferred

- **The grade axis itself** — classifying each registry entry `run`/`jira`/both, the jira bundle check, the report-surface suppressions, and the guidance prose all belong to step 9. This step adds no grade parameter and no conditional policy; it only makes one possible.
- **Extending the registry to the reconcile/review lanes** (`collect_deterministic_findings`, which owns `check_test_strategy_alignment`) — out of this plan's fence. If the registry proves itself, propose it there via `BACKLOG.md`.
- **Any change to a detector's own logic, severity, or output** — this is a pure refactor; a detector bug found while moving it goes to `BUG_BACKLOG.md`, not into this diff.
