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
from datetime import datetime
from functools import lru_cache
from typing import Any

from jinja2 import Environment
from jinja2.utils import htmlsafe_json_dumps
from markupsafe import Markup

from rover_telemetry.db.reading import Snapshot
from rover_telemetry.domain import charts
from rover_telemetry.domain.charts import (
    Absent,
    BatteryPoint,
    MotionPoint,
    ObstaclePoint,
    Point,
    Slot,
    SpeedPoint,
    SpeedValue,
    Value,
    build_axis,
    build_battery,
    build_motion,
    build_obstacles,
)
from rover_telemetry.domain.dashboard import EndReason, Total, build_summary
from rover_telemetry.web.formatting import (
    absent_reason_label,
    end_reason_label,
    format_duration_ms,
    format_received,
    known_sensor,
    sensor_label,
    side_label,
)
from rover_telemetry.web.templating import make_environment

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
    """Стан блока на сторінці: `ok` (є `view` і готовий `content`), `empty` або `error`."""

    key: str
    title: str
    description: str
    state: str
    view: BlockView | None
    content: Markup | None = None
    data_json: Markup | None = None  # дані блока для `<script type="application/json">`


def _number(point: Point | None) -> float | None:
    """Відсутнє значення (і порожній слот) стає `null`, а не нулем (конституція №4)."""
    return point.number if isinstance(point, Value) else None


def _gap_line(axis: list[Slot]) -> list[str]:
    gaps = [f"№ {slot.seq}" for slot in axis if slot.session is None]
    return [f"Сесії, що не дійшли: {', '.join(gaps)}."] if gaps else []


# --- Акумулятор (AC-01…AC-04, AC-14) ---------------------------------------------------------

_CELLS_GENITIVE = {2: "двох"}  # кількість банок прописом; інша кількість — явна правка тут


def _volts(value: float) -> str:
    return f"{value:.1f}".replace(".", ",")


def battery_description(
    cutoff_v: float = charts.CUTOFF_V,
    full_charge_v: float = charts.FULL_CHARGE_V,
    cells: int = charts.BATTERY_CELLS,
) -> str:
    """Копія з маніфесту екранів (screens.md, «Копія „Акумулятор“»); числа — з констант (№3)."""
    return (
        "Акумулятор. Тут видно, як змінювалася напруга акумулятора від виїзду до виїзду. Кожен "
        "виїзд стоїть на своєму номері на горизонтальній осі — це номер сесії, а не час: старіші "
        "виїзди ліворуч, новіші праворуч. Для кожного виїзду показано напругу на початку, "
        "найнижчу за виїзд і наприкінці. "
        f"Нижня лінія ({_volts(cutoff_v)} В) — межа відсічки: коли напруга падає нижче, ровер "
        f"припиняє роботу; верхня ({_volts(full_charge_v)} В) — повністю заряджений акумулятор. "
        "Просадка — на скільки напруга впала під навантаженням: початкова мінус найнижча. Лінії "
        "між виїздами немає: між ними акумулятор міг заряджатися. "
        f"Акумулятор складається з {_CELLS_GENITIVE[cells]} банок, напруга однієї банки — "
        "половина показаної."
    )


_BATTERY_DESCRIPTION = battery_description()
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


# --- Перешкоди (AC-05…AC-09, AC-14) ----------------------------------------------------------

