"""Tests for plan_tool.reprocess — TODO-fill from archive predecessor.

`reprocess` is the cheap counterpart to `create --iterate`: when a
previous create left `_(TODO)_` placeholders in body sections and the
predecessor still exists under ``<plan-dir>/archive/``, the helper
lifts the archive's H2 bodies into the live plan without a Claude
call. These tests cover the archive lookup, the section-by-section
substitution rules, and the wired ``create --reprocess`` CLI path.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from plan_tool.cli import main
from plan_tool.reprocess import (
    ReprocessError,
    ReprocessResult,
    find_archive_for_slug,
    reprocess_plan,
)


_VALID_FRONTMATTER = (
    "---\n"
    "title: Demo Plan\n"
    "status: planning\n"
    "priority: medium\n"
    "steps:\n"
    "  - id: 1\n"
    "    title: First step\n"
    "---\n"
)


def _write_plan_with_todos(path: Path) -> None:
    """A live plan with TODOs in Overview / Risks, populated References,
    and a Steps section that points at frontmatter. Used to assert the
    three substitution outcomes (filled, skipped, unfilled)."""
    path.write_text(
        _VALID_FRONTMATTER
        + "# Demo Plan\n"
        + "\n"
        + "## Overview\n"
        + "\n"
        + "_(TODO)_\n"
        + "\n"
        + "## Risks\n"
        + "\n"
        + "_(TODO)_\n"
        + "\n"
        + "## References\n"
        + "\n"
        + "- [pre-populated reference](https://example.com)\n"
        + "\n"
        + "## Steps\n"
        + "\n"
        + "See the `steps:` block in the frontmatter.\n"
        + "\n"
        + "## Unmatched Section\n"
        + "\n"
        + "_(TODO)_\n",
        encoding="utf-8",
    )


def _write_archive(path: Path) -> None:
    """Matching archive with Overview + Risks populated, but no
    Unmatched Section — so the substitution fills Overview/Risks,
    leaves References and Steps alone, and reports Unmatched as
    unfilled."""
    path.write_text(
        "# Demo Plan (predecessor)\n"
        "\n"
        "## Overview\n"
        "\n"
        "Lifted overview prose from the archive.\n"
        "\n"
        "## Risks\n"
        "\n"
        "- Risk one\n"
        "- Risk two\n"
        "\n"
        "## Steps\n"
        "\n"
        "### 1. archived step prose (should NEVER overwrite Steps)\n"
        "\n"
        "## References\n"
        "\n"
        "- [archived ref that must not clobber the live one](https://nope)\n",
        encoding="utf-8",
    )


class TestFindArchiveForSlug:
    def test_returns_none_when_no_archive_dir(self, tmp_path: Path) -> None:
        plan = tmp_path / "plans" / "2-demo.md"
        plan.parent.mkdir()
        plan.write_text("placeholder", encoding="utf-8")
        assert find_archive_for_slug(plan, "demo") is None

    def test_returns_none_when_no_slug_match(self, tmp_path: Path) -> None:
        plans = tmp_path / "plans"
        plans.mkdir()
        plan = plans / "2-demo.md"
        plan.write_text("placeholder", encoding="utf-8")
        archive_dir = plans / "archive"
        archive_dir.mkdir()
        (archive_dir / "other.replaced.md").write_text("x", encoding="utf-8")
        assert find_archive_for_slug(plan, "demo") is None

    def test_finds_unprefixed_match(self, tmp_path: Path) -> None:
        plans = tmp_path / "plans"
        plans.mkdir()
        plan = plans / "2-demo.md"
        plan.write_text("placeholder", encoding="utf-8")
        archive_dir = plans / "archive"
        archive_dir.mkdir()
        target = archive_dir / "demo.replaced.md"
        target.write_text("x", encoding="utf-8")
        assert find_archive_for_slug(plan, "demo") == target

    def test_finds_priority_prefixed_match(self, tmp_path: Path) -> None:
        plans = tmp_path / "plans"
        plans.mkdir()
        plan = plans / "2-demo.md"
        plan.write_text("placeholder", encoding="utf-8")
        archive_dir = plans / "archive"
        archive_dir.mkdir()
        target = archive_dir / "1-demo.replaced.md"
        target.write_text("x", encoding="utf-8")
        assert find_archive_for_slug(plan, "demo") == target

    def test_finds_legacy_double_digit_prefix(self, tmp_path: Path) -> None:
        plans = tmp_path / "plans"
        plans.mkdir()
        plan = plans / "2-demo.md"
        plan.write_text("placeholder", encoding="utf-8")
        archive_dir = plans / "archive"
        archive_dir.mkdir()
        target = archive_dir / "12-demo.replaced.md"
        target.write_text("x", encoding="utf-8")
        assert find_archive_for_slug(plan, "demo") == target

    def test_returns_most_recent_when_multiple_match(
        self, tmp_path: Path
    ) -> None:
        plans = tmp_path / "plans"
        plans.mkdir()
        plan = plans / "2-demo.md"
        plan.write_text("placeholder", encoding="utf-8")
        archive_dir = plans / "archive"
        archive_dir.mkdir()
        older = archive_dir / "demo.replaced.md"
        older.write_text("old", encoding="utf-8")
        newer = archive_dir / "1-demo.replaced.md"
        newer.write_text("new", encoding="utf-8")
        # Force newer mtime.
        future = time.time() + 60
        os.utime(newer, (future, future))
        assert find_archive_for_slug(plan, "demo") == newer

    def test_does_not_match_suffix(self, tmp_path: Path) -> None:
        """Regression guard: looking up slug 'bar' must not match
        'foo-bar.replaced.md'."""
        plans = tmp_path / "plans"
        plans.mkdir()
        plan = plans / "2-bar.md"
        plan.write_text("placeholder", encoding="utf-8")
        archive_dir = plans / "archive"
        archive_dir.mkdir()
        (archive_dir / "foo-bar.replaced.md").write_text("x", encoding="utf-8")
        assert find_archive_for_slug(plan, "bar") is None


class TestReprocessPlan:
    def test_rejects_unmatched_fence_in_live_or_archive_without_mutation(
        self, tmp_path: Path
    ) -> None:
        plan = tmp_path / "2-demo.md"
        archive = tmp_path / "demo.replaced.md"
        _write_plan_with_todos(plan)
        _write_archive(archive)

        for unsafe_path in (plan, archive):
            unsafe_path.write_text(
                unsafe_path.read_text(encoding="utf-8") + "\n```\n",
                encoding="utf-8",
            )
            before_plan = plan.read_text(encoding="utf-8")
            with pytest.raises(ReprocessError, match="unmatched opening code fence"):
                reprocess_plan(plan, archive)
            assert plan.read_text(encoding="utf-8") == before_plan
            unsafe_path.write_text(
                unsafe_path.read_text(encoding="utf-8").removesuffix("\n```\n"),
                encoding="utf-8",
            )

    def test_fills_todos_skips_populated_skips_steps(
        self, tmp_path: Path
    ) -> None:
        plan = tmp_path / "2-demo.md"
        archive = tmp_path / "demo.replaced.md"
        _write_plan_with_todos(plan)
        _write_archive(archive)

        result = reprocess_plan(plan, archive)

        assert isinstance(result, ReprocessResult)
        assert result.filled == ["Overview", "Risks"]
        # References was already populated → skipped (and Steps is
        # always skipped via the _NEVER_SUBSTITUTE guard).
        assert "References" in result.skipped
        assert "Steps" in result.skipped
        # Unmatched H2 with TODO body but no archive match → unfilled.
        assert result.unfilled == ["Unmatched Section"]

        body = plan.read_text(encoding="utf-8")
        # Overview lifted from archive.
        assert "Lifted overview prose from the archive." in body
        # Risks lifted as bullet list.
        assert "- Risk one" in body
        assert "- Risk two" in body
        # References preserved — archive's competing ref must NOT land.
        assert "[pre-populated reference]" in body
        assert "archived ref that must not clobber" not in body
        # Steps body stays the pointer line — archive's step prose
        # never lands in the body.
        assert "See the `steps:` block in the frontmatter." in body
        assert "archived step prose (should NEVER overwrite Steps)" not in body
        # Unmatched section's TODO stays.
        assert body.count("_(TODO)_") == 1

    def test_substitute_todo_sections_ignores_closed_fenced_pseudo_heading(self) -> None:
        from plan_tool.reprocess import _substitute_todo_sections

        body = (
            "```markdown\n## Risks\n\n_(TODO)_\n```\n\n"
            "## Overview\n\n_(TODO)_\n"
        )
        rewritten, meta = _substitute_todo_sections(
            body, {"overview": "Real replacement.", "risks": "Must stay fenced."}
        )

        assert meta["filled"] == ["Overview"]
        assert "Real replacement." in rewritten
        assert "```markdown\n## Risks\n\n_(TODO)_\n```" in rewritten

    def test_preserves_frontmatter_byte_for_byte(self, tmp_path: Path) -> None:
        plan = tmp_path / "2-demo.md"
        archive = tmp_path / "demo.replaced.md"
        _write_plan_with_todos(plan)
        _write_archive(archive)
        before_fm = plan.read_text(encoding="utf-8").split("---\n", 2)
        assert len(before_fm) >= 3  # opening + yaml + closing remainder

        reprocess_plan(plan, archive)

        after_fm = plan.read_text(encoding="utf-8").split("---\n", 2)
        # First two segments (pre-fence-blank + yaml block) identical.
        assert after_fm[0] == before_fm[0]
        assert after_fm[1] == before_fm[1]

    def test_no_todos_raises(self, tmp_path: Path) -> None:
        plan = tmp_path / "2-demo.md"
        archive = tmp_path / "demo.replaced.md"
        plan.write_text(
            _VALID_FRONTMATTER
            + "# Demo Plan\n\n## Overview\n\nAlready filled.\n",
            encoding="utf-8",
        )
        _write_archive(archive)
        with pytest.raises(ReprocessError, match="no `_\\(TODO\\)_` sections"):
            reprocess_plan(plan, archive)

    def test_missing_plan_raises(self, tmp_path: Path) -> None:
        plan = tmp_path / "missing.md"
        archive = tmp_path / "demo.replaced.md"
        _write_archive(archive)
        with pytest.raises(ReprocessError, match="plan file not found"):
            reprocess_plan(plan, archive)

    def test_missing_archive_raises(self, tmp_path: Path) -> None:
        plan = tmp_path / "2-demo.md"
        _write_plan_with_todos(plan)
        with pytest.raises(ReprocessError, match="archive file not found"):
            reprocess_plan(plan, tmp_path / "missing.replaced.md")

    def test_archive_with_empty_section_leaves_todo(
        self, tmp_path: Path
    ) -> None:
        """An archive H2 with an empty body must NOT clobber the live
        plan's TODO — the substitution falls through to unfilled."""
        plan = tmp_path / "2-demo.md"
        archive = tmp_path / "demo.replaced.md"
        _write_plan_with_todos(plan)
        archive.write_text(
            "# Predecessor\n\n## Overview\n\n\n## Risks\n\n\n",
            encoding="utf-8",
        )
        result = reprocess_plan(plan, archive)
        assert "Overview" in result.unfilled
        assert "Risks" in result.unfilled
        assert result.filled == []


