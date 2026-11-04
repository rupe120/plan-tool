"""Phase helpers for ``completeness-audit``.

``cmd_completeness`` (in :mod:`plan_tool.cli.completeness_cmd`) is the
orchestrator; the named phases it delegates to live here:

- ``_run_deterministic_checks`` — the no-claude well-formedness battery,
  plus (under ``run_purity``) the one per-step MIXED-STEP purity claude pass
  that folds ``medium`` ``granularity-split`` recs into the smell bucket.
  Every deterministic detector it runs is a ``review.DetectorEntry`` reached
  through the registry ``deterministic_detector_registry`` composes, never a
  hard-coded call — so a detector can be admitted or skipped on its own.
- ``_sample_conceptual_audit`` — the single up-front conceptual audit.
- ``_run_iterate_convergence_loop`` — the ``--iterate`` convergence loop
  itself: file-to-step map, scope-guard buffer, iteration-lock session,
  the loop's own single up-front conceptual audit, the ``while``
  convergence loop (triage, per-finding ``apply_finding`` dispatch,
  pre/post-apply drift checks, auto-reconcile, collision sidecar, scope
  eval), and the post-loop re-parse.
- ``_render_completeness_json`` / ``_render_grouped_report`` /
  ``_persist_and_present_report`` — the rendering + persistence tail.

``cmd_completeness`` calls the convergence loop through a qualified
module reference (``completeness_phases._run_iterate_convergence_loop(
...)``), not a bare re-imported name — unlike ``_run_deterministic_checks``
and ``_sample_conceptual_audit``, comparably-sized phases the same
command bare-imports. The qualified form is specifically because the
whole function is wholesale-monkeypatched in
``tests/cli/test_completeness_cmd.py`` (``monkeypatch.setattr(
completeness_phases, "_run_iterate_convergence_loop", fake_loop)``),
which only intercepts calls through the module object; a bare-imported
name binds at import time and the monkeypatch would silently miss it.
Relocating a future phase of comparable size does **not** need the
qualified form unless it is patched the same way — check for a
wholesale monkeypatch on the phase's own name before choosing. The
loop's *other* monkeypatch seams (``apply_finding``, ``shell_review_invoker``)
and the seams used elsewhere in this module (``shell_review_invoker``,
the deterministic detectors) are patched on their *domain* modules
(``plan_tool.review`` / ``plan_tool.launcher``), so a body-local
re-import intercepts identically regardless of which CLI module hosts
the call — relocating those phases retargets nothing.

The two result bundles (:class:`_DeterministicReport`,
:class:`_IterateOutcome`) live here because both the command module
(which builds an empty ``_IterateOutcome`` for its audit-only branch,
and receives one back from the qualified loop call otherwise) and these
phase helpers (which produce/consume them) need the type; the import
edge is one-directional (``completeness_cmd`` → ``completeness_phases``).
Nothing here imports ``completeness_cmd`` at module load time — the one
cross-reference (``_completeness_has_blocking_findings``) is computed by
the orchestrator and passed in, keeping this a pure leaf.
"""

from __future__ import annotations

import dataclasses as dc
import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from plan_tool.review import DetailBundleStatus, Recommendation

from plan_tool.audit_shapes import AuditShapeAdvisory
from plan_tool.convergence import (
    ConvergenceState,
    finding_set_delta,
    is_blocking,
    record_iteration,
    should_continue,
    touch,
)
from plan_tool.parser import (
    ParseError,
    ValidationError,
    parse_plan,
)
from plan_tool.review import (
    AUDIT_DEFAULT_DRY_ROUNDS,
    CARRIED_RESOLUTION_SKIPPED,
    RESTATED_PROPERTY_LABEL,
    audit_targeted_fix,
    confidence_label,
    confidence_value,
    format_recommendation_for_apply,
    restated_property_or_none,
)
from plan_tool.style import (
    error,
    info,
    render_markdown_for_console,
    warn,
)

from plan_tool.cli.reconcile import (
    _emit_drift_halt_warning,
    _emit_scope_guard_plan,
    _print_attributed_files,
    _run_auto_reconcile_on_drift,
)
from plan_tool.completeness_report import (
    ABSENT_BLOCKING_VERDICT,
    _blocking_deterministic_steps,
    _close_conceptual_steps,
    _fresh_audit_required,
    _reaudit_command,
    reaudit_step,
    _verdict_offers_stage,
    format_finding_bullet,
    next_stage_command,
    next_step_gaps,
)


_QUALIFIED_RESULT_UNSET = object()


@dataclass(frozen=True)
class _DeterministicReport:
    """The deterministic well-formedness battery's findings, grouped by
    detector. Produced by ``_run_deterministic_checks`` and consumed by
    the blocking-gate check, the ``--json`` payload, and the grouped
    report — single-sourcing the nine issue lists across all three.

    ``smell_recs`` is advisory: plan-structure heuristics that the
    blocking-gate check never reads — surfaced but never auto-applied and
    never flip the exit code. ``self_consistency_recs`` is the opposite —
    a bucket the gate *does* read at ``medium``+, so a plan-internal
    consistency finding can block while advisory smells stay non-blocking.
    It carries every ``review.SELF_CONSISTENCY_SOURCES`` finding: a
    deliverable no step consumes, an unaccounted signed-off concept, a
    step whose deliverable suppresses a gate, and a plan or step declaring
    no ``intent``. ``purity_coverage_recs`` is the other blocking bucket: a
    failed per-step MIXED-STEP purity scan, or an eligible readable step
    skipped after the purity battery budget expires. Both are ``high``
    coverage errors rather than smells, so they cannot read as low-yield
    convergence under #125.
    Defaulted fields are declared after the original required buckets so
    positional/partial constructors (and the ``_empty_det()`` test helper)
    stay valid."""

    path_style_hint: object
    dep_issues: list
    body_issues: list
    detail_cov_issues: list
    detail_body_issues: list
    files_coh_issues: list
    lessons_issues: list
    smell_recs: list = field(default_factory=list)
    self_consistency_recs: list = field(default_factory=list)
    data_contract_recs: list = field(default_factory=list)
    data_contract_payloads: dict = field(default_factory=dict)
    purity_coverage_recs: list = field(default_factory=list)


@dataclass
class _IterateOutcome:
    """What the ``--iterate`` convergence loop hands back to the
    orchestrator. In audit-only mode an empty instance stands in (no loop
    ran): ``audit_recs is None`` signals "audit fresh below" and ``plan``
    is left for the orchestrator's own parse.

    ``early_exit_code`` carries a loop-internal halt (pre-apply drift,
    post-apply parse failure) back out so the orchestrator can forward it
    as its own rc while still persisting a report — the loop has already
    emitted the warning/scope-guard side effects before returning."""

    applied_outcomes: list = field(default_factory=list)
    deferred_recs: dict = field(default_factory=dict)
    stop_reason: Optional[str] = None
    halt_reason: Optional[str] = None
    iterations: int = 0
    audit_recs: Optional[list] = None
    plan: object = None
    early_exit_code: Optional[int] = None
    # The audit's budget verdict (BACKLOG #60c) so the persisted report can
    # record "coverage unconfirmed", not just the transient stderr line.
    budget: dict = field(default_factory=dict)
    conceptual_bar_blocking_ids: tuple[str, ...] = ()
    audit_incomplete: bool = False
    # The immutable run-grade audit advisory. This is deliberately separate
    # from ``audit_recs`` so it cannot reach normal finding dispatch.
    audit_shape_advisory: Optional[AuditShapeAdvisory] = None
    # Set only after the pre-apply checkpoint persisted the same advisory.
    # Final report persistence must retain that original payload even after
    # iterate applies mutate the plan/detail files.
    audit_shape_advisory_checkpoint_saved: bool = False
    # The one immutable plan/detail capture supplied to every conceptual
    # prompt and both persistence lanes. ``None`` means sampling failed or no
    # conceptual audit evidence exists.
    audit_input_snapshot: object = None
    audit_stage: Optional[str] = None
    audit_capture_failed: bool = False
    # Sampler provenance is presentation-only; it never contributes to audit
    # coverage, qualified-result classification, or persisted sidecars.
    resumed_from_sampler_checkpoint: bool = False
    qualified_result: object = None


def _resolve_plan_for_report(path: Path, outcome: _IterateOutcome, fallback):
    """Return a parsed plan for report rendering, falling back when the
    on-disk frontmatter is temporarily unparseable after a bad apply."""
    try:
        return parse_plan(path)
    except (ParseError, ValidationError):
        if outcome.plan is not None:
            return outcome.plan
        return fallback


def _audit_recs_for_report(audit_recs: list, applied_ids: set[str]) -> list:
    """Report/sidecar view of the conceptual audit recs.

    Under the read-only-audit split (#85) the loop never applies a
    conceptual-correctness finding, so ``applied_ids`` (deterministic ids
    only) can't intersect a ``plan-correctness`` rec — this filter is a
    defensive no-op kept so a future change that *does* apply correctness
    still drops it from the report rather than double-listing it."""
    return [
        r for r in audit_recs
        if not (
            r.source == "plan-correctness"
            and r.id in applied_ids
        )
    ]


_CONTRACT_HEADING_RE = re.compile(r"^(#{2,6})\s+(.+?)\s*$", re.MULTILINE)
_CONTRACT_FIELD_ROW_RE = re.compile(r"^\|\s*`([^`]+)`\s*\|", re.MULTILINE)


def _data_contract_doc_path(repo_root: Path) -> Path:
    return repo_root / "DATA_CONTRACT.md"


def _data_contract_section(text: str, title: str) -> str | None:
    headings = list(_CONTRACT_HEADING_RE.finditer(text))
    # Prefer the backticked-owner token so an owner name that is a substring of
    # another heading resolves the right section; fall back to substring for
    # non-backticked titles (e.g. "Plan manifest"). Mirror ``_section_bounds``.
    for want in (f"`{title}`", title):
        for i, match in enumerate(headings):
            if want in match.group(2):
                level = len(match.group(1))
                end = len(text)
                for later in headings[i + 1 :]:
                    if len(later.group(1)) <= level:
                        end = later.start()
                        break
                return text[match.start() : end]
    return None


def _data_contract_documented_fields(section_text: str) -> set[str]:
    current = _CONTRACT_HEADING_RE.search(section_text)
    search_from = current.end() if current else 0
    nested = _CONTRACT_HEADING_RE.search(section_text, search_from)
    own_text = section_text[: nested.start()] if nested else section_text
    return set(_CONTRACT_FIELD_ROW_RE.findall(own_text))


def _data_contract_obsolete_dataclass_sections(
    text: str, registered: set[str]
) -> set[str]:
    obsolete: set[str] = set()
    for match in _CONTRACT_HEADING_RE.finditer(text):
        title = match.group(2)
        owner_match = re.match(r"`([^`]+)` \(`[^`]+\.py`", title)
        if owner_match and owner_match.group(1) not in registered:
            obsolete.add(owner_match.group(1))
    return obsolete


def _data_contract_record_payload(record) -> dict:
    payload = dc.asdict(record)
    payload["candidate_fields"] = record.candidate
    payload["freshness"] = {
        "registry_fingerprint": record.registry_fingerprint,
        "contract_fingerprint": record.contract_fingerprint,
    }
    return payload


def _data_contract_rec_for_record(record) -> object:
    from plan_tool.review import Recommendation, _make_rec_id

    target = f"DATA_CONTRACT.md:{record.target_section}"
    field = record.field_or_key
    if record.operation == "add":
        body = (
            f"{target} is missing `{field}` from the code-owned "
            f"{record.owner} data contract."
        )
    elif record.operation == "remove":
        body = (
            f"{target} documents stale `{field}` that is no longer in the "
            f"code-owned {record.owner} data contract."
        )
    else:
        body = (
            f"{target} has {record.operation} drift for `{field}` in the "
            f"code-owned {record.owner} data contract."
        )
    fingerprint = json.dumps(_data_contract_record_payload(record), sort_keys=True)
    return Recommendation(
        id=_make_rec_id(None, "data-contract", fingerprint),
        source="data-contract",
        severity="medium",
        step_id=None,
        title=body,
        body=body,
        suggested_action=(
            f"Update DATA_CONTRACT.md section {record.target_section!r} "
            "to match the code-owned persisted data contract."
        ),
        anchor=f"data-contract-{record.owner}-{field}".lower().replace("_", "-"),
        confidence="supported",
    )


def _collect_data_contract_drift(repo_root: Path) -> tuple[list, dict]:
    """Return data-contract drift as recommendations plus apply payloads.

    Step 1 owns the registry and record shape. This adapter only compares the
    registry to the checked-in ``DATA_CONTRACT.md`` so completeness audits can
    report the same drift without duplicating contract ownership.
    """
    from plan_tool import data_contract as contract

    doc_path = _data_contract_doc_path(repo_root)
    if not doc_path.is_file():
        return [], {}
    contract_text = doc_path.read_text(encoding="utf-8")
    records = []

    for item in contract.persisted_dataclass_contracts():
        section = _data_contract_section(contract_text, item.section_title)
        if section is None:
            records.append(
                contract.make_drift_record(
                    source_type="dataclass",
                    owner=item.owner,
                    field_or_key=item.section_title,
                    target_section=item.section_title,
                    operation="add",
                    contract_text=contract_text,
                    candidate={
                        "source_symbol": item.source_symbol,
                        "fields": list(item.field_names),
                        "json_keys": list(item.persisted_json_keys),
                    },
                )
            )
            continue
        documented = _data_contract_documented_fields(section)
        excluded = {entry.field_or_key for entry in item.intentional_exclusions}
        for name in item.field_names:
            if name in excluded:
                continue
            if name in item.in_memory_only:
                # Owned by the dedicated in-memory-only check below, which emits
                # an in-memory-aware record; avoids a duplicate "add" here.
                continue
            if f"`{name}`" not in section:
                records.append(
                    contract.make_drift_record(
                        source_type="dataclass",
                        owner=item.owner,
                        field_or_key=name,
                        target_section=item.section_title,
                        operation="add",
                        contract_text=contract_text,
                        candidate={
                            "source_symbol": item.source_symbol,
                            "field": name,
                            "json_key": item.json_key_aliases.get(name, name),
                        },
                    )
                )
        for field_name, json_key in item.json_key_aliases.items():
            if f"`{field_name}`" in section and f"`{json_key}`" not in section:
                records.append(
                    contract.make_drift_record(
                        source_type="dataclass",
                        owner=item.owner,
                        field_or_key=json_key,
                        target_section=item.section_title,
                        operation="update",
                        contract_text=contract_text,
                        candidate={
                            "source_symbol": item.source_symbol,
                            "field": field_name,
                            "json_key": json_key,
                            "requirement": "json_key_alias",
                        },
                    )
                )
        lower_section = section.lower()
        for name in item.in_memory_only:
            if f"`{name}`" not in section or "in-memory" not in lower_section:
                records.append(
                    contract.make_drift_record(
                        source_type="dataclass",
                        owner=item.owner,
                        field_or_key=name,
                        target_section=item.section_title,
                        operation="update",
                        contract_text=contract_text,
                        candidate={
                            "source_symbol": item.source_symbol,
                            "field": name,
                            "requirement": "in_memory_only",
                        },
                    )
                )
        for constant in item.schema_constants:
            if constant not in section:
                records.append(
                    contract.make_drift_record(
                        source_type="dataclass",
                        owner=item.owner,
                        field_or_key=constant,
                        target_section=item.section_title,
                        operation="add",
                        contract_text=contract_text,
                        candidate={
                            "source_symbol": item.source_symbol,
                            "schema_constant": constant,
                            "requirement": "schema_constant",
                        },
                    )
                )
        for stale in sorted(documented - item.accepted_documented_fields):
            records.append(
                contract.make_drift_record(
                    source_type="dataclass",
                    owner=item.owner,
                    field_or_key=stale,
                    target_section=item.section_title,
                    operation="remove",
                    contract_text=contract_text,
                    candidate={
                        "source_symbol": item.source_symbol,
                        "field": stale,
                    },
                )
            )

    for item in contract.json_object_contracts():
        section = _data_contract_section(contract_text, item.section_title)
        values = item.path_labels + item.keys + item.required_phrases
        if section is None:
            missing = list(values)
        else:
            missing = [value for value in values if value not in section]
        for value in missing:
            records.append(
                contract.make_drift_record(
                    source_type="json_object",
                    owner=item.owner,
                    field_or_key=value,
                    target_section=item.section_title,
                    operation="add",
                    contract_text=contract_text,
                    candidate={
                        "source_symbol": item.source_symbol,
                        "key_or_phrase": value,
                        "path_labels": list(item.path_labels),
                    },
                )
            )
        if section is not None:
            for constant in item.schema_constants:
                if constant not in section:
                    records.append(
                        contract.make_drift_record(
                            source_type="json_object",
                            owner=item.owner,
                            field_or_key=constant,
                            target_section=item.section_title,
                            operation="add",
                            contract_text=contract_text,
                            candidate={
                                "source_symbol": item.source_symbol,
                                "schema_constant": constant,
                                "requirement": "schema_constant",
                            },
                        )
                    )

    registered = {item.owner for item in contract.persisted_dataclass_contracts()}
    for owner in sorted(
        _data_contract_obsolete_dataclass_sections(contract_text, registered)
    ):
        records.append(
            contract.make_drift_record(
                source_type="dataclass",
                owner=owner,
                field_or_key=owner,
                target_section=owner,
                operation="remove",
                contract_text=contract_text,
                candidate={"owner": owner},
            )
        )

    recs = []
    payloads = {}
    for record in records:
        rec = _data_contract_rec_for_record(record)
        recs.append(rec)
        payloads[rec.id] = _data_contract_record_payload(record)
    return recs, payloads


def _input_contract_issue_payload(issue) -> dict:
    return {
        "target": "plan-detail",
        "location": issue.location,
        "owner": issue.owner,
        "field_or_key": issue.field_or_key,
        "code_anchor": issue.code_anchor,
        "reason": issue.reason,
        "step_id": issue.step_id,
        "path": issue.path,
        "operation": "validate-input-reference",
    }


def derive_audit_stage(status) -> str:
    """Closed audit stage ``bare`` | ``detail`` from bundle status (Architecture table).

    ``total == 0`` is bare before ``is_fully_bare`` / otherwise detail — never
    ``status.is_bare`` alone (step-less plans have ``is_bare`` false).
    """
    from plan_tool.convergence import STAGE_BARE, STAGE_DETAIL

    if status.total == 0:
        return STAGE_BARE
    if status.is_fully_bare:
        return STAGE_BARE
    return STAGE_DETAIL