# Копія з маніфесту екранів (screens.md, «Копія „Перешкоди“»); поріг береться з константи.
_OBSTACLES_DESCRIPTION = (
    "Перешкоди. Ровер має чотири датчики відстані: лівий передній, передній, правий передній "
    f"і задній. Коли перед ровером перешкода ближча за поріг — {charts.OBSTACLE_THRESHOLD_MM} "
    "мм, — він зупиняється й чекає, доки шлях звільниться: це утримання. Схема показує, "
    "скільки разів кожен датчик на вході в утримання бачив перешкоду ближче за поріг, за "
    "всіма виїздами. Це лічильники датчиків, а не кількість утримань: в одному утриманні "
    "перешкоду можуть бачити кілька датчиків. Графік нижче показує для кожного виїзду "
    "найменшу відстань до перешкоди на вході в утримання й датчик, що її дав; виїзди стоять "
    "за номером сесії. Коли захист від перешкод вимкнено (тумблер на пульті), утримань не "
    "буває, тож їх відсутність тоді не означає, що перешкод не було; скільки секунд захист "
    "був вимкнений — показано окремо."
)
_SENSOR_CAPTION = (
    "Число біля датчика — у скількох утриманнях цей датчик на вході бачив перешкоду ближче за "
    f"{charts.OBSTACLE_THRESHOLD_MM} мм. Це спрацювання датчиків, а не утримання: суму чисел "
    "не можна читати як кількість утримань."
)
_PROTECTION_WARNING = (
    "За вимкненого захисту від перешкод утримань не буває, тож їх відсутність у такому виїзді "
    "не означає, що перешкод не було."
)
# Порядок на схемі: ключ лічильника, підпис датчика (словник підписів — у `formatting`).
_SENSORS = ("left_front", "front", "right_front", "rear")


def _obstacle_reasons(points: list[ObstaclePoint]) -> list[dict[str, Any]]:
    reasons: list[dict[str, Any]] = []
    for p in points:
        for name, value in (("distance", p.min_mm), ("control_off", p.control_off_s)):
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


def _obstacle_notes(points: list[ObstaclePoint], axis: list[Slot]) -> list[str]:
    notes: list[str] = []
    for p in points:
        for value in (p.min_mm, p.control_off_s):
            if not isinstance(value, Absent):
                continue
            if value.reason is charts.AbsentReason.NO_HOLDS:
                notes.append(f"Утримань не було — виїзд № {p.seq}.")
            else:
                notes.append(f"Немає даних — виїзд № {p.seq}: {value.subject} (ровер не передав).")
    return [*notes, *_gap_line(axis)]


def _holds_total(total: Total) -> tuple[int | None, str | None]:
    """«Утримань усього» — сума `holds_count`, а не сума лічильників датчиків (AC-06)."""
    note = None
    if total.sum is not None and total.missing > 0:
        note = f"без даних у {total.missing} з {total.total} виїздів"
    return total.sum, note


def build_obstacles_block(snapshot: Snapshot) -> BlockView:
    axis = build_axis(snapshot.sessions, snapshot.gaps)
    block = build_obstacles(axis)
    points = [p for p in block.points if not p.is_gap]
    counters = block.counters
    holds_total, holds_note = _holds_total(build_summary(snapshot.sessions, snapshot.gaps).holds)
    data = {
        **block_data_shell("obstacles", axis),
        "distance_mm": [_number(p.min_mm) for p in block.points],
        "no_holds": [
            isinstance(p.min_mm, Absent) and p.min_mm.reason is charts.AbsentReason.NO_HOLDS
            for p in block.points
        ],
        "sensor": [sensor_label(p.sensor) if p.sensor is not None else None for p in block.points],
        # Невідомий датчик іде сирим текстом окремо від підпису (скрипт вставить як textContent).
        "sensor_raw": [
            p.sensor if p.sensor is not None and not known_sensor(p.sensor) else None
            for p in block.points
        ],
        "control_off_s": [_number(p.control_off_s) for p in block.points],
        # Підказка (SCR-05): утримань (нуль — виміряний), захист і тривалість виїзду текстом.
        "holds_count": [slot.session.holds_count if slot.session else None for slot in axis],
        "control_off_text": [
            format_duration_ms(slot.session.tof_control_off_ms) if slot.session else None
            for slot in axis
        ],
        "duration_text": [
            format_duration_ms(slot.session.duration_ms) if slot.session else None for slot in axis
        ],
        "reasons": _obstacle_reasons(points),
    }
    context = {
        "sensors": [
            {"key": key, "label": sensor_label(key), "count": getattr(counters, key).sum}
            for key in _SENSORS
        ],
        "sensor_caption": _SENSOR_CAPTION,
        "holds_total": holds_total,
        "holds_note": holds_note,
        "protection_off": block.protection_off_any,
        "protection_warning": _PROTECTION_WARNING,
        "notes": _obstacle_notes(points, axis),
    }
    return BlockView("_charts_obstacles.html", context, data)


