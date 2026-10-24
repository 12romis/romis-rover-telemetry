"""Схема `rejected`: окремий запис на кожну доставку, байти дослівно (AC-05, AC-07)."""

import psycopg
import pytest

pytestmark = pytest.mark.integration

INSERT = (
    "INSERT INTO rejected (topic, reason_code, reason_text, raw, raw_size, raw_truncated, "
    "received_at) VALUES (%s, %s, %s, %s, %s, %s, now())"
)


def test_repeated_delivery_gives_separate_rows(migrated_db: str) -> None:
    """AC-05: ключа дедублікації немає, кожна доставка — окремий запис."""
    row = ("rover/x/session", "not_json", "не JSON", b"garbage", 7, False)
    with psycopg.connect(migrated_db) as conn:
        conn.execute(INSERT, row)
        conn.execute(INSERT, row)
        ids = conn.execute("SELECT id FROM rejected ORDER BY id").fetchall()
    assert len(ids) == 2
    assert ids[0] != ids[1]


def test_raw_keeps_nul_bytes_and_non_utf8(migrated_db: str) -> None:
    raw = b"\x00\xff\xfe{not json"
    with psycopg.connect(migrated_db) as conn:
        conn.execute(INSERT, ("t", "not_json", "x", raw, len(raw), False))
        stored = conn.execute("SELECT raw FROM rejected").fetchone()
    assert stored is not None
    assert bytes(stored[0]) == raw


def test_truncation_flag_and_size_are_stored_apart_from_raw(migrated_db: str) -> None:
    """AC-07: розмір і позначка обрізання не входять до 1024 байт `raw`."""
    raw = b"a" * 1024
    with psycopg.connect(migrated_db) as conn:
        conn.execute(INSERT, ("t", "unsupported_schema", "x", raw, 5000, True))
        row = conn.execute("SELECT length(raw), raw_size, raw_truncated FROM rejected").fetchone()
    assert row == (1024, 5000, True)


def test_identity_id_cannot_be_set_explicitly(migrated_db: str) -> None:
    with psycopg.connect(migrated_db) as conn, pytest.raises(psycopg.errors.GeneratedAlways):
        conn.execute(
            "INSERT INTO rejected (id, topic, reason_code, reason_text, raw, raw_size, "
            "raw_truncated, received_at) VALUES (1, 't', 'c', 'x', ''::bytea, 0, false, now())"
        )
