> **Replaced**: this file has been superseded by `docs/implementation-plans/2-completeness-apply-split-bridge.md`.
> Preserved here for history; do not edit.

# Plan seed: the completeness-apply split bridge (route a `granularity-split` conceptual finding to `escalate_to_split`)

Builds the **completeness-apply split bridge** arm of BACKLOG **#70**
("Structural-remedy vocabulary: remaining convenience arms"). It is the *missing
convergence link* between "the completeness/detail audit knows a step must split"
and "the plan structure is actually split": today the audit surfaces a
`granularity-split` MIXED-STEP finding ("step mixes refactor + feature") but the
apply path leaves it as **triage prose** — the operator must split / renumber /
re-author the plan by hand. This plan wires the completeness-apply walk to dispatch
that finding to the **already-shipped `escalate_to_split` bridge**, behind the same
opt-in + TTY-confirm gate the merge/re-ground bridges use.

> **Origin (2026-07-08):** while hardening `parallel-rate-limit-switch-scope`,
> detail/completeness correctly found that step 1 mixed a refactor with a feature,
> but the apply path did not route that structural finding to split — the operator
> had to split/renumber/re-author manually.

> **Backlog reconciliation (carry forward — required).** This plan is derived from
> BACKLOG **#70**. Its final docs/status step **must** update `BACKLOG.md`: remove
> the **"Completeness-apply split bridge"** bullet from #70's *Remaining* list (the
> other three arms — multi-step carve, dispatcher consolidation, code-reveals-a-split
> — stay open), and note the ship date. Put this in the acceptance criteria of the
> last step, not in operator memory.

## What this is (the target behavior)

When `completeness-apply` (serial `--jobs 1` interactive walk) replays a saved
conceptual gap map that contains a `granularity-split` **MIXED-STEP** finding
(`source="granularity-split"`, carrying a resolvable `step_id`), and the operator
opted into structural mutation, the walk **dispatches that finding to
`escalate_to_split`** instead of triaging it to prose. `escalate_to_split` already
owns the whole mechanism: it re-parses the plan from disk, runs the PENDING-only
**safety gate** (`split_safety.split_is_safe`), proposes the two halves via Claude
(`_propose_step_split`), applies the 1→2 split, migrates downstream detail files,
and writes the plan — or, when the gate/flag/confirm don't hold, **recommends only**
and mutates nothing (the frozen `EscalateResult` where only `applied` mutates).

The bridge itself is **unchanged** — this plan is the *wiring* into the
completeness-apply lane, mirroring how the interactive review/reconcile walk already
routes a `BLOCKED-STRUCTURAL` verdict through
`cli/review_actions.py:_dispatch_structural_escalation` → `escalate_to_split`.

## The seams (grounded — cite these in detail)

- **The model to copy:** `cli/review_actions.py:_dispatch_structural_escalation`
  (≈788–868) calls `escalate_to_split(plan_path, step_id=rec.step_id,
  repo_root=..., invoker=shell_claude_invoker, allow_split=(allow_split and not
  state.yes_to_all), prompt_fn=None)` and maps all five `EscalateResult.outcome`
  values to a one-line walk status. It guards `rec.step_id is None` (plan-level →
  "re-decompose by hand", no bridge call). **This function is directly reusable.**
- **The bridge:** `launcher.py:escalate_to_split` (≈2689–2777) → frozen
  `EscalateResult` (`launcher.py:2631–2653`), outcomes
  `applied`/`recommended`/`unsafe`/`proposal-unusable`/`step-missing`; only
  `applied` mutates. Decision order: re-parse from disk → step-missing → **safety
  gate before any Claude** → `not allow_split` → propose → confirm → apply.
- **Safety gate:** `split_safety.split_is_safe(plan, target_id)` — blocks when any
  `s.id >= target_id and s.status != StepStatus.PENDING` (DONE/CURRENT carry
  id-keyed run state nothing migrates; parked deferred/wont_do stay PENDING → safe).
  Single choke point; do **not** re-implement safety in the completeness lane.
