### Fixed

- A plan written by an older `create`, whose `source_seed` is recorded relative to the plans directory, now resolves its seed. Its audit sees the seed's scope contract and, for a roadmap plan, the `creates:` paths of the sibling plans, and its saved audits read stale once after upgrade: re-audit once and treat that run as the new baseline. A `source_seed` that resolves repo-relative resolves exactly as before, and a plan whose seed file is gone stays unresolved.
