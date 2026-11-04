"""Tests for plan_tool.review_persistence — save/load/list saved reviews."""

from __future__ import annotations

import json
import os
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

import pytest

from plan_tool.review import (
    CARRIED_RESOLUTION_APPLIED,
    CARRIED_RESOLUTION_OPEN,
    CARRIED_RESOLUTION_SKIPPED,
    Recommendation,
    Redirect,
)
from plan_tool import review_persistence as rp
from plan_tool.audit_shapes import AuditShapeAdvisory, AuditShapeFindingEvidence
from plan_tool.review_persistence import (
    Annotation,
    ReviewLoadError,
    SavedReview,
    carried_resolution_from_annotations,
    compute_plan_fingerprint,
    list_saved_reviews,
    load_review,
    load_sampler_checkpoint,
    plan_reports_dir,
    project_audit_coverage,
    resolve_saved_review,
    save_review,
    save_sampler_checkpoint,
    sampler_checkpoint_path,
    update_annotation,
)


# A plan file whose slug ("x") matches the ``plan_slug`` used across these
# tests, so the canonical reports dir and the legacy reviews dir agree on
# the slug. ``save_review`` derives the reports dir from this path.
_PLAN_REL = "plans/1-x.md"


def _plan_abs(repo_root: Path) -> Path:
    return repo_root / _PLAN_REL


_SAMPLE_RECS = [
    Recommendation(
        id="step1-file-check-abc12345",
        source="file-check",
        severity="high",
        step_id=1,
        title="Step 1: declared file path doesn't resolve",
        body="`a.py` (resolved to /abs/a.py; parent missing)",
        suggested_action="verify the path",
    ),
    Recommendation(
        id="step2-deps-deadbeef",
        source="deps",
        severity="critical",
        step_id=2,
        title="Step 2: depends on step 99 which is unknown",
        body="…",
        suggested_action=None,
    ),
]

_AUDIT_COVERAGE = {
    "budget_limited": False,
    "passes_used": 2,
    "cap": 3,
    "recommendation_kind": None,
    "recommended_passes": None,
    "recommendation_advice": None,
    "confirmation_kind": "confirmed-dry",
    "conforming_pass_count": 2,
    "failed_or_malformed_pass_count": 0,
}

_SAMPLE_ADVISORY = AuditShapeAdvisory(
    shape_id="arm-clustering",
    source_plan_fingerprint="exact-input-sha",
    arm_step_ids=(1, 2),
    material_finding_ids=("finding-a", "finding-b", "finding-c"),
    arm_finding_ids=("finding-a", "finding-b"),
    material_finding_evidence=(
        AuditShapeFindingEvidence("finding-a", "cache", "plan-correctness"),
        AuditShapeFindingEvidence("finding-b", "retry", "plan-completeness"),
        AuditShapeFindingEvidence("finding-c", None, "plan-completeness"),
    ),
    material_finding_count=3,
    arm_finding_count=2,
    committed_step_count=3,
)

# Sentinel for "this raw sidecar carries no checkpoint marker at all", which is
# a different state from a marker present with a ``null`` value.
_NO_MARKER = object()


def _write_raw_sidecar(
    path: Path,
    *,
    version: int,
    kind: str = "completeness",
    marker: object = _NO_MARKER,
) -> Path:
    """Write a saved-review payload verbatim, bypassing ``save_review``.

    The role matrix has to cover raw states the supported writer refuses to
    emit: a marker in a legacy-version sidecar, a non-boolean value, an
    explicit version-3 ``false``, and a marker-less version-3 sidecar.
    """
    payload: dict[str, object] = {
        "version": version,
        "plan_slug": "x",
        "plan_path": _PLAN_REL,
        "created_at": "2026-01-01T00:00:00Z",
        "kind": kind,
        "report_md": "report",
        "recommendations": [
            {
                "id": "step1-file-check-abc12345",
                "source": "file-check",
                "severity": "high",
                "step_id": 1,
                "title": "Step 1: declared file path doesn't resolve",
                "body": "`a.py` (resolved to /abs/a.py; parent missing)",
                "suggested_action": "verify the path",
                "confidence": "limited",
            }
        ],
        "annotations": {},
    }
    if marker is not _NO_MARKER:
        payload["is_pre_apply_checkpoint"] = marker
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


class TestCarriedResolutionFromAnnotations:
    def test_carried_resolution_applied(self) -> None:
        assert carried_resolution_from_annotations(
            {"rec-1": Annotation(status="applied")}
        ) == {"rec-1": (CARRIED_RESOLUTION_APPLIED, "")}

    def test_carried_resolution_skip_drift(self) -> None:
        assert carried_resolution_from_annotations(
            {"rec-1": Annotation(status="skip", halt_reason="drift")}
        ) == {"rec-1": (CARRIED_RESOLUTION_SKIPPED, "drift")}

    def test_carried_resolution_skip_decline(self) -> None:
        assert carried_resolution_from_annotations(
            {"rec-1": Annotation(status="skip")}
        ) == {"rec-1": (CARRIED_RESOLUTION_SKIPPED, "")}

    def test_carried_resolution_open(self) -> None:
        assert carried_resolution_from_annotations(
            {"rec-1": Annotation(status="open")}
        ) == {"rec-1": (CARRIED_RESOLUTION_OPEN, "")}

    def test_carried_resolution_keys_by_rec_id(self) -> None:
        annotations = {
            "step1-file-check-abc12345": Annotation(status="applied"),
            "step2-deps-deadbeef": Annotation(status="open"),
        }

        assert set(carried_resolution_from_annotations(annotations)) == {
            "step1-file-check-abc12345",
            "step2-deps-deadbeef",
        }


class TestReviewsDir:
    def test_reports_dir_under_plan_details(self, tmp_path: Path) -> None:
        plan_path = tmp_path / "plans" / "1-my-feature.md"
        assert (
            plan_reports_dir(plan_path)
            == tmp_path / "plans" / "plan-details" / "my-feature" / "reports"
        )


