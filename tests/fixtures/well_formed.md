---
title: Well-Formed Plan
status: in-progress
priority: medium
steps:
  - id: 1
    title: First step
    files: [a.py, b.py]
    complexity: low
    status: done
  - id: 2
    title: Second step
    complexity: medium
    depends_on: [1]
    detail: plan-details/well-formed/02-second.md
    status: current
  - id: 3
    title: Third step
    depends_on: [2]
---

# Well-Formed Plan

## Overview
A plan that exercises required + optional fields and a realistic shape.
