---
id: T18
title: "Review F8: у domain/charts.py `NO_STRAIGHT` лише коли moving_ms>0 і обидва encoders True, інакше `NOT_REPORTED` (ADR-0003)"
layer: "domain"
deps: []
acs: ["AC-12"]
files_hint: ["src/rover_telemetry/domain/charts.py", "tests/unit/test_charts_motion.py"]
owner: "12romis"
estimate: "S"
status: "done"
step: "COMMIT"
---

# T18 — Review F8: у domain/charts.py `NO_STRAIGHT` лише коли moving_ms>0 і обидва encoders True, інакше `NOT_REPORTED` (ADR-0003)

Follow-up за `_review/review-2026-10-24.md`. Джерело істини — spec.md §5 (AC: AC-12), screens.md, ADR-0001/0002/0003, конституція. Деталі знахідки — у записі рев'ю.
