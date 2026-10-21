# Handoff: resume order for the Integration seam and roadmap-fit work

## Status

This is the entry point for the next session on the Ideation-to-roadmap
seam. It names what is authoritative, where each piece stands, and what to do
next across the Integration and `plan-tool` repositories. It restates no design
decision and authorizes no `roadmap` run, `plan-tool` change, or Integration
application code.

## What is authoritative

| Record | Repository | Role |
| --- | --- | --- |
| [`2026-09-11-roadmap-aidlc-inception-fit.md`](2026-09-11-roadmap-aidlc-inception-fit.md) | `plan-tool` handoffs | The design: eight changes, settled decisions, open design choices, and next steps |
| [`2026-09-11-integration-ideation-roadmap-intake-review.md`](2026-09-11-integration-ideation-roadmap-intake-review.md) | `plan-tool` handoffs | The review question, evaluation criteria, and execution fence |
| `BACKLOG.md` #384 | `plan-tool` | Amended: carried decisions cite their source instead of carrying rejected alternatives |
| `handoffs/README.md` | Integration | Integration's canonical execution checklist; its current checkpoint and single-brief steps require refresh before use |

## Where things stand

- Integration's AI-DLC intent `260909-integration-mvp` completes Verification Gate 1 and is
  parked at `practices-discovery`. The runtime enters that stage as the next
  boundary after approval and parks without producing an Inception artifact.
- Integration commits `6bccfd2` and `e44543f` carry the transport-boundary revision,
  Gate approval, and its audit trail. Commit `0527be7` then directly corrects
  four approval-handoff prose sites so the experiment compares source
  semantics while the production carrier remains a separate choice.
- The Gate receipt fingerprints the bytes before `0527be7`. The current
  corpus is therefore complete and committed but not yet an approval-bound
  frozen source at HEAD. At pickup on 2026-09-11, Integration's worktree is clean and
  local `main` is one commit ahead of `origin/main`.
- The completed decision log repeats confirmed question answers rather than
  adding independent authority. It stays `approval-evidence`; the question
  files supply the inherited `decisions` role.
- The design's § "Settled decisions" lists what is decided. Its
  § "Open design choices" lists what is not, marking each entry unblocked or
  blocked.
- The generic stage-run source-admission boundary completes independent review
  on 2026-09-14. It remains separate from the closed route-local non-stage
  policy, #367's delivered operator-intent policy, and all AI-DLC role-routing
  work.
- No roadmap has run against the AI-DLC corpus.

## Resume order

1. **Restore exact Gate 1 source identity.** Take the four files in Integration
   commit `0527be7` through a fresh Approval & Handoff validation so the Gate
   receipt binds their exact bytes, park again before Inception work, commit
   the resulting audit/state record, and push Integration's local commit. Do not edit
   the source corpus again between validation and the experiment.
2. **Refresh Integration's canonical handoffs README.** Its current checkpoint still
   says Intent Capture, and its steps 3 to 6 still prescribe the initiative
   brief as the production source even though the current design leaves the
   carrier unselected. Align it with the experiment boundary before using it
   as execution authority.
3. **Decide the unblocked design choices** while steps 1 and 2 are in
   progress. They need no corpus.
4. **Run the revised experiment** in `plan-tool-2` once the corpus is frozen:
   the initiative brief against a script-built composition of the
   framework's Inception inputs, with the design's measures and its revision
   pass. Launch each run in the background with a named `.tmp/` log and
   `set -o pipefail`.
5. **Decide what Integration's first roadmap run needs,** and whether the frame
   reaches the wording-only and read-only requests, from the experiment's
   results.
6. **Draft backlog entries and plan seeds** in `plan-tool-2` for the changes
   step 5 selects, then take them through `create`, the two audit gates,
   `detail`, and `run`.
7. **Settle framework requirement IDs** after the Inception-step coverage
   decision.

## Repository discipline

- Roadmap and Integration-support work starts in `plan-tool-2`. It reaches the
  canonical checkout by pushing to `origin` and fast-forwarding canonical
  from a fetch.
- The canonical checkout's `origin` also pushes to a Bitbucket mirror, and
  `plan-tool-2`'s does not. Work pushed from `plan-tool-2` reaches the
  mirror only when canonical pushes.
- Merge commit `af78786e` on `main` carries a commit-message trailer that
  the author's commit rules would normally strip. It stays as is, decided
  2026-09-11; rewriting pushed `main` is not worth a force-push.

## Scope fence

- This handoff authorizes no `roadmap` run, no `plan-tool` change, and no
  Integration application code.
- The design governs every design question; this handoff only orders the
  work.
