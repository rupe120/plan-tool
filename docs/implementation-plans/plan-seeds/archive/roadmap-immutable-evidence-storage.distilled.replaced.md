> **Replaced**: this file was superseded by the completed plan at `docs/implementation-plans/archive/2-roadmap-immutable-evidence-storage.md`.
> Preserved here for history; do not edit.

## Overview

This plan adds one internal, filesystem-confined primitive for publishing immutable noncanonical evidence under a configured roadmap directory. Callers provide a validated namespace, an opaque final identifier, and complete bytes; the primitive publishes a durable regular file exclusively or returns durable opaque bytes from an existing record. It owns safe traversal, private staging, durability, cleanup, and deterministic final-entry enumeration, but does not interpret evidence or drive broader workflows.

## Problem statement

Filesystem confinement, no-follow traversal, first-use directory durability, staging cleanup, exclusive publication, and reuser durability form one operating-system-sensitive protocol that future immutable noncanonical evidence consumers would otherwise duplicate. Embedding that protocol in a receipt runner would mix generic storage safety with escalation-receipt semantics, while treating it as a receipt-schema concern would leave correctness in prose instead of a tested helper. The helper is a prerequisite for `roadmap-structural-revision-escalation`, which retains all receipt-specific behavior.

## Architecture

The primitive accepts a roadmap directory, a closed namespace, an opaque final identifier, and a complete byte payload. Namespace and identifier validation rejects separators, traversal, empty values, and names outside the closed caller-provided grammar before filesystem access. The configured roadmap directory is the trusted root, and every owned child is accessed through descriptor-relative no-follow operations.

Each namespace uses an owned non-link final directory containing only regular files whose names match that namespace's final-name grammar. Private staging uses a distinct hidden non-link sibling namespace that final views never enumerate. Creating either directory fsyncs the new directory and its parent before an operation relies on it; links, special entries, unexpected final filenames, and unavailable required storage directories produce `unsafe-storage` without being followed.

Publication writes, flushes, and fsyncs the complete payload in private staging, links the staged file exclusively into the final directory, and fsyncs the final directory. The primitive returns `created` only after the payload, any newly created directory parents, and the final-directory entry reach their durability boundaries. If the final name already exists, it opens only a regular no-follow file, fsyncs that file and its final directory, and returns its bytes as `existing` for caller-owned validation. It never replaces a final name, exposes a partial final record, or assigns domain meaning to existing bytes.

The primitive removes only its own private staging file after success, failure, or interruption. Crash-left staging entries remain quarantined from final enumeration and are cleaned only after no-follow ownership checks. Final enumeration returns safe final records plus entry status and escaped relative location metadata for unsafe entries, never unsafe-entry bytes.

The closed result contract is `created`, `existing`, `unsafe-storage`, `write-failed`, or `interrupted`. Callers map `existing` bytes through their own strict parser and identity checks to domain outcomes such as reuse, collision, or invalid existing evidence. No storage result authorizes a canonical write, backend call, or broader workflow.

## Out of scope

- Receipt schemas, semantic ids, digest selection, feedback/source freshness, lifecycle telemetry, CLI flags, views, and route or handoff decisions remain with domain-specific consumers.
- Canonical roadmap artifact writes, roadmap writer locks, seed-state changes, backend calls, broad stage runs, and multi-file transaction/recovery logic are not part of this storage primitive.
- A general arbitrary-path file API, user-configurable namespace grammar, and a command that publishes raw operator content are excluded because the primitive accepts only closed storage names and has no CLI surface.

## Risks

- **A safe final name follows a redirected ancestor:** descriptor-relative no-follow operations and owned non-link directories keep every hop inside the configured storage root.
- **A completed final file is acknowledged before it survives a host failure:** file and directory fsync boundaries govern `created`, and an existing-record consumer establishes the same boundary before receiving `existing` bytes.
- **Staging contaminates a view or becomes a second evidence store:** staging remains in a separate hidden owned directory, is never enumerated as final evidence, and is cleaned only through ownership-checked paths.
- **Generic storage decides domain validity:** the API returns opaque existing bytes and a storage result; caller-owned validation determines all domain meaning.
- **The supported platform cannot provide the required no-follow or directory-durability guarantees through the project's runtime:** stop with an explicit platform-boundary result rather than weakening confinement or acknowledging creation as durable.

## Testing

Use temporary directories and deterministic failure injection for unit and interleaving tests. Prove that valid creation produces one complete final regular file, two creators yield one `created` and one durable `existing`, and crashes or write failures leave no partial final file.

Exercise every unsafe path shape at each owned boundary: links, special entries, a non-directory namespace, an unexpected final name, traversal/name violations, and a replaced staging entry. Verify first-use parent and final-directory fsync ordering, reuser file/directory fsync ordering, staging cleanup and quarantine, and final-only enumeration. Tests also prove that the helper neither reads caller-chosen paths nor parses or logs caller bytes.

## Acceptance criteria

- A validated namespace/name and complete byte payload produce either a durable `created` final regular file or durable opaque `existing` bytes; no result overwrites a final name or exposes partial final bytes.
- Every owned filesystem hop rejects links, special entries, traversal, and unsafe directory/file shapes before following or reading them.
- First-use directory creation, staging payload, final link, and reuser paths each reach their documented fsync boundary before returning success.
- Final enumeration excludes staging and returns only safe metadata for unsafe final entries; cleanup touches only owned staging files.
- The primitive contains no receipt/feedback parsing, backend invocation, canonical roadmap mutation, CLI surface, or route decision.
- If the supported platform cannot provide the required no-follow and directory-durability guarantees through the project's runtime, the operation stops with an explicit platform-boundary result rather than weakening those guarantees.

## Deferred

- `roadmap-structural-revision-escalation` will consume the primitive for its receipt namespace and map opaque `existing` bytes through its own v1 schema, identity, redaction, source-binding, telemetry, and view contracts.
- Other noncanonical evidence consumers may adopt the primitive only after their own plans establish a closed namespace/name grammar and domain-validation contract.

## Input

This work consumes a configured roadmap directory, a closed namespace and final-name grammar, complete caller-owned bytes, and filesystem facts about owned storage directories. It does not consume feedback, receipt/schema content, canonical roadmap artifacts, relation graphs, source briefs, backend output, or arbitrary caller-selected paths.
