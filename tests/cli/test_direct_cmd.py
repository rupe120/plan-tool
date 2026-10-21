"""Unit tests for the direct-pipeline size gate
(``plan_tool/cli/direct_cmd.py:gate_create_result_size``).

The gate is deterministic and Claude-free: it re-parses a finished plan from
disk and compares ``len(plan.steps)`` against ``MAX_CHAINABLE_STEPS``. These
tests build the fixture plan on disk with the real parser round-trip (via
``write_plan``) and point a ``CreateResult`` at it, mirroring the on-disk
fixture style in ``tests/cli/test_scope_out_cmd.py``. Steps 4–6 extend this
file with verb and flag-propagation tests.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from plan_tool.cli import direct_cmd
from plan_tool.cli.direct_cmd import (
    MAX_CHAINABLE_STEPS,
    SizeGateResult,
    derive_created_repo_root,
    gate_create_result_size,
)
from plan_tool.concept_tree import concepts_path
from plan_tool.create import CreateResult, SplitProposal, SplitProposalEntry
from plan_tool.grounding import grounding_path
from plan_tool.parser import write_plan
from plan_tool.schema import ChangeType, Plan, PlanStatus, Priority, Step

# Sentinel: the stubbed ``unexpected_dirty_paths`` returns ``[]`` (relocated
# root clean) unless a test overrides it. Distinct from ``None`` (a real return
# value meaning "git status unreadable → abort").
_CLEAN_RELOC = object()


def _plan_with_steps(n: int) -> Plan:
    return Plan(
        title="Direct Chain Plan",
        status=PlanStatus.PLANNING,
        priority=Priority.MEDIUM,
        steps=[Step(id=i, title=f"Step {i}") for i in range(1, n + 1)],
    )


def _mark_project_root(root: Path) -> None:
    """Lay down a ``.plan-tool/plans.json`` marker so ``find_repo_root_from_cwd``
    resolves ``root`` as a project root (mirrors ``is_project_root``)."""
    (root / ".plan-tool").mkdir(parents=True, exist_ok=True)
    (root / ".plan-tool" / "plans.json").write_text(
        '{"plans": []}', encoding="utf-8"
    )


def _create_result(tmp_path: Path, n_steps: int) -> CreateResult:
    """Write an ``n_steps``-step plan to disk and wrap it in a CreateResult."""
    plan_path = tmp_path / "plan.md"
    # write_plan updates an existing plan (it preserves the on-disk body), so
    # seed a minimal file first before writing the generated frontmatter.
    plan_path.write_text("---\n---\n\n# Direct Plan\n", encoding="utf-8")
    write_plan(plan_path, _plan_with_steps(n_steps), expect_unchanged=False)
    # Mark tmp_path a project root so the direct verbs' root derivation
    # (find_repo_root_from_cwd, walked from plan_path.parent) resolves it —
    # matching the no-relocation case where create wrote to the same root.
    _mark_project_root(tmp_path)
    return CreateResult(
        plan_path=plan_path,
        manifest_path=tmp_path / ".plan-tool" / "plans.json",
        manifest_updated=True,
    )


def test_over_large_plan_returns_stop(tmp_path: Path) -> None:
    result = _create_result(tmp_path, MAX_CHAINABLE_STEPS + 1)
    verdict = gate_create_result_size(result)
    assert not verdict.may_proceed
    assert not verdict.split_short_circuit


def test_plan_at_threshold_passes(tmp_path: Path) -> None:
    result = _create_result(tmp_path, MAX_CHAINABLE_STEPS)
    verdict = gate_create_result_size(result)
    assert verdict.may_proceed
    assert verdict.step_count == MAX_CHAINABLE_STEPS


def test_plan_below_threshold_passes(tmp_path: Path) -> None:
    result = _create_result(tmp_path, 2)
    verdict = gate_create_result_size(result)
    assert verdict.may_proceed
    assert verdict.step_count == 2


def test_split_proposal_result_stops_without_parsing(tmp_path: Path) -> None:
    # plan_path is None on the multi-plan split short-circuit: the gate must
    # branch before parsing and must not crash.
    result = CreateResult(
        plan_path=None,
        manifest_path=tmp_path / ".plan-tool" / "plans.json",
        manifest_updated=False,
        split_proposal=SplitProposal(
            entries=[
                SplitProposalEntry(title="A", suggested_slug="a", rationale="x"),
                SplitProposalEntry(title="B", suggested_slug="b", rationale="y"),
            ]
        ),
    )
    verdict = gate_create_result_size(result)
    assert not verdict.may_proceed
    assert verdict.split_short_circuit


def test_verdict_carries_step_count_and_threshold(tmp_path: Path) -> None:
    result = _create_result(tmp_path, 3)
    verdict = gate_create_result_size(result)
    assert verdict.step_count == 3
    assert verdict.threshold == MAX_CHAINABLE_STEPS


def test_gate_spends_no_claude(tmp_path: Path) -> None:
    # A plain call proves it stays Claude-free: tests/conftest.py's autouse
    # gate raises if any backend binary is spawned. The helper also exposes no
    # invoker parameter.
    import inspect

    result = _create_result(tmp_path, 2)
    gate_create_result_size(result)  # would raise if it shelled out

    params = inspect.signature(gate_create_result_size).parameters
    assert "invoker" not in params
    assert "claude_invoker" not in params


# --- cmd_direct_jira -------------------------------------------------------
#
# The verb chains create → detail → completeness-apply → jira in one process.
# Steps 6 owns the real subparser, so these tests build the args namespace by
# hand and stub the module-level handlers (and the git helpers) so no stage
# runs for real and no backend spawns.


def _input_args(tmp_path: Path, **overrides: object) -> argparse.Namespace:
    """A hand-built direct-jira input namespace with the cross-cutting flags."""
    base: dict[str, object] = dict(
        repo_root=tmp_path,
        plans_dir=None,
        manifest=None,
        backend=None,
        model=None,
        on_rate_limit=None,
        fallback_backend=None,
        yes=False,
        iterate=True,
        epic=None,
        max_hours=8,
        format="markdown",
    )
    base.update(overrides)
    return argparse.Namespace(**base)


def _install_stubs(
    monkeypatch: pytest.MonkeyPatch,
    result: CreateResult,
    *,
    create_rc: int = 0,
    detail_rc: int = 0,
    apply_rc: int = 0,
    jira_rc: int = 0,
    start_dirty: bool = False,
    dirty_after: bool = False,
    dirty_sequence: list[bool] | None = None,
    deposit: bool = True,
    dirty_roots: list[Path] | None = None,
    commit_roots: list[tuple[Path, str]] | None = None,
    reloc_dirt: object = _CLEAN_RELOC,
    reloc_expected_sink: list[Path] | None = None,
) -> tuple[list[str], dict[str, argparse.Namespace]]:
    """Stub the four stage handlers plus the three git helpers.

    ``reloc_dirt`` is what the stubbed ``unexpected_dirty_paths`` (the relocated-
    root safety check) returns — ``[]`` (clean) by default, a list of offending
    paths to force an abort, or ``None`` for the unreadable-git case. Only ever
    called on a disjoint relocation. ``reloc_expected_sink`` captures the
    expected-path set the guard built, so a test can assert what it allowlisted.

    ``working_tree_dirty`` is stateful: by default the first call (the
    chain-start precondition) returns ``start_dirty``, every later call returns
    ``dirty_after`` — so a test can keep a clean start while making the tree
    dirty after authoring. Pass ``dirty_sequence`` for per-call control (call N
    returns ``dirty_sequence[N-1]``), needed by the relocation tests where the
    original-root sweep check and the later authoring checks must differ.

    Pass ``dirty_roots`` / ``commit_roots`` to also record the ``root`` argument
    each ``working_tree_dirty`` / ``commit_all`` call received (the latter as a
    ``(root, subject)`` pair) — the relocation tests assert which root each git
    op targeted.

    Returns ``(calls, captured)`` — the ordered stage names and the namespace
    each stage was handed — for assertions.
    """
    calls: list[str] = []
    captured: dict[str, argparse.Namespace] = {}
    dirty_calls = {"n": 0}

    def fake_create(a: argparse.Namespace) -> int:
        calls.append("create")
        captured["create"] = a
        if deposit:
            a._create_result_sink.append(result)
        return create_rc

    def fake_detail(a: argparse.Namespace) -> int:
        calls.append("detail")
        captured["detail"] = a
        return detail_rc

    def fake_apply(a: argparse.Namespace) -> int:
        calls.append("apply")
        captured["apply"] = a
        return apply_rc

    def fake_jira(a: argparse.Namespace) -> int:
        calls.append("jira")
        captured["jira"] = a
        return jira_rc

    def fake_commit(root: Path, subject: str) -> tuple[int, str]:
        calls.append("commit")
        if commit_roots is not None:
            commit_roots.append((root, subject))
        return 0, ""

    def fake_dirty(root: Path) -> bool:
        dirty_calls["n"] += 1
        if dirty_roots is not None:
            dirty_roots.append(root)
        if dirty_sequence is not None:
            idx = dirty_calls["n"] - 1
            return dirty_sequence[idx] if idx < len(dirty_sequence) else False
        return start_dirty if dirty_calls["n"] == 1 else dirty_after

    monkeypatch.setattr(direct_cmd, "cmd_create", fake_create)
    monkeypatch.setattr(direct_cmd, "cmd_detail", fake_detail)
    monkeypatch.setattr(direct_cmd, "cmd_completeness_apply", fake_apply)
    def fake_unexpected(root: Path, expected) -> "list[str] | None":
        if reloc_expected_sink is not None:
            reloc_expected_sink.extend(expected)
        return [] if reloc_dirt is _CLEAN_RELOC else reloc_dirt

    monkeypatch.setattr(direct_cmd, "cmd_jira", fake_jira)
    monkeypatch.setattr(direct_cmd, "commit_all", fake_commit)
    monkeypatch.setattr(direct_cmd, "working_tree_dirty", fake_dirty)
    monkeypatch.setattr(direct_cmd, "unexpected_dirty_paths", fake_unexpected)
    return calls, captured


def test_direct_jira_chains_all_stages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _create_result(tmp_path, 2)
    calls, _ = _install_stubs(monkeypatch, result)
    rc = direct_cmd.cmd_direct_jira(_input_args(tmp_path))
    assert rc == 0
    assert [c for c in calls if c != "commit"] == [
        "create",
        "detail",
        "apply",
        "jira",
    ]


def test_direct_jira_jira_stage_namespace_has_jira_tag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The jira-stage namespace must carry a ``jira_tag`` attribute even
    though direct-jira's own subparser doesn't define ``--jira-tag`` —
    ``cmd_jira`` reads ``args.jira_tag`` directly (not via getattr), so a
    missing attribute would raise ``AttributeError`` mid-chain. Mirrors
    the ``epic=getattr(args, "epic", None)`` default already in place."""
    result = _create_result(tmp_path, 2)
    _, captured = _install_stubs(monkeypatch, result)
    direct_cmd.cmd_direct_jira(_input_args(tmp_path))
    assert captured["jira"].jira_tag is None


