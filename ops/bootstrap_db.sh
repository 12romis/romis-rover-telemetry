#!/usr/bin/env bash
# Крок 1 запуску ingest (sad.md §7): створює БД `rover` і ролі owner, ingest, viewer у Postgres.
# Запускає Оператор від суперкористувача Postgres. Прав на таблиці не видає: їх дають GRANT
# у міграціях. Повторний запуск безпечний: існуюче пропускається. Паролі не друкуються.
#
# Змінні (лише назви; значення — у ~/.config/claude-secrets/rover.env, chmod 600, поза git):
#   ROVER_OWNER_PASSWORD, ROVER_INGEST_PASSWORD, ROVER_VIEWER_PASSWORD
# Необов'язково: ROVER_ENV_FILE (шлях до rover.env), POSTGRES_CONTAINER (за замовчуванням postgres).
set -euo pipefail

ENV_FILE="${ROVER_ENV_FILE:-$HOME/.config/claude-secrets/rover.env}"
CONTAINER="${POSTGRES_CONTAINER:-postgres}"

if [[ -f "$ENV_FILE" ]]; then
    set -a
    # shellcheck source=/dev/null
    source "$ENV_FILE"
    set +a
fi

for var in ROVER_OWNER_PASSWORD ROVER_INGEST_PASSWORD ROVER_VIEWER_PASSWORD; do
    if [[ -z "${!var:-}" ]]; then
        echo "Не задано змінну $var (очікується в $ENV_FILE або в середовищі)." >&2
        exit 1
    fi
done
export ROVER_OWNER_PASSWORD ROVER_INGEST_PASSWORD ROVER_VIEWER_PASSWORD

# Паролі передаються змінними середовища (-e VAR без значення), а не аргументами: їх не видно
# у списку процесів.
psql_su() {
    docker exec -i \
        -e ROVER_OWNER_PASSWORD -e ROVER_INGEST_PASSWORD -e ROVER_VIEWER_PASSWORD \
        "$CONTAINER" psql -U postgres -X -q -v ON_ERROR_STOP=1 "$@"
}

exists() {
    [[ "$(psql_su -tA -c "$1")" == "1" ]]
}

for pair in owner:ROVER_OWNER_PASSWORD ingest:ROVER_INGEST_PASSWORD viewer:ROVER_VIEWER_PASSWORD; do
    role="${pair%%:*}"
    var="${pair##*:}"
    if exists "SELECT 1 FROM pg_roles WHERE rolname = '$role'"; then
        echo "Роль $role вже існує: пропущено."
    else
        psql_su <<SQL
\getenv pw $var
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', '$role', :'pw') \gexec
SQL
        echo "Створено роль $role."
    fi
done

if exists "SELECT 1 FROM pg_database WHERE datname = 'rover'"; then
    echo "База rover вже існує: пропущено."
else
    psql_su -c "CREATE DATABASE rover OWNER owner"
    echo "Створено базу rover (власник owner)."
fi
