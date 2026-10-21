# Demonstration refresh pickup

**Deferred by owner decision, 2026-10-21. The demo needs updating before its
next presentation.** Resume this work separately from repository cleanup and
release preparation. Preserve the four remote demo branches; the local fixture
commits below are preparation material, not approved replacements.

Keep `demo/1-seed`, `demo/2-plan`, `demo/3-detail` and `demo/4-jira` on both
Bitbucket and GitHub. Each branch presents one checkpoint of the same generic
dark-mode-toggle example. This handoff owns the local preparation and remaining
verification; the [release handoff](2026-10-19-public-onboarding-and-release.md)
owns remote publication.

The [sanitized publication record](2026-10-21-sanitized-publication.md) confirms
that all four remote demo names point to a shared needs-updating notice on the
new history. Their previous staged contents remain in private recovery bundles.
The fixture tips below remain local preparation material for a future refresh.

## Current plan pickup: use the plan-tool skill

The current authoring result is
[Teach demos and examples through the plan-tool skill](../docs/implementation-plans/2-skill-led-demo-examples.md)
(`skill-led-demo-examples`), with four run-grade detail files. Resume that plan;
do not create a second seed or re-author the same effort. Its source seed is
[the archived brief](../plan-seeds/archive/skill-led-demo-examples.replaced.md).
The local plan branch is `plan/skill-led-demo-examples`; its base is
`5c38aa9da`. The plan remains `planning`, and all implementation steps remain
unexecuted. Neither a plan pull request nor remote demo publication is part of
this authoring result.

Suggested pickup prompt:

> Use the plan-tool skill to review the completed `skill-led-demo-examples`
> plan and its four detail files with me. Keep user review of created seeds,
> bare plans and details explicit in the demos, and respect any explicit
> delegation to continue. After I authorize execution and the reviewed plan
> bundle meets the merge prerequisite, run the plan, monitor each command to
> confirmed completion, read its results, and finish reconciliation and code
> review. Preserve remote demo refs and publication boundaries.

Read the installed skill and tracked
[shared directives](../integrations/shared/DIRECTIVES.md); the tracked
[Codex router](../integrations/codex/SKILL.md) is the fallback. Use the integration
appropriate to the session. The skill's plan-PR/merge prerequisite still applies
before implementation; this handoff does not authorize a merge or publication.

### Plan scope and user review

The plan retains the dark-mode planning scenario and the advanced TTRPG roadmap
scenario. It converts the guides under `docs/demos/` and the named learning
entry points to assistant requests for grounded seed creation, monitored work,
judged result review and resumption. Commands remain supporting operator
references. No CLI, skill, schema or monitoring implementation changes belong
to the effort.

The owner asks on 2026-10-21 whether the examples have users review created
seeds, plans and details. The plan and every detail now explicitly require:

- Seed review before `create`: outcome, scope, constraints, non-goals and grounding.
- Bare-plan and audit review before `detail`: steps, dependencies and acceptance.
- Detail-bundle and grounded-audit review before execution or local export:
  implementation guidance, verification and unresolved decisions.

At each point the assistant presents artifact links, summarizes changes, asks
for corrections or continuation, and waits unless explicit prior delegation
covers the transition. Silence is not approval. These are conversational review
points using existing behavior, not new tool-enforced gates.

### Authoring evidence and audit trajectory

Provenance, 2026-10-21: all commands use `--backend codex --model gpt-6.1-sol`.
`create skill-led-demo-examples --from-existing
plan-seeds/skill-led-demo-examples.md --iterate -y` selects the direct route,
publishes four steps and archives the seed. `detail skill-led-demo-examples
--commit -y` writes four files and performs its default completeness check.
Both commands use closed stdin and finish before the next invocation starts.
The explicit audit invocations use `completeness-audit skill-led-demo-examples
--iterate --commit --audit-passes 1 -y` with closed stdin.

| Snapshot | Detail coverage | Result and qualification | Report |
| --- | --- | --- | --- |
| Bare-plan gate | 0 of 4 | clean; confirmed; current at snapshot; no conceptual findings; completeness/detail apply routes withheld | [23:38 report](../docs/implementation-plans/plan-details/skill-led-demo-examples/reports/20261021-233834-completeness.md) |
| Initial detail-grounded gate | 4 of 4 | clean; confirmed; no conceptual findings; superseded by the user-review amendment | [23:44 report](../docs/implementation-plans/plan-details/skill-led-demo-examples/reports/20261021-234419-completeness.md) |
| Amended detail-grounded gate | 4 of 4 | clean; confirmed; current; zero blocking or deferred findings | [23:47 report](../docs/implementation-plans/plan-details/skill-led-demo-examples/reports/20261021-234705-completeness.md) |

The amendment adds the owner's user-review requirement across the archived seed,
plan and all four details. It is not an audit finding or a change to the step
graph. The three snapshots contain no recurring conceptual finding; the final
clean result closes authoring. No extra unchanged resampling is needed.

