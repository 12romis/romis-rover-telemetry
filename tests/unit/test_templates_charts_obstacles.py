"""Блок «Перешкоди»: схема датчиків, відстань, вимкнений захист (AC-05…AC-09, AC-14)."""

import json
import re
from collections.abc import Callable
from typing import Any

import pytest
from charts_helpers import manifest_description, page, text_of

from rover_telemetry.domain.dashboard import GapNumber, StoredSession
from rover_telemetry.web import chart_blocks

Factory = Callable[..., StoredSession]
MAC = "288485922c94"
HOLDS = {
    "holds_count": 2,
    "holds_min_mm": 103,
    "holds_min_sensor": "front",
    "holds_left_front": 1,
    "holds_front": 2,
    "holds_right_front": 0,
    "holds_rear": 1,
    "tof_control_off_ms": 0,
}
CAPTION = (
    "Число біля датчика — у скількох утриманнях цей датчик на вході бачив перешкоду ближче "
    "за 190 мм. Це спрацювання датчиків, а не утримання: суму чисел не можна читати як "
    "кількість утримань."
)
PROTECTION_WARNING = (
    "За вимкненого захисту від перешкод утримань не буває, тож їх відсутність у такому "
    "виїзді не означає, що перешкод не було."
)


def block_of(html: str) -> str:
    match = re.search(r'data-chart-block="obstacles".*?</section>', html, re.S)
    assert match is not None
    return match.group(0)


def data_of(html: str) -> dict[str, Any]:
    match = re.search(r'id="chart-data-obstacles">(.*?)</script>', html, re.S)
    assert match is not None
    data: dict[str, Any] = json.loads(match.group(1))
    return data


def notes_of(html: str) -> list[str]:
    return re.findall(r"<li>(.*?)</li>", block_of(html))


def test_obstacles_is_registered_after_battery() -> None:
    assert [b.key for b in chart_blocks.BLOCKS][:2] == ["battery", "obstacles"]


def test_ac14_description_verbatim(stored_session: Factory) -> None:
    html = page([stored_session(seq=1, **HOLDS)])

    assert manifest_description("Перешкоди") in html.replace("&#39;", "'")
    assert "<h2>Перешкоди</h2>" in html


def test_block_order_and_headings(stored_session: Factory) -> None:
    block = block_of(page([stored_session(seq=1, **HOLDS)]))

    marks = [
        block.index(m)
        for m in (
            "Спрацювання датчиків за всі виїзди",
            "Утримань усього",
            'data-chart="obstacles-distance"',
            'data-chart="obstacles-control-off"',
        )
    ]
    assert marks == sorted(marks)
    assert "Найменша відстань до перешкоди на вході в утримання, мм" in block
    assert "Захист від перешкод вимкнено, с" in block


def test_ac05_schema_has_four_labelled_sensors_with_counts_as_svg_text(
    stored_session: Factory,
) -> None:
    html = page(
        [
            stored_session(seq=1, **HOLDS),
            stored_session(seq=2, **{**HOLDS, "holds_left_front": 3, "holds_front": 5}),
        ]
    )

    svg = re.search(r"<svg.*?</svg>", block_of(html), re.S)
    assert svg is not None
    text = text_of(svg.group(0))
    for label in ("лівий передній", "передній", "правий передній", "задній"):
        assert label in text
    # лівий передній 1+3=4, передній 2+5=7, правий передній 0, задній 1+1=2
    assert sorted(re.findall(r"<text[^>]*>(\d+)</text>", svg.group(0))) == ["0", "2", "4", "7"]
    assert "style=" not in svg.group(0) and "<script" not in svg.group(0)


def test_ac06_caption_says_sensor_activations_and_no_sum_is_shown(
    stored_session: Factory,
) -> None:
    html = page([stored_session(seq=1, **HOLDS)])

    block = block_of(html)
    assert CAPTION in text_of(block)
    assert "а не утримання" in block
    # сума лічильників (1+2+0+1 = 4) ніде не названа кількістю утримань
    card = re.search(
        r"Утримань усього.*?</div>\s*<div class=\"card__value\">(.*?)</div>", block, re.S
    )
    assert card is not None and text_of(card.group(1)) == "2"  # holds_count, не сума датчиків


def test_ac06_total_holds_card_is_sum_of_holds_count_not_sensor_sum(
    stored_session: Factory,
) -> None:
    sessions = [
        stored_session(seq=1, **{**HOLDS, "holds_count": 3, "holds_front": 9, "holds_rear": 9}),
        stored_session(seq=2, **{**HOLDS, "holds_count": 4}),
        stored_session(seq=3, holds_front=1),  # без holds_count
    ]

    block = block_of(page(sessions))

    value = re.search(r'card__value">(.*?)</div>', block, re.S)
    assert value is not None and text_of(value.group(1)) == "7"
    assert "без даних у 1 з 3 виїздів" in block


def test_schema_no_data_when_no_session_reported_counters(stored_session: Factory) -> None:
    html = page([stored_session(seq=1, holds_count=0)])

    svg = re.search(r"<svg.*?</svg>", block_of(html), re.S)
    assert svg is not None
    assert text_of(svg.group(0)).count("немає даних") == 4
    assert re.findall(r"<text[^>]*>(\d+)</text>", svg.group(0)) == []


