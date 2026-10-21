> **Auto-archived**: this plan was swept on 2026-08-27 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Roadmap Immutable Evidence Storage
intent: 'Completed 2026-08-15: `plan-tool` provides one small internal helper for immutable,
  noncanonical evidence. A caller selects a code-owned namespace, supplies its
  sealed opaque final name and complete bytes, and receives either a durable
  exclusive creation result or the opaque bytes already stored under that name.
  The helper will publish through a unique, exclusively created dot-prefixed
  same-directory temporary file, establish file and directory durability before
  it returns any final bytes, and enumerate matching final names in byte order.
  It will never parse receipt content,
  choose a route, write a canonical roadmap artifact, invoke a backend, or
  expose a CLI command by itself.'
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Add minimal immutable evidence publication and enumeration helper
  intent: Give noncanonical evidence consumers one sealed-name helper that
    publishes durable opaque bytes without overwriting a final name, returns a
    race loser's directory-synced existing bytes to its caller, and lists
    matching final names deterministically.
  creates:
  - plan_tool/roadmap_evidence_store.py
  - tests/test_roadmap_evidence_store.py
  complexity: medium
  change_type: feature
  status: done
- id: 2
  title: Document the reduced immutable evidence storage boundary
  intent: Make the minimal storage contract and its deliberately excluded
    hardening mechanisms clear to receipt and future evidence consumers.
  files:
  - docs/ARCHITECTURE.md
  complexity: low
  change_type: non-code
  status: done
  depends_on:
  - 1
  depends_on_notes:
    1: Supplies the closed result contract, exclusive-publication behavior,
      and matching-name enumeration that the documentation describes.
---
# Roadmap Immutable Evidence Storage

## Overview

**Completed 2026-08-15.** This plan adds one small internal helper for publishing immutable
noncanonical evidence under a configured roadmap directory. Callers select a
code-owned namespace, provide its sealed final identifier and complete bytes,
and receive either a durable new final record or opaque bytes from the existing
record. The helper owns exclusive final-name creation, first-writer durability,
race-loser reread, and deterministic matching-name enumeration. It does not
interpret evidence or drive a broader workflow.

## Problem statement

The escalation-receipt workflow needs a stable place to keep opaque evidence
without allowing a later writer to overwrite it. That need is smaller than a
general secure filesystem protocol: receipt consumers already validate each
returned byte through their closed schema, duplicate-member rejection,
semantic-id/digest checks, and strict UTF-8 decoding. A compact helper keeps
exclusive publication and first-writer durability consistent with the existing
`durable_write_text` pattern, while leaving evidence validity with the domain
consumer that understands it.

## Architecture

The helper accepts a configured roadmap directory, one code-owned
`EvidenceNamespace`, a matching opaque final identifier, and a complete byte
payload. Version 1 registers only `ESCALATIONS`, whose final-name grammar is
exactly 64 lowercase hexadecimal characters. A future consumer can add a
namespace only by changing the registry and its tests; callers never provide a
grammar or an arbitrary path. A wrong namespace, final name, or non-byte
payload returns `invalid-input` before evidence storage is opened.

The initial `ESCALATIONS` namespace maps exactly to
`<roadmap-dir>/.plan-tool/evidence/escalations`; later impact-routing work
adds its own code-owned `IMPACT_ANALYSES` namespace through the same registry.
The configured roadmap
directory must already exist. On first use, the helper creates any missing
fixed components in that order; after each successful directory creation, it
fsyncs the new directory and its immediate parent before creating the next
component or returning a final result. A pre-existing namespace directory is
used as-is. This first-use sequence, the final-name grammar, and the registry
are the complete namespace lifecycle; callers never select a directory.

The helper writes a uniquely named
`.<final-name>.<primitive-nonce>.tmp` file in the namespace directory using
exclusive creation. A nonce collision retries with a new name and never opens,
overwrites, or unlinks the colliding temporary. The current call flushes the
temporary and establishes the platform's file durability boundary (`fsync`,
with macOS `F_FULLFSYNC` for the acknowledged bytes), then exclusively links
that temporary file to the sealed final name. A winner fsyncs the namespace
directory before returning `created`. A loser that observes `EEXIST` fsyncs
that same directory before reading and returning opaque bytes as `existing`.
The current call removes only its own temporary in a best-effort `finally`
path. A dot-prefixed temporary from any earlier call is ignore-only: it is not
a final record and no later call unlinks it. The helper never overwrites or
reinterprets final bytes. A read, write, link, or synchronization failure
returns `write-failed` with no success result.

