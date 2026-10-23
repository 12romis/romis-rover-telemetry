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
docker run --rm --network infra -e ROVER_OWNER_DATABASE_URL \
  -v "$PWD/migrations:/migrations:ro" rover-telemetry:local \
  sh -c 'yoyo apply --batch --database "$ROVER_OWNER_DATABASE_URL" /migrations'
```

Відкат останньої міграції: `yoyo rollback --batch --database … /migrations` у тому ж виклику.
