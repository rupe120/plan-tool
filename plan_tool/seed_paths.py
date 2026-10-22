"""Default seed placement; explicit caller destinations stay authoritative."""

from pathlib import Path


DEFAULT_SEEDS_SUBPATH = Path("docs") / "implementation-plans" / "plan-seeds"


def default_seeds_dir(repo_root: Path) -> Path:
    """Directory for newly generated seeds, independent of existing folders."""
    return Path(repo_root) / DEFAULT_SEEDS_SUBPATH


def published_seeds_dir(repo_root: Path, entry: dict) -> Path:
    """Retain the root destination for publications predating layout provenance."""
    if entry.get("publication_layout") == "nested":
        return default_seeds_dir(repo_root)
    return Path(repo_root) / "plan-seeds"