def test_direct_jira_jira_tag_override_propagates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _create_result(tmp_path, 2)
    _, captured = _install_stubs(monkeypatch, result)
    direct_cmd.cmd_direct_jira(_input_args(tmp_path, jira_tag="custom-tag"))
    assert captured["jira"].jira_tag == "custom-tag"


def test_direct_jira_exposes_no_legacy_handoff_or_adoption_surface(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """direct-jira inherits paired export without exposing migration authority."""
    result = _create_result(tmp_path, 2)
    _, captured = _install_stubs(monkeypatch, result)
    direct_cmd.cmd_direct_jira(_input_args(tmp_path))
    ns = captured["jira"]
    assert not hasattr(ns, "developer_handoff")
    assert not hasattr(ns, "handoff_output")
    assert not hasattr(ns, "adopt_existing")


def test_direct_jira_rejects_dirty_tree_at_start(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = _create_result(tmp_path, 2)
    calls, _ = _install_stubs(monkeypatch, result, start_dirty=True)
    rc = direct_cmd.cmd_direct_jira(_input_args(tmp_path))
    assert rc == 2
    assert "create" not in calls  # stopped before cmd_create
    err = capsys.readouterr().err
    assert "direct-jira" in err
    assert "--commit" not in err


def test_direct_jira_completeness_apply_uses_jobs_gt_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _create_result(tmp_path, 2)
    _, captured = _install_stubs(monkeypatch, result)
    direct_cmd.cmd_direct_jira(_input_args(tmp_path))
    assert captured["apply"].jobs > 1
    assert captured["apply"].yes is True


def test_direct_jira_commits_before_completeness_apply(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _create_result(tmp_path, 2)
    # Dirty after authoring so the (now dirty-gated) commit fires before apply.
    calls, _ = _install_stubs(monkeypatch, result, dirty_after=True)
    direct_cmd.cmd_direct_jira(_input_args(tmp_path))
    assert calls.index("commit") > calls.index("detail")
    assert calls.index("commit") < calls.index("apply")

    # Clean after authoring (idempotent re-run): nothing staged, so the guarded
    # commit is skipped rather than failing on an empty commit and halting.
    result2 = _create_result(tmp_path, 2)
    calls2, _ = _install_stubs(monkeypatch, result2, dirty_after=False)
    assert direct_cmd.cmd_direct_jira(_input_args(tmp_path)) == 0
    assert "commit" not in calls2


def test_direct_jira_reads_create_result_from_sink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _create_result(tmp_path, 2)
    _, captured = _install_stubs(monkeypatch, result)
    direct_cmd.cmd_direct_jira(_input_args(tmp_path))
    expected = result.plan_path.stem
    assert captured["detail"].name == expected
    assert captured["jira"].name == expected


def test_direct_jira_threads_cross_cutting_flags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _create_result(tmp_path, 2)
    _, captured = _install_stubs(monkeypatch, result)
    args = _input_args(
        tmp_path,
        backend="codex",
        model="opus",
        on_rate_limit="switch",
        fallback_backend="claude",
    )
    direct_cmd.cmd_direct_jira(args)
    for stage in ("detail", "jira"):
        ns = captured[stage]
        assert ns.backend == "codex"
        assert ns.model == "opus"
        assert ns.on_rate_limit == "switch"
        assert ns.fallback_backend == "claude"


def test_direct_jira_stops_on_create_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _create_result(tmp_path, 2)
    calls, _ = _install_stubs(
        monkeypatch, result, create_rc=3, deposit=False
    )
    rc = direct_cmd.cmd_direct_jira(_input_args(tmp_path))
    assert rc == 3
    assert "detail" not in calls
    assert "jira" not in calls


def test_direct_jira_stops_on_detail_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _create_result(tmp_path, 2)
    calls, _ = _install_stubs(monkeypatch, result, detail_rc=5)
    rc = direct_cmd.cmd_direct_jira(_input_args(tmp_path))
    assert rc == 5
    assert "jira" not in calls
    assert "apply" not in calls


def test_direct_jira_stops_on_split_proposal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    split_result = CreateResult(
        plan_path=None,
        manifest_path=tmp_path / ".plan-tool" / "plans.json",
        manifest_updated=False,
        split_proposal=SplitProposal(
            entries=[
                SplitProposalEntry(title="A", suggested_slug="a", rationale="x"),
                SplitProposalEntry(title="B", suggested_slug="b", rationale="y"),
            ]
        ),
    )
    calls, _ = _install_stubs(monkeypatch, split_result)
    rc = direct_cmd.cmd_direct_jira(_input_args(tmp_path))
    assert rc == 0  # deliberate, non-hard-failure halt
    assert "detail" not in calls
    assert "jira" not in calls


def test_direct_jira_stops_on_oversize_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = _create_result(tmp_path, MAX_CHAINABLE_STEPS + 1)
    calls, _ = _install_stubs(monkeypatch, result)
    rc = direct_cmd.cmd_direct_jira(_input_args(tmp_path))
    assert rc == 0
    assert "detail" not in calls
    out = capsys.readouterr().out
    assert "steps" in out  # the gate's human reason was printed


def test_direct_jira_stops_on_iteration_incomplete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _create_result(tmp_path, 2)
    result.iteration_stage_failure = "step re-proposal produced invalid graph"
    calls, _ = _install_stubs(monkeypatch, result)
    rc = direct_cmd.cmd_direct_jira(_input_args(tmp_path))
    assert rc != 0  # rc-0 from create is not treated as convergence
    assert "detail" not in calls
    assert "jira" not in calls


def test_direct_jira_builds_detail_namespace_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _create_result(tmp_path, 2)
    _, captured = _install_stubs(monkeypatch, result)
    direct_cmd.cmd_direct_jira(_input_args(tmp_path))
    ns = captured["detail"]
    for field_name in ("name", "step", "force", "dry_run"):
        assert hasattr(ns, field_name)


def test_direct_jira_builds_jira_namespace_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _create_result(tmp_path, 2)
    _, captured = _install_stubs(monkeypatch, result)
    direct_cmd.cmd_direct_jira(_input_args(tmp_path))
    ns = captured["jira"]
    for field_name in (
        "name",
        "lint",
        "output",
        "epic",
        "max_hours",
        "format",
        "no_write",
        "stdout",
        "jira_tag",
    ):
        assert hasattr(ns, field_name)


def test_direct_jira_sets_detail_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _create_result(tmp_path, 2)
    _, captured = _install_stubs(monkeypatch, result)
    # detail_only must be pinned True regardless of the input's --iterate.
    direct_cmd.cmd_direct_jira(_input_args(tmp_path, iterate=False))
    assert captured["detail"].detail_only is True


# --- cmd_direct_run --------------------------------------------------------
#
# The verb chains create → detail → completeness-apply → run --all --commit →
# reconcile-code (once per code step) in one process. Same hand-built-namespace
# / stubbed-handler style as the direct-jira tests above, plus the run and
# reconcile-code handlers.


def _create_result_typed(
    tmp_path: Path, change_types: list[ChangeType | None]
) -> CreateResult:
    """Write a plan whose steps carry the given ``change_type``s and wrap it."""
    plan_path = tmp_path / "plan.md"
    # write_plan updates an existing plan (it preserves the on-disk body), so
    # seed a minimal file first before writing the typed frontmatter.
    plan_path.write_text("---\n---\n\n# Direct Run Plan\n", encoding="utf-8")
    plan = Plan(
        title="Direct Run Plan",
        status=PlanStatus.PLANNING,
        priority=Priority.MEDIUM,
        steps=[
            Step(id=i, title=f"Step {i}", change_type=ct)
            for i, ct in enumerate(change_types, start=1)
        ],
    )
    write_plan(plan_path, plan, expect_unchanged=False)
    _mark_project_root(tmp_path)
    return CreateResult(
        plan_path=plan_path,
        manifest_path=tmp_path / ".plan-tool" / "plans.json",
        manifest_updated=True,
    )


def _install_run_stubs(
    monkeypatch: pytest.MonkeyPatch,
    result: CreateResult,
    *,
    create_rc: int = 0,
    detail_rc: int = 0,
    apply_rc: int = 0,
    run_rc: int = 0,
    reconcile_fail_step: int | None = None,
    reconcile_fail_rc: int = 7,
    start_dirty: bool = False,
    dirty_after: bool = False,
    dirty_sequence: list[bool] | None = None,
    deposit: bool = True,
    dirty_roots: list[Path] | None = None,
    commit_roots: list[tuple[Path, str]] | None = None,
    reloc_dirt: object = _CLEAN_RELOC,
    reloc_expected_sink: list[Path] | None = None,
) -> tuple[list[str], dict[str, argparse.Namespace], list[argparse.Namespace]]:
    """Stub the five stage handlers plus the three git helpers for ``direct-run``.

    ``reloc_dirt`` / ``reloc_expected_sink`` behave as in ``_install_stubs``:
    the stubbed relocated-root safety check returns ``[]`` (clean) by default,
    and captures the expected-path set when a sink is passed.

    ``working_tree_dirty`` is stateful: by default the first call (the
    chain-start precondition) returns ``start_dirty``, every later call returns
    ``dirty_after`` — so a test can keep a clean start while making the tree
    dirty after authoring/apply. Pass ``dirty_sequence`` for per-call control
    (call N returns ``dirty_sequence[N-1]``), needed by the relocation tests.

    Pass ``dirty_roots`` / ``commit_roots`` to also record the ``root`` argument
    each ``working_tree_dirty`` / ``commit_all`` call received (the latter as a
    ``(root, subject)`` pair).

    Returns ``(calls, captured, reconcile_calls)`` — the ordered stage names,
    the single namespace each non-reconcile stage got, and the per-step
    reconcile namespaces in call order.
    """
    calls: list[str] = []
    captured: dict[str, argparse.Namespace] = {}
    reconcile_calls: list[argparse.Namespace] = []
    dirty_calls = {"n": 0}

    def fake_create(a: argparse.Namespace) -> int:
        calls.append("create")
        captured["create"] = a
        if deposit:
            a._create_result_sink.append(result)
        return create_rc

    def fake_detail(a: argparse.Namespace) -> int:
        calls.append("detail")
        captured["detail"] = a
        return detail_rc

    def fake_apply(a: argparse.Namespace) -> int:
        calls.append("apply")
        captured["apply"] = a
        return apply_rc

    def fake_run(a: argparse.Namespace) -> int:
        calls.append("run")
        captured["run"] = a
        return run_rc

    def fake_reconcile(a: argparse.Namespace) -> int:
        calls.append("reconcile")
        reconcile_calls.append(a)
        if reconcile_fail_step is not None and a.step == reconcile_fail_step:
            return reconcile_fail_rc
        return 0

    def fake_commit(root: Path, subject: str) -> tuple[int, str]:
        calls.append("commit")
        if commit_roots is not None:
            commit_roots.append((root, subject))
        return 0, ""

    def fake_dirty(root: Path) -> bool:
        dirty_calls["n"] += 1
        if dirty_roots is not None:
            dirty_roots.append(root)
        if dirty_sequence is not None:
            idx = dirty_calls["n"] - 1
            return dirty_sequence[idx] if idx < len(dirty_sequence) else False
        return start_dirty if dirty_calls["n"] == 1 else dirty_after

    monkeypatch.setattr(direct_cmd, "cmd_create", fake_create)
    monkeypatch.setattr(direct_cmd, "cmd_detail", fake_detail)
    monkeypatch.setattr(direct_cmd, "cmd_completeness_apply", fake_apply)
    monkeypatch.setattr(direct_cmd, "cmd_run", fake_run)
    def fake_unexpected(root: Path, expected) -> "list[str] | None":
        if reloc_expected_sink is not None:
            reloc_expected_sink.extend(expected)
        return [] if reloc_dirt is _CLEAN_RELOC else reloc_dirt

    monkeypatch.setattr(direct_cmd, "cmd_reconcile_code", fake_reconcile)
    monkeypatch.setattr(direct_cmd, "commit_all", fake_commit)
    monkeypatch.setattr(direct_cmd, "working_tree_dirty", fake_dirty)
    monkeypatch.setattr(direct_cmd, "unexpected_dirty_paths", fake_unexpected)
    return calls, captured, reconcile_calls


def test_direct_run_chains_all_stages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _create_result_typed(tmp_path, [ChangeType.FEATURE])
    calls, _, _ = _install_run_stubs(monkeypatch, result, dirty_after=True)
    rc = direct_cmd.cmd_direct_run(_input_args(tmp_path))
    assert rc == 0
    assert [c for c in calls if c != "commit"] == [
        "create",
        "detail",
        "apply",
        "run",
        "reconcile",
    ]


def test_direct_run_completeness_apply_uses_jobs_gt_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _create_result_typed(tmp_path, [ChangeType.FEATURE])
    calls, captured, _ = _install_run_stubs(
        monkeypatch, result, dirty_after=True
    )
    direct_cmd.cmd_direct_run(_input_args(tmp_path))
    assert captured["apply"].jobs > 1
    assert captured["apply"].yes is True
    # commit before apply (clean HEAD for worktree isolation) and again after
    # apply but before run (clean tree for run's --commit gate).
    commit_positions = [i for i, c in enumerate(calls) if c == "commit"]
    assert any(i < calls.index("apply") for i in commit_positions)
    assert any(
        calls.index("apply") < i < calls.index("run") for i in commit_positions
    )


def test_direct_run_run_namespace_resets_iterate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _create_result_typed(tmp_path, [ChangeType.FEATURE])
    _, captured, _ = _install_run_stubs(monkeypatch, result)
    direct_cmd.cmd_direct_run(_input_args(tmp_path, iterate=True))
    assert captured["run"].iterate is False


def test_direct_run_reads_create_result_from_sink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _create_result_typed(tmp_path, [ChangeType.FEATURE])
    _, captured, reconcile_calls = _install_run_stubs(monkeypatch, result)
    direct_cmd.cmd_direct_run(_input_args(tmp_path))
    expected = result.plan_path.stem
    assert captured["detail"].name == expected
    assert captured["run"].name == expected
    assert reconcile_calls[0].name == expected


def test_direct_run_threads_cross_cutting_flags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _create_result_typed(tmp_path, [ChangeType.FEATURE])
    _, captured, reconcile_calls = _install_run_stubs(monkeypatch, result)
    args = _input_args(
        tmp_path,
        backend="codex",
        model="opus",
        on_rate_limit="switch",
        fallback_backend="claude",
    )
    direct_cmd.cmd_direct_run(args)
    for ns in (captured["detail"], captured["run"], reconcile_calls[0]):
        assert ns.backend == "codex"
        assert ns.model == "opus"
        assert ns.on_rate_limit == "switch"
        assert ns.fallback_backend == "claude"


def test_direct_run_run_stage_gets_commit_and_all(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _create_result_typed(tmp_path, [ChangeType.FEATURE])
    _, captured, _ = _install_run_stubs(monkeypatch, result)
    direct_cmd.cmd_direct_run(_input_args(tmp_path))
    assert captured["run"].mode == "run"
    assert captured["run"].all is True
    assert captured["run"].commit is True


def test_direct_run_commits_authoring_before_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Dirty after authoring: commit fires before run so the --commit gate passes.
    result = _create_result_typed(tmp_path, [ChangeType.FEATURE])
    calls, _, _ = _install_run_stubs(monkeypatch, result, dirty_after=True)
    direct_cmd.cmd_direct_run(_input_args(tmp_path))
    assert "commit" in calls
    assert calls.index("commit") < calls.index("run")

    # Clean after authoring: nothing to commit, so commit_all is never called.
    result2 = _create_result_typed(tmp_path, [ChangeType.FEATURE])
    calls2, _, _ = _install_run_stubs(monkeypatch, result2, dirty_after=False)
    direct_cmd.cmd_direct_run(_input_args(tmp_path))
    assert "commit" not in calls2


def test_direct_run_rejects_dirty_tree_at_start(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = _create_result_typed(tmp_path, [ChangeType.FEATURE])
    calls, _, _ = _install_run_stubs(monkeypatch, result, start_dirty=True)
    rc = direct_cmd.cmd_direct_run(_input_args(tmp_path))
    assert rc == 2
    assert "create" not in calls  # stopped before cmd_create
    err = capsys.readouterr().err
    assert "direct-run" in err
    assert "--commit" not in err


def test_direct_run_sets_detail_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _create_result_typed(tmp_path, [ChangeType.FEATURE])
    _, captured, _ = _install_run_stubs(monkeypatch, result)
    direct_cmd.cmd_direct_run(_input_args(tmp_path, iterate=True))
    assert captured["detail"].detail_only is True


def test_direct_run_reconciles_only_code_steps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # steps 1 (non-code) and 4 (non-code) are skipped; 2 (feature) and 3
    # (refactor) reconcile, in plan order.
    result = _create_result_typed(
        tmp_path,
        [
            ChangeType.NON_CODE,
            ChangeType.FEATURE,
            ChangeType.REFACTOR,
            ChangeType.NON_CODE,
        ],
    )
    _, _, reconcile_calls = _install_run_stubs(monkeypatch, result)
    direct_cmd.cmd_direct_run(_input_args(tmp_path))
    assert [ns.step for ns in reconcile_calls] == [2, 3]


def test_direct_run_stops_on_iteration_incomplete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _create_result_typed(tmp_path, [ChangeType.FEATURE])
    result.iteration_stage_failure = "step re-proposal produced invalid graph"
    calls, _, _ = _install_run_stubs(monkeypatch, result)
    rc = direct_cmd.cmd_direct_run(_input_args(tmp_path))
    assert rc != 0  # rc-0 from create is not treated as convergence
    assert "detail" not in calls
    assert "run" not in calls
    assert "reconcile" not in calls


def test_direct_run_reconciles_each_code_step(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _create_result_typed(
        tmp_path, [ChangeType.FEATURE, ChangeType.REFACTOR, ChangeType.FEATURE]
    )
    _, _, reconcile_calls = _install_run_stubs(monkeypatch, result)
    direct_cmd.cmd_direct_run(_input_args(tmp_path))
    assert [ns.step for ns in reconcile_calls] == [1, 2, 3]


def test_direct_run_stops_on_create_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _create_result_typed(tmp_path, [ChangeType.FEATURE])
    calls, _, _ = _install_run_stubs(
        monkeypatch, result, create_rc=3, deposit=False
    )
    rc = direct_cmd.cmd_direct_run(_input_args(tmp_path))
    assert rc == 3
    assert "detail" not in calls
    assert "run" not in calls
    assert "reconcile" not in calls


def test_direct_run_stops_on_detail_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _create_result_typed(tmp_path, [ChangeType.FEATURE])
    calls, _, _ = _install_run_stubs(monkeypatch, result, detail_rc=5)
    rc = direct_cmd.cmd_direct_run(_input_args(tmp_path))
    assert rc == 5
    assert "run" not in calls
    assert "reconcile" not in calls


def test_direct_run_stops_on_run_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _create_result_typed(tmp_path, [ChangeType.FEATURE])
    calls, _, _ = _install_run_stubs(monkeypatch, result, run_rc=4)
    rc = direct_cmd.cmd_direct_run(_input_args(tmp_path))
    assert rc == 4
    assert "reconcile" not in calls


def test_direct_run_stops_on_reconcile_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _create_result_typed(
        tmp_path, [ChangeType.FEATURE, ChangeType.REFACTOR, ChangeType.FEATURE]
    )
    _, _, reconcile_calls = _install_run_stubs(
        monkeypatch, result, reconcile_fail_step=2, reconcile_fail_rc=9
    )
    rc = direct_cmd.cmd_direct_run(_input_args(tmp_path))
    assert rc == 9
    # stopped at step 2 — step 3 never reconciled.
    assert [ns.step for ns in reconcile_calls] == [1, 2]


def test_direct_run_stops_on_split_proposal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    split_result = CreateResult(
        plan_path=None,
        manifest_path=tmp_path / ".plan-tool" / "plans.json",
        manifest_updated=False,
        split_proposal=SplitProposal(
            entries=[
                SplitProposalEntry(title="A", suggested_slug="a", rationale="x"),
                SplitProposalEntry(title="B", suggested_slug="b", rationale="y"),
            ]
        ),
    )
    calls, _, _ = _install_run_stubs(monkeypatch, split_result)
    rc = direct_cmd.cmd_direct_run(_input_args(tmp_path))
    assert rc == 0  # deliberate, non-hard-failure halt
    assert "detail" not in calls
    assert "run" not in calls
    assert "reconcile" not in calls


def test_direct_run_stops_on_oversize_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = _create_result_typed(
        tmp_path, [ChangeType.FEATURE] * (MAX_CHAINABLE_STEPS + 1)
    )
    calls, _, _ = _install_run_stubs(monkeypatch, result)
    rc = direct_cmd.cmd_direct_run(_input_args(tmp_path))
    assert rc == 0
    assert "detail" not in calls
    out = capsys.readouterr().out
    assert "steps" in out  # the gate's human reason was printed


def test_direct_run_builds_run_namespace_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _create_result_typed(tmp_path, [ChangeType.FEATURE])
    _, captured, _ = _install_run_stubs(monkeypatch, result)
    direct_cmd.cmd_direct_run(_input_args(tmp_path))
    ns = captured["run"]
    for field_name in (
        "name",
        "mode",
        "step",
        "dry_run",
        "yes",
        "allow_missing_parent",
        "no_walk",
        "no_save",
        "max_steps",
    ):
        assert hasattr(ns, field_name)


def test_direct_run_builds_reconcile_namespace_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _create_result_typed(tmp_path, [ChangeType.FEATURE])
    _, _, reconcile_calls = _install_run_stubs(monkeypatch, result)
    direct_cmd.cmd_direct_run(_input_args(tmp_path))
    ns = reconcile_calls[0]
    for field_name in (
        "name",
        "step",
        "dry_run",
        "yes",
        "allow_missing_parent",
    ):
        assert hasattr(ns, field_name)


# --- step 6: registration, dispatch, and namespace field-completeness ------
#
# These drive the REAL parser (via plan_tool.cli.build_parser / assemble) so
# they pin that the two verbs are registered, dispatch to their handlers, and
# yield a namespace complete against the create-side fields the verbs read.


def _real_parser_and_dispatch():
    """The assembled parser + dispatch map from the live command registry."""
    import plan_tool.cli as cli
    from plan_tool.cli.app import COMMAND_MODULES
    from plan_tool.cli.parser import assemble

    return assemble(cli.__doc__, COMMAND_MODULES)


# The create-side fields the verbs read off their own namespace before
# threading it into each stage, plus the global flags make_base_parser
# supplies. A missing one raises AttributeError mid-chain.
_CREATE_SIDE_FIELDS = (
    "from_description",
    "from_existing",
    "slug",
    "output_dir",
    "yes",
    "iterate",
)
_GLOBAL_FIELDS = ("backend", "model", "on_rate_limit", "fallback_backend")


def test_direct_jira_registered_and_dispatches() -> None:
    parser, dispatch = _real_parser_and_dispatch()
    ns = parser.parse_args(["direct-jira", "myslug", "--from", "do a thing"])
    assert ns.command == "direct-jira"
    assert dispatch["direct-jira"] is direct_cmd.cmd_direct_jira


def test_direct_run_registered_and_dispatches() -> None:
    parser, dispatch = _real_parser_and_dispatch()
    ns = parser.parse_args(["direct-run", "myslug", "--from-existing", "seed.md"])
    assert ns.command == "direct-run"
    assert dispatch["direct-run"] is direct_cmd.cmd_direct_run


def test_direct_jira_namespace_is_field_complete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parser, _ = _real_parser_and_dispatch()
    args = parser.parse_args(["direct-jira", "myslug", "--from", "do a thing"])
    for field_name in _CREATE_SIDE_FIELDS + _GLOBAL_FIELDS:
        assert hasattr(args, field_name), f"missing {field_name}"

    # With every stage stubbed, the whole chain runs off the real namespace
    # without an AttributeError from a field the parser forgot to supply.
    result = _create_result(tmp_path, 2)
    _install_stubs(monkeypatch, result)
    assert direct_cmd.cmd_direct_jira(args) == 0


def test_direct_run_namespace_is_field_complete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parser, _ = _real_parser_and_dispatch()
    args = parser.parse_args(["direct-run", "myslug", "--from", "do a thing"])
    for field_name in _CREATE_SIDE_FIELDS + _GLOBAL_FIELDS:
        assert hasattr(args, field_name), f"missing {field_name}"

    # Run + reconcile-code stages stubbed too: the chain drives the parent
    # namespace through every stage without an AttributeError.
    result = _create_result_typed(tmp_path, [ChangeType.FEATURE])
    _install_run_stubs(monkeypatch, result)
    assert direct_cmd.cmd_direct_run(args) == 0


def test_direct_verbs_in_locked_mutating_commands() -> None:
    from plan_tool.cli import app

    assert "direct-jira" in app._LOCKED_MUTATING_COMMANDS
    assert "direct-run" in app._LOCKED_MUTATING_COMMANDS


def test_direct_verbs_in_canonical_order() -> None:
    from plan_tool.cli.parser import CANONICAL_COMMAND_ORDER

    assert "direct-jira" in CANONICAL_COMMAND_ORDER
    assert "direct-run" in CANONICAL_COMMAND_ORDER


@pytest.mark.integration
def test_direct_verbs_help_exits_zero() -> None:
    from plan_tool.cli.app import main

    for verb in ("direct-jira", "direct-run"):
        with pytest.raises(SystemExit) as exc:
            main([verb, "--help"])
        assert exc.value.code == 0


# --- step 2: repo-root derivation, relocation refuse, and threading --------
#
# ``create`` can relocate its working root (a --from-existing seed resolving
# under a different .git ancestor). These tests cover the helper that derives
# the root create actually used, the guard that refuses a nested/ancestor
# relocation, the original-root seed-dirt sweep, and threading the resolved
# root into every downstream stage namespace and git-op.


def _write_plan_at(
    plan_dir: Path,
    *,
    n_steps: int = 2,
    change_types: list[ChangeType | None] | None = None,
) -> Path:
    """Write a plan file under ``plan_dir`` and return its path."""
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_path = plan_dir / "plan.md"
    plan_path.write_text("---\n---\n\n# Relocated Plan\n", encoding="utf-8")
    if change_types is not None:
        plan = Plan(
            title="Relocated Plan",
            status=PlanStatus.PLANNING,
            priority=Priority.MEDIUM,
            steps=[
                Step(id=i, title=f"Step {i}", change_type=ct)
                for i, ct in enumerate(change_types, start=1)
            ],
        )
    else:
        plan = _plan_with_steps(n_steps)
    write_plan(plan_path, plan, expect_unchanged=False)
    return plan_path


def _relocated_result(
    tmp_path: Path,
    *,
    kind: str,
    n_steps: int = 2,
    change_types: list[ChangeType | None] | None = None,
) -> tuple[CreateResult, Path, Path]:
    """Build a CreateResult whose plan lives under a marked root distinct from
    the original repo_root. Returns ``(result, original_root, created_root)``,
    both roots resolved.

    ``kind``: ``"disjoint"`` (sibling roots), ``"nested"`` (created inside
    original), ``"ancestor"`` (created a strict ancestor of original).
    """
    if kind == "disjoint":
        original = tmp_path / "orig"
        created = tmp_path / "reloc"
        _mark_project_root(original)
        _mark_project_root(created)
        plan_dir = created
    elif kind == "nested":
        original = tmp_path / "outer"
        created = tmp_path / "outer" / "inner"
        _mark_project_root(created)  # creates outer too
        plan_dir = created
    elif kind == "ancestor":
        original = tmp_path / "outer" / "inner"
        created = tmp_path / "outer"
        _mark_project_root(created)
        original.mkdir(parents=True, exist_ok=True)
        plan_dir = created
    else:  # pragma: no cover - test misconfiguration
        raise ValueError(kind)

    plan_path = _write_plan_at(
        plan_dir, n_steps=n_steps, change_types=change_types
    )
    result = CreateResult(
        plan_path=plan_path,
        manifest_path=created / ".plan-tool" / "plans.json",
        manifest_updated=True,
    )
    return result, original.resolve(), created.resolve()


# --- derivation helper -----------------------------------------------------


def test_created_repo_root_derives_from_plan_path_parent(tmp_path: Path) -> None:
    # An unrelated ancestor marker plus the owning root's own marker: the helper
    # walks up from the plan's parent and returns the NEAREST (owning) root.
    _mark_project_root(tmp_path)  # unrelated ancestor
    owning = tmp_path / "owning"
    _mark_project_root(owning)
    plan_dir = owning / "docs" / "implementation-plans"
    plan_dir.mkdir(parents=True)
    plan_path = plan_dir / "plan.md"
    plan_path.write_text("x", encoding="utf-8")
    result = CreateResult(
        plan_path=plan_path,
        manifest_path=owning / ".plan-tool" / "plans.json",
        manifest_updated=True,
    )
    assert derive_created_repo_root(result) == owning.resolve()


def test_created_repo_root_matches_common_case(tmp_path: Path) -> None:
    result = _create_result(tmp_path, 3)
    assert derive_created_repo_root(result) == tmp_path.resolve()


# --- refuse-guard: nested / ancestor / disjoint ----------------------------


def test_direct_jira_refuses_nested_relocation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    result, original, _created = _relocated_result(tmp_path, kind="nested")
    commit_roots: list[tuple[Path, str]] = []
    calls, captured = _install_stubs(
        monkeypatch, result, commit_roots=commit_roots
    )
    rc = direct_cmd.cmd_direct_jira(_input_args(original))
    assert rc == 2
    assert "create" in calls  # create ran; refuse fires after it
    for stage in ("detail", "apply", "jira", "commit"):
        assert stage not in calls
    assert commit_roots == []
    assert "nested" in capsys.readouterr().err


def test_direct_run_refuses_nested_relocation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    result, original, _created = _relocated_result(
        tmp_path, kind="nested", change_types=[ChangeType.FEATURE]
    )
    commit_roots: list[tuple[Path, str]] = []
    calls, _, reconcile_calls = _install_run_stubs(
        monkeypatch, result, commit_roots=commit_roots
    )
    rc = direct_cmd.cmd_direct_run(_input_args(original))
    assert rc == 2
    assert "create" in calls
    for stage in ("detail", "apply", "run", "reconcile", "commit"):
        assert stage not in calls
    assert reconcile_calls == []
    assert commit_roots == []
    assert "nested" in capsys.readouterr().err


def test_direct_jira_refuses_ancestor_relocation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    result, original, _created = _relocated_result(tmp_path, kind="ancestor")
    calls, _ = _install_stubs(monkeypatch, result)
    rc = direct_cmd.cmd_direct_jira(_input_args(original))
    assert rc == 2
    for stage in ("detail", "apply", "jira", "commit"):
        assert stage not in calls
    assert "nested" in capsys.readouterr().err


def test_direct_jira_disjoint_relocation_not_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result, original, _created = _relocated_result(tmp_path, kind="disjoint")
    calls, _ = _install_stubs(monkeypatch, result)
    rc = direct_cmd.cmd_direct_jira(_input_args(original))
    assert rc == 0
    for stage in ("detail", "apply", "jira"):
        assert stage in calls


# --- threading the relocated root into stage namespaces --------------------


def test_direct_jira_threads_relocated_repo_root_into_stage_namespaces(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result, original, created = _relocated_result(tmp_path, kind="disjoint")
    _, captured = _install_stubs(monkeypatch, result)
    direct_cmd.cmd_direct_jira(_input_args(original))
    for stage in ("detail", "apply", "jira"):
        assert captured[stage].repo_root == created
        assert captured[stage].repo_root != original


def test_direct_run_threads_relocated_repo_root_into_stage_namespaces(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result, original, created = _relocated_result(
        tmp_path,
        kind="disjoint",
        change_types=[ChangeType.FEATURE, ChangeType.REFACTOR],
    )
    _, captured, reconcile_calls = _install_run_stubs(monkeypatch, result)
    direct_cmd.cmd_direct_run(_input_args(original))
    for stage in ("detail", "apply", "run"):
        assert captured[stage].repo_root == created
    assert reconcile_calls  # both steps are code steps
    for ns in reconcile_calls:
        assert ns.repo_root == created


# --- git-ops target the relocated root -------------------------------------


def test_direct_jira_commits_against_relocated_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result, original, created = _relocated_result(tmp_path, kind="disjoint")
    commit_roots: list[tuple[Path, str]] = []
    # step-0 clean, sweep clean, then author + apply gates dirty.
    _install_stubs(
        monkeypatch,
        result,
        dirty_sequence=[False, False, True, True],
        commit_roots=commit_roots,
    )
    direct_cmd.cmd_direct_jira(_input_args(original))
    assert commit_roots  # the two post-create commits landed
    assert all(root == created for root, _ in commit_roots)
    assert not any(root == original for root, _ in commit_roots)


def test_direct_run_commits_against_relocated_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result, original, created = _relocated_result(
        tmp_path, kind="disjoint", change_types=[ChangeType.FEATURE]
    )
    commit_roots: list[tuple[Path, str]] = []
    _install_run_stubs(
        monkeypatch,
        result,
        dirty_sequence=[False, False, True, True],
        commit_roots=commit_roots,
    )
    direct_cmd.cmd_direct_run(_input_args(original))
    assert commit_roots
    assert all(root == created for root, _ in commit_roots)
    assert not any(root == original for root, _ in commit_roots)


def test_direct_jira_start_precondition_uses_original_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result, original, created = _relocated_result(tmp_path, kind="disjoint")
    dirty_roots: list[Path] = []
    _install_stubs(monkeypatch, result, dirty_roots=dirty_roots)
    direct_cmd.cmd_direct_jira(_input_args(original))
    # The very first dirty check is the step-0 precondition, before create's
    # relocation is known — it must target the original root, not the relocated.
    assert dirty_roots[0] == original


# --- original-root seed-dirt sweep -----------------------------------------


def test_direct_jira_relocated_commits_original_root_dirt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result, original, created = _relocated_result(tmp_path, kind="disjoint")
    commit_roots: list[tuple[Path, str]] = []
    calls, _ = _install_stubs(
        monkeypatch,
        result,
        # step-0 clean, sweep dirty (commit original), later gates clean.
        dirty_sequence=[False, True, False, False],
        commit_roots=commit_roots,
    )
    direct_cmd.cmd_direct_jira(_input_args(original))
    assert len(commit_roots) == 1
    root, subject = commit_roots[0]
    assert root == original
    assert "archive superseded seed after relocation" in subject
    # The sweep commit precedes any downstream stage.
    assert calls.index("commit") < calls.index("detail")


def test_direct_run_relocated_commits_original_root_dirt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result, original, created = _relocated_result(
        tmp_path, kind="disjoint", change_types=[ChangeType.FEATURE]
    )
    commit_roots: list[tuple[Path, str]] = []
    calls, _, _ = _install_run_stubs(
        monkeypatch,
        result,
        dirty_sequence=[False, True, False, False],
        commit_roots=commit_roots,
    )
    direct_cmd.cmd_direct_run(_input_args(original))
    assert len(commit_roots) == 1
    root, subject = commit_roots[0]
    assert root == original
    assert "archive superseded seed after relocation" in subject
    assert calls.index("commit") < calls.index("detail")


def test_direct_jira_relocated_original_root_clean_no_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result, original, created = _relocated_result(tmp_path, kind="disjoint")
    commit_roots: list[tuple[Path, str]] = []
    calls, _ = _install_stubs(
        monkeypatch,
        result,
        dirty_sequence=[False, False, False, False],
        commit_roots=commit_roots,
    )
    direct_cmd.cmd_direct_jira(_input_args(original))
    # Original root clean at the sweep: no extra commit against it; chain
    # proceeds straight to threading the relocated root.
    assert not any(root == original for root, _ in commit_roots)
    for stage in ("detail", "apply", "jira"):
        assert stage in calls


def test_direct_jira_no_relocation_no_original_root_commit_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # created_repo_root == repo_root: the relocation branch (and its sweep dirty
    # check) must be skipped entirely — only the step-0, author, and apply
    # dirty checks fire (3 total), never a 4th sweep check.
    result = _create_result(tmp_path, 2)
    dirty_roots: list[Path] = []
    _install_stubs(monkeypatch, result, dirty_roots=dirty_roots)
    direct_cmd.cmd_direct_jira(_input_args(tmp_path))
    assert len(dirty_roots) == 3


# --- no-relocation regression guards ---------------------------------------


def test_direct_jira_no_relocation_repo_root_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _create_result(tmp_path, 2)
    resolved = tmp_path.resolve()
    commit_roots: list[tuple[Path, str]] = []
    dirty_roots: list[Path] = []
    _, captured = _install_stubs(
        monkeypatch,
        result,
        dirty_after=True,
        dirty_roots=dirty_roots,
        commit_roots=commit_roots,
    )
    direct_cmd.cmd_direct_jira(_input_args(tmp_path))
    for stage in ("detail", "apply", "jira"):
        assert captured[stage].repo_root == resolved
    for root in dirty_roots:
        assert root == resolved
    for root, _ in commit_roots:
        assert root == resolved


def test_direct_run_no_relocation_repo_root_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _create_result_typed(tmp_path, [ChangeType.FEATURE])
    resolved = tmp_path.resolve()
    commit_roots: list[tuple[Path, str]] = []
    dirty_roots: list[Path] = []
    _, captured, reconcile_calls = _install_run_stubs(
        monkeypatch,
        result,
        dirty_after=True,
        dirty_roots=dirty_roots,
        commit_roots=commit_roots,
    )
    direct_cmd.cmd_direct_run(_input_args(tmp_path))
    for stage in ("detail", "apply", "run"):
        assert captured[stage].repo_root == resolved
    for ns in reconcile_calls:
        assert ns.repo_root == resolved
    for root in dirty_roots:
        assert root == resolved
    for root, _ in commit_roots:
        assert root == resolved


# --- step 3: relocated-root cleanliness guard ------------------------------
#
# On a disjoint relocation, ``create``'s downstream stages commit against the
# relocated root. Before ``detail`` runs, the verb checks that root holds no
# uncommitted work beyond ``create``'s own writes — otherwise the stage-4
# ``git add -A`` would fold a stranger's changes into the authoring commit.
# The guard's ``unexpected_dirty_paths`` call is stubbed here (its real git
# behavior is covered in tests/cli/test_gitcommit.py); these tests assert the
# wiring: abort on dirt, proceed when clean, inert with no relocation.


def _collision_replace_fixture(
    tmp_path: Path, *, change_types: list[ChangeType | None] | None = None
) -> tuple[CreateResult, Path, Path, Path, Path]:
    """A disjoint-relocation CreateResult carrying collision-replace writes.

    Returns ``(result, original, created, archived, renamed)`` — the archived
    superseded plan and the renamed detail directory both land under the
    relocated ``created`` root, so the guard must treat them as create's own.
    """
    result, original, created = _relocated_result(
        tmp_path, kind="disjoint", change_types=change_types
    )
    archived = created / "docs" / "implementation-plans" / "archive" / "old.md"
    renamed = created / "docs" / "implementation-plans" / "plan-details" / "plan"
    result.replaced_archives = [(created / "old.md", archived)]
    result.replaced_manifest_entries = ["docs/implementation-plans/old.md"]
    result.plan_details_renamed_to = renamed
    return result, original, created, archived, renamed


def test_direct_jira_relocated_root_with_unrelated_dirt_aborts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result, original, _created = _relocated_result(tmp_path, kind="disjoint")
    calls, _ = _install_stubs(monkeypatch, result, reloc_dirt=["stranger.txt"])
    rc = direct_cmd.cmd_direct_jira(_input_args(original))
    assert rc == 2
    assert "create" in calls
    for stage in ("detail", "apply", "jira"):
        assert stage not in calls


def test_direct_run_relocated_root_with_unrelated_dirt_aborts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result, original, _created = _relocated_result(
        tmp_path, kind="disjoint", change_types=[ChangeType.FEATURE]
    )
    calls, _, reconcile_calls = _install_run_stubs(
        monkeypatch, result, reloc_dirt=["stranger.txt"]
    )
    rc = direct_cmd.cmd_direct_run(_input_args(original))
    assert rc == 2
    assert "create" in calls
    for stage in ("detail", "apply", "run", "reconcile"):
        assert stage not in calls
    assert reconcile_calls == []


def test_direct_jira_relocated_root_unreadable_git_aborts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # None (git status unreadable) must be treated the same as unexpected dirt.
    result, original, _created = _relocated_result(tmp_path, kind="disjoint")
    calls, _ = _install_stubs(monkeypatch, result, reloc_dirt=None)
    rc = direct_cmd.cmd_direct_jira(_input_args(original))
    assert rc == 2
    for stage in ("detail", "apply", "jira"):
        assert stage not in calls


def test_direct_jira_relocated_root_clean_proceeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result, original, _created = _relocated_result(tmp_path, kind="disjoint")
    calls, _ = _install_stubs(monkeypatch, result)  # reloc clean by default
    rc = direct_cmd.cmd_direct_jira(_input_args(original))
    assert rc == 0
    for stage in ("detail", "apply", "jira"):
        assert stage in calls


def test_direct_run_relocated_root_clean_proceeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result, original, _created = _relocated_result(
        tmp_path, kind="disjoint", change_types=[ChangeType.FEATURE]
    )
    calls, _, reconcile_calls = _install_run_stubs(monkeypatch, result)
    rc = direct_cmd.cmd_direct_run(_input_args(original))
    assert rc == 0
    for stage in ("detail", "apply", "run"):
        assert stage in calls
    assert reconcile_calls  # the feature step reconciled


def test_direct_jira_relocated_root_grounding_sidecar_not_flagged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # No concepts.json in play — prove the always-present grounding sidecar is
    # in the expected set on its own, not misread as a stranger's dirt.
    result, original, _created = _relocated_result(tmp_path, kind="disjoint")
    sink: list[Path] = []
    calls, _ = _install_stubs(monkeypatch, result, reloc_expected_sink=sink)
    rc = direct_cmd.cmd_direct_jira(_input_args(original))
    assert rc == 0
    assert grounding_path(result.plan_path) in sink
    assert concepts_path(result.plan_path) in sink
    for stage in ("detail", "apply", "jira"):
        assert stage in calls


def test_direct_jira_no_relocation_skips_guard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _create_result(tmp_path, 2)
    sink: list[Path] = []
    calls, _ = _install_stubs(monkeypatch, result, reloc_expected_sink=sink)
    rc = direct_cmd.cmd_direct_jira(_input_args(tmp_path))
    assert rc == 0
    assert sink == []  # created == repo_root: the guard never ran
    for stage in ("detail", "apply", "jira"):
        assert stage in calls


def test_direct_run_no_relocation_skips_guard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _create_result_typed(tmp_path, [ChangeType.FEATURE])
    sink: list[Path] = []
    calls, _, _ = _install_run_stubs(
        monkeypatch, result, reloc_expected_sink=sink
    )
    rc = direct_cmd.cmd_direct_run(_input_args(tmp_path))
    assert rc == 0
    assert sink == []
    for stage in ("detail", "apply", "run"):
        assert stage in calls


def test_direct_jira_relocated_dirt_message_names_offending_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    result, original, _created = _relocated_result(tmp_path, kind="disjoint")
    _install_stubs(monkeypatch, result, reloc_dirt=["a/weird_stranger.txt"])
    direct_cmd.cmd_direct_jira(_input_args(original))
    err = capsys.readouterr().err
    assert "a/weird_stranger.txt" in err


def test_direct_jira_relocated_collision_replace_writes_not_flagged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result, original, _created, archived, renamed = _collision_replace_fixture(
        tmp_path
    )
    sink: list[Path] = []
    calls, _ = _install_stubs(monkeypatch, result, reloc_expected_sink=sink)
    rc = direct_cmd.cmd_direct_jira(_input_args(original))
    assert rc == 0
    # The collision-replace writes are in the expected set...
    assert archived in sink
    assert renamed in sink
    # ...and the chain proceeds because the guard saw no unrelated dirt.
    for stage in ("detail", "apply", "jira"):
        assert stage in calls


def test_direct_jira_relocated_collision_replace_plus_stranger_still_aborts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result, original, _created, _archived, _renamed = _collision_replace_fixture(
        tmp_path
    )
    calls, _ = _install_stubs(
        monkeypatch, result, reloc_dirt=["stranger.txt"]
    )
    rc = direct_cmd.cmd_direct_jira(_input_args(original))
    assert rc == 2  # expanding the expected set didn't blanket-allow everything
    for stage in ("detail", "apply", "jira"):
        assert stage not in calls


def test_direct_jira_relocated_plan_tool_state_not_flagged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # create writes .plan-tool/ tool state (telemetry, checkpoints) on every
    # create, and the relocated root may not gitignore it. The whole directory
    # must be in the expected set, or the supported disjoint path false-aborts.
    result, original, created = _relocated_result(tmp_path, kind="disjoint")
    sink: list[Path] = []
    calls, _ = _install_stubs(monkeypatch, result, reloc_expected_sink=sink)
    rc = direct_cmd.cmd_direct_jira(_input_args(original))
    assert rc == 0
    assert created / ".plan-tool" in sink
    for stage in ("detail", "apply", "jira"):
        assert stage in calls


def test_direct_jira_relocated_collision_replace_includes_deleted_original(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # archive_existing_source unlinks the superseded plan, so git reports a
    # ' D old.md' the archived copy alone doesn't cover — the deleted original
    # (replaced_archives[i][0]) must be in the expected set too.
    result, original, created, _archived, _renamed = _collision_replace_fixture(
        tmp_path
    )
    deleted_original = created / "old.md"  # replaced_archives[0][0]
    sink: list[Path] = []
    calls, _ = _install_stubs(monkeypatch, result, reloc_expected_sink=sink)
    rc = direct_cmd.cmd_direct_jira(_input_args(original))
    assert rc == 0
    assert deleted_original in sink
    for stage in ("detail", "apply", "jira"):
        assert stage in calls


# --- step 4: end-to-end real-relocation coverage ---------------------------
#
# The step 2/3 tests above stub every stage handler and hand-build a relocated
# CreateResult. This section instead triggers relocation FOR REAL: a
# ``--from-existing`` seed whose body references a file under a *different*
# ``.git`` repo drives the real ``cmd_create``'s seed-derived umbrella override
# (``find_umbrella_root`` case 1 — a disjoint/sibling root), and the real
# ``cmd_direct_jira`` / ``cmd_direct_run`` chains run end to end against the
# relocated root. Only the backend (the claude subprocess) and the execution
# primitives (``run_step`` / ``export_jira``) are neutralized; every stage
# HANDLER (create, detail, completeness-apply, run, reconcile-code, jira) runs
# for real. A NESTED/ancestor relocation is refused by the already-shipped
# ``_resolve_created_repo_root`` guard (rc 2, "nested"); both are covered.

import json as _s4_json
import os as _s4_os
import subprocess as _s4_subprocess

from plan_tool import backend_runner as _s4_backend_runner
from plan_tool import create as _s4_create_module
from plan_tool import detail as _s4_detail_module
from plan_tool import launcher as _s4_launcher_module
from plan_tool import shell as _s4_shell_module
from plan_tool.cli import jira_cmd as _s4_jira_cmd_module
from plan_tool.cli import reconcile as _s4_reconcile_module
from plan_tool.cli import run_cmd as _s4_run_cmd_module
from plan_tool.launcher import ApplyFindingResult as _S4ApplyFindingResult
from plan_tool.launcher import mark_done_and_advance as _s4_mark_done_and_advance
from plan_tool.launcher import resolve_step as _s4_resolve_step
from plan_tool.parser import parse_plan as _s4_parse_plan


# Canned backend envelopes keyed by prompt substring (shapes borrowed from
# tests/test_create.py and tests/test_detail.py — the gates each one clears).
_S4_STEP_JSON = _s4_json.dumps(
    [{"title": "first", "complexity": "low", "files": [], "depends_on": []}]
)
_S4_REF_JSON = _s4_json.dumps(
    [{"title": "Docs", "url": "https://example.com", "description": "x"}]
)
_S4_PRODUCT_REF_JSON = _s4_json.dumps(
    [{
        "token": "hosting-1",
        "references": [{
            "title": "Original product docs",
            "url": "https://original.example.com/docs",
            "description": "Documents the product selected by the original roadmap.",
        }],
    }]
)
# Every required body section populated so create's non-iterating TODO gate
# (active with iterate=False) accepts the plan.
_S4_BODY_JSON = _s4_json.dumps({
    "Overview": "o", "Problem statement": "p", "Architecture": "a",
    "Out of scope": "s", "Risks": "r", "Testing": "t",
    "Acceptance criteria": "c", "Deferred": "d",
})
def _s4_preparation_json(prompt: str) -> str:
    evidence_line = next(
        int(number)
        for raw_line in prompt.splitlines()
        if (number := raw_line.partition("\t")[0]).isdigit()
        and (source_line := raw_line.partition("\t")[2]).strip()
        and not source_line.lstrip().startswith(("#", "---"))
    )
    return _s4_json.dumps({
        "outcome": "single",
        "sections": {
            "Overview": "o", "Problem statement": "p", "Architecture": "a",
            "Out of scope": "s", "Risks": "r", "Testing": "t",
            "Acceptance criteria": "c", "Deferred": "d",
        },
        "evidence_spans": {
            key: [{"start_line": evidence_line, "end_line": evidence_line}]
            for key in (
                "Out of scope",
                "Risks",
                "Testing",
                "Acceptance criteria",
                "Deferred",
            )
        },
    })
# A well-formed 7-section detail body (mirrors tests/test_detail.py
# ``_FIVE_SECTIONS``) plus the empty-deferrals transport envelope the
# structured-detail parser expects.
_S4_DETAIL_BODY = (
    "# Step - detail\n\n"
    "## Summary\n\nReviewer-facing overview of the step.\n\n"
    "## Table of Contents\n\n"
    "- [Why](#why) - motivation\n"
    "- [Files](#files) - paths touched\n"
    "- [Implementation](#implementation) - walkthrough\n"
    "- [Tests](#tests) - coverage\n"
    "- [Acceptance criteria](#acceptance-criteria) - verifiable bullets\n\n"
    "## Why\n\nReason.\n\n"
    "## Files\n\n- foo.py\n\n"
    "## Implementation\n\nWalkthrough.\n\n"
    "## Tests\n\n- one test\n\n"
    "## Acceptance criteria\n\n- returns 42\n"
)
_S4_DETAIL_RESPONSE = (
    _S4_DETAIL_BODY
    + '\n\n<!-- plan-tool-detail-deferrals\n{"deferrals":[]}\n-->'
)


_S4_CONCEPTUAL_AUDIT_CLEAN_RESPONSE = (
    "## Correctness findings\n\n_(none)_\n\n"
    "## Completeness findings\n\n_(none)_\n"
)


def _s4_route(prompt: str) -> str:
    """Route a backend prompt to its canned response.

    Create's steps/refs/body proposals get valid JSON; detail generation gets a
    7-section body; the conceptual audit gets a well-formed empty-findings body
    (a raw ``""`` reads as a malformed/empty backend response and leaves the
    saved sidecar's coverage ``unconfirmed`` — refused as current evidence by
    the completeness-stage-bar-reporting qualified-result gate every sidecar
    consumer now enforces, including ``completeness-apply`` below). Everything
    else returns an inert response so it parses to no findings / a no-op. That
    keeps the conceptual gap map empty,
    so ``completeness-apply`` is a near no-op (empty gap map -> no
    ``apply_finding``, no worktrees).
    """
    if "Propose an initial plan step-list" in prompt:
        return _S4_STEP_JSON
    if "Requested products:" in prompt:
        return _S4_PRODUCT_REF_JSON
    if "developer and API reference documentation" in prompt:
        return _S4_REF_JSON
    if "Synthesize plan body sections" in prompt:
        return _S4_BODY_JSON
    if "Distill a free-form seed into a canonical plan body" in prompt:
        return _s4_preparation_json(prompt)
    if "per-step implementation detail file" in prompt:
        return _S4_DETAIL_RESPONSE
    if "You are auditing this plan's" in prompt:
        return _S4_CONCEPTUAL_AUDIT_CLEAN_RESPONSE
    return "noop"


def _s4_apply_stub(*_a: object, **_kw: object) -> _S4ApplyFindingResult:
    """A no-op ``apply_finding`` for every convergence loop (create/detail/
    completeness-apply). ``NOT-APPLICABLE`` mutates nothing, so a loop sees no
    progress and converges/stalls out fast rather than shelling out."""
    return _S4ApplyFindingResult(
        step_id=None,
        exit_code=0,
        verdict="NOT-APPLICABLE",
        summary="",
        diff_text="",
        pre_snapshot={},
        stdout="",
    )


class _S4RunResult:
    """Minimal ``run_step`` return stub (the fields cmd_run's sweep and
    reconcile-code read)."""

    def __init__(
        self,
        *,
        step_id: int,
        advanced_to: "int | None" = None,
        done: bool = True,
        plan_completed: bool = False,
        exit_code: int = 0,
        stdout: str = "",
    ) -> None:
        self.step_id = step_id
        self.advanced_to = advanced_to
        self.done = done
        self.plan_completed = plan_completed
        self.exit_code = exit_code
        self.stdout = stdout


def _s4_fake_run_step(plan_path, **kwargs):
    """Advance the plan the way the real ``run_step`` does - mark the resolved
    step DONE and persist - so cmd_run ``--all`` terminates (the next
    ``resolve_step`` finds nothing runnable). Never shells out."""
    step_id = kwargs.get("step_id")
    plan = _s4_parse_plan(plan_path)
    step = _s4_resolve_step(plan, step_id)
    advanced = _s4_mark_done_and_advance(plan, step)
    write_plan(plan_path, plan, expect_unchanged=False)
    return _S4RunResult(
        step_id=step.id,
        advanced_to=advanced,
        done=True,
        plan_completed=plan.all_steps_done,
    )


class _S4FakePipe:
    """Minimal Popen.stdout/.stderr stand-in — local (not imported from
    tests/subprocess_doubles.py) since a bare top-level import isn't
    reliable from tests/cli/, whose own directory (not tests/) is what
    pytest inserts onto sys.path for files collected here."""

    def __init__(self, lines: list) -> None:
        self._lines = list(lines)

    def __iter__(self):
        return iter(self._lines)


class _S4FakeProc:
    def __init__(self, stdout_lines: list, stderr_lines: list, returncode: int) -> None:
        self.stdout = _S4FakePipe(stdout_lines)
        self.stderr = _S4FakePipe(stderr_lines)
        self.returncode = returncode
        self.stdin = None

    def wait(self) -> int:
        return self.returncode


def _s4_install_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    """Route backend (claude) subprocess calls to canned envelopes while
    letting real ``git`` calls through. Patches the shared
    ``backend_runner.subprocess.Popen`` that both ``claude_invoke``'s spawn
    and ``plan_tool.cli.gitcommit`` (via ``subprocess.run``, which spawns
    through the same global ``Popen``) reach, branching on argv[0] so git
    plumbing (init/status/commit/log) still executes for real."""
    real_popen = _s4_backend_runner.subprocess.Popen  # delegates git -> real

    def fake_popen(argv, **kwargs):
        first = argv[0] if isinstance(argv, (list, tuple)) and argv else argv
        base = _s4_os.path.basename(str(first)) if isinstance(first, str) else ""
        if base in {"claude", "codex", "agent"}:
            prompt = argv[-1] if isinstance(argv, (list, tuple)) else ""
            envelope = _s4_json.dumps({
                "type": "result",
                "result": _s4_route(prompt),
                "usage": {
                    "input_tokens": 1, "output_tokens": 1,
                    "cache_creation_input_tokens": 0,
                    "cache_read_input_tokens": 0,
                },
            })
            return _S4FakeProc((envelope + "\n").splitlines(keepends=True), [], 0)
        return real_popen(argv, **kwargs)

    monkeypatch.setattr(
        _s4_shell_module.shutil, "which", lambda _n: "/usr/bin/claude"
    )
    monkeypatch.setattr(_s4_backend_runner.subprocess, "Popen", fake_popen)


def _s4_install_chain(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Neutralize every backend seam the real chain touches and return a
    ``stages`` list the execution/jira fakes append to (``run`` / ``reconcile``
    / ``jira``) so a caller can assert which tail stages actually ran."""
    monkeypatch.delenv("PLAN_TOOL_REPO_ROOT", raising=False)
    monkeypatch.delenv("PLAN_TOOL_PLANS_DIR", raising=False)
    monkeypatch.delenv("PLAN_TOOL_BACKEND", raising=False)

    _s4_install_backend(monkeypatch)

    # apply_finding is read as a bare/qualified name at each call site.
    monkeypatch.setattr(_s4_create_module, "apply_finding", _s4_apply_stub)
    monkeypatch.setattr(_s4_detail_module, "apply_finding", _s4_apply_stub)
    monkeypatch.setattr(_s4_launcher_module, "apply_finding", _s4_apply_stub)

    stages: list[str] = []

    def run_step_recording(plan_path, **kwargs):
        stages.append("run")
        return _s4_fake_run_step(plan_path, **kwargs)

    def reconcile_run_step(plan_path, **kwargs):
        stages.append("reconcile")
        return _S4RunResult(
            step_id=kwargs.get("step_id") or 1,
            done=False,
            exit_code=0,
            stdout="",
        )

    monkeypatch.setattr(_s4_run_cmd_module, "run_step", run_step_recording)
    monkeypatch.setattr(_s4_reconcile_module, "run_step", reconcile_run_step)

    from plan_tool.jira import JiraPublicationResult
    from plan_tool.jira_config import Epic

    def fake_export(path, **kwargs):
        stages.append("jira")
        return JiraPublicationResult(
            story_path=kwargs["story_output_path"],
            handoff_path=kwargs["handoff_output_path"],
            story_output="",
            handoff_output="",
            stories=[],
            dropped_history=[],
            changed_created_tickets=[],
            created_to_dropped=[],
        )

    monkeypatch.setattr(_s4_jira_cmd_module, "export_jira", fake_export)
    monkeypatch.setattr(
        _s4_jira_cmd_module,
        "_resolve_epic_for_plan",
        lambda *a, **k: Epic(key="TST", name="Test"),
    )
    monkeypatch.setattr(
        _s4_jira_cmd_module,
        "_resolve_plan_tag_for_plan",
        lambda *a, **k: "tst",
    )
    return stages


def _s4_git_init(root: Path) -> None:
    """git-init + identity (mirrors tests/cli/test_gitcommit.py). git is not a
    blocked backend binary, so this is allowed under the autouse claude gate."""
    root.mkdir(parents=True, exist_ok=True)
    for cmd in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "t@example.com"],
        ["git", "config", "user.name", "Test"],
    ):
        _s4_subprocess.run(cmd, cwd=root, check=True, capture_output=True)


def _s4_git(root: Path, *args: str):
    return _s4_subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True
    )


def _s4_commit_all(root: Path, message: str) -> None:
    _s4_git(root, "add", "-A")
    _s4_git(root, "commit", "-q", "-m", message)


def _s4_setup_repo(root: Path) -> None:
    """Real git repo + plan-tool project root with a realistic ``.gitignore``.

    ``.plan-tool/`` transient state (``runs/``, ``telemetry/``, ``reviews/``,
    checkpoints) is gitignored in every real repo, so create's run-log /
    telemetry writes under a relocated root don't register as ``git status``
    dirt (the relocated-root cleanliness guard reads real ``git status``). Only
    the tracked ``plans.json`` manifest stays visible. Commits an initial state
    so HEAD exists and the tree starts clean."""
    _s4_git_init(root)
    _mark_project_root(root)
    (root / ".gitignore").write_text(
        ".plan-tool/*\n!.plan-tool/plans.json\n", encoding="utf-8"
    )
    _s4_commit_all(root, "init")


def _s4_seed_body(referenced_root: Path) -> str:
    """A prose seed whose ONLY file-path token is an absolute path resolving
    under ``referenced_root`` - so ``find_umbrella_root`` buckets every
    candidate to that repo's ``.git`` (case 1) and relocates there."""
    ref = (referenced_root / "pkg" / "mod.py").resolve()
    return (
        "# Widget notes\n\n"
        "Build the widget the reference describes.\n\n"
        f"See `{ref}` for the reference implementation.\n\n"
        "## References\n\n"
        "- [Widget API](https://example.test/widget-api)\n"
    )


def _s4_disjoint_repos(tmp_path: Path) -> tuple[Path, Path]:
    """Two real sibling git repos (each also a plan-tool project root) with an
    initial commit so HEAD exists and status starts clean. Returns
    ``(original, sibling)``; the seed references a path under ``sibling``."""
    original = tmp_path / "orig"
    sibling = tmp_path / "sib"
    for root in (original, sibling):
        _s4_setup_repo(root)
    return original, sibling


def _s4_nested_repos(tmp_path: Path) -> tuple[Path, Path]:
    """A real outer git repo with a nested inner git repo (``inner/`` gitignored
    in the outer so the outer's status stays clean). Returns ``(outer, inner)``;
    the seed references a path under ``inner`` (an ancestor->descendant, i.e.
    nested, relocation the direct verbs must refuse)."""
    outer = tmp_path / "outer"
    inner = outer / "inner"
    _s4_git_init(outer)
    _mark_project_root(outer)
    # ``inner/`` gitignored so the outer's status stays clean despite the nested
    # repo; ``.plan-tool/`` transient state gitignored as in a real repo.
    (outer / ".gitignore").write_text(
        "inner/\n.plan-tool/*\n!.plan-tool/plans.json\n", encoding="utf-8"
    )
    _s4_commit_all(outer, "init")
    _s4_setup_repo(inner)
    return outer, inner


def _s4_write_committed_seed(root: Path, referenced_root: Path) -> Path:
    """Write ``root/seed.md`` referencing ``referenced_root`` and commit it into
    ``root`` (so the chain's step-0 clean-tree precondition passes). ``create``
    later archives it, which re-dirties ``root`` - the original-root sweep."""
    seed = root / "seed.md"
    seed.write_text(_s4_seed_body(referenced_root), encoding="utf-8")
    _s4_commit_all(root, "add seed")
    return seed


def _s4_write_promoted_tracked_seed(root: Path, referenced_root: Path) -> Path:
    """Create a promoted marker seed whose roadmap stays under ``root``."""
    from plan_tool.roadmap_artifacts import (
        ComponentsArtifact,
        ConstraintsArtifact,
        HostingRow,
        PlanDisposition,
        PlanRow,
        PlansArtifact,
        ResearchDisclosure,
        render_components_artifact,
        render_constraints_artifact,
        render_plans_artifact,
        roadmap_dir,
    )
    from plan_tool.roadmap_seed_state import (
        empty_seed_state,
        render_seed_state_marker,
        seed_state_path,
        write_seed_state,
    )
    from tests.roadmap_accepted_fixtures import publish_accepted_root, with_minimal_upstream

    plans_dir = root / "docs" / "implementation-plans"
    slug = "original-roadmap"
    roadmap_root = roadmap_dir(plans_dir, slug)
    roadmap_root.mkdir(parents=True)
    constraints = render_constraints_artifact(
        ConstraintsArtifact(
            dispositions=(), constraints=(), decisions=(), body="# Constraints\n",
            hosting=(HostingRow(
                "host", "compute", "managed", "Original product", None,
                ResearchDisclosure.EXTERNAL,
            ),),
        )
    )
    components = render_components_artifact(
        ComponentsArtifact(
            system_patterns=(), component_patterns=(), components=(), decisions=(),
            body="# Components\n", stores=(),
        )
    )
    plans = render_plans_artifact(
        PlansArtifact(
            plans=(PlanRow(
                "selected", "Selected", PlanDisposition.KEEP, (),
                "plan-seed-drafts/selected.md", "One bounded plan.",
            ),),
            ordering=(), assumptions=(), decisions=(), body="# Roadmap\n",
        )
    )
    domain, _, _, _ = with_minimal_upstream("")
    publish_accepted_root(plans_dir, slug, (domain, constraints, components, plans))
    state_path = seed_state_path(roadmap_root)
    state = empty_seed_state()
    state["seeds"]["selected"] = {
        "draft_seed_path": "plan-seed-drafts/selected.md",
        "status": "current",
        "digest": None,
        "published": True,
    }
    write_seed_state(state_path, state)

    seed = root / "plan-seeds" / "selected.md"
    seed.parent.mkdir()
    seed.write_text(
        _s4_seed_body(referenced_root)
        + "\n"
        + render_seed_state_marker(
            state_path=state_path,
            repo_root=root,
            roadmap_slug=slug,
            plan_id="selected",
        )
        + "\n",
        encoding="utf-8",
    )
    _s4_commit_all(root, "add promoted tracked seed")
    return seed


def _s4_direct_args(
    verb: str, slug: str, seed: Path, **overrides: object
) -> argparse.Namespace:
    """Build a real (parser-derived) namespace for ``verb`` with ``repo_root``
    left unset (None) so ``cmd_create``'s seed-derived relocation can fire.
    Minimizes the backend surface: create-side ``iterate=False`` (skip create's
    own convergence loop - detail still pins its completeness tail on),
    ``no_distill`` on and lesson capture off (its default)."""
    parser, _ = _real_parser_and_dispatch()
    ns = parser.parse_args([verb, slug, "--from-existing", str(seed)])
    assert ns.repo_root is None  # relocation only fires without a pinned root
    ns.no_distill = True
    ns.lessons = False
    ns.iterate = False
    # Unattended: auto-accept create's output-dir / confirm prompts (the
    # direct verbs are one-shot pipelines; -y is the intended posture).
    ns.yes = True
    for key, value in overrides.items():
        setattr(ns, key, value)
    return ns


def _s4_plan_details_dir(repo_root: Path, slug: str) -> Path:
    return repo_root / "docs" / "implementation-plans" / "plan-details" / slug


def _s4_detail_md_files(repo_root: Path, slug: str) -> list[Path]:
    """Per-step detail markdown files under the plan-details bundle.

    ``create`` creates the ``plan-details/<slug>/`` directory for its
    grounding/concepts ``.json`` sidecars, so the directory's *existence* isn't
    a "detail ran" signal; a step-detail ``.md`` file is (only ``cmd_detail``
    writes those)."""
    bundle = _s4_plan_details_dir(repo_root, slug)
    return sorted(bundle.glob("*.md")) if bundle.exists() else []


def _s4_plan_stem(repo_root: Path, slug: str) -> str:
    """The on-disk plan filename stem (carries create's priority prefix, e.g.
    ``2-reloc-plan``) — the ``plan_name`` the direct verbs stamp into commit
    subjects."""
    matches = sorted(
        (repo_root / "docs" / "implementation-plans").glob(f"*-{slug}.md")
    )
    return matches[0].stem if matches else slug


# --- real cmd_create relocation (proves the fixture triggers relocation) ---


@pytest.mark.integration
def test_seed_relocates_to_broader_sibling_root_via_real_create(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original, sibling = _s4_disjoint_repos(tmp_path)
    seed = _s4_write_committed_seed(original, referenced_root=sibling)
    _s4_install_chain(monkeypatch)
    monkeypatch.chdir(original)

    args = _s4_direct_args("direct-jira", "reloc-plan", seed)
    args._create_result_sink = []
    rc = direct_cmd.cmd_create(args)
    assert rc == 0
    result = args._create_result_sink[-1]
    # The plan (and its manifest entry) landed under the SIBLING root, not the
    # original cwd - real relocation happened.
    assert result.plan_path is not None
    assert result.plan_path.resolve().is_relative_to(sibling.resolve())
    assert not result.plan_path.resolve().is_relative_to(original.resolve())
    assert derive_created_repo_root(result) == sibling.resolve()


@pytest.mark.integration
def test_relocated_promoted_tracked_seed_keeps_original_roadmap_research(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original, sibling = _s4_disjoint_repos(tmp_path)
    seed = _s4_write_promoted_tracked_seed(original, referenced_root=sibling)
    _s4_install_chain(monkeypatch)
    monkeypatch.chdir(original)

    args = _s4_direct_args("direct-jira", "reloc-plan", seed)
    args._create_result_sink = []
    assert direct_cmd.cmd_create(args) == 0

    result = args._create_result_sink[-1]
    assert result.plan_path is not None
    assert result.plan_path.resolve().is_relative_to(sibling.resolve())
    assert "https://original.example.com/docs" in result.plan_path.read_text(
        encoding="utf-8"
    )


@pytest.mark.integration
def test_seed_relocates_to_nested_root_via_real_create(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # cmd_create itself does NOT refuse a nested relocation - it relocates; the
    # refuse guard lives in the direct verbs. Proving create really relocates
    # here confirms the refuse tests below exercise a real relocation, not a
    # no-op that trivially "passes".
    outer, inner = _s4_nested_repos(tmp_path)
    seed = _s4_write_committed_seed(outer, referenced_root=inner)
    _s4_install_chain(monkeypatch)
    monkeypatch.chdir(outer)

    args = _s4_direct_args("direct-jira", "reloc-plan", seed)
    args._create_result_sink = []
    rc = direct_cmd.cmd_create(args)
    assert rc == 0
    result = args._create_result_sink[-1]
    assert result.plan_path is not None
    assert result.plan_path.resolve().is_relative_to(inner.resolve())
    assert derive_created_repo_root(result) == inner.resolve()


# --- broader (disjoint) relocation drives the real chain end to end --------


@pytest.mark.integration
def test_direct_jira_broader_relocation_end_to_end(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original, sibling = _s4_disjoint_repos(tmp_path)
    seed = _s4_write_committed_seed(original, referenced_root=sibling)
    stages = _s4_install_chain(monkeypatch)
    monkeypatch.chdir(original)

    rc = direct_cmd.cmd_direct_jira(
        _s4_direct_args("direct-jira", "reloc-plan", seed)
    )
    assert rc == 0
    assert "jira" in stages
    # Every stage's artifacts landed under the sibling root, not the original.
    assert _s4_detail_md_files(sibling, "reloc-plan")
    assert not _s4_plan_details_dir(original, "reloc-plan").exists()


@pytest.mark.integration
def test_direct_run_broader_relocation_end_to_end(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original, sibling = _s4_disjoint_repos(tmp_path)
    seed = _s4_write_committed_seed(original, referenced_root=sibling)
    stages = _s4_install_chain(monkeypatch)
    monkeypatch.chdir(original)

    rc = direct_cmd.cmd_direct_run(
        _s4_direct_args("direct-run", "reloc-plan", seed)
    )
    assert rc == 0
    assert "run" in stages
    assert "reconcile" in stages
    assert _s4_detail_md_files(sibling, "reloc-plan")
    assert not _s4_plan_details_dir(original, "reloc-plan").exists()


# --- nested relocation refused (rc 2, "nested", before any tail stage) -----


@pytest.mark.integration
def test_direct_jira_nested_relocation_seed_refused(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    outer, inner = _s4_nested_repos(tmp_path)
    seed = _s4_write_committed_seed(outer, referenced_root=inner)
    stages = _s4_install_chain(monkeypatch)
    monkeypatch.chdir(outer)

    rc = direct_cmd.cmd_direct_jira(
        _s4_direct_args("direct-jira", "reloc-plan", seed)
    )
    assert rc == 2
    assert "nested" in capsys.readouterr().err
    assert "jira" not in stages
    assert not _s4_detail_md_files(inner, "reloc-plan")


@pytest.mark.integration
def test_direct_run_nested_relocation_seed_refused(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    outer, inner = _s4_nested_repos(tmp_path)
    seed = _s4_write_committed_seed(outer, referenced_root=inner)
    stages = _s4_install_chain(monkeypatch)
    monkeypatch.chdir(outer)

    rc = direct_cmd.cmd_direct_run(
        _s4_direct_args("direct-run", "reloc-plan", seed)
    )
    assert rc == 2
    assert "nested" in capsys.readouterr().err
    assert "run" not in stages
    assert "reconcile" not in stages
    assert not _s4_detail_md_files(inner, "reloc-plan")


# --- relocation commits land in the relocated repo, not the original -------


@pytest.mark.integration
def test_direct_jira_relocation_commits_land_in_relocated_repo_not_original(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original, sibling = _s4_disjoint_repos(tmp_path)
    seed = _s4_write_committed_seed(original, referenced_root=sibling)
    _s4_install_chain(monkeypatch)
    monkeypatch.chdir(original)

    rc = direct_cmd.cmd_direct_jira(
        _s4_direct_args("direct-jira", "reloc-plan", seed)
    )
    assert rc == 0

    stem = _s4_plan_stem(sibling, "reloc-plan")  # carries the priority prefix
    sib_subjects = _s4_git(sibling, "log", "--format=%s").stdout.decode()
    orig_subjects = _s4_git(original, "log", "--format=%s").stdout.decode()
    # The authoring commit lands in the relocated (sibling) repo.
    assert f"direct-jira({stem}): author plan and detail" in sib_subjects
    # The original root only ever carries the superseded-seed sweep commit -
    # never the chain's authoring/apply commits.
    assert (
        f"direct-jira({stem}): archive superseded seed after relocation"
        in orig_subjects
    )
    assert "author plan and detail" not in orig_subjects
    assert "archive superseded seed after relocation" not in sib_subjects


@pytest.mark.integration
def test_direct_run_relocation_commits_land_in_relocated_repo_not_original(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original, sibling = _s4_disjoint_repos(tmp_path)
    seed = _s4_write_committed_seed(original, referenced_root=sibling)
    _s4_install_chain(monkeypatch)
    monkeypatch.chdir(original)

    rc = direct_cmd.cmd_direct_run(
        _s4_direct_args("direct-run", "reloc-plan", seed)
    )
    assert rc == 0

    stem = _s4_plan_stem(sibling, "reloc-plan")  # carries the priority prefix
    sib_subjects = _s4_git(sibling, "log", "--format=%s").stdout.decode()
    orig_subjects = _s4_git(original, "log", "--format=%s").stdout.decode()
    assert f"direct-run({stem}): author plan and detail" in sib_subjects
    assert (
        f"direct-run({stem}): archive superseded seed after relocation"
        in orig_subjects
    )
    assert "author plan and detail" not in orig_subjects


# --- relocated-root pre-existing dirt aborts before detail (real git status)-


@pytest.mark.integration
def test_direct_jira_relocated_root_preexisting_dirt_aborts_before_detail(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    original, sibling = _s4_disjoint_repos(tmp_path)
    seed = _s4_write_committed_seed(original, referenced_root=sibling)
    # Unrelated untracked dirt in the sibling root, outside create's own writes.
    (sibling / "stranger.txt").write_text("unrelated\n", encoding="utf-8")
    stages = _s4_install_chain(monkeypatch)
    monkeypatch.chdir(original)

    rc = direct_cmd.cmd_direct_jira(
        _s4_direct_args("direct-jira", "reloc-plan", seed)
    )
    assert rc != 0
    assert "stranger.txt" in capsys.readouterr().err
    assert "jira" not in stages
    assert not _s4_detail_md_files(sibling, "reloc-plan")


@pytest.mark.integration
def test_direct_run_relocated_root_preexisting_dirt_aborts_before_detail(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    original, sibling = _s4_disjoint_repos(tmp_path)
    seed = _s4_write_committed_seed(original, referenced_root=sibling)
    (sibling / "stranger.txt").write_text("unrelated\n", encoding="utf-8")
    stages = _s4_install_chain(monkeypatch)
    monkeypatch.chdir(original)

    rc = direct_cmd.cmd_direct_run(
        _s4_direct_args("direct-run", "reloc-plan", seed)
    )
    assert rc != 0
    assert "stranger.txt" in capsys.readouterr().err
    assert "run" not in stages
    assert "reconcile" not in stages
    assert not _s4_detail_md_files(sibling, "reloc-plan")


# --- no relocation: the real chain still succeeds on a single root ----------


@pytest.mark.integration
def test_direct_jira_no_relocation_real_chain_still_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A seed with NO umbrella-triggering file reference: cmd_create keeps the
    # cwd-derived root and the whole chain runs against a single root.
    root = tmp_path / "solo"
    _s4_setup_repo(root)
    seed = root / "seed.md"
    seed.write_text(
        "# Widget notes\n\nBuild the widget. No file references here.\n\n"
        "## References\n\n- [Widget API](https://example.test/widget-api)\n",
        encoding="utf-8",
    )
    _s4_commit_all(root, "add seed")
    stages = _s4_install_chain(monkeypatch)
    monkeypatch.chdir(root)

    rc = direct_cmd.cmd_direct_jira(
        _s4_direct_args("direct-jira", "solo-plan", seed)
    )
    assert rc == 0
    assert "jira" in stages
    assert _s4_detail_md_files(root, "solo-plan")
