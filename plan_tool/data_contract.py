"""Code-owned registry for persisted application data contracts.

The registry is intentionally explicit: dataclass fields are discovered from
the runtime classes, while the set of classes, aliases, sidecar JSON objects,
durable config files, and authored-artifact format-version constants is named
here for documentation drift checks.
"""

from __future__ import annotations

import ast
import dataclasses as dc
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

from plan_tool import audit_shapes
from plan_tool import completeness_report
from plan_tool import detail_artifacts
from plan_tool import grounding
from plan_tool import concept_tree
from plan_tool import locator
from plan_tool import project_config
from plan_tool import project_profile
from plan_tool import purity_cache
from plan_tool import review
from plan_tool import review_persistence
from plan_tool import run_log
from plan_tool import schema
from plan_tool import telemetry


@dataclass(frozen=True)
class IntentionalExclusion:
    owner: str
    field_or_key: str
    reason: str
    rationale: str


@dataclass(frozen=True)
class PersistedDataclassContract:
    owner: str
    cls: type
    section_title: str
    source_symbol: str
    persisted: bool = True
    json_key_aliases: dict[str, str] = field(default_factory=dict)
    in_memory_only: frozenset[str] = frozenset()
    conditionally_persisted: frozenset[str] = frozenset()
    schema_constants: tuple[str, ...] = ()
    open_bag_fields: frozenset[str] = frozenset()
    intentional_exclusions: tuple[IntentionalExclusion, ...] = ()

    @property
    def field_names(self) -> tuple[str, ...]:
        return tuple(f.name for f in dc.fields(self.cls))

    @property
    def persisted_field_names(self) -> tuple[str, ...]:
        excluded = set(self.in_memory_only)
        return tuple(name for name in self.field_names if name not in excluded)

    @property
    def persisted_json_keys(self) -> tuple[str, ...]:
        return tuple(
            self.json_key_aliases.get(name, name)
            for name in self.persisted_field_names
        )

    @property
    def required_persisted_json_keys(self) -> tuple[str, ...]:
        """Keys present in every serialized instance of this contract."""
        return tuple(
            self.json_key_aliases.get(name, name)
            for name in self.persisted_field_names
            if name not in self.conditionally_persisted
        )

    @property
    def accepted_documented_fields(self) -> frozenset[str]:
        return frozenset(self.field_names) | frozenset(self.json_key_aliases.values())


@dataclass(frozen=True)
class JsonObjectContract:
    owner: str
    section_title: str
    source_symbol: str
    path_labels: tuple[str, ...] = ()
    keys: tuple[str, ...] = ()
    required_phrases: tuple[str, ...] = ()
    schema_constants: tuple[str, ...] = ()
    intentional_exclusions: tuple[IntentionalExclusion, ...] = ()


@dataclass(frozen=True)
class ArtifactFormatVersionContract:
    """Names an authored artifact class's format-version constant and its
    live current/supported values — never its dataclass fields or JSON keys.

    Deliberately smaller than :class:`PersistedDataclassContract` and
    :class:`JsonObjectContract`: a plan/detail format version has no
    persisted-dataclass or JSON-object shape to discover, only a name and a
    value pair per class.
    """

    owner: str
    section_title: str
    source_symbol: str
    version_constant: str
    supported_versions_constant: str
    current_version: int
    supported_versions: frozenset[int]


@dataclass(frozen=True)
class DriftRecord:
    source_type: str
    owner: str
    field_or_key: str
    target_section: str
    operation: str
    registry_fingerprint: str
    contract_fingerprint: str
    candidate: dict[str, Any]


@dataclass(frozen=True)
class InputContractReferenceIssue:
    location: str
    reason: str
    owner: str | None = None
    field_or_key: str | None = None
    code_anchor: str | None = None
    step_id: int | None = None
    path: str | None = None


