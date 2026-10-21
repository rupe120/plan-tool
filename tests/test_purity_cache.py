"""Unit tests for the purity-findings cache (`plan_tool/purity_cache.py`)."""

from __future__ import annotations

import dataclasses
import json
import subprocess
from pathlib import Path

import pytest

from plan_tool.granularity import GRANULARITY_SPLIT_SOURCE
from plan_tool.review import Recommendation, Redirect
from plan_tool import purity_cache as pc


def _finding(step_id: int = 2) -> Recommendation:
    return Recommendation(
        id=f"split:{step_id}",
        source=GRANULARITY_SPLIT_SOURCE,
        severity="medium",
        step_id=step_id,
        title="MIXED-STEP: refactor fused with feature",
        body="Step mixes a behavior-preserving refactor with new behavior.",
    )


def _entry(step_id: int = 2, *, findings=None) -> pc.PurityCacheEntry:
    return pc.PurityCacheEntry(
        step_id=step_id,
        cache_key="a" * 64,
        detail_hash="b" * 64,
        all_files_fingerprint="c" * 64,
        change_type="feature",
        depends_on=[1],
        purity_verdict_logic_version=1,
        detail_relpath=f"docs/implementation-plans/plan-details/x/{step_id:02d}-foo.md",
        findings=[_finding(step_id)] if findings is None else findings,
        impl_tests_text="## Implementation\nbody\n## Tests\ncases\n",
        checked_at="2026-07-18T12:34:56Z",
    )


def test_load_missing_cache_returns_empty(tmp_path: Path) -> None:
    cache = pc.load_purity_cache(pc.purity_cache_path(tmp_path, "x"))
    assert cache.entries == {}


def test_save_then_load_round_trips_entry(tmp_path: Path) -> None:
    path = pc.purity_cache_path(tmp_path, "x")
    entry = _entry(2)
    pc.save_purity_cache(path, pc.PurityCache(plan_slug="x", entries={2: entry}))
    loaded = pc.load_purity_cache(path).entries[2]
    assert loaded.cache_key == entry.cache_key
    assert loaded.detail_hash == entry.detail_hash
    assert loaded.all_files_fingerprint == entry.all_files_fingerprint
    assert loaded.change_type == entry.change_type
    assert loaded.depends_on == entry.depends_on
    assert loaded.purity_verdict_logic_version == entry.purity_verdict_logic_version
    assert loaded.detail_relpath == entry.detail_relpath
    assert loaded.findings == entry.findings
    assert loaded.impl_tests_text == entry.impl_tests_text
    assert loaded.step_id == 2


