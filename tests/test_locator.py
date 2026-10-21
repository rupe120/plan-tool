"""Tests for plan_tool.locator."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from plan_tool.locator import (
    PLANS_SUBPATH,
    ManifestError,
    PlanEntry,
    build_plan_tool_context,
    collect_git_ancestors,
    collect_plan_entries,
    collect_project_root_ancestors,
    find_plans_dir,
    find_repo_root,
    find_repo_root_candidates,
    find_repo_root_from_cwd,
    find_umbrella_root,
    list_plans,
    list_plans_from_manifest,
    load_known_roots,
    load_manifest_plan_paths,
    record_known_root,
    resolve_explicit_plans_dir,
    resolve_plan,
    resolve_registered_plan,
    resolve_repo_root,
)


def _make_plan_file(dir_: Path, name: str, *, valid: bool = True) -> Path:
    path = dir_ / name
    if valid:
        path.write_text(
            "---\n"
            "title: Test Plan\n"
            "status: planning\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Only step\n"
            "---\n"
            "# Body\n",
            encoding="utf-8",
        )
    else:
        path.write_text(
            "---\n"
            "priority: low\n"  # missing title, status
            "---\n",
            encoding="utf-8",
        )
    return path


def _make_unstructured_plan(dir_: Path, name: str) -> Path:
    path = dir_ / name
    path.write_text("# Unstructured Plan\n\nNo frontmatter here.\n", encoding="utf-8")
    return path


class TestFindRepoRoot:
    def test_finds_git_ancestor_from_docs_plans_dir(self, tmp_path: Path) -> None:
        plans = tmp_path / "docs" / "implementation-plans"
        plans.mkdir(parents=True)
        (tmp_path / ".git").mkdir()
        assert find_repo_root(plans) == tmp_path

    def test_finds_git_ancestor_from_agents_implementation_plans(
        self, tmp_path: Path
    ) -> None:
        agents_plans = tmp_path / ".agents" / "implementation-plans"
        agents_plans.mkdir(parents=True)
        (tmp_path / ".git").mkdir()
        assert find_repo_root(agents_plans) == tmp_path

    def test_falls_back_without_git(self, tmp_path: Path) -> None:
        plans = tmp_path / "docs" / "implementation-plans"
        plans.mkdir(parents=True)
        assert find_repo_root(plans) == tmp_path


class TestFindRepoRootFromCwd:
    def test_finds_git(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        assert find_repo_root_from_cwd() == tmp_path

    def test_finds_plan_tool_manifest(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # A ``.plan-tool/plans.json`` manifest marks a root even with no
        # ``.git``.
        (tmp_path / ".plan-tool").mkdir()
        (tmp_path / ".plan-tool" / "plans.json").write_text("{}")
        monkeypatch.chdir(tmp_path)
        assert find_repo_root_from_cwd() == tmp_path

    def test_bare_plan_tool_dir_is_not_a_root(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A ``.plan-tool`` directory WITHOUT ``plans.json`` is global/work
        # state (the ``~/.plan-tool`` known-roots cache + lessons, or a
        # per-run ``.plan-tool/runs`` work area), not a plan root. The walk
        # must not stop here — otherwise ``$HOME`` (which carries the
        # known-roots cache) would shadow every real repo root.
        (tmp_path / ".plan-tool").mkdir()  # no plans.json
        monkeypatch.chdir(tmp_path)
        with pytest.raises(FileNotFoundError, match=r"plans\.json"):
            find_repo_root_from_cwd()

    def test_nearest_marker_wins_over_ancestor_git(self, tmp_path: Path) -> None:
        # ``.git`` at the top, ``.plan-tool/plans.json`` deeper: the nearer
        # marker is the plan root, so the walk stops at the inner manifest.
        (tmp_path / ".git").mkdir()
        inner = tmp_path / "sub"
        inner.mkdir()
        (inner / ".plan-tool").mkdir()
        (inner / ".plan-tool" / "plans.json").write_text("{}")
        assert find_repo_root_from_cwd(start=inner) == inner.resolve()

    def test_raises_without_marker(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        with pytest.raises(FileNotFoundError, match=r"\.plan-tool"):
            find_repo_root_from_cwd()

    def test_finds_git_from_explicit_start(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        deep = tmp_path / "a" / "b"
        deep.mkdir(parents=True)
        assert find_repo_root_from_cwd(start=deep) == tmp_path.resolve()

    def test_error_message_uses_explicit_start(self, tmp_path: Path) -> None:
        deep = tmp_path / "a" / "b"
        deep.mkdir(parents=True)
        with pytest.raises(FileNotFoundError, match=str(deep)):
            find_repo_root_from_cwd(start=deep)


class TestFindPlansDir:
    def test_finds_direct_parent(self, tmp_path: Path) -> None:
        plans = tmp_path / "docs" / "implementation-plans"
        plans.mkdir(parents=True)
        found = find_plans_dir(start=tmp_path)
        assert found == plans

    def test_walks_up(self, tmp_path: Path) -> None:
        plans = tmp_path / "docs" / "implementation-plans"
        plans.mkdir(parents=True)
        deep = tmp_path / "a" / "b" / "c"
        deep.mkdir(parents=True)
        found = find_plans_dir(start=deep)
        assert found == plans

    def test_raises_when_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            find_plans_dir(start=tmp_path)


class TestListPlans:
    def test_returns_valid_plans(self, tmp_path: Path) -> None:
        plans_dir = tmp_path / PLANS_SUBPATH
        plans_dir.mkdir(parents=True)
        _make_plan_file(plans_dir, "1-alpha.md")
        _make_plan_file(plans_dir, "2-beta.md")
        entries = list_plans(plans_dir)
        assert len(entries) == 2
        assert all(e.plan is not None for e in entries)
        assert all(e.error is None for e in entries)

    def test_carries_unstructured_plans_as_malformed(self, tmp_path: Path) -> None:
        plans_dir = tmp_path / PLANS_SUBPATH
        plans_dir.mkdir(parents=True)
        _make_plan_file(plans_dir, "1-structured.md")
        _make_unstructured_plan(plans_dir, "2-legacy.md")
        entries = list_plans(plans_dir)
        assert len(entries) == 2
        by_name = {e.path.name: e for e in entries}
        assert by_name["1-structured.md"].plan is not None
        legacy = by_name["2-legacy.md"]
        assert legacy.plan is None
        assert legacy.error is not None

    def test_surfaces_malformed_plans(self, tmp_path: Path) -> None:
        plans_dir = tmp_path / PLANS_SUBPATH
        plans_dir.mkdir(parents=True)
        _make_plan_file(plans_dir, "3-broken.md", valid=False)
        entries = list_plans(plans_dir)
        assert len(entries) == 1
        assert entries[0].plan is None
        # Concise summary, not the raw pydantic dump: names the offending
        # field but drops the boilerplate header, '[type=...]' annotations,
        # and docs URL that str(ValidationError) carries.
        err = entries[0].error
        assert err is not None
        assert "title" in err
        assert "[type=" not in err
        assert "errors.pydantic.dev" not in err
        assert "validation error" not in err.lower()

    def test_results_are_sorted(self, tmp_path: Path) -> None:
        plans_dir = tmp_path / PLANS_SUBPATH
        plans_dir.mkdir(parents=True)
        _make_plan_file(plans_dir, "2-beta.md")
        _make_plan_file(plans_dir, "1-alpha.md")
        entries = list_plans(plans_dir)
        names = [e.path.name for e in entries]
        assert names == sorted(names)


class TestPlanEntrySlug:
    def test_strips_priority_prefix(self, tmp_path: Path) -> None:
        entry = PlanEntry(path=tmp_path / "1-foo-bar.md", plan=None, error=None)
        assert entry.slug == "foo-bar"

    def test_keeps_name_without_prefix(self, tmp_path: Path) -> None:
        entry = PlanEntry(path=tmp_path / "foo-bar.md", plan=None, error=None)
        assert entry.slug == "foo-bar"

    def test_only_strips_numeric_prefix(self, tmp_path: Path) -> None:
        entry = PlanEntry(path=tmp_path / "x-bar.md", plan=None, error=None)
        assert entry.slug == "x-bar"


class TestListPlansFromArbitraryDir:
    def test_lists_plans_in_flat_directory(self, tmp_path: Path) -> None:
        flat = tmp_path / "my-plans"
        flat.mkdir()
        _make_plan_file(flat, "demo.md")
        entries = list_plans(flat)
        assert len(entries) == 1
        assert entries[0].plan is not None


class TestResolveExplicitPlansDir:
    def test_override_wins_over_env(self, tmp_path: Path) -> None:
        override = tmp_path / "override"
        override.mkdir()
        env_dir = tmp_path / "from-env"
        env_dir.mkdir()
        got = resolve_explicit_plans_dir(
            override,
            environ={"PLAN_TOOL_PLANS_DIR": str(env_dir)},
        )
        assert got == override.resolve()

    def test_env_used_when_no_override(self, tmp_path: Path) -> None:
        env_dir = tmp_path / "agent-plans"
        env_dir.mkdir()
        got = resolve_explicit_plans_dir(
            None,
            environ={"PLAN_TOOL_PLANS_DIR": str(env_dir)},
        )
        assert got == env_dir.resolve()

    def test_raises_when_env_dir_missing(self, tmp_path: Path) -> None:
        missing = tmp_path / "nope"
        with pytest.raises(FileNotFoundError, match="PLAN_TOOL_PLANS_DIR"):
            resolve_explicit_plans_dir(
                None,
                environ={"PLAN_TOOL_PLANS_DIR": str(missing)},
            )

    def test_returns_none_when_unset(self, tmp_path: Path) -> None:
        assert (
            resolve_explicit_plans_dir(None, environ={"PLAN_TOOL_PLANS_DIR": ""})
            is None
        )


class TestManifestAndContext:
    def test_list_plans_from_manifest(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        pdir = tmp_path / "plans"
        pdir.mkdir()
        plan_path = _make_plan_file(pdir, "2-zed.md")
        manifest = tmp_path / "m.json"
        manifest.write_text(
            json.dumps({"plans": [str(plan_path.relative_to(tmp_path))]}),
            encoding="utf-8",
        )
        entries = list_plans_from_manifest(tmp_path, manifest_path=manifest)
        assert len(entries) == 1
        assert entries[0].path.resolve() == plan_path.resolve()

    def test_build_plan_tool_context_manifest_mode(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / ".git").mkdir()
        pdir = tmp_path / "plans"
        pdir.mkdir()
        plan_path = _make_plan_file(pdir, "1-alpha.md")
        manifest = tmp_path / "manifest.json"
        manifest.write_text(
            json.dumps({"plans": [str(plan_path.relative_to(tmp_path))]}),
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        ctx = build_plan_tool_context(
            None, environ={"PLAN_TOOL_PLANS_DIR": ""}, manifest_path=manifest
        )
        assert ctx.plans_dir is None
        assert ctx.repo_root == tmp_path.resolve()
        assert len(ctx.entries) == 1
        assert resolve_registered_plan(ctx.entries, "alpha") == plan_path.resolve()

    def test_build_plan_tool_context_dir_mode(self, tmp_path: Path) -> None:
        plans_dir = tmp_path / "flat"
        plans_dir.mkdir()
        (tmp_path / ".git").mkdir()
        _make_plan_file(plans_dir, "1-beta.md")
        ctx = build_plan_tool_context(plans_dir, environ={})
        assert ctx.plans_dir == plans_dir.resolve()
        assert resolve_plan(ctx.plans_dir, "beta").name == "1-beta.md"


class TestResolvePlan:
    def test_exact_match(self, tmp_path: Path) -> None:
        plans_dir = tmp_path / PLANS_SUBPATH
        plans_dir.mkdir(parents=True)
        path = _make_plan_file(plans_dir, "foo-bar.md")
        assert resolve_plan(plans_dir, "foo-bar") == path

    def test_with_md_extension(self, tmp_path: Path) -> None:
        plans_dir = tmp_path / PLANS_SUBPATH
        plans_dir.mkdir(parents=True)
        path = _make_plan_file(plans_dir, "foo-bar.md")
        assert resolve_plan(plans_dir, "foo-bar.md") == path

    def test_adds_priority_prefix(self, tmp_path: Path) -> None:
        plans_dir = tmp_path / PLANS_SUBPATH
        plans_dir.mkdir(parents=True)
        path = _make_plan_file(plans_dir, "2-foo-bar.md")
        assert resolve_plan(plans_dir, "foo-bar") == path

    def test_raises_when_not_found(self, tmp_path: Path) -> None:
        plans_dir = tmp_path / PLANS_SUBPATH
        plans_dir.mkdir(parents=True)
        with pytest.raises(FileNotFoundError):
            resolve_plan(plans_dir, "nope")


class TestResolveRegisteredPlanOrphanHint:
    """When a slug isn't in the manifest but a matching .md exists in the
    same directory as registered plans, the error must point at
    ``plan-tool register`` so users have a recovery path. Closes the
    "completeness says missing, create says exists" asymmetry that came
    from `find_collisions` scanning the filesystem while every other
    subcommand only sees the manifest.
    """

    def _registered(self, dir_: Path, name: str) -> PlanEntry:
        path = _make_plan_file(dir_, name)
        return PlanEntry(path=path.resolve(), plan=None, error=None)

    def test_hint_when_orphan_lives_with_registered_plans(
        self, tmp_path: Path
    ) -> None:
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        registered = self._registered(plans_dir, "1-alpha.md")
        orphan = _make_plan_file(plans_dir, "2-beta.md")
        with pytest.raises(FileNotFoundError) as excinfo:
            resolve_registered_plan([registered], "beta")
        msg = str(excinfo.value)
        assert "no plan matching 'beta'" in msg
        assert "hint:" in msg
        assert str(orphan) in msg
        assert "plan-tool register" in msg

    def test_no_hint_when_no_orphan_present(self, tmp_path: Path) -> None:
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        registered = self._registered(plans_dir, "1-alpha.md")
        with pytest.raises(FileNotFoundError) as excinfo:
            resolve_registered_plan([registered], "ghost")
        assert "hint:" not in str(excinfo.value)

    def test_no_hint_when_no_registered_entries(
        self, tmp_path: Path
    ) -> None:
        # Without any registered entries we have no candidate directory
        # to scan — so even an on-disk match wouldn't be surfaced.
        # That's acceptable; users without a populated manifest hit a
        # different code path (the ``--plans-dir`` mode).
        with pytest.raises(FileNotFoundError) as excinfo:
            resolve_registered_plan([], "anything")
        assert "hint:" not in str(excinfo.value)


class TestCollectPlanEntries:
    def test_carries_parse_error_as_malformed(self, tmp_path: Path) -> None:
        # No '---' fence at all: parse_plan raises ParseError, which the
        # locator now carries as a malformed entry rather than dropping.
        broken = tmp_path / "2-broken.md"
        broken.write_text("this is not valid frontmatter\n", encoding="utf-8")
        entries = collect_plan_entries([broken])
        assert len(entries) == 1
        entry = entries[0]
        assert entry.plan is None
        assert entry.error is not None
        assert "frontmatter fence" in entry.error
        # Slug strips the numeric priority prefix from the filename stem.
        assert entry.slug == "broken"

    def test_carries_invalid_yaml_as_malformed(self, tmp_path: Path) -> None:
        # A colon-trap scalar (`title: a: b`) is invalid YAML — "mapping
        # values are not allowed here" — so it raises ParseError, not
        # ValidationError. Covers the actual in-flight incident.
        broken = tmp_path / "2-broken.md"
        broken.write_text(
            "---\ntitle: a: b\n---\n# Body\n", encoding="utf-8"
        )
        entries = collect_plan_entries([broken])
        assert len(entries) == 1
        entry = entries[0]
        assert entry.plan is None
        assert entry.error is not None
        assert "invalid YAML in frontmatter" in entry.error

    def test_skips_non_md(self, tmp_path: Path) -> None:
        a = tmp_path / "a.md"
        a.write_text(
            "---\ntitle: A\nstatus: planning\npriority: low\n"
            "steps:\n  - id: 1\n    title: S\n---\n",
            encoding="utf-8",
        )
        b = tmp_path / "b.txt"
        b.write_text("x", encoding="utf-8")
        entries = collect_plan_entries([a, b])
        assert len(entries) == 1


class TestManifestErrors:
    def test_malformed_json_raises(self, tmp_path: Path) -> None:
        mf = tmp_path / "m.json"
        mf.write_text("{ not valid json", encoding="utf-8")
        with pytest.raises(ManifestError, match="invalid JSON"):
            load_manifest_plan_paths(tmp_path, manifest_path=mf)

    def test_non_list_plans_raises(self, tmp_path: Path) -> None:
        mf = tmp_path / "m.json"
        mf.write_text(json.dumps({"plans": "oops"}), encoding="utf-8")
        with pytest.raises(ManifestError, match="must be a list"):
            load_manifest_plan_paths(tmp_path, manifest_path=mf)

    def test_absolute_path_rejected(self, tmp_path: Path) -> None:
        mf = tmp_path / "m.json"
        mf.write_text(
            json.dumps({"plans": ["/abs/plan.md"]}), encoding="utf-8"
        )
        with pytest.raises(ManifestError, match="repo-relative"):
            load_manifest_plan_paths(tmp_path, manifest_path=mf)

    def test_missing_manifest_returns_empty(self, tmp_path: Path) -> None:
        """Absent manifest file is not an error — distinct from malformed."""
        missing = tmp_path / "does-not-exist.json"
        assert load_manifest_plan_paths(tmp_path, manifest_path=missing) == []


class TestContextMissingPaths:
    def test_populated_when_entry_does_not_exist(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / ".git").mkdir()
        pdir = tmp_path / "plans"
        pdir.mkdir()
        real = _make_plan_file(pdir, "1-real.md")
        manifest = tmp_path / "m.json"
        manifest.write_text(
            json.dumps(
                {
                    "plans": [
                        str(real.relative_to(tmp_path)),
                        "plans/ghost.md",
                    ]
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        ctx = build_plan_tool_context(
            None, environ={"PLAN_TOOL_PLANS_DIR": ""}, manifest_path=manifest
        )
        assert len(ctx.entries) == 1
        assert len(ctx.missing_paths) == 1
        assert ctx.missing_paths[0].name == "ghost.md"

    def test_empty_when_dir_mode(self, tmp_path: Path) -> None:
        plans_dir = tmp_path / "flat"
        plans_dir.mkdir()
        (tmp_path / ".git").mkdir()
        _make_plan_file(plans_dir, "1-beta.md")
        ctx = build_plan_tool_context(plans_dir, environ={})
        assert ctx.missing_paths == []


class TestResolveRepoRoot:
    def test_returns_override_when_given(self, tmp_path: Path) -> None:
        target = tmp_path / "project"
        target.mkdir()
        env_target = tmp_path / "from-env"
        env_target.mkdir()
        got = resolve_repo_root(
            target,
            environ={"PLAN_TOOL_REPO_ROOT": str(env_target)},
        )
        # Override beats env.
        assert got == target.resolve()

    def test_falls_back_to_env(self, tmp_path: Path) -> None:
        env_target = tmp_path / "project"
        env_target.mkdir()
        got = resolve_repo_root(
            None, environ={"PLAN_TOOL_REPO_ROOT": str(env_target)}
        )
        assert got == env_target.resolve()

    def test_returns_none_when_neither_set(self) -> None:
        assert resolve_repo_root(None, environ={}) is None

    def test_raises_for_nonexistent_override(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="--repo-root"):
            resolve_repo_root(tmp_path / "nope", environ={})

    def test_raises_for_nonexistent_env(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="PLAN_TOOL_REPO_ROOT"):
            resolve_repo_root(
                None,
                environ={"PLAN_TOOL_REPO_ROOT": str(tmp_path / "nope")},
            )

    def test_raises_when_override_is_a_file(self, tmp_path: Path) -> None:
        f = tmp_path / "not-a-dir.txt"
        f.write_text("x", encoding="utf-8")
        with pytest.raises(FileNotFoundError, match="not a directory"):
            resolve_repo_root(f, environ={})

    def test_raises_when_env_is_a_file(self, tmp_path: Path) -> None:
        f = tmp_path / "not-a-dir.txt"
        f.write_text("x", encoding="utf-8")
        with pytest.raises(FileNotFoundError, match="not a directory"):
            resolve_repo_root(None, environ={"PLAN_TOOL_REPO_ROOT": str(f)})

    def test_blank_env_treated_as_unset(self, tmp_path: Path) -> None:
        # Trailing whitespace must not produce a bogus path.
        assert resolve_repo_root(None, environ={"PLAN_TOOL_REPO_ROOT": "   "}) is None


class TestBuildContextWithRepoRootOverride:
    def test_override_used_in_manifest_mode(self, tmp_path: Path) -> None:
        # Project layout: repo_root contains the manifest target.
        repo_root = tmp_path / "project"
        plans_dir = repo_root / "implementation-plans"
        plans_dir.mkdir(parents=True)
        _make_plan_file(plans_dir, "1-alpha.md")
        manifest = tmp_path / "manifest.json"
        manifest.write_text(
            json.dumps({"plans": ["implementation-plans/1-alpha.md"]}),
            encoding="utf-8",
        )

        ctx = build_plan_tool_context(
            None,
            environ={},
            manifest_path=manifest,
            repo_root_override=repo_root,
        )
        assert ctx.repo_root == repo_root.resolve()
        assert len(ctx.entries) == 1
        assert ctx.missing_paths == []

    def test_override_ignores_walk_up_git(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When override points outside a nested ``.git``, the inner repo
        is irrelevant — this is the meta self-validation case."""
        outer = tmp_path / "outer"
        inner = outer / "inner"
        inner.mkdir(parents=True)
        # Both have .git — walk-up would prefer `inner`.
        (outer / ".git").mkdir()
        (inner / ".git").mkdir()
        plans_dir = outer / "implementation-plans"
        plans_dir.mkdir(parents=True)
        _make_plan_file(plans_dir, "1-alpha.md")
        manifest = tmp_path / "manifest.json"
        manifest.write_text(
            json.dumps({"plans": ["implementation-plans/1-alpha.md"]}),
            encoding="utf-8",
        )
        monkeypatch.chdir(inner)

        ctx = build_plan_tool_context(
            None,
            environ={},
            manifest_path=manifest,
            repo_root_override=outer,
        )
        # Override pinned to outer; the inner `.git` is bypassed.
        assert ctx.repo_root == outer.resolve()
        assert len(ctx.entries) == 1

    def test_override_falls_back_to_env(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo_root = tmp_path / "project"
        plans_dir = repo_root / "implementation-plans"
        plans_dir.mkdir(parents=True)
        _make_plan_file(plans_dir, "1-alpha.md")
        manifest = tmp_path / "manifest.json"
        manifest.write_text(
            json.dumps({"plans": ["implementation-plans/1-alpha.md"]}),
            encoding="utf-8",
        )

        ctx = build_plan_tool_context(
            None,
            environ={"PLAN_TOOL_REPO_ROOT": str(repo_root)},
            manifest_path=manifest,
        )
        assert ctx.repo_root == repo_root.resolve()

    def test_no_override_uses_walk_up(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / ".git").mkdir()
        manifest = tmp_path / "manifest.json"
        manifest.write_text(json.dumps({"plans": []}), encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        ctx = build_plan_tool_context(
            None,
            environ={},
            manifest_path=manifest,
        )
        assert ctx.repo_root == tmp_path.resolve()

    def test_override_paired_with_plans_dir(self, tmp_path: Path) -> None:
        """``--plans-dir`` + ``--repo-root`` together: override wins for
        ``ctx.repo_root``, ignoring the walk-up from ``plans_dir``."""
        # plans_dir lives under unrelated `.git` but we override repo_root to
        # somewhere different.
        plans_parent = tmp_path / "scratch"
        plans_dir = plans_parent / "plans"
        plans_dir.mkdir(parents=True)
        (plans_parent / ".git").mkdir()
        _make_plan_file(plans_dir, "1-alpha.md")

        chosen_root = tmp_path / "project"
        chosen_root.mkdir()

        ctx = build_plan_tool_context(
            plans_dir,
            environ={},
            repo_root_override=chosen_root,
        )
        assert ctx.plans_dir == plans_dir.resolve()
        assert ctx.repo_root == chosen_root.resolve()
        # plans_dir scan still works.
        assert len(ctx.entries) == 1


class TestResolvePlanPathAgainstManifestRoot:
    """The manifest is the stable anchor in manifest mode.

    When no ``--repo-root`` / ``PLAN_TOOL_REPO_ROOT`` is given,
    ``build_plan_tool_context`` must walk up from the manifest's parent
    to find the repo root — not from CWD. The 2026-05-21 nested-``.git``
    bug (``.agents/`` shipping as an independent skill bundle with its
    own ``.git``) is the regression these cases pin: CWD walk-up halts
    at the inner ``.git`` and joins manifest entries against the wrong
    root; manifest walk-up continues up to the true repo root.
    """

    def test_cwd_at_manifest_root(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / ".git").mkdir()
        pdir = tmp_path / "plans"
        pdir.mkdir()
        plan_path = _make_plan_file(pdir, "1-alpha.md")
        manifest = tmp_path / "manifest.json"
        manifest.write_text(
            json.dumps({"plans": [str(plan_path.relative_to(tmp_path))]}),
            encoding="utf-8",
        )
        monkeypatch.delenv("PLAN_TOOL_REPO_ROOT", raising=False)
        monkeypatch.chdir(tmp_path)
        ctx = build_plan_tool_context(
            None, environ={"PLAN_TOOL_PLANS_DIR": ""}, manifest_path=manifest
        )
        assert ctx.repo_root == tmp_path.resolve()
        assert ctx.missing_paths == []
        assert len(ctx.entries) == 1

    def test_cwd_in_nested_source_tree(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Outer ``.git`` + nested ``.git`` inside; CWD is nested.

        CWD walk-up would halt at the nested ``.git`` and treat it as
        the repo root — joining manifest entries against the wrong
        path. Manifest-anchored walk-up climbs past the manifest's
        location to the outer ``.git``.
        """
        outer = tmp_path / "outer"
        inner = outer / "inner"
        inner.mkdir(parents=True)
        (outer / ".git").mkdir()
        (inner / ".git").mkdir()
        plans_dir = outer / "plans"
        plans_dir.mkdir()
        plan_path = _make_plan_file(plans_dir, "1-alpha.md")
        manifest = outer / "manifest.json"
        manifest.write_text(
            json.dumps({"plans": [str(plan_path.relative_to(outer))]}),
            encoding="utf-8",
        )
        monkeypatch.delenv("PLAN_TOOL_REPO_ROOT", raising=False)
        monkeypatch.chdir(inner)
        ctx = build_plan_tool_context(
            None, environ={"PLAN_TOOL_PLANS_DIR": ""}, manifest_path=manifest
        )
        assert ctx.repo_root == outer.resolve()
        assert ctx.missing_paths == []
        assert len(ctx.entries) == 1

    def test_cwd_outside_manifest_with_no_git_ancestor(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CWD is in a ``.git``-less sibling; CWD walk-up would raise.

        The manifest anchor saves us: walk-up from the manifest's
        parent reaches the outer ``.git`` even though CWD has no
        ``.git`` ancestor at all.
        """
        outer = tmp_path / "outer"
        outer.mkdir()
        (outer / ".git").mkdir()
        plans_dir = outer / "plans"
        plans_dir.mkdir()
        plan_path = _make_plan_file(plans_dir, "1-alpha.md")
        manifest = outer / "manifest.json"
        manifest.write_text(
            json.dumps({"plans": [str(plan_path.relative_to(outer))]}),
            encoding="utf-8",
        )
        unrelated = tmp_path / "elsewhere"
        unrelated.mkdir()
        monkeypatch.delenv("PLAN_TOOL_REPO_ROOT", raising=False)
        monkeypatch.chdir(unrelated)
        ctx = build_plan_tool_context(
            None, environ={"PLAN_TOOL_PLANS_DIR": ""}, manifest_path=manifest
        )
        assert ctx.repo_root == outer.resolve()
        assert ctx.missing_paths == []
        assert len(ctx.entries) == 1

    def test_no_git_anywhere_raises_filenotfound(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When no ``.git`` exists under the manifest dir or cwd,
        ``build_plan_tool_context`` raises ``FileNotFoundError`` — the
        same shape callers got when the now-removed
        ``find_repo_root_from_manifest`` couldn't find a repo root."""
        manifest = tmp_path / "m.json"
        manifest.write_text(json.dumps({"plans": []}), encoding="utf-8")
        unrelated = tmp_path / "elsewhere"
        unrelated.mkdir()
        monkeypatch.delenv("PLAN_TOOL_REPO_ROOT", raising=False)
        monkeypatch.chdir(unrelated)
        with pytest.raises(FileNotFoundError):
            build_plan_tool_context(
                None,
                environ={"PLAN_TOOL_PLANS_DIR": ""},
                manifest_path=manifest,
            )


@pytest.mark.integration
class TestCliRespectsRepoRootOverride:
    def test_main_resolves_manifest_under_override(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """End-to-end: ``cli.main(["--repo-root", X, "list"])`` resolves
        manifest entries under X and surfaces them in `list` output.
        """
        from plan_tool import cli as cli_module

        repo_root = tmp_path / "project"
        plans_dir = repo_root / "implementation-plans"
        plans_dir.mkdir(parents=True)
        _make_plan_file(plans_dir, "1-alpha.md")
        manifest = tmp_path / "manifest.json"
        manifest.write_text(
            json.dumps({"plans": ["implementation-plans/1-alpha.md"]}),
            encoding="utf-8",
        )
        # cwd is somewhere unrelated with no .git — walk-up would fail.
        unrelated = tmp_path / "elsewhere"
        unrelated.mkdir()
        monkeypatch.chdir(unrelated)

        rc = cli_module.main(
            [
                "--manifest",
                str(manifest),
                "--repo-root",
                str(repo_root),
                "list",
            ]
        )
        assert rc == 0



# --- Step 3: stale-entry remediation hint ---------------------------------


@pytest.mark.integration
class TestCmdListStaleEntryHint:
    def test_warning_includes_remediation_line(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool import cli as cli_module

        (tmp_path / ".git").mkdir()
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        real = _make_plan_file(plans_dir, "1-real.md")
        manifest = tmp_path / "m.json"
        manifest.write_text(
            json.dumps(
                {
                    "plans": [
                        str(real.relative_to(tmp_path)),
                        "plans/ghost.md",
                    ]
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.delenv("PLAN_TOOL_REPO_ROOT", raising=False)
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(["--manifest", str(manifest), "list"])
        assert rc == 0
        err = capsys.readouterr().err
        assert "warning:" in err
        assert "ghost.md" in err
        assert "if no longer needed, remove" in err
        # The remediation cites the manifest path.
        assert str(manifest) in err
        # And the repo-relative form (matches what's actually in the manifest).
        assert '"plans/ghost.md"' in err

    def test_no_warning_when_all_paths_resolve(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool import cli as cli_module

        (tmp_path / ".git").mkdir()
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        real = _make_plan_file(plans_dir, "1-real.md")
        manifest = tmp_path / "m.json"
        manifest.write_text(
            json.dumps({"plans": [str(real.relative_to(tmp_path))]}),
            encoding="utf-8",
        )
        monkeypatch.delenv("PLAN_TOOL_REPO_ROOT", raising=False)
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(["--manifest", str(manifest), "list"])
        assert rc == 0
        err = capsys.readouterr().err
        assert "if no longer needed" not in err


@pytest.mark.integration
class TestCmdListMalformedHint:
    """When a registered plan fails to validate, `list` points the operator
    at `plan-tool validate <slug>` for the full path and field detail."""

    def _setup(self, tmp_path: Path) -> Path:
        (tmp_path / ".git").mkdir()
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        good = _make_plan_file(plans_dir, "1-good.md")
        bad = _make_plan_file(plans_dir, "2-bad.md", valid=False)
        manifest = tmp_path / "m.json"
        manifest.write_text(
            json.dumps(
                {
                    "plans": [
                        str(good.relative_to(tmp_path)),
                        str(bad.relative_to(tmp_path)),
                    ]
                }
            ),
            encoding="utf-8",
        )
        return manifest

    def test_hint_points_at_validate(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool import cli as cli_module

        manifest = self._setup(tmp_path)
        monkeypatch.delenv("PLAN_TOOL_REPO_ROOT", raising=False)
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(["--manifest", str(manifest), "list"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "1 plan failed to validate" in out
        assert "plan-tool validate <slug>" in out
        assert "bad" in out  # names the offending slug as the example

    def test_no_hint_when_all_valid(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool import cli as cli_module

        (tmp_path / ".git").mkdir()
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        good = _make_plan_file(plans_dir, "1-good.md")
        manifest = tmp_path / "m.json"
        manifest.write_text(
            json.dumps({"plans": [str(good.relative_to(tmp_path))]}),
            encoding="utf-8",
        )
        monkeypatch.delenv("PLAN_TOOL_REPO_ROOT", raising=False)
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(["--manifest", str(manifest), "list"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "failed to validate" not in out


class TestCollectGitAncestors:
    def test_returns_every_git_ancestor_innermost_first(
        self, tmp_path: Path
    ) -> None:
        outer = tmp_path / "outer"
        middle = outer / "middle"
        inner = middle / "inner"
        inner.mkdir(parents=True)
        (outer / ".git").mkdir()
        (inner / ".git").mkdir()
        # middle has no .git
        got = collect_git_ancestors(inner)
        assert got == [inner.resolve(), outer.resolve()]

    def test_returns_empty_when_no_git_anywhere(self, tmp_path: Path) -> None:
        sub = tmp_path / "sub"
        sub.mkdir()
        # No .git anywhere — caller decides what to do with the empty list.
        assert collect_git_ancestors(sub) == []


class TestCollectProjectRootAncestors:
    def test_collects_both_git_and_manifest_markers_innermost_first(
        self, tmp_path: Path
    ) -> None:
        # outer is a .git repo; project is a manifest-only dir nested
        # under it (no .git of its own) — the exact shape that used to be
        # invisible to candidate enumeration.
        outer = tmp_path / "outer"
        project = outer / "munters" / "proj"
        inner = project / "sub"
        inner.mkdir(parents=True)
        (outer / ".git").mkdir()
        (project / ".plan-tool").mkdir()
        (project / ".plan-tool" / "plans.json").write_text("{}", encoding="utf-8")
        got = collect_project_root_ancestors(inner)
        assert got == [project.resolve(), outer.resolve()]

    def test_matches_find_repo_root_from_cwd_predicate(
        self, tmp_path: Path
    ) -> None:
        # The innermost project-root ancestor must equal what the
        # stop-at-first walk returns — they share is_project_root.
        project = tmp_path / "proj"
        project.mkdir()
        (project / ".plan-tool").mkdir()
        (project / ".plan-tool" / "plans.json").write_text("{}", encoding="utf-8")
        ancestors = collect_project_root_ancestors(project)
        assert ancestors[0] == find_repo_root_from_cwd(project)

    def test_returns_empty_when_no_marker_anywhere(self, tmp_path: Path) -> None:
        sub = tmp_path / "sub"
        sub.mkdir()
        assert collect_project_root_ancestors(sub) == []


class TestKnownRootsCache:
    def test_record_and_load_roundtrip(self, tmp_path: Path) -> None:
        cache = tmp_path / "git-roots.json"
        root_a = tmp_path / "repo-a"
        root_b = tmp_path / "repo-b"
        root_a.mkdir()
        root_b.mkdir()
        record_known_root(root_a, cache_path=cache)
        record_known_root(root_b, cache_path=cache)
        loaded = load_known_roots(cache_path=cache)
        assert root_a.resolve() in loaded
        assert root_b.resolve() in loaded

    def test_record_is_idempotent(self, tmp_path: Path) -> None:
        cache = tmp_path / "git-roots.json"
        root = tmp_path / "repo"
        root.mkdir()
        record_known_root(root, cache_path=cache)
        record_known_root(root, cache_path=cache)
        loaded = load_known_roots(cache_path=cache)
        assert loaded.count(root.resolve()) == 1

    def test_load_silently_drops_dead_entries(self, tmp_path: Path) -> None:
        cache = tmp_path / "git-roots.json"
        live = tmp_path / "live"
        live.mkdir()
        dead = tmp_path / "dead"  # never created
        cache.write_text(
            json.dumps({"roots": [str(live), str(dead)]}),
            encoding="utf-8",
        )
        loaded = load_known_roots(cache_path=cache)
        assert loaded == [live.resolve()]

    def test_load_returns_empty_for_missing_cache(self, tmp_path: Path) -> None:
        assert load_known_roots(cache_path=tmp_path / "nope.json") == []

    def test_load_returns_empty_for_malformed_cache(
        self, tmp_path: Path
    ) -> None:
        cache = tmp_path / "git-roots.json"
        cache.write_text("{ not json", encoding="utf-8")
        assert load_known_roots(cache_path=cache) == []


class TestFindRepoRootCandidates:
    def test_combines_manifest_walk_cwd_walk_and_cache(
        self, tmp_path: Path
    ) -> None:
        outer = tmp_path / "outer"
        nested = outer / ".agents" / "skills" / "plan-tool"
        # The cached root is a no-``.git`` umbrella *containing* cwd — the
        # cache's legitimate remaining purpose (the ``.git`` walk can't see
        # it, but it owns cwd, so it's a valid candidate).
        umbrella = tmp_path / "umbrella"
        cwd_repo = umbrella / "cwd-repo"
        nested.mkdir(parents=True)
        cwd_repo.mkdir(parents=True)
        (outer / ".git").mkdir()
        (outer / ".agents" / ".git").mkdir()
        (cwd_repo / ".git").mkdir()
        manifest = nested / "m.json"
        manifest.write_text("{}", encoding="utf-8")
        cache = tmp_path / "git-roots.json"
        record_known_root(umbrella, cache_path=cache)

        got = find_repo_root_candidates(
            manifest, cwd=cwd_repo, cache_path=cache
        )
        # All three sources contribute: manifest walk, cwd walk, cache.
        assert (outer / ".agents").resolve() in got
        assert outer.resolve() in got
        assert cwd_repo.resolve() in got
        assert umbrella.resolve() in got
        # Innermost (deepest path) first.
        assert got[0] == (outer / ".agents").resolve()

    def test_cache_root_outside_cwd_tree_is_excluded(
        self, tmp_path: Path
    ) -> None:
        """A root recorded while working in another project must not be
        offered as a candidate here. Otherwise its (possibly larger)
        manifest could hijack ``plan-tool list`` in an unrelated repo."""
        cwd_repo = tmp_path / "cwd-repo"
        foreign = tmp_path / "foreign-repo"
        cwd_repo.mkdir()
        foreign.mkdir()
        (cwd_repo / ".git").mkdir()
        (foreign / ".git").mkdir()
        cache = tmp_path / "git-roots.json"
        record_known_root(foreign, cache_path=cache)

        got = find_repo_root_candidates(cwd=cwd_repo, cache_path=cache)
        assert cwd_repo.resolve() in got
        assert foreign.resolve() not in got

    def test_returns_empty_when_no_candidates(self, tmp_path: Path) -> None:
        manifest = tmp_path / "m.json"
        manifest.write_text("{}", encoding="utf-8")
        cwd = tmp_path / "elsewhere"
        cwd.mkdir()
        cache = tmp_path / "git-roots.json"
        assert find_repo_root_candidates(manifest, cwd=cwd, cache_path=cache) == []


class TestFindUmbrellaRoot:
    """``find_umbrella_root`` returns the ``.git`` that controls the
    files, or — when files span multiple ``.git`` repos — the deepest
    common ancestor of those repos. This is the rule the user pinned:
    the repo root is "the one with the git folder that controls the
    files", with cross-repo plans escalating to the encapsulating
    umbrella even when the umbrella isn't itself a ``.git`` directory.
    """

    def test_all_files_under_one_git_returns_that_repo(
        self, tmp_path: Path
    ) -> None:
        repo = tmp_path / "repo"
        (repo / ".git").mkdir(parents=True)
        (repo / "src").mkdir()
        (repo / "src" / "a.py").write_text("", encoding="utf-8")
        (repo / "src" / "b.py").write_text("", encoding="utf-8")
        got = find_umbrella_root(
            [Path("src/a.py"), Path("src/b.py")],
            search_from=repo,
        )
        assert got == repo.resolve()

    def test_files_span_sibling_repos_returns_common_parent(
        self, tmp_path: Path
    ) -> None:
        umbrella = tmp_path / "umbrella"
        repo_a = umbrella / "app-amplify"
        repo_b = umbrella / "app-infra"
        (repo_a / ".git").mkdir(parents=True)
        (repo_b / ".git").mkdir(parents=True)
        (repo_a / "amplify").mkdir()
        (repo_b / "lib").mkdir()
        (repo_a / "amplify" / "foo.ts").write_text("", encoding="utf-8")
        (repo_b / "lib" / "bar.ts").write_text("", encoding="utf-8")
        got = find_umbrella_root(
            [
                Path("app-amplify/amplify/foo.ts"),
                Path("app-infra/lib/bar.ts"),
            ],
            search_from=umbrella,
        )
        assert got == umbrella.resolve()

    def test_nested_dot_agents_layout_uses_inner_repo_for_inner_files(
        self, tmp_path: Path
    ) -> None:
        """The real project layout: outer repo plus ``.agents/`` skill
        bundle with its own ``.git``. A plan that only touches files
        inside ``.agents/`` must pick ``.agents/`` as the root — that's
        the ``.git`` that controls those files even though the outer
        repo also encloses them. This is the synthetic regression test
        for the layout described in the conversation."""
        outer = tmp_path / "project"
        agents = outer / ".agents"
        (outer / ".git").mkdir(parents=True)
        (agents / ".git").mkdir(parents=True)
        (agents / "skills" / "plan-tool" / "plan_tool").mkdir(parents=True)
        (agents / "skills" / "plan-tool" / "plan_tool" / "locator.py").write_text(
            "", encoding="utf-8"
        )
        (agents / "skills" / "plan-tool" / "plan_tool" / "cli.py").write_text(
            "", encoding="utf-8"
        )
        got = find_umbrella_root(
            [
                Path(".agents/skills/plan-tool/plan_tool/locator.py"),
                Path(".agents/skills/plan-tool/plan_tool/cli.py"),
            ],
            search_from=outer,
        )
        assert got == agents.resolve()

    def test_nested_dot_agents_layout_uses_outer_when_files_span_both(
        self, tmp_path: Path
    ) -> None:
        """Same layout as above, but the plan touches files in BOTH
        the outer project and ``.agents/``. The umbrella must be the
        outer project (the deepest dir that contains both ``.git``
        repos), not ``.agents/`` (which only owns the inner files)."""
        outer = tmp_path / "project"
        agents = outer / ".agents"
        (outer / ".git").mkdir(parents=True)
        (agents / ".git").mkdir(parents=True)
        (outer / "amplify" / "data").mkdir(parents=True)
        (outer / "amplify" / "data" / "resource.ts").write_text(
            "", encoding="utf-8"
        )
        (agents / "skills" / "plan-tool" / "plan_tool").mkdir(parents=True)
        (agents / "skills" / "plan-tool" / "plan_tool" / "locator.py").write_text(
            "", encoding="utf-8"
        )
        got = find_umbrella_root(
            [
                Path("amplify/data/resource.ts"),
                Path(".agents/skills/plan-tool/plan_tool/locator.py"),
            ],
            search_from=outer,
        )
        assert got == outer.resolve()

    def test_fallback_returned_when_no_owning_git(
        self, tmp_path: Path
    ) -> None:
        # No .git anywhere in the tree.
        scratch = tmp_path / "scratch"
        (scratch / "src").mkdir(parents=True)
        (scratch / "src" / "a.py").write_text("", encoding="utf-8")
        got = find_umbrella_root(
            [Path("src/a.py")],
            search_from=scratch,
            fallback=scratch,
        )
        assert got == scratch

    def test_nonexistent_files_walked_up_to_existing_parent(
        self, tmp_path: Path
    ) -> None:
        """For new files the plan will create, the algorithm walks up
        from the proposed path until an existing parent is found and
        uses that parent's owning ``.git``. This is the create-time
        case: the plan references files that don't exist yet but live
        under a known repo."""
        repo = tmp_path / "repo"
        (repo / ".git").mkdir(parents=True)
        (repo / "src").mkdir()
        # `src/new.py` does NOT exist yet — but `src/` does.
        got = find_umbrella_root(
            [Path("src/new.py")],
            search_from=repo,
        )
        assert got == repo.resolve()


class TestBuildContextAutoRecovery:
    """The 2026-05-22 enhancement: when no override is supplied, walk-up
    is exhaustive (every ``.git`` ancestor) and the candidate with the
    most resolved manifest entries wins, with the innermost root
    breaking ties. This restores correct behavior from inside nested
    skill-bundle checkouts without requiring ``--repo-root``."""

    def test_picks_outer_root_when_inner_resolves_zero_entries(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        outer = tmp_path / "outer"
        nested = outer / ".agents" / "skills" / "plan-tool"
        plans_dir = outer / "plans"
        nested.mkdir(parents=True)
        plans_dir.mkdir()
        (outer / ".git").mkdir()
        (outer / ".agents" / ".git").mkdir()
        plan_path = _make_plan_file(plans_dir, "1-alpha.md")
        manifest = nested / "m.json"
        manifest.write_text(
            json.dumps({"plans": [str(plan_path.relative_to(outer))]}),
            encoding="utf-8",
        )
        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        monkeypatch.delenv("PLAN_TOOL_REPO_ROOT", raising=False)
        monkeypatch.chdir(nested)

        ctx = build_plan_tool_context(
            None,
            environ={"PLAN_TOOL_PLANS_DIR": ""},
            manifest_path=manifest,
        )
        assert ctx.repo_root == outer.resolve()
        assert len(ctx.entries) == 1
        assert ctx.missing_paths == []

    def test_manifest_only_dir_under_stray_git_repo_resolves(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Regression: a project dir with a default per-project manifest
        (``.plan-tool/plans.json``) but **no** ``.git``, nested under an
        unrelated git repo, must resolve to itself — not to the outer git
        repo. Before the fix, candidate enumeration only walked ``.git``
        ancestors, so ``list`` / ``register`` silently operated against the
        outer repo (empty manifest → "no plans registered") while
        ``plan-tool root`` correctly reported the inner dir."""
        outer = tmp_path / "outer"  # a stray git repo (e.g. ~/temp/.git)
        project = outer / "munters" / "proj"  # manifest-only project dir
        plans_dir = project / "docs" / "implementation-plans"
        plans_dir.mkdir(parents=True)
        (outer / ".git").mkdir()
        plan_path = _make_plan_file(plans_dir, "1-alpha.md")
        manifest_dir = project / ".plan-tool"
        manifest_dir.mkdir()
        (manifest_dir / "plans.json").write_text(
            json.dumps({"plans": [str(plan_path.relative_to(project))]}),
            encoding="utf-8",
        )
        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        monkeypatch.delenv("PLAN_TOOL_REPO_ROOT", raising=False)
        monkeypatch.chdir(project)

        # No explicit manifest_path: exercises the default per-project
        # manifest discovery the real CLI uses.
        ctx = build_plan_tool_context(
            None, environ={"PLAN_TOOL_PLANS_DIR": ""}
        )
        assert ctx.repo_root == project.resolve()
        assert len(ctx.entries) == 1
        assert ctx.missing_paths == []

    def test_resolves_with_no_git_anywhere(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A project that has never been ``git init``-ed must still
        resolve from its ``.plan-tool/plans.json`` alone — no ``.git``
        exists in the project or any ancestor."""
        project = tmp_path / "uninitialized"
        plans_dir = project / "docs" / "implementation-plans"
        plans_dir.mkdir(parents=True)
        plan_path = _make_plan_file(plans_dir, "1-alpha.md")
        manifest_dir = project / ".plan-tool"
        manifest_dir.mkdir()
        (manifest_dir / "plans.json").write_text(
            json.dumps({"plans": [str(plan_path.relative_to(project))]}),
            encoding="utf-8",
        )
        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        monkeypatch.delenv("PLAN_TOOL_REPO_ROOT", raising=False)
        monkeypatch.chdir(project)

        ctx = build_plan_tool_context(
            None, environ={"PLAN_TOOL_PLANS_DIR": ""}
        )
        assert ctx.repo_root == project.resolve()
        assert len(ctx.entries) == 1

    def test_bare_dir_no_git_no_manifest_raises_clean_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A wholly uninitialized dir (no ``.git``, no manifest) must
        surface the actionable FileNotFoundError the CLI renders as
        guidance — never an unhandled crash."""
        bare = tmp_path / "bare"
        bare.mkdir()
        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        monkeypatch.delenv("PLAN_TOOL_REPO_ROOT", raising=False)
        monkeypatch.chdir(bare)

        with pytest.raises(FileNotFoundError) as excinfo:
            build_plan_tool_context(
                None, environ={"PLAN_TOOL_PLANS_DIR": ""}
            )
        assert "could not find a project root" in str(excinfo.value)

    def test_records_resolved_root_to_cache(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.locator import default_known_roots_path

        outer = tmp_path / "outer"
        nested = outer / ".agents"
        plans_dir = outer / "plans"
        nested.mkdir(parents=True)
        plans_dir.mkdir()
        (outer / ".git").mkdir()
        (nested / ".git").mkdir()
        plan_path = _make_plan_file(plans_dir, "1-alpha.md")
        manifest = nested / "m.json"
        manifest.write_text(
            json.dumps({"plans": [str(plan_path.relative_to(outer))]}),
            encoding="utf-8",
        )
        monkeypatch.delenv("PLAN_TOOL_REPO_ROOT", raising=False)
        monkeypatch.chdir(nested)

        build_plan_tool_context(
            None,
            environ={"PLAN_TOOL_PLANS_DIR": ""},
            manifest_path=manifest,
        )
        cache = default_known_roots_path()
        assert cache.is_file()
        data = json.loads(cache.read_text(encoding="utf-8"))
        assert str(outer.resolve()) in data["roots"]

    def test_hard_errors_when_no_candidate_resolves_entries(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        outer = tmp_path / "outer"
        nested = outer / ".agents"
        nested.mkdir(parents=True)
        (outer / ".git").mkdir()
        (nested / ".git").mkdir()
        manifest = nested / "m.json"
        manifest.write_text(
            json.dumps({"plans": ["plans/ghost.md"]}), encoding="utf-8"
        )
        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        monkeypatch.delenv("PLAN_TOOL_REPO_ROOT", raising=False)
        monkeypatch.chdir(nested)

        with pytest.raises(ManifestError) as excinfo:
            build_plan_tool_context(
                None,
                environ={"PLAN_TOOL_PLANS_DIR": ""},
                manifest_path=manifest,
            )
        msg = str(excinfo.value)
        assert "--repo-root" in msg
        assert str(outer.resolve()) in msg
        assert str(nested.resolve()) in msg

    def test_surfaces_duplicate_plan_files_in_other_roots(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When the same plan file exists under multiple candidate roots,
        the selected root's copy is reported in ``entries`` and the
        other roots' copies are reported in ``duplicate_paths`` so the
        caller can offer to archive them."""
        outer = tmp_path / "outer"
        inner = outer / "inner"
        # Both layouts host a `plans/1-alpha.md`. Both score 1; inner wins on tie.
        (outer / "plans").mkdir(parents=True)
        (inner / "plans").mkdir(parents=True)
        _make_plan_file(outer / "plans", "1-alpha.md")
        _make_plan_file(inner / "plans", "1-alpha.md")
        (outer / ".git").mkdir()
        (inner / ".git").mkdir()
        manifest = inner / "m.json"
        manifest.write_text(
            json.dumps({"plans": ["plans/1-alpha.md"]}), encoding="utf-8"
        )
        monkeypatch.delenv("PLAN_TOOL_REPO_ROOT", raising=False)
        monkeypatch.chdir(inner)

        ctx = build_plan_tool_context(
            None,
            environ={"PLAN_TOOL_PLANS_DIR": ""},
            manifest_path=manifest,
        )
        assert ctx.repo_root == inner.resolve()
        assert len(ctx.entries) == 1
        # The outer copy of 1-alpha.md is the duplicate.
        assert (outer / "plans" / "1-alpha.md").resolve() in ctx.duplicate_paths

    def test_duplicate_paths_empty_when_override_pinned(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``--repo-root`` opts out of candidate enumeration entirely, so
        duplicate detection never runs — the caller owns the root and
        we don't second-guess them."""
        outer = tmp_path / "outer"
        inner = outer / "inner"
        (outer / "plans").mkdir(parents=True)
        (inner / "plans").mkdir(parents=True)
        _make_plan_file(outer / "plans", "1-alpha.md")
        _make_plan_file(inner / "plans", "1-alpha.md")
        (outer / ".git").mkdir()
        (inner / ".git").mkdir()
        manifest = tmp_path / "m.json"
        manifest.write_text(
            json.dumps({"plans": ["plans/1-alpha.md"]}), encoding="utf-8"
        )

        ctx = build_plan_tool_context(
            None,
            environ={},
            manifest_path=manifest,
            repo_root_override=inner,
        )
        assert ctx.duplicate_paths == []

    def test_innermost_wins_ties(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When two candidates resolve the same number of entries (e.g.
        both resolve zero of the plan files because both layouts host
        the same plan-relative path), tie-break by picking the deeper
        path. This keeps behavior aligned with the historical
        ``find_repo_root_from_manifest`` shape when both candidates
        equally fit."""
        outer = tmp_path / "outer"
        inner = outer / "inner"
        # Both layouts have a `plans/1-alpha.md` so both score 1.
        (outer / "plans").mkdir(parents=True)
        (inner / "plans").mkdir(parents=True)
        _make_plan_file(outer / "plans", "1-alpha.md")
        _make_plan_file(inner / "plans", "1-alpha.md")
        (outer / ".git").mkdir()
        (inner / ".git").mkdir()
        manifest = inner / "m.json"
        manifest.write_text(
            json.dumps({"plans": ["plans/1-alpha.md"]}), encoding="utf-8"
        )
        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        monkeypatch.delenv("PLAN_TOOL_REPO_ROOT", raising=False)
        monkeypatch.chdir(inner)

        ctx = build_plan_tool_context(
            None,
            environ={"PLAN_TOOL_PLANS_DIR": ""},
            manifest_path=manifest,
        )
        assert ctx.repo_root == inner.resolve()
