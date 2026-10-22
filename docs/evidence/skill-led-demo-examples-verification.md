# Skill-led demo verification

The assistant-led guides and authored examples support the reading journey. A
bounded live dark-mode rehearsal completes seed → create → bare audit → detail
→ grounded audit → local story/developer-handoff export, with confirmed audit
coverage and passing story lint. This verifies planning and local export on one
small repository; it does not verify feature implementation, browser behavior,
a full TTRPG run or remote presentation checkpoints. Remote publication remains
separately owned by the [release workflow](../../handoffs/2026-10-19-public-onboarding-and-release.md).

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
It is separate from model audit evidence. The parent session reviews actual rehearsal seeds, plans, details and reports
under the owner-authorized execution of this plan, whose final step includes the
bounded planning-to-local-export rehearsal. This is explicit batch scope for
verification, not evidence that a person separately approved each generated
artifact. The guides retain conversational review checkpoints and wait unless
the user explicitly delegates continuation. No remote publication is authorized.

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

## Runtime recovery and captured live rehearsal

Dated observation, 2026-10-21 local / 2026-10-22 UTC: the nested step process
reports an authenticated Codex login but its availability probe exits 1 with
`failed to initialize in-process app-server client: Operation not permitted
(os error 1)`. No model runs in that probe. The parent session then requests the
required execution access and successfully runs the workflow below. The failure
is specific to the restricted child context; it is not an unresolved environment
or authentication blocker. Escalate or hand the action back to a capable parent
before describing that kind of failure as permanently unavailable.

The rehearsal repository is `/private/tmp/plan-tool-dark-mode-rehearsal-cq7oc8wd`,
a new Git repository with no remotes. Its initial checkpoint is `ae4c73d`; the
reviewed seed checkpoint is `6609448`; paired export checkpoint is `9756939`.
It contains a dependency-free HTML/module page with an existing light-theme
initializer and a passing `node --test` baseline (Node `v22.22.0`). The product
checkout at `2aab4c878` supplies the editable CLI; backend is Codex and every
model-backed invocation selects `--model gpt-6.1-sol` explicitly.

Commands below run from that repository with closed stdin and `-y`. Each original
invocation exits before the next starts. Commits checkpoint the seed, reviewed
plan, detail, reports, export configuration and paired outputs.

| Command / checkpoint | Observed result |
| --- | --- |
| `create dark-mode-toggle --from-existing plan-seeds/dark-mode-toggle.md --iterate` | Direct route; one feature step. Headless create omits an unqualified test command. Session review adds the already-passing `node --test` before the bare audit. |
| `completeness-audit dark-mode-toggle --iterate --commit --audit-passes 1` | 0 of 1 detailed; `advisory-only`, confirmed, current; `confirmation_kind=confirmed-dry`, `budget_limited=false`; zero conceptual and deterministic findings. |
| `detail dark-mode-toggle --commit` | One run-grade file; its automatic detail-grounded audit reports zero conceptual findings and confirmed coverage. |
| `completeness-audit dark-mode-toggle --iterate --commit` | 1 of 1 detailed; `advisory-only`, confirmed, current; confirmed-dry and not budget limited. Reuses the fresh conceptual audit without another model call. |
| `jira dark-mode-toggle` | One 8h draft story `DEMO-S1` covering step 1 and a paired developer handoff. Local configuration uses the `DEMO` epic and `THEME` display tag; no real Jira key is configured or created. |
| `jira --lint --input <actual-story-path>` | Pass: one story checked; no lint warning. |
| `node --test` | One baseline test passes before and after planning/export. Application, HTML and test files have no diff from `6609448`. The feature remains unimplemented. |

Both audit stages retain one INFO, limited-confidence granularity advisory:
step 1 touches three allegedly unrelated areas (`app.mjs`, `index.html`,
`theme.mjs`). Session review keeps them together because they deliver the same
small theme outcome; this advisory does not block and is not a conceptual gap.
Do not relabel the report clean or split the feature to silence the heuristic.
The bare completeness/detail apply routes remain withheld at 0 of 1 coverage.

Inspecting the export confirms a binding plan path with step outcome and intent,
followed by an explicitly non-binding suggested implementation route. Both files
carry the same companion fingerprint
`604b80ea780b36bbb66d19a77ae56e9b9679e8e15774097b2cf9b0bf69d90465`.
The story keeps the light fallback, accessible control and reload persistence;
the handoff preserves the plan's scope and acceptance criteria. Node success
checks the baseline only, not the unimplemented acceptance behaviors.

### Retained identities

Paths below are relative to the rehearsal root. The bundle
`.tmp/skill-led-demo-examples.rehearsal.bundle` retains its committed files
locally, and `.tmp/skill-led-demo-examples.rehearsal-location.txt` records the
root. These temporary paths may disappear; the stage outcomes, qualification,
limitations and identities in this record remain the durable summary.

| Artifact | SHA-256 |
| --- | --- |
| `docs/implementation-plans/2-dark-mode-toggle.md` | `3b6510ab5a8d0e3d5c465c9aa39da713f399cb9ead4ce6f5a4466e25e20530b7` |
| `docs/implementation-plans/plan-details/dark-mode-toggle/01-extend-light-only-initialization.md` | `f92a6bf20dc673bfbff93529f50b776b477d23f0c2f19abd855b07ab07d3fbf3` |
| `docs/implementation-plans/plan-details/dark-mode-toggle/reports/20261022-001947-completeness.md` | `c2ac45755c376a45e1bd2e331274f9649313a5f3aa173969bbad43ceb706c1ef` |
| `docs/implementation-plans/plan-details/dark-mode-toggle/reports/20261022-002656-completeness.md` | `7368f477920daa532cdba7deb9babd18e2320630097a22cd0d1465011dac9377` |
| `docs/implementation-plans/plan-details/dark-mode-toggle/jira-stories.md` | `b73f564d7206f8272d9a2e7e80df4c2e4ab9d008ae89f46428dab4eff7c114ed` |
| `docs/implementation-plans/jira-handoffs/dark-mode-toggle/jira-stories.developer-handoff.md` | `de3bcda2aff96ffc3c9b741dceafe05b8129302428b028f0b1c89c777604b2b8` |

The detail automatic audit and Jira export warn that a model-call usage sink is
missing. Saved artifacts and stage outcomes exist; usage/cost is not inferred.
Existing bug-backlog entries own that instrumentation gap.

## Skill observations

All three shipped skill routers carry the same stale quick recipes: the
“complete as possible” path skips the bare audit, the summary says detail
iteration defaults on, and failed-step recovery says to mark the step done
manually. The actual run follows the canonical directives: both audit gates,
one-shot detail, and tool-mediated `run --accept` if recovery is needed.
The confirmed instruction contradictions are filed separately in
[the bug backlog](../../BUG_BACKLOG.md#installed-skill-quick-recipes-contradict-the-required-audit-order-detail-default-and-failed-step-recovery);
no skill behavior or router content changes in this conversion.

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

## Final implementation checks and review

The parent session's final full suite reports **14,698 passed, 66 skipped in
71.48s**. All four launcher step gates also pass. Final local-target checks cover 290 file links and 201 Markdown fragments,
including the review ledger and the corrected RUNBOOK canonical-layout anchor. The
[review ledger](../../handoffs/2026-10-21-skill-led-demo-examples-code-review.md)
retains two independent report-only reviews and their exact ranges and methods;
both report no material findings. The code reconciliation sweep exits 0 with no
eligible steps because this plan is entirely non-code. These checks close the
documentation implementation; they do not broaden the rehearsal's claims.
