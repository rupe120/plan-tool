"""Characterization tests for the reconcile reuse engine + drift/scope seams.

These pin the *current* behavior of the saved-reconcile reuse machinery in
``plan_tool.cli`` — the lookup/ask/prompt/walk helpers for both reconcile
families — plus the drift-halt and scope-guard plan emitters, so
the upcoming "split cli.py into an intent-grouped package" refactor can
relocate them between submodules without silently changing their wording or
exit codes.

This module is the **single-source home for the byte-exact reuse-prompt
wording** of both saved-reconcile families:

- *detail-reconcile* — the ``detail --reconcile`` save,
  ``*-detail-reconcile.json``;
- *run-reconcile* — the ``run --reconcile`` code-side audit save,
  ``*-run-reconcile.json``.

The step-20 dedup gate of the cli-package-split plan requires those wording
pins to live in one place, so they are written here regardless of whether
``test_review_walk.py`` / ``test_cli.py`` also exercise the same helpers
indirectly.

Split-proof conventions (see ``test_package_surface.py``): every symbol
under test is imported from ``plan_tool.cli`` (the package entry point) and
driven with explicit arguments — an injected ``input_fn``, an
``argparse.Namespace`` of flags, a directly-constructed
``PlanToolContext`` / ``SavedReview`` / ``ScopeGuardBuffer`` — never a
``monkeypatch.setattr`` on a ``plan_tool.cli`` module global. Saved fixtures
land on disk through ``review_persistence.save_review`` (the domain
producer), so the lookups exercise the real reports-directory scan. The
``repo`` fixture hands back a *resolved* root so the repo-relative path
tokens in the wording pins are deterministic across platforms (macOS routes
its temp dir through a ``/private`` symlink).

Inventory pointers (``COVERAGE_BASELINE.md``) — already DIRECTLY covered, so
referenced here instead of duplicated:

- ``_print_attributed_files``     → ``tests/test_cli.py`` (imported + called)
- ``_run_auto_reconcile_on_drift`` → ``tests/test_auto_reconcile.py`` /
  ``tests/test_cli.py``
- ``_format_relative_age``        → ``tests/cli/test_console_helpers.py``
  (``TestFormatRelativeAge``)
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import pytest

from plan_tool.cli import (
    ReusableReconcile,
    _ask_reuse_saved_detail_reconcile,
    _ask_reuse_saved_run_reconcile,
    _emit_drift_halt_warning,
    _emit_scope_guard_plan,
    _find_saved_detail_reconcile_for_step,
    _find_saved_run_reconcile_for_step,
    _prompt_reuse_saved_detail_reconcile,
    _prompt_reuse_saved_run_reconcile,
    _save_and_walk_reconcile,
    _save_and_walk_run_reconcile,
    _walk_saved_detail_reconcile,
    _walk_saved_run_reconcile,
    resolve_reusable_reconcile,
)
from plan_tool.fingerprint import compute_code_fingerprint
from plan_tool.locator import PlanToolContext
from plan_tool.parser import parse_plan
from plan_tool.review import Recommendation, Redirect
from plan_tool.review_persistence import (
    SavedReview,
    compute_plan_fingerprint,
    load_review,
    save_review,
)
from plan_tool.run_log import RunLogWriter

# A far-future ``created_at`` makes ``_format_relative_age`` bail to the raw
# ISO string (its ``secs < 0`` guard), so every age token in the wording
# pins below is deterministic rather than wall-clock-dependent.
FUTURE_TS = "2999-01-01T00:00:00Z"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A resolved repo root — keeps repo-relative path tokens stable."""
    return tmp_path.resolve()


def _ctx(repo_root: Path) -> PlanToolContext:
    """Minimal context — the helpers under test only read ``repo_root``."""
    return PlanToolContext(repo_root=repo_root, plans_dir=None, entries=[])


def _rec(step_id: int, kind: str, idx: int = 0) -> Recommendation:
    return Recommendation(
        id=f"step{step_id}-{kind}-{idx}",
        source=kind,
        severity="critical",
        step_id=step_id,
        title="acceptance criteria unmet",
        body="the step's declared work is not all present on disk",
    )


def _saved_in_memory(
    *,
    step_id: int,
    kind: str,
    saved_path: Path,
    n_recs: int = 1,
    n_annotated: int = 0,
    created_at: str = FUTURE_TS,
    plan_slug: str = "demo",
) -> SavedReview:
    """A ``SavedReview`` built directly for the ``_ask_*`` wording pins.

    The ``_ask_*`` helpers only read ``len(recommendations)``,
    ``len(annotations)``, ``created_at`` and ``step_id``, so the
    annotations map just needs the right cardinality.
    """
    return SavedReview(
        plan_slug=plan_slug,
        plan_path="demo.md",
        created_at=created_at,
        report_md="prior audit",
        recommendations=[_rec(step_id, kind, i) for i in range(n_recs)],
        annotations={f"r{i}": None for i in range(n_annotated)},  # len() only
        kind=kind,
        step_id=step_id,
        path=saved_path,
    )


def _seed_save(
    repo_root: Path,
    *,
    kind: str,
    step_id: int,
    now: datetime,
    n_recs: int = 1,
    plan_slug: str = "demo",
) -> Path:
    """Persist a saved review of ``kind`` to the canonical reports dir."""
    return save_review(
        plan_slug=plan_slug,
        plan_path="demo.md",
        repo_root=repo_root,
        report_md="prior audit",
        recommendations=[_rec(step_id, kind, i) for i in range(n_recs)],
        kind=kind,
        step_id=step_id,
        now=now,
    )


