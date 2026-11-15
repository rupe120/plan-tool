### Changed

- `--commit` on `run`, `detail`, `completeness-audit` and `manifest sweep` commits only the paths that verb wrote: the plan, its `plan-details/<slug>/` directory, declared detail files and lessons log, the files under `.plan-tool/` that `.gitignore` does not exclude, any archive moves, and for `run` the files the step changed. Changes another process makes elsewhere in the tree stay out of the commit (BACKLOG #209).
- A failed `--commit` now says whether the commit landed. A commit that went in before a hook rewrote a file is reported as committed, with no `git reset` advice.

### Added

- The first `--commit` in a repo without `.plan-tool/.gitignore` fills the gaps in its ignore rules for plan-tool's runtime state (run logs, `run-prefs.json`, telemetry, review and checkpoint caches, the mutation lock): it writes only the patterns the repo's own rules leave undecided, and commits the file on its own (`plan-tool: ignore runtime state by default`). The file is tracked so a team shares one copy. It is never overwritten, a committed deletion opts out, and a runtime file a repo already tracks stays tracked.

### Fixed

- `--commit` commits a staged delete (`git rm`, the old side of `git mv`), commits a symlink as a link, works from a project root nested below the git top level, and leaves pre-commit hooks' own glob matching alone.