- **The apply walk:** `cli/completeness_cmd.py` filters saved recs by
  `_SAVED_SERIAL_APPLY_SOURCE_RANK` (≈266–268), builds the action fn via
  `_build_review_action_fn(..., extra_apply_sources=_walk_apply_sources)` (≈484–495),
  and calls `review_walk.walk_recommendations(..., extra_apply_sources=...)`
  (≈521–528). The parallel lane is `cli/completeness_apply_parallel.py` +
  `completeness_cmd._apply_walk_recs_parallel` (≈593).
- **The dispatch predicate:** `review_walk.is_dispatchable` (≈238–276) has four
  qualifying paths today; **none matches `granularity-split`**, so the finding is
  triaged, never dispatched.
- **The finding + its absence from the sidecar (THE prerequisite):**
  `granularity.parse_mixed_step_findings` (≈439–498) emits the `medium` MIXED-STEP
  `granularity-split` rec with `step_id=step.id`. But in
  `cli/completeness_phases.py`, `granularity_recs` fold into `smell_recs` (≈550–552)
  and the persisted `sidecar_recs = correctness + conceptual + data_contract`
  (≈1371–1375) **excludes them** — they reach report prose only. The apply walk
  replays `saved.recommendations` (= `sidecar_recs`), so it never sees a
  granularity-split finding today. **Persisting the finding is step one.**
- **Triage-today behavior being changed:** `review.py` keeps `granularity-split`
  OUT of `APPLY_ELIGIBLE_SOURCES` and IN `STRUCTURAL_SOURCES`; `is_structural` →
  `triage_reason` prose ("split via `plan-tool split`, not an apply edit",
  ≈3807–3811). This plan does **not** move it into `APPLY_ELIGIBLE_SOURCES` (it is
  not an `apply_finding` edit) — it adds a **structural dispatch** path, exactly as
  merge/re-ground route through the merge-directive dispatch rather than
  `apply_finding`.

## Resolved design decisions (ground the build on these)

1. **Only the `medium` MIXED-STEP prose findings become dispatchable; the `info`
   deterministic detectors stay advisory/report-only.** `parse_mixed_step_findings`
   emits `severity="medium"` (the higher-confidence, Claude-judged split signal);
   the deterministic title/area detectors (`_split_findings`) emit `info` and are
   heuristic. Persist and dispatch the `medium`+ signal; keep the `info` detectors
   in the report `Smells (advisory)` bucket unchanged. This avoids firing a
   structural mutation off a low-confidence title heuristic.

2. **Persisting granularity-split to the sidecar is a data-contract change.** The
   saved-review sidecar shape is drift-guarded (`DATA_CONTRACT.md` +
   `tests/test_data_contract.py`). Adding `granularity-split` to `sidecar_recs`
   changes what the persisted gap map can contain; update `DATA_CONTRACT.md` in the
   same plan and keep the drift guard green.

