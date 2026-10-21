"""Focused tests for top-level ``plan_tool.cli.main`` app wiring."""

from __future__ import annotations

import pytest

import plan_tool.cli as cli
from plan_tool.claude_errors import (
    OnRateLimitAction,
    OnRateLimitPolicy,
    get_default_on_rate_limit_policy,
    set_default_on_rate_limit_policy,
)


@pytest.fixture(autouse=True)
def _restore_on_rate_limit_policy(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("PLAN_TOOL_BACKEND", raising=False)
    original = get_default_on_rate_limit_policy()
    yield
    set_default_on_rate_limit_policy(original)


def test_on_rate_limit_defaults_to_wait(
    tmp_repo, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("PLAN_TOOL_ON_RATE_LIMIT", raising=False)
    monkeypatch.delenv("PLAN_TOOL_FALLBACK_BACKEND", raising=False)

    assert cli.main(tmp_repo.argv("list")) == 0

    assert get_default_on_rate_limit_policy() == OnRateLimitPolicy(
        action=OnRateLimitAction.WAIT
    )


def test_on_rate_limit_flag_sets_policy(
    tmp_repo, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PLAN_TOOL_ON_RATE_LIMIT", "wait")
    monkeypatch.setenv("PLAN_TOOL_FALLBACK_BACKEND", "cursor")

    assert (
        cli.main(
            tmp_repo.argv(
                "--on-rate-limit",
                "switch",
                "--fallback-backend",
                "codex",
                "list",
            )
        )
        == 0
    )

    assert get_default_on_rate_limit_policy() == OnRateLimitPolicy(
        action=OnRateLimitAction.SWITCH,
        fallback_backend="codex",
    )


def test_on_rate_limit_env_sets_policy(
    tmp_repo, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PLAN_TOOL_ON_RATE_LIMIT", "ask")
    monkeypatch.setenv("PLAN_TOOL_FALLBACK_BACKEND", "codex")

    assert cli.main(tmp_repo.argv("list")) == 0

    assert get_default_on_rate_limit_policy() == OnRateLimitPolicy(
        action=OnRateLimitAction.ASK,
        fallback_backend="codex",
    )


def test_no_wait_on_rate_limit_maps_to_stop_and_beats_env(
    tmp_repo, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PLAN_TOOL_ON_RATE_LIMIT", "wait")

    assert cli.main(tmp_repo.argv("--no-wait-on-rate-limit", "list")) == 0

    assert get_default_on_rate_limit_policy() == OnRateLimitPolicy(
        action=OnRateLimitAction.STOP
    )


def test_no_wait_on_rate_limit_conflicts_with_on_rate_limit(
    tmp_repo, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("PLAN_TOOL_ON_RATE_LIMIT", raising=False)

    with pytest.raises(SystemExit) as excinfo:
        cli.main(
            tmp_repo.argv(
                "--no-wait-on-rate-limit",
                "--on-rate-limit",
                "wait",
                "list",
            )
        )

    assert excinfo.value.code == 2


def test_on_rate_limit_switch_requires_fallback(
    tmp_repo, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("PLAN_TOOL_ON_RATE_LIMIT", raising=False)
    monkeypatch.delenv("PLAN_TOOL_FALLBACK_BACKEND", raising=False)

    with pytest.raises(SystemExit) as excinfo:
        cli.main(tmp_repo.argv("--on-rate-limit", "switch", "list"))

    assert excinfo.value.code == 2


def test_invalid_on_rate_limit_env_returns_usage_error(
    tmp_repo, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PLAN_TOOL_ON_RATE_LIMIT", "hibernate")

    with pytest.raises(SystemExit) as excinfo:
        cli.main(tmp_repo.argv("list"))

    assert excinfo.value.code == 2


@pytest.mark.parametrize(
    "command",
    [
        ("status", "broken"),
        ("detail", "broken"),
        ("completeness-audit", "broken"),
        ("run", "broken", "--all", "--dry-run"),
    ],
)
def test_unsupported_plan_format_version_has_a_supporting_build_direction(
    tmp_repo, capsys: pytest.CaptureFixture[str], command: tuple[str, ...]
) -> None:
    """A plan declaring an unsupported format_version must reach the
    operator as a named, actionable refusal — not a generic unknown-field
    parse error, and not a raw traceback — with the only real direction
    being a build that supports the declared version (this one can't
    safely read or upgrade it, so no in-build command is offered)."""
    bad = tmp_repo.plans_dir / "2-broken.md"
    bad.write_text(
        "---\n"
        "title: Newer plan\n"
        "status: planning\n"
        "priority: low\n"
        "format_version: 999\n"
        "steps:\n"
        "  - id: 1\n"
        "    title: One\n"
        "---\n"
        "# Body\n",
        encoding="utf-8",
    )
    tmp_repo.plans.append(bad)
    tmp_repo.write_manifest()

    rc = cli.main(tmp_repo.argv(*command))

    err = capsys.readouterr().err
    assert rc == 1
    assert "999" in err
    assert "a plan-tool build that supports this format_version" in err
    assert "Traceback" not in err
    assert "plan-tool validate" not in err
    assert "plan-tool list" not in err


def test_unmatched_fence_is_reported_as_a_known_command_error(
    tmp_repo, capsys: pytest.CaptureFixture[str]
) -> None:
    plan_path = tmp_repo.add_plan("1-demo", title="Demo")
    plan_path.write_text(
        plan_path.read_text(encoding="utf-8") + "\n```\n",
        encoding="utf-8",
    )
    tmp_repo.write_manifest()

    assert cli.main(tmp_repo.argv("detail", "demo")) == 2
    err = capsys.readouterr().err
    assert "unmatched opening code fence" in err
    assert "Traceback" not in err


def test_detail_format_error_is_reported_as_a_known_command_error(
    tmp_repo, capsys: pytest.CaptureFixture[str]
) -> None:
    """A ``DetailFormatError`` that no command-specific wrapper converts
    (here, ``split-criteria``, which has no broad ``except`` around its
    detail read) still reaches ``main()``'s typed handler — printing the
    declared-and-supported diagnosis plus forced-regeneration recovery,
    never a raw traceback."""
    from plan_tool.detail_artifacts import render_detail_format_version_marker

    plan_path = tmp_repo.add_plan("1-demo", title="Demo")
    detail_dir = tmp_repo.plans_dir / "plan-details" / "demo"
    detail_dir.mkdir(parents=True)
    (detail_dir / "01-only-step.md").write_text(
        f"# Only step\n{render_detail_format_version_marker(999)}\n\nfine.\n",
        encoding="utf-8",
    )
    tmp_repo.write_manifest()

    assert cli.main(tmp_repo.argv("split-criteria", "demo")) == 1
    err = capsys.readouterr().err
    assert "999" in err
    assert "--recover-refused" in err
    assert "Traceback" not in err


def test_roadmap_resolver_defect_emits_status_before_crash_persistence(
    tmp_repo, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from plan_tool.cli import roadmap_cmd

    monkeypatch.setattr(
        roadmap_cmd,
        "_resolve_cmd_repo_root",
        lambda _args: (_ for _ in ()).throw(RuntimeError("resolver defect")),
    )

    assert cli.main(tmp_repo.argv("roadmap", "demo")) == 1

    captured = capsys.readouterr()
    assert "note: roadmap demo: unexpected-error" in captured.err
    assert "unexpected error: RuntimeError: resolver defect" in captured.err
    assert list((tmp_repo.root / ".plan-tool" / "crashes").glob("*demo*"))
