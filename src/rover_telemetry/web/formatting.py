"""Підписи, одиниці й час для дашборду. `None` («немає даних») ніде не стає нулем чи прочерком."""

import json
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from zoneinfo import ZoneInfo

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
