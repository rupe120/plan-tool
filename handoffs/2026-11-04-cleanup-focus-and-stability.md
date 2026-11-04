# Cleanup for focus and stability

This handoff carries the recommended next cleanup after Jira-grade retirement.
It authorizes no implementation: the current request is to preserve the pickup
context. The backlog remains the queue and scope owner.

| Item | Pickup state |
| --- | --- |
| Baseline | `main` at `b462cce81`; implementation PR #160 and plan-status PR #161 are verified merged |
| Recommended main effort | BACKLOG #376: retire conceptual auto-apply and its direct pipelines |
| Existing plan | [Completeness Apply Retirement](../docs/implementation-plans/2-completeness-apply-retirement.md), planning, six steps, 0/6 detailed, no execution |
| Next action | Re-ground the existing bare plan against current code, correct stale references, and audit before detail authoring |
| Validation status | This recommendation has source inspection only; no new reproduction, test run, or plan audit certifies it |

## Recommended sequence

Keep each effort independently reviewable. Do not turn these recommendations
into one combined cleanup plan.

| Priority | Work and owner | Intended result and route |
| --- | --- | --- |
| 1 | [BACKLOG #376](../BACKLOG.md): retire `completeness-apply`, `direct-run`, and `direct-jira` | Remove competing conceptual-mutation routes, including the interactive apply walk and its parallel worker/replay machinery. Resume the existing plan. |
| 2 | [BUG_BACKLOG](../BUG_BACKLOG.md): duplicated conceptual-correctness findings; valid method citations reported missing | Render each finding once and resolve supported class-method citations correctly. Use separate direct fixes with focused regression tests and the direct convergence loop. |
| 3 | [BUG_BACKLOG](../BUG_BACKLOG.md): full-suite subprocess/worker failures and `GateCleanCandidate` forward-reference failures | Reproduce each reported failure before choosing a fix. Treat unconfirmed causes as investigations; do not widen timeouts or alter model initialization speculatively. |

The latest retirement validation reports 14,916 passed and 67 skipped, with two
independent clean code reviews. That evidence belongs to the merged retirement,
not to a claim that the older intermittent failures reproduce now.

## Main effort: #376 boundary

The supported conceptual-finding workflow will be: read the saved report,
exercise judgment, and apply a bounded edit in the driving session. Retire the
three commands, their hidden callers, help/reference entries, apply-only
machinery, and current instructions. Preserve existing reports, annotations,
sidecars, and run-log readability.

Preserve create/detail deterministic well-formedness repair and existing
reconcile behavior. Do not retain a renamed private conceptual auto-apply
route, introduce a workflow engine, migrate historical artifacts merely to
remove vocabulary, or redesign audit blocking and exit-code policy.

[BACKLOG #369](../BACKLOG.md) separately owns the inventory of other
`apply_finding` authorities. Do not infer that every caller belongs in #376
because it shares a function name. Reconcile the plan's broad “anywhere” intent
with its explicit caller exclusions before expanding any scope.

### Known plan drift to resolve before detail

Source inspection identifies these concrete pickup issues:

- Step 1 proposes reusing Jira-grade hand-fix wording “for every grade.” Jira-grade
  inputs and selectors are retired; ground the instruction in the surviving
  run-grade reporting route.
- Step 5 names obsolete documentation locations, including
  `docs/reference/COMMANDS.md`, `USE_CASES.md`, and `docs/how-to/roadmap-demo.md`.
  Resolve current owners rather than recreating former files.
- Step 6 says to close BACKLOG #367. This effort is #376; #367 owns a separate
  completed brief-rebind confirmation contract.
- The plan predates the merged grade retirement. Inventory live callers and
  references again; do not treat its file list or assumed implementation
  boundaries as current evidence.

## Pickup procedure

1. Fetch current `origin/main`, preserve unrelated changes, and start a focused
   branch. Read [BACKLOG #376 and #369](../BACKLOG.md), the existing plan and
   [canonical driving directives](../integrations/shared/DIRECTIVES.md).
2. Verify the current tracking/promotion record through
   [the tracking workflow](../docs/TRACKING.md). Reuse the existing plan and
   seed; do not create a competing retirement effort.
3. Before execution, use code-canonical reconciliation to re-ground the plan
   when needed. Search by command identifiers and by concepts such as
   conceptual application, unattended pipelines, and parallel replay. Record
   the site inventory and every retained caller's reason before editing.
4. Correct the bounded plan drift, commit, then run the bare-plan
   `completeness-audit --iterate --commit`. Read the saved report and apply
   judged plan-level corrections through the session. Follow the directive
   convergence and scope-discussion rules; missing details are not defects.
5. Author details without iteration, then complete the detail-grounded audit.
   Present the corrected scope for review before implementation; the user
   request for this handoff is not approval to execute the cleanup.
6. Once execution is authorized, follow the normal plan PR, green-step,
   plan-canonical code-reconciliation, code-review, and implementation PR
   gates. Do not run plan-mutating reconciliation against executed work.

Use explicit `--backend codex --model gpt-6.1-sol` for model-backed work, per
the newer owner decision in the shared directives. Commit before long
`plan-tool` calls, pass `--commit` where supported, and monitor each command
to completion. This handoff starts no command or audit.

## Evidence for the smaller follow-ups

- `plan_tool/completeness_report.py:build_report_md` renders a dedicated
  conceptual-correctness section and appends the full grouped report.
  BUG_BACKLOG records a duplicate finding in a real saved report. Confirm
  existing rendering tests before changing the embedded report; standalone
  grouped output must retain its correctness findings.
- `plan_tool/data_contract.py:_module_level_symbol_exists` checks module-level
  names. BUG_BACKLOG records valid `Class.method` citations rejected as missing.
  Confirm the supported dotted-symbol cases and existing tests; preserve
  rejection of genuinely absent symbols. Bare-filename guessing and prose
  negation inference remain separate, unresolved design questions.
- The intermittent-test entries name a short subprocess wait, a direct-run
  worker crash, and Pydantic forward-reference resolution. #376 may remove the
  direct-run test altogether; re-check what remains after retirement rather
  than stabilizing a test for a command being removed.

## Deferred work

Broad consolidation, compact-detail redesign (#149), new convergence
heuristics, and expanded telemetry are not part of this cleanup. Shared
terminal-failure receipts remain a separate cross-command contract. The
pre-existing Jira export collision with a missing custom detail destination
remains tracked in BUG_BACKLOG; grade retirement does not resolve it.

The [retirement review ledger](2026-11-03-jira-grade-retirement-plan.md)
retains the prior implementation's tests, findings, and dispositions. Its PR
publication instructions are historical after the verified merges above.
