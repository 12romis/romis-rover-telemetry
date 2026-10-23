"""Міграція застосовується й відкочується на ефемерному Postgres 16 (ADR-0003)."""

from pathlib import Path

import psycopg
import pytest
from yoyo import get_backend, read_migrations

MIGRATIONS = Path(__file__).parents[2] / "migrations"

pytestmark = pytest.mark.integration


def _applied(url: str) -> list[str]:
    with psycopg.connect(url) as conn:
        return [r[0] for r in conn.execute("SELECT migration_id FROM _yoyo_migration")]


def test_apply_and_rollback(postgres_url: str) -> None:
    backend = get_backend(postgres_url.replace("postgresql://", "postgresql+psycopg://"))
    migrations = read_migrations(str(MIGRATIONS))
    assert len(migrations) == 2

    with backend.lock():
        backend.apply_migrations(backend.to_apply(migrations))
    assert _applied(postgres_url) == ["0001_init", "0002_create_sessions"]

    with backend.lock():
        backend.rollback_migrations(backend.to_rollback(migrations))
    assert _applied(postgres_url) == []
