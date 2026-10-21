# Changelog

Release notes for plan-tool. Unreleased changes wait as fragments in
[`changelog.d/`](changelog.d/README.md); cutting a release collects them below
(see [`docs/RELEASING.md`](docs/RELEASING.md)).

<!-- scriv-insert-here -->

<a id='changelog-0.2.0'></a>
## 0.2.0 — 2026-10-21

### Added

- A candidate can now correct one stale shared paragraph in an existing roadmap artifact. The new `correct-prose` operation replaces one issued block that names several rows, leaves every typed row unchanged, and is refused when the same candidate adds, edits, or removes a row the block names (IPPT-18).
- Structural candidate review and the stack digest now show the exact before and after text of each correction, and an edit that changes the correction requires a fresh approval (IPPT-18).

- Candidate review now lists live prose that still names a design row the candidate's own carried removals record as removed. The evidence is computed from the candidate each time, shown on the propose, review, answer and decide surfaces before approval, and nothing is stored (IPPT-19).
- The confirming approve and the answer-bound seal refuse a candidate whose live prose names a removed row, and the refusal names the defect and both exits: correct the paragraph with the `correct-prose` operation, or mark it as history. A reference to an id that is also a present row is shown as non-blocking and never refuses (IPPT-19).

- Roadmap version comparison now shows a candidate's verified row-linked prose amendments (`bound`) when its direct predecessor is the base, and reports `no-operation-evidence`, `not-applicable`, or `not-directly-bound` otherwise. The raw patch output is unchanged.

- Run-log model-call starts include a SHA-256 digest of the rendered prompt for repeated-prompt analysis, without storing prompt text. Older events remain readable.

### Changed

- The pre-send prompt-budget warning now measures a prompt against the selected model's context window when it is known, instead of always assuming 200,000 tokens. For Codex it reads the usable share of the model's window from `models_cache.json` under `$CODEX_HOME` (default `~/.codex`; refresh it with `codex debug models`). For Claude it uses the window the CLI reported on an earlier call in the same run, when that call used one model or listed the selected model's id (a result that mixes models gives only its smallest window), so a run stops warning `high` about prompts that fit a 1,000,000-token window. When no window is known the warning still uses 200,000 and now says `(default)`.
- A selected `run-reconcile` prompt is the one budget check that can refuse a send. It uses the Codex catalog's window but never a window learned during the run, so its verdict does not depend on which calls happened first.

- plan-tool declares Apache-2.0 licensing and includes the license in its package metadata and distributions.

- A roadmap candidate proposal now admits a canonical context up to 384 KiB, up from 192 KiB, so a legitimate follow-up on a modest roadmap is no longer refused before a model call with `full canonical batch payload exceeds the fixed context ceiling`. Candidates already stored under the 64 KiB or 192 KiB ceiling keep that ceiling and their exact bytes.

- Roadmap mapping guidance decomposes broad scopes into cohesive implementation plans with explicit shared responsibilities, dependencies and eventual acceptance evidence. Materialized seeds retain those boundaries and use canonical testing and acceptance sections. Mapping and seed guidance preserves source-required business production and update responsibilities; base plans retain assigned implementation work when prerequisites are pending.

### Fixed

- Re-running the proposal for a selector-era roadmap candidate stored under the 64 KiB ceiling no longer fails with `candidate capsule cannot be reproduced from its predecessor`. A stored capsule is now reproduced at the ceiling it was issued under, so a later ceiling change cannot break re-entry, review, or promotion of an existing candidate.

- Reviewing, editing, or approving a roadmap candidate whose context includes a decision row no longer refuses with `stored capsule row cannot be restored`. A stored capsule that genuinely cannot be restored now names the artifact, row, and reason.

- A roadmap candidate batch whose rows share narrative paragraphs no longer exceeds the context ceiling because each shared paragraph was repeated once per row. The batch now carries each shared paragraph once, so batches that were refused with `full canonical batch payload exceeds the fixed context ceiling` only because of that repetition can be proposed again. Candidates already stored keep their original context and verify unchanged.

- File-backed plan creation retains supplied local References through normalization, publication and continuation alongside generated research.

- Input-contract audits recognize files declared for creation by eligible registered sibling plans. Roadmap plans share promises only within the same accepted roadmap owner; missing undeclared files and stale symbols in existing files still produce findings.

- Run logs retain completion events for finding applications and direct-source assessments, and record starts for risk classification, conceptual audits, repair retries, intent proposals, and gate suggestions.

<a id='changelog-0.1.0'></a>
## 0.1.0 — 2026-09-25

### Added

- `plan-tool --version` prints the version. In a source checkout it reads
  `pyproject.toml`, so a version bump shows in an editable install without
  reinstalling.

- A reviewer feedback ledger for enrolled roadmaps. Submit, edit, retarget, defer, close and reopen feedback items with
  `plan-tool roadmap <slug> --submit-feedback ITEM_ID --feedback-target ARTIFACT:KIND[:ROW_ID] --feedback-request TEXT`
  and `--edit-feedback`, `--retarget-feedback`, `--defer-feedback`, `--close-feedback` and `--reopen-ledger-feedback`,
  without amending an accepted artifact.
- `--migrate-feedback-ledger` imports the feedback embedded in a legacy enrolled roadmap into the ledger, once.
- `--reject-candidate` and `--discard-candidate` release the active candidate.
- `--respond-decision-settlement RECEIPT_FINAL` with `--decision-settlement-yes` or `--decision-settlement-no` confirms or
  declines a decision settlement that would stale an active candidate.

- `plan-tool run --skip-merge-check` skips the new pre-run merge check for one run.

### Changed

- `--v`, `--ve`, and `--ver` no longer abbreviate `--verbose`, because they now
  also match `--version`. Use `-v`, `--verbose`, or `--verb`.

- `plan-tool roadmap <slug> --decide-candidate ID --candidate-decision approve` is now two invocations. The first prints every unpromoted candidate stacked above the accepted roadmap, the cumulative diff, and a stack digest, and changes nothing. The second, given `--confirm-stack-digest DIGEST`, seals and promotes only when the digest matches the stack.
- `plan-tool roadmap <slug> --propose-candidate` now stacks a new batch under an active structural candidate instead of refusing. A structural change anywhere in a stack needs the confirmed structural approval, and the reviewed answer route (`--review-candidate`, `--answer-question`) refuses such a stack and names `--decide-candidate`.

- `--revise-feedback` and `--propose-candidate` no longer take a feedback selector. One run snapshots every eligible
  ledger item into one inert candidate, and each later run starts from the promoted version.
- Roadmap versions created after enrollment carry no feedback rows; feedback lives in the ledger.
- Answering a review question seals a replacement that becomes the active candidate, and promoting it releases the
  candidate pointer so the next run can start at once.
- Decision settlement on an enrolled roadmap cites an eligible ledger item as its evidence.

- `plan-tool run` now refuses to run on a repository's default branch, and refuses until the plan and a detail file for every committed step are on `origin`'s default branch. A merged plan pull request is the review that precedes `run`. The check does not apply to a repository with no `origin`. Turn it off for a repository with `run.require_merged_plan: false` in `.plan-tool/config.json`, or with `PLAN_TOOL_REQUIRE_MERGED_PLAN=0`.
