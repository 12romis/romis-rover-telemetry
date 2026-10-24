"""Сторінка цілком у браузері: мережа, CSP, телефон, ізоляція блоків, XSS (AC-18, AC-19, AC-21)."""

import json
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from e2e_support import watch_page
from playwright.sync_api import expect

from rover_telemetry.db.reading import Snapshot
from rover_telemetry.domain.dashboard import GapNumber, StoredSession
from rover_telemetry.web import chart_blocks

pytest.importorskip("playwright.sync_api")

pytestmark = pytest.mark.e2e

MAC = "288485922c94"
PHONE = {"width": 360, "height": 800}
FIXTURES = Path(__file__).parents[1] / "fixtures"
UNAVAILABLE = "Графік тимчасово недоступний"
BLOCKS = ("battery", "obstacles", "motion")
CHARTS = {
    "battery": ("battery-voltage", "battery-drop"),
    "obstacles": ("obstacles-distance", "obstacles-control-off"),
    "motion": ("motion-speed", "motion-imbalance"),
}
XSS = '</script><img src=x onerror="window.__pwned=1">'


def from_report(n: int) -> StoredSession:
    """Виїзд зі справжнього звіту ровера з `tests/fixtures/`."""
    r = json.loads((FIXTURES / f"session_seq{n}.json").read_text())
    holds, speed, enc = r.get("holds") or {}, r.get("speed") or {}, r.get("encoders") or {}
    by = holds.get("by_sensor") or {}
    return StoredSession(
        mac=MAC,
        seq=n,
        received_at=datetime(2026, 10, 24, 10, 13, tzinfo=UTC),
        duration_ms=r.get("duration_ms"),
        end_reason=r.get("end_reason"),
        voltage_start_mv=r.get("voltage_start_mv"),
        voltage_end_mv=r.get("voltage_end_mv"),
        voltage_min_mv=r.get("voltage_min_mv"),
        holds_count=holds.get("count"),
        moving_ms=r.get("moving_ms"),
        distance_cm=r.get("distance_cm"),
        fw_version=(r.get("fw") or {}).get("version"),
        payload=r,
        holds_min_mm=holds.get("min_mm"),
        holds_min_sensor=holds.get("min_sensor"),
        holds_left_front=by.get("left_front"),
        holds_front=by.get("front"),
        holds_right_front=by.get("right_front"),
        holds_rear=by.get("rear"),
        tof_control_off_ms=r.get("tof_control_off_ms"),
        speed_left_avg_rpm=speed.get("left_avg_rpm"),
        speed_left_peak_rpm=speed.get("left_peak_rpm"),
        speed_right_avg_rpm=speed.get("right_avg_rpm"),
        speed_right_peak_rpm=speed.get("right_peak_rpm"),
        speed_imbalance_pct=speed.get("imbalance_pct"),
        encoders_left=enc.get("left"),
        encoders_right=enc.get("right"),
    )


def real_snapshot() -> Snapshot:
    return Snapshot([from_report(26), from_report(27)], [GapNumber(MAC, 25)])


def open_page(browser: Any, base_url: str, wait_charts: bool = True) -> tuple[Any, Any]:
    page = browser.new_context(viewport=PHONE, has_touch=True).new_page()
    watch = watch_page(page)
    page.goto(f"{base_url}/")
    if wait_charts:
        page.locator('[data-chart="motion-imbalance"] canvas').wait_for()
    return page, watch


def test_real_reports_page_is_clean_on_the_wire_and_in_console(
    browser: Any, base_url: str, serve_snapshot: Callable[[Snapshot], None]
) -> None:
    """AC-21: лише власний вузол, жодного порушення CSP чи помилки консолі."""
    serve_snapshot(real_snapshot())
    page, watch = open_page(browser, base_url)

    assert page.locator("canvas").count() == 6
    paths = {u.removeprefix(base_url) for u in watch.requests}
    assert {"/", "/static/app.css", "/static/echarts.min.js", "/static/charts.js"} <= paths
    watch.assert_clean(base_url)


