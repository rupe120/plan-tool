# Roadmap intake comparison — Integration Gate 1 corpus

## Decision

The comparison confirms `BACKLOG.md` #384 as the next compatibility slice.
It does not select #383, a source manifest, a generic role reader, or an
AI-DLC-specific adapter. The first slice will carry a closed set of confirmed
upstream decisions as cited inherited facts. It will not use the other options
from an upstream question as Roadmap rejected alternatives.

The observed defect is provenance, not missing stage grounding. Both inputs
let Roadmap preserve the material workflow, hosting, scope, and experience
facts. In both arms, however, Roadmap re-authors confirmed answers as its own
`settled` decisions, invents rejected alternatives, and records no resolvable
source citation. That is the exact #384 selection condition.

## Frozen corpus and method

Integration commit `7caeaec` (`aidlc: revalidate Gate 1 handoff`) is the frozen Gate
1 corpus. Its approval receipt records the final Approval & Handoff stage, and
the control brief's SHA-256 is
`0086ebf87fc582aab38a42611bff5389966b9faff687a055fe6f3942d510a852`.

The runs used independent disposable clones of that commit and GPT-5.6 Sol:

```text
plan-tool --model gpt-5.6-sol roadmap integration-aidlc-brief \
  --from-existing aidlc/spaces/default/intents/260909-integration-mvp/ideation/approval-handoff/initiative-brief.md -y

plan-tool --model gpt-5.6-sol roadmap integration-aidlc-composed-corrected \
  --from-existing comparison-role-sectioned-brief.md -y
```

The control is the approved `initiative-brief.md`. The composed input is a
deterministic, role-sectioned file containing the complete intent statement,
scope document, wireframes, user flow, feasibility assessment, constraint
register, exact confirmed question/answer pairs, and selected project rules.
It excludes the intent-backlog body, stakeholder-map body, approval records,
decision-log repetition, runtime metadata, and unselected answer options.

An earlier generated composed file omitted its confirmed-answer section because
of an extractor defect. Its resulting run is excluded from this comparison.
The corrected source contains all 29 confirmed answers and is the only composed
arm used below.

## Results

| Measure | One approved brief | Role-sectioned composition | Reading |
| --- | --- | --- | --- |
| Gated artifacts | Four accepted artifacts; four plan slices | Four accepted artifacts; three plan slices | Both inputs are sufficient for the current staged writer. |
| Source citations on derived decision rows | None | None | Both arms lose the provenance that distinguishes an inherited answer from a Roadmap call. |
| Confirmed answers recast as Roadmap decisions | Runtime-neutral UI, worker shape, completion/readiness, and connector validation are emitted as `settled` decisions with generated alternatives. | Dynamic steps, chat-only input, raw stream, and separate readiness are emitted the same way. | This is an observed #384 failure, not merely a hypothetical schema preference. |
| Pending rows tied to a distinct upstream open question | None; five Roadmap pending rows are not source-question identities. | None; three Roadmap pending rows are not source-question identities. | Gate 1 declares no unresolved question, so no source-question count exists to carry. |
| Direct contradiction of a confirmed answer | None found in the four artifacts. | None found in the four artifacts. | Both preserve the material box, but neither proves decision provenance. |
| Runtime-neutral workflow surface | Preserved. | Preserved. | Both keep runtime selection in configured workflow steps rather than user-facing navigation. |

The three accepted-risk follow-through items have no traceable obligation
disposition in either arm. The control includes repository recovery states in
one plan; the composed arm explicitly leaves comprehensive recovery beyond the
happy path as a non-goal. Neither route links either result to its accepted-risk
record, neither gives the success-measure follow-through a disposition, and the
composed arm treats a separate submission acknowledgement as outside the proof.
This does not authorize an obligations subsystem: a later capability needs its
own selected contract for exactly-one disposition and a gate.

## Source-blind revision pass

Each arm received the same local feedback on its domain decision: state plainly
that configured workflow steps select runtimes and runtime names do not define
user-facing navigation. The bounded `--revise-feedback` route, which does not
receive the original source, changed only the selected decision rationale and
returned an `awaiting-review` response in both arms. It introduced no box drift.

```text
plan-tool --model gpt-5.6-terra roadmap <arm> \
  --revise-feedback domain:comparison-runtime-neutrality
```

The pass does not select a shared frame or wider reader context. It only shows
that the tested local revision preserves the named property when feedback
supplies it explicitly.

## Consequences

The #384 seed and bare plan may now be authored. Its source carrier and
citation resolution remain plan inputs: each inherited decision will anchor a
live Roadmap row and cite confirmed recorded source material; missing anchors
or unresolved citations will refuse. Roadmap-derived decisions alone will keep
the rejected-alternatives requirement.

#383 remains held. The comparison names no stage and no essential grounded fact
that cannot safely fit in the approved one-file brief. A richer composition
changes decomposition shape, but material volume alone is not evidence for a
generic reader. No manifest, multi-source intake, role reader, or AI-DLC parser
is selected.