def write_pre_apply_audit_checkpoint(
    plan,
    path: Path,
    ctx,
    args,
    *,
    audit_recs: list,
    budget: dict,
    bundle_status,
    code_drifted: bool = False,
    audit_shape_advisory=None,
    audit_input_snapshot=None,
    audit_stage: Optional[str] = None,
    resumed_from_sampler_checkpoint: bool = False,
) -> Optional[Path]:
    """Persist the conceptual audit before the iterate apply loop starts.

    Writes the JSON sidecar + markdown report so a later crash during
    ``apply_finding`` does not discard the expensive audit pass. This is the
    one producer of a pre-apply checkpoint sidecar, so it is the one call that
    requests the checkpoint role — iterate mode alone does not classify a
    report, since the final report of an iterative run is written by the same
    tail with the role left at its final default.
    """
    from plan_tool.review_persistence import normalize_audit_coverage

    normalized_audit_coverage = normalize_audit_coverage(budget)
    correctness_recs = [r for r in audit_recs if r.source == "plan-correctness"]
    conceptual_recs = [r for r in audit_recs if r.source == "plan-completeness"]
    det = _run_deterministic_checks(
        plan, path, ctx, plan_name=args.name, quiet=True,
    )
    from plan_tool.completeness_report import prepare_audit_shape_advisory_display

    advisory_display = prepare_audit_shape_advisory_display(
        audit_shape_advisory,
        plan=plan,
        plan_path=path,
        repo_root=ctx.repo_root,
    )
    grouped_md = _render_grouped_report(
        plan, args, det,
        correctness_recs=correctness_recs,
        conceptual_recs=conceptual_recs,
        audit_recs=audit_recs,
        iterate_enabled=True,
        bundle_status=bundle_status,
        budget=normalized_audit_coverage,
        audit_shape_advisory_display=advisory_display,
        resumed_from_sampler_checkpoint=resumed_from_sampler_checkpoint,
        is_pre_apply_checkpoint=True,
    )
    outcome = _IterateOutcome(
        stop_reason="pre-apply checkpoint",
        audit_recs=list(audit_recs),
        plan=plan,
        budget=budget,
        audit_input_snapshot=audit_input_snapshot,
        audit_stage=audit_stage,
        resumed_from_sampler_checkpoint=resumed_from_sampler_checkpoint,
    )
    return _persist_and_present_report(
        plan, path, args, ctx,
        iterate_enabled=True,
        outcome=outcome,
        correctness_recs=correctness_recs,
        conceptual_recs=conceptual_recs,
        grouped_md=grouped_md,
        smell_recs=det.smell_recs,
        data_contract_recs=det.data_contract_recs,
        data_contract_payloads=det.data_contract_payloads,
        code_drifted=code_drifted,
        quiet_presentation=True,
        suppress_plan_mass=True,
        bundle_status=bundle_status,
        audit_shape_advisory=audit_shape_advisory,
        audit_shape_advisory_display=advisory_display,
        audit_coverage=normalized_audit_coverage,
        is_pre_apply_checkpoint=True,
        audit_input_snapshot=audit_input_snapshot,
        audit_stage=audit_stage,
    )


# Per-step purity call timeout. Observed successful purity returns run
# ~230–300s on current prompt sizes; authoring against the same bundles can
# take ~690s. 900s is the floor so a slow-but-working scan isn't killed.
PURITY_CLAUDE_TIMEOUT_S = 900.0
CONCEPTUAL_AUDIT_CLAUDE_TIMEOUT_S = 1_800.0
PURITY_SCAN_BUDGET_S = 1_800.0

PURITY_CLAUDE_TIMEOUT_ENV = "PLAN_TOOL_PURITY_CLAUDE_TIMEOUT"
CONCEPTUAL_AUDIT_CLAUDE_TIMEOUT_ENV = "PLAN_TOOL_CONCEPTUAL_AUDIT_CLAUDE_TIMEOUT"
PURITY_SCAN_BUDGET_ENV = "PLAN_TOOL_PURITY_SCAN_BUDGET"

# Advisory source for the BACKLOG #144 below-floor reuse note. Kept distinct
# from ``granularity.GRANULARITY_SPLIT_SOURCE`` so it isn't read as a real split
# finding (nor caught by the medium-``granularity-split`` filter) and stays
# ``info`` — folded into the advisory ``smell_recs`` bucket, never blocking.
PURITY_REUSE_ADVISORY_SOURCE = "purity-reuse-advisory"

# Coverage error when a purity scan attempt produced no verdict (timeout,
# empty, or truncated reply). ``high`` + dedicated blocking bucket — not an
# advisory smell — so a failed battery cannot read as low-yield under #125.
# Stable per-step id so recurrence stays identity-stable across rounds.
PURITY_SCAN_FAILED_SOURCE = "purity-scan-failed"
PURITY_SCAN_SKIPPED_SOURCE = "purity-scan-skipped"


def _purity_scan_failed_finding(step) -> "Recommendation":
    """Stable ``high`` coverage error for a failed purity scan."""
    from plan_tool.review import Recommendation, _make_rec_id

    note = (
        f"purity scan failed for step {step.id} — no MIXED-STEP verdict; "
        "re-run with --purity (raise PLAN_TOOL_PURITY_CLAUDE_TIMEOUT if calls time out)"
    )
    return Recommendation(
        id=_make_rec_id(
            step.id, PURITY_SCAN_FAILED_SOURCE, f"purity-scan-failed-step-{step.id}"
        ),
        source=PURITY_SCAN_FAILED_SOURCE,
        severity="high",
        step_id=step.id,
        title=note,
        body=note,
    )


def _purity_scan_skipped_finding(step) -> "Recommendation":
    """Stable ``high`` coverage error for a scan skipped by the pass budget."""
    from plan_tool.review import Recommendation, _make_rec_id

    note = (
        f"purity scan skipped for step {step.id} — the full purity scan budget "
        "expired before it ran; re-run with --purity (raise "
        "PLAN_TOOL_PURITY_SCAN_BUDGET to cover more steps)"
    )
    return Recommendation(
        id=_make_rec_id(
            step.id, PURITY_SCAN_SKIPPED_SOURCE, f"purity-scan-skipped-step-{step.id}"
        ),
        source=PURITY_SCAN_SKIPPED_SOURCE,
        severity="high",
        step_id=step.id,
        title=note,
        body=note,
    )


def _step_has_readable_detail(step, repo_root: Path) -> bool:
    """True when the step has a non-empty detail file (a real scan can run)."""
    if not step.detail:
        return False
    path = repo_root / step.detail
    if not path.is_file():
        return False
    return bool(path.read_text(encoding="utf-8").strip())

# BACKLOG #144 magnitude floor: below this changed fraction on the concatenated
# ## Implementation + ## Tests text (and with no frontmatter/identity change) a
# purity cache miss is graded a trivial edit and the cached verdict is reused
# without a Claude call. Calibrated against local audit history — every trivial
# edit scored 0.000-0.004, every substantive one >= 0.018.
PURITY_REUSE_FLOOR = 0.005
# Absolute companion to the proportional floor: reuse requires BOTH a small
# fraction AND a small absolute edit. The proportional ratio scales with detail
# size, so on a very large step a real mixing edit can stay under 0.5%; the
# absolute cap (chars changed via SequenceMatcher opcodes) bounds that. Sized
# generously enough to still admit genuine trivial edits (a typo, a reworded
# sentence, a link ≈ tens of chars) while catching the "handful of lines" case.
PURITY_REUSE_ABS_FLOOR = 120


def _grade_purity_cache_miss(
    *,
    entry,
    step,
    current_components,
    current_detail_relpath,
    current_impl_tests_text,
) -> list | None:
    """Below-floor reuse hook for the audit path's purity cache miss (#144).

    On a miss the combined key has already moved, so grade the *components*
    (never the opaque key, which can't say which input changed): a genuine miss
    is any change to the step identity (``detail_relpath`` renumber guard) or a
    verdict-affecting component (``all_files_fingerprint`` — a ``files:``/
    ``creates:`` source edit; ``change_type``; ``depends_on``;
    ``purity_verdict_logic_version``), OR an Implementation/Tests change at or
    above the 0.5% floor. Any of those → return ``None`` so the helper computes
    a fresh verdict. A *trivial* miss (all components equal, Impl/Tests moved
    under the floor) reuses the cached verdict and mints one ``info`` advisory.
    """
    from difflib import SequenceMatcher

    from plan_tool.granularity import GRANULARITY_SPLIT_SOURCE
    from plan_tool.review import Recommendation, _make_rec_id

    # Frontmatter / identity OR — any component change is a genuine miss.
    if entry.detail_relpath != current_detail_relpath:  # renumber guard
        return None
    if entry.all_files_fingerprint != current_components.all_files_fingerprint:
        return None
    if entry.change_type != current_components.change_type:
        return None
    if sorted(entry.depends_on) != sorted(current_components.depends_on):
        return None  # sorted, matching the key's order-insensitive fold
    if entry.purity_verdict_logic_version != current_components.logic_version:
        return None

    # Fail-safe: if either side's Implementation/Tests text is empty, the diff
    # is unmeasurable (e.g. a heading variant _impl_tests_section_text couldn't
    # resolve, or a genuinely section-less detail). An empty↔empty compare would
    # score 0% and wrongly reuse; treat it as a genuine miss and re-check.
    if not entry.impl_tests_text.strip() or not current_impl_tests_text.strip():
        return None

    # Magnitude signal: ``SequenceMatcher.ratio()`` is *similarity* (1.0 =
    # identical), so the changed fraction is ``1 - ratio()``. Trivial only when
    # it stays under the floor — comparing ``ratio()`` directly would invert it.
    matcher = SequenceMatcher(
        None, entry.impl_tests_text, current_impl_tests_text
    )
    changed_fraction = 1 - matcher.ratio()
    # Absolute changed-char count from the opcodes (max of the two spans per
    # non-equal block), the size-independent companion to the proportional floor.
    changed_chars = sum(
        max(i2 - i1, j2 - j1)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes()
        if tag != "equal"
    )
    if changed_fraction >= PURITY_REUSE_FLOOR or changed_chars >= PURITY_REUSE_ABS_FLOOR:
        return None

    # Two decimals: this branch only fires below the 0.5% floor, so a plain
    # round()-to-int would print "changed 0%" for a real sub-1% edit.
    changed_pct = round(changed_fraction * 100, 2)
    note = (
        f"purity reused for step {step.id} — changed {changed_pct}% of "
        "Implementation/Tests, below the re-check floor"
    )
    advisory = Recommendation(
        # Stable per-step fingerprint (NOT the volatile M%-bearing body): the id
        # hashes its fingerprint, so folding M% in would churn the id every pass
        # and read as a new finding, inflating recurrence/low-yield counters.
        id=_make_rec_id(
            step.id, PURITY_REUSE_ADVISORY_SOURCE, f"purity-reuse-step-{step.id}"
        ),
        source=PURITY_REUSE_ADVISORY_SOURCE,
        severity="info",
        step_id=step.id,
        title=note,
        body=note,
    )
    return [
        dc.replace(finding, purity_verdict_provenance="below-floor-reuse")
        if finding.source == GRANULARITY_SPLIT_SOURCE
        else finding
        for finding in entry.findings
    ] + [advisory]


def _collect_purity_split_findings(
    plan, path, ctx, *, plan_name: str
) -> list:
    """Per-step Claude purity judgment: the ``medium`` MIXED-STEP
    ``granularity-split`` findings the deterministic detectors can't produce.

    Routes through ``detail._cached_purity_findings`` in ``read_through=True``
    (audit) mode — the cache boundary around
    ``detail.collect_detail_quality_findings``, the one producer that renders
    the detail-quality prompt, invokes claude through a patchable seam, and
    lifts the ``## Structural findings`` block via ``parse_mixed_step_findings``.
    An unchanged step reuses its cached purity verdict and skips the Claude
    call; a *trivially*-changed step (below BACKLOG #144's Impl/Tests floor with
    no frontmatter/identity change, graded by ``_grade_purity_cache_miss``)
    reuses too and adds one ``info`` reuse advisory, still no Claude; a genuine
    miss calls Claude and writes the verdict back. This keeps the ``medium``
    ``granularity-split`` recs (``source`` + ``severity`` + ``step_id`` come
    from that kernel; not re-minted here) plus the reuse advisory. Its quiet probe
    returns ``[]``
    before any claude call for a step with no ``detail`` pointer or a
    missing/empty file, so a bare plan spends nothing; non-code steps are
    dropped inside ``parse_mixed_step_findings``. Done steps are skipped —
    an already-built step is not a split candidate. The body-local ``detail``
    import keeps the edge acyclic (``detail`` doesn't import this module) and
    lets the suites patch ``plan_tool.detail.collect_detail_quality_findings``.
    """
    from plan_tool import detail as detail_mod
    from plan_tool.granularity import GRANULARITY_SPLIT_SOURCE
    from plan_tool.progress import StderrReporter
    from plan_tool.schema import ChangeType, StepStatus
    from plan_tool.shell import resolve_claude_timeout, scoped_claude_timeout

    # Per-step heartbeat: without a reporter this loop's Claude call is silent
    # (`collect_detail_quality_findings` takes the bare-`invoker` branch), so a
    # hung backend child shows no output at all. A StderrReporter lights up the
    # "⋯ step N · Ns elapsed" ticker, naming the step a stall is stuck on.
    reporter = StderrReporter()

    per_call_timeout = resolve_claude_timeout(
        PURITY_CLAUDE_TIMEOUT_S, setting=PURITY_CLAUDE_TIMEOUT_ENV
    )
    scan_budget = resolve_claude_timeout(
        PURITY_SCAN_BUDGET_S,
        setting=PURITY_SCAN_BUDGET_ENV,
        legacy_setting=None,
    )
    scan_started_at = time.monotonic()
    out: list = []
    for step in plan.steps:
        if step.status == StepStatus.DONE:
            continue
        if step.change_type == ChangeType.NON_CODE:
            continue
        readable_detail = _step_has_readable_detail(step, ctx.repo_root)

        remaining = None
        if scan_budget is not None:
            remaining = scan_budget - (time.monotonic() - scan_started_at)
            if remaining <= 0:
                if readable_detail:
                    out.append(_purity_scan_skipped_finding(step))
                    continue
                # Let the existing quiet probe keep its no-detail behavior.
                remaining = None

        # Bound each admitted scan. The pass budget clamps the per-call scope,
        # so an in-flight subprocess cannot extend beyond the whole battery.
        call_timeout = per_call_timeout
        if remaining is not None:
            call_timeout = (
                remaining
                if call_timeout is None
                else min(call_timeout, remaining)
            )
        # Audit path: read through the purity cache — an unchanged step reuses
        # its cached verdict and skips the backend call; a genuine miss calls
        # Claude and writes the verdict back. The scope still applies if the
        # cache boundary needs to invoke the backend.
        with scoped_claude_timeout(call_timeout):
            recs, succeeded = detail_mod._cached_purity_findings(
                path, step,
                repo_root=ctx.repo_root,
                plan_name=plan_name,
                invoker=detail_mod.shell_detail_invoker,
                read_through=True,
                reporter=reporter,
                below_floor_reuse=_grade_purity_cache_miss,
                return_status=True,
            )
        # Keep the medium purity verdict and the below-floor reuse advisory;
        # drop grounding recs. The scan-failed coverage finding is appended
        # below, not returned from the cache boundary.
        has_mixed_verdict = any(
            r.source == GRANULARITY_SPLIT_SOURCE and r.severity == "medium"
            for r in recs
        )
        out.extend(
            r for r in recs
            if (r.source == GRANULARITY_SPLIT_SOURCE and r.severity == "medium")
            or r.source == PURITY_REUSE_ADVISORY_SOURCE
        )
        # Failed scan with a readable detail and no MIXED-STEP verdict:
        # coverage error. A truncated reply that still lifted a medium split
        # already has a verdict, so do not also claim coverage failed.
        if not succeeded and not has_mixed_verdict and readable_detail:
            out.append(_purity_scan_failed_finding(step))
    return out


def _granularity_findings(det_ctx) -> list:
    """The cross-step granularity advisor's recs (split/merge heuristics).

    Its own registry entry rather than a call inside the battery: the advisor
    lives in ``plan_tool.granularity``, which imports ``review`` at module
    load, so its table can't sit beside the review-owned ones. ``invoker=None``
    keeps it no-claude; the body-local import lets the suites patch
    ``plan_tool.granularity.assess_granularity``.
    """
    from plan_tool.granularity import GranularityEvidence, assess_granularity

    return assess_granularity(
        det_ctx.plan,
        stage="completeness",
        evidence=GranularityEvidence(),
        invoker=None,
    )


def _unfiltered_battery_detectors():
    """Return detector tables before and after the smell/self-consistency fan-outs."""
    from plan_tool.review import (
        DetectorEntry,
        DetectorRegistry,
        INPUT_CONTRACT_DETECTORS,
        PLAN_WELL_FORMEDNESS_DETECTORS,
    )

    granularity = DetectorRegistry(
        (
            DetectorEntry(
                "granularity",
                lambda det_ctx, results: _granularity_findings(det_ctx),
            ),
        )
    )
    data_contract = DetectorRegistry(
        (
            DetectorEntry(
                "data-contract-drift",
                lambda det_ctx, results: _collect_data_contract_drift(
                    det_ctx.repo_root
                ),
                # Compares the code-owned registry to DATA_CONTRACT.md; the
                # plan's detail bundle is not an input.
            ),
        )
    )
    return (
        PLAN_WELL_FORMEDNESS_DETECTORS.chain(granularity),
        data_contract.chain(INPUT_CONTRACT_DETECTORS),
    )


def _battery_detectors():
    """Return the retained detector tables in their established call order."""
    pre, post = _unfiltered_battery_detectors()
    return pre, post


def all_deterministic_detectors():
    """Return every retained deterministic detector in call order."""
    from plan_tool.review import (
        SELF_CONSISTENCY_DETECTORS,
        SMELL_DETECTORS,
    )

    pre, post = _unfiltered_battery_detectors()
    return pre.chain(SMELL_DETECTORS, SELF_CONSISTENCY_DETECTORS, post)


def deterministic_detector_registry():
    """Return the complete run-grade deterministic detector registry."""
    return all_deterministic_detectors()


