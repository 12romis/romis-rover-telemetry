"""Реєстр блоків графіків: кожен блок будується окремо, збій одного не ламає сторінку (AC-19).

Блоки додають свої записи в `BLOCKS` (Акумулятор → Перешкоди → Рух і борти — порядок виводу).
Дані блока для `charts.js` мають спільну оболонку (`block_data_shell`):

    {"block": key,
     "slots": [{"seq": N, "gap": bool, "received": "ДД.ММ.РРРР ГГ:ХВ" | None}, ...],
     "constants": {"cutoff_v", "full_charge_v", "obstacle_threshold_mm",
                   "battery_cells", "wheel_circumference_m"}}

плюс ключі, специфічні для блока. `received` — «отримано» за київським часом, не час виїзду.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from rover_telemetry.db.reading import Snapshot
from rover_telemetry.domain import charts
from rover_telemetry.domain.charts import (
    Absent,
    BatteryPoint,
    Point,
    Slot,
    Value,
    build_axis,
    build_battery,
)
from rover_telemetry.domain.dashboard import EndReason
from rover_telemetry.web.formatting import absent_reason_label, end_reason_label, format_received

logger = logging.getLogger("rover_telemetry.web")


@dataclass(frozen=True)
class BlockView:
    """Те, що будує блок: шаблон вмісту, його контекст (`ctx` у шаблоні) і JSON для скрипта."""

    template: str
    context: dict[str, Any]
    data: dict[str, Any]


@dataclass(frozen=True)
class BlockSpec:
    key: str
    title: str
    description: str
    build: Callable[[Snapshot], BlockView]


@dataclass(frozen=True)
class RenderedBlock:
    """Стан блока на сторінці: `ok` (є `view`), `empty` (виїздів немає) або `error`."""

    key: str
    title: str
    description: str
    state: str
    view: BlockView | None


def _number(point: Point | None) -> float | None:
    """Відсутнє значення (і порожній слот) стає `null`, а не нулем (конституція №4)."""
    return point.number if isinstance(point, Value) else None


def _gap_line(axis: list[Slot]) -> list[str]:
    gaps = [f"№ {slot.seq}" for slot in axis if slot.session is None]
    return [f"Сесії, що не дійшли: {', '.join(gaps)}."] if gaps else []


# --- Акумулятор (AC-01…AC-04, AC-14) ---------------------------------------------------------

# Копія з маніфесту екранів (screens.md, «Копія „Акумулятор“»); тест звіряє дослівно.
_BATTERY_DESCRIPTION = (
    "Акумулятор. Тут видно, як змінювалася напруга акумулятора від виїзду до виїзду. Кожен виїзд "
    "стоїть на своєму номері на горизонтальній осі — це номер сесії, а не час: старіші виїзди "
    "ліворуч, новіші праворуч. Для кожного виїзду показано напругу на початку, найнижчу за виїзд і "
    "наприкінці. Нижня лінія (6,0 В) — межа відсічки: коли напруга падає нижче, ровер припиняє "
    "роботу; верхня (8,4 В) — повністю заряджений акумулятор. Просадка — на скільки напруга впала "
    "під навантаженням: початкова мінус найнижча. Лінії між виїздами немає: між ними акумулятор "
    "міг заряджатися. Акумулятор складається з двох банок, напруга однієї банки — половина "
    "показаної."
)
_BATTERY_VALUES = ("start", "min", "end")


def _battery_reasons(points: list[BatteryPoint]) -> list[dict[str, Any]]:
    reasons: list[dict[str, Any]] = []
    for p in points:
        for name in (*_BATTERY_VALUES, "drop"):
            value = getattr(p, name)
            if isinstance(value, Absent):
                reasons.append(
                    {
                        "seq": p.seq,
                        "value": name,
                        "code": value.reason.value,
                        "label": absent_reason_label(value),
                    }
                )
    return reasons


def _battery_notes(points: list[BatteryPoint], axis: list[Slot]) -> list[str]:
    notes: list[str] = []
    for p in points:
        for name in _BATTERY_VALUES:
            value = getattr(p, name)
            if isinstance(value, Absent):
                # Без початкової чи мінімальної просадку обчислити неможливо.
                suffix = " (просадку не обчислено)" if name in ("start", "min") else ""
                notes.append(f"Немає даних — виїзд № {p.seq}: {value.subject}{suffix}.")
    return [*notes, *_gap_line(axis)]


def build_battery_block(snapshot: Snapshot) -> BlockView:
    axis = build_axis(snapshot.sessions, snapshot.gaps)
    block = build_battery(axis)
    points = [p for p in block.points if not p.is_gap]
    data = {
        **block_data_shell("battery", axis),
        "series": {n: [_number(getattr(p, n)) for p in block.points] for n in _BATTERY_VALUES},
        "per_cell": {
            n: [_number(getattr(p, f"per_cell_{n}")) for p in block.points] for n in _BATTERY_VALUES
        },
        "drop": [_number(p.drop) for p in block.points],
        "reasons": _battery_reasons(points),
        "largest_drop_seq": block.largest_drop_seq,
        # Підпис причини завершення — лише для занизької напруги (OP-3); інші без позначки.
        "end_reason_label": [
            end_reason_label(EndReason.VOLTAGE.value) if p.end_reason is EndReason.VOLTAGE else None
            for p in block.points
        ],
    }
    return BlockView("_charts_battery.html", {"notes": _battery_notes(points, axis)}, data)


# Порядок реєстру — порядок на сторінці: Акумулятор → Перешкоди → Рух і борти.
BLOCKS: list[BlockSpec] = [
    BlockSpec("battery", "Акумулятор", _BATTERY_DESCRIPTION, build_battery_block),
]


def block_data_shell(key: str, axis: list[Slot]) -> dict[str, Any]:
    return {
        "block": key,
        "slots": [
            {
                "seq": slot.seq,
                "gap": slot.session is None,
                "received": format_received(slot.session.received_at) if slot.session else None,
            }
            for slot in axis
        ],
        "constants": {
            "cutoff_v": charts.CUTOFF_V,
            "full_charge_v": charts.FULL_CHARGE_V,
            "obstacle_threshold_mm": charts.OBSTACLE_THRESHOLD_MM,
            "battery_cells": charts.BATTERY_CELLS,
            "wheel_circumference_m": charts.WHEEL_CIRCUMFERENCE_M,
        },
    }


def render_blocks(snapshot: Snapshot) -> list[RenderedBlock]:
    """Без виїздів усі блоки `empty` і не будуються (AC-17); збій блока — лише `error` (AC-19)."""
    blocks: list[RenderedBlock] = []
    for spec in BLOCKS:
        if not snapshot.sessions:
            blocks.append(RenderedBlock(spec.key, spec.title, spec.description, "empty", None))
            continue
        try:
            view = spec.build(snapshot)
        except Exception as exc:  # межа ізоляції: причина лише в лог, на сторінку — повідомлення
            logger.error("chart_block_failed block=%s error_class=%s", spec.key, type(exc).__name__)
            blocks.append(RenderedBlock(spec.key, spec.title, spec.description, "error", None))
            continue
        blocks.append(RenderedBlock(spec.key, spec.title, spec.description, "ok", view))
    return blocks
