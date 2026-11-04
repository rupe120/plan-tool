# plan-tool capabilities

The durable **capabilities** of the implemented application, each mapped to the
[`MISSION.md`](MISSION.md) grounding **principle(s)** it serves. This is the
app-level catalog — *outward*-pointing (at a code surface + the principles it
upholds) and *repo-wide*. It is **not** the per-plan `features:` registry
(`Plan.features`/`Step.features`), which is transient and inward-pointing; the
two share no id space. See CLAUDE.md.

Each capability carries a stable kebab-slug **`id`** (a diff-stable handle —
nothing tags against it), a **`title`**, the **`surfaces`** that implement it
(CLI subcommand primary names and/or repo-relative module paths), and the
MISSION **`principles`** (slug ids) it serves. A no-Claude honesty check
(`plan-tool validate`) flags a cited surface that no longer exists, an invalid
principle id, a subcommand with no owning capability, a principle no capability
serves, or a malformed entry. The catalog is authored and maintained by hand.

> Note: *deterministically driven non-determinism* is a near-universal
> baseline — most capabilities serve it — so its presence carries little signal;
> the discriminating links are to the narrow principles (grounding,
> resumability) and convergence.

## Architecture roadmap

- **id:** `architecture-roadmap`
- **surfaces:** `roadmap`, `plan_tool/roadmap.py`, `plan_tool/roadmap_artifacts.py`, `plan_tool/roadmap_gates.py`, `plan_tool/roadmap_seed_manifest.py`, `plan_tool/roadmap_view.py`, `plan_tool/roadmap_html.py`, `plan_tool/roadmap_compare.py`, `plan_tool/roadmap_compare_run.py`, `plan_tool/roadmap_compare_render.py`, `plan_tool/roadmap_diff.py`, `plan_tool/roadmap_er.py`, `plan_tool/roadmap_revision.py`, `plan_tool/roadmap_revision_patch.py`, `plan_tool/roadmap_revision_publish.py`, `plan_tool/roadmap_versions.py`, `plan_tool/roadmap_candidate_context.py`, `plan_tool/roadmap_candidate.py`, `plan_tool/roadmap_candidate_run.py`, `plan_tool/roadmap_candidate_review.py`, `plan_tool/roadmap_version_promotion.py`, `plan_tool/roadmap_escalation_run.py`, `plan_tool/roadmap_escalation_selection.py`, `plan_tool/roadmap_impact_relations.py`, `plan_tool/roadmap_impact_snapshot.py`, `plan_tool/roadmap_evidence_store.py`, `plan_tool/roadmap_relations.py`, `plan_tool/roadmap_source.py`, `plan_tool/roadmap_decision_settlement.py`, `plan_tool/roadmap_decision_settlement_receipt.py`, `plan_tool/roadmap_decision_settlement_run.py`, `plan_tool/roadmap_decision_settlement_enrolled.py`, `plan_tool/run_log.py`, `plan_tool/cli/roadmap_cmd.py`
- **principles:** `converge-on-correct-plan`, `deterministic-non-determinism`, `survive-interruption`
- Stages a concept brief into gated architecture artifacts one rung above
  `create` through four stages: domain, constraints, components, and plans
  (`01-domain.md`, `02-constraints.md`, `03-components.md`, `04-roadmap.md`).
  Stage 4 maps components to an ordered plan list with closed dispositions and
  draft-seed destinations. `--materialize` and `--refresh-seeds` generate
  `SEED_FORMAT.md`-conformant drafts separately; create handoff lines appear
  only for drafts that classify `current`. Opt-in `--apply` (+ confirm or `-y`)
  promotes accepted drafts into `docs/implementation-plans/plan-seeds/` without invoking stages; roadmap
  revisions invalidate rather than overwrite those seeds, and `--refresh-seeds`
  explicitly reprocesses them against current code with a persisted diff report.
  Backend work occurs in roadmap stages and in the standalone seed materializer
  used by `--materialize` and `--refresh-seeds`. Each seed action owns one
  redacted roadmap run record and active snapshot, with source-ordered
  per-seed phases and cleanup at every terminal outcome. `--apply` remains
  backend-free while writing its existing apply-specific record; `--accept-seed`
  and `--view` remain backend-free and log-free. Deterministic gates decide
  whether stage or seed output counts, retrying a candidate with corrections and
  writing nothing after exhaustion. A first stage run holds each gate-clean
  stage in a resume directory and publishes one immutable version, accepted head
  last. A rerun with the same brief resumes from the first stage that is missing
  or fails its re-gate; a changed brief is refused with its remedy, and a
  roadmap that already has an accepted head refuses a stage run.
