"""Середовище Jinja2 для шаблонів дашборду; автоекранування вимкнути не можна."""

import jinja2


def make_environment() -> jinja2.Environment:
    """Шаблони з пакета; без фільтра `safe` — екранування покладається лише на autoescape."""
    return jinja2.Environment(
        loader=jinja2.PackageLoader("rover_telemetry.web", "templates"),
        autoescape=True,
        undefined=jinja2.StrictUndefined,
    )
