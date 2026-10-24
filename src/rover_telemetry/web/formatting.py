"""Підписи, одиниці й час для дашборду. `None` («немає даних») ніде не стає нулем чи прочерком."""

import json
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from zoneinfo import ZoneInfo

from rover_telemetry.domain.charts import Absent, AbsentReason
from rover_telemetry.domain.dashboard import EndReason, classify_end_reason

KYIV = ZoneInfo("Europe/Kyiv")
# Рішення власника №10: єдиний відомий ровер має ім'я; решта показуються ідентифікатором плати.
_ROVER_NAMES = {"288485922c94": "RomisRover"}
_REASON_LABELS = {
    EndReason.DISARM: "Роззброєння",
    EndReason.LINK_LOST: "Зникнення зв'язку з пультом",
    EndReason.VOLTAGE: "Занизька напруга акумулятора",
    EndReason.OTHER: "Інша причина",
}


def _decimal(value: Decimal, places: int, *, keep_zeros: bool) -> str:
    """Округлення ROUND_HALF_UP; кома як розділювач; зайві нулі в кінці — за `keep_zeros`."""
    text = str(value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP))
    if not keep_zeros and "." in text:
        text = text.rstrip("0").rstrip(".")
    return text.replace(".", ",")


def format_distance_cm(cm: int | None) -> str | None:
    """`17` → `0,17 м`, `0` → `0 м`: метри до двох знаків."""
    if cm is None:
        return None
    return f"{_decimal(Decimal(cm) / 100, 2, keep_zeros=False)} м"


def format_duration_ms(ms: int | None) -> str | None:
    """До 60 с — `4,3 с`; від 60 с — `3 хв 7 с`; від 60 хв — `1 год 2 хв`.

    Припущення (screens.md правила не фіксує): у формах «хв с» і «год хв» цілі секунди
    округляються ROUND_HALF_UP.
    """
    if ms is None:
        return None
    if ms < 59950:  # менше за 59,95 с округляється до однієї десяткової нижче 60
        return f"{_decimal(Decimal(ms) / 1000, 1, keep_zeros=False)} с"
    seconds = int((Decimal(ms) / 1000).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours} год {minutes} хв"
    return f"{minutes} хв {sec} с"


def format_voltage_mv(mv: int | None) -> str | None:
    """`7691` → `7,69 В`: вольти з двома знаками."""
    if mv is None:
        return None
    return f"{_decimal(Decimal(mv) / 1000, 2, keep_zeros=True)} В"


def format_received(moment: datetime | None) -> str | None:
    """«Отримано» за київським часом, `ДД.ММ.РРРР ГГ:ХВ`; єдиний час на сторінці."""
    if moment is None:
        return None
    return moment.astimezone(KYIV).strftime("%d.%m.%Y %H:%M")


def end_reason_label(raw: str | None) -> str | None:
    reason = classify_end_reason(raw)
    return None if reason is None else _REASON_LABELS[reason]


def rover_name(mac: str) -> str:
    return _ROVER_NAMES.get(mac, mac)


def format_report(payload: dict[str, Any] | None) -> str | None:
    """Звіт як надіслано ровером, порядок ключів `jsonb`; екранування — справа шаблону."""
    if payload is None:
        return None
    return json.dumps(payload, ensure_ascii=False, indent=2)


# --- Підписи для графіків (feature dashboard-charts) ---

_SIDE_LABELS = {"left": "лівий борт", "right": "правий борт", "left,right": "обидва борти"}
_SENSOR_LABELS = {
    "left_front": "лівий передній",
    "front": "передній",
    "right_front": "правий передній",
    "rear": "задній",
}
_OTHER_SENSOR = "Інший датчик"


def side_label(raw: str | None) -> str:
    """Борт простою мовою; невідоме значення — порожній рядок (сирого тексту не повертаємо)."""
    return _SIDE_LABELS.get(raw or "", "")


def sensor_label(raw: str | None) -> str:
    """Відомі датчики — зі словника; будь-яке інше значення звіту не потрапляє в підпис."""
    return _SENSOR_LABELS.get(raw or "", _OTHER_SENSOR)


def absent_reason_label(absent: Absent) -> str:
    """Причина відсутності простою мовою (screens.md); `subject` доповнює, але не обов'язковий."""
    reason = absent.reason
    if reason is AbsentReason.NOT_MOVING:
        return "ровер не їхав"
    if reason is AbsentReason.NO_STRAIGHT:
        return "прямої ділянки не було"
    if reason is AbsentReason.NO_HOLDS:
        return "утримань не було"
    if reason is AbsentReason.NO_ENCODER:
        side = side_label(absent.subject)
        return f"на борту не було енкодера ({side})" if side else "на борту не було енкодера"
    return f"ровер не передав: {absent.subject}" if absent.subject else "ровер не передав"


def format_speed_mps(rpm: float) -> str:
    """Лінійна швидкість: три знаки, кома; нуль — виміряне значення `0,000 м/с`."""
    mps = Decimal(str(rpm)) * Decimal("0.1382") / 60
    return f"{_decimal(mps, 3, keep_zeros=True)} м/с"


def format_rpm(rpm: float) -> str:
    return f"{_decimal(Decimal(str(rpm)), 1, keep_zeros=True)} об/хв"


def format_voltage_per_cell(mv: int | None) -> str | None:
    """Напруга однієї банки: половина показаної (рішення власника №8)."""
    if mv is None:
        return None
    return f"{_decimal(Decimal(mv) / 2000, 2, keep_zeros=True)} В на банку"
