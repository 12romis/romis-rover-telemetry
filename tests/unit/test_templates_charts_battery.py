"""Блок «Акумулятор» на сторінці: дані для скрипта, примітки, опис (AC-01, AC-03, AC-04, AC-14)."""

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from rover_telemetry.db.reading import Snapshot
from rover_telemetry.domain.dashboard import GapNumber, StoredSession, build_summary
from rover_telemetry.domain.timeline import build_timeline
from rover_telemetry.web import chart_blocks
from rover_telemetry.web.chart_blocks import render_blocks
from rover_telemetry.web.templating import make_environment

Factory = Callable[..., StoredSession]
MAC = "288485922c94"
SCREENS = Path(__file__).parents[2] / "docs" / "features" / "dashboard-charts" / "screens.md"


def manifest_description(title: str) -> str:
    """Копія опису блока з маніфесту екранів без markdown-розмітки (AC-14)."""
    text = SCREENS.read_text()
    marker = text.index(f"**Копія «{title}»")
    quote = next(line for line in text[marker:].splitlines() if line.startswith("> "))
    return quote[2:].replace("**", "")


def page(sessions: list[StoredSession], gaps: list[GapNumber] | None = None) -> str:
    snapshot = Snapshot(sessions, gaps or [])
    return (
        make_environment()
        .get_template("dashboard.html")
        .render(
            state="ok" if sessions else "empty",
            summary=build_summary(sessions, gaps or []),
            items=build_timeline(sessions, gaps or []),
            blocks=render_blocks(snapshot),
        )
    )


def data_of(html: str) -> dict[str, Any]:
    match = re.search(r'id="chart-data-battery">(.*?)</script>', html, re.S)
    assert match is not None
    data: dict[str, Any] = json.loads(match.group(1))
    return data


def notes_of(html: str) -> list[str]:
    block = re.search(r'data-chart-block="battery".*?</section>', html, re.S)
    assert block is not None
    return re.findall(r"<li>(.*?)</li>", block.group(0))


FULL = {"voltage_start_mv": 7691, "voltage_min_mv": 7628, "voltage_end_mv": 7675}


def test_battery_is_first_registered_block() -> None:
    assert chart_blocks.BLOCKS[0].key == "battery"


def test_ac14_description_is_verbatim_from_manifest(stored_session: Factory) -> None:
    html = page([stored_session(seq=1, **FULL)])

    assert manifest_description("Акумулятор") in html.replace("&#39;", "'")
    assert "<h2>Акумулятор</h2>" in html


def test_two_charts_with_subheadings_and_noscript(stored_session: Factory) -> None:
    html = page([stored_session(seq=1, **FULL)])
    block = re.search(r'data-chart-block="battery".*?</section>', html, re.S)
    assert block is not None

    assert "<h3>Напруга по виїздах</h3>" in block.group(0)
    assert "<h3>Просадка</h3>" in block.group(0)
    assert 'data-chart="battery-voltage"' in block.group(0)
    assert 'data-chart="battery-drop"' in block.group(0)
    assert block.group(0).count("<noscript>") == 2


def test_ac01_all_voltages_known(stored_session: Factory) -> None:
    html = page([stored_session(seq=26, **FULL), stored_session(seq=27, **FULL)])

    data = data_of(html)

    assert data["block"] == "battery"
    assert [s["seq"] for s in data["slots"]] == [26, 27]
    assert data["series"] == {"start": [7.691, 7.691], "min": [7.628, 7.628], "end": [7.675, 7.675]}
    assert data["per_cell"]["start"] == [7.691 / 2, 7.691 / 2]
    assert data["drop"] == pytest.approx([0.063, 0.063])
    assert data["reasons"] == []
    assert data["largest_drop_seq"] == 26
    assert data["constants"]["cutoff_v"] == 6.0 and data["constants"]["full_charge_v"] == 8.4
    assert data["constants"]["battery_cells"] == 2
    assert notes_of(html) == []  # підстав для приміток немає — списку немає


def test_ac03_missing_min_is_null_with_reason_and_note(stored_session: Factory) -> None:
    html = page([stored_session(seq=40, voltage_start_mv=7600, voltage_end_mv=7500)])

    data = data_of(html)

    assert data["series"]["min"] == [None] and data["per_cell"]["min"] == [None]
    assert data["drop"] == [None]
    assert data["series"]["start"] == [7.6] and data["series"]["end"] == [7.5]
    codes = {(r["seq"], r["value"], r["code"]) for r in data["reasons"]}
    assert (40, "min", "not_reported") in codes and (40, "drop", "not_reported") in codes
    assert all(r["label"] for r in data["reasons"])
    assert notes_of(html) == [
        "Немає даних — виїзд № 40: мінімальна напруга (просадку не обчислено)."
    ]


def test_ac03_missing_end_note_has_no_drop_suffix(stored_session: Factory) -> None:
    html = page([stored_session(seq=3, voltage_start_mv=7600, voltage_min_mv=7500)])

    assert notes_of(html) == ["Немає даних — виїзд № 3: напруга наприкінці."]
    assert data_of(html)["drop"] == [pytest.approx(0.1)]


def test_ac03_all_missing_never_become_zero(stored_session: Factory) -> None:
    html = page([stored_session(seq=3)])

    data = data_of(html)

    for key in ("start", "min", "end"):
        assert data["series"][key] == [None] and data["per_cell"][key] == [None]
    assert data["drop"] == [None] and data["largest_drop_seq"] is None
    assert len(notes_of(html)) == 3


def test_ac04_only_failsafe_voltage_is_labelled(stored_session: Factory) -> None:
    html = page(
        [
            stored_session(seq=1, end_reason="disarm", **FULL),
            stored_session(seq=2, end_reason="failsafe_voltage", **FULL),
            stored_session(seq=3, end_reason="<script>alert(1)</script>", **FULL),
            stored_session(seq=4, **FULL),
        ]
    )

    data = data_of(html)

    assert data["end_reason_label"] == [None, "Занизька напруга акумулятора", None, None]
    assert "alert(1)" not in html


def test_gaps_are_empty_slots_with_note(stored_session: Factory) -> None:
    html = page(
        [stored_session(seq=3, **FULL), stored_session(seq=6, **FULL)],
        [GapNumber(MAC, 4), GapNumber(MAC, 5)],
    )

    data = data_of(html)

    assert [(s["seq"], s["gap"]) for s in data["slots"]] == [
        (3, False),
        (4, True),
        (5, True),
        (6, False),
    ]
    assert data["series"]["start"][1:3] == [None, None] and data["drop"][1:3] == [None, None]
    assert data["reasons"] == []  # порожній слот — не «немає даних», а «не дійшла»
    assert notes_of(html) == ["Сесії, що не дійшли: № 4, № 5."]


def test_received_is_kyiv_label_and_no_session_time_wording(stored_session: Factory) -> None:
    html = page([stored_session(seq=1, **FULL)])

    assert data_of(html)["slots"][0]["received"] == "23.10.2026 15:00"
    block = re.search(r'data-chart-block="battery".*?</section>', html, re.S)
    assert block is not None
    assert "час виїзду" not in block.group(0).lower() and "час сесії" not in block.group(0).lower()


def test_empty_storage_gives_empty_battery_block() -> None:
    html = page([])

    assert 'data-chart-block="battery" data-state="empty"' in html
    assert "виїздів ще не збережено" in html