# --- Рух і борти (AC-10…AC-14) ---------------------------------------------------------------

# Копія з маніфесту екранів (screens.md, «Копія „Рух і борти“»); тест звіряє дослівно.
_MOTION_DESCRIPTION = (
    "Рух і борти. Борт — ліва або права сторона ровера, швидкість кожного борту вимірюється "
    "окремо. Графік показує для кожного виїзду середню швидкість борту за час руху "
    "(стовпець) і найбільшу (трикутник); виїзди стоять за номером сесії. Різниця бортів — на "
    "скільки відсотків один борт їхав швидше за інший на прямих ділянках: плюс — лівий "
    "швидший, мінус — правий. Це діагностична метрика за прямими ділянками, а не висновок "
    "про несправність, тому вона може не збігатися з різницею середніх швидкостей. Якщо "
    "швидкості немає, блок каже чому: ровер не їхав, на борту не було енкодера (датчика "
    "обертів колеса) або прямої ділянки не було."
)
_DIAGNOSTIC_CAPTION = (
    "Різниця бортів — діагностична метрика за прямими ділянками, а не висновок про несправність."
)
_MILEAGE_CAPTION = (
    "Без енкодера: пробіг такого виїзду рахувався за одним бортом, а якщо енкодера не було на "
    "обох бортах — пробігу немає."
)
_FASTER_LABELS = {
    "left": "лівий борт швидший",
    "right": "правий борт швидший",
    "equal": "борти їхали однаково",
}


def _speed_numbers(avg: SpeedPoint | None, peak: SpeedPoint | None) -> dict[str, float | None]:
    """Швидкості борту; відсутнє значення — `null`, нуль лишається числом."""
    a = avg if isinstance(avg, SpeedValue) else None
    p = peak if isinstance(peak, SpeedValue) else None
    return {
        "avg_rpm": a.rpm if a else None,
        "peak_rpm": p.rpm if p else None,
        "avg_mps": a.mps if a else None,
        "peak_mps": p.mps if p else None,
    }


def _motion_reasons(points: list[MotionPoint]) -> list[dict[str, Any]]:
    reasons: list[dict[str, Any]] = []
    for p in points:
        values = (
            ("left_avg", p.left_avg),
            ("left_peak", p.left_peak),
            ("right_avg", p.right_avg),
            ("right_peak", p.right_peak),
            ("imbalance", p.imbalance_pct),
        )
        for name, value in values:
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


def _first_absent(*points: Point | SpeedPoint | None) -> Absent | None:
    return next((p for p in points if isinstance(p, Absent)), None)


def _motion_missing_note(p: MotionPoint) -> str | None:
    """Одна примітка на виїзд: що саме відсутнє і чому (причини не змішуються)."""
    items = [
        ("швидкість лівого борту", _first_absent(p.left_avg, p.left_peak)),
        ("швидкість правого борту", _first_absent(p.right_avg, p.right_peak)),
        ("різниця бортів", _first_absent(p.imbalance_pct)),
    ]
    missing = [(name, a) for name, a in items if a is not None]
    if not missing:
        return None
    reasons = {a.reason for _, a in missing}
    if reasons == {charts.AbsentReason.NOT_MOVING} and len(missing) == len(items):
        reason = absent_reason_label(Absent(charts.AbsentReason.NOT_MOVING))
        text = f"швидкості й різниця бортів ({reason})"
    else:
        text = "; ".join(f"{name} ({absent_reason_label(Absent(a.reason))})" for name, a in missing)
    return f"Немає даних — виїзд № {p.seq}: {text}."


def _motion_notes(points: list[MotionPoint], axis: list[Slot]) -> list[str]:
    notes: list[str] = []
    for p in points:
        if p.no_encoder:
            sides = side_label(",".join(side.value for side in p.no_encoder))
            notes.append(f"Без енкодера — виїзд № {p.seq}: {sides}.")
        missing = _motion_missing_note(p)
        if missing:
            notes.append(missing)
    return [*notes, *_gap_line(axis)]


