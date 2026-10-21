> **Auto-archived**: this plan was swept on 2026-07-12 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Code Reveals A Split Detector
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Add the code-grounded split detector to the reconcile lane
  files:
  - plan_tool/review.py
  - tests/test_review.py
  - tests/test_review_walk.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/code-reveals-a-split-detector/01-code-grounded-split-detector-reconcile.md
  status: done
- id: 2
  title: Document the code-grounded split producer in CLAUDE.md and RUNBOOK
  files:
  - CLAUDE.md
  - RUNBOOK.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/code-reveals-a-split-detector/02-document-code-grounded-split-producer.md
  status: done
- id: 3
  title: 'Close BACKLOG #70''s last arm and its T2 roll-up'
  files:
  - BACKLOG.md
  complexity: low
  change_type: non-code
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/code-reveals-a-split-detector/03-close-backlog-70-last-arm-its-t2-roll-up.md
  status: done
---
# Code Reveals A Split Detector

## Overview

Add a new deterministic, code-grounded split detector to the `reconcile` lane. It emits an advisory `granularity-split` recommendation for a single non-`DONE` step whose `heuristic_already_done` hits reveal it fuses two separable concerns (part already built across multiple files, part not) and should split along the built/un-built seam. This is the **inverse** of the existing code-grounded merge producer `_reground_already_built_recommendation` and completes the **last open arm** of BACKLOG **#70** ("Code-reveals-a-split detection"). The detector is **advisory `info` only**: it never mutates, never auto-dispatches to the split bridge, and never flips an exit code. It reuses existing machinery (the `heuristic_already_done` hit set, the `granularity-split` literal + `Recommendation` shape, the split-branch `triage_reason`) — no new code-scanning infrastructure, no bridge changes, and no new source token.

## Problem statement

`reconcile` audits a plan **against current code** and already has a code-grounded **merge/re-ground** producer — `_reground_already_built_recommendation` (`review.py:3880`) — which fires when **≥2 distinct steps** look already-built and re-baselines the set. Its **inverse has no producer**: a **single** step whose code reveals it spans **two separable concerns** should be **split**, but nothing detects that from code today. The only split producers are the **static** `granularity.py` detectors (which read plan structure / titles only, never code) and the completeness MIXED-STEP → `escalate_to_split` path. #70's last open arm is precisely a *code-grounded* split producer mirroring the re-ground sibling; until it lands, reconcile can surface a step that must split but has no way to say so.

## Architecture

The producer plugs into `extract_recommendations`'s `if reconcile_lane and step_filter is None:` block (`review.py:3407`), alongside `_reground_already_built_recommendation`.

**Trigger (decidable, conservative built-vs-unbuilt boundary in ONE step).** Fire **one** advisory finding for a single **non-`DONE`** step when, among that step's `heuristic_already_done` hits, there are **≥2 distinct `file` values** (the step's code touches ≥2 separable already-built files) **AND ≥1 declared `step.files` entry has no hit** (a *proxy* for "an un-built portion remains" — see the Risks note) **AND at least one un-hit declared file is a *non-test* file** (path not under a `tests/` dir and basename not matching `test_*`/`*_test`). The test-exclusion clause kills the **dominant false positive**: a step whose only un-hit file is its own test (impl landed, tests pending) is one concern that is merely half-done — *not* two separable concerns — and the tool's type-purity model keeps tests riding with their feature, so splitting there is wrong. That narrowed co-occurrence is the signal that the step fuses ≥2 concerns and should split along the built/un-built seam. Count distinct files with a set comprehension **mirroring the re-ground builder's distinct-step count** (`{hit.file for hit in step_hits}`, cf. `review.py:3897`). The test-exclusion is a trivial string check on the already-in-hand `step.files` paths (no AST/scan). Precision over recall — one finding per qualifying step, or none.

