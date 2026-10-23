#!/usr/bin/env bash
# Змінює ACL брокера за ops/acl.narrow.template, не чіпаючи чужих користувачів (admin, beetroot).
# Запускає Оператор на VPS.
#   apply_acl.sh read    крок 3: додає rover-ingest і rover-viewer (лише читання); RomisRover без змін
#   apply_acl.sh narrow  крок 6: acl -> acl.bak, потім RomisRover лише `write rover/+/session`
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
    narrow)
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
        echo "Використання: $0 read|narrow" >&2
        exit 2
        ;;
esac
