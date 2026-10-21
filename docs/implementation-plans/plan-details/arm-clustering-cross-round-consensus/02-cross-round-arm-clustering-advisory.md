# Step 2 — Add the cross-round arm-clustering advisory to the convergence diagnosis and its render

## Summary

This step gives step 1's round-over-round consensus evidence a caller and a reader. It adds a `plan_tool.audit_shapes` import to `plan_tool/convergence_diagnosis.py`, a new classifier that feeds step 1's `ArmClusteringConsensusEvidence` into `evaluate_arm_clustering` (building the `material_finding_evidence` and `source_plan_fingerprint` it also requires), a new advisory field on `ConvergenceDiagnosis`, and a render function wired into `render_diagnosis` — mirroring exactly how `impact_recurrence` and `edit_drift` already ride along without changing the verdict. The one design wrinkle the sibling advisories don't have: building a trustworthy `source_plan_fingerprint` means reading the plan file off disk via `AuditInputSnapshot.capture(plan_path, repo_root)`, so the new classifier needs a `repo_root` this module has never taken before (the plan path itself is already available on `ReportHistory.plan_path`). The new keyword parameters this step adds to `diagnose_convergence` all default to no-ops, so every existing caller — `plan_tool/cli/convergence_cmd.py`, `plan_tool/cli/completeness_cmd.py`, and this module's own test suite — keeps compiling and behaving unchanged; wiring real committed-step data into those callers is step 4's job, not this one's. This step also fixes this module's own "cycle-free leaf" docstring paragraph, which already omits `convergence` and `granularity` independent of this plan. On green, `plan-tool convergence` and completeness stderr are both *capable* of showing the cross-round advisory, but nothing fires yet because no caller passes real committed-step data until step 4.

## Table of Contents

