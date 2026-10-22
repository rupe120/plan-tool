# Post-1.0 release versioning

| Item | Record |
| --- | --- |
| Base | `e151ce4d9`, merged PR #145 |
| Branch | `feat/post-1-release-versioning` |
| Scope | User-requested enhancement of the version increment process |
| Route | Bounded release-script/category-policy update |
| Current state | Full-suite verification and Claude Code review in progress |

## Property and pre-edit sites

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

## Verification

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

## Claude Code review 1 and dispositions

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
