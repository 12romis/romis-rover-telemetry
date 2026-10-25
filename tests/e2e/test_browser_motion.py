"""Блок «Рух і борти» у браузері: борти, піки, різниця, причини відсутності (AC-10…AC-13)."""

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
FULL = {
    "moving_ms": 2360,
    "speed_left_avg_rpm": 50.8,
    "speed_left_peak_rpm": 181.9,
    "speed_right_avg_rpm": 45.1,
    "speed_right_peak_rpm": 181.4,
    "speed_imbalance_pct": 1.7,
    "encoders_left": True,
    "encoders_right": True,
}


def session(seq: int, **fields: Any) -> StoredSession:
    return StoredSession(
        mac=MAC, seq=seq, received_at=datetime(2026, 10, 24, 10, 13, tzinfo=UTC), **fields
    )


def snapshot() -> Snapshot:
    """36 повний; 37 не їхав; 38 без прямої ділянки; 39 без лівого енкодера; 40 втрачено;
    41 правий швидший, виміряний нуль швидкості."""
    sessions = [
        session(36, **FULL),
        session(37, moving_ms=0, encoders_left=True, encoders_right=True),
        session(38, **{**FULL, "speed_imbalance_pct": None}),
        session(
            39,
            moving_ms=2000,
            encoders_left=False,
            encoders_right=True,
            speed_right_avg_rpm=45.1,
            speed_right_peak_rpm=181.4,
        ),
        session(41, **{**FULL, "speed_left_avg_rpm": 0.0, "speed_imbalance_pct": -2.5}),
    ]
    return Snapshot(sessions, [GapNumber(MAC, 40)])


def open_page(browser: Any, base_url: str, **context: Any) -> tuple[Any, Any]:
    page = browser.new_context(**context).new_page()
    watch = watch_page(page)
    page.goto(f"{base_url}/")
    page.locator('[data-chart="motion-speed"] canvas').wait_for()
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


def values(series: dict[str, Any]) -> list[Any]:
    return [d["value"] if isinstance(d, dict) else d for d in series["data"]]


def test_charts_fit_phone_width_and_paint(
    browser: Any, base_url: str, serve_snapshot: Callable[[Snapshot], None]
) -> None:
    serve_snapshot(snapshot())
    page, watch = open_page(browser, base_url, viewport=PHONE, has_touch=True)

    for name in ("motion-speed", "motion-imbalance"):
        box = page.locator(f'[data-chart="{name}"]').bounding_box()
        assert box is not None and box["x"] >= 0 and box["x"] + box["width"] <= PHONE["width"]
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    painted = page.evaluate(
        """() => [...document.querySelectorAll('[data-chart^="motion"] canvas')].every(c => {
          const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
          for (let i = 3; i < d.length; i += 4) if (d[i] !== 0) return true;
          return false;
        })"""
    )
    assert painted
    watch.assert_clean(base_url)


def test_speed_bars_in_mps_left_solid_right_decal_missing_not_zero(
    browser: Any, base_url: str, serve_snapshot: Callable[[Snapshot], None]
) -> None:
    serve_snapshot(snapshot())
    page, _ = open_page(browser, base_url, viewport=PHONE)

    bars = {s["name"]: s for s in series_of(page, "motion-speed") if s["type"] == "bar"}
    left, right = values(bars["Лівий борт"]), values(bars["Правий борт"])
    assert left[0] == pytest.approx(50.8 * 0.1382 / 60)
    assert right[0] == pytest.approx(45.1 * 0.1382 / 60)
    # 37 не їхав, 39 лівий без енкодера, 40 пропуск — немає стовпців (не нулі)
    assert left[1] is None and left[3] is None and left[4] is None and right[1] is None
    assert right[3] == pytest.approx(45.1 * 0.1382 / 60)
    assert left[5] == 0  # виміряний нуль лишається стовпцем нульової висоти
    assert bars["Правий борт"]["itemStyle"].get("decal") is not None
    assert not bars["Лівий борт"]["itemStyle"].get("decal")


def test_peak_markers_are_triangles_over_own_side(
    browser: Any, base_url: str, serve_snapshot: Callable[[Snapshot], None]
) -> None:
    serve_snapshot(snapshot())
    page, _ = open_page(browser, base_url, viewport=PHONE)

    series = series_of(page, "motion-speed")
    peaks = [s for s in series if s.get("name") in ("Пік лівого борту", "Пік правого борту")]
    assert len(peaks) == 2
    left = next(s for s in peaks if s["name"] == "Пік лівого борту")
    assert left["data"][0][1] == pytest.approx(181.9 * 0.1382 / 60)
    assert left["data"][1][1] is None and left["data"][3][1] is None


def test_imbalance_signed_bars_from_zero_with_direction_labels(
    browser: Any, base_url: str, serve_snapshot: Callable[[Snapshot], None]
) -> None:
    serve_snapshot(snapshot())
    page, _ = open_page(browser, base_url, viewport=PHONE)

    bar = next(s for s in series_of(page, "motion-imbalance") if s["type"] == "bar")
    assert values(bar) == [1.7, None, None, None, None, -2.5]
    labels = [d["label"]["formatter"] for d in bar["data"] if isinstance(d, dict)]
    assert "лівий" in labels[0] and "швидший" in labels[0]
    assert "правий" in labels[1] and "швидший" in labels[1]


