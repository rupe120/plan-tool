# Roadmap plan derivation implementation

## Current testing direction

Owner decision, 2026-10-16: stop at base plans and focus the next tool iterations on application business logic. The [base-plan testing workflow](2026-10-16-roadmap-business-logic-base-plan-loop.md) is the current pickup record. It supersedes further detail authoring and broad infrastructure experimentation. Eight candidate base plans are captured; two delivery rows remain seeds. The identical-seed control completes and demonstrates local References retention. Earlier in-progress notes below are dated implementation provenance, not the current testing instructions.

## Current checkpoint

PR #106 is merged at origin/main f1cba286a. Implementation branch implement/roadmap-plan-derivation uses the independent clone /private/tmp/plan-tool-roadmap-plan-set-20261016. Steps 1–4 are green through run --accept --commit and full plan test gates. Step 5, the matched isolated Integration comparison, remains pending. The claimed outcome requires improved plan boundaries, not context retention or added steps alone.

## Execution evidence

All model-backed runs use explicit clone PYTHONPATH, backend codex and gpt-6.1-sol. Refresh origin/HEAD from Bitbucket before run: this clone inherits a stale investigation-branch pointer; the official remote reports main. No merge-check bypass occurs.

Backend calls commit code/tests before returning, so the post-call dirty-file test-authoring gate misses those committed deltas. Verify each actual commit, then certify via native run --accept --commit with the full plan test command. Keep the test gate enabled. BUG_BACKLOG.md records the issue separately; its repair is outside #496.

- Step 1: 7bc7aff8b, mapping prompt and tests; 31 focused checks, 23 removal mutations, roadmap tests 592 passed/65 skipped. Native run 2026-10-16T17-11-50+00-00-1e4c8f records the authorship limitation. Full gate accepts the step.
- Step 2: 8bc83ec59, seed prompt and tests; 72 focused checks, seven mutation checks, full suite 14,622 passed/67 skipped. Native run 2026-10-16T17-15-25+00-00-1abf9c. Full gate accepts the step.
- Step 3: 85adfc1d4, create References retention and integration regression; affected tests 1,646 passed/65 skipped, full suite 14,631 passed/67 skipped; five retention mutations fail. Native run 2026-10-16T17-20-36+00-00-405231. Full gate accepts the step.
- Step 4: f9d858f9f, both seed handoffs and guide; affected tests 1,646 passed/65 skipped, final regression and proof-removal mutation verified. Full gate accepts the step.

## Remaining work

Run step 5 without mutating the real Integration checkout or frozen accepted source. Compare fresh mappings with equivalent upstream inputs, and compare both handoffs from the same accepted mapping separately. Preserve raw output before repairs and assess plan-level granularity explicitly. Source artifacts remain available in the frozen Integration experiment. No application or provider execution is authorized. Then drive plan-canonical reconcile-code sweeps and code review under the directives; user owns the separate Claude Code review session. Do not claim that review has run here.

## Reconciliation checkpoint

Sweep 1 covers all four code steps (non-code step 5 skipped), reports 20261016-175738 through 20261016-180057. Steps 1/2/4 are clean; step 3's medium step3-run-reconcile-9104ee21 is confirmed coverage debt: parameterizing resume does not exercise cached preparation, and the helper-only restoration check does not reach successful continuation/finalization. Five existing disputed tests pass before the fix. Identifier and vocabulary enumeration is retained in task-specific triage scratch.

Commit 30534a842 adds actual checkpoint reuse across a selected-source change and successful normalized reference refresh/finalization. Full suite: 14,633 passed/67 skipped. Disabling raw-source Reference capture makes both new tests fail, and exact source restoration is verified. No production code changes are necessary for that finding. Sweep 2 covers all four code steps, reports in the 20261016-1805 through 1807 range, with zero recommendations in every report. No third full sweep is warranted on this clean result.

The nested step-5 benchmark attempt cannot initialize Codex and records a blocked sample. The parent session resumes in its functioning execution context: baseline tool f1cba286a, candidate tool 5433b3a53, independent Integration and tool clones under /private/tmp/roadmap-plan-derivation-comparison-20261016. A scratch-only fixed-upstream invoker supplies identical accepted stages 1–3, using the native runner and real Codex generation for stage 4. Baseline accepts five rows (version 20aabc077c6c338ddbfc84ccddf3bd560a0ee0e3bd5b3d6c62afb68fe8adc8cc); candidate accepts ten (version f373ddd13c76d8dd46791f69d9dd75cf69b604da9f054298e9813b2dca8653fb). All five baseline and ten candidate seeds materialize. Raw plan creation is in progress. No improvement or shipment is established by counts alone.

## Code-review convergence

Two independent completed Codex CLI reviews cover f1cba286a..c9df62518 using codex review --base f1cba286a with model gpt-6.1-sol. Both report no actionable regressions and independently run the affected create/roadmap modules: 1,648 passed/65 skipped. No logic changes occur between the two reviews. Reviewed-range/method metadata, final reports and progress logs remain under .tmp/roadmap-plan-derivation.code-review-{1,2}.*. These are Codex reviews, not Claude Code skill runs; the user owns that separate session. Full suite for the reviewed code: 14,633 passed/67 skipped. Code-review convergence does not establish the still-running benchmark's granularity outcome.
