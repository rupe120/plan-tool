> **Status: wrong-repo.** Amplify / APP / Bedrock nightly cost tracking — not plan-tool. Archived 2026-08-03 out of `plan-seeds/` so it stops competing with plan-tool authoring. Relocate to that product's backlog if still needed.

# Plan seed: per-user cost tracking for the background process + AWS quota investigation

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing .agents/skills/plan-tool/plan-seeds/per-user-agent-cost-tracking.md
```

It is **not** itself a plan — `plan-tool create` consumes the prose
below and proposes a step decomposition. The author then runs
`plan-tool detail` per step to flesh the plan out.

---

## Goal

Make per-user spend on the nightly background process **observable
and queryable** so the product team can:

1. Compute the marginal cost of running the background process for
   a single user (Bedrock tokens + downstream resource calls).
2. Make ROI-informed decisions about an upcoming feature that would
   re-trigger the background process for individual users on
   system events (e.g. a career-destination pivot) instead of only
   nightly.
3. Understand how close the nightly run is pushing the account to
   AWS service quotas (Bedrock TPM/RPM, AgentCore concurrency,
   Lambda concurrency) and decide whether automated quota
   monitoring is feasible.

The motivating event-driven re-trigger feature is **out of scope** —
this plan only delivers the measurement substrate it will depend on.

## Context already in place (pre-this-plan)

The architecture below is verified from code (file:line refs
preserved so the detail step can cite them without re-discovery):

1. **Nightly trigger.** EventBridge cron `cron(0 2 * * ? *)` at
   `amplify/resources/backend-process.ts:9-22` fires the
   `backendProcessTrigger` Lambda
   (`amplify/lambda/backend-process-trigger/handler.ts`). The Lambda
   is a thin passthrough that invokes a single AgentCore runtime
   (`InvokeAgentRuntimeCommand`) with the EventBridge event as
   payload.

2. **Background AgentCore runtime.** `agentcore.Runtime`
   "bgProcessRuntime" defined in `amplify/bedrock/resource.ts:287-320`,
   model `claude-sonnet-3.7` resolved from SSM
   `/app/{env}/bedrock/chat-model-id`, entry point
   `amplify/bedrock/bg-agent/agent.py:invoke()`. The runtime
   **iterates over active users** internally
   (`amplify/bedrock/bg-agent/agent.py:290`, `for user_record in
   users_to_process`) — there is no per-user Lambda fan-out today.
   "Active" = users active in the last 3 months
   (`get_active_users_from_last_n_months(months=3)`).

3. **Skill Refiner AgentCore runtime.** `CfnRuntime`
   "SkillRefinerAgentRuntime" at `amplify/bedrock/resource.ts:412-435`,
   model Amazon Nova Micro. **Not part of the nightly flow** —
   triggered event-driven by the `skillsConsumer` Lambda
   (`amplify/lambda/skills-consumer/handler.ts`) off the
   ProfessionalProfile DynamoDB Stream. It still counts as
   per-user spend and must be tracked in the same store as the
   nightly bg-process spend.

4. **Per-user call surface inside bg-agent** (verified from
   `amplify/bedrock/resource.ts:321-358` IAM grants):
   - DynamoDB: GetItem/Query/Scan/UpdateItem against `User`,
     `ProfessionalProfile`, `SessionLog`, `Conversation`, `JobOpp`,
     `Session`, `AssessmentResponse`, `MentorMatch`,
     `MentorProfileCache`.
   - Bedrock: **one** `InvokeAgentRuntime` call per nightly
     run (issued by the trigger Lambda); the runtime then
     makes many internal Bedrock Converse calls across the
     per-user loop. Token counts must be accumulated inside
     the Python agent — the AgentCore response payload is
     whatever the agent code returns, not a structured usage
     envelope.
   - External APIs: LaborDataService classification + OAuth, AssessmentService.
   - ElastiCache (Valkey): cache lookups for LaborDataService tokens and
     AssessmentService responses.
   - SSM: parameter reads for tables/endpoints (cheap, but counted
     for completeness).

5. **No existing cost telemetry.** Verified absent:
   - No `PutMetricData` calls in `amplify/bedrock/bg-agent/` or in
     any Lambda handler.
   - No token-count extraction from the AgentCore response
     (`backend-process-trigger/handler.ts` reads only
     `response.response.transformToString()`).
   - No cost-attribution DynamoDB table.
   - `amplify/monitoring/resource.ts` covers AppSync error/latency
     and AWS Backup only — nothing Bedrock-related.

   This is greenfield instrumentation, not a refactor.

## Design decisions to lock in step 1 (do not relitigate downstream)

These four choices shape every subsequent step. The detail step
for step 1 should verify each against the actual AgentCore response
shape and either confirm or surface the blocker before downstream
steps proceed.

- **Storage: a new DynamoDB table `AgentUsageEvent`, one row per
  *runtime execution* — not one row per user.** Batch runtimes
  (the nightly bg-process) write a single row at end-of-run that
  totals the whole batch's spend; per-user attribution is computed
  at query time by dividing the totals by the number of users
  processed. Single-user runtimes (Skill Refiner today, and any
  future event-driven re-trigger of bg-process for one user)
  write a row keyed to that user. This avoids fanning N
  per-iteration writes into the nightly loop and keeps the
  write surface tiny (~1/night per environment + 1/refiner-fire).
  Not CloudWatch custom metrics as primary store — CW metric
  dimension cardinality on `userId` would still blow out for the
  single-user variant, and CW lacks the userIds list we need for
  attribution. CW remains a secondary surface for aggregate
  dashboards.
  - PK = `executionId` (the AgentCore `runtimeSessionId` for
    bg-process, or `streamRecord#eventID` for refiner). SK =
    `agentRuntime#startedAt` so a single execution that ever
    chained multiple runtimes is still expressible. GSI1 on
    `agentRuntime` + `startedAt` for whole-run rollups across
    executions. GSI2 on `subjectMode` + `startedAt` so the
    resolver can scan only batch rows or only single-user rows.
    DDB TTL ~18 months for cost containment — surface the TTL
    value explicitly in the detail step.
  - Schema fields:
    - **Discriminator:** `subjectMode` (`batch` | `single`).
    - **Identity:** `executionId`, `agentRuntime`
      (`bg-process` | `skill-refiner`), `modelId`,
      `pricingHint` (model + region — the cost calc looks it
      up at query time).
    - **Subject (batch shape):** `userIds` (DynamoDB List
      `L` of user IDs processed in this execution; the agent
      dedupes in Python before write so the list has set
      semantics — `L` is chosen over `SS` for AppSync model
      compatibility, since `a.schema()` does not expose
      `SS`), `userCount` (denormalized integer; redundant
      with list length but cheap and makes the resolver math
      trivial).
    - **Subject (single shape):** `userId` (scalar).
    - **Usage totals (always whole-execution totals, never
      per-user):** `inputTokens`, `outputTokens`,
      `cacheReadTokens`, `cacheWriteTokens` (verify AgentCore
      surfaces these), and downstream counters (`ddbReadOps`,
      `ddbWriteOps`, `laborDataServiceCalls`, `assessmentServiceCalls`,
      `valkeyOps`).
    - **Timing/health:** `startedAt`, `finishedAt`,
      `latencyMs`, `errorType` (nullable).

