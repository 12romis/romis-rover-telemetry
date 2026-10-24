#!/usr/bin/env bash
# Відкат звуження ACL (AC-20): acl.bak -> acl, SIGHUP, пробна публікація від RomisRover.
#   rollback_acl.sh <коли_завершився_виїзд> [--now]
# <коли_завершився_виїзд> — час, коли відомо, що ровер завершив виїзд (ISO 8601, наприклад
# 2026-10-26T14:05:00+03:00). Скрипт відмовляє, якщо минуло менше 30 хв (рішення власника, spec §8),
# і лише --now це обходить. Без acl.bak відмовляє, нічого не змінюючи. Перед відкатом переконайтеся
# через ops/verify_launch.sh, що звіту серед збережених справді немає.
# Змінні: ACL_DIR (/opt/mosquitto/config), MOSQUITTO_CONTAINER (mosquitto), MQTT_ENV_FILE.
set -euo pipefail

ACL_DIR="${ACL_DIR:-/opt/mosquitto/config}"
CONTAINER="${MOSQUITTO_CONTAINER:-mosquitto}"
WINDOW_S=$((30 * 60))
HERE="$(dirname "${BASH_SOURCE[0]}")"

[[ $# -ge 1 ]] || { echo "Використання: $0 <коли_завершився_виїзд> [--now]" >&2; exit 2; }
ended="$1"
force="${2:-}"

[[ -f "$ACL_DIR/acl.bak" ]] || { echo "Немає $ACL_DIR/acl.bak: нічого відкочувати." >&2; exit 1; }

ended_s="$(date -d "$ended" +%s)" || { echo "Не розібрано час '$ended'." >&2; exit 2; }
elapsed=$(($(date +%s) - ended_s))
if [[ "$force" != "--now" ]] && ((elapsed < WINDOW_S)); then
    echo "З завершення виїзду минуло $((elapsed / 60)) хв, треба 30. Не відкочую (обійти: --now)." >&2
    exit 1
fi

if ! grep -qE '^user[[:space:]]+rover-ingest[[:space:]]*$' "$ACL_DIR/acl.bak"; then
    echo "У acl.bak немає rover-ingest: відкат забрав би в ingest читання. Не відкочую." >&2
    exit 1
fi

cat "$ACL_DIR/acl.bak" > "$ACL_DIR/acl"
docker kill --signal=SIGHUP "$CONTAINER" > /dev/null
echo "ACL відновлено з acl.bak, SIGHUP надіслано."

# Ровер знову має писати, читання для rover-ingest лишилося.
MQTT_PROBE_READER=rover-ingest "$HERE/probe_publish.sh" RomisRover "rover/000000000000/session"