The helper enumerates directory entries whose names match the namespace grammar
and returns their opaque bytes sorted by the raw final-name bytes. Before it
returns any listed record, it fsyncs the namespace directory after taking the
entry snapshot, so a final linked by a concurrent winner reaches the same
directory boundary as an `existing` result. It ignores dot-prefixed temporaries
and every non-matching name. A matching final that cannot be read makes that
scan `write-failed`; the helper does not invent an integrity or quarantine
status. Enumeration validates its namespace through the same registry and
returns `invalid-input` before opening storage when it is wrong. The
implementation may use a no-follow final open as local hygiene when the runtime
supplies it, but this plan does not make that flag, ownership proofs, or a
platform capability gate part of the result contract.

The closed storage result contract is `created`, `existing`,
`invalid-input`, or `write-failed`; enumeration returns only the sorted matching
name/opaque-byte records, `invalid-input`, or `write-failed`. Callers map
`existing` bytes through their own strict parser and identity checks to domain
outcomes such as reuse, collision, or invalid existing evidence. No storage
result authorizes a canonical write, backend call, or broader workflow.

## Input

This work consumes a configured roadmap directory, one code-owned namespace
token, its registry-defined final-name grammar, complete caller-owned bytes,
and ordinary filesystem operation results. It does not consume feedback,
receipt/schema content, canonical roadmap artifacts, relation graphs, source
briefs, backend output, caller-provided grammars, or arbitrary caller-selected
paths.

## References

