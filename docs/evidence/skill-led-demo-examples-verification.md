# Skill-led demo verification

Documentation supports the reading journey; the live dark-mode rehearsal **needs
verification** because the available Codex runtime cannot initialize in this
restricted environment. Remote checkpoint publication remains separately owned
by the [release workflow](../../handoffs/2026-10-19-public-onboarding-and-release.md).

## Reviewed snapshot and method

Verification date: 2026-10-21. Source and tool checkout:
`ada9ccbeb092e479d585ac339d732f377bb42d72`. Steps 1–3 are recorded as done
in the plan at this snapshot. This record reviews their documentation and the
minimal fixture; it does not certify the surrounding plan's execution tail.
Checks use this checkout's `.venv/bin/python`; no installed-tool revision is
inferred from the global `plan-tool` executable.

## Reading journey and review checkpoints

| Surface | Request, artifact and reader decision | Result |
| --- | --- | --- |
| [Your first plan](../../README.md#your-first-plan) | Ask for a grounded seed; inspect linked seed, plan/audit and details/audit; correct or authorize each transition. | Narrative review passes; execution and export are separate follow-up requests. |
| [Starting point](../how-to/choose-a-starting-point.md), [situations](../how-to/use-cases.md), [common workflows](../how-to/common-workflows.md) | Choose intake, inspect assistant-authored inputs and review each stage before continuation. | The assistant requests do not assume a prewritten seed; command examples remain supporting references. |
| [Planning preparation](../demos/planning-demo.md#prepare-the-example) and [presentation](../demos/planning-demo.md#present-the-workflow) | Review actual seed before create, bare plan and report before detail, complete details and grounded report before local export. | Links, change summaries, corrections/continuation requests and waiting unless explicitly delegated appear at each boundary. |
| [Reading samples](../demos/dark-mode-example.md) | Inspect scope, dependencies, acceptance, audit questions and both export audiences. | Explicitly authored, incomplete excerpts; no captured report or successful model result is asserted. |
| [Runbook](../../RUNBOOK.md) and the situation/resume requests | Inspect original invocation and saved results before resuming. | Narrative comparison with the [monitoring owner](../../integrations/shared/DIRECTIVES.md#monitor-command-liveness-and-recover-safely) preserves confirmed original-command exit, no overlapping invocation and no stopping a quiet process without authorization. |

Review evidence above concerns what the guides ask the assistant and user to do.
It is separate from model audit evidence. No actual rehearsal seed, bare plan
or detail bundle exists here for user approval; no user approval or delegation
across those live transitions is claimed. On resumption, present each actual
artifact with its link and change summary, ask for corrections or continuation,
and wait for the response unless an explicit delegation covers that transition.
The local export still needs its separate request after detail review.

Both audit stages refer readers to the [audit procedure](../how-to/pipeline/audit.md)
for coverage, qualification, unresolved findings and convergence, rather than
using exit status as a clean verdict. No material discrepancy is identified in
this bounded reading review. Guide corrections, if later needed, belong to
steps 1 (planning), 2 (roadmap) or 3 (first-use/situations), not this status record.

## Roadmap contract review

[Phase 2](../demos/roadmap-demo.md#5-phase-2--the-review-loop-the-part-worth-demoing)
keeps mutable ledger input separate from inert candidates and accepted content.
Its stored-route review distinguishes answered-seal promotion from structural
whole-stack disclosure and digest confirmation; settlement uses its separate
selector and receipt-bound confirmation route.
[Phase 3](../demos/roadmap-demo.md#6-phase-3--promote-the-draft-seeds)
selects accepted-head drafts, reviews materialization and copy destinations,
and requires seed content review before create. Phases 4–6 require bare and
then detail-grounded audit review and stop before execution/export.

These boundaries agree with [Roadmap format](../../ROADMAP_FORMAT.md) and
[the ledger workflow](../../ROADMAP_FEEDBACK_FORMAT.md#ledger-to-candidate-workflow).
The refused-feedback demonstration explicitly limits predecessor-based gate
claims: candidate promotion supplies no predecessor to `check_settled_decisions`.
This is contract review only; no TTRPG generation, candidate mutation, settlement,
materialization or fresh refusal is observed.

## Runtime prerequisite and unverified stages

Observed commands, in order (each exits before the next):

```sh
command -v codex
command -v plan-tool
codex login status
codex --version
codex exec --help
codex exec --ephemeral --ignore-user-config --skip-git-repo-check \
  -C /private/tmp -s read-only -m gpt-6.1-sol \
  'Reply only READY. Do not use tools or read files.' < /dev/null
```

Provenance, 2026-10-21: both executables resolve under
`/Users/joshrusso/.local/bin/`; login status reports `Logged in using ChatGPT`.
Codex version is `0.163.0`. The availability probe exits **1** immediately with
`failed to initialize in-process app-server client: Operation not permitted (os error 1)`.
No model response, provider authentication check or plan-tool run occurs.
This is a runtime permission blocker, not demonstrated missing credentials,
provider quota, audit failure or a successful rehearsal. The original probe's
shell exit is confirmed; there is no live invocation to stop or resume.

| Stage | Observed status |
| --- | --- |
| Disposable consuming repository with working application tests | Not prepared; prerequisite blocked before rehearsal setup. |
| Grounded dark-mode seed and user review | Not reached. |
| Create and bare-plan audit/review | Not reached; no report, coverage, qualification or convergence outcome. |
| Details and grounded audit/review | Not reached; no report, coverage, qualification or convergence outcome. |
| Separately requested local export | Not reached; no story or paired developer handoff. |
| Story lint and companion inspection | Not run; no available rehearsal export to inspect. |
| Live command monitoring | Only prerequisite probe exit observed; no plan-tool lifecycle monitoring demonstrated. |

Resume in an environment permitting the authenticated backend to initialize,
then follow [the landed dark-mode walkthrough](../demos/planning-demo.md).
Keep the disposable repository, manifest, artifacts and audit history outside
this product repository. Record tool/application revisions, backend/model,
actual commands and exits, user review decisions, report identities, coverage,
qualification and unresolved findings. Inspect both outputs against
[Jira output pair](../../JIRA_FORMAT.md#output-pair) and
[paired developer handoff](../../JIRA_FORMAT.md#paired-developer-handoff), then
run `plan-tool jira --lint --input <actual-story-path>` through `cmd_jira_lint`.
Record failures and advisory warnings separately from audit conclusions.

## Retained artifacts and repository checks

Provenance, 2026-10-21: `plans/2-demo.md` passes `parse_plan`,
`render_plan_text` and `parse_plan_text` round-trip checks with equal model
fields and body. This is the minimal non-code placeholder, not a dark-mode
feature plan; it intentionally has no detail artifact. Reading-sample blocks
are incomplete excerpts and are not parsed as complete plans or details.

The handoff's `.tmp/public-release-demo-refresh-v2`, bundle, refs receipt,
verification receipt and base verification receipt are all absent in this
clone. Therefore its three prepared details, story and companion cannot be
rechecked here. The handoff's older lint result remains dated provenance only;
no new lint result is inferred. Missing scratch material does not invalidate
the maintained guides.

Focused existing parser/detail/Jira tests and document-link checks are recorded
below. The plan's authoritative full-suite post-flight gate belongs to the
launcher and is not run inside this step; no new full-suite result is claimed.
Repository checks cannot establish live model reliability or audit qualification.

Observed verification results, 2026-10-21:

- `.venv/bin/python -m pytest tests/test_parser.py tests/test_detail.py tests/test_jira.py tests/test_jira_handoff.py tests/cli/test_jira_cmds.py -q`: **1,166 passed in 4.09s**; existing hermetic behavior coverage, not live export evidence.
- An inline Python check calls `parse_plan(Path('plans/2-demo.md'))`, renders
  its body with `render_plan_text`, reparses with `parse_plan_text`, and asserts
  equal model fields and body: **pass**.
- Local Markdown target/heading inspection across the three step deliverables:
  **40 links pass**, including fragment targets; `git diff --check`: **pass**.
- Two document review passes compare the three deliverables with the dependency
  guides and owning contracts: no remaining material accuracy/completeness
  finding in this bounded change. The second checks the reconciled handoff for
  restart instructions, scenario drift and unsupported verification claims.
