"""Розбір звіту сесії `rover.session.v1` без I/O (контракт: docs/contracts/events.md)."""

import json
import math
import re
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


EVENT = "rover.session.v1"
SCHEMA_VERSION = 1
MAX_BYTES = 1024  # межа розміру з контракту (docs/contracts/events.md, «Доставка»)
_MAC = re.compile(r"[0-9a-f]{12}")  # контракт: 12 hex, нижній регістр

# Межі типів колонок `sessions` (data-model.md): `integer` — int32, `double precision` — скінченний
# float. Це не бізнес-діапазони (перевірок діапазонів значень немає, AC-05), а відсів того, що
# сховище фізично не прийме: інакше воно б падало без ack і зациклювалось (review F1).
_INT_MIN, _INT_MAX = -(2**31), 2**31 - 1
_NUM_ABS_MAX = 1e300

# Типи відомих полів (контракт); `null` і відсутність дозволені для всіх.
_INT, _NUM, _STR, _BOOL = "int", "number", "string", "bool"
_FIELD_TYPES: dict[tuple[str, ...], str] = {
    ("duration_ms",): _INT,
    ("end_reason",): _STR,
    ("voltage_start_mv",): _INT,
    ("voltage_end_mv",): _INT,
    ("voltage_min_mv",): _INT,
    ("holds", "count"): _INT,
    ("holds", "total_ms"): _INT,
    ("holds", "min_mm"): _INT,
    ("holds", "min_sensor"): _STR,
    ("holds", "by_sensor", "left_front"): _INT,
    ("holds", "by_sensor", "front"): _INT,
    ("holds", "by_sensor", "right_front"): _INT,
    ("holds", "by_sensor", "rear"): _INT,
    ("tof_control_off_ms",): _INT,
    ("moving_ms",): _INT,
    ("distance_cm",): _INT,
    ("speed", "left_avg_rpm"): _NUM,
    ("speed", "left_peak_rpm"): _NUM,
    ("speed", "right_avg_rpm"): _NUM,
    ("speed", "right_peak_rpm"): _NUM,
    ("speed", "imbalance_pct"): _NUM,
    ("encoders", "left"): _BOOL,
    ("encoders", "right"): _BOOL,
    ("fw", "version"): _STR,
    ("fw", "git"): _STR,
    ("fw", "dirty"): _BOOL,
    ("fw", "idf"): _STR,
}
_OBJECTS: tuple[tuple[str, ...], ...] = (
    ("holds",),
    ("holds", "by_sensor"),
    ("speed",),
    ("encoders",),
    ("fw",),
)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_int32(value: Any) -> bool:
    return _is_int(value) and bool(_INT_MIN <= value <= _INT_MAX)


def _is_number(value: Any) -> bool:
    if _is_int(value):
        return bool(abs(value) <= _NUM_ABS_MAX)
    return isinstance(value, float) and math.isfinite(value) and abs(value) <= _NUM_ABS_MAX


def _has_type(value: Any, kind: str) -> bool:
    if kind == _INT:
        return _is_int32(value)
    if kind == _NUM:
        return _is_number(value)
    if kind == _STR:
        return isinstance(value, str)
    return isinstance(value, bool)


def _bad_field_type(doc: dict[str, Any]) -> str | None:
    """Перше відоме поле з неправильним типом (`null` і відсутнє не рахуються), або `None`."""
    for path in _OBJECTS:
        value = _at(doc, *path)
        if value is not None and not isinstance(value, dict):
            return ".".join(path)
    for path, kind in _FIELD_TYPES.items():
        value = _at(doc, *path)
        if value is not None and not _has_type(value, kind):
            return ".".join(path)
    return None


def _reject_constant(name: str) -> Any:
    raise ValueError(f"недопустима константа JSON: {name}")  # NaN, Infinity, -Infinity


def _storable_text(doc: Any) -> bool:
    """`False`, якщо в документі є те, чого jsonb/text не приймають: NUL, одиночний сурогат, ±inf.

    Ітеративно, без рекурсії: глибока вкладеність не має вичерпати стек.
    """
    stack = [doc]
    while stack:
        node = stack.pop()
        if isinstance(node, float):
            if not math.isfinite(node):  # `1e999` json.loads читає як inf, а jsonb його не запише
                return False
        elif isinstance(node, str):
            if "\x00" in node:
                return False
            try:
                node.encode("utf-8")
            except UnicodeEncodeError:
                return False
        elif isinstance(node, dict):
            stack.extend(node.keys())
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
    return True


def _reject(topic: str, payload: bytes, received_at: datetime, code: str, text: str) -> Rejection:
    return Rejection(
        topic=topic,
        reason_code=code,
        reason_text=text,
        raw=payload[:MAX_BYTES],
        raw_size=len(payload),
        raw_truncated=code == "too_large",
        received_at=received_at,
    )


def reject_unstorable(topic: str, payload: bytes, received_at: datetime) -> Rejection:
    """Запобіжник обробника: сховище не прийняло значення, яке розбір пропустив (review F1)."""
    return _reject(topic, payload, received_at, "bad_type", "сховище не прийняло значення звіту")


def _topic_mac(topic: str) -> str | None:
    parts = topic.split("/")
    if len(parts) == 3 and parts[0] == "rover" and parts[2] == "session":
        return parts[1]
    return None


def parse_report(topic: str, payload: bytes, received_at: datetime) -> ParsedSession | Rejection:
    """Розбирає повідомлення; першу ваду за порядком SAD §8 повертає як `Rejection`."""

    def reject(code: str, text: str) -> Rejection:
        return _reject(topic, payload, received_at, code, text)

    if len(payload) > MAX_BYTES:
        return reject("too_large", f"повідомлення більше {MAX_BYTES} байт")
    try:
        doc = json.loads(payload.decode("utf-8"), parse_constant=_reject_constant)
    except (ValueError, RecursionError):  # Unicode/JSONDecodeError — нащадки ValueError
        return reject("not_json", "повідомлення не є коректним JSON у UTF-8")
    if not isinstance(doc, dict):
        return reject("not_json", "JSON не є об'єктом")
    if not _storable_text(doc):
        return reject("not_json", "повідомлення містить символ, який не можна зберегти")
    if doc.get("event") != EVENT:
        return reject("unknown_event", f"невідомий тип події, очікується {EVENT}")
    version = doc.get("schema_version")
    if not _is_int(version) or version != SCHEMA_VERSION:
        return reject("unsupported_schema", "непідтримана версія схеми")
    mac, seq = doc.get("mac"), doc.get("seq")
    if mac is None or seq is None:
        return reject("missing_id", "немає ідентифікатора ровера або номера сесії")
    if not isinstance(mac, str) or not _is_int32(seq):
        return reject("bad_type", "ідентифікатор ровера або номер сесії має неправильний тип")
    if mac != _topic_mac(topic):
        return reject("id_mismatch", "ідентифікатори не збігаються")
    if not _MAC.fullmatch(mac):
        return reject("bad_type", "ідентифікатор ровера має бути 12 hex-символів нижнім регістром")
    bad = _bad_field_type(doc)
    if bad is not None:
        return reject("bad_type", f"поле {bad} має неправильний тип")
    return ParsedSession(
        mac=mac,
        seq=seq,
        schema_version=version,
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
