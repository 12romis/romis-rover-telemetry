"""Запуск підписника: очікування БД, QoS 1 з manual ack, вихід при збої (AC-17, AC-18)."""

import logging
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import paho.mqtt.client as mqtt
import psycopg
import pytest

from rover_telemetry.config import IngestSettings
from rover_telemetry.ingest.__main__ import (
    TOPIC_FILTER,
    build_client,
    make_on_connect,
    make_on_message,
    wait_for_db,
)
from rover_telemetry.ingest.handler import Outcome

SETTINGS = IngestSettings.from_env(
    {
        "INGEST_DATABASE_URL": "postgresql://ingest:p@db/rover",
        "MQTT_USERNAME": "rover-ingest",
        "MQTT_PASSWORD": "secret",
    }
)
STAMP = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)


class FakeClient:
    def __init__(self, calls: list[Any]) -> None:
        self.calls = calls

    def ack(self, mid: int, qos: int) -> None:
        self.calls.append(("ack", mid, qos))

    def disconnect(self) -> None:
        self.calls.append(("disconnect",))

    def subscribe(self, topic: str, qos: int) -> None:
        self.calls.append(("subscribe", topic, qos))


def _msg() -> Any:
    return SimpleNamespace(topic="rover/288485922c94/session", payload=b"{}", mid=7, qos=1)


def test_ack_follows_successful_handling_and_received_at_is_set_first() -> None:
    calls: list[Any] = []
    client = FakeClient(calls)

    def handle(conn: Any, topic: str, payload: bytes, received_at: datetime) -> Outcome:
        calls.append(("handle", topic, payload, received_at))
        return Outcome.STORED

    def now() -> datetime:
        calls.append(("now",))
        return STAMP

    on_message = make_on_message("CONN", handle=handle, now=now)
    on_message(client, None, _msg())
    assert calls == [
        ("now",),
        ("handle", "rover/288485922c94/session", b"{}", STAMP),
        ("ack", 7, 1),
    ]


def test_handler_failure_exits_with_code_1_without_ack(caplog: pytest.LogCaptureFixture) -> None:
    """AC-18: збій запису — вихід, ack не надсилається, брокер віддасть звіт знову."""
    calls: list[Any] = []

    def handle(conn: Any, topic: str, payload: bytes, received_at: datetime) -> Outcome:
        raise psycopg.OperationalError("db is down")

    on_message = make_on_message("CONN", handle=handle, now=lambda: STAMP)
    with caplog.at_level(logging.ERROR), pytest.raises(SystemExit) as exit_info:
        on_message(FakeClient(calls), None, _msg())
    assert exit_info.value.code == 1
    assert ("ack", 7, 1) not in calls
    assert ("disconnect",) in calls
    assert any(r.getMessage().startswith("event=error") for r in caplog.records)
    assert "secret" not in caplog.text


def test_rejected_and_duplicate_are_acked_too() -> None:
    for outcome in (Outcome.REJECTED, Outcome.DUPLICATE):
        calls: list[Any] = []
        on_message = make_on_message("C", handle=lambda *_a, o=outcome: o, now=lambda: STAMP)
        on_message(FakeClient(calls), None, _msg())
        assert ("ack", 7, 1) in calls


def test_subscribes_to_session_topics_with_qos1_on_every_connect() -> None:
    calls: list[Any] = []
    on_connect = make_on_connect()
    on_connect(FakeClient(calls), None, None, SimpleNamespace(is_failure=False), None)
    on_connect(FakeClient(calls), None, None, SimpleNamespace(is_failure=False), None)
    assert TOPIC_FILTER == "rover/+/session"
    assert calls == [("subscribe", "rover/+/session", 1)] * 2


def test_failed_connect_exits_with_code_1() -> None:
    calls: list[Any] = []
    on_connect = make_on_connect()
    with pytest.raises(SystemExit) as exit_info:
        on_connect(FakeClient(calls), None, None, SimpleNamespace(is_failure=True), None)
    assert exit_info.value.code == 1
    assert not any(c[0] == "subscribe" for c in calls)


def test_wait_for_db_retries_until_available() -> None:
    attempts: list[tuple[str, float]] = []
    sleeps: list[float] = []

    def connect(url: str, timeout_s: float) -> str:
        attempts.append((url, timeout_s))
        if len(attempts) < 3:
            raise psycopg.OperationalError("not yet")
        return "CONN"

    conn = wait_for_db(SETTINGS, connect=connect, sleep=sleeps.append)  # type: ignore[arg-type]
    assert conn == "CONN"
    assert attempts == [(SETTINGS.database_url, 5.0)] * 3
    assert sleeps == [2.0, 2.0]


def test_client_is_persistent_with_fixed_id_and_manual_ack() -> None:
    client = build_client(SETTINGS)
    assert isinstance(client, mqtt.Client)
    assert client._client_id == b"rover-ingest"
    assert client._clean_session is False
    assert client._manual_ack is True
    assert client._protocol == mqtt.MQTTv311
