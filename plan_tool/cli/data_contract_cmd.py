"""Interactive apply command for saved data-contract drift findings."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from plan_tool.cli.context import _load_context
from plan_tool.cli.parser import Handler
from plan_tool.locator import resolve_plan_for_context
from plan_tool.review import Recommendation, confidence_label
from plan_tool.review_persistence import (
    COMPLETENESS_SIDECAR_SUFFIX,
    ReviewLoadError,
    load_review,
    project_saved_completeness_result,
    resolve_saved_review,
)
from plan_tool.review_walk import WalkState, walk_recommendations
from plan_tool.style import error, warn


DATA_CONTRACT_SOURCE = "data-contract"
DATA_CONTRACT_TARGET = "DATA_CONTRACT.md"
APPLYABLE_OPERATIONS = frozenset({"add", "update", "remove"})


@dataclass(frozen=True)
class _ContractCandidate:
    rec: Recommendation
    payload: dict[str, Any]


def _payload_path(saved_path: Path) -> Path:
    return saved_path.with_name(f"{saved_path.stem}-data-contract.json")


def _load_payloads(saved_path: Path) -> dict[str, dict[str, Any]]:
    path = _payload_path(saved_path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as exc:
        raise ReviewLoadError(f"could not read {path}: {exc}") from exc
    if not isinstance(data, dict) or data.get("kind") != DATA_CONTRACT_SOURCE:
        raise ReviewLoadError(f"{path}: not a data-contract payload sidecar")
    payloads = data.get("payloads", {})
    if not isinstance(payloads, dict):
        raise ReviewLoadError(f"{path}: payloads must be an object")
    return {str(k): v for k, v in payloads.items() if isinstance(v, dict)}


def _payload_target(payload: dict[str, Any]) -> str:
    return str(payload.get("target") or DATA_CONTRACT_TARGET)


def _payload_operation(payload: dict[str, Any]) -> str:
    return str(payload.get("operation") or "")


def _is_applyable_contract_payload(payload: dict[str, Any]) -> bool:
    return (
        _payload_target(payload) == DATA_CONTRACT_TARGET
        and _payload_operation(payload) in APPLYABLE_OPERATIONS
    )


def _filter_candidates(
    recs: list[Recommendation],
    payloads: dict[str, dict[str, Any]],
    *,
    anchors: list[str] | None = None,
) -> tuple[list[_ContractCandidate], list[Recommendation]]:
    candidates: list[_ContractCandidate] = []
    non_applyable: list[Recommendation] = []
    wanted = set(anchors or [])

    for rec in recs:
        if rec.source != DATA_CONTRACT_SOURCE:
            continue
        if wanted and rec.id not in wanted and rec.anchor not in wanted:
            continue
        payload = payloads.get(rec.id)
        if payload is None:
            non_applyable.append(rec)
            continue
        if not _is_applyable_contract_payload(payload):
            non_applyable.append(rec)
            continue
        candidates.append(_ContractCandidate(rec=rec, payload=payload))
    return candidates, non_applyable


def _warn_missing_anchors(
    candidates: list[_ContractCandidate],
    non_applyable: list[Recommendation],
    anchors: list[str] | None,
) -> None:
    if not anchors:
        return
    matched = {c.rec.id for c in candidates} | {
        c.rec.anchor for c in candidates if c.rec.anchor
    }
    matched |= {r.id for r in non_applyable} | {
        r.anchor for r in non_applyable if r.anchor
    }
    missing = set(anchors) - matched
    if missing:
        warn("no data-contract finding matched --anchor " + ", ".join(sorted(missing)))


def _newest_saved_completeness_with_contract_payload(
    name: str,
    repo_root: Path,
    *,
    plan_path: Optional[Path],
) -> tuple[Path, Any, dict[str, dict[str, Any]]]:
    from plan_tool.review_persistence import list_saved_reviews

    newest_eligible: tuple[Path, Any, dict[str, dict[str, Any]]] | None = None
    for path in list_saved_reviews(name, repo_root, plan_path=plan_path):
        if not path.name.endswith(COMPLETENESS_SIDECAR_SUFFIX):
            continue
        try:
            saved = load_review(path)
        except ReviewLoadError:
            continue
        if (
            saved.kind != "completeness"
            or saved.is_pre_apply_checkpoint is not False
            or not project_saved_completeness_result(
                saved, plan_path, repo_root
            ).is_current_final_qualified
        ):
            continue
        payloads = _load_payloads(path)
        if newest_eligible is None:
            newest_eligible = (path, saved, payloads)
        candidates, _ = _filter_candidates(saved.recommendations, payloads)
        if candidates:
            return path, saved, payloads
    if newest_eligible is not None:
        return newest_eligible
    raise FileNotFoundError(
        f"no current final qualified completeness audit for plan {name!r}. Run "
        f"`plan-tool completeness-audit {name}` first."
    )


def _current_freshness(repo_root: Path) -> tuple[str, str]:
    from plan_tool import data_contract as contract

    doc_path = repo_root / DATA_CONTRACT_TARGET
    text = doc_path.read_text(encoding="utf-8")
    return contract.registry_fingerprint(), contract.contract_fingerprint(text)


def _verify_fresh(payload: dict[str, Any], repo_root: Path) -> str | None:
    freshness = payload.get("freshness")
    if not isinstance(freshness, dict):
        return "missing data-contract freshness metadata"
    expected_registry = freshness.get("registry_fingerprint")
    expected_contract = freshness.get("contract_fingerprint")
    if not expected_registry or not expected_contract:
        return "incomplete data-contract freshness metadata"
    current_registry, current_contract = _current_freshness(repo_root)
    if expected_registry != current_registry:
        return "code-owned data-contract registry changed"
    if expected_contract != current_contract:
        return "DATA_CONTRACT.md changed"
    return None


def _section_bounds(text: str, title: str) -> tuple[int, int] | None:
    heading_re = re.compile(r"^(#{2,6})\s+(.+?)\s*$", re.MULTILINE)
    headings = list(heading_re.finditer(text))
    # Prefer the backticked-owner token (``### `SavedReview` (…)``) so an owner
    # name that is a substring of another heading can't resolve the wrong
    # section; fall back to a bare substring for non-backticked titles.
    for want in (f"`{title}`", title):
        for i, match in enumerate(headings):
            if want in match.group(2):
                level = len(match.group(1))
                end = len(text)
                for later in headings[i + 1 :]:
                    if len(later.group(1)) <= level:
                        end = later.start()
                        break
                return match.start(), end
    return None


def _candidate_fields(payload: dict[str, Any]) -> dict[str, Any]:
    fields = payload.get("candidate_fields")
    if isinstance(fields, dict):
        return fields
    fields = payload.get("candidate")
    return fields if isinstance(fields, dict) else {}


def _persisted_cell(payload: dict[str, Any]) -> str:
    """The Persisted column, honoring the drift record's requirement.

    In-memory-only fields must read as not-persisted (the doc convention is
    ``**no** (in-memory)``); the "in-memory" phrase also satisfies the
    collector's drift check, so an applied row converges. See DATA_CONTRACT.md.
    """
    fields = _candidate_fields(payload)
    field = str(fields.get("field") or payload.get("field_or_key") or "")
    if fields.get("requirement") == "in_memory_only":
        return "**no** (in-memory)"
    json_key = fields.get("json_key")
    if json_key and json_key != field:
        return f"yes (as JSON `{json_key}`)"
    return "yes"


def _existing_row_meaning(row_text: str) -> str | None:
    cells = [c.strip() for c in row_text.strip().strip("|").split("|")]
    return cells[2] if len(cells) >= 3 else None


def _contract_row(payload: dict[str, Any], *, meaning: str | None = None) -> str:
    fields = _candidate_fields(payload)
    field = str(fields.get("field") or payload.get("field_or_key") or "")
    if meaning is None:
        source = fields.get("source_symbol") or payload.get("source_symbol")
        meaning = "persisted data-contract field; fill in operator-facing meaning"
        if source:
            meaning += f" (source: `{source}`)"
    return f"| `{field}` | {_persisted_cell(payload)} | {meaning} |\n"


def _apply_add_or_update(text: str, payload: dict[str, Any]) -> str:
    section = str(payload.get("target_section") or "")
    bounds = _section_bounds(text, section)
    fields = _candidate_fields(payload)
    field = str(fields.get("field") or payload.get("field_or_key") or "")
    if not section or not field:
        raise ValueError("data-contract payload is missing target section or field")
    if bounds is None:
        return (
            text.rstrip()
            + f"\n\n### `{section}`\n\n| Field | Persisted | Meaning |\n|---|---|---|\n"
            + _contract_row(payload)
        )
    start, end = bounds
    body = text[start:end]
    row_re = re.compile(rf"^\|\s*`{re.escape(field)}`\s*\|.*(?:\n|$)", re.MULTILINE)
    existing = row_re.search(body)
    if existing:
        # Preserve the operator-written Meaning cell; an update only corrects
        # the Persisted column, so we don't clobber hand-authored prose.
        row = _contract_row(payload, meaning=_existing_row_meaning(existing.group(0)))
        body = body[: existing.start()] + row + body[existing.end() :]
    else:
        table_match = re.search(r"^\|[-: |]+\|\s*$", body, re.MULTILINE)
        insert_at = table_match.end() + 1 if table_match else len(body)
        body = body[:insert_at] + _contract_row(payload) + body[insert_at:]
    return text[:start] + body + text[end:]


def _apply_remove(text: str, payload: dict[str, Any]) -> str:
    section = str(payload.get("target_section") or "")
    bounds = _section_bounds(text, section)
    field = str(_candidate_fields(payload).get("field") or payload.get("field_or_key") or "")
    if bounds is None or not field:
        return text
    start, end = bounds
    body = text[start:end]
    row_re = re.compile(rf"^\|\s*`{re.escape(field)}`\s*\|.*(?:\n|$)", re.MULTILINE)
    body = row_re.sub("", body)
    return text[:start] + body + text[end:]


def _apply_payload_to_contract(doc_path: Path, payload: dict[str, Any]) -> bool:
    text = doc_path.read_text(encoding="utf-8")
    operation = _payload_operation(payload)
    if operation in {"add", "update"}:
        updated = _apply_add_or_update(text, payload)
    elif operation == "remove":
        updated = _apply_remove(text, payload)
    else:
        raise ValueError(f"unsupported data-contract operation {operation!r}")
    if updated == text:
        return False
    doc_path.write_text(updated, encoding="utf-8")
    return True


def _make_action_fn(
    *,
    payloads: dict[str, dict[str, Any]],
    repo_root: Path,
    state: WalkState,
):
    def _action(rec: Recommendation) -> str:
        payload = payloads.get(rec.id)
        if not isinstance(payload, dict) or not _is_applyable_contract_payload(payload):
            state.apply_skip = True
            return (
                "blocked: missing applyable data-contract payload; rerun "
                "`plan-tool completeness-audit` before applying."
            )
        stale_reason = _verify_fresh(payload, repo_root)
        if stale_reason is not None:
            state.apply_skip = True
            return (
                f"blocked: {stale_reason}; rerun `plan-tool completeness-audit` "
                "before applying."
            )
        try:
            changed = _apply_payload_to_contract(repo_root / DATA_CONTRACT_TARGET, payload)
        except Exception as exc:
            state.apply_failed = True
            return f"failed: {exc}"
        if not changed:
            state.apply_skip = True
            return "blocked: DATA_CONTRACT.md already matches this payload."
        return f"updated {DATA_CONTRACT_TARGET}"

    return _action


def _finding_label(rec: Recommendation) -> str:
    anchor = f" [{rec.anchor}]" if rec.anchor else ""
    return f"{rec.id}{anchor}: {rec.title} [{confidence_label(rec.confidence)}]"


def cmd_data_contract_apply(args: argparse.Namespace) -> int:
    ctx = _load_context(args)
    try:
        plan_path = resolve_plan_for_context(ctx, args.name)
    except Exception:
        plan_path = None

    try:
        if args.id:
            saved_path = resolve_saved_review(
                args.name, ctx.repo_root, review_id=args.id, plan_path=plan_path
            )
            saved = load_review(saved_path)
            payloads = None
        else:
            saved_path, saved, payloads = _newest_saved_completeness_with_contract_payload(
                args.name, ctx.repo_root, plan_path=plan_path
            )
    except FileNotFoundError as exc:
        error(str(exc))
        return 2
    except ReviewLoadError as exc:
        error(str(exc))
        return 1

    if saved.kind != "completeness":
        error(f"{saved_path} is a {saved.kind!r} save, not a completeness audit.")
        return 2
    if (
        saved.is_pre_apply_checkpoint is not False
        or not project_saved_completeness_result(
            saved, plan_path, ctx.repo_root
        ).is_current_final_qualified
    ):
        error(
            "saved completeness audit is not final current qualified evidence; "
            f"run `plan-tool completeness-audit {args.name}` before applying."
        )
        return 2

    # An explicitly selected completeness sidecar must establish final,
    # confirmed, current audit evidence before its sibling payload can be
    # parsed or any finding is displayed.  A malformed payload is immaterial
    # when the audit itself is unavailable evidence.
    if payloads is None:
        try:
            payloads = _load_payloads(saved_path)
        except ReviewLoadError as exc:
            error(str(exc))
            return 1

    candidates, non_applyable = _filter_candidates(
        saved.recommendations, payloads, anchors=args.anchor
    )
    _warn_missing_anchors(candidates, non_applyable, args.anchor)

    for rec in non_applyable:
        print(
            "Skipping non-applyable data-contract finding "
            f"{_finding_label(rec)}; target is not DATA_CONTRACT.md or the "
            "structured payload is missing."
        )

    if not candidates:
        print(f"No applyable DATA_CONTRACT.md drift findings in {saved_path}.")
        return 0

    if not sys.stdin.isatty():
        warn(
            f"non-interactive stdin: skipping data-contract apply walk "
            f"({len(candidates)} finding(s)). Re-run "
            f"`plan-tool data-contract-apply {args.name}` on a terminal to walk them."
        )
        for candidate in candidates:
            print(f"  {_finding_label(candidate.rec)}")
        return 0

    saved.recommendations = [candidate.rec for candidate in candidates]
    state = WalkState()
    result = walk_recommendations(
        saved,
        rewalk=args.rewalk,
        action_fn=_make_action_fn(
            payloads=payloads,
            repo_root=ctx.repo_root,
            state=state,
        ),
        state=state,
        skip_info=not args.include_info,
        extra_apply_sources=frozenset({DATA_CONTRACT_SOURCE}),
    )
    print(
        f"\nplan-tool: data-contract-apply done — {result.answered} "
        "finding(s) annotated this session."
    )
    return 0


def register(subparsers) -> dict[str, Handler]:
    sub = subparsers
    p = sub.add_parser(
        "data-contract-apply",
        help="walk saved DATA_CONTRACT.md drift findings from a completeness audit",
        description=(
            "Interactively apply DATA_CONTRACT.md drift recommendations saved "
            "by completeness-audit."
        ),
    )
    p.add_argument("name", help="plan name/slug")
    p.add_argument("--id", help="saved completeness audit id/stem to replay")
    p.add_argument(
        "--anchor",
        action="append",
        help="walk only a recommendation id or anchor (repeatable)",
    )
    p.add_argument(
        "--rewalk",
        action="store_true",
        help="revisit findings already annotated applied/skipped",
    )
    p.add_argument(
        "--include-info",
        action="store_true",
        help="include info-level recommendations in the walk",
    )
    return {"data-contract-apply": cmd_data_contract_apply}
