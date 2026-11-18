# Documentation and onboarding

| Section | Opened |
| --- | --- |
| [Two-tier documentation rollout](#two-tier-documentation-rollout) | 2026-11-18 |

## Two-tier documentation rollout

*Opened 2026-11-18.*

| Field | Value |
| --- | --- |
| Outcome | Give readers a short example they can act on, then link directly to the guide that owns exact behavior, exceptions, or recovery. |
| Shipped | [PR #271](https://bitbucket.org/protagona/plan-tool/pull-requests/271) merged at `d2112d875`. It covers the README slice of #510, the install and format references, and a changelog fragment. |
| Local follow-up | `d0a2aaa15` on `docs/remove-redundant-readme-heading` removes the visible **Start here** wrapper and keeps `#start-here` working. The owner confirmed the revised format reads better. The commit is separate from #271. |
| Next | Complete the remaining #510 verification, then use #515's fresh-reader observations to select the next documentation slice. |

### What to carry forward

- **First tier.** Show a representative input, what the reader gets back,
  and the decision they make next. The README opens its first-plan section
  with the owner's demo prompt, “use the plan tool skill to create a website
  scraper cli,” and shows a possible answer to a clarifying question. The
  `due-dates` example follows with linked artifacts and the due-today
  decision. The owner reports the short scraper prompt worked end to end
  after a clarification. The prepared `due-dates` audit transcripts are
  authored examples. [First plan](../README.md#your-first-plan) ·
  [Prepared demo](../docs/demos/getting-started/README.md)
- **Second tier.** Keep exact rules with their existing owners. The same page
  can open with an example and link down to the detailed sections. Keep
  action-changing conditions beside the action, such as confirmed exit before
  recovery and approval before implementation. Use the live README as the
  exemplar for first use and the pilot for the proposed audit and recovery
  openings. [Pilot proposal](../docs/design-plans/example-first-documentation.md) ·
  [Documentation style](../docs/reference/documentation-style.md)

### Verification and next pickup

1. **Finish #510.** Keep the first-task walkthrough scoped through detail
   review. Complete #377 seed-authoring support and verify the path in a
   consuming repository before closing the entry. #508 can proceed
   independently and remains part of #515's public sign-off. [Backlog](../BACKLOG.md)
2. **Run #515.** Ask a fresh reader to install and discover the skill, follow
   a short prompt, review the seed and both audits, and stop at detail review.
   Capture the environment, assistant, backend, model, commands and artifact
   paths. Record where the reader guesses or backtracks. The pilot's local
   checks cover 71 legacy README anchors, 76 local links, six skill commands,
   the two prepared audit checkpoints, and CLI validation of the demo plan.
   Fresh-reader and live-backend verification still need their own evidence.
   [Install guide](../docs/how-to/install-and-update.md) · [Backlog](../BACKLOG.md)
3. **Use #530 for observed stumbles.** If reading the final audit result is
   the friction, start the audit guide with the pilot's paired bare and
   grounded examples and link directly to the qualification rules. If
   recovery is the friction, start with the observed symptom and the next
   command or decision. Check affected links and contract facts in each
   edit. Keep the general link guard under #529. [Pilot examples](../docs/design-plans/example-first-documentation.md#draft-audit-and-recovery-openings) ·
   [Audit result contract](../docs/how-to/pipeline/audit.md#reading-the-final-qualified-result)

Use the backlog for readiness and scope decisions. Retire this section once
the live pickup and evidence are recorded in their owning documents.
