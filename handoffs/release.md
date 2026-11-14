# Release and publication

Public release preparation, versioning, tagging and sanitized publication. Each section below is one change or route in this workstream, ordered by the date it was opened; new work in the workstream appends a section here instead of creating a file (`README.md` § "Naming").

| Section | Opened |
| --- | --- |
| [Public onboarding and release pickup](#public-onboarding-and-release-pickup) | 2026-10-19 |
| [Public-release cleanup decisions](#public-release-cleanup-decisions) | 2026-10-20 |
| [Public-release snapshot implementation review](#public-release-snapshot-implementation-review) | 2026-10-20 |
| [Public-release content snapshot design review](#public-release-content-snapshot-design-review) | 2026-10-20 |
| [Public-release reference ownership](#public-release-reference-ownership) | 2026-10-20 |
| [Sanitized release publication pickup](#sanitized-release-publication-pickup) | 2026-10-21 |
| [Post-1.0 release versioning](#post-10-release-versioning) | 2026-10-22 |
| [Release 1.1.0 preparation](#release-110-preparation) | 2026-10-22 |
| [Release tag publication](#release-tag-publication) | 2026-10-23 |

## Public onboarding and release pickup

*Opened 2026-10-19.*

The sanitized history is published on Bitbucket and GitHub. Internal work uses
Bitbucket. Version 1.0.0 and the skill-focused README are merged into Bitbucket
main; the internal CLI is current. Finish mirror synchronization and release
tagging before treating the 1.0.0 release as fully distributed. Demo refresh is
deferred and does not block that work.

### Current pickup

| Item | Verified state on 2026-10-21 |
| --- | --- |
| Internal source | `git@bitbucket.org:protagona/plan-tool.git` |
| Bitbucket main | `d90b84ef2f7f0eb4e7222f2cc7cecfea9f7f0aa5` — PR #131 merged |
| Version | 1.0.0 in package metadata and lockfile; changelog entry present; PR #130 merged |
| GitHub mirror main | `03cbb6882696edd5114b3d739517a56919400025` — sanitized v0.2.0 release; behind Bitbucket |
| Release tags | `v0.2.0` exists on both hosts; `v1.0.0` is not present in the checked refs |
| CLI/sync clone | `<sync-clone>`, clean on Bitbucket main `d90b84ef2`; global `plan-tool --version` reports 1.0.0 |
| Working clone | `<working-clone>`; current handoff branch `docs/release-handoff-current`, based on merged Bitbucket main |
| Bitbucket protection | Restored according to the owner; independent branch-restriction reads return 403 for missing token scopes |
| Demo branches | All four names on both hosts point to the shared needs-updating notice; content refresh remains deferred |

The [publication record](release.md#sanitized-release-publication-pickup) owns the exact
sanitized release refs, successful readback, recovery paths and clone cutover.
Its v0.2.0 measurements describe that frozen release, not later main commits.
The [demo handoff](docs-and-onboarding.md#demonstration-refresh-pickup) owns the deferred update work.

### Completed release and onboarding work

- PR #129 merges the final content-selection records, primary-folder READMEs,
  durable how-to guidance and the dedicated `docs/demos/` entry point.
- The owner-approved sanitized publication replaces both hosts' main and tag
  histories. Its root is `9c10d74ca970e97c98a4ce6895ebdc0836b668d9`; the initial
  v0.2.0 release commit is `03cbb6882696edd5114b3d739517a56919400025`. The old
  v0.1.0 tag is retired, and recovery bundles are preserved privately.
- PR #130 merges the 1.0.0 version, matching lockfile entry and release notes.
  Its version-bump commit is `e6e9a8e84218`; 57 release tests and the mandatory
  full pre-push suite pass. Dependency pins stay unchanged.
- PR #131 merges skill-focused onboarding. The README leads with assistant
  setup and conversational planning/execution requests, names both audit gates,
  and places direct CLI guidance below. Internal installation uses Bitbucket.
  Changed link targets and compatibility anchors pass; 42 installer/reference
  tests and the mandatory full pre-push suite pass.
- Owner authorship of the policy Markdown/PDF and Apache-2.0 inclusion are
  settled. The policy PDF digest and exact selected-content checks remain in
  the [merged-selection receipt](../docs/evidence/public-release-merged-selection-verification-20261021.json).

### Next actions

1. Use the designated CLI/sync clone to compare both hosts and fast-forward the
   GitHub mirror to reviewed Bitbucket main. Re-read current refs before acting;
   the recorded mirror state is a pickup measurement. Keep one shared root and
   preserve the clone's dual push URLs and ignored sync configuration.
2. Prepare the `v1.0.0` tag from the merged release history and obtain explicit
   authorization before pushing that tag. The earlier history-replacement
   approval covers v0.2.0 publication, not this new tag. Keep the existing
   v0.2.0 release tag. Public visibility and any organization transfer are
   separate actions.
3. Continue onboarding follow-ups #508–#512 and #377, then exercise #515 in a
   fresh consuming repository. #510 owns the walkthrough; #511 owns skill
   installation/refresh guidance. Recheck their tracking state before taking
   work; this handoff does not certify those items complete.

The Slack announcement draft uses the internal Bitbucket URL. No Slack message
is sent. Demo regeneration, a live demo model run, and both demo audit gates
remain outside the current release route.

### Recovery and local conventions

- Private recovery directory:
  `<release-backup-dir>/2026-10-21-pr129`.
  It contains verified host and local-ref bundles, the published candidate,
  exact operation plan, successful results and previous installed skill copies.
- `archive/pre-sanitization-main-20261021` branches and other former-history
  local refs are private recovery material. Do not push or merge them into the
  sanitized history. For additional clones, preserve local work and refs before
  realigning main with the remote.
- Preserve ignored `.local/reconcile-remotes.py` and `REPO_SYNC.local.md`.
  The designated clone owns dual-host synchronization; this working clone's
  origin pushes only to Bitbucket.
- The earlier publication-confirmation branch holds local pickup records that
  are not merged into main. This handoff branch carries their useful records
  forward; do not merge former source-history branches to recover documentation.
- Preserve the unrelated untracked
  `handoffs/2026-10-16-token-ledger-logging-gaps-reverted-attempt.md`.
- The binary-PDF prompt transport issue, false PDF Files-coherence diagnostic,
  onboarding/workflow-consistency issue and #516 cleanup-use-case example are
  follow-ups. Verify their backlog/tracker state before implementation.

When this release route closes, move durable decisions to their canonical
owners and retire pickup records under [the retention rules](README.md#retention).

## Public-release cleanup decisions

*Opened 2026-10-20.*

Preserve these decisions when changing public setup, examples or package metadata.
The cleanup review closes by owner merge of PR #120. Current implementation
review and release actions belong to [the pickup record](release.md#public-onboarding-and-release-pickup).

### Decisions to preserve

- Use Apache-2.0 in LICENSE, package metadata and contributor-facing guidance.
- Select reviewers per PR; keep architect-tier review for contracts and policy.
- Keep organization targets and contributor mappings in ignored local configuration.
  Tracked setup uses generic examples and portable paths.
- Use neutral example identities while preserving fixture correlations and behavior.
  Retain meaningful technical-product references.
- Keep the owner-authored policy PDF aligned with its Markdown source.
- Keep content preparation, distribution/update procedures and consumer onboarding
  as separate work under #513, #514 and #515.

### Check future changes

Check license bytes and package metadata, local-context reads, reviewer rules,
renamed references, policy source/PDF alignment and fixture identity correlations.
Run the affected checks and the full suite when fixture or runtime behavior changes.
Use the [selection record](../docs/evidence/public-release-content-snapshot.md)
for content decisions and the [verification receipt](../docs/evidence/public-release-content-snapshot-verification-20261020.md)
for measured candidate results. Publication remains an explicit owner decision.

## Public-release snapshot implementation review

*Opened 2026-10-20.*

Use merged [PR #123](https://bitbucket.org/protagona/plan-tool/pull-requests/123) to
review the accepted content-preparation decisions. The merged selected bytes
match the independently tested prose candidate. Current next
actions belong in [the pickup record](release.md#public-onboarding-and-release-pickup).

### Review map

| Area | Property to check |
| --- | --- |
| Selection record and receipt | Exact selected files, report exclusions, useful conclusions and honest verification limits |
| Governing documents | The same provenance judgment in both authorities, using reports, decisions, code and tests; uncertainty does not justify structural rework |
| Policy source and PDF | Owner-approved content, matching text, current tool references and unchanged governance rules |
| Reference repairs | Correct live targets and complete explanations, with findings and closure labels preserved |
| Backlog and coordination | #513 content preparation is complete; #514 distribution and #515 consumer work retain their own owners |

Most added lines in the selection record enumerate report exclusions. Review the
selection rule and accounting before sampling that inventory. The changes add no
runtime code or test behavior.

### Finding dispositions

| Finding | Disposition |
| --- | --- |
| Omitted report references need explicit edit ownership | Fixed: the 13 consumers belong to step 2, with closure checked in independent verification |
| Live RUNBOOK, arc and planning-detail links point at moved files | Fixed: 28 navigation occurrences use existing canonical targets |
| Guidance and compressed ledgers do not carry enough decision context | Fixed: keep the explanation, evidence, disposition and closure needed to continue the work |
| Fresh test PATH omits Python/backend prerequisites | Resolved as environment setup: expose the snapshot Python and installed executable prerequisites; six focused repros and the full suite pass without source/test edits |
| Implementation acceptance | Owner-merged PR #123; future contract/policy changes retain architect-tier review |

### Verification and closure

The [2026-10-20 receipt](../docs/evidence/public-release-content-snapshot-verification-20261020.md)
identifies the exact candidate: ordinary frozen installation succeeds; 573 focused
tests and 14,697 full-suite tests pass, with 67 existing skips. PDF verification
covers all five A4 pages, extracted text, title metadata and URL annotations.
Selected bytes remain unchanged after checks.

The plan-canonical post-run sweep reports no code steps to reconcile. Independent
local reviews find no actionable regressions; local review closure is converged.
Publication remains a separate owner decision.
Documentation revisions require a new candidate identity and appropriate checks;
the receipt's measurements continue to describe only its named bytes.

## Public-release content snapshot design review

*Opened 2026-10-20.*

Use this record when checking the content-selection contract or diagnosing a
planning-workflow issue. The six-step plan supplies content selection, reference
repair, policy alignment, independent verification and backlog reconciliation.
Current release actions belong in [the pickup record](release.md#public-onboarding-and-release-pickup).

### Contract to preserve

- Select content explicitly and keep useful conclusions in maintained documents.
- Keep content digests tied to the bytes they identify; report summaries do not
  inherit captured audit qualification.
- Make guidance self-contained and preserve the judgment rules in both governing
  documents.
- Verify a candidate in an independent repository and environment.
- Keep rights decisions, technical checks, architect review and publication
  authority distinct.

### Findings and dispositions

| Finding | Disposition and useful conclusion |
| --- | --- |
| Shared guidance lacks the same provenance-check route as project guidance | Fixed: step 3 covers both governing documents and preserves the distinction between a bad prior fix and structural recurrence |
| PDF declared in step files appears unmentioned | Refuted: the detail names the PDF twice; the filename extractor excludes the `pdf` extension. Do not alter accurate prose merely to silence this diagnostic |
| Binary PDF enters argv during detail authoring | Tracked: inspect binary artifacts through extracted text and rendered pages; the transport fix belongs to separate tool work |
| Generated detail references resolve beside the wrong owner | Fixed: local targets point to their actual repository owners; all six details parse |

The 2026-10-20 bare audit has zero conceptual findings at 0/6 detail coverage.
The final detail audit has zero conceptual findings at 6/6 coverage and
`confirmed-dry` coverage; its overall result is `awaiting-human-action` because of
the false PDF diagnostic. Preserve that distinction when interpreting a result:
a completed process and a clean audit are different claims.

### Review use

Read [the plan](../docs/implementation-plans/archive/2-public-release-content-snapshot.md),
its details and the [maintained conclusions](../docs/evidence/public-release-content-snapshot.md#applied-dispositions-and-retained-conclusions).
Treat audit measurements as evidence about their named inputs. Review changed
plan content again before a new implementation; use code reconciliation and
implementation review after execution. Do not re-audit unchanged text merely to
obtain a different label for a known diagnostic.

## Public-release reference ownership

*Opened 2026-10-20.*

Use this record to preserve the selection-to-verification dependency. Step 2 owns
all 13 document consumers of omitted report captures, within its 18-file footprint.
Step 5 requires their reference closure before claiming candidate verification.
The plan keeps six steps; content selection, rights and runtime contracts remain
separate responsibilities.

### Review checklist

- Each affected reader receives the conclusion or procedure it needs in maintained
  content, with decisions and measurement limits intact.
- Local links resolve to the selected target; source labels are not presented as
  commands readers must execute.
- New dependencies outside the declared footprint receive an explicit disposition.
- Completion claims describe actual artifacts and checks, rather than relying on
  a green step label alone.

The 2026-10-20 detail-grounded correction audit reports zero conceptual findings,
`confirmed-dry` coverage and no budget limit. The known false PDF coherence
advisory remains separately refuted in the
[design review](release.md#public-release-content-snapshot-design-review).

### Execution rule

When a reviewed correction requires repeating completed work, use explicit step
selection and preserve completed-step history. Do not reset statuses or use
code-canonical `reconcile-plan` to redefine executed intent. The reference repairs
and their verification are recorded in the
[selection record](../docs/evidence/public-release-content-snapshot.md) and
[verification receipt](../docs/evidence/public-release-content-snapshot-verification-20261020.md).

## Sanitized release publication pickup

*Opened 2026-10-21.*

### Status and authorization

**Publication is complete on both hosts, 2026-10-21.** The owner-approved
atomic updates succeed on Bitbucket and GitHub. Full advertised head/tag
readback confirms the approved object IDs below for the initial sanitized
release. The annotated v0.2.0 tag names that release, v0.1.0 is absent, and the four
demo branch names share the needs-updating notice. Later reviewed merges can
advance main; use the [current release pickup](release.md#public-onboarding-and-release-pickup)
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

### Exact candidate

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

### Published remote operation

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
branches in the `docs-and-onboarding.md` § "Demonstration refresh pickup" handoff are not publication targets.

### Recovery and checks

Verified recovery bundles and the captured host ref map are in:

`<release-backup-dir>/2026-10-21-pr129`

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

### Local clones and future work

The 2026-10-21 cutover aligns both local main branches with the initial
sanitized release `03cbb6882696edd5114b3d739517a56919400025`. Current heads
and installed versions are tracked in the release pickup. The designated clone is
`<sync-clone>`; its Bitbucket and GitHub push
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
Use the [release handoff](release.md#public-onboarding-and-release-pickup) for the
broader release route and the [demo refresh handoff](docs-and-onboarding.md#demonstration-refresh-pickup)
only when the deferred demo work resumes.

## Post-1.0 release versioning

*Opened 2026-10-22.*

| Item | Record |
| --- | --- |
| Base | `e151ce4d9`, merged PR #145 |
| Branch | `feat/post-1-release-versioning` |
| Scope | User-requested enhancement of the version increment process |
| Route | Bounded release-script/category-policy update |
| Current state | Complete: 15,135 tests pass; two independent reviews converge with no correctness defects |

### Property and pre-edit sites

Invariant: pending fragments deterministically select a post-1.0 patch/minor/major release; explicit Breaking notes force major after 1.0 and minor before 1.0. Existing --minor raises only patch, never lowers major. A preview names the categories/fragments driving its choice; actual collection retains Breaking notes. Existing clean-tree/tag/ancestry/collision and rollback guards remain.
Identifier search: derive, next_version, cut, MINOR_CATEGORIES/PATCH_CATEGORIES and --minor in scripts/release.py; mapped-category and 1.0-refusal tests; fake_tools's pre-1.0 lock regex. Update category registry, bump precedence/reset, remove post-1.0 refusal, and make fixture tools support all numeric versions.
Vocabulary search: six categories/below 1.0/1.0 and later/bump rule in release.py, docs/RELEASING.md, changelog.d/README.md and pyproject scriv.categories. Update the live policy, both normal/manual routes, refusals and the deliberately-not-decided table.
Design: one visible '### Breaking' fragment category is explicit breaking-change metadata and is collected into release notes. No prose classifier, hidden sidecar or automatic tag/push; maintainers mark incompatible CLI/artifact changes. Other categories retain compatible minor/patch meaning. Format versions remain separate; script does not infer compatibility from them.
Excluded: cutting the 1.1 release, creating/pushing tags, remote synchronization, package publication, prerelease/build metadata, dependency churn, unrelated release-script hardening. Add post-1.0 success/dry-run/major-precedence/reset/rollback and pre-1.0 carve-out tests; preserve all prior safety guards.

The visible Breaking category is the sole new compatibility declaration. The
script does not judge prose or infer whether a change is breaking. The seven
categories are aligned across the script, scriv config, fragment guide and
release guide. Default compatible categories, --minor, dry-run, tag/branch
checks, lock/collection checks and rollback stay on the existing route.

### Verification

The pre-fix run after installing the new fixture contract gives **36 failed,
34 passed**: unsupported 1.x releases, Breaking derivation/collection, major
reset and the six-versus-seven category guard fail as expected. After the
implementation, **74 release tests pass** in 7.21s. Existing refusal/rollback
checks remain green, alongside post-1.0 patch/minor/major, pre-1.0 Breaking,
major precedence with --minor, dry-run immutability and missing Breaking output.

Real **scriv 1.8.0**, run offline in an isolated temporary directory with the
actual updated project config, collects a Breaking+Fixed fragment into a 2.0.0
changelog, retains both headings and their text, deletes the fragment and
retains README. No real project release, tag, push or dependency change is made.

Full suite: **15,135 passed, 67 skipped** in 79.20s. Diff whitespace is clean.
Implementation snapshot: `53c01b562`. `[project].version` remains `1.0.0`;
this task changes the process rather than performing a release.

### Claude Code review 1 and dispositions

Range `e151ce4d9..53c01b5620f44ec18c51b99aaf4e35303d614285`;
actual built-in `code-review` Skill at high effort with independent verification.
Session `7ea0f81e-ab5c-4920-a5a1-d6fde22dbd76`.
No correctness/regression defect. The reviewer reruns **74 tests** in 10.59s;
ruff's configured checks pass. It does not independently rerun the full suite or
real scriv check; those are session-owned results recorded above.

F1 confirmed and corrected: “the six” remains in the release refusal table,
beside the updated seven-category row. A word-boundary search finds that final
stale occurrence; the policy table, fragment guide, script/config registry and
tests align after correction. N1 wrapping/extra-blank-line nits are corrected
without applying whole-file formatting. A runtime AST comparison (excluding
module docstring) against `53c01b562` is identical: no executable statement
changes follow the first review. The targeted suite is rerun after corrections.

Candidates requesting implicit semantic classification, category-order checking
or more overlapping pre-1.0 cases do not show an invariant failure. Category
presence explicitly declares compatibility, pre-1.0 Breaking is normalized to
minor before --minor can raise patch, and category set comparison preserves the
existing collector check. No wider warning/gate is added.

The review briefly detaches/re-attaches HEAD despite report-only instructions.
After it exits, the session independently verifies the same branch and exact
commit, a clean tracked tree, and only the expected untracked handoff. No content
change remains. Final review explicitly forbids checkout/branch mutation.

### Claude Code review 2 and convergence

Range `e151ce4d9..a85b68b1caaa1755a676582932815bc262901134`;
actual built-in `code-review` Skill at high effort plus independent verification.
Session `9693c87b-5f2c-44d8-80bf-be77ea4c416c`.
Clean at correctness/regression level, with an explicit clean/low-yield exit.
The reviewer independently runs **74 release tests** in 7.88s and the full
suite: **15,135 passed, 67 skipped** in 80.33s. Diff whitespace is clean. Its
AST/lint/mutation commands do not complete through its permission layer, so no
independent claim is made for those checks. The session's AST comparison and
real scriv verification remain separately recorded above.

Candidate dispositions: explicit author classification remains the contract;
the pre-1.0 normalization and --minor dominance objections are refuted against
code/tests; the fail-closed unknown-bump branch and tuple grouping are kept.
The handoff headline is closed here after the pending final review completes.
Minor wrap/paragraph placement is advisory; the Breaking policy paragraph is
intentionally separate from the generic fragment-shape bullet. No production
change is required. The second reviewer leaves HEAD/branch unchanged and adds
only its report/test logs under ignored .tmp.

Reviews 1 and 2 give two independent no-correctness-defect passes on executable
snapshot `53c01b562`. The first review's low documentation miss is corrected
before the second; subsequent work is evidence/status only. No material finding
remains, and no actual release, version increment, tag or push is performed.

### Next release prerequisite

The local repository has no `v1.0.0` tag; the release script deliberately retains
its current-tag/ancestry guard. Before cutting the next release, verify the
baseline release commit/tag and obtain the maintainer's go-ahead for publishing
the tag as required by docs/RELEASING.md. Do not bypass the guard or tag an
arbitrary latest main commit. This process update does not create that tag.

## Release 1.1.0 preparation

*Opened 2026-10-22.*

| Item | Record |
| --- | --- |
| Base | `c86c76e7f`, merged release-process PR #146 |
| Branch | `release/1.1.0` |
| Scope | Prepare the next minor release and its review PR |
| Baseline | `v1.0.0` → `968bf5991b75d0f80f8557fb48428444d4395ade`, merge of release PR #130 |
| Current state | PR #147 merged; Bitbucket tags published with explicit approval on 2026-10-23; Jira coverage remains uncertified |

Current publication evidence: [release tag publication](release.md#release-tag-publication).

### Baseline and publication boundaries (preparation record, 2026-10-22)

The 1.0.0 merge has exactly the release version/lock/changelog changes; its
release files match branch commit `e6e9a8e84`, and it is an ancestor of current
main. No remote `v1.0.0` or `v1.1.0` exists on origin at preparation time.
A local annotated `v1.0.0` points to that verified merge, allowing local release
preparation. It is not a tag on latest main or on the 1.1.0 candidate.

Automatic approval review rejects the requested baseline tag push because the
user's “continue” does not explicitly authorize that exact remote publication.
An explicit approval question is pending. No remote tag is pushed, and no
`v1.1.0` tag is created. That tag belongs on the merged release PR commit only
after the maintainer authorizes publication. This working clone has only the
Bitbucket origin; cross-host tag synchronization remains the integration
clone's documented responsibility.

### Release coverage

| Changes since 1.0.0 | Changelog coverage |
| --- | --- |
| PR #137 seed placement, retained legacy destinations, annotate collision protection | Added missing seed-default-location fragment before collection |
| PR #138 corrected run loop help/warnings | Added missing run-iteration-guidance fragment before collection |
| PR #140 preferred step description / accepted legacy title | Existing step-description-alias fragment |
| PR #141 committed test authorship | Existing committed-test-authorship fragment |
| PR #142 validation advice | Existing step-description-diagnostics fragment |
| PR #143 newline preservation | Existing plan-body-newline-preservation fragment |
| PR #144 guarded scope-out recovery | Existing scope-out-rollback-ownership fragment |
| PR #145 H1 preservation | Existing concept-sync-h1-boundaries fragment |
| PR #146 post-1.0 release process | Existing post-1-release-versioning fragment |
| PRs #131–136, #139 and associated handoffs/plans | Documentation/skill-recipe/example or plan-only changes; no fragment required by changelog.d/README.md |

The inventory is grounded in first-parent merges and source diffs since the
1.0.0 baseline. The release adds notes for shipped behavior; no runtime code
is changed. Step-description compatibility/format-v1 decisions remain settled.

**Jira coverage is not certified.** Two configured Atlassian MCP searches for
Done IPPT tickets resolved since 2026-10-21 fail with: “You don't have permission
to connect via API token. Please ask your organization admin for access.”
No Jira record is read or modified. Release readiness still needs the ticket/
fragment check from docs/RELEASING.md, or an explicit maintainer waiver based on
the repository inventory. Keep the release PR draft while this is unresolved.

### Artifact verification

Preparation commit `096716dd0` adds the two missing fragments. The reviewed
script's dry run selects **1.0.0 → 1.1.0, minor**, listing the Added, Changed
and Fixed fragments. Its real run creates commit `8f61ca722` (`Release 1.1.0`).
Nine fragments are collected into the 2026-10-22 1.1.0 section; only README
remains in changelog.d. A captured pre-collection inventory verifies every
fragment bullet survives whitespace-normalized comparison against that section.

`pyproject.toml` and plan-tool's uv.lock entry both read **1.1.0**. The lockfile
is byte-identical to main except that own-version line: no dependency churn.
`uv run plan-tool --version` prints **plan-tool 1.1.0**. Prior release notes
remain beneath the new section. Review results follow on completion.

### Tests

- `uv run pytest tests/ -q -n auto`: **15,136 passed, 66 skipped**.
- `uv run pytest tests/test_release.py tests/test_cli.py -q`: **468 passed**.
- Package-version and CLI version-flag classes in `tests/cli/test_cli_parser.py`: **14 passed**.


### Claude Code review convergence

Both reviews use the actual built-in `code-review` Skill, report-only, with
`claude-sonnet-5-5 --effort high`, over the complete release range
`c86c76e7f..8f61ca7223221809c4fd3e3a565f72ab67c1810d`.

Round 1 session: `72959248-d722-4d47-b665-00b5bf81dc58`. Its completed
consolidation finds no introduced artifact defect. Five candidate points are
triaged: the step-description compatibility decision is settled; naming the
old seed destination is optional wording; the newline bullets describe distinct
paths; unavailable ticket keys are part of the unresolved Jira check; and the
release-tooling feature can use Added. No release artifact change is required.
The reviewer independently runs the full suite: **15,136 passed, 66 skipped**.
Its scratch report retains a test placeholder because its Edit tool is denied;
the completed session output and test log supply that evidence here.

Round 2 session: `31d80a7a-a705-40cf-83bc-a569762ca6f1`. The independent
completed review finds no introduced artifact defect; it verifies the existing
logs and runs 14 version tests successfully. Its report incorrectly counts ten
bullets: the actual collected section contains **eleven** (Added 1, Changed 2,
Fixed 8), because seed-default-location also spans Changed and Fixed. The
source-fragment comparison and first review establish full preservation.
Compatibility classification remains the recorded owner decision; ticket-key
mapping remains part of the unresolved Jira check. No artifact edit is needed.

Two independent completed reviews therefore converge for the release artifacts.
This does not certify release publication readiness. The review branch can open
as a draft with Jira coverage and remote baseline-tag approval still pending.

## Release tag publication

*Opened 2026-10-23.*

The release script supports explicit `--publish` on clean, merged `main`,
with `--remote NAME` and `--dry-run`. Preparation does not publish. The command
checks the exact destination main ref, version/lock/changelog agreement and
absence of fragments, then creates an annotated tag when absent, pushes only
that release ref and reads it back. Matching existing tags are preserved;
conflicting tags are never overwritten. A failed push/read-back retains the
local tag for retry. The destination must have one push URL.

Publication targets current main, so the operator runs it immediately after
the release merge. It does not infer a release PR from history or certify
Jira coverage/approval. Each host requires separate publication.

### Verified release tags

On 2026-10-23 the user explicitly approves creating and publishing both tags.
The push and read-back verify Bitbucket `v1.0.0` peels to
`968bf5991b75d0f80f8557fb48428444d4395ade` and `v1.1.0` peels to
`8a92bb504670a7d1a8c2daf2a746e0339e9e63ee`. The pre-push suite passes.
This resolves the prior tag-publication approval block; Jira coverage remains
uncertified as recorded in the 1.1.0 release handoff.

### Sites and review dispositions

Invariant: publication changes only the current release tag, at the verified
main commit, and leaves existing matching tags untouched. Identifier searches
for `tag`, `push` and `main`, plus vocabulary searches for `never tags`,
`tagging and pushing`, `script never` and `tag the merge commit`, identify
`scripts/release.py`, `tests/test_release.py` and `docs/RELEASING.md`. Those
sites and the new changelog fragment carry the feature.

Initial reviews target `8a92bb504..4c5fcdbad`, using the actual built-in Claude
Code `code-review` Skill with `claude-sonnet-5-5 --effort high`.

Round 1 session: `3ac73c7a-da51-4bc4-8a05-e6518dd007b9`.

Round 2 session: `fe4e08dd-15c3-44b6-94ca-cb7abcfbda23`.

The first review confirms the annotated-tag promise is too broad for existing
lightweight tags, and the usage line omits publication. The correction preserves
the no-overwrite invariant, clarifies existing-tag reuse and adds both local
and remote lightweight-tag tests. The exact-main-ref advisory is confirmed
as a contract gap: suffix matches must not substitute for `refs/heads/main`.
The correction selects that exact key and adds a decoy-ref regression. CLI
flag combinations and failed read-back also gain tests.

Other candidates are declined as requirements beyond this bounded change
(release-commit inference), refuted by the intended snapshot semantics
(main advancing after validation), or retained as non-defect advisories
(network-check ordering, minor subprocess repetition, extra optional test
cases). The two same-function tag reads do not introduce a duplicate-function
consolidation task. Existing tests pin the intentionally accepted tag reuse.

### Verification

- Initial release tests: 86 passed; full suite: 15,147 passed, 67 skipped.
- Corrected release tests: 92 passed.
- Mutation in an isolated scratch copy removes the main identity check; the
  main-drift regression fails as expected. Production code remains untouched.
- Final full suite: **15,153 passed, 67 skipped**.
- Two independent final reviews find no confirmed defects at
  `84877af538932085f1c914a7466511dffb56727a` (range `8a92bb504..84877af53`).
  Both invoke the actual built-in Claude Code review Skill. Round 3 also
  re-runs all 92 release tests successfully. Advisory output is low-yield;
  no additional change is needed for the bounded publication contract.

Final round 3 session: `adc64c7e-7e95-4bfc-a735-6bd20236338e`.

Final round 4 session: `027ce2c2-d0f1-423c-8f57-506faec0e9df`.

Final candidate dispositions retain current-main targeting and matching-tag
reuse as documented contracts. A later main advance correctly refuses a stale
local tag. Option-like remote names fail closed in Git; malformed Git stdout
is hypothetical. Additional parser consolidation, preview wording and optional
refusal fixtures are advisory, not evidence of a publication defect.

The feature commits and this evidence are local on `feat/release-tag-publication`;
no feature branch is pushed and no feature PR is opened by this task.
