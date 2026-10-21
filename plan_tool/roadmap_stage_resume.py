"""First-run resume directory for the roadmap stage run.

Sole owner of ``.plan-tool/runs/<slug>/roadmap-stage-resume/``: one
``stage-<N>.md`` per gate-clean stage plus ``brief.digest``. A damaged file
costs only its own regeneration (warned, never raised, never deleted by a
read); only a brief-digest mismatch raises. Stage text is stored unparsed;
re-gating belongs to the stage run. See ROADMAP_FORMAT.md.
"""

from __future__ import annotations

import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from plan_tool.fileio import durable_write_bytes, is_write_temp_name
from plan_tool.roadmap_artifacts import _validate_slug
from plan_tool.run_log import run_dir

RESUME_DIRNAME = "roadmap-stage-resume"
DIGEST_FILENAME = "brief.digest"

_STAGE_FILE_RE = re.compile(r"stage-([1-9][0-9]*)\.md")
_DIGEST_RE = re.compile(r"[0-9a-f]{64}")


class RoadmapStageResumeBriefChanged(Exception):
    """The brief changed since the held stages were written."""


@dataclass(frozen=True)
class HeldStages:
    directory: Path
    brief_digest: str | None
    stages: tuple[tuple[int, str], ...]
    warnings: tuple[str, ...]


def resume_dir_path(repo_root: Path, slug: str) -> Path:
    _validate_slug(slug)
    return run_dir(repo_root, slug) / RESUME_DIRNAME


def write_brief_digest(repo_root: Path, slug: str, digest: str) -> None:
    path = resume_dir_path(repo_root, slug) / DIGEST_FILENAME
    durable_write_bytes(path, (digest + "\n").encode("utf-8"))


def write_stage(repo_root: Path, slug: str, stage_number: int, text: str) -> None:
    if stage_number < 1:
        raise ValueError(f"stage number must be a positive integer: {stage_number!r}")
    path = resume_dir_path(repo_root, slug) / f"stage-{stage_number}.md"
    durable_write_bytes(path, text.encode("utf-8"))


def _read_digest(directory: Path, warnings: list[str]) -> str | None:
    path = directory / DIGEST_FILENAME
    if not path.exists():
        warnings.append(f"{path}: brief digest file is missing")
        return None
    try:
        value = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError) as exc:
        warnings.append(f"{path}: brief digest unreadable ({exc.__class__.__name__})")
        return None
    if not _DIGEST_RE.fullmatch(value):
        warnings.append(f"{path}: brief digest is not a lowercase SHA-256 hex string")
        return None
    return value


def read_held_stages(repo_root: Path, slug: str) -> HeldStages | None:
    """Return what is readable, or ``None`` when the directory is absent."""
    directory = resume_dir_path(repo_root, slug)
    if not directory.is_dir():
        return None
    warnings: list[str] = []
    brief_digest = _read_digest(directory, warnings)

    present: dict[int, Path] = {}
    for entry in sorted(directory.iterdir()):
        if entry.name == DIGEST_FILENAME or is_write_temp_name(entry.name):
            continue
        match = _STAGE_FILE_RE.fullmatch(entry.name)
        if match is None:
            warnings.append(f"{entry}: unexpected file in the resume directory, ignored")
            continue
        present[int(match.group(1))] = entry

    stages: list[tuple[int, str]] = []
    number = 1
    while number in present:
        path = present[number]
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            warnings.append(f"{path}: stage unreadable ({exc.__class__.__name__}), not held")
            break
        if not text.strip():
            warnings.append(f"{path}: stage file is empty, not held")
            break
        stages.append((number, text))
        number += 1

    for later in sorted(n for n in present if n > number):
        warnings.append(f"{present[later]}: stage follows a gap or damaged stage, not held")
    return HeldStages(directory, brief_digest, tuple(stages), tuple(warnings))


def discard_stages_from(repo_root: Path, slug: str, first_stage: int) -> None:
    directory = resume_dir_path(repo_root, slug)
    if not directory.is_dir():
        return
    for entry in directory.iterdir():
        match = _STAGE_FILE_RE.fullmatch(entry.name)
        if match is not None and int(match.group(1)) >= first_stage:
            try:
                entry.unlink(missing_ok=True)
            except OSError as exc:
                print(f"warning: {entry}: could not discard stage file ({exc})", file=sys.stderr)


def delete_resume(repo_root: Path, slug: str) -> bool:
    directory = resume_dir_path(repo_root, slug)
    if not directory.is_dir():
        return False
    shutil.rmtree(directory)
    return True


def require_matching_brief_digest(held: HeldStages, brief_digest: str) -> None:
    """Raise when held stages were written for a different brief.

    An unverifiable (``None``) held digest passes: the caller regenerates.
    """
    if held.brief_digest is None or held.brief_digest == brief_digest:
        return
    raise RoadmapStageResumeBriefChanged(
        f"the brief changed since the held stages in {held.directory} were written. "
        f"Restore the original brief, delete {held.directory} by hand, "
        "or start a successor slug."
    )
