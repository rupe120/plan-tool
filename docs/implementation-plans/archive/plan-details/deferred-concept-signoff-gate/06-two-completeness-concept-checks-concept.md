# Step 6 — Add the two completeness concept checks (concept-coverage blocking, concept-unsigned-deferral advisory), recomputing coverage by slug, plus a parallel-apply no-loss regression test

## Summary

Add two deterministic (no-claude) checks to `plan_tool/review.py` that read the plan's concept tree and surface two gaps: `check_concept_coverage` flags every `include`, `signed_off=True` concept with no covering step (source `concept-coverage`, `medium` → blocking), and `check_concept_signoff` flags every deferred concept (`defer` / `wont_do`) the operator never signed off (source `concept-unsigned-deferral`, `info` → advisory). The key decision: coverage is **recomputed from each concept's slug against the current plan every run** — the checks never trust a persisted `covered_by`. That is what makes them safe under the parallel `completeness-apply` worktree path, which cannot persist a `concepts.json` write back from a worker; a regression test in `tests/cli/test_completeness_apply_parallel.py` pins that the sidecar is neither captured nor clobbered by the replay tail. Both sources stay out of `APPLY_ELIGIBLE_SOURCES` (apply can't add a step or sign off a deferral), so the blocking `concept-coverage` finding routes through the self-consistency battery and the advisory `concept-unsigned-deferral` rides the smell bucket — reaching the report and the blocking gate with no change to `plan_tool/cli/completeness_phases.py`. `plan_tool/completeness_report.py` gains the disposition vocabulary so the curated report explains the two sources with the right remedy instead of the generic "fix the path / run detail" text.

## Table of Contents

- [Why](#why) — the silent-coverage / unsigned-deferral gap the audit still leaves
- [Input](#input) — the step 1 concept-tree contract these checks read
- [Files (creates vs edits)](#files-creates-vs-edits) — two code edits, two test edits
- [Implementation](#implementation) — the two checks, the seams they fold into, the slug recompute, the report vocabulary
- [Tests](#tests) — coverage, sign-off, no-op, eligibility, and the parallel no-loss regression
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — dataclasses, hashlib, ThreadPoolExecutor, git-worktree
- [Deferred](#deferred) — covered_by persistence, scope-review wiring, phases intro prose

## Why

Steps 1–5 built the concept tree, filled it, let an operator sign it off, and wired the sign-off gate into `create` and `detail`. Nothing yet **audits** the tree against the plan it belongs to. Two gaps stay silent: an `include` concept the operator committed to can have no step that covers it (the plan promises the idea but no step delivers it), and a `defer` / `wont_do` concept can sit unsigned — created under `--yes`, on a non-TTY run, or before this feature — so the deferral was never confirmed by a human. The completeness audit already owns "does the plan cover its own ideas?" (`plan_tool/review.py:detect_orphaned_deliverable`, the `plan-completeness` conceptual axis). These two checks extend that battery to the concept tree: a blocking finding when an included concept is orphaned, and an advisory nudge when a deferral was never signed. Both are deterministic and read only markdown/JSON, so they fit the no-claude well-formedness battery rather than the semantic pass.

## Input

This step reads the concept-tree contract owned by **step 1** (`depends_on: 1`) — reference it, do not re-specify it. What the checks touch on each `ConceptNode`:

- **`state`** — one of `include` / `defer` / `wont_do`. `check_concept_coverage` inspects only `include` nodes; `check_concept_signoff` inspects only `defer` / `wont_do` nodes.
- **`title`** — the human label the coverage slug is derived from. The check slugifies it (kebab-case) and matches that against the plan.
- **`signed_off`** — the operator-only terminal flag step 3's navigator sets. `check_concept_coverage` fires only on `include` nodes that are `signed_off=True` (an unsigned included node is inert — this keeps a cold-start / `--yes`-derived tree, whose nodes are all `signed_off=False`, from raising a blocking finding); `check_concept_signoff` fires when it is `False` on a deferred node.
- **`covered_by`** — deliberately **not read**. Step 2 leaves it empty and step 6 recomputes coverage by slug instead of trusting it (see Implementation). Treat any stored value as advisory only.
- **`read_concepts(plan_path)`** — step 1's loader takes the **plan path** and resolves the sidecar internally (mirroring `plan_tool/grounding.py:read_grounding`), so callers do not pre-resolve `concepts_path`. It returns `None` only when the sidecar is absent; a present unreadable or invalid sidecar raises `ConceptTreeIntegrityError`, which completeness converts into one blocking `concept-integrity` finding and then skips decision evaluation.

If step 1's final field names or state literals differ from the above, follow step 1's shipped contract — it is the owner.

This step also consumes the plan structure it audits against: `Step.features` (feature-id slugs), `Plan.features` (id → title registry), `Step.scope` (`StepScope.COMMITTED` / `DEFERRED` / `WONT_DO`), and `Step.title` — all in `plan_tool/schema.py`.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/review.py` — add `check_concept_coverage` and `check_concept_signoff`; add the two source constants (`CONCEPT_COVERAGE_SOURCE = "concept-coverage"`, `CONCEPT_UNSIGNED_DEFERRAL_SOURCE = "concept-unsigned-deferral"`); fold `check_concept_coverage` into `collect_self_consistency_findings` and `_self_consistency_from_smells` (the two blocking-battery producers that must stay in sync), and `check_concept_signoff` into `collect_smell_findings` (the advisory bucket). Keep both sources **out** of `APPLY_ELIGIBLE_SOURCES` and `STRUCTURAL_SOURCES`.
  - `plan_tool/completeness_report.py` — teach the curated report vocabulary about the two concept sources: a `deferred_kind` special-case + matching `WHY` / `_HEADINGS` entries so a concept-coverage finding renders with the "add a covering step / re-run the concept gate" remedy (not the generic structural-diagnostic text), and update the `## Smells (advisory)` section intro so it names the concept sign-off advisory.
  - `tests/test_completeness_report.py` — disposition/vocabulary tests for the two new sources.
  - `tests/cli/test_completeness_apply_parallel.py` — the parallel-apply no-loss regression test (the concepts sidecar is not captured or clobbered by the replay tail; concept sources are not apply-eligible).

## Implementation

**Add the two checks in `plan_tool/review.py`, modeled on `detect_orphaned_deliverable`.** Both take `(plan: Plan, repo_root: Path, *, plan_name: str, plan_path: Optional[Path] = None)`, return `list[Recommendation]`, shell out to nothing, and read only the concept sidecar plus plan structure. Mirror the sibling: a module-level source constant, stable ids via `_make_rec_id(step_id, source, fingerprint)`, and a body that states the gap plainly. Reach step 1's leaf with a body-local `from plan_tool.concept_tree import read_concepts` — matching how `detect_orphaned_deliverable` imports `plan_tool.detail` inside the function.

- **Guard first.** `if plan_path is None: return []`. Then call `read_concepts(plan_path)`; if it returns `None`, return `[]` because no `concepts.json` exists. Catch `ConceptTreeIntegrityError` and emit one `concept-integrity`, `medium` blocking recommendation directing the operator to repair or explicitly rederive the sidecar, then skip both coverage and unsigned-deferral evaluation. If a valid tree exists but its stored fingerprint does not match the current plan, emit one advisory `concept-stale` recommendation directing the operator to `scope-review --rederive`, then skip both coverage and unsigned-deferral evaluation so stale decisions are never treated as current.

- **`check_concept_coverage` — the blocking check.** For each `include` node with `signed_off=True` (skip unsigned included nodes — a cold-start / `--yes`-derived tree is all `signed_off=False` and must stay inert per §E/§G), compute its slug (kebab-case of `title`) and ask "does any committed step cover this concept?" A concept is **covered** when at least one `StepScope.COMMITTED` step matches the slug — recommended signal: the slug appears in the step's `features:` ids, or matches the slugified `Plan.features` title for one of those ids, or matches the step's slugified `title`. When no committed step matches, emit a `Recommendation` with `source="concept-coverage"`, `severity="medium"` (so `plan_tool/convergence.py:is_blocking` returns `True`), `step_id=None` (plan-altitude), a `body` naming the concept and the remedy ("no step covers included concept `X` — add a covering step, or re-run the `create` / `detail` concept gate and move it to *defer*"), and a `suggested_action` carrying the same remedy so it renders usefully in the grouped `### Self-consistency` section. Keep the matcher **conservative** — prefer a false negative (miss a real gap) over nagging, the same stance `detect_orphaned_deliverable` documents; leave the exact token-matching to the implementer but hold the invariant that coverage is derived only from current plan structure.

- **`check_concept_signoff` — the advisory check.** For each `defer` / `wont_do` node with `signed_off` `False`, emit a `Recommendation` with `source="concept-unsigned-deferral"`, `severity="info"` (advisory — never blocks; smells are excluded from `_completeness_has_blocking_findings`), `step_id=None`, and a `body` naming the concept and the remedy ("deferral of concept `X` was never signed off — re-run `plan-tool create` / `plan-tool detail` and confirm it in the concept walk"). A node already `signed_off=True` produces nothing.

- **The headline decision — recompute coverage from current titles and authoritative feature ownership, never read `covered_by`.** The alternative (persist `covered_by` on each node and read it here) is rejected: the parallel `completeness-apply` path runs each apply in an isolated git worktree off HEAD and replays only the files in `apply_finding`'s `pre_snapshot` (the plan `.md` + every step's detail file — see `plan_tool/cli/completeness_apply_parallel.py` `_capture_changes` and its NOTE). `concepts.json` is not in that snapshot, so a coverage stamp written inside a worker is **lost on teardown**. Recomputing coverage from each current step's title and feature ids catches the explicit replacement semantics in plan §H: split partitions matching feature ownership among children, merge unions source feature ownership, and re-ground preserves the covering title/features or carries their union to a replacement. Nothing is persisted to the sidecar, so there is no coverage write for the worktree to drop.

- **Evaluate every node independently of its ancestors.** Parent state is neither inherited nor derived. `check_concept_coverage` evaluates every signed-off `include` node, including one beneath a `defer` or `wont_do` ancestor; `check_concept_signoff` likewise evaluates each node's own `defer` / `wont_do` state. A mixed subtree is not a fourth persisted state and does not suppress either check.

- **Wire concept-coverage into the blocking self-consistency battery, both producers.** `concept-coverage` is blocking but not apply-eligible — the same shape as `orphaned-deliverable` / `suppression-shape`. Add `check_concept_coverage(...)` to the return of **both** `collect_self_consistency_findings` (which the `--iterate` loop's blocking signal reads) **and** `_self_consistency_from_smells` (which feeds the finalize `--fail-on-findings` gate and the report). These two must stay in sync — the parity is pinned by `TestCollectSelfConsistencyFindings`; adding it to only one lane would make `--iterate` and the audit-only path disagree. Do **not** add it to `collect_deterministic_findings`: that feeds `apply_finding`'s pre/post delta, and the codebase deliberately keeps non-appliable findings out of it (see the `collect_self_consistency_findings` docstring). `concept-coverage` need not join `SELF_CONSISTENCY_SOURCES` (that set only partitions elevated smells) since it is computed fresh like `orphaned-deliverable`.

- **Wire concept-unsigned-deferral into the advisory smell bucket.** Add `check_concept_signoff(...)` to `collect_smell_findings`'s return. That bucket surfaces in the grouped `### Smells (advisory)` section, is passed to `build_report_md(..., smells=...)` for the curated `## Smells (advisory)` section, and is never an input to `_completeness_has_blocking_findings` — so the sign-off advisory shows everywhere yet never flips the exit code.

- **Give the two sources a correct disposition in `plan_tool/completeness_report.py`.** `deferred_kind` today routes any non-apply-eligible, non-`plan-completeness` source to `"diagnostic"`, whose `WHY["diagnostic"]` text ("fix the declared path, run `plan-tool detail`") is wrong for a concept gap. Special-case the two concept sources so they render with the concept-gate remedy: add a `concept-coverage` branch (its remedy: add a covering step or re-run the concept gate) with matching `WHY` / `_HEADINGS` entries, and add the new kind to the disposition-summary `by_kind` counter and the `for kind in (...)` deferred-bucket loop in `build_report_md`. For the advisory `concept-unsigned-deferral`, update the `## Smells (advisory)` section intro so it names the sign-off advisory alongside the brittle-feature-ref / self-referential / granularity items. Keep `is_apply_eligible` returning `False` for both.

**Gotchas / invariants to hold:**
- **Both checks no-op without `plan_path` or a sidecar.** The self-consistency and smell producers already pass `plan_path`; a `None` path or `read_concepts` returning `None` must yield `[]`. A present invalid sidecar instead yields one blocking `concept-integrity` finding, deduplicated across the two check lanes.
- **Keep both sources out of `APPLY_ELIGIBLE_SOURCES` and `STRUCTURAL_SOURCES`.** Apply-eligibility would route a concept finding into `apply_finding` (which can't add a step or sign off a deferral) and, worse, into the parallel worker where its edits would be lost. A test pins `is_apply_eligible` `False` for both.
- **The two self-consistency producers must return the same concept-coverage membership.** Fold `check_concept_coverage` into both `collect_self_consistency_findings` and `_self_consistency_from_smells`; do not let them diverge.
- **The remedy prose travels in the `Recommendation` body/`suggested_action`.** The grouped `### Self-consistency` section intro lives in `plan_tool/cli/completeness_phases.py` (out of scope); carrying the fix in the finding body means the concept-coverage remedy renders correctly there without editing that file.

## Tests

Enumerate unit tests **with** the implementation; each must be green before the step is done (the green-before-done gate). Add to `tests/test_completeness_report.py` unless noted. The concept-tree checks read a step-1 leaf, so tests build a small `ConceptTree` (via step 1's constructors) and write it with `save_concepts`, or inject a fake `read_concepts` — never spawn claude (the conftest real-backend gate stays satisfied because these checks shell out to nothing).

Checks (add to `tests/test_review.py`, the mirror of the source module):
- `test_concept_coverage_flags_uncovered_include` — a `signed_off=True` `include` concept with no matching committed step yields one `concept-coverage`, `medium`.
- `test_concept_coverage_silent_when_unsigned` — an `include` concept with `signed_off=False` (cold-start / `--yes` default) yields nothing, even with no covering step (§E/§G inertness).
- `test_concept_coverage_silent_when_covered` — a `signed_off=True` `include` concept whose slug matches a committed step's `features` / title yields nothing.
- `test_concept_coverage_ignores_deferred_states` — `defer` / `wont_do` nodes never produce a coverage finding.
- `test_concept_coverage_checks_included_child_of_deferred_parent` — a signed-off uncovered `include` child still yields a finding beneath a `defer` parent.
- `test_concept_coverage_recomputed_not_from_covered_by` — a node with a stale/empty `covered_by` but a real covering step is treated as covered (coverage comes from the slug recompute, not the stored field).
- `test_concept_coverage_matches_structural_replacements` — split children with partitioned matching features, a merge replacement with the union of source features, and a re-grounded step preserving the covering title/features each keep their formerly covered concepts covered.
- `test_concept_signoff_flags_unsigned_deferral` — a `defer` node with `signed_off=False` yields one `concept-unsigned-deferral`, `info`.
- `test_concept_signoff_silent_when_signed` — a `defer` node with `signed_off=True` yields nothing.
- `test_concept_signoff_ignores_include` — `include` nodes never produce a sign-off finding.
- `test_concept_checks_noop_without_sidecar` — both checks return `[]` when `read_concepts` returns `None` (no `concepts.json`).
- `test_invalid_concept_tree_reports_blocking_integrity_failure` — a present unreadable, malformed, wrong-version, or field-invalid sidecar emits one blocking `concept-integrity` recommendation and neither concept decision finding.
- `test_stale_concept_tree_reports_without_evaluating_decisions` — a fingerprint mismatch emits one advisory `concept-stale` recommendation with the `scope-review --rederive` remedy and emits neither coverage nor unsigned-deferral findings.
- `test_concept_coverage_in_both_self_consistency_producers` — `check_concept_coverage`'s finding appears in both `collect_self_consistency_findings` and `_self_consistency_from_smells` for the same plan/tree (parity).
- `test_concept_signoff_in_collect_smell_findings` — `check_concept_signoff`'s finding appears in `collect_smell_findings`'s output.

Disposition / report vocabulary (`tests/test_completeness_report.py`):
- `test_concept_sources_not_apply_eligible` — `is_apply_eligible` is `False` for both `concept-coverage` and `concept-unsigned-deferral`.
- `test_deferred_kind_concept_coverage` — `deferred_kind` returns the concept-coverage kind (not `"diagnostic"`) for a `concept-coverage` rec.
- `test_report_explains_concept_coverage_remedy` — `build_report_md` with a `concept-coverage` deferred rec renders the concept-gate remedy heading/text, not the generic "run `plan-tool detail`" line.
- `test_smells_intro_names_concept_signoff` — the `## Smells (advisory)` intro names the concept sign-off advisory when a `concept-unsigned-deferral` rec is in `smells`.

Parallel-apply no-loss regression (`tests/cli/test_completeness_apply_parallel.py`):
- `test_replay_leaves_concepts_sidecar_untouched` — a canonical tree carrying a `concepts.json`; `replay_results` (or `run_parallel_apply` with a fake pool + invoker) over an ordinary apply-eligible finding leaves `concepts.json` unchanged (it is neither in a `FileChange` nor written by `_write_change`).
- `test_capture_changes_excludes_concepts_sidecar` — a `concepts.json` written inside a worker tree but absent from `apply_finding`'s `pre_snapshot` produces no `FileChange` from `_capture_changes` — documenting exactly why coverage is recomputed, not persisted, in the worker.
- `test_concept_findings_not_dispatched_by_parallel_apply` — a `concept-coverage` / `concept-unsigned-deferral` rec is not apply-eligible, so the apply-eligible filter drops it before `dispatch_parallel` (it never reaches a worker).

## Acceptance criteria

- `check_concept_coverage` returns one `medium` `concept-coverage` `Recommendation` per `signed_off=True` `include` concept with no covering committed step, and `[]` when every included concept is covered, when an included concept is `signed_off=False` (cold-start / `--yes` inert), or when there is no `concepts.json`.
- `check_concept_signoff` returns one `info` `concept-unsigned-deferral` `Recommendation` per `defer` / `wont_do` concept with `signed_off=False`, and `[]` otherwise.
- A present invalid `concepts.json` emits one blocking `concept-integrity` recommendation instead of being treated as an absent tree.
- Coverage is derived from concept slugs against current step titles and authoritative feature ownership each run, including the split/merge/re-ground replacement semantics in plan §H; a stale/empty `covered_by` does not change the verdict.
- `check_concept_coverage`'s finding appears in both `collect_self_consistency_findings` and `_self_consistency_from_smells`; `check_concept_signoff`'s appears in `collect_smell_findings`.
- `is_apply_eligible` is `False` for both `concept-coverage` and `concept-unsigned-deferral`.
- `concept-coverage` is blocking (`convergence.is_blocking("medium")` is `True`); `concept-unsigned-deferral` never flips `_completeness_has_blocking_findings`.
- `build_report_md` renders a `concept-coverage` finding with the concept-gate remedy and names the sign-off advisory in the `## Smells (advisory)` intro.
- After `run_parallel_apply` / `replay_results` over an apply-eligible finding, a pre-existing `concepts.json` in the canonical tree is unchanged, and `_capture_changes` never emits a `FileChange` for a concept sidecar.
- Every new test above passes; the full suite stays green.

## References

- [dataclasses — Data Classes (Python 3.13 docs)](https://docs.python.org/3/library/dataclasses.html) — the `Recommendation` / `ConceptNode` field shapes the checks read and build.
- [hashlib — Secure hashes and message digests (Python docs)](https://docs.python.org/3/library/hashlib.html) — how `_make_rec_id` derives the stable finding id these checks reuse.
- [concurrent.futures — ThreadPoolExecutor (Python docs)](https://docs.python.org/3/library/concurrent.futures.html) — the fan-out `run_parallel_apply` uses; context for the no-loss regression.
- [git-worktree Documentation](https://git-scm.com/docs/git-worktree) — the isolated worktrees the parallel apply creates, and why an unsnapshotted `concepts.json` write is lost on teardown.

## Deferred

- **Persisting `covered_by` on each node** — out of scope; this step recomputes coverage by slug and never writes it. Stamping `covered_by` back into `concepts.json` (and making it survive the parallel worktree path) is a later concern if a stored coverage map is ever needed.
- **Wiring these checks into `scope-review`** — step 8's surface; this step only adds the checks to the completeness battery.
- **The grouped `### Self-consistency` section intro naming the concept remedy** — that prose lives in `plan_tool/cli/completeness_phases.py` (out of this step's files); the concept-coverage remedy travels in the finding body instead, so the section renders correctly without a phases edit. A reconcile pass can add a dedicated intro line if desired.
- **Consolidating the two self-consistency producers** (`collect_self_consistency_findings` / `_self_consistency_from_smells`) into one — a reconcile-owned refactor; this step keeps the mirror-not-share convention and folds the concept check into both.
