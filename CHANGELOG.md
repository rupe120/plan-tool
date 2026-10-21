# Changelog

Release notes for plan-tool. Unreleased changes wait as fragments in
[`changelog.d/`](changelog.d/README.md); cutting a release collects them below
(see [`docs/RELEASING.md`](docs/RELEASING.md)).

<!-- scriv-insert-here -->

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
