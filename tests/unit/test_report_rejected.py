"""Відхилення невалідних повідомлень з кодом причини (AC-05, AC-06, AC-07)."""

import copy
import json
from datetime import UTC, datetime
from typing import Any

import pytest

from rover_telemetry.domain.report import ParsedSession, Rejection, parse_report

RECEIVED = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)
MAC = "288485922c94"
TOPIC = f"rover/{MAC}/session"


def _dump(doc: Any) -> bytes:
    return json.dumps(doc, separators=(",", ":")).encode()


def _reject(payload: bytes, topic: str = TOPIC) -> Rejection:
    result = parse_report(topic, payload, RECEIVED)
    assert isinstance(result, Rejection), result
    return result


def _padded(report: dict[str, Any], size: int) -> bytes:
    """Звіт, доповнений зайвим полем до точного розміру в байтах."""
    base = _dump({**report, "pad": ""})
    return _dump({**report, "pad": "x" * (size - len(base))})


def test_too_large(report_seq26: dict[str, Any]) -> None:
    payload = _padded(report_seq26, 1025)
    assert len(payload) == 1025
    rej = _reject(payload)
    assert rej.reason_code == "too_large"
    assert rej.raw == payload[:1024]
    assert rej.raw_size == 1025
    assert rej.raw_truncated is True
    assert rej.received_at == RECEIVED
    assert rej.topic == TOPIC


def test_exactly_1024_bytes_is_accepted(report_seq26: dict[str, Any]) -> None:
    payload = _padded(report_seq26, 1024)
    assert len(payload) == 1024
    assert isinstance(parse_report(TOPIC, payload, RECEIVED), ParsedSession)


def test_too_large_cuts_by_bytes_not_characters(report_seq26: dict[str, Any]) -> None:
    payload = _dump({**report_seq26, "pad": "є" * 600})
    rej = _reject(payload)
    assert rej.reason_code == "too_large"
    assert rej.raw == payload[:1024]
    assert len(rej.raw) == 1024


@pytest.mark.parametrize(
    "payload",
    [b"", b"[1,2]", b"42", b"not json", b'{"a":', b"\xff\xfe{}", b"null"],
)
def test_not_json(payload: bytes) -> None:
    rej = _reject(payload)
    assert rej.reason_code == "not_json"
    assert rej.raw == payload
    assert rej.raw_size == len(payload)
    assert rej.raw_truncated is False
    assert rej.reason_text


@pytest.mark.parametrize("event", ["rover.session.v2", "other", None, 5])
def test_unknown_event(report_seq26: dict[str, Any], event: Any) -> None:
    report = {**report_seq26, "event": event}
    assert _reject(_dump(report)).reason_code == "unknown_event"


def test_missing_event_is_unknown_event(report_seq26: dict[str, Any]) -> None:
    report = {k: v for k, v in report_seq26.items() if k != "event"}
    assert _reject(_dump(report)).reason_code == "unknown_event"


@pytest.mark.parametrize("version", [2, 0, "1", True, 1.0, None])
def test_unsupported_schema_keeps_raw_verbatim(report_seq26: dict[str, Any], version: Any) -> None:
    """AC-07: непідтримана версія; вміст дослівно в межах 1024 байт."""
    payload = _dump({**report_seq26, "schema_version": version})
    rej = _reject(payload)
    assert rej.reason_code == "unsupported_schema"
    assert rej.reason_text == "непідтримана версія схеми"
    assert rej.raw == payload
    assert rej.raw_truncated is False


def test_missing_schema_version_is_unsupported_schema(report_seq26: dict[str, Any]) -> None:
    report = {k: v for k, v in report_seq26.items() if k != "schema_version"}
    assert _reject(_dump(report)).reason_code == "unsupported_schema"


@pytest.mark.parametrize("field", ["mac", "seq"])
@pytest.mark.parametrize("how", ["absent", "null"])
def test_missing_id(report_seq26: dict[str, Any], field: str, how: str) -> None:
    report = copy.deepcopy(report_seq26)
    if how == "absent":
        del report[field]
    else:
        report[field] = None
    assert _reject(_dump(report)).reason_code == "missing_id"


def test_id_mismatch(report_seq26: dict[str, Any]) -> None:
    """AC-06: mac у звіті не збігається з mac у топіку."""
    rej = _reject(_dump(report_seq26), topic="rover/aabbccddeeff/session")
    assert rej.reason_code == "id_mismatch"
    assert rej.reason_text == "ідентифікатори не збігаються"
    assert rej.raw == _dump(report_seq26)


@pytest.mark.parametrize("topic", ["session", "rover/session", f"x/{MAC}/session", ""])
def test_malformed_topic_is_id_mismatch(report_seq26: dict[str, Any], topic: str) -> None:
    assert _reject(_dump(report_seq26), topic=topic).reason_code == "id_mismatch"


