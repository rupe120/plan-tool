"""Save / load / list saved review runs.

A saved review is a JSON file under the plan's reports directory —
``<plan-dir>/plan-details/<plan-slug>/reports/<timestamp>.json`` — containing
the rendered markdown report, the structured ``Recommendation`` list,
and a per-recommendation ``annotations`` dict that the walk feature
mutates as the user marks items. Reports live alongside the plan's detail
files (see :func:`plan_tool.detail.derive_detail_path`) so they travel with
the plan in version control.

The module is intentionally narrow: dataclasses and persistence helpers,
no CLI or claude shell-out. The CLI surface lives in ``cli.py`` and
the walk loop in ``review_walk.py``; both consume what's defined here.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

from plan_tool.audit_shapes import (
    AuditShapeAdvisory,
    AuditShapeFindingEvidence,
    is_well_formed_audit_shape_advisory,
)
from plan_tool.fileio import durable_write_text
from plan_tool.review import (
    CARRIED_RESOLUTION_APPLIED,
    CARRIED_RESOLUTION_OPEN,
    CARRIED_RESOLUTION_SKIPPED,
    Recommendation,
    RECOMMENDATION_SEVERITIES,
    recommendation_from_persisted_mapping,
)
from plan_tool.jira_grade import GRADE_JIRA, GRADE_RUN, is_known_grade
from plan_tool.schema import Plan
from plan_tool.scope_fence import _fenced_code_spans, _strip_frontmatter


# Keep ordinary review writes byte-compatible with the established v1 payload.
# The additive advisory-bearing variant uses v2 and the result-aware
# completeness variant uses v4; readers that predate either version reject it rather than
# reading a payload whose keys they cannot interpret.
SCHEMA_VERSION = 1
_ADVISORY_SCHEMA_VERSION = 2
_ROLE_AWARE_SCHEMA_VERSION = 3
_AUDIT_REVISION_SCHEMA_VERSION = 4
_SUPPORTED_SCHEMA_VERSIONS = (
    SCHEMA_VERSION,
    _ADVISORY_SCHEMA_VERSION,
    _ROLE_AWARE_SCHEMA_VERSION,
    _AUDIT_REVISION_SCHEMA_VERSION,
)

COMPLETENESS_ARTIFACT_STEM_SUFFIX = "-completeness"
COMPLETENESS_REPORT_SUFFIX = f"{COMPLETENESS_ARTIFACT_STEM_SUFFIX}.md"
COMPLETENESS_SIDECAR_SUFFIX = f"{COMPLETENESS_ARTIFACT_STEM_SUFFIX}.json"
SAMPLER_CHECKPOINT_FILENAME = "in-progress-sampler-checkpoint.json"

# Distinguishes an absent checkpoint marker from a present ``null``/false one.
_MARKER_ABSENT = object()
_SAMPLER_STATE_ABSENT = object()
# What ``update_annotation`` rewrites an unknown role as: any non-boolean
# marker re-reads as unknown in every version, so an untrusted sidecar stays
# untrusted without the rewrite inventing a trusted value.
_UNKNOWN_CHECKPOINT_ROLE_MARKER = "unknown"
_SAMPLER_LIFECYCLES = frozenset({"in-progress", "terminal-residue"})


_AUDIT_COVERAGE_LEGACY_KEYS = frozenset(
    {
        "budget_limited",
        "passes_used",
        "cap",
        "recommendation_kind",
        "recommended_passes",
        "recommendation_advice",
        "confirmation_kind",
        "conforming_pass_count",
        "failed_or_malformed_pass_count",
    }
)
_AUDIT_COVERAGE_KEYS = _AUDIT_COVERAGE_LEGACY_KEYS | frozenset(
    {"early_stop_reason"}
)
_AUDIT_COVERAGE_CONFIRMATION_KINDS = frozenset(
    {"confirmed-dry", "confirmed-low-yield"}
)
_AUDIT_COVERAGE_EARLY_STOP_REASONS = frozenset({"plan-quota"})
_VALID_AUDIT_STAGES = frozenset({"bare", "detail"})
_QUALIFIED_RESULT_HEADLINES = frozenset(
    {
        "no-qualified-current-evidence",
        "awaiting-human-action",
        "advisory-only",
        "clean",
    }
)
_QUALIFIED_RESULT_STAGES = frozenset({"bare", "detail", "not-sampled"})
_QUALIFIED_RESULT_COVERAGE = frozenset(
    {"confirmed", "unconfirmed", "unknown-legacy", "not-sampled"}
)
_QUALIFIED_RESULT_REVISION_STATUS = frozenset(
    {"current", "stale", "unknown-legacy", "not-sampled"}
)
# Revision statuses with no current audit evidence: the answer is a fresh audit.
STALE_REVISION_STATUSES = _QUALIFIED_RESULT_REVISION_STATUS - {"current"}
_QUALIFIED_RESULT_UNSET = object()


class AuditInputError(ValueError):
    """Raised when a readable audit source would hide later H2 sections."""


def normalize_audit_stage(value: object) -> Optional[str]:
    """Return a validated bare/detail stage, or ``None`` for legacy/malformed."""
    if isinstance(value, str) and value in _VALID_AUDIT_STAGES:
        return value
    return None


def normalize_audit_revision(value: object) -> Optional[dict[str, object]]:
    """Return a validated immutable plan/detail audit revision, if present.

    Accepts v1 through v3: v2 adds ``source_seed_digest`` and v3 adds
    ``project_context_digest``. See ``DATA_CONTRACT.md``'s qualified-result
    section for why older revisions stay valid instead of being rejected.
    """
    if not isinstance(value, dict):
        return None
    version = value.get("version")
    if version not in (1, 2, 3):
        return None
    expected_keys = {
        "version", "detail_grade", "plan_digest", "detail_bundle_digest", "details",
    }
    if version >= 2:
        expected_keys = expected_keys | {"source_seed_digest"}
    if version >= 3:
        expected_keys = expected_keys | {"project_context_digest"}
    if set(value) != expected_keys:
        return None
    source_seed_digest = value.get("source_seed_digest") if version >= 2 else None
    project_context_digest = (
        value.get("project_context_digest") if version >= 3 else None
    )
    if (
        not isinstance(value["detail_grade"], str)
        or not is_known_grade(value["detail_grade"])
        or not isinstance(value["plan_digest"], str)
        or not value["plan_digest"]
        or not isinstance(value["detail_bundle_digest"], str)
        or not value["detail_bundle_digest"]
        or not isinstance(value["details"], list)
        or not (
            source_seed_digest is None
            or (isinstance(source_seed_digest, str) and source_seed_digest)
        )
        or not (
            project_context_digest is None
            or (
                isinstance(project_context_digest, str)
                and project_context_digest
            )
        )
    ):
        return None
    normalized_details: list[dict[str, object]] = []
    step_ids: set[int] = set()
    for detail in value["details"]:
        if not isinstance(detail, dict) or set(detail) != {
            "step_id", "resolution", "path", "state", "digest"
        }:
            return None
        step_id = detail["step_id"]
        state = detail["state"]
        digest = detail["digest"]
        if (
            isinstance(step_id, bool)
            or not isinstance(step_id, int)
            or step_id in step_ids
            or not isinstance(detail["resolution"], str)
            or not detail["resolution"]
            or not isinstance(detail["path"], str)
            or not detail["path"]
            or not isinstance(state, str)
            or state not in {"present", "missing", "unreadable"}
            or (state == "present" and (not isinstance(digest, str) or not digest))
            or (state != "present" and digest is not None)
        ):
            return None
        step_ids.add(step_id)
        normalized_details.append(
            {
                "step_id": step_id,
                "resolution": detail["resolution"],
                "path": detail["path"],
                "state": state,
                "digest": digest,
            }
        )
    normalized = {
        "version": 3,
        "detail_grade": value["detail_grade"],
        "plan_digest": value["plan_digest"],
        "detail_bundle_digest": value["detail_bundle_digest"],
        "details": normalized_details,
        "source_seed_digest": source_seed_digest,
        "project_context_digest": project_context_digest,
    }
    from plan_tool.fingerprint import _audit_input_digest

    encoded = json.dumps(
        normalized_details, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    if normalized["detail_bundle_digest"] != _audit_input_digest(encoded):
        return None
    return normalized


def normalize_qualified_result(value: object) -> Optional[dict[str, object]]:
    """Return a validated immutable completeness result, if present."""
    if not isinstance(value, dict) or set(value) != {
        "headline", "stage", "coverage", "revision_status", "audit_revision"
    }:
        return None
    headline = value["headline"]
    stage = value["stage"]
    coverage = value["coverage"]
    revision_status = value["revision_status"]
    if not all(
        isinstance(item, str)
        for item in (headline, stage, coverage, revision_status)
    ) or (
        headline not in _QUALIFIED_RESULT_HEADLINES
        or stage not in _QUALIFIED_RESULT_STAGES
        or coverage not in _QUALIFIED_RESULT_COVERAGE
        or revision_status not in _QUALIFIED_RESULT_REVISION_STATUS
    ):
        return None
    audit_revision = value["audit_revision"]
    if audit_revision is None:
        if (stage, coverage, revision_status) != (
            "not-sampled", "not-sampled", "not-sampled"
        ):
            return None
        return {
            "headline": headline,
            "stage": stage,
            "coverage": coverage,
            "revision_status": revision_status,
            "audit_revision": None,
        }
    normalized_revision = normalize_audit_revision(audit_revision)
    if normalized_revision is None or (
        "not-sampled" in {stage, coverage, revision_status}
    ):
        return None
    return {
        "headline": headline,
        "stage": stage,
        "coverage": coverage,
        "revision_status": revision_status,
        "audit_revision": normalized_revision,
    }


def normalize_audit_coverage(value: object) -> Optional[dict[str, object]]:
    """Return the canonical saved form of a conceptual-audit coverage result.

    A saved coverage object is deliberately stricter than the presentation
    payload: it records only producer states that ``audit_plan_until_stable``
    can emit. ``None`` means no trustworthy evidence was supplied, which is
    how a missing or malformed optional legacy field remains distinct from a
    known clean audit.
    """
    if not isinstance(value, dict):
        return None
    legacy_coverage = set(value) == _AUDIT_COVERAGE_LEGACY_KEYS
    if not legacy_coverage and set(value) != _AUDIT_COVERAGE_KEYS:
        return None

    budget_limited = value["budget_limited"]
    passes_used = value["passes_used"]
    cap = value["cap"]
    confirmation_kind = value["confirmation_kind"]
    conforming_pass_count = value["conforming_pass_count"]
    failed_or_malformed_pass_count = value["failed_or_malformed_pass_count"]
    early_stop_reason = None if legacy_coverage else value["early_stop_reason"]
    if (
        not isinstance(budget_limited, bool)
        or isinstance(passes_used, bool)
        or not isinstance(passes_used, int)
        or isinstance(cap, bool)
        or not isinstance(cap, int)
        or isinstance(conforming_pass_count, bool)
        or not isinstance(conforming_pass_count, int)
        or conforming_pass_count < 0
        or isinstance(failed_or_malformed_pass_count, bool)
        or not isinstance(failed_or_malformed_pass_count, int)
        or failed_or_malformed_pass_count < 0
        or passes_used < 1
        or cap < 1
        or passes_used > cap
        or any(
            value[name] is not None
            for name in (
                "recommendation_kind",
                "recommended_passes",
                "recommendation_advice",
            )
        )
        or not (
            confirmation_kind is None
            or isinstance(confirmation_kind, str)
        )
        or not (
            early_stop_reason is None
            or isinstance(early_stop_reason, str)
        )
        or confirmation_kind not in _AUDIT_COVERAGE_CONFIRMATION_KINDS | {None}
        or early_stop_reason not in _AUDIT_COVERAGE_EARLY_STOP_REASONS | {None}
    ):
        return None

    if early_stop_reason == "plan-quota":
        if (
            budget_limited
            or confirmation_kind is not None
            or failed_or_malformed_pass_count < 1
        ):
            return None
    elif budget_limited:
        if cap <= 1 or passes_used != cap or confirmation_kind is not None:
            return None
    elif confirmation_kind is None:
        # A cap-one audit records observed coverage even though no second pass
        # confirmed a dry tail. It is not legacy/unknown data.
        if passes_used != 1 or cap != 1:
            return None
    elif (
        confirmation_kind == "confirmed-low-yield" and passes_used < 2
    ):
        return None

    normalized = {
        "budget_limited": budget_limited,
        "passes_used": passes_used,
        "cap": cap,
        "recommendation_kind": None,
        "recommended_passes": None,
        "recommendation_advice": None,
        "confirmation_kind": confirmation_kind,
        "conforming_pass_count": conforming_pass_count,
        "failed_or_malformed_pass_count": failed_or_malformed_pass_count,
        "early_stop_reason": early_stop_reason,
    }
    if legacy_coverage:
        normalized.pop("early_stop_reason")
    return normalized


def audit_coverage_qualifies_sample(coverage: object) -> bool:
    """Return True when coverage records a qualifying conceptual-audit sample.

    Pass-conformance only (``conforming_pass_count >= 1`` and
    ``failed_or_malformed_pass_count == 0``), except that an explicit terminal
    plan-quota stop never qualifies. The predicate remains deliberately
    independent of ``budget_limited``. This is the predicate ``_resolve_audit_reuse`` uses
    to decide whether a saved sample is trustworthy enough to auto-accept
    under non-interactive reuse; a caller that instead needs "was this run
    actually confirmed/converged" (e.g. the completeness-audit stage bar's
    clean/CI-gating signal) must additionally check ``budget_limited``
    itself -- do not fold that into this shared predicate, which other,
    unrelated callers rely on keeping conformance-only.
    """
    normalized = normalize_audit_coverage(coverage)
    if normalized is None and isinstance(coverage, dict):
        if coverage.get("evidence_status") != "observed":
            return False
        normalized = normalize_audit_coverage(
            {key: coverage.get(key) for key in _AUDIT_COVERAGE_KEYS}
        )
    if normalized is None:
        return False
    return (
        normalized.get("early_stop_reason") is None
        and
        normalized["conforming_pass_count"] >= 1
        and normalized["failed_or_malformed_pass_count"] == 0
    )


def audit_coverage_withholds_final_findings_sidecar(coverage: object) -> bool:
    """Return whether terminal coverage forbids a final findings sidecar."""
    return (
        isinstance(coverage, dict)
        and coverage.get("early_stop_reason") == "plan-quota"
    )


def project_audit_coverage(value: object) -> dict[str, object]:
    """Return the public coverage shape for known or legacy-unknown input."""
    normalized = normalize_audit_coverage(value)
    if normalized is None:
        return {
            "evidence_status": "unknown-legacy",
            "budget_limited": None,
            "passes_used": None,
            "cap": None,
            "recommendation_kind": None,
            "recommended_passes": None,
            "recommendation_advice": None,
            "confirmation_kind": None,
            "conforming_pass_count": None,
            "failed_or_malformed_pass_count": None,
            "early_stop_reason": None,
        }
    projected = {"evidence_status": "observed", **normalized}
    if normalized.get("early_stop_reason") is None:
        projected.pop("early_stop_reason", None)
    return projected


def normalize_sampler_state(value: object) -> Optional[dict[str, object]]:
    """Return a lifecycle-bearing sampler state mapping, if it is well-formed."""
    if not isinstance(value, dict) or value.get("lifecycle") not in _SAMPLER_LIFECYCLES:
        return None
    return dict(value)


def _normalize_checkpoint_role(
    marker: object,
    *,
    version: int,
    kind: str,
    sampler_state: object = _SAMPLER_STATE_ABSENT,
    qualified_result: object = _QUALIFIED_RESULT_UNSET,
) -> Optional[bool]:
    """Return the three-state saved-review role for a raw marker value.

    ``True`` is a confirmed pre-apply checkpoint, ``False`` an ordinary final
    artifact, ``None`` role metadata no reader may trust as final. Fails
    closed: only a version-3/4 completeness sidecar carrying a real JSON
    boolean has a recognized role. A sampler state further requires the
    version-4 completeness checkpoint form with a null result. See
    DATA_CONTRACT.md § ``SavedReview``.
    """
    if sampler_state is not _SAMPLER_STATE_ABSENT:
        if (
            normalize_sampler_state(sampler_state) is None
            or version != _AUDIT_REVISION_SCHEMA_VERSION
            or kind != "completeness"
            or marker is not True
            or qualified_result is not None
        ):
            return None
    if version not in {_ROLE_AWARE_SCHEMA_VERSION, _AUDIT_REVISION_SCHEMA_VERSION}:
        return False if marker is _MARKER_ABSENT else None
    if kind != "completeness" or not isinstance(marker, bool):
        return None
    return marker


@dataclass(frozen=True)
class AuditInputDetail:
    """One grade-selected detail artifact captured for an audit prompt."""

    step_id: int
    resolution: str
    selected_path: str
    state: str
    content: bytes = b""


@dataclass(frozen=True)
class AuditInputSnapshot:
    """Immutable plan/detail/context inputs and their audit fingerprint.

    The conceptual audit takes this one snapshot before sampling. It parses the
    same captured plan text that it fingerprints, one confirmed project
    context block, and the selected-grade detail resolver for each declared
    step, including pointer-missing and unreadable states. This is deliberately
    narrower than
    ``compute_plan_fingerprint``:
    it represents the exact bytes the model was shown, not a directory glob.
    """

    plan: Plan
    plan_bytes: bytes
    plan_body: str
    details: tuple[AuditInputDetail, ...]
    fingerprint: str
    detail_grade: str = GRADE_RUN
    # Bytes of ``plan.source_seed`` at capture time, or ``None`` when unset,
    # outside the repo, or unreadable (BACKLOG #162) — folded into
    # ``fingerprint`` so a seed edited between ``--iterate`` passes counts as
    # drift like a plan/detail edit does, and so the scope-contract block a
    # multi-pass audit renders stays pinned to this one capture rather than
    # re-reading the seed live on every pass.
    source_seed_bytes: Optional[bytes] = None
    # Rendered project-level scope context captured with this audit. Empty for
    # repositories without a valid profile, preserving legacy fingerprints.
    project_context: str = ""

    @classmethod
    def capture(
        cls,
        plan_path: Path,
        repo_root: Path,
        *,
        detail_grade: str = GRADE_RUN,
    ) -> "AuditInputSnapshot":
        from plan_tool.detail_artifacts import (
            derive_jira_detail_path,
            resolve_detail_artifact,
        )
        from plan_tool.parser import _split_frontmatter, parse_plan_text
        from plan_tool.project_profile import project_profile_context

        if not is_known_grade(detail_grade):
            raise ValueError(f"unknown detail grade: {detail_grade!r}")
        plan_bytes = plan_path.read_bytes()
        plan_text = plan_bytes.decode("utf-8")
        plan = parse_plan_text(plan_text)
        plan_body = _split_frontmatter(plan_text).body
        # Pass the raw plan_text, not plan_body — _reject_unmatched_audit_fence
        # does its own frontmatter stripping internally (needed for its other
        # caller below, which passes raw seed text). Re-stripping the already-
        # stripped plan_body would treat a bare "---" divider line inside the
        # body's own prose as a second frontmatter block and excise everything
        # up to it, hiding a genuine unmatched fence that follows.
        _reject_unmatched_audit_fence(plan_text, plan_path)
        details: list[AuditInputDetail] = []
        for step in plan.steps:
            if detail_grade == GRADE_JIRA:
                selected = derive_jira_detail_path(plan_path, plan, step)
                selected_path = str(selected.resolve(strict=False))
                branch = "jira"
                on_disk = selected.is_file()
            else:
                resolution = resolve_detail_artifact(
                    plan_path, plan, step, repo_root
                )
                selected = resolution.path
                selected_path = str(selected.resolve(strict=False))
                branch = "pointer" if resolution.pointer_set else "canonical"
                on_disk = resolution.on_disk
            if not on_disk:
                details.append(
                    AuditInputDetail(step.id, branch, selected_path, "missing")
                )
                continue
            try:
                content = selected.read_bytes()
            except OSError:
                details.append(
                    AuditInputDetail(step.id, branch, selected_path, "unreadable")
                )
            else:
                details.append(
                    AuditInputDetail(
                        step.id, branch, selected_path, "present", content
                    )
                )
        source_seed_path = _resolve_source_seed_path(plan, repo_root)
        source_seed_bytes = _read_source_seed_bytes(plan, repo_root)
        if source_seed_bytes is not None and source_seed_path is not None:
            try:
                source_seed_text = source_seed_bytes.decode("utf-8")
            except UnicodeDecodeError:
                source_seed_text = ""
            _reject_unmatched_audit_fence(source_seed_text, source_seed_path)
        project_context = project_profile_context(repo_root)
        return cls(
            plan=plan,
            plan_bytes=plan_bytes,
            plan_body=plan_body,
            details=tuple(details),
            fingerprint=_audit_input_fingerprint(
                plan_bytes, details, detail_grade,
                source_seed_bytes=source_seed_bytes,
                project_context=project_context,
            ),
            detail_grade=detail_grade,
            source_seed_bytes=source_seed_bytes,
            project_context=project_context,
        )

    def detail_for_step(self, step_id: int) -> AuditInputDetail | None:
        return next((item for item in self.details if item.step_id == step_id), None)

    def matches_disk(self, plan_path: Path, repo_root: Path) -> bool:
        """Whether current selected-grade inputs exactly match this capture."""
        try:
            return self.fingerprint == self.capture(
                plan_path, repo_root, detail_grade=self.detail_grade
            ).fingerprint
        except Exception:  # noqa: BLE001 — freshness is advisory fail-closed
            return False

    @property
    def revision(self) -> dict[str, object]:
        """JSON-safe audit revision derived only from captured inputs."""
        from plan_tool.fingerprint import audit_input_revision

        return audit_input_revision(self)


def _reject_unmatched_audit_fence(source_text: str, source: Path) -> None:
    if _fenced_code_spans(_strip_frontmatter(source_text)).unmatched_opening is not None:
        raise AuditInputError(
            f"{source}: unmatched opening code fence; add a matching closing fence "
            "before auditing."
        )


def _resolve_source_seed_path(plan: Plan, repo_root: Path) -> Optional[Path]:
    """Resolve the readable live or archived source seed without changing fallback."""
    if not plan.source_seed:
        return None
    from plan_tool.pathutil import is_within, latest_seed_archive

    seed_path = repo_root / plan.source_seed
    if not is_within(seed_path, repo_root):
        return None
    if not seed_path.is_file():
        archived = latest_seed_archive(seed_path)
        if archived is None or not is_within(archived, repo_root):
            return None
        seed_path = archived
    return seed_path


def _read_source_seed_bytes(plan: Plan, repo_root: Path) -> Optional[bytes]:
    """Bytes of ``plan.source_seed`` at capture time, or ``None``.

    Same containment posture as :func:`plan_tool.review._format_scope_contract_block`
    — unset, outside-repo, or unreadable all collapse to ``None`` rather than
    raise, since this is an optional informational input to the prompt.

    Falls back to :func:`plan_tool.pathutil.latest_seed_archive` when the
    recorded path is gone: ``create --from-existing`` unconditionally
    archives its seed right after publishing the new plan (BACKLOG #162 —
    the common case, not an edge case, so a missing seed at its original
    path must not read as "never had one" before checking there).
    """
    seed_path = _resolve_source_seed_path(plan, repo_root)
    if seed_path is None:
        return None
    try:
        return seed_path.read_bytes()
    except OSError:
        return None


def _audit_input_fingerprint(
    plan_bytes: bytes,
    details: list[AuditInputDetail] | tuple[AuditInputDetail, ...],
    detail_grade: str = GRADE_RUN,
    *,
    source_seed_bytes: Optional[bytes] = None,
    project_context: str = "",
) -> str:
    """Hash framed prompt inputs without the generic saved-review glob."""
    h = hashlib.sha256()

    def add(label: str, value: bytes) -> None:
        h.update(label.encode("utf-8"))
        h.update(b"\0")
        h.update(str(len(value)).encode("ascii"))
        h.update(b"\0")
        h.update(value)
        h.update(b"\0")

    add("audit-input-v3", b"")
    add("detail-grade", detail_grade.encode("utf-8"))
    add("plan", plan_bytes)
    for detail in details:
        add("step", str(detail.step_id).encode("ascii"))
        add("resolution", detail.resolution.encode("utf-8"))
        add("path", detail.selected_path.encode("utf-8", errors="surrogateescape"))
        add("state", detail.state.encode("ascii"))
        if detail.state == "present":
            add("content", detail.content)
    add("source-seed-present", b"1" if source_seed_bytes is not None else b"0")
    if source_seed_bytes is not None:
        add("source-seed", source_seed_bytes)
    if project_context:
        add("project-context", project_context.encode("utf-8"))
    return h.hexdigest()


def audit_input_fingerprint_matches_disk(
    plan_path: Path, repo_root: Path, fingerprint: str, *, detail_grade: str = GRADE_RUN
) -> bool:
    """Recompute audit freshness through the same capture/resolver path."""
    if not isinstance(fingerprint, str) or not fingerprint:
        return False
    try:
        return AuditInputSnapshot.capture(
            plan_path, repo_root, detail_grade=detail_grade
        ).fingerprint == fingerprint
    except Exception:  # noqa: BLE001 — a bad current input is simply stale
        return False


def _hash_file_into(h: "hashlib._Hash", p: Path) -> None:
    """Stream ``p``'s bytes into ``h`` in 64 KB chunks; skip if unreadable.

    Mirrors :func:`plan_tool.drift_detection.compute_content_hash`'s
    chunked-read / silent-skip posture. Inlined rather than imported so
    this module stays a stdlib-only leaf (no ``drift_detection`` edge);
    the duplication is the permanent cost of that leaf status.
    """
    try:
        with p.open("rb") as fh:
            while True:
                chunk = fh.read(65_536)
                if not chunk:
                    break
                h.update(chunk)
    except OSError:
        pass


def compute_plan_fingerprint(plan_path: Path) -> str:
    """Return a stable SHA-256 hex digest over a plan and its detail bundle.

    Hashes the plan markdown file's bytes, then every detail file in
    ``<plan_path.parent>/plan-details/<slug>/*.md`` (the bundle root —
    the ``reports/`` subdir is excluded by globbing ``*.md`` non-
    recursively), each framed as ``name\\0content`` so the digest moves
    when a detail file is added, removed, or renamed even if surviving
    bytes are unchanged. Detail files are ``sorted()`` by name so
    filesystem enumeration order never perturbs the result.

    This is the *plan-side* axis only; the code axis is the caller-
    supplied ``code_fingerprint`` (a path→hash dict), kept opaque here
    so this module stays a stdlib-only leaf and never walks the repo
    itself. A missing plan file or unreadable detail contributes nothing
    rather than raising (matching ``compute_content_hash``'s skip-
    silently posture), so the digest stays stable and non-empty.
    """
    from plan_tool.locator import slug_from_filename

    h = hashlib.sha256()
    _hash_file_into(h, plan_path)
    slug = slug_from_filename(plan_path)  # default_to_stem=True → never None
    assert slug is not None
    bundle_dir = plan_path.parent / "plan-details" / slug
    for detail in sorted(bundle_dir.glob("*.md"), key=lambda p: p.name):
        h.update(detail.name.encode("utf-8"))
        h.update(b"\0")
        _hash_file_into(h, detail)
    return h.hexdigest()


@dataclass(frozen=True)
class Annotation:
    """One user mark on a recommendation, recorded during a walk.

    ``status`` is ``"applied"``, ``"skip"``, ``"failed"``, or
    ``"open"`` (the implicit default for items the user hasn't reached
    yet). Historically ``"done"`` was used in place of ``"applied"``;
    the loader silently rewrites ``"done"`` → ``"applied"`` so older
    saved files keep working. ``note`` is free-form prose; empty
    string when unset.

    ``"failed"`` is a **non-terminal** mark: the apply attempt errored
    out (Claude exited non-zero / a launcher error, snapshot restored —
    no edit landed), distinct from a deliberate ``"skip"``. The re-walk
    pre-skip does NOT treat it as answered, so the gap is re-prompted on
    the next walk without ``--rewalk`` instead of being silently treated
    as resolved. For carry-forward it reads as unresolved/open.

    ``halt_reason`` disambiguates *why* a ``"skip"`` was recorded:
    ``""`` (default) means the user declined the rec, while
    ``"drift"`` means a pre-apply drift halt skipped it for safety (no
    apply landed, no choice was made). Downstream tooling reading a
    saved review can tell a deliberate decline from a safety skip
    instead of seeing both as plain ``"skip"``.
    """

    status: str
    note: str = ""
    halt_reason: str = ""


def carried_resolution_from_annotations(
    annotations: dict[str, Annotation],
) -> dict[str, tuple[str, str]]:
    """Translate saved review marks into carry-forward resolution tuples."""
    resolutions: dict[str, tuple[str, str]] = {}
    for rec_id, ann in annotations.items():
        if ann.status == "applied":
            resolutions[rec_id] = (CARRIED_RESOLUTION_APPLIED, "")
        elif ann.status == "skip":
            resolutions[rec_id] = (
                CARRIED_RESOLUTION_SKIPPED,
                ann.halt_reason,
            )
        else:
            resolutions[rec_id] = (CARRIED_RESOLUTION_OPEN, "")
    return resolutions


@dataclass
class SavedReview:
    """In-memory representation of one persisted review run.

    Mutable by design: the walk loop appends to ``annotations`` and
    persists incrementally. ``report_md`` is treated as frozen.
    ``recommendations`` is typically frozen too, but the iteration
    loop's triage path (``cli._iterate_reconcile_loop``, session 4
    follow-up) reassigns ``loaded.recommendations`` in memory to the
    apply-eligible subset before passing to ``_walk_with_reconcile_phase``
    -- the on-disk JSON keeps the full set (so later ``reconcile-plan-walk``
    invocations see every finding), but the in-memory object reflects
    the filtered walk. Callers that read ``recommendations`` after
    the iteration loop has mutated it will see the apply-only subset;
    re-load from disk if the full set is needed.

    ``kind`` distinguishes the producer: ``"review"`` (default; from
    ``plan-tool reconcile-plan``), ``"completeness"`` (from
    ``plan-tool completeness-audit``), ``"detail-reconcile"`` (from
    ``plan-tool detail <name> --reconcile`` — plan/detail-side audit
    against the code), or ``"run-reconcile"`` (from
    ``plan-tool run <name> --reconcile`` — code-side audit against the
    plan, with refuse-and-redirect signal for plan-rooted findings).
    The walk loop renders the same way for all kinds; the field exists
    so listings, filenames, and CLI help text can distinguish them.

    ``plan_fingerprint`` / ``code_fingerprint`` capture the plan and code
    state at save time so a reused completeness audit can tell whether
    either moved underneath it. ``plan_fingerprint`` is the digest from
    :func:`compute_plan_fingerprint`; ``""`` is the unset/legacy sentinel.
    ``code_fingerprint`` is **opaque to this module** — a caller-defined
    path→hash map (relative-path string → content-hash hex) that this
    module never interprets, validates, or recomputes. Storing it as
    plain data is what keeps ``review_persistence.py`` a leaf free of a
    ``scope_guard`` / ``drift_detection`` import. Because ``{}`` is
    ambiguous — both a never-computed capture and a legitimately empty
    watched-code surface (docs-only or pre-implementation plans) —
    ``code_fingerprint_present`` disambiguates: ``False`` = never computed
    (legacy/unset → stale), ``True`` = computed (even if the map is
    empty). Freshness logic gates on this marker, never on
    ``code_fingerprint`` truthiness.

    ``is_pre_apply_checkpoint`` is the persisted role: ``True`` = a confirmed
    non-final completeness checkpoint, ``False`` = an ordinary final artifact,
    ``None`` = unknown metadata that readers must not trust as final.
    ``sampler_state`` distinguishes an in-progress sampler boundary from a
    pre-apply checkpoint. DATA_CONTRACT.md § ``SavedReview`` owns the full
    version and malformed-marker policy.
    """

    plan_slug: str
    plan_path: str  # repo-relative path stored as a posix string
    created_at: str  # ISO-8601 UTC, e.g. "2026-05-05T12:34:56Z"
    report_md: str
    recommendations: list[Recommendation]
    annotations: dict[str, Annotation] = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION
    path: Optional[Path] = None  # populated by load_review; None right after save
    kind: str = "review"  # "review" | "completeness" | "detail-reconcile" | "run-reconcile"
    step_id: Optional[int] = None  # set for the reconcile kinds to identify the audited step
    plan_fingerprint: str = ""  # compute_plan_fingerprint digest; "" = unset/legacy
    code_fingerprint: dict[str, str] = field(default_factory=dict)  # opaque path→hash map
    code_fingerprint_present: bool = False  # True iff code_fingerprint was computed
    # Per-step detail-file snapshot at audit time (BACKLOG #61): a
    # path→hash map of each step's on-disk detail file (bare steps absent),
    # so a later apply can re-validate a target hasn't drifted since the
    # audit. Same opaque/present-marker pattern as ``code_fingerprint``.
    detail_bundle_fingerprint: dict[str, str] = field(default_factory=dict)
    detail_bundle_fingerprint_present: bool = False
    # ``True`` only when the run-reconcile producer parsed either a
    # well-formed findings list or the explicit clean sentinel. ``None`` is
    # legacy/unknown and must not be treated as evidence that an absent
    # finding was cleared.
    outcome_evidence_valid: Optional[bool] = None
    # Optional non-routing conceptual-audit shape result. Kept separate from
    # recommendations so it cannot enter a walk or an apply dispatcher.
    audit_shape_advisory: Optional[AuditShapeAdvisory] = None
    # Optional completeness-sidecar provenance. ``None`` means the sidecar
    # predates coverage persistence or its optional payload was malformed;
    # callers project that state as ``unknown-legacy`` rather than clean.
    audit_coverage: Optional[dict[str, object]] = None
    # Persisted checkpoint role, version-4 fenced for new writes: ``True`` = a
    # confirmed non-final checkpoint (a pre-apply checkpoint, or — with
    # ``sampler_state`` also set — an in-progress sampler boundary),
    # ``False`` = ordinary final, ``None`` = unknown.
    is_pre_apply_checkpoint: Optional[bool] = False
    # Optional sampler recovery state. A lifecycle-bearing mapping marks this
    # non-final completeness artifact as either resumable or terminal residue.
    sampler_state: Optional[dict[str, object]] = None
    # Optional #238 plan-mass snapshot (opaque JSON dict — this module never
    # interprets it; see ``plan_tool.completeness_report.plan_mass_to_json``).
    # ``None`` for a sidecar saved before this field existed or a producer
    # that doesn't compute it (e.g. a jira-grade audit).
    plan_mass: Optional[dict] = None
    # The bare/detail bar under which a completeness audit ran. ``None`` means
    # legacy or malformed — readers must not infer from the live plan bundle.
    audit_stage: Optional[str] = None
    # Captured plan/detail provenance for a recovery checkpoint.  It is kept
    # distinct from ``qualified_result.audit_revision`` because a checkpoint
    # is deliberately not a final qualified result.
    checkpoint_audit_revision: Optional[dict[str, object]] = None
    # BACKLOG #166: the sorted ids of every step parsed from the plan at save
    # time (parked steps included — this module never imports
    # ``completeness_report``'s committed-step filter, to stay a leaf).
    # ``save_review`` computes this from its optional ``plan`` argument when
    # supplied, else self-parses ``plan_path`` — so every producer/kind
    # carries the signal, with no call-site changes required. Distinct from
    # #238's ``plan_mass.step_count`` (that field is fenced to reporting
    # only, never a warning input — see BACKLOG #238's scope contract) —
    # this is a dedicated identity signal for ``convergence_diagnosis``'s
    # own re-decomposition check.
    # ``step_ids_present`` disambiguates a real empty tuple from a parse
    # failure at save time (fail-soft: a plan-parse hiccup must never break an
    # otherwise-successful save), matching ``code_fingerprint_present``.
    step_ids: tuple[int, ...] = ()
    step_ids_present: bool = False

    @property
    def qualified_result(self) -> Optional[dict[str, object]]:
        """Return the optional persisted result without making it a schema field."""
        return getattr(self, "_qualified_result", None)

    @property
    def audit_revision(self) -> Optional[dict[str, object]]:
        """Return final, checkpoint, or earlier-v4 audit provenance."""
        result = self.qualified_result
        if result is not None:
            return result["audit_revision"]
        if (
            self.is_pre_apply_checkpoint is True
            and self.checkpoint_audit_revision is not None
        ):
            return self.checkpoint_audit_revision
        return getattr(self, "_legacy_audit_revision", None)

    @property
    def is_sampler_checkpoint(self) -> bool:
        """Return whether this is a sampler checkpoint of any lifecycle."""
        return self.is_pre_apply_checkpoint is True and self.sampler_state is not None

    @property
    def is_in_progress_sampler_checkpoint(self) -> bool:
        """Return whether this is a resumable sampler recovery boundary."""
        return (
            self.kind == "completeness"
            and self.schema_version == _AUDIT_REVISION_SCHEMA_VERSION
            and self.is_pre_apply_checkpoint is True
            and self.qualified_result is None
            and self.sampler_state is not None
            and self.sampler_state.get("lifecycle") == "in-progress"
        )


@dataclass(frozen=True)
class SavedCompletenessResultView:
    """Read-time plan/detail freshness for an immutable saved result."""

    qualified_result: Optional[dict[str, object]]
    view_revision_status: str

    @property
    def is_current_final_qualified(self) -> bool:
        return (
            self.qualified_result is not None
            and self.qualified_result["headline"]
            in {"awaiting-human-action", "advisory-only", "clean"}
            and self.qualified_result["coverage"] == "confirmed"
            and self.qualified_result["revision_status"] == "current"
            and self.view_revision_status == "current"
        )


def project_saved_completeness_result(
    saved: SavedReview,
    plan_path: Optional[Path],
    repo_root: Path,
) -> SavedCompletenessResultView:
    """Project current plan/detail freshness without changing saved evidence."""
    result = saved.qualified_result
    if saved.kind != "completeness" or not isinstance(result, dict):
        return SavedCompletenessResultView(None, "unavailable")
    audit_revision = result["audit_revision"]
    if audit_revision is None:
        return SavedCompletenessResultView(result, "not-sampled")
    if plan_path is None:
        return SavedCompletenessResultView(result, "unknown")
    try:
        current = AuditInputSnapshot.capture(
            plan_path, repo_root, detail_grade=audit_revision["detail_grade"]
        )
    except Exception:  # noqa: BLE001 — saved evidence must fail closed
        return SavedCompletenessResultView(result, "unknown")
    return SavedCompletenessResultView(
        result,
        "current" if current.revision == audit_revision else "stale",
    )


def plan_reports_dir(plan_path: Path) -> Path:
    """Return the per-plan reports directory: the canonical save location.

    ``<plan_path.parent>/plan-details/<plan_slug>/reports/`` — alongside the
    plan's detail files, mirroring :func:`plan_tool.detail.derive_detail_path`.
    ``plan_slug`` strips a leading ``<digit>-`` from the plan filename's stem.
    Doesn't create the directory — callers do that on save.
    """
    from plan_tool.locator import slug_from_filename

    slug = slug_from_filename(plan_path)  # default_to_stem=True → never None
    assert slug is not None
    return plan_path.parent / "plan-details" / slug / "reports"


def sampler_checkpoint_path(plan_path: Path) -> Path:
    """Return the stable non-final sampler checkpoint path for ``plan_path``."""
    return plan_reports_dir(plan_path) / SAMPLER_CHECKPOINT_FILENAME


def _abs_plan_path(repo_root: Path, plan_path: str) -> Path:
    """Resolve the stored ``plan_path`` string to an absolute plan file path.

    Callers store ``plan_path`` as a repo-relative posix string when the plan
    lives under ``repo_root``, else an absolute string (the
    ``relative_to(...)`` / ``str(...resolve())`` pattern in ``cli.py``). Invert
    that here so the reports directory can be derived from the plan's location.
    """
    p = Path(plan_path)
    return p if p.is_absolute() else repo_root / p


def _current_step_ids(abs_plan_path: Path) -> Optional[tuple[int, ...]]:
    """The sorted ids of every step currently parsed from ``abs_plan_path``.

    ``None`` on the same parse-failure set every other soft-fail plan re-read
    in this codebase catches (missing file, malformed frontmatter/YAML,
    schema validation — e.g. ``completeness_report.write_completeness_report``'s
    own signature-stamp and audit-stage-derivation guards) — fail-soft,
    matching this function's only caller: a plan-parse hiccup at save time
    must never break an otherwise-successful report save (BACKLOG #166).
    """
    from plan_tool.parser import ParseError, ValidationError, parse_plan

    try:
        plan = parse_plan(abs_plan_path)
    except (
        FileNotFoundError,
        OSError,
        UnicodeDecodeError,
        ParseError,
        ValidationError,
    ):
        return None
    return tuple(sorted(step.id for step in plan.steps))


def _utc_now_iso() -> str:
    """ISO-8601 UTC with trailing ``Z`` (matches the lessons-log timestamps)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _timestamp_filename(
    now: Optional[datetime] = None, *, kind: str = "review"
) -> str:
    """Filename-safe timestamp: ``YYYYMMDD-HHMMSS[-<kind>].json``.

    Filesystem-safe (no colons), sortable lexically, second-precision
    is fine because reviews aren't generated at sub-second cadence.
    The kind suffix is omitted for the default ``"review"`` so existing
    saves stay byte-compatible with pre-reconcile callers; non-default
    kinds embed verbatim — e.g. ``kind="reconcile"`` →
    ``YYYYMMDD-HHMMSS-reconcile.json``, ``kind="detail-reconcile"`` →
    ``YYYYMMDD-HHMMSS-detail-reconcile.json``,
    ``kind="run-reconcile"`` → ``YYYYMMDD-HHMMSS-run-reconcile.json``.
    """
    ts = (now or datetime.now(timezone.utc)).strftime("%Y%m%d-%H%M%S")
    if kind == "review":
        return f"{ts}.json"
    if kind == "completeness":
        return f"{ts}{COMPLETENESS_SIDECAR_SUFFIX}"
    return f"{ts}-{kind}.json"


def save_review(
    *,
    plan_slug: str,
    plan_path: str,
    repo_root: Path,
    report_md: str,
    recommendations: list[Recommendation],
    annotations: Optional[dict[str, Annotation]] = None,
    now: Optional[datetime] = None,
    kind: str = "review",
    step_id: Optional[int] = None,
    plan_fingerprint: str = "",
    code_fingerprint: Optional[dict[str, str]] = None,
    detail_bundle_fingerprint: Optional[dict[str, str]] = None,
    outcome_evidence_valid: Optional[bool] = None,
    audit_shape_advisory: Optional[AuditShapeAdvisory] = None,
    audit_coverage: Optional[dict[str, object]] = None,
    is_pre_apply_checkpoint: bool = False,
    plan_mass: Optional[dict] = None,
    audit_stage: Optional[str] = None,
    audit_revision: Optional[dict[str, object]] = None,
    checkpoint_audit_revision: Optional[dict[str, object]] = None,
    qualified_result: object = _QUALIFIED_RESULT_UNSET,
    plan: Optional[Plan] = None,
    sampler_state: Optional[dict[str, object]] = None,
    _checkpoint_path: Optional[Path] = None,
) -> Path:
    """Persist a review run to disk and return the file path.

    Creates parent directories as needed. The filename is the UTC
    timestamp at save time (``now`` injectable for deterministic tests).
    Returns the absolute path written to.

    ``annotations`` defaults to empty — the walk loop populates it
    incrementally via :func:`update_annotation` after the initial save.

    ``kind`` is ``"review"`` (default), ``"completeness"`` (from
    ``plan-tool completeness-audit``), ``"detail-reconcile"`` (from
    ``plan-tool detail --reconcile``), or ``"run-reconcile"`` (from
    ``plan-tool run --reconcile``). Embedded into the filename when
    non-default and stored in the JSON payload. The walk loop treats
    all kinds identically; the field exists so listings, filenames,
    and reuse-lookups can distinguish producers.

    ``plan_fingerprint`` / ``code_fingerprint`` capture plan and code
    state for reuse-staleness checks. ``code_fingerprint`` is opaque —
    stored verbatim. Passing ``None`` (the default) records "never
    computed" (``code_fingerprint_present == False``); passing a dict,
    even ``{}``, records a computed capture (``present == True``), so a
    legitimately empty watched-code surface stays distinguishable from
    an unset one.

    ``step_ids`` / ``step_ids_present`` (BACKLOG #166) record every step id
    found in the plan. Unlike the fingerprints above, a caller doesn't have
    to supply this — omitting ``plan`` (the default) makes this function
    parse ``plan_path`` itself, so every kind carries the signal uniformly
    with no call-site changes. A caller that already has an in-hand,
    already-parsed :class:`~plan_tool.schema.Plan` (e.g. the one it used to
    compute its own ``plan_fingerprint``) should pass it as ``plan`` instead
    — this both skips a redundant re-parse and keeps ``step_ids`` describing
    the exact same read as the caller's other fingerprints, rather than a
    later, independent one. Either way, a parse failure records "never
    captured" (``step_ids_present == False``) rather than raising; an
    otherwise-successful save must never fail because this read did.

    ``audit_coverage`` is optional conceptual-audit provenance for a
    completeness sidecar. When supplied it must match one of the producer's
    observed states and is rewritten to the canonical saved object. Omitting
    it preserves the legacy-unknown distinction.

    ``qualified_result`` records the immutable final decision for a
    completeness sidecar. Its presence, including a checkpoint's explicit
    ``None``, writes schema version 4 so older readers reject the payload.
    ``checkpoint_audit_revision`` is allowed only alongside that explicit
    checkpoint-null result; it preserves recovery provenance without
    representing a qualified final decision.

    ``plan_mass`` is #238's optional structural-mass snapshot
    (:func:`plan_tool.completeness_report.plan_mass_to_json`), stored
    opaquely and omitted entirely when ``None`` (the default) so a caller
    that doesn't compute it writes byte-identically to before.

    ``audit_stage`` is the bare/detail bar for a completeness sidecar
    (``"bare"`` or ``"detail"``). Invalid values raise on completeness
    saves; non-completeness kinds ignore the argument and omit the key.

    ``sampler_state`` is reserved for :func:`save_sampler_checkpoint`; a
    sampler artifact always writes to its stable path rather than a
    timestamped report path.
    """
    if audit_stage is not None and kind == "completeness":
        if normalize_audit_stage(audit_stage) is None:
            raise ValueError(
                f"audit_stage must be one of {sorted(_VALID_AUDIT_STAGES)!r}, "
                f"got {audit_stage!r}"
            )
    normalized_audit_coverage = None
    if audit_coverage is not None:
        normalized_audit_coverage = normalize_audit_coverage(audit_coverage)
        if normalized_audit_coverage is None:
            raise ValueError("audit_coverage is not a valid audit producer state")
    normalized_audit_revision = None
    if audit_revision is not None:
        normalized_audit_revision = normalize_audit_revision(audit_revision)
        if normalized_audit_revision is None:
            raise ValueError("audit_revision is not a valid captured revision")
        if kind != "completeness":
            raise ValueError("audit_revision is only valid for a completeness sidecar")
    normalized_checkpoint_audit_revision = None
    if checkpoint_audit_revision is not None:
        normalized_checkpoint_audit_revision = normalize_audit_revision(
            checkpoint_audit_revision
        )
        if normalized_checkpoint_audit_revision is None:
            raise ValueError(
                "checkpoint_audit_revision is not a valid captured revision"
            )
    qualified_result_supplied = qualified_result is not _QUALIFIED_RESULT_UNSET
    normalized_qualified_result = None
    if qualified_result_supplied:
        if kind != "completeness":
            raise ValueError(
                "qualified_result is only valid for a completeness sidecar"
            )
        if normalized_audit_revision is not None:
            raise ValueError(
                "audit_revision must be nested in qualified_result for new "
                "completeness sidecars"
            )
        if hasattr(qualified_result, "as_dict"):
            qualified_result = qualified_result.as_dict()
        if qualified_result is not None:
            normalized_qualified_result = normalize_qualified_result(qualified_result)
            if normalized_qualified_result is None:
                raise ValueError("qualified_result is not a valid completeness result")
        elif not is_pre_apply_checkpoint:
            raise ValueError(
                "an ordinary final completeness sidecar requires qualified_result"
            )
    normalized_sampler_state = None
    if sampler_state is not None:
        normalized_sampler_state = normalize_sampler_state(sampler_state)
        if normalized_sampler_state is None:
            raise ValueError("sampler_state is not a valid sampler lifecycle mapping")
        if not (
            _checkpoint_path is not None
            and kind == "completeness"
            and is_pre_apply_checkpoint
            and qualified_result_supplied
            and normalized_qualified_result is None
        ):
            raise ValueError(
                "sampler_state requires a stable pre-apply completeness checkpoint "
                "with qualified_result null"
            )
    elif _checkpoint_path is not None:
        raise ValueError("a stable sampler checkpoint requires sampler_state")
    if normalized_checkpoint_audit_revision is not None and not (
        kind == "completeness"
        and is_pre_apply_checkpoint
        and qualified_result_supplied
        and normalized_qualified_result is None
    ):
        raise ValueError(
            "checkpoint_audit_revision requires a pre-apply completeness "
            "checkpoint with qualified_result null"
        )
    if is_pre_apply_checkpoint and kind != "completeness":
        raise ValueError(
            "is_pre_apply_checkpoint is only valid for a completeness sidecar"
        )
    abs_plan_path = _abs_plan_path(repo_root, plan_path)
    if (
        _checkpoint_path is not None
        and _checkpoint_path != sampler_checkpoint_path(abs_plan_path)
    ):
        raise ValueError("sampler_state must use the stable sampler checkpoint path")
    target_dir = plan_reports_dir(abs_plan_path)
    target_dir.mkdir(parents=True, exist_ok=True)
    path = _checkpoint_path if _checkpoint_path is not None else target_dir / _timestamp_filename(
        now, kind=kind
    )
    computed_step_ids = (
        tuple(sorted(step.id for step in plan.steps))
        if plan is not None
        else _current_step_ids(abs_plan_path)
    )
    if (
        qualified_result_supplied
        or normalized_audit_revision is not None
        or normalized_checkpoint_audit_revision is not None
    ):
        version = _AUDIT_REVISION_SCHEMA_VERSION
    elif is_pre_apply_checkpoint:
        version = _ROLE_AWARE_SCHEMA_VERSION
    elif audit_shape_advisory is not None:
        version = _ADVISORY_SCHEMA_VERSION
    else:
        version = SCHEMA_VERSION
    payload = {
        "version": version,
        "plan_slug": plan_slug,
        "plan_path": plan_path,
        "created_at": _utc_now_iso() if now is None else now.strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "kind": kind,
        "step_id": step_id,
        "plan_fingerprint": plan_fingerprint,
        "code_fingerprint": code_fingerprint or {},
        "code_fingerprint_present": code_fingerprint is not None,
        "detail_bundle_fingerprint": detail_bundle_fingerprint or {},
        "detail_bundle_fingerprint_present": detail_bundle_fingerprint is not None,
        "step_ids": list(computed_step_ids) if computed_step_ids is not None else [],
        "step_ids_present": computed_step_ids is not None,
        "outcome_evidence_valid": outcome_evidence_valid,
        "report_md": report_md,
        "recommendations": [asdict(r) for r in recommendations],
        "annotations": {
            rec_id: asdict(ann) for rec_id, ann in (annotations or {}).items()
        },
    }
    if audit_shape_advisory is not None:
        payload["audit_shape_advisory"] = asdict(audit_shape_advisory)
    if normalized_audit_coverage is not None:
        payload["audit_coverage"] = normalized_audit_coverage
    if normalized_audit_revision is not None:
        payload["audit_revision"] = normalized_audit_revision
    if normalized_checkpoint_audit_revision is not None:
        payload["checkpoint_audit_revision"] = normalized_checkpoint_audit_revision
    if qualified_result_supplied:
        payload["qualified_result"] = normalized_qualified_result
    if normalized_sampler_state is not None:
        payload["sampler_state"] = normalized_sampler_state
    if version == _AUDIT_REVISION_SCHEMA_VERSION:
        payload["is_pre_apply_checkpoint"] = is_pre_apply_checkpoint
    elif is_pre_apply_checkpoint:
        payload["is_pre_apply_checkpoint"] = True
    if plan_mass is not None:
        payload["plan_mass"] = plan_mass
    normalized_audit_stage = normalize_audit_stage(audit_stage)
    if kind == "completeness" and normalized_audit_stage is not None:
        payload["audit_stage"] = normalized_audit_stage
    durable_write_text(path, json.dumps(payload, indent=2) + "\n")
    return path


def save_sampler_checkpoint(
    *,
    plan_slug: str,
    plan_path: str,
    repo_root: Path,
    report_md: str,
    recommendations: list[Recommendation],
    sampler_state: dict[str, object],
    annotations: Optional[dict[str, Annotation]] = None,
    now: Optional[datetime] = None,
    plan_fingerprint: str = "",
    code_fingerprint: Optional[dict[str, str]] = None,
    detail_bundle_fingerprint: Optional[dict[str, str]] = None,
    audit_shape_advisory: Optional[AuditShapeAdvisory] = None,
    audit_coverage: Optional[dict[str, object]] = None,
    plan_mass: Optional[dict] = None,
    audit_stage: Optional[str] = None,
    checkpoint_audit_revision: Optional[dict[str, object]] = None,
    plan: Optional[Plan] = None,
) -> Path:
    """Durably replace the plan's stable non-final sampler checkpoint."""
    abs_plan_path = _abs_plan_path(repo_root, plan_path)
    return save_review(
        plan_slug=plan_slug,
        plan_path=plan_path,
        repo_root=repo_root,
        report_md=report_md,
        recommendations=recommendations,
        annotations=annotations,
        now=now,
        kind="completeness",
        plan_fingerprint=plan_fingerprint,
        code_fingerprint=code_fingerprint,
        detail_bundle_fingerprint=detail_bundle_fingerprint,
        audit_shape_advisory=audit_shape_advisory,
        audit_coverage=audit_coverage,
        is_pre_apply_checkpoint=True,
        plan_mass=plan_mass,
        audit_stage=audit_stage,
        checkpoint_audit_revision=checkpoint_audit_revision,
        qualified_result=None,
        plan=plan,
        sampler_state=sampler_state,
        _checkpoint_path=sampler_checkpoint_path(abs_plan_path),
    )


class ReviewLoadError(Exception):
    """Raised when a saved review file is malformed or missing required fields."""


def _int_tuple_or_none(value: object) -> Optional[tuple[int, ...]]:
    """Validate a JSON list of ints, or ``None`` for anything malformed.

    Shared by :func:`_load_audit_shape_advisory`'s ``arm_step_ids`` and
    :func:`load_review`'s ``step_ids`` (BACKLOG #166) — the same int-list
    shape, validated once.
    """
    if not isinstance(value, list) or any(
        isinstance(item, bool) or not isinstance(item, int) for item in value
    ):
        return None
    return tuple(value)


def _normalize_legacy_anchor(rec: Recommendation) -> Recommendation:
    """Recover an anchor from pre-wrapper-fix conceptual review titles.

    Old sidecars stored the leading ``[anchor]`` in ``title`` and left
    ``anchor`` unset. Recover it on read for region matching, while preserving
    the historical id so annotations and telemetry joins remain valid.
    """
    if rec.anchor or rec.source not in {"plan-correctness", "plan-completeness"}:
        return rec
    from plan_tool.review import _split_audit_key

    anchor, title = _split_audit_key(rec.title)
    return replace(rec, anchor=anchor, title=title) if anchor else rec


def normalize_restated_property_axis(rec: Recommendation) -> Recommendation:
    """Drop ``restated_property`` from any non-``plan-correctness`` finding.

    The parser only ever sets it there, but a directly edited or
    other-producer-authored sidecar isn't bound by that -- every render
    site trusts DATA_CONTRACT.md's "None for every other finding" contract
    with no per-call check of its own, so it is enforced once, here.
    """
    if rec.restated_property is None or rec.source == "plan-correctness":
        return rec
    return replace(rec, restated_property=None)


def _load_audit_shape_advisory(data: object) -> Optional[AuditShapeAdvisory]:
    """Load an optional advisory without letting it block normal reviews."""
    if not isinstance(data, dict):
        return None
    required = {
        "shape_id",
        "source_plan_fingerprint",
        "arm_step_ids",
        "material_finding_ids",
        "arm_finding_ids",
        "material_finding_evidence",
        "material_finding_count",
        "arm_finding_count",
        "committed_step_count",
    }
    if set(data) != required:
        return None

    def string_tuple(value: object) -> tuple[str, ...] | None:
        if not isinstance(value, list) or any(
            not isinstance(item, str) or not item for item in value
        ):
            return None
        return tuple(value)

    arm_step_ids = _int_tuple_or_none(data["arm_step_ids"])
    material_ids = string_tuple(data["material_finding_ids"])
    arm_ids = string_tuple(data["arm_finding_ids"])
    raw_evidence = data["material_finding_evidence"]
    if (
        not isinstance(data["shape_id"], str)
        or not isinstance(data["source_plan_fingerprint"], str)
        or arm_step_ids is None
        or material_ids is None
        or arm_ids is None
        or not isinstance(raw_evidence, list)
        or any(
            isinstance(data[name], bool) or not isinstance(data[name], int)
            or data[name] < 0
            for name in (
                "material_finding_count",
                "arm_finding_count",
                "committed_step_count",
            )
        )
    ):
        return None
    evidence: list[AuditShapeFindingEvidence] = []
    for item in raw_evidence:
        if (
            not isinstance(item, dict)
            or set(item) != {"finding_id", "anchor", "source"}
            or not isinstance(item.get("finding_id"), str)
            or not item["finding_id"]
            or not isinstance(item.get("anchor"), (str, type(None)))
            or not isinstance(item.get("source"), str)
        ):
            return None
        evidence.append(AuditShapeFindingEvidence(**item))
    if (
        len(set(material_ids)) != len(material_ids)
        or len(set(arm_ids)) != len(arm_ids)
        or not set(arm_ids).issubset(material_ids)
        or tuple(item.finding_id for item in evidence) != material_ids
        or data["material_finding_count"] != len(material_ids)
        or data["arm_finding_count"] != len(arm_ids)
    ):
        return None
    advisory = AuditShapeAdvisory(
        shape_id=data["shape_id"],
        source_plan_fingerprint=data["source_plan_fingerprint"],
        arm_step_ids=arm_step_ids,
        material_finding_ids=material_ids,
        arm_finding_ids=arm_ids,
        material_finding_evidence=tuple(evidence),
        material_finding_count=data["material_finding_count"],
        arm_finding_count=data["arm_finding_count"],
        committed_step_count=data["committed_step_count"],
    )
    return advisory if is_well_formed_audit_shape_advisory(advisory) else None


def _required_string(data: dict[str, object], field: str, path: Path) -> str:
    """Read one required persisted string field."""
    value = data.get(field)
    if not isinstance(value, str):
        raise ReviewLoadError(f"{path}: {field} must be a string")
    return value


def _string_mapping_or_error(
    value: object, field: str, path: Path
) -> dict[str, str]:
    """Read an opaque string-to-string fingerprint mapping."""
    if not isinstance(value, dict) or any(
        not isinstance(key, str) or not isinstance(item, str)
        for key, item in value.items()
    ):
        raise ReviewLoadError(f"{path}: {field} must be a string mapping")
    return value


def _optional_step_id_or_error(value: object, field: str, path: Path) -> Optional[int]:
    """Validate one optional persisted step id."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ReviewLoadError(f"{path}: {field} must be an integer or null")
    return value


def _load_recommendations(data: object, path: Path) -> list[Recommendation]:
    """Load recommendation shapes history and diagnosis can safely consume."""
    if not isinstance(data, list):
        raise ReviewLoadError(f"{path}: recommendations must be a list")
    recommendations: list[Recommendation] = []
    for raw in data:
        if not isinstance(raw, dict):
            raise ReviewLoadError(f"{path}: malformed recommendation")
        for field_name in ("id", "source", "title", "body"):
            if not isinstance(raw.get(field_name), str):
                raise ReviewLoadError(
                    f"{path}: recommendation {field_name} must be a string"
                )
        severity = raw.get("severity")
        if (
            not isinstance(severity, str)
            or severity not in RECOMMENDATION_SEVERITIES
        ):
            raise ReviewLoadError(
                f"{path}: recommendation severity must be one of "
                f"{sorted(RECOMMENDATION_SEVERITIES)!r}"
            )
        _optional_step_id_or_error(raw.get("step_id"), "recommendation step_id", path)
        # suggested_action/anchor/restated_property type-checked inside
        # recommendation_from_persisted_mapping (shared with purity_cache.py).
        try:
            recommendation = recommendation_from_persisted_mapping(raw)
        except (TypeError, ValueError) as exc:
            raise ReviewLoadError(
                f"{path}: malformed recommendation: {exc}"
            ) from exc
        recommendation = normalize_restated_property_axis(
            _normalize_legacy_anchor(recommendation)
        )
        recommendations.append(recommendation)
    return recommendations


def _load_annotations(data: object, path: Path) -> dict[str, Annotation]:
    """Load annotation mappings without leaking dataclass parser errors."""
    if not isinstance(data, dict):
        raise ReviewLoadError(f"{path}: annotations must be an object")
    annotations: dict[str, Annotation] = {}
    for rec_id, raw in data.items():
        if not isinstance(rec_id, str) or not isinstance(raw, dict):
            raise ReviewLoadError(f"{path}: malformed annotations")
        normalized = raw
        # Backward-compat: status="done" was the historical name for what's
        # now "applied". Keep old saves readable without trusting bad shapes.
        if normalized.get("status") == "done":
            normalized = {**normalized, "status": "applied"}
        if not isinstance(normalized.get("status"), str):
            raise ReviewLoadError(f"{path}: annotation status must be a string")
        for field_name in ("note", "halt_reason"):
            if field_name in normalized and not isinstance(
                normalized[field_name], str
            ):
                raise ReviewLoadError(
                    f"{path}: annotation {field_name} must be a string"
                )
        try:
            annotations[rec_id] = Annotation(**normalized)
        except TypeError as exc:
            raise ReviewLoadError(f"{path}: malformed annotations: {exc}") from exc
    return annotations


def load_review(path: Path) -> SavedReview:
    """Parse a saved review JSON file into a :class:`SavedReview`.

    Raises :class:`ReviewLoadError` on malformed JSON, schema mismatch,
    or missing required fields. Forward-compatible with future schema
    versions only when they're a strict superset; older code should
    refuse to load newer files rather than silently dropping unknown
    keys.

    Optional role metadata never raises: a malformed, misplaced, or
    role/version-mismatched checkpoint marker or sampler state loads as the
    unknown role (see :func:`_normalize_checkpoint_role`) so the sidecar
    stays inspectable without being trusted as a final report.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReviewLoadError(f"could not read {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ReviewLoadError(f"{path}: top-level must be an object")
    version = data.get("version")
    if version not in _SUPPORTED_SCHEMA_VERSIONS:
        raise ReviewLoadError(
            f"{path}: schema version {version!r} not supported "
            f"(expected one of {list(_SUPPORTED_SCHEMA_VERSIONS)})"
        )
    plan_slug = _required_string(data, "plan_slug", path)
    plan_path = _required_string(data, "plan_path", path)
    created_at = _required_string(data, "created_at", path)
    report_md = _required_string(data, "report_md", path)
    kind = _required_string(data, "kind", path) if "kind" in data else "review"
    recs = _load_recommendations(data.get("recommendations"), path)
    annotations = _load_annotations(data.get("annotations", {}), path)
    step_id = _optional_step_id_or_error(data.get("step_id"), "step_id", path)
    plan_fingerprint = data.get("plan_fingerprint", "")
    if not isinstance(plan_fingerprint, str):
        raise ReviewLoadError(f"{path}: plan_fingerprint must be a string")
    code_fingerprint = _string_mapping_or_error(
        data.get("code_fingerprint", {}), "code_fingerprint", path
    )
    code_fingerprint_present = data.get("code_fingerprint_present", False)
    if not isinstance(code_fingerprint_present, bool):
        raise ReviewLoadError(f"{path}: code_fingerprint_present must be a boolean")
    detail_bundle_fingerprint = _string_mapping_or_error(
        data.get("detail_bundle_fingerprint", {}), "detail_bundle_fingerprint", path
    )
    detail_bundle_fingerprint_present = data.get(
        "detail_bundle_fingerprint_present", False
    )
    if not isinstance(detail_bundle_fingerprint_present, bool):
        raise ReviewLoadError(
            f"{path}: detail_bundle_fingerprint_present must be a boolean"
        )
    outcome_evidence_valid = data.get("outcome_evidence_valid")
    if outcome_evidence_valid is not None and not isinstance(outcome_evidence_valid, bool):
        raise ReviewLoadError(
            f"{path}: outcome_evidence_valid must be a boolean or null"
        )
    _loaded_step_ids = _int_tuple_or_none(data.get("step_ids"))
    _loaded_step_ids_present = (
        data.get("step_ids_present") is True and _loaded_step_ids is not None
    )
    _loaded_step_ids = _loaded_step_ids or ()
    raw_sampler_state = data.get("sampler_state", _SAMPLER_STATE_ABSENT)
    sampler_state = (
        normalize_sampler_state(raw_sampler_state)
        if raw_sampler_state is not _SAMPLER_STATE_ABSENT
        else None
    )
    checkpoint_role = _normalize_checkpoint_role(
        data.get("is_pre_apply_checkpoint", _MARKER_ABSENT),
        version=version,
        kind=kind,
        sampler_state=raw_sampler_state,
        qualified_result=data.get("qualified_result", _QUALIFIED_RESULT_UNSET),
    )
    try:
        qualified_result = (
            normalize_qualified_result(data.get("qualified_result"))
            if version == _AUDIT_REVISION_SCHEMA_VERSION
            and "qualified_result" in data
            and data.get("qualified_result") is not None
            else None
        )
        checkpoint_audit_revision = (
            normalize_audit_revision(data.get("checkpoint_audit_revision"))
            if (
                version == _AUDIT_REVISION_SCHEMA_VERSION
                and kind == "completeness"
                and checkpoint_role is True
                and "qualified_result" in data
                and data.get("qualified_result") is None
            )
            else None
        )
        audit_shape_advisory = (
            _load_audit_shape_advisory(data.get("audit_shape_advisory"))
            if version
            in {
                _ADVISORY_SCHEMA_VERSION,
                _ROLE_AWARE_SCHEMA_VERSION,
                _AUDIT_REVISION_SCHEMA_VERSION,
            }
            else None
        )
        audit_coverage = normalize_audit_coverage(data.get("audit_coverage"))
        plan_mass = (
            data["plan_mass"] if isinstance(data.get("plan_mass"), dict) else None
        )
        audit_stage = normalize_audit_stage(data.get("audit_stage"))
        legacy_audit_revision = (
            normalize_audit_revision(data.get("audit_revision"))
            if qualified_result is None and version == _AUDIT_REVISION_SCHEMA_VERSION
            else None
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ReviewLoadError(f"{path}: malformed saved review: {exc}") from exc
    saved = SavedReview(
        plan_slug=plan_slug,
        plan_path=plan_path,
        created_at=created_at,
        report_md=report_md,
        recommendations=recs,
        annotations=annotations,
        schema_version=version,
        path=path,
        kind=kind,
        step_id=step_id,
        plan_fingerprint=plan_fingerprint,
        code_fingerprint=code_fingerprint,
        code_fingerprint_present=code_fingerprint_present,
        detail_bundle_fingerprint=detail_bundle_fingerprint,
        detail_bundle_fingerprint_present=detail_bundle_fingerprint_present,
        step_ids=_loaded_step_ids,
        step_ids_present=_loaded_step_ids_present,
        outcome_evidence_valid=outcome_evidence_valid,
        audit_shape_advisory=audit_shape_advisory,
        audit_coverage=audit_coverage,
        is_pre_apply_checkpoint=checkpoint_role,
        sampler_state=sampler_state,
        plan_mass=plan_mass,
        audit_stage=audit_stage,
        checkpoint_audit_revision=checkpoint_audit_revision,
    )
    saved._qualified_result = qualified_result
    saved._legacy_audit_revision = legacy_audit_revision
    return saved


@dataclass(frozen=True)
class SamplerCheckpointLoad:
    """The stable sampler artifact's availability without a false resume."""

    status: str  # "absent" | "valid" | "unreadable" | "not-sampler"
    review: Optional[SavedReview] = None


def load_sampler_checkpoint(plan_path: Path) -> SamplerCheckpointLoad:
    """Load the stable sampler artifact without treating failure as resumable."""
    path = sampler_checkpoint_path(plan_path)
    if not path.exists():
        return SamplerCheckpointLoad("absent")
    try:
        saved = load_review(path)
    except ReviewLoadError:
        return SamplerCheckpointLoad("unreadable")
    if (
        saved.kind != "completeness"
        or saved.is_pre_apply_checkpoint is not True
        or saved.sampler_state is None
    ):
        return SamplerCheckpointLoad("not-sampler")
    return SamplerCheckpointLoad("valid", saved)


def list_report_artifacts(plan_path: Path) -> tuple[Path, ...]:
    """Capture one immutable reports-directory snapshot for a plan."""
    target_dir = plan_reports_dir(plan_path)
    if not target_dir.is_dir():
        return ()
    return tuple(path for path in target_dir.iterdir() if path.is_file())


def list_saved_reviews(
    plan_slug: str,
    repo_root: Path,
    *,
    plan_path: Optional[Path] = None,
    artifact_paths: Optional[Iterable[Path]] = None,
) -> list[Path]:
    """List saved review paths for ``plan_slug`` newest-first.

    Scans the canonical reports directory (:func:`plan_reports_dir`) when
    ``plan_path`` is given, unless the caller supplies one pre-captured
    ``artifact_paths`` snapshot. Returns ``[]`` when it doesn't exist yet.
    Filenames sort lexically — the timestamp format we write is chronologically
    sortable, so reverse-sort is newest-first.

    Includes the in-progress sampler checkpoint when present: its fixed,
    non-timestamped filename sorts lexically ahead of every real timestamped
    save, so it is candidate 0 whenever it exists, not the newest review. A
    caller that wants "the newest real saved review" must filter it out
    itself (:func:`resolve_saved_review`'s id-less path does this).

    (``repo_root`` is retained for call-site signature stability; the
    canonical reports directory is derived from ``plan_path``.)
    """
    if plan_path is None:
        return []
    if artifact_paths is None:
        artifact_paths = list_report_artifacts(plan_path)
    paths = [
        path for path in artifact_paths if path.suffix == ".json"
    ]
    return sorted(paths, key=lambda p: p.name, reverse=True)


def update_annotation(
    saved_path: Path,
    rec_id: str,
    annotation: Annotation,
) -> None:
    """Rewrite the saved file with ``rec_id`` mapped to ``annotation``.

    Loads → mutates the annotations dict → writes back. The full-rewrite
    cost is fine for the walk feature's cadence (one user keystroke per
    write). Raises :class:`ReviewLoadError` if the file is malformed,
    same as :func:`load_review`; the caller decides whether to recover.

    Side effect by design: the write-back persists the load-normalized
    fields, so a legacy save is migrated in place the first time it is
    walked — ``status="done" → "applied"`` (see :func:`load_review`).
    This is an equivalence rewrite (same walk behavior), so it's a free
    forward-migration, not a data change; it lands on the user's file as
    a side effect of annotating.

    The rewrite preserves the saved role and its schema version: a
    confirmed checkpoint stays a version-4 checkpoint, and an unknown role
    is rewritten as an unknown marker rather than collapsing into an
    ordinary final artifact.
    """
    saved = load_review(saved_path)
    saved.annotations[rec_id] = annotation
    payload = {
        "version": saved.schema_version,
        "plan_slug": saved.plan_slug,
        "plan_path": saved.plan_path,
        "created_at": saved.created_at,
        "kind": saved.kind,
        "step_id": saved.step_id,
        "plan_fingerprint": saved.plan_fingerprint,
        "code_fingerprint": saved.code_fingerprint,
        "code_fingerprint_present": saved.code_fingerprint_present,
        "detail_bundle_fingerprint": saved.detail_bundle_fingerprint,
        "detail_bundle_fingerprint_present": saved.detail_bundle_fingerprint_present,
        "step_ids": list(saved.step_ids),
        "step_ids_present": saved.step_ids_present,
        "outcome_evidence_valid": saved.outcome_evidence_valid,
        "report_md": saved.report_md,
        "recommendations": [asdict(r) for r in saved.recommendations],
        "annotations": {
            k: asdict(v) for k, v in saved.annotations.items()
        },
    }
    if saved.audit_shape_advisory is not None:
        payload["audit_shape_advisory"] = asdict(saved.audit_shape_advisory)
    if saved.audit_coverage is not None:
        payload["audit_coverage"] = saved.audit_coverage
    if saved.plan_mass is not None:
        payload["plan_mass"] = saved.plan_mass
    if saved.audit_stage is not None:
        payload["audit_stage"] = saved.audit_stage
    if saved.qualified_result is not None:
        payload["qualified_result"] = saved.qualified_result
    elif saved.is_pre_apply_checkpoint is True:
        payload["qualified_result"] = None
        if saved.checkpoint_audit_revision is not None:
            payload["checkpoint_audit_revision"] = saved.checkpoint_audit_revision
    elif saved.audit_revision is not None:
        # Preserve an older v4 audit-revision-only sidecar without inventing a
        # qualified result during an annotation rewrite.
        payload["audit_revision"] = saved.audit_revision
    if saved.sampler_state is not None:
        payload["sampler_state"] = saved.sampler_state
    if saved.is_pre_apply_checkpoint is False:
        # Version-3/4 finals need their explicit marker: either schema reads a
        # markerless payload as an unknown role. Legacy finals remain markerless.
        if saved.schema_version in {
            _ROLE_AWARE_SCHEMA_VERSION,
            _AUDIT_REVISION_SCHEMA_VERSION,
        }:
            payload["is_pre_apply_checkpoint"] = False
    else:
        payload["is_pre_apply_checkpoint"] = (
            True
            if saved.is_pre_apply_checkpoint
            else _UNKNOWN_CHECKPOINT_ROLE_MARKER
        )
    durable_write_text(saved_path, json.dumps(payload, indent=2) + "\n")


def resolve_saved_review(
    plan_slug: str,
    repo_root: Path,
    *,
    review_id: Optional[str] = None,
    plan_path: Optional[Path] = None,
) -> Path:
    """Pick a saved review path for ``plan_slug``.

    With ``review_id``, resolves that specific run in the canonical reports
    directory (:func:`plan_reports_dir`) — the only path that can reach a
    pinned sampler checkpoint by id. Without an id, returns the newest
    *saved review*, excluding the in-progress sampler checkpoint (see
    DATA_CONTRACT.md's "Sampler checkpoints"). Raises
    :class:`FileNotFoundError` when nothing matches — the CLI converts that
    to a user-facing error.

    (``repo_root`` is retained for call-site signature stability; the
    canonical reports directory is derived from ``plan_path``.)
    """
    if review_id is not None:
        filename = review_id if review_id.endswith(".json") else f"{review_id}.json"
        if plan_path is not None:
            target = plan_reports_dir(plan_path) / filename
            if target.is_file():
                return target
        raise FileNotFoundError(
            f"no saved review for plan {plan_slug!r} with id {review_id!r}"
        )
    candidates = [
        path
        for path in list_saved_reviews(plan_slug, repo_root, plan_path=plan_path)
        if path.name != SAMPLER_CHECKPOINT_FILENAME
    ]
    if not candidates:
        searched = (
            plan_reports_dir(plan_path) if plan_path is not None else "(no plan path)"
        )
        raise FileNotFoundError(
            f"no saved reviews for plan {plan_slug!r} under {searched}"
        )
    return candidates[0]
