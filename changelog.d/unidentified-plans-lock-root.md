### Fixed

- Commands that require a mutation lock reject a custom external
  `--plans-dir` when its checkout cannot be determined. Run from the
  destination checkout or select it with `--repo-root`.
