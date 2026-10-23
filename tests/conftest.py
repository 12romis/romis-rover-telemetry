"""Спільні фікстури pytest: реальні звіти ровера та ефемерний Postgres 16."""

import json
import subprocess
import time
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import psycopg
import pytest

FIXTURES = Path(__file__).parent / "fixtures"
POSTGRES_IMAGE = "pgvector/pgvector:pg16"


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
def postgres_url() -> Iterator[str]:
    """Ефемерний контейнер Postgres 16 на випадковому порту localhost."""
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
        yield url
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
