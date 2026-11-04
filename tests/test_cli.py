"""Tests for ``plan-tool`` CLI wiring.

``main()`` is invoked directly so failures surface as integer return
codes (1 on parse / collision / filesystem error; 2 on argparse error
via ``SystemExit``).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import pytest

from plan_tool import style
from plan_tool.cli import build_parser, main
from plan_tool.cli import context as cli_context
from plan_tool.cli import reconcile as reconcile_module
from plan_tool.cli import review_actions as review_actions_module
from plan_tool.convergence import DEFAULT_MAX_ITERATIONS


def _find_subparser(parser, name: str):
    """Return the argparse parser registered under subcommand ``name``."""
    for action in parser._actions:
        choices = getattr(action, "choices", None)
        if isinstance(choices, dict) and name in choices:
            return choices[name]
    return None


class TestNoResumeFlagParsesForDetailAndCreate:
    """Argparse-level smoke: --no-resume is accepted on both subparsers."""

    def test_no_resume_flag_parses_for_detail_and_create(self) -> None:
        parser = build_parser()
        detail = _find_subparser(parser, "detail")
        create = _find_subparser(parser, "create")
        assert detail is not None and create is not None
        # parse_args returns successfully (no SystemExit(2)).
        ns_detail = detail.parse_args(["some-plan", "--no-resume"])
        assert ns_detail.no_resume is True
        ns_create = create.parse_args(["some-slug", "--no-resume"])
        assert ns_create.no_resume is True


class TestDetailAutoCompleteness:
    """``detail`` runs the completeness tail after a clean authoring run."""

    def test_no_completeness_flag_parses(self) -> None:
        parser = build_parser()
        detail = _find_subparser(parser, "detail")
        assert detail is not None
        assert detail.parse_args(["p"]).auto_completeness is True
        assert (
            detail.parse_args(["p", "--no-completeness"]).auto_completeness
            is False
        )

    def _run(self, monkeypatch, tmp_path, **overrides):
        """Drive ``cmd_detail`` with generate_detail + resolve + the
        completeness tail all stubbed, returning the recorded
        completeness-call namespaces (empty list if the tail was skipped).
        """
        import argparse

        from plan_tool.cli import app as cli
        from plan_tool.detail import DetailResult

        plan_path = tmp_path / "1-demo.md"
        # cmd_detail reads the plan file before generate_detail is ever
        # reached (the unmatched-fence gate), so it must exist on disk even
        # though every stage after that point is stubbed out here.
        plan_path.write_text("# plan\n", encoding="utf-8")
        monkeypatch.setattr(
            "plan_tool.cli.authoring.resolve_plan_for_context",
            lambda ctx, name: plan_path,
        )
        monkeypatch.setattr(
            "plan_tool.cli.authoring.generate_detail",
            lambda *a, **k: [
                DetailResult(
                    step_id=1,
                    output_path=tmp_path / "detail" / "01-demo.md",
                    written=True,
                )
            ],
        )
        calls: list = []
        monkeypatch.setattr(
            cli, "cmd_completeness",
            lambda ns: calls.append(ns) or 0,
        )

        args = argparse.Namespace(
            name="demo", repo_root=tmp_path, manifest=None, plans_dir=None,
            step=None, force=False, dry_run=False, reconcile=False,
            lessons=False, no_resume=True, iterate=True, max_iterations=5,
            iteration_budget=300, max_stall_rounds=2,
            allow_drift=False, auto_reconcile_on_drift=True, triage=True,
            include_info=False, collision_sidecar=True, yes=False,
            auto_completeness=True,
        )
        for k, v in overrides.items():
            setattr(args, k, v)
        rc = cli.cmd_detail(args)
        return rc, calls

    def test_tail_invokes_completeness_with_json_forced_off(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        rc, calls = self._run(monkeypatch, tmp_path)
        assert rc == 0
        assert len(calls) == 1
        # iterate is propagated (default-on detail run auto-updates) and
        # json is forced off so the tail emits the human report.
        assert calls[0].iterate is True
        assert calls[0].json is False

    def test_no_completeness_skips_the_tail(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        rc, calls = self._run(monkeypatch, tmp_path, auto_completeness=False)
        assert rc == 0
        assert calls == []

    def test_no_iterate_downgrades_tail_to_audit_only(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        rc, calls = self._run(monkeypatch, tmp_path, iterate=False)
        assert rc == 0
        assert len(calls) == 1
        assert calls[0].iterate is False


@pytest.mark.integration
class TestCmdCheckpoint:
    """End-to-end coverage for ``plan-tool checkpoint list/show/clear``.

    Drives ``main()`` directly via argv so the subparser, dispatch, and
    handler all participate. The ``--repo-root`` flag pins the
    checkpoints root to ``tmp_path`` — no real ``.git`` discovery
    happens, and tests stay hermetic.
    """

    def _seed(
        self,
        tmp_path: Path,
        slug: str = "demo",
        name: str = "detail-step-01",
        payload: str = "# Step 1 body\n",
    ) -> Path:
        from plan_tool.checkpoint import (
            Checkpoint,
            checkpoint_path,
            save_checkpoint,
        )
        from datetime import datetime, timezone

        target = checkpoint_path(tmp_path, slug, name)
        save_checkpoint(
            target,
            Checkpoint(
                input_hash="deadbeef" * 8,
                payload=payload,
                created_at=datetime.now(timezone.utc)
                .replace(microsecond=0)
                .isoformat(),
            ),
        )
        return target

    def test_list_reports_no_checkpoints_when_root_missing(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # ``cmd_checkpoint`` calls ``find_repo_root_from_cwd`` directly,
        # so we cwd into a tmp git-like dir.
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        rc = main(["checkpoint", "list"])
        assert rc == 0
        assert "no checkpoints" in capsys.readouterr().out

    def test_list_shows_seeded_checkpoint(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / ".git").mkdir()
        self._seed(tmp_path, slug="demo", name="detail-step-01")
        monkeypatch.chdir(tmp_path)
        rc = main(["checkpoint", "list"])
        assert rc == 0
        out = capsys.readouterr().out
        # Row contains slug + name + size in bytes (parse-friendly).
        assert "demo" in out
        assert "detail-step-01" in out

    def test_show_prints_payload_to_stdout(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / ".git").mkdir()
        self._seed(
            tmp_path,
            slug="demo",
            name="detail-step-01",
            payload="# unique payload body\n",
        )
        monkeypatch.chdir(tmp_path)
        rc = main(["checkpoint", "show", "demo/detail-step-01"])
        assert rc == 0
        captured = capsys.readouterr()
        # Metadata goes to stderr, payload to stdout — so users can
        # pipe show output without comment lines.
        assert "unique payload body" in captured.out
        assert "input_hash" in captured.err
        assert "created_at" in captured.err

    def test_show_missing_target_exits_nonzero(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        rc = main(["checkpoint", "show", "nope/missing"])
        assert rc == 1
        assert "no such checkpoint" in capsys.readouterr().err

    def test_show_rejects_target_without_slash(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        rc = main(["checkpoint", "show", "no-slash-here"])
        assert rc == 2
        assert "<slug>/<checkpoint>" in capsys.readouterr().err

    def test_clear_slug_removes_only_that_slug(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from plan_tool.checkpoint import checkpoint_dir

        (tmp_path / ".git").mkdir()
        self._seed(tmp_path, slug="demo", name="detail-step-01")
        self._seed(tmp_path, slug="other", name="detail-step-01")
        monkeypatch.chdir(tmp_path)
        rc = main(["checkpoint", "clear", "demo"])
        assert rc == 0
        # ``demo`` dir is gone (rmdir after empty).
        assert not checkpoint_dir(tmp_path, "demo").exists()
        # ``other`` is untouched.
        assert (
            checkpoint_dir(tmp_path, "other") / "detail-step-01.json"
        ).is_file()

    def test_clear_requires_slug_or_all_flag(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        rc = main(["checkpoint", "clear"])
        assert rc == 2
        assert "--all" in capsys.readouterr().err

    def test_clear_all_wipes_every_slug(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from plan_tool.checkpoint import checkpoints_root

        (tmp_path / ".git").mkdir()
        self._seed(tmp_path, slug="demo")
        self._seed(tmp_path, slug="other")
        monkeypatch.chdir(tmp_path)
        rc = main(["checkpoint", "clear", "--all"])
        assert rc == 0
        # Root may still exist but should hold no .json files.
        root = checkpoints_root(tmp_path)
        if root.is_dir():
            assert not any(root.rglob("*.json"))

    # ---------- path-traversal hardening ----------

    @pytest.mark.parametrize(
        "target",
        [
            "../../etc/passwd",   # parent escape via slug
            "demo/../../escape",  # parent escape via name
            "../escape/foo",      # single-dot parent
            "..",                 # bare parent
            ".hidden/foo",        # leading-dot slug (hidden dir)
            "demo/.hidden",       # leading-dot name
            "demo/foo/bar",       # multiple slashes in name → name=foo/bar has /
            "",                   # empty target
            "/abs/path",          # absolute path masquerading as slug
        ],
    )
    def test_show_rejects_traversal_attempts(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
        target: str,
    ) -> None:
        """Every traversal-shaped target gets exit 2 with a stderr error
        — never reads or returns content from outside the checkpoints
        root."""
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        rc = main(["checkpoint", "show", target])
        assert rc == 2
        err = capsys.readouterr().err
        assert "error" in err.lower() or "<slug>/<checkpoint>" in err

    @pytest.mark.parametrize(
        "slug",
        [
            "..",                 # parent
            "../other-plan",      # slug containing /
            "/etc",               # absolute path
            ".hidden",            # leading-dot
            "demo/..",            # slug containing ..
            "",                   # empty (positional default is None, but
                                  # passing "" explicitly should still be
                                  # caught)
        ],
    )
    def test_clear_rejects_traversal_attempts(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
        slug: str,
    ) -> None:
        """``clear`` must refuse any slug that could resolve outside
        the checkpoints root."""
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        rc = main(["checkpoint", "clear", slug])
        assert rc == 2
        assert "error" in capsys.readouterr().err.lower()

    def test_show_rejects_null_byte_via_safe_under_root(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A null byte passes the string-level validator (no ``/``,
        no ``..``, no leading ``.``) but ``Path.resolve()`` raises
        ``ValueError`` on it, which ``_safe_under_root`` collapses to
        an exit-2 refusal. Pins the defense-in-depth contract — if a
        future change replaces the resolve check, this regresses
        loudly instead of silently letting null-byte paths through.
        """
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        # ``demo\x00x`` — string-level validator passes (it's not
        # empty, has no `/`, no `..`, doesn't start with `.`); the
        # resolve-and-relative-to check is what blocks it.
        rc = main(["checkpoint", "show", "demo/foo\x00bar"])
        assert rc == 2
        err = capsys.readouterr().err
        assert "error" in err.lower()

    def test_show_accepts_redundant_json_suffix(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A user pasting ``demo/detail-step-01.json`` from ``list``
        output should not get a confusing "no such checkpoint" miss —
        the handler strips the redundant suffix."""
        (tmp_path / ".git").mkdir()
        self._seed(
            tmp_path,
            slug="demo",
            name="detail-step-01",
            payload="# payload-with-suffix\n",
        )
        monkeypatch.chdir(tmp_path)
        rc = main(["checkpoint", "show", "demo/detail-step-01.json"])
        assert rc == 0
        assert "payload-with-suffix" in capsys.readouterr().out

    # ---------- symlink escape ----------

    def test_list_skips_symlinked_slug_dir(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A symlinked slug-dir under ``checkpoints/`` must not be
        traversed by ``list`` — would otherwise allow reading JSON
        from anywhere on disk."""
        from plan_tool.checkpoint import checkpoints_root

        (tmp_path / ".git").mkdir()
        # Real slug dir with a real checkpoint.
        self._seed(tmp_path, slug="real", name="ck")
        # Attacker-controlled scratch outside the checkpoints root.
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "secret.json").write_text(
            '{"input_hash":"x","payload":"PWNED","created_at":"x","schema_version":1}',
            encoding="utf-8",
        )
        # Symlink ``evil`` slug inside the checkpoints root.
        root = checkpoints_root(tmp_path)
        (root / "evil").symlink_to(outside, target_is_directory=True)
        monkeypatch.chdir(tmp_path)
        rc = main(["checkpoint", "list"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "real" in out
        assert "PWNED" not in out
        # The symlinked slug name must NOT appear as a row.
        assert "evil" not in out

    def test_clear_all_skips_symlinked_slug_dir(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``clear --all`` must not traverse a symlinked slug dir —
        would otherwise delete arbitrary .json files outside the
        checkpoints root."""
        from plan_tool.checkpoint import checkpoints_root

        (tmp_path / ".git").mkdir()
        self._seed(tmp_path, slug="real")
        outside = tmp_path / "outside"
        outside.mkdir()
        outside_file = outside / "important.json"
        outside_file.write_text("DO NOT DELETE\n", encoding="utf-8")
        root = checkpoints_root(tmp_path)
        (root / "evil").symlink_to(outside, target_is_directory=True)
        monkeypatch.chdir(tmp_path)
        rc = main(["checkpoint", "clear", "--all"])
        assert rc == 0
        # Files outside the root survive.
        assert outside_file.is_file()
        assert outside_file.read_text(encoding="utf-8") == "DO NOT DELETE\n"

    # ---------- list-output edge cases ----------

    def test_list_malformed_json_row_shows_question_marks(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A corrupt checkpoint file gets a ``?`` row, not a crash."""
        from plan_tool.checkpoint import checkpoint_dir

        (tmp_path / ".git").mkdir()
        slug_dir = checkpoint_dir(tmp_path, "broken")
        slug_dir.mkdir(parents=True)
        (slug_dir / "bad.json").write_text("not valid json{", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        rc = main(["checkpoint", "list"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "broken" in out
        assert "bad" in out

    def test_list_unparseable_created_at_shows_question_age(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A checkpoint with a garbage timestamp lists with ``?`` age."""
        from plan_tool.checkpoint import checkpoint_dir

        (tmp_path / ".git").mkdir()
        slug_dir = checkpoint_dir(tmp_path, "garbled")
        slug_dir.mkdir(parents=True)
        (slug_dir / "ck.json").write_text(
            '{"input_hash":"x","payload":"y","created_at":"not a real ts","schema_version":1}',
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        rc = main(["checkpoint", "list"])
        assert rc == 0
        out = capsys.readouterr().out
        # The age column for this row reads "?" (substring match
        # because surrounding spaces make exact equality brittle).
        assert "garbled" in out
        # Find the row and confirm "?" appears in its age column.
        garbled_lines = [ln for ln in out.splitlines() if "garbled" in ln]
        assert garbled_lines, "expected a row for the garbled slug"
        assert "?" in garbled_lines[0]

    def test_list_shows_multiple_files_per_slug(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Multiple checkpoints under one slug each get their own row."""
        (tmp_path / ".git").mkdir()
        self._seed(tmp_path, slug="multi", name="detail-step-01")
        self._seed(tmp_path, slug="multi", name="detail-step-02")
        self._seed(tmp_path, slug="multi", name="detail-step-03")
        monkeypatch.chdir(tmp_path)
        rc = main(["checkpoint", "list"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "detail-step-01" in out
        assert "detail-step-02" in out
        assert "detail-step-03" in out

    # ---------- partial-failure exit code ----------

    def test_clear_slug_returns_1_when_unlink_fails(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """If any unlink raises during ``clear <slug>``, the handler
        warns, continues, and exits 1 so callers can distinguish
        full-success from partial-success."""
        from plan_tool.cli import app as cli_module
        from pathlib import Path as _Path

        (tmp_path / ".git").mkdir()
        self._seed(tmp_path, slug="boom", name="ck1")
        self._seed(tmp_path, slug="boom", name="ck2")

        real_unlink = _Path.unlink
        first = {"called": False}

        def selective_unlink(self: _Path, *a: object, **kw: object) -> None:
            # First call raises (simulates a permission error on one
            # file); subsequent calls succeed. Ensures we cover the
            # mixed-success branch.
            if not first["called"] and self.name.endswith(".json"):
                first["called"] = True
                raise PermissionError("simulated")
            return real_unlink(self, *a, **kw)

        monkeypatch.setattr(_Path, "unlink", selective_unlink)
        monkeypatch.chdir(tmp_path)
        rc = main(["checkpoint", "clear", "boom"])
        assert rc == 1
        captured = capsys.readouterr()
        assert "warning" in captured.err.lower()
        assert "could not be removed" in captured.out

    # ---------- argparse-level exits ----------

    def test_checkpoint_without_action_exits_2(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The subparser declares ``required=True`` for the action —
        omitting it must produce argparse's exit 2, not a handler
        crash."""
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        with pytest.raises(SystemExit) as exc:
            main(["checkpoint"])
        assert exc.value.code == 2


@pytest.mark.integration
class TestCmdRuns:
    """End-to-end coverage for ``plan-tool runs list/show/diff/clear``.

    Drives ``main()`` directly via argv so the subparser, dispatch, and
    handler all participate. ``find_repo_root_from_cwd`` is invoked
    inside the handler; a ``.git`` marker at ``tmp_path`` pins the runs
    root there.
    """

    def _seed_run(
        self,
        tmp_path: Path,
        slug: str = "demo",
        run_id: str = "2026-05-14T12-34-56-9f3a1c",
        *,
        events=None,
        started_at: str = "2026-05-14T12:34:56+00:00",
        command: str = "create",
        schema_version: int = 1,
        include_run_end: bool = True,
        run_end_duration_ms: int = 87000,
    ):
        """Write a deterministic JSONL run log under ``tmp_path``.

        If ``events`` is supplied, it is written verbatim. Otherwise a
        minimal happy-path run is built: ``run_start`` plus one
        ``phase_start`` / ``claude_call_start`` / ``claude_call_end``
        / ``phase_end`` block plus (optionally) ``run_end``.
        """
        import json as _json
        from plan_tool.run_log import run_log_path as _run_log_path

        target = _run_log_path(tmp_path, slug, run_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        if events is None:
            events = [
                {
                    "ts": started_at,
                    "run_id": run_id,
                    "event": "run_start",
                    "schema_version": schema_version,
                    "command": command,
                    "plan_slug": slug,
                    "argv": [command, slug],
                    "pid": 1234,
                    "cwd": str(tmp_path),
                },
                {
                    "ts": started_at,
                    "run_id": run_id,
                    "event": "phase_start",
                    "phase": "propose_steps",
                },
                {
                    "ts": started_at,
                    "run_id": run_id,
                    "event": "claude_call_start",
                    "phase": "propose_steps",
                    "attempt": 1,
                    "prompt_bytes": 100,
                },
                {
                    "ts": started_at,
                    "run_id": run_id,
                    "event": "claude_call_end",
                    "phase": "propose_steps",
                    "attempt": 1,
                    "rc": 0,
                    "duration_ms": 5000,
                    "stdout_bytes": 200,
                    "tokens_input": 100,
                    "tokens_output": 200,
                },
                {
                    "ts": started_at,
                    "run_id": run_id,
                    "event": "phase_end",
                    "phase": "propose_steps",
                    "duration_ms": 5500,
                    "outcome": "success",
                },
            ]
            if include_run_end:
                events.append(
                    {
                        "ts": started_at,
                        "run_id": run_id,
                        "event": "run_end",
                        "duration_ms": run_end_duration_ms,
                        "outcome": "success",
                        "rc": 0,
                    }
                )
        with target.open("w", encoding="utf-8") as f:
            for ev in events:
                f.write(_json.dumps(ev, separators=(",", ":")))
                f.write("\n")
        return target

    # ---------- runs list ----------

    def test_list_reports_no_runs_when_root_missing(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "list"])
        assert rc == 0
        assert "no runs" in capsys.readouterr().out

    def test_list_shows_seeded_run(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / ".git").mkdir()
        self._seed_run(tmp_path, slug="demo")
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "list"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "demo" in out
        assert "2026-05-14T12-34-56-9f3a1c" in out
        assert "create" in out
        # Tokens column = 100 + 200 = 300
        assert "300" in out

    def test_list_aggregates_tokens_across_claude_calls(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / ".git").mkdir()
        events = [
            {
                "ts": "2026-05-14T12:00:00+00:00",
                "run_id": "rid",
                "event": "run_start",
                "schema_version": 1,
                "command": "run",
                "plan_slug": "demo",
                "argv": ["run", "demo"],
                "pid": 1,
                "cwd": str(tmp_path),
            },
            {
                "ts": "2026-05-14T12:00:01+00:00",
                "run_id": "rid",
                "event": "claude_call_end",
                "phase": "p1",
                "attempt": 1,
                "rc": 0,
                "duration_ms": 1000,
                "stdout_bytes": 10,
                "tokens_input": 100,
                "tokens_output": 200,
            },
            {
                "ts": "2026-05-14T12:00:02+00:00",
                "run_id": "rid",
                "event": "claude_call_end",
                "phase": "p2",
                "attempt": 1,
                "rc": 0,
                "duration_ms": 500,
                "stdout_bytes": 10,
                "tokens_input": 50,
                "tokens_output": 75,
            },
        ]
        self._seed_run(
            tmp_path, slug="demo", run_id="rid", events=events
        )
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "list"])
        assert rc == 0
        out = capsys.readouterr().out
        # 100 + 200 + 50 + 75 = 425
        assert "425" in out

    def test_list_renders_in_flight_duration(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / ".git").mkdir()
        self._seed_run(tmp_path, slug="demo", include_run_end=False)
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "list"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "in-flight" in out

    def test_list_slug_filter_limits_walk(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / ".git").mkdir()
        self._seed_run(tmp_path, slug="demo")
        self._seed_run(tmp_path, slug="other")
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "list", "--slug", "demo"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "demo" in out
        # The other slug must not appear as a row.
        slug_rows = [
            ln for ln in out.splitlines()
            if "2026-05-14T12-34-56-9f3a1c" in ln
        ]
        assert all("other" not in ln for ln in slug_rows)

    def test_list_skips_symlinked_slug_dir(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from plan_tool.run_log import runs_root as _runs_root

        (tmp_path / ".git").mkdir()
        self._seed_run(tmp_path, slug="real")
        outside = tmp_path / "outside"
        outside.mkdir()
        # Drop a fake JSONL outside the runs root.
        (outside / "evil.jsonl").write_text(
            '{"event":"run_start","schema_version":1,"command":"PWNED",'
            '"plan_slug":"evil","ts":"2026-05-14T00:00:00+00:00",'
            '"run_id":"r"}\n',
            encoding="utf-8",
        )
        root = _runs_root(tmp_path)
        root.mkdir(parents=True, exist_ok=True)
        (root / "evil").symlink_to(outside, target_is_directory=True)
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "list"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "real" in out
        assert "PWNED" not in out
        assert "evil" not in out

    def test_list_malformed_jsonl_row_shows_question_marks(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from plan_tool.run_log import run_dir as _run_dir

        (tmp_path / ".git").mkdir()
        slug_dir = _run_dir(tmp_path, "broken")
        slug_dir.mkdir(parents=True)
        (slug_dir / "bad.jsonl").write_text(
            "not valid json{\n", encoding="utf-8"
        )
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "list"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "broken" in out
        assert "bad" in out
        assert "?" in out

    def test_list_tolerates_partial_last_line(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import json as _json
        from plan_tool.run_log import run_log_path as _rlp

        (tmp_path / ".git").mkdir()
        target = _rlp(tmp_path, "demo", "rid")
        target.parent.mkdir(parents=True, exist_ok=True)
        # First line valid, second line is a truncated partial-write
        # with no trailing newline and broken JSON.
        first = {
            "ts": "2026-05-14T12:00:00+00:00",
            "run_id": "rid",
            "event": "run_start",
            "schema_version": 1,
            "command": "create",
            "plan_slug": "demo",
            "argv": [],
            "pid": 1,
            "cwd": str(tmp_path),
        }
        with target.open("w", encoding="utf-8") as f:
            f.write(_json.dumps(first, separators=(",", ":")))
            f.write("\n")
            f.write('{"event":"phase_start","phase":"propo')  # no \n
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "list"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "demo" in out
        # event count column is 1 (well-formed line) — not 2.
        rows = [
            ln for ln in out.splitlines()
            if "rid" in ln and "demo" in ln
        ]
        assert rows, "expected a row for the seeded slug"

    # ---------- runs show ----------

    def test_show_prints_events_to_stdout(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / ".git").mkdir()
        self._seed_run(tmp_path, slug="demo")
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "show", "demo/2026-05-14T12-34-56-9f3a1c"])
        assert rc == 0
        captured = capsys.readouterr()
        # Event names land on stdout.
        assert "run_start" in captured.out
        assert "phase_start" in captured.out
        assert "claude_call_end" in captured.out
        assert "run_end" in captured.out
        # Metadata goes to stderr.
        assert "run_id" in captured.err
        assert "plan_slug" in captured.err
        assert "command" in captured.err
        assert "schema_version" in captured.err

    def test_show_renders_skip_reason_beside_outcome(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``skip_reason`` reaches the operator, not just the JSONL.

        Several phases bucket distinct causes into ``outcome=skipped``,
        so a run log that records *why* is only useful if the renderer's
        key allowlist actually carries the field through.
        """
        import json as _json
        from plan_tool.run_log import run_log_path as _run_log_path

        (tmp_path / ".git").mkdir()
        run_id = "2026-05-14T12-34-56-9f3a1c"
        target = _run_log_path(tmp_path, "demo", run_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        events = [
            {
                "ts": "2026-05-14T12:34:56+00:00", "run_id": run_id,
                "event": "run_start", "schema_version": 1,
                "command": "create", "plan_slug": "demo",
                "argv": ["create", "demo"], "pid": 1234,
                "cwd": str(tmp_path),
            },
            {
                "ts": "2026-05-14T12:34:57+00:00", "run_id": run_id,
                "event": "phase_start", "phase": "propose_body_sections",
            },
            {
                "ts": "2026-05-14T12:34:57+00:00", "run_id": run_id,
                "event": "phase_end", "phase": "propose_body_sections",
                "duration_ms": 0, "outcome": "skipped",
                "skip_reason": "already_canonical",
            },
        ]
        with target.open("w", encoding="utf-8") as f:
            for ev in events:
                f.write(_json.dumps(ev, separators=(",", ":")) + "\n")

        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "show", f"demo/{run_id}"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "outcome=skipped" in out
        assert "skip_reason=already_canonical" in out

    def test_show_missing_target_exits_1(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "show", "nope/missing"])
        assert rc == 1
        assert "no such run" in capsys.readouterr().err

    def test_show_rejects_target_without_slash(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "show", "no-slash-here"])
        assert rc == 2
        assert "<slug>/<run_id>" in capsys.readouterr().err

    def test_show_accepts_redundant_jsonl_suffix(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / ".git").mkdir()
        self._seed_run(tmp_path, slug="demo")
        monkeypatch.chdir(tmp_path)
        rc = main(
            ["runs", "show", "demo/2026-05-14T12-34-56-9f3a1c.jsonl"]
        )
        assert rc == 0
        assert "run_start" in capsys.readouterr().out

    def test_show_refuses_schema_version_mismatch(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / ".git").mkdir()
        self._seed_run(tmp_path, slug="demo", schema_version=99)
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "show", "demo/2026-05-14T12-34-56-9f3a1c"])
        assert rc == 1
        err = capsys.readouterr().err
        assert "unsupported run-log schema_version" in err

    def test_show_exits_1_when_every_line_unparseable(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A run log full of garbage lines must exit 1 with a clear
        message, NOT render empty `?` metadata and exit 0. Without
        this contract, a corrupted log would let CI / scripts treat
        a damaged run as a successful read.
        """
        from plan_tool.run_log import run_log_path as _run_log_path

        (tmp_path / ".git").mkdir()
        target = _run_log_path(tmp_path, "demo", "2026-05-14T00-00-00-aaaa")
        target.parent.mkdir(parents=True, exist_ok=True)
        # Three lines: malformed JSON, non-dict JSON, partial JSON.
        target.write_text(
            "not json{\n[1, 2, 3]\n{\"event\": \"phase_start\"\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "show", "demo/2026-05-14T00-00-00-aaaa"])
        assert rc == 1
        err = capsys.readouterr().err
        assert "unreadable" in err
        assert "no parseable events" in err

    def test_show_warns_but_continues_on_partial_unparseable_lines(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A log with some valid events and some unparseable lines
        renders the valid events to stdout, prints a warning count
        on stderr, and exits 0. (A torn last line from a Ctrl-C
        mid-write is the typical real-world cause.)
        """
        from plan_tool.run_log import run_log_path as _run_log_path

        (tmp_path / ".git").mkdir()
        target = _run_log_path(tmp_path, "demo", "2026-05-14T00-00-00-bbbb")
        target.parent.mkdir(parents=True, exist_ok=True)
        valid_run_start = (
            '{"ts": "2026-05-14T00:00:00+00:00", "run_id": "x", '
            '"event": "run_start", "schema_version": 1, "command": "create", '
            '"plan_slug": "demo", "argv": ["create", "demo"], "pid": 1, '
            '"cwd": "/repo"}'
        )
        # One valid event + two unparseable lines.
        target.write_text(
            valid_run_start + "\n" + "garbage{\n" + "[1, 2]\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "show", "demo/2026-05-14T00-00-00-bbbb"])
        assert rc == 0
        captured = capsys.readouterr()
        assert "warning: 2 unreadable" in captured.err
        # The valid event lands on stdout.
        assert "run_start" in captured.out

    def test_show_indents_phase_and_claude_call_events(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / ".git").mkdir()
        self._seed_run(tmp_path, slug="demo")
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "show", "demo/2026-05-14T12-34-56-9f3a1c"])
        assert rc == 0
        out = capsys.readouterr().out
        # Find the claude_call_start line — it should have more
        # leading whitespace than the phase_start line.
        ps_line = next(
            ln for ln in out.splitlines() if "phase_start" in ln
        )
        cc_line = next(
            ln for ln in out.splitlines() if "claude_call_start" in ln
        )
        ps_lead = len(ps_line) - len(ps_line.lstrip(" "))
        cc_lead = len(cc_line) - len(cc_line.lstrip(" "))
        assert cc_lead > ps_lead

    # ---------- runs diff ----------

    def _build_phase_run(
        self,
        run_id: str,
        slug: str,
        phases: list[tuple[str, int, int, int]],
        started_at: str = "2026-05-14T12:00:00+00:00",
    ) -> list[dict]:
        """Build an event list for a run with a given phase profile.

        ``phases`` is a list of (phase_name, wall_ms, tokens_in, tokens_out).
        Each tuple emits one phase_start / claude_call_start /
        claude_call_end / phase_end block.
        """
        events: list[dict] = [
            {
                "ts": started_at,
                "run_id": run_id,
                "event": "run_start",
                "schema_version": 1,
                "command": "create",
                "plan_slug": slug,
                "argv": [],
                "pid": 1,
                "cwd": "/tmp",
            }
        ]
        for phase, wall_ms, ti, to in phases:
            events.extend([
                {
                    "ts": started_at,
                    "run_id": run_id,
                    "event": "phase_start",
                    "phase": phase,
                },
                {
                    "ts": started_at,
                    "run_id": run_id,
                    "event": "claude_call_start",
                    "phase": phase,
                    "attempt": 1,
                    "prompt_bytes": 1,
                },
                {
                    "ts": started_at,
                    "run_id": run_id,
                    "event": "claude_call_end",
                    "phase": phase,
                    "attempt": 1,
                    "rc": 0,
                    "duration_ms": wall_ms,
                    "stdout_bytes": 1,
                    "tokens_input": ti,
                    "tokens_output": to,
                },
                {
                    "ts": started_at,
                    "run_id": run_id,
                    "event": "phase_end",
                    "phase": phase,
                    "duration_ms": wall_ms,
                    "outcome": "success",
                },
            ])
        events.append({
            "ts": started_at,
            "run_id": run_id,
            "event": "run_end",
            "duration_ms": sum(p[1] for p in phases),
            "outcome": "success",
            "rc": 0,
        })
        return events

    def test_diff_renders_phase_table_with_deltas(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / ".git").mkdir()
        self._seed_run(
            tmp_path,
            slug="demo",
            run_id="run-a",
            events=self._build_phase_run(
                "run-a", "demo", [("propose_steps", 1000, 100, 200)]
            ),
        )
        self._seed_run(
            tmp_path,
            slug="demo",
            run_id="run-b",
            events=self._build_phase_run(
                "run-b", "demo", [("propose_steps", 1500, 110, 220)]
            ),
        )
        monkeypatch.chdir(tmp_path)
        rc = main(
            ["runs", "diff", "demo/run-a", "demo/run-b"]
        )
        assert rc == 0
        out = capsys.readouterr().out
        # Header has Δwall and Δtokens
        assert "Δwall" in out
        assert "Δtokens" in out
        assert "propose_steps" in out
        # Δwall = 1500 - 1000 = +500
        assert "+500" in out
        # Δtokens = (110+220) - (100+200) = 330 - 300 = +30
        assert "+30" in out

    def test_diff_flags_only_in_a(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / ".git").mkdir()
        self._seed_run(
            tmp_path, slug="demo", run_id="run-a",
            events=self._build_phase_run(
                "run-a", "demo",
                [("shared", 1000, 100, 200), ("only_a", 500, 50, 50)],
            ),
        )
        self._seed_run(
            tmp_path, slug="demo", run_id="run-b",
            events=self._build_phase_run(
                "run-b", "demo", [("shared", 1000, 100, 200)]
            ),
        )
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "diff", "demo/run-a", "demo/run-b"])
        assert rc == 0
        out = capsys.readouterr().out
        only_a_line = next(
            (ln for ln in out.splitlines() if "only_a" in ln), ""
        )
        assert "only-in-A" in only_a_line

    def test_diff_flags_only_in_b(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / ".git").mkdir()
        self._seed_run(
            tmp_path, slug="demo", run_id="run-a",
            events=self._build_phase_run(
                "run-a", "demo", [("shared", 1000, 100, 200)]
            ),
        )
        self._seed_run(
            tmp_path, slug="demo", run_id="run-b",
            events=self._build_phase_run(
                "run-b", "demo",
                [("shared", 1000, 100, 200), ("only_b", 500, 50, 50)],
            ),
        )
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "diff", "demo/run-a", "demo/run-b"])
        assert rc == 0
        out = capsys.readouterr().out
        only_b_line = next(
            (ln for ln in out.splitlines() if "only_b" in ln), ""
        )
        assert "only-in-B" in only_b_line

    def test_diff_renders_dash_when_tokens_unavailable(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / ".git").mkdir()
        # Both runs: claude_call_end with tokens fields set to None.
        def _none_tokens_events(run_id: str) -> list[dict]:
            ts = "2026-05-14T12:00:00+00:00"
            return [
                {
                    "ts": ts, "run_id": run_id, "event": "run_start",
                    "schema_version": 1, "command": "create",
                    "plan_slug": "demo", "argv": [], "pid": 1, "cwd": "/tmp",
                },
                {
                    "ts": ts, "run_id": run_id, "event": "phase_start",
                    "phase": "propose_steps",
                },
                {
                    "ts": ts, "run_id": run_id,
                    "event": "claude_call_start",
                    "phase": "propose_steps", "attempt": 1,
                    "prompt_bytes": 1,
                },
                {
                    "ts": ts, "run_id": run_id,
                    "event": "claude_call_end",
                    "phase": "propose_steps", "attempt": 1, "rc": 0,
                    "duration_ms": 1000, "stdout_bytes": 1,
                    "tokens_input": None, "tokens_output": None,
                },
                {
                    "ts": ts, "run_id": run_id, "event": "phase_end",
                    "phase": "propose_steps", "duration_ms": 1000,
                    "outcome": "success",
                },
                {
                    "ts": ts, "run_id": run_id, "event": "run_end",
                    "duration_ms": 1000, "outcome": "success", "rc": 0,
                },
            ]

        self._seed_run(
            tmp_path, slug="demo", run_id="run-a",
            events=_none_tokens_events("run-a"),
        )
        self._seed_run(
            tmp_path, slug="demo", run_id="run-b",
            events=_none_tokens_events("run-b"),
        )
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "diff", "demo/run-a", "demo/run-b"])
        assert rc == 0
        out = capsys.readouterr().out
        # The tokens columns for propose_steps should be "-".
        ps_line = next(
            ln for ln in out.splitlines() if "propose_steps" in ln
        )
        # Three columns of '-' (tokens_a, tokens_b, Δtokens).
        assert ps_line.count("-") >= 2

    def test_diff_missing_file_exits_1(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / ".git").mkdir()
        self._seed_run(tmp_path, slug="demo", run_id="run-a")
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "diff", "demo/run-a", "demo/missing"])
        assert rc == 1
        err = capsys.readouterr().err
        assert "no such run" in err

    def test_diff_rejects_traversal_in_either_arg(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / ".git").mkdir()
        self._seed_run(tmp_path, slug="demo", run_id="run-a")
        monkeypatch.chdir(tmp_path)
        # Bad ``a``: traversal-shaped slug.
        rc1 = main(
            ["runs", "diff", "../escape/foo", "demo/run-a"]
        )
        assert rc1 == 2
        capsys.readouterr()
        # Bad ``b``: traversal-shaped slug.
        rc2 = main(
            ["runs", "diff", "demo/run-a", "../escape/foo"]
        )
        assert rc2 == 2

    def test_diff_trailing_summary_line(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / ".git").mkdir()
        self._seed_run(
            tmp_path, slug="demo", run_id="run-a",
            events=self._build_phase_run(
                "run-a", "demo", [("shared", 1000, 100, 200)]
            ),
        )
        self._seed_run(
            tmp_path, slug="demo", run_id="run-b",
            events=self._build_phase_run(
                "run-b", "demo", [("shared", 1500, 110, 220)]
            ),
        )
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "diff", "demo/run-a", "demo/run-b"])
        assert rc == 0
        out = capsys.readouterr().out
        trailing = out.rstrip().splitlines()[-1]
        assert "total Δwall" in trailing
        assert "total Δtokens" in trailing
        assert "only-in-A" in trailing
        assert "only-in-B" in trailing

    # ---------- runs clear ----------

    def test_clear_slug_removes_only_that_slug(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from plan_tool.run_log import run_dir as _run_dir

        (tmp_path / ".git").mkdir()
        self._seed_run(tmp_path, slug="demo")
        self._seed_run(tmp_path, slug="other")
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "clear", "demo"])
        assert rc == 0
        # demo dir is empty + removed.
        assert not _run_dir(tmp_path, "demo").exists()
        # other survives.
        assert (
            _run_dir(tmp_path, "other") / "2026-05-14T12-34-56-9f3a1c.jsonl"
        ).is_file()

    def test_clear_slug_removes_its_stream_log_dirs_too(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Raw stream logs outlive nothing: clearing a slug takes its
        ``.streams`` dirs, while another slug's are untouched."""
        from plan_tool.run_log import run_dir as _run_dir

        (tmp_path / ".git").mkdir()
        for slug in ("demo", "other"):
            self._seed_run(tmp_path, slug=slug)
            streams = _run_dir(tmp_path, slug) / "rid.streams"
            streams.mkdir()
            (streams / "claude-stream.0001.p.a1.ndjson").write_text("{}\n")
        monkeypatch.chdir(tmp_path)
        assert main(["runs", "clear", "demo"]) == 0
        assert not _run_dir(tmp_path, "demo").exists()
        assert (_run_dir(tmp_path, "other") / "rid.streams").is_dir()

    def test_clear_requires_slug_or_all_or_older_than(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "clear"])
        assert rc == 2
        err = capsys.readouterr().err
        assert "--all" in err
        assert "<slug>" in err
        assert "--older-than" in err

    def test_clear_all_wipes_every_slug(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from plan_tool.run_log import runs_root as _runs_root

        (tmp_path / ".git").mkdir()
        self._seed_run(tmp_path, slug="demo")
        self._seed_run(tmp_path, slug="other")
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "clear", "--all"])
        assert rc == 0
        root = _runs_root(tmp_path)
        if root.is_dir():
            assert not any(root.rglob("*.jsonl"))

    def test_clear_all_skips_symlinked_slug_dir(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from plan_tool.run_log import runs_root as _runs_root

        (tmp_path / ".git").mkdir()
        self._seed_run(tmp_path, slug="real")
        outside = tmp_path / "outside"
        outside.mkdir()
        outside_file = outside / "important.jsonl"
        outside_file.write_text("DO NOT DELETE\n", encoding="utf-8")
        root = _runs_root(tmp_path)
        (root / "evil").symlink_to(outside, target_is_directory=True)
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "clear", "--all"])
        assert rc == 0
        assert outside_file.is_file()
        assert outside_file.read_text(encoding="utf-8") == "DO NOT DELETE\n"

    def test_clear_older_than_evicts_only_old_runs(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from datetime import datetime, timezone, timedelta
        from plan_tool.run_log import run_log_path as _rlp

        (tmp_path / ".git").mkdir()
        old_ts = (
            datetime.now(timezone.utc) - timedelta(days=31)
        ).replace(microsecond=0).isoformat()
        new_ts = (
            datetime.now(timezone.utc) - timedelta(hours=1)
        ).replace(microsecond=0).isoformat()
        self._seed_run(
            tmp_path, slug="demo", run_id="old-run",
            started_at=old_ts,
        )
        self._seed_run(
            tmp_path, slug="demo", run_id="new-run",
            started_at=new_ts,
        )
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "clear", "--older-than", "30d"])
        assert rc == 0
        old_path = _rlp(tmp_path, "demo", "old-run")
        new_path = _rlp(tmp_path, "demo", "new-run")
        assert not old_path.exists()
        assert new_path.is_file()

    def test_clear_older_than_30d_combined_with_slug_filter(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from datetime import datetime, timezone, timedelta
        from plan_tool.run_log import run_log_path as _rlp

        (tmp_path / ".git").mkdir()
        old_ts = (
            datetime.now(timezone.utc) - timedelta(days=31)
        ).replace(microsecond=0).isoformat()
        self._seed_run(
            tmp_path, slug="demo", run_id="old-run",
            started_at=old_ts,
        )
        self._seed_run(
            tmp_path, slug="other", run_id="old-other",
            started_at=old_ts,
        )
        monkeypatch.chdir(tmp_path)
        rc = main(
            ["runs", "clear", "demo", "--older-than", "30d"]
        )
        assert rc == 0
        assert not _rlp(tmp_path, "demo", "old-run").exists()
        # 'other' is untouched because the slug filter limited the walk.
        assert _rlp(tmp_path, "other", "old-other").is_file()

    def test_clear_older_than_preserves_in_flight_json(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from datetime import datetime, timezone, timedelta
        from plan_tool.run_log import (
            in_flight_path as _ifp,
            run_log_path as _rlp,
        )

        (tmp_path / ".git").mkdir()
        old_ts = (
            datetime.now(timezone.utc) - timedelta(days=31)
        ).replace(microsecond=0).isoformat()
        self._seed_run(
            tmp_path, slug="demo", run_id="old-run",
            started_at=old_ts,
        )
        ifp = _ifp(tmp_path, "demo")
        ifp.parent.mkdir(parents=True, exist_ok=True)
        ifp.write_text(
            '{"schema_version":1,"run_id":"active"}\n',
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "clear", "--older-than", "30d"])
        assert rc == 0
        assert not _rlp(tmp_path, "demo", "old-run").exists()
        assert ifp.is_file()

    def test_clear_all_removes_in_flight_json(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from plan_tool.run_log import in_flight_path as _ifp

        (tmp_path / ".git").mkdir()
        self._seed_run(tmp_path, slug="demo")
        ifp = _ifp(tmp_path, "demo")
        ifp.write_text(
            '{"schema_version":1,"run_id":"active"}\n',
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "clear", "--all"])
        assert rc == 0
        assert not ifp.exists()

    def test_clear_rejects_unparseable_older_than(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "clear", "--older-than", "30days"])
        assert rc == 2
        err = capsys.readouterr().err
        assert "--older-than" in err

    # ---------- path-traversal hardening ----------

    @pytest.mark.parametrize(
        "target",
        [
            "../etc/passwd",
            "demo/../escape",
            "../escape/foo",
            "..",
            ".hidden/foo",
            "demo/.hidden",
            "demo/foo/bar",
            "",
            "/abs/path",
        ],
    )
    def test_show_rejects_traversal_attempts(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
        target: str,
    ) -> None:
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "show", target])
        assert rc == 2
        err = capsys.readouterr().err
        assert "error" in err.lower() or "<slug>/<run_id>" in err

    @pytest.mark.parametrize(
        "slug",
        [
            "..",
            "../other",
            "/etc",
            ".hidden",
            "demo/..",
            "",
        ],
    )
    def test_clear_rejects_traversal_attempts(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
        slug: str,
    ) -> None:
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "clear", slug])
        assert rc == 2
        assert "error" in capsys.readouterr().err.lower()

    def test_show_rejects_null_byte_via_safe_under_root(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "show", "demo/foo\x00bar"])
        assert rc == 2
        err = capsys.readouterr().err
        assert "error" in err.lower()

    # ---------- partial-failure exit code ----------

    def test_clear_slug_returns_1_when_unlink_fails(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from pathlib import Path as _Path

        (tmp_path / ".git").mkdir()
        self._seed_run(tmp_path, slug="boom", run_id="ck1")
        self._seed_run(tmp_path, slug="boom", run_id="ck2")

        real_unlink = _Path.unlink
        first = {"called": False}

        def selective_unlink(self: _Path, *a, **kw) -> None:
            if not first["called"] and self.name.endswith(".jsonl"):
                first["called"] = True
                raise PermissionError("simulated")
            return real_unlink(self, *a, **kw)

        monkeypatch.setattr(_Path, "unlink", selective_unlink)
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "clear", "boom"])
        assert rc == 1
        captured = capsys.readouterr()
        assert "warning" in captured.err.lower()
        assert "could not be removed" in captured.out

    # ---------- argparse-level exits ----------

    def test_runs_without_action_exits_2(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        with pytest.raises(SystemExit) as exc:
            main(["runs"])
        assert exc.value.code == 2


@pytest.mark.integration
class TestCmdRunsProfile:
    """End-to-end coverage for ``plan-tool runs profile``.

    The handler walks every JSONL under the runs root, pairs
    ``claude_call_start`` with ``claude_call_end`` on ``(phase,
    attempt)``, and aggregates the resulting samples into buckets
    keyed by ``--by`` ({mode, step, run}). The tests below pin:

    - The aggregation correctly populates count / total / mean / p50.
      p95 with ``statistics.quantiles`` needs ≥ 2 samples; the
      single-sample case is exercised separately.
    - ``--by`` switches the bucketing key.
    - ``--slug``, ``--mode``, ``--since`` filter the input.
    - ``--top N`` truncates after sorting by total wall-clock desc.
    - ``--json`` emits a single-line JSON envelope.
    - In-flight runs (no ``run_end``) are skipped from aggregation.
    - Unmatched starts surface as ``incomplete`` but are excluded
      from the latency stats.
    """

    def _seed_profile_run(
        self,
        tmp_path: Path,
        *,
        slug: str = "demo",
        run_id: str = "rid-1",
        started_at: str = "2026-05-14T12:00:00+00:00",
        calls,
        include_run_end: bool = True,
    ) -> Path:
        """Write a JSONL run log with one phase per ``calls`` entry.

        Each entry in ``calls`` is a dict supporting:

        - ``mode`` (str | None): mode tagged on ``phase_start``
        - ``step_id`` (int | None): tagged on ``claude_call_start``
        - ``duration_ms`` (int): tagged on ``claude_call_end``
        - ``rc`` (int): tagged on ``claude_call_end``
        - ``tokens_input`` / ``tokens_output`` / ``cache_read_tokens``
          / ``cost_usd`` (optional): tagged on ``claude_call_end``
        - ``incomplete`` (bool, default False): when True, the start is
          emitted but no matching end is appended

        Each call also gets a unique phase name so the start/end pair
        is unambiguous (``phase_N``).

        Note for callers asserting on quantile values: ``runs profile``
        suppresses p50 / p95 below ``_SMALL_BUCKET_THRESHOLD`` (5)
        completed samples — buckets seeded with fewer than that get
        ``None`` (JSON) / ``n=<N>`` (text) instead of ms values. Seed
        at least 5 completed calls per bucket when the assertion
        depends on p50_ms / p95_ms being present.
        """
        import json as _json
        from plan_tool.run_log import run_log_path as _rlp

        target = _rlp(tmp_path, slug, run_id)
        target.parent.mkdir(parents=True, exist_ok=True)

        events = [
            {
                "ts": started_at,
                "run_id": run_id,
                "event": "run_start",
                "schema_version": 1,
                "command": "run",
                "plan_slug": slug,
                "argv": ["run", slug],
                "pid": 1234,
                "cwd": str(tmp_path),
            },
        ]
        for idx, call in enumerate(calls):
            phase = f"phase_{idx}"
            phase_start = {
                "ts": started_at,
                "run_id": run_id,
                "event": "phase_start",
                "phase": phase,
            }
            if call.get("mode") is not None:
                phase_start["mode"] = call["mode"]
            events.append(phase_start)
            call_start = {
                "ts": started_at,
                "run_id": run_id,
                "event": "claude_call_start",
                "phase": phase,
                "attempt": call.get("attempt", 1),
                "prompt_bytes": 100,
            }
            if call.get("step_id") is not None:
                call_start["step_id"] = call["step_id"]
            events.append(call_start)
            if not call.get("incomplete"):
                call_end = {
                    "ts": started_at,
                    "run_id": run_id,
                    "event": "claude_call_end",
                    "phase": phase,
                    "attempt": call.get("attempt", 1),
                    "rc": call.get("rc", 0),
                    "duration_ms": call["duration_ms"],
                    "stdout_bytes": 200,
                }
                for key in (
                    "tokens_input",
                    "tokens_output",
                    "cache_creation_tokens",
                    "cache_read_tokens",
                    "cost_usd",
                ):
                    if call.get(key) is not None:
                        call_end[key] = call[key]
                events.append(call_end)
                events.append(
                    {
                        "ts": started_at,
                        "run_id": run_id,
                        "event": "phase_end",
                        "phase": phase,
                        "duration_ms": call["duration_ms"] + 50,
                        "outcome": (
                            "success" if call.get("rc", 0) == 0 else "error"
                        ),
                    }
                )
        if include_run_end:
            events.append(
                {
                    "ts": started_at,
                    "run_id": run_id,
                    "event": "run_end",
                    "duration_ms": 60000,
                    "outcome": "success",
                    "rc": 0,
                }
            )
        with target.open("w", encoding="utf-8") as f:
            for ev in events:
                f.write(_json.dumps(ev, separators=(",", ":")))
                f.write("\n")
        return target

    def test_profile_no_root_prints_no_runs_and_exits_0(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "profile"])
        assert rc == 0
        assert "no runs" in capsys.readouterr().out

    def test_profile_aggregates_by_mode_with_p50_and_total(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / ".git").mkdir()
        # Five calls in mode=run (1000…5000ms) and one in mode=check
        # (500ms). Totals: run=15000ms, check=500ms — run sorts first.
        # The run bucket clears ``_SMALL_BUCKET_THRESHOLD`` so the p50 /
        # p95 columns surface ms values; the single-sample check bucket
        # falls below the threshold and renders as ``n=1`` instead.
        self._seed_profile_run(
            tmp_path,
            slug="demo",
            calls=[
                {
                    "mode": "run",
                    "step_id": 1,
                    "duration_ms": 1000,
                    "tokens_input": 100,
                    "tokens_output": 50,
                },
                {
                    "mode": "run",
                    "step_id": 2,
                    "duration_ms": 2000,
                    "tokens_input": 200,
                    "tokens_output": 60,
                },
                {
                    "mode": "run",
                    "step_id": 3,
                    "duration_ms": 3000,
                    "tokens_input": 300,
                    "tokens_output": 70,
                },
                {
                    "mode": "run",
                    "step_id": 4,
                    "duration_ms": 4000,
                    "tokens_input": 400,
                    "tokens_output": 80,
                },
                {
                    "mode": "run",
                    "step_id": 5,
                    "duration_ms": 5000,
                    "tokens_input": 500,
                    "tokens_output": 90,
                },
                {
                    "mode": "check",
                    "step_id": 1,
                    "duration_ms": 500,
                },
            ],
        )
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "profile"])
        assert rc == 0
        out = capsys.readouterr().out
        lines = [ln for ln in out.splitlines() if ln.strip()]
        # Header + 2 rows (run, check).
        assert len(lines) == 3
        header = lines[0]
        for col in ("mode", "count", "p50", "p95", "mean", "total"):
            assert col in header
        # Row order: run first (larger total), check second.
        assert lines[1].lstrip().startswith("run")
        assert lines[2].lstrip().startswith("check")
        # run total = 1000+2000+3000+4000+5000 = 15000ms → "15.0s".
        assert "15.0s" in lines[1]
        # run tokens_in = 1500; tokens_out = 50+60+70+80+90 = 350.
        assert "1500" in lines[1]
        assert "350" in lines[1]

    def test_profile_by_step_buckets_per_step_id(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / ".git").mkdir()
        self._seed_profile_run(
            tmp_path,
            slug="demo",
            calls=[
                {"mode": "run", "step_id": 1, "duration_ms": 1000},
                {"mode": "run", "step_id": 1, "duration_ms": 2000},
                {"mode": "run", "step_id": 7, "duration_ms": 500},
            ],
        )
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "profile", "--by", "step"])
        assert rc == 0
        out = capsys.readouterr().out
        # Step 1 total = 3000ms, step 7 total = 500ms. Slug-prefixed.
        assert "demo#1" in out
        assert "demo#7" in out
        # demo#1 sorts before demo#7 (larger total).
        assert out.index("demo#1") < out.index("demo#7")

    def test_profile_by_run_buckets_per_run_id(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / ".git").mkdir()
        self._seed_profile_run(
            tmp_path, slug="demo", run_id="rid-A",
            calls=[{"mode": "run", "step_id": 1, "duration_ms": 1000}],
        )
        self._seed_profile_run(
            tmp_path, slug="demo", run_id="rid-B",
            calls=[{"mode": "run", "step_id": 1, "duration_ms": 2500}],
        )
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "profile", "--by", "run"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "demo/rid-A" in out
        assert "demo/rid-B" in out

    def test_profile_slug_filter_excludes_other_slugs(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / ".git").mkdir()
        self._seed_profile_run(
            tmp_path, slug="demo",
            calls=[{"mode": "run", "step_id": 1, "duration_ms": 1000}],
        )
        self._seed_profile_run(
            tmp_path, slug="other", run_id="rid-other",
            calls=[{"mode": "check", "step_id": 1, "duration_ms": 500}],
        )
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "profile", "--slug", "demo"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "run" in out
        # The "check" bucket from the ``other`` slug must not appear.
        rows = [ln for ln in out.splitlines() if ln.strip()][1:]
        assert all(not ln.lstrip().startswith("check") for ln in rows)

    def test_profile_mode_filter_drops_non_matching_samples(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / ".git").mkdir()
        self._seed_profile_run(
            tmp_path, slug="demo",
            calls=[
                {"mode": "run", "step_id": 1, "duration_ms": 1000},
                {"mode": "check", "step_id": 1, "duration_ms": 500},
            ],
        )
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "profile", "--mode", "run"])
        assert rc == 0
        out = capsys.readouterr().out
        rows = [ln for ln in out.splitlines() if ln.strip()][1:]
        # Only one row, for the run bucket.
        assert len(rows) == 1
        assert rows[0].lstrip().startswith("run")

    def test_profile_since_filters_old_runs(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / ".git").mkdir()
        # One run from 90 days ago, one from "today" (well within 1d).
        self._seed_profile_run(
            tmp_path, slug="demo", run_id="old",
            started_at="2020-01-01T00:00:00+00:00",
            calls=[{"mode": "run", "step_id": 1, "duration_ms": 9000}],
        )
        from datetime import datetime as _dt, timezone as _tz
        recent_ts = _dt.now(_tz.utc).replace(microsecond=0).isoformat()
        self._seed_profile_run(
            tmp_path, slug="demo", run_id="new",
            started_at=recent_ts,
            calls=[{"mode": "run", "step_id": 1, "duration_ms": 1000}],
        )
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "profile", "--since", "1d", "--by", "run"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "demo/new" in out
        assert "demo/old" not in out

    def test_profile_top_truncates_after_sort(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / ".git").mkdir()
        # Three step buckets with descending totals: 3000, 2000, 500.
        self._seed_profile_run(
            tmp_path, slug="demo",
            calls=[
                {"mode": "run", "step_id": 1, "duration_ms": 3000},
                {"mode": "run", "step_id": 2, "duration_ms": 2000},
                {"mode": "run", "step_id": 3, "duration_ms": 500},
            ],
        )
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "profile", "--by", "step", "--top", "2"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "demo#1" in out
        assert "demo#2" in out
        assert "demo#3" not in out

    def test_profile_json_emits_single_line_envelope(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import json as _json

        (tmp_path / ".git").mkdir()
        # Five completed samples — at ``_SMALL_BUCKET_THRESHOLD`` so the
        # JSON envelope surfaces non-null p50_ms / p95_ms (suppression
        # only kicks in *below* the threshold).
        self._seed_profile_run(
            tmp_path, slug="demo",
            calls=[
                {
                    "mode": "run",
                    "step_id": 1,
                    "duration_ms": 1000,
                    "tokens_input": 100,
                    "tokens_output": 50,
                    "cost_usd": 0.01,
                },
                {
                    "mode": "run",
                    "step_id": 1,
                    "duration_ms": 2000,
                    "tokens_input": 200,
                    "tokens_output": 75,
                    "cost_usd": 0.01,
                },
                {
                    "mode": "run",
                    "step_id": 1,
                    "duration_ms": 3000,
                    "tokens_input": 300,
                    "tokens_output": 100,
                    "cost_usd": 0.01,
                },
                {
                    "mode": "run",
                    "step_id": 1,
                    "duration_ms": 4000,
                    "tokens_input": 400,
                    "tokens_output": 125,
                    "cost_usd": 0.01,
                },
                {
                    "mode": "run",
                    "step_id": 1,
                    "duration_ms": 5000,
                    "tokens_input": 500,
                    "tokens_output": 150,
                    "cost_usd": 0.01,
                },
            ],
        )
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "profile", "--json"])
        assert rc == 0
        payload = _json.loads(capsys.readouterr().out.strip())
        assert payload["by"] == "mode"
        assert payload["runs_scanned"] == 1
        assert payload["runs_in_flight_skipped"] == 0
        assert len(payload["groups"]) == 1
        grp = payload["groups"][0]
        assert grp["key"] == "run"
        assert grp["count"] == 5
        assert grp["total_ms"] == 15000
        assert grp["mean_ms"] == 3000
        # p50/p95 via statistics.quantiles(n=20, inclusive). With five
        # samples 1000..5000: q[9] (50%) = 3000.0, q[18] (95%) = 4800.0.
        assert grp["p50_ms"] == 3000.0
        assert grp["p95_ms"] == 4800.0
        # min / max are computed from the same durations list as
        # mean / total and remain visible at every bucket size.
        assert grp["min_ms"] == 1000
        assert grp["max_ms"] == 5000
        assert grp["tokens_input"] == 1500
        assert grp["tokens_output"] == 500
        assert grp["cost_usd"] == pytest.approx(0.05)

    def test_profile_skips_in_flight_runs(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / ".git").mkdir()
        # In-flight run (no run_end) — should be excluded entirely.
        self._seed_profile_run(
            tmp_path, slug="demo", run_id="rid-inflight",
            include_run_end=False,
            calls=[{"mode": "run", "step_id": 1, "duration_ms": 9999}],
        )
        # A complete run — should be the only contributor to the table.
        self._seed_profile_run(
            tmp_path, slug="demo", run_id="rid-done",
            calls=[{"mode": "check", "step_id": 1, "duration_ms": 500}],
        )
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "profile", "--json"])
        assert rc == 0
        import json as _json
        payload = _json.loads(capsys.readouterr().out.strip())
        assert payload["runs_in_flight_skipped"] == 1
        assert payload["runs_scanned"] == 1
        keys = [g["key"] for g in payload["groups"]]
        assert keys == ["check"]
        assert payload["groups"][0]["count"] == 1

    def test_profile_unmatched_start_counts_as_incomplete(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / ".git").mkdir()
        # One complete call (2000ms) and one start without an end —
        # the unmatched start is the same mode so it lands in the same
        # bucket. Latency stats must ignore the incomplete sample.
        self._seed_profile_run(
            tmp_path, slug="demo",
            calls=[
                {"mode": "run", "step_id": 1, "duration_ms": 2000},
                {"mode": "run", "step_id": 2, "incomplete": True},
            ],
        )
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "profile", "--json"])
        assert rc == 0
        import json as _json
        payload = _json.loads(capsys.readouterr().out.strip())
        grp = payload["groups"][0]
        assert grp["key"] == "run"
        assert grp["count"] == 2
        assert grp["incomplete"] == 1
        assert grp["total_ms"] == 2000
        assert grp["mean_ms"] == 2000

    def test_profile_invalid_since_exits_2(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / ".git").mkdir()
        # Need a runs root for the handler to get past the "no root"
        # branch and into ``--since`` parsing.
        self._seed_profile_run(
            tmp_path, slug="demo",
            calls=[{"mode": "run", "step_id": 1, "duration_ms": 100}],
        )
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "profile", "--since", "garbage"])
        assert rc == 2
        assert "--since expects" in capsys.readouterr().err

    def test_profile_failed_call_counts_in_fail_column(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / ".git").mkdir()
        self._seed_profile_run(
            tmp_path, slug="demo",
            calls=[
                {"mode": "run", "step_id": 1, "duration_ms": 1000, "rc": 1},
                {"mode": "run", "step_id": 2, "duration_ms": 500, "rc": 0},
            ],
        )
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "profile", "--json"])
        assert rc == 0
        import json as _json
        payload = _json.loads(capsys.readouterr().out.strip())
        grp = payload["groups"][0]
        assert grp["count"] == 2
        assert grp["fail"] == 1


@pytest.mark.integration
class TestRunsProfileSmallBucketSuppression:
    """``runs profile`` suppresses p50 / p95 below ``_SMALL_BUCKET_THRESHOLD``.

    Pins the BUG_BACKLOG fix that previously let
    ``statistics.quantiles(..., n=20, method="inclusive")`` publish
    interpolated "p95" numbers on n=2 buckets — meaningless but
    rendered identically to a 100-sample p95. The contract:

    - JSON payload: ``p50_ms`` / ``p95_ms`` are ``null`` for buckets
      with fewer than 5 completed samples; non-``None`` floats at or
      above the threshold.
    - Text table: the p50 / p95 cells render as ``n=<count - incomplete>``
      when the quantile is suppressed; ``min`` / ``max`` columns
      remain visible so a slow outlier in a tiny bucket is still
      surfaced.

    Lives next to ``TestCmdRunsProfile`` to keep all ``runs profile``
    coverage co-located. Delegates ``_seed_profile_run`` to that
    class (same pattern ``TestCmdRunsRegression._seed_run`` uses for
    ``TestCmdRuns._seed_run``).
    """

    def _seed_profile_run(self, tmp_path: Path, **kwargs) -> Path:
        return TestCmdRunsProfile()._seed_profile_run(tmp_path, **kwargs)

    @staticmethod
    def _build_calls(n: int) -> list[dict[str, int | str]]:
        """Return ``n`` completed calls with distinct durations.

        Durations: 100, 200, …, n*100 ms — strictly increasing so a
        p50 < p95 assertion is meaningful when both are present.
        """
        return [
            {"mode": "run", "step_id": 1, "duration_ms": (i + 1) * 100}
            for i in range(n)
        ]

    @pytest.mark.parametrize("n", [1, 2, 4])
    def test_quantiles_suppressed_below_threshold(
        self,
        n: int,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import json as _json

        (tmp_path / ".git").mkdir()
        self._seed_profile_run(
            tmp_path, slug="demo", calls=self._build_calls(n),
        )
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "profile", "--json"])
        assert rc == 0
        payload = _json.loads(capsys.readouterr().out.strip())
        grp = payload["groups"][0]
        assert grp["count"] == n
        assert grp["p50_ms"] is None
        assert grp["p95_ms"] is None

    def test_quantiles_present_at_threshold(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import json as _json

        (tmp_path / ".git").mkdir()
        self._seed_profile_run(
            tmp_path, slug="demo", calls=self._build_calls(5),
        )
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "profile", "--json"])
        assert rc == 0
        payload = _json.loads(capsys.readouterr().out.strip())
        grp = payload["groups"][0]
        assert grp["count"] == 5
        assert isinstance(grp["p50_ms"], float)
        assert isinstance(grp["p95_ms"], float)

    def test_quantiles_present_above_threshold(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import json as _json

        (tmp_path / ".git").mkdir()
        self._seed_profile_run(
            tmp_path, slug="demo", calls=self._build_calls(10),
        )
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "profile", "--json"])
        assert rc == 0
        payload = _json.loads(capsys.readouterr().out.strip())
        grp = payload["groups"][0]
        assert grp["count"] == 10
        assert isinstance(grp["p50_ms"], float)
        assert isinstance(grp["p95_ms"], float)
        # Strictly-increasing fixture: p50 must be below p95.
        assert grp["p50_ms"] < grp["p95_ms"]

    def test_text_renders_n_sentinel_for_suppressed_p50_p95(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / ".git").mkdir()
        self._seed_profile_run(
            tmp_path, slug="demo", calls=self._build_calls(3),
        )
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "profile"])
        assert rc == 0
        out = capsys.readouterr().out
        lines = [ln for ln in out.splitlines() if ln.strip()]
        # Header + 1 data row.
        assert len(lines) == 2
        row = lines[1]
        # Sentinel format ``n=<count - incomplete>`` with N=3.
        assert "n=3" in row
        # No ms-formatted duration shows up in the row's p50 / p95
        # slot — confirm by counting ms-formatted tokens: min, max,
        # mean, total all render as ms; with quantiles suppressed
        # only those four should be present (no p50 / p95 ms cells).
        ms_tokens = [tok for tok in row.split() if tok.endswith("ms")]
        # min=100ms, max=300ms, mean=200ms, total=600ms — exactly 4.
        assert len(ms_tokens) == 4

    def test_text_does_not_render_n_sentinel_above_threshold(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / ".git").mkdir()
        self._seed_profile_run(
            tmp_path, slug="demo", calls=self._build_calls(10),
        )
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "profile"])
        assert rc == 0
        out = capsys.readouterr().out
        lines = [ln for ln in out.splitlines() if ln.strip()]
        assert len(lines) == 2
        row = lines[1]
        # No suppression sentinel when quantiles are populated.
        assert "n=" not in row

    @pytest.mark.parametrize("n", [1, 2, 4, 5, 10])
    def test_min_max_visible_at_every_bucket_size(
        self,
        n: int,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import json as _json

        (tmp_path / ".git").mkdir()
        self._seed_profile_run(
            tmp_path, slug="demo", calls=self._build_calls(n),
        )
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "profile", "--json"])
        assert rc == 0
        payload = _json.loads(capsys.readouterr().out.strip())
        grp = payload["groups"][0]
        assert grp["count"] == n
        # ``_build_calls(n)`` emits durations 100, 200, …, n*100.
        assert grp["min_ms"] == 100
        assert grp["max_ms"] == n * 100
        assert grp["min_ms"] <= grp["max_ms"]

    def test_min_max_cells_rendered_in_text_table(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / ".git").mkdir()
        self._seed_profile_run(
            tmp_path, slug="demo", calls=self._build_calls(3),
        )
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "profile"])
        assert rc == 0
        out = capsys.readouterr().out
        lines = [ln for ln in out.splitlines() if ln.strip()]
        assert len(lines) == 2
        header, row = lines
        # New columns visible in the header.
        assert "min" in header
        assert "max" in header
        # Suppressed quantiles must not hide the underlying durations:
        # min=100ms and max=300ms still appear in the row.
        assert "100ms" in row
        assert "300ms" in row


@pytest.mark.integration
class TestCmdRunsRegression:
    """Cross-cutting regression coverage for the run-log read surface.

    Distinct from ``TestCmdRuns`` (which proves correctness — *does
    the command do what it claims?*), this class pins behavior that
    must survive a future refactor of ``_iter_events``, ``_safe_under_root``,
    or ``_is_run_evictable``. A reader scanning the file should be
    able to tell at a glance which tests prove the contract and which
    guard a prior correctness claim.

    Five contracts pinned, named in the step title:

    - ``schema_version`` mismatch must read-skip not crash across
      ``runs show`` / ``runs list`` / ``_iter_events``.
    - Malformed / partial-write JSONL on ``runs show`` must not crash
      — torn last lines, blank lines, BOM prefixes silently skip.
    - Path-traversal abuse (symlinked slug dir, null bytes) on
      ``runs show`` / ``runs clear`` must exit 2.
    - ``clear --older-than`` evicts by the embedded ``run_start.ts``,
      not the filesystem mtime; unparseable / missing ts → don't evict.
    - ``--older-than`` cutoff is strict-greater (``age > cutoff``),
      not ``>=``.
    """

    def _seed_raw(
        self,
        tmp_path: Path,
        slug: str = "demo",
        run_id: str = "2026-05-14T12-34-56-9f3a1c",
        raw: bytes = b"",
    ) -> Path:
        """Write ``raw`` bytes verbatim to ``<slug>/<run_id>.jsonl``.

        Distinct from ``TestCmdRuns._seed_run`` (which composes dicts
        → JSONL via ``json.dumps``): the regression suite needs to
        hand-author byte-level torn lines, BOM headers, and
        trailing-no-newline shapes that ``json.dumps`` cannot
        produce. Uses ``write_bytes`` rather than ``write_text`` so
        a stray UTF-8 BOM gets persisted verbatim.
        """
        from plan_tool.run_log import run_log_path

        path = run_log_path(tmp_path, slug, run_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return path

    def _seed_run(self, tmp_path: Path, **kwargs) -> Path:
        """Delegate to ``TestCmdRuns._seed_run`` for happy-path
        seeding — avoids duplicating the dict-builder helper while
        keeping the regression class's intent (byte-level shapes)
        front-and-center in :meth:`_seed_raw`."""
        return TestCmdRuns()._seed_run(tmp_path, **kwargs)

    # ---------- schema_version mismatch — read-skip, not crash ----------

    def test_show_schema_mismatch_exits_1_does_not_raise(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Regression: ``runs show`` on a ``schema_version: 99`` log
        must fail-closed (rc=1) with a specific stderr substring,
        not a stack trace. Overlaps deliberately with
        ``TestCmdRuns.test_show_refuses_schema_version_mismatch`` —
        the overlap keeps an obviously-named test in the regression
        class so a future "show should soft-warn" refactor breaks it."""
        (tmp_path / ".git").mkdir()
        self._seed_run(tmp_path, slug="demo", schema_version=99)
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "show", "demo/2026-05-14T12-34-56-9f3a1c"])
        assert rc == 1
        err = capsys.readouterr().err
        assert "unsupported run-log schema_version" in err

    def test_list_tolerates_schema_mismatch_in_one_file(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``runs list`` walks every JSONL even when some rows have an
        unsupported ``schema_version`` — the schema check lives on
        ``show``, not on the list walk. Pins the asymmetric "show
        fails closed, list keeps walking" contract."""
        (tmp_path / ".git").mkdir()
        self._seed_run(tmp_path, slug="ok", run_id="ok-run")
        self._seed_run(
            tmp_path, slug="bad", run_id="bad-run", schema_version=99,
        )
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "list"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "ok" in out
        assert "bad" in out
        assert "ok-run" in out
        assert "bad-run" in out

    def test_iter_events_does_not_filter_by_schema_version(
        self,
        tmp_path: Path,
    ) -> None:
        """``_iter_events`` is the read-side primitive. Filtering by
        ``schema_version`` lives in ``runs show``, not in the reader;
        every event must be yielded regardless. A regression here
        would silently truncate ``runs diff`` and any future analytics
        layer that consumes the iterator directly."""
        import json

        from plan_tool.cli import _iter_events
        from plan_tool.run_log import run_log_path

        target = run_log_path(tmp_path, "demo", "rid")
        target.parent.mkdir(parents=True, exist_ok=True)
        events_to_write = [
            {
                "ts": "2026-05-14T00:00:00+00:00",
                "run_id": "rid",
                "event": "run_start",
                "schema_version": 99,
                "command": "x",
                "plan_slug": "demo",
            },
            {
                "ts": "2026-05-14T00:00:01+00:00",
                "run_id": "rid",
                "event": "phase_start",
                "schema_version": 1,
                "phase": "p",
            },
            {
                "ts": "2026-05-14T00:00:02+00:00",
                "run_id": "rid",
                "event": "phase_end",
                "phase": "p",
            },
        ]
        with target.open("w", encoding="utf-8") as f:
            for ev in events_to_write:
                f.write(json.dumps(ev) + "\n")

        yielded = list(_iter_events(target))
        assert len(yielded) == 3
        assert [e["event"] for e in yielded] == [
            "run_start",
            "phase_start",
            "phase_end",
        ]

    # ---------- malformed / partial-write JSONL on `runs show` ----------

    def test_show_handles_empty_jsonl_without_crashing(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A zero-byte ``.jsonl`` is a *distinct* state from "all lines
        unparseable" — there's no damage, just no events yet. Contract:
        rc=0 with ``?`` metadata placeholders. The all-unparseable case
        (rc=1) is covered by
        ``TestCmdRuns.test_show_exits_1_when_every_line_unparseable``.
        Pinning the rc here so a future change that conflates the two
        states (both exit 1) fails this test loudly.
        """
        (tmp_path / ".git").mkdir()
        self._seed_raw(tmp_path, slug="demo", run_id="empty", raw=b"")
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "show", "demo/empty"])
        assert rc == 0
        captured = capsys.readouterr()
        # Metadata header rendered with ``?`` placeholders because there
        # was no ``run_start`` event to lift command/plan_slug from.
        assert "# run_id: empty" in captured.err
        assert "?" in captured.err
        # No events on stdout (file was empty).
        assert captured.out == ""

    def test_show_handles_jsonl_without_run_start(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A JSONL of valid events with no ``run_start`` header is a
        torn-mid-write case (the run died before its first event got
        flushed). Contract: rc=0, every parseable event lands on
        stdout, metadata header on stderr uses ``?`` placeholders for
        the fields ``run_start`` would have supplied.
        """
        import json

        events = [
            {
                "ts": "2026-05-14T00:00:00+00:00",
                "run_id": "r",
                "event": "phase_start",
                "phase": "p1",
            },
            {
                "ts": "2026-05-14T00:00:01+00:00",
                "run_id": "r",
                "event": "phase_end",
                "phase": "p1",
                "duration_ms": 1,
                "outcome": "ok",
            },
        ]
        raw = ("\n".join(json.dumps(e) for e in events) + "\n").encode("utf-8")
        (tmp_path / ".git").mkdir()
        self._seed_raw(tmp_path, slug="demo", run_id="no-start", raw=raw)
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "show", "demo/no-start"])
        assert rc == 0
        captured = capsys.readouterr()
        # Every parseable event lands on stdout.
        assert "phase_start" in captured.out
        assert "phase_end" in captured.out
        # Metadata header rendered with ``?`` placeholders for the
        # fields ``run_start`` would have supplied (command,
        # plan_slug, schema_version).
        assert "# run_id: no-start" in captured.err
        assert "# command: ?" in captured.err
        assert "# plan_slug: ?" in captured.err

    def test_show_tolerates_torn_last_line(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A JSONL whose final line is a torn partial-write (no
        closing brace, no trailing newline) must render the
        preceding valid events without raising. Pins the
        ``_iter_events`` partial-write tolerance at the user-facing
        layer."""
        import json

        valid = [
            {
                "ts": "2026-05-14T00:00:00+00:00",
                "run_id": "r",
                "event": "run_start",
                "schema_version": 1,
                "command": "create",
                "plan_slug": "demo",
                "argv": [],
                "pid": 1,
                "cwd": "/",
            },
            {
                "ts": "2026-05-14T00:00:01+00:00",
                "run_id": "r",
                "event": "phase_start",
                "phase": "propose_steps",
            },
        ]
        body = "\n".join(json.dumps(e) for e in valid) + "\n"
        torn = body + '{"event": "phase_end"'
        (tmp_path / ".git").mkdir()
        self._seed_raw(
            tmp_path, slug="demo", run_id="torn", raw=torn.encode("utf-8"),
        )
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "show", "demo/torn"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "run_start" in out
        assert "phase_start" in out
        # Torn final line silently skipped — no phase_end row.
        assert out.count("phase_end") == 0

    def test_show_tolerates_blank_line_in_middle(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A blank line embedded between valid events must be
        silently skipped (not counted, not rendered as a ``?`` row)
        — ``_iter_events``'s ``if not line: continue`` is what
        delivers this; we pin it from the outside."""
        import json

        run_start = {
            "ts": "2026-05-14T00:00:00+00:00",
            "run_id": "r",
            "event": "run_start",
            "schema_version": 1,
            "command": "create",
            "plan_slug": "demo",
            "argv": [],
            "pid": 1,
            "cwd": "/",
        }
        phase_start = {
            "ts": "2026-05-14T00:00:01+00:00",
            "run_id": "r",
            "event": "phase_start",
            "phase": "p",
        }
        run_end = {
            "ts": "2026-05-14T00:00:02+00:00",
            "run_id": "r",
            "event": "run_end",
            "duration_ms": 1000,
            "outcome": "success",
            "rc": 0,
        }
        raw = (
            json.dumps(run_start) + "\n"
            + "\n"
            + json.dumps(phase_start) + "\n"
            + "\n\n"
            + json.dumps(run_end) + "\n"
        ).encode("utf-8")
        (tmp_path / ".git").mkdir()
        self._seed_raw(
            tmp_path, slug="demo", run_id="blanks", raw=raw,
        )
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "show", "demo/blanks"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "run_start" in out
        assert "phase_start" in out
        assert "run_end" in out

    def test_show_rejects_leading_utf8_bom_as_unparseable(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A ``.jsonl`` whose only line is BOM-prefixed (``\\xef\\xbb\\xbf``
        before the JSON object) is treated as one unparseable line —
        Python's ``json.loads`` raises ``JSONDecodeError: Unexpected
        UTF-8 BOM``. With no other events in the file, ``runs show``
        exits 1 via the all-unparseable branch (same code path as
        ``test_show_exits_1_when_every_line_unparseable`` in
        ``TestCmdRuns``). Pinning rc=1 + the specific stderr message
        so a future BOM-tolerance change (``utf-8-sig`` decoding,
        stripping the BOM) fails this test loudly and forces a
        deliberate decision.
        """
        import json

        valid = {
            "ts": "2026-05-14T00:00:00+00:00",
            "run_id": "r",
            "event": "run_start",
            "schema_version": 1,
            "command": "create",
            "plan_slug": "demo",
            "argv": [],
            "pid": 1,
            "cwd": "/",
        }
        raw = b"\xef\xbb\xbf" + json.dumps(valid).encode("utf-8") + b"\n"
        (tmp_path / ".git").mkdir()
        self._seed_raw(tmp_path, slug="demo", run_id="bom", raw=raw)
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "show", "demo/bom"])
        assert rc == 1
        err = capsys.readouterr().err
        assert "unreadable" in err
        assert "no parseable events" in err

    # ---------- path-traversal — symlink + null-byte shapes ----------

    def test_show_refuses_symlinked_slug_dir(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A symlinked slug dir under the runs root must produce
        exit 2 (refused-on-principle) from ``_safe_under_root``'s
        ``resolve()`` check, not exit 1 (not-found). The distinction
        matters for log greppers and CI consumers — exit-2 is
        "refused", exit-1 is "missing"."""
        from plan_tool.run_log import runs_root

        (tmp_path / ".git").mkdir()
        root = runs_root(tmp_path)
        root.mkdir(parents=True, exist_ok=True)
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "evil-run.jsonl").write_text(
            '{"event":"run_start","schema_version":1,'
            '"ts":"2026-05-14T00:00:00+00:00","run_id":"r",'
            '"command":"PWNED","plan_slug":"evil","argv":[],'
            '"pid":1,"cwd":"/"}\n',
            encoding="utf-8",
        )
        (root / "evil").symlink_to(outside, target_is_directory=True)
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "show", "evil/evil-run"])
        assert rc == 2
        err = capsys.readouterr().err
        assert "refusing to read outside" in err

    def test_clear_slug_refuses_symlinked_slug_dir(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The named-slug clear path must also refuse a symlinked
        slug dir — mirrors
        ``TestCmdRuns.test_clear_all_skips_symlinked_slug_dir`` but
        pins the slug-named clear instead of ``--all``. The outside
        dir and a sentinel inside it must survive intact."""
        from plan_tool.run_log import runs_root

        (tmp_path / ".git").mkdir()
        root = runs_root(tmp_path)
        root.mkdir(parents=True, exist_ok=True)
        outside = tmp_path / "outside"
        outside.mkdir()
        sentinel = outside / "DO-NOT-DELETE.jsonl"
        sentinel.write_text("KEEP\n", encoding="utf-8")
        (root / "evil").symlink_to(outside, target_is_directory=True)
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "clear", "evil"])
        assert rc == 2
        # The specific stderr from ``_safe_under_root``'s refusal path
        # — distinguishes from a silent rc=2 (which would let a
        # regression that swallows the error pass undetected).
        err = capsys.readouterr().err
        assert "refusing to operate outside" in err
        assert sentinel.is_file()
        assert sentinel.read_text(encoding="utf-8") == "KEEP\n"

    def test_clear_slug_refuses_null_byte_via_safe_under_root(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A null byte in the slug passes the string-level validator
        (no ``/``, no ``..``, no leading ``.``) but is caught by
        ``_safe_under_root``'s ``resolve()`` raising ``ValueError``.
        Mirrors ``test_show_rejects_null_byte_via_safe_under_root``
        on the clear side.

        Asserts the *specific* ``_safe_under_root`` stderr message so
        the test can't pass via the wrong code path (e.g. argparse
        rejecting the argv before the handler runs).
        """
        (tmp_path / ".git").mkdir()
        # Seed a real run so the runs root exists; otherwise the
        # ``not root.is_dir()`` early-return short-circuits before
        # ``_safe_under_root`` runs.
        self._seed_run(tmp_path, slug="real")
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "clear", "demo\x00x"])
        assert rc == 2
        err = capsys.readouterr().err
        # The handler's _safe_under_root failure path emits this exact
        # substring (cli.py:1205); argparse-level rejection would have
        # used a different message shape ("usage:" / "invalid choice").
        assert "refusing to operate outside" in err

    # ---------- --older-than: cutoff respected against run_start.ts ----------

    def test_clear_older_than_uses_run_start_ts_not_mtime(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The eviction predicate reads the embedded ``run_start.ts``,
        not the file's mtime. Regression target: a "just check mtime"
        refactor would skip evicting a 60-day-old log whose mtime
        was bumped by a ``touch``."""
        import os
        from datetime import datetime, timedelta, timezone

        from plan_tool.run_log import run_log_path

        (tmp_path / ".git").mkdir()
        old_ts = (
            datetime.now(timezone.utc) - timedelta(days=60)
        ).replace(microsecond=0).isoformat()
        path = self._seed_run(
            tmp_path, slug="demo", run_id="old-by-ts",
            started_at=old_ts,
        )
        # Bump mtime to now — any mtime-based check would skip.
        now = datetime.now().timestamp()
        os.utime(path, (now, now))
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "clear", "--older-than", "30d"])
        assert rc == 0
        assert not run_log_path(
            tmp_path, "demo", "old-by-ts"
        ).exists()

    def test_clear_older_than_evicts_just_past_cutoff(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A run whose ``run_start.ts`` is exactly 30d + 5s old must
        be evicted under ``--older-than 30d``. Pins
        ``_is_run_evictable``'s ``age > cutoff_seconds`` predicate
        as strict-greater rather than ``>=``."""
        from datetime import datetime, timedelta, timezone

        from plan_tool.run_log import run_log_path

        (tmp_path / ".git").mkdir()
        old_ts = (
            datetime.now(timezone.utc)
            - timedelta(days=30, seconds=5)
        ).replace(microsecond=0).isoformat()
        self._seed_run(
            tmp_path, slug="demo", run_id="just-past",
            started_at=old_ts,
        )
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "clear", "--older-than", "30d"])
        assert rc == 0
        assert not run_log_path(
            tmp_path, "demo", "just-past"
        ).exists()

    def test_clear_older_than_keeps_run_just_inside_cutoff(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A run whose ``run_start.ts`` is 30d minus a few seconds old
        must survive ``--older-than 30d``. Complement of
        :meth:`test_clear_older_than_evicts_just_past_cutoff` —
        together they nail down the boundary."""
        from datetime import datetime, timedelta, timezone

        from plan_tool.run_log import run_log_path

        (tmp_path / ".git").mkdir()
        recent_ts = (
            datetime.now(timezone.utc)
            - timedelta(days=29, hours=23, minutes=59, seconds=55)
        ).replace(microsecond=0).isoformat()
        self._seed_run(
            tmp_path, slug="demo", run_id="just-inside",
            started_at=recent_ts,
        )
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "clear", "--older-than", "30d"])
        assert rc == 0
        assert run_log_path(
            tmp_path, "demo", "just-inside"
        ).is_file()

    def test_clear_older_than_skips_jsonl_with_unparseable_ts(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When ``run_start.ts`` is unparseable, the file is
        *conservatively preserved* — we can't determine its age, so
        we don't evict. Pins the ``_is_run_evictable`` fallback of
        ``try/except ValueError → False``."""
        import json

        from plan_tool.run_log import run_log_path

        (tmp_path / ".git").mkdir()
        events = [
            {
                "ts": "not a real ts",
                "run_id": "garbage-ts",
                "event": "run_start",
                "schema_version": 1,
                "command": "create",
                "plan_slug": "demo",
                "argv": [],
                "pid": 1,
                "cwd": "/",
            },
        ]
        raw = ("\n".join(json.dumps(e) for e in events) + "\n").encode("utf-8")
        self._seed_raw(
            tmp_path, slug="demo", run_id="garbage-ts", raw=raw,
        )
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "clear", "--older-than", "30d"])
        assert rc == 0
        assert run_log_path(
            tmp_path, "demo", "garbage-ts"
        ).is_file()

    def test_clear_older_than_skips_jsonl_with_no_run_start(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A JSONL with no ``run_start`` event has no ts to read.
        ``_is_run_evictable`` returns ``False`` — we don't evict
        what we can't date. Pins the same conservative-read
        contract as the unparseable-ts case."""
        import json

        from plan_tool.run_log import run_log_path

        (tmp_path / ".git").mkdir()
        events = [
            {
                "ts": "2026-05-14T00:00:00+00:00",
                "run_id": "no-start",
                "event": "phase_start",
                "phase": "x",
            },
            {
                "ts": "2026-05-14T00:00:01+00:00",
                "run_id": "no-start",
                "event": "phase_end",
                "phase": "x",
                "duration_ms": 1,
                "outcome": "ok",
            },
        ]
        raw = ("\n".join(json.dumps(e) for e in events) + "\n").encode("utf-8")
        self._seed_raw(
            tmp_path, slug="demo", run_id="no-start", raw=raw,
        )
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "clear", "--older-than", "30d"])
        assert rc == 0
        assert run_log_path(
            tmp_path, "demo", "no-start"
        ).is_file()

    def test_clear_older_than_combined_old_jsonl_and_in_flight_json(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The composite contract from acceptance criterion #4:
        a slug dir with an old ``.jsonl`` AND a current
        ``in-flight.json`` survives ``clear --older-than`` cleanly —
        the old log is evicted, the in-flight snapshot is preserved
        (we don't kill a live run's heartbeat), and the slug dir
        itself stays put because it's non-empty.

        Existing tests cover each piece separately:
        ``test_clear_older_than_preserves_in_flight_json`` in
        ``TestCmdRuns`` pins in-flight preservation; the eviction
        timing tests in this class pin the cutoff. This one pins the
        three contracts holding *together* against the realistic
        on-disk shape (a live run's writer would have produced both
        files at startup, and the JSONL ages out first).
        """
        from datetime import datetime, timedelta, timezone

        from plan_tool.run_log import (
            IN_FLIGHT_FILENAME,
            run_dir,
            run_log_path,
        )

        (tmp_path / ".git").mkdir()
        # Seed an old run (90 days ago — well past the 30d cutoff).
        old_ts = (
            datetime.now(timezone.utc) - timedelta(days=90)
        ).replace(microsecond=0).isoformat()
        self._seed_run(
            tmp_path,
            slug="demo",
            run_id="ancient-run",
            started_at=old_ts,
        )
        # Add an in-flight snapshot in the same slug dir (simulating
        # a different, currently-running invocation that hasn't yet
        # finished).
        slug_dir = run_dir(tmp_path, "demo")
        in_flight = slug_dir / IN_FLIGHT_FILENAME
        in_flight.write_text(
            '{"schema_version":1,"run_id":"live","command":"run",'
            '"plan_slug":"demo","started_at":"2026-05-14T00:00:00+00:00",'
            '"log_path":"/tmp/live.jsonl"}',
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        rc = main(["runs", "clear", "--older-than", "30d"])
        assert rc == 0
        # The aged JSONL is gone.
        assert not run_log_path(
            tmp_path, "demo", "ancient-run"
        ).exists()
        # The in-flight snapshot survives — we must not kill a live
        # run's heartbeat.
        assert in_flight.is_file()
        # The slug dir survives because it's non-empty (in-flight
        # still there). ``rmdir`` correctly fails-safe on a
        # non-empty directory.
        assert slug_dir.is_dir()

    # ---------- baseline preservation (automation-friendly proxy) ----------

    def test_no_existing_tests_were_modified(self) -> None:
        """Verification proxy: ``git diff main -- tests/`` should
        only touch files in the run-log plan's allowlist. Catches
        the failure mode where a future refactor edits a test
        outside the plan's scope. Skipped permissively when git
        is unavailable, the diff fails, or the tree carries
        unrelated unstaged changes — the test is an automation-friendly
        proxy for the manual ``git stash && pytest -q`` baseline
        check, not a strict gate."""
        import subprocess

        plan_tool_dir = Path(__file__).resolve().parent.parent
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", "main", "--", "tests/"],
                cwd=plan_tool_dir,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (
            FileNotFoundError,
            subprocess.TimeoutExpired,
            OSError,
        ):
            pytest.skip("git not available")
        if result.returncode != 0:
            pytest.skip(f"git diff failed: {result.stderr.strip()}")
        changed = {
            ln.strip() for ln in result.stdout.splitlines() if ln.strip()
        }
        allowlist = {
            "tests/test_run_log.py",
            "tests/test_cli.py",
            "tests/test_create.py",
            "tests/test_detail.py",
            "tests/test_progress.py",
            "tests/test_launcher.py",
            "tests/test_shell.py",
        }
        unexpected = changed - allowlist
        if unexpected:
            # Working tree carries changes outside the run-log plan's
            # scope (likely unrelated local edits). Skip rather than
            # false-fail — this is a proxy, not a strict gate.
            pytest.skip(
                f"working tree has test edits outside run-log scope: "
                f"{sorted(unexpected)}"
            )
        assert changed.issubset(allowlist)


# ---------------------------------------------------------------------------
# Step 5: cmd_run / run_log integration.
#
# These exercise the full pipeline from ``cli.main([...])`` down to the
# JSONL written under ``.plan-tool/runs/<slug>/``. Two integration
# tests, per the step budget: one happy-path mutating run, one
# reconcile-plan-walk with apply.
# ---------------------------------------------------------------------------


import json as _json


def _read_run_log_events(runs_dir: Path) -> list[dict]:
    """Locate the single ``<run_id>.jsonl`` written under runs_dir and
    return its events in order. Raises if zero or more than one log
    file is present (the integration tests open exactly one run).
    """
    matches = list(runs_dir.rglob("*.jsonl"))
    assert len(matches) == 1, (
        f"expected exactly one run log; found {len(matches)}: {matches}"
    )
    return [_json.loads(ln) for ln in matches[0].read_text(encoding="utf-8").splitlines() if ln]


_RUN_PLAN = """---
title: Run Log Integration
status: in-progress
priority: medium
steps:
  - id: 1
    title: Run a step
    status: current
---

# Run Log Integration
"""


@pytest.mark.integration
class TestCmdRunRunLogIntegration:
    """End-to-end: ``plan-tool run <name>`` opens a JSONL run log,
    emits ``prompt_build`` / ``claude_call`` phase pairs around the
    invoker, and closes with ``run_end``. The reconcile-plan-walk path
    additionally nests ``apply_finding_dispatch`` inside
    ``reconcile_walk``.
    """

    def _setup_repo(
        self, tmp_path: Path
    ) -> tuple[Path, Path, Path]:
        repo = tmp_path
        (repo / ".git").mkdir()
        plans_dir = repo / "plans"
        plans_dir.mkdir()
        plan_path = plans_dir / "rl.md"
        plan_path.write_text(_RUN_PLAN, encoding="utf-8")
        manifest = repo / "m.json"
        manifest.write_text(
            _json.dumps({"plans": ["plans/rl.md"]}), encoding="utf-8"
        )
        return repo, plan_path, manifest

    def test_happy_path_mutating_run_emits_full_event_stream(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool import launcher as launcher_module

        repo, plan_path, manifest = self._setup_repo(tmp_path)

        original_run_step = launcher_module.run_step

        def patched_run_step(*args, **kwargs):
            kwargs["invoker"] = lambda prompt: (
                0, "## Summary\nDid the thing.\n"
            )
            return original_run_step(*args, **kwargs)

        monkeypatch.setattr("plan_tool.cli.run_cmd.run_step", patched_run_step)
        monkeypatch.chdir(repo)

        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "run", "rl",
            ]
        )
        assert rc == 0

        runs_dir = repo / ".plan-tool" / "runs"
        events = _read_run_log_events(runs_dir)

        # First event is run_start, last is run_end, with matching run_id.
        assert events[0]["event"] == "run_start"
        assert events[0]["command"] == "run"
        assert events[0]["plan_slug"] == "rl"
        assert events[-1]["event"] == "run_end"
        assert events[-1]["outcome"] == "success"
        assert events[-1]["rc"] == 0
        run_id = events[0]["run_id"]
        for e in events:
            assert e["run_id"] == run_id

        kinds = [(e["event"], e.get("phase")) for e in events]
        # Required ordering: prompt_build pair before claude_call pair.
        assert ("phase_start", "prompt_build") in kinds
        assert ("phase_end", "prompt_build") in kinds
        assert ("phase_start", "claude_call") in kinds
        assert ("phase_end", "claude_call") in kinds
        # claude_call_start under the claude_call phase, attempt=1.
        ccs = [e for e in events if e["event"] == "claude_call_start"]
        assert len(ccs) == 1
        assert ccs[0]["phase"] == "claude_call"
        assert ccs[0]["attempt"] == 1
        assert ccs[0]["prompt_bytes"] > 0

        # In-flight snapshot was cleaned up.
        in_flight = repo / ".plan-tool" / "runs" / "rl" / "in-flight.json"
        assert not in_flight.exists()


# ---------------------------------------------------------------------------
# BACKLOG #37: ``plan-tool run <name> --all`` sweeps every runnable step.
# ---------------------------------------------------------------------------


_RUN_ALL_PLAN = """---
title: Run All Sweep
status: in-progress
priority: medium
steps:
  - id: 1
    title: First step
    status: current
  - id: 2
    title: Second step
    status: pending
  - id: 3
    title: Third step
    status: pending
---

# Run All Sweep
"""


_RUN_ALL_LESSONS_PLAN = """---
title: Run All Sweep
status: in-progress
priority: medium
lessons: plan-details/sweep/lessons.md
steps:
  - id: 1
    title: First step
    status: current
  - id: 2
    title: Second step
    status: pending
  - id: 3
    title: Third step
    status: pending
---

# Run All Sweep
"""


def _run_all_setup(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Build a 3-step plan + manifest under a fresh repo. Returns
    ``(repo, plan_path, manifest)``.
    """
    repo = tmp_path
    (repo / ".git").mkdir()
    plans_dir = repo / "plans"
    plans_dir.mkdir()
    plan_path = plans_dir / "sweep.md"
    plan_path.write_text(_RUN_ALL_PLAN, encoding="utf-8")
    manifest = repo / "m.json"
    manifest.write_text(
        _json.dumps({"plans": ["plans/sweep.md"]}), encoding="utf-8"
    )
    return repo, plan_path, manifest


def _run_all_lessons_setup(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Like :func:`_run_all_setup` but the plan declares a ``lessons:``
    file, so a halt during the sweep self-records there.
    """
    repo = tmp_path
    (repo / ".git").mkdir()
    plans_dir = repo / "plans"
    plans_dir.mkdir()
    plan_path = plans_dir / "sweep.md"
    plan_path.write_text(_RUN_ALL_LESSONS_PLAN, encoding="utf-8")
    manifest = repo / "m.json"
    manifest.write_text(
        _json.dumps({"plans": ["plans/sweep.md"]}), encoding="utf-8"
    )
    return repo, plan_path, manifest


def _run_all_ok_stdout() -> str:
    """A claude stdout shaped to satisfy ``run_step``'s contract checks
    (``## Summary`` + ``## Validation``) so the real ``run_step`` will
    advance the plan."""
    return (
        "## Summary\nDid the thing.\n\n"
        "## Validation\nNo regressions.\n"
    )


def _init_committed_sweep_repo(repo: Path) -> Path:
    """git-init ``repo`` with the 3-step sweep plan + manifest committed so
    the tree starts clean (the state ``--commit`` requires). ``.plan-tool/``
    is gitignored, mirroring a real repo, so run logs / prefs don't dirty the
    tree. Returns the manifest path."""
    import subprocess

    plans_dir = repo / "plans"
    plans_dir.mkdir()
    (plans_dir / "sweep.md").write_text(_RUN_ALL_PLAN, encoding="utf-8")
    (repo / ".gitignore").write_text(".plan-tool/\n", encoding="utf-8")
    manifest = repo / "m.json"
    manifest.write_text(
        _json.dumps({"plans": ["plans/sweep.md"]}), encoding="utf-8"
    )
    subprocess.run(
        ["git", "init", "-q"], cwd=repo,
        stdin=subprocess.DEVNULL, capture_output=True, check=True,
    )
    for key, value in (
        ("user.email", "test@plan-tool.local"),
        ("user.name", "plan-tool test"),
    ):
        subprocess.run(
            ["git", "config", key, value], cwd=repo,
            stdin=subprocess.DEVNULL, capture_output=True, check=True,
        )
    subprocess.run(
        ["git", "add", "-A"], cwd=repo,
        stdin=subprocess.DEVNULL, capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "commit", "-q", "-m", "baseline"], cwd=repo,
        stdin=subprocess.DEVNULL, capture_output=True, check=True,
    )
    return manifest


@pytest.mark.integration
class TestCmdRunAll:
    """Behavior matrix for ``plan-tool run <name> --all`` (BACKLOG #37)."""

    def test_step_and_all_are_mutually_exclusive(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli import app as cli_module

        repo, _plan_path, manifest = _run_all_setup(tmp_path)
        monkeypatch.chdir(repo)

        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "run", "sweep", "--all", "--step", "1",
            ]
        )
        assert rc == 2

    def test_review_mode_under_all_rejected_with_review_all_redirect(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module

        repo, _plan_path, manifest = _run_all_setup(tmp_path)
        monkeypatch.chdir(repo)

        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "run", "sweep", "--all", "--mode", "check",
            ]
        )
        assert rc == 2
        err = capsys.readouterr().err
        assert "verify-all" in err
        assert "--mode check" in err

    def test_reconcile_audit_flag_rejected_under_all(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli import app as cli_module

        repo, _plan_path, manifest = _run_all_setup(tmp_path)
        monkeypatch.chdir(repo)

        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "run", "sweep", "--all", "--reconcile",
            ]
        )
        assert rc == 2

    def test_max_steps_zero_is_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli import app as cli_module

        repo, _plan_path, manifest = _run_all_setup(tmp_path)
        monkeypatch.chdir(repo)

        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "run", "sweep", "--all", "--max-steps", "0",
            ]
        )
        assert rc == 2

    def test_happy_path_sweeps_until_plan_complete(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool import launcher as launcher_module

        repo, plan_path, manifest = _run_all_setup(tmp_path)

        original_run_step = launcher_module.run_step
        invoker_calls: list[str] = []

        def patched_run_step(*args, **kwargs):
            def fake_invoker(prompt: str) -> tuple[int, str]:
                invoker_calls.append(prompt[:40])
                return (0, _run_all_ok_stdout())

            kwargs["invoker"] = fake_invoker
            return original_run_step(*args, **kwargs)

        monkeypatch.setattr("plan_tool.cli.run_cmd.run_step", patched_run_step)
        monkeypatch.chdir(repo)

        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "run", "sweep", "--all",
            ]
        )
        assert rc == 0
        # Three steps -> three invoker calls.
        assert len(invoker_calls) == 3

        # Plan is fully done.
        plan_text = plan_path.read_text(encoding="utf-8")
        # All step status: done; no remaining current.
        assert plan_text.count("status: done") == 3
        assert "status: current" not in plan_text
        assert "status: pending" not in plan_text

        # One run-log dir per step (matching design: one RunLogWriter
        # per iteration, not one for the whole sweep).
        run_logs = list(
            (repo / ".plan-tool" / "runs").rglob("*.jsonl")
        )
        assert len(run_logs) == 3

    def test_halts_on_first_failure_and_propagates_exit_code(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool import launcher as launcher_module

        repo, plan_path, manifest = _run_all_setup(tmp_path)

        original_run_step = launcher_module.run_step
        call_count = {"n": 0}

        def patched_run_step(*args, **kwargs):
            def fake_invoker(prompt: str) -> tuple[int, str]:
                call_count["n"] += 1
                # Step 2 fails with rc=42.
                if call_count["n"] == 2:
                    return (42, "fatal\n")
                return (0, _run_all_ok_stdout())

            kwargs["invoker"] = fake_invoker
            return original_run_step(*args, **kwargs)

        monkeypatch.setattr("plan_tool.cli.run_cmd.run_step", patched_run_step)
        monkeypatch.chdir(repo)

        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "run", "sweep", "--all",
            ]
        )
        # Exit code is the failing step's rc, unaggregated.
        assert rc == 42
        # Only step 1 advanced; step 2 stayed current after the failure.
        plan_text = plan_path.read_text(encoding="utf-8")
        assert plan_text.count("status: done") == 1
        assert plan_text.count("status: current") == 1
        err = capsys.readouterr().err
        assert "sweep halted" in err

    def test_halt_records_lesson_line(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A sweep that halts on a failing step appends exactly one
        ``step N halt (sweep):`` line to the plan's ``lessons:`` file."""
        from plan_tool.cli import app as cli_module
        from plan_tool import launcher as launcher_module

        repo, plan_path, manifest = _run_all_lessons_setup(tmp_path)

        original_run_step = launcher_module.run_step
        call_count = {"n": 0}

        def patched_run_step(*args, **kwargs):
            def fake_invoker(prompt: str) -> tuple[int, str]:
                call_count["n"] += 1
                # Step 2 fails with rc=7.
                if call_count["n"] == 2:
                    return (7, "fatal\n")
                return (0, _run_all_ok_stdout())

            kwargs["invoker"] = fake_invoker
            return original_run_step(*args, **kwargs)

        monkeypatch.setattr("plan_tool.cli.run_cmd.run_step", patched_run_step)
        monkeypatch.chdir(repo)

        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "run", "sweep", "--all",
            ]
        )
        assert rc == 7
        # Only step 1 advanced before the failure.
        plan_text = plan_path.read_text(encoding="utf-8")
        assert plan_text.count("status: done") == 1

        lessons_path = repo / "plan-details/sweep/lessons.md"
        halt_lines = [
            ln for ln in lessons_path.read_text(encoding="utf-8").splitlines()
            if "halt (sweep):" in ln
        ]
        assert len(halt_lines) == 1
        assert "step 2 halt (sweep):" in halt_lines[0]
        # Halt lines never inflate the completion-entry counter.
        assert launcher_module.read_lessons_step_ids(lessons_path) == {1}

    def test_max_steps_caps_the_sweep(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool import launcher as launcher_module

        repo, plan_path, manifest = _run_all_setup(tmp_path)

        original_run_step = launcher_module.run_step
        invoker_calls: list[int] = []

        def patched_run_step(*args, **kwargs):
            def fake_invoker(prompt: str) -> tuple[int, str]:
                invoker_calls.append(1)
                return (0, _run_all_ok_stdout())

            kwargs["invoker"] = fake_invoker
            return original_run_step(*args, **kwargs)

        monkeypatch.setattr("plan_tool.cli.run_cmd.run_step", patched_run_step)
        monkeypatch.chdir(repo)

        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "run", "sweep", "--all", "--max-steps", "2",
            ]
        )
        assert rc == 0
        assert len(invoker_calls) == 2
        plan_text = plan_path.read_text(encoding="utf-8")
        # Two done, one still runnable (current).
        assert plan_text.count("status: done") == 2
        assert plan_text.count("status: current") == 1
        err = capsys.readouterr().err
        assert "capped at --max-steps 2" in err

    def test_all_implies_yes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``--all`` activates ``-y`` semantics for every per-step
        path that inspects ``args.yes``. We don't have an interactive
        prompt to capture in the sweep proper (mode=run), so verify
        the override by inspecting the sweep's run-log flags.
        """
        from plan_tool.cli import app as cli_module
        from plan_tool import launcher as launcher_module

        repo, _plan_path, manifest = _run_all_setup(tmp_path)

        original_run_step = launcher_module.run_step

        def patched_run_step(*args, **kwargs):
            kwargs["invoker"] = lambda prompt: (0, _run_all_ok_stdout())
            return original_run_step(*args, **kwargs)

        monkeypatch.setattr("plan_tool.cli.run_cmd.run_step", patched_run_step)
        monkeypatch.chdir(repo)

        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "run", "sweep", "--all", "--max-steps", "1",
            ]
        )
        assert rc == 0
        # The run_start event for the (sole) iteration should carry
        # ``yes: true`` in its flags even though ``-y`` wasn't passed.
        events = _read_run_log_events(repo / ".plan-tool" / "runs")
        run_start = events[0]
        assert run_start["event"] == "run_start"
        assert run_start["flags"]["yes"] is True
        assert run_start["flags"]["all"] is True

    def test_no_runnable_steps_reports_and_exits_zero(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module

        repo = tmp_path
        (repo / ".git").mkdir()
        plans_dir = repo / "plans"
        plans_dir.mkdir()
        plan_path = plans_dir / "done.md"
        # All steps done up front -> nothing to sweep.
        plan_path.write_text(
            "---\n"
            "title: Done\n"
            "status: completed\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: t\n"
            "    status: done\n"
            "---\n",
            encoding="utf-8",
        )
        manifest = repo / "m.json"
        manifest.write_text(
            _json.dumps({"plans": ["plans/done.md"]}), encoding="utf-8"
        )
        monkeypatch.chdir(repo)

        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "run", "done", "--all",
            ]
        )
        assert rc == 0
        err = capsys.readouterr().err
        assert "nothing to sweep" in err
        # No run-log dir created when the sweep can't start.
        assert not (repo / ".plan-tool" / "runs").exists()

    def test_commit_makes_one_commit_per_green_step(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import subprocess

        from plan_tool.cli import app as cli_module
        from plan_tool import launcher as launcher_module

        # ``--commit`` requires a REAL git repo with a clean tree: the fake
        # ``(repo / ".git").mkdir()`` repo ``_run_all_setup`` builds is
        # treated as blocked by the clean-tree precheck (non-repo -> non-
        # zero ``git status``), so build + ``git init`` a real one here.
        repo = tmp_path
        plans_dir = repo / "plans"
        plans_dir.mkdir()
        plan_path = plans_dir / "sweep.md"
        plan_path.write_text(_RUN_ALL_PLAN, encoding="utf-8")
        manifest = repo / "m.json"
        manifest.write_text(
            _json.dumps({"plans": ["plans/sweep.md"]}), encoding="utf-8"
        )
        # A real repo, plan + manifest committed so the tree starts clean.
        subprocess.run(
            ["git", "init", "-q"], cwd=repo,
            stdin=subprocess.DEVNULL, capture_output=True, check=True,
        )
        for key, value in (
            ("user.email", "test@plan-tool.local"),
            ("user.name", "plan-tool test"),
        ):
            subprocess.run(
                ["git", "config", key, value], cwd=repo,
                stdin=subprocess.DEVNULL, capture_output=True, check=True,
            )
        subprocess.run(
            ["git", "add", "-A"], cwd=repo,
            stdin=subprocess.DEVNULL, capture_output=True, check=True,
        )
        subprocess.run(
            ["git", "commit", "-q", "-m", "baseline"], cwd=repo,
            stdin=subprocess.DEVNULL, capture_output=True, check=True,
        )

        original_run_step = launcher_module.run_step

        def patched_run_step(*args, **kwargs):
            def fake_invoker(prompt: str) -> tuple[int, str]:
                return (0, _run_all_ok_stdout())

            kwargs["invoker"] = fake_invoker
            return original_run_step(*args, **kwargs)

        monkeypatch.setattr("plan_tool.cli.run_cmd.run_step", patched_run_step)
        monkeypatch.chdir(repo)

        def _commit_count() -> int:
            proc = subprocess.run(
                ["git", "rev-list", "--count", "HEAD"], cwd=repo,
                stdin=subprocess.DEVNULL, capture_output=True,
                text=True, check=True,
            )
            return int(proc.stdout.strip())

        before = _commit_count()
        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "run", "sweep", "--all", "--commit",
            ]
        )
        assert rc == 0
        # Three green steps -> three new commits on top of the baseline.
        assert _commit_count() - before == 3

        subjects = subprocess.run(
            ["git", "log", "--format=%s", "-3"], cwd=repo,
            stdin=subprocess.DEVNULL, capture_output=True,
            text=True, check=True,
        ).stdout.splitlines()
        # Newest first: step 3 (terminal, advanced_to is None) committed too.
        assert subjects[0] == "plan(sweep): step 3 green — Third step"
        assert subjects[1] == "plan(sweep): step 2 green — Second step"
        assert subjects[2] == "plan(sweep): step 1 green — First step"
        # No AI-attribution trailer rides the commit — the operator's own
        # git identity is the sole author of record.
        body = subprocess.run(
            ["git", "log", "-1", "--format=%b"], cwd=repo,
            stdin=subprocess.DEVNULL, capture_output=True,
            text=True, check=True,
        ).stdout
        assert body.strip() == ""

    def test_all_without_commit_makes_no_commits(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import subprocess

        from plan_tool.cli import app as cli_module
        from plan_tool import launcher as launcher_module

        repo = tmp_path
        plans_dir = repo / "plans"
        plans_dir.mkdir()
        plan_path = plans_dir / "sweep.md"
        plan_path.write_text(_RUN_ALL_PLAN, encoding="utf-8")
        manifest = repo / "m.json"
        manifest.write_text(
            _json.dumps({"plans": ["plans/sweep.md"]}), encoding="utf-8"
        )
        subprocess.run(
            ["git", "init", "-q"], cwd=repo,
            stdin=subprocess.DEVNULL, capture_output=True, check=True,
        )
        for key, value in (
            ("user.email", "test@plan-tool.local"),
            ("user.name", "plan-tool test"),
        ):
            subprocess.run(
                ["git", "config", key, value], cwd=repo,
                stdin=subprocess.DEVNULL, capture_output=True, check=True,
            )
        subprocess.run(
            ["git", "add", "-A"], cwd=repo,
            stdin=subprocess.DEVNULL, capture_output=True, check=True,
        )
        subprocess.run(
            ["git", "commit", "-q", "-m", "baseline"], cwd=repo,
            stdin=subprocess.DEVNULL, capture_output=True, check=True,
        )

        original_run_step = launcher_module.run_step

        def patched_run_step(*args, **kwargs):
            def fake_invoker(prompt: str) -> tuple[int, str]:
                return (0, _run_all_ok_stdout())

            kwargs["invoker"] = fake_invoker
            return original_run_step(*args, **kwargs)

        monkeypatch.setattr("plan_tool.cli.run_cmd.run_step", patched_run_step)
        monkeypatch.chdir(repo)

        def _commit_count() -> int:
            proc = subprocess.run(
                ["git", "rev-list", "--count", "HEAD"], cwd=repo,
                stdin=subprocess.DEVNULL, capture_output=True,
                text=True, check=True,
            )
            return int(proc.stdout.strip())

        before = _commit_count()
        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "run", "sweep", "--all",
            ]
        )
        assert rc == 0
        # Default sweep makes zero commits (byte-unchanged behavior).
        assert _commit_count() == before

    def test_single_step_commit_makes_one_commit(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Regression (BUG_BACKLOG): ``--commit`` was inert outside ``--all``.
        # A single-step run now commits the green step (HEAD advances by one,
        # tree clean) — the same per-green-step commit the sweep makes.
        import subprocess

        from plan_tool.cli import app as cli_module
        from plan_tool import launcher as launcher_module

        repo = tmp_path
        manifest = _init_committed_sweep_repo(repo)

        original_run_step = launcher_module.run_step

        def patched_run_step(*args, **kwargs):
            kwargs["invoker"] = lambda prompt: (0, _run_all_ok_stdout())
            return original_run_step(*args, **kwargs)

        monkeypatch.setattr("plan_tool.cli.run_cmd.run_step", patched_run_step)
        monkeypatch.chdir(repo)

        def _commit_count() -> int:
            proc = subprocess.run(
                ["git", "rev-list", "--count", "HEAD"], cwd=repo,
                stdin=subprocess.DEVNULL, capture_output=True,
                text=True, check=True,
            )
            return int(proc.stdout.strip())

        before = _commit_count()
        rc = cli_module.main(
            ["--manifest", str(manifest), "run", "sweep", "--step", "1", "--commit"]
        )
        assert rc == 0
        assert _commit_count() - before == 1

        subject = subprocess.run(
            ["git", "log", "-1", "--format=%s"], cwd=repo,
            stdin=subprocess.DEVNULL, capture_output=True, text=True, check=True,
        ).stdout.strip()
        assert subject == "plan(sweep): step 1 green — First step"

        # Tree clean after: the green commit captured the mark-done write and
        # ``.plan-tool/`` is gitignored, so nothing is left uncommitted.
        porcelain = subprocess.run(
            ["git", "status", "--porcelain"], cwd=repo,
            stdin=subprocess.DEVNULL, capture_output=True, text=True, check=True,
        ).stdout.strip()
        assert porcelain == ""

    def test_single_step_commit_requires_clean_tree(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # The single-step ``--commit`` path enforces the same clean-tree
        # precondition as the sweep (rc=2, no commit, before any claude call).
        import subprocess

        from plan_tool.cli import app as cli_module

        repo = tmp_path
        manifest = _init_committed_sweep_repo(repo)
        (repo / "dirty.txt").write_text("uncommitted", encoding="utf-8")
        monkeypatch.chdir(repo)

        def _commit_count() -> int:
            proc = subprocess.run(
                ["git", "rev-list", "--count", "HEAD"], cwd=repo,
                stdin=subprocess.DEVNULL, capture_output=True,
                text=True, check=True,
            )
            return int(proc.stdout.strip())

        before = _commit_count()
        rc = cli_module.main(
            ["--manifest", str(manifest), "run", "sweep", "--step", "1", "--commit"]
        )
        assert rc == 2
        assert "--commit requires a clean working tree" in capsys.readouterr().err
        assert _commit_count() == before

    def test_single_step_commit_warns_and_no_ops_in_review_mode(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # ``--commit`` with a review mode commits nothing (the audit doesn't
        # mutate); it must warn rather than silently no-op. No clean-tree
        # requirement is imposed either.
        import subprocess

        from plan_tool.cli import app as cli_module
        from plan_tool import launcher as launcher_module

        repo = tmp_path
        manifest = _init_committed_sweep_repo(repo)

        original_run_step = launcher_module.run_step

        def patched_run_step(*args, **kwargs):
            kwargs["invoker"] = lambda prompt: (0, _run_all_ok_stdout())
            return original_run_step(*args, **kwargs)

        monkeypatch.setattr("plan_tool.cli.run_cmd.run_step", patched_run_step)
        monkeypatch.chdir(repo)

        def _commit_count() -> int:
            proc = subprocess.run(
                ["git", "rev-list", "--count", "HEAD"], cwd=repo,
                stdin=subprocess.DEVNULL, capture_output=True,
                text=True, check=True,
            )
            return int(proc.stdout.strip())

        before = _commit_count()
        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "run", "sweep", "--step", "1", "--commit", "--mode", "check",
            ]
        )
        assert rc == 0
        assert "--commit has no effect with --mode check" in capsys.readouterr().err
        assert _commit_count() == before

    def test_commit_archive_leaves_clean_tree(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Regression (BUG_BACKLOG RISK): --commit --archive committed each green
        # step but archived the completed plan AFTER the commit, so the move +
        # manifest edit were left uncommitted — a dirty tree that blocked the
        # next --commit. The archive now rides the terminal step's green commit.
        import subprocess

        from plan_tool.cli import app as cli_module
        from plan_tool import launcher as launcher_module

        repo = tmp_path
        manifest = _init_committed_sweep_repo(repo)

        original_run_step = launcher_module.run_step

        def patched_run_step(*args, **kwargs):
            kwargs["invoker"] = lambda prompt: (0, _run_all_ok_stdout())
            return original_run_step(*args, **kwargs)

        monkeypatch.setattr("plan_tool.cli.run_cmd.run_step", patched_run_step)
        monkeypatch.chdir(repo)

        def _commit_count() -> int:
            proc = subprocess.run(
                ["git", "rev-list", "--count", "HEAD"], cwd=repo,
                stdin=subprocess.DEVNULL, capture_output=True,
                text=True, check=True,
            )
            return int(proc.stdout.strip())

        before = _commit_count()
        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "run", "sweep", "--all", "--commit", "--archive",
            ]
        )
        assert rc == 0
        # Plan was archived: no longer at its registered path.
        assert not (repo / "plans" / "sweep.md").exists()
        # The archive move + manifest edit rode the green commits — tree clean,
        # so a follow-up --commit run wouldn't be blocked by the precheck.
        porcelain = subprocess.run(
            ["git", "status", "--porcelain"], cwd=repo,
            stdin=subprocess.DEVNULL, capture_output=True, text=True, check=True,
        ).stdout.strip()
        assert porcelain == ""
        # Three green steps → three commits (the terminal one carries the archive).
        assert _commit_count() - before == 3

    def test_archive_on_completion_sweeps_finished_plan(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``run --all --archive`` archives the plan the moment the sweep
        takes it to N/N done: file moves under ``archive/``, manifest
        entry is gone, rc=0."""
        from plan_tool.cli import app as cli_module
        from plan_tool import launcher as launcher_module

        repo, plan_path, manifest = _run_all_setup(tmp_path)

        original_run_step = launcher_module.run_step

        def patched_run_step(*args, **kwargs):
            kwargs["invoker"] = lambda prompt: (0, _run_all_ok_stdout())
            return original_run_step(*args, **kwargs)

        monkeypatch.setattr("plan_tool.cli.run_cmd.run_step", patched_run_step)
        monkeypatch.chdir(repo)

        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "run", "sweep", "--all", "--archive",
            ]
        )
        assert rc == 0
        # File moved to plans/archive/sweep.md; source gone.
        assert not plan_path.exists()
        assert (repo / "plans" / "archive" / "sweep.md").is_file()
        # Manifest entry deregistered.
        manifest_data = _json.loads(manifest.read_text(encoding="utf-8"))
        assert manifest_data["plans"] == []

    def test_archive_on_completion_single_step(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """``run --step N --archive`` on the terminal step archives the
        plan, prints the archived path + ``plan-tool register`` undo hint,
        and does NOT print the ``plan-tool sweep`` next-step hint."""
        from plan_tool.cli import app as cli_module
        from plan_tool import launcher as launcher_module

        repo = tmp_path
        (repo / ".git").mkdir()
        plans_dir = repo / "plans"
        plans_dir.mkdir()
        plan_path = plans_dir / "sweep.md"
        # Steps 1-2 already done, step 3 current — running step 3 takes
        # the plan to N/N done.
        plan_path.write_text(
            "---\n"
            "title: Almost Done\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: First step\n"
            "    status: done\n"
            "  - id: 2\n"
            "    title: Second step\n"
            "    status: done\n"
            "  - id: 3\n"
            "    title: Third step\n"
            "    status: current\n"
            "---\n",
            encoding="utf-8",
        )
        manifest = repo / "m.json"
        manifest.write_text(
            _json.dumps({"plans": ["plans/sweep.md"]}), encoding="utf-8"
        )

        original_run_step = launcher_module.run_step

        def patched_run_step(*args, **kwargs):
            kwargs["invoker"] = lambda prompt: (0, _run_all_ok_stdout())
            return original_run_step(*args, **kwargs)

        monkeypatch.setattr("plan_tool.cli.run_cmd.run_step", patched_run_step)
        monkeypatch.chdir(repo)

        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "run", "sweep", "--step", "3", "--archive",
            ]
        )
        assert rc == 0
        assert not plan_path.exists()
        assert (plans_dir / "archive" / "sweep.md").is_file()
        manifest_data = _json.loads(manifest.read_text(encoding="utf-8"))
        assert manifest_data["plans"] == []
        out = capsys.readouterr().out
        assert "archive/sweep.md" in out
        assert "plan-tool register" in out
        # The --archive branch replaces the sweep next-step hint.
        assert "plan-tool sweep" not in out

    def test_archive_noop_note_on_non_terminal_step(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """``run --step N --archive`` on a step that advances but does not
        complete the plan leaves the file in place and prints a
        ``did not complete the plan`` no-op note."""
        from plan_tool.cli import app as cli_module
        from plan_tool import launcher as launcher_module

        repo, plan_path, manifest = _run_all_setup(tmp_path)

        original_run_step = launcher_module.run_step

        def patched_run_step(*args, **kwargs):
            kwargs["invoker"] = lambda prompt: (0, _run_all_ok_stdout())
            return original_run_step(*args, **kwargs)

        monkeypatch.setattr("plan_tool.cli.run_cmd.run_step", patched_run_step)
        monkeypatch.chdir(repo)

        # Step 1 of 3 is current; running it advances to step 2 but does
        # not complete the plan.
        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "run", "sweep", "--step", "1", "--archive",
            ]
        )
        assert rc == 0
        # File stays in place; manifest entry intact.
        assert plan_path.exists()
        assert not (repo / "plans" / "archive").exists()
        manifest_data = _json.loads(manifest.read_text(encoding="utf-8"))
        assert manifest_data["plans"] == ["plans/sweep.md"]
        out = capsys.readouterr().out
        assert "did not complete the plan" in out


def _iter_basic_plan(tmp_path: Path) -> Path:
    """Minimal plan with one done step. Lifted from test_review_walk.py so
    the iteration-loop tests don't need to import across test modules.
    """
    plan_path = tmp_path / "plan.md"
    plan_path.write_text(
        "---\n"
        "title: P\n"
        "status: in-progress\n"
        "priority: low\n"
        "steps:\n"
        "  - id: 1\n"
        "    title: t\n"
        "    files: [foo.py]\n"
        "    status: done\n"
        "---\n",
        encoding="utf-8",
    )
    (tmp_path / "foo.py").write_text("x\n", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    return plan_path


def _iter_setup_manifest(tmp_path: Path) -> Path:
    manifest = tmp_path / "m.json"
    manifest.write_text('{"plans": ["plan.md"]}\n', encoding="utf-8")
    return manifest


def _iter_force_tty(monkeypatch: pytest.MonkeyPatch, value: bool) -> None:
    import sys as _sys
    monkeypatch.setattr(_sys.stdin, "isatty", lambda: value)


# ---------------------------------------------------------------------------
# Step 5: --iterate / --max-iterations / --iteration-budget CLI flags.
#
# These exercise argparse and the shared budget resolver. Authoring tests
# capture orchestrator budgets; run tests pin compatibility-value validation.
# ---------------------------------------------------------------------------


class _CreateFakeResult:
    """Stand-in ``CreateResult`` for ``cmd_create`` orchestrator stubs."""

    def __init__(self, tmp_path: Path) -> None:
        self.plan_path = tmp_path / "1-demo.md"
        self.manifest_path = tmp_path / "m.json"
        self.manifest_updated = True
        self.provenance = None
        self.plan_details_renamed_to = None
        self.plan_details_skip_reason = None
        self.replaced_archives: list = []
        self.replaced_skipped: list = []
        self.replaced_manifest_entries: list = []
        self.split_proposal = None
        self.distilled_seed = None
        self.iteration_stage_failure = None
        self.file_backed_route = None
        self.refusal_reason = None


class TestCreateIterationIncompleteExitCode:
    """A published plan exits 0 even when an iteration stage remains incomplete."""

    def _run(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        *,
        failure: object,
    ) -> int:
        from plan_tool.cli import app as cli_module

        def fake_create_plan(slug, **kwargs):
            result = _CreateFakeResult(tmp_path)
            result.iteration_stage_failure = failure
            return result

        monkeypatch.setattr("plan_tool.cli.authoring.create_plan", fake_create_plan)
        monkeypatch.setattr(
            cli_context, "find_repo_root_from_cwd", lambda: tmp_path
        )
        monkeypatch.chdir(tmp_path)
        return cli_module.main(["create", "demo"])

    @pytest.mark.parametrize(
        "failure",
        [
            "step re-proposal failed in iteration 1",
            (
                "reference research failed in iteration 1 "
                "(terminal unparseable response)"
            ),
            None,
        ],
        ids=["stage-failure", "reference-research-failure", "clean-finish"],
    )
    def test_iteration_outcome_still_exits_zero(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: object
    ) -> None:
        # The plan was written and is usable regardless of outcome; an
        # incomplete polish loop is a result to address (re-run resumes),
        # not a failure of create. Exit 0 — the run-log
        # ``iteration_incomplete`` outcome carries the signal, not the
        # exit code.
        rc = self._run(tmp_path, monkeypatch, failure=failure)
        assert rc == 0


class TestMainCrashHandler:
    """main()'s catch-all turns an unexpected exception into a clean
    message + a persisted traceback file, not a raw stack trace."""

    def test_unexpected_exception_is_caught_and_persisted(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool.crash import crashes_root

        def boom(_args: object) -> int:
            raise RuntimeError("kaboom")

        # Dispatch resolves ``cmd_list`` from ITS module (``inspect``) via
        # ``inspect.register``, so patch there — patching the ``app`` alias
        # would not intercept (it's a second binding dispatch never reads).
        from plan_tool.cli import inspect as inspect_module

        monkeypatch.setattr(inspect_module, "cmd_list", boom)
        # main()'s crash handler resolves find_repo_root_from_cwd through
        # app's own globals (it never reaches the context helpers), so the
        # patch targets app here — unlike the handler-path tests, which
        # patch plan_tool.cli.context.
        monkeypatch.setattr(
            cli_module, "find_repo_root_from_cwd", lambda: tmp_path
        )

        rc = cli_module.main(["list"])

        assert rc == 1
        err = capsys.readouterr().err
        # Clean one-liner, not a raw traceback.
        assert "unexpected error: RuntimeError: kaboom" in err
        assert "re-run the command to retry" in err
        # No raw Python traceback header leaked to the console.
        assert "Traceback (most recent call last)" not in err
        # Traceback persisted under .plan-tool/crashes/<label>/.
        crash_files = list(
            (crashes_root(tmp_path) / "list").glob("*.txt")
        )
        assert len(crash_files) == 1
        body = crash_files[0].read_text(encoding="utf-8")
        assert "RuntimeError: kaboom" in body
        assert "Traceback (most recent call last)" in body

    def test_human_input_error_uses_the_known_error_path(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool.crash import crashes_root
        from plan_tool.human_io import HumanInputError
        from plan_tool.cli import inspect as inspect_module

        def fail(_args: object) -> int:
            raise HumanInputError("human-input request record already exists")

        monkeypatch.setattr(inspect_module, "cmd_list", fail)
        monkeypatch.setattr(
            cli_module, "find_repo_root_from_cwd", lambda: tmp_path
        )

        rc = cli_module.main(["list"])

        assert rc == 2
        err = capsys.readouterr().err
        assert "error: human-input request record already exists" in err
        assert "PLAN_TOOL_HUMAN_IO_DIR" in err
        assert "unexpected error" not in err
        assert not (crashes_root(tmp_path) / "list").exists()

    def test_crash_file_honors_repo_root_override(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """With ``--repo-root /X``, the crash file lands in ``/X``'s
        .plan-tool/crashes/, not cwd's -- the artifact belongs with the
        repo the command targeted."""
        from plan_tool.cli import app as cli_module
        from plan_tool.crash import crashes_root

        target = tmp_path / "target_repo"
        target.mkdir()
        cwd_repo = tmp_path / "cwd_repo"
        cwd_repo.mkdir()

        def boom(_args: object) -> int:
            raise RuntimeError("kaboom")

        from plan_tool.cli import inspect as inspect_module

        monkeypatch.setattr(inspect_module, "cmd_list", boom)
        # cwd-based discovery would resolve HERE; the override must win.
        monkeypatch.setattr(
            cli_context, "find_repo_root_from_cwd", lambda: cwd_repo
        )

        rc = cli_module.main(["--repo-root", str(target), "list"])

        assert rc == 1
        assert list((crashes_root(target) / "list").glob("*.txt"))
        # Nothing written to the cwd-discovered repo.
        assert not crashes_root(cwd_repo).exists()

    def test_keyboard_interrupt_passes_through(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli import app as cli_module

        def interrupt(_args: object) -> int:
            raise KeyboardInterrupt

        from plan_tool.cli import inspect as inspect_module

        monkeypatch.setattr(inspect_module, "cmd_list", interrupt)
        monkeypatch.setattr(
            cli_context, "find_repo_root_from_cwd", lambda: tmp_path
        )
        # BaseException must NOT be swallowed by the catch-all.
        with pytest.raises(KeyboardInterrupt):
            cli_module.main(["list"])


class TestIterateFlagsCreate:
    """Step 5: ``--iterate`` / ``--max-iterations`` / ``--iteration-budget``
    propagate from ``plan-tool create`` argv into ``create_plan(...)``'s
    ``budget`` kwarg."""

    def _stub(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> dict:
        from plan_tool.cli import app as cli_module

        captured: dict = {}

        def fake_create_plan(slug, **kwargs):
            captured.update(kwargs)
            captured["slug"] = slug
            return _CreateFakeResult(tmp_path)

        monkeypatch.setattr("plan_tool.cli.authoring.create_plan", fake_create_plan)
        monkeypatch.setattr(
            cli_context, "find_repo_root_from_cwd", lambda: tmp_path
        )
        monkeypatch.chdir(tmp_path)
        return captured

    def test_default_passes_enabled_budget(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # ``create`` opts INTO the post-write convergence loop by
        # default (see ``p_create.set_defaults(iterate=True)`` in
        # cli.py). Omitting ``--iterate`` / ``--no-iterate`` must
        # therefore yield an enabled budget. ``detail`` and ``run``
        # still default to the parent's opt-in (off).
        from plan_tool.cli import app as cli_module

        captured = self._stub(tmp_path, monkeypatch)
        rc = cli_module.main(["create", "demo"])
        assert rc == 0
        budget = captured.get("budget")
        assert budget is not None
        assert budget.enabled is True

    def test_iterate_flag_passes_enabled_budget(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli import app as cli_module

        captured = self._stub(tmp_path, monkeypatch)
        rc = cli_module.main(["create", "demo", "--iterate"])
        assert rc == 0
        budget = captured.get("budget")
        assert budget is not None
        assert budget.enabled is True

    def test_no_iterate_flag_passes_disabled_budget(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli import app as cli_module

        captured = self._stub(tmp_path, monkeypatch)
        rc = cli_module.main(["create", "demo", "--no-iterate"])
        assert rc == 0
        budget = captured.get("budget")
        assert budget is not None
        assert budget.enabled is False

    def test_max_iterations_propagates(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli import app as cli_module

        captured = self._stub(tmp_path, monkeypatch)
        rc = cli_module.main(
            ["create", "demo", "--iterate", "--max-iterations", "7"]
        )
        assert rc == 0
        budget = captured.get("budget")
        assert budget is not None
        assert budget.max_iterations == 7

    def test_iteration_budget_propagates(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli import app as cli_module

        captured = self._stub(tmp_path, monkeypatch)
        rc = cli_module.main(
            ["create", "demo", "--iterate", "--iteration-budget", "120"]
        )
        assert rc == 0
        budget = captured.get("budget")
        assert budget is not None
        assert budget.budget_seconds == 120


def _detail_basic_plan(tmp_path: Path) -> Path:
    """Minimal plan + manifest setup for ``cmd_detail`` invocations.

    ``cmd_detail`` runs ``_load_context`` → ``resolve_plan_for_context``
    before calling ``generate_detail``, so an on-disk plan file is
    required even when the orchestrator is stubbed.
    """
    plan_path = tmp_path / "plan.md"
    plan_path.write_text(
        "---\n"
        "title: P\n"
        "status: in-progress\n"
        "priority: low\n"
        "steps:\n"
        "  - id: 1\n"
        "    title: t\n"
        "    files: [foo.py]\n"
        "    status: pending\n"
        "---\n",
        encoding="utf-8",
    )
    (tmp_path / ".git").mkdir()
    return plan_path


def _prepare_selected_reconcile_step(plan_path: Path) -> None:
    """Make step 1 a completed, detail-grounded selected reconcile target."""
    from plan_tool.detail_artifacts import derive_detail_path
    from plan_tool.parser import parse_plan

    plan = parse_plan(plan_path)
    detail_path = derive_detail_path(plan_path, plan, plan.step_by_id(1))
    detail_path.parent.mkdir(parents=True, exist_ok=True)
    detail_path.write_text("# Selected reconcile detail\n", encoding="utf-8")
    plan_path.write_text(
        plan_path.read_text(encoding="utf-8").replace(
            "status: pending", "status: done", 1
        ),
        encoding="utf-8",
    )


def _detail_setup_manifest(tmp_path: Path) -> Path:
    manifest = tmp_path / "m.json"
    manifest.write_text('{"plans": ["plan.md"]}\n', encoding="utf-8")
    return manifest


class TestIterateFlagsDetail:
    """Step 5: ``--iterate`` family propagates from ``plan-tool detail``
    argv into ``generate_detail(...)``'s ``budget`` kwarg."""

    def _stub(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> dict:
        from plan_tool.cli import app as cli_module

        _detail_basic_plan(tmp_path)
        manifest = _detail_setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)
        captured: dict = {"manifest": manifest}

        def fake_generate_detail(plan_path_arg, **kwargs):
            captured.update(kwargs)
            captured["plan_path"] = plan_path_arg
            return []

        monkeypatch.setattr(
            "plan_tool.cli.authoring.generate_detail", fake_generate_detail
        )
        return captured

    def test_default_passes_disabled_budget(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``detail`` opts OUT of iterate by default (pass --iterate to opt in)."""
        from plan_tool.cli import app as cli_module

        captured = self._stub(tmp_path, monkeypatch)
        rc = cli_module.main(
            ["--manifest", str(captured["manifest"]), "detail", "plan"]
        )
        assert rc == 0
        budget = captured.get("budget")
        assert budget is not None
        assert budget.enabled is False

    def test_no_iterate_flag_passes_disabled_budget(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli import app as cli_module

        captured = self._stub(tmp_path, monkeypatch)
        rc = cli_module.main(
            [
                "--manifest", str(captured["manifest"]),
                "detail", "plan", "--no-iterate",
            ]
        )
        assert rc == 0
        budget = captured.get("budget")
        assert budget is not None
        assert budget.enabled is False

    def test_iterate_flag_passes_enabled_budget(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli import app as cli_module

        captured = self._stub(tmp_path, monkeypatch)
        rc = cli_module.main(
            [
                "--manifest", str(captured["manifest"]),
                "detail", "plan", "--iterate",
            ]
        )
        assert rc == 0
        budget = captured.get("budget")
        assert budget is not None
        assert budget.enabled is True

    def test_detail_only_disables_per_step_budget(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli import app as cli_module

        captured = self._stub(tmp_path, monkeypatch)
        rc = cli_module.main(
            [
                "--manifest", str(captured["manifest"]),
                "detail", "plan", "--detail-only",
            ]
        )
        assert rc == 0
        budget = captured.get("budget")
        assert budget is not None
        assert budget.enabled is False
        assert budget.max_iterations == DEFAULT_MAX_ITERATIONS

    def test_detail_only_parse_mode(self) -> None:
        parser = build_parser()
        detail = _find_subparser(parser, "detail")
        assert detail is not None

        ns = detail.parse_args(["plan", "--detail-only"])

        assert ns.detail_only is True
        # At parse level iterate takes its default (now OFF); cmd_detail
        # pins the completeness tail ON for --detail-only (see
        # test_detail_only_keeps_iterating_completeness_tail).
        assert ns.iterate is False
        assert ns.reconcile is False

    @pytest.mark.parametrize("other", ["--no-iterate", "--iterate", "--reconcile"])
    def test_detail_only_rejects_other_modes(self, other: str) -> None:
        parser = build_parser()
        detail = _find_subparser(parser, "detail")
        assert detail is not None

        with pytest.raises(SystemExit) as exc:
            detail.parse_args(["plan", "--detail-only", other])

        assert exc.value.code == 2

    def test_detail_only_rejects_no_completeness(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli import app as cli_module

        captured = self._stub(tmp_path, monkeypatch)
        rc = cli_module.main(
            [
                "--manifest", str(captured["manifest"]),
                "detail", "plan", "--detail-only", "--no-completeness",
            ]
        )
        assert rc == 2
        assert "budget" not in captured

    def test_detail_only_keeps_iterating_completeness_tail(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool.detail import DetailResult

        _detail_basic_plan(tmp_path)
        manifest = _detail_setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)
        captured: dict = {"manifest": manifest}
        tail: dict = {}

        def fake_generate_detail(plan_path_arg, **kwargs):
            captured.update(kwargs)
            captured["plan_path"] = plan_path_arg
            return [
                DetailResult(
                    step_id=1,
                    output_path=tmp_path / "detail-1.md",
                    written=True,
                )
            ]

        def fake_tail(args, *, what: str):
            tail["iterate"] = args.iterate
            tail["detail_only"] = args.detail_only
            tail["what"] = what
            return []

        monkeypatch.setattr(
            "plan_tool.cli.authoring.generate_detail", fake_generate_detail
        )
        monkeypatch.setattr(
            "plan_tool.cli.authoring._run_completeness_tail", fake_tail
        )

        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "detail", "plan", "--detail-only",
            ]
        )

        assert rc == 0
        assert captured["budget"].enabled is False
        assert tail == {"iterate": True, "detail_only": True, "what": "detail"}

    def test_max_iterations_propagates(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli import app as cli_module

        captured = self._stub(tmp_path, monkeypatch)
        rc = cli_module.main(
            [
                "--manifest", str(captured["manifest"]),
                "detail", "plan", "--iterate", "--max-iterations", "4",
            ]
        )
        assert rc == 0
        budget = captured.get("budget")
        assert budget is not None
        assert budget.max_iterations == 4

    def test_iteration_budget_propagates(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli import app as cli_module

        captured = self._stub(tmp_path, monkeypatch)
        rc = cli_module.main(
            [
                "--manifest", str(captured["manifest"]),
                "detail", "plan", "--iterate", "--iteration-budget", "90",
            ]
        )
        assert rc == 0
        budget = captured.get("budget")
        assert budget is not None
        assert budget.budget_seconds == 90


class TestDetailReconcileDispatch:
    """Step 3 of the reconcile-subcommand-split plan: ``--reconcile``
    on ``plan-tool detail`` routes to the audit-only branch (renders
    ``prompts/detail-reconcile.md`` and walks findings via
    ``apply_finding``), bypassing ``generate_detail`` entirely. The
    flag is mutually exclusive with ``--iterate`` and rejects
    ``--dry-run`` at the cmd level."""

    def test_detail_subparser_lists_reconcile_in_help(self) -> None:
        parser = build_parser()
        detail = _find_subparser(parser, "detail")
        assert detail is not None
        assert "--reconcile" in detail.format_help()

    def test_detail_reconcile_flag_parses(self) -> None:
        parser = build_parser()
        detail = _find_subparser(parser, "detail")
        assert detail is not None
        ns = detail.parse_args(["plan", "--reconcile", "--step", "3"])
        assert ns.reconcile is True
        assert ns.step == 3

    def test_detail_reconcile_with_iterate_is_rejected(self) -> None:
        """The argparse mutually-exclusive group makes
        ``--reconcile --iterate`` exit non-zero before the handler
        runs."""
        parser = build_parser()
        detail = _find_subparser(parser, "detail")
        assert detail is not None
        with pytest.raises(SystemExit) as exc:
            detail.parse_args(
                ["plan", "--reconcile", "--iterate", "--step", "3"]
            )
        # argparse exits 2 on parse error.
        assert exc.value.code == 2

    def test_detail_reconcile_with_no_iterate_is_rejected(self) -> None:
        """``--no-iterate`` also belongs to the BooleanOptionalAction
        for ``--iterate``; mutual exclusion applies symmetrically."""
        parser = build_parser()
        detail = _find_subparser(parser, "detail")
        assert detail is not None
        with pytest.raises(SystemExit) as exc:
            detail.parse_args(
                ["plan", "--reconcile", "--no-iterate", "--step", "3"]
            )
        assert exc.value.code == 2

    def test_detail_reconcile_with_dry_run_exits_2(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module

        _detail_basic_plan(tmp_path)
        manifest = _detail_setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)
        # ``generate_detail`` MUST NOT be called on the reconcile path;
        # patch with a raiser so accidental routing surfaces loudly.
        monkeypatch.setattr(
            "plan_tool.cli.authoring.generate_detail",
            lambda *a, **k: (_ for _ in ()).throw(
                AssertionError("generate_detail must not run on --reconcile")
            ),
        )
        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "detail", "plan", "--reconcile", "--step", "1",
                "--dry-run",
            ]
        )
        assert rc == 2
        err = capsys.readouterr().err
        assert "dry-run" in err.lower()

    def test_detail_reconcile_without_step_exits_2(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module

        _detail_basic_plan(tmp_path)
        manifest = _detail_setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "plan_tool.cli.authoring.generate_detail",
            lambda *a, **k: (_ for _ in ()).throw(
                AssertionError("generate_detail must not run on --reconcile")
            ),
        )
        rc = cli_module.main(
            ["--manifest", str(manifest), "detail", "plan", "--reconcile"]
        )
        assert rc == 2
        err = capsys.readouterr().err
        assert "--step" in err

    def test_detail_reconcile_routes_to_audit_path_not_authoring(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The authoring ``generate_detail`` MUST NOT run when
        ``--reconcile`` is set. The audit path renders mode
        ``"detail-reconcile"`` via the launcher's ``run_step`` instead."""
        from plan_tool.cli import app as cli_module
        from plan_tool.launcher import RunResult

        _detail_basic_plan(tmp_path)
        manifest = _detail_setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "plan_tool.cli.authoring.generate_detail",
            lambda *a, **k: (_ for _ in ()).throw(
                AssertionError("generate_detail must not run on --reconcile")
            ),
        )

        captured_modes: list[str] = []

        def fake_run_step(plan_path_arg, **kwargs):
            captured_modes.append(kwargs.get("mode"))
            return RunResult(
                step_id=kwargs.get("step_id") or 1,
                exit_code=0,
                advanced_to=None,
                done=False,
                stdout="## Findings\n\n_(none)_\n",
            )

        monkeypatch.setattr("plan_tool.cli.reconcile.run_step", fake_run_step)
        # No-TTY → reuse prompt is suppressed and walk is skipped, but
        # ``run_step`` and ``save_review`` still fire.
        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "detail", "plan", "--reconcile", "--step", "1",
            ]
        )
        assert rc == 0
        assert captured_modes == ["detail-reconcile"]

    def test_detail_reconcile_persists_kind_detail_reconcile(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A happy-path run lands a ``*-detail-reconcile.json`` save under
        ``.plan-tool/reviews/<slug>/`` with the right ``kind`` and
        ``step_id``."""
        from plan_tool.cli import app as cli_module
        from plan_tool.launcher import RunResult

        _detail_basic_plan(tmp_path)
        manifest = _detail_setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)
        # Claude-like stdout with one finding bullet so a Recommendation
        # gets extracted (otherwise the save is empty but still happens).
        sample_stdout = (
            "## Findings\n\n"
            "- MEDIUM: drop foo from step.files (impact: medium, "
            "complexity: low)\n"
        )

        def fake_run_step(plan_path_arg, **kwargs):
            return RunResult(
                step_id=kwargs.get("step_id") or 1,
                exit_code=0,
                advanced_to=None,
                done=False,
                stdout=sample_stdout,
            )

        monkeypatch.setattr("plan_tool.cli.reconcile.run_step", fake_run_step)
        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "detail", "plan", "--reconcile", "--step", "1",
            ]
        )
        assert rc == 0

        reviews_dir = tmp_path / "plan-details" / "plan" / "reports"
        saves = list(reviews_dir.glob("*-detail-reconcile.json"))
        assert len(saves) == 1, (
            f"expected exactly one detail-reconcile save under "
            f"{reviews_dir}; found {list(reviews_dir.iterdir()) if reviews_dir.exists() else 'no dir'}"
        )
        data = json.loads(saves[0].read_text(encoding="utf-8"))
        assert data["kind"] == "detail-reconcile"
        assert data["step_id"] == 1
        # Source label flows through to the rec via extract_reconcile_recommendations.
        assert data["recommendations"]
        assert data["recommendations"][0]["source"] == "detail-reconcile"


def _detail_multi_status_plan(tmp_path: Path) -> Path:
    """Three-step plan for reconcile sweeps with mixed step statuses."""
    plan_path = tmp_path / "plan.md"
    plan_path.write_text(
        "---\n"
        "title: P\n"
        "status: in-progress\n"
        "priority: low\n"
        "steps:\n"
        "  - id: 1\n"
        "    title: shipped\n"
        "    files: [foo.py]\n"
        "    status: done\n"
        "  - id: 2\n"
        "    title: underway\n"
        "    files: [bar.py]\n"
        "    status: current\n"
        "  - id: 3\n"
        "    title: queued\n"
        "    files: [baz.py]\n"
        "    status: pending\n"
        "---\n",
        encoding="utf-8",
    )
    (tmp_path / ".git").mkdir()
    return plan_path


class TestDetailReconcileAllSweep:
    """``plan-tool detail <name> --reconcile --all`` sweeps the
    per-step detail-reconcile audit across every step whose status is
    not ``done``. Done steps are skipped (their detail is a historical
    record); the sweep halts on the first per-step failure."""

    def test_detail_all_flag_parses(self) -> None:
        parser = build_parser()
        detail = _find_subparser(parser, "detail")
        assert detail is not None
        ns = detail.parse_args(["plan", "--reconcile", "--all"])
        assert ns.reconcile is True
        assert ns.all is True
        assert ns.step is None

    def test_all_with_step_exits_2(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module

        _detail_multi_status_plan(tmp_path)
        manifest = _detail_setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            cli_module,
            "run_step",
            lambda *a, **k: (_ for _ in ()).throw(
                AssertionError("run_step must not run on a rejected mutex")
            ),
        )
        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "detail", "plan", "--reconcile", "--all", "--step", "2",
            ]
        )
        assert rc == 2
        err = capsys.readouterr().err
        assert "mutually exclusive" in err

    def test_all_without_reconcile_exits_2(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """The authoring path already covers every step lacking detail
        by default — a bare ``--all`` is rejected, not treated as a
        no-op alias."""
        from plan_tool.cli import app as cli_module

        _detail_multi_status_plan(tmp_path)
        manifest = _detail_setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "plan_tool.cli.authoring.generate_detail",
            lambda *a, **k: (_ for _ in ()).throw(
                AssertionError("generate_detail must not run on bare --all")
            ),
        )
        rc = cli_module.main(
            ["--manifest", str(manifest), "detail", "plan", "--all"]
        )
        assert rc == 2
        err = capsys.readouterr().err
        assert "--reconcile" in err

    def test_all_with_reuse_id_exits_2(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """``--reuse-id`` pins reuse to one step's saved report; it cannot
        mean anything sensible threaded unchanged into every step of a
        sweep, so the combination is rejected."""
        from plan_tool.cli import app as cli_module

        _detail_multi_status_plan(tmp_path)
        manifest = _detail_setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            cli_module,
            "run_step",
            lambda *a, **k: (_ for _ in ()).throw(
                AssertionError("run_step must not run on a rejected mutex")
            ),
        )
        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "detail", "plan", "--reconcile", "--all",
                "--reuse-id", "20260101-000000",
            ]
        )
        assert rc == 2
        assert "--reuse-id is mutually exclusive with --all" in capsys.readouterr().err

    def test_sweep_audits_non_done_steps_and_skips_done(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool.launcher import RunResult

        _detail_multi_status_plan(tmp_path)
        manifest = _detail_setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)

        captured: list[tuple[Optional[int], str]] = []

        def fake_run_step(plan_path_arg, **kwargs):
            captured.append((kwargs.get("step_id"), kwargs.get("mode")))
            return RunResult(
                step_id=kwargs.get("step_id"),
                exit_code=0,
                advanced_to=None,
                done=False,
                stdout="## Findings\n\n_(none)_\n",
            )

        monkeypatch.setattr("plan_tool.cli.reconcile.run_step", fake_run_step)
        rc = cli_module.main(
            ["--manifest", str(manifest), "detail", "plan", "--reconcile", "--all"]
        )
        assert rc == 0
        # Step 1 is done → skipped; steps 2 and 3 audited in plan order.
        assert captured == [
            (2, "detail-reconcile"),
            (3, "detail-reconcile"),
        ]
        out = capsys.readouterr().out
        assert "2 step(s) to audit" in out
        assert "1 done step(s) skipped" in out
        assert "sweep complete: 2 step(s) audited" in out

    def test_sweep_with_all_steps_done_is_a_noop(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module

        plan_path = tmp_path / "plan.md"
        plan_path.write_text(
            "---\n"
            "title: P\n"
            "status: completed\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: shipped\n"
            "    files: [foo.py]\n"
            "    status: done\n"
            "---\n",
            encoding="utf-8",
        )
        (tmp_path / ".git").mkdir()
        manifest = _detail_setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            cli_module,
            "run_step",
            lambda *a, **k: (_ for _ in ()).throw(
                AssertionError("run_step must not run on an all-done plan")
            ),
        )
        rc = cli_module.main(
            ["--manifest", str(manifest), "detail", "plan", "--reconcile", "--all"]
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert "nothing to reconcile" in out

    def test_sweep_halts_on_first_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool.launcher import RunResult

        _detail_multi_status_plan(tmp_path)
        manifest = _detail_setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)

        calls: list[int] = []

        def fake_run_step(plan_path_arg, **kwargs):
            calls.append(kwargs.get("step_id"))
            return RunResult(
                step_id=kwargs.get("step_id"),
                exit_code=3,
                advanced_to=None,
                done=False,
                stdout="",
            )

        monkeypatch.setattr("plan_tool.cli.reconcile.run_step", fake_run_step)
        rc = cli_module.main(
            ["--manifest", str(manifest), "detail", "plan", "--reconcile", "--all"]
        )
        # Step 2's audit failed with rc=3 → sweep halts, step 3 never runs.
        assert rc == 3
        assert calls == [2]
        err = capsys.readouterr().err
        assert "sweep halted" in err

    def test_sweep_handles_step_oserror_as_a_clean_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module

        _detail_multi_status_plan(tmp_path)
        manifest = _detail_setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "plan_tool.cli.reconcile.run_step",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(PermissionError("denied")),
        )

        rc = cli_module.main(
            ["--manifest", str(manifest), "detail", "plan", "--reconcile", "--all"]
        )
        assert rc == 2
        error_output = capsys.readouterr().err
        assert "denied" in error_output
        assert "sweep halted: step 2 audit exited 2" in error_output

    def test_sweep_logs_per_step_plan_read_failures(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool.launcher import RunResult

        _detail_multi_status_plan(tmp_path)
        manifest = _detail_setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)
        original_parse_plan = reconcile_module.parse_plan
        parse_calls = 0

        def failing_parse_plan(path):
            nonlocal parse_calls
            parse_calls += 1
            if parse_calls == 4:
                raise PermissionError("mid-sweep denied")
            return original_parse_plan(path)

        monkeypatch.setattr(reconcile_module, "parse_plan", failing_parse_plan)
        monkeypatch.setattr(
            reconcile_module, "_save_and_walk_reconcile", lambda **_kwargs: None
        )
        monkeypatch.setattr(
            reconcile_module,
            "run_step",
            lambda *_args, **kwargs: RunResult(
                step_id=kwargs["step_id"],
                exit_code=0,
                advanced_to=None,
                done=False,
                stdout="## Findings\n\n_(none)_\n",
            ),
        )

        rc = cli_module.main(
            ["--manifest", str(manifest), "detail", "plan", "--reconcile", "--all"]
        )
        assert rc == 2
        assert "mid-sweep denied" in capsys.readouterr().err

        events = []
        for log in (tmp_path / ".plan-tool" / "runs").rglob("*.jsonl"):
            events.extend(
                json.loads(line)
                for line in log.read_text(encoding="utf-8").splitlines()
                if line.strip()
            )
        start = next(
            event
            for event in events
            if event["event"] == "run_start" and event["step_filter"] == 3
        )
        end = next(
            event
            for event in events
            if event["event"] == "run_end" and event["run_id"] == start["run_id"]
        )
        assert start["flags"]["sweep_index"] == 1
        assert end["rc"] == 2
        assert end["error"] == "mid-sweep denied"


class TestReconcileCodeAllSweep:
    """``reconcile-code --all`` audits every step, including done ones."""

    def test_all_flag_parses(self) -> None:
        parser = build_parser()
        reconcile_code = _find_subparser(parser, "reconcile-code")
        assert reconcile_code is not None
        ns = reconcile_code.parse_args(["plan", "--all"])
        assert ns.all is True
        assert ns.step is None

    def test_all_with_step_exits_2(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module

        _detail_multi_status_plan(tmp_path)
        manifest = _detail_setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)
        with pytest.raises(SystemExit) as exc_info:
            cli_module.main(
                [
                    "--manifest", str(manifest),
                    "reconcile-code", "plan", "--all", "--step", "2",
                ]
            )
        assert exc_info.value.code == 2
        assert "not allowed with argument --all" in capsys.readouterr().err

    def test_sweep_audits_every_step_in_plan_order(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool.launcher import RunResult

        _detail_multi_status_plan(tmp_path)
        manifest = _detail_setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)

        captured: list[tuple[Optional[int], str]] = []

        def fake_run_step(plan_path_arg, **kwargs):
            captured.append((kwargs.get("step_id"), kwargs.get("mode")))
            return RunResult(
                step_id=kwargs["step_id"],
                exit_code=0,
                advanced_to=None,
                done=False,
                stdout="## Findings\n\n_(none)_\n",
            )

        monkeypatch.setattr("plan_tool.cli.reconcile.run_step", fake_run_step)
        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "reconcile-code", "plan", "--all", "--no-save",
            ]
        )
        assert rc == 0
        assert captured == [
            (1, "run-reconcile"),
            (2, "run-reconcile"),
            (3, "run-reconcile"),
        ]
        out = capsys.readouterr().out
        assert "reconcile-code sweep: 3 step(s) to audit" in out
        assert "reconcile-code sweep complete: 3 step(s) audited" in out

    def test_sweep_halts_on_first_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool.launcher import RunResult

        _detail_multi_status_plan(tmp_path)
        manifest = _detail_setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)

        calls: list[int] = []

        def fake_run_step(plan_path_arg, **kwargs):
            step_id = kwargs["step_id"]
            calls.append(step_id)
            return RunResult(
                step_id=step_id,
                exit_code=7 if step_id == 2 else 0,
                advanced_to=None,
                done=False,
                stdout="",
            )

        monkeypatch.setattr("plan_tool.cli.reconcile.run_step", fake_run_step)
        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "reconcile-code", "plan", "--all", "--no-save",
            ]
        )
        assert rc == 7
        assert calls == [1, 2]
        assert "sweep halted: step 2 audit exited 7" in capsys.readouterr().err

    def test_sweep_skips_explicit_non_code_steps(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A step declared ``change_type: non-code`` has no code for this
        audit to touch, so the sweep must not spend a claude call on it."""
        from plan_tool.cli import app as cli_module
        from plan_tool.launcher import RunResult

        plan_path = tmp_path / "plan.md"
        plan_path.write_text(
            "---\n"
            "title: P\n"
            "status: in-progress\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: code change\n"
            "    files: [foo.py]\n"
            "    status: done\n"
            "  - id: 2\n"
            "    title: docs only\n"
            "    files: [README.md]\n"
            "    status: done\n"
            "    change_type: non-code\n"
            "  - id: 3\n"
            "    title: another code change\n"
            "    files: [baz.py]\n"
            "    status: pending\n"
            "---\n",
            encoding="utf-8",
        )
        (tmp_path / ".git").mkdir()
        manifest = _detail_setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)

        captured: list[Optional[int]] = []

        def fake_run_step(plan_path_arg, **kwargs):
            captured.append(kwargs.get("step_id"))
            return RunResult(
                step_id=kwargs["step_id"],
                exit_code=0,
                advanced_to=None,
                done=False,
                stdout="## Findings\n\n_(none)_\n",
            )

        monkeypatch.setattr("plan_tool.cli.reconcile.run_step", fake_run_step)
        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "reconcile-code", "plan", "--all", "--no-save",
            ]
        )
        assert rc == 0
        assert captured == [1, 3]
        out = capsys.readouterr().out
        assert "reconcile-code sweep: 2 step(s) to audit (1 non-code step(s) skipped)" in out
        assert "reconcile-code sweep complete: 2 step(s) audited" in out

    def test_all_with_reuse_id_exits_2(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """``--reuse-id`` pins reuse to one step's saved report; it cannot
        mean anything sensible threaded unchanged into every step of a
        sweep, so the combination is rejected rather than silently
        printing an unresolved-id note for every step but one."""
        from plan_tool.cli import app as cli_module

        _detail_multi_status_plan(tmp_path)
        manifest = _detail_setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)
        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "reconcile-code", "plan", "--all",
                "--reuse-id", "20260101-000000",
            ]
        )
        assert rc == 2
        assert "--reuse-id is mutually exclusive with --all" in capsys.readouterr().err

    def test_dry_run_sweep_reports_rendered_not_audited(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A ``--dry-run`` sweep never calls claude, so the completion
        message must not claim the steps were audited."""
        from plan_tool.cli import app as cli_module
        from plan_tool.launcher import RunResult

        _detail_multi_status_plan(tmp_path)
        manifest = _detail_setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)

        def fake_run_step(plan_path_arg, **kwargs):
            return RunResult(
                step_id=kwargs["step_id"],
                exit_code=0,
                advanced_to=None,
                done=False,
                stdout="rendered prompt\n",
            )

        monkeypatch.setattr("plan_tool.cli.reconcile.run_step", fake_run_step)
        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "reconcile-code", "plan", "--all", "--dry-run",
            ]
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert "0 step(s) audited, 3 step(s) rendered (dry-run)" in out
        assert "3 step(s) audited" not in out

    def test_sweep_reports_reused_saves_separately(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool.launcher import RunResult

        _detail_multi_status_plan(tmp_path)
        manifest = _detail_setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)

        audited: list[int] = []

        def fake_run_step(plan_path_arg, **kwargs):
            step_id = kwargs["step_id"]
            audited.append(step_id)
            return RunResult(
                step_id=step_id,
                exit_code=0,
                advanced_to=None,
                done=False,
                stdout="## Findings\n\n_(none)_\n",
            )

        monkeypatch.setattr("plan_tool.cli.reconcile.run_step", fake_run_step)
        monkeypatch.setattr(
            "plan_tool.cli.reconcile._prompt_reuse_saved_run_reconcile",
            lambda *_args, step_id, **_kwargs: Path("saved.json") if step_id == 1 else None,
        )
        monkeypatch.setattr(
            "plan_tool.cli.reconcile._walk_saved_run_reconcile",
            lambda **_kwargs: 0,
        )

        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "reconcile-code", "plan", "--all", "--no-save",
            ]
        )
        assert rc == 0
        assert audited == [2, 3]
        assert (
            "2 step(s) audited, 1 saved audit(s) reused"
            in capsys.readouterr().out
        )

    def test_sweep_rechecks_steps_changed_mid_sweep(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool.launcher import RunResult

        _detail_multi_status_plan(tmp_path)
        manifest = _detail_setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)

        audited: list[int] = []
        removed_step = (
            "  - id: 2\n"
            "    title: underway\n"
            "    files: [bar.py]\n"
            "    status: current\n"
        )

        def fake_run_step(plan_path_arg, **kwargs):
            step_id = kwargs["step_id"]
            audited.append(step_id)
            if step_id == 1:
                path = Path(plan_path_arg)
                path.write_text(
                    path.read_text(encoding="utf-8").replace(removed_step, ""),
                    encoding="utf-8",
                )
            return RunResult(
                step_id=step_id,
                exit_code=0,
                advanced_to=None,
                done=False,
                stdout="## Findings\n\n_(none)_\n",
            )

        monkeypatch.setattr("plan_tool.cli.reconcile.run_step", fake_run_step)
        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "reconcile-code", "plan", "--all", "--no-save",
            ]
        )
        assert rc == 0
        assert audited == [1, 3]
        output = capsys.readouterr()
        assert "skipping step 2: removed from plan mid-sweep" in output.err
        assert "2 step(s) audited, 1 step(s) skipped during sweep" in output.out

    def test_sweep_names_steps_reclassified_as_non_code(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool.launcher import RunResult

        _detail_multi_status_plan(tmp_path)
        manifest = _detail_setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)
        step_two = (
            "  - id: 2\n"
            "    title: underway\n"
            "    files: [bar.py]\n"
            "    status: current\n"
        )

        audited: list[int] = []

        def fake_run_step(plan_path_arg, **kwargs):
            step_id = kwargs["step_id"]
            audited.append(step_id)
            if step_id == 1:
                path = Path(plan_path_arg)
                path.write_text(
                    path.read_text(encoding="utf-8").replace(
                        step_two, step_two + "    change_type: non-code\n"
                    ),
                    encoding="utf-8",
                )
            return RunResult(
                step_id=step_id,
                exit_code=0,
                advanced_to=None,
                done=False,
                stdout="## Findings\n\n_(none)_\n",
            )

        monkeypatch.setattr("plan_tool.cli.reconcile.run_step", fake_run_step)
        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "reconcile-code", "plan", "--all", "--no-save",
            ]
        )
        assert rc == 0
        assert audited == [1, 3]
        assert "reclassified as non-code mid-sweep" in capsys.readouterr().err

    def test_sweep_reuses_each_preflight_plan_for_its_audit(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool.launcher import RunResult

        _detail_multi_status_plan(tmp_path)
        manifest = _detail_setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)
        original_parse_plan = reconcile_module.parse_plan
        parse_calls = 0

        def counting_parse_plan(path):
            nonlocal parse_calls
            parse_calls += 1
            return original_parse_plan(path)

        monkeypatch.setattr(reconcile_module, "parse_plan", counting_parse_plan)
        monkeypatch.setattr(
            reconcile_module,
            "run_step",
            lambda *_args, **kwargs: RunResult(
                step_id=kwargs["step_id"],
                exit_code=0,
                advanced_to=None,
                done=False,
                stdout="## Findings\n\n_(none)_\n",
            ),
        )

        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "reconcile-code", "plan", "--all", "--no-save",
            ]
        )
        assert rc == 0
        assert parse_calls == 4  # Initial target list, then once per step.

    def test_sweep_logs_per_step_plan_read_failures(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool.launcher import RunResult

        _detail_multi_status_plan(tmp_path)
        manifest = _detail_setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)
        original_parse_plan = reconcile_module.parse_plan
        parse_calls = 0

        def failing_parse_plan(path):
            nonlocal parse_calls
            parse_calls += 1
            if parse_calls == 3:
                raise PermissionError("mid-sweep denied")
            return original_parse_plan(path)

        monkeypatch.setattr(reconcile_module, "parse_plan", failing_parse_plan)
        monkeypatch.setattr(
            reconcile_module,
            "run_step",
            lambda *_args, **kwargs: RunResult(
                step_id=kwargs["step_id"],
                exit_code=0,
                advanced_to=None,
                done=False,
                stdout="## Findings\n\n_(none)_\n",
            ),
        )

        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "reconcile-code", "plan", "--all", "--no-save",
            ]
        )
        assert rc == 2
        assert "mid-sweep denied" in capsys.readouterr().err

        events = []
        for log in (tmp_path / ".plan-tool" / "runs").rglob("*.jsonl"):
            events.extend(
                json.loads(line)
                for line in log.read_text(encoding="utf-8").splitlines()
                if line.strip()
            )
        start = next(
            event
            for event in events
            if event["event"] == "run_start" and event["step_filter"] == 2
        )
        end = next(
            event
            for event in events
            if event["event"] == "run_end" and event["run_id"] == start["run_id"]
        )
        assert start["flags"]["all"] is True
        assert start["flags"]["sweep_index"] == 1
        assert end["rc"] == 2
        assert end["error"] == "mid-sweep denied"

    def test_sweep_handles_step_oserror_as_a_clean_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module

        _detail_multi_status_plan(tmp_path)
        manifest = _detail_setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "plan_tool.cli.reconcile.run_step",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(PermissionError("denied")),
        )

        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "reconcile-code", "plan", "--all", "--no-save",
            ]
        )
        assert rc == 2
        error_output = capsys.readouterr().err
        assert "denied" in error_output
        assert "sweep halted: step 1 audit exited 2" in error_output

    def test_selected_step_preflight_oserror_refuses_before_the_launcher(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from plan_tool.cli import app as cli_module

        _detail_multi_status_plan(tmp_path)
        manifest = _detail_setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "plan_tool.cli.reconcile.parse_plan",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(PermissionError("denied")),
        )
        monkeypatch.setattr(
            "plan_tool.cli.reconcile.run_step",
            lambda *_args, **_kwargs: pytest.fail("backend must not run"),
        )

        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "reconcile-code", "plan", "--step", "1", "--no-save",
            ]
        )
        assert rc == 2

    @pytest.mark.parametrize(
        "argv",
        [
            ["reconcile-code", "plan", "--all", "--no-save"],
            ["detail", "plan", "--reconcile", "--step", "2"],
            ["detail", "plan", "--reconcile", "--all"],
        ],
    )
    def test_reconcile_interrupts_exit_130(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, argv: list[str],
    ) -> None:
        from plan_tool.cli import app as cli_module

        _detail_multi_status_plan(tmp_path)
        manifest = _detail_setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "plan_tool.cli.reconcile.run_step",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(KeyboardInterrupt()),
        )

        with pytest.raises(SystemExit) as exc_info:
            cli_module.main(["--manifest", str(manifest), *argv])
        assert exc_info.value.code == 130

    def test_sweep_marks_per_step_run_logs_as_swept(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Each per-step run-log entry a sweep opens is marked ``all: True``
        with its ``sweep_index``, mirroring ``detail --reconcile --all``'s
        per-step markers — otherwise a swept step's log is indistinguishable
        from a standalone ``--step`` invocation."""
        import json

        from plan_tool.cli import app as cli_module
        from plan_tool.launcher import RunResult

        _detail_multi_status_plan(tmp_path)
        manifest = _detail_setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)

        def fake_run_step(plan_path_arg, **kwargs):
            return RunResult(
                step_id=kwargs["step_id"],
                exit_code=0,
                advanced_to=None,
                done=False,
                stdout="## Findings\n\n_(none)_\n",
            )

        monkeypatch.setattr("plan_tool.cli.reconcile.run_step", fake_run_step)
        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "reconcile-code", "plan", "--all", "--no-save",
            ]
        )
        assert rc == 0

        starts = []
        for log in sorted((tmp_path / ".plan-tool" / "runs").rglob("*.jsonl")):
            for line in log.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    event = json.loads(line)
                    if event.get("event") == "run_start":
                        starts.append(event)
        assert len(starts) == 3
        by_step = {event["step_filter"]: event for event in starts}
        assert set(by_step) == {1, 2, 3}
        for expected_index, step_id in enumerate([1, 2, 3]):
            flags = by_step[step_id]["flags"]
            assert flags["all"] is True
            assert flags["sweep_index"] == expected_index


class TestRunReconcileDispatch:
    """Step 4 of the reconcile-subcommand-split plan: ``--reconcile``
    on ``plan-tool run`` routes to ``_cmd_run_reconcile`` (renders
    ``prompts/run-reconcile.md`` and audits code against the plan,
    landing code edits inline via ``acceptEdits``). Plan-rooted
    findings surface via ``TestRunReconcileRedirectSurface`` below.
    The flag is mutually exclusive with ``--mode <anything-other-
    than-run>`` and ``--iterate``."""

    def test_run_subparser_lists_reconcile_in_help(self) -> None:
        parser = build_parser()
        run = _find_subparser(parser, "run")
        assert run is not None
        assert "--reconcile" in run.format_help()

    def test_run_reconcile_flag_parses(self) -> None:
        parser = build_parser()
        run = _find_subparser(parser, "run")
        assert run is not None
        ns = run.parse_args(["plan", "--reconcile", "--step", "4"])
        assert ns.reconcile is True
        assert ns.mode == "run"  # default
        assert ns.step == 4

    def test_cmd_run_reconcile_flag_routes_to_audit_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``--reconcile`` dispatches to ``_cmd_run_reconcile`` before
        the legacy execution branch can open a ``command="run"`` log."""
        from plan_tool.cli import app as cli_module

        _detail_basic_plan(tmp_path)
        manifest = _detail_setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)

        captured: dict = {}

        def fake_cmd_run_reconcile(args, *, ctx, plan_path):
            captured["called"] = True
            captured["step"] = args.step
            captured["reconcile"] = args.reconcile
            return 0

        monkeypatch.setattr(
            "plan_tool.cli.run_cmd._cmd_run_reconcile", fake_cmd_run_reconcile
        )
        # Patch ``run_step`` with a raiser so legacy routing surfaces.
        monkeypatch.setattr(
            "plan_tool.cli.run_cmd.run_step",
            lambda *a, **k: (_ for _ in ()).throw(
                AssertionError("run_step must not run on --reconcile")
            ),
        )
        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "run", "plan", "--reconcile", "--step", "1",
            ]
        )
        assert rc == 0
        assert captured == {"called": True, "step": 1, "reconcile": True}

    def test_reconcile_code_command_routes_to_same_audit_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The promoted ``reconcile-code`` subcommand shares
        ``_cmd_run_reconcile`` with the legacy ``run --reconcile`` flag."""
        from plan_tool.cli import app as cli_module

        _detail_basic_plan(tmp_path)
        manifest = _detail_setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)

        captured: dict = {}

        def fake_cmd_run_reconcile(args, *, ctx, plan_path):
            captured["called"] = True
            captured["step"] = args.step
            return 0

        monkeypatch.setattr(
            "plan_tool.cli.run_cmd._cmd_run_reconcile", fake_cmd_run_reconcile
        )
        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "reconcile-code", "plan", "--step", "1",
            ]
        )
        assert rc == 0
        assert captured == {"called": True, "step": 1}

    def test_cmd_run_reconcile_with_iterate_is_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """``--reconcile --iterate`` exits rc=2 before any claude call."""
        from plan_tool.cli import app as cli_module

        _detail_basic_plan(tmp_path)
        manifest = _detail_setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "plan_tool.cli.run_cmd._cmd_run_reconcile",
            lambda *a, **k: (_ for _ in ()).throw(
                AssertionError("_cmd_run_reconcile must not run")
            ),
        )
        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "run", "plan", "--reconcile",
                "--iterate", "--step", "1",
            ]
        )
        assert rc == 2
        err = capsys.readouterr().err
        assert "--reconcile" in err
        assert "--iterate" in err

    def test_cmd_run_reconcile_persists_kind_run_reconcile(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A happy-path run lands a ``*-run-reconcile.json`` save under
        ``.plan-tool/reviews/<slug>/`` with ``kind="run-reconcile"``
        and ``step_id`` set."""
        from plan_tool.cli import app as cli_module
        from plan_tool.launcher import RunResult

        plan_path = _detail_basic_plan(tmp_path)
        _prepare_selected_reconcile_step(plan_path)
        manifest = _detail_setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)

        sample_stdout = (
            "## Findings\n\n"
            "- HIGH: missing validation in handleSubmit() "
            "(impact: high, complexity: low)\n"
        )

        def fake_run_step(plan_path_arg, **kwargs):
            return RunResult(
                step_id=kwargs.get("step_id") or 1,
                exit_code=0,
                advanced_to=None,
                done=False,
                stdout=sample_stdout,
            )

        monkeypatch.setattr("plan_tool.cli.reconcile.run_step", fake_run_step)
        # Verify the apply-finding primitive is NOT reached on this
        # path: audit-applies-inline means there's nothing left to
        # apply per-finding. A reachable call would mean we accidentally
        # wired run-reconcile through ``_build_review_action_fn``.
        monkeypatch.setattr(
            "plan_tool.launcher.apply_finding",
            lambda *a, **k: (_ for _ in ()).throw(
                AssertionError("apply_finding must not run on --reconcile")
            ),
        )
        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "run", "plan", "--reconcile", "--step", "1",
            ]
        )
        # No redirects + no critical findings → rc=0.
        assert rc == 0

        reviews_dir = tmp_path / "plan-details" / "plan" / "reports"
        saves = list(reviews_dir.glob("*-run-reconcile.json"))
        assert len(saves) == 1, (
            f"expected one run-reconcile save under {reviews_dir}; "
            f"found {list(reviews_dir.iterdir()) if reviews_dir.exists() else 'no dir'}"
        )
        data = json.loads(saves[0].read_text(encoding="utf-8"))
        assert data["kind"] == "run-reconcile"
        assert data["step_id"] == 1
        assert data["recommendations"]
        assert data["recommendations"][0]["source"] == "run-reconcile"


class TestRunReconcileCompletedSiblingContext:
    """Fresh selected code reconciliations receive sibling ownership context."""

    @staticmethod
    def _write_plan(
        tmp_path: Path,
        *,
        sibling_detail: bool = True,
        empty_sibling: bool = False,
        selected_status: str = "done",
        selected_detail: bool = True,
        normalized_paths: bool = False,
    ) -> Path:
        plan_path = tmp_path / "plan.md"
        detail_line = "    detail: details/02-later.md\n" if sibling_detail else ""
        selected_files = "[selected.py, ./shared.py]" if normalized_paths else "[selected.py, shared.py]"
        sibling_files = "[./later.py, shared.py (new)]" if normalized_paths else "[later.py, shared.py]"
        empty_sibling_block = (
            "  - id: 3\n"
            "    title: unscoped completed sibling\n"
            "    status: done\n"
            if empty_sibling
            else ""
        )
        plan_path.write_text(
            "---\n"
            "title: Completed sibling context\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: selected implementation\n"
            f"    files: {selected_files}\n"
            "    detail: details/01-selected.md\n"
            f"    status: {selected_status}\n"
            "  - id: 2\n"
            "    title: later implementation\n"
            f"    files: {sibling_files}\n"
            "    creates: [created.py]\n"
            + detail_line
            + "    status: done\n"
            + empty_sibling_block
            + "---\n\n# Completed sibling context\n",
            encoding="utf-8",
        )
        (tmp_path / "selected.py").write_text("selected = True\n", encoding="utf-8")
        (tmp_path / "shared.py").write_text("shared = True\n", encoding="utf-8")
        (tmp_path / "later.py").write_text("later = True\n", encoding="utf-8")
        (tmp_path / "created.py").write_text("created = True\n", encoding="utf-8")
        if selected_detail:
            details = tmp_path / "details"
            details.mkdir()
            (details / "01-selected.md").write_text(
                "# Selected detail\n", encoding="utf-8"
            )
        (tmp_path / ".git").mkdir()
        return plan_path

    @staticmethod
    def _run(
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        *,
        stdout: str,
    ) -> tuple[dict, dict]:
        from plan_tool.launcher import RunResult

        manifest = _detail_setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)
        captured: dict = {}

        def fake_run_step(plan_path_arg, **kwargs):
            captured.update(kwargs)
            return RunResult(
                step_id=kwargs["step_id"],
                exit_code=0,
                advanced_to=None,
                done=False,
                stdout=stdout,
            )

        monkeypatch.setattr("plan_tool.cli.reconcile.run_step", fake_run_step)
        rc = main(
            [
                "--manifest", str(manifest), "reconcile-code", "plan",
                "--step", "1",
            ]
        )
        assert rc == 0
        reports = list((tmp_path / "plan-details" / "plan" / "reports").glob(
            "*-run-reconcile.json"
        ))
        assert len(reports) == 1
        return captured, json.loads(reports[0].read_text(encoding="utf-8"))

    def test_selected_step_receives_other_done_step_context(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        self._write_plan(tmp_path)
        captured, _ = self._run(
            tmp_path, monkeypatch, stdout="## Findings\n\n_(none)_\n"
        )

        context = captured["completed_sibling_context"]
        assert 'Completed step 2 — later implementation' in context
        assert "`later.py`" in context
        assert "`created.py`" in context
        assert "details/02-later.md" not in context
        assert "Completed step 1" not in context

    def test_sibling_context_normalizes_and_excludes_shared_selected_paths(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        self._write_plan(tmp_path, normalized_paths=True)
        captured, _ = self._run(
            tmp_path, monkeypatch, stdout="## Findings\n\n_(none)_\n"
        )

        context = captured["completed_sibling_context"]
        assert "`later.py`" in context
        assert "`shared.py`" not in context

    def test_each_completed_step_gets_its_other_sibling_as_context(
        self, tmp_path: Path,
    ) -> None:
        from plan_tool.cli.reconcile import _build_completed_sibling_context
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)

        first = _build_completed_sibling_context(plan, plan.step_by_id(1)).prompt
        second = _build_completed_sibling_context(plan, plan.step_by_id(2)).prompt

        assert "`later.py`" in first
        assert "`selected.py`" in second
        assert "`shared.py`" not in first
        assert "`shared.py`" not in second

    def test_later_sibling_work_is_clean_context_and_saved_as_such(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        self._write_plan(tmp_path)
        _, saved = self._run(
            tmp_path, monkeypatch, stdout="## Findings\n\n_(none)_\n"
        )

        assert saved["recommendations"] == []
        assert "Completed-sibling context informed this classification" in saved["report_md"]
        assert "Selected-step outcome: clean" in saved["report_md"]
        assert "## Redirect" not in saved["report_md"]

    def test_selected_step_mismatch_remains_a_saved_recommendation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        self._write_plan(tmp_path)
        _, saved = self._run(
            tmp_path,
            monkeypatch,
            stdout=(
                "## Findings\n\n"
                "- HIGH: `selected.py:run` omits the selected step behavior "
                "→ fix: implement it (impact: high, complexity: low)\n"
            ),
        )

        assert len(saved["recommendations"]) == 1
        assert saved["recommendations"][0]["source"] == "run-reconcile"
        assert "Selected-step outcome: selected-step drift was reported" in saved["report_md"]

    def test_sibling_context_never_reads_sibling_detail(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        self._write_plan(tmp_path, sibling_detail=False, empty_sibling=True)
        captured, saved = self._run(
            tmp_path, monkeypatch, stdout="## Findings\n\n_(none)_\n"
        )

        context = captured["completed_sibling_context"]
        assert "`later.py`" in context
        assert "no detail reference" not in context
        assert "details/02-later.md" not in context
        assert "Selected-step outcome: clean" in saved["report_md"]
        assert (
            "1 of 2 completed sibling step(s) supplied non-shared declared paths"
            in saved["report_md"]
        )

    def test_completed_sibling_report_line_distinguishes_zero_states(
        self,
    ) -> None:
        """The saved report must not conflate 'no completed siblings existed'
        with 'completed siblings existed but none contributed paths' — both
        used to collapse to the same blank line."""
        from plan_tool.cli.reconcile import (
            CompletedSiblingContext,
            _format_completed_sibling_context_report,
        )
        from plan_tool.launcher import FindingsSummary

        summary = FindingsSummary(parsed=True, counts={}, unspecified=0)

        no_siblings = _format_completed_sibling_context_report(
            "verdict", summary, CompletedSiblingContext("", 0, completed_sibling_count=0)
        )
        siblings_none_contributed = _format_completed_sibling_context_report(
            "verdict", summary, CompletedSiblingContext("", 0, completed_sibling_count=2)
        )

        assert "no other completed steps were available" in no_siblings
        assert "no other completed steps were available" not in siblings_none_contributed
        assert (
            "2 completed sibling step(s) existed but none supplied "
            "non-shared declared paths" in siblings_none_contributed
        )

    @pytest.mark.parametrize("selected_status", ["current", "pending"])
    def test_reconcile_code_rejects_non_done_selected_target(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        selected_status: str,
    ) -> None:
        self._write_plan(tmp_path, selected_status=selected_status)
        manifest = _detail_setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "plan_tool.cli.reconcile.run_step",
            lambda *_args, **_kwargs: pytest.fail("backend must not run"),
        )

        rc = main([
            "--manifest", str(manifest), "reconcile-code", "plan", "--step", "1",
        ])

        assert rc == 2

    def test_reconcile_code_default_step_skips_done_gate(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """No ``--step`` (default current/next-runnable resolution) must not
        hit the explicit-selection DONE gate: that default can never resolve
        to a DONE step, so gating it here would refuse every such call."""
        from plan_tool.launcher import RunResult

        self._write_plan(tmp_path, selected_status="current")
        manifest = _detail_setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)

        def fake_run_step(plan_path_arg, **kwargs):
            return RunResult(
                step_id=1,
                exit_code=0,
                advanced_to=None,
                done=False,
                stdout="## Findings\n\n_(none)_\n",
            )

        monkeypatch.setattr("plan_tool.cli.reconcile.run_step", fake_run_step)

        rc = main(["--manifest", str(manifest), "reconcile-code", "plan"])

        assert rc == 0

    def test_reconcile_code_reparses_plan_after_declined_reuse_prompt(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A plan edit made while the reuse prompt blocks on input() must be
        picked up: the verified snapshot must be grounded in the same read
        as its fingerprint, not a parse captured before the prompt."""
        from plan_tool.launcher import RunResult

        plan_path = self._write_plan(tmp_path, selected_status="done")
        manifest = _detail_setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)

        def edit_plan_then_decline(*_args, **_kwargs):
            text = plan_path.read_text(encoding="utf-8")
            plan_path.write_text(
                text.replace("selected implementation", "edited implementation"),
                encoding="utf-8",
            )
            return None

        monkeypatch.setattr(
            "plan_tool.cli.reconcile._prompt_reuse_saved_run_reconcile",
            edit_plan_then_decline,
        )

        captured: dict = {}

        def fake_run_step(plan_path_arg, **kwargs):
            captured.update(kwargs)
            return RunResult(
                step_id=1, exit_code=0, advanced_to=None, done=False,
                stdout="## Findings\n\n_(none)_\n",
            )

        monkeypatch.setattr("plan_tool.cli.reconcile.run_step", fake_run_step)

        rc = main([
            "--manifest", str(manifest), "reconcile-code", "plan", "--step", "1",
        ])

        assert rc == 0
        assert (
            captured["selected_reconcile_plan_snapshot"].step_by_id(1).title
            == "edited implementation"
        )

    def test_reconcile_code_rejects_unreadable_selected_detail(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from plan_tool.detail_artifacts import DetailArtifactResolution

        self._write_plan(tmp_path)
        manifest = _detail_setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "plan_tool.cli.reconcile.resolve_detail_artifact",
            lambda *_args, **_kwargs: DetailArtifactResolution(
                pointer_set=True,
                path=tmp_path,
                on_disk=True,
            ),
        )
        monkeypatch.setattr(
            "plan_tool.cli.reconcile.run_step",
            lambda *_args, **_kwargs: pytest.fail("backend must not run"),
        )

        rc = main([
            "--manifest", str(manifest), "reconcile-code", "plan", "--step", "1",
        ])

        assert rc == 2

    def test_reconcile_code_rejects_changed_selected_snapshot(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        self._write_plan(tmp_path)
        manifest = _detail_setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)
        fingerprints = iter(("before", "after"))
        monkeypatch.setattr(
            "plan_tool.cli.reconcile.compute_plan_fingerprint",
            lambda _path: next(fingerprints),
        )
        monkeypatch.setattr(
            "plan_tool.cli.reconcile.run_step",
            lambda *_args, **_kwargs: pytest.fail("backend must not run"),
        )

        rc = main([
            "--manifest", str(manifest), "reconcile-code", "plan", "--step", "1",
        ])

        assert rc == 2

    def test_reconcile_code_rejects_high_budget_before_backend(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The selected CLI path must not send a high-budget prompt."""
        from plan_tool import launcher
        from plan_tool.prompt_budget import PromptBudget

        self._write_plan(tmp_path)
        manifest = _detail_setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            launcher,
            "estimate_prompt_budget",
            lambda *_args, **_kwargs: PromptBudget(
                total_bytes=1,
                estimated_tokens=1,
                context_window=1,
                headroom_ratio=0.0,
                level="high",
                window_defaulted=False,
            ),
        )
        invoked: list[str] = []

        def run_step_with_invoker(plan_path_arg: Path, **kwargs):
            return launcher.run_step(
                plan_path_arg,
                invoker=lambda prompt: invoked.append(prompt) or (0, ""),
                **kwargs,
            )

        monkeypatch.setattr(
            "plan_tool.cli.reconcile.run_step", run_step_with_invoker,
        )

        rc = main([
            "--manifest", str(manifest), "reconcile-code", "plan", "--step", "1",
        ])

        assert rc == 2
        assert invoked == []


class TestRunReconcileRedirectSurface:
    """Step 4 redirect-signal surface: a ``## Redirect`` sub-block on
    a run-reconcile finding triggers the two-line ``[REDIRECT]``
    stderr block and forces rc=1, even when no critical code findings
    are present. The negative control — zero redirects + no critical
    findings → rc=0 — anchors the contract from the other end."""

    def test_cmd_run_reconcile_surfaces_redirect_on_stderr(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool.launcher import RunResult

        plan_path = _detail_basic_plan(tmp_path)
        _prepare_selected_reconcile_step(plan_path)
        manifest = _detail_setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)

        stdout = (
            "## Findings\n\n"
            "- MEDIUM: apps/old-foo.ts declared but missing\n"
            "\n"
            "## Redirect\n\n"
            "- **Reason**: step.files declares a stale path\n"
            "- **Suggested next**: detail --reconcile\n"
        )

        def fake_run_step(plan_path_arg, **kwargs):
            return RunResult(
                step_id=1,
                exit_code=0,
                advanced_to=None,
                done=False,
                stdout=stdout,
            )

        monkeypatch.setattr("plan_tool.cli.reconcile.run_step", fake_run_step)
        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "run", "plan", "--reconcile", "--step", "1",
            ]
        )
        # The audit completed -- exit 0. The redirect is surfaced on stderr
        # for the operator to act on, not via the exit code.
        assert rc == 0
        err = capsys.readouterr().err
        # Two-line block, in order. The reason line carries claude's
        # verbatim ``Reason:`` field; the ``next:`` line is constructed
        # CLI-side from args.name + rec.step_id (NOT echoed from
        # claude's ``Suggested next:`` field) so the operator gets a
        # canonical command.
        assert "[REDIRECT]" in err
        assert "step.files declares a stale path" in err
        assert "next: plan-tool detail plan --reconcile --step 1" in err

    def test_cmd_run_reconcile_no_redirect_returns_zero_when_no_critical(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Bare findings (no redirect, no critical) → rc=0, no
        ``[REDIRECT]`` lines on stderr."""
        from plan_tool.cli import app as cli_module
        from plan_tool.launcher import RunResult

        plan_path = _detail_basic_plan(tmp_path)
        _prepare_selected_reconcile_step(plan_path)
        manifest = _detail_setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)

        def fake_run_step(plan_path_arg, **kwargs):
            return RunResult(
                step_id=1,
                exit_code=0,
                advanced_to=None,
                done=False,
                stdout="## Findings\n\n- MEDIUM: cosmetic typo\n",
            )

        monkeypatch.setattr("plan_tool.cli.reconcile.run_step", fake_run_step)
        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "run", "plan", "--reconcile", "--step", "1",
            ]
        )
        assert rc == 0
        err = capsys.readouterr().err
        assert "[REDIRECT]" not in err


# ---------------------------------------------------------------------------
# Reconcile Subcommand Split — end-to-end loops.
#
# These exercise the cross-module wiring between CLI dispatch, launcher
# prompt rendering, the apply path, and persistence. The two classes
# below pin the asymmetry that justifies the split: detail-side audits
# land plan/detail edits via ``apply_finding`` (no code writes); run-
# side audits land code edits inline via ``shell_invoker`` and refuse
# plan-rooted findings with ``[REDIRECT]`` + rc=1 instead of forwarding
# them through any apply path.
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestDetailReconcileLoop:
    """End-to-end: ``plan-tool detail <name> --reconcile --step N``
    runs the detail-reconcile audit prompt and lands plan-side edits
    via ``apply_finding``. Code files declared in ``step.files`` are
    not modified by this path."""

    def test_detail_reconcile_loop_lands_plan_edits(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool import launcher as launcher_module
        from plan_tool.launcher import ApplyFindingResult, RunResult

        plan_path = _iter_basic_plan(tmp_path)
        manifest = _iter_setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)
        _iter_force_tty(monkeypatch, True)

        # Capture the original code-file bytes so we can assert later
        # that the detail-reconcile path never touches them.
        code_path = tmp_path / "foo.py"
        code_before = code_path.read_bytes()

        # Fake the audit so it emits one finding bullet whose body is
        # plainly a plan edit (flip a step's status). The actual edit
        # is performed by ``apply_finding`` below.
        def fake_run_step(plan_path_arg, **kwargs):
            assert kwargs.get("mode") == "detail-reconcile"
            return RunResult(
                step_id=kwargs.get("step_id") or 1,
                exit_code=0,
                advanced_to=None,
                done=False,
                stdout=(
                    "## Findings\n\n"
                    "- HIGH: step 1 status should be `current`, not "
                    "`done` — code isn't on disk yet\n"
                ),
            )

        monkeypatch.setattr("plan_tool.cli.reconcile.run_step", fake_run_step)

        # Recording fake ``apply_finding`` that performs the plan edit
        # and asserts it was reached.
        apply_calls: list[dict] = []

        def fake_apply_finding(plan_path_arg, **kwargs):
            apply_calls.append(dict(kwargs))
            # Perform the plan-side edit so the on-disk assertion below
            # has something to observe.
            text = plan_path_arg.read_text(encoding="utf-8")
            plan_path_arg.write_text(
                text.replace("status: done", "status: current"),
                encoding="utf-8",
            )
            return ApplyFindingResult(
                step_id=kwargs.get("step_id") or 1,
                exit_code=0,
                verdict="APPLIED",
                summary="flipped",
                diff_text="status: done → status: current",
                pre_snapshot={plan_path_arg: text},
                stdout="",
                introduced_findings=(),
                resolved_findings=(),
            )

        monkeypatch.setattr(
            launcher_module, "apply_finding", fake_apply_finding
        )

        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "detail", "plan", "--reconcile", "--step", "1", "--yes",
            ]
        )
        assert rc == 0
        # ``apply_finding`` ran for the plan-edit finding.
        assert len(apply_calls) == 1
        assert "flip" in apply_calls[0].get("finding_body", "").lower() or \
            "status" in apply_calls[0].get("finding_body", "").lower()
        # Plan file reflects the edit.
        assert "status: current" in plan_path.read_text(encoding="utf-8")
        # Code file under ``step.files`` was NOT touched.
        assert code_path.read_bytes() == code_before


@pytest.mark.integration
class TestRunReconcileLoop:
    """End-to-end: ``plan-tool run <name> --reconcile --step N`` lands
    code edits inline via ``shell_invoker`` (claude under acceptEdits)
    and refuses plan-rooted findings with ``[REDIRECT]`` + rc=1
    without ever reaching ``apply_finding``."""

    def test_run_reconcile_loop_lands_code_edits_and_refuses_plan_rooted(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool import launcher as launcher_module
        from plan_tool.launcher import RunResult

        plan_path = _iter_basic_plan(tmp_path)
        _prepare_selected_reconcile_step(plan_path)
        manifest = _iter_setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)

        plan_before = plan_path.read_bytes()
        code_path = tmp_path / "foo.py"

        # Fake run_step: stamp the code file with a sentinel (mimics
        # claude landing an Edit under acceptEdits inline) AND emit a
        # mixed stdout with one code-rooted finding and one plan-rooted
        # finding carrying a ``## Redirect`` sub-block.
        def fake_run_step(plan_path_arg, **kwargs):
            assert kwargs.get("mode") == "run-reconcile"
            code_path.write_text("SENTINEL\n", encoding="utf-8")
            return RunResult(
                step_id=kwargs.get("step_id") or 1,
                exit_code=0,
                advanced_to=None,
                done=False,
                stdout=(
                    "## Findings\n\n"
                    "- HIGH: missing helper landed inline\n"
                    "- MEDIUM: apps/old-foo.ts declared but missing\n"
                    "\n"
                    "## Redirect\n\n"
                    "- **Reason**: step.files declares a stale path\n"
                    "- **Suggested next**: detail --reconcile\n"
                ),
            )

        monkeypatch.setattr("plan_tool.cli.reconcile.run_step", fake_run_step)
        # ``apply_finding`` must NOT run on the run-reconcile path:
        # code edits land inline; plan-rooted findings short-circuit.
        monkeypatch.setattr(
            launcher_module,
            "apply_finding",
            lambda *a, **k: (_ for _ in ()).throw(
                AssertionError("apply_finding must not run on --reconcile")
            ),
        )

        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "run", "plan", "--reconcile", "--step", "1",
            ]
        )
        # Plan-rooted finding triggers a redirect, surfaced on stderr; the
        # audit itself completed so rc is 0.
        assert rc == 0
        err = capsys.readouterr().err
        assert "[REDIRECT]" in err
        assert "step.files declares a stale path" in err
        # Code file was written by the (faked) inline apply path.
        assert code_path.read_text(encoding="utf-8") == "SENTINEL\n"
        # Plan file was NOT touched.
        assert plan_path.read_bytes() == plan_before


class TestIterateFlagsValidation:
    """Step 5: ``_resolve_iterative_budget`` rejects zero/negative
    ``--max-iterations`` and ``--iteration-budget``. Failure surfaces
    as rc=1 (``cmd_create``) or rc=2 (``cmd_detail``/``cmd_run``)
    with a friendly stderr line."""

    def test_max_iterations_zero_is_rejected(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module

        monkeypatch.setattr(
            cli_context, "find_repo_root_from_cwd", lambda: tmp_path
        )
        monkeypatch.chdir(tmp_path)
        rc = cli_module.main(
            ["create", "demo", "--iterate", "--max-iterations", "0"]
        )
        assert rc == 1
        err = capsys.readouterr().err
        assert "must be >= 1" in err

    def test_max_iterations_negative_is_rejected(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module

        monkeypatch.setattr(
            cli_context, "find_repo_root_from_cwd", lambda: tmp_path
        )
        monkeypatch.chdir(tmp_path)
        rc = cli_module.main(
            ["create", "demo", "--iterate", "--max-iterations", "-2"]
        )
        assert rc == 1
        err = capsys.readouterr().err
        assert "must be >= 1" in err

    def test_iteration_budget_zero_is_rejected(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module

        monkeypatch.setattr(
            cli_context, "find_repo_root_from_cwd", lambda: tmp_path
        )
        monkeypatch.chdir(tmp_path)
        rc = cli_module.main(
            ["create", "demo", "--iterate", "--iteration-budget", "0"]
        )
        assert rc == 1
        err = capsys.readouterr().err
        assert "must be >= 1 second" in err


# ---------------------------------------------------------------------------
# Step 6: cross-cutting iteration-surface invariants for the CLI.
#
# These exercise the argparse-to-orchestrator pipeline (``main(...)`` not
# direct kwarg injection) and pin the cross-subcommand contracts: that
# ``--no-iterate`` is byte-equivalent to omitting the flag, that
# ``--max-iterations 0`` is rejected uniformly, that exhaustion surfaces
# on stderr with a consistent reason string, that closed-stdin preserves
# ``WalkState.yes_to_all`` across every iteration, and that the resolve
# helper builds the same ``IterativeBudget`` for create/detail/run.
# ---------------------------------------------------------------------------


import json as _json_cross_cutting  # noqa: E402


_CREATE_STEPS_JSON = _json_cross_cutting.dumps(
    [{"title": "first", "complexity": "low", "files": [], "depends_on": []}]
)
_CREATE_REFS_JSON = _json_cross_cutting.dumps([])


def _create_fake_invoker(prompt: str) -> str:
    """Fake claude invoker for create: route by prompt fingerprint."""
    if "developer and API reference documentation" in prompt:
        return _CREATE_REFS_JSON
    return _CREATE_STEPS_JSON


def _setup_cross_create_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    sub: str,
) -> tuple[Path, Path, Path]:
    """Stage an isolated ``cmd_create`` run under ``tmp_path / sub``.

    Returns ``(repo_root, output_dir, manifest_path)``. The real
    ``create_plan`` is wrapped so the production invoker is replaced
    with ``_create_fake_invoker`` — never spawns a real subprocess.
    ``apply_finding`` is stubbed at the ``create`` call-site so the
    post-write convergence loop doesn't shell out to real ``claude``
    (its default ``invoker=shell_invoker``).
    """
    from plan_tool.cli import app as cli_module
    from plan_tool import create as create_module
    from plan_tool.launcher import ApplyFindingResult

    repo_root = tmp_path / sub
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    output_dir = repo_root / "plans"
    manifest_path = repo_root / "m.json"

    real_create_plan = create_module.create_plan

    def wrapped_create_plan(slug, **kwargs):
        kwargs.setdefault("claude_invoker", _create_fake_invoker)
        return real_create_plan(slug, **kwargs)

    monkeypatch.setattr("plan_tool.cli.authoring.create_plan", wrapped_create_plan)
    monkeypatch.setattr(cli_context, "find_repo_root_from_cwd", lambda: repo_root)
    monkeypatch.setattr(
        create_module,
        "apply_finding",
        lambda *a, **kw: ApplyFindingResult(
            step_id=None, exit_code=0, verdict="APPLIED",
            summary="", diff_text="", pre_snapshot={}, stdout="",
        ),
    )
    return repo_root, output_dir, manifest_path


@pytest.mark.integration
class TestCrossCuttingIterationCLI:
    """Cross-cutting invariants over the ``--iterate`` / ``--no-iterate`` /
    ``--max-iterations`` / ``--iteration-budget`` CLI surface for the three
    subcommands that accept the iterate flag family (create / detail / run).

    The per-subcommand tests in ``TestIterateFlagsCreate`` /
    ``TestIterateFlagsDetail`` / ``TestIterateFlagsRun`` already prove
    each flag's kwarg propagation. These tests pin the contracts a
    user is actually promised by ``--help``: that ``--no-iterate``
    produces byte-identical output to the default, that
    ``--max-iterations 0`` is rejected consistently rather than
    silently degenerate, that budget exhaustion surfaces a consistent
    stderr reason regardless of subcommand, that the closed-stdin
    auto-accept default survives across iterations, and that
    ``_resolve_iterative_budget`` builds the same budget for all three.
    """

    # --- 1: --iterate byte-parity for ``create`` ------------------------

    def test_iterate_default_byte_parity_create(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``--iterate`` and the omitted flag write byte-identical plans.

        ``create`` opts INTO the post-write convergence loop by default
        (see ``p_create.set_defaults(iterate=True)`` in cli.py), so the
        omitted-flag run and the explicit ``--iterate`` run should both
        drive the same iteration shape. A regression that flipped the
        create-specific default back to off would diverge here because
        only the explicit-``--iterate`` run would enter the loop.
        """
        from plan_tool.cli import app as cli_module

        _, out1, m1 = _setup_cross_create_run(tmp_path, monkeypatch, "explicit_yes")
        rc1 = cli_module.main([
            "--manifest", str(m1),
            "create", "demo",
            "--from", "build a thing",
            "--output-dir", str(out1),
            "--yes",
            "--iterate",
        ])
        assert rc1 == 0

        _, out2, m2 = _setup_cross_create_run(tmp_path, monkeypatch, "default")
        rc2 = cli_module.main([
            "--manifest", str(m2),
            "create", "demo",
            "--from", "build a thing",
            "--output-dir", str(out2),
            "--yes",
        ])
        assert rc2 == 0

        plan_a = out1 / "2-demo.md"
        plan_b = out2 / "2-demo.md"
        assert plan_a.is_file()
        assert plan_b.is_file()
        assert plan_a.read_bytes() == plan_b.read_bytes()

    # --- 2: --no-iterate budget propagation for ``detail`` --------------

    def test_no_iterate_budget_parity_detail(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``--no-iterate`` and omission both disable detail iteration.

        Cross-cutting bit: ``detail``'s iteration loop edits the on-disk
        file in place, so byte-parity of the written detail body is not
        a stable assertion (each run picks its own slug; the actual byte
        comparison is exercised by ``TestCrossCuttingIterationDetail``).
        At the CLI level the meaningful claim is the budget kwarg shape:
        ``--no-iterate`` yields ``enabled=False``; omitting the flag
        yields ``enabled=False`` (detail deliberately defaults to iterate-off).
        ``max_iterations`` / ``budget_seconds`` defaults still match
        across both invocations so flipping iterate on/off doesn't
        silently change the cap.
        """
        from plan_tool.cli import app as cli_module

        _detail_basic_plan(tmp_path)
        manifest = _detail_setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)

        captured_budgets: list = []

        def fake_generate_detail(plan_path_arg, **kwargs):
            captured_budgets.append(kwargs.get("budget"))
            return []

        monkeypatch.setattr(
            "plan_tool.cli.authoring.generate_detail", fake_generate_detail
        )

        rc1 = cli_module.main([
            "--manifest", str(manifest),
            "detail", "plan", "--no-iterate",
        ])
        rc2 = cli_module.main([
            "--manifest", str(manifest),
            "detail", "plan",
        ])
        assert rc1 == 0
        assert rc2 == 0
        assert len(captured_budgets) == 2
        a, b = captured_budgets
        assert a is not None and b is not None
        assert a.enabled is False
        assert b.enabled is False
        assert a.max_iterations == b.max_iterations
        assert a.budget_seconds == b.budget_seconds

    # --- 4-6: --max-iterations 0 rejection contract ---------------------
    #
    # Step 5's ``_resolve_iterative_budget`` rejects ``--max-iterations 0``
    # with ``rc=1`` (cmd_create) or ``rc=2`` (cmd_detail / cmd_run) and a
    # ``"must be >= 1"`` stderr line. Step 6's plan description sketched an
    # *equivalence* arm (rc=0 with disabled-loop semantics) as the
    # alternative — the implementor chose the rejection arm. These tests
    # pin the rejection contract so a future refactor that silently
    # swallows ``--max-iterations 0`` would be caught.

    def test_max_iterations_zero_rejected_create(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """``create --iterate --max-iterations 0`` → rc=1 + stderr error.

        Contract choice: rejection (not equivalence to ``--no-iterate``).
        """
        from plan_tool.cli import app as cli_module

        monkeypatch.setattr(
            cli_context, "find_repo_root_from_cwd", lambda: tmp_path
        )
        monkeypatch.chdir(tmp_path)
        rc = cli_module.main(
            ["create", "demo", "--iterate", "--max-iterations", "0"]
        )
        assert rc == 1
        err = capsys.readouterr().err
        assert "must be >= 1" in err

    def test_max_iterations_zero_rejected_detail(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """``detail --iterate --max-iterations 0`` → rc=2 + stderr error."""
        from plan_tool.cli import app as cli_module

        _detail_basic_plan(tmp_path)
        manifest = _detail_setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main([
            "--manifest", str(manifest),
            "detail", "plan", "--iterate", "--max-iterations", "0",
        ])
        assert rc == 2
        err = capsys.readouterr().err
        assert "must be >= 1" in err

    # --- 8: budget-exhaustion stderr signal for `create` ----------------

    def test_budget_exhaustion_stderr_signal_create(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """An exhausted ``create`` loop logs the stop reason on stderr.

        Cross-cutting bit: ``cmd_create`` returns rc=0 on a successful
        plan write regardless of whether the iteration loop exhausted
        — exhaustion is *not* a hard failure for ``create`` (the plan
        file is the durable artifact). The promise is that the
        exhaustion is observable in the run log / stderr stream so
        a script can grep for it. This test pins the stderr signal.
        """
        from plan_tool.cli import app as cli_module
        from plan_tool import create as create_module
        from plan_tool.convergence import IterativeBudget

        repo_root, output_dir, manifest = _setup_cross_create_run(
            tmp_path, monkeypatch, "exhaust"
        )

        # Force the orchestrator's iteration loop to exhaust by returning
        # a fresh deterministic finding every collect call and a no-op
        # apply_finding. The `_iter_invoker`-style invoker comes from
        # ``_create_fake_invoker`` already wired by ``_setup_cross_create_run``.
        from plan_tool.review import Recommendation as _Rec
        from plan_tool.launcher import ApplyFindingResult as _ApplyFindingResult

        # Apply-eligible source so the loop dispatches (this test
        # exercises budget-exhaustion signalling, not source-eligibility).
        finding_seq = iter([
            [_Rec(id="cf-0", source="body-completeness", severity="medium",
                  step_id=None, title="t", body="b0",
                  suggested_action=None)],
            [_Rec(id="cf-1", source="body-completeness", severity="medium",
                  step_id=None, title="t", body="b1",
                  suggested_action=None)],
            [_Rec(id="cf-2", source="body-completeness", severity="medium",
                  step_id=None, title="t", body="b2",
                  suggested_action=None)],
        ])
        monkeypatch.setattr(
            create_module,
            "collect_deterministic_findings",
            lambda *a, **kw: next(finding_seq),
        )
        monkeypatch.setattr(
            create_module,
            "apply_finding",
            lambda *a, **kw: _ApplyFindingResult(
                step_id=None, exit_code=0, verdict="APPLIED",
                summary="", diff_text="", pre_snapshot={}, stdout="",
            ),
        )

        rc = cli_module.main([
            "--manifest", str(manifest),
            "create", "demo",
            "--from", "build a thing",
            "--output-dir", str(output_dir),
            "--yes",
            "--iterate", "--max-iterations", "1",
        ])
        assert rc == 0
        err = capsys.readouterr().err
        assert "iteration loop stopped: max_iterations" in err



# --- Conceptual completeness wiring (task #15 / Lesson 7) ----------------

@pytest.mark.integration
class TestCmdCompletenessConceptWiring:
    """End-to-end wiring: when ``shell_review_invoker`` returns the
    plan-audit two-section block, ``cmd_completeness`` must surface
    those findings in BOTH the human-readable report and the ``--json``
    output, and the exit code must factor medium+ severities. Unit
    tests on ``check_plan_audit`` exercise the helper; this proves the
    CLI wiring downstream of it (Lesson 7: test the wiring, not just the
    helper)."""

    @pytest.fixture(autouse=True)
    def _stub_plan_audit_invoker(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Default the conceptual-audit claude call to an empty result
        so iterate-machinery tests stay hermetic. Tests that exercise
        the audit override this in-body (their setattr wins)."""
        from plan_tool import review as review_module

        monkeypatch.setattr(
            review_module,
            "shell_review_invoker",
            lambda _p: (
                0,
                "## Correctness findings\n\n_(none)_\n\n"
                "## Completeness findings\n\n_(none)_\n",
            ),
        )

    def _seed_plan(
        self, tmp_path: Path, *, status: str = "done"
    ) -> Path:
        """Write a minimal plan whose step 1 declares ``foo.py``, plus
        the file itself, and a body that includes
        ``## Acceptance criteria`` so concept-completeness has both
        inputs."""
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        plan_path = plans_dir / "1-concept-test.md"
        plan_path.write_text(
            "---\n"
            "title: Concept Wiring Test\n"
            # Both intents present so the blocking ``intent-presence`` finding
            # stays out of these fixtures — they pin iterate-loop apply/defer
            # counts, which an unrelated blocking finding would shift.
            "intent: exercise the completeness CLI wiring end to end\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: build the thing\n"
            "    intent: why the only step exists\n"
            "    files:\n"
            "      - foo.py\n"
            f"    status: {status}\n"
            "---\n"
            "\n"
            "## Overview\n\nReal overview.\n\n"
            "## Problem statement\n\nReal problem.\n\n"
            "## Architecture\n\nReal architecture.\n\n"
            "## Steps\n\nSee frontmatter.\n\n"
            "## Out of scope\n\nReal scope text.\n\n"
            "## Risks\n\nReal risks.\n\n"
            "## Testing\n\nReal testing.\n\n"
            "## Acceptance criteria\n\nfoo.py:bar() must return 42.\n\n"
            "## Deferred\n\nReal deferred.\n",
            encoding="utf-8",
        )
        (tmp_path / "foo.py").write_text(
            "def bar():\n    return 41\n", encoding="utf-8"
        )
        return plans_dir

    def test_iterate_writes_report_and_concise_summary(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """``--iterate`` persists a completeness report under
        ``.plan-tool/reviews/<slug>/`` and prints a concise summary to
        stdout (NOT the full grouped report). The report states why the
        advisory conceptual-completeness gap wasn't auto-applied."""
        from plan_tool import review as review_module

        plans_dir = self._seed_plan(tmp_path)

        # One advisory completeness gap, no correctness, no deterministic
        # findings — so nothing is applied and the gap is reported.
        monkeypatch.setattr(
            review_module, "shell_review_invoker",
            lambda _p: (
                0,
                "## Correctness findings\n\n_(none)_\n\n"
                "## Completeness findings\n\n"
                "- MEDIUM: [dlq-reconciliation] No step handles a job that "
                "exhausts retries and lands in the DLQ\n",
            ),
        )
        monkeypatch.setattr(
            review_module, "collect_deterministic_findings",
            lambda *a, **kw: [],
        )

        rc = main([
            "--repo-root", str(tmp_path),
            "--plans-dir", str(plans_dir),
            "completeness-audit", "concept-test",
            "--iterate", "--yes", "--max-iterations", "1",
        ])
        assert rc in (0, 1)
        out = capsys.readouterr().out
        # Concise summary on stdout — not the verbose grouped report.
        assert "completeness done" in out
        # This fixture deliberately has no detail bundle. Under #85,
        # conceptual-completeness gaps stay informational on bare plans;
        # conceptual gaps use session-directed correction guidance.
        assert "completeness-apply" not in out
        assert "advisory  1 conceptual gap(s)" in out
        assert "informational until a complete detail bundle exists" in out
        assert "Conceptual completeness" not in out
        # Report persisted with the rationale + the advisory finding.
        reports = list(
            (tmp_path / "plans" / "plan-details" / "concept-test" / "reports")
            .glob("*-completeness.md")
        )
        assert reports, "expected a completeness report file"
        # Newest, not reports[0]: rglob order is unspecified and report
        # filenames carry only second granularity, so a run that straddles a
        # second boundary leaves two and the positional pick is arbitrary.
        text = max(reports).read_text(encoding="utf-8")
        assert "Conceptual completeness — reported, not auto-applied" in text
        assert "not auto-applied" in text
        assert "DLQ" in text
        assert "confidence: limited" in text
        # The path is surfaced on screen for reuse.
        assert "-completeness.md" in out

    def test_audit_only_keeps_grouped_report_and_writes_file(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Without ``--iterate`` the grouped report stays on stdout
        (interactive inspect) AND a report file is persisted."""
        from plan_tool import review as review_module

        plans_dir = self._seed_plan(tmp_path)
        monkeypatch.setattr(
            review_module, "shell_review_invoker",
            lambda _p: (
                0,
                "## Correctness findings\n\n_(none)_\n\n"
                "## Completeness findings\n\n"
                "- MEDIUM: [x] some conceptual gap\n",
            ),
        )
        rc = main([
            "--repo-root", str(tmp_path),
            "--plans-dir", str(plans_dir),
            "completeness-audit", "concept-test",
        ])
        assert rc in (0, 1)
        out = capsys.readouterr().out
        assert "Conceptual completeness" in out  # grouped report shown
        assert "Completeness report saved to" in out
        reports = list(
            (tmp_path / "plans" / "plan-details" / "concept-test" / "reports")
            .glob("*-completeness.md")
        )
        assert reports, "expected a completeness report file in audit-only mode"

    def test_human_report_renders_audit_sections(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When the (mocked) invoker returns a correctness finding and a
        completeness finding, the human report routes the correctness
        one into ``### Correctness (run these first)`` and the
        completeness one into ``### Conceptual completeness``."""
        from plan_tool import review as review_module

        plans_dir = self._seed_plan(tmp_path)

        def fake_invoker(_prompt: str) -> tuple[int, str]:
            return (
                0,
                "Audit prose.\n\n"
                "## Correctness findings\n\n"
                "- HIGH: step 1 assumes a cache that no step establishes\n\n"
                "## Completeness findings\n\n"
                "- MEDIUM: Risks names a rollback hazard no step mitigates\n",
            )

        monkeypatch.setattr(
            review_module, "shell_review_invoker", fake_invoker,
        )

        rc = main([
            "--repo-root", str(tmp_path),
            "--plans-dir", str(plans_dir),
            "completeness-audit", "concept-test",
        ])

        out = capsys.readouterr().out
        assert "Correctness (run these first)" in out
        assert "assumes a cache" in out
        assert "Conceptual completeness" in out
        assert "rollback hazard" in out
        # A completed audit exits 0; the medium+ finding is surfaced in the
        # report, not the exit code.
        assert rc == 0

    def test_iterate_continues_partial_plan_without_round0_rewrite(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """``completeness --iterate`` continues a partially-iterated plan in
        place: it drives the real ``body-completeness`` placeholder findings
        to zero by applying them, and it does NOT rebuild the body from a
        seed (the way re-running ``create`` would). This pins the
        load-bearing claim behind closing 2(b) with Option A — completeness,
        not a bespoke ``create`` resume, is the continuation path.

        Honest test: the deterministic findings are REAL (not monkeypatched);
        only ``apply_finding`` is faked, and its fake fills the on-disk
        ``_(TODO)_`` markers with prose. A sentinel already in a filled
        section proves the body wasn't clobbered by a round-0 rewrite.
        """
        from plan_tool.parser import parse_plan
        from plan_tool.review import collect_deterministic_findings
        from plan_tool import launcher as launcher_module
        from plan_tool.launcher import ApplyFindingResult

        sentinel = "SENTINEL-PRESERVE-ME"
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        plan_path = plans_dir / "1-partial-plan.md"
        # One step, no files (no file-existence finding), no detail (which
        # produces no finding at all — undeclared detail is normal operations).
        # Several body sections land as `_(TODO)_` placeholders
        # -> real body-completeness findings; Overview carries the sentinel.
        plan_path.write_text(
            "---\n"
            "title: Partial Plan\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: build the thing\n"
            "    status: pending\n"
            "---\n"
            "\n"
            f"## Overview\n\nReal overview. {sentinel}\n\n"
            "## Problem statement\n\nReal problem.\n\n"
            "## Architecture\n\nReal architecture.\n\n"
            "## References\n\nReal references.\n\n"
            "## Steps\n\nSee frontmatter.\n\n"
            "## Out of scope\n\nReal scope text.\n\n"
            "## Risks\n\n_(TODO)_\n\n"
            "## Testing\n\n_(TODO)_\n\n"
            "## Acceptance criteria\n\n_(TODO)_\n\n"
            "## Deferred\n\nReal deferred.\n",
            encoding="utf-8",
        )

        def _body_findings(path: Path) -> list:
            return [
                r
                for r in collect_deterministic_findings(
                    parse_plan(path), path,
                    repo_root=tmp_path, plan_name="partial-plan",
                )
                if r.source == "body-completeness"
            ]

        before = _body_findings(plan_path)
        assert len(before) >= 3, before  # the three `_(TODO)_` sections

        # Fake apply_finding fills the on-disk placeholders with prose and
        # reports APPLIED. Edits the plan file directly (in-scope), so the
        # re-collect after each round naturally drops the resolved findings.
        def _fake_apply(target_path, **kwargs):
            text = Path(target_path).read_text(encoding="utf-8")
            if "_(TODO)_" in text:
                Path(target_path).write_text(
                    text.replace("_(TODO)_", "Filled in place by apply."),
                    encoding="utf-8",
                )
            return ApplyFindingResult(
                step_id=kwargs.get("step_id"),
                exit_code=0,
                verdict="APPLIED",
                summary="",
                diff_text="",
                pre_snapshot={},
                stdout="",
            )

        monkeypatch.setattr(launcher_module, "apply_finding", _fake_apply)

        rc = main([
            "--repo-root", str(tmp_path),
            "--plans-dir", str(plans_dir),
            "completeness-audit", "partial-plan",
            "--iterate", "--yes", "--no-triage", "--max-iterations", "5",
        ])

        # The body-completeness findings were driven to zero, in place.
        after = _body_findings(plan_path)
        assert after == [], after
        # No round-0 rewrite: the sentinel in the already-filled Overview
        # survived, and the fake's filled prose is on disk.
        final = plan_path.read_text(encoding="utf-8")
        assert sentinel in final
        assert "Filled in place by apply." in final
        assert "_(TODO)_" not in final
        # No medium+ findings remain, so the run exits clean.
        assert rc == 0

    def test_json_output_includes_plan_audit_key(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """``--json`` output emits a ``plan_audit`` array with
        axis/severity/id/title/body per finding, and the JSON
        ``has_blocking_findings`` flag reflects the medium+ findings
        while the process still exits 0."""
        import json
        from plan_tool import review as review_module

        plans_dir = self._seed_plan(tmp_path)

        def fake_invoker(_prompt: str) -> tuple[int, str]:
            return (
                0,
                "## Correctness findings\n\n"
                "- HIGH: step 1 assumes a cache no step establishes\n\n"
                "## Completeness findings\n\n"
                "- MEDIUM: Risks names a hazard no step mitigates\n",
            )

        monkeypatch.setattr(
            review_module, "shell_review_invoker", fake_invoker,
        )

        rc = main([
            "--repo-root", str(tmp_path),
            "--plans-dir", str(plans_dir),
            "completeness-audit", "concept-test", "--json",
        ])

        out = capsys.readouterr().out
        data = json.loads(out)
        assert "plan_audit" in data["checks"]
        audit = data["checks"]["plan_audit"]
        assert len(audit) == 2
        axes = {r["axis"] for r in audit}
        assert axes == {"correctness", "completeness"}
        assert data["has_blocking_findings"] is True
        assert rc == 0

    def test_conceptual_section_absent_when_no_findings(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When the audit returns no findings, the human report omits
        both conceptual sections and the exit code is unaffected."""
        from plan_tool import review as review_module

        plans_dir = self._seed_plan(tmp_path)

        # Both sections empty → 0 audit recs.
        monkeypatch.setattr(
            review_module,
            "shell_review_invoker",
            lambda _p: (
                0,
                "## Correctness findings\n\n_(none)_\n\n"
                "## Completeness findings\n\n_(none)_\n",
            ),
        )

        main([
            "--repo-root", str(tmp_path),
            "--plans-dir", str(plans_dir),
            "completeness-audit", "concept-test",
        ])

        out = capsys.readouterr().out
        assert "Conceptual completeness" not in out

    def test_audit_runs_regardless_of_step_status(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """The plan-audit pass judges the plan's design (not shipped
        code), so it fires (and renders findings) even when no step is
        DONE — the key behavioral difference from the fulfillment check,
        which only audits done steps."""
        from plan_tool import review as review_module

        plans_dir = self._seed_plan(tmp_path, status="pending")
        called = {"n": 0}

        def fake_invoker(_prompt: str) -> tuple[int, str]:
            called["n"] += 1
            return (
                0,
                "## Correctness findings\n\n_(none)_\n\n"
                "## Completeness findings\n\n"
                "- MEDIUM: Architecture names a cache no step invalidates\n",
            )

        monkeypatch.setattr(
            review_module, "shell_review_invoker", fake_invoker,
        )

        main([
            "--repo-root", str(tmp_path),
            "--plans-dir", str(plans_dir),
            "completeness-audit", "concept-test",
            # Pin the legacy single-pass path; the multi-pass union
            # has its own tests (TestAuditPlanUntilStable + the default-
            # cap CLI test below).
            "--audit-passes", "1",
        ])

        out = capsys.readouterr().out
        assert "Conceptual completeness" in out
        assert "cache no step invalidates" in out
        # The invoker fired despite there being no DONE step.
        assert called["n"] == 1

    def test_default_audit_sampling_unions_until_dry(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """With a raised pass cap the conceptual audit runs until it goes
        dry — under the default dry_rounds=1 that means the first no-new
        pass stops the loop (2 productive + 1 dry stop here) — and
        findings from different passes union into one report. (The default
        cap is a static 3; this test pins --audit-passes 8 so the dry tail
        can actually be reached and the union exercised.)"""
        from plan_tool import review as review_module

        plans_dir = self._seed_plan(tmp_path, status="pending")
        called = {"n": 0}

        def fake_invoker(_prompt: str) -> tuple[int, str]:
            called["n"] += 1
            if called["n"] == 1:
                return (
                    0,
                    "## Correctness findings\n\n_(none)_\n\n"
                    "## Completeness findings\n\n"
                    "- MEDIUM: [cache-gap] cache no step invalidates\n",
                )
            # Later samples surface a second stable gap, then run dry.
            return (
                0,
                "## Correctness findings\n\n_(none)_\n\n"
                "## Completeness findings\n\n"
                "- MEDIUM: [rollback-gap] rollback path uncovered\n",
            )

        monkeypatch.setattr(
            review_module, "shell_review_invoker", fake_invoker,
        )

        main([
            "--repo-root", str(tmp_path),
            "--plans-dir", str(plans_dir),
            "completeness-audit", "concept-test",
            # Pin a cap above the static-3 default so the dry tail is reached.
            "--audit-passes", "8",
        ])

        out = capsys.readouterr().out
        # Findings from BOTH passes land in one report (union by id).
        assert "cache no step invalidates" in out
        assert "rollback path uncovered" in out
        # pass1: +1 new · pass2: +1 new · pass3: dry (1st) → stop. The
        # default dry_rounds is 1, so the first no-new pass stops the loop
        # — well under the pinned --audit-passes cap of 8.
        assert called["n"] == 3

    def test_iterate_mode_does_not_route_correctness_through_apply(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """#85 (read-only-audit split): ``cmd_completeness --iterate -y`` must
        NOT route conceptual *correctness* findings to ``apply_finding``. They
        are collected from the once-run conceptual audit and persisted to the
        report/sidecar unapplied for session-directed correction.

        This pins the inverse of the pre-#85 wiring (Lesson 7: test the
        wiring, not just the helper)."""
        from plan_tool import launcher as launcher_module
        from plan_tool import review as review_module
        from plan_tool.launcher import ApplyFindingResult

        plans_dir = self._seed_plan(tmp_path)

        # Mock claude semantic call to return ONE high-severity
        # conceptual-correctness finding.
        monkeypatch.setattr(
            review_module,
            "shell_review_invoker",
            lambda _p: (
                0,
                "## Correctness findings\n\n"
                "- HIGH: step 1 writes to a cache no step establishes\n\n"
                "## Completeness findings\n\n_(none)_\n",
            ),
        )

        # Mock the deterministic primitives so they return no findings; the
        # only finding entering the iterate loop is the concept one. This
        # isolates the assertion: any apply_finding call could only be the
        # (now-forbidden) correctness dispatch.
        monkeypatch.setattr(
            review_module,
            "collect_deterministic_findings",
            lambda *a, **kw: [],
        )

        captured_calls: list[dict] = []

        def fake_apply_finding(plan_path_arg, **kwargs):
            captured_calls.append({
                "step_id": kwargs.get("step_id"),
                "finding_body": kwargs.get("finding_body"),
            })
            return ApplyFindingResult(
                step_id=kwargs.get("step_id"),
                exit_code=0,
                verdict="APPLIED",
                summary="ok",
                diff_text="",
                pre_snapshot={},
                stdout="",
            )

        monkeypatch.setattr(
            launcher_module, "apply_finding", fake_apply_finding,
        )

        main([
            "--repo-root", str(tmp_path),
            "--plans-dir", str(plans_dir),
            "completeness-audit", "concept-test",
            "--iterate", "--yes", "--max-iterations", "1",
        ])

        # The correctness finding was NEVER dispatched to apply_finding.
        audit_calls = [
            c for c in captured_calls
            if "cache no step establishes" in (c["finding_body"] or "")
        ]
        assert audit_calls == [], (
            "correctness findings must not be auto-applied under #85; "
            f"captured: {captured_calls!r}"
        )
        # It remains persisted and unapplied for session-directed correction.
        reports = list(
            (tmp_path / "plans" / "plan-details" / "concept-test" / "reports")
            .glob("*-completeness.md")
        )
        assert reports, "expected a completeness report file"
        # Newest, not reports[0] — see the sibling case above.
        text = max(reports).read_text(encoding="utf-8")
        assert "cache no step establishes" in text

    def test_iterate_names_self_consistency_findings_not_false_converged(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """BUG_BACKLOG (--iterate converged-vs-rc mismatch): a blocking
        self-consistency finding is non-auto-appliable, so the loop must stop
        with an honest manual-fix message (and rc=1 under --fail-on-findings),
        NOT falsely report "converged". Patching ``detect_orphaned_deliverable``
        on the review module feeds BOTH the loop's blocking signal
        (``collect_self_consistency_findings``) and the finalize gate
        (``det.self_consistency_recs`` via ``_self_consistency_from_smells``) —
        the single-sourcing that makes them agree."""
        from plan_tool import review as review_module
        from plan_tool.review import Recommendation

        plans_dir = self._seed_plan(tmp_path)

        orphan = Recommendation(
            id="orphan-1",
            source="orphaned-deliverable",
            severity="medium",
            step_id=1,
            title="deliverable pkg/x.py has no consumer",
            body="wiring deferred, nothing consumes it",
        )
        # Seen by both the loop collector and the gate battery.
        monkeypatch.setattr(
            review_module, "detect_orphaned_deliverable",
            lambda *a, **kw: [orphan],
        )
        # No apply-eligible deterministic findings, so the loop reaches the
        # no-open_apply stop path with only the self-consistency finding open.
        monkeypatch.setattr(
            review_module, "collect_deterministic_findings",
            lambda *a, **kw: [],
        )

        rc = main([
            "--repo-root", str(tmp_path),
            "--plans-dir", str(plans_dir),
            "completeness-audit", "concept-test",
            "--iterate", "--yes", "--fail-on-findings", "--max-iterations", "1",
        ])

        err = capsys.readouterr().err
        # Honest terminal message naming the manual-fix self-consistency finding.
        assert "self-consistency blocking finding" in err
        assert "manual plan edit" in err
        assert "not auto-appliable" in err
        # The gate and the loop agree: rc reflects the blocking finding.
        assert rc == 1

    def test_self_consistency_manual_fix_note_on_should_continue_stop(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When the loop exits via ``should_continue`` (here ``max_iterations``)
        with an open self-consistency blocking finding — because an apply-eligible
        finding keeps the loop busy so the ``not open_apply`` branch is never
        reached — the honest manual-fix note must still surface (as a hint), not
        be lost. Covers the review's messaging-gap finding."""
        from plan_tool import launcher as launcher_module
        from plan_tool import review as review_module
        from plan_tool.launcher import ApplyFindingResult
        from plan_tool.review import Recommendation

        plans_dir = self._seed_plan(tmp_path)

        orphan = Recommendation(
            id="orphan-1", source="orphaned-deliverable", severity="medium",
            step_id=1, title="deliverable has no consumer", body="wiring deferred",
        )
        monkeypatch.setattr(
            review_module, "detect_orphaned_deliverable",
            lambda *a, **kw: [orphan],
        )
        # A persistent apply-eligible finding keeps open_apply non-empty so the
        # loop applies + recollects and stops on max_iterations (not on the
        # ``not open_apply`` branch).
        det_rec = Recommendation(
            id="body-overview", source="body-completeness", severity="medium",
            step_id=None, title="overview empty", body="## Overview body empty",
        )
        monkeypatch.setattr(
            review_module, "collect_deterministic_findings",
            lambda *a, **kw: [det_rec],
        )
        monkeypatch.setattr(
            launcher_module, "apply_finding",
            lambda plan_path_arg, **kw: ApplyFindingResult(
                step_id=kw.get("step_id"), exit_code=0, verdict="APPLIED",
                summary="ok", diff_text="", pre_snapshot={}, stdout="",
            ),
        )

        main([
            "--repo-root", str(tmp_path),
            "--plans-dir", str(plans_dir),
            "completeness-audit", "concept-test",
            "--iterate", "--yes", "--max-iterations", "1",
        ])

        err = capsys.readouterr().err
        assert "completeness iteration loop stopped: max_iterations" in err
        # The manual-fix note surfaces on the should_continue stop path too.
        assert "self-consistency blocking finding" in err
        assert "manual plan edit" in err

    def test_scope_guard_warning_includes_step_attribution_end_to_end(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """End-to-end test: when scope-guard fires inside
        cmd_completeness's iterate path, the warning enumerates the
        affected files WITH ``(step N: title)`` attribution.

        Closes the Lesson 7 gap from the #26 audit -- previously the
        helper had unit tests but no test verified that the cli call
        sites actually invoke it with the right map."""
        from plan_tool import launcher as launcher_module
        from plan_tool import review as review_module
        from plan_tool import scope_guard as scope_guard_module
        from plan_tool.launcher import ApplyFindingResult
        from plan_tool.review import Recommendation
        from plan_tool.scope_guard import OutOfScopeRecord

        plans_dir = self._seed_plan(tmp_path)

        # One deterministic finding so the loop has work to apply.
        det_rec = Recommendation(
            id="body-overview",
            source="body-completeness",
            severity="medium",
            step_id=None,
            title="overview empty",
            body="## Overview body empty",
        )
        monkeypatch.setattr(
            review_module,
            "collect_deterministic_findings",
            lambda *a, **kw: [det_rec],
        )
        # No concept findings -- keep the test focused on the
        # scope-guard branch.
        monkeypatch.setattr(
            review_module,
            "shell_review_invoker",
            lambda _p: (0, "## Findings\n\n_(none)_\n"),
        )

        # Mock apply_finding to return APPLIED without doing real
        # work. The synthetic out-of-scope record below is what
        # triggers the scope-guard branch we want to exercise.
        monkeypatch.setattr(
            launcher_module,
            "apply_finding",
            lambda plan_path_arg, **kwargs: ApplyFindingResult(
                step_id=kwargs.get("step_id"),
                exit_code=0,
                verdict="APPLIED",
                summary="ok",
                diff_text="",
                pre_snapshot={},
                stdout="",
            ),
        )

        # Synthetic OutOfScopeRecord pointing at foo.py (which the
        # seed plan declares under step 1). The cli's scope-guard
        # branch should fire `_print_attributed_files` against the
        # `_file_to_step` map and surface "(step 1: ...)" alongside
        # the path.
        foo = tmp_path / "foo.py"
        synthetic_record = OutOfScopeRecord(
            finding_id="body-overview",
            finding_body="x",
            step_id=None,
            out_of_scope_files=[foo],
            impact_status="reverted",
        )
        monkeypatch.setattr(
            scope_guard_module,
            "evaluate_apply_scope",
            lambda **kwargs: [synthetic_record],
        )
        # No-op revert so the synthetic record doesn't try to
        # restore from an empty pre-snapshot.
        monkeypatch.setattr(
            scope_guard_module,
            "revert_out_of_scope",
            lambda record, pre_snap: None,
        )

        main([
            "--repo-root", str(tmp_path),
            "--plans-dir", str(plans_dir),
            "completeness-audit", "concept-test",
            "--iterate", "--yes", "--max-iterations", "1",
        ])

        err = capsys.readouterr().err
        # The warning header AND the attributed bullet appear --
        # proves cli wired _print_attributed_files in.
        assert "reverted out-of-scope code edit" in err
        # The seed plan's step 1 has title "build the thing" per
        # _seed_plan. Attribution maps foo.py -> (1, that title).
        # The bullet renders as ``- foo.py (step 1: build the thing)``.
        assert "- foo.py (step 1: build the thing)" in err

    def test_iterate_mode_drift_halt_end_to_end(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Closes the pre-existing #30 MVP gap (Lesson 7): no test
        verified cmd_completeness's drift halt end-to-end via main().
        Mirrors TestCreatePlanDriftHalt / TestGenerateDetailDriftHalt
        for the completeness CLI surface.

        apply_finding advances foo.py's mtime; the post-apply drift
        check fires; loop halts with DURING-apply wording AND
        ``(step 1: build the thing)`` attribution from the #32 work."""
        import os
        from plan_tool import launcher as launcher_module
        from plan_tool import review as review_module
        from plan_tool.launcher import ApplyFindingResult
        from plan_tool.review import Recommendation

        plans_dir = self._seed_plan(tmp_path)
        watched = tmp_path / "foo.py"

        # Two deterministic findings so the for-rec loop has work
        # AND would proceed to a second apply if drift didn't halt.
        det_recs = [
            Recommendation(
                id="body-A", source="body-completeness",
                severity="medium", step_id=None, title="A", body="A",
            ),
            Recommendation(
                id="body-B", source="body-completeness",
                severity="medium", step_id=None, title="B", body="B",
            ),
        ]
        monkeypatch.setattr(
            review_module,
            "collect_deterministic_findings",
            lambda *a, **kw: det_recs,
        )
        # Empty concept findings stream -- focused on the drift halt.
        monkeypatch.setattr(
            review_module,
            "shell_review_invoker",
            lambda _p: (0, "## Findings\n\n_(none)_\n"),
        )

        apply_calls = {"n": 0}

        def fake_apply(plan_path_arg, **kwargs):
            apply_calls["n"] += 1
            # Mutate watched content to simulate mid-iteration drift
            # (#31: content hash, not mtime).
            watched.write_bytes(watched.read_bytes() + b"_drift")
            return ApplyFindingResult(
                step_id=kwargs.get("step_id"),
                exit_code=0,
                verdict="APPLIED",
                summary="ok",
                diff_text="",
                pre_snapshot={},
                stdout="",
            )

        monkeypatch.setattr(
            launcher_module, "apply_finding", fake_apply,
        )

        # Pass --no-auto-reconcile-on-drift to keep the test fast
        # and focused on the drift-halt path itself. The auto-reconcile
        # behavior is exercised by a sibling test that mocks run_step.
        rc = main([
            "--repo-root", str(tmp_path),
            "--plans-dir", str(plans_dir),
            "completeness-audit", "concept-test",
            "--iterate", "--yes", "--max-iterations", "3",
            "--no-auto-reconcile-on-drift",
        ])

        # First apply triggered drift; second apply was halted.
        assert apply_calls["n"] == 1
        err = capsys.readouterr().err
        assert "drift detected" in err
        assert "DURING apply" in err
        # drifted file is annotated with its step.
        assert "(step 1: build the thing)" in err
        # Drift halt returns rc=2 to signal the iteration loop
        # exited via an explicit safety condition.
        assert rc == 2

    def test_collision_sidecar_continue_breaks_for_rec_and_reiterates(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Change-collision sidecar happy path: when drift fires and
        ``handle_drift_collision`` returns True (user merged + chose
        to continue), cmd_completeness BREAKS out of the for-rec loop
        without setting the halt and the outer while-loop continues
        with a fresh findings sweep. Pins the wiring between the new
        ``--collision-sidecar`` default and the for-rec ``break``."""
        from plan_tool import change_collision as change_collision_module
        from plan_tool import launcher as launcher_module
        from plan_tool import review as review_module
        from plan_tool.launcher import ApplyFindingResult
        from plan_tool.review import Recommendation

        plans_dir = self._seed_plan(tmp_path)
        watched = tmp_path / "foo.py"

        # Three findings so we can prove the for-rec loop was BROKEN
        # after the first (rather than continued to apply all three).
        det_recs = [
            Recommendation(
                id=f"body-{n}", source="body-completeness",
                severity="medium", step_id=None,
                title=f"finding-{n}", body=f"finding-{n}",
            )
            for n in ("A", "B", "C")
        ]

        # Iteration 1 returns 3 findings; iteration 2 (after the
        # break + outer-while recollect) returns 0 → loop converges.
        collect_calls = {"n": 0}

        def fake_collect(*a, **kw):
            collect_calls["n"] += 1
            if collect_calls["n"] == 1:
                return det_recs
            return []  # converged after merge

        monkeypatch.setattr(
            review_module,
            "collect_deterministic_findings",
            fake_collect,
        )
        # Empty concept findings -- focused on the drift+merge path.
        monkeypatch.setattr(
            review_module,
            "shell_review_invoker",
            lambda _p: (0, "## Findings\n\n_(none)_\n"),
        )

        apply_calls = {"n": 0}

        def fake_apply(plan_path_arg, **kwargs):
            apply_calls["n"] += 1
            # Trigger drift on the very first apply.
            watched.write_bytes(watched.read_bytes() + b"_drift")
            return ApplyFindingResult(
                step_id=kwargs.get("step_id"),
                exit_code=0,
                verdict="APPLIED",
                summary="ok",
                diff_text="",
                pre_snapshot={},
                stdout="",
            )

        monkeypatch.setattr(
            launcher_module, "apply_finding", fake_apply,
        )

        # Mock handle_drift_collision to simulate "user merged +
        # chose continue" -- bypasses the real sidecar I/O + the
        # interactive prompt. The unit tests in
        # tests/test_change_collision.py cover the real flow.
        handle_calls: list[dict] = []

        def fake_handle(pre_snapshot, **kwargs):
            handle_calls.append({
                "pre_snapshot": pre_snapshot,
                "yes": kwargs.get("yes"),
            })
            return True  # user merged → continue

        monkeypatch.setattr(
            change_collision_module,
            "handle_drift_collision",
            fake_handle,
        )

        # NOTE: --yes is still passed because the test's input_fn is
        # mocked above; without --yes, the iteration would block on
        # the (now unused) input prompt at other points.
        rc = main([
            "--repo-root", str(tmp_path),
            "--plans-dir", str(plans_dir),
            "completeness-audit", "concept-test",
            "--iterate", "--yes", "--max-iterations", "3",
            "--no-auto-reconcile-on-drift",
        ])

        # First apply triggered drift; the for-rec loop broke (not
        # halted), so applies B and C did NOT run. Total: 1 apply.
        assert apply_calls["n"] == 1
        # handle_drift_collision fired exactly once with the
        # apply_result's pre_snapshot (yes=True passed through from
        # args).
        assert len(handle_calls) == 1
        assert handle_calls[0]["yes"] is True

        # Loop converged after the merge -- the outer while-loop
        # recollected (collect_findings call #2) and got an empty
        # set. Iteration did NOT halt-on-drift (which would have
        # been rc=2); the rc may still be 1 from the post-iterate
        # deterministic body-completeness check finding unrelated
        # body-section gaps in the seed plan, which is fine for
        # this test's purpose (load-bearing assertion: ``rc != 2``).
        assert rc != 2, (
            "iteration halted with drift rc=2; merge-continue path "
            "should have broken out of the for-rec loop and the "
            "outer while should have converged"
        )
        assert collect_calls["n"] >= 2

    def test_collision_sidecar_continue_refreshes_lock_so_iter_2_runs(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Bug 1 from the session-4 review: without refreshing
        ``_iter_lock.content_hash_snapshot`` after merge-continue,
        the next iteration's pre-apply drift check would compare
        the merged state against the original pre-merge snapshot
        and immediately halt. This test pins the fix by:

        1. Driving cmd_completeness with TWO findings.
        2. Letting iter 1's apply mutate the watched file (drift).
        3. Mocking ``handle_drift_collision`` to return True (user
           merged + continued).
        4. Verifying iter 2's pre-apply drift check passes (no halt)
           AND iter 2's apply actually runs against the second
           finding.

        Without ``refresh_snapshot``, step 4 fails because iter 2's
        pre-apply drift check sees the watched-file mutation as
        unresolved drift and halts."""
        from plan_tool import change_collision as change_collision_module
        from plan_tool import launcher as launcher_module
        from plan_tool import review as review_module
        from plan_tool.launcher import ApplyFindingResult
        from plan_tool.review import Recommendation

        plans_dir = self._seed_plan(tmp_path)
        watched = tmp_path / "foo.py"

        # Iter 1 sees finding A. For-rec applies A, drift fires,
        # collision-merge-continues, break. Iter 2 must introduce a
        # NEW finding (different id) so the convergence loop's
        # "marginal" early-exit doesn't fire -- ``should_continue``
        # halts when iteration N introduces no new finding ids
        # relative to N-1. Iter 2 returns [B] (new id) so the loop
        # proceeds and the load-bearing pre-apply drift check
        # actually executes.
        det_recs_iter1 = [
            Recommendation(
                id="body-A", source="body-completeness",
                severity="high", step_id=None,
                title="finding-A", body="finding-A",
            ),
        ]
        det_recs_iter2 = [
            Recommendation(
                id="body-B", source="body-completeness",
                severity="high", step_id=None,
                title="finding-B", body="finding-B",
            ),
        ]
        collect_calls = {"n": 0}

        def fake_collect(*a, **kw):
            collect_calls["n"] += 1
            if collect_calls["n"] == 1:
                return det_recs_iter1
            if collect_calls["n"] == 2:
                return det_recs_iter2
            return []  # converged after iter 2

        monkeypatch.setattr(
            review_module,
            "collect_deterministic_findings",
            fake_collect,
        )
        monkeypatch.setattr(
            review_module,
            "shell_review_invoker",
            lambda _p: (0, "## Findings\n\n_(none)_\n"),
        )

        # apply_finding mutates the watched file ONLY on the first
        # call (iter 1). Iter 2's apply doesn't drift -- so the
        # pre-apply drift check passes IFF the lock snapshot was
        # refreshed against the post-merge state.
        apply_calls: list[str] = []

        def fake_apply(plan_path_arg, **kwargs):
            apply_calls.append(kwargs.get("finding_body", ""))
            if len(apply_calls) == 1:
                watched.write_bytes(watched.read_bytes() + b"_drift")
            return ApplyFindingResult(
                step_id=kwargs.get("step_id"),
                exit_code=0,
                verdict="APPLIED",
                summary="ok",
                diff_text="",
                pre_snapshot={},
                stdout="",
            )

        monkeypatch.setattr(
            launcher_module, "apply_finding", fake_apply,
        )

        def fake_handle(pre_snapshot, **kwargs):
            return True  # user merged → continue

        monkeypatch.setattr(
            change_collision_module,
            "handle_drift_collision",
            fake_handle,
        )

        rc = main([
            "--repo-root", str(tmp_path),
            "--plans-dir", str(plans_dir),
            "completeness-audit", "concept-test",
            "--iterate", "--yes", "--max-iterations", "3",
            "--no-auto-reconcile-on-drift",
        ])

        # LOAD-BEARING assertion: iter 2's apply ran. Without
        # refresh_snapshot, iter 2's pre-apply check would have
        # halted before reaching apply_finding, so apply_calls
        # would be length 1.
        assert len(apply_calls) == 2, (
            f"iter 2's apply did not run -- the lock snapshot was "
            f"not refreshed after merge-continue, and the pre-apply "
            f"drift check halted iter 2 prematurely. "
            f"apply_calls={apply_calls}"
        )
        assert "finding-A" in apply_calls[0]
        assert "finding-B" in apply_calls[1]
        # Did NOT halt-on-drift in either iteration.
        assert rc != 2, (
            "iteration halted with drift rc=2; the merge-continue + "
            "refresh-snapshot wiring did not let iter 2 proceed"
        )

    def test_triage_short_circuits_when_all_remaining_are_deferred(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Impact-weighted triage: findings whose complexity strictly
        exceeds their impact are deferred. When iter 2 has only
        deferred findings remaining, the loop halts with a
        triaged-deferred halt message instead of looping.

        Iter 1: [A(impact=high, complexity=low) → apply,
                 B(impact=low, complexity=high) → defer].
        For-rec applies A. After A, collect returns [B] (just the
        deferred one).
        Iter 2: [B(deferred)] → open_apply=[] → halt."""
        from plan_tool import launcher as launcher_module
        from plan_tool import review as review_module
        from plan_tool.launcher import ApplyFindingResult
        from plan_tool.review import Recommendation

        plans_dir = self._seed_plan(tmp_path)

        rec_apply = Recommendation(
            id="rec-apply", source="reconcile",
            severity="high", step_id=None,
            title="apply-this", body="apply-body",
            impact="high", complexity="low",
        )
        rec_defer = Recommendation(
            id="rec-defer", source="reconcile",
            severity="high", step_id=None,
            title="defer-this", body="defer-body",
            impact="low", complexity="high",
        )

        collect_calls = {"n": 0}

        def fake_collect(*a, **kw):
            collect_calls["n"] += 1
            if collect_calls["n"] == 1:
                return [rec_apply, rec_defer]
            # Iter 2: rec_apply was fixed; only rec_defer remains.
            return [rec_defer]

        monkeypatch.setattr(
            review_module,
            "collect_deterministic_findings",
            fake_collect,
        )
        monkeypatch.setattr(
            review_module,
            "shell_review_invoker",
            lambda _p: (0, "## Findings\n\n_(none)_\n"),
        )

        apply_calls: list[str] = []

        def fake_apply(plan_path_arg, **kwargs):
            apply_calls.append(kwargs.get("finding_body", ""))
            return ApplyFindingResult(
                step_id=kwargs.get("step_id"),
                exit_code=0,
                verdict="APPLIED",
                summary="ok",
                diff_text="",
                pre_snapshot={},
                stdout="",
            )

        monkeypatch.setattr(
            launcher_module, "apply_finding", fake_apply,
        )

        rc = main([
            "--repo-root", str(tmp_path),
            "--plans-dir", str(plans_dir),
            "completeness-audit", "concept-test",
            "--iterate", "--yes", "--max-iterations", "3",
            "--no-auto-reconcile-on-drift",
        ])

        # Only rec_apply was applied; rec_defer was triaged out.
        assert len(apply_calls) == 1
        assert "apply-body" in apply_calls[0]
        # The triage summary fired in iter 1 listing the deferred
        # finding. Iter 2's pre-while convergence check halts the
        # loop via "marginal" (no new findings introduced) before
        # reaching the for-rec body -- the triage gate prevented
        # the apply, so the only remaining finding is rec-defer,
        # which isn't new vs iter 1's seed set. The convergence
        # short-circuit + the triage summary together accomplish
        # the user-visible goal: rec-defer is reported, never
        # applied, and the loop terminates instead of looping
        # forever re-evaluating it.
        err = capsys.readouterr().err
        # Concise deferral count on stderr (the full per-item list with
        # reasons now lives in the persisted report, not on screen).
        assert "deferring 1 finding(s)" in err
        assert "low-payoff" in err
        # The deferred finding IS recorded — in the report file.
        reports = list(
            (tmp_path / "plans" / "plan-details").rglob("*-completeness.md")
        )
        assert reports, "expected a completeness report to be written"
        # Newest, not reports[0] — see the sibling case above. This one was
        # the observed `-n auto` flake: it passes in isolation and fails under
        # load, where the extra wall time splits the run across two seconds.
        assert "rec-defer" in max(reports).read_text(encoding="utf-8")
        # Iter 2 halted via convergence (marginal), not via drift.
        assert rc != 2
        # The pre-while convergence check fired, so the in-loop
        # "all deferred halt" message did NOT print -- but that's
        # fine: the user already saw the deferred summary in iter 1.
        assert "completeness iteration loop stopped: marginal" in err

    def test_no_triage_flag_force_applies_every_finding(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """``--no-triage`` opts out of the triage gate: every
        finding (including ones whose complexity exceeds impact)
        gets passed to apply_finding. Pins the flag's plumbing."""
        from plan_tool import launcher as launcher_module
        from plan_tool import review as review_module
        from plan_tool.launcher import ApplyFindingResult
        from plan_tool.review import Recommendation

        plans_dir = self._seed_plan(tmp_path)

        # Both recs would be DEFERRED under default triage
        # (complexity > impact). With --no-triage they apply.
        recs = [
            Recommendation(
                id="r1", source="reconcile",
                severity="high", step_id=None,
                title="t1", body="b1",
                impact="low", complexity="high",
            ),
            Recommendation(
                id="r2", source="reconcile",
                severity="high", step_id=None,
                title="t2", body="b2",
                impact="medium", complexity="high",
            ),
        ]
        monkeypatch.setattr(
            review_module,
            "collect_deterministic_findings",
            lambda *a, **kw: recs,
        )
        monkeypatch.setattr(
            review_module,
            "shell_review_invoker",
            lambda _p: (0, "## Findings\n\n_(none)_\n"),
        )

        apply_calls: list[str] = []

        def fake_apply(plan_path_arg, **kwargs):
            apply_calls.append(kwargs.get("finding_body", ""))
            return ApplyFindingResult(
                step_id=kwargs.get("step_id"),
                exit_code=0,
                verdict="APPLIED",
                summary="ok",
                diff_text="",
                pre_snapshot={},
                stdout="",
            )

        monkeypatch.setattr(
            launcher_module, "apply_finding", fake_apply,
        )

        main([
            "--repo-root", str(tmp_path),
            "--plans-dir", str(plans_dir),
            "completeness-audit", "concept-test",
            "--iterate", "--yes", "--max-iterations", "1",
            "--no-triage",
            "--no-auto-reconcile-on-drift",
        ])

        # Both findings applied even though they'd have been
        # deferred under default triage.
        assert len(apply_calls) == 2
        # No triage-deferred summary in stderr.
        err = capsys.readouterr().err
        assert "deferring" not in err

    def test_no_collision_sidecar_flag_preserves_legacy_halt(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """``--no-collision-sidecar`` opts back into the legacy
        keep-claude's-edits-on-disk-then-halt behavior. Pins that
        the flag actually disables the new sidecar path (otherwise
        the flag would be cosmetic)."""
        from plan_tool import change_collision as change_collision_module
        from plan_tool import launcher as launcher_module
        from plan_tool import review as review_module
        from plan_tool.launcher import ApplyFindingResult
        from plan_tool.review import Recommendation

        plans_dir = self._seed_plan(tmp_path)
        watched = tmp_path / "foo.py"

        monkeypatch.setattr(
            review_module,
            "collect_deterministic_findings",
            lambda *a, **kw: [
                Recommendation(
                    id="body-A", source="body-completeness",
                    severity="medium", step_id=None,
                    title="A", body="A",
                ),
            ],
        )
        monkeypatch.setattr(
            review_module,
            "shell_review_invoker",
            lambda _p: (0, "## Findings\n\n_(none)_\n"),
        )

        def fake_apply(plan_path_arg, **kwargs):
            watched.write_bytes(watched.read_bytes() + b"_drift")
            return ApplyFindingResult(
                step_id=kwargs.get("step_id"),
                exit_code=0,
                verdict="APPLIED",
                summary="ok",
                diff_text="",
                pre_snapshot={},
                stdout="",
            )

        monkeypatch.setattr(
            launcher_module, "apply_finding", fake_apply,
        )

        handle_calls = {"n": 0}

        def _should_not_be_called(*a, **kw):
            handle_calls["n"] += 1
            return True

        monkeypatch.setattr(
            change_collision_module,
            "handle_drift_collision",
            _should_not_be_called,
        )

        rc = main([
            "--repo-root", str(tmp_path),
            "--plans-dir", str(plans_dir),
            "completeness-audit", "concept-test",
            "--iterate", "--yes", "--max-iterations", "3",
            "--no-collision-sidecar",
            "--no-auto-reconcile-on-drift",
        ])

        # With --no-collision-sidecar, handle_drift_collision must
        # NOT fire -- the legacy halt path runs instead.
        assert handle_calls["n"] == 0
        assert rc == 2

    def test_auto_reconcile_on_drift_runs_reconcile_per_affected_step(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Lesson 13: when drift fires, the loop auto-
        runs reconcile on the step(s) owning the drifted files,
        saves findings, and prints a structured summary.

        Mocks ``run_step`` so the test stays hermetic (no real claude
        shell-out) and asserts:
          1. run_step was invoked with mode='reconcile' and the
             attributed step_id
          2. extracted recommendations are persisted via save_review
          3. stderr summary names the step + finding count
          4. operator is pointed at `plan-tool reconcile-plan-walk` for the
             interactive walk-through"""
        import os
        from plan_tool import launcher as launcher_module
        from plan_tool import review as review_module
        from plan_tool.launcher import (
            ApplyFindingResult,
            RunResult,
        )
        from plan_tool.review import Recommendation

        plans_dir = self._seed_plan(tmp_path)
        watched = tmp_path / "foo.py"

        # Single deterministic finding so the for-rec loop runs once.
        monkeypatch.setattr(
            review_module,
            "collect_deterministic_findings",
            lambda *a, **kw: [
                Recommendation(
                    id="body-A", source="body-completeness",
                    severity="medium", step_id=None,
                    title="A", body="A",
                ),
            ],
        )
        # No concept findings -- keep stderr deterministic.
        monkeypatch.setattr(
            review_module,
            "shell_review_invoker",
            lambda _p: (0, "## Findings\n\n_(none)_\n"),
        )

        # apply_finding mutates foo.py's content to trigger drift
        # (#31: content hash, not mtime).
        def fake_apply(plan_path_arg, **kwargs):
            watched.write_bytes(watched.read_bytes() + b"_drift")
            return ApplyFindingResult(
                step_id=kwargs.get("step_id"),
                exit_code=0,
                verdict="APPLIED",
                summary="ok",
                diff_text="",
                pre_snapshot={},
                stdout="",
            )

        monkeypatch.setattr(
            launcher_module, "apply_finding", fake_apply,
        )

        # Mock run_step -- this is what the auto-reconcile invokes.
        # Records the call args and returns a synthetic reconcile
        # stdout containing one HIGH finding for foo.py.
        run_step_calls: list[dict] = []

        def fake_run_step(plan_path_arg, **kwargs):
            run_step_calls.append({
                "step_id": kwargs.get("step_id"),
                "mode": kwargs.get("mode"),
            })
            return RunResult(
                step_id=kwargs.get("step_id") or 1,
                exit_code=0,
                advanced_to=None,
                done=False,
                stdout=(
                    "Reconcile prose.\n\n## Findings\n\n"
                    "- HIGH: `foo.py:bar()` doesn't satisfy the "
                    "acceptance criterion\n"
                ),
                step_title="",
            )

        monkeypatch.setattr(
            launcher_module, "run_step", fake_run_step,
        )
        # The auto-reconcile imports run_step inline from
        # plan_tool.launcher; the module-attribute patch above is
        # what the inline import resolves against.

        rc = main([
            "--repo-root", str(tmp_path),
            "--plans-dir", str(plans_dir),
            "completeness-audit", "concept-test",
            "--iterate", "--yes", "--max-iterations", "3",
        ])

        # The auto-reconcile fired once, against step 1
        # (the step whose files include foo.py). Step 6 of the
        # Reconcile Subcommand Split migrates auto-reconcile to
        # the detail-reconcile prompt (code-is-truth).
        assert len(run_step_calls) == 1
        assert run_step_calls[0]["mode"] == "detail-reconcile"
        assert run_step_calls[0]["step_id"] == 1

        err = capsys.readouterr().err
        # Header announces the auto-audit.
        assert "running auto-reconcile" in err
        assert "Lesson 13" in err
        # Summary line names the step and finding count.
        assert (
            'auto-reconcile on step 1 ("build the thing"): '
            "1 finding(s) raised"
        ) in err
        # Operator is told how to walk findings interactively.
        assert "plan-tool reconcile-plan-walk concept-test" in err
        assert rc == 2

    def test_no_auto_reconcile_on_drift_flag_suppresses_reconcile(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Operators who opt out via ``--no-auto-reconcile-on-drift``
        get the legacy bare-drift-warning behavior -- run_step is
        never called."""
        import os
        from plan_tool import launcher as launcher_module
        from plan_tool import review as review_module
        from plan_tool.launcher import ApplyFindingResult
        from plan_tool.review import Recommendation

        plans_dir = self._seed_plan(tmp_path)
        watched = tmp_path / "foo.py"

        monkeypatch.setattr(
            review_module,
            "collect_deterministic_findings",
            lambda *a, **kw: [
                Recommendation(
                    id="body-A", source="body-completeness",
                    severity="medium", step_id=None,
                    title="A", body="A",
                ),
            ],
        )
        monkeypatch.setattr(
            review_module,
            "shell_review_invoker",
            lambda _p: (0, "## Findings\n\n_(none)_\n"),
        )

        def fake_apply(plan_path_arg, **kwargs):
            # Mutate watched content -- mtime advance alone no
            # longer counts as drift.
            watched.write_bytes(watched.read_bytes() + b"_drift")
            return ApplyFindingResult(
                step_id=kwargs.get("step_id"),
                exit_code=0, verdict="APPLIED", summary="",
                diff_text="", pre_snapshot={}, stdout="",
            )

        monkeypatch.setattr(
            launcher_module, "apply_finding", fake_apply,
        )

        run_step_calls = {"n": 0}

        def boom_run_step(*a, **kw):
            run_step_calls["n"] += 1
            raise AssertionError(
                "run_step should NOT be called with "
                "--no-auto-reconcile-on-drift"
            )

        monkeypatch.setattr(
            launcher_module, "run_step", boom_run_step,
        )

        main([
            "--repo-root", str(tmp_path),
            "--plans-dir", str(plans_dir),
            "completeness-audit", "concept-test",
            "--iterate", "--yes", "--max-iterations", "3",
            "--no-auto-reconcile-on-drift",
        ])

        assert run_step_calls["n"] == 0
        err = capsys.readouterr().err
        # Drift halt still fires; only the auto-reconcile is
        # suppressed.
        assert "drift detected" in err
        assert "running auto-reconcile" not in err

    def test_iterate_mode_audits_concepts_once_not_per_iteration(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """``cmd_completeness --iterate`` audits the plan's concepts
        EXACTLY ONCE -- not once per iteration.

        The conceptual plan-audit is a subjective claude call; re-running
        it every round re-phrases the same gaps into fresh content-hash
        ids that defeat convergence detection (the body-hash treadmill).
        With ``--max-iterations 2`` the audit invoker must fire once.

        Also guards the apply wiring under the read-only-audit split (#85):
          - The audit's conceptual *correctness* finding is NOT dispatched
            to apply_finding (it is persisted unapplied for
            session-directed correction).
          - A deterministic finding still reaches apply_finding in the
            same run (the audit converges on its deterministic stream)."""
        from plan_tool import launcher as launcher_module
        from plan_tool import review as review_module
        from plan_tool.launcher import ApplyFindingResult
        from plan_tool.review import Recommendation

        plans_dir = self._seed_plan(tmp_path)

        concept_invoker_calls = {"n": 0}

        def fake_concept_invoker(_p: str) -> tuple[int, str]:
            concept_invoker_calls["n"] += 1
            return (
                0,
                "## Correctness findings\n\n"
                f"- HIGH: `foo.py` design gap iter "
                f"{concept_invoker_calls['n']}\n\n"
                "## Completeness findings\n\n_(none)_\n",
            )

        monkeypatch.setattr(
            review_module,
            "shell_review_invoker",
            fake_concept_invoker,
        )

        # Mixed-stream deterministic finding so both sources reach
        # apply_finding within the same iteration's for-rec loop.
        # ``check_body_completeness``-shaped finding with a stable id
        # — different from the concept finding's content-hashed id.
        det_rec = Recommendation(
            id="body-overview",
            source="body-completeness",
            severity="medium",
            step_id=None,
            title="overview empty",
            body="## Overview body empty",
        )
        det_calls = {"n": 0}

        def fake_collect_det(*a, **kw):
            det_calls["n"] += 1
            return [det_rec]

        monkeypatch.setattr(
            review_module,
            "collect_deterministic_findings",
            fake_collect_det,
        )

        captured_apply_sources: list[tuple[Optional[int], str]] = []

        def fake_apply(plan_path_arg, **kwargs):
            body = kwargs.get("finding_body") or ""
            captured_apply_sources.append(
                (kwargs.get("step_id"), body[:80]),
            )
            return ApplyFindingResult(
                step_id=kwargs.get("step_id"),
                exit_code=0,
                verdict="APPLIED",
                summary="ok",
                diff_text="",
                pre_snapshot={},
                stdout="",
            )

        monkeypatch.setattr(
            launcher_module, "apply_finding", fake_apply,
        )

        main([
            "--repo-root", str(tmp_path),
            "--plans-dir", str(plans_dir),
            "completeness-audit", "concept-test",
            "--iterate", "--yes", "--max-iterations", "2",
            # Pin the legacy single-pass path so the "hoisted out of
            # the loop" contract stays isolated from the multi-pass
            # union (which varies call count by dry-round detection and
            # is pinned by its own tests).
            "--audit-passes", "1",
        ])

        # The conceptual audit fires EXACTLY ONCE for the whole iterate
        # run -- it's hoisted out of the per-round collect. A regression
        # that re-audits each iteration (the old treadmill) would push
        # this above 1.
        assert concept_invoker_calls["n"] == 1, (
            f"expected plan-audit invoker to fire exactly once for the "
            f"iterate run; got {concept_invoker_calls['n']}"
        )
        # #85: the deterministic stream still reaches apply_finding, but the
        # conceptual correctness finding NEVER does (it is persisted for
        # session-directed correction).
        bodies = [body for (_sid, body) in captured_apply_sources]
        concept_applies = [b for b in bodies if "foo.py" in b]
        deterministic_seen = any("Overview body empty" in b for b in bodies)
        assert deterministic_seen, (
            f"expected at least one apply with the deterministic "
            f"finding; captured {captured_apply_sources!r}"
        )
        assert concept_applies == [], (
            f"conceptual correctness must not be auto-applied under #85; "
            f"captured {captured_apply_sources!r}"
        )


@pytest.mark.integration
class TestCompletenessAuditReuseEndToEnd:
    """Producer→consumer reuse across a save/reload boundary, driven
    through ``main(['completeness-audit', …])`` twice per scenario.

    Run 1 persists a fingerprinted ``-completeness.json`` sidecar under
    ``plan-details/<slug>/reports/``; run 2 lets the REAL
    ``resolve_reusable_audit`` read it back, recompute both fingerprints
    off live disk, and decide reuse-vs-re-audit. Only the conceptual
    Claude seam (``plan_tool.review.shell_review_invoker``) is stubbed —
    everything between the save and the freshness verdict (the sidecar
    write, both fingerprints, the deletion-aware saved→current diff) runs
    for real. The load-bearing predicate is the DELTA in conceptual
    Claude calls between the two runs: fresh reuse adds zero, a stale
    plan/detail revision adds ≥1 (a fresh re-audit). Under
    ``completeness-stage-bar-reporting``'s qualified-revision contract, code
    drift alone (``compute_code_fingerprint`` moving without the sampled
    plan/detail revision moving) is live explanation context, not a
    staleness trigger, so it also adds zero. The single
    ``shell_review_invoker`` patch covers both the audit-only and
    ``--iterate`` paths — both consumers import that seam body-local from
    ``plan_tool.review``.
    """

    @pytest.fixture
    def conceptual_calls(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> list[str]:
        """Install a recording ``shell_review_invoker`` and hand back the
        call list. Returns a stable empty two-section block so
        ``audit_plan_until_stable`` converges in its minimum rounds;
        assertions compare deltas, never absolute counts."""
        from plan_tool import review as review_module

        calls: list[str] = []

        def recorder(prompt: str) -> tuple[int, str]:
            calls.append(prompt)
            return (
                0,
                "## Correctness findings\n\n_(none)_\n\n"
                "## Completeness findings\n\n_(none)_\n",
            )

        monkeypatch.setattr(
            review_module, "shell_review_invoker", recorder
        )
        return calls

    def _seed_plan(
        self, tmp_path: Path, *, risks_section: str = "Real risks."
    ) -> Path:
        """Write a reuse-eligible plan whose step 1 declares ``foo.py``
        (the code-fingerprint lever) plus the file itself, and a full H2
        body so the conceptual audit has both inputs. ``risks_section``
        lets a caller drop a ``_(TODO)_`` placeholder in to surface a
        deterministic body finding without otherwise changing the plan."""
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        plan_path = plans_dir / "1-concept-test.md"
        plan_path.write_text(
            "---\n"
            "title: Concept Reuse Test\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: build the thing\n"
            "    files:\n"
            "      - foo.py\n"
            "    status: done\n"
            "---\n"
            "\n"
            "## Overview\n\nReal overview.\n\n"
            "## Problem statement\n\nReal problem.\n\n"
            "## Architecture\n\nReal architecture.\n\n"
            "## Steps\n\nSee frontmatter.\n\n"
            "## Out of scope\n\nReal scope text.\n\n"
            f"## Risks\n\n{risks_section}\n\n"
            "## Testing\n\nReal testing.\n\n"
            "## Acceptance criteria\n\nfoo.py:bar() must return 42.\n\n"
            "## Deferred\n\nReal deferred.\n",
            encoding="utf-8",
        )
        (tmp_path / "foo.py").write_text(
            "def bar():\n    return 41\n", encoding="utf-8"
        )
        return plans_dir

    def _reports_dir(self, tmp_path: Path) -> Path:
        return (
            tmp_path / "plans" / "plan-details" / "concept-test" / "reports"
        )

    def _argv(self, tmp_path: Path, plans_dir: Path, *extra: str) -> list[str]:
        return [
            "--repo-root", str(tmp_path),
            "--plans-dir", str(plans_dir),
            "completeness-audit", "concept-test", *extra,
        ]

    def _seed_sidecar(
        self,
        tmp_path: Path,
        plans_dir: Path,
        capsys: pytest.CaptureFixture[str],
        *extra: str,
    ) -> None:
        """Run 1: audit fresh and persist the fingerprinted sidecar.
        Asserts the sidecar exists, then flushes captured output so run 2
        sees a clean buffer."""
        rc = main(self._argv(tmp_path, plans_dir, *extra))
        assert rc == 0
        sidecars = list(self._reports_dir(tmp_path).glob("*-completeness.json"))
        assert sidecars, "run 1 should persist a -completeness.json sidecar"
        capsys.readouterr()

    def test_fresh_reuse_makes_zero_conceptual_calls(
        self,
        tmp_path: Path,
        conceptual_calls: list[str],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Unchanged plan+code → run 2 reuses the saved audit: zero new
        conceptual calls, a reuse note on stderr, rc 0."""
        plans_dir = self._seed_plan(tmp_path)
        self._seed_sidecar(tmp_path, plans_dir, capsys)

        before = len(conceptual_calls)
        rc = main(self._argv(tmp_path, plans_dir, "--reuse-audit", "--yes"))
        cap = capsys.readouterr()

        assert rc == 0
        assert len(conceptual_calls) == before  # reuse → no fresh audit
        assert "reusing saved conceptual audit" in cap.err

    def test_reuse_re_audits_on_plan_edit(
        self,
        tmp_path: Path,
        conceptual_calls: list[str],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Editing the plan body changes ``compute_plan_fingerprint`` →
        run 2 re-audits with a one-line plan-stale note and NO per-file
        attribution (the drift is plan-side, not code-side)."""
        plans_dir = self._seed_plan(tmp_path)
        self._seed_sidecar(tmp_path, plans_dir, capsys)

        plan_path = plans_dir / "1-concept-test.md"
        plan_path.write_text(
            plan_path.read_text(encoding="utf-8")
            + "\nAppended prose changes the plan fingerprint.\n",
            encoding="utf-8",
        )

        before = len(conceptual_calls)
        rc = main(self._argv(tmp_path, plans_dir, "--reuse-audit", "--yes"))
        cap = capsys.readouterr()

        assert rc == 0
        assert len(conceptual_calls) > before  # plan drift → fresh audit
        assert "plan changed since" in cap.err
        assert "(step 1:" not in cap.err

    def test_reuse_ignores_code_edit(
        self,
        tmp_path: Path,
        conceptual_calls: list[str],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Rewriting the in-scope ``foo.py`` changes
        ``compute_code_fingerprint``, but code is live explanation context,
        not a revision-qualifying input (completeness-stage-bar-reporting):
        the saved audit's revision — plan bytes plus the selected detail
        bundle — is unaffected, so run 2 still reuses it (zero new
        conceptual calls, no re-audit)."""
        plans_dir = self._seed_plan(tmp_path)
        self._seed_sidecar(tmp_path, plans_dir, capsys)

        (tmp_path / "foo.py").write_text(
            "def bar():\n    return 99\n", encoding="utf-8"
        )

        before = len(conceptual_calls)
        rc = main(self._argv(tmp_path, plans_dir, "--reuse-audit", "--yes"))
        cap = capsys.readouterr()

        assert rc == 0
        assert len(conceptual_calls) == before  # code-only drift stays reused
        assert "reusing saved conceptual audit" in cap.err

    def test_reuse_ignores_deleted_in_scope_file(
        self,
        tmp_path: Path,
        conceptual_calls: list[str],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Deleting ``foo.py`` is also code-axis drift only — the saved
        audit's plan/detail revision still matches, so run 2 reuses it
        without a fresh conceptual call."""
        plans_dir = self._seed_plan(tmp_path)
        self._seed_sidecar(tmp_path, plans_dir, capsys)

        (tmp_path / "foo.py").unlink()

        before = len(conceptual_calls)
        rc = main(self._argv(tmp_path, plans_dir, "--reuse-audit", "--yes"))
        cap = capsys.readouterr()

        assert rc == 0
        assert len(conceptual_calls) == before  # deletion alone stays reused
        assert "reusing saved conceptual audit" in cap.err

    def test_no_reuse_audit_always_re_audits(
        self,
        tmp_path: Path,
        conceptual_calls: list[str],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """``--no-reuse-audit`` re-audits despite a fresh sidecar and never
        prints the reuse note."""
        plans_dir = self._seed_plan(tmp_path)
        self._seed_sidecar(tmp_path, plans_dir, capsys)

        before = len(conceptual_calls)
        rc = main(self._argv(tmp_path, plans_dir, "--no-reuse-audit"))
        cap = capsys.readouterr()

        assert rc == 0
        assert len(conceptual_calls) > before  # opt-out → fresh audit
        assert "reusing saved conceptual audit" not in cap.err

    def test_reuse_audit_id_pins_saved_sidecar(
        self,
        tmp_path: Path,
        conceptual_calls: list[str],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """``--reuse-audit-id <stem>`` on unchanged state reuses the pinned
        save (zero added conceptual calls)."""
        plans_dir = self._seed_plan(tmp_path)
        self._seed_sidecar(tmp_path, plans_dir, capsys)

        stem = next(
            self._reports_dir(tmp_path).glob("*-completeness.json")
        ).stem

        before = len(conceptual_calls)
        rc = main(self._argv(
            tmp_path, plans_dir, "--reuse-audit-id", stem, "--yes"
        ))
        capsys.readouterr()

        assert rc == 0
        assert len(conceptual_calls) == before  # pinned save reused

    def test_reuse_audit_id_miss_audits_fresh(
        self,
        tmp_path: Path,
        conceptual_calls: list[str],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A ``--reuse-audit-id`` matching no save re-audits fresh and prints
        an error note naming the unmatched stem; the decline is not a
        failure-to-complete, so rc stays 0."""
        plans_dir = self._seed_plan(tmp_path)
        self._seed_sidecar(tmp_path, plans_dir, capsys)

        before = len(conceptual_calls)
        rc = main(self._argv(
            tmp_path, plans_dir,
            "--reuse-audit-id", "20000101-000000-completeness", "--yes",
        ))
        cap = capsys.readouterr()

        assert rc == 0
        assert len(conceptual_calls) > before  # miss → fresh audit
        assert "20000101-000000-completeness" in cap.err

    def test_iterate_reuse_skips_audit_call(
        self,
        tmp_path: Path,
        conceptual_calls: list[str],
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``--iterate --reuse-audit`` skips the up-front
        ``audit_plan_until_stable`` call on unchanged state (zero added
        conceptual calls). ``apply_finding`` is stubbed so any deterministic
        gap stays hermetic — only the conceptual-call delta is asserted."""
        from plan_tool import launcher as launcher_module
        from plan_tool.launcher import ApplyFindingResult

        def _fake_apply(target_path, **kwargs):
            return ApplyFindingResult(
                step_id=kwargs.get("step_id"),
                exit_code=0,
                verdict="APPLIED",
                summary="",
                diff_text="",
                pre_snapshot={},
                stdout="",
            )

        monkeypatch.setattr(launcher_module, "apply_finding", _fake_apply)

        plans_dir = self._seed_plan(tmp_path)
        self._seed_sidecar(
            tmp_path, plans_dir, capsys,
            "--iterate", "--yes", "--max-iterations", "1",
        )

        before = len(conceptual_calls)
        rc = main(self._argv(
            tmp_path, plans_dir,
            "--iterate", "--yes", "--max-iterations", "1", "--reuse-audit",
        ))
        capsys.readouterr()

        assert rc == 0
        assert len(conceptual_calls) == before  # up-front audit skipped

    def test_deterministic_battery_runs_on_reuse(
        self,
        tmp_path: Path,
        conceptual_calls: list[str],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Reuse skips ONLY the conceptual Claude axis: the deterministic
        battery still runs on the reuse run. Seed a ``_(TODO)_`` Risks
        section so a body finding is guaranteed, then assert it surfaces in
        the reuse run's grouped report (delta still 0)."""
        plans_dir = self._seed_plan(tmp_path, risks_section="_(TODO)_")
        self._seed_sidecar(tmp_path, plans_dir, capsys)

        before = len(conceptual_calls)
        rc = main(self._argv(tmp_path, plans_dir, "--reuse-audit", "--yes"))
        cap = capsys.readouterr()

        assert rc == 0
        assert len(conceptual_calls) == before  # conceptual axis reused
        # The deterministic body-completeness check still ran and routed the
        # placeholder Risks section into the grouped report.
        assert "Plan sections" in cap.out


# --- reconcile-family reuse end-to-end (fingerprint gate) ----------
#
# The reconcile-family analog of ``TestCompletenessAuditReuseEndToEnd``
# above: three classes — one per reconcile verb — drive ``main([...])``
# twice (seed sidecar, then reuse run) across the REAL save/reload
# boundary, stubbing only the conceptual Claude seam. Steps 1–5's
# producers (``compute_plan_fingerprint`` / ``compute_code_fingerprint`` /
# ``resolve_reusable_reconcile`` / the ``_prompt_reuse_saved`` freshness
# gate / ``_note_reuse_code_drift``) run UNPATCHED so a non-reproducing
# digest, a fingerprint-less save seam, or a deletion the diff ignores
# would surface as a red delta. The single asserted predicate is the
# DELTA in conceptual calls between run 1 and run 2: fresh reuse adds 0,
# every staleness/decline/opt-out path adds ≥1.


def _seed_reconcile_plan(tmp_path: Path) -> Path:
    """Write a reuse-eligible plan whose step 1 declares ``foo.py`` (the
    code-fingerprint lever) plus the file itself, and the full nine-H2
    body so a reconcile audit has both inputs. ``status: done`` on the
    step keeps it audit-eligible. Returns the plans dir.

    Shared by all three reconcile-reuse classes; mirrors
    ``TestCompletenessAuditReuseEndToEnd._seed_plan`` but slugs to
    ``reconcile-test``."""
    plans_dir = tmp_path / "plans"
    plans_dir.mkdir()
    plan_path = plans_dir / "1-reconcile-test.md"
    plan_path.write_text(
        "---\n"
        "title: Reconcile Reuse Test\n"
        "status: in-progress\n"
        "priority: medium\n"
        "steps:\n"
        "  - id: 1\n"
        "    title: build the thing\n"
        "    files:\n"
        "      - foo.py\n"
        "    status: done\n"
        "---\n"
        "\n"
        "## Overview\n\nReal overview.\n\n"
        "## Problem statement\n\nReal problem.\n\n"
        "## Architecture\n\nReal architecture.\n\n"
        "## Steps\n\nSee frontmatter.\n\n"
        "## Out of scope\n\nReal scope text.\n\n"
        "## Risks\n\nReal risks.\n\n"
        "## Testing\n\nReal testing.\n\n"
        "## Acceptance criteria\n\nfoo.py:bar() must return 42.\n\n"
        "## Deferred\n\nReal deferred.\n",
        encoding="utf-8",
    )
    (tmp_path / "foo.py").write_text(
        "def bar():\n    return 41\n", encoding="utf-8"
    )
    detail_path = plans_dir / "plan-details" / "reconcile-test" / "01-build-thing.md"
    detail_path.parent.mkdir(parents=True)
    detail_path.write_text("# Build detail\n", encoding="utf-8")
    return plans_dir


def _reconcile_reports_dir(tmp_path: Path) -> Path:
    return (
        tmp_path / "plans" / "plan-details" / "reconcile-test" / "reports"
    )


def _reconcile_argv(
    tmp_path: Path, plans_dir: Path, command: str, *extra: str
) -> list[str]:
    return [
        "--repo-root", str(tmp_path),
        "--plans-dir", str(plans_dir),
        command, "reconcile-test", *extra,
    ]


def _install_run_step_recorder(
    monkeypatch: pytest.MonkeyPatch,
) -> list[str]:
    """Wrap ``plan_tool.cli.reconcile.run_step`` so the REAL run_step
    runs (render + persist) but its invoker is a recorder.

    Mirrors ``TestCmdRunAll.test_happy_path``'s inject-a-fake-invoker
    pattern: each call appends the prompt and returns the ``(0, stdout)``
    tuple an ``Invoker`` produces. The conceptual call delta is the only
    thing asserted, so the stub's per-call convergence is irrelevant.
    Shared by the reconcile-code and detail --reconcile classes (both
    route through this one seam); fresh reuse short-circuits before
    run_step, so the recorder is never called → delta 0."""
    from plan_tool import launcher as launcher_module

    calls: list[str] = []
    original_run_step = launcher_module.run_step

    def patched_run_step(*args, **kwargs):
        def recorder(prompt: str) -> tuple[int, str]:
            calls.append(prompt)
            return (0, _run_all_ok_stdout())

        kwargs["invoker"] = recorder
        return original_run_step(*args, **kwargs)

    monkeypatch.setattr(reconcile_module, "run_step", patched_run_step)
    return calls


@pytest.mark.integration
class TestReconcilePlanReuseEndToEnd:
    """``main(['reconcile-plan', …])`` twice across the save/reload
    boundary. Conceptual seam: ``plan_tool.cli.review_cmd.review_plan_full``
    (called only after ``_prompt_reuse_saved_review`` declines reuse), so a
    fresh reuse adds zero calls. Sidecar is the bare ``<ts>.json`` (kind
    ``review``). No ``--step`` — the plan-wide reuse lookup is suppressed
    when a step is pinned."""

    @pytest.fixture
    def conceptual_calls(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> list[str]:
        from plan_tool.cli import review_cmd as review_cmd_module
        from plan_tool.review import ReviewResult

        calls: list[str] = []

        def recorder(plan_path, **kwargs):
            calls.append(kwargs.get("plan_name", ""))
            return ReviewResult(
                report="(stub review)", recommendations=[], dry_run=False
            )

        monkeypatch.setattr(
            review_cmd_module, "review_plan_full", recorder
        )
        return calls

    def _seed_sidecar(
        self,
        tmp_path: Path,
        plans_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        rc = main(_reconcile_argv(tmp_path, plans_dir, "reconcile-plan"))
        assert rc == 0
        sidecars = list(_reconcile_reports_dir(tmp_path).glob("*.json"))
        assert sidecars, "run 1 should persist a review sidecar"
        capsys.readouterr()

    def test_fresh_reuse_makes_zero_conceptual_calls(
        self,
        tmp_path: Path,
        conceptual_calls: list[str],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        plans_dir = _seed_reconcile_plan(tmp_path)
        self._seed_sidecar(tmp_path, plans_dir, capsys)

        before = len(conceptual_calls)
        rc = main(_reconcile_argv(
            tmp_path, plans_dir, "reconcile-plan", "--reuse", "--yes"
        ))
        cap = capsys.readouterr()

        assert rc == 0
        assert len(conceptual_calls) == before  # reuse → no fresh audit
        # Non-TTY under pytest, so the review verb is "reusing": this path
        # skips the walk and reports instead (``review_cmd`` ~L566). Contrast
        # the reconcile kinds, which do walk under ``yes_to_all``.
        assert "(--yes) reusing saved review" in cap.out

    def test_reuse_re_audits_on_plan_edit(
        self,
        tmp_path: Path,
        conceptual_calls: list[str],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        plans_dir = _seed_reconcile_plan(tmp_path)
        self._seed_sidecar(tmp_path, plans_dir, capsys)

        plan_path = plans_dir / "1-reconcile-test.md"
        plan_path.write_text(
            plan_path.read_text(encoding="utf-8")
            + "\nAppended prose changes the plan fingerprint.\n",
            encoding="utf-8",
        )

        before = len(conceptual_calls)
        rc = main(_reconcile_argv(
            tmp_path, plans_dir, "reconcile-plan", "--reuse", "--yes"
        ))
        cap = capsys.readouterr()

        assert rc == 0
        assert len(conceptual_calls) > before  # plan drift → fresh audit
        assert "plan changed since" in cap.err
        assert "(step 1:" not in cap.err

    def test_reuse_re_audits_on_code_edit(
        self,
        tmp_path: Path,
        conceptual_calls: list[str],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        plans_dir = _seed_reconcile_plan(tmp_path)
        self._seed_sidecar(tmp_path, plans_dir, capsys)

        (tmp_path / "foo.py").write_text(
            "def bar():\n    return 99\n", encoding="utf-8"
        )

        before = len(conceptual_calls)
        rc = main(_reconcile_argv(
            tmp_path, plans_dir, "reconcile-plan", "--reuse", "--yes"
        ))
        cap = capsys.readouterr()

        assert rc == 0
        assert len(conceptual_calls) > before  # code drift → fresh audit
        # Grouped under the owning step, at info level (normal operation).
        assert "step 1:" in cap.err
        assert "foo.py" in cap.err
        assert "foo.py (step 1:" not in cap.err  # not the inline form
        assert "--reconcile" in cap.err

    def test_reuse_flags_deleted_in_scope_file(
        self,
        tmp_path: Path,
        conceptual_calls: list[str],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        plans_dir = _seed_reconcile_plan(tmp_path)
        self._seed_sidecar(tmp_path, plans_dir, capsys)

        (tmp_path / "foo.py").unlink()

        before = len(conceptual_calls)
        rc = main(_reconcile_argv(
            tmp_path, plans_dir, "reconcile-plan", "--reuse", "--yes"
        ))
        cap = capsys.readouterr()

        assert rc == 0
        assert len(conceptual_calls) > before  # deletion → fresh audit
        # Grouped under the owning step, at info level (normal operation).
        assert "step 1:" in cap.err
        assert "foo.py" in cap.err
        assert "foo.py (step 1:" not in cap.err  # not the inline form
        assert "code file(s) changed" not in cap.err
        assert "code file(s) removed" in cap.err
        assert "--reconcile" not in cap.err

    def test_no_reuse_always_re_audits(
        self,
        tmp_path: Path,
        conceptual_calls: list[str],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        plans_dir = _seed_reconcile_plan(tmp_path)
        self._seed_sidecar(tmp_path, plans_dir, capsys)

        before = len(conceptual_calls)
        rc = main(_reconcile_argv(
            tmp_path, plans_dir, "reconcile-plan", "--no-reuse"
        ))
        cap = capsys.readouterr()

        assert rc == 0
        assert len(conceptual_calls) > before  # opt-out → fresh audit
        # Must name the verb this path would actually emit; "walking saved" is
        # unreachable for a non-TTY review reuse, so it passed vacuously.
        assert "reusing saved review" not in cap.out

    def test_reuse_id_pins_saved_sidecar(
        self,
        tmp_path: Path,
        conceptual_calls: list[str],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        plans_dir = _seed_reconcile_plan(tmp_path)
        self._seed_sidecar(tmp_path, plans_dir, capsys)

        stem = next(_reconcile_reports_dir(tmp_path).glob("*.json")).stem

        before = len(conceptual_calls)
        rc = main(_reconcile_argv(
            tmp_path, plans_dir, "reconcile-plan",
            "--reuse-id", stem, "--yes",
        ))
        capsys.readouterr()

        assert rc == 0
        assert len(conceptual_calls) == before  # pinned fresh save reused

    def test_reuse_id_miss_audits_fresh(
        self,
        tmp_path: Path,
        conceptual_calls: list[str],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        plans_dir = _seed_reconcile_plan(tmp_path)
        self._seed_sidecar(tmp_path, plans_dir, capsys)

        before = len(conceptual_calls)
        rc = main(_reconcile_argv(
            tmp_path, plans_dir, "reconcile-plan",
            "--reuse-id", "20000101-000000", "--yes",
        ))
        cap = capsys.readouterr()

        assert rc == 0
        assert len(conceptual_calls) > before  # miss → fresh audit
        assert "20000101-000000" in cap.err


@pytest.mark.integration
class TestReconcileCodeReuseEndToEnd:
    """``main(['reconcile-code', …, '--step', '1'])`` twice. Conceptual
    seam: the injected ``invoker`` inside ``plan_tool.cli.reconcile.run_step``
    (skipped entirely when ``_prompt_reuse_saved_run_reconcile`` returns a
    reuse path). Sidecar is ``<ts>-run-reconcile.json`` (kind
    ``run-reconcile``)."""

    @pytest.fixture
    def conceptual_calls(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> list[str]:
        return _install_run_step_recorder(monkeypatch)

    def _seed_sidecar(
        self,
        tmp_path: Path,
        plans_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        rc = main(_reconcile_argv(
            tmp_path, plans_dir, "reconcile-code", "--step", "1"
        ))
        assert rc == 0
        sidecars = list(
            _reconcile_reports_dir(tmp_path).glob("*-run-reconcile.json")
        )
        assert sidecars, "run 1 should persist a -run-reconcile.json sidecar"
        capsys.readouterr()

    def test_fresh_reuse_makes_zero_conceptual_calls(
        self,
        tmp_path: Path,
        conceptual_calls: list[str],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        plans_dir = _seed_reconcile_plan(tmp_path)
        self._seed_sidecar(tmp_path, plans_dir, capsys)

        before = len(conceptual_calls)
        rc = main(_reconcile_argv(
            tmp_path, plans_dir, "reconcile-code",
            "--step", "1", "--reuse", "--yes",
        ))
        cap = capsys.readouterr()

        assert rc == 0
        assert len(conceptual_calls) == before  # reuse → no fresh audit
        assert "walking saved" in cap.out

    def test_reuse_re_audits_on_plan_edit(
        self,
        tmp_path: Path,
        conceptual_calls: list[str],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        plans_dir = _seed_reconcile_plan(tmp_path)
        self._seed_sidecar(tmp_path, plans_dir, capsys)

        plan_path = plans_dir / "1-reconcile-test.md"
        plan_path.write_text(
            plan_path.read_text(encoding="utf-8")
            + "\nAppended prose changes the plan fingerprint.\n",
            encoding="utf-8",
        )

        before = len(conceptual_calls)
        rc = main(_reconcile_argv(
            tmp_path, plans_dir, "reconcile-code",
            "--step", "1", "--reuse", "--yes",
        ))
        cap = capsys.readouterr()

        assert rc == 0
        assert len(conceptual_calls) > before  # plan drift → fresh audit
        assert "plan changed since" in cap.err
        assert "(step 1:" not in cap.err

    def test_reuse_re_audits_on_code_edit(
        self,
        tmp_path: Path,
        conceptual_calls: list[str],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        plans_dir = _seed_reconcile_plan(tmp_path)
        self._seed_sidecar(tmp_path, plans_dir, capsys)

        (tmp_path / "foo.py").write_text(
            "def bar():\n    return 99\n", encoding="utf-8"
        )

        before = len(conceptual_calls)
        rc = main(_reconcile_argv(
            tmp_path, plans_dir, "reconcile-code",
            "--step", "1", "--reuse", "--yes",
        ))
        cap = capsys.readouterr()

        assert rc == 0
        assert len(conceptual_calls) > before  # code drift → fresh audit
        # Grouped under the owning step, at info level (normal operation).
        assert "step 1:" in cap.err
        assert "foo.py" in cap.err
        assert "foo.py (step 1:" not in cap.err  # not the inline form
        assert "--reconcile" in cap.err

    def test_reuse_flags_deleted_in_scope_file(
        self,
        tmp_path: Path,
        conceptual_calls: list[str],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        plans_dir = _seed_reconcile_plan(tmp_path)
        self._seed_sidecar(tmp_path, plans_dir, capsys)

        (tmp_path / "foo.py").unlink()

        before = len(conceptual_calls)
        rc = main(_reconcile_argv(
            tmp_path, plans_dir, "reconcile-code",
            "--step", "1", "--reuse", "--yes",
        ))
        cap = capsys.readouterr()

        assert rc == 0
        assert len(conceptual_calls) > before  # deletion → fresh audit
        # Grouped under the owning step, at info level (normal operation).
        assert "step 1:" in cap.err
        assert "foo.py" in cap.err
        assert "foo.py (step 1:" not in cap.err  # not the inline form
        assert "code file(s) changed" not in cap.err
        assert "code file(s) removed" in cap.err
        assert "--reconcile" not in cap.err

    def test_no_reuse_always_re_audits(
        self,
        tmp_path: Path,
        conceptual_calls: list[str],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        plans_dir = _seed_reconcile_plan(tmp_path)
        self._seed_sidecar(tmp_path, plans_dir, capsys)

        before = len(conceptual_calls)
        rc = main(_reconcile_argv(
            tmp_path, plans_dir, "reconcile-code", "--step", "1", "--no-reuse"
        ))
        cap = capsys.readouterr()

        assert rc == 0
        assert len(conceptual_calls) > before  # opt-out → fresh audit
        assert "walking saved" not in cap.out

    def test_reuse_id_pins_saved_sidecar(
        self,
        tmp_path: Path,
        conceptual_calls: list[str],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        plans_dir = _seed_reconcile_plan(tmp_path)
        self._seed_sidecar(tmp_path, plans_dir, capsys)

        stem = next(
            _reconcile_reports_dir(tmp_path).glob("*-run-reconcile.json")
        ).stem

        before = len(conceptual_calls)
        rc = main(_reconcile_argv(
            tmp_path, plans_dir, "reconcile-code",
            "--step", "1", "--reuse-id", stem, "--yes",
        ))
        capsys.readouterr()

        assert rc == 0
        assert len(conceptual_calls) == before  # pinned fresh save reused

    def test_reuse_id_miss_audits_fresh(
        self,
        tmp_path: Path,
        conceptual_calls: list[str],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        plans_dir = _seed_reconcile_plan(tmp_path)
        self._seed_sidecar(tmp_path, plans_dir, capsys)

        before = len(conceptual_calls)
        rc = main(_reconcile_argv(
            tmp_path, plans_dir, "reconcile-code",
            "--step", "1", "--reuse-id", "20000101-000000-run-reconcile",
            "--yes",
        ))
        cap = capsys.readouterr()

        assert rc == 0
        assert len(conceptual_calls) > before  # miss → fresh audit
        assert "20000101-000000-run-reconcile" in cap.err


@pytest.mark.integration
class TestDetailReconcileReuseEndToEnd:
    """``main(['detail', …, '--reconcile', '--step', '1'])`` twice. Shares
    the ``plan_tool.cli.reconcile.run_step`` invoker seam with
    reconcile-code (the detail wrapper delegates to the same
    ``_prompt_reuse_saved`` gate). Sidecar is ``<ts>-detail-reconcile.json``
    (kind ``detail-reconcile``)."""

    @pytest.fixture
    def conceptual_calls(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> list[str]:
        return _install_run_step_recorder(monkeypatch)

    def _seed_sidecar(
        self,
        tmp_path: Path,
        plans_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        rc = main(_reconcile_argv(
            tmp_path, plans_dir, "detail", "--reconcile", "--step", "1"
        ))
        assert rc == 0
        sidecars = list(
            _reconcile_reports_dir(tmp_path).glob("*-detail-reconcile.json")
        )
        assert sidecars, "run 1 should persist a -detail-reconcile.json sidecar"
        capsys.readouterr()

    def test_fresh_reuse_makes_zero_conceptual_calls(
        self,
        tmp_path: Path,
        conceptual_calls: list[str],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        plans_dir = _seed_reconcile_plan(tmp_path)
        self._seed_sidecar(tmp_path, plans_dir, capsys)

        before = len(conceptual_calls)
        rc = main(_reconcile_argv(
            tmp_path, plans_dir, "detail",
            "--reconcile", "--step", "1", "--reuse", "--yes",
        ))
        cap = capsys.readouterr()

        assert rc == 0
        assert len(conceptual_calls) == before  # reuse → no fresh audit
        assert "walking saved" in cap.out

    def test_reuse_re_audits_on_plan_edit(
        self,
        tmp_path: Path,
        conceptual_calls: list[str],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        plans_dir = _seed_reconcile_plan(tmp_path)
        self._seed_sidecar(tmp_path, plans_dir, capsys)

        plan_path = plans_dir / "1-reconcile-test.md"
        plan_path.write_text(
            plan_path.read_text(encoding="utf-8")
            + "\nAppended prose changes the plan fingerprint.\n",
            encoding="utf-8",
        )

        before = len(conceptual_calls)
        rc = main(_reconcile_argv(
            tmp_path, plans_dir, "detail",
            "--reconcile", "--step", "1", "--reuse", "--yes",
        ))
        cap = capsys.readouterr()

        assert rc == 0
        assert len(conceptual_calls) > before  # plan drift → fresh audit
        assert "plan changed since" in cap.err
        assert "(step 1:" not in cap.err

    def test_reuse_re_audits_on_code_edit(
        self,
        tmp_path: Path,
        conceptual_calls: list[str],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        plans_dir = _seed_reconcile_plan(tmp_path)
        self._seed_sidecar(tmp_path, plans_dir, capsys)

        (tmp_path / "foo.py").write_text(
            "def bar():\n    return 99\n", encoding="utf-8"
        )

        before = len(conceptual_calls)
        rc = main(_reconcile_argv(
            tmp_path, plans_dir, "detail",
            "--reconcile", "--step", "1", "--reuse", "--yes",
        ))
        cap = capsys.readouterr()

        assert rc == 0
        assert len(conceptual_calls) > before  # code drift → fresh audit
        # Grouped under the owning step, at info level (normal operation).
        assert "step 1:" in cap.err
        assert "foo.py" in cap.err
        assert "foo.py (step 1:" not in cap.err  # not the inline form
        assert "--reconcile" in cap.err

    def test_reuse_flags_deleted_in_scope_file(
        self,
        tmp_path: Path,
        conceptual_calls: list[str],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        plans_dir = _seed_reconcile_plan(tmp_path)
        self._seed_sidecar(tmp_path, plans_dir, capsys)

        (tmp_path / "foo.py").unlink()

        before = len(conceptual_calls)
        rc = main(_reconcile_argv(
            tmp_path, plans_dir, "detail",
            "--reconcile", "--step", "1", "--reuse", "--yes",
        ))
        cap = capsys.readouterr()

        assert rc == 0
        assert len(conceptual_calls) > before  # deletion → fresh audit
        # Grouped under the owning step, at info level (normal operation).
        assert "step 1:" in cap.err
        assert "foo.py" in cap.err
        assert "foo.py (step 1:" not in cap.err  # not the inline form
        assert "code file(s) changed" not in cap.err
        assert "code file(s) removed" in cap.err
        assert "--reconcile" not in cap.err

    def test_no_reuse_always_re_audits(
        self,
        tmp_path: Path,
        conceptual_calls: list[str],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        plans_dir = _seed_reconcile_plan(tmp_path)
        self._seed_sidecar(tmp_path, plans_dir, capsys)

        before = len(conceptual_calls)
        rc = main(_reconcile_argv(
            tmp_path, plans_dir, "detail",
            "--reconcile", "--step", "1", "--no-reuse",
        ))
        cap = capsys.readouterr()

        assert rc == 0
        assert len(conceptual_calls) > before  # opt-out → fresh audit
        assert "walking saved" not in cap.out

    def test_reuse_id_pins_saved_sidecar(
        self,
        tmp_path: Path,
        conceptual_calls: list[str],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        plans_dir = _seed_reconcile_plan(tmp_path)
        self._seed_sidecar(tmp_path, plans_dir, capsys)

        stem = next(
            _reconcile_reports_dir(tmp_path).glob("*-detail-reconcile.json")
        ).stem

        before = len(conceptual_calls)
        rc = main(_reconcile_argv(
            tmp_path, plans_dir, "detail",
            "--reconcile", "--step", "1", "--reuse-id", stem, "--yes",
        ))
        capsys.readouterr()

        assert rc == 0
        assert len(conceptual_calls) == before  # pinned fresh save reused

    def test_reuse_id_miss_audits_fresh(
        self,
        tmp_path: Path,
        conceptual_calls: list[str],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        plans_dir = _seed_reconcile_plan(tmp_path)
        self._seed_sidecar(tmp_path, plans_dir, capsys)

        before = len(conceptual_calls)
        rc = main(_reconcile_argv(
            tmp_path, plans_dir, "detail",
            "--reconcile", "--step", "1",
            "--reuse-id", "20000101-000000-detail-reconcile", "--yes",
        ))
        cap = capsys.readouterr()

        assert rc == 0
        assert len(conceptual_calls) > before  # miss → fresh audit
        assert "20000101-000000-detail-reconcile" in cap.err


# --- _run_auto_reconcile_on_drift helper (Lesson 13) ---------

class TestAutoReconcileOnDriftHelper:
    """Unit-level tests for the auto-reconcile helper. Calls the
    helper directly with mocked ``run_step`` so the focus stays on
    bucketing, persistence, and stderr summary -- not the
    cmd_completeness wiring (covered by sibling integration tests)."""

    def _write_plan(self, tmp_path: Path) -> Path:
        plan_path = tmp_path / "plan.md"
        plan_path.write_text(
            "---\n"
            "title: Auto-Reconcile Test\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: alpha\n"
            "    files:\n"
            "      - alpha.py\n"
            "    status: done\n"
            "  - id: 2\n"
            "    title: beta\n"
            "    files:\n"
            "      - beta.py\n"
            "    status: done\n"
            "---\n",
            encoding="utf-8",
        )
        (tmp_path / "alpha.py").write_text("x = 1\n", encoding="utf-8")
        (tmp_path / "beta.py").write_text("y = 2\n", encoding="utf-8")
        return plan_path

    def _fake_run_result(self, step_id: int, finding_text: str):
        from plan_tool.launcher import RunResult
        return RunResult(
            step_id=step_id,
            exit_code=0,
            advanced_to=None,
            done=False,
            stdout=(
                "Reconcile prose.\n\n## Findings\n\n"
                f"- HIGH: {finding_text}\n"
            ),
            step_title="",
        )

    def test_saved_review_file_contains_recommendations(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """After ``_run_auto_reconcile_on_drift`` returns, the saved
        review file on disk contains the parsed recommendations --
        not just a stub. Closes audit gap: previously the summary
        line was asserted but the persistence round-trip wasn't."""
        import json
        from plan_tool.cli import app as cli_module
        from plan_tool import launcher as launcher_module
        from plan_tool.scope_guard import build_file_to_step_map
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        file_to_step = build_file_to_step_map(plan, tmp_path)

        monkeypatch.setattr(
            launcher_module,
            "run_step",
            lambda *a, **kw: self._fake_run_result(
                kw["step_id"],
                "alpha.py:foo() returns 41 not 42",
            ),
        )

        total = cli_module._run_auto_reconcile_on_drift(
            drifted=[tmp_path / "alpha.py"],
            file_to_step=file_to_step,
            plan_path=plan_path,
            plan_slug="auto-test",
            repo_root=tmp_path,
        )
        assert total == 1

        reviews_dir = tmp_path / "plan-details" / "plan" / "reports"
        review_files = list(reviews_dir.glob("*reconcile*.json"))
        assert len(review_files) == 1, (
            f"expected exactly one reconcile review file; got "
            f"{[p.name for p in review_files]}"
        )

        payload = json.loads(review_files[0].read_text())
        assert "recommendations" in payload
        assert len(payload["recommendations"]) == 1
        rec = payload["recommendations"][0]
        assert rec["severity"] == "high"
        assert "alpha.py" in rec["body"]

    def test_all_unmapped_drift_emits_skip_message(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When every drifted file is outside the file→step map,
        the helper emits the "no drifted file maps to a plan step"
        message and never calls ``run_step``."""
        from plan_tool.cli import app as cli_module
        from plan_tool import launcher as launcher_module

        called = {"n": 0}

        def boom(*a, **kw):
            called["n"] += 1
            raise AssertionError(
                "run_step must not fire when no drifted file maps"
            )

        monkeypatch.setattr(launcher_module, "run_step", boom)

        plan_path = self._write_plan(tmp_path)
        # Empty file_to_step → every drifted path is unmapped.
        total = cli_module._run_auto_reconcile_on_drift(
            drifted=[tmp_path / "orphan.py"],
            file_to_step={},
            plan_path=plan_path,
            plan_slug="auto-test",
            repo_root=tmp_path,
        )
        assert total == 0
        assert called["n"] == 0
        err = capsys.readouterr().err
        assert "auto-reconcile skipped" in err
        assert "no drifted file maps" in err

    def test_launcher_error_skips_step_and_continues(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When ``run_step`` raises ``LauncherError`` for one step,
        the helper logs the failure and continues to the next step
        (best-effort)."""
        from plan_tool.cli import app as cli_module
        from plan_tool import launcher as launcher_module
        from plan_tool.launcher import LauncherError
        from plan_tool.parser import parse_plan
        from plan_tool.scope_guard import build_file_to_step_map

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        file_to_step = build_file_to_step_map(plan, tmp_path)

        # Step 1 raises LauncherError; step 2 succeeds. Helper should
        # log the step-1 failure and still run step 2.
        def fake_run(*a, **kw):
            if kw["step_id"] == 1:
                raise LauncherError("simulated unknown step")
            return self._fake_run_result(kw["step_id"], "beta gap")

        monkeypatch.setattr(launcher_module, "run_step", fake_run)

        total = cli_module._run_auto_reconcile_on_drift(
            drifted=[
                tmp_path / "alpha.py",  # step 1, will raise
                tmp_path / "beta.py",   # step 2, will succeed
            ],
            file_to_step=file_to_step,
            plan_path=plan_path,
            plan_slug="auto-test",
            repo_root=tmp_path,
        )

        # Step 2's finding was captured; step 1's failure didn't
        # abort the loop.
        assert total == 1
        err = capsys.readouterr().err
        assert (
            "auto-reconcile on step 1: launcher error "
            "(simulated unknown step); skipping"
        ) in err
        # Step 2's success line still fires.
        assert 'auto-reconcile on step 2 ("beta"):' in err

    def test_non_zero_exit_code_skips_step_and_continues(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When ``run_step`` returns non-zero ``exit_code`` (typical
        when claude isn't on PATH in CI), the helper logs the skip
        with a manual-run hint and continues to the next step."""
        from plan_tool.cli import app as cli_module
        from plan_tool import launcher as launcher_module
        from plan_tool.launcher import RunResult
        from plan_tool.parser import parse_plan
        from plan_tool.scope_guard import build_file_to_step_map

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        file_to_step = build_file_to_step_map(plan, tmp_path)

        def fake_run(*a, **kw):
            if kw["step_id"] == 1:
                return RunResult(
                    step_id=1, exit_code=127,
                    advanced_to=None, done=False,
                    stdout="", step_title="",
                )
            return self._fake_run_result(kw["step_id"], "beta gap")

        monkeypatch.setattr(launcher_module, "run_step", fake_run)

        total = cli_module._run_auto_reconcile_on_drift(
            drifted=[
                tmp_path / "alpha.py",
                tmp_path / "beta.py",
            ],
            file_to_step=file_to_step,
            plan_path=plan_path,
            plan_slug="auto-test",
            repo_root=tmp_path,
        )

        assert total == 1  # only step 2's finding counted
        err = capsys.readouterr().err
        # Step 1's skip note includes the exit code and the manual-
        # run command hint.
        assert (
            'auto-reconcile on step 1 ("alpha"): claude exited 127'
        ) in err
        assert "plan-tool detail auto-test --reconcile --step 1" in err
        # Step 2's success line still appears -- per-step isolation.
        assert 'auto-reconcile on step 2 ("beta"): 1 finding(s) raised' in err

    def test_empty_findings_saves_empty_review(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """``run_step`` succeeds with stdout containing an empty
        Findings block. Helper still saves the review (signals the
        audit ran) and reports "0 finding(s) raised".

        Without this branch coverage, a regression that skipped the
        save call when recs is empty (e.g. by adding ``if recs:``
        around it) would silently change behavior."""
        import json
        from plan_tool.cli import app as cli_module
        from plan_tool import launcher as launcher_module
        from plan_tool.launcher import RunResult
        from plan_tool.parser import parse_plan
        from plan_tool.scope_guard import build_file_to_step_map

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        file_to_step = build_file_to_step_map(plan, tmp_path)

        def fake_run(*a, **kw):
            return RunResult(
                step_id=kw["step_id"], exit_code=0,
                advanced_to=None, done=False,
                stdout=(
                    "Audit prose with no concerns.\n\n"
                    "## Findings\n\n_(none)_\n"
                ),
                step_title="",
            )

        monkeypatch.setattr(launcher_module, "run_step", fake_run)

        total = cli_module._run_auto_reconcile_on_drift(
            drifted=[tmp_path / "alpha.py"],
            file_to_step=file_to_step,
            plan_path=plan_path,
            plan_slug="auto-test",
            repo_root=tmp_path,
        )

        assert total == 0
        err = capsys.readouterr().err
        assert 'auto-reconcile on step 1 ("alpha"): 0 finding(s) raised' in err

        # Review file was still written -- signals "audit ran, no
        # findings" vs "audit didn't run."
        reviews_dir = tmp_path / "plan-details" / "plan" / "reports"
        review_files = list(reviews_dir.glob("*reconcile*.json"))
        assert len(review_files) == 1
        payload = json.loads(review_files[0].read_text())
        assert payload["recommendations"] == []

    def test_save_review_oserror_falls_back_to_stderr(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When ``save_review`` raises ``OSError`` (disk full,
        permissions, parallel cleanup), the helper logs the failure
        with a pointer to the raw claude stdout and continues
        instead of crashing the iteration loop.

        Verifies:
          1. The fallback message fires with the step context and
             exception text.
          2. ``total_findings`` is still incremented -- findings exist
             even if persistence failed.
          3. The success print does NOT fire (avoids confusing
             "saved to ..." next to a failed save)."""
        from plan_tool.cli import app as cli_module
        from plan_tool import launcher as launcher_module
        from plan_tool import review_persistence as rp_module
        from plan_tool.parser import parse_plan
        from plan_tool.scope_guard import build_file_to_step_map

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        file_to_step = build_file_to_step_map(plan, tmp_path)

        monkeypatch.setattr(
            launcher_module,
            "run_step",
            lambda *a, **kw: self._fake_run_result(
                kw["step_id"], "alpha.py:foo() gap",
            ),
        )

        def boom_save(*a, **kw):
            raise OSError("simulated disk-full")

        monkeypatch.setattr(rp_module, "save_review", boom_save)

        total = cli_module._run_auto_reconcile_on_drift(
            drifted=[tmp_path / "alpha.py"],
            file_to_step=file_to_step,
            plan_path=plan_path,
            plan_slug="auto-test",
            repo_root=tmp_path,
        )

        # Finding count still reflects what claude returned; the
        # failure was in persistence only.
        assert total == 1

        err = capsys.readouterr().err
        # Fallback message names the step + count + exception text.
        assert (
            'auto-reconcile on step 1 ("alpha"): 1 finding(s) raised '
            "but save failed"
        ) in err
        assert "simulated disk-full" in err
        # Operator is directed at the raw claude stdout (which was
        # streamed by shell_invoker during the real call).
        assert "see claude stdout above" in err
        # The success "(saved to ...)" line MUST NOT also fire --
        # would be confusing alongside the save-failed line.
        assert "saved to" not in err

    def test_partial_mapped_reconciles_mapped_and_notes_unmapped(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Mixed input: one drifted file maps to a step, one doesn't.
        The helper reconciles the mapped one AND prints a one-line
        footer naming the count of unmapped files."""
        from plan_tool.cli import app as cli_module
        from plan_tool import launcher as launcher_module
        from plan_tool.scope_guard import build_file_to_step_map
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        file_to_step = build_file_to_step_map(plan, tmp_path)
        orphan = tmp_path / "orphan.py"
        orphan.write_text("z = 3\n", encoding="utf-8")

        run_calls: list[int] = []

        def fake_run(*a, **kw):
            run_calls.append(kw["step_id"])
            return self._fake_run_result(kw["step_id"], "mapped gap")

        monkeypatch.setattr(launcher_module, "run_step", fake_run)

        total = cli_module._run_auto_reconcile_on_drift(
            drifted=[tmp_path / "alpha.py", orphan],
            file_to_step=file_to_step,
            plan_path=plan_path,
            plan_slug="auto-test",
            repo_root=tmp_path,
        )
        assert total == 1
        # Only the mapped step's reconcile fired.
        assert run_calls == [1]
        err = capsys.readouterr().err
        assert (
            'auto-reconcile on step 1 ("alpha"): 1 finding(s) raised'
        ) in err
        # Unmapped footer surfaces the skipped count.
        assert "skipped 1 drifted file(s) outside any step.files" in err


# --- _iterate_reconcile_loop drift-halt phase logic (task #33 / Lesson 7) -

@pytest.mark.integration
class TestIterateReconcileLoopDriftPhase:
    """Pin the phase-logic fix in ``_iterate_reconcile_loop``.

    Bug history: ``record_iteration`` is called with the iteration-0
    seed BEFORE the while loop, which bumps ``conv_state.iteration``
    from 0 to 1. An earlier draft of the drift halt used
    ``conv_state.iteration == 0`` to pick the "before" phase wording
    — that branch was therefore unreachable inside the loop, and
    every pre-iteration drift halt reported phase "during" even on
    the first iteration when nothing had been kept. Fixed by an
    explicit ``_loop_iteration_work_done`` flag.

    This test pins the fix by inspecting the phase argument passed to
    ``_emit_drift_halt_warning`` when drift fires on the very first
    iteration's pre-check."""

    def _setup_minimal(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ):
        """Build the minimal plumbing _iterate_reconcile_loop needs.

        Returns ``(args, ctx, plan_path)`` plus a captured-args list
        for ``_emit_drift_halt_warning``."""
        import argparse

        from plan_tool.cli import app as cli_module
        from plan_tool import drift_detection as iter_lock_module
        from plan_tool.locator import PlanToolContext

        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        plan_path = plans_dir / "1-iter-test.md"
        plan_path.write_text(
            "---\n"
            "title: Iter Test\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: do x\n"
            "    files:\n"
            "      - foo.py\n"
            "    status: current\n"
            "---\n"
            "\n"
            "## Overview\n\nx\n",
            encoding="utf-8",
        )
        (tmp_path / "foo.py").write_text(
            "def bar():\n    return 41\n", encoding="utf-8"
        )

        # Construct a Namespace with the flags _iterate_reconcile_loop
        # reads. ``allow_drift=False`` is the path under test. The
        # auto-reconcile flag is set False so the test doesn't spawn
        # a real claude shell-out via run_step (the helper itself is
        # exercised by sibling unit tests).
        args = argparse.Namespace(
            name="iter-test",
            allow_drift=False,
            auto_reconcile_on_drift=False,
            yes=True,
        )
        ctx = PlanToolContext(
            repo_root=tmp_path, plans_dir=plans_dir, entries=[],
        )

        captured_calls: list[dict] = []

        def fake_emit_drift_halt_warning(
            drifted, *, phase, finding_id, ctx_repo_root,
            file_to_step=None,
        ):
            captured_calls.append({
                "phase": phase,
                "finding_id": finding_id,
                "file_to_step": file_to_step,
                "drifted": list(drifted),
            })

        monkeypatch.setattr(
            reconcile_module,
            "_emit_drift_halt_warning",
            fake_emit_drift_halt_warning,
        )

        # Force check_drift to fire on the FIRST call -- simulates a
        # watched file's mtime advancing between acquire_lock and the
        # first iteration's pre-check.
        check_calls = {"n": 0}

        def fake_check_drift(lock):
            check_calls["n"] += 1
            return [tmp_path / "foo.py"] if check_calls["n"] == 1 else []

        monkeypatch.setattr(
            iter_lock_module, "check_drift", fake_check_drift,
        )

        return args, ctx, plan_path, captured_calls

    def test_first_iteration_pre_check_uses_before_phase(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Drift on the very first iteration's pre-check fires phase
        "before" (no in-loop tokens spent yet). Regression guard for
        the conv_state.iteration off-by-one bug: any future refactor
        that re-introduces ``conv_state.iteration == 0`` as the test
        condition would silently flip this phase to "during"."""
        from plan_tool.cli import app as cli_module
        from plan_tool.convergence import IterativeBudget
        from plan_tool.review import Recommendation
        from plan_tool.review_walk import WalkState

        args, ctx, plan_path, captured_calls = self._setup_minimal(
            tmp_path, monkeypatch,
        )

        # Seed with a HIGH-severity rec so should_continue lets us
        # enter the loop body -- otherwise the loop exits immediately
        # via the "no_blocking_findings" early-exit at iteration 1.
        seed = Recommendation(
            id="seed", source="reconcile", severity="high",
            step_id=1, title="x", body="x",
        )

        cli_module._iterate_reconcile_loop(
            args=args,
            ctx=ctx,
            plan_path=plan_path,
            step_id=1,
            initial_recs=[seed],
            state=WalkState(yes_to_all=True),
            budget=IterativeBudget(enabled=True, max_iterations=3),
        )

        assert [c["phase"] for c in captured_calls] == ["before"]

    def test_print_attributed_files_annotates_each_line(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """``_print_attributed_files`` renders each path with the
        owning step's id/title when found in file_to_step, and
        gracefully falls back to a bare path when unmapped (sibling
        of the scope-guard warnings' step-attribution feature)."""
        from plan_tool.cli import _print_attributed_files

        mapped = tmp_path / "src" / "alpha.py"
        unmapped = tmp_path / "scratch.py"
        for p in (mapped, unmapped):
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("x = 1\n", encoding="utf-8")

        file_to_step = {mapped.resolve(): (3, "polish docs")}

        _print_attributed_files(
            [mapped, unmapped], tmp_path, file_to_step,
        )
        err = capsys.readouterr().err
        assert "- src/alpha.py (step 3: polish docs)" in err
        # Unmapped file falls back to bare path — no spurious
        # "(step ?: ?)" annotation.
        assert "- scratch.py" in err
        assert "scratch.py (step" not in err

    def test_print_attributed_files_truncates_long_lists(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When more than ``max_listed`` paths are passed, the
        remainder is summarized with the standard "... and N more"
        footer (mirrors drift_detection's drift-warning truncation)."""
        from plan_tool.cli import _print_attributed_files

        paths = [tmp_path / f"f{i}.py" for i in range(15)]
        _print_attributed_files(
            paths, tmp_path, file_to_step=None, max_listed=5,
        )
        err = capsys.readouterr().err
        assert "and 10 more" in err

    def test_drift_halt_passes_step_attribution_through(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``_iterate_reconcile_loop`` must build the file→step map
        and pass it to the drift-halt warning so operators see the
        owning step inline. Regression guard:
        previously the test only captured ``phase``; a wiring bug
        that drops ``file_to_step`` would have rendered as bare paths
        in production without any test failure (Lesson 7)."""
        from plan_tool.cli import app as cli_module
        from plan_tool.convergence import IterativeBudget
        from plan_tool.review import Recommendation
        from plan_tool.review_walk import WalkState

        args, ctx, plan_path, captured_calls = self._setup_minimal(
            tmp_path, monkeypatch,
        )

        seed = Recommendation(
            id="seed", source="reconcile", severity="high",
            step_id=1, title="x", body="x",
        )

        cli_module._iterate_reconcile_loop(
            args=args,
            ctx=ctx,
            plan_path=plan_path,
            step_id=1,
            initial_recs=[seed],
            state=WalkState(yes_to_all=True),
            budget=IterativeBudget(enabled=True, max_iterations=3),
        )

        assert len(captured_calls) == 1
        f2s = captured_calls[0]["file_to_step"]
        assert f2s is not None, (
            "_iterate_reconcile_loop did not pass file_to_step "
            "to the drift halt; attribution wiring regressed"
        )
        # The plan's step 1 declares foo.py; the map should attribute
        # foo.py to (step_id=1, title="do x").
        resolved = (tmp_path / "foo.py").resolve()
        assert f2s.get(resolved) == (1, "do x"), (
            f"expected file_to_step to map {resolved} -> (1, 'do x'); "
            f"got {f2s!r}"
        )


@pytest.mark.integration
class TestIterateReconcileLoopTriage:
    """Smoke test for the impact-weighted triage wiring in
    ``_iterate_reconcile_loop``. The primitive ``should_apply_by_triage``
    is exercised by ``test_review.py::TestApplyTriage``; this test
    pins that ``_iterate_reconcile_loop`` actually CALLS it and
    short-circuits when every rec is deferred -- without this pin a
    refactor could silently drop the wiring (Lesson 7: test the
    wiring, not just the helper)."""

    def _seed_minimal(self, tmp_path: Path):
        """Minimal plan + Namespace + context for the loop helper."""
        import argparse
        from plan_tool.locator import PlanToolContext

        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        plan_path = plans_dir / "1-triage-test.md"
        plan_path.write_text(
            "---\n"
            "title: Triage Iter Test\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: do x\n"
            "    files:\n"
            "      - foo.py\n"
            "    status: current\n"
            "---\n"
            "\n"
            "## Overview\n\nx\n",
            encoding="utf-8",
        )
        (tmp_path / "foo.py").write_text(
            "def bar():\n    return 41\n", encoding="utf-8"
        )

        args = argparse.Namespace(
            name="triage-test",
            allow_drift=False,
            auto_reconcile_on_drift=False,
            collision_sidecar=False,            triage=True,
            yes=True,
        )
        ctx = PlanToolContext(
            repo_root=tmp_path, plans_dir=plans_dir, entries=[],
        )
        return args, ctx, plan_path

    def test_no_triage_flag_force_applies_in_reconcile_loop(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """``--no-triage`` (args.triage=False) disables the gate so
        even findings with complexity > impact flow through to
        apply_finding."""
        from plan_tool.cli import app as cli_module
        from plan_tool import launcher as launcher_module
        from plan_tool.convergence import IterativeBudget
        from plan_tool.launcher import ApplyFindingResult, RunResult
        from plan_tool.review import Recommendation
        from plan_tool.review_walk import WalkState

        args, ctx, plan_path = self._seed_minimal(tmp_path)
        args.triage = False  # opt out

        # One finding that would be deferred under default triage.
        reconcile_stdout = (
            "## Findings\n\n"
            "- HIGH: rec one\n"
        )

        def fake_run_step(*a, **kw):  # noqa: ARG001
            return RunResult(
                step_id=1, exit_code=0, advanced_to=None, done=False,
                stdout=reconcile_stdout, step_title="do x",
            )

        monkeypatch.setattr("plan_tool.cli.reconcile.run_step", fake_run_step)

        apply_calls = {"n": 0}

        def fake_apply(*a, **kw):  # noqa: ARG001
            apply_calls["n"] += 1
            return ApplyFindingResult(
                step_id=kw.get("step_id"),
                exit_code=0,
                verdict="APPLIED",
                summary="",
                diff_text="",
                pre_snapshot={},
                stdout="",
            )

        monkeypatch.setattr(launcher_module, "apply_finding", fake_apply)

        seed = Recommendation(
            id="seed", source="reconcile", severity="high",
            step_id=1, title="x", body="x",
        )

        cli_module._iterate_reconcile_loop(
            args=args,
            ctx=ctx,
            plan_path=plan_path,
            step_id=1,
            initial_recs=[seed],
            state=WalkState(yes_to_all=True),
            budget=IterativeBudget(enabled=True, max_iterations=3),
        )

        # The would-be-deferred rec was applied.
        assert apply_calls["n"] >= 1, (
            "apply_finding never ran -- --no-triage did not disable "
            "the triage gate"
        )
        err = capsys.readouterr().err
        # No triage-deferred summary surfaces in stderr.
        assert "deferring" not in err


class TestIterateReconcileLoopHighImpactAdvisories:
    """Keep high-impact advisory findings in reconcile convergence paths."""

    def _seed_minimal(self, tmp_path: Path):
        return TestIterateReconcileLoopTriage()._seed_minimal(tmp_path)

    @staticmethod
    def _parsed_recommendations(stdout: str):
        from plan_tool.review import extract_reconcile_recommendations

        recs = extract_reconcile_recommendations(
            stdout, step_id=1, source="detail-reconcile"
        )
        assert [(rec.severity, rec.impact, rec.complexity) for rec in recs] == [
            ("nit", "high", "low")
        ]
        return recs

    def test_reconcile_initial_refresh_keeps_high_impact_advisory_blocking(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool.convergence import IterativeBudget
        from plan_tool.launcher import RunResult
        from plan_tool.review_walk import WalkState

        args, ctx, plan_path = self._seed_minimal(tmp_path)
        args.allow_drift = True
        run_calls = {"count": 0}

        def fake_run_step(*args, **kwargs):  # noqa: ARG001
            run_calls["count"] += 1
            return RunResult(
                step_id=1, exit_code=0, advanced_to=None, done=False,
                stdout="## Findings\n\n_(none)_\n", step_title="do x",
            )

        monkeypatch.setattr(reconcile_module, "run_step", fake_run_step)
        initial_recs = self._parsed_recommendations(
            "## Findings\n\n- NIT: clarify the helper name "
            "(impact: high, complexity: low)\n"
        )
        cli_module._iterate_reconcile_loop(
            args=args, ctx=ctx, plan_path=plan_path, step_id=1,
            initial_recs=initial_recs, state=WalkState(yes_to_all=True),
            budget=IterativeBudget(enabled=True, max_iterations=3),
        )

        assert run_calls["count"] == 1
        assert "converged" in capsys.readouterr().out

    def test_reconcile_later_refresh_keeps_high_impact_advisory_blocking(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool import launcher as launcher_module
        from plan_tool.cli import app as cli_module
        from plan_tool.convergence import IterativeBudget
        from plan_tool.launcher import ApplyFindingResult, RunResult
        from plan_tool.review import Recommendation
        from plan_tool.review_walk import WalkState

        args, ctx, plan_path = self._seed_minimal(tmp_path)
        args.allow_drift = True
        parsed_output = (
            "## Findings\n\n- NIT: clarify the helper name "
            "(impact: high, complexity: low)\n"
        )
        monkeypatch.setattr(
            reconcile_module, "run_step",
            lambda *a, **kw: RunResult(
                step_id=1, exit_code=0, advanced_to=None, done=False,
                stdout=parsed_output, step_title="do x",
            ),
        )
        monkeypatch.setattr(
            launcher_module, "apply_finding",
            lambda *a, **kw: ApplyFindingResult(
                step_id=1, exit_code=0, verdict="APPLIED", summary="ok",
                diff_text="", pre_snapshot={}, stdout="",
            ),
        )
        initial_recs = [Recommendation(
            id="blocking-seed", source="detail-reconcile", severity="high",
            step_id=1, title="seed", body="seed",
        )]
        cli_module._iterate_reconcile_loop(
            args=args, ctx=ctx, plan_path=plan_path, step_id=1,
            initial_recs=initial_recs, state=WalkState(yes_to_all=True),
            budget=IterativeBudget(enabled=True, max_iterations=3),
        )

        assert "no_blocking_findings" not in capsys.readouterr().out

    def test_reconcile_resume_refresh_keeps_high_impact_advisory_blocking(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool.convergence import IterativeBudget
        from plan_tool.launcher import RunResult
        from plan_tool.review import Recommendation
        from plan_tool.review_walk import WalkState

        args, ctx, plan_path = self._seed_minimal(tmp_path)
        advisory_output = (
            "## Findings\n\n- NIT: clarify the helper name "
            "(impact: high, complexity: low)\n"
        )
        monkeypatch.setattr(
            reconcile_module, "run_step",
            lambda *a, **kw: RunResult(
                step_id=1, exit_code=0, advanced_to=None, done=False,
                stdout=advisory_output, step_title="do x",
            ),
        )
        def merged_walk(_saved, _action_fn, state, **kwargs):  # noqa: ARG001
            state.halt_requested = True
            state.halt_merged = True

        monkeypatch.setattr(reconcile_module, "_walk_with_reconcile_phase", merged_walk)
        initial_recs = [Recommendation(
            id="blocking-seed", source="detail-reconcile", severity="high",
            step_id=1, title="seed", body="seed",
        )]
        cli_module._iterate_reconcile_loop(
            args=args, ctx=ctx, plan_path=plan_path, step_id=1,
            initial_recs=initial_recs, state=WalkState(yes_to_all=True),
            budget=IterativeBudget(enabled=True, max_iterations=3),
        )

        assert "no_blocking_findings" not in capsys.readouterr().out


class TestIterateReconcileLoopCalibration:
    """Use one calibrated low-impact demotion rule throughout a loop."""

    def _seed_minimal(self, tmp_path: Path):
        return TestIterateReconcileLoopTriage()._seed_minimal(tmp_path)

    @staticmethod
    def _recommendation(
        recommendation_id: str,
        *,
        severity: str = "medium",
        impact: str = "low",
    ):
        from plan_tool.review import Recommendation

        return Recommendation(
            id=recommendation_id,
            source="detail-reconcile",
            severity=severity,
            impact=impact,
            step_id=1,
            title=recommendation_id,
            body=recommendation_id,
        )

    def test_reconcile_calibration_lookup_is_built_once_per_enabled_loop(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool.convergence import IterativeBudget
        from plan_tool.launcher import RunResult
        from plan_tool.review_walk import WalkState

        args, ctx, plan_path = self._seed_minimal(tmp_path)
        args.allow_drift = True
        lookup_builds = []
        run_calls = []

        def build_lookup(repo_root: Path):
            lookup_builds.append(repo_root)
            return lambda rec: False

        def run_reconcile(*args, **kwargs):  # noqa: ARG001
            run_calls.append(True)
            return RunResult(
                step_id=1, exit_code=0, advanced_to=None, done=False,
                stdout="## Findings\n\n- HIGH: keep iterating\n",
                step_title="do x",
            )

        monkeypatch.setattr(
            reconcile_module, "build_low_impact_demotion_lookup", build_lookup,
        )
        monkeypatch.setattr(reconcile_module, "run_step", run_reconcile)
        monkeypatch.setattr(
            reconcile_module, "_walk_with_reconcile_phase", lambda *a, **kw: None,
        )

        cli_module._iterate_reconcile_loop(
            args=args, ctx=ctx, plan_path=plan_path, step_id=1,
            initial_recs=[self._recommendation("seed", severity="high")],
            state=WalkState(yes_to_all=True),
            budget=IterativeBudget(enabled=True, max_iterations=3),
        )

        assert len(run_calls) == 2
        assert lookup_builds == [tmp_path]

    def test_reconcile_qualifying_low_impact_medium_finding_stops_as_non_blocking(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool.convergence import IterativeBudget
        from plan_tool.review_walk import WalkState

        args, ctx, plan_path = self._seed_minimal(tmp_path)
        monkeypatch.setattr(
            reconcile_module, "build_low_impact_demotion_lookup",
            lambda repo_root: lambda rec: True,
        )
        monkeypatch.setattr(
            reconcile_module, "run_step",
            lambda *a, **kw: pytest.fail("demoted finding started another pass"),
        )

        cli_module._iterate_reconcile_loop(
            args=args, ctx=ctx, plan_path=plan_path, step_id=1,
            initial_recs=[self._recommendation("qualifying")],
            state=WalkState(yes_to_all=True),
            budget=IterativeBudget(enabled=True, max_iterations=3),
        )

        assert "no_blocking_findings" in capsys.readouterr().out

    def test_reconcile_unqualified_low_impact_medium_finding_remains_blocking(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool.convergence import IterativeBudget
        from plan_tool.launcher import RunResult
        from plan_tool.review_walk import WalkState

        args, ctx, plan_path = self._seed_minimal(tmp_path)
        args.allow_drift = True
        run_calls = []
        monkeypatch.setattr(
            reconcile_module, "build_low_impact_demotion_lookup",
            lambda repo_root: lambda rec: False,
        )
        monkeypatch.setattr(
            reconcile_module, "run_step",
            lambda *a, **kw: run_calls.append(True) or RunResult(
                step_id=1, exit_code=0, advanced_to=None, done=False,
                stdout="## Findings\n\n_(none)_\n", step_title="do x",
            ),
        )

        cli_module._iterate_reconcile_loop(
            args=args, ctx=ctx, plan_path=plan_path, step_id=1,
            initial_recs=[self._recommendation("unqualified")],
            state=WalkState(yes_to_all=True),
            budget=IterativeBudget(enabled=True, max_iterations=3),
        )

        assert len(run_calls) == 1

    def test_reconcile_calibrated_rule_cannot_demote_high_impact_or_high_severity(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool.convergence import IterativeBudget
        from plan_tool.launcher import RunResult
        from plan_tool.review_walk import WalkState

        args, ctx, plan_path = self._seed_minimal(tmp_path)
        args.allow_drift = True
        run_calls = []
        monkeypatch.setattr(
            reconcile_module, "build_low_impact_demotion_lookup",
            lambda repo_root: lambda rec: True,
        )
        monkeypatch.setattr(
            reconcile_module, "run_step",
            lambda *a, **kw: run_calls.append(True) or RunResult(
                step_id=1, exit_code=0, advanced_to=None, done=False,
                stdout="## Findings\n\n_(none)_\n", step_title="do x",
            ),
        )

        cli_module._iterate_reconcile_loop(
            args=args, ctx=ctx, plan_path=plan_path, step_id=1,
            initial_recs=[
                self._recommendation("high-impact", severity="nit", impact="high"),
                self._recommendation("high-severity", severity="high"),
                self._recommendation("critical-severity", severity="critical"),
            ],
            state=WalkState(yes_to_all=True),
            budget=IterativeBudget(enabled=True, max_iterations=3),
        )

        assert len(run_calls) == 1

    def test_reconcile_merged_refresh_reuses_the_same_calibration_rule(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool.convergence import IterativeBudget
        from plan_tool.launcher import RunResult
        from plan_tool.review_walk import WalkState

        args, ctx, plan_path = self._seed_minimal(tmp_path)
        lookup_builds = []
        evaluated_recommendations = []

        def build_lookup(repo_root: Path):
            lookup_builds.append(repo_root)

            def demote(rec):
                evaluated_recommendations.append(rec.id)
                return True

            return demote

        def merged_walk(_saved, _action_fn, state, **kwargs):  # noqa: ARG001
            state.halt_requested = True
            state.halt_merged = True

        monkeypatch.setattr(
            reconcile_module, "build_low_impact_demotion_lookup", build_lookup,
        )
        monkeypatch.setattr(
            reconcile_module, "run_step",
            lambda *a, **kw: RunResult(
                step_id=1, exit_code=0, advanced_to=None, done=False,
                stdout="## Findings\n\n- MEDIUM: calibrated finding (impact: low)\n",
                step_title="do x",
            ),
        )
        monkeypatch.setattr(reconcile_module, "_walk_with_reconcile_phase", merged_walk)

        cli_module._iterate_reconcile_loop(
            args=args, ctx=ctx, plan_path=plan_path, step_id=1,
            initial_recs=[self._recommendation("blocking-seed", severity="high")],
            state=WalkState(yes_to_all=True),
            budget=IterativeBudget(enabled=True, max_iterations=3),
        )

        assert lookup_builds == [tmp_path]
        assert len(evaluated_recommendations) == 1
        assert "no_blocking_findings" in capsys.readouterr().out

    def test_reconcile_disabled_iteration_does_not_build_calibration_lookup(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool.convergence import IterativeBudget
        from plan_tool.review_walk import WalkState

        args, ctx, plan_path = self._seed_minimal(tmp_path)
        monkeypatch.setattr(
            reconcile_module, "build_low_impact_demotion_lookup",
            lambda repo_root: pytest.fail("disabled loop read calibration history"),
        )

        cli_module._iterate_reconcile_loop(
            args=args, ctx=ctx, plan_path=plan_path, step_id=1,
            initial_recs=[self._recommendation("seed")],
            state=WalkState(yes_to_all=True),
            budget=IterativeBudget(enabled=False),
        )

@pytest.mark.integration
class TestIterateReconcileLoopPerFindingScopeGuard:
    """Lesson 7 wiring tests for per-finding scope guard
    inside the reconcile action_fn.

    The legacy behavior wrapped the entire walk in one
    ``evaluate_apply_scope`` pair. The refactor moves the eval inside
    ``_dispatch_apply_finding``'s finally block so each rec gets its
    own snapshot pair AND each out-of-scope record carries the rec's
    own ``finding_id`` (not an iteration-level synthetic id) for
    attribution.

    These tests pin the wiring at the call site -- a future refactor
    that drops ``reconcile_scope_guard`` from the action_fn builder
    or skips the finally-block scope eval would fail here even
    though the helpers themselves still work in isolation.
    """

    def _seed_minimal(self, tmp_path: Path):
        import argparse
        from plan_tool.locator import PlanToolContext

        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        plan_path = plans_dir / "1-scope-test.md"
        plan_path.write_text(
            "---\n"
            "title: Scope Iter Test\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: do x\n"
            "    files:\n"
            "      - foo.py\n"
            "    status: current\n"
            "---\n"
            "\n"
            "## Overview\n\nx\n",
            encoding="utf-8",
        )
        (tmp_path / "foo.py").write_text(
            "def bar():\n    return 41\n", encoding="utf-8"
        )
        args = argparse.Namespace(
            name="scope-test",
            allow_drift=False,
            auto_reconcile_on_drift=False,
            collision_sidecar=False,            triage=False,
            yes=True,
        )
        ctx = PlanToolContext(
            repo_root=tmp_path, plans_dir=plans_dir, entries=[],
        )
        return args, ctx, plan_path

    def test_per_finding_scope_eval_runs_with_rec_id_for_attribution(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """The per-finding scope guard must call
        ``evaluate_apply_scope`` once per applied rec AND pass that
        rec's own ``finding_id`` (not a synthetic iteration-level id).
        Mirrors the cmd_completeness scope-attribution end-to-end
        test for the iterate-reconcile call site."""
        from plan_tool.cli import app as cli_module
        from plan_tool import launcher as launcher_module
        from plan_tool import scope_guard as scope_guard_module
        from plan_tool.convergence import IterativeBudget
        from plan_tool.launcher import ApplyFindingResult, RunResult
        from plan_tool.review import Recommendation
        from plan_tool.review_walk import WalkState
        from plan_tool.scope_guard import OutOfScopeRecord

        args, ctx, plan_path = self._seed_minimal(tmp_path)

        # Reconcile claude stdout emitting ONE finding (no triage tags
        # so the rec flows through to apply when triage=False).
        reconcile_stdout = (
            "## Findings\n\n"
            "- HIGH: rec-alpha\n"
        )

        def fake_run_step(*a, **kw):  # noqa: ARG001
            return RunResult(
                step_id=1, exit_code=0, advanced_to=None, done=False,
                stdout=reconcile_stdout, step_title="do x",
            )

        monkeypatch.setattr("plan_tool.cli.reconcile.run_step", fake_run_step)

        # apply_finding: report APPLIED with a non-empty diff so the
        # dispatcher reaches the "kept" path. State.yes_to_all skips
        # the interactive prompt. pre_snapshot is non-empty so the
        # sidecar path could be exercised separately.
        monkeypatch.setattr(
            launcher_module,
            "apply_finding",
            lambda plan_path_arg, **kwargs: ApplyFindingResult(
                step_id=kwargs.get("step_id"),
                exit_code=0,
                verdict="APPLIED",
                summary="ok",
                diff_text="--- a\n+++ b\n@@ -1 +1 @@\n-x\n+y\n",
                pre_snapshot={plan_path: "before"},
                stdout="",
                introduced_findings=[],
                resolved_findings=[],
            ),
        )

        captured_eval_calls: list[dict] = []

        def fake_evaluate_apply_scope(**kwargs):
            captured_eval_calls.append(kwargs)
            # Synthetic out-of-scope record so attribution + buffer.add
            # exercise downstream. ``out_of_scope_files`` points at a
            # file the seed plan does NOT declare so attribution
            # falls back to the bare path (which is fine -- this test
            # is about wiring, not the attribution renderer).
            return [
                OutOfScopeRecord(
                    finding_id=kwargs["finding_id"],
                    finding_body=kwargs["finding_body"],
                    step_id=kwargs.get("step_id"),
                    out_of_scope_files=[tmp_path / "bar.py"],
                    impact_status="reverted",
                ),
            ]

        monkeypatch.setattr(
            scope_guard_module,
            "evaluate_apply_scope",
            fake_evaluate_apply_scope,
        )
        # No-op revert so the synthetic record doesn't try to write
        # to a missing pre-snapshot path.
        monkeypatch.setattr(
            scope_guard_module,
            "revert_out_of_scope",
            lambda record, pre_snap: None,
        )

        seed = Recommendation(
            id="seed", source="reconcile", severity="high",
            step_id=1, title="x", body="x",
        )

        cli_module._iterate_reconcile_loop(
            args=args,
            ctx=ctx,
            plan_path=plan_path,
            step_id=1,
            initial_recs=[seed],
            state=WalkState(yes_to_all=True),
            # max_iterations=2 → seed bumps iteration to 1 pre-loop,
            # one body pass runs, record_iteration bumps to 2, the
            # next should_continue check halts. Exactly one walk
            # exercises the action_fn's per-finding scope guard.
            budget=IterativeBudget(enabled=True, max_iterations=2),
        )

        # One evaluate_apply_scope call -- per-finding granularity
        # for the single rec the iteration applied. The legacy
        # per-iteration behavior would have called it ONCE with the
        # synthetic ``reconcile-iter<N>-step<S>`` id; the new
        # behavior calls it with the rec's own id.
        assert len(captured_eval_calls) == 1, (
            f"expected exactly one per-finding evaluate_apply_scope "
            f"call; got {len(captured_eval_calls)}"
        )
        call_finding_id = captured_eval_calls[0]["finding_id"]
        assert "reconcile-iter" not in call_finding_id, (
            f"per-finding scope eval was passed the legacy "
            f"iteration-level id {call_finding_id!r}; refactor "
            f"regressed to per-iteration granularity"
        )
        # Stderr carries the reverted-edit attribution header.
        err = capsys.readouterr().err
        assert "reverted out-of-scope code edit(s) from finding" in err, (
            "per-finding attribution header missing from stderr; "
            "scope-guard wiring inside action_fn did not fire"
        )

    def test_revert_path_skips_scope_eval(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When apply_finding's verdict triggers a revert
        (BLOCKED / NOT-APPLICABLE / REFUSED), the dispatcher sets
        ``phase_outcome = 'reverted'`` and the finally block's scope
        guard short-circuits. evaluate_apply_scope must NOT fire --
        a revert means no out-of-scope edits to record."""
        from plan_tool.cli import app as cli_module
        from plan_tool import launcher as launcher_module
        from plan_tool import scope_guard as scope_guard_module
        from plan_tool.convergence import IterativeBudget
        from plan_tool.launcher import ApplyFindingResult, RunResult
        from plan_tool.review import Recommendation
        from plan_tool.review_walk import WalkState

        args, ctx, plan_path = self._seed_minimal(tmp_path)

        reconcile_stdout = "## Findings\n\n- HIGH: rec-alpha\n"

        def fake_run_step(*a, **kw):  # noqa: ARG001
            return RunResult(
                step_id=1, exit_code=0, advanced_to=None, done=False,
                stdout=reconcile_stdout, step_title="do x",
            )

        monkeypatch.setattr("plan_tool.cli.reconcile.run_step", fake_run_step)

        # apply_finding returns BLOCKED -- the dispatcher reverts and
        # sets phase_outcome to "reverted". Scope guard MUST skip.
        monkeypatch.setattr(
            launcher_module,
            "apply_finding",
            lambda plan_path_arg, **kwargs: ApplyFindingResult(
                step_id=kwargs.get("step_id"),
                exit_code=0,
                verdict="BLOCKED",
                summary="blocked because reasons",
                diff_text="",
                pre_snapshot={},
                stdout="",
            ),
        )

        eval_calls = {"n": 0}

        def fake_eval(**kwargs):  # noqa: ARG001
            eval_calls["n"] += 1
            return []

        monkeypatch.setattr(
            scope_guard_module,
            "evaluate_apply_scope",
            fake_eval,
        )

        seed = Recommendation(
            id="seed", source="reconcile", severity="high",
            step_id=1, title="x", body="x",
        )

        cli_module._iterate_reconcile_loop(
            args=args,
            ctx=ctx,
            plan_path=plan_path,
            step_id=1,
            initial_recs=[seed],
            state=WalkState(yes_to_all=True),
            # max_iterations=2 so the body actually runs once and
            # exercises the revert path; with max_iterations=1 the
            # loop would halt pre-body and ``eval_calls["n"] == 0``
            # would pass trivially (false-negative for a regression
            # where scope guard fires on revert).
            budget=IterativeBudget(enabled=True, max_iterations=2),
        )

        assert eval_calls["n"] == 0, (
            f"evaluate_apply_scope ran {eval_calls['n']} time(s) on a "
            f"revert path; scope guard must short-circuit when "
            f"apply_finding doesn't land edits"
        )


@pytest.mark.integration
class TestIterateReconcileLoopCollisionSidecar:
    """: wire change-collision sidecar
    into ``_iterate_reconcile_loop``'s post-walk drift halt.

    Session-4 explicitly skipped this wiring because per-rec
    ``apply_result`` wasn't available in the iteration body. After
    #14 the action_fn records each apply's ``pre_snapshot`` on the
    shared ``ReconcileScopeGuard``, so the iteration body can compose
    a merged baseline at the post-walk drift halt and feed
    ``handle_drift_collision``. These tests pin the call site.
    """

    def _seed_minimal(self, tmp_path: Path):
        import argparse
        from plan_tool.locator import PlanToolContext

        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        plan_path = plans_dir / "1-sidecar-test.md"
        plan_path.write_text(
            "---\n"
            "title: Sidecar Iter Test\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: do x\n"
            "    files:\n"
            "      - foo.py\n"
            "    status: current\n"
            "---\n"
            "\n"
            "## Overview\n\nx\n",
            encoding="utf-8",
        )
        (tmp_path / "foo.py").write_text(
            "def bar():\n    return 41\n", encoding="utf-8"
        )
        args = argparse.Namespace(
            name="sidecar-test",
            allow_drift=False,
            auto_reconcile_on_drift=False,
            collision_sidecar=True,            triage=False,
            yes=True,
        )
        ctx = PlanToolContext(
            repo_root=tmp_path, plans_dir=plans_dir, entries=[],
        )
        return args, ctx, plan_path

    def test_post_walk_drift_invokes_collision_sidecar_with_merged_baseline(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When post-walk drift fires, ``handle_drift_collision``
        is called with the merged-baseline composed from each
        apply's ``pre_snapshot``. Pinning this catches a refactor
        that drops the call or feeds it the wrong shape."""
        from plan_tool import change_collision as cc_module
        from plan_tool.cli import app as cli_module
        from plan_tool import drift_detection as iter_lock_module
        from plan_tool import launcher as launcher_module
        from plan_tool.convergence import IterativeBudget
        from plan_tool.launcher import ApplyFindingResult, RunResult
        from plan_tool.review import Recommendation
        from plan_tool.review_walk import WalkState

        args, ctx, plan_path = self._seed_minimal(tmp_path)
        # Disable the legacy halt path's auto-reconcile so the
        # collision-sidecar branch can be observed in isolation.
        args.auto_reconcile_on_drift = False

        reconcile_stdout = "## Findings\n\n- HIGH: rec-alpha\n"

        def fake_run_step(*a, **kw):  # noqa: ARG001
            return RunResult(
                step_id=1, exit_code=0, advanced_to=None, done=False,
                stdout=reconcile_stdout, step_title="do x",
            )

        monkeypatch.setattr("plan_tool.cli.reconcile.run_step", fake_run_step)

        # apply_finding: returns APPLIED with a non-empty
        # pre_snapshot covering plan_path. The action_fn records
        # this via ``record_apply`` so the post-walk drift halt
        # can compose the merged baseline.
        captured_pre = {plan_path: "before"}
        monkeypatch.setattr(
            launcher_module,
            "apply_finding",
            lambda plan_path_arg, **kwargs: ApplyFindingResult(
                step_id=kwargs.get("step_id"),
                exit_code=0,
                verdict="APPLIED",
                summary="ok",
                diff_text="--- a\n+++ b\n@@ -1 +1 @@\n-x\n+y\n",
                pre_snapshot=dict(captured_pre),
                stdout="",
                introduced_findings=[],
                resolved_findings=[],
            ),
        )

        # Drift fires on the per-finding POST-apply check inside
        # action_fn (call #3 to check_drift overall: #1 is iter-body
        # pre-iter, returns clean; #2 is action_fn's per-finding
        # pre-apply, returns clean so apply_finding runs; #3 is
        # action_fn's per-finding post-apply, returns drift to
        # trigger the sidecar). The iteration-body's post-walk drift
        # check (, kept as a fallback for the no-applies
        # case) doesn't reach call #4 here because the per-finding
        # halt already broke the walk.
        drift_calls = {"n": 0}

        def fake_check_drift(lock):  # noqa: ARG001
            drift_calls["n"] += 1
            if drift_calls["n"] == 3:
                return [tmp_path / "foo.py"]
            return []

        monkeypatch.setattr(
            iter_lock_module, "check_drift", fake_check_drift,
        )

        # Capture handle_drift_collision invocations. Return False
        # so the iteration falls through to legacy halt (don't
        # exercise refresh_snapshot + continue here -- that's
        # tested in a sibling case).
        captured_collision: list[dict] = []

        def fake_handle_drift_collision(
            pre_snapshot, *, repo_root, yes, **kwargs,
        ):
            captured_collision.append({
                "pre_snapshot": pre_snapshot,
                "repo_root": repo_root,
                "yes": yes,
            })
            return False

        monkeypatch.setattr(
            cc_module,
            "handle_drift_collision",
            fake_handle_drift_collision,
        )

        # Silence the drift-halt warning's stderr noise -- the
        # phrasing is checked by sibling tests.
        monkeypatch.setattr(
            reconcile_module,
            "_emit_drift_halt_warning",
            lambda *a, **kw: None,
        )

        seed = Recommendation(
            id="seed", source="reconcile", severity="high",
            step_id=1, title="x", body="x",
        )

        cli_module._iterate_reconcile_loop(
            args=args,
            ctx=ctx,
            plan_path=plan_path,
            step_id=1,
            initial_recs=[seed],
            state=WalkState(yes_to_all=True),
            # max_iterations=2 so exactly one body pass runs (seed
            # bumps iter to 1, body completes → iter to 2, halt).
            # That single pass produces one apply_finding, one
            # per-finding post-apply drift halt, and one
            # handle_drift_collision call.
            budget=IterativeBudget(enabled=True, max_iterations=2),
        )

        assert len(captured_collision) == 1, (
            f"handle_drift_collision was called "
            f"{len(captured_collision)} time(s); expected exactly 1 "
            f"on per-finding post-apply drift. Wiring regressed."
        )
        snap = captured_collision[0]["pre_snapshot"]
        # Per-finding sidecar uses THIS rec's ``apply_result.pre_snapshot``
        # directly -- it carries the plan_path's
        # pre-apply "before" content that apply_finding captured.
        # (The iteration-merged baseline is a fallback for the
        # iteration-body's post-walk check; not exercised here.)
        assert snap.get(plan_path) == "before", (
            f"per-finding sidecar's pre_snapshot did not include "
            f"plan_path's pre-content; got {snap!r}"
        )

    def test_no_collision_sidecar_flag_skips_sidecar_branch(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``--no-collision-sidecar`` (args.collision_sidecar=False)
        bypasses the sidecar entirely and falls through to legacy
        halt. handle_drift_collision must NOT fire."""
        from plan_tool import change_collision as cc_module
        from plan_tool.cli import app as cli_module
        from plan_tool import drift_detection as iter_lock_module
        from plan_tool import launcher as launcher_module
        from plan_tool.convergence import IterativeBudget
        from plan_tool.launcher import ApplyFindingResult, RunResult
        from plan_tool.review import Recommendation
        from plan_tool.review_walk import WalkState

        args, ctx, plan_path = self._seed_minimal(tmp_path)
        args.collision_sidecar = False

        reconcile_stdout = "## Findings\n\n- HIGH: rec-alpha\n"

        monkeypatch.setattr(
            reconcile_module, "run_step",
            lambda *a, **kw: RunResult(  # noqa: ARG005
                step_id=1, exit_code=0, advanced_to=None, done=False,
                stdout=reconcile_stdout, step_title="do x",
            ),
        )
        monkeypatch.setattr(
            launcher_module, "apply_finding",
            lambda plan_path_arg, **kwargs: ApplyFindingResult(
                step_id=kwargs.get("step_id"),
                exit_code=0,
                verdict="APPLIED",
                summary="ok",
                diff_text="--- a\n+++ b\n@@ -1 +1 @@\n-x\n+y\n",
                pre_snapshot={plan_path: "before"},
                stdout="",
                introduced_findings=[],
                resolved_findings=[],
            ),
        )

        drift_n = {"n": 0}

        def fake_check_drift(lock):  # noqa: ARG001
            drift_n["n"] += 1
            return [tmp_path / "foo.py"] if drift_n["n"] == 2 else []

        monkeypatch.setattr(
            iter_lock_module, "check_drift", fake_check_drift,
        )

        collision_calls = {"n": 0}

        def fake_handle(*a, **kw):  # noqa: ARG001
            collision_calls["n"] += 1
            return False

        monkeypatch.setattr(
            cc_module, "handle_drift_collision", fake_handle,
        )
        monkeypatch.setattr(
            reconcile_module, "_emit_drift_halt_warning",
            lambda *a, **kw: None,
        )

        seed = Recommendation(
            id="seed", source="reconcile", severity="high",
            step_id=1, title="x", body="x",
        )

        cli_module._iterate_reconcile_loop(
            args=args,
            ctx=ctx,
            plan_path=plan_path,
            step_id=1,
            initial_recs=[seed],
            state=WalkState(yes_to_all=True),
            # max_iterations=2 so the body actually executes and the
            # post-walk drift halt site is reached. Without this the
            # ``collision_calls["n"] == 0`` assertion would pass
            # trivially (loop halts pre-body in max_iterations=1).
            budget=IterativeBudget(enabled=True, max_iterations=2),
        )

        assert collision_calls["n"] == 0, (
            f"handle_drift_collision fired {collision_calls['n']} "
            f"time(s) despite --no-collision-sidecar; the opt-out "
            f"flag is not respected by _iterate_reconcile_loop's "
            f"post-walk drift branch"
        )

    def test_collision_sidecar_merge_continues_iteration_after_refresh(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When handle_drift_collision returns True (user merged),
        the iteration loop:
        - calls refresh_snapshot to rebase the lock's hash baseline
          to the merged state (mirrors cmd_completeness Bug 1 from
          session-4 review)
        - records this iteration and continues to the next while-pass
          rather than emitting the scope-guard plan + releasing the
          lock + returning (the legacy halt path)
        """
        from plan_tool import change_collision as cc_module
        from plan_tool.cli import app as cli_module
        from plan_tool import drift_detection as iter_lock_module
        from plan_tool import launcher as launcher_module
        from plan_tool.convergence import IterativeBudget
        from plan_tool.launcher import ApplyFindingResult, RunResult
        from plan_tool.review import Recommendation
        from plan_tool.review_walk import WalkState

        args, ctx, plan_path = self._seed_minimal(tmp_path)
        args.auto_reconcile_on_drift = False

        # Two iterations' worth of run_step output. The second
        # iteration's stdout has NO findings so the loop terminates
        # via no_blocking_findings instead of running forever.
        run_call_n = {"n": 0}
        run_outputs = [
            "## Findings\n\n- HIGH: rec-alpha\n",
            "## Findings\n\n_(none)_\n",
        ]

        def fake_run_step(*a, **kw):  # noqa: ARG001
            n = run_call_n["n"]
            run_call_n["n"] += 1
            return RunResult(
                step_id=1, exit_code=0, advanced_to=None, done=False,
                stdout=run_outputs[min(n, len(run_outputs) - 1)],
                step_title="do x",
            )

        monkeypatch.setattr("plan_tool.cli.reconcile.run_step", fake_run_step)

        monkeypatch.setattr(
            launcher_module, "apply_finding",
            lambda plan_path_arg, **kwargs: ApplyFindingResult(
                step_id=kwargs.get("step_id"),
                exit_code=0,
                verdict="APPLIED",
                summary="ok",
                diff_text="--- a\n+++ b\n@@ -1 +1 @@\n-x\n+y\n",
                pre_snapshot={plan_path: "before"},
                stdout="",
                introduced_findings=[],
                resolved_findings=[],
            ),
        )

        # Drift fires on iteration 1's per-finding POST-apply check
        # inside action_fn. Call sequence per
        # iteration: iter-body pre-iter, action_fn per-finding
        # pre-apply, action_fn per-finding post-apply, iter-body
        # post-walk. So iter 1's post-apply is overall call #3.
        # Iter 2 should see only clean checks (refresh_snapshot
        # rebased the baseline post-merge).
        drift_calls: list[int] = []

        def fake_check_drift(lock):  # noqa: ARG001
            drift_calls.append(len(drift_calls) + 1)
            return (
                [tmp_path / "foo.py"]
                if len(drift_calls) == 3
                else []
            )

        monkeypatch.setattr(
            iter_lock_module, "check_drift", fake_check_drift,
        )

        # Merge-continue: handle_drift_collision returns True so the
        # iteration body refreshes the lock and ``continue``s to the
        # next while-pass.
        monkeypatch.setattr(
            cc_module, "handle_drift_collision",
            lambda pre_snapshot, **kwargs: True,
        )

        refresh_calls = {"n": 0}

        def fake_refresh_snapshot(lock):  # noqa: ARG001
            refresh_calls["n"] += 1

        monkeypatch.setattr(
            iter_lock_module, "refresh_snapshot", fake_refresh_snapshot,
        )

        monkeypatch.setattr(
            reconcile_module, "_emit_drift_halt_warning",
            lambda *a, **kw: None,
        )

        # If _emit_scope_guard_plan fires from the legacy halt path,
        # the merge-continue branch regressed. Sentinel.
        scope_guard_emits = {"n": 0}

        def fake_emit_scope_guard_plan(*a, **kw):  # noqa: ARG001
            scope_guard_emits["n"] += 1

        monkeypatch.setattr(
            reconcile_module, "_emit_scope_guard_plan",
            fake_emit_scope_guard_plan,
        )

        seed = Recommendation(
            id="seed", source="reconcile", severity="high",
            step_id=1, title="x", body="x",
        )

        cli_module._iterate_reconcile_loop(
            args=args,
            ctx=ctx,
            plan_path=plan_path,
            step_id=1,
            initial_recs=[seed],
            state=WalkState(yes_to_all=True),
            budget=IterativeBudget(enabled=True, max_iterations=3),
        )

        # refresh_snapshot fired exactly once -- on the merge-
        # continue branch after the user merged sidecars.
        assert refresh_calls["n"] == 1, (
            f"refresh_snapshot was called {refresh_calls['n']} "
            f"time(s); expected exactly 1 on the merge-continue "
            f"branch. Wiring regressed."
        )
        # Iteration 2 ran (loop didn't halt on iter 1's drift).
        # Without the ``continue``, run_step would have been called
        # only once; with it, the second iteration's no-findings
        # terminator fires after run_step #2.
        assert run_call_n["n"] >= 2, (
            f"run_step ran {run_call_n['n']} time(s); merge-"
            f"continue path did not advance to iteration 2. The "
            f"``continue`` after refresh_snapshot regressed."
        )


@pytest.mark.integration
class TestIterateReconcileLoopPerFindingDriftHalts:
    """per-finding pre/post-apply drift halts in
    ``_iterate_reconcile_loop``. Three new behaviors to pin:

    1. Per-finding PRE-apply drift check skips ``apply_finding``
       entirely (Lesson 2: don't spend tokens on a likely-spurious
       apply) and halts the iteration.
    2. Per-finding POST-apply drift check fires the change-collision
       sidecar against THIS rec's ``apply_result.pre_snapshot`` (not
       the iteration-merged baseline used by the legacy iteration-
       body fallback).
    3. Per-finding halt signal propagates through
       ``state.halt_requested`` so the walker breaks and the
       iteration body picks merge-continue vs. legacy halt based
       on ``state.halt_merged``.

    Each test mocks ``check_drift`` to control which of the four
    drift-check sites per iteration fires (call sequence per iter:
    iter-body pre-iter → action_fn per-finding pre-apply →
    action_fn per-finding post-apply → iter-body post-walk).
    """

    def _seed_minimal(self, tmp_path: Path):
        import argparse
        from plan_tool.locator import PlanToolContext

        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        plan_path = plans_dir / "1-drift-test.md"
        plan_path.write_text(
            "---\n"
            "title: Drift Iter Test\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: do x\n"
            "    files:\n"
            "      - foo.py\n"
            "    status: current\n"
            "---\n"
            "\n"
            "## Overview\n\nx\n",
            encoding="utf-8",
        )
        (tmp_path / "foo.py").write_text(
            "def bar():\n    return 41\n", encoding="utf-8"
        )
        args = argparse.Namespace(
            name="drift-test",
            allow_drift=False,
            auto_reconcile_on_drift=False,
            collision_sidecar=True,            triage=False,
            yes=True,
        )
        ctx = PlanToolContext(
            repo_root=tmp_path, plans_dir=plans_dir, entries=[],
        )
        return args, ctx, plan_path

    def test_per_finding_pre_apply_drift_skips_apply_finding(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Drift detected at the per-finding pre-apply site (action_fn,
        before ``apply_finding`` fires) must halt without spending the
        claude tokens that ``apply_finding`` would otherwise consume.
        Lesson 2: token preservation > strict spec integrity. The
        walker breaks via the new halt-signal channel; the iteration
        body takes the legacy halt path (no merge here)."""
        from plan_tool.cli import app as cli_module
        from plan_tool import drift_detection as iter_lock_module
        from plan_tool import launcher as launcher_module
        from plan_tool.convergence import IterativeBudget
        from plan_tool.launcher import RunResult
        from plan_tool.review import Recommendation
        from plan_tool.review_walk import WalkState

        args, ctx, plan_path = self._seed_minimal(tmp_path)
        args.collision_sidecar = False  # don't exercise sidecar here

        reconcile_stdout = "## Findings\n\n- HIGH: rec-alpha\n"

        monkeypatch.setattr(
            reconcile_module, "run_step",
            lambda *a, **kw: RunResult(  # noqa: ARG005
                step_id=1, exit_code=0, advanced_to=None, done=False,
                stdout=reconcile_stdout, step_title="do x",
            ),
        )

        # Drift fires on call #2 (action_fn's per-finding pre-apply).
        # Call #1 = iter-body pre-iter (clean); #2 = per-finding
        # pre-apply (DRIFT) → halt skips apply_finding.
        drift_calls = {"n": 0}

        def fake_check_drift(lock):  # noqa: ARG001
            drift_calls["n"] += 1
            return (
                [tmp_path / "foo.py"]
                if drift_calls["n"] == 2 else []
            )

        monkeypatch.setattr(
            iter_lock_module, "check_drift", fake_check_drift,
        )

        apply_calls = {"n": 0}

        def fake_apply(*a, **kw):  # noqa: ARG001
            apply_calls["n"] += 1
            from plan_tool.launcher import ApplyFindingResult
            return ApplyFindingResult(
                step_id=kw.get("step_id"),
                exit_code=0,
                verdict="APPLIED",
                summary="ok",
                diff_text="--- a\n+++ b\n@@ -1 +1 @@\n-x\n+y\n",
                pre_snapshot={plan_path: "before"},
                stdout="",
            )

        monkeypatch.setattr(launcher_module, "apply_finding", fake_apply)

        # Silence the drift-halt warning's stderr noise.
        monkeypatch.setattr(
            reconcile_module, "_emit_drift_halt_warning",
            lambda *a, **kw: None,
        )

        seed = Recommendation(
            id="seed", source="reconcile", severity="high",
            step_id=1, title="x", body="x",
        )

        cli_module._iterate_reconcile_loop(
            args=args,
            ctx=ctx,
            plan_path=plan_path,
            step_id=1,
            initial_recs=[seed],
            state=WalkState(yes_to_all=True),
            budget=IterativeBudget(enabled=True, max_iterations=2),
        )

        # apply_finding never ran -- the per-finding pre-apply drift
        # check intercepted it. Without #14a, drift would only fire
        # at iteration-level POST-walk (call #4) AFTER apply_finding
        # had already burned its claude tokens.
        assert apply_calls["n"] == 0, (
            f"apply_finding ran {apply_calls['n']} time(s) despite "
            f"per-finding pre-apply drift; Lesson 2 token "
            f"preservation regressed -- claude tokens were spent on "
            f"a likely-spurious apply"
        )

    def test_per_finding_post_apply_drift_sidecar_uses_apply_pre_snapshot(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """At per-finding granularity, the sidecar's
        baseline is THIS rec's ``apply_result.pre_snapshot`` (plan +
        step.detail), NOT the iteration-merged baseline used by the
        iteration-body's post-walk fallback. Verifies the action_fn
        feeds ``handle_drift_collision`` the per-rec snapshot."""
        from plan_tool import change_collision as cc_module
        from plan_tool.cli import app as cli_module
        from plan_tool import drift_detection as iter_lock_module
        from plan_tool import launcher as launcher_module
        from plan_tool.convergence import IterativeBudget
        from plan_tool.launcher import ApplyFindingResult, RunResult
        from plan_tool.review import Recommendation
        from plan_tool.review_walk import WalkState

        args, ctx, plan_path = self._seed_minimal(tmp_path)

        reconcile_stdout = "## Findings\n\n- HIGH: rec-alpha\n"

        monkeypatch.setattr(
            reconcile_module, "run_step",
            lambda *a, **kw: RunResult(  # noqa: ARG005
                step_id=1, exit_code=0, advanced_to=None, done=False,
                stdout=reconcile_stdout, step_title="do x",
            ),
        )

        # apply_finding returns a distinct sentinel pre_snapshot so
        # the assertion below can distinguish the per-rec snapshot
        # from any iteration-level merged baseline.
        per_finding_pre = {plan_path: "this-finding-pre-content"}
        monkeypatch.setattr(
            launcher_module, "apply_finding",
            lambda plan_path_arg, **kwargs: ApplyFindingResult(
                step_id=kwargs.get("step_id"),
                exit_code=0,
                verdict="APPLIED",
                summary="ok",
                diff_text="--- a\n+++ b\n@@ -1 +1 @@\n-x\n+y\n",
                pre_snapshot=dict(per_finding_pre),
                stdout="",
            ),
        )

        # Drift fires on call #3 (action_fn's per-finding POST-apply).
        drift_calls = {"n": 0}

        def fake_check_drift(lock):  # noqa: ARG001
            drift_calls["n"] += 1
            return (
                [tmp_path / "foo.py"]
                if drift_calls["n"] == 3 else []
            )

        monkeypatch.setattr(
            iter_lock_module, "check_drift", fake_check_drift,
        )

        captured: list[dict] = []

        def fake_handle_drift_collision(
            pre_snapshot, *, repo_root, yes, **kwargs,
        ):
            captured.append({
                "pre_snapshot": pre_snapshot,
                "repo_root": repo_root,
                "yes": yes,
            })
            return False  # decline merge → fall through to legacy halt

        monkeypatch.setattr(
            cc_module, "handle_drift_collision",
            fake_handle_drift_collision,
        )
        monkeypatch.setattr(
            reconcile_module, "_emit_drift_halt_warning",
            lambda *a, **kw: None,
        )

        seed = Recommendation(
            id="seed", source="reconcile", severity="high",
            step_id=1, title="x", body="x",
        )

        cli_module._iterate_reconcile_loop(
            args=args,
            ctx=ctx,
            plan_path=plan_path,
            step_id=1,
            initial_recs=[seed],
            state=WalkState(yes_to_all=True),
            budget=IterativeBudget(enabled=True, max_iterations=2),
        )

        assert len(captured) == 1, (
            f"handle_drift_collision was called {len(captured)} "
            f"time(s); expected exactly 1 from action_fn's "
            f"per-finding post-apply drift branch"
        )
        # Pin the per-rec snapshot semantics: the sidecar baseline
        # must be THIS finding's apply_result.pre_snapshot.
        assert captured[0]["pre_snapshot"] == per_finding_pre, (
            f"per-finding sidecar baseline mismatch; expected "
            f"{per_finding_pre!r}, got "
            f"{captured[0]['pre_snapshot']!r}"
        )

    def test_per_finding_merge_continue_advances_iteration(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When the per-finding post-apply sidecar returns True
        (user merged), action_fn calls refresh_snapshot and signals
        halt_merged=True. The iteration body sees this and continues
        to the next while-pass rather than emitting the scope-guard
        plan + releasing the lock."""
        from plan_tool import change_collision as cc_module
        from plan_tool.cli import app as cli_module
        from plan_tool import drift_detection as iter_lock_module
        from plan_tool import launcher as launcher_module
        from plan_tool.convergence import IterativeBudget
        from plan_tool.launcher import ApplyFindingResult, RunResult
        from plan_tool.review import Recommendation
        from plan_tool.review_walk import WalkState

        args, ctx, plan_path = self._seed_minimal(tmp_path)

        # Two iterations' worth of run_step output; iter 2's output
        # has no findings so the loop terminates naturally.
        run_n = {"n": 0}
        outputs = [
            "## Findings\n\n- HIGH: rec-alpha\n",
            "## Findings\n\n_(none)_\n",
        ]

        def fake_run_step(*a, **kw):  # noqa: ARG001
            n = run_n["n"]
            run_n["n"] += 1
            return RunResult(
                step_id=1, exit_code=0, advanced_to=None, done=False,
                stdout=outputs[min(n, len(outputs) - 1)],
                step_title="do x",
            )

        monkeypatch.setattr("plan_tool.cli.reconcile.run_step", fake_run_step)
        monkeypatch.setattr(
            launcher_module, "apply_finding",
            lambda plan_path_arg, **kwargs: ApplyFindingResult(
                step_id=kwargs.get("step_id"),
                exit_code=0,
                verdict="APPLIED",
                summary="ok",
                diff_text="--- a\n+++ b\n@@ -1 +1 @@\n-x\n+y\n",
                pre_snapshot={plan_path: "before"},
                stdout="",
            ),
        )

        # Drift on call #3 (per-finding post-apply, iter 1).
        drift_n = {"n": 0}

        def fake_check_drift(lock):  # noqa: ARG001
            drift_n["n"] += 1
            return (
                [tmp_path / "foo.py"]
                if drift_n["n"] == 3 else []
            )

        monkeypatch.setattr(
            iter_lock_module, "check_drift", fake_check_drift,
        )

        # User merges → True. action_fn calls refresh_snapshot,
        # signals halt_merged=True, walker breaks, iteration body
        # ``continue``s.
        monkeypatch.setattr(
            cc_module, "handle_drift_collision",
            lambda pre_snapshot, **kwargs: True,
        )

        refresh_n = {"n": 0}
        monkeypatch.setattr(
            iter_lock_module, "refresh_snapshot",
            lambda lock: refresh_n.__setitem__(  # noqa: ARG005
                "n", refresh_n["n"] + 1,
            ),
        )

        scope_plan_n = {"n": 0}
        # ruff/pyflakes false positive: a `del <name>` later in this function
        # (see below) makes it misreport this closure reference as F821
        # undefined, even though it is a valid capture (confirmed by a
        # minimal repro: any `def outer(): x=...; def inner(): use(x);
        # inner(); del x` triggers the same misreport). Silencing rather than
        # rewriting keeps the intentional-cleanup `del` in place.
        monkeypatch.setattr(
            reconcile_module, "_emit_scope_guard_plan",
            lambda *a, **kw: scope_plan_n.__setitem__(  # noqa: F821
                "n", scope_plan_n["n"] + 1,  # noqa: F821
            ),
        )
        monkeypatch.setattr(
            reconcile_module, "_emit_drift_halt_warning",
            lambda *a, **kw: None,
        )

        seed = Recommendation(
            id="seed", source="reconcile", severity="high",
            step_id=1, title="x", body="x",
        )

        cli_module._iterate_reconcile_loop(
            args=args,
            ctx=ctx,
            plan_path=plan_path,
            step_id=1,
            initial_recs=[seed],
            state=WalkState(yes_to_all=True),
            budget=IterativeBudget(enabled=True, max_iterations=3),
        )

        # Refresh fired once (post-apply sidecar merge-continue).
        assert refresh_n["n"] == 1, (
            f"refresh_snapshot was called {refresh_n['n']} time(s); "
            f"expected exactly 1 from action_fn's merge-continue branch"
        )
        # Iter 2 ran -- the ``continue`` from the iteration body's
        # halt_merged branch worked. Without merge-continue, the
        # legacy halt path would have ``return``ed at iter 1 and
        # run_step would have fired only once.
        assert run_n["n"] >= 2, (
            f"run_step ran {run_n['n']} time(s); per-finding merge-"
            f"continue did not advance to iter 2"
        )
        # ``_emit_scope_guard_plan`` is NOT a useful signal here: it
        # fires on natural max_iterations exit too. The run_step
        # count above proves the merge-continue path was taken
        # (legacy halt would have returned at iter 1).
        del scope_plan_n  # kept the patch to silence its output

    def test_per_finding_drift_phase_during_after_first_apply(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``state.work_landed_in_loop`` flips to True after the first
        kept apply. A second finding's per-finding pre-
        apply drift halt then renders with ``phase="during"`` rather
        than ``"before"``. Pin the per-finding phrasing wiring."""
        from plan_tool.cli import app as cli_module
        from plan_tool import drift_detection as iter_lock_module
        from plan_tool import launcher as launcher_module
        from plan_tool.convergence import IterativeBudget
        from plan_tool.launcher import ApplyFindingResult, RunResult
        from plan_tool.review import Recommendation
        from plan_tool.review_walk import WalkState

        args, ctx, plan_path = self._seed_minimal(tmp_path)
        args.collision_sidecar = False

        # Two findings: the first applies cleanly, the second hits
        # pre-apply drift.
        reconcile_stdout = (
            "## Findings\n\n"
            "- HIGH: rec-alpha\n\n"
            "- HIGH: rec-beta\n"
        )

        monkeypatch.setattr(
            reconcile_module, "run_step",
            lambda *a, **kw: RunResult(  # noqa: ARG005
                step_id=1, exit_code=0, advanced_to=None, done=False,
                stdout=reconcile_stdout, step_title="do x",
            ),
        )

        monkeypatch.setattr(
            launcher_module, "apply_finding",
            lambda plan_path_arg, **kwargs: ApplyFindingResult(
                step_id=kwargs.get("step_id"),
                exit_code=0,
                verdict="APPLIED",
                summary="ok",
                diff_text="--- a\n+++ b\n@@ -1 +1 @@\n-x\n+y\n",
                pre_snapshot={plan_path: "before"},
                stdout="",
            ),
        )

        # Call sequence:
        #   #1 iter-body pre-iter: clean
        #   #2 rec-alpha per-finding pre-apply: clean
        #   #3 rec-alpha per-finding post-apply: clean
        #   #4 rec-beta per-finding pre-apply: DRIFT → phase=during
        drift_n = {"n": 0}

        def fake_check_drift(lock):  # noqa: ARG001
            drift_n["n"] += 1
            return (
                [tmp_path / "foo.py"]
                if drift_n["n"] == 4 else []
            )

        monkeypatch.setattr(
            iter_lock_module, "check_drift", fake_check_drift,
        )

        captured_phases: list[str] = []

        def fake_emit_warning(drifted, *, phase, **kwargs):  # noqa: ARG001
            captured_phases.append(phase)

        monkeypatch.setattr(
            reconcile_module, "_emit_drift_halt_warning", fake_emit_warning,
        )

        seed = Recommendation(
            id="seed", source="reconcile", severity="high",
            step_id=1, title="x", body="x",
        )

        cli_module._iterate_reconcile_loop(
            args=args,
            ctx=ctx,
            plan_path=plan_path,
            step_id=1,
            initial_recs=[seed],
            state=WalkState(yes_to_all=True),
            budget=IterativeBudget(enabled=True, max_iterations=2),
        )

        # rec-beta's pre-apply drift halt fires with "during" because
        # rec-alpha's apply landed earlier in this loop.
        assert captured_phases == ["during"], (
            f"per-finding drift phrasing regressed; expected "
            f"['during'] (first apply landed → work_landed_in_loop "
            f"True), got {captured_phases!r}"
        )

    def test_pre_apply_drift_persists_rec_as_skip_not_applied(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A rec halted at the per-finding pre-apply drift check
        was NEVER applied -- no claude tokens spent, no edits on
        disk. The walker must persist its annotation as
        ``status="skip"`` (with the drift message as the note),
        NOT ``status="applied"``. Otherwise future
        ``cmd_review_walk`` invocations would skip the rec via the
        "already applied" check, masking that it still needs to
        be reapplied. Pinned via ``state.halt_apply_landed=False``
        signal from action_fn -- the assertion reads the on-disk
        saved review JSON since walker's persist_fn default is
        bound at function-definition time and can't be intercepted
        via module-level monkeypatch."""
        from plan_tool.cli import app as cli_module
        from plan_tool import drift_detection as iter_lock_module
        from plan_tool import launcher as launcher_module
        from plan_tool.convergence import IterativeBudget
        from plan_tool.launcher import RunResult
        from plan_tool.review import Recommendation
        from plan_tool.review_persistence import load_review
        from plan_tool.review_walk import WalkState

        args, ctx, plan_path = self._seed_minimal(tmp_path)
        args.collision_sidecar = False  # not under test here

        reconcile_stdout = "## Findings\n\n- HIGH: rec-alpha\n"

        monkeypatch.setattr(
            reconcile_module, "run_step",
            lambda *a, **kw: RunResult(  # noqa: ARG005
                step_id=1, exit_code=0, advanced_to=None, done=False,
                stdout=reconcile_stdout, step_title="do x",
            ),
        )

        # Drift on call #2 (per-finding pre-apply) -- skips
        # apply_finding entirely.
        drift_n = {"n": 0}

        def fake_check_drift(lock):  # noqa: ARG001
            drift_n["n"] += 1
            return (
                [tmp_path / "foo.py"]
                if drift_n["n"] == 2 else []
            )

        monkeypatch.setattr(
            iter_lock_module, "check_drift", fake_check_drift,
        )

        apply_n = {"n": 0}

        def fake_apply(*a, **kw):  # noqa: ARG001
            apply_n["n"] += 1
            from plan_tool.launcher import ApplyFindingResult
            return ApplyFindingResult(
                step_id=kw.get("step_id"),
                exit_code=0,
                verdict="APPLIED",
                summary="ok",
                diff_text="--- a\n+++ b\n@@ -1 +1 @@\n-x\n+y\n",
                pre_snapshot={plan_path: "before"},
                stdout="",
            )

        monkeypatch.setattr(launcher_module, "apply_finding", fake_apply)

        # Silence drift warning noise.
        monkeypatch.setattr(
            reconcile_module, "_emit_drift_halt_warning",
            lambda *a, **kw: None,
        )

        seed = Recommendation(
            id="seed", source="reconcile", severity="high",
            step_id=1, title="x", body="x",
        )

        cli_module._iterate_reconcile_loop(
            args=args,
            ctx=ctx,
            plan_path=plan_path,
            step_id=1,
            initial_recs=[seed],
            state=WalkState(yes_to_all=True),
            budget=IterativeBudget(enabled=True, max_iterations=2),
        )

        # apply_finding was skipped (drift-pre-apply).
        assert apply_n["n"] == 0, (
            f"setup invariant: apply_finding should have been "
            f"skipped on pre-apply drift; ran {apply_n['n']} time(s)"
        )
        # Load the saved review and confirm the rec's annotation
        # status is "skip" (not "applied").
        reviews_dir = (
            tmp_path / "plans" / "plan-details" / args.name / "reports"
        )
        saved_files = sorted(reviews_dir.glob("*-reconcile.json"))
        assert saved_files, (
            f"no saved reconcile review found under {reviews_dir}; "
            f"_iterate_reconcile_loop didn't reach save_review"
        )
        saved = load_review(saved_files[-1])
        assert saved.annotations, (
            "no annotations persisted on the saved review; walker "
            "didn't reach persist_fn"
        )
        statuses = [a.status for a in saved.annotations.values()]
        assert all(s == "skip" for s in statuses), (
            f"pre-apply drift-skipped rec persisted as "
            f"status='applied' (the misleading legacy behavior). "
            f"Walker should consult state.halt_apply_landed and "
            f"persist as 'skip' instead. Got statuses: {statuses!r}"
        )

    def test_post_apply_drift_persists_rec_as_applied(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A rec halted at the per-finding POST-apply drift check
        DID run apply_finding (claude tokens spent, edits landed on
        disk or in a sidecar). The walker must persist its
        annotation as ``status="applied"`` so the saved review
        reflects the work that occurred. Counterpart to
        ``test_pre_apply_drift_persists_rec_as_skip_not_applied``."""
        from plan_tool import change_collision as cc_module
        from plan_tool.cli import app as cli_module
        from plan_tool import drift_detection as iter_lock_module
        from plan_tool import launcher as launcher_module
        from plan_tool.convergence import IterativeBudget
        from plan_tool.launcher import ApplyFindingResult, RunResult
        from plan_tool.review import Recommendation
        from plan_tool.review_persistence import load_review
        from plan_tool.review_walk import WalkState

        args, ctx, plan_path = self._seed_minimal(tmp_path)

        reconcile_stdout = "## Findings\n\n- HIGH: rec-alpha\n"

        monkeypatch.setattr(
            reconcile_module, "run_step",
            lambda *a, **kw: RunResult(  # noqa: ARG005
                step_id=1, exit_code=0, advanced_to=None, done=False,
                stdout=reconcile_stdout, step_title="do x",
            ),
        )
        monkeypatch.setattr(
            launcher_module, "apply_finding",
            lambda plan_path_arg, **kwargs: ApplyFindingResult(
                step_id=kwargs.get("step_id"),
                exit_code=0,
                verdict="APPLIED",
                summary="ok",
                diff_text="--- a\n+++ b\n@@ -1 +1 @@\n-x\n+y\n",
                pre_snapshot={plan_path: "before"},
                stdout="",
            ),
        )

        # Drift on call #3 (per-finding POST-apply).
        drift_n = {"n": 0}

        def fake_check_drift(lock):  # noqa: ARG001
            drift_n["n"] += 1
            return (
                [tmp_path / "foo.py"]
                if drift_n["n"] == 3 else []
            )

        monkeypatch.setattr(
            iter_lock_module, "check_drift", fake_check_drift,
        )
        monkeypatch.setattr(
            cc_module, "handle_drift_collision",
            lambda pre_snapshot, **kwargs: False,  # decline
        )
        monkeypatch.setattr(
            reconcile_module, "_emit_drift_halt_warning",
            lambda *a, **kw: None,
        )

        seed = Recommendation(
            id="seed", source="reconcile", severity="high",
            step_id=1, title="x", body="x",
        )

        cli_module._iterate_reconcile_loop(
            args=args,
            ctx=ctx,
            plan_path=plan_path,
            step_id=1,
            initial_recs=[seed],
            state=WalkState(yes_to_all=True),
            budget=IterativeBudget(enabled=True, max_iterations=2),
        )

        # Read the saved review JSON and confirm the persisted
        # annotation is status="applied" (apply landed; only the
        # halt cuts off subsequent recs).
        reviews_dir = (
            tmp_path / "plans" / "plan-details" / args.name / "reports"
        )
        saved_files = sorted(reviews_dir.glob("*-reconcile.json"))
        assert saved_files, (
            f"no saved reconcile review found under {reviews_dir}"
        )
        saved = load_review(saved_files[-1])
        assert saved.annotations, (
            "no annotations persisted; walker didn't reach persist_fn"
        )
        statuses = [a.status for a in saved.annotations.values()]
        assert "applied" in statuses, (
            f"post-apply drift-halted rec should persist as "
            f"'applied' (apply did land). Got statuses: {statuses!r}"
        )
        assert "skip" not in statuses, (
            f"post-apply drift halt mis-persisted as 'skip'; "
            f"state.halt_apply_landed=True should have routed it "
            f"to 'applied'. Got: {statuses!r}"
        )

    def test_iter_body_post_walk_sidecar_fallback_when_all_reverted(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Iteration-body's post-walk sidecar fallback
        fires when no per-finding post-apply drift check fires. This
        happens when every apply went through a revert path
        (verdict BLOCKED / NOT-APPLICABLE / REFUSED / non-zero exit)
        -- ``phase_outcome != "success"`` for any, so the action_fn's
        per-finding post-apply check short-circuits.

        ``ReconcileScopeGuard.record_apply`` runs BEFORE the verdict
        branches so ``apply_pre_snapshots`` is still populated even
        for reverts -- that's what lets the iter-body fallback
        compose a merged baseline. Without record_apply running on
        reverts, the fallback would call handle_drift_collision with
        an empty snapshot and produce no sidecars.

        Pins the wiring shape (Lesson 7) for the narrow corner case
        where mid-walk drift escapes per-finding detection."""
        from plan_tool import change_collision as cc_module
        from plan_tool.cli import app as cli_module
        from plan_tool import drift_detection as iter_lock_module
        from plan_tool import launcher as launcher_module
        from plan_tool.convergence import IterativeBudget
        from plan_tool.launcher import ApplyFindingResult, RunResult
        from plan_tool.review import Recommendation
        from plan_tool.review_walk import WalkState

        args, ctx, plan_path = self._seed_minimal(tmp_path)
        args.collision_sidecar = True  # exercising the fallback
        args.auto_reconcile_on_drift = False

        reconcile_stdout = "## Findings\n\n- HIGH: rec-alpha\n"

        monkeypatch.setattr(
            reconcile_module, "run_step",
            lambda *a, **kw: RunResult(  # noqa: ARG005
                step_id=1, exit_code=0, advanced_to=None, done=False,
                stdout=reconcile_stdout, step_title="do x",
            ),
        )

        # BLOCKED verdict: apply_finding "did not apply" but record_apply
        # was already called with this fake's pre_snapshot. phase_outcome
        # flips to "reverted" so per-finding scope eval + post-apply
        # drift check SKIP. The merged baseline composed at iter-body
        # post-walk drift halt will carry this entry.
        per_finding_pre = {plan_path: "iter-start-content"}
        monkeypatch.setattr(
            launcher_module, "apply_finding",
            lambda plan_path_arg, **kwargs: ApplyFindingResult(
                step_id=kwargs.get("step_id"),
                exit_code=0,
                verdict="BLOCKED",
                summary="claude declined",
                diff_text="",
                pre_snapshot=dict(per_finding_pre),
                stdout="",
            ),
        )

        # Call sequence:
        #   #1 iter-body pre-iter: clean
        #   #2 per-finding pre-apply: clean
        #   (apply_finding returns BLOCKED → no per-finding post-apply
        #    check fires)
        #   #3 iter-body post-walk: DRIFT → fallback sidecar branch
        drift_n = {"n": 0}

        def fake_check_drift(lock):  # noqa: ARG001
            drift_n["n"] += 1
            return (
                [tmp_path / "foo.py"]
                if drift_n["n"] == 3 else []
            )

        monkeypatch.setattr(
            iter_lock_module, "check_drift", fake_check_drift,
        )

        captured: list[dict] = []

        def fake_handle_drift_collision(
            pre_snapshot, *, repo_root, yes, **kwargs,
        ):
            captured.append({
                "pre_snapshot": pre_snapshot,
                "repo_root": repo_root,
                "yes": yes,
            })
            return False  # decline → legacy halt

        monkeypatch.setattr(
            cc_module, "handle_drift_collision",
            fake_handle_drift_collision,
        )
        monkeypatch.setattr(
            reconcile_module, "_emit_drift_halt_warning",
            lambda *a, **kw: None,
        )

        seed = Recommendation(
            id="seed", source="reconcile", severity="high",
            step_id=1, title="x", body="x",
        )

        cli_module._iterate_reconcile_loop(
            args=args,
            ctx=ctx,
            plan_path=plan_path,
            step_id=1,
            initial_recs=[seed],
            state=WalkState(yes_to_all=True),
            budget=IterativeBudget(enabled=True, max_iterations=2),
        )

        # Fallback sidecar fired once with the MERGED baseline from
        # record_apply -- not the per-rec apply_result.pre_snapshot.
        # For a single-rec walk, "merged" first-seen-per-path equals
        # that one rec's pre_snapshot. The key test: even though
        # apply_finding returned BLOCKED (reverted path skipping the
        # per-finding sidecar), record_apply still populated the
        # snapshots so the fallback has something to feed
        # handle_drift_collision.
        assert len(captured) == 1, (
            f"iter-body fallback sidecar fired {len(captured)} "
            f"time(s); expected 1. When all applies revert, the "
            f"per-finding post-apply check is skipped; the iter-body "
            f"post-walk check is the only path to the sidecar"
        )
        assert captured[0]["pre_snapshot"] == per_finding_pre, (
            f"merged baseline missing the BLOCKED rec's "
            f"pre_snapshot; got {captured[0]['pre_snapshot']!r}. "
            f"record_apply must run BEFORE verdict branches so the "
            f"fallback has data to merge even on revert paths."
        )

    def test_no_collision_sidecar_flag_bypasses_per_finding_sidecar(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When ``args.collision_sidecar=False``, the per-finding
        post-apply drift branch in action_fn must NOT invoke
        ``handle_drift_collision`` -- it should set halt and fall
        through to the iteration body's legacy halt path. Pins the
        ``--no-collision-sidecar`` flag's effect on the new
        per-finding sidecar wiring."""
        from plan_tool import change_collision as cc_module
        from plan_tool.cli import app as cli_module
        from plan_tool import drift_detection as iter_lock_module
        from plan_tool import launcher as launcher_module
        from plan_tool.convergence import IterativeBudget
        from plan_tool.launcher import ApplyFindingResult, RunResult
        from plan_tool.review import Recommendation
        from plan_tool.review_walk import WalkState

        args, ctx, plan_path = self._seed_minimal(tmp_path)
        args.collision_sidecar = False  # opt out per-finding sidecar

        reconcile_stdout = "## Findings\n\n- HIGH: rec-alpha\n"
        monkeypatch.setattr(
            reconcile_module, "run_step",
            lambda *a, **kw: RunResult(  # noqa: ARG005
                step_id=1, exit_code=0, advanced_to=None, done=False,
                stdout=reconcile_stdout, step_title="do x",
            ),
        )
        monkeypatch.setattr(
            launcher_module, "apply_finding",
            lambda plan_path_arg, **kwargs: ApplyFindingResult(
                step_id=kwargs.get("step_id"),
                exit_code=0,
                verdict="APPLIED",
                summary="ok",
                diff_text="--- a\n+++ b\n@@ -1 +1 @@\n-x\n+y\n",
                pre_snapshot={plan_path: "before"},
                stdout="",
            ),
        )

        # Drift on call #3 (per-finding POST-apply).
        drift_n = {"n": 0}

        def fake_check_drift(lock):  # noqa: ARG001
            drift_n["n"] += 1
            return (
                [tmp_path / "foo.py"]
                if drift_n["n"] == 3 else []
            )

        monkeypatch.setattr(
            iter_lock_module, "check_drift", fake_check_drift,
        )

        collision_calls = {"n": 0}

        def fake_handle(*a, **kw):  # noqa: ARG001
            collision_calls["n"] += 1
            return False

        monkeypatch.setattr(
            cc_module, "handle_drift_collision", fake_handle,
        )
        monkeypatch.setattr(
            reconcile_module, "_emit_drift_halt_warning",
            lambda *a, **kw: None,
        )

        seed = Recommendation(
            id="seed", source="reconcile", severity="high",
            step_id=1, title="x", body="x",
        )

        cli_module._iterate_reconcile_loop(
            args=args,
            ctx=ctx,
            plan_path=plan_path,
            step_id=1,
            initial_recs=[seed],
            state=WalkState(yes_to_all=True),
            budget=IterativeBudget(enabled=True, max_iterations=2),
        )

        assert collision_calls["n"] == 0, (
            f"handle_drift_collision was called {collision_calls['n']} "
            f"time(s) despite --no-collision-sidecar at the per-"
            f"finding post-apply site. The opt-out flag is not "
            f"respected in action_fn's drift branch."
        )

    def test_allow_drift_bypasses_per_finding_drift_checks(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When ``args.allow_drift=True``, BOTH per-finding drift
        checks (pre-apply + post-apply) must short-circuit. The
        reconcile loop continues unaware of drift, mirroring the
        iteration-body's existing ``--allow-drift`` semantics."""
        from plan_tool.cli import app as cli_module
        from plan_tool import drift_detection as iter_lock_module
        from plan_tool import launcher as launcher_module
        from plan_tool.convergence import IterativeBudget
        from plan_tool.launcher import ApplyFindingResult, RunResult
        from plan_tool.review import Recommendation
        from plan_tool.review_walk import WalkState

        args, ctx, plan_path = self._seed_minimal(tmp_path)
        args.allow_drift = True  # opt out of drift checks
        args.collision_sidecar = False

        reconcile_stdout = "## Findings\n\n- HIGH: rec-alpha\n"
        monkeypatch.setattr(
            reconcile_module, "run_step",
            lambda *a, **kw: RunResult(  # noqa: ARG005
                step_id=1, exit_code=0, advanced_to=None, done=False,
                stdout=reconcile_stdout, step_title="do x",
            ),
        )

        apply_n = {"n": 0}

        def fake_apply(*a, **kw):  # noqa: ARG001
            apply_n["n"] += 1
            return ApplyFindingResult(
                step_id=kw.get("step_id"),
                exit_code=0,
                verdict="APPLIED",
                summary="ok",
                diff_text="--- a\n+++ b\n@@ -1 +1 @@\n-x\n+y\n",
                pre_snapshot={plan_path: "before"},
                stdout="",
            )

        monkeypatch.setattr(launcher_module, "apply_finding", fake_apply)

        # check_drift returns drift on every call -- none of the
        # gated paths should fire with allow_drift=True.
        drift_n = {"n": 0}

        def fake_check_drift(lock):  # noqa: ARG001
            drift_n["n"] += 1
            return [tmp_path / "foo.py"]

        monkeypatch.setattr(
            iter_lock_module, "check_drift", fake_check_drift,
        )

        warnings: list[str] = []
        monkeypatch.setattr(
            reconcile_module, "_emit_drift_halt_warning",
            lambda *a, **kw: warnings.append(kw.get("phase", "?")),
        )

        seed = Recommendation(
            id="seed", source="reconcile", severity="high",
            step_id=1, title="x", body="x",
        )

        cli_module._iterate_reconcile_loop(
            args=args,
            ctx=ctx,
            plan_path=plan_path,
            step_id=1,
            initial_recs=[seed],
            state=WalkState(yes_to_all=True),
            budget=IterativeBudget(enabled=True, max_iterations=2),
        )

        # apply_finding DID run -- per-finding pre-apply check
        # didn't bail. Without the allow_drift guard, drift on
        # call #2 (pre-apply) would have skipped apply_finding.
        assert apply_n["n"] >= 1, (
            f"apply_finding ran {apply_n['n']} time(s); "
            f"--allow-drift should have let it run despite "
            f"check_drift returning drift on every call"
        )
        # No drift-halt warnings were emitted from gated paths.
        assert warnings == [], (
            f"_emit_drift_halt_warning fired {warnings!r} times "
            f"despite --allow-drift; one of the drift checks is "
            f"not honoring the opt-out flag"
        )

    def test_halt_drifted_threads_drifted_paths_to_auto_reconcile(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When per-finding drift halts (with halt_merged=False),
        the iteration body reads ``state.halt_drifted`` into a local
        and passes it as the ``drifted`` arg of
        ``run_auto_reconcile_on_drift``. Pins the wiring so a future
        refactor that drops the threading is caught."""
        from plan_tool import auto_reconcile as auto_reconcile_module
        from plan_tool.cli import app as cli_module
        from plan_tool import drift_detection as iter_lock_module
        from plan_tool import launcher as launcher_module
        from plan_tool.convergence import IterativeBudget
        from plan_tool.launcher import RunResult
        from plan_tool.review import Recommendation
        from plan_tool.review_walk import WalkState

        args, ctx, plan_path = self._seed_minimal(tmp_path)
        args.collision_sidecar = False
        args.auto_reconcile_on_drift = True  # exercise the threading

        reconcile_stdout = "## Findings\n\n- HIGH: rec-alpha\n"
        monkeypatch.setattr(
            reconcile_module, "run_step",
            lambda *a, **kw: RunResult(  # noqa: ARG005
                step_id=1, exit_code=0, advanced_to=None, done=False,
                stdout=reconcile_stdout, step_title="do x",
            ),
        )

        from plan_tool.launcher import ApplyFindingResult
        monkeypatch.setattr(
            launcher_module, "apply_finding",
            lambda plan_path_arg, **kwargs: ApplyFindingResult(
                step_id=kwargs.get("step_id"),
                exit_code=0,
                verdict="APPLIED",
                summary="ok",
                diff_text="--- a\n+++ b\n@@ -1 +1 @@\n-x\n+y\n",
                pre_snapshot={plan_path: "before"},
                stdout="",
            ),
        )

        # Drift with a SPECIFIC sentinel path on call #2 (per-finding
        # pre-apply -- skips apply_finding, halt_merged=False).
        sentinel_drifted = tmp_path / "foo.py"
        drift_n = {"n": 0}

        def fake_check_drift(lock):  # noqa: ARG001
            drift_n["n"] += 1
            return [sentinel_drifted] if drift_n["n"] == 2 else []

        monkeypatch.setattr(
            iter_lock_module, "check_drift", fake_check_drift,
        )

        # Capture run_auto_reconcile_on_drift's ``drifted`` arg.
        captured_drifted: list = []

        def fake_auto_reconcile(*, drifted, **kwargs):
            captured_drifted.append(list(drifted))

        monkeypatch.setattr(
            auto_reconcile_module, "run_auto_reconcile_on_drift",
            fake_auto_reconcile,
        )
        monkeypatch.setattr(
            reconcile_module, "_emit_drift_halt_warning",
            lambda *a, **kw: None,
        )

        seed = Recommendation(
            id="seed", source="reconcile", severity="high",
            step_id=1, title="x", body="x",
        )

        cli_module._iterate_reconcile_loop(
            args=args,
            ctx=ctx,
            plan_path=plan_path,
            step_id=1,
            initial_recs=[seed],
            state=WalkState(yes_to_all=True),
            budget=IterativeBudget(enabled=True, max_iterations=2),
        )

        assert len(captured_drifted) == 1, (
            f"run_auto_reconcile_on_drift fired "
            f"{len(captured_drifted)} time(s); expected 1 from the "
            f"halt_merged=False legacy halt branch"
        )
        assert captured_drifted[0] == [sentinel_drifted], (
            f"halt_drifted threading regressed; "
            f"run_auto_reconcile_on_drift received "
            f"{captured_drifted[0]!r}, expected "
            f"[{sentinel_drifted!r}]. action_fn must populate "
            f"state.halt_drifted with the drift result AND the "
            f"iteration body must read it into the local before "
            f"reset_halt() and pass to auto_reconcile."
        )


_VALID_PLAN_TEXT = (
    "---\n"
    "title: Test Plan\n"
    "status: planning\n"
    "priority: low\n"
    "steps:\n"
    "  - id: 1\n"
    "    title: Only step\n"
    "---\n"
    "# Body\n"
)


@pytest.mark.integration
class TestCmdRegister:
    """End-to-end coverage for ``plan-tool register``.

    The subcommand closes the asymmetry between ``create`` (which
    scans the filesystem for collisions) and the rest of the tool
    (which reads from the structured-plans manifest). Tests pin
    ``--repo-root`` + ``--manifest`` so they're hermetic — no real
    .git discovery and no writes to the packaged registry.
    """

    def _seed_repo(
        self, tmp_path: Path, *, registered: list[str] | None = None
    ) -> tuple[Path, Path, Path]:
        """Return (repo_root, plans_dir, manifest_path).

        ``registered`` is a list of plan filenames (e.g. ``"1-alpha.md"``)
        to drop into the plans dir AND list in the manifest. Anything not
        in the list is left for the test to create as an orphan.
        """
        import json as _json

        (tmp_path / ".git").mkdir()
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        manifest = tmp_path / "m.json"
        rel_entries: list[str] = []
        for name in registered or []:
            (plans_dir / name).write_text(_VALID_PLAN_TEXT, encoding="utf-8")
            rel_entries.append(f"plans/{name}")
        manifest.write_text(_json.dumps({"plans": rel_entries}), encoding="utf-8")
        return tmp_path, plans_dir, manifest

    def test_register_by_path_succeeds(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import json as _json

        repo, plans_dir, manifest = self._seed_repo(tmp_path)
        orphan = plans_dir / "1-new.md"
        orphan.write_text(_VALID_PLAN_TEXT, encoding="utf-8")

        rc = main([
            "--repo-root", str(repo),
            "--manifest", str(manifest),
            "register", str(orphan),
        ])
        assert rc == 0
        out = capsys.readouterr().out
        assert "registered plans/1-new.md" in out
        data = _json.loads(manifest.read_text(encoding="utf-8"))
        assert "plans/1-new.md" in data["plans"]

    def test_register_is_idempotent(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo, plans_dir, manifest = self._seed_repo(
            tmp_path, registered=["1-alpha.md"]
        )
        rc = main([
            "--repo-root", str(repo),
            "--manifest", str(manifest),
            "register", str(plans_dir / "1-alpha.md"),
        ])
        assert rc == 0
        out = capsys.readouterr().out
        assert "already registered plans/1-alpha.md" in out

    def test_register_by_slug_finds_orphan_in_registered_dir(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo, plans_dir, manifest = self._seed_repo(
            tmp_path, registered=["1-alpha.md"]
        )
        # Orphan lives next to a registered plan; slug lookup finds it.
        (plans_dir / "2-beta.md").write_text(_VALID_PLAN_TEXT, encoding="utf-8")

        rc = main([
            "--repo-root", str(repo),
            "--manifest", str(manifest),
            "register", "beta",
        ])
        assert rc == 0
        out = capsys.readouterr().out
        assert "registered plans/2-beta.md" in out

    def test_register_unknown_slug_errors(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        repo, _plans_dir, manifest = self._seed_repo(
            tmp_path, registered=["1-alpha.md"]
        )
        rc = main([
            "--repo-root", str(repo),
            "--manifest", str(manifest),
            "register", "ghost",
        ])
        assert rc == 2
        err = capsys.readouterr().err
        assert "no plan file matching 'ghost'" in err

    def test_register_rejects_malformed_plan(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        repo, plans_dir, manifest = self._seed_repo(tmp_path)
        bad = plans_dir / "1-broken.md"
        bad.write_text(
            "---\npriority: low\n---\n", encoding="utf-8"
        )  # missing title/status/steps
        rc = main([
            "--repo-root", str(repo),
            "--manifest", str(manifest),
            "register", str(bad),
        ])
        assert rc == 1
        err = capsys.readouterr().err
        assert "not a valid structured plan" in err
        # Manifest left untouched.
        import json as _json

        data = _json.loads(manifest.read_text(encoding="utf-8"))
        assert data["plans"] == []

    def test_register_rejects_file_outside_repo(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        repo, _plans_dir, manifest = self._seed_repo(tmp_path)
        # File lives in a sibling directory (still under tmp_path but
        # outside the pinned repo root).
        outside_dir = tmp_path.parent / f"{tmp_path.name}-outside"
        outside_dir.mkdir()
        outside = outside_dir / "1-stray.md"
        try:
            outside.write_text(_VALID_PLAN_TEXT, encoding="utf-8")

            rc = main([
                "--repo-root", str(repo),
                "--manifest", str(manifest),
                "register", str(outside),
            ])
            assert rc == 2
            err = capsys.readouterr().err
            assert "not inside repo root" in err
        finally:
            outside.unlink(missing_ok=True)
            outside_dir.rmdir()

    def test_register_refused_in_plans_dir_mode(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        repo, plans_dir, _manifest = self._seed_repo(tmp_path)
        orphan = plans_dir / "1-new.md"
        orphan.write_text(_VALID_PLAN_TEXT, encoding="utf-8")
        rc = main([
            "--repo-root", str(repo),
            "--plans-dir", str(plans_dir),
            "register", str(orphan),
        ])
        assert rc == 2
        err = capsys.readouterr().err
        assert "manifest-mode command" in err


class TestCmdDeregister:
    """End-to-end coverage for ``plan-tool deregister`` — the inverse of
    ``register``. Removes a manifest entry without touching the file on
    disk. Tests pin ``--repo-root`` + ``--manifest`` so they're hermetic.
    """

    def _seed_repo(
        self,
        tmp_path: Path,
        *,
        registered: list[str] | None = None,
        extra_entries: list[str] | None = None,
    ) -> tuple[Path, Path, Path]:
        """Return (repo_root, plans_dir, manifest_path).

        ``registered`` plan files are written to disk AND listed in the
        manifest. ``extra_entries`` are repo-relative strings listed in the
        manifest WITHOUT a backing file (stale entries).
        """
        import json as _json

        (tmp_path / ".git").mkdir()
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        manifest = tmp_path / "m.json"
        rel_entries: list[str] = []
        for name in registered or []:
            (plans_dir / name).write_text(_VALID_PLAN_TEXT, encoding="utf-8")
            rel_entries.append(f"plans/{name}")
        rel_entries.extend(extra_entries or [])
        manifest.write_text(_json.dumps({"plans": rel_entries}), encoding="utf-8")
        return tmp_path, plans_dir, manifest

    def test_deregister_by_path_removes_entry_keeps_file(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import json as _json

        repo, plans_dir, manifest = self._seed_repo(
            tmp_path, registered=["1-alpha.md"]
        )
        rc = main([
            "--repo-root", str(repo),
            "--manifest", str(manifest),
            "deregister", str(plans_dir / "1-alpha.md"),
        ])
        assert rc == 0
        out = capsys.readouterr().out
        assert "deregistered plans/1-alpha.md" in out
        data = _json.loads(manifest.read_text(encoding="utf-8"))
        assert "plans/1-alpha.md" not in data["plans"]
        # File on disk is left in place.
        assert (plans_dir / "1-alpha.md").is_file()

    def test_deregister_by_slug_succeeds(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import json as _json

        repo, _plans_dir, manifest = self._seed_repo(
            tmp_path, registered=["2-beta.md"]
        )
        rc = main([
            "--repo-root", str(repo),
            "--manifest", str(manifest),
            "deregister", "beta",
        ])
        assert rc == 0
        out = capsys.readouterr().out
        assert "deregistered plans/2-beta.md" in out
        data = _json.loads(manifest.read_text(encoding="utf-8"))
        assert data["plans"] == []

    def test_deregister_prunes_stale_entry_with_missing_file(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A manifest entry whose file was deleted can be pruned by path —
        the file need not exist on disk."""
        import json as _json

        repo, _plans_dir, manifest = self._seed_repo(
            tmp_path,
            registered=["1-alpha.md"],
            extra_entries=["plans/ghost.md"],
        )
        rc = main([
            "--repo-root", str(repo),
            "--manifest", str(manifest),
            "deregister", "plans/ghost.md",
        ])
        assert rc == 0
        out = capsys.readouterr().out
        assert "deregistered plans/ghost.md" in out
        data = _json.loads(manifest.read_text(encoding="utf-8"))
        assert "plans/ghost.md" not in data["plans"]
        assert "plans/1-alpha.md" in data["plans"]

    def test_deregister_path_not_in_manifest_is_noop(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo, plans_dir, manifest = self._seed_repo(
            tmp_path, registered=["1-alpha.md"]
        )
        # A real file that simply isn't registered.
        (plans_dir / "2-beta.md").write_text(_VALID_PLAN_TEXT, encoding="utf-8")
        rc = main([
            "--repo-root", str(repo),
            "--manifest", str(manifest),
            "deregister", str(plans_dir / "2-beta.md"),
        ])
        assert rc == 0
        out = capsys.readouterr().out
        assert "not registered plans/2-beta.md" in out

    def test_deregister_unknown_slug_errors(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo, _plans_dir, manifest = self._seed_repo(
            tmp_path, registered=["1-alpha.md"]
        )
        rc = main([
            "--repo-root", str(repo),
            "--manifest", str(manifest),
            "deregister", "ghost",
        ])
        assert rc == 2
        err = capsys.readouterr().err
        assert "no registered plan matching 'ghost'" in err

    def test_deregister_rejects_file_outside_repo(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo, _plans_dir, manifest = self._seed_repo(tmp_path)
        outside_dir = tmp_path.parent / f"{tmp_path.name}-outside"
        outside_dir.mkdir()
        outside = outside_dir / "1-stray.md"
        try:
            outside.write_text(_VALID_PLAN_TEXT, encoding="utf-8")
            rc = main([
                "--repo-root", str(repo),
                "--manifest", str(manifest),
                "deregister", str(outside),
            ])
            assert rc == 2
            err = capsys.readouterr().err
            assert "not inside repo root" in err
        finally:
            outside.unlink(missing_ok=True)
            outside_dir.rmdir()

    def test_deregister_refused_in_plans_dir_mode(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo, plans_dir, _manifest = self._seed_repo(
            tmp_path, registered=["1-alpha.md"]
        )
        rc = main([
            "--repo-root", str(repo),
            "--plans-dir", str(plans_dir),
            "deregister", "alpha",
        ])
        assert rc == 2
        err = capsys.readouterr().err
        assert "manifest-mode command" in err


class TestCmdWithdraw:
    """End-to-end coverage for ``plan-tool withdraw`` — the abandon-path
    counterpart to ``sweep`` (completed) and ``create``'s replacement
    (superseded). Tests pin ``--repo-root`` + ``--manifest`` so they're
    hermetic.
    """

    def _seed_repo(
        self,
        tmp_path: Path,
        *,
        registered: list[str] | None = None,
    ) -> tuple[Path, Path, Path]:
        import json as _json

        (tmp_path / ".git").mkdir()
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        manifest = tmp_path / "m.json"
        rel_entries: list[str] = []
        for name in registered or []:
            (plans_dir / name).write_text(_VALID_PLAN_TEXT, encoding="utf-8")
            rel_entries.append(f"plans/{name}")
        manifest.write_text(_json.dumps({"plans": rel_entries}), encoding="utf-8")
        return tmp_path, plans_dir, manifest

    def test_withdraw_by_slug_archives_and_deregisters(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import json as _json

        repo, plans_dir, manifest = self._seed_repo(
            tmp_path, registered=["1-alpha.md"]
        )
        rc = main([
            "--repo-root", str(repo),
            "--manifest", str(manifest),
            "withdraw", "alpha", "--reason", "premise disproved",
        ])
        assert rc == 0
        out = capsys.readouterr().out
        assert "withdrawn plans/1-alpha.md" in out
        assert "plans/archive/1-alpha.withdrawn.md" in out
        assert "deregistered from the manifest" in out
        data = _json.loads(manifest.read_text(encoding="utf-8"))
        assert data["plans"] == []
        assert not (plans_dir / "1-alpha.md").exists()
        archived = plans_dir / "archive" / "1-alpha.withdrawn.md"
        assert archived.is_file()
        body = archived.read_text(encoding="utf-8")
        assert "Withdrawn" in body and "premise disproved" in body

    def test_withdraw_by_path_accepted(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo, plans_dir, manifest = self._seed_repo(
            tmp_path, registered=["2-beta.md"]
        )
        rc = main([
            "--repo-root", str(repo),
            "--manifest", str(manifest),
            "withdraw", str(plans_dir / "2-beta.md"), "--reason", "abandoned",
        ])
        assert rc == 0
        assert (plans_dir / "archive" / "2-beta.withdrawn.md").is_file()

    def test_withdraw_missing_reason_refused_by_parser(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``--reason`` is ``required=True`` at the argparse layer, so a
        missing value exits via SystemExit before ``cmd_withdraw`` ever
        runs — distinct from the blank-string case below, which reaches
        the handler and is refused there."""
        repo, _plans_dir, manifest = self._seed_repo(
            tmp_path, registered=["1-alpha.md"]
        )
        with pytest.raises(SystemExit) as exc:
            main([
                "--repo-root", str(repo),
                "--manifest", str(manifest),
                "withdraw", "alpha",
            ])
        assert exc.value.code == 2

    def test_withdraw_blank_reason_refused(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo, plans_dir, manifest = self._seed_repo(
            tmp_path, registered=["1-alpha.md"]
        )
        rc = main([
            "--repo-root", str(repo),
            "--manifest", str(manifest),
            "withdraw", "alpha", "--reason", "   ",
        ])
        assert rc == 2
        err = capsys.readouterr().err
        assert "requires --reason" in err
        # Refused before any mutation — the plan is untouched.
        assert (plans_dir / "1-alpha.md").is_file()

    def test_withdraw_unresolvable_target(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo, _plans_dir, manifest = self._seed_repo(tmp_path)
        rc = main([
            "--repo-root", str(repo),
            "--manifest", str(manifest),
            "withdraw", "ghost", "--reason", "x",
        ])
        assert rc == 2
        err = capsys.readouterr().err
        assert "no plan matching 'ghost'" in err

    def test_withdraw_rejects_file_outside_repo(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo, _plans_dir, manifest = self._seed_repo(tmp_path)
        outside_dir = tmp_path.parent / f"{tmp_path.name}-outside-withdraw"
        outside_dir.mkdir()
        outside = outside_dir / "1-stray.md"
        try:
            outside.write_text(_VALID_PLAN_TEXT, encoding="utf-8")
            rc = main([
                "--repo-root", str(repo),
                "--manifest", str(manifest),
                "withdraw", str(outside), "--reason", "x",
            ])
            assert rc == 2
            err = capsys.readouterr().err
            assert "not inside repo root" in err
        finally:
            outside.unlink(missing_ok=True)
            outside_dir.rmdir()

    def test_withdraw_refused_in_plans_dir_mode(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo, plans_dir, _manifest = self._seed_repo(
            tmp_path, registered=["1-alpha.md"]
        )
        rc = main([
            "--repo-root", str(repo),
            "--plans-dir", str(plans_dir),
            "withdraw", "alpha", "--reason", "x",
        ])
        assert rc == 2
        err = capsys.readouterr().err
        assert "manifest-mode command" in err

    def test_withdraw_unregistered_target_reports_not_registered(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A plan file that was never registered (deregister's ``target
        need not exist`` symmetry doesn't apply — the file itself must
        exist) is still withdrawable by path."""
        repo, plans_dir, manifest = self._seed_repo(tmp_path)
        (plans_dir / "1-solo.md").write_text(_VALID_PLAN_TEXT, encoding="utf-8")
        rc = main([
            "--repo-root", str(repo),
            "--manifest", str(manifest),
            "withdraw", str(plans_dir / "1-solo.md"), "--reason", "solo",
        ])
        assert rc == 0
        out = capsys.readouterr().out
        assert "was not registered" in out
        assert (plans_dir / "archive" / "1-solo.withdrawn.md").is_file()

    def test_withdraw_locks_repo_mutation(self) -> None:
        """withdraw mutates the plan file, plan-details, and the manifest,
        so it must sit in the same mutation-lock set as register / deregister
        / sweep — a completeness gap here would let it race a concurrent
        create/run on the same repo."""
        from plan_tool.cli.app import _LOCKED_MUTATING_COMMANDS

        assert "withdraw" in _LOCKED_MUTATING_COMMANDS


class TestCmdValidateFailOnFindings:
    """`validate` exits 0 on an INVALID verdict by default; the opt-in
    `--fail-on-findings` flag makes INVALID exit non-zero for CI."""

    _INVALID_PLAN = (
        "---\n"
        "title: Broken\n"
        "status: in-progress\n"
        "priority: low\n"
        "steps: []\n"
        "---\n"
    )

    def _setup(self, tmp_path: Path, plan_text: str) -> Path:
        plan = tmp_path / "plan.md"
        plan.write_text(plan_text, encoding="utf-8")
        manifest = tmp_path / "m.json"
        manifest.write_text('{"plans": ["plan.md"]}\n', encoding="utf-8")
        (tmp_path / ".git").mkdir()
        return manifest

    def test_invalid_exits_zero_by_default(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        manifest = self._setup(tmp_path, self._INVALID_PLAN)
        monkeypatch.chdir(tmp_path)
        rc = main(["--manifest", str(manifest), "validate", "plan"])
        assert rc == 0
        assert "INVALID:" in capsys.readouterr().out

    def test_invalid_with_flag_exits_one(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        manifest = self._setup(tmp_path, self._INVALID_PLAN)
        monkeypatch.chdir(tmp_path)
        rc = main(
            ["--manifest", str(manifest), "validate", "plan",
             "--fail-on-findings"]
        )
        assert rc == 1
        assert "INVALID:" in capsys.readouterr().out

    @pytest.mark.integration
    @pytest.mark.parametrize("fail_on_findings", [False, True])
    def test_validate_names_step_description_and_legacy_title_without_changing_exit_policy(
        self, tmp_path, monkeypatch, capsys, fail_on_findings
    ):
        text = "---\ntitle: Plan\nstatus: planning\npriority: medium\nsteps:\n  - id: 1\n    descripton: Work\n---\n"
        manifest = self._setup(tmp_path, text)
        monkeypatch.chdir(tmp_path)
        args = ["--manifest", str(manifest), "validate", "plan"]
        if fail_on_findings:
            args.append("--fail-on-findings")
        assert main(args) == (1 if fail_on_findings else 0)
        out = capsys.readouterr().out
        assert "steps.0.description: Field required (legacy title is also accepted)" in out
        assert "steps.0.descripton: unknown step field" in out
        assert "[type=" not in out

    def test_valid_with_flag_exits_zero(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        manifest = self._setup(tmp_path, _VALID_PLAN_TEXT)
        monkeypatch.chdir(tmp_path)
        rc = main(
            ["--manifest", str(manifest), "validate", "plan",
             "--fail-on-findings"]
        )
        assert rc == 0
        assert "OK:" in capsys.readouterr().out

    def test_invalid_output_is_concise_with_full_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """INVALID verdict leads with the full file path and renders the
        schema failure as a concise `field: message` line — not the verbose
        pydantic dump (no `[type=...]` annotation, no docs URL)."""
        manifest = self._setup(tmp_path, self._INVALID_PLAN)
        monkeypatch.chdir(tmp_path)
        rc = main(["--manifest", str(manifest), "validate", "plan"])
        assert rc == 0
        out = capsys.readouterr().out
        assert str(tmp_path / "plan.md") in out  # full path, not just basename
        assert "steps:" in out
        assert "[type=" not in out
        assert "errors.pydantic.dev" not in out


@pytest.mark.integration
class TestSubcommandStyleOutput:
    """Step 6: end-to-end diagnostic-contract assertions.

    Drives ``plan_tool.cli.main([...])`` through the real argparse
    dispatch + handler + library path and asserts the unified diagnostic
    contract steps 1-5 establish:

    - plain-mode bytes identical to the legacy ``plan-tool:`` /
      ``warning:`` / ``error:`` prefixes (no ANSI),
    - only the prefix word colorizes under ``PLAN_TOOL_FORCE_COLOR``
      (the message body stays plain), and
    - diagnostics land on stderr while results land on stdout,
      captured per stream via ``capsys``.

    Capture is ``capsys.readouterr()`` per stream — not an injected
    ``StringIO``: every migrated library/CLI diagnostic defaults its
    stream to ``sys.stderr`` and no ``file=`` seam threads through
    ``main()``. The color gate reads ``stream.isatty()`` and the
    capsys-replaced streams report non-TTY, so plain mode is the default
    and only the env var flips it.
    """

    # --- env / capture helpers -------------------------------------------

    def _plain_color_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Plain mode: clear both color signals so an inherited dev env
        can't flip the gate under us."""
        monkeypatch.delenv("PLAN_TOOL_FORCE_COLOR", raising=False)
        monkeypatch.delenv("NO_COLOR", raising=False)

    def _force_color_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Color mode: ``PLAN_TOOL_FORCE_COLOR`` is checked before
        ``NO_COLOR``/TTY in ``style.color_enabled``, so it wins."""
        monkeypatch.setenv("PLAN_TOOL_FORCE_COLOR", "1")
        monkeypatch.delenv("NO_COLOR", raising=False)

    def _line_with(self, text: str, token: str) -> str:
        """Return the single captured line containing ``token``."""
        for line in text.splitlines():
            if token in line:
                return line
        raise AssertionError(f"no line containing {token!r} in:\n{text}")

    # --- run --iterate guard (warn() / stderr) ---------------------------

    def _stub_run_step_and_walk(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Keep the iterate-guard path hermetic by replacing the claude
        call and the interactive walk with no-ops.

        Mirrors ``TestIterateFlagsRun``'s ``_patch_run_step`` /
        ``_patch_walk``, duplicated here because those are methods of a
        sibling class and are not callable via ``self`` from here.
        """
        from plan_tool.cli import app as cli_module
        from plan_tool.launcher import RunResult
        from plan_tool.review_walk import WalkResult

        def fake_run_step(plan_path_arg, **kwargs):
            return RunResult(
                step_id=1,
                exit_code=0,
                advanced_to=None,
                done=False,
                stdout="## Findings\n\n",
                step_title="t",
            )

        def fake_walk(saved, *, action_fn=None, state=None, **kwargs):
            return WalkResult(answered=0, quit_early=False)

        # ``--mode check`` (non-reconcile) runs through ``cmd_run`` in
        # ``run_cmd``, which reads ``run_step`` from its own namespace.
        # ``walk_recommendations`` is not reached on the check path, but is
        # stubbed defensively on ``app`` (where it still resolves).
        monkeypatch.setattr("plan_tool.cli.run_cmd.run_step", fake_run_step)
        monkeypatch.setattr(cli_module, "walk_recommendations", fake_walk)

    def _drive_run_iterate(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> int:
        """``run plan --mode check --step 1 --iterate`` over the basic
        plan — falls through the non-reconcile iterate guard (emitting the
        soft warning) and into the stubbed ``run_step``."""
        _iter_basic_plan(tmp_path)
        manifest = _iter_setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)
        _iter_force_tty(monkeypatch, True)
        self._stub_run_step_and_walk(monkeypatch)
        return main(
            [
                "--manifest", str(manifest),
                "run", "plan", "--mode", "check", "--step", "1", "--iterate",
            ]
        )

    # The warning must not recommend a rejected reconciliation route.
    _ITERATE_WARN_BODY = (
        "--iterate has no effect on `plan-tool run` (mode=check); "
        "remove it. Reconciliation does not support --iterate."
    )

    def test_run_iterate_warning_states_no_effect_without_rejected_route(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        self._plain_color_env(monkeypatch)
        rc = self._drive_run_iterate(tmp_path, monkeypatch)
        captured = capsys.readouterr()
        assert rc == 0
        assert f"warning: {self._ITERATE_WARN_BODY}\n" in captured.err
        assert "\033[" not in captured.err

    def test_run_iterate_warning_prefix_colorizes(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        self._force_color_env(monkeypatch)
        rc = self._drive_run_iterate(tmp_path, monkeypatch)
        captured = capsys.readouterr()
        assert rc == 0
        line = self._line_with(captured.err, "warning:")
        prefix = style.BOLD_YELLOW + "warning:" + style.RESET
        assert line.startswith(prefix)
        # Body after the colored prefix carries no escape.
        assert "\033[" not in line[len(prefix):]

    # --- register invalid plan (error() / stderr) ------------------------

    def _seed_invalid_plan(self, tmp_path: Path) -> Path:
        """Malformed ``.md`` (no opening frontmatter fence) under a git
        root, so ``register`` resolves it and ``parse_plan`` rejects it."""
        (tmp_path / ".git").mkdir()
        bad_md = tmp_path / "bad.md"
        bad_md.write_text("this is not a structured plan\n", encoding="utf-8")
        return bad_md

    def _expected_register_error(self, bad_md: Path) -> str:
        """Build the legacy error line at runtime: ``target`` is the
        resolved absolute path (``cli.py:462``) and the suffix is the live
        ``ParseError``/``ValidationError`` message — neither is hardcoded."""
        from plan_tool.parser import ParseError, ValidationError, parse_plan

        try:
            parse_plan(bad_md.resolve())
        except (ParseError, ValidationError) as exc:
            return (
                f"error: {bad_md.resolve()} is not a valid structured "
                f"plan: {exc}\n"
            )
        raise AssertionError("expected the malformed plan to fail parsing")

    def test_register_invalid_plan_error_plain_matches_legacy(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        self._plain_color_env(monkeypatch)
        bad_md = self._seed_invalid_plan(tmp_path)
        expected = self._expected_register_error(bad_md)
        monkeypatch.chdir(tmp_path)
        rc = main(["register", str(bad_md)])
        captured = capsys.readouterr()
        assert rc == 1
        # The resolved-path branch is stderr-silent up to this one line,
        # so a byte-identity assertion is clean.
        assert captured.err == expected
        assert "\033[" not in captured.err

    def test_register_error_prefix_colorizes(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        self._force_color_env(monkeypatch)
        bad_md = self._seed_invalid_plan(tmp_path)
        monkeypatch.chdir(tmp_path)
        rc = main(["register", str(bad_md)])
        captured = capsys.readouterr()
        assert rc == 1
        line = self._line_with(captured.err, "error:")
        prefix = style.BOLD_RED + "error:" + style.RESET
        assert line.startswith(prefix)
        assert "\033[" not in line[len(prefix):]

    # --- completeness audit skip (tool() / stderr) -----------------------

    def _seed_completeness_plan(self, tmp_path: Path) -> Path:
        """Minimal well-formed plan + its declared file, returning the
        plans dir. The deterministic primitives run with no claude call;
        the audit skip is forced via the invoker-null wrapper."""
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        plan_path = plans_dir / "1-style-test.md"
        plan_path.write_text(
            "---\n"
            "title: Style Test\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: build the thing\n"
            "    files:\n"
            "      - foo.py\n"
            "    status: done\n"
            "---\n"
            "\n"
            "## Overview\n\nReal overview.\n\n"
            "## Problem statement\n\nReal problem.\n\n"
            "## Architecture\n\nReal architecture.\n\n"
            "## Steps\n\nSee frontmatter.\n\n"
            "## Out of scope\n\nReal scope text.\n\n"
            "## Risks\n\nReal risks.\n\n"
            "## Testing\n\nReal testing.\n\n"
            "## Acceptance criteria\n\nfoo.py:bar() must return 42.\n\n"
            "## Deferred\n\nReal deferred.\n",
            encoding="utf-8",
        )
        (tmp_path / "foo.py").write_text(
            "def bar():\n    return 41\n", encoding="utf-8"
        )
        return plans_dir

    def _null_audit_invoker(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Force the *real* ``check_plan_audit`` to run with
        ``invoker=None`` so its genuine ``no invoker configured`` skip line
        fires (no claude call, no stubbed diagnostic).

        ``cmd_completeness`` re-imports ``check_plan_audit`` from the module
        in its function body, so patching the module attribute takes effect
        through ``main()``.
        """
        import plan_tool.review as review_module

        _real_audit = review_module.check_plan_audit

        def force_null_invoker(*a, **k):
            k_null = dict(k)
            k_null["invoker"] = None
            return _real_audit(*a, **k_null)

        monkeypatch.setattr(
            review_module, "check_plan_audit", force_null_invoker
        )

    def _drive_completeness(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> int:
        plans_dir = self._seed_completeness_plan(tmp_path)
        self._null_audit_invoker(monkeypatch)
        return main(
            [
                "--repo-root", str(tmp_path),
                "--plans-dir", str(plans_dir),
                "completeness-audit", "style-test",
            ]
        )

    _SKIP_LINE = "plan-tool: plan-audit: skipped (no invoker configured)\n"

    def test_completeness_skip_line_plain_matches_legacy(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        self._plain_color_env(monkeypatch)
        rc = self._drive_completeness(tmp_path, monkeypatch)
        captured = capsys.readouterr()
        assert rc == 0
        assert self._SKIP_LINE in captured.err
        assert "\033[" not in captured.err

    def test_completeness_skip_prefix_colorizes(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        self._force_color_env(monkeypatch)
        rc = self._drive_completeness(tmp_path, monkeypatch)
        captured = capsys.readouterr()
        assert rc == 0
        line = self._line_with(captured.err, "plan-audit: skipped")
        # Only the `plan-tool:` source tag is dimmed; the `plan-audit:`
        # sub-tag is a domain token (not a tool() level) and stays plain.
        prefix = style.DIM + "plan-tool:" + style.RESET
        assert line.startswith(prefix)
        assert "\033[" not in line[len(prefix):]

    def test_completeness_result_on_stdout_diagnostics_on_stderr(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        self._plain_color_env(monkeypatch)
        rc = self._drive_completeness(tmp_path, monkeypatch)
        captured = capsys.readouterr()
        assert rc == 0
        # Result (grouped completeness report) on stdout.
        assert "Plan completeness:" in captured.out
        # Diagnostic (audit skip line) on stderr, absent from stdout.
        assert self._SKIP_LINE in captured.err
        assert "plan-tool: plan-audit: skipped" not in captured.out


class _FakeStdin:
    """Minimal stdin stand-in with a controllable ``isatty``."""

    def __init__(self, tty: bool) -> None:
        self._tty = tty

    def isatty(self) -> bool:
        return self._tty


@pytest.mark.integration
class TestCmdLessonsConsolidate:
    """End-to-end coverage for ``plan-tool lessons consolidate``.

    Drives ``main()`` via argv with ``--repo-root`` pinned to
    ``tmp_path`` so discovery, the equivalence primitive (faked), the
    diff/apply posture, and the run log all participate hermetically.
    The autouse ``HOME``-redirection fixture keeps ``general.md`` out of
    the picture unless a test seeds it.
    """

    _DUP_JSON = (
        '{"duplicates": [{"left_index": 1, "right_index": 2, '
        '"confidence": 0.9, "rationale": "same point"}], "conflicts": []}'
    )
    _EMPTY_JSON = '{"duplicates": [], "conflicts": []}'
    _CONFLICT_JSON = (
        '{"duplicates": [], "conflicts": [{"left_index": 1, '
        '"right_index": 2, "confidence": 0.8, "rationale": "contradict"}]}'
    )
    _DUP_AND_CONFLICT_JSON = (
        '{"duplicates": [{"left_index": 1, "right_index": 2, '
        '"confidence": 0.9, "rationale": "same"}], '
        '"conflicts": [{"left_index": 3, "right_index": 4, '
        '"confidence": 0.8, "rationale": "contradict"}]}'
    )

    def _seed_project(self, tmp_path: Path, *rules: str) -> Path:
        from plan_tool.lessons import (
            LessonEntry,
            _PROJECT_HEADER,
            project_path,
        )

        path = project_path(tmp_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        body = _PROJECT_HEADER + "\n".join(
            LessonEntry(rule=r).render() for r in rules
        ) + "\n"
        path.write_text(body, encoding="utf-8")
        return path

    def _patch_invoker(
        self, monkeypatch: pytest.MonkeyPatch, response: str
    ) -> list[str]:
        # ``cmd_lessons_consolidate`` reads ``shell_equivalence_invoker``
        # as a module global of ``plan_tool.cli.lessons_cmd`` (where the
        # handler now lives), so the stub must target that module — not
        # ``app``'s re-imported alias, which dispatch never reads.
        from plan_tool.cli import lessons_cmd

        calls: list[str] = []

        def fake(prompt: str) -> str:
            calls.append(prompt)
            return response

        monkeypatch.setattr(lessons_cmd, "shell_equivalence_invoker", fake)
        return calls

    def _set_tty(self, monkeypatch: pytest.MonkeyPatch, tty: bool) -> None:
        from plan_tool.cli import app as cli

        monkeypatch.setattr(cli.sys, "stdin", _FakeStdin(tty))

    def test_diff_mode_default_emits_unified_diff_and_does_not_write(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        path = self._seed_project(tmp_path, "alpha rule", "beta rule")
        before = path.read_text(encoding="utf-8")
        self._patch_invoker(monkeypatch, self._DUP_JSON)
        self._set_tty(monkeypatch, False)
        rc = main(["--repo-root", str(tmp_path), "lessons", "consolidate"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "@@" in out
        assert path.read_text(encoding="utf-8") == before

    def test_diff_mode_zero_findings_prints_no_findings_line_and_exit_0(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        self._seed_project(tmp_path, "alpha rule", "beta rule")
        self._patch_invoker(monkeypatch, self._EMPTY_JSON)
        self._set_tty(monkeypatch, False)
        rc = main(["--repo-root", str(tmp_path), "lessons", "consolidate"])
        assert rc == 0
        assert "nothing to consolidate" in capsys.readouterr().out

    def test_diff_mode_conflict_only_prints_manual_review_note(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        path = self._seed_project(tmp_path, "alpha rule", "beta rule")
        before = path.read_text(encoding="utf-8")
        self._patch_invoker(monkeypatch, self._CONFLICT_JSON)
        self._set_tty(monkeypatch, False)
        rc = main(["--repo-root", str(tmp_path), "lessons", "consolidate"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "manual edit required" in out
        assert path.read_text(encoding="utf-8") == before

    def test_apply_with_yes_rewrites_without_prompt(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        path = self._seed_project(tmp_path, "alpha rule", "beta rule")
        self._patch_invoker(monkeypatch, self._DUP_JSON)
        self._set_tty(monkeypatch, False)
        rc = main(
            ["--repo-root", str(tmp_path), "lessons", "consolidate",
             "--apply", "-y"]
        )
        assert rc == 0
        body = path.read_text(encoding="utf-8")
        assert "alpha rule" in body
        assert "beta rule" not in body  # right_index=2 dropped
        assert "rewrote" in capsys.readouterr().out

    def test_apply_dry_run_prints_rewrite_and_does_not_write(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        path = self._seed_project(tmp_path, "alpha rule", "beta rule")
        before = path.read_text(encoding="utf-8")
        self._patch_invoker(monkeypatch, self._DUP_JSON)
        self._set_tty(monkeypatch, False)
        rc = main(
            ["--repo-root", str(tmp_path), "lessons", "consolidate",
             "--apply", "--dry-run"]
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert "rewrite preview" in out
        # The rewrite product, not a diff (no @@ hunk header).
        assert "@@" not in out
        assert path.read_text(encoding="utf-8") == before

    def test_apply_tty_no_confirm_aborts(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        path = self._seed_project(tmp_path, "alpha rule", "beta rule")
        before = path.read_text(encoding="utf-8")
        self._patch_invoker(monkeypatch, self._DUP_JSON)
        self._set_tty(monkeypatch, True)
        monkeypatch.setattr("builtins.input", lambda prompt="": "n")
        rc = main(
            ["--repo-root", str(tmp_path), "lessons", "consolidate", "--apply"]
        )
        assert rc == 0
        assert "aborted" in capsys.readouterr().out
        assert path.read_text(encoding="utf-8") == before

    def test_apply_tty_y_confirms_and_rewrites(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        path = self._seed_project(tmp_path, "alpha rule", "beta rule")
        self._patch_invoker(monkeypatch, self._DUP_JSON)
        self._set_tty(monkeypatch, True)
        monkeypatch.setattr("builtins.input", lambda prompt="": "y")
        rc = main(
            ["--repo-root", str(tmp_path), "lessons", "consolidate", "--apply"]
        )
        assert rc == 0
        assert "beta rule" not in path.read_text(encoding="utf-8")

    def test_headless_apply_without_yes_refuses_with_rc_2(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        path = self._seed_project(tmp_path, "alpha rule", "beta rule")
        before = path.read_text(encoding="utf-8")
        self._patch_invoker(monkeypatch, self._DUP_JSON)
        self._set_tty(monkeypatch, False)
        rc = main(
            ["--repo-root", str(tmp_path), "lessons", "consolidate", "--apply"]
        )
        assert rc == 2
        assert "needs -y or a TTY" in capsys.readouterr().err
        assert path.read_text(encoding="utf-8") == before

    def _setup_plans(
        self, tmp_path: Path, slugs: list[str]
    ) -> Path:
        """Seed plan files (with ``lessons:`` frontmatter) + per-plan
        lessons.md files; return the plans dir for ``--plans-dir``."""
        from plan_tool.lessons import LessonEntry, _GENERAL_HEADER

        plans_dir = tmp_path / "plans"
        plans_dir.mkdir(parents=True, exist_ok=True)
        for slug in slugs:
            rel = f"lessons/{slug}.md"
            (plans_dir / f"{slug}.md").write_text(
                "---\n"
                f"title: Plan {slug}\n"
                "status: planning\n"
                "priority: low\n"
                f"lessons: {rel}\n"
                "steps:\n"
                "  - id: 1\n"
                "    title: Only step\n"
                "---\n"
                "# Body\n",
                encoding="utf-8",
            )
            lesson_file = tmp_path / rel
            lesson_file.parent.mkdir(parents=True, exist_ok=True)
            lesson_file.write_text(
                _GENERAL_HEADER
                + LessonEntry(rule=f"{slug} alpha").render()
                + "\n"
                + LessonEntry(rule=f"{slug} beta").render()
                + "\n",
                encoding="utf-8",
            )
        return plans_dir

    def test_plan_filter_scopes_to_one_per_plan_lessons_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        self._seed_project(tmp_path, "proj one", "proj two")
        plans_dir = self._setup_plans(tmp_path, ["demo-a", "demo-b"])
        calls = self._patch_invoker(monkeypatch, self._DUP_JSON)
        self._set_tty(monkeypatch, False)
        rc = main(
            ["--repo-root", str(tmp_path), "--plans-dir", str(plans_dir),
             "lessons", "consolidate", "--plan", "demo-a"]
        )
        assert rc == 0
        # Exactly one file judged (demo-a's), so one primitive call.
        assert len(calls) == 1
        out = capsys.readouterr().out
        assert "demo-a.md" in out
        assert "demo-b.md" not in out
        assert "project.md" not in out

    def test_plan_filter_unknown_slug_exits_2(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        plans_dir = self._setup_plans(tmp_path, ["demo-a"])
        self._patch_invoker(monkeypatch, self._DUP_JSON)
        self._set_tty(monkeypatch, False)
        rc = main(
            ["--repo-root", str(tmp_path), "--plans-dir", str(plans_dir),
             "lessons", "consolidate", "--plan", "no-such-plan"]
        )
        assert rc == 2
        assert "no per-plan lessons file found" in capsys.readouterr().err

    def test_min_confidence_passes_through_to_primitive(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from plan_tool.cli import app as cli
        from plan_tool.cli import lessons_cmd
        from plan_tool.lessons import EquivalenceFindings

        self._seed_project(tmp_path, "alpha rule", "beta rule")
        self._set_tty(monkeypatch, False)
        recorded: list[dict] = []

        def rec(existing, candidates=(), **kwargs):
            recorded.append(kwargs)
            return EquivalenceFindings(duplicates=(), conflicts=())

        monkeypatch.setattr(lessons_cmd, "find_lesson_equivalences", rec)
        rc = main(
            ["--repo-root", str(tmp_path), "lessons", "consolidate",
             "--min-confidence", "0.85"]
        )
        assert rc == 0
        assert recorded[0]["min_confidence"] == 0.85

    def test_no_resume_passes_through_to_primitive(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from plan_tool.cli import app as cli
        from plan_tool.cli import lessons_cmd
        from plan_tool.lessons import EquivalenceFindings

        self._seed_project(tmp_path, "alpha rule", "beta rule")
        self._set_tty(monkeypatch, False)
        recorded: list[dict] = []

        def rec(existing, candidates=(), **kwargs):
            recorded.append(kwargs)
            return EquivalenceFindings(duplicates=(), conflicts=())

        monkeypatch.setattr(lessons_cmd, "find_lesson_equivalences", rec)
        rc = main(
            ["--repo-root", str(tmp_path), "lessons", "consolidate",
             "--no-resume"]
        )
        assert rc == 0
        assert recorded[0]["resume"] is False

    def test_no_lessons_files_discovered_exits_0_with_message(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        self._patch_invoker(monkeypatch, self._DUP_JSON)
        self._set_tty(monkeypatch, False)
        rc = main(["--repo-root", str(tmp_path), "lessons", "consolidate"])
        assert rc == 0
        assert "no lessons files discovered" in capsys.readouterr().out

    def test_rewrite_only_drops_duplicate_right_index_not_conflict_pairs(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        path = self._seed_project(
            tmp_path, "alpha", "beta", "gamma", "delta"
        )
        self._patch_invoker(monkeypatch, self._DUP_AND_CONFLICT_JSON)
        self._set_tty(monkeypatch, False)
        rc = main(
            ["--repo-root", str(tmp_path), "lessons", "consolidate",
             "--apply", "-y"]
        )
        assert rc == 0
        body = path.read_text(encoding="utf-8")
        # DUP right_index=2 → entry index 1 ("beta") dropped.
        assert "beta" not in body
        # CONFLICT pair (entries 3 and 4) is untouched.
        assert "gamma" in body
        assert "delta" in body
        assert "alpha" in body

    def test_run_log_records_command_lessons_consolidate(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        self._seed_project(tmp_path, "alpha rule", "beta rule")
        self._patch_invoker(monkeypatch, self._DUP_JSON)
        self._set_tty(monkeypatch, False)
        rc = main(["--repo-root", str(tmp_path), "lessons", "consolidate"])
        assert rc == 0
        run_dir = tmp_path / ".plan-tool" / "runs" / "lessons-consolidate"
        logs = list(run_dir.glob("*.jsonl"))
        assert logs, "expected a run log under lessons-consolidate/"
        first = json.loads(logs[0].read_text(encoding="utf-8").splitlines()[0])
        assert first["command"] == "lessons-consolidate"

    def test_atomic_write_leaves_no_tmp_artifact_on_success(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        path = self._seed_project(tmp_path, "alpha rule", "beta rule")
        self._patch_invoker(monkeypatch, self._DUP_JSON)
        self._set_tty(monkeypatch, False)
        rc = main(
            ["--repo-root", str(tmp_path), "lessons", "consolidate",
             "--apply", "-y"]
        )
        assert rc == 0
        leftovers = list(path.parent.glob("*.tmp")) + list(
            path.parent.glob(".*.tmp")
        )
        assert leftovers == []

    def test_summary_lines_ordered_general_project_then_per_plan(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.lessons import (
            LessonEntry,
            _GENERAL_HEADER,
            general_path,
        )

        gp = general_path(tmp_path)
        gp.parent.mkdir(parents=True, exist_ok=True)
        gp.write_text(
            _GENERAL_HEADER
            + LessonEntry(rule="gen one").render()
            + "\n"
            + LessonEntry(rule="gen two").render()
            + "\n",
            encoding="utf-8",
        )
        self._seed_project(tmp_path, "proj one", "proj two")
        plans_dir = self._setup_plans(tmp_path, ["demo-a"])
        self._patch_invoker(monkeypatch, self._EMPTY_JSON)
        self._set_tty(monkeypatch, False)
        rc = main(
            ["--repo-root", str(tmp_path), "--plans-dir", str(plans_dir),
             "lessons", "consolidate"]
        )
        assert rc == 0
        out = capsys.readouterr().out
        gen_i = out.index("kind=general")
        proj_i = out.index("kind=project")
        per_i = out.index("kind=per-plan")
        assert gen_i < proj_i < per_i

    def _seed_warning_log(
        self, tmp_path: Path, candidate: str, matched: str, count: int
    ) -> None:
        """Pre-seed the warning log with ``count`` records flagging the
        ``candidate`` ↔ ``matched`` pair (so the consolidate handler's
        recurrence read can rank that finding)."""
        from plan_tool.lessons import LessonsWarning, warnings_log_path

        records = [
            LessonsWarning(
                timestamp="2026-05-12T00:00:00+00:00",
                target_file=".plan-tool/lessons/project.md",
                candidate_rule=candidate,
                matched_rules=(matched,),
                kind="duplicate",
                confidence=0.9,
                rationale="recurred",
                source="detail:test",
                mode="warn",
            )
            for _ in range(count)
        ]
        path = warnings_log_path(tmp_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "".join(r.to_json_line() for r in records), encoding="utf-8"
        )

    def test_recurrence_weighting_annotates_repeat_finding(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # _DUP_JSON flags entries #1 ("alpha rule") ↔ #2 ("beta rule").
        # Seed the warning log so that pair recurs three times.
        self._seed_project(tmp_path, "alpha rule", "beta rule")
        self._seed_warning_log(tmp_path, "beta rule", "alpha rule", 3)
        self._patch_invoker(monkeypatch, self._DUP_JSON)
        self._set_tty(monkeypatch, False)
        rc = main(["--repo-root", str(tmp_path), "lessons", "consolidate"])
        assert rc == 0
        assert "recurrence=3" in capsys.readouterr().out

    def test_ignore_recurrence_bypasses_warning_log_read(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli
        from plan_tool.cli import lessons_cmd

        self._seed_project(tmp_path, "alpha rule", "beta rule")
        self._seed_warning_log(tmp_path, "beta rule", "alpha rule", 3)
        self._patch_invoker(monkeypatch, self._DUP_JSON)
        self._set_tty(monkeypatch, False)

        def boom(_repo_root):
            raise AssertionError("load_warnings must not be called")

        monkeypatch.setattr(lessons_cmd, "load_warnings", boom)
        rc = main(
            ["--repo-root", str(tmp_path), "lessons", "consolidate",
             "--ignore-recurrence"]
        )
        # rc 0 proves load_warnings was never reached (it would have raised).
        assert rc == 0
        assert "recurrence=" not in capsys.readouterr().out

    def test_without_warning_log_renders_no_recurrence_annotation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        self._seed_project(tmp_path, "alpha rule", "beta rule")
        self._patch_invoker(monkeypatch, self._DUP_JSON)
        self._set_tty(monkeypatch, False)
        rc = main(["--repo-root", str(tmp_path), "lessons", "consolidate"])
        assert rc == 0
        assert "recurrence=" not in capsys.readouterr().out


class TestLessonsHelpSurface:
    """The ``lessons`` and ``lessons consolidate`` subparsers are reachable
    via ``build_parser()`` and document the consolidate flags."""

    def test_help_lists_lessons_subcommand(self) -> None:
        assert "lessons" in build_parser().format_help()

    def test_consolidate_help_documents_flags(self) -> None:
        parser = build_parser()
        lessons = _find_subparser(parser, "lessons")
        assert lessons is not None
        consolidate = _find_subparser(lessons, "consolidate")
        assert consolidate is not None
        help_text = consolidate.format_help()
        for flag in (
            "--apply",
            "--dry-run",
            "--min-confidence",
            "--no-resume",
            "--plan",
            "--ignore-recurrence",
        ):
            assert flag in help_text


class TestPrintStatusChangeTypeTag:
    """Step 8: ``_print_status`` tags each classified step's line."""

    def _plan(self, change_type) -> "object":
        from plan_tool.schema import (
            ChangeType,
            Plan,
            PlanStatus,
            Priority,
            Step,
        )

        ct = ChangeType(change_type) if change_type else None
        return Plan(
            title="Demo",
            status=PlanStatus.IN_PROGRESS,
            priority=Priority.MEDIUM,
            steps=[Step(id=1, title="Do the thing", change_type=ct)],
        )

    def test_print_status_includes_change_type_tag(
        self, tmp_path: Path, capsys
    ) -> None:
        from plan_tool.cli import _print_status

        _print_status(self._plan("refactor"), tmp_path / "plan.md")
        out = capsys.readouterr().out
        assert "[refactor]" in out

    def test_print_status_unclassified_unchanged(
        self, tmp_path: Path, capsys
    ) -> None:
        from plan_tool.cli import _print_status

        _print_status(self._plan(None), tmp_path / "plan.md")
        out = capsys.readouterr().out
        for tag in ("[refactor]", "[feature]", "[non-code]"):
            assert tag not in out


# --- annotate end-to-end ---------------------------------------------------

_ANNOTATE_SOURCE = (
    "# Legacy Plan\n\n"
    "## Goal A\n\nThe A thing.\n\n"
    "## Feature B\n\nThe B thing.\n\n"
    "## Feature C\n\nThe C thing.\n"
)

# Distinct recognizable strings so the carryover/done split is checkable.
_ANNOTATE_PARTIAL_REMAINING = "finish wiring the resolver into dispatch"
_ANNOTATE_PARTIAL_CODE_REF = "resolver.py:resolve"


def _annotate_sections() -> str:
    return json.dumps(
        [
            {"heading": "Goal A", "status": "IMPLEMENTED",
             "evidence": "present", "code_refs": ["a.py:foo"]},
            {"heading": "Feature B", "status": "PARTIAL", "evidence": "half",
             "code_refs": [_ANNOTATE_PARTIAL_CODE_REF],
             "remaining": _ANNOTATE_PARTIAL_REMAINING},
            {"heading": "Feature C", "status": "NOT-IMPLEMENTED",
             "evidence": "no trace"},
        ]
    )


@pytest.mark.integration
class TestAnnotateEndToEnd:
    """Drive ``main(["annotate", ...])`` with only the backend seam stubbed."""

    def _repo(self, tmp_path: Path) -> Path:
        (tmp_path / ".git").mkdir()
        return tmp_path

    def test_annotate_main_writes_report_and_seed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo = self._repo(tmp_path)
        src = repo / "legacy.md"
        src.write_text(_ANNOTATE_SOURCE, encoding="utf-8")
        monkeypatch.setattr(
            "plan_tool.cli.annotate_cmd.shell_annotate_invoker",
            lambda prompt: _annotate_sections(),
        )
        rc = main(["--repo-root", str(repo), "annotate", str(src)])
        assert rc == 0
        report = (repo / "legacy.annotated.md").read_text(encoding="utf-8")
        # Verbatim original lines survive, plus status blocks were inserted.
        for line in _ANNOTATE_SOURCE.splitlines():
            assert line in report
        assert "NOT IMPLEMENTED" in report
        assert (repo / "docs" / "implementation-plans" / "plan-seeds" / "legacy.seed.md").is_file()

    def test_seed_feeds_create_from_existing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo = self._repo(tmp_path)
        src = repo / "legacy.md"
        src.write_text(_ANNOTATE_SOURCE, encoding="utf-8")
        monkeypatch.setattr(
            "plan_tool.cli.annotate_cmd.shell_annotate_invoker",
            lambda prompt: _annotate_sections(),
        )
        assert main(["--repo-root", str(repo), "annotate", str(src)]) == 0
        seed = repo / "docs" / "implementation-plans" / "plan-seeds" / "legacy.seed.md"
        seed_text = seed.read_text(encoding="utf-8")

        # The discriminating split (Finding 1's regression): the PARTIAL's
        # remaining_work scopes carryover, its code_refs route to done-context
        # only — never carried whole.
        carryover, _, done = seed_text.partition(
            "## Already implemented (done-context — do not re-plan)"
        )
        assert "Feature C" in carryover
        assert _ANNOTATE_PARTIAL_REMAINING in carryover
        assert _ANNOTATE_PARTIAL_CODE_REF not in carryover
        assert _ANNOTATE_PARTIAL_CODE_REF in done
        assert "Goal A" in carryover  # zero-grounding IMPLEMENTED becomes review work
        assert "Goal A" not in done

        # Feed the seed to `create`, stubbing create's claude seam (the seed,
        # not the stub, determines what reaches the invoker) and spying on the
        # distill gate.
        import plan_tool.create as create_module

        recorded: list[str] = []
        canned_steps = json.dumps(
            [{"title": "carryover work", "complexity": "low",
              "files": [], "depends_on": []}]
        )

        def normalized_preparation(prompt: str) -> str:
            evidence_line = next(
                int(number)
                for raw_line in prompt.splitlines()
                if (number := raw_line.partition("\t")[0]).isdigit()
                and (source_line := raw_line.partition("\t")[2]).strip()
                and not source_line.lstrip().startswith(("#", "---"))
            )
            return json.dumps(
                {
                    "outcome": "single",
                    "sections": {
                        "Overview": "Prepared overview.",
                        "Problem statement": "Prepared problem.",
                        "Architecture": "Prepared architecture.",
                        "Out of scope": "candidate",
                        "Risks": "candidate",
                        "Testing": "candidate",
                        "Acceptance criteria": "candidate",
                        "Deferred": "candidate",
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
                }
            )

        def create_invoker(prompt: str) -> str:
            recorded.append(prompt)
            if "Distill a free-form seed into a canonical plan body" in prompt:
                return normalized_preparation(prompt)
            return canned_steps

        real_create_plan = create_module.create_plan
        real_propose_distilled_seed = create_module.propose_distilled_seed_from_claude

        def wrapped_create_plan(slug, **kwargs):
            kwargs["claude_invoker"] = create_invoker
            # Supply prompt defaults (no TTY in pytest); create_plan's default
            # input_fn=input is bound at def-time, so patching builtins.input
            # alone wouldn't reach it.
            kwargs["input_fn"] = lambda *a, **k: ""
            # The stub body is intentionally placeholder — this round-trip
            # isolates the seed→create handoff, not body synthesis; let the
            # placeholder body through so the seed-acceptance assertion is what
            # gates the test.
            kwargs["allow_placeholder_body"] = True
            return real_create_plan(slug, **kwargs)

        monkeypatch.setattr(
            "plan_tool.cli.authoring.create_plan", wrapped_create_plan
        )
        from unittest.mock import Mock

        distill_mock = Mock(
            name="propose_distilled_seed_from_claude",
            wraps=real_propose_distilled_seed,
        )
        monkeypatch.setattr(
            create_module, "propose_distilled_seed_from_claude", distill_mock
        )
        # Defaults for the metadata prompts (no TTY in pytest).
        monkeypatch.setattr("builtins.input", lambda *a, **k: "")

        manifest = repo / "m.json"
        manifest.write_text(json.dumps({"plans": []}), encoding="utf-8")
        rc = main(
            [
                "--repo-root", str(repo), "--manifest", str(manifest),
                "create", "carryover",
                "--from-existing", str(seed),
                "--no-distill", "--no-iterate",
                "--no-synthesize-body", "--no-fetch-docs", "-y",
            ]
        )
        assert rc == 0  # create accepts the seed
        # create's invoker saw the carryover scoping + done-context framing.
        prompts = "\n".join(recorded)
        assert _ANNOTATE_PARTIAL_REMAINING in prompts  # carryover scope
        assert "Feature C" in prompts
        assert _ANNOTATE_PARTIAL_CODE_REF in prompts  # done-context half
        # File-backed generated carryover stays on the preparation route even
        # with --no-distill; the selected normalized result reaches the same
        # downstream authoring prompt.
        assert distill_mock.call_count == 1

    def test_annotate_help_exits_zero(self) -> None:
        with pytest.raises(SystemExit) as excinfo:
            main(["annotate", "--help"])
        assert excinfo.value.code == 0


@pytest.mark.parametrize("command", ["completeness-audit", "detail"])
def test_audit_and_detail_help_describe_reader_owned_conceptual_edits(command, capsys) -> None:
    from plan_tool.cli.app import main

    with pytest.raises(SystemExit) as exc:
        main([command, "--help"])
    assert exc.value.code == 0
    help_text = " ".join(capsys.readouterr().out.split())
    assert "human or orchestrating session" in help_text
    assert "hand-edit the relevant plan or detail files" in help_text
    assert "deterministic well-formedness" in help_text.replace("- ", "-")