- `--compare` binds an accepted-head or explicitly selected immutable base to an
  explicitly selected immutable target, or by default the active candidate. Cards and deterministic JSON
  explain Git's complete four-artifact patch; they do not replace it. For a
  candidate target whose direct predecessor is the base they also list its
  row-linked prose amendments (`bound`, `not-applicable`,
  `not-directly-bound`, or `no-operation-evidence`). This
  exclusive route is read-only and remains separate from `--view` and every
  lifecycle writer or acceptance action.
- `roadmap_feedback_ledger.py` owns mutable reviewer input and
  `roadmap_feedback_ledger_run.py` owns guarded ledger mutations. Candidate
  context snapshots eligible items and current derived context; candidate
  storage, review, and promotion remain separate from accepted-head selection.
- `--settle-decision <artifact>:<decision-id> --settlement-evidence
  <artifact>:<feedback-id> --confirm-decision-settlement` is one exclusive,
  operator-confirmed action that moves a single Roadmap-derived `pending`
  decision to `settled`, bound to a named, live feedback row that cites it. It
  invokes no backend and publishes an immutable, redacted receipt before any
  canonical write. It dispatches straight to the enrolled runner. See
  `docs/how-to/roadmap.md` § 5 for the two permanent enrolled-lineage limits
  (`BACKLOG.md` #395 for a selector-era lineage, and non-canonical accepted
  bytes), for settling while a candidate is active, and for recovering a
  hand-edited row.
- `--propose-candidate`, `--decide-candidate
  <candidate-version-id> --candidate-decision approve|edit|reject`,
  `--review-candidate <initial-candidate-version-id>`, `--answer-question
  <question-id> --answer <text>`, and `--promote-review-seal <seal-id>` expose
  one ordered immutable lifecycle. One ordinary ledger intake validates typed
  operations into a bounded or structural inert candidate; reviewers never
  select a structural route. Structural approval is two invocations: the first
  prints the whole unpromoted stack and a digest and writes nothing, and
  `--confirm-stack-digest <digest>` seals the top candidate only when the
  recomputed digest matches, so one approval covers every hop beneath it. Edit
  stores a replacement requiring a fresh decision, and reject releases only the
  active candidate. Promotion alone moves the accepted head;
  its accepted-root, active-candidate, stored-binding, and gate checks precede
  journaled publication. The separate confirmed decision settlement also moves it via
  `--settle-decision`. The
  proposal, question, and replacement routes accept the command's fake-backend
  seam; promotion remains backend-free. Ordinary readers resolve
  the accepted head while every stored version remains immutable.
- There is no structural-rewrite, escalation, or impact-analysis route:
  `--escalate-feedback`, `--escalation-reason`, `--analyze-escalation`,
  `--rewrite-structural`, `--rewrite-analysis`, `--view escalations`, and
  `--view impact-analyses` are retired, and no command writes an escalation
  receipt or an impact analysis. Records those routes stored under
  `<roadmap-dir>/.plan-tool/evidence/` stay on disk, and nothing reads them.
- There is no legacy writer mode: `--from-stage`, `--confirm-brief-rebind`,
  `--enroll-version`, `--enroll-baselines`, `--migrate-feedback-ledger`,
  `--restore-revision`, and `--reopen-feedback` are retired, and the version
  store is the only write target.

## Plan authoring

- **id:** `plan-authoring`
- **surfaces:** `create`, `detail`, `plan_tool/create.py`, `plan_tool/detail.py`
- **principles:** `converge-on-correct-plan`, `deterministic-non-determinism`
- `detail` authors the sole supported detail input, the run-grade file described in `DETAIL_FORMAT.md`.

## Plan completeness & convergence

- **id:** `plan-completeness`
- **surfaces:** `completeness-audit`, `completeness-apply`, `data-contract-apply`, `convergence`, `gate-status`, `plan_tool/completeness_report.py`, `plan_tool/convergence_diagnosis.py`, `plan_tool/data_contract.py`
- **principles:** `converge-on-correct-plan`, `deterministic-non-determinism`
- `completeness-audit` grounds its audit on the canonical run-grade bundle.

## Code reconciliation

