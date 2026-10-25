"""Спільні помічники тестів блоків графіків: сторінка з реєстром і копії описів з маніфесту."""

import re
from pathlib import Path

from rover_telemetry.db.reading import Snapshot
from rover_telemetry.domain.dashboard import GapNumber, StoredSession, build_summary
from rover_telemetry.domain.timeline import build_timeline
from rover_telemetry.web.chart_blocks import render_blocks
from rover_telemetry.web.templating import make_environment

SCREENS = Path(__file__).parents[2] / "docs" / "features" / "dashboard-charts" / "screens.md"


def manifest_description(title: str) -> str:
    """Копія опису блока з маніфесту екранів без markdown-розмітки (AC-14)."""
    text = SCREENS.read_text()
    marker = text.index(f"**Копія «{title}»")
    quote = next(line for line in text[marker:].splitlines() if line.startswith("> "))
    return quote[2:].replace("**", "")


def page(sessions: list[StoredSession], gaps: list[GapNumber] | None = None) -> str:
    snapshot = Snapshot(sessions, gaps or [])
    return (
        make_environment()
        .get_template("dashboard.html")
        .render(
            state="ok" if sessions else "empty",
            summary=build_summary(sessions, gaps or []),
            items=build_timeline(sessions, gaps or []),
            blocks=render_blocks(snapshot),
        )
    )


def text_of(fragment: str) -> str:
    """Видимий текст фрагмента HTML з однаковими пробілами."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", fragment)).strip()
