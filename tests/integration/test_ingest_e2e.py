"""Наскрізні тести ingest на ефемерних Postgres і Mosquitto (AC-17, AC-18, конституція №7).

Сервіс запускається справжнім процесом `python -m rover_telemetry.ingest`; прод-брокера й
прод-БД тести не торкаються.
"""

import json
import os
import random
import signal
import subprocess
import sys
import time
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import paho.mqtt.client as mqtt
import psycopg
import pytest
from paho.mqtt.enums import CallbackAPIVersion

pytestmark = pytest.mark.integration

MAC = "288485922c94"
TOPIC = f"rover/{MAC}/session"
CATCH_UP_LIMIT_S = 60  # spec §6: наздоганяння черги і самовідновлення


class Ingest:
    """Процес сервісу приймання з журналом у файлі (канал stdout міг би заповнитися)."""

    def __init__(self, env: dict[str, str], log_path: Path) -> None:
        self.log_path = log_path
        self._log = log_path.open("wb")
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "rover_telemetry.ingest"],
            env=env,
            stdout=self._log,
            stderr=subprocess.STDOUT,
        )

    def stop(self) -> int:
        """SIGTERM: чисте відключення, код 0."""
        self.proc.send_signal(signal.SIGTERM)
        return self.proc.wait(timeout=30)

    def kill(self) -> None:
        self.proc.kill()
        self.proc.wait(timeout=30)

    def log(self) -> str:
        return self.log_path.read_text()

    def close(self) -> None:
        if self.proc.poll() is None:
            self.proc.kill()
            self.proc.wait(timeout=30)
        self._log.close()


@pytest.fixture
def start_ingest(
    migrated_db: str, mosquitto_port: int, tmp_path: Path
) -> Iterator[Callable[[], Ingest]]:
    """Фабрика запуску; один client id на тест, щоб постійна сесія переживала перезапуски."""
    client_id = f"test-ingest-{uuid.uuid4().hex[:8]}"
    base = migrated_db.rsplit("@", 1)[1]
    env = {
        **os.environ,
        "INGEST_DATABASE_URL": f"postgresql://ingest:test@{base}",
        "MQTT_HOST": "127.0.0.1",
        "MQTT_PORT": str(mosquitto_port),
        "MQTT_USERNAME": "test",
        "MQTT_PASSWORD": "test",
        "MQTT_CLIENT_ID": client_id,
        "DB_WAIT_INTERVAL_S": "0.5",
        "DB_CONNECT_TIMEOUT_S": "3",
    }
    started: list[Ingest] = []

    def start() -> Ingest:
        ingest = Ingest(env, tmp_path / f"ingest-{len(started)}.log")
        started.append(ingest)
        return ingest

    yield start
    for ingest in started:
        ingest.close()


def _report(template: dict[str, Any], seq: int) -> bytes:
    return json.dumps({**template, "mac": MAC, "seq": seq}, separators=(",", ":")).encode()


def _publish(port: int, payloads: list[bytes]) -> None:
    client = mqtt.Client(CallbackAPIVersion.VERSION2, client_id=f"pub-{uuid.uuid4().hex[:8]}")
    client.connect("127.0.0.1", port)
    client.loop_start()
    try:
        infos = [client.publish(TOPIC, p, qos=1) for p in payloads]
        for info in infos:
            info.wait_for_publish(timeout=30)
            assert info.is_published()
    finally:
        client.loop_stop()
        client.disconnect()


def _seqs(url: str) -> list[int]:
    with psycopg.connect(url) as conn:
        return [r[0] for r in conn.execute("SELECT seq FROM sessions ORDER BY seq")]


def _wait_for(predicate: Callable[[], bool], timeout_s: float, what: str) -> float:
    start = time.monotonic()
    while time.monotonic() - start < timeout_s:
        if predicate():
            return time.monotonic() - start
        time.sleep(0.2)
    raise AssertionError(f"не дочекалися: {what} за {timeout_s} с")