def test_slot_states_not_moving_no_straight_and_no_encoder(
    browser: Any, base_url: str, serve_snapshot: Callable[[Snapshot], None]
) -> None:
    serve_snapshot(snapshot())
    page, _ = open_page(browser, base_url, viewport=PHONE)

    speed = next(s for s in series_of(page, "motion-speed") if s.get("name") == "Стан слота")
    assert {r[0]: r[1] for r in speed["data"]} == {1: "no_data"}  # лише «не їхав»
    imb = next(s for s in series_of(page, "motion-imbalance") if s.get("name") == "Стан слота")
    assert {r[0]: r[1] for r in imb["data"]} == {1: "no_data", 2: "no_data", 3: "no_data"}
    caption = next(s for s in series_of(page, "motion-speed") if s.get("name") == "Без енкодера")
    assert [(r[0], r[1]) for r in caption["data"]] == [(3, "без енкодера: лівий борт")]


def test_tooltip_has_both_sides_in_mps_and_rpm_and_imbalance(
    browser: Any, base_url: str, serve_snapshot: Callable[[Snapshot], None]
) -> None:
    serve_snapshot(snapshot())
    page, watch = open_page(browser, base_url, viewport=PHONE, has_touch=True)

    tap_slot(page, "motion-speed", "36")
    tip = page.locator(".chart-tip").first
    tip.wait_for()
    text = tip.inner_text()
    assert "Виїзд № 36" in text and "Отримано (за київським часом): 24.10.2026 13:13" in text
    assert "Лівий борт, середня — 50,8 об/хв (0,117 м/с)" in text
    assert "Лівий борт, пікова — 181,9 об/хв (0,419 м/с)" in text
    assert "Правий борт, середня — 45,1 об/хв (0,104 м/с)" in text
    assert "Різниця бортів — 1,7 %, лівий борт швидший" in text
    watch.assert_clean(base_url)


def test_tooltip_reasons_do_not_mix(
    browser: Any, base_url: str, serve_snapshot: Callable[[Snapshot], None]
) -> None:
    serve_snapshot(snapshot())
    page, _ = open_page(browser, base_url, viewport=PHONE, has_touch=True)

    tap_slot(page, "motion-speed", "37")
    page.get_by_text("Виїзд № 37").first.wait_for()
    assert (
        "Лівий борт, середня — немає даних — ровер не їхав"
        in page.locator(".chart-tip").first.inner_text()
    )

    tap_slot(page, "motion-speed", "38")
    page.get_by_text("Виїзд № 38").first.wait_for()
    text = page.locator(".chart-tip").first.inner_text()
    assert "Лівий борт, середня — 50,8 об/хв" in text
    assert "Різниця бортів — немає даних — прямої ділянки не було" in text

    tap_slot(page, "motion-speed", "39")
    page.get_by_text("Виїзд № 39").first.wait_for()
    text = page.locator(".chart-tip").first.inner_text()
    assert "Лівий борт, середня — немає даних — на борту не було енкодера (лівий борт)" in text
    assert "Правий борт, середня — 45,1 об/хв" in text
    assert "Енкодера не було — лівий борт" in text


def test_gap_slot_has_no_tooltip(
    browser: Any, base_url: str, serve_snapshot: Callable[[Snapshot], None]
) -> None:
    serve_snapshot(snapshot())
    page, _ = open_page(browser, base_url, viewport=PHONE, has_touch=True)

    tap_slot(page, "motion-imbalance", "41")  # контроль: дотик до виїзду підказку показує
    page.get_by_text("Виїзд № 41").first.wait_for()
    tap_slot(page, "motion-imbalance", "40")

    expect(page.locator(".chart-tip:visible")).to_have_count(0)  # попередня підказка зникла
    expect(page.get_by_text("Виїзд № 40")).to_have_count(0)


def test_slot_state_text_names_the_reason_along_the_slot(
    browser: Any, base_url: str, serve_snapshot: Callable[[Snapshot], None]
) -> None:
    """Review F3, AC-12: «немає даних — ровер не їхав» / «— прямої ділянки не було»."""
    serve_snapshot(snapshot())
    page, _ = open_page(browser, base_url, viewport=PHONE)

    speed = next(s for s in series_of(page, "motion-speed") if s.get("name") == "Стан слота")
    imb = next(s for s in series_of(page, "motion-imbalance") if s.get("name") == "Стан слота")
    assert {row[0]: row[2] for row in speed["data"]}[1] == "немає даних — ровер не їхав"
    texts = {row[0]: row[2] for row in imb["data"]}
    assert texts[1] == "немає даних — ровер не їхав"
    assert texts[2] == "немає даних — прямої ділянки не було"


def test_slot_without_both_encoders_names_both_sides_not_one(
    browser: Any, base_url: str, serve_snapshot: Callable[[Snapshot], None]
) -> None:
    """Review G1, AC-12, AC-13: за двох відсутніх енкодерів слот не називає лише лівий борт."""
    none = {
        "speed_left_avg_rpm": None,
        "speed_left_peak_rpm": None,
        "speed_right_avg_rpm": None,
        "speed_right_peak_rpm": None,
        "speed_imbalance_pct": None,
    }
    serve_snapshot(
        Snapshot(
            [session(37, **{**FULL, **none, "encoders_left": False, "encoders_right": False})],
            [],
        )
    )
    page, _ = open_page(browser, base_url, viewport=PHONE)

    speed = next(s for s in series_of(page, "motion-speed") if s.get("name") == "Стан слота")
    assert speed["data"][0][2] == "немає даних — на борту не було енкодера (обидва борти)"
    caption = next(s for s in series_of(page, "motion-speed") if s.get("name") == "Без енкодера")
    assert caption["data"] == [[0, "без енкодера: обидва борти"]]
