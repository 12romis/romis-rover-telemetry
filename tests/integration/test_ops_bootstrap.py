"""Скрипт Оператора `ops/bootstrap_db.sh` створює БД `rover` і ролі (sad.md §7, крок 1).

Працює лише з ефемерним контейнером Postgres: ім'я передається через POSTGRES_CONTAINER,
прод-контейнер `postgres` тести не торкаються.
"""

import os
import shutil
import subprocess
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager
from pathlib import Path

import psycopg
import pytest

pytestmark = pytest.mark.integration

SCRIPT = Path(__file__).parents[2] / "ops" / "bootstrap_db.sh"
PASSWORDS = {
    "ROVER_OWNER_PASSWORD": "own'er pw",  # лапка: пароль не повинен ламати SQL
    "ROVER_INGEST_PASSWORD": "ingest-pw",
    "ROVER_VIEWER_PASSWORD": "viewer-pw",
}


@pytest.fixture
def pristine_postgres(
    postgres_factory: Callable[[str], AbstractContextManager[tuple[str, str]]],
) -> Iterator[tuple[str, str]]:
    """Свіжий Postgres без БД `rover` і без ролей: (ім'я контейнера, URL суперкористувача)."""
    with postgres_factory("postgres") as server:
        yield server


def _run(container: str, env_extra: dict[str, str]) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("ROVER_") and k != "HOME"} | {
        "HOME": "/nonexistent",
        "POSTGRES_CONTAINER": container,
        **env_extra,
    }
    return subprocess.run(
        ["bash", str(SCRIPT)], env=env, capture_output=True, text=True, timeout=120, check=False
    )


def _roles(url: str) -> list[str]:
    with psycopg.connect(url) as conn:
        rows = conn.execute(
            "SELECT rolname FROM pg_roles WHERE rolname IN ('owner','ingest','viewer') "
            "ORDER BY rolname"
        ).fetchall()
    return [r[0] for r in rows]


def test_script_has_valid_bash_syntax() -> None:
    assert subprocess.run(["bash", "-n", str(SCRIPT)], check=False).returncode == 0
    if shutil.which("shellcheck"):
        assert subprocess.run(["shellcheck", str(SCRIPT)], check=False).returncode == 0


def _as(url: str, role: str, autocommit: bool = False) -> psycopg.Connection:
    """Підключення до БД rover від імені ролі з паролем із PASSWORDS."""
    host, port = url.split("@", 1)[1].rsplit("/", 1)[0].split(":")
    return psycopg.connect(
        host=host,
        port=int(port),
        dbname="rover",
        user=role,
        password=PASSWORDS[f"ROVER_{role.upper()}_PASSWORD"],
        autocommit=autocommit,
    )


def test_creates_database_and_roles_without_printing_passwords(
    pristine_postgres: tuple[str, str],
) -> None:
    name, url = pristine_postgres
    result = _run(name, PASSWORDS)
    assert result.returncode == 0, result.stderr
    assert _roles(url) == ["ingest", "owner", "viewer"]
    with psycopg.connect(url) as conn:
        row = conn.execute(
            "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname = 'rover'"
        ).fetchone()
    assert row == ("owner",)
    for password in PASSWORDS.values():
        assert password not in result.stdout + result.stderr
    # Паролі справді задано: кожна роль входить у БД rover зі своїм паролем.
    for role in ("owner", "ingest", "viewer"):
        with _as(url, role) as conn:
            assert conn.execute("SELECT current_user").fetchone() == (role,)


def test_owner_can_create_tables_but_roles_have_no_table_rights(
    pristine_postgres: tuple[str, str],
) -> None:
    """Права на таблиці дають міграції, а не скрипт."""
    name, url = pristine_postgres
    assert _run(name, PASSWORDS).returncode == 0
    with _as(url, "owner", autocommit=True) as conn:
        conn.execute("CREATE TABLE t (x int)")
    with _as(url, "viewer") as conn, pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute("SELECT * FROM t")


def test_second_run_changes_nothing_and_succeeds(pristine_postgres: tuple[str, str]) -> None:
    name, url = pristine_postgres
    first = _run(name, PASSWORDS)
    second = _run(name, PASSWORDS)
    assert first.returncode == second.returncode == 0, second.stderr
    assert _roles(url) == ["ingest", "owner", "viewer"]
    assert "вже існує" in second.stdout


@pytest.mark.parametrize("missing", sorted(PASSWORDS))
def test_missing_password_stops_before_creating_anything(
    pristine_postgres: tuple[str, str], missing: str
) -> None:
    name, url = pristine_postgres
    result = _run(name, {k: v for k, v in PASSWORDS.items() if k != missing})
    assert result.returncode != 0
    assert missing in result.stderr
    assert _roles(url) == []
    with psycopg.connect(url) as conn:
        assert conn.execute("SELECT 1 FROM pg_database WHERE datname = 'rover'").fetchone() is None