def persisted_dataclass_contracts() -> tuple[PersistedDataclassContract, ...]:
    return (
        PersistedDataclassContract(
            owner="ConceptTree",
            cls=concept_tree.ConceptTree,
            section_title="ConceptTree",
            source_symbol="plan_tool/concept_tree.py:ConceptTree",
            schema_constants=("CONCEPTS_SCHEMA_VERSION",),
        ),
        PersistedDataclassContract(
            owner="ConceptNode",
            cls=concept_tree.ConceptNode,
            section_title="ConceptNode",
            source_symbol="plan_tool/concept_tree.py:ConceptNode",
        ),
        PersistedDataclassContract(
            owner="SavedReview",
            cls=review_persistence.SavedReview,
            section_title="SavedReview",
            source_symbol="plan_tool/review_persistence.py:SavedReview",
            json_key_aliases={"schema_version": "version"},
            in_memory_only=frozenset({"path"}),
            conditionally_persisted=frozenset(
                {
                    "audit_shape_advisory",
                    "audit_coverage",
                    "is_pre_apply_checkpoint",
                    "sampler_state",
                    "plan_mass",
                    "audit_stage",
                    "checkpoint_audit_revision",
                }
            ),
            schema_constants=("SCHEMA_VERSION",),
        ),
        PersistedDataclassContract(
            owner="PlanMass",
            cls=completeness_report.PlanMass,
            section_title="PlanMass",
            source_symbol="plan_tool/completeness_report.py:PlanMass",
        ),
        PersistedDataclassContract(
            owner="SoftEdge",
            cls=completeness_report.SoftEdge,
            section_title="SoftEdge",
            source_symbol="plan_tool/completeness_report.py:SoftEdge",
        ),
        PersistedDataclassContract(
            owner="AuditShapeAdvisory",
            cls=audit_shapes.AuditShapeAdvisory,
            section_title="AuditShapeAdvisory",
            source_symbol="plan_tool/audit_shapes.py:AuditShapeAdvisory",
        ),
        PersistedDataclassContract(
            owner="Recommendation",
            cls=review.Recommendation,
            section_title="Recommendation",
            source_symbol="plan_tool/review.py:Recommendation",
        ),
        PersistedDataclassContract(
            owner="Redirect",
            cls=review.Redirect,
            section_title="Redirect",
            source_symbol="plan_tool/review.py:Redirect",
        ),
        PersistedDataclassContract(
            owner="Annotation",
            cls=review_persistence.Annotation,
            section_title="Annotation",
            source_symbol="plan_tool/review_persistence.py:Annotation",
        ),
        PersistedDataclassContract(
            owner="DecisionEvent",
            cls=telemetry.DecisionEvent,
            section_title="DecisionEvent",
            source_symbol="plan_tool/telemetry.py:DecisionEvent",
            schema_constants=("TELEMETRY_SCHEMA_VERSION",),
            open_bag_fields=frozenset({"context"}),
        ),
        PersistedDataclassContract(
            owner="AttemptFailed",
            cls=run_log.AttemptFailed,
            section_title="AttemptFailed",
            source_symbol="plan_tool/run_log.py:AttemptFailed",
        ),
        PersistedDataclassContract(
            owner="ModelFailureReceipt",
            cls=run_log.ModelFailureReceipt,
            section_title="ModelFailureReceipt",
            source_symbol="plan_tool/run_log.py:ModelFailureReceipt",
            conditionally_persisted=frozenset({"sidecar_path"}),
        ),
        PersistedDataclassContract(
            owner="GateViolations",
            cls=run_log.GateViolations,
            section_title="GateViolations",
            source_symbol="plan_tool/run_log.py:GateViolations",
        ),
        PersistedDataclassContract(
            owner="BackendSpawn",
            cls=run_log.BackendSpawn,
            section_title="BackendSpawn",
            source_symbol="plan_tool/run_log.py:BackendSpawn",
        ),
        PersistedDataclassContract(
            owner="BackendTermination",
            cls=run_log.BackendTermination,
            section_title="BackendTermination",
            source_symbol="plan_tool/run_log.py:BackendTermination",
        ),
        PersistedDataclassContract(
            owner="RunInterrupted",
            cls=run_log.RunInterrupted,
            section_title="RunInterrupted",
            source_symbol="plan_tool/run_log.py:RunInterrupted",
        ),
        PersistedDataclassContract(
            owner="BackendRecoveryWait",
            cls=run_log.BackendRecoveryWait,
            section_title="BackendRecoveryWait",
            source_symbol="plan_tool/run_log.py:BackendRecoveryWait",
        ),
        PersistedDataclassContract(
            owner="RoadmapPreflightFailed",
            cls=run_log.RoadmapPreflightFailed,
            section_title="RoadmapPreflightFailed",
            source_symbol="plan_tool/run_log.py:RoadmapPreflightFailed",
        ),
        PersistedDataclassContract(
            owner="RoadmapStageWritten",
            cls=run_log.RoadmapStageWritten,
            section_title="RoadmapStageWritten",
            source_symbol="plan_tool/run_log.py:RoadmapStageWritten",
        ),
        PersistedDataclassContract(
            owner="RoadmapSeedApplyResult",
            cls=run_log.RoadmapSeedApplyResult,
            section_title="RoadmapSeedApplyResult",
            source_symbol="plan_tool/run_log.py:RoadmapSeedApplyResult",
        ),
        PersistedDataclassContract(
            owner="RoadmapStructuralRevisionPreflight",
            cls=run_log.RoadmapStructuralRevisionPreflight,
            section_title="RoadmapStructuralRevisionPreflight",
            source_symbol="plan_tool/run_log.py:RoadmapStructuralRevisionPreflight",
        ),
        PersistedDataclassContract(
            owner="RoadmapStructuralRevisionAttempt",
            cls=run_log.RoadmapStructuralRevisionAttempt,
            section_title="RoadmapStructuralRevisionAttempt",
            source_symbol="plan_tool/run_log.py:RoadmapStructuralRevisionAttempt",
        ),
        PersistedDataclassContract(
            owner="RoadmapEscalationPreflight",
            cls=run_log.RoadmapEscalationPreflight,
            section_title="RoadmapEscalationPreflight",
            source_symbol="plan_tool/run_log.py:RoadmapEscalationPreflight",
        ),
        PersistedDataclassContract(
            owner="RoadmapEscalationResult",
            cls=run_log.RoadmapEscalationResult,
            section_title="RoadmapEscalationResult",
            source_symbol="plan_tool/run_log.py:RoadmapEscalationResult",
        ),
        PersistedDataclassContract(
            owner="RoadmapImpactPreflight",
            cls=run_log.RoadmapImpactPreflight,
            section_title="RoadmapImpactPreflight",
            source_symbol="plan_tool/run_log.py:RoadmapImpactPreflight",
        ),
        PersistedDataclassContract(
            owner="RoadmapImpactResult",
            cls=run_log.RoadmapImpactResult,
            section_title="RoadmapImpactResult",
            source_symbol="plan_tool/run_log.py:RoadmapImpactResult",
        ),
        PersistedDataclassContract(
            owner="Grounding",
            cls=grounding.Grounding,
            section_title="Grounding",
            source_symbol="plan_tool/grounding.py:Grounding",
            schema_constants=("GROUNDING_SCHEMA_VERSION",),
        ),
        PersistedDataclassContract(
            owner="ProjectProfile",
            cls=project_profile.ProjectProfile,
            section_title="ProjectProfile",
            source_symbol="plan_tool/project_profile.py:ProjectProfile",
            schema_constants=("PROJECT_PROFILE_SCHEMA_VERSION",),
        ),
        PersistedDataclassContract(
            owner="PurityCacheEntry",
            cls=purity_cache.PurityCacheEntry,
            section_title="PurityCacheEntry",
            source_symbol="plan_tool/purity_cache.py:PurityCacheEntry",
            schema_constants=("PURITY_CACHE_SCHEMA_VERSION",),
        ),
    )


