# Documentation map

*Start at the repository [README](../README.md) for common tasks and first use.*

The documents at this level are shared operating references. Choose a section
below when you need a task procedure, exact contract, rationale, evidence, or
historical record.

## Shared operating references

- [Architecture](ARCHITECTURE.md) — module boundaries and ownership.
- [Backends](BACKENDS.md) — supported assistants and their configuration.
- [Gates](GATES.md) — gate coverage and reconcile direction.
- [Glossary](GLOSSARY.md) — recurring terms.
- [Iteration](ITERATION.md) — convergence, scope-out, and split criteria.
- [Operations](OPERATIONS.md) — headless runs, logs, worktrees, and recovery.
- [Tracking](TRACKING.md) — backlog and work-tracking rules.

## Documentation by purpose

| Need | Read |
| --- | --- |
| Complete a task or recover a run | [How-to guides](how-to/README.md) |
| Explore or present a worked example | [Demonstrations](demos/README.md) |
| Look up commands and exact contracts | [Reference](reference/README.md) |
| Understand a settled design choice | [Explanations](explanations/README.md) |
| Inspect benchmarks and measured outcomes | [Evidence](evidence/README.md) |
| Check a decision or retired contract | [History](history/README.md) |
| See how `plan-tool` connects to an external system or framework | [Integrations](integrations/README.md) |

## Choose a folder for new documentation

| Primary folder | Intent |
| --- | --- |
| [`cli/`](cli/README.md) | Generated flag and subcommand reference; edit the generator, not these pages. |
| [`concepts/`](concepts/README.md) | Project briefs and problem framing before decomposition. |
| [`design-plans/`](design-plans/README.md) | Proposed architecture and alternatives awaiting design review. |
| [`demos/`](demos/README.md) | Demo walkthroughs, presenter scripts and preparation instructions. |
| [`evidence/`](evidence/README.md) | Dated measurements, verification receipts and limitations supporting decisions. |
| [`explanations/`](explanations/README.md) | Maintained design rationale and conceptual understanding. |
| [`history/`](history/README.md) | Explicitly historical decisions and retired contracts still needed for correct action. |
| [`how-to/`](how-to/README.md) | Reusable task procedures and recovery instructions. |
| [`implementation-plans/`](implementation-plans/README.md) | Structured execution plans, step details and backlog routing arcs. |
| [`integrations/`](integrations/README.md) | External-system and framework integration guidance. |
| [`presentations/`](presentations/README.md) | Audience-facing decks and presentation assets. |
| [`reference/`](reference/README.md) | Precise command, format and process contracts. |

Session progress, remaining work, owner questions and pickup instructions belong
in top-level [handoffs/](../handoffs/README.md), not in a how-to guide. Backlog
entries own future work under [Tracking](TRACKING.md). Add folder-purpose READMEs
at this primary layer; per-plan detail and report directories follow their
artifact formats instead of acquiring separate orientation files.
