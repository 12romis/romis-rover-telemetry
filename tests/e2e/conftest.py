"""Спільні фікстури браузерних тестів: справжній `app` у потоці, Chromium, збір порушень.

Без встановленого Playwright чи Chromium тести пропускаються (див. маркер `e2e`).
"""

import socket
import threading
import time
from collections.abc import Callable, Iterator
from typing import Any

import pytest
import uvicorn

from rover_telemetry.db.reading import Snapshot
from rover_telemetry.web.app import app, load_snapshot


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture
def base_url() -> Iterator[str]:
    """Справжній `app` (його middleware і заголовки) на вільному порту localhost."""
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.1)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        app.dependency_overrides.clear()


@pytest.fixture
def serve_snapshot(base_url: str) -> Callable[[Snapshot], None]:
    def serve(snapshot: Snapshot) -> None:
        app.dependency_overrides[load_snapshot] = lambda: snapshot

    return serve


@pytest.fixture
def browser() -> Iterator[Any]:
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as p:
        try:
            instance = p.chromium.launch()
        except sync_api.Error as exc:  # браузер не встановлено
            pytest.skip(f"Chromium недоступний: {str(exc).splitlines()[0]}")
        yield instance
        instance.close()
