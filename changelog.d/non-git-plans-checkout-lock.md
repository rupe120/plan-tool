### Fixed

- Mutating commands respect the lock on a separate non-Git checkout selected
  through its `docs/implementation-plans` directory, even when the command
  uses a different repository root.
