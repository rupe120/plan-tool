"""Tests for scripts/release.py: the version derivation and release-commit script."""
from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Sequence
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "release.py"
_spec = importlib.util.spec_from_file_location("release_script", SCRIPT)
release = importlib.util.module_from_spec(_spec)
sys.modules["release_script"] = release
_spec.loader.exec_module(release)

PYPROJECT = """\
[build-system]
requires = ["hatchling"]

[project]
name = "plan-tool"
classifiers = [
    ["nested"],
]
version = "0.1.0"

[tool.other]
version = "9.9.9"

[tool.scriv]
categories = ["Breaking", "Added", "Changed", "Deprecated", "Removed", "Fixed", "Security"]
version = "literal: pyproject.toml: project.version"
"""
UV_LOCK = 'version = 1\n\n[[package]]\nname = "plan-tool"\nversion = "0.1.0"\nsource = { editable = "." }\n'
CHANGELOG = "# Changelog\n\n<!-- scriv-insert-here -->\n"


class Repo:
    def __init__(self, path: Path) -> None:
        self.path = path

    def git(self, *args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=self.path, capture_output=True, text=True, check=True
        ).stdout

    def write(self, rel: str, content: str) -> None:
        target = self.path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def commit_all(self, message: str) -> None:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def fragment(self, name: str, *categories: str) -> None:
        body = "\n".join(f"### {c}\n\n- A {c.lower()} change ({name}).\n" for c in categories)
        self.write(f"changelog.d/{name}.md", body)

    def head(self) -> str:
        return self.git("rev-parse", "HEAD").strip()

    def dirty(self) -> str:
        return self.git("status", "--porcelain").strip()


def _git_env(home: Path) -> dict[str, str]:
    return {
        **os.environ,
        "HOME": str(home),
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
    }


@pytest.fixture(scope="session")
def _repo_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build the immutable tagged release baseline once per worker."""
    root = tmp_path_factory.mktemp("release-template")
    env = _git_env(root)
    subprocess.run(["git", "init", "-q", "-b", "release-branch"], cwd=root, env=env, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, env=env, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=root, env=env, check=True)
    r = Repo(root)
    r.write("pyproject.toml", PYPROJECT)
    r.write("uv.lock", UV_LOCK)
    r.write("CHANGELOG.md", CHANGELOG)
    r.write("changelog.d/README.md", "# Changelog fragments\n")
    r.commit_all("Start")
    r.git("tag", "v0.1.0")
    return root


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _repo_template: Path) -> Repo:
    for key, value in _git_env(tmp_path).items():
        monkeypatch.setenv(key, value)
    root = tmp_path / "repo"
    shutil.copytree(_repo_template, root)
    return Repo(root)


def fake_tools(
    root: Path, *, fail: str | None = None, extra_heading: str | None = None, lock_churn: bool = False
):
    """Stand-in for `uv lock` and `uvx scriv collect`; it writes the contract scriv's output has."""

    def tool(argv: Sequence[str], cwd: Path) -> None:
        if fail and argv[0] == fail:
            raise release.ReleaseError(f"`{' '.join(argv)}` exited 1")
        if argv[0] == "uv":
            version = re.search(r'^version = "(.*)"$', (cwd / "pyproject.toml").read_text(), re.M)
            lock = (cwd / "uv.lock").read_text()
            lock = re.sub(r'(?<=name = "plan-tool"\n)version = "\d+\.\d+\.\d+"', f'version = "{version[1]}"', lock)
            (cwd / "uv.lock").write_text(lock + ("# unrelated churn\n" if lock_churn else ""))
            return
        version = re.search(r'^version = "(.*)"$', (cwd / "pyproject.toml").read_text(), re.M)[1]
        sections: dict[str, list[str]] = {}
        for fragment in sorted((cwd / "changelog.d").glob("*.md")):
            if fragment.name == "README.md":
                continue
            title = None
            for line in fragment.read_text().splitlines():
                if line.startswith("### "):
                    title = line[4:]
                    sections.setdefault(title, [])
                elif line.startswith("- "):
                    sections[title].append(line)
            fragment.unlink()
        if extra_heading:
            sections.setdefault(extra_heading, [])
        block = [f"<a id='changelog-{version}'></a>", f"## {version} — 2026-01-01", ""]
        for title, bullets in sections.items():
            block += [f"### {title}", "", *bullets, ""]
        marker = "<!-- scriv-insert-here -->\n"
        text = (cwd / "CHANGELOG.md").read_text()
        (cwd / "CHANGELOG.md").write_text(text.replace(marker, marker + "\n" + "\n".join(block) + "\n"))

    return tool


# --- fragment parsing -------------------------------------------------------


def test_fragment_sections_reads_level_three_headings() -> None:
    assert release.fragment_sections("### Added\n\n- One.\n\n### Fixed\n\n- Two.\n") == ["Added", "Fixed"]


