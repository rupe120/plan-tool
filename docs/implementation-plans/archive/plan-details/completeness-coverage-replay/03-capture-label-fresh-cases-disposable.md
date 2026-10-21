# Step 3 — Capture and label fresh cases in disposable worktrees

> **Withdrawn 2026-08-20 (user-confirmed).** This detail remains provenance only,
> not an implementation instruction. Do not execute it; a future measurement
> requires a new, bounded design after measured operational audit cost.

## Summary

Create `benchmarks/corpus/completeness-coverage/cases.json` and `benchmarks/corpus/completeness-coverage/fixtures.bundle` from real, fresh completeness-audit observations. Collect each trajectory in an isolated disposable worktree, retain its committed source history and audit evidence, and use the capture-only runner so no audit report or telemetry enters that worktree. The key decision is fail-closed admission: only a fully captured, conforming fresh audit can supply labels; incomplete evidence stays visible but cannot count as coverage. On green, every candidate can be evaluated against every eligible case, while unresolved and excluded records remain visible.

## Table of Contents

- [Summary](#summary) — Reviewer-level description of the captured corpus evidence.
- [Table of Contents](#table-of-contents) — Links to every section in this detail.
- [Why](#why) — Why fresh captures must not alter normal report history.
- [Input](#input) — Step 1’s contract and the audit evidence each case needs.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two committed corpus artifacts.
- [Implementation](#implementation) — Capture, labelling, history-retention, and cleanup rules.
- [Tests](#tests) — Data validation and non-code verification.
- [Acceptance criteria](#acceptance-criteria) — Observable evidence and cleanup outcomes.
- [References](#references) — JSON, hashing, worktree, and bundle guidance.
- [Applicable guardrails](#applicable-guardrails) — Boundaries for this measurement-only step.
- [Deferred](#deferred) — Replay, publication, and automation work outside collection.

## Why

`plan_tool/completeness_report.py:write_completeness_report` saves reports in the directory from `plan_tool/review_persistence.py:plan_reports_dir`, and `plan_tool/completeness_report.py:resolve_reusable_audit` can later treat saved evidence as audit history. An experimental audit must therefore not leave scratch reports beside the real plan, where it could affect later reuse or convergence decisions. Existing `plan_tool/review_persistence.py:SavedReview` data does not establish the full evidence step 1 requires, so this step collects fresh, explicitly labelled cases instead.

## Input

- **Step 1 corpus contract:** Use step 1’s landed `COMPLETENESS_COVERAGE_REPLAY_FORMAT.md`, `benchmarks/corpus/completeness-coverage/manifest.json`, and `plan_tool/completeness_coverage_corpus.py` as the authority for record shape, ordering, labels, exclusions, and serialization. Do not add fields or relax admission while collecting cases.

- **Frozen audit inputs:** Capture the prompt-visible plan and detail state through `plan_tool/review_persistence.py:AuditInputSnapshot`, including its `capture()` method and `revision` property, backed by `plan_tool/fingerprint.py:audit_input_revision`. Retain the captured state rather than rebuilding it from later disk reads.

- **Fresh audit series:** Use step 1’s capture-only runner around `plan_tool/review.py:render_plan_audit_prompt`, `plan_tool/review.py:check_plan_audit`, `plan_tool/review.py:audit_plan_until_stable`, and `plan_tool/shell.py:claude_invoke`. It calls the discovery engine directly rather than the completeness CLI, uses the sealed-root read-only profile, and suppresses all audit telemetry writers. `check_plan_audit` can issue a conformance retry and later audit passes carry findings into new prompts, so every rendered prompt and backend attempt belongs in the ordered evidence trace. Retain the final `confirmation_kind`; a non-budget-limited one-pass series is still unconfirmed and cannot label a case.

## Files (creates vs edits)

- **New files:**
  - `benchmarks/corpus/completeness-coverage/cases.json` — Store the ordered eligible cases, unresolved comparisons, and exclusions collected under step 1’s contract.
  - `benchmarks/corpus/completeness-coverage/fixtures.bundle` — Retain the Git objects needed to resolve each eligible capture’s recorded commit and tree after worktree cleanup.

- **Existing files (edits only):**
  - None.

## Implementation

- **Foundational logic: fail-closed fresh-case admission.** Admit a case only when step 1’s validator can bind its clean committed worktree, whole-audit identity, complete ordered attempt trace, audit configuration, and authoritative fresh-label evidence. Preserve incomplete or failed capture as the contract-defined exclusion or unresolved record; never replace missing evidence with an empty value, copied label, or inferred match.

- **Use isolated committed histories.** Create each manifest-required trajectory in its own disposable worktree from a clean source revision. Commit every captured snapshot before auditing it, preserve the original source checkout and its history, and avoid amend, reset, rebase, or report edits there. A unique temporary branch per trajectory is one suitable approach, but isolation and preserved commit identity are the requirements.

- **Capture every fresh observation.** Run the capture-only full-discovery runner for every recorded snapshot, including snapshots that step 2 will later simulate as reuse. Supply a multi-pass cap sufficient to obtain `confirmed-dry` or `confirmed-low-yield`, never a one-pass label collection, and do not request saved-audit reuse. Record candidate-independent ordered position, terminal status, and pre-run reuse key for each snapshot; step 2 derives each candidate’s outcome rather than collection choosing one.

- **Record the complete audit series.** Capture the pre-run reuse key before discovery, then retain every rendered prompt digest, carried-finding state, retry state, backend recovery attempt, raw response evidence, outcome, and final `confirmation_kind`. A skipped, failed, malformed, unrecorded, budget-limited, or unconfirmed series cannot supply authoritative labels.

- **Label only supported findings.** Assign labels through the step 1 registry and preserve the contract-required response evidence for every assignment. A reviewed registry mapping is the only cross-snapshot identity; recommendation identifiers, anchors, filenames, and prose remain provenance only. Record an unmapped or ambiguous finding as unresolved rather than inventing a new identity.

- **Exercise every candidate’s interval.** Collect at least one eligible ordered witness for every selectable candidate that has both an unchanged non-terminal reuse and a later unchanged non-terminal snapshot at which that candidate’s interval makes a periodic full discovery due. A shared trajectory is valid only when it reaches the named interval. Do not let the corpus-wide diversity floor or terminal confirmation stand in for that per-candidate proof.

- **Seal the entire audit lifecycle.** Before an audit starts, confirm the model-visible source-root inventory matches the committed snapshot and contains no readable ignored or untracked path. Run each backend attempt through step 1’s read-only profile, suppress review and shell prompt-budget telemetry, and avoid the completeness CLI so no report or audit-coverage telemetry writer runs. Recheck the sealed inventory after every attempt. If any writer, mutation, or access fence cannot be proven absent, retain the result as ineligible.

- **Retain history before cleanup.** Add every eligible snapshot’s commit and tree to `benchmarks/corpus/completeness-coverage/fixtures.bundle` before removing its worktree. Verify the retained bundle resolves both recorded objects after removal; a worktree path is not retained evidence.

- **Keep capture runtime external and clean.** Keep raw-attempt staging and temporary capture state outside the sealed worktree. The capture runner must create no saved audit report or telemetry there; verify that after each snapshot and before worktree removal. Remove only external temporary data after the required capture evidence has been serialized, leaving any pre-existing worktree state untouched.

- **Serialize through the landed contract.** Use step 1’s corpus serializer and validator before committing `benchmarks/corpus/completeness-coverage/cases.json`. Preserve manifest trajectory and snapshot order; do not reorder records for convenience.

## Tests

Step 3 adds no test module; it supplies real data for step 1’s landed corpus suite.

### Verification (non-code step)

1. **Corpus-contract validation** — Run `tests/test_completeness_coverage_corpus.py` against `benchmarks/corpus/completeness-coverage/cases.json` and confirm the corpus loads without repair or backend access.

2. **Fresh-series verification** — Confirm every eligible snapshot has a committed worktree identity, explicit audit configuration, complete prompt and backend trace, observed coverage, `confirmed-dry` or `confirmed-low-yield`, and authoritative labels.

3. **Comparison verification** — Check `benchmarks/corpus/completeness-coverage/cases.json` against `benchmarks/corpus/completeness-coverage/manifest.json`; every diversity-floor trajectory and branch is represented in the declared order, every selectable candidate has its own reuse and non-terminal interval-due witness, and every eligible case is present in the evaluation universe of every candidate.

4. **Label-evidence verification** — Confirm every recorded label maps to declared registry data and retained fresh-output evidence. Confirm ambiguous findings remain unresolved.

5. **Bundle verification** — Remove each disposable worktree, then verify `benchmarks/corpus/completeness-coverage/fixtures.bundle` still resolves every eligible commit and tree.

6. **Source-preservation verification** — Compare each source checkout’s branch, `HEAD`, source-root inventory, and report/telemetry inventory before and after every backend attempt; the collection does not alter them.

7. **Capture-fence verification** — After every snapshot, confirm no saved report, audit-coverage telemetry, review telemetry, shell telemetry, or other runtime writer entered the sealed source root; the external capture scratch is cleaned only after evidence transfer.

8. **Artifact-scope verification** — Inspect the final change and confirm this step commits only `benchmarks/corpus/completeness-coverage/cases.json` and `benchmarks/corpus/completeness-coverage/fixtures.bundle`.

## Acceptance criteria

- `benchmarks/corpus/completeness-coverage/cases.json` validates through step 1’s landed corpus contract.

- Every eligible case records the complete worktree, whole-audit identity, ordered attempt trace, configuration, candidate-independent policy facts, `confirmed-dry` or `confirmed-low-yield` coverage, and authoritative fresh-label evidence required by that contract.

- Every manifest-required reuse, changed-input, periodic full-discovery, and terminal-confirmation comparison has real ordered snapshot evidence or a visible contract-defined unresolved/excluded record; each selectable candidate has its own reuse and non-terminal interval-due witness; and every eligible snapshot stays in every candidate's evaluation universe.

- No failed, malformed, skipped, budget-limited, unconfirmed, opaque, or incomplete audit series supplies an authoritative label set.

- Every cross-snapshot label identity is an explicit registry mapping backed by retained fresh-output evidence; no prose or identifier matching fills a gap.

- `benchmarks/corpus/completeness-coverage/fixtures.bundle` resolves every eligible capture’s recorded commit and tree after its disposable worktree is removed.

- The capture-only runner leaves no report, audit-coverage telemetry, prompt-budget telemetry, or other runtime writer in the sealed source root; external capture scratch is removed after evidence transfer without changing pre-existing worktree state.

- Collection leaves the original source checkouts and histories unchanged.

- The only committed artifacts from this step are `benchmarks/corpus/completeness-coverage/cases.json` and `benchmarks/corpus/completeness-coverage/fixtures.bundle`.

## References

- [Python 3.13 json — JSON Encoder and Decoder](https://docs.python.org/3.13/library/json.html) — Use stable JSON handling through the step 1 serializer.

- [Python 3.13 hashlib — Secure Hashes and Message Digests](https://docs.python.org/3.13/library/hashlib.html) — Review SHA-256 handling for captured identities and evidence digests.

- [RFC 8785 — JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785.html) — Use it to assess stable serialization expectations for retained evidence.

- [Git worktree documentation](https://git-scm.com/docs/git-worktree) — Review linked-worktree creation, clean removal, and pruning behavior.

- [Git bundle documentation](https://git-scm.com/docs/git-bundle) — Review how to retain the commits and reachable objects needed for later verification.

## Applicable guardrails

- **The plan’s “## Plan intent”, evidence-bound measurement:** Limit this step to collecting evidence; do not add a cache, re-check lane, or cadence decision.

- **The plan’s “## Step intent”, fresh-case evidence:** Capture the required branches from fresh labelled observations and keep incomplete legacy evidence out of coverage.

- **The plan’s “## Out of scope”, audit behavior and CLI surface:** Do not change audit prompts, budgets, gates, exit behavior, saved-report semantics, or command surfaces.

- **The plan’s “## Out of scope”, matching and corpus scope:** Do not add content matching, inferred labels, automatic selection, or unrelated benchmark captures.

## Deferred

- `plan_tool/completeness_coverage_replay.py` schedule evaluation — Step 2 owns deterministic replay, losses, unresolved comparisons, and terminal results.

- `docs/COMPLETENESS_COVERAGE_REPLAY_RESULT.json`, `docs/COMPLETENESS_COVERAGE_REPLAY_REPORT.md`, and `BACKLOG.md` — Step 4 owns publication and the resulting status decision.

- `plan_tool/scenario_capture.py:capture_scenario` integration — Its environment-gated, best-effort scenario telemetry is not strict corpus admission; consider shared capture tooling only after this manual collection proves a common contract.

- BACKLOG #173 cache and re-check behavior — Remains outside this measurement until the published replay result permits a scoped follow-up.
