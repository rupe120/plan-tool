---
title: Shopping cart — percentage discounts + total-helper extraction (detail fixture)
status: planning
priority: low
test_command: uv run pytest tests/ -q --tb=no
steps:
- id: 1
  title: Add percentage-discount support to the cart — new src/discounts.py holds the
    coupon table and percentage-clamp logic; src/cart.py gains a discounted_total()
    that applies a looked-up coupon to the subtotal
  files:
  - src/cart.py
  creates:
  - src/discounts.py
  - tests/test_discounts.py
  complexity: low
  change_type: feature
- id: 2
  title: Extract line-item subtotal math out of Cart.subtotal into a module-level
    line_item_total() helper — behavior-preserving refactor pinned by the existing
    cart tests
  files:
  - src/cart.py
  - tests/test_cart.py
  complexity: low
  change_type: refactor
  depends_on:
  - 1
---
# Shopping cart — percentage discounts + total-helper extraction (detail fixture)

This plan is a **benchmark fixture**, not real project work. It is the input for
the *detail-drafting* family: a backend is asked to draft each step's detail
markdown, and the result is scored — judge-free — for the required-H2 set
(`plan_tool/detail.py:_REQUIRED_H2_TOKENS`), files-coherence cleanliness
(`plan_tool/review.py:check_files_coherence`), and acceptance-bullet
parseability (`plan_tool/detail.py:parse_acceptance_bullets`).

The plan parses under `plan_tool/schema.py:Plan` with exactly two steps. The
two steps' footprints are chosen so a faithful draft yields **zero** coherence
findings, while a drifting draft that cites a near-miss path (e.g.
`src/discount.py` instead of `src/discounts.py`) surfaces a `detail_only`
finding the scorer can detect.

## Overview

A small cart library gains percentage-off coupons (step 1, feature) on top of a
behavior-preserving extraction of its subtotal math (step 2, refactor). The
steps exist only to give the detail drafter a realistic, footprint-anchored
target.

## Scratch repo (embedded)

Step 2's engine materializes this `repo` map (path → contents) into a tempdir +
`git init` before asking the backend to draft detail. The footprint paths above
resolve against these files. The format is documented in
`docs/BENCHMARK_DESIGN.md`.

```json
{
  "repo": {
    "src/cart.py": "\"\"\"A tiny shopping cart.\"\"\"\n\n\nclass Cart:\n    def __init__(self):\n        self.items = []  # list[(unit_price, qty)]\n\n    def add(self, unit_price, qty):\n        self.items.append((unit_price, qty))\n\n    def subtotal(self):\n        total = 0\n        for unit_price, qty in self.items:\n            total += unit_price * qty\n        return total\n",
    "tests/test_cart.py": "from src.cart import Cart\n\n\ndef test_subtotal_sums_line_items():\n    c = Cart()\n    c.add(100, 2)\n    c.add(50, 1)\n    assert c.subtotal() == 250\n"
  }
}
```

## Scoring anchors

- **Required H2s:** each drafted detail file must contain all seven sections
  named in `_REQUIRED_H2_TOKENS` (summary, table, why, files, implementation,
  tests, acceptance).
- **Files coherence (step 1):** declares `src/cart.py`, `src/discounts.py`,
  `tests/test_discounts.py`. A clean draft mentions all three → zero
  `files_only` nits and no `detail_only` near-miss.
- **Files coherence (step 2):** declares `src/cart.py`, `tests/test_cart.py`.
  Both exist in the embedded repo; a clean draft mentions both.
- **Acceptance bullets:** the drafted `## Acceptance criteria` must yield a
  non-empty list under `parse_acceptance_bullets`.
