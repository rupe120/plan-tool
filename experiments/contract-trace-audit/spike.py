"""Spike for BACKLOG #66 — contract-trace / path-enumeration audit.

Thesis: the *control-flow / contract-coverage* findings the conceptual sampler
catches only stochastically (different samples → different cells of a path
matrix) can be caught **deterministically** by walking the grid once over the
plan's declared contracts. This spike validates the DOWNSTREAM half of that
claim — *given a contract model, does a grid-walk surface the real findings?* —
using the `escalate-structural-findings-to-split` plan's three known findings as
the fixture. It does NOT attempt the hard UPSTREAM half (extracting the contract
model from plan prose); that model is hand-encoded here (see LESSONS.md).

The three fixture findings (each found by a *separate* conceptual-audit run at
varying severity — the sampling variance #66 exists to kill):

  1. step8 plan-level KeyError — `escalate_to_split(step_id=None)` → `step_by_id(None)`
  2. step7 dropped outcomes  — the in-loop branch reads only `recommendation`,
     silently dropping `unsafe` (carries `blocking`) and `proposal-unusable`
  3. step3 gate leak         — the verdict literal rendered to a non-opt-in caller

A grid-walk over the declared contract finds ALL THREE in one deterministic
pass. Run: `python experiments/contract-trace-audit/spike.py`
"""

from __future__ import annotations

from dataclasses import dataclass, field

# --- the declared contract model (hand-extracted from the plan) ------------- #

# escalate_to_split's outcome enum (the plan's declared field discipline lives
# in POPULATED_FIELD for reference; the coverage check keys on whether the caller
# *surfaces* each outcome, not on a field-read heuristic — see LESSONS.md, the
# spike's own first iteration mis-modeled this).
OUTCOMES = ("applied", "recommended", "unsafe", "proposal-unusable", "step-missing")
POPULATED_FIELD = {
    "applied": "target_id",
    "recommended": "recommendation",
    "unsafe": "blocking",
    "proposal-unusable": None,
    "step-missing": None,
}
# Outcomes that name a *recognized structural target* and so MUST surface a
# signal to the operator (invariant 1: "never silently skipped"). step-missing is
# the one genuine no-target outcome, so it is exempt from the must-surface rule.
RECOGNIZED_TARGET = {"applied", "recommended", "unsafe", "proposal-unusable"}


@dataclass
class Caller:
    """A site that invokes escalate_to_split and consumes its result."""

    name: str
    # the outcomes this caller surfaces a signal for (handles, not silently drops)
    surfaces: frozenset[str]
    # can this caller dispatch a finding whose step_id is None (plan-level)?
    can_pass_none_step_id: bool
    # does it guard step_id is None before calling escalate_to_split?
    guards_none_step_id: bool


@dataclass
class PromptContract:
    """The shared apply-finding prompt's verdict-injection contract (step 3)."""

    # is the BLOCKED-STRUCTURAL verdict literal static in the template (leaks to
    # every caller) or injected via an opt-in extra_var (guard (a))?
    verdict_literal_static_in_template: bool


@dataclass
class ContractModel:
    callers: list[Caller]
    prompt: PromptContract
    finding: list[str] = field(default_factory=list)


# --- the grid-walk (deterministic checks over the contract) ----------------- #


def trace(model: ContractModel) -> list[str]:
    """Walk the (caller × outcome × step_id) grid + the prompt contract; return
    every contract violation. Deterministic — no sampling, full coverage."""
    findings: list[str] = []

    for caller in model.callers:
        # CHECK 1 — outcome coverage. Every recognized-target outcome must be
        # surfaced (invariant 1). An outcome the caller does not handle is a
        # silent drop — regardless of which result field carries its signal.
        for outcome in sorted(RECOGNIZED_TARGET):
            if outcome not in caller.surfaces:
                carrier = POPULATED_FIELD[outcome] or "a note (no result field)"
                findings.append(
                    f"[{caller.name}] outcome '{outcome}' is silently dropped — "
                    f"its signal ({carrier}) is never surfaced (invariant 1)"
                )

        # CHECK 2 — crash input. A caller that can hand a plan-level (step_id is
        # None) finding to escalate_to_split without guarding it hits
        # step_by_id(None) → KeyError.
        if caller.can_pass_none_step_id and not caller.guards_none_step_id:
            findings.append(
                f"[{caller.name}] passes step_id=None to escalate_to_split "
                f"(plan-level finding) → step_by_id(None) KeyError; no guard"
            )

    # CHECK 3 — prompt verdict-injection (guard (a)). A static literal renders to
    # non-opt-in callers (e.g. create), defeating the opt-in scoping.
    if model.prompt.verdict_literal_static_in_template:
        findings.append(
            "[prompt] BLOCKED-STRUCTURAL verdict literal is static in "
            "apply-finding.md → leaks to non-opt-in callers (guard (a) defeated)"
        )

    return findings


