"""Спільні фікстури pytest: реальні звіти ровера та ефемерний Postgres 16."""

import json
import socket
import subprocess
import time
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import psycopg
import pytest
from yoyo import get_backend, read_migrations

FIXTURES = Path(__file__).parent / "fixtures"
POSTGRES_IMAGE = "pgvector/pgvector:pg16"
MIGRATIONS = Path(__file__).parents[1] / "migrations"
# Тестові паролі ролей; реальні створює скрипт Оператора (ops/bootstrap_db.sh).
ROLE_PASSWORD = "test"


def load_report(seq: int) -> dict[str, Any]:
    report: dict[str, Any] = json.loads((FIXTURES / f"session_seq{seq}.json").read_text())
    return report


@pytest.fixture
def report_seq26() -> dict[str, Any]:
    return load_report(26)


@pytest.fixture
def report_seq27() -> dict[str, Any]:
    return load_report(27)


@pytest.fixture(scope="session")
def postgres_server() -> Iterator[tuple[str, str]]:
    """Ефемерний контейнер Postgres 16 на випадковому порту localhost: (ім'я, URL)."""
    name = f"rover-test-{uuid.uuid4().hex[:8]}"
    subprocess.run(
        [
            "docker", "run", "-d", "--rm", "--name", name,
            "-e", "POSTGRES_PASSWORD=test", "-e", "POSTGRES_DB=rover",
            "-p", "127.0.0.1::5432", POSTGRES_IMAGE,
        ],
        check=True,
        capture_output=True,
    )  # fmt: skip
    try:
        port = (
            subprocess.run(
                ["docker", "port", name, "5432/tcp"], check=True, capture_output=True, text=True
            )
            .stdout.splitlines()[0]
            .rsplit(":", 1)[1]
        )
        url = f"postgresql://postgres:test@127.0.0.1:{port}/rover"
        for _ in range(60):
            try:
                psycopg.connect(url, connect_timeout=2).close()
                break
            except psycopg.OperationalError:
                time.sleep(1)
        else:
            raise RuntimeError("Postgres не піднявся за 60 с")
        # Ролі існують до будь-якої міграції: GRANT потребує їх (data-model.md, Test fixtures).
        with psycopg.connect(url, autocommit=True) as conn:
            for role in ("ingest", "viewer"):
                conn.execute(f"CREATE ROLE {role} LOGIN PASSWORD '{ROLE_PASSWORD}'")
        yield name, url
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)


@pytest.fixture(scope="session")
def postgres_url(postgres_server: tuple[str, str]) -> str:
    return postgres_server[1]


@pytest.fixture(scope="session")
def postgres_container(postgres_server: tuple[str, str]) -> str:
    """Ім'я контейнера Postgres (для `docker pause` у наскрізних тестах)."""
    return postgres_server[0]


MOSQUITTO_IMAGE = "eclipse-mosquitto:2"
# Як на проді (sad.md §7): постійні сесії й черга до 1000. Анонімний доступ — лише в тесті.
MOSQUITTO_CONF = """listener 1883
allow_anonymous true
persistence true
persistence_location /mosquitto/data/
max_queued_messages 1000
"""


def _mqtt_ready(port: int) -> bool:
    """Брокер відповідає CONNACK на MQTT 3.1.1 CONNECT (проксі Docker приймає TCP раніше)."""
    connect = b"\x10\x0c\x00\x04MQTT\x04\x02\x00\x3c\x00\x00"
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1) as sock:
            sock.sendall(connect)
            return sock.recv(4)[:2] == b"\x20\x02"
    except OSError:
        return False


@pytest.fixture(scope="session")
def mosquitto_port(tmp_path_factory: pytest.TempPathFactory) -> Iterator[int]:
    """Ефемерний брокер на випадковому порту 127.0.0.1; прод-брокера тести не торкаються."""
    conf = tmp_path_factory.mktemp("mosquitto") / "mosquitto.conf"
    conf.write_text(MOSQUITTO_CONF)
    name = f"rover-mqtt-{uuid.uuid4().hex[:8]}"
    subprocess.run(
        [
            "docker", "run", "-d", "--rm", "--name", name,
            "-v", f"{conf}:/mosquitto/config/mosquitto.conf:ro",
            "-p", "127.0.0.1::1883", MOSQUITTO_IMAGE,
        ],
        check=True,
        capture_output=True,
    )  # fmt: skip
    try:
        port = int(
            subprocess.run(
                ["docker", "port", name, "1883/tcp"], check=True, capture_output=True, text=True
            )
            .stdout.splitlines()[0]
            .rsplit(":", 1)[1]
        )
        for _ in range(60):
            if _mqtt_ready(port):
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("Mosquitto не піднявся за 30 с")
        yield port
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)


def role_url(url: str, role: str, dbname: str) -> str:
    """Рядок підключення до `dbname` від імені ролі `ingest` або `viewer`."""
    host = url.split("@", 1)[1].rsplit("/", 1)[0]
    return f"postgresql://{role}:{ROLE_PASSWORD}@{host}/{dbname}"


@pytest.fixture
def migrated_db(postgres_url: str) -> Iterator[str]:
    """Свіжа БД у спільному контейнері з усіма міграціями; віддає URL власника (postgres)."""
    dbname = f"t_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(postgres_url, autocommit=True) as conn:
        conn.execute(f"CREATE DATABASE {dbname}")
    base = postgres_url.rsplit("/", 1)[0]
    url = f"{base}/{dbname}"
    backend = get_backend(url.replace("postgresql://", "postgresql+psycopg://"))
    with backend.lock():
        backend.apply_migrations(backend.to_apply(read_migrations(str(MIGRATIONS))))
    yield url
    with psycopg.connect(postgres_url, autocommit=True) as conn:
        conn.execute(f"DROP DATABASE {dbname} WITH (FORCE)")


@pytest.fixture
def ingest_url(migrated_db: str) -> str:
    """Рядок підключення до `migrated_db` від ролі `ingest` (лише INSERT)."""
    return role_url(migrated_db, "ingest", migrated_db.rsplit("/", 1)[1])


@pytest.fixture
def viewer_url(migrated_db: str) -> str:
    """Рядок підключення до `migrated_db` від ролі `viewer` (лише SELECT)."""
    return role_url(migrated_db, "viewer", migrated_db.rsplit("/", 1)[1])