def _subscribed_and_stored(
    ingest: Ingest, port: int, url: str, template: dict[str, Any], seq: int
) -> None:
    """Публікує звіт, поки сервіс не збереже його: доводить, що підписка й сесія брокера діють."""
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        assert ingest.proc.poll() is None, ingest.log()
        _publish(port, [_report(template, seq)])
        try:
            _wait_for(lambda: seq in _seqs(url), 3, f"звіт {seq} збережено")
            return
        except AssertionError:
            continue
    raise AssertionError(f"сервіс не зберіг прогрівний звіт\n{ingest.log()}")


def test_storage_failure_means_no_ack_and_exactly_one_record_after_recovery(
    start_ingest: Callable[[], Ingest],
    migrated_db: str,
    mosquitto_port: int,
    postgres_container: str,
    report_seq26: dict[str, Any],
) -> None:
    """AC-18: БД недоступна -> без ack і вихід 1; після відновлення звіт збережено один раз."""
    first = start_ingest()
    _subscribed_and_stored(first, mosquitto_port, migrated_db, report_seq26, 1)

    subprocess.run(["docker", "pause", postgres_container], check=True, capture_output=True)
    try:
        _publish(mosquitto_port, [_report(report_seq26, 2)])
        _wait_for(lambda: first.proc.poll() is not None, 30, "вихід сервісу при збої БД")
    finally:
        subprocess.run(["docker", "unpause", postgres_container], check=True, capture_output=True)
    assert first.proc.returncode == 1, first.log()
    assert "event=error" in first.log()
    assert _seqs(migrated_db) == [1]

    second = start_ingest()
    _wait_for(lambda: _seqs(migrated_db) == [1, 2], 30, "звіт 2 збережено після відновлення")
    assert second.stop() == 0

    # Звіт підтверджено після збереження: наступний запуск його вже не отримує.
    third = start_ingest()
    time.sleep(5)
    assert _seqs(migrated_db) == [1, 2]
    assert "event=duplicate" not in third.log()
    assert "event=stored" not in third.log()


def test_backlog_of_1000_reports_is_caught_up_within_60s(
    start_ingest: Callable[[], Ingest],
    migrated_db: str,
    mosquitto_port: int,
    report_seq26: dict[str, Any],
) -> None:
    """AC-17: черга збережена, порядок довільний, облік втрат — лише справжній пропуск."""
    first = start_ingest()
    _subscribed_and_stored(first, mosquitto_port, migrated_db, report_seq26, 1)
    assert first.stop() == 0

    missing = 500
    seqs = [s for s in range(2, 1002) if s != missing]
    seqs = seqs[:1000]
    random.Random(17).shuffle(seqs)
    _publish(mosquitto_port, [_report(report_seq26, s) for s in seqs])

    second = start_ingest()
    expected = sorted({1, *seqs})
    elapsed = _wait_for(
        lambda: len(_seqs(migrated_db)) == len(expected), CATCH_UP_LIMIT_S, "1000 звітів збережено"
    )
    assert _seqs(migrated_db) == expected
    assert elapsed <= CATCH_UP_LIMIT_S
    with psycopg.connect(migrated_db) as conn:
        gaps = conn.execute("SELECT seq FROM session_gaps ORDER BY seq").fetchall()
    assert gaps == [(missing,)]
    assert "event=error" not in second.log()


def test_service_continues_within_60s_after_being_killed(
    start_ingest: Callable[[], Ingest],
    migrated_db: str,
    mosquitto_port: int,
    report_seq26: dict[str, Any],
) -> None:
    """Самовідновлення: після аварійного зупинення сервіс продовжує <= 60 с."""
    first = start_ingest()
    _subscribed_and_stored(first, mosquitto_port, migrated_db, report_seq26, 1)
    first.kill()

    _publish(mosquitto_port, [_report(report_seq26, 2)])
    second = start_ingest()
    elapsed = _wait_for(lambda: 2 in _seqs(migrated_db), CATCH_UP_LIMIT_S, "звіт 2 збережено")
    assert elapsed <= CATCH_UP_LIMIT_S
    assert second.proc.poll() is None
    assert _seqs(migrated_db) == [1, 2]
