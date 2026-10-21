# Structural stop in the live completeness and reconcile loops (#158, part 2 of 2)

> **Superseded (2026-08-11):** do not author from this seed. The advisory-only
> design in `docs/implementation-plans/2-convergence-non-severity-advisories.md`
> superseded both `impact-recurrence-0*` seeds. Loop-terminating
> `recurring_high_impact_seam` / `structural_stop` was **withdrawn** when
> BACKLOG **#158** closed (2026-08-11) — do not revive a hard iterate stop.

Second half of the re-seed of `2-impact-recurrence-structural-stop.md` (spinning
/ structural, 2026-07-20). Part 1 (`impact-recurrence-01-classifier`) delivers a
proven offline classifier that no caller uses. This plan wires it into the two
live iterate loops BACKLOG **#158** names, and settles the loop-integration
contracts the replaced plan left contradictory.

**Depends on:** `impact-recurrence-01-classifier` shipped. Do not start before
it; its verdict record is this plan's only input contract.

## Why this is a separate plan

In the replaced decomposition, four loop-integration facts were spread across
steps 5, 6, 7 and 8 and contradicted each other, so no audit finding could
localize:

- `stop-reason-precedence` (HIGH) — `_run_iterate_convergence_loop` feeds
  `should_continue` from **deterministic** findings only
  (`state.current_finding_ids` / `state.has_blocking_findings`, both from
  `_open_findings_now()`). A conceptual seam never enters that set, so once the
  deterministic findings drain, the loop returns `converged` and the new
  `structural_stop` arm is **unreachable** — precisely the "exits as if it
  converged" symptom the work exists to fix.
- `completeness-stop-boundary` (HIGH) — the same step carried both a pre-apply
  and a post-apply placement verbatim, in prose, criteria and test names.
- `deterministic-convergence-preemption` (MEDIUM) — ordering the stop last means
  it fires while deterministic findings are still open, ending the deterministic
  apply loop mid-convergence; the plan never said whether that was intended.
- `reconcile-window-scope` (MEDIUM) — reconcile's window fills from iterations
  *inside one invocation* (with `--max-iterations` defaulting to 3, it would
  halt on essentially any persistent high-impact finding on its third pass),
  while completeness's spans invocations. One stated rule, two real behaviors.
- `stop-decision-telemetry` (HIGH) — telemetry recording was promised in the Out
  of scope prose and listed in a `change_type: non-code` docs step whose detail
  said "**any code change**" was deferred, while the `record_decision` call must
  live at the stop sites.

**The re-cut rule:** each loop's integration is settled *before* it is wired, and
the reachability fix is its own first-class step rather than an assumption.

## Outcome

A live completeness iterate loop and a live reconcile iterate loop each
terminate with a distinct non-successful `recurring_high_impact_seam` /
`structural_stop` outcome — reachably, at a single stated boundary — when part
1's classifier qualifies a seam, printing a recommend-only next action beside
any ordinary severity/decomposition diagnosis, and never mutating plan
structure.

## Decisions this seed settles (the plan must not re-open them)

1. **Reachability is fixed first, explicitly.** The conceptual seam must be able
   to reach the stop decision. The plan's first step establishes how — by
   supplying the classifier verdict to `should_continue` as a **caller-supplied
   input** that is evaluated independently of `_open_findings_now()`, not by
   folding conceptual findings into the deterministic finding set (which would
   change deterministic gate semantics). A test pins that the stop is reachable
   in exactly the state the replaced plan made unreachable: deterministic
   findings drained, conceptual seam still open.
2. **One boundary: post-apply, pre-next-Claude-pass.** The stop is evaluated
   after normal apply work and report persistence, before the next Claude pass.
   Every criterion, test name and Deferred note states that one placement. The
   pre-apply shape is deleted, not carried alongside.
3. **Deterministic work drains first.** The stop does not preempt deterministic
   well-formedness convergence: it is evaluated only when there is no
   outstanding deterministic apply work for the loop to do. This resolves
   `deterministic-convergence-preemption` in the safe direction, and the plan
   says so rather than leaving it implied by ordering.
4. **Each loop declares its own series scope, out loud.** Completeness passes a
   cross-invocation series; reconcile passes a within-invocation series, and the
   plan states the consequence for a default `--max-iterations 3` run and picks
   a defensible response (require a series of separate invocations for reconcile
   too, or state and test the intended within-invocation behavior). The
   asymmetry is named in the plan body, not discovered by an auditor.
5. **Both loops get identical failure isolation.** A classifier exception falls
   through to existing loop behavior in **both** call sites, each with its own
   regression test. No site declines the guard on the grounds that the loader is
   total — the guard is around the classify call.
6. **Both loops render both verdicts.** Where the ordinary
   severity/decomposition diagnosis is also present, both are printed without
   conflation, at both call sites, with tests at both.
7. **Telemetry lands at the stop sites, in the wiring steps.** The
   `record_decision` call for a structural stop is authored in the step that
   owns each stop site — not deferred to the documentation step, which stays
   `non-code`.
