"""Classify the on-disk draft seed for every row in a roadmap manifest."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from plan_tool.roadmap_artifacts import (
    COMPONENTS_FILENAME,
    CONSTRAINTS_FILENAME,
    DOMAIN_FILENAME,
    DRAFT_SEEDS_DIRNAME,
    LEGACY_DRAFT_SEEDS_DIRNAME,
    PLANS_FILENAME,
    PlansArtifact,
    RoadmapArtifactError,
    _validate_draft_seed_path,
    resolve_draft_seed_path,
    roadmap_dir,
)
from plan_tool.roadmap_gates import (
    find_duplicate_draft_seed_basenames,
    validate_draft_seed_content,
)
from plan_tool.roadmap_seed_state import digest_text, load_seed_state, seed_state_path


DRAFT_SEED_STATE_DUPLICATE = "duplicate"
DRAFT_SEED_STATE_PATH_ESCAPING = "path-escaping"
DRAFT_SEED_STATE_MISSING = "missing"
DRAFT_SEED_STATE_DIGEST_MISMATCHED = "digest-mismatched"
DRAFT_SEED_STATE_STALE = "stale"
DRAFT_SEED_STATE_MALFORMED = "malformed"
DRAFT_SEED_STATE_CURRENT = "current"

DRAFT_SEED_STATE_PRECEDENCE = (
    DRAFT_SEED_STATE_DUPLICATE,
    DRAFT_SEED_STATE_PATH_ESCAPING,
    DRAFT_SEED_STATE_MISSING,
    DRAFT_SEED_STATE_DIGEST_MISMATCHED,
    DRAFT_SEED_STATE_STALE,
    DRAFT_SEED_STATE_MALFORMED,
    DRAFT_SEED_STATE_CURRENT,
)

_TOP_LEVEL_ARTIFACT_FILENAMES = (
    DOMAIN_FILENAME,
    CONSTRAINTS_FILENAME,
    COMPONENTS_FILENAME,
    PLANS_FILENAME,
)


class NoPublishedRoadmapVersionError(RoadmapArtifactError):
    """The roadmap folder has no accepted head, so there is nothing to read."""


def leftover_top_level_artifacts(folder: Path) -> tuple[str, ...]:
    """The top-level ``0N-*.md`` names present in a roadmap folder.

    Existence only; the files are never read. The one definition of "which
    top-level artifacts exist" for the refusal message and the warning.
    """
    return tuple(
        name for name in _TOP_LEVEL_ARTIFACT_FILENAMES if (folder / name).exists()
    )


def no_published_version_message(plans_dir: Path, slug: str) -> str:
    """Name the missing version; point at hand conversion when top-level files exist.

    Checks existence only and never reads the top-level files. See
    docs/how-to/roadmap.md section 1.
    """
    message = f"roadmap '{slug}' has no published version"
    folder = roadmap_dir(plans_dir, slug)
    if leftover_top_level_artifacts(folder):
        message += (
            "; its top-level artifact files predate versioned roadmaps and are not read — "
            "convert by hand: delete the top-level files and regenerate under the same slug, "
            "or start a successor slug from the brief (docs/how-to/roadmap.md section 1)"
        )
    return message


ORPHAN_SEED_RECORD_SIDECAR_ENTRY = "sidecar-entry"
ORPHAN_SEED_RECORD_FILE = "file"


@dataclass(frozen=True)
class DraftSeedClassification:
    """The current, computed state of one plan row's draft seed."""

    plan_id: str
    state: str
    detail: str = ""


@dataclass(frozen=True)
class OrphanSeedRecord:
    """One sidecar entry or draft file with no current plan-row owner."""

    kind: str
    plan_id: str | None = None
    path: Path | None = None


def _classification(
    plan_id: str, state: str, detail: str = ""
) -> DraftSeedClassification:
    return DraftSeedClassification(plan_id=plan_id, state=state, detail=detail)


