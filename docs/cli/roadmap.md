# `plan-tool roadmap`

## Usage

```
plan-tool roadmap [-h] [-y] [--from-existing PATH] [--apply] [--refresh-seeds] [--accept-seed PLAN_ID] [--materialize [PLAN_ID]] [--view {summary,walk,ledger,index,seeds,html}] [--output PATH] [--compare] [--comparison-base VERSION_ID] [--comparison-target VERSION_ID] [--comparison-output {cards,patch,json}] [--revise-feedback] [--propose-candidate] [--submit-feedback ITEM_ID] [--retarget-feedback ITEM_ID] [--edit-feedback ITEM_ID] [--defer-feedback ITEM_ID] [--close-feedback ITEM_ID] [--reopen-ledger-feedback ITEM_ID] [--feedback-target ARTIFACT:KIND[:ROW_ID]] [--feedback-request TEXT] [--review-candidate INITIAL_CANDIDATE_VERSION_ID] [--answer-question QUESTION_ID] [--answer TEXT] [--reject-candidate CANDIDATE_VERSION_ID] [--discard-candidate CANDIDATE_VERSION_ID] [--decide-candidate CANDIDATE_VERSION_ID] [--candidate-decision CHOICE] [--candidate-correction TEXT] [--confirm-stack-digest DIGEST] [--promote-review-seal REVIEW_SEAL_ID] [--settle-decision SELECTOR] [--settlement-evidence SELECTOR] [--confirm-decision-settlement] [--respond-decision-settlement RECEIPT_FINAL] [--decision-settlement-yes] [--decision-settlement-no] [--mode {current,review}] [--id ROW_ID] slug
```

```
plan-tool roadmap [-h] [-y] --apply slug
```

## Arguments

| Argument | Description |
| --- | --- |
| `slug` | roadmap slug — names the roadmaps/<slug>/ directory the artifacts land in. Required: this verb has no interactive slug confirmation to fall back on. |

## Options