def test_purity_cache_dir_is_gitignored() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    sample = repo_root / ".plan-tool" / "purity-cache" / "x.json"
    result = subprocess.run(
        ["git", "check-ignore", str(sample)],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, ".plan-tool/purity-cache is not gitignored"


def test_entry_keyed_by_step_id(tmp_path: Path) -> None:
    path = pc.purity_cache_path(tmp_path, "x")
    cache = pc.PurityCache(plan_slug="x", entries={2: _entry(2), 5: _entry(5)})
    pc.save_purity_cache(path, cache)
    loaded = pc.load_purity_cache(path)
    assert loaded.entries[2].step_id == 2
    assert loaded.entries[5].step_id == 5


def test_load_prunes_entries_for_absent_steps(tmp_path: Path) -> None:
    path = pc.purity_cache_path(tmp_path, "x")
    pc.save_purity_cache(
        path, pc.PurityCache(plan_slug="x", entries={2: _entry(2), 9: _entry(9)})
    )
    loaded = pc.load_purity_cache(path, valid_step_ids={2})
    assert set(loaded.entries) == {2}


def test_empty_findings_distinct_from_absent_entry(tmp_path: Path) -> None:
    path = pc.purity_cache_path(tmp_path, "x")
    pc.save_purity_cache(
        path, pc.PurityCache(plan_slug="x", entries={2: _entry(2, findings=[])})
    )
    loaded = pc.load_purity_cache(path)
    assert 2 in loaded.entries  # checked, pure
    assert loaded.entries[2].findings == []
    assert 3 not in loaded.entries  # never checked


@pytest.mark.parametrize("confidence", ["supported", "limited"])
def test_findings_recommendation_fields_round_trip(
    tmp_path: Path, confidence: str
) -> None:
    path = pc.purity_cache_path(tmp_path, "x")
    entry = _entry(2, findings=[dataclasses.replace(_finding(2), confidence=confidence)])
    pc.save_purity_cache(path, pc.PurityCache(plan_slug="x", entries={2: entry}))
    rec = pc.load_purity_cache(path).entries[2].findings[0]
    src = entry.findings[0]
    assert rec.id == src.id
    assert rec.source == GRANULARITY_SPLIT_SOURCE
    assert rec.severity == src.severity
    assert rec.title == src.title
    assert rec.body == src.body
    assert rec.confidence == confidence


def test_cached_recommendation_redirect_round_trips(tmp_path: Path) -> None:
    path = pc.purity_cache_path(tmp_path, "x")
    rec = dataclasses.replace(
        _finding(2),
        redirect=Redirect(reason="plan-owned", suggested_next="plan-tool detail x"),
    )
    entry = _entry(2, findings=[rec])
    pc.save_purity_cache(path, pc.PurityCache(plan_slug="x", entries={2: entry}))

    assert pc.load_purity_cache(path).entries[2].findings[0].redirect == rec.redirect


def test_cached_finding_drops_restated_property_on_load(tmp_path: Path) -> None:
    """This cache's own findings are always ``GRANULARITY_SPLIT_SOURCE``, not
    ``plan-correctness`` -- ``restated_property`` is Correctness-axis only,
    and this is a second, independent deserialization path from
    ``review_persistence._load_recommendations`` that must enforce the same
    invariant rather than trust the parser to have gated it."""
    path = pc.purity_cache_path(tmp_path, "x")
    rec = dataclasses.replace(
        _finding(2), restated_property="should never survive here"
    )
    entry = _entry(2, findings=[rec])
    pc.save_purity_cache(path, pc.PurityCache(plan_slug="x", entries={2: entry}))

    loaded = pc.load_purity_cache(path).entries[2].findings[0]
    assert loaded.restated_property is None


def test_malformed_cached_recommendation_redirect_degrades_to_empty_cache(
    tmp_path: Path,
) -> None:
    path = pc.purity_cache_path(tmp_path, "x")
    rec = dataclasses.replace(
        _finding(2),
        redirect=Redirect(reason="plan-owned", suggested_next="plan-tool detail x"),
    )
    pc.save_purity_cache(
        path, pc.PurityCache(plan_slug="x", entries={2: _entry(2, findings=[rec])})
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["entries"]["2"]["findings"][0]["redirect"] = {"reason": "plan-owned"}
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert pc.load_purity_cache(path).entries == {}


def test_legacy_cached_confidence_loads_unknown_and_rewrite_writes_null(
    tmp_path: Path,
) -> None:
    path = pc.purity_cache_path(tmp_path, "x")
    pc.save_purity_cache(path, pc.PurityCache(plan_slug="x", entries={2: _entry(2)}))
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["entries"]["2"]["findings"][0].pop("confidence")
    path.write_text(json.dumps(payload), encoding="utf-8")

    cache = pc.load_purity_cache(path)
    assert cache.entries[2].findings[0].confidence is None
    pc.save_purity_cache(path, cache)

    rewritten = json.loads(path.read_text(encoding="utf-8"))
    assert rewritten["entries"]["2"]["findings"][0]["confidence"] is None


def test_invalid_cached_confidence_degrades_to_empty_cache(tmp_path: Path) -> None:
    path = pc.purity_cache_path(tmp_path, "x")
    pc.save_purity_cache(path, pc.PurityCache(plan_slug="x", entries={2: _entry(2)}))
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["entries"]["2"]["findings"][0]["confidence"] = "uncertain"
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert pc.load_purity_cache(path).entries == {}


def test_non_string_cached_restated_property_degrades_to_empty_cache(
    tmp_path: Path,
) -> None:
    """``_entry_from_json`` used to skip the type check
    ``review_persistence._load_recommendations`` applied, so a malformed
    ``restated_property`` (e.g. an int) reached ``restated_property_or_none``
    and crashed with an ``AttributeError`` far from this load site. Now
    shared via ``recommendation_from_persisted_mapping`` -- caught here,
    same as every other malformed-field case in this file."""
    path = pc.purity_cache_path(tmp_path, "x")
    pc.save_purity_cache(path, pc.PurityCache(plan_slug="x", entries={2: _entry(2)}))
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["entries"]["2"]["findings"][0]["restated_property"] = 42
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert pc.load_purity_cache(path).entries == {}


def test_save_is_atomic_and_creates_dir(tmp_path: Path) -> None:
    path = pc.purity_cache_path(tmp_path, "x")
    assert not path.parent.exists()
    pc.save_purity_cache(path, pc.PurityCache(plan_slug="x", entries={2: _entry(2)}))
    assert path.is_file()
    assert not list(path.parent.glob("*.tmp"))


def test_step_id_string_key_boundary(tmp_path: Path) -> None:
    import json

    path = pc.purity_cache_path(tmp_path, "x")
    pc.save_purity_cache(path, pc.PurityCache(plan_slug="x", entries={2: _entry(2)}))
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert list(on_disk["entries"]) == ["2"]  # string key on disk
    assert isinstance(next(iter(pc.load_purity_cache(path).entries)), int)


def test_purity_cache_path_location(tmp_path: Path) -> None:
    assert pc.purity_cache_path(tmp_path, "my-plan") == (
        tmp_path / ".plan-tool" / "purity-cache" / "my-plan.json"
    )


def test_malformed_file_load_posture(tmp_path: Path) -> None:
    path = pc.purity_cache_path(tmp_path, "x")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{ not valid json", encoding="utf-8")
    # Documented posture: a corrupt/newer-version file degrades to an empty cache.
    assert pc.load_purity_cache(path).entries == {}
    path.write_text('{"version": 999, "entries": {}}', encoding="utf-8")
    assert pc.load_purity_cache(path).entries == {}
