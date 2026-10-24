"""Затримка побудови блоків на 1000 виїздів (NFR): `read_snapshot` + `render_blocks`, p95 ≤ 1 с."""

import json
import time
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from rover_telemetry.config import WebSettings
from rover_telemetry.db.reading import open_connection, read_snapshot
from rover_telemetry.db.sessions import connect, insert_session
from rover_telemetry.domain.report import ParsedSession, parse_report
from rover_telemetry.web.chart_blocks import render_blocks

pytestmark = pytest.mark.integration

MAC = "288485922c94"
LIMIT_S = 1.0  # spec §6: p95 ≤ 1 с при ≤ 1000 виїздів
RUNS = 20


def test_blocks_p95_with_1000_sessions(
    ingest_url: str, viewer_url: str, report_seq27: dict[str, Any], client: TestClient
) -> None:
    with connect(ingest_url, timeout_s=5) as conn:
        for seq in range(1, 1001):
            raw = json.dumps({**report_seq27, "seq": seq}).encode()
            parsed = parse_report(f"rover/{MAC}/session", raw, datetime(2026, 10, 23, tzinfo=UTC))
            assert isinstance(parsed, ParsedSession)
            insert_session(conn, parsed)
        conn.commit()
    settings = WebSettings(
        database_url=viewer_url, db_connect_timeout_s=3, db_statement_timeout_s=5
    )

    timings = []
    for _ in range(RUNS):
        started = time.perf_counter()
        with open_connection(settings) as conn:
            blocks = render_blocks(read_snapshot(conn))
        timings.append(time.perf_counter() - started)
    p95 = sorted(timings)[int(RUNS * 0.95) - 1]
    html = client.get("/").text

    assert [b.state for b in blocks] == ["ok", "ok", "ok"]
    print(f"html_bytes={len(html.encode())} blocks_p95_s={p95:.3f}")  # для рішення spec §8
    assert p95 <= LIMIT_S, f"p95={p95:.3f} с"
