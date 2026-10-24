"""Блок «Рух і борти»: швидкості, різниця бортів, причини відсутності (AC-10…AC-14)."""

import json
import re
from collections.abc import Callable
from typing import Any

from charts_helpers import manifest_description, page, text_of

from rover_telemetry.domain.dashboard import GapNumber, StoredSession
from rover_telemetry.web import chart_blocks

Factory = Callable[..., StoredSession]
MAC = "288485922c94"
FULL = {
    "moving_ms": 2360,
    "speed_left_avg_rpm": 50.8,
    "speed_left_peak_rpm": 181.9,
    "speed_right_avg_rpm": 45.1,
    "speed_right_peak_rpm": 181.4,
    "speed_imbalance_pct": 1.7,
    "encoders_left": True,
    "encoders_right": True,
}
DIAGNOSTIC = (
    "Різниця бортів — діагностична метрика за прямими ділянками, а не висновок про несправність."
)
MILEAGE = (
    "Без енкодера: пробіг такого виїзду рахувався за одним бортом, а якщо енкодера не було "
    "на обох бортах — пробігу немає."
)


def block_of(html: str) -> str:
    match = re.search(r'data-chart-block="motion".*?</section>', html, re.S)
    assert match is not None
    return match.group(0)


def data_of(html: str) -> dict[str, Any]:
    match = re.search(r'id="chart-data-motion">(.*?)</script>', html, re.S)
    assert match is not None
    data: dict[str, Any] = json.loads(match.group(1))
    return data


def notes_of(html: str) -> list[str]:
    return re.findall(r"<li>(.*?)</li>", block_of(html))


def test_motion_is_registered_third() -> None:
    assert [b.key for b in chart_blocks.BLOCKS] == ["battery", "obstacles", "motion"]


def test_ac14_description_verbatim_and_structure(stored_session: Factory) -> None:
    html = page([stored_session(seq=1, **FULL)])
    block = block_of(html)

    assert manifest_description("Рух і борти") in html.replace("&#39;", "'")
    assert "<h2>Рух і борти</h2>" in block
    assert "<h3>Швидкість бортів, м/с</h3>" in block
    assert "<h3>Різниця бортів, %</h3>" in block
    assert 'data-chart="motion-speed"' in block and 'data-chart="motion-imbalance"' in block
    assert block.count("<noscript>") == 2


def test_ac10_speeds_in_rpm_and_mps(stored_session: Factory) -> None:
    data = data_of(page([stored_session(seq=36, **FULL)]))

    assert data["left"][0]["avg_rpm"] == 50.8 and data["left"][0]["peak_rpm"] == 181.9
    assert data["right"][0]["avg_rpm"] == 45.1
    assert abs(data["left"][0]["avg_mps"] - 50.8 * 0.1382 / 60) < 1e-9
    assert abs(data["right"][0]["peak_mps"] - 181.4 * 0.1382 / 60) < 1e-9
    assert data["constants"]["wheel_circumference_m"] == 0.1382
    assert data["reasons"] == [] and data["no_encoder"] == [None]


def test_ac11_imbalance_direction_labels_and_diagnostic_caption(stored_session: Factory) -> None:
    html = page(
        [
            stored_session(seq=1, **FULL),
            stored_session(seq=2, **{**FULL, "speed_imbalance_pct": -2.5}),
            stored_session(seq=3, **{**FULL, "speed_imbalance_pct": 0.0}),
        ]
    )

    imbalance = data_of(html)["imbalance"]

    assert imbalance[0] == {"pct": 1.7, "faster": "left", "faster_label": "лівий борт швидший"}
    assert imbalance[1] == {"pct": -2.5, "faster": "right", "faster_label": "правий борт швидший"}
    assert imbalance[2] == {"pct": 0.0, "faster": "equal", "faster_label": "борти їхали однаково"}
    assert DIAGNOSTIC in text_of(block_of(html))


def test_diagnostic_caption_only_when_there_is_an_imbalance(stored_session: Factory) -> None:
    html = page([stored_session(seq=1, moving_ms=0)])

    assert DIAGNOSTIC not in text_of(block_of(html))


