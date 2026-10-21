"""Read-only gate verdicts from immutable final completeness results."""

from pathlib import Path

from plan_tool.completeness_report import is_reusable_audit_sidecar
from plan_tool.locator import slug_from_filename
from plan_tool.review_persistence import (
    ReviewLoadError,
    list_saved_reviews,
    load_review,
    project_saved_completeness_result,
)


def build_gate_status(
    plan_path: Path,
    repo_root: Path,
    *,
    detail_grade: str,
    current_stage: str | None,
) -> dict[str, object]:
    """Select the newest final result per stage within the requested grade."""
    slug = slug_from_filename(plan_path)
    stages: dict[str, object] = {"bare": None, "detail": None}
    for path in list_saved_reviews(slug, repo_root, plan_path=plan_path):
        try:
            saved = load_review(path)
        except ReviewLoadError:
            continue
        if not is_reusable_audit_sidecar(saved):
            continue
        result = saved.qualified_result
        if result is None or result["stage"] not in stages:
            continue
        revision = result["audit_revision"]
        if revision is None or revision["detail_grade"] != detail_grade:
            continue
        stage = result["stage"]
        if stages[stage] is not None:
            continue
        view = project_saved_completeness_result(saved, plan_path, repo_root)
        stages[stage] = {
            "report": path.stem,
            "created_at": saved.created_at,
            "headline": result["headline"],
            "coverage": result["coverage"],
            "revision_status": result["revision_status"],
            "view_revision_status": view.view_revision_status,
            "confirmation_kind": (saved.audit_coverage or {}).get("confirmation_kind"),
            "plan_digest": revision["plan_digest"],
            "detail_bundle_digest": revision["detail_bundle_digest"],
            "converged": view.is_current_final_qualified
            and result["headline"] in {"clean", "advisory-only"},
        }
    try:
        display_path = plan_path.relative_to(repo_root).as_posix()
    except ValueError:
        display_path = str(plan_path)
    return {
        "version": 1,
        "plan": slug,
        "plan_path": display_path,
        "detail_grade": detail_grade,
        "current_stage": current_stage,
        "stages": stages,
    }