def json_object_contracts() -> tuple[JsonObjectContract, ...]:
    return (
        JsonObjectContract(
            owner="Plan manifest",
            section_title="Plan manifest",
            source_symbol="plan_tool/locator.py:load_manifest_plan_paths",
            path_labels=(str(locator.DEFAULT_MANIFEST_SUBPATH),),
            keys=("plans",),
            required_phrases=("repo-relative", "path strings"),
        ),
        JsonObjectContract(
            owner="Project configuration",
            section_title="Project configuration",
            source_symbol="plan_tool/project_config.py",
            path_labels=(
                str(project_config.PROJECT_CONFIG_SUBPATH),
                "~/.plan-tool/config.json",
            ),
            keys=(
                "branch_awareness",
                "enabled",
                "branch_prefixes",
                project_config.SMELL_CONFIG_BLOCK,
                project_config.VALIDATION_MACHINERY_PATHS_KEY,
                project_config.ROADMAP_FEEDBACK_CONFIG_BLOCK,
                project_config.STAGE_LIMITS_CONFIG_BLOCK,
                project_config.MAX_ACTIVE_FEEDBACK_ITEMS_KEY,
                project_config.MAX_RESPONSE_BYTES_KEY,
                project_config.MAX_PROSE_AMENDMENT_BYTES_KEY,
            ),
        ),
        JsonObjectContract(
            owner="Purity findings cache",
            section_title="Purity findings cache",
            source_symbol="plan_tool/purity_cache.py",
            path_labels=(".plan-tool/purity-cache/<slug>.json",),
            keys=("version", "plan_slug", "entries"),
        ),
    )


