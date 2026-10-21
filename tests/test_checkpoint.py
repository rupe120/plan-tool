"""Tests for plan_tool.checkpoint.

Pure in-memory / tmp-path tests. No claude shell-out — the module is a
pure-I/O primitive, and callers in steps 2/3 (detail.py, create.py) own
their own integration tests with injected invokers.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from plan_tool.checkpoint import (
    CHECKPOINT_SCHEMA_VERSION,
    CHECKPOINTS_REL,
    DEFAULT_MAX_AGE_SECONDS,
    Checkpoint,
    checkpoint_dir,
    checkpoint_path,
    checkpoints_root,
    compute_input_hash,
    discard_checkpoint,
    load_if_valid,
    save_checkpoint,
)


# A recent, tz-aware timestamp so checkpoints minted by ``_make_checkpoint``
# stay inside ``DEFAULT_MAX_AGE_SECONDS`` (30d) regardless of the wall-clock
# date the suite runs on. A pinned literal here silently expires once "now"
# drifts past the cliff, failing the freshness-relying load tests. Tests that
# need a *stale* or *garbage* timestamp pass ``created_at`` explicitly.
_RECENT_CREATED_AT = datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _make_checkpoint(
    input_hash: str = "abc123",
    payload: str = "hello",
    created_at: str = _RECENT_CREATED_AT,
) -> Checkpoint:
    return Checkpoint(
        input_hash=input_hash,
        payload=payload,
        created_at=created_at,
    )


# ---------- path helpers ----------

def test_checkpoints_root_under_dot_plan_tool(tmp_path: Path) -> None:
    assert checkpoints_root(tmp_path) == tmp_path / ".plan-tool" / "checkpoints"
    assert CHECKPOINTS_REL[0] == ".plan-tool"


def test_checkpoint_dir_namespaces_by_slug(tmp_path: Path) -> None:
    assert (
        checkpoint_dir(tmp_path, "foo-plan")
        == tmp_path / ".plan-tool" / "checkpoints" / "foo-plan"
    )


def test_checkpoint_path_appends_json_suffix(tmp_path: Path) -> None:
    p = checkpoint_path(tmp_path, "foo", "detail-step-3")
    assert p.name == "detail-step-3.json"
    assert p.parent == checkpoint_dir(tmp_path, "foo")


# ---------- compute_input_hash ----------

def test_hash_is_deterministic_for_same_payload() -> None:
    payload = {"step_id": 1, "files": ["a", "b"]}
    assert compute_input_hash(payload) == compute_input_hash(payload)


def test_hash_is_order_independent_for_dict_keys() -> None:
    assert compute_input_hash({"a": 1, "b": 2}) == compute_input_hash(
        {"b": 2, "a": 1}
    )


def test_hash_differs_when_any_field_changes() -> None:
    base = {"step_id": 1, "files": ["a", "b"]}
    mutated = {"step_id": 1, "files": ["a", "c"]}
    assert compute_input_hash(base) != compute_input_hash(mutated)


def test_hash_handles_lists_of_strings_and_ints() -> None:
    payload = {"step_id": 1, "files": ["a", "b"], "depends_on": [3]}
    digest = compute_input_hash(payload)
    # hex sha256 digest = 64 chars
    assert isinstance(digest, str)
    assert len(digest) == 64
    int(digest, 16)  # parseable as hex


def test_hash_raises_on_non_json_serializable_input(tmp_path: Path) -> None:
    with pytest.raises(TypeError):
        compute_input_hash({"path": tmp_path})


# ---------- save_checkpoint ----------

def test_save_creates_parent_directory(tmp_path: Path) -> None:
    target = tmp_path / "a" / "b" / "c.json"
    save_checkpoint(target, _make_checkpoint())
    assert target.is_file()


def test_save_writes_all_dataclass_fields_as_json(tmp_path: Path) -> None:
    target = tmp_path / "cp.json"
    cp = _make_checkpoint(input_hash="deadbeef", payload="body")
    save_checkpoint(target, cp)

    obj = json.loads(target.read_text(encoding="utf-8"))
    assert obj == {
        "input_hash": "deadbeef",
        "payload": "body",
        "created_at": _RECENT_CREATED_AT,
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
    }


def test_save_overwrites_existing_file(tmp_path: Path) -> None:
    target = tmp_path / "cp.json"
    save_checkpoint(target, _make_checkpoint(payload="first"))
    save_checkpoint(target, _make_checkpoint(payload="second"))

    obj = json.loads(target.read_text(encoding="utf-8"))
    assert obj["payload"] == "second"


def test_save_leaves_no_temp_file_on_success(tmp_path: Path) -> None:
    target = tmp_path / "cp.json"
    save_checkpoint(target, _make_checkpoint())

    leftovers = list(target.parent.glob("*.tmp"))
    assert leftovers == []


# ---------- load_if_valid ----------

def test_load_returns_none_when_file_missing(tmp_path: Path) -> None:
    assert (
        load_if_valid(tmp_path / "missing.json", expected_input_hash="x")
        is None
    )


def test_load_returns_checkpoint_when_hash_matches(tmp_path: Path) -> None:
    target = tmp_path / "cp.json"
    cp = _make_checkpoint(input_hash="match")
    save_checkpoint(target, cp)

    loaded = load_if_valid(target, expected_input_hash="match")
    assert loaded == cp


def test_load_returns_none_when_hash_mismatch(tmp_path: Path) -> None:
    target = tmp_path / "cp.json"
    save_checkpoint(target, _make_checkpoint(input_hash="real"))

    assert load_if_valid(target, expected_input_hash="other") is None


def test_load_returns_none_when_schema_version_mismatch(tmp_path: Path) -> None:
    target = tmp_path / "cp.json"
    target.write_text(
        json.dumps(
            {
                "input_hash": "x",
                "payload": "y",
                "created_at": "2026-05-13T00:00:00+00:00",
                "schema_version": 99,
            }
        ),
        encoding="utf-8",
    )
    assert load_if_valid(target, expected_input_hash="x") is None


def test_load_returns_none_on_malformed_json(tmp_path: Path) -> None:
    target = tmp_path / "cp.json"
    target.write_text("not valid json{", encoding="utf-8")
    assert load_if_valid(target, expected_input_hash="x") is None


def test_load_returns_none_when_checkpoint_older_than_max_age(
    tmp_path: Path,
) -> None:
    """A checkpoint older than ``max_age_seconds`` is treated as
    stale even when the hash matches — protects against an abandoned
    plan's cache being silently replayed weeks later."""
    target = tmp_path / "cp.json"
    target.write_text(
        json.dumps(
            {
                "input_hash": "x",
                "payload": "y",
                # 60 days old.
                "created_at": "2026-03-14T00:00:00+00:00",
                "schema_version": CHECKPOINT_SCHEMA_VERSION,
            }
        ),
        encoding="utf-8",
    )
    # Default expiration (30d) → stale.
    assert load_if_valid(target, expected_input_hash="x") is None
    # Explicit None → no expiration check, hash matches → loads.
    cp = load_if_valid(target, expected_input_hash="x", max_age_seconds=None)
    assert cp is not None and cp.payload == "y"


