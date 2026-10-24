"""Підсумки дашборду з рядків одного знімка читання, без I/O (feature ADR-0001).

Єдине місце правила «`NULL` ≠ 0» (конституція №4): сума лише за відомими значеннями плюс
кількість виїздів без даних; якщо відомих немає — `None`, а не нуль.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


@dataclass(frozen=True)
class StoredSession:
    """Збережений виїзд: колонки `sessions` без `raw`; `None` = `NULL` = «немає даних»."""

    mac: str
    seq: int
    received_at: datetime
    duration_ms: int | None = None
    end_reason: str | None = None
    voltage_start_mv: int | None = None
    voltage_end_mv: int | None = None
    voltage_min_mv: int | None = None
    holds_count: int | None = None
    moving_ms: int | None = None
    distance_cm: int | None = None
    fw_version: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GapNumber:
    """Номер сесії без виїзду (рядок `session_gaps`); втрачений і відхилений не відрізняються."""

    mac: str
    seq: int


@dataclass(frozen=True)
class Total:
    """Підсумок: `sum` лише за виїздами з даними, `missing` — без даних, `total` — усіх."""

    sum: int | None
    missing: int
    total: int


class EndReason(Enum):
    DISARM = "disarm"
    LINK_LOST = "failsafe_link_lost"
    VOLTAGE = "failsafe_voltage"
    OTHER = "other"


_KNOWN_REASONS = {r.value: r for r in EndReason if r is not EndReason.OTHER}


def classify_end_reason(raw: str | None) -> EndReason | None:
    """`None` лишається `None` («немає даних»); невідоме значення — `OTHER`."""
    if raw is None:
        return None
    return _KNOWN_REASONS.get(raw, EndReason.OTHER)


@dataclass(frozen=True)
class Summary:
    """Вісім підсумків екрана; `None` там, де значення немає."""

    sessions: int
    distance: Total
    moving: Total
    holds: Total
    last_voltage_end_mv: int | None
    last_seq: int | None
    last_received_at: datetime | None
    last_fw_version: str | None
    lost: int | None


def _total(sessions: list[StoredSession], value: Callable[[StoredSession], int | None]) -> Total:
    known = [v for v in map(value, sessions) if v is not None]
    return Total(
        sum=sum(known) if known else None,
        missing=len(sessions) - len(known),
        total=len(sessions),
    )


def build_summary(sessions: Iterable[StoredSession], gaps: Iterable[GapNumber]) -> Summary:
    rows = list(sessions)
    # «Останній» виїзд — найбільший номер, за рівності — за `mac` (детермінований порядок).
    last = min(rows, key=lambda s: (-s.seq, s.mac), default=None)
    return Summary(
        sessions=len(rows),
        distance=_total(rows, lambda s: s.distance_cm),
        moving=_total(rows, lambda s: s.moving_ms),
        holds=_total(rows, lambda s: s.holds_count),
        last_voltage_end_mv=last.voltage_end_mv if last else None,
        last_seq=last.seq if last else None,
        last_received_at=max((s.received_at for s in rows), default=None),
        last_fw_version=last.fw_version if last else None,
        lost=len(list(gaps)) if rows else None,
    )