def test_fragment_sections_skips_categories_left_in_scrivs_comment_template() -> None:
    """An unedited `scriv create` template must not count its commented-out categories."""
    template = (
        "<!--\nA new scriv changelog fragment.\n\nUncomment the section that is right.\n-->\n\n"
        "<!--\n### Removed\n\n- A bullet item for the Removed category.\n\n-->\n"
        "<!--\n### Added\n\n- A bullet item for the Added category.\n\n-->\n"
        "### Fixed\n\n- A real fix.\n"
    )
    assert release.fragment_sections(template) == ["Fixed"]


def test_fragment_sections_skips_a_one_line_comment_and_an_anchor() -> None:
    text = "<!-- ### Removed -->\n<a id='x'></a>\n### Security\n\n- Patched.\n"
    assert release.fragment_sections(text) == ["Security"]


def test_fragment_sections_flags_text_before_the_first_heading() -> None:
    assert release.fragment_sections("Some prose.\n\n### Added\n\n- One.\n") == [None, "Added"]


def test_fragment_sections_treats_a_deeper_heading_as_content_not_a_category() -> None:
    """scriv opens a new section only for a heading at the first heading's level."""
    assert release.fragment_sections("### Added\n\n#### Detail\n\n- One.\n") == ["Added"]


def test_fragment_sections_of_an_empty_fragment_is_empty() -> None:
    assert release.fragment_sections("\n\n") == []


# --- bump derivation --------------------------------------------------------


@pytest.mark.parametrize(
    ("categories", "bump"),
    [
        (["Added"], "minor"),
        (["Changed"], "minor"),
        (["Deprecated"], "minor"),
        (["Removed"], "minor"),
        (["Fixed"], "patch"),
        (["Security"], "patch"),
        (["Fixed", "Security"], "patch"),
        (["Fixed", "Added"], "minor"),
    ],
)
def test_derive_maps_every_category_to_its_bump(categories: list[str], bump: str) -> None:
    assert release.derive({"a.md": list(categories)})[0] == bump


def test_derive_lists_the_fragments_that_carry_each_category() -> None:
    _, by_category = release.derive({"a.md": ["Added"], "b.md": ["Added", "Fixed"]})
    assert by_category == {"Added": ["a.md", "b.md"], "Fixed": ["b.md"]}


@pytest.mark.parametrize(
    ("titles", "message"),
    [([], "no category heading"), ([None], "before its first category"), (["Notes"], "unknown category")],
)
def test_derive_refuses_a_fragment_it_cannot_categorize(titles: list, message: str) -> None:
    with pytest.raises(release.ReleaseError, match=message):
        release.derive({"a.md": titles})


def test_this_repos_scriv_categories_are_exactly_the_ones_the_bump_table_maps() -> None:
    """A category added to [tool.scriv] without a bump rule would make every release refuse."""
    real = tomllib.loads((SCRIPT.parents[1] / "pyproject.toml").read_text(encoding="utf-8"))
    mapped = release.MAJOR_CATEGORIES + release.MINOR_CATEGORIES + release.PATCH_CATEGORIES
    assert sorted(real["tool"]["scriv"]["categories"]) == sorted(mapped)
    assert len(set(mapped)) == len(mapped)


@pytest.mark.parametrize(
    ("current", "bump", "expected"),
    [((0, 1, 3), "minor", "0.2.0"), ((0, 1, 3), "patch", "0.1.4"), ((0, 9, 0), "minor", "0.10.0")],
)
def test_next_version_resets_the_patch_on_a_minor_bump(current: tuple, bump: str, expected: str) -> None:
    assert release.next_version(current, bump) == expected


def test_fragment_paths_select_exactly_the_files_scriv_collects(tmp_path: Path) -> None:
    """scriv globs `*.rst` and `*.md` and skips `README.*` case-sensitively; a `Readme.md` is collected."""
    plain = tmp_path / "plain" / "changelog.d"
    plain.mkdir(parents=True)
    for name in ("README.md", "README.rst", "a.md", "b.rst", "notes.txt"):
        (plain / name).write_text("x")
    # Its own directory: on a case-insensitive filesystem `Readme.md` and `README.md` are one file.
    cased = tmp_path / "cased" / "changelog.d"
    cased.mkdir(parents=True)
    (cased / "Readme.md").write_text("x")

    assert [p.name for p in release.fragment_paths(tmp_path / "plain")] == ["a.md", "b.rst"]
    assert [p.name for p in release.fragment_paths(tmp_path / "cased")] == ["Readme.md"]


def test_release_script_is_executable_because_the_docs_run_it_directly() -> None:
    assert os.access(SCRIPT, os.X_OK)
    assert SCRIPT.read_text().startswith("#!/usr/bin/env python3")


# --- pyproject edit and scriv output ---------------------------------------


def test_set_project_version_keeps_a_trailing_comment_on_the_version_line() -> None:
    edited = release.set_project_version('[project]\nversion = "0.1.0"  # "old"\n', "0.2.0")
    assert edited == '[project]\nversion = "0.2.0"  # "old"\n'


def test_set_project_version_edits_only_the_project_table() -> None:
    edited = release.set_project_version(PYPROJECT, "0.2.0")
    assert edited == PYPROJECT.replace('version = "0.1.0"', 'version = "0.2.0"')
    assert 'version = "9.9.9"' in edited and 'version = "literal:' in edited