8. **The documentation step declares exactly what it covers.** The replaced
   plan's step 8 was a third persistent recurrer purely from footprint drift: it
   was `change_type: non-code` while declaring `plan_tool/telemetry.py`,
   `plan_tool/telemetry_analysis.py` and `tests/test_telemetry_analysis.py`, its
   detail covered 4 of its 7 declared files, and it declared `RUNBOOK.md` while
   deferring it — producing a HIGH telemetry gap, a MEDIUM RUNBOOK gap, a
   blocking self-consistency finding and seven files-coherence NITs, every
   audit, forever. Here the docs step is `non-code` and declares **only** docs
   files it actually writes; every code file moves to the step that writes it
   (decision 7).
9. **The operator has a documented way past a stop they disagree with.** A
   plan-only completeness audit rarely moves the code fingerprint, so a
   false-positive stop is otherwise sticky. The plan names the recovery path
   (and records it in `RUNBOOK.md` beside the other structural remedies) rather
   than assuming the mitigation "apply the finding or use the existing remedy"
   is always available.

## In scope

- `plan_tool/convergence.py` — the `structural_stop` reason on `should_continue`
  as a caller-supplied input, plus `tests/test_convergence.py`.
- `plan_tool/cli/completeness_cmd.py`, `plan_tool/cli/completeness_phases.py` —
  the completeness stop site, its series declaration, failure isolation, dual
  rendering, and its telemetry call; `tests/cli/test_completeness_cmd.py`.
- `plan_tool/cli/reconcile.py` — the same five things for reconcile;
  `tests/test_cli.py`.
- `plan_tool/telemetry.py` / `plan_tool/telemetry_analysis.py` — recording and
  read-only resolution of the structural-stop decision family;
  `tests/test_telemetry_analysis.py`.
- Documentation and backlog closeout: `docs/how-to/pipeline/audit.md`, `RUNBOOK.md`
  (operator walkthrough and the recovery path from decision 9),
  `DATA_CONTRACT.md`, `CLAUDE.md`, `BACKLOG.md`.

## Out of scope / non-goals

- Anything part 1 owns — the window rule, pass de-duplication, eligibility, the
  verdict record, and the recommendation arms are consumed as-is. If a wiring
  need reveals a classifier defect, fix it as a change to part 1's shipped
  contract in its own right; do not re-implement the rule at a call site.
- Threading the stop into the remaining Claude-invoking iterate loops (`create`,
  `detail`) — only completeness and reconcile are wired here.
- Changing `recurring_regions` / `diagnose_convergence` / `classify_fork`
  semantics, or extending `convergence.is_blocking_impact` / the calibrated
  impact policy to any new caller.
- Any automatic structural mutation from a loop; any operator flag to disable or
  tune the three-pass threshold; auto-tuning the threshold from telemetry.
- Folding conceptual findings into the deterministic blocking-finding set — that
  would change gate semantics for every completeness caller (see decision 1).
- A second telemetry or evidence store; new `--jobs`/parallel surfaces.

## Allowed behavior changes

Only these, and only when the classifier qualifies a seam: the two loops may
terminate earlier than they do today, with a distinct non-successful reason and
new recommend-only output. The command's **exit code stays 0** (a completed
audit exits 0 even with findings — the exit-code convention), report persistence
is preserved, and every non-qualifying history behaves byte-for-byte as today.

## Allowed reorganization

None. `should_continue` gains a caller-supplied input; no caller is restructured
and no logic is re-homed.

## Verification

- **Reachability:** a test in the exact state that made the replaced design
  unreachable — deterministic findings drained, conceptual seam still open,
  qualifying history — reaches `structural_stop`.
- **Boundary:** the classifier is invoked exactly once per invocation, at the
  post-apply / pre-next-pass point, in both loops.
- **Preemption:** with outstanding deterministic apply work, the stop does not
  fire and the deterministic loop converges as today.
- **Series scope:** completeness's cross-invocation window and reconcile's
  declared window each behave as stated, including a default
  `--max-iterations 3` reconcile run that must not halt on an ordinary
  persistent finding.
- **Failure isolation:** an exception from the classifier leaves each loop's
  behavior unchanged — one test per site.
- **Dual rendering:** both verdicts print, unconflated, at both sites.
- **No mutation:** no plan file, seed, or structural remedy is written by either
  loop under any of the above.
- **Telemetry:** a structural stop records one decision event whose outcome
  `analyze_decisions` resolves read-only, with no auto-tuning and no plan or
  configuration mutation.

## Stop / defer

Out-of-scope discoveries become `BACKLOG.md` / `BUG_BACKLOG.md` entries, not
plan expansion. In particular: if the reconcile series-scope decision (4) turns
out to need a change to how reconcile persists its `detail-reconcile` sidecars,
that is a separate entry — this plan declares and tests the behavior of the
sidecars as they exist.

## Backlog reconciliation

BACKLOG **#158** is **closed**; hard loop-terminating
`recurring_high_impact_seam` / `structural_stop` was **withdrawn**. This seed is
superseded by the advisory-only plan
`docs/implementation-plans/2-convergence-non-severity-advisories.md` — do not
author from it or revive a machine iterate stop.
