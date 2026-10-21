### Added

- Run-log model-call starts include a SHA-256 digest of the rendered prompt for repeated-prompt analysis, without storing prompt text. Older events remain readable.

### Fixed

- Run logs retain completion events for finding applications and direct-source assessments, and record starts for risk classification, conceptual audits, repair retries, intent proposals, and gate suggestions.