def _run_deterministic_checks(
    plan, path, ctx, *, plan_name: str, quiet: bool, run_purity: bool = False,
) -> _DeterministicReport:
    """Run the deterministic well-formedness battery and bundle its seven
    issue lists plus the advisory smell bucket.

    Every detector is reached through :func:`deterministic_detector_registry`,
    never a hard-coded call, so one can be admitted or skipped on its own
    (``TestDeterministicDetectorRegistry`` fails the build on a direct call).
    The registry runs in the battery's established order: correctness
    primitives (file existence, path-style detection, dep validation) BEFORE
    completeness primitives (body sections, detail coverage, detail bodies,
    files coherence, lessons) so structural blockers surface ahead of
    authoring gaps. The advisory smell fan-out (``collect_smell_findings``)
    runs after: those findings are surfaced in the report but, by living only
    here (never in ``review.collect_deterministic_findings``), never enter the
    ``--iterate`` apply loop. ``plan_name`` lets the smell collector mint
    stable rec ids via ``review._make_rec_id`` (same contract
    ``collect_deterministic_findings`` uses). None of these detectors is
    monkeypatched in the suites except via the domain module
    (``plan_tool.review``), so each entry resolves its detector at call time —
    a patch on the domain module is honored. ``quiet`` (set under --iterate,
    which narrates its own progress) suppresses the audit-only ``[1/2]``
    banner and the deterministic-count tail.

    ``run_purity`` opts in the one claude-judged pass in this phase: a
    per-step MIXED-STEP purity judgment (``_collect_purity_split_findings``)
    that folds ``medium`` ``granularity-split`` recs into the advisory
    ``smell_recs`` bucket and purity coverage errors (failed or budget-skipped
    scans) into the blocking ``purity_coverage_recs`` bucket. It is a dedicated flag,
    not ``quiet``: the main audit passes ``run_purity=True`` while the pre-apply
    checkpoint (``write_pre_apply_audit_checkpoint``) passes ``False`` so the
    purity pass fires at most once per audit — both call sites are ``quiet``
    under ``--iterate``, so ``quiet`` can't tell them apart. The registry's
    detectors stay no-claude regardless.
    """
    from plan_tool.review import (
        DetectorContext,
        collect_smell_findings,
        SELF_CONSISTENCY_SOURCES,
        _input_contract_reference_recommendation,
        _self_consistency_from_smells,
    )

    if not quiet:
        if run_purity:
            # The deterministic battery stays no-claude; the per-step purity
            # pass below is the one claude call this phase makes.
            print(
                "plan-tool: [1/2] deterministic well-formedness checks "
                "(sections, files, deps, lessons; no claude) + per-step "
                "mixed-refactor purity check (claude)…",
                file=sys.stderr,
            )
        else:
            print(
                "plan-tool: [1/2] deterministic well-formedness checks "
                "(sections, files, deps, lessons; no claude)…",
                file=sys.stderr,
            )

    det_ctx = DetectorContext(
        plan=plan,
        repo_root=ctx.repo_root,
        plan_name=plan_name,
        plan_path=path,
    )
    pre_detectors, post_detectors = _battery_detectors()

    # 1) Correctness primitives, then completeness primitives. ``plan_path``
    # rides in on the context, so the detail checks judge a step whose
    # ``detail:`` pointer is unset but whose canonical file is on disk — the
    # same set the audit prompt's detail bundle renders.
    detector_results = pre_detectors.run_all(det_ctx)
    path_style_hint = detector_results["path-style-mismatch"]
    dep_issues = detector_results["deps"]
    body_issues = detector_results["body-completeness"]
    detail_cov_issues = list(detector_results.get("detail-coverage", []))
    detail_body_issues = list(
        detector_results.get("detail-body-completeness", [])
    )
    files_coh_issues = detector_results.get("files-coherence", [])
    lessons_issues = detector_results["lessons-coverage"]

    # 2) Advisory smells — surfaced in the report only. Deliberately left
    # out of the deterministic-count tail below: smells are advisory and
    # should not inflate the well-formedness finding count. The cross-step
    # granularity advisor folds its recs into the same bucket — one render
    # path, and the bucket is never an input to
    # ``_completeness_has_blocking_findings``, so granularity advice surfaces
    # everywhere yet never flips the rc.
    granularity_recs = detector_results["granularity"]
    smell_recs = collect_smell_findings(
        plan, ctx.repo_root, plan_name=plan_name, plan_path=path,
    ) + granularity_recs
    # The one claude-judged addition: per-step MIXED-STEP purity findings.
    # Gated off ``run_purity`` (not ``quiet``) so it fires once per audit,
    # never from the checkpoint. Medium ``granularity-split`` + reuse advisories
    # stay in the advisory smell bucket; ``purity-scan-failed`` coverage errors
    # partition into the blocking ``purity_coverage_recs`` bucket.
    purity_coverage_recs: list = []
    if run_purity:
        purity_recs = _collect_purity_split_findings(
            plan, path, ctx, plan_name=plan_name
        )
        purity_coverage_recs = [
            r
            for r in purity_recs
            if r.source in {
                PURITY_SCAN_FAILED_SOURCE,
                PURITY_SCAN_SKIPPED_SOURCE,
            }
        ]
        smell_recs = smell_recs + [
            r
            for r in purity_recs
            if r.source not in {
                PURITY_SCAN_FAILED_SOURCE,
                PURITY_SCAN_SKIPPED_SOURCE,
            }
        ]
    # Blocking-capable self-consistency battery: every ``medium``
    # ``SELF_CONSISTENCY_SOURCES`` rec partitioned off ``smell_recs`` (so they gate
    # at ``medium``+ instead of riding the advisory bucket) + the plan-altitude
    # ``orphaned-deliverable`` check, both owned by ``_self_consistency_from_smells``
    # so the ``--iterate`` loop's blocking signal (``collect_self_consistency_findings``)
    # draws from identical membership and can't diverge from this gate. Partitioned
    # after the ``run_purity`` fold (keying on source leaves ``granularity-split``
    # untouched); stays out of the advisory ``smell_recs`` bucket and ``_det_total``.
    self_consistency_recs = _self_consistency_from_smells(
        smell_recs, plan, ctx.repo_root, plan_name=plan_name, plan_path=path,
    )
    smell_recs = [
        r for r in smell_recs if r.source not in SELF_CONSISTENCY_SOURCES
    ]
    # ``post_detectors`` (data-contract-drift + both input-contract entries)
    # all transitively call ``data_contract.persisted_dataclass_contracts()``,
    # which resolves ~26 classes across nine modules by live attribute access
    # with no guard. A transient ``AttributeError`` there — observed when the
    # installed binary raced a concurrent edit to this repo's working tree —
    # would otherwise take the whole deterministic battery down with it, even
    # though every other detector already ran cleanly. Caught narrowly (this
    # exception class only) and reported rather than swallowed, matching the
    # ``could not write completeness report`` precedent below. See RUNBOOK.md
    # § "Repair data-contract docs" (concurrent-editing hazard).
    try:
        detector_results.update(post_detectors.run_all(det_ctx))
    except AttributeError as exc:
        warn(
            "data-contract/input-contract checks crashed and were skipped "
            f"for this run: {exc!r}. This is expected only if something else "
            "was concurrently editing this repo's working tree; re-run "
            "completeness-audit against a quiescent tree to confirm."
        )
        for key in post_detectors.keys:
            detector_results.setdefault(
                key, ([], {}) if key == "data-contract-drift" else []
            )
    data_contract_recs, data_contract_payloads = detector_results[
        "data-contract-drift"
    ]
    # Check plan-body input contracts before per-step input contracts.
    input_contract_issues = list(
        detector_results.get("input-contract-references-plan", [])
    ) + list(detector_results.get("input-contract-references-steps", []))
    for issue in input_contract_issues:
        rec = _input_contract_reference_recommendation(issue)
        data_contract_recs.append(rec)
        data_contract_payloads[rec.id] = _input_contract_issue_payload(issue)
    # Decision telemetry (#72, best-effort): record what the granularity advisor
    # saw so its thresholds can be tuned from the distribution over time.
    from plan_tool.granularity import (
        GRANULARITY_MERGE_SOURCE,
        GRANULARITY_SPLIT_SOURCE,
    )
    from plan_tool.review_persistence import compute_plan_fingerprint
    from plan_tool.telemetry import record_granularity

    # plan_fingerprint only: this event is about plan structure, and the map is
    # not in hand here. code_fingerprint stays at its None default — it fires
    # every --iterate round, so re-hashing the footprint per round is forbidden.
    try:
        _gran_plan_fp = compute_plan_fingerprint(path)
    except Exception:
        _gran_plan_fp = ""
    record_granularity(
        ctx.repo_root,
        plan_slug=plan_name,
        stage="completeness",
        steps=len(plan.steps),
        split=sum(1 for r in granularity_recs if r.source == GRANULARITY_SPLIT_SOURCE),
        merge=sum(1 for r in granularity_recs if r.source == GRANULARITY_MERGE_SOURCE),
        plan_fingerprint=_gran_plan_fp,
    )

    if not quiet:
        _det_total = (
            (1 if path_style_hint is not None else 0)
            + len(dep_issues)
            + len(body_issues)
            + len(detail_cov_issues)
            + len(detail_body_issues)
            + len(files_coh_issues)
            + len(lessons_issues)
            + len(data_contract_recs)
            + len(purity_coverage_recs)
        )
        print(
            f"plan-tool: deterministic checks done · "
            f"{_det_total} finding(s)",
            file=sys.stderr,
        )

    return _DeterministicReport(
        path_style_hint=path_style_hint,
        dep_issues=dep_issues,
        body_issues=body_issues,
        detail_cov_issues=detail_cov_issues,
        detail_body_issues=detail_body_issues,
        files_coh_issues=files_coh_issues,
        lessons_issues=lessons_issues,
        smell_recs=smell_recs,
        self_consistency_recs=self_consistency_recs,
        data_contract_recs=data_contract_recs,
        data_contract_payloads=data_contract_payloads,
        purity_coverage_recs=purity_coverage_recs,
    )


def emit_bare_plan_banner(
    plan, plan_path, repo_root, *, bundle_status=None,
):
    """Print the bare-plan audit banner when ≥1 step lacks a detail file.

    A **bare plan** (some/all steps not yet `detail`-authored) is a valid
    early-pipeline audit target — but the operator must know the audit is
    plan-internal only, not detail/code-grounded, so a `converged` verdict
    isn't read as fully validated. No-op print for a fully-detailed plan.
    Returns the :class:`DetailBundleStatus` so callers can phrase the
    grounding line honestly (a fully-bare plan grounds on the plan body +
    code at HEAD, not the detail bundle). (BACKLOG #61.)
    """
    if bundle_status is None:
        from plan_tool.review import audit_detail_bundle_status

        status = audit_detail_bundle_status(
            plan, plan_path, repo_root
        )
    else:
        status = bundle_status
    if status.is_bare:
        kind = "bare" if status.is_fully_bare else "partially-detailed"
        print(
            "plan-tool: BARE-PLAN AUDIT — "
            f"{status.detailed_count} of {status.total} step(s) have a "
            f"detail file ({kind} plan). Auditing plan-internal consistency "
            "only; bare steps are judged at the concept level. Detail/code-"
            "grounded findings require a detail bundle.",
            file=sys.stderr,
        )
    return status


def emit_coverage_unconfirmed(budget) -> bool:
    """Print the conceptual-audit unconfirmed-coverage warning, if needed.

    A pass-cap stop and a typed terminal plan quota both leave coverage
    unconfirmed; generic failed passes retain their neutral pass behavior.
    """
    from plan_tool.review_persistence import (
        audit_coverage_withholds_final_findings_sidecar,
    )

    if audit_coverage_withholds_final_findings_sidecar(budget):
        stop = "early after a terminal plan quota"
    elif budget.get("budget_limited"):
        stop = "at the pass cap (still discovering)"
    else:
        return False
    print(
        "plan-tool: ⚠ COVERAGE UNCONFIRMED — conceptual sampling ended "
        f"{stop} at {budget.get('passes_used', '?')} pass(es). "
        "A clean/`converging` verdict here is not fully validated.",
        file=sys.stderr,
    )
    return True


def _sample_conceptual_audit(
    plan,
    path,
    ctx,
    *,
    max_passes: int,
    dry_rounds: int,
    budget_report=None,
    advisory_out=None,
    bundle_status=None,
    audit_input_snapshot=None,
    require_audit_input_snapshot: bool = False,
    resumed_from_checkpoint_out=None,
) -> list:
    """Run the conceptual audit against the captured run-grade bundle.

    The plan is read (and the repo at HEAD via Read/Grep) and judged on two
    axes — correctness (sound, internally consistent ideas) and
    completeness (no orphaned concepts, uncovered risks, dangling criteria
    the bundle doesn't resolve) — run for up to ``max_passes`` full audit
    passes until findings run dry, unioned by stable id. The body-local
    ``plan_tool.review`` import keeps ``shell_review_invoker`` /
    ``audit_plan_until_stable`` the monkeypatch seam the domain suites drive
    through ``main()``. Not called when the iterate loop already audited
    (the orchestrator reuses that result).
    """
    from plan_tool.review import (
        audit_plan_until_stable,
        plan_audit_invoker_from_review_invoker,
        shell_review_invoker,
    )
    from plan_tool.progress import StderrReporter
    from plan_tool.shell import resolve_claude_timeout, scoped_claude_timeout

    if resumed_from_checkpoint_out is not None:
        resumed_from_checkpoint_out[:] = [False]
    if require_audit_input_snapshot and audit_input_snapshot is None:
        return []

    emit_bare_plan_banner(
        plan, path, ctx.repo_root,
        bundle_status=bundle_status,
    )
    print(
        f"plan-tool: [2/2] conceptual audit via claude "
        f"(≤{max_passes} pass(es), stops after {dry_rounds} "
        f"dry round(s); each pass is one claude call and can "
        f"take several minutes)…",
        file=sys.stderr,
    )
    # Heartbeat per claude call — start line, ``Ns elapsed`` ticks,
    # done/FAILED — so the long calls show liveness. ``budget_report`` (when
    # the caller passes one) carries the budget verdict out for the report.
    budget = budget_report if budget_report is not None else {}
    captured_advisory: list = []
    conceptual_timeout = resolve_claude_timeout(
        CONCEPTUAL_AUDIT_CLAUDE_TIMEOUT_S,
        setting=CONCEPTUAL_AUDIT_CLAUDE_TIMEOUT_ENV,
    )
    sampler_resumed: list[bool] = []
    with scoped_claude_timeout(conceptual_timeout):
        recs = audit_plan_until_stable(
            plan, path,
            repo_root=ctx.repo_root,
            invoker=plan_audit_invoker_from_review_invoker(
                shell_review_invoker
            ),
            max_passes=max_passes,
            dry_rounds=dry_rounds,
            reporter=StderrReporter(),
            budget_report=budget,
            advisory_out=captured_advisory,
            audit_input_snapshot=audit_input_snapshot,
            resumed_out=sampler_resumed,
        )
    if advisory_out is not None:
        advisory_out[:] = captured_advisory or [None]
    if resumed_from_checkpoint_out is not None:
        resumed_from_checkpoint_out[:] = [
            bool(sampler_resumed and sampler_resumed[0])
        ]
    # Decision telemetry (#72, best-effort): passes spent + whether coverage was
    # budget-limited + findings/size — the data to tune the static pass count.
    from plan_tool.locator import slug_from_filename
    from plan_tool.review_persistence import (
        audit_coverage_withholds_final_findings_sidecar,
        compute_plan_fingerprint,
    )

    if not audit_coverage_withholds_final_findings_sidecar(budget):
        emit_coverage_unconfirmed(budget)
    from plan_tool.telemetry import record_audit_coverage

    # plan_fingerprint only: this event is about audit coverage, not code state,
    # and fires every --iterate round — carrying the code map would re-hash the
    # footprint per round. Best-effort so a compute error can't perturb the rc.
    try:
        _cov_plan_fp = compute_plan_fingerprint(path)
    except Exception:
        _cov_plan_fp = ""
    record_audit_coverage(
        ctx.repo_root,
        plan_slug=slug_from_filename(path) or "",
        passes=int(budget.get("passes_used", 0) or 0),
        budget_limited=bool(budget.get("budget_limited", False)),
        early_stop_reason=budget.get("early_stop_reason"),
        findings=len(recs),
        steps=len(plan.steps),
        plan_fingerprint=_cov_plan_fp,
    )
    return recs


def _sampled_bundle_status(audit_input_snapshot) -> DetailBundleStatus:
    """Project captured detail states into the shared stage-status model.

    The sampled stage must identify the plan/detail bytes shown to the audit,
    not whichever artifacts happen to be on disk after an iteration changes
    them. A captured ``present`` detail is detailed; missing and unreadable
    captures remain bare for the audit's grounding status.
    """
    from plan_tool.review import DetailBundleStatus

    detailed_step_ids = tuple(
        detail.step_id
        for detail in audit_input_snapshot.details
        if detail.state == "present"
    )
    bare_step_ids = tuple(
        detail.step_id
        for detail in audit_input_snapshot.details
        if detail.state != "present"
    )
    return DetailBundleStatus(
        total=len(audit_input_snapshot.plan.steps),
        detailed_step_ids=detailed_step_ids,
        bare_step_ids=bare_step_ids,
    )


def _fmt_finding_counts(recs) -> str:
    """One-line severity breakdown of a finding list, e.g.
    ``2 critical, 1 high, 3 medium``. Zero buckets are dropped; an
    empty list renders ``no findings``."""
    from collections import Counter

    counts = Counter(r.severity.lower() for r in recs)
    order = ("critical", "high", "medium", "low", "nit", "info")
    parts = [f"{counts[s]} {s}" for s in order if counts.get(s)]
    return ", ".join(parts) if parts else "no findings"


def _sc_manual_fix_note(sc_recs) -> str:
    """Honest terminal note for open self-consistency blocking findings.

    They are non-auto-appliable (not ``apply_finding``
    targets — the fix is a manual plan edit). Phrased so it neither reads as
    "converged" nor claims these are the *only* blockers: under
    ``--fail-on-findings`` any blocking finding gates, so the report is the
    source of truth for the full set. See BUG_BACKLOG."""
    srcs = ", ".join(sorted({r.source for r in sc_recs}))
    return (
        f"{len(sc_recs)} self-consistency blocking finding(s) ({srcs}) require "
        f"a manual plan edit (not auto-appliable). Under --fail-on-findings any "
        f"blocking finding exits non-zero; see the completeness report for the "
        f"full set."
    )


def _finding_progress_label(rec) -> str:
    """Short, scannable label for one finding's progress line:
    ``<source>/<severity> [confidence: value]: <title>`` (title trimmed by
    the reporter)."""
    return (
        f"{rec.source}/{rec.severity} [{confidence_label(rec.confidence)}]: "
        f"{rec.title.strip()}"
    )


def _resolution_for_verdict(verdict: str) -> tuple[str, str]:
    """Map an ``apply_finding`` verdict to a carried-finding ``(resolution,
    reason)`` tuple. The reason carries the exact verdict so a
    ``BLOCKED-STRUCTURAL`` block stays distinguishable downstream.

    This is the live apply path that makes ``CARRIED_RESOLUTION_BLOCKED``
    reachable — saved annotations only ever carry applied / skip / open
    (``carried_resolution_from_annotations``), never blocked.
    """
    from plan_tool.review import (
        CARRIED_RESOLUTION_APPLIED,
        CARRIED_RESOLUTION_BLOCKED,
        CARRIED_RESOLUTION_OPEN,
        CARRIED_RESOLUTION_SKIPPED,
    )

    if verdict == "APPLIED":
        return (CARRIED_RESOLUTION_APPLIED, "")
    if verdict in ("BLOCKED", "BLOCKED-STRUCTURAL"):
        return (CARRIED_RESOLUTION_BLOCKED, verdict)
    if verdict == "NOT-APPLICABLE":
        return (CARRIED_RESOLUTION_SKIPPED, verdict)
    # UNKNOWN (or any unrecognized verdict): the apply result is untrusted,
    # so no deliberate choice was made — stay retry-neutral (open).
    return (CARRIED_RESOLUTION_OPEN, verdict)


