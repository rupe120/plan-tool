> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Align first-use and situation examples with assistant-authored seeds, monitoring and separate completion requests

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Align the learning examples in `README.md`, the three scoped how-to guides and `RUNBOOK.md` with the assistant-led demos from steps 1 and 2. Lead with requests to draft grounded seeds, prepare reviewed plans and inspect results. Keep planning, execution and local export as separate requests, and explain safe monitoring and resumption through existing procedural references. Readers can follow a consistent interaction while retaining direct CLI guidance.

## Table of Contents

- [Summary](#summary) — Deliverable and observable result.
- [Table of Contents](#table-of-contents) — Section navigation.
- [Why](#why) — Where the current learning routes disagree.
- [Input](#input) — Dependency outcomes and procedural contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — The bounded documentation footprint.
- [Implementation](#implementation) — Requests, monitoring and completion boundaries.
- [Tests](#tests) — Reviewer-run documentation checks.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Existing owners of the relevant rules.
- [Applicable guardrails](#applicable-guardrails) — Constraints on this conversion.
- [Deferred](#deferred) — Related surfaces outside this step.

## Why

`README.md:Your first plan` already introduces assistant-led planning, but the situation and starting-point guides lead readers through commands or assume they supply the seed themselves. `docs/how-to/use-cases.md:Execute a plan locally, one step at a time` also presents a post-run completeness audit and treats a dry-run reconciliation as drift evidence, contrary to the current execution contract. The entry pages need consistent requests and review points so readers understand who prepares inputs, how to monitor a command and when a separate request authorizes the next outcome.

## Input

- **Step 1:** Use its assistant-led dark-mode walkthrough and reading samples as the concrete planning example. Read the resulting `docs/demos/planning-demo.md` and `docs/demos/dark-mode-example.md` rather than assuming their final wording.
- **Step 2:** Use its assistant-led TTRPG walkthrough in `docs/demos/roadmap-demo.md` for the larger-concept route. Reference its outcome without copying its roadmap procedures.
- **Procedural authority:** Reuse `integrations/shared/DIRECTIVES.md:Monitor command liveness and recover safely`, `The two audit gates`, `Authoring hygiene` and `After run finishes a plan`. These contracts govern examples; this step does not revise them.
- **Evidence limits:** Use `handoffs/2026-10-21-demo-refresh.md:Verification and presentation boundary` to distinguish preparation from demonstrated results. Documentation checks do not prove successful live model runs or audit convergence.

## Files (creates vs edits)

**New files:**

- None.

**Existing files (edits only):**

- `README.md` — Make seed preparation explicit in the first request and clarify monitoring, resumption and separate follow-up requests.
- `docs/how-to/use-cases.md` — Lead relevant situations with assistant requests and correct conflicting learning examples.
- `docs/how-to/choose-a-starting-point.md` — Pair input choices with requests that let the assistant prepare grounded inputs.
- `docs/how-to/common-workflows.md` — Add the assistant entry route while retaining the operator procedures and correcting directly conflicting examples.
- `RUNBOOK.md` — Connect operational entry, completion and recovery sections to the same request and monitoring model.

## Implementation

- **User review checkpoints.** Carry the same explicit seed, plan and detail review checkpoints through the README, situation examples, starting-point guide, common workflows and RUNBOOK entry route; avoid a single request that silently consumes all three artifacts. The assistant links each artifact, summarizes changes and asks for corrections or continuation. Wait for the user unless explicit existing delegation covers that transition; do not infer approval from elapsed time. This changes the demo interaction, not tool enforcement.

- **Foundational logic: assistant request → inspectable artifact → human decision.** Apply this pattern across the five scoped files. Reuse existing procedural owners unchanged; reject a second policy embedded in the examples.

- **Make the first request include seed authoring.** In `README.md:Your first plan`, ask the assistant to inspect the consuming repository, draft a grounded seed with a scope fence and references, then drive the skill through both audit gates. The request must stop before implementation and bring material scope or design questions back to the reader.

- **Keep subsequent outcomes explicit.** Provide separate requests for authorized execution, local story export and status inspection. Execution must include code reconciliation and review; local export must remain distinct from tracker publication. A status request must not silently authorize implementation.

- **Make resumption depend on observed state.** Replace ambiguous “continue from its next step” wording with a request to inspect the plan, reports and any active invocation first. Resume only after the original command has definitely exited, using its recorded outcome to select the next incomplete stage within the requested scope.

- **Convert input selection without removing operator routes.** In `docs/how-to/choose-a-starting-point.md`, pair existing situations with short assistant requests. A short idea can ask the assistant to author the seed; an existing draft can ask it to assess and ground the source; an old plan can request carryover assessment; a project-sized concept can request roadmap preparation. Retain commands as supporting operator examples and preserve their documented intake distinctions.

- **Align the situation catalog with those requests.** In `docs/how-to/use-cases.md:Use-case catalog` and `Pick your entry point`, make relevant planning, execution, handoff, stale-plan and next-iteration examples follow the same interaction. Preserve the suitability guidance and specialized command coverage rather than converting every reference example.

- **Correct contradictions in the converted routes.** In `docs/how-to/use-cases.md:Turn a rough idea into a buildable plan`, include the bare audit before detail and the detail-grounded audit afterward. In `Drive a plan to "actually correct," not just "generated"`, remove routine reliance on `detail --iterate`. In `Execute a plan locally, one step at a time`, use the existing post-run reconciliation and review contract: a dry run supplies prompts, and a post-run completeness audit is not part of that tail.

- **Keep workflow depth in its existing home.** Add a concise assistant entry to `docs/how-to/common-workflows.md`, linking to the step 1 and step 2 demos. Check its `create`, `detail`, audit and `run` examples for contradictions introduced by the new entry route. Explain pre-execution plan reconciliation separately from post-execution code reconciliation; preserve the remaining operator reference material.

- **Teach monitoring without promising new observability.** In `RUNBOOK.md:Progress output during long claude calls`, `Workflow: investigating a slow run` and `Workflow: recover from an interrupted create/detail run`, connect reader requests to the canonical liveness procedure. Quiet output, a checkpoint or a backend completion message must not imply command completion or justify a second invocation. Link to `integrations/shared/DIRECTIVES.md:Monitor command liveness and recover safely` for the detailed procedure and intervention rule.

- **Keep completion requests separate from preparation.** In `RUNBOOK.md:Workflow: start a new plan` and `Workflow: drive a plan to completion`, distinguish preparing a reviewed bundle from executing it. Link to supporting operator procedures without implying that reading a demo, requesting a plan or inspecting progress authorizes execution or publication.

- **Preserve navigation and example honesty.** Prefer existing headings. Before renaming one, search for inbound fragment links and update affected links within scope. Fix local links touched by this conversion and label authored samples or preparation evidence accurately.

## Tests

### Verification (non-code step)

The test-authoring gate does not apply to this `non-code` step; it keys on `feature` and `refactor`. No matching documentation test files cover these five pages. Use these reviewer-run checks instead of adding a prose checker or changing `tests/test_detail.py` or `tests/test_detail_artifacts.py`.

1. `verify_first_request_includes_assistant_authored_seed` — Confirm the first-use request asks for repository grounding, seed preparation, both audit gates and a stop before implementation.
2. `verify_followup_requests_keep_outcomes_separate` — Read the planning, status, execution and local-export requests across all five files; confirm each names its intended result and review boundary.
3. `verify_resume_waits_for_original_command_exit` — Confirm recovery examples require checking the original invocation and forbid overlapping work while its exit remains unconfirmed.
4. `verify_progress_is_not_completion_evidence` — Compare monitoring claims with `integrations/shared/DIRECTIVES.md:Monitor command liveness and recover safely`; confirm no quiet-output timeout or backend-only completion shortcut appears.
5. `verify_learning_routes_preserve_both_audit_gates` — Trace converted planning examples through bare audit, detail authoring and detail-grounded audit without routine `detail --iterate`.
6. `verify_execution_tail_uses_plan_as_authority` — Confirm converted execution examples use code reconciliation and review, exclude post-run completeness auditing and do not treat `--dry-run` as drift evidence.
7. `verify_links_and_heading_targets_exist` — Check changed relative links and fragments, including links to dependency-step outputs; search inbound links before changing headings.
8. `verify_documentation_diff_stays_scoped` — Review the diff for only the five declared files, retained CLI access, accurate evidence labels and absence of new procedural policy.

## Acceptance criteria

- The step’s deliverables show explicit user review of seeds, plans and details at the correct stage boundaries, including artifact links, change summaries and correction/continuation requests; continuation follows a user response or explicit prior delegation.
- `README.md:Your first plan` explicitly asks the assistant to prepare a grounded seed and stops the planning request before implementation.
- The five scoped files use consistent requests for planning, status inspection, authorized execution and local export.
- The starting-point and situation guides let readers begin with an idea without requiring a prewritten seed.
- Converted planning examples preserve both audit gates and do not recommend routine `detail --iterate`.
- Monitoring and recovery examples distinguish backend completion from command exit and require inspecting the original invocation before resuming.
- Converted execution examples describe the existing reconciliation and review tail without post-run completeness auditing or dry-run drift claims.
- Direct CLI procedures remain accessible, and changed links and heading fragments point to existing targets.
- Verification checks pass without production-code changes, new automated prose checks or edits outside the declared files.

## References

- [README.md](../../../../../README.md) — Read “Your first plan” and “Decision flow” for the current entry routes.
- [docs/demos/planning-demo.md](../../../../demos/planning-demo.md) — Use step 1’s assistant-led planning example.
- [docs/demos/roadmap-demo.md](../../../../demos/roadmap-demo.md) — Use step 2’s larger-concept example.
- [integrations/shared/DIRECTIVES.md](../../../../../integrations/shared/DIRECTIVES.md) — Read the seed, audit, monitoring and execution contracts.
- [SEED_FORMAT.md](../../../../../SEED_FORMAT.md) — Check seed scope and reference requirements.
- [JIRA_FORMAT.md](../../../../../JIRA_FORMAT.md) — Check local export and paired developer-handoff behavior.
- [handoffs/2026-10-21-demo-refresh.md](../../../../../handoffs/2026-10-21-demo-refresh.md) — Check the preparation and publication boundary.
- [docs/reference/documentation-style.md](../../../../reference/documentation-style.md) — Follow task-first structure and preserve technical facts.

## Applicable guardrails

- **The plan’s “Scope guardrails,” existing behavior:** Limit changes to explanations and examples in the declared files. Monitoring passages must describe supported behavior and link to its owner.
- **The plan’s “Scope guardrails,” procedural ownership:** Keep entry pages concise and point to canonical procedures instead of copying a competing workflow policy.
- **The plan’s “Out of scope,” bounded conversion:** Retain specialized operator references unless they directly contradict the interaction this step teaches.
- **The plan’s “Scope guardrails,” publication boundary:** Example requests must preserve the distinction between local preparation and separately authorized external actions.
- **The plan’s “Scope guardrails,” private recovery material:** Use public procedural links and suitable preparation summaries; do not expose private recovery content.

## Deferred

- `docs/demos/planning-demo.md` and `docs/demos/dark-mode-example.md` — Step 1 owns their content; this step links to the resulting examples.
- `docs/demos/roadmap-demo.md` — Step 2 owns its scenario and roadmap review boundaries.
- `integrations/shared/DIRECTIVES.md` and assistant integration routers — Reuse their existing authority unchanged; changing shared behavior requires separate intentional work.
- Unrelated command-reference corrections and historical presentation material — They do not serve this step’s focused learning route.
