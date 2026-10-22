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
