"""Підписи та одиниці дашборду (AC-04, AC-06, AC-09)."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from rover_telemetry.web.formatting import (
    end_reason_label,
    format_distance_cm,
    format_duration_ms,
    format_received,
    format_report,
    format_voltage_mv,
    rover_name,
)


@pytest.mark.parametrize(
    ("cm", "expected"),
    [(17, "0,17 м"), (0, "0 м"), (150, "1,5 м"), (1234, "12,34 м"), (100, "1 м")],
)
def test_distance(cm: int, expected: str) -> None:
    """AC-06: виміряний нуль — «0 м»; метри з комою, до двох знаків."""
    assert format_distance_cm(cm) == expected


@pytest.mark.parametrize(
    ("ms", "expected"),
    [
        (0, "0 с"),
        (4300, "4,3 с"),
        (27660, "27,7 с"),
        (5000, "5 с"),
        (59949, "59,9 с"),
        (187000, "3 хв 7 с"),
        (60000, "1 хв 0 с"),
        (3720000, "1 год 2 хв"),
    ],
)
def test_duration(ms: int, expected: str) -> None:
    """AC-06: нуль — «0 с»; від 60 с — хвилини, від 60 хв — години."""
    assert format_duration_ms(ms) == expected


def test_duration_rounds_half_up() -> None:
    """Припущення: секунди у формі «хв с» округляються ROUND_HALF_UP (screens.md мовчить)."""
    assert format_duration_ms(60500) == "1 хв 1 с"
    assert format_duration_ms(250) == "0,3 с"


@pytest.mark.parametrize(("mv", "expected"), [(7691, "7,69 В"), (7675, "7,68 В"), (7700, "7,70 В")])
def test_voltage(mv: int, expected: str) -> None:
    assert format_voltage_mv(mv) == expected


def test_none_stays_none_for_all() -> None:
    """AC-06: відсутнє значення — `None` (шаблон покаже «немає даних»), не «0» і не «—»."""
    assert format_distance_cm(None) is None
    assert format_duration_ms(None) is None
    assert format_voltage_mv(None) is None
    assert format_received(None) is None
    assert end_reason_label(None) is None
    assert format_report(None) is None


def test_received_kyiv_with_dst_change() -> None:
    """AC-09: Київ переходить на зимовий час 2026-10-25: до +3, після +2."""
    before = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
    after = datetime(2026, 10, 25, 12, 0, tzinfo=UTC)
    assert format_received(before) == "24.10.2026 15:00"
    assert format_received(after) == "25.10.2026 14:00"


def test_no_session_time_wording() -> None:
    """Конституція №5: слів «час виїзду»/«час сесії» у модулі немає."""
    import rover_telemetry.web.formatting as module

    source = Path(module.__file__).read_text().lower()
    assert "час виїзду" not in source
    assert "час сесії" not in source


@pytest.mark.parametrize(
    ("raw", "label"),
    [
        ("disarm", "Роззброєння"),
        ("failsafe_link_lost", "Зникнення зв'язку з пультом"),
        ("failsafe_voltage", "Занизька напруга акумулятора"),
        ("brand_new", "Інша причина"),
    ],
)
def test_end_reason_label(raw: str, label: str) -> None:
    """AC-04: відома причина словами, невідома — «Інша причина»."""
    assert end_reason_label(raw) == label


def test_rover_name() -> None:
    assert rover_name("288485922c94") == "RomisRover"
    assert rover_name("aabbccddeeff") == "aabbccddeeff"


def test_format_report_keeps_order_nulls_and_does_not_escape(
    report_seq26: dict[str, Any],
) -> None:
    """AC-05, AC-06: порядок ключів не міняється, null лишається null, розмітки не екрановано."""
    text = format_report(report_seq26)
    assert text is not None
    assert json.loads(text) == report_seq26
    assert "null" in text
    assert text.index('"event"') < text.index('"mac"')
    assert format_report({"x": "<b>&"}) == '{\n  "x": "<b>&"\n}'
    assert format_report({"т": "я"}) == '{\n  "т": "я"\n}'  # ensure_ascii=False
