# Step 3 — Capture and label fresh cases in disposable worktrees, preserve source histories, and delete scratch reports

## Summary

Create `benchmarks/corpus/completeness-coverage/cases.json` with real, labelled audit cases that satisfy step 1’s corpus contract. Collect every case in a clean disposable worktree, capture the committed repository and prompt-visible identities before a fresh audit, and retain only the required evidence in the corpus. The key decision is that audit reports stay scratch data: preserve the source history and remove reports created by the experiment before removing its worktree. On green, the committed corpus contains eligible cases and explicit exclusions for every manifest-required comparison.

## Table of Contents

- [Summary](#summary) — Reviewer-level description of the captured corpus evidence.
- [Table of Contents](#table-of-contents) — Links to every section in this detail.
- [Why](#why) — Why fresh captures must not alter normal report history.
- [Input](#input) — Step 1’s contract and the audit evidence used for each case.
- [Files (creates vs edits)](#files-creates-vs-edits) — The single committed corpus artifact.
- [Implementation](#implementation) — Capture, labelling, history-preservation, and cleanup rules.
- [Tests](#tests) — Non-code verification for the captured data.
- [Acceptance criteria](#acceptance-criteria) — Observable evidence and cleanup outcomes.
- [References](#references) — JSON, hashing, and worktree references.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries for this measurement-only step.
- [Deferred](#deferred) — Replay, publication, and automation work outside this capture.

## Why

`plan_tool/completeness_report.py:write_completeness_report` saves timestamped reports under the directory returned by `plan_tool/review_persistence.py:plan_reports_dir`, and `plan_tool/completeness_report.py:resolve_reusable_audit` can later read that history. Experimental audits of deliberately varied fixture states must therefore run outside the source worktree and remove their generated reports, or they can make an experiment look like real audit history. A legacy `plan_tool/review_persistence.py:SavedReview` still lacks the complete evidence required by step 1, so the corpus needs fresh, explicitly labelled captures.

## Input

- **Step 1 corpus contract:** Use the completed `COMPLETENESS_COVERAGE_REPLAY_FORMAT.md`, `benchmarks/corpus/completeness-coverage/manifest.json`, and `plan_tool/completeness_coverage_corpus.py` as the only schema, eligibility, ordering, and serialization authority. Do not add fields or relax an admission rule while collecting data.

- **Frozen audit inputs:** Capture each case through `plan_tool/review_persistence.py:AuditInputSnapshot`, including its `capture()` and `revision` behavior. Preserve the captured state rather than rebuilding plan, detail, seed, or project-context identity after the audit.

- **Fresh audit evidence:** Use `plan_tool/review.py:render_plan_audit_prompt`, `plan_tool/review.py:check_plan_audit`, `plan_tool/review.py:audit_plan_until_stable`, and the step-1 `plan_tool/shell.py:claude_invoke` observer through the capture hand-off. Supply an explicit `--audit-passes` value for each collection run, do not request saved-audit reuse, and preserve every prompt and backend recovery attempt's identity, retry state, raw output, and outcome.

- **Scratch-report location:** Treat the outputs of `plan_tool/completeness_report.py:write_completeness_report` as temporary experiment data. Its report directory is determined from the plan path by `plan_tool/review_persistence.py:plan_reports_dir`; inventory that directory before each scratch audit so cleanup never removes a report already present in the committed source revision.

## Files (creates vs edits)

- **New files:**
  - `benchmarks/corpus/completeness-coverage/cases.json` — Commit the complete ordered set of eligible cases and contract-defined exclusions collected from fresh disposable-worktree audits.
  - `benchmarks/corpus/completeness-coverage/fixtures.bundle` — Commit the Git bundle that retains every eligible capture's commit and tree for future corpus verification.

- **Existing files (edits only):**
  - None.

## Implementation

- **Foundational logic: fail-closed fresh-case capture.** Add a case only when step 1’s validator can bind its clean committed worktree, whole-fresh-audit pre-run reuse key, complete ordered attempt trace, audit configuration, authoritative fresh observations, and explicit labels. Record an incomplete, skipped, failed/malformed, or budget-limited series as the contract’s exclusion record with its reason; never fill a gap with an empty value, a copied case, or an inferred label.

- **Use independent committed fixture histories and retain them.** Create each required trajectory in its own disposable worktree from a committed source revision. Make any fixture change there, commit each captured snapshot before auditing it, record its commit and tree identities, and export those objects into `fixtures.bundle` before removing the worktree. A future verifier must resolve both objects from the committed bundle. Do not amend, reset, rebase, or otherwise alter the source branch or its pre-existing reports.

- **Seal the runtime and capture authority at the audit boundary.** Before each fresh audit, verify that the model-visible source-root inventory exactly matches the committed tree and has no ignored or untracked readable path. Enable capture mode, which suppresses prompt-budget and shell-backstop telemetry writes under that root, then capture the `AuditInputSnapshot` revision and every rendered-prompt and backend recovery attempt's identity, carried context, retry state, raw output, outcome, final coverage, and configuration from the same committed state. Treat labels as authoritative only when the complete series conforms, contains no skipped, failed/malformed, or unrecorded recovery attempt, and is not budget-limited; otherwise record an exclusion.

- **Collect fresh labels even for later reuse comparisons.** Every recorded snapshot needs an authoritative fresh full-discovery observation. The step 2 evaluator will simulate reuse from these ordered records; do not substitute a reused saved report for the current snapshot’s fresh labels.

- **Label findings explicitly and retain their evidence.** Before capture, use the manifest's versioned registry. For each assignment, retain the raw response bytes and digest, attempt index, and parsed recommendation reference that the declared label summarizes. A reviewed explicit registry mapping is the only cross-snapshot identity; recommendation IDs, anchors, and prose stay provenance only. An unmapped or ambiguous fresh finding is an unresolved exclusion, not a newly inferred label.

- **Exercise the declared comparison set.** Populate every manifest-required candidate trajectory and branch with distinct committed source histories. Use selectable intervals of at least two. Record snapshot zero as full discovery; then include changed-input forced discoveries, interval-due full discoveries, unchanged reuse-eligible snapshots that carry the complete predecessor label set, and terminal confirmations exactly as the manifest requires.

- **Keep source and scratch state separate.** `plan_tool/cli/gitcommit.py:worktree_add`, `worktree_remove`, and `worktree_prune` show the repository’s linked-worktree lifecycle. One suitable approach is a unique scratch branch per trajectory, but the required result is isolation: the source checkout remains unchanged while the disposable worktree carries the experiment.

- **Clean reports after every snapshot.** Before each audit, inventory its `plan_reports_dir`. Immediately after that snapshot, transfer the capture evidence, remove only report and sidecar paths absent from the inventory, and assert the scratch worktree is clean before the next fixture commit or audit preflight. Retain the same inventory comparison and final registered-worktree check before removing the disposable worktree, so reports that belonged to the source revision remain untouched.

- **Serialize through step 1’s contract.** Use the step 1 corpus serializer and validator before committing `benchmarks/corpus/completeness-coverage/cases.json`. Preserve declared trajectory and snapshot order; do not sort records merely for convenience.

- **Do not reuse unrelated capture paths.** `plan_tool/scenario_capture.py:capture_scenario` permits best-effort and dirty-state telemetry, while this corpus requires strict admission. Keep the formats separate.

## Tests

This non-code step adds no test module. Run the step 1 corpus contract suite as the data validator.

### Verification (non-code step)

1. `tests/test_completeness_coverage_corpus.py` — Run the step 1 corpus loader and validator against `benchmarks/corpus/completeness-coverage/cases.json`.

2. **Fresh-audit verification** — Inspect every eligible record and confirm it has an explicit fresh audit configuration, captured prompt-visible identity, committed worktree identity, and declared labels.

3. **Trajectory verification** — Cross-check `benchmarks/corpus/completeness-coverage/cases.json` against `benchmarks/corpus/completeness-coverage/manifest.json` and confirm every required comparison uses the required ordered snapshots and independent source history.

4. **Runtime and trace verification** — Confirm capture mode created no source-root telemetry/runtime state before a prompt and that every backend recovery attempt has raw output and a linked rendered prompt. Confirm an opaque retry becomes an exclusion.

5. **Label verification** — Confirm every label exists in the manifest registry and points to raw fresh output, a digest, an attempt, and a parsed recommendation reference. Confirm unmapped or ambiguous findings are unresolved exclusions rather than identifier or prose matches.

6. **Exclusion verification** — Confirm every failed admission, including a visible ignored/untracked path, source-root runtime write, opaque retry, or missing bundle object, remains visible with a contract-defined reason and cannot be mistaken for an eligible case.

7. **Source-history verification** — Compare each source checkout’s branch and `HEAD` before and after collection; they remain unchanged and clean. Verify `fixtures.bundle` resolves each eligible record's commit and tree after the linked worktree is removed.

8. **Scratch-cleanup verification** — For every snapshot, compare the report inventory before and after cleanup and confirm the worktree is clean before the next fixture commit or audit. At the end, generated reports are gone, pre-existing reports remain, and no scratch worktree stays registered.

## Acceptance criteria

- `benchmarks/corpus/completeness-coverage/cases.json` loads and validates through the step 1 corpus contract.

- Every eligible case records the complete committed worktree, whole-fresh-audit pre-run key, ordered attempt trace, audit configuration, and authoritative fresh-label evidence required by step 1.

- Every manifest-required reuse, changed-input, full-discovery, and terminal-confirmation comparison has real ordered snapshots from independent committed fixture histories.

- Every trajectory records snapshot-zero, changed-input, interval, reuse, and terminal outcomes under the manifest's fixed observation policy.

- Every selectable candidate has an interval of at least two, and every reuse record carries its authoritative predecessor's complete label set.

- Each fresh label has an explicit declared scope; no label is inferred from recommendation prose, anchors, filenames, or a legacy sidecar.

- Each label has a manifest registry id and retained raw fresh-output evidence; an unmapped or ambiguous finding remains unresolved.

- Every incomplete capture is retained as an explicit exclusion with a reason and never counts as coverage.

- Source branches, commits, and pre-existing reports remain unchanged after collection.

- `fixtures.bundle` resolves every eligible commit and tree after its disposable worktree is removed, and an ignored or untracked model-readable path makes a capture ineligible.

- Capture mode leaves no telemetry/runtime path under the model-readable root before a prompt, and every backend recovery attempt is retained or makes the case ineligible.

- Scratch reports and sidecars created by each collection audit are removed before the next snapshot and before their disposable worktrees are removed.

- The only committed artifacts from this step are `benchmarks/corpus/completeness-coverage/cases.json` and `benchmarks/corpus/completeness-coverage/fixtures.bundle`.

## References

- [Python 3.13 json — JSON Encoder and Decoder](https://docs.python.org/3.13/library/json.html) — Use its stable encoding options through the step 1 serializer.

- [Python 3.13 hashlib — Secure Hashes and Message Digests](https://docs.python.org/3.13/library/hashlib.html) — Review SHA-256 identity handling used by captured audit inputs.

- [RFC 8785 — JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785.html) — Preserve stable JSON bytes and semantic record ordering.

- [Git worktree documentation](https://git-scm.com/docs/git-worktree) — Review linked-worktree creation, removal, and pruning behavior for disposable captures.

## Applicable guardrails

- **The plan’s “## Plan intent”, evidence-bound measurement:** Limit this step to collecting evidence. Do not add a cache, a re-check lane, or a cadence decision.

- **The plan’s “## Step intent”, fresh-case evidence:** Capture every required branch from fresh labelled observations and leave incomplete legacy evidence excluded.

- **The plan’s “## Out of scope”, audit behavior and CLI surface:** Do not change completeness prompts, budgets, gates, exit behavior, saved-report semantics, or command surfaces.

- **The plan’s “## Out of scope”, label and decision policy:** Do not add prose matching, inferred labels, automatic selection, or unrelated benchmark coverage.

## Deferred

- `plan_tool/completeness_coverage_replay.py` schedule evaluation — Step 2 owns deterministic replay, losses, unresolved comparisons, and terminal results.

- `docs/COMPLETENESS_COVERAGE_REPLAY_RESULT.json`, `docs/COMPLETENESS_COVERAGE_REPLAY_REPORT.md`, and `BACKLOG.md` updates — Step 4 owns publication and the resulting status decision.

- Automated corpus-capture tooling — A future implementation or reconcile step may consider shared capture helpers only after this manual evidence collection proves the needed workflow.

- BACKLOG #173 cache and re-check behavior — Remains outside this measurement until the published replay result permits a scoped follow-up.
