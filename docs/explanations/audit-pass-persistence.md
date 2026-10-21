# Audit process example: Audit Pass Persistence

This example shows how the plan-tool audit gates turn a broad, plausible idea
into the smallest proof that completes its intent. It is a process example,
not a claim that an audit pass alone makes a plan ready to implement.

## The proof under review

`audit-pass-persistence` will preserve a successfully written checkpoint for a
conceptual-audit pass that will be followed by another pass. A matching later
invocation will resume at the next un-run pass. It will not create a global
repository snapshot, change reusable-final selection, or recover final output
delivery.

## What the gates establish

The bare-plan gate will judge the intent and step graph before detail prose
multiplies the design. The detail-grounded gate will then judge the selected
contracts and routes against the detail bundle and code at HEAD.

The gates therefore answer different questions:

| Gate | Question | Useful result |
| --- | --- | --- |
| Bare plan | Does the planned proof belong, and does its plan-level contract hold? | A bounded plan can proceed to detail. |
| Detail grounded | Do the selected delivery contracts actually preserve that proof? | Specific missing contracts or tests can be corrected before implementation. |

## Dated evidence

On 2026-08-31, the bare-plan audit first exposed several concerns that looked
like natural extensions: global repository identity, reusable-final precedence,
and terminal-result delivery recovery. They did not belong to the recovery
proof. The plan was recut to declare a smaller recovery fence and to preserve
existing reuse behavior.

The same audit then found two defects inside that smaller proof:

- a terminal pass could overwrite the prior resumable prefix before its
  non-resumable transition succeeded;
- a write error could occur after the stable replacement was visible, so it
  could not prove that the prior prefix remained.

The correction made terminal paths suppress the ordinary resumable write and
made recovery depend on the artifact actually present after publication. It did
not add a new snapshot, CLI flag, final-result recovery path, or reuse policy.
The scoped bare plan then reached a confirmed, zero-gap audit result. See
[`20260831-202935-completeness.md` — retained historical summary](../evidence/public-release-content-snapshot.md#applied-dispositions-and-retained-conclusions).

After detail authoring, the detail-grounded audit identified the next two real
contracts: a named non-resumable terminal residue state and run-log provenance
for a successful resume. Those findings stay inside the proof and are handled
as the next bounded application batch. See
[`20260831-211426-completeness.md` — retained historical summary](../evidence/public-release-content-snapshot.md#applied-dispositions-and-retained-conclusions).

## Why this is valuable

The audit process will keep an implementation plan honest in four ways:

1. It tests whether an apparent requirement belongs before elaborating it.
2. It converts a vague safety statement into a named observable property and
   route.
3. It requires identifier and vocabulary sweeps after a recut, so stale prose
   cannot silently restore a removed capability.
4. It separates a real in-scope correction from the eventual, more general
   system someone could build later.

The next action is always proportional to the active gate: author detail after
a clean bare-plan gate; apply the smallest detail-grounded contract correction
after the detail gate; execute only after the detail bundle converges.