def _effective_audit_passes(args) -> int:
    """The number of conceptual-audit passes the audit actually runs with.

    Each pass is a full, independent audit over the whole plan + code at
    HEAD; extra passes re-roll the LLM's non-determinism rather than cover
    more of the plan, so the count does not scale with plan size. An
    explicit ``--audit-passes N`` (``dest=audit_passes``, also reachable via
    the deprecated ``--audit-samples`` alias) always wins; otherwise (the
    ``None`` sentinel the reuse decision reads as "not passed explicitly")
    the default is a static ``3``."""
    val = getattr(args, "audit_passes", None)
    if val is not None:
        return val
    return 3


def _coverage_input_from_reusable_audit(coverage) -> dict:
    """Adapt the reusable audit's public coverage projection for old sinks.

    ``ReusableAudit`` deliberately exposes the public known-or-unknown
    shape, including ``evidence_status``.  The established renderer and
    checkpoint interfaces predate that projection and consume the producer
    shape instead.  This is an exact unwrap of observed evidence, not a new
    coverage verdict; an unknown legacy result remains the explicit empty
    marker that those sinks render as unknown rather than clean.
    """
    if not isinstance(coverage, dict):
        return {}
    if coverage.get("evidence_status") != "observed":
        return {}
    unwrapped = {
        "budget_limited": coverage.get("budget_limited"),
        "passes_used": coverage.get("passes_used"),
        "cap": coverage.get("cap"),
        "recommendation_kind": coverage.get("recommendation_kind"),
        "recommended_passes": coverage.get("recommended_passes"),
        "recommendation_advice": coverage.get("recommendation_advice"),
        "confirmation_kind": coverage.get("confirmation_kind"),
        "conforming_pass_count": coverage.get("conforming_pass_count"),
        "failed_or_malformed_pass_count": coverage.get(
            "failed_or_malformed_pass_count"
        ),
    }
    if "early_stop_reason" in coverage:
        unwrapped["early_stop_reason"] = coverage["early_stop_reason"]
    return unwrapped


def compute_conceptual_bar_blocking_ids(
    recs,
    *,
    audit_stage: str,
    classify_domain=None,
) -> tuple[str, ...]:
    """Return stable ids where the stage bar blocks on conceptual findings.

    ``classify_domain`` is supplied unconditionally regardless of stage --
    the stage-differentiated treatment lives inside ``is_blocking_finding``
    itself, not here.
    """
    from plan_tool.convergence import CONCEPTUAL_SOURCES, is_blocking_finding
    from plan_tool.review import classify_finding_domain

    domain_fn = (
        classify_domain if classify_domain is not None else classify_finding_domain
    )
    blocking = [
        rec.id
        for rec in recs
        if rec.source in CONCEPTUAL_SOURCES
        and is_blocking_finding(rec, stage=audit_stage, classify_domain=domain_fn)
    ]
    return tuple(sorted(blocking))


def _conceptual_bar_from_audit_recs(
    recs,
    *,
    audit_stage: str,
    coverage,
) -> tuple[tuple[str, ...], bool]:
    """Compute bar-blocking ids and audit_incomplete from coverage + recs.

    ``audit_incomplete`` also covers ``budget_limited`` directly, not only
    ``audit_coverage_qualifies_sample``'s pass-conformance check: a
    still-discovering run ordinarily has every individual pass parse
    cleanly (``normalize_audit_coverage`` requires ``confirmation_kind is
    None`` whenever ``budget_limited`` is True, so conformance can never by
    itself indicate confirmation), and per DATA_CONTRACT.md ``budget_limited``
    alone already means "coverage is unconfirmed." Checking conformance only
    would let a well-formed but never-converged sample read as complete for
    the clean / ``--fail-on-findings`` CI-gating signal this feeds.
    ``audit_coverage_qualifies_sample`` stays conformance-only -- it is
    shared with ``_resolve_audit_reuse``, whose reuse-acceptance semantics
    are unrelated and must not change here.
    """
    from plan_tool.review_persistence import audit_coverage_qualifies_sample

    budget_limited = isinstance(coverage, dict) and bool(coverage.get("budget_limited"))
    audit_incomplete = budget_limited or not audit_coverage_qualifies_sample(coverage)
    if audit_incomplete:
        return (), True
    return (
        compute_conceptual_bar_blocking_ids(recs, audit_stage=audit_stage),
        False,
    )


# Halts on drift clear on a re-audit (each run takes a fresh drift baseline), so
# the verdict treats them as a retry; every other halt (a plan that fails to
# parse, a reverted edit, an unmatched fence) is reproduced by re-auditing.
HALT_PRE_APPLY_DRIFT = "pre-apply drift detected"
HALT_POST_APPLY_DRIFT = "post-apply drift detected"
HALT_DRIFT_REASONS = frozenset({HALT_PRE_APPLY_DRIFT, HALT_POST_APPLY_DRIFT})

_REMAP_STOP_FOR_CONCEPTUAL_BAR = frozenset({
    "converged",
    "no_blocking_findings",
    "all_auto_apply_findings_deferred",
})


def _remap_iterate_stop_for_conceptual_bar(
    candidate_reason: str | None,
    *,
    conceptual_bar_blocking_ids: tuple[str, ...],
    audit_incomplete: bool,
) -> str | None:
    """Remap leaf iterate exits when the stage bar still blocks conceptually."""
    if (
        candidate_reason in _REMAP_STOP_FOR_CONCEPTUAL_BAR
        and conceptual_bar_blocking_ids
        and not audit_incomplete
    ):
        return "terminal_hand_apply"
    return candidate_reason


def _conceptual_completeness_manual_fix_note(recs) -> str:
    """Honest terminal note for blocking conceptual completeness gaps."""
    return (
        f"{len(recs)} conceptual completeness gap(s) require a manual plan "
        f"or detail edit by the human or orchestrating session (not auto-appliable). "
        f"Read the completeness report for the "
        f"full set."
    )


def _split_conceptual_recs(recs) -> tuple[list, list]:
    """Split conceptual recs into (correctness, completeness) by source.

    ``CONCEPTUAL_SOURCES`` (``plan_tool.convergence``) names the pair this
    splits; centralized here so the same two-way split isn't reimplemented
    at each iterate-halt call site.
    """
    correctness = [r for r in recs if r.source == "plan-correctness"]
    completeness = [r for r in recs if r.source == "plan-completeness"]
    return correctness, completeness


def _conceptual_bar_remedy_lines(
    *,
    audit_recs,
    conceptual_bar_blocking_ids: tuple[str, ...],
    bundle_status,
    plan_name: str,
    remapped: bool,
) -> list[str]:
    """Class-mapped remedy hint lines for conceptual findings at iterate stop."""
    lines: list[str] = []
    bar_blockers = [r for r in audit_recs if r.id in conceptual_bar_blocking_ids]
    if remapped and bar_blockers:
        correctness, completeness_bar = _split_conceptual_recs(bar_blockers)
        if correctness:
            lines.append(
                f"  {len(correctness)} conceptual correctness gap(s) require "
                f"a session-directed plan or detail edit by the reader (not auto-appliable)"
            )
        if completeness_bar:
            lines.append(
                f"  {_conceptual_completeness_manual_fix_note(completeness_bar)}"
            )
    if bundle_status.is_bare and not remapped:
        outside_bar = [
            r for r in audit_recs
            if r.source == "plan-completeness"
            and r.id not in conceptual_bar_blocking_ids
            and r.severity.lower() == "medium"
        ]
        if outside_bar and not bar_blockers:
            lines.append(
                "  plan-tool: conceptual completeness gap(s) "
                f"({len(outside_bar)}) stay informational until a detail "
                "bundle exists; see the completeness report for details."
            )
    return lines


def _print_conceptual_bar_stop_remedies(
    *,
    audit_recs,
    conceptual_bar_blocking_ids: tuple[str, ...],
    bundle_status,
    plan_name: str,
    remapped: bool,
    print_header: bool = True,
) -> None:
    """Emit class-mapped conceptual remedy lines to stderr at iterate stop.

    ``print_header`` is independent of ``remapped``: a caller that already
    printed its own "completeness iteration halting" banner for this same
    stop event (a blocking self-consistency finding, whose note owns the
    halt) passes ``print_header=False`` so only the remedy lines print --
    the header only ever means "the stop reason really is terminal_hand_apply".
    """
    lines = _conceptual_bar_remedy_lines(
        audit_recs=audit_recs,
        conceptual_bar_blocking_ids=conceptual_bar_blocking_ids,
        bundle_status=bundle_status,
        plan_name=plan_name,
        remapped=remapped,
    )
    if remapped and print_header:
        print(
            "plan-tool: completeness iteration halting -- conceptual bar "
            f"blockers remain ({len(conceptual_bar_blocking_ids)} finding(s)); "
            "deterministic work is done but the audit gate is not clear.",
            file=sys.stderr,
        )
    for line in lines:
        print(line.strip(), file=sys.stderr)


def _print_all_auto_apply_deferred_halt_message(
    *,
    audit_recs,
    bundle_status,
    audit_incomplete: bool,
    deferred_count: int,
) -> None:
    """Emit the iterate loop's ``all_auto_apply_findings_deferred`` halt note.

    Four mutually exclusive shapes, keyed on bundle bareness and which
    conceptual sources are present in ``audit_recs``. Extracted from
    ``_run_iterate_convergence_loop`` -- a plain, independently testable
    function instead of five levels of nesting inline in a ``while True:``
    loop, which is what let HEAD's own predecessor patch this twice for two
    different bugs (see BUG_BACKLOG / CLAUDE.md).
    """
    saved_correctness, saved_completeness = _split_conceptual_recs(audit_recs)
    if bundle_status.is_bare and saved_correctness:
        print(
            f"plan-tool: completeness iteration halting "
            f"-- all {deferred_count} remaining "
            f"auto-apply finding(s) are deferred/advisory. "
            f"Correctness gap(s) are saved for a "
            f"session-directed edit; see the "
            f"completeness report for details.",
            file=sys.stderr,
        )
    elif (
        bundle_status.is_bare
        and saved_completeness
        and not saved_correctness
    ):
        # Informational copy is only for medium completeness outside the
        # bare bar. Incomplete samples blank the bar set — never call
        # high/critical (or any) gaps "informational".
        if audit_incomplete:
            print(
                f"plan-tool: completeness iteration "
                f"halting -- all {deferred_count} "
                f"remaining auto-apply finding(s) are "
                f"deferred/advisory. Conceptual "
                f"completeness findings were recorded "
                f"but the audit sample did not qualify "
                f"— re-run with a live sample before "
                f"treating them as advisory or blocking.",
                file=sys.stderr,
            )
        else:
            blocking_comp = [
                r for r in saved_completeness
                if r.severity.lower()
                in {"high", "critical"}
            ]
            if blocking_comp:
                print(
                    f"plan-tool: completeness "
                    f"iteration halting -- all "
                    f"{deferred_count} remaining "
                    f"auto-apply finding(s) are "
                    f"deferred/advisory. "
                    f"{_conceptual_completeness_manual_fix_note(blocking_comp)}",
                    file=sys.stderr,
                )
            else:
                print(
                    f"plan-tool: completeness "
                    f"iteration halting -- all "
                    f"{deferred_count} remaining "
                    f"auto-apply finding(s) are "
                    f"deferred/advisory. "
                    f"Completeness gap(s) stay "
                    f"informational until a detail "
                    f"bundle exists; see the "
                    f"completeness report for details.",
                    file=sys.stderr,
                )
    else:
        print(
            f"plan-tool: completeness iteration halting "
            f"-- all {deferred_count} remaining "
            f"auto-apply finding(s) are deferred/advisory. "
            f"Conceptual findings are saved for a "
            f"session-directed edit; see the "
            f"completeness report for details.",
            file=sys.stderr,
        )


def _warn_audit_incomplete(*, reuse: bool = False) -> None:
    """Surface the settled route when pass-conformance did not qualify."""
    if reuse:
        warn(
            "saved conceptual audit lacks pass-conformance evidence — "
            "re-run with a live sample (use --no-reuse-audit when a weak "
            "sidecar caused this)"
        )
    else:
        warn(
            "conceptual audit did not produce a qualifying sample — "
            "re-run with a live audit pass"
        )


def _warn_if_audit_incomplete(coverage, *, reuse: bool) -> None:
    """Call ``_warn_audit_incomplete`` only when ``coverage`` genuinely
    fails pass-conformance. Shared by ``finalize_completeness_run`` and
    ``_run_iterate_convergence_loop``, whose fresh-audit branches both
    re-check ``audit_coverage_qualifies_sample`` after computing the
    conceptual bar to decide whether this warning (distinct from
    ``emit_coverage_unconfirmed``'s budget-limited callout) applies."""
    from plan_tool.review_persistence import (
        audit_coverage_qualifies_sample,
        audit_coverage_withholds_final_findings_sidecar,
    )

    if audit_coverage_withholds_final_findings_sidecar(coverage):
        emit_coverage_unconfirmed(coverage)
        return
    if not audit_coverage_qualifies_sample(coverage):
        _warn_audit_incomplete(reuse=reuse)


