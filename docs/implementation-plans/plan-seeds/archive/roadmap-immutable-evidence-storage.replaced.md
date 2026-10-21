> **Replaced**: this file was superseded by the completed plan at `docs/implementation-plans/archive/2-roadmap-immutable-evidence-storage.md`.
> Preserved here for history; do not edit.

# Plan seed: Roadmap Immutable Evidence Storage

## Outcome

`plan-tool` will provide one internal, filesystem-confined primitive for
publishing immutable noncanonical evidence under a configured roadmap
directory. A caller supplies a validated namespace, final opaque identifier,
and complete bytes. The primitive will create or open only an owned non-link
directory, stage bytes outside the final namespace, publish a complete regular
final file exclusively, and establish the documented durability boundary before
returning a creation or reusable-existing result. It will never parse receipt
content, choose a route, write a canonical roadmap artifact, invoke a backend,
or expose a CLI command by itself.

## Why this is separate work

Filesystem confinement, no-follow traversal, first-use directory durability,
staging cleanup, exclusive publication, and reuser durability are one
cross-cutting mechanism. They are not escalation-receipt semantics. Keeping
them inside a receipt runner forces every future immutable noncanonical record
to duplicate an operating-system-sensitive protocol, while treating them as a
receipt schema makes correctness depend on prose rather than a tested helper.

The helper is a prerequisite for
`roadmap-structural-revision-escalation`; that plan retains receipt selection,
schema validation, semantic identity, source freshness, redaction, lifecycle
events, and views. The helper receives bytes and safe storage names only. It
does not know a feedback selector, semantic id, receipt field, or route class.

## Architecture

The primitive accepts a roadmap directory, a closed namespace, an opaque final
identifier, and a complete byte payload. Namespace and identifier validation
reject separators, traversal, empty values, and names outside their closed
caller-provided grammar before filesystem access. It opens the configured
roadmap directory as its trusted root, then uses descriptor-relative no-follow
operations for every owned child.

For each namespace, final records live in a non-link directory containing only
regular files whose names meet that namespace's final-name grammar. Staging
lives in a distinct hidden non-link sibling namespace that views never
enumerate. First creation of either owned directory fsyncs the new directory
and its parent directory before an operation relies on it. A link, special
entry, unexpected final filename, or unavailable required storage directory is
an unsafe-storage result; the primitive never follows it.

Publication writes, flushes, and fsyncs the complete byte payload in private
staging, then links that file exclusively into the final directory and fsyncs
the final directory. A `created` result is available only after the payload,
new-directory parents when applicable, and final-directory entry reach their
durability boundaries. On an existing final name, the primitive opens only a
regular no-follow file, fsyncs it and its final directory, and returns its
bytes as a durable existing record for the caller to validate. It never
replaces a final name, exposes a partial final record, or interprets existing
bytes as equal, stale, malformed, or routable.

After every success, failure, or interruption, the primitive removes only its
own private staging file. A crash-left staging entry is quarantined from final
enumeration and is cleaned only after no-follow ownership checks. A caller's
view lists final namespace entries only; it receives entry status and escaped
relative location metadata for unsafe entries, never their bytes.

The result contract is closed: `created`, `existing`, `unsafe-storage`,
`write-failed`, or `interrupted`. A caller maps `existing` bytes through its
own strict parser and identity check to domain outcomes such as reuse,
collision, or invalid existing evidence. No result authorizes a canonical
write, backend call, or broader workflow.

## Input

This work consumes a configured roadmap directory, a closed namespace and
final-name grammar, complete caller-owned bytes, and filesystem facts about
the owned storage directories. It does not consume feedback, receipt/schema
content, canonical roadmap artifacts, relation graphs, source briefs, backend
output, or arbitrary caller-selected paths.

## In scope

- A small internal storage API, typed closed result contract, and deterministic
  final-entry enumeration suitable for noncanonical evidence consumers.
- Descriptor-relative non-link directory/file operations, private staging,
  exclusive final linking, directory creation, durability, cleanup, and
  failure/interruption behavior.
- Unit and interleaving tests for path validation, links/special files,
  first-use durability, final-link contention, reuser durability, staging
  cleanup, and no-partial final records.
- Internal documentation naming the ownership boundary and the rule that
  callers validate returned existing bytes themselves.

## Out of scope / Non-goals

- Receipt schemas, semantic ids, digest selection, feedback/source freshness,
  lifecycle telemetry, CLI flags, views, and route or handoff decisions.
- Canonical roadmap artifact writes, roadmap writer locks, seed-state changes,
  backend calls, broad stage runs, or multi-file transaction/recovery logic.
- A general arbitrary-path file API, user-configurable namespace grammar, or
  a command that publishes raw operator content.

## Risks

- **A safe final name follows a redirected ancestor:** descriptor-relative
  no-follow operations and non-link owned directories keep each hop inside the
  configured storage root.
- **A completed final file is acknowledged before it survives a host failure:**
  file and directory fsync boundaries define `created`; an existing-record
  consumer establishes the same boundary before it receives `existing` bytes.
- **Staging contaminates a view or becomes a second evidence store:** staging
  is a separate hidden owned directory, never enumerated as final evidence,
  and receives cleanup only through ownership-checked paths.
- **Generic storage decides domain validity:** the API returns opaque existing
  bytes and a storage result only; caller-owned validation decides all domain
  meaning.

## Testing

Use temporary directories and deterministic failure injection to prove that
valid creation produces one complete final regular file; two creators yield
one `created` and one durable `existing`; and a crash or write failure leaves
no partial final file. Test every unsafe path shape at each owned boundary:
link, special entry, non-directory namespace, unexpected final name,
traversal/name violation, and replaced staging entry. Test first-use parent
and final-directory fsync ordering, reuser file/directory fsync ordering,
staging cleanup/quarantine, and final-only enumeration. Tests must prove that
the helper neither reads caller-chosen paths nor parses or logs caller bytes.

## Acceptance criteria

- A validated namespace/name and complete byte payload produce either a durable
  `created` final regular file or durable opaque `existing` bytes; no result
  overwrites a final name or exposes partial final bytes.
- Every owned filesystem hop rejects links, special entries, traversal, and
  unsafe directory/file shapes before following or reading them.
- First-use directory creation, staging payload, final link, and reuser paths
  each reach their documented fsync boundary before their success result.
- Final enumeration excludes staging and returns only safe metadata for unsafe
  final entries; cleanup touches only owned staging files.
- The primitive contains no receipt/feedback parsing, backend invocation,
  canonical roadmap mutation, CLI surface, or route decision.

## Deferred

- `roadmap-structural-revision-escalation` consumes the primitive for its
  receipt namespace and maps opaque `existing` bytes through its own v1 schema,
  identity, redaction, source-binding, telemetry, and view contracts.
- Other noncanonical evidence consumers may adopt the primitive only after
  their own plan establishes a closed namespace/name grammar and domain
  validation contract.

## Stop / defer

If the supported platform cannot provide the required no-follow and directory
durability guarantees through the project's runtime, stop with an explicit
platform-boundary result. Do not weaken confinement or acknowledge creation as
durable merely to make a filesystem shape pass.