**Routing (reuse the `granularity-split` literal at `severity="info"`).** Emit `source="granularity-split"` as a **hard-coded literal, not imported** — `review.py` must not import `granularity.py` (the cycle rule, already how `STRUCTURAL_SOURCES` duplicates the literal at `review.py:4190`) — with `severity="info"`, `step_id=<the step>`, and remedy prose pointing at `plan-tool split`. `info` + `granularity-split` gives `is_structural=True` (split-branch `triage_reason`, deferred, pointed at `plan-tool split`) but is **NOT** auto-dispatched: `split_escalation_target` (`review_walk.py:352`) gates auto-dispatch on `severity == "medium"` **and** the source being in `extra_apply_sources`, so an `info` finding stays recommend-only — exactly like the deterministic `info` split hints granularity already emits. Do **not** use a neutral literal (`granularity-merge`); its directive grammar is merge/reground, the wrong family for a split.

**Stay OUT of `APPLY_ELIGIBLE_SOURCES`.** `STRUCTURAL_SOURCES` is disjoint from `APPLY_ELIGIBLE_SOURCES` by design (pinned by `test_structural_sources_disjoint_from_apply_eligible`, `test_review.py:8946`). This producer changes neither set.

**Reconcile-lane double gate (same as re-ground).** The shared completeness/run-gate builder (`collect_deterministic_findings`, `review.py:4574`) calls `extract_recommendations` with `heuristic_hits=[]` **and** `reconcile_lane=False`, so the producer stays off every non-reconcile surface by both guards (empty hits → no signal; `reconcile_lane=False` → the block never runs). `review_plan_full` (`review.py:6062`) passes `reconcile_lane=True`.

**Distinct rec id, own remedy prose.** Mint the id like the re-ground builder (`_make_rec_id(step_id, "granularity-split", fingerprint)`) with a **step-keyed** fingerprint `code-reveals-split:<step_id>` — **not** the hit-file set. The concept identity is the *step* ("this step should split"), so folding the volatile built-file set into the id would re-hash the same concept to a new id whenever a coincidental hit lands or another file gets built between passes, losing a prior `skip` annotation (the advisory re-nags) and making the convergence diagnostic see churn instead of a stable recurrence. This mirrors the sibling `_reground_already_built_recommendation`, which keys only on its step-id set. Carry the finding's own title/body/suggested prose (name the built files, the un-built remainder, and a **runnable** `plan-tool split <plan_name> --step <step_id>` scaffold — the two `--into` half-titles can't be auto-derived, but the plan-name + `--step <id>` prefix can, matching the sibling producers that each emit a runnable invocation: re-ground carries `plan-tool create <plan> --from-existing <seed>`, the convergence `FORK_SCOPE_OUT` arm prints `plan-tool scope-out <name> --step N`); the structural `triage_reason` branch names only the generic `plan-tool split` remedy, not the specifics. The body **must** carry two caveats the coarse signal demands (mirroring re-ground's "confirm the steps really are built" hedge):
- **Confirm two *separable* concerns, not one half-done concern.** Tell the operator to verify the step genuinely fuses two concerns before splitting — the built/un-built seam is a proxy, not proof.
- **Preserve the built half's status.** `plan-tool split` (`create.py:_apply_step_split`) leaves the first half at the target's status and later halves `PENDING`, so **no half is marked `DONE`** — but the detector's whole premise is that part is *already built*. The remedy prose must tell the operator to **mark the built half `done` after splitting**, or `run` will re-implement already-built code. (This is the detection↔remedy mismatch the split verb alone can't close; naming it in the prose is the in-scope fix — auto-marking is out of scope.)
- **Multi-step ordering.** When several steps qualify in one pass, note that each rendered `--step <id>` is against the *current* numbering and `plan-tool split` renumbers to contiguous `1..N`, so apply splits **highest-id-first** (or re-run reconcile between splits) to keep the ids valid.

