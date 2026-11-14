# Review remote refs before the shared snapshot

Use this proposal to select the exact branch and tag operations before replacing
both hosts’ `main` with one sanitized root. The observations are dated 2026-10-21;
re-read every target and require its expected old object ID before any deletion
or replacement. This document authorizes no remote mutation.

## Current disposition

The 2026-10-21 owner-approved 23-ref cleanup is complete. Ten additional
merged-work refs and the two retired audit branches are also deleted; one
PR #126 source is already absent. The [completed triage](public-release-outside-commit-triage-20261021.md)
owns the results and subsequent decisions. Keep the four demo stages on both
hosts. The inventories below preserve the pre-cleanup evidence and expected tips;
they are not a list of current remote refs or outstanding deletion requests.

## Proposed sequence

1. Preserve the fetched histories in a recoverable private backup. A local bundle
   passes `git bundle verify`; copy it to durable private storage before relying
   on it for a destructive operation. The working copy is
   `.tmp/public-release-pre-snapshot-refs-20261021.bundle`. Its SHA-256 is
   `0d079533d9ba88251b61dc1dbd7ddfbb12e5a9cde411817db03029e8fa1e552f`.
2. With owner approval, delete the 23 non-main refs in the contained table below.
   Each tip is an ancestor of the observed Bitbucket `main`; these branches add
   no commits beyond that baseline. Keep `main` unchanged during this cleanup.
3. Preserve the 22 non-main refs with outside commits until their owners select
   retention, replay or retirement. Ancestry is not proof of unshipped code: a
   squash merge can ship equivalent changes without making the tip an ancestor.
   Inspect content and active work before choosing which patches to replay.
4. Keep the existing `v0.1.0` tag unchanged during routine branch cleanup. Before
   public visibility, select its disposition explicitly: its current commit belongs
   to the pre-snapshot history. Prefer preserving that release in the private backup
   and using a new release tag on the sanitized history rather than silently moving
   an existing release tag.
5. Settle the outstanding work, freeze the final selected source and verify its
   independent root. The current verified root is a checkpoint; only the pickup
   handoff differs among its selected paths on merged main. The newer verification
   receipt is outside that candidate. Include any later chosen edits explicitly
   before re-verifying.
6. Obtain approval for exact root, both destination tips and all remaining ref
   changes. Coordinate a write pause, apply only the approved operations, and
   verify both hosts against the expected root. Treat public visibility separately.

## Observed baseline

Bitbucket `main`: `b66e09961475be07eb11b76beed94d6483e42c7e`.
GitHub `main`: `5ecee0880ccc9df4937a5153f7700ba9b0e753fe`.
The fetch captures 13 Bitbucket branches and 34 GitHub branches, plus one tag
per host. A new Bitbucket branch appears between initial listing and fetch;
this is why execution must revalidate refs instead of relying on this snapshot.

## Proposed deletions: contained non-main branches

| Host | Branch | Expected old tip |
| --- | --- | --- |
| bitbucket | `docs/handoff-stack-propagation-after-41` | `e4f99e0e3b49c4015c10deab2592cc387d1bdc8a` |
| bitbucket | `fix/candidate-capsule-decision-restore-span-table` | `7da09c54b3cbb8b70dff1caa96fd1acfcb328854` |
| bitbucket | `fix/codex-skill-install-root` | `c520796098ebee4ef165e44c247339512b7f59c3` |
| bitbucket | `plan/roadmap-stack-layer` | `eaf3b74746d56691f2f4e140d6ddb1c643f6a71c` |
| github | `cleanup-completeness-next-steps` | `26976311f4235b4dc33920753b089b578875d3bb` |
| github | `direct/gate-status` | `67afb92203429d12815188d4865122c3ebba388c` |
| github | `direct/run-end-authoring-result` | `5f30862f30d6c3e5dffc563830a9bd1607b501bc` |
| github | `direct/run-end-line-cap` | `c43b463548d18840f1a1a8d28ea9eb1724f88542` |
| github | `direct/run-end-usage-totals` | `4220c004cf5026008bd31b2216a1559143da6c3e` |
| github | `docs/backlog-anchor-and-single-decision` | `59b22f416ea7f71429e321b1f3338005415baa9b` |
| github | `docs/backlog-batch-driver-gaps` | `1208f66f22569d24c62041c8e3490c56fdcee5ad` |
| github | `docs/codex-sol-for-all-work` | `a80c41b47385521ae1d2bc1ee96435ec1471f218` |
| github | `docs/driver-contract-arc` | `bea995fe0cad917603338dec32ee153151729627` |
| github | `docs/roadmap-to-plan-backlog` | `5e9122a47d87b564a0cb3283f3f444cf1630f065` |
| github | `feature/create-fetch-reference-docs` | `c1c3d864a0c93f9d8352ce1d71961946c6a423c8` |
| github | `fence-channel-out-of-scope` | `211f83d156c26a8ca24e6aadcef0a8e1a418c33e` |
| github | `fix/annotate-seed-consume-remaining-work` | `60f2dc0a680e5822e868f4a301f896385e664455` |
| github | `graceful-iteration-failure-and-crash-recovery` | `a10464c96886548e2b7231937df0d6f9347321cf` |
| github | `plan/convergence-actuation-and-surfacing` | `e3aab45455a8d99af8b3b4ed5cd6779a80ef7ab3` |
| github | `pluggable-backends` | `89e5100aa03fc56bf3b46d2d3e42276af1b0c190` |
| github | `roadmap-01-detail` | `139851dcf2eb723774c08582c80b3ba0fcd18483` |
| github | `split-overloaded-prompts` | `d25470b49e877ba7cde13c6c76848c4400c1a70a` |
| github | `worktree-code-review-loop-round9` | `5f0e4e3cb3d2a39664299639ff85bde3e8bcf7e9` |

