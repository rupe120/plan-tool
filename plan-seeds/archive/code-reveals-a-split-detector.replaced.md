> **Replaced**: this file has been superseded by `docs/implementation-plans/2-code-reveals-a-split-detector.md`.
> Preserved here for history; do not edit.

# Plan seed: code-reveals-a-split detector (BACKLOG #70's last open arm)

Implements the **one remaining open arm** of BACKLOG **#70** (*Structural-remedy
vocabulary: remaining convenience arms*). #70's Remaining list (BACKLOG.md ~:1114–1115)
names it verbatim:

> **Code-reveals-a-split detection** — reconcile can reveal a step that *must split*;
> no producer for it lands yet.

**Backlog reconciliation (required):** this plan is derived from BACKLOG.md **#70**.
Its final docs/status step MUST update BACKLOG.md when the work ships — strike the
"Code-reveals-a-split detection" arm from #70's Remaining list. Because this is the
**last** open arm (multi-step carve, per-remedy `--merge`/`--reground` flags, re-ground
re-baseline, and the completeness-apply split bridge all already shipped), the entry
should then be marked **fully shipped** (move #70 to a closed/shipped disposition, and
update the T2 tier roll-up parenthetical at BACKLOG.md ~:482–484 that itemizes #70's
arms by prose). Verify no other arm remains before closing; if one does, reword instead.

## The gap (a code-grounded merge producer exists; the split inverse does not)

`reconcile` audits a plan **against current code**. It already has a code-grounded
**merge/re-ground** producer — `_reground_already_built_recommendation`
(`review.py:3880`) fires when **≥2 distinct steps** look already-built (→ re-baseline
the set). Its **inverse has no producer**: a **single** step whose code reveals it spans
**two separable concerns** should be **split**, but nothing detects that from code today.
The only split producers are the **static** `granularity.py` detectors (read plan
structure / titles only, never code) and the completeness MIXED-STEP → `escalate_to_split`
path. #70's last arm is a *code-grounded* split producer, mirroring the re-ground sibling.

## Guiding principle

Detection is **unconditional and advisory**; mutation stays **recommend-only**. This adds
a **new deterministic, code-grounded detector** to the reconcile lane that emits a
`granularity-split` recommendation — it never mutates, never auto-dispatches to the split
bridge, and never flips an exit code. It reuses existing machinery (the
`heuristic_already_done` hit set, the `granularity-split` literal + Recommendation shape,
the split-branch `triage_reason`) — **no new code-scanning infrastructure**, no bridge
changes, no new source token.

## Resolved decisions (pin these)

