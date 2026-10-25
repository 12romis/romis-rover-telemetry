---
id: T20
title: "Review F10+F14: видалити мертві форматери з дубльованими константами; прибрати тавтологічний статичний тест JS, прихований імпорт і type: ignore/noqa без обґрунтування"
layer: "ui"
deps: []
acs: ["AC-01", "AC-10"]
files_hint: ["src/rover_telemetry/web/formatting.py", "src/rover_telemetry/web/templating.py", "tests/unit/test_formatting.py", "tests/unit/test_charts_js_static.py", "tests/unit/test_charts_battery.py", "tests/unit/test_charts_motion.py", "tests/unit/test_charts_obstacles.py"]
owner: "12romis"
estimate: "S"
status: "done"
step: "COMMIT"
---

# T20 — Review F10+F14: видалити мертві форматери з дубльованими константами; прибрати тавтологічний статичний тест JS, прихований імпорт і type: ignore/noqa без обґрунтування

Follow-up за `_review/review-2026-10-24.md`. Джерело істини — spec.md §5 (AC: AC-01, AC-10), screens.md, ADR-0001/0002/0003, конституція. Деталі знахідки — у записі рев'ю.
