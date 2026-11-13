"""Characterization tests for ``plan-tool install-skill``.

Driven through ``main(argv)`` against a temp repo (the split-proof
convention — see ``tests/cli/conftest.py``). ``install-skill`` makes no
claude call, so these need no invoker stubbing; the bundled
``integrations/claude/SKILL.md`` and ``integrations/shared/DIRECTIVES.md``
resolve from the real install.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
import yaml

import plan_tool.cli as cli
from plan_tool.backend import _packaged_integrations_dir


def _bundled(integration: str = "claude") -> Path:
    """The real bundled ``<integration>`` SKILL.md (asserted to exist)."""
    root = _packaged_integrations_dir()
    assert root is not None
    src = root / integration / "SKILL.md"
    assert src.is_file()
    return src.resolve()


def _bundled_directives() -> Path:
    """The real bundled shared DIRECTIVES.md (asserted to exist)."""
    root = _packaged_integrations_dir()
    assert root is not None
    src = root / "shared" / "DIRECTIVES.md"
    assert src.is_file()
    return src.resolve()


def _dest(repo, root: str = ".claude") -> Path:
    return repo.root / root / "skills" / "plan-tool" / "SKILL.md"


def _directives_dest(repo, root: str = ".claude") -> Path:
    return repo.root / root / "skills" / "plan-tool" / "DIRECTIVES.md"


class TestInstallSkill:
    def test_symlink_install_points_at_bundled_source(self, tmp_repo) -> None:
        assert cli.main(tmp_repo.argv("install-skill")) == 0
        dest = _dest(tmp_repo)
        assert dest.is_symlink()
        assert dest.resolve() == _bundled()
        directives_dest = _directives_dest(tmp_repo)
        assert directives_dest.is_symlink()
        assert directives_dest.resolve() == _bundled_directives()

    @pytest.mark.parametrize("integration", ["claude", "codex", "cursor"])
    def test_installed_router_defers_to_project_choices_and_ships_shared_selection_policy(
        self, tmp_repo, integration
    ) -> None:
        assert cli.main(
            tmp_repo.argv("install-skill", "--integration", integration)
        ) == 0
        root = ".agents" if integration == "codex" else ".claude"
        router = _dest(tmp_repo, root)
        directives = _directives_dest(tmp_repo, root)
        assert router.read_bytes() == _bundled(integration).read_bytes()
        assert directives.read_bytes() == _bundled_directives().read_bytes()
        assert router.is_symlink() == (integration != "codex")
        assert directives.is_symlink() == (integration != "codex")
        router_text = router.read_text(encoding="utf-8")
        assert "honor explicit user requests; otherwise omit selection" in router_text
        assert "DIRECTIVES.md#which-model-to-run-a-subcommand-with" in router_text
        policy = directives.read_text(encoding="utf-8")
        assert "Honor explicit user requests for backend and model" in policy
        assert "flags so project defaults apply" in policy
        # The regime is chosen by reading backends.json, so the two paragraphs
        # cannot both apply to one project.
        assert "Tell the two regimes apart by reading `.plan-tool/backends.json`" in policy
        assert "use\nthese recommendations" in policy
        assert "`--model` overrides model defaults" in policy

    def test_symlink_install_is_idempotent(self, tmp_repo) -> None:
        assert cli.main(tmp_repo.argv("install-skill")) == 0
        # Second run sees the same link and reports already-installed, rc 0,
        # without rewriting.
        assert cli.main(tmp_repo.argv("install-skill")) == 0
        assert _dest(tmp_repo).is_symlink()

    def test_collision_with_foreign_file_refuses(self, tmp_repo) -> None:
        dest = _dest(tmp_repo)
        dest.parent.mkdir(parents=True)
        dest.write_text("not the skill", encoding="utf-8")
        assert cli.main(tmp_repo.argv("install-skill")) == 2
        # Left untouched.
        assert dest.read_text(encoding="utf-8") == "not the skill"

    def test_force_overwrites_foreign_file(self, tmp_repo) -> None:
        dest = _dest(tmp_repo)
        dest.parent.mkdir(parents=True)
        dest.write_text("not the skill", encoding="utf-8")
        assert cli.main(tmp_repo.argv("install-skill", "--force")) == 0
        assert dest.is_symlink()
        assert dest.resolve() == _bundled()

    def test_copy_embeds_file_contents(self, tmp_repo) -> None:
        assert cli.main(tmp_repo.argv("install-skill", "--copy")) == 0
        dest = _dest(tmp_repo)
        assert not dest.is_symlink()
        assert dest.read_bytes() == _bundled().read_bytes()
        directives_dest = _directives_dest(tmp_repo)
        assert not directives_dest.is_symlink()
        assert directives_dest.read_bytes() == _bundled_directives().read_bytes()

    def test_copy_is_idempotent(self, tmp_repo) -> None:
        assert cli.main(tmp_repo.argv("install-skill", "--copy")) == 0
        assert cli.main(tmp_repo.argv("install-skill", "--copy")) == 0
        assert not _dest(tmp_repo).is_symlink()

    def test_root_agents_installs_under_dot_agents(self, tmp_repo) -> None:
        assert cli.main(
            tmp_repo.argv("install-skill", "--root", ".agents")
        ) == 0
        assert _dest(tmp_repo, ".agents").is_symlink()
        assert _directives_dest(tmp_repo, ".agents").is_symlink()
        assert not (tmp_repo.root / ".claude").exists()

    def test_user_install_targets_home(self, tmp_repo) -> None:
        # The autouse conftest fixture pins Path.home() to a per-test temp
        # dir, so --user lands there hermetically.
        assert cli.main(tmp_repo.argv("install-skill", "--user")) == 0
        dest = Path.home() / ".claude" / "skills" / "plan-tool" / "SKILL.md"
        assert dest.is_symlink()
        assert dest.resolve() == _bundled()
        directives_dest = (
            Path.home() / ".claude" / "skills" / "plan-tool" / "DIRECTIVES.md"
        )
        assert directives_dest.is_symlink()
        assert directives_dest.resolve() == _bundled_directives()
        # --user must not write under the repo.
        assert not (tmp_repo.root / ".claude").exists()

    def test_missing_bundled_source_returns_1(
        self, tmp_repo, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Point integrations discovery at an empty dir (no SKILL.md) so the
        # source resolves to None. Patch the seam this module binds.
        from plan_tool.cli import skill_cmd

        empty = tmp_path / "no-integrations"
        empty.mkdir()
        monkeypatch.setattr(
            skill_cmd, "_packaged_integrations_dir", lambda: empty
        )
        assert cli.main(tmp_repo.argv("install-skill")) == 1
        assert not (tmp_repo.root / ".claude").exists()

    def test_collision_on_directives_only_refuses_and_leaves_skill_uninstalled(
        self, tmp_repo
    ) -> None:
        # A foreign file sits only at the DIRECTIVES.md destination; the
        # SKILL.md destination doesn't exist yet. The whole set must be
        # refused, not just the colliding half — "check every path before
        # writing any" means the SKILL.md destination is never created.
        directives_dest = _directives_dest(tmp_repo)
        directives_dest.parent.mkdir(parents=True)
        directives_dest.write_text("not directives", encoding="utf-8")
        assert cli.main(tmp_repo.argv("install-skill")) == 2
        assert directives_dest.read_text(encoding="utf-8") == "not directives"
        assert not _dest(tmp_repo).exists()

    def test_force_unlinks_only_the_colliding_path(self, tmp_repo) -> None:
        assert cli.main(tmp_repo.argv("install-skill")) == 0
        skill_dest = _dest(tmp_repo)
        # Deliberate: pin the SKILL.md symlink's inode, not just its
        # target string, so a later assert can prove --force left an
        # already-correct sibling untouched rather than unlinking and
        # relinking it -- a fresh symlink to the identical target gets a
        # new inode, so readlink() alone can't tell the two apart, but
        # lstat().st_ino can.
        skill_target_before = os.readlink(skill_dest)
        skill_inode_before = skill_dest.lstat().st_ino

        directives_dest = _directives_dest(tmp_repo)
        directives_dest.unlink()
        directives_dest.write_text("not directives", encoding="utf-8")

        assert cli.main(tmp_repo.argv("install-skill", "--force")) == 0
        assert directives_dest.is_symlink()
        assert directives_dest.resolve() == _bundled_directives()
        assert os.readlink(skill_dest) == skill_target_before
        assert skill_dest.lstat().st_ino == skill_inode_before

    def test_second_run_skips_the_already_correct_path_and_installs_the_missing_one(
        self, tmp_repo
    ) -> None:
        # Models an upgrade from the single-file installer: SKILL.md was
        # already correctly installed (by hand here, standing in for a
        # pre-this-step install) and DIRECTIVES.md doesn't exist yet.
        skill_dest = _dest(tmp_repo)
        skill_dest.parent.mkdir(parents=True)
        os.symlink(_bundled(), skill_dest)
        skill_target_before = os.readlink(skill_dest)

        assert cli.main(tmp_repo.argv("install-skill")) == 0

        directives_dest = _directives_dest(tmp_repo)
        assert directives_dest.is_symlink()
        assert directives_dest.resolve() == _bundled_directives()
        # The pre-existing SKILL.md symlink was skipped, not rewritten.
        assert os.readlink(skill_dest) == skill_target_before

    def test_missing_directives_source_returns_1(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Patch only the shared-reference resolver; the real SKILL.md
        # source still resolves, so this pins that either bundled source
        # being absent is a hard failure, not just the first one checked.
        from plan_tool.cli import skill_cmd

        monkeypatch.setattr(
            skill_cmd, "_bundled_shared_directives_source", lambda: None
        )
        assert cli.main(tmp_repo.argv("install-skill")) == 1
        assert not (tmp_repo.root / ".claude").exists()

    def test_collision_error_names_every_colliding_path(
        self, tmp_repo, capsys: pytest.CaptureFixture[str]
    ) -> None:
        skill_dest = _dest(tmp_repo)
        skill_dest.parent.mkdir(parents=True)
        skill_dest.write_text("not the skill", encoding="utf-8")
        directives_dest = _directives_dest(tmp_repo)
        directives_dest.write_text("not directives", encoding="utf-8")

        assert cli.main(tmp_repo.argv("install-skill")) == 2
        captured = capsys.readouterr()
        output = captured.out + captured.err
        assert str(skill_dest) in output
        assert str(directives_dest) in output

    def test_cursor_integration_symlink_points_at_the_bundled_cursor_router(
        self, tmp_repo
    ) -> None:
        assert cli.main(
            tmp_repo.argv("install-skill", "--integration", "cursor")
        ) == 0
        dest = _dest(tmp_repo)
        assert dest.is_symlink()
        assert dest.resolve() == _bundled("cursor")
        directives_dest = _directives_dest(tmp_repo)
        assert directives_dest.is_symlink()
        assert directives_dest.resolve() == _bundled_directives()

    def test_cursor_integration_copy_embeds_the_bundled_cursor_router_bytes(
        self, tmp_repo
    ) -> None:
        assert cli.main(
            tmp_repo.argv("install-skill", "--integration", "cursor", "--copy")
        ) == 0
        dest = _dest(tmp_repo)
        assert not dest.is_symlink()
        assert dest.read_bytes() == _bundled("cursor").read_bytes()
        directives_dest = _directives_dest(tmp_repo)
        assert not directives_dest.is_symlink()
        assert directives_dest.read_bytes() == _bundled_directives().read_bytes()

    def test_codex_integration_defaults_to_agents_root_and_copies_because_codex_skips_symlinks(
        self, tmp_repo
    ) -> None:
        # Codex scans .agents/skills and silently skips a symlinked SKILL.md
        # (measured on codex-cli 0.160.1), so neither default may regress.
        assert cli.main(
            tmp_repo.argv("install-skill", "--integration", "codex")
        ) == 0
        dest = _dest(tmp_repo, ".agents")
        assert not dest.is_symlink()
        assert dest.read_bytes() == _bundled("codex").read_bytes()
        directives_dest = _directives_dest(tmp_repo, ".agents")
        assert not directives_dest.is_symlink()
        assert directives_dest.read_bytes() == _bundled_directives().read_bytes()
        assert not (tmp_repo.root / ".claude").exists()

    def test_codex_integration_honors_an_explicit_root(self, tmp_repo) -> None:
        # Deliberately not forced to .agents: an explicit --root wins.
        assert cli.main(
            tmp_repo.argv(
                "install-skill", "--integration", "codex", "--root", ".claude"
            )
        ) == 0
        assert not _dest(tmp_repo).is_symlink()
        assert not (tmp_repo.root / ".agents").exists()

    def test_non_codex_integrations_keep_the_claude_root_default(
        self, tmp_repo
    ) -> None:
        assert cli.main(tmp_repo.argv("install-skill")) == 0
        assert _dest(tmp_repo).is_symlink()
        assert not (tmp_repo.root / ".agents").exists()

    def test_switching_to_copy_without_force_refuses_the_mixed_mode_silently(
        self, tmp_repo, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # A prior plain run installed symlinks; asking for --copy now must
        # not silently leave a mixed install (symlink here, real copy for
        # a sibling path installed fresh) -- but switching modes still
        # replaces content at an existing path, so it needs --force like
        # any other rewrite, not a silent, unconfirmed switch.
        assert cli.main(tmp_repo.argv("install-skill")) == 0
        assert cli.main(tmp_repo.argv("install-skill", "--copy")) == 2
        captured = capsys.readouterr()
        assert "--force" in (captured.out + captured.err)
        dest = _dest(tmp_repo)
        assert dest.is_symlink()  # left untouched, not silently switched

    def test_collision_and_mode_switch_together_both_named_without_force(
        self, tmp_repo, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # SKILL.md is a genuine foreign file (collision); DIRECTIVES.md is
        # a correct prior symlink install, now needing to switch to --copy
        # (mode-switch). Both need --force, for different reasons -- the
        # error must name both, not return after the first category.
        skill_dest = _dest(tmp_repo)
        skill_dest.parent.mkdir(parents=True)
        skill_dest.write_text("not the skill", encoding="utf-8")
        os.symlink(_bundled_directives(), _directives_dest(tmp_repo))

        assert cli.main(tmp_repo.argv("install-skill", "--copy")) == 2
        captured = capsys.readouterr()
        output = captured.out + captured.err
        assert str(skill_dest) in output
        assert str(_directives_dest(tmp_repo)) in output

    def test_switching_to_copy_with_force_rewrites_an_existing_correct_symlink(
        self, tmp_repo
    ) -> None:
        assert cli.main(tmp_repo.argv("install-skill")) == 0
        assert cli.main(tmp_repo.argv("install-skill", "--copy", "--force")) == 0
        dest = _dest(tmp_repo)
        assert not dest.is_symlink()
        assert dest.read_bytes() == _bundled().read_bytes()
        directives_dest = _directives_dest(tmp_repo)
        assert not directives_dest.is_symlink()
        assert directives_dest.read_bytes() == _bundled_directives().read_bytes()

    def test_switching_to_symlink_with_force_rewrites_an_existing_correct_copy(
        self, tmp_repo
    ) -> None:
        assert cli.main(tmp_repo.argv("install-skill", "--copy")) == 0
        assert cli.main(tmp_repo.argv("install-skill", "--force")) == 0
        dest = _dest(tmp_repo)
        assert dest.is_symlink()
        assert dest.resolve() == _bundled()
        directives_dest = _directives_dest(tmp_repo)
        assert directives_dest.is_symlink()
        assert directives_dest.resolve() == _bundled_directives()

    def test_directory_at_destination_reports_a_clean_error_under_force(
        self, tmp_repo, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # A directory classifies as a collision (not a symlink, not a
        # matching file); unlink() would raise IsADirectoryError on it,
        # so this must be refused up front, not crash.
        skill_dest = _dest(tmp_repo)
        skill_dest.mkdir(parents=True)
        assert cli.main(tmp_repo.argv("install-skill", "--force")) == 2
        captured = capsys.readouterr()
        assert str(skill_dest) in (captured.out + captured.err)
        assert skill_dest.is_dir()

    def test_directory_at_one_destination_refuses_the_whole_set_even_missing_items(
        self, tmp_repo
    ) -> None:
        # The other item (SKILL.md) is missing -- writable on its own --
        # but a directory sitting at DIRECTIVES.md's destination must
        # refuse the whole set up front, not write SKILL.md and then fail
        # on DIRECTIVES.md, which would leave a partial install.
        directives_dest = _directives_dest(tmp_repo)
        directives_dest.mkdir(parents=True)
        assert cli.main(tmp_repo.argv("install-skill", "--force")) == 2
        assert not _dest(tmp_repo).exists()
        assert directives_dest.is_dir()


def test_tracked_skill_folder_holds_every_file_its_router_links() -> None:
    """This repo's tracked skill must carry the siblings its router cites.

    Presence only — deliberately no content-drift check against
    ``integrations/`` (BACKLOG #443's Non-goals).
    """
    skill_dir = Path(__file__).resolve().parents[2] / ".claude" / "skills" / "plan-tool"
    text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    targets = {
        t
        for t in re.findall(r"\]\(([^)#\s]+)", text)
        if "://" not in t
    }
    assert "DIRECTIVES.md" in targets
    missing = sorted(t for t in targets if not (skill_dir / t).is_file())
    assert missing == []


_REPO_ROOT = Path(__file__).resolve().parents[2]
_SKILL_FILES = sorted(
    [
        *(_REPO_ROOT / "integrations").glob("*/SKILL.md"),
        *(_REPO_ROOT / ".claude" / "skills").glob("*/SKILL.md"),
    ]
)


@pytest.mark.parametrize(
    "skill_md", _SKILL_FILES, ids=lambda p: str(p.relative_to(_REPO_ROOT))
)
def test_skill_frontmatter_is_valid_yaml_for_a_strict_parser(skill_md: Path) -> None:
    """Every shipped or tracked SKILL.md frontmatter parses with ``safe_load``.

    An unquoted ``argument-hint`` starting with ``[`` is a YAML flow sequence
    that breaks the block mapping; a lenient host loads it anyway, a strict
    one rejects the whole file (BACKLOG #444). Glob-discovered, so a new
    router or skill fails here too.
    """
    match = re.match(r"---\r?\n(.*?)\r?\n---", skill_md.read_text(encoding="utf-8"), re.S)
    assert match is not None, f"{skill_md} has no frontmatter block"
    parsed = yaml.safe_load(match.group(1))
    assert isinstance(parsed, dict)
    assert isinstance(parsed.get("argument-hint", ""), str)


def test_skill_file_discovery_finds_every_router_and_the_tracked_skill() -> None:
    """The glob must not silently match nothing and pass vacuously."""
    names = {str(p.relative_to(_REPO_ROOT)) for p in _SKILL_FILES}
    assert {
        "integrations/claude/SKILL.md",
        "integrations/codex/SKILL.md",
        "integrations/cursor/SKILL.md",
        ".claude/skills/plan-tool/SKILL.md",
    } <= names
