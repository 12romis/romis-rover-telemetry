"""Скрипти запуску: ACL брокера, пробна публікація, перевірка, відкат (AC-13, AC-14, AC-19, AC-20).

Працюють лише з ефемерними Mosquitto і Postgres; прод-брокер і прод-БД тести не торкаються.
"""

import os
import shutil
import subprocess
import uuid
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager
from datetime import UTC, datetime, timedelta
from pathlib import Path

import psycopg
import pytest
from yoyo import get_backend, read_migrations

pytestmark = pytest.mark.integration

OPS = Path(__file__).parents[2] / "ops"
MIGRATIONS = Path(__file__).parents[2] / "migrations"
IMAGE = "eclipse-mosquitto:2"
USERS = ["admin", "RomisRover", "rover-ingest", "rover-viewer"]
# ACL до звуження: як на проді після кроку 3, лише RomisRover ще readwrite rover/#.
ACL_BEFORE = """# admin — повний доступ
user admin
topic readwrite #

# beetroot — тільки простір імен esp32test/
user beetroot
topic readwrite esp32test/#

user RomisRover
topic readwrite rover/#
"""
CONF = """listener 1883
allow_anonymous false
password_file /mosquitto/config/passwd
acl_file /mosquitto/config/acl
persistence true
persistence_location /mosquitto/data/
"""
SESSION_TOPIC = "rover/000000000000/session"
OTHER_TOPIC = "rover/000000000000/other"
DELIVERED, NOT_DELIVERED = 0, 3


def _pw(user: str) -> str:
    return f"pw-{user}"


class Broker:
    def __init__(self, name: str, conf_dir: Path, env_file: Path) -> None:
        self.name, self.conf_dir, self.env_file = name, conf_dir, env_file

    @property
    def env(self) -> dict[str, str]:
        return {
            **os.environ,
            "MOSQUITTO_CONTAINER": self.name,
            "ACL_DIR": str(self.conf_dir),
            "MQTT_ENV_FILE": str(self.env_file),
        }

    def run(
        self, script: str, *args: str, extra: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(OPS / script), *args],
            env={**self.env, **(extra or {})},
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )

    def probe(self, user: str, topic: str, reader: str = "rover-viewer") -> int:
        return self.run(
            "probe_publish.sh", user, topic, extra={"MQTT_PROBE_READER": reader}
        ).returncode

    def sub_debug(self, user: str | None, topic: str) -> str:
        creds = ["-u", user, "-P", _pw(user)] if user else []
        out = subprocess.run(
            [
                "docker",
                "exec",
                self.name,
                "mosquitto_sub",
                "-h",
                "localhost",
                "-d",
                "-W",
                "2",
                "-t",
                topic,
                *creds,
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        return out.stdout + out.stderr


@pytest.fixture
def broker(tmp_path: Path) -> Iterator[Broker]:
    conf = tmp_path / "config"
    conf.mkdir()
    (conf / "mosquitto.conf").write_text(CONF)
    (conf / "acl").write_text(ACL_BEFORE)
    (conf / "passwd").touch()
    cmds = " && ".join(f"mosquitto_passwd -b passwd {u} {_pw(u)}" for u in [*USERS, "beetroot"])
    subprocess.run(
        ["docker", "run", "--rm", "-v", f"{conf}:/c", IMAGE, "sh", "-c", f"cd /c && {cmds}"],
        check=True,
        capture_output=True,
    )
    (conf / "passwd").chmod(0o644)
    env_file = tmp_path / "mqtt.env"
    env_file.write_text(
        "".join(f"MQTT_{u.upper().replace('-', '_')}_PASSWORD={_pw(u)}\n" for u in USERS)
    )
    name = f"rover-acl-{uuid.uuid4().hex[:8]}"
    subprocess.run(
        ["docker", "run", "-d", "--rm", "--name", name, "-v", f"{conf}:/mosquitto/config", IMAGE],
        check=True,
        capture_output=True,
    )
    try:
        for _ in range(40):
            ready = subprocess.run(
                ["docker", "exec", name, "mosquitto_pub", "-h", "localhost", "-u", "admin",
                 "-P", _pw("admin"), "-t", "ready", "-m", "1"],
                capture_output=True,
                check=False,
            )  # fmt: skip
            if ready.returncode == 0:
                break
            subprocess.run(["sleep", "0.5"], check=True)
        else:
            raise RuntimeError("Mosquitto не піднявся")
        yield Broker(name, conf, env_file)
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)


def _acl(broker: Broker) -> str:
    return (broker.conf_dir / "acl").read_text()


def test_scripts_have_valid_bash_syntax() -> None:
    for script in sorted(OPS.glob("*.sh")):
        assert subprocess.run(["bash", "-n", str(script)], check=False).returncode == 0, script
        if shutil.which("shellcheck"):
            assert subprocess.run(["shellcheck", str(script)], check=False).returncode == 0


def test_template_grants_only_what_adr_0003_allows() -> None:
    text = (OPS / "acl.narrow.template").read_text()
    lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]
    assert lines == [
        "user RomisRover",
        "topic write rover/+/session",
        "user rover-ingest",
        "topic read rover/+/session",
        "user rover-viewer",
        "topic read rover/+/session",
    ]
    assert "password" not in text.lower()


