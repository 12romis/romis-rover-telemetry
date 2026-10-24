"""Ряди блоку «Рух і борти» (AC-10…AC-13): м/с, різниця бортів, причини відсутності."""

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from rover_telemetry.domain.charts import (
    Absent,
    AbsentReason,
    Side,
    SpeedValue,
    Value,
    build_axis,
    build_motion,
)
from rover_telemetry.domain.dashboard import GapNumber, StoredSession

Factory = Callable[..., StoredSession]
FIXTURES = Path(__file__).parents[1] / "fixtures"

FULL = {
    "moving_ms": 2360,
    "speed_left_avg_rpm": 30.6,
    "speed_left_peak_rpm": 100.1,
    "speed_right_avg_rpm": 30.3,
    "speed_right_peak_rpm": 105.0,
    "speed_imbalance_pct": 1.1,
    "encoders_left": True,
    "encoders_right": True,
}


def _point(stored_session: Factory, **fields: object):  # type: ignore[no-untyped-def]
    block = build_motion(build_axis([stored_session(seq=1, **fields)], []))
    return block.points[0]


def _mps(rpm: float) -> float:
    return rpm * 0.1382 / 60


def test_ac10_speeds_in_rpm_and_mps_by_contract_formula(stored_session: Factory) -> None:
    p = _point(stored_session, **FULL)

    assert p.left_avg == SpeedValue(30.6, pytest.approx(_mps(30.6)))
    assert p.left_peak == SpeedValue(100.1, pytest.approx(_mps(100.1)))
    assert p.right_avg == SpeedValue(30.3, pytest.approx(_mps(30.3)))
    assert p.right_peak == SpeedValue(105.0, pytest.approx(_mps(105.0)))
    assert p.no_encoder == ()


def test_ac10_zero_speed_is_a_measured_value(stored_session: Factory) -> None:
    p = _point(stored_session, **{**FULL, "speed_left_avg_rpm": 0.0})

    assert p.left_avg == SpeedValue(0.0, 0.0)


def test_ac11_imbalance_with_direction_by_sign(stored_session: Factory) -> None:
    left = _point(stored_session, **{**FULL, "speed_imbalance_pct": 1.1})
    right = _point(stored_session, **{**FULL, "speed_imbalance_pct": -2.5})

    assert left.imbalance_pct == Value(1.1) and left.faster is Side.LEFT
    assert right.imbalance_pct == Value(-2.5) and right.faster is Side.RIGHT


def test_ac11_zero_imbalance_is_equal_not_missing(stored_session: Factory) -> None:
    p = _point(stored_session, **{**FULL, "speed_imbalance_pct": 0.0})

    assert p.imbalance_pct == Value(0.0)
    assert p.faster == "equal"


def test_ac12_not_moving_beats_other_reasons(stored_session: Factory) -> None:
    p = _point(stored_session, moving_ms=0, encoders_left=False, encoders_right=True)

    for absent in (p.left_avg, p.left_peak, p.right_avg, p.right_peak, p.imbalance_pct):
        assert absent == Absent(AbsentReason.NOT_MOVING)
    assert p.faster is None


def test_ac12_no_encoder_names_the_side_and_keeps_other_side(stored_session: Factory) -> None:
    p = _point(
        stored_session,
        moving_ms=2360,
        encoders_left=False,
        encoders_right=True,
        speed_right_avg_rpm=30.3,
        speed_right_peak_rpm=105.0,
    )

    assert p.left_avg == Absent(AbsentReason.NO_ENCODER, "left")
    assert p.left_peak == Absent(AbsentReason.NO_ENCODER, "left")
    assert isinstance(p.right_avg, SpeedValue) and isinstance(p.right_peak, SpeedValue)
    assert p.imbalance_pct == Absent(AbsentReason.NO_ENCODER, "left")


def test_ac12_both_encoders_missing(stored_session: Factory) -> None:
    p = _point(stored_session, moving_ms=2360, encoders_left=False, encoders_right=False)

    assert p.left_avg == Absent(AbsentReason.NO_ENCODER, "left")
    assert p.right_avg == Absent(AbsentReason.NO_ENCODER, "right")
    assert p.imbalance_pct == Absent(AbsentReason.NO_ENCODER, "left,right")


