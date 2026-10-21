# Documentation placement review pickup

Primary documentation folders have purpose READMEs; per-plan detail, report and
other artifact folders retain their existing format contracts. The documentation
map routes session progress to `handoffs/`, general task procedures to
`docs/how-to/`, and demo walkthroughs and presenter runbooks to `docs/demos/`.

## Review scope and result

All 18 how-to pages are screened by purpose, headings, introductions and searches
for session status, pending work and dated assumptions. This is a placement and
initial-workflow review, not a fresh audit of every CLI flag or source-map line.

- The demo update checklist lives in `2026-10-21-demo-refresh.md`, outside how-to.
- `docs/demos/README.md` is the demo entry point. The planning demo and roadmap
  demo runbook live beside it. The planning demo needs updating before its next
  presentation; its refresh remains deferred. The former roadmap-demo location
  is a routing page so retained plan and audit citations continue to resolve.
- Installation guidance handles credentials/source movement conditionally.
- Branch-awareness states the current opt-in behavior without a former-state comparison.
- Common workflows and the audit introduction name both audit gates. The common
  workflow no longer calls missing bare-plan details a design defect. The audit
  diagram distinguishes deterministic edits from conceptual session judgment.
- The roadmap demo keeps its repeatable setup/output contract; per-session owner
  narration is removed. Runtime `pending` states, recovery instructions and dated
  measurements remain where they explain correct operation.

## Verification and next action

All 12 primary `docs/` folders have a README; the new READMEs and updated
navigation resolve their relative file targets. No new README is added beneath
plan-details, reports, archives or individual evidence bundles. The generated CLI
index remains unchanged. Focused locator, generated CLI-reference and backlog-readability checks pass:
120 tests in 0.75 seconds. Reviewed how-to file targets resolve. Continue release
preparation independently of the deferred demo refresh. These selected-document
edits require a new candidate verification before publication; the earlier frozen
2,601-file root remains a measured checkpoint.

The demo relocation passes relative-link checks and all 53 roadmap-format
tests. The removed-route documentation guard follows the roadmap demo to its
new location. Root and documentation indexes expose the demo entry point.
