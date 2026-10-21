> **Replaced**: this file has been superseded by `docs/implementation-plans/2-cross-invocation-audit-history.md`.
> Preserved here for history; do not edit.

# Seed: cross-invocation audit history

## Outcome

`plan-tool convergence <name>` renders a separate, read-only summary of saved
completeness-audit history. It reports a severity-classified pairwise
trajectory only when adjacent reports establish reliable finding identity.
Otherwise it reports `identity-uncertain` with coverage and raw unmatched ids.

## In scope

- Load saved completeness reports for one plan and compare only compatible
  audit stage, detail grade, and sampling configuration.
- Link expected finding identities by reliable anchors; artifact revisions may
  differ between audit runs and do not establish identity themselves.
- Render a distinct cross-invocation history section in the existing
  `convergence` output, with documented state meanings and fixtures.
- Keep the implementation read-only and zero-Claude.

## Out of scope

- New CLI verbs, Claude calls, changed exit codes, gates, or plan mutations.
- Content-based or fuzzy finding matching.
- Changes to #125's severity classifier, #173's caching/recheck design, or
  any confirmation decision when identity is uncertain.

## Acceptance criteria

- Comparable saved reports render a severity-classified pairwise trajectory.
- A single report, incompatible stage/grade/configuration, anchor drift, or
  unmatched ids renders `identity-uncertain` and raw evidence rather than a
  convergence confirmation.
- Existing convergence advisories remain separate and unchanged.
- Tests cover each state, and documentation tells the operator what to do with
  an uncertain result.

## Risks

- Independent audit runs can describe the same concern with different ids or
  anchors. The reader must preserve that uncertainty instead of inferring a
  positive or negative trend.
- Report loading must keep legacy/malformed evidence distinct from current,
  comparable evidence.

## Deferred

- Cross-invocation cache/recheck behavior remains #173.
- Persisted audit-coverage schema versioning remains #301.
- Retry-loop notification restructuring remains #302.