def classify_draft_seeds(
    artifact: PlansArtifact, *, plans_dir: Path, slug: str
) -> dict[str, DraftSeedClassification]:
    """Compute each plan row's draft-seed state without changing disk state."""
    root = roadmap_dir(plans_dir, slug)
    state = load_seed_state(seed_state_path(root))
    duplicate_details = {
        violation.row_id: violation.message
        for violation in find_duplicate_draft_seed_basenames(artifact.plans)
        if violation.row_id is not None
    }
    classifications: dict[str, DraftSeedClassification] = {}

    for plan in artifact.plans:
        duplicate_detail = duplicate_details.get(plan.id)
        if duplicate_detail is not None:
            classifications[plan.id] = _classification(
                plan.id, DRAFT_SEED_STATE_DUPLICATE, duplicate_detail
            )
            continue

        entry = state["seeds"].get(plan.id)
        if entry is not None:
            try:
                _validate_draft_seed_path(entry["draft_seed_path"])
            except RoadmapArtifactError as exc:
                classifications[plan.id] = _classification(
                    plan.id, DRAFT_SEED_STATE_PATH_ESCAPING, str(exc)
                )
                continue

        try:
            source = resolve_draft_seed_path(plans_dir, slug, plan.draft_seed_path)
        except RoadmapArtifactError as exc:
            classifications[plan.id] = _classification(
                plan.id, DRAFT_SEED_STATE_PATH_ESCAPING, str(exc)
            )
            continue
        if not source.is_file():
            classifications[plan.id] = _classification(plan.id, DRAFT_SEED_STATE_MISSING)
            continue

        if entry is None or entry["digest"] is None:
            classifications[plan.id] = _classification(
                plan.id, DRAFT_SEED_STATE_DIGEST_MISMATCHED
            )
            continue

        try:
            text = source.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            if entry["status"] == "invalidated":
                classifications[plan.id] = _classification(
                    plan.id, DRAFT_SEED_STATE_STALE
                )
            else:
                classifications[plan.id] = _classification(
                    plan.id, DRAFT_SEED_STATE_MALFORMED, str(exc)
                )
            continue

        if entry["digest"] != digest_text(text):
            classifications[plan.id] = _classification(
                plan.id, DRAFT_SEED_STATE_DIGEST_MISMATCHED
            )
            continue

        if entry["status"] == "invalidated":
            classifications[plan.id] = _classification(plan.id, DRAFT_SEED_STATE_STALE)
            continue

        violations = validate_draft_seed_content(text, plan=plan)
        if violations:
            classifications[plan.id] = _classification(
                plan.id,
                DRAFT_SEED_STATE_MALFORMED,
                "\n".join(violation.message for violation in violations),
            )
            continue

        classifications[plan.id] = _classification(plan.id, DRAFT_SEED_STATE_CURRENT)

    return classifications


def find_orphan_seed_records(
    artifact: PlansArtifact, *, plans_dir: Path, slug: str
) -> tuple[OrphanSeedRecord, ...]:
    """Return sidecar entries and top-level draft files no plan row owns."""
    root = roadmap_dir(plans_dir, slug)
    state = load_seed_state(seed_state_path(root))
    plan_ids = {plan.id for plan in artifact.plans}
    records: list[OrphanSeedRecord] = [
        OrphanSeedRecord(
            kind=ORPHAN_SEED_RECORD_SIDECAR_ENTRY,
            plan_id=plan_id,
        )
        for plan_id in sorted(state["seeds"])
        if plan_id not in plan_ids
    ]

    owned_paths: set[Path] = set()
    for plan in artifact.plans:
        try:
            owned_paths.add(
                resolve_draft_seed_path(plans_dir, slug, plan.draft_seed_path)
            )
        except RoadmapArtifactError:
            continue

    for dirname in (DRAFT_SEEDS_DIRNAME, LEGACY_DRAFT_SEEDS_DIRNAME):
        directory = root / dirname
        if not directory.exists() or not directory.is_dir():
            continue
        for source in sorted(directory.iterdir(), key=lambda path: path.name):
            if not source.is_file() or source in owned_paths:
                continue
            records.append(
                OrphanSeedRecord(
                    kind=ORPHAN_SEED_RECORD_FILE,
                    path=source,
                )
            )

    return tuple(records)