def _plan_path(repo_root: Path) -> Path:
    # Same plan_path string ("demo.md") the saves were written under,
    # resolved against the repo root — so the lookups scan the same dir.
    return repo_root / "demo.md"


# --------------------------------------------------------------------------
# _find_saved_*_for_step — kind isolation + step matching
# --------------------------------------------------------------------------


class TestFindSavedReconcileFamilies:
    """The two lookups stay scoped to their own save kind so a
    detail-reconcile save is never offered for replay against a run-reconcile
    audit (and vice versa), and a save for one step never matches another."""

    def _seed_both(self, repo_root: Path, *, step_id: int) -> dict:
        return {
            "detail-reconcile": _seed_save(
                repo_root, kind="detail-reconcile", step_id=step_id,
                now=datetime(2026, 1, 1, 0, 0, 0),
            ),
            "run-reconcile": _seed_save(
                repo_root, kind="run-reconcile", step_id=step_id,
                now=datetime(2026, 1, 1, 0, 0, 0),
            ),
        }

    def test_each_lookup_matches_only_its_own_kind(self, repo: Path) -> None:
        seeded = self._seed_both(repo, step_id=1)
        plan_path = _plan_path(repo)

        detail = _find_saved_detail_reconcile_for_step(
            "demo", repo, step_id=1, plan_path=plan_path
        )
        run = _find_saved_run_reconcile_for_step(
            "demo", repo, step_id=1, plan_path=plan_path
        )

        assert detail is not None and detail[0] == seeded["detail-reconcile"]
        assert run is not None and run[0] == seeded["run-reconcile"]

    def test_step_mismatch_returns_none(self, repo: Path) -> None:
        self._seed_both(repo, step_id=1)
        plan_path = _plan_path(repo)
        assert (
            _find_saved_detail_reconcile_for_step(
                "demo", repo, step_id=2, plan_path=plan_path
            )
            is None
        )
        assert (
            _find_saved_run_reconcile_for_step(
                "demo", repo, step_id=2, plan_path=plan_path
            )
            is None
        )

    def test_no_saves_returns_none(self, repo: Path) -> None:
        plan_path = _plan_path(repo)
        assert (
            _find_saved_detail_reconcile_for_step(
                "demo", repo, step_id=1, plan_path=plan_path
            )
            is None
        )
        assert (
            _find_saved_run_reconcile_for_step(
                "demo", repo, step_id=1, plan_path=plan_path
            )
            is None
        )


# --------------------------------------------------------------------------
# _ask_reuse_saved_* — byte-exact metadata + prompt wording, answer matrix
# --------------------------------------------------------------------------


class _Recorder:
    """Captures the prompt string and returns a scripted answer."""

    def __init__(self, answer: str) -> None:
        self.answer = answer
        self.prompts: list[str] = []

    def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.answer


