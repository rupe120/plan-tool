---
title: Plan With Status Notes
status: in-progress
priority: medium
steps:
  - id: 1
    title: First step
    status: done
    status_note: Skipped DB migration — already applied in a prior plan.
  - id: 2
    title: Second step
    depends_on: [1]
    scope: deferred
    status_note: Waiting on credentials from ops.
  - id: 3
    title: Third step
    depends_on: [2]
    scope: deferred
---

# Plan With Status Notes

## Overview
Exercises the optional `status_note` field on steps.
