---
id: T19
title: "Review F7+F4: рендер вмісту блока й JSON під try у render_blocks; holds_count і тривалість виїзду в даних блока «Перешкоди» (формат format_duration_ms)"
layer: "ports"
deps: ["T18"]
acs: ["AC-08", "AC-09", "AC-19"]
files_hint: ["src/rover_telemetry/web/chart_blocks.py", "src/rover_telemetry/web/templates/dashboard.html", "tests/unit/test_chart_blocks.py", "tests/unit/test_templates_charts_obstacles.py"]
owner: "12romis"
estimate: "S"
status: "done"
step: "COMMIT"
---

# T19 — Review F7+F4: рендер вмісту блока й JSON під try у render_blocks; holds_count і тривалість виїзду в даних блока «Перешкоди» (формат format_duration_ms)

Follow-up за `_review/review-2026-10-24.md`. Джерело істини — spec.md §5 (AC: AC-08, AC-09, AC-19), screens.md, ADR-0001/0002/0003, конституція. Деталі знахідки — у записі рев'ю.
