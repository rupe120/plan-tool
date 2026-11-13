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


@pytest.fixture
def project_models(tmp_repo, monkeypatch):
    import json
    import shutil
    from plan_tool import model_specs
    from plan_tool.backend import get_active_backend, set_active_backend

    original = get_active_backend()
    monkeypatch.setattr(model_specs, "fetch_catalog", lambda **kw: pytest.fail("unexpected catalog access"))
    monkeypatch.setattr(shutil, "which", lambda binary: f"/fake/{binary}")
    path = tmp_repo.root / ".plan-tool" / "backends.json"
    path.parent.mkdir(exist_ok=True)
    payload = {
        "default_backend": "codex",
        "backends": {
            "codex": {"model": "base-codex", "commands": {
                "list": {"model": "list-codex"},
                "create": {"model": "create-codex"},
                "detail": {"model": "detail-codex"},
                "run": {"model": "run-codex"},
                "reconcile-plan": {"model": "reconcile-codex"},
                "completeness-audit": {"model": "nested-codex"},
            }},
            "claude": {"model": "base-claude", "commands": {
                "list": {"model": "list-claude"},
            }},
        },
    }
    path.write_text(json.dumps(payload))
    yield path, payload
    set_active_backend(original)


@pytest.mark.integration
@pytest.mark.parametrize("flags,environment,backend,model", [
    ([], None, "codex", "list-codex"),
    ([], "claude", "claude", "list-claude"),
    (["--backend", "claude"], "codex", "claude", "list-claude"),
    (["--model", "claude-sonnet-4-5"], "codex", "claude", "claude-sonnet-4-5"),
    (["--model", "opaque"], None, "codex", "opaque"),
    (["--backend", "claude", "--model", "gpt-5.6-terra"], None, "claude", "gpt-5.6-terra"),
])
def test_project_selection_preserves_explicit_override_authority(
    tmp_repo, project_models, monkeypatch, flags, environment, backend, model,
):
    from plan_tool.backend import get_active_backend

    if environment:
        monkeypatch.setenv("PLAN_TOOL_BACKEND", environment)
    assert cli.main(tmp_repo.argv(*flags, "list")) == 0
    active = get_active_backend()
    assert active.name == backend
    assert model in active.streaming_argv("prompt")


@pytest.mark.integration
@pytest.mark.parametrize("route", ["flag", "environment", "ancestor"])
def test_project_selection_uses_resolved_repository_without_cross_invocation_leakage(
    tmp_repo, project_models, monkeypatch, route,
):
    from plan_tool.backend import get_active_backend

    child = tmp_repo.root / "child"
    child.mkdir()
    monkeypatch.chdir(child)
    if route == "environment":
        monkeypatch.setenv("PLAN_TOOL_REPO_ROOT", str(tmp_repo.root))
    argv = tmp_repo.argv("list") if route == "flag" else ["list"]
    assert cli.main(argv) == 0
    assert "list-codex" in get_active_backend().streaming_argv("P")
    project_models[0].unlink()
    assert cli.main(argv) == 0
    assert get_active_backend().name == "claude"
    assert "list-codex" not in get_active_backend().streaming_argv("P")


@pytest.mark.integration
@pytest.mark.parametrize("field,value", [
    ("default_backend", None), ("default_backend", ""),
    ("backends", {"codex": {"commands": {"typo-command": {"model": "x"}}}}),
    ("backends", {"codex": {"commands": {"detail": {"model": 123}}}}),
])
def test_invalid_project_selection_returns_usage_error_before_dispatch(
    tmp_repo, project_models, field, value,
):
    import json

    path, payload = project_models
    payload[field] = value
    path.write_text(json.dumps(payload))
    assert cli.main(tmp_repo.argv("list")) == 2


