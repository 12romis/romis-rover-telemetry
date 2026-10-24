"""Сторінка dashboard.html: опис, вісім карток, стани empty/error (AC-01, AC-07, AC-11)."""

import json
from collections.abc import Callable
from datetime import UTC, datetime
from html.parser import HTMLParser
from typing import Any

from rover_telemetry.domain.dashboard import StoredSession, build_summary
from rover_telemetry.domain.report import ParsedSession, parse_report
from rover_telemetry.domain.timeline import build_timeline
from rover_telemetry.web.templating import make_environment

Factory = Callable[..., StoredSession]
ERROR_TEXT = "Дані тимчасово недоступні. Спробуйте оновити сторінку трохи пізніше."


def stored(report: dict[str, Any], received_at: datetime) -> StoredSession:
    topic = f"rover/{report['mac']}/session"
    parsed = parse_report(topic, json.dumps(report).encode(), received_at)
    assert isinstance(parsed, ParsedSession)
    return StoredSession(
        mac=parsed.mac,
        seq=parsed.seq,
        received_at=parsed.received_at,
        duration_ms=parsed.duration_ms,
        end_reason=parsed.end_reason,
        voltage_start_mv=parsed.voltage_start_mv,
        voltage_end_mv=parsed.voltage_end_mv,
        voltage_min_mv=parsed.voltage_min_mv,
        holds_count=parsed.holds_count,
        moving_ms=parsed.moving_ms,
        distance_cm=parsed.distance_cm,
        fw_version=parsed.fw_version,
        payload=parsed.payload,
    )


def page(sessions: list[StoredSession], gaps: list[Any] | None = None, state: str = "ok") -> str:
    summary = build_summary(sessions, gaps or [])
    items = build_timeline(sessions, gaps or [])
    template = make_environment().get_template("dashboard.html")
    return template.render(state=state, summary=summary, items=items)


def cards(html: str) -> list[str]:
    """Тексти карток у порядку появи: «підпис|значення|підпис під значенням»."""
    out: list[list[str]] = []

    class Parser(HTMLParser):
        cls = ""

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            if tag != "div":  # <em class="no-data"> лишається всередині поточного поля
                return
            self.cls = dict(attrs).get("class") or ""
            if self.cls.split()[:1] == ["card"]:
                out.append(["", "", ""])

        def handle_endtag(self, tag: str) -> None:
            if tag == "div":
                self.cls = ""

        def handle_data(self, data: str) -> None:
            for index, name in enumerate(("card__label", "card__value", "card__note")):
                if self.cls == name and data.strip():
                    out[-1][index] += data.strip()

    Parser().feed(html)
    return ["|".join(c) for c in out]


def test_ac01_eight_cards_in_order(
    report_seq26: dict[str, Any], report_seq27: dict[str, Any]
) -> None:
    """AC-01: вісім карток у порядку таблиці підсумків, зі значеннями з фікстур."""
    html = page(
        [
            stored(report_seq26, datetime(2026, 10, 23, 12, 0, tzinfo=UTC)),
            stored(report_seq27, datetime(2026, 10, 24, 12, 0, tzinfo=UTC)),
        ]
    )
    result = cards(html)
    assert [c.split("|")[0] for c in result] == [
        "Виїздів",
        "Пробіг",
        "Час руху",
        "Утримань перед перешкодою",
        "Кінцева напруга останнього виїзду",
        "Отримано востаннє (за київським часом)",
        "Прошивка останнього виїзду",
        "Втрачені сесії",
    ]
    assert result[0].split("|")[1] == "2"
    assert result[1].split("|")[1] == "0,17 м"
    assert result[2].split("|")[1] == "2,4 с"
    assert result[3].split("|")[1] == "1"
    assert result[4].startswith("Кінцева напруга останнього виїзду|7,68 В")
    assert result[4].endswith("|виїзд № 27")
    assert result[5].split("|")[1] == "24.10.2026 15:00"
    assert result[7].split("|")[1] == "0"  # виміряний нуль втрачених


def test_ac07_partial_missing_note(stored_session: Factory) -> None:
    """AC-07: сума відомих + «без даних у 1 з 3 виїздів»."""
    html = page(
        [
            stored_session(seq=1, distance_cm=0, moving_ms=1000, holds_count=0),
            stored_session(seq=2, distance_cm=50, moving_ms=1000, holds_count=0),
            stored_session(seq=3, moving_ms=1000, holds_count=0),
        ]
    )
    distance = cards(html)[1]
    assert distance == "Пробіг|0,5 м|без даних у 1 з 3 виїздів"
    assert cards(html)[3] == "Утримань перед перешкодою|0|"  # виміряний нуль, не «немає даних»


def test_ac07_nothing_known_is_no_data_without_note(stored_session: Factory) -> None:
    html = page([stored_session(seq=1), stored_session(seq=2)])
    assert cards(html)[1] == "Пробіг|немає даних|"


def test_last_voltage_missing_not_substituted(stored_session: Factory) -> None:
    html = page(
        [stored_session(seq=1, voltage_end_mv=7600), stored_session(seq=2, voltage_end_mv=None)]
    )
    assert cards(html)[4] == "Кінцева напруга останнього виїзду|немає даних|виїзд № 2"


def test_ac11_empty_state() -> None:
    """AC-11: «Виїздів 0» — число; решта — «немає даних»; опис і повідомлення є."""
    html = page([], state="empty")
    result = cards(html)
    assert len(result) == 8
    assert result[0] == "Виїздів|0|"
    assert all("немає даних" in c for c in result[1:])
    assert "Це дашборд ровера" in html
    assert "виїздів ще немає" in html.lower()


def test_ac12_error_state_has_no_cards_or_details() -> None:
    template = make_environment().get_template("dashboard.html")
    html = template.render(state="error", summary=None, items=[])
    assert ERROR_TEXT in html
    assert "Це дашборд ровера" in html
    assert cards(html) == []
    for leak in ("Traceback", "psycopg", "Error"):
        assert leak not in html
