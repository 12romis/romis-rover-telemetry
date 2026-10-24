#!/usr/bin/env bash
# Перевірка запуску (AC-19): що ровер <mac> має збережені сесії, коли отримано останню, звідки
# починається облік втрат і який розрив до останнього відомого номера (27).
#   verify_launch.sh <mac>
# Читає під роллю viewer (пароль ROVER_VIEWER_PASSWORD із rover.env). Розрив до 27 — довідка для
# ручної перевірки, а не втрата. Відхилені пробні публікації (мак 000000000000) не враховуються.
# Код виходу 1, якщо збережених сесій цього ровера немає (перевірку пройдено не вважати).
# Змінні: ROVER_ENV_FILE (~/.config/claude-secrets/rover.env), POSTGRES_CONTAINER (postgres),
# KNOWN_LAST_SEQ (27, spec AC-19).
set -euo pipefail

mac="${1:-}"
[[ "$mac" =~ ^[0-9a-f]{12}$ ]] || { echo "Використання: $0 <mac: 12 hex нижнім регістром>" >&2; exit 2; }
ENV_FILE="${ROVER_ENV_FILE:-$HOME/.config/claude-secrets/rover.env}"
CONTAINER="${POSTGRES_CONTAINER:-postgres}"
KNOWN_LAST_SEQ="${KNOWN_LAST_SEQ:-27}"

if [[ -f "$ENV_FILE" ]]; then
    set -a
    # shellcheck source=/dev/null
    source "$ENV_FILE"
    set +a
fi
[[ -n "${ROVER_VIEWER_PASSWORD:-}" ]] || {
    echo "Не задано змінну ROVER_VIEWER_PASSWORD (очікується в $ENV_FILE)." >&2
    exit 1
}
export PGPASSWORD="$ROVER_VIEWER_PASSWORD"

query() {
    docker exec -i -e PGPASSWORD "$CONTAINER" \
        psql -U viewer -d rover -X -tA -v ON_ERROR_STOP=1 -v mac="$mac" -v known="$KNOWN_LAST_SEQ" "$@"
}

summary="$(query <<'SQL'
SELECT count(*) || '|' || coalesce(min(seq)::text, '') || '|' || coalesce(max(seq)::text, '')
FROM sessions WHERE mac = :'mac';
SQL
)"
IFS='|' read -r count first_seq _last <<< "$summary"
rejected="$(query <<'SQL'
SELECT count(*) FROM rejected WHERE topic <> 'rover/000000000000/session';
SQL
)"

echo "ровер: $mac"
echo "відхилених (без пробного 000000000000): $rejected"
if [[ "$count" == "0" ]]; then
    echo "сесій немає: перевірку запуску не пройдено."
    exit 1
fi

echo "збережено сесій: $count"
query <<'SQL' | sed -e 's/^/остання сесія: /'
SELECT 'seq=' || seq || ', отримано ' || to_char(received_at AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS') || ' UTC'
FROM sessions WHERE mac = :'mac' ORDER BY received_at DESC, seq DESC LIMIT 1;
SQL
echo "початок обліку втрат: seq=$first_seq (найменший збережений)"
if ((first_seq > KNOWN_LAST_SEQ + 1)); then
    echo "розрив до $KNOWN_LAST_SEQ: $((first_seq - KNOWN_LAST_SEQ - 1)) (довідка для ручної перевірки, не втрата)"
else
    echo "розрив до $KNOWN_LAST_SEQ: 0"
fi
