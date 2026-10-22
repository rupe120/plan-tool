"""Persisted concept decision records with stable positional identity."""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import tempfile
import unicodedata
import copy
from dataclasses import asdict, dataclass, field
from pathlib import Path
from string import Template
from typing import Any, Callable, Iterable, Optional

from plan_tool.renderer import prompts_dir
from plan_tool.response_contract import JSON_ROOT_OBJECT, JsonResponseContract
from plan_tool.shell import shell_concept_invoker


CONCEPTS_FILENAME = "concepts.json"
CONCEPTS_SCHEMA_VERSION = 1
CONCEPT_REVIEW_STATES = frozenset({"unreviewed", "approved", "rejected"})
CONCEPT_EMIT_MAX_DEPTH = 3
CONCEPT_EMIT_MAX_BREADTH = 12

# The two record shapes a concepts.json file may hold. The full tree is a cache
# of plan text and is fingerprint-gated on load; the flat decision record is an
# operator/tool decision confirmed after edits, so it skips the staleness check.
RECORD_KIND_FULL_TREE = "full-tree"
RECORD_KIND_DECISION = "decision-record"
CONCEPT_RECORD_KINDS = frozenset({RECORD_KIND_FULL_TREE, RECORD_KIND_DECISION})
CONCEPT_FLAT_DECISIONS = frozenset({"defer", "wont_do"})


class InvalidConceptTreeError(ValueError):
    """A present concept record is malformed or fails an integrity check."""


class StaleConceptTreeError(ValueError):
    """A valid concept record was derived from a different plan revision."""


# Concise aliases make the failure categories convenient for callers.
InvalidConceptsError = InvalidConceptTreeError
StaleConceptsError = StaleConceptTreeError


@dataclass
class ConceptNode:
    """One persisted concept and its mutable review/decision attributes."""

    id: str
    title: str
    parent_path: list[str] = field(default_factory=list)
    order: int = 0
    source: str = ""
    decision: str = ""
    rationale: str = ""
    review_state: str = "unreviewed"
    source_metadata: dict[str, str] = field(default_factory=dict)
    bucket: str = ""


@dataclass
class ConceptTree:
    """The complete concept sidecar for one exact plan revision."""

    plan_slug: str
    plan_fingerprint: str
    concepts: list[ConceptNode] = field(default_factory=list)
    schema_version: int = CONCEPTS_SCHEMA_VERSION
    record_kind: str = RECORD_KIND_FULL_TREE


def concept_id(title: str, parent_path: Iterable[str]) -> str:
    """Return the SHA-256 identity of ``title`` at ``parent_path``.

    Length-prefixing and NUL delimiters make component boundaries
    unambiguous. Only positional titles participate in identity.
    """
    if not isinstance(title, str):
        raise ValueError("concept title must be a non-empty string")
    parents = list(parent_path)
    if any(not isinstance(part, str) for part in parents):
        raise ValueError("parent path must contain non-empty strings")
    normalized = [
        " ".join(unicodedata.normalize("NFKC", component).split())
        for component in [*parents, title]
    ]
    if any(not component for component in normalized):
        raise ValueError("title path components must be non-empty strings")
    digest = hashlib.sha256()
    for component in normalized:
        encoded = component.encode("utf-8")
        digest.update(str(len(encoded)).encode("ascii"))
        digest.update(b"\0")
        digest.update(encoded)
        digest.update(b"\0")
    return digest.hexdigest()