@pytest.mark.integration
@pytest.mark.parametrize("backend,flags,expected", [
    ("claude", [], 127), ("codex", [], 127),
    ("codex", ["--model", "claude-sonnet-4-5"], 0),
])
def test_project_defaults_preflight_but_model_only_claude_stays_lazy(
    tmp_repo, project_models, monkeypatch, backend, flags, expected,
):
    import json
    import shutil
    from plan_tool.cli.app import EXEC_NOT_FOUND_EXIT

    path, payload = project_models
    payload["default_backend"] = backend
    path.write_text(json.dumps(payload))
    monkeypatch.setattr(shutil, "which", lambda binary: None)
    assert cli.main(tmp_repo.argv(*flags, "list")) == (
        EXEC_NOT_FOUND_EXIT if expected == 127 else expected
    )


@pytest.mark.integration
@pytest.mark.parametrize("default_backend", ["Codex", " codex "])
def test_mixed_case_default_backend_does_not_raise_a_spurious_model_hint(
    tmp_repo, project_models, monkeypatch, capsys, default_backend,
):
    """A model family that infers the project's own backend changed nothing,
    so the 'remove or change --model' hint must not appear (case/space-blind)."""
    import json
    import shutil
    from plan_tool.cli.app import EXEC_NOT_FOUND_EXIT

    path, payload = project_models
    payload["default_backend"] = default_backend
    path.write_text(json.dumps(payload))
    monkeypatch.setattr(shutil, "which", lambda binary: None)
    assert cli.main(tmp_repo.argv("--model", "gpt-5.6-terra", "list")) == EXEC_NOT_FOUND_EXIT
    err = capsys.readouterr().err
    assert "backend selected but its 'codex' executable was not found" in err
    assert "remove or change --model" not in err


@pytest.mark.integration
def test_create_and_detail_inherit_distinct_project_models_with_fake_invokers(
    tmp_repo, project_models, monkeypatch,
):
    import json
    from plan_tool import create, detail
    from plan_tool.backend import get_active_backend

    observed = []

    def create_invoke(prompt, **kwargs):
        active = get_active_backend()
        observed.append((active.name, active.streaming_argv("P")))
        if prompt.startswith("# Distill"):
            sections = {key: "Explain project usage." for key in (
                "Overview", "Problem statement", "Architecture", "Testing",
                "Out of scope", "Risks", "Acceptance criteria", "Deferred",
            )}
            return 0, json.dumps({
                "outcome": "single", "sections": sections,
                "evidence_spans": {key: [{"start_line": 1, "end_line": 1}]
                                   for key in ("Out of scope", "Risks", "Testing",
                                               "Acceptance criteria", "Deferred")},
            })
        if "synthes" in prompt.lower() and '"Overview"' in prompt:
            return 0, json.dumps({key: "Explain project usage." for key in (
                "Overview", "Problem statement", "Architecture", "Testing",
                "Out of scope", "Risks", "Acceptance criteria", "Deferred",
            )})
        if "reference" in prompt.lower() and "url" in prompt.lower():
            return 0, json.dumps([{
                "title": "Python docs", "url": "https://docs.python.org/3/",
                "description": "Usage guide reference",
            }])
        return 0, json.dumps([{
            "title": "Write guide", "intent": "Explain project usage",
            "complexity": "low", "files": [], "depends_on": [],
            "change_type": "non-code",
        }])

    def detail_invoke(prompt, **kwargs):
        active = get_active_backend()
        observed.append((active.name, active.streaming_argv("P")))
        return 0, "# Write guide\n\n" + "\n\n".join(
            f"## {heading}\n\nExplain project usage."
            for heading in ("Summary", "Table of Contents", "Why", "Files",
                            "Implementation", "Tests", "Acceptance criteria")
        ) + '\n\n<!-- plan-tool-detail-deferrals\n{"deferrals": []}\n-->'

    monkeypatch.setattr(create, "claude_invoke", create_invoke)
    monkeypatch.setattr(detail, "claude_invoke", detail_invoke)
    assert cli.main(tmp_repo.argv(
        "create", "project-proof", "--from", "Write a usage guide", "--yes",
        "--no-iterate", "--no-fetch-docs",
    )) == 0
    assert observed and all(name == "codex" and "create-codex" in argv
                            for name, argv in observed)
    observed.clear()
    assert cli.main(tmp_repo.argv("detail", "project-proof")) == 0
    assert observed and all(name == "codex" and "detail-codex" in argv
                            for name, argv in observed)
    assert list(tmp_repo.root.rglob("*write-guide.md"))


