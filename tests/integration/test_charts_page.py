"""Графіки наскрізно на реальному Postgres: свіжість, дубль, відхилене, `null`, лише читання.

Сценарій на живому сховищі (сесії 36–39, лише читання, роль `viewer`), що НЕ входить у набір:
    python - <<'PY'   # з `DASHBOARD_DATABASE_URL` ролі viewer у середовищі
    from rover_telemetry.config import WebSettings
    from rover_telemetry.db.reading import open_connection, read_snapshot
    from rover_telemetry.web.chart_blocks import render_blocks
    with open_connection(WebSettings.from_env()) as c:
        for b in render_blocks(read_snapshot(c)):
            print(b.key, b.state, b.view and b.view.data)
    PY
і звірити ряди з `docs/features/dashboard-charts/screens.md`: сесія 39 без руху — `not_moving`,
сесія 36 — відстань 6 мм як у звіті. Результат записується у `ship`.
"""

import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from rover_telemetry.db.sessions import connect, insert_rejected
from rover_telemetry.domain.report import Rejection

pytestmark = pytest.mark.integration

MAC = "288485922c94"
BLOCKS = ("battery", "obstacles", "motion")


def block_data(html: str, key: str) -> dict[str, Any]:
    match = re.search(rf'id="chart-data-{key}">(.*?)</script>', html, re.S)
    assert match is not None, key
    data: dict[str, Any] = json.loads(match.group(1))
    return data


def seqs(html: str, key: str) -> list[int]:
    return [slot["seq"] for slot in block_data(html, key)["slots"]]


def summary_sessions(html: str) -> str:
    """Значення картки «Виїздів» у підсумках (AC-22: той самий набір, що й у графіках)."""
    match = re.search(
        r'card__label">Виїздів</div>\s*<div class="card__value">(.*?)</div>', html, re.S
    )
    assert match is not None
    return re.sub(r"<[^>]+>", "", match.group(1)).strip()


def test_ac17_empty_storage_three_empty_blocks_and_zero_sessions(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.text.count('data-state="empty"') == 3
    assert response.text.count("виїздів ще не збережено") == 3
    assert "application/json" not in response.text
    card = re.search(r'Виїздів</div>\s*<div class="card__value">(.*?)</div>', response.text, re.S)
    assert card is not None and re.sub(r"<[^>]+>", "", card.group(1)).strip() == "0"


def test_ac22_new_session_is_in_every_block_and_summary_on_refresh(
    client: TestClient,
    store: Callable[..., bool],
    report_seq26: dict[str, Any],
    report_seq27: dict[str, Any],
) -> None:
    store(report_seq26)
    before = client.get("/").text
    assert all(seqs(before, k) == [26] for k in BLOCKS)
    assert summary_sessions(before) == "1"

    store(report_seq27)
    after = client.get("/").text

    assert all(seqs(after, k) == [26, 27] for k in BLOCKS)
    assert summary_sessions(after) == "2"  # підсумки враховують новий виїзд так само, як графіки
    assert after.count("<details") == 2
    assert client.get("/").headers["cache-control"] == "no-store"


def test_ac23_duplicate_and_rejected_add_no_point_and_rejected_number_is_an_empty_slot(
    client: TestClient,
    store: Callable[..., bool],
    ingest_url: str,
    report_seq26: dict[str, Any],
    report_seq27: dict[str, Any],
) -> None:
    store(report_seq26)
    store(report_seq27, seq=28)
    assert store(report_seq26, minute=40) is False  # дубль
    rejection = Rejection(
        f"rover/{MAC}/session", "bad_type", "x", b"{}", 27, False, datetime.now(UTC)
    )
    with connect(ingest_url, timeout_s=5) as conn:
        insert_rejected(conn, rejection)
        conn.commit()

    html = client.get("/").text

    for key in BLOCKS:
        data = block_data(html, key)
        assert [s["seq"] for s in data["slots"]] == [26, 27, 28]
        assert [s["gap"] for s in data["slots"]] == [False, True, False]  # 27 — порожнє місце
    assert html.count("<details") == 2


def test_missing_values_are_null_with_reason_never_zero(
    client: TestClient, store: Callable[..., bool]
) -> None:
    """Порожній звіт: у даних усіх блоків `null` + причина; число 0 нічого не заміщує."""
    store({"event": "rover.session.v1", "schema_version": 1, "mac": MAC}, seq=1)

    html = client.get("/").text

    battery = block_data(html, "battery")
    assert battery["series"] == {"start": [None], "min": [None], "end": [None]}
    assert battery["drop"] == [None] and battery["largest_drop_seq"] is None
    obstacles = block_data(html, "obstacles")
    assert obstacles["distance_mm"] == [None] and obstacles["control_off_s"] == [None]
    motion = block_data(html, "motion")
    assert motion["left"][0] == {
        "avg_rpm": None,
        "peak_rpm": None,
        "avg_mps": None,
        "peak_mps": None,
    }
    assert motion["imbalance"][0]["pct"] is None
    for data in (battery, obstacles, motion):
        assert data["reasons"], data["block"]
        assert all(r["code"] and r["label"] for r in data["reasons"])


def test_real_fixtures_give_measured_values(
    client: TestClient,
    store: Callable[..., bool],
    report_seq26: dict[str, Any],
    report_seq27: dict[str, Any],
) -> None:
    store(report_seq26)
    store(report_seq27)

    html = client.get("/").text

    battery = block_data(html, "battery")
    assert battery["series"]["start"][1] == 7.691 and battery["drop"][1] == pytest.approx(0.063)
    motion = block_data(html, "motion")
    assert motion["left"][1]["avg_rpm"] == 30.6 and motion["imbalance"][1]["pct"] == 1.1
    obstacles = block_data(html, "obstacles")
    assert obstacles["distance_mm"][1] == 103 and obstacles["sensor"][1] == "передній"


def test_ac20_page_cannot_change_data_and_has_no_forms(
    client: TestClient, store: Callable[..., bool], report_seq26: dict[str, Any]
) -> None:
    store(report_seq26)

    for method in ("post", "put", "delete"):
        assert getattr(client, method)("/").status_code == 405
    html = client.get("/").text

    for forbidden in ("<form", "<button", "method="):
        assert forbidden not in html


def test_report_markup_stays_inside_json_and_cannot_close_the_script(
    client: TestClient, store: Callable[..., bool], report_seq27: dict[str, Any]
) -> None:
    evil = "</script><img src=x onerror=alert(1)>"
    report = {**report_seq27, "holds": {**report_seq27["holds"], "min_sensor": evil}}
    store(report)

    html = client.get("/").text

    assert block_data(html, "obstacles")["sensor_raw"] == [evil]
    assert evil not in html  # у сторінці лише екранований `<…` усередині JSON
    assert "<img" not in html
