"""Вісь графіків за номером сесії з порожніми місцями (AC-15, AC-16, AC-17, AC-23)."""

from collections.abc import Callable
from datetime import UTC, datetime

from rover_telemetry.domain import charts
from rover_telemetry.domain.charts import (
    Absent,
    AbsentReason,
    Slot,
    Value,
    build_axis,
)
from rover_telemetry.domain.dashboard import GapNumber, StoredSession

Factory = Callable[..., StoredSession]
MAC = "288485922c94"


def test_new_chart_fields_default_to_none(stored_session: Factory) -> None:
    """Нові поля `StoredSession` необов'язкові: наявні виклики не ламаються."""
    s = stored_session(seq=1)

    assert s.holds_min_mm is None
    assert s.speed_imbalance_pct is None
    assert s.encoders_left is None
    assert s.encoders_right is None
    assert s.tof_control_off_ms is None


def test_ac16_axis_is_ordered_by_seq_not_received_at(stored_session: Factory) -> None:
    late_low = stored_session(seq=26, received_at=datetime(2026, 10, 25, tzinfo=UTC))
    early_high = stored_session(seq=27, received_at=datetime(2026, 10, 20, tzinfo=UTC))

    axis = build_axis([early_high, late_low], [])

    assert [slot.seq for slot in axis] == [26, 27]
    assert [slot.session for slot in axis] == [late_low, early_high]


def test_ac15_gap_is_empty_slot_in_place(stored_session: Factory) -> None:
    sessions = [stored_session(seq=n) for n in (3, 6)]
    gaps = [GapNumber(MAC, 4), GapNumber(MAC, 5)]

    axis = build_axis(sessions, gaps)

    assert [slot.seq for slot in axis] == [3, 4, 5, 6]
    assert [slot.session is None for slot in axis] == [False, True, True, False]


def test_ac23_rejected_number_is_just_a_gap_and_duplicate_gap_is_one_slot(
    stored_session: Factory,
) -> None:
    """Відхилений номер у `gaps` не відрізняється від втраченого; один номер — один слот."""
    sessions = [stored_session(seq=1), stored_session(seq=3)]
    gaps = [GapNumber(MAC, 2), GapNumber(MAC, 2)]

    axis = build_axis(sessions, gaps)

    assert axis == [Slot(1, sessions[0]), Slot(2, None), Slot(3, sessions[1])]


def test_ac17_no_sessions_means_empty_axis_even_with_gaps() -> None:
    assert build_axis([], []) == []
    assert build_axis([], [GapNumber(MAC, 4)]) == []


def test_gap_number_equal_to_stored_seq_does_not_duplicate_slot(stored_session: Factory) -> None:
    s = stored_session(seq=5)

    axis = build_axis([s], [GapNumber(MAC, 5)])

    assert axis == [Slot(5, s)]


def test_value_zero_is_a_value_not_absent() -> None:
    """`null` ≠ 0: нуль — виміряне значення, відсутнє — окремий тип із причиною."""
    zero = Value(0.0)
    absent = Absent(AbsentReason.NOT_REPORTED)

    assert zero.number == 0.0
    assert not isinstance(zero, Absent)
    assert absent.reason is AbsentReason.NOT_REPORTED
    assert absent.subject is None
    assert Absent(AbsentReason.NO_ENCODER, "left").subject == "left"


def test_absent_reasons_are_the_five_from_adr_0003() -> None:
    assert {r.name for r in AbsentReason} == {
        "NOT_MOVING",
        "NO_ENCODER",
        "NO_STRAIGHT",
        "NO_HOLDS",
        "NOT_REPORTED",
    }


def test_named_constants_have_sourced_values() -> None:
    assert charts.CUTOFF_V == 6.0
    assert charts.FULL_CHARGE_V == 8.4
    assert charts.OBSTACLE_THRESHOLD_MM == 190
    assert charts.BATTERY_CELLS == 2
    assert charts.WHEEL_CIRCUMFERENCE_M == 0.1382
    assert charts.SECONDS_PER_MINUTE == 60
