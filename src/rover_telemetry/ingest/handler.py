"""Обробка одного повідомлення: розбір -> запис -> COMMIT -> результат (feature ADR-0001)."""

import logging
from datetime import UTC, datetime
from enum import StrEnum

import psycopg

from rover_telemetry.db.sessions import insert_rejected, insert_session
from rover_telemetry.domain.report import ParsedSession, parse_report, reject_unstorable

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
    Єдиний виняток — сховище відмовило саме через значення звіту (клас 22, `DataError`): таке
    повідомлення не мине й за повторної доставки, тож воно йде у відхилені, а не зациклює сервіс.
    """
    result = parse_report(topic, payload, received_at)
    if isinstance(result, ParsedSession):
        try:
            outcome = Outcome.STORED if insert_session(conn, result) else Outcome.DUPLICATE
            ids = f"mac={result.mac} seq={result.seq}"
        except (psycopg.DataError, UnicodeEncodeError):
            conn.rollback()
            result = reject_unstorable(topic, payload, received_at)
    if not isinstance(result, ParsedSession):
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
