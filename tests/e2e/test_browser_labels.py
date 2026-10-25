"""Читабельність підписів на вузькому екрані: нічого не виходить за полотно й не перекривається.

Review G1, G2, G5, AC-12, AC-13, AC-18. Дані близькі до реальних сесій 36–39 (виїзд без руху,
без обох енкодерів, з відсічкою нижче 6,0 В), екран — телефон 360 px.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from e2e_support import text_problems, watch_page

from rover_telemetry.db.reading import Snapshot
from rover_telemetry.domain.dashboard import StoredSession

pytest.importorskip("playwright.sync_api")

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
    "voltage_start_mv": 7600,
    "voltage_min_mv": 5000,
    "voltage_end_mv": 7500,
    "end_reason": "failsafe_voltage",
}
NO_SPEEDS = {
    "speed_left_avg_rpm": None,
    "speed_left_peak_rpm": None,
    "speed_right_avg_rpm": None,
    "speed_right_peak_rpm": None,
    "speed_imbalance_pct": None,
}


def session(seq: int, **fields: Any) -> StoredSession:
    return StoredSession(
        mac=MAC, seq=seq, received_at=datetime(2026, 10, 24, 10, 13, tzinfo=UTC), **fields
    )


def snapshot() -> Snapshot:
    """36 повний (мінімум нижче відсічки); 37 без обох енкодерів і без мінімальної напруги;
    38 не їхав."""
    return Snapshot(
        [
            session(36, **FULL),
            session(
                37,
                **{
                    **FULL,
                    **NO_SPEEDS,
                    "encoders_left": False,
                    "encoders_right": False,
                    "voltage_min_mv": None,
                },
            ),
            session(38, **{**FULL, **NO_SPEEDS, "moving_ms": 0}),
        ],
        [],
    )


@pytest.mark.parametrize(
    "name", ["battery-voltage", "battery-drop", "motion-speed", "motion-imbalance"]
)
def test_chart_texts_stay_inside_and_do_not_overlap_on_a_phone(
    browser: Any, base_url: str, serve_snapshot: Callable[[Snapshot], None], name: str
) -> None:
    serve_snapshot(snapshot())
    page = browser.new_context(viewport=PHONE, has_touch=True).new_page()
    watch_page(page)
    page.goto(f"{base_url}/")
    page.locator(f'[data-chart="{name}"] canvas').wait_for()

    assert text_problems(page, name) == []