**Shape.** Add `_code_reveals_split_recommendations(heuristic_hits, plan, *, plan_name)` returning `list[Recommendation]` — **one recommendation per qualifying step** (a single reconcile pass can flag several steps), so a list, not an `Optional`. Group hits by `step_id` and iterate `plan.steps`, appending per qualifying step, so the reconcile-lane emit is one `recs.extend(...)` call.

**Mutual exclusion with re-ground (resolve the contradiction at the source).** The split producer and `_reground_already_built_recommendation` would otherwise contradict each other: re-ground fires on **≥2 distinct step_ids with any hit** and its remedy is "mark the already-built steps `done`" (a *mutating* action under `--reground`); a split-qualifying step (≥2 distinct hit files, ≥1 un-hit file) is only **partially** built, so it must never be offered for "mark done." A prose-only precedence caveat cannot fix this — re-ground is emitted first, is the visible/mutating finding, and the split advisory is `info` (hidden without `--include-info`), so an operator acts on "mark A done" and drops A's un-built portion before ever reading the caveat. **Resolution: make the two mutually exclusive by excluding split-qualifying steps from re-ground's input.** In the emit block, compute the split-qualifying step-id set first, then call `_reground_already_built_recommendation` with the hit list **filtered to drop those steps' hits** — so a partially-built multi-file step is a *split* candidate only, never a re-ground candidate. This keeps the re-ground **builder unchanged** (only its call-site input is filtered) and makes the two clean inverses: **fully/simply-built → re-ground; partially-built across ≥2 files → split.** If the exclusion drops re-ground below 2 steps it correctly returns no finding. A test pins that a co-qualifying step appears in the split finding and is **absent** from the re-ground set.

The **same exclusion applies to the static pairwise `granularity-merge` findings** emitted in the reconcile-lane block (section 2b, `review.py:3419`): a "merge step A with its neighbor" advisory (A is *too small*) directly contradicts "split step A" (A is *too big / fuses concerns*), and the pairwise-merge finding is the *visible* one (kept past `skip_info`) while the split is hidden. Drop any pairwise-merge finding whose flagged pair includes a split-qualifying step before appending it, so a split-qualifying step never also carries a merge advisory. A test pins this too. **Recoverability caveat:** the pair's ids are fully recoverable only for an **adjacent** pair (where `_merge_rec` attaches the `render_merge_action` marker, so `parse_merge_action` returns both ids); a **gapped** pair carries `step_id=lo_id` and *no* marker (its `hi_id` lives only in title prose), so the exclusion can key on `lo_id` but not a split-qualifying step at the gapped *higher* end. Gapped pairwise merges are already the weaker, prose-only, recommend-only form, so this residual (a split-qualifying step at the far end of a gapped merge still seeing both advisories) is a narrow **accepted limitation**, noted rather than closed — closing it would require parsing `hi_id` out of prose, out of scope.

**Seams already in place (verify before extending):** `review.py` — `heuristic_already_done` (`:835`, returns `HeuristicHit(step_id, file, symbol, pattern)` at `:268`), `_reground_already_built_recommendation` (`:3880`), the emit block (`:3407`), `extract_recommendations` (`:3314`), `review_plan_full` (`:6062`), `STRUCTURAL_SOURCES` / `is_structural` (`:4195`/`:4296`), `triage_reason` split branch (`:4373`), `APPLY_ELIGIBLE_SOURCES` (`:4157`), `_make_rec_id`. `review_walk.py` — `split_escalation_target` (`:352`), `is_apply_as_finding` (`:316`, structural → False). `granularity.py` — `GRANULARITY_SPLIT_SOURCE = "granularity-split"` (`:41`), reuse the literal value only.

## References