The plan and all four amended detail files parse with current readers.
`uv run pytest tests/ -q -n auto` reports **14,698 passed, 66 skipped in
62.83 seconds**. Local handoff links and whitespace checks pass. These checks
cover plan authoring; they do not certify a converted demo or live consuming-repo
rehearsal. Detail's automatic audit warns that its model-call usage has no
run-log sink; its saved report is retained, but usage/cost is not inferred.

Named local logs: `.tmp/skill-led-demo-examples.create.log`,
`.tmp/skill-led-demo-examples.detail.log`,
`.tmp/skill-led-demo-examples.audit-bare-1.log`, and
`.tmp/skill-led-demo-examples.audit-detail-final.log`. They are transient;
the committed reports above own the retained conclusions.

### Earlier example preparation

Preparation provenance, 2026-10-21: Git object `0b8f96427` contains the earlier
task-list demo attempt; those files are absent from this plan's baseline.
Inspect with `git show 0b8f96427 --stat` and targeted file reads if useful.
The new plan uses it as design input, keeps the current documentation placement
and scenarios, and does not cherry-pick it over `docs/demos/`.

The local dark-mode fixture preparation below remains separate from the plan
and from verified live model output. Confirm any `.tmp/` path exists before
relying on it in another clone.

## Local candidate

The local review repository is `.tmp/public-release-demo-refresh-v2`. Its bundle
is `.tmp/public-release-demo-refresh.bundle`, and its machine-readable ref and
verification receipts are `.tmp/public-release-demo-refresh.refs.json` and
`.tmp/public-release-demo-refresh.verification.json`. These files are local
preparation artifacts, not remote refs. Copy the private recovery bundle named
in the release handoff to durable private storage before replacing remote refs.

| Ref | Local target | What it presents |
| --- | --- | --- |
| sanitized root | `949e6dd5e8c093e7c073e004d468eb022a15484c` | 2,608 selected paths from source `256f466380dda423117273da0ed69735048474d3` |
| `main` | `d8aa550190c8a2cc3cf3d5284d385e30633b4231` | Release 0.2.0 metadata and collected changelog |
| `v0.2.0` | annotated tag object `4a534a841c7b3daaa0fe8e60ec4916da0c28c2f9` | Points to the local release commit |
| `demo/1-seed` | `9ff9e70e6f1ff15e66f56b9155e7f6fb751c7733` | Scope-fenced brief with the required References section |
| `demo/2-plan` | `6e22cdd88dbe1f7ad71e46ca8dba3264b98b9842` | Current-format plan with intent, three steps and test footprints |
| `demo/3-detail` | `d1bde66e824430b907d9fb7db7bd59b9facaf274` | Three run-grade detail files |
| `demo/4-jira` | `c563f3202885c54e3dee0e18faeb7872c4103870` | Local story export and paired developer handoff |

The demo commits form one direct chain above `main`. The repository has one
parentless root, no remotes or alternates, and no old source commits reachable
from its refs. The bundle verifies and `git fsck` passes. The old `v0.1.0` tag
is retained in private recovery material and remains unchanged on both hosts.
The 2,608-path base includes the primary documentation-folder
READMEs and the documentation placement handoff. Its path and content digests
are recorded in `.tmp/public-release-demo-base.verification.json`. The earlier
2,601-path [final-selection receipt](../docs/evidence/public-release-final-selection-verification-20261021.json)
continues to describe its own frozen candidate, not these later bytes.

## Verification and presentation boundary

The plan parses, all three detail files carry the supported format marker, and
the current Jira renderer produced the stories and paired handoff from explicit
local fixture input. `plan-tool jira dark-mode-toggle --lint` exits successfully
with three advisory warnings: the 3h, 2h and 2h stories are below its 4h soft
decomposition floor. The prepared cards disclose that these are presentation
fixtures. No model-generated plan, qualified bare-plan audit or qualified
detail-grounded audit is claimed for these branches.

The first full-suite run exposed a missing `## References` section in the demo
seed. The current `create --from-existing` preflight requires it; the seed and
all four local demo commits were refreshed, and that specific test passes. Five
other failures came from an isolated test PATH without the installed `codex`
executable; the focused fallback test passes with the executables on PATH. The
final isolated run on `demo/4-jira` passes: **14,698 passed, 66 skipped in
58.00 seconds**, using locked dependencies and the local Python 3.14 interpreter.

## Remaining demo verification and publication

Resume the reviewed plan above for local conversion and live-rehearsal evidence.
The following checks continue to constrain any later checkpoint publication.

1. Review the exact local refs, stage differences, bundle and old remote tips.
2. Exercise live `create` → bare audit → `detail` → detail audit → Jira in a
   separate React consuming repository with a working test command and
   authenticated backend. Keep the actual coverage and convergence reports.
   This is required before describing the live workflow as verified.
3. Review and authorize the demo ref updates separately, then read both hosts
   back and confirm matching tips. Main, release tags, public visibility and any
   GitHub organization transfer remain with the release workflow.

Use [the demo guide](../docs/demos/planning-demo.md) for the reusable workflow.
Use [the documentation placement handoff](2026-10-21-documentation-placement-review.md)
for the primary-folder README and how-to review record.
