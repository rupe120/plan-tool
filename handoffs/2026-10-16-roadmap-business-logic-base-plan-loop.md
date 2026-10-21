# Roadmap → seed → base-plan business-logic testing loop

## Pickup and owner decisions

The task is to improve **plan-tool**, using Integration as a benchmark for creation of a complete, appropriately granular set of plans from roadmap artifacts. Improve the existing flow; do not add an alternative creation mode or persistent plan-set layer.

Owner decisions, 2026-10-16:

- **Stop at base plans. Do not create detail files.** The owner limits token expenditure and wants insight from raw base plans.
- **Focus on application business logic.** Infrastructure and other non-business-logic decomposition are lower priority. Preserve existing observed-deployment acceptance obligations; do not spend this loop redesigning infrastructure plans.
- Iterate on evidence from base plans to improve roadmap mapping, selected-row seed materialization and ordinary create. Do not manually repair Integration plans and call that a tool improvement.
- Use **`gpt-6.1-sol` for every Codex execution**.

This supersedes the recommendation to proceed to detail in the initial [base-plan review](../docs/evidence/roadmap-plan-derivation-review.md). The nine-plan, 53-detail retrospective replay remains review context only; no new details are authorized in this loop.

## Where to work

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

## What the current sample establishes

Baseline mapping has five rows; candidate has ten. All five baseline base plans and eight candidate base plans are captured. Candidate AWS delivery and end-to-end proof remain seeds. The business-logic focus does not require generating those two delivery plans before investigating the captured application routes.

Candidate plans available: `integration-run-foundation`, `integration-runtime-contracts`, `integration-isolated-sessions`, `integration-observable-conversation`, `integration-repository-references`, `integration-ready-handoffs`, `integration-revision-review`, `integration-workflow-experience`. Candidate capture checkpoint `e348508` includes all eight and the unmodified remaining seeds. Browser create has native `run_end`, outcome `ok`, rc 0. No create from that initial batch remains active.

The baseline `integration-ready-handoffs` has one prerequisite-verification-only step despite an implementation outcome. Candidate has six implementation/proof steps. Worker output has a named durable producer and conversation consumes it. Repository-reference identity and browser integration have bounded routes. These are useful observations, not proof of complete semantic coverage or optimal plan count.

The identical-seed worker control uses SHA-256 `bbc4e7f7b8e227cb3dc4193f1611cb05fe30cddd703bbe4643278d16ae12fc6f` in fresh application-baseline clones. Baseline control checkpoint `06c40c0` loses all four local artifact References; candidate `4eb7fd9` retains them. Both creates complete. Their raw plans contain seven and nine steps respectively; counts do not establish quality.

## The iteration procedure

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

## Business-logic observations driving the next adjustment

`rule-handoff-check` in the frozen domain explicitly requires corrected-revision evidence and owner-requested reevaluation. The accepted mapping and seeds preserve these outcomes, but the producer/update operation deserves closer review. Existing `roadmap-plans.md` already says to assign shared producers and consumers: merely repeating that sentence is not a useful change. Sharpen it around the operation that supplies new/corrected evidence, content or identity, including extensions to existing producers.

Cleanup mechanics, safe-output-release policy and durable handoff-content storage are not comparably explicit upstream. Do not assert that materialization dropped them or prescribe mechanisms from retrospective knowledge. Trace whether the business outcome requires a missing source-level contract, and record uncertainty honestly.

The baseline handoff seed says predecessor presence must be established when the plan is created/detailed. That language can collapse future implementation into a prerequisite checklist. Preserve blocked execution/acceptance without changing the authored implementation outcome. Never fabricate a settled prerequisite interface.

## Controlled execution and token use

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

## Completed first business-logic iteration

Tool commit **`586255721`** changes only existing mapping/seed guidance and create's step-proposal guidance, with three focused regression tests. It preserves assigned business production/update/integration operations and keeps implementation conditional on pending prerequisites. No schema, gate, detail prompt or infrastructure decomposition changes. Site enumeration remains `.tmp/roadmap-plan-derivation.business-logic-sites.md`.

