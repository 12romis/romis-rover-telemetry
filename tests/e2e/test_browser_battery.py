"""Блок «Акумулятор» у браузері: 360 px, дотик, порожні слоти, `null` ≠ 0, CSP (AC-01…AC-19)."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from e2e_support import watch_page
from playwright.sync_api import expect

from rover_telemetry.db.reading import Snapshot
from rover_telemetry.domain.dashboard import GapNumber, StoredSession

pytest.importorskip("playwright.sync_api")

pytestmark = pytest.mark.e2e

MAC = "288485922c94"
PHONE = {"width": 360, "height": 740}
UNAVAILABLE = "Графік тимчасово недоступний"


def session(seq: int, **fields: Any) -> StoredSession:
    return StoredSession(
        mac=MAC, seq=seq, received_at=datetime(2026, 10, 24, 10, 13, tzinfo=UTC), **fields
    )


def snapshot() -> Snapshot:
    """36, 37 — повні; 38 без мінімальної напруги; 39 занизька напруга; 40 втрачено; 41 повний."""
    sessions = [
        session(36, voltage_start_mv=7870, voltage_min_mv=7630, voltage_end_mv=7650),
        session(37, voltage_start_mv=7800, voltage_min_mv=7550, voltage_end_mv=7600),
        session(38, voltage_start_mv=7790, voltage_end_mv=7500),
        session(
            39,
            voltage_start_mv=7500,
            voltage_min_mv=6100,
            voltage_end_mv=6100,
            end_reason="failsafe_voltage",
        ),
        session(41, voltage_start_mv=7700, voltage_min_mv=7690, voltage_end_mv=7695),
    ]
    return Snapshot(sessions, [GapNumber(MAC, 40)])


def open_page(browser: Any, base_url: str, **context: Any) -> tuple[Any, Any]:
    ctx = browser.new_context(**context)
    page = ctx.new_page()
    watch = watch_page(page)
    page.goto(f"{base_url}/")
    page.locator('[data-chart="battery-voltage"] canvas').wait_for()
    return page, watch


def option_of(page: Any, name: str) -> dict[str, Any]:
    result: dict[str, Any] = page.evaluate(
        '(name) => echarts.getInstanceByDom(document.querySelector(`[data-chart="${name}"]`))'
        ".getOption()",
        name,
    )
    return result


def pixel_of(page: Any, name: str, category: str) -> tuple[float, float]:
    """Піксель центра слота в межах сторінки: низ графіка по вертикалі, центр категорії по x."""
    page.locator(f'[data-chart="{name}"]').scroll_into_view_if_needed()
    px = page.evaluate(
        """(args) => {
          const el = document.querySelector(`[data-chart="${args.name}"]`);
          const chart = echarts.getInstanceByDom(el);
          const x = chart.convertToPixel({xAxisIndex: 0}, args.category);
          const r = el.getBoundingClientRect();
          return [r.left + x, r.top + r.height / 2];
        }""",
        {"name": name, "category": category},
    )
    return float(px[0]), float(px[1])


def test_charts_fit_phone_width_and_are_painted(
    browser: Any, base_url: str, serve_snapshot: Callable[[Snapshot], None]
) -> None:
    serve_snapshot(snapshot())
    page, watch = open_page(browser, base_url, viewport=PHONE, has_touch=True)

    for name in ("battery-voltage", "battery-drop"):
        box = page.locator(f'[data-chart="{name}"]').bounding_box()
        assert box is not None and box["x"] >= 0 and box["x"] + box["width"] <= PHONE["width"]
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    painted = page.evaluate(
        """() => [...document.querySelectorAll('[data-chart^="battery"] canvas')].every(c => {
          const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
          for (let i = 3; i < d.length; i += 4) if (d[i] !== 0) return true;
          return false;
        })"""
    )
    assert painted
    watch.assert_clean(base_url)


def test_axis_is_session_number_in_seq_order_with_gap_slot(
    browser: Any, base_url: str, serve_snapshot: Callable[[Snapshot], None]
) -> None:
    serve_snapshot(snapshot())
    page, _ = open_page(browser, base_url, viewport=PHONE)

    for name in ("battery-voltage", "battery-drop"):
        option = option_of(page, name)
        assert option["xAxis"][0]["name"] == "Номер сесії"
        assert option["xAxis"][0]["data"] == ["36", "37", "38", "39", "40", "41"]
    # слот 40 — п'ята категорія (індекс 4): окрема серія малює рамку «не дійшла» лише для нього
    for name in ("battery-voltage", "battery-drop"):
        gap = [s for s in option_of(page, name)["series"] if s.get("name") == "Сесія не дійшла"]
        assert len(gap) == 1 and [row[0] for row in gap[0]["data"]] == [4]


def test_reference_lines_come_from_data_and_lie_inside_the_axis(
    browser: Any, base_url: str, serve_snapshot: Callable[[Snapshot], None]
) -> None:
    serve_snapshot(snapshot())
    page, _ = open_page(browser, base_url, viewport=PHONE)

    option = option_of(page, "battery-voltage")
    lines = [d for s in option["series"] for d in (s.get("markLine") or {}).get("data", [])]
    values = sorted(d["yAxis"] for d in lines)
    assert values == [6.0, 8.4]
    axis = option["yAxis"][0]
    assert axis["min"] < 6.0 and axis["max"] > 8.4  # відсічка не є краєм графіка
    labels = [d["label"]["formatter"] for d in lines]
    assert any(t.startswith("Відсічка 6,0 В") for t in labels)
    assert any(t.startswith("Повний заряд 8,4 В") for t in labels)


def test_missing_voltage_is_not_drawn_and_not_zero(
    browser: Any, base_url: str, serve_snapshot: Callable[[Snapshot], None]
) -> None:
    serve_snapshot(snapshot())
    page, _ = open_page(browser, base_url, viewport=PHONE)

    option = option_of(page, "battery-voltage")
    names = ("На початку", "Мінімум", "Наприкінці")
    marker_series = {s["name"]: s["data"] for s in option["series"] if s.get("name") in names}
    assert marker_series["Мінімум"][2][1] is None  # слот 38: мінімальна напруга відсутня
    for data in marker_series.values():
        for row in data:
            assert row[1] != 0
    drop = option_of(page, "battery-drop")["series"][0]["data"]
    assert drop[2] is None  # просадка не обчислена — стовпця немає, не нуль


def test_series_differ_by_shape_and_label(
    browser: Any, base_url: str, serve_snapshot: Callable[[Snapshot], None]
) -> None:
    serve_snapshot(snapshot())
    page, _ = open_page(browser, base_url, viewport=PHONE)

    legend = option_of(page, "battery-voltage")["legend"][0]["data"]
    assert [(d["name"], d["icon"]) for d in legend] == [
        ("На початку", "circle"),
        ("Мінімум", "diamond"),
        ("Наприкінці", "rect"),
    ]


def test_largest_drop_and_end_reason_are_labelled(
    browser: Any, base_url: str, serve_snapshot: Callable[[Snapshot], None]
) -> None:
    serve_snapshot(snapshot())
    page, _ = open_page(browser, base_url, viewport=PHONE)

    drop = option_of(page, "battery-drop")["series"][0]["data"]
    labelled = [i for i, d in enumerate(drop) if isinstance(d, dict) and d["label"]["show"]]
    assert labelled == [3]  # слот 39: просадка 1,4 В — найбільша
    assert drop[3]["label"]["formatter"] == "найбільша просадка"
    reasons = [
        row[2]
        for s in option_of(page, "battery-voltage")["series"]
        if s.get("name") == "Причина завершення"
        for row in s["data"]
    ]
    assert reasons == [None, None, None, "Занизька напруга акумулятора", None, None]


def test_tap_shows_tooltip_with_received_and_values_then_outside_tap_hides_it(
    browser: Any, base_url: str, serve_snapshot: Callable[[Snapshot], None]
) -> None:
    serve_snapshot(snapshot())
    page, watch = open_page(browser, base_url, viewport=PHONE, has_touch=True)

    x, y = pixel_of(page, "battery-voltage", "37")
    page.touchscreen.tap(x, y)
    tip = page.locator(".chart-tip")
    tip.first.wait_for()
    text = tip.first.inner_text()
    assert "Виїзд № 37" in text
    assert "Отримано (за київським часом): 24.10.2026 13:13" in text
    assert "Напруга на початку — 7,80 В (3,90 В на банку)" in text
    assert "Мінімальна напруга — 7,55 В" in text
    assert "Напруга наприкінці — 7,60 В" in text
    assert "Просадка — 0,25 В" in text
    assert "час виїзду" not in text.lower() and "час сесії" not in text.lower()

    x2, y2 = pixel_of(page, "battery-voltage", "36")
    page.touchscreen.tap(x2, y2)
    page.get_by_text("Виїзд № 36").first.wait_for()  # перенесено на інший слот

    page.touchscreen.tap(PHONE["width"] / 2, 8)  # поза графіком
    expect(page.locator(".chart-tip:visible")).to_have_count(0)  # дотик поза графіком ховає
    watch.assert_clean(base_url)


def test_tooltip_marks_missing_value_with_italic_no_data_and_reason(
    browser: Any, base_url: str, serve_snapshot: Callable[[Snapshot], None]
) -> None:
    serve_snapshot(snapshot())
    page, _ = open_page(browser, base_url, viewport=PHONE, has_touch=True)

    x, y = pixel_of(page, "battery-voltage", "38")
    page.touchscreen.tap(x, y)
    tip = page.locator(".chart-tip").first
    tip.wait_for()

    text = tip.inner_text()
    assert "Мінімальна напруга — немає даних (ровер не передав: мінімальна напруга)" in text
    assert "Просадка — немає даних" in text
    assert tip.locator("em").first.inner_text() == "немає даних"


def test_tap_on_gap_slot_shows_no_tooltip(
    browser: Any, base_url: str, serve_snapshot: Callable[[Snapshot], None]
) -> None:
    serve_snapshot(snapshot())
    page, _ = open_page(browser, base_url, viewport=PHONE, has_touch=True)

    x, y = pixel_of(page, "battery-voltage", "40")
    page.touchscreen.tap(x, y)
    page.wait_for_timeout(400)

    assert page.get_by_text("Виїзд № 40").count() == 0


def test_corrupted_block_data_replaces_only_that_blocks_charts(
    browser: Any, base_url: str, serve_snapshot: Callable[[Snapshot], None]
) -> None:
    serve_snapshot(snapshot())
    ctx = browser.new_context(viewport=PHONE)
    page = ctx.new_page()
    watch_page(page)

    def corrupt(route: Any) -> None:
        response = route.fetch()
        body = response.text().replace(
            'id="chart-data-battery">{', 'id="chart-data-battery">{broken', 1
        )
        route.fulfill(response=response, body=body)

    page.route(f"{base_url}/", corrupt)
    page.goto(f"{base_url}/")
    page.get_by_text(UNAVAILABLE).first.wait_for()

    battery = page.locator('[data-chart-block="battery"]')
    assert battery.locator("canvas").count() == 0
    assert battery.locator(".chart").first.inner_text().startswith(UNAVAILABLE)
    assert battery.locator("h2").inner_text() == "Акумулятор"  # заголовок і опис лишились
    assert page.get_by_text("Підсумки за всі виїзди").count() == 1
    assert page.locator("details.session").count() == 5


def test_missing_echarts_script_shows_message_not_blank(
    browser: Any, base_url: str, serve_snapshot: Callable[[Snapshot], None]
) -> None:
    serve_snapshot(snapshot())
    ctx = browser.new_context(viewport=PHONE)
    page = ctx.new_page()
    page.route(f"{base_url}/static/echarts.min.js", lambda route: route.abort())
    page.goto(f"{base_url}/")

    page.get_by_text(UNAVAILABLE).first.wait_for()
    assert page.locator("canvas").count() == 0
