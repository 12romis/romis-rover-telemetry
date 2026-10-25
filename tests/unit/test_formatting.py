"""Підписи та одиниці дашборду (AC-04, AC-06, AC-09)."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from rover_telemetry.domain.charts import Absent, AbsentReason
from rover_telemetry.web.formatting import (
    absent_reason_label,
    end_reason_label,
    format_distance_cm,
    format_duration_ms,
    format_received,
    format_report,
    format_voltage_mv,
    rover_name,
    sensor_label,
    side_label,
)
from rover_telemetry.web.templating import make_environment


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


# --- Підписи для графіків (feature dashboard-charts) ---


@pytest.mark.parametrize(
    ("absent", "expected"),
    [
        (Absent(AbsentReason.NOT_MOVING), "ровер не їхав"),
        (Absent(AbsentReason.NO_STRAIGHT), "прямої ділянки не було"),
        (Absent(AbsentReason.NO_HOLDS), "утримань не було"),
        (Absent(AbsentReason.NO_ENCODER), "на борту не було енкодера"),
        (Absent(AbsentReason.NO_ENCODER, "left"), "на борту не було енкодера (лівий борт)"),
        (Absent(AbsentReason.NO_ENCODER, "right"), "на борту не було енкодера (правий борт)"),
        (
            Absent(AbsentReason.NO_ENCODER, "left,right"),
            "на борту не було енкодера (обидва борти)",
        ),
        (Absent(AbsentReason.NOT_REPORTED), "ровер не передав"),
        (
            Absent(AbsentReason.NOT_REPORTED, "мінімальна напруга"),
            "ровер не передав: мінімальна напруга",
        ),
    ],
)
def test_absent_reason_label(absent: Absent, expected: str) -> None:
    assert absent_reason_label(absent) == expected


def test_every_absent_reason_has_a_label() -> None:
    """Нова причина без підпису не може потрапити на сторінку."""
    for reason in AbsentReason:
        assert absent_reason_label(Absent(reason)).strip(), reason


def test_html_in_subject_stays_text() -> None:
    label = absent_reason_label(Absent(AbsentReason.NOT_REPORTED, "<b>x</b>"))
    env = make_environment()

    rendered = env.from_string("{{ absent_reason_label(a) }}").render(
        a=Absent(AbsentReason.NOT_REPORTED, "<b>x</b>"), absent_reason_label=absent_reason_label
    )

    assert "<b>" in label  # функція не екранує: це справа autoescape
    assert "<b>" not in rendered and "&lt;b&gt;" in rendered


@pytest.mark.parametrize(
    ("raw", "label"),
    [
        ("left_front", "лівий передній"),
        ("front", "передній"),
        ("right_front", "правий передній"),
        ("rear", "задній"),
        ("<b>x</b>", "Інший датчик"),
        ("", "Інший датчик"),
    ],
)
def test_sensor_label(raw: str, label: str) -> None:
    assert sensor_label(raw) == label


@pytest.mark.parametrize(
    ("raw", "label"),
    [
        ("left", "лівий борт"),
        ("right", "правий борт"),
        ("left,right", "обидва борти"),
        ("other", ""),
    ],
)
def test_side_label(raw: str, label: str) -> None:
    assert side_label(raw) == label


def test_chart_formatters_registered_in_environment() -> None:
    env = make_environment()
    for name in (
        "absent_reason_label",
        "sensor_label",
        "side_label",
    ):
        assert name in env.globals, name
