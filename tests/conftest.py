"""Спільні фікстури pytest: реальні звіти ровера та ефемерний Postgres 16."""

import json
import socket
import subprocess
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from yoyo import get_backend, read_migrations

from rover_telemetry.domain.dashboard import StoredSession

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


@contextmanager
def run_postgres(dbname: str) -> Iterator[tuple[str, str]]:
    """Ефемерний контейнер Postgres 16 на випадковому порту localhost: (ім'я, URL до `dbname`)."""
    name = f"rover-test-{uuid.uuid4().hex[:8]}"
    subprocess.run(
        [
            "docker", "run", "-d", "--rm", "--name", name,
            "-e", "POSTGRES_PASSWORD=test", "-e", f"POSTGRES_DB={dbname}",
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
        url = f"postgresql://postgres:test@127.0.0.1:{port}/{dbname}"
        for _ in range(60):
            try:
                psycopg.connect(url, connect_timeout=2).close()
                break
            except psycopg.OperationalError:
                time.sleep(1)
        else:
            raise RuntimeError("Postgres не піднявся за 60 с")
        yield name, url
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)


@pytest.fixture(scope="session")
def postgres_factory() -> Callable[[str], AbstractContextManager[tuple[str, str]]]:
    """Запускає окремий ефемерний Postgres (для тестів, що потребують чистого сервера)."""
    return run_postgres


@pytest.fixture(scope="session")
def postgres_server() -> Iterator[tuple[str, str]]:
    """Спільний контейнер для тестів БД: база `rover` і ролі `ingest`, `viewer`."""
    with run_postgres("rover") as (name, url):
        # Ролі існують до будь-якої міграції: GRANT потребує їх (data-model.md, Test fixtures).
        with psycopg.connect(url, autocommit=True) as conn:
            for role in ("ingest", "viewer"):
                conn.execute(f"CREATE ROLE {role} LOGIN PASSWORD '{ROLE_PASSWORD}'")
        yield name, url


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


@pytest.fixture
def stored_session() -> Callable[..., StoredSession]:
    """Фабрика виїзду з БД: за замовчуванням усе `None`; поля задаються іменованими аргументами."""
    from datetime import UTC, datetime

    def make(mac: str = "288485922c94", seq: int = 1, **fields: Any) -> StoredSession:
        base: dict[str, Any] = {"received_at": datetime(2026, 10, 23, 12, 0, tzinfo=UTC)}
        return StoredSession(mac=mac, seq=seq, **{**base, **fields})

    return make


# --- Сторінка на реальному Postgres: застосунок під `viewer`, запис — роллю `ingest` ---


@pytest.fixture
def client(viewer_url: str) -> Iterator[TestClient]:
    from rover_telemetry.config import WebSettings
    from rover_telemetry.web.app import app, get_settings

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
    from datetime import UTC, datetime

    from rover_telemetry.db.sessions import connect, insert_session
    from rover_telemetry.domain.report import ParsedSession, parse_report

    mac = "288485922c94"

    def put(report: dict[str, Any], seq: int | None = None, minute: int = 0) -> bool:
        doc = {**report, **({"seq": seq} if seq is not None else {})}
        received = datetime(2026, 10, 23, 12, minute % 60, tzinfo=UTC)
        parsed = parse_report(f"rover/{mac}/session", json.dumps(doc).encode(), received)
        assert isinstance(parsed, ParsedSession)
        with connect(ingest_url, timeout_s=5) as conn:
            created = insert_session(conn, parsed)
            conn.commit()
        return created

    return put