def _run_iterate_convergence_loop(
    plan,
    path,
    ctx,
    args,
    budget,
    *,
    bundle_status,
    audit_stage: str,
    audit_input_snapshot=None,
    audit_capture_failed: bool = False,
    sampled_audit_stage: str | None = None,
    reused_audit_recs=None,
    reused_audit_advisory=None,
    reused_audit_coverage=None,
    run_logger=None,
    code_drifted: bool = False,
) -> _IterateOutcome:
    """Drive the --iterate convergence loop and return its outcome bundle.

    Owns the entire ``if budget.enabled:`` phase verbatim: the file-to-step
    map, scope-guard buffer, iteration-lock session, the single up-front
    conceptual audit, the ``while`` convergence loop (triage, per-finding
    ``apply_finding`` dispatch, pre/post-apply drift checks, auto-reconcile,
    collision sidecar, scope eval), and the post-loop re-parse. Every
    body-local domain import (``apply_finding``, ``shell_review_invoker``,
    ``audit_plan_until_stable``, the iteration-lock / scope-guard /
    change-collision helpers) stays body-local so the domain suites'
    monkeypatch seams keep intercepting through ``main()`` with zero
    retarget.

    Returns an :class:`_IterateOutcome` carrying the applied/deferred
    dispositions, stop reason, iteration count, the once-computed audit
    recs (both conceptual sources, persisted unapplied under #85), and
    the final re-parsed ``plan``.
    A loop-internal halt (pre-apply drift, post-apply parse failure)
    returns ``_IterateOutcome(early_exit_code=2, halt_reason=...)``; the
    orchestrator persists the report via :func:`finalize_completeness_run`
    before forwarding that rc.
    """
    # Direct callers of this internal phase predate the command's capture
    # hand-off. Preserve that test/programmatic seam, but a command capture
    # failure is explicit no-evidence state: retrying here would give one run
    # two plan/detail identities and could make the prompt disagree with the
    # report's sampled stage.
    if audit_input_snapshot is None and not audit_capture_failed:
        try:
            from plan_tool.review_persistence import AuditInputSnapshot

            audit_input_snapshot = AuditInputSnapshot.capture(
                path, ctx.repo_root
            )
        except Exception:  # noqa: BLE001 — outcome records unsampled evidence
            audit_capture_failed = True
    if audit_input_snapshot is not None:
        # Direct callers can still enter this phase with an older parsed plan.
        # Rebind it before any scope, deterministic, or conceptual work so
        # this phase shares the command's single captured input identity.
        plan = audit_input_snapshot.plan
    if audit_input_snapshot is not None and sampled_audit_stage is None:
        sampled_bundle_status = _sampled_bundle_status(audit_input_snapshot)
        sampled_audit_stage = derive_audit_stage(sampled_bundle_status)

    # When the iterate loop runs it audits the plan's concepts exactly
    # once (up front, not per-round). The post-loop report reuses that
    # single result instead of spending another claude call. ``None``
    # means "no loop ran -- the report should audit fresh below".
    _iterate_audit_recs: Optional[list] = None
    # Disposition tracking for the persisted report + concise console
    # summary (populated by the loop below; stay empty in audit-only mode).
    from plan_tool.completeness_report import AppliedOutcome as _AppliedOutcome
    _applied_outcomes: list = []
    _deferred_recs: dict = {}
    _loop_stop_reason: Optional[str] = None
    _loop_iterations = 0
    # Accepted reuse has already established this coverage verdict.  Seed it
    # before the checkpoint so the checkpoint, returned iterate outcome, and
    # final report all describe the same conceptual audit without another
    # Claude call.  An unknown legacy sidecar remains an explicit empty
    # coverage marker — do not use truthiness to replace it with fresh state.
    _audit_budget: dict = (
        _coverage_input_from_reusable_audit(reused_audit_coverage)
        if reused_audit_recs is not None
        else {}
    )
    _iterate_audit_advisory = None
    _audit_advisory_checkpoint_saved = False
    _resumed_from_sampler_checkpoint = False
    _conceptual_bar_blocking_ids: tuple[str, ...] = ()
    _audit_incomplete = False
    if budget.enabled:
        from plan_tool.launcher import apply_finding, revert_apply_if_parse_broken
        from plan_tool.review import (
            ReviewError,
            assemble_carried_findings,
            audit_plan_until_stable,
            collect_deterministic_findings,
            collect_self_consistency_findings,
            plan_audit_invoker_from_review_invoker,
            SELF_CONSISTENCY_SOURCES,
            shell_review_invoker,
        )
        from plan_tool.scope_guard import (
            ScopeGuardBuffer,
            build_file_to_step_map,
            compute_in_scope_paths,
            compute_plan_tool_artifact_paths,
            compute_snapshot_dirs,
            evaluate_apply_scope,
            revert_out_of_scope,
            snapshot_subtrees,
        )

        # File→step map for drift warnings. Computed
        # once before the loop -- the plan's step.files shouldn't
        # change between iterations (apply_finding edits plan body
        # and detail files, not step.files declarations), so a single
        # snapshot is fine.
        _file_to_step = build_file_to_step_map(plan, ctx.repo_root)

        # Hoist the plan fingerprint once so every per-finding apply-verdict
        # telemetry line carries the same join key without re-hashing per rec.
        # Best-effort: a compute failure degrades to "".
        from plan_tool.review_persistence import (
            compute_plan_fingerprint as _compute_plan_fingerprint,
        )
        try:
            _apply_verdict_plan_fp = _compute_plan_fingerprint(path)
        except Exception:
            _apply_verdict_plan_fp = ""

        def _collect_det_findings(plan_obj, plan_path_obj):
            """Deterministic well-formedness findings only.

            These are content-addressed by *structure* (missing section,
            unresolved path, ...), so their ids are stable across rounds
            and they genuinely converge: an apply that fills a gap makes
            the finding disappear next round. The subjective conceptual
            plan-audit deliberately does NOT run here -- it re-phrases
            the same concepts each round, minting fresh ids that defeat
            convergence detection (the body-hash treadmill). It runs
            exactly once below, and only its blocking *correctness*
            findings feed the apply loop.
            """
            return collect_deterministic_findings(
                plan_obj, plan_path_obj,
                repo_root=ctx.repo_root, plan_name=args.name,
            )

        in_scope = compute_in_scope_paths(plan, path, ctx.repo_root)
        ignored_artifact_paths = compute_plan_tool_artifact_paths(
            path, ctx.repo_root
        )
        scope_dirs = compute_snapshot_dirs(in_scope, ctx.repo_root)
        scope_buffer = ScopeGuardBuffer()

        # Acquire the per-repo iteration lock for the convergence loop.
        # ``iteration_session`` releases it AND restores the SIGINT handler
        # on EVERY exit path -- a clean break, an early ``return 2``, or an
        # unexpected exception escaping the loop -- so a crash leaves no
        # stale lockfile. We watch only IMPLEMENTATION files (step.files),
        # NOT plan + detail (apply_finding edits those every iteration;
        # watching them would trip a false-positive drift warning naming
        # the loop's own edits).
        from plan_tool.scope_guard import compute_drift_watched_paths
        _drift_watched = compute_drift_watched_paths(
            plan, path, ctx.repo_root
        )
        from plan_tool.drift_detection import iteration_session
        with iteration_session(
            ctx.repo_root,
            enabled=True,
            slug=args.name,
            command="completeness",
            loop_name="completeness",
            watched_paths=_drift_watched,
            file_to_step=_file_to_step,
        ) as _iter_lock:
                from plan_tool.progress import NullReporter, StderrReporter

                _progress = StderrReporter()

                state = ConvergenceState(budget=budget)
                print(
                    f"\nplan-tool: completeness convergence loop "
                    f"(≤{budget.max_iterations} iterations, "
                    f"{int(budget.budget_seconds)}s no-progress deadline — "
                    f"resets on every round/apply, not a total-time cap)",
                    file=sys.stderr,
                )
                # Conceptual audit runs ONCE, here. Under the read-only-audit
                # split (#85) NEITHER conceptual source is applied by this loop:
                # correctness (design problems) and completeness ("what else?")
                # are both persisted in the post-loop report/sidecar for the
                # reader to hand-edit in the relevant plan or detail files. The loop
                # spends its apply budget only on the deterministic
                # well-formedness findings, which genuinely converge (a filled
                # gap disappears next round). Re-using ``_audit_recs`` for the
                # report avoids a second claude call.
                _bundle_status = bundle_status
                if reused_audit_recs is not None:
                    # Reuse the saved conceptual audit: skip the up-front
                    # claude call entirely and seed the loop's audit recs
                    # from the sidecar. Under #85 the loop applies neither
                    # conceptual source, so the reused recs just flow into
                    # the persisted report unchanged (the deterministic
                    # apply stream is unaffected by reuse).
                    print(
                        "plan-tool: reusing saved conceptual audit "
                        "(skipping the up-front audit call)",
                        file=sys.stderr,
                    )
                    _audit_recs = reused_audit_recs
                    _iterate_audit_advisory = reused_audit_advisory
                else:
                    _bundle_status = emit_bare_plan_banner(
                        plan, path, ctx.repo_root,
                        bundle_status=bundle_status,
                    )
                    _grounding = (
                        "plan body + code at HEAD"
                        if _bundle_status.is_fully_bare
                        else "the detail bundle"
                    )
                    print(
                        "plan-tool: auditing plan concepts "
                        f"(≤{_effective_audit_passes(args)} "
                        f"pass(es), run once, grounded in {_grounding})…",
                        file=sys.stderr,
                    )
                    _captured_advisory: list = []
                    _sampler_resumed: list[bool] = []
                    if audit_input_snapshot is None:
                        _audit_recs = []
                    else:
                        _audit_recs = audit_plan_until_stable(
                            plan, path,
                            repo_root=ctx.repo_root,
                            invoker=plan_audit_invoker_from_review_invoker(
                                shell_review_invoker
                            ),
                            max_passes=_effective_audit_passes(args),
                            dry_rounds=getattr(
                                args, "audit_dry_rounds", AUDIT_DEFAULT_DRY_ROUNDS
                            ),
                            # Heartbeat per claude call — each pass runs for
                            # minutes; the start/elapsed/done lines show liveness.
                            reporter=_progress,
                            run_logger=run_logger,
                            budget_report=_audit_budget,
                            advisory_out=_captured_advisory,
                            audit_input_snapshot=audit_input_snapshot,
                            resumed_out=_sampler_resumed,
                        )
                        _iterate_audit_advisory = (
                            _captured_advisory[0] if _captured_advisory else None
                        )
                        _resumed_from_sampler_checkpoint = bool(
                            _sampler_resumed and _sampler_resumed[0]
                        )
                        from plan_tool.review_persistence import (
                            audit_coverage_withholds_final_findings_sidecar,
                        )

                        if not audit_coverage_withholds_final_findings_sidecar(
                            _audit_budget
                        ):
                            emit_coverage_unconfirmed(_audit_budget)
                (
                    _conceptual_bar_blocking_ids,
                    _audit_incomplete,
                ) = _conceptual_bar_from_audit_recs(
                    _audit_recs,
                    audit_stage=sampled_audit_stage or audit_stage,
                    coverage=_audit_budget,
                )
                _warn_if_audit_incomplete(
                    _audit_budget, reuse=reused_audit_recs is not None
                )
                # Fingerprints (rec.id) already dispatched to apply_finding this
                # loop. A finding is applied at most once -- re-applying the same
                # guidance that already ran is the churn this whole restructure
                # removes (point 3). Stable deterministic ids make this dedupe
                # reliable across rounds.
                applied_fingerprints: set[str] = set()
                # Live verdict history this run: rec.id → (resolution, reason),
                # accumulated as each apply lands and folded into the carried
                # context handed to later applies.
                _carried_resolution: dict[str, tuple[str, str]] = {}

                def _open_findings_now():
                    """Current open set: deterministic well-formedness findings
                    plus the blocking-capable self-consistency battery.

                    Under the read-only-audit split (#85) the conceptual
                    correctness findings are persisted unapplied (walked later
                    by the reader), so the loop converges on its
                    deterministic findings. The self-consistency battery
                    (``orphaned-deliverable`` / ``suppression-shape``) is
                    non-auto-appliable but **blocking**: it is included here so
                    the loop's blocking signal + convergence messaging agree
                    with the finalize ``--fail-on-findings`` gate (which reads
                    ``det.self_consistency_recs``) instead of falsely reporting
                    "converged". It is NOT folded into
                    ``collect_deterministic_findings`` (which ``apply_finding``
                    uses for pre/post deltas); the triage partition defers it
                    (not apply-eligible) and the stop path names it as a
                    manual-fix finding. See BUG_BACKLOG."""
                    return _collect_det_findings(plan, path) + (
                        collect_self_consistency_findings(
                            plan, ctx.repo_root,
                            plan_name=args.name, plan_path=path,
                        )
                    )

                print(
                    "plan-tool: running deterministic well-formedness checks…",
                    file=sys.stderr,
                )
                current_findings = _open_findings_now()
                state.current_finding_ids = frozenset(r.id for r in current_findings)
                state.has_blocking_findings = any(
                    is_blocking(r.severity) for r in current_findings
                )
                print(
                    f"plan-tool: {len(current_findings)} open finding(s): "
                    f"{_fmt_finding_counts(current_findings)}",
                    file=sys.stderr,
                )
                # Reset the no-progress timer: it was stamped at state
                # construction, before the minutes-long round-0 audit above.
                # Without this, a slow audit alone trips the deadline at
                # iteration=0. budget_seconds measures iteration progress, not
                # the up-front audit.
                touch(state)

                def _halt(reason: str) -> _IterateOutcome:
                    return _IterateOutcome(
                        applied_outcomes=list(_applied_outcomes),
                        deferred_recs=dict(_deferred_recs),
                        stop_reason=f"halted: {reason}",
                        halt_reason=reason,
                        iterations=state.iteration,
                        audit_recs=_audit_recs_for_report(
                            _audit_recs, applied_fingerprints,
                        ),
                        plan=plan,
                        budget=_audit_budget,
                        conceptual_bar_blocking_ids=_conceptual_bar_blocking_ids,
                        audit_incomplete=_audit_incomplete,
                        audit_shape_advisory=_iterate_audit_advisory,
                        audit_shape_advisory_checkpoint_saved=(
                            _audit_advisory_checkpoint_saved
                        ),
                        audit_input_snapshot=audit_input_snapshot,
                        audit_stage=sampled_audit_stage,
                        audit_capture_failed=audit_input_snapshot is None,
                        resumed_from_sampler_checkpoint=(
                            _resumed_from_sampler_checkpoint
                        ),
                        early_exit_code=2,
                    )

                _checkpoint_advisory = _iterate_audit_advisory
                if _checkpoint_advisory is not None:
                    from plan_tool.review_persistence import (
                        audit_input_fingerprint_matches_disk,
                    )

                    if not audit_input_fingerprint_matches_disk(
                        path,
                        ctx.repo_root,
                        _checkpoint_advisory.source_plan_fingerprint,
                    ):
                        _checkpoint_advisory = None
                _checkpoint_path = write_pre_apply_audit_checkpoint(
                    plan, path, ctx, args,
                    audit_recs=_audit_recs,
                    budget=_audit_budget,
                    bundle_status=bundle_status,
                    code_drifted=code_drifted,
                    audit_shape_advisory=_checkpoint_advisory,
                    audit_input_snapshot=audit_input_snapshot,
                    audit_stage=sampled_audit_stage,
                    resumed_from_sampler_checkpoint=(
                        _resumed_from_sampler_checkpoint
                    ),
                )
                _audit_advisory_checkpoint_saved = (
                    _checkpoint_advisory is not None and _checkpoint_path is not None
                )
                while True:
                    cont, reason = should_continue(state)
                    if not cont:
                        _loop_stop_reason = _remap_iterate_stop_for_conceptual_bar(
                            reason,
                            conceptual_bar_blocking_ids=_conceptual_bar_blocking_ids,
                            audit_incomplete=_audit_incomplete,
                        )
                        bar = "─" * 60
                        open_count = len(state.current_finding_ids)
                        hints: list[str] = []
                        if open_count > 0:
                            hints.append(
                                f"  plan-tool reconcile-plan-walk {args.name}   "
                                f"# interactively review the {open_count} open finding(s)"
                            )
                            # Tailor the remedy lines to what the open
                            # diagnostics actually are — only name
                            # `plan-tool detail` when a detail file is
                            # genuinely missing, not whenever findings
                            # remain (a files-coherence drift wants a
                            # `files:` edit, and `detail` would no-op).
                            from plan_tool.completeness_report import (
                                DETAIL_LEVEL_DIAGNOSTIC_SOURCES,
                                deferred_kind,
                                diagnostic_remedies,
                            )
                            _open_recs = [
                                r for r in current_findings
                                if r.id in state.current_finding_ids
                            ]
                            # A stop via ``should_continue`` (no_progress /
                            # max_iterations / deadline) can exit with open
                            # self-consistency blocking findings still present
                            # (they never resolve — they need a manual edit). The
                            # ``not open_apply`` branch below can't have printed
                            # its note on this path, so surface it here too so the
                            # honest manual-fix guidance isn't lost. See BUG_BACKLOG.
                            _open_sc = [
                                r for r in _open_recs
                                if r.source in SELF_CONSISTENCY_SOURCES
                                and is_blocking(r.severity)
                            ]
                            if _open_sc:
                                hints.append(
                                    f"  {_sc_manual_fix_note(_open_sc)}"
                                )
                            _open_diag = [
                                r for r in _open_recs
                                if deferred_kind(r) == "diagnostic"
                            ]
                            if _bundle_status.is_bare:
                                _open_diag = [
                                    r for r in _open_diag
                                    if r.source
                                    not in DETAIL_LEVEL_DIAGNOSTIC_SOURCES
                                ]
                            for _line in diagnostic_remedies(
                                _open_diag, args.name
                            ):
                                hints.append(f"  {_line}")
                        if reason == "deadline_exceeded":
                            hints.append(
                                f"  plan-tool completeness-audit {args.name} --iteration-budget 1800   "
                                f"# resume with a larger wall-clock budget"
                            )
                        elif reason == "max_iterations":
                            hints.append(
                                f"  plan-tool completeness-audit {args.name} --max-iterations 5   "
                                f"# resume with a larger iteration cap"
                            )
                        elif reason == "no_progress":
                            hints.append(
                                f"  plan-tool completeness-audit {args.name} --max-stall-rounds 0   "
                                f"# the open-finding count stopped shrinking; "
                                f"these likely need manual edits. Re-run with this "
                                f"to disable the stall stop and keep iterating."
                            )
                        elif reason == "time_budget_exceeded":
                            hints.append(
                                f"  plan-tool completeness-audit {args.name}   "
                                f"# time budget reached — stopped cleanly at a "
                                f"round boundary (completed gaps are durable). "
                                f"Re-run to continue where it left off, or raise "
                                f"--time-budget for a longer run."
                            )
                        if _loop_stop_reason == "terminal_hand_apply":
                            hints.extend(
                                _conceptual_bar_remedy_lines(
                                    audit_recs=_audit_recs,
                                    conceptual_bar_blocking_ids=(
                                        _conceptual_bar_blocking_ids
                                    ),
                                    bundle_status=_bundle_status,
                                    plan_name=args.name,
                                    remapped=True,
                                )
                            )
                        hint_block = (
                            "\n  What to do:\n" + "\n".join(hints)
                            if hints else ""
                        )
                        print(
                            f"\n{bar}\n"
                            f"  completeness iteration loop stopped: "
                            f"{_loop_stop_reason}\n"
                            f"  iteration={state.iteration} · "
                            f"open_findings={open_count}"
                            f"{hint_block}\n"
                            f"{bar}",
                            file=sys.stderr,
                        )
                        break
                    open_findings = [
                        r
                        for r in current_findings
                        if r.id in state.current_finding_ids
                        and r.id not in applied_fingerprints
                    ]
                    # Impact-weighted triage (session 4 follow-up). Findings
                    # whose complexity strictly exceeds their impact are
                    # deferred without spending claude tokens on apply. When
                    # ``--no-triage`` is passed, every finding lands in
                    # ``open_apply`` (legacy behavior). When all remaining
                    # findings are deferred, the loop halts so convergence
                    # short-circuits instead of looping with no productive
                    # work to do.
                    from plan_tool.review import partition_findings_for_triage
                    from plan_tool.completeness_report import (
                        DETAIL_LEVEL_FINDING_SOURCES,
                        deferred_kind,
                    )

                    bare_detail_level: list = []
                    if _bundle_status.is_bare:
                        bare_detail_level = [
                            r for r in open_findings
                            if r.source in DETAIL_LEVEL_FINDING_SOURCES
                        ]
                        open_findings = [
                            r for r in open_findings
                            if r.source not in DETAIL_LEVEL_FINDING_SOURCES
                        ]

                    open_apply, open_deferred = partition_findings_for_triage(
                        open_findings,
                        triage_enabled=getattr(args, "triage", True),
                        include_info=getattr(args, "include_info", False),
                    )
                    open_deferred = [*open_deferred, *bare_detail_level]
                    # Accumulate deferred findings for the persisted report;
                    # print only a concise count to the terminal (the full,
                    # per-item list -- with reasons -- lands in the report file
                    # so the screen stays readable).
                    for _r in open_deferred:
                        _deferred_recs.setdefault(_r.id, _r)
                        # A triaged-away finding is never dispatched; record it
                        # as skipped so the carried context reads it as a
                        # deliberate no-op, not still-open.
                        _carried_resolution.setdefault(
                            _r.id, (CARRIED_RESOLUTION_SKIPPED, "deferred")
                        )
                    if open_deferred:
                        _kc = {"advisory-conceptual": 0, "diagnostic": 0,
                               "info": 0, "triage": 0, "open": 0}
                        for _r in open_deferred:
                            _kc[deferred_kind(_r)] += 1
                        print(
                            f"plan-tool: deferring {len(open_deferred)} finding(s) "
                            f"({_kc['diagnostic']} structural-diagnostic, "
                            f"{_kc['info']} info, {_kc['triage']} low-payoff) "
                            f"— see the completeness report for the full list + "
                            f"why each was deferred",
                            file=sys.stderr,
                        )
                    if not open_apply:
                        # Blocking-but-non-appliable self-consistency findings
                        # (``orphaned-deliverable`` / ``suppression-shape``) get
                        # a terminal message naming their own finding class
                        # rather than the generic conceptual-gap line (they
                        # are neither auto-appliable nor apply-walk targets —
                        # the fix is a manual plan edit) and must NOT read as
                        # "converged"
                        # (they flip the ``--fail-on-findings`` rc). See
                        # BUG_BACKLOG.
                        sc_blocking = [
                            r for r in open_deferred
                            if r.source in SELF_CONSISTENCY_SOURCES
                            and is_blocking(r.severity)
                        ]
                        if sc_blocking:
                            _loop_stop_reason = "manual_fix_blocking_findings"
                            print(
                                "plan-tool: completeness iteration halting -- "
                                + _sc_manual_fix_note(sc_blocking),
                                file=sys.stderr,
                            )
                        elif open_deferred:
                            _loop_stop_reason = (
                                "all_auto_apply_findings_deferred"
                            )
                        else:
                            _loop_stop_reason = _loop_stop_reason or "converged"
                        _loop_stop_reason = _remap_iterate_stop_for_conceptual_bar(
                            _loop_stop_reason,
                            conceptual_bar_blocking_ids=_conceptual_bar_blocking_ids,
                            audit_incomplete=_audit_incomplete,
                        )
                        # SC owns stop kind when it blocks (not remapped), but
                        # still print conceptual bar remedies when the bar set
                        # is non-empty — otherwise correctness/completeness
                        # routes are lost beside the SC note.
                        _print_conceptual_bar = (
                            _loop_stop_reason == "terminal_hand_apply"
                            or (
                                bool(sc_blocking)
                                and bool(_conceptual_bar_blocking_ids)
                                and not _audit_incomplete
                            )
                        )
                        if _print_conceptual_bar:
                            _print_conceptual_bar_stop_remedies(
                                audit_recs=_audit_recs,
                                conceptual_bar_blocking_ids=(
                                    _conceptual_bar_blocking_ids
                                ),
                                bundle_status=_bundle_status,
                                plan_name=args.name,
                                remapped=True,
                                # The SC branch above already printed its own
                                # "completeness iteration halting" banner for
                                # this same stop event when sc_blocking is what
                                # triggered this print (not a genuine remap to
                                # terminal_hand_apply) -- a second header would
                                # read as two separate halts.
                                print_header=(
                                    _loop_stop_reason == "terminal_hand_apply"
                                ),
                            )
                        elif _loop_stop_reason == "all_auto_apply_findings_deferred":
                            _print_all_auto_apply_deferred_halt_message(
                                audit_recs=_audit_recs,
                                bundle_status=_bundle_status,
                                audit_incomplete=_audit_incomplete,
                                deferred_count=len(open_deferred),
                            )
                        elif _loop_stop_reason == "converged":
                            _print_conceptual_bar_stop_remedies(
                                audit_recs=_audit_recs,
                                conceptual_bar_blocking_ids=(
                                    _conceptual_bar_blocking_ids
                                ),
                                bundle_status=_bundle_status,
                                plan_name=args.name,
                                remapped=False,
                            )
                        break
                    round_no = state.iteration + 1
                    print(
                        f"\nplan-tool: ── iteration {round_no}/"
                        f"{budget.max_iterations} ── {len(open_findings)} open · "
                        f"applying {len(open_apply)}"
                        + (
                            f" · deferring {len(open_deferred)}"
                            if open_deferred else ""
                        ),
                        file=sys.stderr,
                    )
                    # Enumerate findings up front: the per-finding progress
                    # line below is transient (heartbeat overwrites it), so this
                    # keeps the actual findings on screen for the whole round.
                    for idx, rec in enumerate(open_apply, start=1):
                        print(
                            f"        [{idx}/{len(open_apply)}] "
                            f"{_finding_progress_label(rec)}",
                            file=sys.stderr,
                        )
                    for idx, rec in enumerate(open_apply, start=1):
                        # Pre-apply drift check (task #30). If the user
                        # edited a watched (step.files) file BEFORE this apply
                        # starts, halt now -- spending claude tokens on a
                        # likely-spurious apply is pure waste. Pre-check is
                        # the token-efficient gate.
                        if not getattr(args, "allow_drift", False):
                            from plan_tool.drift_detection import check_drift

                            pre_drifted = check_drift(_iter_lock)
                            if pre_drifted:
                                _emit_drift_halt_warning(
                                    pre_drifted,
                                    phase="before",
                                    finding_id=rec.id,
                                    ctx_repo_root=ctx.repo_root,
                                    file_to_step=_file_to_step,
                                )
                                # Lesson 13 (audit > observe):
                                # automatically run reconcile against the
                                # step(s) owning the drifted files so the
                                # operator sees structured findings inline
                                # rather than just "drift on file X". Opt-out
                                # via --no-auto-reconcile-on-drift.
                                if getattr(args, "auto_reconcile_on_drift", True):
                                    _run_auto_reconcile_on_drift(
                                        drifted=pre_drifted,
                                        file_to_step=_file_to_step,
                                        plan_path=path,
                                        plan_slug=args.name,
                                        repo_root=ctx.repo_root,
                                    )
                                _emit_scope_guard_plan(
                                    scope_buffer,
                                    plan_path=path,
                                    plan_slug=args.name,
                                    ctx=ctx,
                                )
                                return _halt(HALT_PRE_APPLY_DRIFT)

                        pre_snap = snapshot_subtrees(scope_dirs)
                        # Loop owns the progress line so it carries the real
                        # [idx/total] within this round (apply_finding's own
                        # reporter hardcodes [1/1], which reads as redundant when
                        # called once per finding). NullReporter silences the
                        # inner one; the StderrReporter heartbeat keeps the user
                        # informed during the 10-30s+ claude call.
                        _handle = _progress.start_step(
                            idx, len(open_apply), _finding_progress_label(rec)
                        )
                        # Wrap the apply in an ``apply_finding_dispatch`` phase
                        # (source/finding_label/verdict) + pass run_logger, so
                        # the audit loop's applies are logged + bucketable —
                        # matching create/detail (the loop left them unlogged).
                        if run_logger is not None:
                            run_logger.phase_start(
                                "apply_finding_dispatch",
                                step_id=rec.step_id,
                                source=rec.source,
                                finding_label=next(
                                    (ln.strip() for ln in rec.body.splitlines()
                                     if ln.strip()),
                                    rec.source,
                                ),
                            )
                        _apply_t0 = time.monotonic()
                        try:
                            parse_plan(path)
                        except (ParseError, ValidationError) as exc:
                            error(
                                f"plan failed to parse before apply_finding: {exc}"
                            )
                            _emit_scope_guard_plan(
                                scope_buffer,
                                plan_path=path,
                                plan_slug=args.name,
                                ctx=ctx,
                            )
                            return _halt("plan failed to parse before apply_finding")
                        # Carried context: every finding surfaced this run, with
                        # the resolution known so far. ``_audit_recs`` (conceptual)
                        # and ``current_findings`` (deterministic) are disjoint by
                        # source under #85, but collapse to one rec per id anyway
                        # (``assemble_carried_findings`` does not dedup) so a stray
                        # id collision can't double-count.
                        _union = {
                            r.id: r
                            for r in [*_audit_recs, *current_findings]
                        }
                        carried = assemble_carried_findings(
                            list(_union.values()),
                            resolution_by_id=_carried_resolution,
                        )
                        apply_result = apply_finding(
                            path,
                            repo_root=ctx.repo_root,
                            finding_body=format_recommendation_for_apply(rec),
                            targeted_fix=audit_targeted_fix(rec),
                            carried_findings=carried,
                            step_id=rec.step_id,
                            plan_name=args.name,
                            auto_fix_introduced=True,
                            reporter=NullReporter(),
                            run_logger=run_logger,
                            anchor=(rec.anchor or ""),
                            plan_fingerprint=_apply_verdict_plan_fp,
                        )
                        _apply_elapsed = time.monotonic() - _apply_t0
                        apply_reverted = revert_apply_if_parse_broken(apply_result)
                        if run_logger is not None:
                            run_logger.phase_end(
                                "apply_finding_dispatch",
                                int(_apply_elapsed * 1000),
                                (
                                    "reverted" if apply_reverted
                                    else apply_result.verdict.lower()
                                ),
                                step_id=rec.step_id,
                                source=rec.source,
                                verdict=(
                                    "REVERTED" if apply_reverted
                                    else apply_result.verdict
                                ),
                            )
                        if apply_reverted:
                            error(
                                "reverted apply-finding edits: post-edit plan "
                                "failed to parse (keeping would wedge the "
                                "iterate loop); fix the YAML and re-run"
                            )
                            _emit_scope_guard_plan(
                                scope_buffer,
                                plan_path=path,
                                plan_slug=args.name,
                                ctx=ctx,
                            )
                            return _halt(
                                "reverted apply-finding edits: post-edit plan "
                                "failed to parse"
                            )
                        if apply_result.exit_code == 0:
                            _handle.complete(
                                _apply_elapsed,
                                len((apply_result.stdout or "").encode("utf-8")),
                            )
                        else:
                            _handle.fail(
                                _apply_elapsed,
                                f"claude exit {apply_result.exit_code}",
                            )
                        if apply_result.verdict != "APPLIED":
                            print(
                                f"        → {apply_result.verdict}"
                                + (
                                    f": {apply_result.summary.splitlines()[0][:80]}"
                                    if apply_result.summary.strip() else ""
                                ),
                                file=sys.stderr,
                            )
                        # Mark this finding's fingerprint applied (tokens are
                        # spent) so neither this round's siblings nor any later
                        # round re-dispatches the same guidance, regardless of
                        # verdict (point 3). A finding that didn't resolve won't
                        # resolve on an identical re-apply -- it needs manual
                        # attention, surfaced as still-open in the final report.
                        applied_fingerprints.add(rec.id)
                        # Fold this finding's verdict into the carried history so
                        # a later finding's apply sees how this one resolved.
                        _carried_resolution[rec.id] = _resolution_for_verdict(
                            apply_result.verdict
                        )
                        _applied_outcomes.append(
                            _AppliedOutcome(
                                rec=rec,
                                verdict=apply_result.verdict,
                                summary=apply_result.summary or "",
                            )
                        )
                        # Post-apply drift check. If the user edited a watched
                        # file DURING this apply (race), the apply's edits to
                        # plan/detail may have been driven by in-flight code
                        # changes. KEEP the apply's output -- the claude
                        # tokens are already spent and the edits may still be
                        # useful (user reviews via git diff). Halt subsequent
                        # applies to prevent compounding the issue. NO revert:
                        # token value preservation wins over strict spec
                        # integrity in the rare during-apply-drift case.
                        if not getattr(args, "allow_drift", False):
                            from plan_tool.drift_detection import check_drift

                            post_drifted = check_drift(_iter_lock)
                            if post_drifted:
                                _emit_drift_halt_warning(
                                    post_drifted,
                                    phase="during",
                                    finding_id=rec.id,
                                    ctx_repo_root=ctx.repo_root,
                                    file_to_step=_file_to_step,
                                )
                                # Change-collision sidecar + pause-for-merge
                                # (session 4 follow-up to #29). When drift
                                # fires post-apply, save claude's edits to
                                # sidecars next to the originals and pause
                                # for the user to merge. On Enter, break out
                                # of the for-rec loop so the outer while-loop
                                # recollects findings against the merged
                                # state. On Ctrl-C / headless / decline, fall
                                # through to the legacy halt-with-rc=2 path
                                # (which still runs auto-reconcile + emits
                                # the scope-guard plan stub). Opt out via
                                # ``--no-collision-sidecar`` to keep claude's
                                # edits on disk in the legacy "review via
                                # git diff" model.
                                if getattr(args, "collision_sidecar", True):
                                    from plan_tool.change_collision import (
                                        handle_drift_collision,
                                    )
                                    if handle_drift_collision(
                                        apply_result.pre_snapshot,
                                        repo_root=ctx.repo_root,
                                        yes=args.yes,
                                    ):
                                        # User merged + chose to continue.
                                        # Run scope-eval + revert out-of-
                                        # scope edits BEFORE breaking, so
                                        # the tree is clean for the next
                                        # iteration (Bug 3 from session-4
                                        # review). Then refresh the lock's
                                        # content-hash snapshot so the next
                                        # pre-apply drift check compares
                                        # against the merged state (Bug 1).
                                        # Without these two steps the
                                        # merge-continue path would either
                                        # leak out-of-scope edits or halt
                                        # immediately on the same drift.
                                        touch(state)
                                        post_snap = snapshot_subtrees(scope_dirs)
                                        records = evaluate_apply_scope(
                                            finding_id=rec.id,
                                            finding_body=rec.body,
                                            step_id=rec.step_id,
                                            pre_snapshot=pre_snap,
                                            post_snapshot=post_snap,
                                            in_scope_paths=in_scope,
                                            repo_root=ctx.repo_root,
                                            ignored_artifact_paths=(
                                                ignored_artifact_paths
                                            ),
                                        )
                                        for r in records:
                                            if r.impact_status == "reverted":
                                                revert_out_of_scope(
                                                    r, pre_snap,
                                                )
                                                print(
                                                    f"plan-tool: reverted "
                                                    f"out-of-scope code "
                                                    f"edit(s) from finding "
                                                    f"{r.finding_id} "
                                                    f"({len(r.out_of_scope_files)}"
                                                    f" file(s)) before "
                                                    f"continuing after "
                                                    f"collision merge:",
                                                    file=sys.stderr,
                                                )
                                                _print_attributed_files(
                                                    r.out_of_scope_files,
                                                    ctx.repo_root,
                                                    _file_to_step,
                                                )
                                            elif r.impact_status == "kept-by-impact":
                                                print(
                                                    f"plan-tool: kept "
                                                    f"out-of-scope code "
                                                    f"edit(s) from finding "
                                                    f"{r.finding_id} "
                                                    f"(referenced by "
                                                    f"in-scope file, "
                                                    f"{len(r.out_of_scope_files)}"
                                                    f" file(s)):",
                                                    file=sys.stderr,
                                                )
                                                _print_attributed_files(
                                                    r.out_of_scope_files,
                                                    ctx.repo_root,
                                                    _file_to_step,
                                                )
                                            scope_buffer.add(r)
                                        from plan_tool.drift_detection import (
                                            refresh_snapshot,
                                        )
                                        refresh_snapshot(_iter_lock)
                                        break
                                # Lesson 13 — see pre-apply
                                # branch above for the rationale.
                                if getattr(args, "auto_reconcile_on_drift", True):
                                    _run_auto_reconcile_on_drift(
                                        drifted=post_drifted,
                                        file_to_step=_file_to_step,
                                        plan_path=path,
                                        plan_slug=args.name,
                                        repo_root=ctx.repo_root,
                                    )
                                _emit_scope_guard_plan(
                                    scope_buffer,
                                    plan_path=path,
                                    plan_slug=args.name,
                                    ctx=ctx,
                                )
                                return _halt(HALT_POST_APPLY_DRIFT)
                        # Each apply_finding can take 10-15 min. Touch the
                        # convergence state so the budget-seconds deadline
                        # debounces on forward progress, not total wall-clock.
                        touch(state)
                        post_snap = snapshot_subtrees(scope_dirs)
                        records = evaluate_apply_scope(
                            finding_id=rec.id,
                            finding_body=rec.body,
                            step_id=rec.step_id,
                            pre_snapshot=pre_snap,
                            post_snapshot=post_snap,
                            in_scope_paths=in_scope,
                            repo_root=ctx.repo_root,
                            ignored_artifact_paths=ignored_artifact_paths,
                        )
                        for r in records:
                            if r.impact_status == "reverted":
                                revert_out_of_scope(r, pre_snap)
                                print(
                                    f"plan-tool: reverted out-of-scope code edit(s) "
                                    f"from finding {r.finding_id} "
                                    f"({len(r.out_of_scope_files)} file(s)):",
                                    file=sys.stderr,
                                )
                                _print_attributed_files(
                                    r.out_of_scope_files,
                                    ctx.repo_root,
                                    _file_to_step,
                                )
                            elif r.impact_status == "kept-by-impact":
                                print(
                                    f"plan-tool: kept out-of-scope code edit(s) "
                                    f"from finding {r.finding_id} (referenced by "
                                    f"in-scope file, "
                                    f"{len(r.out_of_scope_files)} file(s)):",
                                    file=sys.stderr,
                                )
                                _print_attributed_files(
                                    r.out_of_scope_files,
                                    ctx.repo_root,
                                    _file_to_step,
                                )
                            scope_buffer.add(r)
                    try:
                        plan = parse_plan(path)
                    except (ParseError, ValidationError) as exc:
                        error(
                            f"plan failed to parse after apply_finding: {exc}"
                        )
                        # Release the lock before returning so a parse-recovery
                        # retry isn't blocked. Drift detection is skipped on
                        # this error path (the parse failure is a more pressing
                        # signal than a content change on a watched file, and
                        # the failure itself implies the plan file was just
                        # edited).
                        return _halt("plan failed to parse after apply_finding")
                    print(
                        "plan-tool: re-checking after applies "
                        "(deterministic checks; no new claude audit)…",
                        file=sys.stderr,
                    )
                    try:
                        current_findings = _open_findings_now()
                    except ReviewError as exc:
                        # apply_finding's edit left the plan with an unmatched
                        # opening code fence — parse_plan above didn't catch
                        # this (the YAML/frontmatter is fine), but
                        # collect_deterministic_findings's own guard does.
                        # Nothing upstream of this loop iteration re-validates
                        # fence safety after an edit, so this must be caught
                        # here or it crashes the whole audit uncaught.
                        error(
                            f"plan has an unmatched opening code fence after "
                            f"apply_finding: {exc}"
                        )
                        return _halt(
                            "plan has an unmatched opening code fence after "
                            "apply_finding"
                        )
                    record_iteration(state, (r.id for r in current_findings))
                    introduced, resolved, _persisted = finding_set_delta(
                        state.previous_finding_ids, state.current_finding_ids
                    )
                    print(
                        f"plan-tool: iteration {state.iteration} done · "
                        f"✓{len(resolved)} resolved · +{len(introduced)} new · "
                        f"{len(state.current_finding_ids)} open remain",
                        file=sys.stderr,
                    )
                    # Update has_blocking_findings so should_continue can fire
                    # ``no_blocking_findings`` when only nit/info remains.
                    state.has_blocking_findings = any(
                        is_blocking(r.severity) for r in current_findings
                    )

                # End-of-loop: emit a follow-up plan stub if any out-of-scope
                # edits were buffered, so reverted code work is captured and
                # documentation drift is highlighted for human review.
                _emit_scope_guard_plan(
                    scope_buffer,
                    plan_path=path,
                    plan_slug=args.name,
                    ctx=ctx,
                )

        # Hand the once-computed conceptual audit to the report below so
        # it doesn't spend a second claude call. Under #85 the loop applies
        # NEITHER conceptual source, so ``applied_fingerprints`` (deterministic
        # ids only) can't match a plan-correctness rec — this filter is a
        # defensive no-op (mirrors ``_audit_recs_for_report``) kept so a future
        # change that does apply correctness still drops it from the report
        # rather than double-listing it against the ``## Applied`` section.
        _iterate_audit_recs = [
            r for r in _audit_recs
            if not (
                r.source == "plan-correctness"
                and r.id in applied_fingerprints
            )
        ]
        _loop_iterations = state.iteration

    return _IterateOutcome(
        applied_outcomes=_applied_outcomes,
        deferred_recs=_deferred_recs,
        stop_reason=_loop_stop_reason,
        iterations=_loop_iterations,
        audit_recs=_iterate_audit_recs,
        plan=plan,
        budget=_audit_budget,
        conceptual_bar_blocking_ids=_conceptual_bar_blocking_ids,
        audit_incomplete=_audit_incomplete,
        audit_shape_advisory=_iterate_audit_advisory,
        audit_shape_advisory_checkpoint_saved=_audit_advisory_checkpoint_saved,
        audit_input_snapshot=audit_input_snapshot,
        audit_stage=sampled_audit_stage,
        audit_capture_failed=audit_capture_failed or audit_input_snapshot is None,
        resumed_from_sampler_checkpoint=_resumed_from_sampler_checkpoint,
    )


