"""Обробка одного повідомлення: розбір -> запис -> COMMIT -> результат (feature ADR-0001)."""

import logging
from datetime import UTC, datetime
from enum import StrEnum

import psycopg

from rover_telemetry.db.sessions import insert_rejected, insert_session
from rover_telemetry.domain.report import ParsedSession, parse_report

log = logging.getLogger(__name__)


class Outcome(StrEnum):
    STORED = "stored"
    DUPLICATE = "duplicate"
    REJECTED = "rejected"


def handle_message(
    conn: psycopg.Connection, topic: str, payload: bytes, received_at: datetime
) -> Outcome:
    """Повертає результат лише після COMMIT, тож викликач підтверджує брокеру після нього.

    Помилку запису чи COMMIT не ловить: вона піднімається, результату (отже й `ack`) немає.
    """
    result = parse_report(topic, payload, received_at)
    if isinstance(result, ParsedSession):
        outcome = Outcome.STORED if insert_session(conn, result) else Outcome.DUPLICATE
        ids = f"mac={result.mac} seq={result.seq}"
    else:
        insert_rejected(conn, result)
        outcome = Outcome.REJECTED
        ids = f"reason_code={result.reason_code}"
    conn.commit()
    latency_ms = round((datetime.now(UTC) - received_at).total_seconds() * 1000)
    # Лише службові поля: вмісту звіту й паролів у лозі немає (SAD §8, Logging).
    log.info(
        "event=%s %s received_at=%s latency_ms=%d",
        outcome,
        ids,
        received_at.isoformat(),
        latency_ms,
    )
    return outcome