def concepts_path(plan_path: Path) -> Path:
    """Return ``plan-details/<slug>/concepts.json`` beside ``plan_path``."""
    from plan_tool.locator import slug_from_filename

    slug = slug_from_filename(plan_path)
    assert slug is not None
    return plan_path.parent / "plan-details" / slug / CONCEPTS_FILENAME


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_node(node: ConceptNode, index: int, record_kind: str) -> None:
    prefix = f"concepts[{index}]"
    if not isinstance(node.id, str):
        raise InvalidConceptTreeError(f"{prefix}.id must be a string")
    if not isinstance(node.title, str) or not node.title:
        raise InvalidConceptTreeError(f"{prefix}.title must be a non-empty string")
    if not isinstance(node.parent_path, list) or any(
        not isinstance(part, str) or not part for part in node.parent_path
    ):
        raise InvalidConceptTreeError(f"{prefix}.parent_path must be a string list")
    if not _is_int(node.order) or node.order < 0:
        raise InvalidConceptTreeError(f"{prefix}.order must be a non-negative integer")
    for name in ("source", "decision", "rationale", "bucket"):
        if not isinstance(getattr(node, name), str):
            raise InvalidConceptTreeError(f"{prefix}.{name} must be a string")
    if node.review_state not in CONCEPT_REVIEW_STATES:
        raise InvalidConceptTreeError(f"{prefix}.review_state is unknown")
    if not isinstance(node.source_metadata, dict) or any(
        not isinstance(key, str) or not isinstance(value, str)
        for key, value in node.source_metadata.items()
    ):
        raise InvalidConceptTreeError(
            f"{prefix}.source_metadata must map strings to strings"
        )
    if record_kind == RECORD_KIND_DECISION:
        # A flat decision node has no hierarchy; its bucket and decision are the
        # only validity anchors later steps read.
        if node.parent_path:
            raise InvalidConceptTreeError(
                f"{prefix}.parent_path must be empty in a decision record"
            )
        if not node.bucket:
            raise InvalidConceptTreeError(
                f"{prefix}.bucket must be a non-empty string in a decision record"
            )
        if node.decision not in CONCEPT_FLAT_DECISIONS:
            raise InvalidConceptTreeError(
                f"{prefix}.decision must be one of {sorted(CONCEPT_FLAT_DECISIONS)}"
            )
    try:
        expected_id = concept_id(node.title, node.parent_path)
    except ValueError as exc:
        raise InvalidConceptTreeError(f"{prefix}: {exc}") from exc
    if node.id != expected_id:
        raise InvalidConceptTreeError(f"{prefix}.id does not match its position")


def _validate_tree(tree: ConceptTree, expected_slug: Optional[str] = None) -> None:
    if not _is_int(tree.schema_version) or tree.schema_version != CONCEPTS_SCHEMA_VERSION:
        raise InvalidConceptTreeError("unsupported schema_version")
    if tree.record_kind not in CONCEPT_RECORD_KINDS:
        raise InvalidConceptTreeError("unsupported record_kind")
    if not isinstance(tree.plan_slug, str) or not tree.plan_slug:
        raise InvalidConceptTreeError("plan_slug must be a non-empty string")
    if expected_slug is not None and tree.plan_slug != expected_slug:
        raise InvalidConceptTreeError("plan_slug does not match the plan path")
    if not isinstance(tree.plan_fingerprint, str) or not tree.plan_fingerprint:
        raise InvalidConceptTreeError("plan_fingerprint must be a non-empty string")
    if not isinstance(tree.concepts, list):
        raise InvalidConceptTreeError("concepts must be a list")

    identities: set[str] = set()
    positions: set[tuple[tuple[str, ...], str]] = set()
    for index, node in enumerate(tree.concepts):
        if not isinstance(node, ConceptNode):
            raise InvalidConceptTreeError(f"concepts[{index}] must be a ConceptNode")
        _validate_node(node, index, tree.record_kind)
        if node.id in identities:
            raise InvalidConceptTreeError("duplicate concept id")
        identities.add(node.id)
        positions.add((tuple(node.parent_path), node.title))
    for index, node in enumerate(tree.concepts):
        for depth, title in enumerate(node.parent_path):
            if (tuple(node.parent_path[:depth]), title) not in positions:
                raise InvalidConceptTreeError(
                    f"concepts[{index}].parent_path is not represented by the tree"
                )


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise InvalidConceptTreeError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _decode_tree(data: object) -> ConceptTree:
    # Required subset stays the legacy field set; the new optional keys widen the
    # allowed bound so old records missing them decode to their field defaults
    # while unknown keys are still rejected as tampering.
    tree_required = {"plan_slug", "plan_fingerprint", "concepts", "schema_version"}
    tree_allowed = tree_required | {"record_kind"}
    node_required = {
        "id", "title", "parent_path", "order", "source", "decision",
        "rationale", "review_state", "source_metadata",
    }
    node_allowed = node_required | {"bucket"}
    if not isinstance(data, dict) or not tree_required <= set(data) <= tree_allowed:
        raise InvalidConceptTreeError("top-level record has missing or unknown fields")
    if not isinstance(data["concepts"], list):
        raise InvalidConceptTreeError("concepts must be a list")
    nodes: list[ConceptNode] = []
    for index, raw in enumerate(data["concepts"]):
        if not isinstance(raw, dict) or not node_required <= set(raw) <= node_allowed:
            raise InvalidConceptTreeError(
                f"concepts[{index}] has missing or unknown fields"
            )
        nodes.append(ConceptNode(**raw))
    return ConceptTree(
        plan_slug=data["plan_slug"],
        plan_fingerprint=data["plan_fingerprint"],
        concepts=nodes,
        schema_version=data["schema_version"],
        record_kind=data.get("record_kind", RECORD_KIND_FULL_TREE),
    )