3. **Gate = the existing structural opt-in + TTY confirm; recommend-only otherwise;
   never unattended.** Reuse the shipped structural-remedy gate shape (the
   `--apply-structural`/`--include-info` opt-in the merge/re-ground bridges ride,
   plus the `escalate_to_split` `allow_split` + interactive `_confirm_split`). With
   the flag absent → **recommend only** (print the runnable
   `plan-tool split <plan> --step N --into ... --into ...`), no Claude, no mutation.
   Under `-y`/`yes_to_all` and in the **parallel** lane (`--jobs > 1`, which requires
   `-y`) → **recommend only**, never auto-confirm: structural mutation must not
   happen unattended (mirror `escalate_to_split`'s `allow_split=(allow_split and not
   yes_to_all)` invariant; a blanket fast-forward or a worktree worker must never
   reshape the plan spine).

4. **Safety uses `split_is_safe` unchanged — it already keys on run-reflecting
   `status`.** The entry's "real run evidence, not just `status: current`" concern is
   already satisfied by the shipped gate: it blocks **any** non-PENDING at-or-after
   the target (both CURRENT *and* DONE), which is strictly stronger than "current
   only". Do **not** fork a second safety notion here. (Extending the gate to consult
   run-log / git-worktree markers beyond `status` is a separate hardening — see
   Deferred — not part of this bridge.)

5. **An applied split HALTS the walk and demands a re-audit; it does not continue
   down the stale gap map.** A 1→2 split **renumbers** every step from the target
   onward, so every *other* saved finding's `step_id`/anchor is now stale. On an
   `applied` outcome the walk must stop and tell the operator to re-run
   `completeness-audit` (the gap map is invalid), rather than applying subsequent
   findings against wrong ids — analogous to how the review walk reverts and
   short-circuits on `BLOCKED-STRUCTURAL`. `recommended`/`unsafe`/other outcomes do
   **not** halt (nothing mutated); they record a one-line status and continue.

6. **Reuse `_dispatch_structural_escalation`; do not fork a second escalation body.**
   It already takes a `rec` with `step_id`, wires `shell_claude_invoker`,
   `allow_split`, and `prompt_fn=None`, and maps every outcome. The completeness lane
   should call it (threading `allow_split` from the structural opt-in), not
   re-derive the mapping.

## Deferred (out of scope — file to BACKLOG #70 / BUG_BACKLOG as they surface)

- **The other three #70 arms** — multi-step/region carve, per-remedy
  `--merge`/`--reground` walk flags + dispatcher consolidation, and the
  code-reveals-a-split reconcile producer — stay open under #70.
- **Run-evidence hardening of `split_is_safe`** beyond the `status` field (consulting
  run-log `run-started` markers or `git status --porcelain`) — a separate change to
  the single choke point, affecting every `escalate_to_split` caller, not just this
  bridge. Note it; do not bundle it.
- **Parallel-lane structural mutation** — the `--jobs > 1` worktree lane stays
  recommend-only for structural findings (decision 3); building safe parallel
  structural apply is future design.
- **`create`-side structural dispatch** — `create.py`'s convergence loop still does
  not route through `escalate_to_split` (the create-side trigger is separately
  deferred per CLAUDE.md); this plan is completeness-apply only.

## Acceptance criteria (plan-level)

- A saved conceptual gap map containing a `medium` `granularity-split` MIXED-STEP
  finding (resolvable `step_id`), walked by `completeness-apply` **with the
  structural opt-in + an interactive confirm on a safe plan**, dispatches to
  `escalate_to_split` and **applies** the 1→2 split (plan renumbered, downstream
  detail files migrated) — the operator does not hand-edit the plan.
- **Without** the opt-in, under `-y`, in the parallel lane, on an **unsafe** plan
  (a non-PENDING step at/after the target), or a declined/non-TTY confirm → the walk
  **recommends only**: it prints the runnable `plan-tool split … --step N --into …`,
  spends **no Claude on mutation**, and leaves plan + detail files byte-unchanged
  (only `applied` mutated).
- A `granularity-split` `medium` finding is now **persisted to the saved sidecar**
  (not report-prose only), `DATA_CONTRACT.md` documents the addition, and its drift
  guard stays green; the `info` deterministic granularity detectors remain
  report-only advisory.
- On an **applied** split the walk **halts and instructs a re-audit** (stale gap
  map), and does not apply any later saved finding against the now-renumbered ids.
- `granularity-split` stays **out** of `APPLY_ELIGIBLE_SOURCES` and does **not** flip
  an exit code; the new path is a structural dispatch, not an `apply_finding` edit.
- Docs updated: `CLAUDE.md` (the escalate-to-split bridge *callers* list gains the
  completeness-apply lane), `RUNBOOK.md` (operator walkthrough),
  `docs/cli/completeness-apply.md` (the new opt-in + recommend-only default), and
  **`BACKLOG.md` #70** (remove the completeness-apply split bridge bullet from
  *Remaining*, note the ship date).

## Tests (where coverage lands)

- `tests/cli/test_completeness_cmd.py` — sidecar now carries a `medium`
  granularity-split (extend/counter the existing folds-into-smells test at ≈699);
  the apply walk dispatches it to a **stubbed** `escalate_to_split` (stub the bridge,
  do not spawn real Claude); recommend-only under no-flag / `-y` / unsafe.
- `tests/cli/test_review_actions.py` — `TestStructuralEscalation` is the template
  for the outcome→status mapping if a completeness-side wrapper is added.
- `tests/test_review_walk.py` — a new dispatchable path for `granularity-split`
  (merge/re-ground dispatchability tests ≈2748–2812 are the analog).
- `tests/test_data_contract.py` — the sidecar-shape drift guard stays green with the
  new source persisted.
- Seam discipline: stub `escalate_to_split` / the split proposer; the conftest
  autouse gate must not see a real backend spawn.
