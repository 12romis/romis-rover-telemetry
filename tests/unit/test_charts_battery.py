"""Ряди блоку «Акумулятор» (AC-01…AC-04): `NULL` ≠ 0, просадка, причина завершення."""

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from rover_telemetry.domain.charts import (
    Absent,
    AbsentReason,
    BatteryPoint,
    Value,
    build_axis,
    build_battery,
)
from rover_telemetry.domain.dashboard import EndReason, GapNumber, StoredSession

Factory = Callable[..., StoredSession]
FIXTURES = Path(__file__).parents[1] / "fixtures"


def _battery(stored_session: Factory, **fields: object) -> BatteryPoint:
    session = stored_session(seq=1, **fields)
    block = build_battery(build_axis([session], []))
    return block.points[0]


def test_ac01_all_three_voltages_in_volts_and_per_cell(stored_session: Factory) -> None:
    p = _battery(stored_session, voltage_start_mv=7691, voltage_min_mv=7628, voltage_end_mv=7675)

    assert (p.start, p.min, p.end) == (Value(7.691), Value(7.628), Value(7.675))
    assert p.per_cell_start == Value(7.691 / 2)
    assert p.per_cell_min == Value(7.628 / 2)
    assert p.per_cell_end == Value(7.675 / 2)


def test_ac02_drop_is_start_minus_min(stored_session: Factory) -> None:
    p = _battery(stored_session, voltage_start_mv=7691, voltage_min_mv=7628)

    assert isinstance(p.drop, Value)
    assert p.drop.number == pytest.approx(0.063)


def test_ac02_zero_drop_is_a_measured_value(stored_session: Factory) -> None:
    p = _battery(stored_session, voltage_start_mv=7600, voltage_min_mv=7600)

    assert p.drop == Value(0.0)


def test_ac03_missing_min_has_no_drop_and_keeps_other_voltages(stored_session: Factory) -> None:
    p = _battery(stored_session, voltage_start_mv=7691, voltage_end_mv=7675)

    assert p.min == Absent(AbsentReason.NOT_REPORTED, "мінімальна напруга")
    assert p.per_cell_min == Absent(AbsentReason.NOT_REPORTED, "мінімальна напруга")
    assert p.drop == Absent(AbsentReason.NOT_REPORTED, "просадка")
    assert p.start == Value(7.691) and p.end == Value(7.675)


def test_ac03_missing_start_has_no_drop(stored_session: Factory) -> None:
    p = _battery(stored_session, voltage_min_mv=7600)

    assert p.start == Absent(AbsentReason.NOT_REPORTED, "початкова напруга")
    assert p.drop == Absent(AbsentReason.NOT_REPORTED, "просадка")


def test_ac03_all_three_missing_never_become_numbers(stored_session: Factory) -> None:
    p = _battery(stored_session)

    assert p.start == Absent(AbsentReason.NOT_REPORTED, "початкова напруга")
    assert p.min == Absent(AbsentReason.NOT_REPORTED, "мінімальна напруга")
    assert p.end == Absent(AbsentReason.NOT_REPORTED, "напруга наприкінці")
    for absent in (p.per_cell_start, p.per_cell_min, p.per_cell_end, p.drop):
        assert isinstance(absent, Absent)


def test_ac04_voltage_failsafe_is_marked_others_are_not(stored_session: Factory) -> None:
    low = _battery(stored_session, end_reason="failsafe_voltage")
    ok = _battery(stored_session, end_reason="disarm")
    unknown = _battery(stored_session, end_reason="strange")
    none = _battery(stored_session)

    assert low.end_reason is EndReason.VOLTAGE
    assert ok.end_reason is EndReason.DISARM
    assert unknown.end_reason is EndReason.OTHER
    assert none.end_reason is None


def test_gap_slots_become_gap_points_and_keep_order(stored_session: Factory) -> None:
    sessions = [stored_session(seq=3, voltage_start_mv=7000), stored_session(seq=6)]

    block = build_battery(build_axis(sessions, [GapNumber("288485922c94", 4)]))

    assert [(p.seq, p.is_gap) for p in block.points] == [(3, False), (4, True), (6, False)]
    gap = block.points[1]
    assert gap.start == gap.min == gap.end == gap.drop is None


def test_largest_drop_seq_picks_biggest_and_lowest_seq_on_tie(stored_session: Factory) -> None:
    sessions = [
        stored_session(seq=1, voltage_start_mv=8000, voltage_min_mv=7900),
        stored_session(seq=2, voltage_start_mv=8000, voltage_min_mv=7500),
        stored_session(seq=3, voltage_start_mv=8000, voltage_min_mv=7500),
        stored_session(seq=4, voltage_start_mv=8000),
    ]

    assert build_battery(build_axis(sessions, [])).largest_drop_seq == 2


def test_largest_drop_seq_none_when_no_drop_known(stored_session: Factory) -> None:
    assert build_battery(build_axis([stored_session(seq=1)], [])).largest_drop_seq is None
    assert build_battery([]).largest_drop_seq is None


def test_empty_axis_gives_no_points() -> None:
    assert build_battery(build_axis([], [])).points == []


def test_fixtures_seq26_seq27(stored_session: Factory) -> None:
    rows = []
    for n in (26, 27):
        r = json.loads((FIXTURES / f"session_seq{n}.json").read_text())
        rows.append(
            stored_session(
                seq=n,
                voltage_start_mv=r.get("voltage_start_mv"),
                voltage_min_mv=r.get("voltage_min_mv"),
                voltage_end_mv=r.get("voltage_end_mv"),
                end_reason=r.get("end_reason"),
            )
        )

    block = build_battery(build_axis(rows, []))

    assert [p.seq for p in block.points] == [26, 27]
    p27 = block.points[1]
    assert p27.start == Value(7.691) and isinstance(p27.drop, Value)
