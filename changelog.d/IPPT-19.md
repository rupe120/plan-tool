### Added

- Candidate review now lists live prose that still names a design row the candidate's own carried removals record as removed. The evidence is computed from the candidate each time, shown on the propose, review, answer and decide surfaces before approval, and nothing is stored (IPPT-19).
- The confirming approve and the answer-bound seal refuse a candidate whose live prose names a removed row, and the refusal names the defect and both exits: correct the paragraph with the `correct-prose` operation, or mark it as history. A reference to an id that is also a present row is shown as non-blocking and never refuses (IPPT-19).