1. **The trigger — a decidable, conservative built-vs-unbuilt boundary in ONE step.**
   Fire **one** advisory finding for a single **non-`DONE`** step when, among that step's
   `heuristic_already_done` hits, there are **≥2 distinct `file` values** (the step's code
   touches ≥2 separable already-built files) **AND ≥1 declared `step.files` entry has no
   hit** (a genuinely un-built portion remains). That co-occurrence — part of the step is
   already built across multiple files while part is not — is the decidable signal that
   the step fuses ≥2 concerns and should split along the built/un-built seam. Count
   distinct files with a set comprehension **mirroring the re-ground builder's distinct-step
   count** (`{hit.file for hit in step_hits}`, cf. `review.py:3897`). Precision over recall
   (matches the granularity detectors' stated philosophy) — one finding per qualifying
   step, or none.
2. **Routing: reuse the `granularity-split` literal at `severity="info"`.** Emit
   `source="granularity-split"` (**hard-coded literal, not imported** — `review.py` must
   not import `granularity.py`; the cycle rule, already how `STRUCTURAL_SOURCES`
   duplicates the literal at `review.py:4190`), `severity="info"`, `step_id=<the step>`,
   with remedy prose pointing at `plan-tool split`. `info` + `granularity-split` gives
   `is_structural=True` (split-branch `triage_reason`, deferred, pointed at `plan-tool
   split`) but is **NOT** auto-dispatched: `split_escalation_target` (`review_walk.py:352`)
   gates auto-dispatch on `severity == "medium"` **and** the source being in
   `extra_apply_sources`, so an `info` finding stays recommend-only — exactly like the
   deterministic `info` split hints granularity already emits. Do **not** use a neutral
   literal (`granularity-merge`) — its directive grammar is merge/reground, the wrong
   family for a split.
3. **Stay OUT of `APPLY_ELIGIBLE_SOURCES`.** `STRUCTURAL_SOURCES` is disjoint from
   `APPLY_ELIGIBLE_SOURCES` by design (pinned by
   `test_structural_sources_disjoint_from_apply_eligible`, `test_review.py:8946`). A
   structural source is never apply-eligible; this producer changes neither set.
4. **Scope to the reconcile lane — the same double gate as re-ground.** Plug the new
   builder into `extract_recommendations`'s `if reconcile_lane and step_filter is None:`
   block (`review.py:3407`), alongside `_reground_already_built_recommendation`. The
   shared completeness/run-gate builder (`collect_deterministic_findings`,
   `review.py:4574`) calls `extract_recommendations` with `heuristic_hits=[]` **and**
   `reconcile_lane=False`, so the producer stays off every non-reconcile surface by both
   guards (empty hits → no signal; `reconcile_lane=False` → the block never runs).
5. **Distinct rec id, own remedy prose.** Mint the id like the re-ground builder
   (`_make_rec_id(step_id, "granularity-split", fingerprint)` with a
   `code-reveals-split:<step_id>:<sorted files>` fingerprint) so distinct triggers yield
   distinct ids while the shared source routes correctly. Carry the finding's own
   title/body/suggested prose (name the built files, the un-built remainder, and
   `plan-tool split`); the neutral/structural `triage_reason` branch names no remedy.

## Seams already in place (verify before extending)

- **`review.py`** — `heuristic_already_done` (`:835`, returns `HeuristicHit(step_id, file,
  symbol, pattern)` at `:268`), `_reground_already_built_recommendation` (`:3880`, the
  mirror), the `if reconcile_lane and step_filter is None:` emit block (`:3407`),
  `extract_recommendations` (`:3314`), `review_plan_full` (`:6062`, passes
  `reconcile_lane=True`), `STRUCTURAL_SOURCES` / `is_structural` (`:4195`/`:4296`),
  `triage_reason` split branch (`:4373`), `APPLY_ELIGIBLE_SOURCES` (`:4157`),
  `_make_rec_id`.
- **`review_walk.py`** — `split_escalation_target` (`:352`, the `medium`+opt-in
  auto-dispatch gate this stays under), `is_apply_as_finding` (`:316`, structural → False).
- **`granularity.py`** — `GRANULARITY_SPLIT_SOURCE = "granularity-split"` (`:41`) — reuse
  the **literal value** only; do not import or call its detectors (cycle rule).

## Scope of work

1. **The code-grounded split producer + wiring (`review.py`, `tests/test_review.py`).**
   Add `_code_reveals_split_recommendation(heuristic_hits, plan, *, plan_name)` returning
   `Optional[Recommendation]` per qualifying step (or a list, one per step — pick to
   mirror the re-ground builder's shape), decision-1 trigger, decision-2/5 routing/id.
   Call it from the `:3407` reconcile-lane block alongside the re-ground builder. Mirror
   the re-ground test suite: a `TestCodeGroundedSplitBuilder` (trigger boundaries: no
   hits, single file, ≥2 files but all declared files hit → **no** finding, ≥2 files +
   an un-hit declared file → finding, `DONE` step skipped), a gating class (emits only in
   reconcile lane + `step_filter is None`; omitted by `collect_deterministic_findings`),
   and a `review_plan_full` integration test. Also assert it stays `info` (not
   auto-dispatched) via the `split_escalation_target` boundary
   (`test_review_walk.py:2865`-style) and stays out of `APPLY_ELIGIBLE_SOURCES`.
2. **Docs (`CLAUDE.md`, `RUNBOOK.md`).** Add the code-grounded split producer as the
   **third** code-grounded reconcile producer beside re-ground: CLAUDE.md's granularity-
   advisor paragraph (~:64, the "second producer outside granularity.py" sentence → note a
   third), the escalate-to-split paragraph (~:62) and the structural-vocabulary re-split
   bullet (~:70); RUNBOOK.md's code-grounded re-ground callout (~:1727 → sibling split
   callout) and the four-remedies model (~:2347).
3. **BACKLOG #70 close-out (`BACKLOG.md`).** Strike the "Code-reveals-a-split detection"
   arm; mark #70 fully shipped (it's the last arm) incl. the T2 roll-up parenthetical
   (~:482–484); per the reconciliation requirement above.

## Non-goals / out of scope

- **Any mutation / auto-split.** Recommend-only; the finding points at `plan-tool split`.
  No change to `escalate_to_split`, the split bridge, or `split_escalation_target`.
- **A new source token.** Reuse `granularity-split`; introduce no `code-split` literal.
- **New code-scanning.** The trigger reads only the existing `heuristic_already_done` hit
  list + `step.files`; no AST/diff/git analysis.
- **Touching the static `granularity.py` detectors** or importing them into `review.py`.
- **Promoting to `medium`/blocking or into `extra_apply_sources`** — advisory `info` only;
  a later measurement item could consider promotion (cf. #110's pattern), out of scope here.

## Risks

- **False "must split" calls** on superficial multi-file symbol overlap — keep it
  advisory (`info`), conservative (the built-AND-unbuilt co-occurrence, not mere
  multi-file), and reconcile-lane-only. `heuristic_already_done`'s coarse first-hit-per-file
  matching means "≥2 distinct files" is a proxy, not proof — precision-over-recall framing
  and recommend-only routing bound the blast radius.
- **Cycle regression** — importing `granularity` into `review.py` for the literal would
  re-introduce the forbidden edge; hard-code the string, as `STRUCTURAL_SOURCES` already
  does.
- **Lane leak** — an unconditional emit would surface the finding on completeness/review;
  respect the `reconcile_lane and step_filter is None` + non-empty-hits double gate.

## Acceptance criteria (plan-level)

- `reconcile` (via `review_plan_full`) surfaces an advisory `granularity-split` finding
  for a single non-`DONE` step whose `heuristic_already_done` hits span **≥2 distinct
  files** while **≥1 declared file has no hit** — scoped to the reconcile lane (absent
  from `collect_deterministic_findings` / completeness / review / run-gate paths),
  `severity="info"`, `step_id` set, carrying its own `plan-tool split` remedy prose.
- The finding is `is_structural=True` (split-branch `triage_reason`), is **never**
  auto-dispatched to `escalate_to_split` (blocked by `split_escalation_target`'s
  `medium`+opt-in gate), is **not** in `APPLY_ELIGIBLE_SOURCES` (disjointness test still
  green), and never flips an exit code. No new source token; `review.py` still does not
  import `granularity`.
- The re-ground finding, the static granularity detectors, `escalate_to_split`, and every
  existing structural-routing test remain unchanged/green.
- CLAUDE.md + RUNBOOK document the code-grounded split producer as the third reconcile
  producer; BACKLOG #70's last arm is struck and #70 is closed as fully shipped (T2
  roll-up updated), with a pre-close check that no other arm remains.
