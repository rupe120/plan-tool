"""Fixtures for the ``tests/cli/`` package-surface and command tests.

These fixtures exist to keep the CLI tests **split-proof**: every test
in this package drives the CLI through its public seams — ``main(argv)``
with a temp repo + manifest, or ``build_parser()`` — instead of reaching
into ``plan_tool.cli`` module globals. See ``test_package_surface.py``'s
module docstring for the full rationale; the short version is that the
upcoming "split cli.py into an intent-grouped package" refactor will move
functions between modules, so any test that ``setattr``\\s a cli-module
global, or imports a private helper only to monkeypatch it, would break
on the move even though behavior is unchanged.

The :class:`CliRepo` helper builds a throwaway git repo with a
``structured_plans.json``-style manifest. ``main()`` is then driven with
``repo.argv("list")`` etc., so the test exercises the real
parse → dispatch → command path end to end. To stub a dependency
(``claude`` calls, network), monkeypatch the *domain* module that owns it
(``plan_tool.launcher``, ``plan_tool.shell``, …) — never a name re-exported
into ``plan_tool.cli``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import json

import pytest


def _minimal_plan_text(*, title: str, status: str, priority: str) -> str:
    """Smallest frontmatter that satisfies :class:`plan_tool.schema.Plan`.

    Title / status / priority and a single step are the only required
    fields; everything else is optional, so this is the leanest plan that
    ``parse_plan`` / the ``Plan`` model will accept.
    """
    return (
        "---\n"
        f"title: {title}\n"
        f"status: {status}\n"
        f"priority: {priority}\n"
        "steps:\n"
        "  - id: 1\n"
        "    title: Only step\n"
        "---\n"
        "# Body\n"
    )


@dataclass
class CliRepo:
    """A temp git repo + manifest, plus argv helpers for driving ``main``.

    Attributes
    ----------
    root:
        Repo root (contains a stub ``.git`` so repo-root discovery and
        ``.plan-tool/`` caches land here).
    plans_dir:
        Directory the plan ``*.md`` files live in.
    manifest_path:
        Path to the ``structured_plans.json``-style manifest. The file
        is (re)written by :meth:`write_manifest` to list every plan added
        via :meth:`add_plan`.
    """

    root: Path
    plans_dir: Path
    manifest_path: Path
    plans: list[Path] = field(default_factory=list)

    def add_plan(
        self,
        stem: str,
        *,
        title: str = "Test Plan",
        status: str = "planning",
        priority: str = "low",
    ) -> Path:
        """Write a minimal valid plan file under ``plans_dir`` and register it.

        Returns the plan's path. Call :meth:`write_manifest` (or rely on
        :func:`registered_plan`) to flush the manifest after adding plans.
        """
        path = self.plans_dir / f"{stem}.md"
        path.write_text(
            _minimal_plan_text(title=title, status=status, priority=priority),
            encoding="utf-8",
        )
        self.plans.append(path)
        return path

    def write_manifest(self) -> Path:
        """Write the manifest listing every plan added so far (repo-relative)."""
        rels = [str(p.relative_to(self.root)) for p in self.plans]
        self.manifest_path.write_text(
            json.dumps({"plans": rels}), encoding="utf-8"
        )
        return self.manifest_path

    def argv(self, *args: str) -> list[str]:
        """Build an argv that pins this repo + manifest, then appends ``args``.

        The pinned global flags (``--repo-root`` / ``--manifest``) keep
        ``main()`` off the ambient cwd-discovery path, so the test is
        hermetic regardless of where pytest runs.
        """
        return [
            "--repo-root",
            str(self.root),
            "--manifest",
            str(self.manifest_path),
            *args,
        ]


@pytest.fixture
def tmp_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> CliRepo:
    """An empty git repo with a plans dir and an empty written manifest."""
    monkeypatch.delenv("PLAN_TOOL_PLANS_DIR", raising=False)
    monkeypatch.delenv("PLAN_TOOL_REPO_ROOT", raising=False)
    (tmp_path / ".git").mkdir()
    plans_dir = tmp_path / "plans"
    plans_dir.mkdir()
    repo = CliRepo(
        root=tmp_path,
        plans_dir=plans_dir,
        manifest_path=tmp_path / "structured_plans.json",
    )
    repo.write_manifest()
    return repo


@pytest.fixture
def registered_plan(tmp_repo: CliRepo) -> CliRepo:
    """A repo with one planning-status plan ``1-demo`` registered in the manifest."""
    tmp_repo.add_plan("1-demo", title="Demo Plan")
    tmp_repo.write_manifest()
    return tmp_repo
