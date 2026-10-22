### Fixed

- Scope-out recovery preserves concurrent plan/concept edits, restores only its own published bytes, and reports incomplete rollback with affected paths. Publication is durable, retains existing file modes and symlink targets, and detail undo refuses occupied destinations.
