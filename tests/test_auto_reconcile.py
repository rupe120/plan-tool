"""Tests for plan_tool.auto_reconcile.

Drives :func:`run_auto_reconcile_on_drift` through its ``file=`` seam and
stubs the lazily-imported ``launcher`` / ``review`` /
``review_persistence`` callables so each ``plan-tool:`` diagnostic head
can be asserted without a real claude shell-out. The iteration entry
points' wiring (cmd_completeness, _iterate_reconcile_loop, create_plan,
generate_detail) is covered by sibling integration tests in
``test_cli.py`` / ``test_create.py`` / ``test_detail.py``.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from plan_tool import style
from plan_tool.auto_reconcile import run_auto_reconcile_on_drift
from plan_tool.review import Recommendation


def _rec(rec_id: str = "r1") -> Recommendation:
    """A minimal non-directive reconcile recommendation. Non-``granularity-merge``
    source → the stamp pass's ``directive_target_ids`` returns None (no-op), so it
    stands in for a real rec wherever a stamped save path iterates the list."""
    return Recommendation(
        id=rec_id, source="reconcile", severity="info",
        step_id=1, title="t", body="b",
    )


class _FakeResult:
    """Stand-in for launcher.run_step's return value."""

    def __init__(self, *, exit_code: int = 0, stdout: str = "report") -> None:
        self.exit_code = exit_code
        self.stdout = stdout


