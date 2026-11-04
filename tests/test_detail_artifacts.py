"""Tests for the shared detail-artifact path-resolution leaf.

Characterization first: the ``TestCharacterization*`` classes pin the four
resolution families' behavior at their existing public seams —
``plan_tool.fingerprint`` (bundle fingerprint + purity key),
``plan_tool.review`` (bundle status), and ``plan_tool.scope_out`` (the two
private resolvers) — and were written and run green **before** the extraction
into ``plan_tool/detail_artifacts.py``. They must pass byte-for-byte
unmodified after it.

The resolution matrix pinned here (see the step-1 detail file):

| state                     | fingerprint     | review   | _resolve_detail_source | _resolve_carved_detail_path |
|---------------------------|-----------------|----------|------------------------|-----------------------------|
| pointer set, file exists  | hash pointer    | detailed | pointer path           | (pointer, False)            |
| pointer set, file missing | key omitted     | bare     | pointer path anyway    | (None, True)                |
| pointer unset, canonical  | hash canonical  | detailed | canonical path         | (canonical, False)          |
| pointer unset, nothing    | key omitted     | bare     | None                   | (None, False)               |
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

from plan_tool.detail import derive_detail_path, derive_step_slug
from plan_tool.detail_artifacts import (
    DETAIL_FORMAT_VERSION,
    SUPPORTED_DETAIL_FORMAT_VERSIONS,
    DetailFormatError,
    locate_detail_format_carrier,
    render_detail_format_version_marker,
    require_supported_detail_format_version,
    strip_detail_format_version_marker,
    upgrade_detail_body_to_current,
)
from plan_tool.fingerprint import (
    compute_detail_bundle_fingerprint,
    compute_purity_cache_key,
)
from plan_tool.review import audit_detail_bundle_status
from plan_tool.schema import Plan, Step
from plan_tool.scope_out import (
    _resolve_carved_detail_path,
    _resolve_detail_source,
)


def _sha(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _plan_with_steps(steps: list[Step]) -> Plan:
    return Plan(title="Demo", status="planning", priority="medium", steps=steps)


class TestCharacterizationFingerprint:
    """`compute_detail_bundle_fingerprint` / `compute_purity_cache_key`:
    pointer-first selection, no fallback for a set-but-missing pointer."""

    def test_bundle_fingerprint_prefers_pointer_over_canonical(
        self, tmp_path: Path
    ) -> None:
        plan_path = tmp_path / "2-foo.md"
        step = Step(id=1, title="Wire renderer", detail="docs/details/s1.md")
        plan = _plan_with_steps([step])
        _write(tmp_path / "docs/details/s1.md", "# pointer body")
        _write(derive_detail_path(plan_path, plan, step), "# canonical body")
        fp = compute_detail_bundle_fingerprint(plan, plan_path, tmp_path)
        assert fp == {"docs/details/s1.md": _sha("# pointer body")}

    def test_bundle_fingerprint_set_but_missing_pointer_omits_key(
        self, tmp_path: Path
    ) -> None:
        plan_path = tmp_path / "2-foo.md"
        step = Step(id=1, title="Wire renderer", detail="docs/details/gone.md")
        plan = _plan_with_steps([step])
        # Canonical file exists — must NOT be used as a fallback.
        _write(derive_detail_path(plan_path, plan, step), "# canonical body")
        fp = compute_detail_bundle_fingerprint(plan, plan_path, tmp_path)
        assert fp == {}

    def test_purity_key_detail_hash_uses_pointer_else_canonical(
        self, tmp_path: Path
    ) -> None:
        plan_path = tmp_path / "2-foo.md"
        pointed = Step(id=1, title="Wire renderer", detail="docs/details/s1.md")
        unpointed = Step(id=2, title="Build widget")
        bare = Step(id=3, title="Ship it")
        plan = _plan_with_steps([pointed, unpointed, bare])
        _write(tmp_path / "docs/details/s1.md", "# pointer body")
        _write(derive_detail_path(plan_path, plan, pointed), "# canonical body")
        _write(derive_detail_path(plan_path, plan, unpointed), "# canonical two")

        _, c1 = compute_purity_cache_key(plan, plan_path, pointed, tmp_path)
        assert c1.detail_hash == _sha("# pointer body")
        _, c2 = compute_purity_cache_key(plan, plan_path, unpointed, tmp_path)
        assert c2.detail_hash == _sha("# canonical two")
        _, c3 = compute_purity_cache_key(plan, plan_path, bare, tmp_path)
        assert c3.detail_hash is None


class TestCharacterizationReview:
    """`audit_detail_bundle_status`: pointer-first, no canonical fallback
    for a set-but-missing pointer."""

    def test_audit_bundle_status_pointer_and_canonical_cases(
        self, tmp_path: Path
    ) -> None:
        plan_path = tmp_path / "2-foo.md"
        s1 = Step(id=1, title="Wire renderer", detail="docs/details/s1.md")
        s2 = Step(id=2, title="Build widget", detail="docs/details/gone.md")
        s3 = Step(id=3, title="Ship artifact")
        s4 = Step(id=4, title="Document flow")
        plan = _plan_with_steps([s1, s2, s3, s4])
        _write(tmp_path / "docs/details/s1.md", "# s1")
        # s2's canonical exists, but its set pointer is authoritative → bare.
        _write(derive_detail_path(plan_path, plan, s2), "# s2 canonical")
        _write(derive_detail_path(plan_path, plan, s3), "# s3 canonical")
        status = audit_detail_bundle_status(plan, plan_path, tmp_path)
        assert status.total == 4
        assert status.detailed_step_ids == (1, 3)
        assert status.bare_step_ids == (2, 4)


class TestCharacterizationScopeOut:
    """`_resolve_detail_source` / `_resolve_carved_detail_path`: the two
    deliberately different missing-file policies."""

    def test_scope_out_resolve_source_returns_missing_pointer_path(
        self, tmp_path: Path
    ) -> None:
        plan_path = tmp_path / "2-foo.md"
        step = Step(id=1, title="Wire renderer", detail="docs/details/gone.md")
        plan = _plan_with_steps([step])
        # Even with the canonical on disk, a set pointer is authoritative.
        _write(derive_detail_path(plan_path, plan, step), "# canonical")
        assert (
            _resolve_detail_source(plan_path, plan, step, tmp_path)
            == tmp_path / "docs/details/gone.md"
        )

    def test_scope_out_resolve_source_adopts_only_exact_canonical(
        self, tmp_path: Path
    ) -> None:
        plan_path = tmp_path / "2-foo.md"
        adopted = Step(id=1, title="Wire renderer")
        orphaned = Step(id=5, title="Build widget thing")
        plan = _plan_with_steps([adopted, orphaned])
        canonical = _write(
            derive_detail_path(plan_path, plan, adopted), "# canonical"
        )
        # Same-``NN``-prefix, different slug: never adopted.
        _write(
            derive_detail_path(plan_path, plan, orphaned).with_name(
                "05-other-slug.md"
            ),
            "# stale sibling",
        )
        assert (
            _resolve_detail_source(plan_path, plan, adopted, tmp_path)
            == canonical
        )
        assert _resolve_detail_source(plan_path, plan, orphaned, tmp_path) is None

    def test_carved_detail_path_three_cases(self, tmp_path: Path) -> None:
        plan_path = tmp_path / "2-foo.md"
        pointed = Step(id=1, title="Wire renderer", detail="docs/details/s1.md")
        lost = Step(id=2, title="Build widget", detail="docs/details/gone.md")
        adopted = Step(id=3, title="Ship artifact")
        never = Step(id=4, title="Document flow")
        plan = _plan_with_steps([pointed, lost, adopted, never])
        _write(tmp_path / "docs/details/s1.md", "# s1")
        # `lost`'s canonical exists — the set pointer still wins (no fallback).
        _write(derive_detail_path(plan_path, plan, lost), "# lost canonical")
        canonical = _write(
            derive_detail_path(plan_path, plan, adopted), "# adopted"
        )
        assert _resolve_carved_detail_path(plan_path, plan, pointed, tmp_path) == (
            tmp_path / "docs/details/s1.md",
            False,
        )
        assert _resolve_carved_detail_path(plan_path, plan, lost, tmp_path) == (
            None,
            True,
        )
        assert _resolve_carved_detail_path(plan_path, plan, adopted, tmp_path) == (
            canonical,
            False,
        )
        assert _resolve_carved_detail_path(plan_path, plan, never, tmp_path) == (
            None,
            False,
        )


class TestCharacterizationDerivation:
    """Canonical path / slug derivation conventions."""

    def test_derive_detail_path_format(self, tmp_path: Path) -> None:
        step = Step(id=3, title="Build it")
        plan = _plan_with_steps([step])
        # Leading ``<digit>-`` stripped from the plan stem.
        assert (
            derive_detail_path(tmp_path / "2-foo.md", plan, step)
            == tmp_path / "plan-details" / "foo" / "03-build.md"
        )
        # Unprefixed stem kept as-is.
        assert (
            derive_detail_path(tmp_path / "manual.md", plan, step)
            == tmp_path / "plan-details" / "manual" / "03-build.md"
        )

    def test_derive_step_slug_stopwords_and_length_cap(self) -> None:
        # Stopwords ("add", "the", "to", "a") and single-char tokens drop.
        assert derive_step_slug("Add the renderer to a widget") == (
            "renderer-widget"
        )
        # Everything dropped → "step" fallback.
        assert derive_step_slug("A x") == "step"
        assert derive_step_slug("") == "step"
        # Cap at 40 chars, truncating on the last ``-`` inside the budget.
        assert derive_step_slug(
            "Reconfigure sophisticated architecture components everywhere"
        ) == "reconfigure-sophisticated-architecture"


class TestSharedResolver:
    """`detail_artifacts.resolve_detail_artifact`: reports the three facts
    (pointer_set, path, on_disk) each consumer maps to its own policy."""

    def test_resolver_state_matrix_preserves_pointer_and_canonical_behavior(self, tmp_path: Path) -> None:
        from plan_tool.detail_artifacts import resolve_detail_artifact

        plan_path = tmp_path / "2-foo.md"
        s1 = Step(id=1, title="Wire renderer", detail="docs/details/s1.md")
        s2 = Step(id=2, title="Build widget", detail="docs/details/gone.md")
        s3 = Step(id=3, title="Ship artifact")
        s4 = Step(id=4, title="Document flow")
        plan = _plan_with_steps([s1, s2, s3, s4])
        _write(tmp_path / "docs/details/s1.md", "# s1")
        _write(derive_detail_path(plan_path, plan, s1), "# canonical decoy")
        _write(derive_detail_path(plan_path, plan, s2), "# canonical decoy")
        canonical3 = _write(
            derive_detail_path(plan_path, plan, s3), "# s3 canonical"
        )

        r1 = resolve_detail_artifact(plan_path, plan, s1, tmp_path)
        assert (r1.pointer_set, r1.path, r1.on_disk) == (
            True, tmp_path / "docs/details/s1.md", True,
        )
        r2 = resolve_detail_artifact(plan_path, plan, s2, tmp_path)
        assert (r2.pointer_set, r2.path, r2.on_disk) == (
            True, tmp_path / "docs/details/gone.md", False,
        )
        r3 = resolve_detail_artifact(plan_path, plan, s3, tmp_path)
        assert (r3.pointer_set, r3.path, r3.on_disk) == (
            False, canonical3, True,
        )
        r4 = resolve_detail_artifact(plan_path, plan, s4, tmp_path)
        assert (r4.pointer_set, r4.on_disk) == (False, False)
        assert r4.path == derive_detail_path(plan_path, plan, s4)


class TestLeafAndReexports:
    """Import-safety and compatibility seams of the extraction."""

    def test_leaf_does_not_import_detail(self) -> None:
        """Importing the leaf in a fresh interpreter must pull in neither
        ``plan_tool.detail`` nor ``plan_tool.review`` — the whole point of
        the extraction is that ``fingerprint``/``review`` can import it at
        module load without closing the ``detail`` → ``review`` cycle.

        Registers a stub ``plan_tool`` package first (same bypass as
        ``test_rate_limit_loop``'s leaf test): the real package ``__init__``
        eagerly imports ``detail``/``review`` itself, which would mask what
        the *leaf's* import graph pulls in.
        """
        pkg_dir = Path(__file__).resolve().parents[1] / "plan_tool"
        code = (
            "import sys, types\n"
            "pkg = types.ModuleType('plan_tool')\n"
            f"pkg.__path__ = [{str(pkg_dir)!r}]\n"
            "sys.modules['plan_tool'] = pkg\n"
            "import plan_tool.detail_artifacts\n"
            "assert 'plan_tool.detail' not in sys.modules\n"
            "assert 'plan_tool.review' not in sys.modules\n"
            "assert 'plan_tool.fingerprint' not in sys.modules\n"
        )
        proc = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True
        )
        assert proc.returncode == 0, proc.stderr

    def test_moved_names_reexported_from_detail(self) -> None:
        """The re-exports are the *same objects*, so a monkeypatch on either
        module path patches the one implementation."""
        from plan_tool import detail, detail_artifacts

        assert detail.derive_detail_path is detail_artifacts.derive_detail_path
        assert detail.derive_step_slug is detail_artifacts.derive_step_slug
        assert (
            detail.find_unreferenced_detail_for_step
            is detail_artifacts.find_unreferenced_detail_for_step
        )
        assert detail._plan_slug is detail_artifacts._plan_slug

    def test_package_exports_unchanged(self) -> None:
        from plan_tool import derive_detail_path as pkg_derive_detail_path
        from plan_tool import derive_step_slug as pkg_derive_step_slug
        from plan_tool.detail_artifacts import (
            derive_detail_path as leaf_derive_detail_path,
            derive_step_slug as leaf_derive_step_slug,
        )

        assert pkg_derive_detail_path is leaf_derive_detail_path
        assert pkg_derive_step_slug is leaf_derive_step_slug


class TestDetailFormatVersion:
    """``require_supported_detail_format_version``'s fixed post-H1 marker
    slot: resolve-then-check, mirroring
    ``parser._require_supported_plan_format_version``'s shape for a detail
    file, which has no frontmatter to hold a version key."""

    def test_body_with_no_marker_resolves_to_supported_legacy_and_is_unchanged(
        self,
    ) -> None:
        body = "# Title\n\n## Summary\n\nSome text.\n"
        require_supported_detail_format_version(body)  # raises nothing

    def test_marker_free_body_refuses_when_legacy_version_is_retired(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import plan_tool.detail_artifacts as detail_artifacts_module

        monkeypatch.setattr(
            detail_artifacts_module, "SUPPORTED_DETAIL_FORMAT_VERSIONS", frozenset({2})
        )
        marker_free = "# Title\n\n## Summary\n"
        declares_one = (
            f"# Title\n{render_detail_format_version_marker(1)}\n\n## Summary\n"
        )
        for body in (marker_free, declares_one):
            with pytest.raises(DetailFormatError):
                require_supported_detail_format_version(body)

    def test_body_with_current_version_marker_parses_identically(self) -> None:
        body = f"# Title\n{render_detail_format_version_marker()}\n\n## Summary\n"
        require_supported_detail_format_version(body)  # raises nothing

    def test_leading_blank_lines_preserve_the_h1_carrier_slot(self) -> None:
        current = (
            f"\n\n# Title\n{render_detail_format_version_marker()}\n\n## Summary\n"
        )
        require_supported_detail_format_version(current)  # raises nothing

        unsupported = (
            "\n\n# Title\n<!-- plan-tool:detail-format-version: 999 -->\n"
            "\n## Summary\n"
        )
        with pytest.raises(DetailFormatError):
            require_supported_detail_format_version(unsupported)

    def test_body_declaring_unsupported_version_is_refused_by_name(self) -> None:
        body = (
            "# Title\n<!-- plan-tool:detail-format-version: 999 -->\n\n## Summary\n"
        )
        with pytest.raises(DetailFormatError) as exc_info:
            require_supported_detail_format_version(body)
        message = str(exc_info.value)
        assert "999" in message
        assert str(sorted(SUPPORTED_DETAIL_FORMAT_VERSIONS)) in message

    @pytest.mark.parametrize("payload", ["", "one", "1.5", "true"])
    def test_malformed_marker_payload_fails_closed(self, payload: str) -> None:
        body = (
            f"# Title\n<!-- plan-tool:detail-format-version: {payload} -->\n"
            "\n## Summary\n"
        )
        with pytest.raises(DetailFormatError):
            require_supported_detail_format_version(body)

    @pytest.mark.parametrize("payload", ["١", "４", "9" * 5000])
    def test_reader_and_upgrader_refuse_noncanonical_integer_payloads(
        self, payload: str
    ) -> None:
        body = (
            f"# Title\n<!-- plan-tool:detail-format-version: {payload} -->\n"
            "\n## Summary\n"
        )

        with pytest.raises(DetailFormatError):
            require_supported_detail_format_version(body)
        with pytest.raises(DetailFormatError):
            upgrade_detail_body_to_current(body)

    @pytest.mark.parametrize(
        "body",
        [
            "",
            "## Summary\n\nNo H1 at all.\n",
            "Some preamble.\n# Title\n\n## Summary\n",
        ],
    )
    def test_body_with_no_valid_carrier_h1_has_no_marker_slot(
        self, body: str
    ) -> None:
        assert locate_detail_format_carrier(body) is None
        # Marker-shaped text appended to a carrier-less body doesn't
        # matter — there's no slot to check, so this resolves to the
        # supported legacy version.
        require_supported_detail_format_version(
            body + "<!-- plan-tool:detail-format-version: 999 -->\n"
        )

    def test_carrier_locator_accepts_only_a_column_zero_h1(self) -> None:
        assert locate_detail_format_carrier("\n\n# Title\n## Summary\n") == (2, 3)
        assert locate_detail_format_carrier("## Summary\n\nBody.\n") is None
        assert locate_detail_format_carrier("  # Title\n\n## Summary\n") is None
        assert (
            locate_detail_format_carrier("Preamble.\n# Title\n\n## Summary\n")
            is None
        )

    def test_marker_shaped_text_outside_the_fixed_slot_is_ordinary_prose(
        self,
    ) -> None:
        body = (
            "# Title\n"
            "Some ordinary prose, not a marker.\n\n"
            "## Implementation\n"
            "<!-- plan-tool:detail-format-version: 999 -->\n"
        )
        require_supported_detail_format_version(body)  # raises nothing

    def test_second_marker_after_the_fixed_slot_is_ordinary_prose(self) -> None:
        body = (
            f"# Title\n{render_detail_format_version_marker()}\n"
            "<!-- plan-tool:detail-format-version: 999 -->\n\n## Summary\n"
        )

        require_supported_detail_format_version(body)  # raises nothing

    def test_unrelated_html_comment_in_the_slot_is_treated_as_absent(self) -> None:
        body = "# Title\n<!-- note to self -->\n\n## Summary\n"
        require_supported_detail_format_version(body)  # raises nothing

    def test_render_detail_format_version_marker_round_trips(self) -> None:
        body = f"# Title\n{render_detail_format_version_marker()}\n\n## Summary\n"
        require_supported_detail_format_version(body)  # raises nothing

    def test_strip_removes_only_the_fixed_slot_marker(self) -> None:
        prose_marker = "<!-- plan-tool:detail-format-version: 999 -->"
        body = (
            f"# Title\n{render_detail_format_version_marker()}\n\n## Summary\n\n"
            f"{prose_marker}\n"
        )

        stripped = strip_detail_format_version_marker(body)

        assert render_detail_format_version_marker() not in stripped
        assert prose_marker in stripped

    def test_default_version_is_a_supported_version(self) -> None:
        assert DETAIL_FORMAT_VERSION in SUPPORTED_DETAIL_FORMAT_VERSIONS


class TestUpgradeDetailBodyToCurrent:
    def test_marker_free_body_gains_the_current_marker_after_its_h1(self) -> None:
        body = "# Title\n\n## Summary\n\nSome text.\n"

        upgraded = upgrade_detail_body_to_current(body)

        lines = upgraded.splitlines()
        first_non_blank_after_h1 = next(
            line for line in lines[1:] if line.strip() != ""
        )
        assert first_non_blank_after_h1 == render_detail_format_version_marker()

    def test_upgrade_changes_only_the_inserted_line(self) -> None:
        body = "# Title\n\n## Summary\n\nSome text.\n"

        upgraded = upgrade_detail_body_to_current(body)

        original_lines = body.splitlines(keepends=True)
        upgraded_lines = upgraded.splitlines(keepends=True)
        assert len(upgraded_lines) == len(original_lines) + 1
        assert upgraded_lines[0] == original_lines[0]
        assert upgraded_lines[2:] == original_lines[1:]

    def test_body_already_declaring_the_current_version_is_returned_unchanged(
        self,
    ) -> None:
        body = f"# Title\n{render_detail_format_version_marker()}\n\n## Summary\n"

        assert upgrade_detail_body_to_current(body) == body

    def test_upgrade_refuses_a_body_with_no_valid_carrier_h1_rather_than_synthesizing_one(
        self,
    ) -> None:
        """Carrier-less detail refuses instead of inventing a heading."""
        body = "## Summary\n\nNo H1 at all.\n"

        with pytest.raises(DetailFormatError) as exc_info:
            upgrade_detail_body_to_current(body)
        assert "carrier" in str(exc_info.value).lower()

    def test_upgrade_accepts_leading_blank_lines_before_the_carrier_h1(
        self,
    ) -> None:
        body = "\n\n# Title\n\n## Summary\n"

        upgraded = upgrade_detail_body_to_current(body)

        lines = upgraded.splitlines()
        h1_index = lines.index("# Title")
        first_non_blank_after_h1 = next(
            line for line in lines[h1_index + 1 :] if line.strip() != ""
        )
        assert first_non_blank_after_h1 == render_detail_format_version_marker()

    def test_h1_with_no_following_content_gains_the_marker(self) -> None:
        """The decided edge: a missing H1 is the only refusal condition, so
        a bare H1 upgrades rather than refusing."""
        body = "# Title\n"

        upgraded = upgrade_detail_body_to_current(body)

        assert upgraded == f"# Title\n{render_detail_format_version_marker()}\n"

    def test_upgrade_refuses_an_unsupported_marker_by_name(self) -> None:
        body = (
            "# Title\n<!-- plan-tool:detail-format-version: 999 -->\n\n## Summary\n"
        )

        with pytest.raises(DetailFormatError) as exc_info:
            upgrade_detail_body_to_current(body)
        message = str(exc_info.value)
        assert "999" in message
        assert str(sorted(SUPPORTED_DETAIL_FORMAT_VERSIONS)) in message

    @pytest.mark.parametrize("payload", ["", "one", "1.5", "true"])
    def test_upgrade_refuses_a_malformed_marker_rather_than_treating_it_as_absent(
        self, payload: str
    ) -> None:
        body = (
            f"# Title\n<!-- plan-tool:detail-format-version: {payload} -->\n"
            "\n## Summary\n"
        )

        with pytest.raises(DetailFormatError):
            upgrade_detail_body_to_current(body)

    @pytest.mark.parametrize(
        "body",
        [
            "# Title\n<!-- plan-tool:detail-format-version: 999 -->\n\n## Summary\n",
            "# Title\n<!-- plan-tool:detail-format-version: one -->\n\n## Summary\n",
            "# Title\n\n## Summary\n",
            f"# Title\n{render_detail_format_version_marker()}\n\n## Summary\n",
        ],
    )
    def test_upgrade_refuses_exactly_what_the_reader_gate_refuses(
        self, body: str
    ) -> None:
        """Pins the single-decision invariant: the reader gate and the
        upgrader must never disagree about which declared values are
        acceptable, because the upgrader calls the same gate rather than
        re-deriving its own accepted-state set."""
        gate_raised = False
        try:
            require_supported_detail_format_version(body)
        except DetailFormatError:
            gate_raised = True

        upgrade_raised = False
        try:
            upgrade_detail_body_to_current(body)
        except DetailFormatError:
            upgrade_raised = True

        assert gate_raised == upgrade_raised

    def test_marker_shaped_prose_outside_the_slot_stays_prose_and_is_not_a_declaration(
        self,
    ) -> None:
        body = (
            "# Title\n"
            "Some ordinary prose, not a marker.\n\n"
            "## Implementation\n"
            "<!-- plan-tool:detail-format-version: 999 -->\n"
        )

        upgraded = upgrade_detail_body_to_current(body)

        assert "<!-- plan-tool:detail-format-version: 999 -->\n" in upgraded
        assert "Some ordinary prose, not a marker.\n" in upgraded
        assert render_detail_format_version_marker() in upgraded

    def test_upgraded_body_passes_the_reader_gate(self) -> None:
        body = "# Title\n\n## Summary\n\nSome text.\n"

        upgraded = upgrade_detail_body_to_current(body)

        require_supported_detail_format_version(upgraded)  # raises nothing

    def test_every_detail_upgradable_state_has_a_declared_upgrade_path_to_current(
        self,
    ) -> None:
        for state in (None, *sorted(SUPPORTED_DETAIL_FORMAT_VERSIONS)):
            if state is None:
                body = "# Title\n\n## Summary\n"
            else:
                body = (
                    f"# Title\n{render_detail_format_version_marker(state)}\n\n"
                    "## Summary\n"
                )

            upgraded = upgrade_detail_body_to_current(body)

            assert render_detail_format_version_marker() in upgraded, state

    def test_adding_a_supported_detail_version_without_a_path_fails_closed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A new supported value needs a coded upgrade route."""
        import plan_tool.detail_artifacts as detail_artifacts_module

        monkeypatch.setattr(
            detail_artifacts_module,
            "SUPPORTED_DETAIL_FORMAT_VERSIONS",
            frozenset({1, 2}),
        )
        body = f"# Title\n{render_detail_format_version_marker(2)}\n\n## Summary\n"

        with pytest.raises(NotImplementedError):
            upgrade_detail_body_to_current(body)


def test_retired_jira_grade_module_is_absent() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    assert not (repo_root / "plan_tool" / "jira_grade.py").exists()
    assert not (repo_root / "tests" / "test_jira_grade.py").exists()


def test_detail_artifacts_has_no_jira_path_derivation() -> None:
    from plan_tool import detail_artifacts

    assert not hasattr(detail_artifacts, "derive_jira_detail_path")
    assert not hasattr(detail_artifacts, "_JIRA_GRADE_DIRNAME")


def test_no_live_jira_grade_detail_bundles_exist() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    live_details = repo_root / "docs" / "implementation-plans" / "plan-details"
    assert list(live_details.glob("*/jira")) == []
