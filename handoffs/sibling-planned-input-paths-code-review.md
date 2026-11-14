# Sibling planned Input paths review ledger

| Item | Evidence |
| --- | --- |
| Base | `313c60536` (merged plan PR #98) |
| Latest logic commit | `a25fd51f7` |
| Checks | affected modules: 1,198 passed, 1 skipped; full suite: 14,558 passed, 67 skipped; failing-before-fix identity regressions; selector mutations |
| Reviewer | fresh report-only `codex exec`, `gpt-6.1-sol` each pass |
| Disposition | converged: two consecutive independent clean reviews; delivery publication pending |

The scope is eligible sibling explicit creates in the two Input consumers.
Existing-file symbols stay validated. No CLI/schema/shared-reader changes
belong here. The public validator already normalizes planned paths; testing
its raw private resolver bypasses that contract.

## Findings and dispositions

- Reconcile sweep 1, high, malformed marker with valid plain metadata:
  **fixed `f1f097d5e`**. New audited/candidate regressions fail before correction.
- Review 1 (`origin/main...4deb27cf3`), medium, null identity falls back to
  ordinary selection: **fixed `f1f097d5e`**.
- Reconcile sweep 2, high, and review 2 (`origin/main...f1f097d5e`), P2,
  source structural owner differs from plan output directory:
  **fixed `0f02d7c5d`**. Live/archive × state-present/absent matrix reproduces
  the missing-state failures and preserves existing state-backed behavior.
- Review 2, P2, noncanonical creates strings remain raw:
  **refuted** by real plan and detail consumer tests with `./pkg/future.py`;
  `data_contract._normalize_planned_paths` runs before `_code_anchor_resolves`.
  Both canonical/noncanonical public-route cases pass before any code change;
  keep their coverage. No normalization change is applied.
- Review 3 (`origin/main...61ed10dc2`), medium, tracked null identity bypasses
  conflict checks: **fixed `a25fd51f7`**. Six tracked/null cells fail before
  correction; full state/target/invalid-key matrix passes afterward.
- Executor-committed tests cause the authorship gate to miss committed deltas:
  **tracked BACKLOG #87**. The documented acceptance route reruns gates without
  disabling test authorship enforcement.

## Final review window

Review 4 against `origin/main...a25fd51f7`: **clean**. Method: full diff and
contract/test inspection, tracing both consumer routes and shared readers.
Its read-only pytest attempt cannot create temporary directories; the parent
session supplies the successful focused and full-suite runs.
Review 5 against `313c60536...0fa82819a` (same logic `a25fd51f7`): **clean**.
Method: full diff inspection, selector/public-consumer traces through shared
readers and normalization, regression assertions, plan/details, saved reports,
and handoff/ledger accuracy. No pytest attempt in the read-only reviewer.

The loop closes as **converged**, with two consecutive independent clean
reviews against the latest logic change. No finding remains pending. Delivery
publication and the isolated replay remain separate next actions.

Raw report-only artifacts and command logs use
`.tmp/sibling-planned-input-paths.review-N.*`. Reconcile reports are tracked
under the plan detail bundle; the pickup names all three complete sweeps.