def test_phone_no_sideways_scroll_and_every_chart_reacts_to_tap(
    browser: Any, base_url: str, serve_snapshot: Callable[[Snapshot], None]
) -> None:
    """AC-18: усе вміщується в 360 px; дотик до слота показує підказку, поза графіком ховає."""
    serve_snapshot(real_snapshot())
    page, _ = open_page(browser, base_url)

    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    for key in BLOCKS:
        for name in CHARTS[key]:
            chart = page.locator(f'[data-chart="{name}"]')
            chart.scroll_into_view_if_needed()
            box = chart.bounding_box()
            assert box is not None
            assert (
                box["height"] >= 44 and box["x"] >= 0 and box["x"] + box["width"] <= PHONE["width"]
            )
            x, y = page.evaluate(
                """(name) => {
                  const el = document.querySelector(`[data-chart="${name}"]`);
                  const c = echarts.getInstanceByDom(el);
                  const r = el.getBoundingClientRect();
                  return [r.left + c.convertToPixel({xAxisIndex: 0}, '27'), r.top + r.height / 2];
                }""",
                name,
            )
            page.touchscreen.tap(x, y)
            page.get_by_text("Виїзд № 27").first.wait_for()
            page.touchscreen.tap(PHONE["width"] / 2, 2)  # поза графіком
            expect(page.locator(".chart-tip:visible")).to_have_count(0)


def test_gap_slot_tap_gives_no_tooltip_and_no_console_error(
    browser: Any, base_url: str, serve_snapshot: Callable[[Snapshot], None]
) -> None:
    serve_snapshot(real_snapshot())
    page, watch = open_page(browser, base_url)

    page.locator('[data-chart="battery-voltage"]').scroll_into_view_if_needed()
    x, y = page.evaluate(
        """() => {
          const el = document.querySelector('[data-chart="battery-voltage"]');
          const c = echarts.getInstanceByDom(el);
          const r = el.getBoundingClientRect();
          return [r.left + c.convertToPixel({xAxisIndex: 0}, '25'), r.top + r.height / 2];
        }"""
    )
    page.touchscreen.tap(x, y)
    page.wait_for_timeout(400)

    expect(page.get_by_text("Виїзд № 25")).to_have_count(0)
    assert watch.console_errors == []


