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
    SCHEMA_VERSION,
    _AUDIT_REVISION_SCHEMA_VERSION,
    AuditInputSnapshot,
    load_review,
    normalize_audit_revision,
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
    assert len(saved.recommendations) == len(raw["recommendations"])

    raw_revision = _raw_revision(raw, parts["shape"])
    if parts["revision"] is None:
        assert raw_revision is None
        assert saved.audit_revision is None and saved.qualified_result is None
        return

    assert raw_revision is not None and raw_revision["version"] == int(parts["revision"])
    current = _current_revision_version(tmp_path)
    loaded = saved.audit_revision
    assert loaded is not None, "the reader dropped a revision an older release wrote"
    assert loaded == normalize_audit_revision(raw_revision)
    assert loaded["version"] == current
    if int(parts["revision"]) < 4:
        assert loaded["sibling_paths_digest"] is None  # absent before v4: reads as none
    if parts["shape"] == "completeness-checkpoint":
        assert saved.is_pre_apply_checkpoint is True
        assert saved.qualified_result is None
    else:
        assert saved.is_pre_apply_checkpoint is False
        assert saved.qualified_result["audit_revision"] == loaded
        assert saved.qualified_result["coverage"] == "confirmed"


def test_every_current_format_version_has_a_captured_example(tmp_path: Path) -> None:
    """A version bump must add an example of the new version in the same change."""
    names = [_parts(path) for path in EXAMPLES]
    completeness = {int(m["sidecar"]) for m in names if SHAPE_KIND[m["shape"]] == "completeness"}
    reconcile = {int(m["sidecar"]) for m in names if SHAPE_KIND[m["shape"]].endswith("-reconcile")}
    revisions = {int(m["revision"]) for m in names if m["revision"]}

    assert _AUDIT_REVISION_SCHEMA_VERSION in completeness, "no example of the current completeness sidecar version"
    assert SCHEMA_VERSION in reconcile, "no example of the current reconcile sidecar version"
    assert _current_revision_version(tmp_path) in revisions, "no example of the current audit-revision version"


def test_the_readme_lists_every_example() -> None:
    readme = (FIXTURES / "README.md").read_text(encoding="utf-8")
    for path in EXAMPLES:
        assert path.name in readme, f"{path.name} is not described in tests/fixtures/versioned/README.md"