def test_set_project_version_without_a_project_version_refuses() -> None:
    with pytest.raises(release.ReleaseError, match=r"under \[project\]"):
        release.set_project_version('[project]\nname = "x"\n\n[tool.other]\nversion = "1.0.0"\n', "0.2.0")


def test_collected_titles_stops_at_the_next_versions_anchor() -> None:
    changelog = (
        "<!-- scriv-insert-here -->\n\n<a id='changelog-0.2.0'></a>\n## 0.2.0 — d\n\n### Fixed\n\n- x\n\n"
        "<a id='changelog-0.1.0'></a>\n## 0.1.0 — d\n\n### Removed\n\n- y\n"
    )
    assert release.collected_titles(changelog, "0.2.0") == ["Fixed"]


def test_collected_titles_without_the_versions_section_refuses() -> None:
    with pytest.raises(release.ReleaseError, match="changelog-0.2.0"):
        release.collected_titles("<a id='changelog-0.1.0'></a>\n", "0.2.0")


# --- the release commit -----------------------------------------------------


def test_release_commits_a_minor_bump_when_any_fragment_adds(repo: Repo, capsys) -> None:
    repo.fragment("IPPT-1", "Added")
    repo.fragment("IPPT-2", "Fixed")
    repo.commit_all("Fragments")
    before = repo.head()

    assert release.cut(repo.path, force_minor=False, dry_run=False, tool=fake_tools(repo.path)) == 0

    assert repo.git("log", "-1", "--format=%s").strip() == "Release 0.2.0"
    assert repo.git("rev-parse", "HEAD~1").strip() == before
    assert repo.dirty() == ""
    assert 'version = "0.2.0"' in (repo.path / "pyproject.toml").read_text()
    assert 'name = "plan-tool"\nversion = "0.2.0"' in (repo.path / "uv.lock").read_text()
    assert "## 0.2.0" in (repo.path / "CHANGELOG.md").read_text()
    assert sorted(p.name for p in (repo.path / "changelog.d").iterdir()) == ["README.md"]
    assert "0.1.0 (tag v0.1.0) -> 0.2.0: minor" in capsys.readouterr().out


def test_release_commit_touches_only_the_release_paths_and_carries_no_trailer(repo: Repo) -> None:
    repo.fragment("IPPT-1", "Fixed")
    repo.commit_all("Fragments")

    release.cut(repo.path, force_minor=False, dry_run=False, tool=fake_tools(repo.path))

    changed = set(repo.git("show", "--name-only", "--format=", "HEAD").split())
    assert changed == {"pyproject.toml", "uv.lock", "CHANGELOG.md", "changelog.d/IPPT-1.md"}
    assert repo.git("log", "-1", "--format=%B").strip() == "Release 0.1.1"


def test_release_bumps_a_patch_when_every_fragment_is_a_fix(repo: Repo) -> None:
    repo.fragment("IPPT-1", "Fixed")
    repo.fragment("IPPT-2", "Security")
    repo.commit_all("Fragments")

    release.cut(repo.path, force_minor=False, dry_run=False, tool=fake_tools(repo.path))

    assert repo.git("log", "-1", "--format=%s").strip() == "Release 0.1.1"


def test_minor_flag_raises_a_patch_bump_to_a_minor_bump(repo: Repo, capsys) -> None:
    """A format-version bump filed under Fixed is invisible to fragments; --minor covers it."""
    repo.fragment("IPPT-1", "Fixed")
    repo.commit_all("Fragments")

    release.cut(repo.path, force_minor=True, dry_run=False, tool=fake_tools(repo.path))

    assert repo.git("log", "-1", "--format=%s").strip() == "Release 0.2.0"
    assert "(raised by --minor)" in capsys.readouterr().out


def test_minor_flag_is_a_no_op_when_the_fragments_already_say_minor(repo: Repo, capsys) -> None:
    repo.fragment("IPPT-1", "Added")
    repo.commit_all("Fragments")

    release.cut(repo.path, force_minor=True, dry_run=True)

    out = capsys.readouterr().out
    assert "-> 0.2.0: minor\n" in out and "raised" not in out


def test_dry_run_reports_the_reason_and_changes_nothing(repo: Repo, capsys) -> None:
    repo.fragment("IPPT-1", "Added")
    repo.commit_all("Fragments")
    before = repo.head()

    assert release.cut(repo.path, force_minor=False, dry_run=True) == 0

    assert repo.head() == before and repo.dirty() == ""
    out = capsys.readouterr().out
    assert "0.1.0 (tag v0.1.0) -> 0.2.0: minor" in out and "Added      IPPT-1.md" in out


@pytest.mark.parametrize("failing_tool", ["uv", "uvx"])
def test_a_tool_failure_restores_the_tree_and_makes_no_commit(repo: Repo, failing_tool: str) -> None:
    repo.fragment("IPPT-1", "Added")
    repo.commit_all("Fragments")
    before = repo.head()

    with pytest.raises(release.ReleaseError, match="exited 1"):
        release.cut(repo.path, force_minor=False, dry_run=False, tool=fake_tools(repo.path, fail=failing_tool))

    assert repo.head() == before
    assert repo.dirty() == ""
    assert 'version = "0.1.0"' in (repo.path / "pyproject.toml").read_text()
    assert (repo.path / "changelog.d" / "IPPT-1.md").exists()


