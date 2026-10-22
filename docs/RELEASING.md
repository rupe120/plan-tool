# Releasing

*Part of the plan-tool developer docs. Start at [Contributing](../CONTRIBUTING.md).*

This page says how plan-tool versions are chosen, how a change reaches the
changelog, and how a release is cut. A **release** here is a tagged commit on
`main` plus a changelog entry. plan-tool is installed by `git clone` and an
editable `uv tool install`, so there is no package-index publication. An install
that follows `main` sees every change as it lands. A team that wants a stable build
checks out a tag.

## Choose the version

The version lives in `pyproject.toml` (`[project].version`). The script derives
its next value from the pending fragment categories, with the strongest bump
winning:

| Categories present | At 1.0 and later | Before 1.0 |
| --- | --- | --- |
| **Breaking** | major (`1.2.3` → `2.0.0`) | minor (`0.2.3` → `0.3.0`) |
| otherwise any **Added**, **Changed**, **Deprecated**, **Removed** | minor (`1.2.3` → `1.3.0`) | minor (`0.2.3` → `0.3.0`) |
| only **Fixed** and **Security** | patch (`1.2.3` → `1.2.4`) | patch (`0.2.3` → `0.2.4`) |

At 1.0 and later, compatible features use a minor release and compatible fixes
use a patch. An incompatible public CLI or persisted-contract change must have
an explicit `### Breaking` section explaining the incompatibility and the
user's upgrade action. This section is collected into release notes. Other
categories alone never declare a breaking change: a public removal belongs
under **Breaking** even if it also has a **Removed** entry. The script checks
categories; the author and reviewer judge compatibility.

Before 1.0, breaking changes still use a minor bump and retain their **Breaking**
notes. The script does not promote a 0.x release to 1.0 automatically; the first
stable release uses the manual procedure.