@pytest.mark.parametrize(
    ("field", "value"),
    [("seq", "26"), ("seq", True), ("seq", 2.5), ("mac", 123), ("mac", True)],
)
def test_bad_type_of_id_precedes_topic_check(
    report_seq26: dict[str, Any], field: str, value: Any
) -> None:
    report = {**report_seq26, field: value}
    assert _reject(_dump(report)).reason_code == "bad_type"


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("duration_ms",), "4300"),
        (("distance_cm",), 1.5),
        (("end_reason",), 3),
        (("holds",), [1]),
        (("holds", "count"), "0"),
        (("holds", "by_sensor", "front"), True),
        (("holds", "min_sensor"), 5),
        (("speed", "left_avg_rpm"), "88"),
        (("speed", "imbalance_pct"), True),
        (("encoders", "left"), 1),
        (("fw", "dirty"), "false"),
        (("fw", "version"), 7),
        (("fw",), "x"),
    ],
)
def test_bad_type_of_known_field(
    report_seq26: dict[str, Any], path: tuple[str, ...], value: Any
) -> None:
    report = copy.deepcopy(report_seq26)
    node = report
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    assert _reject(_dump(report)).reason_code == "bad_type"


def test_null_and_absent_optional_fields_are_not_rejections(report_seq26: dict[str, Any]) -> None:
    """AC-05: відсутні поля й явні null — не причина відхилення; діапазонів немає."""
    report = {
        k: v
        for k, v in report_seq26.items()
        if k not in {"fw", "speed", "holds", "voltage_min_mv", "end_reason"}
    }
    report["distance_cm"] = None
    report["duration_ms"] = -5
    assert isinstance(parse_report(TOPIC, _dump(report), RECEIVED), ParsedSession)


def test_order_first_failing_check_wins(report_seq26: dict[str, Any]) -> None:
    """Повідомлення з двома вадами дає причину, що першою за порядком SAD §8."""
    both = {**report_seq26, "event": "x", "schema_version": 2}
    assert _reject(_dump(both)).reason_code == "unknown_event"
    both = {**report_seq26, "schema_version": 2}
    del both["mac"]
    assert _reject(_dump(both)).reason_code == "unsupported_schema"
    both = {**report_seq26, "seq": None, "distance_cm": "x"}
    assert _reject(_dump(both), topic="rover/aabbccddeeff/session").reason_code == "missing_id"
    both = {**report_seq26, "distance_cm": "x"}
    assert _reject(_dump(both), topic="rover/aabbccddeeff/session").reason_code == "id_mismatch"
    huge = _padded({**report_seq26, "event": "x"}, 1500)
    assert _reject(huge).reason_code == "too_large"


# Повідомлення, які розбір колись пропускав, а Postgres не приймає: без відсіву на вході ingest
# падав би без ack і зациклювався на одному повідомленні (review F1, AC-05, конституція №7).
@pytest.mark.parametrize(
    "payload",
    [
        b'{"event":"rover.session.v1","schema_version":1,"mac":"288485922c94","seq":1,"x":NaN}',
        b'{"event":"rover.session.v1","schema_version":1,"mac":"288485922c94","seq":1,"x":Infinity}',
        b'{"event":"rover.session.v1","schema_version":1,"mac":"288485922c94","seq":1,"x":-Infinity}',
        b'{"event":"rover.session.v1","schema_version":1,"mac":"288485922c94","seq":1,"x":1e999}',
        b'{"event":"rover.session.v1","schema_version":1,"mac":"288485922c94","seq":1,"x":"\\u0000"}',
        b'{"event":"rover.session.v1","schema_version":1,"mac":"288485922c94","seq":1,"\\u0000":1}',
        b'{"event":"rover.session.v1","schema_version":1,"mac":"288485922c94","seq":1,"x":"\\ud800"}',
        b'{"event":"rover.session.v1","schema_version":1,"mac":"288485922c94","seq":1,"x":[["\\u0000"]]}',
        b"[" * 1000,
        b"[" * 500 + b"]" * 500,
    ],
)
def test_unstorable_content_is_not_json(payload: bytes) -> None:
    rej = _reject(payload)
    assert rej.reason_code == "not_json"
    assert rej.raw == payload


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("seq",), 2**31),
        (("seq",), -(2**31) - 1),
        (("duration_ms",), 2**31),
        (("holds", "count"), 2**40),
        (("speed", "left_avg_rpm"), 1e301),
        (("speed", "left_avg_rpm"), -1e301),
    ],
)
def test_value_that_does_not_fit_its_column_is_bad_type(
    report_seq26: dict[str, Any], path: tuple[str, ...], value: Any
) -> None:
    report = copy.deepcopy(report_seq26)
    node = report
    for key in path[:-1]:
        node = node.setdefault(key, {})
    node[path[-1]] = value
    payload = json.dumps(report).encode()
    assert _reject(payload).reason_code == "bad_type"


@pytest.mark.parametrize("value", [2**31 - 1, -(2**31)])
def test_int32_bounds_are_accepted(report_seq26: dict[str, Any], value: int) -> None:
    report = {**report_seq26, "seq": value}
    topic = f"rover/{MAC}/session"
    assert isinstance(parse_report(topic, _dump(report), RECEIVED), ParsedSession)


@pytest.mark.parametrize(
    "mac", ["XYZ", "288485922C94", "288485922c9", "288485922c944", " 288485922c94"]
)
def test_mac_must_be_12_lowercase_hex(report_seq26: dict[str, Any], mac: str) -> None:
    """Контракт: 12 hex, нижній регістр; навіть якщо топік і звіт збігаються (review F3)."""
    report = {**report_seq26, "mac": mac}
    assert _reject(_dump(report), topic=f"rover/{mac}/session").reason_code == "bad_type"