def _render_completeness_json(
    args,
    det: _DeterministicReport,
    audit_recs,
    *,
    has_blocking: bool,
    budget=None,
    halt_reason: str | None = None,
    early_exit_code: int | None = None,
    audit_shape_advisory_display=None,
    plan_mass=None,
    audit_stage: str = "detail",
    audit_incomplete: bool = False,
    conceptual_bar_blocking_ids: tuple[str, ...] = (),
    stop_reason: str | None = None,
    finalize_not_clean: bool | None = None,
    qualified_result=None,
) -> int:
    """Emit the machine-readable ``--json`` payload and return the process
    rc. ``has_blocking`` is the ``_completeness_has_blocking_findings``
    verdict computed once by the orchestrator (so this leaf needs no
    back-reference to the command module); it lands in the payload as
    ``has_blocking_findings`` and, under ``--fail-on-findings``, mirrors
    into the exit code.

    ``budget`` mirrors the coverage-confidence block already present in
    the markdown report. When the iterate loop halted, ``halt_reason`` /
    ``early_exit_code`` mirror the ``## Halt`` section in the markdown report;
    ``early_exit_code`` wins over ``--fail-on-findings`` for the process rc.
    """
    import json as _json

    out = {
        "plan": args.name,
        "checks": {
            "correctness": {
                "path_style": (
                    None
                    if det.path_style_hint is None
                    else {
                        "missing_count": det.path_style_hint.missing_count,
                        "total": det.path_style_hint.total,
                        "ratio": det.path_style_hint.ratio,
                        "examples": det.path_style_hint.examples,
                    }
                ),
                "dep_issues": [
                    {
                        "step_id": d.step_id,
                        "depends_on": d.depends_on,
                        "reason": d.reason,
                    }
                    for d in det.dep_issues
                ],
            },
            "body_sections": [
                {
                    "severity": "medium",
                    "kind": i.kind,
                    "section": i.section,
                    "details": i.details,
                }
                for i in det.body_issues
            ],
            "detail_coverage": [
                {
                    "severity": "medium",
                    "kind": i.kind,
                    "step_id": i.step_id,
                    "detail_path": i.detail_path,
                }
                for i in det.detail_cov_issues
            ],
            "detail_body": [
                {
                    "severity": "medium",
                    "kind": i.kind,
                    "step_id": i.step_id,
                    "section": i.section,
                    "detail_path": i.detail_path,
                }
                for i in det.detail_body_issues
            ],
            "files_coherence": [
                {
                    "severity": (
                        "info" if i.kind == "detail_only" else "nit"
                    ),
                    "kind": i.kind,
                    "step_id": i.step_id,
                    "path": i.path,
                    "near_match": i.near_match,
                }
                for i in det.files_coh_issues
            ],
            "lessons": [
                {
                    "severity": "medium",
                    "kind": i.kind,
                    "step_id": i.step_id,
                    "lessons_path": i.lessons_path,
                }
                for i in det.lessons_issues
            ],
            "data_contract": [
                {
                    "severity": r.severity,
                    "source": r.source,
                    "id": r.id,
                    "anchor": r.anchor,
                    "title": r.title,
                    "confidence": confidence_value(r.confidence),
                    "message": r.body,
                    "payload": det.data_contract_payloads.get(r.id),
                }
                for r in det.data_contract_recs
            ],
            "plan_audit": [
                {
                    "axis": (
                        "correctness"
                        if r.source == "plan-correctness"
                        else "completeness"
                    ),
                    "severity": r.severity,
                    "id": r.id,
                    "title": r.title,
                    "confidence": confidence_value(r.confidence),
                    "body": r.body,
                    "restated_property": restated_property_or_none(r),
                }
                for r in audit_recs
            ],
            # Advisory smells carry their ``source`` tokens (``feature-ref`` /
            # ``self-referential`` / ``claim-vs-delivery`` and the cross-step
            # ``granularity-split`` / ``granularity-merge`` advice), not a
            # correctness/completeness axis — so key on ``source``. Never an
            # input to ``has_blocking_findings``.
            "smells": [
                {
                    "severity": r.severity,
                    "source": r.source,
                    "id": r.id,
                    "title": r.title,
                    "confidence": confidence_value(r.confidence),
                    "body": r.body,
                }
                for r in det.smell_recs
            ],
            # Blocking-capable plan-internal consistency findings — keyed on
            # ``source`` like ``smells``, but this bucket *does* feed
            # ``has_blocking_findings`` (at medium+).
            "self_consistency": [
                {
                    "severity": r.severity,
                    "source": r.source,
                    "id": r.id,
                    "title": r.title,
                    "confidence": confidence_value(r.confidence),
                    "body": r.body,
                }
                for r in det.self_consistency_recs
            ],
            # Failed purity-scan coverage — ``high`` errors; feed
            # ``has_blocking_findings``. Not smells: a failed battery must
            # not read as advisory / low-yield.
            "purity_coverage": [
                {
                    "severity": r.severity,
                    "source": r.source,
                    "id": r.id,
                    "title": r.title,
                    "confidence": confidence_value(r.confidence),
                    "body": r.body,
                }
                for r in det.purity_coverage_recs
            ],
        },
        "coverage": _project_audit_coverage_for_public_output(budget),
        "qualified_result": (
            qualified_result.as_dict()
            if hasattr(qualified_result, "as_dict")
            else qualified_result
        ),
    }
    if audit_shape_advisory_display is not None:
        from plan_tool.completeness_report import audit_shape_advisory_json

        out["audit_shape_advisory"] = audit_shape_advisory_json(
            audit_shape_advisory_display
        )
    if plan_mass is not None:
        out["plan_mass"] = plan_mass
    out["stage"] = audit_stage
    out["audit_incomplete"] = audit_incomplete
    out["conceptual_bar_blocking_ids"] = (
        None if audit_incomplete else list(conceptual_bar_blocking_ids)
    )
    out["has_blocking_findings"] = has_blocking
    if stop_reason is not None:
        out["stop_reason"] = stop_reason
    if halt_reason is not None:
        out["halt_reason"] = halt_reason
    if early_exit_code is not None:
        out["early_exit_code"] = early_exit_code
    print(_json.dumps(out, indent=2, sort_keys=False))
    # The audit completed -- exit 0. ``has_blocking_findings`` in the
    # payload is what a headless caller gates on, not the process code.
    # --fail-on-findings additionally mirrors finalize-not-clean into the
    # rc so a CI step can gate on the exit code instead of parsing JSON.
    # An iterate halt rc wins over both.
    if early_exit_code is not None:
        return early_exit_code
    if getattr(args, "fail_on_findings", False):
        blocks = (
            finalize_not_clean
            if finalize_not_clean is not None
            else (audit_incomplete or has_blocking)
        )
        if blocks:
            return 1
    return 0