@pytest.mark.parametrize("broken", BLOCKS)
def test_server_side_failure_of_one_block_leaves_the_rest_alive(
    broken: str,
    browser: Any,
    base_url: str,
    serve_snapshot: Callable[[Snapshot], None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(snapshot: Snapshot) -> chart_blocks.BlockView:
        raise ValueError("секрет-у-винятку")

    monkeypatch.setattr(
        chart_blocks,
        "BLOCKS",
        [replace(s, build=boom) if s.key == broken else s for s in chart_blocks.BLOCKS],
    )
    serve_snapshot(real_snapshot())
    page, watch = open_page(browser, base_url, wait_charts=False)

    page.get_by_text(UNAVAILABLE).first.wait_for()
    assert page.get_by_text(UNAVAILABLE).count() == 1
    assert "секрет-у-винятку" not in page.content() and "ValueError" not in page.content()
    for key in BLOCKS:
        canvases = page.locator(f'[data-chart-block="{key}"] canvas').count()
        assert canvases == (0 if key == broken else 2), key
    expect(page.get_by_text("Підсумки за всі виїзди")).to_have_count(1)
    expect(page.locator("details.session")).to_have_count(2)
    assert watch.console_errors == []


@pytest.mark.parametrize("broken", BLOCKS)
def test_browser_side_failure_of_one_block_leaves_the_rest_alive(
    broken: str, browser: Any, base_url: str, serve_snapshot: Callable[[Snapshot], None]
) -> None:
    serve_snapshot(real_snapshot())
    page = browser.new_context(viewport=PHONE).new_page()
    watch_page(page)

    def corrupt(route: Any) -> None:
        response = route.fetch()
        marker = f'id="chart-data-{broken}">{{'
        route.fulfill(response=response, body=response.text().replace(marker, marker + "x", 1))

    page.route(f"{base_url}/", corrupt)
    page.goto(f"{base_url}/")
    page.get_by_text(UNAVAILABLE).first.wait_for()

    for key in BLOCKS:
        section = page.locator(f'[data-chart-block="{key}"]')
        if key == broken:
            assert section.locator("canvas").count() == 0
            assert section.locator(".chart").first.inner_text().startswith(UNAVAILABLE)
        else:
            section.locator("canvas").first.wait_for()
            assert section.locator("canvas").count() == 2
    expect(page.locator("details.session")).to_have_count(2)


def test_two_blocks_failing_at_once_leave_the_third(
    browser: Any,
    base_url: str,
    serve_snapshot: Callable[[Snapshot], None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(snapshot: Snapshot) -> chart_blocks.BlockView:
        raise RuntimeError("x")

    monkeypatch.setattr(
        chart_blocks,
        "BLOCKS",
        [replace(s, build=boom) if s.key != "obstacles" else s for s in chart_blocks.BLOCKS],
    )
    serve_snapshot(real_snapshot())
    page, _ = open_page(browser, base_url, wait_charts=False)

    page.locator('[data-chart-block="obstacles"] canvas').first.wait_for()
    assert page.get_by_text(UNAVAILABLE).count() == 2
    expect(page.locator("details.session")).to_have_count(2)


def test_empty_storage_three_empty_blocks_and_no_sideways_scroll(
    browser: Any, base_url: str, serve_snapshot: Callable[[Snapshot], None]
) -> None:
    serve_snapshot(Snapshot([], []))
    page, watch = open_page(browser, base_url, wait_charts=False)

    expect(page.locator('[data-state="empty"]')).to_have_count(3)
    assert page.get_by_text("виїздів ще не збережено").count() == 3
    assert page.locator("canvas").count() == 0
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    assert watch.console_errors == []


def test_markup_from_a_report_is_never_executed_or_inserted(
    browser: Any, base_url: str, serve_snapshot: Callable[[Snapshot], None]
) -> None:
    """Ризик SAD §11: `fw_version`, `holds_min_sensor`, `end_reason` з розміткою — лише текст."""
    evil = StoredSession(
        mac=MAC,
        seq=50,
        received_at=datetime(2026, 10, 24, 10, 13, tzinfo=UTC),
        end_reason=XSS,
        fw_version=XSS,
        voltage_start_mv=7600,
        voltage_min_mv=7500,
        voltage_end_mv=7550,
        holds_count=1,
        holds_min_mm=100,
        holds_min_sensor=XSS,
        moving_ms=1000,
        payload={"fw": {"version": XSS}},
    )
    serve_snapshot(Snapshot([evil], []))
    page, watch = open_page(browser, base_url)

    for name in ("obstacles-distance", "battery-voltage"):
        chart = page.locator(f'[data-chart="{name}"]')
        chart.scroll_into_view_if_needed()
        x, y = page.evaluate(
            """(name) => {
              const el = document.querySelector(`[data-chart="${name}"]`);
              const c = echarts.getInstanceByDom(el);
              const r = el.getBoundingClientRect();
              return [r.left + c.convertToPixel({xAxisIndex: 0}, '50'), r.top + r.height / 2];
            }""",
            name,
        )
        page.touchscreen.tap(x, y)
        page.get_by_text("Виїзд № 50").first.wait_for()

    assert page.evaluate("window.__pwned === undefined")
    assert XSS in (page.locator("details.session").first.text_content() or "")  # як текст
    assert page.get_by_text("Занизька").count() == 0  # невідома причина не отримує позначки
    watch.assert_clean(base_url)
