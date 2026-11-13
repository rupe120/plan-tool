# Explicit overengineering checkpoints: behavioral test

## What this result supports

The checkpoint instructions make the question explicit in this small, loaded-context
test. They do not demonstrate better design decisions: both conditions choose the
same bounded remedies and preserve the necessary ownership protection. The installed
workflow still needs the updated instructions before it can use these checkpoints.

This is a dated measurement (2026-11-12), not a new gate or a reliability claim.
There is one fresh session per condition, with four obvious synthetic situations
in each session. The four answers within a session are not independent trials.
No production task or unattended pipeline runs in this test.

## Method and evidence

| Item | Value |
| --- | --- |
| Baseline | `5c38aa9da36f30202f5e5543f29da6bf18895c3d` shared directives |
| Checkpoints | `ceefc80c64204ebe54a6dde20aaa8a2157105c9a` shared directives |
| CLI / model | Codex 0.167.2 / `gpt-6.1-sol`, reported reasoning effort `none` |
| Execution | Sequential ephemeral sessions, read-only sandbox, user config disabled |
| Input | Identical task below; `PROCESS.md` contains the full shared directives at the respective revision |
| Context | Both fixture directories are beneath the same checkout and inherit its project instructions; this isolates the shared-directives change, not all process policy |
| Loading | Each session explicitly receives the instruction to follow `PROCESS.md`; logs show both read it |
| Assessment | Session review of the responses below; no automated semantic scorer |

The test asks whether each response explicitly questions overengineering,
compares a smaller alternative against the current requirement, and proposes a
bounded action. Situation B checks that simplification preserves necessary safety.
These are response observations, not proof that a later implementation follows them.

The invocation for each condition is:

```sh
codex exec --ephemeral --ignore-user-config --skip-git-repo-check \
  -s read-only -C <fixture-directory> -o <response-file> - < <task-file>
```

The initial sandbox attempt cannot initialize the app-server client. The external
runs proceed after the owner authorizes sending the shared directives and synthetic
scenarios to OpenAI. Raw local logs and fixture copies live in ignored
`.tmp/overengineering-checkpoints/`; this record retains the inputs and outputs
needed to assess the conclusion without those scratch files.

## Results

| Situation | Baseline | With checkpoints |
| --- | --- | --- |
| A: bare plan adds providers, scheduling, and cache for a file-existence check | Proposes removing the unsupported architecture | Explicitly asks the question and proposes the same simplification |
| B: deletion must enforce document ownership | Preserves authentication and transactional ownership protection | Explicitly answers no and explains why the smaller alternative violates the requirement |
| C: absent-versus-zero timeout bug gets a plugin-engine remedy | Rejects the engine and proposes an absence check with focused coverage | Explicitly asks the question and proposes the same bounded correction |
| D: final diff adds an unused event bus and hooks to a count command | Proposes removing unused machinery | Explicitly asks the question and proposes the same removal |

The explicit question appears in 0 of 4 baseline answers and 4 of 4 checkpoint
answers (C uses “this correction”). Both conditions make the expected substantive
choice in all four situations. The checkpoint response also promises to record each
decision in the existing handoff or review ledger; no such write is exercised.

## Delivery check and limits

On 2026-11-12, a local read checks the new section heading in three instruction
sources: this clone contains it; the installed Codex skill directives and the
Claude directive symlink target do not. The local machine paths are environment
observations, not portable configuration requirements.

A source search finds `DIRECTIVES.md` references in `plan_tool/cli/skill_cmd.py`,
the installer, but none in the authoring/execution orchestrators. The create,
detail, and plan-audit templates do not contain the new explicit question.
They can still have proportionality guidance and a backend can receive project
instructions through other routes. The observation establishes that these edits
do not automatically inject the new checkpoint into every subprocess prompt.

Therefore the change is sufficient to elicit an explicit question in this loaded
sample, but insufficient to establish delivery or compliance throughout the real
process. Update the active instruction sources through the normal installation
route, then observe a real session at stage transitions. This test supplies no
reason by itself to add an automated semantic gate or expand every prompt.

## Exact task

