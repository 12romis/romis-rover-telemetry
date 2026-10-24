"""Токени `--chart-*` в `app.css`: контраст із тлом картки ≥ 4.5:1 (spec §6, OP-1)."""

import re
from pathlib import Path

import pytest

from rover_telemetry.web import templating

CSS = (Path(templating.__file__).parent / "static" / "app.css").read_text()
MIN_CONTRAST = 4.5  # WCAG AA для тексту; spec §6

REQUIRED = {
    "--chart-start",
    "--chart-min",
    "--chart-end",
    "--chart-drop",
    "--chart-distance",
    "--chart-control-off",
    "--chart-left",
    "--chart-right",
    "--chart-peak",
    "--chart-imbalance",
    "--chart-reference",
    "--chart-gap",
}


def _tokens() -> dict[str, str]:
    root = re.search(r":root\s*{(.*?)}", CSS, re.S)
    assert root is not None
    return dict(re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", root.group(1)))


def _luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))

    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_wcag_contrast_reference_values() -> None:
    assert contrast("#000000", "#ffffff") == pytest.approx(21.0)
    assert contrast("#ffffff", "#ffffff") == pytest.approx(1.0)


def test_all_required_chart_tokens_exist() -> None:
    assert set(_tokens()) >= REQUIRED


def test_chart_height_is_fixed_length() -> None:
    assert re.fullmatch(r"\d+px", _tokens()["--chart-height"])


@pytest.mark.parametrize("name", sorted(REQUIRED))
def test_chart_color_contrasts_with_surface(name: str) -> None:
    tokens = _tokens()
    assert contrast(tokens[name], tokens["--color-surface"]) >= MIN_CONTRAST, name


def test_no_data_color_contrasts_with_surface() -> None:
    tokens = _tokens()
    assert contrast(tokens["--color-no-data"], tokens["--color-surface"]) >= MIN_CONTRAST