class TestSaveReview:
    def test_save_load_normalized_audit_coverage(self, tmp_path: Path) -> None:
        path = save_review(
            plan_slug="x", plan_path=_PLAN_REL, repo_root=tmp_path,
            report_md="report", recommendations=_SAMPLE_RECS,
            kind="completeness", audit_coverage=_AUDIT_COVERAGE,
        )

        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["audit_coverage"] == _AUDIT_COVERAGE
        assert load_review(path).audit_coverage == _AUDIT_COVERAGE

    def test_normalized_audit_coverage_accepts_cap_one_unconfirmed(
        self, tmp_path: Path
    ) -> None:
        coverage = {
            **_AUDIT_COVERAGE,
            "passes_used": 1,
            "cap": 1,
            "confirmation_kind": None,
        }
        path = save_review(
            plan_slug="x", plan_path=_PLAN_REL, repo_root=tmp_path,
            report_md="report", recommendations=[], kind="completeness",
            audit_coverage=coverage,
        )

        assert load_review(path).audit_coverage == coverage

    @pytest.mark.parametrize(
        "coverage",
        [
            {
                **_AUDIT_COVERAGE,
                "budget_limited": True,
                "passes_used": 2,
                "cap": 3,
                "confirmation_kind": None,
            },
            {
                **_AUDIT_COVERAGE,
                "passes_used": 1,
                "cap": 3,
                "confirmation_kind": "confirmed-low-yield",
            },
        ],
    )
    def test_normalized_audit_coverage_rejects_producer_impossible_tuples(
        self, tmp_path: Path, coverage: dict[str, object]
    ) -> None:
        path = save_review(
            plan_slug="x", plan_path=_PLAN_REL, repo_root=tmp_path,
            report_md="report", recommendations=_SAMPLE_RECS,
            kind="completeness", audit_coverage=_AUDIT_COVERAGE,
        )
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["audit_coverage"] = coverage
        path.write_text(json.dumps(payload), encoding="utf-8")

        loaded = load_review(path)
        assert loaded.recommendations == _SAMPLE_RECS
        assert loaded.audit_coverage is None
        assert project_audit_coverage(loaded.audit_coverage)["evidence_status"] == (
            "unknown-legacy"
        )

    def test_missing_or_malformed_audit_coverage_is_unknown_but_loadable(
        self, tmp_path: Path
    ) -> None:
        legacy_path = save_review(
            plan_slug="x", plan_path=_PLAN_REL, repo_root=tmp_path,
            report_md="report", recommendations=_SAMPLE_RECS, kind="completeness",
        )
        malformed_path = save_review(
            plan_slug="y", plan_path="plans/1-y.md", repo_root=tmp_path,
            report_md="report", recommendations=_SAMPLE_RECS, kind="completeness",
        )
        malformed_payload = json.loads(malformed_path.read_text(encoding="utf-8"))
        malformed_payload["audit_coverage"] = "not an object"
        malformed_path.write_text(json.dumps(malformed_payload), encoding="utf-8")

        for path in (legacy_path, malformed_path):
            loaded = load_review(path)
            assert loaded.recommendations == _SAMPLE_RECS
            assert loaded.audit_coverage is None
            projected = project_audit_coverage(loaded.audit_coverage)
            assert projected["evidence_status"] == "unknown-legacy"
            assert projected["budget_limited"] is None
            assert projected["passes_used"] is None
            assert projected["cap"] is None
            assert projected["confirmation_kind"] is None

    def test_unknown_audit_coverage_projection_has_no_clean_verdict(self) -> None:
        projected = project_audit_coverage(None)

        assert projected["evidence_status"] == "unknown-legacy"
        assert {
            projected["budget_limited"],
            projected["passes_used"],
            projected["cap"],
            projected["confirmation_kind"],
        } == {None}

    def test_audit_shape_advisory_round_trips_without_finding_prose(
        self, tmp_path: Path
    ) -> None:
        advisory = AuditShapeAdvisory(
            shape_id="arm-clustering",
            source_plan_fingerprint="exact-input-sha",
            arm_step_ids=(1, 2, 3),
            material_finding_ids=("finding-a", "finding-b", "finding-c"),
            arm_finding_ids=("finding-a", "finding-b", "finding-c"),
            material_finding_evidence=(
                AuditShapeFindingEvidence(
                    "finding-a", "cache", "plan-correctness"
                ),
                AuditShapeFindingEvidence(
                    "finding-b", "retry", "plan-completeness"
                ),
                AuditShapeFindingEvidence(
                    "finding-c", None, "plan-completeness"
                ),
            ),
            material_finding_count=3,
            arm_finding_count=3,
            committed_step_count=5,
        )
        path = save_review(
            plan_slug="x",
            plan_path=_PLAN_REL,
            repo_root=tmp_path,
            report_md="report",
            recommendations=_SAMPLE_RECS,
            kind="completeness",
            audit_shape_advisory=advisory,
        )

        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["version"] == 2
        assert "title" not in payload["audit_shape_advisory"]
        assert "body" not in payload["audit_shape_advisory"]
        assert load_review(path).audit_shape_advisory == advisory

    def test_malformed_optional_advisory_leaves_review_usable(
        self, tmp_path: Path
    ) -> None:
        advisory = AuditShapeAdvisory(
            shape_id="arm-clustering",
            source_plan_fingerprint="exact-input-sha",
            arm_step_ids=(1, 2, 3),
            material_finding_ids=("finding-a", "finding-b", "finding-c"),
            arm_finding_ids=("finding-a", "finding-b", "finding-c"),
            material_finding_evidence=(
                AuditShapeFindingEvidence("finding-a", None, "plan-correctness"),
                AuditShapeFindingEvidence("finding-b", None, "plan-completeness"),
                AuditShapeFindingEvidence("finding-c", None, "plan-completeness"),
            ),
            material_finding_count=3,
            arm_finding_count=3,
            committed_step_count=5,
        )
        path = save_review(
            plan_slug="x", plan_path=_PLAN_REL, repo_root=tmp_path,
            report_md="report", recommendations=_SAMPLE_RECS,
            audit_shape_advisory=advisory,
        )
        data = json.loads(path.read_text(encoding="utf-8"))
        data["audit_shape_advisory"]["arm_step_ids"] = [1, 1, 2]
        path.write_text(json.dumps(data), encoding="utf-8")

        loaded = load_review(path)

        assert loaded.recommendations == _SAMPLE_RECS
        assert loaded.audit_shape_advisory is None

    def test_load_recovers_legacy_conceptual_anchor_without_changing_id(
        self, tmp_path: Path
    ) -> None:
        path = save_review(
            plan_slug="x", plan_path=_PLAN_REL, repo_root=tmp_path,
            report_md="report",
            recommendations=[
                Recommendation(
                    id="legacy-id", source="plan-completeness", severity="low",
                    step_id=None, title="[cache-retention] Retention is vague",
                    body="Retention is vague",
                )
            ],
        )
        loaded = load_review(path).recommendations[0]

        assert loaded.id == "legacy-id"
        assert loaded.anchor == "cache-retention"
        assert loaded.title == "Retention is vague"

    def test_round_trips_outcome_evidence_valid_and_annotation_rewrite(
        self, tmp_path: Path
    ) -> None:
        path = save_review(
            plan_slug="x", plan_path=_PLAN_REL, repo_root=tmp_path,
            report_md="report", recommendations=_SAMPLE_RECS,
            kind="run-reconcile", outcome_evidence_valid=True,
        )

        assert load_review(path).outcome_evidence_valid is True
        update_annotation(path, _SAMPLE_RECS[0].id, Annotation(status="skip"))
        assert load_review(path).outcome_evidence_valid is True

    def test_legacy_outcome_evidence_is_unknown(self, tmp_path: Path) -> None:
        path = save_review(
            plan_slug="x", plan_path=_PLAN_REL, repo_root=tmp_path,
            report_md="report", recommendations=[], kind="run-reconcile",
        )
        assert load_review(path).outcome_evidence_valid is None

    def test_round_trips_purity_verdict_provenance(self, tmp_path: Path) -> None:
        tagged = Recommendation(
            id="purity-1", source="granularity-split", severity="medium",
            step_id=1, title="Mixed step", body="Split it.",
            purity_verdict_provenance="fresh",
        )
        path = save_review(
            plan_slug="x", plan_path=_PLAN_REL, repo_root=tmp_path,
            report_md="report", recommendations=[tagged],
        )

        assert load_review(path).recommendations[0].purity_verdict_provenance == "fresh"

    def test_loads_legacy_recommendation_without_purity_provenance(
        self, tmp_path: Path
    ) -> None:
        path = save_review(
            plan_slug="x", plan_path=_PLAN_REL, repo_root=tmp_path,
            report_md="report", recommendations=[_SAMPLE_RECS[0]],
        )
        data = json.loads(path.read_text(encoding="utf-8"))
        data["recommendations"][0].pop("purity_verdict_provenance")
        path.write_text(json.dumps(data), encoding="utf-8")

        assert load_review(path).recommendations[0].purity_verdict_provenance is None

    def test_creates_directory_and_file(self, tmp_path: Path) -> None:
        path = save_review(
            plan_slug="my-feature",
            plan_path="implementation-plans/1-my-feature.md",
            repo_root=tmp_path,
            report_md="## Plan Review\n\nbody\n",
            recommendations=_SAMPLE_RECS,
        )
        assert path.is_file()
        assert path.parent == plan_reports_dir(
            tmp_path / "implementation-plans" / "1-my-feature.md"
        )
        assert path.suffix == ".json"

    def test_filename_is_timestamp(self, tmp_path: Path) -> None:
        fixed = datetime(2026, 5, 5, 12, 34, 56, tzinfo=timezone.utc)
        path = save_review(
            plan_slug="x",
            plan_path="plans/x.md",
            repo_root=tmp_path,
            report_md="",
            recommendations=[],
            now=fixed,
        )
        assert path.name == "20260505-123456.json"

    def test_payload_structure(self, tmp_path: Path) -> None:
        fixed = datetime(2026, 5, 5, 12, 34, 56, tzinfo=timezone.utc)
        path = save_review(
            plan_slug="x",
            plan_path="plans/x.md",
            repo_root=tmp_path,
            report_md="md",
            recommendations=_SAMPLE_RECS,
            now=fixed,
        )
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["version"] == 1
        assert data["plan_slug"] == "x"
        assert data["plan_path"] == "plans/x.md"
        assert data["created_at"] == "2026-05-05T12:34:56Z"
        assert data["report_md"] == "md"
        assert len(data["recommendations"]) == 2
        assert data["recommendations"][0]["id"] == "step1-file-check-abc12345"
        assert data["annotations"] == {}

    def test_save_with_annotations(self, tmp_path: Path) -> None:
        path = save_review(
            plan_slug="x",
            plan_path="plans/x.md",
            repo_root=tmp_path,
            report_md="",
            recommendations=_SAMPLE_RECS,
            annotations={
                "step1-file-check-abc12345": Annotation(
                    status="applied", note="fixed in commit 123"
                ),
            },
        )
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["annotations"] == {
            "step1-file-check-abc12345": {
                "status": "applied",
                "note": "fixed in commit 123",
                "halt_reason": "",
            }
        }

    def test_timestamp_filename_detail_reconcile_kind_suffixes_correctly(
        self, tmp_path: Path
    ) -> None:
        """``kind="detail-reconcile"`` lands the suffix verbatim — same
        rule the existing ``"reconcile"`` literal exercised, but
        proof against a future suffix-format regression."""
        fixed = datetime(2026, 5, 5, 12, 34, 56, tzinfo=timezone.utc)
        path = save_review(
            plan_slug="x",
            plan_path="plans/x.md",
            repo_root=tmp_path,
            report_md="",
            recommendations=[],
            now=fixed,
            kind="detail-reconcile",
            step_id=3,
        )
        assert path.name == "20260505-123456-detail-reconcile.json"

    def test_timestamp_filename_run_reconcile_kind_suffixes_correctly(
        self, tmp_path: Path
    ) -> None:
        """``kind="run-reconcile"`` lands the suffix verbatim. Locks
        the on-disk filename contract used by
        ``_find_saved_run_reconcile_for_step``'s cheap pre-filter and
        by step 8's integration test."""
        fixed = datetime(2026, 5, 5, 12, 34, 56, tzinfo=timezone.utc)
        path = save_review(
            plan_slug="x",
            plan_path="plans/x.md",
            repo_root=tmp_path,
            report_md="",
            recommendations=[],
            now=fixed,
            kind="run-reconcile",
            step_id=4,
        )
        assert path.name == "20260505-123456-run-reconcile.json"


def test_plan_quota_coverage_normalizes_and_projects() -> None:
    from plan_tool.review_persistence import (
        audit_coverage_withholds_final_findings_sidecar,
        normalize_audit_coverage,
    )

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

    assert normalize_audit_coverage(coverage) == coverage
    assert project_audit_coverage(coverage) == {
        "evidence_status": "observed",
        **coverage,
    }
    assert audit_coverage_withholds_final_findings_sidecar(coverage) is True
    assert audit_coverage_withholds_final_findings_sidecar({}) is False


def test_legacy_coverage_without_early_stop_reason_remains_valid() -> None:
    from plan_tool.review_persistence import normalize_audit_coverage

    legacy = {
        "budget_limited": False,
        "passes_used": 2,
        "cap": 3,
        "recommendation_kind": None,
        "recommended_passes": None,
        "recommendation_advice": None,
        "confirmation_kind": "confirmed-dry",
        "conforming_pass_count": 2,
        "failed_or_malformed_pass_count": 0,
    }

    assert normalize_audit_coverage(legacy) == legacy
    assert project_audit_coverage(legacy) == {
        "evidence_status": "observed",
        **legacy,
    }


def test_nonquota_coverage_omits_optional_early_stop_reason() -> None:
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
        "early_stop_reason": None,
    }

    projected = project_audit_coverage(coverage)
    assert projected["evidence_status"] == "observed"
    assert "early_stop_reason" not in projected


