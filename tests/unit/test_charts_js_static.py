"""Статичні перевірки `charts.js` без браузера: заборонені виклики й доменні числа (SAD §8)."""

import re
from datetime import datetime
from pathlib import Path

import pytest
from charts_helpers import page

from rover_telemetry.domain.dashboard import StoredSession
from rover_telemetry.web import templating

STATIC = Path(templating.__file__).parent / "static"
JS = STATIC / "charts.js"
FORBIDDEN_CALLS = ("innerHTML", "outerHTML", "insertAdjacentHTML", "eval(", "new Function")
FORBIDDEN_NETWORK = ("fetch(", "XMLHttpRequest", "document.write", "WebSocket", "sendBeacon")
# Доменні числа приходять у даних блока (`constants`), у файлі їх немає (SAD §8, конституція №3).
DOMAIN_NUMBERS = (r"\b6\.0\b", r"\b8\.4\b", r"\b190\b", r"\b0\.1382\b", r"\b60\b")


@pytest.fixture(scope="module")
def source() -> str:
    return JS.read_text()


@pytest.mark.parametrize("token", FORBIDDEN_CALLS)
def test_no_html_injection_or_eval(source: str, token: str) -> None:
    assert token not in source


@pytest.mark.parametrize("token", FORBIDDEN_NETWORK)
def test_no_network_or_document_write(source: str, token: str) -> None:
    assert token not in source


@pytest.mark.parametrize("pattern", DOMAIN_NUMBERS)
def test_no_domain_numbers(source: str, pattern: str) -> None:
    assert re.search(pattern, source) is None


def test_no_external_addresses(source: str) -> None:
    assert "http://" not in source and "https://" not in source


def test_no_session_time_wording(source: str) -> None:
    lowered = source.lower()
    assert "час виїзду" not in lowered and "час сесії" not in lowered


def test_axis_is_named_session_number(source: str) -> None:
    assert "Номер сесії" in source


def test_every_block_is_isolated_by_try_catch(source: str) -> None:
    """Збій одного блока не зупиняє інші: `try/catch` стоїть у `startBlock`, що йде по блоку."""
    body = re.search(r"function startBlock\(section\) \{(.*?)\n  \}\n", source, re.S)
    assert body is not None
    assert (
        "try {" in body.group(1)
        and "catch" in body.group(1)
        and "unavailable(section)" in body.group(1)
    )


def test_is_one_iife_with_strict_mode(source: str) -> None:
    body = re.sub(r"\A\s*/\*.*?\*/\s*", "", source, count=1, flags=re.S)  # вступний коментар
    assert body.startswith("(function") and "'use strict'" in source


def test_script_tags_in_page_are_local_and_deferred() -> None:
    def make(**fields: int) -> StoredSession:
        return StoredSession(mac="288485922c94", seq=1, received_at=datetime.now(), **fields)

    html = page([make(voltage_start_mv=7000)])
    empty = page([])

    assert '<script src="/static/echarts.min.js" defer></script>' in html
    assert '<script src="/static/charts.js" defer></script>' in html
    assert html.index("echarts.min.js") < html.index("charts.js")
    assert "charts.js" not in empty  # без блоків з даними скрипти не потрібні