- **id:** `code-reconciliation`
- **surfaces:** `reconcile-plan`, `reconcile-code`, `reconcile-plan-walk`, `verify-all`, `plan_tool/refresh.py`
- **principles:** `keep-the-plan-true-to-code`, `converge-on-correct-plan`

## Decision telemetry

- **id:** `decision-telemetry`
- **surfaces:** `telemetry`, `decide`, `plan_tool/telemetry.py`, `plan_tool/telemetry_analysis.py`, `plan_tool/cli/telemetry_cmd.py`, `plan_tool/cli/decision_cmd.py`
- **principles:** `converge-on-correct-plan`, `deterministic-non-determinism`

## Project context

- **id:** `project-context`
- **surfaces:** `init`, `create`, `detail`, `completeness-audit`,
  `plan_tool/project_profile.py`, `plan_tool/cli/init_cmd.py`,
  `plan_tool/create.py`, `plan_tool/detail.py`, `plan_tool/review.py`
- **principles:** `converge-on-correct-plan`, `write-for-the-human`
- `init` records one confirmed project-level intent plus optional non-goals and
  settled decisions in a tracked, repo-owned profile. Decisions are an ordered
  list of statements, not a categorized ledger. The profile guides the
  scope-bearing prompts in `create`, `detail`, and `completeness-audit`; it is
  never repository evidence, a plan-necessity verdict, or an execution input.
  The command does not infer or evaluate that content.

## Forward-seed bridge

- **id:** `forward-seed-bridge`
- **surfaces:** `annotate`
- **principles:** `keep-the-plan-true-to-code`

## Step execution

- **id:** `step-execution`
- **surfaces:** `run`, `suggest-gates`, `plan_tool/launcher.py`, `plan_tool/renderer.py`
- **principles:** `converge-on-correct-plan`, `deterministic-non-determinism`
- `run` executes a step from its declared run-grade detail under the execution
  lifecycle and gates.

## Structural remedies

- **id:** `structural-remedies`
- **surfaces:** `split`, `merge`, `scope-out`, `split-criteria`, `plan_tool/granularity.py`, `plan_tool/split_criteria.py`
- **principles:** `converge-on-correct-plan`

## Concept decisions

- **id:** `concept-decisions`
- **surfaces:** `scope-review`, `plan_tool/concept_tree.py`, `plan_tool/concept_bootstrap.py`, `plan_tool/concept_review.py`, `plan_tool/concept_sync.py`, `plan_tool/schema.py`, `plan_tool/create.py`, `plan_tool/detail.py`, `plan_tool/review.py`, `plan_tool/reground.py`, `plan_tool/scope_out.py`
- **principles:** `converge-on-correct-plan`, `write-for-the-human`

## Jira export

- **id:** `jira-export`
- **surfaces:** `jira`, `plan_tool/jira.py`
- **principles:** `deterministic-non-determinism`, `write-for-the-human`
- `jira` grounds stories and the paired developer handoff on one captured
  declared run-grade input snapshot; neither output is a detail input.

## Direct pipeline

- **id:** `direct-pipeline`
- **surfaces:** `direct-jira`, `direct-run`, `plan_tool/cli/direct_cmd.py`
- **principles:** `converge-on-correct-plan`, `deterministic-non-determinism`

## Plan discovery & management

- **id:** `plan-management`
- **surfaces:** `list`, `status`, `validate`, `register`, `deregister`, `root`, `sweep`, `withdraw`, `plan_tool/locator.py`
- **principles:** `deterministic-non-determinism`

## Run state & resumption

- **id:** `run-state`
- **surfaces:** `checkpoint`, `runs`, `lessons`, `plan_tool/checkpoint.py`
- **principles:** `survive-interruption`

## Parallel workspaces

- **id:** `parallel-workspaces`
- **surfaces:** `worktree`, `plan_tool/worktree.py`, `plan_tool/cli/worktree_cmd.py`
- **principles:** `deterministic-non-determinism`

## Branch binding

- **id:** `branch-binding`
- **surfaces:** `attach-branch`, `detach-branch`, `plan_tool/branch_ownership.py`
- **principles:** `keep-the-plan-true-to-code`

## Backend abstraction

- **id:** `backend-abstraction`
- **surfaces:** `bench`, `plan_tool/backend.py`, `plan_tool/shell.py`
- **principles:** `deterministic-non-determinism`

## Skill distribution

- **id:** `skill-distribution`
- **surfaces:** `install-skill`
- **principles:** `write-for-the-human`
