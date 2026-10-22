### Fixed

- Concept synchronization no longer normalizes existing LF, CRLF and CR body newlines when reading plans. Scope-out failure rollback restores the original plan newline bytes and matching provenance.
