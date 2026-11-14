# Release tag publication

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

## Verified release tags

On 2026-10-23 the user explicitly approves creating and publishing both tags.
The push and read-back verify Bitbucket `v1.0.0` peels to
`968bf5991b75d0f80f8557fb48428444d4395ade` and `v1.1.0` peels to
`8a92bb504670a7d1a8c2daf2a746e0339e9e63ee`. The pre-push suite passes.
This resolves the prior tag-publication approval block; Jira coverage remains
uncertified as recorded in the 1.1.0 release handoff.

## Sites and review dispositions

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

## Verification

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