def test_ac07_distance_sensor_and_threshold_in_data(stored_session: Factory) -> None:
    html = page(
        [
            stored_session(seq=1, **HOLDS),
            stored_session(seq=2, **{**HOLDS, "holds_min_sensor": "top", "holds_min_mm": 6}),
        ]
    )

    data = data_of(html)

    assert data["block"] == "obstacles"
    assert data["distance_mm"] == [103, 6]
    assert data["sensor"] == ["передній", "Інший датчик"]
    assert data["sensor_raw"] == [None, "top"]  # сире — лише для невідомого, як текст
    assert data["constants"]["obstacle_threshold_mm"] == 190
    assert data["reasons"] == []


def test_ac08_no_holds_is_not_zero_and_not_no_data(stored_session: Factory) -> None:
    html = page(
        [
            stored_session(seq=1, **HOLDS),
            stored_session(seq=39, holds_count=0, tof_control_off_ms=1500),
        ]
    )

    data = data_of(html)

    assert data["distance_mm"] == [103, None]
    assert data["no_holds"] == [False, True]
    assert {
        "seq": 39,
        "value": "distance",
        "code": "no_holds",
        "label": "утримань не було",
    } in data["reasons"]
    assert "Утримань не було — виїзд № 39." in notes_of(html)
    assert not any("Немає даних — виїзд № 39" in n for n in notes_of(html))
    assert data["control_off_s"][1] == 1.5  # секунди лишаються


def test_missing_distance_with_holds_is_no_data_note(stored_session: Factory) -> None:
    html = page([stored_session(seq=40, holds_count=2, tof_control_off_ms=0)])

    data = data_of(html)

    assert data["distance_mm"] == [None] and data["no_holds"] == [False]
    assert data["reasons"][0]["code"] == "not_reported"
    assert notes_of(html) == ["Немає даних — виїзд № 40: відстань до перешкоди (ровер не передав)."]


def test_ac09_zero_seconds_is_a_value_and_missing_is_null(stored_session: Factory) -> None:
    html = page(
        [
            stored_session(seq=1, **HOLDS),  # 0 мс
            stored_session(seq=2, **{**HOLDS, "tof_control_off_ms": None}),
        ]
    )

    data = data_of(html)

    assert data["control_off_s"] == [0.0, None]
    assert any(r["seq"] == 2 and r["value"] == "control_off" for r in data["reasons"])
    assert "Немає даних — виїзд № 2: секунди вимкненого захисту (ровер не передав)." in notes_of(
        html
    )


def test_ac09_warning_only_when_protection_was_off(stored_session: Factory) -> None:
    off = page([stored_session(seq=1, **{**HOLDS, "tof_control_off_ms": 6660})])
    on = page([stored_session(seq=1, **HOLDS)])

    assert PROTECTION_WARNING in text_of(block_of(off))
    assert "За вимкненого захисту" not in block_of(on)


def test_gaps_note_and_empty_slots(stored_session: Factory) -> None:
    html = page(
        [stored_session(seq=3, **HOLDS), stored_session(seq=6, **HOLDS)],
        [GapNumber(MAC, 4), GapNumber(MAC, 5)],
    )

    data = data_of(html)

    assert [(s["seq"], s["gap"]) for s in data["slots"]] == [
        (3, False),
        (4, True),
        (5, True),
        (6, False),
    ]
    assert data["distance_mm"][1:3] == [None, None] and data["control_off_s"][1:3] == [None, None]
    assert "Сесії, що не дійшли: № 4, № 5." in notes_of(html)


def test_empty_storage_has_no_schema_with_zeros() -> None:
    block = block_of(page([]))

    assert 'data-state="empty"' in block and "виїздів ще не збережено" in block
    assert "<svg" not in block


def test_report_strings_never_reach_html_unescaped(stored_session: Factory) -> None:
    evil = "</script><script>alert(1)</script>"
    html = page([stored_session(seq=1, **{**HOLDS, "holds_min_sensor": evil})])

    assert "alert(1)" not in re.sub(r'id="chart-data-obstacles">.*?</script>', "", html, flags=re.S)
    assert data_of(html)["sensor_raw"] == [evil]
    # скрипти на сторінці — лише блоки даних і власні файли `/static/`, інших немає
    allowed = html.count('<script type="application/json"') + html.count('<script src="/static/')
    assert html.count("<script") == allowed


@pytest.mark.parametrize("n", [26, 27])
def test_real_fixtures_render(n: int, stored_session: Factory) -> None:
    r = json.loads(
        (
            __import__("pathlib").Path(__file__).parents[1] / "fixtures" / f"session_seq{n}.json"
        ).read_text()
    )
    holds = r.get("holds") or {}
    by = holds.get("by_sensor") or {}

    html = page(
        [
            stored_session(
                seq=n,
                holds_count=holds.get("count"),
                holds_min_mm=holds.get("min_mm"),
                holds_min_sensor=holds.get("min_sensor"),
                holds_front=by.get("front"),
                tof_control_off_ms=r.get("tof_control_off_ms"),
            )
        ]
    )

    assert data_of(html)["slots"][0]["seq"] == n
