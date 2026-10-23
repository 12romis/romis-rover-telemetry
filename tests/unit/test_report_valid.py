"""Розбір валідного звіту в `ParsedSession` (AC-02, AC-10, AC-11, AC-12)."""

import dataclasses
import json
from datetime import UTC, datetime
from typing import Any

import pytest

from rover_telemetry.domain.report import ParsedSession, parse_report

RECEIVED = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)

# Колонка sessions -> шлях поля контракту (крапка = вкладеність).
COLUMNS = {
    "duration_ms": "duration_ms",
    "end_reason": "end_reason",
    "voltage_start_mv": "voltage_start_mv",
    "voltage_end_mv": "voltage_end_mv",
    "voltage_min_mv": "voltage_min_mv",
    "holds_count": "holds.count",
    "holds_total_ms": "holds.total_ms",
    "holds_min_mm": "holds.min_mm",
    "holds_min_sensor": "holds.min_sensor",
    "holds_left_front": "holds.by_sensor.left_front",
    "holds_front": "holds.by_sensor.front",
    "holds_right_front": "holds.by_sensor.right_front",
    "holds_rear": "holds.by_sensor.rear",
    "tof_control_off_ms": "tof_control_off_ms",
    "moving_ms": "moving_ms",
    "distance_cm": "distance_cm",
    "speed_left_avg_rpm": "speed.left_avg_rpm",
    "speed_left_peak_rpm": "speed.left_peak_rpm",
    "speed_right_avg_rpm": "speed.right_avg_rpm",
    "speed_right_peak_rpm": "speed.right_peak_rpm",
    "speed_imbalance_pct": "speed.imbalance_pct",
    "encoders_left": "encoders.left",
    "encoders_right": "encoders.right",
    "fw_version": "fw.version",
    "fw_git": "fw.git",
    "fw_dirty": "fw.dirty",
    "fw_idf": "fw.idf",
}


def _get(doc: dict[str, Any], path: str) -> Any:
    node: Any = doc
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def _parse(report: dict[str, Any]) -> ParsedSession:
    raw = json.dumps(report, separators=(",", ":")).encode()
    result = parse_report(f"rover/{report['mac']}/session", raw, RECEIVED)
    assert isinstance(result, ParsedSession)
    return result


@pytest.mark.parametrize("fixture", ["report_seq26", "report_seq27"])
def test_every_value_matches_the_report(fixture: str, request: pytest.FixtureRequest) -> None:
    """AC-02: кожне значення збереженої сесії збігається зі звітом, без перерахунку."""
    report: dict[str, Any] = request.getfixturevalue(fixture)
    session = _parse(report)
    assert session.mac == report["mac"]
    assert session.seq == report["seq"]
    assert session.schema_version == 1
    assert session.received_at == RECEIVED
    for column, path in COLUMNS.items():
        assert getattr(session, column) == _get(report, path), column


def test_columns_cover_the_dataclass(report_seq26: dict[str, Any]) -> None:
    """Жодного поля ParsedSession поза таблицею відповідності (поле = колонка sessions)."""
    names = {f.name for f in dataclasses.fields(ParsedSession)}
    assert names == set(COLUMNS) | {"mac", "seq", "schema_version", "received_at", "raw", "payload"}


def test_null_is_none_and_zero_is_zero(report_seq26: dict[str, Any]) -> None:
    """AC-10: null не перетворюється на 0, виміряний нуль лишається нулем."""
    report = {**report_seq26, "distance_cm": None, "moving_ms": 0}
    report["speed"] = {**report["speed"], "left_avg_rpm": None}
    report["holds"] = {**report["holds"], "count": 0}
    session = _parse(report)
    assert session.distance_cm is None
    assert session.speed_left_avg_rpm is None
    assert session.moving_ms == 0
    assert session.holds_count == 0
    assert session.holds_min_mm is None


def test_absent_dirty_is_none(report_seq26: dict[str, Any]) -> None:
    report = {**report_seq26, "fw": {"version": "x", "git": "x", "idf": "v6.1"}}
    assert _parse(report).fw_dirty is None


def test_fractional_speed_is_not_rounded(report_seq26: dict[str, Any]) -> None:
    report = {**report_seq26, "speed": {**report_seq26["speed"], "left_avg_rpm": 88.4}}
    assert _parse(report).speed_left_avg_rpm == 88.4


def test_only_received_at_is_a_time_field() -> None:
    """AC-11: часу сесії немає, лише `received_at` (тип datetime)."""
    time_fields = [f.name for f in dataclasses.fields(ParsedSession) if "datetime" in str(f.type)]
    assert time_fields == ["received_at"]


def test_unknown_field_is_kept_in_raw_and_payload(report_seq26: dict[str, Any]) -> None:
    """AC-12: зайве поле не заважає, а вміст зберігається дослівно."""
    report = {**report_seq26, "extra": 1}
    raw = json.dumps(report).encode()
    result = parse_report(f"rover/{report['mac']}/session", raw, RECEIVED)
    assert isinstance(result, ParsedSession)
    assert result.raw == raw
    assert result.payload["extra"] == 1
