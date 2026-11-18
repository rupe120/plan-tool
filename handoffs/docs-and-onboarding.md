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
| Local follow-up | `c5b202ed6` applies the owner-approved README heading cleanup and keeps `#start-here` working. `01390e991` brings the prepared demo seed and plan checkpoints into line with file-backed create preflight. |
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

### Local verification

On 2026-11-18, a local source clone on macOS arm64 (macOS 27.2.1, uv
0.9.9, Python 3.13.9) supplied an isolated editable install and a wheel,
both reporting plan-tool 1.6.0. For each install, project-local
`plan-tool install-skill --integration <assistant>` and the same command
with `--copy` passed for Claude Code, Codex, and Cursor in fresh Git
repositories. All 12 installations placed a readable router and sibling
reference in the expected directory. Assistant discovery remains part of
the live walkthrough.

The prepared seed now passes file-backed preflight and selects preparation.
The three guardrail bodies agree across the seed and every prepared plan
checkpoint. The wheel's `plan-tool validate due-dates` passes on each
prepared plan branch. The reading walk stops on `demo/5-detail-audit`;
the audit transcripts are authored and no live backend result is recorded.
A local link check preserves 79 README anchors from the merged pilot and
resolves 80 local links across the README, install guide, and reference
index. The focused create, installer, router, and start-screen suite passes
1,200 tests after the fixture fix.

The [prepared review path](../docs/demos/getting-started/README.md#first-plan-review)
now names both transcripts and the stop at step 5. The local reading walk
confirms that `step.sh live` starts from the previous prepared checkpoint
and that `git show` displays the authored transcript while preserving the
live branch and its HEAD. The [presenter runbook](../docs/demos/getting-started/RUNBOOK.md#when-something-goes-wrong)
uses that read-only route while a command is quiet and requires confirmed
exit before returning to the prepared branches.

### Verification and next pickup

1. **Finish #510.** Keep the first-task walkthrough scoped through detail
   review. Complete #377 seed-authoring support and verify the path in a
   consuming repository before closing the entry. #508 can proceed
   independently and remains part of #515's public sign-off. [Backlog](../BACKLOG.md)
   The [#377 plan](../docs/implementation-plans/2-installed-seed-authoring.md)
   takes the direct route from its [archived seed](../docs/implementation-plans/plan-seeds/archive/installed-seed-authoring.replaced.md).
   The owner authorizes Codex `gpt-6.2-sol` to author and audit the plan.
   The plan reuses the existing shared reference and installer.
   Both bare audits use
   `completeness-audit installed-seed-authoring --iterate --commit --audit-passes 1`
   with that backend and model. The [first report](../docs/implementation-plans/plan-details/installed-seed-authoring/reports/20261118-184624-completeness.md)
   covers 0 of 3 details, confirms current evidence, and reports four
   findings, two of them blocking. Commit `1011f63fa` clarifies canonical-shape
   routing, carried guardrails, the isolated wheel check, and approval before
   commit and create. The [re-audit](../docs/implementation-plans/plan-details/installed-seed-authoring/reports/20261118-184910-completeness.md)
   has the same detail coverage and a fresh conceptual call. It reports
   confirmed, current `advisory-only` evidence with no blockers and no
   budget limit. Detail authoring owns the remaining preparation example
   check for source-backed evidence sections, including Risks.
   The owner authorizes `detail --commit` and the grounded audit.
   `detail installed-seed-authoring --commit -y` writes and commits all
   three details before its automatic audit. The subsequent grounded checks
   use `completeness-audit installed-seed-authoring --iterate --commit --audit-passes 1`.
   All five reports cover 3 of 3 run-grade details and have confirmed,
   current evidence for their respective snapshots.

   | Grounded report | Material changes |
   | --- | --- |
   | [Automatic audit](../docs/implementation-plans/plan-details/installed-seed-authoring/reports/20261118-192500-completeness.md) | Four findings. Clarify fenced-only canonical bodies, strict-step authority, preparation evidence, and active backlog references. |
   | [First re-audit](../docs/implementation-plans/plan-details/installed-seed-authoring/reports/20261118-192922-completeness.md) | Three findings. Specify direct outcomes and refusal recovery, and consolidate the shortcut test. |
   | [Second re-audit](../docs/implementation-plans/plan-details/installed-seed-authoring/reports/20261118-193225-completeness.md) | Two findings. Specify continuation for registered normalized plans and the pending backlog status. |
   | [Third re-audit](../docs/implementation-plans/plan-details/installed-seed-authoring/reports/20261118-193515-completeness.md) | One finding. Extend the approved-seed handoff to the large-document shortcut. |
   | [Last re-audit](../docs/implementation-plans/plan-details/installed-seed-authoring/reports/20261118-193820-completeness.md) | Two findings. Apply the handoff to all authoring entries, prove the CLI selects the approved seed body, and consolidate example intake checks in step 2. |

   The last two rounds audit the prior corrections, so the loop stops under
   the repo's own-edits exit. Commit `ea494bf6d` applies the last two remedies.
   All details parse and a local replay verifies the standalone and legacy
   provenance selection paths. The audit has no clean verdict for the final
   commit. The tool's step 3 authoring fingerprint remains advisory and
   reflects the plan footprint before the tracking paths were added. Step 3's
   detail covers those paths. The reviewed bundle still needs approval and
   normal merge to the remote default branch before execution.
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
