"""Smoke-тест скелета: web віддає /healthz, ingest імпортується."""

import importlib

from fastapi.testclient import TestClient

from rover_telemetry.web.app import app


def test_web_healthz() -> None:
    response = TestClient(app).get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ingest_importable() -> None:
    module = importlib.import_module("rover_telemetry.ingest.__main__")
    assert callable(module.main)
