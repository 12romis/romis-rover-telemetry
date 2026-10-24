"""Хронологія виїздів із позначками номерів без виїзду (AC-03, AC-08, AC-09, AC-16)."""

from collections.abc import Callable
from datetime import UTC, datetime

from rover_telemetry.domain.dashboard import GapNumber, StoredSession
from rover_telemetry.domain.timeline import GapItem, SessionItem, build_timeline

Factory = Callable[..., StoredSession]
MAC = "288485922c94"


def test_ac03_order_is_seq_desc_regardless_of_received_at(stored_session: Factory) -> None:
    """AC-03, AC-09: порядок за номером; пізніше «отримано» його не змінює."""
    old_seq_late = stored_session(seq=26, received_at=datetime(2026, 10, 25, tzinfo=UTC))
    new_seq_early = stored_session(seq=27, received_at=datetime(2026, 10, 20, tzinfo=UTC))

    items = build_timeline([old_seq_late, new_seq_early], [])

    assert items == [SessionItem(new_seq_early), SessionItem(old_seq_late)]


def test_ac08_gap_marker_in_place(stored_session: Factory) -> None:
    """AC-08: позначка стоїть між виїздами на місці свого номера, по одній на номер."""
    sessions = [stored_session(seq=n) for n in (3, 6)]
    gaps = [GapNumber(MAC, 4), GapNumber(MAC, 5)]

    items = build_timeline(sessions, gaps)

    assert [type(i).__name__ for i in items] == ["SessionItem", "GapItem", "GapItem", "SessionItem"]
    assert [i.seq if isinstance(i, GapItem) else i.session.seq for i in items] == [6, 5, 4, 3]


def test_no_gaps_only_sessions(stored_session: Factory) -> None:
    items = build_timeline([stored_session(seq=1), stored_session(seq=2)], [])

    assert all(isinstance(i, SessionItem) for i in items)


def test_ac16_rejected_number_is_ordinary_gap(stored_session: Factory) -> None:
    """AC-16: функція не приймає відхилених; номер без виїзду — звичайний `GapItem`."""
    items = build_timeline([stored_session(seq=1), stored_session(seq=3)], [GapNumber(MAC, 2)])

    assert items[1] == GapItem(mac=MAC, seq=2)


def test_empty_sessions_gives_empty_list() -> None:
    """Пропуски без жодного виїзду не вигадуються."""
    assert build_timeline([], [GapNumber(MAC, 2)]) == []


def test_same_seq_different_mac_ordered_by_mac(stored_session: Factory) -> None:
    items = build_timeline(
        [stored_session(mac="bb", seq=5), stored_session(mac="aa", seq=5)],
        [],
    )

    assert [i.session.mac for i in items if isinstance(i, SessionItem)] == ["aa", "bb"]
