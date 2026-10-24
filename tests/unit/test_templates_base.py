"""Базовий макет, макроси й опис (AC-02, AC-06, AC-10)."""

from pathlib import Path

import pytest

from rover_telemetry.web import templating

WEB = Path(templating.__file__).parent
FILES = [*(WEB / "templates").glob("*.html"), WEB / "static" / "app.css"]


def render(source: str, **context: object) -> str:
    return templating.make_environment().from_string(source).render(**context)


def test_ac02_description_has_three_definitions() -> None:
    """AC-02: опис пояснює ровер, виїзд і утримання простою мовою."""
    html = render("{% include '_description.html' %}")
    phrases = ("Це дашборд ровера", "Виїзд — один запуск", "Утримання — коли ровер зупиняється")
    for phrase in phrases:
        assert phrase in html


def test_ac06_zero_is_a_number_none_is_no_data() -> None:
    """AC-06: нуль — `0`, `None` — «немає даних» з окремим класом."""
    macro = "{% from '_macros.html' import metric_card %}"
    zero = render(macro + "{{ metric_card('Пробіг', '0 м') }}")
    assert "0 м" in zero and "no-data" not in zero
    bare_zero = render(macro + "{{ metric_card('Виїздів', 0) }}")
    assert ">0<" in bare_zero.replace(" ", "").replace("\n", "") and "no-data" not in bare_zero
    missing = render(macro + "{{ metric_card('Пробіг', None) }}")
    assert 'class="no-data"' in missing and "немає даних" in missing


def test_metric_card_note_and_wide() -> None:
    html = render(
        "{% from '_macros.html' import metric_card %}"
        "{{ metric_card('Л', 'В', note='без даних у 1 з 2', wide=True) }}"
    )
    assert "card--wide" in html and "без даних у 1 з 2" in html


def test_value_is_escaped() -> None:
    html = render(
        "{% from '_macros.html' import metric_card %}{{ metric_card('x', v) }}",
        v="<script>alert(1)</script>",
    )
    assert "<script>" not in html and "&lt;script&gt;" in html


def test_state_message() -> None:
    html = render(
        "{% from '_macros.html' import state_message %}{{ state_message('Дані недоступні') }}"
    )
    assert "Дані недоступні" in html


def test_base_layout_is_mobile_ready() -> None:
    html = render("{% extends 'base.html' %}{% block content %}x{% endblock %}")
    assert '<html lang="uk">' in html
    assert '<meta name="viewport" content="width=device-width, initial-scale=1">' in html
    assert '<link rel="stylesheet" href="/static/app.css">' in html


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_no_external_addresses_scripts_or_inline_styles(path: Path) -> None:
    """CSP `default-src 'self'`: ні зовнішніх адрес, ні скриптів, ні інлайн-стилів."""
    text = path.read_text().lower()
    for forbidden in ("http://", "https://", "@import", "<script", "style="):
        assert forbidden not in text, f"{path.name}: {forbidden}"


def test_css_has_wide_breakpoint_and_touch_target() -> None:
    css = (WEB / "static" / "app.css").read_text()
    assert "@media (min-width: 640px)" in css
    assert "44px" in css
