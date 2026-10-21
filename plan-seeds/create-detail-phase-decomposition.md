# Seed: decompose create_plan and generate_detail into named phase functions

## Outcome

`plan_tool/create.py:create_plan` (~1699 lines) and `plan_tool/detail.py:generate_detail`
(~1721 lines) each become a short top-level function — a sequence of calls to
named phase functions — instead of one continuous body, with zero behavior
change, confirmed by the existing direct-call test suites (158 and 211 call
sites respectively) passing unmodified.

## In scope

- Extract `create_plan`'s pre-loop and post-loop phases into named functions at
  the boundaries the code already treats as natural handoffs: slug/output-dir
  resolution, metadata prompt, the distill first-pass, steps resolution,
  change-type review, plan-object assembly, concept bootstrap/merge, intent
  offer, references proposal, body-sections synthesis, the fail-loud TODO gate,
  collision archival, write+reparse, plan-details rename, fingerprint+concept-
  sync, manifest append (pre-loop); checkpoint cleanup, path-issue advisory,
  post-loop concept sync, pending-decision advisory (post-loop).
- Extract `create_plan`'s convergence `while True` loop (currently ~640 inline
  lines) into one named function taking its full closed-over state as explicit
  parameters/return. Do not further sub-decompose the loop body itself — its
  ordering (drift check → triage → apply → re-derive findings → checkpoint) is
  dense enough that every reordering risk should stay inside one reviewable
  unit rather than spread across several.
- Extract `generate_detail`'s pre-loop setup (jobs/guard validation, plan parse,
  concept load, target-step resolution, orphan-detail adoption, checkpoint
  pre-scan, invoke-target setup) into named functions.
- Extract `generate_detail`'s two post-loop split-resolution blocks ("Phase B"
  and "trigger-2") into named functions. They are near-duplicates of each other
  (both rebuild `results` from on-disk state via the same `written_keys`/
  `min_split` pattern) — share one helper between them rather than keeping two
  ~90-line copies, as long as each caller's own ordering guarantee is preserved
  exactly (Phase B processes high→low id so an earlier split never renumbers a
  not-yet-processed target; trigger-2's recursive re-entry passes `resume=False`
  because the new split-half steps have no checkpoint to probe).
- Extract `generate_detail`'s per-step inner convergence loop (currently ~570
  inline lines, the single largest un-seamed block in either function) into one
  named function, for the same reason as `create_plan`'s loop: keep its dense,
  ordering-sensitive body inside one reviewable unit.
- Leave the jira-lane early fork (`_generate_jira_detail`) and the `jobs > 1`
  concurrent-dispatch fork (`_generate_detail_concurrent`) exactly as they are
  today — both are already correctly extracted; touch their call sites only as
  much as the surrounding phase extraction requires.

## Out of scope

- Unifying `create_plan`'s outer apply-loop and `generate_detail`'s inner
  per-step apply-loop, even though they share a near-identical "triage → dedup
  → drift check → collision-sidecar → auto-reconcile" shape (plan-level vs.
  step-level scoping). A shared implementation is a behavior-risking design
  change, not a pure extraction, and does not belong inside a zero-behavior-
  change refactor. Name it as a candidate for its own future seed; do not
  attempt it here.
- Changing `resume`/`force`/checkpoint semantics for either function. Every
  checkpoint-read/write call, `create_plan`'s discard-only-on-clean-finish rule,
  and `generate_detail`'s per-step durable-write discard rule must land in
  whichever extracted function now owns that code, unchanged.
- `generate_detail`'s two structural-split mechanisms ("Trigger 2" in-loop
  escalation vs. "Phase B" post-loop resolution) merging into one mechanism.
  They are deliberately kept distinct today — the code's own comments warn that
  a shared accumulator name would let one silently discard the other's
  recommendations. Extraction may relocate them; it must not merge them.
- Any change to the ordering constraints documented in the functions' own
  comments (see "Architecture" below) — these are decisions, not incidental
  code shape, and moving the commented code to a new function must carry the
  comment with it.
- `plan_tool/cli/run_cmd.py:cmd_run`. Its own size (505 lines) is a similar
  decompose-in-place problem, but it is a different file/orchestrator with a
  materially lower risk profile (no recursion, ~370 fewer combined direct-call
  test sites) — a candidate for its own, much smaller follow-up, not bundled
  here.

## Allowed behavior changes

None. Every phase's inputs, outputs, side effects, ordering relative to its
neighbors, and error-raising conditions must be identical before and after.

## Allowed reorganization

