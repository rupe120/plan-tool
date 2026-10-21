> **Replaced**: this file has been superseded by `docs/implementation-plans/2-cross-invocation-audit-history.md`.
> Preserved here for history; do not edit.

## Overview

`plan-tool convergence <name>` adds a separate, read-only summary of saved completeness-audit history to the existing `convergence` output. It reports a severity-classified pairwise trajectory only when adjacent reports establish reliable finding identity; otherwise it reports `identity-uncertain` with coverage and raw unmatched ids. The feature remains zero-Claude and does not change exit codes, gates, or plans.

## Problem statement

The existing `convergence` output does not summarize completeness-audit history across invocations. Operators need to see whether comparable adjacent reports show a severity trajectory without treating changed ids, anchors, artifact revisions, legacy evidence, or malformed evidence as reliable confirmation.

## Architecture

Load saved completeness reports for one plan and compare only reports with compatible audit stage, detail grade, and sampling configuration. Compare adjacent reports pairwise, linking expected finding identities through reliable anchors; differing artifact revisions do not establish identity by themselves.

Render the result as a distinct cross-invocation history section in the existing `convergence` output. When identity cannot be established because there is only one report, configurations are incompatible, anchors drift, or ids remain unmatched, render `identity-uncertain`, coverage, and raw unmatched ids instead of confirming a positive or negative trend. Keep legacy or malformed evidence distinct from current comparable evidence, and keep existing convergence advisories separate and unchanged.

## Out of scope

- New CLI verbs, Claude calls, changed exit codes, gates, or plan mutations.
- Content-based or fuzzy finding matching.
- Changes to #125's severity classifier, #173's caching/recheck design, or any confirmation decision when identity is uncertain.

## Risks

- Independent audit runs can describe the same concern with different ids or anchors. The reader must preserve that uncertainty instead of inferring a positive or negative trend.
- Report loading must keep legacy/malformed evidence distinct from current, comparable evidence.

## Testing

Tests cover every result state: a severity-classified pairwise trajectory for comparable saved reports, and `identity-uncertain` for a single report, incompatible stage, incompatible grade, incompatible sampling configuration, anchor drift, or unmatched ids. Coverage also verifies that existing convergence advisories remain separate and unchanged.

## Acceptance criteria

- Comparable saved reports render a severity-classified pairwise trajectory.
- A single report, incompatible stage/grade/configuration, anchor drift, or unmatched ids renders `identity-uncertain` and raw evidence rather than a convergence confirmation.
- Existing convergence advisories remain separate and unchanged.
- Tests cover each state, and documentation tells the operator what to do with an uncertain result.

## Deferred

- Cross-invocation cache/recheck behavior remains #173.
- Persisted audit-coverage schema versioning remains #301.
- Retry-loop notification restructuring remains #302.

## Input

The plan consumes saved completeness reports for one plan. It relies on their audit stage, detail grade, sampling configuration, finding ids, reliable anchors, artifact revisions, coverage, and legacy/malformed status; only compatible reports with reliable finding identity support a severity-classified pairwise trajectory.