Validation completes: **14,636 passed / 67 skipped** in 59.70 seconds. Removing each of the three new guidance clauses independently makes its focused test fail; original bytes are restored. Backlog checks: 30 passed. Two fresh independent completed Codex reviews are clean:

- Review 1: `codex review --base 1ecb8cfa3 -c 'model="gpt-6.1-sol"'`, launched at code snapshot `586255721`; no actionable defects, 58 focused tests pass.
- Review 2: `codex review --commit 586255721 -c 'model="gpt-6.1-sol"'`; no actionable regression, three focused tests pass.

Original shell sessions 53544 (tests), 60261 and 78321 (reviews) all exit 0. Logs and exact review metadata: `.tmp/roadmap-plan-derivation.business-logic-full-tests.log`, `.business-logic-review-{1,2}.log` and `.business-logic-reviews.json`, each prefixed with `roadmap-plan-derivation`. These are Codex reviews, not the user's separate Claude Code session.

### Unchanged-seed rerun

New independent full clone: `E/business-logic-loop1-integration`, checked out at **`1b7e769`**, exactly the baseline checkpoint immediately before its handoff create. The existing three baseline planning outputs are therefore present in both runs. Tracked changes against application baseline are planning/manifest/brief paths only. Copy both ignored immutable stores byte-for-byte; do not copy another arm's generated plans or runtime checkpoints. Remove the clone's remote. No manual seed or plan repairs. Raw rerun capture checkpoint: **`1d69e52`**.

Selected seed: `docs/implementation-plans/roadmaps/integration-granularity-comparison/plan-seed-drafts/integration-ready-handoffs.md`, SHA-256 **`2b1a13d2ae6d2765ab96ebf3d71330332bdd8ab95104f7f2d4f70a03e525842c`**. Native `create integration-ready-handoffs --from-existing <seed> --iterate -y` uses implementation tool commit `586255721`, explicit PYTHONPATH, Codex `gpt-6.1-sol`, and closed stdin. Mapping and seed are unchanged; this rerun exercises the create adjustment, not the changed mapping or materialization prompts.

Log: `E/business-logic-loop1-ready-handoffs-create.log`. Run id **`2026-10-16T19-03-42+00-00-0000db`**. Original session 29179 exits 0; native `run_end` records outcome `ok`, rc 0 and duration 190114 ms. No process remains active.

| Baseline raw plan | Rerun raw plan |
| --- | --- |
| One non-code step checks predecessors and stops implementation. | Five steps: (1) prerequisite verification, (2) durable completion and final workflow closure, (3) revision-bound readiness, (4) authorized inspection/reevaluation/continuation, (5) integrated API/browser proof. |
| The implementation outcome in the seed has no corresponding implementation route. | Implementation remains authored behind explicit prerequisite dependencies; actual producer integration is bound after predecessors land. |

Insight: **planning-time grounding must not turn an execution prerequisite into deletion of the business implementation outcome**. The rerun supports this bounded fix in one sample; it does not establish a general success rate. The source phrase requiring predecessor presence at create/detail remains unchanged, so seed guidance also needs to avoid introducing that phase confusion in future materializations.

The separate question of who supplies corrected evidence remains unresolved: the new plan recognizes current evidence, checks applicability and reevaluates after correction, but this does not independently demonstrate the upstream production/update contract. Do not claim the entire original handoff gap is closed.

## Completed second business-logic iteration

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

## Paused pickup: handoff-content continuity

**Paused at the owner's request, 2026-10-16.** The [read-only handoff-content trace](../docs/evidence/roadmap-handoff-content-trace.md) is complete. No model run, detail authoring or application implementation occurs during this trace, and no process remains running.

Question: does the next runtime receive the actual work produced at the intended revision, rather than only a ready flag, revision metadata or retained console output?