class TestLoadReview:
    def test_round_trip(self, tmp_path: Path) -> None:
        path = save_review(
            plan_slug="x",
            plan_path="plans/x.md",
            repo_root=tmp_path,
            report_md="full report",
            recommendations=_SAMPLE_RECS,
            annotations={
                "step1-file-check-abc12345": Annotation("applied", "x"),
            },
        )
        loaded = load_review(path)
        assert loaded.plan_slug == "x"
        assert loaded.plan_path == "plans/x.md"
        assert loaded.report_md == "full report"
        assert len(loaded.recommendations) == 2
        assert loaded.recommendations[0] == _SAMPLE_RECS[0]
        assert loaded.recommendations[1] == _SAMPLE_RECS[1]
        assert loaded.annotations == {
            "step1-file-check-abc12345": Annotation("applied", "x"),
        }
        assert loaded.path == path

    @pytest.mark.parametrize("confidence", ["supported", "limited"])
    def test_saved_recommendation_confidence_round_trips(
        self, tmp_path: Path, confidence: str
    ) -> None:
        path = save_review(
            plan_slug="x",
            plan_path=_PLAN_REL,
            repo_root=tmp_path,
            report_md="report",
            recommendations=[replace(_SAMPLE_RECS[0], confidence=confidence)],
        )

        assert load_review(path).recommendations[0].confidence == confidence

    def test_saved_recommendation_redirect_round_trips(self, tmp_path: Path) -> None:
        rec = replace(
            _SAMPLE_RECS[0],
            redirect=Redirect(reason="plan-owned", suggested_next="plan-tool detail x"),
        )
        path = save_review(
            plan_slug="x",
            plan_path=_PLAN_REL,
            repo_root=tmp_path,
            report_md="report",
            recommendations=[rec],
        )

        assert load_review(path).recommendations[0].redirect == rec.redirect

    def test_saved_recommendation_restated_property_round_trips(
        self, tmp_path: Path
    ) -> None:
        # restated_property is Correctness-axis only (enforced on load by
        # normalize_restated_property_axis) -- source must be
        # "plan-correctness", unlike _SAMPLE_RECS[0]'s "file-check".
        rec = replace(
            _SAMPLE_RECS[0],
            source="plan-correctness",
            restated_property=(
                "the resolution-confidence chain has no route for a "
                "confidently-resolved-but-degenerate mapping"
            ),
        )
        path = save_review(
            plan_slug="x",
            plan_path=_PLAN_REL,
            repo_root=tmp_path,
            report_md="report",
            recommendations=[rec],
        )

        assert (
            load_review(path).recommendations[0].restated_property
            == rec.restated_property
        )

    def test_legacy_sidecar_with_no_restated_property_loads_none(
        self, tmp_path: Path
    ) -> None:
        # _write_raw_sidecar's payload predates the field entirely (no key
        # at all, not even null) -- the round-trip test above only proves a
        # *populated* value survives; a pre-existing sidecar must still load.
        path = _write_raw_sidecar(tmp_path / "legacy-no-restated.json", version=1)

        assert load_review(path).recommendations[0].restated_property is None

    def test_load_rejects_malformed_recommendation_restated_property(
        self, tmp_path: Path
    ) -> None:
        path = _write_raw_sidecar(
            tmp_path / "invalid-restated-property.json", version=1
        )
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["recommendations"][0]["restated_property"] = 42
        path.write_text(json.dumps(payload), encoding="utf-8")

        with pytest.raises(ReviewLoadError, match="recommendation restated_property"):
            load_review(path)

    def test_load_drops_restated_property_from_a_non_correctness_source(
        self, tmp_path: Path
    ) -> None:
        """The field is Correctness-axis only by contract; a hand-edited or
        other-producer sidecar isn't bound by the parser's own gating, so
        load time re-enforces it. ``_write_raw_sidecar``'s fixture recommendation
        has source "file-check"."""
        path = _write_raw_sidecar(
            tmp_path / "non-correctness-restated.json", version=1
        )
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["recommendations"][0]["restated_property"] = "should be dropped"
        path.write_text(json.dumps(payload), encoding="utf-8")

        assert load_review(path).recommendations[0].restated_property is None

    def test_load_rejects_malformed_recommendation_redirect(
        self, tmp_path: Path
    ) -> None:
        path = _write_raw_sidecar(tmp_path / "invalid-redirect.json", version=1)
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["recommendations"][0]["redirect"] = {"reason": "plan-owned"}
        path.write_text(json.dumps(payload), encoding="utf-8")

        with pytest.raises(ReviewLoadError, match="recommendation redirect"):
            load_review(path)

    def test_legacy_sidecar_confidence_loads_unknown_and_rewrite_writes_null(
        self, tmp_path: Path
    ) -> None:
        path = _write_raw_sidecar(tmp_path / "legacy-confidence.json", version=1)
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["recommendations"][0].pop("confidence")
        path.write_text(json.dumps(payload), encoding="utf-8")

        assert load_review(path).recommendations[0].confidence is None
        update_annotation(path, "step1-file-check-abc12345", Annotation("skip"))

        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["recommendations"][0]["confidence"] is None

    def test_sidecar_null_confidence_remains_unknown(self, tmp_path: Path) -> None:
        path = _write_raw_sidecar(tmp_path / "null-confidence.json", version=1)
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["recommendations"][0]["confidence"] = None
        path.write_text(json.dumps(payload), encoding="utf-8")

        assert load_review(path).recommendations[0].confidence is None

    @pytest.mark.parametrize("confidence", ["uncertain", "SUPPORTED", 1, False, []])
    def test_load_rejects_invalid_recommendation_confidence(
        self, tmp_path: Path, confidence: object
    ) -> None:
        path = _write_raw_sidecar(tmp_path / "invalid-confidence.json", version=1)
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["recommendations"][0]["confidence"] = confidence
        path.write_text(json.dumps(payload), encoding="utf-8")

        with pytest.raises(ReviewLoadError, match="recommendation confidence"):
            load_review(path)

    def test_load_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ReviewLoadError):
            load_review(tmp_path / "nope.json")

    def test_load_malformed_json_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.json"
        path.write_text("{ not json", encoding="utf-8")
        with pytest.raises(ReviewLoadError):
            load_review(path)

    def test_load_invalid_utf8_raises_review_load_error(self, tmp_path: Path) -> None:
        path = tmp_path / "bad-utf8.json"
        path.write_bytes(b"\xff")

        with pytest.raises(ReviewLoadError):
            load_review(path)

    @pytest.mark.parametrize("annotations", [[], {"rec-1": []}])
    def test_load_malformed_annotations_raise_review_load_error(
        self, tmp_path: Path, annotations: object
    ) -> None:
        path = _write_raw_sidecar(tmp_path / "bad-annotations.json", version=1)
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["annotations"] = annotations
        path.write_text(json.dumps(payload), encoding="utf-8")

        with pytest.raises(ReviewLoadError):
            load_review(path)

    @pytest.mark.parametrize("field", ["note", "halt_reason"])
    def test_load_annotations_rejects_explicit_null_strings(
        self, tmp_path: Path, field: str
    ) -> None:
        path = _write_raw_sidecar(tmp_path / "null-annotation.json", version=1)
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["annotations"] = {"rec-1": {"status": "skip", field: None}}
        path.write_text(json.dumps(payload), encoding="utf-8")

        with pytest.raises(ReviewLoadError, match=rf"annotation {field}"):
            load_review(path)

    @pytest.mark.parametrize("kind", [[], {}, 1, True, None])
    def test_load_nonstring_kind_raises_review_load_error(
        self, tmp_path: Path, kind: object
    ) -> None:
        path = _write_raw_sidecar(tmp_path / "bad-kind.json", version=1)
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["kind"] = kind
        path.write_text(json.dumps(payload), encoding="utf-8")

        with pytest.raises(ReviewLoadError):
            load_review(path)

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("report_md", []),
            ("recommendations", {"id": "not-a-list"}),
            ("code_fingerprint", {"path": 1}),
        ],
    )
    def test_load_rejects_unsafe_convergence_fields(
        self, tmp_path: Path, field: str, value: object
    ) -> None:
        path = _write_raw_sidecar(tmp_path / "unsafe.json", version=1)
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload[field] = value
        path.write_text(json.dumps(payload), encoding="utf-8")

        with pytest.raises(ReviewLoadError):
            load_review(path)

    @pytest.mark.parametrize("severity", ["urgent", "", None, 1])
    def test_load_rejects_unknown_recommendation_severity(
        self, tmp_path: Path, severity: object
    ) -> None:
        path = _write_raw_sidecar(tmp_path / "unknown-severity.json", version=1)
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["recommendations"][0]["severity"] = severity
        path.write_text(json.dumps(payload), encoding="utf-8")

        with pytest.raises(ReviewLoadError, match="recommendation severity"):
            load_review(path)

    def test_load_optional_audit_metadata_is_total(self, tmp_path: Path) -> None:
        path = _write_raw_sidecar(tmp_path / "optional.json", version=4)
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["qualified_result"] = {
            "headline": [],
            "stage": {},
            "coverage": ["unknown"],
            "revision_status": None,
            "audit_revision": [],
        }
        payload["audit_coverage"] = {
            "budget_limited": False,
            "passes_used": 1,
            "cap": 1,
            "recommendation_kind": None,
            "recommended_passes": None,
            "recommendation_advice": None,
            "confirmation_kind": [],
            "conforming_pass_count": 1,
            "failed_or_malformed_pass_count": 0,
        }
        path.write_text(json.dumps(payload), encoding="utf-8")

        loaded = load_review(path)

        assert loaded.qualified_result is None
        assert loaded.audit_coverage is None

    @pytest.mark.parametrize(
        "error", [TypeError("bad value"), ValueError("bad value")]
    )
    def test_load_converts_field_coercion_errors_to_review_load_error(
        self, tmp_path: Path, monkeypatch, error: Exception
    ) -> None:
        path = _write_raw_sidecar(tmp_path / "coercion.json", version=4)

        def raise_coercion_error(value: object) -> None:
            raise error

        monkeypatch.setattr(rp, "normalize_audit_coverage", raise_coercion_error)

        with pytest.raises(ReviewLoadError, match="malformed saved review"):
            load_review(path)

    def test_load_does_not_mask_saved_review_construction_errors(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        path = _write_raw_sidecar(tmp_path / "constructor.json", version=4)

        def raise_constructor_error(**kwargs: object) -> None:
            raise TypeError("constructor defect")

        monkeypatch.setattr(rp, "SavedReview", raise_constructor_error)

        with pytest.raises(TypeError, match="constructor defect"):
            load_review(path)

    def test_load_wrong_schema_version_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "future.json"
        path.write_text(
            json.dumps(
                {
                    "version": 999,
                    "plan_slug": "x",
                    "plan_path": "p",
                    "created_at": "2026-01-01T00:00:00Z",
                    "report_md": "",
                    "recommendations": [],
                    "annotations": {},
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(ReviewLoadError, match="schema version"):
            load_review(path)

    def test_load_rewrites_legacy_done_status_to_applied(
        self, tmp_path: Path
    ) -> None:
        """Older saves used status="done"; load silently rewrites to "applied"."""
        path = tmp_path / "legacy.json"
        path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "plan_slug": "x",
                    "plan_path": "plans/x.md",
                    "created_at": "2026-01-01T00:00:00Z",
                    "report_md": "",
                    "recommendations": [
                        {
                            "id": "r-1",
                            "source": "deps",
                            "severity": "high",
                            "step_id": 1,
                            "title": "t",
                            "body": "b",
                            "suggested_action": None,
                        }
                    ],
                    "annotations": {
                        "r-1": {"status": "done", "note": "fixed"}
                    },
                }
            ),
            encoding="utf-8",
        )
        loaded = load_review(path)
        assert loaded.annotations["r-1"].status == "applied"
        assert loaded.annotations["r-1"].note == "fixed"

    def test_load_top_level_not_object_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "list.json"
        path.write_text("[1, 2, 3]", encoding="utf-8")
        with pytest.raises(ReviewLoadError):
            load_review(path)

    def test_save_and_load_review_round_trip_detail_reconcile_kind(
        self, tmp_path: Path
    ) -> None:
        """``kind="detail-reconcile"`` and ``step_id`` survive the
        save → load round-trip so reuse-lookups can key off them."""
        path = save_review(
            plan_slug="x",
            plan_path="plans/x.md",
            repo_root=tmp_path,
            report_md="audit · step 3",
            recommendations=_SAMPLE_RECS,
            kind="detail-reconcile",
            step_id=3,
        )
        loaded = load_review(path)
        assert loaded.kind == "detail-reconcile"
        assert loaded.step_id == 3
        assert loaded.report_md == "audit · step 3"

    def test_save_and_load_review_round_trip_run_reconcile_kind(
        self, tmp_path: Path
    ) -> None:
        """``kind="run-reconcile"`` and ``step_id`` survive the
        save → load round-trip so
        ``_find_saved_run_reconcile_for_step`` can key off them."""
        path = save_review(
            plan_slug="x",
            plan_path="plans/x.md",
            repo_root=tmp_path,
            report_md="code audit · step 4",
            recommendations=_SAMPLE_RECS,
            kind="run-reconcile",
            step_id=4,
        )
        loaded = load_review(path)
        assert loaded.kind == "run-reconcile"
        assert loaded.step_id == 4
        assert loaded.report_md == "code audit · step 4"

    def test_load_preserves_non_legacy_kinds(self, tmp_path: Path) -> None:
        """The three live kinds (``"review"``, ``"detail-reconcile"``,
        ``"run-reconcile"``) round-trip verbatim."""
        for kind in ("review", "detail-reconcile", "run-reconcile"):
            path = tmp_path / f"{kind}.json"
            path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "plan_slug": "x",
                        "plan_path": "p",
                        "created_at": "2026-01-01T00:00:00Z",
                        "kind": kind,
                        "step_id": 1,
                        "report_md": "",
                        "recommendations": [],
                        "annotations": {},
                    }
                ),
                encoding="utf-8",
            )
            loaded = load_review(path)
            assert loaded.kind == kind


class TestSaveReviewKindSuffix:
    """Reconcile Subcommand Split step 8: pin the on-disk filename
    contract for the three live ``kind`` values. The detail and run
    reconcile audits write distinct ``-detail-reconcile.json`` /
    ``-run-reconcile.json`` suffixes so review-walk reuse and the
    ``_find_saved_*`` helpers can match by filename without parsing
    the body. The default ``review`` kind keeps the legacy bare-
    timestamp shape so existing saves round-trip."""

    def test_kind_detail_reconcile_writes_detail_suffix(
        self, tmp_path: Path
    ) -> None:
        fixed = datetime(2026, 5, 5, 12, 34, 56, tzinfo=timezone.utc)
        path = save_review(
            plan_slug="x",
            plan_path="plans/x.md",
            repo_root=tmp_path,
            report_md="",
            recommendations=[],
            now=fixed,
            kind="detail-reconcile",
            step_id=3,
        )
        assert path.name == "20260505-123456-detail-reconcile.json"

    def test_kind_run_reconcile_writes_run_suffix(
        self, tmp_path: Path
    ) -> None:
        fixed = datetime(2026, 5, 5, 12, 34, 56, tzinfo=timezone.utc)
        path = save_review(
            plan_slug="x",
            plan_path="plans/x.md",
            repo_root=tmp_path,
            report_md="",
            recommendations=[],
            now=fixed,
            kind="run-reconcile",
            step_id=4,
        )
        assert path.name == "20260505-123456-run-reconcile.json"

    def test_default_kind_keeps_legacy_filename(self, tmp_path: Path) -> None:
        """``kind="review"`` (the default) writes the bare-timestamp
        filename — no kind suffix — preserving the legacy shape that
        ``TestListSavedReviews`` / ``TestResolveSavedReview`` exercise."""
        fixed = datetime(2026, 5, 5, 12, 34, 56, tzinfo=timezone.utc)
        path = save_review(
            plan_slug="x",
            plan_path="plans/x.md",
            repo_root=tmp_path,
            report_md="",
            recommendations=[],
            now=fixed,
        )
        assert path.name == "20260505-123456.json"