@pytest.mark.integration
class TestCmdCreateReprocess:
    """End-to-end through ``main()``: ``create <slug> --reprocess``
    resolves the registered plan, finds the archive, runs the
    substitution, and prints the report."""

    def _seed_repo(
        self, tmp_path: Path
    ) -> tuple[Path, Path, Path, Path]:
        (tmp_path / ".git").mkdir()
        plans = tmp_path / "plans"
        plans.mkdir()
        archive_dir = plans / "archive"
        archive_dir.mkdir()
        plan = plans / "2-demo.md"
        _write_plan_with_todos(plan)
        archive = archive_dir / "demo.replaced.md"
        _write_archive(archive)
        manifest = tmp_path / "m.json"
        manifest.write_text(
            json.dumps({"plans": ["plans/2-demo.md"]}), encoding="utf-8"
        )
        return tmp_path, plan, archive, manifest

    def test_happy_path_fills_and_reports(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        repo, plan, _archive, manifest = self._seed_repo(tmp_path)
        rc = main([
            "--repo-root", str(repo),
            "--manifest", str(manifest),
            "create", "demo", "--reprocess",
        ])
        assert rc == 0
        out = capsys.readouterr().out
        assert "reprocessed" in out
        assert "filled (2)" in out
        assert "Overview" in out
        assert "Risks" in out
        # Body actually mutated.
        body = plan.read_text(encoding="utf-8")
        assert "Lifted overview prose from the archive." in body

    def test_missing_archive_exits_with_error(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        (tmp_path / ".git").mkdir()
        plans = tmp_path / "plans"
        plans.mkdir()
        plan = plans / "2-demo.md"
        _write_plan_with_todos(plan)
        manifest = tmp_path / "m.json"
        manifest.write_text(
            json.dumps({"plans": ["plans/2-demo.md"]}), encoding="utf-8"
        )
        rc = main([
            "--repo-root", str(tmp_path),
            "--manifest", str(manifest),
            "create", "demo", "--reprocess",
        ])
        assert rc == 1
        err = capsys.readouterr().err
        assert "no archive matching slug 'demo'" in err

    def test_unregistered_slug_emits_orphan_hint(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When the slug isn't in the manifest, the standard
        orphan-hint surface fires (no special-casing in reprocess)."""
        (tmp_path / ".git").mkdir()
        plans = tmp_path / "plans"
        plans.mkdir()
        registered = plans / "1-other.md"
        _write_plan_with_todos(registered)
        # demo lives on disk but isn't in the manifest → orphan path.
        orphan = plans / "2-demo.md"
        _write_plan_with_todos(orphan)
        manifest = tmp_path / "m.json"
        manifest.write_text(
            json.dumps({"plans": ["plans/1-other.md"]}), encoding="utf-8"
        )
        rc = main([
            "--repo-root", str(tmp_path),
            "--manifest", str(manifest),
            "create", "demo", "--reprocess",
        ])
        assert rc == 1
        err = capsys.readouterr().err
        assert "no plan matching 'demo'" in err
        assert "plan-tool register" in err
