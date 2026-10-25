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
    # `tojson` для даних графіків: стабільний порядок ключів і без NaN/Infinity (їх не читає
    # `JSON.parse`), тож такі дані — збій блока, а не зламана сторінка.
    env.policies["json.dumps_kwargs"] = {"sort_keys": True, "allow_nan": False}
    env.globals.update(
        format_distance_cm=formatting.format_distance_cm,
        format_duration_ms=formatting.format_duration_ms,
        format_voltage_mv=formatting.format_voltage_mv,
        format_received=formatting.format_received,
        end_reason_label=formatting.end_reason_label,
        rover_name=formatting.rover_name,
        format_report=formatting.format_report,
        absent_reason_label=formatting.absent_reason_label,
        sensor_label=formatting.sensor_label,
        side_label=formatting.side_label,
    )
    return env
