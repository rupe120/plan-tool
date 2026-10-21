---
title: Dependency Cycle
status: planning
priority: low
steps:
  - id: 1
    title: Depends on 2
    depends_on: [2]
  - id: 2
    title: Depends on 1
    depends_on: [1]
---

# 1 -> 2 -> 1 cycle.