class TestAutoReconcileStyleOutput:
    """auto_reconcile.py's ``plan-tool:`` diagnostics route through
    ``style.tool()``. Plain mode stays byte-identical to the legacy
    ``print(f"plan-tool: ...")`` strings; under ``PLAN_TOOL_FORCE_COLOR``
    only the ``plan-tool:`` tag carries ANSI.
    """

    def _mapped(self, tmp_path: Path) -> tuple[Path, dict, Path]:
        """Return (drifted_path, file_to_step, plan_path) for a single
        drifted file owned by step 1."""
        src = tmp_path / "src.py"
        src.write_text("changed\n", encoding="utf-8")
        file_to_step = {src.resolve(): (1, "the title")}
        plan_path = tmp_path / "plans" / "2-foo.md"
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text("# plan\n", encoding="utf-8")
        return src, file_to_step, plan_path

    def _stub_run_loop(
        self,
        monkeypatch: pytest.MonkeyPatch,
        *,
        run_step,
        recs=None,
        save_review=None,
    ) -> None:
        import plan_tool.launcher as launcher
        import plan_tool.review as review
        import plan_tool.review_persistence as review_persistence

        monkeypatch.setattr(launcher, "run_step", run_step)
        monkeypatch.setattr(
            review,
            "extract_reconcile_recommendations",
            lambda *a, **k: (recs if recs is not None else ["r1"]),
        )
        if save_review is not None:
            monkeypatch.setattr(
                review_persistence, "save_review", save_review
            )

    def test_skip_no_mapped_files_plain(self, tmp_path: Path) -> None:
        buf = io.StringIO()
        total = run_auto_reconcile_on_drift(
            drifted=[Path("x.py")],
            file_to_step={},
            plan_path=tmp_path / "plans" / "2-foo.md",
            plan_slug="foo",
            repo_root=tmp_path,
            file=buf,
        )
        assert total == 0
        assert buf.getvalue() == (
            "plan-tool: auto-reconcile skipped: no drifted file maps "
            "to a plan step (run `plan-tool detail <slug> --reconcile "
            "--step N` manually to investigate)\n"
        )

    def test_running_banner_plain(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        src, file_to_step, plan_path = self._mapped(tmp_path)
        self._stub_run_loop(
            monkeypatch,
            run_step=lambda *a, **k: _FakeResult(),
            save_review=lambda *a, **k: tmp_path / "review.json",
        )
        buf = io.StringIO()
        run_auto_reconcile_on_drift(
            drifted=[src],
            file_to_step=file_to_step,
            plan_path=plan_path,
            plan_slug="foo",
            repo_root=tmp_path,
            file=buf,
        )
        assert (
            "plan-tool: running auto-reconcile on 1 affected "
            "step(s) to surface what the drift means for the plan "
            "(Lesson 13: audit > observe)...\n"
        ) in buf.getvalue()

    def test_launcher_error_plain(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.launcher import LauncherError

        src, file_to_step, plan_path = self._mapped(tmp_path)

        def _boom(*a, **k):
            raise LauncherError("kaboom")

        self._stub_run_loop(monkeypatch, run_step=_boom)
        buf = io.StringIO()
        run_auto_reconcile_on_drift(
            drifted=[src],
            file_to_step=file_to_step,
            plan_path=plan_path,
            plan_slug="foo",
            repo_root=tmp_path,
            file=buf,
        )
        assert (
            "plan-tool: auto-reconcile on step 1: launcher error "
            "(kaboom); skipping"
        ) in buf.getvalue()

    def test_auto_reconcile_reraises_a_detail_format_caused_launcher_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A ``LauncherError`` whose cause chain contains a
        ``DetailFormatError`` (``run_step`` wrapping the renderer's
        ``DetailGradeError``, itself wrapping the original refusal) must
        escape the per-step loop rather than being logged and skipped —
        unlike the ordinary ``LauncherError`` case above."""
        from plan_tool.detail_artifacts import DetailFormatError
        from plan_tool.launcher import LauncherError

        src, file_to_step, plan_path = self._mapped(tmp_path)

        def _boom(*a, **k):
            try:
                raise DetailFormatError("detail declares an unsupported version")
            except DetailFormatError as exc:
                raise LauncherError(str(exc)) from exc

        self._stub_run_loop(monkeypatch, run_step=_boom)
        buf = io.StringIO()
        with pytest.raises(LauncherError):
            run_auto_reconcile_on_drift(
                drifted=[src],
                file_to_step=file_to_step,
                plan_path=plan_path,
                plan_slug="foo",
                repo_root=tmp_path,
                file=buf,
            )
        assert "skipping" not in buf.getvalue()

    def test_claude_nonzero_plain(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        src, file_to_step, plan_path = self._mapped(tmp_path)
        self._stub_run_loop(
            monkeypatch, run_step=lambda *a, **k: _FakeResult(exit_code=1)
        )
        buf = io.StringIO()
        run_auto_reconcile_on_drift(
            drifted=[src],
            file_to_step=file_to_step,
            plan_path=plan_path,
            plan_slug="foo",
            repo_root=tmp_path,
            file=buf,
        )
        assert (
            'plan-tool: auto-reconcile on step 1 ("the title"): '
            "claude exited 1; skipping"
        ) in buf.getvalue()

    def test_save_failed_plain(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        src, file_to_step, plan_path = self._mapped(tmp_path)

        def _raise_oserror(*a, **k):
            raise OSError("disk full")

        self._stub_run_loop(
            monkeypatch,
            run_step=lambda *a, **k: _FakeResult(),
            recs=["r1", "r2"],
            save_review=_raise_oserror,
        )
        buf = io.StringIO()
        total = run_auto_reconcile_on_drift(
            drifted=[src],
            file_to_step=file_to_step,
            plan_path=plan_path,
            plan_slug="foo",
            repo_root=tmp_path,
            file=buf,
        )
        assert total == 2
        assert (
            "2 finding(s) raised but save failed (disk full); see "
            "claude stdout above"
        ) in buf.getvalue()

    def test_save_succeeded_plain(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        src, file_to_step, plan_path = self._mapped(tmp_path)
        saved = tmp_path / "review.json"
        self._stub_run_loop(
            monkeypatch,
            run_step=lambda *a, **k: _FakeResult(),
            recs=["r1"],
            save_review=lambda *a, **k: saved,
        )
        buf = io.StringIO()
        run_auto_reconcile_on_drift(
            drifted=[src],
            file_to_step=file_to_step,
            plan_path=plan_path,
            plan_slug="foo",
            repo_root=tmp_path,
            file=buf,
        )
        out = buf.getvalue()
        assert f"1 finding(s) raised (saved to {saved})" in out
        assert (
            "plan-tool: walk findings interactively with "
            "`plan-tool reconcile-plan-walk foo`\n"
        ) in out

    def test_unmapped_note_plain(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        src, file_to_step, plan_path = self._mapped(tmp_path)
        unmapped = tmp_path / "orphan.py"
        unmapped.write_text("x\n", encoding="utf-8")
        self._stub_run_loop(
            monkeypatch,
            run_step=lambda *a, **k: _FakeResult(),
            save_review=lambda *a, **k: tmp_path / "review.json",
        )
        buf = io.StringIO()
        run_auto_reconcile_on_drift(
            drifted=[src, unmapped],
            file_to_step=file_to_step,
            plan_path=plan_path,
            plan_slug="foo",
            repo_root=tmp_path,
            file=buf,
        )
        assert (
            "plan-tool: auto-reconcile skipped 1 drifted file(s) "
            "outside any step.files declaration\n"
        ) in buf.getvalue()

    def test_skip_line_color_prefix_only(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PLAN_TOOL_FORCE_COLOR", "1")
        buf = io.StringIO()
        run_auto_reconcile_on_drift(
            drifted=[Path("x.py")],
            file_to_step={},
            plan_path=tmp_path / "plans" / "2-foo.md",
            plan_slug="foo",
            repo_root=tmp_path,
            file=buf,
        )
        out = buf.getvalue()
        assert out.startswith(style.DIM + "plan-tool:" + style.RESET + " ")
        assert "auto-reconcile skipped: no drifted file maps" in out


_VALID_PLAN = """---
title: Auto Reconcile Plan
status: in-progress
priority: medium
steps:
  - id: 1
    title: Build the widget
    files:
      - src.py
    status: pending
---

# Auto Reconcile Plan
"""


class TestAutoReconcileFingerprints:
    """The auto-reconcile save captures both staleness axes, and a plan
    parse failure falls back to ``code_fingerprint=None`` without poisoning
    the drift halt."""

    def _spy_save_review(self, monkeypatch: pytest.MonkeyPatch, captured: dict):
        import plan_tool.launcher as launcher
        import plan_tool.review as review
        import plan_tool.review_persistence as review_persistence

        monkeypatch.setattr(
            launcher, "run_step", lambda *a, **k: _FakeResult()
        )
        monkeypatch.setattr(
            review,
            "extract_reconcile_recommendations",
            lambda *a, **k: [_rec("r1")],
        )

        def _spy(*a, **k):
            captured.update(k)
            return Path("review.json")

        monkeypatch.setattr(review_persistence, "save_review", _spy)

    def test_auto_reconcile_save_includes_fingerprints(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan_path = tmp_path / "1-auto.md"
        plan_path.write_text(_VALID_PLAN, encoding="utf-8")
        src = tmp_path / "src.py"
        src.write_text("def widget():\n    return 1\n", encoding="utf-8")
        file_to_step = {src.resolve(): (1, "Build the widget")}

        captured: dict = {}
        self._spy_save_review(monkeypatch, captured)
        run_auto_reconcile_on_drift(
            drifted=[src],
            file_to_step=file_to_step,
            plan_path=plan_path,
            plan_slug="auto",
            repo_root=tmp_path,
            file=io.StringIO(),
        )
        assert isinstance(captured["plan_fingerprint"], str)
        assert captured["plan_fingerprint"] != ""
        assert isinstance(captured["code_fingerprint"], dict)
        assert "src.py" in captured["code_fingerprint"]

    def test_auto_reconcile_parse_failure_falls_back(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # An invalid plan (no frontmatter) makes ``parse_plan`` raise, so the
        # save still fires with ``code_fingerprint=None`` (drift halt intact).
        plan_path = tmp_path / "1-auto.md"
        plan_path.write_text("# not a plan\n", encoding="utf-8")
        src = tmp_path / "src.py"
        src.write_text("x\n", encoding="utf-8")
        file_to_step = {src.resolve(): (1, "Build the widget")}

        captured: dict = {}
        self._spy_save_review(monkeypatch, captured)
        run_auto_reconcile_on_drift(
            drifted=[src],
            file_to_step=file_to_step,
            plan_path=plan_path,
            plan_slug="auto",
            repo_root=tmp_path,
            file=io.StringIO(),
        )
        assert captured["plan_fingerprint"] == ""
        assert captured["code_fingerprint"] is None