```text
You are driving a software task. Follow the process instructions in PROCESS.md. This is a bounded tabletop test: do not execute plan-tool, edit files, or call external services. Give the actual user-facing response and next action you would take for EACH independent situation below. Do not discuss the experiment.

A. You have finished the bare plan and are about to author detail. Outcome: a local CLI command should print whether one named JSON configuration file exists. Proposed steps: build a provider interface for future file formats, a provider registry, an async scanning scheduler, a persistent result cache, and the command renderer. Current requirements name only a local existence check; there are no performance measurements or future-format requirements. What do you do next?

B. All detail files are authored and the audit is clean. Outcome: prevent deleting another user's document in a multi-user service. Details implement authentication, a database ownership predicate in the deletion transaction, and a focused test proving cross-user deletion is refused. A simpler proposal deletes by document ID without checking ownership. What do you do next before implementation?

C. During code review, a real bug shows an optional timeout value of zero falls back to the default because the code uses `value or default`. The required behavior distinguishes absent from zero. The review suggests a configurable precedence engine with plugin resolvers and a new policy schema. Existing callers need only the optional integer and the default. What do you do next before applying the correction?

D. Implementation is complete and tests pass. Outcome: a command displays a count from an existing database query. The diff also adds a generic dashboard event bus and three unused extension hooks; none is required by the settled acceptance criteria. What do you do next before requesting pull-request review?
```

## Baseline response

**A.** “The intent is to report whether one named local JSON file exists. Four proposed steps—provider interface, registry, scheduler, and cache—have no requirement supporting them. I propose removing those four and keeping a direct existence check with command output.”

**Next action:** Surface that scope reduction before authoring detail. Once settled, revise the bare plan, sweep references to the removed concepts, commit, and repeat the bare audit before detail.

**B.** “The ownership check is necessary to prevent cross-user deletion. Deleting by document ID alone violates that requirement. Authentication, the transactional ownership predicate, and the focused refusal test are proportional to the outcome.”

**Next action:** Verify that the authenticated identity reaches the deletion predicate and that the test exercises another user’s document. Retain those safeguards and proceed through the merged-plan checkpoint into implementation.

**C.** “The bug is valid, but the proposed precedence engine, plugin resolvers, and policy schema outgrow it. This triggers `remedy-proportionality`. I propose an explicit absent-value check so zero remains zero.”

**Next action:** Before editing, enumerate affected sites through identifier and vocabulary searches. Verify their contracts, then apply the bounded correction and focused coverage for absent, zero, and nonzero values; run affected tests and re-review.

**D.** “The count display satisfies the intended outcome. The generic event bus and three unused hooks add unsupported scope. I propose removing them before requesting review.”

**Next action:** Trace their references and remove the unused infrastructure and dependent scaffolding. Verify that the command still displays the existing query’s count, run affected tests, and complete plan-canonical reconciliation and code-review convergence on the reduced diff before requesting pull-request review.

## Checkpoint response

**A.** “Are we overengineering this? Yes. The outcome is one local file-existence check. Future-format providers, a registry, async scheduling, and persistent caching have no current requirement.”

Next action: simplify the bare plan to a direct existence check and CLI output, sweep references to the removed concepts, then commit and re-audit the revised bare plan before authoring detail.

**B.** “Are we overengineering this? No. Deleting by document ID alone violates the ownership boundary. Authentication identifies the caller; the ownership predicate in the deletion transaction prevents cross-user deletion; the focused test proves refusal.”

Next action: retain those mechanisms, record why the simpler proposal fails the acceptance property, and proceed through the merged-plan prerequisite before implementation.

**C.** “Are we overengineering this correction? Yes. The bug requires distinguishing absence from zero. A precedence engine, plugin resolvers, and policy schema add capabilities the callers do not need.”

Next action: before editing, enumerate affected sites using identifier and vocabulary searches. Use an explicit absence check, such as `default if value is None else value`, and add focused coverage for absent, zero, and nonzero values. Validate and review the bounded correction.

**D.** “Are we overengineering this? Yes. The command needs to display the existing query’s count. The event bus and unused hooks do not support any settled acceptance property.”

Next action: remove that machinery and its references, verify the count behavior with affected tests, and complete the required reconciliation and review convergence before requesting pull-request review.

For each situation, I would record the decision in the existing handoff or review ledger.
