"""Налаштування з змінних середовища; назви — у `.env.example`, значення — поза git."""

import os
from collections.abc import Mapping
from dataclasses import dataclass, field


class ConfigError(Exception):
    """Обов'язкова змінна середовища не задана або порожня."""


def _required(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "")
    if not value:
        raise ConfigError(f"не задано змінну середовища {name}")
    return value


@dataclass(frozen=True)
class IngestSettings:
    """Налаштування сервісу приймання. Паролів і рядків підключення за замовчуванням немає."""

    database_url: str = field(repr=False)
    mqtt_username: str
    mqtt_password: str = field(repr=False)
    mqtt_host: str
    mqtt_port: int
    # Сталий client id потрібен постійній сесії брокера (конституція №7).
    mqtt_client_id: str
    # Інтервал очікування БД і таймаут підключення — вибір розбиття задач (ADR-0001:
    # «кілька секунд», «менше за keepalive»), а не вимога контракту.
    db_wait_interval_s: float
    db_connect_timeout_s: float

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "IngestSettings":
        env = os.environ if env is None else env
        return cls(
            database_url=_required(env, "INGEST_DATABASE_URL"),
            mqtt_username=_required(env, "MQTT_USERNAME"),
            mqtt_password=_required(env, "MQTT_PASSWORD"),
            mqtt_host=env.get("MQTT_HOST") or "mosquitto",
            mqtt_port=int(env.get("MQTT_PORT") or "1883"),
            mqtt_client_id=env.get("MQTT_CLIENT_ID") or "rover-ingest",
            db_wait_interval_s=float(env.get("DB_WAIT_INTERVAL_S") or "2"),
            db_connect_timeout_s=float(env.get("DB_CONNECT_TIMEOUT_S") or "5"),
        )


@dataclass(frozen=True)
class WebSettings:
    """Налаштування дашборду: рядок підключення ролі `viewer` і таймаути читання."""

    database_url: str = field(repr=False)
    # Таймаути з'єднання й запиту — вибір розбиття задач (SAD §4: менші за таймаут Caddy, щоб
    # недоступне сховище давало повідомлення AC-12, а не зависання), а не вимога специфікації.
    db_connect_timeout_s: float = 3.0
    db_statement_timeout_s: float = 5.0

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "WebSettings":
        env = os.environ if env is None else env
        return cls(
            database_url=_required(env, "WEB_DATABASE_URL"),
            db_connect_timeout_s=float(env.get("WEB_DB_CONNECT_TIMEOUT_S") or "3"),
            db_statement_timeout_s=float(env.get("WEB_DB_STATEMENT_TIMEOUT_S") or "5"),
        )
