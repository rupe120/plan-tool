"""Characterization tests for the completeness-audit reporting helpers.

These pin the three small, pure helpers ``cmd_completeness`` leans on so the
upcoming "split cli.py into an intent-grouped package" refactor can relocate
them without changing the strings an operator sees or the gate a headless
caller reads:

  | helper                              | what it produces                     |
  |-------------------------------------|--------------------------------------|
  | ``_fmt_finding_counts``             | the ``2 critical, 1 high`` breakdown |
  | ``_finding_progress_label``         | the per-finding progress line label  |
  | ``_completeness_has_blocking_findings`` | the ``--json`` blocking gate     |

``COVERAGE_BASELINE.md`` marks all three ``indirectly covered`` — exercised
only as transitive callees when a test drives ``main(["completeness-audit",
…])`` — so per the cli-package-split plan's no-duplication rule they get
their first *direct* unit tests here. Each is pure (no I/O, no claude call):
they are imported from ``plan_tool.cli`` and called with hand-built
recommendation / issue objects, so nothing here patches a ``plan_tool.cli``
module global (see ``test_package_surface.py`` for the split-proof rationale).

The end-to-end completeness contract is already pinned in ``tests/test_cli.py``
and the inventory pointer stands in for it rather than a duplicate here:

  - the deterministic authoring-gap checks surfacing in the report, and the
    ``has_blocking_findings`` flag reflecting medium+ findings in ``--json``,
    are driven through ``main()`` with the conceptual audit stubbed at the
    launcher boundary (``plan_tool.review.shell_review_invoker``) — see
    ``tests/test_cli.py`` (``data["has_blocking_findings"]`` assertions and
    the deterministic-findings-surface wiring tests).

The five per-phase classes below (``TestRunDeterministicChecks`` …
``TestPersistAndPresentReport``) cover the named phase helpers step 21
carved out of ``cmd_completeness``. Those helpers are module-private and
deliberately NOT re-exported onto the ``plan_tool.cli`` package surface
(see ``test_package_surface.py``), so — by *deliberate, documented
exception* to this package's "import only via ``plan_tool.cli``"
convention — these tests reach into their owning implementation module
``plan_tool.cli.completeness_phases`` directly. The exception is sound
because these are internal-seam unit tests, not surface-contract tests;
do not "fix" the import back to the package, and do not promote the
helpers to the surface to enable it. The conceptual-audit test still
patches the *domain* seam (``plan_tool.review.audit_plan_until_stable``),
never a ``plan_tool.cli`` global, so no real claude call fires.
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import importlib
import inspect
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import argparse

import pytest

from plan_tool.cli import (
    _completeness_has_blocking_findings,
    _finding_progress_label,
    _fmt_finding_counts,
)
from plan_tool.cli.completeness_cmd import (
    _print_stale_detail_preflight,
    _resolve_audit_reuse,
    compute_conceptual_bar_blocking_ids,
    finalize_completeness_run,
    register,
)
from plan_tool.cli.completeness_phases import (
    _resolution_for_verdict,
    _run_iterate_convergence_loop,
)
from plan_tool.review import (
    CARRIED_RESOLUTION_APPLIED,
    CARRIED_RESOLUTION_BLOCKED,
    CARRIED_RESOLUTION_OPEN,
    CARRIED_RESOLUTION_SKIPPED,
)
from plan_tool.completeness_report import (
    AuditShapeAdvisoryDisplay,
    ReusableAudit,
    UNTRUSTED_PERSISTENT,
    UNTRUSTED_TRANSIENT,
    blocking_verdict_from_gate,
)
from plan_tool.convergence import IterativeBudget, STAGE_BARE, STAGE_DETAIL
from plan_tool.locator import slug_from_filename
from plan_tool.review_persistence import Annotation, load_review, plan_reports_dir, save_review
# Per-phase helpers extracted from ``cmd_completeness`` in step 21. They are
# module-private and not re-exported onto ``plan_tool.cli``, so they are
# imported here directly from their owning implementation module — a
# deliberate exception to the package-import convention documented in the
# module docstring above.
from plan_tool.cli.completeness_phases import (
    _DeterministicReport,
    _IterateOutcome,
    _apply_files_coherence,
    _collect_data_contract_drift,
    _persist_and_present_report,
    _render_completeness_json,
    _render_grouped_report as _render_grouped_report_with_verdict,
    _run_deterministic_checks,
    _sample_conceptual_audit,
    all_deterministic_detectors,
    deterministic_detector_registry,
    write_pre_apply_audit_checkpoint,
    derive_audit_stage,
)
from plan_tool.create import PLAN_BODY_SECTIONS
from plan_tool.parser import ValidationError as ParserValidationError, parse_plan
from plan_tool.review import DetailBodyIssue, DetailBundleStatus, DetailCoverageIssue, Recommendation


@pytest.fixture(autouse=True)
def _save_current_completeness_fixtures(monkeypatch: pytest.MonkeyPatch):
    """Make direct completeness fixtures model a completed sampled audit."""
    import plan_tool.review_persistence as persistence
    from plan_tool.fingerprint import audit_input_detail_fingerprint
    from plan_tool.review_persistence import AuditInputSnapshot

    original = persistence.save_review

    def save_current(**kwargs):
        if (
            kwargs.get("kind") == "completeness"
            and kwargs.get("qualified_result") is None
        ):
            root = kwargs["repo_root"]
            plan_path = Path(kwargs["plan_path"])
            if not plan_path.is_absolute():
                plan_path = root / plan_path
            if plan_path.is_file():
                snapshot = AuditInputSnapshot.capture(plan_path, root)
                kwargs["qualified_result"] = {
                    "headline": "awaiting-human-action",
                    "stage": "detail",
                    "coverage": "confirmed",
                    "revision_status": "current",
                    "audit_revision": snapshot.revision,
                }
                kwargs["plan_fingerprint"] = snapshot.revision["plan_digest"]
                kwargs["detail_bundle_fingerprint"] = (
                    audit_input_detail_fingerprint(snapshot)
                )
        return original(**kwargs)

    monkeypatch.setattr(persistence, "save_review", save_current)
    monkeypatch.setitem(globals(), "save_review", save_current)


def _rec(
    severity: str,
    *,
    source: str = "plan-completeness",
    title: str = "t",
    impact: str | None = None,
    complexity: str | None = None,
) -> Recommendation:
    """A minimal :class:`Recommendation` carrying just the fields the
    helpers under test read (``severity`` / ``source`` / ``title``)."""
    return Recommendation(
        id=f"{source}-{severity}",
        source=source,
        severity=severity,
        step_id=None,
        title=title,
        body="body",
        impact=impact,
        complexity=complexity,
    )


def _corr_rec(rec_id: str, *, severity: str = "high", anchor: str = "step1-over-pack") -> Recommendation:
    """A structural finding on one step (via anchor)."""
    return Recommendation(
        id=rec_id,
        source="granularity-split",
        severity=severity,
        step_id=None,
        title="Step 1 packs too much",
        body="…",
        anchor=anchor,
    )


class TestPrintStaleDetailPreflight:
    """The completeness-audit deterministic pre-flight (BACKLOG #165) —
    warns on stderr before any Claude call when a step's detail file was
    authored against an earlier plan version. No sidecar, no baseline, or
    a matching fingerprint all print nothing."""

    def _plan_and_seed(
        self, tmp_path: Path, *, out_of_scope: str
    ) -> tuple[Path, "Plan"]:
        from plan_tool.parser import parse_plan

        plan_path = tmp_path / "1-demo.md"
        plan_path.write_text(
            "---\ntitle: Demo\nstatus: planning\npriority: low\n"
            "steps:\n  - id: 1\n    title: Only step\n"
            "    detail: plan-details/demo/01-step.md\n"
            f"---\n# Body\n\n## Out of scope\n\n{out_of_scope}\n",
            encoding="utf-8",
        )
        return plan_path, parse_plan(plan_path)

    def test_prints_nothing_without_a_sidecar(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        plan_path, plan = self._plan_and_seed(tmp_path, out_of_scope="x")
        _print_stale_detail_preflight(plan, plan_path)
        assert capsys.readouterr().err == ""

    def test_prints_nothing_when_fingerprint_matches(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from plan_tool.grounding import (
            compute_step_authoring_fingerprint,
            write_grounding,
        )

        plan_path, plan = self._plan_and_seed(tmp_path, out_of_scope="Skip auth.")
        fp = compute_step_authoring_fingerprint(
            plan.steps[0], out_of_scope="Skip auth.", deferred=""
        )
        write_grounding(
            plan_path,
            plan_fingerprint="",
            code_fingerprint={},
            step_authoring_fingerprints={"1": fp},
        )
        _print_stale_detail_preflight(plan, plan_path)
        assert capsys.readouterr().err == ""

    def test_warns_on_stderr_when_a_step_is_stale(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from plan_tool.grounding import (
            compute_step_authoring_fingerprint,
            write_grounding,
        )
        from plan_tool.parser import parse_plan

        plan_path, plan = self._plan_and_seed(tmp_path, out_of_scope="Skip auth.")
        fp = compute_step_authoring_fingerprint(
            plan.steps[0], out_of_scope="Skip auth.", deferred=""
        )
        write_grounding(
            plan_path,
            plan_fingerprint="",
            code_fingerprint={},
            step_authoring_fingerprints={"1": fp},
        )
        plan_path.write_text(
            plan_path.read_text(encoding="utf-8").replace(
                "Skip auth.", "Skip auth and retries."
            ),
            encoding="utf-8",
        )
        narrowed_plan = parse_plan(plan_path)

        _print_stale_detail_preflight(narrowed_plan, plan_path)

        err = capsys.readouterr().err
        assert "stale detail: step(s) 1" in err
        assert "plan-tool detail --force" in err


class TestFmtFindingCounts:
    """``_fmt_finding_counts`` — the one-line severity breakdown."""

    def test_empty_list_renders_no_findings(self) -> None:
        assert _fmt_finding_counts([]) == "no findings"

    def test_buckets_render_in_fixed_severity_order(self) -> None:
        # Input order is deliberately scrambled; output follows the fixed
        # critical → high → medium → low → nit → info ordering.
        recs = [
            _rec("medium"), _rec("critical"), _rec("medium"),
            _rec("high"), _rec("medium"),
        ]
        assert _fmt_finding_counts(recs) == "1 critical, 1 high, 3 medium"

    def test_zero_buckets_are_dropped(self) -> None:
        # Only the populated severities appear; absent ones leave no
        # ``0 <sev>`` residue.
        assert _fmt_finding_counts([_rec("nit"), _rec("info"), _rec("info")]) == (
            "1 nit, 2 info"
        )

    def test_severity_match_is_case_insensitive(self) -> None:
        # The counter lower-cases each severity, so mixed-case buckets fold
        # together and still map onto the canonical order labels.
        assert _fmt_finding_counts([_rec("CRITICAL"), _rec("Critical")]) == (
            "2 critical"
        )


class TestFindingProgressLabel:
    """``_finding_progress_label`` — the ``<source>/<severity>: <title>`` line."""

    def test_formats_source_severity_and_title(self) -> None:
        rec = _rec("high", source="plan-correctness", title="ordering gap")
        assert _finding_progress_label(rec) == (
            "plan-correctness/high [confidence: limited]: ordering gap"
        )

    def test_title_is_stripped(self) -> None:
        rec = _rec("medium", source="deps", title="  padded title  ")
        assert _finding_progress_label(rec) == (
            "deps/medium [confidence: limited]: padded title"
        )


class TestResolutionForVerdict:
    """``_resolution_for_verdict`` maps an apply verdict to the carried
    ``(resolution, reason)`` tuple. This is the live path that makes
    ``blocked`` reachable — saved annotations never carry it."""

    def test_resolution_for_verdict_maps_applied(self) -> None:
        assert _resolution_for_verdict("APPLIED") == (
            CARRIED_RESOLUTION_APPLIED, ""
        )

    def test_resolution_for_verdict_maps_blocked(self) -> None:
        # Both blocked verdicts carry the exact verdict as the reason so
        # BLOCKED-STRUCTURAL stays distinguishable downstream.
        assert _resolution_for_verdict("BLOCKED") == (
            CARRIED_RESOLUTION_BLOCKED, "BLOCKED"
        )
        assert _resolution_for_verdict("BLOCKED-STRUCTURAL") == (
            CARRIED_RESOLUTION_BLOCKED, "BLOCKED-STRUCTURAL"
        )

    def test_resolution_for_verdict_maps_skipped(self) -> None:
        assert _resolution_for_verdict("NOT-APPLICABLE") == (
            CARRIED_RESOLUTION_SKIPPED, "NOT-APPLICABLE"
        )

    def test_resolution_for_verdict_maps_unknown_open(self) -> None:
        # An untrusted apply result stays retry-neutral (open), not a
        # deliberate skip — both the contract token and any junk verdict.
        assert _resolution_for_verdict("UNKNOWN") == (
            CARRIED_RESOLUTION_OPEN, "UNKNOWN"
        )
        assert _resolution_for_verdict("gibberish") == (
            CARRIED_RESOLUTION_OPEN, "gibberish"
        )


class TestCompletenessHasBlockingFindings:
    """``_completeness_has_blocking_findings`` — the medium+ blocking gate.

    Surfaced as ``has_blocking_findings`` in ``--json``; it no longer drives
    the exit code. Each keyword argument is a distinct finding bucket, so the
    tests flip exactly one at a time off an all-clear baseline.
    """

    def _clear(self, **overrides) -> dict:
        base = dict(
            path_style_hint=None,
            dep_issues=[],
            body_issues=[],
            detail_cov_issues=[],
            detail_body_issues=[],
            lessons_issues=[],
            data_contract_recs=(),
            self_consistency_recs=(),
            purity_coverage_recs=(),
            audit_recs=(),
            audit_stage=STAGE_DETAIL,
        )
        base.update(overrides)
        return base

    def test_all_clear_is_not_blocking(self) -> None:
        assert _completeness_has_blocking_findings(**self._clear()) is False

    def test_path_style_hint_blocks(self) -> None:
        assert _completeness_has_blocking_findings(
            **self._clear(path_style_hint="repo-relative")
        ) is True

    def test_dep_issues_block(self) -> None:
        assert _completeness_has_blocking_findings(
            **self._clear(dep_issues=["step 2 blocked on 1"])
        ) is True

    def test_body_issues_block(self) -> None:
        assert _completeness_has_blocking_findings(
            **self._clear(body_issues=["missing acceptance section"])
        ) is True

    def test_detail_body_issues_block(self) -> None:
        assert _completeness_has_blocking_findings(
            **self._clear(detail_body_issues=["placeholder detail body"])
        ) is True

    def test_lessons_issues_block(self) -> None:
        assert _completeness_has_blocking_findings(
            **self._clear(lessons_issues=["missing lessons entry"])
        ) is True

    def test_missing_on_disk_detail_coverage_blocks(self) -> None:
        issue = DetailCoverageIssue(
            step_id=2, kind="missing_on_disk", detail_path="plan-details/x.md"
        )
        assert _completeness_has_blocking_findings(
            **self._clear(detail_cov_issues=[issue])
        ) is True

    def test_non_missing_detail_coverage_kind_does_not_block(self) -> None:
        # The gate filters detail-coverage issues by ``kind == "missing_on_disk"``;
        # any other kind is non-blocking on its own.
        other = SimpleNamespace(kind="present_but_stale")
        assert _completeness_has_blocking_findings(
            **self._clear(detail_cov_issues=[other])
        ) is False

    def test_files_coherence_is_not_a_blocking_gate_input(self) -> None:
        """INFO/NIT coherence diagnostics cannot appear blocking by signature."""
        assert "files_coh_issues" not in inspect.signature(
            _completeness_has_blocking_findings
        ).parameters

    def test_audit_recs_block_at_medium_and_above_at_detail(self) -> None:
        for sev in ("medium", "high", "critical"):
            assert _completeness_has_blocking_findings(
                **self._clear(audit_recs=[_rec(sev)])
            ) is True, sev

    def test_bare_medium_completeness_not_blocking_under_bar(self) -> None:
        assert _completeness_has_blocking_findings(
            **self._clear(
                audit_recs=[_rec("medium", source="plan-completeness")],
                audit_stage=STAGE_BARE,
            )
        ) is False

    def test_bare_medium_correctness_still_blocks(self) -> None:
        assert _completeness_has_blocking_findings(
            **self._clear(
                audit_recs=[_rec("medium", source="plan-correctness")],
                audit_stage=STAGE_BARE,
            )
        ) is True

    def test_detail_docs_medium_demoted_under_bar(self) -> None:
        from tests.test_review import docs_detail_body_fixture

        assert _completeness_has_blocking_findings(
            **self._clear(
                audit_recs=[docs_detail_body_fixture()],
                audit_stage=STAGE_DETAIL,
            )
        ) is False

    def test_detail_code_logic_medium_blocks(self) -> None:
        assert _completeness_has_blocking_findings(
            **self._clear(
                audit_recs=[
                    _rec(
                        "medium",
                        source="plan-correctness",
                        title="logic gap",
                    )
                ],
                audit_stage=STAGE_DETAIL,
            )
        ) is True

    def test_precomputed_conceptual_bar_ids_win_over_recompute(self) -> None:
        """When ``conceptual_bar_blocking_ids`` is given, it drives the
        conceptual arm directly instead of recomputing from ``audit_recs`` --
        the two must be able to disagree here to prove the passed tuple (not
        a fresh ``compute_conceptual_bar_blocking_ids`` call) decided it."""
        # audit_recs alone would not block (nit only); the passed tuple does.
        assert _completeness_has_blocking_findings(
            **self._clear(
                audit_recs=[_rec("nit")],
                conceptual_bar_blocking_ids=("plan-correctness-fake",),
            )
        ) is True
        # audit_recs alone would block (medium+); an explicit empty tuple
        # (not None) must suppress that, proving it isn't recomputed either.
        assert _completeness_has_blocking_findings(
            **self._clear(
                audit_recs=[_rec("high")],
                conceptual_bar_blocking_ids=(),
            )
        ) is False

    def test_non_conceptual_arms_unchanged(self) -> None:
        issue = DetailCoverageIssue(
            step_id=2, kind="missing_on_disk", detail_path="plan-details/x.md"
        )
        assert _completeness_has_blocking_findings(
            **self._clear(
                detail_cov_issues=[issue],
                audit_stage=STAGE_BARE,
            )
        ) is True
        assert _completeness_has_blocking_findings(
            **self._clear(
                self_consistency_recs=[_rec("medium", source="intent-presence")],
                audit_stage=STAGE_BARE,
            )
        ) is True

    def test_audit_recs_below_medium_do_not_block(self) -> None:
        assert _completeness_has_blocking_findings(
            **self._clear(audit_recs=[_rec("nit"), _rec("info")])
        ) is False

    def test_completeness_report_gate_keeps_high_impact_nit_advisory(self) -> None:
        assert _completeness_has_blocking_findings(
            **self._clear(
                audit_recs=[_rec("nit", impact="high", complexity="low")]
            )
        ) is False

    def test_audit_rec_severity_match_is_case_insensitive(self) -> None:
        assert _completeness_has_blocking_findings(
            **self._clear(audit_recs=[_rec("HIGH")])
        ) is True

    def test_data_contract_drift_can_block(self) -> None:
        assert _completeness_has_blocking_findings(
            **self._clear(data_contract_recs=[_rec("medium", source="data-contract")])
        ) is True

    def test_input_contract_findings_are_blocking(self) -> None:
        assert _completeness_has_blocking_findings(
            **self._clear(
                data_contract_recs=[
                    _rec("medium", source="data-contract", title="stale input")
                ]
            )
        ) is True

    def test_self_consistency_recs_block_at_medium_and_above(self) -> None:
        for sev in ("medium", "high", "critical"):
            assert _completeness_has_blocking_findings(
                **self._clear(
                    self_consistency_recs=[_rec(sev, source="orphaned-deliverable")]
                )
            ) is True, sev

    def test_orphaned_deliverable_medium_blocks(self) -> None:
        # A ``medium`` orphaned-deliverable rec on the self-consistency bucket
        # flips the blocking gate (step 3's producer).
        assert _completeness_has_blocking_findings(
            **self._clear(
                self_consistency_recs=[_rec("medium", source="orphaned-deliverable")]
            )
        ) is True

    def test_self_consistency_suppression_blocks(self) -> None:
        # The elevated ``suppression-shape`` rec (this step's first producer)
        # blocks through the same medium+ branch as ``orphaned-deliverable``.
        assert _completeness_has_blocking_findings(
            **self._clear(
                self_consistency_recs=[_rec("medium", source="suppression-shape")]
            )
        ) is True

    def test_self_consistency_recs_below_medium_do_not_block(self) -> None:
        assert _completeness_has_blocking_findings(
            **self._clear(
                self_consistency_recs=[
                    _rec("info", source="orphaned-deliverable"),
                    _rec("nit", source="orphaned-deliverable"),
                ]
            )
        ) is False

    def test_intent_presence_blocks_at_medium(self) -> None:
        # Promoted onto the blocking bucket: a ``medium`` intent rec flips the
        # gate through the same medium+ branch as every other member, and the
        # threshold is still the threshold — an ``info`` one does not.
        assert _completeness_has_blocking_findings(
            **self._clear(
                self_consistency_recs=[_rec("medium", source="intent-presence")]
            )
        ) is True
        assert _completeness_has_blocking_findings(
            **self._clear(
                self_consistency_recs=[_rec("info", source="intent-presence")]
            )
        ) is False

    def test_claim_vs_delivery_on_smell_recs_never_blocks(self) -> None:
        # ``claim-vs-delivery`` is an ``info`` advisory that rides ``smell_recs``
        # — a bucket ``_completeness_has_blocking_findings`` does not even accept
        # as a parameter, so it can never gate. The all-clear baseline (smells
        # unrepresented) stays non-blocking, and even were an ``info`` claim rec
        # to leak onto the blocking bucket it stays below the medium+ threshold.
        assert _completeness_has_blocking_findings(**self._clear()) is False
        assert _completeness_has_blocking_findings(
            **self._clear(
                self_consistency_recs=[_rec("info", source="claim-vs-delivery")]
            )
        ) is False

    def test_self_consistency_rec_severity_match_is_case_insensitive(self) -> None:
        assert _completeness_has_blocking_findings(
            **self._clear(
                self_consistency_recs=[_rec("MEDIUM", source="orphaned-deliverable")]
            )
        ) is True

    def test_all_clear_stays_not_blocking_with_empty_self_consistency(self) -> None:
        # The all-clear baseline now carries ``self_consistency_recs=()``; it
        # must still be non-blocking.
        assert _completeness_has_blocking_findings(**self._clear()) is False

    def test_purity_coverage_recs_block_at_high(self) -> None:
        # Failed purity scan is a coverage error (``high``), not an advisory
        # smell — it must flip the blocking gate.
        assert _completeness_has_blocking_findings(
            **self._clear(
                purity_coverage_recs=[
                    _rec("high", source="purity-scan-failed")
                ]
            )
        ) is True
        assert _completeness_has_blocking_findings(
            **self._clear(
                purity_coverage_recs=[
                    _rec("info", source="purity-scan-failed")
                ]
            )
        ) is False


# --- Per-phase helpers (step 21 extraction) --------------------------------
#
# The five classes below give each named phase helper its first *direct*
# unit test, so a maintainer editing one phase gets a focused failure on
# that seam instead of a far-away end-to-end break. The phantom phases in
# the step title get no class: "detail-bundle assembly" lives inside
# ``audit_plan_until_stable`` (review.py), consumed at the
# ``_sample_conceptual_audit`` boundary; and ``_run_iterate_convergence_loop``
# is integration-shaped (real apply_finding / drift / lock) and stays pinned
# by the domain suites (``tests/test_review_walk.py`` et al.).


def _sectioned_plan_text(steps_block: str, *, intent: str = "") -> str:
    """A detector-clean plan: every ``create.PLAN_BODY_SECTIONS`` H2 carries
    real (non-placeholder) content so ``check_body_completeness`` finds no
    gap. ``steps_block`` is the frontmatter ``steps:`` YAML, letting a caller
    inject a dependency gap without disturbing the clean body.

    ``intent`` is the plan-level value; omitted by default, which the blocking
    ``intent-presence`` check flags. Pass it (with per-step intents in
    ``steps_block``) to build a fixture clean against *every* detector."""
    body = "\n".join(
        f"## {name}\n\nReal content for the {name} section.\n"
        for name in PLAN_BODY_SECTIONS
    )
    return (
        "---\n"
        "title: Sectioned Plan\n"
        f"{f'intent: {intent}\n' if intent else ''}"
        "status: planning\n"
        "priority: low\n"
        f"{steps_block}"
        "---\n"
        "# Sectioned Plan\n\n"
        f"{body}"
    )


# A single non-detail, non-footprint step — clean against every detector but
# ``intent-presence``, which every no-intent plan trips.
_CLEAN_STEPS = "steps:\n  - id: 1\n    title: Only step\n"
# The same step carrying an intent; paired with ``_sectioned_plan_text``'s
# ``intent=`` it builds a fixture that trips nothing at all.
_INTENT_BEARING_STEPS = (
    "steps:\n  - id: 1\n    title: Only step\n    intent: why the step exists\n"
)
_PLAN_INTENT = "why this plan exists"
# One step whose title mixes a refactor verb ("Refactor") and a feature verb
# ("add"), tripping the real ``granularity-split`` detector — with no files,
# so well-formedness stays clean (no path-style/file-existence finding).
_GRANULARITY_SPLIT_STEPS = (
    "steps:\n  - id: 1\n    title: Refactor the parser and add caching\n"
)
# Step 2 (committed) depends on a parked step 1. The schema rejects this at
# parse time — a committed step can never depend on deferred/wont_do work —
# so a parseable plan can no longer carry a dependency gap at all.
_DEP_GAP_STEPS = (
    "steps:\n"
    "  - id: 1\n    title: First\n    scope: deferred\n"
    "  - id: 2\n    title: Second\n    depends_on: [1]\n"
)


def _write_and_parse(tmp_repo, steps_block: str, *, intent: str = ""):
    """Write the sectioned plan into the tmp repo and return ``(plan, path)``."""
    path = tmp_repo.plans_dir / "1-sectioned.md"
    path.write_text(
        _sectioned_plan_text(steps_block, intent=intent), encoding="utf-8"
    )
    return parse_plan(path), path


def _qualifying_producer_coverage(
    *,
    budget_limited: bool = False,
    passes_used: int = 1,
    cap: int = 1,
) -> dict[str, object]:
    """Producer-shaped coverage that ``audit_coverage_qualifies_sample`` accepts."""
    return {
        "budget_limited": budget_limited,
        "passes_used": passes_used,
        "cap": cap,
        "recommendation_kind": None,
        "recommended_passes": None,
        "recommendation_advice": None,
        "confirmation_kind": None,
        "conforming_pass_count": 1,
        "failed_or_malformed_pass_count": 0,
    }


def _hoisted_bundle(plan, path, repo_root):
    """Mirror ``cmd_completeness``'s pre-branch hoist for finalize/loop callers."""
    from plan_tool.review import audit_detail_bundle_status

    bundle_status = audit_detail_bundle_status(
        plan, path, repo_root,
    )
    return bundle_status, derive_audit_stage(bundle_status)


def _write_input_contract_plan(tmp_repo):
    plan_tool_dir = tmp_repo.root / "plan_tool"
    plan_tool_dir.mkdir()
    (plan_tool_dir / "review_persistence.py").write_text(
        "class SavedReview:\n    pass\n", encoding="utf-8"
    )
    detail_dir = tmp_repo.root / "details"
    detail_dir.mkdir()
    (detail_dir / "01.md").write_text(
        "# Step 1\n\n"
        "## Summary\n\nsummary\n\n"
        "## Table of Contents\n\n- [Input](#input) - input\n\n"
        "## Input\n\n"
        "Reads `SavedReview.not_a_field` from "
        "`plan_tool/review_persistence.py:SavedReview`.\n\n"
        "## Why\n\nwhy\n\n"
        "## Files\n\nplan_tool/review_persistence.py\n\n"
        "## Implementation\n\nimplementation\n\n"
        "## Tests\n\ntests\n\n"
        "## Acceptance criteria\n\nacceptance\n",
        encoding="utf-8",
    )
    steps = (
        "steps:\n"
        "  - id: 1\n"
        "    title: Only step\n"
        "    files: [plan_tool/review_persistence.py]\n"
        "    detail: details/01.md\n"
    )
    path = tmp_repo.plans_dir / "1-sectioned.md"
    path.write_text(_sectioned_plan_text(steps), encoding="utf-8")
    return parse_plan(path), path


def _mixed_step_rec(step_id: int = 1) -> Recommendation:
    """A ``medium`` MIXED-STEP ``granularity-split`` rec, matching the shape
    ``granularity.parse_mixed_step_findings`` produces (``source`` +
    ``severity`` + ``step_id`` that downstream steps 3-4 key on)."""
    return Recommendation(
        id=f"granularity-split-{step_id}",
        source="granularity-split",
        severity="medium",
        step_id=step_id,
        title=f"Step {step_id}: mixed refactor + feature (split recommended)",
        body="mixes a behavior-preserving refactor with new behavior",
    )


def _write_plan_with_detail(
    tmp_repo, *, detail_body: str = "detail prose\n", change_type: str | None = None
):
    """Write a one-step plan whose step carries a real on-disk detail file,
    so the per-step purity producer's quiet probe has a body to judge.
    ``change_type`` (e.g. ``non-code``) is stamped onto the step when given."""
    detail_rel = "details/01.md"
    detail_path = tmp_repo.root / detail_rel
    detail_path.parent.mkdir(parents=True, exist_ok=True)
    detail_path.write_text(detail_body, encoding="utf-8")
    ct_line = f"    change_type: {change_type}\n" if change_type else ""
    steps = (
        "steps:\n"
        "  - id: 1\n"
        "    title: Only step\n"
        f"{ct_line}"
        f"    detail: {detail_rel}\n"
    )
    path = tmp_repo.plans_dir / "1-sectioned.md"
    path.write_text(_sectioned_plan_text(steps), encoding="utf-8")
    return parse_plan(path), path


def _detail_with_impl_tests(impl: str = "impl prose", tests: str = "tests prose") -> str:
    """A detail body carrying real ``## Implementation`` + ``## Tests`` sections
    so ``_impl_tests_section_text`` (and step 4's diff) have content to compare."""
    return (
        "## Summary\n\nsummary\n\n"
        f"## Implementation\n\n{impl}\n\n"
        f"## Tests\n\n{tests}\n"
    )


def _seed_purity_entry(tmp_repo, plan, path, step, *, impl_tests_text, **overrides):
    """Store a purity cache entry for ``step`` whose combined ``cache_key`` is
    stale (forces a *miss*) but whose components default to the current tree's,
    so step-4 grading routes on the components. ``overrides`` replaces any stored
    field (``change_type``, ``all_files_fingerprint``, ``detail_relpath``, …)."""
    from plan_tool.fingerprint import compute_purity_cache_key
    from plan_tool.purity_cache import (
        PurityCache,
        PurityCacheEntry,
        purity_cache_path,
        save_purity_cache,
    )

    _key, comps = compute_purity_cache_key(plan, path, step, tmp_repo.root)
    slug = slug_from_filename(path)
    fields = dict(
        step_id=step.id,
        cache_key="stale-key-forces-miss",
        detail_hash=comps.detail_hash,
        all_files_fingerprint=comps.all_files_fingerprint,
        change_type=comps.change_type,
        depends_on=list(comps.depends_on),
        purity_verdict_logic_version=comps.logic_version,
        detail_relpath=step.detail,
        findings=[],
        impl_tests_text=impl_tests_text,
        checked_at="2026-07-18T00:00:00Z",
    )
    fields.update(overrides)
    entry = PurityCacheEntry(**fields)
    save_purity_cache(
        purity_cache_path(tmp_repo.root, slug),
        PurityCache(plan_slug=slug, entries={step.id: entry}),
    )
    return entry


# Explicit completed empty set: an omitted verdict reads as ``absent``.
_CLEAR_VERDICT = blocking_verdict_from_gate([])


def _render_grouped_report(*args, **kw):
    """Render with a verdict blocking every listed conceptual gap unless a test
    passes ``verdict=`` to pin advisory or untrusted behavior."""
    if "verdict" not in kw:
        listed = [*kw.get("correctness_recs", ()), *kw.get("conceptual_recs", ())]
        kw["verdict"] = blocking_verdict_from_gate([r.id for r in listed])
    return _render_grouped_report_with_verdict(*args, **kw)


def _empty_det() -> _DeterministicReport:
    """An all-clear deterministic report — every issue list empty, no hint."""
    return _DeterministicReport(
        path_style_hint=None,
        dep_issues=[],
        body_issues=[],
        detail_cov_issues=[],
        detail_body_issues=[],
        files_coh_issues=[],
        lessons_issues=[],
    )


def _advisory_display() -> AuditShapeAdvisoryDisplay:
    return AuditShapeAdvisoryDisplay(
        shape_id="arm-clustering",
        source_plan_fingerprint="fresh-snapshot",
        arm_steps=((2, "Focused work"), (3, "Focused follow-up")),
        material_finding_count=4,
        arm_finding_count=3,
        committed_step_count=5,
        anchor_groups=(
            ("Correctness", ("design-gap",)),
            ("Completeness", ("risk-gap", "edge-gap")),
        ),
    )


def _det_with_smells(smell_recs: list) -> _DeterministicReport:
    """An otherwise all-clear report carrying only the given smell recs."""
    return _DeterministicReport(
        path_style_hint=None,
        dep_issues=[],
        body_issues=[],
        detail_cov_issues=[],
        detail_body_issues=[],
        files_coh_issues=[],
        lessons_issues=[],
        smell_recs=smell_recs,
    )


def _det_with_self_consistency(recs: list) -> _DeterministicReport:
    """An otherwise all-clear report carrying only the given
    self-consistency recs."""
    return _DeterministicReport(
        path_style_hint=None,
        dep_issues=[],
        body_issues=[],
        detail_cov_issues=[],
        detail_body_issues=[],
        files_coh_issues=[],
        lessons_issues=[],
        self_consistency_recs=recs,
    )


def test_grouped_report_renders_full_concept_coverage_finding() -> None:
    rec = dataclasses.replace(
        _rec("medium", source="concept-coverage"),
        id="plan-concept-coverage-stable",
        body="Concept `abc123` needs an explicit owner or structured deferral.",
        anchor="concept-link",
    )
    md = _render_grouped_report(
        SimpleNamespace(title="P"), SimpleNamespace(name="p"),
        _det_with_self_consistency([rec]),
        correctness_recs=[], conceptual_recs=[], audit_recs=[],
        iterate_enabled=False,
    )
    assert "### Self-consistency" in md
    assert "`[concept-link]`" in md
    assert rec.body in md
    assert "_(no completeness issues detected)_" not in md


def test_json_preserves_explicit_link_concept_finding(capsys) -> None:
    rec = dataclasses.replace(
        _rec("medium", source="concept-coverage"),
        id="plan-concept-coverage-stable",
        title="Missing explicit concept link",
        body="Full owner-or-deferral remedy.",
    )
    rc = _render_completeness_json(
        SimpleNamespace(name="p", fail_on_findings=True),
        _det_with_self_consistency([rec]), [], has_blocking=True,
    )
    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert payload["has_blocking_findings"] is True
    assert payload["checks"]["self_consistency"] == [{
        "severity": "medium",
        "source": "concept-coverage",
        "id": "plan-concept-coverage-stable",
        "title": "Missing explicit concept link",
        "confidence": "limited",
        "body": "Full owner-or-deferral remedy.",
    }]


def test_medium_concept_coverage_blocks_existing_gate() -> None:
    assert _completeness_has_blocking_findings(
        path_style_hint=None,
        dep_issues=[], body_issues=[], detail_cov_issues=[],
        detail_body_issues=[], lessons_issues=[],
        self_consistency_recs=[_rec("medium", source="concept-coverage")],
        audit_stage=STAGE_DETAIL,
        data_contract_recs=[],
        purity_coverage_recs=[],
    )


class TestRunDeterministicChecks:
    """``_run_deterministic_checks`` — the no-claude authoring-gap battery.

    Asserts *which* issue field fires, not detector wording (that is the
    detectors' own suites in ``plan_tool/review.py``).
    """

    def test_clean_plan_yields_empty_report(self, tmp_repo) -> None:
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        report = _run_deterministic_checks(plan, path, ctx, plan_name="p", quiet=True)
        assert report.path_style_hint is None
        assert report.dep_issues == []
        assert report.body_issues == []
        assert report.detail_cov_issues == []
        assert report.detail_body_issues == []
        assert report.files_coh_issues == []
        assert report.lessons_issues == []

    def test_dependency_gap_rejected_at_parse(self, tmp_repo) -> None:
        # A committed step depending on a parked step is a hard parse error,
        # so the dep gap can't reach the deterministic checks at all — the
        # check moved from a soft runtime warning to a parse-time guard.
        with pytest.raises(ParserValidationError, match="depends_on parked"):
            _write_and_parse(tmp_repo, _DEP_GAP_STEPS)

    def test_returns_deterministic_report_type(self, tmp_repo) -> None:
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        report = _run_deterministic_checks(plan, path, ctx, plan_name="p", quiet=True)
        assert isinstance(report, _DeterministicReport)
        for field in (
            "path_style_hint",
            "dep_issues",
            "body_issues",
            "detail_cov_issues",
            "detail_body_issues",
            "files_coh_issues",
            "lessons_issues",
            "smell_recs",
            "self_consistency_recs",
            "data_contract_recs",
            "data_contract_payloads",
        ):
            assert hasattr(report, field)

    def test_completeness_audit_reports_canonical_only_detail_findings(
        self, tmp_repo
    ) -> None:
        # A step whose ``detail:`` pointer was never persisted but whose
        # canonical file is on disk must have its body judged — pins that
        # ``_run_deterministic_checks`` threads the plan path through.
        # Plan ``1-sectioned.md`` → bundle ``plan-details/sectioned/``;
        # step 1 "Only step" → canonical ``01-only-step.md``.
        steps = "steps:\n  - id: 1\n    title: Only step\n"
        plan, path = _write_and_parse(tmp_repo, steps)
        bundle = tmp_repo.plans_dir / "plan-details" / "sectioned"
        bundle.mkdir(parents=True)
        (bundle / "01-only-step.md").write_text(
            "# Step 1\n\n## Summary\n\nonly a summary\n", encoding="utf-8"
        )
        report = _run_deterministic_checks(
            plan, path, SimpleNamespace(repo_root=tmp_repo.root),
            plan_name="p", quiet=True,
        )
        assert {i.step_id for i in report.detail_body_issues} == {1}
        rel = "plans/plan-details/sectioned/01-only-step.md"
        assert {i.detail_path for i in report.detail_body_issues} == {rel}
        # The reattach-the-pointer diagnostic still fires alongside it.
        assert [i.kind for i in report.detail_cov_issues] == [
            "unreferenced_on_disk"
        ]

    def test_intent_presence_lands_on_self_consistency_recs(self, tmp_repo) -> None:
        # The blocking-capable bucket, never the advisory one — and still
        # capped at two however many steps lack an intent.
        steps = (
            "steps:\n"
            "  - id: 1\n    title: First\n"
            "  - id: 2\n    title: Second\n"
            "  - id: 3\n    title: Third\n"
        )
        plan, path = _write_and_parse(tmp_repo, steps)
        report = _run_deterministic_checks(
            plan, path, SimpleNamespace(repo_root=tmp_repo.root),
            plan_name="p", quiet=True,
        )
        intent_recs = [
            r for r in report.self_consistency_recs
            if r.source == "intent-presence"
        ]
        assert len(intent_recs) == 2
        assert all(r.severity == "medium" for r in intent_recs)
        assert not [
            r for r in report.smell_recs if r.source == "intent-presence"
        ]

    def test_intent_presence_still_reaches_the_smell_fanout(self, tmp_repo) -> None:
        # The detector stays in ``SMELL_DETECTORS``: the partition moves the
        # findings, it does not move where they are computed.
        from plan_tool.review import collect_smell_findings

        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        recs = collect_smell_findings(
            plan, tmp_repo.root, plan_name="p", plan_path=path
        )
        assert [
            r.source for r in recs if r.source == "intent-presence"
        ] == ["intent-presence", "intent-presence"]

    def test_plan_with_intents_yields_no_intent_findings(self, tmp_repo) -> None:
        steps = (
            "steps:\n"
            "  - id: 1\n    title: First\n    intent: why the first step\n"
            "  - id: 2\n    title: Second\n    intent: why the second step\n"
        )
        plan, path = _write_and_parse(tmp_repo, steps, intent=_PLAN_INTENT)
        assert plan.intent == _PLAN_INTENT
        report = _run_deterministic_checks(
            plan, path, SimpleNamespace(repo_root=tmp_repo.root),
            plan_name="p", quiet=True,
        )
        assert not [
            r for r in report.smell_recs if r.source == "intent-presence"
        ]
        assert not [
            r for r in report.self_consistency_recs
            if r.source == "intent-presence"
        ]

    def test_run_deterministic_checks_yields_intent_self_consistency_bucket(
        self, tmp_repo
    ) -> None:
        # Clean steps trip no suppression-shape producer, but they declare no
        # intent — so the blocking bucket carries exactly the two intent recs.
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        report = _run_deterministic_checks(
            plan, path, ctx, plan_name="p", quiet=True
        )
        assert [r.source for r in report.self_consistency_recs] == [
            "intent-presence",
            "intent-presence",
        ]

    def test_intent_bearing_plan_yields_empty_self_consistency_bucket(
        self, tmp_repo
    ) -> None:
        # The empty-bucket control, restated for a plan that supplies both
        # altitudes' intents.
        plan, path = _write_and_parse(
            tmp_repo, _INTENT_BEARING_STEPS, intent=_PLAN_INTENT
        )
        report = _run_deterministic_checks(
            plan, path, SimpleNamespace(repo_root=tmp_repo.root),
            plan_name="p", quiet=True,
        )
        assert report.self_consistency_recs == []

    def test_run_deterministic_checks_collects_concept_findings(
        self, tmp_repo
    ) -> None:
        from plan_tool.concept_tree import ConceptNode, ConceptTree, concept_id, save_concepts
        from plan_tool.review_persistence import compute_plan_fingerprint

        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        node = ConceptNode(
            id=concept_id("Missing owner", []),
            title="Missing owner",
            decision="include",
            review_state="approved",
        )
        save_concepts(
            path,
            ConceptTree(
                plan_slug="sectioned",
                plan_fingerprint=compute_plan_fingerprint(path),
                concepts=[node],
            ),
        )
        report = _run_deterministic_checks(
            plan, path, SimpleNamespace(repo_root=tmp_repo.root),
            plan_name="p", quiet=True,
        )
        assert [r.source for r in report.self_consistency_recs] == [
            "concept-coverage",
            "intent-presence",
            "intent-presence",
        ]
        # Partitioned off the advisory bucket entirely — and the plan's
        # ``intent-presence`` findings now leave with it, so nothing remains.
        assert report.smell_recs == []

    def test_run_deterministic_checks_collects_data_contract_drift(
        self, tmp_repo, monkeypatch
    ) -> None:
        import plan_tool.cli.completeness_phases as phases

        rec = _rec("medium", source="data-contract")
        payload = {
            "target_section": "SavedReview",
            "operation": "add",
            "candidate_fields": {"field": "new_field"},
            "freshness": {"registry_fingerprint": "r", "contract_fingerprint": "c"},
        }
        monkeypatch.setattr(
            phases,
            "_collect_data_contract_drift",
            lambda repo_root: ([rec], {rec.id: payload}),
        )
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        report = _run_deterministic_checks(
            plan, path, ctx, plan_name="p", quiet=True
        )
        assert report.data_contract_recs == [rec]
        assert report.data_contract_payloads == {rec.id: payload}

    def test_run_deterministic_checks_no_data_contract_drift_yields_empty_bucket(
        self, tmp_repo, monkeypatch
    ) -> None:
        import plan_tool.cli.completeness_phases as phases

        monkeypatch.setattr(
            phases, "_collect_data_contract_drift", lambda repo_root: ([], {})
        )
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        report = _run_deterministic_checks(
            plan, path, ctx, plan_name="p", quiet=True
        )
        assert report.data_contract_recs == []
        assert report.data_contract_payloads == {}

    def test_run_deterministic_checks_survives_data_contract_attribute_error(
        self, tmp_repo, monkeypatch, capsys
    ) -> None:
        """A transient ``AttributeError`` from ``post_detectors`` (e.g. a race
        importing ``run_log`` against a concurrently-edited working tree)
        must not take the whole deterministic battery down — it is caught,
        reported, and the run completes with an empty data-contract bucket
        rather than crashing.
        """
        import plan_tool.cli.completeness_phases as phases

        def _boom(repo_root):
            raise AttributeError(
                "module 'plan_tool.run_log' has no attribute 'RoadmapLocalRevisionPreflight'"
            )

        monkeypatch.setattr(phases, "_collect_data_contract_drift", _boom)
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        report = _run_deterministic_checks(
            plan, path, ctx, plan_name="p", quiet=True
        )
        assert report.data_contract_recs == []
        assert report.data_contract_payloads == {}
        assert "RoadmapLocalRevisionPreflight" in capsys.readouterr().err

    def test_collect_data_contract_drift_reports_alias_in_memory_and_constants(
        self, tmp_path
    ) -> None:
        from plan_tool import data_contract as contract

        saved = next(
            item
            for item in contract.persisted_dataclass_contracts()
            if item.owner == "SavedReview"
        )
        rows = "\n".join(
            f"| `{name}` | documented |" for name in saved.field_names
        )
        (tmp_path / "DATA_CONTRACT.md").write_text(
            "\n".join(
                [
                    "# Data Contract",
                    "",
                    "## Saved review sidecar",
                    "",
                    "### `SavedReview` (`review_persistence.py`)",
                    "",
                    "| Field | Meaning |",
                    "|---|---|",
                    rows,
                    "",
                ]
            ),
            encoding="utf-8",
        )

        recs, payloads = _collect_data_contract_drift(tmp_path)
        saved_payloads = [
            payload
            for payload in payloads.values()
            if payload["owner"] == "SavedReview"
        ]
        candidate_by_requirement = {
            payload["candidate_fields"].get("requirement"): payload
            for payload in saved_payloads
        }

        assert candidate_by_requirement["schema_constant"]["field_or_key"] == (
            "SCHEMA_VERSION"
        )
        assert candidate_by_requirement["json_key_alias"]["field_or_key"] == "version"
        assert candidate_by_requirement["json_key_alias"]["candidate_fields"][
            "field"
        ] == "schema_version"
        assert candidate_by_requirement["in_memory_only"]["field_or_key"] == "path"
        assert all(rec.source == "data-contract" for rec in recs)

    def test_data_contract_drift_recommendation_is_supported(self) -> None:
        from plan_tool.data_contract import make_drift_record
        from plan_tool.cli.completeness_phases import _data_contract_rec_for_record

        rec = _data_contract_rec_for_record(
            make_drift_record(
                source_type="dataclass",
                owner="Recommendation",
                field_or_key="confidence",
                target_section="Recommendation",
                operation="add",
                contract_text="",
            )
        )

        assert rec.confidence == "supported"

    def test_in_memory_only_drift_converges_after_apply(self, tmp_path) -> None:
        """Applying an in-memory-only drift record clears it on re-audit.

        Regression: the apply actuator used to render every row ``persisted =
        yes`` and never emit the "in-memory" phrase the drift check requires, so
        the finding re-surfaced after every apply and mislabeled the field.
        """
        from plan_tool import data_contract as contract
        from plan_tool.cli import data_contract_cmd

        saved = next(
            item
            for item in contract.persisted_dataclass_contracts()
            if item.owner == "SavedReview"
        )
        rows = "\n".join(
            f"| `{name}` | documented |" for name in saved.field_names
        )
        doc = tmp_path / "DATA_CONTRACT.md"
        doc.write_text(
            "\n".join(
                [
                    "# Data Contract",
                    "",
                    "### `SavedReview` (`review_persistence.py`)",
                    "",
                    "| Field | Persisted | Meaning |",
                    "|---|---|---|",
                    rows,
                    "",
                ]
            ),
            encoding="utf-8",
        )

        def _in_memory_payload(payloads):
            return next(
                p
                for p in payloads.values()
                if p["owner"] == "SavedReview"
                and p["candidate_fields"].get("requirement") == "in_memory_only"
            )

        _, payloads = _collect_data_contract_drift(tmp_path)
        payload = _in_memory_payload(payloads)
        assert data_contract_cmd._apply_payload_to_contract(doc, payload) is True

        # The applied row reads not-persisted and carries the in-memory phrase.
        assert "| `path` | **no** (in-memory) |" in doc.read_text(encoding="utf-8")

        # Re-audit: the in-memory drift is gone (converged), no re-surface.
        _, payloads_after = _collect_data_contract_drift(tmp_path)
        assert not [
            p
            for p in payloads_after.values()
            if p["owner"] == "SavedReview"
            and p["candidate_fields"].get("requirement") == "in_memory_only"
        ]

    def test_run_deterministic_checks_collects_input_contract_findings(
        self, tmp_repo
    ) -> None:
        plan, path = _write_input_contract_plan(tmp_repo)
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        report = _run_deterministic_checks(
            plan, path, ctx, plan_name="p", quiet=True
        )
        recs = [r for r in report.data_contract_recs if "not_a_field" in r.body]
        assert len(recs) == 1
        assert report.data_contract_payloads[recs[0].id]["target"] == "plan-detail"

    def test_run_deterministic_checks_threads_plan_name_and_collects_smells(
        self, tmp_repo, monkeypatch
    ) -> None:
        # Patch the smell collector on the *domain* module — the body-local
        # import in ``_run_deterministic_checks`` resolves to the patch.
        import plan_tool.review

        smell = _rec("info", source="feature-ref")
        seen: dict = {}

        def fake(plan, repo_root, *, plan_name, plan_path=None):
            seen["plan_name"] = plan_name
            return [smell]

        monkeypatch.setattr(plan_tool.review, "collect_smell_findings", fake)
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        report = _run_deterministic_checks(
            plan, path, ctx, plan_name="myplan", quiet=True
        )
        assert seen["plan_name"] == "myplan"
        assert report.smell_recs == [smell]

    def test_run_deterministic_checks_no_smells_yields_empty_bucket(
        self, tmp_repo, monkeypatch
    ) -> None:
        import plan_tool.review

        monkeypatch.setattr(
            plan_tool.review, "collect_smell_findings", lambda *a, **k: []
        )
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        report = _run_deterministic_checks(
            plan, path, ctx, plan_name="p", quiet=True
        )
        assert report.smell_recs == []

    def test_suppression_routes_to_self_consistency_not_smells(
        self, tmp_repo, monkeypatch
    ) -> None:
        # The elevated ``suppression-shape`` rec is partitioned off the advisory
        # ``smell_recs`` bucket onto the blocking-capable ``self_consistency``
        # bucket; other smells stay put.
        import plan_tool.review

        smell = _rec("info", source="feature-ref")
        supp = _rec("medium", source="suppression-shape")
        monkeypatch.setattr(
            plan_tool.review,
            "collect_smell_findings",
            lambda *a, **k: [smell, supp],
        )
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        report = _run_deterministic_checks(
            plan, path, ctx, plan_name="p", quiet=True
        )
        assert report.self_consistency_recs == [supp]
        assert supp not in report.smell_recs
        assert report.smell_recs == [smell]

    def test_orphaned_deliverable_lands_on_self_consistency_recs(
        self, tmp_repo, monkeypatch, capsys
    ) -> None:
        # The orphaned-deliverable detector's recs join the blocking-capable
        # ``self_consistency_recs`` bucket, never the advisory ``smell_recs``,
        # and stay out of the deterministic well-formedness count.
        import re

        import plan_tool.review

        orphan = _rec("medium", source="orphaned-deliverable")

        def _count_line(returns) -> int:
            monkeypatch.setattr(
                plan_tool.review,
                "detect_orphaned_deliverable",
                lambda *a, **k: returns,
            )
            plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
            ctx = SimpleNamespace(repo_root=tmp_repo.root)
            report = _run_deterministic_checks(
                plan, path, ctx, plan_name="p", quiet=False
            )
            err = capsys.readouterr().err
            m = re.search(r"(\d+) finding\(s\)", err)
            assert m is not None, err
            return report, int(m.group(1))

        report, count_with = _count_line([orphan])
        assert orphan in report.self_consistency_recs
        assert orphan not in report.smell_recs
        _, count_without = _count_line([])
        # The orphaned rec must not inflate ``_det_total``.
        assert count_with == count_without

    def test_claim_vs_delivery_lands_on_smell_recs(
        self, tmp_repo, monkeypatch, capsys
    ) -> None:
        # The claim-vs-delivery detector's recs join the advisory ``smell_recs``
        # bucket (not the blocking ``self_consistency_recs``), and stay out of
        # the deterministic well-formedness count. Patched on the domain module
        # so the body-local ``collect_smell_findings`` calls the stub.
        import re

        import plan_tool.review

        claim = _rec("info", source="claim-vs-delivery")

        def _run(returns):
            monkeypatch.setattr(
                plan_tool.review, "detect_claim_vs_delivery",
                lambda *a, **k: returns,
            )
            plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
            ctx = SimpleNamespace(repo_root=tmp_repo.root)
            report = _run_deterministic_checks(
                plan, path, ctx, plan_name="p", quiet=False
            )
            err = capsys.readouterr().err
            m = re.search(r"(\d+) finding\(s\)", err)
            assert m is not None, err
            return report, int(m.group(1))

        report, count_with = _run([claim])
        assert claim in report.smell_recs
        assert claim not in report.self_consistency_recs
        _, count_without = _run([])
        assert count_with == count_without

    def test_run_deterministic_checks_folds_granularity_into_smells(
        self, tmp_repo, monkeypatch
    ) -> None:
        # The cross-step granularity advisor's recs join the smell bucket
        # alongside the (patched) smell collector's output — one bucket.
        import plan_tool.granularity
        import plan_tool.review

        smell = _rec("info", source="feature-ref")
        gran = _rec("info", source="granularity-merge")
        monkeypatch.setattr(
            plan_tool.review, "collect_smell_findings", lambda *a, **k: [smell]
        )
        monkeypatch.setattr(
            plan_tool.granularity, "assess_granularity", lambda *a, **k: [gran]
        )
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        # ``run_purity`` defaults off, so the claude-judged MIXED-STEP producer
        # never fires here: the bucket is exactly the info detectors' output.
        report = _run_deterministic_checks(
            plan, path, ctx, plan_name="p", quiet=True
        )
        assert report.smell_recs == [smell, gran]
        assert not any(
            r.source == "granularity-split" and r.severity == "medium"
            for r in report.smell_recs
        )

    def test_run_deterministic_checks_produces_medium_mixed_step_finding(
        self, tmp_repo, monkeypatch
    ) -> None:
        # With the claude purity producer stubbed to return a medium mixed-step
        # rec, run_purity=True folds it into the advisory smell bucket.
        import plan_tool.detail

        mixed = _mixed_step_rec(step_id=1)
        # Flows through the read-through cache helper, which calls the producer
        # with return_status=True → the mock must return (findings, succeeded).
        monkeypatch.setattr(
            plan_tool.detail,
            "collect_detail_quality_findings",
            lambda *a, **k: ([mixed], True),
        )
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        report = _run_deterministic_checks(
            plan, path, ctx, plan_name="p", quiet=True, run_purity=True
        )
        found = [
            r for r in report.smell_recs
            if r.source == "granularity-split" and r.severity == "medium"
        ]
        assert len(found) == 1
        assert found[0].purity_verdict_provenance == "fresh"
        assert found[0].step_id == 1

    def test_purity_producer_keeps_only_medium_granularity_split(
        self, tmp_repo, monkeypatch
    ) -> None:
        # The producer filters its findings to the medium granularity-split
        # signal: an info split rec and a non-granularity rec are dropped.
        import plan_tool.detail

        mixed = _mixed_step_rec(step_id=1)
        info_split = _rec("info", source="granularity-split")
        grounding = _rec("medium", source="claude")
        monkeypatch.setattr(
            plan_tool.detail,
            "collect_detail_quality_findings",
            lambda *a, **k: ([mixed, info_split, grounding], True),
        )
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        report = _run_deterministic_checks(
            plan, path, ctx, plan_name="p", quiet=True, run_purity=True
        )
        # Only the medium mixed-step rec joins; the patched producer's other
        # recs (info split, claude grounding) never reach the bucket.
        medium = [
            r for r in report.smell_recs
            if r.source == "granularity-split" and r.severity == "medium"
        ]
        assert len(medium) == 1
        assert medium[0].purity_verdict_provenance == "fresh"
        assert info_split not in report.smell_recs
        assert grounding not in report.smell_recs

    def test_purity_pass_short_circuits_without_detail_bundle(
        self, tmp_repo
    ) -> None:
        # A plan whose step has no detail pointer: the real producer's quiet
        # probe returns [] before any claude call, so no medium rec appears and
        # the conftest backend gate confirms nothing spawned.
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        report = _run_deterministic_checks(
            plan, path, ctx, plan_name="p", quiet=True, run_purity=True
        )
        assert not any(
            r.source == "granularity-split" and r.severity == "medium"
            for r in report.smell_recs
        )

    def test_purity_pass_uses_patchable_invoker_seam(
        self, tmp_repo, monkeypatch
    ) -> None:
        # End-to-end through the real ``collect_detail_quality_findings``: the
        # only claude touch is the ``shell_detail_invoker`` seam, patched to a
        # canned MIXED-STEP response. Unmarked — the conftest gate blocks any
        # real backend spawn.
        import plan_tool.detail

        monkeypatch.setattr(
            plan_tool.detail,
            "shell_detail_invoker",
            lambda prompt: (
                "## Structural findings\n"
                "- MIXED-STEP: refactors the parser, then adds caching.\n"
            ),
        )
        plan, path = _write_plan_with_detail(tmp_repo)
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        report = _run_deterministic_checks(
            plan, path, ctx, plan_name="p", quiet=True, run_purity=True
        )
        medium = [
            r for r in report.smell_recs
            if r.source == "granularity-split" and r.severity == "medium"
        ]
        assert len(medium) == 1
        assert medium[0].step_id == 1

    def test_non_code_step_yields_no_mixed_step_finding(
        self, tmp_repo, monkeypatch
    ) -> None:
        # A non-code step is skipped before the producer is called, so even a
        # producer that would return a mixed-step rec yields none.
        import plan_tool.detail

        monkeypatch.setattr(
            plan_tool.detail,
            "collect_detail_quality_findings",
            lambda *a, **k: [_mixed_step_rec()],
        )
        plan, path = _write_plan_with_detail(tmp_repo, change_type="non-code")
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        report = _run_deterministic_checks(
            plan, path, ctx, plan_name="p", quiet=True, run_purity=True
        )
        assert not any(
            r.source == "granularity-split" and r.severity == "medium"
            for r in report.smell_recs
        )

    def test_info_split_detectors_stay_report_only_and_unchanged(
        self, tmp_repo, monkeypatch
    ) -> None:
        # The deterministic info granularity-split detector still fires; the
        # medium producer is an addition, not a replacement.
        import plan_tool.detail

        mixed = _mixed_step_rec(step_id=1)
        monkeypatch.setattr(
            plan_tool.detail,
            "collect_detail_quality_findings",
            lambda *a, **k: ([mixed], True),
        )
        plan, path = _write_and_parse(tmp_repo, _GRANULARITY_SPLIT_STEPS)
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        report = _run_deterministic_checks(
            plan, path, ctx, plan_name="p", quiet=True, run_purity=True
        )
        info_split = [
            r for r in report.smell_recs
            if r.source == "granularity-split" and r.severity == "info"
        ]
        assert info_split  # the real title heuristic still tripped
        assert any(
            r.id == mixed.id and r.purity_verdict_provenance == "fresh"
            for r in report.smell_recs
        )  # the medium rec is an addition

    def test_purity_medium_rec_excluded_from_deterministic_count(
        self, tmp_repo, monkeypatch, capsys
    ) -> None:
        # The medium mixed-step rec rides the advisory smell bucket, so an
        # otherwise-clean plan still reports 0 deterministic finding(s).
        import plan_tool.detail
        import plan_tool.review

        monkeypatch.setattr(
            plan_tool.review, "collect_smell_findings", lambda *a, **k: []
        )
        monkeypatch.setattr(
            plan_tool.detail,
            "collect_detail_quality_findings",
            lambda *a, **k: ([_mixed_step_rec()], True),
        )
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        report = _run_deterministic_checks(
            plan, path, ctx, plan_name="p", quiet=False, run_purity=True
        )
        assert any(
            r.source == "granularity-split" and r.severity == "medium"
            for r in report.smell_recs
        )
        assert "0 finding(s)" in capsys.readouterr().err

    def test_pre_apply_checkpoint_does_not_refire_purity_pass(
        self, tmp_repo, monkeypatch
    ) -> None:
        # The purity producer fires once (main audit, run_purity=True) but not
        # again from write_pre_apply_audit_checkpoint (run_purity defaults off),
        # even though both call sites run quiet=True under --iterate.
        import plan_tool.detail

        calls: list = []

        def counting(*a, **k):
            calls.append(k)
            return [_mixed_step_rec()], True

        monkeypatch.setattr(
            plan_tool.detail, "collect_detail_quality_findings", counting
        )
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        # Main audit under --iterate (quiet=True) still runs the purity pass.
        _run_deterministic_checks(
            plan, path, ctx, plan_name="p", quiet=True, run_purity=True
        )
        assert len(calls) == 1
        # The pre-apply checkpoint delegates to _run_deterministic_checks with
        # run_purity off, so it must not re-run the per-step producer.
        write_pre_apply_audit_checkpoint(
            plan, path, ctx, SimpleNamespace(name="p"),
            audit_recs=[], budget={},
            bundle_status=_hoisted_bundle(plan, path, tmp_repo.root)[0],
        )
        assert len(calls) == 1

    def test_run_deterministic_checks_passes_completeness_stage_and_no_invoker(
        self, tmp_repo, monkeypatch
    ) -> None:
        # The no-claude guarantee: completeness invokes the advisor at the
        # ``completeness`` stage with ``invoker=None``.
        import plan_tool.granularity

        seen: dict = {}

        def fake(plan, *, stage, evidence, invoker=None):
            seen["stage"] = stage
            seen["invoker"] = invoker
            return []

        monkeypatch.setattr(plan_tool.granularity, "assess_granularity", fake)
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        _run_deterministic_checks(plan, path, ctx, plan_name="p", quiet=True)
        assert seen["stage"] == "completeness"
        assert seen["invoker"] is None

    def test_granularity_recs_excluded_from_deterministic_count(
        self, tmp_repo, monkeypatch, capsys
    ) -> None:
        # A granularity-only plan (clean well-formedness) keeps the
        # deterministic finding count at 0 — advisory smells don't inflate it.
        import plan_tool.review

        monkeypatch.setattr(
            plan_tool.review, "collect_smell_findings", lambda *a, **k: []
        )
        plan, path = _write_and_parse(tmp_repo, _GRANULARITY_SPLIT_STEPS)
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        report = _run_deterministic_checks(
            plan, path, ctx, plan_name="p", quiet=False
        )
        assert report.smell_recs  # the real advisor tripped on the mixed title
        assert all(r.source.startswith("granularity-") for r in report.smell_recs)
        assert "0 finding(s)" in capsys.readouterr().err

    def test_deterministic_report_constructs_without_smell_recs(self) -> None:
        # The seven prior fields with no ``smell_recs`` builds fine (default
        # empty), proving ``_empty_det()`` stays valid.
        report = _DeterministicReport(
            path_style_hint=None,
            dep_issues=[],
            body_issues=[],
            detail_cov_issues=[],
            detail_body_issues=[],
            files_coh_issues=[],
            lessons_issues=[],
        )
        assert report.smell_recs == []

    def test_collect_purity_split_reuses_cache_on_hit(
        self, tmp_repo, monkeypatch
    ) -> None:
        # A matching cache entry serves its cached medium granularity-split
        # verdict and skips the Claude producer entirely (read-through path).
        import plan_tool.detail
        from plan_tool.fingerprint import compute_purity_cache_key
        from plan_tool.purity_cache import (
            PurityCache,
            PurityCacheEntry,
            purity_cache_path,
            save_purity_cache,
        )

        plan, path = _write_plan_with_detail(tmp_repo)
        step = plan.steps[0]
        key, comps = compute_purity_cache_key(plan, path, step, tmp_repo.root)
        cached = _mixed_step_rec(step_id=step.id)
        slug = slug_from_filename(path)
        entry = PurityCacheEntry(
            step_id=step.id,
            cache_key=key,
            detail_hash=comps.detail_hash,
            all_files_fingerprint=comps.all_files_fingerprint,
            change_type=comps.change_type,
            depends_on=list(comps.depends_on),
            purity_verdict_logic_version=comps.logic_version,
            detail_relpath=step.detail,
            findings=[cached],
            impl_tests_text="",
            checked_at="2026-07-18T00:00:00Z",
        )
        save_purity_cache(
            purity_cache_path(tmp_repo.root, slug),
            PurityCache(plan_slug=slug, entries={step.id: entry}),
        )
        calls: list = []
        monkeypatch.setattr(
            plan_tool.detail,
            "collect_detail_quality_findings",
            lambda *a, **k: (calls.append(k), ([], True))[1],
        )
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        report = _run_deterministic_checks(
            plan, path, ctx, plan_name="p", quiet=True, run_purity=True
        )
        medium = [
            r for r in report.smell_recs
            if r.source == "granularity-split" and r.severity == "medium"
        ]
        assert len(medium) == 1
        assert medium[0].purity_verdict_provenance == "exact-cache"
        assert calls == []  # served from cache — no Claude producer call

    def test_collect_purity_split_misses_and_writes_back(
        self, tmp_repo, monkeypatch
    ) -> None:
        # No matching entry: the audit path calls the (patched) producer and
        # writes the fresh purity verdict back to the store.
        import plan_tool.detail
        from plan_tool.purity_cache import load_purity_cache, purity_cache_path

        mixed = _mixed_step_rec(step_id=1)
        monkeypatch.setattr(
            plan_tool.detail,
            "collect_detail_quality_findings",
            lambda *a, **k: ([mixed], True),
        )
        plan, path = _write_plan_with_detail(tmp_repo)
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        report = _run_deterministic_checks(
            plan, path, ctx, plan_name="p", quiet=True, run_purity=True
        )
        assert any(
            r.id == mixed.id and r.purity_verdict_provenance == "fresh"
            for r in report.smell_recs
        )
        cache = load_purity_cache(
            purity_cache_path(tmp_repo.root, slug_from_filename(path))
        )
        assert cache.entries[1].findings == [mixed]

    def test_collect_purity_split_failed_scan_emits_coverage_error(
        self, tmp_repo, monkeypatch
    ) -> None:
        # A failed purity scan (succeeded=False, empty findings) must not look
        # like a clean empty verdict — the audit emits a stable high
        # purity-scan-failed coverage error (blocking bucket, not smell).
        import plan_tool.detail
        from plan_tool.cli.completeness_phases import PURITY_SCAN_FAILED_SOURCE

        monkeypatch.setattr(
            plan_tool.detail,
            "collect_detail_quality_findings",
            lambda *a, **k: ([], False),
        )
        plan, path = _write_plan_with_detail(tmp_repo)
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        report = _run_deterministic_checks(
            plan, path, ctx, plan_name="p", quiet=True, run_purity=True
        )
        failed = [
            r for r in report.purity_coverage_recs
            if r.source == PURITY_SCAN_FAILED_SOURCE
        ]
        assert len(failed) == 1
        assert failed[0].severity == "high"
        assert failed[0].step_id == plan.steps[0].id
        assert not any(
            r.source == PURITY_SCAN_FAILED_SOURCE for r in report.smell_recs
        )
        # Stable fingerprint across rounds (same step → same id).
        report2 = _run_deterministic_checks(
            plan, path, ctx, plan_name="p", quiet=True, run_purity=True
        )
        failed2 = [
            r for r in report2.purity_coverage_recs
            if r.source == PURITY_SCAN_FAILED_SOURCE
        ]
        assert failed2[0].id == failed[0].id
        assert _completeness_has_blocking_findings(
            path_style_hint=None,
            dep_issues=[],
            body_issues=[],
            detail_cov_issues=[],
            detail_body_issues=[],
            lessons_issues=[],
            purity_coverage_recs=failed,
            audit_stage=STAGE_DETAIL,
            data_contract_recs=[],
            self_consistency_recs=[],
        ) is True

    def test_partial_mixed_verdict_skips_failed_advisory(
        self, tmp_repo, monkeypatch
    ) -> None:
        # Truncated reply: Structural MIXED-STEP lifted, ## Findings missing
        # → succeeded=False but a medium verdict exists. Coverage advisory
        # must not claim "no MIXED-STEP verdict" beside that split.
        import plan_tool.detail
        from plan_tool.cli.completeness_phases import PURITY_SCAN_FAILED_SOURCE

        mixed = _mixed_step_rec(step_id=1)
        monkeypatch.setattr(
            plan_tool.detail,
            "collect_detail_quality_findings",
            lambda *a, **k: ([mixed], False),
        )
        plan, path = _write_plan_with_detail(tmp_repo)
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        report = _run_deterministic_checks(
            plan, path, ctx, plan_name="p", quiet=True, run_purity=True
        )
        medium = [
            r for r in report.smell_recs
            if r.source == "granularity-split" and r.severity == "medium"
        ]
        assert len(medium) == 1
        assert not any(
            r.source == PURITY_SCAN_FAILED_SOURCE for r in report.smell_recs
        )
        assert not any(
            r.source == PURITY_SCAN_FAILED_SOURCE
            for r in report.purity_coverage_recs
        )

    def test_collect_purity_split_quiet_probe_emits_no_failed_advisory(
        self, tmp_repo, monkeypatch
    ) -> None:
        # No detail file → quiet probe (succeeded=False) must stay silent.
        import plan_tool.detail
        from plan_tool.cli.completeness_phases import PURITY_SCAN_FAILED_SOURCE

        monkeypatch.setattr(
            plan_tool.detail,
            "collect_detail_quality_findings",
            lambda *a, **k: ([], False),
        )
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        report = _run_deterministic_checks(
            plan, path, ctx, plan_name="p", quiet=True, run_purity=True
        )
        assert not any(
            r.source == PURITY_SCAN_FAILED_SOURCE for r in report.smell_recs
        )
        assert not any(
            r.source == PURITY_SCAN_FAILED_SOURCE
            for r in report.purity_coverage_recs
        )

    def test_purity_timeout_uses_shell_resolution(self, tmp_repo, monkeypatch) -> None:
        import plan_tool.detail
        import plan_tool.shell as shell
        from plan_tool.cli.completeness_phases import PURITY_CLAUDE_TIMEOUT_S

        seen: list[float | None] = []

        def fake_cached(*args, **kwargs):
            seen.append(shell._effective_subprocess_timeout())
            return [], True

        monkeypatch.setattr(plan_tool.detail, "_cached_purity_findings", fake_cached)
        plan, path = _write_plan_with_detail(tmp_repo)
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        monkeypatch.setenv("PLAN_TOOL_PURITY_SCAN_BUDGET", "0")

        for value, expected in [
            (None, PURITY_CLAUDE_TIMEOUT_S),
            ("1200", 1200.0),
            ("0", None),
            ("nope", None),
        ]:
            if value is None:
                monkeypatch.delenv("PLAN_TOOL_CLAUDE_TIMEOUT", raising=False)
            else:
                monkeypatch.setenv("PLAN_TOOL_CLAUDE_TIMEOUT", value)
            _run_deterministic_checks(
                plan, path, ctx, plan_name="p", quiet=True, run_purity=True
            )
            assert seen.pop() == expected

    def test_purity_timeout_uses_its_phase_setting(self, tmp_repo, monkeypatch) -> None:
        import plan_tool.detail
        import plan_tool.shell as shell

        seen: list[float | None] = []
        monkeypatch.setattr(
            plan_tool.detail,
            "_cached_purity_findings",
            lambda *args, **kwargs: (seen.append(shell._effective_subprocess_timeout()) or ([], True)),
        )
        plan, path = _write_plan_with_detail(tmp_repo)
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        monkeypatch.setenv("PLAN_TOOL_CLAUDE_TIMEOUT", "600")
        monkeypatch.setenv("PLAN_TOOL_PURITY_SCAN_BUDGET", "0")

        for value, expected in [(None, 600.0), ("300", 300.0), ("0", None)]:
            if value is None:
                monkeypatch.delenv("PLAN_TOOL_PURITY_CLAUDE_TIMEOUT", raising=False)
            else:
                monkeypatch.setenv("PLAN_TOOL_PURITY_CLAUDE_TIMEOUT", value)
            _run_deterministic_checks(
                plan, path, ctx, plan_name="p", quiet=True, run_purity=True
            )
            assert seen.pop() == expected

    def test_purity_scan_budget_clamps_and_reports_skipped(
        self, tmp_repo, monkeypatch
    ) -> None:
        import plan_tool.detail
        import plan_tool.shell as shell
        from plan_tool.cli import completeness_phases
        from plan_tool.cli.completeness_phases import PURITY_SCAN_SKIPPED_SOURCE

        for step_id in (1, 2):
            detail_path = tmp_repo.root / f"details/{step_id:02d}.md"
            detail_path.parent.mkdir(parents=True, exist_ok=True)
            detail_path.write_text("detail prose\n", encoding="utf-8")
        steps = "".join(
            f"  - id: {step_id}\n    title: Step {step_id}\n    detail: details/{step_id:02d}.md\n"
            for step_id in (1, 2)
        )
        path = tmp_repo.plans_dir / "1-sectioned.md"
        path.write_text(_sectioned_plan_text(f"steps:\n{steps}"), encoding="utf-8")
        plan = parse_plan(path)
        seen: list[float | None] = []
        monkeypatch.setattr(
            plan_tool.detail,
            "_cached_purity_findings",
            lambda *args, **kwargs: (seen.append(shell._effective_subprocess_timeout()) or ([], True)),
        )
        clock = iter([100.0, 100.0, 105.0])
        monkeypatch.setattr(completeness_phases.time, "monotonic", lambda: next(clock))
        monkeypatch.setenv("PLAN_TOOL_PURITY_SCAN_BUDGET", "5")

        report = _run_deterministic_checks(
            plan,
            path,
            SimpleNamespace(repo_root=tmp_repo.root),
            plan_name="p",
            quiet=True,
            run_purity=True,
        )

        assert seen == [5.0]
        skipped = [
            rec
            for rec in report.purity_coverage_recs
            if rec.source == PURITY_SCAN_SKIPPED_SOURCE
        ]
        assert [rec.step_id for rec in skipped] == [2]
        assert skipped[0].severity == "high"

    @pytest.mark.parametrize("budget", ["0", "-1", "not-a-number"])
    def test_disabled_purity_scan_budget_keeps_scanning(
        self, tmp_repo, monkeypatch, budget
    ) -> None:
        import plan_tool.detail
        from plan_tool.cli import completeness_phases
        from plan_tool.cli.completeness_phases import PURITY_SCAN_SKIPPED_SOURCE

        for step_id in (1, 2):
            detail_path = tmp_repo.root / f"details/{step_id:02d}.md"
            detail_path.parent.mkdir(parents=True, exist_ok=True)
            detail_path.write_text("detail prose\n", encoding="utf-8")
        steps = "".join(
            f"  - id: {step_id}\n    title: Step {step_id}\n    detail: details/{step_id:02d}.md\n"
            for step_id in (1, 2)
        )
        path = tmp_repo.plans_dir / "1-sectioned.md"
        path.write_text(_sectioned_plan_text(f"steps:\n{steps}"), encoding="utf-8")
        plan = parse_plan(path)
        calls: list[object] = []
        monkeypatch.setattr(
            plan_tool.detail,
            "_cached_purity_findings",
            lambda *args, **kwargs: (calls.append(args[1]) or ([], True)),
        )
        monkeypatch.setenv("PLAN_TOOL_PURITY_SCAN_BUDGET", budget)

        recs = completeness_phases._collect_purity_split_findings(
            plan, path, SimpleNamespace(repo_root=tmp_repo.root), plan_name="p"
        )

        assert len(calls) == 2
        assert not any(rec.source == PURITY_SCAN_SKIPPED_SOURCE for rec in recs)


# --- Deterministic-detector registry ---------------------------------------
#
# Two guards keep the registry the battery's only dispatch path. The
# characterization corpus below is the behavioural half: it pins the whole
# ``_DeterministicReport`` — every bucket, in order — for a fixture set that
# exercises each detector, so a detector dropped from the registry fails here.
# ``TestDeterministicDetectorRegistry`` holds the source-level half.


def _write_canonical_only_detail_plan(tmp_repo):
    """One step whose ``detail:`` pointer is unset while its canonical bundle
    file is on disk — trips the detail-coverage and detail-body arms together."""
    steps = "steps:\n  - id: 1\n    title: Only step\n"
    plan, path = _write_and_parse(tmp_repo, steps)
    bundle = tmp_repo.plans_dir / "plan-details" / "sectioned"
    bundle.mkdir(parents=True)
    (bundle / "01-only-step.md").write_text(
        "# Step 1\n\n## Summary\n\nonly a summary\n", encoding="utf-8"
    )
    return plan, path


def _write_footprint_plan(tmp_repo):
    """One step creating a deliverable nothing consumes (its detail defers the
    wiring) under an acceptance criterion naming a path no step delivers —
    exercises the plan-footprint detectors in both fan-outs at once."""
    detail_rel = "details/01.md"
    detail_path = tmp_repo.root / detail_rel
    detail_path.parent.mkdir(parents=True, exist_ok=True)
    detail_path.write_text(
        "## Summary\n\nShip the primitive.\n\n"
        "## Deferred\n\nWiring `pkg/orphan_widget.py` into its caller is "
        "deferred to a later plan.\n",
        encoding="utf-8",
    )
    body = "\n".join(
        "## Acceptance criteria\n\n- `pkg/never_built.py` exists.\n"
        if name == "Acceptance criteria"
        else f"## {name}\n\nReal content for the {name} section.\n"
        for name in PLAN_BODY_SECTIONS
    )
    path = tmp_repo.plans_dir / "1-sectioned.md"
    path.write_text(
        "---\n"
        "title: Sectioned Plan\n"
        "status: planning\n"
        "priority: low\n"
        "steps:\n"
        "  - id: 1\n"
        "    title: Ship the widget\n"
        "    creates:\n"
        "      - pkg/orphan_widget.py\n"
        f"    detail: {detail_rel}\n"
        "---\n"
        "# Sectioned Plan\n\n"
        f"{body}",
        encoding="utf-8",
    )
    return parse_plan(path), path


def _write_missing_body_plan(tmp_repo):
    """A plan with no body sections at all and a declared file that isn't on
    disk — the body-completeness / lessons / file-existence arms."""
    path = tmp_repo.plans_dir / "1-sectioned.md"
    path.write_text(
        "---\n"
        "title: Sectioned Plan\n"
        "status: planning\n"
        "priority: low\n"
        "steps:\n"
        "  - id: 1\n"
        "    title: Only step\n"
        "    files: [src/nowhere.py]\n"
        "---\n"
        "# Sectioned Plan\n",
        encoding="utf-8",
    )
    return parse_plan(path), path


def _write_concept_coverage_plan(tmp_repo):
    """A plan carrying an unowned concept record — the one fixture whose
    finding is minted by a *smell* detector and then partitioned onto the
    self-consistency bucket by source."""
    from plan_tool.concept_tree import (
        ConceptNode,
        ConceptTree,
        concept_id,
        save_concepts,
    )
    from plan_tool.review_persistence import compute_plan_fingerprint

    plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
    save_concepts(
        path,
        ConceptTree(
            plan_slug="sectioned",
            plan_fingerprint=compute_plan_fingerprint(path),
            concepts=[
                ConceptNode(
                    id=concept_id("Missing owner", []),
                    title="Missing owner",
                    decision="include",
                    review_state="approved",
                )
            ],
        ),
    )
    return plan, path


# Each entry exercises a different slice of the battery; together they reach
# every bucket ``_DeterministicReport`` carries.
_DETECTOR_CORPUS = (
    ("clean", lambda repo: _write_and_parse(repo, _CLEAN_STEPS)),
    (
        "granularity-split",
        lambda repo: _write_and_parse(repo, _GRANULARITY_SPLIT_STEPS),
    ),
    ("canonical-only-detail", _write_canonical_only_detail_plan),
    ("input-contract", _write_input_contract_plan),
    ("footprint", _write_footprint_plan),
    ("missing-body", _write_missing_body_plan),
    ("concept-coverage", _write_concept_coverage_plan),
)


def _characterize_det(report) -> dict:
    """Render a ``_DeterministicReport`` field by field, order included.

    The comparison surface for the registry refactor: issue records go through
    ``repr`` and recommendations through their identifying tuple, so a detector
    that moved, dropped, or duplicated a finding shows up as a diff."""
    def _issues(items) -> list[str]:
        return [repr(i) for i in items]

    def _recs(items) -> list[list]:
        return [[r.source, r.severity, r.step_id, r.id, r.title] for r in items]

    hint = report.path_style_hint
    return {
        # ``repo_root`` is left out: it is the (tmp) repo path, not a finding.
        "path_style_hint": None
        if hint is None
        else [hint.missing_count, hint.total, hint.ratio, list(hint.examples)],
        "dep_issues": _issues(report.dep_issues),
        "body_issues": _issues(report.body_issues),
        "detail_cov_issues": _issues(report.detail_cov_issues),
        "detail_body_issues": _issues(report.detail_body_issues),
        "files_coh_issues": _issues(report.files_coh_issues),
        "lessons_issues": _issues(report.lessons_issues),
        "smell_recs": _recs(report.smell_recs),
        "self_consistency_recs": _recs(report.self_consistency_recs),
        "data_contract_recs": _recs(report.data_contract_recs),
        "data_contract_payloads": sorted(report.data_contract_payloads),
        "purity_coverage_recs": _recs(report.purity_coverage_recs),
    }


def _characterize_corpus(tmp_repo) -> dict:
    """Run the battery over every corpus fixture and return its rendering."""
    out: dict = {}
    for name, build in _DETECTOR_CORPUS:
        # One repo root per fixture: the corpus reuses plan filenames, and the
        # footprint/file-existence detectors resolve paths against the root.
        root = tmp_repo.root / name
        plans_dir = root / "plans"
        plans_dir.mkdir(parents=True, exist_ok=True)
        scoped = SimpleNamespace(root=root, plans_dir=plans_dir)
        plan, path = build(scoped)
        report = _run_deterministic_checks(
            plan,
            path,
            SimpleNamespace(repo_root=scoped.root),
            plan_name="p",
            quiet=True,
        )
        out[name] = _characterize_det(report)
    return out


def _characterization_digest(rendering: dict) -> str:
    """A stable digest of one fixture's field-by-field rendering."""
    payload = json.dumps(rendering, sort_keys=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


# The readable half of the characterization: which buckets each fixture fills
# and how full. A diff here names the bucket whose detector moved.
# No fixture declares an ``intent``, so every one gains the same two
# ``intent-presence`` findings on the *blocking* bucket — the uniform ``+2``
# across fixtures with different step counts is the readable proof that the cap
# is per plan, and it is what empties ``smell_recs`` for the fixtures whose only
# smells were the intent pair.
_CORPUS_BUCKET_COUNTS = {
    "clean": {"self_consistency_recs": 2},
    "granularity-split": {"smell_recs": 2, "self_consistency_recs": 2},
    "canonical-only-detail": {
        "detail_cov_issues": 1,
        "detail_body_issues": 6,
        "self_consistency_recs": 2,
    },
    "input-contract": {
        "files_coh_issues": 1,
        "self_consistency_recs": 2,
        "data_contract_recs": 1,
        "data_contract_payloads": 1,
    },
    "footprint": {
        "detail_body_issues": 6,
        "smell_recs": 1,
        "self_consistency_recs": 3,
    },
    "missing-body": {
        "path_style_hint": 1,
        "body_issues": 10,
        "self_consistency_recs": 2,
    },
    "concept-coverage": {"self_consistency_recs": 3},
}

# The exact half: a digest over the full rendering, so a finding that changed
# content, id, or position — not just count — fails too. It renders issue
# records through ``repr``; carrier shape changes affect the digest while
# the readable bucket counts pin detector membership.
_CORPUS_DIGESTS = {
    "clean": "240cebc1535841cb",
    "granularity-split": "fa5fd0fa57ce826e",
    "canonical-only-detail": "d6c8cda65007e22f",
    "input-contract": "c835daa372aebc71",
    "footprint": "8b222e03aa09475c",
    "missing-body": "c0d06cc7d11ee753",
    "concept-coverage": "f3c626d7730d63c1",
}


def _corpus_bucket_counts(rendering: dict) -> dict:
    """The non-empty buckets of one fixture's rendering, by size."""
    counts: dict = {}
    for bucket, value in rendering.items():
        if bucket == "path_style_hint":
            if value is not None:
                counts[bucket] = 1
        elif value:
            counts[bucket] = len(value)
    return counts


def test_deterministic_report_characterization(tmp_repo) -> None:
    """The battery's whole ``_DeterministicReport``, pinned field by field.

    Pinned before the detector registry landed and unchanged by it: the
    registry only changes *how* the detectors are reached, never what they
    find. An entry dropped from the registry fails here even though the
    source-level guard would still pass."""
    corpus = _characterize_corpus(tmp_repo)
    assert set(corpus) == set(_CORPUS_DIGESTS)
    assert {
        name: _corpus_bucket_counts(rendering)
        for name, rendering in corpus.items()
    } == _CORPUS_BUCKET_COUNTS
    for name, rendering in corpus.items():
        assert _characterization_digest(rendering) == _CORPUS_DIGESTS[name], (
            f"{name} rendering changed:\n"
            + json.dumps(rendering, indent=1)
        )


# Every detector the battery runs, in dispatch order. Nineteen entries: the
# ten plan-level well-formedness ones (``check_input_contract_references``
# contributes two, its plan-body arm and its per-step arm), ``granularity`` and
# ``data-contract-drift`` (owned by the phase module, not ``review``), the six
# inside ``collect_smell_findings``, and the one inside
# ``_self_consistency_from_smells``.
_REGISTRY_KEYS = (
    "file-existence",
    "path-style-mismatch",
    "deps",
    "body-completeness",
    "detail-coverage",
    "detail-body-completeness",
    "files-coherence",
    "lessons-coverage",
    "granularity",
    "feature-refs",
    "suppression-shape",
    "self-referential-features",
    "claim-vs-delivery",
    "concept-coverage",
    "intent-presence",
    "orphaned-deliverable",
    "data-contract-drift",
    "input-contract-references-plan",
    "input-contract-references-steps",
)

# A called name shaped like a detector. Deliberately broad: the guard's job is
# to fail on a *newly added* detector that skipped the registry, and a new one
# will be named like its siblings.
_DETECTOR_NAME_RE = re.compile(
    r"_?(check|detect|validate|assess|collect)_[a-z0-9_]+"
)

# Detector-shaped calls the guarded functions may still make directly, each
# with the reason it is not a registry entry.
_DIRECT_CALL_ALLOWLIST = {
    # The smell group's own registry dispatcher — a fan-out, not a detector.
    "collect_smell_findings",
    "_collect_purity_split_findings",
}

# The battery plus every fan-out it dispatches: the functions that must reach
# detectors only through the registry. Deliberately not a count — a stated
# number goes stale the moment a fan-out is added, and a maintainer who reads
# it as the invariant skips registering theirs.
_GUARDED_FANOUTS = (
    ("plan_tool.cli.completeness_phases", "_run_deterministic_checks"),
    ("plan_tool.review", "collect_smell_findings"),
    ("plan_tool.review", "_self_consistency_from_smells"),
    # The fourth registry-dispatching fan-out. No detector-shaped direct call
    # today, so the entry is green on arrival — it closes the hole rather than
    # reporting one.
    ("plan_tool.review", "collect_self_consistency_findings"),
)


def _direct_detector_calls(source: str, func_name: str) -> set[str]:
    """Detector-shaped names ``func_name`` calls directly in ``source``."""
    target = next(
        node
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.FunctionDef) and node.name == func_name
    )
    called: set[str] = set()
    for node in ast.walk(target):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            name = func.id
        elif isinstance(func, ast.Attribute):
            name = func.attr
        else:
            continue
        if _DETECTOR_NAME_RE.fullmatch(name):
            called.add(name)
    return called


class TestDeterministicDetectorRegistry:
    """The two guards that keep the registry the battery's only dispatch path.

    The source-level guard catches a detector added without being registered;
    ``test_deterministic_report_characterization`` catches one registered
    wrong or dropped. Neither subsumes the other, so both carry a negative
    case proving they can still fail."""

    def test_registry_is_the_only_dispatch_path(self) -> None:
        seen: set[str] = set()
        for module_name, func_name in _GUARDED_FANOUTS:
            source = inspect.getsource(importlib.import_module(module_name))
            called = _direct_detector_calls(source, func_name)
            seen |= called
            unregistered = sorted(called - _DIRECT_CALL_ALLOWLIST)
            assert not unregistered, (
                f"{module_name}:{func_name} calls a detector directly "
                f"instead of through the registry: {unregistered}"
            )
        # The allowlist can't rot either: every exemption must still be live.
        assert _DIRECT_CALL_ALLOWLIST <= seen

    def test_source_guard_fails_on_a_hard_coded_detector_call(self) -> None:
        # The negative case: a detector wired in by hand rather than
        # registered. Without this the guard could rot into a tautology.
        injected = (
            "def collect_smell_findings(plan, repo_root):\n"
            "    return detect_suppression_shape(plan, repo_root)\n"
        )
        assert _direct_detector_calls(injected, "collect_smell_findings") == {
            "detect_suppression_shape"
        }
        assert not (
            _direct_detector_calls(injected, "collect_smell_findings")
            <= _DIRECT_CALL_ALLOWLIST
        )

    def test_registry_covers_the_battery(self) -> None:
        registry = deterministic_detector_registry()
        assert registry.keys == _REGISTRY_KEYS
        assert len(registry) == 19

    def test_battery_dispatches_exactly_the_registry(
        self, tmp_repo, monkeypatch
    ) -> None:
        # The composed table can't drift from what actually runs: one audit
        # dispatches every registry key, once, in the declared order.
        from plan_tool.review import DetectorRegistry

        dispatched: list[str] = []
        run_all = DetectorRegistry.run_all

        def spy(self, det_ctx):
            dispatched.extend(self.keys)
            return run_all(self, det_ctx)

        monkeypatch.setattr(DetectorRegistry, "run_all", spy)
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        _run_deterministic_checks(
            plan,
            path,
            SimpleNamespace(repo_root=tmp_repo.root),
            plan_name="p",
            quiet=True,
        )
        assert tuple(dispatched) == _REGISTRY_KEYS

    def test_test_strategy_alignment_stays_out_of_the_battery(
        self, tmp_repo, monkeypatch
    ) -> None:
        # It belongs to ``review.collect_deterministic_findings`` (the
        # reconcile/review lane), so no battery entry may reach it.
        import plan_tool.review

        def _boom(*a, **k):
            raise AssertionError("check_test_strategy_alignment ran in the battery")

        monkeypatch.setattr(
            plan_tool.review, "check_test_strategy_alignment", _boom
        )
        assert "test-strategy" not in " ".join(_REGISTRY_KEYS)
        _characterize_corpus(tmp_repo)

    def test_dropping_a_registry_entry_breaks_characterization(
        self, tmp_repo, monkeypatch
    ) -> None:
        # The behavioural guard's negative case: remove ``concept-coverage``
        # from the smell table and the pinned rendering no longer reproduces.
        import plan_tool.review
        from plan_tool.review import DetectorRegistry

        monkeypatch.setattr(
            plan_tool.review,
            "SMELL_DETECTORS",
            DetectorRegistry(
                tuple(
                    entry
                    for entry in plan_tool.review.SMELL_DETECTORS
                    if entry.key != "concept-coverage"
                )
            ),
        )
        rendering = _characterize_corpus(tmp_repo)["concept-coverage"]
        assert [r[0] for r in rendering["self_consistency_recs"]] == [
            "intent-presence",
            "intent-presence",
        ]
        assert (
            _characterization_digest(rendering)
            != _CORPUS_DIGESTS["concept-coverage"]
        )

    def test_shared_detectors_run_once_per_audit(
        self, tmp_repo, monkeypatch
    ) -> None:
        # ``suppression-shape`` and ``concept-coverage`` feed both the advisory
        # smell bucket and (by source) the self-consistency bucket; the
        # partition must reuse their output, never recompute it.
        import plan_tool.review

        calls: dict[str, int] = {}

        def _counted(name):
            real = getattr(plan_tool.review, name)

            def wrapper(*args, **kwargs):
                calls[name] = calls.get(name, 0) + 1
                return real(*args, **kwargs)

            monkeypatch.setattr(plan_tool.review, name, wrapper)

        for detector in (
            "detect_suppression_shape",
            "check_concept_coverage",
            "detect_orphaned_deliverable",
        ):
            _counted(detector)

        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        _run_deterministic_checks(
            plan,
            path,
            SimpleNamespace(repo_root=tmp_repo.root),
            plan_name="p",
            quiet=True,
        )
        assert calls == {
            "detect_suppression_shape": 1,
            "check_concept_coverage": 1,
            "detect_orphaned_deliverable": 1,
        }


class TestPurityCacheMissGrading:
    """Step 4 (BACKLOG #144): grade a purity cache *miss* — a trivial edit
    (below the 0.5% Impl/Tests floor, no frontmatter/identity change) reuses the
    cached verdict with an info advisory and no Claude; a genuine miss (above the
    floor, any component change, or cold) re-computes through the producer."""

    def _patched_producer(self, monkeypatch, findings):
        """Patch the purity producer to a call-counting stub returning
        ``(findings, True)``; return the call list."""
        import plan_tool.detail

        calls: list = []
        monkeypatch.setattr(
            plan_tool.detail,
            "collect_detail_quality_findings",
            lambda *a, **k: (calls.append(k), (findings, True))[1],
        )
        return calls

    def _run(self, tmp_repo, plan, path):
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        return _run_deterministic_checks(
            plan, path, ctx, plan_name="p", quiet=True, run_purity=True
        )

    def test_audit_miss_below_floor_reuses_verdict_no_claude(
        self, tmp_repo, monkeypatch
    ) -> None:
        # Below the floor with matching components: reuse the cached medium
        # granularity-split verdict, add one info reuse advisory, no producer.
        body = _detail_with_impl_tests()
        plan, path = _write_plan_with_detail(tmp_repo, detail_body=body)
        step = plan.steps[0]
        from plan_tool.detail import _impl_tests_section_text

        cached = dataclasses.replace(
            _mixed_step_rec(step_id=step.id), confidence="supported"
        )
        _seed_purity_entry(
            tmp_repo, plan, path, step,
            impl_tests_text=_impl_tests_section_text(body),
            findings=[cached],
        )
        calls = self._patched_producer(monkeypatch, [])
        report = self._run(tmp_repo, plan, path)
        reused = [
            r for r in report.smell_recs
            if r.source == "granularity-split" and r.severity == "medium"
        ]
        assert len(reused) == 1
        assert reused[0].purity_verdict_provenance == "below-floor-reuse"
        assert reused[0].confidence == "supported"
        advisories = [
            r for r in report.smell_recs
            if r.source == "purity-reuse-advisory"
        ]
        assert len(advisories) == 1
        assert advisories[0].severity == "info"
        assert advisories[0].purity_verdict_provenance is None
        assert advisories[0].confidence == "limited"
        assert calls == []  # reused — no Claude producer call

    def test_audit_miss_empty_impl_tests_recomputes_not_reuse(
        self, tmp_repo, monkeypatch
    ) -> None:
        # Fail-safe: when the Implementation/Tests text is unmeasurable (no such
        # sections resolved, e.g. a heading variant), an empty↔empty compare
        # would score 0% and wrongly reuse. The grader must instead treat it as a
        # genuine miss and call the producer (code-review stale-hit finding).
        body = "## Summary\n\nsummary only, no Implementation/Tests sections\n"
        plan, path = _write_plan_with_detail(tmp_repo, detail_body=body)
        step = plan.steps[0]
        _seed_purity_entry(
            tmp_repo, plan, path, step,
            impl_tests_text="",  # stored baseline also empty
            findings=[_mixed_step_rec(step_id=step.id)],
        )
        calls = self._patched_producer(monkeypatch, [])
        self._run(tmp_repo, plan, path)
        assert calls != []  # unmeasurable → recomputed, not reused

    def test_grade_absolute_floor_catches_large_step_small_proportion(
        self,
    ) -> None:
        # Absolute-floor guard: on a very large step a real (>120-char) mixing
        # edit can score under the 0.5% proportional floor; the absolute cap must
        # still grade it a genuine miss. A truly tiny edit stays reusable.
        from plan_tool.cli.completeness_phases import _grade_purity_cache_miss
        from plan_tool.fingerprint import PurityKeyComponents
        from plan_tool.purity_cache import PurityCacheEntry
        from plan_tool.schema import Step

        base = "x" * 25000
        comps = PurityKeyComponents(
            detail_hash="d", all_files_fingerprint="a",
            change_type="feature", depends_on=(), logic_version=1,
        )

        def _entry(text: str) -> PurityCacheEntry:
            return PurityCacheEntry(
                step_id=1, cache_key="stale", detail_hash="d",
                all_files_fingerprint="a", change_type="feature", depends_on=[],
                purity_verdict_logic_version=1, detail_relpath="d.md",
                findings=[], impl_tests_text=text, checked_at="2026-01-01T00:00:00Z",
            )

        step = Step(id=1, title="Big")
        common = dict(
            step=step, current_components=comps, current_detail_relpath="d.md"
        )
        # >120-char change, but <0.5% of the 25k base → absolute floor fires.
        big = _grade_purity_cache_miss(
            entry=_entry(base), current_impl_tests_text=base + "y" * 130, **common
        )
        assert big is None  # genuine miss despite the small proportion
        # A tiny (<120-char, <0.5%) change still reuses.
        tiny = _grade_purity_cache_miss(
            entry=_entry(base), current_impl_tests_text=base + "y" * 8, **common
        )
        assert tiny is not None

    def test_audit_miss_above_floor_calls_claude(
        self, tmp_repo, monkeypatch
    ) -> None:
        # Impl/Tests changed wholesale (>= floor): a genuine miss re-computes
        # via the producer and writes the fresh verdict back.
        from plan_tool.purity_cache import load_purity_cache, purity_cache_path

        body = _detail_with_impl_tests(impl="A B C D E F G", tests="H I J K")
        plan, path = _write_plan_with_detail(tmp_repo, detail_body=body)
        step = plan.steps[0]
        _seed_purity_entry(
            tmp_repo, plan, path, step,
            impl_tests_text="totally different baseline text nothing shared zzz",
            findings=[],
        )
        fresh = _mixed_step_rec(step_id=step.id)
        calls = self._patched_producer(monkeypatch, [fresh])
        report = self._run(tmp_repo, plan, path)
        assert any(
            r.id == fresh.id and r.purity_verdict_provenance == "fresh"
            for r in report.smell_recs
        )
        assert not any(
            r.source == "purity-reuse-advisory" for r in report.smell_recs
        )
        assert len(calls) == 1  # genuine miss — producer called
        cache = load_purity_cache(
            purity_cache_path(tmp_repo.root, slug_from_filename(path))
        )
        assert cache.entries[step.id].findings == [fresh]

    def test_audit_miss_change_type_flip_calls_claude(
        self, tmp_repo, monkeypatch
    ) -> None:
        # A below-floor Impl/Tests diff but a stored change_type differing from
        # the current step: the frontmatter OR grades the miss genuine.
        body = _detail_with_impl_tests()
        plan, path = _write_plan_with_detail(tmp_repo, detail_body=body)
        step = plan.steps[0]
        from plan_tool.detail import _impl_tests_section_text

        _seed_purity_entry(
            tmp_repo, plan, path, step,
            impl_tests_text=_impl_tests_section_text(body),
            change_type="refactor",  # differs from the current step
        )
        calls = self._patched_producer(monkeypatch, [_mixed_step_rec(step.id)])
        self._run(tmp_repo, plan, path)
        assert len(calls) == 1

    def test_audit_miss_depends_on_change_calls_claude(
        self, tmp_repo, monkeypatch
    ) -> None:
        # A below-floor diff but a stored depends_on differing: genuine miss.
        body = _detail_with_impl_tests()
        plan, path = _write_plan_with_detail(tmp_repo, detail_body=body)
        step = plan.steps[0]
        from plan_tool.detail import _impl_tests_section_text

        _seed_purity_entry(
            tmp_repo, plan, path, step,
            impl_tests_text=_impl_tests_section_text(body),
            depends_on=[2],  # differs from the current step's []
        )
        calls = self._patched_producer(monkeypatch, [_mixed_step_rec(step.id)])
        self._run(tmp_repo, plan, path)
        assert len(calls) == 1

    def test_audit_miss_all_files_change_recomputes_under_below_floor_diff(
        self, tmp_repo, monkeypatch
    ) -> None:
        # Round-3 HIGH guard: the detail body is byte-identical (~0% diff), but
        # the stored all_files_fingerprint differs (a files:/creates: source
        # edit). Checking the component — not just the diff — forces re-check.
        body = _detail_with_impl_tests()
        plan, path = _write_plan_with_detail(tmp_repo, detail_body=body)
        step = plan.steps[0]
        from plan_tool.detail import _impl_tests_section_text

        _seed_purity_entry(
            tmp_repo, plan, path, step,
            impl_tests_text=_impl_tests_section_text(body),
            all_files_fingerprint="a-different-source-fingerprint",
        )
        calls = self._patched_producer(monkeypatch, [_mixed_step_rec(step.id)])
        report = self._run(tmp_repo, plan, path)
        assert len(calls) == 1  # re-computed, never reused
        assert not any(
            r.source == "purity-reuse-advisory" for r in report.smell_recs
        )

    def test_audit_miss_logic_version_bump_recomputes(
        self, tmp_repo, monkeypatch
    ) -> None:
        # A stored logic version older than the current constant invalidates
        # reuse even under a below-floor diff.
        body = _detail_with_impl_tests()
        plan, path = _write_plan_with_detail(tmp_repo, detail_body=body)
        step = plan.steps[0]
        from plan_tool.detail import _impl_tests_section_text
        from plan_tool.fingerprint import PURITY_VERDICT_LOGIC_VERSION

        _seed_purity_entry(
            tmp_repo, plan, path, step,
            impl_tests_text=_impl_tests_section_text(body),
            purity_verdict_logic_version=PURITY_VERDICT_LOGIC_VERSION - 1,
        )
        calls = self._patched_producer(monkeypatch, [_mixed_step_rec(step.id)])
        self._run(tmp_repo, plan, path)
        assert len(calls) == 1

    def test_audit_below_floor_renumber_does_not_reuse(
        self, tmp_repo, monkeypatch
    ) -> None:
        # Round-4 renumber guard: a stored detail_relpath differing from the
        # current step's (a renumber reassigned the id) grades genuine even with
        # every other component matching and a below-floor diff.
        body = _detail_with_impl_tests()
        plan, path = _write_plan_with_detail(tmp_repo, detail_body=body)
        step = plan.steps[0]
        from plan_tool.detail import _impl_tests_section_text

        _seed_purity_entry(
            tmp_repo, plan, path, step,
            impl_tests_text=_impl_tests_section_text(body),
            detail_relpath="details/99-was-a-different-step.md",
            findings=[_mixed_step_rec(step.id)],  # the *old* step's verdict
        )
        calls = self._patched_producer(monkeypatch, [])
        report = self._run(tmp_repo, plan, path)
        assert len(calls) == 1  # re-computed, old verdict never leaked
        assert not any(
            r.source == "purity-reuse-advisory" for r in report.smell_recs
        )

    def test_audit_reuse_advisory_id_is_stable_across_passes(
        self, tmp_repo, monkeypatch
    ) -> None:
        # Two reuses with *different* changed fractions (M%) mint advisories with
        # the same id — the id keys on a stable per-step token, not the M% body.
        # Raise the floor so meaningfully-different-magnitude edits still reuse.
        import plan_tool.cli.completeness_phases as phases
        from plan_tool.cli.completeness_phases import _grade_purity_cache_miss
        from plan_tool.fingerprint import PurityKeyComponents, PURITY_VERDICT_LOGIC_VERSION
        from plan_tool.purity_cache import PurityCacheEntry

        monkeypatch.setattr(phases, "PURITY_REUSE_FLOOR", 0.9)
        comps = PurityKeyComponents(
            detail_hash="h",
            all_files_fingerprint="fp",
            change_type="",
            depends_on=(),
            logic_version=PURITY_VERDICT_LOGIC_VERSION,
        )
        entry = PurityCacheEntry(
            step_id=3,
            cache_key="stale",
            detail_hash="h",
            all_files_fingerprint="fp",
            change_type="",
            depends_on=[],
            purity_verdict_logic_version=PURITY_VERDICT_LOGIC_VERSION,
            detail_relpath="d.md",
            findings=[],
            impl_tests_text="the original baseline text",
            checked_at="2026-07-18T00:00:00Z",
        )
        step = SimpleNamespace(id=3)
        first = _grade_purity_cache_miss(
            entry=entry, step=step, current_components=comps,
            current_detail_relpath="d.md",
            current_impl_tests_text="the original baseline text plus a bit",
        )
        second = _grade_purity_cache_miss(
            entry=entry, step=step, current_components=comps,
            current_detail_relpath="d.md",
            current_impl_tests_text="an almost entirely rewritten body here now",
        )
        adv1 = [r for r in first if r.source == "purity-reuse-advisory"][0]
        adv2 = [r for r in second if r.source == "purity-reuse-advisory"][0]
        assert adv1.id == adv2.id  # id stable despite differing M%
        assert adv1.body != adv2.body  # body carries the varying M%

    def test_audit_below_floor_reuse_does_not_advance_baseline(
        self, tmp_repo, monkeypatch
    ) -> None:
        # A below-floor reuse writes nothing: the stored entry (cache_key and
        # impl_tests_text baseline) is unchanged after the audit.
        from plan_tool.purity_cache import load_purity_cache, purity_cache_path

        body = _detail_with_impl_tests()
        plan, path = _write_plan_with_detail(tmp_repo, detail_body=body)
        step = plan.steps[0]
        from plan_tool.detail import _impl_tests_section_text

        baseline = _impl_tests_section_text(body)
        _seed_purity_entry(
            tmp_repo, plan, path, step, impl_tests_text=baseline,
        )
        self._patched_producer(monkeypatch, [])
        self._run(tmp_repo, plan, path)
        cache = load_purity_cache(
            purity_cache_path(tmp_repo.root, slug_from_filename(path))
        )
        assert cache.entries[step.id].cache_key == "stale-key-forces-miss"
        assert cache.entries[step.id].impl_tests_text == baseline

    def test_audit_miss_no_entry_calls_claude(
        self, tmp_repo, monkeypatch
    ) -> None:
        # A cold step (no cached entry) is a genuine miss — the producer is
        # called and the verdict written back, not silently skipped/advised.
        from plan_tool.purity_cache import load_purity_cache, purity_cache_path

        body = _detail_with_impl_tests()
        plan, path = _write_plan_with_detail(tmp_repo, detail_body=body)
        step = plan.steps[0]
        fresh = _mixed_step_rec(step.id)
        calls = self._patched_producer(monkeypatch, [fresh])
        report = self._run(tmp_repo, plan, path)
        assert len(calls) == 1
        assert not any(
            r.source == "purity-reuse-advisory" for r in report.smell_recs
        )
        cache = load_purity_cache(
            purity_cache_path(tmp_repo.root, slug_from_filename(path))
        )
        assert cache.entries[step.id].findings == [fresh]

    def test_audit_ratio_uses_changed_fraction_not_similarity(
        self, tmp_repo, monkeypatch
    ) -> None:
        # A near-identical baseline stays below the floor (reuse); a wholesale
        # rewrite goes above (re-compute) — pins the signal as 1 - ratio().
        from plan_tool.detail import _impl_tests_section_text

        # Near-identical: reuse.
        body = _detail_with_impl_tests()
        plan, path = _write_plan_with_detail(tmp_repo, detail_body=body)
        step = plan.steps[0]
        _seed_purity_entry(
            tmp_repo, plan, path, step,
            impl_tests_text=_impl_tests_section_text(body),
        )
        calls = self._patched_producer(monkeypatch, [_mixed_step_rec(step.id)])
        report = self._run(tmp_repo, plan, path)
        assert any(
            r.source == "purity-reuse-advisory" for r in report.smell_recs
        )
        assert calls == []

    def test_audit_reuse_advisory_is_info_and_non_blocking(
        self, tmp_repo, monkeypatch
    ) -> None:
        # The reuse advisory is info-severity and never makes the audit block.
        from plan_tool.cli.completeness_cmd import (
            _completeness_has_blocking_findings,
        )
        from plan_tool.detail import _impl_tests_section_text

        body = _detail_with_impl_tests()
        plan, path = _write_plan_with_detail(tmp_repo, detail_body=body)
        step = plan.steps[0]
        _seed_purity_entry(
            tmp_repo, plan, path, step,
            impl_tests_text=_impl_tests_section_text(body),
        )
        self._patched_producer(monkeypatch, [])
        report = self._run(tmp_repo, plan, path)
        advisory = [
            r for r in report.smell_recs if r.source == "purity-reuse-advisory"
        ][0]
        assert advisory.severity == "info"
        # smell_recs never feed the blocking gate, so no advisory can flip it.
        assert not _completeness_has_blocking_findings(
            path_style_hint=None,
            dep_issues=[],
            body_issues=[],
            detail_cov_issues=[],
            detail_body_issues=[],
            lessons_issues=[],
            audit_stage=STAGE_DETAIL,
            data_contract_recs=[],
            self_consistency_recs=[],
            purity_coverage_recs=[],
        )

    def test_audit_empty_cached_verdict_reuses_as_pure_below_floor(
        self, tmp_repo, monkeypatch
    ) -> None:
        # An entry with findings=[] ("pure") reuses below the floor: advisory
        # only, no split rec, no Claude.
        from plan_tool.detail import _impl_tests_section_text

        body = _detail_with_impl_tests()
        plan, path = _write_plan_with_detail(tmp_repo, detail_body=body)
        step = plan.steps[0]
        _seed_purity_entry(
            tmp_repo, plan, path, step,
            impl_tests_text=_impl_tests_section_text(body),
            findings=[],
        )
        calls = self._patched_producer(monkeypatch, [])
        report = self._run(tmp_repo, plan, path)
        assert calls == []
        assert not any(
            r.source == "granularity-split" for r in report.smell_recs
        )
        assert any(
            r.source == "purity-reuse-advisory" for r in report.smell_recs
        )

    def test_detail_loop_always_calls_claude(
        self, tmp_repo, monkeypatch
    ) -> None:
        # The detail-authoring site (read_through=False, no reuse hook) always
        # reaches the producer even with a would-hit cache entry present.
        import plan_tool.detail
        from plan_tool.fingerprint import compute_purity_cache_key
        from plan_tool.purity_cache import (
            PurityCache,
            PurityCacheEntry,
            purity_cache_path,
            save_purity_cache,
        )

        body = _detail_with_impl_tests()
        plan, path = _write_plan_with_detail(tmp_repo, detail_body=body)
        step = plan.steps[0]
        key, comps = compute_purity_cache_key(plan, path, step, tmp_repo.root)
        slug = slug_from_filename(path)
        entry = PurityCacheEntry(
            step_id=step.id,
            cache_key=key,  # an exact match — would hit on the audit path
            detail_hash=comps.detail_hash,
            all_files_fingerprint=comps.all_files_fingerprint,
            change_type=comps.change_type,
            depends_on=list(comps.depends_on),
            purity_verdict_logic_version=comps.logic_version,
            detail_relpath=step.detail,
            findings=[],
            impl_tests_text="",
            checked_at="2026-07-18T00:00:00Z",
        )
        save_purity_cache(
            purity_cache_path(tmp_repo.root, slug),
            PurityCache(plan_slug=slug, entries={step.id: entry}),
        )
        calls = self._patched_producer(monkeypatch, [])
        plan_tool.detail._cached_purity_findings(
            path, step,
            repo_root=tmp_repo.root,
            plan_name="p",
            invoker=plan_tool.detail.shell_detail_invoker,
            read_through=False,
        )
        assert len(calls) == 1  # write-through always calls Claude


class TestSampleConceptualAudit:
    """``_sample_conceptual_audit`` — the single ``audit_plan_until_stable``
    call. The claude seam is stubbed on the *domain* module so no real call
    fires and the body-local import resolves to the patch."""

    def test_returns_audited_recs(self, tmp_repo, monkeypatch) -> None:
        import plan_tool.review

        sentinel = [_rec("medium")]
        monkeypatch.setattr(
            plan_tool.review,
            "audit_plan_until_stable",
            lambda *a, **k: sentinel,
        )
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        out = _sample_conceptual_audit(
            plan, path, ctx, max_passes=1, dry_rounds=1
        )
        assert out is sentinel

    def test_invokes_domain_seam_once_no_real_call(
        self, tmp_repo, monkeypatch
    ) -> None:
        import plan_tool.review

        calls: list[dict] = []

        def fake(*args, **kwargs):
            calls.append(kwargs)
            return []

        monkeypatch.setattr(
            plan_tool.review, "audit_plan_until_stable", fake
        )
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        _sample_conceptual_audit(plan, path, ctx, max_passes=2, dry_rounds=1)
        # Exactly one audit call (no real claude leak); the pass knobs
        # thread through to the domain seam.
        assert len(calls) == 1
        assert calls[0]["max_passes"] == 2
        assert calls[0]["dry_rounds"] == 1

    def test_plan_quota_warning_prints_once_with_noniterate_tail(
        self, tmp_repo, monkeypatch, capsys
    ) -> None:
        import plan_tool.review
        from plan_tool.cli.completeness_phases import _warn_if_audit_incomplete

        def quota_stopped_audit(*_args, **kwargs):
            kwargs["budget_report"].update(
                {
                    "passes_used": 1,
                    "budget_limited": False,
                    "early_stop_reason": "plan-quota",
                }
            )
            return []

        monkeypatch.setattr(
            plan_tool.review, "audit_plan_until_stable", quota_stopped_audit
        )
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        budget: dict = {}
        _sample_conceptual_audit(
            plan,
            path,
            SimpleNamespace(repo_root=tmp_repo.root),
            max_passes=1,
            dry_rounds=1,
            budget_report=budget,
        )
        _warn_if_audit_incomplete(budget, reuse=False)

        assert capsys.readouterr().err.count("COVERAGE UNCONFIRMED") == 1

    def test_conceptual_timeout_uses_its_phase_setting(
        self, tmp_repo, monkeypatch
    ) -> None:
        import plan_tool.review
        import plan_tool.shell as shell

        seen: list[float | None] = []
        monkeypatch.setattr(
            plan_tool.review,
            "audit_plan_until_stable",
            lambda *args, **kwargs: (seen.append(shell._effective_subprocess_timeout()) or []),
        )
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        monkeypatch.setenv("PLAN_TOOL_CLAUDE_TIMEOUT", "600")

        for value, expected in [(None, 600.0), ("1500", 1500.0), ("0", None)]:
            if value is None:
                monkeypatch.delenv(
                    "PLAN_TOOL_CONCEPTUAL_AUDIT_CLAUDE_TIMEOUT", raising=False
                )
            else:
                monkeypatch.setenv("PLAN_TOOL_CONCEPTUAL_AUDIT_CLAUDE_TIMEOUT", value)
            _sample_conceptual_audit(
                plan, path, ctx, max_passes=1, dry_rounds=1
            )
            assert seen.pop() == expected

    def test_threads_fresh_audit_shape_advisory_without_changing_recs(
        self, tmp_repo, monkeypatch
    ) -> None:
        import plan_tool.review
        from plan_tool.audit_shapes import AuditShapeAdvisory

        sentinel_recs = [_rec("medium")]
        sentinel_advisory = AuditShapeAdvisory(
            shape_id="arm-clustering",
            source_plan_fingerprint="snapshot",
            arm_step_ids=(1,),
            material_finding_ids=("finding",),
            arm_finding_ids=("finding",),
            material_finding_evidence=(),
            material_finding_count=1,
            arm_finding_count=1,
            committed_step_count=2,
        )

        def fake_audit(*_args, **kwargs):
            kwargs["advisory_out"][:] = [sentinel_advisory]
            return sentinel_recs

        monkeypatch.setattr(plan_tool.review, "audit_plan_until_stable", fake_audit)
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        out: list = []
        recs = _sample_conceptual_audit(
            plan, path, SimpleNamespace(repo_root=tmp_repo.root),
            max_passes=1, dry_rounds=1, advisory_out=out,
        )

        assert recs is sentinel_recs
        assert out == [sentinel_advisory]

    def test_threads_positive_sampler_resume_without_changing_recs(
        self, tmp_repo, monkeypatch
    ) -> None:
        """Only the sampler's positive result enables final provenance."""
        import plan_tool.review

        sentinel_recs = [_rec("medium")]

        def fake_audit(*_args, **kwargs):
            kwargs["resumed_out"][:] = [True]
            return sentinel_recs

        monkeypatch.setattr(plan_tool.review, "audit_plan_until_stable", fake_audit)
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        resumed: list[bool] = []
        recs = _sample_conceptual_audit(
            plan,
            path,
            SimpleNamespace(repo_root=tmp_repo.root),
            max_passes=1,
            dry_rounds=1,
            resumed_from_checkpoint_out=resumed,
        )

        assert recs is sentinel_recs
        assert resumed == [True]


class TestFingerprintTelemetry:
    """Phase-2 backfill: the granularity + audit-coverage recorder calls stamp a
    non-empty ``plan_fingerprint`` and leave ``code_fingerprint`` at ``{}`` (no
    per-``--iterate``-round re-hash), best-effort so a compute error can't flip rc."""

    def test_granularity_event_carries_plan_fingerprint_only(self, tmp_repo) -> None:
        from plan_tool.review_persistence import compute_plan_fingerprint
        from plan_tool.telemetry import read_decisions

        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        _run_deterministic_checks(plan, path, ctx, plan_name="p", quiet=True)
        events = [e for e in read_decisions(tmp_repo.root) if e.kind == "granularity"]
        assert len(events) == 1
        assert events[0].plan_fingerprint == compute_plan_fingerprint(path)
        assert events[0].code_fingerprint == ""

    def test_audit_coverage_event_carries_plan_fingerprint_only(
        self, tmp_repo, monkeypatch
    ) -> None:
        import plan_tool.review
        from plan_tool.review_persistence import compute_plan_fingerprint
        from plan_tool.telemetry import read_decisions

        def quota_stopped_audit(*_args, **kwargs):
            kwargs["budget_report"].update(
                {
                    "passes_used": 1,
                    "budget_limited": False,
                    "early_stop_reason": "plan-quota",
                }
            )
            return []

        monkeypatch.setattr(
            plan_tool.review, "audit_plan_until_stable", quota_stopped_audit
        )
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        _sample_conceptual_audit(plan, path, ctx, max_passes=1, dry_rounds=1)
        events = [e for e in read_decisions(tmp_repo.root) if e.kind == "audit-coverage"]
        assert len(events) == 1
        assert events[0].plan_fingerprint == compute_plan_fingerprint(path)
        assert events[0].code_fingerprint == ""
        assert events[0].context["early_stop_reason"] == "plan-quota"

    def test_completeness_fingerprint_compute_failure_is_best_effort(
        self, tmp_repo, monkeypatch
    ) -> None:
        import plan_tool.review_persistence
        from plan_tool.telemetry import read_decisions

        def _boom(*a, **k):
            raise RuntimeError("fingerprint blew up")

        monkeypatch.setattr(
            plan_tool.review_persistence, "compute_plan_fingerprint", _boom
        )
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        report = _run_deterministic_checks(plan, path, ctx, plan_name="p", quiet=True)
        # The phase still returns its normal report despite the raising compute.
        assert isinstance(report, _DeterministicReport)
        events = [e for e in read_decisions(tmp_repo.root) if e.kind == "granularity"]
        assert len(events) == 1
        assert events[0].plan_fingerprint == ""


class TestRenderGroupedReport:
    """``_render_grouped_report`` — pure Markdown assembly. Pins header
    presence/absence and branching, not whole-document bytes (those are
    owned by ``tests/test_completeness_report.py``)."""

    def test_correctness_group_always_present(self) -> None:
        md = _render_grouped_report(
            SimpleNamespace(title="P"),
            SimpleNamespace(name="p"),
            _empty_det(),
            correctness_recs=[],
            conceptual_recs=[],
            audit_recs=[],
            iterate_enabled=False,
        )
        assert "### Correctness (run these first)" in md

    def test_correctness_restatement_renders_here_too(self) -> None:
        """This section renders ``correctness_recs`` independently of
        ``build_report_md``'s ``## Conceptual correctness`` -- the same
        finding lands in both sections of one persisted report, so both
        must carry the restatement or a reader who only sees this one
        (it renders first) never sees the evidence."""
        rec = Recommendation(
            id="bare-gap", source="plan-correctness", severity="high",
            step_id=None, title="t", body="body",
            restated_property="the safety net has no route for this case",
        )
        md = _render_grouped_report(
            SimpleNamespace(title="P"),
            SimpleNamespace(name="p"),
            _empty_det(),
            correctness_recs=[rec],
            conceptual_recs=[],
            audit_recs=[],
            iterate_enabled=False,
        )
        assert "the safety net has no route for this case" in md

    def test_purity_coverage_distinguishes_skipped_scans(self) -> None:
        det = dataclasses.replace(
            _empty_det(),
            purity_coverage_recs=[
                _rec(
                    "high",
                    source="purity-scan-skipped",
                    title="budget expired",
                )
            ],
        )
        md = _render_grouped_report(
            SimpleNamespace(title="P"),
            SimpleNamespace(name="p"),
            det,
            correctness_recs=[],
            conceptual_recs=[],
            audit_recs=[],
            iterate_enabled=False,
        )

        assert "### Purity coverage" in md
        assert "PLAN_TOOL_PURITY_SCAN_BUDGET" in md
        assert "budget expired" in md

    def test_default_header_claims_detail_grounding(self) -> None:
        md = _render_grouped_report(
            SimpleNamespace(title="P"), SimpleNamespace(name="p"), _empty_det(),
            correctness_recs=[], conceptual_recs=[], audit_recs=[],
            iterate_enabled=False,
        )
        assert "grounded in the per-step detail bundle and the code at HEAD" in md

    def test_bare_plan_header_drops_false_grounding_claim(self) -> None:
        from plan_tool.review import DetailBundleStatus

        status = DetailBundleStatus(
            total=3, detailed_step_ids=(), bare_step_ids=(1, 2, 3)
        )
        md = _render_grouped_report(
            SimpleNamespace(title="P"), SimpleNamespace(name="p"), _empty_det(),
            correctness_recs=[], conceptual_recs=[], audit_recs=[],
            iterate_enabled=False, bundle_status=status,
            verdict=_CLEAR_VERDICT,
        )
        assert "Bare-plan audit" in md
        assert "0 of 3 step(s) detailed" in md
        # the false unconditional grounding claim must NOT appear for a bare plan
        assert (
            "grounded in the per-step detail bundle and the code at HEAD"
            not in md
        )
        suggested = md.split("### Suggested next steps", 1)[1]
        assert "plan-tool detail p" in suggested
        assert "plan-tool run p" not in suggested

    def test_bare_plan_missing_detail_transitions_to_detail(self) -> None:
        det = _DeterministicReport(
            path_style_hint=None,
            dep_issues=[],
            body_issues=[],
            detail_cov_issues=[
                DetailCoverageIssue(
                    step_id=2,
                    kind="missing_on_disk",
                    detail_path="plans/details/p-step-2.md",
                )
            ],
            detail_body_issues=[],
            files_coh_issues=[],
            lessons_issues=[],
        )
        md = _render_grouped_report(
            SimpleNamespace(title="P"),
            SimpleNamespace(name="p"),
            det,
            correctness_recs=[],
            conceptual_recs=[],
            audit_recs=[],
            iterate_enabled=False,
            bundle_status=SimpleNamespace(
                is_bare=True,
                is_fully_bare=True,
                detailed_count=0,
                total=2,
            ),
            verdict=_CLEAR_VERDICT,
        )
        suggested = md.split("### Suggested next steps", 1)[1]
        assert "Detail coverage" in md
        assert "plan-tool detail p" in suggested
        assert "plan-tool run p" not in suggested
        assert "conceptual-completeness findings are informational" in suggested

    def test_bare_plan_conceptual_findings_omit_apply_next_step(self) -> None:
        conceptual = [_rec("medium", source="plan-completeness")]
        md = _render_grouped_report(
            SimpleNamespace(title="P"),
            SimpleNamespace(name="p"),
            _empty_det(),
            correctness_recs=[],
            conceptual_recs=conceptual,
            audit_recs=conceptual,
            iterate_enabled=False,
            bundle_status=SimpleNamespace(
                is_bare=True,
                is_fully_bare=True,
                detailed_count=0,
                total=1,
            ),
            verdict=_CLEAR_VERDICT,
        )
        suggested = md.split("### Suggested next steps", 1)[1]
        assert "Conceptual completeness" in md
        assert "completeness-apply" not in suggested
        assert "plan-tool detail p" in suggested
        assert "plan-tool run p" not in suggested
        assert "conceptual-completeness findings are informational" in suggested

    def test_partial_detail_body_issue_omits_iterate_next_step(self) -> None:
        det = _DeterministicReport(
            path_style_hint=None,
            dep_issues=[],
            body_issues=[],
            detail_cov_issues=[],
            detail_body_issues=[
                DetailBodyIssue(
                    step_id=1,
                    kind="missing",
                    section="Tests",
                    detail_path="plans/details/p-step-1.md",
                )
            ],
            files_coh_issues=[],
            lessons_issues=[],
        )
        md = _render_grouped_report(
            SimpleNamespace(title="P"),
            SimpleNamespace(name="p"),
            det,
            correctness_recs=[],
            conceptual_recs=[],
            audit_recs=[],
            iterate_enabled=False,
            bundle_status=SimpleNamespace(
                is_bare=True,
                is_fully_bare=False,
                detailed_count=1,
                total=2,
            ),
            verdict=_CLEAR_VERDICT,
        )
        suggested = md.split("### Suggested next steps", 1)[1]
        assert "Detail file sections" in md
        assert "completeness-audit p --iterate" not in suggested
        assert "plan-tool detail p" in suggested
        assert "plan-tool run p" not in suggested
        assert "conceptual-completeness findings are informational" in suggested

    def test_budget_limited_emits_coverage_unconfirmed(self) -> None:
        md = _render_grouped_report(
            SimpleNamespace(title="P"), SimpleNamespace(name="p"), _empty_det(),
            correctness_recs=[], conceptual_recs=[], audit_recs=[],
            iterate_enabled=False,
            budget={"budget_limited": True, "passes_used": 16},
        )
        assert "Coverage unconfirmed" in md
        assert "16 pass" in md

    def test_budget_limited_coverage_reports_facts_without_a_passes_fallback(self) -> None:
        md = _render_grouped_report(
            SimpleNamespace(title="P"), SimpleNamespace(name="p"), _empty_det(),
            correctness_recs=[], conceptual_recs=[], audit_recs=[],
            iterate_enabled=False,
            budget={
                "budget_limited": True,
                "passes_used": 5,
                "recommendation_advice": "ignored",
            },
        )
        assert "Coverage unconfirmed" in md
        assert "--audit-passes" not in md
        assert "ignored" not in md

    def test_grouped_and_json_audit_output_share_a_fresh_advisory(self, capsys) -> None:
        display = _advisory_display()
        grouped = _render_grouped_report(
            SimpleNamespace(title="P"),
            SimpleNamespace(name="p"),
            _empty_det(),
            correctness_recs=[],
            conceptual_recs=[],
            audit_recs=[],
            iterate_enabled=False,
            audit_shape_advisory_display=display,
        )
        _render_completeness_json(
            SimpleNamespace(name="p", fail_on_findings=False),
            _empty_det(),
            [],
            has_blocking=False,
            audit_shape_advisory_display=display,
        )
        payload = json.loads(capsys.readouterr().out)
        assert "arm-clustering" in grouped
        assert "Focused work" in grouped
        assert "[risk-gap]" in grouped
        assert payload["has_blocking_findings"] is False
        assert payload["audit_shape_advisory"] == {
            "shape_id": "arm-clustering",
            "source_plan_fingerprint": "fresh-snapshot",
            "arm_steps": [
                {"id": 2, "title": "Focused work"},
                {"id": 3, "title": "Focused follow-up"},
            ],
            "material_finding_count": 4,
            "arm_finding_count": 3,
            "committed_step_count": 5,
            "evidence": [
                {"axis": "correctness", "anchors": ["design-gap"]},
                {"axis": "completeness", "anchors": ["risk-gap", "edge-gap"]},
            ],
        }

    def test_no_coverage_line_when_not_budget_limited(self) -> None:
        md = _render_grouped_report(
            SimpleNamespace(title="P"), SimpleNamespace(name="p"), _empty_det(),
            correctness_recs=[], conceptual_recs=[], audit_recs=[],
            iterate_enabled=False, budget={"budget_limited": False},
        )
        assert "Coverage unconfirmed" not in md

    def test_confirmed_low_yield_emits_converged_callout(self) -> None:
        # BACKLOG #125 — a low-yield stop gets its own callout, distinct from
        # both "Coverage unconfirmed" and a silent fully-clean audit.
        md = _render_grouped_report(
            SimpleNamespace(title="P"), SimpleNamespace(name="p"), _empty_det(),
            correctness_recs=[], conceptual_recs=[], audit_recs=[],
            iterate_enabled=False,
            budget={
                "budget_limited": False,
                "passes_used": 2,
                "confirmation_kind": "confirmed-low-yield",
            },
        )
        assert "Converged (low-yield)" in md
        assert "2 pass" in md
        assert "Coverage unconfirmed" not in md

    def test_confirmed_dry_emits_no_low_yield_callout(self) -> None:
        md = _render_grouped_report(
            SimpleNamespace(title="P"), SimpleNamespace(name="p"), _empty_det(),
            correctness_recs=[], conceptual_recs=[], audit_recs=[],
            iterate_enabled=False,
            budget={
                "budget_limited": False,
                "passes_used": 1,
                "confirmation_kind": "confirmed-dry",
            },
        )
        assert "Converged (low-yield)" not in md
        assert "Coverage unconfirmed" not in md

    def test_conceptual_group_conditional(self) -> None:
        conceptual = [_rec("medium", source="plan-completeness")]
        with_group = _render_grouped_report(
            SimpleNamespace(title="P"),
            SimpleNamespace(name="p"),
            _empty_det(),
            correctness_recs=[],
            conceptual_recs=conceptual,
            audit_recs=conceptual,
            iterate_enabled=False,
        )
        assert "### Conceptual completeness" in with_group
        without_group = _render_grouped_report(
            SimpleNamespace(title="P"),
            SimpleNamespace(name="p"),
            _empty_det(),
            correctness_recs=[],
            conceptual_recs=[],
            audit_recs=[],
            iterate_enabled=False,
        )
        assert "### Conceptual completeness" not in without_group

    def test_all_clear_empty_state_line(self) -> None:
        md = _render_grouped_report(
            SimpleNamespace(title="P"),
            SimpleNamespace(name="p"),
            _empty_det(),
            correctness_recs=[],
            conceptual_recs=[],
            audit_recs=[],
            iterate_enabled=False,
        )
        assert "_(no completeness issues detected)_" in md

    def test_grouped_report_renders_data_contract_drift(self) -> None:
        rec = Recommendation(
            id="plan-data-contract-abc123",
            source="data-contract",
            severity="medium",
            step_id=None,
            title="DATA_CONTRACT.md:SavedReview is missing `new_field`.",
            body="DATA_CONTRACT.md:SavedReview is missing `new_field`.",
            anchor="data-contract-savedreview-new-field",
        )
        det = _DeterministicReport(
            path_style_hint=None,
            dep_issues=[],
            body_issues=[],
            detail_cov_issues=[],
            detail_body_issues=[],
            files_coh_issues=[],
            lessons_issues=[],
            data_contract_recs=[rec],
        )
        md = _render_grouped_report(
            SimpleNamespace(title="P"),
            SimpleNamespace(name="p"),
            det,
            correctness_recs=[],
            conceptual_recs=[],
            audit_recs=[],
            iterate_enabled=False,
        )
        assert "### Data contract" in md
        assert "data-contract-savedreview-new-field" in md
        assert "new_field" in md
        assert "_(no completeness issues detected)_" not in md

    def test_grouped_report_renders_input_contract_findings(self) -> None:
        rec = _rec("medium", source="data-contract", title="stale input")
        rec = dataclasses.replace(
            rec,
            body="details/01.md:## Input cites `SavedReview.not_a_field`.",
            anchor="data-contract-input-savedreview-not-a-field",
        )
        det = dataclasses.replace(_empty_det(), data_contract_recs=[rec])
        md = _render_grouped_report(
            SimpleNamespace(title="P"),
            SimpleNamespace(name="p"),
            det,
            correctness_recs=[],
            conceptual_recs=[],
            audit_recs=[],
            iterate_enabled=False,
        )
        assert "### Data contract" in md
        assert "SavedReview.not_a_field" in md

    def test_grouped_report_no_issues_stays_clean_when_data_contract_empty(
        self,
    ) -> None:
        md = _render_grouped_report(
            SimpleNamespace(title="P"),
            SimpleNamespace(name="p"),
            _DeterministicReport(
                path_style_hint=None,
                dep_issues=[],
                body_issues=[],
                detail_cov_issues=[],
                detail_body_issues=[],
                files_coh_issues=[],
                lessons_issues=[],
                data_contract_recs=[],
            ),
            correctness_recs=[],
            conceptual_recs=[],
            audit_recs=[],
            iterate_enabled=False,
        )
        assert "_(no completeness issues detected)_" in md

    def test_next_steps_bullet_tracks_budget_enabled(self) -> None:
        args = SimpleNamespace(name="myplan")
        # A deterministic finding makes the next-steps block structural, so
        # the structural bullet flips with the iterate (budget-enabled) flag.
        # A conceptual-correctness gap is not structural: no apply verb
        # targets it (#85), so it never earns the auto-apply bullet.
        det = _empty_det()
        det.dep_issues.append(
            SimpleNamespace(step_id=2, depends_on=1, reason="unknown")
        )
        off = _render_grouped_report(
            SimpleNamespace(title="P"), args, det,
            correctness_recs=[], conceptual_recs=[], audit_recs=[],
            iterate_enabled=False,
        )
        on = _render_grouped_report(
            SimpleNamespace(title="P"), args, det,
            correctness_recs=[], conceptual_recs=[], audit_recs=[],
            iterate_enabled=True,
        )
        assert "### Suggested next steps" in off
        assert "completeness-audit myplan --iterate" in off
        assert "reconcile-plan-walk myplan" in on

    def test_blocking_correctness_gap_on_a_detailed_plan_is_not_auto_apply(
        self,
    ) -> None:
        """Deliberate: a blocking conceptual-correctness gap on a detailed plan
        reads as a session-directed edit, never as ``--iterate`` auto-apply or
        the reconcile walk, and the re-audit command is named once."""
        rec = _rec("high", source="plan-correctness")
        verdict = blocking_verdict_from_gate([rec.id])
        for iterate in (False, True):
            md = _render_grouped_report(
                SimpleNamespace(title="P"), SimpleNamespace(name="p"),
                _empty_det(),
                correctness_recs=[rec], conceptual_recs=[], audit_recs=[rec],
                iterate_enabled=iterate, bundle_status=_COMPLETE_BUNDLE,
                 verdict=verdict,
            )
            steps = md.split("### Suggested next steps", 1)[1]
            assert "session-directed edit" in steps
            assert "auto-apply" not in steps
            assert "reconcile-plan-walk" not in steps
            assert steps.count("completeness-audit p --iterate") == 1

    def test_grouped_report_renders_smells_section(self) -> None:
        smell = _rec("info", source="feature-ref", title="brittle ref")
        det = _det_with_smells([smell])
        md = _render_grouped_report(
            SimpleNamespace(title="P"),
            SimpleNamespace(name="p"),
            det,
            correctness_recs=[],
            conceptual_recs=[],
            audit_recs=[],
            iterate_enabled=False,
        )
        assert "### Smells (advisory)" in md
        assert "body" in md  # the rec body is rendered

    def test_medium_mixed_step_finding_surfaces_in_grouped_report(self) -> None:
        # The medium mixed-step rec renders in the advisory smells section.
        mixed = _mixed_step_rec(step_id=1)
        det = _det_with_smells([mixed])
        md = _render_grouped_report(
            SimpleNamespace(title="P"),
            SimpleNamespace(name="p"),
            det,
            correctness_recs=[],
            conceptual_recs=[],
            audit_recs=[],
            iterate_enabled=False,
        )
        assert "### Smells (advisory)" in md
        assert mixed.body in md

    def test_grouped_report_omits_smells_section_when_none(self) -> None:
        md = _render_grouped_report(
            SimpleNamespace(title="P"),
            SimpleNamespace(name="p"),
            _empty_det(),
            correctness_recs=[],
            conceptual_recs=[],
            audit_recs=[],
            iterate_enabled=False,
        )
        assert "### Smells (advisory)" not in md

    def test_smell_only_plan_not_reported_as_no_issues(self) -> None:
        # Only ``smell_recs`` populated → the smells section shows and the
        # all-clear line does not (pins the ``has_any`` edit).
        det = _det_with_smells([_rec("info", source="self-referential")])
        md = _render_grouped_report(
            SimpleNamespace(title="P"),
            SimpleNamespace(name="p"),
            det,
            correctness_recs=[],
            conceptual_recs=[],
            audit_recs=[],
            iterate_enabled=False,
        )
        assert "### Smells (advisory)" in md
        assert "_(no completeness issues detected)_" not in md

    def test_grouped_report_renders_self_consistency_section(self) -> None:
        rec = _rec("medium", source="orphaned-deliverable", title="orphan")
        det = _det_with_self_consistency([rec])
        md = _render_grouped_report(
            SimpleNamespace(title="P"),
            SimpleNamespace(name="p"),
            det,
            correctness_recs=[],
            conceptual_recs=[],
            audit_recs=[],
            iterate_enabled=False,
        )
        assert "### Self-consistency" in md
        assert rec.body in md
        # A self-consistency finding is an issue, so the all-clear line stays off.
        assert "_(no completeness issues detected)_" not in md

    def test_blocking_self_consistency_next_step_is_not_called_advisory(
        self,
    ) -> None:
        # The report's whole point after the promotion: a plan whose only
        # finding is a blocking intent rec must not be told it has nothing to
        # do — the old tail fell through to the advisory line.
        rec = _rec("medium", source="intent-presence", title="no intent")
        md = _render_grouped_report(
            SimpleNamespace(title="P"),
            SimpleNamespace(name="p"),
            _det_with_self_consistency([rec]),
            correctness_recs=[],
            conceptual_recs=[],
            audit_recs=[],
            iterate_enabled=False,
        )
        suggested = md.split("### Suggested next steps", 1)[1]
        assert "advisory under the audit's blocking bar" not in suggested
        assert "one-line `intent:`" in suggested
        assert "intent-presence" in suggested


    def test_non_intent_self_consistency_next_step_says_manual_edit(self) -> None:
        rec = _rec("medium", source="orphaned-deliverable", title="orphan")
        md = _render_grouped_report(
            SimpleNamespace(title="P"),
            SimpleNamespace(name="p"),
            _det_with_self_consistency([rec]),
            correctness_recs=[],
            conceptual_recs=[],
            audit_recs=[],
            iterate_enabled=False,
        )
        suggested = md.split("### Suggested next steps", 1)[1]
        assert "advisory under the audit's blocking bar" not in suggested
        assert "session-directed edit to the plan" in suggested
        assert "one-line `intent:`" not in suggested

    def test_advisory_self_consistency_rec_keeps_the_advisory_tail(self) -> None:
        # Below medium the bucket does not gate, so the tail must not promise a
        # fix the finding does not need.
        rec = _rec("info", source="orphaned-deliverable", title="orphan")
        md = _render_grouped_report(
            SimpleNamespace(title="P"),
            SimpleNamespace(name="p"),
            _det_with_self_consistency([rec]),
            correctness_recs=[],
            conceptual_recs=[],
            audit_recs=[],
            iterate_enabled=False,
        )
        suggested = md.split("### Suggested next steps", 1)[1]
        # Advisory: listed, holds back no stage, and the stage is the one command.
        assert "hold back no stage" in suggested
        assert "`plan-tool run p`" in suggested

    def test_grouped_report_omits_self_consistency_section_when_none(self) -> None:
        md = _render_grouped_report(
            SimpleNamespace(title="P"),
            SimpleNamespace(name="p"),
            _empty_det(),
            correctness_recs=[],
            conceptual_recs=[],
            audit_recs=[],
            iterate_enabled=False,
        )
        assert "### Self-consistency" not in md
        assert "_(no completeness issues detected)_" in md

    def test_bare_plan_correctness_names_a_session_directed_edit(self) -> None:
        correctness = [_rec("high", source="plan-correctness")]
        md = _render_grouped_report(
            SimpleNamespace(title="P"),
            SimpleNamespace(name="p"),
            _empty_det(),
            correctness_recs=correctness,
            conceptual_recs=[],
            audit_recs=correctness,
            iterate_enabled=False,
            bundle_status=SimpleNamespace(
                is_bare=True,
                is_fully_bare=True,
                detailed_count=0,
                total=1,
            ),
        )
        suggested = md.split("### Suggested next steps", 1)[1]
        assert "session-directed edit" in suggested
        assert "advisory under the audit's blocking bar" not in suggested

    def test_bare_plan_correctness_bullet_counts_only_correctness_gaps(
        self,
    ) -> None:
        correctness = [
            _rec("high", source="plan-correctness", title="c1"),
            _rec("medium", source="plan-correctness", title="c2"),
        ]
        conceptual = [
            _rec("medium", source="plan-completeness", title="x1"),
            _rec("medium", source="plan-completeness", title="x2"),
            _rec("low", source="plan-completeness", title="x3"),
        ]
        md = _render_grouped_report(
            SimpleNamespace(title="P"),
            SimpleNamespace(name="p"),
            _empty_det(),
            correctness_recs=correctness,
            conceptual_recs=conceptual,
            audit_recs=correctness + conceptual,
            iterate_enabled=False,
            bundle_status=SimpleNamespace(
                is_bare=True,
                is_fully_bare=True,
                detailed_count=0,
                total=1,
            ),
            verdict=blocking_verdict_from_gate([r.id for r in correctness]),
        )
        suggested = md.split("### Suggested next steps", 1)[1]
        apply_lines = [
            line for line in suggested.splitlines() if line.startswith("- Close ")
        ]
        assert len(apply_lines) == 1
        assert "2 conceptual-correctness gap(s)" in apply_lines[0]
        assert "non-blocking completeness gaps stay informational" in apply_lines[0]

    def test_bare_plan_correctness_replaces_the_iterate_reaudit_bullet(
        self,
    ) -> None:
        correctness = [_rec("high", source="plan-correctness")]
        md = _render_grouped_report(
            SimpleNamespace(title="P"),
            SimpleNamespace(name="p"),
            _empty_det(),
            correctness_recs=correctness,
            conceptual_recs=[],
            audit_recs=correctness,
            iterate_enabled=False,
            bundle_status=SimpleNamespace(
                is_bare=True,
                is_fully_bare=True,
                detailed_count=0,
                total=1,
            ),
        )
        suggested = md.split("### Suggested next steps", 1)[1]
        # The iterate-and-auto-apply bullet is replaced by the edit instruction;
        # the single `--iterate` row left is the re-audit after that edit.
        assert "re-run with the convergence loop" not in suggested
        assert suggested.count("completeness-audit p --iterate") == 1
        assert "session-directed edit" in suggested

    def test_bare_plan_deterministic_finding_keeps_its_own_iterate_bullet(
        self,
    ) -> None:
        det = _DeterministicReport(
            path_style_hint=None,
            dep_issues=[],
            body_issues=[
                SimpleNamespace(kind="missing", section="Overview", details="d")
            ],
            detail_cov_issues=[],
            detail_body_issues=[],
            files_coh_issues=[],
            lessons_issues=[],
        )
        correctness = [_rec("high", source="plan-correctness")]
        md = _render_grouped_report(
            SimpleNamespace(title="P"),
            SimpleNamespace(name="p"),
            det,
            correctness_recs=correctness,
            conceptual_recs=[],
            audit_recs=correctness,
            iterate_enabled=False,
            bundle_status=SimpleNamespace(
                is_bare=True,
                is_fully_bare=True,
                detailed_count=0,
                total=1,
            ),
        )
        suggested = md.split("### Suggested next steps", 1)[1]
        assert "completeness-audit p --iterate" in suggested
        assert "deterministic finding(s)" in suggested
        assert "deterministic/correctness" not in suggested
        assert "session-directed edit" in suggested

    def test_bare_plan_iterate_arm_does_not_offer_reconcile_walk_for_correctness(
        self,
    ) -> None:
        det = _DeterministicReport(
            path_style_hint=None,
            dep_issues=[],
            body_issues=[
                SimpleNamespace(kind="missing", section="Overview", details="d")
            ],
            detail_cov_issues=[],
            detail_body_issues=[],
            files_coh_issues=[],
            lessons_issues=[],
        )
        correctness = [_rec("high", source="plan-correctness")]
        md = _render_grouped_report(
            SimpleNamespace(title="P"),
            SimpleNamespace(name="p"),
            det,
            correctness_recs=correctness,
            conceptual_recs=[],
            audit_recs=correctness,
            iterate_enabled=True,
            bundle_status=SimpleNamespace(
                is_bare=True,
                is_fully_bare=True,
                detailed_count=0,
                total=1,
            ),
        )
        suggested = md.split("### Suggested next steps", 1)[1]
        assert "reconcile-plan-walk p" in suggested
        assert "remaining finding(s)" in suggested
        assert "session-directed edit" in suggested

    def test_bare_plan_correctness_omits_detail_authoring(self) -> None:
        det = _DeterministicReport(
            path_style_hint=None,
            dep_issues=[],
            body_issues=[],
            detail_cov_issues=[
                DetailCoverageIssue(
                    step_id=1,
                    kind="missing_on_disk",
                    detail_path="plans/details/p-step-1.md",
                )
            ],
            detail_body_issues=[],
            files_coh_issues=[],
            lessons_issues=[],
        )
        correctness = [_rec("high", source="plan-correctness")]
        md = _render_grouped_report(
            SimpleNamespace(title="P"),
            SimpleNamespace(name="p"),
            det,
            correctness_recs=correctness,
            conceptual_recs=[],
            audit_recs=correctness,
            iterate_enabled=False,
            bundle_status=SimpleNamespace(
                is_bare=True,
                is_fully_bare=True,
                detailed_count=0,
                total=1,
            ),
        )
        suggested = md.split("### Suggested next steps", 1)[1]
        assert "plan-tool detail" not in suggested
        assert "session-directed edit" in suggested


_COMPLETE_BUNDLE = SimpleNamespace(
    is_bare=False, is_fully_bare=False, detailed_count=1, total=1
)


def _render_with_verdict(verdict, *, conceptual=(), **kw) -> str:
    return _render_grouped_report(
        SimpleNamespace(title="P"),
        SimpleNamespace(name="p"),
        _empty_det(),
        correctness_recs=[],
        conceptual_recs=list(conceptual),
        audit_recs=list(conceptual),
        iterate_enabled=False,
        bundle_status=_COMPLETE_BUNDLE,
        verdict=verdict,
        **kw,
    )


def _gate_verdict(
    *, audit_incomplete, conceptual_bar_blocking_ids, blocking_deterministic
):
    return blocking_verdict_from_gate(
        conceptual_bar_blocking_ids,
        blocking_deterministic,
        untrusted_cause=UNTRUSTED_PERSISTENT if audit_incomplete else "",
    )


class TestNextStepVerdictWiring:
    """The finalize gate's own result reaches every next-step reader; no
    reader derives blocking from its own lists."""

    @staticmethod
    def _bare_gate_inputs(**overrides) -> dict:
        base = dict(
            path_style_hint=None,
            dep_issues=[],
            body_issues=[],
            detail_cov_issues=[],
            detail_body_issues=[],
            lessons_issues=[],
            data_contract_recs=(),
            self_consistency_recs=(),
            purity_coverage_recs=(),
        )
        base.update(overrides)
        return base

    def test_clean_gate_builds_empty_set_verdict_and_offers_stage(self) -> None:
        from plan_tool.cli.completeness_cmd import _blocking_deterministic_findings

        verdict = _gate_verdict(
            audit_incomplete=False,
            conceptual_bar_blocking_ids=(),
            blocking_deterministic=_blocking_deterministic_findings(
                **self._bare_gate_inputs()
            ),
        )
        assert verdict.is_completed_empty_set
        md = _render_with_verdict(verdict)
        assert "No gaps to close — `plan-tool run p`" in md

    def test_blocking_bar_id_closes_every_next_step_surface(self) -> None:
        verdict = blocking_verdict_from_gate(["plan-completeness-high"])
        md = _render_with_verdict(verdict)
        suggested = md.split("### Suggested next steps", 1)[1]
        assert "No gaps to close" not in md
        assert "plan-tool run p" not in suggested
        assert "plan-tool jira p" not in suggested
        assert "plan-tool detail p" not in suggested
        assert "plan-tool completeness-audit p" in suggested

    def test_deterministic_blocker_with_empty_bar_ids_is_not_clear(self) -> None:
        """An empty id tuple must never be read as 'nothing blocks'."""
        from plan_tool.cli.completeness_cmd import _blocking_deterministic_findings

        verdict = _gate_verdict(
            audit_incomplete=False,
            conceptual_bar_blocking_ids=(),
            blocking_deterministic=_blocking_deterministic_findings(
                **self._bare_gate_inputs(dep_issues=[object()])
            ),
        )
        assert verdict.blocking_ids == ()
        assert not verdict.is_completed_empty_set
        md = _render_with_verdict(verdict)
        assert "No gaps to close" not in md
        assert "plan-tool run p" not in md.split("### Suggested next steps", 1)[1]

    def test_incomplete_audit_builds_incomplete_verdict_not_empty_set(self) -> None:

        verdict = _gate_verdict(
            audit_incomplete=True,
            conceptual_bar_blocking_ids=(),
            blocking_deterministic=(),
        )
        assert verdict.state == "incomplete"
        md = _render_with_verdict(verdict)
        assert "No gaps to close" not in md
        assert "plan-tool run p" not in md.split("### Suggested next steps", 1)[1]

    @pytest.mark.parametrize(
        "overrides",
        [
            {},
            {"path_style_hint": object()},
            {"dep_issues": [object()]},
            {"body_issues": [object()]},
            {"detail_cov_issues": [SimpleNamespace(kind="missing_on_disk")]},
            {"detail_cov_issues": [SimpleNamespace(kind="other")]},
            {"detail_body_issues": [object()]},
            {"lessons_issues": [object()]},
            {"data_contract_recs": [_rec("high", source="data-contract")]},
            {"data_contract_recs": [_rec("low", source="data-contract")]},
            {"self_consistency_recs": [_rec("medium", source="intent")]},
            {"purity_coverage_recs": [_rec("high", source="purity-scan-skipped")]},
        ],
    )
    @pytest.mark.parametrize("bar_ids", [(), ("x",)])
    @pytest.mark.parametrize("audit_incomplete", [False, True])
    def test_verdict_clear_iff_gate_clear(
        self, overrides, bar_ids, audit_incomplete
    ) -> None:
        from plan_tool.cli.completeness_cmd import _blocking_deterministic_findings

        inputs = self._bare_gate_inputs(**overrides)
        gate_blocks = _completeness_has_blocking_findings(
            **inputs,
            audit_recs=(),
            audit_stage=STAGE_DETAIL,
            conceptual_bar_blocking_ids=bar_ids,
        )
        verdict = _gate_verdict(
            audit_incomplete=audit_incomplete,
            conceptual_bar_blocking_ids=bar_ids,
            blocking_deterministic=_blocking_deterministic_findings(**inputs),
        )
        assert verdict.is_completed_empty_set is (
            not gate_blocks and not audit_incomplete
        )

    @pytest.mark.parametrize(
        "stop_reason",
        [
            None, "converged", "no_blocking_findings",
            "all_auto_apply_findings_deferred", "terminal_hand_apply",
            "manual_fix_blocking_findings", "deadline_exceeded",
            "time_budget_exceeded", "max_iterations", "no_progress",
            "marginal", "plan-quota",
        ],
    )
    @pytest.mark.parametrize("set_nonempty", [False, True])
    @pytest.mark.parametrize("audit_incomplete", [False, True])
    @pytest.mark.parametrize(
        "headline",
        ["clean", "advisory-only", "awaiting-human-action",
         "no-qualified-current-evidence"],
    )
    def test_trust_follows_the_gate_and_the_gaps_named_are_the_gates_ids(
        self, stop_reason, set_nonempty, audit_incomplete, headline
    ) -> None:
        """A stage is offered iff the set is empty, finalize is clean, and the
        result is neither unqualified nor awaiting a person; whatever the
        verdict, the ids it names are exactly the gate's (never dropped)."""
        from plan_tool.cli.completeness_cmd import (
            _completeness_finalize_is_clean,
            _verdict_untrusted_cause,
        )
        from plan_tool.completeness_report import (
            _verdict_offers_stage,
            next_step_gaps,
        )

        ids = ("plan-correctness-high",) if set_nonempty else ()
        verdict = blocking_verdict_from_gate(
            ids,
            untrusted_cause=_verdict_untrusted_cause(
                audit_incomplete=audit_incomplete,
                stop_reason=stop_reason,
                qualified_headline=headline,
                revision_status="current",
                blocking_set_nonempty=set_nonempty,
            ),
        )
        finalize_clean = _completeness_finalize_is_clean(
            audit_incomplete=audit_incomplete,
            has_blocking=set_nonempty,
            stop_reason=stop_reason,
        )
        expected_offer = (
            finalize_clean
            and not set_nonempty
            and headline not in (
                "awaiting-human-action", "no-qualified-current-evidence"
            )
        )
        assert _verdict_offers_stage(verdict) is expected_offer
        trusted_set = (
            not audit_incomplete
            and headline != "no-qualified-current-evidence"
            and set_nonempty
        )
        if trusted_set:  # a non-empty set names its gaps whatever the stop
            assert verdict.state == "set"
        elif not expected_offer:
            assert verdict.state == "incomplete"
        assert set(verdict.blocking_ids) == set(ids)
        listed = _rec("high", source="plan-correctness")  # id plan-correctness-high
        gaps = next_step_gaps(verdict, correctness=[listed])
        assert [r.id for r in gaps.close_correctness] == list(ids)

    @pytest.mark.parametrize(
        ("audit_incomplete", "stop_reason", "headline", "cause"),
        [
            (True, "converged", "clean", UNTRUSTED_PERSISTENT),
            (False, "converged", "no-qualified-current-evidence", UNTRUSTED_PERSISTENT),
            (False, "terminal_hand_apply", "awaiting-human-action", UNTRUSTED_PERSISTENT),
            (False, "converged", "awaiting-human-action", UNTRUSTED_PERSISTENT),
            (False, "deadline_exceeded", "awaiting-human-action", UNTRUSTED_TRANSIENT),
            (False, "max_iterations", "awaiting-human-action", UNTRUSTED_TRANSIENT),
            (False, "no_progress", "awaiting-human-action", UNTRUSTED_TRANSIENT),
            (False, "manual_fix_blocking_findings", "awaiting-human-action", UNTRUSTED_PERSISTENT),
            (False, None, "awaiting-human-action", UNTRUSTED_PERSISTENT),
            (True, "max_iterations", "awaiting-human-action", UNTRUSTED_PERSISTENT),
            (False, "converged", "clean", ""),
            (False, "converged", "advisory-only", ""),
        ],
    )
    def test_untrusted_cause_separates_a_retry_from_a_reproduction(
        self, audit_incomplete, stop_reason, headline, cause
    ) -> None:
        """A cut-short stop is transient (re-audit continues it); unqualified
        coverage or a wait on a person is persistent (re-audit reproduces it)."""
        from plan_tool.cli.completeness_cmd import _verdict_untrusted_cause

        assert _verdict_untrusted_cause(
            audit_incomplete=audit_incomplete,
            stop_reason=stop_reason,
            qualified_headline=headline,
            revision_status="current",
            blocking_set_nonempty=False,
        ) == cause

    @pytest.mark.parametrize(
        ("halt_reason", "cause"),
        [
            ("pre-apply drift detected", "transient"),
            ("post-apply drift detected", "transient"),
            ("plan failed to parse before apply_finding", "persistent"),
            (
                "reverted apply-finding edits: post-edit plan failed to parse",
                "persistent",
            ),
            (
                "plan has an unmatched opening code fence after apply_finding",
                "persistent",
            ),
        ],
    )
    def test_halt_cause_follows_whether_a_reaudit_reproduces_it(
        self, halt_reason, cause
    ) -> None:
        """Deliberate: a drift halt clears on a re-audit (each run takes a fresh
        drift baseline), so it reads as a retry; a halt on text that fails to
        parse or on a reverted edit is reproduced, so it prescribes triage. The
        cause comes from the outcome's own ``halt_reason``, not from parsing
        the free-text stop reason."""
        from plan_tool.cli.completeness_cmd import _verdict_untrusted_cause

        assert _verdict_untrusted_cause(
            audit_incomplete=False,
            stop_reason=f"halted: {halt_reason}",
            qualified_headline="awaiting-human-action",
            revision_status="current",
            halt_reason=halt_reason,
        ) == cause

    def test_omitted_deterministic_arm_is_a_type_error_not_a_clear_gate(
        self,
    ) -> None:
        """Deliberate: the gate predicate never reads "nothing blocks" because
        a caller forgot an arm; every raw arm, or the collected tuple, is
        required."""
        from plan_tool.cli.completeness_cmd import _completeness_has_blocking_findings

        with pytest.raises(TypeError, match="needs blocking_deterministic"):
            _completeness_has_blocking_findings(
                audit_stage=STAGE_DETAIL, audit_recs=[]
            )
        with pytest.raises(TypeError, match="needs blocking_deterministic"):
            _completeness_has_blocking_findings(
                path_style_hint=None, dep_issues=[], body_issues=[],
                detail_cov_issues=[], detail_body_issues=[], lessons_issues=[],
                audit_stage=STAGE_DETAIL,  # data-contract/self-consistency/purity omitted
            )
        assert _completeness_has_blocking_findings(
            audit_stage=STAGE_DETAIL, blocking_deterministic=()
        ) is False

    @pytest.mark.parametrize("audit_incomplete", [False, True])
    def test_legacy_unknown_coverage_on_a_current_revision_is_stale_revision(
        self, audit_incomplete
    ) -> None:
        """The legacy-coverage reason the classifier really produces
        (headline no-evidence, coverage ``unknown-legacy``, revision
        ``current``) is a fresh-audit answer: a re-audit observes coverage
        anew, so "re-auditing unchanged text reproduces this" is false."""
        from plan_tool.cli.completeness_cmd import _verdict_untrusted_cause

        assert _verdict_untrusted_cause(
            audit_incomplete=audit_incomplete,
            stop_reason="converged",
            qualified_headline="no-qualified-current-evidence",
            revision_status="current",
            coverage_status="unknown-legacy",
        ) == "stale-revision"

    def test_unconfirmed_coverage_on_a_current_revision_stays_persistent(
        self,
    ) -> None:
        """Carve-out pin: only legacy-unknown coverage is a fresh-audit
        answer; budget-limited / unconfirmed coverage keeps hand triage."""
        from plan_tool.cli.completeness_cmd import _verdict_untrusted_cause

        assert _verdict_untrusted_cause(
            audit_incomplete=True,
            stop_reason="converged",
            qualified_headline="no-qualified-current-evidence",
            revision_status="current",
            coverage_status="unconfirmed",
        ) == "persistent"

    @pytest.mark.parametrize("revision", ["stale", "unknown-legacy", "not-sampled"])
    @pytest.mark.parametrize("audit_incomplete", [False, True])
    @pytest.mark.parametrize("stop_reason", ["converged", "max_iterations"])
    def test_stale_revision_wins_over_incomplete_and_cut_short_stop(
        self, revision, audit_incomplete, stop_reason
    ) -> None:
        """No evidence on changed or unsampled text is a fresh-audit answer
        whatever the coverage or stop; it is never ``persistent`` triage."""
        from plan_tool.cli.completeness_cmd import _verdict_untrusted_cause

        assert _verdict_untrusted_cause(
            audit_incomplete=audit_incomplete,
            stop_reason=stop_reason,
            qualified_headline="no-qualified-current-evidence",
            revision_status=revision,
        ) == "stale-revision"

    @pytest.mark.parametrize(
        "stop_reason", ["max_iterations", "deadline_exceeded", "terminal_hand_apply"]
    )
    def test_nonempty_blocking_set_on_qualified_result_is_trusted_whatever_the_stop(
        self, stop_reason
    ) -> None:
        """Carve-out pin: trust follows the gate; a non-empty set stays ``""``."""
        from plan_tool.cli.completeness_cmd import _verdict_untrusted_cause

        assert _verdict_untrusted_cause(
            audit_incomplete=False,
            stop_reason=stop_reason,
            qualified_headline="awaiting-human-action",
            revision_status="current",
            blocking_set_nonempty=True,
        ) == ""

    def test_fresh_audit_branch_names_no_deterministic_step_for_absent_verdict(
        self,
    ) -> None:
        """The fresh-audit branch fires only for an ``absent`` verdict, which
        carries no deterministic findings: its steps are the re-audit line."""
        md = _render_with_verdict(
            None, qualified_result={
                "headline": "no-qualified-current-evidence",
                "stage": "detail",
                "coverage": "unconfirmed",
                "revision_status": "current",
                "audit_revision": None,
            }
        )
        steps = md.split("### Suggested next steps", 1)[1]
        assert "run a fresh audit before reusing or applying" in steps
        assert "Close the blocking" not in steps

    def test_deterministic_blocker_still_named_when_verdict_is_incomplete(
        self,
    ) -> None:
        """Carve-out pin: an incomplete verdict still names its blocking
        deterministic finding once, via the earlier no-stage block."""
        rec = _rec("high", source="purity-coverage", title="Uncovered purity row")
        verdict = blocking_verdict_from_gate(
            [], [rec], untrusted_cause=UNTRUSTED_PERSISTENT
        )
        md = _render_with_verdict(
            verdict, qualified_result={
                "headline": "no-qualified-current-evidence",
                "stage": "detail",
                "coverage": "unconfirmed",
                "revision_status": "current",
                "audit_revision": None,
            }
        )
        steps = md.split("### Suggested next steps", 1)[1]
        assert steps.count("Close the blocking `purity-coverage` finding") == 1

    def test_pre_apply_checkpoint_report_offers_no_stage(self) -> None:
        """The checkpoint has no gate result, so it never claims a clear one."""
        md = _render_with_verdict(None, is_pre_apply_checkpoint=True)
        assert "No gaps to close" not in md
        assert "plan-tool run p" not in md.split("### Suggested next steps", 1)[1]

    def test_verdict_uses_post_loop_stage_not_frozen_outcome_ids(self) -> None:
        """The verdict is built from the ids ``finalize_completeness_run``
        recomputes at the sampled stage, not from the loop's frozen outcome."""
        source = inspect.getsource(finalize_completeness_run)
        assert "blocking_verdict_from_gate(" in source
        assert "verdict_blocking_ids," in source
        assert "compute_conceptual_bar_blocking_ids(" in source
        assert "audit_recs, audit_stage=result_audit_stage" in source
        assert "outcome.conceptual_bar_blocking_ids" not in source

    def test_json_payload_signature_is_unchanged_by_verdict_wiring(self) -> None:
        """``--json`` keeps its own gate bool; the verdict never enters it."""
        params = inspect.signature(_render_completeness_json).parameters
        assert "verdict" not in params
        assert "has_blocking" in params

    def test_next_steps_sink_receives_reaudit_command_when_gate_blocks(
        self, tmp_repo, capsys, monkeypatch
    ) -> None:
        import plan_tool.completeness_report
        import plan_tool.review

        monkeypatch.setattr(
            plan_tool.completeness_report,
            "write_completeness_report",
            lambda *a, **k: tmp_repo.root / "report.md",
        )
        monkeypatch.setattr(
            plan_tool.review, "check_concept_coverage", lambda *a, **k: []
        )
        path = tmp_repo.plans_dir / "1-demo.md"
        path.write_text(_sectioned_plan_text(_CLEAN_STEPS), encoding="utf-8")
        sink: list = []
        _persist_and_present_report(
            SimpleNamespace(title="Demo Plan", steps=[]),
            path,
            SimpleNamespace(name="1-demo", _next_steps_sink=sink),
            SimpleNamespace(repo_root=tmp_repo.root),
            iterate_enabled=True,
            outcome=_IterateOutcome(stop_reason="done", iterations=1),
            correctness_recs=[],
            conceptual_recs=[],
            grouped_md="## grouped\n",
            bundle_status=_COMPLETE_BUNDLE,
            verdict=blocking_verdict_from_gate(["plan-completeness-high"]),
        )
        capsys.readouterr()
        assert sink[-1][0].startswith("plan-tool completeness-audit 1-demo")
        assert not any(
            cmd.startswith(("plan-tool run", "plan-tool jira", "plan-tool detail"))
            for cmd, _ in sink
        )


    @pytest.mark.parametrize("with_sink", [True, False])
    def test_empty_set_stage_row_comes_from_the_standalone_block_not_the_parent_sink(
        self, tmp_repo, capsys, monkeypatch, with_sink
    ) -> None:
        """A parent that takes the sink appends the one shared stage itself, so
        the sink stays free of it; the standalone block prints it exactly once."""
        import plan_tool.completeness_report
        import plan_tool.review

        monkeypatch.setattr(
            plan_tool.completeness_report,
            "write_completeness_report",
            lambda *a, **k: tmp_repo.root / "report.md",
        )
        monkeypatch.setattr(
            plan_tool.review, "check_concept_coverage", lambda *a, **k: []
        )
        path = tmp_repo.plans_dir / "1-demo.md"
        path.write_text(_sectioned_plan_text(_CLEAN_STEPS), encoding="utf-8")
        sink: list = []
        args = SimpleNamespace(name="1-demo")
        if with_sink:
            args._next_steps_sink = sink
        _persist_and_present_report(
            SimpleNamespace(title="Demo Plan", steps=[]),
            path,
            args,
            SimpleNamespace(repo_root=tmp_repo.root),
            iterate_enabled=True,
            outcome=_IterateOutcome(stop_reason="done", iterations=1),
            correctness_recs=[],
            conceptual_recs=[],
            grouped_md="## grouped\n",
            bundle_status=_COMPLETE_BUNDLE,
            verdict=blocking_verdict_from_gate([]),
        )
        captured = capsys.readouterr()
        out = captured.out + captured.err
        if with_sink:
            assert sink == []
            assert "plan-tool run 1-demo" not in out
        else:
            assert out.count("plan-tool run 1-demo") == 1


class TestRenderCompletenessJson:
    """``_render_completeness_json`` — the ``--json`` payload shape + rc."""

    def test_payload_keys_present(self, capsys) -> None:
        args = SimpleNamespace(name="myplan", fail_on_findings=False)
        rc = _render_completeness_json(
            args, _empty_det(), [], has_blocking=False
        )
        data = json.loads(capsys.readouterr().out)
        assert data["plan"] == "myplan"
        assert "checks" in data
        assert isinstance(data["has_blocking_findings"], bool)
        for group in (
            "correctness",
            "body_sections",
            "detail_coverage",
            "detail_body",
            "files_coherence",
            "lessons",
            "data_contract",
            "plan_audit",
            "smells",
            "self_consistency",
        ):
            assert group in data["checks"]
        assert data["checks"]["smells"] == []
        assert data["checks"]["self_consistency"] == []
        assert data["checks"]["data_contract"] == []
        assert rc == 0

    def test_plan_audit_bucket_carries_the_restatement(self, capsys) -> None:
        """A headless/CI consumer of ``--json`` is exactly the kind of
        "whoever triages the finding" the restatement exists to reach --
        every other rendering surface (markdown report, interactive walk,
        apply prompt) already carries it."""
        rec = Recommendation(
            id="bare-gap", source="plan-correctness", severity="high",
            step_id=None, title="t", body="body",
            restated_property="the safety net has no route for this case",
        )
        args = SimpleNamespace(name="myplan", fail_on_findings=False)
        _render_completeness_json(args, _empty_det(), [rec], has_blocking=False)
        data = json.loads(capsys.readouterr().out)
        assert data["checks"]["plan_audit"][0]["restated_property"] == (
            "the safety net has no route for this case"
        )

    def test_plan_audit_bucket_treats_whitespace_only_as_absent(self, capsys) -> None:
        """A whitespace-only stored value must read as absent here too, the
        same as every other rendering surface -- this bucket was the one
        that had drifted (round-2 added the field raw, unstripped)."""
        rec = Recommendation(
            id="whitespace-restated", source="plan-correctness", severity="high",
            step_id=None, title="t", body="body", restated_property="   ",
        )
        args = SimpleNamespace(name="myplan", fail_on_findings=False)
        _render_completeness_json(args, _empty_det(), [rec], has_blocking=False)
        data = json.loads(capsys.readouterr().out)
        assert data["checks"]["plan_audit"][0]["restated_property"] is None

    def test_json_payload_includes_data_contract_drift(self, capsys) -> None:
        rec = _rec("medium", source="data-contract", title="contract drift")
        payload = {
            "target_section": "SavedReview",
            "operation": "add",
            "candidate_fields": {"field": "new_field"},
            "freshness": {"registry_fingerprint": "r", "contract_fingerprint": "c"},
        }
        det = _DeterministicReport(
            path_style_hint=None,
            dep_issues=[],
            body_issues=[],
            detail_cov_issues=[],
            detail_body_issues=[],
            files_coh_issues=[],
            lessons_issues=[],
            data_contract_recs=[rec],
            data_contract_payloads={rec.id: payload},
        )
        args = SimpleNamespace(name="p", fail_on_findings=False)
        _render_completeness_json(args, det, [], has_blocking=True)
        data = json.loads(capsys.readouterr().out)
        assert data["checks"]["data_contract"] == [
            {
                "severity": rec.severity,
                "source": "data-contract",
                "id": rec.id,
                "anchor": rec.anchor,
                "title": rec.title,
                "confidence": "limited",
                "message": rec.body,
                "payload": payload,
            }
        ]

    def test_json_payload_includes_input_contract_findings(self, capsys) -> None:
        rec = dataclasses.replace(
            _rec("medium", source="data-contract", title="stale input"),
            body="details/01.md:## Input cites `SavedReview.not_a_field`.",
        )
        payload = {
            "target": "plan-detail",
            "location": "details/01.md:## Input",
            "owner": "SavedReview",
            "field_or_key": "not_a_field",
            "code_anchor": None,
            "reason": "stale",
            "step_id": 1,
            "path": "details/01.md",
            "operation": "validate-input-reference",
        }
        det = dataclasses.replace(
            _empty_det(),
            data_contract_recs=[rec],
            data_contract_payloads={rec.id: payload},
        )
        args = SimpleNamespace(name="p", fail_on_findings=False)
        _render_completeness_json(args, det, [], has_blocking=True)
        data = json.loads(capsys.readouterr().out)
        assert data["checks"]["data_contract"][0]["payload"] == payload

    def test_json_payload_includes_smells_group(self, capsys) -> None:
        smell = _rec("info", source="feature-ref", title="brittle ref")
        det = _det_with_smells([smell])
        args = SimpleNamespace(name="p", fail_on_findings=False)
        _render_completeness_json(args, det, [], has_blocking=False)
        data = json.loads(capsys.readouterr().out)
        assert data["checks"]["smells"] == [
            {
                "severity": smell.severity,
                "source": smell.source,
                "id": smell.id,
                "title": smell.title,
                "confidence": "limited",
                "body": smell.body,
            }
        ]

    def test_json_payload_includes_granularity_in_smells_group(self, capsys) -> None:
        # A granularity rec rides the smells group keyed on ``source``
        # (``granularity-merge``), not an axis.
        gran = _rec("info", source="granularity-merge", title="merge steps")
        det = _det_with_smells([gran])
        args = SimpleNamespace(name="p", fail_on_findings=False)
        _render_completeness_json(args, det, [], has_blocking=False)
        data = json.loads(capsys.readouterr().out)
        assert data["checks"]["smells"] == [
            {
                "severity": gran.severity,
                "source": "granularity-merge",
                "id": gran.id,
                "title": gran.title,
                "confidence": "limited",
                "body": gran.body,
            }
        ]

    def test_medium_mixed_step_finding_in_json_smells(self, capsys) -> None:
        # The medium mixed-step rec rides the ``smells`` group keyed on
        # ``source`` (``granularity-split``), same channel as the info recs.
        mixed = _mixed_step_rec(step_id=1)
        det = _det_with_smells([mixed])
        args = SimpleNamespace(name="p", fail_on_findings=False)
        _render_completeness_json(args, det, [], has_blocking=False)
        data = json.loads(capsys.readouterr().out)
        assert data["checks"]["smells"] == [
            {
                "severity": "medium",
                "source": "granularity-split",
                "id": mixed.id,
                "title": mixed.title,
                "confidence": "limited",
                "body": mixed.body,
            }
        ]

    def test_render_json_includes_self_consistency_group(self, capsys) -> None:
        rec = _rec("medium", source="orphaned-deliverable", title="orphan")
        det = _det_with_self_consistency([rec])
        args = SimpleNamespace(name="p", fail_on_findings=False)
        _render_completeness_json(args, det, [], has_blocking=True)
        data = json.loads(capsys.readouterr().out)
        assert data["checks"]["self_consistency"] == [
            {
                "severity": rec.severity,
                "source": rec.source,
                "id": rec.id,
                "title": rec.title,
                "confidence": "limited",
                "body": rec.body,
            }
        ]
        # The self-consistency rec must not leak into the advisory smells group.
        assert data["checks"]["smells"] == []

    def test_render_json_self_consistency_empty_group_when_none(self, capsys) -> None:
        args = SimpleNamespace(name="p", fail_on_findings=False)
        _render_completeness_json(args, _empty_det(), [], has_blocking=False)
        data = json.loads(capsys.readouterr().out)
        assert data["checks"]["self_consistency"] == []

    def test_json_renders_legacy_confidence_as_unknown(self, capsys) -> None:
        """Public output normalizes a persisted legacy value without changing it."""
        rec = dataclasses.replace(
            _rec("medium", source="feature-ref", title="legacy support"),
            confidence=None,
        )
        _render_completeness_json(
            SimpleNamespace(name="p", fail_on_findings=False),
            _det_with_smells([rec]), [], has_blocking=False,
        )
        data = json.loads(capsys.readouterr().out)
        assert data["checks"]["smells"][0]["confidence"] == "unknown"

    def test_coverage_confirmation_kind_in_payload(self, capsys) -> None:
        # BACKLOG #125 — the low-yield verdict must be machine-readable, not
        # just a stderr/markdown blurb.
        args = SimpleNamespace(name="p", fail_on_findings=False)
        _render_completeness_json(
            args, _empty_det(), [], has_blocking=False,
            budget={
                "budget_limited": False,
                "passes_used": 2,
                "cap": 4,
                "confirmation_kind": "confirmed-low-yield",
            },
        )
        data = json.loads(capsys.readouterr().out)
        assert data["coverage"]["confirmation_kind"] == "confirmed-low-yield"

    def test_coverage_confirmation_kind_none_when_absent(self, capsys) -> None:
        args = SimpleNamespace(name="p", fail_on_findings=False)
        _render_completeness_json(args, _empty_det(), [], has_blocking=False)
        data = json.loads(capsys.readouterr().out)
        assert data["coverage"]["confirmation_kind"] is None

    def test_smells_do_not_affect_has_blocking(self, capsys) -> None:
        # A smell-only det driven through the payload keeps has_blocking
        # false — smells are not a blocking input.
        det = _det_with_smells([_rec("info", source="self-referential")])
        args = SimpleNamespace(name="p", fail_on_findings=True)
        rc = _render_completeness_json(args, det, [], has_blocking=False)
        data = json.loads(capsys.readouterr().out)
        assert data["has_blocking_findings"] is False
        assert rc == 0

    def test_fail_on_findings_rc_mirror(self, capsys) -> None:
        # rc is 1 only when blocking AND the flag is set.
        assert _render_completeness_json(
            SimpleNamespace(name="p", fail_on_findings=True),
            _empty_det(), [], has_blocking=True,
        ) == 1
        capsys.readouterr()
        assert _render_completeness_json(
            SimpleNamespace(name="p", fail_on_findings=True),
            _empty_det(), [], has_blocking=False,
        ) == 0
        capsys.readouterr()
        assert _render_completeness_json(
            SimpleNamespace(name="p", fail_on_findings=False),
            _empty_det(), [], has_blocking=True,
        ) == 0

    def test_halt_fields_in_payload_and_rc(self, capsys) -> None:
        args = SimpleNamespace(name="p", fail_on_findings=True)
        rc = _render_completeness_json(
            args,
            _empty_det(),
            [],
            has_blocking=True,
            halt_reason="plan failed to parse before apply_finding",
            early_exit_code=2,
        )
        data = json.loads(capsys.readouterr().out)
        assert data["halt_reason"] == "plan failed to parse before apply_finding"
        assert data["early_exit_code"] == 2
        assert rc == 2

    def test_json_includes_stage_audit_incomplete_and_bar_ids(self, capsys) -> None:
        args = SimpleNamespace(name="p", fail_on_findings=False)
        _render_completeness_json(
            args,
            _empty_det(),
            [_rec("medium", source="plan-correctness")],
            has_blocking=True,
            audit_stage=STAGE_BARE,
            audit_incomplete=False,
            conceptual_bar_blocking_ids=("plan-correctness-medium",),
        )
        data = json.loads(capsys.readouterr().out)
        assert data["stage"] == "bare"
        assert data["audit_incomplete"] is False
        assert data["conceptual_bar_blocking_ids"] == ["plan-correctness-medium"]
        assert data["has_blocking_findings"] is True

    def test_json_conceptual_bar_ids_null_when_audit_incomplete(self, capsys) -> None:
        args = SimpleNamespace(name="p", fail_on_findings=False)
        _render_completeness_json(
            args,
            _empty_det(),
            [],
            has_blocking=False,
            audit_incomplete=True,
            conceptual_bar_blocking_ids=(),
        )
        data = json.loads(capsys.readouterr().out)
        assert data["conceptual_bar_blocking_ids"] is None
        assert data["conceptual_bar_blocking_ids"] != []

    def test_json_fail_on_findings_exits_one_on_audit_incomplete(self, capsys) -> None:
        args = SimpleNamespace(name="p", fail_on_findings=True)
        rc = _render_completeness_json(
            args,
            _empty_det(),
            [],
            has_blocking=False,
            audit_incomplete=True,
            finalize_not_clean=True,
        )
        capsys.readouterr()
        assert rc == 1

    def test_json_fail_on_findings_exits_one_on_bar_blocker(self, capsys) -> None:
        args = SimpleNamespace(name="p", fail_on_findings=True)
        rc = _render_completeness_json(
            args,
            _empty_det(),
            [_rec("medium", source="plan-correctness")],
            has_blocking=True,
            audit_stage=STAGE_DETAIL,
            finalize_not_clean=True,
        )
        capsys.readouterr()
        assert rc == 1

    def test_json_includes_stop_reason_when_iterate_ran(self, capsys) -> None:
        args = SimpleNamespace(name="p", fail_on_findings=False)
        _render_completeness_json(
            args,
            _empty_det(),
            [],
            has_blocking=False,
            stop_reason="converged",
        )
        data = json.loads(capsys.readouterr().out)
        assert data["stop_reason"] == "converged"

    def test_plan_quota_json_reports_unconfirmed_early_stop(self, capsys) -> None:
        coverage = {
            "budget_limited": False,
            "passes_used": 2,
            "cap": 3,
            "recommendation_kind": None,
            "recommended_passes": None,
            "recommendation_advice": None,
            "confirmation_kind": None,
            "conforming_pass_count": 1,
            "failed_or_malformed_pass_count": 1,
            "early_stop_reason": "plan-quota",
        }

        rc = _render_completeness_json(
            SimpleNamespace(name="p", fail_on_findings=False),
            _empty_det(),
            [],
            has_blocking=False,
            budget=coverage,
            audit_incomplete=True,
            conceptual_bar_blocking_ids=("must-not-publish",),
        )

        payload = json.loads(capsys.readouterr().out)
        assert rc == 0
        assert payload["coverage"]["early_stop_reason"] == "plan-quota"
        assert payload["coverage"]["budget_limited"] is False
        assert payload["audit_incomplete"] is True
        assert payload["conceptual_bar_blocking_ids"] is None


class TestPersistAndPresentReport:
    """``_persist_and_present_report`` — the persistence tail. Keeps
    ``build_report_md`` / ``console_summary`` real; only the write seam is
    injected, on the domain module."""

    def test_writes_report_and_returns_path(self, tmp_repo, capsys) -> None:
        path = tmp_repo.plans_dir / "1-demo.md"
        path.write_text(_sectioned_plan_text(_CLEAN_STEPS), encoding="utf-8")
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        report_path = _persist_and_present_report(
            SimpleNamespace(title="Demo Plan", steps=[]),
            path,
            SimpleNamespace(name="1-demo"),
            ctx,
            iterate_enabled=False,
            outcome=_IterateOutcome(),
            correctness_recs=[],
            conceptual_recs=[],
            grouped_md="## grouped\n",
        )
        assert report_path is not None
        assert report_path.is_file()
        assert "Completeness report saved to" in capsys.readouterr().out

    def test_plan_quota_markdown_report_omits_final_reusable_sidecar(
        self, tmp_repo, capsys
    ) -> None:
        path = tmp_repo.plans_dir / "1-demo.md"
        path.write_text(_sectioned_plan_text(_CLEAN_STEPS), encoding="utf-8")
        report_path = _persist_and_present_report(
            SimpleNamespace(title="Demo Plan", steps=[]),
            path,
            SimpleNamespace(name="1-demo"),
            SimpleNamespace(repo_root=tmp_repo.root),
            iterate_enabled=False,
            outcome=_IterateOutcome(),
            correctness_recs=[],
            conceptual_recs=[],
            grouped_md="## grouped\n",
            audit_coverage={"early_stop_reason": "plan-quota"},
        )

        assert report_path is not None
        assert report_path.is_file()
        assert not report_path.with_suffix(".json").exists()

    def test_plan_mass_failure_is_swallowed_report_still_written(
        self, tmp_repo, capsys, monkeypatch
    ) -> None:
        """#238: compute_plan_mass is best-effort — a failure there must not
        turn an otherwise-successful completeness audit into a crash or a
        withheld report (reporting-only scope fence, BACKLOG #238)."""
        import plan_tool.completeness_report

        def boom(*args, **kwargs):
            raise RuntimeError("disk read failed mid-scan")

        monkeypatch.setattr(
            plan_tool.completeness_report, "compute_plan_mass", boom
        )
        path = tmp_repo.plans_dir / "1-demo.md"
        path.write_text(_sectioned_plan_text(_CLEAN_STEPS), encoding="utf-8")
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        report_path = _persist_and_present_report(
            SimpleNamespace(title="Demo Plan", steps=[]),
            path,
            SimpleNamespace(name="1-demo"),
            ctx,
            iterate_enabled=False,
            outcome=_IterateOutcome(),
            correctness_recs=[],
            conceptual_recs=[],
            grouped_md="## grouped\n",
        )
        assert report_path is not None
        assert report_path.is_file()
        assert "## Plan mass" not in report_path.read_text(encoding="utf-8")

    def test_plan_mass_failure_skips_first_saved_plan_mass_lookup(
        self, tmp_repo, capsys, monkeypatch
    ) -> None:
        """#238: when compute_plan_mass_best_effort returns None, there is
        no delta baseline to render — first_saved_plan_mass must not still
        scan and load every saved sidecar for nothing."""
        import plan_tool.completeness_report

        monkeypatch.setattr(
            plan_tool.completeness_report,
            "compute_plan_mass_best_effort",
            lambda *a, **k: None,
        )

        def must_not_be_called(*args, **kwargs):
            raise AssertionError("first_saved_plan_mass should be skipped")

        monkeypatch.setattr(
            plan_tool.completeness_report,
            "first_saved_plan_mass",
            must_not_be_called,
        )
        path = tmp_repo.plans_dir / "1-demo.md"
        path.write_text(_sectioned_plan_text(_CLEAN_STEPS), encoding="utf-8")
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        report_path = _persist_and_present_report(
            SimpleNamespace(title="Demo Plan", steps=[]),
            path,
            SimpleNamespace(name="1-demo"),
            ctx,
            iterate_enabled=False,
            outcome=_IterateOutcome(),
            correctness_recs=[],
            conceptual_recs=[],
            grouped_md="## grouped\n",
        )
        assert report_path is not None

    def test_oserror_is_swallowed_returns_none(
        self, tmp_repo, capsys, monkeypatch
    ) -> None:
        import plan_tool.completeness_report

        def boom(*args, **kwargs):
            raise OSError("disk full")

        monkeypatch.setattr(
            plan_tool.completeness_report, "write_completeness_report", boom
        )
        path = tmp_repo.plans_dir / "1-demo.md"
        path.write_text(_sectioned_plan_text(_CLEAN_STEPS), encoding="utf-8")
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        report_path = _persist_and_present_report(
            SimpleNamespace(title="Demo Plan", steps=[]),
            path,
            SimpleNamespace(name="1-demo"),
            ctx,
            iterate_enabled=False,
            outcome=_IterateOutcome(),
            correctness_recs=[],
            conceptual_recs=[],
            grouped_md="## grouped\n",
        )
        assert report_path is None
        assert "could not write completeness report" in capsys.readouterr().err

    def test_final_qualified_result_reaches_parent_sink(
        self, tmp_repo, capsys
    ) -> None:
        from plan_tool.review_persistence import AuditInputSnapshot

        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        result = {
            "headline": "clean",
            "stage": "detail",
            "coverage": "confirmed",
            "revision_status": "current",
            "audit_revision": AuditInputSnapshot.capture(
                path, tmp_repo.root
            ).revision,
        }
        sink: list[object] = []
        _persist_and_present_report(
            plan,
            path,
            SimpleNamespace(
                name="1-sectioned", _final_qualified_result_sink=sink
            ),
            SimpleNamespace(repo_root=tmp_repo.root),
            iterate_enabled=False,
            outcome=_IterateOutcome(qualified_result=result),
            correctness_recs=[],
            conceptual_recs=[],
            grouped_md="## grouped\n",
        )
        assert sink == [result]
        assert sink[0] is result

    def test_pre_apply_checkpoint_does_not_reach_parent_sink(
        self, tmp_repo
    ) -> None:
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        bundle_status, _audit_stage = _hoisted_bundle(plan, path, tmp_repo.root)
        sink: list[object] = []
        write_pre_apply_audit_checkpoint(
            plan,
            path,
            SimpleNamespace(repo_root=tmp_repo.root),
            SimpleNamespace(
                name="1-sectioned", _final_qualified_result_sink=sink
            ),
            audit_recs=[_corr_rec("c")],
            budget={},
            bundle_status=bundle_status,
        )
        assert sink == []

    def test_persist_passes_union_and_fingerprints(
        self, tmp_repo, capsys, monkeypatch
    ) -> None:
        """The caller computes both fingerprints and persists the
        correctness+conceptual union (correctness first)."""
        import plan_tool.completeness_report
        import plan_tool.fingerprint
        import plan_tool.review_persistence

        captured: dict = {}

        def spy(*args, **kwargs):
            captured.update(kwargs)
            return tmp_repo.root / "report.md"

        monkeypatch.setattr(
            plan_tool.completeness_report, "write_completeness_report", spy
        )
        monkeypatch.setattr(
            plan_tool.review_persistence,
            "compute_plan_fingerprint",
            lambda _p: "PLAN_FP",
        )
        monkeypatch.setattr(
            plan_tool.fingerprint,
            "compute_code_fingerprint",
            lambda *a, **k: {"plan_tool/x.py": "CODE_FP"},
        )
        path = tmp_repo.plans_dir / "1-demo.md"
        path.write_text(_sectioned_plan_text(_CLEAN_STEPS), encoding="utf-8")
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        corr = _rec("high", source="plan-correctness", title="corr")
        concept = _rec("medium", source="plan-completeness", title="concept")
        _persist_and_present_report(
            SimpleNamespace(title="Demo Plan", steps=[]),
            path,
            SimpleNamespace(name="1-demo"),
            ctx,
            iterate_enabled=False,
            outcome=_IterateOutcome(),
            correctness_recs=[corr],
            conceptual_recs=[concept],
            grouped_md="## grouped\n",
        )
        assert captured["recommendations"] == [corr, concept]
        assert captured["plan_fingerprint"] == "PLAN_FP"
        assert captured["code_fingerprint"] == {"plan_tool/x.py": "CODE_FP"}

    def test_persist_forwards_audit_shape_advisory(
        self, tmp_repo, capsys, monkeypatch
    ) -> None:
        import plan_tool.completeness_report
        from plan_tool.audit_shapes import AuditShapeAdvisory

        captured: dict = {}
        monkeypatch.setattr(
            plan_tool.completeness_report,
            "write_completeness_report",
            lambda *_args, **kwargs: (
                captured.update(kwargs) or tmp_repo.root / "report.md"
            ),
        )
        advisory = AuditShapeAdvisory(
            shape_id="arm-clustering",
            source_plan_fingerprint="snapshot",
            arm_step_ids=(1, 2, 3),
            material_finding_ids=("a", "b", "c"),
            arm_finding_ids=("a", "b", "c"),
            material_finding_evidence=(),
            material_finding_count=3,
            arm_finding_count=3,
            committed_step_count=5,
        )
        path = tmp_repo.plans_dir / "1-demo.md"
        path.write_text(_sectioned_plan_text(_CLEAN_STEPS), encoding="utf-8")
        _persist_and_present_report(
            SimpleNamespace(title="Demo Plan", steps=[]),
            path,
            SimpleNamespace(name="1-demo"),
            SimpleNamespace(repo_root=tmp_repo.root),
            iterate_enabled=False,
            outcome=_IterateOutcome(),
            correctness_recs=[],
            conceptual_recs=[],
            grouped_md="## grouped\n",
            audit_shape_advisory=advisory,
        )

        assert captured["audit_shape_advisory"] is advisory

    def test_persist_folds_medium_granularity_split_into_sidecar(
        self, tmp_repo, capsys, monkeypatch
    ) -> None:
        # The medium mixed-step ``granularity-split`` rec rides ``smell_recs``
        # and is now persisted to the sidecar (after the correctness/conceptual/
        # data-contract recs) so completeness-apply can replay it through the
        # split bridge.
        import plan_tool.completeness_report

        captured: dict = {}

        def spy(*args, **kwargs):
            captured.update(kwargs)
            return tmp_repo.root / "report.md"

        monkeypatch.setattr(
            plan_tool.completeness_report, "write_completeness_report", spy
        )
        path = tmp_repo.plans_dir / "1-demo.md"
        path.write_text(_sectioned_plan_text(_CLEAN_STEPS), encoding="utf-8")
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        corr = _rec("high", source="plan-correctness", title="corr")
        concept = _rec("medium", source="plan-completeness", title="concept")
        drift = _rec("medium", source="data-contract", title="contract")
        mixed = _mixed_step_rec(step_id=2)
        _persist_and_present_report(
            SimpleNamespace(title="Demo Plan", steps=[]),
            path,
            SimpleNamespace(name="1-demo"),
            ctx,
            iterate_enabled=False,
            outcome=_IterateOutcome(),
            correctness_recs=[corr],
            conceptual_recs=[concept],
            data_contract_recs=[drift],
            grouped_md="## grouped\n",
            smell_recs=[mixed],
        )
        assert captured["recommendations"] == [corr, concept, drift, mixed]
        assert mixed.step_id == 2

    def test_persist_drops_info_granularity_split_from_sidecar(
        self, tmp_repo, capsys, monkeypatch
    ) -> None:
        # An ``info`` (deterministic) split rec stays advisory-only — only the
        # ``medium`` prose MIXED-STEP rec is persisted.
        import plan_tool.completeness_report

        captured: dict = {}

        def spy(*args, **kwargs):
            captured.update(kwargs)
            return tmp_repo.root / "report.md"

        monkeypatch.setattr(
            plan_tool.completeness_report, "write_completeness_report", spy
        )
        path = tmp_repo.plans_dir / "1-demo.md"
        path.write_text(_sectioned_plan_text(_CLEAN_STEPS), encoding="utf-8")
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        info_split = _rec("info", source="granularity-split", title="deterministic split")
        _persist_and_present_report(
            SimpleNamespace(title="Demo Plan", steps=[]),
            path,
            SimpleNamespace(name="1-demo"),
            ctx,
            iterate_enabled=False,
            outcome=_IterateOutcome(),
            correctness_recs=[],
            conceptual_recs=[],
            grouped_md="## grouped\n",
            smell_recs=[info_split],
        )
        assert captured["recommendations"] == []

    def test_persist_drops_granularity_merge_from_sidecar(
        self, tmp_repo, capsys, monkeypatch
    ) -> None:
        # ``granularity-merge`` is not the split-bridge family; it stays
        # advisory-only regardless of severity.
        import plan_tool.completeness_report

        captured: dict = {}

        def spy(*args, **kwargs):
            captured.update(kwargs)
            return tmp_repo.root / "report.md"

        monkeypatch.setattr(
            plan_tool.completeness_report, "write_completeness_report", spy
        )
        path = tmp_repo.plans_dir / "1-demo.md"
        path.write_text(_sectioned_plan_text(_CLEAN_STEPS), encoding="utf-8")
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        merge_med = _rec("medium", source="granularity-merge", title="merge medium")
        merge_info = _rec("info", source="granularity-merge", title="merge info")
        _persist_and_present_report(
            SimpleNamespace(title="Demo Plan", steps=[]),
            path,
            SimpleNamespace(name="1-demo"),
            ctx,
            iterate_enabled=False,
            outcome=_IterateOutcome(),
            correctness_recs=[],
            conceptual_recs=[],
            grouped_md="## grouped\n",
            smell_recs=[merge_med, merge_info],
        )
        assert captured["recommendations"] == []

    def test_persist_drops_repo_structural_smell_from_sidecar(
        self, tmp_repo, capsys, monkeypatch
    ) -> None:
        # A non-granularity smell (e.g. brittle feature ref) stays advisory-only.
        import plan_tool.completeness_report

        captured: dict = {}

        def spy(*args, **kwargs):
            captured.update(kwargs)
            return tmp_repo.root / "report.md"

        monkeypatch.setattr(
            plan_tool.completeness_report, "write_completeness_report", spy
        )
        path = tmp_repo.plans_dir / "1-demo.md"
        path.write_text(_sectioned_plan_text(_CLEAN_STEPS), encoding="utf-8")
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        smell = _rec("medium", source="feature-ref", title="brittle feature ref")
        _persist_and_present_report(
            SimpleNamespace(title="Demo Plan", steps=[]),
            path,
            SimpleNamespace(name="1-demo"),
            ctx,
            iterate_enabled=False,
            outcome=_IterateOutcome(),
            correctness_recs=[],
            conceptual_recs=[],
            grouped_md="## grouped\n",
            smell_recs=[smell],
        )
        assert captured["recommendations"] == []

    def test_persist_preserves_existing_union_when_no_medium_split(
        self, tmp_repo, capsys, monkeypatch
    ) -> None:
        # With no medium split in ``smell_recs`` the persisted union is the
        # prior correctness+conceptual+data-contract set, order intact.
        import plan_tool.completeness_report

        captured: dict = {}

        def spy(*args, **kwargs):
            captured.update(kwargs)
            return tmp_repo.root / "report.md"

        monkeypatch.setattr(
            plan_tool.completeness_report, "write_completeness_report", spy
        )
        path = tmp_repo.plans_dir / "1-demo.md"
        path.write_text(_sectioned_plan_text(_CLEAN_STEPS), encoding="utf-8")
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        corr = _rec("high", source="plan-correctness", title="corr")
        concept = _rec("medium", source="plan-completeness", title="concept")
        drift = _rec("medium", source="data-contract", title="contract")
        info_split = _rec("info", source="granularity-split", title="deterministic split")
        _persist_and_present_report(
            SimpleNamespace(title="Demo Plan", steps=[]),
            path,
            SimpleNamespace(name="1-demo"),
            ctx,
            iterate_enabled=False,
            outcome=_IterateOutcome(),
            correctness_recs=[corr],
            conceptual_recs=[concept],
            data_contract_recs=[drift],
            grouped_md="## grouped\n",
            smell_recs=[info_split],
        )
        assert captured["recommendations"] == [corr, concept, drift]

    def test_persist_passes_data_contract_recommendations(
        self, tmp_repo, capsys, monkeypatch
    ) -> None:
        import plan_tool.completeness_report

        captured: dict = {}

        def spy(*args, **kwargs):
            captured.update(kwargs)
            return tmp_repo.root / "report.md"

        monkeypatch.setattr(
            plan_tool.completeness_report, "write_completeness_report", spy
        )
        path = tmp_repo.plans_dir / "1-demo.md"
        path.write_text(_sectioned_plan_text(_CLEAN_STEPS), encoding="utf-8")
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        corr = _rec("high", source="plan-correctness", title="corr")
        concept = _rec("medium", source="plan-completeness", title="concept")
        drift = _rec("medium", source="data-contract", title="contract")
        _persist_and_present_report(
            SimpleNamespace(title="Demo Plan", steps=[]),
            path,
            SimpleNamespace(name="1-demo"),
            ctx,
            iterate_enabled=False,
            outcome=_IterateOutcome(),
            correctness_recs=[corr],
            conceptual_recs=[concept],
            data_contract_recs=[drift],
            grouped_md="## grouped\n",
        )
        assert captured["recommendations"] == [corr, concept, drift]

    def test_persist_passes_data_contract_payloads(
        self, tmp_repo, capsys, monkeypatch
    ) -> None:
        import plan_tool.completeness_report

        captured: dict = {}

        def spy(*args, **kwargs):
            captured.update(kwargs)
            return tmp_repo.root / "report.md"

        monkeypatch.setattr(
            plan_tool.completeness_report, "write_completeness_report", spy
        )
        path = tmp_repo.plans_dir / "1-demo.md"
        path.write_text(_sectioned_plan_text(_CLEAN_STEPS), encoding="utf-8")
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        drift = _rec("medium", source="data-contract", title="contract")
        payload = {
            drift.id: {
                "target_section": "SavedReview",
                "operation": "add",
                "candidate_fields": {"field": "new_field"},
                "freshness": {
                    "registry_fingerprint": "r",
                    "contract_fingerprint": "c",
                },
            }
        }
        _persist_and_present_report(
            SimpleNamespace(title="Demo Plan", steps=[]),
            path,
            SimpleNamespace(name="1-demo"),
            ctx,
            iterate_enabled=False,
            outcome=_IterateOutcome(),
            correctness_recs=[],
            conceptual_recs=[],
            data_contract_recs=[drift],
            data_contract_payloads=payload,
            grouped_md="## grouped\n",
        )
        assert captured["data_contract_payloads"] == payload

    def test_persist_report_forwards_input_contract_recommendations(
        self, tmp_repo, capsys, monkeypatch
    ) -> None:
        import plan_tool.completeness_report

        captured: dict = {}

        def spy(*args, **kwargs):
            captured.update(kwargs)
            return tmp_repo.root / "report.md"

        monkeypatch.setattr(
            plan_tool.completeness_report, "write_completeness_report", spy
        )
        path = tmp_repo.plans_dir / "1-demo.md"
        path.write_text(_sectioned_plan_text(_CLEAN_STEPS), encoding="utf-8")
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        rec = _rec("medium", source="data-contract", title="stale input")
        payload = {
            rec.id: {
                "target": "plan-detail",
                "location": "details/01.md:## Input",
                "operation": "validate-input-reference",
            }
        }
        _persist_and_present_report(
            SimpleNamespace(title="Demo Plan", steps=[]),
            path,
            SimpleNamespace(name="1-demo"),
            ctx,
            iterate_enabled=False,
            outcome=_IterateOutcome(),
            correctness_recs=[],
            conceptual_recs=[],
            data_contract_recs=[rec],
            data_contract_payloads=payload,
            grouped_md="## grouped\n",
        )
        assert captured["recommendations"] == [rec]
        assert captured["data_contract_payloads"] == payload

    def test_persist_and_present_passes_bundle_status_to_console_summary(
        self, tmp_repo, capsys, monkeypatch
    ) -> None:
        import plan_tool.completeness_report

        monkeypatch.setattr(
            plan_tool.completeness_report,
            "write_completeness_report",
            lambda *a, **k: tmp_repo.root / "report.md",
        )
        path = tmp_repo.plans_dir / "1-demo.md"
        path.write_text(_sectioned_plan_text(_CLEAN_STEPS), encoding="utf-8")
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        conceptual = [_rec("medium", source="plan-completeness")]
        _persist_and_present_report(
            SimpleNamespace(title="Demo Plan", steps=[]),
            path,
            SimpleNamespace(name="1-demo"),
            ctx,
            iterate_enabled=True,
            outcome=_IterateOutcome(
                stop_reason="done",
                iterations=1,
                resumed_from_sampler_checkpoint=True,
            ),
            correctness_recs=[],
            conceptual_recs=conceptual,
            grouped_md="## grouped\n",
            bundle_status=SimpleNamespace(
                is_bare=True,
                is_fully_bare=True,
                detailed_count=0,
                total=1,
            ),
        )
        out = capsys.readouterr().out
        # No verdict reached the console: the gap is listed as advisory.
        assert "advisory  1 conceptual gap(s)" in out
        assert "informational until a complete detail bundle exists" in out
        assert "provenance resumed from a durable sampler pass boundary" in out
        advisory_line = next(
            line for line in out.splitlines() if line.strip().startswith("advisory")
        )
        assert "completeness-apply" not in advisory_line

    def test_persist_and_present_bare_clean_prints_detail_next_step(
        self, tmp_repo, capsys, monkeypatch
    ) -> None:
        import plan_tool.completeness_report
        import plan_tool.review

        monkeypatch.setattr(
            plan_tool.completeness_report,
            "write_completeness_report",
            lambda *a, **k: tmp_repo.root / "report.md",
        )
        monkeypatch.setattr(
            plan_tool.review, "check_concept_coverage", lambda *a, **k: []
        )
        path = tmp_repo.plans_dir / "1-demo.md"
        path.write_text(_sectioned_plan_text(_CLEAN_STEPS), encoding="utf-8")
        _persist_and_present_report(
            SimpleNamespace(title="Demo Plan", steps=[]),
            path,
            SimpleNamespace(name="1-demo"),
            SimpleNamespace(repo_root=tmp_repo.root),
            iterate_enabled=True,
            outcome=_IterateOutcome(stop_reason="done", iterations=1),
            correctness_recs=[],
            conceptual_recs=[],
            grouped_md="## grouped\n",
            bundle_status=SimpleNamespace(
                is_bare=True,
                is_fully_bare=True,
                detailed_count=0,
                total=1,
            ),
            verdict=_CLEAR_VERDICT,
        )
        captured = capsys.readouterr()
        assert "Next steps:" in captured.err
        assert "plan-tool detail 1-demo" in captured.err
        assert "plan-tool run 1-demo" not in captured.err

    def test_skip_sidecar_write_suppresses_persist_but_presents(
        self, tmp_repo, capsys, monkeypatch
    ) -> None:
        """``skip_sidecar_write=True`` short-circuits the write (so
        ``write_completeness_report`` never fires and no path is returned)
        while the grouped report is still printed."""
        import plan_tool.completeness_report

        def boom(*args, **kwargs):  # pragma: no cover - must not be reached
            raise AssertionError("write_completeness_report must not run")

        monkeypatch.setattr(
            plan_tool.completeness_report, "write_completeness_report", boom
        )
        path = tmp_repo.plans_dir / "1-demo.md"
        path.write_text(_sectioned_plan_text(_CLEAN_STEPS), encoding="utf-8")
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        report_path = _persist_and_present_report(
            SimpleNamespace(title="Demo Plan", steps=[]),
            path,
            SimpleNamespace(name="1-demo"),
            ctx,
            iterate_enabled=False,
            outcome=_IterateOutcome(),
            correctness_recs=[],
            conceptual_recs=[],
            grouped_md="## grouped\n",
            skip_sidecar_write=True,
        )
        out = capsys.readouterr().out
        assert report_path is None
        assert "grouped" in out
        assert "Completeness report saved to" not in out

    def test_pre_apply_checkpoint_sidecar_is_marked_and_v4(
        self, tmp_repo
    ) -> None:
        """The one producer of crash-recovery evidence marks its sidecar, so a
        role-unaware version-1/2 reader rejects it instead of reading it as a
        converged final report."""
        from plan_tool.review_persistence import AuditInputSnapshot

        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        bundle_status, audit_stage = _hoisted_bundle(plan, path, tmp_repo.root)
        snapshot = AuditInputSnapshot.capture(path, tmp_repo.root)
        report_path = write_pre_apply_audit_checkpoint(
            plan,
            path,
            ctx,
            SimpleNamespace(name="1-sectioned"),
            audit_recs=[_corr_rec("c")],
            budget={},
            bundle_status=bundle_status,
            audit_input_snapshot=snapshot,
            audit_stage=audit_stage,
        )
        assert report_path is not None
        assert report_path.name.endswith("-completeness.md")
        sidecar = report_path.with_suffix(".json")
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        assert payload["version"] == 4
        assert payload["is_pre_apply_checkpoint"] is True
        assert payload["qualified_result"] is None
        assert payload["checkpoint_audit_revision"] == snapshot.revision
        assert "audit_revision" not in payload
        saved = load_review(sidecar)
        assert saved.is_pre_apply_checkpoint is True
        assert saved.audit_revision == snapshot.revision
        from plan_tool.review_persistence import update_annotation

        update_annotation(sidecar, "c", Annotation(status="skip"))
        rewritten = json.loads(sidecar.read_text(encoding="utf-8"))
        assert rewritten["checkpoint_audit_revision"] == snapshot.revision

    def test_iterate_plan_quota_keeps_checkpoint_sidecar(
        self, tmp_repo
    ) -> None:
        from plan_tool.completeness_report import is_reusable_audit_sidecar
        from plan_tool.review_persistence import AuditInputSnapshot

        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        bundle_status, audit_stage = _hoisted_bundle(plan, path, tmp_repo.root)
        coverage = {
            "budget_limited": False,
            "passes_used": 1,
            "cap": 3,
            "recommendation_kind": None,
            "recommended_passes": None,
            "recommendation_advice": None,
            "confirmation_kind": None,
            "conforming_pass_count": 0,
            "failed_or_malformed_pass_count": 1,
            "early_stop_reason": "plan-quota",
        }
        report_path = write_pre_apply_audit_checkpoint(
            plan,
            path,
            SimpleNamespace(repo_root=tmp_repo.root),
            SimpleNamespace(name="1-sectioned"),
            audit_recs=[_corr_rec("quota")],
            budget=coverage,
            bundle_status=bundle_status,
            audit_input_snapshot=AuditInputSnapshot.capture(path, tmp_repo.root),
            audit_stage=audit_stage,
        )

        assert report_path is not None
        checkpoint = load_review(report_path.with_suffix(".json"))
        assert checkpoint.is_pre_apply_checkpoint is True
        assert checkpoint.audit_coverage == coverage
        assert is_reusable_audit_sidecar(checkpoint) is False

    def test_iterate_final_report_omits_checkpoint_marker(
        self, tmp_repo, capsys
    ) -> None:
        """Iteration mode alone does not classify a report: an iterative run's
        final save stays an ordinary final artifact."""
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        report_path = _persist_and_present_report(
            plan,
            path,
            SimpleNamespace(name="1-sectioned"),
            ctx,
            iterate_enabled=True,
            outcome=_IterateOutcome(stop_reason="done", iterations=1),
            correctness_recs=[_corr_rec("c")],
            conceptual_recs=[],
            grouped_md="## grouped\n",
        )
        assert report_path is not None
        sidecar = report_path.with_suffix(".json")
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        assert "is_pre_apply_checkpoint" not in payload
        assert payload["version"] != 3
        assert load_review(sidecar).is_pre_apply_checkpoint is False

# --- Step 6: saved-audit reuse flags + decision helper -------------------


def _ru(
    *,
    fresh: bool = True,
    plan_match: bool = True,
    code_match: bool = True,
    drifted_code=None,
    created_at: str = "2026-05-05T12:34:56Z",
    correctness=None,
    conceptual=None,
    audit_coverage=None,
) -> ReusableAudit:
    """Hand-build a :class:`ReusableAudit`. ``saved`` only needs
    ``created_at`` for the helper under test, so a lightweight namespace
    stands in for the full :class:`SavedReview`."""
    return ReusableAudit(
        saved=SimpleNamespace(created_at=created_at),
        correctness_recs=correctness if correctness is not None else [],
        conceptual_recs=conceptual if conceptual is not None else [],
        fresh=fresh,
        plan_match=plan_match,
        code_match=code_match,
        drifted_code=drifted_code if drifted_code is not None else [],
        audit_coverage=(
            audit_coverage
            if audit_coverage is not None
            else {
                "evidence_status": "unknown-legacy",
                "budget_limited": None,
                "passes_used": None,
                "cap": None,
                "recommendation_kind": None,
                "recommended_passes": None,
                "recommendation_advice": None,
                "confirmation_kind": None,
            }
        ),
    )


def _observed_audit_coverage(
    *,
    budget_limited: bool,
    passes_used: int,
    cap: int,
    confirmation_kind: str | None,
    conforming_pass_count: int = 1,
    failed_or_malformed_pass_count: int = 0,
) -> dict[str, object]:
    """A reusable audit's public known-coverage result."""
    return {
        "evidence_status": "observed",
        "budget_limited": budget_limited,
        "passes_used": passes_used,
        "cap": cap,
        "recommendation_kind": None,
        "recommended_passes": None,
        "recommendation_advice": None,
        "confirmation_kind": confirmation_kind,
        "conforming_pass_count": conforming_pass_count,
        "failed_or_malformed_pass_count": failed_or_malformed_pass_count,
    }


def _reuse_args(**overrides) -> SimpleNamespace:
    """Args namespace for ``_resolve_audit_reuse`` with reuse-relevant
    defaults (mirroring the parsed ``completeness-audit`` namespace)."""
    base = dict(
        name="myplan",
        reuse_audit=None,
        reuse_audit_id=None,
        audit_passes=None,
        yes=False,
        json=False,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


# A step that owns a code file, for the attributed code-drift warning.
_FILE_STEP = (
    "steps:\n"
    "  - id: 1\n"
    "    title: Wire it\n"
    "    files:\n"
    "      - plan_tool/widget.py\n"
)


class TestReuseAuditFlagParsing:
    """``--reuse-audit`` / ``--no-reuse-audit`` / ``--reuse-audit-id`` land
    on the ``completeness-audit`` subparser with the documented defaults."""

    def _parse(self, *flags):
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="cmd")
        register(sub)
        return parser.parse_args(["completeness-audit", "myplan", *flags])

    def test_reuse_audit_default_is_none(self) -> None:
        assert self._parse().reuse_audit is None

    def test_no_reuse_audit_sets_false(self) -> None:
        assert self._parse("--no-reuse-audit").reuse_audit is False

    def test_reuse_audit_sets_true(self) -> None:
        assert self._parse("--reuse-audit").reuse_audit is True

    def test_reuse_audit_id_captures_stem(self) -> None:
        stem = "20260505-120000-completeness"
        assert self._parse("--reuse-audit-id", stem).reuse_audit_id == stem

    def test_audit_passes_default_is_none_sentinel(self) -> None:
        # ``None`` (not the numeric default) is the unset sentinel the reuse
        # decision reads as "not passed explicitly".
        assert self._parse().audit_passes is None
        assert self._parse("--audit-passes", "3").audit_passes == 3

    def test_purity_defaults_off_and_is_opt_in(self) -> None:
        # The advisory per-step purity pass is opt-in: measured at zero
        # reported findings against a dominant call-timeout rate, so it stays
        # off until it is evaluable (BACKLOG #210). ``--no-purity`` keeps
        # parsing — it is now a no-op — so existing recipes don't break.
        assert self._parse().purity is False
        assert self._parse("--purity").purity is True
        assert self._parse("--no-purity").purity is False

    def test_audit_samples_deprecated_alias_maps_to_audit_passes(self) -> None:
        # The legacy ``--audit-samples`` flag is kept as a deprecated alias on
        # the same ``audit_passes`` dest, so old invocations still parse.
        assert self._parse("--audit-samples", "3").audit_passes == 3


class TestCompletenessFencePreflight:
    def test_unmatched_fence_writes_no_completeness_report_or_sidecar(
        self, registered_plan, capsys
    ) -> None:
        from plan_tool.cli import main

        plan_path = registered_plan.plans_dir / "1-demo.md"
        plan_path.write_text(
            plan_path.read_text(encoding="utf-8") + "\n```\n",
            encoding="utf-8",
        )

        assert main(registered_plan.argv("completeness-audit", "demo")) == 2
        assert "unmatched opening code fence" in capsys.readouterr().err
        reports = plan_reports_dir(plan_path)
        assert not reports.exists()


def _spy_detectors(monkeypatch, names) -> list[str]:
    """Record which of ``names`` the battery calls, keeping real behavior.

    Patches on the *domain* module, which is where each registry lambda
    resolves its detector at call time.
    """
    import plan_tool.review

    called: list[str] = []

    def wrap(name):
        real = getattr(plan_tool.review, name)

        def spy(*args, **kwargs):
            called.append(name)
            return real(*args, **kwargs)

        return spy

    for name in names:
        monkeypatch.setattr(plan_tool.review, name, wrap(name))
    return called


class TestRunGradeDeterministicBattery:
    """The retained detector dispatch order."""


    def test_deterministic_detector_registry_dispatches_retained_run_grade_checks(
        self, tmp_repo, monkeypatch
    ) -> None:
        from plan_tool.review import DetectorRegistry

        dispatched: list[str] = []
        run_all = DetectorRegistry.run_all

        def spy(self, det_ctx):
            dispatched.extend(self.keys)
            return run_all(self, det_ctx)

        monkeypatch.setattr(DetectorRegistry, "run_all", spy)
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        _run_deterministic_checks(
            plan, path, SimpleNamespace(repo_root=tmp_repo.root),
            plan_name="p", quiet=True,
        )
        assert tuple(dispatched) == _REGISTRY_KEYS


@pytest.mark.integration
class TestRunGradeReportSurfaces:
    """The retained report, sidecar, JSON, and format-validation surfaces."""

    def _stub_audit(self, monkeypatch):
        import plan_tool.review

        monkeypatch.setattr(
            plan_tool.review, "audit_plan_until_stable", lambda *a, **k: []
        )

    def _sectioned_plan(self, registered_plan):
        """Give the registered plan its required body sections."""
        from plan_tool.parser import parse_plan

        path = registered_plan.plans_dir / "1-demo.md"
        path.write_text(_sectioned_plan_text(_CLEAN_STEPS), encoding="utf-8")
        plan = parse_plan(path)
        return plan, path

    def _reports(self, registered_plan):
        from plan_tool.review_persistence import plan_reports_dir

        target = plan_reports_dir(registered_plan.plans_dir / "1-demo.md")
        if not target.is_dir():
            return [], []
        return (
            sorted(p.name for p in target.glob("*.md")),
            sorted(p.name for p in target.glob("*.json")),
        )


    def test_default_grade_still_writes_sidecar(
        self, registered_plan, monkeypatch, capsys
    ) -> None:
        from plan_tool.cli import main

        self._stub_audit(monkeypatch)
        self._sectioned_plan(registered_plan)
        assert main(
            registered_plan.argv("completeness-audit", "demo", "-y")
        ) == 0
        mds, jsons = self._reports(registered_plan)
        assert len(mds) == 1
        assert len(jsons) == 1


    @pytest.mark.parametrize("extra", [(), ("--json",)])
    def test_default_grade_warns_nothing(
        self, registered_plan, monkeypatch, capsys, extra
    ) -> None:
        from plan_tool.cli import main

        self._stub_audit(monkeypatch)
        self._sectioned_plan(registered_plan)
        assert main(
            registered_plan.argv(
                "completeness-audit", "demo", "-y", *extra
            )
        ) == 0
        assert "no findings sidecar written" not in capsys.readouterr().err

    @pytest.mark.parametrize("extra", [(), ("--json",)])
    def test_completeness_report_and_json_refuse_an_unsupported_detail_marker(
        self, registered_plan, monkeypatch, capsys, extra
    ) -> None:
        """Both the ordinary markdown-report path and ``--json`` must
        return the typed exit-1 diagnosis rather than persisting or
        rendering a partial mass/report result."""
        from plan_tool.cli import main
        from plan_tool.detail_artifacts import (
            derive_detail_path,
            render_detail_format_version_marker,
        )

        self._stub_audit(monkeypatch)
        plan_path = registered_plan.plans_dir / "1-demo.md"
        plan_path.write_text(_sectioned_plan_text(_CLEAN_STEPS), encoding="utf-8")
        plan = parse_plan(plan_path)
        detail_path = derive_detail_path(plan_path, plan, plan.steps[0])
        detail_path.parent.mkdir(parents=True, exist_ok=True)
        detail_path.write_text(
            f"# Only step\n{render_detail_format_version_marker(999)}\n\nfine.\n",
            encoding="utf-8",
        )

        rc = main(
            registered_plan.argv("completeness-audit", "demo", "-y", *extra)
        )
        assert rc == 1
        err = capsys.readouterr().err
        assert "999" in err
        assert "Traceback" not in err


    def test_default_json_unchanged(
        self, registered_plan, monkeypatch, capsys
    ) -> None:
        from plan_tool.cli import main

        self._stub_audit(monkeypatch)
        self._sectioned_plan(registered_plan)
        assert main(
            registered_plan.argv("completeness-audit", "demo", "-y", "--json")
        ) == 0
        payload = json.loads(capsys.readouterr().out)
        assert "detail_grade" not in payload
        assert "detail_bundle_fingerprint" not in payload


class TestRunGradeGroupedReportProse:
    """Run-grade grouped-report wording and next steps."""

    def _det(self, **overrides):
        base = dict(
            path_style_hint=None,
            dep_issues=[],
            body_issues=[],
            detail_cov_issues=[],
            detail_body_issues=[],
            files_coh_issues=[],
            lessons_issues=[],
        )
        base.update(overrides)
        return _DeterministicReport(**base)

    def _render(self, det, *, conceptual=(), **kwargs):
        return _render_grouped_report(
            SimpleNamespace(title="Demo", steps=[]),
            SimpleNamespace(name="demo"),
            det,
            correctness_recs=[],
            conceptual_recs=list(conceptual),
            audit_recs=list(conceptual),
            iterate_enabled=False,
            **kwargs,
        )


    def test_grade_run_next_steps_unchanged(self) -> None:
        det = self._det(
            body_issues=[
                SimpleNamespace(kind="missing", section="Overview", details="d")
            ],
            detail_cov_issues=[
                DetailCoverageIssue(
                    step_id=1, kind="missing_on_disk", detail_path="d/01.md"
                )
            ],
        )
        out = self._render(det, conceptual=[_rec("medium")])
        assert "completeness-audit demo --iterate" in out
        assert "plan-tool detail demo" in out
        assert "session-directed edit" in out
        assert "DETAIL_FORMAT.md" not in out


    def test_run_coverage_and_body_wording_unchanged(self) -> None:
        det = self._det(
            detail_cov_issues=[
                DetailCoverageIssue(
                    step_id=2, kind="missing_on_disk", detail_path="d/02.md"
                )
            ],
            detail_body_issues=[
                DetailBodyIssue(
                    step_id=1, kind="missing", section="Why", detail_path="d/01.md"
                )
            ],
        )
        out = self._render(det)
        assert "- WARN: step 2 detail `d/02.md` declared but missing on disk" in out
        assert (
            "- WARN: step 1 detail `d/01.md` — section `## Why` missing" in out
        )
        assert "### Grounding" not in out

    def test_detailed_plan_correctness_next_steps_unchanged(self) -> None:
        correctness = [_rec("high", source="plan-correctness")]
        out = _render_grouped_report(
            SimpleNamespace(title="Demo", steps=[]),
            SimpleNamespace(name="demo"),
            self._det(),
            correctness_recs=correctness,
            conceptual_recs=[],
            audit_recs=correctness,
            iterate_enabled=False,
            bundle_status=SimpleNamespace(
                is_bare=False,
                is_fully_bare=False,
                detailed_count=2,
                total=2,
            ),
        )
        suggested = out.split("### Suggested next steps", 1)[1]
        assert "completeness-audit demo --iterate" in suggested
        assert "completeness-apply demo" not in suggested


class TestResolveAuditReuse:
    """``_resolve_audit_reuse`` — the (flag × freshness × TTY) policy."""

    def _patch_lookup(self, monkeypatch, ru, *, calls=None):
        import plan_tool.completeness_report

        def fake(*args, **kwargs):
            if calls is not None:
                calls.append((args, kwargs))
            return ru

        monkeypatch.setattr(
            plan_tool.completeness_report, "resolve_reusable_audit", fake
        )

    def test_no_reuse_flag_skips_lookup(self, tmp_repo, monkeypatch) -> None:
        calls: list = []
        self._patch_lookup(monkeypatch, _ru(), calls=calls)
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        out = _resolve_audit_reuse(
            plan, path, ctx, _reuse_args(reuse_audit=False)
        )
        assert out is None
        assert calls == []  # never even looked up a sidecar

    def test_no_sidecar_returns_none(self, tmp_repo, monkeypatch, capsys) -> None:
        self._patch_lookup(monkeypatch, None)
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        out = _resolve_audit_reuse(plan, path, ctx, _reuse_args())
        assert out is None
        assert capsys.readouterr().err == ""  # silent first-run path

    def test_reuse_audit_id_miss_errors_and_audits_fresh(
        self, tmp_repo, monkeypatch, capsys
    ) -> None:
        self._patch_lookup(monkeypatch, None)
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        out = _resolve_audit_reuse(
            plan, path, ctx,
            _reuse_args(reuse_audit_id="20260505-120000-completeness"),
        )
        assert out is None
        err = capsys.readouterr().err
        assert "20260505-120000-completeness" in err

    def test_fresh_reused_under_yes(self, tmp_repo, monkeypatch) -> None:
        corr = _rec("high", source="plan-correctness")
        concept = _rec("medium", source="plan-completeness")
        coverage = _observed_audit_coverage(
            budget_limited=True,
            passes_used=3,
            cap=3,
            confirmation_kind=None,
        )
        self._patch_lookup(
            monkeypatch,
            _ru(
                correctness=[corr], conceptual=[concept], audit_coverage=coverage
            ),
        )
        # input must never be consulted under --yes.
        monkeypatch.setattr(
            "builtins.input",
            lambda *a, **k: (_ for _ in ()).throw(AssertionError("prompted")),
        )
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        coverage_out = [None]
        out = _resolve_audit_reuse(
            plan,
            path,
            ctx,
            _reuse_args(yes=True),
            coverage_out=coverage_out,
        )
        assert out == [corr, concept]  # correctness first
        assert coverage_out == [coverage]

    def test_fresh_reused_non_tty(self, tmp_repo, monkeypatch) -> None:
        concept = _rec("medium", source="plan-completeness")
        coverage = _observed_audit_coverage(
            budget_limited=False,
            passes_used=1,
            cap=1,
            confirmation_kind="confirmed-dry",
        )
        self._patch_lookup(
            monkeypatch, _ru(conceptual=[concept], audit_coverage=coverage)
        )
        monkeypatch.setattr("sys.stdin", SimpleNamespace(isatty=lambda: False))
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        out = _resolve_audit_reuse(plan, path, ctx, _reuse_args())
        assert out == [concept]

    def test_fresh_reused_under_json_does_not_prompt(
        self, tmp_repo, monkeypatch
    ) -> None:
        """``--json`` auto-accepts a fresh reuse without prompting, even
        on a TTY — a ``[Y/n]`` line on stdout would corrupt the
        machine-readable report.
        """
        concept = _rec("medium", source="plan-completeness")
        coverage = _observed_audit_coverage(
            budget_limited=False,
            passes_used=1,
            cap=1,
            confirmation_kind="confirmed-dry",
        )
        self._patch_lookup(
            monkeypatch, _ru(conceptual=[concept], audit_coverage=coverage)
        )
        # TTY is live; only the --json gate must suppress the prompt.
        monkeypatch.setattr("sys.stdin", SimpleNamespace(isatty=lambda: True))
        monkeypatch.setattr(
            "builtins.input",
            lambda *a, **k: (_ for _ in ()).throw(AssertionError("prompted")),
        )
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        out = _resolve_audit_reuse(plan, path, ctx, _reuse_args(json=True))
        assert out == [concept]

    def test_fresh_prompt_accept(self, tmp_repo, monkeypatch) -> None:
        concept = _rec("medium", source="plan-completeness")
        coverage = _observed_audit_coverage(
            budget_limited=False,
            passes_used=1,
            cap=1,
            confirmation_kind="confirmed-dry",
        )
        self._patch_lookup(
            monkeypatch, _ru(conceptual=[concept], audit_coverage=coverage)
        )
        monkeypatch.setattr("sys.stdin", SimpleNamespace(isatty=lambda: True))
        monkeypatch.setattr("builtins.input", lambda *a, **k: "")  # empty = Yes
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        out = _resolve_audit_reuse(plan, path, ctx, _reuse_args())
        assert out == [concept]

    def test_fresh_prompt_decline(self, tmp_repo, monkeypatch) -> None:
        concept = _rec("medium", source="plan-completeness")
        self._patch_lookup(monkeypatch, _ru(conceptual=[concept]))
        monkeypatch.setattr("sys.stdin", SimpleNamespace(isatty=lambda: True))
        monkeypatch.setattr("builtins.input", lambda *a, **k: "n")
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        out = _resolve_audit_reuse(plan, path, ctx, _reuse_args())
        assert out is None

    def test_reuse_flag_true_reuses_fresh(self, tmp_repo, monkeypatch) -> None:
        concept = _rec("medium", source="plan-completeness")
        self._patch_lookup(monkeypatch, _ru(conceptual=[concept]))
        monkeypatch.setattr(
            "builtins.input",
            lambda *a, **k: (_ for _ in ()).throw(AssertionError("prompted")),
        )
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        # Explicit --reuse-audit wins even over an explicit --audit-passes.
        out = _resolve_audit_reuse(
            plan, path, ctx, _reuse_args(reuse_audit=True, audit_passes=3)
        )
        assert out == [concept]

    def test_explicit_audit_passes_forces_fresh(
        self, tmp_repo, monkeypatch
    ) -> None:
        concept = _rec("medium", source="plan-completeness")
        self._patch_lookup(monkeypatch, _ru(conceptual=[concept]))
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        # --yes would auto-accept, but an explicit --audit-passes suppresses
        # it and forces a fresh audit.
        out = _resolve_audit_reuse(
            plan, path, ctx, _reuse_args(yes=True, audit_passes=2)
        )
        assert out is None

    def test_stale_by_plan_declines_with_note(
        self, tmp_repo, monkeypatch, capsys
    ) -> None:
        self._patch_lookup(
            monkeypatch,
            _ru(fresh=False, plan_match=False, code_match=True, drifted_code=[]),
        )
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        out = _resolve_audit_reuse(plan, path, ctx, _reuse_args(yes=True))
        assert out is None
        err = capsys.readouterr().err
        assert "plan changed" in err
        assert "(step " not in err  # no attributed file list on plan drift

    def test_weak_conformance_declines_with_note(
        self, tmp_repo, monkeypatch, capsys
    ) -> None:
        """A non-qualifying saved sample declines under non-explicit reuse
        (``--yes`` without ``--reuse-audit``) with a message explaining why --
        unlike every other decline branch above, this one used to be silent."""
        coverage = _observed_audit_coverage(
            budget_limited=False,
            passes_used=1,
            cap=1,
            confirmation_kind=None,
            conforming_pass_count=0,
            failed_or_malformed_pass_count=1,
        )
        self._patch_lookup(
            monkeypatch, _ru(audit_coverage=coverage)
        )
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        out = _resolve_audit_reuse(plan, path, ctx, _reuse_args(yes=True))
        assert out is None
        err = capsys.readouterr().err
        assert "pass-conformance" in err
        assert "live sample" in err

    def test_weak_conformance_reuses_under_explicit_reuse_audit(
        self, tmp_repo, monkeypatch, capsys
    ) -> None:
        """Explicit ``--reuse-audit`` still bypasses the quality gate (and
        prints no decline note, since nothing was declined)."""
        corr = _rec("high", source="plan-correctness")
        coverage = _observed_audit_coverage(
            budget_limited=False,
            passes_used=1,
            cap=1,
            confirmation_kind=None,
            conforming_pass_count=0,
            failed_or_malformed_pass_count=1,
        )
        self._patch_lookup(
            monkeypatch, _ru(correctness=[corr], audit_coverage=coverage)
        )
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        out = _resolve_audit_reuse(
            plan, path, ctx, _reuse_args(reuse_audit=True)
        )
        assert out == [corr]
        assert "pass-conformance" not in capsys.readouterr().err

    def test_weak_conformance_reuses_under_explicit_reuse_audit_id(
        self, tmp_repo, monkeypatch, capsys
    ) -> None:
        """``--reuse-audit-id`` bypasses the quality gate exactly like
        ``--reuse-audit`` -- ``_reuse_is_explicit`` ORs the two disjuncts,
        and only the ``reuse_audit=True`` half had a test until now."""
        corr = _rec("high", source="plan-correctness")
        coverage = _observed_audit_coverage(
            budget_limited=False,
            passes_used=1,
            cap=1,
            confirmation_kind=None,
            conforming_pass_count=0,
            failed_or_malformed_pass_count=1,
        )
        self._patch_lookup(
            monkeypatch, _ru(correctness=[corr], audit_coverage=coverage)
        )
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        out = _resolve_audit_reuse(
            plan, path, ctx,
            _reuse_args(reuse_audit_id="20260505-120000-completeness"),
        )
        assert out == [corr]
        assert "pass-conformance" not in capsys.readouterr().err

    def test_weak_conformance_still_reaches_interactive_prompt(
        self, tmp_repo, monkeypatch
    ) -> None:
        """A human at a live TTY (no --yes/--json/--reuse-audit) must still
        get the [Y/n] prompt for a non-qualifying saved audit -- unlike the
        non-interactive auto-accept paths, a human present to judge the
        situation should not be silently routed to a fresh audit."""
        concept = _rec("medium", source="plan-completeness")
        coverage = _observed_audit_coverage(
            budget_limited=False,
            passes_used=1,
            cap=1,
            confirmation_kind=None,
            conforming_pass_count=0,
            failed_or_malformed_pass_count=1,
        )
        self._patch_lookup(
            monkeypatch, _ru(conceptual=[concept], audit_coverage=coverage)
        )
        monkeypatch.setattr("sys.stdin", SimpleNamespace(isatty=lambda: True))
        monkeypatch.setattr("builtins.input", lambda *a, **k: "")  # empty = Yes
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        out = _resolve_audit_reuse(plan, path, ctx, _reuse_args())
        assert out == [concept]

    def test_stale_by_code_emits_attributed_info(
        self, tmp_repo, monkeypatch, capsys
    ) -> None:
        plan, path = _write_and_parse(tmp_repo, _FILE_STEP)
        drifted = (tmp_repo.root / "plan_tool/widget.py").resolve()
        self._patch_lookup(
            monkeypatch,
            _ru(
                fresh=False,
                plan_match=True,
                code_match=False,
                drifted_code=[drifted],
            ),
        )
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        out = _resolve_audit_reuse(plan, path, ctx, _reuse_args(yes=True))
        assert out is None
        err = capsys.readouterr().err
        # Normal operation, surfaced at info level (not a warning).
        assert "info:" in err
        assert "warning:" not in err
        # Files are grouped under their owning step: the step header carries
        # the title once, the file is listed bare beneath it.
        assert "step 1: Wire it" in err
        assert "plan_tool/widget.py" in err
        assert "plan_tool/widget.py (step 1" not in err  # not the inline form
        # No recovery hint: the staleness self-heals (re-run + --commit
        # rewrites the sidecar fingerprint), and `detail --reconcile` never
        # touched the completeness sidecar this check reads anyway.
        assert "--reconcile" not in err
        assert "Next steps" not in err

    def test_drift_out_set_on_code_drift(
        self, tmp_repo, monkeypatch
    ) -> None:
        """The ``drift_out`` out-param records True when the saved audit is
        stale because code moved under the plan (BACKLOG #65 wiring)."""
        plan, path = _write_and_parse(tmp_repo, _FILE_STEP)
        drifted = (tmp_repo.root / "plan_tool/widget.py").resolve()
        self._patch_lookup(
            monkeypatch,
            _ru(
                fresh=False,
                plan_match=True,
                code_match=False,
                drifted_code=[drifted],
            ),
        )
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        drift_out = [False]
        _resolve_audit_reuse(
            plan, path, ctx, _reuse_args(yes=True), drift_out=drift_out
        )
        assert drift_out[0] is True

    def test_drift_out_unset_on_plan_drift(
        self, tmp_repo, monkeypatch
    ) -> None:
        """Plan-side staleness (no code drift) leaves ``drift_out`` False."""
        self._patch_lookup(
            monkeypatch,
            _ru(fresh=False, plan_match=False, code_match=True, drifted_code=[]),
        )
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        drift_out = [False]
        _resolve_audit_reuse(
            plan, path, ctx, _reuse_args(yes=True), drift_out=drift_out
        )
        assert drift_out[0] is False

    def test_drift_out_unset_on_fresh_reuse(
        self, tmp_repo, monkeypatch
    ) -> None:
        """A fresh saved audit (no staleness) leaves ``drift_out`` False."""
        concept = _rec("medium", source="plan-completeness")
        self._patch_lookup(monkeypatch, _ru(conceptual=[concept]))
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        drift_out = [False]
        _resolve_audit_reuse(
            plan, path, ctx, _reuse_args(reuse_audit=True), drift_out=drift_out
        )
        assert drift_out[0] is False

    def test_stale_by_code_groups_files_sharing_a_step(
        self, tmp_repo, monkeypatch, capsys
    ) -> None:
        """Several drifted files owned by the same step print the (long) step
        title once as a header, not repeated per file."""
        two_file_step = (
            "steps:\n"
            "  - id: 1\n"
            "    title: Wire it\n"
            "    files:\n"
            "      - plan_tool/widget.py\n"
            "      - plan_tool/gadget.py\n"
        )
        plan, path = _write_and_parse(tmp_repo, two_file_step)
        drifted = [
            (tmp_repo.root / "plan_tool/widget.py").resolve(),
            (tmp_repo.root / "plan_tool/gadget.py").resolve(),
        ]
        self._patch_lookup(
            monkeypatch,
            _ru(
                fresh=False,
                plan_match=True,
                code_match=False,
                drifted_code=drifted,
            ),
        )
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        _resolve_audit_reuse(plan, path, ctx, _reuse_args(yes=True))
        err = capsys.readouterr().err
        assert err.count("step 1: Wire it") == 1  # title printed once
        assert "plan_tool/widget.py" in err
        assert "plan_tool/gadget.py" in err


# --------------------------------------------------------------------------
# `--commit` on completeness-audit / completeness-apply
# --------------------------------------------------------------------------


def _init_git_repo(root) -> None:
    import subprocess

    for cmd in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "t@example.com"],
        ["git", "config", "user.name", "Test"],
    ):
        subprocess.run(cmd, cwd=root, check=True, capture_output=True)


def _git_commit_all(root, message: str) -> None:
    import subprocess

    subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", message],
        cwd=root, check=True, capture_output=True,
    )


def _attach_minimal_detail(tmp_repo, plan_path) -> None:
    detail_rel = "plans/details/01-only-step.md"
    detail_path = tmp_repo.root / detail_rel
    detail_path.parent.mkdir(parents=True, exist_ok=True)
    detail_path.write_text("# Step 1\n\n## Summary\n\nDetail.\n", encoding="utf-8")
    text = plan_path.read_text(encoding="utf-8")
    plan_path.write_text(
        text.replace(
            "    title: Only step\n",
            f"    title: Only step\n    detail: {detail_rel}\n",
        ),
        encoding="utf-8",
    )


class TestCompletenessCommitSubjects:
    def test_audit_subject(self) -> None:
        from plan_tool.cli.completeness_cmd import _completeness_commit_subject

        assert _completeness_commit_subject("demo") == (
            "plan(demo): completeness — applied audit findings"
        )

    def test_apply_subject_singular_and_plural(self) -> None:
        from plan_tool.cli.completeness_phases import (
            _completeness_apply_commit_subject,
        )

        assert _completeness_apply_commit_subject("demo", 1) == (
            "plan(demo): completeness — applied 1 gap"
        )
        assert _completeness_apply_commit_subject("demo", 3) == (
            "plan(demo): completeness — applied 3 gaps"
        )


class TestCompletenessCommitGates:
    def test_audit_commit_requires_iterate(
        self, registered_plan, capsys
    ) -> None:
        # --commit commits the iterate loop's applied edits; without --iterate
        # there are none, so reject before any claude call.
        from plan_tool.cli import main

        rc = main(registered_plan.argv("completeness-audit", "demo", "--commit"))
        assert rc == 2
        assert "requires --iterate" in capsys.readouterr().err

    def test_audit_commit_iterate_dirty_tree_rejected(
        self, tmp_repo, capsys
    ) -> None:
        import shutil

        from plan_tool.cli import main

        shutil.rmtree(tmp_repo.root / ".git")
        _init_git_repo(tmp_repo.root)
        tmp_repo.add_plan("1-demo", title="Demo")
        tmp_repo.write_manifest()
        _git_commit_all(tmp_repo.root, "init")
        (tmp_repo.root / "stray.txt").write_text("x\n", encoding="utf-8")

        rc = main(
            tmp_repo.argv("completeness-audit", "demo", "--commit", "--iterate")
        )
        assert rc == 2
        assert "clean working tree" in capsys.readouterr().err

    def test_apply_commit_dirty_tree_rejected(self, tmp_repo, capsys) -> None:
        import shutil

        from plan_tool.cli import main

        shutil.rmtree(tmp_repo.root / ".git")
        _init_git_repo(tmp_repo.root)
        tmp_repo.add_plan("1-demo", title="Demo")
        tmp_repo.write_manifest()
        _git_commit_all(tmp_repo.root, "init")
        (tmp_repo.root / "stray.txt").write_text("x\n", encoding="utf-8")

        rc = main(tmp_repo.argv("completeness-apply", "demo", "--commit"))
        assert rc == 2
        assert "clean working tree" in capsys.readouterr().err


class TestCompletenessApplyCommit:
    def test_apply_commit_creates_commit_after_edits(
        self, tmp_repo, monkeypatch
    ) -> None:
        import shutil
        import subprocess
        from datetime import datetime, timezone

        import plan_tool.cli.completeness_phases as phases
        from plan_tool.cli import main
        from plan_tool.review_persistence import save_review
        from plan_tool.review_walk import WalkResult

        shutil.rmtree(tmp_repo.root / ".git")
        _init_git_repo(tmp_repo.root)
        plan_path = tmp_repo.add_plan("1-demo", title="Demo")
        _attach_minimal_detail(tmp_repo, plan_path)
        tmp_repo.write_manifest()
        # Persist a completeness audit carrying one conceptual gap.
        save_review(
            plan_slug="demo",
            plan_path=plan_path.relative_to(tmp_repo.root).as_posix(),
            repo_root=tmp_repo.root,
            report_md="# report\n",
            recommendations=[_rec("medium", source="plan-completeness")],
            kind="completeness",
            now=datetime(2026, 6, 13, 12, 0, 0, tzinfo=timezone.utc),
        )
        _git_commit_all(tmp_repo.root, "init")  # clean tree incl the audit

        def fake_walk(saved, **kw):
            # Simulate a gap-closing edit landing on disk.
            (tmp_repo.plans_dir / "applied-edit.txt").write_text(
                "edit\n", encoding="utf-8"
            )
            return WalkResult(answered=1, quit_early=False)

        monkeypatch.setattr(phases, "walk_recommendations", fake_walk)
        # The walk is per-finding and TTY-gated now; simulate a terminal so
        # the (stubbed) walk runs.
        monkeypatch.setattr("sys.stdin", SimpleNamespace(isatty=lambda: True))

        rc = main(
            tmp_repo.argv("completeness-apply", "demo", "--commit")
        )
        assert rc == 0
        log = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            cwd=tmp_repo.root, capture_output=True, text=True,
        ).stdout
        assert "plan(demo): completeness — applied 1 gap" in log

    def test_apply_commit_warns_when_saved_audit_gitignored(
        self, tmp_repo, monkeypatch, capsys
    ) -> None:
        """Belt-and-suspenders: when the saved audit JSON sits on a
        gitignored path, the walker's in-place annotations can't be staged
        by ``git add -A``. The run still commits the (tracked) gap edits,
        but warns so the dropped annotations aren't silent."""
        import shutil
        import subprocess
        from datetime import datetime, timezone

        import plan_tool.cli.completeness_phases as phases
        from plan_tool.cli import main
        from plan_tool.review_persistence import save_review
        from plan_tool.review_walk import WalkResult

        shutil.rmtree(tmp_repo.root / ".git")
        _init_git_repo(tmp_repo.root)
        plan_path = tmp_repo.add_plan("1-demo", title="Demo")
        _attach_minimal_detail(tmp_repo, plan_path)
        tmp_repo.write_manifest()
        # Ignore every saved completeness JSON, wherever it lands.
        (tmp_repo.root / ".gitignore").write_text(
            "*-completeness.json\n", encoding="utf-8"
        )
        save_review(
            plan_slug="demo",
            plan_path=plan_path.relative_to(tmp_repo.root).as_posix(),
            repo_root=tmp_repo.root,
            report_md="# report\n",
            recommendations=[_rec("medium", source="plan-completeness")],
            kind="completeness",
            now=datetime(2026, 6, 13, 12, 0, 0, tzinfo=timezone.utc),
        )
        _git_commit_all(tmp_repo.root, "init")  # audit JSON is ignored, not added

        def fake_walk(saved, **kw):
            (tmp_repo.plans_dir / "applied-edit.txt").write_text(
                "edit\n", encoding="utf-8"
            )
            return WalkResult(answered=1, quit_early=False)

        monkeypatch.setattr(phases, "walk_recommendations", fake_walk)
        monkeypatch.setattr("sys.stdin", SimpleNamespace(isatty=lambda: True))

        rc = main(
            tmp_repo.argv("completeness-apply", "demo", "--commit")
        )
        assert rc == 0
        err = capsys.readouterr().err
        assert "gitignored path" in err
        # The tracked gap edit still committed; the ignored JSON did not.
        tracked = subprocess.run(
            ["git", "ls-files"],
            cwd=tmp_repo.root, capture_output=True, text=True,
        ).stdout
        assert "applied-edit.txt" in tracked
        assert "-completeness.json" not in tracked


# --- _apply_files_coherence — the deterministic files-coherence fold --------
#
# completeness-apply resolves the files-coherence subset the audit emits but
# apply_finding can't (frontmatter, not prose), with no claude call. These
# pin the helper directly: one step declaring ``src/service.py`` whose detail
# cites two same-basename near-misses — ``src/sub/service.py`` (created →
# resolvable → belongs in allowed_mentions) and ``src/other/service.py``
# (never created → a typo the helper must report but never write).
_COHERENCE_PLAN = """\
---
title: Coherence Fold
status: planning
priority: low
steps:
  - id: 1
    title: Touch the service
    files:
      - src/service.py
    detail: plans/details/01-touch.md
---
# Coherence Fold
"""

_COHERENCE_DETAIL = """\
# Step 1 — Touch the service

The sibling helper `src/sub/service.py` is read for context, and a stale
reference to `src/other/service.py` lingers from a move.
"""


def _seed_coherence(repo):
    """Write the plan + detail + the one real cited file; return the plan path."""
    (repo.root / "src" / "sub").mkdir(parents=True, exist_ok=True)
    (repo.root / "src" / "service.py").write_text("# declared\n", encoding="utf-8")
    (repo.root / "src" / "sub" / "service.py").write_text("# real\n", encoding="utf-8")
    (repo.plans_dir / "details").mkdir(parents=True, exist_ok=True)
    (repo.plans_dir / "details" / "01-touch.md").write_text(
        _COHERENCE_DETAIL, encoding="utf-8"
    )
    plan_path = repo.plans_dir / "1-coherence.md"
    plan_path.write_text(_COHERENCE_PLAN, encoding="utf-8")
    return plan_path


def _mentions(plan_path):
    return parse_plan(plan_path).step_by_id(1).allowed_mentions


class TestApplyFilesCoherence:
    def test_report_only_does_not_write(self, tmp_repo, capsys) -> None:
        plan_path = _seed_coherence(tmp_repo)
        added = _apply_files_coherence(plan_path, tmp_repo.root, apply=False)
        cap = capsys.readouterr()
        text = cap.out + cap.err
        assert added == 0
        assert "would add" in text
        assert "src/sub/service.py" in text
        assert "src/other/service.py" in text  # flagged as a typo
        assert _mentions(plan_path) == []

    def test_apply_adds_only_the_resolvable_path(self, tmp_repo, capsys) -> None:
        plan_path = _seed_coherence(tmp_repo)
        added = _apply_files_coherence(plan_path, tmp_repo.root, apply=True)
        assert added == 1
        mentions = _mentions(plan_path)
        assert "src/sub/service.py" in mentions
        assert "src/other/service.py" not in mentions  # typo left for prose fix

    def test_apply_is_idempotent(self, tmp_repo) -> None:
        plan_path = _seed_coherence(tmp_repo)
        _apply_files_coherence(plan_path, tmp_repo.root, apply=True)
        # Second run: the resolvable path is now recognized, so it's no longer
        # drift; nothing more is added.
        added = _apply_files_coherence(plan_path, tmp_repo.root, apply=True)
        assert added == 0
        assert _mentions(plan_path).count("src/sub/service.py") == 1

    def test_threads_plan_path_so_canonical_only_details_are_seen(
        self, tmp_repo
    ) -> None:
        """The allowed-mentions promotion resolves a canonical-only detail file
        (``detail:`` pointer unset, file on disk) — the same set the audit that
        emitted these findings judged."""
        from plan_tool.detail_artifacts import derive_detail_path

        plan_path = _seed_coherence(tmp_repo)
        # Drop the pointer and move the body to the canonical path.
        plan_path.write_text(
            plan_path.read_text(encoding="utf-8").replace(
                "    detail: plans/details/01-touch.md\n", ""
            ),
            encoding="utf-8",
        )
        plan = parse_plan(plan_path)
        canonical = derive_detail_path(plan_path, plan, plan.steps[0])
        canonical.parent.mkdir(parents=True, exist_ok=True)
        canonical.write_text(_COHERENCE_DETAIL, encoding="utf-8")
        added = _apply_files_coherence(plan_path, tmp_repo.root, apply=True)
        assert added == 1
        assert "src/sub/service.py" in _mentions(plan_path)

    def test_clean_plan_writes_nothing(self, tmp_repo) -> None:
        plan_path = _seed_coherence(tmp_repo)
        # Pre-declare both citations: no detail_only drift remains.
        text = plan_path.read_text(encoding="utf-8").replace(
            "    detail: plans/details/01-touch.md\n",
            "    allowed_mentions:\n"
            "      - src/sub/service.py\n"
            "      - src/other/service.py\n"
            "    detail: plans/details/01-touch.md\n",
        )
        plan_path.write_text(text, encoding="utf-8")
        added = _apply_files_coherence(plan_path, tmp_repo.root, apply=True)
        assert added == 0


class TestCompletenessApplyDetailBundleGate:
    def _save_empty_completeness(self, tmp_repo, plan_path) -> None:
        from plan_tool.review_persistence import save_review

        save_review(
            plan_slug="demo",
            plan_path=plan_path.relative_to(tmp_repo.root).as_posix(),
            repo_root=tmp_repo.root,
            report_md="# report\n",
            recommendations=[],
            kind="completeness",
        )

    def _save_conceptual_completeness(self, tmp_repo, plan_path) -> None:
        from plan_tool.review_persistence import save_review

        save_review(
            plan_slug="demo",
            plan_path=plan_path.relative_to(tmp_repo.root).as_posix(),
            repo_root=tmp_repo.root,
            report_md="# report\n",
            recommendations=[_rec("medium", source="plan-completeness")],
            kind="completeness",
        )

    def _save_correctness(self, tmp_repo, plan_path, *, rec_id="corr-1") -> None:
        from plan_tool.review_persistence import save_review

        save_review(
            plan_slug="demo",
            plan_path=plan_path.relative_to(tmp_repo.root).as_posix(),
            repo_root=tmp_repo.root,
            report_md="# report\n",
            recommendations=[
                Recommendation(
                    id=rec_id,
                    source="plan-correctness",
                    severity="high",
                    step_id=None,
                    title="design gap",
                    body="fix the design",
                    anchor=rec_id,
                )
            ],
            kind="completeness",
        )

    def _save_both_conceptual(
        self, tmp_repo, plan_path, *, corr_id="corr-1", comp_id="comp-1"
    ) -> None:
        from plan_tool.review_persistence import save_review

        save_review(
            plan_slug="demo",
            plan_path=plan_path.relative_to(tmp_repo.root).as_posix(),
            repo_root=tmp_repo.root,
            report_md="# report\n",
            recommendations=[
                Recommendation(
                    id=corr_id,
                    source="plan-correctness",
                    severity="high",
                    step_id=None,
                    title="design gap",
                    body="fix design",
                    anchor=corr_id,
                ),
                Recommendation(
                    id=comp_id,
                    source="plan-completeness",
                    severity="medium",
                    step_id=None,
                    title="missing thing",
                    body="add thing",
                    anchor=comp_id,
                ),
            ],
            kind="completeness",
        )

    def _save_granularity_split(self, tmp_repo, plan_path) -> None:
        from plan_tool.granularity import GRANULARITY_SPLIT_SOURCE
        from plan_tool.review_persistence import save_review

        save_review(
            plan_slug="demo",
            plan_path=plan_path.relative_to(tmp_repo.root).as_posix(),
            repo_root=tmp_repo.root,
            report_md="# report\n",
            recommendations=[
                Recommendation(
                    id="split-1",
                    source=GRANULARITY_SPLIT_SOURCE,
                    severity="medium",
                    step_id=1,
                    title="mixed step",
                    body="split me",
                    anchor="split-1",
                )
            ],
            kind="completeness",
        )

    def _save_data_contract(self, tmp_repo, plan_path) -> None:
        from plan_tool.review_persistence import save_review

        save_review(
            plan_slug="demo",
            plan_path=plan_path.relative_to(tmp_repo.root).as_posix(),
            repo_root=tmp_repo.root,
            report_md="# report\n",
            recommendations=[
                Recommendation(
                    id="dc-1",
                    source="data-contract",
                    severity="medium",
                    step_id=None,
                    title="contract drift",
                    body="update contract",
                    anchor="dc-1",
                )
            ],
            kind="completeness",
        )

    def test_bare_plan_skips_files_coherence_writer(
        self, tmp_repo, monkeypatch, capsys
    ) -> None:
        import plan_tool.cli.completeness_phases as phases
        from plan_tool.cli import main

        plan_path = tmp_repo.add_plan("1-demo", title="Demo")
        tmp_repo.write_manifest()
        self._save_empty_completeness(tmp_repo, plan_path)

        def fail_if_called(*_args, **_kwargs):
            raise AssertionError("files-coherence writer must not run")

        monkeypatch.setattr(phases, "_apply_files_coherence", fail_if_called)
        rc = main(tmp_repo.argv("completeness-apply", "demo"))
        assert rc == 0
        err = capsys.readouterr().err
        assert "skipping files-coherence apply" in err
        assert "complete detail bundle" in err

    def test_bare_plan_with_only_completeness_gaps_skips_the_walk(
        self, tmp_repo, monkeypatch, capsys
    ) -> None:
        import plan_tool.cli.completeness_phases as phases
        from plan_tool.cli import main

        plan_path = tmp_repo.add_plan("1-demo", title="Demo")
        tmp_repo.write_manifest()
        self._save_conceptual_completeness(tmp_repo, plan_path)

        def fail_walk(*_args, **_kwargs):
            raise AssertionError("conceptual walk must not run")

        monkeypatch.setattr(phases, "walk_recommendations", fail_walk)
        monkeypatch.setattr("sys.stdin", SimpleNamespace(isatty=lambda: True))
        rc = main(tmp_repo.argv("completeness-apply", "demo"))
        assert rc == 0
        cap = capsys.readouterr()
        assert "withholding" in cap.err
        assert "plan-completeness/medium" in cap.out
        assert "plan-tool detail demo" in cap.out

    def test_bare_plan_walks_correctness_gaps(
        self, tmp_repo, monkeypatch, capsys
    ) -> None:
        import plan_tool.cli.completeness_phases as phases
        from plan_tool.cli import main
        from plan_tool.review_walk import WalkResult

        plan_path = tmp_repo.add_plan("1-demo", title="Demo")
        tmp_repo.write_manifest()
        self._save_correctness(tmp_repo, plan_path)
        seen: dict = {}

        def fake_walk(saved, **kwargs):
            seen["recs"] = list(saved.recommendations)
            return WalkResult(answered=0, quit_early=False)

        monkeypatch.setattr(phases, "walk_recommendations", fake_walk)
        monkeypatch.setattr("sys.stdin", SimpleNamespace(isatty=lambda: True))
        rc = main(tmp_repo.argv("completeness-apply", "demo"))
        assert rc == 0
        assert len(seen["recs"]) == 1
        assert seen["recs"][0].source == "plan-correctness"

    def test_bare_plan_withholds_completeness_gaps_from_the_walk(
        self, tmp_repo, monkeypatch
    ) -> None:
        import plan_tool.cli.completeness_phases as phases
        from plan_tool.cli import main
        from plan_tool.review_walk import WalkResult

        plan_path = tmp_repo.add_plan("1-demo", title="Demo")
        tmp_repo.write_manifest()
        self._save_both_conceptual(tmp_repo, plan_path)
        seen: dict = {}

        def fake_walk(saved, **kwargs):
            seen["recs"] = list(saved.recommendations)
            return WalkResult(answered=0, quit_early=False)

        monkeypatch.setattr(phases, "walk_recommendations", fake_walk)
        monkeypatch.setattr("sys.stdin", SimpleNamespace(isatty=lambda: True))
        rc = main(tmp_repo.argv("completeness-apply", "demo"))
        assert rc == 0
        assert [r.source for r in seen["recs"]] == ["plan-correctness"]

    def test_bare_plan_withholds_granularity_split_from_the_walk(
        self, tmp_repo, monkeypatch, capsys
    ) -> None:
        import plan_tool.cli.completeness_phases as phases
        from plan_tool.cli import main
        from plan_tool.granularity import GRANULARITY_SPLIT_SOURCE

        plan_path = tmp_repo.add_plan("1-demo", title="Demo")
        tmp_repo.write_manifest()
        self._save_granularity_split(tmp_repo, plan_path)
        escalate_calls: list = []

        def fake_escalate(*_a, **_k):
            escalate_calls.append(True)
            return SimpleNamespace(outcome="applied")

        monkeypatch.setattr(
            "plan_tool.launcher.escalate_to_split", fake_escalate
        )
        monkeypatch.setattr(
            phases,
            "walk_recommendations",
            lambda *a, **k: (_ for _ in ()).throw(
                AssertionError("walk must not run when only split is saved")
            ),
        )
        monkeypatch.setattr("sys.stdin", SimpleNamespace(isatty=lambda: True))
        rc = main(
            tmp_repo.argv(
                "completeness-apply", "demo", "--apply-structural"
            )
        )
        assert rc == 0
        assert escalate_calls == []
        assert GRANULARITY_SPLIT_SOURCE in capsys.readouterr().out

    def test_bare_plan_withholds_data_contract_from_the_walk(
        self, tmp_repo, monkeypatch, capsys
    ) -> None:
        import plan_tool.cli.completeness_phases as phases
        from plan_tool.cli import main

        plan_path = tmp_repo.add_plan("1-demo", title="Demo")
        tmp_repo.write_manifest()
        self._save_data_contract(tmp_repo, plan_path)

        def fail_walk(*_a, **_k):
            raise AssertionError("walk must not run when only data-contract saved")

        redirect_calls: list = []

        def fake_redirect(rec, **kwargs):
            redirect_calls.append(rec.id)
            return "redirected"

        monkeypatch.setattr(
            phases, "_data_contract_completeness_redirect", fake_redirect
        )
        monkeypatch.setattr(phases, "walk_recommendations", fail_walk)
        monkeypatch.setattr("sys.stdin", SimpleNamespace(isatty=lambda: True))
        rc = main(tmp_repo.argv("completeness-apply", "demo"))
        assert rc == 0
        assert redirect_calls == []
        assert "data-contract/medium" in capsys.readouterr().out

    def test_bare_plan_reports_withheld_gaps_with_the_detail_pointer(
        self, tmp_repo, monkeypatch, capsys
    ) -> None:
        import plan_tool.cli.completeness_phases as phases
        from plan_tool.cli import main
        from plan_tool.review_walk import WalkResult

        plan_path = tmp_repo.add_plan("1-demo", title="Demo")
        tmp_repo.write_manifest()
        self._save_both_conceptual(tmp_repo, plan_path)
        monkeypatch.setattr(
            phases,
            "walk_recommendations",
            lambda *a, **k: WalkResult(answered=0, quit_early=False),
        )
        monkeypatch.setattr("sys.stdin", SimpleNamespace(isatty=lambda: True))
        rc = main(tmp_repo.argv("completeness-apply", "demo"))
        assert rc == 0
        cap = capsys.readouterr()
        assert "withholding 1 saved gap" in cap.err
        assert "plan-completeness/medium" in cap.out
        assert "plan-tool detail demo" in cap.out

    def test_bare_plan_still_skips_files_coherence_when_the_walk_runs(
        self, tmp_repo, monkeypatch
    ) -> None:
        import plan_tool.cli.completeness_phases as phases
        from plan_tool.cli import main
        from plan_tool.review_walk import WalkResult

        plan_path = tmp_repo.add_plan("1-demo", title="Demo")
        tmp_repo.write_manifest()
        self._save_correctness(tmp_repo, plan_path)

        def fail_coherence(*_a, **_k):
            raise AssertionError("files-coherence writer must not run")

        monkeypatch.setattr(phases, "_apply_files_coherence", fail_coherence)
        monkeypatch.setattr(
            phases,
            "walk_recommendations",
            lambda *a, **k: WalkResult(answered=0, quit_early=False),
        )
        monkeypatch.setattr("sys.stdin", SimpleNamespace(isatty=lambda: True))
        rc = main(tmp_repo.argv("completeness-apply", "demo"))
        assert rc == 0

    def test_bare_plan_carried_context_keeps_the_withheld_gaps(
        self, tmp_repo, monkeypatch
    ) -> None:
        import plan_tool.cli.completeness_phases as phases
        import plan_tool.review as review_module
        from plan_tool.cli import main
        from plan_tool.launcher import ApplyFindingResult
        from plan_tool.review_walk import WalkResult

        plan_path = tmp_repo.add_plan("1-demo", title="Demo")
        tmp_repo.write_manifest()
        self._save_both_conceptual(tmp_repo, plan_path)
        captured: dict = {}
        real_assemble = review_module.assemble_carried_findings

        def spy_assemble(recs, **kwargs):
            captured["titles"] = {r.title for r in recs}
            return real_assemble(recs, **kwargs)

        monkeypatch.setattr(
            review_module, "assemble_carried_findings", spy_assemble
        )

        def fake_apply(plan_path_arg, **kwargs):
            return ApplyFindingResult(
                step_id=1,
                exit_code=0,
                verdict="NOT-APPLICABLE",
                summary="skip",
                diff_text="",
                pre_snapshot={plan_path: plan_path.read_text()},
                stdout="## Verdict\nNOT-APPLICABLE\n",
            )

        from plan_tool import launcher as launcher_module

        monkeypatch.setattr(launcher_module, "apply_finding", fake_apply)

        def fake_walk(saved, *, action_fn, **kwargs):
            action_fn(saved.recommendations[0])
            return WalkResult(answered=1, quit_early=False)

        monkeypatch.setattr(phases, "walk_recommendations", fake_walk)
        monkeypatch.setattr("sys.stdin", SimpleNamespace(isatty=lambda: True))
        rc = main(tmp_repo.argv("completeness-apply", "demo"))
        assert rc == 0
        assert "missing thing" in captured["titles"]

    def test_bare_plan_non_interactive_stdin_exits_2(
        self, tmp_repo, monkeypatch, capsys
    ) -> None:
        import plan_tool.cli.completeness_phases as phases
        from plan_tool.cli import main

        plan_path = tmp_repo.add_plan("1-demo", title="Demo")
        tmp_repo.write_manifest()
        self._save_correctness(tmp_repo, plan_path)

        def fail_walk(*_a, **_k):
            raise AssertionError("walk must not run on non-interactive stdin")

        monkeypatch.setattr(phases, "walk_recommendations", fail_walk)
        monkeypatch.setattr("sys.stdin", SimpleNamespace(isatty=lambda: False))
        rc = main(tmp_repo.argv("completeness-apply", "demo"))
        assert rc == 2
        assert "non-interactive stdin" in capsys.readouterr().err

    def test_bare_plan_blocked_structural_verdict_does_not_reach_the_split_bridge(
        self, tmp_repo, monkeypatch
    ) -> None:
        import plan_tool.cli.completeness_phases as phases
        from plan_tool.cli import main
        from plan_tool.launcher import ApplyFindingResult
        from plan_tool.review_persistence import save_review
        from plan_tool.review_walk import WalkResult

        plan_path = tmp_repo.add_plan("1-demo", title="Demo")
        tmp_repo.write_manifest()
        save_review(
            plan_slug="demo",
            plan_path=plan_path.relative_to(tmp_repo.root).as_posix(),
            repo_root=tmp_repo.root,
            report_md="# report\n",
            recommendations=[
                Recommendation(
                    id="corr-1",
                    source="plan-correctness",
                    severity="high",
                    step_id=1,
                    title="design gap",
                    body="fix the design",
                    anchor="corr-1",
                )
            ],
            kind="completeness",
        )
        escalate_calls: list = []

        def fake_escalate(*_a, **kwargs):
            escalate_calls.append(kwargs)
            return SimpleNamespace(
                outcome="recommended",
                recommendation=SimpleNamespace(
                    suggested_action="plan-tool split demo --step 1"
                ),
            )

        monkeypatch.setattr(
            "plan_tool.launcher.escalate_to_split", fake_escalate
        )

        def fake_apply(plan_path_arg, **kwargs):
            return ApplyFindingResult(
                step_id=1,
                exit_code=0,
                verdict="BLOCKED-STRUCTURAL",
                summary="needs split",
                diff_text="",
                pre_snapshot={plan_path: plan_path.read_text()},
                stdout="## Verdict\nBLOCKED-STRUCTURAL\n",
            )

        from plan_tool import launcher as launcher_module

        monkeypatch.setattr(launcher_module, "apply_finding", fake_apply)

        def fake_walk(saved, *, action_fn, **kwargs):
            for rec in saved.recommendations:
                action_fn(rec)
            return WalkResult(answered=1, quit_early=False)

        monkeypatch.setattr(phases, "walk_recommendations", fake_walk)
        monkeypatch.setattr("sys.stdin", SimpleNamespace(isatty=lambda: True))
        monkeypatch.setattr("builtins.input", lambda *a, **k: "")
        rc = main(
            tmp_repo.argv(
                "completeness-apply", "demo", "--apply-structural"
            )
        )
        assert rc == 0
        assert not escalate_calls or all(
            call.get("allow_split") is False for call in escalate_calls
        )

    def test_fully_detailed_plan_blocked_structural_still_escalates(
        self, tmp_repo, monkeypatch
    ) -> None:
        import plan_tool.cli.completeness_phases as phases
        from plan_tool.cli import main
        from plan_tool.launcher import ApplyFindingResult
        from plan_tool.review_persistence import save_review
        from plan_tool.review_walk import WalkResult

        plan_path = tmp_repo.add_plan("1-demo", title="Demo")
        _attach_minimal_detail(tmp_repo, plan_path)
        tmp_repo.write_manifest()
        save_review(
            plan_slug="demo",
            plan_path=plan_path.relative_to(tmp_repo.root).as_posix(),
            repo_root=tmp_repo.root,
            report_md="# report\n",
            recommendations=[
                Recommendation(
                    id="corr-1",
                    source="plan-correctness",
                    severity="high",
                    step_id=1,
                    title="design gap",
                    body="fix the design",
                    anchor="corr-1",
                )
            ],
            kind="completeness",
        )
        escalate_calls: list = []

        def fake_escalate(*_a, **kwargs):
            escalate_calls.append(kwargs)
            return SimpleNamespace(
                outcome="recommended",
                recommendation=SimpleNamespace(
                    suggested_action="plan-tool split demo --step 1"
                ),
            )

        monkeypatch.setattr(
            "plan_tool.launcher.escalate_to_split", fake_escalate
        )

        def fake_apply(plan_path_arg, **kwargs):
            return ApplyFindingResult(
                step_id=1,
                exit_code=0,
                verdict="BLOCKED-STRUCTURAL",
                summary="needs split",
                diff_text="",
                pre_snapshot={plan_path: plan_path.read_text()},
                stdout="## Verdict\nBLOCKED-STRUCTURAL\n",
            )

        from plan_tool import launcher as launcher_module

        monkeypatch.setattr(launcher_module, "apply_finding", fake_apply)

        def fake_walk(saved, *, action_fn, **kwargs):
            for rec in saved.recommendations:
                action_fn(rec)
            return WalkResult(answered=1, quit_early=False)

        monkeypatch.setattr(phases, "walk_recommendations", fake_walk)
        monkeypatch.setattr("sys.stdin", SimpleNamespace(isatty=lambda: True))
        monkeypatch.setattr("builtins.input", lambda *a, **k: "")
        rc = main(
            tmp_repo.argv(
                "completeness-apply", "demo", "--apply-structural"
            )
        )
        assert rc == 0
        assert len(escalate_calls) == 1
        assert escalate_calls[0]["allow_split"] is True

    def test_fully_detailed_plan_walks_both_conceptual_sources(
        self, tmp_repo, monkeypatch
    ) -> None:
        import plan_tool.cli.completeness_phases as phases
        from plan_tool.cli import main
        from plan_tool.review_walk import WalkResult

        plan_path = tmp_repo.add_plan("1-demo", title="Demo")
        _attach_minimal_detail(tmp_repo, plan_path)
        tmp_repo.write_manifest()
        self._save_both_conceptual(tmp_repo, plan_path)
        seen: dict = {}

        def fake_walk(saved, **kwargs):
            seen["recs"] = list(saved.recommendations)
            return WalkResult(answered=0, quit_early=False)

        monkeypatch.setattr(phases, "walk_recommendations", fake_walk)
        monkeypatch.setattr("sys.stdin", SimpleNamespace(isatty=lambda: True))
        rc = main(tmp_repo.argv("completeness-apply", "demo"))
        assert rc == 0
        assert [r.source for r in seen["recs"]] == [
            "plan-correctness", "plan-completeness"
        ]

    def test_bare_iterate_halt_names_apply_only_for_correctness(
        self, tmp_repo, monkeypatch, capsys
    ) -> None:
        import plan_tool.cli.completeness_phases as cphases
        import plan_tool.review as review_module
        from plan_tool.cli.completeness_cmd import _load_context
        from plan_tool.cli.completeness_phases import _run_iterate_convergence_loop
        from plan_tool.cli.app import build_parser
        from plan_tool.convergence import IterativeBudget
        from plan_tool.parser import parse_plan
        from plan_tool.review import Recommendation

        def _run_with_audit(audit_recs):
            plan_path = tmp_repo.add_plan("1-demo", title="Demo")
            tmp_repo.write_manifest()
            files_coherence = Recommendation(
                id="fc-1",
                source="files-coherence",
                severity="info",
                step_id=1,
                title="citation",
                body="add path",
                anchor="fc-1",
            )
            monkeypatch.setattr(
                review_module,
                "collect_deterministic_findings",
                lambda *a, **k: [files_coherence],
            )
            monkeypatch.setattr(
                review_module,
                "collect_self_consistency_findings",
                lambda *a, **k: [],
            )
            monkeypatch.setattr(
                review_module,
                "audit_plan_until_stable",
                lambda *a, **k: audit_recs,
            )
            monkeypatch.setattr(
                cphases,
                "write_pre_apply_audit_checkpoint",
                lambda *a, **k: None,
            )
            args = build_parser().parse_args(
                tmp_repo.argv(
                    "completeness-audit", "demo", "--iterate", "--yes",
                    "--max-iterations", "1",
                )
            )
            ctx = _load_context(args)
            plan = parse_plan(plan_path)
            bundle_status, audit_stage = _hoisted_bundle(
                plan, plan_path, tmp_repo.root,
            )
            _run_iterate_convergence_loop(
                plan,
                plan_path,
                ctx,
                args,
                IterativeBudget(enabled=True, max_iterations=1),
                bundle_status=bundle_status,
                audit_stage=audit_stage,
                reused_audit_recs=None,
            )

        _run_with_audit([
            Recommendation(
                id="pc-1", source="plan-correctness", severity="high",
                step_id=None, title="gap", body="b", anchor="pc-1",
            ),
        ])
        corr_err = capsys.readouterr().err
        assert "Correctness gap(s) are saved for" in corr_err
        assert "session-directed edit" in corr_err

        _run_with_audit([
            Recommendation(
                id="pcomp-1", source="plan-completeness", severity="medium",
                step_id=None, title="gap", body="b", anchor="pcomp-1",
            ),
        ])
        comp_err = capsys.readouterr().err
        # This stub never populates budget_report, so audit_incomplete is
        # True here -- the incomplete-sample route, not the "stays
        # informational" one (that route requires a qualifying sample; see
        # TestPrintAllAutoApplyDeferredHaltMessage for direct coverage of
        # both).
        assert "audit sample did not qualify" in comp_err
        assert "live sample" in comp_err
        assert "completeness-apply" not in comp_err

    def test_fully_detailed_plan_runs_files_coherence_writer(
        self, tmp_repo, monkeypatch, capsys
    ) -> None:
        import plan_tool.cli.completeness_phases as phases
        from plan_tool.cli import main

        plan_path = tmp_repo.plans_dir / "1-demo.md"
        plan_path.write_text(_COHERENCE_PLAN, encoding="utf-8")
        (tmp_repo.plans_dir / "details").mkdir(parents=True, exist_ok=True)
        (tmp_repo.plans_dir / "details" / "01-touch.md").write_text(
            _COHERENCE_DETAIL, encoding="utf-8"
        )
        tmp_repo.plans = [plan_path]
        tmp_repo.write_manifest()
        self._save_empty_completeness(tmp_repo, plan_path)

        calls: list[tuple[object, object, bool]] = []

        def record_call(plan_path_arg, repo_root_arg, *, apply):
            calls.append((plan_path_arg, repo_root_arg, apply))
            return 0

        monkeypatch.setattr(phases, "_apply_files_coherence", record_call)
        rc = main(tmp_repo.argv("completeness-apply", "demo"))
        assert rc == 0
        assert calls == [(plan_path, tmp_repo.root, True)]
        assert "skipping files-coherence apply" not in capsys.readouterr().err


class TestCompletenessApplyRunLog:
    """``completeness-apply`` persists a RunLogWriter for the walk's
    apply-finding dispatches.

    Regression: the apply-walk built ``_build_review_action_fn`` with no
    ``run_logger``, so a claude failure inside the interactive walk left
    no JSONL trace (unlike the run/detail paths). The command must now
    open a ``completeness-apply`` run log and thread it into the action
    so ``apply_finding`` receives a non-None ``run_logger``.
    """

    pytestmark = pytest.mark.integration

    def test_apply_walk_writes_run_log_and_threads_run_logger(
        self, tmp_repo, monkeypatch
    ) -> None:
        from plan_tool.cli.app import main
        from plan_tool.launcher import ApplyFindingResult
        from plan_tool.review import Recommendation
        from plan_tool.review_persistence import save_review

        plan_path = tmp_repo.add_plan("1-demo", title="Demo Plan")
        _attach_minimal_detail(tmp_repo, plan_path)
        tmp_repo.write_manifest()

        rec = Recommendation(
            id="plan-completeness-gap-1",
            source="plan-completeness",
            severity="medium",
            step_id=1,
            title="a conceptual gap",
            body="close this gap",
        )
        save_review(
            plan_slug="1-demo",
            plan_path=str(plan_path),
            repo_root=tmp_repo.root,
            report_md="report",
            recommendations=[rec],
            kind="completeness",
        )

        captured: dict = {}

        def fake_apply_finding(plan_path_arg, **kwargs):
            captured["run_logger"] = kwargs.get("run_logger")
            return ApplyFindingResult(
                step_id=1, exit_code=0, verdict="APPLIED",
                summary="closed the gap",
                diff_text="--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n+b\n",
                pre_snapshot={plan_path: "a\n"},
                stdout="",
            )

        from plan_tool import launcher as launcher_module
        monkeypatch.setattr(
            launcher_module, "apply_finding", fake_apply_finding
        )

        # The walk is per-finding and TTY-gated now (no blanket auto-apply).
        # Simulate a terminal, drive the walk's per-gap choice to "apply"
        # (a), and auto-confirm the keep-prompt (empty = yes).
        import functools

        import plan_tool.cli.completeness_phases as phases
        from plan_tool.review_walk import (
            walk_recommendations as _real_walk,
        )

        monkeypatch.setattr("sys.stdin", SimpleNamespace(isatty=lambda: True))
        monkeypatch.setattr("builtins.input", lambda *a, **k: "")
        monkeypatch.setattr(
            phases,
            "walk_recommendations",
            functools.partial(_real_walk, input_fn=lambda *a, **k: "a"),
        )

        rc = main(tmp_repo.argv("completeness-apply", "1-demo"))
        assert rc == 0

        # The apply dispatch received a live run_logger (was None before).
        assert "run_logger" in captured
        assert captured["run_logger"] is not None

        # A completeness-apply run log landed with run_start + run_end.
        logs = list(
            (tmp_repo.root / ".plan-tool" / "runs").glob("*/*.jsonl")
        )
        assert logs, "expected a run-log JSONL under .plan-tool/runs/<slug>/"
        events = [
            json.loads(line)
            for line in logs[0].read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert any(
            e.get("event") == "run_start"
            and e.get("command") == "completeness-apply"
            for e in events
        )
        assert any(e.get("event") == "run_end" for e in events)

    def test_keyboard_interrupt_exits_130_after_recording_run_end(
        self, tmp_repo, monkeypatch
    ) -> None:
        from plan_tool.cli.app import main
        import plan_tool.cli.completeness_phases as phases
        from plan_tool.review import Recommendation
        from plan_tool.review_persistence import save_review

        plan_path = tmp_repo.add_plan("1-demo", title="Demo Plan")
        _attach_minimal_detail(tmp_repo, plan_path)
        tmp_repo.write_manifest()
        save_review(
            plan_slug="1-demo",
            plan_path=str(plan_path),
            repo_root=tmp_repo.root,
            report_md="report",
            recommendations=[
                Recommendation(
                    id="plan-completeness-gap-1",
                    source="plan-completeness",
                    severity="medium",
                    step_id=1,
                    title="a conceptual gap",
                    body="close this gap",
                )
            ],
            kind="completeness",
        )
        monkeypatch.setattr("sys.stdin", SimpleNamespace(isatty=lambda: True))
        monkeypatch.setattr(
            phases,
            "walk_recommendations",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(KeyboardInterrupt()),
        )

        with pytest.raises(SystemExit) as exc:
            main(tmp_repo.argv("completeness-apply", "1-demo"))
        assert exc.value.code == 130

        log_path = next(
            (tmp_repo.root / ".plan-tool" / "runs" / "demo").glob("*.jsonl")
        )
        events = [
            json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()
        ]
        assert events[-1]["event"] == "run_end"
        assert events[-1]["rc"] == 130
        assert events[-1]["error"] == "interrupted"


class TestGranularitySmellNeverGates:
    """End-to-end: a granularity smell surfaces in the audit report but
    never flips the exit code — even under ``--fail-on-findings`` — because
    it rides the advisory ``smell_recs`` bucket the blocking gate never reads."""

    pytestmark = pytest.mark.integration

    def _register_granularity_plan(self, tmp_repo):
        path = tmp_repo.plans_dir / "1-gran.md"
        # Intent-bearing so the granularity smell is the only finding — a
        # missing intent blocks and would flip the rc this test pins at 0.
        path.write_text(
            _sectioned_plan_text(
                _GRANULARITY_SPLIT_STEPS.replace(
                    "and add caching\n",
                    "and add caching\n    intent: why the step exists\n",
                ),
                intent=_PLAN_INTENT,
            ),
            encoding="utf-8",
        )
        tmp_repo.plans.append(path)
        tmp_repo.write_manifest()
        return path

    def test_granularity_smell_does_not_flip_rc_under_fail_on_findings(
        self, tmp_repo, monkeypatch, capsys
    ) -> None:
        import plan_tool.review
        from plan_tool.cli import main

        self._register_granularity_plan(tmp_repo)
        # Stub the conceptual audit to find nothing, so the only finding is
        # the deterministic granularity smell.
        monkeypatch.setattr(
            plan_tool.review,
            "shell_review_invoker",
            lambda _p: (
                0,
                "## Correctness findings\n\n_(none)_\n\n"
                "## Completeness findings\n\n_(none)_\n",
            ),
        )

        rc = main(
            tmp_repo.argv("completeness-audit", "gran", "--fail-on-findings")
        )
        out = capsys.readouterr().out
        assert rc == 0
        # The grouped report prints console-rendered (heading markers
        # stripped), so match the section title and the broadened blurb.
        assert "Smells (advisory)" in out
        assert "granularity" in out


class TestDeriveAuditStage:
    """``derive_audit_stage`` — Architecture table for bare vs detail stage."""

    def test_total_zero_is_bare_stage(self) -> None:
        status = DetailBundleStatus(
            total=0, detailed_step_ids=(), bare_step_ids=(),
        )
        assert status.is_bare is False
        assert derive_audit_stage(status) == "bare"

    def test_fully_bare_plan_is_bare_stage(self) -> None:
        status = DetailBundleStatus(
            total=3, detailed_step_ids=(), bare_step_ids=(1, 2, 3),
        )
        assert derive_audit_stage(status) == "bare"

    def test_partial_detail_is_detail_stage(self) -> None:
        status = DetailBundleStatus(
            total=3, detailed_step_ids=(1,), bare_step_ids=(2, 3),
        )
        assert derive_audit_stage(status) == "detail"

    def test_fully_detailed_is_detail_stage(self) -> None:
        status = DetailBundleStatus(
            total=3, detailed_step_ids=(1, 2, 3), bare_step_ids=(),
        )
        assert derive_audit_stage(status) == "detail"


class TestPrintAllAutoApplyDeferredHaltMessage:
    """``_print_all_auto_apply_deferred_halt_message`` -- the four mutually
    exclusive shapes, extracted from the iterate loop's inline cascade."""

    def _bare_status(self) -> DetailBundleStatus:
        return DetailBundleStatus(total=1, detailed_step_ids=(), bare_step_ids=(1,))

    def _detail_status(self) -> DetailBundleStatus:
        return DetailBundleStatus(total=1, detailed_step_ids=(1,), bare_step_ids=())

    def test_bare_with_correctness_names_a_session_directed_edit(self, capsys) -> None:
        from plan_tool.cli.completeness_phases import (
            _print_all_auto_apply_deferred_halt_message,
        )

        corr = _rec("medium", source="plan-correctness")
        _print_all_auto_apply_deferred_halt_message(
            audit_recs=[corr],
            bundle_status=self._bare_status(),
            audit_incomplete=False,
            deferred_count=1,
        )
        err = capsys.readouterr().err
        assert "Correctness gap(s) are saved for" in err
        assert "session-directed edit" in err

    def test_bare_completeness_only_incomplete_names_live_sample(self, capsys) -> None:
        from plan_tool.cli.completeness_phases import (
            _print_all_auto_apply_deferred_halt_message,
        )

        comp = _rec("medium", source="plan-completeness")
        _print_all_auto_apply_deferred_halt_message(
            audit_recs=[comp],
            bundle_status=self._bare_status(),
            audit_incomplete=True,
            deferred_count=1,
        )
        err = capsys.readouterr().err
        assert "audit sample did not qualify" in err
        assert "live sample" in err

    def test_bare_completeness_only_blocking_names_manual_fix(self, capsys) -> None:
        from plan_tool.cli.completeness_phases import (
            _print_all_auto_apply_deferred_halt_message,
        )

        comp = _rec("high", source="plan-completeness")
        _print_all_auto_apply_deferred_halt_message(
            audit_recs=[comp],
            bundle_status=self._bare_status(),
            audit_incomplete=False,
            deferred_count=1,
        )
        err = capsys.readouterr().err
        assert "conceptual completeness gap(s) require a manual plan edit" in err

    def test_bare_completeness_only_non_blocking_stays_informational(
        self, capsys
    ) -> None:
        from plan_tool.cli.completeness_phases import (
            _print_all_auto_apply_deferred_halt_message,
        )

        comp = _rec("medium", source="plan-completeness")
        _print_all_auto_apply_deferred_halt_message(
            audit_recs=[comp],
            bundle_status=self._bare_status(),
            audit_incomplete=False,
            deferred_count=1,
        )
        err = capsys.readouterr().err
        assert "Completeness gap(s) stay informational until a detail bundle exists" in err

    def test_detail_stage_falls_back_to_generic_note(self, capsys) -> None:
        from plan_tool.cli.completeness_phases import (
            _print_all_auto_apply_deferred_halt_message,
        )

        comp = _rec("medium", source="plan-completeness")
        _print_all_auto_apply_deferred_halt_message(
            audit_recs=[comp],
            bundle_status=self._detail_status(),
            audit_incomplete=False,
            deferred_count=1,
        )
        err = capsys.readouterr().err
        assert "Conceptual findings are saved for" in err
        assert "session-directed edit" in err


class TestEmitBarePlanBanner:
    """``emit_bare_plan_banner`` — the operator-facing bare-plan audit signal
    (BACKLOG #61). Bare plan → banner + accurate status; fully-detailed → silent."""

    def test_banner_and_status_for_bare_plan(self, tmp_repo, capsys) -> None:
        from plan_tool.cli.completeness_phases import emit_bare_plan_banner

        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)  # 1 step, no detail
        status = emit_bare_plan_banner(plan, path, tmp_repo.root)
        assert status.is_bare is True
        assert status.is_fully_bare is True
        err = capsys.readouterr().err
        assert "BARE-PLAN AUDIT" in err
        assert "detail/code-grounded findings require a detail bundle" in err.lower()
        assert "plan-tool detail" not in err

    def test_silent_when_fully_detailed(self, tmp_repo, capsys) -> None:
        from plan_tool.cli.completeness_phases import emit_bare_plan_banner
        from plan_tool.detail import derive_detail_path

        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        dp = derive_detail_path(path, plan, plan.steps[0])
        dp.parent.mkdir(parents=True, exist_ok=True)
        dp.write_text("## Acceptance criteria\n\nbody\n", encoding="utf-8")
        status = emit_bare_plan_banner(plan, path, tmp_repo.root)
        assert status.is_bare is False
        err = capsys.readouterr().err
        assert "BARE-PLAN AUDIT" not in err

    def test_emit_bare_plan_banner_uses_passed_status(
        self, tmp_repo, monkeypatch, capsys
    ) -> None:
        from plan_tool.cli.completeness_phases import emit_bare_plan_banner

        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        status = DetailBundleStatus(
            total=1, detailed_step_ids=(), bare_step_ids=(1,),
        )

        def _boom(*_a, **_kw):
            raise AssertionError("audit_detail_bundle_status must not run")

        monkeypatch.setattr(
            "plan_tool.review.audit_detail_bundle_status", _boom
        )
        returned = emit_bare_plan_banner(
            plan, path, tmp_repo.root, bundle_status=status,
        )
        assert returned is status
        assert "BARE-PLAN AUDIT" in capsys.readouterr().err


class TestDetailBundleStaleness:
    """``_detail_bundle_staleness`` — apply-walk freshness gate (BACKLOG #61
    slice 3). Flags detail files changed since the saved audit; silent for
    legacy saves that predate the snapshot."""

    def test_flags_drift_and_clean(self, tmp_repo) -> None:
        from types import SimpleNamespace
        from plan_tool.cli.completeness_phases import _detail_bundle_staleness
        from plan_tool.fingerprint import compute_detail_bundle_fingerprint
        from plan_tool.detail import derive_detail_path

        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        dp = derive_detail_path(path, plan, plan.steps[0])
        dp.parent.mkdir(parents=True, exist_ok=True)
        dp.write_text("## Acceptance criteria\n\noriginal\n", encoding="utf-8")
        snapshot = compute_detail_bundle_fingerprint(plan, path, tmp_repo.root)
        saved = SimpleNamespace(
            detail_bundle_fingerprint=snapshot,
            detail_bundle_fingerprint_present=True,
        )
        # No drift right after the snapshot.
        assert _detail_bundle_staleness(saved, path, tmp_repo.root) == []
        # Mutate the detail file → drift flagged.
        dp.write_text("## Acceptance criteria\n\nCHANGED\n", encoding="utf-8")
        drifted = _detail_bundle_staleness(saved, path, tmp_repo.root)
        assert len(drifted) == 1

    def test_empty_for_legacy_save_without_snapshot(self, tmp_repo) -> None:
        from types import SimpleNamespace
        from plan_tool.cli.completeness_phases import _detail_bundle_staleness

        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        saved = SimpleNamespace(
            detail_bundle_fingerprint={},
            detail_bundle_fingerprint_present=False,
        )
        assert _detail_bundle_staleness(saved, path, tmp_repo.root) == []


class TestEffectiveAuditPasses:
    """`_effective_audit_passes` — static default of 3 full audit passes;
    an explicit `--audit-passes` (or its `--audit-samples` alias) wins. The
    count is NOT scaled by plan size: each pass is a full independent audit
    over the whole plan + code, so extra passes only re-roll LLM
    non-determinism (the old `clamp(2·steps + dep_edges, 8, 16)` sizing was
    reverted — #59/#60)."""

    def test_default_is_static_three(self) -> None:
        from types import SimpleNamespace
        from plan_tool.cli.completeness_cmd import _effective_audit_passes

        args = SimpleNamespace(audit_passes=None)
        assert _effective_audit_passes(args) == 3

    def test_explicit_audit_passes_wins(self) -> None:
        from types import SimpleNamespace
        from plan_tool.cli.completeness_cmd import _effective_audit_passes

        args = SimpleNamespace(audit_passes=7)
        assert _effective_audit_passes(args) == 7

    def test_missing_attr_falls_back_to_default(self) -> None:
        from types import SimpleNamespace
        from plan_tool.cli.completeness_cmd import _effective_audit_passes

        # A caller that doesn't carry the parsed flag still gets the static 3.
        assert _effective_audit_passes(SimpleNamespace()) == 3


class TestEmitCoverageUnconfirmed:
    """`emit_coverage_unconfirmed` — budget-limited trust signal (BACKLOG #60c)."""

    def test_fires_when_budget_limited(self, capsys) -> None:
        from plan_tool.cli.completeness_phases import emit_coverage_unconfirmed

        fired = emit_coverage_unconfirmed(
            {"budget_limited": True, "passes_used": 16}
        )
        assert fired is True
        err = capsys.readouterr().err
        assert "COVERAGE UNCONFIRMED" in err
        assert "16 pass" in err

    def test_silent_when_clean_or_absent(self, capsys) -> None:
        from plan_tool.cli.completeness_phases import emit_coverage_unconfirmed

        assert emit_coverage_unconfirmed({"budget_limited": False}) is False
        assert emit_coverage_unconfirmed({}) is False
        assert capsys.readouterr().err == ""

    def test_omits_retired_data_driven_advice_when_present(self, capsys) -> None:
        from plan_tool.cli.completeness_phases import emit_coverage_unconfirmed

        emit_coverage_unconfirmed({
            "budget_limited": True,
            "passes_used": 5,
            "recommendation_advice": "retired route",
        })
        err = capsys.readouterr().err
        assert "retired route" not in err
        assert "--audit-passes" not in err

    def test_reports_budget_facts_without_generic_advice(
        self, capsys
    ) -> None:
        from plan_tool.cli.completeness_phases import emit_coverage_unconfirmed

        emit_coverage_unconfirmed({"budget_limited": True, "passes_used": 5})
        err = capsys.readouterr().err
        assert "COVERAGE UNCONFIRMED" in err
        assert "--audit-passes" not in err

    def test_emit_coverage_unconfirmed_fires_even_when_sample_qualifies(
        self, capsys
    ) -> None:
        """Pass-conformance (well-formedness) is not a confirmation signal.

        ``normalize_audit_coverage`` enforces that a valid ``budget_limited``
        coverage object always has ``confirmation_kind is None``, and a
        still-discovering run's individual passes ordinarily parse fine --
        so a "qualifying" (well-formed) sample says nothing about whether
        the audit actually converged. The warning must fire on
        ``budget_limited`` alone.
        """
        from plan_tool.cli.completeness_phases import emit_coverage_unconfirmed

        fired = emit_coverage_unconfirmed(
            _qualifying_producer_coverage(
                budget_limited=True, passes_used=3, cap=3,
            )
        )
        assert fired is True
        assert "COVERAGE UNCONFIRMED" in capsys.readouterr().err

    def test_plan_quota_coverage_warning_names_the_terminal_reason(
        self, capsys
    ) -> None:
        from plan_tool.cli.completeness_phases import emit_coverage_unconfirmed

        assert emit_coverage_unconfirmed(
            {"early_stop_reason": "plan-quota", "passes_used": 2}
        ) is True
        message = capsys.readouterr().err
        assert "terminal plan quota" in message
        assert "pass cap" not in message

    def test_reused_plan_quota_skips_generic_live_audit_advice(self, capsys) -> None:
        from plan_tool.cli.completeness_phases import _warn_if_audit_incomplete

        _warn_if_audit_incomplete(
            {"early_stop_reason": "plan-quota", "passes_used": 2}, reuse=True
        )

        message = capsys.readouterr().err
        assert "terminal plan quota" in message
        assert "re-run with a live audit pass" not in message

    def test_live_plan_quota_warns_without_caller_side_coordination(self, capsys) -> None:
        from plan_tool.cli.completeness_phases import _warn_if_audit_incomplete

        _warn_if_audit_incomplete(
            {"early_stop_reason": "plan-quota", "passes_used": 2}, reuse=False
        )

        message = capsys.readouterr().err
        assert "terminal plan quota" in message
        assert "re-run with a live audit pass" not in message


class TestRenderCoverageConfidenceMarkdown:
    def test_render_coverage_confidence_fires_even_when_sample_qualifies(
        self,
    ) -> None:
        """Companion to the ``emit_coverage_unconfirmed`` case above: the
        markdown callout must not be silenced by pass-conformance either."""
        from plan_tool.cli.completeness_phases import (
            _render_coverage_confidence_markdown,
        )

        md = _render_coverage_confidence_markdown(
            _qualifying_producer_coverage(
                budget_limited=True, passes_used=3, cap=3,
            )
        )
        assert md is not None
        assert "Coverage unconfirmed" in md

    def test_plan_quota_coverage_markdown_names_the_terminal_reason(self) -> None:
        from plan_tool.cli.completeness_phases import (
            _render_coverage_confidence_markdown,
        )

        md = _render_coverage_confidence_markdown(
            {
                "budget_limited": False,
                "passes_used": 2,
                "cap": 3,
                "recommendation_kind": None,
                "recommended_passes": None,
                "recommendation_advice": None,
                "confirmation_kind": None,
                "conforming_pass_count": 1,
                "failed_or_malformed_pass_count": 1,
                "early_stop_reason": "plan-quota",
            }
        )

        assert md is not None
        assert "terminal plan quota" in md
        assert "pass cap" not in md

    def test_partial_plan_quota_coverage_keeps_the_terminal_reason(self) -> None:
        from plan_tool.cli.completeness_phases import (
            _render_coverage_confidence_markdown,
        )

        md = _render_coverage_confidence_markdown(
            {
                "budget_limited": False,
                "passes_used": 2,
                "early_stop_reason": "plan-quota",
            }
        )

        assert md is not None
        assert "terminal plan quota" in md


# --------------------------------------------------------------------------
# Step 4 — carried_findings wiring into the two apply sites
# --------------------------------------------------------------------------


def test_carried_findings_do_not_touch_scope_guard_surface() -> None:
    """The advisory carried context is structurally independent of the scope
    guard: ``compute_in_scope_paths`` takes no ``carried_findings``, the loop
    computes it once before the per-finding round loop, and the context flows
    only to ``apply_finding``."""
    import inspect

    from plan_tool.cli.completeness_phases import _run_iterate_convergence_loop
    from plan_tool.scope_guard import compute_in_scope_paths

    assert "carried_findings" not in inspect.signature(
        compute_in_scope_paths
    ).parameters

    src = inspect.getsource(_run_iterate_convergence_loop)
    assert "in_scope = compute_in_scope_paths(" in src
    # in_scope is computed once, ahead of the per-finding apply loop.
    assert src.index("in_scope = compute_in_scope_paths(") < src.index(
        "while True"
    )
    # The carried set reaches apply_finding only; the scope-guard call stays
    # carried-free.
    assert "carried_findings=carried" in src


def test_iterate_loop_reverts_on_post_edit_parse_failure() -> None:
    """The completeness iterate loop must hard-revert a parse-breaking
    apply before the next finding — mirroring review_actions."""
    import inspect

    from plan_tool.cli.completeness_phases import _run_iterate_convergence_loop

    src = inspect.getsource(_run_iterate_convergence_loop)
    revert = "apply_reverted = revert_apply_if_parse_broken(apply_result)"
    assert revert in src
    assert src.index(revert) < src.index("run_logger.phase_end(", src.index(revert))
    assert '"reverted" if apply_reverted' in src
    assert "plan failed to parse before apply_finding" in src


def test_iterate_loop_halts_with_populated_outcome() -> None:
    """Halt paths return halt_reason + audit_recs so finalize can persist."""
    import inspect

    from plan_tool.cli.completeness_phases import _run_iterate_convergence_loop

    src = inspect.getsource(_run_iterate_convergence_loop)
    assert "def _halt(reason: str)" in src
    assert "halt_reason=reason" in src
    assert "return _halt(" in src
    assert "return _IterateOutcome(early_exit_code=2)" not in src


def test_cmd_completeness_hoists_bundle_status_once() -> None:
    from plan_tool.cli.completeness_cmd import cmd_completeness

    src = inspect.getsource(cmd_completeness)
    hoist_at = src.index("audit_detail_bundle_status(")
    iterate_at = src.index("if budget.enabled:")
    assert hoist_at < iterate_at
    assert "derive_audit_stage(bundle_status)" in src


def test_iterate_loop_does_not_call_audit_detail_bundle_status() -> None:
    from plan_tool.cli.completeness_phases import _run_iterate_convergence_loop

    src = inspect.getsource(_run_iterate_convergence_loop)
    assert "audit_detail_bundle_status(" not in src


def test_sampled_audit_stage_uses_shared_stage_derivation() -> None:
    """A partial captured bundle remains a detail-stage audit everywhere."""
    import inspect

    from plan_tool.cli.completeness_cmd import cmd_completeness
    from plan_tool.cli.completeness_phases import _run_iterate_convergence_loop

    assert "derive_audit_stage(sampled_bundle_status)" in inspect.getsource(
        cmd_completeness
    )
    assert "derive_audit_stage(sampled_bundle_status)" in inspect.getsource(
        _run_iterate_convergence_loop
    )


def test_cmd_completeness_uses_plan_captured_after_pre_capture_edit(
    tmp_repo, monkeypatch
) -> None:
    """A capture-time edit cannot split later evaluation from audit inputs."""
    import plan_tool.cli.completeness_cmd as completeness_cmd
    from plan_tool.cli import main
    from plan_tool.review_persistence import AuditInputSnapshot

    _plan, path = _write_and_parse(
        tmp_repo, _INTENT_BEARING_STEPS, intent=_PLAN_INTENT,
    )
    tmp_repo.plans.append(path)
    tmp_repo.write_manifest()
    captured_text = _sectioned_plan_text(
        _INTENT_BEARING_STEPS, intent=_PLAN_INTENT,
    ).replace("Sectioned Plan", "Captured Snapshot")
    real_capture = AuditInputSnapshot.capture

    def capture_after_edit(plan_path, repo_root, **kwargs):
        plan_path.write_text(captured_text, encoding="utf-8")
        return real_capture(plan_path, repo_root, **kwargs)

    seen: list[str] = []

    def fake_reuse(plan, *_args, **_kwargs):
        seen.append(plan.title)
        return None

    def fake_finalize(plan, *_args, **_kwargs):
        seen.append(plan.title)
        return 0

    monkeypatch.setattr(AuditInputSnapshot, "capture", capture_after_edit)
    monkeypatch.setattr(completeness_cmd, "_resolve_audit_reuse", fake_reuse)
    monkeypatch.setattr(completeness_cmd, "finalize_completeness_run", fake_finalize)

    assert main(tmp_repo.argv("completeness-audit", "1-sectioned", "--json")) == 0
    assert seen == ["Captured Snapshot", "Captured Snapshot"]


def test_iterate_phase_uses_supplied_captured_plan(tmp_repo) -> None:
    """Programmatic iterate callers get the same captured-plan invariant."""
    from plan_tool.review_persistence import AuditInputSnapshot

    stale_plan, path = _write_and_parse(
        tmp_repo, _INTENT_BEARING_STEPS, intent=_PLAN_INTENT,
    )
    path.write_text(
        _sectioned_plan_text(
            _INTENT_BEARING_STEPS, intent=_PLAN_INTENT,
        ).replace("Sectioned Plan", "Captured Snapshot"),
        encoding="utf-8",
    )
    snapshot = AuditInputSnapshot.capture(path, tmp_repo.root)
    bundle_status, audit_stage = _hoisted_bundle(stale_plan, path, tmp_repo.root)

    outcome = _run_iterate_convergence_loop(
        stale_plan,
        path,
        SimpleNamespace(repo_root=tmp_repo.root),
        SimpleNamespace(name="1-sectioned"),
        IterativeBudget(enabled=False),
        bundle_status=bundle_status,
        audit_stage=audit_stage,
        audit_input_snapshot=snapshot,
    )

    assert outcome.plan.title == "Captured Snapshot"


def test_finalize_does_not_call_audit_detail_bundle_status() -> None:
    from plan_tool.cli.completeness_cmd import finalize_completeness_run

    src = inspect.getsource(finalize_completeness_run)
    assert "audit_detail_bundle_status(" not in src


def test_checkpoint_accepts_threaded_bundle_status() -> None:
    from plan_tool.cli.completeness_phases import write_pre_apply_audit_checkpoint

    src = inspect.getsource(write_pre_apply_audit_checkpoint)
    assert "bundle_status" in inspect.signature(
        write_pre_apply_audit_checkpoint
    ).parameters
    assert "detail_grade" not in inspect.signature(
        write_pre_apply_audit_checkpoint
    ).parameters
    assert "audit_detail_bundle_status(" not in src


def test_step_less_plan_stage_bare_via_hoist(
    tmp_repo, monkeypatch, capsys
) -> None:
    from plan_tool.cli import main
    from plan_tool.convergence import STAGE_BARE

    plan, path = _write_and_parse(
        tmp_repo, _INTENT_BEARING_STEPS, intent=_PLAN_INTENT,
    )
    tmp_repo.plans.append(path)
    tmp_repo.write_manifest()
    zero_status = DetailBundleStatus(
        total=0, detailed_step_ids=(), bare_step_ids=(),
    )
    monkeypatch.setattr(
        "plan_tool.review.audit_detail_bundle_status",
        lambda *a, **k: zero_status,
    )
    seen: list = []

    def _record_stage(status):
        seen.append(status.total)
        return STAGE_BARE

    monkeypatch.setattr(
        "plan_tool.cli.completeness_cmd.derive_audit_stage", _record_stage
    )
    monkeypatch.setattr(
        "plan_tool.review.audit_plan_until_stable", lambda *a, **k: []
    )
    rc = main(
        tmp_repo.argv(
            "completeness-audit", "1-sectioned", "-y", "--audit-passes", "1",
        )
    )
    assert rc == 0
    # The persisted audit stage is derived once from the current hoisted
    # status, then once from the independently captured audit input.
    assert seen == [0, 1]


def test_iterate_loop_writes_pre_apply_checkpoint() -> None:
    import inspect

    from plan_tool.cli.completeness_phases import _run_iterate_convergence_loop

    src = inspect.getsource(_run_iterate_convergence_loop)
    assert "write_pre_apply_audit_checkpoint(" in src
    checkpoint_at = src.index("write_pre_apply_audit_checkpoint(")
    while_at = src.index("while True:")
    assert checkpoint_at < while_at


def test_cmd_completeness_finalizes_on_halt() -> None:
    """Orchestrator must not return before the report tail on iterate halt."""
    import inspect

    from plan_tool.cli.completeness_cmd import cmd_completeness

    src = inspect.getsource(cmd_completeness)
    assert "finalize_completeness_run(" in src
    assert "return outcome.early_exit_code" not in src


def test_build_report_md_includes_halt_section() -> None:
    from plan_tool.completeness_report import build_report_md

    md = build_report_md(
        plan_title="Demo",
        plan_name="demo",
        iterate_enabled=True,
        stop_reason="halted: parse failure",
        iterations=1,
        applied=(),
        deferred={},
        advisory_conceptual=(),
        open_findings=(),
        grouped_report_md="",
        correctness=(),
        smells=(),
        plan=None,
        halt_reason="plan failed to parse after apply_finding",
    )
    assert "## Halt" in md
    assert "plan failed to parse after apply_finding" in md


class TestFinalizeCompletenessRun:
    """``finalize_completeness_run`` persists a report even on iterate halt."""

    def test_fresh_audit_only_persists_coverage_before_reuse(
        self, tmp_repo, monkeypatch, capsys
    ) -> None:
        plan, path = _write_and_parse(
            tmp_repo, _INTENT_BEARING_STEPS, intent=_PLAN_INTENT
        )
        coverage = {
            "budget_limited": True,
            "passes_used": 3,
            "cap": 3,
            "recommendation_kind": None,
            "recommended_passes": None,
            "recommendation_advice": None,
            "confirmation_kind": None,
            "conforming_pass_count": 1,
            "failed_or_malformed_pass_count": 0,
        }

        def fresh_audit(*_args, budget_report, **_kwargs):
            budget_report.update(coverage)
            return []

        monkeypatch.setattr(
            "plan_tool.cli.completeness_cmd._sample_conceptual_audit",
            fresh_audit,
        )
        bundle_status, audit_stage = _hoisted_bundle(plan, path, tmp_repo.root)
        rc = finalize_completeness_run(
            plan,
            path,
            SimpleNamespace(repo_root=tmp_repo.root),
            SimpleNamespace(
                name="1-sectioned", json=False, fail_on_findings=False, commit=False
            ),
            budget=IterativeBudget(enabled=False),
            outcome=_IterateOutcome(),
            reused_audit_recs=None,
            code_drifted=False,
            audit_passes=3,
            audit_dry_rounds=1,
            bundle_status=bundle_status,
            audit_stage=audit_stage,
        )

        assert rc == 0
        sidecars = list(plan_reports_dir(path).glob("*-completeness.json"))
        assert len(sidecars) == 1
        assert load_review(sidecars[0]).audit_coverage == coverage
        # budget_limited=True means unconfirmed regardless of pass-conformance
        # (see _conceptual_bar_from_audit_recs) -- the callout must appear.
        assert "Coverage unconfirmed" in capsys.readouterr().out

    def test_audit_incomplete_warning_prints_exactly_once(
        self, tmp_repo, monkeypatch, capsys
    ) -> None:
        """The audit-only (non-iterate) markdown path used to print
        ``_warn_audit_incomplete`` twice for the identical event -- once
        unconditionally right after computing ``audit_incomplete``, and
        again later, guarded on the same ``outcome.audit_recs is None``
        condition, right before the ``--fail-on-findings`` check."""
        plan, path = _write_and_parse(
            tmp_repo, _INTENT_BEARING_STEPS, intent=_PLAN_INTENT
        )
        coverage = {
            "budget_limited": False,
            "passes_used": 1,
            "cap": 1,
            "recommendation_kind": None,
            "recommended_passes": None,
            "recommendation_advice": None,
            "confirmation_kind": None,
            "conforming_pass_count": 0,
            "failed_or_malformed_pass_count": 1,
        }

        def fresh_audit(*_args, budget_report, **_kwargs):
            budget_report.update(coverage)
            return []

        monkeypatch.setattr(
            "plan_tool.cli.completeness_cmd._sample_conceptual_audit",
            fresh_audit,
        )
        bundle_status, audit_stage = _hoisted_bundle(plan, path, tmp_repo.root)
        rc = finalize_completeness_run(
            plan,
            path,
            SimpleNamespace(repo_root=tmp_repo.root),
            SimpleNamespace(
                name="1-sectioned", json=False, fail_on_findings=False, commit=False
            ),
            budget=IterativeBudget(enabled=False),
            outcome=_IterateOutcome(),
            reused_audit_recs=None,
            code_drifted=False,
            audit_passes=3,
            audit_dry_rounds=1,
            bundle_status=bundle_status,
            audit_stage=audit_stage,
        )

        assert rc == 0
        err = capsys.readouterr().err
        assert err.count("did not produce a qualifying sample") == 1

    @staticmethod
    def _finalize_with_sample(tmp_repo, monkeypatch, coverage, recs, **arg_overrides):
        plan, path = _write_and_parse(
            tmp_repo, _INTENT_BEARING_STEPS, intent=_PLAN_INTENT
        )

        def fresh_audit(*_args, budget_report, **_kwargs):
            budget_report.update(coverage)
            return list(recs)

        monkeypatch.setattr(
            "plan_tool.cli.completeness_cmd._sample_conceptual_audit",
            fresh_audit,
        )
        bundle_status, audit_stage = _hoisted_bundle(plan, path, tmp_repo.root)
        sink: list = []
        args = SimpleNamespace(
            name="1-sectioned", json=False, fail_on_findings=False, commit=False,
            _blocking_verdict_sink=sink,
        )
        for key, value in arg_overrides.items():
            setattr(args, key, value)
        rc = finalize_completeness_run(
            plan,
            path,
            SimpleNamespace(repo_root=tmp_repo.root),
            args,
            budget=IterativeBudget(enabled=False),
            outcome=_IterateOutcome(),
            reused_audit_recs=None,
            code_drifted=False,
            audit_passes=3,
            audit_dry_rounds=1,
            bundle_status=bundle_status,
            audit_stage=audit_stage,
        )
        return rc, sink

    def test_budget_limited_audit_keeps_blocking_ids_on_incomplete_verdict(
        self, tmp_repo, monkeypatch
    ) -> None:
        """Deliberate: the gate's ids are () on an incomplete audit but the
        verdict still names the HIGH correctness gap the sample found."""
        corr = _rec("high", source="plan-correctness")
        coverage = _qualifying_producer_coverage(
            budget_limited=True, passes_used=3, cap=3,
        )
        rc, sink = self._finalize_with_sample(
            tmp_repo, monkeypatch, coverage, [corr]
        )
        assert rc == 0
        (verdict,) = sink
        assert verdict.state == "incomplete"
        assert corr.id in verdict.blocking_ids
        from plan_tool.completeness_report import _verdict_offers_stage

        assert _verdict_offers_stage(verdict) is False

    def test_incomplete_audit_does_not_flip_has_blocking_findings(
        self, tmp_repo, monkeypatch, capsys
    ) -> None:
        """Only the verdict gains ids: ``--fail-on-findings`` and
        ``has_blocking_findings`` keep the incomplete-audit non-blocking gate."""
        corr = _rec("high", source="plan-correctness")
        coverage = _qualifying_producer_coverage(
            budget_limited=True, passes_used=3, cap=3,
        )
        rc, sink = self._finalize_with_sample(
            tmp_repo, monkeypatch, coverage, [corr],
            json=True, fail_on_findings=True,
        )
        payload = json.loads(capsys.readouterr().out)
        assert payload["has_blocking_findings"] is False
        assert sink[0].blocking_ids == (corr.id,)
        # An incomplete audit is already not clean under --fail-on-findings;
        # the rc must equal the same audit's rc with no ids to retain.
        rc_without_ids, _ = self._finalize_with_sample(
            tmp_repo, monkeypatch, coverage, [],
            json=True, fail_on_findings=True,
        )
        capsys.readouterr()
        assert rc == rc_without_ids

    def test_finalize_passes_one_verdict_to_every_list_reader(
        self, tmp_repo, monkeypatch
    ) -> None:
        """The grouped report, the persist call, and the verdict sink all
        receive the same ``BlockingVerdict`` object finalize built once."""
        import plan_tool.cli.completeness_cmd as cmd

        seen: dict[str, object] = {}
        real_render = cmd._render_grouped_report
        real_persist = cmd._persist_and_present_report

        def render(*a, **kw):
            seen["render"] = kw.get("verdict")
            return real_render(*a, **kw)

        def persist(*a, **kw):
            seen["persist"] = kw.get("verdict")
            return real_persist(*a, **kw)

        monkeypatch.setattr(cmd, "_render_grouped_report", render)
        monkeypatch.setattr(cmd, "_persist_and_present_report", persist)
        corr = _rec("high", source="plan-correctness")
        coverage = _qualifying_producer_coverage(
            budget_limited=True, passes_used=3, cap=3,
        )
        _, sink = self._finalize_with_sample(
            tmp_repo, monkeypatch, coverage, [corr]
        )
        (verdict,) = sink
        assert seen["render"] is verdict
        assert seen["persist"] is verdict

    def test_json_payload_gate_fields_do_not_follow_the_verdict_ids(
        self, tmp_repo, monkeypatch, capsys
    ) -> None:
        """Deliberate: an incomplete audit's verdict keeps its ids while the
        ``--json`` gate fields stay the gate's (null ids, non-blocking)."""
        corr = _rec("high", source="plan-correctness")
        coverage = _qualifying_producer_coverage(
            budget_limited=True, passes_used=3, cap=3,
        )
        _, sink = self._finalize_with_sample(
            tmp_repo, monkeypatch, coverage, [corr], json=True,
        )
        payload = json.loads(capsys.readouterr().out)
        assert sink[0].blocking_ids == (corr.id,)
        assert payload["conceptual_bar_blocking_ids"] is None
        assert payload["has_blocking_findings"] is False

    def test_unqualified_audit_keeps_ids_and_offers_no_stage(
        self, tmp_repo, monkeypatch
    ) -> None:
        corr = _rec("high", source="plan-correctness")
        coverage = {
            "budget_limited": False,
            "passes_used": 1,
            "cap": 1,
            "recommendation_kind": None,
            "recommended_passes": None,
            "recommendation_advice": None,
            "confirmation_kind": None,
            "conforming_pass_count": 0,
            "failed_or_malformed_pass_count": 1,
        }
        rc, sink = self._finalize_with_sample(
            tmp_repo, monkeypatch, coverage, [corr]
        )
        assert rc == 0
        from plan_tool.completeness_report import _verdict_offers_stage

        assert sink[0].blocking_ids == (corr.id,)
        assert _verdict_offers_stage(sink[0]) is False

    def test_complete_audit_gate_and_verdict_ids_agree(self) -> None:
        """On a qualified sample the gate's ids equal the stage bar's ids, so
        the verdict copy and the gate copy cannot diverge when complete."""
        from plan_tool.cli.completeness_cmd import (
            _conceptual_bar_from_audit_recs,
            compute_conceptual_bar_blocking_ids,
        )

        corr = _rec("high", source="plan-correctness")
        coverage = _qualifying_producer_coverage()
        gate_ids, incomplete = _conceptual_bar_from_audit_recs(
            [corr], audit_stage="detail", coverage=coverage
        )
        assert incomplete is False
        assert gate_ids == compute_conceptual_bar_blocking_ids(
            [corr], audit_stage="detail"
        )
        assert corr.id in gate_ids

    def test_conceptual_bar_pair_still_returns_empty_ids_when_incomplete(
        self,
    ) -> None:
        """The gate pair keeps its meaning; only the verdict copy gains ids."""
        from plan_tool.cli.completeness_cmd import _conceptual_bar_from_audit_recs

        corr = _rec("high", source="plan-correctness")
        coverage = _qualifying_producer_coverage(
            budget_limited=True, passes_used=3, cap=3,
        )
        assert _conceptual_bar_from_audit_recs(
            [corr], audit_stage="detail", coverage=coverage
        ) == ((), True)

    def test_budget_limited_conforming_sample_gets_no_conformance_warning(
        self, tmp_repo, monkeypatch, capsys
    ) -> None:
        """A still-discovering audit whose every attempted pass parsed fine
        (``budget_limited=True`` but pass-conformant) must print only the
        budget-limited callout, never ``_warn_audit_incomplete``'s
        conformance-specific message -- that message is reserved for a
        sample that genuinely failed to parse, and printing it here told the
        operator to ``--no-reuse-audit`` for the wrong reason."""
        plan, path = _write_and_parse(
            tmp_repo, _INTENT_BEARING_STEPS, intent=_PLAN_INTENT
        )
        coverage = _qualifying_producer_coverage(
            budget_limited=True, passes_used=3, cap=3,
        )

        def fresh_audit(*_args, budget_report, **_kwargs):
            budget_report.update(coverage)
            return []

        monkeypatch.setattr(
            "plan_tool.cli.completeness_cmd._sample_conceptual_audit",
            fresh_audit,
        )
        bundle_status, audit_stage = _hoisted_bundle(plan, path, tmp_repo.root)
        rc = finalize_completeness_run(
            plan,
            path,
            SimpleNamespace(repo_root=tmp_repo.root),
            SimpleNamespace(
                name="1-sectioned", json=False, fail_on_findings=False, commit=False
            ),
            budget=IterativeBudget(enabled=False),
            outcome=_IterateOutcome(),
            reused_audit_recs=None,
            code_drifted=False,
            audit_passes=3,
            audit_dry_rounds=1,
            bundle_status=bundle_status,
            audit_stage=audit_stage,
        )

        assert rc == 0
        captured = capsys.readouterr()
        assert "did not produce a qualifying sample" not in captured.err
        assert "pass-conformance evidence" not in captured.err
        assert "Coverage unconfirmed" in captured.out

    def test_audit_only_reuse_replays_budget_coverage_without_audit(
        self, tmp_repo, monkeypatch, capsys
    ) -> None:
        import plan_tool.cli.completeness_cmd as completeness_cmd

        plan, path = _write_and_parse(
            tmp_repo, _INTENT_BEARING_STEPS, intent=_PLAN_INTENT
        )
        coverage = _observed_audit_coverage(
            budget_limited=True,
            passes_used=3,
            cap=3,
            confirmation_kind=None,
            conforming_pass_count=0,
            failed_or_malformed_pass_count=1,
        )

        def audit_should_not_run(*_args, **_kwargs):
            raise AssertionError("reused coverage must not trigger a conceptual audit")

        monkeypatch.setattr(
            completeness_cmd, "_sample_conceptual_audit", audit_should_not_run
        )
        from plan_tool.review_persistence import AuditInputSnapshot

        snapshot = AuditInputSnapshot.capture(path, tmp_repo.root)
        args = SimpleNamespace(
            name="1-sectioned", json=False, fail_on_findings=False, commit=False
        )
        bundle_status, audit_stage = _hoisted_bundle(plan, path, tmp_repo.root)
        rc = finalize_completeness_run(
            plan,
            path,
            SimpleNamespace(repo_root=tmp_repo.root),
            args,
            budget=IterativeBudget(enabled=False),
            outcome=_IterateOutcome(),
            reused_audit_recs=[],
            reused_audit_coverage=coverage,
            code_drifted=False,
            audit_passes=3,
            audit_dry_rounds=1,
            bundle_status=bundle_status,
            audit_stage=audit_stage,
            audit_input_snapshot=snapshot,
            sampled_audit_stage=audit_stage,
        )

        assert rc == 0
        assert "Coverage unconfirmed" in capsys.readouterr().out
        assert not list(plan_reports_dir(path).glob("*-completeness.json"))

        args.json = True
        rc = finalize_completeness_run(
            plan,
            path,
            SimpleNamespace(repo_root=tmp_repo.root),
            args,
            budget=IterativeBudget(enabled=False),
            outcome=_IterateOutcome(),
            reused_audit_recs=[],
            reused_audit_coverage=coverage,
            code_drifted=False,
            audit_passes=3,
            audit_dry_rounds=1,
            bundle_status=bundle_status,
            audit_stage=audit_stage,
            audit_input_snapshot=snapshot,
            sampled_audit_stage=audit_stage,
        )
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["coverage"] == coverage
        assert payload["qualified_result"]["coverage"] == "unconfirmed"

    def test_coverage_less_reuse_renders_unknown_without_audit(
        self, tmp_repo, monkeypatch, capsys
    ) -> None:
        import plan_tool.cli.completeness_cmd as completeness_cmd

        plan, path = _write_and_parse(
            tmp_repo, _INTENT_BEARING_STEPS, intent=_PLAN_INTENT
        )
        coverage = _ru().audit_coverage
        monkeypatch.setattr(
            completeness_cmd,
            "_sample_conceptual_audit",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("legacy reuse must not trigger a conceptual audit")
            ),
        )
        args = SimpleNamespace(
            name="1-sectioned", json=False, fail_on_findings=False, commit=False
        )
        bundle_status, audit_stage = _hoisted_bundle(plan, path, tmp_repo.root)
        assert finalize_completeness_run(
            plan,
            path,
            SimpleNamespace(repo_root=tmp_repo.root),
            args,
            budget=IterativeBudget(enabled=False),
            outcome=_IterateOutcome(),
            reused_audit_recs=[],
            reused_audit_coverage=coverage,
            code_drifted=False,
            audit_passes=3,
            audit_dry_rounds=1,
            bundle_status=bundle_status,
            audit_stage=audit_stage,
        ) == 0
        assert "Coverage confidence unknown" in capsys.readouterr().out

        args.json = True
        assert finalize_completeness_run(
            plan,
            path,
            SimpleNamespace(repo_root=tmp_repo.root),
            args,
            budget=IterativeBudget(enabled=False),
            outcome=_IterateOutcome(),
            reused_audit_recs=[],
            reused_audit_coverage=coverage,
            code_drifted=False,
            audit_passes=3,
            audit_dry_rounds=1,
            bundle_status=bundle_status,
            audit_stage=audit_stage,
        ) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["coverage"]["evidence_status"] == "unknown-legacy"
        assert payload["coverage"]["budget_limited"] is None

    def test_halted_iterate_persists_halt_section_and_returns_rc2(
        self, tmp_repo, capsys
    ) -> None:
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        args = SimpleNamespace(
            name="1-sectioned",
            json=False,
            fail_on_findings=False,
            commit=False,
        )
        outcome = _IterateOutcome(
            halt_reason="plan failed to parse before apply_finding",
            early_exit_code=2,
            stop_reason="halted: parse failure",
            audit_recs=[],
            iterations=1,
        )
        bundle_status, audit_stage = _hoisted_bundle(plan, path, tmp_repo.root)
        rc = finalize_completeness_run(
            plan,
            path,
            ctx,
            args,
            budget=IterativeBudget(enabled=True),
            outcome=outcome,
            reused_audit_recs=None,
            code_drifted=False,
            audit_passes=1,
            audit_dry_rounds=1,
            bundle_status=bundle_status,
            audit_stage=audit_stage,
        )
        assert rc == 2
        reports = list(plan_reports_dir(path).glob("*-completeness.md"))
        assert len(reports) == 1
        text = reports[0].read_text(encoding="utf-8")
        assert "## Halt" in text
        assert "plan failed to parse before apply_finding" in text

    def test_json_includes_halt_fields_and_returns_rc2(
        self, tmp_repo, capsys
    ) -> None:
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        args = SimpleNamespace(
            name="1-sectioned",
            json=True,
            fail_on_findings=True,
            commit=False,
        )
        outcome = _IterateOutcome(
            halt_reason="plan failed to parse before apply_finding",
            early_exit_code=2,
            audit_recs=[],
        )
        bundle_status, audit_stage = _hoisted_bundle(plan, path, tmp_repo.root)
        rc = finalize_completeness_run(
            plan,
            path,
            ctx,
            args,
            budget=IterativeBudget(enabled=True),
            outcome=outcome,
            reused_audit_recs=None,
            code_drifted=False,
            audit_passes=1,
            audit_dry_rounds=1,
            bundle_status=bundle_status,
            audit_stage=audit_stage,
        )
        assert rc == 2
        data = json.loads(capsys.readouterr().out)
        assert data["halt_reason"] == "plan failed to parse before apply_finding"
        assert data["early_exit_code"] == 2

    def test_finalize_fail_on_findings_incomplete_exits_one(
        self, tmp_repo, monkeypatch,
    ) -> None:
        plan, path = _write_and_parse(
            tmp_repo, _INTENT_BEARING_STEPS, intent=_PLAN_INTENT,
        )
        monkeypatch.setattr(
            "plan_tool.cli.completeness_cmd._sample_conceptual_audit",
            lambda *a, **k: [],
        )
        bundle_status, audit_stage = _hoisted_bundle(plan, path, tmp_repo.root)
        coverage = {
            "budget_limited": True,
            "passes_used": 1,
            "cap": 3,
            "conforming_pass_count": 0,
            "failed_or_malformed_pass_count": 1,
        }
        outcome = _IterateOutcome(
            audit_recs=[],
            audit_incomplete=True,
            budget=coverage,
        )
        rc = finalize_completeness_run(
            plan,
            path,
            SimpleNamespace(repo_root=tmp_repo.root),
            SimpleNamespace(
                name="1-sectioned", json=False, fail_on_findings=True, commit=False,
            ),
            budget=IterativeBudget(enabled=False),
            outcome=outcome,
            reused_audit_recs=None,
            code_drifted=False,
            audit_passes=1,
            audit_dry_rounds=1,
            bundle_status=bundle_status,
            audit_stage=audit_stage,
        )
        assert rc == 1

    def test_finalize_clean_requires_eligible_stop_reason(
        self, tmp_repo, monkeypatch,
    ) -> None:
        plan, path = _write_and_parse(
            tmp_repo, _INTENT_BEARING_STEPS, intent=_PLAN_INTENT,
        )
        qualifying = _qualifying_producer_coverage()

        def fresh_audit(*_args, budget_report, **_kwargs):
            budget_report.update(qualifying)
            return []

        monkeypatch.setattr(
            "plan_tool.cli.completeness_cmd._sample_conceptual_audit",
            fresh_audit,
        )
        bundle_status, audit_stage = _hoisted_bundle(plan, path, tmp_repo.root)
        args = SimpleNamespace(
            name="1-sectioned", json=False, fail_on_findings=True, commit=False,
        )
        blocked = finalize_completeness_run(
            plan,
            path,
            SimpleNamespace(repo_root=tmp_repo.root),
            args,
            budget=IterativeBudget(enabled=True),
            outcome=_IterateOutcome(
                audit_recs=[],
                audit_incomplete=False,
                stop_reason="terminal_hand_apply",
                budget=qualifying,
            ),
            reused_audit_recs=None,
            code_drifted=False,
            audit_passes=1,
            audit_dry_rounds=1,
            bundle_status=bundle_status,
            audit_stage=audit_stage,
        )
        assert blocked == 1
        clean = finalize_completeness_run(
            plan,
            path,
            SimpleNamespace(repo_root=tmp_repo.root),
            args,
            budget=IterativeBudget(enabled=False),
            outcome=_IterateOutcome(),
            reused_audit_recs=None,
            code_drifted=False,
            audit_passes=1,
            audit_dry_rounds=1,
            bundle_status=bundle_status,
            audit_stage=audit_stage,
        )
        assert clean == 0

    def test_finalize_blocks_on_genuine_non_eligible_stop_reason(
        self, tmp_repo, monkeypatch,
    ) -> None:
        """Companion to the ``terminal_hand_apply`` case above: a stop
        reason ``should_continue`` actually emits for a run that hit its
        iteration cap without converging (``"max_iterations"``) must also
        block ``--fail-on-findings`` clean, not just the one value the
        other test happens to exercise -- a membership check that widened
        to allow anything but ``terminal_hand_apply`` would pass that test
        while silently reporting an unconverged capped run as clean."""
        plan, path = _write_and_parse(
            tmp_repo, _INTENT_BEARING_STEPS, intent=_PLAN_INTENT,
        )
        qualifying = _qualifying_producer_coverage()

        def fresh_audit(*_args, budget_report, **_kwargs):
            budget_report.update(qualifying)
            return []

        monkeypatch.setattr(
            "plan_tool.cli.completeness_cmd._sample_conceptual_audit",
            fresh_audit,
        )
        bundle_status, audit_stage = _hoisted_bundle(plan, path, tmp_repo.root)
        args = SimpleNamespace(
            name="1-sectioned", json=False, fail_on_findings=True, commit=False,
        )
        rc = finalize_completeness_run(
            plan,
            path,
            SimpleNamespace(repo_root=tmp_repo.root),
            args,
            budget=IterativeBudget(enabled=True),
            outcome=_IterateOutcome(
                audit_recs=[],
                audit_incomplete=False,
                stop_reason="max_iterations",
                budget=qualifying,
            ),
            reused_audit_recs=None,
            code_drifted=False,
            audit_passes=1,
            audit_dry_rounds=1,
            bundle_status=bundle_status,
            audit_stage=audit_stage,
        )
        assert rc == 1

    def test_bare_deferred_medium_completeness_clean_when_sample_qualifies(
        self, tmp_repo, monkeypatch, capsys,
    ) -> None:
        from plan_tool.review import DetailBundleStatus

        plan, path = _write_and_parse(
            tmp_repo, _INTENT_BEARING_STEPS, intent=_PLAN_INTENT,
        )
        medium_completeness = _rec("medium", source="plan-completeness")
        qualifying = _qualifying_producer_coverage()
        bare_status = DetailBundleStatus(
            total=0, detailed_step_ids=(), bare_step_ids=(),
        )
        monkeypatch.setattr(
            "plan_tool.review.audit_detail_bundle_status",
            lambda *a, **k: bare_status,
        )
        bundle_status, audit_stage = _hoisted_bundle(plan, path, tmp_repo.root)
        assert audit_stage == STAGE_BARE
        args = SimpleNamespace(
            name="1-sectioned", json=True, fail_on_findings=True, commit=False,
        )
        outcome = _IterateOutcome(
            audit_recs=[medium_completeness],
            conceptual_bar_blocking_ids=(),
            audit_incomplete=False,
            stop_reason="converged",
            budget=qualifying,
        )
        rc = finalize_completeness_run(
            plan,
            path,
            SimpleNamespace(repo_root=tmp_repo.root),
            args,
            budget=IterativeBudget(enabled=True),
            outcome=outcome,
            reused_audit_recs=None,
            code_drifted=False,
            audit_passes=1,
            audit_dry_rounds=1,
            bundle_status=bundle_status,
            audit_stage=audit_stage,
        )
        data = json.loads(capsys.readouterr().out)
        assert data["has_blocking_findings"] is False
        assert data["stage"] == "bare"
        assert rc == 0


class TestIterateReuseCoverage:
    def test_iterate_reuse_replays_low_yield_coverage_without_audit(
        self, tmp_repo, monkeypatch, capsys
    ) -> None:
        from plan_tool import review as review_module
        import plan_tool.cli.completeness_phases as completeness_phases
        from plan_tool.cli.app import build_parser
        from plan_tool.cli.context import _load_context

        plan_path = tmp_repo.add_plan("1-demo", title="Demo")
        tmp_repo.write_manifest()
        coverage = _observed_audit_coverage(
            budget_limited=False,
            passes_used=2,
            cap=3,
            confirmation_kind="confirmed-low-yield",
        )
        expected_checkpoint_coverage = {
            key: value for key, value in coverage.items()
            if key != "evidence_status"
        }
        checkpoint_budgets: list[dict] = []

        monkeypatch.setattr(
            review_module, "collect_deterministic_findings", lambda *_a, **_kw: []
        )
        monkeypatch.setattr(
            review_module, "collect_self_consistency_findings", lambda *_a, **_kw: []
        )
        monkeypatch.setattr(
            review_module,
            "audit_plan_until_stable",
            lambda *_a, **_kw: (_ for _ in ()).throw(
                AssertionError("iterate reuse must skip the up-front audit")
            ),
        )
        monkeypatch.setattr(
            completeness_phases,
            "write_pre_apply_audit_checkpoint",
            lambda *_a, **kwargs: checkpoint_budgets.append(kwargs["budget"]),
        )
        args = build_parser().parse_args(
            tmp_repo.argv(
                "completeness-audit", "demo", "--iterate", "--yes",
                "--max-iterations", "1",
            )
        )
        ctx = _load_context(args)
        plan = parse_plan(plan_path)
        bundle_status, audit_stage = _hoisted_bundle(plan, plan_path, tmp_repo.root)
        outcome = _run_iterate_convergence_loop(
            plan,
            plan_path,
            ctx,
            args,
            IterativeBudget(enabled=True, max_iterations=1),
            bundle_status=bundle_status,
            audit_stage=audit_stage,
            reused_audit_recs=[],
            reused_audit_coverage=coverage,
        )

        assert checkpoint_budgets == [expected_checkpoint_coverage]
        assert outcome.budget == expected_checkpoint_coverage

        assert finalize_completeness_run(
            plan,
            plan_path,
            ctx,
            args,
            budget=IterativeBudget(enabled=True),
            outcome=outcome,
            reused_audit_recs=[],
            reused_audit_coverage=coverage,
            code_drifted=False,
            audit_passes=3,
            audit_dry_rounds=1,
            bundle_status=bundle_status,
            audit_stage=audit_stage,
        ) == 0
        reports = list(plan_reports_dir(plan_path).glob("*-completeness.md"))
        assert len(reports) == 1
        assert "Converged (low-yield)" in reports[0].read_text(encoding="utf-8")

        capsys.readouterr()
        args.json = True
        assert finalize_completeness_run(
            plan,
            plan_path,
            ctx,
            args,
            budget=IterativeBudget(enabled=True),
            outcome=outcome,
            reused_audit_recs=[],
            reused_audit_coverage=coverage,
            code_drifted=False,
            audit_passes=3,
            audit_dry_rounds=1,
            bundle_status=bundle_status,
            audit_stage=audit_stage,
        ) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["coverage"] == coverage

    def test_iterate_plan_quota_keeps_only_recovery_checkpoint(
        self, tmp_repo, monkeypatch
    ) -> None:
        from plan_tool import review as review_module
        from plan_tool.cli.app import build_parser
        from plan_tool.cli.completeness_phases import (
            _coverage_input_from_reusable_audit,
        )
        from plan_tool.cli.context import _load_context
        from plan_tool.completeness_report import plan_reports_dir

        plan_path = tmp_repo.add_plan("1-demo", title="Demo")
        tmp_repo.write_manifest()
        coverage = {
            "budget_limited": False,
            "passes_used": 1,
            "cap": 3,
            "recommendation_kind": None,
            "recommended_passes": None,
            "recommendation_advice": None,
            "confirmation_kind": None,
            "conforming_pass_count": 0,
            "failed_or_malformed_pass_count": 1,
            "early_stop_reason": "plan-quota",
        }

        assert _coverage_input_from_reusable_audit(
            {"evidence_status": "observed", **coverage}
        ) == coverage

        monkeypatch.setattr(
            review_module, "collect_deterministic_findings", lambda *_a, **_kw: []
        )
        monkeypatch.setattr(
            review_module,
            "collect_self_consistency_findings",
            lambda *_a, **_kw: [],
        )

        def quota_audit(*_args, budget_report=None, **_kwargs):
            assert budget_report is not None
            budget_report.update(coverage)
            return []

        monkeypatch.setattr(
            review_module, "audit_plan_until_stable", quota_audit
        )
        args = build_parser().parse_args(
            tmp_repo.argv(
                "completeness-audit", "demo", "--iterate", "--yes",
                "--max-iterations", "1",
            )
        )
        ctx = _load_context(args)
        plan = parse_plan(plan_path)
        bundle_status, audit_stage = _hoisted_bundle(plan, plan_path, tmp_repo.root)
        outcome = _run_iterate_convergence_loop(
            plan,
            plan_path,
            ctx,
            args,
            IterativeBudget(enabled=True, max_iterations=1),
            bundle_status=bundle_status,
            audit_stage=audit_stage,
        )

        assert outcome.audit_incomplete is True
        assert outcome.budget == coverage
        assert finalize_completeness_run(
            plan,
            plan_path,
            ctx,
            args,
            budget=IterativeBudget(enabled=True),
            outcome=outcome,
            reused_audit_recs=None,
            code_drifted=False,
            audit_passes=3,
            audit_dry_rounds=1,
            bundle_status=bundle_status,
            audit_stage=audit_stage,
        ) == 0

        sidecars = list(plan_reports_dir(plan_path).glob("*-completeness.json"))
        assert len(sidecars) == 1
        checkpoint = load_review(sidecars[0])
        assert checkpoint.is_pre_apply_checkpoint is True


class TestFinalizeTailRunLogging:
    """The finalize tail's purity calls must reach the run log.

    Regression (BUG_BACKLOG, 2026-07-28): ``cmd_completeness`` closed the
    iterate loop's ``RunLogWriter`` in a ``finally`` that ran *before*
    ``finalize_completeness_run``. The tail then spent minutes of claude on
    the per-step purity pass with ``run_end`` already logged and
    ``in-flight.json`` deleted — every persisted signal said the run was
    finished. Extending the log's lifetime is only half the fix: the
    ``claude_call_end`` events only land while a sink is installed, so the
    tail must install one around the purity pass.
    """

    def _args(self):
        return SimpleNamespace(
            name="1-sectioned",
            json=False,
            fail_on_findings=False,
            commit=False,
        )

    def _fake_logger(self, calls):
        return SimpleNamespace(
            install_call_end_sink=lambda phase, attempt: calls.append(
                ("install", phase, attempt)
            ),
            uninstall_call_end_sink=lambda: calls.append(("uninstall",)),
        )

    def test_sink_is_installed_around_the_purity_pass(
        self, tmp_repo, monkeypatch, capsys
    ) -> None:
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        calls: list[tuple] = []
        sink_state: list[list[tuple]] = []

        real_checks = _run_deterministic_checks

        def _spy(*a, **kw):
            # Snapshot the sink state *during* the pass: an install must
            # already have happened and not yet been undone.
            sink_state.append(list(calls))
            return real_checks(*a, **kw)

        monkeypatch.setattr(
            "plan_tool.cli.completeness_cmd._run_deterministic_checks", _spy
        )
        bundle_status, audit_stage = _hoisted_bundle(plan, path, tmp_repo.root)
        finalize_completeness_run(
            plan, path, SimpleNamespace(repo_root=tmp_repo.root), self._args(),
            budget=IterativeBudget(enabled=True),
            outcome=_IterateOutcome(audit_recs=[]),
            reused_audit_recs=None,
            code_drifted=False,
            audit_passes=1,
            audit_dry_rounds=1,
            run_logger=self._fake_logger(calls),
            bundle_status=bundle_status,
            audit_stage=audit_stage,
        )
        assert sink_state and sink_state[0] == [("install", "purity_scan", 1)]
        assert calls == [("install", "purity_scan", 1), ("uninstall",)]

    def test_sink_is_uninstalled_when_the_pass_raises(
        self, tmp_repo, monkeypatch, capsys
    ) -> None:
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        calls: list[tuple] = []

        def _boom(*a, **kw):
            raise RuntimeError("purity exploded")

        monkeypatch.setattr(
            "plan_tool.cli.completeness_cmd._run_deterministic_checks", _boom
        )
        bundle_status, audit_stage = _hoisted_bundle(plan, path, tmp_repo.root)
        with pytest.raises(RuntimeError, match="purity exploded"):
            finalize_completeness_run(
                plan, path, SimpleNamespace(repo_root=tmp_repo.root), self._args(),
                budget=IterativeBudget(enabled=True),
                outcome=_IterateOutcome(audit_recs=[]),
                reused_audit_recs=None,
                code_drifted=False,
                audit_passes=1,
                audit_dry_rounds=1,
                run_logger=self._fake_logger(calls),
                bundle_status=bundle_status,
                audit_stage=audit_stage,
            )
        # The sink must not leak onto whatever runs next.
        assert calls == [("install", "purity_scan", 1), ("uninstall",)]

    def test_no_run_logger_keeps_previous_behavior(
        self, tmp_repo, capsys
    ) -> None:
        """``run_logger`` defaults to None for callers that own no log."""
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        bundle_status, audit_stage = _hoisted_bundle(plan, path, tmp_repo.root)
        rc = finalize_completeness_run(
            plan, path, SimpleNamespace(repo_root=tmp_repo.root), self._args(),
            budget=IterativeBudget(enabled=True),
            outcome=_IterateOutcome(audit_recs=[]),
            reused_audit_recs=None,
            code_drifted=False,
            audit_passes=1,
            audit_dry_rounds=1,
            bundle_status=bundle_status,
            audit_stage=audit_stage,
        )
        assert rc == 0
        assert len(list(plan_reports_dir(path).glob("*-completeness.md"))) == 1


class TestParseFailureHelpers:
    def test_introduced_parse_failure_detects_synthetic_id(self) -> None:
        from plan_tool.launcher import (
            POST_EDIT_PARSE_FAILURE_ID,
            introduced_parse_failure,
        )
        from plan_tool.review import Recommendation as _Rec

        rec = _Rec(
            id=POST_EDIT_PARSE_FAILURE_ID,
            source="apply-validation",
            severity="critical",
            step_id=1,
            title="post-edit plan failed to parse",
            body="broken yaml",
            suggested_action=None,
        )
        assert introduced_parse_failure((rec,))
        assert not introduced_parse_failure(())

    def test_revert_apply_if_parse_broken_restores_snapshot(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.launcher import (
            ApplyFindingResult,
            POST_EDIT_PARSE_FAILURE_ID,
            revert_apply_if_parse_broken,
        )
        from plan_tool.review import Recommendation as _Rec

        plan_path = tmp_path / "plan.md"
        plan_path.write_text("before\n", encoding="utf-8")
        plan_path.write_text("after\n", encoding="utf-8")
        snapshot = {plan_path: "before\n"}
        result = ApplyFindingResult(
            step_id=1,
            exit_code=0,
            verdict="APPLIED",
            summary="broke yaml",
            diff_text="",
            pre_snapshot=snapshot,
            stdout="",
            introduced_findings=(
                _Rec(
                    id=POST_EDIT_PARSE_FAILURE_ID,
                    source="apply-validation",
                    severity="critical",
                    step_id=1,
                    title="post-edit plan failed to parse",
                    body="broken yaml",
                    suggested_action=None,
                ),
            ),
        )
        assert revert_apply_if_parse_broken(result) is True
        assert plan_path.read_text(encoding="utf-8") == "before\n"
        result_no_failure = ApplyFindingResult(
            step_id=1,
            exit_code=0,
            verdict="APPLIED",
            summary="ok",
            diff_text="",
            pre_snapshot=snapshot,
            stdout="",
            introduced_findings=(),
        )
        assert revert_apply_if_parse_broken(result_no_failure) is False


def _carried_by_title(carried, title: str):
    """Find the single CarriedFinding whose title matches, or fail."""
    matches = [c for c in carried if c.title == title]
    assert len(matches) == 1, f"expected one {title!r} in {carried!r}"
    return matches[0]


@pytest.mark.integration
class TestIterateApplyTelemetryForwarding:
    def _run_loop(
        self,
        tmp_repo,
        monkeypatch,
        *,
        fingerprint_fn,
        apply_calls: list[dict],
        apply_result=None,
        run_logger=None,
    ):
        from plan_tool import launcher as launcher_module
        from plan_tool import review as review_module
        import plan_tool.cli.completeness_phases as completeness_phases
        from plan_tool.cli.app import build_parser
        from plan_tool.cli.context import _load_context
        import plan_tool.review_persistence as persistence

        plan_path = tmp_repo.add_plan("1-demo", title="Demo")
        tmp_repo.write_manifest()
        findings = [
            Recommendation(
                id="det-a", source="body-completeness", severity="medium",
                step_id=None, title="gap A", body="fill A", anchor="overview",
            ),
            Recommendation(
                id="det-b", source="body-completeness", severity="medium",
                step_id=None, title="gap B", body="fill B", anchor=None,
            ),
        ]
        monkeypatch.setattr(
            review_module,
            "collect_deterministic_findings",
            lambda *a, **kw: findings,
        )
        monkeypatch.setattr(
            review_module,
            "collect_self_consistency_findings",
            lambda *a, **kw: [],
        )
        monkeypatch.setattr(
            persistence, "compute_plan_fingerprint", fingerprint_fn
        )
        monkeypatch.setattr(
            completeness_phases,
            "write_pre_apply_audit_checkpoint",
            lambda *a, **kw: None,
        )

        def fake_apply(*args, **kwargs):
            apply_calls.append(kwargs)
            return apply_result or SimpleNamespace(
                exit_code=0, verdict="APPLIED", summary="applied",
                stdout="", diff_text="", pre_snapshot={},
                introduced_findings=(), resolved_findings=(),
            )

        monkeypatch.setattr(launcher_module, "apply_finding", fake_apply)
        args = build_parser().parse_args(
            tmp_repo.argv(
                "completeness-audit", "demo", "--iterate", "--yes",
                "--no-triage", "--max-iterations", "1",
            )
        )
        ctx = _load_context(args)
        plan = parse_plan(plan_path)
        bundle_status, audit_stage = _hoisted_bundle(plan, plan_path, tmp_repo.root)
        outcome = _run_iterate_convergence_loop(
            plan,
            plan_path,
            ctx,
            args,
            IterativeBudget(enabled=True, max_iterations=1),
            reused_audit_recs=[],
            bundle_status=bundle_status,
            audit_stage=audit_stage,
            run_logger=run_logger,
        )
        return plan_path, outcome

    def test_iterate_apply_loop_hoists_and_forwards_telemetry_keys(
        self, tmp_repo, monkeypatch
    ) -> None:
        fingerprint_calls: list[Path] = []
        apply_calls: list[dict] = []
        plan_path, outcome = self._run_loop(
            tmp_repo,
            monkeypatch,
            fingerprint_fn=lambda path: (
                fingerprint_calls.append(path) or "shared-iterate-fp"
            ),
            apply_calls=apply_calls,
        )

        assert outcome.early_exit_code is None
        assert [call["anchor"] for call in apply_calls] == ["overview", ""]
        assert {call["plan_fingerprint"] for call in apply_calls} == {
            "shared-iterate-fp"
        }
        assert all("record_verdict" not in call for call in apply_calls)
        assert fingerprint_calls == [plan_path]

    def test_iterate_apply_logs_reverted_final_disposition(
        self, tmp_repo, monkeypatch
    ) -> None:
        from plan_tool.launcher import POST_EDIT_PARSE_FAILURE_ID

        class _Logger:
            def __init__(self) -> None:
                self.ends: list[tuple[str, int, str, dict]] = []

            def phase_start(self, *_args, **_kwargs) -> None:
                pass

            def phase_end(self, phase, duration, outcome, **extra) -> None:
                self.ends.append((phase, duration, outcome, extra))

        logger = _Logger()
        apply_calls: list[dict] = []
        _path, outcome = self._run_loop(
            tmp_repo,
            monkeypatch,
            fingerprint_fn=lambda _path: "shared-iterate-fp",
            apply_calls=apply_calls,
            apply_result=SimpleNamespace(
                exit_code=0,
                verdict="APPLIED",
                summary="broke yaml",
                stdout="",
                diff_text="",
                pre_snapshot={},
                introduced_findings=(
                    SimpleNamespace(id=POST_EDIT_PARSE_FAILURE_ID),
                ),
                resolved_findings=(),
            ),
            run_logger=logger,
        )

        assert outcome.early_exit_code == 2
        assert logger.ends[0][0] == "apply_finding_dispatch"
        assert logger.ends[0][2] == "reverted"
        assert logger.ends[0][3]["verdict"] == "REVERTED"

    def test_iterate_apply_loop_fingerprint_failure_is_best_effort(
        self, tmp_repo, monkeypatch
    ) -> None:
        def fail_fingerprint(_path):
            raise OSError("fingerprint unavailable")

        apply_calls: list[dict] = []
        _plan_path, outcome = self._run_loop(
            tmp_repo,
            monkeypatch,
            fingerprint_fn=fail_fingerprint,
            apply_calls=apply_calls,
        )

        assert outcome.early_exit_code is None
        assert [(call["anchor"], call["plan_fingerprint"]) for call in apply_calls] == [
            ("overview", ""),
            ("", ""),
        ]


@pytest.mark.integration
class TestCarriedFindingsWiring:
    """End-to-end: the iterate loop and the saved-audit replay walk both hand
    ``apply_finding`` a carried set reflecting earlier applies this run."""

    def _correctness_rec(self, slug: str, title: str):
        return Recommendation(
            id=f"corr-{slug}", source="plan-correctness", severity="high",
            step_id=1, title=title, body=f"{slug} body", anchor=slug,
        )

    def test_high_impact_advisory_audit_finding_is_reported_but_not_in_completeness_open_set(
        self, tmp_repo, monkeypatch
    ) -> None:
        """#85: the iterate loop applies only its deterministic findings — it
        does NOT auto-apply plan-correctness (or plan-completeness). Both
        conceptual sources are persisted to the sidecar unapplied for
        ``completeness-apply`` to walk."""
        from plan_tool import launcher as launcher_module
        from plan_tool import review as review_module
        from plan_tool.cli import main
        from plan_tool.review_persistence import (
            list_saved_reviews,
            load_review,
        )

        plan_path = tmp_repo.add_plan("1-demo", title="Demo")
        tmp_repo.write_manifest()

        a = self._correctness_rec("alpha", "alpha gap")
        b = self._correctness_rec("beta", "beta gap")
        comp = Recommendation(
            id="comp-x", source="plan-completeness", severity="nit",
            step_id=1, title="missing thing", body="comp body", anchor="comp-x",
            impact="high", complexity="low",
        )
        monkeypatch.setattr(
            review_module, "audit_plan_until_stable",
            lambda *args, **kw: [a, b, comp],
        )
        monkeypatch.setattr(
            review_module, "collect_deterministic_findings",
            lambda *args, **kw: [],
        )

        captured: list = []

        def fake_apply(plan_path, **kwargs):
            captured.append(kwargs["finding_body"])
            return SimpleNamespace(
                exit_code=0, verdict="APPLIED",
                summary="s", stdout="", diff_text="", pre_snapshot={},
                introduced_findings=(), resolved_findings=(),
            )

        monkeypatch.setattr(launcher_module, "apply_finding", fake_apply)

        rc = main(tmp_repo.argv(
            "completeness-audit", "demo", "--iterate", "--yes",
            "--max-iterations", "1",
        ))
        assert rc in (0, 1)
        # No conceptual finding was dispatched to apply_finding by the loop.
        assert captured == []
        # Both conceptual sources persisted to the sidecar, unapplied.
        saved_path = next(
            p
            for p in list_saved_reviews(
                "demo", tmp_repo.root, plan_path=plan_path
            )
            if p.name.endswith("-completeness.json")
        )
        saved = load_review(saved_path)
        sources = {r.id: r.source for r in saved.recommendations}
        assert sources.get("corr-alpha") == "plan-correctness"
        assert sources.get("corr-beta") == "plan-correctness"
        assert sources.get("comp-x") == "plan-completeness"
        assert next(r for r in saved.recommendations if r.id == "comp-x").impact == "high"

    def _save_completeness(self, tmp_repo, plan_path, *, recs, annotations):
        from plan_tool.review_persistence import save_review

        return save_review(
            plan_slug="demo",
            plan_path=plan_path.relative_to(tmp_repo.root).as_posix(),
            repo_root=tmp_repo.root,
            report_md="# report\n",
            recommendations=recs,
            annotations=annotations,
            kind="completeness",
        )

    def _gap(self, slug: str, title: str):
        return Recommendation(
            id=f"gap-{slug}", source="plan-completeness", severity="medium",
            step_id=1, title=title, body=f"{slug} body", anchor=slug,
        )

    def _contract(self, slug: str, title: str, *, body: str = "contract body"):
        return Recommendation(
            id=f"contract-{slug}",
            source="data-contract",
            severity="medium",
            step_id=None,
            title=title,
            body=body,
            anchor=slug,
            suggested_action="Update DATA_CONTRACT.md",
        )

    def _write_contract_payloads(self, saved_path, payloads: dict) -> None:
        saved_path.with_name(f"{saved_path.stem}-data-contract.json").write_text(
            json.dumps(
                {
                    "kind": "data-contract",
                    "review_id": saved_path.stem,
                    "payloads": payloads,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def _drive_apply_walk(self, tmp_repo, monkeypatch, *, apply_stub, extra):
        """Drive ``completeness-apply`` with the interactive walk simulated so
        the action dispatcher (and apply stub) actually runs."""
        import sys

        import plan_tool.cli.completeness_phases as phases
        from plan_tool import launcher as launcher_module
        from plan_tool.cli import main
        from plan_tool.review_walk import WalkResult

        # Pretend an interactive terminal so the walk isn't skipped.
        monkeypatch.setattr(
            sys, "stdin", SimpleNamespace(isatty=lambda: True)
        )
        monkeypatch.setattr(launcher_module, "apply_finding", apply_stub)

        def fake_walk(saved, *, action_fn, state, **kw):
            for rec in saved.recommendations:
                state.apply_skip = False
                action_fn(rec)
            return WalkResult(answered=len(saved.recommendations),
                              quit_early=False)

        monkeypatch.setattr(phases, "walk_recommendations", fake_walk)
        return main(tmp_repo.argv("completeness-apply", "demo", *extra))

    def test_completeness_apply_builds_carried_from_full_saved_set(
        self, tmp_repo, monkeypatch
    ) -> None:
        from plan_tool.review_persistence import Annotation

        plan_path = tmp_repo.add_plan("1-demo", title="Demo")
        _attach_minimal_detail(tmp_repo, plan_path)
        tmp_repo.write_manifest()
        g1 = self._gap("gap-one", "first gap")
        g2 = self._gap("gap-two", "second gap")
        # A non-completeness finding the verb won't walk, but whose saved
        # annotation must still seed the carried context.
        x1 = Recommendation(
            id="claude-x1", source="claude", severity="high", step_id=1,
            title="legacy finding", body="x1 body", anchor="legacy",
        )
        self._save_completeness(
            tmp_repo, plan_path, recs=[g1, g2, x1],
            annotations={
                "claude-x1": Annotation(status="applied"),
                g2.id: Annotation(status="skip"),
            },
        )

        captured: list = []

        def apply_stub(plan_path, **kwargs):
            captured.append(kwargs["carried_findings"])
            return SimpleNamespace(
                exit_code=0, verdict="APPLIED", diff_text="", summary="",
                stdout="", pre_snapshot={}, introduced_findings=(),
                resolved_findings=(),
            )

        # --anchor narrows the WALK to gap-one, but the carried context must
        # still cover the full saved set.
        rc = self._drive_apply_walk(
            tmp_repo, monkeypatch, apply_stub=apply_stub,
            extra=["--anchor", "gap-one"],
        )
        assert rc == 0
        assert len(captured) == 1  # only the anchored gap is walked
        carried = captured[0]
        titles = {c.title for c in carried}
        assert titles == {"first gap", "second gap", "legacy finding"}
        assert _carried_by_title(
            carried, "legacy finding"
        ).resolution == CARRIED_RESOLUTION_APPLIED
        assert _carried_by_title(
            carried, "second gap"
        ).resolution == CARRIED_RESOLUTION_SKIPPED
        assert _carried_by_title(
            carried, "first gap"
        ).resolution == CARRIED_RESOLUTION_OPEN

    def test_completeness_apply_accumulates_replay_verdicts(
        self, tmp_repo, monkeypatch
    ) -> None:
        plan_path = tmp_repo.add_plan("1-demo", title="Demo")
        _attach_minimal_detail(tmp_repo, plan_path)
        tmp_repo.write_manifest()
        g1 = self._gap("gap-one", "first gap")
        g2 = self._gap("gap-two", "second gap")
        self._save_completeness(
            tmp_repo, plan_path, recs=[g1, g2], annotations={},
        )

        # first gap -> BLOCKED, second gap -> APPLIED.
        verdicts = {"gap-one body": "BLOCKED", "gap-two body": "APPLIED"}
        captured: list = []

        def apply_stub(plan_path, **kwargs):
            captured.append(kwargs["carried_findings"])
            return SimpleNamespace(
                exit_code=0,
                verdict=verdicts[kwargs["finding_body"].splitlines()[-1]],
                diff_text="", summary="declined", stdout="", pre_snapshot={},
                introduced_findings=(), resolved_findings=(),
            )

        rc = self._drive_apply_walk(
            tmp_repo, monkeypatch, apply_stub=apply_stub, extra=[],
        )
        assert rc == 0
        assert len(captured) == 2
        # The second apply's carried set reflects the first's fresh BLOCKED
        # verdict — not derivable from the (empty) saved annotations.
        second_carried = captured[1]
        assert _carried_by_title(
            second_carried, "first gap"
        ).resolution == CARRIED_RESOLUTION_BLOCKED

    def _corr(self, slug: str, title: str):
        return Recommendation(
            id=f"corr-{slug}", source="plan-correctness", severity="high",
            step_id=1, title=title, body=f"{slug} body", anchor=slug,
        )

    def test_apply_walks_both_sources_correctness_first(
        self, tmp_repo, monkeypatch
    ) -> None:
        """#85: the audit persists both conceptual sources unapplied; this
        verb walks BOTH — plan-correctness before plan-completeness —
        regardless of their saved order."""
        plan_path = tmp_repo.add_plan("1-demo", title="Demo")
        _attach_minimal_detail(tmp_repo, plan_path)
        tmp_repo.write_manifest()
        # Save with completeness BEFORE correctness to prove the sort flips it.
        comp = self._gap("comp-one", "missing thing")
        corr = self._corr("corr-one", "design gap")
        self._save_completeness(
            tmp_repo, plan_path, recs=[comp, corr], annotations={},
        )

        walked: list = []

        def apply_stub(plan_path, **kwargs):
            walked.append(kwargs["finding_body"])
            return SimpleNamespace(
                exit_code=0, verdict="APPLIED", diff_text="", summary="",
                stdout="", pre_snapshot={}, introduced_findings=(),
                resolved_findings=(),
            )

        rc = self._drive_apply_walk(
            tmp_repo, monkeypatch, apply_stub=apply_stub, extra=[],
        )
        assert rc == 0
        # Both conceptual sources walked, correctness first.
        assert [body.splitlines()[-1] for body in walked] == [
            "corr-one body", "comp-one body",
        ]
        assert all("confidence: limited" in body for body in walked)

    def test_apply_anchor_targets_correctness_source(
        self, tmp_repo, monkeypatch
    ) -> None:
        """--anchor resolves against a plan-correctness finding too, not just
        plan-completeness."""
        plan_path = tmp_repo.add_plan("1-demo", title="Demo")
        _attach_minimal_detail(tmp_repo, plan_path)
        tmp_repo.write_manifest()
        comp = self._gap("comp-one", "missing thing")
        corr = self._corr("corr-one", "design gap")
        self._save_completeness(
            tmp_repo, plan_path, recs=[comp, corr], annotations={},
        )

        walked: list = []

        def apply_stub(plan_path, **kwargs):
            walked.append(kwargs["finding_body"])
            return SimpleNamespace(
                exit_code=0, verdict="APPLIED", diff_text="", summary="",
                stdout="", pre_snapshot={}, introduced_findings=(),
                resolved_findings=(),
            )

        rc = self._drive_apply_walk(
            tmp_repo, monkeypatch, apply_stub=apply_stub,
            extra=["--anchor", "corr-one"],
        )
        assert rc == 0
        assert len(walked) == 1
        assert walked[0].endswith("corr-one body")
        assert "confidence: limited" in walked[0]

    def test_apply_redirects_data_contract_findings_from_saved_audit(
        self, tmp_repo, monkeypatch
    ) -> None:
        plan_path = tmp_repo.add_plan("1-demo", title="Demo")
        _attach_minimal_detail(tmp_repo, plan_path)
        tmp_repo.write_manifest()
        contract = self._contract("contract-one", "contract drift")
        saved_path = self._save_completeness(
            tmp_repo, plan_path, recs=[contract], annotations={},
        )
        self._write_contract_payloads(
            saved_path,
            {contract.id: {"target": "DATA_CONTRACT.md", "operation": "add"}},
        )

        messages: list[str] = []

        def apply_stub(*a, **k):  # pragma: no cover - must never be reached
            raise AssertionError("generic apply_finding must not run")

        def fake_walk(saved, *, action_fn, state, **kw):
            messages.append(action_fn(saved.recommendations[0]))
            return SimpleNamespace(answered=1, quit_early=False)

        import sys as _sys
        import plan_tool.cli.completeness_phases as phases
        from plan_tool import launcher as launcher_module
        from plan_tool.cli import main

        monkeypatch.setattr(_sys, "stdin", SimpleNamespace(isatty=lambda: True))
        monkeypatch.setattr(launcher_module, "apply_finding", apply_stub)
        monkeypatch.setattr(phases, "walk_recommendations", fake_walk)

        rc = main(tmp_repo.argv("completeness-apply", "demo"))
        assert rc == 0
        assert "data-contract-apply" in messages[0]

    def test_input_reference_findings_are_non_applyable_in_completeness_apply(
        self, tmp_repo, monkeypatch
    ) -> None:
        plan_path = tmp_repo.add_plan("1-demo", title="Demo")
        _attach_minimal_detail(tmp_repo, plan_path)
        tmp_repo.write_manifest()
        contract = self._contract(
            "input-ref", "stale ## Input reference", body="plan-detail body"
        )
        saved_path = self._save_completeness(
            tmp_repo, plan_path, recs=[contract], annotations={},
        )
        self._write_contract_payloads(
            saved_path,
            {contract.id: {"target": "plan-detail", "operation": "add"}},
        )

        messages: list[str] = []

        def fake_walk(saved, *, action_fn, state, **kw):
            messages.append(action_fn(saved.recommendations[0]))
            return SimpleNamespace(answered=1, quit_early=False)

        import sys as _sys
        import plan_tool.cli.completeness_phases as phases
        from plan_tool.cli import main

        monkeypatch.setattr(_sys, "stdin", SimpleNamespace(isatty=lambda: True))
        monkeypatch.setattr(phases, "walk_recommendations", fake_walk)

        rc = main(tmp_repo.argv("completeness-apply", "demo"))
        assert rc == 0
        assert "not applyable by completeness-apply" in messages[0]
        assert "data-contract-apply" not in messages[0]

    def test_apply_orders_data_contract_after_conceptual_sources(
        self, tmp_repo, monkeypatch
    ) -> None:
        plan_path = tmp_repo.add_plan("1-demo", title="Demo")
        _attach_minimal_detail(tmp_repo, plan_path)
        tmp_repo.write_manifest()
        comp = self._gap("comp-one", "missing thing")
        corr = self._corr("corr-one", "design gap")
        contract = self._contract("contract-one", "contract drift")
        self._save_completeness(
            tmp_repo, plan_path, recs=[contract, comp, corr], annotations={},
        )

        seen: list[str] = []

        def fake_walk(saved, **kw):
            seen.extend(r.source for r in saved.recommendations)
            return SimpleNamespace(answered=0, quit_early=False)

        import sys as _sys
        import plan_tool.cli.completeness_phases as phases
        from plan_tool.cli import main

        monkeypatch.setattr(_sys, "stdin", SimpleNamespace(isatty=lambda: True))
        monkeypatch.setattr(phases, "walk_recommendations", fake_walk)

        rc = main(tmp_repo.argv("completeness-apply", "demo"))
        assert rc == 0
        assert seen == ["plan-correctness", "plan-completeness", "data-contract"]

    def test_apply_anchor_targets_data_contract_source(
        self, tmp_repo, monkeypatch
    ) -> None:
        plan_path = tmp_repo.add_plan("1-demo", title="Demo")
        _attach_minimal_detail(tmp_repo, plan_path)
        tmp_repo.write_manifest()
        comp = self._gap("comp-one", "missing thing")
        contract = self._contract("contract-one", "contract drift")
        self._save_completeness(
            tmp_repo, plan_path, recs=[comp, contract], annotations={},
        )

        seen: list[str] = []

        def fake_walk(saved, **kw):
            seen.extend(r.id for r in saved.recommendations)
            return SimpleNamespace(answered=0, quit_early=False)

        import sys as _sys
        import plan_tool.cli.completeness_phases as phases
        from plan_tool.cli import main

        monkeypatch.setattr(_sys, "stdin", SimpleNamespace(isatty=lambda: True))
        monkeypatch.setattr(phases, "walk_recommendations", fake_walk)

        rc = main(
            tmp_repo.argv("completeness-apply", "demo", "--anchor", "contract-one")
        )
        assert rc == 0
        assert seen == [contract.id]

    def test_data_contract_routing_intent_reaches_walker_and_action_builder(
        self, tmp_repo, monkeypatch
    ) -> None:
        plan_path = tmp_repo.add_plan("1-demo", title="Demo")
        _attach_minimal_detail(tmp_repo, plan_path)
        tmp_repo.write_manifest()
        contract = self._contract("contract-one", "contract drift")
        self._save_completeness(
            tmp_repo, plan_path, recs=[contract], annotations={},
        )

        build_sources: list[frozenset[str]] = []
        walk_sources: list[frozenset[str]] = []

        def fake_build(**kwargs):
            build_sources.append(kwargs["extra_apply_sources"])

            def action(rec):
                raise AssertionError("generic builder must not handle data-contract")

            return action

        def fake_walk(saved, *, action_fn, state, extra_apply_sources, **kw):
            walk_sources.append(extra_apply_sources)
            action_fn(saved.recommendations[0])
            return SimpleNamespace(answered=1, quit_early=False)

        import sys as _sys
        import plan_tool.cli.completeness_phases as phases
        from plan_tool.cli import main

        monkeypatch.setattr(_sys, "stdin", SimpleNamespace(isatty=lambda: True))
        monkeypatch.setattr(phases, "_build_review_action_fn", fake_build)
        monkeypatch.setattr(phases, "walk_recommendations", fake_walk)

        rc = main(tmp_repo.argv("completeness-apply", "demo"))
        assert rc == 0
        # Both seams share one opt-in set — now also carrying granularity-split
        # so the completeness-apply lane can route the MIXED-STEP split.
        _expected = frozenset(
            {"plan-correctness", "data-contract", "granularity-split"}
        )
        assert build_sources == [_expected]
        assert walk_sources == [_expected]

    def test_data_contract_carried_resolution_updates_after_apply(
        self, tmp_repo, monkeypatch
    ) -> None:
        plan_path = tmp_repo.add_plan("1-demo", title="Demo")
        _attach_minimal_detail(tmp_repo, plan_path)
        tmp_repo.write_manifest()
        contract = self._contract("contract-one", "contract drift")
        gap = self._gap("gap-one", "first gap")
        saved_path = self._save_completeness(
            tmp_repo, plan_path, recs=[gap, contract], annotations={},
        )
        self._write_contract_payloads(
            saved_path,
            {contract.id: {"target": "DATA_CONTRACT.md", "operation": "add"}},
        )

        import sys as _sys
        import plan_tool.cli.completeness_phases as phases
        from plan_tool.cli import main
        from plan_tool.review_persistence import (
            Annotation,
            load_review,
            update_annotation,
        )

        def fake_walk(saved, *, action_fn, state, **kw):
            contract_rec = next(
                r for r in saved.recommendations
                if r.source == "data-contract"
            )
            msg = action_fn(contract_rec)
            assert state.last_apply_verdict == "NOT-APPLICABLE"
            annotation = Annotation(status="skip", note=msg)
            update_annotation(saved.path, contract_rec.id, annotation)
            saved.annotations[contract_rec.id] = annotation
            return SimpleNamespace(answered=1, quit_early=False)

        monkeypatch.setattr(_sys, "stdin", SimpleNamespace(isatty=lambda: True))
        monkeypatch.setattr(phases, "walk_recommendations", fake_walk)

        rc = main(tmp_repo.argv("completeness-apply", "demo"))
        assert rc == 0
        saved = load_review(saved_path)
        assert saved.annotations[contract.id].status == "skip"


class TestCompletenessApplyParallel:
    """``--jobs N`` (N>1) non-interactive parallel apply path (#74/B2)."""

    def _save(self, tmp_repo, plan_path, recs, *, audit_shape_advisory=None):
        from plan_tool.review_persistence import save_review

        return save_review(
            plan_slug="demo",
            plan_path=plan_path.relative_to(tmp_repo.root).as_posix(),
            repo_root=tmp_repo.root, report_md="# r\n",
            recommendations=recs,
            annotations={},
            kind="completeness",
            audit_shape_advisory=audit_shape_advisory,
        )

    def _recs(self):
        return [
            Recommendation(id="corr-1", source="plan-correctness",
                           severity="high", step_id=1, title="t", body="b1",
                           anchor="corr-1"),
            Recommendation(id="comp-1", source="plan-completeness",
                           severity="medium", step_id=1, title="t", body="b2",
                           anchor="comp-1"),
        ]

    def _contract_rec(self):
        return Recommendation(
            id="contract-1", source="data-contract", severity="medium",
            step_id=None, title="contract", body="contract body",
            anchor="contract-1", suggested_action="Update DATA_CONTRACT.md",
        )

    def _setup(self, tmp_repo):
        plan_path = tmp_repo.add_plan("1-demo", title="Demo")
        _attach_minimal_detail(tmp_repo, plan_path)
        tmp_repo.write_manifest()
        return plan_path, self._save(tmp_repo, plan_path, self._recs())

    def test_dirty_tree_refused(self, tmp_repo, monkeypatch, capsys):
        import sys as _sys

        import plan_tool.cli.completeness_phases as phases
        from plan_tool.cli import main

        self._setup(tmp_repo)
        monkeypatch.setattr(phases, "working_tree_dirty", lambda root: True)
        monkeypatch.setattr(_sys, "stdin",
                            SimpleNamespace(isatty=lambda: True))
        rc = main(tmp_repo.argv("completeness-apply", "demo", "--jobs", "2",
                                "-y"))
        assert rc == 2
        assert "clean working tree" in capsys.readouterr().err

    def test_tty_without_yes_refused(self, tmp_repo, monkeypatch, capsys):
        import sys as _sys

        import plan_tool.cli.completeness_phases as phases
        from plan_tool.cli import main

        self._setup(tmp_repo)
        monkeypatch.setattr(phases, "working_tree_dirty", lambda root: False)
        monkeypatch.setattr(_sys, "stdin",
                            SimpleNamespace(isatty=lambda: True))
        rc = main(tmp_repo.argv("completeness-apply", "demo", "--jobs", "2"))
        assert rc == 2
        assert "-y" in capsys.readouterr().err

    def test_keyboard_interrupt_records_interrupted_run_end(
        self, tmp_repo, monkeypatch
    ):
        import json
        import sys as _sys

        import plan_tool.cli.completeness_apply_parallel as par
        import plan_tool.cli.completeness_phases as phases
        from plan_tool.cli import main

        self._setup(tmp_repo)
        monkeypatch.setattr(phases, "working_tree_dirty", lambda root: False)
        monkeypatch.setattr(_sys, "stdin", SimpleNamespace(isatty=lambda: True))
        monkeypatch.setattr(
            par,
            "run_parallel_apply",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(KeyboardInterrupt()),
        )

        with pytest.raises(SystemExit) as exc:
            main(tmp_repo.argv("completeness-apply", "demo", "--jobs", "2", "-y"))
        assert exc.value.code == 130

        log_path = next(
            (tmp_repo.root / ".plan-tool" / "runs" / "demo").glob("*.jsonl")
        )
        events = [
            json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()
        ]
        assert events[-1]["event"] == "run_end"
        assert events[-1]["rc"] == 130
        assert events[-1]["error"] == "interrupted"

    def test_single_anchor_degrades_to_serial(self, tmp_repo, monkeypatch,
                                              capsys):
        import sys as _sys

        from plan_tool.cli import main

        self._setup(tmp_repo)
        # Non-interactive stdin so the degraded serial walk reports + returns.
        monkeypatch.setattr(_sys, "stdin",
                            SimpleNamespace(isatty=lambda: False))
        rc = main(tmp_repo.argv("completeness-apply", "demo", "--jobs", "2",
                                "--anchor", "corr-1"))
        # The degrade decision happens before the TTY gate, so the stderr
        # line below is the assertion that carries this test's intent; the
        # serial walk then skips on non-interactive stdin and reports rc=2.
        assert rc == 2
        assert "nothing to parallelize" in capsys.readouterr().err

    def test_parallel_applies_and_persists_annotations(
        self, tmp_repo, monkeypatch, capsys
    ):
        import sys as _sys

        import plan_tool.cli.completeness_apply_parallel as par
        import plan_tool.cli.completeness_phases as phases
        from plan_tool.cli import main
        from plan_tool.review_persistence import load_review

        plan_path, saved_path = self._setup(tmp_repo)
        monkeypatch.setattr(phases, "working_tree_dirty", lambda root: False)
        monkeypatch.setattr(_sys, "stdin",
                            SimpleNamespace(isatty=lambda: True))

        recs = self._recs()

        def fake_run(walk_recs, **kwargs):
            # Mirror run_parallel_apply's contract: persist each finding's
            # disposition incrementally via the callback.
            persist = kwargs.get("persist")
            out = par.ReplayOutcome()
            out.applied.append((recs[0], "APPLIED"))     # corr-1
            if persist:
                persist(recs[0], "applied", "APPLIED")
            out.failed.append((recs[1], "reverted — parse"))  # comp-1
            if persist:
                persist(recs[1], "failed", "reverted — parse")
            out.conflicts = 1
            return out

        monkeypatch.setattr(par, "run_parallel_apply", fake_run)
        rc = main(tmp_repo.argv("completeness-apply", "demo", "--jobs", "3",
                                "-y"))
        assert rc == 0
        out = capsys.readouterr().out
        assert "1 applied, 1 failed" in out
        assert "re-run serially on conflict" in out
        saved = load_review(saved_path)
        assert saved.annotations["corr-1"].status == "applied"
        assert saved.annotations["comp-1"].status == "failed"

    def test_parallel_apply_presents_fresh_arm_advice_once_before_dispatch(
        self, tmp_repo, monkeypatch, capsys
    ):
        import sys as _sys

        from plan_tool.audit_shapes import AuditShapeAdvisory, AuditShapeFindingEvidence
        import plan_tool.cli.completeness_apply_parallel as par
        import plan_tool.cli.completeness_phases as phases
        from plan_tool.cli import main
        from plan_tool.review_persistence import AuditInputSnapshot

        plan_path = tmp_repo.add_plan("1-demo", title="Demo")
        _attach_minimal_detail(tmp_repo, plan_path)
        plan_path.write_text(
            plan_path.read_text(encoding="utf-8").replace(
                "  - id: 1\n"
                "    title: Only step\n"
                "    detail: plans/details/01-only-step.md\n",
                "  - id: 1\n"
                "    title: Focused first\n"
                "    detail: plans/details/01-only-step.md\n"
                "  - id: 2\n"
                "    title: Focused second\n"
                "    detail: plans/details/02-focused-second.md\n"
                "  - id: 3\n"
                "    title: Focused third\n"
                "    detail: plans/details/03-focused-third.md\n"
                "  - id: 4\n"
                "    title: Follow-up\n"
                "    detail: plans/details/04-follow-up.md\n"
                "  - id: 5\n"
                "    title: Later work\n"
                "    detail: plans/details/05-later-work.md\n",
            ),
            encoding="utf-8",
        )
        for step_id, slug in (
            (2, "focused-second"),
            (3, "focused-third"),
            (4, "follow-up"),
            (5, "later-work"),
        ):
            (tmp_repo.root / f"plans/details/{step_id:02d}-{slug}.md").write_text(
                f"# Step {step_id}\n\n## Summary\n\nDetail.\n",
                encoding="utf-8",
            )
        tmp_repo.write_manifest()
        snapshot = AuditInputSnapshot.capture(plan_path, tmp_repo.root)
        advisory = AuditShapeAdvisory(
            shape_id="arm-clustering",
            source_plan_fingerprint=snapshot.fingerprint,
            arm_step_ids=(1, 2, 3),
            material_finding_ids=("opaque-a", "opaque-b", "opaque-c"),
            arm_finding_ids=("opaque-a", "opaque-b", "opaque-c"),
            material_finding_evidence=(
                AuditShapeFindingEvidence("opaque-a", "corr", "plan-correctness"),
                AuditShapeFindingEvidence("opaque-b", "risk", "plan-completeness"),
                AuditShapeFindingEvidence("opaque-c", "edge", "plan-completeness"),
            ),
            material_finding_count=3,
            arm_finding_count=3,
            committed_step_count=5,
        )
        self._save(
            tmp_repo, plan_path, self._recs(), audit_shape_advisory=advisory
        )
        monkeypatch.setattr(phases, "working_tree_dirty", lambda root: False)
        monkeypatch.setattr(_sys, "stdin", SimpleNamespace(isatty=lambda: True))

        seen: list[str] = []

        def fake_run(walk_recs, **kwargs):
            kwargs["pre_apply_presentation"]()
            seen.extend(rec.id for rec in walk_recs)
            return par.ReplayOutcome()

        monkeypatch.setattr(par, "run_parallel_apply", fake_run)
        assert main(tmp_repo.argv("completeness-apply", "demo", "--jobs", "2", "-y")) == 0
        out = capsys.readouterr().out
        assert out.count("arm-clustering") == 1
        assert seen == ["corr-1", "comp-1"]

    def test_parallel_apply_excludes_data_contract_findings(
        self, tmp_repo, monkeypatch
    ):
        import sys as _sys

        import plan_tool.cli.completeness_apply_parallel as par
        import plan_tool.cli.completeness_phases as phases
        from plan_tool.cli import main

        plan_path = tmp_repo.add_plan("1-demo", title="Demo")
        _attach_minimal_detail(tmp_repo, plan_path)
        tmp_repo.write_manifest()
        recs = [self._contract_rec()] + self._recs()
        self._save(tmp_repo, plan_path, recs)
        monkeypatch.setattr(phases, "working_tree_dirty", lambda root: False)
        monkeypatch.setattr(_sys, "stdin",
                            SimpleNamespace(isatty=lambda: True))

        seen: list[str] = []

        def fake_run(walk_recs, **kwargs):
            seen.extend(r.source for r in walk_recs)
            return par.ReplayOutcome()

        monkeypatch.setattr(par, "run_parallel_apply", fake_run)
        rc = main(tmp_repo.argv("completeness-apply", "demo", "--jobs", "3",
                                "-y"))
        assert rc == 0
        assert seen == ["plan-correctness", "plan-completeness"]

    def test_parallel_threads_run_logger(
        self, tmp_repo, monkeypatch, capsys
    ):
        """The parallel path builds and threads a run_logger (was dropped),
        so per-finding apply calls land in the run log like the serial walk."""
        import sys as _sys

        import plan_tool.cli.completeness_apply_parallel as par
        import plan_tool.cli.completeness_phases as phases
        from plan_tool.cli import main

        self._setup(tmp_repo)
        monkeypatch.setattr(phases, "working_tree_dirty", lambda root: False)
        monkeypatch.setattr(_sys, "stdin",
                            SimpleNamespace(isatty=lambda: True))

        captured: dict = {}

        def fake_run(walk_recs, **kwargs):
            captured["run_logger"] = kwargs.get("run_logger")
            from plan_tool.telemetry import record_apply_verdict
            record_apply_verdict(
                tmp_repo.root, plan_slug="demo", verdict="NOT-APPLICABLE"
            )
            return par.ReplayOutcome()

        monkeypatch.setattr(par, "run_parallel_apply", fake_run)
        rc = main(tmp_repo.argv("completeness-apply", "demo", "--jobs", "2",
                                "-y"))
        assert rc == 0
        # A live writer is threaded through (None before the fix).
        assert captured["run_logger"] is not None
        from plan_tool.telemetry import read_decisions
        event = [e for e in read_decisions(tmp_repo.root)
                 if e.kind == "apply-verdict"][-1]
        assert event.run_id == captured["run_logger"].run_id
        from plan_tool.telemetry import record_apply_verdict
        record_apply_verdict(
            tmp_repo.root, plan_slug="after-command", verdict="BLOCKED"
        )
        assert read_decisions(tmp_repo.root)[-1].run_id == ""

    def test_parallel_hoists_and_recomputes_plan_fingerprints(
        self, tmp_repo, monkeypatch
    ):
        import sys as _sys

        import plan_tool.cli.completeness_apply_parallel as par
        import plan_tool.cli.completeness_phases as phases
        import plan_tool.review_persistence as persistence
        from plan_tool.cli import main

        self._setup(tmp_repo)
        monkeypatch.setattr(phases, "working_tree_dirty", lambda root: False)
        monkeypatch.setattr(_sys, "stdin", SimpleNamespace(isatty=lambda: True))
        fingerprints = iter(["pre-dispatch", "conflict-rerun"])
        monkeypatch.setattr(
            persistence, "compute_plan_fingerprint", lambda path: next(fingerprints)
        )
        captured = {}

        def fake_run(walk_recs, **kwargs):
            captured["worker"] = kwargs["plan_fingerprint"]
            captured["rerun"] = kwargs["compute_plan_fingerprint_fn"]()
            return par.ReplayOutcome()

        monkeypatch.setattr(par, "run_parallel_apply", fake_run)
        assert main(tmp_repo.argv(
            "completeness-apply", "demo", "--jobs", "2", "-y"
        )) == 0
        assert captured == {
            "worker": "pre-dispatch", "rerun": "conflict-rerun"
        }

    def test_parallel_command_real_replay_binds_run_and_evaluated_fingerprints(
        self, tmp_repo, monkeypatch
    ):
        import contextlib
        import sys as _sys

        import plan_tool.cli.completeness_apply_parallel as par
        import plan_tool.cli.completeness_phases as phases
        import plan_tool.review_persistence as persistence
        from plan_tool.cli import main
        from plan_tool.telemetry import read_decisions

        plan_path, _ = self._setup(tmp_repo)
        plan_rel = plan_path.relative_to(tmp_repo.root).as_posix()
        monkeypatch.setattr(phases, "working_tree_dirty", lambda root: False)
        monkeypatch.setattr(_sys, "stdin", SimpleNamespace(isatty=lambda: True))
        fingerprints = iter(["pre-dispatch", "conflict-rerun"])
        monkeypatch.setattr(
            persistence, "compute_plan_fingerprint", lambda path: next(fingerprints)
        )

        class CanonicalPool:
            def __init__(self, *args, **kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

            @contextlib.contextmanager
            def acquire(self):
                yield SimpleNamespace(
                    repo_root=tmp_repo.root, plan_path=plan_path
                )

        monkeypatch.setattr(par, "WorktreePool", CanonicalPool)

        def fake_apply(rec, *, plan_fingerprint, **kwargs):
            if rec.id == "corr-1" and plan_fingerprint == "pre-dispatch":
                stale = par.FileChange(
                    path=plan_rel, pre="stale worker baseline", post="stale post"
                )
                return par.FindingApplyResult(
                    rec=rec, verdict="APPLIED", summary="", exit_code=0,
                    changes=(stale,), recordable_verdict="APPLIED",
                    resolved_step_id=1, plan_fingerprint=plan_fingerprint,
                )
            return par.FindingApplyResult(
                rec=rec, verdict="NOT-APPLICABLE", summary="", exit_code=0,
                recordable_verdict="NOT-APPLICABLE", resolved_step_id=1,
                plan_fingerprint=plan_fingerprint,
            )

        monkeypatch.setattr(par, "apply_finding_in_tree", fake_apply)

        assert main(tmp_repo.argv(
            "completeness-apply", "demo", "--jobs", "2", "-y"
        )) == 0

        events = [
            event for event in read_decisions(tmp_repo.root)
            if event.kind == "apply-verdict"
        ]
        assert {
            (event.anchor, event.plan_fingerprint, event.context["verdict"])
            for event in events
        } == {
            ("corr-1", "conflict-rerun", "NOT-APPLICABLE"),
            ("comp-1", "pre-dispatch", "NOT-APPLICABLE"),
        }
        assert len({event.run_id for event in events}) == 1
        assert events[0].run_id

    def test_parallel_pre_skips_open_deferred_findings(
        self, tmp_repo, monkeypatch, capsys
    ):
        """Parallel pre-skip mirrors the serial walk: only unannotated or
        ``failed`` recs are re-walked; ``open`` (and applied/skip) pre-skip,
        so a deferred gap is not silently re-applied by --jobs N."""
        import sys as _sys

        import plan_tool.cli.completeness_apply_parallel as par
        import plan_tool.cli.completeness_phases as phases
        from plan_tool.cli import main
        from plan_tool.review_persistence import Annotation, save_review

        plan_path = tmp_repo.add_plan("1-demo", title="Demo")
        _attach_minimal_detail(tmp_repo, plan_path)
        tmp_repo.write_manifest()
        recs = self._recs()  # corr-1, comp-1
        save_review(
            plan_slug="demo",
            plan_path=plan_path.relative_to(tmp_repo.root).as_posix(),
            repo_root=tmp_repo.root, report_md="# r\n",
            recommendations=recs,
            annotations={
                "corr-1": Annotation(status="open"),      # deferred → skip
                "comp-1": Annotation(status="failed"),    # failed → re-walk
            },
            kind="completeness",
        )
        monkeypatch.setattr(phases, "working_tree_dirty", lambda root: False)
        monkeypatch.setattr(_sys, "stdin",
                            SimpleNamespace(isatty=lambda: True))

        seen: dict = {}

        def fake_run(walk_recs, **kwargs):
            seen["ids"] = [r.id for r in walk_recs]
            return par.ReplayOutcome()

        monkeypatch.setattr(par, "run_parallel_apply", fake_run)
        rc = main(tmp_repo.argv("completeness-apply", "demo", "--jobs", "2",
                                "-y"))
        assert rc == 0
        # open pre-skipped; only the failed rec is re-walked.
        assert seen["ids"] == ["comp-1"]

    def test_jobs_1_uses_interactive_walk_not_parallel(
        self, tmp_repo, monkeypatch
    ):
        """--jobs 1 (default) must never enter the parallel path."""
        import sys as _sys

        import plan_tool.cli.completeness_apply_parallel as par
        from plan_tool.cli import main

        self._setup(tmp_repo)
        monkeypatch.setattr(
            par, "run_parallel_apply",
            lambda *a, **k: pytest.fail("parallel path must not run at jobs=1"),
        )
        monkeypatch.setattr(_sys, "stdin",
                            SimpleNamespace(isatty=lambda: False))
        rc = main(tmp_repo.argv("completeness-apply", "demo", "--jobs", "1"))
        # The monkeypatched ``run_parallel_apply`` above is what proves the
        # claim; rc=2 is the serial path's non-interactive skip, reached
        # precisely because jobs=1 did not parallelize.
        assert rc == 2

    def test_non_tty_without_yes_refused(self, tmp_repo, monkeypatch, capsys):
        """#74/B2 fix: --jobs>1 requires -y even non-interactively (CI/pipe);
        it must not silently auto-mutate just because stdin isn't a TTY."""
        import sys as _sys

        import plan_tool.cli.completeness_phases as phases
        from plan_tool.cli import main

        self._setup(tmp_repo)
        monkeypatch.setattr(phases, "working_tree_dirty", lambda root: False)
        monkeypatch.setattr(_sys, "stdin",
                            SimpleNamespace(isatty=lambda: False))
        rc = main(tmp_repo.argv("completeness-apply", "demo", "--jobs", "2"))
        assert rc == 2
        assert "-y" in capsys.readouterr().err

    def test_already_annotated_gaps_skipped(self, tmp_repo, monkeypatch,
                                           capsys):
        """#74/B2 fix: a second --jobs run skips gaps already applied/skipped
        (unless --rewalk), mirroring the serial walk's pre-skip."""
        import sys as _sys

        import plan_tool.cli.completeness_apply_parallel as par
        import plan_tool.cli.completeness_phases as phases
        from plan_tool.cli import main
        from plan_tool.review_persistence import Annotation, save_review

        plan_path = tmp_repo.add_plan("1-demo", title="Demo")
        _attach_minimal_detail(tmp_repo, plan_path)
        tmp_repo.write_manifest()
        # Both gaps already answered.
        save_review(
            plan_slug="demo",
            plan_path=plan_path.relative_to(tmp_repo.root).as_posix(),
            repo_root=tmp_repo.root, report_md="# r\n",
            recommendations=self._recs(),
            annotations={"corr-1": Annotation(status="applied"),
                         "comp-1": Annotation(status="skip")},
            kind="completeness",
        )
        monkeypatch.setattr(phases, "working_tree_dirty", lambda root: False)
        monkeypatch.setattr(_sys, "stdin",
                            SimpleNamespace(isatty=lambda: True))
        monkeypatch.setattr(
            par, "run_parallel_apply",
            lambda *a, **k: pytest.fail("no gaps should be dispatched"),
        )
        rc = main(tmp_repo.argv("completeness-apply", "demo", "--jobs", "2",
                                "-y"))
        assert rc == 0
        assert "already answered" in capsys.readouterr().out

    def test_info_gaps_skipped_without_include_info(self, tmp_repo,
                                                   monkeypatch):
        """#74/B2 fix: the parallel path honors skip-info like the walk."""
        import sys as _sys

        import plan_tool.cli.completeness_apply_parallel as par
        import plan_tool.cli.completeness_phases as phases
        from plan_tool.cli import main
        from plan_tool.review_persistence import save_review

        plan_path = tmp_repo.add_plan("1-demo", title="Demo")
        _attach_minimal_detail(tmp_repo, plan_path)
        tmp_repo.write_manifest()
        info_rec = Recommendation(
            id="info-1", source="plan-completeness", severity="info",
            step_id=1, title="t", body="b", anchor="info-1")
        save_review(
            plan_slug="demo",
            plan_path=plan_path.relative_to(tmp_repo.root).as_posix(),
            repo_root=tmp_repo.root, report_md="# r\n",
            recommendations=[info_rec], annotations={}, kind="completeness",
        )
        monkeypatch.setattr(phases, "working_tree_dirty", lambda root: False)
        monkeypatch.setattr(_sys, "stdin",
                            SimpleNamespace(isatty=lambda: True))
        dispatched = []
        monkeypatch.setattr(
            par, "run_parallel_apply",
            lambda recs, **k: dispatched.append(list(recs)) or par.ReplayOutcome(),
        )
        rc = main(tmp_repo.argv("completeness-apply", "demo", "--jobs", "2",
                                "-y"))
        assert rc == 0
        # The lone info gap was filtered out — nothing dispatched.
        assert dispatched == [] or dispatched == [[]]

    def test_bare_plan_parallel_lane_fans_out_only_correctness(
        self, tmp_repo, monkeypatch
    ):
        import sys as _sys

        import plan_tool.cli.completeness_apply_parallel as par
        import plan_tool.cli.completeness_phases as phases
        from plan_tool.cli import main
        from plan_tool.review_persistence import save_review

        plan_path = tmp_repo.add_plan("1-demo", title="Demo")
        tmp_repo.write_manifest()
        save_review(
            plan_slug="demo",
            plan_path=plan_path.relative_to(tmp_repo.root).as_posix(),
            repo_root=tmp_repo.root,
            report_md="# r\n",
            recommendations=[
                Recommendation(
                    id="corr-1", source="plan-correctness", severity="high",
                    step_id=1, title="t", body="b1", anchor="corr-1",
                ),
                Recommendation(
                    id="comp-1", source="plan-completeness", severity="medium",
                    step_id=1, title="t", body="b2", anchor="comp-1",
                ),
            ],
            annotations={},
            kind="completeness",
        )
        monkeypatch.setattr(phases, "working_tree_dirty", lambda root: False)
        monkeypatch.setattr(_sys, "stdin",
                            SimpleNamespace(isatty=lambda: True))
        seen: list[str] = []

        def fake_run(walk_recs, **kwargs):
            seen.extend(r.source for r in walk_recs)
            return par.ReplayOutcome()

        monkeypatch.setattr(par, "run_parallel_apply", fake_run)
        rc = main(tmp_repo.argv("completeness-apply", "demo", "--jobs", "2",
                                "-y"))
        assert rc == 0
        assert seen == ["plan-correctness"]

    def test_bare_plan_parallel_lane_does_not_replay_a_created_detail_file(
        self, tmp_repo, monkeypatch
    ):
        import sys as _sys

        import plan_tool.cli.completeness_apply_parallel as par
        import plan_tool.cli.completeness_phases as phases
        from plan_tool.cli import main
        from plan_tool.review_persistence import save_review

        _init_git_repo(tmp_repo.root)
        plan_path = tmp_repo.add_plan("1-demo", title="Demo")
        detail_rel = "plans/details/01-only-step.md"
        text = plan_path.read_text(encoding="utf-8")
        plan_path.write_text(
            text.replace(
                "    title: Only step\n",
                f"    title: Only step\n    detail: {detail_rel}\n",
            ),
            encoding="utf-8",
        )
        tmp_repo.write_manifest()
        _git_commit_all(tmp_repo.root, "init")
        save_review(
            plan_slug="demo",
            plan_path=plan_path.relative_to(tmp_repo.root).as_posix(),
            repo_root=tmp_repo.root,
            report_md="# r\n",
            recommendations=[
                Recommendation(
                    id="corr-1", source="plan-correctness", severity="high",
                    step_id=1, title="t", body="b1", anchor="corr-1",
                ),
            ],
            annotations={},
            kind="completeness",
        )
        detail_path = tmp_repo.root / detail_rel
        monkeypatch.setattr(phases, "working_tree_dirty", lambda root: False)
        monkeypatch.setattr(_sys, "stdin",
                            SimpleNamespace(isatty=lambda: True))

        real_apply_in_tree = par.apply_finding_in_tree

        def patched_apply(rec, **kwargs):
            def fake_invoker(prompt: str) -> tuple[int, str]:
                p = kwargs["plan_path"]
                p.write_text(
                    p.read_text(encoding="utf-8") + "\nApplied edit.\n",
                    encoding="utf-8",
                )
                d = kwargs["repo_root"] / detail_rel
                d.parent.mkdir(parents=True, exist_ok=True)
                d.write_text("# unauthorized\n", encoding="utf-8")
                return 0, "## Verdict\nAPPLIED\n"

            kwargs["invoker"] = fake_invoker
            return real_apply_in_tree(rec, **kwargs)

        monkeypatch.setattr(par, "apply_finding_in_tree", patched_apply)
        rc = main(tmp_repo.argv("completeness-apply", "demo", "--jobs", "2",
                                "-y"))
        assert rc == 0
        assert "Applied edit." in plan_path.read_text(encoding="utf-8")
        assert not detail_path.exists()


class TestCompletenessApplyStructuralSplit:
    """Step 4: ``--apply-structural`` wires the saved ``medium``
    ``granularity-split`` MIXED-STEP finding into the serial walk so it reaches
    the escalate-to-split dispatch, gated behind the flag + an interactive
    confirm (never a blanket ``-y``, never the ``--jobs > 1`` parallel lane)."""

    def _split_rec(self, *, step_id=1, severity="medium"):
        from plan_tool.granularity import GRANULARITY_SPLIT_SOURCE

        return Recommendation(
            id=f"gsplit-{step_id}",
            source=GRANULARITY_SPLIT_SOURCE,
            severity=severity,
            step_id=step_id,
            title="step mixes a refactor with new behavior",
            body="split the refactor half from the feature half",
            anchor=f"gsplit-{step_id}",
            suggested_action="plan-tool split demo --step 1",
        )

    def _save(self, tmp_repo, plan_path, recs):
        from plan_tool.review_persistence import save_review

        return save_review(
            plan_slug="demo",
            plan_path=plan_path.relative_to(tmp_repo.root).as_posix(),
            repo_root=tmp_repo.root, report_md="# r\n",
            recommendations=recs, annotations={}, kind="completeness",
        )

    def _setup(self, tmp_repo, recs):
        plan_path = tmp_repo.add_plan("1-demo", title="Demo")
        _attach_minimal_detail(tmp_repo, plan_path)
        tmp_repo.write_manifest()
        return plan_path, self._save(tmp_repo, plan_path, recs)

    def _drive(self, tmp_repo, monkeypatch, *, argv_extra, stdin_tty=True):
        """Run completeness-apply with the serial walk stubbed to drive the
        real ``action_fn`` over the saved split rec. Returns
        ``(rc, escalate_calls, captured)`` — ``captured`` holds the walk's
        ``extra_apply_sources`` and the (filtered, sorted) recommendations."""
        import sys as _sys

        import plan_tool.cli.completeness_phases as phases
        from plan_tool.cli import main
        from plan_tool.granularity import GRANULARITY_SPLIT_SOURCE
        from plan_tool.review_walk import WalkResult

        captured: dict = {}
        calls: list[dict] = []

        def fake_escalate(plan_path, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                outcome="recommended", target_id=kwargs.get("step_id"),
                recommendation=SimpleNamespace(
                    suggested_action="plan-tool split demo --step 1 --into ..."
                ),
                blocking=[],
            )

        monkeypatch.setattr(
            "plan_tool.launcher.escalate_to_split", fake_escalate
        )

        def fake_walk(saved, *, action_fn, extra_apply_sources, **kw):
            captured["extra_apply_sources"] = extra_apply_sources
            captured["recommendations"] = list(saved.recommendations)
            split = next(
                r for r in saved.recommendations
                if r.source == GRANULARITY_SPLIT_SOURCE
            )
            action_fn(split)
            return WalkResult(answered=1, quit_early=False)

        monkeypatch.setattr(phases, "walk_recommendations", fake_walk)
        monkeypatch.setattr(
            _sys, "stdin", SimpleNamespace(isatty=lambda: stdin_tty)
        )
        rc = main(tmp_repo.argv("completeness-apply", "demo", *argv_extra))
        return rc, calls, captured

    def test_apply_structural_flag_registered(self) -> None:
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="cmd")
        register(sub)
        args = parser.parse_args(
            ["completeness-apply", "demo", "--apply-structural"]
        )
        assert args.apply_structural is True
        default = parser.parse_args(["completeness-apply", "demo"])
        assert default.apply_structural is False

    def test_medium_split_survives_saved_walk_filter(
        self, tmp_repo, monkeypatch
    ) -> None:
        from plan_tool.granularity import GRANULARITY_SPLIT_SOURCE

        recs = [
            self._split_rec(step_id=1),
            Recommendation(id="dc-1", source="data-contract", severity="medium",
                           step_id=None, title="t", body="b", anchor="dc-1"),
            Recommendation(id="comp-1", source="plan-completeness",
                           severity="medium", step_id=1, title="t", body="b",
                           anchor="comp-1"),
            Recommendation(id="corr-1", source="plan-correctness",
                           severity="high", step_id=1, title="t", body="b",
                           anchor="corr-1"),
        ]
        self._setup(tmp_repo, recs)
        rc, _calls, cap = self._drive(
            tmp_repo, monkeypatch, argv_extra=["--apply-structural"]
        )
        assert rc == 0
        sources = [r.source for r in cap["recommendations"]]
        assert GRANULARITY_SPLIT_SOURCE in sources
        # Sorts LAST — after the reversible conceptual + data-contract applies.
        assert sources == [
            "plan-correctness", "plan-completeness", "data-contract",
            GRANULARITY_SPLIT_SOURCE,
        ]

    def test_walk_apply_sources_includes_granularity_split(
        self, tmp_repo, monkeypatch
    ) -> None:
        import sys as _sys

        import plan_tool.cli.completeness_phases as phases
        from plan_tool.cli import main
        from plan_tool.granularity import GRANULARITY_SPLIT_SOURCE
        from plan_tool.review_walk import WalkResult

        self._setup(tmp_repo, [self._split_rec(step_id=1)])
        seen: dict = {}
        real_builder = phases._build_review_action_fn

        def spy_builder(**kwargs):
            seen["builder"] = kwargs.get("extra_apply_sources")
            return real_builder(**kwargs)

        def fake_walk(saved, *, extra_apply_sources, **kw):
            seen["walk"] = extra_apply_sources
            return WalkResult(answered=0, quit_early=False)

        monkeypatch.setattr(phases, "_build_review_action_fn", spy_builder)
        monkeypatch.setattr(phases, "walk_recommendations", fake_walk)
        monkeypatch.setattr(
            _sys, "stdin", SimpleNamespace(isatty=lambda: True)
        )
        rc = main(
            tmp_repo.argv("completeness-apply", "demo", "--apply-structural")
        )
        assert rc == 0
        # Both seams must agree, or the walk annotates without dispatching.
        assert GRANULARITY_SPLIT_SOURCE in seen["builder"]
        assert GRANULARITY_SPLIT_SOURCE in seen["walk"]
        assert seen["builder"] == seen["walk"]

    def test_apply_structural_dispatches_medium_split_to_escalate(
        self, tmp_repo, monkeypatch
    ) -> None:
        self._setup(tmp_repo, [self._split_rec(step_id=1)])
        rc, calls, _cap = self._drive(
            tmp_repo, monkeypatch, argv_extra=["--apply-structural"]
        )
        assert rc == 0
        assert len(calls) == 1
        assert calls[0]["step_id"] == 1
        assert calls[0]["allow_split"] is True

    def test_medium_split_recommend_only_without_flag(
        self, tmp_repo, monkeypatch
    ) -> None:
        plan_path, _saved = self._setup(tmp_repo, [self._split_rec(step_id=1)])
        before = plan_path.read_text(encoding="utf-8")
        rc, calls, _cap = self._drive(
            tmp_repo, monkeypatch, argv_extra=[]
        )
        assert rc == 0
        assert len(calls) == 1
        assert calls[0]["allow_split"] is False  # recommend-only
        # No split landed — the plan file is unchanged.
        assert plan_path.read_text(encoding="utf-8") == before

    def test_medium_split_recommend_only_under_yes(
        self, tmp_repo, monkeypatch
    ) -> None:
        self._setup(tmp_repo, [self._split_rec(step_id=1)])
        rc, calls, _cap = self._drive(
            tmp_repo, monkeypatch, argv_extra=["--apply-structural", "-y"]
        )
        assert rc == 0
        assert len(calls) == 1
        # A blanket -y fast-forward never auto-confirms an irreversible split.
        assert calls[0]["allow_split"] is False

    def test_medium_split_not_fanned_out_in_parallel(
        self, tmp_repo, monkeypatch, capsys
    ) -> None:
        import sys as _sys

        import plan_tool.cli.completeness_apply_parallel as par
        import plan_tool.cli.completeness_phases as phases
        from plan_tool.cli import main
        from plan_tool.granularity import GRANULARITY_SPLIT_SOURCE

        # A mixed sidecar: a conceptual gap (fans out) plus a medium split
        # (must NOT). The parallel lane runs, so the split is deferred with a
        # visible breadcrumb rather than silently dropped.
        recs = [
            Recommendation(id="comp-1", source="plan-completeness",
                           severity="medium", step_id=1, title="t", body="b",
                           anchor="comp-1"),
            self._split_rec(step_id=1),
        ]
        self._setup(tmp_repo, recs)
        monkeypatch.setattr(phases, "working_tree_dirty", lambda root: False)
        monkeypatch.setattr(
            _sys, "stdin", SimpleNamespace(isatty=lambda: True)
        )
        seen: list[str] = []

        def fake_run(walk_recs, **kw):
            seen.extend(r.source for r in walk_recs)
            return par.ReplayOutcome()

        monkeypatch.setattr(par, "run_parallel_apply", fake_run)
        rc = main(
            tmp_repo.argv("completeness-apply", "demo", "--jobs", "2", "-y")
        )
        assert rc == 0
        # Only the conceptual source is fanned out — the split stays serial.
        assert GRANULARITY_SPLIT_SOURCE not in seen
        assert seen == ["plan-completeness"]
        # The deferral is surfaced, not silently dropped ("no silent caps").
        assert "mixed-step split" in capsys.readouterr().err


class TestPassConformanceAndConceptualBar:
    """Step 4: pass-conformance aggregates and conceptual bar-blocking set."""

    def test_auto_reuse_declines_when_conformance_missing(
        self, tmp_repo, monkeypatch
    ) -> None:
        concept = _rec("medium", source="plan-completeness")
        TestResolveAuditReuse()._patch_lookup(
            monkeypatch,
            _ru(
                conceptual=[concept],
                audit_coverage={
                    "evidence_status": "observed",
                    "budget_limited": False,
                    "passes_used": 2,
                    "cap": 2,
                    "recommendation_kind": None,
                    "recommended_passes": None,
                    "recommendation_advice": None,
                    "confirmation_kind": "confirmed-dry",
                },
            ),
        )
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        out = _resolve_audit_reuse(plan, path, ctx, _reuse_args(yes=True))
        assert out is None

    def test_explicit_reuse_without_conformance_sets_audit_incomplete(
        self, tmp_repo, monkeypatch, capsys
    ) -> None:
        concept = _rec("medium", source="plan-completeness")
        legacy = {
            "evidence_status": "observed",
            "budget_limited": False,
            "passes_used": 2,
            "cap": 2,
            "recommendation_kind": None,
            "recommended_passes": None,
            "recommendation_advice": None,
            "confirmation_kind": "confirmed-dry",
        }
        TestResolveAuditReuse()._patch_lookup(
            monkeypatch, _ru(conceptual=[concept], audit_coverage=legacy)
        )
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        out = _resolve_audit_reuse(
            plan, path, ctx, _reuse_args(reuse_audit=True)
        )
        assert out == [concept]
        bundle_status, audit_stage = _hoisted_bundle(plan, path, tmp_repo.root)
        rc = finalize_completeness_run(
            plan,
            path,
            ctx,
            SimpleNamespace(
                name="1-sectioned", json=False, fail_on_findings=False, commit=False
            ),
            budget=IterativeBudget(enabled=False),
            outcome=_IterateOutcome(),
            reused_audit_recs=out,
            reused_audit_coverage=legacy,
            code_drifted=False,
            audit_passes=1,
            audit_dry_rounds=1,
            bundle_status=bundle_status,
            audit_stage=audit_stage,
        )
        assert rc == 0
        assert "pass-conformance" in capsys.readouterr().err

    def test_explicit_reuse_with_conformance_qualifies_sample(
        self, tmp_repo, monkeypatch
    ) -> None:
        corr = _rec("medium", source="plan-correctness")
        coverage = _observed_audit_coverage(
            budget_limited=False,
            passes_used=1,
            cap=1,
            confirmation_kind="confirmed-dry",
        )
        TestResolveAuditReuse()._patch_lookup(
            monkeypatch, _ru(correctness=[corr], audit_coverage=coverage)
        )
        ctx = SimpleNamespace(repo_root=tmp_repo.root)
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        out = _resolve_audit_reuse(
            plan, path, ctx, _reuse_args(reuse_audit=True)
        )
        assert out == [corr]
        bundle_status, audit_stage = _hoisted_bundle(plan, path, tmp_repo.root)
        from plan_tool.cli.completeness_cmd import _conceptual_bar_from_audit_recs

        bar_ids, incomplete = _conceptual_bar_from_audit_recs(
            out, audit_stage=audit_stage, coverage=coverage
        )
        assert incomplete is False
        assert bar_ids == ("plan-correctness-medium",)

    def test_budget_limited_marks_incomplete_even_when_pass_conformance_qualifies(
        self, tmp_repo
    ) -> None:
        """A still-discovering (budget-limited) run must not read as complete.

        Pass-conformance alone (``audit_coverage_qualifies_sample``) can't
        tell confirmation apart from conformance -- a still-discovering run
        ordinarily has every individual pass parse fine. ``budget_limited``
        is checked directly here so a well-formed but never-converged
        sample doesn't feed a false "clean" into finalize / --fail-on-findings.
        """
        from plan_tool.cli.completeness_cmd import _conceptual_bar_from_audit_recs

        corr = _rec("medium", source="plan-correctness")
        coverage = _observed_audit_coverage(
            budget_limited=True, passes_used=3, cap=3, confirmation_kind=None,
        )
        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        _, audit_stage = _hoisted_bundle(plan, path, tmp_repo.root)
        bar_ids, incomplete = _conceptual_bar_from_audit_recs(
            [corr], audit_stage=audit_stage, coverage=coverage
        )
        assert incomplete is True
        assert bar_ids == ()

    def test_iterate_path_computes_bar_blocking_ids_with_audit_stage(
        self, tmp_repo, monkeypatch
    ) -> None:
        from plan_tool import review as review_module
        from plan_tool.cli.app import build_parser
        from plan_tool.cli.context import _load_context

        plan_path = tmp_repo.add_plan("1-demo", title="Demo")
        tmp_repo.write_manifest()
        corr = _rec("medium", source="plan-correctness")
        budget = {
            "budget_limited": False,
            "passes_used": 1,
            "cap": 1,
            "recommendation_kind": None,
            "recommended_passes": None,
            "recommendation_advice": None,
            "confirmation_kind": "confirmed-dry",
            "conforming_pass_count": 1,
            "failed_or_malformed_pass_count": 0,
        }

        def fake_audit(*_a, budget_report=None, **_kw):
            if budget_report is not None:
                budget_report.update(budget)
            return [corr]

        monkeypatch.setattr(
            review_module, "collect_deterministic_findings", lambda *_a, **_kw: []
        )
        monkeypatch.setattr(
            review_module, "collect_self_consistency_findings", lambda *_a, **_kw: []
        )
        monkeypatch.setattr(review_module, "audit_plan_until_stable", fake_audit)
        args = build_parser().parse_args(
            tmp_repo.argv(
                "completeness-audit", "demo", "--iterate", "--yes",
                "--max-iterations", "1",
            )
        )
        ctx = _load_context(args)
        plan = parse_plan(plan_path)
        bundle_status, audit_stage = _hoisted_bundle(plan, plan_path, tmp_repo.root)
        outcome = _run_iterate_convergence_loop(
            plan,
            plan_path,
            ctx,
            args,
            IterativeBudget(enabled=True, max_iterations=1),
            bundle_status=bundle_status,
            audit_stage=audit_stage,
        )
        assert outcome.conceptual_bar_blocking_ids == ("plan-correctness-medium",)
        assert outcome.audit_incomplete is False

    def test_iterate_fresh_budget_limited_conforming_gets_no_conformance_warning(
        self, tmp_repo, monkeypatch, capsys
    ) -> None:
        """Mirrors the non-iterate case in ``TestFinalizeCompletenessRun``:
        the iterate loop's own fresh-audit branch must not print
        ``_warn_audit_incomplete``'s conformance-specific message for a
        still-discovering (``budget_limited=True``) sample whose attempted
        passes all parsed cleanly -- ``emit_coverage_unconfirmed`` already
        reports the budget-limited fact accurately."""
        from plan_tool import review as review_module
        from plan_tool.cli.app import build_parser
        from plan_tool.cli.context import _load_context

        plan_path = tmp_repo.add_plan("1-demo", title="Demo")
        tmp_repo.write_manifest()
        budget = _qualifying_producer_coverage(
            budget_limited=True, passes_used=3, cap=3,
        )

        def fake_audit(*_a, budget_report=None, **_kw):
            if budget_report is not None:
                budget_report.update(budget)
            return []

        monkeypatch.setattr(
            review_module, "collect_deterministic_findings", lambda *_a, **_kw: []
        )
        monkeypatch.setattr(
            review_module, "collect_self_consistency_findings", lambda *_a, **_kw: []
        )
        monkeypatch.setattr(review_module, "audit_plan_until_stable", fake_audit)
        args = build_parser().parse_args(
            tmp_repo.argv(
                "completeness-audit", "demo", "--iterate", "--yes",
                "--max-iterations", "1",
            )
        )
        ctx = _load_context(args)
        plan = parse_plan(plan_path)
        bundle_status, audit_stage = _hoisted_bundle(plan, plan_path, tmp_repo.root)
        capsys.readouterr()
        _run_iterate_convergence_loop(
            plan,
            plan_path,
            ctx,
            args,
            IterativeBudget(enabled=True, max_iterations=1),
            bundle_status=bundle_status,
            audit_stage=audit_stage,
        )
        err = capsys.readouterr().err
        assert "did not produce a qualifying sample" not in err
        assert "pass-conformance evidence" not in err
        assert "COVERAGE UNCONFIRMED" in err

    def test_iterate_fresh_non_conforming_sample_gets_conformance_warning(
        self, tmp_repo, monkeypatch, capsys
    ) -> None:
        """Companion presence-test: a genuinely non-conforming fresh sample
        (a failed/malformed pass, not just budget-limited) must still print
        the conformance warning through the iterate loop's own fresh-audit
        branch -- the two tests above only ever assert its absence, which
        can't by itself prove the branch still fires it when it should."""
        from plan_tool import review as review_module
        from plan_tool.cli.app import build_parser
        from plan_tool.cli.context import _load_context

        plan_path = tmp_repo.add_plan("1-demo", title="Demo")
        tmp_repo.write_manifest()
        budget = {
            "budget_limited": False,
            "passes_used": 1,
            "cap": 1,
            "recommendation_kind": None,
            "recommended_passes": None,
            "recommendation_advice": None,
            "confirmation_kind": None,
            "conforming_pass_count": 0,
            "failed_or_malformed_pass_count": 1,
        }

        def fake_audit(*_a, budget_report=None, **_kw):
            if budget_report is not None:
                budget_report.update(budget)
            return []

        monkeypatch.setattr(
            review_module, "collect_deterministic_findings", lambda *_a, **_kw: []
        )
        monkeypatch.setattr(
            review_module, "collect_self_consistency_findings", lambda *_a, **_kw: []
        )
        monkeypatch.setattr(review_module, "audit_plan_until_stable", fake_audit)
        args = build_parser().parse_args(
            tmp_repo.argv(
                "completeness-audit", "demo", "--iterate", "--yes",
                "--max-iterations", "1",
            )
        )
        ctx = _load_context(args)
        plan = parse_plan(plan_path)
        bundle_status, audit_stage = _hoisted_bundle(plan, plan_path, tmp_repo.root)
        capsys.readouterr()
        _run_iterate_convergence_loop(
            plan,
            plan_path,
            ctx,
            args,
            IterativeBudget(enabled=True, max_iterations=1),
            bundle_status=bundle_status,
            audit_stage=audit_stage,
        )
        err = capsys.readouterr().err
        assert err.count("did not produce a qualifying sample") == 1

    def test_iterate_reuse_path_computes_bar_after_hoist(
        self, tmp_repo, monkeypatch
    ) -> None:
        from plan_tool import review as review_module
        import plan_tool.cli.completeness_phases as completeness_phases
        from plan_tool.cli.app import build_parser
        from plan_tool.cli.context import _load_context

        plan_path = tmp_repo.add_plan("1-demo", title="Demo")
        tmp_repo.write_manifest()
        corr = _rec("medium", source="plan-correctness")
        coverage = _observed_audit_coverage(
            budget_limited=False,
            passes_used=1,
            cap=1,
            confirmation_kind="confirmed-dry",
        )
        bar_calls: list = []

        def fake_bar(*_a, **kwargs):
            bar_calls.append(kwargs.get("audit_stage"))
            return ("plan-correctness-medium",)

        # compute_conceptual_bar_blocking_ids now lives in completeness_phases
        # alongside its sole caller here (_conceptual_bar_from_audit_recs), so
        # the bare-name call it makes resolves through completeness_phases'
        # own module globals -- patching completeness_cmd's re-imported copy
        # would not intercept it.
        monkeypatch.setattr(
            completeness_phases, "compute_conceptual_bar_blocking_ids", fake_bar
        )
        monkeypatch.setattr(
            review_module, "collect_deterministic_findings", lambda *_a, **_kw: []
        )
        monkeypatch.setattr(
            review_module, "collect_self_consistency_findings", lambda *_a, **_kw: []
        )
        monkeypatch.setattr(
            review_module,
            "audit_plan_until_stable",
            lambda *_a, **_kw: (_ for _ in ()).throw(
                AssertionError("iterate reuse must skip the up-front audit")
            ),
        )
        args = build_parser().parse_args(
            tmp_repo.argv(
                "completeness-audit", "demo", "--iterate", "--yes",
                "--max-iterations", "1",
            )
        )
        ctx = _load_context(args)
        plan = parse_plan(plan_path)
        bundle_status, audit_stage = _hoisted_bundle(plan, plan_path, tmp_repo.root)
        outcome = _run_iterate_convergence_loop(
            plan,
            plan_path,
            ctx,
            args,
            IterativeBudget(enabled=True, max_iterations=1),
            bundle_status=bundle_status,
            audit_stage=audit_stage,
            reused_audit_recs=[corr],
            reused_audit_coverage=coverage,
        )
        assert bar_calls == [audit_stage]
        assert outcome.conceptual_bar_blocking_ids == ("plan-correctness-medium",)

    def test_iterate_failed_command_capture_is_not_retried(
        self, tmp_repo, monkeypatch, capsys
    ) -> None:
        """A failed pre-audit capture remains no-evidence under --iterate."""
        import plan_tool.review as review_module
        from plan_tool.cli import main
        from plan_tool.review_persistence import AuditInputSnapshot

        tmp_repo.add_plan("1-demo", title="Demo")
        tmp_repo.write_manifest()
        calls = 0

        def failed_capture(*_args, **_kwargs):
            nonlocal calls
            calls += 1
            raise OSError("fixture capture failure")

        monkeypatch.setattr(AuditInputSnapshot, "capture", failed_capture)
        monkeypatch.setattr(
            review_module, "collect_deterministic_findings", lambda *_a, **_kw: []
        )
        monkeypatch.setattr(
            review_module, "collect_self_consistency_findings", lambda *_a, **_kw: []
        )
        monkeypatch.setattr(
            review_module,
            "audit_plan_until_stable",
            lambda *_a, **_kw: (_ for _ in ()).throw(
                AssertionError("failed command capture must skip conceptual audit")
            ),
        )

        rc = main(
            tmp_repo.argv(
                "completeness-audit", "demo", "--iterate", "--yes", "--json",
                "--max-iterations", "1",
            )
        )
        payload = json.loads(capsys.readouterr().out)

        assert rc == 0
        assert calls == 1
        assert payload["qualified_result"]["headline"] == "no-qualified-current-evidence"

    def test_finalize_refreshes_stale_pre_loop_bundle_status(
        self, tmp_repo, monkeypatch, capsys
    ) -> None:
        """A deterministic apply round that authors a step's first detail
        file flips the plan bare -> detail mid-loop; the final report/JSON
        must reflect that, not the pre-loop bare snapshot the loop's own
        (once-only) conceptual audit was grounded in."""
        import plan_tool.cli.completeness_phases as completeness_phases
        from plan_tool.cli import main
        from plan_tool.cli.completeness_phases import _IterateOutcome
        from plan_tool.parser import parse_plan

        tmp_repo.add_plan("1-demo", title="Demo")
        tmp_repo.write_manifest()

        code_finding = Recommendation(
            id="code-1",
            source="plan-completeness",
            severity="medium",
            step_id=None,
            title="Real bug",
            body="Fix `plan_tool/foo.py`.",
        )
        coverage = _observed_audit_coverage(
            budget_limited=False, passes_used=1, cap=1,
            confirmation_kind="confirmed-dry",
        )

        def fake_loop(plan, path, ctx, args, budget, *, bundle_status, audit_stage, **_kw):
            # Simulate a deterministic apply round authoring the step's
            # first detail file -- exactly the kind of mid-loop change that
            # flips bare -> detail.
            detail = path.parent / "plan-details" / "demo" / "01-only-step.md"
            detail.parent.mkdir(parents=True, exist_ok=True)
            detail.write_text("## Summary\n\nDone.\n", encoding="utf-8")
            return _IterateOutcome(
                stop_reason="converged",
                audit_recs=[code_finding],
                plan=parse_plan(path),
                budget=coverage,
                # Frozen at the *pre*-apply (bare) stage the loop's own
                # once-only conceptual audit ran under -- stale on purpose,
                # to prove finalize doesn't just trust it verbatim.
                conceptual_bar_blocking_ids=(),
                audit_incomplete=False,
            )

        monkeypatch.setattr(
            completeness_phases, "_run_iterate_convergence_loop", fake_loop
        )

        rc = main(
            tmp_repo.argv(
                "completeness-audit", "demo", "--iterate", "--yes", "--json",
                "--max-iterations", "1",
            )
        )
        out = capsys.readouterr().out
        payload = json.loads(out)
        assert payload["stage"] == "detail"
        assert payload["has_blocking_findings"] is True
        # exit-code convention: a completed audit exits 0 regardless of
        # findings unless --fail-on-findings is passed.
        assert rc == 0

    def test_audit_only_reuse_path_computes_bar_after_hoist(
        self, tmp_repo, monkeypatch
    ) -> None:
        import plan_tool.cli.completeness_cmd as completeness_cmd

        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        corr = _rec("medium", source="plan-correctness")
        coverage = _observed_audit_coverage(
            budget_limited=False,
            passes_used=1,
            cap=1,
            confirmation_kind="confirmed-dry",
        )
        monkeypatch.setattr(
            completeness_cmd,
            "_sample_conceptual_audit",
            lambda *_a, **_kw: (_ for _ in ()).throw(
                AssertionError("reuse must not trigger live audit")
            ),
        )
        bundle_status, audit_stage = _hoisted_bundle(plan, path, tmp_repo.root)
        finalize_completeness_run(
            plan,
            path,
            SimpleNamespace(repo_root=tmp_repo.root),
            SimpleNamespace(
                name="1-sectioned", json=False, fail_on_findings=False, commit=False
            ),
            budget=IterativeBudget(enabled=False),
            outcome=_IterateOutcome(),
            reused_audit_recs=[corr],
            reused_audit_coverage=coverage,
            code_drifted=False,
            audit_passes=1,
            audit_dry_rounds=1,
            bundle_status=bundle_status,
            audit_stage=audit_stage,
        )
        from plan_tool.cli.completeness_cmd import _conceptual_bar_from_audit_recs

        bar_ids, incomplete = _conceptual_bar_from_audit_recs(
            [corr], audit_stage=audit_stage, coverage=coverage
        )
        assert incomplete is False
        assert bar_ids == ("plan-correctness-medium",)

    def test_halt_outcome_carries_bar_and_incomplete(
        self, tmp_repo, monkeypatch
    ) -> None:
        from plan_tool import review as review_module
        from plan_tool.cli.app import build_parser
        from plan_tool.cli.context import _load_context

        plan_path = tmp_repo.add_plan("1-demo", title="Demo")
        tmp_repo.write_manifest()
        corr = _rec("medium", source="plan-correctness")
        budget = {
            "budget_limited": False,
            "passes_used": 1,
            "cap": 1,
            "recommendation_kind": None,
            "recommended_passes": None,
            "recommendation_advice": None,
            "confirmation_kind": "confirmed-dry",
            "conforming_pass_count": 1,
            "failed_or_malformed_pass_count": 0,
        }

        def fake_audit(*_a, budget_report=None, **_kw):
            if budget_report is not None:
                budget_report.update(budget)
            return [corr]

        monkeypatch.setattr(
            review_module, "collect_self_consistency_findings", lambda *_a, **_kw: []
        )
        monkeypatch.setattr(review_module, "audit_plan_until_stable", fake_audit)
        body_issue = Recommendation(
            id="body-1",
            source="body-completeness",
            severity="medium",
            step_id=None,
            title="missing risks",
            body="add ## Risks section",
        )
        monkeypatch.setattr(
            review_module,
            "collect_deterministic_findings",
            lambda *_a, **_kw: [body_issue],
        )
        drift_path = tmp_repo.root / "plan_tool" / "widget.py"
        drift_path.parent.mkdir(parents=True, exist_ok=True)
        drift_path.write_text("x", encoding="utf-8")
        monkeypatch.setattr(
            "plan_tool.drift_detection.check_drift",
            lambda _lock: [drift_path],
        )
        args = build_parser().parse_args(
            tmp_repo.argv(
                "completeness-audit", "demo", "--iterate", "--yes",
                "--max-iterations", "2",
            )
        )
        ctx = _load_context(args)
        plan = parse_plan(plan_path)
        bundle_status, audit_stage = _hoisted_bundle(plan, plan_path, tmp_repo.root)
        outcome = _run_iterate_convergence_loop(
            plan,
            plan_path,
            ctx,
            args,
            IterativeBudget(enabled=True, max_iterations=2),
            bundle_status=bundle_status,
            audit_stage=audit_stage,
        )
        assert outcome.early_exit_code == 2
        assert outcome.conceptual_bar_blocking_ids == ("plan-correctness-medium",)
        assert outcome.audit_incomplete is False

    def test_reuse_conformance_reads_coverage_input_not_live_budget_report(
        self, tmp_repo, monkeypatch
    ) -> None:
        from plan_tool import review as review_module
        from plan_tool.cli.app import build_parser
        from plan_tool.cli.context import _load_context

        plan_path = tmp_repo.add_plan("1-demo", title="Demo")
        tmp_repo.write_manifest()
        coverage = _observed_audit_coverage(
            budget_limited=False,
            passes_used=2,
            cap=3,
            confirmation_kind="confirmed-low-yield",
            conforming_pass_count=2,
            failed_or_malformed_pass_count=0,
        )
        expected_checkpoint_coverage = {
            key: value for key, value in coverage.items()
            if key != "evidence_status"
        }

        def audit_should_not_run(*_a, budget_report=None, **_kw):
            if budget_report is not None:
                budget_report.update(
                    {
                        "conforming_pass_count": 99,
                        "failed_or_malformed_pass_count": 99,
                    }
                )
            return []

        monkeypatch.setattr(
            review_module, "collect_deterministic_findings", lambda *_a, **_kw: []
        )
        monkeypatch.setattr(
            review_module, "collect_self_consistency_findings", lambda *_a, **_kw: []
        )
        monkeypatch.setattr(
            review_module, "audit_plan_until_stable", audit_should_not_run
        )
        args = build_parser().parse_args(
            tmp_repo.argv(
                "completeness-audit", "demo", "--iterate", "--yes",
                "--max-iterations", "1",
            )
        )
        ctx = _load_context(args)
        plan = parse_plan(plan_path)
        bundle_status, audit_stage = _hoisted_bundle(plan, plan_path, tmp_repo.root)
        outcome = _run_iterate_convergence_loop(
            plan,
            plan_path,
            ctx,
            args,
            IterativeBudget(enabled=True, max_iterations=1),
            bundle_status=bundle_status,
            audit_stage=audit_stage,
            reused_audit_recs=[],
            reused_audit_coverage=coverage,
        )
        assert outcome.budget == expected_checkpoint_coverage
        assert outcome.audit_incomplete is False

    def test_audit_incomplete_omits_measured_empty_bar_set(
        self, tmp_repo, monkeypatch
    ) -> None:
        import plan_tool.cli.completeness_cmd as completeness_cmd

        plan, path = _write_and_parse(tmp_repo, _CLEAN_STEPS)
        corr = _rec("medium", source="plan-correctness")
        legacy_coverage = {
            "evidence_status": "observed",
            "budget_limited": False,
            "passes_used": 1,
            "cap": 1,
            "recommendation_kind": None,
            "recommended_passes": None,
            "recommendation_advice": None,
            "confirmation_kind": "confirmed-dry",
        }
        monkeypatch.setattr(
            completeness_cmd,
            "_sample_conceptual_audit",
            lambda *_a, **_kw: [corr],
        )
        bundle_status, audit_stage = _hoisted_bundle(plan, path, tmp_repo.root)
        finalize_completeness_run(
            plan,
            path,
            SimpleNamespace(repo_root=tmp_repo.root),
            SimpleNamespace(
                name="1-sectioned", json=False, fail_on_findings=False, commit=False
            ),
            budget=IterativeBudget(enabled=False),
            outcome=_IterateOutcome(),
            reused_audit_recs=[corr],
            reused_audit_coverage=legacy_coverage,
            code_drifted=False,
            audit_passes=1,
            audit_dry_rounds=1,
            bundle_status=bundle_status,
            audit_stage=audit_stage,
        )
        from plan_tool.cli.completeness_cmd import _conceptual_bar_from_audit_recs

        bar_ids, incomplete = _conceptual_bar_from_audit_recs(
            [corr], audit_stage=audit_stage, coverage=legacy_coverage
        )
        assert incomplete is True
        assert bar_ids == ()
        assert compute_conceptual_bar_blocking_ids(
            [corr], audit_stage=audit_stage
        ) != ()


def _bar_steering_budget() -> dict:
    return {
        "budget_limited": False,
        "passes_used": 1,
        "cap": 1,
        "recommendation_kind": None,
        "recommended_passes": None,
        "recommendation_advice": None,
        "confirmation_kind": "confirmed-dry",
        "conforming_pass_count": 1,
        "failed_or_malformed_pass_count": 0,
    }


def _iterate_loop_args(tmp_repo, *, max_iterations: int = 1):
    from plan_tool.cli.app import build_parser
    from plan_tool.cli.context import _load_context

    args = build_parser().parse_args(
        tmp_repo.argv(
            "completeness-audit", "demo", "--iterate", "--yes",
            "--max-iterations", str(max_iterations),
        )
    )
    return args, _load_context(args)


def _stub_iterate_collectors(monkeypatch, *, det=None, sc=None) -> None:
    from plan_tool import review as review_module

    monkeypatch.setattr(
        review_module,
        "collect_deterministic_findings",
        lambda *_a, **_kw: list(det or []),
    )
    monkeypatch.setattr(
        review_module,
        "collect_self_consistency_findings",
        lambda *_a, **_kw: list(sc or []),
    )


class TestBarSteeringMidRun:
    """Step 5 — conceptual bar steers iterate loop stop kind + remedies."""

    def _run(
        self,
        tmp_repo,
        monkeypatch,
        *,
        audit_recs,
        det=None,
        sc=None,
        max_iterations: int = 1,
        reused_audit_recs=None,
        reused_audit_coverage=None,
        plan_path=None,
    ):
        from plan_tool import review as review_module

        if plan_path is None:
            plan_path = tmp_repo.add_plan("1-demo", title="Demo")
            tmp_repo.write_manifest()
        budget = _bar_steering_budget()

        def fake_audit(*_a, budget_report=None, **_kw):
            if budget_report is not None:
                budget_report.update(budget)
            return list(audit_recs)

        _stub_iterate_collectors(monkeypatch, det=det, sc=sc)
        if reused_audit_recs is None:
            monkeypatch.setattr(
                review_module, "audit_plan_until_stable", fake_audit
            )
        else:
            monkeypatch.setattr(
                review_module,
                "audit_plan_until_stable",
                lambda *_a, **_kw: (_ for _ in ()).throw(
                    AssertionError("reuse must skip live audit")
                ),
            )
        args, ctx = _iterate_loop_args(tmp_repo, max_iterations=max_iterations)
        plan = parse_plan(plan_path)
        bundle_status, audit_stage = _hoisted_bundle(
            plan, plan_path, tmp_repo.root,
        )
        return _run_iterate_convergence_loop(
            plan,
            plan_path,
            ctx,
            args,
            IterativeBudget(enabled=True, max_iterations=max_iterations),
            bundle_status=bundle_status,
            audit_stage=audit_stage,
            reused_audit_recs=reused_audit_recs,
            reused_audit_coverage=reused_audit_coverage,
        ), plan_path

    def test_iteration_zero_converged_with_bar_blockers_becomes_terminal_hand_apply(
        self, tmp_repo, monkeypatch,
    ) -> None:
        corr = _rec("medium", source="plan-correctness")
        outcome, _ = self._run(tmp_repo, monkeypatch, audit_recs=[corr])
        assert outcome.stop_reason == "terminal_hand_apply"
        assert outcome.stop_reason != "converged"

    def test_no_blocking_findings_with_conceptual_bar_blockers_remapped(
        self, tmp_repo, monkeypatch,
    ) -> None:
        from plan_tool import review as review_module
        from plan_tool.launcher import ApplyFindingResult

        corr = _rec("medium", source="plan-correctness")
        body_issue = Recommendation(
            id="body-1",
            source="body-completeness",
            severity="medium",
            step_id=None,
            title="missing risks",
            body="add ## Risks section",
        )
        info_issue = Recommendation(
            id="info-1",
            source="body-completeness",
            severity="info",
            step_id=None,
            title="nit",
            body="minor",
        )
        call_count = [0]

        def fake_det(*_a, **_kw):
            call_count[0] += 1
            return [body_issue] if call_count[0] == 1 else [info_issue]

        monkeypatch.setattr(
            review_module, "collect_deterministic_findings", fake_det
        )
        monkeypatch.setattr(
            review_module, "collect_self_consistency_findings", lambda *_a, **_kw: []
        )

        def fake_apply(plan_path_arg, **kwargs):
            return ApplyFindingResult(
                step_id=None,
                exit_code=0,
                verdict="APPLIED",
                summary="fixed",
                diff_text="",
                pre_snapshot={plan_path_arg: plan_path_arg.read_text()},
                stdout="",
            )

        monkeypatch.setattr(
            "plan_tool.launcher.apply_finding", fake_apply,
        )
        outcome, _ = self._run(
            tmp_repo, monkeypatch, audit_recs=[corr], max_iterations=3,
        )
        assert outcome.stop_reason == "terminal_hand_apply"

    def test_all_auto_apply_deferred_with_bar_blockers_remapped(
        self, tmp_repo, monkeypatch,
    ) -> None:
        corr = _rec("medium", source="plan-correctness")
        deferred = _rec(
            "medium",
            source="body-completeness",
            impact="low",
            complexity="high",
        )
        outcome, _ = self._run(
            tmp_repo, monkeypatch, audit_recs=[corr], det=[deferred],
        )
        assert outcome.stop_reason == "terminal_hand_apply"
        assert outcome.stop_reason != "all_auto_apply_findings_deferred"

    def test_converged_when_bar_clear_unchanged(
        self, tmp_repo, monkeypatch,
    ) -> None:
        comp = _rec("medium", source="plan-completeness")
        outcome, _ = self._run(tmp_repo, monkeypatch, audit_recs=[comp])
        assert outcome.stop_reason == "converged"

    def test_max_iterations_not_remapped_when_bar_blocks(
        self, tmp_repo, monkeypatch,
    ) -> None:
        from plan_tool import review as review_module
        from plan_tool.cli.app import build_parser
        from plan_tool.cli.context import _load_context
        from plan_tool.launcher import ApplyFindingResult

        plan_path = tmp_repo.add_plan("1-demo", title="Demo")
        tmp_repo.write_manifest()
        corr = _rec("medium", source="plan-correctness")
        body_issue = Recommendation(
            id="body-1",
            source="body-completeness",
            severity="medium",
            step_id=None,
            title="missing risks",
            body="add ## Risks section",
        )
        budget = _bar_steering_budget()

        def fake_audit(*_a, budget_report=None, **_kw):
            if budget_report is not None:
                budget_report.update(budget)
            return [corr]

        monkeypatch.setattr(review_module, "audit_plan_until_stable", fake_audit)
        monkeypatch.setattr(
            review_module,
            "collect_deterministic_findings",
            lambda *_a, **_kw: [body_issue],
        )
        monkeypatch.setattr(
            review_module, "collect_self_consistency_findings", lambda *_a, **_kw: []
        )

        def fake_apply(plan_path_arg, **kwargs):
            return ApplyFindingResult(
                step_id=None,
                exit_code=0,
                verdict="NOT-APPLICABLE",
                summary="still open",
                diff_text="",
                pre_snapshot={plan_path_arg: plan_path_arg.read_text()},
                stdout="",
            )

        monkeypatch.setattr("plan_tool.launcher.apply_finding", fake_apply)
        args, ctx = _iterate_loop_args(tmp_repo, max_iterations=1)
        plan = parse_plan(plan_path)
        bundle_status, audit_stage = _hoisted_bundle(
            plan, plan_path, tmp_repo.root,
        )
        outcome = _run_iterate_convergence_loop(
            plan,
            plan_path,
            ctx,
            args,
            IterativeBudget(enabled=True, max_iterations=1),
            bundle_status=bundle_status,
            audit_stage=audit_stage,
        )
        assert outcome.stop_reason == "max_iterations"

    def test_bare_correctness_bar_blocker_prints_session_edit_hint(
        self, tmp_repo, monkeypatch, capsys,
    ) -> None:
        corr = _rec("medium", source="plan-correctness")
        self._run(tmp_repo, monkeypatch, audit_recs=[corr])
        err = capsys.readouterr().err
        assert "session-directed plan edit" in err

    def test_bare_high_completeness_bar_blocker_prints_hand_edit(
        self, tmp_repo, monkeypatch, capsys,
    ) -> None:
        comp = _rec("high", source="plan-completeness")
        self._run(tmp_repo, monkeypatch, audit_recs=[comp])
        err = capsys.readouterr().err
        assert "manual plan edit" in err
        assert "informational until" not in err
        assert "completeness-apply" not in err

    def test_bare_medium_completeness_outside_bar_informational_only(
        self, tmp_repo, monkeypatch, capsys,
    ) -> None:
        comp = _rec("medium", source="plan-completeness")
        outcome, _ = self._run(tmp_repo, monkeypatch, audit_recs=[comp])
        err = capsys.readouterr().err
        assert outcome.stop_reason == "converged"
        assert "informational until" in err
        assert "terminal_hand_apply" not in (outcome.stop_reason or "")

    def test_detail_completeness_bar_blocker_prints_hand_edit_guidance(
        self, tmp_repo, monkeypatch, capsys,
    ) -> None:
        plan_path = tmp_repo.add_plan("1-demo", title="Demo")
        _attach_minimal_detail(tmp_repo, plan_path)
        tmp_repo.write_manifest()
        comp = _rec("high", source="plan-completeness")
        self._run(
            tmp_repo, monkeypatch, audit_recs=[comp], plan_path=plan_path,
        )
        err = capsys.readouterr().err
        assert "manual plan edit" in err

    def test_iterate_reuse_with_bar_blockers_remaps_terminal_hand_apply(
        self, tmp_repo, monkeypatch,
    ) -> None:
        corr = _rec("medium", source="plan-correctness")
        coverage = _observed_audit_coverage(
            budget_limited=False,
            passes_used=1,
            cap=1,
            confirmation_kind="confirmed-dry",
        )
        outcome, _ = self._run(
            tmp_repo,
            monkeypatch,
            audit_recs=[corr],
            reused_audit_recs=[corr],
            reused_audit_coverage=coverage,
        )
        assert outcome.stop_reason == "terminal_hand_apply"

    def test_audit_incomplete_skips_bar_remap(
        self, tmp_repo, monkeypatch,
    ) -> None:
        corr = _rec("medium", source="plan-correctness")
        legacy_coverage = {
            "evidence_status": "observed",
            "budget_limited": False,
            "passes_used": 1,
            "cap": 1,
            "recommendation_kind": None,
            "recommended_passes": None,
            "recommendation_advice": None,
            "confirmation_kind": "confirmed-dry",
        }
        outcome, _ = self._run(
            tmp_repo,
            monkeypatch,
            audit_recs=[corr],
            reused_audit_recs=[corr],
            reused_audit_coverage=legacy_coverage,
        )
        assert outcome.audit_incomplete is True
        assert outcome.stop_reason == "converged"
        assert outcome.stop_reason != "terminal_hand_apply"

    def test_conceptual_ids_never_join_current_finding_ids(
        self, tmp_repo, monkeypatch,
    ) -> None:
        from plan_tool import convergence as convergence_module

        corr = _rec("medium", source="plan-correctness")
        seen: list[frozenset[str]] = []
        orig = convergence_module.should_continue

        def spy(state, **kw):
            seen.append(state.current_finding_ids)
            return orig(state, **kw)

        monkeypatch.setattr(convergence_module, "should_continue", spy)
        outcome, _ = self._run(tmp_repo, monkeypatch, audit_recs=[corr])
        assert outcome.conceptual_bar_blocking_ids == ("plan-correctness-medium",)
        for ids in seen:
            assert ids.isdisjoint(outcome.conceptual_bar_blocking_ids)

    def test_has_blocking_findings_stays_deterministic_only(self) -> None:
        import inspect

        from plan_tool.cli.completeness_phases import _run_iterate_convergence_loop

        src = inspect.getsource(_run_iterate_convergence_loop)
        post_apply = src.split("record_iteration(state", 1)[1]
        post_apply = post_apply.split("state.has_blocking_findings", 1)[1]
        assert "_audit_recs" not in post_apply[:300]

    def test_sc_blocking_still_prints_conceptual_bar_remedies(
        self, tmp_repo, monkeypatch, capsys,
    ) -> None:
        """SC owns stop kind; conceptual bar remedies must still print."""
        corr = _rec("medium", source="plan-correctness")
        orphan = _rec("medium", source="orphaned-deliverable", title="orphan")
        outcome, _ = self._run(
            tmp_repo, monkeypatch, audit_recs=[corr], sc=[orphan],
        )
        err = capsys.readouterr().err
        assert outcome.stop_reason == "manual_fix_blocking_findings"
        assert "self-consistency blocking" in err
        assert "session-directed plan edit" in err
        assert "terminal_hand_apply" not in (outcome.stop_reason or "")
        # One halt, one banner: the SC note owns the halt here (stop_reason
        # is manual_fix_blocking_findings, not terminal_hand_apply), so the
        # conceptual-bar remedy print alongside it must not add a second
        # "completeness iteration halting" header.
        assert err.count("completeness iteration halting") == 1

    def test_deferred_incomplete_high_completeness_not_informational(
        self, tmp_repo, monkeypatch, capsys,
    ) -> None:
        """Incomplete blanks the bar — never call high completeness informational."""
        comp = _rec("high", source="plan-completeness")
        deferred = _rec(
            "medium",
            source="body-completeness",
            impact="low",
            complexity="high",
        )
        legacy_coverage = {
            "evidence_status": "observed",
            "budget_limited": False,
            "passes_used": 1,
            "cap": 1,
            "recommendation_kind": None,
            "recommended_passes": None,
            "recommendation_advice": None,
            "confirmation_kind": "confirmed-dry",
        }
        outcome, _ = self._run(
            tmp_repo,
            monkeypatch,
            audit_recs=[comp],
            det=[deferred],
            reused_audit_recs=[comp],
            reused_audit_coverage=legacy_coverage,
        )
        err = capsys.readouterr().err
        assert outcome.audit_incomplete is True
        assert outcome.stop_reason == "all_auto_apply_findings_deferred"
        assert "informational until" not in err
        assert "did not qualify" in err or "live sample" in err

    def test_deferred_bare_medium_completeness_stays_informational(
        self, tmp_repo, monkeypatch, capsys,
    ) -> None:
        comp = _rec("medium", source="plan-completeness")
        deferred = _rec(
            "medium",
            source="body-completeness",
            impact="low",
            complexity="high",
        )
        outcome, _ = self._run(
            tmp_repo, monkeypatch, audit_recs=[comp], det=[deferred],
        )
        err = capsys.readouterr().err
        assert outcome.stop_reason == "all_auto_apply_findings_deferred"
        assert "informational until" in err
        assert "manual plan edit" not in err


# --- Step 6: convergence loop advisories on completeness stderr ------------


def _advisory_dt(day: int) -> datetime:
    return datetime(2026, 6, day, 9, 0, 0, tzinfo=timezone.utc)


def _advisory_high_impact_rec(
    rec_id: str,
    *,
    anchor: str = "step5-over-pack",
    title: str = "Step 5 packs too much",
) -> Recommendation:
    return Recommendation(
        id=rec_id,
        source="plan-completeness",
        severity="medium",
        step_id=None,
        title=title,
        body="…",
        anchor=anchor,
        impact="high",
    )


def _advisory_correctness_rec(
    rec_id: str,
    *,
    anchor: str = "step5-gap",
    title: str = "Plan contradicts code",
) -> Recommendation:
    return Recommendation(
        id=rec_id,
        source="plan-correctness",
        severity="medium",
        step_id=None,
        title=title,
        body="…",
        anchor=anchor,
    )


def _advisory_mechanism_rec(
    rec_id: str,
    *,
    anchor: str = "serializer-choice",
    title: str = "Select a serializer choice",
) -> Recommendation:
    """A classified bare correctness finding about an internal choice."""
    return Recommendation(
        id=rec_id,
        source="plan-correctness",
        severity="medium",
        step_id=None,
        title=title,
        body="Use a serializer choice for the internal payload.",
        anchor=anchor,
        suggested_action="Specify the serializer choice in detail.",
    )


def _save_advisory_sidecar(
    repo,
    *,
    recs,
    when,
    audit_stage: str = "bare",
    annotations: dict | None = None,
):
    return save_review(
        plan_slug="demo",
        plan_path="plans/1-demo.md",
        repo_root=repo.root,
        report_md="report body\n",
        recommendations=recs,
        annotations=annotations,
        now=when,
        kind="completeness",
        audit_stage=audit_stage,
    )


def _seed_two_impact_recurrence_passes(repo) -> Recommendation:
    seam = _advisory_high_impact_rec("p1")
    for day in (1, 2):
        _save_advisory_sidecar(
            repo,
            recs=[_advisory_high_impact_rec(f"p{day}", anchor=seam.anchor)],
            when=_advisory_dt(day),
        )
    return seam


def _finalize_controlled_audit(
    tmp_repo,
    capsys,
    *,
    resumed_from_sampler_checkpoint: bool,
    json_output: bool,
):
    """Finalize identical evidence with only sampler provenance varied."""
    from plan_tool.review_persistence import AuditInputSnapshot

    plan, path = _write_and_parse(
        tmp_repo, _INTENT_BEARING_STEPS, intent=_PLAN_INTENT,
    )
    snapshot = AuditInputSnapshot.capture(path, tmp_repo.root)
    bundle_status, audit_stage = _hoisted_bundle(plan, path, tmp_repo.root)
    outcome = _IterateOutcome(
        audit_recs=[],
        budget=_qualifying_producer_coverage(),
        audit_input_snapshot=snapshot,
        audit_stage=audit_stage,
        resumed_from_sampler_checkpoint=resumed_from_sampler_checkpoint,
    )
    rc = finalize_completeness_run(
        plan,
        path,
        SimpleNamespace(repo_root=tmp_repo.root),
        SimpleNamespace(
            name="1-sectioned",
            json=json_output,
            fail_on_findings=False,
            commit=False,
        ),
        budget=IterativeBudget(enabled=False),
        outcome=outcome,
        reused_audit_recs=None,
        code_drifted=False,
        audit_passes=1,
        audit_dry_rounds=1,
        bundle_status=bundle_status,
        audit_stage=audit_stage,
        audit_input_snapshot=snapshot,
        sampled_audit_stage=audit_stage,
    )
    assert rc == 0
    output = capsys.readouterr().out
    return outcome, json.loads(output) if json_output else output


def test_resumed_audit_finalization_matches_uninterrupted_qualified_result(
    tmp_repo, capsys,
) -> None:
    """Resume provenance cannot contribute to final-evidence classification."""
    resumed, resumed_output = _finalize_controlled_audit(
        tmp_repo,
        capsys,
        resumed_from_sampler_checkpoint=True,
        json_output=False,
    )
    uninterrupted, uninterrupted_output = _finalize_controlled_audit(
        tmp_repo,
        capsys,
        resumed_from_sampler_checkpoint=False,
        json_output=False,
    )

    assert resumed.qualified_result.as_dict() == uninterrupted.qualified_result.as_dict()
    assert "Audit provenance" in resumed_output
    assert "Audit provenance" not in uninterrupted_output


def test_resumed_audit_finalization_matches_uninterrupted_coverage(
    tmp_repo, capsys,
) -> None:
    """Resume provenance cannot change the public coverage record."""
    resumed, resumed_payload = _finalize_controlled_audit(
        tmp_repo,
        capsys,
        resumed_from_sampler_checkpoint=True,
        json_output=True,
    )
    uninterrupted, uninterrupted_payload = _finalize_controlled_audit(
        tmp_repo,
        capsys,
        resumed_from_sampler_checkpoint=False,
        json_output=True,
    )

    assert resumed.budget == uninterrupted.budget
    assert resumed_payload["coverage"] == uninterrupted_payload["coverage"]


def test_resumed_audit_json_contract_has_no_resume_field(tmp_repo, capsys) -> None:
    """Keep sampler provenance out of the public machine-readable payload."""
    resumed, resumed_payload = _finalize_controlled_audit(
        tmp_repo,
        capsys,
        resumed_from_sampler_checkpoint=True,
        json_output=True,
    )
    uninterrupted, uninterrupted_payload = _finalize_controlled_audit(
        tmp_repo,
        capsys,
        resumed_from_sampler_checkpoint=False,
        json_output=True,
    )

    assert resumed_payload == uninterrupted_payload
    assert "resumed_from_sampler_checkpoint" not in resumed_payload
    assert resumed.qualified_result.as_dict() == resumed_payload["qualified_result"]


def test_qualified_result_precedence_and_advisory_remainder() -> None:
    """No evidence wins before stop mapping; bare non-blocking work is advisory."""
    from plan_tool.cli.completeness_cmd import (
        QUALIFIED_RESULT_ADVISORY,
        QUALIFIED_RESULT_NO_EVIDENCE,
        classify_qualified_audit_result,
    )

    coverage = {
        "budget_limited": False,
        "passes_used": 1,
        "cap": 1,
        "recommendation_kind": None,
        "recommended_passes": None,
        "recommendation_advice": None,
        "confirmation_kind": None,
        "conforming_pass_count": 1,
        "failed_or_malformed_pass_count": 0,
    }
    no_evidence = classify_qualified_audit_result(
        audit_completed=False,
        audit_capture=None,
        audit_stage=None,
        coverage=coverage,
        coverage_is_legacy_unknown=False,
        revision_current=None,
        has_blocking=True,
        stop_reason="halted: drift",
    )
    assert no_evidence.headline == QUALIFIED_RESULT_NO_EVIDENCE
    assert no_evidence.stage == "not-sampled"
    legacy_unknown = classify_qualified_audit_result(
        audit_completed=True,
        audit_capture=SimpleNamespace(revision={"captured": True}),
        audit_stage=STAGE_BARE,
        coverage=coverage,
        coverage_is_legacy_unknown=True,
        revision_current=True,
        has_blocking=False,
        stop_reason="converged",
    )
    assert legacy_unknown.headline == QUALIFIED_RESULT_NO_EVIDENCE
    assert legacy_unknown.coverage == "unknown-legacy"
    advisory = classify_qualified_audit_result(
        audit_completed=True,
        audit_capture=SimpleNamespace(revision={"captured": True}),
        audit_stage=STAGE_BARE,
        coverage=coverage,
        coverage_is_legacy_unknown=False,
        revision_current=True,
        has_blocking=False,
        stop_reason="converged",
        result_bearing_findings=True,
    )
    assert advisory.headline == QUALIFIED_RESULT_ADVISORY


@pytest.mark.parametrize(
    "stop_reason",
    (
        None,
        "converged",
        "no_blocking_findings",
        "terminal_hand_apply",
        "manual_fix_blocking_findings",
        "all_auto_apply_findings_deferred",
        "max_iterations",
        "halted: parse failure",
    ),
)
def test_qualified_result_no_evidence_overrides_every_stop(stop_reason: str | None) -> None:
    """Evidence qualification leads before any iterate-stop interpretation."""
    from plan_tool.cli.completeness_cmd import (
        QUALIFIED_RESULT_NO_EVIDENCE,
        classify_qualified_audit_result,
    )

    captured = SimpleNamespace(revision={"captured": True})
    qualifying = _qualifying_producer_coverage()
    unconfirmed = dict(qualifying, budget_limited=True)
    cases = (
        (
            "not-captured",
            dict(audit_completed=False, audit_capture=None),
            ("not-sampled", "not-sampled", "not-sampled", None),
        ),
        (
            "unconfirmed",
            dict(audit_completed=True, audit_capture=captured, coverage=unconfirmed),
            ("bare", "unconfirmed", "current", captured.revision),
        ),
        (
            "legacy-coverage",
            dict(
                audit_completed=True,
                audit_capture=captured,
                coverage_is_legacy_unknown=True,
            ),
            ("bare", "unknown-legacy", "current", captured.revision),
        ),
        (
            "stale-revision",
            dict(audit_completed=True, audit_capture=captured, revision_current=False),
            ("bare", "confirmed", "stale", captured.revision),
        ),
    )
    base = dict(
        audit_completed=True,
        audit_capture=captured,
        audit_stage=STAGE_BARE,
        coverage=qualifying,
        coverage_is_legacy_unknown=False,
        revision_current=True,
        has_blocking=True,
        stop_reason=stop_reason,
        result_bearing_findings=True,
        finalize_clean=False,
    )

    for label, overrides, qualifiers in cases:
        result = classify_qualified_audit_result(**(base | overrides))
        assert result.headline == QUALIFIED_RESULT_NO_EVIDENCE, label
        assert (
            result.stage,
            result.coverage,
            result.revision_status,
            result.audit_revision,
        ) == qualifiers, label


@pytest.mark.parametrize(
    ("has_blocking", "result_bearing_findings", "finalize_clean", "expected"),
    (
        (True, False, True, "awaiting-human-action"),
        (False, True, True, "advisory-only"),
        (False, False, True, "clean"),
        (False, False, False, "awaiting-human-action"),
    ),
)
def test_qualified_result_audit_only_mapping(
    has_blocking: bool,
    result_bearing_findings: bool,
    finalize_clean: bool,
    expected: str,
) -> None:
    """Qualified audit-only outcomes have one blocking/advisory/clean mapping."""
    from plan_tool.cli.completeness_cmd import classify_qualified_audit_result

    result = classify_qualified_audit_result(
        audit_completed=True,
        audit_capture=SimpleNamespace(revision={"captured": True}),
        audit_stage=STAGE_BARE,
        coverage=_qualifying_producer_coverage(),
        coverage_is_legacy_unknown=False,
        revision_current=True,
        has_blocking=has_blocking,
        stop_reason=None,
        result_bearing_findings=result_bearing_findings,
        finalize_clean=finalize_clean,
    )

    assert result.headline == expected


@pytest.mark.parametrize(
    ("stop_reason", "deferred_recs", "result_bearing_findings", "expected"),
    (
        ("terminal_hand_apply", (), False, "awaiting-human-action"),
        ("manual_fix_blocking_findings", (), False, "awaiting-human-action"),
        ("halted: parse failure", (), False, "awaiting-human-action"),
        ("max_iterations", (), False, "awaiting-human-action"),
        ("all_auto_apply_findings_deferred", (), True, "awaiting-human-action"),
        (
            "all_auto_apply_findings_deferred",
            (
                Recommendation(
                    id="advisory",
                    source="plan-correctness",
                    severity="nit",
                    step_id=1,
                    title="Optional wording",
                    body="Optional wording improvement.",
                ),
            ),
            True,
            "advisory-only",
        ),
        (
            "all_auto_apply_findings_deferred",
            (
                Recommendation(
                    id="material",
                    source="plan-correctness",
                    severity="medium",
                    step_id=1,
                    title="Missing behavior",
                    body="Describe the missing behavior.",
                ),
            ),
            True,
            "awaiting-human-action",
        ),
        ("converged", (), True, "advisory-only"),
        ("no_blocking_findings", (), True, "advisory-only"),
    ),
)
def test_qualified_result_iterate_stop_matrix(
    stop_reason: str,
    deferred_recs: tuple[Recommendation, ...],
    result_bearing_findings: bool,
    expected: str,
) -> None:
    """Every current iterate stop maps deterministically after qualification."""
    from plan_tool.cli.completeness_cmd import classify_qualified_audit_result

    result = classify_qualified_audit_result(
        audit_completed=True,
        audit_capture=SimpleNamespace(revision={"captured": True}),
        audit_stage=STAGE_DETAIL,
        coverage=_qualifying_producer_coverage(),
        coverage_is_legacy_unknown=False,
        revision_current=True,
        has_blocking=False,
        stop_reason=stop_reason,
        deferred_recs=deferred_recs,
        result_bearing_findings=result_bearing_findings,
    )

    assert result.headline == expected


def test_deferred_completeness_requires_human_action_at_every_stage() -> None:
    """Conceptual completeness is never an apply-eligible advisory deferral."""
    from plan_tool.cli.completeness_cmd import (
        QUALIFIED_RESULT_AWAITING_ACTION,
        classify_qualified_audit_result,
    )

    coverage = _qualifying_producer_coverage()
    deferred = Recommendation(
        id="detail-gap",
        source="plan-completeness",
        severity="medium",
        step_id=1,
        title="Detail-stage gap",
        body="Fix the detailed plan.",
    )
    common = dict(
        audit_completed=True,
        audit_capture=SimpleNamespace(revision={"captured": True}),
        coverage=coverage,
        coverage_is_legacy_unknown=False,
        revision_current=True,
        has_blocking=False,
        stop_reason="all_auto_apply_findings_deferred",
        deferred_recs=[deferred],
        conceptual_bar_blocking_ids=(),
        result_bearing_findings=True,
        finalize_clean=True,
    )

    detail = classify_qualified_audit_result(audit_stage="detail", **common)
    bare = classify_qualified_audit_result(audit_stage="bare", **common)

    assert detail.headline == QUALIFIED_RESULT_AWAITING_ACTION
    assert bare.headline == QUALIFIED_RESULT_AWAITING_ACTION


def _seed_two_edit_drift_passes(repo) -> list[Recommendation]:
    gone = _advisory_correctness_rec("gone", anchor="vanished-gap", title="Vanished gap")
    applied = _advisory_correctness_rec("applied", anchor="applied-gap", title="Applied gap")
    _save_advisory_sidecar(
        repo,
        recs=[gone, applied],
        when=_advisory_dt(1),
        annotations={"applied": Annotation(status="applied")},
    )
    _save_advisory_sidecar(
        repo,
        recs=[_advisory_correctness_rec("carry1")],
        when=_advisory_dt(2),
    )
    return [
        _advisory_correctness_rec("new1", anchor="vanished-gap", title="Vanished gap restated"),
        _advisory_correctness_rec("new2", anchor="applied-gap", title="Applied gap restated"),
        _advisory_correctness_rec("new3", anchor="fresh-gap", title="Fresh unrelated gap"),
    ]


def _stub_clean_completeness_audit(monkeypatch) -> None:
    import plan_tool.review

    budget = {
        "budget_limited": False,
        "passes_used": 1,
        "cap": 1,
        "recommendation_kind": None,
        "recommended_passes": None,
        "recommendation_advice": None,
        "confirmation_kind": "confirmed-dry",
        "conforming_pass_count": 1,
        "failed_or_malformed_pass_count": 0,
    }

    def fake_audit(*_args, budget_report=None, **_kwargs):
        if budget_report is not None:
            budget_report.update(budget)
        return []

    monkeypatch.setattr(plan_tool.review, "audit_plan_until_stable", fake_audit)


def _prepare_clean_demo_plan(registered_plan) -> None:
    path = registered_plan.plans_dir / "1-demo.md"
    path.write_text(
        _sectioned_plan_text(_INTENT_BEARING_STEPS, intent=_PLAN_INTENT),
        encoding="utf-8",
    )


class TestCompletenessStderrConvergenceAdvisories:
    """Loop-pattern advisories on completeness stderr."""

    def _run(
        self,
        registered_plan,
        monkeypatch,
        capsys,
        *extra: str,
        audit_recs: list | None = None,
        attach_detail: bool = False,
    ) -> int:
        from plan_tool.cli import main
        import plan_tool.review

        _prepare_clean_demo_plan(registered_plan)
        if attach_detail:
            _attach_minimal_detail(
                registered_plan, registered_plan.plans_dir / "1-demo.md"
            )

        budget = {
            "budget_limited": False,
            "passes_used": 1,
            "cap": 1,
            "recommendation_kind": None,
            "recommended_passes": None,
            "recommendation_advice": None,
            "confirmation_kind": "confirmed-dry",
            "conforming_pass_count": 1,
            "failed_or_malformed_pass_count": 0,
        }

        def fake_audit(*_args, budget_report=None, **_kwargs):
            if budget_report is not None:
                budget_report.update(budget)
            return list(audit_recs or [])

        monkeypatch.setattr(plan_tool.review, "audit_plan_until_stable", fake_audit)
        return main(
            registered_plan.argv(
                "completeness-audit", "demo", "-y", "--no-reuse-audit", *extra
            )
        )

    def test_completeness_stderr_prints_impact_recurrence_when_history_fires(
        self, registered_plan, monkeypatch, capsys
    ) -> None:
        seam = _seed_two_impact_recurrence_passes(registered_plan)
        third = _advisory_high_impact_rec("p3", anchor=seam.anchor)
        rc = self._run(
            registered_plan, monkeypatch, capsys, audit_recs=[third]
        )
        err = capsys.readouterr().err
        assert rc == 0
        assert "High-impact seam recurrence" in err

    def test_completeness_stderr_prints_edit_drift_when_history_fires(
        self, registered_plan, monkeypatch, capsys
    ) -> None:
        third_pass = _seed_two_edit_drift_passes(registered_plan)
        rc = self._run(
            registered_plan, monkeypatch, capsys, audit_recs=third_pass
        )
        err = capsys.readouterr().err
        assert rc == 0
        assert "Edit drift" in err

    def test_completeness_stderr_prints_standalone_mechanism_advisory_after_one_completed_bare_pass(
        self, registered_plan, monkeypatch, capsys
    ) -> None:
        rc = self._run(
            registered_plan,
            monkeypatch,
            capsys,
            audit_recs=[_advisory_mechanism_rec("mechanism")],
        )
        err = capsys.readouterr().err

        assert rc == 0
        assert "Bare-plan mechanism advisory" in err

    def test_completeness_stderr_combines_same_current_mechanism_and_edit_drift(
        self, registered_plan, monkeypatch, capsys
    ) -> None:
        _save_advisory_sidecar(
            registered_plan,
            recs=[
                _advisory_mechanism_rec("gone", anchor="serializer-choice"),
                _advisory_correctness_rec(
                    "applied", anchor="applied-gap", title="Applied gap"
                ),
            ],
            when=_advisory_dt(1),
            annotations={"applied": Annotation(status="applied")},
        )
        _save_advisory_sidecar(
            registered_plan,
            recs=[_advisory_correctness_rec("carry", anchor="carry-gap")],
            when=_advisory_dt(2),
        )
        rc = self._run(
            registered_plan,
            monkeypatch,
            capsys,
            audit_recs=[
                _advisory_mechanism_rec("new-mechanism", anchor="serializer-choice"),
                _advisory_correctness_rec(
                    "new-drift", anchor="applied-gap", title="Applied gap restated"
                ),
                _advisory_correctness_rec("fresh", anchor="fresh-gap"),
            ],
        )
        err = capsys.readouterr().err

        assert rc == 0
        assert "Bare-plan mechanism and edit-drift advisory" in err
        assert "Select a serializer choice" in err
        assert "\n⚠ Bare-plan mechanism advisory:" not in err
        assert 'Matched findings: "Applied gap restated".' in err

    def test_completeness_stderr_keeps_unmatched_mechanism_and_edit_drift_advice_separate(
        self, registered_plan, monkeypatch, capsys
    ) -> None:
        _save_advisory_sidecar(
            registered_plan,
            recs=[
                _advisory_mechanism_rec("gone", anchor="combined-choice"),
                _advisory_correctness_rec(
                    "gone-drift", anchor="drift-gap", title="Prior drift gap"
                ),
            ],
            when=_advisory_dt(1),
        )
        _save_advisory_sidecar(
            registered_plan,
            recs=[_advisory_correctness_rec("carry", anchor="carry-gap")],
            when=_advisory_dt(2),
        )
        rc = self._run(
            registered_plan,
            monkeypatch,
            capsys,
            audit_recs=[
                _advisory_mechanism_rec("combined", anchor="combined-choice"),
                _advisory_mechanism_rec(
                    "standalone", anchor="standalone-choice", title="Select a carrier"
                ),
                _advisory_correctness_rec(
                    "drift-only", anchor="drift-gap", title="Restated drift gap"
                ),
            ],
        )
        err = capsys.readouterr().err

        assert rc == 0
        assert "Bare-plan mechanism and edit-drift advisory" in err
        assert "Bare-plan mechanism advisory" in err
        assert "Select a carrier" in err
        assert "Edit drift" in err
        assert 'Matched findings: "Restated drift gap".' in err

    def test_completeness_stderr_omits_mechanism_advisory_for_detail_stage(
        self, registered_plan, monkeypatch, capsys
    ) -> None:
        rc = self._run(
            registered_plan,
            monkeypatch,
            capsys,
            audit_recs=[_advisory_mechanism_rec("mechanism")],
            attach_detail=True,
        )
        err = capsys.readouterr().err

        assert rc == 0
        assert "Bare-plan mechanism" not in err

    def test_completeness_stderr_prints_both_advisories_when_both_fire(
        self, registered_plan, monkeypatch, capsys
    ) -> None:
        seam = _advisory_high_impact_rec("p1")
        gone = _advisory_correctness_rec("gone", anchor="vanished-gap", title="Vanished gap")
        applied = _advisory_correctness_rec("applied", anchor="applied-gap", title="Applied gap")
        _save_advisory_sidecar(
            registered_plan,
            recs=[gone, applied, seam],
            when=_advisory_dt(1),
            annotations={"applied": Annotation(status="applied")},
        )
        _save_advisory_sidecar(
            registered_plan,
            recs=[
                _advisory_correctness_rec("carry1"),
                _advisory_high_impact_rec("p2", anchor=seam.anchor),
            ],
            when=_advisory_dt(2),
        )
        third = [
            _advisory_correctness_rec("new1", anchor="vanished-gap", title="Vanished gap restated"),
            _advisory_correctness_rec("new2", anchor="applied-gap", title="Applied gap restated"),
            _advisory_correctness_rec("new3", anchor="fresh-gap", title="Fresh unrelated gap"),
            _advisory_high_impact_rec("p3", anchor=seam.anchor),
        ]
        rc = self._run(
            registered_plan, monkeypatch, capsys, audit_recs=third
        )
        err = capsys.readouterr().err
        assert rc == 0
        assert "High-impact seam recurrence" in err
        assert "Edit drift" in err

    def test_completeness_stderr_silent_when_classifiers_do_not_fire(
        self, registered_plan, monkeypatch, capsys
    ) -> None:
        seam = _advisory_high_impact_rec("p1")
        _save_advisory_sidecar(
            registered_plan,
            recs=[seam],
            when=_advisory_dt(1),
        )
        _save_advisory_sidecar(
            registered_plan,
            recs=[_advisory_high_impact_rec("p2", anchor=seam.anchor)],
            when=_advisory_dt(2),
        )
        rc = self._run(registered_plan, monkeypatch, capsys)
        err = capsys.readouterr().err
        assert rc == 0
        assert "High-impact seam recurrence" not in err
        assert "Edit drift" not in err


    def test_completeness_stderr_skips_when_sidecar_not_written(
        self, registered_plan, monkeypatch, capsys
    ) -> None:
        from plan_tool.cli import main

        mechanism = _advisory_mechanism_rec("mechanism")
        assert self._run(
            registered_plan, monkeypatch, capsys, audit_recs=[mechanism]
        ) == 0
        assert "Bare-plan mechanism" in capsys.readouterr().err

        _stub_clean_completeness_audit(monkeypatch)
        rc = main(
            registered_plan.argv(
                "completeness-audit", "demo", "-y", "--reuse-audit"
            )
        )
        err = capsys.readouterr().err
        assert rc == 0
        assert "reusing saved conceptual audit" in err
        assert "Bare-plan mechanism" not in err

    def test_completeness_advisories_do_not_change_exit_code(
        self, registered_plan, monkeypatch, capsys
    ) -> None:
        seam = _seed_two_impact_recurrence_passes(registered_plan)
        third = _advisory_high_impact_rec("p3", anchor=seam.anchor)
        rc = self._run(
            registered_plan, monkeypatch, capsys, audit_recs=[third]
        )
        assert rc == 0
        capsys.readouterr()

        rc_fail = self._run(
            registered_plan,
            monkeypatch,
            capsys,
            "--fail-on-findings",
            audit_recs=[third],
        )
        assert rc_fail == 0
        assert "High-impact seam recurrence" in capsys.readouterr().err

    def test_completeness_mechanism_advisory_does_not_change_iterate_stop_reason(
        self, tmp_repo, monkeypatch, capsys
    ) -> None:
        from plan_tool.cli.app import build_parser
        from plan_tool.cli.context import _load_context
        from plan_tool.parser import parse_plan

        plan_path = tmp_repo.add_plan("1-demo", title="Demo")
        path = plan_path
        path.write_text(
            _sectioned_plan_text(_INTENT_BEARING_STEPS, intent=_PLAN_INTENT),
            encoding="utf-8",
        )
        tmp_repo.write_manifest()

        budget = {
            "budget_limited": False,
            "passes_used": 1,
            "cap": 1,
            "recommendation_kind": None,
            "recommended_passes": None,
            "recommendation_advice": None,
            "confirmation_kind": "confirmed-dry",
            "conforming_pass_count": 1,
            "failed_or_malformed_pass_count": 0,
        }

        mechanism = _advisory_mechanism_rec("mechanism")
        unlabelled = dataclasses.replace(
            mechanism,
            title="Clarify the plan outcome",
            body="Clarify the observable outcome before detail authoring.",
            suggested_action="State the outcome in the plan body.",
        )

        def fake_control_audit(*_args, budget_report=None, **_kwargs):
            if budget_report is not None:
                budget_report.update(budget)
            return [unlabelled]

        def fake_advisory_audit(*_args, budget_report=None, **_kwargs):
            if budget_report is not None:
                budget_report.update(budget)
            return [mechanism]

        import plan_tool.review

        monkeypatch.setattr(
            plan_tool.review, "collect_deterministic_findings", lambda *_a, **_kw: []
        )
        monkeypatch.setattr(
            plan_tool.review, "collect_self_consistency_findings", lambda *_a, **_kw: []
        )
        monkeypatch.setattr(
            plan_tool.review, "audit_plan_until_stable", fake_control_audit
        )

        args = build_parser().parse_args(
            tmp_repo.argv(
                "completeness-audit",
                "demo",
                "--iterate",
                "-y",
                "--max-iterations",
                "1",
                "--no-reuse-audit",
            )
        )
        ctx = _load_context(args)
        plan = parse_plan(plan_path)
        bundle_status, audit_stage = _hoisted_bundle(plan, plan_path, tmp_repo.root)
        control_outcome = _run_iterate_convergence_loop(
            plan,
            plan_path,
            ctx,
            args,
            IterativeBudget(enabled=True, max_iterations=1),
            bundle_status=bundle_status,
            audit_stage=audit_stage,
        )

        monkeypatch.setattr(
            plan_tool.review, "audit_plan_until_stable", fake_advisory_audit
        )
        advisory_outcome = _run_iterate_convergence_loop(
            plan,
            plan_path,
            ctx,
            args,
            IterativeBudget(enabled=True, max_iterations=1),
            bundle_status=bundle_status,
            audit_stage=audit_stage,
        )

        from plan_tool.cli import main

        advisory_rc = main(
            tmp_repo.argv(
                "completeness-audit",
                "demo",
                "--iterate",
                "-y",
                "--max-iterations",
                "1",
                "--no-reuse-audit",
            )
        )
        advisory_err = capsys.readouterr().err
        assert advisory_rc == 0
        assert "Bare-plan mechanism" in advisory_err
        assert advisory_outcome.stop_reason == control_outcome.stop_reason


    def test_completeness_mechanism_advisory_does_not_change_audit_only_rc_or_fail_on_findings(
        self, registered_plan, monkeypatch, capsys
    ) -> None:
        import plan_tool.cli.completeness_cmd as completeness_cmd

        mechanism = _advisory_mechanism_rec("mechanism")
        emit_advisories = completeness_cmd._emit_convergence_loop_advisories
        monkeypatch.setattr(
            completeness_cmd, "_emit_convergence_loop_advisories", lambda *_a, **_kw: None
        )
        control_rc = self._run(
            registered_plan, monkeypatch, capsys, audit_recs=[mechanism]
        )
        assert "Bare-plan mechanism" not in capsys.readouterr().err

        monkeypatch.setattr(
            completeness_cmd, "_emit_convergence_loop_advisories", emit_advisories
        )
        advisory_rc = self._run(
            registered_plan, monkeypatch, capsys, audit_recs=[mechanism]
        )
        err = capsys.readouterr().err
        assert advisory_rc == control_rc == 0
        assert "Bare-plan mechanism" in err

        monkeypatch.setattr(
            completeness_cmd, "_emit_convergence_loop_advisories", lambda *_a, **_kw: None
        )
        control_fail_rc = self._run(
            registered_plan,
            monkeypatch,
            capsys,
            "--fail-on-findings",
            audit_recs=[mechanism],
        )
        capsys.readouterr()

        monkeypatch.setattr(
            completeness_cmd, "_emit_convergence_loop_advisories", emit_advisories
        )
        advisory_fail_rc = self._run(
            registered_plan,
            monkeypatch,
            capsys,
            "--fail-on-findings",
            audit_recs=[mechanism],
        )
        assert advisory_fail_rc == control_fail_rc == 1
        assert "Bare-plan mechanism" in capsys.readouterr().err


# The 18 --iterate-loop support helpers step 1 of the cli-layering plan moved
# out of completeness_cmd.py into completeness_phases.py. Step 2 then moved
# the loop itself (their sole remaining caller for 6 of the 18) alongside
# them, so those 6 are no longer re-imported into completeness_cmd.py at
# all; the other 12 still have a direct caller in completeness_cmd.py
# (cmd_completeness / finalize_completeness_run / cmd_completeness_apply /
# _resolve_audit_reuse / _completeness_has_blocking_findings) and stay
# re-imported there as bare names.
_RELOCATED_ITERATE_HELPER_NAMES = (
    "_fmt_finding_counts",
    "_finding_progress_label",
    "_effective_audit_passes",
    "_sampled_bundle_status",
    "_coverage_input_from_reusable_audit",
    "_conceptual_bar_from_audit_recs",
    "_warn_if_audit_incomplete",
    "compute_conceptual_bar_blocking_ids",
    "_warn_audit_incomplete",
    "_split_conceptual_recs",
)
# The 6 loop-only helpers: moved with the loop in step 2, so
# completeness_cmd.py no longer has these as attributes at all.
_LOOP_ONLY_RELOCATED_HELPER_NAMES = (
    "_sc_manual_fix_note",
    "_remap_iterate_stop_for_conceptual_bar",
    "_conceptual_bar_remedy_lines",
    "_print_conceptual_bar_stop_remedies",
    "_print_all_auto_apply_deferred_halt_message",
    "_conceptual_completeness_manual_fix_note",
)
# _resolution_for_verdict's last completeness_cmd.py caller was the
# completeness-apply dispatch tail (not the --iterate loop); step 5 moved
# that tail into completeness_phases.py, so completeness_cmd.py has no
# reason left to re-import it either -- same end state as the loop-only
# helpers above, different mover.
_APPLY_WALK_ONLY_RELOCATED_HELPER_NAMES = (
    "_resolution_for_verdict",
)


class TestRelocatedIterateHelperOwnership:
    """Pins which module owns the 19 --iterate-loop/apply-walk helpers
    relocated by steps 1-2 and 5 of the cli-layering plan: they are DEFINED
    in ``completeness_phases.py``. 11 of the 19 are also RE-IMPORTED (bare
    name) into ``completeness_cmd.py`` for a surviving direct caller there;
    the other 8 (6 loop-only from step 2, plus ``_resolution_for_verdict``
    from step 5) are no longer attributes of ``completeness_cmd`` at all."""

    def test_relocated_iterate_helpers_are_defined_in_completeness_phases(
        self,
    ) -> None:
        import plan_tool.cli.completeness_cmd as completeness_cmd
        import plan_tool.cli.completeness_phases as completeness_phases

        for name in _RELOCATED_ITERATE_HELPER_NAMES:
            phases_fn = getattr(completeness_phases, name)
            cmd_fn = getattr(completeness_cmd, name)
            # Checking __module__ through BOTH modules is what proves
            # completeness_cmd RE-IMPORTS the name rather than redefining
            # it -- a stray leftover `def` in completeness_cmd would report
            # its own module here and fail this check even though every
            # call site still resolves the name successfully.
            assert phases_fn.__module__ == "plan_tool.cli.completeness_phases", name
            assert cmd_fn.__module__ == "plan_tool.cli.completeness_phases", name
            assert cmd_fn is phases_fn, name

    def test_loop_only_helpers_are_defined_in_completeness_phases_only(
        self,
    ) -> None:
        import plan_tool.cli.completeness_cmd as completeness_cmd
        import plan_tool.cli.completeness_phases as completeness_phases

        for name in _LOOP_ONLY_RELOCATED_HELPER_NAMES:
            phases_fn = getattr(completeness_phases, name)
            assert phases_fn.__module__ == "plan_tool.cli.completeness_phases", name
            # Their only caller (the loop) moved into completeness_phases.py
            # alongside them in step 2, so completeness_cmd.py has no reason
            # left to re-import them -- a stray re-import here would be dead
            # weight this check would miss if it only asserted presence.
            assert not hasattr(completeness_cmd, name), name

    def test_apply_walk_only_helpers_are_defined_in_completeness_phases_only(
        self,
    ) -> None:
        import plan_tool.cli.completeness_cmd as completeness_cmd
        import plan_tool.cli.completeness_phases as completeness_phases

        for name in _APPLY_WALK_ONLY_RELOCATED_HELPER_NAMES:
            phases_fn = getattr(completeness_phases, name)
            assert phases_fn.__module__ == "plan_tool.cli.completeness_phases", name
            # Its only remaining caller (the completeness-apply dispatch
            # tail) moved into completeness_phases.py in step 5, so
            # completeness_cmd.py has no reason left to re-import it.
            assert not hasattr(completeness_cmd, name), name

    def test_run_iterate_convergence_loop_is_defined_in_completeness_phases(
        self,
    ) -> None:
        """Step 2 of the cli-layering plan moves the ``--iterate`` loop
        itself (not just its support helpers) into completeness_phases.py.
        ``cmd_completeness`` reaches it through a qualified module reference
        (``completeness_phases._run_iterate_convergence_loop``), not a bare
        re-imported name -- unlike the 12-name group above, completeness_cmd
        never binds this name as its own attribute at all."""
        import plan_tool.cli.completeness_cmd as completeness_cmd
        import plan_tool.cli.completeness_phases as completeness_phases

        assert (
            completeness_phases._run_iterate_convergence_loop.__module__
            == "plan_tool.cli.completeness_phases"
        )
        # completeness_cmd reaches the loop only through its qualified
        # `completeness_phases` module reference -- checking through BOTH
        # paths proves the call site really resolves through that module
        # attribute rather than a stray local re-definition or re-import.
        assert (
            completeness_cmd.completeness_phases._run_iterate_convergence_loop
            is completeness_phases._run_iterate_convergence_loop
        )
        assert not hasattr(completeness_cmd, "_run_iterate_convergence_loop")

    def test_completeness_phases_source_never_imports_completeness_cmd(
        self,
    ) -> None:
        # Mechanically checks completeness_phases.py's own module docstring
        # claim that the import edge is one-directional (completeness_cmd ->
        # completeness_phases), matching this repo's existing leaf-import
        # idiom (source-text scan, as in
        # tests/test_rate_limit_loop.py::test_leaf_has_no_first_party_runtime_import).
        import plan_tool.cli.completeness_phases as completeness_phases

        src = Path(inspect.getfile(completeness_phases))
        text = src.read_text(encoding="utf-8")
        import_lines = [
            line for line in text.splitlines()
            if re.match(r"^\s*(from|import)\s", line)
        ]
        offending = [line for line in import_lines if "completeness_cmd" in line]
        assert not offending, offending


# --- Step 3: the merged next-steps block offers `run` only on an empty set --

_EMPTY_SET = "empty-set"
_NON_EMPTY_SET = "non-empty-set"
_INCOMPLETE = "incomplete"
_ABSENT = "absent"
_VERDICT_STATES = [_EMPTY_SET, _NON_EMPTY_SET, _INCOMPLETE, _ABSENT]


def _verdict_for(state: str):
    from plan_tool.completeness_report import blocking_verdict_from_gate

    if state == _EMPTY_SET:
        return blocking_verdict_from_gate([])
    if state == _NON_EMPTY_SET:
        return blocking_verdict_from_gate(["gap-1"])
    if state == _INCOMPLETE:
        return blocking_verdict_from_gate([], untrusted_cause=UNTRUSTED_TRANSIENT)
    return None


class TestAuthoringMergedBlockGatesRunOnBlockingVerdict:
    """The detail/split/merge ``Next steps:`` block reads the tail's structured
    blocking verdict, never the printed command text."""

    @staticmethod
    def _drive(tmp_repo, monkeypatch, capsys, command, state, *,
               tail_next_steps=(), tail_raises=False, no_completeness=False,
               tail_current=False, bare=False, extra_argv=()):
        import plan_tool.cli.app as app
        import plan_tool.cli.authoring as authoring
        from plan_tool.cli import main
        from plan_tool.detail import DetailResult, MergeResult, SplitResult

        root = tmp_repo.root

        def result(step_id: int) -> DetailResult:
            return DetailResult(
                step_id=step_id, output_path=root / f"{step_id}-x.md", written=True
            )

        monkeypatch.setattr(
            authoring, "generate_detail", lambda *_a, **_k: [result(1)]
        )
        monkeypatch.setattr(
            authoring,
            "split_step",
            lambda _p, *, target_id, new_titles, **_k: SplitResult(
                target_id=target_id,
                original_title="Only step",
                new_ids=[1, 2],
                new_titles=list(new_titles),
                detail_results=[result(1)],
            ),
        )
        monkeypatch.setattr(
            authoring,
            "merge_steps",
            lambda _p, *, merge_ids, **_k: MergeResult(
                merged_id=3,
                merged_title="Merged",
                folded_ids=list(merge_ids),
                folded_titles=["A", "B"],
                detail_results=[result(3)],
            ),
        )

        def fake_completeness(a):
            if tail_raises:
                raise RuntimeError("audit exploded")
            a._next_steps_sink.extend(tail_next_steps)
            verdict = _verdict_for(state)
            if verdict is not None:
                a._blocking_verdict_sink.append(verdict)
            if tail_current:
                # The audit hands back the bundle status it judged; the
                # bundle's bareness is the test's input.
                a._bundle_status_sink.append(SimpleNamespace(is_bare=bare))
            return 0

        monkeypatch.setattr(app, "cmd_completeness", fake_completeness)
        if tail_current:
            # The final result proves the artifacts on disk; the bundle's
            # bareness is the test's input (the generators here write nothing).
            monkeypatch.setattr(
                authoring, "_tail_result_freshness",
                lambda *_a, **_k: "current",
            )
        argv = {
            "detail": ["detail", "demo"],
            "split": ["split", "demo", "--step", "1", "--into", "A",
                      "--into", "B"],
            "merge": ["merge", "demo", "--steps", "3", "--steps", "4", "--yes"],
        }[command]
        if no_completeness:
            argv.append("--no-completeness")
        argv.extend(extra_argv)
        assert main(tmp_repo.argv(*argv)) == 0
        return capsys.readouterr().err

    @pytest.mark.parametrize("command", ["detail", "split", "merge"])
    @pytest.mark.parametrize("state", _VERDICT_STATES)
    def test_stage_entry_only_for_empty_blocking_set(
        self, registered_plan, monkeypatch, capsys, command, state
    ) -> None:
        """The one shared stage (`run` for a detailed run-grade bundle) appears
        only for a completed empty set whose tail proves the artifacts."""
        err = self._drive(
            registered_plan, monkeypatch, capsys, command, state,
            tail_current=True,
            tail_next_steps=[("plan-tool completeness-audit demo --iterate", "x")]
            if state != _EMPTY_SET
            else [],
        )
        assert err.count("Next steps:") == 1
        if state == _EMPTY_SET:
            assert err.count("plan-tool run demo") == 1
            assert "plan-tool jira demo" not in err
            assert "plan-tool completeness-audit demo" not in err
        else:
            assert "plan-tool run demo" not in err
            assert "plan-tool completeness-audit demo --iterate" in err
        # reconcile-plan survives every verdict state.
        assert "plan-tool reconcile-plan demo" in err

    @pytest.mark.parametrize("command", ["detail", "split", "merge"])
    @pytest.mark.parametrize("state", _VERDICT_STATES)
    def test_stale_tail_offers_no_stage_beside_the_fresh_audit(
        self, registered_plan, monkeypatch, capsys, command, state
    ) -> None:
        """A tail result that no longer matches the artifacts stands alone as
        the fresh-audit follow-up, even when its verdict was an empty set."""
        err = self._drive(registered_plan, monkeypatch, capsys, command, state)
        assert "plan-tool run demo" not in err
        assert "plan-tool jira demo" not in err
        assert "plan-tool detail demo" not in err
        assert err.count("plan-tool completeness-audit demo") == 1

    @pytest.mark.parametrize("command", ["detail", "split", "merge"])
    def test_bare_bundle_names_detail_not_run(
        self, registered_plan, monkeypatch, capsys, command
    ) -> None:
        err = self._drive(
            registered_plan, monkeypatch, capsys, command, _EMPTY_SET,
            tail_current=True, bare=True,
        )
        assert err.count("plan-tool detail demo") == 1
        assert "plan-tool run demo" not in err

    @pytest.mark.parametrize("command", ["detail", "split", "merge"])
    @pytest.mark.parametrize("state", [_NON_EMPTY_SET, _INCOMPLETE, _ABSENT])
    def test_parent_keeps_leading_reaudit_command_when_stage_is_withheld(
        self, registered_plan, monkeypatch, capsys, command, state
    ) -> None:
        """Withholding the stage must not drop the re-audit lead: it stays ahead
        of the standing reconcile-plan entry."""
        err = self._drive(registered_plan, monkeypatch, capsys, command, state)
        block = err.split("Next steps:", 1)[1]
        assert "plan-tool run demo" not in block
        assert block.index("plan-tool completeness-audit demo") < block.index(
            "plan-tool reconcile-plan demo"
        )

    @pytest.mark.parametrize("bare", [True, False])
    @pytest.mark.parametrize("state", _VERDICT_STATES)
    def test_stage_rows_name_the_shared_stage_for_the_grade_and_bundle(
        self, monkeypatch, tmp_path, state, bare
    ) -> None:
        """Only a completed empty verdict offers detail or run for the bundle."""
        import plan_tool.cli.authoring as authoring

        plan_path = tmp_path / "1-demo.md"
        plan_path.write_text(_sectioned_plan_text(_CLEAN_STEPS), encoding="utf-8")
        monkeypatch.setattr(
            authoring, "_tail_result_freshness",
            lambda *_a, **_k: "current",
        )
        verdict = _verdict_for(state) or authoring.ABSENT_BLOCKING_VERDICT
        _follow, rows = authoring._authoring_guidance(
            "demo", path=plan_path, repo_root=tmp_path,
            tail_outcome=authoring._CompletenessTailOutcome(
                [], None, verdict, SimpleNamespace(is_bare=bare)
            ),
        )
        if state != _EMPTY_SET:
            assert rows == []
            return
        suffix = ""
        expected = (
            f"plan-tool detail demo{suffix}"
            if bare
            else "plan-tool run demo"
        )
        assert [c for c, _ in rows] == [expected]

    def test_run_gate_reads_verdict_not_command_text(
        self, registered_plan, monkeypatch, capsys
    ) -> None:
        err = self._drive(
            registered_plan, monkeypatch, capsys, "detail", _NON_EMPTY_SET,
            tail_next_steps=[
                ("plan-tool completeness-audit demo", "then run the next step")
            ],
        )
        assert "plan-tool run demo" not in err

    def test_detail_no_completeness_omits_run_because_no_audit_ran(
        self, registered_plan, monkeypatch, capsys
    ) -> None:
        err = self._drive(
            registered_plan, monkeypatch, capsys, "detail", _EMPTY_SET,
            no_completeness=True,
        )
        assert "plan-tool run demo" not in err

    def test_detail_failed_tail_omits_run_because_no_verdict_arrived(
        self, registered_plan, monkeypatch, capsys
    ) -> None:
        err = self._drive(
            registered_plan, monkeypatch, capsys, "detail", _EMPTY_SET,
            tail_raises=True,
        )
        assert "warning: auto-completeness pass failed" in err
        assert "plan-tool run demo" not in err

    def test_legacy_list_tail_double_reads_as_absent_verdict(self) -> None:
        import plan_tool.cli.authoring as authoring
        from plan_tool.completeness_report import ABSENT_BLOCKING_VERDICT

        outcome = authoring._coerce_completeness_tail_outcome([("a", "b")])
        assert outcome.blocking_verdict is ABSENT_BLOCKING_VERDICT
        assert authoring._authoring_guidance(
            "demo", path=Path("p.md"), repo_root=Path("."),
            tail_outcome=outcome,
        )[1] == []
        assert authoring._authoring_guidance(
            "demo", path=Path("p.md"), repo_root=Path("."),
            tail_outcome=None,
        )[1] == []


# --- Step 4: the grouped report's next-steps block agrees with the readers --

_GROUPED_STAGES = {
    "step-less": SimpleNamespace(
        is_bare=True, is_fully_bare=True, detailed_count=0, total=0
    ),
    "bare": SimpleNamespace(
        is_bare=True, is_fully_bare=True, detailed_count=0, total=2
    ),
    "partially-detailed": SimpleNamespace(
        is_bare=True, is_fully_bare=False, detailed_count=1, total=2
    ),
    "detailed": SimpleNamespace(
        is_bare=False, is_fully_bare=False, detailed_count=2, total=2
    ),
}
_GROUPED_VERDICTS = {
    "empty-set": blocking_verdict_from_gate([]),
    "non-empty-set": blocking_verdict_from_gate(["plan-correctness-high"]),
    "blocking-deterministic": blocking_verdict_from_gate(
        [], [_rec("det", source="intent")]
    ),
    "incomplete": blocking_verdict_from_gate([], untrusted_cause=UNTRUSTED_TRANSIENT),
    "absent": None,
}


@pytest.mark.parametrize("stage", list(_GROUPED_STAGES))
@pytest.mark.parametrize("state", list(_GROUPED_VERDICTS))
def test_grouped_report_offers_a_stage_only_for_a_completed_empty_set(
    state, stage
) -> None:
    """The grouped report is the fourth reader: at every stage and grade it
    follows the verdict, never a stage it could derive from the bundle."""
    bundle = _GROUPED_STAGES[stage]
    md = _render_grouped_report(
        SimpleNamespace(title="P"),
        SimpleNamespace(name="p"),
        _empty_det(),
        correctness_recs=[],
        conceptual_recs=[],
        audit_recs=[],
        iterate_enabled=False,
        bundle_status=bundle,
        verdict=_GROUPED_VERDICTS[state],
    )
    suggested = md.split("### Suggested next steps", 1)[1]
    if state == "empty-set":
        if bundle.is_bare:
            expected = "plan-tool detail p" + (
                ""
            )
        else:
            expected = "plan-tool run p"
        assert expected in suggested
    else:
        # Keys, not words: the absent message itself says "No gaps are listed".
        assert "no plan-level gaps remain" not in md
        for stage_command in (
            "plan-tool run p", "plan-tool jira p", "plan-tool detail p"
        ):
            assert stage_command not in suggested
        assert "plan-tool completeness-audit p" in suggested
    # Exactly one next command, the one every reader shares, named once.
    from plan_tool.completeness_report import next_stage_command

    from plan_tool.completeness_report import ABSENT_BLOCKING_VERDICT

    verdict = _GROUPED_VERDICTS[state] or ABSENT_BLOCKING_VERDICT
    next_cmd, _desc = next_stage_command(
        "p", bundle, verdict=verdict
    )
    assert suggested.count(f"`{next_cmd}`") == 1
    assert suggested.count("`plan-tool completeness-audit p") == (
        0 if state == "empty-set" else 1
    )
    if state in ("empty-set", "incomplete", "absent"):
        # Nothing is listed to close, so no step may tell the operator to.
        assert not [
            line for line in suggested.splitlines() if line.startswith("- Close ")
        ]


@pytest.mark.parametrize("bare", [True, False])
def test_grouped_report_advisory_gap_is_listed_without_close_or_reaudit_wording(
     bare
) -> None:
    """Advisory conceptual gaps (a completed empty set) are not 'close … then
    re-audit': the only row is the stage, and no re-audit command appears."""
    advisory = [_rec("medium", source="plan-completeness")]
    md = _render_grouped_report(
        SimpleNamespace(title="P"),
        SimpleNamespace(name="p"),
        _empty_det(),
        correctness_recs=[],
        conceptual_recs=advisory,
        audit_recs=advisory,
        iterate_enabled=False,
        bundle_status=SimpleNamespace(
            is_bare=bare, is_fully_bare=bare, detailed_count=0 if bare else 1, total=1
        ),
        verdict=_CLEAR_VERDICT,
    )
    suggested = md.split("### Suggested next steps", 1)[1]
    assert "completeness-audit" not in suggested
    assert not [ln for ln in suggested.splitlines() if ln.startswith("- Close ")]
    expected = (
        "plan-tool detail p" + ("")
        if bare
        else "plan-tool run p"
    )
    assert suggested.count(f"`{expected}`") == 1


def test_grouped_report_incomplete_with_nothing_listed_is_not_told_to_close_gaps(
) -> None:
    md = _render_grouped_report(
        SimpleNamespace(title="P"),
        SimpleNamespace(name="p"),
        _empty_det(),
        correctness_recs=[],
        conceptual_recs=[],
        audit_recs=[],
        iterate_enabled=False,
        bundle_status=_GROUPED_STAGES["detailed"],
        verdict=blocking_verdict_from_gate([], untrusted_cause=UNTRUSTED_TRANSIENT),
    )
    suggested = md.split("### Suggested next steps", 1)[1]
    reaudit = (
        "plan-tool completeness-audit p --iterate"
    )
    assert suggested.count(f"`{reaudit}`") == 1
    assert not [ln for ln in suggested.splitlines() if ln.startswith("- Close ")]
    assert "gaps above are closed" not in suggested


# --- Round-3 amendments: the grouped report's closing rows ------------------

def _grouped_suggested(*, verdict, det=None, bundle="detailed",
                       correctness=(), conceptual=()) -> str:
    md = _render_grouped_report(
        SimpleNamespace(title="P"),
        SimpleNamespace(name="p"),
        det or _empty_det(),
        correctness_recs=list(correctness),
        conceptual_recs=list(conceptual),
        audit_recs=[*correctness, *conceptual],
        iterate_enabled=False,
        bundle_status=_GROUPED_STAGES[bundle],
        verdict=verdict,
    )
    return md.split("### Suggested next steps", 1)[1]


def _stage_row(bundle: str = "detailed") -> str:
    from plan_tool.completeness_report import next_stage_command

    command, description = next_stage_command(
        "p", _GROUPED_STAGES[bundle], verdict=_CLEAR_VERDICT
    )
    return f"- `{command}` — {description}."


def test_grouped_advisory_wording_follows_only_advisory_rows() -> None:
    """Amendment 4: a structural step is required, so it is never followed by
    'advisory, hold back no stage'; a findings-only listing still is."""
    det = dataclasses.replace(
        _empty_det(),
        dep_issues=[SimpleNamespace(step_id=2, depends_on=1, reason="unknown")],
    )
    required = _grouped_suggested(verdict=_CLEAR_VERDICT, det=det)
    assert required.rstrip().splitlines()[-1] == _stage_row()
    advisory = _grouped_suggested(
        verdict=_CLEAR_VERDICT, conceptual=[_rec("medium", source="plan-completeness")]
    )
    assert advisory.rstrip().splitlines()[-1] != _stage_row()
    assert advisory.rstrip().splitlines()[-1].endswith(_stage_row()[2:])


def test_grouped_blocker_covered_by_a_structural_bullet_is_listed_once() -> None:
    """Amendment 5: a deterministic blocker whose arm the structural bullet
    already remedies is not repeated as a 'close directly' step."""
    det = dataclasses.replace(
        _empty_det(),
        dep_issues=[SimpleNamespace(step_id=2, depends_on=1, reason="unknown")],
    )
    blocker = _rec("deps", source="deps")
    other = _rec("sc", source="orphaned-deliverable")
    suggested = _grouped_suggested(
        verdict=blocking_verdict_from_gate([], [blocker, other]), det=det
    )
    direct = [ln for ln in suggested.splitlines() if ln.startswith("- Close the blocking")]
    assert len(direct) == 1
    assert "`orphaned-deliverable`" in direct[0]


def test_grouped_bare_plan_calls_no_completeness_gap_informational_when_blocking() -> None:
    """Amendment 8: with a completeness gap in the blocking set the correctness
    bullet does not call completeness gaps informational."""
    correctness = [_rec("high", source="plan-correctness")]
    blocking_completeness = [_rec("high", source="plan-completeness")]
    suggested = _grouped_suggested(
        verdict=blocking_verdict_from_gate(
            [r.id for r in (*correctness, *blocking_completeness)]
        ),
        bundle="bare", correctness=correctness, conceptual=blocking_completeness,
    )
    bullet = next(
        ln for ln in suggested.splitlines()
        if ln.startswith("- Close ") and "correctness" in ln
    )
    assert "informational" not in bullet


@pytest.mark.parametrize("cause", [UNTRUSTED_TRANSIENT, UNTRUSTED_PERSISTENT])
def test_grouped_incomplete_keeps_the_blocking_correctness_gap_as_a_gap_to_close(
    cause,
) -> None:
    """Amendment 1 at the fourth reader."""
    correctness = [_rec("high", source="plan-correctness")]
    suggested = _grouped_suggested(
        verdict=blocking_verdict_from_gate(
            [r.id for r in correctness], untrusted_cause=cause
        ),
        correctness=correctness,
        bundle="bare",
    )
    assert [ln for ln in suggested.splitlines() if ln.startswith("- Close ")]
    assert "plan-tool detail p" not in suggested


def test_grouped_persistent_cause_row_is_the_shared_description() -> None:
    """Amendment 3: the grouped report's closing row reuses the shared
    description for the cause, so persistent and transient rows differ."""
    from plan_tool.completeness_report import _reaudit_command

    rows = {}
    for cause in (UNTRUSTED_TRANSIENT, UNTRUSTED_PERSISTENT):
        verdict = blocking_verdict_from_gate([], untrusted_cause=cause)
        suggested = _grouped_suggested(verdict=verdict)
        _command, why = _reaudit_command("p", verdict)
        assert why in suggested
        rows[cause] = why
    assert rows[UNTRUSTED_TRANSIENT] != rows[UNTRUSTED_PERSISTENT]


@pytest.mark.parametrize("bare", [True, False])
def test_fresh_audit_follow_up_command_is_the_shared_reaudit_command(bare) -> None:
    """Amendment 7: the parents' fresh-audit row is built by the shared
    ``_reaudit_command`` with the required iteration flag."""
    import plan_tool.cli.authoring as authoring
    from plan_tool.completeness_report import (
        ABSENT_BLOCKING_VERDICT,
        _reaudit_command,
    )

    command, _ = authoring._fresh_completeness_audit_follow_up(
        "demo", bare_plan=bare
    )
    assert command == _reaudit_command(
        "demo", ABSENT_BLOCKING_VERDICT
    )[0]


def test_authoring_guidance_checks_the_tail_and_bundle_once(
    monkeypatch, tmp_path
) -> None:
    """Follow-up rows and the stage row come from one freshness check, and the
    stage row reads the bundle status the audit already computed: guidance
    never scans the bundle a second time."""
    import plan_tool.cli.authoring as authoring
    import plan_tool.review as review

    plan_path = tmp_path / "1-demo.md"
    plan_path.write_text(_sectioned_plan_text(_CLEAN_STEPS), encoding="utf-8")
    calls = {"fresh": 0, "bundle": 0}

    def _fresh(*_a, **_k):
        calls["fresh"] += 1
        return "current"

    def _bundle(*_a, **_k):
        calls["bundle"] += 1
        return SimpleNamespace(is_bare=False)

    monkeypatch.setattr(authoring, "_tail_result_freshness", _fresh)
    monkeypatch.setattr(review, "audit_detail_bundle_status", _bundle)
    outcome = authoring._CompletenessTailOutcome(
        [("plan-tool x", "tail row")],
        None,
        blocking_verdict_from_gate([]),
        SimpleNamespace(is_bare=False),
    )
    follow_up, stage = authoring._authoring_guidance(
        "demo", path=plan_path, repo_root=tmp_path,
        tail_outcome=outcome,
    )
    assert follow_up == [("plan-tool x", "tail row")]
    assert [c for c, _ in stage] == ["plan-tool run demo"]
    assert calls == {"fresh": 1, "bundle": 0}


class TestTailMovedArtifactsThroughRealSnapshots:
    """The staleness claim comes from comparing the result's recorded revision
    with the files on disk, not from the verdict's cause or the tail's
    ability to prove itself current."""

    @staticmethod
    def _guidance(tmp_path, *, result_from_snapshot=True, edit=False, cause=""):
        import plan_tool.cli.authoring as authoring
        from plan_tool.review_persistence import AuditInputSnapshot

        plan_path = tmp_path / "1-demo.md"
        plan_path.write_text(_sectioned_plan_text(_CLEAN_STEPS), encoding="utf-8")
        result = None
        if result_from_snapshot:
            snapshot = AuditInputSnapshot.capture(
                plan_path, tmp_path
            )
            result = {
                "headline": "no-qualified-current-evidence",
                "stage": "detail",
                "coverage": "unconfirmed",
                "revision_status": "current",
                "audit_revision": snapshot.revision,
            }
        if edit:
            plan_path.write_text(
                plan_path.read_text(encoding="utf-8") + "\nAn edit after the tail.\n",
                encoding="utf-8",
            )
        outcome = authoring._CompletenessTailOutcome(
            [], result,
            blocking_verdict_from_gate(["plan-correctness-high"], untrusted_cause=cause),
        )
        rows, _stage = authoring._authoring_guidance(
            "demo", path=plan_path, repo_root=tmp_path,
            tail_outcome=outcome,
        )
        return rows[0][1]

    @pytest.mark.parametrize("cause", ["transient", "persistent"])
    def test_an_edit_after_the_tail_reads_stale_not_the_original_cause(
        self, tmp_path, cause
    ) -> None:
        why = self._guidance(tmp_path, edit=True, cause=cause)
        assert "no current audit evidence" in why
        assert "reproduces" not in why and "stopped early" not in why

    @pytest.mark.parametrize(
        ("cause", "phrase"),
        [
            ("transient", "the audit stopped early"),
            ("persistent", "re-auditing unchanged text reproduces this result"),
        ],
    )
    def test_unchanged_files_keep_the_original_cause(
        self, tmp_path, cause, phrase
    ) -> None:
        assert phrase in self._guidance(tmp_path, cause=cause)

    def test_a_missing_final_result_is_not_called_stale(self, tmp_path) -> None:
        """Deliberate: no result to compare is not evidence the files moved;
        the gate's gaps, computed on unchanged text, stay named."""
        why = self._guidance(tmp_path, result_from_snapshot=False)
        assert "no current audit evidence" not in why
        assert "1 blocking gap(s) open" in why


    def test_a_failed_capture_is_unproven_not_moved(
        self, tmp_path, monkeypatch
    ) -> None:
        """Deliberate (carve-out): a capture that raises proves nothing about
        whether the files changed, and ``project_saved_completeness_result``
        classifies it ``unknown``; ``status`` and the authoring tail must agree,
        so the verdict keeps its own cause."""
        from plan_tool.review_persistence import AuditInputSnapshot

        real = AuditInputSnapshot.capture
        calls = {"n": 0}

        def flaky(*a, **k):
            calls["n"] += 1
            if calls["n"] > 1:  # the fixture's own capture succeeds
                raise OSError("plan deleted")
            return real(*a, **k)

        monkeypatch.setattr(AuditInputSnapshot, "capture", staticmethod(flaky))
        why = self._guidance(tmp_path, cause="persistent")
        assert "no current audit evidence" not in why
        assert "re-auditing unchanged text reproduces this result" in why

    def test_a_verdict_with_only_failing_deterministic_checks_is_not_hidden(
        self,
    ) -> None:
        """Deliberate: an unmoved verdict naming only deterministic blockers
        must not collapse into the fixed "run a fresh audit" row, which would
        hide the failing checks."""
        import plan_tool.cli.authoring as authoring
        from types import SimpleNamespace

        from plan_tool.completeness_report import DeterministicArmFinding

        real = SimpleNamespace(
            id="det", source="intent", severity="medium", title="t", body=""
        )
        arm = DeterministicArmFinding(
            id="deterministic-deps", source="deps", severity="medium",
            step_id=None, title="2 blocking deps finding(s)", body="",
        )
        _c, real_why = authoring._fresh_completeness_audit_follow_up(
            "demo",
            verdict=blocking_verdict_from_gate([], [real]),
        )
        assert "1 blocking gap(s) open" in real_why
        _c, arm_why = authoring._fresh_completeness_audit_follow_up(
            "demo",
            verdict=blocking_verdict_from_gate([], [arm]),
        )
        assert "1 deterministic check(s) failing" in arm_why

    def test_the_not_current_path_captures_the_bundle_once(
        self, tmp_path, monkeypatch
    ) -> None:
        """Both freshness checks share one capture of the bundle on disk."""
        from plan_tool.review_persistence import AuditInputSnapshot

        real = AuditInputSnapshot.capture
        calls = {"n": 0}

        def counting(*a, **k):
            calls["n"] += 1
            return real(*a, **k)

        monkeypatch.setattr(AuditInputSnapshot, "capture", staticmethod(counting))
        self._guidance(tmp_path, edit=True, cause="persistent")
        assert calls["n"] == 2  # the fixture's snapshot, plus exactly one check


@pytest.mark.integration
class TestRetiredAuditGradeSelector:
    def test_completeness_audit_rejects_removed_grade_selector(self, registered_plan, capsys):
        from plan_tool.cli import main

        with pytest.raises(SystemExit) as caught:
            main(registered_plan.argv("completeness-audit", "demo", "--grade", "jira"))
        assert caught.value.code == 2
        assert "unrecognized arguments: --grade jira" in capsys.readouterr().err


@pytest.mark.integration
class TestRunGradeAuditPersistence:
    def test_completeness_audit_persists_run_grade_report_and_qualified_sidecar(
        self, registered_plan, monkeypatch,
    ):
        from plan_tool.cli import main
        from plan_tool.review_persistence import load_review, plan_reports_dir
        import plan_tool.review

        def audit(*args, budget_report, **kwargs):
            budget_report.update(_qualifying_producer_coverage())
            budget_report["confirmation_kind"] = "confirmed-dry"
            return []

        monkeypatch.setattr(plan_tool.review, "audit_plan_until_stable", audit)
        plan_path = registered_plan.plans_dir / "1-demo.md"
        plan_path.write_text(_sectioned_plan_text(_CLEAN_STEPS))
        assert main(registered_plan.argv("completeness-audit", "demo", "-y")) == 0
        reports = list(plan_reports_dir(plan_path).glob("*-completeness.md"))
        assert len(reports) == 1
        saved = load_review(reports[0].with_suffix(".json"))
        assert saved.qualified_result["audit_revision"]["detail_grade"] == "run"
        assert saved.qualified_result["coverage"] == "confirmed"
        assert saved.is_pre_apply_checkpoint is False
