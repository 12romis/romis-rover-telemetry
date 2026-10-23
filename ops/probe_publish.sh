#!/usr/bin/env bash
# Пробна публікація: <user> публікує в <topic>, читач перевіряє, чи повідомлення дійшло.
#   probe_publish.sh <user> <topic> [повідомлення]
# Заборонений запис брокер мовчки відкидає (PUBACK RC:0, код виходу 0), тож результат — лише
# доставка читачу. Код виходу: 0 доставлено, 3 не доставлено, 1/2 помилка запуску.
# Читач: MQTT_PROBE_READER (за замовчуванням rover-viewer). Він бачить лише те, що йому дозволено
# читати: щоб довести, що запис на ІНШИЙ топік заборонено, читач має бути admin.
# Пароль користувача U — змінна MQTT_<U великими, '-' -> '_'>_PASSWORD у mqtt.env
# (RomisRover -> MQTT_ROMISROVER_PASSWORD, rover-ingest -> MQTT_ROVER_INGEST_PASSWORD).
# Змінні: MQTT_ENV_FILE (~/.config/claude-secrets/mqtt.env), MOSQUITTO_CONTAINER (mosquitto).
set -euo pipefail

[[ $# -ge 2 ]] || { echo "Використання: $0 <user> <topic> [повідомлення]" >&2; exit 2; }
user="$1"
topic="$2"
message="${3:-probe-$(date +%s)-$RANDOM}"
reader="${MQTT_PROBE_READER:-rover-viewer}"
ENV_FILE="${MQTT_ENV_FILE:-$HOME/.config/claude-secrets/mqtt.env}"
CONTAINER="${MOSQUITTO_CONTAINER:-mosquitto}"

pw_var() { local u="${1^^}"; echo "MQTT_${u//-/_}_PASSWORD"; }

if [[ -f "$ENV_FILE" ]]; then
    set -a
    # shellcheck source=/dev/null
    source "$ENV_FILE"
    set +a
fi
pub_var="$(pw_var "$user")"
sub_var="$(pw_var "$reader")"
for var in "$pub_var" "$sub_var"; do
    [[ -n "${!var:-}" ]] || { echo "Не задано змінну $var (очікується в $ENV_FILE)." >&2; exit 1; }
done
export PUB_PW="${!pub_var}" SUB_PW="${!sub_var}"

# Усе виконується всередині контейнера брокера, паролі йдуть змінними середовища.
received="$(docker exec -e PUB_PW -e SUB_PW "$CONTAINER" sh -c '
    out="$(mktemp)"
    mosquitto_sub -h localhost -u "$1" -P "$SUB_PW" -t "$2" -q 1 -C 1 -W 5 > "$out" &
    sub=$!
    sleep 1
    mosquitto_pub -h localhost -u "$3" -P "$PUB_PW" -t "$2" -q 1 -m "$4"
    wait "$sub" || true
    cat "$out"
    rm -f "$out"
' sh "$reader" "$topic" "$user" "$message")"

if [[ "$received" == "$message" ]]; then
    echo "ДОСТАВЛЕНО: $user -> $topic (бачить $reader)"
    exit 0
fi
echo "НЕ ДОСТАВЛЕНО: $user -> $topic (читач $reader не отримав)"
exit 3