def test_ac12_not_moving_has_no_zeros_and_one_grouped_note(stored_session: Factory) -> None:
    html = page([stored_session(seq=39, moving_ms=0, encoders_left=True, encoders_right=True)])

    data = data_of(html)

    assert data["left"][0] == {
        "avg_rpm": None,
        "peak_rpm": None,
        "avg_mps": None,
        "peak_mps": None,
    }
    assert data["imbalance"][0] == {"pct": None, "faster": None, "faster_label": None}
    assert {r["code"] for r in data["reasons"]} == {"not_moving"}
    assert notes_of(html) == [
        "Немає даних — виїзд № 39: швидкості й різниця бортів (ровер не їхав)."
    ]


def test_ac12_ac13_no_encoder_note_marker_and_mileage_warning(stored_session: Factory) -> None:
    html = page(
        [
            stored_session(seq=40, **FULL),
            stored_session(
                seq=41,
                moving_ms=2360,
                encoders_left=False,
                encoders_right=True,
                speed_right_avg_rpm=45.1,
                speed_right_peak_rpm=181.4,
            ),
        ]
    )

    data = data_of(html)

    assert data["left"][1]["avg_rpm"] is None and data["right"][1]["avg_rpm"] == 45.1
    assert data["no_encoder"] == [None, "без енкодера: лівий борт"]
    assert data["imbalance"][1]["pct"] is None
    assert notes_of(html) == [
        "Без енкодера — виїзд № 41: лівий борт.",
        "Немає даних — виїзд № 41: швидкість лівого борту (на борту не було енкодера); "
        "різниця бортів (на борту не було енкодера).",
    ]
    assert MILEAGE in text_of(block_of(html))


def test_ac13_both_sides_and_marker_even_when_not_moving(stored_session: Factory) -> None:
    html = page([stored_session(seq=5, moving_ms=0, encoders_left=False, encoders_right=False)])

    assert data_of(html)["no_encoder"] == ["без енкодера: обидва борти"]
    assert "Без енкодера — виїзд № 5: обидва борти." in notes_of(html)
    assert "Немає даних — виїзд № 5: швидкості й різниця бортів (ровер не їхав)." in notes_of(html)


def test_mileage_warning_only_when_some_session_lacks_encoder(stored_session: Factory) -> None:
    html = page([stored_session(seq=1, **FULL)])

    assert "Без енкодера:" not in text_of(block_of(html))


def test_ac12_no_straight_keeps_speeds_and_says_why(stored_session: Factory) -> None:
    html = page([stored_session(seq=7, **{**FULL, "speed_imbalance_pct": None})])

    data = data_of(html)

    assert data["left"][0]["avg_rpm"] == 50.8
    assert data["imbalance"][0]["pct"] is None
    assert [r["code"] for r in data["reasons"]] == ["no_straight"]
    assert notes_of(html) == ["Немає даних — виїзд № 7: різниця бортів (прямої ділянки не було)."]


def test_zero_speed_is_a_value_and_zero_imbalance_is_not_missing(stored_session: Factory) -> None:
    html = page(
        [stored_session(seq=1, **{**FULL, "speed_left_avg_rpm": 0.0, "speed_imbalance_pct": 0.0})]
    )

    data = data_of(html)

    assert data["left"][0]["avg_rpm"] == 0.0 and data["left"][0]["avg_mps"] == 0.0
    assert data["imbalance"][0]["pct"] == 0.0
    assert notes_of(html) == []


def test_gaps_note_and_empty_slots(stored_session: Factory) -> None:
    html = page([stored_session(seq=3, **FULL), stored_session(seq=5, **FULL)], [GapNumber(MAC, 4)])

    data = data_of(html)

    assert [(s["seq"], s["gap"]) for s in data["slots"]] == [(3, False), (4, True), (5, False)]
    assert (
        data["left"][1] is None and data["imbalance"][1] is None and data["no_encoder"][1] is None
    )
    assert notes_of(html) == ["Сесії, що не дійшли: № 4."]


def test_empty_storage() -> None:
    block = block_of(page([]))

    assert 'data-state="empty"' in block and "виїздів ще не збережено" in block