# --- the two encoded states: pre-fix (buggy) and post-fix (fixed) ----------- #


def pre_fix_model() -> ContractModel:
    """The escalate plan's contract as the audit first found it (buggy)."""
    return ContractModel(
        callers=[
            # step 7 (detail in-loop): item 4 handles `applied` (break+re-author),
            # item 5 reads `recommendation` (recommended) then `continue` for
            # everything else — so `unsafe` and `proposal-unusable` are dropped.
            Caller("step7-detail-loop",
                   surfaces=frozenset({"applied", "recommended"}),
                   can_pass_none_step_id=False, guards_none_step_id=False),
            # step 8 (review walk): maps every outcome to a status string, but the
            # builder-level verdict opt-in offers BLOCKED-STRUCTURAL to plan-level
            # findings too, and it did not guard step_id is None before escalating.
            Caller("step8-review-walk",
                   surfaces=frozenset(RECOGNIZED_TARGET),
                   can_pass_none_step_id=True, guards_none_step_id=False),
        ],
        prompt=PromptContract(verdict_literal_static_in_template=True),
    )


def post_fix_model() -> ContractModel:
    """The contract after this session's fixes (should trace clean)."""
    return ContractModel(
        callers=[
            # step 7 now surfaces every recognized-target outcome
            Caller("step7-detail-loop",
                   surfaces=frozenset(RECOGNIZED_TARGET),
                   can_pass_none_step_id=False, guards_none_step_id=False),
            # step 8 now guards step_id is None before escalating
            Caller("step8-review-walk",
                   surfaces=frozenset(RECOGNIZED_TARGET),
                   can_pass_none_step_id=True, guards_none_step_id=True),
        ],
        # verdict injected via the structural_verdict_option extra_var, not static
        prompt=PromptContract(verdict_literal_static_in_template=False),
    )


def main() -> None:
    print("=== contract-trace spike: escalate-structural-findings-to-split ===\n")
    for label, model in (("PRE-FIX (buggy)", pre_fix_model()),
                         ("POST-FIX (this session's fixes)", post_fix_model())):
        findings = trace(model)
        print(f"--- {label}: {len(findings)} finding(s) ---")
        for f in findings:
            print(f"  • {f}")
        print()

    pre = trace(pre_fix_model())
    post = trace(post_fix_model())
    blob = "\n".join(pre)
    # The 3 known finding *classes* (the grid-walk pinpoints step7's drop as two
    # precise cells — unsafe + proposal-unusable — which is strictly more useful
    # than the audit's single "step7 drops the unsafe outcome" prose finding).
    classes = {
        "step7 dropped outcomes": "step7-detail-loop] outcome" in blob,
        "step8 plan-level KeyError": "passes step_id=None" in blob,
        "step3 gate leak": "verdict literal is static" in blob,
    }
    missing = [name for name, hit in classes.items() if not hit]
    assert not missing, f"grid-walk missed known finding class(es): {missing}"
    assert not post, f"expected post-fix to trace clean, got {len(post)}"
    print(f"VALIDATED: one deterministic grid-walk surfaced all 3 known finding "
          f"classes (as {len(pre)} precise cells) pre-fix, and traced clean "
          f"post-fix. No sampling — full coverage of the (caller × outcome × "
          f"step_id) grid + the prompt-injection contract.")


if __name__ == "__main__":
    main()