- [Python 3.13 os — Miscellaneous operating system interfaces](https://docs.python.org/3.13/library/os.html) — Documents hard links, file and directory synchronization, directory enumeration, and the optional no-follow open flag used by the helper.
- [POSIX link and linkat](https://pubs.opengroup.org/onlinepubs/9699919799/functions/link.html) — Specifies exclusive hard-link publication and `EEXIST` race handling.
- [Linux fsync(2) manual page](https://man7.org/linux/man-pages/man2/fsync.2.html) — Explains the file and containing-directory durability boundary for a new final name.
- [Apple fsync(2) manual page](https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/fsync.2.html) — Documents macOS `F_FULLFSYNC` for acknowledged file bytes.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Receipt schemas, semantic ids, digest selection, feedback/source freshness, lifecycle telemetry, CLI flags, views, and route or handoff decisions remain with domain-specific consumers.
- Canonical roadmap artifact writes, roadmap writer locks, seed-state changes, backend calls, broad stage runs, and multi-file transaction/recovery logic are not part of this storage helper.
- A general arbitrary-path file API, user-configurable namespace grammar, and a command that publishes raw operator content are excluded because the helper accepts only closed storage names and has no CLI surface.

### Reduced-scope fence

- **Capability probe and `platform-boundary`** — the helper uses the platform durability call directly; there is no supported configuration where refusing to run beats the `durable_write_text` boundary every canonical artifact already accepts.
- **Cross-process namespace lock** — exclusive create resolves the only real race; scans see a final atomically or not at all.
- **Link-time inode proofs and `nlink` accounting** — they defend only against the same-owner attacker the plan already excludes.
- **Staging recovery state machine** — a crash leaves at most a dot-prefixed temp file the scan never matches; later calls leave it untouched, so it is not a correctness hazard.
- **Unsafe-entry quarantine and percent-encoded locations** — a non-matching name is skipped; consumers validate matching entries' bytes anyway. (`O_NOFOLLOW` on the final open may stay as one-line hygiene, without a gate built around it.)

## Risks

- **A writer overwrites existing evidence:** exclusive final-name linking returns existing bytes to the loser and never replaces the final name.
- **A first use or reported final disappears after a host failure:** the helper establishes every newly created directory boundary, then the temporary file and namespace-directory boundaries before `created`, `existing`, or a listed final returns bytes.
- **A crash leaves temporary data beside evidence:** the temporary name is dot-prefixed, never matches the sealed final grammar, and later calls leave it untouched.
- **A corrupt final passes storage as domain-valid:** storage returns opaque bytes only; every receipt consumer owns strict decoding, schema, and identity validation.
- **One unrelated directory entry hides valid evidence:** scans skip non-matching names and return matching records in byte-sorted order.

## Testing

Use temporary directories and deterministic failure injection. Prove that the
sealed `ESCALATIONS` registry rejects every other namespace, name, and payload
before evidence storage is opened; a valid winner produces one complete final
record; a competing creator gets the same opaque bytes as `existing`; and no
call overwrites a final name.

Verify the fixed first-use directory sequence and its new-directory/parent
sync ordering. Verify file synchronization followed by namespace-directory
synchronization before `created`, `existing`, or a listed final returns bytes,
including macOS's stronger file-sync call. Inject write, link, read, and sync
failures and prove `write-failed` without a success result. Force a provisional
temporary-name collision and prove each concurrent publisher creates a distinct
exclusive temporary, one creator returns `created`, and the loser returns
directory-synced `existing` bytes. Test current-call-only best-effort cleanup
and crash-left dot temporary files: enumeration and later calls leave those
entries untouched without treating them as evidence. Enumeration tests assert
invalid-namespace rejection before storage access, raw-name-byte ordering,
matching names with opaque bytes, non-matching-name skipping, and a matching
read failure. Tests also prove that the helper neither reads caller-chosen paths
nor parses or logs caller bytes. Step 2 verification confirms that
`docs/ARCHITECTURE.md` states this result contract, each durability boundary,
and every reduced-scope exclusion.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — tests cover sealed input validation, durable exclusive
  publication, race-loser reread, temporary-file handling, and enumeration;
  green before completion.
- step 2 (non-code) — verification covers the architecture and scope fence
  against the implemented result contract.

## Acceptance criteria

- `ESCALATIONS` maps to the fixed namespace path under the configured existing roadmap directory; first use creates each missing fixed component and synchronizes it with its parent before any final result. Both publication and enumeration return `invalid-input` for an unregistered namespace before evidence storage is opened; publication also rejects an invalid final name or non-byte payload there.
- A valid publication returns only durable `created` or opaque `existing` bytes; it never overwrites a final name, exposes a temporary file as evidence, or assigns domain meaning to existing bytes. All ordinary storage failures return `write-failed` without success.
- A `created`, `existing`, or listed-final byte result follows the relevant file and namespace-directory synchronization boundary, including macOS `F_FULLFSYNC` for acknowledged file bytes.
- Every temporary name is created exclusively for one call; retrying a nonce collision never touches another temporary, and only the creating call may best-effort unlink its own temporary. Crash-left temporaries remain ignored non-evidence.
- A competing creator synchronizes the sealed final directory, then re-reads and returns opaque bytes as `existing`; caller-owned comparison decides reuse, collision, or invalid evidence.
- Enumeration returns only grammar-matching final names with opaque bytes in raw-byte order, skips every other name, returns `invalid-input` for an unregistered namespace, and reports an ordinary matching-entry read failure as `write-failed`.
- `docs/ARCHITECTURE.md` documents the four-result storage contract, first-use and returned-byte durability boundaries, and the complete reduced-scope fence for this helper.
- The helper contains no receipt/feedback parsing, backend invocation, canonical roadmap mutation, CLI surface, route decision, capability gate, lock protocol, inode/link-count protocol, recovery state machine, or unsafe-entry quarantine.

## Deferred

- `roadmap-structural-revision-escalation` will consume the helper for its receipt namespace and map opaque `existing` bytes through its own v1 schema, identity, redaction, source-binding, telemetry, and view contracts. Its later re-grounding reduces the prerequisite mapping to `created`, `existing`, `invalid-input`, and `write-failed`.
- Other noncanonical evidence consumers may adopt the helper only after their own plans add and test a new code-owned namespace registry entry plus their domain-validation contract.
