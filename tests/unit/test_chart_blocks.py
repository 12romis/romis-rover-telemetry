"""Реєстр блоків графіків: ізоляція збою кожного блока, стани, дані (AC-17, AC-19, AC-22)."""

import logging
from collections.abc import Callable, Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from rover_telemetry.db.reading import Snapshot
from rover_telemetry.domain.charts import build_axis
from rover_telemetry.domain.dashboard import GapNumber, StoredSession
from rover_telemetry.web import chart_blocks
from rover_telemetry.web.app import app, load_snapshot
from rover_telemetry.web.chart_blocks import (
    BlockSpec,
    BlockView,
    block_data_shell,
    render_blocks,
)

Factory = Callable[..., StoredSession]
UNAVAILABLE = (
    "Графік тимчасово недоступний. Решта сторінки працює — спробуйте оновити сторінку "
    "трохи пізніше."
)
MAC = "288485922c94"


def _ok(key: str) -> Callable[[Snapshot], BlockView]:
    def build(snapshot: Snapshot) -> BlockView:
        return BlockView("_description.html", {}, {"block": key, "n": len(snapshot.sessions)})

    return build


def _boom(snapshot: Snapshot) -> BlockView:
    raise ValueError("секрет-у-винятку")


def _specs(*failing: str) -> list[BlockSpec]:
    return [
        BlockSpec(key, title, f"Опис {key}.", _boom if key in failing else _ok(key))
        for key, title in (("battery", "Акумулятор"), ("obstacles", "Перешкоди"), ("motion", "Рух"))
    ]


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def serve(snapshot: Snapshot) -> None:
    app.dependency_overrides[load_snapshot] = lambda: snapshot


def test_registry_starts_with_only_known_blocks() -> None:
    assert {spec.key for spec in chart_blocks.BLOCKS} <= {"battery", "obstacles", "motion"}


def test_empty_snapshot_gives_empty_state_without_calling_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def build(snapshot: Snapshot) -> BlockView:
        calls.append("called")
        return BlockView("_description.html", {}, {})

    monkeypatch.setattr(
        chart_blocks, "BLOCKS", [BlockSpec("battery", "Акумулятор", "Опис.", build)]
    )

    blocks = render_blocks(Snapshot([], []))

    assert [(b.key, b.state, b.view) for b in blocks] == [("battery", "empty", None)]
    assert calls == []


def test_ok_state_carries_view_title_and_description(
    monkeypatch: pytest.MonkeyPatch, stored_session: Factory
) -> None:
    monkeypatch.setattr(chart_blocks, "BLOCKS", _specs())

    blocks = render_blocks(Snapshot([stored_session(seq=1)], []))

    assert [(b.key, b.title, b.state) for b in blocks] == [
        ("battery", "Акумулятор", "ok"),
        ("obstacles", "Перешкоди", "ok"),
        ("motion", "Рух", "ok"),
    ]
    assert blocks[0].description == "Опис battery."
    assert blocks[0].view is not None and blocks[0].view.data == {"block": "battery", "n": 1}