def test_scriv_output_that_disagrees_with_the_derived_categories_is_refused(repo: Repo) -> None:
    """If scriv sees an Added section the parse missed, the patch bump is wrong: roll back."""
    repo.fragment("IPPT-1", "Fixed")
    repo.commit_all("Fragments")
    before = repo.head()

    with pytest.raises(release.ReleaseError, match="the bump may be wrong"):
        release.cut(
            repo.path, force_minor=False, dry_run=False, tool=fake_tools(repo.path, extra_heading="Added")
        )

    assert repo.head() == before and repo.dirty() == ""


def test_scriv_collect_runs_with_no_edit_and_no_add_so_git_config_cannot_intervene(repo: Repo) -> None:
    """scriv reads scriv.collect.edit and scriv.collect.add from git config unless the flags are given."""
    repo.fragment("IPPT-1", "Added")
    repo.commit_all("Fragments")
    calls: list[list[str]] = []
    inner = fake_tools(repo.path)

    def recording(argv: Sequence[str], cwd: Path) -> None:
        calls.append(list(argv))
        inner(argv, cwd)

    release.cut(repo.path, force_minor=False, dry_run=False, tool=recording)

    assert ["uvx", "scriv", "collect", "--no-edit", "--no-add"] in calls


def test_a_lock_update_beyond_plan_tools_own_version_line_is_refused_and_rolled_back(repo: Repo) -> None:
    """The release commit must not carry unrelated dependency churn from a drifted uv.lock."""
    repo.fragment("IPPT-1", "Added")
    repo.commit_all("Fragments")
    before = repo.head()

    with pytest.raises(release.ReleaseError, match="did not change exactly"):
        release.cut(repo.path, force_minor=False, dry_run=False, tool=fake_tools(repo.path, lock_churn=True))

    assert repo.head() == before and repo.dirty() == ""


def test_a_commit_failure_restores_the_tree(repo: Repo) -> None:
    repo.fragment("IPPT-1", "Added")
    repo.commit_all("Fragments")
    hook = repo.path / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)
    before = repo.head()

    with pytest.raises(release.ReleaseError, match="commit failed"):
        release.cut(repo.path, force_minor=False, dry_run=False, tool=fake_tools(repo.path))

    assert repo.head() == before and repo.dirty() == ""


# --- refusals ----------------------------------------------------------------


def _refused(repo: Repo, message: str) -> None:
    with pytest.raises(release.ReleaseError, match=message):
        release.cut(repo.path, force_minor=False, dry_run=False, tool=fake_tools(repo.path))


def test_release_refuses_when_there_are_no_fragments(repo: Repo) -> None:
    _refused(repo, "nothing to release")


def test_release_refuses_an_unreleased_current_version(repo: Repo) -> None:
    """Without a v<version> tag the base is unreleased, so a bump would skip a release."""
    repo.fragment("IPPT-1", "Added")
    repo.commit_all("Fragments")
    repo.git("tag", "-d", "v0.1.0")
    _refused(repo, "no tag v0.1.0")


def test_release_refuses_a_tag_that_is_not_an_ancestor_of_head(repo: Repo) -> None:
    """A branch cut before the tag, or a tag on another line of history, does not follow that release."""
    repo.git("switch", "-q", "-c", "side")
    repo.write("side.txt", "x")
    repo.commit_all("Side")
    repo.git("tag", "-f", "v0.1.0")
    repo.git("switch", "-q", "release-branch")
    repo.fragment("IPPT-1", "Added")
    repo.commit_all("Fragments")
    _refused(repo, "not an ancestor of HEAD")


def test_release_refuses_when_the_new_versions_tag_already_exists(repo: Repo) -> None:
    """v0.2.0 existing means v0.1.0 is not the latest release; committing 0.2.0 would collide at tag time."""
    repo.fragment("IPPT-1", "Added")
    repo.commit_all("Fragments")
    repo.git("tag", "v0.2.0")
    _refused(repo, "tag v0.2.0 already exists")


def test_release_refuses_a_restructuredtext_fragment_scriv_would_parse_differently(repo: Repo) -> None:
    repo.write("changelog.d/IPPT-1.rst", "Added\n=====\n\n- Something.\n")
    repo.commit_all("Fragments")
    _refused(repo, "not a Markdown fragment")


def test_release_refuses_a_dirty_tree(repo: Repo) -> None:
    repo.fragment("IPPT-1", "Added")
    _refused(repo, "uncommitted changes")


def test_release_refuses_a_detached_head(repo: Repo) -> None:
    repo.fragment("IPPT-1", "Added")
    repo.commit_all("Fragments")
    repo.git("checkout", "-q", "--detach")
    _refused(repo, "HEAD is detached")