- [typing — Support for type hints (Python 3.13)](https://docs.python.org/3/library/typing.html) — Official reference for the `list[Recommendation]` return annotation the new producer uses (one rec per qualifying step).
- [dataclasses — Data Classes (Python 3.13)](https://docs.python.org/3/library/dataclasses.html) — Official reference for @dataclass(frozen=True) semantics, relevant to constructing Recommendation/HeuristicHit instances the detector emits and reads.
- [Displays (comprehensions) — Python Language Reference](https://docs.python.org/3/reference/expressions.html#displays-for-lists-sets-and-dictionaries) — Primary reference for set-comprehension semantics, the exact construct used to count distinct files ({hit.file for hit in step_hits}) that drives the trigger boundary.
- [pytest — How to mark test functions with attributes](https://docs.pytest.org/en/stable/how-to/mark.html) — Official guide to pytest markers, consulted when adding the new TestCodeGroundedSplitBuilder / gating test classes and honoring the repo's @pytest.mark.integration convention.
- [pytest — How to use fixtures](https://docs.pytest.org/en/stable/how-to/fixtures.html) — Official fixtures reference for wiring the tmp_path-hermetic plan/invoker fixtures the review_plan_full integration test needs.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- **Any mutation / auto-split.** Recommend-only; the finding points at `plan-tool split`. No change to `escalate_to_split`, the split bridge, or `split_escalation_target`.
- **A new source token.** Reuse `granularity-split`; introduce no `code-split` literal.
- **New code-scanning.** The trigger reads only the existing `heuristic_already_done` hit list + `step.files`; no AST/diff/git analysis.
- **Touching the static `granularity.py` detectors** or importing them into `review.py`.
- **Promoting to `medium`/blocking or into `extra_apply_sources`** — advisory `info` only.

## Risks

- **False "must split" calls** on superficial multi-file symbol overlap — keep it advisory (`info`), conservative (the built-AND-unbuilt co-occurrence, not mere multi-file), and reconcile-lane-only. `heuristic_already_done`'s coarse first-hit-per-file matching means "≥2 distinct files" is a proxy, not proof — precision-over-recall framing and recommend-only routing bound the blast radius.
- **"No hit" over-counts the un-built side (three classes, not two).** A declared file yields no hit in *three* cases, only one of which is genuinely un-built: (1) unscannable extension (`.yaml`/`.txt` are never opened), (2) not-yet-created on disk, and — the **highest-frequency** class — (3) *scanned but no title-symbol match* (e.g. a declared `test_*.py` whose contents don't contain the derived title symbol). Class (3) means an ordinary multi-file step with a test file can trip the un-built condition on that test file alone. Accepted as precision-over-recall (advisory `info`, recommend-only); **not** narrowed here (extension/existence filtering would be new code-scanning — see Out of scope). Named so the disclosure doesn't lag the detail's Input caveat.
- **`step.creates` under-count blind spot.** The un-built check reads only `step.files` (the set `heuristic_already_done` scans), so a step whose un-built work lives entirely in `step.creates` (new files not yet on disk) — with every existing `files` entry already hit — never triggers, even though "existing files done, new files pending" is the *cleanest* built/un-built seam. An accepted recall limitation (the inverse of the over-count above); using `step.files` keeps the comparison a plain string set-diff against exactly what the heuristic reads.
- **≥2-hit-files recall floor.** The trigger requires **≥2 distinct hit files**, so a two-file step with exactly **one** built file plus one un-built non-test file — arguably the simplest built/un-built seam — never fires. Accepted by design: the ≥2-built-files bar is what makes "the built side already spans multiple separable files" a credible fuses-concerns signal; a single built file is too thin to distinguish a two-concern step from an ordinary half-done one. Named so the accepted-tradeoff list is complete.
- **Cycle regression** — importing `granularity` into `review.py` for the literal would re-introduce the forbidden edge; hard-code the string, as `STRUCTURAL_SOURCES` already does.
- **Lane leak** — an unconditional emit would surface the finding on completeness/review; respect the `reconcile_lane and step_filter is None` + non-empty-hits double gate.

## Testing

Mirror the re-ground test suite in `tests/test_review.py`:
- **`TestCodeGroundedSplitBuilder`** — trigger boundaries: no hits, single file, ≥2 files but all declared files hit → **no** finding; ≥2 files + an un-hit declared file → finding; `DONE` step skipped.
- **A gating class** — asserts the producer emits only in the reconcile lane + `step_filter is None`, and is omitted by `collect_deterministic_findings`.
- **A `review_plan_full` integration test** — surfaces the advisory `granularity-split` finding end-to-end through reconcile, asserting it in the report / returned recs / saved JSON. Do **not** assert default interactive-walk visibility: `walk_recommendations`'s `skip_info` carve hides this per-step `info` finding unless `--include-info` is passed.
- Assert the finding stays `info` (not auto-dispatched) via the `split_escalation_target` boundary (`test_review_walk.py:2865`-style) and stays out of `APPLY_ELIGIBLE_SOURCES`.

Existing suites that must stay green: `test_structural_sources_disjoint_from_apply_eligible` (`test_review.py:8946`), the re-ground finding tests, the static granularity detector tests, and every existing structural-routing test.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — unit tests added with the implementation; green before completion.
- step 2 (non-code) — verification appropriate to the artifacts; no test-ordering directive.
- step 3 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- `reconcile` (via `review_plan_full`) surfaces an advisory `granularity-split` finding for a single non-`DONE` step whose `heuristic_already_done` hits span **≥2 distinct files** while **≥1 declared file has no hit** — scoped to the reconcile lane (absent from `collect_deterministic_findings` / completeness / review / run-gate paths), `severity="info"`, `step_id` set, carrying its own runnable `plan-tool split <plan> --step <id>` remedy prose. "Surfaces" means the markdown report, the returned recs, and the saved JSON sidecar — **not** the default interactive walk: `review_walk.py:walk_recommendations`'s `skip_info` carve keeps only pairwise `granularity-merge` info recs visible, so this per-step `info` `granularity-split` finding is walked only under `--include-info` (the shipped info-visibility contract). Acceptance/tests assert report + returned-recs + saved-JSON visibility, not default-walk visibility.
- The finding is `is_structural=True` (split-branch `triage_reason`), is **never** auto-dispatched to `escalate_to_split` (blocked by `split_escalation_target`'s `medium`+opt-in gate), is **not** in `APPLY_ELIGIBLE_SOURCES` (disjointness test still green), and never flips an exit code. No new source token; `review.py` still does not import `granularity`.
- Split and re-ground are **mutually exclusive**: a split-qualifying step (≥2 hit files, ≥1 un-hit file) is excluded from re-ground's input at the emit site, so it appears in the split finding and is **absent** from any re-ground set — a partially-built step is never offered for "mark done." The re-ground **builder** (`_reground_already_built_recommendation`) body is unchanged (only its call-site input is filtered) and its own unit tests stay green.
- The static granularity detectors, `escalate_to_split`, and every existing structural-routing test remain unchanged/green.
- CLAUDE.md + RUNBOOK document the code-grounded split producer as the **second** code-grounded reconcile producer beside re-ground (re-ground is the only pre-existing one; the pairwise `granularity-merge` findings come from the static `granularity.py` advisor, not code). Sites updated: CLAUDE.md granularity-advisor paragraph (~:64) and the structural-vocabulary **re-split producer enumeration** bullet (~:70); RUNBOOK.md code-grounded re-ground callout (~:1727), the `Smells (advisory)` note, and the four-remedies re-split entry (~:2347). The CLAUDE.md **escalate-to-split paragraph (~:62) is deliberately NOT edited** — a recommend-only `info` producer never routes through that bridge, so it has nothing to add there.
- BACKLOG #70's last arm ("Code-reveals-a-split detection") is struck and #70 is closed as fully shipped, including the T2 tier roll-up parenthetical (`BACKLOG.md` ~:482–484), with a pre-close check that no other arm remains.

## Deferred

- **Promotion to `medium`/blocking or into `extra_apply_sources`** — a later measurement item could consider promotion (cf. #110's pattern); out of scope here, kept advisory `info` only for now.