def artifact_format_version_contracts() -> tuple[ArtifactFormatVersionContract, ...]:
    """Version-only registry for the two authored-artifact format versions.

    Reads ``current_version``/``supported_versions`` directly off the live
    ``plan_tool.schema``/``plan_tool.detail_artifacts`` constants at call
    time, rather than copying their values as literals here, so a version
    bump with no matching ``DATA_CONTRACT.md`` update fails the drift-guard
    tests on its own.
    """
    return (
        ArtifactFormatVersionContract(
            owner="Plan format version",
            section_title="Plan format version",
            source_symbol="plan_tool/schema.py:PLAN_FORMAT_VERSION",
            version_constant="PLAN_FORMAT_VERSION",
            supported_versions_constant="SUPPORTED_PLAN_FORMAT_VERSIONS",
            current_version=schema.PLAN_FORMAT_VERSION,
            supported_versions=frozenset(schema.SUPPORTED_PLAN_FORMAT_VERSIONS),
        ),
        ArtifactFormatVersionContract(
            owner="Detail format version",
            section_title="Detail format version",
            source_symbol="plan_tool/detail_artifacts.py:DETAIL_FORMAT_VERSION",
            version_constant="DETAIL_FORMAT_VERSION",
            supported_versions_constant="SUPPORTED_DETAIL_FORMAT_VERSIONS",
            current_version=detail_artifacts.DETAIL_FORMAT_VERSION,
            supported_versions=frozenset(
                detail_artifacts.SUPPORTED_DETAIL_FORMAT_VERSIONS
            ),
        ),
    )


def intentional_exclusions() -> tuple[IntentionalExclusion, ...]:
    exclusions: list[IntentionalExclusion] = []
    for contract in persisted_dataclass_contracts():
        exclusions.extend(contract.intentional_exclusions)
    for contract in json_object_contracts():
        exclusions.extend(contract.intentional_exclusions)
    return tuple(exclusions)


def registered_open_bag_keys() -> dict[tuple[str, str], frozenset[str]]:
    return {
        ("DecisionEvent", "context"): frozenset(
            {
                "action",
                "after_steps",
                "backend",
                "before_steps",
                "budget_limited",
                "can_split",
                "candidate_fingerprint",
                "cap",
                "classified_as",
                "criteria",
                "criteria_count",
                "error_class",
                "early_stop_reason",
                "excerpt",
                "file_footprint",
                "findings",
                "fired_count",
                "had_split_hint",
                "merge",
                "mode",
                "markers",
                "passes",
                "plan_fingerprint",
                "predicate_counts",
                "proposed_change_type",
                "recommended_passes",
                "resolved_change_type",
                "phase",
                "split",
                "split_step_ids",
                "split_steps",
                "stage",
                "step_id",
                "steps",
            }
        )
    }