class TestAskReuseWordingDetailReconcile:
    QUESTION = (
        "Walk that one instead of running a fresh detail-reconcile? [y/N] "
    )

    def test_metadata_and_prompt_are_byte_exact(
        self, repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        saved_path = repo / "20260101-000000-detail-reconcile.json"
        saved = _saved_in_memory(
            step_id=4, kind="detail-reconcile", saved_path=saved_path,
            n_recs=1, n_annotated=0,
        )
        rec = _Recorder("yes")

        result = _ask_reuse_saved_detail_reconcile(
            saved_path, saved, "demo", repo_root=repo, input_fn=rec,
        )

        assert result is True
        assert rec.prompts == [self.QUESTION]
        assert capsys.readouterr().out == (
            "\nA saved detail-reconcile for 'demo' step 4 exists "
            f"({FUTURE_TS}, 1 rec(s), 0 annotated):\n"
            "  20260101-000000-detail-reconcile.json\n"
        )

    def test_blank_declines(self, repo: Path) -> None:
        saved_path = repo / "s.json"
        saved = _saved_in_memory(
            step_id=4, kind="detail-reconcile", saved_path=saved_path
        )
        assert (
            _ask_reuse_saved_detail_reconcile(
                saved_path, saved, "demo",
                repo_root=repo, input_fn=_Recorder(""),
            )
            is False
        )


class TestAskReuseWordingRunReconcile:
    QUESTION = (
        "Walk that one instead of running a fresh run-reconcile? [y/N] "
    )

    def test_metadata_and_prompt_are_byte_exact(
        self, repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        saved_path = repo / "20260101-000000-run-reconcile.json"
        saved = _saved_in_memory(
            step_id=7, kind="run-reconcile", saved_path=saved_path,
            n_recs=3, n_annotated=2,
        )
        rec = _Recorder("y")

        result = _ask_reuse_saved_run_reconcile(
            saved_path, saved, "demo", repo_root=repo, input_fn=rec,
        )

        assert result is True
        assert rec.prompts == [self.QUESTION]
        assert capsys.readouterr().out == (
            "\nA saved run-reconcile for 'demo' step 7 exists "
            f"({FUTURE_TS}, 3 rec(s), 2 annotated):\n"
            "  20260101-000000-run-reconcile.json\n"
        )

    def test_blank_declines(self, repo: Path) -> None:
        saved_path = repo / "s.json"
        saved = _saved_in_memory(
            step_id=7, kind="run-reconcile", saved_path=saved_path
        )
        assert (
            _ask_reuse_saved_run_reconcile(
                saved_path, saved, "demo",
                repo_root=repo, input_fn=_Recorder(""),
            )
            is False
        )


# --------------------------------------------------------------------------
# _prompt_reuse_saved_* — suppression gating + byte-exact --yes wording
# --------------------------------------------------------------------------


def _prompt_args(**overrides) -> argparse.Namespace:
    base = dict(dry_run=False, no_walk=False, no_save=False, yes=False)
    base.update(overrides)
    return argparse.Namespace(**base)


def _seed_fresh_save(
    repo_root: Path, *, kind: str, now: datetime = datetime(2999, 1, 1, 0, 0, 0),
) -> tuple[Path, Path]:
    """Write a fingerprint plan + its in-scope code file, then persist a
    save of ``kind`` carrying both fingerprints computed from current disk.

    Returns ``(saved_path, plan_path)`` so the freshness gate reads the
    located sidecar as fresh against disk. The plan declares step 1
    (``Build the widget``) watching ``widget.py``; ``plan_slug`` is
    ``"fingerprint"`` (the save dir the lookups scan)."""
    plan_path = _write_fingerprint_plan(repo_root)
    saved_path = _seed_reconcile_sidecar(
        repo_root, plan_path, kind=kind, step_id=1, now=now,
    )
    return saved_path, plan_path


class TestPromptReuseDetailReconcile:
    def test_yes_returns_path_with_byte_exact_line(
        self, repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        saved_path, plan_path = _seed_fresh_save(
            repo, kind="detail-reconcile",
        )
        result = _prompt_reuse_saved_detail_reconcile(
            _ctx(repo), "fingerprint", _prompt_args(yes=True),
            step_id=1, plan_path=plan_path,
        )
        assert result == saved_path
        rel = saved_path.relative_to(repo).as_posix()
        assert capsys.readouterr().out == (
            f"\n(--yes) walking saved detail-reconcile for 'fingerprint' "
            f"step 1 ({FUTURE_TS}, 1 rec(s)): {rel}\n"
        )

    def test_dry_run_suppresses_prompt(self, repo: Path) -> None:
        _, plan_path = _seed_fresh_save(repo, kind="detail-reconcile")
        result = _prompt_reuse_saved_detail_reconcile(
            _ctx(repo), "fingerprint", _prompt_args(yes=True, dry_run=True),
            step_id=1, plan_path=plan_path,
        )
        assert result is None

    def test_non_tty_without_yes_stale_save_suppresses(
        self, repo: Path
    ) -> None:
        # Non-TTY + unset default auto-accepts a FRESH save, so drift the
        # watched code file to make the located save stale — the freshness
        # gate then declines to a fresh audit (returns None).
        _, plan_path = _seed_fresh_save(repo, kind="detail-reconcile")
        (repo / "widget.py").write_text(
            "def widget():\n    return 999\n", encoding="utf-8"
        )
        result = _prompt_reuse_saved_detail_reconcile(
            _ctx(repo), "fingerprint", _prompt_args(yes=False),
            step_id=1, plan_path=plan_path,
        )
        assert result is None

    def test_non_tty_without_yes_fresh_save_auto_accepts(
        self, repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Unset default (no --yes) on non-TTY stdin auto-accepts a fresh save.
        saved_path, plan_path = _seed_fresh_save(repo, kind="detail-reconcile")
        result = _prompt_reuse_saved_detail_reconcile(
            _ctx(repo), "fingerprint", _prompt_args(yes=False),
            step_id=1, plan_path=plan_path,
        )
        assert result == saved_path
        assert "(reuse) walking saved detail-reconcile" in capsys.readouterr().out


class TestPromptReuseRunReconcile:
    def test_yes_returns_path_with_byte_exact_line(
        self, repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        saved_path, plan_path = _seed_fresh_save(
            repo, kind="run-reconcile",
        )
        result = _prompt_reuse_saved_run_reconcile(
            _ctx(repo), "fingerprint", _prompt_args(yes=True),
            step_id=1, plan_path=plan_path,
        )
        assert result == saved_path
        rel = saved_path.relative_to(repo).as_posix()
        assert capsys.readouterr().out == (
            f"\n(--yes) walking saved run-reconcile for 'fingerprint' "
            f"step 1 ({FUTURE_TS}, 1 rec(s)): {rel}\n"
        )

    @pytest.mark.parametrize("flag", ["dry_run", "no_walk", "no_save"])
    def test_flag_suppresses_prompt(self, repo: Path, flag: str) -> None:
        _, plan_path = _seed_fresh_save(repo, kind="run-reconcile")
        result = _prompt_reuse_saved_run_reconcile(
            _ctx(repo), "fingerprint", _prompt_args(yes=True, **{flag: True}),
            step_id=1, plan_path=plan_path,
        )
        assert result is None

    def test_non_tty_without_yes_stale_save_suppresses(
        self, repo: Path
    ) -> None:
        # Non-TTY + unset default auto-accepts a FRESH save, so drift the
        # watched code file to make the located save stale — the freshness
        # gate then declines to a fresh audit (returns None).
        _, plan_path = _seed_fresh_save(repo, kind="run-reconcile")
        (repo / "widget.py").write_text(
            "def widget():\n    return 999\n", encoding="utf-8"
        )
        result = _prompt_reuse_saved_run_reconcile(
            _ctx(repo), "fingerprint", _prompt_args(yes=False),
            step_id=1, plan_path=plan_path,
        )
        assert result is None

    def test_non_tty_without_yes_fresh_save_auto_accepts(
        self, repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Unset default (no --yes) on non-TTY stdin auto-accepts a fresh save.
        saved_path, plan_path = _seed_fresh_save(repo, kind="run-reconcile")
        result = _prompt_reuse_saved_run_reconcile(
            _ctx(repo), "fingerprint", _prompt_args(yes=False),
            step_id=1, plan_path=plan_path,
        )
        assert result == saved_path
        assert "(reuse) walking saved run-reconcile" in capsys.readouterr().out


# --------------------------------------------------------------------------
# _prompt_reuse_saved — fingerprint-freshness gate (fresh / stale / legacy)
# --------------------------------------------------------------------------


class TestPromptReuseFreshnessGate:
    """A located save is offered for reuse only when both fingerprints
    still match disk; any staleness declines to a fresh audit (returns
    ``None``) without raising or exiting non-zero."""

    def test_stale_code_declines_with_attributed_info(
        self, repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        saved_path, plan_path = _seed_fresh_save(repo, kind="detail-reconcile")
        # Edit a watched (step.files) code file after the save → code drift.
        (repo / "widget.py").write_text(
            "def widget():\n    return 999\n", encoding="utf-8"
        )
        result = _prompt_reuse_saved_detail_reconcile(
            _ctx(repo), "fingerprint", _prompt_args(yes=True),
            step_id=1, plan_path=plan_path,
        )
        assert result is None
        err = capsys.readouterr().err
        # Grouped under the owning step (title once in the header), at info
        # level — a detected code change re-running the audit is normal.
        assert "info:" in err
        assert "step 1: Build the widget" in err
        assert "widget.py" in err
        assert "widget.py (step 1:" not in err  # not the inline form
        assert "plan-tool detail" in err and "--reconcile" in err

    def test_stale_plan_declines_with_oneline_note(
        self, repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        saved_path, plan_path = _seed_fresh_save(repo, kind="detail-reconcile")
        # Append prose to the plan → plan fingerprint flips, code untouched.
        with plan_path.open("a", encoding="utf-8") as fh:
            fh.write("\nextra prose\n")
        result = _prompt_reuse_saved_detail_reconcile(
            _ctx(repo), "fingerprint", _prompt_args(yes=True),
            step_id=1, plan_path=plan_path,
        )
        assert result is None
        err = capsys.readouterr().err
        assert "plan changed since" in err
        # Plan-only drift names no per-file attributed list.
        assert "widget.py (step 1:" not in err

    def test_legacy_save_without_fingerprints_declines(
        self, repo: Path
    ) -> None:
        plan_path = _write_fingerprint_plan(repo)
        # Legacy capture: no fingerprints (code_fingerprint_present=False).
        _seed_reconcile_sidecar(
            repo, plan_path, kind="detail-reconcile", step_id=1,
            now=datetime(2999, 1, 1), present=False,
        )
        result = _prompt_reuse_saved_detail_reconcile(
            _ctx(repo), "fingerprint", _prompt_args(yes=True),
            step_id=1, plan_path=plan_path,
        )
        assert result is None

    def test_fresh_save_offers_via_prompt(
        self, repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import sys

        monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
        saved_path, plan_path = _seed_fresh_save(repo, kind="detail-reconcile")
        # Fresh + interactive: "y" accepts, "" declines.
        accept = _prompt_reuse_saved_detail_reconcile(
            _ctx(repo), "fingerprint",
            _prompt_args(yes=False), step_id=1, plan_path=plan_path,
            input_fn=lambda _prompt: "y",
        )
        assert accept == saved_path
        decline = _prompt_reuse_saved_detail_reconcile(
            _ctx(repo), "fingerprint",
            _prompt_args(yes=False), step_id=1, plan_path=plan_path,
            input_fn=lambda _prompt: "",
        )
        assert decline is None

    def test_parse_failure_declines_not_raises(self, repo: Path) -> None:
        saved_path, plan_path = _seed_fresh_save(repo, kind="detail-reconcile")
        # Corrupt the plan after the save so the gate's verdict recompute
        # hits a parse failure — best-effort posture declines, never raises.
        plan_path.write_text("not a valid plan\n", encoding="utf-8")
        result = _prompt_reuse_saved_detail_reconcile(
            _ctx(repo), "fingerprint", _prompt_args(yes=True),
            step_id=1, plan_path=plan_path,
        )
        assert result is None

    def test_both_wrappers_share_the_gate(
        self, repo: Path
    ) -> None:
        # Seed a fresh save of EACH kind, then drift the shared code file so
        # both wrappers' gate verdicts go stale. Both must decline — the gate
        # lives in the shared core, not the wrappers.
        plan_path = _write_fingerprint_plan(repo)
        _seed_reconcile_sidecar(
            repo, plan_path, kind="detail-reconcile", step_id=1,
            now=datetime(2999, 1, 1),
        )
        _seed_reconcile_sidecar(
            repo, plan_path, kind="run-reconcile", step_id=1,
            now=datetime(2999, 1, 1),
        )
        (repo / "widget.py").write_text(
            "def widget():\n    return 999\n", encoding="utf-8"
        )
        assert _prompt_reuse_saved_detail_reconcile(
            _ctx(repo), "fingerprint", _prompt_args(yes=True),
            step_id=1, plan_path=plan_path,
        ) is None
        assert _prompt_reuse_saved_run_reconcile(
            _ctx(repo), "fingerprint", _prompt_args(yes=True),
            step_id=1, plan_path=plan_path,
        ) is None


# --------------------------------------------------------------------------
# _walk_saved_* — exit codes for the deterministic load / empty / replay paths
# --------------------------------------------------------------------------


def _run_logger(repo_root: Path) -> RunLogWriter:
    return RunLogWriter.start(
        repo_root=repo_root, slug="demo", command="test", argv=[],
    )


class TestWalkSavedDetailReconcileExitCodes:
    def test_load_error_returns_1(
        self, repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        bad = repo / "broken.json"
        bad.write_text("{bad", encoding="utf-8")
        rc = _walk_saved_detail_reconcile(
            ctx=_ctx(repo), path=_plan_path(repo), plan_name="demo",
            reuse_path=bad, yes=False, run_logger=_run_logger(repo),
        )
        assert rc == 1
        assert (
            "error loading saved detail-reconcile" in capsys.readouterr().err
        )

    def test_empty_recommendations_returns_0(
        self, repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        saved = _seed_save(
            repo, kind="detail-reconcile", step_id=1,
            now=datetime(2026, 1, 1), n_recs=0,
        )
        rc = _walk_saved_detail_reconcile(
            ctx=_ctx(repo), path=_plan_path(repo), plan_name="demo",
            reuse_path=saved, yes=False, run_logger=_run_logger(repo),
        )
        assert rc == 0
        assert (
            "(saved detail-reconcile has no recommendations to walk)"
            in capsys.readouterr().out
        )


class TestWalkSavedRunReconcileExitCodes:
    def test_load_error_returns_1(
        self, repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        bad = repo / "broken.json"
        bad.write_text("nope", encoding="utf-8")
        rc = _walk_saved_run_reconcile(
            ctx=_ctx(repo), path=_plan_path(repo), plan_name="demo",
            reuse_path=bad, yes=False, run_logger=_run_logger(repo),
        )
        assert rc == 1
        assert "error loading saved run-reconcile" in capsys.readouterr().err

    def test_empty_recommendations_returns_0(
        self, repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        saved = _seed_save(
            repo, kind="run-reconcile", step_id=1,
            now=datetime(2026, 1, 1), n_recs=0,
        )
        rc = _walk_saved_run_reconcile(
            ctx=_ctx(repo), path=_plan_path(repo), plan_name="demo",
            reuse_path=saved, yes=False, run_logger=_run_logger(repo),
        )
        assert rc == 0
        assert (
            "(saved run-reconcile has no recommendations)"
            in capsys.readouterr().out
        )

    def test_recommendations_without_redirect_replay_to_0(
        self, repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # No finding carries a redirect, so replay surfaces no [REDIRECT]
        # lines and returns 0 without entering an interactive walk.
        saved = _seed_save(
            repo, kind="run-reconcile", step_id=2,
            now=datetime(2026, 1, 1), n_recs=2,
        )
        rc = _walk_saved_run_reconcile(
            ctx=_ctx(repo), path=_plan_path(repo), plan_name="demo",
            reuse_path=saved, yes=False, run_logger=_run_logger(repo),
        )
        assert rc == 0
        out = capsys.readouterr()
        assert "Replaying saved run-reconcile" in out.out
        assert "[REDIRECT]" not in out.err

    def test_redirect_replay_renders_stored_confidence(
        self, repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rec = Recommendation(
            id="step2-run-reconcile-1",
            source="run-reconcile",
            severity="medium",
            step_id=2,
            title="Follow up elsewhere",
            body="This work belongs in a follow-up plan.",
            confidence=None,
            redirect=Redirect(reason="follow-up owns this work", suggested_next=""),
        )
        saved = save_review(
            plan_slug="demo",
            plan_path="demo.md",
            repo_root=repo,
            report_md="prior audit",
            recommendations=[rec],
            kind="run-reconcile",
            step_id=2,
            now=datetime(2026, 1, 1),
        )

        assert _walk_saved_run_reconcile(
            ctx=_ctx(repo), path=_plan_path(repo), plan_name="demo",
            reuse_path=saved, yes=False, run_logger=_run_logger(repo),
        ) == 0
        assert "[confidence: unknown]" in capsys.readouterr().err


# --------------------------------------------------------------------------
# _emit_drift_halt_warning — before/during phrasing + step attribution
# --------------------------------------------------------------------------


class TestEmitDriftHaltWarning:
    def test_before_phase_phrasing(
        self, repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _emit_drift_halt_warning(
            [repo / "src" / "a.py"],
            phase="before", finding_id="step1-x",
            ctx_repo_root=repo,
        )
        err = capsys.readouterr().err
        assert "BEFORE applying finding step1-x" in err
        assert "No edits made this round." in err
        assert "src/a.py" in err

    def test_during_phase_phrasing(
        self, repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _emit_drift_halt_warning(
            [repo / "src" / "a.py"],
            phase="during", finding_id="step1-x",
            ctx_repo_root=repo,
        )
        err = capsys.readouterr().err
        assert "DURING apply of finding step1-x" in err
        assert "KEPT" in err

    def test_file_to_step_attribution_passthrough(
        self, repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        target = repo / "src" / "a.py"
        _emit_drift_halt_warning(
            [target],
            phase="before", finding_id="step1-x",
            ctx_repo_root=repo,
            file_to_step={target.resolve(): (3, "Wire the cache")},
        )
        assert "src/a.py (step 3: Wire the cache)" in capsys.readouterr().err

    def test_empty_drift_is_noop(
        self, repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _emit_drift_halt_warning(
            [], phase="before", finding_id="step1-x", ctx_repo_root=repo,
        )
        assert capsys.readouterr().err == ""


# --------------------------------------------------------------------------
# _emit_scope_guard_plan — bucketing, id increment, per-scope partitioning
# --------------------------------------------------------------------------


def _scope_record(repo_root: Path, rel: str, *, finding_id: str):
    from plan_tool.scope_guard import OutOfScopeRecord

    return OutOfScopeRecord(
        finding_id=finding_id,
        finding_body="edited a file outside the declared step scope",
        step_id=1,
        out_of_scope_files=[repo_root / rel],
        impact_status="reverted",
    )


class TestEmitScopeGuardPlan:
    def test_empty_buffer_is_noop(
        self, repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from plan_tool.scope_guard import ScopeGuardBuffer

        _emit_scope_guard_plan(
            ScopeGuardBuffer(),
            plan_path=_plan_path(repo), plan_slug="demo", ctx=_ctx(repo),
        )
        assert capsys.readouterr().err == ""
        assert not (repo / "docs").exists()

    def test_project_scope_writes_plan_and_reports(
        self, repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from plan_tool.scope_guard import ScopeGuardBuffer

        buf = ScopeGuardBuffer()
        buf.add(_scope_record(repo, "src/widget.py", finding_id="f1"))

        _emit_scope_guard_plan(
            buf, plan_path=_plan_path(repo), plan_slug="demo", ctx=_ctx(repo),
        )

        written = (
            repo / "docs" / "implementation-plans"
            / "1-out-of-scope-findings-from-demo.md"
        )
        assert written.is_file()
        assert capsys.readouterr().err == (
            "plan-tool: wrote 1 out-of-scope finding(s) (project scope) to "
            "docs/implementation-plans/1-out-of-scope-findings-from-demo.md\n"
        )

    def test_next_id_increments_past_existing_plans(
        self, repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from plan_tool.scope_guard import ScopeGuardBuffer

        plans_dir = repo / "docs" / "implementation-plans"
        plans_dir.mkdir(parents=True)
        (plans_dir / "3-existing.md").write_text("x", encoding="utf-8")

        buf = ScopeGuardBuffer()
        buf.add(_scope_record(repo, "src/widget.py", finding_id="f1"))
        _emit_scope_guard_plan(
            buf, plan_path=_plan_path(repo), plan_slug="demo", ctx=_ctx(repo),
        )

        assert (plans_dir / "4-out-of-scope-findings-from-demo.md").is_file()

    def test_buffer_spanning_scopes_emits_one_plan_per_scope(
        self, repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from plan_tool.scope_guard import ScopeGuardBuffer

        buf = ScopeGuardBuffer()
        buf.add(_scope_record(repo, "src/widget.py", finding_id="proj"))
        buf.add(
            _scope_record(
                repo, ".agents/skills/foo/helper.py", finding_id="skill"
            )
        )

        _emit_scope_guard_plan(
            buf, plan_path=_plan_path(repo), plan_slug="demo", ctx=_ctx(repo),
        )

        project_plan = (
            repo / "docs" / "implementation-plans"
            / "1-out-of-scope-findings-from-demo.md"
        )
        skill_plan = (
            repo / ".agents" / "skills" / "foo" / "implementation-plans"
            / "1-out-of-scope-findings-from-demo.md"
        )
        assert project_plan.is_file()
        assert skill_plan.is_file()
        err = capsys.readouterr().err
        assert "(project scope)" in err
        assert "(skill scope)" in err


# --------------------------------------------------------------------------
# _save_and_walk_* — both staleness axes land on the saved sidecar
# --------------------------------------------------------------------------


def _write_fingerprint_plan(
    repo_root: Path, *, new_entry: bool = False, docs_only: bool = False
) -> Path:
    """Plan whose single step declares an on-disk code file.

    ``new_entry`` adds a ``gadget.py (new)`` entry left *uncreated* so a
    test can land it after a save. ``docs_only`` drops the ``files:`` block
    entirely so the watched code surface is empty (``code_fingerprint={}``).
    """
    plan_path = repo_root / "1-fingerprint.md"
    if docs_only:
        files_block = ""
    else:
        files_block = "    files:\n      - widget.py\n"
        if new_entry:
            files_block += "      - gadget.py (new)\n"
    plan_path.write_text(
        "---\n"
        "title: Fingerprint Plan\n"
        "status: in-progress\n"
        "priority: medium\n"
        "steps:\n"
        "  - id: 1\n"
        "    title: Build the widget\n"
        f"{files_block}"
        "    status: pending\n"
        "---\n\n# Fingerprint Plan\n",
        encoding="utf-8",
    )
    if not docs_only:
        (repo_root / "widget.py").write_text(
            "def widget():\n    return 1\n", encoding="utf-8"
        )
    return plan_path


def _save_args(**overrides) -> argparse.Namespace:
    """Namespace for the save seams; ``no_walk`` keeps the walk off."""
    base = {"name": "fingerprint", "yes": False, "no_save": False, "no_walk": True}
    base.update(overrides)
    return argparse.Namespace(**base)


class TestSaveAndWalkPersistsFingerprints:
    """Each reconcile save seam captures the plan + code staleness axes."""

    def test_save_and_walk_reconcile_persists_fingerprints(
        self, repo: Path
    ) -> None:
        plan_path = _write_fingerprint_plan(repo)
        _save_and_walk_reconcile(
            args=_save_args(),
            ctx=_ctx(repo),
            plan_path=plan_path,
            step_id=1,
            stdout="",
            report="verdict",
        )
        saved = list(
            (repo / "plan-details" / "fingerprint" / "reports").glob(
                "*-detail-reconcile.json"
            )
        )
        assert len(saved) == 1
        loaded = load_review(saved[0])
        assert loaded.plan_fingerprint != ""
        assert loaded.code_fingerprint_present is True
        assert "widget.py" in loaded.code_fingerprint
        assert "1-fingerprint.md" not in loaded.code_fingerprint

    def test_save_and_walk_run_reconcile_persists_fingerprints(
        self, repo: Path
    ) -> None:
        plan_path = _write_fingerprint_plan(repo)
        _save_and_walk_run_reconcile(
            args=_save_args(),
            ctx=_ctx(repo),
            plan_path=plan_path,
            step_id=1,
            stdout="",
            report="verdict",
        )
        saved = list(
            (repo / "plan-details" / "fingerprint" / "reports").glob(
                "*-run-reconcile.json"
            )
        )
        assert len(saved) == 1
        loaded = load_review(saved[0])
        assert loaded.plan_fingerprint != ""
        assert loaded.code_fingerprint_present is True
        assert "widget.py" in loaded.code_fingerprint
        assert "1-fingerprint.md" not in loaded.code_fingerprint


# --------------------------------------------------------------------------
# resolve_reusable_reconcile — fingerprint-gated reuse verdict
# --------------------------------------------------------------------------

_RT0 = datetime(2026, 6, 1, 12, 0, 0)
_RT1 = datetime(2026, 6, 1, 12, 0, 5)
_RT2 = datetime(2026, 6, 1, 12, 0, 9)


def _seed_reconcile_sidecar(
    repo_root: Path,
    plan_path: Path,
    *,
    kind: str,
    step_id: int,
    now: datetime,
    present: bool = True,
    recs: list[Recommendation] | None = None,
    plan_slug: str = "fingerprint",
) -> Path:
    """Persist a reconcile sidecar with fingerprints computed from current
    disk. ``present=False`` writes a legacy/never-computed capture
    (``plan_fingerprint=""``, ``code_fingerprint=None``)."""
    plan = parse_plan(plan_path)
    if present:
        plan_fp = compute_plan_fingerprint(plan_path)
        code_fp: dict[str, str] | None = compute_code_fingerprint(
            plan, plan_path, repo_root
        )
    else:
        plan_fp = ""
        code_fp = None
    if recs is None:
        recs = [_rec(step_id, kind, 0)]
    return save_review(
        plan_slug=plan_slug,
        plan_path=plan_path.relative_to(repo_root).as_posix(),
        repo_root=repo_root,
        report_md="prior audit",
        recommendations=recs,
        kind=kind,
        step_id=step_id,
        plan_fingerprint=plan_fp,
        code_fingerprint=code_fp,
        now=now,
    )


class TestResolveReusableReconcile:
    """The read/verdict seam: locate the newest kind-matching sidecar,
    recompute both fingerprints, and return a freshness verdict."""

    def test_fresh(self, repo: Path) -> None:
        plan_path = _write_fingerprint_plan(repo)
        _seed_reconcile_sidecar(
            repo, plan_path, kind="detail-reconcile", step_id=1, now=_RT0
        )

        result = resolve_reusable_reconcile(
            "fingerprint", repo, plan_path=plan_path,
            kind_filter="detail-reconcile",
        )

        assert isinstance(result, ReusableReconcile)
        assert result.plan_match is True
        assert result.code_match is True
        assert result.fresh is True
        assert result.drifted_code == []

    def test_missing_returns_none(self, repo: Path) -> None:
        plan_path = _write_fingerprint_plan(repo)
        assert (
            resolve_reusable_reconcile(
                "fingerprint", repo, plan_path=plan_path,
                kind_filter="detail-reconcile",
            )
            is None
        )

    def test_stale_by_plan(self, repo: Path) -> None:
        plan_path = _write_fingerprint_plan(repo)
        _seed_reconcile_sidecar(
            repo, plan_path, kind="detail-reconcile", step_id=1, now=_RT0
        )
        # Append prose to the plan markdown — flips the plan fingerprint,
        # leaves the watched code surface untouched.
        with plan_path.open("a", encoding="utf-8") as fh:
            fh.write("\nextra prose\n")

        result = resolve_reusable_reconcile(
            "fingerprint", repo, plan_path=plan_path,
            kind_filter="detail-reconcile",
        )

        assert result is not None
        assert result.plan_match is False
        assert result.fresh is False
        assert result.drifted_code == []

    def test_stale_by_code(self, repo: Path) -> None:
        plan_path = _write_fingerprint_plan(repo)
        _seed_reconcile_sidecar(
            repo, plan_path, kind="detail-reconcile", step_id=1, now=_RT0
        )
        (repo / "widget.py").write_text(
            "def widget():\n    return 999\n", encoding="utf-8"
        )

        result = resolve_reusable_reconcile(
            "fingerprint", repo, plan_path=plan_path,
            kind_filter="detail-reconcile",
        )

        assert result is not None
        assert result.code_match is False
        assert result.fresh is False
        assert result.drifted_code == [(repo / "widget.py").resolve()]

    def test_deleted_in_scope_file(self, repo: Path) -> None:
        plan_path = _write_fingerprint_plan(repo)
        _seed_reconcile_sidecar(
            repo, plan_path, kind="detail-reconcile", step_id=1, now=_RT0
        )
        # Vanished hashed file → footprint membership, not content drift.
        (repo / "widget.py").unlink()

        result = resolve_reusable_reconcile(
            "fingerprint", repo, plan_path=plan_path,
            kind_filter="detail-reconcile",
        )

        assert result is not None
        assert result.code_match is False
        assert result.fresh is False
        assert result.drifted_code == []
        assert result.footprint_removed == [(repo / "widget.py").resolve()]

    def test_new_file_landed(self, repo: Path) -> None:
        plan_path = _write_fingerprint_plan(repo, new_entry=True)
        # gadget.py absent at capture → omitted from the saved map.
        _seed_reconcile_sidecar(
            repo, plan_path, kind="detail-reconcile", step_id=1, now=_RT0
        )
        (repo / "gadget.py").write_text("gadget = 3\n", encoding="utf-8")

        result = resolve_reusable_reconcile(
            "fingerprint", repo, plan_path=plan_path,
            kind_filter="detail-reconcile",
        )

        assert result is not None
        assert result.code_match is False
        assert result.fresh is False
        assert result.drifted_code == []
        assert result.footprint_added == [(repo / "gadget.py").resolve()]

    def test_legacy_sidecar_is_stale(self, repo: Path) -> None:
        plan_path = _write_fingerprint_plan(repo)
        _seed_reconcile_sidecar(
            repo, plan_path, kind="detail-reconcile", step_id=1,
            now=_RT0, present=False,
        )

        result = resolve_reusable_reconcile(
            "fingerprint", repo, plan_path=plan_path,
            kind_filter="detail-reconcile",
        )

        assert result is not None
        assert result.code_match is False
        assert result.fresh is False
        assert result.drifted_code == []

    def test_docs_only_empty_code_fp_is_fresh(self, repo: Path) -> None:
        plan_path = _write_fingerprint_plan(repo, docs_only=True)
        _seed_reconcile_sidecar(
            repo, plan_path, kind="detail-reconcile", step_id=1, now=_RT0
        )

        result = resolve_reusable_reconcile(
            "fingerprint", repo, plan_path=plan_path,
            kind_filter="detail-reconcile",
        )

        assert result is not None
        assert result.saved.code_fingerprint == {}
        assert result.saved.code_fingerprint_present is True
        assert result.code_match is True
        assert result.fresh is True

    def test_kind_filter_isolation(self, repo: Path) -> None:
        plan_path = _write_fingerprint_plan(repo)
        _seed_reconcile_sidecar(
            repo, plan_path, kind="detail-reconcile", step_id=1, now=_RT0
        )
        # The detail-reconcile save is invisible under the run filter…
        assert (
            resolve_reusable_reconcile(
                "fingerprint", repo, plan_path=plan_path,
                kind_filter="run-reconcile",
            )
            is None
        )
        # …and the run-reconcile save resolves under its own filter.
        _seed_reconcile_sidecar(
            repo, plan_path, kind="run-reconcile", step_id=1, now=_RT1
        )
        run = resolve_reusable_reconcile(
            "fingerprint", repo, plan_path=plan_path,
            kind_filter="run-reconcile",
        )
        assert run is not None
        assert run.saved.kind == "run-reconcile"

    def test_picks_newest(self, repo: Path) -> None:
        plan_path = _write_fingerprint_plan(repo)
        _seed_reconcile_sidecar(
            repo, plan_path, kind="detail-reconcile", step_id=1, now=_RT0,
            recs=[_rec(1, "detail-reconcile", 0)],
        )
        _seed_reconcile_sidecar(
            repo, plan_path, kind="detail-reconcile", step_id=1, now=_RT1,
            recs=[_rec(1, "detail-reconcile", 1)],
        )
        # A newer sidecar of another kind must be ignored.
        _seed_reconcile_sidecar(
            repo, plan_path, kind="run-reconcile", step_id=1, now=_RT2
        )

        result = resolve_reusable_reconcile(
            "fingerprint", repo, plan_path=plan_path,
            kind_filter="detail-reconcile",
        )

        assert result is not None
        assert [r.id for r in result.saved.recommendations] == [
            "step1-detail-reconcile-1"
        ]

    def test_pinned_by_id(self, repo: Path) -> None:
        plan_path = _write_fingerprint_plan(repo)
        old = _seed_reconcile_sidecar(
            repo, plan_path, kind="run-reconcile", step_id=1, now=_RT0,
            recs=[_rec(1, "run-reconcile", 0)],
        )
        _seed_reconcile_sidecar(
            repo, plan_path, kind="run-reconcile", step_id=1, now=_RT1,
            recs=[_rec(1, "run-reconcile", 1)],
        )
        full_stem = old.stem  # "<ts>-run-reconcile"
        bare_stem = full_stem[: -len("-run-reconcile")]

        for review_id in (bare_stem, full_stem):
            result = resolve_reusable_reconcile(
                "fingerprint", repo, plan_path=plan_path,
                review_id=review_id, kind_filter="run-reconcile",
            )
            assert result is not None
            assert [r.id for r in result.saved.recommendations] == [
                "step1-run-reconcile-0"
            ]

    def test_pinned_id_missing_returns_none(self, repo: Path) -> None:
        plan_path = _write_fingerprint_plan(repo)
        _seed_reconcile_sidecar(
            repo, plan_path, kind="run-reconcile", step_id=1, now=_RT0
        )
        assert (
            resolve_reusable_reconcile(
                "fingerprint", repo, plan_path=plan_path,
                review_id="20990101-000000", kind_filter="run-reconcile",
            )
            is None
        )


class TestSelectedRunReconcilePreflight:
    """The run-reconcile selected-step preflight mirrors its adjacent
    OSError/UnicodeDecodeError wrap: a present, readable detail body
    declaring an unsupported format version raises ``LauncherError``
    naming the step and the declared version, not ``DetailFormatError``
    directly."""

    def test_selected_run_reconcile_preflight_refuses_an_unsupported_detail_marker(
        self, repo: Path
    ) -> None:
        from plan_tool.cli.reconcile import _read_selected_run_reconcile_detail
        from plan_tool.detail_artifacts import (
            DetailFormatError,
            render_detail_format_version_marker,
        )
        from plan_tool.launcher import LauncherError
        from plan_tool.schema import Plan, PlanStatus, Priority, Step

        plan_path = repo / "demo.md"
        detail_path = repo / "detail.md"
        detail_path.write_text(
            f"# Step 1\n{render_detail_format_version_marker(999)}\n\nfine.\n",
            encoding="utf-8",
        )
        step = Step(id=1, title="Build it", detail="detail.md", status="done")
        plan = Plan(
            title="Demo", status=PlanStatus.IN_PROGRESS, priority=Priority.LOW,
            steps=[step],
        )

        with pytest.raises(LauncherError, match=r"step 1.*999") as exc_info:
            _read_selected_run_reconcile_detail(plan_path, plan, step, repo)
        assert not isinstance(exc_info.value, DetailFormatError)
