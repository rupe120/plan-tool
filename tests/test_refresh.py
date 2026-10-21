"""Unit coverage for ``plan_tool.refresh`` — the drift-gate / scoped-reconcile
/ re-stamp entry point.

All tests call :func:`plan_tool.refresh.refresh_plan` directly (the CLI
surface is step 4) and are hermetic (``tmp_path``). Per TESTING.md the
reconcile seam is stubbed: drift cases patch
``plan_tool.auto_reconcile.run_auto_reconcile_on_drift`` with a spy
returning an int, and the no-drift case patches
``plan_tool.launcher.run_step`` to *raise* to prove no invoker is spawned.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from plan_tool.fingerprint import compute_code_fingerprint
from plan_tool.grounding import read_grounding, write_grounding
from plan_tool.parser import ParseError, parse_plan
from plan_tool.review_persistence import compute_plan_fingerprint
from plan_tool.scope_guard import build_file_to_step_map
from plan_tool.refresh import RefreshOutcome, refresh_plan


_VALID_FRONTMATTER = (
    "---\n"
    "title: Demo Plan\n"
    "status: planning\n"
    "priority: medium\n"
    "steps:\n"
    "  - id: 1\n"
    "    title: First step\n"
    "    files:\n"
    "      - src/foo.py\n"
    "      - src/bar.py\n"
    "    detail: docs/details/step-1.md\n"
    "---\n"
    "# Demo Plan\n"
)


def _seed_plan(tmp_path: Path) -> Path:
    """Write a parseable plan with two declared code files + a detail file,
    seed the code on disk, and return the plan path."""
    plan_path = tmp_path / "docs" / "plans" / "2-demo.md"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(_VALID_FRONTMATTER, encoding="utf-8")
    detail = tmp_path / "docs" / "details" / "step-1.md"
    detail.parent.mkdir(parents=True, exist_ok=True)
    detail.write_text("# detail\n", encoding="utf-8")
    src = tmp_path / "src"
    src.mkdir(parents=True, exist_ok=True)
    (src / "foo.py").write_text("foo = 1\n", encoding="utf-8")
    (src / "bar.py").write_text("bar = 2\n", encoding="utf-8")
    return plan_path


def _ground(tmp_path: Path, plan_path: Path) -> None:
    """Write a grounding baseline matching the current code state."""
    plan = parse_plan(plan_path)
    write_grounding(
        plan_path,
        plan_fingerprint=compute_plan_fingerprint(plan_path),
        code_fingerprint=compute_code_fingerprint(plan, plan_path, tmp_path),
    )


def _spy_reconcile(monkeypatch: pytest.MonkeyPatch, *, returns: int = 0):
    """Patch the reconcile seam with a spy capturing its kwargs."""
    calls: list[dict] = []

    def _spy(**kwargs) -> int:
        calls.append(kwargs)
        return returns

    monkeypatch.setattr(
        "plan_tool.auto_reconcile.run_auto_reconcile_on_drift", _spy
    )
    return calls


def test_no_drift_returns_clean_outcome(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan_path = _seed_plan(tmp_path)
    _ground(tmp_path, plan_path)

    outcome = refresh_plan(plan_path, tmp_path)

    assert outcome == RefreshOutcome(plan_slug="demo")
    assert outcome.drifted is False
    assert outcome.reconciled is False
    assert outcome.findings == 0
    assert outcome.grounding_path is None


def test_no_drift_spawns_no_invoker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan_path = _seed_plan(tmp_path)
    _ground(tmp_path, plan_path)

    def _boom(*a, **k):  # pragma: no cover - must never be called
        raise AssertionError("run_step spawned on the no-drift fresh path")

    monkeypatch.setattr("plan_tool.launcher.run_step", _boom)

    outcome = refresh_plan(plan_path, tmp_path)
    assert outcome.reconciled is False


def test_no_drift_does_not_rewrite_sidecar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan_path = _seed_plan(tmp_path)
    _ground(tmp_path, plan_path)
    from plan_tool.grounding import grounding_path

    before = grounding_path(plan_path).read_bytes()
    refresh_plan(plan_path, tmp_path)
    assert grounding_path(plan_path).read_bytes() == before


def test_drift_runs_scoped_reconcile_over_exact_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan_path = _seed_plan(tmp_path)
    _ground(tmp_path, plan_path)
    calls = _spy_reconcile(monkeypatch)

    changed = tmp_path / "src" / "foo.py"
    changed.write_text("foo = 99\n", encoding="utf-8")

    outcome = refresh_plan(plan_path, tmp_path)

    assert len(calls) == 1
    kwargs = calls[0]
    assert kwargs["drifted"] == [changed.resolve()]
    assert kwargs["plan_slug"] == "demo"
    assert kwargs["repo_root"] == tmp_path
    assert kwargs["file_to_step"] == build_file_to_step_map(
        parse_plan(plan_path), tmp_path
    )
    assert outcome.drifted_files == [changed.resolve()]


def test_drift_restamps_grounding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A drift whose reconcile is CLEAN (zero findings — the code moved but
    # nothing plan-affecting) re-stamps the baseline so the next refresh
    # fast-paths. (Drift WITH pending findings is the opposite case — see
    # test_drift_with_findings_does_not_restamp.)
    plan_path = _seed_plan(tmp_path)
    _ground(tmp_path, plan_path)
    _spy_reconcile(monkeypatch)  # returns=0 → clean reconcile

    (tmp_path / "src" / "foo.py").write_text("foo = 99\n", encoding="utf-8")
    refresh_plan(plan_path, tmp_path)

    plan = parse_plan(plan_path)
    expected = compute_code_fingerprint(plan, plan_path, tmp_path)
    assert read_grounding(plan_path).code_fingerprint == expected

    # An immediately-following refresh now takes the no-drift fast path.
    outcome2 = refresh_plan(plan_path, tmp_path)
    assert outcome2.drifted is False
    assert outcome2.reconciled is False


def test_drift_outcome_reports_findings_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan_path = _seed_plan(tmp_path)
    _ground(tmp_path, plan_path)
    _spy_reconcile(monkeypatch, returns=3)

    (tmp_path / "src" / "foo.py").write_text("foo = 99\n", encoding="utf-8")
    outcome = refresh_plan(plan_path, tmp_path)

    assert outcome.findings == 3
    assert outcome.reconciled is True
    assert outcome.drifted is True
    # Pending findings ⇒ baseline NOT re-stamped (gate stays dirty; #68).
    assert outcome.grounding_path is None


def test_drift_with_findings_does_not_restamp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # BACKLOG #68 regression: a drift whose reconcile surfaces (unapplied)
    # findings must NOT re-stamp the grounding — restamping would clear the
    # drift gate against a still-unreconciled plan, so the next --refresh would
    # falsely report "no drift" and mask the staleness. The gate stays dirty
    # until a walk applies the findings.
    plan_path = _seed_plan(tmp_path)
    _ground(tmp_path, plan_path)
    before = read_grounding(plan_path).code_fingerprint
    _spy_reconcile(monkeypatch, returns=2)

    (tmp_path / "src" / "foo.py").write_text("foo = 99\n", encoding="utf-8")
    outcome = refresh_plan(plan_path, tmp_path)

    assert outcome.findings == 2
    assert outcome.grounding_path is None
    # Baseline fingerprint unchanged — the gate was NOT cleared.
    assert read_grounding(plan_path).code_fingerprint == before

    # A second --refresh re-surfaces the drift (still dirty), not a fast no-op.
    outcome2 = refresh_plan(plan_path, tmp_path)
    assert outcome2.drifted is True
    assert outcome2.reconciled is True
    assert outcome2.grounding_path is None


def test_no_baseline_treated_as_needs_grounding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan_path = _seed_plan(tmp_path)  # no grounding written
    calls = _spy_reconcile(monkeypatch)

    outcome = refresh_plan(plan_path, tmp_path)

    assert outcome.needs_grounding is True
    assert outcome.drifted is True
    expected_scope = sorted(
        build_file_to_step_map(parse_plan(plan_path), tmp_path)
    )
    assert outcome.drifted_files == expected_scope
    assert calls[0]["drifted"] == expected_scope
    assert outcome.grounding_path is not None
    assert read_grounding(plan_path) is not None


def test_no_baseline_does_not_crash_on_missing_field(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan_path = _seed_plan(tmp_path)
    from plan_tool.grounding import grounding_path

    # Old-schema / malformed sidecar → read_grounding returns None, so this
    # is treated identically to absent.
    gp = grounding_path(plan_path)
    gp.parent.mkdir(parents=True, exist_ok=True)
    gp.write_text('{"schema_version": 0, "bogus": true}\n', encoding="utf-8")
    _spy_reconcile(monkeypatch)

    outcome = refresh_plan(plan_path, tmp_path)
    assert outcome.needs_grounding is True


def test_missing_creates_file_omitted_no_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan_path = _seed_plan(tmp_path)
    # Declare a creates: file that is not on disk; it must be omitted from
    # the fingerprint rather than crashing.
    text = plan_path.read_text(encoding="utf-8").replace(
        "    detail: docs/details/step-1.md\n",
        "    creates:\n      - src/not_yet.py\n"
        "    detail: docs/details/step-1.md\n",
    )
    plan_path.write_text(text, encoding="utf-8")
    _ground(tmp_path, plan_path)
    _spy_reconcile(monkeypatch)

    # Unchanged tree → no-drift fast path, no crash on the absent creates file.
    outcome = refresh_plan(plan_path, tmp_path)
    assert outcome.drifted is False


def test_footprint_rewrite_restamps_without_reconcile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """files: membership churn (path no longer declared) restamps only."""
    plan_path = _seed_plan(tmp_path)
    _ground(tmp_path, plan_path)
    calls = _spy_reconcile(monkeypatch)

    text = plan_path.read_text(encoding="utf-8").replace(
        "      - src/bar.py\n",
        "",
    )
    plan_path.write_text(text, encoding="utf-8")
    before = read_grounding(plan_path).code_fingerprint

    outcome = refresh_plan(plan_path, tmp_path)

    assert calls == []
    assert outcome.drifted is True
    assert outcome.reconciled is False
    assert outcome.drifted_files == []
    assert outcome.grounding_path is not None
    after = read_grounding(plan_path).code_fingerprint
    assert after != before
    assert "src/bar.py" not in after


def test_declared_file_deleted_routes_to_reconcile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Still-declared path missing on disk must not silently restamp."""
    plan_path = _seed_plan(tmp_path)
    _ground(tmp_path, plan_path)
    calls = _spy_reconcile(monkeypatch)
    before = read_grounding(plan_path).code_fingerprint

    (tmp_path / "src" / "bar.py").unlink()

    outcome = refresh_plan(plan_path, tmp_path)

    assert len(calls) == 1
    assert calls[0]["drifted"] == [(tmp_path / "src" / "bar.py").resolve()]
    assert outcome.drifted is True
    assert outcome.reconciled is True
    assert outcome.drifted_files == [(tmp_path / "src" / "bar.py").resolve()]
    # Clean reconcile (spy returns 0) restamps; gate captures the thinner map.
    assert read_grounding(plan_path).code_fingerprint != before
    assert "src/bar.py" not in read_grounding(plan_path).code_fingerprint


