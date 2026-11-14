# Convergence and evidence backlog arc

## File intent

This file is the execution guide for backlog work that makes convergence
signals trustworthy before those signals influence plan decomposition, scope,
or remediation decisions.

## Details

It records the dependency order for provenance, calibration, and trajectory
work; the evidence each item must produce; and the boundaries that keep a
measurement from becoming an unproven classifier or automatic decision maker.

## Choose this arc when

The limiting problem is not a missing feature but uncertainty about whether
audit findings, fixes, and plan decomposition are producing reliable evidence.
Start after the trust-core staleness route has a stable baseline.

## Delivery cadence

Commit each resolved backlog item before starting the next one. Plan-tool work
uses committed green-step checkpoints; direct changes include their regression
coverage and backlog retirement in one bounded commit.
Do not push automatically; push only when the user explicitly requests it.

## Ordered route

1. **Retired 2026-08-19:** #231's proposed causal-provenance feature did not
   earn implementation. The bounded stage-revision trajectory
   (`3 → 2 → 3 → 1 → 3`) requires an
   operator pause and scope decision, but it cannot show that a prior edit
   caused a later model finding. Keep that pause in the driving workflow; do
   not recreate it as a persisted classifier or CLI route.
2. **Delivered 2026-08-19:** the `plan-tool decide` recorder accepts only
   `plan` or `step:<id>`, a closed outcome, and a rationale; it reports a
   failed persistence attempt rather than falsely claiming a durable record.
   It creates neither a chat surface nor a metric-derived decomposition verdict.
3. **Withdrawn 2026-08-20 (user-confirmed):** #299's proposed labelled coverage
   replay did not earn implementation. The detail-grounded audit established
   that proving its model-visible input boundary requires a hermetic capture
   runner, rather than a bounded measurement. Keep #173 deferred and use fresh
   completeness audits. Re-open this route only after measured operational
   audit cost justifies a new, bounded decision. This id stays the withdrawn
   coverage-replay record; later `response_contract` leftover work is #300
   and is not this route.
4. **Delivered 2026-08-20:** the direct `plan-quota-recovery` fixes preserve
   terminal quota diagnostics without changing the confirmed Cursor matcher.
   `21f46aad`, `f9fe30af`, `d82c8b15`, `5937c63f`, `e9f61b3b`, `fc23910f`,
   `a89ef20e`, and `792cfcbc` resolved the feature's five review rounds.
   **#301** (versioned saved audit coverage) and **#302** (one checked
   rate-limit recovery completion path) remain deferred structural follow-ups:
   neither is a live defect or an active arc stage. Re-open #301 only for an
   intentional coverage-format addition and #302 only for a deliberate
   recovery-loop hardening pass.
5. **Delivered 2026-08-21:** #247's independent, zero-Claude ledger lists
   saved completeness artifacts with their saved metadata or opaque state. It
   provides evidence visibility only: it does not compare entries or make a
   convergence claim.
6. **Deferred:** #303 remains the next separately scoped comparison route until
   a persistence design can admit eligible history across plan identity, audit
   revision, coverage, provenance, and finding identity. #247's delivered
   ledger is a visibility prerequisite, not admission evidence. Incomplete,
   malformed, stale, copied, or incompatible evidence must fail closed to the
   #247 ledger rather than produce a comparison.
7. #256 remains deferred unless a labelled corpus shows that the mandatory
   manual identifier-and-vocabulary sweep lacks a deterministic locator and
   bounded candidates improve complete class sweeps. Its only possible first
   cut is advisory candidates, not a per-pass call or persisted inference.
8. #260 is parked. Re-open reporting only for a preserved, concrete misleading
   output with a named reader action and focused fixture; do not recreate a
   renderer umbrella.
