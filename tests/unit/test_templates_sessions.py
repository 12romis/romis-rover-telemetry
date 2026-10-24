"""Список виїздів: <details>, позначки пропусків, блок звіту (AC-03, AC-05, AC-06, AC-08, AC-09)."""

import json
from collections.abc import Callable
from datetime import UTC, datetime
from html.parser import HTMLParser
from typing import Any

from rover_telemetry.domain.dashboard import GapNumber, StoredSession, build_summary
from rover_telemetry.domain.report import ParsedSession, parse_report
from rover_telemetry.domain.timeline import build_timeline
from rover_telemetry.web.templating import make_environment

Factory = Callable[..., StoredSession]
LABELS = [
    "Отримано (за київським часом)",
    "Причина завершення",
    "Тривалість",
    "Час руху",
    "Пробіг",
    "Утримань",
    "Напруга на початку",
    "Мінімальна напруга",
    "Напруга наприкінці",
    "Прошивка",
]


def from_report(report: dict[str, Any], received_at: datetime) -> StoredSession:
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


def page(sessions: list[StoredSession], gaps: list[GapNumber] | None = None) -> str:
    gaps = gaps or []
    template = make_environment().get_template("dashboard.html")
    return template.render(
        state="ok",
        summary=build_summary(sessions, gaps),
        items=build_timeline(sessions, gaps),
    )


class Rows(HTMLParser):
    """Збирає <details>: заголовок і пари dt/dd; рахує нерозгортувані позначки."""

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[dict[str, Any]] = []
        self.gaps: list[str] = []
        self._tag = ""
        self._cls = ""
        self._label = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._tag, self._cls = tag, dict(attrs).get("class") or ""
        if tag == "details":
            self.rows.append({"head": "", "fields": {}, "report": ""})
        if tag == "div" and "gap" in self._cls.split():
            self.gaps.append("")

    def handle_endtag(self, tag: str) -> None:
        self._tag = ""

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text:
            return
        if self._tag == "summary":
            self.rows[-1]["head"] += text
        elif self._tag == "dt":
            self._label = text
        elif self._tag in ("dd", "em") and self._label:
            self.rows[-1]["fields"][self._label] = text
        elif self._tag == "pre":
            self.rows[-1]["report"] += data
        elif "gap" in self._cls.split() and self.gaps:
            self.gaps[-1] += text


def rows(html: str) -> Rows:
    parser = Rows()
    parser.feed(html)
    return parser


def test_ac03_ten_fields_per_details_in_seq_order(
    report_seq26: dict[str, Any], report_seq27: dict[str, Any]
) -> None:
    """AC-03: <details> на виїзд, 10 полів, від більшого номера до меншого."""
    received = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)
    html = page(
        [from_report(report_seq26, received), from_report(report_seq27, received)],
    )
    parsed = rows(html)
    heads = [r["head"] for r in parsed.rows]
    assert heads == ["RomisRover · Виїзд № 27", "RomisRover · Виїзд № 26"]
    assert list(parsed.rows[0]["fields"]) == LABELS
    assert parsed.rows[0]["fields"]["Пробіг"] == "0,17 м"
    assert parsed.rows[0]["fields"]["Напруга наприкінці"] == "7,68 В"
    assert parsed.rows[0]["fields"]["Причина завершення"] == "Роззброєння"
    assert html.count("<details") == 2
    assert "<script" not in html


def test_ac06_zero_vs_no_data(stored_session: Factory) -> None:
    """AC-06: виміряний 0 — «0 м», відсутнє — «немає даних»; у звіті — null, не 0."""
    zero = stored_session(seq=2, distance_cm=0, payload={"distance_cm": 0})
    missing = stored_session(
        seq=1, distance_cm=None, voltage_min_mv=None, payload={"distance_cm": None}
    )
    parsed = rows(page([zero, missing]))
    assert parsed.rows[0]["fields"]["Пробіг"] == "0 м"
    assert parsed.rows[1]["fields"]["Пробіг"] == "немає даних"
    assert parsed.rows[1]["fields"]["Мінімальна напруга"] == "немає даних"
    assert parsed.rows[1]["fields"]["Причина завершення"] == "немає даних"  # NULL ≠ «Інша причина»
    assert '"distance_cm": null' in parsed.rows[1]["report"]
    assert '"distance_cm": 0' in parsed.rows[0]["report"]


def test_ac04_unknown_reason_is_other(stored_session: Factory) -> None:
    parsed = rows(page([stored_session(seq=1, end_reason="brand_new")]))
    assert parsed.rows[0]["fields"]["Причина завершення"] == "Інша причина"


def test_ac05_full_report_inside_details(report_seq27: dict[str, Any]) -> None:
    """AC-05: у <details> повний звіт, включно з полями, яких немає в таблиці."""
    html = page([from_report(report_seq27, datetime(2026, 10, 23, 12, 0, tzinfo=UTC))])
    report = rows(html).rows[0]["report"]
    assert json.loads(report) == report_seq27
    assert '"speed"' in report


def test_ac08_ac16_gap_marker_is_not_expandable(stored_session: Factory) -> None:
    """AC-08, AC-16: позначка без <details>, з номером, на своєму місці."""
    mac = "288485922c94"
    html = page(
        [stored_session(mac=mac, seq=3), stored_session(mac=mac, seq=1)],
        [GapNumber(mac, 2)],
    )
    parsed = rows(html)
    assert len(parsed.rows) == 2 and html.count("<details") == 2
    assert parsed.gaps == ["RomisRover · № 2 — виїзду з цим номером немає"]
    assert html.index("Виїзд № 3") < html.index("№ 2 —") < html.index("Виїзд № 1")


def test_ac09_received_label_and_no_session_time(stored_session: Factory) -> None:
    """AC-09: підпис «Отримано (за київським часом)», слів про час виїзду немає."""
    html = page([stored_session(seq=1, received_at=datetime(2026, 10, 25, 12, 0, tzinfo=UTC))])
    assert rows(html).rows[0]["fields"]["Отримано (за київським часом)"] == "25.10.2026 14:00"
    assert "час виїзду" not in html.lower() and "час сесії" not in html.lower()


def test_xss_values_are_escaped(stored_session: Factory) -> None:
    evil = "<script>alert(1)</script>"
    html = page(
        [
            stored_session(
                seq=1,
                fw_version=evil,
                end_reason=evil,
                payload={"fw": {"version": evil}, "x": "</pre><script>alert(2)</script>"},
            )
        ]
    )
    assert "<script" not in html
    assert "&lt;script&gt;" in html
    assert "&lt;/pre&gt;" in html
