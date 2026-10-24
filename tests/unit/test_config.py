"""Налаштування з середовища: розділені рядки підключення, паролі без значень за замовчуванням."""

import dataclasses

import pytest

from rover_telemetry.config import ConfigError, IngestSettings, WebSettings

INGEST_ENV = {
    "INGEST_DATABASE_URL": "postgresql://ingest:p@postgres:5432/rover",
    "MQTT_USERNAME": "rover-ingest",
    "MQTT_PASSWORD": "secret",
}


def test_ingest_settings_defaults() -> None:
    s = IngestSettings.from_env(INGEST_ENV)
    assert s.database_url == INGEST_ENV["INGEST_DATABASE_URL"]
    assert (s.mqtt_host, s.mqtt_port) == ("mosquitto", 1883)
    assert s.mqtt_client_id == "rover-ingest"  # сталий id потрібен постійній сесії (конст. №7)
    assert s.db_wait_interval_s == 2.0
    assert s.db_connect_timeout_s == 5.0


def test_ingest_settings_overrides() -> None:
    env = {
        **INGEST_ENV,
        "MQTT_HOST": "broker",
        "MQTT_PORT": "8883",
        "MQTT_CLIENT_ID": "rover-ingest-2",
        "DB_WAIT_INTERVAL_S": "0.5",
        "DB_CONNECT_TIMEOUT_S": "3",
    }
    s = IngestSettings.from_env(env)
    assert (s.mqtt_host, s.mqtt_port, s.mqtt_client_id) == ("broker", 8883, "rover-ingest-2")
    assert (s.db_wait_interval_s, s.db_connect_timeout_s) == (0.5, 3.0)


@pytest.mark.parametrize("name", ["INGEST_DATABASE_URL", "MQTT_USERNAME", "MQTT_PASSWORD"])
@pytest.mark.parametrize("how", ["absent", "empty"])
def test_missing_secret_is_a_config_error(name: str, how: str) -> None:
    env = dict(INGEST_ENV)
    if how == "absent":
        del env[name]
    else:
        env[name] = ""
    with pytest.raises(ConfigError, match=name):
        IngestSettings.from_env(env)


def test_web_settings_requires_its_own_url() -> None:
    assert WebSettings.from_env({"WEB_DATABASE_URL": "postgresql://viewer@h/rover"}).database_url
    with pytest.raises(ConfigError, match="WEB_DATABASE_URL"):
        WebSettings.from_env({"INGEST_DATABASE_URL": "x"})


def test_services_do_not_see_each_others_database_url() -> None:
    ingest_fields = {f.name for f in dataclasses.fields(IngestSettings)}
    web_fields = {f.name for f in dataclasses.fields(WebSettings)}
    assert web_fields == {"database_url"}
    assert "mqtt_password" in ingest_fields
    ingest = IngestSettings.from_env({**INGEST_ENV, "WEB_DATABASE_URL": "postgresql://v@h/r"})
    assert "WEB_DATABASE_URL" not in repr(ingest)
    web = WebSettings.from_env({"WEB_DATABASE_URL": "postgresql://v@h/r", **INGEST_ENV})
    assert INGEST_ENV["INGEST_DATABASE_URL"] not in repr(web)


def test_password_is_not_in_repr() -> None:
    assert "secret" not in repr(IngestSettings.from_env(INGEST_ENV))
