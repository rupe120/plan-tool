### Changed

- New and rewritten plans use step `description`; legacy step `title` remains accepted. Matching dual-key strings are accepted, while conflicting or invalid values are rejected. Plan format stays v1 with no explicit upgrade required; older installations that do not recognize `description` cannot read the new output (BACKLOG #517).

### Fixed

- Rewriting a plan preserves its body bytes, including CRLF and CR line endings, while retaining concurrent-edit protection (BACKLOG #517).
