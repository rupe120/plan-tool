from pathlib import Path

import pytest

from plan_tool.seed_paths import default_seeds_dir, published_seeds_dir


def test_new_seed_default_ignores_existing_root_seeds(tmp_path: Path) -> None:
    old = tmp_path / "plan-seeds" / "existing.md"
    old.parent.mkdir()
    old.write_text("keep these bytes")
    assert default_seeds_dir(tmp_path) == tmp_path / "docs/implementation-plans/plan-seeds"
    assert old.read_text() == "keep these bytes"
    assert not default_seeds_dir(tmp_path).exists()


@pytest.mark.parametrize("entry", [{}, {"published": True}, {"publication_layout": "root"}])
def test_legacy_publications_keep_root_even_when_nested_directory_exists(
    tmp_path: Path, entry: dict,
) -> None:
    default_seeds_dir(tmp_path).mkdir(parents=True)
    assert published_seeds_dir(tmp_path, entry) == tmp_path / "plan-seeds"


def test_new_publications_keep_nested_destination_even_when_root_exists(tmp_path: Path) -> None:
    (tmp_path / "plan-seeds").mkdir()
    assert published_seeds_dir(tmp_path, {"publication_layout": "nested"}) == default_seeds_dir(tmp_path)
