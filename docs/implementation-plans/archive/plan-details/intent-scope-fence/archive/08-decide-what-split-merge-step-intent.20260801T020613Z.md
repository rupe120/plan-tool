> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 8 — Decide what split and merge do with a step's intent

## Summary

This step settles what `plan_tool/detail.py`'s two structural verbs do with step 1's `Step.intent` and writes the answer down as a contract instead of leaving it to whatever the code happens to do. **Split never copies the target's intent onto a half** — that needs no production edit, so its work is the stated rule plus the tests that pin it. **Merge keeps an intent only when every folded member states the same one, and clears it otherwise** — one small fold added beside the existing `merged_change_type` / `merged_eta` folds in `merge_steps`. The main design decision is that a member's intent never survives a fold on its own: the survivor also does the other members' work, so a one-line why that covers part of a step reads as authoritative while fencing the model away from the rest. On green, both verbs leave every surviving step with an intent that is true of it or with none at all, and a plan carrying no intent anywhere splits and merges to frontmatter with no `intent:` key in it.

## Table of Contents

- [Summary](#summary) — the two rules, and the one that costs no production code.
- [Why](#why) — why a carried-over why is worse than no why at all.
- [Input](#input) — the four contracts this step reads from step 1 and from `create.py`'s transforms.
- [Files (creates vs edits)](#files-creates-vs-edits) — two edited files, no new files.
- [Implementation](#implementation) — the split rule, the merge fold, the rejected alternatives, and seven gotchas.
- [Tests](#tests) — 13 new cases across four existing classes, and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — checkable facts a reviewer can run.
- [References](#references) — the pydantic, YAML, and pytest behavior this step leans on.
- [Applicable guardrails](#applicable-guardrails) — the fence entries that bind, and the two places breaking them is tempting.
- [Deferred](#deferred) — what steps 9 and 10 own, and the four things routed out.

## Why

Split and merge are the two verbs that change which steps exist. A split takes one step that did two things and makes two steps; a merge takes several and makes one. Both rewrite `files`, `change_type`, `complexity`, `depends_on`, `status`, and `concept_ids` deterministically, and every one of those folds is written down — `_MERGE_CHANGE_TYPE_RANK` picks the dominant type, `_apply_step_split` owns the edges and the first half's status, `_apply_step_merge` owns the ordered union of concept ownership. Once step 1 lands, there is one more field on `Step` and no rule for it. The default that falls out of the code is not obviously wrong, but nobody stated it, so nobody can rely on it: the next person to touch the `replacements = [Step(...)]` list in `split_step` sees `change_type` and `complexity` being passed down and adds `intent=target.intent` in the same spirit, and that one line puts a claim about the parent's purpose on two steps that each do half of it. The plan's rule for propagation is that every surviving step ends with a defensible value — carried, composed, or cleared — and never one that is quietly false. This step is where that rule gets written for split and merge.

## Input

Four contracts this step reads and does not own. Read each off HEAD before you start; where a landed name differs from a name below, the landed name wins.

- **Step 1's step-level field.** `Step.intent` (created by step 1 in `plan_tool/schema.py`; not at HEAD), `Optional[str] = None`, storing whatever YAML handed over with no stripping and no cap. So this step must handle `None`, `""`, `"   "`, a normal one-liner, and a value with real newlines — step 1 preserves all of them, so the merge fold decides what each one means.
- **`plan_tool/create.py:_apply_step_split`'s ownership split.** It trusts the caller for content and owns only `id`, `depends_on`, and `status`, applying them through `rep.model_copy(update={...})` on each replacement. It never adds a field the caller left unset, so whatever `split_step` does (or does not) put on a replacement is what lands on disk. It also refuses replacements that drop or invent `concept_ids`; there is no matching conservation rule for `intent`, and this step does not add one.
- **`plan_tool/create.py:_apply_step_merge`'s ownership split.** Same shape, inverted: it trusts the `merged` step for authored content and owns `id`, `depends_on`, `status`, and `concept_ids`, applied through `merged.model_copy(update={...})`. So an `intent` set on the `merged = Step(...)` assembly in `merge_steps` survives the fold unchanged, and `plan_tool/create.py` needs no edit.
- **`plan_tool/parser.py:write_plan`'s dump flags.** It dumps with `model_dump(exclude_defaults=True, exclude_none=True)`, so a field left at `None` writes no key. That is the whole mechanism behind "a plan with no intent is rewritten with no `intent:` line" — this step gets it for free and must not defeat it by writing `""`.

**What the tests here cannot prove.** Nothing in this suite can show that a kept intent actually reaches the model doing the merged re-author — that path runs through step 4's fence renderer, and this step depends only on step 1. See [Deferred](#deferred).

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/detail.py` — add the unanimous-intent fold helper beside `_MERGE_CHANGE_TYPE_RANK` / `_MERGE_COMPLEXITY_RANK`; pass its result as `intent=` in `merge_steps`'s `merged = Step(...)` assembly; extend the comment above `split_step`'s `replacements = [Step(...)]` list and both verbs' docstrings so each states its intent rule.
  - `tests/test_detail.py` — add an `intents=` parameter to the `_build_merge_plan` helper; add 13 cases across `TestSplitStepOnDemand`, `TestInteractiveSplit`, `TestMergeSteps`, and `TestMergeBridge`.

Deliberate zero-diff files, named so a reviewer can check them: `plan_tool/create.py` (both transforms already carry whatever the caller sets), `plan_tool/launcher.py` (see the split rule below), `plan_tool/cli/authoring.py` and `plan_tool/cli/convergence_cmd.py` (no new flag — `plan-tool split --into` and `plan-tool merge --title` keep their current surface).

## Implementation

### The two rules

State both in the verbs' docstrings, in these terms:

- **Split: a half never inherits the target's intent.** The target's one line describes the whole of what the target was for; the split exists because that was two things. Copying it onto both halves makes it authoritative and wrong on both. Each half starts with no intent, and step 2's advisory finding is what asks the author to fill one in.
- **Merge: the survivor keeps an intent only when every folded member states the same one.** Anything else clears it. "The same" means equal after collapsing runs of whitespace; a missing or blank intent on any member clears.

Neither verb touches the plan-level `Plan.intent`. A split or a merge changes how the work is cut up, not what the plan is for.

### Split — no production edit, two comments and a docstring

`split_step` builds its replacements as `Step(id=0, title=t, change_type=..., complexity=..., concept_ids=...)` and never passes `intent`, so each half starts at `None`. `_apply_step_split` copies replacements without adding fields. The rule already holds; what is missing is the statement of it.

- Extend the comment above the `replacements` list. It enumerates what the halves inherit from the parent, so leaving `intent` out of that list silently reads as an oversight and invites the one-line "fix". Say plainly that intent is *not* inherited and why.
- Add the rule to `split_step`'s docstring next to the existing sentence about replacements inheriting `change_type`/`complexity`.

**The second producer of split halves needs no edit either.** `plan_tool/launcher.py:escalate_to_split` — the bridge `generate_detail`'s Phase-B purity check and the review/reconcile walk use — builds its two halves from `plan_tool/create.py:_propose_step_split`, which parses a fresh model proposal through `_parse_steps_json`. Those replacements are built from the model's JSON, never from the target `Step`, so the parent's intent has no path onto them. After step 7 that parse reads an `intent` key when one is present, but the split proposal prompt does not ask for one — and a per-half intent the model volunteers is the half's own, which the rule allows. Pin this path with a test rather than an edit: `tests/test_detail.py` already drives the real bridge end to end through `generate_detail`, so the case lands inside this step's declared files.

### Merge — one small fold

Add a helper beside the two rank tables in `plan_tool/detail.py`, named for what it returns — one way: `_unanimous_intent(member_steps) -> Optional[str]`. Contract:

- Return `None` when any member's intent is `None`, empty, or whitespace-only.
- Return `None` when the members' intents differ after collapsing runs of whitespace.
- Otherwise return **the first member's text as written**. The collapsed form is only the comparison key; merge does not rewrite the string it keeps.

Then pass `intent=_unanimous_intent(member_steps)` in the `merged = Step(...)` assembly, beside `merged_files`, `merged_change_type`, and `merged_eta`. It belongs in that block because that block is exactly where the other per-field folds live, and because `merge_bridge` and `cmd_merge` both reach the fold through `merge_steps` — putting it anywhere else creates a second rule.

Treating blank as absent matches step 2's precedence rule, which classifies a whitespace-only value as *missing* rather than over-long. Keep the two consistent; a value the advisory check calls missing must not be a value merge treats as a statement.

**Rejected alternatives, and why:**

- **Join the distinct member intents with `"; "`.** Composition is allowed by the plan, and this is the only composition available without a Claude call — but it produces machine prose that then reads as the author's stated purpose. It also fails on size: two members with ~100-character intents already clear step 2's 200-character cap, so a routine two-step merge would manufacture its own advisory finding. Clearing loses information; joining invents authority.
- **Keep the one member that has an intent when the others are silent.** This is the tempting middle ground and it is the case the rule exists to refuse. The survivor also does the silent member's work, so an intent covering only part of the merged step is exactly the "authoritative but wrong" shape — worse here than elsewhere, because after step 5 that line reaches the `run` prompt as a boundary and tells the model the rest of the step is out of scope.
- **Ask Claude to compose one from the folded detail bodies.** New token spend the plan does not allow, and it is a judgment about what a good intent says — the one thing the plan bans anywhere in this feature.
- **Add `intent=` parameters to `split_step` / `merge_steps` so an operator can name the halves' purposes.** No CLI file is in this step's list, so the parameter would have no caller. Routed out — see [Deferred](#deferred).

### Gotchas

- **Never write `""`.** `write_plan` drops `None` fields, so a cleared intent leaves no key in the rewritten frontmatter. An empty string would be written, adding an `intent:` line to plans that never had one — which is the migration the plan forbids.
- **Leave `plan.intent` alone.** Both verbs persist through `plan.model_copy(update={"steps": new_steps})`, which carries every other plan-level field through untouched. Keep that call shape.
- **Keep the fold out of `merge_bridge`.** The bridge's job is opt-in, confirmation, and outcome mapping; it calls `merge_steps` for both its dry-run preview and its real apply, so it inherits the rule automatically. A second copy there would drift.
- **Leave the dry-run previews as they are.** `SplitResult.new_plan` and `MergeResult.new_plan` rows are `(id, title, depends_on)`. Adding intent changes a public dataclass shape, which is outside what the plan allows to change.
- **Do not hand the survivor's intent to the re-author separately.** `merge_steps` writes the folded plan before it re-authors, and `generate_detail` re-parses the plan from disk, so the re-author already sees whatever the fold decided.
- **Reuse step 6's whitespace collapse if it is reusable, otherwise repeat it.** If step 6 landed a standalone collapse helper in `plan_tool/create.py`, call it through the lazy `from plan_tool.create import ...` that `merge_steps` already does for `_apply_step_merge`. If the collapse is baked into step 6's `## Outcome` lift, repeat the one expression here rather than exporting a private name — and see [Deferred](#deferred) for the consolidation.
- **The comparison is intents against each other.** It never compares an intent to plan prose, to a detail body, or to a diff. That is what keeps this step inside the plan's fence, and the folded members' full bodies sitting right there in `prior_body` are the temptation to watch for.

## Tests

### Tests for this step

All 13 land in `tests/test_detail.py`, in the four classes that already cover these verbs. `_build_merge_plan` gains an `intents:` mapping parameter, mirroring its existing `concept_ids:` and `statuses:` parameters; the split cases seed the target's intent by parsing `_SPLIT_PLAN_PENDING`, setting the field, and writing the plan back, the way `_owned_pending_plan` already does for `concept_ids`.

`TestSplitStepOnDemand`:

- `test_split_halves_do_not_inherit_the_target_intent` — target carries an intent; after the split both halves have `intent is None`.
- `test_split_leaves_the_plan_intent_untouched` — the plan-level intent is unchanged by the split's write.
- `test_split_writes_no_intent_key_when_nothing_carries_one` — on a plan with no intent anywhere, the rewritten file contains no `intent:` line.

`TestInteractiveSplit`:

- `test_phase_b_split_halves_do_not_inherit_the_target_intent` — drives the real `escalate_to_split` path through `generate_detail`; neither half's intent equals the mixed target's, and both are `None` under the `_SPLIT_JSON` fixture.

`TestMergeSteps`:

- `test_merged_step_keeps_a_unanimous_member_intent` — both members state the same intent; the survivor keeps it.
- `test_merged_step_keeps_the_first_members_text_verbatim` — members differ only in spacing; the stored value is the first member's string, not a collapsed rewrite.
- `test_merged_step_clears_on_differing_member_intents` — two different intents; the survivor has `None`.
- `test_merged_step_clears_when_a_member_has_no_intent` — one member `None`, the other set; the survivor has `None`.
- `test_merged_step_clears_when_a_member_intent_is_blank` — whitespace-only counts as absent, so the survivor has `None`.
- `test_merged_step_has_no_intent_when_no_member_carries_one` — the legacy case: no member has one, the fold returns `None`, nothing raises.
- `test_merge_leaves_the_plan_intent_untouched` — the plan-level intent survives the fold's write.
- `test_merge_writes_no_intent_key_when_nothing_carries_one` — on a plan with no intent anywhere, the rewritten file contains no `intent:` line.

`TestMergeBridge`:

- `test_merge_bridge_applied_fold_uses_the_same_intent_rule` — through the bridge's applied path, the survivor's intent obeys the same rule, proving the bridge holds no second copy of it.

**Green-before-done gate:** every case above, plus the existing `TestSplitStepOnDemand`, `TestInteractiveSplit`, `TestMergeSteps`, `TestMergeBridge`, `TestMergeIsSafe`, and `TestSplitIsSafe` classes, must pass before this step is finished. Run `uv run pytest tests/test_detail.py -q` for the loop and the full suite before closing — no existing plan fixture anywhere in `tests/` may need an edit, which is this step's share of the plan's no-migration proof.

## Acceptance criteria

- Splitting a step whose `intent` is set leaves both halves with `intent is None` in the written plan.
- Splitting through `plan_tool/launcher.py:escalate_to_split` (the Phase-B path) likewise leaves neither half carrying the target's intent text.
- Merging two steps that state the same intent (ignoring whitespace differences) leaves the survivor carrying the first member's text exactly as written.
- Merging two steps that state different intents, or where any member's intent is missing, empty, or whitespace-only, leaves the survivor with `intent is None`.
- After either verb, `parse_plan(plan_path).intent` equals what it was before.
- After either verb on a plan where no step and no plan carries an intent, `"intent:" not in plan_path.read_text()`.
- `plan_tool/detail.py`'s `split_step` and `merge_steps` docstrings each state their verb's intent rule.
- `git diff --stat` for this step names exactly `plan_tool/detail.py` and `tests/test_detail.py`.
- `rg "intent" plan_tool/create.py plan_tool/launcher.py plan_tool/cli/authoring.py plan_tool/cli/convergence_cmd.py` shows no change from HEAD in those four files.
- `uv run pytest tests/test_detail.py -q` passes, and the full suite passes with no edits to existing plan fixtures.

## References

- [pydantic BaseModel API](https://docs.pydantic.dev/latest/api/base_model/) — `model_copy(update=...)` semantics: it copies the model and overrides only the named fields, which is why a field set (or left unset) on a replacement or on the `merged` step survives `create.py`'s two transforms untouched.
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — `safe_dump` behavior behind `write_plan`; read it for why a `None` field writes no key and a plan with no intent is rewritten without one.
- [YAML Ain't Markup Language (YAML™) revision 1.2.2](https://yaml.org/spec/1.2.2/) — scalar styles and line folding: why a plain multi-line scalar arrives space-joined while a `|` literal block keeps its newlines, which decides what the whitespace-collapse comparison actually compares.
- [How to parametrize fixtures and test functions — pytest](https://docs.pytest.org/en/stable/how-to/parametrize.html) — table-driven cases for the merge fold's five member-intent combinations.

## Applicable guardrails

- **"Nothing becomes required at parse time, and no plan on disk is migrated."** This binds the write path on both verbs: a cleared intent must be `None`, never `""`, so a plan that had no `intent:` key still has none after a split or a merge. Two of this step's acceptance criteria exist to check exactly that.
- **"No step ships a check comparing an intent against prose or against a diff."** The merge fold compares members' intents to each other, which is not what the fence forbids. The tempting breach is right beside the fold: `merge_steps` reads the folded members' full detail bodies into `prior_body`, so checking a kept intent against them, or composing one from them, is one short reach away. Do neither.
- **"Allowed behavior changes: two optional frontmatter fields; one advisory finding class; and rendered input reaching three consumers across five templates — `detail.md` and `detail-jira.md`, `run.md` and `run-jira.md`, and `plan-audit.md`. The run lane additionally gains the plan's existing guardrail and `## Out of scope` sections whether or not an intent is set. Nothing else."** So this step adds no CLI flag, no new finding source, and no change to the `SplitResult` / `MergeResult` shapes. It sets a field the plan already allows, at the two places that assemble a step.
- **"Allowed reorganization: one named move (step 3). Nothing else."** So no extracting a shared one-line collapse helper out of `create.py` here, even though this step is its second user.
- **Audit fence:** a finding asking that intent propagation widen past the four structural verbs, or that intent become required, belongs in `BACKLOG.md`, not in this step.

## Deferred

- **Scope-out and reground propagation** — step 9 owns `plan_tool/scope_out.py` and `plan_tool/reground.py` and the forward seeds they write.
- **Writing the four propagation rules down in the reference docs** — step 11 owns `PLAN_FORMAT.md`, `SEED_FORMAT.md`, `CLAUDE.md`, and the flow docs.
- **A test that a kept intent reaches the merged step's re-author prompt** — that runs through step 4's fence renderer, and this step depends only on step 1, so the assertion cannot be relied on to be available when this step runs. Worth adding once step 4 has landed.
- **Operator-named intents on the CLI** (`plan-tool split --into "…" --intent "…"`, `plan-tool merge --intent "…"`) — no CLI file is in this step's list, so the parameter would have no caller, and the fence caps what behavior may change. File in `BACKLOG.md` if wanted.
- **Showing the intent decision in the dry-run preview** — `SplitResult.new_plan` / `MergeResult.new_plan` rows would have to grow a field, changing a public dataclass. `BACKLOG.md`.
- **Asking the split proposal for a per-half intent** — the rule here permits a freshly authored per-half value, but the prompt lives in `plan_tool/create.py:_propose_step_split`, which is not in this step's file list.
- **A conservation check for `intent` in `plan_tool/create.py:_apply_step_split`**, mirroring the one it enforces for `concept_ids` — unnecessary (this step's rule is that nothing is conserved) and `plan_tool/create.py` is not in scope.
- **One shared one-line collapse helper** across `plan_tool/create.py` (steps 6 and 7) and `plan_tool/detail.py` — a consolidation across modules that `detail` cannot mint. Route it to reconcile or `BACKLOG.md` rather than widening this step.
