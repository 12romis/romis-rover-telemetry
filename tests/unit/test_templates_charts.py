"""Макроси блока графіка: стани ok/empty/error, дані лише через `tojson` (AC-17, AC-18, AC-19)."""

import json
import re
from pathlib import Path

from rover_telemetry.web import templating
from rover_telemetry.web.templating import make_environment

TEMPLATES = Path(templating.__file__).parent / "templates"
UNAVAILABLE = (
    "Графік тимчасово недоступний. Решта сторінки працює — спробуйте оновити сторінку "
    "трохи пізніше."
)
IMPORT = "{% from '_macros.html' import chart_block, chart, chart_notes, chart_warning %}"


def render(source: str, **context: object) -> str:
    return make_environment().from_string(IMPORT + source).render(**context)


BLOCK_OK = (
    "{% call chart_block('battery', 'Акумулятор', 'ok', data, 'Опис блока.') %}"
    "{{ chart('voltage', 'Напруга') }}{{ chart_notes(notes) }}{{ chart_warning('Застереження.') }}"
    "{% endcall %}"
)


def test_ok_block_has_title_description_chart_data_and_noscript() -> None:
    html = render(BLOCK_OK, data={"points": [1]}, notes=["Рядок"])

    assert "<h2>Акумулятор</h2>" in html
    assert "Опис блока." in html
    assert "<h3>Напруга</h3>" in html
    assert 'class="chart" data-chart="voltage"' in html
    assert "Графік завантажується…" in html
    noscript = re.search(r"<noscript>(.*?)</noscript>", html, re.S)
    assert noscript is not None and UNAVAILABLE in noscript.group(1)
    assert '<ul class="chart-notes">' in html and "<li>Рядок</li>" in html
    assert 'class="chart-warning"' in html and "Застереження." in html


def test_data_is_embedded_as_json_script_and_roundtrips() -> None:
    html = render(BLOCK_OK, data={"points": [1, None], "name": "ровер"}, notes=[])

    match = re.search(
        r'<script type="application/json" id="chart-data-battery">(.*?)</script>', html, re.S
    )
    assert match is not None
    assert json.loads(match.group(1)) == {"points": [1, None], "name": "ровер"}


def test_data_with_script_close_tag_cannot_break_out() -> None:
    evil = "</script><script>alert(1)</script><b>&'\""
    html = render(BLOCK_OK, data={"x": evil}, notes=[])

    body = re.search(r'id="chart-data-battery">(.*?)</script>', html, re.S)
    assert body is not None
    assert "</script" not in body.group(1) and "<" not in body.group(1)
    assert json.loads(body.group(1))["x"] == evil
    assert html.count("<script") == 1  # лише блок даних


def test_empty_block_keeps_description_and_says_no_data() -> None:
    html = render(
        "{% call chart_block('battery', 'Акумулятор', 'empty', none, 'Опис блока.') %}X"
        "{% endcall %}"
    )

    assert "<h2>Акумулятор</h2>" in html and "Опис блока." in html
    assert "немає даних</em>: виїздів ще не збережено" in html
    assert 'data-chart="' not in html and "application/json" not in html and "X" not in html


def test_error_block_has_only_title_and_plain_message() -> None:
    html = render(
        "{% call chart_block('battery', 'Акумулятор', 'error', none, 'Опис блока.') %}X"
        "{% endcall %}"
    )

    assert "<h2>Акумулятор</h2>" in html and UNAVAILABLE in html
    assert "Опис блока." not in html and 'data-chart="' not in html and "X" not in html
    for technical in ("Traceback", "Error", "/src/", "Exception", "chart_block_failed"):
        assert technical not in html


def test_chart_notes_render_nothing_without_lines_and_escape_text() -> None:
    assert render("{{ chart_notes([]) }}").strip() == ""
    html = render("{{ chart_notes(lines) }}", lines=["<b>x</b>"])
    assert "<b>" not in html and "&lt;b&gt;" in html


def test_macros_do_not_use_safe_filter() -> None:
    for path in TEMPLATES.glob("*.html"):
        assert "|safe" not in path.read_text().replace(" ", ""), path.name


def test_loading_placeholder_is_visible_until_charts_js_replaces_it() -> None:
    """Review F11, screens.md `loading`: заповнювач не під `hidden` і має висоту графіка."""
    html = render(BLOCK_OK, data={"points": [1]}, notes=[])

    tag = re.search(r'<div class="chart"[^>]*>', html)
    assert tag is not None and "hidden" not in tag.group(0)
    assert ".chart[hidden]" not in (TEMPLATES.parent / "static" / "app.css").read_text()


def test_without_script_the_placeholder_is_hidden_by_noscript_stylesheet() -> None:
    """Без скрипта «завантажується…» ховає стиль із `<noscript>` (CSP без inline)."""
    base = (TEMPLATES / "base.html").read_text()
    css = (TEMPLATES.parent / "static" / "no-js.css").read_text()

    assert '<noscript><link rel="stylesheet" href="/static/no-js.css"></noscript>' in base
    assert re.search(r"\.chart\s*\{[^}]*display:\s*none", css)
