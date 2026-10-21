> **Auto-archived**: this plan was swept on 2026-07-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Update telemetry docs and retire BACKLOG #72

## Summary

Reconcile the project documentation after steps 1–5 ship telemetry producer hardening. Update `CLAUDE.md` with the final recorder and analysis boundaries, and add an operator workflow, quick-reference entries, storage guidance, and a matching Table-of-contents link to `RUNBOOK.md`. Remove the completed `BACKLOG.md` #72 entry and repair every priority or cross-entry reference that still treats its telemetry capability as future work. On green, the docs match the checked-in telemetry behavior, `plan-tool telemetry` is easy to discover, and `BACKLOG.md` contains no stale `#72` reference.

## Table of Contents

- [Summary](#summary) — The three documentation updates and their final result.
- [Table of Contents](#table-of-contents) — Links to every section in this detail.
- [Why](#why) — Why shipped producer work must leave the forward-looking backlog.
- [Input](#input) — Dependency-step outcomes and plan sections that control the edits.
- [Files (creates vs edits)](#files-creates-vs-edits) — The three documentation files changed.
- [Implementation](#implementation) — The verification gate, backlog retirement, architecture update, and operator workflow.
- [Tests](#tests) — Existing suites that support the documentation claims.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — The plan, tracking entry, and source surfaces to verify.
- [Deferred](#deferred) — Code and broader telemetry work outside this docs-only step.

## Why

`BACKLOG.md` #72 still presents producer hardening as unfinished and names #72 as the next concrete pick, while `RUNBOOK.md` does not expose the shipped `plan-tool telemetry` workflow or list its local decision log. Steps 1–5 close the remaining producer gaps: compact fingerprint storage, unambiguous create assessment joins, failed-invocation apply outcomes, canonical parallel replay recording, and direct best-effort coverage. Keeping #72 in a forward-looking backlog after those outcomes ship would misdirect prioritization, while incomplete architecture and operator docs would hide the behavior that now exists.

## Input

- **Step 1 provides compact code-state telemetry.** Its completed outcome keeps fingerprint-heavy decision events under the existing size boundary while preserving rich maps for structure-inspecting consumers and keeping historical rows readable.
- **Step 2 provides the create parent-child join.** Its completed outcome associates every interactive create outcome with one assessment occurrence without repeating the assessment’s code-state value.
- **Step 3 provides failed-invocation apply telemetry.** Its completed outcome records unusable primary and auto-fix follow-up backend responses as a distinct apply result without changing host return or exception behavior.
- **Step 4 provides canonical parallel ownership.** Its completed outcome makes `plan_tool/cli/completeness_apply_parallel.py:replay_results` the durable writer for the result selected by canonical replay.
- **Step 5 provides the forwarding and best-effort proof.** Its completed outcome covers the three authoritative serial callers, interactive keep/reject ownership, and the code-reveals-split and escalate-to-split producer guards.
- **The plan controls the closure boundary.** Use `docs/implementation-plans/2-telemetry-producer-hardening.md:## Out of scope` and `## Deferred` to decide whether anything remains. The current plan defers no producer-hardening requirement, so unrelated expansions must not keep #72 open.
- **Checked-in state limits shipped claims.** Make the documentation edits only after the dependency outcomes and focused tests exist at HEAD.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `BACKLOG.md` — remove the completed `#72` entry, remove it from the quality and priority roll-ups, point the next concrete pick at the correct remaining item, and rewrite cross-entry references to name the shipped telemetry surfaces instead of a retired backlog number.
  - `CLAUDE.md` — update the existing telemetry Architecture paragraph or paragraphs to describe the hardened producer contract and its relationship to the read-only analysis leaf without duplicating an existing registration.
  - `RUNBOOK.md` — add `plan-tool telemetry` and `--json` to Quick reference, document the local telemetry directory, add an operator workflow, and add the matching Table-of-contents entry.

These three declared files are the complete step-6 edit scope; no production,
test, generated-reference, or data-contract file is changed here.

## Implementation

The foundational rule is: **verify every dependency outcome at HEAD, then retire #72 and replace its forward-looking references with the shipped surface names.**

### Verify the shipped producer surface first

Use the stable owning symbols rather than guessing names introduced inside dependency steps:

- **Compact persistence and compatibility:** inspect `plan_tool/telemetry.py:DecisionEvent`, `record_decision`, `read_decisions`, and `_MAX_LINE_BYTES`. Confirm step 1’s compact code-state contract is present, historical map-shaped or missing values remain readable, and unrelated oversized rows are still dropped whole rather than truncated.
- **Rich-map separation:** confirm `plan_tool/refresh.py:refresh_plan`, `plan_tool/review.py:extract_recommendations`, and `plan_tool/cli/completeness_phases.py:_persist_and_present_report` still retain full maps where per-path comparisons require them.
- **Create association:** inspect `plan_tool/telemetry.py:record_create_granularity_assessment`, `record_create_step_outcome`, and `plan_tool/create.py:_review_step_change_types`. Confirm one assessment occurrence owns its interactive outcomes and the child events do not repeat the assessment’s code-state value.
- **Apply failure classification:** inspect `plan_tool/launcher.py:apply_finding`, `plan_tool/telemetry.py:record_apply_verdict`, and `plan_tool/telemetry_analysis.py:resolve_decision_inline`. Confirm unusable primary responses are represented distinctly and remain mapped into the existing four-outcome analysis vocabulary.
- **Parallel ownership:** inspect `plan_tool/cli/completeness_apply_parallel.py:apply_finding_in_tree`, `replay_results`, and `plan_tool/cli/completeness_cmd.py:_apply_walk_recs_parallel`. Confirm speculative workers and conflict reruns do not write authoritative events and canonical replay records only the selected result with the command’s canonical keys.
- **Forwarding and guards:** confirm the step 5 suites cover the serial loops in `plan_tool/create.py:create_plan`, `plan_tool/detail.py:generate_detail`, `plan_tool/cli/completeness_cmd.py:_run_iterate_convergence_loop`, and `plan_tool/cli/review_actions.py:_build_review_action_fn`.

If any outcome is missing, stop and route the gap to its owning step. Do not edit production code, tests, `DATA_CONTRACT.md`, or generated CLI documentation from this non-code step.

### Retire `BACKLOG.md` #72

Delete the full `BACKLOG.md:#72 — Decision/outcome telemetry` entry. The earlier phase credits and final producer-hardening work remain available in their implementation plans, which is the historical home required by `BACKLOG.md:## Purpose`; do not keep a shipped-status stub.

Sweep every `#72` occurrence in `BACKLOG.md`:

- **Remove it from open-work roll-ups.** Drop #72 from the `heuristic-tuning` current-items roll-up, the T3 tier, and the Readiness lens’s “Highest open by tier” chain.
- **Repoint priority guidance.** Replace the stale `Next concrete pick` recommendation with the actual highest remaining concrete item at implementation time. At current HEAD that is the concrete #97 build, but re-check the surrounding priority list before writing.
- **Replace capability references with live names.** Where another entry still depends on the shipped recorder or analysis, refer to `plan_tool/telemetry.py`, `plan_tool/telemetry_analysis.py`, or `plan-tool telemetry` as appropriate. Do not leave phrases such as “once #72 phase 2–3 lands,” “#72’s deferred analysis surface,” or “gated on #72.”
- **Preserve the other entry’s intent.** References in entries such as #97, #82, #116, and #117 may still describe valid telemetry-backed tuning or reuse. Rewrite those references to the shipped surface rather than deleting the dependency or measurement rationale.
- **Do not invent a replacement backlog item.** The plan’s `## Deferred` states that no producer-hardening requirement remains. Plan-level out-of-scope expansions are not unfinished #72 work.

The end-state check is `rg -n '#72' BACKLOG.md` returning no matches.

### Reconcile `CLAUDE.md` telemetry architecture

Update the existing `CLAUDE.md:Decision telemetry (telemetry.py)` Architecture registration and any neighboring decision-outcome analysis paragraph. Extend the existing text rather than adding a second competing description.

Keep the architecture summary short and cover these stable rules:

- `plan_tool/telemetry.py` remains the local, stdlib-only, best-effort recorder and tolerant reader.
- The code-state field is a compact equality anchor in telemetry; grounding and saved-review flows retain full maps when they need per-path inspection.
- Create assessment events own their shared code-state snapshot, while child outcomes join through one assessment occurrence identity.
- `plan_tool/launcher.py:apply_finding` supplies apply-result classification, including unusable primary responses, while canonical replay owns durable parallel apply recording.
- `plan_tool/telemetry_analysis.py:analyze_decisions` remains compute-on-read and advisory. It does not persist derived outcomes, auto-tune thresholds, or import CLI wiring.
- `plan_tool/cli/telemetry_cmd.py:cmd_telemetry` stays a thin read-only command surface.

Do not repeat field tables or token lists already owned by `DATA_CONTRACT.md`, and do not re-register command or capability metadata owned by earlier plans.

### Add the `RUNBOOK.md` operator workflow

Make the command discoverable in three places:

- **Quick reference:** add `plan-tool telemetry` and `plan-tool telemetry --json` under Discovery & inspection. Describe the first as the human-readable cross-plan outcome report and the second as its machine-readable form.
- **Local storage:** update `RUNBOOK.md:What's in .plan-tool/ (commit vs. delete)` to name `.plan-tool/telemetry/decisions.jsonl` as gitignored, local, append-only analysis input. Deleting it is safe for the application but removes local telemetry history.
- **Workflow and navigation:** add an H2 such as `## Workflow: analyze heuristic outcomes with plan-tool telemetry` and the matching `#workflow-analyze-heuristic-outcomes-with-plan-tool-telemetry` entry under `RUNBOOK.md:Table of contents`.

The workflow should explain:

- Run `plan-tool telemetry` for a repository-wide summary grouped by `(kind, decision)`.
- Use `plan-tool telemetry --json` for scripts and CI-side inspection; keep the complete flag contract linked to `docs/cli/telemetry.md`.
- Read `acted-on`, `no-op`, `reverted`, and `still-open` as outcome counts. Keep `resolved` and `unresolved` separate so missing correlation is not presented as a poor heuristic result.
- Treat recommendations as advisory. `plan_tool/telemetry_analysis.py:analyze_decisions` reports tuning evidence but never changes thresholds, plans, or configuration.
- Expect `No telemetry recorded yet.` with an absent or empty local log; the command still exits successfully.
- Explain the producer-hardening effect briefly: fingerprint-heavy events use a compact code-state identity, failed primary and follow-up applies remain visible, create child outcomes join to one assessment, and parallel or interactive apply records only a canonical landed result.
- State that the command spends no backend call, writes no run log, and does not mutate the plan or telemetry log.

Keep internal persistence detail in `CLAUDE.md` and `DATA_CONTRACT.md`; the runbook should focus on what an operator runs and how to interpret the result.

## Tests

No new unit tests belong to this docs-only step. The dependency suites provide the evidence behind the documentation:

- `tests/test_telemetry.py` — compact persistence, legacy reading, create association, apply recorder shape, and best-effort behavior remain green.
- `tests/test_telemetry_analysis.py` — inline and asynchronous outcomes, aggregation, recommendation coverage, and leaf boundaries remain green.
- `tests/test_create.py` — create assessment ownership and serial apply forwarding remain green.
- `tests/test_launcher.py` — unusable primary responses, ordinary apply recording, suppression, and escalation guards remain green.
- `tests/cli/test_completeness_apply_parallel.py` — speculative suppression and canonical replay recording remain green.
- `tests/cli/test_completeness_cmd.py` — canonical plan fingerprint and run binding remain green.
- `tests/cli/test_telemetry_cmd.py` — text, JSON, empty-log, read-only, registration, and capability contracts remain green.

### Verification (non-code step)

- `verify_dependency_symbols` — confirm every source anchor named in Implementation exists at HEAD before making shipped claims.
- `verify_dependency_suites` — run the focused telemetry, launcher, create, parallel-apply, command, and analysis suites.
- `verify_backlog_retirement` — confirm `rg -n '#72' BACKLOG.md` returns no matches and the replacement priority guidance names an open item.
- `verify_backlog_cross_references` — confirm every rewritten dependency points to a real shipped module or command and no entry still says telemetry analysis is unbuilt.
- `verify_claude_architecture_accuracy` — compare the telemetry Architecture prose with `plan_tool/telemetry.py`, `plan_tool/telemetry_analysis.py`, `plan_tool/launcher.py:apply_finding`, and `plan_tool/cli/completeness_apply_parallel.py:replay_results`.
- `verify_runbook_commands` — compare the documented invocations with `plan-tool telemetry --help` and `docs/cli/telemetry.md`.
- `verify_runbook_toc_anchor` — confirm the new Table-of-contents link points to the exact new workflow heading.
- `verify_runbook_storage_path` — confirm `.plan-tool/telemetry/decisions.jsonl` matches `plan_tool/telemetry.py:telemetry_path`.
- `verify_scoped_diff` — confirm the final diff changes only `BACKLOG.md`, `CLAUDE.md`, and `RUNBOOK.md`.

## Acceptance criteria

- The dependency outcomes from steps 1–5 are present at HEAD before any shipped claim is written.
- `rg -n '#72' BACKLOG.md` returns no matches.
- `BACKLOG.md` no longer lists decision telemetry as open T3 or heuristic-tuning work, and `Next concrete pick` names a currently open item.
- Cross-entry telemetry references in `BACKLOG.md` point to `plan_tool/telemetry.py`, `plan_tool/telemetry_analysis.py`, or `plan-tool telemetry` without claiming the analysis surface is still pending.
- `CLAUDE.md`’s telemetry Architecture text describes compact code-state storage, create assessment joining, failed apply visibility, canonical parallel replay ownership, and advisory compute-on-read analysis.
- `RUNBOOK.md:Quick reference` lists both `plan-tool telemetry` and `plan-tool telemetry --json`.
- `RUNBOOK.md:What's in .plan-tool/ (commit vs. delete)` documents `.plan-tool/telemetry/decisions.jsonl`.
- `RUNBOOK.md` contains the telemetry workflow and a matching Table-of-contents anchor.
- The workflow explains the four outcomes, resolved-versus-unresolved coverage, advisory recommendations, empty-log behavior, and the command’s read-only/no-backend contract.
- `plan-tool telemetry --help` agrees with every command and flag documented in `RUNBOOK.md`.
- The focused dependency suites and the full test suite pass.
- The final diff contains no files outside `BACKLOG.md`, `CLAUDE.md`, and `RUNBOOK.md`.

## References

- [Telemetry Producer Hardening plan](docs/implementation-plans/2-telemetry-producer-hardening.md) — use its Out of scope, Deferred, and Acceptance criteria sections to decide what shipped and whether any residual remains.
- [BACKLOG.md](BACKLOG.md) — use `## Purpose`, the quality and priority roll-ups, and the #72 entry as the retirement and pointer-sweep contract.
- [Telemetry recorder](plan_tool/telemetry.py) — verify the persisted event, compact code-state, create association, apply recorder, size boundary, and tolerant-reader claims.
- [Telemetry analysis](plan_tool/telemetry_analysis.py) — verify the outcome vocabulary, aggregation, recommendations, rendering, and machine-readable projection described to operators.
- [Telemetry command](plan_tool/cli/telemetry_cmd.py) — verify the command’s read-only text and JSON wiring.
- [Apply producer](plan_tool/launcher.py) — verify failed-invocation classification and serial recording behavior before documenting it as shipped.
- [Parallel apply replay](plan_tool/cli/completeness_apply_parallel.py) — verify canonical replay ownership before documenting at-most-once best-effort parallel recording.

## Deferred

- **Production code, tests, and `DATA_CONTRACT.md` changes** — owned by steps 1–5; a verification gap routes back to the owning step.
- **Changes to the four public outcome labels** — excluded by the plan; this step documents the existing vocabulary only.
- **Automatic threshold or configuration tuning** — the analysis remains advisory.
- **A second analytics command, dashboard, cache, or decision log** — outside this plan and unnecessary for closing producer hardening.
- **General telemetry rotation or time-windowed reads** — outside this producer-hardening plan; track separately only if measured storage or performance evidence justifies it.
- **Historical telemetry backfill** — existing local rows remain tolerated, but this step neither rewrites nor reconstructs them.
- **Broad parallel-apply restructuring** — canonical telemetry ownership shipped without changing worker isolation or replay ordering beyond step 4’s scope.
