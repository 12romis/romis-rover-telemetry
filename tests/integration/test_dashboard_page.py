"""Сторінка наскрізно на реальному Postgres: ролі viewer і ingest, фікстури (AC-14, AC-17, AC-18).

Дані пише `ingest` (лише INSERT), читає застосунок під `viewer`; підмін немає.
"""

import json
import re
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient

from rover_telemetry.config import WebSettings
from rover_telemetry.db.sessions import connect, insert_session
from rover_telemetry.domain.report import ParsedSession, parse_report
from rover_telemetry.web.app import app, get_settings

pytestmark = pytest.mark.integration

MAC = "288485922c94"
LATENCY_LIMIT_S = 1.0  # spec §6: p95 ≤ 1 с при ≤ 1000 виїздів (припущення, підтверджує власник)


@pytest.fixture
def client(viewer_url: str) -> Iterator[TestClient]:
    settings = WebSettings(
        database_url=viewer_url, db_connect_timeout_s=3, db_statement_timeout_s=5
    )
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def store(ingest_url: str) -> Callable[..., bool]:
    """Зберігає звіт ролью `ingest`; повертає `False` для дубля `(mac, seq)`."""

    def put(report: dict[str, Any], seq: int | None = None, minute: int = 0) -> bool:
        doc = {**report, **({"seq": seq} if seq is not None else {})}
        received = datetime(2026, 10, 23, 12, minute % 60, tzinfo=UTC)
        parsed = parse_report(f"rover/{MAC}/session", json.dumps(doc).encode(), received)
        assert isinstance(parsed, ParsedSession)
        with connect(ingest_url, timeout_s=5) as conn:
            created = insert_session(conn, parsed)
            conn.commit()
        return created

    return put


def cards(html: str) -> dict[str, str]:
    """Підпис картки → текст значення."""
    pairs = re.findall(
        r'card__label">([^<]+)</div>\s*<div class="card__value">(.*?)</div>', html, re.S
    )
    return {label: re.sub(r"<[^>]+>", "", value).strip() for label, value in pairs}


def test_ac17_new_session_visible_after_refresh(
    client: TestClient,
    store: Callable[..., bool],
    report_seq26: dict[str, Any],
    report_seq27: dict[str, Any],
) -> None:
    """AC-17: новий виїзд видно першим при першому оновленні; підсумки його враховують."""
    store(report_seq26)
    store(report_seq27)
    before = client.get("/")
    assert cards(before.text)["Виїздів"] == "2"

    store({**report_seq27, "distance_cm": 100, "voltage_end_mv": 7500}, seq=28, minute=30)
    after = client.get("/")

    assert after.status_code == 200
    summary = cards(after.text)
    assert summary["Виїздів"] == "3"
    assert summary["Пробіг"] == "1,17 м"
    assert summary["Кінцева напруга останнього виїзду"].startswith("7,50 В")
    assert summary["Отримано востаннє (за київським часом)"] == "23.10.2026 15:30"
    assert after.text.index("Виїзд № 28") < after.text.index("Виїзд № 27")


def test_ac18_duplicate_does_not_change_page(
    client: TestClient, store: Callable[..., bool], report_seq26: dict[str, Any]
) -> None:
    """AC-18: повторна доставка `(mac, seq)` — один рядок, сторінка не змінюється."""
    assert store(report_seq26) is True
    first = client.get("/").text
    assert store(report_seq26, minute=45) is False
    second = client.get("/").text

    assert second == first
    assert second.count("<details") == 1


def test_ac14_dashboard_cannot_write(
    client: TestClient,
    store: Callable[..., bool],
    report_seq26: dict[str, Any],
    viewer_url: str,
) -> None:
    """AC-14: запис через маршрут — 405, через з'єднання viewer — відмова; дані без змін."""
    store(report_seq26)
    for method in ("post", "put", "delete"):
        assert getattr(client, method)("/").status_code == 405
    with psycopg.connect(viewer_url) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("DELETE FROM sessions")
        conn.rollback()
        assert conn.execute("SELECT count(*) FROM sessions").fetchone() == (1,)


def test_null_never_rendered_as_number(client: TestClient, store: Callable[..., bool]) -> None:
    """Коректність відсутніх значень: порожній звіт — «немає даних», а не 0."""
    store({"event": "rover.session.v1", "schema_version": 1, "mac": MAC}, seq=1)
    html = client.get("/").text
    summary = cards(html)
    assert summary["Пробіг"] == "немає даних"
    assert summary["Час руху"] == "немає даних"
    assert summary["Утримань перед перешкодою"] == "немає даних"
    assert "0 м" not in html


def test_no_external_hosts_or_scripts_and_mobile_ready(
    client: TestClient, store: Callable[..., bool], report_seq26: dict[str, Any]
) -> None:
    """Зовнішні залежності: 0; AC-10: viewport і перенесення довгих значень."""
    store(report_seq26)
    html = client.get("/").text
    css = client.get("/static/app.css").text
    assert "<script" not in html
    assert not re.findall(r'(?:src|href)="https?://', html)
    assert not re.findall(r"@import|url\(\s*['\"]?https?://", css)
    assert 'name="viewport"' in html
    assert "overflow-wrap" in css


def test_latency_p95_with_1000_sessions(
    client: TestClient, store: Callable[..., bool], report_seq27: dict[str, Any], ingest_url: str
) -> None:
    """NFR: p95 формування сторінки ≤ 1 с при 1000 виїздів зі звітами."""
    with connect(ingest_url, timeout_s=5) as conn:
        for seq in range(1, 1001):
            raw = json.dumps({**report_seq27, "seq": seq}).encode()
            parsed = parse_report(f"rover/{MAC}/session", raw, datetime(2026, 10, 23, tzinfo=UTC))
            assert isinstance(parsed, ParsedSession)
            insert_session(conn, parsed)
        conn.commit()

    timings = []
    for _ in range(20):
        started = time.perf_counter()
        response = client.get("/")
        timings.append(time.perf_counter() - started)
        assert response.status_code == 200
    p95 = sorted(timings)[int(len(timings) * 0.95) - 1]

    assert response.text.count("<details") == 1000
    assert p95 <= LATENCY_LIMIT_S, f"p95={p95:.3f} с"
