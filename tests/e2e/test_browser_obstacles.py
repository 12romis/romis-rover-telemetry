"""Блок «Перешкоди» у браузері: відстань на тлі порога, «утримань не було», захист (AC-05…AC-09)."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from e2e_support import expect, watch_page

from rover_telemetry.db.reading import Snapshot
from rover_telemetry.domain.dashboard import GapNumber, StoredSession

pytestmark = pytest.mark.e2e

MAC = "288485922c94"
PHONE = {"width": 360, "height": 740}
XSS = '<img src=x onerror="window.__pwned=1">'


def session(seq: int, **fields: Any) -> StoredSession:
    return StoredSession(
        mac=MAC, seq=seq, received_at=datetime(2026, 10, 24, 10, 13, tzinfo=UTC), **fields
    )


def snapshot() -> Snapshot:
    """36: 6 мм; 37: 103 мм, захист вимкнено 6,66 с; 38: утримань не було; 39: відстань не
    передано; 40 втрачено; 41: невідомий датчик із розміткою."""
    sessions = [
        session(36, holds_count=3, holds_min_mm=6, holds_min_sensor="front", tof_control_off_ms=0),
        session(
            37,
            holds_count=2,
            holds_min_mm=103,
            holds_min_sensor="left_front",
            holds_left_front=1,
            holds_front=2,
            tof_control_off_ms=6660,
            duration_ms=657000,
        ),
        session(38, holds_count=0, tof_control_off_ms=1500),
        session(39, holds_count=2, tof_control_off_ms=0),
        session(41, holds_count=1, holds_min_mm=80, holds_min_sensor=XSS, tof_control_off_ms=0),
    ]
    return Snapshot(sessions, [GapNumber(MAC, 40)])


def open_page(browser: Any, base_url: str, **context: Any) -> tuple[Any, Any]:
    page = browser.new_context(**context).new_page()
    watch = watch_page(page)
    page.goto(f"{base_url}/")
    page.locator('[data-chart="obstacles-distance"] canvas').wait_for()
    return page, watch


def series_of(page: Any, name: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = page.evaluate(
        '(name) => echarts.getInstanceByDom(document.querySelector(`[data-chart="${name}"]`))'
        ".getOption().series",
        name,
    )
    return result


def tap_slot(page: Any, name: str, category: str) -> None:
    page.locator(f'[data-chart="{name}"]').scroll_into_view_if_needed()
    x, y = page.evaluate(
        """(args) => {
          const el = document.querySelector(`[data-chart="${args.name}"]`);
          const chart = echarts.getInstanceByDom(el);
          const x = chart.convertToPixel({xAxisIndex: 0}, args.category);
          const r = el.getBoundingClientRect();
          return [r.left + x, r.top + r.height / 2];
        }""",
        {"name": name, "category": category},
    )
    page.touchscreen.tap(x, y)


def test_both_charts_fit_phone_width_and_are_painted(
    browser: Any, base_url: str, serve_snapshot: Callable[[Snapshot], None]
) -> None:
    serve_snapshot(snapshot())
    page, watch = open_page(browser, base_url, viewport=PHONE, has_touch=True)

    for name in ("obstacles-distance", "obstacles-control-off"):
        box = page.locator(f'[data-chart="{name}"]').bounding_box()
        assert box is not None and box["x"] >= 0 and box["x"] + box["width"] <= PHONE["width"]
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    painted = page.evaluate(
        """() => [...document.querySelectorAll('[data-chart^="obstacles"] canvas')].every(c => {
          const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
          for (let i = 3; i < d.length; i += 4) if (d[i] !== 0) return true;
          return false;
        })"""
    )
    assert painted
    watch.assert_clean(base_url)


def test_distance_bars_from_zero_without_filtering_and_missing_are_not_zero(
    browser: Any, base_url: str, serve_snapshot: Callable[[Snapshot], None]
) -> None:
    serve_snapshot(snapshot())
    page, _ = open_page(browser, base_url, viewport=PHONE)

    bar = next(s for s in series_of(page, "obstacles-distance") if s["type"] == "bar")
    values = [d["value"] if isinstance(d, dict) else d for d in bar["data"]]
    # 36: 6 мм показано як у звіті; 38 «утримань не було», 39 «не передано», 40 пропуск — не нулі
    assert values == [6, 103, None, None, None, 80]
    option = page.evaluate(
        "() => echarts.getInstanceByDom("
        "document.querySelector('[data-chart=\"obstacles-distance\"]')).getOption()"
    )
    assert option["yAxis"][0]["min"] == 0
    assert option["xAxis"][0]["name"] == "Номер сесії"


def test_threshold_line_comes_from_data_with_label_and_sensor_labels_sit_on_bars(
    browser: Any, base_url: str, serve_snapshot: Callable[[Snapshot], None]
) -> None:
    serve_snapshot(snapshot())
    page, _ = open_page(browser, base_url, viewport=PHONE)

    series = series_of(page, "obstacles-distance")
    lines = [d for s in series for d in (s.get("markLine") or {}).get("data", [])]
    assert [d["yAxis"] for d in lines] == [190]
    assert lines[0]["label"]["formatter"] == "Поріг 190 мм"
    bar = next(s for s in series if s["type"] == "bar")
    labels = [d["label"]["formatter"] for d in bar["data"] if isinstance(d, dict)]
    assert labels == ["передній", "лівий передній", "Інший датчик"]  # сирий текст на графік не йде


def test_slot_states_no_holds_is_a_frame_not_a_bar_and_missing_is_hatched(
    browser: Any, base_url: str, serve_snapshot: Callable[[Snapshot], None]
) -> None:
    serve_snapshot(snapshot())
    page, _ = open_page(browser, base_url, viewport=PHONE)

    states = next(s for s in series_of(page, "obstacles-distance") if s.get("name") == "Стан слота")
    kinds = {row[0]: row[1] for row in states["data"]}
    assert kinds == {2: "no_holds", 3: "no_data"}  # індекси слотів 38 і 39


def test_control_off_bars_zero_is_a_zero_height_bar_with_label(
    browser: Any, base_url: str, serve_snapshot: Callable[[Snapshot], None]
) -> None:
    serve_snapshot(snapshot())
    page, _ = open_page(browser, base_url, viewport=PHONE)

    bar = next(s for s in series_of(page, "obstacles-control-off") if s["type"] == "bar")
    items = bar["data"]
    values = [d["value"] if isinstance(d, dict) else d for d in items]
    assert values == [0.0, 6.66, 1.5, 0.0, None, 0.0]  # слот 40 — пропуск
    assert items[0]["label"]["formatter"] == "0 с" and items[1]["label"]["formatter"] == "6,7 с"


def test_tooltip_for_a_slot_with_distance_sensor_and_protection(
    browser: Any, base_url: str, serve_snapshot: Callable[[Snapshot], None]
) -> None:
    serve_snapshot(snapshot())
    page, watch = open_page(browser, base_url, viewport=PHONE, has_touch=True)

    tap_slot(page, "obstacles-distance", "37")
    tip = page.locator(".chart-tip").first
    tip.wait_for()

    text = tip.inner_text()
    assert "Виїзд № 37" in text and "Отримано (за київським часом): 24.10.2026 13:13" in text
    assert "Найменша відстань — 103 мм" in text
    assert "Датчик — лівий передній" in text
    assert "Захист вимкнено — 6,7 с" in text
    watch.assert_clean(base_url)


def test_tooltip_no_holds_and_not_reported_are_different(
    browser: Any, base_url: str, serve_snapshot: Callable[[Snapshot], None]
) -> None:
    serve_snapshot(snapshot())
    page, _ = open_page(browser, base_url, viewport=PHONE, has_touch=True)

    tap_slot(page, "obstacles-distance", "38")
    page.get_by_text("Виїзд № 38").first.wait_for()
    no_holds = page.locator(".chart-tip").first.inner_text()
    assert "Найменша відстань — утримань не було" in no_holds
    assert "немає даних" not in no_holds.split("Захист")[0]
    assert "Захист вимкнено — 1,5 с" in no_holds

    tap_slot(page, "obstacles-distance", "39")
    page.get_by_text("Виїзд № 39").first.wait_for()
    missing = page.locator(".chart-tip").first.inner_text()
    assert "Найменша відстань — немає даних — ровер не передав: відстань до перешкоди" in missing
    assert "Захист вимкнено — 0 с" in missing


def test_gap_slot_has_no_tooltip(
    browser: Any, base_url: str, serve_snapshot: Callable[[Snapshot], None]
) -> None:
    serve_snapshot(snapshot())
    page, _ = open_page(browser, base_url, viewport=PHONE, has_touch=True)

    tap_slot(page, "obstacles-control-off", "39")  # контроль: дотик до виїзду підказку показує
    page.get_by_text("Виїзд № 39").first.wait_for()
    tap_slot(page, "obstacles-control-off", "40")

    expect(page.locator(".chart-tip:visible")).to_have_count(0)  # попередня підказка зникла
    expect(page.get_by_text("Виїзд № 40")).to_have_count(0)


def test_markup_in_report_sensor_is_text_only_never_executed(
    browser: Any, base_url: str, serve_snapshot: Callable[[Snapshot], None]
) -> None:
    serve_snapshot(snapshot())
    page, watch = open_page(browser, base_url, viewport=PHONE, has_touch=True)

    tap_slot(page, "obstacles-distance", "41")
    tip = page.locator(".chart-tip").first
    tip.wait_for()

    assert XSS in tip.inner_text()  # як текст
    assert tip.locator("img").count() == 0
    assert page.evaluate("window.__pwned === undefined")
    assert page.locator("body img").count() == 0
    watch.assert_clean(base_url)


def test_slot_state_text_names_the_reason_along_the_slot(
    browser: Any, base_url: str, serve_snapshot: Callable[[Snapshot], None]
) -> None:
    """Review F3, AC-12/AC-08: штрихування підписане причиною, а «утримань не було» лишається."""
    serve_snapshot(snapshot())
    page, _ = open_page(browser, base_url, viewport=PHONE)

    states = next(s for s in series_of(page, "obstacles-distance") if s.get("name") == "Стан слота")
    texts = {row[0]: row[2] for row in states["data"]}
    assert texts == {
        2: "утримань не було",
        3: "немає даних — ровер не передав: відстань до перешкоди",
    }


def test_tooltip_has_holds_duration_and_protection_as_duration_text(
    browser: Any, base_url: str, serve_snapshot: Callable[[Snapshot], None]
) -> None:
    """Review F4, SCR-05: «Утримань: N» (нуль виміряний), тривалість виїзду, захист «7 хв 56 с»."""
    sessions = [
        session(
            1,
            holds_count=1,
            holds_min_mm=80,
            holds_min_sensor="front",
            tof_control_off_ms=475800,
            duration_ms=657000,
        ),
        session(2, holds_count=0, tof_control_off_ms=1500, duration_ms=8300),
    ]
    serve_snapshot(Snapshot(sessions, []))
    page, _ = open_page(browser, base_url, viewport=PHONE, has_touch=True)

    tap_slot(page, "obstacles-distance", "1")
    page.get_by_text("Виїзд № 1").first.wait_for()
    first = page.locator(".chart-tip").first.inner_text()
    assert "Утримань — 1" in first
    assert "Захист вимкнено — 7 хв 56 с" in first
    assert "Тривалість виїзду — 10 хв 57 с" in first

    tap_slot(page, "obstacles-distance", "2")
    page.get_by_text("Виїзд № 2").first.wait_for()
    second = page.locator(".chart-tip").first.inner_text()
    assert "Утримань — 0" in second and "Найменша відстань — утримань не було" in second
    assert "Тривалість виїзду — 8,3 с" in second