- **Per-user attribution is computed at query time by even
  distribution.** For a batch event, each user in `userIds` is
  charged `totals / userCount`. We accept the loss of per-user
  variance signal inside a single nightly batch — the agent's
  work is similar enough per user that the average is the
  honest answer, and avoiding the per-iteration write fan-out
  is the explicit win. Per-user variance is still observable
  *across* batches (e.g., the Skill Refiner row that fires
  whenever a specific user updates skills) and via the
  event-driven re-trigger feature once it lands.

- **Cost is computed at query time, not stored.** Storing only
  counts means pricing-table updates do not require DDB
  rewrites or back-fill. `pricingHint` pins the row to the
  correct pricing-table entry. The calculator divides the
  resulting USD by `userCount` when attributing to a single
  user from a batch row.

- **Cost calculator: in-repo versioned pricing table.** A
  TypeScript module exporting `{ modelId, region,
  inputPricePerMTok, outputPricePerMTok,
  cacheReadPricePerMTok, cacheWritePricePerMTok,
  pricingVersion, effectiveFrom }`. No live AWS Pricing API
  dependency — out of scope and overkill for the current
  cadence of pricing changes. The refresh process is a
  documented manual cadence (see step 9 / docs deliverable).

- **Skill Refiner uses the same table with `subjectMode =
  single`.** Same schema, distinguished by `agentRuntime` and
  the populated `userId` scalar (not `userIds` set). Refiner
  rows stamp the `userId` of the affected ProfessionalProfile
  (from the DynamoDB Stream record's `userID` field), not the
  signed-in caller. This keeps per-user totals stacking
  bg-process (averaged share) + refiner (direct attribution)
  correctly.

## Scope of work

1. **Finalize the `AgentUsageEvent` schema and create the DDB
   table.** Three pre-implementation verifications, then the
   schema lands: (a) confirm the Python agent can read the
   incoming `runtimeSessionId` from the AgentCore runtime
   context so it can be persisted as `executionId` — if not,
   the agent generates its own UUID at `invoke()` entry and
   logs both ids so the row stays traceable against the
   trigger Lambda's CloudWatch log group; (b) confirm the DDB
   Stream record on `ProfessionalProfile` exposes the `userID`
   of the affected row so refiner events can stamp it; (c)
   sanity-check that the `userIds` List on a batch row stays
   under the DDB 400KB item limit at projected scale (~10K
   users per night is the documented ceiling — note it
   explicitly in the docs deliverable). **Token-capture
   mechanism is settled, not verified:** AgentCore response
   payloads are whatever the agent returns, not a structured
   usage envelope, so the agent accumulates per-Converse-call
   usage internally (see step 3). Files:
   `amplify/data/resource.ts` (add `AgentUsageEvent` model —
   `userIds` as `a.string().array()` → DDB `L`, not `SS`, for
   AppSync model compatibility), `amplify/data/schema/` (new
   schema file).

2. **Add the pricing table and cost calculator module.**
   Pure-function module in `packages/shared/src/` (or
   `amplify/lambda/shared/` if the calc is only ever server-side
   — decide in detail) exporting `computeCost(event)` and the
   versioned pricing table for Claude Sonnet 3.7 and Amazon Nova
   Micro at the deployment regions. No Bedrock Pricing API
   dependency. Lock the pricing-version semantics:
   `pricingVersion` is monotonic, never edit a published row,
   always append.

3. **Instrument the bg-process AgentCore runtime to emit a
   single batch usage event at end-of-run.** Modify
   `amplify/bedrock/bg-agent/agent.py` so the `invoke()`
   entry point opens a runtime-scoped accumulator object:
   token totals, downstream counters, and a Python `set` of
   user IDs (dedupes naturally; converted to a List at write
   time per the schema lock in step 1). Every Bedrock Converse
   call inside the agent adds its `usage.inputTokens` and
   `usage.outputTokens` (plus cache-read/write tokens when
   present) to the accumulator. The per-user loop
   (`for user_record in users_to_process`) adds each
   processed `user_record.id` to the set. After the loop
   exits, a **single** `AgentUsageEvent` row is written via
   boto3 DynamoDB with `subjectMode = "batch"`, the deduped
   `userIds` list, and `userCount`. Add `dynamodb:PutItem`
   on the new table to the runtime role grants in
   `amplify/bedrock/resource.ts:321-339`. **Critical:** the
   write must not break the loop — a PutItem failure logs
   and continues; the user recommendations are not
   best-effort, the usage event is. Equally critical: write
   the event in a `try/finally` so a mid-loop Python
   exception still flushes the partial-batch row with the
   users processed so far and an `errorType` set — losing
   all cost data because one user blew up the loop is not
   acceptable. (Note: a hard SIGKILL from an AgentCore
   runtime ceiling bypasses `finally` entirely; that gap is
   accepted for v1 and tracked in the Risks section.)

4. **Instrument downstream resource counters with a
   runtime-scoped accumulator.** Wrap the DDB, LaborDataService,
   AssessmentService, and Valkey call sites in
   `amplify/bedrock/bg-agent/logic/` and
   `amplify/bedrock/bg-agent/labor_data_service_oauth.py` with the same
   accumulator object opened in step 3 (passed explicitly
   through the call stack — *not* a module-level global).
   Counters tick on every call regardless of which user
   iteration triggered them; per-user attribution comes later
   from even distribution at query time. **These counters are
   operation counts, not RCU/WCU consumption** — a Query
   returning 100 items counts as 1 op, not the ~13 RCUs it
   actually consumed. They're a call-volume signal for cost
   correlation, not a direct input to the USD cost
   calculator. The docs deliverable in step 9 must state this
   explicitly so consumers do not misread the dashboard.
   Counters attach to the single end-of-run row written in
   step 3 — do not emit additional rows. Acceptance: on a
   sandbox nightly run, the single batch row has non-zero
   values for at least `ddbReadOps` and one of
   `laborDataServiceCalls` or `assessmentServiceCalls`, and `userCount`
   matches the number of user IDs in `userIds`.

5. **Instrument the Skill Refiner pipeline as `subjectMode =
   single`.** The write happens **inside
   `amplify/bedrock/skills-refiner-agent/agent.py`**, not in
   the consumer Lambda — only the agent knows actual token
   counts. The Lambda
   (`amplify/lambda/skills-consumer/handler.ts`) changes
   only enough to pass the originating Stream record's
   `userID` and `eventID` through to the agent so the agent
   can populate `userId` and `executionId`. The agent writes
   each event with `subjectMode = "single"`, `userId`
   populated from the ProfessionalProfile's `userID`,
   `userIds`/`userCount` unset, `executionId =
   "{streamRecordEventID}"`, `agentRuntime = "skill-refiner"`.
   **Idempotency:** Stream retries can re-invoke the consumer
   for the same record; use a conditional PutItem
   (`ConditionExpression: attribute_not_exists(executionId)`)
   so the first successful write is canonical and retries
   become no-ops. The agent logs and continues on
   conditional-check failure — duplicate skip is not an
   error. Add `dynamodb:PutItem` grant on the new table to
   the Skill Refiner runtime role (see
   `amplify/bedrock/resource.ts:412-435` and
   `amplify/resources/labor-data-service-int.ts`).

6. **Admin GraphQL query: `getUserAgentCost`.** New custom Query
   resolver in `amplify/data/resource.ts` returning, for a given
   `userId` + date range: total input tokens, output tokens,
   computed USD cost, breakdown by `agentRuntime`, and downstream
   call totals. Resolver logic:
   - For `subjectMode = "single"` rows: query GSI2 by
     `subjectMode = "single"` over the date range, filter to
     rows where `userId == :userId`, attribute the full totals.
   - For `subjectMode = "batch"` rows: query GSI2 by
     `subjectMode = "batch"` over the date range, filter to
     rows where `contains(userIds, :userId)`, attribute
     `(totals / userCount)` as the user's share. Document the
     filter-expression scan cost; expected batch row count per
     month is ~30/env so this is cheap.
   - Sum both contributions for the response.
   **Bound the scan:** reject date ranges over 12 months with
   a validation error before querying — the FilterExpression
   `contains(userIds, X)` is unbounded-scan-shaped and a
   multi-year range over the refiner-mode partition will get
   expensive fast. 12 months is the default ceiling; tune
   later if the admin UI demands longer windows.
   Auth: `allow.groups(['Admin'])` only. The computed-cost path
   runs through step 2's calculator (which gains a
   `divideBy(userCount)` mode). **No UI in scope** — this is
   the data API for the admin panel (`/admin/app-settings`) to
   consume later.

