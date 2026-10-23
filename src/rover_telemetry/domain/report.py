"""Розбір звіту сесії `rover.session.v1` без I/O (контракт: docs/contracts/events.md)."""

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class ParsedSession:
    """Один валідний звіт; поля 1:1 з колонками `sessions`. `None` = «немає даних»."""

    mac: str
    seq: int
    schema_version: int
    received_at: datetime
    raw: bytes
    payload: dict[str, Any]
    duration_ms: int | None
    end_reason: str | None
    voltage_start_mv: int | None
    voltage_end_mv: int | None
    voltage_min_mv: int | None
    holds_count: int | None
    holds_total_ms: int | None
    holds_min_mm: int | None
    holds_min_sensor: str | None
    holds_left_front: int | None
    holds_front: int | None
    holds_right_front: int | None
    holds_rear: int | None
    tof_control_off_ms: int | None
    moving_ms: int | None
    distance_cm: int | None
    speed_left_avg_rpm: float | None
    speed_left_peak_rpm: float | None
    speed_right_avg_rpm: float | None
    speed_right_peak_rpm: float | None
    speed_imbalance_pct: float | None
    encoders_left: bool | None
    encoders_right: bool | None
    fw_version: str | None
    fw_git: str | None
    fw_dirty: bool | None
    fw_idf: str | None


@dataclass(frozen=True)
class Rejection:
    """Повідомлення, що не стало сесією; зберігається в `rejected`."""

    topic: str
    reason_code: str
    reason_text: str
    raw: bytes
    raw_size: int
    raw_truncated: bool
    received_at: datetime


def _at(doc: dict[str, Any], *path: str) -> Any:
    """Значення за шляхом полів; відсутнє поле й явний `null` дають `None`, нуль лишається 0."""
    node: Any = doc
    for key in path:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node


def parse_report(topic: str, payload: bytes, received_at: datetime) -> ParsedSession | Rejection:
    doc: dict[str, Any] = json.loads(payload)
    return ParsedSession(
        mac=doc["mac"],
        seq=doc["seq"],
        schema_version=doc["schema_version"],
        received_at=received_at,
        raw=payload,
        payload=doc,
        duration_ms=_at(doc, "duration_ms"),
        end_reason=_at(doc, "end_reason"),
        voltage_start_mv=_at(doc, "voltage_start_mv"),
        voltage_end_mv=_at(doc, "voltage_end_mv"),
        voltage_min_mv=_at(doc, "voltage_min_mv"),
        holds_count=_at(doc, "holds", "count"),
        holds_total_ms=_at(doc, "holds", "total_ms"),
        holds_min_mm=_at(doc, "holds", "min_mm"),
        holds_min_sensor=_at(doc, "holds", "min_sensor"),
        holds_left_front=_at(doc, "holds", "by_sensor", "left_front"),
        holds_front=_at(doc, "holds", "by_sensor", "front"),
        holds_right_front=_at(doc, "holds", "by_sensor", "right_front"),
        holds_rear=_at(doc, "holds", "by_sensor", "rear"),
        tof_control_off_ms=_at(doc, "tof_control_off_ms"),
        moving_ms=_at(doc, "moving_ms"),
        distance_cm=_at(doc, "distance_cm"),
        speed_left_avg_rpm=_at(doc, "speed", "left_avg_rpm"),
        speed_left_peak_rpm=_at(doc, "speed", "left_peak_rpm"),
        speed_right_avg_rpm=_at(doc, "speed", "right_avg_rpm"),
        speed_right_peak_rpm=_at(doc, "speed", "right_peak_rpm"),
        speed_imbalance_pct=_at(doc, "speed", "imbalance_pct"),
        encoders_left=_at(doc, "encoders", "left"),
        encoders_right=_at(doc, "encoders", "right"),
        fw_version=_at(doc, "fw", "version"),
        fw_git=_at(doc, "fw", "git"),
        fw_dirty=_at(doc, "fw", "dirty"),
        fw_idf=_at(doc, "fw", "idf"),
    )
