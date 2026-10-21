> **Auto-archived**: this plan was swept on 2026-08-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Restore saved coverage when reusing a completeness audit

## Summary

Thread step 1’s saved conceptual-audit coverage result through the accepted reuse path in `plan_tool/cli/completeness_cmd.py`. Reused audit-only and `--iterate` runs must give the same known or unknown coverage result to the existing Markdown and JSON renderers, without calling Claude again. Keep `plan_tool/completeness_report.py:ReusableAudit` as the single read seam and preserve the current reuse, freshness, sidecar, and grade rules. On green, a fingerprint-fresh reused audit reports its original budget-limited or low-yield verdict everywhere the fresh audit would report it.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the reuse-time coverage wiring.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — The report mismatch this step removes.
- [Input](#input) — Saved coverage and command-flow contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed by this step.
- [Implementation](#implementation) — Required reuse routing and invariants.
- [Tests](#tests) — Focused coverage for audit-only and iterate reuse.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary references for the no-call and JSON boundaries.
- [Applicable guardrails](#applicable-guardrails) — Plan fences that limit this work.
- [Deferred](#deferred) — Related work left outside this step.

## Why

`plan_tool/cli/completeness_cmd.py:finalize_completeness_run` currently supplies fresh local budget state to `plan_tool/cli/completeness_phases.py:_render_completeness_json` and `_render_grouped_report`. When `_resolve_audit_reuse` skips the conceptual audit, that local state is empty even though the saved findings are fresh, so the report can lose a budget-limited or confirmed-low-yield verdict. Reuse must carry the saved provenance beside the reused findings so reports describe what the original audit established.

## Input

- **Step 1 outcome:** Step 1 provides one normalized known-or-unknown coverage result through `plan_tool/completeness_report.py:ReusableAudit` and makes the persistence writer accept selected coverage. This step transports that result and chooses the fresh producer for each non-reuse branch; it does not normalize or infer coverage again.

- **Reuse decision contract:** `plan_tool/cli/completeness_cmd.py:_resolve_audit_reuse` returns reused findings or `None`, while `plan_tool/cli/completeness_cmd.py:_accept_reuse` already carries the saved audit-shape advisory through an additive output channel. Preserve the findings return contract that callers and tests use.

- **Renderer contract:** `plan_tool/cli/completeness_phases.py:_render_completeness_json` and `_render_grouped_report` consume the conceptual audit’s coverage input. Use the API landed by step 1 rather than rebuilding a default coverage dictionary in the command. Known coverage renders `evidence_status: "observed"`; a coverage-less legacy reuse renders `evidence_status: "unknown-legacy"`, null verdict-bearing fields, and Markdown’s explicit unknown-confidence notice.

- **Iterate contract:** `plan_tool/cli/completeness_cmd.py:_run_iterate_convergence_loop` stores the up-front conceptual-audit result in `_audit_budget` and passes it to `plan_tool/cli/completeness_phases.py:write_pre_apply_audit_checkpoint`. A reused iterate run must seed that same coverage result before the checkpoint and final report paths consume it.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/completeness_report.py` — Keep `ReusableAudit` and `resolve_reusable_audit`’s command-facing coverage access aligned with step 1’s known-or-unknown result, without changing fingerprint freshness.
  - `plan_tool/cli/completeness_cmd.py` — Carry accepted reused coverage through audit-only and iterate control flow to the existing report renderers and checkpoint path.
  - `tests/test_completeness_report.py` — Extend reusable-sidecar fixtures and assertions for the command-facing known and unknown coverage result.
  - `tests/cli/test_completeness_cmd.py` — Cover coverage handoff, audit-only reuse, iterate reuse, and the no-Claude-call boundary.

## Implementation

- **Foundational logic: coverage selection before every sink.** Select coverage by how the conceptual findings were obtained: use `_noniter_budget` after a fresh audit-only call, `outcome.budget` after a fresh iterate call, and step 1’s saved known-or-unknown result only after `_resolve_audit_reuse` accepts a fingerprint-fresh sidecar. In the iterate reuse branch, select and seed the saved value inside `_run_iterate_convergence_loop` before `write_pre_apply_audit_checkpoint`, then return the same value as `outcome.budget` for finalization. In audit-only and all final paths, give the selected value to JSON, Markdown, and the final sidecar writer; do not claim that finalization can supply an earlier checkpoint.

- **Keep `ReusableAudit` as the read seam.** Have `plan_tool/cli/completeness_cmd.py` consume saved coverage from `plan_tool/completeness_report.py:ReusableAudit`, not from raw `SavedReview` data or `report_md`. `resolve_reusable_audit` must retain its existing plan and code fingerprint verdicts; coverage availability must not make a sidecar fresh or stale.

- **Preserve the reuse helper’s return shape.** `_resolve_audit_reuse` must continue returning the correctness-first findings list or `None`. One suitable approach is to mirror its existing `advisory_out` pattern with an additive coverage output, so accepted reuse returns the saved coverage without widening the findings contract that tests and callers already rely on.

- **Do not select coverage by truthiness.** An unknown result is meaningful evidence that the old sidecar lacks coverage provenance. Keep an explicit accepted-reuse path or source marker so an unknown value cannot fall back to the empty fresh-audit budget and be rendered as an ordinary clean/default result.

- **Use one selected value for audit-only output and persistence.** In `finalize_completeness_run`, pass the selected conceptual-audit coverage result to both `_render_completeness_json` and `_render_grouped_report`, then on to `_persist_and_present_report`. Markdown, `--json`, and a freshly written completeness sidecar must therefore agree on the saved budget-limited, confirmed-low-yield, clean, or unknown state. Keep accepted audit-only reuse’s existing `skip_sidecar_write` behavior.

- **Seed iterate coverage before the checkpoint.** Thread accepted reused coverage into `_run_iterate_convergence_loop` and initialize its conceptual-audit coverage state when it skips the up-front audit. `write_pre_apply_audit_checkpoint` and the returned `_IterateOutcome.budget` must receive that saved result, so the iterate checkpoint and final report do not disagree.

- **Leave fresh and stale behavior alone.** A fresh conceptual audit still supplies the coverage it produced. Missing, stale, declined, and explicitly bypassed reuse still follow the existing fresh-audit branch. An explicit `--audit-passes` suppresses automatic reuse only; an explicit fresh `--reuse-audit` continues to win and reuses without a Claude call, as the current resolver and CLI help promise.

- **Keep the no-call boundary intact.** An accepted reuse must not invoke `plan_tool/review.py:audit_plan_until_stable` merely to restore coverage. The existing reused iterate branch must continue to skip its up-front conceptual audit.

- **Preserve persistence policy while supplying its value.** Preserve audit-only reused runs’ `skip_sidecar_write` behavior and existing Jira-grade reuse rejection and sidecar suppression. This step passes selected fresh or accepted-reuse coverage to the writer that step 1 extended; it does not make reuse write another sidecar or change the sidecar contract.

## Tests

### Tests for this step

- `test_resolve_reusable_audit_fresh` — Extend `tests/test_completeness_report.py` to assert that a fingerprint-fresh sidecar exposes its saved normalized coverage through `ReusableAudit`.

- `test_resolve_reusable_audit_coverage_less_sidecar_is_fresh_and_unknown` — `tests/test_completeness_report.py` proves a sidecar with valid fingerprints but no coverage remains reusable and exposes the explicit unknown result.

- `test_fresh_reused_under_yes_carries_saved_coverage` — `tests/cli/test_completeness_cmd.py` verifies `_resolve_audit_reuse` preserves its findings return order while handing saved coverage to its caller.

- `test_fresh_audit_only_persists_coverage_before_reuse` — `tests/cli/test_completeness_cmd.py` runs a fresh audit-only fixture with a non-default budget verdict, then proves the written sidecar holds it for the following reuse.

- `test_audit_only_reuse_replays_budget_limited_coverage_without_audit` — `tests/cli/test_completeness_cmd.py` verifies reused Markdown and `--json` report the saved budget-limited facts while the conceptual-audit seam is unreachable.

- `test_iterate_reuse_replays_confirmed_low_yield_coverage_without_audit` — `tests/cli/test_completeness_cmd.py` verifies reused iterate checkpoint/final reporting retains the saved low-yield verdict in Markdown and `--json` without an up-front conceptual audit.

- `test_coverage_less_reuse_renders_unknown_without_audit` — `tests/cli/test_completeness_cmd.py` verifies `evidence_status == "unknown-legacy"`, null verdict fields, and Markdown’s explicit unknown-confidence notice without a replacement Claude call.

- `test_explicit_reuse_wins_over_audit_passes` — `tests/cli/test_completeness_cmd.py` preserves the existing precedence: a fresh explicit `--reuse-audit` with `--audit-passes N` returns saved findings and coverage without invoking the conceptual audit.

Every listed test must be green before this step is complete.

## Acceptance criteria

- A fingerprint-fresh reused audit with saved budget-limited coverage renders the same coverage facts in Markdown and `--json` without invoking the conceptual audit.

- A fingerprint-fresh reused audit with saved confirmed-low-yield coverage renders that verdict in audit-only and `--iterate` reuse paths.

- An accepted iterate reuse gives the saved coverage result to both `write_pre_apply_audit_checkpoint` and the final `finalize_completeness_run` report path.

- A coverage-less but fingerprint-fresh sidecar still reuses findings, renders `evidence_status == "unknown-legacy"` with no verdict-bearing default values, and does not make another Claude call.

- Stale, declined, disabled, and explicitly fresh audit paths retain their current audit and freshness behavior.

- Reused audit-only runs retain their current no-new-sidecar behavior, and Jira-grade reuse behavior remains unchanged.

## References

- [Claude Code CLI Reference](https://code.claude.com/docs/en/cli-usage) — Use for the non-interactive execution boundary that reuse must not cross.

- [Python `json` — JSON encoder and decoder](https://docs.python.org/3.13/library/json.html) — Use for preserving the machine-readable known-versus-unknown coverage result.

- [RFC 8259: The JavaScript Object Notation (JSON) Data Interchange Format](https://www.rfc-editor.org/rfc/rfc8259.html) — Use for the JSON object and null interoperability rules behind the public coverage output.

## Applicable guardrails

- **The plan’s intent:** Carry the original coverage provenance to both report surfaces without spending another conceptual-audit call.

- **The plan’s step intent:** Limit this step to reuse-time delivery of saved coverage for Markdown and JSON reporting.

- **The plan’s `## Out of scope`, audit-policy boundary:** Pass through the existing coverage verdict; do not adjust the policy that created it.

- **The plan’s `## Out of scope`, legacy-reuse boundary:** Keep coverage-less sidecars reusable for findings and report their unknown state rather than forcing a fresh audit.

- **The plan’s `## Out of scope`, saved-sidecar boundary:** Restrict changes to the declared completeness reuse path; leave unrelated consumers and persistence behavior alone.

- **The plan’s `## Out of scope`, checkpoint boundary:** Thread coverage into the existing checkpoint call without changing checkpoint identity or migration behavior.

## Deferred

- Checkpoint and final-artifact identity migration — The plan’s separately tracked checkpoint risk owns that concern; this step only supplies the existing checkpoint path with reused coverage.
