"""Ряди блоку «Перешкоди» (AC-05…AC-09): відстань, «утримань не було», лічильники датчиків."""

from collections.abc import Callable

import pytest

from rover_telemetry.domain.charts import (
    Absent,
    AbsentReason,
    ObstaclePoint,
    Value,
    build_axis,
    build_obstacles,
)
from rover_telemetry.domain.dashboard import GapNumber, StoredSession, Total

Factory = Callable[..., StoredSession]


def _point(stored_session: Factory, **fields: object) -> ObstaclePoint:
    block = build_obstacles(build_axis([stored_session(seq=1, **fields)], []))
    return block.points[0]


def test_ac07_min_distance_and_sensor(stored_session: Factory) -> None:
    p = _point(stored_session, holds_count=1, holds_min_mm=103, holds_min_sensor="front")

    assert p.min_mm == Value(103)
    assert p.sensor == "front"


def test_ac07_unknown_sensor_is_passed_raw(stored_session: Factory) -> None:
    p = _point(stored_session, holds_count=1, holds_min_mm=90, holds_min_sensor="top")

    assert p.sensor == "top"


def test_ac08_no_holds_is_its_own_absence(stored_session: Factory) -> None:
    p = _point(stored_session, holds_count=0)

    assert p.min_mm == Absent(AbsentReason.NO_HOLDS)


def test_ac08_holds_but_no_distance_is_not_reported(stored_session: Factory) -> None:
    p = _point(stored_session, holds_count=2)

    assert p.min_mm == Absent(AbsentReason.NOT_REPORTED, "відстань до перешкоди")


def test_unknown_holds_count_without_distance_is_not_reported(stored_session: Factory) -> None:
    p = _point(stored_session)

    assert p.min_mm == Absent(AbsentReason.NOT_REPORTED, "відстань до перешкоди")


def test_ac09_control_off_seconds_zero_is_a_value(stored_session: Factory) -> None:
    assert _point(stored_session, tof_control_off_ms=0).control_off_s == Value(0.0)
    assert _point(stored_session, tof_control_off_ms=6660).control_off_s == Value(6.66)


def test_ac09_control_off_null_is_absent(stored_session: Factory) -> None:
    p = _point(stored_session)

    assert p.control_off_s == Absent(AbsentReason.NOT_REPORTED, "секунди вимкненого захисту")


def test_ac09_no_holds_keeps_control_off_seconds(stored_session: Factory) -> None:
    p = _point(stored_session, holds_count=0, tof_control_off_ms=6660)

    assert p.min_mm == Absent(AbsentReason.NO_HOLDS)
    assert p.control_off_s == Value(6.66)


def test_ac09_protection_off_any(stored_session: Factory) -> None:
    on = [stored_session(seq=1, tof_control_off_ms=0), stored_session(seq=2)]
    off = [*on, stored_session(seq=3, tof_control_off_ms=1)]

    assert build_obstacles(build_axis(on, [])).protection_off_any is False
    assert build_obstacles(build_axis(off, [])).protection_off_any is True


def test_ac05_sensor_counters_sum_known_only(stored_session: Factory) -> None:
    sessions = [
        stored_session(seq=1, holds_left_front=0, holds_front=2, holds_right_front=1),
        stored_session(seq=2, holds_left_front=3, holds_front=1),
        stored_session(seq=3),
    ]

    c = build_obstacles(build_axis(sessions, [])).counters

    assert c.left_front == Total(sum=3, missing=1, total=3)  # нуль — виміряне значення
    assert c.front == Total(sum=3, missing=1, total=3)
    assert c.right_front == Total(sum=1, missing=2, total=3)
    assert c.rear == Total(sum=None, missing=3, total=3)  # ніхто не передав: не 0


def test_ac06_counters_have_no_sum_of_sensors() -> None:
    """Суму чотирьох лічильників як «кількість утримань» не подаємо."""
    from rover_telemetry.domain.charts import SensorCounters

    assert not hasattr(SensorCounters, "total")
    assert not hasattr(SensorCounters, "sum")


def test_gap_slot_is_gap_point(stored_session: Factory) -> None:
    sessions = [stored_session(seq=1), stored_session(seq=3)]

    block = build_obstacles(build_axis(sessions, [GapNumber("288485922c94", 2)]))

    assert [(p.seq, p.is_gap) for p in block.points] == [(1, False), (2, True), (3, False)]
    gap = block.points[1]
    assert gap.min_mm is None and gap.control_off_s is None and gap.sensor is None


def test_empty_axis() -> None:
    block = build_obstacles([])

    assert block.points == [] and block.protection_off_any is False
    assert block.counters.front == Total(sum=None, missing=0, total=0)


@pytest.mark.parametrize("n", [26, 27])
def test_fixtures(n: int, stored_session: Factory) -> None:
    import json
    from pathlib import Path

    r = json.loads((Path(__file__).parents[1] / "fixtures" / f"session_seq{n}.json").read_text())
    holds = r.get("holds") or {}
    s = stored_session(
        seq=n,
        holds_count=holds.get("count"),
        holds_min_mm=holds.get("min_mm"),
        holds_min_sensor=holds.get("min_sensor"),
        tof_control_off_ms=r.get("tof_control_off_ms"),
    )

    p = build_obstacles(build_axis([s], [])).points[0]

    assert p.seq == n
