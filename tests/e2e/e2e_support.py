"""Помічники браузерних тестів: збір порушень CSP, помилок консолі та запитів сторінки."""

from dataclasses import dataclass, field
from typing import Any

import pytest

# Без пакета playwright пропускається кожен тестовий модуль, що імпортує цей файл (маркер `e2e`).
expect = pytest.importorskip("playwright.sync_api").expect


@dataclass
class Watch:
    """Що сторінка зробила: порушення CSP, помилки консолі, усі запити."""

    violations: list[str] = field(default_factory=list)
    console_errors: list[str] = field(default_factory=list)
    requests: list[str] = field(default_factory=list)

    def assert_clean(self, base_url: str) -> None:
        assert self.violations == []
        assert self.console_errors == []
        assert self.requests, "сторінка не робила запитів"
        foreign = [u for u in self.requests if not u.startswith((base_url, "data:", "blob:"))]
        assert foreign == [], foreign


def watch_page(page: Any) -> Watch:
    watch = Watch()
    page.set_default_timeout(10_000)  # провал має бути швидким, а не 30-секундним
    page.expose_function("report_violation", lambda detail: watch.violations.append(str(detail)))
    page.add_init_script(
        "document.addEventListener('securitypolicyviolation', e =>"
        " window.report_violation(e.violatedDirective + ' ' + e.blockedURI));"
    )
    page.on("console", lambda m: watch.console_errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: watch.console_errors.append(str(e)))
    page.on("request", lambda r: watch.requests.append(r.url))
    return watch


# Рамки всіх текстових рядків графіка в координатах полотна (з урахуванням повороту).
_TEXT_BOXES_JS = """(name) => {
  const chart = echarts.getInstanceByDom(document.querySelector(`[data-chart="${name}"]`));
  const boxes = [];
  for (const el of chart.getZr().storage.getDisplayList(true)) {
    if (el.type !== 'tspan' || !el.style.text || !el.style.text.trim()) continue;
    const r = el.getBoundingRect();
    const m = el.getComputedTransform() || [1, 0, 0, 1, 0, 0];
    const corners = [[r.x, r.y], [r.x + r.width, r.y], [r.x, r.y + r.height],
      [r.x + r.width, r.y + r.height]];
    const pts = corners
      .map(([x, y]) => [m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]]);
    const xs = pts.map(p => p[0]);
    const ys = pts.map(p => p[1]);
    boxes.push([el.style.text, Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)]);
  }
  return {width: chart.getWidth(), height: chart.getHeight(), boxes};
}"""

TOLERANCE_PX = 1.0  # сусідні рядки одного підпису торкаються краями; це не перекриття


def text_problems(page: Any, name: str) -> list[str]:
    """Підписи графіка, що виходять за полотно або перекривають один одного (AC-18)."""
    data = page.evaluate(_TEXT_BOXES_JS, name)
    boxes = data["boxes"]
    problems = [
        f"поза полотном: {text!r}"
        for text, x1, y1, x2, y2 in boxes
        if x1 < -TOLERANCE_PX
        or y1 < -TOLERANCE_PX
        or x2 > data["width"] + TOLERANCE_PX
        or y2 > data["height"] + TOLERANCE_PX
    ]
    for i, (ta, ax1, ay1, ax2, ay2) in enumerate(boxes):
        for tb, bx1, by1, bx2, by2 in boxes[i + 1 :]:
            overlap_x = min(ax2, bx2) - max(ax1, bx1)
            overlap_y = min(ay2, by2) - max(ay1, by1)
            if overlap_x > TOLERANCE_PX and overlap_y > TOLERANCE_PX:
                problems.append(f"перекриття: {ta!r} і {tb!r}")
    return problems