def test_content_drift_unions_still_declared_deletes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Content edit + still-declared delete must both enter reconcile scope."""
    plan_path = _seed_plan(tmp_path)
    _ground(tmp_path, plan_path)
    calls = _spy_reconcile(monkeypatch)

    (tmp_path / "src" / "foo.py").write_text("foo = 99\n", encoding="utf-8")
    (tmp_path / "src" / "bar.py").unlink()

    outcome = refresh_plan(plan_path, tmp_path)

    assert len(calls) == 1
    drifted = set(calls[0]["drifted"])
    assert drifted == {
        (tmp_path / "src" / "foo.py").resolve(),
        (tmp_path / "src" / "bar.py").resolve(),
    }
    assert set(outcome.drifted_files) == drifted


def test_malformed_plan_propagates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan_path = tmp_path / "docs" / "plans" / "2-bad.md"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text("---\nnot: valid: yaml: here\n", encoding="utf-8")

    with pytest.raises(ParseError):
        refresh_plan(plan_path, tmp_path)


# --- drift-gate decision telemetry ----------------------------------------


def _drift_gate_events(tmp_path: Path):
    from plan_tool.telemetry import DRIFT_GATE_KIND, read_decisions

    return [e for e in read_decisions(tmp_path) if e.kind == DRIFT_GATE_KIND]


def test_no_drift_records_drift_gate_decision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan_path = _seed_plan(tmp_path)
    _ground(tmp_path, plan_path)

    refresh_plan(plan_path, tmp_path)

    (event,) = _drift_gate_events(tmp_path)
    assert event.context == {"verdict": "no-drift", "drifted_files": 0, "findings": 0}
    assert event.code_fingerprint != {}  # code_fp carried even on the hot path
    assert event.plan_fingerprint == ""  # plan-file read skipped on no-drift


def test_no_baseline_records_drift_gate_decision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan_path = _seed_plan(tmp_path)  # no grounding written
    _spy_reconcile(monkeypatch)

    refresh_plan(plan_path, tmp_path)

    (event,) = _drift_gate_events(tmp_path)
    assert event.context["verdict"] == "no-baseline"


def test_drift_records_drift_gate_decision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan_path = _seed_plan(tmp_path)
    _ground(tmp_path, plan_path)
    _spy_reconcile(monkeypatch, returns=3)

    (tmp_path / "src" / "foo.py").write_text("foo = 99\n", encoding="utf-8")
    outcome = refresh_plan(plan_path, tmp_path)

    (event,) = _drift_gate_events(tmp_path)
    assert event.context["verdict"] == "drifted"
    assert event.context["drifted_files"] == len(outcome.drifted_files)
    assert event.context["findings"] == 3
    assert event.plan_fingerprint != ""  # computed on the drifted verdict


def test_drift_gate_record_is_best_effort(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan_path = _seed_plan(tmp_path)
    _ground(tmp_path, plan_path)

    def _boom(*a, **k):
        raise RuntimeError("telemetry blew up")

    monkeypatch.setattr("plan_tool.refresh.record_drift_gate", _boom)

    # A raising recorder must not change the outcome or propagate.
    outcome = refresh_plan(plan_path, tmp_path)
    assert outcome == RefreshOutcome(plan_slug="demo")
