#!/usr/bin/env bash
# Перевірка публікації дашборду (AC-15, конституція №12).
#   verify_dashboard.sh          — лише локальна конфігурація compose: у `web` немає опублікованих
#                                  портів і є alias `rover-web`; до мережі не ходить.
#   verify_dashboard.sh <URL>    — додатково для https-адреси: код 200, чотири заголовки безпеки,
#                                  у HTML немає посилань на сторонні вузли.
# Секретів не друкує. Змінні: COMPOSE_FILE_PATH (docker-compose.yml у корені репозиторію).
# Коди виходу: 0 — усе гаразд, 1 — перевірка не пройдена, 2 — неправильне використання.
set -euo pipefail

url="${1:-}"
if [[ -n "$url" && ! "$url" =~ ^https://[^/]+(/.*)?$ ]]; then
    echo "Використання: $0 [https://адреса] — лише https (конституція №12)." >&2
    exit 2
fi

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compose_file="${COMPOSE_FILE_PATH:-$root/docker-compose.yml}"
fail() { echo "ПОМИЛКА: $*" >&2; exit 1; }

config="$(docker compose -f "$compose_file" config --format json)" || fail "compose-конфігурація не читається"
printf '%s' "$config" | python3 -c '
import json, sys
web = json.load(sys.stdin)["services"]["web"]
if web.get("ports"):
    print("ПОМИЛКА: сервіс web публікує порт на хост (конституція №12)", file=sys.stderr)
    sys.exit(1)
aliases = (web.get("networks") or {}).get("infra", {}).get("aliases", [])
if "rover-web" not in aliases:
    print("ПОМИЛКА: у мережі infra немає alias rover-web", file=sys.stderr)
    sys.exit(1)
' || exit 1
echo "compose: портів не опубліковано, alias rover-web є"

[[ -z "$url" ]] && exit 0

headers="$(mktemp)"
body="$(mktemp)"
trap 'rm -f "$headers" "$body"' EXIT
code="$(curl -sS -o "$body" -D "$headers" -w '%{http_code}' --max-time 10 "$url")" || fail "адреса недоступна"
[[ "$code" == "200" ]] || fail "очікувався код 200, отримано $code"

check_header() {
    grep -iq "^$1: $2" "$headers" || fail "заголовок $1: $2 відсутній"
}
check_header "Content-Security-Policy" "default-src 'self'"
check_header "Cache-Control" "no-store"
check_header "X-Content-Type-Options" "nosniff"
check_header "Referrer-Policy" "no-referrer"

own_host="$(printf '%s' "$url" | sed -E 's#^https://([^/:]+).*#\1#')"
foreign="$(grep -oE '(src|href)="https?://[^/"]+' "$body" | sed -E 's#.*//##' | grep -vxF "$own_host" || true)"
[[ -z "$foreign" ]] || fail "сторінка посилається на сторонні вузли: $(printf '%s' "$foreign" | tr '\n' ' ')"
echo "сторінка: 200, заголовки безпеки на місці, сторонніх вузлів немає"
