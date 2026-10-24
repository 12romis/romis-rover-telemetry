"""ECharts на canvas і його підказка під незміненим CSP `default-src 'self'` (AC-21, ADR-0002).

Піднімає справжній `app` (його middleware і заголовки) у потоці й додає лише тестовий маршрут
зі сторінкою-пробою. Без встановленого Playwright чи Chromium тести пропускаються.
"""

import socket
import threading
import time
from collections.abc import Iterator
from typing import Any

import pytest
import uvicorn
from fastapi.responses import HTMLResponse, Response

from rover_telemetry.web.app import app

playwright_sync = pytest.importorskip("playwright.sync_api")

pytestmark = pytest.mark.e2e

PROBE_HTML = (
    "<!doctype html><html><head><meta charset='utf-8'><title>probe</title></head>"
    "<body><div id='chart'></div><script src='/static/echarts.min.js'></script>"
    "<script src='/__probe.js'></script></body></html>"
)
# Підказка — DOM-елемент із textContent: рядок HTML зі `style=` порушив би CSP (ADR-0002).
PROBE_JS = """
const el = document.getElementById('chart');
const chart = echarts.init(el, null, {renderer: 'canvas', width: 400, height: 300});
chart.setOption({
  animation: false,
  xAxis: {type: 'category', data: ['1', '2', '3']},
  yAxis: {type: 'value'},
  tooltip: {trigger: 'axis', formatter: (p) => {
    const node = document.createElement('div');
    node.textContent = 'значення ' + p[0].value;
    return node;
  }},
  series: [{type: 'bar', data: [5, 8, 3]}],
});
window.__ready = true;
"""


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture
def base_url() -> Iterator[str]:
    async def probe_page() -> HTMLResponse:
        return HTMLResponse(PROBE_HTML)

    async def probe_js() -> Response:
        return Response(PROBE_JS, media_type="text/javascript")

    app.add_api_route("/__probe", probe_page, methods=["GET"])
    app.add_api_route("/__probe.js", probe_js, methods=["GET"])
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.1)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        app.router.routes[:] = [
            r
            for r in app.router.routes
            if getattr(r, "path", "") not in {"/__probe", "/__probe.js"}
        ]


@pytest.fixture
def browser() -> Iterator[Any]:
    with playwright_sync.sync_playwright() as p:
        try:
            instance = p.chromium.launch()
        except playwright_sync.Error as exc:  # браузер не встановлено
            pytest.skip(f"Chromium недоступний: {str(exc).splitlines()[0]}")
        yield instance
        instance.close()


def test_canvas_and_tooltip_work_under_unchanged_csp(browser: Any, base_url: str) -> None:
    page = browser.new_page()
    violations: list[str] = []
    console_errors: list[str] = []
    requests: list[str] = []
    page.expose_function("report_violation", lambda detail: violations.append(str(detail)))
    page.add_init_script(
        "document.addEventListener('securitypolicyviolation', e =>"
        " window.report_violation(e.violatedDirective + ' ' + e.blockedURI));"
    )
    page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: console_errors.append(str(e)))
    page.on("request", lambda r: requests.append(r.url))

    response = page.goto(f"{base_url}/__probe")
    page.locator("#chart canvas").wait_for()  # `wait_for_function` — це `eval`, його блокує CSP
    assert response is not None
    assert response.headers["content-security-policy"] == "default-src 'self'"

    # canvas не порожній: є хоч один непрозорий піксель
    painted = page.evaluate(
        """() => {
          const c = document.querySelector('#chart canvas');
          const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
          for (let i = 3; i < d.length; i += 4) if (d[i] !== 0) return true;
          return false;
        }"""
    )
    assert painted

    # підказка з'являється при наведенні й тримає текст як textContent
    box = page.locator("#chart canvas").bounding_box()
    assert box is not None
    page.mouse.move(box["x"] + 120, box["y"] + 200)
    page.mouse.move(box["x"] + 125, box["y"] + 205)
    page.get_by_text("значення 8").or_(page.get_by_text("значення 5")).first.wait_for()

    assert violations == []
    assert console_errors == []
    assert requests, "сторінка не робила запитів"
    assert all(url.startswith(base_url) or url.startswith("data:") for url in requests), requests