7. **AWS quota investigation deliverable.** Produce a Markdown
   table enumerating every quota the nightly run + event-driven
   re-trigger feature will pressure:
   - Bedrock **cross-region inference profile** TPM/RPM for
     `claude-sonnet-3.7` — this is the actual quota the
     bg-agent hits, since the model is resolved from SSM as a
     cross-region inference profile ARN, not a direct on-demand
     model ID. Cross-region profiles have a distinct quota
     dimension from direct on-demand `InvokeModel` and must be
     measured separately.
   - Bedrock **direct on-demand** `InvokeModel` TPM/RPM for
     `amazon-nova-micro` — the Skill Refiner uses Nova Micro;
     verify during the investigation whether it routes through
     a cross-region inference profile or direct on-demand and
     adjust this row accordingly.
   - Bedrock AgentCore `InvokeAgentRuntime` quotas (concurrent
     sessions, requests per minute) — these are the least
     documented; the deliverable must note if Service Quotas API
     does not expose them and what alternative observation
     surfaces exist (CloudWatch usage metrics under the
     `AWS/Bedrock` namespace, AWS Health events).
   - Lambda concurrent executions in the deployment account.
   - DynamoDB on-demand throughput partition limits for the
     tables hit per user.
   - External rate limits: LaborDataService classification API,
     AssessmentService API (document the contractual limits; these are
     not AWS quotas but are quota-shaped).
   For each row: current limit, observed peak (sample from one
   real nightly run after step 3 lands), whether the quota is
   queryable via `service-quotas` GetServiceQuota, whether usage
   is queryable via CloudWatch, **monitoring feasibility
   verdict** (`automatable` / `manual-only` / `not-observable`).
   Output file: `docs/agent-cost-tracking.md` (see step 9).

