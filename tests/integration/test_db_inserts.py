"""Запис сесій і відхилених під роллю `ingest` (AC-01, AC-03, AC-03b, AC-05b)."""

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg
import pytest

from rover_telemetry.db.sessions import connect, insert_rejected, insert_session
from rover_telemetry.domain.report import ParsedSession, Rejection, parse_report

pytestmark = pytest.mark.integration

T0 = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)


def _session(report: dict[str, Any], received_at: datetime = T0) -> ParsedSession:
    raw = json.dumps(report, separators=(",", ":")).encode()
    result = parse_report(f"rover/{report['mac']}/session", raw, received_at)
    assert isinstance(result, ParsedSession)
    return result


def _rejection(mac: str, reason: str = "bad_type") -> Rejection:
    return Rejection(f"rover/{mac}/session", reason, "x", b"{}", 2, False, T0)


def test_new_session_is_stored_with_received_at(
    ingest_url: str, migrated_db: str, report_seq26: dict[str, Any]
) -> None:
    """AC-01: сесія з'являється серед збережених разом із часом «отримано»."""
    with connect(ingest_url, timeout_s=5) as conn:
        assert insert_session(conn, _session(report_seq26)) is True
        conn.commit()
    with psycopg.connect(migrated_db) as conn:
        row = conn.execute(
            "SELECT mac, seq, received_at, distance_cm, speed_left_avg_rpm, payload->>'seq' "
            "FROM sessions"
        ).fetchone()
    assert row == ("288485922c94", 26, T0, 0, None, "26")


def test_duplicate_is_ignored_and_keeps_first_received_at(
    ingest_url: str, migrated_db: str, report_seq26: dict[str, Any]
) -> None:
    """AC-03: повтор не змінює сесію й час «отримано»."""
    with connect(ingest_url, timeout_s=5) as conn:
        assert insert_session(conn, _session(report_seq26)) is True
        conn.commit()
        assert insert_session(conn, _session(report_seq26, T0 + timedelta(hours=1))) is False
        conn.commit()
    with psycopg.connect(migrated_db) as conn:
        rows = conn.execute("SELECT received_at FROM sessions").fetchall()
        rejected = conn.execute("SELECT count(*) FROM rejected").fetchone()
    assert rows == [(T0,)]
    assert rejected == (0,)


def test_duplicate_with_different_content_leaves_stored_session_unchanged(
    ingest_url: str, migrated_db: str, report_seq26: dict[str, Any]
) -> None:
    """AC-03b: той самий (mac, seq) з іншим вмістом — звичайний дубль."""
    changed = {**report_seq26, "duration_ms": 999, "distance_cm": 12345}
    with connect(ingest_url, timeout_s=5) as conn:
        assert insert_session(conn, _session(report_seq26)) is True
        conn.commit()
        assert insert_session(conn, _session(changed)) is False
        conn.commit()
    with psycopg.connect(migrated_db) as conn:
        row = conn.execute("SELECT duration_ms, distance_cm FROM sessions").fetchone()
    assert row == (report_seq26["duration_ms"], 0)


def test_rejected_does_not_occupy_the_session_number(
    ingest_url: str, migrated_db: str, report_seq26: dict[str, Any]
) -> None:
    """AC-05b: відхилений звіт з (mac, N) не заважає валідній сесії (mac, N)."""
    with connect(ingest_url, timeout_s=5) as conn:
        insert_rejected(conn, _rejection("288485922c94"))
        conn.commit()
        assert insert_session(conn, _session(report_seq26)) is True
        conn.commit()
    with psycopg.connect(migrated_db) as conn:
        counts = (
            conn.execute("SELECT count(*) FROM sessions").fetchone(),
            conn.execute("SELECT count(*) FROM rejected").fetchone(),
        )
    assert counts == ((1,), (1,))


def test_rejected_repeat_gives_separate_rows(ingest_url: str, migrated_db: str) -> None:
    with connect(ingest_url, timeout_s=5) as conn:
        insert_rejected(conn, _rejection("aaaaaaaaaaaa"))
        insert_rejected(conn, _rejection("aaaaaaaaaaaa"))
        conn.commit()
    with psycopg.connect(migrated_db) as conn:
        assert conn.execute("SELECT count(*) FROM rejected").fetchone() == (2,)


def test_uncommitted_insert_is_not_stored(
    ingest_url: str, migrated_db: str, report_seq26: dict[str, Any]
) -> None:
    """COMMIT робить викликач: без нього сесії немає."""
    with connect(ingest_url, timeout_s=5) as conn:
        insert_session(conn, _session(report_seq26))
        conn.rollback()
    with psycopg.connect(migrated_db) as conn:
        assert conn.execute("SELECT count(*) FROM sessions").fetchone() == (0,)


@pytest.mark.parametrize("table", ["sessions", "rejected"])
@pytest.mark.parametrize(
    "sql",
    ["SELECT 1 FROM {t}", "UPDATE {t} SET raw = ''::bytea", "DELETE FROM {t}"],
)
def test_ingest_role_can_only_insert(ingest_url: str, table: str, sql: str) -> None:
    with (
        connect(ingest_url, timeout_s=5) as conn,
        pytest.raises(psycopg.errors.InsufficientPrivilege),
    ):
        conn.execute(sql.format(t=table))