**Formats keep their own versions.** Plan, detail and run-log formats have
separate version constants and evolution rules
([`DATA_CONTRACT.md`](../DATA_CONTRACT.md#version-evolution-policy)). A format
version bump requires at least a minor package release; use **Breaking** when
it breaks the supported compatibility contract. The script does not infer a
format bump from prose. Use an appropriate category or `--minor` to raise a
fix-only release to minor. `--minor` never lowers a major bump.

`uv run scripts/release.py --dry-run` prints the current tag, proposed version,
bump and contributing categories/fragments. It explains the pre-1.0 breaking
exception when applicable, without collecting notes, changing files or
committing. A major bump resets both minor and patch; a minor bump resets patch.

## Record each change

A change a user of the tool would notice adds one fragment to `changelog.d/`
in the same branch. The format, the naming rule, and the cases that need no
fragment are in [`changelog.d/README.md`](../changelog.d/README.md).

Jira carries the same fact from the other side. A ticket that ships a
user-visible change has a fragment named for its key. A ticket that needs no
fragment, or that closed without shipping a change, carries the `no-changelog`
label.

## Cut a release

1. Confirm `main` is green, and that every ticket resolved since the previous
   release has either a fragment or the `no-changelog` label. Two checks cover
   the two facts:
   - **Missing fragments.** List the tickets resolved since the previous
     release without the label:
     `project = IPPT AND statusCategory = Done AND resolved >= <previous release date> AND (labels is EMPTY OR labels != no-changelog)`.
     Take the date from the previous tag (`git log -1 --format=%cs vX.Y.Z`); for
     the first release, use the date the board started. Each listed key needs a
     fragment in `changelog.d/`.
   - **Stale fragments.** A fragment whose key is not in that list is stale or
     mistyped, ignoring a suffix such as `-2`. Check by eye any fragment named
     for a slug instead of a key.
2. On a release branch off `main`, run `uv run scripts/release.py --dry-run` to
   see the derived version and the fragments that force it, then run
   `uv run scripts/release.py`. The dry run makes the tree, branch, tag, and
   fragment checks the real run makes and skips the steps that write, so a
   preview that passes can still fail in `uv` or scriv.

   The real run sets `[project].version`, runs `uv lock` and
   `uvx scriv collect --no-edit --no-add` (so a `scriv.collect.*` git setting
   cannot open an editor or stage files), checks that scriv collected exactly
   the categories it derived the bump from, and commits `pyproject.toml`,
   `uv.lock`, `CHANGELOG.md`, and the deleted fragments as `Release X.Y.Z`. A
   failure before the commit restores those paths to HEAD.
3. Push the branch and open a pull request. After it merges, tag the merge
   commit `vX.Y.Z` (under a squash merge, the new commit on `main`). Pushing the
   tag is a separate step that needs the maintainer's go-ahead; the script never
   tags or pushes.

The script refuses, with a message, in these cases:

| It refuses when | Do this |
| --- | --- |
| The tree has uncommitted changes, `HEAD` is detached, or the branch is `main` | Commit or stash; check out a release branch off `main`. |
| No tag `v<current version>` exists | The current version is unreleased. [Cut it by hand](#cut-a-release-by-hand). |
| That tag is not an ancestor of `HEAD` | Branch from a commit that contains the tag, such as `main` after the last release merged. |
| The tag for the new version already exists | `v<current version>` is not the latest release; check the tags before releasing. |
| The version is not `X.Y.Z` | [Cut it by hand](#cut-a-release-by-hand); prerelease and build suffixes are outside this script. |
| `changelog.d/` holds no fragment | Nothing to release. |
| A fragment is not Markdown, has an unknown category, no category, or text before its first category heading | Fix the fragment; the categories are the seven in the table above and `changelog.d/README.md`. |
| `[tool.scriv].categories` in `pyproject.toml` is not the script's seven categories | Map the new category to a bump in `scripts/release.py`, or restore the seven. |
| scriv's output disagrees with the derived categories, or leaves a fragment behind | The script restores the release paths. Read scriv's parse of the fragments before trusting any bump. |
| `git`, `uv lock`, or `uvx scriv collect` is missing or fails; `uv lock` changes more than plan-tool's own version line in `uv.lock`; `pyproject.toml` is unreadable or has no `[project].version` line | Fix the cause and run again; the script restores the release paths first. For a drifted lock, commit the lock update on its own first. |

If the script cannot restore the release paths after a failure, it prints the
`git restore` command to run before retrying.

### Cut a release by hand

The first release, and any release the script refuses, follow the same steps
without it:

1. Pick the version from the first table and set `[project].version` in
   `pyproject.toml`.
2. Run `uv lock`. It rewrites one line of `uv.lock`, plan-tool's own version.
3. Run `uvx scriv collect`. It merges every fragment into `CHANGELOG.md` under
   the new version heading, reading the version from `pyproject.toml`, and
   deletes the fragments it consumed. `changelog.d/README.md` stays.
4. Commit `pyproject.toml`, `uv.lock`, `CHANGELOG.md`, and the deleted
   fragments as `Release X.Y.Z`.
5. Tag that commit `vX.Y.Z`, with the same go-ahead rule for pushing the tag.

`plan-tool --version` prints a build's version. In a clone it reads
`[project].version` from `pyproject.toml`, so a bump shows without reinstalling
an editable install; `git describe --tags` in the clone adds the exact commit
between releases once a tag exists. The first release has no earlier tag for the
script to start from, so it is cut by hand, and the maintainer chooses its
version: `v0.1.0` or a later one.

## Deliberately not decided

| Not decided | Why |
| --- | --- |
| Publishing to PyPI or an internal index | Installation stays clone-based; a published package needs its own decisions on naming, credentials, and support. |
| Tagging and pushing from the script, or running it from a pipeline | The tag needs the maintainer's go-ahead. A pipeline that pushes a release branch needs a stored access token; add it when a one-click release is wanted. |
| A Fix Version and a `next` release in Jira | The release check above uses resolution dates and `changelog.d/`. Add a Fix Version when someone must ask, after the fact, which release shipped a ticket ([`docs/TRACKING.md`](TRACKING.md#deliberately-not-configured)). |
| Backport branches for old tags | Not needed until a team stays on an old tag; decide when one does. |

## Keep Bitbucket and GitHub synchronized

Use one designated integration clone to synchronize `main` on both hosts.
Working clones can push review branches to the review host. Fetch both hosts
before integrating changes so reviewed work from either host joins the same
history. The designated clone has two `origin` push URLs; other working clones
can retain a single push destination.

For each synchronization:

1. Require a clean integration clone. Fetch each host's `main` separately and
   compare the resulting commit IDs and ancestry.
2. Fast-forward when one tip contains the other. If the tips diverge, review and
   merge locally, then test the resulting commit. Different roots require the
   deliberate snapshot procedure below, rather than an unrelated-history merge.
3. Run the required checks on the exact local commit to publish. Push that commit
   explicitly to each host's `main` using ordinary fast-forward pushes.
4. Read both remote heads back and confirm they equal the tested commit. Two
   pushes are separate operations: if one fails, fetch and compare again before
   retrying. Preserve concurrent remote work; never force a routine sync.

A developer may keep an ignored local helper for comparison, testing and pushing.
Its location and commands belong in that machine's local reminder, rather than a
tracked installation requirement. Release tags need their own explicit pushes
and verification on both hosts; pushing `main` does not publish a tag.

### Prepare the shared sanitized root

The owner-selected release base is one independently verified sanitized root
for both hosts. Maintain shared ancestry after that base so changes from either
host can be merged locally and pushed back to both.

1. Freeze the selected source commit and exact path inventory from the
   [content selection record](evidence/public-release-content-snapshot.md).
   Include reviewed release guidance in a new selection; preserve modes and
   symlink targets. Export into an independent repository with one parentless
   commit, no shared object storage and no source remotes.
2. Inspect the selected files for credentials and client material; retain the
   owner-approved content and rights decisions. Record the scan scope and any
   unresolved findings. Verify exact exported blobs/modes, repository integrity,
   a clean installation and the required tests. Record source commit, selected
   inventory, root ID and results outside the frozen candidate.
3. Before replacing either host's `main`, obtain owner authorization for the
   concrete root and both destination branches. Record current remote heads,
   preserve a recoverable backup, and coordinate a pause in writes. Replacing
   existing branch history requires a deliberate non-fast-forward operation;
   dual push URLs alone do not perform it. Visibility and organization transfer
   are separate owner-authorized actions.
4. After authorized replacement, verify both `main` tips and their reachable
   history against the approved root. Inventory other branches and tags before
   public visibility; changing `main` alone does not remove other published refs.
   Re-clone working copies from the shared base and rebind the installed CLI and
   skills as described in [Install and update](how-to/install-and-update.md).
5. Resume ordinary synchronization on the shared base. Bring any outstanding
   work across as reviewed changes against that base; merging a pre-snapshot
   branch would reintroduce its ancestry. Keep subsequent commits eligible for
   both hosts.

Preparing and verifying the candidate does not replace remote branches or make
repositories public. Keep unresolved destination and verification work in #514
until the reviewed release candidate and operating procedure are complete.
