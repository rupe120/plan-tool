# Sibling planned Input paths pickup

## Current route

The plan PR #98 merges at `313c60536`. The implementation on
`run/sibling-planned-input-paths` completes all three steps. Delivery-PR
publication and merge remain pending; the isolated Integration replay stays paused.

Sibling selection is same-owner accepted-roadmap membership for a
roadmap-derived audited plan; otherwise repository-manifest plans. Only
explicit creates grant absent-file exemptions. Undeclared and edit-only
missing paths and stale symbols in existing files remain findings. Unknown,
malformed or conflicting identity cannot widen selection. Resolved structural
source ownership wins over the output plan directory.

## Implementation and verification

- Selector: `373997be9`; both Input consumers: `bf44003f3`; docs/source-bug
  retirement: `9117f36a7`. Green plan checkpoints include `4deb27cf3`.
- Confirmed identity corrections: `f1f097d5e` (malformed marker and explicit
  null fallback), `0f02d7c5d` (structural owner), `a25fd51f7` (null fields with
  valid lifecycle tracking). The regressions fail before their corrections.
- Final affected-module check: 1,198 passed, 1 skipped. Final full suite:
  **14,558 passed, 67 skipped** in 47.16 seconds. Logs are task-prefixed under
  `.tmp/`. Selector mutation checks reject dropping sibling selection and
  disabling same-owner matching. Both consumer routes and existing-symbol
  validation have focused regression coverage.
- Backend-committed tests trigger false authorship failures for steps 1–2.
  Inspection, mutation checks and independent full suites precede documented
  `run --step N --accept --commit` recovery. Each acceptance reruns the suite;
  no exemption is added. Existing BACKLOG #87 carries this reproduction.
- Complete `reconcile-code --all --no-walk -y` sweeps cover steps 1–2 and skip
  non-code step 3. Reports: `20261016-025056` / `025124` (malformed marker),
  `025457` / `025525` (source owner), `025917` / `025941` (clean). All six JSON
  reports are tracked in the plan detail reports directory. After sweep 3,
  the focused tracked/null correction uses its reproduced matrix and tests
  rather than another full sweep.
- The changelog fragment is `changelog.d/sibling-planned-input-paths.md`.
  No CLI, schema, shared identity-reader or lower validator change is present.
- Independent review findings and final review closure belong in
  [the review ledger](sibling-planned-input-paths-code-review.md).

## Delivery and next action

The final independent review window converges with two consecutive clean
passes against logic `a25fd51f7`. Publish the code PR after
branch-specific user approval required by the shared directives. Keep the
plan gate unchanged. After the code PR merges, fetch and verify the merged
snapshot in the actual installed tool source before resuming the saved replay.

## Resume the isolated Integration replay

Use the experiment's independent repository and accepted roadmap store. Verify
its recorded stop and installed tool version before resuming. Repository identity
must come from its contents and recorded inputs, not its temporary directory name.

Copy: `/private/tmp/integration-roadmap-plan-regeneration-20261015`, independent Git,
branch `experiment/roadmap-plan-regeneration`, no remote. Latest replay stop
commit `f74956b`; source Integration checkout remains unchanged. Results:
`docs/experiments/roadmap-plan-regeneration/README.md` and `result.json`.
Two of nine base plans exist. Connector has 4/4 details and passes both gates;
catalog has 6/6 details and zero conceptual findings but eight deterministic
false positives in `20261016-003744-completeness`. Seven seeds wait.

After the verified fix is delivered to the actual installed tool source, record
its exact commit and resume in that copy with:

```bash
plan-tool --backend codex --model gpt-6.1-sol completeness-audit workflow-catalog-core --iterate --audit-passes 1 --commit -y < /dev/null
```

Do not re-create those two plans, ignore the gate, manufacture placeholders or
remove truthful future Input contracts. Continue the remaining accepted order
only after the catalog gate clears. The test permits plan authoring and audits,
not Integration application execution or provider probes. All later Codex calls use
gpt-6.1-sol under explicit session direction.
