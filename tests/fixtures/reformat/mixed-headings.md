# Mixed Heading Plan

## Overview

A synthetic fixture exercising mixed heading conventions in a single document
so `parse_source` can verify it rejects the mix rather than silently picking
one form.

## Phase 1 — Setup

- Configure `apps/web/foo.ts` for the new build target.

### Step 2 — Implementation

- Edit `apps/web/bar.ts` to wire the new module.

## Acceptance criteria

- The parser rejects this file with a clear error pointing at the first
  non-conforming heading.
