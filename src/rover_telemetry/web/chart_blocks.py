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
from rover_telemetry.domain.charts import Slot
from rover_telemetry.web.formatting import format_received

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


# Порожній за замовчуванням: кожна задача блока додає свій запис (T10–T12).
BLOCKS: list[BlockSpec] = []


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