| Option | Default | Description |
| --- | --- | --- |
| `-y`, `--yes` | off | skip the interactive promote confirmation (relevant only with --apply): the deliberate second opt-in that may copy seeds into docs/implementation-plans/plan-seeds/ without a TTY. Useful for scripted/unattended runs. |
| `--from-existing` `PATH` | — | path to the concept brief a first stage run grounds a new roadmap in. A run that failed part-way holds its passed stages and the next run resumes from them, but only for the same brief content. Refused beside an accepted head. Not used with --apply. |
| `--apply` | off | apply-only mode: read the accepted version's roadmap and promote draft seeds into docs/implementation-plans/plan-seeds/ after confirm (or -y). Does not run stages or invoke the backend. |
| `--refresh-seeds` | off | explicitly regenerate roadmap-derived seeds against the current codebase, restoring a consumed or archived seed at its original path when needed. Writes a before/after difference report; does not rewrite any roadmap artifact. |
| `--accept-seed` `PLAN_ID` | — | accept one validated directly edited digest-mismatched draft as current without regenerating it or running roadmap stages. |
| `--materialize` `PLAN_ID` | — | explicitly regenerate every recoverable draft seed, or only PLAN_ID when supplied. Skips current drafts and refuses duplicate plan rows; writes the seed refresh difference report. |
| `--view` `{summary|walk|ledger|index|seeds|html}` | — | inspection mode: render a compact review summary, traceability walk, decision ledger, reverse citation index, or draft-seed state report over the accepted version and print it; or a self-contained, print-formatted HTML page carrying every parsed row of all four artifacts with its resolvable references linked and dangling or ambiguous ones marked, written to <roadmap-dir>/review.html by default. Runs no stage and invokes no backend; does not require --from-existing. --mode and --id refine views; --output refines html. |
| `--output` `PATH` | — | valid only with --view html: write the rendered page to PATH and print the path, or to <roadmap-dir>/review.html when omitted (the html view writes a file by default — it is meant to be opened and printed, not piped). PATH of '-' prints to stdout instead of writing, matching every other view's default. Creates missing parent directories and overwrites an existing file; touches no other roadmap state — no artifact, lifecycle sidecar, or run log. |
| `--compare` | — | compare the accepted-head roadmap version (or --comparison-base) with the active candidate (or --comparison-target). When no candidate is active, requires --comparison-target; a roadmap with no accepted head is refused. Accepts no companion roadmap options and never writes roadmap state. |
| `--comparison-base` `VERSION_ID` | — | stored immutable version to use as the comparison base instead of the accepted head; valid only with --compare. |
| `--comparison-target` `VERSION_ID` | — | stored immutable version to use as the comparison target instead of the active candidate; valid only with --compare. |
| `--comparison-output` `{cards|patch|json}` | `cards` | comparison presentation: cards (default), complete Git patch, or deterministic JSON; valid only with --compare. |
| `--revise-feedback` | — | build one inert candidate from the current eligible ledger batch. Accepts no feedback selector or companion roadmap option. |
| `--propose-candidate` | — | build or re-enter the one admitted inert candidate from the current eligible ledger batch. Prints the candidate's narrative evidence. Accepts no selector or companion roadmap option. |
| `--submit-feedback` `ITEM_ID` | — | submit one reviewer ledger item with --feedback-target and --feedback-request. |
| `--retarget-feedback` `ITEM_ID` | — | retarget one ledger item with --feedback-target. |
| `--edit-feedback` `ITEM_ID` | — | edit one ledger item with --feedback-target and/or --feedback-request. |
| `--defer-feedback` `ITEM_ID` | — | defer one reviewer ledger item. |
| `--close-feedback` `ITEM_ID` | — | close one reviewer ledger item. |
| `--reopen-ledger-feedback` `ITEM_ID` | — | reopen one retained reviewer ledger item. |
| `--feedback-target` `ARTIFACT:KIND[:ROW_ID]` | — | target for one ledger submit, retarget, or edit action. |
| `--feedback-request` `TEXT` | — | request text for one ledger submit or edit action. |
| `--review-candidate` `INITIAL_CANDIDATE_VERSION_ID` | — | request or return the stored review question for one initial candidate and print its narrative evidence. Accepts no companion roadmap option. |
| `--answer-question` `QUESTION_ID` | — | record exactly one stored-question answer with --answer and materialize its sealed replacement, printing the replacement's narrative evidence. |
| `--answer` `TEXT` | — | exact opaque reviewer answer for --answer-question. Required exactly once and not valid on its own. |
| `--reject-candidate` `CANDIDATE_VERSION_ID` | — | reject and release exactly the active candidate. |
| `--discard-candidate` `CANDIDATE_VERSION_ID` | — | discard and release exactly the active candidate. |
| `--decide-candidate` `CANDIDATE_VERSION_ID` | — | disclose and decide one active structural candidate with --candidate-decision. Every decision prints the candidate's narrative evidence before it runs. Approve prints the candidate's whole stack and its digest and writes nothing until --confirm-stack-digest supplies that digest. |
| `--candidate-decision` `{approve|edit|reject}` | — | one structural candidate choice: approve, edit, or reject; valid only with --decide-candidate. Approve is confirmed with --confirm-stack-digest. |
| `--candidate-correction` `TEXT` | — | one correction for --decide-candidate --candidate-decision edit. |
| `--confirm-stack-digest` `DIGEST` | — | the stack digest printed by --decide-candidate --candidate-decision approve, exactly as printed. Valid only with that pair and needed exactly once; approve refuses with no write when it differs from the digest recomputed at confirm time. -y is not confirmation. |
| `--promote-review-seal` `REVIEW_SEAL_ID` | — | promote exactly one sealed candidate through the accepted-head writer guard; a structural approval already at the accepted head reports already promoted. Accepts no companion roadmap option or backend. |
| `--settle-decision` `SELECTOR` | — | settle one selected pending Roadmap-derived decision to settled, only with exactly one --settlement-evidence and one --confirm-decision-settlement. Accepts no companion roadmap options and invokes no backend. |
| `--settlement-evidence` `SELECTOR` | — | named, live feedback row citing --settle-decision's selected decision. Required exactly once alongside --settle-decision. |
| `--confirm-decision-settlement` | — | explicitly confirm --settle-decision for one selected decision. Required exactly once; -y is not confirmation. |
| `--respond-decision-settlement` `RECEIPT_FINAL` | — | apply one exact enrolled settlement confirmation receipt. |
| `--decision-settlement-yes` | — | affirm --respond-decision-settlement. |
| `--decision-settlement-no` | — | decline --respond-decision-settlement. |
| `--mode` `{current|review}` | — | valid only with --view: render the design-state roadmap ('current', the default) or the review-channel roadmap ('review', which also surfaces feedback rows and removals). Rejected without --view. |
| `--id` `ROW_ID` | — | valid only with --view index: the row id to query, printing just that id's citers. Omit for the full citation map. Rejected with any other --view value. |