def test_read_phase_adds_readers_and_keeps_rover_readwrite(broker: Broker) -> None:
    result = broker.run("apply_acl.sh", "read")
    assert result.returncode == 0, result.stderr
    acl = _acl(broker)
    assert "user rover-ingest\ntopic read rover/+/session" in acl
    assert "user rover-viewer\ntopic read rover/+/session" in acl
    assert "user RomisRover\ntopic readwrite rover/#" in acl
    assert "user beetroot\ntopic readwrite esp32test/#" in acl
    assert not (broker.conf_dir / "acl.bak").exists()
    # Пробне повідомлення від RomisRover доходить до читача (крок 5 запуску).
    assert broker.probe("RomisRover", SESSION_TOPIC) == DELIVERED


def test_narrow_phase_backs_up_and_restricts(broker: Broker) -> None:
    assert broker.run("apply_acl.sh", "read").returncode == 0
    before = _acl(broker)
    result = broker.run("apply_acl.sh", "narrow")
    assert result.returncode == 0, result.stderr
    assert (broker.conf_dir / "acl.bak").read_text() == before
    acl = _acl(broker)
    assert "topic readwrite rover/#" not in acl
    assert "user RomisRover\ntopic write rover/+/session" in acl
    assert "user admin\ntopic readwrite #" in acl and "user beetroot" in acl

    assert broker.probe("RomisRover", SESSION_TOPIC) == DELIVERED
    # Адмін читає все: заборонений запис на інший топік справді не доходить.
    assert broker.probe("RomisRover", OTHER_TOPIC, reader="admin") == NOT_DELIVERED
    # rover-ingest не може публікувати (AC-16, брокерна частина).
    assert broker.probe("rover-ingest", SESSION_TOPIC) == NOT_DELIVERED


def test_narrow_phase_refuses_without_ingest_reader(broker: Broker) -> None:
    """Без читання для rover-ingest у поточному ACL `acl.bak` не годився б для відкату."""
    before = _acl(broker)
    result = broker.run("apply_acl.sh", "narrow")
    assert result.returncode != 0
    assert "rover-ingest" in result.stderr
    assert _acl(broker) == before
    assert not (broker.conf_dir / "acl.bak").exists()


def test_rover_cannot_read_and_anonymous_is_refused(broker: Broker) -> None:
    """AC-13, AC-14. Mosquitto приймає підписку write-користувача, але нічого йому не віддає."""
    assert broker.run("apply_acl.sh", "read").returncode == 0
    # До звуження ровер (readwrite rover/#) читає: перевірка нижче змістовна.
    assert broker.probe("admin", SESSION_TOPIC, reader="RomisRover") == DELIVERED
    assert broker.run("apply_acl.sh", "narrow").returncode == 0
    assert broker.probe("admin", SESSION_TOPIC, reader="RomisRover") == NOT_DELIVERED
    assert "not authorised" in broker.sub_debug(None, SESSION_TOPIC).lower()


def _ended(minutes_ago: int) -> str:
    return (datetime.now(UTC) - timedelta(minutes=minutes_ago)).isoformat()


def test_rollback_refuses_without_backup(broker: Broker) -> None:
    before = _acl(broker)
    result = broker.run("rollback_acl.sh", _ended(60))
    assert result.returncode != 0
    assert "acl.bak" in result.stderr
    assert _acl(broker) == before


def test_rollback_refuses_inside_30_minutes_unless_now(broker: Broker) -> None:
    assert broker.run("apply_acl.sh", "read").returncode == 0
    assert broker.run("apply_acl.sh", "narrow").returncode == 0
    narrowed = _acl(broker)
    early = broker.run("rollback_acl.sh", _ended(5))
    assert early.returncode != 0
    assert "30" in early.stderr
    assert _acl(broker) == narrowed

    forced = broker.run("rollback_acl.sh", _ended(5), "--now")
    assert forced.returncode == 0, forced.stderr
    assert "user RomisRover\ntopic readwrite rover/#" in _acl(broker)