Split each function's body into named phase functions within the same file
(`create.py` / `detail.py`) — no cross-file moves. Thread shared mutable state
(named under "Architecture" below) as explicit parameters and return values
between the new functions rather than via closures, except where a phase is
already the natural sole owner of a piece of state for its whole lifetime (e.g.
the convergence-loop-local accumulators, which never escape the loop today and
shouldn't need to escape their extracted function either).

## Architecture

Both functions already delegate every Claude round-trip to a named top-level
helper (`propose_steps_from_claude`, `_author_step_detail`, etc.) — what remains
inline is the *orchestration* connecting those calls, plus the two large
un-seamed convergence loops named above. The decomposition target is to give the
connecting orchestration and the loops the same top-level-function treatment the
round-trips already got, not to invent a new pattern.

Load-bearing state each extraction must thread explicitly — not exhaustive (the
detail phase re-derives the full list against live code), but every item below
is a decision this seed is pinning, not leaving to derivation:

- `create_plan`: `plan_path` is the single source of truth *after* the write
  phase — later phases re-parse it from disk rather than trust the in-memory
  `Plan`, because `apply_finding` mutates the file directly. Any extracted phase
  after the write must keep this re-parse-from-disk pattern.
- `create_plan`: the convergence-loop phase must call `write_plan` (frontmatter-
  only rewrite), never `write_new_plan` (body rebuild) — the wrong call would
  clobber every section `apply_finding` filled in a prior iteration. State this
  explicitly in the extracted function's docstring; the distinction is exactly
  the kind of thing a future edit could get backwards without the warning that
  exists inline today.
- `create_plan`: `references` is resolved once before the loop and never
  reassigned; the loop's own per-iteration `refs_proposal` is a distinct name
  for the same concept and must not be conflated with it during extraction.
- `create_plan`: the References patch inside the loop applies unconditionally
  regardless of that iteration's steps-reproposal outcome — this exists because
  of a previously-fixed bug (a successful references round discarded when steps
  re-proposal failed in the same iteration). Preserve the unconditional
  application.
- `generate_detail`: `mixed_steps`, `structural_seen`, `structural_split_ids`,
  and `inloop_structural_recs` are four separately named accumulators for the
  two distinct split mechanisms — keep exactly four, not merged into fewer.
- `generate_detail`: the pre-scan's `invoke_total`/`invoke_idx` counters get
  corrected mid-loop when a user declines a resume prompt at the TTY — an
  extracted pre-scan phase and an extracted per-step-loop phase must still be
  able to perform this correction; don't split them in a way that makes the
  counter unreachable from the loop.
- `generate_detail`: the final concept-persistence branch's legacy-vs-flat fork
  (a legacy full-tree record refuses new flat deferrals, citing `BACKLOG.md`
  #131) is a real behavioral fork, not incidental structure — preserve both
  arms verbatim in whichever function ends up owning persistence.

## Risks

- Both functions are called directly by their test suites at very high density
  (`create_plan(`: 158 sites in `tests/test_create.py`; `generate_detail(`: 211
  sites in `tests/test_detail.py`) — this is the primary safety net for a
  zero-behavior-change claim, but it also means a *signature* change (not just
  a body decomposition) has an outsized blast radius. Do not change either
  function's public signature; only its body.
- `generate_detail` calls itself recursively twice (Phase B, trigger-2) to
  re-author split halves. Any extracted sub-function that participates in that
  recursive call graph must not assume it executes only once per top-level
  invocation.
- The convergence loops in both functions are the densest, most ordering-
  sensitive code in the codebase per this seed's own research; extracting each
  as a single function rather than sub-decomposing further is a deliberate
  risk-reduction choice, not an oversight — resist splitting them further
  during `detail`/`completeness-audit` without a specific, code-grounded
  reason.

## Testing

The existing direct-call test suites (`tests/test_create.py`,
`tests/test_detail.py`) are the primary proof: they must pass with zero
assertion changes, since they test the functions' public contract, not their
internal shape. Where a specific ordering constraint named under "Architecture"
above has no existing test pinning it (e.g. the References-patch-applies-
unconditionally rule, or the legacy-vs-flat concept-persistence fork), add one
characterization test per constraint before extracting the code that implements
it, so a future edit that violates the constraint fails a test instead of
silently reintroducing the bug each comment describes.

## Acceptance criteria

- `create_plan` and `generate_detail` are each a short sequence of calls to
  named phase functions; no phase function exceeds roughly the size of the
  largest already-extracted helper in its file (a concrete ceiling belongs to
  `detail`, not this seed).
- The two convergence loops (create's outer, detail's per-step inner) are each
  one named function, not further sub-decomposed.
- `tests/test_create.py` and `tests/test_detail.py` pass with zero assertion
  changes.
- Every ordering/state constraint listed under "Architecture" is preserved and,
  where it lacked a test, now has one.

## Deferred

Unifying the two functions' near-identical apply-loop shape, and `cmd_run`'s
own decomposition, are named above as related findings but explicitly out of
scope for this seed — file them separately if worth pursuing.

## References

- `plan_tool/create.py` — current `create_plan` authoring sequence targeted
  for named-phase extraction.
- `plan_tool/detail.py` — current `generate_detail` sequence that shares the
  decomposition objective.
- `tests/test_create.py` and `tests/test_detail.py` — direct-call contract
  coverage that keeps extraction behavior-preserving.
