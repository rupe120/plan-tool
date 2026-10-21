from __future__ import annotations

from pathlib import Path

from plan_tool.schema import Plan, Step
from plan_tool.scope_guard import (
    compute_in_scope_paths,
    compute_plan_tool_artifact_paths,
    compute_snapshot_dirs,
    evaluate_apply_scope,
)


def _plan() -> Plan:
    return Plan(
        title="Demo",
        status="planning",
        priority="medium",
        steps=[
            Step(
                id=1,
                title="Build",
                files=["src/foo.py"],
                detail="docs/implementation-plans/plan-details/demo/01-build.md",
            )
        ],
    )


def test_plan_tool_owned_paths_are_ignored_without_expanding_snapshot(
    tmp_path: Path,
) -> None:
    plan_path = tmp_path / "docs" / "implementation-plans" / "2-demo.md"
    in_scope = compute_in_scope_paths(_plan(), plan_path, tmp_path)
    ignored = compute_plan_tool_artifact_paths(plan_path, tmp_path)

    assert (tmp_path / ".plan-tool").resolve() not in in_scope
    assert (tmp_path / ".plan-tool").resolve() in ignored
    assert not any(
        p == tmp_path / ".plan-tool" for p in compute_snapshot_dirs(in_scope, tmp_path)
    )

    report = (
        tmp_path
        / "docs"
        / "implementation-plans"
        / "plan-details"
        / "demo"
        / "reports"
        / "run.json"
    )
    state = tmp_path / ".plan-tool" / "telemetry" / "decisions.jsonl"
    other = tmp_path / "docs" / "implementation-plans" / "other.md"
    pre = {report: None, state: None, other: None}
    post = {report: "{}", state: "{}", other: "x"}

    records = evaluate_apply_scope(
        finding_id="f1",
        finding_body="body",
        step_id=1,
        pre_snapshot=pre,
        post_snapshot=post,
        in_scope_paths=in_scope,
        repo_root=tmp_path,
        ignored_artifact_paths=ignored,
    )

    assert len(records) == 1
    assert records[0].impact_status == "kept-documentation"
    assert records[0].out_of_scope_files == [other]
