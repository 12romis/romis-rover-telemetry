"""Основа графіків без I/O: константи з джерелами, значення/відсутність і вісь за номером сесії.

Правило «`NULL` ≠ 0» (конституція №4) закріплене типами: точка — `Value(число)` або
`Absent(причина)` (ADR-0003), нуль — виміряне значення, а не відсутнє.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

from rover_telemetry.domain.dashboard import GapNumber, StoredSession

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