def test_ac12_no_straight_section_does_not_mix_with_other_reasons(stored_session: Factory) -> None:
    p = _point(stored_session, **{**FULL, "speed_imbalance_pct": None})

    assert p.imbalance_pct == Absent(AbsentReason.NO_STRAIGHT)
    assert isinstance(p.left_avg, SpeedValue)  # швидкості лишаються числами
    assert p.faster is None


def test_ac12_unknown_moving_or_encoders_is_not_reported_not_no_straight(
    stored_session: Factory,
) -> None:
    """Review F8, ADR-0003: «прямої ділянки не було» лише за відомих руху й енкодерів."""
    base = {**FULL, "speed_imbalance_pct": None}
    for unknown in ({"moving_ms": None}, {"encoders_left": None}, {"encoders_right": None}):
        p = _point(stored_session, **{**base, **unknown})
        assert isinstance(p.imbalance_pct, Absent)
        assert p.imbalance_pct.reason is AbsentReason.NOT_REPORTED, unknown


def test_ac12_unreported_speed_with_encoder_and_motion(stored_session: Factory) -> None:
    p = _point(stored_session, **{**FULL, "speed_left_peak_rpm": None})

    assert p.left_peak == Absent(AbsentReason.NOT_REPORTED, "швидкість")


def test_ac13_no_encoder_marker_independent_of_priority(stored_session: Factory) -> None:
    """Навіть коли причина відсутності — «не їхав», позначка «без енкодера» лишається."""
    p = _point(stored_session, moving_ms=0, encoders_left=False, encoders_right=True)

    assert p.no_encoder == (Side.LEFT,)


def test_ac13_none_encoder_is_not_marked(stored_session: Factory) -> None:
    assert _point(stored_session).no_encoder == ()


def test_ac13_both_sides_marked_and_block_flag(stored_session: Factory) -> None:
    sessions = [
        stored_session(seq=1, **FULL),
        stored_session(seq=2, encoders_left=False, encoders_right=False),
    ]

    block = build_motion(build_axis(sessions, []))

    assert block.points[1].no_encoder == (Side.LEFT, Side.RIGHT)
    assert block.any_no_encoder is True
    assert build_motion(build_axis(sessions[:1], [])).any_no_encoder is False


def test_no_data_at_all_is_not_reported_not_zero(stored_session: Factory) -> None:
    p = _point(stored_session)

    assert isinstance(p.left_avg, Absent) and p.left_avg.reason is AbsentReason.NOT_REPORTED
    assert isinstance(p.imbalance_pct, Absent)
    assert p.imbalance_pct.reason is AbsentReason.NOT_REPORTED


def test_gap_slot(stored_session: Factory) -> None:
    block = build_motion(
        build_axis([stored_session(seq=1), stored_session(seq=3)], [GapNumber("288485922c94", 2)])
    )

    gap = block.points[1]
    assert gap.is_gap and gap.left_avg is None and gap.imbalance_pct is None
    assert gap.no_encoder == () and gap.faster is None


def test_empty_axis() -> None:
    block = build_motion([])

    assert block.points == [] and block.any_no_encoder is False


@pytest.mark.parametrize("n", [26, 27])
def test_fixtures(n: int, stored_session: Factory) -> None:
    r = json.loads((FIXTURES / f"session_seq{n}.json").read_text())
    sp, enc = r.get("speed") or {}, r.get("encoders") or {}
    s = stored_session(
        seq=n,
        moving_ms=r.get("moving_ms"),
        speed_left_avg_rpm=sp.get("left_avg_rpm"),
        speed_left_peak_rpm=sp.get("left_peak_rpm"),
        speed_right_avg_rpm=sp.get("right_avg_rpm"),
        speed_right_peak_rpm=sp.get("right_peak_rpm"),
        speed_imbalance_pct=sp.get("imbalance_pct"),
        encoders_left=enc.get("left"),
        encoders_right=enc.get("right"),
    )

    p = build_motion(build_axis([s], [])).points[0]

    assert p.seq == n