def load_concepts(
    plan_path: Path, expected_plan_fingerprint: str
) -> Optional[ConceptTree]:
    """Load a current concept tree, return ``None`` only when it is absent."""
    path = concepts_path(plan_path)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError) as exc:
        raise InvalidConceptTreeError(f"cannot read {path}: {exc}") from exc
    try:
        data = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=lambda value: (_ for _ in ()).throw(
                InvalidConceptTreeError(f"non-finite JSON number: {value}")
            ),
        )
    except InvalidConceptTreeError:
        raise
    except (json.JSONDecodeError, TypeError) as exc:
        raise InvalidConceptTreeError("malformed concepts JSON") from exc
    tree = _decode_tree(data)

    from plan_tool.locator import slug_from_filename

    slug = slug_from_filename(plan_path)
    assert slug is not None
    _validate_tree(tree, slug)
    if not isinstance(expected_plan_fingerprint, str):
        raise TypeError("expected_plan_fingerprint must be a string")
    # A decision record is a confirmed operator/tool decision, not a cache of
    # plan text, so its fingerprint is provenance only and never gates the load.
    if (
        tree.record_kind == RECORD_KIND_FULL_TREE
        and tree.plan_fingerprint != expected_plan_fingerprint
    ):
        raise StaleConceptTreeError("stored plan fingerprint is stale")
    return tree


def save_concepts(
    plan_path: Path, tree: ConceptTree,
    *, publish: Callable[[Path, bytes], None] | None = None,
) -> Path:
    """Validate and atomically publish a tree; an optional publisher owns the write."""
    from plan_tool.locator import slug_from_filename

    slug = slug_from_filename(plan_path)
    assert slug is not None
    _validate_tree(tree, slug)
    path = concepts_path(plan_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(asdict(tree), indent=2, allow_nan=False) + "\n"
    if publish is not None:
        publish(path, text.encode("utf-8"))
        return path
    temporary = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent,
        prefix=f".{path.name}.", suffix=".tmp", delete=False,
    )
    temporary_path = Path(temporary.name)
    try:
        try:
            temporary.write(text)
            temporary.flush()
            os.fsync(temporary.fileno())
        finally:
            temporary.close()
        os.replace(temporary_path, path)
    except BaseException:
        with contextlib.suppress(OSError):
            temporary_path.unlink()
        raise
    return path


def render_concept_emit_prompt(evidence: str, *, plan_context: str = "") -> str:
    """Render the bounded concept-enrichment request from supplied text only."""
    template_path = prompts_dir() / "concept-emit.md"
    template = Template(template_path.read_text(encoding="utf-8"))
    return template.safe_substitute(
        evidence=evidence,
        plan_context=plan_context or "(no plan context supplied)",
        max_depth=str(CONCEPT_EMIT_MAX_DEPTH),
        max_breadth=str(CONCEPT_EMIT_MAX_BREADTH),
        response_format_block=_CONCEPT_EMIT_RESPONSE_CONTRACT.render_prompt_block(),
    )


