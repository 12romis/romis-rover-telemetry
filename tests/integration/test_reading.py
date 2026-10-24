"""Один знімок читання для дашборду (AC-08, AC-14, AC-16)."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg
import pytest

from rover_telemetry.config import WebSettings
from rover_telemetry.db.reading import open_connection, read_snapshot
from rover_telemetry.db.sessions import connect, insert_rejected, insert_session
from rover_telemetry.domain.dashboard import GapNumber
from rover_telemetry.domain.report import ParsedSession, Rejection, parse_report

pytestmark = pytest.mark.integration

MAC = "288485922c94"


def _insert(ingest_url: str, report: dict[str, Any], seq: int) -> None:
    raw = json.dumps({**report, "seq": seq}).encode()
    parsed = parse_report(f"rover/{MAC}/session", raw, datetime(2026, 10, 23, 12, 0, tzinfo=UTC))
    assert isinstance(parsed, ParsedSession)
    with connect(ingest_url, timeout_s=5) as conn:
        insert_session(conn, parsed)
        conn.commit()


@pytest.fixture
def stored(ingest_url: str, report_seq26: dict[str, Any], report_seq27: dict[str, Any]) -> None:
    """seq 26, 27 і 30 (пропуски 28, 29), порожній звіт із NULL-ами (31), відхилене."""
    _insert(ingest_url, report_seq26, 26)
    _insert(ingest_url, report_seq27, 27)
    _insert(ingest_url, report_seq27, 30)
    _insert(ingest_url, {"event": "rover.session.v1", "schema_version": 1, "mac": MAC}, 31)
    rejection = Rejection(
        f"rover/{MAC}/session", "bad_type", "x", b"{}", 2, False, datetime.now(UTC)
    )
    with connect(ingest_url, timeout_s=5) as conn:
        insert_rejected(conn, rejection)
        conn.commit()


def _settings(viewer_url: str) -> WebSettings:
    return WebSettings(database_url=viewer_url, db_connect_timeout_s=3, db_statement_timeout_s=5)


def test_snapshot_reads_sessions_and_gaps(stored: None, viewer_url: str) -> None:
    """AC-08, AC-16: виїзди без raw; пропуски 28, 29; відхилене виїздом не є."""
    with open_connection(_settings(viewer_url)) as conn:
        snapshot = read_snapshot(conn)

    assert sorted(s.seq for s in snapshot.sessions) == [26, 27, 30, 31]
    assert sorted(snapshot.gaps, key=lambda g: g.seq) == [GapNumber(MAC, 28), GapNumber(MAC, 29)]
    s26 = next(s for s in snapshot.sessions if s.seq == 26)
    assert s26.distance_cm == 0  # виміряний нуль лишається 0
    assert s26.payload["event"] == "rover.session.v1"
    empty = next(s for s in snapshot.sessions if s.seq == 31)
    assert empty.distance_cm is None and empty.end_reason is None  # NULL, не 0


def test_snapshot_is_read_only(stored: None, viewer_url: str) -> None:
    """AC-14: у знімку транзакція READ ONLY, запис відхиляється, дані без змін."""
    with open_connection(_settings(viewer_url)) as conn:
        read_snapshot(conn)
        assert conn.execute("SHOW transaction_read_only").fetchone() == ("on",)
        with pytest.raises(psycopg.Error):
            conn.execute("DELETE FROM sessions")
    with open_connection(_settings(viewer_url)) as conn:
        assert len(read_snapshot(conn).sessions) == 4


def test_snapshot_does_not_read_raw_or_rejected() -> None:
    from rover_telemetry.db import reading

    source = Path(reading.__file__).read_text().lower()
    assert "raw" not in source.replace("raw_", "")
    assert "from rejected" not in source


def test_empty_database(migrated_db: str, viewer_url: str) -> None:
    with open_connection(_settings(viewer_url)) as conn:
        snapshot = read_snapshot(conn)
    assert snapshot.sessions == [] and snapshot.gaps == []


_CHART_FIELDS = (
    "holds_min_mm",
    "holds_min_sensor",
    "holds_left_front",
    "holds_front",
    "holds_right_front",
    "holds_rear",
    "tof_control_off_ms",
    "speed_left_avg_rpm",
    "speed_left_peak_rpm",
    "speed_right_avg_rpm",
    "speed_right_peak_rpm",
    "speed_imbalance_pct",
    "encoders_left",
    "encoders_right",
)


def test_snapshot_reads_chart_columns(stored: None, viewer_url: str) -> None:
    """Нові колонки для графіків читаються тим самим знімком (AC-12, AC-13)."""
    with open_connection(_settings(viewer_url)) as conn:
        snapshot = read_snapshot(conn)

    s27 = next(s for s in snapshot.sessions if s.seq == 27)
    assert s27.holds_min_mm == 103
    assert s27.holds_min_sensor == "front"
    assert (s27.holds_left_front, s27.holds_front) == (0, 1)  # виміряний нуль — не None
    assert (s27.holds_right_front, s27.holds_rear) == (1, 1)
    assert s27.tof_control_off_ms == 6660
    assert (s27.speed_left_avg_rpm, s27.speed_left_peak_rpm) == (30.6, 100.1)
    assert (s27.speed_right_avg_rpm, s27.speed_right_peak_rpm) == (30.3, 105.0)
    assert s27.speed_imbalance_pct == 1.1
    assert (s27.encoders_left, s27.encoders_right) == (True, True)
    # позиційне створення не зсунуло наявні поля
    assert s27.end_reason == "disarm" and s27.fw_version == "4727195"
    assert s27.payload["event"] == "rover.session.v1"


def test_snapshot_null_chart_columns_stay_none(stored: None, viewer_url: str) -> None:
    """`NULL` у кожній новій колонці читається як `None`, не `0` і не `False`."""
    with open_connection(_settings(viewer_url)) as conn:
        snapshot = read_snapshot(conn)

    empty = next(s for s in snapshot.sessions if s.seq == 31)
    for name in _CHART_FIELDS:
        assert getattr(empty, name) is None, name


def test_snapshot_false_encoder_and_zero_speed_are_values(
    ingest_url: str, viewer_url: str, report_seq27: dict[str, Any]
) -> None:
    report = {
        **report_seq27,
        "encoders": {"left": False, "right": True},
        "speed": {**report_seq27["speed"], "left_avg_rpm": 0.0},
    }
    _insert(ingest_url, report, 40)

    with open_connection(_settings(viewer_url)) as conn:
        (s,) = read_snapshot(conn).sessions

    assert s.encoders_left is False and s.encoders_right is True
    assert s.speed_left_avg_rpm == 0.0


def test_snapshot_duplicate_and_rejected_add_no_session(
    stored: None, ingest_url: str, viewer_url: str, report_seq27: dict[str, Any]
) -> None:
    """AC-23: повтор `(mac, seq)` не дає другого виїзду, відхилене виїздом не стає."""
    _insert(ingest_url, report_seq27, 27)

    with open_connection(_settings(viewer_url)) as conn:
        snapshot = read_snapshot(conn)

    assert sorted(s.seq for s in snapshot.sessions) == [26, 27, 30, 31]
