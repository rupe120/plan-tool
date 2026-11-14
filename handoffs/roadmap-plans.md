# Roadmap to plans

Deriving plans and seeds from roadmap artifacts: handoff investigation, derivation, breakdown, sibling inputs, selectors and seed rules. Each section below is one change or route in this workstream, ordered by the date it was opened; new work in the workstream appends a section here instead of creating a file (`README.md` § "Naming").

| Section | Opened |
| --- | --- |
| [Roadmap seed `## Risks` presence rule — review ledger](#roadmap-seed--risks-presence-rule--review-ledger) | 2026-10-10 |
| [Roadmap plan handoff investigation pickup](#roadmap-plan-handoff-investigation-pickup) | 2026-10-15 |
| [Sibling planned Input paths review ledger](#sibling-planned-input-paths-review-ledger) | 2026-10-15 |
| [Sibling planned Input paths pickup](#sibling-planned-input-paths-pickup) | 2026-10-15 |
| [Roadmap → seed → base-plan business-logic testing loop](#roadmap--seed--base-plan-business-logic-testing-loop) | 2026-10-16 |
| [Roadmap plan derivation implementation](#roadmap-plan-derivation-implementation) | 2026-10-16 |
| [Roadmap plan breakdown — review handoff](#roadmap-plan-breakdown--review-handoff) | 2026-10-23 |
| [Roadmap plan-row selector documentation](#roadmap-plan-row-selector-documentation) | 2026-10-23 |
| [Roadmap seed examples](#roadmap-seed-examples) | 2026-10-23 |

## Roadmap seed `## Risks` presence rule — review ledger

*Opened 2026-10-10.*

| Field | Value |
| --- | --- |
| Change | A draft seed without a non-empty `## Risks` section classifies `malformed` (`missing-draft-seed-risks`). Owner decision 2026-10-10: roadmap seeds must carry `## Risks` |
| Branch | `fix/roadmap-seed-risks-required` |
| Reviewer | `/code-review high main` in-session (forked), report-only |

### Settled decisions

- Presence only. A fenced example or a `_(TODO)_`/`TODO` placeholder (the existing `scope_fence` vocabulary) does not count; what a risk says is never judged, and `TBD`/`None.` pass.
- A plan row whose artifacts state no risk writes one explicit line saying so (prompt and correction message name it); the prompt still forbids inventing a risk.
- Consequence accepted by the owner: existing drafts without `Risks`, Integration's included, are `malformed` until `--refresh-seeds` or a hand edit plus `--accept-seed`.
- `Testing` and `Acceptance criteria` stay ungated; stated in `ROADMAP_FORMAT.md`.

### Findings (round 1)

| # | Finding | Disposition |
| --- | --- | --- |
| 1 | Prompt forbids inventing a risk but the gate demands content: a row with no stated risk had no compliant reply | **Fixed.** Prompt and correction name the one-line statement; `create` accepts it because any seed line is citable |
| 2 | Deleted entry dropped the undecided `Testing` / `Acceptance criteria` follow-up | **Fixed.** Stated as deliberately not gated in `ROADMAP_FORMAT.md` |
| 3 | Consumers of the rule not pinned | **Fixed.** Classifier and `--apply` tests (`malformed` on a matching digest); gate disabled turns them red |
| 4 | Doc: a hand edit goes through `digest-mismatched` and needs `--accept-seed` | **Fixed** |
| 5 | A placeholder-only body satisfies the gate | **Fixed in part.** Reuses `_is_placeholder_section`; a bare `-` still passes (vocabulary matching beyond the existing placeholder set is the semantic check this gate refuses) |
| 6 | Sections extracted twice | **Fixed.** One `_draft_seed_sections` dict |
| 7 | Prompt leaks "roadmap gate"; unwrapped line | **Fixed** |
| 8 | A handoff still lists the decision as open | **Fixed** |

## Roadmap plan handoff investigation pickup

*Opened 2026-10-15.*

### Delivery and review status

| Item | Evidence |
| --- | --- |
| Plan merge | PR #95, `8e2615213` on origin/main |
| Delivery branch | `run/roadmap-plan-handoff-investigation` |
| Reviewed delivery | `8e2615213...787217835` |
| Execution | Both non-code steps green and committed; full parallel suite passes after each step |
| Reconcile | `reconcile-code § "Roadmap plan handoff investigation pickup" --all --no-walk -y`: no code steps to reconcile |
| Reviews 3 and 4 | Two consecutive independent `gpt-6.1-sol` report-only reviews: clean, no material findings |
| Publication | Delivery PR remains pending authorization; no follow-on feature is implemented |

The delivered design record is `docs/explanations/roadmap-plan-handoff.md`.
It selects existing prose/reference inputs for the bounded Integration journey, no
new #493/#494 tool implementation, and a conditional #462 recommendation that
preserves its independent evidence gate. The #492 anchor and stage arc remain.

### Validation and convergence

- Seed review preserves all seven #492 scope fields verbatim, verifies a usable
  intent, one References section, balanced fences and captured Scope guardrails.
  Source review distinguishes Integration baseline `25d6517dd47949040b94904669128a5f0ba9aa06`
  from the earlier bounded evidence record.
- `create --iterate` completes with two non-code steps. Restore its lost local
  evidence references before auditing; the selected raw seed is retained in
  `plan-seeds/archive/roadmap-plan-handoff-investigation.replaced.md`.
- Bare audits use `--backend codex --model gpt-5.6-terra completeness-audit
  § "Roadmap plan handoff investigation pickup" --iterate --audit-passes 1 --commit -y`.
  Reports in the plan's `reports/` directory: `20261015-214054` (HIGH missing-evidence
  completion contract), `20261015-214627` (HIGH disposition targets),
  `20261015-214855` (MEDIUM independent #462 gate). All have 0/2 detail coverage;
  completeness and detail-level apply routes are withheld. The trajectory exits
  through auditing session edits: the last two findings refine disposition
  wording; the session explicitly retains the bounded decision record, finishes
  the correction, and proceeds to detail. This is not a clean bare-audit claim.
- `detail --commit -y` authors once with `gpt-5.6-terra` and commits both steps.
  Its built-in detail-grounded report `20261015-215526` finds MEDIUM missing step-1
  follow-on dispositions; the session adds the producer obligation. Fresh audit
  `20261015-215801` finds MEDIUM provider-versus-owner question substitution; the
  session corrects every authoring/verification site and repairs reference links.
- The third detail-stage snapshot, `20261015-215913-completeness.md`, is clean,
  confirmed, current, 2/2 detailed, run grade, zero findings, and stop `converged`.
  Its command is the same iterative audit above. The previous two findings are
  distinct detail-authoring defects, not repetitions of the bare findings.
- Existing backlog tests: 30 passed. All 14 local detail reference links resolve.
  YAML parsing and `git diff --check` pass. No new test is required for plan prose.

### Settled boundaries

The observable is a reviewed record, not proven good decomposition. The record
compares existing input delivery for create, detail and completeness-audit and
separately recommends dispositions for #493, #462 and #494. #462 keeps its own
evidence gate; a conditional recommendation does not unblock it or prevent #492
completion. Missing evidence required for a tool-side conclusion keeps #492 open.
A provider question remains distinct from an owner product decision. No new
live probe, semantic checker, schema, CLI, execution policy or Integration write ships.

### Delivery review findings

- R1 HIGH accepted outcome/version missing: fixed `3c6d1a03f`; name the actual accepted store/version and `rule-answer-engine-acceptance` rather than an abstract planning outcome.
- R1 HIGH settled session policy reopened: fixed `3c6d1a03f`; preserve the asking-session requirement and keep the unexercised in-workflow refusal as the provider question.
- R1 MEDIUM input and interface trace absent: fixed `3c6d1a03f`; trace `ChatCommand`/`DriverEvent` and the three prompt routes, including References rather than full Architecture for detail.
- R2 MEDIUM accepted-head path incorrect: fixed `787217835`; reference `.roadmap-versions/accepted-head.json` and separate Git source identity from the local immutable store.
- R3 clean: fresh `gpt-6.1-sol` review of `8e2615213...787217835`; named code, Integration sources and accepted store verified; no material findings.
- R4 clean: independent `gpt-6.1-sol` review of `8e2615213...3c7180e29`; plan acceptance and final tracking/ledger accuracy verified; no material findings. The delivery review converges with two consecutive clean passes.

Reports are local `.tmp/roadmap-plan-handoff-investigation.delivery-review-{1,2,3,4}.md`.
No logic changes occur in this delivery. Source checks, document-link checks and
existing backlog checks validate the documentation corrections; no Integration writes
or provider probes occur. Subsequent Codex executions use `gpt-6.1-sol` under
the owner's session direction.

### Next action

The confirmation review is clean. Request publication authorization for this
separate delivery branch and PR. Do not merge or publish automatically.
No changelog fragment is needed: this delivery changes developer evidence and
tracking only, with no shipped command behavior change. Keep #493 and #494
gated; later work needs independently demonstrated delivery/status needs.

## Sibling planned Input paths review ledger

*Opened 2026-10-15.*

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

### Findings and dispositions

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

### Final review window

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

## Sibling planned Input paths pickup

*Opened 2026-10-15.*

### Current route

The plan PR #98 merges at `313c60536`. The implementation on
`run/sibling-planned-input-paths` completes all three steps. Delivery-PR
publication and merge remain pending; the isolated Integration replay stays paused.

Sibling selection is same-owner accepted-roadmap membership for a
roadmap-derived audited plan; otherwise repository-manifest plans. Only
explicit creates grant absent-file exemptions. Undeclared and edit-only
missing paths and stale symbols in existing files remain findings. Unknown,
malformed or conflicting identity cannot widen selection. Resolved structural
source ownership wins over the output plan directory.

### Implementation and verification

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
  [the review ledger](roadmap-plans.md#sibling-planned-input-paths-review-ledger).

### Delivery and next action

The final independent review window converges with two consecutive clean
passes against logic `a25fd51f7`. Publish the code PR after
branch-specific user approval required by the shared directives. Keep the
plan gate unchanged. After the code PR merges, fetch and verify the merged
snapshot in the actual installed tool source before resuming the saved replay.

### Resume the isolated Integration replay

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

## Roadmap → seed → base-plan business-logic testing loop

*Opened 2026-10-16.*

### Pickup and owner decisions

The task is to improve **plan-tool**, using Integration as a benchmark for creation of a complete, appropriately granular set of plans from roadmap artifacts. Improve the existing flow; do not add an alternative creation mode or persistent plan-set layer.

Owner decisions, 2026-10-16:

- **Stop at base plans. Do not create detail files.** The owner limits token expenditure and wants insight from raw base plans.
- **Focus on application business logic.** Infrastructure and other non-business-logic decomposition are lower priority. Preserve existing observed-deployment acceptance obligations; do not spend this loop redesigning infrastructure plans.
- Iterate on evidence from base plans to improve roadmap mapping, selected-row seed materialization and ordinary create. Do not manually repair Integration plans and call that a tool improvement.
- Use **`gpt-6.1-sol` for every Codex execution**.

This supersedes the recommendation to proceed to detail in the initial [base-plan review](../docs/evidence/roadmap-plan-derivation-review.md). The nine-plan, 53-detail retrospective replay remains review context only; no new details are authorized in this loop.

### Where to work

Resolve `<implementation-tool-root>` and `<original-shared-root>` from the
locally selected checkouts with `git -C <checkout> rev-parse --show-toplevel`.
They are distinct roles. `<experiment-root>` is a locally selected isolated
scratch directory containing the named clones and harness; record these roots
in ignored local context. An unavailable original experiment is an evidence
limitation, not a reason to create a directory and claim its recorded results.

| Purpose | Location / identity |
| --- | --- |
| Tool implementation | `<implementation-tool-root>`, branch `implement/roadmap-plan-derivation` |
| Implementation base | `f1cba286a49b95a6ac7900e60f4f2e5fa40a366a` (PR #106 merge) |
| Initial candidate tool frozen for comparison | `5433b3a532e1f2f79526ed679511a2643f04a95d` |
| Isolated experiment root, abbreviated `E` | `<experiment-root>` |
| Baseline tool / Integration clones | `E/baseline-tool`, `E/baseline-integration` |
| Candidate tool / Integration clones | `E/candidate-tool`, `E/candidate-integration` |
| Application baseline | Integration `998a78706a22bcf8b64be7ce382608fff1f8189a` |
| Original accepted roadmap | `integration-aidlc-mvp`, version `c7743c56d7b3da8450d5c4c060dc4a407414fbb77e3967813000a4538f9a4987` |
| Fresh comparison roadmap | `integration-granularity-comparison` |
| Fresh baseline accepted version | `20aabc077c6c338ddbfc84ccddf3bd560a0ee0e3bd5b3d6c62afb68fe8adc8cc` |
| Fresh candidate accepted version | `f373ddd13c76d8dd46791f69d9dd75cf69b604da9f054298e9813b2dca8653fb` |

The original shared checkout at `<original-shared-root>` is not the implementation checkout. Preserve its unrelated untracked handoff. Experiment clones have independent Git stores, manifests and runtime state. Do not use shared worktrees or merge generated output live.

### What the current sample establishes

Baseline mapping has five rows; candidate has ten. All five baseline base plans and eight candidate base plans are captured. Candidate AWS delivery and end-to-end proof remain seeds. The business-logic focus does not require generating those two delivery plans before investigating the captured application routes.

Candidate plans available: `integration-run-foundation`, `integration-runtime-contracts`, `integration-isolated-sessions`, `integration-observable-conversation`, `integration-repository-references`, `integration-ready-handoffs`, `integration-revision-review`, `integration-workflow-experience`. Candidate capture checkpoint `e348508` includes all eight and the unmodified remaining seeds. Browser create has native `run_end`, outcome `ok`, rc 0. No create from that initial batch remains active.

The baseline `integration-ready-handoffs` has one prerequisite-verification-only step despite an implementation outcome. Candidate has six implementation/proof steps. Worker output has a named durable producer and conversation consumes it. Repository-reference identity and browser integration have bounded routes. These are useful observations, not proof of complete semantic coverage or optimal plan count.

The identical-seed worker control uses SHA-256 `bbc4e7f7b8e227cb3dc4193f1611cb05fe30cddd703bbe4643278d16ae12fc6f` in fresh application-baseline clones. Baseline control checkpoint `06c40c0` loses all four local artifact References; candidate `4eb7fd9` retains them. Both creates complete. Their raw plans contain seven and nine steps respectively; counts do not establish quality.

### The iteration procedure

1. **Freeze inputs and preserve raw outputs.** Record tool commit, application baseline, model, accepted version, selected rows, source hashes, exact commands and clone paths. Commit inputs before every model invocation. Keep raw mappings, seeds and first published base plans unchanged. Use a new isolated clone or new first-run store for a changed mapping; never rewrite the original accepted head.
2. **Review a bounded business route.** Select a witnessed obligation such as corrected readiness, durable handoff content, revision identity, disconnected output or submission binding. Start with the source outcome, not a preferred implementation. Avoid regenerating the entire set merely to collect more prose.
3. **Trace the obligation through the pipeline.** Read all relevant domain rules, constraints, components and accepted mapping narrative; then the selected seed; then base-plan body and steps. Write down producer, consumer, required production/update operation, order, integration owner and eventual observable completion. Distinguish repository revision from workflow-configuration revision, and raw output from engine evidence.
4. **Attribute the first gap.** Use the table below. A missing requirement upstream is not a materializer loss; an existing producer is not proof that a newly required operation exists. An absent per-step mechanism is not automatically a base-plan defect.
5. **Make the smallest general tool adjustment.** Enumerate identifier and vocabulary sites before editing. Improve existing prompts/input delivery where the trace supports it. Preserve accepted scope, sibling ownership and uncertainty. Do not add Integration-specific nouns, new schemas, semantic quality gates, fixed counts, mandatory matrices or a new authoring route.
6. **Verify the change.** Run affected hermetic tests, mutate the changed guidance to show its contract test fails, restore exact bytes, and run the required suite. Review correctness and completeness across all affected sites. Commit a bounded change before another plan-tool invocation. Direct code changes require the repository's review convergence loop.
7. **Rerun only the affected creation path.** Prefer identical selected-seed input to isolate create changes, and fixed upstream artifacts to assess mapping changes. Use the existing native roadmap/materialization/create routes. Preserve results before interpretation; do not fix generated plans to improve the comparison. Stop at base plan.
8. **Compare and decide.** State what improves, what remains unclear, where the first loss occurs and whether another bounded adjustment is justified. Keep one-sample limitations explicit. Stop when the latest results add no material actionable base-plan insight, findings mostly describe the last edit, or further progress requires an owner scope decision. Do not spend detail tokens as a substitute for this judgment.

| First gap | Appropriate response |
| --- | --- |
| Requirement absent or ambiguous in upstream source | Record the source limitation; use existing roadmap feedback/review routes if clarification is needed. Do not silently invent it in a seed. |
| Source requirement present but mapping gives no producer/integration owner | Improve stage-four assignment guidance, then test a fresh mapping with the same upstream source. |
| Accepted mapping assignment disappears or changes in selected seed | Improve per-row preservation; do not repartition accepted rows during materialization. |
| Seed contains implementation outcome but create emits only checks/prerequisites | Improve create's grounding guidance: retain conditional implementation work without inventing prerequisite interfaces or implementing sibling scope. |
| Base outcome/ownership is clear but an internal mechanism is unspecified | Record as unassessed at this altitude. Do not author detail or inflate the seed. |
| Source References disappear during create | Verify binary retention using identical input; preserve external research alongside local References. |

### Business-logic observations driving the next adjustment

`rule-handoff-check` in the frozen domain explicitly requires corrected-revision evidence and owner-requested reevaluation. The accepted mapping and seeds preserve these outcomes, but the producer/update operation deserves closer review. Existing `roadmap-plans.md` already says to assign shared producers and consumers: merely repeating that sentence is not a useful change. Sharpen it around the operation that supplies new/corrected evidence, content or identity, including extensions to existing producers.

Cleanup mechanics, safe-output-release policy and durable handoff-content storage are not comparably explicit upstream. Do not assert that materialization dropped them or prescribe mechanisms from retrospective knowledge. Trace whether the business outcome requires a missing source-level contract, and record uncertainty honestly.

The baseline handoff seed says predecessor presence must be established when the plan is created/detailed. That language can collapse future implementation into a prerequisite checklist. Preserve blocked execution/acceptance without changing the authored implementation outcome. Never fabricate a settled prerequisite interface.

### Controlled execution and token use

The initial fixed-upstream harness is `E/roadmap-plan-derivation-fixed-upstream.py`. It calls native `roadmap.run_roadmap`, replays exact frozen stages 1–3 through their native gates, and invokes the real backend only for stage four. Logs report four stages; only the fourth is model-generated. Both initial stage-four outputs pass on their first attempt. The brief is the accepted version's `brief.md`. Do not substitute the repaired replay or inject retrospective owner decisions into generation inputs.

Run commands from the target Integration clone with explicit tool binding, because the global installed tool may point elsewhere:

```sh
env PYTHONPATH=<pinned-tool-clone> \
  <implementation-tool-root>/.venv/bin/python \
  -c 'from plan_tool.cli.app import main; raise SystemExit(main())' \
  --backend codex --model gpt-6.1-sol \
  create <slug> --from-existing <selected-seed> --iterate -y < /dev/null
```

Use durable feature-prefixed logs, `set -o pipefail` when piping, and save the original shell session. Wait for its exit **and** matching native `run_end`. Do not terminate a quiet command or start a duplicate. Only one invocation per plan. No detail, application implementation, deployment or live provider integration tests belong to this benchmark.

The initial nested attempts fail at Codex app-server initialization; the parent session succeeds using the execution tool's approved escalation. Those failure logs remain at `E/*-fresh.log` and `E/*-materialize.log`. A wrapper that calls `main()` without `raise SystemExit(main())` can mask the native exit code; never use its shell status as evidence of completion.

### Completed first business-logic iteration

Tool commit **`586255721`** changes only existing mapping/seed guidance and create's step-proposal guidance, with three focused regression tests. It preserves assigned business production/update/integration operations and keeps implementation conditional on pending prerequisites. No schema, gate, detail prompt or infrastructure decomposition changes. Site enumeration remains `.tmp/roadmap-plan-derivation.business-logic-sites.md`.

Validation completes: **14,636 passed / 67 skipped** in 59.70 seconds. Removing each of the three new guidance clauses independently makes its focused test fail; original bytes are restored. Backlog checks: 30 passed. Two fresh independent completed Codex reviews are clean:

- Review 1: `codex review --base 1ecb8cfa3 -c 'model="gpt-6.1-sol"'`, launched at code snapshot `586255721`; no actionable defects, 58 focused tests pass.
- Review 2: `codex review --commit 586255721 -c 'model="gpt-6.1-sol"'`; no actionable regression, three focused tests pass.

Original shell sessions 53544 (tests), 60261 and 78321 (reviews) all exit 0. Logs and exact review metadata: `.tmp/roadmap-plan-derivation.business-logic-full-tests.log`, `.business-logic-review-{1,2}.log` and `.business-logic-reviews.json`, each prefixed with `roadmap-plan-derivation`. These are Codex reviews, not the user's separate Claude Code session.

#### Unchanged-seed rerun

New independent full clone: `E/business-logic-loop1-integration`, checked out at **`1b7e769`**, exactly the baseline checkpoint immediately before its handoff create. The existing three baseline planning outputs are therefore present in both runs. Tracked changes against application baseline are planning/manifest/brief paths only. Copy both ignored immutable stores byte-for-byte; do not copy another arm's generated plans or runtime checkpoints. Remove the clone's remote. No manual seed or plan repairs. Raw rerun capture checkpoint: **`1d69e52`**.

Selected seed: `docs/implementation-plans/roadmaps/integration-granularity-comparison/plan-seed-drafts/integration-ready-handoffs.md`, SHA-256 **`2b1a13d2ae6d2765ab96ebf3d71330332bdd8ab95104f7f2d4f70a03e525842c`**. Native `create integration-ready-handoffs --from-existing <seed> --iterate -y` uses implementation tool commit `586255721`, explicit PYTHONPATH, Codex `gpt-6.1-sol`, and closed stdin. Mapping and seed are unchanged; this rerun exercises the create adjustment, not the changed mapping or materialization prompts.

Log: `E/business-logic-loop1-ready-handoffs-create.log`. Run id **`2026-10-16T19-03-42+00-00-0000db`**. Original session 29179 exits 0; native `run_end` records outcome `ok`, rc 0 and duration 190114 ms. No process remains active.

| Baseline raw plan | Rerun raw plan |
| --- | --- |
| One non-code step checks predecessors and stops implementation. | Five steps: (1) prerequisite verification, (2) durable completion and final workflow closure, (3) revision-bound readiness, (4) authorized inspection/reevaluation/continuation, (5) integrated API/browser proof. |
| The implementation outcome in the seed has no corresponding implementation route. | Implementation remains authored behind explicit prerequisite dependencies; actual producer integration is bound after predecessors land. |

Insight: **planning-time grounding must not turn an execution prerequisite into deletion of the business implementation outcome**. The rerun supports this bounded fix in one sample; it does not establish a general success rate. The source phrase requiring predecessor presence at create/detail remains unchanged, so seed guidance also needs to avoid introducing that phase confusion in future materializations.

The separate question of who supplies corrected evidence remains unresolved: the new plan recognizes current evidence, checks applicability and reevaluates after correction, but this does not independently demonstrate the upstream production/update contract. Do not claim the entire original handoff gap is closed.

### Completed second business-logic iteration

The [corrected-evidence trace and results](../docs/evidence/roadmap-corrected-evidence-iteration.md) records source anchors, commands, raw artifacts, hashes, limitations and outcomes. No further production change is necessary: this iteration tests the already-reviewed guidance at `586255721` (invocation snapshot `cacea5aa3`).

First incomplete assignment: the domain rule, correction requirement and component roles survive into the original seed/base plans, but the accepted stage-four narrative does not explicitly assign the operation producing corrected content and renewed evidence. Worker evidence supply and consumer reevaluation alone do not establish that operation. This is a mapping-responsibility gap rather than loss of `rule-handoff-check` during seed creation.

Independent full clone: **`E/business-logic-loop2-seed-integration`**, detached, no remote, initialized from `5e72651`. Remove only the selected old handoff draft in this copy and commit as `f5ab5a4`; all original stores and other seeds remain unchanged. Original source files and prior comparison outputs are never repaired.

| Test | Observed result | Raw checkpoint / native run |
| --- | --- | --- |
| Materialize only `integration-ready-handoffs` against existing `f373` mapping | Preserves corrected-revision rules and implementation behind missing prerequisites. Does not invent the unassigned production operation. Other nine seeds are visible, so this is not an identical-corpus wording comparison with original all-row generation. | `8006a29`; `2026-10-16T19-30-37+00-00-447e57`, completed rc 0, 63.545s |
| Generate one new stage-four mapping with updated guidance | Ten rows again. `isolated-step-execution` owns initial/corrected outputs and renewed evidence; `revision-safe-step-handoffs` requests the operations and evaluates results. `assumption-completed-revision-correction` names unsupported completed-content correction and rules out consuming unfinished-step replacement. | `555bb07`; `2026-10-16T19-32-35+00-00-078566`, completed rc 0, 110.341s |
| Materialize only new `revision-safe-step-handoffs` | Retains the producer/request/evaluate chain, all five dependencies, proof requirements and explicit unsupported-correction stop condition. No seed correction needed. | `7e1a172`; `2026-10-16T19-35-41+00-00-8ffde6`, completed rc 0, 97.064s |
| Create only that base plan with `--iterate -y` | Six steps include supported input/evidence production requests, completed-content correction without replacement, guarded continuation and real integrated proof. References and uncertainty survive. | **`9211d7e`**; `2026-10-16T19-37-42+00-00-64bdb4`, outcome ok, rc 0, 301.134s |

New roadmap slug: `integration-business-logic-loop2`, accepted version **`41c1e9369d922888946f93d9f76b31bd42cc2e798909053372abbfbeec770e49`**. Harness `E/roadmap-plan-derivation-business-loop2.py` replays frozen upstream through native gates and invokes the model only for stage four, first attempt. Accepted stages 1–3 and brief are byte-identical to the prior accepted candidate. Native publication adds trailing newlines to unnormalized source responses; compare accepted copies to accepted copies. No source-content change is responsible for the mapping observation.

Seed SHA-256: `d6b659741d4c73dae933735ae8cf85be3f438a727c557fd2e3dd28f26c97a7bb`. Base-plan SHA-256: `c35cb2d0f0f1a6b05bf446efe41b59fc9a3884c2261cef28b995d2729b0a52a7`. JSON boundary checks and feature-prefixed logs remain in `E`; exact names are in the evidence record. Both original immutable stores and accepted heads remain byte-identical. No application code or detail files are created. Original sessions 80433, 64508, 31565 and 87128 all exit 0 with native run_end; no model call remains running.

Insights: operation ownership improves completeness without increasing plan count; correction after completion and replacement after failure are distinct business cases; seeds should preserve assigned supply operations, not just checks; runtime support stays an explicit prerequisite. These are planning observations, not evidence of supported runtime behavior, a general success rate or full Integration-gap closure. Do not call this raw plan execution-ready or detail-grounded.

### Paused pickup: handoff-content continuity

**Paused at the owner's request, 2026-10-16.** The [read-only handoff-content trace](../docs/evidence/roadmap-handoff-content-trace.md) is complete. No model run, detail authoring or application implementation occurs during this trace, and no process remains running.

Question: does the next runtime receive the actual work produced at the intended revision, rather than only a ready flag, revision metadata or retained console output?

Findings:

- The new mapping and handoff base plan already require supported production of actual successor inputs and proof of successor consumption. This improves the consumer contract.
- The actual input package remains an explicit source uncertainty under `runtime-contract-proof`, `assumption-successor-input-production` and pending `decision-provisional-runtime-native-handoff`.
- The settled session-store boundary keeps live processes, checkout and credentials inside the worker. Durable output history is not proof of durable handoff-artifact content. Do not infer permission to store secret-bearing state or add recovery requirements.
- The earlier worker base plan is from the initial `f373` mapping; no producer seed/base plan for new `isolated-step-execution` exists in the `41c1` mapping yet. Do not report an ungenerated artifact as an omission.
- No new tool defect or prompt change is established by the read-only trace. Mechanism details remain deliberately unselected.

#### Producer seed result and Integration check (2026-10-16)

`isolated-step-execution` was materialized alone in `E/business-logic-loop3-producer-integration` (raw capture `ffe10a6`, seed SHA-256 `6fecb9125c98ba776455da41811552352fbafb35870e52be914639eff613cfc7`, exit 0). The seed preserves production, correction and renewed-evidence operations and the open `assumption-successor-input-production`, but the accepted source assigns no owner for making produced output available to the successor. First gap: accepted source and mapping, not materialization. No base plan was created; one would restate the same question.

Integration already implements that availability (immutable released handoff sets in Aurora, delivered to the successor launch only for a passing predecessor revision). It was absent from the Integration base plan through the bare-stage audits and appeared only after detail authoring (`8dcdb8b`), so bare plans did not identify it there. Integration needs no roadmap feedback item. Evidence and the unfiled plan-tool finding: [handoff-content trace](../docs/evidence/roadmap-handoff-content-trace.md).

#### Guidance change and loop-5 result (2026-10-16)

The availability finding became a whole-chain hop-trace clause in `roadmap-plans.md` (commit `0d8d7ca95` on `implement/roadmap-plan-derivation`; full suite 14,637 passed / 67 skipped; two `/code-review` high rounds, stopped on a same-line flip). A fresh mapping on the frozen upstream (`E/business-logic-loop5-hoptrace-integration`, raw capture `c1a0f22`) names an owner for every hop, and the producer and handoff seeds carry them. Residual (accepted known limit): the producer seed does not state worker release of handoff content for the successor. Details and limits: [handoff-content trace](../docs/evidence/roadmap-handoff-content-trace.md) § "Guidance change and mapping reruns".

**Pickup:** Decided 2026-10-16: (1) the residual producer-seed wording is an accepted known limit at seed altitude; no further guidance change. (2) No backlog entry for a mapping-altitude audit: three stage-4 samples on the frozen upstream (loop5-7) all owned every hop (see the trace's variation check). Deliberately not filed; reopen only if a second route shows an unowned hop, citing BACKLOG #435 as the model-judged narrative-review precedent and keeping any audit advisory with no gate or exit-code change. (3) Decided 2026-10-16: the third `/code-review` (high, headless) on `0d8d7ca95` is deferred to the pre-publication pass, before any push or PR; nothing has changed in the code since round 2. No details; no base plan from these seeds.

#### Pre-publication `/code-review` (high, 2026-10-16 branch diff, `0d8d7ca95`)

The first run was mis-scoped (target `f1cba286a` was read as the #106 merge commit; its findings are void, log `.misscoped-merge-106.log`). The rerun with the default `merge-base...HEAD` target returned eight findings; log `.tmp/roadmap-plan-derivation.pre-publication-code-review-high.log` in the implementation checkout.

| Finding | Disposition |
| --- | --- |
| Committed docs name AI assistants (handoffs, BACKLOG) | Not applied: the owner's standing decision (2026-09-25) is that attribution greps and scrubs are not worth cycles. |
| Plan `status: completed` while #496 stays open | Not applied: #496 deliberately stays open through implementation and comparison review; plan status tracks plan steps. |
| 8 raw run-reconcile reports committed | Not applied: `reports/` is committed repo-wide (936 tracked files). |
| Prompt tests pin fixed phrases | Not applied: matches the existing prompt-test convention; the changed guidance was mutation-verified. |
| Hop-trace rule could inflate row counts | Not applied: no count target by design; three samples gave 10, 10 and 9 rows. |
| `create.py` References restore and render use substring dedup at two sites; restore appends a missing section at end of file | Awaiting owner decision: low-severity edge, same class at two sites. |
| New step-proposal prompt text applies to every `create`, not only roadmap-derived seeds | Awaiting owner decision: scope question, not a defect. |

Decisions on the two open rows (2026-10-16, owner): the References substring dedup was fixed as a class; the shared step-proposal prompt text stays as is. Known tradeoff: the same prerequisite guidance sits in the roadmap prompts and the shared step-proposal prompt, so the two can drift.

Branch-wide `/code-review` (high), four rounds on `merge-base...HEAD` after a discarded mis-scoped first run. Round 1: five dismissed, References dedup fixed as a class. Round 2: five of seven on the new helper. Round 3: the line-merge helper flipped to indentation and fenced-block symptoms, so the invariant was stated (a protected References block is never dropped or split; it is present when verbatim and contiguous, else appended once, idempotent) and the helper replaced. Round 4: seven findings, four on the latest edits or a status line (an emptied References heading, a frontmatter anchor scan, a stale verification claim, partial-block duplication), three repeats (assistant names in docs: owner decision 2026-09-25; shared step-proposal prompt: owner decision above; seed-versus-plans prompt wording: read three times, the seed text preserves what the mapping assigns and does not contradict it). Applied: the empty heading is filled in place, frontmatter is excluded from the scan, the BACKLOG claim is dated. Accepted limit, owner to confirm: a partially edited protected block can leave one duplicated bullet; rounds 2 and 4 want line-level append and round 3 wants block integrity, so the block-integrity side was chosen (no dropped content). Stopped on a self-seeded majority; no round 5. Code head `1ddc48bf9`, full suite 14,642 passed / 67 skipped (`.tmp/roadmap-plan-derivation.references-dedup4-full-tests.log` in the checkout).

Seed-altitude audit pilot (2026-10-16): no tool command audits a seed; the repo rule makes it a session procedure. Two independent read-only audits of the loop-5 seeds found no material defect (four LOW, confirmed) and verified the repository claims. A blind sensitivity check on a scratch copy with three planted defects caught all three. Disposition: run the procedure after `--materialize`; no verb, no backlog entry. Details and limits: [trace](../docs/evidence/roadmap-handoff-content-trace.md) § "Seed-altitude correctness audit pilot".

The implementation shipped in PR #107 (merged to `main` as `b90edb570`, code head `1ddc48bf9`, full suite 14,642 passed / 67 skipped). The working checkout `<implementation-tool-root>` is scratch. Preserve the unrelated untracked token-ledger handoff in the original shared checkout.

BACKLOG #496 closed 2026-10-19: the loop met its stop condition. The closure record, including what was deliberately not done and the accepted limits, is in [backlog decisions](../docs/history/backlog-decisions.md#496--roadmap-mapping-and-seed-to-plan-derivation-in-the-existing-pipeline).

### Related records

- [Benchmark inputs and witnessed gaps](../docs/evidence/roadmap-plan-set-benchmark.md)
- [Initial base-plan assessment](../docs/evidence/roadmap-plan-derivation-review.md)
- [Comparison record](../docs/evidence/roadmap-plan-derivation-comparison.md): the resumed section records observations; lower sections retain the initial failed-attempt provenance.
- [Implementation handoff](roadmap-plans.md#roadmap-plan-derivation-implementation)
- [#496 closure record](../docs/history/backlog-decisions.md#496--roadmap-mapping-and-seed-to-plan-derivation-in-the-existing-pipeline) (closed 2026-10-19)

## Roadmap plan derivation implementation

*Opened 2026-10-16.*

### Current testing direction

Owner decision, 2026-10-16: stop at base plans and focus the next tool iterations on application business logic. The [base-plan testing workflow](roadmap-plans.md#roadmap--seed--base-plan-business-logic-testing-loop) is the current pickup record. It supersedes further detail authoring and broad infrastructure experimentation. Eight candidate base plans are captured; two delivery rows remain seeds. The identical-seed control completes and demonstrates local References retention. Earlier in-progress notes below are dated implementation provenance, not the current testing instructions.

### Current checkpoint

PR #106 is merged at origin/main f1cba286a. Implementation branch implement/roadmap-plan-derivation uses the independent clone /private/tmp/plan-tool-roadmap-plan-set-20261016. Steps 1–4 are green through run --accept --commit and full plan test gates. Step 5, the matched isolated Integration comparison, remains pending. The claimed outcome requires improved plan boundaries, not context retention or added steps alone.

### Execution evidence

All model-backed runs use explicit clone PYTHONPATH, backend codex and gpt-6.1-sol. Refresh origin/HEAD from Bitbucket before run: this clone inherits a stale investigation-branch pointer; the official remote reports main. No merge-check bypass occurs.

Backend calls commit code/tests before returning, so the post-call dirty-file test-authoring gate misses those committed deltas. Verify each actual commit, then certify via native run --accept --commit with the full plan test command. Keep the test gate enabled. BUG_BACKLOG.md records the issue separately; its repair is outside #496.

- Step 1: 7bc7aff8b, mapping prompt and tests; 31 focused checks, 23 removal mutations, roadmap tests 592 passed/65 skipped. Native run 2026-10-16T17-11-50+00-00-1e4c8f records the authorship limitation. Full gate accepts the step.
- Step 2: 8bc83ec59, seed prompt and tests; 72 focused checks, seven mutation checks, full suite 14,622 passed/67 skipped. Native run 2026-10-16T17-15-25+00-00-1abf9c. Full gate accepts the step.
- Step 3: 85adfc1d4, create References retention and integration regression; affected tests 1,646 passed/65 skipped, full suite 14,631 passed/67 skipped; five retention mutations fail. Native run 2026-10-16T17-20-36+00-00-405231. Full gate accepts the step.
- Step 4: f9d858f9f, both seed handoffs and guide; affected tests 1,646 passed/65 skipped, final regression and proof-removal mutation verified. Full gate accepts the step.

### Remaining work

Run step 5 without mutating the real Integration checkout or frozen accepted source. Compare fresh mappings with equivalent upstream inputs, and compare both handoffs from the same accepted mapping separately. Preserve raw output before repairs and assess plan-level granularity explicitly. Source artifacts remain available in the frozen Integration experiment. No application or provider execution is authorized. Then drive plan-canonical reconcile-code sweeps and code review under the directives; user owns the separate Claude Code review session. Do not claim that review has run here.

### Reconciliation checkpoint

Sweep 1 covers all four code steps (non-code step 5 skipped), reports 20261016-175738 through 20261016-180057. Steps 1/2/4 are clean; step 3's medium step3-run-reconcile-9104ee21 is confirmed coverage debt: parameterizing resume does not exercise cached preparation, and the helper-only restoration check does not reach successful continuation/finalization. Five existing disputed tests pass before the fix. Identifier and vocabulary enumeration is retained in task-specific triage scratch.

Commit 30534a842 adds actual checkpoint reuse across a selected-source change and successful normalized reference refresh/finalization. Full suite: 14,633 passed/67 skipped. Disabling raw-source Reference capture makes both new tests fail, and exact source restoration is verified. No production code changes are necessary for that finding. Sweep 2 covers all four code steps, reports in the 20261016-1805 through 1807 range, with zero recommendations in every report. No third full sweep is warranted on this clean result.

The nested step-5 benchmark attempt cannot initialize Codex and records a blocked sample. The parent session resumes in its functioning execution context: baseline tool f1cba286a, candidate tool 5433b3a53, independent Integration and tool clones under /private/tmp/roadmap-plan-derivation-comparison-20261016. A scratch-only fixed-upstream invoker supplies identical accepted stages 1–3, using the native runner and real Codex generation for stage 4. Baseline accepts five rows (version 20aabc077c6c338ddbfc84ccddf3bd560a0ee0e3bd5b3d6c62afb68fe8adc8cc); candidate accepts ten (version f373ddd13c76d8dd46791f69d9dd75cf69b604da9f054298e9813b2dca8653fb). All five baseline and ten candidate seeds materialize. Raw plan creation is in progress. No improvement or shipment is established by counts alone.

### Code-review convergence

Two independent completed Codex CLI reviews cover f1cba286a..c9df62518 using codex review --base f1cba286a with model gpt-6.1-sol. Both report no actionable regressions and independently run the affected create/roadmap modules: 1,648 passed/65 skipped. No logic changes occur between the two reviews. Reviewed-range/method metadata, final reports and progress logs remain under .tmp/roadmap-plan-derivation.code-review-{1,2}.*. These are Codex reviews, not Claude Code skill runs; the user owns that separate session. Full suite for the reviewed code: 14,633 passed/67 skipped. Code-review convergence does not establish the still-running benchmark's granularity outcome.

## Roadmap plan breakdown — review handoff

*Opened 2026-10-23.*

Review whether stage 4 incorporates the useful lessons from seed breakdown at
roadmap altitude. Treat the plan list in `04-roadmap.md` as a critical design
artifact, analogous to reviewing the step list in a bare plan: its boundaries,
responsibilities and dependencies shape everything authored downstream.

### Pickup state

| Item | State |
| --- | --- |
| Grounding snapshot | `adba0f005`, main after merged PR #153 |
| User concern | The plan-ID list must reflect deliberate decomposition, rather than receive attention only after seeds expose oversized or incomplete plans. |
| Current work | Review handoff only; no confirmed decomposition bug or approved implementation change. |
| Separate completed work | PRs #151–153 clarify seed materialization, plan-row selection and demo workflow. They do not change stage-4 decomposition. |
| Next action | Compare existing rules and representative retained outputs; report evidence-backed gaps or conclude that no change is justified. |

### Current contract and owners

| Surface | What it owns | Read first |
| --- | --- | --- |
| Stage-4 plan mapping | Cohesive plan outcomes, scope boundaries, delivery ownership, prerequisites, ordering and eventual proof | [Stage-4 prompt](../plan_tool/prompts/roadmap-plans.md), especially “Map complete implementation responsibilities”; [roadmap schema](../ROADMAP_FORMAT.md#04-roadmapmd--frontmatter-schema) |
| Roadmap structure checks | Row identity, coverage, references, ordering, intent/non-goal presence and other observable contracts | [Roadmap gates](../plan_tool/roadmap_gates.py), especially `check_plan_review_context`, `check_component_plan_coverage`, `check_plan_ordering_totality` |
| Seed one-plan versus split judgment | Cohesive effort versus independent top-level efforts, grounded in concrete shared implementation when claimed | [Seed distillation prompt](../plan_tool/prompts/distill-seed.md), “Decide: one plan, or many?”; [seed format](../SEED_FORMAT.md) |
| Materialization | Expand the selected accepted row into its draft seed while preserving supplied responsibilities and boundaries | [Seed materializer prompt](../plan_tool/prompts/roadmap-seed.md), [materializer](../plan_tool/roadmap.py), [seed workflow](../docs/how-to/roadmap.md#7-promote-accepted-draft-seeds-or-create-directly-from-them) |
| Accepted roadmap changes | Reviewer ledger input, inert candidates, review and promotion | [Feedback lifecycle](../ROADMAP_FEEDBACK_FORMAT.md), [immutable artifact contract](../ROADMAP_FORMAT.md) |

Stage 4 already requires a cohesive outcome, explicit boundary, identifiable
prerequisites and verifiable completion for every plan. It explicitly says to
split overly broad **plan rows**: splitting the steps of one broad plan is not
a substitute. It allows keep/merge/split/cross-cutting delivery shapes, rejects
fixed plan counts and directory-based boundaries, assigns shared producers and
consumer integration, and names ownership for each required business transition.
The rows collectively stay within the smallest end-to-end proof boundary.

The stage-4 prompt reads the brief and three upstream artifacts only; it forbids
repository inspection. Seed distillation can reason about named implementation
coupling. Do not copy its file/function-based criterion literally into stage 4
or infer that every downstream split proves a stage-4 defect.

Materialization preserves the accepted row and narrative. It must surface an
overly broad mapping through roadmap review, **not repartition accepted rows**.
The later create route can still return a split proposal; trace the reason
before deciding which earlier boundary, if any, needs correction.

### Identity and relationships

- A roadmap plan row's `id` identifies a proposed implementation effort; its
  title is human-facing text. The printed create handoff reuses the row ID as
  its plan slug.
- Component-to-plan coverage can be many-to-many: one component can need several
  plans, and one plan can span components. Do not equate a component with a plan.
- The current schema assigns one `draft_seed_path` to each plan row. Materialize
  selects that existing row ID before its seed file exists. This current
  row-to-draft contract is distinct from broader conceptual relationships among
  roadmap responsibilities, seeds and eventual plans.
- This review does not authorize a new seed-sharing/cardinality contract or
  a repartitioning of accepted roadmaps.

### Review procedure and evidence

1. Compare stage-4, seed-distillation and materialization guidance. Build a small
   matrix: principle, current stage-4 provision, seed-side provision, justified
   altitude difference, and any remaining gap. Check instruction composition in
   `roadmap.py`, not just the standalone prompt text.
2. Inspect the existing `TestPlansPromptTemplate` tests in
   [tests/test_roadmap.py](../tests/test_roadmap.py). They pin responsibility
   guidance, shared production/integration, handoffs, sizing and acceptance;
   prompt-presence assertions do not establish model decomposition quality.
3. Select a small, explicitly named set of retained stage-4 artifacts and their
   source brief/upstream versions, where available. Record exact paths,
   versions and source availability; mark unavailable evidence. Do not silently
   evaluate every roadmap or treat synthetic fixtures as successful live runs.
4. For each reviewed plan row, identify its outcome, non-goals, producer/consumer
   responsibilities, necessary integration, dependency handoffs and completion
   proof. Ask whether the complete plan set delivers the source-required path,
   whether any responsibility lacks an owner, and whether a row combines
   independent efforts or fragments one cohesive effort unnecessarily.
5. If downstream seeds/create split a row, compare the saved evidence and code
   grounding with the original accepted mapping. Distinguish an original mapping
   gap from new code knowledge, source changes or a materializer's own omission.
6. Report findings before applying changes: source, row IDs, failure scenario,
   actual missing principle, existing guidance/tests, and smallest plausible
   remedy. Present consequential scope/decomposition choices to the user.

Use the [roadmap demo's plan-mapping review](../docs/demos/roadmap-demo.md)
as a reading exercise, not evidence that a fresh run passes. The analogy to a
bare plan sets the level of scrutiny; it does not mean `completeness-audit`
accepts a roadmap or that its plan/detail audit loop already reviews stage 4.

### Scope fence and stopping rule

**In scope:** assessment of existing stage-4 decomposition guidance and its
relationship to seed breakdown, prompt assembly/tests, and named retained
outputs. Deliver a comparison matrix, evidence-backed findings and a proposed
bounded follow-up only if a real gap remains.

**Out of scope:** implementing prompt/schema/CLI changes in this handoff task;
repository grounding inside stage 4; new fields, automatic semantic gates,
quality scores, fixed size/plan-count thresholds, changing seed cardinality,
new concurrency, and live generation/rehearsal or publication without a separate
request. Do not turn a judged property into a vocabulary matcher.

If existing rules already cover the observed issue, identify whether the remedy
is clearer review practice, a prompt-delivery defect or an evidenced behavior
failure. Do not add another restatement merely because an output can be bad.
If representative evidence is unavailable, report that limit before proposing
new generation work. If no material gap is established, close the assessment
without an implementation proposal. Structural changes need their own scope
and user decision; use the normal plan/review workflow if work is authorized.

### Requested pickup result

Return the rule comparison, the named evidence examined, findings with source
and responsibility ownership, and unresolved decisions. Separate demonstrated
defects from hypotheses and advisory review questions. Preserve accepted-head
selection and existing roadmap review/promotion authority throughout.

### Handoff verification

All local link targets and heading anchors resolve; whitespace checks pass.
Two independent actual Claude Code `code-review` Skill sessions review
`adba0f005..92a7643f284f045ce1e24775d6085f3eba8b22c5` with
`claude-sonnet-5-5 --effort high` and reach **low-yield convergence**: no
material defects, only optional navigation/retention wording. Those advisories
do not expand the assessment scope or presume a code change. No runtime tests,
live roadmap generation or decomposition assessment occur in this handoff task.

Review 1 session: `3be992df-f64e-4dfe-b50e-00c38967f64c`.

Review 2 session: `b248a04f-9456-4b2d-8e4a-654961fc3bcd`.

## Roadmap plan-row selector documentation

*Opened 2026-10-23.*

The starting-point guide describes artifact publication, selected seed
materialization/review and separate plan creation. It no longer claims stage
runs emit seeds or implementation plans. Related README, common-workflows,
roadmap-guide and TTRPG demo examples use `<roadmap-plan-id>` instead of
`first-plan` / `my-first-plan` and explain its existing `plans[].id` source.

The plan row and declared seed path exist before first materialization. The
selector is neither a seed filename nor a newly assigned plan name. Omitting
it processes all recoverable drafts. Actual reported draft/promoted paths
replace assumed basenames, and later create remains a separate action.

### Scope and sites

Invariant: intake guidance distinguishes existing roadmap plan-row selection
from generating a seed and creating an implementation plan. Identifier searches
cover `first-plan`, `my-first-plan`, `--materialize` and `plans[].id`; vocabulary
searches cover emitted plans, draft plan seeds and plan naming. The five
reading surfaces above receive the same bounded clarification. Runtime CLI
syntax, stage-4 decomposition and lifecycle behavior are unchanged.

Sources: `plan_tool/cli/roadmap_cmd.py` resolves the optional materialize operand
against accepted row classifications; `ROADMAP_FORMAT.md` defines plan ids and
seed destinations; `docs/how-to/roadmap.md` section 7 owns later seed state.

- Seed-path and CLI-reference tests: **15 passed**.
- All five surfaces name the selector; the added guide anchor resolves.
- `git diff --check` passes.
- Two independent actual built-in Claude Code reviews target
  `e1eae0c0a..c2cb06e3f903d364753e09ecf8011d19d2aac1b4`, with
  `claude-sonnet-5-5 --effort high`. Round 1 finds no correctness defect;
  round 2 returns only low-severity wording feedback. This is **low-yield
  convergence**, not a claim that both reviews have no advisory output.
- Retained wording advisories: explicitly name materialize output as the
  source of the repo-relative draft path (the seeds view is for state), and
  say the tool's later create handoff reuses the selected roadmap ID. Current
  examples use that same placeholder and actual reported paths, so neither
  changes the selector contract. Optional line wrapping is also retained.
- Other candidates are refuted or declined: explained placeholders are
  substitution notation; no-ID versus selected-ID examples are alternatives;
  missing per-state lifecycle detail belongs to the linked guide. A current
  draft's selected-ID refusal does not contradict what the selector identifies.
- The fulfilled starting-point backlog entry is removed. Runtime promotion
  summary wording remains separately tracked and unchanged.

Review 1 session: `3046877a-4e3b-4c16-a60c-c30dc4814c00`.

Review 2 session: `fe1891fe-3f2e-47d6-9a27-7a703bc7f04b`.

## Roadmap seed examples

*Opened 2026-10-23.*

`docs/how-to/common-workflows.md` separates roadmap stage publication from
explicit seed materialization. The examples review the mapping, materialize
all recoverable drafts or a selected plan ID, inspect state and reported paths,
and review seed scope/references/Stack/prerequisites before create.

Direct draft consumption and optional promotion are alternatives. New promoted
seeds default to `docs/implementation-plans/plan-seeds/`; recorded legacy
publication and draft paths remain supported. The guide names the actual
reported path, preserves plan ordering/scope fences and continues through
both ordinary plan audit gates. No runtime behavior or default changes.

### Sites and evidence

Invariant: copied examples consume an explicitly materialized, reviewed seed
at its reported location; stage completion alone supplies no seed file.
Identifier search (`plan-seeds/`, `seeds/`, `materializ`) and vocabulary search
(`draft seed`, `ordered create`) locate the roadmap overview and the ordinary
pipeline handoff. Both sites receive the correction. The unchanged lifecycle
prose and other workflow sections remain outside this task.

Sources: `plan_tool/seed_paths.py` for nested/default versus legacy publication;
`docs/how-to/roadmap.md` section 7 for materialization, digest acceptance and
optional promotion; the generated roadmap command reference for flags.

- `uv run pytest tests/test_seed_paths.py tests/cli/test_cli_reference.py -q`: **15 passed**.
- The added seed-preparation link and heading anchor resolve.
- `git diff --check` passes.
- Initial reviews of `46daebb53..cc24341fc` use actual Claude Code Skill
  invocations (confirmed in session logs). One persisted first-round report
  describes its internal inline recipe as no Skill invocation; the outer
  session log explicitly contains `Skill(code-review)`. Round 2 records the
  invocation directly. Both verify the tracked source/path correction.
- A bounded follow-up changes inspection to `--view seeds`, separates the
  materialization heading, clarifies preserving hand edits before regeneration
  and explicitly points at the printed promotion create handoff.
- Two independent final actual Claude Code reviews of
  `46daebb53..fe525f41d986483cc0b9ea53fb96dc0edb2dace8` converge at **low-yield**:
  zero factual/correctness defects, only low-severity presentation feedback.
  Retained advisories: the seed subsection also contains general read-back
  prose; the conditional preservation warning appears before the first-run
  command. Neither changes the executable route or path contract. No further
  iteration is needed for the tracked defect.
- Final focused checks repeat with **15 passed**. The original backlog entry
  is removed with this correction. Separate README materialization drift and
  the destination-specific promotion summary are filed in BUG_BACKLOG; neither
  is claimed fixed here.

Review 1 session: `d21d9904-d78c-49eb-a4be-4e0877272516`.

Review 2 session: `e4a33535-6995-4092-b1bf-6df0e2b99b18`.

Review 3 session: `e392ae9a-3855-48bc-94b9-000b4a06c8e6`.

Review 4 session: `b9ad6952-4891-41f3-a990-94b926a48e36`.
