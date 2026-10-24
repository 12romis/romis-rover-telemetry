"""Середовище Jinja2 для шаблонів дашборду; автоекранування вимкнути не можна."""

import jinja2

from rover_telemetry.web import formatting


def make_environment() -> jinja2.Environment:
    """Шаблони з пакета; без фільтра `safe` — екранування покладається лише на autoescape."""
    env = jinja2.Environment(
        loader=jinja2.PackageLoader("rover_telemetry.web", "templates"),
        autoescape=True,
        undefined=jinja2.StrictUndefined,
    )
    env.globals.update(
        format_distance_cm=formatting.format_distance_cm,
        format_duration_ms=formatting.format_duration_ms,
        format_voltage_mv=formatting.format_voltage_mv,
        format_received=formatting.format_received,
        end_reason_label=formatting.end_reason_label,
        rover_name=formatting.rover_name,
        format_report=formatting.format_report,
    )
    return env
