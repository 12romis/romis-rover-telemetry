"""Права ролей Postgres: `viewer` лише читає, `ingest` лише дописує (AC-15, AC-16)."""

import json
from datetime import UTC, datetime

import psycopg
import pytest

from rover_telemetry.db.sessions import connect, insert_rejected, insert_session
from rover_telemetry.domain.report import ParsedSession, Rejection, parse_report

pytestmark = pytest.mark.integration

TABLES = ["sessions", "rejected"]
WRITES = {
    "INSERT": {
        "sessions": "INSERT INTO sessions (mac, seq, schema_version, received_at, raw, payload) "
        "VALUES ('x', 1, 1, now(), ''::bytea, '{}')",
        "rejected": "INSERT INTO rejected (topic, reason_code, reason_text, raw, raw_size, "
        "raw_truncated, received_at) VALUES ('t', 'c', 'x', ''::bytea, 0, false, now())",
    },
    "UPDATE": {t: f"UPDATE {t} SET raw = ''::bytea" for t in TABLES},
    "DELETE": {t: f"DELETE FROM {t}" for t in TABLES},
}


@pytest.fixture
def stored(migrated_db: str, ingest_url: str, report_seq26: dict[str, object]) -> None:
    """Одна сесія й одне відхилене, записані роллю `ingest`."""
    raw = json.dumps(report_seq26).encode()
    parsed = parse_report("rover/288485922c94/session", raw, datetime.now(UTC))
    assert isinstance(parsed, ParsedSession)
    rejection = Rejection("rover/x/session", "not_json", "x", b"junk", 4, False, datetime.now(UTC))
    with connect(ingest_url, timeout_s=5) as conn:
        insert_session(conn, parsed)
        insert_rejected(conn, rejection)
        conn.commit()


def _snapshot(url: str) -> list[list[tuple[object, ...]]]:
    with psycopg.connect(url) as conn:
        return [
            conn.execute("SELECT * FROM sessions ORDER BY mac, seq").fetchall(),
            conn.execute("SELECT * FROM rejected ORDER BY id").fetchall(),
        ]


@pytest.mark.parametrize("table", TABLES)
@pytest.mark.parametrize("action", ["INSERT", "UPDATE", "DELETE"])
def test_viewer_cannot_write(
    stored: None, migrated_db: str, viewer_url: str, table: str, action: str
) -> None:
    """AC-15: облікові дані дашборду не змінюють і не видаляють дані."""
    before = _snapshot(migrated_db)
    with (
        psycopg.connect(viewer_url) as conn,
        pytest.raises(psycopg.errors.InsufficientPrivilege),
    ):
        conn.execute(WRITES[action][table])
    assert _snapshot(migrated_db) == before


@pytest.mark.parametrize("table", TABLES)
@pytest.mark.parametrize("action", ["UPDATE", "DELETE", "SELECT"])
def test_ingest_cannot_read_change_or_delete(
    stored: None, migrated_db: str, ingest_url: str, table: str, action: str
) -> None:
    """AC-16 (частина сховища): сервіс приймання лише дописує."""
    sql = f"SELECT * FROM {table}" if action == "SELECT" else WRITES[action][table]
    before = _snapshot(migrated_db)
    with (
        psycopg.connect(ingest_url) as conn,
        pytest.raises(psycopg.errors.InsufficientPrivilege),
    ):
        conn.execute(sql)
    assert _snapshot(migrated_db) == before


@pytest.mark.parametrize("table", TABLES)
def test_viewer_reads_tables_and_gaps(stored: None, viewer_url: str, table: str) -> None:
    with psycopg.connect(viewer_url) as conn:
        assert conn.execute(f"SELECT count(*) FROM {table}").fetchone() == (1,)
        assert conn.execute("SELECT count(*) FROM session_gaps").fetchone() == (0,)


def test_ingest_cannot_read_session_gaps(stored: None, ingest_url: str) -> None:
    with psycopg.connect(ingest_url) as conn, pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute("SELECT * FROM session_gaps")
