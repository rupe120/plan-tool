"""Drift guard for the generated CLI reference under ``docs/cli/``.

The reference set is produced from the live argparse parser by
``plan_tool.cli_reference``; these tests assert the committed files match
what the generator emits today, so a flag/help change that isn't
re-baselined fails CI rather than silently rotting the docs. Re-baseline
an intentional CLI change with::

    python -m plan_tool.cli_reference --write
"""

from __future__ import annotations

import argparse

import pytest

from plan_tool import cli_reference


def test_roadmap_reference_no_longer_documents_the_removed_structural_rewrite_route() -> None:
    """The escalation, impact-analysis, and exact-pair rewrite routes are gone, so the reference names none."""
    reference = cli_reference.render_reference()["roadmap.md"]

    for removed in (
        "--rewrite-structural",
        "--rewrite-analysis",
        "--escalate-feedback",
        "--analyze-escalation",
        "same-artifact",
        "cross-artifact",
    ):
        assert removed not in reference


def test_roadmap_reference_documents_structural_approval_lifecycle() -> None:
    """Render the parser-owned structural decision surface without publication claims."""
    reference = cli_reference.render_reference()["roadmap.md"]

    for boundary in (
        "--decide-candidate",
        "--candidate-decision",
        "one structural candidate choice: approve, edit, or reject",
        "--promote-review-seal",
    ):
        assert boundary in reference


class TestCliReferenceDrift:
    def test_tristate_boolean_default_renders_unset(self) -> None:
        """An unset BooleanOptionalAction is neither the on nor off arm."""
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--reuse", action=argparse.BooleanOptionalAction, default=None
        )
        action = next(
            action for action in parser._actions if action.dest == "reuse"
        )
        assert cli_reference._format_default(action) == "—"

    def test_reference_dir_exists(self) -> None:
        assert cli_reference.REFERENCE_DIR.is_dir(), (
            "docs/cli/ missing — run `python -m plan_tool.cli_reference --write`"
        )

    def test_every_generated_file_matches_disk(self) -> None:
        """Each generated file is present on disk and byte-identical."""
        rendered = cli_reference.render_reference()
        mismatches: list[str] = []
        for filename, expected in rendered.items():
            path = cli_reference.REFERENCE_DIR / filename
            if not path.exists():
                mismatches.append(f"{filename} (missing on disk)")
            elif path.read_text(encoding="utf-8") != expected:
                mismatches.append(f"{filename} (stale content)")
        assert not mismatches, (
            "CLI reference is stale — run "
            "`python -m plan_tool.cli_reference --write`: "
            + ", ".join(mismatches)
        )

    def test_no_orphan_reference_files(self) -> None:
        """No committed ``*.md`` lacks a generator counterpart (renamed cmd)."""
        rendered = set(cli_reference.render_reference())
        on_disk = {p.name for p in cli_reference.REFERENCE_DIR.glob("*.md")}
        orphans = sorted(on_disk - rendered)
        assert not orphans, (
            "orphaned CLI reference files (command renamed/removed?) — "
            "delete them and re-run the generator: " + ", ".join(orphans)
        )

    def test_every_subcommand_has_a_reference_file(self) -> None:
        import argparse

        import plan_tool.cli as cli

        parser = cli.build_parser()
        action = cli_reference._subparsers_action(parser)
        rendered = cli_reference.render_reference()
        for pseudo in action._choices_actions:
            assert f"{pseudo.dest}.md" in rendered, (
                f"no reference rendered for subcommand {pseudo.dest!r}"
            )
        assert "README.md" in rendered

    def test_index_links_every_command(self) -> None:
        rendered = cli_reference.render_reference()
        index = rendered["README.md"]
        for filename in rendered:
            if filename == "README.md":
                continue
            name = filename[: -len(".md")]
            assert f"]({name}.md)" in index, f"{name} missing from index"

    def test_scope_review_reference_is_generated(self) -> None:
        rendered = cli_reference.render_reference()
        assert "scope-review.md" in rendered
        assert "scope-review" in rendered["README.md"]

    def test_retired_direct_verbs_have_no_generated_reference(self) -> None:
        rendered = cli_reference.render_reference()
        assert "direct-jira.md" not in rendered
        assert "direct-run.md" not in rendered
        index = rendered["README.md"]
        assert "](direct-jira.md)" not in index
        assert "](direct-run.md)" not in index