8. **Quota monitoring wiring + missing-batch-row alarm (OR
   formal deferral).** Two deliverables in this step, sharing
   the same monitoring deployment surface (CloudWatch + SNS):

   (i) **Quota monitoring** — based on step 7 verdicts:
   either (a) implement a Lambda that polls Service Quotas +
   CloudWatch on a cron and emits a custom `QuotaUtilization`
   CloudWatch metric per quota, with a CloudWatch alarm at
   80% threshold; **or** (b) record a structured `Deferred`
   section in the plan documenting which quotas are not
   feasible to monitor automatically, the manual check
   cadence (e.g. weekly Service Quotas console review), and
   the trigger conditions that would justify revisiting. The
   decision must be made here, not left ambiguous. This is
   the step most likely to surface the user-stated risk that
   "quota management may not be feasible" — an acceptable
   outcome as long as the deferral is explicit.

   (ii) **Missing-nightly-batch-row alarm** — a CloudWatch
   alarm that fires if no `AgentUsageEvent` row with
   `subjectMode = "batch"` and `agentRuntime = "bg-process"`
   lands within ~26 hours of the prior one (2 AM UTC nightly
   schedule + 2-hour grace). Implementation: emit a
   `BatchUsageEventWritten` custom metric from the bg-agent
   on successful PutItem, or a scheduled Lambda that scans
   GSI1 for the latest batch row per environment, then alarm
   on absence. Routes to the same SNS topic as the quota
   alarms. This catches a silent failure of the cost
   instrumentation the next morning rather than at
   quarter-end cost review.

