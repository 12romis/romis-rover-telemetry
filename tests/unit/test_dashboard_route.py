"""Маршрут GET /: стани ok/empty/error, лише читання, заголовки безпеки (AC-11, AC-12, AC-13)."""

import logging
from collections.abc import Callable, Iterator

import psycopg
import pytest
from fastapi.testclient import TestClient

from rover_telemetry.db.reading import Snapshot
from rover_telemetry.domain.dashboard import GapNumber, StoredSession
from rover_telemetry.web.app import app, load_snapshot

Factory = Callable[..., StoredSession]
SECURITY_HEADERS = {
    "content-security-policy": "default-src 'self'",
    "cache-control": "no-store",
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
}
SECRET_ERROR = 'connection to server at "postgres" (172.18.0.2), port 5432 failed: secret-detail'


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def serve(snapshot: Snapshot) -> None:
    app.dependency_overrides[load_snapshot] = lambda: snapshot


def test_ok_page(client: TestClient, stored_session: Factory) -> None:
    serve(Snapshot([stored_session(seq=2), stored_session(seq=4)], [GapNumber("288485922c94", 3)]))

    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.text.count("<details") == 2
    assert "виїзду з цим номером немає" in response.text


def test_ac11_empty_page(client: TestClient) -> None:
    serve(Snapshot([], []))

    response = client.get("/")

    assert response.status_code == 200
    assert "Виїздів ще немає" in response.text
    assert "<details" not in response.text


def test_ac12_storage_down_gives_503_without_details(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    def broken() -> Snapshot:
        raise psycopg.OperationalError(SECRET_ERROR)

    app.dependency_overrides[load_snapshot] = broken
    with caplog.at_level(logging.ERROR):
        response = client.get("/")

    assert response.status_code == 503
    assert "Дані тимчасово недоступні" in response.text
    assert "Це дашборд ровера" in response.text  # опис лишається
    for leak in ("secret-detail", "OperationalError", "172.18.0.2", "psycopg"):
        assert leak not in response.text
    assert "secret-detail" in caplog.text  # повна причина — лише в лозі
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_ac13_no_write_routes(client: TestClient, method: str) -> None:
    serve(Snapshot([], []))
    assert getattr(client, method)("/").status_code == 405


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_docs_disabled(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 404


def test_security_headers_on_every_response(client: TestClient) -> None:
    serve(Snapshot([], []))
    for response in (client.get("/"), client.get("/healthz"), client.get("/static/app.css")):
        for name, value in SECURITY_HEADERS.items():
            assert response.headers[name] == value, (name, response.url)


def test_static_css_served(client: TestClient) -> None:
    response = client.get("/static/app.css")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/css")
