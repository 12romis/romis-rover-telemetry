"""Читання для дашборду: один знімок лише для читання (feature ADR-0001, конституція №10, №11)."""

from dataclasses import dataclass

import psycopg

from rover_telemetry.config import WebSettings
from rover_telemetry.domain.dashboard import GapNumber, StoredSession

# Колонки `sessions` для `StoredSession`; сирий звіт і `rejected` сторінка не читає (SAD §1).
_SESSION_COLUMNS = (
    "mac, seq, received_at, duration_ms, end_reason, voltage_start_mv, voltage_end_mv, "
    "voltage_min_mv, holds_count, moving_ms, distance_cm, fw_version, payload, "
    # Колонки графіків — у кінці, у порядку полів `StoredSession` (позиційне створення).
    "holds_min_mm, holds_min_sensor, holds_left_front, holds_front, holds_right_front, "
    "holds_rear, tof_control_off_ms, speed_left_avg_rpm, speed_left_peak_rpm, "
    "speed_right_avg_rpm, speed_right_peak_rpm, speed_imbalance_pct, encoders_left, "
    "encoders_right"
)
_SELECT_SESSIONS = f"SELECT {_SESSION_COLUMNS} FROM sessions"
_SELECT_GAPS = "SELECT mac, seq FROM session_gaps"


@dataclass(frozen=True)
class Snapshot:
    sessions: list[StoredSession]
    gaps: list[GapNumber]


def open_connection(settings: WebSettings) -> psycopg.Connection:
    """З'єднання на один запит сторінки, без пулу; помилки підключення піднімаються викликачу."""
    return psycopg.connect(
        settings.database_url,
        connect_timeout=max(1, round(settings.db_connect_timeout_s)),
        autocommit=False,
    )


def read_snapshot(conn: psycopg.Connection, statement_timeout_s: float = 5.0) -> Snapshot:
    """Виїзди й номери без виїзду з одного знімка: `REPEATABLE READ` + `READ ONLY`."""
    conn.rollback()  # знімок починається з чистої транзакції; налаштування діють до її кінця
    conn.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
    conn.read_only = True
    try:
        # SET LOCAL не приймає параметрів; значення — число з налаштувань, не ввід користувача.
        conn.execute(f"SET LOCAL statement_timeout = {int(statement_timeout_s * 1000)}")
        sessions = [StoredSession(*row) for row in conn.execute(_SELECT_SESSIONS)]
        gaps = [GapNumber(*row) for row in conn.execute(_SELECT_GAPS)]
    finally:
        conn.rollback()  # знімок нічого не змінює; транзакцію завершуємо відкатом
    return Snapshot(sessions=sessions, gaps=gaps)
