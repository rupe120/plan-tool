"""Captured examples of each version of a persisted format must still load.

``tests/fixtures/versioned/`` holds files written by the code of the release or
commit in each name, captured once and never edited. A record built from today's
output only checks the shape its author expects; these check what an older
release really wrote. A failing example means the reader regressed: fix the
reader, not the example. See ``tests/fixtures/versioned/README.md``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from plan_tool.review_persistence import (
    _SUPPORTED_SCHEMA_VERSIONS,
    AuditInputSnapshot,
    load_review,
)

FIXTURES = Path(__file__).parent / "fixtures" / "versioned"
EXAMPLES = sorted((FIXTURES / "saved-review").glob("*.json"))
NAME_RE = re.compile(
    r"^(?P<shape>[a-z-]+)\.sidecar-v(?P<sidecar>\d+)"
    r"(?:\.revision-v(?P<revision>\d+))?\.(?P<source>.+)\.json$"
)
SHAPE_KIND = {
    "completeness-final": "completeness",
    "completeness-checkpoint": "completeness",
    "completeness-legacy": "completeness",
    "completeness-advisory": "completeness",
    "completeness-checkpoint-no-revision": "completeness",
    "review": "review",
    "run-reconcile": "run-reconcile",
    "detail-reconcile": "detail-reconcile",
}


def _parts(path: Path) -> re.Match[str]:
    match = NAME_RE.match(path.name)
    assert match, f"{path.name} does not follow <shape>.sidecar-vN[.revision-vM].<source>.json"
    assert match["shape"] in SHAPE_KIND, path.name
    return match


def _raw_revision(raw: dict, shape: str) -> dict | None:
    if shape == "completeness-final":
        return raw["qualified_result"]["audit_revision"]
    if shape == "completeness-checkpoint":
        return raw["checkpoint_audit_revision"]
    return None


def _current_revision_version(tmp_path: Path) -> int:
    plan = tmp_path / "plan.md"
    plan.write_text(
        "---\ntitle: Demo\nstatus: planning\npriority: medium\nsteps:\n"
        "  - id: 1\n    title: First\n---\n\n# Plan\n",
        encoding="utf-8",
    )
    return AuditInputSnapshot.capture(plan, tmp_path).revision["version"]


def test_examples_exist() -> None:
    assert EXAMPLES, "tests/fixtures/versioned/saved-review/ holds no examples"


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_a_captured_example_loads_through_the_current_reader(path: Path, tmp_path: Path) -> None:
    """The file's own claims (sidecar and revision version, kind, shape) hold, and the reader
    keeps its meaning: kind, checkpoint flag, recommendations, and the revision upgraded to
    today's version with the digests an older record lacked read as ``None``."""
    parts = _parts(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    saved = load_review(path)

    assert raw["version"] == int(parts["sidecar"])
    assert saved.kind == SHAPE_KIND[parts["shape"]]
    assert [(r.id, r.severity) for r in saved.recommendations] == [
        (r["id"], r["severity"]) for r in raw["recommendations"]
    ]
    assert saved.plan_fingerprint == raw["plan_fingerprint"]
    assert saved.is_pre_apply_checkpoint is bool(raw.get("is_pre_apply_checkpoint"))
    if parts["shape"] == "completeness-advisory":
        assert saved.audit_shape_advisory is not None
        assert saved.audit_shape_advisory.shape_id == raw["audit_shape_advisory"]["shape_id"]

    raw_revision = _raw_revision(raw, parts["shape"])
    if parts["revision"] is None:
        assert raw_revision is None
        assert saved.audit_revision is None and saved.qualified_result is None
        return

    assert raw_revision is not None and raw_revision["version"] == int(parts["revision"])
    current = _current_revision_version(tmp_path)
    loaded = saved.audit_revision
    assert loaded is not None, "the reader dropped a revision an older release wrote"
    # The expected record is written out here, not computed by the reader: a current-version
    # revision loads unchanged, and an older one gains only its version and the digests it
    # lacked, read as None (a report of a plan without siblings stays current after upgrade).
    expected = dict(raw_revision)
    if int(parts["revision"]) < 4:
        assert "sibling_paths_digest" not in raw_revision
        expected.update(version=current, sibling_paths_digest=None)
    assert loaded == expected
    if parts["shape"] == "completeness-checkpoint":
        assert saved.is_pre_apply_checkpoint is True
        assert saved.qualified_result is None
    else:
        assert saved.is_pre_apply_checkpoint is False
        assert saved.qualified_result["audit_revision"] == loaded
        assert saved.qualified_result["coverage"] == "confirmed"


def test_every_supported_sidecar_version_has_a_captured_example(tmp_path: Path) -> None:
    """A version bump must add an example of the new version in the same change. The bound is
    the reader's own supported set, so a new sidecar version cannot be added without one."""
    sidecars = {int(_parts(path)["sidecar"]) for path in EXAMPLES}
    missing = set(_SUPPORTED_SCHEMA_VERSIONS) - sidecars
    assert not missing, f"no example of sidecar version(s) {sorted(missing)}"
    assert sidecars <= set(_SUPPORTED_SCHEMA_VERSIONS), "an example claims a version the reader no longer supports"


def test_the_current_audit_revision_version_has_a_captured_example(tmp_path: Path) -> None:
    revisions = {int(_parts(path)["revision"]) for path in EXAMPLES if _parts(path)["revision"]}
    assert _current_revision_version(tmp_path) in revisions, "no example of the current audit-revision version"


def test_the_readme_table_has_a_row_for_every_example() -> None:
    rows = [
        line for line in (FIXTURES / "README.md").read_text(encoding="utf-8").splitlines()
        if line.startswith("| `")
    ]
    for path in EXAMPLES:
        assert any(row.startswith(f"| `{path.name}` |") for row in rows), (
            f"{path.name} has no row in tests/fixtures/versioned/README.md"
        )
