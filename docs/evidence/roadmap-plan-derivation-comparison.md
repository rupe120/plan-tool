# Roadmap plan derivation comparison

## Current resumed comparison

The parent session runs Codex successfully after the nested startup failure. The current comparison pins baseline tool `f1cba286a` (PR #106 merge) and candidate tool `5433b3a53`, with `gpt-6.1-sol` and Integration application baseline `998a78706a22bcf8b64be7ce382608fff1f8189a`. A scratch-only invoker replays the same frozen stages 1–3 through native gates and generates stage four with the real backend; it changes no production runner or accepted benchmark source.

Baseline stage four publishes version `20aabc077c6c338ddbfc84ccddf3bd560a0ee0e3bd5b3d6c62afb68fe8adc8cc` with five plans; candidate publishes `f373ddd13c76d8dd46791f69d9dd75cf69b604da9f054298e9813b2dca8653fb` with ten. All five baseline plans and ten candidate seeds are captured without repairs; eight candidate base plans are captured. Owner direction stops this loop at base plans and focuses further testing on application business logic. Candidate AWS delivery and end-to-end proof remain seeds. The baseline combines session execution, chat, streaming, repository references and revision review in one eight-step live plan. Candidate mapping assigns separate bounded routes. Counts alone do not establish improvement.

The first candidate base plan retains all four local artifact References; the first baseline plan loses them. A stricter control therefore supplies byte-identical raw worker seed input (SHA-256 `bbc4e7f7b8e227cb3dc4193f1611cb05fe30cddd703bbe4643278d16ae12fc6f`) and the same accepted store in fresh independent Integration clones. Both controls complete: baseline checkpoint `06c40c0` loses the four local artifact References, while candidate `4eb7fd9` retains them. Separate same-mapping materialization samples remain observations; their available generated planning documents differ, so do not treat their wording differences as a causal estimate.

The experiment root remains `/private/tmp/roadmap-plan-derivation-comparison-20261016`; raw artifacts are committed inside the isolated clones. The [base-plan assessment](roadmap-plan-derivation-review.md) records clearer responsibility boundaries and unresolved business-logic obligations. The [testing handoff](../../handoffs/roadmap-business-logic-base-plan-loop.md) owns bounded iteration, source-to-plan gap attribution and current pickup. No detail files are authored for the new plans; no full semantic-coverage or shipment claim is established.

## Bounded business-logic follow-up

Owner direction stops at base plans and prioritizes application business logic. Tool commit `586255721` sharpens production/update assignment and preserves conditional implementation when prerequisites are pending. The unchanged-seed handoff rerun uses baseline pre-create checkpoint `1b7e769` and seed SHA-256 `2b1a13d2ae6d2765ab96ebf3d71330332bdd8ab95104f7f2d4f70a03e525842c`. Its raw five-step plan retains completion, readiness, authorized actions and integrated proof behind prerequisite checks; baseline emits only the prerequisite check. Native create completes, rc 0, with run_end `2026-10-16T19-03-42+00-00-0000db`; raw capture is `1d69e52` in `E/business-logic-loop1-integration`.

The [testing handoff](../../handoffs/roadmap-business-logic-base-plan-loop.md#completed-first-business-logic-iteration) records exact commands, validation, reviews and next attribution question. This sample exercises create only: unchanged mapping/seed inputs cannot establish the effect of their updated prompts. Corrected-evidence production remains unresolved; no semantic-coverage or efficiency claim follows from the five-step result.

## Corrected-evidence mapping-to-base-plan trace

The [second business-logic iteration](roadmap-corrected-evidence-iteration.md) locates an implicit production-operation assignment in the earlier mapping. One new stage-four sample, with identical accepted upstream inputs, explicitly assigns corrected-output/evidence production to isolated execution and requests/evaluation to the handoff owner, retaining an unsupported-capability assumption. Its ten rows do not increase the previous candidate count. One selected seed and six-step base plan retain that assignment and the prohibition on using unfinished-step replacement for completed-content correction. All native calls complete; raw capture is `9211d7e`. No new production change, detail authoring, application implementation or live capability proof occurs. The testing handoff records durable-content continuity as the next bounded case.

## Initial nested failure record — 2026-10-16

The record below describes the initial failed attempts only. It does not describe the current backend availability or resumed outputs.

Recorded 2026-10-16. This record supports review of BACKLOG #496. The matched
comparison is **blocked before model generation** by a local Codex startup
failure in both isolated arms. It supplies no observed granularity or coverage
improvement. Keep #496 open for the comparison; do not substitute the repaired
retrospective replay for raw output.

## Inputs and isolation

The [benchmark](roadmap-plan-set-benchmark.md#reproduction-identity) owns the
pinned inputs. The experiment root is
`/private/tmp/roadmap-plan-derivation-comparison-20261016` (abbreviated `E` below).
Each arm has its own full tool clone and Integration clone, made with
`git clone --no-hardlinks --no-local`, with independent object stores, indexes,
branch namespaces and `.plan-tool` state. Both clones have their origin removed.
No worktree, shared state directory, live merge or publication participates.

| Input | Baseline | Candidate |
| --- | --- | --- |
| Tool commit | `6c197474d13cfeb1a7121020c0bbc919c90aa7b9` | `5433b3a532e1f2f79526ed679511a2643f04a95d` |
| Tool source | `E/baseline-tool` | `E/candidate-tool` |
| Integration source | `998a78706a22bcf8b64be7ce382608fff1f8189a` | same |
| Integration directory | `E/baseline-integration` | `E/candidate-integration` |
| Input checkpoint after brief staging | `36f220065f96ca273cad514d8e09ae20901822e8` | `5794e1e2e8241b9004dfedb865ddd4232b47c9a8` |
| Accepted mapping | `c7743c56d7b3da8450d5c4c060dc4a407414fbb77e3967813000a4538f9a4987` | same |
| Backend / requested model | Codex / `gpt-6.1-sol` | same |
| Python host | development checkout `.venv/bin/python` | same |
| Invocation overrides | `--backend codex --model gpt-6.1-sol` | same |
| Retry settings | CLI defaults, three attempts per attempted unit | same |

The intended difference is the tool change across steps 1–4. The candidate also
contains intervening commits; these runs cannot isolate a causal effect even
if generation later succeeds. No resolved model identity or model response is
available: the requested backend fails at initialization.

The source replay checkout is at
`44935a91f0ca6733b9d94ab4a7c39f186de17f93`; its authored-plan checkpoint is
`ea4e25df9397b19c96f6748e029e445d6769c701`. Neither supplies a generated arm.
The complete local roadmap folder, including ignored immutable members, is
copied into each Integration clone. Existing draft seeds and `seed-state.json` are
removed **only in those copies** to request fresh materialization. Top-level
legacy files remain unused. Both tool versions successfully load all four
artifacts using `load_accepted_roadmap_artifacts`; every copied immutable-store
file remains byte-equal to the source after the attempts.

The brief for the fresh route is the accepted version's `brief.md`, copied as
`roadmap-plan-derivation-comparison-brief.md`, not a similarly named concept in
the replay. The same frozen mapping route consumes the same accepted mapping
in both arms. Later Integration `25d6517dd47949040b94904669128a5f0ba9aa06` supplies
declared **retrospective review context**, not baseline code: its retrospective
and seam-study bytes are retained at `E/retro.md` and `E/seam.md`. No extra
owner-decision text from repaired replay seeds is injected into either arm.

## Commands, raw failures and interventions

From each arm's Integration directory, use the development checkout's absolute Python
path and bind `PYTHONPATH` to that arm's tool clone. The executed materialize
entry uses `main()`; the fresh entry uses `raise SystemExit(main())`:

```sh
PYTHONPATH=<E/arm-tool> <development-python> -c 'from plan_tool.cli.app import main; main()' --backend codex --model gpt-6.1-sol roadmap integration-aidlc-mvp --materialize
PYTHONPATH=<E/arm-tool> <development-python> -c 'from plan_tool.cli.app import main; raise SystemExit(main())' --backend codex --model gpt-6.1-sol roadmap integration-plan-derivation-fresh --from-existing roadmap-plan-derivation-comparison-brief.md
```

The materialization wrapper returns shell status 0 because it discards main's
return value; **that status does not establish completion**. Both logs end in
`note: roadmap integration-aidlc-mvp: exhausted`. Each lists all nine rows as
`refresh exhausted its retry budget (invoke failure)` and contains 27 backend
startup failures. Fresh runs return 1 and stop at stage 1 after three attempts.
The following exact excerpts preserve the evidence even after scratch cleanup:

```text
WARNING: proceeding, even though we could not create PATH aliases: Operation not permitted (os error 1)
Reading additional input from stdin...
Error: failed to initialize in-process app-server client: Operation not permitted (os error 1)
plan-tool: codex exited with code 1
```

```text
error: roadmap seeds: connector-registry-seed: refresh exhausted its retry budget (invoke failure)
error: roadmap seeds: bitbucket-deployment-pipelines: refresh exhausted its retry budget (invoke failure)
note: roadmap integration-aidlc-mvp: exhausted
```

```text
error: roadmap integration-plan-derivation-fresh: stage 1 exhausted its retry budget (invoke failure)
  the stages that passed are held; the next plain run resumes at stage 1
  backend exit code 1
note: roadmap integration-plan-derivation-fresh: stage-exhausted
```

The diagnostic is an observed startup failure; its deeper cause is unverified.
No model response, seed, fresh mapping or first published base plan exists
from these attempts. There is no session-directed output repair or review
bypass. Automatic retries are retained in the logs, not excluded as failed
samples. An initial CLI discovery attempt (`python -m plan_tool`) refuses
because the package has no `__main__`; subsequent commands use the CLI app.
No create call follows failed materialization. No application or provider runs.

Fresh mapping comparison remains unperformed: first-run stores never reach
stage four, so equivalent upstream generated artifacts are unavailable. The
same-accepted-mapping handoff comparison has matched source bytes but no seeds
or raw plans to compare. A resumed experiment must establish equivalent
upstream artifacts before attributing fresh stage-four differences to guidance.

## Artifact inventory

All immutable members below reside beneath each arm's copied accepted version
and beneath the original replay store. SHA-256 applies to exact bytes. These
are **inputs**, not new outputs. The accepted-head selector still names the
pinned version. The development plan's report history receives no experiment
reports.

| Accepted member | Bytes | SHA-256 |
| --- | ---: | --- |
| `01-domain.md` | 24789 | `a4592773a1dc958f4f3e5480e6eba9e7209a594a4bd6683a7cacfdfde608736e` |
| `02-constraints.md` | 26166 | `45be44a895380f6148874282447090f68c2e91ca8044e13e5c9f478f91f45df5` |
| `03-components.md` | 17487 | `011954dbfdd1c8ece323ac32e11fedd1618c0d3e1c8e4c4c40299f17f6c26cd6` |
| `04-roadmap.md` | 32145 | `62f566242dee1ee418c509883587737e42887bfe1864dc68dcaa6bfe5a273c19` |
| `brief.md` | 5532 | `0086ebf87fc582aab38a42611bff5389966b9faff687a055fe6f3942d510a852` |
| `candidate-evidence.json` | 930117 | `df9e7916f72d5710fcddfe607fe7ec4d15a17c8b4cb815e71245db0ed9c33b8e` |
| `version.json` | 1106 | `0134be642c6941cdfc2f90d6aa6da1195175353cb041ae2b4e8f553ac1cb6929` |

Raw command logs remain at `E/<name>`; each arm's native reports and runtime
state remain inside its own Integration clone. Keep these directories for review.
The committed excerpts above support the blocked finding independently of
those temporary locations; they do not preserve nonexistent generated output.

| Attempt log | Bytes | SHA-256 |
| --- | ---: | --- |
| `baseline-fresh.log` | 1607 | `3c41ced052ba05df469a75dd45ce6f0a9ce9f0a9b5fc5afe2810b027e3ad491c` |
| `baseline-materialize.log` | 9971 | `0a2548e2c1d655b85b61fe09002641584dc5981720563c518102a67c6a7a45bc` |
| `candidate-fresh.log` | 1607 | `3c41ced052ba05df469a75dd45ce6f0a9ce9f0a9b5fc5afe2810b027e3ad491c` |
| `candidate-materialize.log` | 9972 | `661015f632c2c5cced1be4116acd69aee55110087b2b1534c4ce10d1be804253` |

## Obligation traces and granularity assessment

The table distinguishes supplied review context from observations of generated
artifacts. `Unavailable` means generation never supplies bytes; it is not an
omission finding. The benchmark's “Witnessed failures to retain” names these
cases. The retrospective describes a coordinated fix “across
isolated-engine-worker, step-completion-and-handoff, and
repository-browse-and-reference (one shared boundary contract written down
first)”; the seam study states that completion steps “consume the
readiness-evidence table and report-revision definition owed by
isolated-engine-worker.” These retrospective observations motivate tracing
producers and consumers; they do not prove a new mapping fixes the boundary.

| Witnessed obligation / source | Producer → consumers and required order to inspect | Frozen mapping context | Baseline and candidate seed / raw plan / fresh mapping | Eventual acceptance evidence to retain |
| --- | --- | --- | --- | --- |
| Readiness-correction intake; benchmark, retrospective, seam study | Worker readiness evidence → completion authority; corrected evidence must reach readiness before transition | Completion intent requires checks against “the completed revision” and exact blockers | Unavailable in both arms; correction-intake route unassessed | Observe blocked-to-corrected intake without premature advancement |
| Session-lifetime cleanup; benchmark replay cases | Worker lifetime owner → process, credential and checkout consumers; cleanup follows terminal lifecycle | Worker intent keeps “repository credentials, live processes, and checkout access behind the worker boundary” | Unavailable in both arms; cleanup route unassessed | Observe cleanup across terminal and replacement paths |
| Safe output release; benchmark replay cases | Worker release boundary → persisted evidence, output and repository consumers; release precedes exposure | Worker isolation obligation supplies boundary context, not proof of safe release | Unavailable in both arms; release responsibility unassessed | Observe withholding and safe release at the actual boundary |
| Handoff content continuity; retrospective | Worker output → completion and successor runtime; content precedes successor consumption | Completion checks required outputs; retrospective specifies material “keyed by (emitting session, revision)” | Unavailable in both arms; shared implementation route unassessed | Observe successor access to the correct predecessor content |
| Catalog revision identity; benchmark replay cases | Catalog revision authority → chat review and completion; identity precedes decisions | Chat intent says “component-workflow-catalog supplies its revision identity” | Unavailable in both arms; identity producer implementation unassessed | Observe revision-bound review and handoff decisions |
| Disconnected output indexing; benchmark replay cases | Durable worker/output producer → reconnecting chat observer; indexing must survive absent observers | Chat intent requires “ordered output event identifiers” and replay | Unavailable in both arms; disconnected producer route unassessed | Observe disconnected production and cursor replay without execution restart |
| Submission reference binding; benchmark replay cases, seam study | Repository reference authority → chat submission → worker action; bind before execution | Repository intent preserves “selected path and revision without silently substituting different content” | Unavailable in both arms; submission binding route unassessed | Observe revision-bound submission and unreadable/stale refusal |
| Local References retention; benchmark and replay README | Accepted artifacts and selected seed → create → raw plan; source references precede authoring | Same accepted mapping in both materialization attempts | No seeds or create outputs; no measured retention difference | Inspect exact local References in first published plans before repairs |
| Observed deployment proof; benchmark acceptance-route finding | Infrastructure/environment, SPA and pipeline delivery → deployed journey verification; deployment precedes pass | Infrastructure intent requires “demonstrating initial dev deployment”; SPA requires “the deployed SPA to exercise” the journey | Unavailable in both arms; acceptance preservation unassessed | Observed dev deployment, independent environment addition and deployed SPA journey; local document checks cannot replace these |

These producer/consumer descriptions identify what a reviewer must inspect;
implementation routes, dependency satisfaction and acceptance retention remain
unknown. No independent second reviewer participates, so reviewer agreement
is unmeasured. First visible gap attribution is **unavailable generation**, not
missing supplied context, mapping omission, materialization loss or create loss.

The frozen mapping contains broad catalog, worker, chat, repository and
cross-cutting delivery responsibilities. For example its worker sizing says
“One initial session plus one owner-requested sequential replacement remains
the smallest isolation and continuation proof”; its chat row combines question
input, durable observation and revision review. These are candidates for
review of cohesive implementation boundaries, not evidence that a particular
split is necessary. No fresh mapping, seed boundary or plan boundary exists to
show a narrower route. Therefore the required granularity improvement over
the overly high-level Integration baseline is **not demonstrated**, including whether
these broad routes remain too broad. More rows or steps alone would not answer
that question.

## Disposition and resumption

Retain [BACKLOG #496](../../BACKLOG.md) with the isolated comparison pending.
Steps 1–4 deliver mapping guidance, per-row context, create References retention
and workflow/regression coverage in the candidate; this failed experiment does
not demonstrate the full Outcome. Re-run in an environment where the pinned
Codex backend initializes, preserving both failure logs. Record effective model,
settings and any changed input identities; use fresh independent clones and
existing first-run / accepted-head routes. Preserve raw mappings, seeds and
first published plans before repairs, then complete the responsibility traces
and granularity judgment. Do not declare shipment from this record alone.

This is a blocked sample, with no semantic certification, success-rate estimate,
causal improvement claim or efficiency measurement. It does not authorize
#462, #493, #494, new comparison infrastructure, Integration implementation or live
provider execution. The [roadmap workflow](../how-to/roadmap.md),
[roadmap contract](../../ROADMAP_FORMAT.md) and
[tracking lifecycle](../TRACKING.md#the-life-of-an-item) continue to own those
boundaries.