- [Summary](#summary) — what this step delivers and where the line is drawn
- [Why](#why) — the gap this step closes
- [Input](#input) — step 1's contract and the leaf contracts this step calls into
- [Files (creates vs edits)](#files-creates-vs-edits) — what changes, file by file
- [Implementation](#implementation) — the new classifier, the fingerprint/evidence assembly, the render wiring, and the docstring fix
- [Tests](#tests) — test roster
- [Acceptance criteria](#acceptance-criteria)
- [References](#references)
- [Applicable guardrails](#applicable-guardrails)
- [Deferred](#deferred)

## Why

Step 1 built a pure function that resolves round-over-round consensus targets, but deliberately stopped short of calling `evaluate_arm_clustering` or touching `ConvergenceDiagnosis` — assembling the advisory and rendering it needs a new `audit_shapes` import, and the plan draws that line at this step on purpose (see step 1's own Implementation, "Where this step's scope ends, and why"). Without this step, step 1's evidence has no consumer: `evaluate_arm_clustering` still only ever fires from `review.py`'s same-execution multi-pass path, so `--audit-passes 1` — the setting this repo's own stopping-rule convention recommends for scope-contract-bound audits — still shows nothing, even after step 1 lands. This step closes that gap by giving the evidence a caller (`evaluate_arm_clustering`, fed with a real fingerprint and finding evidence, not the signature's void-inducing defaults) and a reader (a line in `render_diagnosis`, gated on the render staying silent when nothing fires, per the plan's Architecture point 8).

## Input

- **Step 1's classifier and its result type** (`plan_tool/convergence_diagnosis.py`, landed by step 1) — `classify_arm_clustering_consensus(history, *, declared_step_ids, step_statuses, window=CROSS_ROUND_CONSENSUS_WINDOW, classify_domain=None) -> Optional[ArmClusteringConsensusEvidence]`, where `ArmClusteringConsensusEvidence` carries `window_audit_stage: str`, `rounds_used: int`, `consensus_targets: dict[str, int]`, and `material_finding_ids: tuple[str, ...]`. `consensus_targets` is keyed by the **newest window pass's** finding ids — every id in `material_finding_ids` is guaranteed to be a finding on that same newest pass. This step calls that function; it does not re-derive its matching, materiality, or currency rules.
- **`RunFinding.audit_step_target`** (step 1) — not read directly by this step's own code (step 1's classifier already consumes it), but the newest pass's `RunFinding.anchor` / `RunFinding.source` per resolved id *is* what this step reads to build `material_finding_evidence`.
- **`evaluate_arm_clustering`'s full parameter contract** (`plan_tool/audit_shapes.py`) — `declared_step_ids: Sequence[int]`, `material_finding_ids: Sequence[str]`, `consensus_targets: Mapping[str, int]`, `source_plan_fingerprint: str = ""`, `material_finding_evidence: Sequence[AuditShapeFindingEvidence] = ()`. Both defaulted parameters are traps this plan's Risks section names, but on this specific code path **nothing runtime catches either one** — checking twice is what makes this worth stating precisely rather than by analogy:
  - `evaluate_arm_clustering` itself only checks `isinstance(source_plan_fingerprint, str)` (`audit_shapes.py:216`) — an empty string passes that check and produces a normal-looking, non-`None` advisory.
  - `is_well_formed_audit_shape_advisory` would reject an empty fingerprint, but this step never calls it (Implementation §2.8 — that validator exists for a *saved, reloaded* sidecar advisory; this one is computed fresh and rendered immediately, never round-tripped).
  - `plan_tool/completeness_report.py`'s anchor-skip rendering, which does react to empty `material_finding_evidence`, belongs to the *same-execution* saved-sidecar advisory's own renderer — a different, unused pipeline. This step's own render (`_arm_clustering_lines`, Implementation §4) never reads `material_finding_evidence`, any per-finding anchor, or `source_plan_fingerprint` at all.

  Concretely: shipping a caller bug that leaves either parameter at its default produces an `AuditShapeAdvisory` that *looks* fine and renders identically — the field is simply wrong, silently, forever, with no test failure unless one is written for exactly this. The **only** protection is `test_arm_clustering_never_uses_the_signature_defaults` (Tests) — supply both arguments for real, every time evidence is present, because nothing else on this path will ever catch getting it wrong.
- **`AuditInputSnapshot.capture(plan_path, repo_root) -> AuditInputSnapshot`** (`plan_tool/review_persistence.py`) — reads the plan file bytes off disk, parses it, and resolves each step's detail artifact, returning `.fingerprint` as the "dedicated exact audit-input fingerprint" `DATA_CONTRACT.md` requires for this exact field. `review_persistence` is already one of this module's three top-level imports (`SavedReview`, `list_saved_reviews`, `load_review`, `Annotation`, `ReviewLoadError` already come from it), so adding `AuditInputSnapshot` to that same import statement is not a new edge. This call touches the filesystem and can raise (missing/unreadable plan file) — every other function in this module is pure over already-loaded `ReportHistory` data, so this is the one place that changes.
- **`ReportHistory.plan_path: str`** — already carries "the plan path the history was loaded for" (its own docstring). This step reuses it as `AuditInputSnapshot.capture`'s `plan_path` argument rather than adding a redundant new parameter for it; only `repo_root` is genuinely new information this module has never needed before.

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**

- `plan_tool/convergence_diagnosis.py`:
  - Add a new top-level import: `from plan_tool.audit_shapes import AuditShapeAdvisory, AuditShapeFindingEvidence, evaluate_arm_clustering`.
  - Add a new top-level import: `from plan_tool.jira_grade import GRADE_RUN` (for `classify_arm_clustering`'s `detail_grade` parameter default — `jira_grade.py` is a pure stdlib-only leaf, no cycle risk).
  - Add `AuditInputSnapshot` to the existing `from plan_tool.review_persistence import (...)` statement.
  - Add a new advisory dataclass wrapping an `AuditShapeAdvisory` with the two cross-round-specific fields the render needs (round count, audit stage) — see Implementation.
  - Add a new classifier function that calls step 1's classifier, assembles `material_finding_evidence` and `source_plan_fingerprint`, and calls `evaluate_arm_clustering`.
  - Add `declared_step_ids`, `step_statuses`, and `repo_root` keyword-only parameters to `diagnose_convergence`, all defaulting to no-ops; wire the new classifier's result into both `ConvergenceDiagnosis` constructions (the no-history branch and the main branch) alongside `impact_recurrence` / `edit_drift`.
  - Add a new field to `ConvergenceDiagnosis` for the advisory.
  - Add a new render-lines function and wire it into `render_diagnosis`'s "loop-pattern advisories" block, beside `_impact_recurrence_lines` / `_edit_drift_lines`.
  - Update `ConvergenceDiagnosis`'s, `render_diagnosis`'s, **and `diagnose_convergence`'s** docstrings — all three currently enumerate the newest-run signals by count (`diagnose_convergence`'s own: "Also records six newest-run signals…", naming exactly six) and go stale the moment this step lands a seventh. `diagnose_convergence` is the exact function this step edits to wire in the new classifier, so missing its own docstring here would be the most directly-implicated omission, not an edge case.
  - Fix the module's own "cycle-free leaf" docstring paragraph (currently: "it imports ``review_persistence``, ``review``, and ``locator``") to name the module's true import set: `review_persistence`, `review`, `locator`, `convergence`, `granularity`, plus the two new `audit_shapes` and `jira_grade` edges this step adds (the latter for `GRADE_RUN` in the classifier's `detail_grade` parameter, § "The classifier"). `convergence` and `granularity` are already-landed imports this paragraph has always omitted, independent of this plan — fix all of it in one edit, not just append the new edges onto the stale baseline.
- `tests/test_convergence_diagnosis.py`:
  - New test class for the new classifier.
  - New plan-file-writing test helper (this is the first classifier in this module that needs a real on-disk plan for `AuditInputSnapshot.capture` to succeed against — mirror `tests/test_completeness_report.py`'s `_write_minimal_plan` / `_fresh_advisory_display` pattern rather than inventing a new shape).
  - Extend the `_diag` and `_adv_diag` fixture-construction helpers with the new field.
  - New `diagnose_convergence` / `render_diagnosis` wiring tests, following the existing `test_diagnose_populates_impact_recurrence_when_classifier_fires` / `test_render_impact_recurrence_advisory_names_seam_and_is_recommend_only` / `test_render_both_advisories_together` / `test_render_advisory_mutation_deleting_helpers_goes_red` pattern (the last one extended, not duplicated).

## Implementation

### 1. The advisory dataclass

`AuditShapeAdvisory` (from `audit_shapes.py`) already carries everything the render needs about the arm and finding counts (`arm_step_ids`, `material_finding_count`, `arm_finding_count`, `committed_step_count`), but it carries nothing about *how many rounds* produced it — that's the piece the plan's Architecture point 8 and Acceptance criteria require the render to name, so a reader can tell this advisory apart from the pre-existing same-execution one when both fire in the same output. One reasonable shape (naming is a recommendation, matching how `ImpactRecurrenceAdvisory` / `EditDriftAdvisory` are each named `<Concept>Advisory`):

```python
@dataclass(frozen=True)
class ArmClusteringAdvisory:
    """Recommend-only signal when cross-round consensus resolves an arm-clustering shape."""
    window_audit_stage: str
    rounds_used: int
    shape: AuditShapeAdvisory
```

Wrapping rather than flattening keeps `AuditShapeAdvisory` the single source of truth for the arm/finding data (matching how `plan_tool/completeness_report.py`'s `AuditShapeAdvisoryDisplay` also wraps rather than re-declares those fields), while `window_audit_stage` / `rounds_used` carry exactly the two facts step 1's `ArmClusteringConsensusEvidence` has that `AuditShapeAdvisory` doesn't.

### 2. The classifier

One reasonable shape, mirroring `classify_impact_recurrence(history, *, window=WINDOW_SIZE)` / `classify_edit_drift(history, *, window=WINDOW_SIZE, classify_domain=None)`'s `(history, *, ...) -> Optional[XAdvisory]` signature, extended with what this one needs that the siblings don't (real committed-step data, a repo root):

```python
def classify_arm_clustering(
    history: ReportHistory,
    *,
    declared_step_ids: Sequence[int] = (),
    step_statuses: Optional[Mapping[int, StepStatus]] = None,
    repo_root: Optional[Path] = None,
    detail_grade: str = GRADE_RUN,
    window: int = CROSS_ROUND_CONSENSUS_WINDOW,
    classify_domain: Optional[Callable[[RunFinding], str]] = None,
) -> Optional[ArmClusteringAdvisory]:
    ...
```

`detail_grade` (`GRADE_RUN` / `GRADE_JIRA` from `plan_tool/jira_grade.py`) must reach `AuditInputSnapshot.capture` as its own `detail_grade` keyword (§ 2 point 6 below) — defaulting to `GRADE_RUN` matches `AuditInputSnapshot.capture`'s own default, but a caller auditing a jira-graded plan must pass `GRADE_JIRA` explicitly (step 4 threads `cmd_convergence`'s real `args.grade` here; this step's own tests exercise both grades directly). Leaving this unthreaded would silently fingerprint a jira-graded plan's run-grade bundle instead of the jira-grade one its saved history was actually audited against — the exact "dedicated exact audit-input fingerprint" guarantee this step's Input section cites `AuditInputSnapshot.capture` for in the first place.

What it must do, in order:

1. **Cheap short-circuit.** `repo_root is None` means a fingerprint can never be captured, so nothing downstream can produce a well-formed advisory regardless of what step 1's evidence says — return `None` immediately, before calling into step 1's classifier. `declared_step_ids` needs no equivalent early guard: an empty sequence already makes step 1's currency check drop every candidate, so its own classifier already returns `None` cleanly.
2. **Call step 1's classifier**: `evidence = classify_arm_clustering_consensus(history, declared_step_ids=declared_step_ids, step_statuses=step_statuses or {}, window=window, classify_domain=classify_domain)`. `None` in, `None` out.
3. **Do not pass `diagnose_convergence`'s own `window` parameter here.** That parameter is sized for the trailing-run *verdict* certification (`WINDOW_SIZE=3`, an unrelated claim); arm-clustering's window is `CROSS_ROUND_CONSENSUS_WINDOW=2` (step 1), and this function's own `window` keyword already defaults to it — leave `diagnose_convergence` to call this function without overriding it (see § 4).
4. **Look up the newest window pass's findings.** `build_collapsed_completeness_passes(history)`'s last element is the newest pass step 1's windowing (`_impact_recurrence_trailing_window`) always keys `window_audit_stage` from — the same fact `classify_impact_recurrence` / `classify_edit_drift` already rely on. Build an id→`RunFinding` lookup from that pass's `findings`; every id in `evidence.material_finding_ids` is guaranteed present there (Input), so no defensive fallback for a missing id is needed.
5. **Assemble `material_finding_evidence`**: one `AuditShapeFindingEvidence(finding_id=id, anchor=finding.anchor, source=finding.source)` per id in `evidence.material_finding_ids`, in that same order — leaving this empty is the documented trap that silently empties the render (Input).
6. **Capture the fingerprint**, threading `detail_grade` through so the captured bundle matches the grade the saved history was actually audited at (never silently defaulting to run grade for a jira-graded plan), wrapped so a filesystem failure degrades to "no advisory," never an exception surfacing out of `diagnose_convergence` (this module's established "total by design" ethos — see `load_report_history`'s own docstring, and `cmd_convergence`'s existing best-effort `try/except` around plan parsing):
   ```python
   try:
       fingerprint = AuditInputSnapshot.capture(
           Path(history.plan_path), repo_root, detail_grade=detail_grade
       ).fingerprint
   except Exception:
       return None
   ```
7. **Call `evaluate_arm_clustering`** with `declared_step_ids`, `evidence.material_finding_ids`, `evidence.consensus_targets`, the captured `fingerprint` as `source_plan_fingerprint`, and the assembled `material_finding_evidence`. Its own gap-free proper-majority-arm math is untouched (Out of scope) — this step supplies real, non-default arguments to it and nothing more.
8. **Do not call `is_well_formed_audit_shape_advisory`.** That validator exists to fail closed on a *saved, user-editable sidecar's* advisory (its own docstring says so explicitly); this advisory is computed fresh and rendered immediately every `plan-tool convergence` run, never persisted or reloaded, so that check doesn't apply here — matching how `classify_impact_recurrence` / `classify_edit_drift` never call it either.
9. **Wrap and return.** `None` from `evaluate_arm_clustering` → `None` overall; otherwise `ArmClusteringAdvisory(window_audit_stage=evidence.window_audit_stage, rounds_used=evidence.rounds_used, shape=<the AuditShapeAdvisory>)`.

### 3. Wiring into `diagnose_convergence`

Add the four new keyword-only parameters (`declared_step_ids: Sequence[int] = ()`, `step_statuses: Optional[Mapping[int, StepStatus]] = None`, `repo_root: Optional[Path] = None`, `detail_grade: str = GRADE_RUN`) alongside the existing `window` / `audit_stage` / `classify_domain`. Compute the advisory in the same place `impact_recurrence` and `edit_drift` are already computed — before the `if not series_runs` no-history branch — and include it in **both** `ConvergenceDiagnosis` constructions in that function, not only the main-path one; the no-history branch already includes `impact_recurrence` / `edit_drift` for the same reason (a caller reading the field shouldn't need to know which branch fired). In practice `classify_arm_clustering` will itself return `None` on an empty `history.runs` (step 1's classifier has nothing to match), so this is about field completeness and consistency with the sibling advisories, not a case that needs to actually fire on no-history.

Because every new parameter defaults to a no-op (`()`, `None`, `None`, `GRADE_RUN`), every existing call site — `plan_tool/cli/convergence_cmd.py:cmd_convergence`, `plan_tool/cli/completeness_cmd.py:_convergence_loop_advisory_lines`, and this module's own test suite, none of which pass the new keywords — keeps compiling and behaving exactly as before. The advisory stays permanently `None` in production until step 4 threads real committed-step data through those two CLI call sites; that is the intended, staged state after this step lands alone.

### 4. Render

New render-lines function, mirroring `_impact_recurrence_lines` / `_edit_drift_lines`'s `(advisory) -> list[str]` shape and closing boilerplate ("recommend-only … run-readiness gate"):

```python
def _arm_clustering_lines(advisory: ArmClusteringAdvisory) -> list[str]:
    ...
```

Requirements on its output, not its exact wording:

- **Name the arm's step ids** from `advisory.shape.arm_step_ids`. This module has no parsed `Plan` on hand (unlike `plan_tool/completeness_report.py`'s version, which prints step titles) — name ids only, matching how `_impact_recurrence_seam_label` already omits step titles for the same reason.
- **Name the evidence counts** — `advisory.shape.arm_finding_count` of `advisory.shape.material_finding_count`, across `advisory.shape.committed_step_count` committed steps.
- **Name the round count and stage explicitly** — something naming `advisory.rounds_used` and `advisory.window_audit_stage` (e.g. "across N saved `<stage>` rounds"). This is the acceptance-criteria requirement that keeps this advisory textually distinguishable from the pre-existing same-execution one, which can fire independently in the same completeness-audit output and carries no such phrase.
- **End with the same recommend-only boilerplate** the sibling advisories use, so `render_diagnosis`'s existing tests-by-substring convention (`"recommend-only"`, `"run-readiness gate"`) generalizes to this one too.

Wire it into `render_diagnosis`'s existing "Loop-pattern advisories" block, beside the `impact_recurrence` / `edit_drift` calls:

```python
if diagnosis.arm_clustering is not None:
    lines.extend(_arm_clustering_lines(diagnosis.arm_clustering))
```

Silence on `None` is the whole contract for the non-firing case (Architecture point 8) — no separate "insufficient evidence" line, matching `impact_recurrence` / `edit_drift`'s existing behavior exactly.

### 5. Docstring accuracy

Three docstrings in this file currently enumerate the newest-run signals by count and go stale the moment this step lands: `ConvergenceDiagnosis`'s own docstring ("`latest_blocking` / `code_drift` / `finding_churn` / `structural_recurrence` / `impact_recurrence` / `edit_drift` are newest-run signals…"), `render_diagnosis`'s ("…edit-drift self-seeding appends an edit-drift advisory […]; none of the five alters the headline"), and `diagnose_convergence`'s own ("Also records six newest-run signals the verdict alone cannot carry — `latest_blocking` […], `code_drift` […], …"). Update all three to include the new seventh signal (`arm_clustering`) in the same edit — this is the same kind of drift the module's "cycle-free leaf" paragraph already has, and all three sit in the same file this step is already touching.

## Tests

### Tests for this step

`tests/test_convergence_diagnosis.py`:

- New helper mirroring `tests/test_completeness_report.py`'s `_write_minimal_plan` / `_fresh_advisory_display` — writes a real plan markdown file at `_plan_abs(tmp_path)` (a handful of committed steps is enough) so `AuditInputSnapshot.capture` has real bytes to read. Existing helpers (`_impact_history`, `_edit_drift_history`) never write a plan file because their classifiers never need one; this is genuinely new fixture infrastructure this step adds.
- `test_arm_clustering_skips_when_repo_root_is_none` — `classify_arm_clustering(history, declared_step_ids=..., repo_root=None)` returns `None` without attempting a fingerprint capture, even when step 1's evidence would otherwise resolve.
- `test_arm_clustering_returns_none_when_consensus_evidence_is_none` — step 1's classifier returning `None` (e.g. via a monkeypatch or an unmatched history) short-circuits before any fingerprint capture or `evaluate_arm_clustering` call.
- `test_arm_clustering_fires_with_real_evidence_and_fingerprint` — using the new plan-file helper plus a constructed multi-round saved history that step 1's classifier resolves to ≥3 material findings on a majority arm, asserts a non-`None` `ArmClusteringAdvisory` whose `.shape` is a well-formed `AuditShapeAdvisory` (`shape_id == "arm-clustering"`, `source_plan_fingerprint` non-empty and equal to a directly-computed `AuditInputSnapshot.capture(...).fingerprint`, `material_finding_evidence` non-empty with real `anchor`/`source` values, not the `AuditShapeFindingEvidence(finding_id, None, "")` defaults `evaluate_arm_clustering` fabricates for a missing id).
- `test_arm_clustering_never_uses_the_signature_defaults` — asserts the call into `evaluate_arm_clustering` is never made with an empty `material_finding_evidence` tuple or an empty `source_plan_fingerprint` when evidence is present (spy or inspect the resulting advisory's `material_finding_evidence`/`source_plan_fingerprint` directly).
- `test_arm_clustering_capture_failure_returns_none` — `AuditInputSnapshot.capture` raising (point `repo_root` at a path with no plan file, or monkeypatch the classmethod to raise) is swallowed, not propagated.
- `test_arm_clustering_does_not_call_well_formed_validator` — spy on / monkeypatch `is_well_formed_audit_shape_advisory` and assert it is never called by `classify_arm_clustering`.

`test_diagnose_populates_arm_clustering_when_classifier_fires` (new, alongside the existing `test_diagnose_populates_impact_recurrence_when_classifier_fires` / `test_diagnose_populates_edit_drift_when_classifier_fires`) — `diagnose_convergence(history, declared_step_ids=..., step_statuses=..., repo_root=tmp_path)` populates `.arm_clustering` when the classifier fires.

`test_diagnose_default_arm_clustering_params_are_no_ops` (new) — `diagnose_convergence(history)` called with no new keywords (matching every existing call site and every other test in this file) always yields `arm_clustering is None` and never raises, even against a history that would otherwise resolve a consensus arm.

`test_render_arm_clustering_advisory_names_rounds_and_is_recommend_only` (new, mirrors `test_render_impact_recurrence_advisory_names_seam_and_is_recommend_only`) — asserts the step ids, the round count, "recommend-only", and "run-readiness gate" all appear in `render_diagnosis`'s output.

`test_render_all_three_loop_pattern_advisories_together` (extends `test_render_both_advisories_together`) — all three of `impact_recurrence` / `edit_drift` / `arm_clustering` render together without one suppressing another.

`test_render_advisory_mutation_deleting_helpers_goes_red` (extend, not duplicate) — add a third `monkeypatch.setattr(mod, "_arm_clustering_lines", lambda *a, **k: [])` assertion beside the existing two.

`test_end_to_end_arm_clustering_through_load_and_render` (new, mirrors `test_end_to_end_impact_recurrence_through_load_and_render`) — saves real reports via `_save`, writes the real plan file, loads history via `load_report_history`, and asserts the rendered output of `diagnose_convergence(..., declared_step_ids=..., step_statuses=..., repo_root=tmp_path)` names the arm.

Extend `_diag` and `_adv_diag` with an `arm_clustering: ArmClusteringAdvisory | None = None` keyword, threaded into their `ConvergenceDiagnosis(...)` construction, matching how `impact_recurrence` / `edit_drift` are already there.

Every test above must be green before this step is considered finished.

## Acceptance criteria

- `ConvergenceDiagnosis` gains a new field carrying the cross-round arm-clustering advisory, defaulting to `None`, populated in both branches of `diagnose_convergence`.
- `diagnose_convergence` accepts `declared_step_ids`, `step_statuses`, `repo_root`, and `detail_grade` as new keyword-only parameters, each defaulting to a no-op; every existing call site (`plan_tool/cli/convergence_cmd.py`, `plan_tool/cli/completeness_cmd.py`, and this module's existing tests) compiles and behaves unchanged without passing them.
- The new classifier calls step 1's `classify_arm_clustering_consensus` unchanged, never re-derives matching/materiality/currency logic, and never calls `is_well_formed_audit_shape_advisory`.
- The call into `evaluate_arm_clustering` always supplies a non-empty `material_finding_evidence` (real `anchor`/`source` per resolved id) and a non-empty `source_plan_fingerprint` from `AuditInputSnapshot.capture(...).fingerprint` — never either signature default — whenever step 1's evidence is present and `repo_root` is not `None`.
- A filesystem failure capturing the fingerprint degrades to "no advisory," never an exception out of `diagnose_convergence` or `classify_arm_clustering`.
- `render_diagnosis` prints a line for the cross-round advisory only when it is present, and that line names the round count and audit stage explicitly (e.g. "across N saved `<stage>` rounds"), distinguishing it from the pre-existing same-execution advisory's own wording.
- `evaluate_arm_clustering`'s own signature and math, `classify_impact_recurrence` / `classify_edit_drift`'s bodies, and `plan_tool/review.py`'s same-execution consensus path are all unmodified.
- No new blocking gate, exit-code flip, or apply-dispatch reads the cross-round advisory any differently than the same-execution one does today — it feeds only `render_diagnosis`'s printed output.
- The module's own "cycle-free leaf" docstring paragraph names `review_persistence`, `review`, `locator`, `convergence`, `granularity`, `audit_shapes`, and `jira_grade` — not just the new edges appended onto the previously-incomplete list.
- `plan_tool/cli/convergence_cmd.py` and `plan_tool/cli/completeness_cmd.py` are untouched by this step's diff.

## References

- [difflib — Helpers for computing deltas (Python 3 Standard Library)https: — background for `_matches`' tier-3 fuzzy-title leg, which step 1's classifier (consumed unchanged here) relies on.
- [collections.abc — Abstract Base Classes for Containershttps: — the `Mapping` contract `step_statuses` and `consensus_targets` both satisfy.
- [dataclasses — Data Classeshttps: — field defaults for the new `ArmClusteringAdvisory` type and the new keyword-only parameters this step adds to `diagnose_convergence`.

## Applicable guardrails

The plan's `## Out of scope` section binds this step on several points:

- No change to `evaluate_arm_clustering`'s signature or arm math in `plan_tool/audit_shapes.py` — this step only supplies real arguments to it.
- No change to the existing same-execution (`--audit-passes N > 1`) consensus path in `plan_tool/review.py` — this step's declared files don't include `review.py` at all.
- No new blocking gate, exit-code flip, or apply-dispatch keyed on the advisory — it feeds `render_diagnosis`'s printed output only, exactly as `impact_recurrence` / `edit_drift` do.
- No reviving the retired region-trending diagnostic's vocabulary — the new names this step adds must not resemble `spinning` / `FORK_*` / `recurring_regions`.
- `classify_impact_recurrence` / `classify_edit_drift`'s own logic, and the shared helpers they and step 1's classifier expose (`build_collapsed_completeness_passes`, `_matches`, `_impact_recurrence_trailing_window`), are consumed read-only — this step calls them, never edits their bodies.
- No gating cross-round consensus on evidence that a fix was attempted between rounds — this step doesn't touch that logic at all; it lives entirely in step 1's classifier.
- Rendering stays silent when a previously-firing arm's consensus becomes unresolvable (Architecture point 8) — no explicit "insufficient evidence" line.
- Cross-round materiality (`is_blocking_finding`, decided inside step 1's classifier) is not made to agree with same-execution materiality (`is_blocking_impact` / calibration lookup) — this step doesn't touch either.

## Deferred

- Threading real `declared_step_ids` and real per-step status from a parsed plan into `plan_tool/cli/convergence_cmd.py` and `plan_tool/cli/completeness_cmd.py` — step 4. Until then, the new parameters this step adds stay at their no-op defaults in production.
- Hoisting the plan parse once inside `cmd_convergence` — step 3.
- Updating CLAUDE.md, `docs/ARCHITECTURE.md`, `docs/how-to/pipeline/audit.md`, and closing out `BACKLOG.md` #264 — step 5.
- The residual `_matches` tier-1 misattribution risk the plan's Risks section describes — an accepted property of reusing `_matches` unchanged, closed by no step in this plan.
- Any change to `evaluate_arm_clustering`'s own math, or to the same-execution consensus path in `plan_tool/review.py` — both plan-level Out of scope, not this step's to touch.
