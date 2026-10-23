"""Обробка одного повідомлення: розбір, запис, COMMIT, результат (AC-01, AC-03, AC-05, AC-06)."""

import json
import logging
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg
import pytest

from rover_telemetry.db.sessions import connect
from rover_telemetry.ingest.handler import Outcome, handle_message

pytestmark = pytest.mark.integration

MAC = "288485922c94"
TOPIC = f"rover/{MAC}/session"


@pytest.fixture
def conn(ingest_url: str) -> Iterator[psycopg.Connection]:
    with connect(ingest_url, timeout_s=5) as c:
        yield c


def _now() -> datetime:
    return datetime.now(UTC)


def _count(url: str, table: str) -> int:
    with psycopg.connect(url) as c:
        row = c.execute(f"SELECT count(*) FROM {table}").fetchone()
    assert row is not None
    return int(row[0])


def test_valid_report_is_stored_and_committed_before_return(
    conn: psycopg.Connection, migrated_db: str, report_seq26: dict[str, Any]
) -> None:
    """AC-01: після повернення результату сесія вже видна іншому з'єднанню (COMMIT був)."""
    received = _now()
    outcome = handle_message(conn, TOPIC, json.dumps(report_seq26).encode(), received)
    assert outcome is Outcome.STORED
    with psycopg.connect(migrated_db) as c:
        row = c.execute("SELECT seq, received_at FROM sessions").fetchone()
    assert row == (26, received)


def test_duplicate_keeps_received_at_and_adds_nothing_to_rejected(
    conn: psycopg.Connection, migrated_db: str, report_seq26: dict[str, Any]
) -> None:
    """AC-03."""
    payload = json.dumps(report_seq26).encode()
    first = _now()
    assert handle_message(conn, TOPIC, payload, first) is Outcome.STORED
    assert handle_message(conn, TOPIC, payload, first + timedelta(hours=1)) is Outcome.DUPLICATE
    with psycopg.connect(migrated_db) as c:
        rows = c.execute("SELECT received_at FROM sessions").fetchall()
    assert rows == [(first,)]
    assert _count(migrated_db, "rejected") == 0


def test_garbage_is_stored_as_rejected_each_time(
    conn: psycopg.Connection, migrated_db: str
) -> None:
    """AC-05: сесії немає, кожна повторна доставка — окремий запис."""
    junk = b"\x00\xffnot json"
    assert handle_message(conn, TOPIC, junk, _now()) is Outcome.REJECTED
    assert handle_message(conn, TOPIC, junk, _now()) is Outcome.REJECTED
    assert _count(migrated_db, "sessions") == 0
    with psycopg.connect(migrated_db) as c:
        rows = c.execute("SELECT reason_code, raw, topic FROM rejected").fetchall()
    assert [(r[0], bytes(r[1]), r[2]) for r in rows] == [("not_json", junk, TOPIC)] * 2


def test_mac_not_matching_topic_is_rejected(
    conn: psycopg.Connection, migrated_db: str, report_seq26: dict[str, Any]
) -> None:
    """AC-06."""
    outcome = handle_message(
        conn, "rover/aabbccddeeff/session", json.dumps(report_seq26).encode(), _now()
    )
    assert outcome is Outcome.REJECTED
    assert _count(migrated_db, "sessions") == 0
    with psycopg.connect(migrated_db) as c:
        assert c.execute("SELECT reason_code FROM rejected").fetchone() == ("id_mismatch",)


def test_storage_failure_is_raised_not_swallowed(
    conn: psycopg.Connection, report_seq26: dict[str, Any]
) -> None:
    """ADR-0001: збій запису піднімається, результату (отже й ack) немає."""
    conn.close()
    with pytest.raises(psycopg.Error):
        handle_message(conn, TOPIC, json.dumps(report_seq26).encode(), _now())


def test_log_line_has_event_and_no_report_content(
    conn: psycopg.Connection, report_seq26: dict[str, Any], caplog: pytest.LogCaptureFixture
) -> None:
    payload = json.dumps(report_seq26).encode()
    with caplog.at_level(logging.INFO, logger="rover_telemetry.ingest.handler"):
        handle_message(conn, TOPIC, payload, _now())
        handle_message(conn, TOPIC, payload, _now())
        handle_message(conn, TOPIC, b"SECRET-GARBAGE", _now())
    lines = [r.getMessage() for r in caplog.records]
    assert len(lines) == 3
    assert lines[0].startswith(f"event=stored mac={MAC} seq=26 received_at=")
    assert "latency_ms=" in lines[0]
    assert lines[1].startswith(f"event=duplicate mac={MAC} seq=26 ")
    assert lines[2].startswith("event=rejected reason_code=not_json ")
    joined = "\n".join(lines)
    assert "SECRET-GARBAGE" not in joined
    assert "duration_ms" not in joined
    assert "voltage" not in joined