def test_load_returns_none_on_unparseable_created_at(tmp_path: Path) -> None:
    """Hand-edited checkpoints with garbage timestamps shouldn't crash
    the loader — they fall through as "stale" the same way a missing
    file does."""
    target = tmp_path / "cp.json"
    target.write_text(
        json.dumps(
            {
                "input_hash": "x",
                "payload": "y",
                "created_at": "not a real timestamp",
                "schema_version": CHECKPOINT_SCHEMA_VERSION,
            }
        ),
        encoding="utf-8",
    )
    assert load_if_valid(target, expected_input_hash="x") is None


def test_load_returns_none_on_missing_required_field(tmp_path: Path) -> None:
    target = tmp_path / "cp.json"
    target.write_text(
        json.dumps(
            {
                "input_hash": "x",
                # payload missing
                "created_at": "2026-05-13T00:00:00+00:00",
                "schema_version": CHECKPOINT_SCHEMA_VERSION,
            }
        ),
        encoding="utf-8",
    )
    assert load_if_valid(target, expected_input_hash="x") is None


# ---------- discard_checkpoint ----------

def test_discard_removes_existing_file_returns_true(tmp_path: Path) -> None:
    target = tmp_path / "cp.json"
    save_checkpoint(target, _make_checkpoint())

    assert discard_checkpoint(target) is True
    assert not target.exists()


def test_discard_returns_false_when_file_absent(tmp_path: Path) -> None:
    assert discard_checkpoint(tmp_path / "ghost.json") is False
