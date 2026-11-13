# Overengineering checkpoints: next-session pickup

Use the merged checkpoints on the next real task. No implementation work or
installation repair remains for this change; the open question is whether the
judgments consistently catch unnecessary work in practice.

| Item | Current state |
| --- | --- |
| Delivery | [PR #194](https://bitbucket.org/protagona/plan-tool/pull-requests/194) is merged into `main` at `daf5b6959` |
| Checkouts | This clone and the source checkout behind the active Claude links are clean and aligned with that merge before this handoff |
| Codex installation | Installed skill router and shared directives match the merged source byte for byte |
| Claude installation | Both directive links resolve to the updated shared source; the skill router includes the reminder |
| Verification | Full parallel suite: 14,752 passed, 67 skipped; the pre-push suite also passes |
| Behavioral evidence | One final executable Codex task visibly exercises the pre-edit checkpoint and final-review answer; broader reliability remains unmeasured |

## What to do next

1. Pick the user's next real task; do not create a separate implementation
   effort just to elaborate these checks.
2. Before the first edit, explicitly ask **“Are we overengineering this?”**
   State the required outcome, the simpler alternative, and what justifies
   any extra complexity or what will be simplified.
3. Apply the same judgment at the relevant seed, bare-plan, detail, and
   audit/review correction-batch transitions. During final review, consider
   the whole change again and include the answer in the completion response.
4. If the checkpoint exposes unnecessary machinery, simplify within the
   settled scope. Surface any change to a settled contract or scope to the
   user before proceeding. Preserve required safety and ownership properties.
5. If a real task misses a checkpoint or reveals a substantive limitation,
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
