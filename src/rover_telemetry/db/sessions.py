"""Запис сесій і відхилених повідомлень. Роль `ingest` має лише INSERT (конституція №10)."""

import dataclasses

import psycopg
from psycopg.types.json import Jsonb

from rover_telemetry.domain.report import ParsedSession, Rejection

# Колонки `sessions` = поля ParsedSession 1:1; імена беруться з dataclass, не з вводу.
_SESSION_COLUMNS = [f.name for f in dataclasses.fields(ParsedSession)]
# ON CONFLICT без цілі: будь-який конфлікт — дубль, бо єдине обмеження унікальності — ключ
# (mac, seq) (feature ADR-0005). SELECT не потрібен, тож ролі ingest читати не дозволено.
_INSERT_SESSION = (
    f"INSERT INTO sessions ({', '.join(_SESSION_COLUMNS)}) "
    f"VALUES ({', '.join(['%s'] * len(_SESSION_COLUMNS))}) ON CONFLICT DO NOTHING"
)
_REJECTED_COLUMNS = [f.name for f in dataclasses.fields(Rejection)]
_INSERT_REJECTED = (
    f"INSERT INTO rejected ({', '.join(_REJECTED_COLUMNS)}) "
    f"VALUES ({', '.join(['%s'] * len(_REJECTED_COLUMNS))})"
)


def connect(url: str, timeout_s: float) -> psycopg.Connection:
    """З'єднання з транзакцією, яку завершує викликач: `ack` іде лише після `commit()`."""
    return psycopg.connect(url, connect_timeout=max(1, round(timeout_s)), autocommit=False)


def insert_session(conn: psycopg.Connection, session: ParsedSession) -> bool:
    """`True` — нова сесія, `False` — дубль `(mac, seq)`. COMMIT робить викликач."""
    values = [
        Jsonb(session.payload) if name == "payload" else getattr(session, name)
        for name in _SESSION_COLUMNS
    ]
    return conn.execute(_INSERT_SESSION, values).rowcount == 1


def insert_rejected(conn: psycopg.Connection, rejection: Rejection) -> None:
    """Кожна доставка — окремий запис. COMMIT робить викликач."""
    conn.execute(_INSERT_REJECTED, [getattr(rejection, name) for name in _REJECTED_COLUMNS])
