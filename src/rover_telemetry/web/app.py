"""Дашборд лише для читання: сторінка «Підсумки + виїзди», `/static`, `/healthz`."""

import logging
from collections.abc import Awaitable, Callable
from functools import lru_cache
from pathlib import Path
from typing import Annotated

import psycopg
from fastapi import Depends, FastAPI, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from rover_telemetry.config import WebSettings
from rover_telemetry.db.reading import Snapshot, open_connection, read_snapshot
from rover_telemetry.domain.dashboard import build_summary
from rover_telemetry.domain.timeline import build_timeline
from rover_telemetry.web.chart_blocks import render_blocks
from rover_telemetry.web.templating import make_environment

logger = logging.getLogger("rover_telemetry.web")

# CSP без inline-скриптів і стилів: сторінка не звертається до сторонніх вузлів (spec §6).
SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'self'",
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}

app = FastAPI(title="romis-rover-telemetry", docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
_templates = make_environment()


@app.middleware("http")
async def security_headers(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    response = await call_next(request)
    response.headers.update(SECURITY_HEADERS)
    if request.url.path.startswith("/static/"):
        # Закріплені файли перевіряються за ETag при кожному відкритті; HTML лишається `no-store`.
        response.headers["Cache-Control"] = "no-cache"
    return response


@lru_cache
def get_settings() -> WebSettings:
    return WebSettings.from_env()  # відсутня змінна — помилка конфігурації, не «сховище недоступне»


def load_snapshot(settings: Annotated[WebSettings, Depends(get_settings)]) -> Snapshot:
    """Один знімок читання на запит; з'єднання закривається завжди."""
    with open_connection(settings) as conn:
        return read_snapshot(conn, settings.db_statement_timeout_s)


def _render(state: str, status_code: int, snapshot: Snapshot | None = None) -> HTMLResponse:
    context: dict[str, object] = {"state": state, "summary": None, "items": [], "blocks": []}
    if snapshot is not None:
        context["summary"] = build_summary(snapshot.sessions, snapshot.gaps)
        context["items"] = build_timeline(snapshot.sessions, snapshot.gaps)
        context["blocks"] = render_blocks(snapshot)
    html = _templates.get_template("dashboard.html").render(**context)
    return HTMLResponse(html, status_code=status_code)


@app.exception_handler(psycopg.Error)
async def storage_unavailable(request: Request, exc: psycopg.Error) -> HTMLResponse:
    # Причина — лише в лог (SAD §8); на сторінку технічних подробиць не потрапляє (AC-12).
    logger.error("dashboard_read_failed error_class=%s error=%s", type(exc).__name__, exc)
    return _render("error", 503)


@app.get("/", response_class=HTMLResponse)
def dashboard(snapshot: Annotated[Snapshot, Depends(load_snapshot)]) -> HTMLResponse:
    return _render("ok" if snapshot.sessions else "empty", 200, snapshot)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
