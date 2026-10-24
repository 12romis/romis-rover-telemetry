"""Фікстури seq 26 і 27 — реальні звіти ровера (конституція №15)."""

from typing import Any


def test_fixtures_are_real_reports(
    report_seq26: dict[str, Any], report_seq27: dict[str, Any]
) -> None:
    assert report_seq26["seq"] == 26
    assert report_seq27["seq"] == 27
    assert report_seq26["event"] == report_seq27["event"] == "rover.session.v1"
    assert report_seq26["mac"] == report_seq27["mac"] == "288485922c94"


def test_null_is_preserved_in_fixture(report_seq26: dict[str, Any]) -> None:
    assert report_seq26["speed"]["left_avg_rpm"] is None
    assert report_seq26["distance_cm"] == 0
