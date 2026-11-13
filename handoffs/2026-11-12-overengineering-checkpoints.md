# Overengineering checkpoints: next-session pickup

Use the merged checkpoints on the next real task. No checkpoint implementation
work remains. Before a model-backed task, refresh the active instruction
sources to include the project backend/model selection guidance in PR #195.
The open behavioral question is whether the judgments consistently catch
unnecessary work in practice.

| Item | Current state |
| --- | --- |
| Delivery | [PR #194](https://bitbucket.org/protagona/plan-tool/pull-requests/194) is merged at `daf5b6959`; [PR #195](https://bitbucket.org/protagona/plan-tool/pull-requests/195) adds project model selection at `c46512f7f` |
| Handoff publication | [PR #196](https://bitbucket.org/protagona/plan-tool/pull-requests/196) is open for this handoff and index entry |
| Checkouts | This handoff branch includes `main` through `c46512f7f`; the source checkout behind the active Claude links remains at `daf5b6959` at this review |
| Codex installation | Installed router and directives contain the checkpoints but predate PR #195; neither matches current `main` byte for byte |
| Claude installation | Both directive links resolve to the earlier source checkout; its router contains the reminder but lacks PR #195 selection guidance |
| Verification provenance | PR #194 full suite: 14,752 passed, 67 skipped; its pre-push suite also passes. These counts describe that snapshot, not current `main` |
| Behavioral evidence | One final executable Codex task visibly exercises the pre-edit checkpoint and final-review answer; broader reliability remains unmeasured |

## What to do next

1. Resolve and refresh the active instruction source checkout and installed
   copies from merged `main`, preserving unrelated changes. Verify the
   checkpoint section, router reminder, and backend/model guidance together.
   Copied-skill freshness validation remains separately scoped in
   [BACKLOG #525](../BACKLOG.md); do not implement it as part of this pickup.
2. Pick the user's next real task; do not create a separate implementation
   effort just to elaborate these checks.
3. Before the first edit, explicitly ask **“Are we overengineering this?”**
   State the required outcome, the simpler alternative, and what justifies
   any extra complexity or what will be simplified.
4. Apply the same judgment at the relevant seed, bare-plan, detail, and
   audit/review correction-batch transitions. During final review, consider
   the whole change again and include the answer in the completion response.
5. If the checkpoint exposes unnecessary machinery, simplify within the
   settled scope. Surface any change to a settled contract or scope to the
   user before proceeding. Preserve required safety and ownership properties.
6. If a real task misses a checkpoint or reveals a substantive limitation,
   record the concrete observation in the existing evidence or review record
   before proposing another instruction change.

The question and its answer must be visible; a small diff alone does not show
that the explicit checkpoint occurs. Conversely, asking the question does not
prove that the design is proportionate.

## Canonical sources and settled boundaries

- [Shared directives](../integrations/shared/DIRECTIVES.md#explicit-overengineering-checkpoints)
  own the checkpoint timing and judgment. [CONTRIBUTING](../CONTRIBUTING.md#code-review-where-the-craft-gets-taught)
  routes developers to that contract.
- The [Codex](../integrations/codex/SKILL.md),
  [Claude](../integrations/claude/SKILL.md), and
  [Cursor](../integrations/cursor/SKILL.md) routers carry the short entry
  reminder: an answer before editing and a final-review answer at completion.
- [Backend/model selection](../integrations/shared/DIRECTIVES.md#which-model-to-run-a-subcommand-with)
  honors explicit user requests. Otherwise, when `.plan-tool/backends.json`
  exists, omit `--backend` and `--model`; without it, use the documented
  recommendations. Deterministic commands need neither flag. See
  [BACKENDS](../docs/BACKENDS.md) for configuration and precedence. Do not
  copy the test record's explicit experiment model into new task invocations
  as an unconditional override of project settings.
- This is a session judgment. No automated semantic gate, new blocking
  predicate, exit-code change, extra model pass, or pipeline-prompt expansion
  is part of the change.
- Future reuse or flexibility alone does not justify extra machinery. A
  simpler option that violates a current acceptance or safety property is
  not an acceptable simplification.

## Evidence and its limits

The [test record](../docs/evidence/overengineering-checkpoints-test.md) owns
the exact scenarios, responses, methods, installation checks, and limitations.
Provenance from 2026-11-12:

| Test | Observed result |
| --- | --- |
| Four loaded-context scenarios, baseline versus checkpoints | Explicit question: 0/4 versus 4/4; both conditions make the same substantive choices |
| Executable task with updated directives only | The assistant reads the reference but omits both explicit checkpoints |
| Same task with first skill-entry reminder | Pre-edit question appears; final-review answer is absent |
| Same task with clarified reminder | Both checkpoints are visible; the argparse/JSON change stays small and its two tests pass |

These are small synthetic/executable fixtures, not production delivery or
independent repeated trials of the final wording. Claude, Cursor, and the
plan-stage transitions are not behaviorally tested. The result supports
instruction delivery and visible judgment on one direct task, not improved
design quality or reliable compliance across tasks.

## Latest-change review

Review scope is `daf5b6959..c46512f7f`, the merged project-model-selection
change. Direct block comparisons confirm that the checkpoint section and all
three router reminders remain unchanged. The relevant change is backend/model
selection guidance, not a new overengineering mechanism or behavioral trial.

The [project-model-selection record](2026-11-12-project-model-selection-implementation.md)
owns that feature's execution and review evidence, including its 14,824-pass,
67-skip full-suite receipt. That record is not evidence that the explicit
overengineering checkpoints run on a real task. Its remaining preflight issue
is separately tracked as BACKLOG #526; neither that issue nor #525 expands
this handoff's checkpoint scope.

## Local pickup and retirement

The original local commits remain on
`archive/overengineering-checkpoints-local` in both checkouts; no reset or
deletion is needed to recover that provenance. The merged PR branch is
`docs/explicit-overengineering-checkpoints`. Scratch fixtures and logs under
`.tmp/overengineering-checkpoints/` are optional local evidence, not required
inputs for pickup; the tracked test record retains the conclusions.

Before updating installed instructions, resolve the actual source checkout
and compare it with the installed files. Preserve newer unrelated rules;
do not overwrite them with an older clone's entire instruction file.

Retire this handoff and its index entry when observation on the next real
task has a durable home and no pickup decision remains. Keep the canonical
instructions and evidence record.