def test_release_refuses_to_run_on_main(repo: Repo) -> None:
    """The docs cut the release on a branch and merge it by pull request; main itself is refused."""
    repo.fragment("IPPT-1", "Added")
    repo.commit_all("Fragments")
    repo.git("branch", "-m", "main")
    _refused(repo, "on main")


def test_a_failed_restore_says_so_and_names_the_command_to_run(repo: Repo, capsys) -> None:
    """A rollback that cannot restore must not pass silently: the tree is left modified."""
    repo.fragment("IPPT-1", "Added")
    repo.commit_all("Fragments")

    def tool(argv: Sequence[str], cwd: Path) -> None:
        (cwd / ".git" / "index.lock").write_text("")
        raise release.ReleaseError("`uv lock` exited 1")

    with pytest.raises(release.ReleaseError, match="exited 1"):
        release.cut(repo.path, force_minor=False, dry_run=False, tool=tool)

    err = capsys.readouterr().err
    assert "could NOT restore" in err and "git restore --source=HEAD" in err
    assert 'version = "0.2.0"' in (repo.path / "pyproject.toml").read_text()


def test_a_missing_git_binary_is_a_refusal_not_a_traceback(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_git(*args, **kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(release.subprocess, "run", no_git)
    with pytest.raises(release.ReleaseError, match="'git' is not on PATH"):
        release._git(Path("."), "status")


def test_an_unparseable_pyproject_exits_2_with_a_message(
    repo: Repo, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    repo.write("pyproject.toml", "[project\nversion = ")
    monkeypatch.chdir(repo.path)

    assert release.main(["--dry-run"]) == 2
    assert "release: cannot read pyproject.toml" in capsys.readouterr().err



def test_release_refuses_a_version_that_is_not_x_y_z(repo: Repo) -> None:
    repo.write("pyproject.toml", PYPROJECT.replace('version = "0.1.0"', 'version = "0.2.0rc1"'))
    repo.commit_all("Pre-release")
    _refused(repo, "not X.Y.Z")


def test_release_refuses_when_scriv_categories_drift_from_the_bump_table(repo: Repo) -> None:
    repo.write("pyproject.toml", PYPROJECT.replace('"Security"]', '"Security", "Performance"]'))
    repo.fragment("IPPT-1", "Added")
    repo.commit_all("New category")
    _refused(repo, "differ from the categories")


def test_release_refuses_a_fragment_with_an_unknown_category(repo: Repo) -> None:
    repo.fragment("IPPT-1", "Notes")
    repo.commit_all("Fragments")
    _refused(repo, "unknown category")


def test_main_exits_2_with_a_message_on_a_refusal(repo: Repo, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.chdir(repo.path)

    assert release.main(["--dry-run"]) == 2
    assert "release: no fragments" in capsys.readouterr().err


def _released_base(repo: Repo, version: str) -> None:
    repo.write("pyproject.toml", PYPROJECT.replace('version = "0.1.0"', f'version = "{version}"'))
    repo.write("uv.lock", UV_LOCK.replace('version = "0.1.0"', f'version = "{version}"'))
    repo.commit_all("Released baseline")
    repo.git("tag", f"v{version}")


@pytest.mark.parametrize(("current", "categories", "expected"), [
    ("1.0.0", ["Fixed", "Security"], "1.0.1"),
    ("1.2.3", ["Added", "Fixed"], "1.3.0"),
    ("1.2.3", ["Breaking", "Added", "Fixed"], "2.0.0"),
    ("2.4.7", ["Breaking"], "3.0.0"),
])
def test_post_one_release_commits_derived_version_and_collects_breaking_notes(repo, current, categories, expected):
    _released_base(repo, current)
    repo.fragment("change", *categories)
    repo.commit_all("Pending changes")
    tags = repo.git("tag", "--list")

    assert release.cut(repo.path, force_minor=False, dry_run=False, tool=fake_tools(repo.path)) == 0

    assert repo.git("log", "-1", "--format=%s").strip() == f"Release {expected}"
    assert tomllib.loads((repo.path / "pyproject.toml").read_text())["project"]["version"] == expected
    lock = tomllib.loads((repo.path / "uv.lock").read_text())
    assert lock["package"][0]["version"] == expected
    notes = (repo.path / "CHANGELOG.md").read_text()
    assert all(f"### {category}" in notes for category in categories)
    assert "change" in notes
    assert not (repo.path / "changelog.d/change.md").exists()
    assert repo.dirty() == ""
    assert repo.git("tag", "--list") == tags


@pytest.mark.parametrize("force_minor", [False, True])
def test_breaking_preview_explains_major_and_minor_flag_cannot_demote_it(repo, capsys, force_minor):
    _released_base(repo, "1.4.9")
    repo.fragment("api-removal", "Breaking")
    repo.fragment("bug-fix", "Fixed")
    repo.commit_all("Pending changes")
    before = repo.head()

    release.cut(repo.path, force_minor=force_minor, dry_run=True)

    output = capsys.readouterr().out
    assert "1.4.9 (tag v1.4.9) -> 2.0.0: major" in output
    assert "Breaking   api-removal.md" in output
    assert "Fixed      bug-fix.md" in output
    assert "raised by --minor" not in output
    assert repo.head() == before and repo.dirty() == ""


def test_breaking_before_one_keeps_minor_policy_and_explains_it(repo, capsys):
    repo.fragment("incompatible", "Breaking")
    repo.commit_all("Pending changes")
    release.cut(repo.path, force_minor=False, dry_run=False, tool=fake_tools(repo.path))
    assert repo.git("log", "-1", "--format=%s").strip() == "Release 0.2.0"
    assert "before 1.0" in capsys.readouterr().out
    assert "### Breaking" in (repo.path / "CHANGELOG.md").read_text()


@pytest.mark.parametrize("failing_tool", ["uv", "uvx"])
def test_major_release_failure_restores_all_release_inputs(repo, failing_tool):
    _released_base(repo, "1.2.3")
    repo.fragment("incompatible", "Breaking")
    repo.commit_all("Pending changes")
    before = repo.head()
    snapshots = {p: (repo.path / p).read_bytes() for p in ["pyproject.toml", "uv.lock", "CHANGELOG.md", "changelog.d/incompatible.md"]}
    with pytest.raises(release.ReleaseError, match="exited 1"):
        release.cut(repo.path, force_minor=False, dry_run=False, tool=fake_tools(repo.path, fail=failing_tool))
    assert repo.head() == before and repo.dirty() == ""
    assert all((repo.path / p).read_bytes() == content for p, content in snapshots.items())


@pytest.mark.parametrize(("current", "bump", "expected"), [
    ((1, 2, 9), "patch", "1.2.10"),
    ((1, 2, 9), "minor", "1.3.0"),
    ((1, 2, 9), "major", "2.0.0"),
    ((2, 0, 1), "major", "3.0.0"),
])
def test_next_version_resets_subordinate_components_for_post_one_bumps(current, bump, expected):
    assert release.next_version(current, bump) == expected


def test_breaking_category_dominates_all_compatible_categories():
    assert release.derive({"a.md": ["Fixed", "Breaking"], "b.md": ["Added"]}) == (
        "major", {"Fixed": ["a.md"], "Breaking": ["a.md"], "Added": ["b.md"]},
    )


def test_post_one_minor_override_raises_fix_only_preview(repo, capsys):
    _released_base(repo, "1.2.8")
    repo.fragment("fix", "Fixed")
    repo.commit_all("Pending fix")
    release.cut(repo.path, force_minor=True, dry_run=True)
    assert "-> 1.3.0: minor (raised by --minor)" in capsys.readouterr().out
    assert repo.dirty() == ""


def test_major_release_refuses_existing_destination_tag(repo):
    _released_base(repo, "1.9.9")
    repo.git("tag", "v2.0.0")
    repo.fragment("break", "Breaking")
    repo.commit_all("Pending change")
    _refused(repo, "tag v2.0.0 already exists")
    assert repo.dirty() == ""


def test_major_collection_must_retain_breaking_category_or_restore_inputs(repo):
    _released_base(repo, "1.2.3")
    repo.fragment("break", "Breaking")
    repo.commit_all("Pending change")
    before = repo.head()
    tools = fake_tools(repo.path)

    def lose_breaking(argv, cwd):
        tools(argv, cwd)
        if argv[0] == "uvx":
            path = cwd / "CHANGELOG.md"
            path.write_text(path.read_text().replace("### Breaking", "### Changed"))

    with pytest.raises(release.ReleaseError, match="bump may be wrong"):
        release.cut(repo.path, force_minor=False, dry_run=False, tool=lose_breaking)
    assert repo.head() == before and repo.dirty() == ""
    assert (repo.path / "changelog.d/break.md").exists()
    assert (repo.path / "CHANGELOG.md").read_text() == CHANGELOG


def test_unknown_bump_cannot_silently_become_patch():
    with pytest.raises(release.ReleaseError, match="unknown release bump"):
        release.next_version((1, 2, 3), "typo")


@pytest.fixture
def publication(repo: Repo, tmp_path: Path) -> tuple[Repo, Path]:
    repo.write("CHANGELOG.md", CHANGELOG + "\n<a id='changelog-0.1.0'></a>\n## 0.1.0\n")
    repo.commit_all("Release 0.1.0")
    repo.git("switch", "-c", "main")
    repo.git("tag", "-d", "v0.1.0")
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)
    repo.git("remote", "add", "origin", str(remote))
    repo.git("push", "origin", "main")
    return repo, remote


def test_publish_creates_only_release_tag_and_retry_is_idempotent(publication):
    repo, remote = publication
    head = repo.head()
    assert release.publish(repo.path, remote="origin", dry_run=False) == 0
    assert repo.git("cat-file", "-t", "v0.1.0").strip() == "tag"
    assert repo.git("ls-remote", str(remote), "refs/tags/v0.1.0^{}").split()[0] == head
    assert release.publish(repo.path, remote="origin", dry_run=False) == 0
    assert repo.head() == head and not repo.dirty()


def test_publish_dry_run_changes_neither_local_nor_remote_tags(publication):
    repo, remote = publication
    release.publish(repo.path, remote="origin", dry_run=True)
    assert not repo.git("tag", "--list", "v0.1.0").strip()
    assert not repo.git("ls-remote", str(remote), "refs/tags/*").strip()


@pytest.mark.parametrize("condition", ["branch", "dirty", "main-drift", "lock", "notes", "fragments", "local-tag", "remote-tag", "push-urls"])
def test_publish_refuses_invalid_release_without_remote_mutation(publication, condition):
    repo, remote = publication
    if condition == "branch":
        repo.git("switch", "release-branch")
    elif condition == "dirty":
        repo.write("untracked.txt", "pending")
    elif condition == "main-drift":
        repo.write("new.txt", "change")
        repo.commit_all("Further change")
    elif condition in {"lock", "notes", "fragments"}:
        if condition == "lock":
            repo.write("uv.lock", UV_LOCK.replace("0.1.0", "0.2.0"))
        elif condition == "notes":
            repo.write("CHANGELOG.md", CHANGELOG)
        else:
            repo.fragment("pending.md", "Fixed")
        repo.commit_all("Invalid release")
        repo.git("push", "origin", "main")
    elif condition == "local-tag":
        repo.git("tag", "v0.1.0", "HEAD~1")
    elif condition == "remote-tag":
        repo.git("tag", "v0.1.0", "HEAD~1")
        repo.git("push", "origin", "refs/tags/v0.1.0")
        repo.git("tag", "-d", "v0.1.0")
    else:
        repo.git("config", "--add", "remote.origin.pushurl", str(remote))
        repo.git("config", "--add", "remote.origin.pushurl", str(remote) + "-other")
    before = repo.git("ls-remote", str(remote))
    with pytest.raises(release.ReleaseError):
        release.publish(repo.path, remote="origin", dry_run=False)
    assert repo.git("ls-remote", str(remote)) == before


def test_publish_keeps_local_tag_after_failed_push_for_retry(publication, monkeypatch):
    repo, _ = publication
    original = release._git
    def fail_push(root, *args):
        if args[0] == "push":
            raise release.ReleaseError("push rejected")
        return original(root, *args)
    monkeypatch.setattr(release, "_git", fail_push)
    with pytest.raises(release.ReleaseError, match="push rejected"):
        release.publish(repo.path, remote="origin", dry_run=False)
    assert repo.git("rev-parse", "v0.1.0^{}").strip() == repo.head()
    monkeypatch.setattr(release, "_git", original)
    assert release.publish(repo.path, remote="origin", dry_run=False) == 0


@pytest.mark.parametrize("already_remote", [False, True])
def test_publish_preserves_existing_matching_lightweight_tags(publication, already_remote):
    repo, remote = publication
    repo.git("tag", "v0.1.0")
    if already_remote:
        repo.git("push", "origin", "refs/tags/v0.1.0")
        repo.git("tag", "-d", "v0.1.0")
    release.publish(repo.path, remote="origin", dry_run=False)
    assert repo.git("ls-remote", str(remote), "refs/tags/v0.1.0").split()[0] == repo.head()
    assert not repo.git("ls-remote", str(remote), "refs/tags/v0.1.0^{}").strip()


def test_publish_requires_exact_main_ref_not_a_suffix_match(publication, monkeypatch):
    repo, _ = publication
    original = release._git
    def decoy_main(root, *args):
        if args[0] == "ls-remote" and args[-1] == "refs/heads/main":
            return f"{repo.head()}\trefs/heads/decoy/refs/heads/main\n"
        return original(root, *args)
    monkeypatch.setattr(release, "_git", decoy_main)
    with pytest.raises(release.ReleaseError, match="HEAD must equal"):
        release.publish(repo.path, remote="origin", dry_run=False)
    assert not repo.git("tag", "--list", "v0.1.0").strip()


@pytest.mark.parametrize("argv", [["--publish", "--minor"], ["--remote", "origin"]])
def test_publication_arguments_cannot_accidentally_prepare_a_release(argv):
    with pytest.raises(SystemExit) as exc:
        release.main(argv)
    assert exc.value.code == 2


def test_publish_reports_failed_readback_and_preserves_local_tag(publication, monkeypatch):
    repo, _ = publication
    original = release._git
    tag_reads = 0
    def missing_readback(root, *args):
        nonlocal tag_reads
        if args[0] == "ls-remote" and args[-1].endswith("^{}"):
            tag_reads += 1
            if tag_reads == 2:
                return ""
        return original(root, *args)
    monkeypatch.setattr(release, "_git", missing_readback)
    with pytest.raises(release.ReleaseError, match="cannot verify remote"):
        release.publish(repo.path, remote="origin", dry_run=False)
    assert repo.git("rev-parse", "v0.1.0^{}").strip() == repo.head()


@pytest.mark.parametrize(
    ("destination", "expected"),
    [
        ("git@github.com:owner/plan-tool.git", "owner/plan-tool"),
        ("git@github.com:owner/plan-tool", "owner/plan-tool"),
        ("https://github.com/owner/plan-tool.git", "owner/plan-tool"),
        ("ssh://git@github.com/owner/plan-tool.git", "owner/plan-tool"),
        ("git@ssh.bitbucket.org:team/plan-tool.git", None),
        ("/tmp/remote.git", None),
    ],
)
def test_github_repository_is_recognized_only_for_github_push_urls(destination, expected) -> None:
    assert release.github_repository(destination) == expected


def test_release_notes_are_the_versions_section_without_its_heading() -> None:
    changelog = (
        "# Changelog\n\n<a id='changelog-0.2.0'></a>\n## 0.2.0 — 2026-11-06\n\n"
        "### Added\n\n- New.\n\n<a id='changelog-0.1.0'></a>\n## 0.1.0\n\n- Old.\n"
    )

    assert release.release_notes(changelog, "0.2.0") == "### Added\n\n- New.\n"


class _FakeGh:
    """Records gh calls; `existing` says whether `release view` finds a release."""

    def __init__(self, *, existing: bool = False, create_rc: int = 0) -> None:
        self.existing = existing
        self.create_rc = create_rc
        self.calls: list[tuple[str, ...]] = []
        self.notes: str | None = None

    def __call__(self, root: Path, *args: str) -> subprocess.CompletedProcess[str]:
        self.calls.append(args)
        if args[:2] == ("release", "view"):
            return subprocess.CompletedProcess(args, 0 if self.existing else 1, "", "")
        if args[:2] == ("release", "create"):
            self.notes = Path(args[args.index("--notes-file") + 1]).read_text(encoding="utf-8")
            return subprocess.CompletedProcess(args, self.create_rc, "", "boom" if self.create_rc else "")
        raise AssertionError(f"unexpected gh call {args}")

    def created(self) -> list[tuple[str, ...]]:
        return [call for call in self.calls if call[:2] == ("release", "create")]


@pytest.fixture
def github_publication(publication, monkeypatch):
    repo, remote = publication
    repo.write(
        "CHANGELOG.md",
        CHANGELOG + "\n<a id='changelog-0.1.0'></a>\n## 0.1.0\n\n### Added\n\n- First.\n",
    )
    repo.commit_all("Release notes")
    repo.git("push", "origin", "main")
    monkeypatch.setattr(
        release,
        "github_repository",
        lambda destination: "owner/plan-tool" if destination == str(remote) else None,
    )
    return repo, remote


def test_publish_to_github_creates_the_release_from_the_changelog_section(github_publication, monkeypatch):
    repo, remote = github_publication
    gh = _FakeGh()
    monkeypatch.setattr(release, "_gh", gh)

    assert release.publish(repo.path, remote="origin", dry_run=False) == 0

    assert repo.git("ls-remote", str(remote), "refs/tags/v0.1.0^{}").split()[0] == repo.head()
    (create,) = gh.created()
    assert create[2:5] == ("v0.1.0", "-R", "owner/plan-tool")
    assert "--verify-tag" in create
    assert gh.notes == "### Added\n\n- First.\n"


def test_a_retry_after_the_tag_published_creates_the_missing_release(github_publication, monkeypatch):
    repo, _ = github_publication
    failing = _FakeGh(create_rc=1)
    monkeypatch.setattr(release, "_gh", failing)
    with pytest.raises(release.ReleaseError, match="is published but creating its GitHub release failed"):
        release.publish(repo.path, remote="origin", dry_run=False)

    gh = _FakeGh()
    monkeypatch.setattr(release, "_gh", gh)
    assert release.publish(repo.path, remote="origin", dry_run=False) == 0
    assert len(gh.created()) == 1


def test_an_existing_github_release_is_left_as_it_is(github_publication, monkeypatch):
    repo, _ = github_publication
    gh = _FakeGh(existing=True)
    monkeypatch.setattr(release, "_gh", gh)

    assert release.publish(repo.path, remote="origin", dry_run=False) == 0
    assert gh.created() == []


def test_publish_dry_run_makes_no_gh_call(github_publication, monkeypatch, capsys):
    repo, _ = github_publication
    gh = _FakeGh()
    monkeypatch.setattr(release, "_gh", gh)

    assert release.publish(repo.path, remote="origin", dry_run=True) == 0
    assert gh.calls == []
    assert "Ensure GitHub release v0.1.0 on owner/plan-tool" in capsys.readouterr().out


def test_a_missing_gh_leaves_the_tag_published_and_names_the_manual_command(github_publication, monkeypatch):
    repo, remote = github_publication

    def no_gh(root, *args):
        raise release.ReleaseError("'gh' is not on PATH")

    monkeypatch.setattr(release, "_gh", no_gh)
    with pytest.raises(release.ReleaseError, match="gh release create v0.1.0 -R owner/plan-tool"):
        release.publish(repo.path, remote="origin", dry_run=False)
    assert repo.git("ls-remote", str(remote), "refs/tags/v0.1.0^{}").split()[0] == repo.head()


def test_publish_to_a_non_github_remote_makes_no_gh_call(publication, monkeypatch):
    repo, _ = publication
    gh = _FakeGh()
    monkeypatch.setattr(release, "_gh", gh)

    assert release.publish(repo.path, remote="origin", dry_run=False) == 0
    assert gh.calls == []
