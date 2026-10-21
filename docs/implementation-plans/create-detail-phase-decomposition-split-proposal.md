# Split proposal for `create-detail-phase-decomposition`

`plan-tool create` determined this seed describes 2 independent plans, so no plan was created. Create each below as its own plan: carve the seed using the line ranges, then run `plan-tool create <slug> --from-existing <file>` for each.

For a project-sized concept, consider **`plan-tool roadmap`** with a concept brief to derive an ordered plan list and draft seeds before creating each plan individually.

Run the carve commands from the source checkout root, resolved with
`git rev-parse --show-toplevel`.

## 1. Decompose create_plan into named phases

- **Suggested slug:** `decompose-create-plan-phases`
- **Why its own plan:** This plan extracts plan_tool/create.py:create_plan into same-file phase functions while preserving its signature, convergence-loop ordering, state flow, checkpoints, and behavior independently of generate_detail.
- **Seed lines:** 1–182
- **Carve:** `sed -n '1,182p' plan-seeds/create-detail-phase-decomposition.md > decompose-create-plan-phases.md`

## 2. Decompose generate_detail into named phases

- **Suggested slug:** `decompose-generate-detail-phases`
- **Why its own plan:** This plan extracts plan_tool/detail.py:generate_detail into same-file phase functions while preserving its signature, recursive split flows, accumulators, checkpoints, ordering, and behavior independently of create_plan.
- **Seed lines:** 1–182
- **Carve:** `sed -n '1,182p' plan-seeds/create-detail-phase-decomposition.md > decompose-generate-detail-phases.md`