def registry_fingerprint() -> str:
    payload = {
        "dataclasses": [
            {
                "owner": c.owner,
                "fields": c.field_names,
                "persisted": c.persisted_field_names,
                "json_key_aliases": c.json_key_aliases,
                "in_memory_only": sorted(c.in_memory_only),
                "conditionally_persisted": sorted(c.conditionally_persisted),
                "schema_constants": c.schema_constants,
                "open_bag_fields": sorted(c.open_bag_fields),
            }
            for c in persisted_dataclass_contracts()
        ],
        "open_bag_keys": {
            f"{owner}.{field}": sorted(keys)
            for (owner, field), keys in registered_open_bag_keys().items()
        },
        "json_objects": [
            {
                "owner": c.owner,
                "paths": c.path_labels,
                "keys": c.keys,
                "required_phrases": c.required_phrases,
                "schema_constants": c.schema_constants,
            }
            for c in json_object_contracts()
        ],
        "intentional_exclusions": [dc.asdict(e) for e in intentional_exclusions()],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


_H2_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_BACKTICK_RE = re.compile(r"`([^`\n]+)`")
_CONTRACT_REF_RE = re.compile(
    r"^(?P<owner>[A-Z][A-Za-z0-9_]+)\."
    r"(?P<field>[A-Za-z_][A-Za-z0-9_]*)"
    r"(?:\.(?P<key>[A-Za-z_][A-Za-z0-9_]*))?$"
)
_CODE_ANCHOR_RE = re.compile(
    r"^(?P<path>(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.py)"
    r"(?::(?P<symbol>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?))?$"
)
# Mirrors create.py's _LOCAL_CODE_SKIP_DIRS (kept local rather than shared to
# avoid coupling this module to create.py for one constant).
_ANCHOR_SEARCH_SKIP_DIRS = frozenset(
    {
        ".git",
        ".plan-tool",
        ".tox",
        ".venv",
        "__pycache__",
        "build",
        "coverage",
        "dist",
        "node_modules",
        "target",
        "third_party",
        "vendor",
    }
)


def _input_section(text: str) -> str | None:
    headings = list(_H2_RE.finditer(text or ""))
    for i, match in enumerate(headings):
        title = match.group(1).strip().rstrip(":.").lower()
        if title != "input":
            continue
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        return text[match.end() : end]
    return None


def _contract_by_owner() -> dict[str, PersistedDataclassContract]:
    return {item.owner: item for item in persisted_dataclass_contracts()}


def _valid_contract_field(
    contract: PersistedDataclassContract, field_or_alias: str
) -> bool:
    return field_or_alias in contract.persisted_field_names or (
        field_or_alias in contract.json_key_aliases.values()
    )


def _valid_open_bag_key(owner: str, field_name: str, key: str | None) -> bool:
    if key is None:
        return False
    return key in registered_open_bag_keys().get((owner, field_name), frozenset())


def _module_level_symbol_exists(tree: ast.AST, symbol: str) -> bool:
    for node in getattr(tree, "body", []):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == symbol:
                return True
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == symbol:
                    return True
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == symbol:
                return True
    return False


def _normalize_planned_paths(paths: Iterable[str]) -> frozenset[str]:
    """Repo-relative posix forms of a plan's ``creates:`` entries.

    Prefix-strips ``./`` and leading slashes explicitly — ``lstrip("./")``
    would eat the leading dot of a dotted directory (``.plan-tool/…``).
    """
    out: set[str] = set()
    for raw in paths:
        cleaned = (raw or "").strip().replace("\\", "/")
        while cleaned.startswith("./"):
            cleaned = cleaned[2:]
        cleaned = cleaned.lstrip("/")
        if cleaned:
            out.add(cleaned)
    return frozenset(out)


def _walk_anchor_search_tree(repo_root: Path) -> tuple[str, ...]:
    """Repo-relative posix paths of every non-vendor file under ``repo_root``."""
    paths: list[str] = []
    try:
        for directory, dirnames, filenames in repo_root.walk():
            dirnames[:] = [
                name for name in dirnames if name not in _ANCHOR_SEARCH_SKIP_DIRS
            ]
            paths.extend(
                (directory / name).relative_to(repo_root).as_posix()
                for name in filenames
            )
    except OSError:
        return ()
    return tuple(paths)


def _resolve_anchor_path(
    repo_root: Path,
    rel_path: str,
    tree_provider: Callable[[], tuple[str, ...]] | None = None,
) -> Path | None:
    """Resolve ``rel_path`` against ``repo_root``, or by a unique tail match
    elsewhere in the tree (a citation written relative to a monorepo
    subdirectory root). ``None`` on no match *or* an ambiguous one.
    ``tree_provider``, if given, is called at most once and reused — see
    BUG_BACKLOG for why it's per-call, not cached across calls.

    Deliberately requires ``rel_path`` to carry a directory (no bare-filename
    fallback): a bare name is a global search with no per-file distinctiveness
    requirement, so a generic name (``config.py``) can coincidentally and
    silently resolve against an unrelated real file elsewhere in the repo,
    masking a genuinely missing dependency. A multi-segment suffix is far
    less likely to collide by accident. See BUG_BACKLOG.
    """
    direct = repo_root / rel_path
    if direct.is_file():
        return direct
    if "/" not in rel_path:
        return None
    suffix = f"/{rel_path}"
    tree = tree_provider() if tree_provider is not None else _walk_anchor_search_tree(repo_root)
    matches = [p for p in tree if p.endswith(suffix)]
    return (repo_root / matches[0]) if len(matches) == 1 else None


def _code_anchor_resolves(
    repo_root: Path,
    anchor: str,
    planned_paths: frozenset[str] = frozenset(),
    tree_provider: Callable[[], tuple[str, ...]] | None = None,
) -> tuple[bool, str | None]:
    match = _CODE_ANCHOR_RE.match(anchor)
    if not match:
        return True, None
    rel_path = match.group("path")
    symbol = match.group("symbol")
    path = _resolve_anchor_path(repo_root, rel_path, tree_provider)
    if path is None:
        # A path the plan's own steps will create is not drift: the anchor
        # names a dependency contract this plan produces, so "does not exist"
        # is a claim about build order, not about the anchor. Any step counts,
        # not just earlier ones — the finding asserts non-existence, and the
        # plan refutes it regardless of which step lands first.
        if rel_path in planned_paths:
            return True, None
        return False, f"code anchor path `{rel_path}` does not exist"
    resolved_rel_path = path.relative_to(repo_root).as_posix()
    if symbol is None:
        return True, None

    parts = symbol.split(".")
    owner = parts[0]
    field_name = parts[1] if len(parts) == 2 else None
    contracts = _contract_by_owner()
    contract = contracts.get(owner)
    if contract is not None:
        if contract.source_symbol.split(":", 1)[0] != resolved_rel_path:
            return False, f"code anchor `{anchor}` points at the wrong owner path"
        if field_name is None:
            return True, None
        if _valid_contract_field(contract, field_name):
            return True, None
        return False, f"code anchor `{anchor}` names an unregistered field"

    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError) as exc:
        return False, f"code anchor `{anchor}` could not be parsed: {exc}"
    if len(parts) == 1 and _module_level_symbol_exists(tree, owner):
        return True, None
    return False, f"code anchor `{anchor}` does not resolve in HEAD"