def build_motion_block(snapshot: Snapshot) -> BlockView:
    axis = build_axis(snapshot.sessions, snapshot.gaps)
    block = build_motion(axis)
    points = [p for p in block.points if not p.is_gap]

    def imbalance(p: MotionPoint) -> dict[str, Any] | None:
        if p.is_gap:
            return None
        faster = p.faster.value if isinstance(p.faster, charts.Side) else p.faster
        return {
            "pct": _number(p.imbalance_pct),
            "faster": faster,
            "faster_label": _FASTER_LABELS.get(faster) if faster else None,
        }

    def no_encoder(p: MotionPoint) -> str | None:
        if not p.no_encoder:
            return None
        return f"без енкодера: {side_label(','.join(side.value for side in p.no_encoder))}"

    data = {
        **block_data_shell("motion", axis),
        "left": [
            None if p.is_gap else _speed_numbers(p.left_avg, p.left_peak) for p in block.points
        ],
        "right": [
            None if p.is_gap else _speed_numbers(p.right_avg, p.right_peak) for p in block.points
        ],
        "imbalance": [imbalance(p) for p in block.points],
        "no_encoder": [no_encoder(p) for p in block.points],
        "reasons": _motion_reasons(points),
    }
    context = {
        "notes": _motion_notes(points, axis),
        "diagnostic_caption": _DIAGNOSTIC_CAPTION,
        "has_imbalance": any(isinstance(p.imbalance_pct, Value) for p in points),
        "mileage_caption": _MILEAGE_CAPTION,
        "any_no_encoder": block.any_no_encoder,
    }
    return BlockView("_charts_motion.html", context, data)


# Порядок реєстру — порядок на сторінці: Акумулятор → Перешкоди → Рух і борти.
BLOCKS: list[BlockSpec] = [
    BlockSpec("battery", "Акумулятор", _BATTERY_DESCRIPTION, build_battery_block),
    BlockSpec("obstacles", "Перешкоди", _OBSTACLES_DESCRIPTION, build_obstacles_block),
    BlockSpec("motion", "Рух і борти", _MOTION_DESCRIPTION, build_motion_block),
]


@lru_cache(maxsize=4096)
def _received(moment: datetime) -> str | None:
    """«Отримано» одного виїзду форматується раз на всі три блоки (1000 виїздів × 3 слоти)."""
    return format_received(moment)


def block_data_shell(key: str, axis: list[Slot]) -> dict[str, Any]:
    return {
        "block": key,
        "slots": [
            {
                "seq": slot.seq,
                "gap": slot.session is None,
                "received": _received(slot.session.received_at) if slot.session else None,
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


@lru_cache(maxsize=1)
def _environment() -> Environment:
    return make_environment()


def _render_view(view: BlockView) -> tuple[Markup, Markup]:
    """Вміст блока й JSON рендеряться тут, під межею ізоляції, а не під час рендеру сторінки.

    JSON готується за політикою `tojson` середовища (`json.dumps_kwargs`) — тією, що й для решти
    шаблонів: одна серіалізація, без розбіжностей між перевіркою і вставкою.
    """
    env = _environment()
    policies = env.policies
    data_json = htmlsafe_json_dumps(
        view.data, dumps=policies["json.dumps_function"], **policies["json.dumps_kwargs"]
    )
    return Markup(env.get_template(view.template).render(ctx=view.context)), data_json


def render_blocks(snapshot: Snapshot) -> list[RenderedBlock]:
    """Без виїздів усі блоки `empty` і не будуються (AC-17); збій блока — лише `error` (AC-19)."""
    blocks: list[RenderedBlock] = []
    for spec in BLOCKS:
        if not snapshot.sessions:
            blocks.append(RenderedBlock(spec.key, spec.title, spec.description, "empty", None))
            continue
        try:
            view = spec.build(snapshot)
            content, data_json = _render_view(view)
        except Exception as exc:  # межа ізоляції: причина лише в лог, на сторінку — повідомлення
            logger.error("chart_block_failed block=%s error_class=%s", spec.key, type(exc).__name__)
            blocks.append(RenderedBlock(spec.key, spec.title, spec.description, "error", None))
            continue
        blocks.append(
            RenderedBlock(spec.key, spec.title, spec.description, "ok", view, content, data_json)
        )
    return blocks
