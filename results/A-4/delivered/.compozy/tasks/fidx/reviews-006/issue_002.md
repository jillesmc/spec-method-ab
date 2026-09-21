---
round: 6
round_created_at: 2026-09-21T02:48:37.078652316Z
status: pending
file: .compozy/tasks/fidx/memory/task_04.md
line: 18
severity: low
author: unknown
---

# Issue 002: task_04 workflow memory still documents a design that reviews-001/002 already reversed

## Review Comment

`.compozy/tasks/fidx/memory/task_04.md:18-23` says error messages are fixed literals and warns 'don't switch to str(exc) — that would break the contract.' This is now false: `fidx/__main__.py:93,100-104,116-128` interpolate `str(exc)` for every non-`PermissionError` case, added by reviews-001/issue_001 and reviews-002/issue_001 to fix mislabeling. reviews-005/issue_001 already flagged this exact staleness but left it uncorrected. A future remediation agent trusting this memory could revert the fix and reintroduce the previously-fixed bug. Fix: update task_04.md's Decisions section.

## Triage

- Decision: `UNREVIEWED`
- Notes:
