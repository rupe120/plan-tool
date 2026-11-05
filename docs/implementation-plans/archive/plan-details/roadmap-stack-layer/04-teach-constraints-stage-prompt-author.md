> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Teach the constraints stage prompt to author one stack row per concern, with `open` for undecided and no invented vendor

<!-- plan-tool:detail-format-version: 1 -->

## Summary

- Edits `plan_tool/prompts/roadmap-constraints.md` so a first-run constraints response carries a `stack` collection: one row per required concern, each either a chosen value or an explicit `open`.
- The key rule is the split between hosting and stack. The hosting block stays vendor-neutral and still bans an invented vendor, product, or pending decision. A stack row may record `open`, and the prompt tells the model to use it when the brief leaves the concern undecided. It must never name a vendor the brief does not name.
- The prompt's rule list, collection count, and embedded example all change together, and the tests that pin those phrases are updated in the same step.
- `tests/test_roadmap.py` gains a Integration-brief replay under the invoker seam: canned output with the deployment platform as `open` clears the gates, renders, and re-parses. Tests also pin that the prompt carries the open-versus-invented-vendor instruction.
- On green, the prompt can no longer leave a stack-less first run unexplained. What a real model does with the Integration brief is not tested here.

## Table of Contents

- [Summary](#summary) — what the step does and the result on green
- [Why](#why) — the gap in the prompt and the Integration case
- [Input](#input) — what steps 1 and 2 hand this step, and what the replay can and cannot prove
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files touched
- [Implementation](#implementation) — prompt edits, the sibling sites that move with them, and the constraints
- [Tests](#tests) — the cases that pin the behavior
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — docs worth reading for this step
- [Applicable guardrails](#applicable-guardrails) — the plan fences that bind this step
- [Deferred](#deferred) — work that belongs elsewhere

## Why

- The prompt forbids inventing "a vendor, product detail, a deployment unit, or a pending decision" in the hosting block. A brief that says "not decided" therefore has nowhere to put that fact in the output.
- Observed in the Integration brief (see the plan's "## Problem statement"): the brief fixes no cloud service and names only a relational store. The accepted roadmap showed no trace that the vendor was open and introduced PostgreSQL, which the brief never named.
- Steps 1 and 2 give the artifact a `stack` collection and a gate that binds once the collection is present. Without prompt text, the model does not know the collection exists, and a first run that omits it is accepted and shown as "stack not recorded" instead of authoring the rows.
- The already-implemented signal flags `plan_tool/prompts/roadmap-constraints.md` on `# Constraints`. That is the example's body heading. `rg -n -i 'stack' plan_tool/prompts/roadmap-constraints.md` returns nothing at HEAD, so none of this step's work exists yet.

## Input

- **Step 1 output.** A stack row type and a `stack` collection on `ConstraintsArtifact`. Each row has an id, a `concern`, and either a `choice` or an `open` marker. A concern vocabulary constant names the three required concerns.
- **Step 2 output.** A gate that refuses a first-run artifact missing a required concern, naming an unknown concern, or repeating a stack id. A decision anchored to a stack row resolves, including a row recorded `open`.
- **Names come from the landed code.** HEAD has no `stack` symbol in `plan_tool/roadmap_artifacts.py`, and these steps had not landed when this file was written. Read the landed row fields, concern spellings, and `CONSTRAINTS_ROW_KEYS`. They win over every name used here. The prompt must use the landed spellings, because `test_constraints_prompt_names_every_required_row_key` pins them.
- **What the replay proves.** Canned output through the real parser and gates shows the contract is satisfiable. It does not show a real model follows the instruction. Observing the real Integration brief is a separate act that gates nothing.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/prompts/roadmap-constraints.md`:
    - add a `## Stack` section beside `## Hosting`;
    - update the collection count in `## The frontmatter inventory` and add the `stack` bullet;
    - update the rule list and its "all seven" count;
    - add stack rows to the embedded example, with no prose line for them: stack rows are not prose-inventory rows, so the example body does not name them.
  - `tests/test_roadmap.py`:
    - add `StackRow` to the `_required_constraints_row_keys` row-type tuple;
    - update `_CONSTRAINTS_GATE_PROMPT_SUBJECTS` for the changed rule phrasing and the new stack gate;
    - extend `_constraints` and `_constraints_text` (the shared canned-artifact builders) so the stage stubs carry a total stack;
    - add the new cases under Tests.

## Implementation

**The `## Stack` section.** Place it after `## Hosting` and before `## The frontmatter inventory`, in the same plain, short style. It must say:
- Author exactly one stack row for each of the three required concerns: deployment platform, store engine, and language/runtime. Use the landed concern spellings.
- Each row records a chosen value, or `open` when the brief leaves that concern undecided. `open` is a real answer, like `not-load-bearing` for dispositions. It is the only honest answer when the brief says "not decided".
- A chosen value must come from the brief. Never invent a vendor, product, or version the brief does not name. When the brief names only a category (a relational store), record the category or record `open`. Do not narrow it to a product.
- Hosting stays as described in `## Hosting`. The hosting prohibitions still stand there. The two blocks differ on purpose: hosting rows cannot be undecided, and stack rows can.
- Recommendation: add one short worked contrast. A brief that says "no account or service is fixed yet" yields `open` for the deployment platform and not a vendor. A brief that names a store engine yields that choice.
- A stack row is a decision anchor target. Say a `pending` decision may anchor to an `open` row, so the operator can confirm the call later. Do not tell the model it must write one, and do not invent a decision to fill the section.

**Sibling sites inside the prompt (one class: the collection count and rule count).** Name the class as "prompt text that states how many collections or rules exist", then search by identifier and by vocabulary. Run `rg -n 'four collections|all four|all seven|seven\b|exactly these seven' plan_tool/prompts/roadmap-constraints.md`.
- `## The frontmatter inventory` says "four collections, in this order". Change to five and add the `stack` bullet naming every row key from step 1 as a whole token.
- The inventory's opening clause lists the keys that are required on every row, and the optional ones. Add the stack row's optional keys there if step 1 gave it any.
- Rule 2 says ids are unique "across all four collections". Update the count. Step 2's gate reports duplicate stack ids, so this must say stack rows share the id space.
- Add a rule for stack totality (every required concern has exactly one row, and each row carries exactly one of a choice or `open: true`) and, if step 2 shipped it, unknown concern. Update the "Meet all seven the first time" count to match the new total. Keep rule 7's "disposition, constraint, and decision id" scope. Stack ids are not prose-inventory rows unless step 2's gate says otherwise, so state that explicitly rather than leaving it to the reader.
- The `## Shape` example is the one fenced block opening on `---`. Keep it a single block, because `_prompt_example` asserts exactly one. Add `stack:` after `hosting:` with placeholder-style ids and one row recorded `open`, so the example shows both states. The example must parse, clear the gate set, and carry no plausible vendor. Use `<one line>` or neutral placeholders for choice text.

**Constraints on the prompt.**
- Do not cite any `*_FORMAT.md` file. `test_constraints_prompt_cites_no_repo_document`-style checks exist for components, and the repo's established rule is that prompts restate contracts inline.
- A literal `$` must be written `$$`. Add no new `${...}` placeholder. This step needs no new variable, so the placeholder-subset test stays green untouched.
- Do not tell the model to read the repository. Do not add a vendor list or example product names anywhere in the prose. The plan bans a closed vendor vocabulary. The existing example's `product: Cloud Run` is hosting and stays as it is.
- Rejected alternative: a separate stack stage or prompt. The plan keeps stack in `02-constraints.md`, so the constraints prompt owns it.

**The shared test builders.** `_constraints` and `_constraints_text` feed every stage stub. A stack-less canned artifact stays valid, because the gate never refuses absence, so shipped first-run tests stay green and are not touched. Only the Integration-brief replay fixture carries a total stack (three rows, at least one `open`).

**Replay test shape.** Stage the Integration brief text in the env's `brief_path`. The brief says no account or specific service is fixed and names only a relational store. Drive the shipped stages through `_StubInvoker` with canned conforming replies, where the constraints reply records the deployment platform as `open` and the store engine as the generic category. Assert on parsed fields, not on prose. Use the real parser and the real gates, never a stubbed gate.

## Tests

All in `tests/test_roadmap.py`, extending `TestConstraintsPromptTemplate` and `TestConstraintsPromptExample`, plus one replay class.

- `test_constraints_prompt_names_every_required_row_key` — the existing parametrized case now also covers the stack row's keys, because `StackRow` joins `_required_constraints_row_keys`; deleting the stack bullet turns it red.
- `test_constraints_prompt_names_every_stack_concern` — the prompt names each required concern from the landed concern constant, parametrized so a renamed concern fails loudly.
- `test_constraints_prompt_tells_the_model_to_record_open_when_the_brief_is_undecided` — the flattened prompt carries the open-versus-invented-vendor instruction, asserted on the stable phrase and on the `open` token.
- `test_constraints_prompt_still_forbids_inventing_a_hosting_vendor` — the hosting prohibition survives, pinned as a deliberate carve-out beside the new stack permission. Without it, widening the `open` allowance into hosting stays green.
- `test_constraints_prompt_states_every_constraints_gate_rule` — the existing parametrized case over `CONSTRAINTS_GATES`, now covering step 2's stack gate through its `_CONSTRAINTS_GATE_PROMPT_SUBJECTS` entry.
- `test_prompt_example_carries_a_total_stack_with_one_open_row` — the embedded example parses, has one row per required concern, and shows both a choice and `open`.
- `test_prompt_example_clears_the_constraints_gate_set` — the existing case, now run over an example that carries a stack.
- `test_prompt_example_stack_names_no_vendor` — the example's stack rows contain only placeholders and `open`. This keeps the example from teaching a vendor by copy.
- `test_integration_brief_replay_open_deployment_platform_clears_gates_and_renders` — with the stub invoker returning canned output recording the deployment platform as `open`, the stage run completes and writes `02-constraints.md`. The written file re-parses through `load_constraints_artifact` with the `open` row intact.
- `test_integration_brief_replay_prompt_reaches_the_model_with_the_open_instruction` — the prompt the stub invoker received for stage 2 holds the brief text and the open-versus-invented-vendor instruction.
- `test_integration_brief_replay_invented_vendor_is_not_a_gate_failure` — the replay documents that no gate judges a choice's quality: a canned artifact with a vendor choice also clears. This pins that the guard is the prompt, not a check. Do not add a vendor gate.

### Tests for this step

- Every case above must be green before the step is finished, run with `uv run pytest tests/test_roadmap.py -q`, then the full suite with `-n auto`.
- Every shipped-table test that runs stage 2 must be green on the updated `_constraints` builder. A stage-2 test left red is a missed site, not noise.
- The replay uses the invoker seam only. It must not spawn a real backend, and the autouse gate in `tests/conftest.py` enforces that.
- Verify the prompt-pinning tests by mutation: delete the `## Stack` section and the `open` instruction in turn, and confirm each test named above goes red.

## Acceptance criteria

- `plan_tool/prompts/roadmap-constraints.md` names every stack row key and each required concern as whole tokens.
- The prompt instructs recording `open` for an undecided concern and forbids inventing a vendor the brief does not name.
- The hosting block's prohibition on inventing a vendor, product detail, deployment unit, or pending decision is unchanged.
- The prompt's collection count and rule count agree with the rules it lists, and `rg -n 'four collections|all four' plan_tool/prompts/roadmap-constraints.md` returns nothing.
- The embedded example is still the only `---`-opening fenced block, parses, clears the constraints gate set, and carries no vendor name in its stack rows.
- The Integration-brief replay completes under the invoker seam with the deployment platform recorded `open`, and the written artifact re-parses.
- `rg -n 'FORMAT\.md' plan_tool/prompts/roadmap-constraints.md` returns nothing, and `rg -P '\$(?!\{|\$)' plan_tool/prompts/roadmap-constraints.md` returns nothing.
- `uv run pytest tests/test_roadmap.py -q` and the full suite pass.

## References

- [pytest: How to monkeypatch/mock modules and environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — covers keeping the replay off a real backend.
- [pytest: How to parametrize fixtures and test functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — covers the per-concern and per-key parametrized cases.
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — covers how `open` and `null` read back, so the example's `open` marker is never confused with a missing value.

## Applicable guardrails

- **The plan's "## Out of scope", stack concerns and vendor vocabulary.** The prompt names only the three required concerns and carries no vendor or product list. Example text uses placeholders.
- **The plan's "## Out of scope", judging whether a choice is good.** This step adds no gate and no prompt rule that rates a stack choice. The invented-vendor ban is an instruction to the model, and the replay pins that it is not a check.
- **The plan's "## Out of scope", approval blocks on stack content.** Nothing here blocks anything. A stack that is `open` is accepted.
- **The plan's step intent for this step.** The replay shows only what a stubbed backend can show. Do not claim, in test names or comments, that it measures real-model behavior.
- **The plan's "## Out of scope", regenerating existing versions.** This step edits one prompt for first runs and touches no accepted version.

## Deferred

- Observing a real model on the Integration brief — a separate observation that gates nothing, per the plan's step intent. It needs a real backend, which the suite cannot supply.
- A gate comparing a stack choice with a hosting or store `product` — deliberately not built (plan decision, 2026-10-08).
- Stack rendering in first-run output, `INDEX.md`, and candidate review — owned by other steps of this plan.
- Updating the components stage prompt's store-engine guidance to point at the stack — not needed for this step's outcome, and a different prompt file outside this step's files.
