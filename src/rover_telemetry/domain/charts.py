"""Основа графіків без I/O: константи з джерелами, значення/відсутність і вісь за номером сесії.

Правило «`NULL` ≠ 0» (конституція №4) закріплене типами: точка — `Value(число)` або
`Absent(причина)` (ADR-0003), нуль — виміряне значення, а не відсутнє.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from typing import Literal

from rover_telemetry.domain.dashboard import (
    EndReason,
    GapNumber,
    StoredSession,
    Total,
    classify_end_reason,
)

# Константи ровера; кожна має джерело (конституція №3), нових чисел без джерела тут немає.
CUTOFF_V = 6.0  # відсічка живлення, контракт подій
FULL_CHARGE_V = 8.4  # повний заряд двох банок, рішення власника №9
OBSTACLE_THRESHOLD_MM = 190  # поріг перешкоди, контракт подій і конституція №3
BATTERY_CELLS = 2  # кількість банок, рішення власника №8
WHEEL_CIRCUMFERENCE_M = 0.1382  # довжина обводу колеса (діаметр 44 мм), контракт подій
SECONDS_PER_MINUTE = 60  # об/хв → об/с для швидкості в м/с


class AbsentReason(Enum):
    """Чому значення на графіку відсутнє (ADR-0003); порядок пріоритету задає окремий ряд."""

    NOT_MOVING = "not_moving"
    NO_ENCODER = "no_encoder"
    NO_STRAIGHT = "no_straight"
    NO_HOLDS = "no_holds"
    NOT_REPORTED = "not_reported"


@dataclass(frozen=True)
class Value:
    """Виміряне значення; нуль — теж значення."""

    number: float


@dataclass(frozen=True)
class Absent:
    """Відсутнє значення з причиною; `subject` — про що мова (назва значення чи борт)."""

    reason: AbsentReason
    subject: str | None = None


Point = Value | Absent


@dataclass(frozen=True)
class Slot:
    """Місце на осі: номер сесії і виїзд, або `None` для номера без виїзду."""

    seq: int
    session: StoredSession | None


def build_axis(sessions: Iterable[StoredSession], gaps: Iterable[GapNumber]) -> list[Slot]:
    """Вісь за номером сесії (не за «отримано»); номери без виїзду — порожні місця (AC-15, AC-16).

    Без збережених виїздів осі немає: блоки покажуть «немає даних» (AC-17). Втрачений і
    відхилений номер однакові, а один номер дає один слот (AC-23).
    """
    by_seq: dict[int, StoredSession] = {}
    for s in sessions:
        by_seq.setdefault(s.seq, s)
    if not by_seq:
        return []
    numbers = set(by_seq) | {g.seq for g in gaps}
    return [Slot(seq, by_seq.get(seq)) for seq in sorted(numbers)]


# --- Блок «Акумулятор» (AC-01…AC-04) ---------------------------------------------------------

_MV_PER_V = 1000  # мВ → В: контракт передає напругу в мілівольтах


@dataclass(frozen=True)
class BatteryPoint:
    """Напруги виїзду у вольтах; порожнє місце осі — `is_gap` і `None` у всіх значеннях."""

    seq: int
    is_gap: bool
    start: Point | None
    min: Point | None
    end: Point | None
    per_cell_start: Point | None
    per_cell_min: Point | None
    per_cell_end: Point | None
    drop: Point | None
    end_reason: EndReason | None


@dataclass(frozen=True)
class BatteryBlock:
    points: list[BatteryPoint]
    largest_drop_seq: int | None


def _volts(mv: int | None, subject: str, cells: int = 1) -> Point:
    if mv is None:
        return Absent(AbsentReason.NOT_REPORTED, subject)
    return Value(mv / _MV_PER_V / cells)


def _battery_point(slot: Slot) -> BatteryPoint:
    s = slot.session
    if s is None:
        return BatteryPoint(slot.seq, True, None, None, None, None, None, None, None, None)
    names = ("початкова напруга", "мінімальна напруга", "напруга наприкінці")
    start, low, end = s.voltage_start_mv, s.voltage_min_mv, s.voltage_end_mv
    if start is None or low is None:
        drop: Point = Absent(AbsentReason.NOT_REPORTED, "просадка")
    else:
        drop = Value((start - low) / _MV_PER_V)
    return BatteryPoint(
        seq=slot.seq,
        is_gap=False,
        start=_volts(start, names[0]),
        min=_volts(low, names[1]),
        end=_volts(end, names[2]),
        per_cell_start=_volts(start, names[0], BATTERY_CELLS),
        per_cell_min=_volts(low, names[1], BATTERY_CELLS),
        per_cell_end=_volts(end, names[2], BATTERY_CELLS),
        drop=drop,
        end_reason=classify_end_reason(s.end_reason),
    )


def build_battery(axis: list[Slot]) -> BatteryBlock:
    """Ряди блоку; найбільша просадка — найменший `seq` при рівності (рішення задачі T3)."""
    points = [_battery_point(slot) for slot in axis]
    drops = [(p.drop.number, p.seq) for p in points if isinstance(p.drop, Value)]
    largest = min(drops, key=lambda d: (-d[0], d[1]))[1] if drops else None
    return BatteryBlock(points=points, largest_drop_seq=largest)


# --- Блок «Перешкоди» (AC-05…AC-09) ----------------------------------------------------------

_MS_PER_S = 1000  # мс → с: контракт передає `tof_control_off_ms` у мілісекундах


@dataclass(frozen=True)
class ObstaclePoint:
    """Найменша відстань і секунди вимкненого захисту; `sensor` — сире значення контракту."""

    seq: int
    is_gap: bool
    min_mm: Point | None
    sensor: str | None
    control_off_s: Point | None


@dataclass(frozen=True)
class SensorCounters:
    """Спрацювання датчиків за всіма виїздами; це не кількість утримань (AC-06), суми немає."""

    left_front: Total
    front: Total
    right_front: Total
    rear: Total


@dataclass(frozen=True)
class ObstacleBlock:
    points: list[ObstaclePoint]
    counters: SensorCounters
    protection_off_any: bool


def _obstacle_point(slot: Slot) -> ObstaclePoint:
    s = slot.session
    if s is None:
        return ObstaclePoint(slot.seq, True, None, None, None)
    min_mm: Point
    if s.holds_min_mm is not None:
        min_mm = Value(s.holds_min_mm)
    elif s.holds_count == 0:
        min_mm = Absent(AbsentReason.NO_HOLDS)  # виміряно, що утримань не було
    else:
        min_mm = Absent(AbsentReason.NOT_REPORTED, "відстань до перешкоди")
    off: Point
    if s.tof_control_off_ms is None:
        off = Absent(AbsentReason.NOT_REPORTED, "секунди вимкненого захисту")
    else:
        off = Value(s.tof_control_off_ms / _MS_PER_S)
    return ObstaclePoint(slot.seq, False, min_mm, s.holds_min_sensor, off)


def _counter(sessions: list[StoredSession], name: str) -> Total:
    """Сума лише за виїздами, що передали лічильник; жоден не передав — `None`, не нуль."""
    known = [v for s in sessions if (v := getattr(s, name)) is not None]
    return Total(
        sum=sum(known) if known else None,
        missing=len(sessions) - len(known),
        total=len(sessions),
    )


def build_obstacles(axis: list[Slot]) -> ObstacleBlock:
    sessions = [slot.session for slot in axis if slot.session is not None]
    return ObstacleBlock(
        points=[_obstacle_point(slot) for slot in axis],
        counters=SensorCounters(
            left_front=_counter(sessions, "holds_left_front"),
            front=_counter(sessions, "holds_front"),
            right_front=_counter(sessions, "holds_right_front"),
            rear=_counter(sessions, "holds_rear"),
        ),
        protection_off_any=any((s.tof_control_off_ms or 0) > 0 for s in sessions),
    )


# --- Блок «Рух і борти» (AC-10…AC-13) --------------------------------------------------------


class Side(Enum):
    LEFT = "left"
    RIGHT = "right"


@dataclass(frozen=True)
class SpeedValue:
    """Швидкість борту: об/хв колеса з контракту і м/с за його формулою."""

    rpm: float
    mps: float


SpeedPoint = SpeedValue | Absent


@dataclass(frozen=True)
class MotionPoint:
    """Швидкості бортів і різниця; `faster` — за знаком різниці (плюс — лівий швидший)."""

    seq: int
    is_gap: bool
    left_avg: SpeedPoint | None
    left_peak: SpeedPoint | None
    right_avg: SpeedPoint | None
    right_peak: SpeedPoint | None
    imbalance_pct: Point | None
    faster: Side | Literal["equal"] | None
    no_encoder: tuple[Side, ...]


@dataclass(frozen=True)
class MotionBlock:
    points: list[MotionPoint]
    any_no_encoder: bool


def _speed(rpm: float | None, side: Side, s: StoredSession) -> SpeedPoint:
    """Значення, що є, лишається числом; причина відсутності — за пріоритетом ADR-0003."""
    if rpm is not None:
        return SpeedValue(rpm, rpm * WHEEL_CIRCUMFERENCE_M / SECONDS_PER_MINUTE)
    if s.moving_ms == 0:
        return Absent(AbsentReason.NOT_MOVING)
    if (s.encoders_left if side is Side.LEFT else s.encoders_right) is False:
        return Absent(AbsentReason.NO_ENCODER, side.value)
    return Absent(AbsentReason.NOT_REPORTED, "швидкість")


def _no_encoder(s: StoredSession) -> tuple[Side, ...]:
    """Позначка «без енкодера» не залежить від пріоритету причин (AC-13); `None` не позначається."""
    sides = ((Side.LEFT, s.encoders_left), (Side.RIGHT, s.encoders_right))
    return tuple(side for side, present in sides if present is False)


def _imbalance(s: StoredSession, missing: tuple[Side, ...]) -> Point:
    if s.speed_imbalance_pct is not None:
        return Value(s.speed_imbalance_pct)
    if s.moving_ms == 0:
        return Absent(AbsentReason.NOT_MOVING)
    if missing:
        return Absent(AbsentReason.NO_ENCODER, ",".join(side.value for side in missing))
    # «Прямої ділянки не було» — лише за відомих руху й енкодерів (ADR-0003).
    if s.moving_ms is not None and s.encoders_left is True and s.encoders_right is True:
        return Absent(AbsentReason.NO_STRAIGHT)
    return Absent(AbsentReason.NOT_REPORTED, "різниця бортів")


def _faster(imbalance: Point) -> Side | Literal["equal"] | None:
    if not isinstance(imbalance, Value):
        return None
    if imbalance.number == 0:
        return "equal"
    return Side.LEFT if imbalance.number > 0 else Side.RIGHT


def _motion_point(slot: Slot) -> MotionPoint:
    s = slot.session
    if s is None:
        return MotionPoint(slot.seq, True, None, None, None, None, None, None, ())
    missing = _no_encoder(s)
    imbalance = _imbalance(s, missing)
    return MotionPoint(
        seq=slot.seq,
        is_gap=False,
        left_avg=_speed(s.speed_left_avg_rpm, Side.LEFT, s),
        left_peak=_speed(s.speed_left_peak_rpm, Side.LEFT, s),
        right_avg=_speed(s.speed_right_avg_rpm, Side.RIGHT, s),
        right_peak=_speed(s.speed_right_peak_rpm, Side.RIGHT, s),
        imbalance_pct=imbalance,
        faster=_faster(imbalance),
        no_encoder=missing,
    )


def build_motion(axis: list[Slot]) -> MotionBlock:
    points = [_motion_point(slot) for slot in axis]
    return MotionBlock(points=points, any_no_encoder=any(p.no_encoder for p in points))
