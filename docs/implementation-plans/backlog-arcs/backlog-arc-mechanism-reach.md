# Mechanism-reach backlog arc

## File intent

This file routes work that keeps a focused plan on its requested property
while it reuses the smallest suitable existing owner. It distinguishes ordinary
reuse from a shared semantic change that requires its own intentional plan.

## Choose this arc when

Choose this arc when plan authoring or review can turn one vertical property
into a registry, shared policy, repository-wide identity, consumer migration,
or other cross-owner contract without proof that the property requires it.
Do not choose it merely because a focused implementation calls a shared file or
helper unchanged; that is ordinary reuse. Do not use it to implement a shared
semantic change itself; author that change as its own plan after this arc has
identified it.

## Delivery cadence

Treat the remaining #336 and #335 entries as plan-tool work. Commit before
every command. #334's authoring contract and fixtures are complete; #336 can
preserve an excluded shared semantic change as a manual handoff, then #335
adds the audit lens. A manual handoff or recommendation remains a decision
surface: it never
authorizes a rewrite, a scope expansion, or a shared-mechanism change.

## Ordered route

1. **Completed — #334.** [The authoring plan](../archive/2-mechanism-reach-01-authoring.md)
   establishes reuse, bounded extension, and separately intentional shared
   semantics.
2. Execute **#336**. It preserves a split-create `defer` as
   an operator-visible handoff for separately intentional work, without
   creating that work automatically.
3. Execute **#335** after #336. Its lens may inspect an explicitly
   selected broad contract, but it must not infer a mechanism from a bare plan
   or treat local use of a shared structure as a defect.
4. When #335 identifies a genuine shared semantic change, create a separate
   backlog item and plan for that contract. The focused vertical plan does not
   absorb the shared change; #336's manual handoff names the separate work.

## Decision gates

- Semantic reach, not file count or consumer count, decides the route. One
  central edit can change repository-wide behavior; many files can remain one
  command-path proof.
- Reuse an existing common structure when it already satisfies the property.
  Do not clone it merely to make the plan look local.
- A bounded additive extension can remain in a focused plan when it is the
  smallest suitable owner and existing consumers retain their behavior and
  schema interpretation. An available local adapter does not disqualify it.
- A change to shared authority, lifecycle, identity, precedence, schema, or
  existing-consumer behavior is separate intentional work. Name its affected
  contracts and proof surface before authoring it.
- The audit records an explicit missing necessity proof. It does not decide
  that a proposed shared mechanism is wrong, select a replacement, or add
  consumers to justify it.

## Exit and handoff

This arc finishes when #336 preserves an excluded shared semantic change as a
manual handoff and #335
surfaces only explicit, unjustified shared semantic commitments as manual
decisions. A required shared change leaves this arc as one separately scoped
backlog item; an unchanged or bounded owner choice needs no follow-up arc.

## Out of scope

This arc does not create a global scope-control framework, new plan schema,
consumer-count threshold, automatic scope rewrite, or automatic plan split. It
does not make audit output an exit-code gate or a substitute for author and
user architectural judgment.
