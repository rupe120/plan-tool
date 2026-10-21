"""Characterization tests for the JIRA command seams in ``plan_tool.cli``.

Pins the epic-resolution / assignment helpers and the ``jira config``
wizard sub-flows so the "split cli.py into an intent-grouped package"
refactor can relocate them without changing what they resolve, persist, or
print. Per ``tests/cli/COVERAGE_BASELINE.md`` these symbols are
``indirectly covered`` only — the legacy ``test_jira.py`` drives them
transitively through ``main(["jira", …])`` but never names them, so a
direct unit test is the gap this module fills. ``plan_tool.jira_config`` is
the domain module; its own parsing/round-trip is covered by
``test_jira_config.py`` and not re-tested here.

Split-proof conventions (see ``test_package_surface.py``): every cli symbol
is imported from ``plan_tool.cli`` and called directly; config files are
written through the public ``plan_tool.jira_config`` writer. Interactive
flows are scripted by patching ``builtins.input`` / ``sys.stdin.isatty``
(process-level seams), never a ``plan_tool.cli`` module global.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable, Optional

import pytest

from plan_tool.cli import (
    _assign_epic_for_plan,
    _assign_plan_tag_for_plan,
    _dedupe_plan_tag,
    _print_jira_config,
    _resolve_epic_for_plan,
    _resolve_plan_tag_for_plan,
    _wizard_add_epic,
    _wizard_assign_plan,
    _wizard_edit_epic,
    _wizard_remove_epic,
    _wizard_resolve_plan_rel,
    _wizard_unassign_plan,
)
from plan_tool.jira import (
    JiraPublicationResult,
    Story,
    _render_story_json,
    _render_story_markdown,
    _StoryRenderInput,
    derive_jira_output_path,
    derive_plan_tag_acronym,
)

from plan_tool.jira_config import (
    Epic,
    JiraConfig,
    JiraConfigError,
    default_config_path,
    load_jira_config,
    plan_rel_path,
    validate_plan_tag,
    write_jira_config,
)


def _format_markdown(
    plan_title: str,
    stories: list[Story],
    *,
    epic: Epic,
    step_detail_map: Optional[dict[int, str]] = None,
    plan_tag: str = "",
) -> str:
    """Test-local stand-in for the retired public ``format_markdown``
    wrapper: exercises the same still-live ``_render_story_markdown`` /
    ``_StoryRenderInput`` boundary the companion pipeline also renders
    through, without a public library surface no production code calls."""
    return _render_story_markdown(
        _StoryRenderInput(
            plan_title=plan_title,
            epic=epic,
            new_stories=stories,
            detail_map=step_detail_map or {},
            plan_tag=plan_tag,
        )
    )


def _format_json(
    plan_title: str,
    stories: list[Story],
    *,
    epic: Epic,
    step_detail_map: Optional[dict[int, str]] = None,
    plan_tag: str = "",
) -> str:
    """Test-local stand-in for the retired public ``format_json`` wrapper
    — see :func:`_format_markdown`."""
    return _render_story_json(
        _StoryRenderInput(
            plan_title=plan_title,
            epic=epic,
            new_stories=stories,
            detail_map=step_detail_map or {},
            plan_tag=plan_tag,
        )
    )


def _script_stdin(
    monkeypatch: pytest.MonkeyPatch,
    responses: Iterable[str],
    *,
    tty: bool = True,
) -> None:
    """Feed ``responses`` to successive ``input()`` calls; set ``isatty``."""
    it = iter(responses)
    monkeypatch.setattr("builtins.input", lambda *_a, **_k: next(it))
    monkeypatch.setattr(sys.stdin, "isatty", lambda: tty)


def _write_config(repo_root: Path, config: JiraConfig) -> Path:
    path = default_config_path(repo_root)
    write_jira_config(config, path)
    return path


def _make_plan(repo_root: Path, stem: str = "1-demo") -> Path:
    plan = repo_root / "docs" / "plans" / f"{stem}.md"
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text(
        "---\n"
        "title: Demo\n"
        "status: in-progress\n"
        "priority: medium\n"
        "steps:\n"
        "  - id: 1\n"
        "    title: First\n"
        "    files: [parser.py]\n"
        "    status: current\n"
        "---\n"
        "# Demo\n",
        encoding="utf-8",
    )
    return plan


def _write_manifest(repo_root: Path, plan: Path) -> Path:
    manifest = repo_root / "plans.json"
    rel = plan.relative_to(repo_root).as_posix()
    manifest.write_text(f'{{"plans": ["{rel}"]}}\n', encoding="utf-8")
    return manifest


def _lint_story(
    *,
    ac: list[str],
    id: str = "AUTH-S1",
    layer: str = "unspecified",
    ui_impact: str = "",
    frontend_test_recommendation: list[str] | None = None,
    estimate_hours: int = 4,
) -> Story:
    # Default at the 4h floor so the advisory story-size lint doesn't perturb
    # tests that aren't about size; the size lint has its own test below.
    return Story(
        id=id,
        title="Add behavior",
        description="Ship observable behavior.",
        acceptance_criteria=ac,
        files=["parser.py"],
        steps=[1],
        depends_on=[],
        estimate_hours=estimate_hours,
        layer=layer,
        ui_impact=ui_impact,
        frontend_test_recommendation=list(frontend_test_recommendation or []),
    )


class TestCmdJiraLint:
    def test_lint_input_flags_existing_markdown(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module

        (tmp_path / ".git").mkdir()
        path = tmp_path / "jira-stories.md"
        path.write_text(
            _format_markdown(
                "Demo",
                [_lint_story(ac=["Code is clean"])],
                epic=Epic(key="AUTH", name="Auth"),
            )
            + "\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(["jira", "--lint", "--input", str(path)])

        assert rc == 1
        captured = capsys.readouterr()
        assert "vague phrasing" in captured.err
        assert "jira lint found" in captured.err

    def test_lint_input_passes_existing_json(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module

        (tmp_path / ".git").mkdir()
        path = tmp_path / "jira-stories.json"
        path.write_text(
            _format_json(
                "Demo",
                [_lint_story(ac=["GET /foo returns 200 with a cursor field"])],
                epic=Epic(key="AUTH", name="Auth"),
            )
            + "\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(["jira", "--lint", "--input", str(path)])

        assert rc == 0
        assert "jira lint passed: 1 story" in capsys.readouterr().out

    def test_lint_plan_uses_existing_artifact_without_epic_assignment(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module

        (tmp_path / ".git").mkdir()
        plan = _make_plan(tmp_path)
        manifest = _write_manifest(tmp_path, plan)
        target = (
            tmp_path
            / "docs"
            / "plans"
            / "plan-details"
            / "demo"
            / "jira-stories.md"
        )
        target.parent.mkdir(parents=True)
        target.write_text(
            _format_markdown(
                "Demo",
                [_lint_story(ac=["Code is clean"])],
                epic=Epic(key="AUTH", name="Auth"),
            )
            + "\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(
            ["--manifest", str(manifest), "jira", "--lint", "demo"]
        )

        assert rc == 1
        assert "vague phrasing" in capsys.readouterr().err
        assert not default_config_path(tmp_path).exists()

    def test_lint_plan_without_existing_artifact_does_not_generate(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module

        (tmp_path / ".git").mkdir()
        plan = _make_plan(tmp_path)
        manifest = _write_manifest(tmp_path, plan)

        def fake_export(path: Path, **kwargs) -> JiraPublicationResult:
            raise AssertionError("jira --lint must not invoke export_jira")

        monkeypatch.setattr("plan_tool.cli.jira_cmd.export_jira", fake_export)
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(["--manifest", str(manifest), "jira", "--lint", "demo"])

        assert rc == 2
        assert "jira lint artifact does not exist" in capsys.readouterr().err
        assert not default_config_path(tmp_path).exists()

    def test_lint_rejects_plan_and_input_together(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module

        (tmp_path / ".git").mkdir()
        path = tmp_path / "jira-stories.md"
        path.write_text("", encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(["jira", "--lint", "demo", "--input", str(path)])

        assert rc == 2
        assert "either a plan name or --input" in capsys.readouterr().err

    def test_lint_flags_missing_ui_impact_from_json(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module

        (tmp_path / ".git").mkdir()
        path = tmp_path / "jira-stories.json"
        path.write_text(
            _format_json(
                "Demo",
                [
                    _lint_story(
                        ac=["GET /foo returns 200 with a cursor field"],
                        layer="backend",
                        ui_impact="",
                    )
                ],
                epic=Epic(key="AUTH", name="Auth"),
            )
            + "\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(["jira", "--lint", "--input", str(path)])

        # Layer metadata is advisory (never blocks the export write), so
        # --lint surfaces the warning but does not fail — otherwise a freshly
        # written export would fail its own lint. Only AC lint blocks (rc 1).
        assert rc == 0
        captured = capsys.readouterr()
        assert "UI-impact note" in captured.err
        assert "advisory warning" in captured.out

    def test_lint_flags_missing_test_rec_from_json(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module

        (tmp_path / ".git").mkdir()
        path = tmp_path / "jira-stories.json"
        path.write_text(
            _format_json(
                "Demo",
                [
                    _lint_story(
                        ac=["GET /foo returns 200 with a cursor field"],
                        layer="frontend",
                        frontend_test_recommendation=[],
                    )
                ],
                epic=Epic(key="AUTH", name="Auth"),
            )
            + "\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(["jira", "--lint", "--input", str(path)])

        # Layer metadata is advisory: --lint surfaces the warning at rc 0.
        assert rc == 0
        captured = capsys.readouterr()
        assert "test recommendation" in captured.err
        assert "advisory warning" in captured.out

    def test_lint_flags_undersized_story_from_json(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module

        (tmp_path / ".git").mkdir()
        path = tmp_path / "jira-stories.json"
        path.write_text(
            _format_json(
                "Demo",
                [
                    _lint_story(
                        ac=["GET /foo returns 200 with a cursor field"],
                        estimate_hours=2,
                    )
                ],
                epic=Epic(key="AUTH", name="Auth"),
            )
            + "\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(["jira", "--lint", "--input", str(path)])

        # The size floor is advisory: --lint surfaces the warning at rc 0.
        assert rc == 0
        captured = capsys.readouterr()
        assert "soft decomposition floor" in captured.err
        assert "advisory warning" in captured.out

    def test_lint_passes_complete_layer_metadata(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module

        (tmp_path / ".git").mkdir()
        path = tmp_path / "jira-stories.json"
        path.write_text(
            _format_json(
                "Demo",
                [
                    _lint_story(
                        ac=["GET /foo returns 200 with a cursor field"],
                        layer="frontend",
                        ui_impact="renders a new balance row on the summary card",
                        frontend_test_recommendation=[
                            "Add a component test asserting the balance row "
                            "renders when the account has a balance",
                        ],
                    ),
                    _lint_story(
                        id="AUTH-S2",
                        ac=["POST /bar returns 201 with a `location` header"],
                        layer="backend",
                        ui_impact="none",
                    ),
                ],
                epic=Epic(key="AUTH", name="Auth"),
            )
            + "\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(["jira", "--lint", "--input", str(path)])

        assert rc == 0
        assert "jira lint passed: 2 stories" in capsys.readouterr().out

    def test_lint_ac_finding_blocks_even_with_layer_warning(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # A blocking AC finding still fails --lint (rc 1) even when an
        # advisory layer warning is also present — the advisory class must
        # not mask the blocking class.
        from plan_tool.cli import app as cli_module

        (tmp_path / ".git").mkdir()
        path = tmp_path / "jira-stories.json"
        path.write_text(
            _format_json(
                "Demo",
                [
                    _lint_story(
                        ac=["Code is clean"],
                        layer="backend",
                        ui_impact="",
                    )
                ],
                epic=Epic(key="AUTH", name="Auth"),
            )
            + "\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(["jira", "--lint", "--input", str(path)])

        assert rc == 1
        captured = capsys.readouterr()
        assert "acceptance-criteria" in captured.err
        # The layer warning is still surfaced alongside the blocking failure.
        assert "UI-impact note" in captured.err


class TestResolveEpicForPlan:
    def test_absent_config_returns_none(self, tmp_path: Path) -> None:
        plan = _make_plan(tmp_path)
        assert _resolve_epic_for_plan(tmp_path, plan) is None

    def test_plan_outside_repo_returns_none(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        outside = tmp_path / "elsewhere.md"
        outside.write_text("x", encoding="utf-8")
        assert _resolve_epic_for_plan(repo, outside) is None

    def test_unassigned_plan_returns_none(self, tmp_path: Path) -> None:
        plan = _make_plan(tmp_path)
        _write_config(tmp_path, JiraConfig(epics=[Epic(key="AUTH", name="Auth")]))
        assert _resolve_epic_for_plan(tmp_path, plan) is None

    def test_assigned_plan_returns_epic(self, tmp_path: Path) -> None:
        plan = _make_plan(tmp_path)
        rel = plan_rel_path(plan, tmp_path)
        assert rel is not None
        _write_config(
            tmp_path,
            JiraConfig(
                epics=[Epic(key="AUTH", name="Auth")],
                plan_assignments={rel: "AUTH"},
            ),
        )
        epic = _resolve_epic_for_plan(tmp_path, plan)
        assert epic is not None and epic.key == "AUTH"


class TestAssignEpicForPlan:
    def test_plan_outside_repo_returns_none(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        outside = tmp_path / "elsewhere.md"
        outside.write_text("x", encoding="utf-8")
        assert _assign_epic_for_plan(repo, outside) is None
        assert "not under repo root" in capsys.readouterr().err

    def test_no_epics_with_requested_key_errors(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        plan = _make_plan(tmp_path)
        assert _assign_epic_for_plan(tmp_path, plan, requested_key="AUTH") is None
        assert "no epics defined" in capsys.readouterr().err

    def test_no_epics_non_tty_errors(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        plan = _make_plan(tmp_path)
        monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
        assert _assign_epic_for_plan(tmp_path, plan) is None
        assert "no epics defined" in capsys.readouterr().err

    def test_no_epics_tty_inline_create_persists(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan = _make_plan(tmp_path)
        rel = plan_rel_path(plan, tmp_path)
        # accept the "create a new epic?" offer, then key/name/id/desc.
        _script_stdin(monkeypatch, ["y", "AUTH", "Authentication", "", ""])
        epic = _assign_epic_for_plan(tmp_path, plan)
        assert epic is not None and epic.key == "AUTH"
        reloaded = load_jira_config(tmp_path)
        assert reloaded.epic_for_plan(rel) is not None
        assert reloaded.epic_for_plan(rel).key == "AUTH"

    def test_no_epics_tty_inline_create_collision_returns_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan = _make_plan(tmp_path)
        # accept the offer, then key/name/jira-id that collides with key/desc.
        _script_stdin(
            monkeypatch, ["y", "AUTH", "Authentication", "AUTH-1234", ""]
        )
        assert _assign_epic_for_plan(tmp_path, plan) is None
        assert not default_config_path(tmp_path).is_file()

    def test_no_epics_tty_decline_returns_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan = _make_plan(tmp_path)
        _script_stdin(monkeypatch, ["n"])
        assert _assign_epic_for_plan(tmp_path, plan) is None
        assert not default_config_path(tmp_path).is_file()

    def test_requested_key_match_persists(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan = _make_plan(tmp_path)
        rel = plan_rel_path(plan, tmp_path)
        _write_config(tmp_path, JiraConfig(epics=[Epic(key="AUTH", name="Auth")]))
        # No prompts needed; lowercase request is normalized to the key.
        epic = _assign_epic_for_plan(tmp_path, plan, requested_key="auth")
        assert epic is not None and epic.key == "AUTH"
        assert load_jira_config(tmp_path).plan_assignments[rel] == "AUTH"

    def test_requested_key_no_match_errors(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        plan = _make_plan(tmp_path)
        _write_config(tmp_path, JiraConfig(epics=[Epic(key="AUTH", name="Auth")]))
        assert _assign_epic_for_plan(tmp_path, plan, requested_key="ZZZ") is None
        assert "does not match" in capsys.readouterr().err

    def test_non_tty_without_key_errors(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        plan = _make_plan(tmp_path)
        _write_config(tmp_path, JiraConfig(epics=[Epic(key="AUTH", name="Auth")]))
        monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
        assert _assign_epic_for_plan(tmp_path, plan) is None
        assert "not a TTY" in capsys.readouterr().err

    def test_tty_select_existing_key_persists(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan = _make_plan(tmp_path)
        rel = plan_rel_path(plan, tmp_path)
        _write_config(tmp_path, JiraConfig(epics=[Epic(key="AUTH", name="Auth")]))
        _script_stdin(monkeypatch, ["AUTH"])
        epic = _assign_epic_for_plan(tmp_path, plan)
        assert epic is not None and epic.key == "AUTH"
        assert load_jira_config(tmp_path).plan_assignments[rel] == "AUTH"

    def test_tty_empty_selection_returns_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan = _make_plan(tmp_path)
        _write_config(tmp_path, JiraConfig(epics=[Epic(key="AUTH", name="Auth")]))
        _script_stdin(monkeypatch, [""])
        assert _assign_epic_for_plan(tmp_path, plan) is None

    def test_tty_new_inline_epic_appends(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan = _make_plan(tmp_path)
        rel = plan_rel_path(plan, tmp_path)
        _write_config(tmp_path, JiraConfig(epics=[Epic(key="AUTH", name="Auth")]))
        # Select "new", then key/name/id/desc for the inline epic.
        _script_stdin(monkeypatch, ["new", "PAY", "Payments", "", ""])
        epic = _assign_epic_for_plan(tmp_path, plan)
        assert epic is not None and epic.key == "PAY"
        reloaded = load_jira_config(tmp_path)
        assert {e.key for e in reloaded.epics} == {"AUTH", "PAY"}
        assert reloaded.plan_assignments[rel] == "PAY"

    def test_tty_unknown_key_returns_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan = _make_plan(tmp_path)
        _write_config(tmp_path, JiraConfig(epics=[Epic(key="AUTH", name="Auth")]))
        _script_stdin(monkeypatch, ["ZZZ"])
        assert _assign_epic_for_plan(tmp_path, plan) is None


class TestDedupePlanTag:
    def test_no_collision_returns_candidate(self) -> None:
        assert _dedupe_plan_tag("DCL", set()) == "DCL"
        assert _dedupe_plan_tag("DCL", {"OTHER"}) == "DCL"

    def test_collision_appends_numeric_suffix(self) -> None:
        assert _dedupe_plan_tag("DCL", {"DCL"}) == "DCL2"

    def test_collision_skips_taken_suffixes(self) -> None:
        assert _dedupe_plan_tag("DCL", {"DCL", "DCL2", "DCL3"}) == "DCL4"

    def test_empty_candidate_returned_unchanged(self) -> None:
        # Nothing to derive from — a numeric suffix on "" would fabricate
        # a misleading tag, so the collision logic is skipped entirely.
        assert _dedupe_plan_tag("", {""}) == ""


class TestResolvePlanTagForPlan:
    def test_absent_config_returns_none(self, tmp_path: Path) -> None:
        plan = _make_plan(tmp_path)
        assert _resolve_plan_tag_for_plan(tmp_path, plan) is None

    def test_plan_outside_repo_returns_none(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        outside = tmp_path / "elsewhere.md"
        outside.write_text("x", encoding="utf-8")
        assert _resolve_plan_tag_for_plan(repo, outside) is None

    def test_untagged_plan_returns_none(self, tmp_path: Path) -> None:
        plan = _make_plan(tmp_path)
        _write_config(tmp_path, JiraConfig(epics=[Epic(key="AUTH", name="Auth")]))
        assert _resolve_plan_tag_for_plan(tmp_path, plan) is None

    def test_tagged_plan_returns_tag(self, tmp_path: Path) -> None:
        plan = _make_plan(tmp_path)
        rel = plan_rel_path(plan, tmp_path)
        assert rel is not None
        _write_config(tmp_path, JiraConfig(plan_tags={rel: "DEMO"}))
        assert _resolve_plan_tag_for_plan(tmp_path, plan) == "DEMO"


class TestAssignPlanTagForPlan:
    def test_plan_outside_repo_returns_none(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        outside = tmp_path / "elsewhere.md"
        outside.write_text("x", encoding="utf-8")
        assert _assign_plan_tag_for_plan(repo, outside) is None
        assert "not under repo root" in capsys.readouterr().err

    def test_requested_tag_persists_verbatim(self, tmp_path: Path) -> None:
        plan = _make_plan(tmp_path)
        rel = plan_rel_path(plan, tmp_path)
        tag = _assign_plan_tag_for_plan(
            tmp_path, plan, requested_tag="custom-tag"
        )
        assert tag == "custom-tag"
        assert load_jira_config(tmp_path).plan_tags[rel] == "custom-tag"

    def test_requested_tag_invalid_raises(self, tmp_path: Path) -> None:
        plan = _make_plan(tmp_path)
        with pytest.raises(JiraConfigError, match="invalid plan tag"):
            _assign_plan_tag_for_plan(tmp_path, plan, requested_tag="has a space")
        assert not default_config_path(tmp_path).is_file()

    def test_non_tty_auto_derives_and_persists_silently(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan = _make_plan(tmp_path)
        rel = plan_rel_path(plan, tmp_path)
        monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
        tag = _assign_plan_tag_for_plan(tmp_path, plan)
        assert tag == "DEMO"
        assert load_jira_config(tmp_path).plan_tags[rel] == "DEMO"

    def test_tty_auto_accept_flag_skips_prompt(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan = _make_plan(tmp_path)
        monkeypatch.setattr(sys.stdin, "isatty", lambda: True)

        def _boom(*_a: object, **_k: object) -> str:
            raise AssertionError("input() should not be called with auto_accept")

        monkeypatch.setattr("builtins.input", _boom)
        tag = _assign_plan_tag_for_plan(tmp_path, plan, auto_accept=True)
        assert tag == "DEMO"

    def test_tty_empty_response_accepts_default(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan = _make_plan(tmp_path)
        _script_stdin(monkeypatch, [""])
        assert _assign_plan_tag_for_plan(tmp_path, plan) == "DEMO"

    def test_tty_typed_response_overrides_default(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan = _make_plan(tmp_path)
        rel = plan_rel_path(plan, tmp_path)
        _script_stdin(monkeypatch, ["mytag"])
        tag = _assign_plan_tag_for_plan(tmp_path, plan)
        assert tag == "mytag"
        assert load_jira_config(tmp_path).plan_tags[rel] == "mytag"

    def test_tty_invalid_typed_response_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan = _make_plan(tmp_path)
        _script_stdin(monkeypatch, ["has a space"])
        with pytest.raises(JiraConfigError, match="invalid plan tag"):
            _assign_plan_tag_for_plan(tmp_path, plan)

    def test_tty_cancel_returns_none_without_persisting(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan = _make_plan(tmp_path)
        monkeypatch.setattr(sys.stdin, "isatty", lambda: True)

        def _raise_ctrl_c(*_a: object, **_k: object) -> str:
            raise KeyboardInterrupt

        monkeypatch.setattr("builtins.input", _raise_ctrl_c)
        assert _assign_plan_tag_for_plan(tmp_path, plan) is None
        assert not default_config_path(tmp_path).is_file()

    def test_dedupes_against_existing_tags(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A later plan whose derived acronym collides with an
        already-tagged plan gets a numeric-suffixed default instead of
        silently sharing the same grouping tag."""
        monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
        plan_a = _make_plan(tmp_path, stem="1-demo")
        assert _assign_plan_tag_for_plan(tmp_path, plan_a) == "DEMO"

        # Crafted so its four-word acronym also derives to "DEMO".
        plan_b = _make_plan(tmp_path, stem="2-decompose-export-merge-output")
        rel_b = plan_rel_path(plan_b, tmp_path)
        tag_b = _assign_plan_tag_for_plan(tmp_path, plan_b)
        assert tag_b == "DEMO2"
        assert load_jira_config(tmp_path).plan_tags[rel_b] == "DEMO2"


