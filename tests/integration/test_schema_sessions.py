"""Схема `sessions`: складений ключ, NULL проти 0, єдина часова мітка (AC-04, AC-10, AC-11)."""

import json

import psycopg
import pytest

pytestmark = pytest.mark.integration

INSERT = (
    "INSERT INTO sessions (mac, seq, schema_version, received_at, raw, payload, "
    "holds_count, distance_cm) VALUES (%s, %s, 1, now(), %s, %s::jsonb, %s, %s)"
)


def _insert(
    conn: psycopg.Connection, mac: str, seq: int, holds: int | None, dist: int | None
) -> None:
    raw = json.dumps({"mac": mac, "seq": seq}).encode()
    conn.execute(INSERT, (mac, seq, raw, raw.decode(), holds, dist))


def test_same_seq_for_different_mac_is_stored(migrated_db: str) -> None:
    """AC-04: унікальність номера діє лише в межах одного ровера."""
    with psycopg.connect(migrated_db) as conn:
        _insert(conn, "aaaaaaaaaaaa", 7, 1, 1)
        _insert(conn, "bbbbbbbbbbbb", 7, 1, 1)
        count = conn.execute("SELECT count(*) FROM sessions WHERE seq = 7").fetchone()
    assert count == (2,)


def test_same_mac_and_seq_is_rejected_by_key(migrated_db: str) -> None:
    with psycopg.connect(migrated_db) as conn:
        _insert(conn, "aaaaaaaaaaaa", 7, 1, 1)
        with pytest.raises(psycopg.errors.UniqueViolation):
            _insert(conn, "aaaaaaaaaaaa", 7, 1, 1)


def test_null_and_zero_are_distinguished(migrated_db: str) -> None:
    """AC-10: NULL («немає даних») і виміряний 0 зберігаються як різні значення."""
    with psycopg.connect(migrated_db) as conn:
        _insert(conn, "aaaaaaaaaaaa", 1, None, None)
        _insert(conn, "aaaaaaaaaaaa", 2, 0, 0)
        rows = conn.execute(
            "SELECT seq, holds_count, distance_cm, speed_left_avg_rpm FROM sessions ORDER BY seq"
        ).fetchall()
    assert rows == [(1, None, None, None), (2, 0, 0, None)]


def test_only_received_at_is_a_time_column(migrated_db: str) -> None:
    """AC-11: часу сесії немає, лише «отримано»."""
    with psycopg.connect(migrated_db) as conn:
        cols = conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'sessions' "
            "AND (data_type LIKE 'timestamp%%' OR data_type = 'date' OR data_type LIKE 'time%%')"
        ).fetchall()
    assert cols == [("received_at",)]


def test_primary_key_is_the_only_unique_constraint(migrated_db: str) -> None:
    """ADR-0005: ON CONFLICT DO NOTHING без цілі безпечний лише з одним обмеженням."""
    with psycopg.connect(migrated_db) as conn:
        rows = conn.execute(
            "SELECT i.indisprimary, array_agg(a.attname ORDER BY a.attnum) "
            "FROM pg_index i JOIN pg_attribute a ON a.attrelid = i.indrelid "
            "AND a.attnum = ANY(i.indkey) "
            "WHERE i.indrelid = 'sessions'::regclass AND i.indisunique GROUP BY i.indexrelid, "
            "i.indisprimary"
        ).fetchall()
    assert rows == [(True, ["mac", "seq"])]
