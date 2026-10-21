# Sanitized release publication pickup

## Status and authorization

**Publication is complete on both hosts, 2026-10-21.** The owner-approved
atomic updates succeed on Bitbucket and GitHub. Full advertised head/tag
readback confirms the approved object IDs below for the initial sanitized
release. The annotated v0.2.0 tag names that release, v0.1.0 is absent, and the four
demo branch names share the needs-updating notice. Later reviewed merges can
advance main; use the [current release pickup](2026-10-19-public-onboarding-and-release.md)
for current host tips, installed version and remaining release steps. Demo
refresh stays deferred.

The owner reports Bitbucket main protection restored on 2026-10-21. Independent
API verification remains unavailable: the CLI token's branch-restrictions read
returns 403 for missing privilege scopes. Record restoration as owner-reported;
no further protection change is pending.

The two clean local clones are aligned with the new main. Their previous local
refs are saved in private bundles, and each former local main is retained as
`archive/pre-sanitization-main-20261021`. These archive branches are private
recovery refs and must not be pushed. The cutover refreshes the CLI's editable environment and copied Codex skill
files. Version 0.2.0 verification belongs to this frozen publication record;
the current installed version belongs to the release pickup.

Results and push logs are in `.tmp/public-release-publication.results.json`
and `.tmp/public-release-publication.{bitbucket,github}.latest.push.log`, with
copies in the private recovery directory below. Prior failed attempts are
retained there as provenance; they do not describe the current remote state.

## Exact candidate

- Merged source: `08607a7dbd2de3ad31c849dcc34d175c8b514e06` (PR #129).
- Sanitized root: `9c10d74ca970e97c98a4ce6895ebdc0836b668d9`; 2,610 selected source paths.
- Release 0.2.0 commit: `03cbb6882696edd5114b3d739517a56919400025`. Its parent is the sanitized root.
- Annotated `v0.2.0` tag object: `7533be5f03d0ca489577bcaad1c642888ae93d92`; target is the release commit.
- Shared demo notice commit: `0fc0aa4c6b38e97c3ca37f6b70b6f5f43d9b72bf`; parent is the release commit.
- Local candidate: `.tmp/public-release-0.2.0-merged`.
- Candidate bundle: `.tmp/public-release-0.2.0-merged.bundle`.
- Machine-readable commands and expected tips: `.tmp/public-release-publication.plan.json`.

The release collects 11 pending fragments into the changelog. The only lockfile
change is plan-tool's own version from 0.1.0 to 0.2.0. Locked offline installation
passes, the CLI reports `plan-tool 0.2.0`, and the final tree passes **14,698 tests
with 66 skips in 77.50 seconds**. The working tree remains clean. The bundle
verifies and all candidate refs share the one sanitized root.

## Published remote operation

The following owner-approved updates are applied to Bitbucket
`protagona/plan-tool` and GitHub `rupe120/plan-tool`, with exact-tip leases and
an atomic operation on each host. Both hosts pass post-write readback. The
expected-tip columns retain the operation's recovery baseline.

| Ref | Expected Bitbucket object | Expected GitHub object | Published object |
| --- | --- | --- | --- |
| `refs/heads/main` | `08607a7dbd2de3ad31c849dcc34d175c8b514e06` | `5ecee0880ccc9df4937a5153f7700ba9b0e753fe` | `03cbb6882696edd5114b3d739517a56919400025` |
| `refs/heads/demo/1-seed` | `5de7a9eeed0cbad1e7dccaec48e59ce7d36bcb4e` | `5de7a9eeed0cbad1e7dccaec48e59ce7d36bcb4e` | `0fc0aa4c6b38e97c3ca37f6b70b6f5f43d9b72bf` |
| `refs/heads/demo/2-plan` | `4acc200c9b8e772d84320feae853bd85f43f3beb` | `4acc200c9b8e772d84320feae853bd85f43f3beb` | `0fc0aa4c6b38e97c3ca37f6b70b6f5f43d9b72bf` |
| `refs/heads/demo/3-detail` | `9f9760906b3dad547eae6fbd4cda55fba3463b2b` | `9f9760906b3dad547eae6fbd4cda55fba3463b2b` | `0fc0aa4c6b38e97c3ca37f6b70b6f5f43d9b72bf` |
| `refs/heads/demo/4-jira` | `96109a24f7e0b1f4d74fce4be8b5f7ac4ea67aa5` | `96109a24f7e0b1f4d74fce4be8b5f7ac4ea67aa5` | `0fc0aa4c6b38e97c3ca37f6b70b6f5f43d9b72bf` |
| `refs/tags/v0.1.0` | `9715245b57e9d5f695d9bea068b155fea8939a8b` | `9715245b57e9d5f695d9bea068b155fea8939a8b` | delete |
| `refs/tags/v0.2.0` | `absent` | `absent` | `7533be5f03d0ca489577bcaad1c642888ae93d92` |

The four demo names share the notice commit until a separate demo refresh.
Their previous staged content remains recoverable from private backups. This
choice is included in the owner's publication approval; the local fixture
branches in the demo-refresh handoff are not publication targets.

## Recovery and checks

Verified recovery bundles and the captured host ref map are in:

`/Users/joshrusso/.local/share/plan-tool/release-backups/2026-10-21-pr129`

- `public-release-publication-backup.bundle` covers every advertised current
  branch and tag from both hosts in separate host namespaces.
- `public-release-pre-snapshot-refs-20261021.bundle` also retains the earlier
  cleanup recovery refs.
- `remote-refs.json` records expected remote tips and bundle SHA-256 digests.

Re-read both hosts' full head/tag inventories immediately before any write.
Stop if either differs from the captured map. After each host's atomic update,
read its refs back and compare exact objects. If one host succeeds and the other
fails, report that partial state and preserve both results; do not issue an
unreviewed rollback or relax leases. The verification covers advertised heads
and tags; provider-held PR refs and retained objects are outside that check.
Public visibility and organization transfer are separate operations.

## Local clones and future work

The 2026-10-21 cutover aligns both local main branches with the initial
sanitized release `03cbb6882696edd5114b3d739517a56919400025`. Current heads
and installed versions are tracked in the release pickup. The designated clone is
`/Users/joshrusso/bitbucket/protagona/plan-tool`; its Bitbucket and GitHub push
URLs remain configured. Ignored sync scripts and reminder files retain their
bytes. Cutover checks confirm its editable 0.2.0 installation and matching
user-level Codex SKILL.md and DIRECTIVES.md against that bundled source. Previous installed
skill copies are preserved in private recovery storage.

For additional clones, preserve local work and refs before realigning main with
the new remote history. Do not merge the former root or push private archive
branches into published history. Use the designated clone for dual-host sync.
The documentation confirmation branch starts from the sanitized release and
carries only pickup and receipt updates; its parentage does not reintroduce the
former source history.

This handoff and later verification records are outside the frozen candidate.
Use the [release handoff](2026-10-19-public-onboarding-and-release.md) for the
broader release route and the [demo refresh handoff](2026-10-21-demo-refresh.md)
only when the deferred demo work resumes.