class TestDerivePlanTagAcronym:
    def test_multi_word_slug_takes_first_letters(self) -> None:
        assert (
            derive_plan_tag_acronym("decomposition-convergence-loop") == "DCL"
        )

    def test_single_word_slug_falls_back_to_the_word(self) -> None:
        assert derive_plan_tag_acronym("auth") == "AUTH"

    def test_long_single_word_slug_is_capped(self) -> None:
        assert (
            derive_plan_tag_acronym("supercalifragilistic")
            == "supercalifragilistic"[:12].upper()
        )

    def test_many_word_slug_is_capped(self) -> None:
        slug = "-".join(f"w{i}" for i in range(20))
        assert len(derive_plan_tag_acronym(slug)) <= 12

    def test_no_alnum_returns_empty(self) -> None:
        assert derive_plan_tag_acronym("---") == ""


class TestPrintJiraConfig:
    def test_absent_config_prints_bootstrap_hint(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        path = default_config_path(tmp_path)
        _print_jira_config(JiraConfig(), path, tmp_path)
        out = capsys.readouterr().out
        assert f"no jira config at {path}" in out
        assert "plan-tool jira config" in out

    def test_populated_config_lists_epics_and_assignments(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = JiraConfig(
            epics=[
                Epic(
                    key="AUTH",
                    name="Authentication",
                    jira_epic_id="PROJ-1",
                    description="login work",
                )
            ],
            plan_assignments={"docs/plans/1-demo.md": "AUTH"},
        )
        path = _write_config(tmp_path, config)
        _print_jira_config(config, path, tmp_path)
        out = capsys.readouterr().out
        assert "AUTH  Authentication → PROJ-1" in out
        assert "login work" in out
        assert "docs/plans/1-demo.md → AUTH" in out

    def test_populated_config_lists_plan_tags(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = JiraConfig(plan_tags={"docs/plans/1-demo.md": "DEMO"})
        path = _write_config(tmp_path, config)
        _print_jira_config(config, path, tmp_path)
        out = capsys.readouterr().out
        assert "Plan tags:" in out
        assert "docs/plans/1-demo.md → [DEMO]" in out

    def test_empty_config_renders_none_placeholders(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        path = _write_config(tmp_path, JiraConfig())
        _print_jira_config(JiraConfig(), path, tmp_path)
        out = capsys.readouterr().out
        assert (
            "Epics:" in out
            and "Plan assignments:" in out
            and "Plan tags:" in out
        )
        assert out.count("(none)") == 3


class TestWizardAddEpic:
    def test_valid_epic_appended(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config = JiraConfig()
        _script_stdin(monkeypatch, ["AUTH", "Authentication", "PROJ-9", "desc"])
        _wizard_add_epic(config)
        assert [e.key for e in config.epics] == ["AUTH"]
        assert config.epics[0].jira_epic_id == "PROJ-9"
        assert config.epics[0].description == "desc"

    def test_invalid_key_skips(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = JiraConfig()
        # "a" → upper "A" is too short, so validate_epic_key rejects it.
        _script_stdin(monkeypatch, ["a"])
        _wizard_add_epic(config)
        assert config.epics == []
        assert capsys.readouterr().out  # diagnostic printed

    def test_duplicate_key_skips(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = JiraConfig(epics=[Epic(key="AUTH", name="Auth")])
        _script_stdin(monkeypatch, ["AUTH"])
        _wizard_add_epic(config)
        assert len(config.epics) == 1
        assert "already exists" in capsys.readouterr().out

    def test_empty_name_skips(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = JiraConfig()
        _script_stdin(monkeypatch, ["AUTH", ""])
        _wizard_add_epic(config)
        assert config.epics == []
        assert "name is required" in capsys.readouterr().out

    def test_key_matching_jira_project_skips(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = JiraConfig()
        _script_stdin(monkeypatch, ["AUTH", "Authentication", "AUTH-1234"])
        _wizard_add_epic(config)
        assert config.epics == []
        assert "matches the real JIRA project key" in capsys.readouterr().out

    def test_key_matching_a_sibling_epics_jira_project_skips(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # New epic AUTH has no jira id of its own — the collision comes
        # from the already-configured PAY epic's jira_epic_id.
        config = JiraConfig(
            epics=[Epic(key="PAY", name="Pay", jira_epic_id="AUTH-500")]
        )
        _script_stdin(monkeypatch, ["AUTH", "Authentication", ""])
        _wizard_add_epic(config)
        assert [e.key for e in config.epics] == ["PAY"]
        assert "matches the real JIRA project key" in capsys.readouterr().out


class TestWizardEditEpic:
    def test_no_epics_reports(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = JiraConfig()
        _script_stdin(monkeypatch, [])
        _wizard_edit_epic(config)
        assert "no epics defined" in capsys.readouterr().out

    def test_unknown_key_reports(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = JiraConfig(epics=[Epic(key="AUTH", name="Auth")])
        _script_stdin(monkeypatch, ["ZZZ"])
        _wizard_edit_epic(config)
        assert "no epic with key" in capsys.readouterr().out

    def test_blank_keeps_clear_dash_removes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config = JiraConfig(
            epics=[
                Epic(key="AUTH", name="Auth", jira_epic_id="PROJ-1", description="d")
            ]
        )
        # key, name (blank → keep), jira id (blank → keep), desc ("-" → clear).
        _script_stdin(monkeypatch, ["AUTH", "", "", "-"])
        _wizard_edit_epic(config)
        edited = config.epic_by_key("AUTH")
        assert edited is not None
        assert edited.name == "Auth"
        assert edited.jira_epic_id == "PROJ-1"
        assert edited.description is None

    def test_jira_id_matching_key_skips(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = JiraConfig(epics=[Epic(key="AUTH", name="Auth")])
        # key, name (blank → keep), jira id introduces the collision.
        _script_stdin(monkeypatch, ["AUTH", "", "AUTH-1234"])
        _wizard_edit_epic(config)
        edited = config.epic_by_key("AUTH")
        assert edited is not None
        assert edited.jira_epic_id is None  # rejected — left unchanged
        assert "matches the real JIRA project key" in capsys.readouterr().out


class TestWizardRemoveEpic:
    def test_no_epics_reports(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = JiraConfig()
        _script_stdin(monkeypatch, [])
        _wizard_remove_epic(config)
        assert "no epics defined" in capsys.readouterr().out

    def test_unknown_key_reports(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = JiraConfig(epics=[Epic(key="AUTH", name="Auth")])
        _script_stdin(monkeypatch, ["ZZZ"])
        _wizard_remove_epic(config)
        assert "no epic with key" in capsys.readouterr().out

    def test_yes_unassigns_dependent_plans(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config = JiraConfig(
            epics=[Epic(key="AUTH", name="Auth")],
            plan_assignments={"docs/a.md": "AUTH"},
        )
        _script_stdin(monkeypatch, ["AUTH"])  # no confirm prompt under yes=True
        _wizard_remove_epic(config, yes=True)
        assert config.epics == []
        assert config.plan_assignments == {}

    def test_confirm_cancel_keeps_epic(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config = JiraConfig(
            epics=[Epic(key="AUTH", name="Auth")],
            plan_assignments={"docs/a.md": "AUTH"},
        )
        _script_stdin(monkeypatch, ["AUTH", "n"])  # decline the unassign confirm
        _wizard_remove_epic(config, yes=False)
        assert [e.key for e in config.epics] == ["AUTH"]
        assert config.plan_assignments == {"docs/a.md": "AUTH"}


class TestWizardAssignAndUnassignPlan:
    def test_assign_requires_an_epic_first(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        config = JiraConfig()
        _script_stdin(monkeypatch, [])
        _wizard_assign_plan(config, tmp_path)
        assert "add an epic first" in capsys.readouterr().out

    def test_assign_resolves_path_and_records(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "plan.md").write_text("x", encoding="utf-8")
        config = JiraConfig(epics=[Epic(key="AUTH", name="Auth")])
        _script_stdin(monkeypatch, ["plan.md", "AUTH"])
        _wizard_assign_plan(config, tmp_path)
        assert config.plan_assignments == {"plan.md": "AUTH"}

    def test_assign_empty_plan_input_skips(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        config = JiraConfig(epics=[Epic(key="AUTH", name="Auth")])
        _script_stdin(monkeypatch, [""])
        _wizard_assign_plan(config, tmp_path)
        assert config.plan_assignments == {}
        assert "no plan specified" in capsys.readouterr().out

    def test_unassign_none_reports(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = JiraConfig()
        _script_stdin(monkeypatch, [])
        _wizard_unassign_plan(config)
        assert "no plan assignments" in capsys.readouterr().out

    def test_unassign_removes_existing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config = JiraConfig(
            epics=[Epic(key="AUTH", name="Auth")],
            plan_assignments={"docs/a.md": "AUTH"},
        )
        _script_stdin(monkeypatch, ["docs/a.md"])
        _wizard_unassign_plan(config)
        assert config.plan_assignments == {}

    def test_unassign_unknown_path_reports(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config = JiraConfig(
            epics=[Epic(key="AUTH", name="Auth")],
            plan_assignments={"docs/a.md": "AUTH"},
        )
        _script_stdin(monkeypatch, ["docs/other.md"])
        _wizard_unassign_plan(config)
        assert "no assignment for" in capsys.readouterr().out
        assert config.plan_assignments == {"docs/a.md": "AUTH"}


class TestWizardResolvePlanRel:
    def test_direct_repo_relative_path_resolves(self, tmp_path: Path) -> None:
        (tmp_path / "plan.md").write_text("x", encoding="utf-8")
        assert _wizard_resolve_plan_rel("plan.md", tmp_path) == "plan.md"

    def test_unresolvable_returns_none(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert _wizard_resolve_plan_rel("nope.md", tmp_path) is None
        assert "could not resolve" in capsys.readouterr().out


def _companion_setup(tmp_path: Path, *, epic_key: str = "AUTH") -> tuple[Path, Path]:
    """A plan + manifest + a jira config defining one epic (unassigned).

    ``--epic <epic_key>`` resolves against this config without a plan
    assignment already present, so every companion test controls epic
    resolution explicitly rather than depending on interactive/TTY state.
    """
    (tmp_path / ".git").mkdir()
    plan = _make_plan(tmp_path)
    manifest = _write_manifest(tmp_path, plan)
    _write_config(tmp_path, JiraConfig(epics=[Epic(key=epic_key, name="Auth")]))
    return plan, manifest


class TestCmdJiraPairedExport:
    def test_default_export_passes_the_derived_story_and_handoff_paths(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from plan_tool.cli import app as cli_module

        plan, manifest = _companion_setup(tmp_path)
        seen: dict[str, object] = {}

        def fake_export(plan_path: Path, **kwargs: object) -> JiraPublicationResult:
            seen.update(kwargs)
            return JiraPublicationResult(
                story_path=kwargs["story_output_path"],
                handoff_path=kwargs["handoff_output_path"],
                story_output="story",
                handoff_output="handoff",
                stories=[],
                dropped_history=[],
                changed_created_tickets=[],
                created_to_dropped=[],
            )

        monkeypatch.setattr("plan_tool.cli.jira_cmd.export_jira", fake_export)
        monkeypatch.chdir(tmp_path)
        assert cli_module.main(["--manifest", str(manifest), "jira", "demo", "--epic", "AUTH"]) == 0

        assert seen["story_output_path"] == derive_jira_output_path(
            plan, None, format="markdown"
        ).resolve()
        assert seen["handoff_output_path"] == (
            plan.parent / "jira-handoffs" / "demo" / "jira-stories.developer-handoff.md"
        )
        assert seen["grade"] == "run"
        assert "wrote story to" in capsys.readouterr().out

    def test_paired_export_forwards_jira_grade(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli import app as cli_module

        _, manifest = _companion_setup(tmp_path)
        seen: dict[str, object] = {}

        def fake_export(plan_path: Path, **kwargs: object) -> JiraPublicationResult:
            seen.update(kwargs)
            return JiraPublicationResult(
                story_path=kwargs["story_output_path"],
                handoff_path=kwargs["handoff_output_path"],
                story_output="story",
                handoff_output="handoff",
                stories=[],
                dropped_history=[],
                changed_created_tickets=[],
                created_to_dropped=[],
            )

        monkeypatch.setattr("plan_tool.cli.jira_cmd.export_jira", fake_export)
        monkeypatch.chdir(tmp_path)
        assert cli_module.main(
            ["--manifest", str(manifest), "jira", "demo", "--epic", "AUTH", "--grade", "jira"]
        ) == 0
        assert seen["grade"] == "jira"

    def test_no_write_renders_and_prints_both_artifacts(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from plan_tool.cli import app as cli_module

        _, manifest = _companion_setup(tmp_path)
        seen: dict[str, object] = {}

        class FakeRender:
            class story_export:
                output = "story"

            handoff_body = "handoff"

        def fake_render(plan_path: Path, **kwargs: object) -> FakeRender:
            seen.update(kwargs)
            return FakeRender()

        monkeypatch.setattr("plan_tool.cli.jira_cmd.render_jira_export", fake_render)
        monkeypatch.chdir(tmp_path)
        assert cli_module.main(
            [
                "--manifest", str(manifest), "jira", "demo", "--epic", "AUTH",
                "--no-write", "--adopt-existing",
            ]
        ) == 0

        assert seen["adopt_existing"] is True
        out = capsys.readouterr().out
        assert "--- story" in out
        assert "--- developer handoff" in out

    def test_no_write_keeps_render_only_behavior_for_unmatched_run_grade_body(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli import app as cli_module

        plan_path, manifest = _companion_setup(tmp_path)
        plan_path.write_text(
            plan_path.read_text(encoding="utf-8") + "\n```\n",
            encoding="utf-8",
        )
        rendered: list[Path] = []

        class FakeRender:
            class story_export:
                output = "story"

            handoff_body = "handoff"

        def fake_render(path: Path, **_kwargs: object) -> FakeRender:
            rendered.append(path)
            return FakeRender()

        monkeypatch.setattr("plan_tool.cli.jira_cmd.render_jira_export", fake_render)
        monkeypatch.chdir(tmp_path)

        assert cli_module.main(
            ["--manifest", str(manifest), "jira", "demo", "--epic", "AUTH", "--no-write"]
        ) == 0
        assert rendered == [plan_path]

    def test_export_options_reject_config_and_lint(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from plan_tool.cli import app as cli_module

        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        assert cli_module.main(["jira", "config", "--adopt-existing"]) == 2
        assert "cannot be combined" in capsys.readouterr().err
        assert cli_module.main(["jira", "demo", "--lint", "--handoff-output", "out.md"]) == 2
        assert "cannot be combined" in capsys.readouterr().err

    def test_retired_flags_are_not_accepted(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from plan_tool.cli import app as cli_module

        _, manifest = _companion_setup(tmp_path)
        monkeypatch.chdir(tmp_path)
        with pytest.raises(SystemExit) as developer_handoff:
            cli_module.main(["--manifest", str(manifest), "jira", "demo", "--developer-handoff"])
        assert developer_handoff.value.code == 2
        with pytest.raises(SystemExit) as dry_run:
            cli_module.main(["--manifest", str(manifest), "jira", "demo", "--dry-run"])
        assert dry_run.value.code == 2