@pytest.mark.parametrize("broken", ["battery", "obstacles", "motion"])
def test_failure_of_one_block_is_isolated(
    broken: str,
    monkeypatch: pytest.MonkeyPatch,
    stored_session: Factory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(chart_blocks, "BLOCKS", _specs(broken))

    with caplog.at_level(logging.ERROR, logger="rover_telemetry.web"):
        blocks = render_blocks(Snapshot([stored_session(seq=1)], []))

    states = {b.key: b.state for b in blocks}
    assert states[broken] == "error"
    assert [s for k, s in states.items() if k != broken] == ["ok", "ok"]
    assert f"chart_block_failed block={broken} error_class=ValueError" in caplog.text
    assert "секрет-у-винятку" not in caplog.text
    assert next(b for b in blocks if b.key == broken).view is None


def test_page_survives_failed_block_with_plain_message(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    stored_session: Factory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """AC-19: повідомлення на місці блока, без подробиць; решта сторінки працює."""
    monkeypatch.setattr(chart_blocks, "BLOCKS", _specs("obstacles"))
    serve(Snapshot([stored_session(seq=2), stored_session(seq=4)], [GapNumber(MAC, 3)]))

    with caplog.at_level(logging.ERROR, logger="rover_telemetry.web"):
        response = client.get("/")

    assert response.status_code == 200
    assert response.text.count(UNAVAILABLE) == 1
    assert "секрет-у-винятку" not in response.text and "ValueError" not in response.text
    assert "Підсумки за всі виїзди" in response.text and response.text.count("<details") == 2
    assert 'data-state="error"' in response.text and response.text.count('data-state="ok"') == 2
    assert "chart_block_failed block=obstacles error_class=ValueError" in caplog.text


def test_all_blocks_failing_still_gives_page(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, stored_session: Factory
) -> None:
    monkeypatch.setattr(chart_blocks, "BLOCKS", _specs("battery", "obstacles", "motion"))
    serve(Snapshot([stored_session(seq=1)], []))

    response = client.get("/")

    assert response.status_code == 200
    assert response.text.count(UNAVAILABLE) == 3
    assert "Підсумки за всі виїзди" in response.text and response.text.count("<details") == 1


def test_empty_storage_page_has_three_empty_blocks_and_zero_sessions(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-17: «немає даних» у кожному блоці, підсумки — нуль виїздів як число."""
    monkeypatch.setattr(chart_blocks, "BLOCKS", _specs())
    serve(Snapshot([], []))

    response = client.get("/")

    assert response.status_code == 200
    assert response.text.count('data-state="empty"') == 3
    assert response.text.count("виїздів ще не збережено") == 3
    assert "Підсумки за всі виїзди" in response.text


def test_blocks_stand_between_summary_and_sessions_in_registry_order(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, stored_session: Factory
) -> None:
    monkeypatch.setattr(chart_blocks, "BLOCKS", _specs())
    serve(Snapshot([stored_session(seq=1)], []))

    html = client.get("/").text

    marks = [
        html.index(m)
        for m in (
            "Підсумки за всі виїзди",
            'data-chart-block="battery"',
            'data-chart-block="obstacles"',
            'data-chart-block="motion"',
            'aria-label="Виїзди"',
        )
    ]
    assert marks == sorted(marks)


def test_unregistered_blocks_are_simply_absent(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, stored_session: Factory
) -> None:
    monkeypatch.setattr(chart_blocks, "BLOCKS", [])
    serve(Snapshot([stored_session(seq=1)], []))

    response = client.get("/")

    assert response.status_code == 200 and "data-chart-block" not in response.text


def test_storage_error_page_has_no_blocks(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import psycopg

    monkeypatch.setattr(chart_blocks, "BLOCKS", _specs())

    def broken() -> Snapshot:
        raise psycopg.OperationalError("x")

    app.dependency_overrides[load_snapshot] = broken

    response = client.get("/")

    assert response.status_code == 503 and "data-chart-block" not in response.text


def test_data_shell_slots_gaps_and_constants(stored_session: Factory) -> None:
    sessions = [
        stored_session(seq=3, received_at=datetime(2026, 10, 24, 10, 13, tzinfo=UTC)),
        stored_session(seq=1),
    ]
    axis = build_axis(sessions, [GapNumber(MAC, 2)])

    shell = block_data_shell("battery", axis)

    assert shell["block"] == "battery"
    assert shell["slots"] == [
        {"seq": 1, "gap": False, "received": "23.10.2026 15:00"},
        {"seq": 2, "gap": True, "received": None},
        {"seq": 3, "gap": False, "received": "24.10.2026 13:13"},
    ]
    assert shell["constants"] == {
        "cutoff_v": 6.0,
        "full_charge_v": 8.4,
        "obstacle_threshold_mm": 190,
        "battery_cells": 2,
        "wheel_circumference_m": 0.1382,
    }


def test_page_has_only_get_route_for_page(client: TestClient) -> None:
    serve(Snapshot([], []))
    assert client.post("/").status_code == 405


def _bad_data(snapshot: Snapshot) -> BlockView:
    """Несеріалізовне в JSON значення: `tojson` упав би під час рендеру всієї сторінки."""
    return BlockView("_description.html", {}, {"block": "x", "n": datetime(2026, 10, 24)})


def _bad_template(snapshot: Snapshot) -> BlockView:
    return BlockView("_немає_такого_шаблону.html", {}, {"block": "x"})


@pytest.mark.parametrize("build", [_bad_data, _bad_template])
def test_ac19_render_failure_of_one_block_is_isolated(
    build: Callable[[Snapshot], BlockView],
    monkeypatch: pytest.MonkeyPatch,
    stored_session: Factory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Review F7: ізоляція охоплює рендер вмісту блока й JSON, а не лише `spec.build`."""
    specs = _specs()
    specs[1] = BlockSpec("obstacles", "Перешкоди", "Опис obstacles.", build)
    monkeypatch.setattr(chart_blocks, "BLOCKS", specs)

    with caplog.at_level(logging.ERROR, logger="rover_telemetry.web"):
        blocks = render_blocks(Snapshot([stored_session(seq=1)], []))

    assert {b.key: b.state for b in blocks} == {
        "battery": "ok",
        "obstacles": "error",
        "motion": "ok",
    }
    assert "chart_block_failed block=obstacles" in caplog.text
    assert next(b for b in blocks if b.key == "obstacles").view is None


def test_ac19_page_survives_block_whose_data_cannot_be_serialized(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    stored_session: Factory,
) -> None:
    specs = _specs()
    specs[1] = BlockSpec("obstacles", "Перешкоди", "Опис obstacles.", _bad_data)
    monkeypatch.setattr(chart_blocks, "BLOCKS", specs)
    serve(Snapshot([stored_session(seq=2)], []))

    response = client.get("/")

    assert response.status_code == 200
    assert response.text.count(UNAVAILABLE) == 1
    assert response.text.count('data-state="ok"') == 2
