"""Хронологія виїздів: виїзди й позначки номерів без виїзду в одному списку, без I/O."""

from collections.abc import Iterable
from dataclasses import dataclass

from rover_telemetry.domain.dashboard import GapNumber, StoredSession


@dataclass(frozen=True)
class SessionItem:
    session: StoredSession


@dataclass(frozen=True)
class GapItem:
    """Позначка «виїзду з цим номером немає»; однакова для втраченого й відхиленого номера."""

    mac: str
    seq: int


def build_timeline(
    sessions: Iterable[StoredSession], gaps: Iterable[GapNumber]
) -> list[SessionItem | GapItem]:
    """Порядок лише за `(seq ↓, mac ↑)`; «отримано» участі в ньому не бере (AC-03, AC-09)."""
    rows = list(sessions)
    if not rows:
        return []  # пропуски рахуються від найменшого збереженого номера; без виїздів їх немає
    items: list[SessionItem | GapItem] = [SessionItem(s) for s in rows]
    items.extend(GapItem(g.mac, g.seq) for g in gaps)
    return sorted(items, key=_key)


def _key(item: SessionItem | GapItem) -> tuple[int, str]:
    if isinstance(item, SessionItem):
        return (-item.session.seq, item.session.mac)
    return (-item.seq, item.mac)
