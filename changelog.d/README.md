# Changelog fragments

Each change a user of the tool would notice adds one file here, in the same
branch. A release collects the fragments into [`CHANGELOG.md`](../CHANGELOG.md)
and deletes them ([`docs/RELEASING.md`](../docs/RELEASING.md)). This README
stays.

## Name and format

- **Name:** the ticket key, for example `IPPT-123.md`. A change with no ticket
  takes a short slug instead, for example `roadmap-revision-retention.md`. A
  ticket that spans several pull requests keeps one fragment: the first pull
  request adds it and later ones amend it. If a release has already collected
  it, a later pull request adds a new fragment named for the ticket with a
  suffix, for example `IPPT-123-2.md`, that describes only what that pull
  request adds.
- **Body:** one or more category sections, each a bullet list. Write for
  someone who uses the tool, not someone who reads the diff, and name the
  ticket key in parentheses. The categories are Breaking, Added, Changed, Deprecated,
  Removed, Fixed, and Security.

Use `### Breaking` for an incompatible public change, including an incompatible
removal. Explain what changes and how users upgrade. This is explicit release
metadata: it forces major at 1.0 and later, minor before 1.0, and remains visible
in the collected notes. A **Changed** or **Removed** heading alone selects minor;
authors and reviewers must mark incompatibility explicitly.

Example (`IPPT-123.md`):

```markdown
### Fixed

- `plan-tool jira` no longer drops a story whose title contains a colon (IPPT-123).
```

A fragment can carry several categories:

```markdown
### Added

- A `--frobnicate` flag on `plan-tool run` (IPPT-130).

### Changed

- The default audit pass count is now 1 (IPPT-130).
```

## When no fragment is needed

Deliberately no fragment for documentation-only changes, test-only changes, or
an internal refactor with no user-visible effect. Say so in the pull request
description, so the omission reads as a decision and not an oversight, and put
the `no-changelog` label on the ticket. The release check compares the
tickets that need a fragment with the fragments, and the label is what tells
it which tickets to leave out ([`docs/RELEASING.md`](../docs/RELEASING.md)).
