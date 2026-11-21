### Fixed

- Mutating commands lock the checkout they operate on, including when
  `--plans-dir` points to another checkout. If the destination is already
  locked, the command stops before changing it.
