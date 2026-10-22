# Plan seeds

New plan seeds default to this directory: `docs/implementation-plans/plan-seeds/`.
Author seeds using [SEED_FORMAT.md](../../../SEED_FORMAT.md), then pass the exact
path to `plan-tool create <slug> --from-existing <path>`.

Existing seeds remain in the repository-root `plan-seeds/` directory. This change
moves the default for new files only; it does not relocate, rename or rewrite
existing seed files. Existing explicit paths remain valid. Annotate destination
flags still override the default, and its report stays beside the source unless
a report/output override is supplied. Roadmap updates retain the destination of
an already published seed.


Default annotate seed output refuses an existing destination instead of replacing
it. A batch with same-named sources in different directories fails its collision
preflight. Use separate invocations with distinct explicit `--seed` paths for
those sources. Explicit `--seed`, `--seed-dir` and `--output-dir` destinations
retain their replacement behavior.
