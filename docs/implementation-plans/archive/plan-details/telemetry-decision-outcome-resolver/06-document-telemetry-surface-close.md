> **Auto-archived**: this plan was swept on 2026-07-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Document the telemetry surface and close BACKLOG #72 phase 3

## Summary

Documents the decision-outcome telemetry workflow in `USE_CASES.md` and registers the new resolver leaf in `CLAUDE.md`'s `## Architecture` section. It then updates `BACKLOG.md` entry `#72` to credit phase 3 as shipped and retain only the producer-side hardening that this plan explicitly deferred. The key decision is to verify steps 1–5 at HEAD before making any shipped claim; a missing command, resolver, or test routes back to its owning step instead of being repaired here. On green, developers can find and interpret `plan-tool telemetry`, and the backlog clearly separates the completed resolver surface from the remaining hardening work.

## Table of Contents

- [Why](#why) — why the shipped telemetry reader needs operator and maintainer documentation
- [Input](#input) — the upstream contracts and plan sections that control these edits
- [Files (creates vs edits)](#files-creates-vs-edits) — the three documentation files changed
- [Implementation](#implementation) — the verification gate and the required documentation updates
- [Tests](#tests) — documentation-focused checks for this non-code step
- [Acceptance criteria](#acceptance-criteria) — observable conditions for completion
- [References](#references) — the plan, tracking entry, and shipped source surfaces
- [Deferred](#deferred) — producer hardening and later scaling work left outside this plan

## Why

Steps 1–5 add the completed-run reader, decision-to-outcome resolver, aggregation and recommendations, and the `plan-tool telemetry` command, but the operator workflow and leaf architecture are not yet described in the scoped documentation. `BACKLOG.md` entry `#72` also still says there is no consumer and lists the resolver as remaining phase-3 work. Leaving those surfaces unchanged would hide a usable command, mislead maintainers about the new leaf, and keep shipped work at the top of the forward-looking backlog. This step reconciles the docs with the completed implementation while preserving the separate producer-hardening work that the plan deliberately leaves open.

## Input

This step consumes documentation and implementation outcomes owned elsewhere:

- **Steps 1–4 provide the analysis surface.** Their completed outcome is a read-only `plan_tool/telemetry_analysis.py` leaf that resolves decisions, aggregates by `(kind, decision)`, and emits advisory recommendations.
- **Step 5 provides the command surface.** Its completed outcome is `plan_tool/cli/telemetry_cmd.py:cmd_telemetry` and `register`, including the optional `--json` output.
- **The plan controls the remaining scope.** Use `docs/implementation-plans/2-telemetry-decision-outcome-resolver.md:## Out of scope` and `## Deferred` as the source of truth for work that must not be described as shipped.
- **The backlog entry is an accumulated credit record.** Preserve the phase-1, schema, and phase-2 linkage credits in `BACKLOG.md:#72 — Decision/outcome telemetry`; add the phase-3 plan credit beside them rather than replacing them.
- **Verification is limited to checked-in state.** Documentation may claim phase 3 shipped only when the expected step 1–5 modules, command wiring, generated command reference, and tests are present at HEAD.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `USE_CASES.md` — add a situation-first entry showing when to run `plan-tool telemetry`, how to read its advisory output, and when `--json` is useful.
  - `CLAUDE.md` — add a sibling Architecture paragraph for the decision-outcome resolver leaf and its command surface.
  - `BACKLOG.md` — update entry `#72` to credit phase 3, remove the resolver and outcome-verdict work from `Remaining`, and retain the producer-side hardening named by this plan.

## Implementation

The foundational rule is: **document only telemetry behavior verified at HEAD, then trim only the backlog work this plan shipped.**

### Verify the shipped surface first

Before editing the three scoped files, confirm the outcomes owned by steps 1–5:

- **Completed-run reading exists.** Check `plan_tool/run_log.py:read_run_events`, `read_run_outcome`, and `RunOutcome`, plus their coverage in `tests/test_run_log.py`.
- **The resolver and aggregation exist.** Check `plan_tool/telemetry_analysis.py:resolve_decisions`, `analyze_decisions`, `render_analysis`, and the leaf-owned JSON projection delivered by steps 2–5. Confirm its tests in `tests/test_telemetry_analysis.py`, including the async join and ownerless-row cases.
- **The CLI is reachable.** Check `plan_tool/cli/telemetry_cmd.py:cmd_telemetry` and `register`, the module's membership in `plan_tool/cli/app.py:COMMAND_MODULES`, and `"telemetry"` in `plan_tool/cli/parser.py:CANONICAL_COMMAND_ORDER`.
- **The command contract is covered.** Check `tests/cli/test_telemetry_cmd.py` and the generated `docs/cli/telemetry.md` delivered by step 5.
- **Stop on a missing dependency outcome.** Route a gap back to the step that owns it. Do not add or repair production code, tests, generated command docs, or capability registration in this non-code step.

### Add the operator workflow to `USE_CASES.md`

Add one entry under `USE_CASES.md:## Use-case catalog`, following the situation → command → result pattern used by the numbered siblings.

The entry should make these facts clear:

- **Use the command to review heuristic outcomes across plans and time.** This is for deciding whether a signal appears over-sensitive, under-used, frequently reverted, or poorly correlated.
- **Show the default command and machine form.** Include `plan-tool telemetry` and `plan-tool telemetry --json`; keep flag-level detail in the generated command reference from step 5.
- **Explain the grouping key.** Results group by `(kind, decision)`, because one kind such as `granularity` can contain several unrelated decisions.
- **Explain the verdicts in operator terms.** Name `acted-on`, `no-op`, `reverted`, and `still-open` without restating the resolver's matching mechanism.
- **Keep recommendations advisory.** State that the command reports counts, coverage, and tuning suggestions but never changes a threshold, plan, or configuration.
- **Treat missing correlation honestly.** Explain that legacy or ownerless events remain counted even when they cannot be joined to a later outcome; low coverage is not the same as a bad heuristic.
- **Link to the generated reference.** Point readers to `docs/cli/telemetry.md` for the command contract and flags.

Renumbering later use cases is acceptable if needed, but preserve every existing entry and keep `USE_CASES.md:## Pick your entry point` focused on choosing an authoring workflow rather than forcing this analysis command into that table.

### Register the leaf in `CLAUDE.md`

Add a sibling paragraph under `CLAUDE.md:## Architecture`, matching the existing one-paragraph-per-leaf convention.

Cover the stable boundaries rather than duplicating implementation detail:

- **Name the owning leaf and command.** Identify `plan_tool/telemetry_analysis.py` as the read-only decision-outcome resolver behind `plan-tool telemetry`.
- **Name its inputs and outputs.** It reads decision telemetry plus existing run-log and report-history evidence, resolves per-event outcomes, then aggregates by `(kind, decision)` into advisory recommendations.
- **Preserve the dependency rule.** The leaf may use the read-only sibling leaves established by steps 1–3 but must not import `plan_tool.cli`; `plan_tool/cli/telemetry_cmd.py` remains thin wiring.
- **Preserve compute-on-read and non-mutation.** Derived verdicts are not a second persisted telemetry store, and the command does not auto-tune or mutate plans or configuration.
- **Mention tolerant coverage.** Ownerless and legacy rows are counted and remain unresolved where their join keys do not support correlation.

Do not repeat the command-registration material already owned by step 5 in `CAPABILITIES.md` and `docs/cli/telemetry.md`.

### Reconcile `BACKLOG.md` entry `#72`

Update `BACKLOG.md:#72 — Decision/outcome telemetry` as an append-only phase ledger:

- **Add the phase-3 credit.** Cite `docs/implementation-plans/2-telemetry-decision-outcome-resolver.md` and state that the resolver, four-verdict model, cross-plan aggregation, advisory recommendations, and `plan-tool telemetry`/`--json` surface shipped.
- **Remove only this plan's completed work from `Remaining (phase 3)`.** The read-only resolver, analysis command, and outcome-verdict derivation must no longer appear as future work.
- **Retain the companion producer hardening.** Carry forward the items from the plan's `## Deferred` section: backend-invocation-failure apply events, canonical-repo telemetry from parallel completeness workers, `_MAX_LINE_BYTES` mitigation, create-outcome fingerprint deduplication, and the named direct regression-test gaps.
- **Make the residual status explicit.** Prefer a short `Remaining (producer hardening)` clause so readers do not mistake those items for missing resolver functionality.
- **Reconcile stale prose within the entry.** Statements such as “still with no consumer,” “no cross-plan/over-time aggregation,” and “no recommend-adjustments analysis surface” must either describe historical phase credit clearly or be rewritten to match HEAD.
- **Preserve still-valid dependencies and cross-entry citations.** References from `#97`, `#117`, and other consumers can continue pointing to `#72` now that its analysis surface exists.
- **Keep or retire the entry consistently.** The recommended approach is to retain `#72` as the tracking home for its explicitly deferred producer hardening. Under that approach, leave `#72` in the priority lenses and do not run a retirement sweep. If repository policy instead requires complete removal once the main capability ships, first move every residual item to an existing named tracking entry; do not invent a new backlog number in this step.

## Tests

No production or unit-test files are changed by this step.

### Verification (non-code step)

- `verify_step_1_to_5_symbols_exist` — confirm the run reader, resolver, aggregation, command handler, dispatch registration, generated command reference, and their test files exist at HEAD before documenting phase 3 as shipped.
- `verify_use_case_command_matches_help` — compare the commands and flags written in `USE_CASES.md` with `plan-tool telemetry --help` and `docs/cli/telemetry.md`.
- `verify_use_case_links` — confirm every new relative link in `USE_CASES.md` points to an existing file or heading.
- `verify_claude_architecture_entry` — confirm `CLAUDE.md:## Architecture` names `plan_tool/telemetry_analysis.py`, `plan-tool telemetry`, the no-`plan_tool.cli` boundary, and the advisory/non-mutating contract.
- `verify_backlog_phase_ledger` — confirm `BACKLOG.md:#72` retains its earlier phase credits and adds the phase-3 plan citation.
- `verify_backlog_remaining_matches_plan` — compare the residual `BACKLOG.md` list directly with `docs/implementation-plans/2-telemetry-decision-outcome-resolver.md:## Deferred`.
- `verify_no_stale_no_consumer_claim` — search the `BACKLOG.md:#72` entry for claims that the resolver, aggregation, or recommendation surface is still missing.
- `verify_scoped_diff_only` — confirm the final diff changes only `USE_CASES.md`, `CLAUDE.md`, and `BACKLOG.md`.
- `verify_documentation_suite` — run the repository documentation and capability checks that cover these files, then run the full test suite if the normal completion workflow requires it.

## Acceptance criteria

- `USE_CASES.md:## Use-case catalog` contains a situation-first entry for `plan-tool telemetry` and its `--json` form.
- The new use-case entry explains `(kind, decision)` grouping, the four outcome labels, low-correlation handling, and the advisory-only rule.
- `CLAUDE.md:## Architecture` contains a paragraph for `plan_tool/telemetry_analysis.py` and accurately states its leaf boundary and command relationship.
- `BACKLOG.md:#72 — Decision/outcome telemetry` credits `docs/implementation-plans/2-telemetry-decision-outcome-resolver.md` for the shipped phase-3 surface.
- `BACKLOG.md` no longer lists the resolver, outcome derivation, cross-plan aggregation, or `plan-tool telemetry` as unfinished work.
- Every producer-hardening item from the plan's `## Deferred` section remains tracked in `BACKLOG.md`, with no new backlog identifier invented.
- Earlier phase-1, schema, and phase-2 credits remain intact in `BACKLOG.md`.
- No production-code, test-code, generated CLI-reference, or capability file is changed by this step.
- All commands, links, file paths, and architecture claims in the edited docs match the checked-in step 1–5 implementation.

## References

- [Telemetry Decision Outcome Resolver plan](docs/implementation-plans/2-telemetry-decision-outcome-resolver.md) — use `## Out of scope`, `## Deferred`, and `## Acceptance criteria` as the authority for shipped and remaining scope.
- [BACKLOG #72](BACKLOG.md#72--decisionoutcome-telemetry--understand-heuristics-across-scenarios-over-time-recommend-tuning) — preserve the accumulated phase credits and reconcile its remaining-work list.
- [Telemetry analysis leaf](plan_tool/telemetry_analysis.py) — verify the step 2–4 resolver, aggregation, rendering, and machine-output symbols before documenting them.
- [Telemetry command](plan_tool/cli/telemetry_cmd.py) — verify the step-5 operator surface and `--json` contract.
- [Completed-run reader](plan_tool/run_log.py) — verify the step-1 run-outcome input used by the resolver.
- [Telemetry command tests](tests/cli/test_telemetry_cmd.py) — verify the read-only, no-Claude, no-mutation, always-exit-0 command behavior.
- [Telemetry analysis tests](tests/test_telemetry_analysis.py) — verify the outcome vocabulary, async join, aggregation, and ownerless-row behavior described by the docs.

## Deferred

- **Backend-invocation-failure apply telemetry** — remains companion producer hardening from the plan's `## Deferred` section.
- **Canonical-repo telemetry from parallel `completeness-apply --jobs N` workers** — remains producer-side routing work outside this resolver plan.
- **Oversized-event handling at `_MAX_LINE_BYTES`** — a dropped-event counter, scoped map, or compact digest needs its own implementation decision.
- **Create-outcome `code_fingerprint` deduplication** — changing the producer shape and join policy is outside this docs-only step.
- **Direct regression tests for apply-loop forwarding and best-effort compute failures** — remain tracked with the producer hardening.
- **Persisted verdict caching and time-windowed log reads** — stay compute-on-read unless measured performance justifies a separate plan.
