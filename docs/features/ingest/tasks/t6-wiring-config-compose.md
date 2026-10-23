---
id: T6
title: "Розділити налаштування й паролі: INGEST_DATABASE_URL, MQTT_*, compose environment"
layer: "wiring"
deps: []
blocks: ["T10"]
acs: ["AC-16"]
files_hint: ["src/rover_telemetry/config.py", "docker-compose.yml", ".env.example", "tests/unit/test_config.py"]
owner: "12romis"
estimate: "S"
context_budget: "S"
status: "todo"
step: ""
---

## Why (user story)

> **As a** Оператор сервера
> **I want** щоб ровер, сервіс приймання й дашборд мали лише ті права, що потрібні для їхньої ролі
> **So that** витік одного пароля не дозволяє підробити звіт чи змінити збережені дані
>
> — `spec.md §4, US-08, verbatim` · full text: [spec.md](../spec.md)

Забирає в `ingest` чужі паролі: рядок підключення до БД роздається на контейнер, у конфігурації немає значень за замовчуванням для паролів.

## Inlined context

> **Hard rule:** **Секрети поза git.** Паролі, токени, рядки підключення — лише в `~/.config/claude-secrets/rover.env` (chmod 600) або `.env`, що ігнорується git. У репозиторії — `.env.example` з назвами змінних.
>
> — `constitution.md, №9, verbatim` · full text: [constitution.md](../../../constitution.md)

> **Hard rule:** **Найменші права.** Окремі облікові записи брокера (ровер — лише запис у `rover/+/session`; ingest — лише читання) і окремі ролі Postgres (ingest — лише вставка; дашборд — лише читання).
>
> — `constitution.md, №10, verbatim` · full text: [constitution.md](../../../constitution.md)

> `ingest` — другий сервіс у `docker-compose.yml` (той самий образ `rover-telemetry`, команда `python -m rover_telemetry.ingest`), мережа `infra`, порти на хост не публікуються (конституція №12), `restart: unless-stopped`. Одна репліка: другий екземпляр із тим самим client id витісняв би перший. Рядок підключення до БД роздається на контейнер (`INGEST_DATABASE_URL` лише в `ingest`, `WEB_DATABASE_URL` лише в `web`, через `environment:`), бо поточний `env_file: .env` дає обом сервісам увесь файл — це змінюється в задачах (compose, `.env.example`, `config.py`). Сховище — наявний Postgres у мережі `infra`. Брокер змінюється лише ACL і файлом паролів.
>
> — `sad.md §7, Deployment view, verbatim` · full text: [sad.md](../sad.md)

> └── config.py            # INGEST_DATABASE_URL, MQTT_*, client id; без значень за замовчуванням для паролів
>
> — `sad.md §5, Internal decomposition, abridged` · full text: [sad.md](../sad.md)

> **Chosen:** варіант 1. Повідомлення обробляються по одному в callback: розбір → INSERT → COMMIT → `ack`; з кожного повідомлення COMMIT робиться окремо (без пакетного запису). Помилка запису чи COMMIT — вихід із кодом 1 без `ack`.
>
> — `adr/0001, Decision outcome, abridged` · full text: [adr/0001-commit-before-ack-and-exit-on-storage-failure.md](../adr/0001-commit-before-ack-and-exit-on-storage-failure.md)

**Fallback:** insufficient or contradicted by the code → read the named file in full ([spec.md](../spec.md) · [sad.md](../sad.md) · [data-model.md](../data-model.md) · [adr/](../adr/)) and follow it. Do not guess.

## Data delta

No DB changes.

## API contract

Internal — no API surface.

## Acceptance criteria

### AC-16 (US-08) — authorization

> **Given** облікові дані сервісу приймання
> **When** вони використані, щоб змінити чи видалити вже збережену сесію або щоб надіслати звіт брокеру
> **Then** сховище чи брокер відмовляє: сервіс лише читає звіти з брокера й дописує нові записи
>
> — `spec.md §5, AC-16, verbatim` · full text: [spec.md](../spec.md)

## Checklist

- [ ] `config.py`: замість єдиного `DATABASE_URL` — `IngestSettings` (`INGEST_DATABASE_URL`, `MQTT_HOST`, `MQTT_PORT`, `MQTT_USERNAME`, `MQTT_PASSWORD`, `MQTT_CLIENT_ID`, `DB_WAIT_INTERVAL_S`, `DB_CONNECT_TIMEOUT_S`) і `WebSettings` (`WEB_DATABASE_URL`); `from_env` без значень за замовчуванням для `*_PASSWORD`/`*_URL` (порожній рядок → помилка конфігурації на старті).
- [ ] Значення за замовчуванням для `DB_WAIT_INTERVAL_S` (2 с) і `DB_CONNECT_TIMEOUT_S` (5 с): ADR-0001 залишає їх цьому розбиттю («кілька секунд», «менше за keepalive»); зафіксувати в коментарі, що це вибір `tasks`, а не контракт.
- [ ] `docker-compose.yml`: прибрати `env_file: .env` з обох служб; `ingest` отримує лише `INGEST_DATABASE_URL`, `MQTT_*` через `environment: ${…}`, `web` — лише `WEB_DATABASE_URL`; `restart: unless-stopped` і мережа `infra` лишаються, `ports` немає.
- [ ] `.env.example`: назви нових змінних без значень; стару `DATABASE_URL` прибрати.
- [ ] `tests/unit/test_config.py`: відсутній пароль → помилка; `IngestSettings` не містить `WEB_DATABASE_URL`, `WebSettings` — `INGEST_DATABASE_URL`.

## Edge cases

| Case | Behaviour |
|---|---|
| Порожній `INGEST_DATABASE_URL` чи `MQTT_PASSWORD` | Помилка конфігурації на старті, процес не запускається |
| Є `.env` із обома рядками | Кожна служба бачить лише свої змінні через `environment:` |
| `MQTT_CLIENT_ID` не задано | Фіксований client id за замовчуванням `rover-ingest` (постійна сесія потребує сталого id, конституція №7) |

## Definition of Done

- [ ] `pytest tests/unit/test_config.py` проходить
- [ ] `docker compose config` не показує `INGEST_DATABASE_URL` у `web` і навпаки
- [ ] у репозиторії немає значень паролів (`.env.example` — лише назви)
- [ ] `ruff`, `mypy src` без попереджень
- [ ] every Hard Rule inlined above still holds
- [ ] lint + vet clean (`ruff check . && ruff format --check . && mypy src`)
