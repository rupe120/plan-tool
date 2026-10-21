> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-incremental-revision.md`.
> Preserved here for history; do not edit.

# Plan seed: Roadmap Incremental Revision

## Outcome

`plan-tool roadmap` will turn one or more explicitly selected, related feedback
rows into a bounded revision session: it will obtain small, schema-checked
patches for only the affected roadmap collections, preserve every non-targeted
canonical row and reviewer-owned review state, and publish the complete valid
revision only after its affected artifacts and relations validate. A routine
feedback response will no longer require a backend to re-emit an entire stage
or every later roadmap artifact.

## In scope

- A feedback-targeted roadmap revision surface that accepts stable feedback
  row ids, resolves their owning stage and targets from the canonical artifacts,
  and rejects unknown, duplicate, incompatible, or reviewer-closed selections
  before a backend call.
- A revision-session model that derives the minimal affected artifact
  collections and their dependency order from canonical row ids and declared
  relations. The model receives the selected feedback, target collection,
  immutable dependency summary, and only the context needed to make that
  patch.
- A structured patch contract and deterministic merger. The patch's supported
  operations are a closed set — `create` fixes their exact vocabulary (e.g.
  add/modify/remove a design row, add a feedback response) — and an operation
  outside that set is a gate failure, not a silent no-op. A backend may
  propose changes only to the session's allowlisted collections; the merger
  preserves non-targeted rows, IDs, settled decisions, removals, and feedback
  outside the selected rows. In particular, a row in `awaiting-review` remains
  unchanged unless it is expressly selected and the reviewer has reopened it.
- Validation after each proposed patch and a final cross-artifact gate before
  publication. A parse failure, fence violation, exhausted retry, interrupt,
  or incomplete downstream patch leaves the pre-session canonical artifacts
  intact and leaves derived seeds untouched.
- A reviewable session record that identifies selected feedback, affected
  collections, input/output digests, proposed artifact changes, validation
  results, and any deliberately deferred downstream work. Each successfully
  published session is a small Git checkpoint rather than an opaque full
  regeneration.
- A bounded context policy for roadmap authoring: stable identifiers and
  concise dependency summaries travel between patches; unrelated artifact prose
  and unselected feedback do not. The policy reports context size and selected
  collection counts so an operator can understand why a call is large.
- Migration from the current `--from-stage` re-entry path without weakening
  full-run bootstrap or the read-only roadmap views. The initial four-stage
  roadmap creation path remains available; incremental revision becomes the
  preferred path after feedback exists.

## Architecture

Treat the canonical roadmap files as the source of truth and a revision as a
transaction over named artifact collections, not as a text replacement. The
revision planner owns selection and impact calculation deterministically; the
backend supplies constrained semantic edits, never authority to choose rows or
silently widen scope. A judged call is unavoidable at this one point —
drafting a compliant edit to a selected row requires the same semantic
judgment every existing roadmap stage already performs, and no deterministic
transform can propose it. A patch carries stable row identifiers and supported
operations rather than a complete YAML document. The merger is the sole writer
of canonical artifacts and enforces the allowlist before gate evaluation.

An affected downstream collection receives its own bounded patch request after
its upstream patch validates. Publication is atomic at the revision-session
boundary: either the complete, gate-valid collection set replaces the current
state or no canonical artifact changes. The session does not infer reviewer
approval, delete feedback rows, mutate settled decisions, promote seeds, or
refresh derived seed prose. On successful publication it does mark the derived
drafts of the revision's affected plan IDs stale in the roadmap's seed-state
sidecar — status only, never draft prose — replacing today's blanket
all-seeds invalidation; this per-plan-id staleness signal is what
`roadmap-seed-materialization.md`'s targeted materializer consumes, and that
plan's Deferred section assigns the mechanics here.

The command design must make the distinction clear:

- Existing `--from-stage` remains a broad, authoring-stage re-entry mechanism.
- The new targeted mode is feedback/collection scoped, reports its exact write
  set before invoking a backend, and makes no unselected artifact writable.
- Read-only views continue to render the on-disk canonical artifacts, including
  a review view that shows the selected rows and session outcome.

The plan may choose the final flag or subcommand spelling, but the selection is
explicit and machine-checkable; a generic "revise this roadmap" mode that
silently expands to every open feedback row is not acceptable.

## Out of scope / Non-goals

- Replacing the four canonical roadmap artifacts, their existing gate model,
  or their role as the canonical design record.
- Changing the reviewer-owned feedback lifecycle, auto-accepting proposed
  responses, or using an AWS/IAM/SCM identity as an application-reviewer role.
- Generating, promoting, overwriting, or refreshing roadmap-derived plan seeds;
  that is the sibling effort `roadmap-seed-materialization.md`, which lands
  first — this seed's targeted revision then supplies the per-plan-id staleness
  signal its materializer consumes.
- A general-purpose YAML diff engine, arbitrary human text edits through the
  CLI, collaborative real-time editing, or a new external persistence service.
- Rewriting the full `--from-stage` path merely to share abstractions unless a
  named ownership boundary makes that move necessary.
- Treating model agreement, prose quality, document length, or token count as
  a correctness gate. The binary observable is whether the proposed patch
  changes only its declared allowlist and the resulting canonical artifacts
  satisfy their existing shape and relation gates.

## Allowed behavior changes

- A new explicit targeted-revision command surface and its session artifacts.
- A selected feedback revision may update only the canonical collections that
  the session reports; a successful revision does not rewrite otherwise
  unaffected later stages.
- `awaiting-review` content becomes protected by a deterministic write fence,
  not only by prompt instructions.

## Allowed reorganization

Only a small extraction that gives full-stage and targeted revision paths one
shared, deterministic artifact validation/publish boundary, carved out of
`roadmap.py`'s existing per-stage gate-evaluation loop and `_write_artifact` —
the only code that owns "write this artifact only once its gates pass" today,
and the reason a second, drifting copy of that rule is the blocker a targeted
path would otherwise create. Do not move the artifact schema, gate
definitions, or review views merely to make the new path look uniform.

## Verification

- A selected single feedback row produces requests bounded to its owning and
  genuinely dependent collections; an unrelated row and its prose never enter
  the backend input or output write set.
- Attempts to patch an unselected row, replace an entire document, invent a
  feedback/removal row, alter a settled decision, or alter unselected
  `awaiting-review` content fail before publication.
- Valid multi-collection revisions publish together and pass the existing
  artifact parsers and cross-stage gates; a failure at any point preserves the
  prior files byte-for-byte.
- The initial full roadmap path, `--from-stage`, seed promotion/refresh, and
  all read-only views retain their documented behavior.
- Tests exercise empty/unknown/duplicate selection, incompatible feedback,
  dependency ordering, retry/interrupt recovery, parse and gate rejection,
  context-bound reporting, and Git-clean failure paths without a live backend.

## Stop / defer

File discoveries outside the Outcome in `BACKLOG.md` or `BUG_BACKLOG.md` with
the session evidence that supports them. Do not add arbitrary document-editing,
review workflow redesign, seed regeneration, or new persistence infrastructure
to this effort. If an existing roadmap relation cannot be expressed as a
bounded collection dependency, stop and surface that schema decision instead
of falling back to a silent full-artifact rewrite.
