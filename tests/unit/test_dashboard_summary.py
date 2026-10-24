"""Підсумки дашборду з рядків одного знімка (AC-01, AC-04, AC-07, AC-11)."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from rover_telemetry.domain.dashboard import (
    EndReason,
    GapNumber,
    StoredSession,
    Total,
    build_summary,
    classify_end_reason,
)
from rover_telemetry.domain.report import ParsedSession, parse_report

Factory = Callable[..., StoredSession]
RECEIVED = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)


def from_fixture(report: dict[str, Any], received_at: datetime = RECEIVED) -> StoredSession:
    """Реальний звіт → `parse_report` → рядок `sessions`, як його прочитає `db`."""
    import json

    parsed = parse_report(
        f"rover/{report['mac']}/session", json.dumps(report).encode(), received_at
    )
    assert isinstance(parsed, ParsedSession)
    return StoredSession(
        mac=parsed.mac,
        seq=parsed.seq,
        received_at=parsed.received_at,
        duration_ms=parsed.duration_ms,
        end_reason=parsed.end_reason,
        voltage_start_mv=parsed.voltage_start_mv,
        voltage_end_mv=parsed.voltage_end_mv,
        voltage_min_mv=parsed.voltage_min_mv,
        holds_count=parsed.holds_count,
        moving_ms=parsed.moving_ms,
        distance_cm=parsed.distance_cm,
        fw_version=parsed.fw_version,
        payload=parsed.payload,
    )


def test_ac01_summary_of_real_fixtures(
    report_seq26: dict[str, Any], report_seq27: dict[str, Any]
) -> None:
    """AC-01: підсумки seq 26 + 27 — кількість, пробіг, час руху, утримання, останній виїзд."""
    later = datetime(2026, 10, 23, 14, 0, tzinfo=UTC)
    s26 = from_fixture(report_seq26)
    s27 = from_fixture(report_seq27, later)

    summary = build_summary([s26, s27], [])

    assert summary.sessions == 2
    assert summary.distance == Total(sum=17, missing=0, total=2)
    assert summary.moving == Total(sum=s26.moving_ms + s27.moving_ms, missing=0, total=2)  # type: ignore[operator]
    assert summary.holds == Total(sum=1, missing=0, total=2)
    assert summary.last_voltage_end_mv == s27.voltage_end_mv
    assert summary.last_seq == 27
    assert summary.last_received_at == later
    assert summary.last_fw_version == s27.fw_version
    assert summary.lost == 0


def test_ac07_partial_missing_sums_only_known(stored_session: Factory) -> None:
    """AC-07: сума лише за відомими, `missing` — скільки без даних; виміряний 0 не «missing»."""
    sessions = [
        stored_session(seq=1, distance_cm=0),
        stored_session(seq=2, distance_cm=50),
        stored_session(seq=3, distance_cm=None),
    ]

    summary = build_summary(sessions, [])

    assert summary.distance == Total(sum=50, missing=1, total=3)


def test_ac07_nothing_known_is_none_not_zero(stored_session: Factory) -> None:
    """AC-07: даних немає в жодному — `sum is None`, а не 0."""
    sessions = [stored_session(seq=1), stored_session(seq=2)]

    summary = build_summary(sessions, [])

    assert summary.distance == Total(sum=None, missing=2, total=2)
    assert summary.holds.sum is None


def test_ac01_last_voltage_not_substituted(stored_session: Factory) -> None:
    """Кінцева напруга останнього виїзду `NULL` лишається `None`, попередня не підставляється."""
    sessions = [
        stored_session(seq=1, voltage_end_mv=7600),
        stored_session(seq=2, voltage_end_mv=None),
    ]

    assert build_summary(sessions, []).last_voltage_end_mv is None


def test_last_session_ties_broken_by_mac(stored_session: Factory) -> None:
    """Однаковий `seq` у різних `mac`: «останній» за `(seq ↓, mac)` — детермінований."""
    sessions = [
        stored_session(mac="bb", seq=5, fw_version="b"),
        stored_session(mac="aa", seq=5, fw_version="a"),
    ]

    assert build_summary(sessions, []).last_fw_version == "a"


def test_last_received_is_max_not_last_seq(stored_session: Factory) -> None:
    """Останнє «отримано» — максимум за всіма виїздами, а не за виїздом з найбільшим номером."""
    late = datetime(2026, 10, 24, 1, 0, tzinfo=UTC)
    sessions = [
        stored_session(seq=1, received_at=late),
        stored_session(seq=2, received_at=RECEIVED),
    ]

    assert build_summary(sessions, []).last_received_at == late


def test_ac08_lost_counts_gaps(stored_session: Factory) -> None:
    """AC-08: кількість втрачених сесій = кількість номерів без виїзду."""
    gaps = [GapNumber(mac="288485922c94", seq=3), GapNumber(mac="288485922c94", seq=4)]

    assert build_summary([stored_session(seq=2), stored_session(seq=5)], gaps).lost == 2


def test_ac11_empty_set(stored_session: Factory) -> None:
    """AC-11: виїздів немає — 0 (виміряне), решта `None`."""
    summary = build_summary([], [])

    assert summary.sessions == 0
    assert summary.distance == Total(sum=None, missing=0, total=0)
    assert summary.moving.sum is None
    assert summary.holds.sum is None
    assert summary.last_voltage_end_mv is None
    assert summary.last_seq is None
    assert summary.last_received_at is None
    assert summary.last_fw_version is None
    assert summary.lost is None


def test_ac04_classify_end_reason() -> None:
    """AC-04: відомі причини, невідома → OTHER, `None` → `None` (не OTHER)."""
    assert classify_end_reason("disarm") is EndReason.DISARM
    assert classify_end_reason("failsafe_link_lost") is EndReason.LINK_LOST
    assert classify_end_reason("failsafe_voltage") is EndReason.VOLTAGE
    assert classify_end_reason("something_new") is EndReason.OTHER
    assert classify_end_reason(None) is None