def test_rollback_restores_rover_and_keeps_ingest_reading(broker: Broker) -> None:
    """AC-20: RomisRover знову пише, rover-ingest читає."""
    assert broker.run("apply_acl.sh", "read").returncode == 0
    assert broker.run("apply_acl.sh", "narrow").returncode == 0
    assert broker.probe("RomisRover", OTHER_TOPIC, reader="admin") == NOT_DELIVERED
    result = broker.run("rollback_acl.sh", _ended(45))
    assert result.returncode == 0, result.stderr
    assert broker.probe("RomisRover", OTHER_TOPIC, reader="admin") == DELIVERED
    assert broker.probe("RomisRover", SESSION_TOPIC, reader="rover-ingest") == DELIVERED


@pytest.fixture
def launched_db(
    postgres_factory: Callable[[str], AbstractContextManager[tuple[str, str]]],
) -> Iterator[tuple[str, str, dict[str, str]]]:
    """Свіжий Postgres, створений ops/bootstrap_db.sh, з міграціями: (контейнер, URL, паролі)."""
    passwords = {
        "ROVER_OWNER_PASSWORD": "o-pw",
        "ROVER_INGEST_PASSWORD": "i-pw",
        "ROVER_VIEWER_PASSWORD": "v-pw",
    }
    with postgres_factory("postgres") as (name, url):
        env = {
            **os.environ,
            "POSTGRES_CONTAINER": name,
            "ROVER_ENV_FILE": "/nonexistent",
            **passwords,
        }
        subprocess.run(
            ["bash", str(OPS / "bootstrap_db.sh")], env=env, check=True, capture_output=True
        )
        base = url.rsplit("/", 1)[0] + "/rover"
        owner = base.replace("postgres:test", "owner:o-pw").replace(
            "postgresql://", "postgresql+psycopg://"
        )
        backend = get_backend(owner)
        with backend.lock():
            backend.apply_migrations(backend.to_apply(read_migrations(str(MIGRATIONS))))
        yield name, base, {**env}


def _verify(
    name: str, env: dict[str, str], mac: str, *extra: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(OPS / "verify_launch.sh"), mac, *extra],
        env={**env, "POSTGRES_CONTAINER": name},
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def _store(url: str, mac: str, seq: int) -> None:
    with psycopg.connect(url, user="postgres", password="test") as conn:
        conn.execute(
            "INSERT INTO sessions (mac, seq, schema_version, received_at, raw, payload) "
            "VALUES (%s, %s, 1, now(), ''::bytea, '{}')",
            (mac, seq),
        )


def test_verify_launch_reports_last_session_start_and_gap_to_27(
    launched_db: tuple[str, str, dict[str, str]],
) -> None:
    """AC-19: сесія з часом «отримано», початок обліку, розрив до 27 як довідка."""
    name, url, env = launched_db
    mac = "288485922c94"
    for seq in (31, 32):
        _store(url, mac, seq)
    result = _verify(name, env, mac)
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "остання сесія: seq=32" in out
    assert "отримано" in out
    assert "початок обліку втрат: seq=31" in out
    assert "розрив до 27: 3" in out  # 28, 29, 30 — довідка, не втрата
    assert "не втрата" in out
    assert "v-pw" not in out + result.stderr


def test_verify_launch_fails_when_no_session_and_excludes_probe_rejections(
    launched_db: tuple[str, str, dict[str, str]],
) -> None:
    name, url, env = launched_db
    with psycopg.connect(url, user="postgres", password="test") as conn:
        for topic in (SESSION_TOPIC, "rover/288485922c94/session"):
            conn.execute(
                "INSERT INTO rejected (topic, reason_code, reason_text, raw, raw_size, "
                "raw_truncated, received_at) "
                "VALUES (%s, 'not_json', 'x', ''::bytea, 0, false, now())",
                (topic,),
            )
    result = _verify(name, env, "288485922c94")
    assert result.returncode != 0
    assert "сесій немає" in result.stdout
    assert "відхилених (без пробного 000000000000): 1" in result.stdout


def test_verify_launch_rejects_malformed_mac(launched_db: tuple[str, str, dict[str, str]]) -> None:
    name, _url, env = launched_db
    assert _verify(name, env, "NOT-A-MAC; DROP TABLE sessions").returncode != 0
