# Smallest proof first — review record

## Scope

Owner-requested direct change: require concrete present need before elaborating
new machinery. Source range: `ebce39522^..ebce39522`, based on main `e1a285b25`.
The closed consumer set is step proposal (combined/split), body synthesis,
detail, execution and conceptual audit, with seed/session authoring guidance.

The rule asks for the simplest existing end-to-end path and the current
requirement plus repository/platform evidence that makes each departure
necessary. It preserves safety, compatibility, authority, audit properties and
explicit owner choices. It adds no model call, response field, persisted schema,
size heuristic, semantic minimality gate or automatic scope rewrite.

## Verification

- `.venv/bin/python -m pytest tests/test_create.py tests/test_detail.py tests/test_review.py tests/test_renderer.py -q -n auto`: 2,751 passed, one skipped.
- `.venv/bin/python -m pytest tests/ -q -n auto`: 14,752 passed, 67 skipped in 73.46 seconds. Skips are retained as incomplete individual cases, not passing evidence.
- `git diff --check`: passed.

The first affected run exposed instruction placement in the existing produced-file
heading block and scope-fence byte measurements. Moving the instructions into
the existing Constraints/What to do sections preserves those contracts; the
existing structural tests pass unchanged. One added synthesis assertion was
corrected to normalize whitespace.

These tests establish prompt delivery and existing contracts. They do not
certify the semantic minimality of model-generated plans.

## Independent review convergence

Two fresh `codex exec --ephemeral -s read-only -m gpt-6.1-sol` reviews inspected
the same source range with strict changed-path scope. Each read AGENTS.md,
changed source/prompts/tests/docs and relevant callers and response contracts;
neither read the other's findings or edited files. Both report-only reviews
returned clean: no concrete correctness or completeness defects. Both checked
proposal arms, prompt section boundaries, scope-fence metrics, preserved owner
and safety contracts and absence of new semantic gating. They did not rerun
verification. No logic changes follow these reviews.

## Exploratory behavior probe

One fresh read-only Sol call rendered the updated ordinary step-proposal prompt
against Loom's manual sandbox pipeline request and source baseline `cde1c02`.
It inspected existing release scripts, configuration, IAM construction and
operator documentation without live provider calls or mutations. Its ordinary
JSON output contains three steps: a bounded authority adapter justified by
missing existing deployment-role permissions; generator/pipeline wiring reusing
release commands; and operator documentation. The earlier Loom implementation
plan contains seven steps and about 120 KB of detail.

This is one exploratory observation with different preparation/context, not a
controlled comparison or a minimality guarantee. In particular, the probe
preserves per-operation review and handoff requirements from the baseline
runbook; it does not establish the separately approved single-step Loom design,
hosted execution, authority availability or deployment success. Owner scope
choices and implementation review remain necessary.

## Remaining work

Merge review only. This record does not install the new guidance into other
clones or claim the separate Loom deployment workflow is complete. The source
change is owner-tracked, with no assigned Jira ticket. Its changelog fragment is
`changelog.d/smallest-proof-first.md`.