def _project_audit_coverage_for_public_output(coverage_input) -> dict[str, object]:
    """Project persisted-or-fresh coverage without turning unknown into clean."""
    from plan_tool.review_persistence import project_audit_coverage

    projected = project_audit_coverage(coverage_input)
    if projected["evidence_status"] != "unknown-legacy":
        return projected
    # These phase helpers historically accepted partial fresh budget maps from
    # direct in-process callers. Keep their display behavior stable, but never
    # allow this compatibility lane to reach a sidecar: persistence requires
    # the strict normalized producer object above.
    if not isinstance(coverage_input, dict) or not isinstance(
        coverage_input.get("budget_limited"), bool
    ):
        return projected
    confirmation_kind = coverage_input.get("confirmation_kind")
    if confirmation_kind not in {None, "confirmed-dry", "confirmed-low-yield"}:
        confirmation_kind = None
    fallback = {
        "evidence_status": "observed",
        "budget_limited": coverage_input["budget_limited"],
        "passes_used": coverage_input.get("passes_used"),
        "cap": coverage_input.get("cap"),
        "recommendation_kind": None,
        "recommended_passes": None,
        "recommendation_advice": None,
        "confirmation_kind": confirmation_kind,
    }
    if "early_stop_reason" in coverage_input:
        fallback["early_stop_reason"] = coverage_input["early_stop_reason"]
    return fallback


def _render_coverage_confidence_markdown(coverage_input) -> Optional[str]:
    """Render the one coverage-confidence callout from the shared projection."""
    from plan_tool.review_persistence import (
        audit_coverage_withholds_final_findings_sidecar,
    )

    coverage = _project_audit_coverage_for_public_output(coverage_input)
    if coverage["evidence_status"] == "unknown-legacy":
        # ``None`` remains the historical "no coverage input supplied" marker
        # for internal callers. A supplied malformed/legacy value is explicit
        # unknown evidence and must not read as a clean conceptual audit.
        if coverage_input is None:
            return None
        return (
            "> **Coverage confidence unknown:** this reused legacy sidecar "
            "lacks saved conceptual-audit evidence, so its coverage verdict "
            "cannot be confirmed."
        )
    if audit_coverage_withholds_final_findings_sidecar(coverage):
        return (
            "> **Coverage unconfirmed:** conceptual sampling ended early after "
            f"a terminal plan quota at {coverage['passes_used']} pass(es) — "
            "this audit did not confirm coverage."
        )
    if coverage["budget_limited"]:
        return (
            "> **Coverage unconfirmed:** this audit was budget-limited at "
            f"{coverage['passes_used']} pass(es) (still discovering at the "
            "pass cap) — a clean/`converging` verdict here is not fully "
            "validated."
        )
    if coverage["confirmation_kind"] == "confirmed-low-yield":
        # BACKLOG #125 — converged, but not on a literal zero-new pass: the
        # final streak kept discovering findings, all advisory (nit/info).
        # Distinct from the budget-limited callout above so it isn't mistaken
        # for either an unconverged run or an exhaustively clean one.
        return (
            "> **Converged (low-yield):** this audit stopped at "
            f"{coverage['passes_used']} pass(es) once only advisory "
            "(nit/info) findings remained — no material (medium+) finding "
            "resurfaced. Some listed advisory findings may be residual "
            "precision noise the sampler never fully explored."
        )
    return None


def _render_grouped_report(
    plan,
    args,
    det: _DeterministicReport,
    *,
    correctness_recs,
    conceptual_recs,
    audit_recs,
    iterate_enabled: bool,
    bundle_status=None,
    budget=None,
    audit_shape_advisory_display=None,
    resumed_from_sampler_checkpoint: bool = False,
    qualified_result=_QUALIFIED_RESULT_UNSET,
    is_pre_apply_checkpoint: bool = False,
    verdict=ABSENT_BLOCKING_VERDICT,
) -> str:
    """Assemble the grouped Markdown report as a single string.

    ``verdict`` is the finalize gate's blocking verdict; omitted reads as
    ``absent`` (no stage transition offered).

    It's persisted to a reusable report file in every mode; in
    audit-only mode it's also printed to stdout for interactive
    inspection, while --iterate prints a concise summary instead so
    the long automated run doesn't bury its result.
    """
    _g: list[str] = []
    _p = _g.append
    _p(f"## Plan completeness: {plan.title}")
    _p("")
    if qualified_result is not _QUALIFIED_RESULT_UNSET:
        from plan_tool.completeness_report import render_qualified_result_markdown

        _p(
            render_qualified_result_markdown(
                qualified_result,
                is_pre_apply_checkpoint=is_pre_apply_checkpoint,
                heading="###",
            )
        )
        _p("")
    if resumed_from_sampler_checkpoint:
        _p("### Audit provenance")
        _p("")
        _p(
            "This audit resumed from a durable sampler pass boundary. "
            "This provenance does not change its findings, coverage, or "
            "qualified result."
        )
        _p("")
    if bundle_status is not None and bundle_status.is_bare:
        kind = "bare" if bundle_status.is_fully_bare else "partially-detailed"
        _p(
            "_Two layers: deterministic checks confirm the plan document is "
            "well-formed (sections, files, deps); the conceptual audit asks "
            "claude whether the plan's own ideas are correct, complete, and "
            "unambiguous. "
            f"**Bare-plan audit — {bundle_status.detailed_count} of "
            f"{bundle_status.total} step(s) detailed ({kind}):** bare steps are "
            "judged at the plan/concept level only (no detail bundle to ground "
            "against); detail/code-grounded findings require a detail bundle._"
        )
    else:
        _p(
            "_Two layers: deterministic checks confirm the plan document is "
            "well-formed (sections, files, deps); the conceptual audit asks "
            "claude whether the plan's own ideas are correct, complete, and "
            "unambiguous, "
            "grounded in the per-step detail bundle and the code at HEAD._"
        )
    _p("")
    coverage_confidence = _render_coverage_confidence_markdown(budget)
    if coverage_confidence is not None:
        _p(coverage_confidence)
        _p("")

    if audit_shape_advisory_display is not None:
        from plan_tool.completeness_report import render_audit_shape_advisory_markdown

        _p(
            render_audit_shape_advisory_markdown(
                audit_shape_advisory_display, heading="###"
            )
        )
        _p("")

    correctness_lines: list[str] = []
    if det.path_style_hint is not None:
        pct = round(det.path_style_hint.ratio * 100)
        correctness_lines.append(
            f"- CRITICAL: {det.path_style_hint.missing_count} of "
            f"{det.path_style_hint.total} declared file paths don't resolve "
            f"under repo root ({pct}% mismatch)"
        )
    for d in det.dep_issues:
        sev = "CRITICAL" if d.reason == "unknown" else "WARN"
        correctness_lines.append(
            f"- {sev}: step {d.step_id} depends on step {d.depends_on} "
            f"which is {d.reason}"
        )
    # Conceptual-correctness findings (claude) join the correctness group:
    # an unsound or contradictory concept is a structural blocker, same
    # band as a broken dependency. Render the *full* body, not ``rec.title``
    # (the body's first line clipped to 120 chars), so an over-long finding
    # doesn't read truncated mid-thought; the ``[anchor-slug]`` cross-
    # references the address command in the report's conceptual section.
    for rec in correctness_recs:
        correctness_lines.append(format_finding_bullet(rec, rec.anchor or ""))
        restated = restated_property_or_none(rec)
        if restated:
            correctness_lines.append(f"  - {RESTATED_PROPERTY_LABEL}: {restated}")
    # Always render the Correctness group, even when empty, so a reader can
    # tell "the audit ran and found the concepts sound" apart from "the
    # correctness layer wasn't emitted" (report defect #3). check_plan_audit
    # now guarantees the layer is sampled; this guarantees it's reported.
    _p("### Correctness (run these first)")
    _p("")
    _p(
        "_Verified: file paths resolve, dependencies are coherent, and "
        "the plan's stated concepts are internally sound._"
    )
    _p("")
    if correctness_lines:
        for line in correctness_lines:
            _p(line)
    else:
        _p("- _(none — paths resolve, deps coherent, concepts sound)_")
    _p("")

    if det.body_issues:
        _p("### Plan sections")
        _p("")
        _p(
            "_Required headings in the plan document are missing or still "
            "placeholder. `## Acceptance criteria` here is the plan's own "
            "section — not a Jira story's acceptance criteria._"
        )
        _p("")
        for issue in det.body_issues:
            _p(
                f"- {issue.kind.upper()}: plan section `## {issue.section}` "
                f"— {issue.details}"
            )
        _p("")

    if det.detail_cov_issues:
        _p("### Detail coverage")
        _p("")
        for issue in det.detail_cov_issues:
            _p(
                f"- WARN: step {issue.step_id} detail "
                f"`{issue.detail_path}` declared but missing on disk"
            )
        _p("")

    if det.detail_body_issues:
        _p("### Detail file sections")
        _p("")
        _p(
            "_Required headings in each step's detail file are missing or "
            "placeholder. `## Acceptance criteria` here is the detail "
            "file's section — not a Jira story's acceptance criteria._"
        )
        _p("")
        for issue in det.detail_body_issues:
            verb = "missing" if issue.kind == "missing" else "empty/placeholder"
            _p(
                f"- WARN: step {issue.step_id} detail `{issue.detail_path}` "
                f"— section `## {issue.section}` {verb}"
            )
        _p("")

    if det.files_coh_issues:
        _p("### Files coherence")
        _p("")
        for issue in det.files_coh_issues:
            if issue.kind == "detail_only":
                _p(
                    f"- INFO: step {issue.step_id} detail cites "
                    f"`{issue.path}` resembling declared "
                    f"`{issue.near_match}` (typo/stale path?)"
                )
            else:
                _p(
                    f"- NIT: step {issue.step_id} declared `{issue.path}` "
                    "not mentioned in detail"
                )
        _p("")

    if det.lessons_issues:
        _p("### Lessons coverage")
        _p("")
        for issue in det.lessons_issues:
            if issue.kind == "missing_file":
                _p(
                    f"- WARN: lessons file `{issue.lessons_path}` missing "
                    "but plan has done steps"
                )
            else:
                _p(
                    f"- WARN: step {issue.step_id} done but no entry in "
                    f"`{issue.lessons_path}`"
                )
        _p("")

    if det.data_contract_recs:
        _p("### Data contract")
        _p("")
        _p(
            "_Persisted data shapes in code and `DATA_CONTRACT.md` have "
            "drifted. Update the named contract section before treating the "
            "plan as complete._"
        )
        _p("")
        for rec in det.data_contract_recs:
            _p(format_finding_bullet(rec, rec.anchor or rec.id))
        _p("")

    if conceptual_recs:
        _p("### Conceptual completeness")
        _p("")
        _p(
            "_Coverage gaps in the plan's own ideas that the detail bundle "
            "and code at HEAD don't already resolve: orphaned concepts, "
            "uncovered risks, dangling acceptance criteria, missing edge "
            "cases._"
        )
        _p("")
        # The bullet renders the *full* finding body (not the clipped
        # ``rec.title``); the ``[anchor-slug]`` cross-references the address
        # command in the report's dedicated conceptual section.
        for rec in conceptual_recs:
            _p(format_finding_bullet(rec, rec.anchor or ""))
        _p("")

    if det.smell_recs:
        _p("### Smells (advisory)")
        _p("")
        _p(
            "_Advisory plan-structure heuristics (brittle feature refs, "
            "self-referential steps, cross-step granularity split/merge "
            "advice, per-step mixed refactor + feature (MIXED-STEP) split "
            "findings, and claim-vs-delivery — a deliverable the acceptance "
            "prose claims that no step delivers), plus unsigned concept "
            "deferral reminders. Reported for a human to act "
            "on; never auto-applied and never block the run._"
        )
        _p("")
        for rec in det.smell_recs:
            _p(format_finding_bullet(rec, rec.anchor or ""))
        _p("")

    if det.self_consistency_recs:
        _p("### Self-consistency")
        _p("")
        _p(
            "_Blocking-capable plan-internal consistency findings (a "
            "medium+ finding here blocks, unlike the advisory smells above): "
            "claims the plan makes that its own steps don't deliver, or "
            "deliverables no step consumes, including signed-off concepts "
            "with neither an explicit committed owner nor a valid structured "
            "deferral, plus a plan or step declaring no `intent`._"
        )
        _p("")
        for rec in det.self_consistency_recs:
            _p(format_finding_bullet(rec, rec.anchor or ""))
        _p("")

    if det.purity_coverage_recs:
        _p("### Purity coverage")
        _p("")
        _p(
            "_A per-step MIXED-STEP purity scan either produced no verdict "
            "(timeout, empty reply, or truncated parse) or was skipped after "
            "the full purity budget expired. Coverage failure is an error — it "
            "blocks — not an advisory smell. Re-run with `--purity`; raise "
            "`PLAN_TOOL_PURITY_CLAUDE_TIMEOUT` for failed calls or "
            "`PLAN_TOOL_PURITY_SCAN_BUDGET` for skipped scans._"
        )
        _p("")
        for rec in det.purity_coverage_recs:
            _p(format_finding_bullet(rec, rec.anchor or ""))
        _p("")

    has_any = (
        det.path_style_hint is not None
        or det.dep_issues
        or det.body_issues
        or det.detail_cov_issues
        or det.detail_body_issues
        or det.files_coh_issues
        or det.lessons_issues
        or det.data_contract_recs
        or det.smell_recs
        or det.self_consistency_recs
        or det.purity_coverage_recs
        or audit_recs
    )
    if not has_any:
        _p("_(no completeness issues detected)_")
        _p("")

    # Close the report with the concrete follow-up command for what was
    # found, so the reader leaves with a next action instead of
    # re-deriving the audit → apply workflow. Condition-driven: each
    # bullet appears only when the finding class it addresses did.
    _p("### Suggested next steps")
    _p("")
    _bare_plan = bool(
        bundle_status is not None and getattr(bundle_status, "is_bare", False)
    )
    if verdict is None:
        verdict = ABSENT_BLOCKING_VERDICT  # same as the other readers: None holds the stage
    _gaps = next_step_gaps(
        verdict, correctness=correctness_recs, advisory_conceptual=conceptual_recs
    )
    _correctness_apply = (bool(_gaps.close_correctness)) and (_bare_plan)
    # No apply verb targets a conceptual-correctness gap (#85), so the
    # structural bullet's auto-apply wording names deterministic findings only.
    _structural_findings_noun = "deterministic finding(s)"
    _structural = bool(
        det.path_style_hint is not None
        or det.dep_issues
        or det.body_issues
        or (det.detail_body_issues and not _bare_plan)
        or (det.files_coh_issues and not _bare_plan)
        or det.lessons_issues
        or det.data_contract_recs
    )
    _missing_detail = any(
        i.kind == "missing_on_disk" for i in det.detail_cov_issues
    )
    _detail_level = bool(
        _missing_detail or det.detail_body_issues or det.files_coh_issues
    )
    # Deliberately its own flag rather than a member of ``_structural``: these
    # findings block but no apply verb targets them, so the structural bullet's
    # `--iterate` / walk suggestions would name a command that cannot close them.
    from plan_tool.convergence import is_blocking
    from plan_tool.review import INTENT_PRESENCE_SOURCE

    _blocking_sc = [
        rec for rec in det.self_consistency_recs if is_blocking(rec.severity)
    ]
    _blocking_purity = [
        rec for rec in det.purity_coverage_recs if is_blocking(rec.severity)
    ]
    _next_steps: list[str] = []
    if _structural:
        if iterate_enabled:
            # The convergence loop already ran; what's left resisted
            # auto-apply or was deferred — point at the interactive walk.
            _iterate_findings_noun = (
                "remaining finding(s)"
                if _correctness_apply
                else "finding(s)"
            )
            _next_steps.append(
                f"- `plan-tool reconcile-plan-walk {args.name}` — interactively "
                f"review the {_iterate_findings_noun} the iterate loop left open."
            )
        elif not _verdict_offers_stage(verdict):
            # The closing re-audit below is this same command; name it once.
            _next_steps.append(
                f"- The convergence loop in the re-audit below auto-applies the "
                f"{_structural_findings_noun} above."
            )
        else:
            _next_steps.append(
                f"- `plan-tool completeness-audit {args.name} --iterate` — "
                "re-run with the convergence loop to auto-apply the "
                f"{_structural_findings_noun} above."
            )
    if _blocking_sc:
        # Name each source so the reader can find its findings above.
        _sc_sources = ", ".join(sorted({r.source for r in _blocking_sc}))
        _sc_fix = "make a session-directed edit to the plan"
        if any(r.source == INTENT_PRESENCE_SOURCE for r in _blocking_sc):
            _sc_fix = "add a one-line `intent:` to the plan or the named step(s)"
            if any(r.source != INTENT_PRESENCE_SOURCE for r in _blocking_sc):
                _sc_fix += ", and make a session-directed edit to the plan for the rest"
        _next_steps.append(
            f"- Close the {len(_blocking_sc)} blocking self-consistency "
            f"finding(s) above ({_sc_sources}) — {_sc_fix}. No apply verb "
            "targets them."
        )
    if _blocking_purity:
        _next_steps.append(
            f"- Re-run `plan-tool completeness-audit {args.name} --purity` "
            f"to clear the {len(_blocking_purity)} purity coverage error(s) "
            "above (raise `PLAN_TOOL_PURITY_CLAUDE_TIMEOUT` for failed calls "
            "or `PLAN_TOOL_PURITY_SCAN_BUDGET` for skipped scans). "
            "No apply verb targets them."
        )
    if _missing_detail and not _bare_plan:
        _next_steps.append(
            f"- `plan-tool detail {args.name}` — author detail files for "
            "the step(s) missing them."
        )
    if _correctness_apply:
        _next_steps.append(
            f"- Close the {len(_gaps.close_correctness)} conceptual-correctness "
            "gap(s) above through a session-directed edit to the plan body"
            + (
                " (the non-blocking completeness gaps stay informational "
                "until a detail bundle exists)."
                if _gaps.advisory_completeness
                else "."
            )
        )
    # The bare-plan correctness bullet above already covers its gaps.
    _next_steps.extend(
        f"- {step}"
        for step in _close_conceptual_steps(
            dc.replace(_gaps, close_correctness=())
            if _correctness_apply
            else _gaps,
            bare_plan=_bare_plan,
        )
    )
    _next_command, _next_description = next_stage_command(
        args.name, bundle_status, verdict=verdict,
    )
    if not _verdict_offers_stage(verdict):
        _covered_sources = {
            r.source
            for r in (
                *det.data_contract_recs,
                *_blocking_sc,
                *_blocking_purity,
            )
        }
        if _structural:
            _covered_sources |= {
                "path-style-mismatch", "deps", "body-completeness",
                "lessons-coverage",
            }
            if not _bare_plan:
                _covered_sources.add("detail-body")
        if _missing_detail and ((not _bare_plan)):
            _covered_sources.add("detail-coverage")
        _next_steps.extend(
            f"- {step}"
            for step in _blocking_deterministic_steps(
                verdict, covered_sources=_covered_sources
            )
        )
        _next_steps.append(
            f"- {reaudit_step(args.name, verdict)}"
        )
    elif _bare_plan and not _next_steps and (_detail_level or conceptual_recs):
        _next_steps.append(
            "- Detail-level and conceptual-completeness findings are "
            "reported in this bare-plan audit. Review plan-level gaps now; "
            "leave detail-only remedies for detail authoring. "
            f"`{_next_command}` — "
            f"{_next_description}."
        )
    elif _next_steps:
        _next_steps.append(f"- `{_next_command}` — {_next_description}.")
    elif has_any:
        _next_steps.append(
            "- The finding(s) above are advisory and hold back no stage — "
            f"`{_next_command}` — {_next_description}."
        )
    else:
        _next_steps.append(
            f"- No gaps to close — `{_next_command}` — {_next_description}."
        )
    _qualified_payload = (
        qualified_result.as_dict()
        if hasattr(qualified_result, "as_dict")
        else qualified_result
    )
    if _fresh_audit_required(
        _qualified_payload if isinstance(_qualified_payload, dict) else None,
        verdict,
        False,
    ):
        _reaudit, _note = _reaudit_command(args.name, verdict)
        _next_steps = [
            f"- `{_reaudit}` — run a fresh audit before reusing or applying "
            "saved findings.",
        ]
    for _line in _next_steps:
        _p(_line)
    _p("")


    return "\n".join(_g)