def _parse_emitted_concepts(stdout: str, evidence: str) -> list[tuple[str, list[str], str]]:
    """Return validated ``(title, parent_path, evidence_excerpt)`` entries."""
    payload = _CONCEPT_EMIT_RESPONSE_CONTRACT.decode(
        stdout, allow_surrounding=False, object_pairs_hook=_reject_duplicate_keys
    )
    if not isinstance(payload, dict):
        return []
    roots = payload["concepts"]
    if not isinstance(roots, list) or len(roots) > CONCEPT_EMIT_MAX_BREADTH:
        return []

    allowed_fields = {"id", "title", "suggested_state", "evidence_rationale", "children"}
    required_fields = {"title", "suggested_state", "evidence_rationale"}
    parsed: list[tuple[str, list[str], str]] = []

    def visit(raw_nodes: object, parent_path: list[str], depth: int) -> bool:
        if (
            not isinstance(raw_nodes, list)
            or len(raw_nodes) > CONCEPT_EMIT_MAX_BREADTH
            or depth > CONCEPT_EMIT_MAX_DEPTH
        ):
            return False
        for raw in raw_nodes:
            if (
                not isinstance(raw, dict)
                or not required_fields <= set(raw) <= allowed_fields
                or not isinstance(raw["title"], str)
                or not raw["title"].strip()
                or not isinstance(raw["suggested_state"], str)
                or not isinstance(raw["evidence_rationale"], str)
                or not raw["evidence_rationale"].strip()
            ):
                return False
            title = " ".join(raw["title"].split())
            rationale = raw["evidence_rationale"].strip()
            # Requiring a literal excerpt gives local validation real teeth:
            # a fluent rationale unsupported by the envelope is not evidence.
            if rationale.casefold() not in evidence.casefold():
                return False
            parsed.append((title, list(parent_path), rationale))
            children = raw.get("children", [])
            if not visit(children, [*parent_path, title], depth + 1):
                return False
        return True

    return parsed if visit(roots, [], 1) else []


def emit_concept_tree(
    tree: ConceptTree,
    evidence: str,
    *,
    plan_context: str = "",
    invoker: Callable[[str], str] = shell_concept_invoker,
) -> Optional[ConceptTree]:
    """Propose evidence-backed concepts for a full tree without persistence.

    Invalid model output and an empty candidate set are normal no-enrichment
    outcomes. Flat decision records require bucket and decision values a
    generic emitted node cannot supply, so they are not enriched. The caller's
    tree is never mutated.
    """
    if tree.record_kind == RECORD_KIND_DECISION:
        return None

    prompt = render_concept_emit_prompt(evidence, plan_context=plan_context)
    try:
        emitted = _parse_emitted_concepts(invoker(prompt), evidence)
    except Exception:  # backend/injected invoker failures are fail-soft here
        return None
    if not emitted:
        return None

    fresh = copy.deepcopy(tree)
    occupied = {(tuple(node.parent_path), node.title) for node in fresh.concepts}
    next_order = max((node.order for node in fresh.concepts), default=-1) + 1
    added = False
    for title, parent_path, excerpt in emitted:
        position = (tuple(parent_path), title)
        if position in occupied:
            continue
        node = ConceptNode(
            id=concept_id(title, parent_path),
            title=title,
            parent_path=parent_path,
            order=next_order,
            source=excerpt,
        )
        fresh.concepts.append(node)
        occupied.add(position)
        next_order += 1
        added = True
    if not added:
        return None

    # Import lazily: concept_bootstrap owns the public three-way contract and
    # imports these record types itself.
    from plan_tool.concept_bootstrap import rederive_concepts

    merged = rederive_concepts(tree, fresh).updated_tree
    if merged is None:
        return None
    # Enrichment is additive. Even the core's harmless baseline bookkeeping
    # would technically rewrite source metadata on a legacy/in-memory node,
    # so retain every pre-existing record byte-for-byte and take only the
    # contract-approved additions from the candidate.
    existing_by_id = {node.id: node for node in tree.concepts}
    merged.concepts = [
        copy.deepcopy(existing_by_id.get(node.id, node))
        for node in merged.concepts
    ]
    return merged


read_concepts = load_concepts
write_concepts = save_concepts
_CONCEPT_EMIT_RESPONSE_CONTRACT = JsonResponseContract(
    root=JSON_ROOT_OBJECT,
    example={
        "concepts": [{
            "title": "concept title",
            "suggested_state": "candidate",
            "evidence_rationale": "literal evidence excerpt",
            "children": [],
        }]
    },
    required_keys=frozenset({"concepts"}),
    exact_keys=True,
)