class TestFingerprintPersistence:
    """Reuse Saved Completeness Audit step 1: ``plan_fingerprint`` and
    the opaque ``code_fingerprint`` (plus its ``code_fingerprint_present``
    marker) ride inside the v1 payload, survive save → load → annotate,
    and tolerate legacy sidecars that predate them."""

    def test_save_persists_plan_and_code_fingerprint(
        self, tmp_path: Path
    ) -> None:
        path = save_review(
            plan_slug="x",
            plan_path="plans/x.md",
            repo_root=tmp_path,
            report_md="",
            recommendations=[],
            plan_fingerprint="abc",
            code_fingerprint={"a.py": "h1"},
        )
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["plan_fingerprint"] == "abc"
        assert data["code_fingerprint"] == {"a.py": "h1"}
        assert data["code_fingerprint_present"] is True

    def test_round_trip_fingerprints(self, tmp_path: Path) -> None:
        path = save_review(
            plan_slug="x",
            plan_path="plans/x.md",
            repo_root=tmp_path,
            report_md="",
            recommendations=[],
            plan_fingerprint="abc",
            code_fingerprint={"a.py": "h1"},
        )
        loaded = load_review(path)
        assert loaded.plan_fingerprint == "abc"
        assert loaded.code_fingerprint == {"a.py": "h1"}
        assert loaded.code_fingerprint_present is True

    def test_save_defaults_fingerprints_empty(self, tmp_path: Path) -> None:
        path = save_review(
            plan_slug="x",
            plan_path="plans/x.md",
            repo_root=tmp_path,
            report_md="",
            recommendations=[],
        )
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["plan_fingerprint"] == ""
        assert data["code_fingerprint"] == {}
        assert data["code_fingerprint_present"] is False

    def test_save_computed_empty_code_fingerprint_marks_present(
        self, tmp_path: Path
    ) -> None:
        """An explicit empty dict (computed-but-empty watched-code
        surface) marks ``present == True`` — distinct from the ``None``
        default (never computed)."""
        path = save_review(
            plan_slug="x",
            plan_path="plans/x.md",
            repo_root=tmp_path,
            report_md="",
            recommendations=[],
            code_fingerprint={},
        )
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["code_fingerprint"] == {}
        assert data["code_fingerprint_present"] is True
        loaded = load_review(path)
        assert loaded.code_fingerprint == {}
        assert loaded.code_fingerprint_present is True

    def test_load_legacy_without_fingerprints_defaults(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "legacy.json"
        path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "plan_slug": "x",
                    "plan_path": "plans/x.md",
                    "created_at": "2026-01-01T00:00:00Z",
                    "report_md": "",
                    "recommendations": [],
                    "annotations": {},
                }
            ),
            encoding="utf-8",
        )
        loaded = load_review(path)
        assert loaded.plan_fingerprint == ""
        assert loaded.code_fingerprint == {}
        assert loaded.code_fingerprint_present is False

    def test_code_fingerprint_opaque_roundtrip(self, tmp_path: Path) -> None:
        fp = {"x/y.py": "deadbeef", "z.ts": "cafe"}
        path = save_review(
            plan_slug="x",
            plan_path="plans/x.md",
            repo_root=tmp_path,
            report_md="",
            recommendations=[],
            code_fingerprint=fp,
        )
        loaded = load_review(path)
        assert loaded.code_fingerprint == fp

    def test_update_annotation_preserves_fingerprints(
        self, tmp_path: Path
    ) -> None:
        path = save_review(
            plan_slug="x",
            plan_path="plans/x.md",
            repo_root=tmp_path,
            report_md="",
            recommendations=_SAMPLE_RECS,
            plan_fingerprint="abc",
            code_fingerprint={},
            detail_bundle_fingerprint={"plans/plan-details/x/1.md": "def"},
        )
        update_annotation(
            path,
            "step1-file-check-abc12345",
            Annotation("applied", "fixed"),
        )
        loaded = load_review(path)
        assert loaded.plan_fingerprint == "abc"
        assert loaded.code_fingerprint == {}
        assert loaded.code_fingerprint_present is True
        assert loaded.detail_bundle_fingerprint == {"plans/plan-details/x/1.md": "def"}
        assert loaded.detail_bundle_fingerprint_present is True


_STEP_IDS_PLAN = """---
title: Step Ids Plan
status: in-progress
priority: medium
steps:
  - id: 3
    title: Third
    status: pending
  - id: 1
    title: First
    status: pending
  - id: 2
    title: Second
    status: pending
---

# Step Ids Plan
"""


class TestStepIds:
    """BACKLOG #166: ``save_review`` computes ``step_ids`` / ``step_ids_present``
    either from a caller-supplied, already-parsed ``plan`` (skipping a
    re-parse and keeping the signal describing the same read as the
    caller's other fingerprints) or, when omitted, by self-parsing
    ``plan_path`` at save time — so every kind carries the signal with no
    call-site changes required. Either way a plan-parse failure must never
    break the save."""

    def test_save_prefers_a_caller_supplied_plan_over_reparsing(
        self, tmp_path: Path
    ) -> None:
        """When ``plan`` is supplied, ``step_ids`` reflects it directly —
        not a fresh read of ``plan_path`` (which may already differ, e.g. a
        concurrent edit, or simply because re-parsing is wasted work when
        the caller already has the exact plan it wants recorded)."""
        from plan_tool.parser import parse_plan_text

        plan_path = tmp_path / "plans" / "1-x.md"
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        # On-disk plan has steps {1, 2, 3}; the caller's in-hand ``plan``
        # (below) is a different, already-parsed object with steps {9}.
        plan_path.write_text(_STEP_IDS_PLAN, encoding="utf-8")
        in_hand_plan = parse_plan_text(
            "---\ntitle: T\nstatus: in-progress\npriority: medium\n"
            "steps:\n  - id: 9\n    title: Nine\n    status: pending\n"
            "---\n"
        )
        path = save_review(
            plan_slug="x",
            plan_path="plans/1-x.md",
            repo_root=tmp_path,
            report_md="",
            recommendations=[],
            plan=in_hand_plan,
        )
        loaded = load_review(path)
        assert loaded.step_ids == (9,)
        assert loaded.step_ids_present is True

    def test_save_persists_sorted_step_ids_from_a_parseable_plan(
        self, tmp_path: Path
    ) -> None:
        plan_path = tmp_path / "plans" / "1-x.md"
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(_STEP_IDS_PLAN, encoding="utf-8")
        path = save_review(
            plan_slug="x",
            plan_path="plans/1-x.md",
            repo_root=tmp_path,
            report_md="",
            recommendations=[],
        )
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["step_ids"] == [1, 2, 3]
        assert data["step_ids_present"] is True
        loaded = load_review(path)
        assert loaded.step_ids == (1, 2, 3)
        assert loaded.step_ids_present is True

    def test_save_without_a_readable_plan_records_not_present(
        self, tmp_path: Path
    ) -> None:
        """No plan file exists at ``plans/x.md`` — the parse fails, and the
        save must still succeed (fail-soft, never blocks an otherwise-good
        report save)."""
        path = save_review(
            plan_slug="x",
            plan_path="plans/x.md",
            repo_root=tmp_path,
            report_md="",
            recommendations=[],
        )
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["step_ids"] == []
        assert data["step_ids_present"] is False
        loaded = load_review(path)
        assert loaded.step_ids == ()
        assert loaded.step_ids_present is False

    def test_save_with_invalid_utf8_plan_records_not_present(
        self, tmp_path: Path
    ) -> None:
        """A decode failure is another fail-soft plan read."""
        plan_path = tmp_path / "plans" / "1-x.md"
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_bytes(b"\xff")

        path = save_review(
            plan_slug="x",
            plan_path="plans/1-x.md",
            repo_root=tmp_path,
            report_md="",
            recommendations=[],
        )

        loaded = load_review(path)
        assert loaded.step_ids == ()
        assert loaded.step_ids_present is False

    def test_update_annotation_preserves_step_ids(self, tmp_path: Path) -> None:
        plan_path = tmp_path / "plans" / "1-x.md"
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(_STEP_IDS_PLAN, encoding="utf-8")
        path = save_review(
            plan_slug="x",
            plan_path="plans/1-x.md",
            repo_root=tmp_path,
            report_md="",
            recommendations=_SAMPLE_RECS,
        )
        update_annotation(
            path,
            "step1-file-check-abc12345",
            Annotation("applied", "fixed"),
        )
        loaded = load_review(path)
        assert loaded.step_ids == (1, 2, 3)
        assert loaded.step_ids_present is True

    def test_load_legacy_without_step_ids_defaults(self, tmp_path: Path) -> None:
        path = tmp_path / "legacy.json"
        path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "plan_slug": "x",
                    "plan_path": "plans/x.md",
                    "created_at": "2026-01-01T00:00:00Z",
                    "report_md": "",
                    "recommendations": [],
                    "annotations": {},
                }
            ),
            encoding="utf-8",
        )
        loaded = load_review(path)
        assert loaded.step_ids == ()
        assert loaded.step_ids_present is False

    def test_load_rejects_malformed_step_ids_despite_present_marker(
        self, tmp_path: Path
    ) -> None:
        """A corrupt ``step_ids`` (non-int entry) never reads as present,
        even if the marker itself claims otherwise."""
        path = tmp_path / "corrupt.json"
        path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "plan_slug": "x",
                    "plan_path": "plans/x.md",
                    "created_at": "2026-01-01T00:00:00Z",
                    "report_md": "",
                    "recommendations": [],
                    "annotations": {},
                    "step_ids": [1, "two", 3],
                    "step_ids_present": True,
                }
            ),
            encoding="utf-8",
        )
        loaded = load_review(path)
        assert loaded.step_ids == ()
        assert loaded.step_ids_present is False


def _write_plan_with_bundle(
    repo_root: Path,
    *,
    plan_body: str = "# Plan\n",
    detail_files: Optional[dict[str, str]] = None,
) -> Path:
    """Lay down ``plans/1-x.md`` plus a ``plan-details/x/`` bundle and
    return the absolute plan path. ``detail_files`` maps filename → body."""
    plan_path = repo_root / _PLAN_REL
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(plan_body, encoding="utf-8")
    if detail_files:
        bundle = plan_path.parent / "plan-details" / "x"
        bundle.mkdir(parents=True, exist_ok=True)
        for name, body in detail_files.items():
            (bundle / name).write_text(body, encoding="utf-8")
    return plan_path


