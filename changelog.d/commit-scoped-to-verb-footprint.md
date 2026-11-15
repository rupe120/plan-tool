### Changed

- `--commit` on `run`, `detail`, `completeness-audit` and `manifest sweep` commits only the paths that verb wrote: the plan, its `plan-details/<slug>/` directory, declared detail files and lessons log, the files under `.plan-tool/` that `.gitignore` does not exclude, any archive moves, and for `run` the files the step changed. Changes another process makes elsewhere in the tree stay out of the commit (BACKLOG #209).
- A failed `--commit` now says whether the commit landed. A commit that went in before a hook rewrote a file is reported as committed, with no `git reset` advice.

### Added

- plan-tool writes `.plan-tool/.gitignore` (it ignores itself) before a `--commit` verb's clean-tree check, so its runtime state (run logs, `run-prefs.json`, telemetry, review and checkpoint caches, the mutation lock) is ignored by default. An existing file is never overwritten, and a runtime file a repo already tracks stays tracked.

### Fixed

- `--commit` commits a staged delete (`git rm`, the old side of `git mv`), commits a symlink as a link, works from a project root nested below the git top level, and leaves pre-commit hooks' own glob matching alone.