9. **Documentation: `docs/agent-cost-tracking.md`.** Single
   consolidating doc covering: `AgentUsageEvent` schema and TTL,
   the cost-calculator pricing-refresh process, how to query
   per-user cost (with a sample GraphQL call), the quota
   investigation table from step 7, and the monitoring runbook
   or deferral note from step 8. Cross-link from README.md (per
   CLAUDE.md's "checked-in files never reference CLAUDE.md"
   rule).

10. **Tests.** Unit tests for: cost-calculator math across both
    models and a pricing-version boundary; usage-event-writer
    happy-path and DDB-failure-doesnt-throw paths; counter
    accumulator round-trip; admin resolver auth (non-admin =
    denied, admin = data shape correct). One integration test
    against a sandbox bg-agent run that asserts at least one
    well-formed row lands in `AgentUsageEvent`.

## Non-goals

- **Event-driven re-trigger of the background process.** The
  feature this plan enables is explicitly out of scope. This
  plan delivers measurement only.
- **Admin UI for per-user cost.** Step 6 builds the resolver and
  the data shape; the React/RN admin pages that consume it are
  a follow-on.
- **Live AWS Pricing API integration.** Pricing lives in a
  checked-in versioned table; manual refresh on Bedrock pricing
  changes is acceptable for this iteration.
- **Historical back-fill.** Usage events start accumulating
  from deploy day forward. CloudWatch metric history and CUR /
  Cost Explorer remain the only authoritative source for spend
  before instrumentation went live; that is explicitly
  acknowledged and not patched.
- **Cost optimization.** The plan answers "what does it cost"
  not "how do we cut it." Optimization decisions enabled by
  this data are downstream work.
- **Mobile or web app exposure of cost.** Admin-only resolver;
  no end-user-facing surface.
- **Multi-account / cross-account cost.** Single AWS account
  per environment; no consolidated-billing aggregation in
  scope.

## Acceptance criteria (plan-level)

- After one full nightly run completes in a sandbox or dev
  environment, the `AgentUsageEvent` table contains **exactly
  one** row with `subjectMode = "batch"` and `agentRuntime =
  "bg-process"` for that run, with non-null `inputTokens`,
  `outputTokens`, at least one non-zero downstream counter,
  a populated `userIds` set, and `userCount` matching the set
  size.
- A ProfessionalProfile update in the same environment produces
  a follow-on `AgentUsageEvent` row with `subjectMode =
  "single"`, `agentRuntime = "skill-refiner"`, populated
  `userId`, and unset `userIds`/`userCount`.