9. **Delivered 2026-09-01:** `Recommendation.restated_property` ships as an
   inline addition to `plan_tool/prompts/plan-audit.md`'s "Property coverage
   versus delivery mechanisms" rule, not the separate downstream pass
   originally proposed — a separate pass has less grounding than the call
   that traced the plan and wrote the finding, so it risks misrepresenting
   what was actually found. Its wire format is a `### Restated` /
   `### Fix` sub-block pair (mirroring the existing `## Redirect`
   convention), not the inline `→ restated:`/`→ fix:` trailing markers first
   shipped — two code-review rounds showed the inline form corruptible by
   marker-shaped text anywhere earlier in the body, since the property-
   coverage rule's mandatory verbatim citation can legitimately contain it;
   a heading that must start its own line cannot be produced by *inline*
   quoted prose the way an inline phrase can. A round-4 review found this
   still under-covered a *multi-line* citation, which can contain a genuine
   line-starting heading of its own — round 4 required such a citation to be
   fenced and excluded matches inside a fence, but a round-5 review found
   that fence-recognizer was itself a positional regex, defeated five
   distinct ways (unclosed/nested/tilde/indented/CRLF fences); fixed by
   reusing `plan_tool/jira_grade.py`'s existing correct fence scanner
   instead of a third from-scratch regex. #357 (judged bare-gap classifier consuming
   this field) is unblocked but remains an investigation, not a seed: name
   the closed vocabulary, false-positive mode, and a refuting fixture first,
   per this arc's Evidence requirements and
   `docs/explanations/nondeterministic-plan-design.md`'s Rule 3 ("climb the determinism
   ladder before adding a judge").
10. **Withdrawn 2026-09-15 (owner-confirmed):** `orchestrator-owned-convergence-eval`
    did not earn implementation. 25 bare-plan audits across 2026-09-14/15
    never converged — the scope moved under the audit four times (four
    evidence contexts to one, 13 steps to 8, persistent run logs to none),
    and each reshape brought new surface rather than the same gap recurring.
    The conceptual reason: after the v1 narrowing the evaluator's eligibility
    gate leaves the judge almost nothing to decide (at most `converged` vs
    `continue` on a qualified low-yield report with remaining material
    findings), a choice the orchestrating session driving `plan-tool` can
    already make with more evidence than the evaluator's envelope permits
    (history, live code, the source seed) and without stacking a second judge
    on top of the audit. Keep the convergence pause in the driving workflow
    (per item 1 above); do not recreate it as a judged CLI route. The plan and
    its plan-details bundle moved to `docs/implementation-plans/archive/` with
    a superseded banner; its seed moved to `plan-seeds/archive/`. The
    evaluator-adapter and governance proposals tied to this evaluator were
    retired as moot; their former IDs do not identify current backlog work.
    #376 shipped in 1.2.0 (2026-11-05): `completeness-apply`, `direct-run`,
    and `direct-jira` were removed and conceptual findings are applied by
    judged edits in the driving session. #369 stays live for the remaining
    `apply_finding` authority inventory, decoupled from the evaluator's
    evidence gate.
11. **#490 is `ready`.** Record an operator's decision on an audit finding
    (`declined`, `accepted-risk`, `reopened`, each with a reason) and show it
    to the next audit, so a settled finding is not re-reported as new while
    its cited text is unchanged. A disposition is evidence of a human call, not
    a classifier: it changes how the report presents a finding, never blocking
    or exit behavior.

## Evidence requirements

- Every proposed signal names its source data, false-positive mode, and a test
  fixture that would refute it.
- A finding that recurs after an edit is traced through git history before it
  becomes evidence for a split, scope-out, or re-seed.
- Measurement steps may close with "no action". Do not turn a negative result
  into a weaker implementation just to keep the arc moving.
- An independently generated report pair with uncertain finding identity is
  evidence for operator review, never evidence for a convergence confirmation.

## Exit and handoff

The arc ends when the tool can state what it knows about a trajectory, what it
does not know, and which operator action remains judgment-owned. It does not
turn those limits into a hidden causal classifier.

## Out of scope

This arc does not widen a retired trajectory mechanism, change blocking merely
to reduce report counts, or automate a decomposition decision.
