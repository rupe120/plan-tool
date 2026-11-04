### Breaking

- Retire legacy Jira-grade detail inputs and the `--grade` selectors on `detail`, `jira`, `completeness-audit`, `convergence`, and `gate-status`, plus `run --detail-grade`. Use canonical detail authored by `plan-tool detail` and omit the removed selectors. Legacy compact detail files are not migrated or accepted as inputs; author canonical detail for affected plans. Jira stories and their paired developer handoff retain their output contracts (IPPT-17).