Findings:

- The new mapping and handoff base plan already require supported production of actual successor inputs and proof of successor consumption. This improves the consumer contract.
- The actual input package remains an explicit source uncertainty under `runtime-contract-proof`, `assumption-successor-input-production` and pending `decision-provisional-runtime-native-handoff`.
- The settled session-store boundary keeps live processes, checkout and credentials inside the worker. Durable output history is not proof of durable handoff-artifact content. Do not infer permission to store secret-bearing state or add recovery requirements.
- The earlier worker base plan is from the initial `f373` mapping; no producer seed/base plan for new `isolated-step-execution` exists in the `41c1` mapping yet. Do not report an ungenerated artifact as an omission.
- No new tool defect or prompt change is established by the read-only trace. Mechanism details remain deliberately unselected.

### Producer seed result and Integration check (2026-10-16)

`isolated-step-execution` was materialized alone in `E/business-logic-loop3-producer-integration` (raw capture `ffe10a6`, seed SHA-256 `6fecb9125c98ba776455da41811552352fbafb35870e52be914639eff613cfc7`, exit 0). The seed preserves production, correction and renewed-evidence operations and the open `assumption-successor-input-production`, but the accepted source assigns no owner for making produced output available to the successor. First gap: accepted source and mapping, not materialization. No base plan was created; one would restate the same question.

Integration already implements that availability (immutable released handoff sets in Aurora, delivered to the successor launch only for a passing predecessor revision). It was absent from the Integration base plan through the bare-stage audits and appeared only after detail authoring (`8dcdb8b`), so bare plans did not identify it there. Integration needs no roadmap feedback item. Evidence and the unfiled plan-tool finding: [handoff-content trace](../docs/evidence/roadmap-handoff-content-trace.md).

### Guidance change and loop-5 result (2026-10-16)

The availability finding became a whole-chain hop-trace clause in `roadmap-plans.md` (commit `0d8d7ca95` on `implement/roadmap-plan-derivation`; full suite 14,637 passed / 67 skipped; two `/code-review` high rounds, stopped on a same-line flip). A fresh mapping on the frozen upstream (`E/business-logic-loop5-hoptrace-integration`, raw capture `c1a0f22`) names an owner for every hop, and the producer and handoff seeds carry them. Residual (accepted known limit): the producer seed does not state worker release of handoff content for the successor. Details and limits: [handoff-content trace](../docs/evidence/roadmap-handoff-content-trace.md) § "Guidance change and mapping reruns".

**Pickup:** Decided 2026-10-16: (1) the residual producer-seed wording is an accepted known limit at seed altitude; no further guidance change. (2) No backlog entry for a mapping-altitude audit: three stage-4 samples on the frozen upstream (loop5-7) all owned every hop (see the trace's variation check). Deliberately not filed; reopen only if a second route shows an unowned hop, citing BACKLOG #435 as the model-judged narrative-review precedent and keeping any audit advisory with no gate or exit-code change. (3) Decided 2026-10-16: the third `/code-review` (high, headless) on `0d8d7ca95` is deferred to the pre-publication pass, before any push or PR; nothing has changed in the code since round 2. No details; no base plan from these seeds.

### Pre-publication `/code-review` (high, 2026-10-16 branch diff, `0d8d7ca95`)

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

## Related records

- [Benchmark inputs and witnessed gaps](../docs/evidence/roadmap-plan-set-benchmark.md)
- [Initial base-plan assessment](../docs/evidence/roadmap-plan-derivation-review.md)
- [Comparison record](../docs/evidence/roadmap-plan-derivation-comparison.md): the resumed section records observations; lower sections retain the initial failed-attempt provenance.
- [Implementation handoff](2026-10-16-roadmap-plan-derivation-implementation.md)
- [#496 closure record](../docs/history/backlog-decisions.md#496--roadmap-mapping-and-seed-to-plan-derivation-in-the-existing-pipeline) (closed 2026-10-19)