- `getUserAgentCost(userId, startDate, endDate)` invoked from
  an admin session returns a USD cost figure that matches a
  hand-calculated value combining: (a) the user's even-share
  attribution from every batch row in the range whose
  `userIds` contains them, and (b) the full attribution from
  every single-mode row in the range with their `userId`.
  Non-admin callers receive an authorization error.
- A mid-loop exception in the bg-agent still flushes a batch
  usage event containing the users processed so far and a
  populated `errorType` (verified by fault-injection unit test
  in step 10) — losing all cost data because one user blew up
  the run is not acceptable.
- A failure of the usage-event PutItem itself does not abort
  the bg-agent runtime; the user recommendations write
  succeeds.
- `docs/agent-cost-tracking.md` exists, includes the quota
  investigation table, and contains either the monitoring
  wiring description (step 8 option a) or the formal deferral
  note (step 8 option b) — never both, never neither.
- For every quota row in the investigation table, the
  feasibility verdict is one of the three allowed values
  (`automatable` / `manual-only` / `not-observable`); no row
  is marked TBD.

## Risks

- **Per-Converse usage extraction depends on the Bedrock SDK
  returning a `usage` block on every call path.** The
  accumulator design is settled, but stale Bedrock SDK
  versions, certain streaming modes, or specific
  cross-region inference paths may omit the usage envelope on
  individual responses. The detail for step 3 must confirm
  every Converse call site the agent makes returns
  `usage.inputTokens`/`usage.outputTokens` in the version of
  `boto3` / Bedrock SDK pinned for the runtime — and log a
  warning (not a hard fail) for any call that returns no
  usage so the gap is visible in CloudWatch rather than
  silently zeroing totals.
- **Loss of per-user variance signal within a nightly batch.**
  Even-distribution attribution charges every user in a batch
  the same share. A user whose iteration triggered an
  expensive LaborDataService re-classification looks identical to a
  user whose iteration was cheap. This is the explicit
  tradeoff for avoiding the per-iteration write fan-out. If
  the product owner later asks "which specific user is
  driving cost spikes within a batch?" the answer is "we
  cannot tell from this data — instrument event-driven
  re-trigger first, then attribute the resulting single-mode
  rows directly." Document this limit prominently in the docs
  deliverable.
- **The single end-of-run write is a single point of failure
  for whole-batch cost data.** A PutItem failure on the
  end-of-run row means all cost data for that nightly run is
  lost, vs. losing one user's data in the rejected
  per-iteration design. Mitigations layered: (a) write under
  a `try/finally` so a mid-loop Python exception flushes the
  partial-batch row with `errorType` set; (b) the
  missing-nightly-batch-row alarm from step 8(ii) catches
  silent loss the next morning rather than at quarter-end.
  **Gap accepted for v1:** an AgentCore runtime hard kill
  (SIGKILL on the container, timeout enforcement) bypasses
  `finally` entirely and loses the whole night's row. If
  this fires in practice, the upgrade path is checkpoint
  writes via `UpdateItem` with `ADD` on counters every N
  users — explicitly deferred from v1 to keep the writer
  simple.
- **`userIds` List may approach the DDB 400KB item limit.**
  ~10K users per night fits comfortably; growth beyond that
  requires either splitting the batch row into chunks or
  moving the user list to a sidecar S3 object referenced by
  URI. Document the ceiling explicitly in the docs
  deliverable so the next person who scales to 50K users has
  prior warning.
- **Pricing-table drift.** The checked-in table will go stale
  on the next AWS Bedrock price change. The docs deliverable
  must spell out the refresh cadence and who owns it; the
  pricing-version-stamping design means stale prices are
  recoverable, but unnoticed staleness is the risk.
- **AgentCore service quotas may not be exposed via the
  Service Quotas API at all.** This is the user's stated risk
  ("quota management may not be feasible") and step 7 is
  designed to land on a verdict — automatable or not — rather
  than ship a half-built monitor. Accept the possibility that
  step 8 lands entirely on option (b).
- **Cost from `dataLayerProcessor` and SQS consumers is not
  tracked.** This plan covers the two AgentCore runtimes plus
  their immediate downstream calls. Other Lambdas in the
  per-user data pipeline (notification publishers, AssessmentService
  sync, etc.) are not instrumented. If product later asks
  "what did this user cost end-to-end across all systems," a
  second pass will be required — call this out in the docs
  deliverable so the limitation is visible to the product
  owner from day one.
