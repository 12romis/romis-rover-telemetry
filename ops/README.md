# ops — скрипти Оператора

Скрипти запуску ingest у проді. Їх виконує Оператор на VPS; тести й агент прод не чіпають.
Порядок кроків — `docs/features/ingest/sad.md` §7 (Launch checklist). Значень паролів тут немає:
вони лише в `~/.config/claude-secrets/rover.env` (chmod 600, поза git).

## Змінні

| Змінна | Де | Для чого |
|---|---|---|
| `ROVER_OWNER_PASSWORD`, `ROVER_INGEST_PASSWORD`, `ROVER_VIEWER_PASSWORD` | `rover.env` | паролі ролей Postgres (`bootstrap_db.sh`) |
| `ROVER_OWNER_DATABASE_URL` | `rover.env` | рядок підключення `owner` для міграцій: `postgresql+psycopg://owner:<пароль>@postgres:5432/rover` (спецсимволи пароля — у URL-кодуванні) |
| `INGEST_DATABASE_URL`, `MQTT_*` | `.env` поруч із `docker-compose.yml` | налаштування сервісу `ingest` (див. `.env.example`) |
| `WEB_DATABASE_URL` | `.env` | рядок підключення `viewer` для `web` (поза цією фічею) |

## Крок 1. База і ролі

```bash
ops/bootstrap_db.sh
```

Створює роль `owner`, `ingest`, `viewer` і базу `rover` (власник `owner`). Прав на таблиці не
видає. Повторний запуск безпечний: існуюче пропускається. Паролі не друкуються. Контейнер Postgres
за замовчуванням `postgres` (інший — `POSTGRES_CONTAINER=<ім'я>`).

## Крок 2. Міграції від `owner`

Таблиці `sessions`, `rejected`, представлення `session_gaps` і `GRANT` створює міграція; запуск —
образом сервісу в мережі `infra` (рядок підключення передається змінною, не аргументом):

```bash
docker compose build ingest
set -a; . ~/.config/claude-secrets/rover.env; set +a
docker run --rm -i --network infra -e ROVER_OWNER_DATABASE_URL \
  -v "$PWD/migrations:/migrations:ro" rover-telemetry:local python - <<'PY'
import os
from yoyo import get_backend, read_migrations

backend = get_backend(os.environ["ROVER_OWNER_DATABASE_URL"])  # пароль не потрапляє в argv
migrations = read_migrations("/migrations")
with backend.lock():
    backend.apply_migrations(backend.to_apply(migrations))
PY
```

Відкат останньої міграції: у тому ж скрипті `backend.rollback_migrations(backend.to_rollback(migrations)[:1])`. `yoyo apply --database <URL>` не використовуйте: пароль у URL видно в аргументах процесу.

## Брокер: кроки 3–8

Конфігурація брокера — `/opt/mosquitto/config` (`acl`, `passwd`), контейнер `mosquitto`. Паролі
користувачів брокера — у `~/.config/claude-secrets/mqtt.env`. Пароль користувача `U` — змінна
`MQTT_<U великими, «-» → «_»>_PASSWORD`: `MQTT_ROMISROVER_PASSWORD`, `MQTT_ROVER_INGEST_PASSWORD`,
`MQTT_ROVER_VIEWER_PASSWORD` (і `MQTT_ADMIN_PASSWORD`, якщо читач проб — `admin`).

Скрипти: `apply_acl.sh` (зміна ACL за `acl.narrow.template`, чужих користувачів не чіпає),
`probe_publish.sh` (пробна публікація; паролі клієнтам іде через тимчасові файли параметрів, не `-P`), `verify_launch.sh` (перевірка в БД), `rollback_acl.sh`.

**3. Читання для ingest і viewer.** Додайте користувачів у файл паролів (пароль запитується
інтерактивно; потім збережіть його в `mqtt.env`) і розширте ACL лише читанням:

```bash
docker exec -it mosquitto mosquitto_passwd /mosquitto/config/passwd rover-ingest
docker exec -it mosquitto mosquitto_passwd /mosquitto/config/passwd rover-viewer
ops/apply_acl.sh read          # RomisRover лишається readwrite rover/#; SIGHUP
```

**4. Запуск `ingest`** під `rover-ingest` (значення — у `.env`, див. `.env.example`):

```bash
docker compose up -d ingest && docker logs -f ingest
```

Порівняйте `seq` першого отриманого звіту з 27: якщо є черга від брокера, він буде більшим
(spec §8, D3).

**5. Пробне повідомлення наскрізь.** Проба — не JSON, тож має потрапити в `rejected` із топіком
`rover/000000000000/session` (рядок `event=rejected` у логу):

```bash
ops/probe_publish.sh RomisRover rover/000000000000/session     # ДОСТАВЛЕНО
```

**6. Звуження ACL** (`acl` → `acl.bak`, `RomisRover` лише `write rover/+/session`, SIGHUP) і проби:

```bash
ops/apply_acl.sh narrow
ops/probe_publish.sh RomisRover rover/000000000000/session                  # ДОСТАВЛЕНО (код 0)
MQTT_PROBE_READER=admin ops/probe_publish.sh RomisRover rover/000000000000/other   # НЕ ДОСТАВЛЕНО (код 3)
ops/probe_publish.sh rover-ingest rover/000000000000/session                # НЕ ДОСТАВЛЕНО (код 3)
```

Заборонену публікацію брокер відкидає мовчки (`PUBACK RC:0`, код виходу `mosquitto_pub` 0), тож
перевіряє лише доставка читачу. Читач за замовчуванням `rover-viewer` бачить лише `rover/+/session`;
щоб довести заборону запису на інший топік, читач має бути `admin`.

**AC-13 / AC-14 на живому брокері:** `RomisRover` не отримує звіти
(`MQTT_PROBE_READER=RomisRover ops/probe_publish.sh admin rover/000000000000/session` → код 3).
Анонімне підключення перевіряє `ops/apply_acl.sh check-anon` (так само автоматично перед `narrow`):
вона підключається до живого брокера без облікових даних і очікує `not authorised`.

**7. Наступний реальний звіт** (AC-19):

```bash
ops/verify_launch.sh 288485922c94
```

Друкує останню сесію з часом «отримано», початок обліку втрат (найменший збережений `seq`) і
розрив до 27. Розрив — довідка для ручної перевірки, а не втрата. Код виходу 1 — сесій немає.

**8. Невдача** (AC-20). Лише коли відомо, що ровер завершив виїзд, минуло 30 хв, а `verify_launch.sh`
не знаходить звіту. Відсутність виїздів сама по собі відкату не викликає:

```bash
ops/rollback_acl.sh 2026-10-26T14:05:00+03:00      # час завершення виїзду; --now обходить 30 хв
```

Відновлює `acl.bak` (з читанням для `rover-ingest`), надсилає SIGHUP і перевіряє, що `RomisRover`
знову пише. Без `acl.bak` скрипт відмовляє, нічого не змінюючи.