def _persist_and_present_report(
    plan,
    path: Path,
    args,
    ctx,
    *,
    iterate_enabled: bool,
    outcome: _IterateOutcome,
    correctness_recs,
    conceptual_recs,
    grouped_md: str,
    smell_recs=(),
    data_contract_recs=(),
    data_contract_payloads=None,
    code_drifted: bool = False,
    skip_sidecar_write: bool = False,
    halt_reason: Optional[str] = None,
    quiet_presentation: bool = False,
    suppress_plan_mass: bool = False,
    bundle_status=None,
    audit_shape_advisory=None,
    audit_shape_advisory_display=None,
    audit_coverage=None,
    is_pre_apply_checkpoint: bool = False,
    audit_input_snapshot=None,
    audit_stage: Optional[str] = None,
    verdict=None,
) -> Optional[Path]:
    """Persist the full report (every mode) and either print it (audit-
    only) or a concise summary (--iterate). ``verdict`` is the finalize
    gate's blocking verdict handed to every next-step reader; ``None``
    (the pre-apply checkpoint, which has no gate result) reads as
    ``absent``. The report states why each
    non-applied finding wasn't addressed — especially the advisory
    conceptual-completeness gaps. Returns the saved report path (or
    ``None`` when the write failed).

    ``skip_sidecar_write`` short-circuits the ``write_completeness_report``
    → ``save_review`` persistence step only — set when an audit-only run
    reused a saved audit, so the newest sidecar pointer stays stable and
    the reports dir does not grow. Report rendering/presentation is
    unaffected (``report_path`` stays ``None``, so the audit-only path
    omits the "saved to" line).

    A terminal plan-quota in ``audit_coverage`` still writes and presents the
    Markdown report, but omits its ordinary final findings sidecar. This is
    intentionally separate from ``skip_sidecar_write``.

    ``code_drifted`` (code moved under the plan since its last audit) is
    threaded to both the persisted report (``build_report_md``) and the
    console next-step commands so each can lead with a ``reconcile-plan``
    rebase suggestion when a critical/high finding is present (BACKLOG #65).

    ``audit_coverage`` accepts the selected completed-audit provenance for
    the sibling sidecar. The completeness writer validates and normalizes it;
    the caller still owns choosing fresh versus reused evidence.

    ``suppress_plan_mass`` skips computing the plan-mass snapshot — set on
    the pre-apply checkpoint delegation (``write_pre_apply_audit_checkpoint``)
    so only the final report computes it, keeping the snapshot out of the
    rarely-read checkpoint report.

    ``is_pre_apply_checkpoint`` marks the saved sidecar as crash-recovery
    evidence rather than a converged result. Only that same checkpoint
    delegation sets it: every other caller — including
    ``finalize_completeness_run`` after an iterative loop — keeps the final
    default, so the role names the producer, never the run's mode.

    """
    from plan_tool.cli.console import _print_next_steps
    from plan_tool.completeness_report import (
        build_report_md,
        console_summary,
        prepare_audit_shape_advisory_display,
        suggested_next_step_commands,
        write_completeness_report,
    )
    from plan_tool.fingerprint import (
        audit_input_detail_fingerprint,
        compute_code_fingerprint,
    )
    from plan_tool.review_persistence import (
        audit_coverage_withholds_final_findings_sidecar,
        compute_plan_fingerprint,
    )

    withhold_final_findings_sidecar = (
        not is_pre_apply_checkpoint
        and audit_coverage_withholds_final_findings_sidecar(audit_coverage)
    )
    if audit_shape_advisory_display is None:
        audit_shape_advisory_display = prepare_audit_shape_advisory_display(
            audit_shape_advisory,
            plan=plan,
            plan_path=path,
            repo_root=ctx.repo_root,
        )
    report_advisory_display = (
        None
        if "Audit shape advisory" in grouped_md
        else audit_shape_advisory_display
    )
    advisory_conceptual = conceptual_recs
    deferred_recs = list(outcome.deferred_recs.values())
    # The final report needs a concept-specific non-appliable disposition,
    # including in audit-only mode where the iterate outcome has no deferred
    # collector. Re-run the pure reader here so the grouped report, JSON path,
    # and saved artifact all use the same authoritative predicate.
    from plan_tool.review import check_concept_coverage

    concept_link_recs = [
        rec
        for rec in check_concept_coverage(plan, path, plan_name=args.name)
        if rec.source == "concept-coverage"
    ]
    deferred_ids = {rec.id for rec in deferred_recs}
    deferred_recs.extend(
        rec for rec in concept_link_recs if rec.id not in deferred_ids
    )
    # Conceptual correctness has its own report bucket, not loop-unreached gaps.
    open_findings: list = []

    report_path = None
    if not skip_sidecar_write:
        try:
            # Preserve both conceptual axes and the replayable purity-split
            # subset for saved readers; other structural smells stay advisory.
            from plan_tool.granularity import GRANULARITY_SPLIT_SOURCE

            sidecar_recs = None
            if not withhold_final_findings_sidecar:
                mixed_split_recs = [
                    r for r in smell_recs
                    if r.source == GRANULARITY_SPLIT_SOURCE
                    and r.severity == "medium"
                ]
                sidecar_recs = (
                    list(correctness_recs)
                    + list(conceptual_recs)
                    + list(data_contract_recs)
                    + concept_link_recs
                    + mixed_split_recs
                )
            # Keep the legacy combined fingerprint as report metadata. The
            # sampled audit revision below alone decides plan/detail freshness.
            plan_fp = compute_plan_fingerprint(path)
            code_fp = compute_code_fingerprint(plan, path, ctx.repo_root)
            detail_bundle_fp = (
                audit_input_detail_fingerprint(
                    audit_input_snapshot, ctx.repo_root
                )
                if audit_input_snapshot is not None
                else None
            )
            try:
                plan_rel = path.resolve().relative_to(
                    ctx.repo_root.resolve()
                ).as_posix()
            except ValueError:
                plan_rel = str(path)
            plan_mass_snapshot = None
            plan_mass_first_step_count = None
            plan_mass_first_detail_bytes = None
            if not suppress_plan_mass:
                from plan_tool.completeness_report import (
                    compute_plan_mass_best_effort,
                    first_saved_plan_mass,
                )
                from plan_tool.locator import slug_from_filename

                plan_mass_snapshot = compute_plan_mass_best_effort(
                    plan, path, ctx.repo_root
                )
                # No point scanning + loading every saved sidecar for a
                # delta baseline that build_report_md will never render —
                # plan_mass=None omits the whole section (see its docstring).
                if plan_mass_snapshot is not None:
                    try:
                        first_mass = first_saved_plan_mass(
                            slug_from_filename(path), ctx.repo_root, path
                        )
                    except Exception:
                        first_mass = None
                    if first_mass is not None:
                        plan_mass_first_step_count = first_mass.get("step_count")
                        plan_mass_first_detail_bytes = first_mass.get(
                            "detail_bundle_bytes"
                        )
            report_md = build_report_md(
                plan_title=plan.title,
                plan_name=args.name,
                iterate_enabled=iterate_enabled,
                stop_reason=outcome.stop_reason,
                iterations=outcome.iterations,
                applied=outcome.applied_outcomes,
                deferred=deferred_recs,
                advisory_conceptual=advisory_conceptual,
                open_findings=open_findings,
                grouped_report_md=grouped_md,
                correctness=correctness_recs,
                smells=list(smell_recs),
                plan=plan,
                code_drifted=code_drifted,
                halt_reason=halt_reason,
                bundle_status=bundle_status,
                audit_shape_advisory_display=report_advisory_display,
                plan_mass=plan_mass_snapshot,
                plan_mass_first_step_count=plan_mass_first_step_count,
                plan_mass_first_detail_bytes=plan_mass_first_detail_bytes,
                qualified_result=outcome.qualified_result,
                is_pre_apply_checkpoint=is_pre_apply_checkpoint,
                verdict=verdict,
            )
            plan_mass_payload = None
            if plan_mass_snapshot is not None:
                from plan_tool.completeness_report import plan_mass_to_json

                plan_mass_payload = plan_mass_to_json(plan_mass_snapshot)
            # Prefer the caller's already-resolved bundle status over
            # re-deriving inside ``write_completeness_report`` (avoids a
            # second parse and keeps stage aligned with the run just finished).
            # ``plan=plan`` (BACKLOG #166) reuses this same already-parsed
            # plan for step_ids too, instead of write_completeness_report
            # parsing its own copy — keeping step_ids and plan_fp (just
            # above) describing the same read.
            report_path = write_completeness_report(
                path, report_md,
                repo_root=ctx.repo_root,
                recommendations=sidecar_recs,
                plan_fingerprint=plan_fp,
                code_fingerprint=code_fp,
                detail_bundle_fingerprint=detail_bundle_fp,
                plan=plan,
                plan_rel_path=plan_rel,
                data_contract_payloads=data_contract_payloads or {},
                audit_shape_advisory=audit_shape_advisory,
                audit_coverage=audit_coverage,
                is_pre_apply_checkpoint=is_pre_apply_checkpoint,
                plan_mass=plan_mass_payload,
                audit_stage=audit_stage,
                qualified_result=(
                    None
                    if is_pre_apply_checkpoint
                    else outcome.qualified_result
                ),
                checkpoint_audit_revision=(
                    audit_input_snapshot.revision
                    if is_pre_apply_checkpoint and audit_input_snapshot is not None
                    else None
                ),
                audit_stage_is_sampled=True,
            )
        except OSError as exc:
            warn(
                f"could not write completeness report: {exc}"
            )

    if quiet_presentation and report_path is not None:
        try:
            display = report_path.resolve().relative_to(ctx.repo_root.resolve())
        except ValueError:
            display = report_path
        info(f"completeness report saved to {display}")
    elif iterate_enabled:
        # --iterate: concise result to stdout; full detail is in the file.
        print(
            console_summary(
                plan_name=args.name,
                iterate_enabled=True,
                stop_reason=outcome.stop_reason,
                iterations=outcome.iterations,
                applied=outcome.applied_outcomes,
                deferred=deferred_recs,
                advisory_conceptual=advisory_conceptual,
                open_findings=open_findings,
                report_path=report_path
                if report_path is not None
                else Path("(unwritten)"),
                plan=plan,
                correctness=correctness_recs,
                bundle_status=bundle_status,
                audit_shape_advisory_display=audit_shape_advisory_display,
                resumed_from_sampler_checkpoint=(
                    outcome.resumed_from_sampler_checkpoint
                ),
                qualified_result=outcome.qualified_result,
                verdict=verdict,
            )
        )
        # The disposition next-steps (apply / split / re-audit) as clean
        # (command, description) tuples. When a parent command (detail /
        # split via ``_run_completeness_tail``) passes a ``_next_steps_sink``
        # list on ``args``, hand them up so the parent merges them into its
        # single pipeline block instead of printing a second one here.
        # Standalone (no sink): print our own clean block, falling back to the
        # shared stage-aware transition when nothing is outstanding.
        next_cmds = suggested_next_step_commands(
            plan_name=args.name,
            applied=outcome.applied_outcomes,
            deferred=deferred_recs,
            advisory_conceptual=advisory_conceptual,
            open_findings=open_findings,
            plan=plan,
            code_drifted=code_drifted,
            bundle_status=bundle_status,
            correctness=correctness_recs,
            qualified_result=outcome.qualified_result,
            is_pre_apply_checkpoint=is_pre_apply_checkpoint,
            verdict=verdict,
            # A parent that takes the sink appends the stage itself.
            include_stage=not isinstance(
                getattr(args, "_next_steps_sink", None), list
            ),
        )
        sink = getattr(args, "_next_steps_sink", None)
        if isinstance(sink, list):
            sink.extend(next_cmds)
        else:
            _print_next_steps("Next steps:", next_cmds)
    else:
        # Audit-only: the grouped report stays on stdout for interactive
        # reading, rendered console-friendly (markdown markers stripped —
        # an italic-wrapped path like `_…/report.md_` breaks terminal
        # click-to-open); the persisted copy keeps the raw markdown.
        print(render_markdown_for_console(grouped_md))
        if report_path is not None:
            print(f"\nCompleteness report saved to {report_path}")

    # An authoring parent owns the single next-steps block but needs the same
    # final decision that produced its disposition commands. Checkpoints are
    # recovery-only evidence and never leave this phase through that channel.
    result_sink = getattr(args, "_final_qualified_result_sink", None)
    if not is_pre_apply_checkpoint and isinstance(result_sink, list):
        result_sink.append(outcome.qualified_result)

    return report_path
