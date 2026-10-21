> **Withdrawn 2026-08-11** — Withdrawn after the detail-stage audit exposed an unresolved high-severity provenance-ordering defect and non-convergent correctness contracts; re-seed the capability from the audited invariants before implementation.
> Preserved here for history; do not edit.

---
title: Bad Fix Provenance
intent: A same-issue recurrence after an applied remedy note surfaces as a recommend-only
  bad-fix advisory; identity alone stays non-causal.
status: planning
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Route existing apply annotations through one writer
  intent: Makes every existing interactive and completeness-apply disposition use
    one behavior-preserving durable annotation path.
  files:
  - plan_tool/review_persistence.py
  - plan_tool/review_walk.py
  - plan_tool/cli/completeness_cmd.py
  - plan_tool/cli/completeness_apply_parallel.py
  - tests/test_review_persistence.py
  - tests/test_review_walk.py
  - tests/cli/test_completeness_cmd.py
  - tests/cli/test_completeness_apply_parallel.py
  complexity: medium
  change_type: refactor
  detail: docs/implementation-plans/plan-details/bad-fix-provenance/01-route-existing-apply-annotations.md
  status: current
- id: 2
  title: Persist qualified remedy provenance on annotations
  intent: Adds ordered, source-marked operator remedy evidence without treating automated
    apply output or legacy annotations as causal evidence.
  files:
  - plan_tool/review_persistence.py
  - plan_tool/review_walk.py
  - plan_tool/cli/completeness_cmd.py
  - plan_tool/cli/completeness_apply_parallel.py
  - plan_tool/convergence_diagnosis.py
  - tests/test_review_persistence.py
  - tests/test_review_walk.py
  - tests/cli/test_completeness_cmd.py
  - tests/cli/test_completeness_apply_parallel.py
  - tests/test_convergence_diagnosis.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: Supplies the behavior-preserving writer seam every producer will use.
  detail: docs/implementation-plans/plan-details/bad-fix-provenance/02-persist-qualified-remedy-provenance-on.md
- id: 3
  title: Add the completeness-record command for hand-applied findings
  intent: Lets an operator preserve remedy evidence after editing a finding by hand,
    using completeness-apply's newest-report default and --id override, with a required
    explicit remedy note for an applied record.
  files:
  - plan_tool/cli/completeness_cmd.py
  - plan_tool/cli/app.py
  - plan_tool/cli/parser.py
  - plan_tool/cli/__init__.py
  - plan_tool/repo_lock.py
  - CAPABILITIES.md
  - docs/cli/README.md
  - tests/cli/package_surface_help.golden.txt
  - tests/cli/test_completeness_cmd.py
  - tests/test_repo_lock.py
  creates:
  - docs/cli/completeness-record.md
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  depends_on_notes:
    2: Provides source-marked, timestamped remedy evidence for the selected Annotation.
  detail: docs/implementation-plans/plan-details/bad-fix-provenance/03-completeness-record-command-hand.md
- id: 4
  title: Extract the shared fuzzy-title comparison
  intent: Moves only _matches's existing tier-3 title comparison into a shared helper,
    preserving every current matcher result before bad-fix uses it.
  files:
  - plan_tool/convergence_diagnosis.py
  - tests/test_convergence_diagnosis.py
  complexity: low
  change_type: refactor
  detail: docs/implementation-plans/plan-details/bad-fix-provenance/04-extract-shared-fuzzy-title-comparison.md