## Outside commits: retained demos and pending dispositions

Owner decision, 2026-10-21: retain all four `demo/*` stages on both hosts for
demonstrations. Their updates are separate work; they are excluded from deletion.
The [triage record](public-release-outside-commit-triage-20261021.md) owns current
per-branch dispositions.

Counts are reachable commits absent from the observed Bitbucket main, not a
measurement of distinct features or unshipped patches.

| Host | Branch | Outside commits | Expected old tip |
| --- | --- | --- | --- |
| bitbucket | `demo/1-seed` | 2 | `5de7a9eeed0cbad1e7dccaec48e59ce7d36bcb4e` |
| bitbucket | `demo/2-plan` | 3 | `4acc200c9b8e772d84320feae853bd85f43f3beb` |
| bitbucket | `demo/3-detail` | 4 | `9f9760906b3dad547eae6fbd4cda55fba3463b2b` |
| bitbucket | `demo/4-jira` | 5 | `96109a24f7e0b1f4d74fce4be8b5f7ac4ea67aa5` |
| bitbucket | `docs/backlog-run-accept-and-seed-frontmatter-followups` | 1 | `3fa28e6cd1518e6022eece1eb0486e70cc98fdfb` |
| bitbucket | `docs/token-ledger-harness-evidence` | 1 | `747ce72589ba8c28bf524dc792128986377fd727` |
| bitbucket | `fix/audit-next-steps-open-correctness` | 6 | `abf9b1ba6ec9cf9f857fcc1595cb00f3efd8d04b` |
| bitbucket | `test-suite-performance` | 42 | `1b19c94c9559023c4b546297516237de771f6e18` |
| github | `agent/ground-create-synthesis-local-code` | 1 | `607460e87f8c50ed742f2a7118b4859c15b280d1` |
| github | `cleanup/backlog-drift-and-version-flag` | 25 | `f8a4ade90602d45738c1bbfa894b3dafa2ad161d` |
| github | `codex/roadmap-feedback-batch-revision` | 171 | `d9a83a82a943c0c94aa8a81708db9e0c6da1cede` |
| github | `codex/roadmap-stack-aware-approval-seed` | 46 | `39358b73a05fe3cac3e2fa6e5990833ec6416de9` |
| github | `codex/roadmap-structural-approval-handoff` | 60 | `dba3add7498d4a705d98514d699778499094f05c` |
| github | `demo/1-seed` | 2 | `5de7a9eeed0cbad1e7dccaec48e59ce7d36bcb4e` |
| github | `demo/2-plan` | 3 | `4acc200c9b8e772d84320feae853bd85f43f3beb` |
| github | `demo/3-detail` | 4 | `9f9760906b3dad547eae6fbd4cda55fba3463b2b` |
| github | `demo/4-jira` | 5 | `96109a24f7e0b1f4d74fce4be8b5f7ac4ea67aa5` |
| github | `docs/developer-front-door` | 84 | `3f0f23c175d4aa482ae47fc28850926d35ecb14c` |
| github | `fix/backlog-entry-id-uniqueness` | 47 | `bdf21340f2326e685da5943f814a3d20582a0f39` |
| github | `fix/reconcile-all-round-2` | 1 | `e610ef1762219d6a40eff6c41b98a30a7e1b32f4` |
| github | `plan/telemetry-linkage-backfill` | 25 | `9bd85705a2f0cba9803b5a6d0148345e797b98a0` |
| github | `read-only-audit-split` | 1 | `e9108cb18a2ef88e800c12282590d17c345aa06b` |

## Tags

Both hosts expose `v0.1.0` at
`9715245b57e9d5f695d9bea068b155fea8939a8b`. Keep its old history private
if selecting a public sanitized-root-only release.

## Evidence and limits

Classification uses `git merge-base --is-ancestor` and `git rev-list --count`
against the observed Bitbucket main in an independent bare review repository.
All fetched branch/tag tips are preserved under host-qualified refs in the bundle.
Raw listings and classification live in `.tmp/public-release-ref-review.*`.
This covers advertised branch and tag refs, not hosting-provider pull-request
refs, caches, forks, artifacts or backups. Remote ref cleanup alone does not
certify provider-side erasure.

The [candidate receipt](public-release-distribution-verification-20261021.json)
owns the selected content and test results. The [pickup handoff](../../handoffs/public-onboarding-and-release.md)
owns the next action.
