# Process contracts

This reference names the authority and handoff of each high-level process.
It complements the format and flow documents; it does not duplicate their
implementation mechanics.

| Process | Purpose and authority | Durable output | Does not do | Handoff |
| --- | --- | --- | --- | --- |
| `create` | Turns an idea or seed into a registered plan. The accepted plan body and frontmatter are authoritative for planned work. | Plan file and manifest entry. | Write step detail or implementation code. | Bare conceptual audit, then `detail`. |
| `detail` | Authors run-grade detail for the plan's steps. The plan controls step scope and `steps[].detail` names that artifact. | Run-grade detail. | Execute code or author Jira outputs. | Completeness audit, `run`, or Jira export. |
| Completeness audit | Judges the plan's concepts, coverage, and unambiguity. The plan and selected detail bundle are the audit subject, not the implementation. | Persisted audit report. | Fulfill a plan in code or blindly apply conceptual findings. | Human judgment through completeness apply or a direct plan/detail edit, then a fresh audit. |
| Completeness apply | Lets an operator apply saved conceptual findings. The operator chooses the amendment. | Plan/detail edits and applied-finding record. | Act as a non-interactive blanket writer. | Commit, then re-audit. |
| `run` | Fulfills an authoritative plan step in code. The plan and declared run-grade detail define the expected result. | Code, tests, run log, and step status. | Rewrite plan intent to fit delivered code. | `reconcile-code` after the completed plan. |
| `reconcile-plan` | Re-grounds an unexecuted plan against code that moved independently. Current code is authoritative for that pre-execution correction. | Plan edits or saved review findings. | Reconcile code created by the plan's own execution. | Detail or execution after the plan is current. |
| `reconcile-code` | Reconciles delivered code with the plan after execution. The plan is authoritative; plan-side defects redirect to plan/detail work. | Code edits or saved review findings. | Narrow plan intent to accept under-delivery. | Verification and code review. |
| `jira` | Produces final consumer handoff. It reads the declared run-grade detail bundle and always writes concise stories with a provenance-stamped developer handoff. The implementation plan fixes the handoff's complete, dependency-ordered path; Jira story and handoff prose explains that path and treats its implementation route as a suggestion that a developer may improve while preserving the step's spirit and outcome. | Jira stories and a generated developer-handoff source file. | Change plans, upstream detail, audit inputs, external Jira state, or turn a suggested mechanism into a plan requirement. | Operator copies the current generated source files to Jira; a later paired export regenerates both from current inputs. |
| `annotate` | Classifies an existing plan or notes against current code and prepares forward-looking carryover. The source stays authoritative as an input snapshot. | Additive report and `create --from-existing` seed. | Mutate the source except the explicit archive option. | `create` for the next plan iteration. |
| Roadmap | Develops and maintains roadmap-level artifacts above individual plans. Each mode owns only its declared evidence or canonical-write boundary. | Roadmap artifacts, draft seeds, or immutable evidence. | Let evidence views or analysis routes mutate canonical roadmap state. | `create` from an accepted seed or the explicitly named roadmap workflow. |

## Using this reference in code and prompts

Code points here only at boundaries a nearby implementation can make easy to
invert. Prompt assembly may render a selected row only when a concrete failure
shows that its current plan, detail, code-anchor, and format context cannot
state the needed boundary. It must select that row deterministically and test
the resulting routing; it must not ingest arbitrary repository docstrings.

The detailed operational contracts remain in `docs/how-to/pipeline/detail.md`,
`docs/how-to/pipeline/audit.md`, `docs/how-to/pipeline/run.md`, `ROADMAP_FORMAT.md`, and the generated
`docs/cli/` reference — for `jira` specifically, see `JIRA_FORMAT.md` (story
schema and the developer-handoff contract) and `docs/cli/jira.md`
(the generated flag reference).
