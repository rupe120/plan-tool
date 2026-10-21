# Authored-artifact structure versioning: design and delivery record

Use [PLAN_FORMAT.md](../../PLAN_FORMAT.md), [DETAIL_FORMAT.md](../../DETAIL_FORMAT.md)
and [DATA_CONTRACT.md](../../DATA_CONTRACT.md) for the current format contracts.
This record supplies design decisions, parser edge cases and review findings that
help maintain those contracts. Preserve fail-closed handling, byte identity and
explicit recovery boundaries when changing the readers or writers.

The dated delivery and review sections describe the 2026-09 format-version rollout.
Read each finding with its disposition; a round's pending findings are not the
current project backlog.

## Status

The plan and run-grade detail classes declare their structure version. Maintain
their observable reader/writer contract: a missing declaration reads as version 1;
a supported declaration parses; malformed and unsupported declarations refuse
explicitly. Reading must not upgrade an artifact or synthesize missing content.
Current exact values and compatibility rules belong in the FORMAT documents and
`DATA_CONTRACT.md`.

Preserve these decisions when extending the implementation:

- Keep structure version separate from content revision and accepted-head lineage.
- Use a bounded converter for a demonstrated break; do not introduce a general
  descriptor, slot-inventory or model-assisted migration subsystem.
- Keep raw bytes and failure/recovery behavior explicit. Test refusal routes and
  accepted exceptions as well as successful parsing.
- Give roadmap structure-version work its own scope and re-entry decision; it
  does not follow automatically from plan/detail versioning.

The dated review cases below retain the failure inputs, proposed remedies and
finding dispositions needed to check parser changes. Round-24 findings retain
pending judgments; validate them against current code and tests before treating
them as new work. The project backlog owns current follow-ups. A superseded
round's pending statement is not a current implementation instruction.

The decision record and per-class contracts explain the design. Use the review
cases for concrete parser edge cases, especially wrapper/fence ambiguity,
byte preservation and unsupported-version error routing.

## Decision record

### 2026-09-08 — version and revision are separate concepts

An artifact **version** names the expected structure that a reader and writer
share. An artifact **revision** names a change to its content. They are
separate concepts and must not be represented by one field, one counter, or one
lifecycle.

Roadmap revisions continue to alter roadmap content. They retain the structure
version of the artifact they produce. A later structure upgrade can carry a
revision's content forward into a new structure, but the upgrade does not become
a content-revision mechanism.

