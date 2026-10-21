"""Tests for ``plan_tool.pathutil`` — the shared read-only path helpers."""

from __future__ import annotations

from pathlib import Path

from plan_tool.pathutil import (
    display_path,
    is_within,
    latest_seed_archive,
    literal_path,
    normalize_declared_path,
)


class TestIsWithin:
    def test_true_for_a_nested_path(self, tmp_path: Path) -> None:
        assert is_within(tmp_path / "a" / "b.md", tmp_path) is True

    def test_true_for_the_root_itself(self, tmp_path: Path) -> None:
        assert is_within(tmp_path, tmp_path) is True

    def test_false_for_a_sibling_tree(self, tmp_path: Path) -> None:
        root = tmp_path / "repo"
        root.mkdir()
        assert is_within(tmp_path / "elsewhere" / "x.md", root) is False

    def test_resolves_before_comparing(self, tmp_path: Path) -> None:
        """``..`` is judged by where it lands, not how it is spelled."""
        root = tmp_path / "repo"
        (root / "sub").mkdir(parents=True)
        assert is_within(root / "sub" / ".." / "x.md", root) is True
        assert is_within(root / ".." / "x.md", root) is False


class TestDisplayPath:
    def test_renders_repo_relative(self, tmp_path: Path) -> None:
        assert display_path(tmp_path / "docs" / "p.md", tmp_path) == str(
            Path("docs") / "p.md"
        )

    def test_absolute_when_no_repo_root(self, tmp_path: Path) -> None:
        target = tmp_path / "p.md"
        assert display_path(target, None) == str(target)

    def test_absolute_when_outside_the_repo(self, tmp_path: Path) -> None:
        root = tmp_path / "repo"
        root.mkdir()
        outside = tmp_path / "other" / "p.md"
        assert display_path(outside, root) == str(outside)

    def test_resolves_through_a_dangling_symlink_to_its_missing_target(
        self, tmp_path: Path
    ) -> None:
        """Pins the half of literal_path's docstring contrast that lived
        untested: display_path follows the link and names the (nonexistent)
        target, "missing.md", not the link itself, "dangling.md"."""
        root = tmp_path / "repo"
        root.mkdir()
        link = root / "dangling.md"
        link.symlink_to(root / "missing.md")

        assert display_path(link, root) == "missing.md"


class TestLiteralPath:
    def test_renders_repo_relative(self, tmp_path: Path) -> None:
        assert literal_path(tmp_path / "docs" / "p.md", tmp_path) == str(
            Path("docs") / "p.md"
        )

    def test_falls_back_to_the_string_form_outside_the_repo(
        self, tmp_path: Path
    ) -> None:
        root = tmp_path / "repo"
        root.mkdir()
        outside = tmp_path / "other" / "p.md"
        assert literal_path(outside, root) == str(outside)

    def test_preserves_dangling_symlink_lexical_path(self, tmp_path: Path) -> None:
        root = tmp_path / "repo"
        root.mkdir()
        link = root / "dangling.md"
        link.symlink_to(root / "missing.md")

        assert literal_path(link, root) == "dangling.md"


class TestLatestSeedArchive:
    """Shared with ``roadmap.py`` (moved here from a private copy) and now
    also ``review_persistence.py``'s seed-drift fallback (BACKLOG #162)."""

    def test_none_when_no_archive_dir(self, tmp_path: Path) -> None:
        assert latest_seed_archive(tmp_path / "notes.md") is None

    def test_finds_the_base_generation(self, tmp_path: Path) -> None:
        archive = tmp_path / "archive"
        archive.mkdir()
        target = archive / "notes.replaced.md"
        target.write_text("archived", encoding="utf-8")

        assert latest_seed_archive(tmp_path / "notes.md") == target

    def test_picks_the_newest_numbered_generation(self, tmp_path: Path) -> None:
        import os
        import time

        archive = tmp_path / "archive"
        archive.mkdir()
        base = archive / "notes.replaced.md"
        base.write_text("gen 0", encoding="utf-8")
        newest = archive / "notes.replaced.2.md"
        newest.write_text("gen 2", encoding="utf-8")
        older = archive / "notes.replaced.1.md"
        older.write_text("gen 1", encoding="utf-8")
        # mtime is the tiebreaker, not filename sort — make it unambiguous.
        now = time.time()
        os.utime(base, (now, now))
        os.utime(older, (now + 1, now + 1))
        os.utime(newest, (now + 2, now + 2))

        assert latest_seed_archive(tmp_path / "notes.md") == newest

    def test_ignores_a_different_stem_or_suffix(self, tmp_path: Path) -> None:
        archive = tmp_path / "archive"
        archive.mkdir()
        (archive / "other.replaced.md").write_text("x", encoding="utf-8")
        (archive / "notes.replaced.txt").write_text("x", encoding="utf-8")

        assert latest_seed_archive(tmp_path / "notes.md") is None


class TestNormalizeDeclaredPath:
    def test_unifies_dotted_and_creation_spellings(self) -> None:
        """Ownership comparison must not split one path across declaration styles."""
        assert {
            normalize_declared_path("foo.py"),
            normalize_declared_path("./foo.py"),
            normalize_declared_path("foo.py (new)"),
        } == {"foo.py"}

    def test_preserves_dotdot_for_resolve_time_symlink_awareness(self) -> None:
        """A ``..`` segment must reach ``Path.resolve()`` unresolved.

        Collapsing it lexically here (rather than at resolve time) would let
        a ``..`` through a symlinked directory land somewhere ``.resolve()``
        would never actually reach — see :func:`is_within`.
        """
        assert (
            normalize_declared_path("linked_dir/../real_file.py")
            == "linked_dir/../real_file.py"
        )


def test_console_reexports_are_the_shared_implementations() -> None:
    """``app`` re-exports these names and the package-surface test pins them.

    Binding rather than re-implementing is what keeps them from drifting
    back apart.
    """
    from plan_tool.cli.console import _is_within, _short_path

    assert _is_within is is_within
    assert _short_path is display_path
