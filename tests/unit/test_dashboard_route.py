"""Маршрут GET /: стани ok/empty/error, лише читання, заголовки безпеки (AC-11, AC-12, AC-13)."""

import hashlib
import logging
from collections.abc import Callable, Iterator
from pathlib import Path

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
    """CSP, nosniff і referrer — скрізь; `no-store` — на всьому, крім `/static` (там `no-cache`)."""
    serve(Snapshot([], []))
    for response in (client.get("/"), client.get("/healthz"), client.get("/static/app.css")):
        for name, value in SECURITY_HEADERS.items():
            if name == "cache-control" and "/static/" in str(response.url):
                continue
            assert response.headers[name] == value, (name, response.url)


def test_static_is_no_cache_with_etag_and_html_stays_no_store(client: TestClient) -> None:
    """AC-21: CSP не змінено; HTML — `no-store`, статика — перевірка за ETag (`no-cache`)."""
    serve(Snapshot([], []))

    page = client.get("/")
    asset = client.get("/static/echarts.min.js")

    assert page.headers["content-security-policy"] == "default-src 'self'"
    assert page.headers["cache-control"] == "no-store"
    assert asset.status_code == 200
    assert asset.headers["cache-control"] == "no-cache"
    assert asset.headers["content-security-policy"] == "default-src 'self'"
    assert asset.headers["etag"]
    assert (
        client.get(
            "/static/echarts.min.js", headers={"If-None-Match": asset.headers["etag"]}
        ).status_code
        == 304
    )


def test_vendored_echarts_matches_sha256_in_vendor_md() -> None:
    """Закріплена копія збігається з хешем у `VENDOR.md`; оновлення перераховує хеш."""
    static = Path(__file__).parents[2] / "src" / "rover_telemetry" / "web" / "static"
    digest = hashlib.sha256((static / "echarts.min.js").read_bytes()).hexdigest()

    vendor = (static / "VENDOR.md").read_text()

    assert digest in vendor
    assert "Apache-2.0" in vendor
    assert (static / "LICENSE-echarts").exists() and (static / "NOTICE-echarts").exists()


def test_static_css_served(client: TestClient) -> None:
    response = client.get("/static/app.css")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/css")
