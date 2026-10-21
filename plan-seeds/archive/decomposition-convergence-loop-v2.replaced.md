> **Replaced**: this file has been superseded by `docs/implementation-plans/2-convergence-actuation-and-surfacing.md`.
> Preserved here for history; do not edit.

## Overview

Ship the two levers deliberately deferred from the v1 `plan-tool convergence`
diagnostic (**BACKLOG #57**):

1. **Opt-in auto-execution of the localized re-split** (`FORK_LOCALIZED`) —
   wire the recommended in-place split behind an explicit flag + TTY confirm,
   mirroring the `--apply-scope-out` gate the same command already ships for
   `FORK_SCOPE_OUT`. The *structural* re-seed (`FORK_STRUCTURAL`) stays
   human-authored and recommend-only — an auto-re-decompose that guesses wrong
   silently reshapes the plan's spine, exactly the case the
   never-mutate-structure-unattended invariant exists for.
2. **Report-section surfacing** — fold the convergence verdict into the
   completeness report output itself (as a short "Convergence diagnosis"
   section printed only when the loop is spinning / stalled), so the operator
   sees the diagnosis *exactly when it trips* instead of having to remember to
   run a separate `plan-tool convergence <plan>` invocation.

Both levers reuse the shipped v1 machinery unchanged: `load_report_history` →
`build_region_trends` → `diagnose_convergence` → `classify_fork` /
`render_diagnosis` in `plan_tool/convergence_diagnosis.py`. This seed adds no
new detector, no new finding source, and no new report schema — it wires
existing analysis into an actuator (lever 1) and into the completeness render
path (lever 2).

> **Source:** BACKLOG #57, "Decomposition convergence loop: opt-in
> auto-execution + report-section surfacing" (T2). The v1 read-only diagnostic
> already shipped (`convergence_diagnosis.py` + `cli/convergence_cmd.py`); this
> plan closes out the two remaining levers parked in the v1 seed's `##
> Deferred` (`plan-seeds/decomposition-convergence-loop.distilled.md`). **The
> plan's final docs/status step MUST reconcile BACKLOG #57**: remove the entry
> once both levers ship, or leave a trimmed entry naming any lever intentionally
> left for later, and keep the [Quality/accuracy lens](../BACKLOG.md) roll-up
> in sync (facets `convergence` + `audit-coverage`).

## Problem statement

v1 automated the *detection and recommendation* half of the
audit-detects-bad-decomposition → re-decompose pipeline edge, and the
subsequent scope-out executor added an *applied* carve for `FORK_SCOPE_OUT`
(behind `--apply-scope-out`). Two gaps remain:

- **The localized re-split is still recommend-only.** When the diagnosis says a
  single step is over-packed and the fix is an in-place 1→2 re-split
  (`FORK_LOCALIZED`), the operator must copy the printed `plan-tool split …`
  command and run it by hand. Every other fork has either an actuator
  (`FORK_SCOPE_OUT` → `scope_out_step`) or a deliberate human-only policy
  (`FORK_STRUCTURAL` → re-seed). The localized fork is the odd one out — a safe,
  bounded mutation with no actuator.
- **The verdict is invisible unless you go looking for it.** The signature is
  most useful surfaced *exactly when it trips*. Today it only appears if the
  operator independently decides to run `plan-tool convergence`. A plan can
  spin through several `completeness --iterate` invocations, each reporting
  `no_blocking_findings`, while the convergence diagnostic that would explain
  the non-convergence sits unqueried.

## Architecture

### Lever 1 — actuate the localized re-split

**Precedent to mirror exactly:** `cli/convergence_cmd.py:_actuate_scope_out`
already implements the shape. `--apply-scope-out` actuates *only* a `spinning`
`FORK_SCOPE_OUT` verdict, carving `classify_fork(diagnosis).step_focus`, and
returns 0 for every completed outcome, exiting 1 only on a post-seed
`NarrowError` mutation failure. Lever 1 adds the sibling `--apply-split` flag
that actuates *only* a `spinning` `FORK_LOCALIZED` verdict.

**The load-bearing design decision — the two `--into` titles.** Unlike
scope-out (which carves one *known* step and needs no extra input), the
localized split is a 1→2 that needs **two concern titles** the diagnosis does
**not** hold: `_split_command` deliberately renders them as
`--into "<first sub-step>" --into "<second sub-step>"` placeholders because no
granularity finding carrying the concern split reaches the sidecar in v1. So
"auto-execute the localized split" cannot be a fully-deterministic zero-input
carve the way scope-out is. Resolve this explicitly — the plan should pick and
justify one:

- **(A) Operator supplies the titles.** `--apply-split` *requires* two
  `--into "<title>"` values (reuse `cmd_split`'s own `--into` parsing); the
  command then dispatches the deterministic `cli/authoring.py:cmd_split`
  executor against `classify_fork(...).step_focus`. Stays **zero-Claude** and
  fully deterministic — the operator provides exactly the one thing the
  diagnosis can't infer. This preserves the convergence command's zero-Claude
  property and is the recommended default. Missing/insufficient `--into` values
  → refuse with the recommend-only render (never split blindly).
- **(B) Route through `escalate_to_split`.** The `launcher.py:escalate_to_split`
  bridge already turns a recognized over-packed step into an *applied* 1→2 split
  by proposing the split via Claude, behind `allow_split` + a TTY `yes` confirm.
  Reuse would give title-free auto-execution but **spends Claude** and is
  specialized for the MIXED-STEP refactor+feature shape, not a generic
  over-pack — a poorer fit and it breaks the command's zero-Claude contract.

Recommend **(A)** for v2 (deterministic, zero-Claude, smallest surface); note
(B) as a future enhancement if title inference is ever wanted. Either way the
gate is identical to scope-out's: **recommend-only unless `--apply-split` + a
TTY confirm hold**, `-y` is the deliberate second opt-in that bypasses the
confirm, and a non-TTY invocation without `-y` declines to recommend-only.

**Fork safety.** Actuate on `FORK_LOCALIZED` only. A `FORK_SCOPE_OUT`,
`FORK_STRUCTURAL`, `FORK_NONE`, or non-`spinning` verdict under `--apply-split`
must fall through to the same render + exit-0 path `_actuate_scope_out` uses for
a non-matching verdict (print the diagnosis, mutate nothing). `--apply-split`
and `--apply-scope-out` are mutually exclusive per invocation (each targets a
different fork); reject passing both.

**Staleness.** Reuse the same fingerprint staleness guard the scope-out carve
uses (`convergence_cmd.py:~118`), so an `--apply-split` against a
since-renumbered plan refuses rather than splitting the wrong (renumbered) step.
Treat an empty saved/current fingerprint as **stale** (fail-closed), consistent
with the BUG_BACKLOG staleness-guard direction.

### Lever 2 — surface the diagnosis in the completeness report

**Where.** The completeness report is assembled by
`completeness_report.py:build_report_md` and persisted by
`write_completeness_report`. Add an optional "Convergence diagnosis" section to
the rendered report, produced by reusing `load_report_history` →
`diagnose_convergence` → `render_diagnosis` (no new logic).

**The history-window ordering nuance (must resolve).** `write_completeness_report`
writes *this* run's sidecar, and the diagnostic's window must count the run just
completed. Two clean options — the plan picks one and documents it:

- Compute the diagnosis over the **prior** on-disk history plus the current
  in-memory run appended, *before* the sidecar write; or
- Write the sidecar first, then run `load_report_history` (now inclusive of the
  current run) and append the section to the rendered/stored report.

Prefer whichever keeps `build_report_md` a pure renderer and confines the
history read to the persistence path. Do **not** double-count the current run.

**When to show it — "after K stalled runs".** The section prints **only** when
the diagnosis is worth surfacing — `spinning`, or arguably `insufficient-history`
suppressed. Do **not** append a reassuring `converging` / `no-history` section on
every ordinary report (noise, and it would read as an endorsement). Gate on
verdict; keep the healthy path byte-for-byte unchanged.

**No Claude, no exit-code change.** The section is rendered from report JSON
already on disk (same zero-Claude property as the standalone command) and never
flips the completeness exit code (exit-code convention: completeness exits
non-zero only on failure-to-complete, and a convergence verdict is a finding-like
signal, not a failure).

## Out of scope

- **Auto-executing the structural re-seed (`FORK_STRUCTURAL`).** Stays
  human-authored and recommend-only, forever — an auto-re-decompose that guesses
  wrong reshapes the plan spine. This is the never-mutate-structure-unattended
  invariant, not a deferral.
- **New detectors, finding sources, or report-schema fields.** Both levers reuse
  the shipped v1 analysis verbatim. The producer-side changes (persist
  `smell_recs`, per-finding BLOCKED marker, plan/detail body size) remain the
  separately-tracked v2 prerequisites from the v1 seed — this plan does not
  touch them.
- **`--min-runs` / `--fail-on-findings` CI flags.** Still out; the spin
  threshold N stays a detector keyword, and the exit-code convention holds.
- **Cross-plan sweep / backlog-health view.** Out.
- **Claude-assisted title inference for the localized split** (option B above).
  Out for v2; the deterministic operator-supplied-titles path (A) is the ship
  target.

## Risks

- **`--apply-split` splits the wrong step after a renumber.** Severity: high.
  Mitigation: the same fingerprint staleness guard the scope-out carve uses,
  fail-closed on an empty fingerprint; `classify_fork(...).step_focus` re-derived
  from the freshly-loaded history, not a saved step number.
- **Blind split with placeholder titles.** Severity: high (produces garbage
  sub-steps). Mitigation: option (A) — refuse `--apply-split` unless two valid
  `--into` titles are supplied; never substitute the `<first sub-step>`
  placeholder as a real title.
- **Report section always printed → noise / false endorsement.** Severity:
  medium. Mitigation: gate the section on a `spinning` (stalled) verdict only;
  leave the healthy report path unchanged.
- **Double-counting the current run in the window.** Severity: medium (could
  trip `spinning` one run early or render a stale window). Mitigation: single,
  documented ordering of sidecar-write vs. history-read; a fixture test that
  asserts the window length after one report equals the on-disk sidecar count.
- **Import-cycle pressure from the completeness→convergence edge.** Severity:
  low. Mitigation: `convergence_diagnosis.py` is already a leaf below the CLI
  importing only `review_persistence`/`review`/`locator`/`convergence`;
  `completeness_report.py` may import it, not vice-versa. Lazy-import if it would
  close a cycle.

## Testing

- **Lever 1 (unit, `tests/cli/test_convergence_cmd.py`):** `--apply-split`
  actuates only a `spinning` `FORK_LOCALIZED` verdict and dispatches `cmd_split`
  against `classify_fork(...).step_focus` with the supplied `--into` titles;
  a non-`FORK_LOCALIZED` / non-spinning verdict under `--apply-split` renders +
  exits 0 and mutates nothing; missing/insufficient `--into` refuses to split;
  `--apply-split` + `--apply-scope-out` together is rejected; the staleness
  guard refuses a since-renumbered / empty-fingerprint plan; exit 0 for every
  completed outcome and 1 only on a mutation failure (mirror the scope-out
  actuator's test matrix). Assert **zero Claude** (autouse backend gate).
- **Lever 2 (unit, `tests/test_completeness_report.py`):** the "Convergence
  diagnosis" section is appended **only** on a `spinning` verdict and omitted on
  `converging` / `no-history` / `insufficient-history`; the healthy report is
  byte-for-byte unchanged; the window includes the current run exactly once
  (fixture asserting window length == on-disk sidecar count after one report);
  rendered from JSON with zero Claude; the completeness exit code is unaffected.
- **Integration (`@pytest.mark.integration`, one per lever):** drive
  `plan-tool convergence <plan> --apply-split --into "A" --into "B"` through
  `main([...])` against a fixture history that is spinning-localized and assert
  the plan is re-split and the run exits 0; drive `completeness --iterate` on a
  spinning-history fixture and assert the report contains the diagnosis section.
- Reuse the real-`SavedReview`-schema fixtures the v1 diagnostic tests already
  pin; add no assumed-shape fixtures.

## Acceptance criteria

- `plan-tool convergence <plan> --apply-split` actuates the in-place re-split
  **only** for a `spinning` `FORK_LOCALIZED` verdict, requires two operator-
  supplied `--into` titles, is recommend-only without `--apply-split` + a TTY
  confirm (`-y` bypasses the confirm), and spends **zero Claude**.
- The structural re-seed path is **never** auto-executed; `FORK_STRUCTURAL`
  stays recommend-only.
- `--apply-split` refuses (recommend-only, exit 0) on a non-`FORK_LOCALIZED` /
  non-spinning verdict, on missing `--into` titles, and on a stale / empty-
  fingerprint diagnosis; `--apply-split` and `--apply-scope-out` are mutually
  exclusive.
- `--apply-split` exits 0 for every completed outcome and 1 **only** on a
  mutation failure mid-split (failure-to-complete), consistent with
  `--apply-scope-out`.
- The completeness report prints a "Convergence diagnosis" section **only when
  the plan is spinning**, rendered from saved report JSON with zero Claude, the
  current run counted in the window exactly once, and the healthy-plan report
  output unchanged; the completeness exit code is unaffected.
- `convergence_diagnosis.py` remains a cycle-free leaf; the completeness →
  convergence import edge (if added) is one-way and acyclic.
- BACKLOG #57 is reconciled in the plan's final step (entry removed, or trimmed
  to name any lever left for later) and the Quality/accuracy lens roll-up is
  kept in sync.
- Docs updated: CLAUDE.md's convergence-diagnostic paragraph and RUNBOOK.md's
  convergence walkthrough note `--apply-split` alongside `--apply-scope-out`,
  and the completeness-report doc notes the new section; regenerate the
  `docs/cli/` reference for the new flag.

## Deferred

- **Claude-assisted title inference for the localized split** (option B via
  `escalate_to_split`) — only if the operator-supplied-titles path proves
  insufficient in practice.
- The v1 producer-side prerequisites (persist `smell_recs` / per-finding
  BLOCKED marker / plan-detail body size) remain tracked separately; they
  sharpen the *detector*, not these two actuator/surfacing levers.