class TestComputePlanFingerprint:
    """Reuse Saved Completeness Audit step 1: the plan-side digest covers
    the plan markdown plus every ``plan-details/<slug>/*.md`` file, is
    enumeration-order-independent, and moves when any plan byte, detail
    byte, or the detail-file set changes."""

    def test_compute_plan_fingerprint_deterministic(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_plan_with_bundle(
            tmp_path,
            detail_files={"01-a.md": "alpha", "02-b.md": "beta"},
        )
        assert compute_plan_fingerprint(plan_path) == compute_plan_fingerprint(
            plan_path
        )

    def test_compute_plan_fingerprint_changes_on_plan_or_detail_edit(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_plan_with_bundle(
            tmp_path,
            detail_files={"01-a.md": "alpha"},
        )
        base = compute_plan_fingerprint(plan_path)
        plan_path.write_text("# Plan edited\n", encoding="utf-8")
        after_plan_edit = compute_plan_fingerprint(plan_path)
        assert after_plan_edit != base
        (plan_path.parent / "plan-details" / "x" / "01-a.md").write_text(
            "alpha edited", encoding="utf-8"
        )
        after_detail_edit = compute_plan_fingerprint(plan_path)
        assert after_detail_edit != after_plan_edit

    def test_compute_plan_fingerprint_changes_on_detail_set_change(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_plan_with_bundle(
            tmp_path,
            detail_files={"01-a.md": "alpha"},
        )
        base = compute_plan_fingerprint(plan_path)
        bundle = plan_path.parent / "plan-details" / "x"
        # Adding a detail file changes the digest.
        (bundle / "02-b.md").write_text("beta", encoding="utf-8")
        with_added = compute_plan_fingerprint(plan_path)
        assert with_added != base
        # Deleting one changes it again.
        (bundle / "02-b.md").unlink()
        assert compute_plan_fingerprint(plan_path) == base
        # A stray non-.md file in the bundle dir does NOT affect the digest.
        (bundle / "notes.txt").write_text("ignore", encoding="utf-8")
        assert compute_plan_fingerprint(plan_path) == base

    def test_generated_handoff_does_not_change_plan_fingerprint(
        self, tmp_path: Path
    ) -> None:
        """A companion developer-handoff under ``jira-handoffs/<slug>/`` is
        outside the ``plan-details/<slug>/*.md`` glob this digest walks, so
        creating or editing one never moves the plan fingerprint."""
        plan_path = _write_plan_with_bundle(
            tmp_path,
            detail_files={"01-a.md": "alpha"},
        )
        base = compute_plan_fingerprint(plan_path)

        handoff_dir = plan_path.parent / "jira-handoffs" / "x"
        handoff_dir.mkdir(parents=True)
        handoff = handoff_dir / "jira-stories.developer-handoff.md"
        handoff.write_text("# Developer handoff\n", encoding="utf-8")
        assert compute_plan_fingerprint(plan_path) == base

        handoff.write_text("# Developer handoff, edited\n", encoding="utf-8")
        assert compute_plan_fingerprint(plan_path) == base

    def test_compute_plan_fingerprint_no_detail_bundle(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_plan_with_bundle(tmp_path)
        digest = compute_plan_fingerprint(plan_path)
        assert digest
        assert digest == compute_plan_fingerprint(plan_path)

    def test_compute_plan_fingerprint_non_empty_even_when_plan_missing(
        self, tmp_path: Path
    ) -> None:
        # The digest is always a non-empty 64-char hex string — a missing or
        # unreadable plan contributes nothing rather than yielding "". This is
        # what keeps the empty-fingerprint staleness gap closed *at the source*:
        # every save path persists ``compute_plan_fingerprint(...)`` as its
        # ``plan_fingerprint``, so a persisted merge/re-ground directive can
        # never carry an empty fingerprint — which ``_saved_directive_is_stale``
        # (review_actions) and the scope-out guard (convergence_cmd) treat as
        # "freshness unknown". Regression-guards that closed-at-source invariant
        # so the deliberate "empty == unknown" guard behavior stays unreachable.
        missing = tmp_path / "does-not-exist.md"
        digest = compute_plan_fingerprint(missing)
        assert digest  # non-empty
        assert len(digest) == 64  # sha256 hex, never ""


class TestListSavedReviews:
    def test_empty_when_no_dir(self, tmp_path: Path) -> None:
        assert list_saved_reviews("nope", tmp_path) == []

    def test_newest_first(self, tmp_path: Path) -> None:
        save_review(
            plan_slug="x", plan_path=_PLAN_REL, repo_root=tmp_path,
            report_md="", recommendations=[],
            now=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        )
        save_review(
            plan_slug="x", plan_path=_PLAN_REL, repo_root=tmp_path,
            report_md="", recommendations=[],
            now=datetime(2026, 5, 5, 12, 0, 0, tzinfo=timezone.utc),
        )
        save_review(
            plan_slug="x", plan_path=_PLAN_REL, repo_root=tmp_path,
            report_md="", recommendations=[],
            now=datetime(2026, 3, 15, 0, 0, 0, tzinfo=timezone.utc),
        )
        paths = list_saved_reviews("x", tmp_path, plan_path=_plan_abs(tmp_path))
        assert [p.name for p in paths] == [
            "20260505-120000.json",
            "20260315-000000.json",
            "20260101-000000.json",
        ]

    def test_ignores_non_json(self, tmp_path: Path) -> None:
        save_review(
            plan_slug="x", plan_path=_PLAN_REL, repo_root=tmp_path,
            report_md="", recommendations=[],
        )
        # Drop a stray file in the reports dir.
        (plan_reports_dir(_plan_abs(tmp_path)) / "notes.txt").write_text(
            "ignore me", encoding="utf-8"
        )
        paths = list_saved_reviews("x", tmp_path, plan_path=_plan_abs(tmp_path))
        assert all(p.suffix == ".json" for p in paths)


class TestUpdateAnnotation:
    def test_update_annotation_preserves_audit_coverage(self, tmp_path: Path) -> None:
        path = save_review(
            plan_slug="x", plan_path=_PLAN_REL, repo_root=tmp_path,
            report_md="report", recommendations=_SAMPLE_RECS,
            kind="completeness", audit_coverage=_AUDIT_COVERAGE,
        )

        update_annotation(path, _SAMPLE_RECS[0].id, Annotation(status="applied"))

        assert load_review(path).audit_coverage == _AUDIT_COVERAGE

    def test_update_annotation_preserves_plan_mass(self, tmp_path: Path) -> None:
        """#238: an annotation write must not silently strip the sidecar's
        plan-mass snapshot — the rewrite path forwards it exactly like
        audit_coverage/audit_shape_advisory/is_pre_apply_checkpoint."""
        mass = {"step_count": 3, "detail_bundle_bytes": 120}
        path = save_review(
            plan_slug="x", plan_path=_PLAN_REL, repo_root=tmp_path,
            report_md="report", recommendations=_SAMPLE_RECS,
            kind="completeness", plan_mass=mass,
        )

        update_annotation(path, _SAMPLE_RECS[0].id, Annotation(status="applied"))

        assert load_review(path).plan_mass == mass

    def test_update_annotation_preserves_audit_stage(self, tmp_path: Path) -> None:
        path = save_review(
            plan_slug="x", plan_path=_PLAN_REL, repo_root=tmp_path,
            report_md="report", recommendations=_SAMPLE_RECS,
            kind="completeness", audit_stage="detail",
        )

        update_annotation(path, _SAMPLE_RECS[0].id, Annotation(status="applied"))

        assert load_review(path).audit_stage == "detail"

    def test_writes_only_annotations(self, tmp_path: Path) -> None:
        path = save_review(
            plan_slug="x",
            plan_path="plans/x.md",
            repo_root=tmp_path,
            report_md="report body",
            recommendations=_SAMPLE_RECS,
        )
        update_annotation(
            path,
            "step1-file-check-abc12345",
            Annotation(status="applied", note="fixed"),
        )
        loaded = load_review(path)
        # Annotation persisted.
        assert loaded.annotations == {
            "step1-file-check-abc12345": Annotation("applied", "fixed"),
        }
        # report_md and recommendations unchanged.
        assert loaded.report_md == "report body"
        assert loaded.recommendations == _SAMPLE_RECS

    def test_overwrites_existing_annotation(self, tmp_path: Path) -> None:
        path = save_review(
            plan_slug="x",
            plan_path="plans/x.md",
            repo_root=tmp_path,
            report_md="",
            recommendations=_SAMPLE_RECS,
        )
        update_annotation(
            path, "step1-file-check-abc12345",
            Annotation("skip", "deferred"),
        )
        update_annotation(
            path, "step1-file-check-abc12345",
            Annotation("applied", "actually fixed"),
        )
        loaded = load_review(path)
        assert loaded.annotations[
            "step1-file-check-abc12345"
        ] == Annotation("applied", "actually fixed")

    def test_multiple_annotations_coexist(self, tmp_path: Path) -> None:
        path = save_review(
            plan_slug="x",
            plan_path="plans/x.md",
            repo_root=tmp_path,
            report_md="",
            recommendations=_SAMPLE_RECS,
        )
        update_annotation(
            path, "step1-file-check-abc12345",
            Annotation("applied", "a"),
        )
        update_annotation(
            path, "step2-deps-deadbeef",
            Annotation("skip", "b"),
        )
        loaded = load_review(path)
        assert len(loaded.annotations) == 2


class TestCheckpointRole:
    """The persisted checkpoint / final / unknown role matrix."""

    def test_save_writes_v3_true_checkpoint_marker_for_completeness(
        self, tmp_path: Path
    ) -> None:
        path = save_review(
            plan_slug="x", plan_path=_PLAN_REL, repo_root=tmp_path,
            report_md="report", recommendations=_SAMPLE_RECS,
            kind="completeness", is_pre_apply_checkpoint=True,
            audit_coverage=_AUDIT_COVERAGE,
            audit_shape_advisory=_SAMPLE_ADVISORY,
        )

        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["version"] == 3
        assert payload["is_pre_apply_checkpoint"] is True

        loaded = load_review(path)
        assert loaded.is_pre_apply_checkpoint is True
        # The checkpoint stays usable crash-recovery evidence: the role fence
        # must not cost it its report, findings, or other completeness metadata.
        assert loaded.report_md == "report"
        assert loaded.recommendations == _SAMPLE_RECS
        assert loaded.audit_coverage == _AUDIT_COVERAGE
        assert loaded.audit_shape_advisory == _SAMPLE_ADVISORY

    def test_save_refuses_checkpoint_role_on_a_non_completeness_sidecar(
        self, tmp_path: Path
    ) -> None:
        with pytest.raises(ValueError, match="completeness"):
            save_review(
                plan_slug="x", plan_path=_PLAN_REL, repo_root=tmp_path,
                report_md="report", recommendations=_SAMPLE_RECS,
                kind="run-reconcile", is_pre_apply_checkpoint=True,
            )

    @pytest.mark.parametrize(
        ("advisory", "expected_version"),
        [(None, 1), (_SAMPLE_ADVISORY, 2)],
        ids=["plain", "advisory"],
    )
    def test_final_save_omits_checkpoint_marker_and_retains_current_version(
        self,
        tmp_path: Path,
        advisory: Optional[AuditShapeAdvisory],
        expected_version: int,
    ) -> None:
        path = save_review(
            plan_slug="x", plan_path=_PLAN_REL, repo_root=tmp_path,
            report_md="report", recommendations=_SAMPLE_RECS,
            kind="completeness", audit_shape_advisory=advisory,
        )

        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["version"] == expected_version
        assert "is_pre_apply_checkpoint" not in payload
        assert load_review(path).is_pre_apply_checkpoint is False

    def test_load_v3_explicit_false_checkpoint_marker_is_final(
        self, tmp_path: Path
    ) -> None:
        path = _write_raw_sidecar(tmp_path / "raw.json", version=3, marker=False)

        assert load_review(path).is_pre_apply_checkpoint is False

    @pytest.mark.parametrize("version", [1, 2])
    def test_load_unmarked_v1_v2_legacy_checkpoint_role_is_final(
        self, tmp_path: Path, version: int
    ) -> None:
        path = _write_raw_sidecar(tmp_path / "raw.json", version=version)

        loaded = load_review(path)
        assert loaded.is_pre_apply_checkpoint is False
        assert loaded.recommendations == [_SAMPLE_RECS[0]]

    @pytest.mark.parametrize(
        "marker",
        ["true", "false", "unknown", 1, 0, 1.0, None, [], {}, [True]],
        ids=[
            "str-true", "str-false", "str-unknown", "int-1", "int-0",
            "float", "null", "empty-list", "empty-dict", "list-of-bool",
        ],
    )
    def test_load_invalid_checkpoint_marker_is_unknown(
        self, tmp_path: Path, marker: object
    ) -> None:
        path = _write_raw_sidecar(tmp_path / "raw.json", version=3, marker=marker)

        loaded = load_review(path)
        assert loaded.is_pre_apply_checkpoint is None
        assert loaded.recommendations == [_SAMPLE_RECS[0]]

    @pytest.mark.parametrize(
        ("version", "kind", "marker"),
        [
            (3, "review", True),
            (3, "run-reconcile", False),
            (1, "completeness", True),
            (1, "completeness", False),
            (2, "completeness", True),
        ],
        ids=[
            "v3-review", "v3-run-reconcile", "v1-true", "v1-false", "v2-true",
        ],
    )
    def test_load_marker_on_non_completeness_or_legacy_version_is_unknown(
        self, tmp_path: Path, version: int, kind: str, marker: bool
    ) -> None:
        path = _write_raw_sidecar(
            tmp_path / "raw.json", version=version, kind=kind, marker=marker
        )

        loaded = load_review(path)
        assert loaded.is_pre_apply_checkpoint is None
        assert loaded.recommendations == [_SAMPLE_RECS[0]]

    @pytest.mark.parametrize("kind", ["completeness", "review"])
    def test_load_markerless_v3_sidecar_is_unknown(
        self, tmp_path: Path, kind: str
    ) -> None:
        path = _write_raw_sidecar(tmp_path / "raw.json", version=3, kind=kind)

        loaded = load_review(path)
        assert loaded.is_pre_apply_checkpoint is None
        assert loaded.recommendations == [_SAMPLE_RECS[0]]

    def test_role_unaware_reader_rejects_v3_checkpoint(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = save_review(
            plan_slug="x", plan_path=_PLAN_REL, repo_root=tmp_path,
            report_md="report", recommendations=_SAMPLE_RECS,
            kind="completeness", is_pre_apply_checkpoint=True,
        )
        # Stand in for a build that predates the role: it must refuse the file
        # rather than read a checkpoint whose marker it cannot interpret.
        monkeypatch.setattr(rp, "_SUPPORTED_SCHEMA_VERSIONS", (1, 2))

        with pytest.raises(ReviewLoadError, match="schema version"):
            load_review(path)

    def test_update_annotation_preserves_checkpoint_role_and_v3_matrix(
        self, tmp_path: Path
    ) -> None:
        annotation = Annotation(status="applied", note="walked")
        checkpoint = save_review(
            plan_slug="x", plan_path=_PLAN_REL, repo_root=tmp_path,
            report_md="report", recommendations=_SAMPLE_RECS,
            kind="completeness", is_pre_apply_checkpoint=True,
            audit_shape_advisory=_SAMPLE_ADVISORY,
        )
        final = save_review(
            plan_slug="y", plan_path="plans/1-y.md", repo_root=tmp_path,
            report_md="report", recommendations=_SAMPLE_RECS,
            kind="completeness",
        )
        v3_final = _write_raw_sidecar(
            tmp_path / "explicit-v3-final.json", version=3, marker=False
        )
        unknown_paths = [
            _write_raw_sidecar(tmp_path / "legacy-marker.json", version=1, marker=True),
            _write_raw_sidecar(tmp_path / "markerless-v3.json", version=3),
            _write_raw_sidecar(tmp_path / "bad-marker.json", version=3, marker="yes"),
        ]

        for path in [checkpoint, final, v3_final, *unknown_paths]:
            update_annotation(path, "step1-file-check-abc12345", annotation)

        reloaded_checkpoint = load_review(checkpoint)
        assert reloaded_checkpoint.is_pre_apply_checkpoint is True
        assert reloaded_checkpoint.schema_version == 3
        assert reloaded_checkpoint.audit_shape_advisory == _SAMPLE_ADVISORY
        assert reloaded_checkpoint.annotations == {
            "step1-file-check-abc12345": annotation
        }

        final_payload = json.loads(final.read_text(encoding="utf-8"))
        assert "is_pre_apply_checkpoint" not in final_payload
        assert final_payload["version"] == 1
        assert load_review(final).is_pre_apply_checkpoint is False

        v3_final_payload = json.loads(v3_final.read_text(encoding="utf-8"))
        assert v3_final_payload["version"] == 3
        assert v3_final_payload["is_pre_apply_checkpoint"] is False
        assert load_review(v3_final).is_pre_apply_checkpoint is False

        for path in unknown_paths:
            assert load_review(path).is_pre_apply_checkpoint is None, path


def test_sampler_checkpoint_path_is_stable_and_outside_completeness_stems(
    tmp_path: Path,
) -> None:
    plan_path = _plan_abs(tmp_path)
    checkpoint = sampler_checkpoint_path(plan_path)

    assert checkpoint.parent == plan_reports_dir(plan_path)
    assert checkpoint.name == rp.SAMPLER_CHECKPOINT_FILENAME
    assert not checkpoint.name.endswith(rp.COMPLETENESS_REPORT_SUFFIX)
    assert not checkpoint.name.endswith(rp.COMPLETENESS_SIDECAR_SUFFIX)
    assert checkpoint.name != rp._timestamp_filename(kind="completeness")


def test_save_sampler_checkpoint_replaces_the_same_artifact_and_round_trips_state(
    tmp_path: Path,
) -> None:
    first = save_sampler_checkpoint(
        plan_slug="x", plan_path=_PLAN_REL, repo_root=tmp_path,
        report_md="first", recommendations=_SAMPLE_RECS,
        sampler_state={"lifecycle": "in-progress", "next_pass": 2},
    )
    second = save_sampler_checkpoint(
        plan_slug="x", plan_path=_PLAN_REL, repo_root=tmp_path,
        report_md="second", recommendations=_SAMPLE_RECS,
        sampler_state={"lifecycle": "in-progress", "next_pass": 3},
    )

    assert first == second == sampler_checkpoint_path(_plan_abs(tmp_path))
    assert [path.name for path in plan_reports_dir(_plan_abs(tmp_path)).glob("*.json")] == [
        rp.SAMPLER_CHECKPOINT_FILENAME
    ]
    loaded = load_review(second)
    assert loaded.report_md == "second"
    assert loaded.recommendations == _SAMPLE_RECS
    assert loaded.sampler_state == {"lifecycle": "in-progress", "next_pass": 3}


def test_sampler_checkpoint_uses_a_nonfinal_role(tmp_path: Path) -> None:
    path = save_sampler_checkpoint(
        plan_slug="x", plan_path=_PLAN_REL, repo_root=tmp_path,
        report_md="checkpoint", recommendations=[],
        sampler_state={"lifecycle": "in-progress"},
    )

    loaded = load_review(path)
    assert loaded.schema_version == 4
    assert loaded.is_pre_apply_checkpoint is True
    assert loaded.is_in_progress_sampler_checkpoint
    assert loaded.is_pre_apply_checkpoint is not False
    assert json.loads(path.read_text(encoding="utf-8"))["qualified_result"] is None


def test_terminal_sampler_residue_uses_the_nonresumable_lifecycle(
    tmp_path: Path,
) -> None:
    path = save_sampler_checkpoint(
        plan_slug="x", plan_path=_PLAN_REL, repo_root=tmp_path,
        report_md="terminal residue", recommendations=[],
        sampler_state={"lifecycle": "terminal-residue", "next_pass": 4},
    )

    loaded = load_review(path)
    assert loaded.sampler_state == {"lifecycle": "terminal-residue", "next_pass": 4}
    assert not loaded.is_in_progress_sampler_checkpoint
    assert load_sampler_checkpoint(_plan_abs(tmp_path)).status == "valid"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload.update({"is_pre_apply_checkpoint": False}),
        lambda payload: payload.update({"kind": "review"}),
        lambda payload: payload.update({"sampler_state": []}),
    ],
    ids=["final-marker", "non-completeness-kind", "invalid-state-shape"],
)
def test_sampler_state_with_a_final_or_invalid_role_fails_closed(
    tmp_path: Path, mutate: object,
) -> None:
    path = save_sampler_checkpoint(
        plan_slug="x", plan_path=_PLAN_REL, repo_root=tmp_path,
        report_md="checkpoint", recommendations=[],
        sampler_state={"lifecycle": "in-progress"},
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert callable(mutate)
    mutate(payload)
    path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_review(path)
    assert loaded.is_pre_apply_checkpoint is None
    assert not loaded.is_in_progress_sampler_checkpoint


def test_load_sampler_checkpoint_declines_absent_or_unreadable_artifacts(
    tmp_path: Path,
) -> None:
    plan_path = _plan_abs(tmp_path)
    assert load_sampler_checkpoint(plan_path).status == "absent"

    checkpoint = sampler_checkpoint_path(plan_path)
    checkpoint.parent.mkdir(parents=True)
    checkpoint.write_text("not json", encoding="utf-8")

    declined = load_sampler_checkpoint(plan_path)
    assert declined.status == "unreadable"
    assert declined.review is None

    _write_raw_sidecar(checkpoint, version=4, marker=True)
    non_sampler = load_sampler_checkpoint(plan_path)
    assert non_sampler.status == "not-sampler"
    assert non_sampler.review is None


def test_update_annotation_preserves_sampler_checkpoint_state_and_nonfinal_role(
    tmp_path: Path,
) -> None:
    state = {"lifecycle": "in-progress", "next_pass": 2}
    path = save_sampler_checkpoint(
        plan_slug="x", plan_path=_PLAN_REL, repo_root=tmp_path,
        report_md="checkpoint", recommendations=_SAMPLE_RECS, sampler_state=state,
    )

    update_annotation(path, _SAMPLE_RECS[0].id, Annotation(status="applied"))

    loaded = load_review(path)
    assert loaded.sampler_state == state
    assert loaded.is_pre_apply_checkpoint is True
    assert loaded.is_in_progress_sampler_checkpoint


def test_list_saved_reviews_keeps_sampler_checkpoint_in_the_raw_listing(
    tmp_path: Path,
) -> None:
    save_review(
        plan_slug="x", plan_path=_PLAN_REL, repo_root=tmp_path,
        report_md="final", recommendations=[],
    )
    checkpoint = save_sampler_checkpoint(
        plan_slug="x", plan_path=_PLAN_REL, repo_root=tmp_path,
        report_md="checkpoint", recommendations=[],
        sampler_state={"lifecycle": "in-progress"},
    )

    paths = list_saved_reviews("x", tmp_path, plan_path=_plan_abs(tmp_path))
    assert checkpoint in paths


@pytest.mark.parametrize("lifecycle", ("in-progress", "terminal-residue"))
def test_sampler_checkpoint_lifecycles_are_rejected_by_each_final_evidence_reader(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    lifecycle: str,
) -> None:
    """Keep either sampler lifecycle out of every current final-evidence gate."""
    from plan_tool.cli import data_contract_cmd
    from plan_tool.cli.completeness_phases import _saved_audit_revision_is_current
    from plan_tool.cli.data_contract_cmd import (
        _newest_saved_completeness_with_contract_payload,
        cmd_data_contract_apply,
    )
    from plan_tool.cli.review_cmd import (
        _direct_walk_role_ineligibility,
        _review_reuse_ineligibility,
    )
    from plan_tool.completeness_report import (
        is_reusable_audit_sidecar,
        resolve_reusable_audit,
    )
    from plan_tool.convergence_diagnosis import load_report_history

    plan_path = _plan_abs(tmp_path)
    checkpoint = save_sampler_checkpoint(
        plan_slug="x",
        plan_path=_PLAN_REL,
        repo_root=tmp_path,
        report_md="sampler checkpoint",
        recommendations=_SAMPLE_RECS,
        sampler_state={"lifecycle": lifecycle},
    )
    saved = load_review(checkpoint)

    assert is_reusable_audit_sidecar(saved) is False
    assert resolve_reusable_audit("x", tmp_path, plan_path=plan_path) is None
    assert _saved_audit_revision_is_current(saved, plan_path, tmp_path) is False
    assert _review_reuse_ineligibility(saved) is not None
    assert _direct_walk_role_ineligibility(saved) is not None
    assert load_report_history(plan_path).runs == []
    with pytest.raises(FileNotFoundError, match="no current final qualified"):
        _newest_saved_completeness_with_contract_payload(
            "x", tmp_path, plan_path=plan_path
        )

    context = SimpleNamespace(repo_root=tmp_path)
    monkeypatch.setattr(data_contract_cmd, "_load_context", lambda _: context)
    monkeypatch.setattr(
        data_contract_cmd,
        "resolve_plan_for_context",
        lambda _ctx, _name: plan_path,
    )
    monkeypatch.setattr(
        data_contract_cmd,
        "resolve_saved_review",
        lambda *_args, **_kwargs: checkpoint,
    )
    monkeypatch.setattr(
        data_contract_cmd,
        "_load_payloads",
        lambda _path: pytest.fail("ineligible sampler must not read payloads"),
    )

    assert cmd_data_contract_apply(SimpleNamespace(name="x", id=checkpoint.stem)) == 2
    assert "not final current qualified evidence" in capsys.readouterr().err


@pytest.mark.parametrize("lifecycle", ("in-progress", "terminal-residue"))
def test_direct_saved_review_walk_rejects_stable_sampler_checkpoint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    lifecycle: str,
) -> None:
    """Reject stable sampler evidence before either direct-walk selection can walk it."""
    from plan_tool.cli import review_cmd
    from plan_tool.cli.review_cmd import cmd_review_walk
    from plan_tool.locator import PlanToolContext

    plan_path = _plan_abs(tmp_path)
    plan_path.parent.mkdir(parents=True)
    plan_path.write_text("# Plan\n", encoding="utf-8")
    checkpoint = save_sampler_checkpoint(
        plan_slug="x",
        plan_path=_PLAN_REL,
        repo_root=tmp_path,
        report_md="sampler checkpoint",
        recommendations=_SAMPLE_RECS,
        sampler_state={"lifecycle": lifecycle},
    )
    context = PlanToolContext(repo_root=tmp_path, plans_dir=None, entries=[])
    monkeypatch.setattr(review_cmd, "_load_context", lambda _: context)
    monkeypatch.setattr(
        review_cmd,
        "resolve_plan_for_context",
        lambda _ctx, _name: plan_path,
    )
    monkeypatch.setattr(
        review_cmd,
        "walk_recommendations",
        lambda *_args, **_kwargs: pytest.fail(
            "ineligible sampler must not start a recommendation walk"
        ),
    )

    default_args = SimpleNamespace(
        name="x", id=None, rewalk=False, include_info=False
    )
    assert cmd_review_walk(default_args) == 2
    assert "no current final qualified completeness audit" in capsys.readouterr().err

    explicit_args = SimpleNamespace(
        name="x", id=checkpoint.name, rewalk=False, include_info=False
    )
    assert cmd_review_walk(explicit_args) == 2
    assert "is a sampler checkpoint, not a final saved review" in capsys.readouterr().err


class TestResolveSavedReview:
    def test_picks_newest_by_default(self, tmp_path: Path) -> None:
        save_review(
            plan_slug="x", plan_path=_PLAN_REL, repo_root=tmp_path,
            report_md="", recommendations=[],
            now=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        )
        save_review(
            plan_slug="x", plan_path=_PLAN_REL, repo_root=tmp_path,
            report_md="", recommendations=[],
            now=datetime(2026, 5, 5, 12, 0, 0, tzinfo=timezone.utc),
        )
        path = resolve_saved_review("x", tmp_path, plan_path=_plan_abs(tmp_path))
        assert path.name == "20260505-120000.json"

    def test_explicit_id_resolves(self, tmp_path: Path) -> None:
        save_review(
            plan_slug="x", plan_path=_PLAN_REL, repo_root=tmp_path,
            report_md="", recommendations=[],
            now=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        )
        save_review(
            plan_slug="x", plan_path=_PLAN_REL, repo_root=tmp_path,
            report_md="", recommendations=[],
            now=datetime(2026, 5, 5, 12, 0, 0, tzinfo=timezone.utc),
        )
        path = resolve_saved_review(
            "x", tmp_path, review_id="20260101-000000",
            plan_path=_plan_abs(tmp_path),
        )
        assert path.name == "20260101-000000.json"

    def test_explicit_id_with_extension_resolves(self, tmp_path: Path) -> None:
        save_review(
            plan_slug="x", plan_path=_PLAN_REL, repo_root=tmp_path,
            report_md="", recommendations=[],
            now=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        )
        path = resolve_saved_review(
            "x", tmp_path, review_id="20260101-000000.json",
            plan_path=_plan_abs(tmp_path),
        )
        assert path.name == "20260101-000000.json"

    def test_explicit_id_can_resolve_a_checkpoint_for_recovery_readers(
        self, tmp_path: Path
    ) -> None:
        checkpoint = save_review(
            plan_slug="x", plan_path=_PLAN_REL, repo_root=tmp_path,
            report_md="", recommendations=[], kind="completeness",
            is_pre_apply_checkpoint=True,
            now=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        )

        assert resolve_saved_review(
            "x", tmp_path, review_id=checkpoint.stem,
            plan_path=_plan_abs(tmp_path),
        ) == checkpoint

    def test_missing_id_raises(self, tmp_path: Path) -> None:
        save_review(
            plan_slug="x", plan_path=_PLAN_REL, repo_root=tmp_path,
            report_md="", recommendations=[],
        )
        with pytest.raises(FileNotFoundError):
            resolve_saved_review(
                "x", tmp_path, review_id="nope",
                plan_path=_plan_abs(tmp_path),
            )

    def test_no_reviews_at_all_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            resolve_saved_review("x", tmp_path)

    def test_no_id_skips_the_in_progress_sampler_checkpoint(
        self, tmp_path: Path
    ) -> None:
        """The checkpoint's fixed filename sorts lexically ahead of every
        timestamped save; without an id, "newest" must still mean the
        newest real saved review, never the recovery checkpoint."""
        save_review(
            plan_slug="x", plan_path=_PLAN_REL, repo_root=tmp_path,
            report_md="", recommendations=[],
            now=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        )
        save_sampler_checkpoint(
            plan_slug="x", plan_path=_PLAN_REL, repo_root=tmp_path,
            report_md="checkpoint", recommendations=[],
            sampler_state={"lifecycle": "in-progress"},
        )

        path = resolve_saved_review("x", tmp_path, plan_path=_plan_abs(tmp_path))

        assert path.name == "20260101-000000.json"

    def test_no_id_raises_when_only_a_sampler_checkpoint_exists(
        self, tmp_path: Path
    ) -> None:
        save_sampler_checkpoint(
            plan_slug="x", plan_path=_PLAN_REL, repo_root=tmp_path,
            report_md="checkpoint", recommendations=[],
            sampler_state={"lifecycle": "in-progress"},
        )

        with pytest.raises(FileNotFoundError):
            resolve_saved_review("x", tmp_path, plan_path=_plan_abs(tmp_path))


class TestAtomicJsonWrite:
    """Bug-backlog-drain step 7: ``save_review`` and ``update_annotation``
    write JSON atomically via ``_atomic_write_text`` (tempfile +
    ``os.replace``). An interrupt or ``OSError`` mid-write leaves the
    target either untouched (first save) or holding its prior valid
    JSON (overwrite), never truncated — and the tempfile is unlinked
    rather than left as an orphan."""

    def test_save_review_replace_failure_leaves_no_target_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _raising_replace(src, dst):
            raise OSError("disk full")

        monkeypatch.setattr(os, "replace", _raising_replace)
        with pytest.raises(OSError, match="disk full"):
            save_review(
                plan_slug="x",
                plan_path="plans/x.md",
                repo_root=tmp_path,
                report_md="md",
                recommendations=_SAMPLE_RECS,
            )
        target_dir = plan_reports_dir(tmp_path / "plans" / "x.md")
        # Directory was created by save_review's mkdir, but no .json
        # file landed inside it (replace was the last step and it failed).
        assert target_dir.is_dir()
        assert list(target_dir.glob("*.json")) == []
        # No tempfile orphan either — _atomic_write_text's cleanup ran.
        assert list(target_dir.glob(".*.tmp")) == []

    def test_update_annotation_replace_failure_preserves_prior_content(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Save once cleanly so we have a prior valid file to overwrite.
        path = save_review(
            plan_slug="x",
            plan_path="plans/x.md",
            repo_root=tmp_path,
            report_md="report body",
            recommendations=_SAMPLE_RECS,
            annotations={
                "step1-file-check-abc12345": Annotation("applied", "first"),
            },
        )
        pre_bytes = path.read_bytes()
        pre_loaded = load_review(path)

        # Now break os.replace and try to update.
        def _raising_replace(src, dst):
            raise OSError("simulated rename failure")

        monkeypatch.setattr(os, "replace", _raising_replace)
        with pytest.raises(OSError, match="simulated rename failure"):
            update_annotation(
                path,
                "step1-file-check-abc12345",
                Annotation("skip", "second"),
            )

        # Prior file content survived intact.
        assert path.read_bytes() == pre_bytes
        # Re-loading via load_review (which parses the JSON) yields
        # the pre-mutation snapshot. Load-bearing recovery assertion.
        post_loaded = load_review(path)
        assert post_loaded.annotations == pre_loaded.annotations
        assert post_loaded.report_md == pre_loaded.report_md
        assert post_loaded.recommendations == pre_loaded.recommendations
        # And the raw bytes still parse as JSON.
        json.loads(path.read_text(encoding="utf-8"))

    def test_replace_failure_does_not_leak_tempfile(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _raising_replace(src, dst):
            raise OSError("disk full")

        monkeypatch.setattr(os, "replace", _raising_replace)
        with pytest.raises(OSError):
            save_review(
                plan_slug="x",
                plan_path="plans/x.md",
                repo_root=tmp_path,
                report_md="",
                recommendations=[],
            )
        target_dir = plan_reports_dir(tmp_path / "plans" / "x.md")
        # No .tmp orphan remains — the helper's cleanup path ran.
        assert list(target_dir.glob(".*.tmp")) == []
        # Belt-and-suspenders: walk the whole tree for any .tmp leftover.
        leftover = [p for p in target_dir.rglob("*") if p.name.endswith(".tmp")]
        assert leftover == []


def test_detail_bundle_fingerprint_round_trips(tmp_path: Path) -> None:
    """A passed detail-bundle fingerprint survives save → load with its
    present-marker True (BACKLOG #61)."""
    from plan_tool.review_persistence import save_review, load_review

    fp = {"docs/details/01-x.md": "abc123"}
    path = save_review(
        plan_slug="x",
        plan_path="plans/x.md",
        repo_root=tmp_path,
        report_md="r",
        recommendations=[],
        detail_bundle_fingerprint=fp,
    )
    loaded = load_review(path)
    assert loaded.detail_bundle_fingerprint == fp
    assert loaded.detail_bundle_fingerprint_present is True


def test_detail_bundle_fingerprint_absent_marker(tmp_path: Path) -> None:
    """Omitting the fingerprint records present=False (distinct from an
    empty-but-computed bundle), mirroring the code_fingerprint marker."""
    from plan_tool.review_persistence import save_review, load_review

    path = save_review(
        plan_slug="x",
        plan_path="plans/x.md",
        repo_root=tmp_path,
        report_md="r",
        recommendations=[],
    )
    loaded = load_review(path)
    assert loaded.detail_bundle_fingerprint == {}
    assert loaded.detail_bundle_fingerprint_present is False


def test_audit_revision_round_trips_and_legacy_stays_unknown(tmp_path: Path) -> None:
    """A saved sampled revision is distinct from an older readable sidecar."""
    from plan_tool.review_persistence import (
        AuditInputSnapshot,
        load_review,
        project_saved_completeness_result,
        save_review,
    )

    plan_path = tmp_path / "plans" / "1-demo.md"
    plan_path.parent.mkdir(parents=True)
    plan_path.write_text(
        "---\n"
        "title: Demo\nstatus: planning\npriority: medium\nsteps:\n"
        "  - id: 1\n    title: First\n    detail: details/01-first.md\n"
        "---\n\n# Plan\n",
        encoding="utf-8",
    )
    detail = tmp_path / "details" / "01-first.md"
    detail.parent.mkdir()
    detail.write_text("# first\n", encoding="utf-8")
    snapshot = AuditInputSnapshot.capture(plan_path, tmp_path)
    current = save_review(
        plan_slug="demo",
        plan_path="plans/1-demo.md",
        repo_root=tmp_path,
        report_md="report",
        recommendations=[],
        kind="completeness",
        qualified_result={
            "headline": "clean",
            "stage": "detail",
            "coverage": "confirmed",
            "revision_status": "current",
            "audit_revision": snapshot.revision,
        },
    )
    for qualifier in ("coverage", "revision_status"):
        malformed = {
            "headline": "no-qualified-current-evidence",
            "stage": "detail",
            "coverage": "unconfirmed",
            "revision_status": "current",
            "audit_revision": snapshot.revision,
        }
        malformed[qualifier] = "not-sampled"
        with pytest.raises(ValueError, match="qualified_result"):
            save_review(
                plan_slug="malformed",
                plan_path="plans/1-demo.md",
                repo_root=tmp_path,
                report_md="report",
                recommendations=[],
                kind="completeness",
                qualified_result=malformed,
            )
    legacy = save_review(
        plan_slug="legacy",
        plan_path="plans/1-legacy.md",
        repo_root=tmp_path,
        report_md="report",
        recommendations=[],
        kind="completeness",
    )

    current_raw = json.loads(current.read_text(encoding="utf-8"))
    assert current_raw["version"] == 4
    assert "audit_revision" not in current_raw
    assert current_raw["qualified_result"]["audit_revision"] == snapshot.revision
    archived_bytes = current.read_bytes()
    assert load_review(current).audit_revision == snapshot.revision
    assert current.read_bytes() == archived_bytes
    assert load_review(legacy).audit_revision is None
    update_annotation(current, "example", Annotation(status="skip"))
    updated = load_review(current)
    assert updated.is_pre_apply_checkpoint is False
    assert updated.audit_revision == snapshot.revision
    assert updated.qualified_result == current_raw["qualified_result"]

    plan_path.write_text(plan_path.read_text(encoding="utf-8") + "\n# drift\n", encoding="utf-8")
    view = project_saved_completeness_result(updated, plan_path, tmp_path)
    assert view.view_revision_status == "stale"
    assert updated.qualified_result["revision_status"] == "current"


@pytest.mark.parametrize("version", [1, 2, 3])
def test_supported_v1_v2_and_v3_run_grade_revisions_normalize_with_historical_optional_digests(
    tmp_path: Path, version: int,
) -> None:
    """Older sampled reports stay reusable until a profile supplies new input."""
    from plan_tool.review_persistence import AuditInputSnapshot

    plan_path = tmp_path / "plans" / "1-demo.md"
    plan_path.parent.mkdir(parents=True)
    plan_path.write_text(
        "---\n"
        "title: Demo\nstatus: planning\npriority: medium\nsteps:\n"
        "  - id: 1\n    title: First\n"
        "---\n\n# Plan\n",
        encoding="utf-8",
    )
    snapshot = AuditInputSnapshot.capture(plan_path, tmp_path)
    legacy_v2 = dict(snapshot.revision)
    legacy_v2["version"] = version
    if version < 3:
        del legacy_v2["project_context_digest"]
    if version < 2:
        del legacy_v2["source_seed_digest"]

    assert rp.normalize_audit_revision(legacy_v2) == snapshot.revision


def test_grade_aware_capture_keeps_missing_and_unreadable_details(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every selected step stays in the revision even without readable bytes."""
    from plan_tool.review_persistence import AuditInputSnapshot

    plan_path = tmp_path / "plans" / "1-demo.md"
    plan_path.parent.mkdir(parents=True)
    plan_path.write_text(
        "---\n"
        "title: Demo\nstatus: planning\npriority: medium\nsteps:\n"
        "  - id: 1\n    title: Present\n    detail: details/01-present.md\n"
        "  - id: 2\n    title: Unreadable\n    detail: details/02-unreadable.md\n"
        "  - id: 3\n    title: Missing\n    detail: details/03-missing.md\n"
        "---\n\n# Plan\n",
        encoding="utf-8",
    )
    present = tmp_path / "details" / "01-present.md"
    unreadable = tmp_path / "details" / "02-unreadable.md"
    present.parent.mkdir()
    present.write_text("# present\n", encoding="utf-8")
    unreadable.write_text("# unreadable\n", encoding="utf-8")
    real_read_bytes = Path.read_bytes

    def read_bytes(path: Path) -> bytes:
        if path == unreadable:
            raise OSError("permission denied")
        return real_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    snapshot = AuditInputSnapshot.capture(plan_path, tmp_path)

    assert [detail.state for detail in snapshot.details] == [
        "present", "unreadable", "missing"
    ]
    assert [detail["state"] for detail in snapshot.revision["details"]] == [
        "present", "unreadable", "missing"
    ]


def test_audit_snapshot_rejects_unmatched_archived_source_seed(tmp_path: Path) -> None:
    from plan_tool.review_persistence import AuditInputError, AuditInputSnapshot

    plan_path = tmp_path / "plans" / "1-demo.md"
    plan_path.parent.mkdir(parents=True)
    plan_path.write_text(
        "---\ntitle: Demo\nsource_seed: seeds/demo.md\nstatus: planning\n"
        "priority: medium\nsteps:\n  - id: 1\n    title: First\n---\n",
        encoding="utf-8",
    )
    archived_seed = tmp_path / "seeds" / "archive" / "demo.replaced.md"
    archived_seed.parent.mkdir(parents=True)
    archived_seed.write_text("## Source\n\n```\n", encoding="utf-8")

    with pytest.raises(AuditInputError, match="unmatched opening code fence"):
        AuditInputSnapshot.capture(plan_path, tmp_path)


def test_completeness_sidecar_round_trips_audit_stage(tmp_path: Path) -> None:
    path = save_review(
        plan_slug="x", plan_path=_PLAN_REL, repo_root=tmp_path,
        report_md="report", recommendations=_SAMPLE_RECS,
        kind="completeness", audit_stage="bare",
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["audit_stage"] == "bare"
    assert load_review(path).audit_stage == "bare"


def test_audit_stage_invalid_on_load_becomes_none(tmp_path: Path) -> None:
    path = save_review(
        plan_slug="x", plan_path=_PLAN_REL, repo_root=tmp_path,
        report_md="report", recommendations=_SAMPLE_RECS,
        kind="completeness", audit_stage="bare",
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["audit_stage"] = "bogus"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert load_review(path).audit_stage is None


def test_non_completeness_kind_omits_audit_stage(tmp_path: Path) -> None:
    path = save_review(
        plan_slug="x", plan_path=_PLAN_REL, repo_root=tmp_path,
        report_md="report", recommendations=_SAMPLE_RECS,
        kind="review", audit_stage="detail",
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert "audit_stage" not in payload
    assert load_review(path).audit_stage is None


def test_save_review_rejects_invalid_stage_for_completeness(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="audit_stage"):
        save_review(
            plan_slug="x", plan_path=_PLAN_REL, repo_root=tmp_path,
            report_md="report", recommendations=_SAMPLE_RECS,
            kind="completeness", audit_stage="bogus",
        )


@pytest.mark.parametrize("damage", ["jira", "malformed", "boolean-version", "jira-resolution"])
def test_rejected_revision_cannot_fall_back_to_legacy_provenance(tmp_path, damage):
    from plan_tool.review_persistence import AuditInputSnapshot

    plan_path = tmp_path / "demo.md"
    plan_path.write_text("---\ntitle: Demo\nstatus: planning\npriority: medium\nsteps:\n  - id: 1\n    title: First\n---\n# Demo\n")
    revision = AuditInputSnapshot.capture(plan_path, tmp_path).revision
    path = rp.save_review(
        plan_slug="demo", plan_path="demo.md", repo_root=tmp_path,
        report_md="report", recommendations=[], kind="completeness",
        qualified_result={"headline": "clean", "stage": "bare", "coverage": "confirmed",
                          "revision_status": "current", "audit_revision": revision},
    )
    payload = json.loads(path.read_text())
    bad = dict(revision)
    if damage == "jira":
        bad["detail_grade"] = "jira"
    elif damage == "malformed":
        bad.pop("plan_digest")
    elif damage == "boolean-version":
        bad["version"] = True
    else:
        bad["details"] = [dict(revision["details"][0], resolution="jira")]
    payload["qualified_result"]["audit_revision"] = bad
    payload["audit_revision"] = revision
    path.write_text(json.dumps(payload))
    archived_bytes = path.read_bytes()
    saved = rp.load_review(path)
    assert saved.report_md == "report"
    assert saved.audit_revision is None
    assert rp.project_saved_completeness_result(saved, plan_path, tmp_path).view_revision_status == "unavailable"
    assert path.read_bytes() == archived_bytes
    assert rp.normalize_audit_revision(bad) is None


@pytest.mark.parametrize("grade", ["run", "jira", "malformed", "null"])
def test_sampler_checkpoint_rejects_explicit_invalid_revision_before_resume(tmp_path, grade):
    from plan_tool.review_persistence import AuditInputSnapshot

    plan_path = _plan_abs(tmp_path)
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text("---\ntitle: Demo\nstatus: planning\npriority: medium\nsteps:\n  - id: 1\n    title: First\n---\n")
    revision = AuditInputSnapshot.capture(plan_path, tmp_path).revision
    path = save_sampler_checkpoint(
        plan_slug="x", plan_path=_PLAN_REL, repo_root=tmp_path,
        report_md="checkpoint", recommendations=[],
        sampler_state={"lifecycle": "in-progress"}, checkpoint_audit_revision=revision,
    )
    payload = json.loads(path.read_text())
    if grade == "jira":
        payload["checkpoint_audit_revision"]["detail_grade"] = "jira"
    elif grade == "malformed":
        payload["checkpoint_audit_revision"].pop("plan_digest")
    elif grade == "null":
        payload["checkpoint_audit_revision"] = None
    path.write_text(json.dumps(payload))
    archived_bytes = path.read_bytes()
    assert load_sampler_checkpoint(plan_path).status == ("valid" if grade == "run" else "not-sampler")
    assert load_review(path).is_in_progress_sampler_checkpoint is (grade == "run")
    assert path.read_bytes() == archived_bytes


@pytest.mark.parametrize("grade", ["run", "jira"])
@pytest.mark.parametrize("helper", ["capture", "freshness"])
def test_audit_helpers_reject_removed_grade_keyword(tmp_path, grade, helper):
    from plan_tool.review_persistence import (
        AuditInputSnapshot,
        audit_input_fingerprint_matches_disk,
    )

    with pytest.raises(TypeError, match="detail_grade"):
        if helper == "capture":
            AuditInputSnapshot.capture(tmp_path / "plan.md", tmp_path, detail_grade=grade)
        else:
            audit_input_fingerprint_matches_disk(
                tmp_path / "plan.md", tmp_path, "digest", detail_grade=grade
            )