def _anchor_matches_reference(anchor: str, owner: str, field_name: str) -> bool:
    match = _CODE_ANCHOR_RE.match(anchor)
    if not match:
        return False
    symbol = match.group("symbol")
    if symbol is None:
        return False
    parts = symbol.split(".")
    if parts[0] != owner:
        return False
    return len(parts) == 1 or (len(parts) == 2 and parts[1] == field_name)


def check_input_contract_references(
    text: str,
    repo_root: Path,
    *,
    location: str,
    step_id: int | None = None,
    path: str | None = None,
    planned_paths: Iterable[str] = (),
    tree_provider: Callable[[], tuple[str, ...]] | None = None,
) -> list[InputContractReferenceIssue]:
    """Validate explicit ``## Input`` contract refs against the code registry.

    The grammar is intentionally narrow: only backticked registered-owner
    references such as ``SavedReview.recommendations`` and backticked Python
    anchors such as ``plan_tool/review.py:Recommendation.source`` are checked.

    ``planned_paths`` are repo-relative paths the plan's own steps will create
    (their ``creates:`` lists); an anchor pointing at one is not flagged for
    non-existence. Callers without a plan in hand pass nothing and get the
    disk-only check.

    ``tree_provider``, if given, is the caller's shared fallback-walk hook —
    pass one when checking several bodies in one read-only sweep (e.g. every
    step of a plan) so they share a single walk. Callers that don't pass one
    get a walk scoped to just this call.
    """
    section = _input_section(text)
    if section is None:
        return []

    contracts = _contract_by_owner()
    planned = _normalize_planned_paths(planned_paths)
    tokens = [m.group(1).strip() for m in _BACKTICK_RE.finditer(section)]
    code_anchors = [token for token in tokens if _CODE_ANCHOR_RE.match(token)]
    issues: list[InputContractReferenceIssue] = []

    if tree_provider is None:
        # Walk the tree at most once for this call, only if some anchor
        # actually needs the fallback.
        tree_box: list[tuple[str, ...]] = []

        def _lazy_tree_provider() -> tuple[str, ...]:
            if not tree_box:
                tree_box.append(_walk_anchor_search_tree(repo_root))
            return tree_box[0]

        tree_provider = _lazy_tree_provider

    for anchor in code_anchors:
        ok, reason = _code_anchor_resolves(repo_root, anchor, planned, tree_provider)
        if not ok:
            issues.append(
                InputContractReferenceIssue(
                    location=location,
                    reason=reason or f"code anchor `{anchor}` does not resolve",
                    code_anchor=anchor,
                    step_id=step_id,
                    path=path,
                )
            )

    for token in tokens:
        match = _CONTRACT_REF_RE.match(token)
        if not match:
            continue
        owner = match.group("owner")
        contract = contracts.get(owner)
        if contract is None:
            continue
        field_name = match.group("field")
        key = match.group("key")
        valid_field = _valid_contract_field(contract, field_name)
        valid_key = _valid_open_bag_key(owner, field_name, key)
        if key is not None and not valid_key:
            issues.append(
                InputContractReferenceIssue(
                    location=location,
                    owner=owner,
                    field_or_key=f"{field_name}.{key}",
                    reason=f"`{token}` is not a registered open-bag key",
                    step_id=step_id,
                    path=path,
                )
            )
            continue
        if key is None and not valid_field:
            issues.append(
                InputContractReferenceIssue(
                    location=location,
                    owner=owner,
                    field_or_key=field_name,
                    reason=f"`{token}` is not a registered persisted field or alias",
                    step_id=step_id,
                    path=path,
                )
            )
            continue
        has_matching_anchor = any(
            _anchor_matches_reference(anchor, owner, field_name)
            for anchor in code_anchors
        )
        if not has_matching_anchor:
            issues.append(
                InputContractReferenceIssue(
                    location=location,
                    owner=owner,
                    field_or_key=f"{field_name}.{key}" if key else field_name,
                    reason=f"`{token}` lacks a matching HEAD code-location anchor",
                    step_id=step_id,
                    path=path,
                )
            )
    return issues


def contract_fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_drift_record(
    *,
    source_type: str,
    owner: str,
    field_or_key: str,
    target_section: str,
    operation: str,
    contract_text: str,
    candidate: dict[str, Any] | None = None,
) -> DriftRecord:
    payload = dict(candidate or {})
    payload.setdefault("owner", owner)
    payload.setdefault("field_or_key", field_or_key)
    payload.setdefault("target_section", target_section)
    return DriftRecord(
        source_type=source_type,
        owner=owner,
        field_or_key=field_or_key,
        target_section=target_section,
        operation=operation,
        registry_fingerprint=registry_fingerprint(),
        contract_fingerprint=contract_fingerprint(contract_text),
        candidate=payload,
    )