The immutable accepted-head roadmap-version store is content and lineage
authority, not a structure-version mechanism. It remains separate. The paused
roadmap-revision-retention route (#242) also remains separate and does not
resume through this work.

### 2026-09-08 — the versioning design is policy, not architecture

A descriptor-driven upgrade architecture was proposed and is **refused**. The
refused proposal gave each published version an immutable format descriptor
file, projected artifacts into a generic content inventory keyed by stable
semantic slot IDs, had a planner emit typed operations against those slots,
admitted a model proposal on an `assisted` route under a human seal, and bound
each publish to an upgrade receipt with digests, route classification, and
interruption resume.

It is refused because it builds a general migration subsystem to avoid a
pairwise-converter chain that the measured change history does not produce, and
because its durability, atomicity, and provenance guarantees are already
supplied by git and by shipped code. Enumerated so a later session does not
re-derive any single piece in isolation:

- **Immutable format descriptors and a descriptor registry** duplicate the
  pydantic model, the FORMAT docs, and `plan_tool/data_contract.py`'s registry.
  A descriptor that points at executable checks is a second source of truth
  against a codebase whose stated rule is that the code wins.
- **Stable semantic slot IDs and a lossless content inventory** trade N-1
  converters for N projectors plus a generic planner, which is more code and
  is itself the ever-changing intermediate schema the proposal warned against.
  Prose is retained byte-for-byte either way, and the frontmatter that slots
  would serve is flat and small.
- **A typed-operation envelope with model proposals, seals, and receipts**
  re-implements the roadmap structural-revision envelope that already ships
  across `roadmap_structural_operations.py`,
  `roadmap_structural_revision_proof.py`, and
  `roadmap_structural_revision_run.py`. Building a parallel one is the
  duplication the consolidation rule in `CLAUDE.md` exists to stop.
- **The `assisted` route** collapses under the proposal's own rule. Work that
  needs judgment to select or interpret prose is re-authoring, which the
  `create` / `detail` / audit pipeline already performs under review.
- **Frozen per-descriptor fixture corpora** duplicate
  `docs/implementation-plans/archive/`, which holds 144 real historical plans.

What the proposal got right is retained as policy below: version is not
revision, reading never upgrades, a bump is judged by observable contract
change, the roadmap is one bundle unit, and **missing information is never
synthesized**.

### 2026-09-08 — the roadmap artifact class is deferred

The four staged roadmap artifacts are **out of scope for #356 entirely**, both
the in-band declaration and any upgrade. Plans and run-grade detail files ship
the declaration; roadmaps do not.

Full context in [Roadmap staged artifacts](#roadmap-staged-artifacts--deferred),
including the two verified code facts that force the deferral and the re-entry
trigger.

## Evidence behind the decisions

Measured 2026-09-08 over the repository's full history, from the initial import
on 2026-05-23. This is provenance for the policy; it is not a gate.

### Structural change rate

| Format | Field or section changes | Additive with a default | Breaking |
|---|---:|---:|---:|
| Plan frontmatter (`plan_tool/schema.py`) | 17 | 16 | 1 |
| Run-grade detail required sections | 0 | 0 | 0 |
| Roadmap staged rows (`roadmap_artifacts.py`) | ~10 | ~9 | 1 |

Two breaking changes in roughly fifteen weeks, across three formats. Both were
absorbed without any migration code:

- **Plan `effort`, deleted 2026-06-08** in commit `071c0a26`, titled "removed
  'legacy' logic since the app is not widely used". `Plan` is `extra="forbid"`,
  so deletion makes any surviving artifact a hard parse failure. No plan on
  disk carries `effort:` today.
- **Roadmap entity `fields`, added 2026-08-02** in commit `4c60b3ab`, as a
  **required** key through `_parse_field_rows`' `_require_key`. All six Integration
  roadmaps carry it today.

The relevant lesson is not that breaks are rare. It is that at this population
a re-authoring pass or a one-off script has twice been cheaper than
infrastructure, and the support window below is what keeps that true.

### Live artifact population

| Repository | Registered plans | Detail files | Roadmaps |
|---|---:|---:|---:|
| `plan-tool` | 36 (plus 144 archived) | 2574 | 0 |
| `integration` | 1 | 6 | 6 |

No other repository on this machine carries a `.plan-tool` manifest. Every
artifact is in git and has one owner.

## The versioning policy

Five rules. Together they bound the live converter chain at length one,
structurally rather than by discipline.

1. **Additive never bumps.** A new optional field or section with a default
   reads as absent under the same version. The reader tolerates absence; the
   writer emits the value. This is how sixteen of the seventeen plan-field
   changes landed, and it is the rule that keeps the common case free.
2. **Only a break bumps.** A break is an artifact valid under N that is invalid
   or means something different under N+1: a rename, a required-field removal,
   a type change, a meaning change, or newly required content.
3. **The support window is current and current-minus-one.** Both are readable;
   only current is writable. A break ships exactly one path forward.
4. **Retire before bumping again.** Version N is retired through a dated,
   user-approved record before N+2 ships. This is the rule that keeps at most
   one converter alive at any time. Reuse the shape of
   [`docs/history/roadmap-evidence-v1-retirement.md`](../history/roadmap-evidence-v1-retirement.md):
   closed roster, inventory, dated approval, fail-closed outcome.
5. **Content the old artifact lacks is a revision, never an upgrade.** A
   structure upgrade may transform existing content. It may not invent absent
   content. Absent content routes to a placeholder plus the existing audit
   channel, or to re-authoring through `create --from-existing`.

## The upgrade process

An upgrade is a frontmatter transform followed by a git commit. **Git is the
rollback and the provenance record**, which is why no candidate file, receipt,
atomic-replace protocol, or resume mechanism appears anywhere below. The
standing rule to commit before every `plan-tool` invocation supplies the clean
baseline that makes this sufficient, and `write_plan`'s compare-and-swap guard
supplies concurrent-edit safety.

### What a breaking bump ships

One commit, containing all of the following. The coverage test fails when the
transform or the registry entry is absent, so the obligation is held by a
failing test rather than by this prose.

- A reader accepting both versions, gating on the declared value **before**
  strict validation.
- A writer stamping only the new version.
- One pure transform, `upgrade_N_to_N1(raw: dict) -> dict`, with no file
  access, no network, and no model call.
- A registry entry mapping every supported version to its path to current.
- Fixtures taken from real artifacts in `docs/implementation-plans/archive/`,
  not synthetic ones.
- The retirement record for the version leaving the support window, per rule 4.

### What the operator runs

Discovery belongs in `list`, which already enumerates registered plans and
already carries an unparseable one as a malformed entry rather than failing.
A version column there is close to free.

```
$ plan-tool list
36 plans; 2 at format version 1, current is 2

$ plan-tool upgrade --all --dry-run
docs/implementation-plans/2-foo.md    1 -> 2   deterministic
docs/implementation-plans/2-bar.md    1 -> 2   placeholder written: risk_profile

$ plan-tool upgrade --all --commit
```

Rollback is `git revert`.

**The absent-content case reuses a shipped channel rather than adding one.**
When a new version requires a field the old artifact lacks, the upgrade writes
the `_(TODO)_` placeholder the formats already define, and the completeness
audit already reports placeholders as findings. The gap surfaces through the
existing review loop. This satisfies rule 5 with no new review state, no seal,
and no new refusal path.

Scope of `--all` is one repository, because plan discovery is per-project
through `locator.py`. A consuming repository lags independently and is safe to
lag by one version, which is rule 3's purpose. Unregistered plan files are
reported and not touched, matching `sweep`'s existing report-do-not-adopt
stance.

**Archived artifacts are deliberately exempt.** Files under
`docs/implementation-plans/archive/` are not upgraded and are not required to
parse under the current version. They are historical records, and the strict
reader path does not walk them.

### Verification

Four binary observables, none requiring judgment:

- the upgraded artifact parses at the new version;
- running the upgrade a second time is an identity operation;
- for plans, the resulting diff touches frontmatter only;
- the full suite passes against the upgraded corpus.

### Not allowed

Enumerated rather than implied:

- Upgrading, inferring, or repairing a version at read time. Reading never
  upgrades; a reader meeting an unsupported version refuses.
- Inventing content the source artifact does not contain.
- Renumbering steps, changing ids, or editing prose.
- Downgrading. Upgrade support is directional and names an explicit target.
- Bumping for prompt wording, prose-quality guidance, or an implementation
  refactor while the observable contract holds.

## Per-class contracts

### Plan

The easy case, and the one that ships first. `parser.py:write_plan`
reserializes frontmatter and takes the body from the current file unchanged, so
a plan upgrade cannot corrupt prose. Its compare-and-swap guard already refuses
a write over a concurrent edit. An upgrade is therefore a pure frontmatter
dictionary transform.

The declaration must be written by the writer rather than carried as a model
default, because `write_plan` dumps with `exclude_defaults=True` and would
silently elide it.

### Run-grade detail

Ships the declaration through a body marker, keeping `DETAIL_FORMAT.md`'s
pure-markdown contract. The marker precedent is
`roadmap_seed_state.py:render_seed_state_marker`.

**Detail should rarely bump.** Its required section set is unchanged since the
initial import. If it does bump, the transform is a heading insert or rename,
and `detail.py` already synthesizes stub headings for a missing required
section. Anything beyond that is re-authoring through `detail`, which is a
revision under rule 5.

A bulk upgrade writes in place and does **not** call
`_archive_existing_detail`; git is the rollback. Archiving 2574 files would
double the corpus. That helper remains the correct behavior for the
interactive re-author path.

### Roadmap staged artifacts — deferred

**Decision: the roadmap class is out of scope for #356. Neither the in-band
declaration nor an upgrade ships. This is deliberate and user-confirmed, not an
oversight or an unfinished edge.**

Two verified facts force it, and the first one rules out shipping even the
declaration alone.

**A stamp is a byte change, and enrolled roadmap versions are bound to exact
bytes.** `roadmap_versions.py` digests raw staged artifact bytes with
`hashlib.sha256(artifact_bytes)` and `_require_content_matches_record` raises
`RoadmapVersionError("stored artifact bytes do not match their record
digests")` on any mismatch. Writing a version declaration into the four staged
artifacts changes those bytes, so every enrolled roadmap's stored digests stop
matching its files on disk. The bare plan's step 4 already names this as an
open question against baseline enrollment's canonical-text check; it does not
resolve it, and it cannot be resolved inside a declaration-only effort.

**A field named `format_version` already ships in the same subsystem, meaning
something else.** `roadmap_source_identity.py` defines
`BASELINE_FORMAT_VERSION = 1` and carries `format_version` on both
`BaselineRecord` and `CanonicalSourceIdentity`, bound to a `stage_key` and
persisted inside escalation receipts and impact analyses. It versions the
**semantic projection** used for baseline identity, not the staged artifact's
on-disk markdown structure. Introducing a second in-band structure version for
the same artifact requires settling the relationship between the two first.
Merging or renaming them for label convenience is explicitly refused.

**Context that makes deferral cheap.** Six roadmaps exist, all in Integration, all
owned by one person. No roadmap format break is pending. The one roadmap break
to date, required entity `fields` on 2026-08-02, was absorbed with no migration
code and every artifact carries the field today. Deferring costs nothing now
and avoids settling a digest-and-lineage interaction under no schedule pressure.

**What deferral does not mean.** The roadmap format is not permanently
unversioned. `ROADMAP_FORMAT.md` remains the owner of the staged contract. The
#328 accepted-head contract is preserved unchanged, and #242 stays paused. This
decision creates no new gate, no new refusal, and no change to any shipped
roadmap behavior.

**Re-entry trigger.** Re-enter when an actual breaking change to a staged
roadmap artifact is needed. At that point open a fresh backlog entry and settle
these three questions before writing code:

1. Whether a structure upgrade republishes the bundle as a new accepted-head
   version whose record marks it structure-only, preserving lineage at the cost
   of one record field; or whether enrolled roadmaps are exempt from upgrade;
   or whether re-enrollment with an accepted lineage break is correct. The
   first is the current recommendation.
2. How an in-band structure version relates to
   `CanonicalSourceIdentity.format_version`, without renaming or merging either.
3. Whether all four staged artifacts must always declare the same version. The
   current recommendation is yes, one bundle version, with a mixed-version
   bundle refusing, because a four-way compatibility matrix is not a policy.

## Consequence for the bare plan

**Done, 2026-09-08.** The plan is revised and validates
(`plan-tool validate authored-artifact-format-version` → `OK`). This section
now records what changed and why, for a session that needs to know the plan's
provenance — it is not a pending to-do.

| Original step | Disposition applied |
|---|---|
| 1, 2 — plan reader gate and writer stamp | Kept unchanged, same ids |
| 3, 4 — roadmap reader gate and writer stamp | **Cut**, per the roadmap deferral to #362 |
| 5, 6 — detail marker, reader, and writer stamp | Kept, renumbered to 3, 4 |
| 7 — register version constants in `data_contract.py` | Kept, renumbered to 5, narrowed from three classes to two |
| 8 — upgrade entry point and coverage test | Kept, renumbered to 6, narrowed to two classes |
| 9 — backlog and `CLAUDE.md` reconciliation | Kept, renumbered to 7; its intent now names that the roadmap follow-up (#362) was carved before this plan started, so deleting #356 on shipping discharges it fully rather than leaving a dangling roadmap promise |

The plan is 7 steps, not 9. Cut steps were not left as gaps in the numbering —
`depends_on` and `depends_on_notes` were renumbered throughout, including the
registry step's dependency list (now `[1, 3]` instead of `[1, 3, 5]`) and the
upgrade-entry-point step's (now `[2, 4]` instead of `[2, 4, 6]`).

Before step 7 deleted #356, its scope contract was narrowed to match: the
roadmap class was carved to **#362** rather than left in Outcome/In-scope, and
its Origin line recorded the 2026-09-08 narrowing with a pointer to this
handoff. **#362** remains its own entry, carrying the two verified code facts
that force the deferral, the re-entry trigger, and its three open design
questions — so a future session re-entering it does not have to re-derive this
handoff's reasoning from a one-line backlog stub.

The plan's `## Overview`, `## Architecture`, `## Out of scope`, `## Testing`,
`## Acceptance criteria`, and `## Deferred` sections were swept for both the
roadmap-class identifiers (steps 3/4, the `ROADMAP_FORMAT.md` reference, the
`roadmap_artifacts.py` file lists) and the vocabulary ("three classes" →
"two classes", "all three readers" → "each reader"), per
`CLAUDE.md` § "Documentation is forward-looking". The `## Overview` and
`## Out of scope` sections additionally gained a short forward pointer to
`BACKLOG.md` #362, rather than silently dropping all mention of the roadmap
class — an absent roadmap mention would read as an oversight, not a decision.

## Disposition of the original design questions

All eleven questions from this handoff's first revision, so none is silently
dropped.

| # | Subject | Disposition |
|---|---|---|
| 1 | What a version promises | Answered: the observable reader and writer contract, per policy rule 2 |
| 2 | What independently bumps each class | Answered by rules 1 and 2; the roadmap half defers |
| 3 | Declaration location and spelling | Answered and shipped: plan frontmatter key and detail body marker |
| 4 | Reader compatibility states | Answered: absent reads as 1; supported parses; unsupported refuses naming both values; malformed refuses |
| 5 | Upgrade interface shape | Answered: library entry point plus coverage test now; the `upgrade` verb ships with the first real break |
| 6 | Which semantic slots to introduce | Moot. No slot layer exists under the refused architecture |
| 7 | Deterministic, assisted, or review-required | Answered by rule 5 and the placeholder channel. No `assisted` route exists |
| 8 | Roadmap revision and accepted-head interaction | **Deferred** with the roadmap class; re-entry question 1 |
| 9 | Bundle atomicity and rollback | Deferred with the roadmap class. For plans and detail, git is the rollback |
| 10 | Analogous persisted `schema_version` contracts | Partly answered: the review sidecar's additive multi-version read is the precedent to follow. `CanonicalSourceIdentity.format_version` is the one that must stay unrelated, and it is re-entry question 2 |
| 11 | Descriptor and fixture retention | Moot for descriptors. Fixture retention follows rule 4's retirement record |

## Next actions

For a breaking authored-format change, name the observable contract change and
provide its raw upgrade path, operator route and coverage under `DATA_CONTRACT.md`.
For roadmap structure-version work, start from the separately scoped re-entry
questions in the decision record. Do not extend a completed plan to absorb it.

Before applying a review case below, reproduce the relevant property against
current code and existing tests. Check that the path is live, preserve deliberate
exceptions, and file unresolved scope decisions in the project backlog.

## Review pass 1 — /code-review high findings (2026-09-09)

**Scope:** `5d9ce9ac..4c74d32e` — the full authored-artifact-format-version
implementation range (steps 1–7, commits `d7a30b1e` through `e6336aa4`) plus
the post-run reconcile-fix commits `127143b0`, `7d44d73e`, and `4c74d32e`.
70 files changed, +5209/-299.

**Method:** a full 10-angle finder pass (5 correctness + 3 cleanup + altitude
+ conventions) against the diff, followed by direct verification of the
strongest candidates against live source. Two investigated candidates were
**refuted** before this list was finalized and are not carried below: the
`format_version: null` handling in `parser.py` is deliberately fail-closed,
pinned by `tests/test_parser.py::test_non_integer_declared_values_fail_closed`;
and a suspected `body=None` crash in `detail.py:_author_step_detail`'s
resumed-checkpoint branch is already guarded by a pre-scan re-validation at
`detail.py:3960-3971` that forces a fresh invoke instead. The review did not
attach a per-finding severity or `[CONFIRMED]`/`[PLAUSIBLE]` tag; it named one
dominant defect class covering findings 1–7 below: this diff adds a new
fail-closed `DetailFormatError` refusal and re-raises it through roughly a
dozen functions whose own docstrings promise "best-effort," "never a raise,"
or "swallows any failure," several with no surrounding handler at the call
site.

### Finding 1

**File:** `plan_tool/completeness_report.py:1642`

**Summary:** `compute_plan_mass_best_effort` re-raises `DetailFormatError`,
contradicting its own docstring's guarantee that it "must never turn an
otherwise-successful completeness audit into a crash"; both call sites are
unguarded.

**Failure scenario:** Running `completeness-audit --iterate` on a plan
completes a multi-round, Claude-consuming audit successfully; if any
already-committed `done` step (not necessarily the one under audit) has a
stray/foreign detail-format marker, `cli/completeness_cmd.py:808` (`--json`
path, no try/except) or the try block in
`cli/completeness_phases.py:5077-5233` (whose `except OSError` does not catch
`DetailFormatError`) aborts, discarding the entire completed report and
sidecar JSON that `completeness-apply` depends on.

**Disposition:** **Confirmed (documentation contract only).** Step 3's selected
acceptance contract explicitly requires completeness mass reads to re-raise
`DetailFormatError` and forbids a partial mass report. The existing
`test_plan_mass_wrapper_propagates_detail_format_error` pins that behavior.
The proposed behavior reversal is rejected; the real defect is the stale broad
wording, corrected in `609ff995`. Ordinary computation failures remain
best-effort.

### Finding 2

**File:** `plan_tool/split_criteria.py:762`

**Summary:** `_read_detail_bodies`'s inserted
`require_supported_detail_format_version` call breaks its own explicit
docstring contract ("A missing or unreadable detail file contributes
nothing … never a raise") and the CLI command's documented always-exits-0
guarantee.

**Failure scenario:** `plan-tool split-criteria <plan>` (documented in
`cli/split_criteria_cmd.py` as "a pure state diagnostic, always exits 0")
exits 1 instead if any single step's detail file has a malformed/unsupported
marker, because the raise propagates uncaught through
`evaluate_split_criteria` into `cmd_split_criteria`.

**Disposition:** **Confirmed (documentation contract only).** Step 3 explicitly
requires `split-criteria` to return its established non-zero command-error
outcome with no partial criterion report for a present unsupported detail. The
proposed behavior reversal is rejected; the real defect is that "always exits
0" overstated input-failure behavior. `609ff995` corrects the helper, CLI help,
README, RUNBOOK, and package-help golden as one vocabulary sweep;
`test_split_criteria_refuses_an_unsupported_detail_marker` pins the refusal.

### Finding 3

**File:** `plan_tool/gates.py:131`

**Summary:** `load_step_details` raises `DetailFormatError` uncaught,
contradicting its own "Best-effort: … is simply absent from the result"
docstring three lines above.

**Failure scenario:** `plan-tool suggest-gates` reads every remaining and
every `done` step's detail body (`gates.py` callers at lines ~351/366); one
unrelated `done` step with a bad marker aborts gate suggestion for the step
actually being worked on, instead of that step's context simply being
omitted as documented.

**Disposition:** **Confirmed (documentation contract only).** The selected
contract distinguishes missing or unreadable detail files, which remain
omitted, from readable unsupported artifacts, which every semantic reader must
refuse. `suggest-gates` is one of the enumerated readers. The proposed behavior
reversal is rejected; `609ff995` fixes the docstring's missing distinction, and
`TestLoadDoneDetails` covers both sides.

### Finding 4

**File:** `plan_tool/detail.py:1996`

**Summary:** `_format_already_implemented_block` (and
`collect_step_grounding_findings` at line 1292) re-raise `DetailFormatError`,
contradicting their own "Heuristic failures are swallowed … detail must keep
working" / "never a gate" docstrings.

**Failure scenario:** Authoring step 30 of a plan
(`plan-tool detail <plan> --step 30`) scans every step's detail body for
already-implemented heuristics/grounding findings; if unrelated step 12 has a
malformed marker, authoring a brand-new, unconnected step 30 now fails
instead of silently degrading.

**Disposition:** **Confirmed (documentation contract only).** Step 3 names both
broad exception boundaries and requires each to re-raise the typed refusal.
Otherwise an unsupported artifact would be interpreted after the plan's
fail-closed gate. The proposed behavior reversal is rejected; `609ff995`
corrects the stale "best-effort" wording while preserving the narrower fallback
for ordinary heuristic failures; `TestDetailFormatVersionAuthoringBoundaries`
pins the split.

### Finding 5

**File:** `plan_tool/cli/authoring.py:2164`

**Summary:** `_run_completeness_tail` re-raises `DetailFormatError`,
contradicting its docstring's "Best-effort: a failure here must never flip
the caller's successful-authoring rc".

**Failure scenario:** `plan-tool detail <plan> --step N` writes step N's file
successfully (rc==0, wrote==True, confirmed at `authoring.py:1848-1854`),
then the automatic post-authoring completeness tail hits an unrelated
sibling step's bad marker and the whole command exits 1 — success output
followed by a failure exit code for a step that had nothing wrong with it.

**Disposition:** **Confirmed (documentation contract only).** The step 3
acceptance contract says an automatic authoring tail re-raises whenever it runs;
only direct targeted recovery with `--no-completeness` skips that tail. Treating
a newly written step as success while a sibling semantic input is unreadable by
this build would publish a partial audit result. The proposed behavior reversal
is rejected; `609ff995` clarifies the docstring, and
`TestDetailTailAuditFollowUp::test_auto_completeness_tail_reraises_detail_format_error`
pins the required outcome.

### Finding 6

**File:** `plan_tool/launcher.py:3594`

**Summary:** `run_all_done_steps`'s per-step loop calls `render_prompt` with
no per-step try/except, so a `DetailFormatError` from one step's detail body
(surfaced via the renderer's new format-version gate) aborts the whole batch
and discards every result already computed for earlier steps.

**Failure scenario:** `plan-tool verify-all` (or a deep reconcile driving
`_run_deep_for_step`/`run_all_done_steps`) processes 20 done steps; step 15
has a malformed marker — the loop raises there, and the `RunResults` already
collected for steps 1-14 are thrown away since `results` is never returned
before the exception propagates.

**Disposition:** **Refuted.** The batch-level no-partial-result behavior
is intentional: a selected unsupported detail refuses the semantic review, so
earlier per-step results must not be returned as a complete batch. The review
did expose a different command-boundary defect: `render_prompt` raised
`DetailGradeError` directly here, unlike `run_step`, so the CLI could report an
unexpected error instead of its established `LauncherError`. `d727976b` adds
that narrow translation and
`TestRunAllDoneSteps::test_detail_render_refusal_is_a_launcher_error`; removing
the catch makes the regression fail with the raw `DetailGradeError`.

### Finding 7

**File:** `plan_tool/cli/completeness_apply_parallel.py:559`

**Summary:** `dispatch_parallel`'s comment claims a `DetailFormatError`
"aborts the batch … never permits a sibling apply," but
`ThreadPoolExecutor.map` submits all tasks eagerly and `__exit__` does
`shutdown(wait=True)` without `cancel_futures`, so sibling worker threads
already running keep executing (burning real claude subprocess calls) even
though their results are discarded.

**Failure scenario:** A parallel completeness-apply batch with `--jobs 4`
dispatches 4 findings concurrently; if the first-completed worker raises
`DetailFormatError`, the other 3 workers' already-started claude calls run to
completion anyway before the exception propagates out of the `with` block —
wasted backend spend the comment implies was prevented.

**Disposition:** **Confirmed (documentation contract only).** `apply_one` runs
in an isolated worktree, and only the later serial replay can apply a candidate
to the canonical tree. The behavior contract promises no sibling canonical
application and no partial apply report; it cannot promise cancellation of
backend work already running when another worker refuses. Adding cancellation
machinery would broaden the change without preventing already-started subprocess
spend. `609ff995` clarifies the production comment and docstring, and the
matching test wording is synchronized in the repair disposition commit:
isolated workers may finish, but none of their disposable changes is published.

### Finding 8

**File:** `plan_tool/detail_artifacts.py:385`

**Summary:** `upgrade_detail_body_to_current` re-derives
`locate_detail_format_carrier` and the marker regex match that
`require_supported_detail_format_version` (called two lines above) already
computed and discarded, causing 4 total `text.splitlines()` calls and
duplicate raw_value extraction for one upgrade call.

**Failure scenario:** Not a crash, but wasted work on every raw-upgrade call:
the carrier/raw_value pair computed inside
`require_supported_detail_format_version` (lines 341-349) is thrown away,
then `locate_detail_format_carrier(text)` and `text.splitlines()` are both
re-run at lines 385 and 395 to recompute the identical values from the same
immutable text.

**Disposition:** **Declined.** This is a micro-optimization without a measured
failure. Validation and transformation deliberately have different return
contracts; returning the reader's private carrier state would widen and couple
their APIs to save a few `splitlines()` calls on one small, operator-invoked
artifact. The current direct code is the smaller implementation and no behavior
or scale criterion requires an abstraction.

### Finding 9

**File:** `plan_tool/detail_artifacts.py:320`

**Summary:** `require_supported_detail_format_version`'s own docstring admits
it duplicates `parser.py`'s `_require_supported_plan_format_version`'s
"resolve-then-check" shape by hand rather than sharing a helper; a third
near-identical copy already exists in `review_persistence.py`'s
`_SUPPORTED_SCHEMA_VERSIONS` check.

**Failure scenario:** A future change to the refusal-message wording or the
resolve-then-check policy must be made in three separate places by hand;
they have already diverged slightly in message text, so a maintainer fixing
one copy can leave the other two stale.

**Disposition:** **Refuted.** These are not three copies of one artifact
contract. Plans use typed YAML frontmatter and `ValidationError`; details use a
fixed Markdown carrier and `DetailFormatError`; saved reviews use an existing
JSON schema version with additive multi-version read semantics. Their shared
"resolve/check" outline is not a mergeable semantic unit. The user-confirmed
design refuses a generic descriptor/migration layer, and step 5 explicitly
keeps the version-only plan/detail registry separate from persisted-dataclass
and JSON-object schemas.

### Finding 10

**File:** `plan_tool/cli/reconcile.py:291`

**Summary:** `_read_selected_run_reconcile_detail` adds format-version
validation and `DetailFormatError`-to-`LauncherError` translation directly in
`reconcile.py`, which repo `CLAUDE.md` explicitly designates a "leaf helper"
that holds "no business logic" — duplicating logic that belongs in
`launcher.py`, the orchestrator that already owns the equivalent translation
for the ordinary detail-read path via `renderer.py`.

**Failure scenario:** The same validation-and-translation logic now exists
in two places (`launcher.py`'s renderer-mediated path and this CLI leaf's own
inline copy); a future change to the translation's wording or behavior is
easy to apply to only one.

**Disposition:** **Refuted.** Step 3 explicitly assigns the selected
run-reconcile preflight to this helper and requires the refusal to surface
through the established `LauncherError`. The format grammar is not duplicated:
the helper calls `require_supported_detail_format_version`; its local
translation is the command boundary beside its existing missing/unreadable
translations. Moving selected-detail resolution into the general launcher
would be a broader refactor and would obscure which reconcile input is being
validated.

### Finding 11

**File:** `plan_tool/detail_artifacts.py:264`

**Summary:** `_INTEGER_LITERAL_RE = re.compile(r"^-?\d+$")` accepts
non-canonical integer literals like `"01"` as valid, silently treating a
malformed marker as the canonical version it happens to equal.

**Failure scenario:** A hand-edited or corrupted detail file with
`<!-- plan-tool:detail-format-version: 01 -->` is accepted as version 1 with
no diagnostic, even though `render_detail_format_version_marker` only ever
emits the canonical `1` — the function's own docstring claims malformed
payloads are "refused rather than defaulting," which does not hold for this
case.

**Disposition:** **Refuted.** The selected marker grammar explicitly defines a
bare `-?\d+` payload and even recommends `re.fullmatch(r"-?\d+", value)`.
Consequently `01` is a valid integer literal whose value is version 1. The
writer emits a canonical spelling, but the reader contract does not impose
lexical canonicality; "malformed" means outside the selected integer-literal
grammar.

### Finding 12

**File:** `plan_tool/detail.py:2282`

**Summary:** `stamp_detail_format_version_marker` rebuilds the whole document
via `body.splitlines()`/`"\n".join(...)`, which normalizes any Unicode
line-separator characters (`\v`, `\f`, U+2028, U+2029, etc.) anywhere in the
body to plain `\n`, contradicting the docstring's claim that "only the slot
itself is rewritten."

**Failure scenario:** An authored detail body containing one of these rare
line-boundary characters elsewhere in its prose has that character silently
collapsed to `\n` on every stamp; the sibling function
`upgrade_detail_body_to_current` in `detail_artifacts.py` deliberately avoids
this by using `splitlines(keepends=True)` with a `_line_terminator()` helper,
showing the pattern this function should have followed.

**Disposition:** **Confirmed.** The invariant is: stamping may normalize the
managed H1/marker slot, while every byte outside it remains the authored body.
Identifier enumeration covered `stamp_detail_format_version_marker`,
`locate_detail_format_carrier`, `_line_terminator`, and the sibling raw upgrader;
the vocabulary sweep covered "touches nothing outside," "byte-for-byte,"
`splitlines`, and line-separator handling. `e067d2ad` now rebuilds from
`splitlines(keepends=True)` and recognizes every separator Python treats as a
line boundary. The new
`TestDetailFormatVersionStamp::test_stamp_preserves_non_newline_line_separators_outside_the_slot`
covers VT, FF, U+2028, and U+2029; restoring the old join makes it fail.

### Finding 13

**File:** `plan_tool/auto_reconcile.py:169`

**Summary:** The fail-closed detection walks only `exc.__cause__` (explicit
`raise ... from exc` chaining), never `__context__`, so it depends on an
unenforced invariant that every wrapping hop in the `DetailFormatError` →
`DetailGradeError` → `LauncherError` chain always uses explicit `from exc`.

**Failure scenario:** If a future refactor of `renderer.py` or `launcher.py`'s
wrapping code drops the explicit `from exc` on one hop (an implicit bare
raise inside an except block still sets `__context__`, not `__cause__`), this
walk finds `cause is None` without ever seeing the `DetailFormatError`, and
the intended fail-closed refusal silently reverts to a best-effort skip with
no test on the chain itself to catch the regression.

**Disposition:** **Refuted.** Every current production hop in this route uses
explicit `raise ... from exc`, and the fail-closed walk deliberately follows
that concrete chain. Renderer coverage pins `DetailFormatError` to
`DetailGradeError`; launcher coverage pins its translation to `LauncherError`;
`test_auto_reconcile_reraises_a_detail_format_caused_launcher_error` pins that
the named cause escapes instead of being skipped. A hypothetical future wrapper
that drops explicit chaining is not a present defect and does not justify
accepting arbitrary implicit context as equivalent provenance now.

### Finding 14

**File:** `plan_tool/annotate.py:228`

**Summary:** `_try_parse_plan` only carves `UnsupportedPlanFormatVersionError`
out of its broad `except Exception: return None`, so any other exception type
from the new version-check machinery (a latent `TypeError`/`KeyError` bug) is
silently swallowed and the input is misreported as "not a plan-tool plan."

**Failure scenario:** A bug introduced later in the format-version resolution
code that raises something other than `UnsupportedPlanFormatVersionError`
would be invisible here — `annotate` would just treat a real plan as rough
notes instead of surfacing `AnnotateError`, unlike every other
`DetailFormatError` call site in this diff which explicitly re-raises.

**Disposition:** **Refuted.** `_try_parse_plan` intentionally accepts arbitrary
rough notes, so its pre-existing broad parse fallback is the feature boundary.
The new gate has one documented named refusal,
`UnsupportedPlanFormatVersionError`, and this change carves that error out into
`AnnotateError` before any backend call. No current alternate exception from the
version resolver reproduces the scenario. A possible future implementation bug
is speculative and belongs with the refactor that introduces it, not in this
bounded format-version change.

### Finding 15

**File:** `plan_tool/cli/inspect.py:613`

**Summary:** `cmd_validate` implements the same "this exception always fails
validate regardless of `--fail-on-findings`" policy twice via two different
mechanisms in the same function: an
`isinstance(exc, UnsupportedPlanFormatVersionError)` check at line 613 for
the plan-level refusal, and a separate `try/except DetailFormatError` at
lines 635-638 for the detail-level refusal.

**Failure scenario:** Not a crash, but a maintenance hazard: a future change
to the exit-code carve-out policy (e.g. relaxing it, or adding a third named
exception) has to be found and updated in two structurally different places
in the same function instead of one shared predicate.

**Disposition:** **Declined.** The two arms run at different phases with
different available state: plan parsing fails before a `Plan` exists, while the
detail refusal arises from the later pointer-backed suppression scan. Both
return the same required exit `1` and are independently covered. A shared
predicate would not consolidate their control flow; it would add indirection to
two already-local typed exception boundaries without changing behavior.

## Review pass 1 triage and repair (2026-09-09)

The 15 submitted findings resolve to 7 confirmed, 6 refuted, and 2 declined.
Six confirmations are contract-documentation defects (findings 1–5 and 7), and
finding 12 is the behavioral defect. Finding 6's investigation also exposed one
adjacent confirmed command-boundary defect.

- `d727976b` fixes the adjacent multi-step review command boundary and adds its
  regression test.
- `e067d2ad` fixes finding 12's outside-slot byte mutation and adds its
  regression test.
- `609ff995` sweeps the best-effort/refusal distinction through every cited
  helper, split-criteria's live user docs, help text, and golden coverage.
- `7e1c5052` refreshes the generated CLI reference after its drift test caught
  the help-text update.

The two new behavioral tests are mutation-checked: removing the launcher catch
reproduces raw `DetailGradeError`, and restoring the old marker join loses all
four covered separators. The focused review surface passes (`96 passed`); the
generated-reference/package surface passes (`54 passed`); and the complete
parallel suite passes (`12384 passed, 189 skipped`). This triage is not a
convergence claim: the next required evidence is a fresh independent review of
`5d9ce9ac..7e1c5052` plus this disposition record.

## Review pass 2 — /code-review high findings (2026-09-09)

**Scope:** `5d9ce9ac..7e1c5052` — a fresh independent review of the complete
cumulative implementation range, per this doc's own "next required evidence"
note at the end of the pass-1 triage above.

**Method:** 10 parallel finder angles plus a dedicated Phase-3 sweep; every
strong candidate was verified live against the working tree (not just read).
The review cross-checked against this same handoff doc's pass-1 findings and
dispositions to avoid re-litigating already-triaged material. Findings 1, 3,
5, 6, 7, and 8 below are genuinely new relative to pass 1; findings 2 and 4
surfaced from tracing the "apply-or-recommend gate" family (`merge_bridge`,
`scope_out_step`) that pass 1's dominant finding class (fail-closed
`DetailFormatError` breaking a "never raises" contract) had not reached. Full
suite is green (`12384 passed, 189 skipped`), consistent with these being
coverage gaps rather than regressions the suite already catches.

### Finding 1

**File:** `plan_tool/detail.py:2231`

**Summary:** The "preserve body bytes while stamping version" fix (commit
`e067d2ad`) only fixed `stamp_detail_format_version_marker`; the upstream
`parse_detail_response` still rebuilds the accepted body via a plain
(non-keepends) `splitlines()` + `"\n".join(...)`, which silently collapses
every non-`\n` line terminator (CRLF, VT, FF, FS/GS/RS, NEL, U+2028, U+2029)
anywhere in the body to `\n` before the stamp function ever runs.

**Failure scenario:** A claude response body containing CRLF or a Unicode
line-separator character anywhere outside the H1 (e.g. a fenced code block
quoting a Windows-style file) loses those exact bytes during authoring.
Verified live: `parse_detail_response("# Title\r\n...` ```\r\nline
one\r\nline two\r\n` ```\r\n...")` returns a body with zero `\r\n` sequences,
and the same holds for `\v`/`\f`. The new regression test
`test_stamp_preserves_non_newline_line_separators_outside_the_slot` never
catches this because it calls `stamp_detail_format_version_marker` directly,
bypassing `parse_detail_response` entirely — so the documented/tested
invariant ("every byte outside the slot remains the authored body") does not
hold for the real authoring pipeline (`_author_step_detail` calls
`parse_detail_response` then `stamp_detail_format_version_marker` in
sequence).

**Disposition:** **Confirmed.** The invariant is that the real authoring
pipeline preserves interior body line terminators before the writer normalizes
only the managed marker slot. Identifier enumeration covered
`parse_detail_response`, `parse_structured_detail_response`,
`stamp_detail_format_version_marker`, and their `splitlines`/join sites; the
vocabulary sweep covered "byte-for-byte," CRLF, line endings, separators, and
"outside the slot." `parse_jira_detail_response` stays unchanged because step
4 explicitly excludes that artifact class. `4a0f57ef` switches the run-grade
parser to `splitlines(keepends=True)` plus an exact join and adds a
parse-then-stamp regression over CRLF, VT, FF, U+2028, and U+2029. Restoring the
old split/join makes that test fail with every separator normalized to LF.

### Finding 2

**File:** `plan_tool/detail.py:6997`

**Summary:** `merge_bridge`'s apply-branch `except (DetailError, OSError)`
does not include the new `DetailFormatError` that `merge_steps` now raises
pre-write (reading a folded member's own detail body), so it escapes
uncaught instead of mapping to the documented
`MergeBridgeResult(outcome="invalid")` the function's docstring promises
("never a raised DetailError").

**Failure scenario:** Verified live with a constructed 4-step plan where the
merge member (step 2) has a detail file declaring
`detail-format-version: 999`: calling
`merge_bridge(merge_ids=[2,3], allow_merge=True, yes=True, ...)` raises
`DetailFormatError` straight out of the function instead of returning a
structured outcome. `plan_tool/cli/review_actions.py:1327` calls
`merge_bridge` with no surrounding try/except as part of the automated
structural-remedy walk dispatcher, so a merge remedy targeting steps with a
corrupted sibling marker crashes the whole review/reconcile walk instead of
being classified `invalid` and continuing to the next finding.

**Disposition:** **Refuted.** `merge_bridge` promises that its own
`DetailError` validation/authoring failures map to structured outcomes; it does
not promise that no typed artifact refusal can escape. `DetailFormatError` is a
separate class by design. Step 3 explicitly requires every review-walk action
handler to re-raise it instead of classifying the failure and continuing, and
`review_walk.py` does so on apply, run, and apply-all paths. Converting this
pre-write refusal to `invalid` would violate the selected fail-closed contract
and hide the declared-and-supported diagnosis.

### Finding 3

**File:** `plan_tool/detail_artifacts.py:347`

**Summary:** `require_supported_detail_format_version` inspects only the
single line at the computed slot index, so a detail body with two
marker-shaped lines stacked immediately after the H1 is validated using only
the first line's value, silently ignoring an actually-unsupported version
declared on the very next line.

**Failure scenario:** Verified live:
`require_supported_detail_format_version("# Title\n<!--
plan-tool:detail-format-version: 1 -->\n<!-- plan-tool:detail-format-version:
999 -->\n\n## Summary\nbody\n")` raises nothing and treats the file as
version 1, even though a second, unsupported declaration (999) sits right
where the writer's own `stamp_detail_format_version_marker` explicitly
anticipates and collapses "stacked proposals." This breaks the feature's
core fail-closed contract ("malformed refuses, it does not default") for a
shape the writer is defensive against but the reader is not.

**Disposition:** **Refuted.** The reader contract assigns meaning to exactly
one line: the first non-blank line after the carrier H1. A marker-shaped line
anywhere else is explicitly ordinary prose, even when it immediately follows a
valid declaration. The writer's defensive collapse of consecutive model
proposals does not expand the persisted reader grammar. `9cf2d4c9` adds
`test_second_marker_after_the_fixed_slot_is_ordinary_prose` so this fixed-slot
boundary is explicit in coverage.

### Finding 4

**File:** `plan_tool/scope_out.py:1315`

**Summary:** `scope_out_step`'s own docstring states
`_prepare_concept_narrow_update` is "the one step here that can raise" past
the gates (so the five `ScopeOutResult` outcomes form a closed, non-raising
contract elsewhere), but the newly added
`require_supported_detail_format_version` call a few lines later, in the
same pre-seed-write zone, is a second, undocumented raise point.

**Failure scenario:** Verified live with a constructed 4-step plan where the
carved step (id 2) has a detail file declaring `detail-format-version: 999`:
calling `scope_out_step(carved_id=2, allow_scope_out=True, yes=True, ...)`
raises `DetailFormatError` directly out of the function before the seed is
even written, contradicting the stated "one step here that can raise"
invariant. Any caller relying on that closed-contract guarantee (mirroring
`merge_bridge`'s identical apply-or-recommend gate shape) gets an unhandled
exception instead of a structured result.

**Disposition:** **Confirmed (documentation contract only).** The behavior is
required: step 3 names `scope_out_step` as a semantic reader and says its typed
refusal reaches the app handler. Existing single- and region-carve tests pin
that propagation. The real defect is the older local comment's claim that
concept preparation is the only pre-seed raise. `9cf2d4c9` updates the function
docstring and replaces the stale block with a terse two-line distinction between
concept/detail refusals and structured non-mutating outcomes.

### Finding 5

**File:** `plan_tool/cli/app.py:763`

**Summary:** The new `except DetailFormatError` handler in `main()`, which
prints the `--recover-refused` remediation hint, is unreachable from `run`,
`reconcile-code`/run-reconcile, `jira`, `validate`, and `annotate`, because
each of those commands catches and locally translates the exception (into
`LauncherError`/`JiraError`/its own handling, then `return rc`) before it
ever escapes back up to `main()`'s dispatch try/except.

**Failure scenario:** Confirmed by tracing `plan_tool/cli/run_cmd.py:1171`
(`except LauncherError as exc: error(str(exc)); rc=2; return rc` inside
`cmd_run`, never re-raising) and the identical pattern in
`cli/reconcile.py:1719`, `cli/jira_cmd.py`, `cli/inspect.py:635`, and
`cli/annotate_cmd.py:210`. Running `plan-tool run <plan> --step N` against a
step whose detail file has a corrupted format-version marker exits 2 with
only the bare `LauncherError` message — the operator never sees the
`--recover-refused` guidance the feature was built to surface, even though
`run` is the most common command to trip this refusal.

**Disposition:** **Refuted.** The app handler is intentionally the boundary for
commands that propagate `DetailFormatError` raw; step 3 lists completeness,
scope-out, suggest-gates, split-criteria, and the apply surfaces. Commands with
established domain errors instead preserve the declared-and-supported diagnosis
through `LauncherError`, `JiraError`, or `AnnotateError`. The selected acceptance
criterion requires that diagnosis and no traceback; it does not require every
domain wrapper to duplicate the raw handler's recovery hint. The documented
recovery route remains in `docs/cli/detail.md`.

### Finding 6

**File:** `plan_tool/detail.py:2289`

**Summary:** `stamp_detail_format_version_marker`'s marker-collapse loop only
drops CONSECUTIVE marker-shaped lines at the slot; a second marker-shaped
line separated from the first by a blank line survives the stamp and is
folded into the visible document body as stray leftover content,
contradicting the docstring's claim that "any marker-shaped line(s) already
in the slot ... are dropped."

**Failure scenario:** Given a slot area shaped `# Title\n\n<!--
plan-tool:detail-format-version: 1 -->\n\n<!-- plan-tool:detail-format-version:
2 -->\n\n## Summary\n`, the collapse loop stops after the first marker line
(the intervening blank line breaks the `while ... match(...)` condition), so
the second marker line is re-emitted verbatim ahead of `## Summary` in the
final stamped file. Lower confidence than finding 3 since it requires an
unusual non-adjacent duplicate-marker input no normal code path currently
produces.

**Disposition:** **Confirmed (documentation contract only).** Step 4 says to
collapse consecutive marker-shaped proposals starting at the slot, while a
marker-shaped line elsewhere—including prose between the managed marker and
`## Summary`—must survive. The implementation already follows that rule. The
docstring and `DETAIL_FORMAT.md` used the looser plural "line(s)," so
`4a0f57ef`/`9cf2d4c9` make the consecutive boundary explicit and add
`test_stamp_preserves_blank_separated_marker_beyond_the_slot` to prevent a
future broad deletion from violating the out-of-slot prose rule.

### Finding 7

**File:** `plan_tool/launcher.py:2924`

**Summary:** `apply_finding`'s new format-version pre-check reads every
tracked detail file from disk, then `_snapshot_text_files(tracked)` on the
next line re-reads the exact same files a second time for the pre-edit
snapshot.

**Failure scenario:** For every finding `apply_finding` processes, each
tracked detail file is opened and read twice in immediate succession with no
caching between the version-check loop and the snapshot. Not a correctness
bug — avoidable I/O on a per-finding hot path.

**Disposition:** **Declined.** This is real duplicate I/O but is imposed by the
selected transaction boundary: step 3 requires every editable current detail
to pass the gate before `_snapshot_text_files`, and says no unsupported body may
reach a snapshot. Combining the reads would require widening the snapshot API
and changing that ordering contract. No measured latency or scale problem
justifies that broader refactor in this review repair.

### Finding 8

**File:** `plan_tool/detail_artifacts.py:231`

**Summary:** An 11-line block comment introducing the format-version-contract
section restates material already fully documented in `DATA_CONTRACT.md` and
`DETAIL_FORMAT.md` (both updated in this same diff), violating the repo
CLAUDE.md's "Code comments" rule to keep comments terse and point at a
maintained doc instead of inlining a long block.

**Failure scenario:** Not a functional bug — a maintenance/drift risk: the
same contract now has three write locations that can silently diverge as the
feature evolves.

**Disposition:** **Confirmed.** The comment duplicates maintained format docs
and violates the repository's terse-comment rule. Identifier enumeration
covered the whole format-version section; the vocabulary sweep found the same
carrier/resolve/check explanation in `DETAIL_FORMAT.md`, `DATA_CONTRACT.md`, and
the completed detail files. `9cf2d4c9` replaces the block with a two-line
purpose statement and pointer to `DETAIL_FORMAT.md`.

## Review pass 2 triage and repair (2026-09-09)

The eight submitted findings resolve to 4 confirmed, 3 refuted, and 1 declined.
Finding 1 is the behavioral correction; findings 4, 6, and 8 are contract or
comment precision. No behavior is changed for the fixed-slot reader, typed
review-walk refusal, domain-error routing, or pre-snapshot gate ordering.

- `4a0f57ef` preserves interior line terminators through
  `parse_detail_response`, adds the mutation-checked pipeline regression, and
  makes the stamper's consecutive-slot boundary explicit.
- `9cf2d4c9` shortens the duplicated format comment, corrects scope-out's raise
  contract, synchronizes `DETAIL_FORMAT.md`, and adds the fixed-slot reader
  regression.

The focused parser/stamper/reader/merge/scope-out surface passes (`225 passed`).
The complete parallel suite also passes (`12387 passed, 189 skipped`). This is
not a convergence claim: the next required evidence is a fresh independent
review of `5d9ce9ac..9cf2d4c9` plus this disposition record.

## Review pass 3 — /code-review high findings (2026-09-09)

**Scope:** `5d9ce9ac..9cf2d4c9` — a fresh independent review of the complete
cumulative implementation range, per this doc's own "next required evidence"
note at the end of the pass-2 triage above.

**Method:** parallel finder angles including a dedicated line-by-line and
removed-behavior sweep, with the strongest candidates verified live against
the working tree. One investigated candidate was **refuted** and is not
carried below: a claimed "blank-separated marker line survives unstamped"
bug in `stamp_detail_format_version_marker` is explicitly documented
behavior, already pinned by
`tests/test_detail.py::test_stamp_preserves_blank_separated_marker_beyond_the_slot`
(the same false positive an earlier pass-3 sub-pass had independently
raised and dropped). Finding 1 below is flagged by the review as the most
severe finding of this pass and was confirmed with a live three-command
reproduction.

### Finding 1

**File:** `plan_tool/parser.py:403`

**Summary:** `UnsupportedPlanFormatVersionError` subclasses `ValidationError`
instead of staying independent, so ~20 pre-existing
`except (ParseError, ValidationError)` sites across the codebase swallow it
before it reaches `cli/app.py`'s dedicated handler.

**Failure scenario:** Confirmed via live reproduction: a plan declaring
`format_version: 2` gives `plan-tool validate` the correct rc=1 with
`INVALID:` + guidance (`cmd_validate` special-cases
`isinstance(exc, UnsupportedPlanFormatVersionError)` to work around the
swallow), but `plan-tool detail <name>` is caught by `detail.py:3828`'s
`except (ParseError, ValidationError) as exc: raise DetailError(...)` and
exits 2 with a bare "failed to parse ..." message, and
`plan-tool completeness-audit <name>` is caught the same way at
`cli/completeness_cmd.py:946` and also exits 2 with a generic message —
both lose the documented rc=1 and the "--use a build that supports this
format_version" remediation entirely. The same file already names this
exact hazard: `ConcurrentModificationError`'s docstring states it is
"Deliberately NOT a subclass of ParseError/ValidationError so the
`except (ParseError, ValidationError)` blocks scattered across callers
don't swallow it" — that precedent wasn't applied to the new exception.

**Disposition:** **Confirmed (command boundary, not hierarchy).** The selected
step explicitly requires the `ValidationError` subtype, so the
`ConcurrentModificationError` precedent cannot change this type. The actual
class-wide site enumeration found the local presentation boundaries in
`detail.py:_parse_detail_plan_and_dispatch`,
`cli/completeness_cmd.py:cmd_completeness`, and
`cli/run_cmd.py:_cmd_run_sweep`; each converted the named refusal before
`app.main` could render its build direction. `8e46777c` re-raises only that
subtype at those boundaries, preserving ordinary malformed-plan handling.
The app-level regression now covers `status`, `detail`, `completeness-audit`,
and `run --all --dry-run`, all with the typed exit-1 direction.

### Finding 2

**File:** `plan_tool/detail.py:2225`

**Summary:** `parse_detail_response`'s preamble-skip treats any column-0
line starting with `#` as the real carrier H1, not just genuine preamble —
a model's narrative aside before the real title gets stamped as the
document's title.

**Failure scenario:** Reproduced directly: a response beginning
`# Note: this step depends on the prior migration...\n\n# Real
Title\n\n## Summary\n...` parses and stamps to `# Note: this step depends
on the prior migration...\n\n<!-- plan-tool:detail-format-version:
1 -->\n\n# Real Title\n\n## Summary...` — the bogus note becomes the
persisted H1/carrier and the marker is spliced after it; the real title is
demoted to orphaned body prose. Related symptom, same root cause: when the
spurious `#` line sits inside an unbalanced fenced code sample in the
preamble, slicing at that point leaves a dangling closing fence, so
`_fenced_code_spans` treats everything after it as fenced — hiding the real
`##` headings and silently rejecting an otherwise well-formed response
(verified: returns `None`). Neither case is covered by this diff's own new
tests, which only exercise plain non-`#` preamble.

**Disposition:** **Confirmed.** `8e46777c` enumerates unfenced H1 candidates
and selects the first candidate block that can satisfy the required-section
contract, rather than treating the first column-0 `#` as a title. The sweep
also ignores heading-looking fenced examples; the regression proves the writer
stamps the actual title rather than the preamble note.

### Finding 3

**File:** `plan_tool/detail.py:2703`

**Summary:** The checkpoint-resume (`cached is not None`) branch of
`_author_step_detail` has no `body is None` guard, unlike the fresh-invoke
branch; a stale pre-diff checkpoint reparsed under the new stricter
`parse_detail_response` can crash instead of failing cleanly.

**Failure scenario:** `_detail_step_input_hash` is documented as
deliberately narrow and doesn't key on the plan-tool build/version, so a
checkpoint saved before this diff (accepted via the old lenient
`line.lstrip().startswith('#')` rule, e.g. an indented H1) is still a valid
cache hit after upgrading. On resume, `parse_detail_response(cached.payload)`
now returns `None`, which falls through unguarded to
`if step.all_files: ... if f in body` (`TypeError`) or
`stamp_detail_format_version_marker(None)` (`AttributeError`) instead of the
clean `DetailResult(written=False, ...)` the fresh-invoke path returns for
the same condition.

**Disposition:** **Confirmed.** A resumed payload that no longer parses now
returns a failed `DetailResult`, reports an error phase, and discards the
unusable checkpoint instead of reaching string operations with `None`. The
new resume regression pins the no-invocation, no-crash result and checkpoint
removal; the existing declined-resume test continues to cover the separate
interactive discard route.

### Finding 4

**File:** `plan_tool/launcher.py:2932`

**Summary:** `apply_finding`'s new format-version refusal loop reads every
tracked detail file (`errors='replace'`), then `_snapshot_text_files` (line
2941, strict utf-8) reads the identical file list again moments later for
the pre-edit snapshot.

**Failure scenario:** Every detail file in the plan is read from disk twice,
with two different decode-error policies, on every `apply_finding`
invocation (once per applied finding during a `completeness-apply`/
`detail --iterate` run). The already-read text is discarded and never
passed to `_snapshot_text_files`.

**Disposition:** **Declined.** This is an unmeasured local I/O optimization,
not a behavioral defect. The current gate intentionally reads with replacement
semantics before the strict snapshot establishes the transaction baseline;
threading a shared snapshot through that boundary would change the selected
decode/error ordering without evidence of a material cost.

### Finding 5

**File:** `plan_tool/cli/app.py:766`

**Summary:** The new `except DetailFormatError` handler (with its
`--recover-refused` hint) never fires for `run`/`jira`/`reconcile` — they
wrap the same condition into `LauncherError`/`JiraError` and handle it
locally first.

**Failure scenario:** Confirmed via grep: `plan_tool/cli/run_cmd.py:1171`,
`plan_tool/cli/jira_cmd.py:389`, and several sites in
`plan_tool/cli/reconcile.py` catch `LauncherError`/`JiraError` and return
locally with no next-step guidance. An operator who first hits a refused
detail via `plan-tool run` or `plan-tool jira` never sees the
`--recover-refused` pointer.

**Disposition:** **Refuted.** The selected contract assigns different command
outcomes deliberately: `run` retains `LauncherError`, Jira retains `JiraError`,
and their local wrappers preserve the named diagnosis. `cli/app.py` adds the
recovery direction only for otherwise-propagated `DetailFormatError`; duplicating
that direction across the domain wrappers is outside this bounded change.

### Finding 6

**File:** `plan_tool/detail.py:7296`

**Summary:** `_capture_detail_lessons_after_validation` re-reads the
just-converged detail body without calling
`require_supported_detail_format_version`, unlike all ~20 sibling read
sites this diff swept.

**Failure scenario:** `detail_body = detail_path.read_text(...)` at line
7296 is used directly by `extract_and_append_detail_lessons` with no
format-version gate; the apply-finding convergence loop can edit the file
multiple times before this read runs.

**Disposition:** **Refuted.** The plan explicitly carves lesson distillation
out: it consumes only the same-invocation body that this writer has just
stamped, after a clean quality pass, rather than an externally supplied
run-grade artifact. Its on-disk reread is not an independent reader boundary.

### Finding 7

**File:** `plan_tool/detail.py:1999`

**Summary:** `_format_already_implemented_block` special-cases
`DetailFormatError` out of its own existing best-effort exception fallback,
forcing a hard abort whenever any OTHER step's detail file is refused —
which is what necessitated the entire separate `--recover-refused`
flag/mode.

**Failure scenario:** This loop already treats a per-sibling `OSError` as
"unreadable, skip and continue." Extending that same pattern to
`DetailFormatError` for this informational cross-step read would let an
ordinary `detail --step N --force` repair one broken sibling without the
new flag, its CLI validation block, and `recovery_only` threaded through
five signatures.

**Disposition:** **Refuted.** The selected fail-closed contract names
`_format_already_implemented_block` as a semantic reader that must re-raise
`DetailFormatError`. The explicit `--recover-refused` path is the intentional
way to suppress sibling reads for one forced, targeted replacement; ordinary
authoring must not silently omit refused context.

### Finding 8

**File:** `plan_tool/schema.py:216`

**Summary:** `Plan.format_version` is a bare pydantic `int` field with no
bool-exclusion, unlike `parser.py`'s explicit `type(declared) is not int`
guard on raw frontmatter.

**Failure scenario:** `Plan.model_validate({..., 'format_version': True,
...})` silently coerces to `format_version == 1` instead of refusing. Not
reachable today since every parse goes through the guarded path, but the
schema doesn't independently enforce the invariant it exists to protect.

**Disposition:** **Refuted.** The raw-frontmatter gate is the artifact
admission boundary and runs before `Plan.model_validate`; direct Pydantic model
construction is not a plan reader. Adding a second schema validator would
duplicate the deliberately early parser rule without closing a reachable
artifact path.

### Finding 9

**File:** `plan_tool/detail_artifacts.py:277`

**Summary:** The detail format-version carrier uses a hand-built positional
scanner instead of this repo's own established heading-anchored-sub-block
convention for machine-parsed markup.

**Failure scenario:** `CLAUDE.md`'s own history of exactly this failure
class prescribes a heading-anchored sub-block. Finding 2 above is a direct
instance of the predicted failure: the positional H1 heuristic is defeated
by ordinary model-authored content.

**Disposition:** **Refuted.** The fixed post-H1 marker slot is a
user-confirmed design choice and `locate_detail_format_carrier` remains its
single reader/writer/upgrader decision point. Finding 2 fixes response
extraction before that slot is stamped; replacing the slot with a generic
heading-anchored architecture would reopen the refused design.

### Finding 10

**File:** `plan_tool/cli/authoring.py:1566`

**Summary:** An 8-line block comment justifying `--recover-refused`'s
companion-shape rule violates `CLAUDE.md`'s code-comment terseness rule;
`DETAIL_FORMAT.md`'s new section already carries the same explanation.

**Failure scenario:** `CLAUDE.md` § "Code comments": keep comments to a
line or two and cite a maintained doc instead of inlining a long block;
lines 1566-1573 are a full paragraph restating already-documented logic.

**Disposition:** **Confirmed (documentation only).** `8e46777c` reduces the
comment to one line and points to `DETAIL_FORMAT.md`, the maintained contract
authority for the companion-shape rule.

## Review pass 3 triage and repair (2026-09-09)

The ten findings resolve to 4 confirmed, 5 refuted, and 1 declined. Before the
confirmed edits, identifier and vocabulary sweeps covered the named
plan-format, response-H1/preamble, checkpoint-resume, and recovery-comment
sites above. `8e46777c` contains the repairs and their regression tests.

Validation passed for the affected surface (`1372 passed`) and the full
parallel suite completed its test work with `12390 passed, 190 skipped`; one
unrelated `test_direct_jira_relocation_commits_land_in_relocated_repo_not_original`
worker exited unexpectedly, and the exact test passed when rerun alone. This
is not a convergence claim: a fresh independent review of `8e46777c` remains
required.

## Review pass 4 — /code-review high findings (2026-09-09)

**Scope:** `5d9ce9ac..8e46777c` — a fresh independent review of the complete
cumulative implementation range, per this doc's own "a fresh independent
review of `8e46777c` remains required" note at the end of the pass-3 triage
above.

**Method:** 10 parallel finder angles, with the strongest candidates
verified live against the working tree. One angle's report on the
`auto_reconcile.py` issue (finding 6) was refined and corrected by a later
angle before finalizing, and that same later angle surfaced finding 9
(`cmd_validate`) as new. Finding 12 below (`launcher.py:2941`, the
`apply_finding` double-read) reproduces the same locus as pass 3's finding 4
(`launcher.py:2932`), which pass 3 **declined** as an unmeasured I/O
optimization — recorded here for the triage record, not argued.

### Finding 1

**File:** `plan_tool/detail.py:318`

**Summary:** `_detail_response_body_start` bounds each H1 candidate's
required-heading window by the NEXT candidate line rather than by
end-of-document, so an unrelated unfenced line starting with `# ` (e.g. a
stray note, or a one-line comment example the model forgot to fence) can
make it silently pick the WRONG H1 as the detail body's start, discarding
the real title and preceding sections.

**Failure scenario:** Reproduced directly: `body = '# Real Title\n\n##
Summary\n...\n# Accidental heading, unfenced\n## Table of
Contents\n...## Why...## Files...## Implementation...## Tests...##
Acceptance...'`. `parse_detail_response` returns a NON-`None` body starting
at `'# Accidental heading...'` — the real title and Summary are silently
dropped, and since exactly one required section (summary) is now missing,
the `<=1`-missing stub path fires and appends a fake `## Summary` stub,
masking the data loss. This detail file is written to disk as if correct.
The pre-diff code (first `#` line wins, no windowed rescoring) would have
parsed this input correctly, so this is a new regression. Independently
reproduced by two other reviewer angles.

**Disposition:** See the 2026-09-10 pass-4 triage below.

### Finding 2

**File:** `plan_tool/detail.py:2257`

**Summary:** `parse_detail_response`'s courtesy-preamble fallback picks
`first_fence` as the FIRST triple-backtick line anywhere in the message,
not the opening fence of the real wrapped response, so a preamble
containing its own earlier complete fenced example makes the fallback slice
still contain the real fence's now-unmatched opening delimiter, which the
unclosed-fence-spans-to-EOF rule then treats as swallowing the rest of the
document.

**Failure scenario:** Reproduced directly: `response = "Note: don't format
it like this:\n` ```\n# Bad Title\n` ```\nHere's the real detail:\n\n`
```markdown\n# Title\n...(all 7 required sections)...` ```\n"`.
`parse_detail_response` returns `None` even though the real fenced content
is a well-formed detail response, because the global leading/trailing fence
strip removes only the message's absolute last ` ``` ` line, leaving the
real fenced block's opener unmatched inside the fallback's slice and hiding
every required heading behind the resulting giant fenced span.

**Disposition:** See the 2026-09-10 pass-4 triage below.

### Finding 3

**File:** `plan_tool/launcher.py:3598`

**Summary:** `run_all_done_steps` (`verify_plan --rollup`, `cmd_review_all
--mode`) and `_run_deep_for_step` (`verify_plan --deep`, called unguarded at
line 3431) now raise `LauncherError` mid-loop the instant ONE done step's
detail file has an unsupported/malformed format-version marker, aborting
the whole "verify-all" sweep instead of reporting that step's failure and
continuing.

**Failure scenario:** A plan with 20 done steps where only step 7's detail
file is corrupted: `plan-tool verify-all` (with or without `--deep`) raises
`LauncherError` inside the per-step loop, caught by `cli/review_cmd.py` as a
single error/exit 2 — losing pass/fail verdicts for all 19 unaffected
steps. `tests/test_launcher.py::test_deep_reconcile_refuses_an_unsupported_detail_marker`
documents this isolation gap in its own docstring, confirming the
batch-wide blast radius was never exercised end-to-end.

**Disposition:** See the 2026-09-10 pass-4 triage below.

### Finding 4

**File:** `plan_tool/detail.py:5317`

**Summary:** `generate_detail`'s per-step authoring loop (serial at line
5317, and the `--jobs` pre-dispatch loop at line 3290) calls
`render_detail_prompt` unguarded; it transitively reaches `review.py`'s
`check_files_coherence`/`check_detail_body_completeness` (neither accepts
or honors a `step_filter`, confirmed by reading both function bodies), so
ANY step's on-disk detail file with a bad marker aborts detail authoring
for the WHOLE invocation, contradicting `generate_detail`'s own docstring:
"Per-step failures ... are aggregated into the result list rather than
aborted — successful steps still get written."

**Failure scenario:** Running `plan-tool detail <plan>` (no `--step`,
multiple pending steps) where step 3 authors successfully and step 5's
authoring then triggers `heuristic_already_done`'s whole-plan scan and hits
step 9's corrupted detail marker: `DetailFormatError` propagates out of
`generate_detail` entirely, discarding the in-memory results list
(including step 3's already-written outcome) and skipping the completeness
tail/summary for the whole run.

**Disposition:** See the 2026-09-10 pass-4 triage below.

### Finding 5

**File:** `plan_tool/create.py:11446`

**Summary:** `create.py`'s `--iterate` (default ON) post-write convergence
loop calls `collect_deterministic_findings` and `apply_finding`, both of
which can raise `DetailFormatError`, but `create.py` never imports or
handles `DetailFormatError` anywhere (0 references) — it falls into
`create.py`'s own generic `except Exception as exc` at line 11446, gets
wrapped into a plain `CreateError`, and `cli/app.py:main()` has no `except
CreateError` handler, so it falls through to the generic "UNEXPECTED
exception" crash-style branch instead of the dedicated `DetailFormatError`
handler (with its `--recover-refused` hint) at `cli/app.py:766`.

**Failure scenario:** `plan-tool create --from-existing <seed>` references
a predecessor's detail file with a corrupted marker; the convergence loop's
`collect_deterministic_findings` call raises `DetailFormatError`, and the
user sees a generic crash dump instead of the clean refusal message plus
the recover-refused next-step this feature's UX was built around.

**Disposition:** See the 2026-09-10 pass-4 triage below.

### Finding 6

**File:** `plan_tool/auto_reconcile.py:169`

**Summary:** `run_auto_reconcile_on_drift`'s bare `raise` inside `except
LauncherError as exc:` re-raises the outer `LauncherError` itself, not the
wrapped `DetailFormatError`. None of its ~7 call sites
(`plan_tool/detail.py:4469/4674`, `plan_tool/create.py:10520/10643`,
`plan_tool/cli/reconcile.py:2349/2618/2718`) catch `LauncherError`, and
`plan_tool/cli/app.py:main()` has no `except LauncherError` clause at all —
confirmed by grep.

**Failure scenario:** During a `--iterate` drift-recovery pass, a step's
detail file declaring an unsupported format version causes auto-reconcile
to raise `LauncherError`; it propagates uncaught through
`detail.py`/`create.py` all the way to `main()`'s generic `except
Exception` catch-all, producing "plan-tool: unexpected error:
LauncherError: ..." plus a saved crash traceback instead of the polished
`DetailFormatError` UX (with the `--recover-refused` hint) this entire
feature was built to surface for exactly this condition.

**Disposition:** See the 2026-09-10 pass-4 triage below.

### Finding 7

**File:** `plan_tool/cli/authoring.py:2159`

**Summary:** `_run_completeness_tail` re-raises `DetailFormatError` before
its catch-all `except Exception`, but has no matching arm for
`UnsupportedPlanFormatVersionError`, even though the call being wrapped
(`app.cmd_completeness`) explicitly does `except
UnsupportedPlanFormatVersionError: raise` (`cli/completeness_cmd.py:944-946`)
specifically so this refusal isn't concealed.

**Failure scenario:** A plan with an unsupported `format_version` is
completeness-audited via the auto-tail after `detail` writes a file:
`cmd_completeness` raises `UnsupportedPlanFormatVersionError`, which falls
into `_run_completeness_tail`'s generic handler and is downgraded to
"plan-tool: warning: auto-completeness pass failed (...); detail files
were written successfully" on stderr — the exact concealment the sibling
`DetailFormatError` re-raise one line above was written to prevent.

**Disposition:** See the 2026-09-10 pass-4 triage below.

### Finding 8

**File:** `plan_tool/launcher.py:2564`

**Summary:** `_compute_findings_delta` special-cases `DetailFormatError`
(propagating it) immediately before its generic `except Exception`, but has
no equivalent carve-out for `UnsupportedPlanFormatVersionError`, which the
same function's own post-edit `parse_plan(plan_path)` reparse (line ~2530)
can raise.

**Failure scenario:** If a Claude-authored `apply_finding` edit leaves the
plan frontmatter declaring an unsupported `format_version`, the post-edit
delta computation misdiagnoses this as the generic synthetic
post-edit-parse-failure finding ("no longer parses as valid
YAML/frontmatter"), hiding the real, distinctly-named format-version
refusal.

**Disposition:** See the 2026-09-10 pass-4 triage below.

### Finding 9

**File:** `plan_tool/cli/inspect.py:611`

**Summary:** `cmd_validate` moved `print(f"OK: {path}")` from immediately
after a successful parse to after `collect_smell_findings`, wrapped in a
try/except that catches only `DetailFormatError`. Any OTHER exception
raised by `collect_smell_findings` now propagates without ever printing the
previously-unconditional "OK:" line.

**Failure scenario:** A `plan-tool validate` run whose plan parses
successfully but whose smell-detection pass raises some unrelated exception
(an `OSError` reading a referenced file, a latent bug in a heuristic) now
shows no "OK:" line before crashing, differing from the prior guarantee
that a successfully-parsed plan always printed "OK: `<path>`" regardless of
what happened afterward.

**Disposition:** See the 2026-09-10 pass-4 triage below.

### Finding 10

**File:** `plan_tool/review.py:1704`

**Summary:** `_resolve_detail_body` (and `_filter_symbols_by_detail` at line
1270) changed from truncate-then-read (`path.read_text(...)[:max_bytes]`)
to read-full-then-truncate (read the whole file, validate it via
`require_supported_detail_format_version`'s two internal `splitlines()`
passes, THEN slice to `max_bytes`) — the `max_bytes` budget no longer
bounds actual I/O/CPU for a large detail file.

**Failure scenario:** A detail file far larger than `max_bytes` now costs
O(full file size) to read and line-split twice per call, for every caller
of these shared resolvers across `review.py`/`completeness_report.py`,
instead of the O(`max_bytes`) the budget parameter was meant to enforce.

**Disposition:** See the 2026-09-10 pass-4 triage below.

### Finding 11

**File:** `plan_tool/detail.py:318`

**Summary:** `_detail_response_body_start` is O(n²) in response length: for
every line i it builds `"".join(lines[i:])` and feeds it to
`locate_detail_format_carrier`, which re-splits that suffix — an
O(n-i) copy+scan per line, quadratic overall, run on every claude response
during detail authoring/reconcile/merge.

**Failure scenario:** A several-hundred-line detail response turns what was
a linear-time parse into a quadratic one on every authoring attempt/retry,
adding measurable latency at run/reconcile scale across a multi-step plan.

**Disposition:** See the 2026-09-10 pass-4 triage below.

### Finding 12

**File:** `plan_tool/launcher.py:2941`

**Summary:** `apply_finding`'s new pre-check loop (just above) reads every
tracked detail file's full text once purely to call
`require_supported_detail_format_version`, then `_snapshot_text_files(tracked)`
two lines later reads the exact same file set again — doubling file I/O
(and the double-`splitlines` validation cost) on every `apply_finding` call
across the whole plan's detail bundle.

**Failure scenario:** Every `completeness-apply` / `run --iterate` /
`reconcile` invocation that calls `apply_finding` now performs 2x the file
reads it needs for every step's detail file in the plan, not just the
finding's target step.

**Disposition:** See the 2026-09-10 pass-4 triage below.

### Finding 13

**File:** `plan_tool/gates.py:132`

**Summary:** The `"try: text = path.read_text(...) except OSError: <skip>"`
+ `"require_supported_detail_format_version(text, path=path)"` shape is
copy-pasted at roughly 15 call sites introduced by this diff (`gates.py`,
`split_criteria.py`, `completeness_report.py`, `review.py` x4, `detail.py`
x4, `scope_out.py` x2, `annotate.py`) with no shared helper, and has
already drifted: some sites pass `errors="replace"`, others use strict
utf-8.

**Failure scenario:** A future change to the read-then-validate contract
must be hand-applied at all ~15 sites; the encoding drift already present
means a non-UTF-8 detail file is handled inconsistently depending on which
call site reads it.

**Disposition:** See the 2026-09-10 pass-4 triage below.

### Finding 14

**File:** `plan_tool/renderer.py:278`

**Summary:** `_load_detail`'s two branches duplicate the identical
read+`require_supported_detail_format_version`+re-raise-as-`DetailGradeError`
block almost verbatim, within the same function.

**Failure scenario:** A future change to the `DetailGradeError` message
format or to which exceptions get wrapped must be edited in two places
inside one function body; a partial edit would leave the pointer-set vs
pointer-unset paths inconsistent.

**Disposition:** See the 2026-09-10 pass-4 triage below.

### Finding 15

**File:** `plan_tool/detail.py:2292`

**Summary:** `stamp_detail_format_version_marker`'s docstring (and
`locate_detail_format_carrier`'s in `detail_artifacts.py`) is 4+ paragraphs
restating the full write/read contract inline, violating the repo
`CLAUDE.md`'s "Code comments" rule: "Keep comments and docstrings terse ...
not a paragraph. When a flow or contract needs more depth, put it in the
relevant doc ... instead of inlining a long block."

**Failure scenario:** This is the "block comments rot and drift from the
code" pattern the cited rule warns about — the same contract is already the
primary subject of `DETAIL_FORMAT.md`'s "Format version marker" section, so
a future change now has two places that must be kept in sync by hand.

**Disposition:** See the 2026-09-10 pass-4 triage below.

## Review pass 4 triage and repair (2026-09-10)

The 15 findings resolve to 7 confirmed, 4 refuted, and 4 declined.
`0f309913` holds the confirmed source/test changes. The repair stays at the
authored-response and named-refusal boundaries; it does not add a generic
reader abstraction, alter batch continuation, or broaden command outcomes.

### Pre-edit sweep and update directive check

The defect class is: **a response parser must retain the authored detail body,
and named format refusals must reach their selected command boundary without
being recast as ordinary failure.** Before editing, the identifier inventory
used `parse_detail_response`, `_detail_response_body_start`,
`locate_detail_format_carrier`, `stamp_detail_format_version_marker`,
`DetailFormatError`, `UnsupportedPlanFormatVersionError`,
`_run_completeness_tail`, and `_compute_findings_delta`. The resulting source
sites were the parser and its tests, the one `create_plan` post-publication
catch-all, the authoring tail, the launcher post-edit delta, and the two cited
docstrings. The vocabulary inventory used `preamble`, `fence`, `heading`,
`required section`, `fixed marker slot`, `carrier H1`, `best-effort`, and
`refusal` across the plan, step-3/4 detail, docs, source, and tests.

- The plan and detail keep the selected policy: an unsupported detail stops a
  parent command before sibling result reporting; only ordinary failures use
  a per-item continuation. Findings 3 and 4 therefore do not authorize a
  batch-wide behavioral change.
- The parser's only response-start site and its focused tests change together.
  The marker locator remains the one carrier recognizer, no version grammar
  changes, and no Jira-grade parser changes land.
- The three exception sites each retain their existing scope: `create` and
  the authoring tail re-raise only their named refusal; the post-edit delta
  re-raises only the plan-version subtype. The generic fallbacks remain for
  their original errors.
- The docstring sweep is intentionally two sites only. `DETAIL_FORMAT.md`
  remains the detailed contract authority, so no plan or format prose changes.

This is proportional to the intent: it proves the exact data-retention and
typed-routing properties, not a future multi-fence parser, generic artifact
reader, or revised batch API.

### Finding 1

**Disposition:** **Confirmed.** The window between successive H1 candidates
could discard the real title and Summary when an accidental later H1 appeared.
`0f309913` selects the latest unfenced H1 before the first required H2, so an
H1 after Summary cannot replace the carrier. The regression asserts the full
body is retained rather than a stubbed fragment.

### Finding 2

**Disposition:** **Confirmed.** The fallback now uses the final fenced span,
which is the real wrapper after a complete fenced preamble example. The
regression proves a preamble's `# Bad title` is excluded and the real title is
accepted.

### Finding 3

**Disposition:** **Refuted.** This reverses pass-1 finding 6 and the selected
plan contract: a format refusal reaches the parent command before a sibling
result is recorded. `run_all_done_steps` and `_run_deep_for_step` must not
produce a partial verify-all report after a semantic artifact refusal.

### Finding 4

**Disposition:** **Refuted.** This is the same selected fail-closed policy as
pass-1 findings 4 and 5. `generate_detail` may aggregate ordinary per-step
authoring failures, but a semantic read of a refused sibling stops the parent
invocation; targeted `--recover-refused --no-completeness` remains the narrow
recovery route.

### Finding 5

**Disposition:** **Confirmed.** `create_plan` now restores protected evidence
and re-raises `DetailFormatError` before its generic finalization handler. The
regression drives a convergence refusal and asserts it remains typed.

### Finding 6

**Disposition:** **Refuted.** The settled drift-halt contract specifically
requires a detail-format-caused `LauncherError` to escape the per-step skip.
The existing auto-reconcile regression pins that exact wrapper and its message;
rewrapping it as `DetailFormatError` would alter the selected command outcome.

### Finding 7

**Disposition:** **Confirmed.** `_run_completeness_tail` now re-raises
`UnsupportedPlanFormatVersionError` alongside `DetailFormatError`, preserving
`cmd_completeness`'s named refusal instead of emitting a warning-only success
tail. The CLI boundary regression asserts exit 1 with no warning.

### Finding 8

**Disposition:** **Confirmed.** `_compute_findings_delta` now re-raises
`UnsupportedPlanFormatVersionError`, so a model-authored unsupported plan
version is not misreported as a generic post-edit parse finding. Its regression
changes frontmatter through `apply_finding` and asserts the exact subtype.

### Finding 9

**Disposition:** **Refuted.** `validate`'s `OK:` verdict means its full
pointer-backed check completed. Printing it before the smell scan would again
mislabel a detail-format refusal as valid. An unrelated exception is a command
failure, not a completed validation verdict, and does not justify a second
success path.

### Finding 10

**Disposition:** **Declined.** This is an unmeasured I/O optimization. The
full read is the selected gate-before-truncation ordering; changing the shared
resolver's budget semantics would widen the repair without evidence of a
material limit.

### Finding 11

**Disposition:** **Confirmed with finding 1.** The previous suffix-joining
candidate scan was quadratic. Finding 1's one-pass fenced-span scan removes
that cost while preserving the selected H1 rule; no separate abstraction is
needed.

### Finding 12

**Disposition:** **Declined.** This is the same `apply_finding` double-read
that pass 3 declined. The preflight's replacement-decoding gate and the
strict snapshot intentionally have different transaction roles; no new
measured cost changes that decision.

### Finding 13

**Disposition:** **Declined.** A generic read-and-gate helper would erase
intentional caller-specific decode/error policies and broaden the patch beyond
the reported boundary. The selected artifact gate remains direct at each
semantic reader.

### Finding 14

**Disposition:** **Declined.** The two renderer branches share behavior but
retain distinct pointer-resolution paths. No current inconsistency or failed
property requires a refactor.

### Finding 15

**Disposition:** **Confirmed.** The two docstrings now state only their local
purpose and point to `DETAIL_FORMAT.md`; the detailed carrier/marker contract
has one documentation authority.

### Validation and next review

- Exact final-candidate regressions: `5 passed` — the two response-parser
  cases, create convergence refusal, authoring-tail plan refusal, and
  post-edit plan-version refusal.
- Wider focused and full parallel suite commands were allowed to complete, but
  their detached terminal runners did not return final summaries to this
  session. Do not record them as green from partial progress; rerun
  `uv run pytest tests/ -q -n auto` if a reproducible full-suite receipt is
  required before the external review.
- **Full-suite receipt obtained 2026-09-10** (the code-review-loop driver, at
  HEAD `8cf3a96f`): `uv run pytest tests/ -q -n auto` → `12397 passed, 189
  skipped in 255.77s`, exit 0. Log: `.tmp/authored-artifact-format-version.pass4-full-suite.log`.
  This satisfies the rerun request above.
- Request a fresh external `/code-review` of `5d9ce9ac..0f309913`. This handoff
  must only claim convergence after that review returns no new actionable
  findings or a qualified low-yield result.

## Review pass 5 — /code-review high findings (2026-09-10)

**Scope:** `5d9ce9ac..0f309913` — a fresh independent review of the complete
cumulative implementation range, per the pass-4 triage's explicit request.

**Method:** 10 parallel finder angles, direct reproduction of the top
candidates, and cross-referencing against this same handoff doc (which by
this point records 4 prior `/code-review` passes and ~48 already-triaged
findings on this diff). Several candidates independently surfaced by
multiple angles — the `apply_finding` double file-read, the whole-plan
blast radius forcing `--recover-refused`, `verify-all` aborting its whole
batch, `suggest-gates` crashing on an unrelated step's bad marker, and a
few duplication/read-helper suggestions — were traced to this doc and found
already raised in prior passes and explicitly refuted or declined as
intentional fail-closed design; they are excluded below rather than
re-reported. A first invocation of this review (same scope) returned an
incomplete final summary — it asserted 13 total findings but the delivered
text contained full detail for only 2 of them, referencing 11 more that
were never actually included. That run's source agent was no longer
addressable by the time this was noticed, so rather than fabricate or
silently drop the missing 11, the review was re-run from scratch; the 7
findings below are that re-run's complete, self-consistent result.

### Finding 1

**File:** `plan_tool/detail.py:2213`

**Summary:** `parse_detail_response` now rejects a previously-valid
response shape: preamble + one wrapping fence + trailing remark, whenever
the wrapped body contains its own internal same-length code fence, because
`_detail_response_body_start` (line 318) recomputes fence spans in a way
that lets the inner fence's closer end the outer fence early, hiding the
real H1.

**Failure scenario:** A claude response like "Sure, here's the detail
file:\n\n` ```markdown\n# Step 3 — Foo\n...\n## Implementation\nExample:\n`
```python\ndef foo(): ...\n` ```\n...\n` ```\n\nLet me know if you need
anything else!" parses successfully on the pre-diff commit (verified via
git worktree of `5d9ce9ac`) and now returns `None` on HEAD (verified
directly), rejecting the whole response and burning the single retry even
though it's valid — the same shape without the internal code fence still
parses fine.

**Disposition:** See the 2026-09-10 pass-5 triage below.

### Finding 2

**File:** `plan_tool/detail_artifacts.py:336`

**Summary:** `declared = int(raw_value)` is unguarded against Python's
integer-string conversion length limit, so an overlong all-digit marker
payload crashes with a raw `ValueError` instead of the intended
`DetailFormatError` (duplicated at line 397 in
`upgrade_detail_body_to_current`).

**Failure scenario:** A detail file whose slot reads `<!--
plan-tool:detail-format-version: 999...9 -->` (5000 nines) makes
`require_supported_detail_format_version` raise `ValueError: Exceeds the
limit (4300 digits) for integer string conversion...` (Python 3.11+ default
limit) — reproduced directly. None of the ~20 call sites, all built to
catch `DetailFormatError`, catch this, so it surfaces as an unhandled crash
instead of the clean refusal / `--recover-refused` guidance every other
malformed marker gets.

**Disposition:** See the 2026-09-10 pass-5 triage below.

### Finding 3

**File:** `plan_tool/cli/completeness_apply_parallel.py:178`

**Summary:** `UnsupportedPlanFormatVersionError` (a `ValidationError`
subclass) is caught by the broader `except (ParseError, ValidationError)`
clause in `apply_finding_in_tree` before it can reach the `except
DetailFormatError: raise` guard added right below it for exactly this
purpose, so the fail-closed batch-abort built for a detail-format refusal
never fires for its plan-format sibling.

**Failure scenario:** Running `completeness-apply --jobs 4` when the
on-disk plan's `format_version` has become unsupported (drift, bad merge,
etc.): `apply_finding_in_tree` converts the refusal into an ordinary
`FindingApplyResult(exit_code=1, ...)` for that one finding, and
`dispatch_parallel`/`replay_results` proceed to apply every other finding's
isolated-worktree candidate onto the same canonical, unsupported-format
plan — exactly the outcome the adjacent, specifically-tested
`DetailFormatError` carve-out was written to prevent. Same gap at
`dispatch_parallel`'s `_guarded` (line 541) and `replay_results`' parse gate
(line 485).

**Disposition:** See the 2026-09-10 pass-5 triage below.

### Finding 4

**File:** `plan_tool/cli/authoring.py:1764`

**Summary:** `cmd_detail`'s `except DetailError as exc:` (identically at
`cmd_split:2248`, `cmd_merge:2459`; same shape via
`completeness_phases.py:838`'s `apply_rc=1` default) does not catch the new
sibling class `DetailFormatError`, so when a format refusal correctly
escapes to `main()`'s handler, the function's own `finally:
run_logger.run_end(...)` fires with `err_msg` still `None`.

**Failure scenario:** `plan-tool detail <plan> --step N` on a plan with a
malformed detail marker prints the correct "Try: --recover-refused"
guidance to the console but the persisted run-log entry records
`outcome=error, rc=1, error=None`, permanently losing the diagnostic text
from run-log history even though the console got it right.

**Disposition:** See the 2026-09-10 pass-5 triage below.

### Finding 5

**File:** `plan_tool/detail_artifacts.py:259`

**Summary:** `_INTEGER_LITERAL_RE`'s `\d` is Unicode-aware, so a non-ASCII
decimal digit (e.g. Arabic-Indic `١` or fullwidth `４`) is silently parsed
by `int()` and accepted as the equivalent ASCII version number,
inconsistent with the sibling plan-format check which refuses any
non-native-int value outright.

**Failure scenario:** A detail file with `<!--
plan-tool:detail-format-version: ١ -->` (U+0661) is silently accepted as
version 1 with no error (verified directly), even though
`render_detail_format_version_marker` never emits anything but ASCII
digits, so only a hand-crafted/corrupted marker can produce this — slipping
past the "refuses rather than defaulting" contract the same function's
docstring states.

**Disposition:** See the 2026-09-10 pass-5 triage below.

### Finding 6

**File:** `plan_tool/scope_out.py:271`

**Summary:** A carved step's detail body — including its `<!--
plan-tool:detail-format-version: N -->` marker line — is appended verbatim
into the generated `create --from-existing` seed with no stripping (same
pattern in `detail.py:6842`'s `merge_steps` prior_body construction),
leaking an internal bookkeeping comment into a document a human reviews and
a future Claude authoring call consumes as prior context.

**Failure scenario:** `plan-tool scope-out <plan> --step N` on a step whose
detail file was written by this build's writer produces a seed whose
"prior detail body" section literally contains `<!--
plan-tool:detail-format-version: 1 -->`, which is then fed into the next
`create --from-existing <seed>` Claude prompt as if it were real step
content.

**Disposition:** See the 2026-09-10 pass-5 triage below.

### Finding 7

**File:** `plan_tool/detail.py:5759`

**Summary:** `generate_detail`'s and `require_supported_detail_format_version`'s
(`plan_tool/detail_artifacts.py:302`) docstrings each inline several
paragraphs restating the `DETAIL_FORMAT.md` "Format version marker"
contract instead of citing it, violating this repo's own `CLAUDE.md` "Code
comments" rule — the same defect class this diff already fixed at two
sibling functions (`stamp_detail_format_version_marker` /
`locate_detail_format_carrier`) but didn't fully sweep.

**Failure scenario:** Any future change to the marker's resolve-then-check
contract now has three places to keep in sync by hand (`DETAIL_FORMAT.md`
plus these two docstrings) instead of the one authority `DETAIL_FORMAT.md`
already establishes — the "block comments rot and drift from the code"
problem the already-fixed sibling docstrings themselves cite as their
reason for trimming.

**Disposition:** See the 2026-09-10 pass-5 triage below.

## Review pass 5 triage and repair (2026-09-10)

All 7 findings are **confirmed** and repaired in `e38668f5`
(`fix(detail): harden format refusal boundaries`). The repair keeps the
existing altitude and selected fail-closed policy: it proves the malformed
artifact and response-boundary behavior reported by this review; it does not
add a format framework, a general parser mode, or a revised batch API.

### Pre-edit sweep and update-directive check

The defect class is: **authored detail boundaries must preserve valid content,
refuse malformed fixed-slot declarations through their named command boundary,
and never pass writer bookkeeping into human/model context.** Before editing,
the identifier inventory covered `parse_detail_response`, `_fenced_code_spans`,
`_INTEGER_LITERAL_RE`, `require_supported_detail_format_version`,
`upgrade_detail_body_to_current`, `DetailFormatError`,
`UnsupportedPlanFormatVersionError`, `apply_finding_in_tree`,
`dispatch_parallel`, `replay_results`, `cmd_detail`, `cmd_split`, `cmd_merge`,
`_apply_walk_recs_parallel`, `_scope_block`, `render_carved_seed`,
`render_carved_region_seed`, `merge_steps`, and `generate_detail`. The
vocabulary sweep covered `preamble`, `wrapper fence`, `marker`, `fixed slot`,
`ASCII decimal`, `unsupported`, `refusal`, `prior body`, `seed`, `run log`,
and `docstring` across source, focused tests, `DETAIL_FORMAT.md`, the selected
plan/detail bundle, seeds, and backlog.

- The parser changes only its preamble-plus-fenced-wrapper fallback: it tries
  earlier scanner spans only after the legacy latest span cannot identify a
  valid body, then removes only the now-unmatched wrapper tail. Ordinary
  response selection remains unchanged.
- The marker reader is the only grammar decision point. ASCII decimal payloads
  retain the selected integer form; Unicode numerals and Python-overlong
  numerals become the existing `DetailFormatError`. The upgrader remains safe
  by first calling that reader gate, rather than gaining a second parser.
- Both parallel-apply paths keep ordinary per-finding failure isolation. Only
  the named unsupported-plan subtype joins the existing hard detail refusal;
  replay restores the affected write before aborting. The authoring and
  parallel-completeness command tails now retain that already-propagating
  refusal text in their run-log `run_end` event.
- The new fixed-slot-only stripper is deliberately applied at the two exposed
  context sinks: `_scope_block` covers single and regional carved seeds, and
  `merge_steps` covers its prior-body prompt. Marker-shaped prose outside the
  fixed slot remains content. No broader read helper or document mutation is
  introduced.
- The docstring sweep changes exactly the two reported long docstrings;
  `DETAIL_FORMAT.md` remains the detailed format authority.

This is true and proportional to the plan intent: the smallest proof closes
the reported format/version boundary defects, stays at implementation-detail
altitude, and sweeps related identifiers and vocabulary only where they affect
that property.

### Finding dispositions

1. **Confirmed.** The parser now preserves a preamble-wrapped detail body
   containing a same-length inner code fence and excludes the outer-fence
   commentary tail. The regression asserts the exact body round-trips.
2. **Confirmed.** Overlong ASCII digit payloads now become
   `DetailFormatError`, never Python's raw conversion `ValueError`; the
   regression proves both reader and upgrader behavior.
3. **Confirmed.** `UnsupportedPlanFormatVersionError` now escapes the worker
   and dispatcher and restores the candidate before replay aborts, matching the
   existing named detail-format refusal policy.
4. **Confirmed.** `detail`, `split`, `merge`, and parallel
   `completeness-apply` retain the escaping refusal's text in `run_end` while
   preserving the existing top-level command handler and exit status.
5. **Confirmed.** The fixed-slot marker grammar is ASCII decimal; Arabic-Indic
   and fullwidth numerals now refuse rather than being silently canonicalized.
6. **Confirmed.** Carved seeds and merge prior-body context strip only the
   fixed-slot marker. Tests preserve an identical marker-shaped line in normal
   prose.
7. **Confirmed.** `generate_detail` and
   `require_supported_detail_format_version` received terse local docstrings.
   Pass 6 corrects the `generate_detail` flow-document citation.

### Validation and next review

- Focused suites: `1064 passed` —
  `tests/test_detail.py`, `tests/test_detail_artifacts.py`,
  `tests/test_scope_out.py`, `tests/cli/test_completeness_apply_parallel.py`,
  and `tests/cli/test_authoring_cmds.py`.
- Full suite at `e38668f5`: `uv run pytest tests/ -q -n auto` →
  `12409 passed, 190 skipped in 282.14s`; receipt:
  `/private/tmp/plan-tool-pass5-full-suite.log`.
- Convergence remains open. The separately-operated code-review loop must
  review the new committed snapshot (`0f309913..e38668f5`) and append its
  findings here before this handoff can claim convergence.

## Review pass 6 — /code-review high findings (2026-09-10)

**Scope:** `0f309913..e38668f5` — the pass-5 repair commit only, per the
pass-5 triage's explicit request.

**Method:** parallel finder angles plus direct code reading and live
reproduction for the top two candidates; the changed test files
(`tests/test_detail.py`, `tests/test_detail_artifacts.py`,
`tests/test_scope_out.py`, `tests/cli/test_authoring_cmds.py`,
`tests/cli/test_completeness_apply_parallel.py`) were run and all 1064
pass. Findings 1 and 2 are outside the literal diff hunks but are, in the
review's words, "sibling sites of the exact class this diff fixed
elsewhere, left unswept" — continuing the same incomplete-sweep pattern
pass-5's finding 3 identified. Finding 3 is explicitly flagged by the
review as lower-confidence: its own attempt to construct an adversarial
input was correctly rejected by the existing completeness gate.

### Finding 1

**File:** `plan_tool/review_walk.py:842`

**Summary:** The interactive review/completeness-apply walk's pre-existing
hard-abort guards only catch `DetailFormatError`, so the new
`UnsupportedPlanFormatVersionError` hard-refusal class this diff adds
elsewhere (`completeness_apply_parallel.py`, `completeness_phases.py`) is
not recognized here and falls through to the generic `except Exception`
handler.

**Failure scenario:** Running an interactive `plan-tool
completeness-audit`/`review` walk (human at a TTY, `--jobs 1`) and applying
a finding whose edit trips a plan `format_version` refusal
(`UnsupportedPlanFormatVersionError`, a `ValidationError` subclass, distinct
from `DetailFormatError`) hits `except DetailFormatError: raise` (no match)
then `except Exception as exc: output_fn(f'action failed: {exc}');
continue` at lines 842/1066/1143 — printed as an ordinary recoverable
per-item failure, `state.yes_to_all` cleared, and the walk keeps prompting,
instead of aborting with the dedicated `UnsupportedPlanFormatVersionError`
recovery message `cli/app.py` already renders for every other path this
diff hardened.

**Disposition:** See the 2026-09-10 pass-6 triage below.

### Finding 2

**File:** `plan_tool/parser.py:447`

**Summary:** `parse_plan_text` has no guard against Python's
integer-string-conversion length limit when YAML parses a plan's
`format_version` scalar — the exact bug class this diff just fixed for the
detail-format-version marker, left unfixed at the plan level.

**Failure scenario:** A plan file's frontmatter contains `format_version: `
followed by 4301+ digits. `yaml.safe_load(split.frontmatter_yaml)`
internally calls `int()` on the scalar and raises a bare `ValueError:
Exceeds the limit (4300 digits)...`, which is not a `yaml.YAMLError`
subclass, so `parse_plan_text`'s `except yaml.YAMLError` does not catch it
— it propagates uncaught through every caller (any CLI command,
`completeness_apply_parallel.replay_results`'s parse gate, etc.) as an
unhandled crash instead of a clean `ParseError`/`UnsupportedPlanFormatVersionError`.
Verified by direct reproduction: `yaml.safe_load('format_version: ' +
'9'*5000)` and `parse_plan_text(...)` both raise the unguarded `ValueError`.

**Disposition:** See the 2026-09-10 pass-6 triage below.

### Finding 3

**File:** `plan_tool/detail.py:2267`

**Summary:** `parse_detail_response`'s new reversed-fence-candidate fallback
loop could in principle accept an earlier, unintended fenced block as the
response wrapper instead of correctly rejecting a malformed/ambiguous
response.

**Failure scenario:** Two independent review passes flagged that when the
true (textually-last) wrapper's heading check fails, the loop walks
backward through every earlier fence span until one satisfies
`_detail_response_body_start`, with no confirmation the chosen span is the
intended wrapper rather than a coincidental match. Lower confidence: my own
attempt to construct a concrete adversarial input (an early decoy fence
plus a same-length-nested-fence collision in the real content) was
correctly rejected (returned `None`) by the existing required-H2
completeness gate, so triggering an actual wrong-but-accepted body appears
to require a narrow coincidence — flagging as plausible-but-unconfirmed
given two independent votes.

**Disposition:** See the 2026-09-10 pass-6 triage below.

### Finding 4

**File:** `plan_tool/detail.py:5771`

**Summary:** `generate_detail`'s new short docstring cites the wrong
maintained doc for the contract it replaced.

**Failure scenario:** The deleted ~70-line docstring's facts
(`recovery_only` semantics, jobs/iterate/split mutual exclusion, checkpoint
resume, extract_lessons gating) live in `docs/DETAIL_FLOW.md` (confirmed
via grep), but the replacement docstring points to `docs/RUN_FLOW.md`,
which documents the `run` phase and contains zero hits for any of those
terms. A reader following the citation lands in the wrong document and
finds none of the information the docstring used to state inline.

**Disposition:** See the 2026-09-10 pass-6 triage below.

### Finding 5

**File:** `plan_tool/cli/authoring.py:1764`

**Summary:** `except DetailFormatError as exc: err_msg = str(exc); raise` is
copy-pasted identically across `cmd_detail` (1764), `cmd_split` (2251), and
`cmd_merge` (2465).

**Failure scenario:** Not a crash — a maintenance cost: a future change to
this handling, or a fourth command wrapping detail authoring, must remember
to duplicate the same 3-line clause or its run-log diagnostic silently
goes blank on a format refusal (as it did for these three before this
fix).

**Disposition:** See the 2026-09-10 pass-6 triage below.

### Finding 6

**File:** `plan_tool/detail_artifacts.py:351`

**Summary:** `strip_detail_format_version_marker` re-derives the same
carrier/slot-line lookup that `require_supported_detail_format_version`
already computes just above it, instead of sharing the result.

**Failure scenario:** Not a bug — cheap redundant computation:
`merge_steps` (`detail.py:6790-6791`) and `scope_out._scope_block` each
call `require_supported_detail_format_version(body, ...)` immediately
followed by `strip_detail_format_version_marker(body)` on the same text,
walking `locate_detail_format_carrier` twice per detail body for no
functional reason.

**Disposition:** See the 2026-09-10 pass-6 triage below.

### Finding 7

**File:** `plan_tool/detail.py:2262`

**Summary:** The new `line_index_by_offset` dict-building loop in
`parse_detail_response` duplicates offset-to-line-index bookkeeping that
`_detail_response_body_start` (defined a few dozen lines above in the same
file) already performs internally.

**Failure scenario:** Not a bug — maintenance cost: the same `offset = 0;
for i, line in enumerate(lines): ...; offset += len(line)` accumulation
pattern is now written independently in two places in this file, so a
future correction to one (e.g., a non-line-boundary offset edge case) will
not automatically propagate to the other.

**Disposition:** See the 2026-09-10 pass-6 triage below.

## Review pass 6 triage and repair (2026-09-10)

`150c21d6` resolves the four actionable pass-6 findings. Findings 5–7 are
declined because they identify no behavior defect and their proposed shared
abstractions exceed the review's narrow intent.

### Update-directive check and sweep

**Defect class:** format/version refusal paths must end consistently, and the
detail-response parser must reject a later malformed wrapper instead of
accepting an earlier preamble example.

Before editing, the identifier inventory covered
`UnsupportedPlanFormatVersionError`, the three `review_walk` hard-abort
guards, `yaml.safe_load`, `parse_detail_response`,
`_detail_response_body_start`, `_fenced_code_spans`, `generate_detail`,
`strip_detail_format_version_marker`, and
`require_supported_detail_format_version`. The vocabulary sweep covered
"format refusal", "format_version", "wrapper", "preamble", "fence", and
"carrier/slot" across the named callers and tests.

The result is checked against the shape of each defect rather than replayed at
every textual match:

- all three review-walk action boundaries now re-raise the plan-version
  refusal; existing top-level handlers already own their terminal rendering;
- only the YAML conversion boundary catches the raw integer-conversion
  `ValueError`; later schema/version behavior stays unchanged;
- the parser selects only the latest raw H1 immediately following a
  scanner-recognized wrapper opener, then lets the existing required-section
  gate reject an incomplete response. It does not introduce a generalized
  wrapper grammar or a new parser helper;
- the docstring points to the existing `DETAIL_FLOW.md` authority; and
- the repeated local exception clauses, marker lookup, and local offset scan
  remain local because no selected behavior requires a new shared API.

This is true and proportional to the reported intent: the smallest proofs make
the existing refusals and response contract true, without adding eventual
capability. The update remains at implementation-detail altitude; it changes
no bare plan, backlog item, or selected product scope.

### Finding dispositions

1. **Confirmed.** `UnsupportedPlanFormatVersionError` now escapes each of
   `_auto_apply` and the two interactive review-walk action paths beside
   `DetailFormatError`, so a version refusal cannot be downgraded to a
   recoverable per-finding failure. The regression exercises `apply-all`,
   `apply`, and `run` modes.
2. **Confirmed.** `parse_plan_text` translates a `ValueError` raised by
   `yaml.safe_load` for an overlong numeric `format_version` into the existing
   `ParseError` boundary. The 5,000-digit regression proves no raw Python
   conversion error escapes.
3. **Confirmed.** The review's initial nested-fence construction did not
   reproduce, but a simpler goal-level reproduction did: a complete earlier
   fenced example followed by a later wrapper containing only `# Actual` and
   `## Summary` made the former fallback accept the example. The revised
   fallback anchors on the latest raw H1 directly after a recognized wrapper
   opener, so the existing section check rejects the malformed later response
   instead of falling back. The regression asserts `None` for that exact case.
4. **Confirmed.** `generate_detail` now directs readers to
   `docs/DETAIL_FLOW.md`, the maintained detail-authoring flow document.
5. **Declined.** The three `err_msg = str(exc); raise` clauses are deliberate
   local diagnostics at three command boundaries. Extracting them adds a
   shared helper without changing any refusal behavior.
6. **Declined.** Reusing a carrier lookup between validation and marker
   stripping would broaden their function contracts for an insignificant
   second scan; the current calls remain correct at both `merge` and
   `scope-out` consumers.
7. **Declined.** The parser's offset-to-line map is locally owned by its
   fenced-wrapper selection. Extracting it from the separate body-start scan
   would add an abstraction without fixing an incorrect offset or response
   decision.

### Validation and next review

- Focused regressions: `59 passed` — the three affected test classes.
- Affected-module suite: `991 passed in 6.64s` —
  `tests/test_review_walk.py`, `tests/test_parser.py`, and
  `tests/test_detail.py`; receipt:
  `/private/tmp/plan-tool-pass6-affected.log`.
- Two parallel full-suite attempts exercised all tests but are not clean
  receipts because xdist workers terminated while running unrelated tests:
  first, `12413 passed, 190 skipped` before a worker crash in
  `test_direct_jira_relocation_commits_land_in_relocated_repo_not_original`;
  retry, `12412 passed, 190 skipped` before worker crashes in
  `test_direct_jira_relocated_root_preexisting_dirt_aborts_before_detail` and
  `test_matching_local_receipt_resumes_only_when_head_path_is_absent`.
  Receipts: `/private/tmp/plan-tool-pass6-full-suite.log` and
  `/private/tmp/plan-tool-pass6-full-suite-retry.log`.
- All three worker-crashed tests pass when run serially: `3 passed in 10.41s`.

Convergence remains open. No competing code review was run here. The
separately-operated review loop must review the fresh source snapshot
`e38668f5..150c21d6` and append its findings before this handoff can claim
convergence.

## Review pass 7 — /code-review high findings (2026-09-10)

**Scope:** `e38668f5..150c21d6` — the pass-6 repair commit only, per the
pass-6 triage's explicit request.

**Method:** full diff read plus two independent verification agents; the
`parser.py` broadened `except (yaml.YAMLError, ValueError)` and the three
`review_walk.py` `UnsupportedPlanFormatVersionError` re-raise additions were
traced against every caller and confirmed correct — no regression. A
hypothesized "incomplete sweep" of `UnsupportedPlanFormatVersionError`
handling at five other `except DetailFormatError` sites (`detail.py:1327`,
`detail.py:2032`, `completeness_report.py:1644`, `review.py:9096`,
`create.py:11447`) was investigated and **refuted**: none of those sites
ever re-parse plan frontmatter, so `UnsupportedPlanFormatVersionError`
cannot reach them.

**This is the third consecutive round (5, 6, 7) to find a confirmed defect
in `parse_detail_response`'s fence/wrapper-selection logic**, each fix
seeding the next: pass-5 fixed a nested-code-fence collision; pass-6's fix
for that area's "reversed-fence fallback" concern (itself flagged
low-confidence/unconfirmed by the pass-6 review) is the fix that
**introduced** the regression below. The finding below is verified by
running the identical input against both the pre-fix (`e38668f5`) and
post-fix (`150c21d6`) code and observing the pre-fix code handle it
correctly.

### Finding 1

**File:** `plan_tool/detail.py:2270`

**Summary:** The rewritten fenced-wrapper fallback in
`parse_detail_response` picks the textually-last H1 anywhere in the
document that merely follows *some* fence-open line, without checking that
a required detail-format heading (e.g. `## Summary`) follows it or that it
belongs to the fence being unwound — so a legitimate, complete wrapped
response is discarded (or silently replaced) whenever the model appends any
trailing fenced illustrative snippet whose first line starts with `#`.

**Failure scenario:** Input: a proper "Sure, here's the detail file:\n\n`
```markdown\n<complete 7-section body>` ```\n\n" response followed by an
ordinary trailing example like "Note:\n\n` ```python\n# Example
usage\nfoo()\n` ```\n". `# Example usage` is the last line in the document
matching `locate_detail_format_carrier` and is immediately preceded by a
real fence-open (`` ```python ``), so the loop (lines 2270-2282) picks it
as `first_heading`, discarding the entire valid answer before it. The
truncated remainder has only 0 of 7 required headings, so
`parse_detail_response` returns `None` for a perfectly valid response —
confirmed by direct execution (returns `'# Step 3 — Foo\n\n##
Summary...'` on the pre-fix code at `e38668f5`, but `None` on this diff's
code). Worse: if the trailing decoy block is itself a *near-complete*
detail body (missing exactly one section), the function silently returns
the DECOY's content (with a synthesized stub) in place of the real, valid
answer — verified by direct execution, producing `'# Decoy\n\n##
Summary...## Acceptance criteria\n\n_(stub: ...)_'` while completely
dropping the real `# Step 3 — Foo` body. This is a regression versus the
pre-diff code, which validated each fenced candidate against
`_detail_response_body_start`'s required-heading check before accepting it
and thus handled both scenarios correctly.

**Disposition:** See the 2026-09-10 pass-7 triage below.

## Review pass 7 triage and repair (2026-09-10)

**User-directed structural fix, not a routine patch.** After three
consecutive rounds (5, 6, 7) found confirmed defects in the same
`parse_detail_response` fence/wrapper-selection logic, each fix seeding the
next, this was surfaced to the user as a scope decision rather than
auto-applied as a fourth targeted patch. The user selected a redesign of
the wrapper-selection logic itself: bound each candidate to its own fence
span, rather than continuing to patch the newest reported input against an
otherwise positional heuristic. `85b8a19b` implements it.

### Investigation and design

The confirmed defect: the fallback picked whichever H1 sat nearest to *any*
fence-open line, scanning backward from the end of the document with no
bound on how far the extracted body could run — so a trailing illustrative
snippet (e.g. a decoy ` ```python example``` `) after a complete, valid
wrapped response could discard that response entirely, or, if the trailing
snippet happened to look near-complete, silently replace it.

**A first attempt (bind each candidate to its own span, prefer the first
valid one in document order) was tested against the existing suite and
found to violate a separately-tested, already-shipped policy**:
`test_later_invalid_wrapper_does_not_fall_back_to_an_earlier_example`
explicitly requires that when the *last* wrapper in a document is present
but invalid, the function returns `None` rather than falling back to an
earlier, complete-looking wrapper. Preferring the first valid candidate
broke this test outright. This is exactly the class of mistake
`CLAUDE.md`'s "check the remedy against the goal" rule warns about: the
first design closed the round-7 finding but regressed a sibling, previously
correct case a green test suite would have caught before this fix landed
(and did, on the first run).

**The shipped design instead preserves the existing last-wrapper-wins
direction and adds one narrow exception.** Each fence span becomes an
independent candidate, bounded to that span alone — using the same
rescan-after-excluding-the-opener technique the prior code already relied
on, so a candidate correctly survives one same-length nested fence inside
its own body (verified against
`test_preamble_wrapped_body_with_same_length_inner_fence_parses`, the
pass-5 regression this design must not break). Candidates are then walked
**last-to-first**, and the first one with **at least one** required H2
heading wins. A candidate with **zero** required headings is not a genuine
attempt at the detail-response contract at all — it is incidental content,
like a bare illustrative code snippet — so it is skipped rather than
treated as the final answer or as a reason to give up. This is the single
narrow condition under which the design does *not* strictly honor
"last-wrapper-wins": a zero-heading trailing candidate never counts as "the
last wrapper" in the first place.

**Known, deliberately accepted residual.** A trailing wrapper with *some*
required headings present (not zero, but incomplete) is structurally
indistinguishable from a genuine-but-broken final attempt, and the design
does not try to distinguish them — it still wins over an earlier, complete
wrapper, per the existing policy. Fully closing this narrower case would
require overriding `test_later_invalid_wrapper_does_not_fall_back_to_an_earlier_example`'s
contract, which is out of scope for this fix and was not asked for.
`test_trailing_wrapper_with_some_required_headings_still_wins_per_last_wrapper_policy`
pins this as intentional, not a gap to close on a future pass.

### Verification

- `test_trailing_illustrative_snippet_does_not_discard_or_replace_a_complete_wrapped_response`
  pins the confirmed defect fixed: reproduces the review's exact case 1
  input and asserts the real response is returned intact, with the decoy
  excluded.
- `test_trailing_wrapper_with_some_required_headings_still_wins_per_last_wrapper_policy`
  pins the accepted residual (case 2 from the review) as intentional
  behavior under the existing policy, not a silent gap.
- The full pre-existing `TestParseDetailResponse` class, including both
  cited prior-round regressions
  (`test_preamble_wrapped_body_with_same_length_inner_fence_parses`,
  `test_later_invalid_wrapper_does_not_fall_back_to_an_earlier_example`),
  passes unchanged: `44 passed`.
- `tests/test_detail.py`: `595 passed`.
- Full suite: `uv run pytest tests/ -q -n auto` → `12417 passed, 189
  skipped`, exit 0.

### Next review

Convergence remains open. A fresh independent review of
`150c21d6..85b8a19b` is the next required evidence, per the same pattern
every prior pass in this loop has followed.

## Review pass 8 — /code-review high findings (2026-09-10)

**Scope:** `150c21d6..85b8a19b` — the pass-7 structural fix, per that fix's
own explicit next-review request.

**Method:** three independent background angle agents plus manual analysis,
converged and cross-verified. Findings 1 and 2 were empirically reproduced
against both the parent commit (`150c21d6`) and the fix's HEAD (`85b8a19b`)
before being reported, independently by two of the three angles for finding
1. **This is the fourth consecutive round (5, 6, 7, 8) to find a confirmed
defect in `parse_detail_response`'s wrapper-selection logic** — this time in
the pass-7 structural fix itself, which was written specifically to close
the pass-5/6/7 recurrence.

### Finding 1

**File:** `plan_tool/detail.py:2301`

**Summary:** `parse_detail_response`'s rewritten fenced-wrapper fallback
truncates — and can silently corrupt with fabricated stub content — a
fully valid, complete detail response whenever it contains two or more
same-length internal code fences (e.g. a `` ```python``` `` example in
both `## Implementation` and `## Tests`).

**Failure scenario:** `_fenced_code_spans` (`plan_tool/scope_fence.py`)
tracks one global opener with no nesting, so two internal
`` ```python `` fences inside one `` ```markdown `` wrapper produce 3
top-level spans instead of 1: the first inner close prematurely closes
the outer span, the second inner fence's open becomes a spurious new
top-level span, and the true wrapper close becomes a third
(unmatched-to-EOF) span. `window_end = spans[idx + 1][0]` then bounds
the real candidate to end at the second inner fence's opening line,
cutting off everything after it. Verified by direct execution: on
parent commit `150c21d6`, `parse_detail_response` returns the full,
correct body byte-for-byte; on this diff's HEAD (`85b8a19b`), the
identical input either returns `None` (discarding a valid response
outright) or — when only one required heading falls after the
truncation point — returns a body with the real `## Tests` content
silently dropped and the real `## Acceptance criteria` bullet silently
replaced by the fabricated `_(stub: model omitted this section — fill
in manually)_` marker, with no error and no retry.

**Disposition:** See the 2026-09-10 pass-8 triage below.

### Finding 2

**File:** `plan_tool/detail.py:2312`

**Summary:** The candidate-acceptance filter `if not candidate_headings:
continue` checks for ANY `##` heading via the unfiltered `_H2_HEADING_RE`,
not headings restricted to `_REQUIRED_H2_TOKENS` — contradicting the
function's own inline comment, which states a candidate should be
skipped when it has "zero required headings".

**Failure scenario:** A trailing decoy fence containing only a
non-required heading (e.g. `# Note\n\n## Notes\n\nUnrelated trailing
note.`) has a non-empty `candidate_headings` (`{"notes"}`), so it is
accepted as `wrapped_text` and the earlier, complete, correct answer is
never even reached by the reversed loop's `break`. Verified directly:
`parse_detail_response` on a complete valid wrapped 7-section response
followed by such a trailing `## Notes` decoy returns `None` — the real
answer is discarded because the decoy "wins" the selection per the
comment's own stated (but unimplemented) contract.

**Disposition:** See the 2026-09-10 pass-8 triage below.

### Finding 3

**File:** `plan_tool/detail.py:2336`

**Summary:** `headings` is recomputed via `_h2_matches_outside_fences(_H2_HEADING_RE,
text)` immediately after the wrapped-response block even though, for
the accepted candidate, `text` is byte-identical to `candidate`, whose
heading set was already computed as `candidate_headings` a few lines
earlier right before the loop's `break`.

**Failure scenario:** `_h2_matches_outside_fences` internally calls
`_fenced_code_spans(text)` (a full line-by-line rescan) plus a regex
`finditer` and a membership check per match — non-trivial work for a
potentially large detail body, executed twice on the identical string
for no functional reason.

**Disposition:** See the 2026-09-10 pass-8 triage below.

### Finding 4

**File:** `plan_tool/detail.py:2287`

**Summary:** The new `line_index_by_offset` map re-derives, via a second
full line-by-line walk, the exact same cumulative-offset accounting
`_fenced_code_spans` just performed internally one line earlier to
produce `spans` — duplicating logic instead of extending
`FencedCodeScan`/`_fenced_code_spans` to expose line boundaries
alongside span offsets.

**Failure scenario:** Not a bug — two independent O(document-length)
walks now exist for one piece of information (line-start offsets). A
future change to how `_fenced_code_spans` counts offsets has to be kept
in sync with this separate hand-rolled copy in `detail.py`.

**Disposition:** See the 2026-09-10 pass-8 triage below.

### Finding 5

**File:** `plan_tool/detail.py:2259`

**Summary:** The new inline comment block violates this repo's
`CLAUDE.md` § "Code comments" terseness rule.

**Failure scenario:** None of the depth (candidate-building rationale,
the last-wrapper-wins policy, the residual-risk carve-out) is pushed to
a maintained doc and cited with a pointer; it was fully inlined, and
had already drifted from what the code actually does (it claimed a
"zero required headings" skip that the implementation didn't perform —
finding 2).

**Disposition:** See the 2026-09-10 pass-8 triage below.

## Review pass 8 triage and repair (2026-09-10)

All 5 findings are **confirmed**. Findings 1 and 2 are behavioral defects
in the pass-7 fix itself, repaired in `00504b68`. Findings 3 and 5 are
fixed in `e13bd34a` as small, same-function, no-risk cleanups. Finding 4 is
**declined**: extracting a shared offset/line-boundary helper for
`_fenced_code_spans` touches a second module's public return shape for a
pure-duplication concern with no observed inconsistency, disproportionate
to this fix.

### Root cause and corrected design

The pass-7 fix bounded each fence-wrapped candidate by the **next raw
fence span's start** (`spans[idx + 1][0]`). This is unsound in general:
`_fenced_code_spans` is a flat, non-nesting scanner, so a same-length
nested example fence inside the real body doesn't just shift the true
wrapper's own span end early (already known and handled since pass-5) —
with **two or more** such nested fences, it also manufactures **extra,
spurious top-level spans** for the later nested fences. Bounding by "the
next span" then lands on one of those spurious entries instead of the
true close.

The fix repartitions the document by **genuine candidate H1 positions**
(H1 lines that are actually preceded by a fence-open line, deduplicated
and sorted) rather than by raw fence spans, and bounds each candidate by
the **next genuine candidate's own start**. This is verified to survive
any number of same-length nested fences inside one candidate's own body
(the rescan-after-excluding-the-opener technique still resolves each
inner pair as matched, regardless of count, as long as the region itself
is bounded correctly), while still correctly excluding a later, separate
wrapper — a genuine second candidate — from bleeding into an earlier
one. Finding 2's fix changes `if not candidate_headings: continue` to
check membership in `_REQUIRED_H2_TOKENS` specifically, matching what the
(now-corrected) comment already claimed.

### Verification

- Two new regression tests pin both confirmed defects: one reproduces the
  exact two-inner-fence input and asserts the complete body round-trips
  with no stub fabricated; the other reproduces a trailing
  non-required-heading decoy and asserts the earlier complete response
  still wins.
- The full pre-existing `TestParseDetailResponse` class, including all
  four prior-round regressions this design must not break (same-length
  single nested fence, no-fallback-to-an-earlier-example, the two pass-7
  cases), passes unchanged.
- `tests/test_detail.py`: `597 passed`.
- Full suite: `uv run pytest tests/ -q -n auto` → `12419 passed, 189
  skipped`, exit 0. A first attempt hit 18 failures confined entirely to
  `tests/test_roadmap_version_promotion.py` — confirmed unrelated and
  transient: all 18 pass in isolation (serial run) and a clean full-suite
  retry reproduced none of them. This matches a recurring pattern of
  unexplained `-n auto`-only failures/crashes observed independently in
  the pass-4 and pass-6 triage attempts; worth a `BUG_BACKLOG.md` entry
  to root-cause rather than continuing to work around it per-round.

### Next review

Convergence remains open. A fresh independent review of
`85b8a19b..e13bd34a` is the next required evidence.

## Review pass 9 — /code-review high findings (2026-09-10)

**Scope:** `85b8a19b..e13bd34a` — the pass-8 fix and cleanup, per that
triage's explicit next-review request.

**Method:** manual analysis with direct execution verification for every
finding. **This is the fifth consecutive round (5, 6, 7, 8, 9) to find a
confirmed defect touching `parse_detail_response`'s wrapper-selection
logic.** Unlike rounds 5–8, this round's findings are not uniformly
self-seeded: findings 2 and 3 were verified (by this session, re-running
them against the pass-8 parent commit `85b8a19b`) to be **pre-existing**,
present before any of the pass-5 through pass-8 fixes touched this
function — they are not regressions from recent work. Finding 1 **is** a
genuine new gap introduced by the pass-8 fix, also verified directly.

### Finding 1 — confirmed regression from pass-8

**File:** `plan_tool/detail.py:2291`

**Summary:** When the document contains only one genuine wrapper H1, the
candidate region is bounded only by end-of-document instead of by the
wrapper's own fence close, so a trailing fenced block with no heading (a
common illustrative decoy) gets merged into the parsed body.

**Failure scenario:** `raw = "Sure, here's the detail file:\n\n```markdown\n<complete
valid 7-section body>```\n\nHere's an example of unrelated fenced
content that happens to close:\n```\nsome trailing example\n```\n"`.
Verified directly by this session: on pre-fix `85b8a19b`,
`parse_detail_response` returns the trimmed body correctly. On
post-fix HEAD (`e13bd34a`), it returns the body with a stray literal
` ``` ` line appended, followed by the decoy paragraph and fragment —
corrupting the persisted detail file with content the model never
intended as part of the response. Root cause: with only one
`h1_start`, `region_end_line = len(lines)`, so the region includes the
real closing fence AND the trailing decoy; the per-region rescan then
treats the real closing fence (now opener-less) as a new opener that
pairs with the decoy's opening fence, leaving the decoy's own closing
fence as the sole "unmatched" boundary instead of the real one.

**Disposition:** See the 2026-09-10 pass-9 triage below.

### Finding 2 — confirmed, pre-existing (not a recent regression)

**File:** `plan_tool/detail.py:2283`

**Summary:** `locate_detail_format_carrier(lines[h1_index])` checks only
whether a single line matches the bare `# text` shape, with no awareness
of fence context, so any `#`-prefixed line inside an unrelated nested
example fence (e.g. a Python/shell comment) is misidentified as a second
genuine wrapper H1, fragmenting one valid response into two incomplete
candidates.

**Failure scenario:** A courtesy-preamble-wrapped, fully valid, all-7-heading
response whose `## Implementation` contains a fenced code example, where
a later fenced example's first line begins with `# ` (e.g. `# This looks
like a heading but is just illustrative prose`), adds that comment line
to the candidate set. Verified directly by this session against both
`85b8a19b` and `e13bd34a`: `parse_detail_response` returns `None` on
**both**, confirming this predates the pass-7/8 fixes and is not
introduced by them.

**Disposition:** _(pending — routed to `BUG_BACKLOG.md`, not this fix's
scope)_

### Finding 3 — confirmed, pre-existing (not a recent regression)

**File:** `plan_tool/detail.py:2247`

**Summary:** The unrelated "lenient fence stripping" step earlier in the
same function (untouched by any pass-5 through pass-8 fix) only strips
the first and last lines of the raw response, so a document consisting of
two adjacent complete fenced wrappers with no preamble text has its
shared boundary fences left as literal stray lines, and the
wrapped-candidate partitioning logic is never entered at all.

**Failure scenario:** `raw = "```markdown\n<complete body1>```\n\n```markdown\n<complete
body2>```"` (two independent, complete, valid wrapped responses back to
back). `parse_detail_response(raw)` returns a single string that is
body1 concatenated with body2, with literal fence-marker lines left in
the middle — because stripping only `lines[0]`/`lines[-1]` leaves the
second body's H1 apparently unwrapped, so `_detail_response_body_start`
finds it directly and the function takes the non-wrapped path, consuming
everything through the end of the raw text. Verified directly by this
session against both `85b8a19b` and `e13bd34a`: reproduces on **both**,
confirming this predates the pass-7/8 fixes.

**Disposition:** _(pending — routed to `BUG_BACKLOG.md`, not this fix's
scope)_

### Finding 4

**File:** `plan_tool/detail.py:2292`

**Summary:** `region_start`/`region_end` are recomputed by re-summing all
line lengths from the start of the document for every candidate (the
same sum computed twice — once as one candidate's end, again as the
next's start), and `h1_starts` de-duplicates via an O(n) `in` scan
immediately before sorting.

**Failure scenario:** Not a bug — needless duplicated work for N
candidates instead of O(1) lookups via a precomputed cumulative-offset
list; real-world detail responses are small so the cost is negligible
today.

**Disposition:** See the 2026-09-10 pass-9 triage below.

### Finding 5 — process finding, not a code defect

**Summary:** Both this diff's commits and the accompanying handoff doc
describe the pass-8 h1-based partitioning as a "structural fix" replacing
a "positional heuristic", but findings 1–3 above show it is still a
positional heuristic — matching any bare `#`-shaped line as a genuine
wrapper H1 regardless of fence context — that a fenced code comment or a
fenceless-heading decoy can defeat. Per this repo's own `CLAUDE.md` ("a
claim that a fix is structural is itself a claim to verify, not a
property a fix earns by intent"), this is round 3+ (pass-7, pass-8, and
now this review) of the same mechanism finding new adversarial inputs,
suggesting the underlying approach — not just its latest edge case —
needs reconsideration.

**Disposition:** **Resolved by user decision.** Presented to the user as a
three-way choice (keep patching / redesign with an explicit sentinel / ship
as-is and stop); the user selected the sentinel redesign. See the
2026-09-10 pass-9 triage below.

### Finding 6

**File:** `plan_tool/detail.py:2266`

**Summary:** The comment defers the deliberately-accepted
"last-wrapper-wins" residual entirely to `TestParseDetailResponse` rather
than stating it inline or in a maintained doc, contrary to `CLAUDE.md`'s
own "say deliberately not X, with the reason, instead of leaving X out"
rule.

**Failure scenario:** A reader of `detail.py` who doesn't also open
`test_detail.py` has no way to learn this known limitation exists.

**Disposition:** See the 2026-09-10 pass-9 triage below.

## Review pass 9 triage and repair (2026-09-10)

**This round did not end in another patch.** Presented to the user as a
three-way scope decision — keep patching, redesign with an explicit
non-positional sentinel, or ship the pass-8 state as-is and stop — the
user selected the redesign. `4dbb2cc0` implements it.

### What changed

`parse_detail_response`'s entire candidate-partitioning/selection block
(finding 1's home, and the mechanism findings 5 and the round-7/8 findings
before it all traced to) is **deleted**, not patched again. In its place:
an explicit sentinel pair,
`<!-- plan-tool:detail-response-start -->` / `<!-- plan-tool:detail-response-end -->`,
matching this codebase's existing HTML-comment marker family (the format
version marker, the deferrals envelope). The model uses it when it can't
avoid adding commentary or a fence around its answer; extraction between
the two markers is exact substring slicing — a preamble before the start
marker or trailing commentary after the end marker is excluded
unconditionally, regardless of its own shape, because nothing about the
extraction infers document structure. A response that is neither a plain
unwrapped title (the unaffected, common path) nor sentinel-delimited is
unparseable and triggers the existing retry mechanism, whose reprompt now
teaches the sentinel explicitly. The main authoring prompt gained the same
guidance so a well-behaved model doesn't need a failed first attempt to
learn about it.

### Finding dispositions

1. **Closed by the redesign**, not fixed in place. The candidate region
   this finding's boundary lived in no longer exists; extraction is now a
   direct substring slice with no "region" to under- or over-bound.
2. **Confirmed pre-existing, out of scope.** Filed to `BUG_BACKLOG.md`
   ("`parse_detail_response` misreads a `#`-prefixed comment inside a
   nested example fence as a genuine wrapper H1"). Untouched by this
   redesign — it lives in `_detail_response_body_start`/
   `locate_detail_format_carrier`, the plain-path machinery this fix left
   alone, and reproduces identically before and after.
3. **Confirmed pre-existing, out of scope.** Filed to `BUG_BACKLOG.md`
   ("`parse_detail_response` merges two adjacent complete wrapped
   responses into one corrupted body"). Untouched by this redesign — it
   lives in the leading/trailing bare-fence-stripping step, which this fix
   kept unchanged and only extended (`_strip_bare_fence_lines`) to also
   apply to a sentinel-extracted body.
4. **Moot.** The offset/dedup computation this finding named no longer
   exists; the redesign has no per-candidate loop to duplicate work across.
5. **Resolved by the user's decision**, recorded above and in the Status
   section. This is the one finding in this round that named a scope
   decision rather than a code defect, and it was surfaced rather than
   auto-applied, per this project's own "Audit the why, not the what" rule.
6. **Moot.** The specific comment this finding named no longer exists; the
   new docstring documents the sentinel, the fail-closed default, and
   cites this handoff by date and review-pass range rather than only a
   test class.

### Verification

- Nine tests in `TestParseDetailResponse` are new or rewritten: sentinel
  extraction with a preceding fenced example, with two same-length nested
  fences, with a trailing illustrative snippet after the end marker; the
  now-closed pass-8 residual (a near-complete trailing decoy, without a
  sentinel, is unparseable rather than silently winning); a general
  ambiguous-multi-wrapper-without-sentinel case; and a test pinning that a
  sentinel-shaped phrase appearing inline (not alone on its own line) is
  not mistaken for a real boundary.
- `tests/test_detail.py`: `599 passed`.
- Full suite: `uv run pytest tests/ -q -n auto` → `12421 passed, 189
  skipped`, exit 0.

### Next review

Convergence remains open. A fresh independent review of
`e13bd34a..4dbb2cc0` is the next required evidence — this time reviewing a
genuinely different mechanism, not another patch to the one five
consecutive rounds already touched.

## Review pass 10 — /code-review high findings (2026-09-10)

**Scope:** `e13bd34a..4dbb2cc0` — the sentinel redesign, per that fix's
own explicit next-review request.

**Method:** 10 parallel finder angles; every strong candidate was verified
by direct execution against both the diff's HEAD and its parent commit
(including a temporary worktree at the parent commit to distinguish new
regressions from the two pre-existing, already-backlogged bugs). **The
headline finding: the sentinel's primary, non-adversarial use case —
bracketing a response with no inner code fence — was broken**, confirmed
with a direct reproduction, not just static tracing.

### Finding 1 — most severe

**File:** `plan_tool/detail.py:2286` (pre-fix line numbering)

**Summary:** When the wrapper sentinel brackets content that is not
itself inside a code fence, `_detail_response_body_start` finds the real
unfenced H1 first, so the plain (non-sentinel) branch runs and slices to
the end of the raw text instead of stopping at the end marker — the
literal `<!-- plan-tool:detail-response-end -->` line and any trailing
commentary get embedded in the persisted detail file.

**Failure scenario:** Verified by direct execution: `raw = "Sure, here you
go:\n\n<!-- plan-tool:detail-response-start -->\n# Title\n...all 7
sections...\n<!-- plan-tool:detail-response-end -->\n\nLet me know if you
need anything else!"` → `parse_detail_response` returns a body ending in
"...- returns 42\n<!-- plan-tool:detail-response-end -->\n\nLet me know if
you need anything else!", directly contradicting the function's own
docstring and `DETAIL_FORMAT.md`'s claim that content after the end marker
is "excluded unconditionally".

**Disposition:** See the 2026-09-10 pass-10 triage below.

### Finding 2

**File:** `plan_tool/detail.py:2470` (pre-fix line numbering)

**Summary:** `parse_structured_detail_response`'s interaction with the
sentinel is broken in both possible placements of the mandatory trailing
deferrals envelope, which every real detail response must include.

**Failure scenario:** Verified by direct execution of both orderings: with
the deferrals envelope placed after the sentinel end-marker (the literal
reading of "immediately after the last line of the file"), the returned
body is corrupted with the literal end-marker line embedded at its tail
(same root cause as finding 1). With the deferrals envelope placed before
the end-marker (inside the bracketed "file"), `_DETAIL_DEFERRALS_RE`'s
end-of-string anchor no longer matches (the end-marker line follows it),
so the entire otherwise-valid response is rejected (`None`). Since every
real step response ends with this envelope, the sentinel was broken for
its actual intended everyday use, not just adversarial edge cases.

**Disposition:** See the 2026-09-10 pass-10 triage below.

### Finding 3

**File:** `plan_tool/detail.py:2289` (pre-fix line numbering)

**Summary:** `_DETAIL_RESPONSE_WRAPPER_RE.search()` used a lazy,
unanchored match, so it paired with the leftmost start/end marker pair in
the text — an earlier decoy or illustrative sentinel pair won over the
real, later, correctly-wrapped answer.

**Failure scenario:** Verified by direct execution: a response that first
demonstrates the sentinel syntax (a decoy `<!-- start -->\n# Bad\n<!--
end -->`) before the real bracketed answer caused `parse_detail_response`
to match the decoy pair and return `None`, discarding a fully valid,
complete response — reintroducing the exact "positional heuristic defeated
by adversarial input" class this rewrite was built to eliminate, just
moved from fence detection onto the sentinel markers themselves.

**Disposition:** See the 2026-09-10 pass-10 triage below.

### Finding 4

**File:** `plan_tool/detail.py:2236` (pre-fix line numbering)

**Summary:** The sentinel marker-line regex anchors didn't tolerate a
trailing `\r`, unlike the `\r?\n` used elsewhere in the same pattern, so a
CRLF-terminated sentinel line never matched.

**Failure scenario:** Verified by direct execution: a fully compliant,
correctly sentinel-wrapped, fenced response using CRLF line endings
throughout returned `None` from `parse_detail_response` — a compliant
response using Windows-style line endings was unconditionally rejected.

**Disposition:** See the 2026-09-10 pass-10 triage below.

### Finding 5

**File:** `plan_tool/detail.py:2231` (pre-fix line numbering)

**Summary:** `_strip_bare_fence_lines`'s trailing-fence check required
exact equality to three backticks, while the leading check accepted any
`startswith("\`\`\`")` run length — a 4-or-more-backtick fence had its
opener stripped but not its closer.

**Failure scenario:** Verified by direct execution: a response wrapped in
a 4-backtick fence with no sentinel was accepted and returned the body
with a stray literal 4-backtick line appended, silently succeeding with
corrupted output where the new contract demands either a clean parse or a
hard reject.

**Disposition:** See the 2026-09-10 pass-10 triage below.

### Finding 6 — process finding about this same round's own filing

**File:** `BUG_BACKLOG.md:157` (as filed in the pass-9 triage)

**Summary:** The "misreads a `#`-prefixed comment inside a nested example
fence" entry, added in the pass-9/redesign commit, was not verified
against that same diff's own resulting HEAD and describes a failure mode
already resolved as a side effect of the same commit's rewrite, while its
"Fix" section says a non-positional sentinel is needed — exactly what that
diff ships.

**Failure scenario:** Verified by direct execution: the entry's own
described repro returns a fabricated-stub/fragmented result on the parent
commit `e13bd34a`, but cleanly returns `None` (fail-closed, not corrupted)
at the redesign's HEAD `4dbb2cc0` — the entry's "verified directly against
both `85b8a19b` and `e13bd34a`" claim never checked the state it was
committed alongside, leaving a stale bug report and an unresolved
cross-reference to a fix that already shipped.

**Disposition:** See the 2026-09-10 pass-10 triage below.

### Finding 7

**File:** `plan_tool/detail.py:2260` (pre-fix line numbering)

**Summary:** `parse_detail_response`'s docstring inlined a long historical
narrative (the positional-heuristic failure history and "review passes
5-9" citation) duplicating `DETAIL_FORMAT.md`'s own new rule-3 prose
almost verbatim, violating this repo's own `CLAUDE.md` § "Code comments"
terseness rule.

**Disposition:** See the 2026-09-10 pass-10 triage below.

### Finding 8

**File:** `plan_tool/detail.py:2221` (pre-fix line numbering)

**Summary:** `_strip_bare_fence_lines` hand-rolled bare-fence-line
detection instead of reusing the already-imported `_fenced_code_spans` or
the repo's canonical fence-line regexes (`scope_fence.py`), which
CLAUDE.md calls out as the preferred fence-aware scanner.

**Failure scenario:** Not a crash, but a missed-reuse cost: the hand-rolled
check couldn't recognize `~~~` fences, indented fences, or (per finding 5)
longer backtick runs — all of which the existing, tested primitives
already handle correctly elsewhere in the codebase.

**Disposition:** See the 2026-09-10 pass-10 triage below.

### Finding 9

**File:** `plan_tool/detail.py:2236` (pre-fix line numbering)

**Summary:** A third, differently-styled HTML-comment sentinel convention
was introduced in the same file that already has two others
(`plan-tool:detail-format-version:` colon-style and
`plan-tool-detail-deferrals` dash-style), with no shared parsing helper or
documented single convention.

**Failure scenario:** Cleanup/maintenance cost only: three near-identical
hand-rolled comment-marker regexes now coexist in one module with no
consolidation, and a future fourth marker has three inconsistent
precedents to choose from.

**Disposition:** See the 2026-09-10 pass-10 triage below.

## Review pass 10 triage and repair (2026-09-10)

Findings 1-6 are **confirmed** and repaired in `57cbc08d`. Finding 7 is
**confirmed** and fixed (docstring trimmed to a pointer plus the one
non-obvious invariant). Finding 8 is **confirmed and substantially
addressed** as a side effect of fixing findings 4/5. Finding 9 is
**declined**: consolidating three semantically different marker kinds
(an integer version, a JSON envelope, a plain boundary pair) into one
shared parser is a broader refactor with no measured defect behind it,
disproportionate to this fix.

### What changed

- **Findings 1-3 (selection correctness):** the sentinel is now checked
  **unconditionally, before** the plain path, whenever exactly one of
  each marker is present — not only when the plain path fails to find a
  title. Zero, or more than one, of either marker is treated as ambiguous
  and refused (`None`) rather than resolved by picking a leftmost match.
  This closes finding 1 directly, and finding 2 as a consequence (the
  deferrals-after-end-marker case is the same root cause); both prompts
  and `DETAIL_FORMAT.md` were also clarified so the deferrals envelope's
  placement (always after the end marker, never inside it) is
  unambiguous going forward.
- **Findings 4-5, and 8 (fence-line recognition):** `_strip_bare_fence_lines`
  now reuses this module's own imported, tested `_FENCE_OPEN_RE`/
  `_FENCE_CLOSE_RE` (from `scope_fence.py`) instead of a narrower
  hand-rolled `startswith`/`==` check, fixing CRLF tolerance and
  longer/tilde fence recognition as one change rather than three separate
  patches.
- **Finding 6:** the stale `BUG_BACKLOG.md` entry is removed, re-verified
  against the current HEAD immediately before removal (not merely
  re-asserted). The sibling entry ("merges two adjacent complete wrapped
  responses") remains — re-verified separately to still reproduce
  identically at this same HEAD, so it stays filed.
- **Finding 7:** the docstring now states the one non-obvious invariant
  (sentinel checked before the plain path, unconditionally) in a few
  lines and points to `DETAIL_FORMAT.md` rules 1-4 for the rest, rather
  than restating the full contract and its provenance history inline.

### Verification

- Six new regression tests pin all five confirmed defects: sentinel
  wrapping an unfenced body without leaking the end marker; the
  deferrals-envelope interaction; two ambiguous sentinel pairs; CRLF
  tolerance; a 4-backtick fence parsing cleanly.
- `tests/test_detail.py`: `604 passed`.
- Full suite: `uv run pytest tests/ -q -n auto` → `12426 passed, 189
  skipped`, exit 0.

### Next review

Convergence remains open. A fresh independent review of
`4dbb2cc0..57cbc08d` is the next required evidence.

## Review pass 11 — /code-review high findings (2026-09-10)

**Scope:** `4dbb2cc0..57cbc08d` — the pass-10 fix, per that fix's own
explicit next-review request.

**Method:** 10 parallel finder angles converged on the same headline
finding; every candidate was verified by direct execution, several
cross-checked against the parent commit via a temporary git worktree to
confirm regression vs. pre-existing status.

### Finding 1 — headline

**File:** `plan_tool/detail.py:2281` (pre-fix line numbering)

**Summary:** The new wrapper-sentinel marker search
(`_DETAIL_RESPONSE_START_LINE_RE`/`_END_LINE_RE.finditer(text)`) scans raw
text with no fenced-code exclusion, unlike the sibling `_matches_outside_fences`/
`_detail_response_body_start` in the very same file — so any well-formed,
unwrapped detail response containing even one incidental occurrence of a
marker line (e.g. a fenced example in `## Implementation` illustrating the
sentinel syntax) is hard-rejected.

**Failure scenario:** Confirmed regression via git worktree diff against
parent commit `4dbb2cc0`: a fully valid, unwrapped, all-seven-heading
detail response whose `## Implementation` section contains a fenced code
block showing the sentinel syntax as illustrative text (each alone on its
own line) parses correctly at `4dbb2cc0` but returns `None` at HEAD
(`57cbc08d`). This reintroduces, under new syntax, the exact defect class
the pass-9 commit's own message and `DETAIL_FORMAT.md` claim to have
eliminated with a "non-positional" boundary.

**Disposition:** See the 2026-09-10 pass-11 triage below.

### Finding 2

**File:** `plan_tool/detail.py:2468` (pre-fix line numbering)

**Summary:** `parse_structured_detail_response` computes `match.start()`
against `raw.strip()` but slices the un-stripped `raw` with it, silently
truncating the persisted detail body whenever the raw response has any
leading whitespace.

**Failure scenario:** Confirmed repro: `raw = "\n\n" + <well-formed body>
+ <deferrals envelope>`. `_DETAIL_DEFERRALS_RE.search(raw.strip())` finds
`match.start()` relative to the 2-char-shorter stripped string;
`raw[: match.start()]` then cuts 2 characters short of the real boundary,
so `parsed.body` silently ends short — no error, no rejection, a
`ParsedDetailResponse` is returned with corrupted content written to disk.
Reachable any time raw model output starts with leading whitespace/blank
lines.

**Disposition:** See the 2026-09-10 pass-11 triage below.

### Finding 3

**File:** `plan_tool/detail.py:2465` (pre-fix line numbering)

**Summary:** `_DETAIL_DEFERRALS_RE.search` is a leftmost, DOTALL-greedy
match anchored only at end-of-string, so a document that legitimately
quotes/illustrates the deferrals-envelope syntax before the real trailing
envelope locks onto the earlier occurrence and its greedy payload group
swallows through to the true end.

**Failure scenario:** Confirmed repro: a well-formed response whose `##
Why` section shows a fenced illustrative example of the deferrals-envelope
syntax, followed by the real envelope at the true end. `match.start()`
lands inside the illustrative example instead of the real envelope's
position; the greedy payload captures everything through to the real end,
which fails `json.loads`, and `parse_structured_detail_response` returns
`None` for an otherwise fully compliant response.

**Disposition:** See the 2026-09-10 pass-11 triage below.

### Finding 4

**File:** `plan_tool/detail.py:2236` (pre-fix line numbering)

**Summary:** `_strip_bare_fence_lines`'s reuse of `_FENCE_OPEN_RE`/
`_FENCE_CLOSE_RE` (which additionally recognize `~~~` and 4+-backtick
fences, unlike the old literal ``` string checks) extends the pre-existing
blind strip-first/last-fence-shaped-line behavior to those new fence
styles, silently corrupting real document content that legitimately starts
or ends with such a fence.

**Failure scenario:** Confirmed regression via parent-commit diff: a
document ending with a legitimate `~~~`-fenced example (e.g. `## Tests`
showing command output) as its true last content has that trailing `~~~`
line dropped at HEAD but not at the parent commit, leaving a
dangling/unterminated fence in the persisted body.

**Disposition:** See the 2026-09-10 pass-11 triage below.

### Finding 5

**File:** `plan_tool/detail.py:2289` (pre-fix line numbering)

**Summary:** The sentinel branch only strips a bare fence line from the
extracted body; it never applies `_detail_response_body_start`'s
preamble-skipping logic, so commentary placed *inside* the brackets before
the `#` title — the exact scenario the sentinel exists to accommodate per
its own docstring — is hard-rejected.

**Failure scenario:** Confirmed repro: a sentinel-wrapped response with
"Sure, here you go:" as commentary before the title, inside the brackets,
returns `None` at HEAD.

**Disposition:** See the 2026-09-10 pass-11 triage below.

### Findings 6-9 (documentation/duplication/hygiene)

Findings 6-9 named: `DETAIL_FORMAT.md`'s rule 3.1 overstating the
"non-positional boundary" guarantee given finding 1; a reuse gap (the
marker search reinventing fence-blind matching instead of calling the
module's own `_matches_outside_fences`); a test-coverage gap (no existing
test covered "a marker occurrence inside a fenced span"); and the two
near-identical start/end marker regexes risking independent drift with no
shared factory.

**Disposition:** See the 2026-09-10 pass-11 triage below.

## Review pass 11 triage and repair (2026-09-10)

Findings 1-5 are **confirmed** and repaired in `4d18ecf5`. Findings 6-8 are
**confirmed and addressed** as a consequence of that same repair (the
`DETAIL_FORMAT.md` overstatement no longer applies once finding 1 is
fixed; the reuse gap is closed by extending — not reinventing —
`_matches_outside_fences`'s family; the missing test-coverage gap is
closed by new regression tests). Finding 9 (near-identical regex pair, no
shared factory) is **declined**: a factory for two three-line regexes
differing only in one literal token is not proportionate cleanup on its
own.

### A self-caught regression during this round's own repair

A first fix attempt (applying the existing `_matches_outside_fences`
helper directly to the sentinel and deferrals markers) was tested against
the existing suite **before commit** and found to introduce a new
regression: excluding "anything inside a fence" also excludes a fence
scanner artifact. A same-length nested example fence inside a
sentinel-wrapped body (already known since pass-8) can make the true
closer surface as a separate, later, *unmatched-to-end-of-text* span — the
scanner's single, non-nesting pass — and naive fence-exclusion treated
that dangling artifact as a real fence, swallowing the sentinel's own end
marker and reproducing pass-8's original defect under the new fix. This
was caught by the existing `test_sentinel_wrapped_body_survives_two_same_length_inner_fences`
regression test (pass-10) failing locally, **before** any commit landed —
the loop's own regression coverage did its job. The corrected design
(below) resolves both findings simultaneously rather than trading one for
the other.

### Corrected design

`_matches_outside_closed_fences` (new) distinguishes genuinely-closed
fence spans from the scanner's trailing unmatched-to-EOF pseudo-span,
using `FencedCodeScan.unmatched_opening` to drop that one artifact entry
before filtering. Used for the sentinel and deferrals markers, which can
sit after a wrapping fence; H2 headings keep the stricter, unmodified
`_matches_outside_fences`, having no equivalent wrapping interaction.
`_strip_bare_fence_lines`'s trailing-strip logic uses the same
closed-vs-artifact distinction, conditioned on whether the document also
opens with a fence: if it does (the whole-response-wrap hypothesis, where
the artifact chain can occur), the trailing strip stays unconditional; if
it doesn't, a trailing fence-shaped line is protected unless it is itself
provably part of an already-complete span that reaches end-of-text from a
non-zero start (real, embedded content) — except when it is genuinely
unmatched (no opener anywhere), preserving the original lone-closer
leniency finding 4 would otherwise have broken. The deferrals-envelope
offset bug (finding 2) and greedy-match bug (finding 3) are fixed together
via one shared `_find_real_deferrals_match` helper — anchoring the
full, end-anchored regex at the position of the *last* non-fenced
marker-start line, rather than searching the whole text with the greedy
payload regex directly — used by both existing call sites (closing the
same finding at its second, previously separate, occurrence). The sentinel
branch now runs `_detail_response_body_start` on its own extracted content
before falling back to using it as-is, gaining the same preamble-skip
leniency the plain path already had.

### Verification

- Eight new regression tests pin all five confirmed defects plus the
  self-caught regression's corrected behavior: a fenced illustrative
  example of the sentinel syntax no longer hijacks a plain response;
  deferrals-offset consistency with leading whitespace; a fenced
  illustrative deferrals example no longer hijacks the real envelope; a
  legitimate trailing fence with no leading wrap survives; commentary
  inside the sentinel's own brackets is tolerated.
- The full pre-existing `TestParseDetailResponse` class — every
  pass-5-through-pass-10 regression this design must not break — passes
  unchanged.
- `tests/test_detail.py`: `609 passed`.
- Full suite: `uv run pytest tests/ -q -n auto` → `12431 passed, 189
  skipped`, exit 0. Two intermediate attempts hit the already-backlogged
  `tests/test_roadmap_version_promotion.py` flakiness (a fourth
  occurrence) and one process was killed by the OS for low system memory
  under concurrent load from multiple Claude sessions on this shared
  machine — both strengthened the existing `BUG_BACKLOG.md` entry rather
  than blocking this fix.

### Next review

Convergence remains open. A fresh independent review of
`57cbc08d..4d18ecf5` is the next required evidence.

## Review pass 12 — /code-review high findings (2026-09-10)

**Scope:** `57cbc08d..4d18ecf5` — the pass-11 fix, per that fix's own
explicit next-review request.

**Method:** `/code-review --effort high --range 57cbc08d..4d18ecf5` run as
a background agent per the code-review-loop skill (179 tool uses, ~29
minutes); every finding below is stated by the review as verified by
direct execution against the working tree, not static tracing alone.

### Finding 1

**File:** `plan_tool/detail.py:341`

**Summary:** `_matches_outside_closed_fences` unconditionally drops the
trailing dangling-to-EOF span from the exclusion set whenever
`unmatched_opening` is set, so a genuinely unterminated (not merely a
scanner-artifact) code fence anywhere in the response makes everything
after it — including a coincidental marker-shaped line — count as real,
unfenced text.

**Failure scenario:** A fully valid 7-section response whose `## Tests`
section shows an illustrative sentinel example inside a fence the model
forgot to close, containing a line
`<!-- plan-tool:detail-response-end -->`: `parse_detail_response` finds
one `ends` match and zero `starts`, hits `len(starts) != 1`, and returns
`None`. Verified by direct execution: the same body without the
unterminated fence parses cleanly; with it, `parse_detail_response`
returns `None`, wrongly rejecting a complete, correct response.

**Disposition:** **Confirmed, accepted as a residual rather than fixed.**
Investigation confirmed the review's repro fails closed (returns `None`,
triggering a retry) rather than corrupting content, for a genuinely
ambiguous compound case: distinguishing a real unterminated fence from a
same-length-nested-fence scanner artifact — the mechanism finding 6/8's
history in this same loop is built around — needs a nesting-aware
scanner, which does not exist anywhere in this codebase (see finding 8's
disposition, which empirically rules out the review's own suggested
fix). Patching this exact function a sixth time on a heuristic with no
better foundation than the five that preceded it was rejected in favor
of documenting and testing the residual:
`test_marker_inside_a_genuinely_unterminated_fence_is_a_known_residual`
pins the fail-closed outcome, and `DETAIL_FORMAT.md` rule 3.1 now states
it as an accepted, narrow residual rather than silently carrying it.

### Finding 2

**File:** `plan_tool/detail.py:2630`

**Summary:** `_strip_structural_findings_preserving_deferrals` excises
`## Structural findings` via `_STRUCTURAL_BLOCK_RE.sub()` (imported from
`granularity.py`), which is not fence-aware, even though this same diff
added fence-awareness for the sibling sentinel/deferrals markers a few
lines below in the same function.

**Failure scenario:** A response whose `## Implementation` legitimately
fences an illustrative example containing the literal heading
`## Structural findings`: the regex spans from that heading to the next
`^#{1,6}` heading or EOF and deletes the example's closing fence line
along with the matched text, leaving a phantom unterminated fence. That
phantom fence then hides every later real H2 section from
`parse_detail_response`'s H2 check. Verified by direct execution: the
stripped output ends with an unclosed fence swallowing `## Tests` and
the deferrals envelope, and `parse_structured_detail_response` on the
result returns `None` for an otherwise fully valid response.

**Disposition:** **Confirmed, pre-existing, out of scope.** The function
predates the sentinel-redesign range under review; the defect is real
but unrelated to this round's fix. Filed to `BUG_BACKLOG.md` rather than
fixed here, per round 9's precedent for pre-existing bugs surfaced
incidentally by a review scoped to different work.

### Finding 3

**File:** `plan_tool/detail.py:2856` (also `plan_tool/detail.py:3017`)

**Summary:** The raw substring shortcut
`f"<!-- {_DETAIL_DEFERRALS_MARKER}" in raw` (duplicated at a second call
site) is not fence-aware, unlike the newly fence-aware
`_find_real_deferrals_match` it sits beside — the fence-blindness fix
from this diff was not swept to this sibling check.

**Failure scenario:** With `require_deferral_envelope=False`, a response
whose body legitimately fences an illustrative example of the
deferrals-envelope syntax (no real trailing envelope):
`parse_structured_detail_response` correctly returns `None`
(fence-aware), but the substring check is still `True`, forcing
`body = None` and rejecting a response `parse_detail_response(raw)` would
have accepted cleanly. Verified by direct execution.

**Disposition:** **Confirmed, pre-existing, out of scope.** Both call
sites predate this range. Filed to `BUG_BACKLOG.md`, same as finding 2.

### Finding 4

**File:** `plan_tool/detail.py:2315`

**Summary:** `_strip_bare_fence_lines`'s "document opens with a fence"
branch still strips the trailing fence-close line unconditionally,
unlike the sibling "no leading fence" branch this same diff just added
protection to — the diff's stated fix ("distinguish real fenced content
from scanner artifacts") only covers one of the two branches.

**Failure scenario:** A response wrapped in an outer fence that is
itself never closed (a documented common model failure mode) whose
`## Tests` section legitimately ends in its own complete fenced example:
the real closing fence of that Tests example gets stripped, persisting
an unterminated code fence to disk. Combined with any single stray
fence-shaped line earlier in the body, `_detail_response_body_start`'s
own unguarded scan then treats the rest of the document as fenced,
hiding all required H2 headings and rejecting a fully valid response
outright. Both variants verified by direct execution; the truncation
variant reproduces identically on the pre-diff parent commit `57cbc08d`,
confirming the fix was never extended to this branch.

**Disposition:** **Confirmed, fixed.** A closer can only close a
matching-character opener — a CommonMark fact, not a heuristic — so
`_strip_bare_fence_lines` now compares the leading fence's character
against the trailing candidate's: a different-character trailing fence
is protected as real content, while a same-character one keeps the
existing, correct, artifact-tolerant unconditional strip.
`test_never_closed_leading_fence_preserves_a_different_character_trailing_fence`
pins the fix.

### Finding 5

**File:** `plan_tool/granularity.py:466`

**Summary:** `parse_mixed_step_findings`'s `_STRUCTURAL_BLOCK_RE.search(raw)`
(called from `plan_tool/detail.py` on the raw response before the purity
strip) shares the same non-fence-awareness as finding 2, so it can lift a
MIXED-STEP bullet out of a purely illustrative fenced example.

**Failure scenario:** A response whose `## Implementation` fences an
example containing `## Structural findings\n\n- MIXED-STEP: ...` for
illustrative purposes generates a real `granularity-split`
medium-severity `Recommendation` even though the model never flagged an
actual mixed-step issue. Verified by direct execution:
`parse_mixed_step_findings` returns a populated `Recommendation` for such
input.

**Disposition:** **Confirmed, pre-existing, out of scope.** Predates this
range and shares its root cause with finding 2 rather than this round's
work. Filed to `BUG_BACKLOG.md`.

### Finding 6

**File:** `plan_tool/detail.py:2310`

**Summary:** `start > 0` in
`has_embedded_trailing_fence = any(end == len(text) and start > 0 for start, end in closed_spans)`
is dead: this code only runs after already confirming `lines[0]` does not
match `_FENCE_OPEN_RE`, so no span in `closed_spans` can ever start at
offset 0.

**Failure scenario:** Not a crash — a future reader could believe
`start > 0` is filtering a real case when the guard above already makes
that structurally impossible; independently flagged by four separate
review angles.

**Disposition:** **Confirmed, fixed as a side effect of finding 4's
repair.** The character-comparison rewrite replaced this branch
entirely; the dead condition no longer exists in the new code.

### Finding 7

**File:** `plan_tool/detail.py:323`

**Summary:** `_matches_outside_closed_fences` duplicates nearly the
entire body of `_matches_outside_fences`, differing only in whether the
trailing unmatched span is dropped from the exclusion set.

**Failure scenario:** A future fix to the span-containment filter has to
be found and applied in two places by hand; `tests/test_duplication.py`'s
AST-normalized duplicate guard doesn't currently catch this pair only
because the one differing line breaks its exact-match comparison. Should
be one function parameterized by e.g. `keep_trailing_unmatched: bool`.

**Disposition:** **Confirmed, fixed.** The two functions are consolidated
into one, `_matches_outside_fences(pattern, text, *, keep_trailing_unmatched=False)`,
exactly as the finding's own suggested remedy states. Every call site is
updated; `grep` confirms no remaining reference to the old name.

### Finding 8

**File:** `plan_tool/scope_fence.py:161`

**Summary:** Three consecutive rounds (per the commit history) have each
patched a caller-side heuristic in `detail.py` rather than the root
cause: `_fenced_code_spans` does a single-pass, non-nesting scan that
misreads a same-length nested fence as closing its parent early, and the
codebase already has a sibling scanner (`jira_grade.fenced_spans` +
`review._outside_fences`) built for exactly this reuse purpose that was
never checked or reused here.

**Failure scenario:** Each new marker kind added to `detail.py` (three
now coexist) needs its own caller to correctly reason about
`unmatched_opening`, and this round's own commit message documents that a
first attempt at exactly this reasoning was already wrong once before
landing — a self-validating or nesting-aware scanner would remove the
need to get this right at every caller.

**Disposition:** **Refuted.** Tested directly against the exact
same-length-nested-fence case this finding names: `jira_grade.fenced_spans`
does **not** correctly handle that nesting either — it fails differently,
treating real markdown content as fenced. The suggested root fix does not
exist anywhere in this codebase to reuse. This is the review-time form of
this project's own "verify a remedy's justification against the code"
rule: a plausible-sounding reuse suggestion was checked and found false
before any code changed on its authority.

### Finding 9

**File:** `DETAIL_FORMAT.md:266`

**Summary:** Rule 3.1 still states "Extraction is a substring slice
between the two markers, not an inference," but `parse_detail_response`'s
sentinel branch now runs `_detail_response_body_start` on the bracketed
content to skip preamble before the title — performing exactly the
inference the doc says extraction is not — and the doc was not updated
alongside the code.

**Failure scenario:** A reader or future audit trusting `DETAIL_FORMAT.md`'s
literal claim would not expect or review for the preamble-skip behavior
inside the sentinel brackets, violating this repo's own "Documentation is
forward-looking" mandate.

**Disposition:** **Confirmed, fixed.** Rule 3.1 now states that locating
the markers excludes fenced occurrences, describes the accepted residual
from finding 1, and no longer overstates extraction as a pure substring
slice with no inference involved in locating the boundary.

### Finding 10

**File:** `DETAIL_FORMAT.md:245`

**Summary:** Rule 2 ("A leading fence line and a trailing one are each
stripped independently") no longer matches the actual, much more
conditional/asymmetric behavior `_strip_bare_fence_lines` now implements,
and this diff didn't update the doc.

**Failure scenario:** A reviewer relying on the doc's simple description
would not predict the conditional logic or the corruption bug it enables
(finding 4), misjudging the fence-stripping contract when reviewing or
extending this code.

**Disposition:** **Confirmed, fixed.** Rule 2 now describes the
conditional trailing-strip contract, including the character-matching
rule finding 4 adds.

### Finding 11

**File:** `plan_tool/detail.py:326` (also `plan_tool/detail.py:2287-2298`)

**Summary:** `_matches_outside_closed_fences`'s docstring and
`_strip_bare_fence_lines`'s docstring each run 6-12+ lines walking
through the scanner-artifact scenario in full, violating this repo's own
`CLAUDE.md` "## Code comments" rule to keep docstrings terse and cite a
maintained doc instead of inlining a long block.

**Failure scenario:** This reasoning exists only in code comments that
will rot independently of `DETAIL_FORMAT.md` (already drifting per
findings 9-10) — the exact block-comment-rot failure mode the rule exists
to prevent, reintroduced one round after this same handoff's pass-10
finding 7 was fixed for the identical pattern.

**Disposition:** **Confirmed, fixed.** Both docstrings are trimmed to a
line or two pointing at `DETAIL_FORMAT.md` rule 2/3.1 for the full
contract.

### Findings 12, 13, 15 (declined)

**Finding 12** (`plan_tool/detail.py:2369`): `parse_detail_response`'s
sentinel branch duplicates the plain branch's identical
`_strip_bare_fence_lines` → `_detail_response_body_start` → slice
sequence. **Finding 13** (`plan_tool/detail.py:2361`):
`parse_detail_response` re-runs the full fence scan multiple times per
call instead of computing one scan and threading it through. **Finding
15** (`plan_tool/scope_fence.py:53`): `FencedCodeScan.unmatched_opening`
carries a different meaning at this diff's two new call sites (presence
means "trust the content that follows") than at roughly a dozen
pre-existing ones (presence means "malformed, reject"), and a named
derived accessor would remove the ambiguity.

**Disposition:** **Declined, all three.** None names a behavioral
defect — each is a duplication, efficiency, or API-clarity concern with
a plausible but unmeasured remedy. This exact function
(`parse_detail_response` and its immediate helpers) has now regressed in
five consecutive review rounds (5, 6, 7, 8, 9) from changes made to it
for reasons that were not behavioral defects at the time, and this
round's own two genuine fixes (findings 4 and 7/14) already carry real
risk to the same code. Declining further non-defect edits to the same
hot path — rather than reaching for the more general or more "complete"
version of a fix — matches this project's own "close the fix with the
smallest change that makes the finding true" rule.

### Finding 14

**File:** `plan_tool/detail.py:2305`

**Summary:** The identical three-line phantom-span derivation
(`scan = _fenced_code_spans(text); fenced_spans = scan.spans[:-1] if scan.unmatched_opening is not None else scan.spans`)
is duplicated verbatim between `_matches_outside_closed_fences` and
`_strip_bare_fence_lines`.

**Failure scenario:** A future correction to the phantom-opener
heuristic (e.g. to also guard finding 1's genuinely-unterminated-fence
case) has to be found and updated in both copies by hand.

**Disposition:** **Confirmed, fixed.** Extracted into a shared
`_fence_spans(text, *, keep_trailing_unmatched=False)` helper, used by
both the consolidated `_matches_outside_fences` (finding 7) and
`_strip_bare_fence_lines`.

## Review pass 12 triage and repair (2026-09-10)

The 15 submitted findings resolve to: 2 fixed as genuine defects in
round 11's own work (findings 4, 6), 1 confirmed but accepted as a
documented, tested residual rather than patched again (finding 1), 3
confirmed pre-existing bugs routed to `BUG_BACKLOG.md` as out of scope
for this range (findings 2, 3, 5), 1 refuted after direct verification
(finding 8 — the suggested root-cause reuse target does not actually
work), 2 duplication findings fixed together by consolidation (findings
7, 14), 2 documentation-drift findings fixed (findings 9, 10), 1
comment-terseness finding fixed (finding 11), and 3 declined as
duplication/efficiency/API-clarity concerns with no behavioral defect,
deliberately avoiding further non-defect changes to a five-times-regressed
function (findings 12, 13, 15).

`4d269617` applies the repair. The two new regression tests are
mutation-checked: `test_never_closed_leading_fence_preserves_a_different_character_trailing_fence`
fails if the character comparison is dropped;
`test_marker_inside_a_genuinely_unterminated_fence_is_a_known_residual`
fails if the ambiguous case silently resolves either direction instead
of rejecting. `tests/test_detail.py` passed (`611 passed`) and the full
suite passed (`12433 passed, 189 skipped`), exit 0, no worker crashes or
kills — the first clean run this round, after the prior session's five
consecutive out-of-memory kills from concurrent load on this shared
machine (unrelated to this change; already recorded in `BUG_BACKLOG.md`).

### Next review

Convergence remains open. A fresh independent review of
`4d18ecf5..4d269617` is the next required evidence.

## Review pass 13 — /code-review high findings (2026-09-11)

**Scope:** `4d18ecf5..4d269617` — the pass-12 fix, per that fix's own
explicit next-review request.

**Method:** `/code-review --effort high --range 4d18ecf5..4d269617` run as
a background agent per the code-review-loop skill (83 tool uses, ~14
minutes, six finder angles including a dedicated gap sweep).

### Finding 1 — headline

**File:** `plan_tool/detail.py:2338` (pre-fix line numbering)

**Summary:** `parse_detail_response`'s wrapper-sentinel path can silently
accept and truncate a valid response instead of hard-rejecting it,
contradicting the `DETAIL_FORMAT.md` rule 3.1 guarantee the pass-12 diff
itself added ("reads as no sentinel present and hard-rejects rather than
accepting a possibly-wrong boundary").

**Failure scenario:** A real sentinel wrap (real start marker, real end
marker) whose `## Tests` section also contains an illustrative,
genuinely-never-closed fence with a coincidental end-marker-shaped line
inside it. Verified by direct execution: `parse_detail_response` returns
the document truncated at the fake end marker, with the real
`## Acceptance criteria` section silently dropped and replaced by a
stub, instead of `None`. `_matches_outside_fences(..., keep_trailing_unmatched=True)`
dropped the never-closed fence's trailing span from exclusion, so the
coincidental end-marker line was "found" as real, giving exactly one
start/end pair. The pass-12 regression test only covered the
zero-start-marker case, where rejection happened for an unrelated reason
(a start/end count mismatch), so this true-positive combination — a real
start marker present — was untested and the pass-12 disposition's "fails
closed" characterization did not hold for it.

**Disposition:** **Confirmed — this is the ninth consecutive review round
(passes 5–13) to find a defect touching this exact parsing mechanism.**
Investigated at length: no text-based signal distinguishes "a same-length
nested example fence caused the scanner to mis-locate a real wrap's true
close" (the legitimate case pass 11 added leniency for) from "an
illustrative fence the model genuinely never closed" (this finding's
case) without a nesting-aware scanner, which this codebase does not have
(round 12 already refuted the one candidate for reuse,
`jira_grade.fenced_spans`). A count-based heuristic (require evidence of
another same-length closed fence elsewhere in the document before
trusting the trailing span) was drafted and verified to distinguish the
two known cases, but — consistent with every prior heuristic tried in
this exact function across 5+ rounds — it is itself defeatable by a
combination the two known cases don't cover (a document with one
legitimate closed example *and*, separately, an abandoned illustrative
fence). Per this project's own "Audit the why, not the what" rule, this
was surfaced to the user rather than resolved with a tenth patch. **The
user selected "fail closed always."** `parse_detail_response`'s sentinel
start/end marker search and `_find_real_deferrals_match`'s deferrals
marker search no longer use the `keep_trailing_unmatched` leniency at
all — both now exclude every fenced span unconditionally, including a
trailing unmatched-to-EOF one. This closes the corruption class
entirely, at the cost of two known legitimate inputs (a sentinel-wrapped
body containing one or two same-length nested example fences) now
rejecting and retrying instead of parsing — a trade the user explicitly
confirmed. `_strip_bare_fence_lines`'s own, separate use of the same
leniency (a different mechanism, for the "lone trailing closer with no
partner" case, unrelated to marker detection) is untouched. Two existing
tests pinning the now-superseded nested-fence leniency are rewritten to
assert `None` with docstrings recording the supersession; a third test
whose "known residual" premise (marker-detection ambiguity) no longer
holds is rewritten to assert the new, unambiguous "never found inside an
unclosed fence" guarantee using the actual corruption-shaped repro (a
real start marker present). Verifying this fix also surfaced one
adjacent, pre-existing, unrelated defect (an unmatched fence swallowing a
genuine trailing heading causes a duplicate stub on the *plain*, non-sentinel
path) — routed to `BUG_BACKLOG.md` rather than fixed here, out of scope
for this range.

### Finding 2

**File:** `plan_tool/detail.py:2287`

**Summary:** `_strip_bare_fence_lines`'s trailing-fence check compares
only the closer's fence character against the opener, never its run
length — unlike `_fenced_code_spans` (`scope_fence.py`), which correctly
requires `len(closer) >= len(opener)`. Confirmed independently by five
separate review angles.

**Failure scenario:** A response opens with a 4-backtick wrap the model
never closes, and legitimately ends with its own separate, properly
self-closed 3-backtick example. Verified by direct execution: the
example's own real closing fence gets stripped, even though
`_fenced_code_spans` on the same text reports the whole thing genuinely
unmatched (a 3-backtick line can never close a 4-backtick opener). Root
cause: this branch hand-rolled open/close pairing a second time instead
of delegating to `_fenced_code_spans`'s own correct length rule — the
fourth time this exact function has been patched with a narrower check
than the scanner it duplicates.

**Disposition:** **Confirmed, fixed.** `_strip_bare_fence_lines` now
compares the full fence run — character and length — matching
`_fenced_code_spans`'s own closer rule exactly, instead of the
character-only comparison pass 12 introduced.
`test_never_closed_leading_fence_preserves_a_shorter_run_trailing_fence`
pins the fix.

### Finding 3

**File:** `BUG_BACKLOG.md:400`

**Summary:** A `BUG_BACKLOG.md` entry added within the pass-12 diff
references `_matches_outside_closed_fences`, a function that same diff's
own code change removes (merged into `_matches_outside_fences`),
violating this repo's `CLAUDE.md` "Documentation is forward-looking" rule
to sweep identifiers after a structural change.

**Failure scenario:** The entry told a future fixer to mirror
"`_matches_outside_fences`/`_matches_outside_closed_fences`"; as of that
same commit, `_matches_outside_closed_fences` no longer exists. Confirmed
by two independent review angles plus direct grep.

**Disposition:** **Confirmed, fixed.** The entry now points at
`_matches_outside_fences` (the merged form) and the finding-1 fix that
further pared it down.

### Finding 4

**File:** `DETAIL_FORMAT.md:289`

**Summary:** Rule 3.1's stated mechanism for the "marker inside a
genuinely unterminated fence" residual ("reads as no sentinel present")
didn't match the actual code path, and the same wording was copied into
the pass-12 test's docstring.

**Failure scenario:** For the tested case (lone END marker, no START
marker), direct execution showed the END marker *was* found (not
excluded) — rejection actually came from the starts/ends count-asymmetry
check, not from the marker reading as absent. Confirmed by mutation
testing: the test did pin real behavior, but its documented explanation
of the mechanism was wrong, and that wrong mental model is what produced
finding 1's real, non-cosmetic bug.

**Disposition:** **Confirmed, superseded rather than separately fixed.**
Finding 1's fix rewrites rule 3.1 entirely — the "reads as no sentinel
present" phrasing this finding disputes no longer exists in the doc.
Rule 3.1 now states plainly that marker search excludes every fenced
span unconditionally, with no residual left to mischaracterize.

### Finding 5

**File:** `plan_tool/detail.py:2277`

**Summary:** The pass-12 commit message's justification for dropping the
`start > 0` guard cited the wrong branch; the guard is actually dead only
because both current callers `.strip()` the text first, an unstated
precondition.

**Failure scenario:** Verified: `_strip_bare_fence_lines(['', '```\n', 'fenced content\n', '```\n'])`
(empty leading line) behaves differently under the old vs. new code. Not
reachable via either current call site today, but latent for a future
direct caller.

**Disposition:** **Confirmed (documentation gap, not a live defect).**
Verified unreachable via both current call sites, per this finding's own
claim. Rather than change behavior for an unreachable input, the
precondition is now stated explicitly in `_strip_bare_fence_lines`'s
docstring, per this project's own "prefer the explicit over the implicit"
rule — a future direct caller passing un-stripped lines now has the
precondition documented instead of silently relied upon.

### Finding 6

**File:** `plan_tool/detail.py:303`

**Summary:** `_fence_spans`'s `keep_trailing_unmatched=True` parameter
name is inverted from its actual effect — it *drops* the trailing
unmatched span rather than preserving it. Independently flagged by two
review angles.

**Failure scenario:** Not live today (all call sites at the time used it
correctly), but a naming footgun in a function whose history already
shows repeated review-round regressions; a future maintainer reading the
name literally could flip a call site the wrong way.

**Disposition:** **Declined, not renamed.** Finding 1's fix removed two
of the parameter's three call sites (the sentinel and deferrals marker
searches no longer use it at all), leaving exactly one remaining consumer
(`_strip_bare_fence_lines`), now documented in its own updated docstring
with the full rationale. The ambiguity's practical surface is
substantially smaller than when this finding was raised; a rename adds
churn to a function already touched twice this round without closing a
live defect. Revisit if a second consumer is ever added.

### Finding 7

**File:** `plan_tool/detail.py:2332`

**Summary:** `parse_detail_response` calls `_matches_outside_fences`
twice on identical text, each re-running a full `_fenced_code_spans`
scan.

**Failure scenario:** No incorrect output — redundant `O(n)` rescanning
on every response versus computing the span list once and reusing it.

**Disposition:** **Declined.** No behavioral defect and no measured
performance problem on the small documents this function processes; same
reasoning as pass 12's declined efficiency findings (12, 13).

### Finding 8

**File:** `plan_tool/detail.py:334`

**Summary:** `_detail_response_body_start` still calls
`_fenced_code_spans(text).spans` directly instead of the pass-12
`_fence_spans(text)` wrapper, an inconsistent migration.

**Failure scenario:** Behaviorally equivalent today (both give the full,
un-dropped span list — `_fence_spans(text)` with its default
`keep_trailing_unmatched=False` is exactly `_fenced_code_spans(text).spans`),
but a future change to `_fence_spans` would silently miss this call site.

**Disposition:** **Declined.** A pure style-consistency nit with no
behavioral difference today; same reasoning as finding 7 and pass 12's
declined findings.

## Review pass 13 triage and repair (2026-09-11)

The 8 submitted findings resolve to: 1 confirmed headline defect
requiring a user-directed design decision rather than another heuristic
(finding 1 — the ninth consecutive round to touch this mechanism), 2
straightforward confirmed-and-fixed bugs (findings 2, 3), 1 confirmed
finding superseded by finding 1's own fix rather than separately patched
(finding 4), 1 confirmed documentation gap closed by making an
unreachable-today precondition explicit rather than changing behavior
(finding 5), and 3 declined as naming/efficiency/consistency concerns
with no live defect (findings 6, 7, 8).

Finding 1 was surfaced to the user with four concrete options (fail
closed always; an evidence-gated heuristic; a real nesting-aware
scanner; accept as a documented residual) rather than resolved
unilaterally, per this project's "Audit the why, not the what" rule and
this exact loop's own precedent (passes 9 and 10). **The user selected
"fail closed always."** Findings 2 and 5 were fixed independently of that
decision (they don't touch the ambiguous leniency logic). `8799ca64`
applies the full repair across `plan_tool/detail.py`, `tests/test_detail.py`,
`BUG_BACKLOG.md`, and `DETAIL_FORMAT.md`. `tests/test_detail.py` passed
(`612 passed`); the full suite passed (`12434 passed, 189 skipped`, exit
0).

### Next review

Convergence remains open. A fresh independent review of
`4d269617..8799ca64` is the next required evidence.

## Review pass 14 — /code-review high findings (2026-09-11)

**Scope:** `4d269617..8799ca64` — the pass-13 fix, per that fix's own
explicit next-review request.

**Method:** `/code-review --effort high --range 4d269617..8799ca64` run as
a background agent per the code-review-loop skill (65 tool uses, ~23
minutes, 10 parallel finder angles plus a gap-sweep pass, personal
verification via direct code execution in a throwaway worktree at the
pre-diff commit to distinguish pre-existing from introduced).

### Finding 1 — headline

**File:** `plan_tool/detail.py:2292` (pre-fix line numbering)

**Summary:** `_strip_bare_fence_lines`'s no-leading-fence branch silently
corrupts a response ending in an unclosed (or length-mismatched) trailing
fence instead of preserving or rejecting it — the exact silent-corruption
hazard round 13 explicitly eliminated from marker search, still present
in this sibling branch of the same function.

**Failure scenario:** A plain (no leading fence) response whose
`## Acceptance criteria` section ends with a 4-backtick opener the model
never validly re-closes, followed by a bare 3-backtick line. Verified by
direct execution: the trailing 3-backtick line gets silently dropped and
the 4-backtick opener is left dangling/unclosed in the persisted file,
instead of the real content being preserved or the response being
rejected per round 13's own stated policy for this hazard class.
Reproduced identically at the pre-diff parent commit `4d269617` — this
session independently confirmed it is pre-existing, not a round-13
regression.

**Disposition:** **Confirmed, fixed.** This session's own round-13 commit
message claimed to close "the corruption class entirely," which
overreached: it closed the class for marker search only, not for this
sibling mechanism sharing the identical `keep_trailing_unmatched=True`
leniency. Rather than route this to `BUG_BACKLOG.md` as merely
pre-existing (the round-9-through-12 precedent for out-of-scope bugs),
this session judged it squarely within the class its own prior commit
claimed to close and fixed it directly, per this project's "fix the class,
not the cited spot" rule. The fix is structural, not another heuristic: a
genuinely partner-less trailing closer (nothing fenced before it — the
scanner's reported unmatched-opener position *is* the trailing line's own
position) is still stripped; a trailing closer sitting inside a fence
whose real opener is earlier in the document (real, if malformed, content
in between) is now protected instead of truncated. This is a provable
positional fact from the scanner's own span data, not a guess.
`test_no_leading_wrap_protects_real_content_trapped_in_a_dangling_fence`
pins the fix.

### Finding 2

**File:** `plan_tool/detail.py:2288` (pre-fix line numbering)

**Summary:** `_strip_bare_fence_lines`'s opening-fence branch misdetects a
leading single-line inline code span containing a backtick (e.g.
`` ```rm -rf /``` deletes files.``) as a document-wrapping opener, because
it re-matches `lines[0]` against `_FENCE_OPEN_RE` by hand instead of
replicating `_fenced_code_spans`'s CommonMark backtick-in-info-string
exclusion (`scope_fence.py:177`).

**Failure scenario:** A response whose first line is such an inline code
span, followed by a genuine, complete trailing fenced example under
`## Tests`. Verified by direct execution: the real trailing example's own
closing fence gets stripped as though it closed the fake leading wrap,
silently truncating real fenced content — the same corruption class round
13 was written to eliminate. Reproduced identically at `4d269617` —
pre-existing, but in a function this diff directly modified (its sibling
closing-check logic), so the diff touched this function without closing
this adjacent hole in it.

**Disposition:** **Confirmed, fixed.** Structural, not heuristic:
`_strip_bare_fence_lines` no longer decides "does the document open with
a fence" by re-matching `lines[0]` in isolation. It asks
`_fenced_code_spans` (the same scanner every other fence decision in this
module already trusts) whether *it* considers position 0 fenced — which
already, correctly, excludes the backtick-in-info-string case. A false
"opens with a fence" reading is now structurally impossible; the
detection can't drift from the scanner's own judgment because it no
longer re-derives it.
`test_leading_inline_code_span_with_a_backtick_is_not_a_fake_wrap` pins
the fix.

### Finding 3

**File:** `DETAIL_FORMAT.md:254`

**Summary:** Rule 2's prose said only "a closer can only close a
matching-character opener," but `_strip_bare_fence_lines` also requires
the closer's run length to be `>=` the opener's — the doc was never
updated for the round-12 length check, even though the code's own
docstring claimed rule 2 covered "character *and* length."

**Failure scenario:** A reader trusting the doc literally would believe
any same-character trailing fence closes any leading fence of that
character regardless of run length — exactly what the round-13 regression
test `test_never_closed_leading_fence_preserves_a_shorter_run_trailing_fence`
proves is false. The same doc/code-drift class this handoff's own round-12
review (finding 10) already found and fixed once for the character
dimension; the length dimension reintroduced it narrower and unfixed.
Independently flagged by three separate review angles.

**Disposition:** **Confirmed, fixed.** Rule 2 is rewritten to describe the
actual, current contract for both branches — including the length
requirement, the backtick-in-info-string exclusion (finding 2), and the
position-based "genuinely partner-less closer" distinction (finding 1) —
rather than patched narrowly a third time.

### Finding 4

**File:** `plan_tool/detail.py:303` (also `plan_tool/detail.py:2271`)

**Summary:** `_fence_spans` and `_strip_bare_fence_lines`'s docstrings
were re-expanded from terse one-line pointers back into multi-paragraph
inlined narratives restating the whole round-13 corruption story,
violating this repo's `CLAUDE.md` "## Code comments" rule for the third
time in this exact file's review history.

**Failure scenario:** This handoff records this identical pattern being
fixed at pass-10 finding 7 and again at pass-12 finding 11 ("Confirmed,
fixed. Both docstrings are trimmed to a line or two pointing at
DETAIL_FORMAT.md rule 2/3.1") — the round-13 diff re-bloated the same two
docstrings a round later, and (per finding 3) the DETAIL_FORMAT.md
pointer it cited didn't even carry what the docstring claimed, so the
prose was both non-terse and inaccurate.

**Disposition:** **Confirmed, fixed.** Both docstrings are trimmed back to
a line or two pointing at `DETAIL_FORMAT.md` rule 2, and the one inline
comment this round's own fix added is trimmed to a single line now that
the full rationale lives in the doc rule 3 fixed.

### Finding 5

**File:** `plan_tool/detail.py:427`

**Summary:** Round 13 makes a previously-parseable, unremarkable shape (a
sentinel-wrapped response containing a same-length nested example fence,
e.g. a code sample under `## Implementation`) now deterministically
rejected, but `_REPROMPT_SUFFIX` had no corresponding guidance telling the
model how to avoid re-triggering the rejection on retry.

**Failure scenario:** `plan_tool/prompts/plan-audit.md` already carries
the fix for this exact CommonMark issue ("open your fence with four or
more backticks" when the cited text has its own triple-backtick
sequence), but `_REPROMPT_SUFFIX` (used on retry) had no equivalent
instruction. With `_MAX_INVOKE_ATTEMPTS = 2`, a model whose natural style
wraps commentary in a sentinel and includes a same-length nested example
fence for that step's content could hit the identical rejection on both
attempts, permanently failing to author that step.

**Disposition:** **Confirmed, fixed.** `_REPROMPT_SUFFIX`'s point 1 now
carries the same guidance `plan-audit.md` already uses: if the response is
also wrapped in a fence and the body itself contains a fenced example,
open the wrap with four or more backticks so the body's own example can't
be mistaken for the wrap's closer — steering the model away from the
exact shape that now rejects, rather than only reactively rejecting it.

### Finding 6

**File:** `plan_tool/detail.py:2303` (pre-fix line numbering)

**Summary:** `_strip_bare_fence_lines`'s fence-run char+length closer
comparison duplicates the identical predicate already implemented in
`_fenced_code_spans`'s inner loop instead of extracting a shared helper —
acknowledged in its own docstring ("matching `_fenced_code_spans`'s own
closer rule") without factoring it into one shared predicate both call
sites use.

**Failure scenario:** A future CommonMark edge-case fix to one copy (e.g.
tilde/backtick asymmetry, or a length-off-by-one) could silently drift
from the other.

**Disposition:** **Confirmed, fixed.** `_fence_run_closes(opener_char,
opener_len, candidate_run)` is extracted into `scope_fence.py`, and both
`_fenced_code_spans` and `_strip_bare_fence_lines` now call it as the
single source of truth for the closer rule.

## Review pass 14 triage and repair (2026-09-11)

**All 6 submitted findings are confirmed and fixed — the first round in
this loop with zero declined or refuted findings.** Findings 1 and 2 are
both genuine, pre-existing corruption hazards (verified not to reproduce
as regressions of round 13's own diff, but sharing its exact hazard
class), fixed structurally using the scanner's own span data rather than
another positional heuristic. This session judged both squarely inside
the class round 13's own commit message claimed to close, rather than
routing them to `BUG_BACKLOG.md` as merely pre-existing and out of scope
— the "fix the class, not the cited spot" rule applied to this session's
own prior overreaching closure claim. Before finalizing, this session
grepped the full codebase for every other `_matches_outside_fences`/
`_fence_spans` call site and every other hand-rolled fence-character
comparison, to catch any further unswept sibling before another review
round has to. None were found.

Four regression tests are added (two for findings 1-2, matching the
project's "name a test for the invariant it pins" convention); the
duplicated closer predicate (finding 6) is consolidated into
`scope_fence.py:_fence_run_closes`, shared by `_fenced_code_spans` and
`_strip_bare_fence_lines`; `DETAIL_FORMAT.md` rule 2 is rewritten in full
rather than patched a third time; both over-long docstrings are trimmed
back to pointers. `tests/test_detail.py` and `tests/test_scope_fence.py`
passed (`682 passed`) with the closer-predicate consolidation alone, and
the full `test_detail.py` suite passed (`614 passed`, two new regression
tests) after all six fixes landed. `d9558fd3` applies the repair; the
full suite passed (`12436 passed, 189 skipped`, exit 0).

### Next review

Convergence remains open. A fresh independent review of
`8799ca64..d9558fd3` is the next required evidence.

## Review pass 15 — /code-review high findings (2026-09-11)

**Scope:** `8799ca64..d9558fd3` — the pass-14 fix, per that fix's own
explicit next-review request.

**Method:** `/code-review --effort high --range 8799ca64..d9558fd3` run as
a background agent per the code-review-loop skill (164 tool uses, ~21
minutes, 7 parallel finder angles plus personal verification via direct
execution and git-worktree comparisons against the pre-diff commit).

### Finding 1 — headline

**File:** `plan_tool/detail.py:2289` (pre-fix line numbering)

**Summary:** The "opens with a fence" branch of `_strip_bare_fence_lines`
strips a trailing closer-shaped line whenever it matches the leading
opener's character/length, without checking whether that opener was
already validly closed earlier in the document — the exact corruption
hazard round 14 rewrote this function to fix, left unswept in this third
sub-case of the same branch.

**Failure scenario:** A response opening with `` ```markdown `` that is
validly closed mid-document, followed by unrelated later content
containing its own separate, complete fenced example (e.g. a
`## Verification` section ending in its own fenced block). Verified by
direct execution: that unrelated example's real closing fence is
silently deleted, leaving a dangling, unclosed code block in the
persisted file — a non-`None`, seemingly-accepted result. Reproduced
identically against the pass-14 commit `d9558fd3` and its parent
`8799ca64` — pre-existing, not a round-14 regression, but this diff's
commit message explicitly enumerated and fixed two other sibling
instances of this exact hazard shape in this exact function and implied
the sweep was complete.

**Disposition:** **Confirmed, fixed — the third instance of this exact
hazard class in this exact function, and the fourth consecutive round to
find a defect touching it.** As with round 14's own findings 1-2, this
session judged it squarely inside the class this session's own prior
commit claimed to close, rather than routing it to `BUG_BACKLOG.md`.
Structural, not another heuristic: the leading opener's own span (from
`_fenced_code_spans`'s pairing) is now checked directly — the trailing
line is trusted as *this* opener's own closer only when the leading fence
never validly closes at all (covers both the genuinely-unterminated case
and the same-length-nesting scanner-artifact case, where the existing
char/length check remains the right signal) or the scanner's own pairing
shows the leading span reaching all the way to EOF (a genuine
whole-document wrap). When the leading fence closes validly *earlier*,
a later fence-shaped line is left untouched regardless of whether it
happens to share the same character and length.
`test_leading_wrap_closed_early_protects_an_unrelated_later_example` pins
the fix, mutation-verified to fail against the pre-fix parent commit.

### Finding 2

**File:** `plan_tool/detail.py:2286` (pre-fix line numbering)

**Summary:** `_strip_bare_fence_lines` crashes with `AttributeError` when
`lines[0]` is blank (violating the function's documented-but-unenforced
precondition) while `opens_with_fence` is computed `True` from a *later*
line landing at text-offset 0 — the round-14 redesign decides "opens with
a fence" from the joined text's span data without confirming `lines[0]`
itself is genuinely fence-shaped.

**Failure scenario:** Verified by direct execution:
`_strip_bare_fence_lines(['', '```\n', 'fenced content\n', '```\n'])`
raises `AttributeError: 'NoneType' object has no attribute 'group'` on
the round-14 code. The immediately-preceding commit (`8799ca64`, round
13) returns the input unchanged for the identical call — a graceful, if
undocumented, fallback that round 14's refactor silently turned into a
hard crash. Not reachable via either current call site (both `.strip()`
the text first), but a genuine robustness regression against round 13's
own explicit decision (its finding 5) to leave this exact case
non-crashing rather than guard it.

**Disposition:** **Confirmed, fixed.** Rather than merely re-document the
precondition again (round 13's precedent for this same unreachable-input
class), this session added the missing guard: `opens_with_fence` now
additionally requires `lines[0]` to independently match the fence-open
pattern, not merely that position 0 of the joined text looks fenced —
converting a crash on a violated precondition back into the documented
graceful pass-through, and closing the finding permanently rather than
re-declining it a second time.
`test_strip_bare_fence_lines_does_not_crash_on_a_blank_first_line` pins
the fix, mutation-verified to crash against the pre-fix parent commit.

### Finding 3

**File:** `plan_tool/detail.py:303`

**Summary:** `_fence_spans`'s docstring, edited in the round-14 diff,
claimed `keep_trailing_unmatched=True` is "used only by
`_strip_bare_fence_lines`" — but that same diff's own rewrite of
`_strip_bare_fence_lines` stopped calling `_fence_spans` entirely (it
calls `_fenced_code_spans` directly), so no call site anywhere in the
codebase still passes `True`.

**Failure scenario:** `grep -rn "_fence_spans("` showed exactly one
remaining call site (`_matches_outside_fences`), always with the default
`False`. The `keep_trailing_unmatched` branch was fully dead with a false
caller claim; a future maintainer trusting the docstring could route
`_strip_bare_fence_lines` back through it to "fix" a perceived
regression, silently reintroducing the coarse trailing-span-drop behavior
this diff's own tests were written to replace.

**Disposition:** **Confirmed, fixed.** `_fence_spans` is removed entirely
— it was a pure pass-through wrapper around `_fenced_code_spans(text).spans`
once the dead branch is gone — and `_matches_outside_fences` now calls
`_fenced_code_spans` directly.

### Finding 4

**File:** `plan_tool/detail.py:2282` (pre-fix line numbering)

**Summary:** The `elif not any(end == len(text) ...): lines = lines[:-1]`
branch inside `_strip_bare_fence_lines` is provably unreachable dead
code.

**Failure scenario:** Proven analytically (given `_fenced_code_spans`'s
single-opener state machine, `scan.unmatched_opening is None` combined
with a close-shaped last line can only arise when that line closed an
already-open fence ending exactly at `len(text)`, making
`any(end==len(text)...)` always true) and confirmed empirically by
independent fuzz runs. It misrepresented the function's contract as
handling a case that cannot occur.

**Disposition:** **Confirmed, fixed.** The dead `elif` branch is deleted;
the `unmatched_opening is None` case now falls through to "protect,
don't strip" implicitly, which is what the dead branch always evaluated
to anyway.

### Finding 5

**File:** `plan_tool/detail.py:2272` (pre-fix line numbering)

**Summary:** `opens_with_fence = scan.unmatched_opening == 0 or any(start == 0 for start, _end in scan.spans)`
— the `scan.unmatched_opening == 0` disjunct is redundant.

**Failure scenario:** In `_fenced_code_spans`, whenever the loop ends
with a dangling opener, `spans.append((opener[2], len(text)))` runs
immediately before `unmatched_opening=opener[2]` is set, so any time
`unmatched_opening == 0` a span with `start == 0` is already guaranteed
present in `scan.spans` — the second disjunct alone is always sufficient.
No behavioral cost, but the condition reads as guarding a distinct case
it never does.

**Disposition:** **Confirmed, fixed.** The redundant disjunct is removed;
`opens_with_fence` (now also requiring `opening_match is not None`, per
finding 2) checks only `any(start == 0 for start, _end in scan.spans)`.

### Finding 6

**File:** `tests/test_detail.py:1805`

**Summary:** `test_leading_inline_code_span_with_a_backtick_is_not_a_fake_wrap`
(added in round 14) does not actually pin the regression its docstring
claims to guard against.

**Failure scenario:** Verified by mutation against `8799ca64` (round 14's
own parent commit, pre-fix): the test passes unchanged under the old,
buggy code. The test's raw text placed `## Acceptance criteria` after the
real fenced `## Tests` example, so that example was never the document's
actual trailing content and the fake-wrap-stripping failure mode the test
names was never exercised — a false sense of coverage for exactly the
class of bug the round-14 diff was about.

**Disposition:** **Confirmed, fixed.** The test is rewritten so the
fenced example is the document's true last content (`## Acceptance
criteria` now precedes `## Tests`); re-verified by mutation to fail
against the pre-round-14 baseline (`8799ca64`) and pass at HEAD.

### Finding 7

**File:** `plan_tool/detail.py:2270` (pre-fix line numbering)

**Summary:** `_strip_bare_fence_lines` now unconditionally runs a full
`O(n)` `_fenced_code_spans` scan on every call, and `parse_detail_response`
re-derives fence-span state via 4+ separate full-text scans per
invocation instead of computing and threading it once.

**Failure scenario:** No incorrect output — repeated linear work on every
response parse versus computing the span list once and reusing it.

**Disposition:** **Declined.** No behavioral defect and no measured
performance problem on the small documents this function processes; same
reasoning as pass 12's declined findings 12-13 and pass 13's declined
findings 6-7.

## Review pass 15 triage and repair (2026-09-11)

**6 of 7 submitted findings are confirmed and fixed; 1 is declined as an
unmeasured efficiency concern with no behavioral defect.** Findings 1-2
are the fourth consecutive round to confirm a defect touching this exact
function — finding 1 a third instance of the corruption-hazard class
round 14's own commit message claimed to close, finding 2 a genuine
crash regression introduced by round 14's own refactor. Both are fixed
structurally: finding 1 by checking the leading opener's actual span
data (does it reach EOF, or never close at all) instead of blindly
comparing the first/last line's fence shape; finding 2 by requiring
`lines[0]` to independently match the fence-open pattern before trusting
the joined text's span-0 verdict. Findings 3-5 are consolidation/dead-code
cleanups exposed once findings 1-2 forced a closer look at the same
logic — `_fence_spans` is removed entirely (now unused after
`_strip_bare_fence_lines` stopped calling it), a provably-unreachable
branch is deleted, and a redundant condition is simplified. Finding 6 is
notable on its own: this session's own round-14 regression test for a
confirmed, real bug did not actually exercise the bug it claimed to
guard against — caught only by this round's mutation verification, not
by static review, underscoring this project's "verify by mutation, never
by reading" rule.

Two new regression tests are added for findings 1-2, mutation-verified
against the pre-fix parent commit to confirm each fails without its fix
(one via a wrong assertion, one via the actual crash). Before finalizing,
this session re-ran the same full-codebase sweep as round 14 (every
`_FENCE_OPEN_RE`/`_FENCE_CLOSE_RE`/`_fenced_code_spans`/`_fence_run_closes`
call site) to catch any further unswept sibling before another review
round has to; none were found. `tests/test_detail.py` and
`tests/test_scope_fence.py` passed (`686 passed`, two new regression
tests). `b451ee80` applies the repair. The first full-suite attempt was
killed by the OS for low system memory (a fifth occurrence of the
already-documented, unrelated pattern on this shared machine); a retry
at reduced parallelism hit 18 failures confined to
`tests/test_roadmap_version_promotion.py`, all confirmed to pass cleanly
in isolation immediately after — environmental, not a regression, since
this change touches only `plan_tool/detail.py`, `plan_tool/scope_fence.py`,
and `DETAIL_FORMAT.md`. A clean retry passed (`12438 passed, 189
skipped`, exit 0).

### Next review

Convergence remains open. A fresh independent review of
`d9558fd3..b451ee80` is the next required evidence.

### Between-round addendum — self-found residual (2026-09-11)

Before launching round 16, this session adversarially stress-tested its
own round-15 fix and found one further gap: `scan.unmatched_opening is
not None` treats *any* unmatched fence anywhere in the document as
proof the leading fence never closed, but the field records only the
single most-recently-opened-and-never-closed position, which can belong
to a completely separate, later, unrelated fence. A response opening
with a fence that closes early, followed by a `## Verification` section
opening a 4-backtick fence with real content that never closes, ending
in a bare 3-backtick line matching the *leading* opener's shape (but not
the 4-backtick one) — the trailing 3-backtick line is incorrectly
stripped. Verified no required content is lost in this repro. Filed to
`BUG_BACKLOG.md` (`2786d6d1`) rather than fixed inline: no triggering
review finding, low severity, and this function had already regressed
once this session from an in-scope fix.

## Review pass 16 — /code-review high findings (2026-09-11)

**Scope:** `d9558fd3..b451ee80` — the pass-15 fix, per that fix's own
explicit next-review request.

**Method:** `/code-review --effort high --range d9558fd3..b451ee80` run as
a background agent per the code-review-loop skill (80 tool uses, ~11
minutes; six correctness/cleanup finder angles plus a gap-sweep, five of
which independently converged on the same core defect).

### Finding 1 — headline

**File:** `plan_tool/detail.py:2284` (pre-fix line numbering)

**Summary:** `leading_reaches_eof`'s `scan.unmatched_opening is not None`
disjunct treats any unmatched fence anywhere in the document as proof
the leading fence never closed, so a leading fence that closed validly
early still lets an unrelated, later, separately-unclosed fence's
trailing line get stripped as if it were the leading fence's own closer.

**Failure scenario:** Verified by direct execution — the same shape this
session's own between-round addendum above already found and filed.
The review additionally proposed a specific remedy: drop the
`scan.unmatched_opening is not None` disjunct entirely, keeping only
`any(start == 0 and end == len(text) for start, end in scan.spans)`,
claimed to "still pass all three known scenarios."

**Disposition:** **Confirmed as a real defect (this session already
filed it); the proposed remedy is refuted.** Verified the remedy
directly rather than trusting the claim: it does pass the full existing
suite, but that is exactly the "green suite is not evidence for a site
you didn't change" trap this project's own testing rules warn about —
no existing test exercised the case it silently breaks. Direct
execution confirms the proposed remedy stops stripping the true wrap
closer of a plain (non-sentinel) response containing a same-length
nested example fence (the round-9-11 scanner-artifact leniency),
leaving a dangling stray fence marker in otherwise-correct output. The
underlying tension is structural: a genuine early close and a
nested-fence scanner mis-pairing that merely *looks* like an early close
produce identical span shapes, the same class of text-alone ambiguity
that took 9 rounds and a user decision to resolve for marker search
(rule 3.1). A regression test
(`test_plain_wrap_with_a_same_length_inner_fence_still_strips_the_true_closer`)
is added specifically so this exact remedy (or an equivalent one) fails
immediately rather than shipping silently. The `BUG_BACKLOG.md` entry is
updated to record this round's independent confirmation and the rejected
remedy. **Superseded 2026-09-11 (pass 18):** the caller has sufficient
local anchors — reply offset 0 and the pre-frontmatter fence position — so
no `FencedCodeScan` API change is required.

### Finding 2

**File:** `plan_tool/detail.py:2276`

**Summary:** The 8-line inline comment above `leading_reaches_eof`
violates this repo's `CLAUDE.md` "## Code comments" rule for a third
recurrence in this exact file's history (pass-10 finding 7, pass-12
finding 11), and is also factually imprecise — it framed
`scan.unmatched_opening is set` as meaning specifically the leading
fence never closes, which finding 1 shows isn't guaranteed.

**Failure scenario:** This handoff records the identical
docstring/comment-bloat pattern being trimmed twice before, both citing
this exact rule; a third recurrence one round later, now inline.

**Disposition:** **Confirmed, fixed.** The comment is trimmed to a
pointer at `DETAIL_FORMAT.md` rule 2, which is also updated to state the
residual accurately (a *necessary, not sufficient* signal) rather than
repeat the imprecise framing.

### Finding 3

**File:** `plan_tool/detail.py:2251`

**Summary:** `_strip_bare_fence_lines`'s docstring stated an absolute
precondition ("`lines[0]` is never blank") that the same diff's own code
change contradicted: it added a guard (`opening_match is not None`)
specifically to tolerate a blank `lines[0]`, plus a test that
deliberately passes one.

**Failure scenario:** Not a runtime bug as shipped, but a reader trusting
the stated absolute precondition could remove the now-seemingly-redundant
guard as dead defensive code, reintroducing the round-15 crash.

**Disposition:** **Confirmed, fixed.** The docstring now states the
precondition is defended against rather than assumed to always hold, per
this project's own "prefer the explicit over the implicit" directive.

## Review pass 16 triage and repair (2026-09-11)

**Finding 1 is confirmed as a real defect — already independently found
and filed by this session before the round launched — but its proposed
remedy is refuted after direct verification: it silently regresses a
real, legitimate, previously-untested feature.** This is a notable
instance of this project's "verify a remedy's justification against the
code" rule: a plausible-sounding, test-suite-passing fix was checked
directly and found to trade a narrow, low-severity gap for a broader,
silent regression of intentional round-9-11 functionality. Findings 2-3
are straightforward and fixed: a docstring-terseness violation
(recurring a third time) and a precondition claim the code itself
already contradicted.

Given this round's headline finding was already self-discovered and
filed, and its only new content was a remedy this session verified and
rejected, the net *code* change this round is narrow: a comment trim, a
docstring correction, one new regression test guarding the rejected
remedy, and a strengthened `BUG_BACKLOG.md` entry. `tests/test_detail.py`
and `tests/test_scope_fence.py` passed (`687 passed`, one new regression
test).

### Convergence assessment

**This is the fourth consecutive round (13, 14, 15, 16) to touch this
exact function or its immediate surroundings**, but the shape has
changed materially: round 16 found no *new* defect — its headline
finding was independently pre-empted by this session's own adversarial
testing, and its only substantive contribution (the proposed remedy) was
checked and correctly rejected. Severity has been shrinking each round
(round 13: a severe, user-decision-requiring corruption class; round 14:
two real corruption bugs plus cleanup; round 15: one narrower corruption
bug, one self-seeded crash, plus cleanup; round 16: zero new defects, one
refuted remedy, two doc/comment fixes) and the remaining known gap is
explicitly accepted and documented (`BUG_BACKLOG.md`) rather than
silently outstanding. Per this project's "same finding or region keeps
resurfacing" non-converging signal, this pattern would ordinarily
warrant surfacing to the user — but the *region* (this function) is no
longer producing new material findings, only progressively smaller and
more accurately-classified residue. This session judges the trend as
converging rather than stalled, and will treat a materially clean or
low-yield round 17 as the second confirming data point per this
project's severity-aware stopping rule, rather than continuing
indefinitely on count alone.

`f1d47a63` applies the repair (comment/docstring fixes, new regression
test, strengthened backlog entry — no behavioral code change, since the
review's proposed behavioral fix was rejected).

### Next review (completed)

Pass 17 completed the independent review of `b451ee80..f1d47a63`; its
findings and subsequent triage appear below.

## Review pass 17 — /code-review high findings (2026-09-11)

**Scope:** `b451ee80..f1d47a63` — the pass-16 fix, per that fix's own
explicit next-review request.

**Method:** `/code-review --effort high --range b451ee80..f1d47a63` run as
a background agent per the code-review-loop skill (87 tool uses, ~15
minutes).

**Process note:** Starting with this round, the driving session switched
from triage-and-fix-inline back to the code-review-loop skill's default
report-only mode, at the user's explicit direction. Findings below are a
faithful transcript of what the review reported. Where this session did
hands-on verification before the mode switch (findings 1 and 2 were
partially investigated first), that verification is recorded as context,
but the **disposition itself is left pending** for the user or a future
session to make, not decided here.

### Finding 1

**File:** `plan_tool/detail.py:2279` (pre-fix line numbering)

**Summary:** The pass-15/16 `BUG_BACKLOG.md` entry's central claim — "not
identified... structural, not a matter of finding the right condition" —
is disputed by the review as factually wrong. Suggested fix: replace
`scan.unmatched_opening is not None` with
`scan.unmatched_opening in (0, trailing_line_start)`.

**Failure scenario:** As filed in `BUG_BACKLOG.md`: a leading fence that
closes validly early, followed by a separate, later, unrelated
never-closed fence whose dangling opener line happens to share the
leading opener's character/length, has its trailing line wrongly
stripped.

**Verification note (this session, before the mode switch):** The
suggested condition was checked directly against three constructed
cases (leading-never-closes; the legitimate same-length-nested-fence
case pinned by `test_plain_wrap_with_a_same_length_inner_fence_still_strips_the_true_closer`;
and the adversarial unrelated-later-fence case from `BUG_BACKLOG.md`) and
correctly distinguished all three — `scan.unmatched_opening` landed at
exactly `0`, exactly `trailing_line_start`, and at neither position,
respectively, for the three cases. `tests/test_detail.py` (617 tests)
passed with this condition applied. This is genuine evidence the
suggested remedy is viable, offered here as context for whoever
dispositions the finding — it is not itself a disposition.

**Disposition:** **Confirmed, fixed in `e8847e83`.** The scanner position
distinguishes the leading opener (offset 0) and the trailing scanner
artifact from an unrelated later opener. A regression preserves the latter's
trailing fence, and the now-false `BUG_BACKLOG.md` entry is deleted.

### Finding 2

**File:** `plan_tool/roadmap.py:1318` (`_strip_reply_lines`)

**Summary:** `has_outer_opener = _fenced_code_spans(preamble).unmatched_opening is not None`
has the identical "which opener is it" ambiguity the pass-15/16 work
documented and deferred for `detail.py`, but here it is undocumented,
unswept, and (per the review) does cause real content loss.

**Failure scenario:** A stage reply whose preamble contains an unrelated,
never-closed illustrative fence, followed by real frontmatter and
artifact content that legitimately ends in its own closing code fence,
has that legitimate trailing fence silently stripped by
`_strip_reply_lines(reply, strip_unpaired_trailing_fence=False)` — the
exact call signature both real callers (`_run_stage`,
`_materialize_plan_seed`) use.

**Verification note (this session, before the mode switch):** Confirmed
the failure scenario by direct execution — the trailing fence is indeed
dropped. This session then tried porting finding 1's precise remedy
shape to this function and found it does **not** transfer cleanly:
`roadmap.py`'s preamble-before-frontmatter design has no fixed anchor
position analogous to `detail.py`'s "wrap must start at line 0," and
several constructed test cases showed the same span shape arising from
both a genuine scanner-artifact and a genuinely unrelated adversarial
fence whenever the two fences share a character/length — an ambiguity
that appears structural here, not resolved by the same technique. This
is offered as context, not a disposition; a different session or more
time may find a remedy this session didn't.

**Disposition:** **Confirmed, fixed in `e8847e83`.** The selected
frontmatter fence supplies the missing anchor: only an unmatched opener on
the last nonblank preamble line is an outer wrapper. The regression preserves
an artifact closer after an earlier unrelated fence.

### Finding 3

**File:** `docs/evidence/authored-artifact-structure-versioning.md:4650`

**Summary:** At the time this diff's range ended, `BUG_BACKLOG.md` and
`DETAIL_FORMAT.md` referenced "a round-16 review" as complete, but this
handoff doc's own "Next review" pointer was still one round stale. The
review itself notes: "Resolved one commit later, outside this diff's
range, but present at this committed snapshot."

**Failure scenario:** A reader following only this handoff doc's
convergence tracking would have no way to know round 16 happened,
between when `f1d47a63` landed and when the handoff commit caught up.

**Disposition:** **Refuted as a current defect.** `1c32154d` records pass
17 after the existing pass-16 triage, so the current handoff no longer lacks
the round-16 state; the stale pointer existed only within the reviewed
historical range and needs no further edit.

### Finding 4

**File:** `DETAIL_FORMAT.md:281`

**Summary:** The rewritten rule-2 prose dropped the removed inline
comment's positive justification for keeping the
`unmatched_opening is not None` disjunct (why it's needed for the
legitimate nested-fence case), leaving only the negative/residual
framing.

**Failure scenario:** A future maintainer reading only `detail.py` +
`DETAIL_FORMAT.md` (not `BUG_BACKLOG.md`'s round-16 discussion) could
conclude the disjunct is pure liability and drop it — the already-once-rejected
round-16 proposal — relying entirely on the regression test to catch the
regression rather than on the documentation to prevent the attempt.

**Disposition:** **Confirmed, fixed in `e8847e83`.** Rule 2 now states why
the same-length scanner-artifact position still permits stripping.

### Finding 5

**File:** `DETAIL_FORMAT.md:272`

**Summary:** A pre-existing (unmodified by the pass-15/16 diffs) sentence
about the blank-`lines[0]` guard reads, under its natural parse, as
contradicting the round-15 docstring and the verified runtime behavior —
DETAIL_FORMAT.md says the guard behavior is "rather than falling back to
the no-leading-fence case," while the code's own docstring and direct
execution both show it does fall through to that case.

**Failure scenario:** A reader trusting `DETAIL_FORMAT.md`'s literal
wording over the docstring could misunderstand the actual control flow.

**Disposition:** **Confirmed, fixed in `e8847e83`.** Rule 2 now says the
blank first line falls through to the no-leading-fence path.

### Finding 6

**File:** `tests/test_detail.py:1829`

**Summary:** The new `test_plain_wrap_with_a_same_length_inner_fence_still_strips_the_true_closer`
test's fixture-construction pattern (nest a same-length fenced example
into `_FIVE_SECTIONS`'s Implementation section) is hand-copied a third
time rather than factored into a shared helper — the identical
transformation already appears at
`test_sentinel_wrapped_body_with_same_length_inner_fence_now_fails_closed`
and its two-fence sibling.

**Failure scenario:** A future change to the nested-fence shape needed to
exercise this scenario class requires updating three call sites by hand
instead of one shared helper.

**Disposition:** **Declined.** The three fixtures cover one nested fence,
two nested fences, and the plain-response path; no behavior change requires
their common construction to evolve. A helper would add indirection without
closing a demonstrated defect.

### Finding 7

**File:** `BUG_BACKLOG.md:517`

**Summary:** The residual entry's narrative (the round-16 proposal, why
it was tested, why it regresses the legitimate case) is duplicated
near-verbatim across three locations (`BUG_BACKLOG.md`, the new test's
docstring, `DETAIL_FORMAT.md`'s "Accepted residual" paragraph) instead of
stated once with pointers.

**Failure scenario:** A future correction to this narrative (e.g. if
finding 1 above is acted on and the "fix: not identified" conclusion is
reversed) requires updating three near-duplicate prose copies to stay
consistent.

**Disposition:** **Confirmed, fixed in `e8847e83`.** Deleting the obsolete
backlog entry and trimming the test to its current invariant leaves the
format document as the single live rule rather than three copies of a
superseded round-16 rationale.

## Review pass 17 triage and repair (2026-09-11)

**Finding class:** fence stripping must identify the candidate fence that
authorizes deletion; another unmatched fence must not silently remove real
artifact content.

**Pre-edit sweep:** `_strip_bare_fence_lines` has the sentinel and plain
response callers; `_strip_reply_lines` feeds both `_run_stage` and
`_materialize_plan_seed`. The identifier sweep covered
`unmatched_opening`, both strip helpers, and both lift callers. The vocabulary
sweep covered `outer`, `preamble`, `trailing`, `same-length`, and
`unrelated` across the source, tests, format rule, backlog, and handoff.
Only the two predicates above shared the reported ownership error; marker
search's separate fail-closed policy remains unchanged.

`e8847e83` applies the initial two direct fixes. At that snapshot,
`_strip_bare_fence_lines` stripped only when the trailing marker was a scanner
artifact or a span from the leading opener reached EOF; `_strip_reply_lines`
treated an opener as outer only when it was the final nonblank preamble line
before the selected frontmatter fence. The new regressions preserve the
previously lost detail/roadmap trailing fences; existing whole-wrapper tests
cover the retained normal behavior.

**Validation:** `tests/test_detail.py::TestParseDetailResponse` plus
`tests/test_roadmap.py::TestCleanPath` — 61 passed; the two complete affected
modules — 1,092 passed, 168 skipped; full parallel suite — 12,440 passed,
190 skipped.

### Next review (completed)

Pass 18 completed the independent review of `f1d47a63..e8847e83`; its
findings and subsequent triage appear below.

## Review pass 18 — /code-review high findings (2026-09-11)

**Scope:** `f1d47a63..e8847e83` — the pass-17 fix, per the pass-17 triage's
own explicit next-review request.

**Method:** `/code-review --effort high --range f1d47a63..e8847e83` run as
a background agent per the code-review-loop skill (118 tool uses, ~23
minutes).

**Scope note (from the review itself):** the requested range predates
`03da117e` (the pass-17 disposition commit, authored by the repo's own
user), so the review's initial read of stale `_(pending)_` markers
against a since-shipped fix is dropped as moot below — only its
substantive findings are recorded.

### Finding 1

**File:** `plan_tool/roadmap.py:1311`

**Summary:** The pass-17 fix narrowed `has_outer_opener` to require the
preamble's unmatched fence opener to sit exactly on the last non-blank
preamble line. The review reports this is a false negative whenever the
model's reply has any text between the fence-open line and the
frontmatter `---` — a genuine whole-reply wrap is no longer recognized,
so its trailing closer fence is left un-stripped and leaks into the
persisted artifact.

**Failure scenario:** Reply =
`'```markdown\nHere is the domain artifact:\n---\nentities: []\nbusiness_rules: []\nworkflows: []\n---\n\n# Domain\n\nSome real prose body.\n```'`.
The review reports verifying directly against both `f1d47a63` (pre-fix)
and `e8847e83` (post-fix): the old check correctly stripped the trailing
fence for this input; the new code computes `unmatched_opening=0` vs.
`last_preamble_line_start=12`, so `has_outer_opener=False` and the
trailing fence survives. Piped through `_lift_artifact_text` and
`parse_domain_artifact`, the stray fence lands verbatim in
`artifact.body`, which `render_domain_artifact` writes byte-for-byte into
the stage file — silent, persistent content corruption for the
`_run_stage` caller. The review reports `_materialize_plan_seed` is not
silently corrupted for this same input because `validate_draft_seed_content`
independently re-scans and rejects a stray trailing fence, forcing a
retry instead — but that still means a legitimate model reply is
spuriously rejected as if it were the model's fault.

**Verification note (this session):** Reproduced directly — the trailing
fence is indeed left in the output for this exact input, confirming the
regression claim.

**Disposition:** **Confirmed, fixed in `8fc86c27`.** A reply-start opener
and the final pre-frontmatter opener are the two genuine wrapper anchors;
the repair restores the reply-start case without reauthorizing the earlier
unrelated-preamble false positive. Regressions exercise `_run_stage` and
seed materialization separately.

### Finding 2

**File:** `docs/evidence/authored-artifact-structure-versioning.md:4726`

**Summary:** The round-16 section's closing rationale — "a proper fix
still needs `FencedCodeScan` to expose per-opener origin" — is left
standing even though `e8847e83` (in the reviewed range) shipped a
working caller-side fix with no scanner API change, and deleted the
`BUG_BACKLOG.md` entry making the identical claim. The review frames
this against this repo's own `CLAUDE.md` "Documentation is
forward-looking" → "Delete on sight" rule for a rationale that depends
on something the same range reverses.

**Failure scenario:** A reader of the round-16 section could conclude a
`FencedCodeScan` API redesign is still required, scoping unnecessary
work around a premise later commits in this same file already falsified.

**Disposition:** **Confirmed, fixed in this handoff update.** The stale
pass-16 claim is explicitly marked superseded by the local-anchor repair;
no scanner API work is implied.

### Finding 3

**File:** `plan_tool/detail.py:2280`

**Summary:** In `scan.unmatched_opening in (0, trailing_line_start)`,
the review reports the `0` alternative is dead: `_fenced_code_spans`
always appends `(opener_offset, len(text))` to `spans` in the same
branch that sets `unmatched_opening=opener_offset`, so
`unmatched_opening == 0` already implies the sibling
`any(start == 0 and end == len(text) ...)` disjunct is true.
`DETAIL_FORMAT.md`'s rule 2 is reported to compound this by documenting
it as a third, independently meaningful trigger.

**Failure scenario:** Reported as correctness-neutral (the review states
it verified this via code trace and a 20,000-case randomized property
check), but a future maintainer reading the code or the doc could
believe there are three independently-necessary trigger conditions
rather than two, complicating the next edit to this function.

**Disposition:** **Confirmed, fixed in `8fc86c27`.** The code and rule 2
now name only the leading-span-to-EOF and trailing-scanner-artifact
triggers; behavior is unchanged.

## Review pass 18 triage and repair (2026-09-11)

**Finding class (superseded 2026-09-11 by pass 19):** reply-fence stripping
was expected to preserve both forms of a genuine whole-reply wrapper while
refusing to let an unrelated preamble fence authorize deletion. The latter
property requires ambiguous wrapper-shaped replies to retry instead.

**Pre-edit sweep:** `_strip_reply_lines` serves `_run_stage` and
`_materialize_plan_seed`; the review finding and tests cover each caller.
The identifier sweep covered `has_outer_opener`, `last_preamble_line_start`,
`_lift_artifact_text`, `unmatched_opening`, and the detail-strip predicate.
The vocabulary sweep covered `outer`, `preamble`, `frontmatter`, `trailing`,
`unmatched`, and `per-opener origin` across code, tests, the format rule,
backlog, and handoff. No other predicate claimed wrapper ownership.

At `8fc86c27`, the reply-start anchor was restored alongside the
final-nonblank pre-frontmatter anchor. Pass 19 supersedes that expansion:
an ambiguous wrapper-shaped reply retries rather than being classified as
either safe form. The detail condition removes a redundant `0` check and the
format rule now describes the two real triggers. The pass-16 scanner API
rationale is marked superseded rather than left as current design.

**Validation:** focused parser/stage/materialization suites — 84 passed,
2 skipped; complete affected modules — 1,092 passed, 168 skipped; full
parallel suite — 12,440 passed, 190 skipped.

### Next review (completed)

Pass 19 completed the independent review of `e8847e83..8fc86c27`; its
findings and subsequent triage appear below.

## Review pass 19 — /code-review high findings (2026-09-11)

**Scope:** `e8847e83..8fc86c27` — the pass-18 fix, per the pass-18 triage's
own explicit next-review request.

**Method:** `/code-review --effort high --range e8847e83..8fc86c27` run as
a background agent per the code-review-loop skill (55 tool uses, ~25
minutes, 10 parallel finder angles, one including a 300k-case fuzz
differential). 11 findings submitted.

### Finding 1 — headline

**File:** `plan_tool/roadmap.py:1311`

**Summary:** `has_outer_opener = preamble_scan.unmatched_opening in (0, last_preamble_line_start)`
reintroduces, for the offset-0 case, the exact corruption bug the
immediately preceding fix (pass 17) had just closed: an unrelated,
never-closed illustrative fence that merely happens to be the reply's
first line is now wrongly treated as an outer whole-reply wrapper,
silently stripping a genuine trailing content fence.

**Failure scenario:** `reply = '```text\nnot an outer wrapper, just an illustrative example the model forgot to close\n---\nformat: 1\n---\n\n# Artifact\n\nSome real content that legitimately ends in a fence:\n```\n'`.
The review reports reproducing directly: at `e8847e83` (pre-diff)
`_strip_reply_lines` correctly preserves the trailing fence; at
`8fc86c27` (post-diff) `unmatched_opening == 0`, so `has_outer_opener` is
now `True` and the genuine trailing fence is stripped, silently
truncating real artifact content by one line. The review reports 7 of 10
finder angles independently confirmed this via direct execution.

**Verification note (this session):** Reproduced directly — the trailing
fence is indeed stripped for this exact input, confirming the
regression.

**Disposition:** **Confirmed, fixed in `35a32efa`.** An opener that is not
directly adjacent to frontmatter is ambiguous and now yields no lifted
artifact, so `_run_stage` retries instead of writing a truncated body.

### Finding 2

**File:** `plan_tool/roadmap.py:1888`

**Summary:** The corruption from finding 1 has asymmetric, materially
worse consequences depending on caller: `_materialize_plan_seed`
independently re-validates via `validate_draft_seed_content` and
retries, but `_run_stage` (writing the domain/constraints/components/plans
stage files via `publish_stage_artifact`) has no equivalent fence-balance
gate anywhere in its gate sets.

**Failure scenario:** The same adversarial reply from finding 1, fed
through `_run_stage`, is reported to produce a stage artifact body with a
dangling unmatched code fence that `parse_domain_artifact` accepts with
no error, writing it straight to disk — silent, permanent on-disk
corruption with no retry and no operator-visible signal, unlike the seed
path which at least surfaces a retry for the identical underlying
defect.

**Disposition:** **Confirmed as the same defect class, fixed in
`35a32efa`.** The exact ambiguous reply now reaches the existing parse-retry
channel for both callers; no new stage gate is needed.

### Finding 3

**File:** `plan_tool/roadmap.py:1311`

**Summary:** The fix is reported to still be incomplete in the opposite
direction: a genuine whole-reply wrap with commentary on *both* sides of
the opening fence (before it, and between it and frontmatter) still
fails to be recognized, leaving a real wrapper's trailing fence
un-stripped and leaking into the persisted artifact.

**Failure scenario:** `reply = 'Sure, here it is:\n\n```markdown\nHere is the artifact:\n---\n...\n```'`.
The review reports `unmatched_opening` lands at neither `0` nor
`last_preamble_line_start`, so `has_outer_opener` is `False` and the
wrapper's trailing fence is left in the persisted output — the same
false-negative class as pass-18 findings 1/2, just with a preamble shape
that fix didn't anticipate either.

**Verification note (this session):** Reproduced directly — the trailing
fence is indeed left un-stripped for this exact input.

**Disposition:** **Confirmed, fixed by fail-closed retry in `35a32efa`.**
The response is intentionally retried rather than guessing whether the
commentary belongs to a genuine wrapper or an illustrative fence.

### Finding 4

**File:** `plan_tool/roadmap.py:1280`

**Summary:** The docstring's guarantee — "leaving a trailing artifact
fence intact after an earlier, unrelated unclosed illustrative fence" —
is reported false for the offset-0 case demonstrated in finding 1.

**Failure scenario:** A maintainer or auditor trusting this docstring
would conclude the offset-0 sub-case is already safe against unrelated
preamble fences and rule out finding 1's corruption as impossible per
the stated contract.

**Disposition:** **Confirmed, fixed in `35a32efa`.** The docstring now
states the direct-frontmatter boundary and the ambiguous-response retry rule.

### Finding 5

**File:** `tests/test_roadmap.py:5146`

**Summary:** No test is reported to exercise "unmatched opener at offset
0 followed by unrelated real content before frontmatter" — the existing
regression test `test_unrelated_unclosed_preamble_fence_preserves_artifact_closer`
places its illustrative fence after preceding preamble text, so its
unmatched opener never lands at offset 0 and cannot catch finding 1's
regression.

**Failure scenario:** The new `0` branch shipped with zero adversarial
coverage; the full suite stayed green despite the confirmed corruption,
per this project's own "a green suite says nothing about the sites you
didn't change" rule.

**Disposition:** **Confirmed, fixed in `35a32efa`.** The stage regression
first sends an offset-0 unclosed fence and then the commentary-on-both-sides
shape; both must retry before a clean artifact is written.

### Finding 6

**File:** `tests/test_roadmap.py:8355`

**Summary:** `TestMaterializePlanSeed`'s fixture is reported to have been
edited in place from a bare, preamble-free wrap to one with leading
commentary, while `TestCleanPath`'s fixture moved the opposite
direction — net effect, no test in the suite is reported to still send
`_materialize_plan_seed` a bare wrapped reply with zero preceding
commentary, even though that's one of the two ways the new
`has_outer_opener` tuple can fire.

**Failure scenario:** A future regression confined to
`_materialize_plan_seed`'s handling of a bare, preamble-free wrapper
would pass the full suite undetected, since coverage for that exact
input shape was reported moved rather than added alongside.

**Disposition:** **Confirmed, fixed in `35a32efa`.** Bare and
external-preamble seed wrappers now have distinct tests, and the exact
ambiguous preamble test proves seed materialization retries.

### Finding 7

**File:** `plan_tool/detail.py:2279`

**Summary:** `leading_reaches_eof` (an `any()` generator scan over
`scan.spans`) is now computed unconditionally before the cheap
`trailing_is_scanner_artifact` equality check, losing the short-circuit
evaluation order the prior single `A or B` expression had (cheap check
first).

**Failure scenario:** Every call where the trailing line is the lone
unmatched-opener scanner artifact — previously resolved by the cheap
equality alone — now also pays for a full scan of `scan.spans`. Reported
as low severity, a concrete newly-introduced regression in evaluation
order, not output.

**Disposition:** **Confirmed, fixed in `35a32efa`.** The scanner-artifact
equality now runs before the span scan, restoring the prior short circuit.

### Finding 8

**File:** `plan_tool/roadmap.py:1311`

**Summary:** No shared helper exists for "classify an unmatched-opener
position as an outer wrapper" even though `plan_tool/scope_fence.py`
already centralizes the analogous closing-character rule
(`_fence_run_closes`). `detail.py` and `roadmap.py` are reported to each
hand-roll a differently-shaped OR-of-positions predicate over the same
`FencedCodeScan` output, with no shared regression surface forcing them
to stay in sync.

**Failure scenario:** The review frames this as the pattern behind the
~18 rounds of review already churning on this logic: a fix to one file's
edge case has no mechanism forcing the sibling file's copy to be
updated, so the two predicates keep silently diverging — as they
already have, per findings 1 and 3 above.

**Disposition:** **Declined.** The detail and roadmap predicates implement
different contracts: detail strips one response boundary, while roadmap
classifies a frontmatter wrapper and fails closed on ambiguity. Sharing an
ownership helper would broaden the repair without resolving that distinction;
the shared CommonMark closer predicate is reused where the contract is exact.

### Finding 9

**File:** `plan_tool/roadmap.py:1311`

**Summary:** `has_outer_opener` OR's two independently-motivated
conditions into one positional-tuple membership test, inconsistent with
`detail.py`'s move in the same diff toward two separately-named booleans
for an analogous OR.

**Failure scenario:** A reader or debugger inspecting `has_outer_opener`
alone cannot tell which justification fired without re-deriving
`last_preamble_line_start` by hand.

**Disposition:** **Confirmed, fixed in `35a32efa`.** The positional tuple
is gone; the named direct-frontmatter check and ambiguity branch expose the
only two outcomes.

### Finding 10

**File:** `plan_tool/roadmap.py:1311`

**Summary:** Per `~/.claude/CLAUDE.md`'s "Prefer the explicit over the
implicit," this remains a purely positional heuristic — a numeric offset
matching one of two hand-picked "special" values — rather than a
structural signal, and the review reports it has already been defeated
twice within this diff's own two-round history (finding 1's new false
positive, finding 3's still-open false negative).

**Failure scenario:** The review frames each round as adding one more
special-cased offset to cover the last round's counter-example (round 17
added `last_preamble_line_start`, round 18 added `0`), with no finite
closed set of offsets exhaustive against arbitrary model commentary
placement.

**Disposition:** **Confirmed, fixed in `35a32efa`.** The repair stops adding
offset cases: any non-direct unmatched opener is rejected for retry.

### Finding 11

**File:** `plan_tool/roadmap.py:1318`

**Summary:** The trailing-candidate test is a bare
`lines[-1].rstrip() == "```"` string comparison, unlike `detail.py`'s
`_FENCE_CLOSE_RE.match(...)` + `_fence_run_closes(...)`, so it never
validates the candidate actually closes the opening fence's
character/run-length. Reported pre-existing, but inside the function
this diff modified.

**Failure scenario:** A reply that correctly opens with 4+ backticks per
`DETAIL_FORMAT.md`'s own guidance (for content containing its own
triple-backtick sequences) never has its trailing wrapper line stripped
by this function, leaving a stray fence-shaped line in the persisted
artifact even when `has_outer_opener` correctly identifies the wrapper.

**Disposition:** **Confirmed, fixed in `35a32efa`.** Roadmap now uses
`_FENCE_OPEN_RE`, `_FENCE_CLOSE_RE`, and `_fence_run_closes`; a four-backtick
wrapper regression proves the matching close is removed.

## Review pass 19 triage and repair (2026-09-11)

**Finding class:** the parser cannot reliably tell wrapper commentary from an
unclosed illustrative preamble fence once either has content before
frontmatter. The required property is no silent content deletion or addition;
the existing stage and seed retry loops are the smallest proof for ambiguous
replies, not a new wrapper-classification system.

**Pre-edit sweep:** `_strip_reply_lines` feeds `_lift_artifact_text` at both
`_run_stage` and `_materialize_plan_seed`. The identifier sweep covered
`has_outer_opener`, `unmatched_opening`, `last_preamble_line_start`, the
trailing closer comparison, and the detail scanner-artifact predicate. The
vocabulary sweep covered `outer`, `wrapper`, `preamble`, `frontmatter`,
`ambiguous`, `trailing`, `unmatched`, and `four-backtick` across source,
tests, the format contract, backlog, and handoff. Only roadmap owns the
frontmatter wrapper decision; the CommonMark closer rule is shared directly.

`35a32efa` accepts only an unmatched opener directly before frontmatter;
anything earlier yields no lifted artifact and consumes the existing retry
channel. The stage regression sends both reported ambiguous shapes before a
clean reply, and the seed regression covers the same class. Bare and
external-preamble seed wrappers remain accepted independently. Roadmap now
uses the shared closer predicate, including four-backtick wrappers. The detail
short circuit is restored without changing its parser result.

**Validation:** focused parser/stage/materialization suites — 87 passed,
2 skipped; complete affected modules — 1,094 passed, 168 skipped; full
parallel suite — 12,443 passed, 190 skipped.

### Next review (completed)

Pass 20 completed the independent review of `8fc86c27..35a32efa`; its
findings and subsequent triage appear below.

## Review pass 20 — /code-review high findings (2026-09-11)

**Scope:** `8fc86c27..35a32efa` — the pass-19 fix (the fail-closed,
ambiguous-opener-retry redesign), per the pass-19 triage's own explicit
next-review request.

**Method:** `/code-review --effort high --range 8fc86c27..35a32efa` run as
a background agent per the code-review-loop skill (85 tool uses, ~16
minutes; 3 parallel finder angles plus manual execution-based
verification, since this commit is itself a fix for 11 prior findings —
the review traced each disposition against the code rather than trusting
the handoff doc's claims, and stress-tested the new retry logic with
tilde fences, 4/5-backtick mismatches, CRLF, blank-line preambles, and
adversarial illustrative-fence shapes).

**Headline result:** the review reports **no new correctness regression** —
the redesign genuinely closes all 11 prior findings, including the
reintroduced-regression and the commentary-on-both-sides false negative,
and as a side effect now also intercepts one adversarial input shape the
old code silently mishandled. All 6 findings below are cleanup/efficiency/
hygiene items, including one pre-existing, already-documented residual
surfaced for recall — a material shift from rounds 17-19's pattern.

**Note:** the review's own full-suite run hit 2 failures in
`tests/cli/test_direct_cmd.py` from an xdist "node down" worker crash —
it identifies this as the already-documented, unrelated flake pattern in
`BUG_BACKLOG.md`, not a regression from this diff.

### Finding 1

**File:** `plan_tool/roadmap.py:1309`

**Summary:** The "find the first literal `---` line" search bounding the
preamble (and the identical search in `_lift_artifact_text`) is
fence-unaware, so a fully self-closed illustrative example in the
preamble containing its own fake `---`/`---` pair can still make
`_lift_artifact_text` return a garbage-but-non-`None` lift instead of
retrying.

**Failure scenario:** The review reports a constructed reply where a
preamble example fences its own fake frontmatter, and `_lift_artifact_text`
parses the fake frontmatter instead of the real one. It reports this is
currently caught by `check_artifact_non_empty` rejecting the resulting
empty `DomainArtifact` (forcing a retry) only because the fake preamble
happened to be empty-shaped — nothing prevents a coincidentally
row-shaped illustrative example from passing gates. Reported as
pre-existing (already named in the function's own docstring as a known,
deliberately unaddressed residual — "not attempted here; the stage's own
parse/gate retry loop is the backstop"), not introduced by this diff.

**Disposition:** **Deferred to the existing `BUG_BACKLOG.md` entry
"`_lift_artifact_text`'s frontmatter search can be misled…"** The review
reproduces its empty-shaped fake frontmatter case but does not provide a
row-shaped accepted artifact; that tracked design decision remains the
proportional owner.

### Finding 2

**File:** `plan_tool/roadmap.py:1329`

**Summary:** `if lines and lines[0].startswith('```'): lines = lines[1:]`
is reported to have zero effect on `_lift_artifact_text`'s output — dead
code left over from the redesign, since the sole caller independently
re-searches the *returned* lines for the frontmatter fence and joins
from that index onward regardless of whether this line was stripped.

**Failure scenario:** The review reports confirming by direct execution:
patching this step out and diffing `_lift_artifact_text`'s output across
several fixture shapes produces identical results in every case.

**Disposition:** **Confirmed, fixed in `b5ac8fd5`.** The leading-line
deletion cannot affect the later frontmatter-based lift and is removed.

### Finding 3

**File:** `plan_tool/roadmap.py` (commit-level)

**Summary:** Commit `35a32efa` is reported to bundle two independently-
reviewable fixes — the roadmap.py ambiguous-opener-retry redesign and an
unrelated detail.py short-circuit-evaluation-order fix — under a subject
naming only the former, which the review frames against this repo's own
`CLAUDE.md` "Make commits meaningfully bounded" rule.

**Failure scenario:** A future `git log -S`/blame search for the
detail.py performance fix, or a revert of just the roadmap redesign,
would not find or isolate it from the commit message alone per the
review.

**Disposition:** **Refuted as a required history rewrite.** `35a32efa` is
one bounded pass-19 remediation batch; the handoff records the detail
short-circuit change and its exact identifier. Splitting or amending a landed
commit would add history risk without changing the repair.

### Finding 4

**File:** `plan_tool/roadmap.py:1331`

**Summary:** The "does this candidate line actually close that opener"
check (`_FENCE_CLOSE_RE.match` then `_fence_run_closes`) is reported
duplicated verbatim between `roadmap.py`'s `_strip_reply_lines` and
`detail.py`'s `_strip_bare_fence_lines`, with no shared helper — narrower
than the already-declined "unify wrapper-classification predicates"
finding (pass-19 finding 8, which correctly stays declined per the
review since the two functions decide *whether* a fence is outer
differently), but this is purely the mechanical closer-matching
boilerplate.

**Failure scenario:** A future fix to the closing-match handling (e.g.
an escaping edge case) would need to be applied at both call sites by
hand per the review.

**Disposition:** **Declined.** Both callers already share the load-bearing
CommonMark run comparison. The remaining regex match necessarily consumes
different local input shapes, so another helper would add a wrapper without a
demonstrated consistency defect.

### Finding 5

**File:** `plan_tool/scope_fence.py:173`

**Summary:** `_fenced_code_spans` matches the fence-open pattern to build
`FencedCodeScan.unmatched_opening` but discards the captured fence-run
string; `roadmap.py`'s caller is reported to re-slice and re-match the
same source line a second time just to recover it.

**Failure scenario:** Reported as redoing work the scanner's own loop
already did moments earlier before discarding it. The review suggests an
`unmatched_opening_run: str | None` field on `FencedCodeScan` would let
the caller skip the second regex pass and its allocation entirely.

**Disposition:** **Declined.** Extending `FencedCodeScan` changes its shared
data contract merely to avoid one local re-match; no correctness property
requires it.

### Finding 6

**File:** `plan_tool/roadmap.py:1325`

**Summary:** `preamble[unmatched_opening:].splitlines()[0]` is reported to
copy and split the entire remainder of the preamble merely to obtain its
first line.

**Failure scenario:** Reported as low severity in practice since reply
preambles are short; the review suggests a `.find("\n", ...)`-bounded
slice would extract just the needed line without the full copy/split.

**Disposition:** **Declined.** Preambles are short and this micro-allocation
does not affect the safety property. A bespoke slice adds mechanism with no
measured benefit.

## Review pass 20 triage and cleanup (2026-09-11)

**Finding class:** the pass-19 fail-closed boundary is correct; the remaining
items are an existing design-owned residual or cleanup proposals. The
smallest proof remains that ambiguous input retries without content loss, not
a scanner API, a new classifier, or a performance abstraction.

**Scope sweep:** `_strip_reply_lines` has one caller through
`_lift_artifact_text`, reached by both stage and seed retry loops. The
identifier sweep covered the dead leading-line strip, frontmatter search,
closer matcher, `FencedCodeScan`, and the detail short circuit. The vocabulary
sweep covered `frontmatter`, `preamble`, `wrapper`, `fence`, `closer`,
`unmatched`, `retry`, and `ambiguity` across the source, tests, backlog, and
handoff. The later pass-22 review found that this listed sweep omitted the
active lessons ledger; pass-22 triage corrects that omission. The
fake-frontmatter route is the existing tracked residual; no new defect or owner
is created.

`b5ac8fd5` deletes only the dead leading-line strip. No output behavior
changes; the focused stage/seed suite passes (32 passed, 2 skipped) and the
complete roadmap suite passes (477 passed, 168 skipped). The last full-suite
run on the preceding source repair passed 12,443 tests with 190 skipped.

### Next review (completed)

Pass 21 completed the independent review of `35a32efa..b5ac8fd5`; its
findings and subsequent triage appear below.

## Review pass 21 — /code-review high findings (2026-09-11)

**Scope:** `35a32efa..b5ac8fd5` — `6ad44686` (pass-19 triage docs),
`879b733b` (pass-20 report), and `b5ac8fd5` (the 2-line cleanup), per the
pass-20 triage's own explicit next-review request.

**Method:** `/code-review --effort high --range 35a32efa..b5ac8fd5` run as
a background agent per the code-review-loop skill (153 tool uses, ~11
minutes, 10 finder angles). Because the code change is a pure 2-line
deletion, multiple angles empirically verified it is behavior-preserving
by reconstructing the pre-diff function and diffing its output against
post-diff across fixture sets up to a 400,000-case randomized fuzz —
zero divergence. **The review reports no correctness regression exists
in this diff.** All 4 findings below are documentation-consistency
issues.

**Note:** the review flagged that current HEAD has since advanced past
the reviewed range (`3e8e1342`, the pass-20 triage commit, landed after
`b5ac8fd5`) and explicitly asked that findings 3 and 4 be checked against
current HEAD before acting, since they might already be moot. This
session checked: finding 3 **is** moot (already resolved by `3e8e1342`);
finding 4 is **not** moot (still present at current HEAD) — see each
finding's own note below.

### Finding 1

**File:** `plan_tool/roadmap.py:1353`

**Summary:** At the reviewed snapshot, `_lift_artifact_text`'s docstring
claimed "a leading and a trailing fence are stripped independently," but
only the trailing fence was stripped as an independent step — the leading
fence was merely an incidental side effect of the `---`-search that already
existed.

**Failure scenario:** A maintainer trusting the docstring's contract
adds a new direct caller of `_strip_reply_lines` (bypassing
`_lift_artifact_text`) expecting a leading wrapper-fence line to already
be stripped from the returned `lines`; it will not be, since that
guarantee no longer exists as an independent mechanism, per the review.

**Disposition:** **Confirmed, fixed in `0a71f922`.** The docstring now
separates first-frontmatter selection from the conditional final-fence strip.

### Finding 2

**File:** `plan_tool/roadmap.py:1275`

**Summary:** At the reviewed snapshot, `_strip_reply_lines`'s one-line
docstring summary "Drop outer preamble/trailing fences from a stage reply"
overclaimed post-diff behavior: the function only validates an ambiguous
opener (returning `[]` if unsafe) and drops a trailing closer — it no longer
drops a leading preamble fence line itself.

**Failure scenario:** Same class as finding 1 (the review notes both
were seeded by the same deletion) — a reader debugging leading-fence
behavior looks for a strip step in this function that no longer exists.

**Disposition:** **Confirmed, fixed in `0a71f922`.** The helper now states
its fail-closed ambiguity boundary and conditional trailing-fence behavior.

### Finding 3

**File:** `docs/evidence/authored-artifact-structure-versioning.md`

**Summary:** The review reports pass-20 finding 2 (describing exactly the
dead code `b5ac8fd5` deletes) was left `**Disposition:** _(pending)_` at
the end of the reviewed range, instead of being updated inline as every
other resolved finding across passes 17-20 has been.

**Verification note (this session):** **Already moot.** `3e8e1342` (the
pass-20 triage commit, landed after `b5ac8fd5` but before this review
ran) already fills in this exact disposition ("Confirmed, fixed in
`b5ac8fd5`"). The review itself flagged this possibility and asked for
it to be checked against current HEAD before acting; confirmed resolved.

**Disposition:** **Refuted as an actionable current defect.** `3e8e1342`
already recorded the fix before this review began, so no second update is
needed.

### Finding 4

**File:** `docs/evidence/authored-artifact-structure-versioning.md:389`

**Summary:** At the reviewed snapshot, the pass-20 summary text (appearing
near-verbatim in two places) stated "6 lower-severity cleanup/efficiency
findings plus one pre-existing, already-documented residual," which read as
7 total, but the itemized list contained only 6 findings, one of which
(finding 1) *was* that same residual, not an additional 7th item.

**Failure scenario:** A reader reconciling the stated count against the
6 itemized findings either goes looking for a missing 7th finding or
miscounts the actual yield.

**Verification note (triage):** Confirmed at the pre-triage snapshot in both
locations the review cited; this triage corrects the wording.

**Disposition:** **Confirmed, fixed in this triage.** Both summaries now
state that the pre-existing residual is one of the six findings.

## Review pass 21 triage and documentation repair (2026-09-11)

**Finding class:** post-cleanup documentation and handoff status must describe
the fail-closed parser boundary and the exact review count without implying a
second leading-fence strip or a seventh finding. The smallest repair is wording
at those sites; parser behavior and the deferred fake-frontmatter design remain
unchanged.

**Pre-edit sweep:** `_strip_reply_lines` and `_lift_artifact_text` are the two
docstring identifiers, with their two stage/seed callers checked for a changed
contract. The vocabulary sweep covered `leading`, `trailing`, `preamble`,
`frontmatter`, `wrapper`, `ambiguous`, `six`, `residual`, and `Next review` in
the source and handoff. It found two count summaries, one stale completed-review
marker, and no further promise of independent leading-fence stripping.

`0a71f922` changes only the two source docstrings. The handoff records the
already-resolved pass-20 disposition, corrects both count summaries, and marks
the pass-20 review request completed. The roadmap suite passes: 477 passed,
168 skipped.

### Next review (completed)

Pass 22 completed the independent review of `b5ac8fd5..0a71f922`; its
findings and subsequent triage appear below.

## Review pass 22 — /code-review high findings (2026-09-11)

**Scope:** `b5ac8fd5..0a71f922` — the pass-21 docstring/doc repair, per the
pass-21 triage's own explicit next-review request.

**Method:** `/code-review --effort high --range b5ac8fd5..0a71f922` run as
a background agent per the code-review-loop skill (107 tool uses, ~22
minutes; 7 parallel background angles covering 10 perspectives, plus
independent verification via git history, direct code execution, and
cross-file greps). The diff touches only a handoff markdown log and two
docstring rewrites in `plan_tool/roadmap.py` — zero executable code
changed in the reviewed range — yet several of the diff's own new claims
are reported inaccurate against the code and `git log`, and cross-file
tracing (prompted by the diff's own precedent citation to
`detail.parse_detail_response`) surfaced one real, pre-existing bug in a
sibling function.

### Finding 1

**File:** `plan_tool/detail.py:2450` (`parse_jira_detail_response`)

**Summary:** At the reviewed snapshot, this function's docstring claimed
"the same envelope leniency as `parse_detail_response`... a leading or
trailing fence is stripped independently," but `parse_detail_response`
used the fence-run-aware `_strip_bare_fence_lines`, while
`parse_jira_detail_response` inlined a naive check with no pairing/fence-run
awareness — the exact truncation class the roadmap repair had disavowed.

**Failure scenario:** A jira-grade detail response whose legitimate final
content is a closing code-fence line has that line unconditionally
stripped, silently truncating real content — the same truncation class
`roadmap.py`'s fix exists to prevent. Reported not introduced by this
diff, but surfaced by tracing this diff's own precedent cross-reference.

**Verification note (this session):** Reproduced directly — with
`raw = "# Title\n\nSome content\n\nExample:\n```\nreal trailing content that legitimately ends in a fence\n```"`,
the unconditional trailing-strip removes the real closing fence, leaving
the content improperly un-fenced. Confirms the underlying mechanism; the
full `parse_jira_detail_response` call separately returns `body=None`
for this exact input for unrelated downstream gate reasons, but the
truncation bug in the stripping step itself is real.

**Disposition:** **Confirmed, fixed in `984ea390`.** The Jira parser now
uses `_strip_bare_fence_lines`; a valid Jira-grade body with a final content
fence remains accepted unchanged.

### Finding 2

**File:** `plan_tool/roadmap.py:1275`

**Summary:** At the reviewed snapshot, `_strip_reply_lines`'s new docstring
headline stated fail-closed behavior as unconditional, but the guard was
skipped when `strip_unpaired_trailing_fence=True`.

**Failure scenario:** The review reports verifying by direct execution:
the same ambiguous-inner-fence input returns `[]` with
`strip_unpaired_trailing_fence=False` but a full non-empty line list with
`strip_unpaired_trailing_fence=True` — contradicting the headline's
unqualified claim for a caller in that mode.

**Disposition:** **Confirmed, fixed in `4aee8839`.** The headline now names
the explicit unpaired-stripping exception.

### Finding 3

**File:** `plan_tool/roadmap.py:1354`

**Summary:** At the reviewed snapshot, `_lift_artifact_text`'s docstring
said "a matching final fence is conditionally stripped," but under
`strip_unpaired_trailing_fence=True` any trailing fence-shaped line was
stripped regardless of whether it matched the opener's character/run length.

**Failure scenario:** The review reports verifying by direct execution: a
reply opening with `` ``` `` and ending in a non-matching `~~~` line has
the mismatched `~~~` stripped anyway when
`strip_unpaired_trailing_fence=True`, contradicting the word "matching."

**Disposition:** **Confirmed, fixed in `4aee8839`.** The docstring now says
only that a final fence is conditionally stripped.

### Finding 4

**File:** `docs/evidence/authored-artifact-structure-versioning.md:5714`

**Summary:** Pass-21 findings 1 and 2 (about the exact two `roadmap.py`
docstring overclaims) were reported left `_(pending)_` at this diff's own
end state (`0a71f922`), even though `0a71f922` — the final commit in this
same diff — already applies exactly the fix each finding describes.

**Verification note (this session):** Already moot — as with round 21's
analogous finding, this was resolved by `6d5924ab`, which landed after
`0a71f922` but before this review ran, and is already reflected at
current HEAD.

**Disposition:** **Refuted as an actionable current defect.** `6d5924ab`
already recorded both dispositions before this review began.

### Finding 5

**File:** `docs/evidence/authored-artifact-structure-versioning.md:5668`

**Summary:** A "### Next review" heading added within this diff is
reported to still read "Convergence remains open... is the next required
evidence" even though "## Review pass 21," added six lines below within
this same diff, already performs exactly that review — unlike every
sibling heading in this file (including one earlier in this same diff,
correctly updated to "(completed)").

**Failure scenario:** A reader scanning for outstanding review
obligations sees an apparently open request for a range already
reviewed.

**Disposition:** **Refuted as an actionable current defect.** `6d5924ab`
already marked this pass-21 request completed before this review began.

### Finding 6

**File:** `docs/evidence/authored-artifact-structure-versioning.md:394`

**Summary:** At the reviewed snapshot, two descriptions of the pass-21 range
as "the cleanup commit plus its docs commit" undercounted it —
`git log --oneline 35a32efa..b5ac8fd5` shows three commits, including the
pass-19 triage docs commit.

**Failure scenario:** A reader trusting this description to bound what
pass 21 actually reviewed undercounts by a full commit's worth of
handoff prose.

**Disposition:** **Confirmed, fixed in this triage.** Both range
descriptions now name all three commits.

### Finding 7

**File:** `docs/evidence/authored-artifact-structure-versioning.md`

**Summary:** Pass-21 finding 3 cites a specific line number for pass-20
finding 2's stale disposition, but the review reports that at this
diff's own endpoint that line number lands on unrelated text (finding
2's own file-line, not the disposition, which sits elsewhere) — the
citation is reported wrong even on arrival, not only after later drift.

**Failure scenario:** A reader jumping to the cited line to verify the
claim lands on the wrong text and cannot confirm the finding.

**Disposition:** **Confirmed, fixed in this triage.** The cited pass-21
finding now names the pass-20 finding without a fragile line number.

### Finding 8

**File:** `.plan-tool/lessons/project.md:1352`

**Summary:** At the reviewed snapshot, this actively-consulted lessons ledger
told future plan steps to mirror naive independent leading/trailing fence
stripping — the exact truncation mechanism this review found in the Jira
parser. The prior scope sweep omitted the lessons ledger.

**Failure scenario:** A future plan step building a new
generate-parse-retry loop reads this lesson as the precedent to copy and
reimplements naive independent leading/trailing fence stripping,
reintroducing the truncation-risk class this repo's fence-handling
rounds already moved away from — the review connects this directly to
finding 1's sibling defect in `parse_jira_detail_response`, which still
has exactly this shape.

**Disposition:** **Confirmed, fixed in `984ea390`.** The lesson now points
to preamble skipping and `_strip_bare_fence_lines`' content-fence protection.

**Note on scope (from the review itself):** finding 1 sits outside the
literal diff range but is reported per the review's recall-mode
guidance, since it was found by tracing this diff's own precedent
citation and shares the exact defect class the diff's docstring fix
addresses. Findings 2-8 are within the reviewed range.

## Review pass 22 triage and repair (2026-09-11)

**Finding class:** a Jira-grade reply must preserve a real final content fence;
the existing fence-aware helper is the smallest proof. Its option-sensitive
roadmap documentation and the active authoring lesson must describe that same
boundary, while completed review pointers and range descriptions must remain
factual.

**Pre-edit sweep:** `parse_jira_detail_response` has three runtime consumers
(cached detail reuse, authoring retries, and checkpoint validation), all routed
through this one parser. The identifier sweep covered
`_strip_bare_fence_lines`, `strip_unpaired_trailing_fence`, both roadmap lift
helpers, the pass-21 range, and its cited pass-20 finding. The vocabulary sweep
covered `fence`, `leading`, `trailing`, `wrapper`, `content`, `preamble`,
`independent`, `matching`, `Next review`, and `cleanup` across source, tests,
the lessons ledger, and handoff. It found no second naive Jira envelope parser.

`984ea390` routes the Jira parser through the existing fence helper, then keeps
its prior newline normalization when building the validated body. Its regression
is a full Jira-grade acceptance case whose final code fence remains content;
the complete detail suite passes (619 passed). `4aee8839` updates only the two
roadmap docstrings. This handoff records the two already-resolved findings,
corrects the two three-commit range descriptions, and removes the invalid
line-number citation.

### Next review (completed)

Pass 23 completed the independent review of `0a71f922..4aee8839`; its
findings and subsequent triage appear below.

## Review pass 23 — /code-review high findings (2026-09-11)

**Scope:** `0a71f922..4aee8839` — the pass-22 jira-fence fix (`984ea390`)
plus the roadmap docstring qualification (`4aee8839`), per the pass-22
triage's own explicit next-review request. All 7 findings below are
within this reviewed range (no out-of-range/recall-mode findings this
round).

**Method:** `/code-review --effort high --range 0a71f922..4aee8839` run as
a background agent per the code-review-loop skill (101 tool uses, ~18
minutes, 10 parallel finder angles plus direct execution verification of
the top candidate against pre-fix (`984ea390^`) and post-fix (`984ea390`)
behavior, confirmed independently by two separate traces).

**Headline result:** the fix that was supposed to stop
`parse_jira_detail_response` from truncating a legitimate trailing
content fence (pass-22 finding 1) is reported to introduce a **new
regression** for the combined case — a response wrapped entirely in an
outer code fence *and* legitimately ending in its own example fence —
which now gets wrongly rejected, where it parsed fine before that fix.

### Finding 1 — headline

**File:** `plan_tool/detail.py:2454`

**Summary:** At the reviewed snapshot, the new call through
`_strip_bare_fence_lines` regressed a Jira-grade response that both wrapped
its whole reply in an outer code fence and legitimately ended its own content
in a trailing example fence.

**Failure scenario:** `raw = '```\n' + _JIRA_BODY + '\nExample:\n```\nreal trailing content\n```\n' + '```\n'`
(whole reply wrapped, content ends in its own fenced example). The
review reports verifying by direct execution: at `984ea390^`,
`parse_jira_detail_response(raw).body` parses with no findings; at
`984ea390`, it returns `body=None` with two `unterminated-fence`
blocking findings. Root cause reported in `_strip_bare_fence_lines`:
`_fenced_code_spans` pairs fences by nearest-neighbor, misattributing
the outer wrap's opener as paired with the inner example's opener,
leaving the outer closer un-stripped as literal trailing content. The
review reports this reaches the retry loop (feeding a bogus complaint
back to the model) and the resume-checkpoint pre-scan (silently
invalidating a previously-valid cached checkpoint with no diagnostic).
The added test from the pass-22 fix does not cover this combined
wrap+trailing-fence scenario.

**Verification note (this session):** Reproduced directly with the
review's exact repro — `body is None` with two `unterminated-fence`
blocking findings, confirming the regression.

**Disposition:** **Confirmed, fixed in `e12f9ac6`.** A bare matching
first/last wrapper is removed before nested fences are scanned; the Jira and
run-grade combined-wrapper regressions both preserve the final content fence.

### Finding 2

**File:** `plan_tool/detail.py:2456`

**Summary:** At the reviewed snapshot,
`parse_jira_detail_response`'s `first_heading` scan was a plain,
non-fence-aware search for a line starting with `#`, unlike
`parse_detail_response`'s fence-aware scan.

**Failure scenario:** The review reports a preamble commentary example
whose fenced content happens to start with `#` (e.g. a shell comment)
causes the naive scan to pick the fenced line as `first_heading`,
slicing off the fence's own opener while keeping its closer and
corrupting fence balance downstream — the well-formed response is
rejected even though the real heading was present and unambiguous.

**Disposition:** **Confirmed, fixed in `e12f9ac6`.** The Jira scan now skips
headings inside closed fenced preambles; a regression proves it selects the
real detail heading.

### Finding 3

**File:** `plan_tool/detail.py:2462`

**Summary:** At the reviewed snapshot, `line.rstrip("\r\n")` stripped only
literal CR/LF after `splitlines(keepends=True)`, so other Unicode
line-boundary characters could survive in the parsed body.

**Failure scenario:** The review reports verifying by direct execution:
a jira body containing a mid-line form feed is preserved verbatim
post-diff, where pre-diff it was normalized to a plain `\n`. The written
detail file on disk now silently carries a stray control character it
did not before.

**Disposition:** **Confirmed, fixed in `e12f9ac6`.** The parsed Jira body
again uses the prior `splitlines()` normalization; a form-feed regression
proves it becomes a newline.

### Finding 4

**File:** `plan_tool/detail.py:2252`

**Summary:** At the reviewed snapshot, `_strip_bare_fence_lines`'s docstring
said "Both current call sites" after this diff added a third.

**Failure scenario:** A reader relying on "Both" to enumerate every
caller of this invariant undercounts by one.

**Disposition:** **Confirmed, fixed in `e12f9ac6`.** Its docstring now names
all three callers.

### Finding 5

**File:** `plan_tool/detail.py:2447`

**Summary:** The new `parse_jira_detail_response` docstring states a
true-but-incomplete guarantee without disclosing the still-present
non-fence-aware heading-scan gap (finding 2). The review frames this
against this repo's own `CLAUDE.md` "Prefer the explicit over the
implicit," noting the sibling docstring touched in the same commit
range (`roadmap.py`'s `_strip_reply_lines`) explicitly names its own
closely analogous residual gap, while this one leaves it implicit.

**Failure scenario:** Inconsistent documentation convention applied two
lines apart in the same diff, per the review.

**Disposition:** **Refuted as a separate defect.** Finding 2 removes the
heading-scan gap; the corrected docstring remains terse and no residual needs
its own disclosure.

### Finding 6

**File:** `plan_tool/detail.py:2812`

**Summary:** Resumed jira-grade checkpoints are reported to now be
parsed via the heavier `_strip_bare_fence_lines` → `_fenced_code_spans`
full-text regex scan twice per resumed step, instead of the old
two-line index check done twice.

**Failure scenario:** Reported as pure wasted work on the ordinary
resume happy-path — ordinary efficiency cost, not a correctness issue.

**Disposition:** **Declined.** No measurement identifies this short parser
scan as material, and its fence scan is the safety boundary that preserves
unpaired-tail tolerance outside the explicit bare-wrapper case.

### Finding 7

**File:** `tests/test_detail.py:16263`

**Summary:** No test in `TestJiraGradeGate` is reported to combine
"response wrapped in an outer fence" with "content legitimately ends in
its own fence" — exactly the combination confirmed broken in finding 1.

**Failure scenario:** The review reports the suite added by the pass-22
fix would not have caught finding 1's regression, and still won't catch
a re-regression, since the two existing tests each exercise only one
half of the interaction.

**Disposition:** **Confirmed, fixed in `e12f9ac6`.** The Jira regression now
combines the whole-reply wrapper with the final content fence.

## Review pass 23 triage and repair (2026-09-11)

**Finding class:** a bare whole-reply wrapper must be removed before a scanner
can mistake its nested same-run fence for the wrapper close; otherwise the
actual final wrapper fence remains as content. The Jira parser must also select
only an unfenced heading and preserve its pre-existing Unicode newline
normalization. These are parser properties, not an invitation to generalize
the fence scanner or optimize its unmeasured resume cost.

**Pre-edit sweep:** `_strip_bare_fence_lines` has two run-grade callers and
one Jira-grade caller. Replaying the reported wrapper shape against the two
run-grade paths found the same appended-outer-fence result, so both receive the
same bounded first/last bare-wrapper guard. The identifier sweep covered the
wrapper helper, `_fenced_code_spans`, `_fence_run_closes`, first-heading scan,
and newline normalization. The vocabulary sweep covered `bare`, `outer`,
`wrapper`, `nested`, `fence`, `heading`, `preamble`, `content`, `Unicode`,
`checkpoint`, and `resume` across source, tests, and handoff.

`e12f9ac6` adds one narrow shared boundary: only a valid bare first/last fence
pair is removed before the existing scanner handles all other shapes. It leaves
the existing info-string wrapper behavior intact, including the early-close
regression coverage. The repair adds Jira wrapper/content, fenced-preamble, and
Unicode-normalization tests plus the matching run-grade wrapper/content test.
The complete detail suite passes: 623 passed.

### Next review

Convergence remains open. A fresh independent code review of
`4aee8839..e12f9ac6` is the next required evidence; the separate review process
will record its result in this handoff.

## Review pass 24 — /code-review high findings (2026-09-11)

**Scope:** `4aee8839..e12f9ac6` — the pass-23 nested-fence fix, per the
pass-23 triage's own explicit next-review request.

**Method:** `/code-review --effort high --range 4aee8839..e12f9ac6` run as
a background agent per the code-review-loop skill (135 tool uses, ~31
minutes, 6 finder angles, three consolidated report iterations).

**Load-bearing discovery, verified by this session:** the review reports
— and this session independently confirmed by reading the code —
**`parse_jira_detail_response` is currently unreachable in production.**
All three of its call sites sit downstream of
`_raise_if_jira_detail_authoring_requested`, whose own docstring reads
"Refuse the retired compact-detail writer before it can mutate state,"
and one call site passes the literal `GRADE_JIRA` constant rather than a
variable. **This means the entire pass-22/pass-23 jira-fence effort
(`984ea390`, `e12f9ac6`'s jira-side changes) modified dead code.** The
review reclassifies each finding's severity as LIVE (reachable via
`parse_detail_response`, the default, unguarded authoring path, or its
checkpoint-resume path) or DEAD (reachable only through the disabled
jira writer) accordingly — preserved in each finding below.

### Finding 1 — headline (LIVE)

**File:** `plan_tool/detail.py:2250` (`_strip_whole_bare_fence_wrapper`)

**Summary:** The new pre-pass checks only `lines[0]`/`lines[-1]` in
isolation and never verifies (via a full-text scan, as its sibling
`_strip_bare_fence_lines` does) that they form one contiguous fence span
across the whole text. The guard that appears intended to catch this
only scans the isolated first line in isolation, so it is reported
always `False` and never fires — confirmed by the review's 6 independent
execution passes.

**Failure scenario:** A run-grade response that legitimately opens with
its own small self-closed fenced example and separately, legitimately
ends with an unrelated fenced example. The leading block's opener and
trailing block's closer get stripped even though they don't pair with
each other; the orphaned interior fence lines swallow the whole real
body as unterminated, so `parse_detail_response` wrongly returns `None`
for a fully valid document.

**Verification note (this session):** Reproduced directly via
`parse_detail_response` with an independent leading+trailing fenced-block
shape — returns `None`. Also checked against the pre-`e12f9ac6` parent
commit (`4aee8839`): the identical input **also** returns `None` there.
This is not a new regression introduced by `e12f9ac6` — it is a
pre-existing live gap that `e12f9ac6`'s stated purpose ("preserve nested
detail fence wrappers") targeted but did not actually close, because its
guard is vacuous.

**Disposition:** _(pending)_

### Finding 2 (LIVE, consequence of finding 1)

**File:** `plan_tool/detail.py:4150`

**Summary:** The run-grade checkpoint pre-scan (no jira guard applies)
calls `parse_structured_detail_response`, which calls
`parse_detail_response`; it only checks whether the parsed checkpoint is
`None` to decide usability. Finding 1's corruption is reported to sail
through this gate as an outright rejection.

**Failure scenario:** A `run --resume` on a step whose cached response
has finding 1's shape has its previously-valid checkpoint silently
discarded with no diagnostic, forcing a wasted re-invocation of an
already-correct step.

**Disposition:** _(pending)_

### Finding 3 (LIVE, pre-existing)

**File:** `plan_tool/detail.py:267` (`_H2_HEADING_RE`)

**Summary:** `parse_detail_response`'s heading regex is anchored on a
literal `\n` and is reported not aware of the broader Unicode
line-boundary set `str.splitlines()` treats as line breaks (e.g. form
feed). A heading preceded by such a character is invisible to section
detection — its content folds into the previous section and a false
"model omitted this section" stub is fabricated. The review reports this
diff fixed the identical defect class in the (dead) sibling
`parse_jira_detail_response` while adding a docstring claiming the two
parsers share "the same envelope leniency" — leaving the live parser's
version of the same bug unfixed and now misleadingly claimed as parity.

**Failure scenario:** The review reports verifying directly: a
`_GOOD_BODY`-shaped response with a form-feed character before a real
heading has that heading's content silently merged into the prior
section, with a fabricated stub appended claiming the model omitted it.
Confirmed present at both `4aee8839` and current HEAD — pre-existing,
newly misleading given this diff's unequal fix and new parity claim.

**Disposition:** _(pending)_

### Finding 4 (DEAD today, genuine new regression)

**File:** `plan_tool/detail.py:2485`

**Summary:** `parse_jira_detail_response`'s new fence-aware heading scan
is reported to treat an unclosed/illustrative fence anywhere in the
preamble as swallowing everything after it (including the real heading)
to end-of-text. The old naive scan had no such fence-awareness and found
the heading regardless. The review reports this is dead code today
(gated behind the disabled jira writer) but will corrupt output the
moment jira-grade authoring is ever re-enabled; it also reports checking
the mirror case for the live run-grade parser and finding the same
unclosed-fence-swallows-heading behavior reproduces there too, but
confirmed identical before and after this diff (pre-existing, not
introduced or fixed by it).

**Disposition:** _(pending)_

### Finding 5 (LIVE and dead-reachable)

**File:** `plan_tool/detail.py:2296`

**Summary:** `_strip_bare_fence_lines`'s pre-existing unconditional
leading-line strip (whenever line 0 opens any fence, info-string or not)
is reported to still corrupt a body whose first line legitimately opens
its own small, already-closed nested example, contradicting this diff's
docstring claim that "nested examples stay content."

**Failure scenario:** The review reports a response opening with an
info-string-bearing fenced example (bypassing the new pre-pass) followed
by the actual step content — rejected via the jira path (dead code) with
spurious findings, and reproduced via `parse_detail_response`'s plain
path too. Reported pre-existing (also present at `4aee8839`), not new,
but the exact defect class this diff's docstring now claims closed.

**Disposition:** _(pending)_

### Finding 6 (dead today, will matter if jira is re-enabled)

**File:** `plan_tool/detail.py:477`

**Summary:** When either jira-side corruption bug (findings 4-5) zeroes
out `JiraDetailParse.findings`, `_jira_retry_suffix([])` is reported to
return only a generic contract restatement with no specific complaint.

**Failure scenario:** Latent per the review: once jira-grade authoring
is reachable again, a model emitting a valid body with an incidental
unclosed preamble fence would get a content-free retry prompt and likely
repeat the mistake until attempts exhaust.

**Disposition:** _(pending)_

### Finding 7 (LIVE relevance — governs shared helpers)

**File:** `DETAIL_FORMAT.md:245`

**Summary:** `_strip_bare_fence_lines`'s docstring still cites "rule 2
for the full, non-obvious contract," but the review reports rule 2 (last
touched before this diff's range) was not updated to describe the new
pre-pass, its bare/no-info-string/pairing criteria, or the interaction
hazards in findings 1 and 5 — despite this doc's established pattern of
tracking every prior nuance change in this exact area with round
annotations.

**Disposition:** _(pending)_

### Finding 8 (LIVE, docstring accuracy)

**File:** `plan_tool/detail.py:2274`

**Summary:** `_strip_bare_fence_lines`'s docstring claims "All three
current call sites pass already-`.strip()`ed text, so `lines[0]` is not
expected to be blank," but the review reports that since this diff wires
the new pre-pass in front of all three call sites, a blank `lines[0]` is
now a normal, easily reachable outcome (functionally harmless, since the
existing defended-against path handles it), not the rare edge case the
docstring frames it as.

**Disposition:** _(pending)_

### Finding 9 (reuse/cleanup)

**File:** `plan_tool/detail.py:2485`

**Summary:** The new heading-scan loop is reported to hand-roll "is this
offset inside a fenced span" via manual offset tracking, duplicating the
existing `_matches_outside_fences` helper already used elsewhere in this
file and `_detail_response_body_start`'s own established pattern — now a
third independent implementation of the same primitive.

**Failure scenario:** Not a runtime divergence by itself, per the review,
but a future correction to fence-exclusion boundary semantics would need
to be applied in multiple places with nothing enforcing they stay in
sync.

**Disposition:** _(pending)_

### Finding 10 (test-coverage gap, recurring pattern)

**File:** `tests/test_detail.py:1844`

**Summary:** The review reports no test covers: independent
leading+trailing fenced blocks (finding 1, live), an unclosed preamble
fence before a real heading (finding 4), a leading example with an info
string or nested inside a genuine wrap (finding 5), or the Unicode-boundary
normalization gap between the two "same-contract" siblings (finding 3,
live) — despite this diff explicitly targeting fence-wrapper
interactions. The review explicitly notes this is the same "added
coverage proves only the narrow fixed case" pattern already flagged in
this handoff (pass-23 finding 7), now recurred in the very fix meant to
close it.

**Disposition:** _(pending)_

### Finding 11 (minor, live but low-impact)

**File:** `plan_tool/detail.py:2254`

**Summary:** The opening-line "bare" check in
`_strip_whole_bare_fence_wrapper` is reported to use unqualified
`.rstrip()` (strips the full Unicode-whitespace class) while the closing
line's bareness is governed by the stricter `_FENCE_CLOSE_RE` (ASCII
space/tab only) — an inconsistent definition of "bare" between the two
ends of one check.

**Disposition:** _(pending)_

## Maintenance lesson: verify the live path before hardening a parser

The 2026-09 review finds two rounds of wrapper fixes on a Jira parser behind a
retired-writer guard while the intended live-parser defect remains. The example
supports a concrete maintenance rule: trace production callers before changing a
parser, reproduce the stated failure on the live route, and test the sibling input
combinations a fix can affect.

Keep any decision to restore a retired route separate from a fix to current
behavior. If a proposed remedy changes scope or hardens an unreachable path,
surface that decision before adding more parser machinery. The pending round-24
findings above retain their evidence for a current-code review.

## References

- The source entry #356 was deleted by completed plan step 7; this handoff and
  the completed plan now hold its implementation record.
- [BACKLOG #362](../../BACKLOG.md) — the deferred roadmap follow-up entry, filed
  2026-09-08, carrying its own re-entry trigger and design questions.
- [Authored Artifact Format Version](../implementation-plans/archive/2-authored-artifact-format-version.md)
  — the bare plan, revised to two classes and 7 steps.
- [`DATA_CONTRACT.md`](../../DATA_CONTRACT.md) § "Version-evolution policy" — the
  fail-closed reader rule this work extends to the authored-artifact layer.
- [Roadmap Evidence Version-1 Retirement](../history/roadmap-evidence-v1-retirement.md)
  — the retirement-record shape policy rule 4 reuses.
- [Roadmap Immutable Candidate Versions](../implementation-plans/archive/2-roadmap-immutable-candidate-versions.md)
  — the completed content and lineage contract, preserved unchanged.
- `BACKLOG.md` #242 and `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md`
  — the separate paused content-retention route (the retention handoff was retired 2026-09-29).
- `plan_tool/parser.py:write_plan`, `plan_tool/roadmap_versions.py:_require_content_matches_record`,
  `plan_tool/roadmap_source_identity.py:BASELINE_FORMAT_VERSION` — the seams
  verified 2026-09-08.