- id: 5
  title: Add the bad-fix provenance advisory to convergence
  intent: Warns operators when a recurring issue follows a recorded applied remedy
    so they re-check that edit before blaming plan structure; uses a dedicated same-issue
    helper and its own identity×note predicate (not edit-drift's prior-apply set),
    only for unresolved findings in the newest of at least three distinct collapsed
    same-stage passes.
  files:
  - plan_tool/convergence_diagnosis.py
  - plan_tool/cli/completeness_cmd.py
  - tests/test_convergence_diagnosis.py
  - tests/cli/test_convergence_cmd.py
  - tests/cli/test_completeness_cmd.py
  - tests/test_audit_shapes.py
  complexity: high
  change_type: feature
  depends_on:
  - 2
  - 3
  - 4
  depends_on_notes:
    2: Supplies source-marked, ordered evidence that can qualify as an intervening
      remedy.
    3: Adds the explicit operator remedy evidence for hand-applied findings.
    4: Supplies the behavior-preserving shared title helper.
  detail: docs/implementation-plans/plan-details/bad-fix-provenance/05-bad-fix-provenance-advisory-convergence.md
- id: 6
  title: 'Document annotation provenance and close backlog #231'
  intent: Explains every annotation producer and gives operators the new hand-apply
    recording route.
  files:
  - DATA_CONTRACT.md
  - CLAUDE.md
  - integrations/shared/DIRECTIVES.md
  - BACKLOG.md
  - tests/test_data_contract.py
  complexity: medium
  change_type: non-code
  depends_on:
  - 2
  - 3
  - 5
  depends_on_notes:
    2: Provenance fields must land before DATA_CONTRACT lists every producer's evidence.
    3: Provides the command that the operator guidance must name.
    5: Provides the advisory wording and final provenance rule the contract documents.
  detail: docs/implementation-plans/plan-details/bad-fix-provenance/06-document-annotation-provenance-close.md
---
# Bad Fix Provenance

## Overview

Add durable apply-to-finding provenance so `plan-tool convergence` can issue a recommend-only “likely bad fix / re-check the last edit” advisory when a later finding matches an earlier one and an intervening **applied** remedy note exists. Every apply path, including hand-apply, records an `Annotation`; the diagnostic then joins same-issue identity with that history on its own predicate. The advisory does not change `stop_reason`, exit codes, plan contents, or create a second provenance store.

## Problem statement

A later recurrence alone cannot establish that the last edit caused the issue, so current recurrence and `edit_drift` advice cannot make a bad-fix claim. Claude-session and operator hand-apply edits prose without an annotation, while `DATA_CONTRACT.md` says only the interactive walk populates them. The saved audit history therefore lacks ordered, operator-authored intervening-remedy evidence needed for a reliable recommend-only advisory; `plan_tool/review_persistence.py:Annotation` already owns the persisted status, note, and halt-reason shape that steps 1–2 extend with this provenance.

## Architecture

**Shared writer (step 1).** One helper near `plan_tool/review_persistence.py:update_annotation` persists `annotations[rec_id]` using the existing `Annotation` behavior. Interactive walk and `completeness-apply` (serial + parallel) all call it, but step 1 is behavior-preserving: its statuses, notes, halt reasons, output, and saved shape remain unchanged. It is the one writer seam step 2 extends, so no producer continues to rewrite a sidecar directly.

**Qualified remedy provenance (step 2).** Extend the same `Annotation` record — never a second store — with a valid UTC `recorded_at`, a `note_source` that distinguishes explicit operator remedy text from generated apply status/output or no note, and the identity of the sidecar it updated (report filename/stem plus that report's immutable `created_at`). The writer stamps new records once and preserves those fields through load/save. A qualifying remedy is exactly: `status=applied`, empty `halt_reason`, stripped non-empty `note`, `note_source=operator`, and a valid `recorded_at` strictly earlier than the recurring pass’s `created_at`. New records must always carry the timestamp, source, and source-report identity; legacy annotations missing required provenance fail closed and cannot trigger bad-fix. Interactive walk may mark a note operator-authored only when the operator explicitly entered that remedy text. Serial and parallel `completeness-apply` preserve their disposition but write generated verdict/status text as non-operator evidence, so values such as `APPLIED` and `NOT-APPLICABLE` never qualify.

**Collapsed provenance history (steps 2 and 5).** `build_collapsed_completeness_passes` must retain every source annotation event and its complete payload for each finding across the reports it merges; it must not reduce provenance to the one terminal/winning `annotations[rec_id]` value or the collapse's replacement `created_at`. This is an in-memory view derived from the existing sidecar annotations, not another persisted provenance store. Step 5 evaluates only events from a **prior distinct** collapsed pass, selects the latest qualifying `recorded_at` before the recurring pass, and renders that event's original report identity and report-created time. An annotation merged into the recurring pass itself never supplies cross-pass evidence.

**Hand-apply record command (step 3).** The thin completeness-family **record** CLI joins the existing repo-wide mutation-lock set before it selects a report or writes a sidecar. Contention fails before any selected sidecar changes. With the lock held, it uses the same saved-report selection contract as `completeness-apply`: default to this plan's newest `*-completeness.json`, and let `--id` select a specific saved audit. It then requires a finding selector (rec id and/or anchor) within that selected report: omitting both errors without mutating the sidecar, **ambiguous anchor matches error** unless rec id disambiguates, and id plus a conflicting anchor is rejected. An `applied` record requires a stripped non-empty operator remedy note and writes `note_source=operator`; a deliberate decline records `status=skip` with empty `halt_reason` and does not need remedy evidence.

**Same-issue identity (dedicated helper).** Bad-fix uses a dedicated helper (name at detail time; e.g. `same_issue_identity`) — **not** full `plan_tool/convergence_diagnosis.py:_matches`. Existing `_matches` consumers (`classify_edit_drift`, `classify_impact_recurrence`) keep today’s semantics, including tier-1 step-focus. Routing bad-fix through full `_matches` would treat unrelated same-step findings as one issue. Equal finding `id` is only a candidate-pair optimization: it must still satisfy one of the decisive content tiers below and can never emit an advisory alone. Ordered decisive tiers for the dedicated helper:

| Priority | Signal |
|---|---|
| 1 | Equal `anchor` when **both** sides have a non-empty anchor |
| 2 | Equal normalized issue skeleton (`plan_tool/review.py:_normalize_audit_fingerprint` over recommendation **body**, or body skeleton) when anchors are absent on either side, unequal, or otherwise non-decisive |
| 3 | Shared fuzzy-title helper extracted in step 4 from `_matches` tier 3 only |

One-sided or disagreeing anchors **fall through** to skeleton before title — they do not skip straight to fuzzy title. Finding ids churn with wording and remain only a prefilter, never the sole identity.

**Skeleton needs body on the history model.** Today `RunFinding` (via `_finding_from_recommendation`) carries `id` / `anchor` / `title` only — not `Recommendation.body` — so skeleton matching cannot run on the flattened history convergence already loads. Step 5 must put recommendation `body` (or a persisted skeleton derived at flatten time) on every pass the matcher reads; Architecture and acceptance treat that as load-bearing, not optional.

**Intervening remedy evidence (advisory trigger).** For the bad-fix advisory only, use the complete step-2 qualifying-remedy predicate — applied status, **empty** halt reason, stripped non-empty operator-authored note, and valid earlier timestamp. Deliberate decline, any halt reason (including `drift`), `status=failed`, generated status/output text, whitespace-only notes, legacy annotations missing provenance, and annotations recorded at or after the recurring pass **never** trigger the advisory even when identity matches. Writer still records dispositions; they are not all bad-fix evidence.

**Cross-pass annotation lookup.** Identity match first against an earlier pass’s findings; then load `annotations[matched_prior_rec_id]` from the pass where the remedy was recorded — never the newest finding’s id after id churn. Compare `recorded_at`, not the immutable saved report’s `created_at`, to establish that the remedy intervened; render the stored recording time and source with the note.

**Evaluation window (same stream as sibling advisories).** Bad-fix evaluates `build_collapsed_completeness_passes` only, with the same `audit_stage` trailing-window gate as `classify_impact_recurrence` / `classify_edit_drift`. The inherited default is `WINDOW_SIZE` = **three** same-stage collapsed finals: it stays silent with fewer than three, even when identity and a prior applied non-empty note exist. It does **not** scan `detail-reconcile` / `run-reconcile` series or raw cross-kind `ReportHistory.runs`. The recurring candidate must be a finding in the newest collapsed pass admitted to that window and must still be open there: skip it when that newest pass annotates it `applied` or a deliberate `skip` with empty `halt_reason`. “Intervening” means a qualifying applied note on a **prior, distinct collapsed pass** in that same-stage window (not necessarily only the immediately adjacent pass). When adjacent completeness finals have identical finding-id sets, collapsing can merge an applied note and its re-audit into one pass; with no separate earlier collapsed pass to pair, bad-fix stays silent. When several qualifying source events exist for the same issue in the window, cite the one with the latest qualifying `recorded_at` before the recurring pass and identify its original sidecar report.

**Separate from edit-drift’s prior-apply set.** Bad-fix does **not** inherit `_build_prior_apply_set` (which treats applied / deliberate-skip closes and disappearance-between-passes as prior-apply without a note requirement). Its predicate is only: same-issue identity **and** the step-2 qualifying intervening remedy on the matched prior finding.

**Render (step 5).** Add bad-fix through the sibling advisory wiring end-to-end: a dedicated `classify_*` helper and `ConvergenceDiagnosis` field feed `diagnose_convergence`; `render_diagnosis` renders them through `_bad_fix_lines`; and `_convergence_loop_advisory_lines` explicitly includes those lines for completeness `--iterate` stderr. Recommend-only lines name the recurring finding (anchor or title), excerpt the qualifying operator remedy note, and identify its recording time, source, and original sidecar report — same operator usefulness bar as `_edit_drift_lines` listing matched titles. Surfaces: `plan-tool convergence`, and completeness `--iterate` stderr whenever loaded history already satisfies the predicate (same stance as impact-recurrence / edit-drift). Identity without a qualifying note → no bad-fix advisory (existing recurrence / edit-drift behavior unchanged). Never flip `stop_reason` / exit code. `self-seeded-finding` stays `judgment_only`.

**Checkpoint sidecars.** `load_report_history` excludes pre-apply checkpoint roles; remedy notes written only on checkpoint sidecars are invisible to this diagnostic — remain silent (documented risk, not a second store).

## Input

Saved completeness-report history and sidecar `annotations[rec_id]` (`Annotation`: `status`, `note`, `halt_reason`, `recorded_at`, `note_source`, and source-report identity). Collapse derives an in-memory per-finding event history retaining each source annotation, its immutable report identity, and its outcome. Flattened findings for matching must expose `id`, `anchor`, `title`, and recommendation **`body`** (or a flatten-time skeleton) so the dedicated same-issue helper can run tier 2. The hand-apply record CLI takes a saved completeness report selected by the usual `--id` contract, a required finding selector (rec id and/or anchor), and an explicit remedy note for `applied` while holding the repo mutation lock.

## References

- [Python dataclasses — Data Classes](https://docs.python.org/3/library/dataclasses.html) — Defines frozen dataclasses and asdict serialization used by the existing Annotation persistence shape.
- [Python json — JSON encoder and decoder](https://docs.python.org/3/library/json.html) — Covers the JSON read/write behavior needed to preserve and evolve saved-review sidecars.
- [Python os — Miscellaneous operating system interfaces](https://docs.python.org/3/library/os.html#os.replace) — Documents os.replace and fsync semantics underlying the durable shared annotation writer.
- [Python argparse — Parser for command-line options, arguments and subcommands](https://docs.python.org/3/library/argparse.html) — Covers subcommand and argument validation needed for the completeness-family hand-apply record CLI.
- [Python difflib — Helpers for computing deltas](https://docs.python.org/3/library/difflib.html#difflib.SequenceMatcher) — Documents SequenceMatcher behavior used by the existing fuzzy-title identity fallback.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Hard edit-drift / iterate stop, exit-code flip, and `--fail-on-findings` changes: this signal is recommend-only.
- Plan mutation, auto split / scope-out / re-seed: owned by `#159` / `#160` / `#168` / `#116`.
- Raw full-body Claude issue similarity and prose “sounds like last edit” grading: not an accepted identity matcher.
- Converting `self-seeded-finding` into a gate or adding a second provenance store: `annotations` carries the note.
- Changing `_matches` step-focus semantics for edit-drift / impact-recurrence consumers.
- Stage bars (`#91` / `#248`), reporting polish `#260`, four-loop consistency `#261`, Stage 4 `#241` / `#164`, Stage 5 chat, and detail-prompt fence copy (`#229`): separate work.

## Risks

- An apply path can bypass the shared writer, leaving an otherwise valid remedy without provenance; **high**. Route every known apply and hand-apply path through the writer and test each path’s sidecar output. Remaining gap: an unrecognized future apply entry point.
- Weak same-issue identity, especially the fuzzy-title fallback, can join unrelated findings; **medium**. Use the dedicated ordered tiers (not full `_matches`); keep the signal recommend-only. Matching evidence is not causation.
- An annotation can record a procedural disposition rather than a remedy; **high**. Advisory trigger requires applied status, empty halt reason, a stripped non-empty **operator** note, and a valid earlier recording time. Declines, drift, failed status, generated apply output, and legacy undated/source-less annotations never fire bad-fix. Notes remain operator-authored evidence, not proof the edit caused or fixed the issue.
- A hand-apply record request can select the wrong saved finding or persist unusable remedy evidence; **medium**. Require at least one finding selector, error on ambiguous anchors unless rec id disambiguates, reject id-plus-conflicting-anchor, and require an explicit non-empty note for `applied`. No cross-report identity repair for records that no longer identify a saved finding.
- A note recorded later on an older report can appear to predate a recurrence if the diagnostic reads the report timestamp; **high**. Compare the annotation's valid `recorded_at` to the recurring pass, fail closed for missing/malformed times, and retain provenance through collapse.
- Missing, incomplete, or unreadable saved history can suppress a valid advisory; **low**. Silent without both required evidence; recovering absent provenance is out of scope.
- Reuse-audit history can collapse an applied-note final and an identical-id re-audit into one `CompatiblePass`, leaving no distinct earlier pass to pair with a later candidate; **low**. Stay silent rather than infer a recurrence from annotations merged into the same collapsed pass.
- Collapse can overwrite a qualifying annotation with a later disposition or attribute it to the newest source report; **medium**. Derive and retain all source annotation events with their original report identities, then choose the nearest qualifying event only from a prior distinct collapsed pass.
- Concurrent sidecar writers can lose annotations in a whole-file rewrite; **medium**. Add `completeness-record` to the existing repo-wide mutation-lock policy and test that contention fails before the selected sidecar changes.
- Remedy notes that exist only on pre-apply **checkpoint** sidecars never reach `load_report_history`; **low**. Diagnostic stays silent; do not invent a checkpoint-scanning path in this plan.

## Testing

- Shared writer: interactive walk and serial/parallel apply all preserve their pre-step-1 `Annotation` status/note/halt-reason behavior while using the one writer. Step 2 then stamps every new annotation with a valid UTC recording time, note source, and source-report identity, reads legacy annotations without inventing provenance, and keeps each source event plus its outcome through sidecar load/save and collapse.
- Collapse: a prior collapsed pass containing multiple annotations for one finding preserves both their original report identities and outcomes; bad-fix selects the nearest qualifying event by `recorded_at` and renders that event's original report rather than the collapse's newest report. An event merged into the recurring collapsed pass still cannot qualify.
- Record CLI: defaults to the newest completeness sidecar and `--id` selects an older sidecar without mutating the newer one; neither finding selector errors without mutation; ambiguous/conflicting selectors fail; `applied` rejects empty/whitespace notes and persists an explicit operator note, while deliberate decline remains separate. A held repo mutation lock makes the command fail before reading or writing the sidecar, and a contention fixture proves its bytes are unchanged.
- Same-issue fixtures: tier precedence; equal id alone does not match, while an equal-id candidate plus anchor/skeleton/title does; id churn via anchor or skeleton; one-sided anchor falls through to skeleton; id-churn + annotation lookup via matched prior `rec_id`. Step 4 proves extraction of the title comparator leaves every existing `_matches` result unchanged before step 5 consumes it.
- Synthetic histories: fire only for identity **and** an intervening qualifying remedy on a prior distinct collapsed pass; silent for identity-only, note-only, mismatched identity, a terminal (`applied` or deliberate `skip` with empty `halt_reason`) newest-pass annotation, decline, every non-empty halt reason, failed annotations, generated output such as `APPLIED`, missing/legacy source or timestamp, a timestamp at/after the recurrence, missing history, and edit-drift-style disappearance without a note.
- Window: collapsed completeness + same `audit_stage` only; reconcile sidecars do not join. Fewer than the inherited default three same-stage collapsed finals stay silent. Cover a reuse-collapsed history where the applied note and identical-id re-audit merge into one pass, so no advisory fires without a later distinct collapsed pass.
- Render: advisory lines cite finding, operator-note excerpt, recording time/source, and recording pass; convergence and iterate-stderr hook both covered.
- No retired fork/region imports; no `stop_reason` / exit-code change.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (refactor) — regression tests prove the unified writer preserves existing annotation behavior.
- step 2 (feature) — tests cover new provenance fields, source-report identity, producer-specific note sources, ordering, legacy silence, and full collapse-event preservation.
- step 3 (feature) — tests cover saved-report/finding selection, explicit hand-apply remedy notes, and repo mutation-lock contention before any sidecar mutation.
- step 4 (refactor) — parity tests prove title-match extraction leaves existing `_matches` behavior unchanged.
- step 5 (feature) — tests cover the eligible same-issue/advisory behavior this step adds.
- step 6 (non-code) — verification appropriate to the artifacts rather than unit tests.

## Acceptance criteria

- Step 1 routes every interactive and serial/parallel `completeness-apply` disposition through one writer without changing the existing `Annotation` status, note, or halt-reason behavior.
- Step 2 extends each new `Annotation` with valid UTC `recorded_at`, `note_source`, and immutable source-report identity; it preserves every source annotation event and outcome through load/save and collapse, and treats legacy annotations missing required provenance as non-qualifying.
- Interactive operator text and the applied record command persist `note_source=operator`; serial/parallel generated verdict or output text uses a non-operator source, so generated values such as `APPLIED` never become remedy evidence.
- The record CLI joins the existing repo-wide mutation-lock set before report selection or mutation, so lock contention fails without changing a sidecar. It defaults to the newest saved completeness report and supports the same `--id` override as `completeness-apply`; it requires rec id and/or anchor, errors without mutation when both are absent or the anchor is ambiguous, rejects id-plus-conflicting-anchor, requires a stripped non-empty operator note for `applied`, and records deliberate decline as `status=skip` with empty `halt_reason`.
- Step 4 extracts only `_matches`' existing tier-3 fuzzy-title comparison into a shared helper and locks its behavior with parity tests before step 5 consumes it.
- Same-issue matching uses a dedicated helper: equal `id` is a candidate prefilter only and never matches alone; the first decisive tier is equal `anchor` (both present), normalized issue skeleton over recommendation **body** (or flatten-time skeleton), then the step-4 shared fuzzy-title helper. One-sided anchors fall through to skeleton before title; existing `_matches` consumers keep current semantics.
- History findings used by the matcher carry `body` or a persisted skeleton so tier 2 can run.
- Bad-fix evaluates collapsed completeness passes with the same `audit_stage` window as impact-recurrence / edit-drift: the inherited default requires at least three same-stage collapsed finals, and fewer stay silent. It evaluates only unresolved findings in the newest pass, skips newest-pass `applied` and deliberate-skip annotations, and does not use `_build_prior_apply_set`.
- Cross-pass provenance: identity match, then a source annotation event for `matched_prior_rec_id` on a prior, distinct collapsed pass. It selects the latest qualifying event by `recorded_at` and renders its original sidecar identity/report-created time; an event merged into the same collapsed pass as its re-audit is not a cross-pass match and stays silent.
- Intervening remedy evidence is exactly applied status, empty `halt_reason`, stripped non-empty note, `note_source=operator`, and valid `recorded_at` strictly before the recurring pass; any generated, legacy, malformed, or post-recurrence annotation stays silent.
- When multiple qualifying notes exist, the advisory cites the nearest prior.
- `plan-tool convergence` and completeness `--iterate` stderr (via `_emit_convergence_loop_advisories`) emit the recommend-only bad-fix advisory only when identity and the qualifying intervening remedy are both present; rendered lines name the finding, excerpt the operator note, and identify the recording pass/time/source.
- Bad-fix uses the same `diagnose_convergence` → `ConvergenceDiagnosis` → `render_diagnosis` / `_bad_fix_lines` and explicit `_convergence_loop_advisory_lines` wiring as the sibling loop advisories, so both render paths expose the same eligible findings.
- The bad-fix signal alone does not alter `stop_reason`, an exit code, `--fail-on-findings`, or `self-seeded-finding`'s `judgment_only` status.
- `DATA_CONTRACT.md` lists the expanded annotation fields and producers (including step 1’s routed paths), DIRECTIVES / `CLAUDE.md` names the record command and explicit remedy-note requirement for hand-apply, and backlog `#231` is updated in the final docs/status step.

## Deferred

- A hard exit keyed on this signal: future entry after this ships.
- Re-seed actuation after a named seam: `#159` / `#160` / `#168` after their own re-premise.
- Valid out-of-scope findings: defer to `BACKLOG.md` / `BUG_BACKLOG.md`.
