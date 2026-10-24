"""Облік втрат `session_gaps` (AC-08, AC-09)."""

import json
from datetime import UTC, datetime
from typing import Any

import psycopg
import pytest

from rover_telemetry.db.sessions import connect, insert_session
from rover_telemetry.domain.report import ParsedSession, parse_report

pytestmark = pytest.mark.integration

MAC_A = "288485922c94"
MAC_B = "aabbccddeeff"


def _store(ingest_url: str, report: dict[str, Any], mac: str, seqs: list[int]) -> None:
    with connect(ingest_url, timeout_s=5) as conn:
        for seq in seqs:
            raw = json.dumps({**report, "mac": mac, "seq": seq}).encode()
            parsed = parse_report(f"rover/{mac}/session", raw, datetime.now(UTC))
            assert isinstance(parsed, ParsedSession)
            insert_session(conn, parsed)
            conn.commit()


def _gaps(viewer_url: str) -> list[tuple[str, int]]:
    with psycopg.connect(viewer_url) as conn:
        rows = conn.execute("SELECT mac, seq FROM session_gaps ORDER BY mac, seq").fetchall()
    return [(m, int(s)) for m, s in rows]


def test_empty_sessions_give_no_gaps(viewer_url: str) -> None:
    assert _gaps(viewer_url) == []


def test_lost_session_is_counted_from_lowest_stored_seq(
    ingest_url: str, viewer_url: str, report_seq26: dict[str, Any]
) -> None:
    """AC-08: 28, 29, 31 -> втрачено 30; сесії до 28 втраченими не вважаються."""
    _store(ingest_url, report_seq26, MAC_A, [28, 29, 31])
    assert _gaps(viewer_url) == [(MAC_A, 30)]


def test_late_session_disappears_from_gaps(
    ingest_url: str, viewer_url: str, report_seq26: dict[str, Any]
) -> None:
    """AC-09: порядок отримання довільний; 30 після 31 і 32 більше не втрачена."""
    _store(ingest_url, report_seq26, MAC_A, [28, 29, 31, 32])
    assert _gaps(viewer_url) == [(MAC_A, 30)]
    _store(ingest_url, report_seq26, MAC_A, [30])
    assert _gaps(viewer_url) == []


def test_lower_seq_shifts_the_start(
    ingest_url: str, viewer_url: str, report_seq26: dict[str, Any]
) -> None:
    """AC-08: менший номер, що надійшов пізніше, зсуває початок обліку."""
    _store(ingest_url, report_seq26, MAC_A, [28, 29])
    assert _gaps(viewer_url) == []
    _store(ingest_url, report_seq26, MAC_A, [25])
    assert _gaps(viewer_url) == [(MAC_A, 26), (MAC_A, 27)]


def test_two_rovers_are_not_mixed(
    ingest_url: str, viewer_url: str, report_seq26: dict[str, Any]
) -> None:
    _store(ingest_url, report_seq26, MAC_A, [1, 2, 3])
    _store(ingest_url, report_seq26, MAC_B, [1, 3])
    assert _gaps(viewer_url) == [(MAC_B, 2)]
