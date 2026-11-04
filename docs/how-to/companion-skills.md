# Choose companion skills

Use this guide to choose optional skills alongside plan-tool in Claude Code,
Codex, or Cursor. Start with the bundled [plan-tool skill](../../README.md#install-the-assistant-skill),
then add skills for the work in the consuming repository. Companion skills
provide domain knowledge and techniques; plan-tool supplies the planning,
audit, execution, and reconciliation workflow.

## Choose by the work

Install a skill when it addresses a recurring task or a concrete gap. Skill
names differ between catalogs; these categories are recommendations, not
required packages or additions to plan-tool's gates.

| Work | Useful skill category | Where it helps |
| --- | --- | --- |
| Implement a feature | Language, framework, database, or platform expertise | Ground the seed and details in the project's actual stack; implement within the agreed scope. |
| Cover changed behavior | Testing and test design | Choose meaningful assertions, isolate external calls, and cover deliberate exemptions and failure paths. |
| Investigate a failure | Root-cause debugging | Reproduce the failure, trace its source, and test a bounded correction. |
| Review implementation | Code review and finding triage | Check the diff against the plan, verify findings against existing tests, and retain evidence for the review loop. |
| Change a security boundary | Security review for the relevant stack | Examine authentication, permissions, secrets, and untrusted inputs where the work changes them. |
| Maintain developer guidance | Documentation and API-reference writing | Update contracts, examples, and cross-references alongside behavior changes. |
| Prepare delivery | Release and packaging | Follow the repository's versioning, changelog, distribution, and release-verification procedure. |
| Resume across sessions | Handoff and evidence consolidation | Record completed work, saved reports, unresolved decisions, and the next action. |

For a Python CLI, testing, debugging, and packaging skills are likely starting
points. A frontend application may benefit more from framework, accessibility,
and browser-testing skills. Infrastructure work needs expertise for its actual
provider and deployment tools.

## Check fit before installing

Read the skill's instructions, supporting scripts, and required companion
skills. Check its source, maintenance, supported versions, tool requirements,
and fit with the repository. Popularity can help discovery; it does not prove
compatibility.

Choose skills that complement the existing workflow. A companion skill must
not silently replace the agreed plan, bypass an audit gate, change a step's
status, broaden scope, or authorize publication. Resolve conflicting advice
under the session's instruction hierarchy and the repository's documented
contracts. A generic test-first recipe, for example, does not establish a new
plan-tool test-ordering gate.

Prefer a focused skill over a workflow bundle that introduces another planner,
execution loop, or automatic parallelism. When a skill mostly repeats project
guidance, use that guidance directly. Repository-specific release or handoff
procedures can be better candidates for a small local skill than a generic
package with different defaults.

## Make availability explicit

| Assistant | Setup and verification |
| --- | --- |
| Claude Code | Install in a skill location supported by the current CLI, reload the session, and confirm discovery. Treat slash commands and plugins as separate capabilities unless their documentation says otherwise. |
| Codex | Install in a skill location supported by the current CLI, reload the session, and confirm discovery. Verify any required external tools separately. |
| Cursor | Use the skill mechanism supported by the current Cursor Agent version and confirm discovery there. Do not assume an editor extension is available to the `agent` CLI. |

The [installation guide](install-and-update.md) owns plan-tool installation and
skill refresh. Use each companion skill's own instructions for its package;
`plan-tool install-skill` installs the bundled plan-tool integration, not a
third-party catalog.

Check both the assistant driving the session and the backend selected by
plan-tool. A skill available to the parent session is not proof that a fresh
backend subprocess can discover it. Shared `SKILL.md` syntax alone also does
not establish portable tools, permissions, or commands. Put required project
contracts and acceptance criteria in tracked repository guidance and plan
artifacts rather than relying on an optional personal skill installation.

## Try one at a time

Use a candidate on one bounded task and inspect its output, scope, and
verification. Keep it when it improves the work without duplicating the
plan-tool workflow. Record any team-required skill, installation source, and
refresh procedure in the consuming repository's setup documentation. Optional
skills remain optional; a recommendation does not add a completion criterion.
