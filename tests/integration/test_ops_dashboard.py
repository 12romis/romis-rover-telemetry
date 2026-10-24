"""Публікація дашборду: compose без портів з alias rover-web, runbook, скрипт перевірки (AC-15)."""

import json
import os
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

ROOT = Path(__file__).parents[2]
SCRIPT = ROOT / "ops" / "verify_dashboard.sh"
README = (ROOT / "ops" / "README.md").read_text()


def compose_config(file: Path) -> dict[str, dict[str, object]]:
    env = {**os.environ, "WEB_DATABASE_URL": "postgresql://viewer:x@postgres/rover"}
    out = subprocess.run(
        ["docker", "compose", "-f", str(file), "config", "--format", "json"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    ).stdout
    services: dict[str, dict[str, object]] = json.loads(out)["services"]
    return services


def test_web_has_no_published_ports_and_rover_web_alias() -> None:
    """Конституція №12: порти не публікуються; Caddy звертається до alias `rover-web`."""
    web = compose_config(ROOT / "docker-compose.yml")["web"]
    assert not web.get("ports")
    networks = web["networks"]
    assert isinstance(networks, dict)
    assert "rover-web" in networks["infra"]["aliases"]


def test_ingest_has_no_published_ports() -> None:
    assert not compose_config(ROOT / "docker-compose.yml")["ingest"].get("ports")


def run_script(*args: str, compose_file: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "WEB_DATABASE_URL": "postgresql://viewer:x@postgres/rover"}
    if compose_file is not None:
        env["COMPOSE_FILE_PATH"] = str(compose_file)
    return subprocess.run(
        ["bash", str(SCRIPT), *args], capture_output=True, text=True, env=env, cwd=ROOT
    )


def test_script_without_url_checks_local_config_only() -> None:
    result = run_script()
    assert result.returncode == 0, result.stderr


def test_script_fails_when_web_publishes_a_port(tmp_path: Path) -> None:
    bad = tmp_path / "docker-compose.yml"
    bad.write_text(
        "services:\n  web:\n    image: x\n    ports: ['8000:8000']\n"
        "    networks:\n      infra:\n        aliases: [rover-web]\n"
        "networks:\n  infra:\n    external: true\n"
    )
    result = run_script(compose_file=bad)
    assert result.returncode == 1
    assert "порт" in result.stderr


def test_script_rejects_non_https_url() -> None:
    result = run_script("http://rover.example")
    assert result.returncode == 2
    assert "https" in result.stderr


def test_runbook_covers_publication_steps() -> None:
    for needle in (
        "reverse_proxy rover-web:8000",
        "CONNECTION LIMIT",
        "DNS",
        "security review",
        "verify_dashboard.sh",
        "docker stop",  # перевірка ізоляції від приймання (AC-15)
    ):
        assert needle in README, needle
