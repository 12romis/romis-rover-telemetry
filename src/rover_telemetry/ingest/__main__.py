"""Точка входу `python -m rover_telemetry.ingest`: підписник на rover/+/session.

QoS 1, фіксований client id, постійна сесія, manual ack: брокеру підтверджується лише те, що
вже збережено й закомічено. Збій сховища — вихід з кодом 1 без ack (feature ADR-0001).
"""

import logging
import signal
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from types import FrameType
from typing import Any

import paho.mqtt.client as mqtt
import psycopg
from paho.mqtt.enums import CallbackAPIVersion

from rover_telemetry.config import ConfigError, IngestSettings
from rover_telemetry.db.sessions import connect
from rover_telemetry.ingest.handler import handle_message

log = logging.getLogger(__name__)

TOPIC_FILTER = "rover/+/session"


def wait_for_db(
    settings: IngestSettings,
    *,
    connect: Callable[[str, float], psycopg.Connection] = connect,
    sleep: Callable[[float], None] = time.sleep,
) -> psycopg.Connection:
    """Чекає доступності БД до підключення до брокера (ADR-0001), щоб не плодити перезапуски."""
    while True:
        try:
            return connect(settings.database_url, settings.db_connect_timeout_s)
        except psycopg.Error as err:
            log.warning("event=db_wait error=%s", type(err).__name__)
            sleep(settings.db_wait_interval_s)


def make_on_connect() -> Callable[[Any, Any, Any, Any, Any], None]:
    def on_connect(
        client: Any, userdata: Any, flags: Any, reason_code: Any, properties: Any
    ) -> None:
        if reason_code.is_failure:
            log.error("event=error stage=mqtt_connect reason=%s", reason_code)
            raise SystemExit(1)
        # Підписка відновлюється на кожному (пере)підключенні.
        client.subscribe(TOPIC_FILTER, qos=1)

    return on_connect


def make_on_message(
    conn: psycopg.Connection,
    *,
    handle: Callable[[psycopg.Connection, str, bytes, datetime], Any] = handle_message,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> Callable[[Any, Any, Any], None]:
    def on_message(client: Any, userdata: Any, msg: Any) -> None:
        received_at = now()  # першим кроком: верхня межа часу сесії
        try:
            handle(conn, msg.topic, bytes(msg.payload), received_at)
        except Exception as err:
            # Лише тип помилки: тіло повідомлення й паролі в лог не потрапляють.
            log.error("event=error stage=handle error=%s", type(err).__name__)
            client.disconnect()
            raise SystemExit(1) from err
        client.ack(msg.mid, msg.qos)  # лише після COMMIT усередині handle

    return on_message


def build_client(settings: IngestSettings) -> mqtt.Client:
    client = mqtt.Client(
        CallbackAPIVersion.VERSION2,
        client_id=settings.mqtt_client_id,
        protocol=mqtt.MQTTv311,
        clean_session=False,
    )
    client.manual_ack_set(True)
    client.username_pw_set(settings.mqtt_username, settings.mqtt_password)
    return client


def main() -> None:
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(message)s")
    try:
        settings = IngestSettings.from_env()
    except ConfigError as err:
        log.error("event=error stage=config error=%s", err)
        raise SystemExit(1) from err
    conn = wait_for_db(settings)
    client = build_client(settings)
    client.on_connect = make_on_connect()
    client.on_message = make_on_message(conn)

    def stop(signum: int, frame: FrameType | None) -> None:
        # Чисте відключення; непідтверджені повідомлення лишаються в черзі брокера.
        client.disconnect()

    signal.signal(signal.SIGTERM, stop)
    client.connect(settings.mqtt_host, settings.mqtt_port)
    client.loop_forever(retry_first_connection=True)
    conn.close()


if __name__ == "__main__":
    main()
