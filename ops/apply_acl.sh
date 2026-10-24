#!/usr/bin/env bash
# Змінює ACL брокера за ops/acl.narrow.template, не чіпаючи чужих користувачів (admin, beetroot).
# Запускає Оператор на VPS.
#   apply_acl.sh read    крок 3: додає rover-ingest і rover-viewer (лише читання); RomisRover без змін
#   apply_acl.sh narrow  крок 6: acl -> acl.bak, потім RomisRover лише `write rover/+/session`;
#                        відмовляє, якщо брокер пускає анонімів (AC-14) або RomisRover уже звужено
#                        (інакше acl.bak затерся б звуженим ACL, і відкат нічого б не повернув)
#   apply_acl.sh check-anon  лише перевірка, що анонімне підключення брокер відхиляє (AC-14)
# Після зміни брокеру надсилається SIGHUP. Паролі тут не потрібні.
# Змінні: ACL_DIR (за замовчуванням /opt/mosquitto/config), MOSQUITTO_CONTAINER (mosquitto).
set -euo pipefail

ACL_DIR="${ACL_DIR:-/opt/mosquitto/config}"
CONTAINER="${MOSQUITTO_CONTAINER:-mosquitto}"
TEMPLATE="$(dirname "${BASH_SOURCE[0]}")/acl.narrow.template"
ACL="$ACL_DIR/acl"

# Блок користувача: рядок `user NAME` і все до наступного `user`.
block() { awk -v u="$2" '$1 == "user" { p = ($2 == u) } p' "$1"; }
without() { awk -v u="$2" '$1 == "user" { skip = ($2 == u) } !skip' "$1"; }

# Записує вміст у наявний файл на місці (зберігає inode і права, важливо для bind mount).
# Спершу збирає все в тимчасовий файл: пряме `> "$ACL"` усікло б файл раніше, ніж його прочитано.
write_acl() {
    local tmp
    tmp="$(mktemp)"
    cat > "$tmp"
    cat "$tmp" > "$ACL"
    rm -f "$tmp"
}

reload() {
    docker kill --signal=SIGHUP "$CONTAINER" > /dev/null
    echo "SIGHUP надіслано контейнеру $CONTAINER."
}

# AC-14: перевіряє живий брокер, а не файл конфігурації (include, listener-и тощо його обходять).
# Коди: 0 аноніми відхилено, 1 брокер їх пускає, 2 перевірку не вдалося виконати (контейнер не
# запущено, немає mosquitto_sub): це не відповідь про брокер, тож повідомлення інше.
anonymous_refused() {
    local out
    if [[ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER" 2> /dev/null)" != "true" ]]; then
        return 2
    fi
    out="$(docker exec "$CONTAINER" mosquitto_sub -h localhost -d -W 2 -t 'rover/+/session' 2>&1)" \
        || [[ $? -ne 126 && $? -ne 127 ]] || return 2
    grep -qi 'not authorised' <<< "$out"
}

# Друкує підсумок перевірки й завершує скрипт, якщо аноніми не відхилено.
require_anonymous_refused() {
    local code=0
    anonymous_refused || code=$?
    case "$code" in
        0) ;;
        2) echo "Не вдалося виконати перевірку анонімного доступу в контейнері $CONTAINER" \
            "(не запущено чи немає mosquitto_sub)." >&2
            exit 1 ;;
        *) echo "Брокер приймає анонімне підключення: спершу allow_anonymous false (AC-14)." >&2
            exit 1 ;;
    esac
}

mode="${1:-}"
[[ -f "$ACL" ]] || { echo "Немає файла $ACL." >&2; exit 1; }

case "$mode" in
    read)
        {
            without "$ACL" rover-ingest | awk -v u=rover-viewer '$1 == "user" { skip = ($2 == u) } !skip'
            echo
            block "$TEMPLATE" rover-ingest
            echo
            block "$TEMPLATE" rover-viewer
        } | write_acl
        echo "ACL: додано читання для rover-ingest і rover-viewer; RomisRover без змін."
        reload
        ;;
    check-anon)
        require_anonymous_refused
        echo "Анонімне підключення відхилено."
        ;;
    narrow)
        require_anonymous_refused
        # Уже звужено: блок збігається з шаблоном або (після ручної правки) в ньому немає readwrite.
        # Тоді acl.bak — єдина копія повного доступу, і затирати його не можна.
        current="$(block "$ACL" RomisRover)"
        if [[ "$current" == "$(block "$TEMPLATE" RomisRover)" ]] ||
            { [[ -f "$ACL_DIR/acl.bak" ]] && ! grep -q 'readwrite' <<< "$current"; }; then
            echo "RomisRover у $ACL уже звужено: повторний запуск затер би acl.bak звуженим ACL." >&2
            exit 1
        fi
        if ! grep -qE '^user[[:space:]]+rover-ingest[[:space:]]*$' "$ACL"; then
            echo "У $ACL немає rover-ingest: спершу 'apply_acl.sh read'. Без цього acl.bak" \
                "не збереже читання для ingest і відкат його забере (AC-20)." >&2
            exit 1
        fi
        cp -p "$ACL" "$ACL_DIR/acl.bak"
        echo "Збережено копію: $ACL_DIR/acl.bak"
        {
            without "$ACL" RomisRover
            echo
            block "$TEMPLATE" RomisRover
        } | write_acl
        echo "ACL: RomisRover лише write rover/+/session."
        reload
        ;;
    *)
        echo "Використання: $0 read|narrow|check-anon" >&2
        exit 2
        ;;
esac
