### Changed

- Newly generated seeds default to `docs/implementation-plans/plan-seeds/`. Existing seed files and recorded legacy publication locations remain in place; explicit destinations still take precedence.

### Fixed

- Default annotate output refuses existing seeds and colliding source names, and preserves files created concurrently. Explicit output destinations retain their existing replacement behavior.