@pytest.mark.integration
@pytest.mark.parametrize("command,model", [
    (("run", "demo", "--mode", "check", "--dry-run"), "run-codex"),
    (("detail", "demo", "--reconcile", "--step", "1"), "detail-codex"),
    (("review", "demo", "--dry-run"), "reconcile-codex"),
])
def test_modes_and_aliases_keep_parent_command_model(
    tmp_repo, project_models, monkeypatch, command, model,
):
    from plan_tool.backend import get_active_backend

    from plan_tool import launcher
    from plan_tool.launcher import ClaudeRunStats

    calls = []

    def review_invoke(prompt, **kwargs):
        calls.append(get_active_backend().streaming_argv("P"))
        return 0, "No findings.", "", ClaudeRunStats()

    monkeypatch.setattr(launcher, "_run_streaming_once", review_invoke)
    tmp_repo.add_plan("1-demo")
    tmp_repo.write_manifest()
    assert cli.main(tmp_repo.argv(*command)) == 0
    if "--reconcile" in command:
        assert calls and all(model in argv for argv in calls)
    assert model in get_active_backend().streaming_argv("P")


@pytest.mark.integration
def test_configured_provisional_model_skips_catalog_discovery_and_keeps_warnings(
    tmp_repo, project_models, monkeypatch, capsys,
):
    import json
    from plan_tool import model_specs
    from plan_tool.backend import get_active_backend

    path, payload = project_models
    payload["default_backend"] = "gemini"
    payload["backends"]["gemini"] = {"commands": {"list": {"model": "opaque"}}}
    payload["backends"]["typo"] = {"model": "unused"}
    path.write_text(json.dumps(payload))
    monkeypatch.setattr(model_specs, "fetch_catalog", lambda **kw: pytest.fail("configured model needs no catalog"))
    assert cli.main(tmp_repo.argv("list")) == 0
    assert "opaque" in get_active_backend().streaming_argv("P")
    err = capsys.readouterr().err
    assert "provisional" in err
    assert "unknown backend 'typo'" in err


@pytest.mark.integration
def test_sequential_repository_invocations_keep_models_isolated(
    tmp_repo, project_models, tmp_path,
):
    import json
    from plan_tool.backend import get_active_backend

    second = tmp_path / "second-project"
    settings = second / ".plan-tool"
    settings.mkdir(parents=True)
    (settings / "backends.json").write_text(json.dumps({
        "default_backend": "claude",
        "backends": {"claude": {"commands": {"list": {"model": "second-model"}}}},
    }))
    for root, model in ((tmp_repo.root, "list-codex"), (second, "second-model"),
                        (tmp_repo.root, "list-codex")):
        assert cli.main(["--repo-root", str(root), "list"]) == 0
        assert model in get_active_backend().streaming_argv("P")


@pytest.mark.integration
def test_project_model_family_never_selects_a_different_backend(
    tmp_repo, project_models,
):
    import json
    from plan_tool.backend import get_active_backend

    path, payload = project_models
    payload["default_backend"] = "claude"
    payload["backends"]["claude"]["commands"]["list"]["model"] = "gpt-5.6-terra"
    path.write_text(json.dumps(payload))
    assert cli.main(tmp_repo.argv("list")) == 0
    assert get_active_backend().name == "claude"
    assert "gpt-5.6-terra" in get_active_backend().streaming_argv("P")
